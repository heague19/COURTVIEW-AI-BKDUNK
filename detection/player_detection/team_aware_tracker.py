# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection
파일: team_aware_tracker.py
설명: 팀별 분리 트래커 — 크로스팀 ID 스위칭 원천 차단
      - 먼저 HSV로 빠른 팀 분류
      - team_a → tracker_a, team_b → tracker_b 분리 추적
      - 같은 팀끼리만 매칭 → 상대팀 선수와 ID 스왑 불가
      - unknown(심판 등) → tracker_unknown

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-30
버전: 1.0.0

의존성:
    - detection/player_detection/player_tracker.py: PlayerTracker
    - detection/player_detection/team_classifier.py: TeamClassifier
    - detection/player_detection/models.py: _PlayerCandidate, PlayerTrackerConfig, TeamClassifierConfig
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from detection.player_detection.player_tracker import PlayerTracker
from detection.player_detection.team_classifier import TeamClassifier
from detection.player_detection.models import (
    PlayerTrackerConfig,
    TeamClassifierConfig,
    _PlayerCandidate,
    _TrackState,
)
from shared.dto.player_dto import Team

logger: Final = logging.getLogger(__name__)


# =============================================================================
# 팀 트랙 결과
# =============================================================================
@dataclass(slots=True)
class TeamTrackResult:
    """팀별 트래커 결과."""
    track: _TrackState
    team: Team
    global_track_id: int  # 팀 간 고유 ID
    role: str = "player"  # player/referee/coach/staff


