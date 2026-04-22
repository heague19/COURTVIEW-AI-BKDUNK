# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline/fusion
파일: tracking_fusion.py
설명: 멀티카메라 트래킹 융합 오케스트레이터
      - 각 카메라 뷰의 트래킹 결과(로컬 track_id)를 글로벌 ID로 통합
      - player_detector.detect_multi_view()가 이미 크로스뷰 매칭 수행
      - ReID는 digit(등번호) + team(색상)으로 대체 (별도 모델 불필요)
      - 이 모듈은 프레임 간 글로벌 ID 유지 + 트래킹 결과 수집만 담당
      - IoU, 코사인 유사도 등은 기존 모듈에 구현 완료

      데이터 흐름:
        detection_fusion 결과 (SceneFusionResult.player_result)
          → 뷰별 선수 목록 (fused_objects)
          → 글로벌 ID 할당/갱신 (이전 프레임 매핑 유지)
          → GlobalTrackResult

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/pipeline/fusion/detection_fusion.py: SceneFusionResult
    - shared/dto/detection_dto.py: DetectedObject
    - shared/constants/tracking_constants.py: MAX_TRACK_AGE

소비자:
    - engine/pipeline/frame_pipeline.py: 🔴 FRAME 파이프라인 후처리
    - engine/pipeline/event_pipeline.py: 🟠 EVENT 선수 이벤트 연결
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from shared.constants.tracking_constants import MAX_TRACK_AGE

_logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_GLOBAL_TRACKS: Final[int] = 30
_MAX_HISTORY: Final[int] = 200
_MATCH_THRESHOLD: Final[float] = 0.4


# =============================================================================
# 글로벌 트랙
# =============================================================================
@dataclass(slots=True)
class GlobalTrack:
    """
    프레임 간 유지되는 글로벌 트랙.

    Attributes:
        global_id: 글로벌 고유 ID
        last_bbox: 마지막 바운딩 박스 (x1, y1, x2, y2)
        last_position_3d: 마지막 3D 위치 (x, y, z) — 미터, None 가능
        team_id: 팀 ID
        jersey_number: 등번호 (-1 = 미식별)
        frames_since_seen: 마지막 관측 이후 프레임 수
        total_frames: 총 관측 프레임 수
    """

    global_id: int = -1
    last_bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    last_position_3d: tuple[float, float, float] | None = None
    team_id: str = ""
    jersey_number: int = -1
    frames_since_seen: int = 0
    total_frames: int = 0
    _team_history: list[str] = field(default_factory=list)  # 최근 팀 분류 이력

    def update_team(self, raw_team_id: str, window: int = 20) -> None:
        """팀 분류 스무딩 — 최근 N프레임 다수결로 team_id 확정."""
        if raw_team_id:
            self._team_history.append(raw_team_id)
            if len(self._team_history) > window:
                self._team_history = self._team_history[-window:]
        # 다수결 (unknown 제외)
        known = [t for t in self._team_history if t and t != "unknown"]
        if known:
            from collections import Counter
            self.team_id = Counter(known).most_common(1)[0][0]


# =============================================================================
# 융합 결과
# =============================================================================
@dataclass(slots=True)
class TrackingFusionResult:
    """
    트래킹 융합 결과.

    Attributes:
        frame_index: 프레임 인덱스
        active_tracks: 활성 글로벌 트랙 목록
        new_tracks: 이번 프레임에 신규 생성된 트랙 수
        lost_tracks: 이번 프레임에 소실된 트랙 수
        processing_time_ms: 처리 시간 (ms)
    """

    frame_index: int = 0
    active_tracks: list[GlobalTrack] = field(default_factory=list)
    new_tracks: int = 0
    lost_tracks: int = 0
    processing_time_ms: float = 0.0


