# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/data_extraction
파일: action_extractor.py
설명: CV-Action / CV-Phase 학습 데이터 추출기 (2026-04-26 신설).

      두 분류 체계를 한 추출기에서 동시 라벨링:
        - 동작 7cls: shooting / dribbling / passing / layup /
                    rebounding / movement / idle
        - 위상 6cls: idle / preparation / loading /
                    execution / follow_through / recovery

      한 trigger 이벤트 → ActionClassRecord 1건 (전 30 + 후 30 프레임 = 4초)
                       + PhaseClassRecord N건 (시퀀스 내 매 프레임)

      추출 파일:
        - action_class.jsonl   (ActionClassRecord 시퀀스 단위)
        - phase_class.jsonl    (PhaseClassRecord 프레임 단위)
        - metadata.json

      두 .jsonl 은 SELF_LEARNING upload_service 가 .jsonl.zst 로 압축 후 S3 업로드.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-26
버전: 1.0.0
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from shared.dto.dataset_dto import (
    ActionClassRecord,
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
    PhaseClassRecord,
    UploadStatus,
)

_logger = logging.getLogger(__name__)

# 7 동작 클래스
ACTION_CLASSES: Final[tuple[str, ...]] = (
    "shooting", "dribbling", "passing", "layup",
    "rebounding", "movement", "idle",
)

# 6 위상 클래스
PHASE_CLASSES: Final[tuple[str, ...]] = (
    "idle", "preparation", "loading",
    "execution", "follow_through", "recovery",
)

# 윈도우: trigger 전 30 + 후 30 프레임 (≈ 4초 @ 15fps)
DEFAULT_WINDOW_BEFORE: Final[int] = 30
DEFAULT_WINDOW_AFTER: Final[int] = 30
DEFAULT_FLUSH_THRESHOLD: Final[int] = 100
DEFAULT_FLUSH_INTERVAL_SEC: Final[float] = 300.0


@dataclass(slots=True)
class _PendingFrame:
    """버퍼된 프레임 컨텍스트."""
    frame_index: int
    actor_id: int
    keypoints: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    ball_position: tuple[float, float, float] | None = None
    confidence: float = 1.0