# =============================================================================
# 팀별 분리 트래커
# =============================================================================
class TeamAwareTracker:
    """
    팀별 분리 트래커 — 크로스팀 스위칭 원천 차단.

    파이프라인:
        1. 모든 player 감지 → 빠른 팀 분류 (K-Means HSV)
        2. team_a 감지 → tracker_a에 전달
        3. team_b 감지 → tracker_b에 전달
        4. unknown → tracker_unknown에 전달 (심판 등)
        5. 각 트래커 독립 매칭 → 크로스팀 스왑 불가

    사용 예시::

        >>> tat = TeamAwareTracker()
        >>> tat.initialize()
        >>> results = tat.update(candidates, frame_index, frame)
        >>> for r in results:
        ...     print(f"GID{r.global_track_id} {r.team.value}")
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._initialized = False

        # 팀별 독립 트래커
        self._tracker_a = PlayerTracker()
        self._tracker_b = PlayerTracker()
        self._tracker_unknown = PlayerTracker()

        # 팀 분류기
        self._team_classifier = TeamClassifier()

        # role 분류 모델 (COURTVIEW_player.pt)
        self._role_model: Any = None

        # 글로벌 ID 오프셋 (팀 간 ID 충돌 방지)
        # tracker_a: 1~999, tracker_b: 1000~1999, unknown: 2000~2999
        self._OFFSET_A: int = 0
        self._OFFSET_B: int = 1000
        self._OFFSET_UNK: int = 2000

        # 통계
        self._total_frames: int = 0

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def is_calibrated(self) -> bool:
        return self._team_classifier.is_calibrated

    @property
    def team_classifier(self) -> TeamClassifier:
        return self._team_classifier

    def initialize(
        self,
        tracker_config: PlayerTrackerConfig | None = None,
        team_config: TeamClassifierConfig | None = None,
    ) -> None:
        """트래커 초기화."""
        tc = tracker_config or PlayerTrackerConfig()
        team_cfg = team_config or TeamClassifierConfig(device="cpu")

        self._tracker_a.initialize(tc)
        self._tracker_b.initialize(tc)
        self._tracker_unknown.initialize(tc)
        self._team_classifier.initialize(team_cfg)

        # role 모델 로드 (COURTVIEW_player.pt)
        try:
            from pathlib import Path
            from ultralytics import YOLO
            role_path = Path("weights/COURTVIEW_player.pt")
            if role_path.exists():
                self._role_model = YOLO(str(role_path))
                logger.info("Role 모델 로드: %s", role_path.name)
            else:
                logger.info("Role 모델 없음 — role 보정 비활성화")
        except Exception:
            logger.warning("Role 모델 로드 실패")
            self._role_model = None

        self._initialized = True
        logger.info("TeamAwareTracker 초기화 완료")

    def update(
        self,
        candidates: list[_PlayerCandidate],
        frame_index: int = 0,
        frame: NDArray[np.uint8] | None = None,
    ) -> list[TeamTrackResult]:
        """
        프레임 업데이트 — 팀별 분리 트래킹.

        Args:
            candidates: player 감지 후보
            frame_index: 프레임 인덱스
            frame: BGR 이미지

        Returns:
            TeamTrackResult 목록 (팀 + 글로벌 ID 포함)
        """
        if not self._initialized:
            return []

        with self._lock:
            self._total_frames += 1
            tc = self._team_classifier

            # 0. role 감지 (프레임 단위 1회)
            role_boxes: list[tuple[float, float, str]] = []
            if self._role_model is not None and frame is not None:
                try:
                    rr = self._role_model.predict(frame, conf=0.3, verbose=False)
                    if rr and rr[0].boxes is not None:
                        for i in range(len(rr[0].boxes)):
                            rxy = rr[0].boxes.xyxy[i].cpu().numpy()
                            rc = int(rr[0].boxes.cls[i].cpu().numpy())
                            rn = self._role_model.names.get(rc, "unknown")
                            role_boxes.append(
                                ((rxy[0] + rxy[2]) / 2, (rxy[1] + rxy[3]) / 2, rn)
                            )
                except Exception:
                    pass

            # 1. 팀 캘리브레이션 (player role만 수집 — 심판 색상 오염 방지)
            if not tc.is_calibrated and frame is not None:
                player_cands = []
                for cand in candidates:
                    role = self._find_role(cand.center_x, cand.center_y, role_boxes)
                    if role == "player":
                        player_cands.append(cand)
                if player_cands:
                    tc.calibrate(player_cands, frame)

            # 2. team 먼저 → role 역방향 보정 → 팀별 분리
            cands_a: list[_PlayerCandidate] = []
            cands_b: list[_PlayerCandidate] = []
            cands_unk: list[_PlayerCandidate] = []

            for cand in candidates:
                # team 분류 (빠름)
                if frame is not None:
                    team, conf = tc.classify(cand, frame)
                else:
                    team = Team.UNKNOWN
                    conf = 0.0

                # role 확인
                role = self._find_role(cand.center_x, cand.center_y, role_boxes)

                # 역방향 보정: team 분류 됐어도 role이 심판이면 → unknown
                if role in ("referee", "coach", "staff"):
                    cands_unk.append(cand)
                elif team == Team.TEAM_A:
                    cands_a.append(cand)
                elif team == Team.TEAM_B:
                    cands_b.append(cand)
                else:
                    cands_unk.append(cand)

            # 2.5. unknown candidate별 role 기억
            unk_roles: dict[int, str] = {}
            for idx, cand in enumerate(cands_unk):
                role = self._find_role(cand.center_x, cand.center_y, role_boxes)
                unk_roles[idx] = role

            # 3. 팀별 독립 트래킹
            tracks_a = self._tracker_a.update(cands_a, frame_index, frame=frame)
            tracks_b = self._tracker_b.update(cands_b, frame_index, frame=frame)
            tracks_unk = self._tracker_unknown.update(cands_unk, frame_index, frame=frame)

            # 4. 결과 통합 (글로벌 ID + role 부여)
            results: list[TeamTrackResult] = []

            for t in tracks_a:
                results.append(TeamTrackResult(
                    track=t,
                    team=Team.TEAM_A,
                    global_track_id=t.track_id + self._OFFSET_A,
                    role="player",
                ))

            for t in tracks_b:
                results.append(TeamTrackResult(
                    track=t,
                    team=Team.TEAM_B,
                    global_track_id=t.track_id + self._OFFSET_B,
                    role="player",
                ))

            for t in tracks_unk:
                # unknown 트랙의 role 매칭 (가장 가까운 candidate)
                best_role = "unknown"
                for idx, cand in enumerate(cands_unk):
                    d = (cand.center_x - t.center[0]) ** 2 + (cand.center_y - t.center[1]) ** 2
                    if d < 5000:
                        best_role = unk_roles.get(idx, "unknown")
                        break

                results.append(TeamTrackResult(
                    track=t,
                    team=Team.UNKNOWN,
                    global_track_id=t.track_id + self._OFFSET_UNK,
                    role=best_role,
                ))

            return results

    @staticmethod
    def _find_role(
        cx: float, cy: float,
        role_boxes: list[tuple[float, float, str]],
    ) -> str:
        """가장 가까운 role bbox 매칭."""
        best_dist = 999999.0
        best_role = "player"
        for rx, ry, rn in role_boxes:
            d = (cx - rx) ** 2 + (cy - ry) ** 2
            if d < best_dist:
                best_dist = d
                best_role = rn
        return best_role if best_dist < 10000 else "player"

    def shutdown(self) -> None:
        """트래커 종료."""
        self._tracker_a.shutdown()
        self._tracker_b.shutdown()
        self._tracker_unknown.shutdown()
        self._team_classifier.shutdown()
        self._initialized = False

    def __repr__(self) -> str:
        a = len([t for t in self._tracker_a._tracks.values() if t.is_confirmed])
        b = len([t for t in self._tracker_b._tracks.values() if t.is_confirmed])
        u = len([t for t in self._tracker_unknown._tracks.values() if t.is_confirmed])
        return f"TeamAwareTracker(A={a}, B={b}, UNK={u}, cal={self.is_calibrated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "TeamAwareTracker",
    "TeamTrackResult",
]

__version__ = "1.0.0"