# =============================================================================
# 트래킹 융합 오케스트레이터
# =============================================================================
class TrackingFusion:
    """
    프레임 간 글로벌 ID 유지 오케스트레이터.

    detection_fusion의 player_result에서 융합된 선수 목록을 받아
    이전 프레임의 글로벌 트랙과 매핑합니다.

    크로스뷰 매칭(IoU/ReID)은 detection 모듈이 이미 수행했으므로,
    이 모듈은 프레임 간 연속성(temporal association)만 담당합니다:
      1. 이전 글로벌 트랙 ↔ 현재 융합 선수 IoU 매칭
      2. 매칭 성공 → 트랙 갱신
      3. 매칭 실패(신규) → 새 글로벌 ID 발급
      4. 미관측 트랙 → age 증가, MAX_TRACK_AGE 초과 시 삭제

    Attributes:
        _active_globals: 활성 글로벌 트랙
        _next_global_id: 다음 글로벌 ID
        _max_age: 최대 미관측 허용 프레임
        _match_threshold: IoU 매칭 임계치
        _history: 융합 이력
        _total_fusions: 총 융합 횟수
        _lock: 스레드 안전 잠금
    """

    __slots__ = (
        "_active_globals",
        "_next_global_id",
        "_max_age",
        "_match_threshold",
        "_history",
        "_total_fusions",
        "_lock",
    )

    def __init__(
        self,
        max_age: int = MAX_TRACK_AGE,
        match_threshold: float = _MATCH_THRESHOLD,
    ) -> None:
        self._active_globals: dict[int, GlobalTrack] = {}
        self._next_global_id: int = 1
        self._max_age: int = max_age
        self._match_threshold: float = match_threshold
        self._history: list[TrackingFusionResult] = []
        self._total_fusions: int = 0
        self._lock: RLock = RLock()

    # =========================================================================
    # 융합 실행
    # =========================================================================
    def fuse(
        self,
        fused_players: list[dict[str, float]],
        frame_index: int = 0,
    ) -> TrackingFusionResult:
        """
        현재 프레임의 융합된 선수 목록을 글로벌 트랙과 매칭.

        Args:
            fused_players: 융합된 선수 목록. 각 항목은 최소
                           {"x1", "y1", "x2", "y2"} bbox 키 포함.
                           선택: "team_id", "jersey_number", "x3d", "y3d", "z3d"
            frame_index: 프레임 인덱스

        Returns:
            TrackingFusionResult
        """
        t0 = time.perf_counter()
        new_count = 0
        lost_count = 0

        with self._lock:
            # 1. 미관측 트랙 age 증가
            for track in self._active_globals.values():
                track.frames_since_seen += 1

            # 2. 현재 선수 → 글로벌 트랙 매칭
            matched_globals: set[int] = set()

            for player in fused_players:
                bbox = (
                    player.get("x1", 0.0),
                    player.get("y1", 0.0),
                    player.get("x2", 0.0),
                    player.get("y2", 0.0),
                )

                best_id = self._find_best_match(bbox, matched_globals)

                if best_id is not None:
                    # 기존 트랙 갱신
                    track = self._active_globals[best_id]
                    track.last_bbox = bbox
                    track.frames_since_seen = 0
                    track.total_frames += 1
                    if "team_id" in player:
                        track.update_team(str(player["team_id"]))
                    if "jersey_number" in player:
                        track.jersey_number = int(player["jersey_number"])
                    if "x3d" in player:
                        track.last_position_3d = (
                            player["x3d"], player["y3d"], player["z3d"],
                        )
                    matched_globals.add(best_id)
                else:
                    # 신규 트랙 생성
                    gid = self._next_global_id
                    self._next_global_id += 1
                    new_track = GlobalTrack(
                        global_id=gid,
                        last_bbox=bbox,
                        team_id=str(player.get("team_id", "")),
                        jersey_number=int(player.get("jersey_number", -1)),
                        frames_since_seen=0,
                        total_frames=1,
                    )
                    if "x3d" in player:
                        new_track.last_position_3d = (
                            player["x3d"], player["y3d"], player["z3d"],
                        )
                    self._active_globals[gid] = new_track
                    matched_globals.add(gid)
                    new_count += 1

            # 3. 오래된 트랙 삭제
            expired = [
                gid for gid, t in self._active_globals.items()
                if t.frames_since_seen > self._max_age
            ]
            for gid in expired:
                del self._active_globals[gid]
                lost_count += 1

            # 결과
            active_list = list(self._active_globals.values())

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        result = TrackingFusionResult(
            frame_index=frame_index,
            active_tracks=active_list,
            new_tracks=new_count,
            lost_tracks=lost_count,
            processing_time_ms=elapsed_ms,
        )

        with self._lock:
            self._total_fusions += 1
            self._history.append(result)
            if len(self._history) > _MAX_HISTORY:
                self._history = self._history[-_MAX_HISTORY:]

        return result

    # =========================================================================
    # 내부: IoU 기반 매칭
    # =========================================================================
    def _find_best_match(
        self,
        bbox: tuple[float, float, float, float],
        already_matched: set[int],
    ) -> int | None:
        """기존 글로벌 트랙 중 IoU가 가장 높은 트랙 ID 반환."""
        best_id: int | None = None
        best_iou: float = self._match_threshold

        for gid, track in self._active_globals.items():
            if gid in already_matched:
                continue
            iou = self._compute_iou(bbox, track.last_bbox)
            if iou > best_iou:
                best_iou = iou
                best_id = gid

        return best_id

    @staticmethod
    def _compute_iou(
        box_a: tuple[float, float, float, float],
        box_b: tuple[float, float, float, float],
    ) -> float:
        """두 bbox의 IoU 계산."""
        x1 = max(box_a[0], box_b[0])
        y1 = max(box_a[1], box_b[1])
        x2 = min(box_a[2], box_b[2])
        y2 = min(box_a[3], box_b[3])

        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
        area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
        union = area_a + area_b - inter

        if union < 1e-6:
            return 0.0
        return inter / union

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def num_active_tracks(self) -> int:
        """활성 트랙 수."""
        return len(self._active_globals)

    @property
    def total_fusions(self) -> int:
        """총 융합 횟수."""
        return self._total_fusions

    def reset(self) -> None:
        """상태 초기화 (글로벌 ID도 리셋)."""
        with self._lock:
            self._active_globals.clear()
            self._next_global_id = 1
            self._history.clear()
            self._total_fusions = 0

    def __repr__(self) -> str:
        return (
            f"TrackingFusion(active={self.num_active_tracks}, "
            f"fusions={self._total_fusions})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "GlobalTrack",
    "TrackingFusionResult",
    "TrackingFusion",
]

__version__ = "1.0.0"
