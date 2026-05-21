# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/data_extraction
파일: recorder_event_extractor.py
설명: CV-Recorder (이벤트 통합 모델) 학습 데이터 추출기.
      Score(made/missed) + Rebound + Assist + Steal + Turnover + Block
      6개 이벤트를 한 시퀀스에서 인과관계 보존하며 추출.

      예시 시퀀스:
        프레임 100: 슛 시도
        프레임 110: 미스
        프레임 115: 리바운드 (defensive)
        프레임 120: 패스
        프레임 130: 어시스트 → 득점

      이런 인과 체인을 단일 RecorderEventRecord로 저장하여
      "1회 라벨링으로 다중 이벤트 학습 데이터 확보".

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-25
버전: 1.0.0

의존성:
    - shared/dto/dataset_dto.py: RecorderEventRecord, DatasetType
    - shared/dto/ball_dto.py: BallTrack
    - shared/dto/player_dto.py: PlayerTrack
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Final, Literal
from uuid import uuid4

from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
    RecorderEventRecord,
    UploadStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================

# 이벤트 시퀀스 윈도우 (전 60 + 트리거 + 후 60 ≈ 4초 @ 30fps)
_PRE_FRAMES: Final[int] = 60
_POST_FRAMES: Final[int] = 60
_TOTAL_FRAMES: Final[int] = _PRE_FRAMES + _POST_FRAMES + 1

# 이벤트 그룹화 윈도우 (이 시간 내 발생한 이벤트는 같은 시퀀스로)
_CAUSAL_LINK_FRAMES: Final[int] = 90      # 3초

# 버퍼 크기 (메모리 한계)
_MAX_BUFFER: Final[int] = 1000

# 이벤트 종류
EventType = Literal["score", "rebound", "assist", "steal", "turnover", "block"]


# =============================================================================
# 설정
# =============================================================================

@dataclass(slots=True)
class RecorderEventExtractorConfig:
    """RecorderEventExtractor 설정."""

    pre_frames: int = _PRE_FRAMES
    post_frames: int = _POST_FRAMES
    causal_link_frames: int = _CAUSAL_LINK_FRAMES
    max_buffer: int = _MAX_BUFFER
    # 라벨 신뢰도 임계값 (낮으면 학습 제외)
    min_confidence: float = 0.5
    # 자동 라벨링 여부 (False면 외부 라벨러가 push)
    auto_label_from_score_detector: bool = True


# =============================================================================
# 추출 세션 (단일 경기)
# =============================================================================

@dataclass(slots=True)
class _ExtractionSession:
    """경기 단위 추출 상태."""

    game_id: str = ""
    metadata: DatasetMetadata = field(default_factory=DatasetMetadata)
    records: list[RecorderEventRecord] = field(default_factory=list)
    # 프레임 버퍼 (롤링 윈도우)
    ball_history: deque = field(default_factory=lambda: deque(maxlen=_TOTAL_FRAMES + 60))
    player_history: deque = field(default_factory=lambda: deque(maxlen=_TOTAL_FRAMES + 60))
    hoop_history: deque = field(default_factory=lambda: deque(maxlen=_TOTAL_FRAMES + 60))
    # 대기 중인 이벤트 (윈도우 채워지면 records로 flush)
    pending_events: list[tuple[int, str, dict]] = field(default_factory=list)
    # 인과 체인 추적 (직전 이벤트와 이번 이벤트 연결)
    last_event_frame: int = -9999
    last_event_type: str = ""


# =============================================================================
# 메인 추출기
# =============================================================================

