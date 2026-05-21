# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/data_extraction
파일: possession_frame_extractor.py
설명: CV-Possession 프레임 단위 볼 소유자 학습 데이터 추출기.
      매 프레임 (또는 N프레임마다) 정답 possessor + 후보군 +
      거리/손-볼 거리 특징을 PossessionFrameRecord로 저장.

      라벨 소스:
        - 자동: 룰 기반 detector(거리 + 손위치)가 score_possession()으로
                후보 점수 계산, top-1을 정답으로
        - 수동: 외부 라벨러가 push_possession_label()로 직접 지정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-25
버전: 1.0.0

의존성:
    - shared/dto/dataset_dto.py: PossessionFrameRecord, DatasetType
"""

from __future__ import annotations

import logging
import math
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Final
from uuid import uuid4

from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
    PossessionFrameRecord,
    UploadStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================

# 프레임 샘플링 간격 (1=매프레임, 3=10fps@30fps, 5=6fps)
_SAMPLE_INTERVAL: Final[int] = 3

# 시퀀스 컨텍스트 (직전 N프레임 possessor)
_RECENT_CONTEXT_LEN: Final[int] = 30

# 후보 선별 거리 (이 미터 이내 선수만 후보)
_CANDIDATE_RADIUS_M: Final[float] = 3.0

# 손-볼 매핑용 키포인트 이름 (UK25 wrist/finger)
_HAND_KEYPOINT_NAMES: Final[tuple[str, ...]] = (
    "left_wrist", "right_wrist",
    "left_fingertip", "right_fingertip",
)

# 버퍼
_MAX_BUFFER: Final[int] = 50000


# =============================================================================
# 설정
# =============================================================================

@dataclass(slots=True)
class PossessionFrameExtractorConfig:
    """PossessionFrameExtractor 설정."""

    sample_interval: int = _SAMPLE_INTERVAL
    recent_context_len: int = _RECENT_CONTEXT_LEN
    candidate_radius_m: float = _CANDIDATE_RADIUS_M
    max_buffer: int = _MAX_BUFFER
    min_confidence: float = 0.5
    # 자동 라벨링 활성화 (False면 push_possession_label만 사용)
    auto_label: bool = True


# =============================================================================
# 추출 세션
# =============================================================================

@dataclass(slots=True)
class _PossessionSession:
    """경기 단위 Possession 추출 상태."""

    game_id: str = ""
    metadata: DatasetMetadata = field(default_factory=DatasetMetadata)
    records: list[PossessionFrameRecord] = field(default_factory=list)
    # 직전 N프레임 possessor (시퀀스 컨텍스트)
    recent_possessors: deque = field(default_factory=lambda: deque(maxlen=_RECENT_CONTEXT_LEN))
    # 마지막 샘플 프레임
    last_sample_frame: int = -9999


# =============================================================================
# 메인 추출기
# =============================================================================

class PossessionFrameExtractor:
    """
    CV-Possession 프레임 단위 학습 데이터 추출기.

    워크플로우:
        1. start_session(game_id)
        2. 매 프레임 push_frame(frame, ball, players)
            → sample_interval 마다 자동 라벨링 후 레코드 생성
        3. 외부 라벨러가 있으면 push_possession_label()로 덮어쓰기
        4. finalize() → ExtractionResult

    스레드 안전: yes (RLock).
    """

    def __init__(self, config: PossessionFrameExtractorConfig | None = None) -> None:
        self._config = config or PossessionFrameExtractorConfig()
        self._lock = threading.RLock()
        self._session: _PossessionSession | None = None

    def start_session(self, game_id: str) -> None:
        """경기 시작."""
        with self._lock:
            self._session = _PossessionSession(
                game_id=game_id,
                metadata=DatasetMetadata(
                    dataset_id=uuid4(),
                    dataset_type=DatasetType.POSSESSION_FRAME,
                    source_game_ids=[game_id],
                    description="CV-Possession per-frame ball possessor labels",
                ),
            )
            self._session.recent_possessors = deque(
                maxlen=self._config.recent_context_len,
            )
            logger.info(
                "PossessionFrameExtractor session 시작: game_id=%s", game_id,
            )

    def push_frame(
        self,
        frame_index: int,
        ball_position: tuple[float, float, float] | None,
        player_keypoints: dict[int, dict[str, tuple[float, float, float]]],
        manual_possessor_id: int | None = None,
        manual_confidence: float = 1.0,
    ) -> None:
        """
        매 프레임 호출.

        manual_possessor_id 가 주어지면 그 값을 정답으로 (수동 라벨).
        주어지지 않으면 auto_label=True 일 때 룰 기반으로 자동 라벨.
        """
        with self._lock:
            if self._session is None:
                return
            interval = self._config.sample_interval
            if frame_index - self._session.last_sample_frame < interval:
                return
            self._session.last_sample_frame = frame_index

            # 후보 선별 + 거리 계산
            candidates, distances, hand_distances = self._compute_features(
                ball_position, player_keypoints,
            )

            # 라벨 결정
            if manual_possessor_id is not None:
                possessor_id: int | None = manual_possessor_id
                confidence = manual_confidence
                source = "manual"
            elif self._config.auto_label and candidates:
                possessor_id, confidence = self._auto_label(
                    candidates, distances, hand_distances,
                )
                source = "auto"
                if confidence < self._config.min_confidence:
                    # 자동 신뢰도 낮으면 free ball로 처리하되 기록은 남김
                    possessor_id = None
            else:
                possessor_id = None
                confidence = 0.0
                source = "auto"

            record = PossessionFrameRecord(
                frame_index=frame_index,
                possessor_id=possessor_id,
                confidence=confidence,
                candidate_player_ids=candidates,
                ball_position=ball_position,
                candidate_distances_m=distances,
                candidate_hand_distances_m=hand_distances,
                recent_possessor_ids=list(self._session.recent_possessors),
                label_source=source,
            )
            self._session.records.append(record)
            self._session.recent_possessors.append(possessor_id)

            if len(self._session.records) > self._config.max_buffer:
                logger.warning("Possession buffer overflow — finalize 권장")

    def push_possession_label(
        self,
        frame_index: int,
        possessor_id: int | None,
        confidence: float = 1.0,
    ) -> None:
        """
        가장 최근 push_frame 결과의 라벨을 외부 라벨러가 덮어씀.
        (frame_index 일치하는 마지막 레코드만 갱신)
        """
        with self._lock:
            if self._session is None or not self._session.records:
                return
            last = self._session.records[-1]
            if last.frame_index != frame_index:
                return
            last.possessor_id = possessor_id
            last.confidence = confidence
            last.label_source = "manual"
            # recent context도 갱신
            if self._session.recent_possessors:
                self._session.recent_possessors[-1] = possessor_id

    def _compute_features(
        self,
        ball_position: tuple[float, float, float] | None,
        player_keypoints: dict[int, dict[str, tuple[float, float, float]]],
    ) -> tuple[list[int], list[float], list[float]]:
        """후보 선별 + 거리/손거리 계산."""
        if ball_position is None or not player_keypoints:
            return [], [], []
        bx, by, bz = ball_position
        radius = self._config.candidate_radius_m

        candidates: list[int] = []
        distances: list[float] = []
        hand_distances: list[float] = []

        for pid, kps in player_keypoints.items():
            # 선수 중심 = pelvis or hips_center 우선, 없으면 첫 키포인트
            center = (
                kps.get("pelvis")
                or kps.get("hips_center")
                or kps.get("nose")
            )
            if center is None and kps:
                center = next(iter(kps.values()))
            if center is None:
                continue
            cx, cy, cz = center
            dist = math.sqrt(
                (bx - cx) ** 2 + (by - cy) ** 2 + (bz - cz) ** 2,
            )
            if dist > radius:
                continue

            # 손-볼 최소 거리
            min_hand = float("inf")
            for hk in _HAND_KEYPOINT_NAMES:
                hp = kps.get(hk)
                if hp is None:
                    continue
                hx, hy, hz = hp
                hd = math.sqrt(
                    (bx - hx) ** 2 + (by - hy) ** 2 + (bz - hz) ** 2,
                )
                if hd < min_hand:
                    min_hand = hd
            if not math.isfinite(min_hand):
                min_hand = dist

            candidates.append(pid)
            distances.append(dist)
            hand_distances.append(min_hand)

        return candidates, distances, hand_distances

    def _auto_label(
        self,
        candidates: list[int],
        distances: list[float],
        hand_distances: list[float],
    ) -> tuple[int | None, float]:
        """
        룰 기반 점수 계산 → top-1 + confidence.

        score = 1 / (hand_distance + 0.1) + 0.3 / (center_distance + 0.1)
        confidence = top1_score / (top1_score + top2_score)
        """
        if not candidates:
            return None, 0.0
        scores: list[float] = []
        for d, hd in zip(distances, hand_distances):
            score = 1.0 / (hd + 0.1) + 0.3 / (d + 0.1)
            scores.append(score)

        # top-1, top-2 분리도
        ranked = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True,
        )
        top1 = ranked[0]
        top1_score = scores[top1]
        if len(ranked) >= 2:
            top2_score = scores[ranked[1]]
            confidence = top1_score / (top1_score + top2_score + 1e-6)
        else:
            confidence = 1.0
        return candidates[top1], confidence

    def finalize(self) -> tuple[ExtractionResult, list[PossessionFrameRecord]] | None:
        """
        경기 종료.

        반환: (메타 ExtractionResult, 레코드 리스트).
        ExtractionResult.records 필드가 없는 설계상 레코드는 별도로 노출.
        """
        with self._lock:
            if self._session is None:
                return None
            records = list(self._session.records)
            self._session.metadata.total_records = len(records)
            result = ExtractionResult(
                game_id=self._session.game_id,
                metadata=self._session.metadata,
                record_count=len(records),
                upload_status=UploadStatus.PENDING,
            )
            logger.info(
                "PossessionFrameExtractor finalized: game_id=%s, records=%d",
                self._session.game_id, len(records),
            )
            self._session = None
            return result, records


__all__ = [
    "PossessionFrameExtractor",
    "PossessionFrameExtractorConfig",
]

__version__ = "1.0.0"