class ActionExtractor:
    """
    CV-Action / CV-Phase 통합 추출기.

    사용:
        ext = ActionExtractor(output_dir=Path("...session_dir"))
        ext.start_session(game_id="g1")
        # 매 프레임:
        ext.push_frame(frame_index, actor_id, keypoints, ball_position)
        # 동작 trigger 발생 시:
        ext.push_action_trigger(trigger_frame, action_class, actor_id)
        # phase 라벨 (rule-engine 또는 수동):
        ext.push_phase_label(frame_index, phase_class, parent_action)
        # 종료:
        action_result, phase_result = ext.finalize()
    """

    __slots__ = (
        "_output_dir", "_game_id",
        "_lock", "_started_at", "_finalized",
        "_frame_buffer",          # deque[_PendingFrame] — sliding window
        "_action_records",        # ActionClassRecord 누적
        "_phase_records",         # PhaseClassRecord 누적
        "_window_before", "_window_after",
        "_min_confidence",
    )

    def __init__(
        self,
        output_dir: Path,
        window_before: int = DEFAULT_WINDOW_BEFORE,
        window_after: int = DEFAULT_WINDOW_AFTER,
        min_confidence: float = 0.5,
    ) -> None:
        self._output_dir = output_dir
        self._game_id = ""
        self._lock = threading.RLock()
        self._started_at = 0.0
        self._finalized = False
        # ring buffer — window_before + window_after 만큼 보관
        self._frame_buffer: deque[_PendingFrame] = deque(maxlen=window_before + window_after + 10)
        self._action_records: list[ActionClassRecord] = []
        self._phase_records: list[PhaseClassRecord] = []
        self._window_before = window_before
        self._window_after = window_after
        self._min_confidence = min_confidence

    # =========================================================================
    # 세션 수명
    # =========================================================================
    def start_session(self, game_id: str) -> None:
        with self._lock:
            self._game_id = game_id
            self._started_at = time.time()
            self._finalized = False
            self._action_records.clear()
            self._phase_records.clear()
            self._frame_buffer.clear()
            _logger.info("ActionExtractor 세션 시작: game_id=%s", game_id)

    # =========================================================================
    # 프레임 / 트리거 입력
    # =========================================================================
    def push_frame(
        self,
        frame_index: int,
        actor_id: int,
        keypoints: dict[str, tuple[float, float, float]],
        ball_position: tuple[float, float, float] | None = None,
        confidence: float = 1.0,
    ) -> None:
        """매 프레임 호출 — sliding window 에 컨텍스트 누적."""
        if self._finalized:
            return
        with self._lock:
            self._frame_buffer.append(_PendingFrame(
                frame_index=frame_index, actor_id=actor_id,
                keypoints=keypoints, ball_position=ball_position,
                confidence=confidence,
            ))

    def push_action_trigger(
        self,
        trigger_frame: int,
        action_class: str,
        actor_id: int,
        label_source: str = "auto",
    ) -> bool:
        """
        동작 trigger 발생 시 호출.

        sliding window 의 trigger ±window 프레임을 ActionClassRecord 1건으로 추출.
        동일 actor_id 의 keypoint 시퀀스 + ball_position 함께 기록.

        Args:
            trigger_frame: 트리거 프레임 인덱스
            action_class: ACTION_CLASSES 중 1
            actor_id: 동작 주체
            label_source: 'auto' / 'manual' / 'corrected'

        Returns:
            추가 성공 여부 (윈도우 미수집 / 클래스 invalid 시 False)
        """
        if self._finalized:
            return False
        if action_class not in ACTION_CLASSES:
            _logger.warning("invalid action_class: %s", action_class)
            return False

        with self._lock:
            window = self._collect_window(trigger_frame, actor_id)
            if not window:
                return False

            keypoints_seq = [f.keypoints for f in window]
            ball_seq = [f.ball_position for f in window]
            ball_at_trigger = next(
                (f.ball_position for f in window if f.frame_index == trigger_frame),
                None,
            )

            record = ActionClassRecord(
                trigger_frame=trigger_frame,
                action_class=action_class,
                frame_indices=[f.frame_index for f in window],
                actor_id=actor_id,
                actor_keypoints=keypoints_seq,
                ball_position=ball_at_trigger,
                confidence=min(f.confidence for f in window),
                label_source=label_source,
            )
            self._action_records.append(record)
            _logger.debug(
                "action 추가: %s @ frame=%d actor=%d (window=%d)",
                action_class, trigger_frame, actor_id, len(window),
            )
            return True

    def push_phase_label(
        self,
        frame_index: int,
        phase_class: str,
        actor_id: int,
        parent_action: str = "",
        label_source: str = "auto",
    ) -> bool:
        """
        프레임 단위 phase 라벨 푸시.

        Args:
            frame_index: 라벨 대상 프레임
            phase_class: PHASE_CLASSES 중 1
            actor_id: 위상 주체
            parent_action: 동시 ActionClassRecord 의 action_class (연결 키)
            label_source: 'auto' / 'manual' / 'corrected'

        Returns:
            추가 성공 여부
        """
        if self._finalized:
            return False
        if phase_class not in PHASE_CLASSES:
            _logger.warning("invalid phase_class: %s", phase_class)
            return False

        # buffer 에서 해당 frame 의 keypoint 찾기 (없어도 등록은 함 — 라벨만)
        kp: dict[str, tuple[float, float, float]] = {}
        with self._lock:
            for f in self._frame_buffer:
                if f.frame_index == frame_index and f.actor_id == actor_id:
                    kp = f.keypoints
                    break
            self._phase_records.append(PhaseClassRecord(
                frame_index=frame_index,
                phase_class=phase_class,
                actor_id=actor_id,
                actor_keypoints=kp,
                parent_action=parent_action,
                label_source=label_source,
            ))
            return True

    # =========================================================================
    # finalize → ExtractionResult × 2
    # =========================================================================
    def finalize(self) -> tuple[ExtractionResult | None, ExtractionResult | None]:
        """
        세션 종료. 두 .jsonl 파일 생성 + ExtractionResult × 2 반환.

        Returns:
            (action_result, phase_result) — 각각 None 일 수 있음 (레코드 0건)
        """
        with self._lock:
            if self._finalized:
                return None, None
            self._finalized = True

            self._output_dir.mkdir(parents=True, exist_ok=True)

            action_result = self._write_jsonl(
                records=self._action_records,
                file_name="action_class.jsonl",
                dataset_type=DatasetType.ACTION_CLASS,
            ) if self._action_records else None

            phase_result = self._write_jsonl(
                records=self._phase_records,
                file_name="phase_class.jsonl",
                dataset_type=DatasetType.PHASE_CLASS,
            ) if self._phase_records else None

            _logger.info(
                "ActionExtractor finalize: action=%d, phase=%d",
                len(self._action_records), len(self._phase_records),
            )
            return action_result, phase_result

    # =========================================================================
    # 내부
    # =========================================================================
    def _collect_window(self, trigger_frame: int, actor_id: int) -> list[_PendingFrame]:
        """trigger_frame ± window 범위 + 동일 actor_id 의 프레임 수집."""
        lo = trigger_frame - self._window_before
        hi = trigger_frame + self._window_after
        return [
            f for f in self._frame_buffer
            if lo <= f.frame_index <= hi and f.actor_id == actor_id
            and f.confidence >= self._min_confidence
        ]

    def _write_jsonl(
        self,
        records: list[Any],
        file_name: str,
        dataset_type: DatasetType,
    ) -> ExtractionResult:
        path = self._output_dir / file_name
        with path.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(_to_dict(r), ensure_ascii=False) + "\n")

        size = path.stat().st_size
        meta = DatasetMetadata(
            dataset_type=dataset_type,
            total_records=len(records),
            source_game_ids=[self._game_id] if self._game_id else [],
            description=f"motion_analysis/action_extractor — {dataset_type.value}",
        )
        return ExtractionResult(
            game_id=self._game_id,
            metadata=meta,
            record_count=len(records),
            file_path=str(path),
            file_size_bytes=size,
            upload_status=UploadStatus.PENDING,
        )


def _to_dict(record: Any) -> dict[str, Any]:
    """dataclass → dict (slots 호환)."""
    if hasattr(record, "__slots__"):
        return {s: getattr(record, s) for s in record.__slots__}
    return record.__dict__


__all__ = [
    "ACTION_CLASSES",
    "PHASE_CLASSES",
    "ActionExtractor",
    "DEFAULT_WINDOW_BEFORE",
    "DEFAULT_WINDOW_AFTER",
]
__version__ = "1.0.0"