class RecorderEventExtractor:
    """
    CV-Recorder 통합 이벤트 학습 데이터 추출기.

    워크플로우:
        1. 매 프레임 push_frame(ball, players, hoop) 호출
        2. 이벤트 발생 시 push_event(type, subtype, players) 호출
        3. 윈도우 가득 차면 자동으로 RecorderEventRecord 생성
        4. finalize() → ExtractionResult 반환

    스레드 안전: yes (RLock).
    """

    def __init__(self, config: RecorderEventExtractorConfig | None = None) -> None:
        self._config = config or RecorderEventExtractorConfig()
        self._lock = threading.RLock()
        self._session: _ExtractionSession | None = None

    def start_session(self, game_id: str) -> None:
        """경기 시작 시 호출."""
        with self._lock:
            self._session = _ExtractionSession(
                game_id=game_id,
                metadata=DatasetMetadata(
                    dataset_id=uuid4(),
                    dataset_type=DatasetType.RECORDER_EVENT,
                    source_game_ids=[game_id],
                    description="CV-Recorder unified event sequences",
                ),
            )
            logger.info("RecorderEventExtractor session 시작: game_id=%s", game_id)

    def push_frame(
        self,
        frame_index: int,
        ball_position: tuple[float, float, float] | None,
        player_keypoints: dict[int, dict[str, tuple[float, float, float]]],
        hoop_position: tuple[float, float, float] | None = None,
    ) -> None:
        """매 프레임 호출. 시퀀스 버퍼에 누적."""
        with self._lock:
            if self._session is None:
                return
            self._session.ball_history.append((frame_index, ball_position))
            self._session.player_history.append((frame_index, player_keypoints))
            self._session.hoop_history.append((frame_index, hoop_position))

            # 대기 이벤트 중 윈도우 채워진 것 flush
            ready = [
                (fi, et, info) for (fi, et, info) in self._session.pending_events
                if frame_index - fi >= self._config.post_frames
            ]
            for fi, et, info in ready:
                self._flush_event(fi, et, info)
                self._session.pending_events.remove((fi, et, info))

    def push_event(
        self,
        frame_index: int,
        event_type: EventType,
        subtype: str = "",
        primary_player_id: int | None = None,
        secondary_player_id: int | None = None,
        confidence: float = 1.0,
        label_source: str = "auto",
        quarter: int = 1,
        game_clock_sec: float = 0.0,
        score_diff: int = 0,
    ) -> None:
        """이벤트 발생 시 호출. 윈도우 채워질 때까지 pending에 보관."""
        with self._lock:
            if self._session is None:
                return
            if confidence < self._config.min_confidence:
                return
            info = {
                "subtype": subtype,
                "primary_player_id": primary_player_id,
                "secondary_player_id": secondary_player_id,
                "confidence": confidence,
                "label_source": label_source,
                "quarter": quarter,
                "game_clock_sec": game_clock_sec,
                "score_diff": score_diff,
                # 인과 링크: 직전 이벤트가 가까우면 함께 묶임
                "causal_prev_event": (
                    self._session.last_event_type
                    if frame_index - self._session.last_event_frame
                    <= self._config.causal_link_frames
                    else ""
                ),
            }
            self._session.pending_events.append((frame_index, event_type, info))
            self._session.last_event_frame = frame_index
            self._session.last_event_type = event_type

    def _flush_event(self, trigger_frame: int, event_type: str, info: dict) -> None:
        """pending 이벤트를 RecorderEventRecord로 변환."""
        if self._session is None:
            return
        start_fi = trigger_frame - self._config.pre_frames
        end_fi = trigger_frame + self._config.post_frames

        # 시퀀스 슬라이스
        frame_indices: list[int] = []
        ball_positions: list[tuple[float, float, float] | None] = []
        primary_kps: list[dict[str, tuple[float, float, float]]] = []
        secondary_kps: list[dict[str, tuple[float, float, float]]] = []
        hoop_pos = None

        primary_id = info["primary_player_id"]
        secondary_id = info["secondary_player_id"]

        for (fi, ball_pos), (_, kps), (_, hp) in zip(
            self._session.ball_history,
            self._session.player_history,
            self._session.hoop_history,
        ):
            if not (start_fi <= fi <= end_fi):
                continue
            frame_indices.append(fi)
            ball_positions.append(ball_pos)
            primary_kps.append(kps.get(primary_id, {}) if primary_id is not None else {})
            secondary_kps.append(kps.get(secondary_id, {}) if secondary_id is not None else {})
            if hp is not None and hoop_pos is None:
                hoop_pos = hp

        if len(frame_indices) < self._config.pre_frames + self._config.post_frames * 0.7:
            # 시퀀스 부족 → 학습 가치 낮음
            return

        record = RecorderEventRecord(
            trigger_frame=trigger_frame,
            primary_event=event_type,
            primary_subtype=info["subtype"],
            frame_indices=frame_indices,
            ball_positions=ball_positions,
            primary_player_id=primary_id,
            secondary_player_id=secondary_id,
            primary_keypoints=primary_kps,
            secondary_keypoints=secondary_kps,
            hoop_position=hoop_pos,
            quarter=info["quarter"],
            game_clock_sec=info["game_clock_sec"],
            score_diff=info["score_diff"],
            label_source=info["label_source"],
            confidence=info["confidence"],
        )
        self._session.records.append(record)
        if len(self._session.records) > self._config.max_buffer:
            logger.warning("Recorder buffer overflow — finalize 권장")

    def finalize(self) -> tuple[ExtractionResult, list[RecorderEventRecord]] | None:
        """
        경기 종료 시 호출. 남은 pending 이벤트 처리 후
        (메타데이터 ExtractionResult, 레코드 리스트) 튜플 반환.

        ExtractionResult는 메타/업로드 추적용이며 records 필드를 갖지 않음.
        실제 레코드는 두 번째 요소로 별도 반환하여 직렬화 단에서
        파일로 떨궈 ExtractionResult.file_path/s3_key 를 채우는 흐름을 따른다.
        """
        with self._lock:
            if self._session is None:
                return None
            # 남은 pending도 flush (윈도우 부족해도)
            for fi, et, info in self._session.pending_events:
                self._flush_event(fi, et, info)
            self._session.pending_events.clear()

            records = list(self._session.records)
            self._session.metadata.total_records = len(records)
            result = ExtractionResult(
                game_id=self._session.game_id,
                metadata=self._session.metadata,
                record_count=len(records),
                upload_status=UploadStatus.PENDING,
            )
            logger.info(
                "RecorderEventExtractor finalized: game_id=%s, records=%d",
                self._session.game_id, len(records),
            )
            self._session = None
            return result, records


__all__ = [
    "RecorderEventExtractor",
    "RecorderEventExtractorConfig",
    "EventType",
]

__version__ = "1.0.0"
