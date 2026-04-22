# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/data_extraction
파일: violation_sequence_extractor.py
설명: 바이올레이션 시계열 패턴 추출기
      - 위반 전 30프레임 + 후 10프레임 = 40프레임 시퀀스
      - 공 위치, 위반자 키포인트/속도 시계열 포함
      - 정상 시퀀스 네거티브 샘플링 (10:1 비율)
      - 시퀀스 모델(LSTM/Transformer) 학습용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - configs/ai_referee/data_extraction.yaml: violation_sequence 섹션
    - ai_referee/rules/base_rule.py: RuleResult, FrameContext
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
    ViolationSequenceRecord,
)

from ai_referee.rules.base_rule import FrameContext, RuleCategory, RuleResult

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_DEFAULT_MAX_EXTRACTIONS: Final[int] = 200
_DEFAULT_MAX_RECORDS: Final[int] = 50000
_DEFAULT_FRAMES_BEFORE: Final[int] = 30
_DEFAULT_FRAMES_AFTER: Final[int] = 10
_DEFAULT_NEGATIVE_RATIO: Final[float] = 0.10
_DEFAULT_MIN_NEGATIVE_INTERVAL: Final[int] = 90


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ViolationSequenceExtractorConfig:
    """바이올레이션 시퀀스 추출기 설정."""

    max_extractions: int = _DEFAULT_MAX_EXTRACTIONS
    max_records_per_extraction: int = _DEFAULT_MAX_RECORDS
    frames_before: int = _DEFAULT_FRAMES_BEFORE
    frames_after: int = _DEFAULT_FRAMES_AFTER
    negative_sampling_ratio: float = _DEFAULT_NEGATIVE_RATIO
    min_negative_interval: int = _DEFAULT_MIN_NEGATIVE_INTERVAL


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _FrameData:
    """프레임 데이터 (시계열 구성용)."""
    frame_number: int
    ball_position: tuple[float, float, float] | None
    player_keypoints: dict[int, dict[str, tuple[float, float, float]]]
    player_velocities: dict[int, dict[str, float]]
    quarter: int
    game_clock_sec: float
    is_backcourt: bool


@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""
    extraction_id: UUID
    game_id: str
    records: list[ViolationSequenceRecord]
    frame_history: list[_FrameData]
    max_history: int
    violation_count: int
    last_negative_frame: int
    negative_count: int


# =============================================================================
# 추출기
# =============================================================================
class ViolationSequenceExtractor:
    """
    바이올레이션 시계열 패턴 추출기.

    위반 전후 40프레임 시퀀스를 추출하여 시퀀스 모델 학습에 사용.
    정상 시퀀스도 10:1 비율로 네거티브 샘플링.

    사용 예시::

        >>> extractor = ViolationSequenceExtractor()
        >>> eid = extractor.create_extraction("game_001")
        >>> extractor.push_frame(eid, context)  # 매 프레임
        >>> extractor.add_violation(eid, rule_result)
        True
        >>> extractor.sample_negative(eid, context)  # 주기적 호출
    """

    __slots__ = ("_config", "_sessions", "_lock", "_total_records")

    def __init__(
        self, config: ViolationSequenceExtractorConfig | None = None,
    ) -> None:
        self._config = config or ViolationSequenceExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "ViolationSequenceExtractor"

    @property
    def total_extractions(self) -> int:
        with self._lock:
            return len(self._sessions)

    @property
    def total_records(self) -> int:
        with self._lock:
            return self._total_records

    def __repr__(self) -> str:
        return (
            f"ViolationSequenceExtractor("
            f"extractions={self.total_extractions}, "
            f"records={self.total_records})"
        )

    # -- 세션 관리 --

    def create_extraction(self, game_id: str) -> UUID | None:
        """추출 세션 생성."""
        with self._lock:
            if len(self._sessions) >= self._config.max_extractions:
                logger.warning(
                    "추출 세션 한도 도달: %d", self._config.max_extractions,
                )
                return None
            total_seq = self._config.frames_before + 1 + self._config.frames_after
            eid = uuid4()
            self._sessions[eid] = _ExtractionSession(
                extraction_id=eid,
                game_id=game_id,
                records=[],
                frame_history=[],
                max_history=total_seq + 20,  # 여유분
                violation_count=0,
                last_negative_frame=-_DEFAULT_MIN_NEGATIVE_INTERVAL,
                negative_count=0,
            )
            return eid

    def push_frame(self, extraction_id: UUID, context: FrameContext) -> None:
        """
        프레임 데이터 저장 (시계열 추출용).

        매 프레임마다 호출하여 공 위치, 키포인트, 속도 히스토리를 축적.
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return

            # 백코트 여부 추정
            is_backcourt = False
            ball_pos = context.ball_position
            if ball_pos is not None and context.half_court_x > 0:
                # 공이 하프라인 이전이면 백코트
                is_backcourt = ball_pos[0] < context.half_court_x

            frame_data = _FrameData(
                frame_number=context.frame_number,
                ball_position=context.ball_position,
                player_keypoints=dict(context.player_keypoints),
                player_velocities=dict(context.joint_velocities),
                quarter=context.quarter,
                game_clock_sec=context.game_clock_sec,
                is_backcourt=is_backcourt,
            )
            session.frame_history.append(frame_data)

            if len(session.frame_history) > session.max_history:
                session.frame_history = session.frame_history[-session.max_history:]

    def add_violation(
        self,
        extraction_id: UUID,
        result: RuleResult,
    ) -> bool:
        """
        바이올레이션 시퀀스 추출.

        Args:
            extraction_id: 추출 세션 ID
            result: 바이올레이션 판정 결과 (violated=True)

        Returns:
            추출 성공 여부
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                return False
            if not result.violated:
                return False
            if result.category != RuleCategory.VIOLATION:
                return False

            record = self._build_sequence(
                session=session,
                trigger_frame=result.frame_number,
                violation_type=(
                    result.violation_type.value if result.violation_type else ""
                ),
                rule_set=result.rule_set.value if result.rule_set else "",
                label="CONFIRMED",
                offending_player_id=result.offending_player_id,
            )
            if record is None:
                return False

            session.records.append(record)
            session.violation_count += 1
            self._total_records += 1
            return True

    def sample_negative(
        self,
        extraction_id: UUID,
        context: FrameContext,
    ) -> bool:
        """
        정상 시퀀스 네거티브 샘플링.

        위반 미발생 구간에서 확률적으로 네거티브 샘플을 수집.
        violation_count 대비 ratio 비율로 제한.

        Args:
            extraction_id: 추출 세션 ID
            context: 현재 프레임 컨텍스트

        Returns:
            샘플링 성공 여부
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                return False

            # 최소 간격 체크
            if (
                context.frame_number - session.last_negative_frame
                < self._config.min_negative_interval
            ):
                return False

            # 비율 제한
            max_negatives = max(
                1, int(session.violation_count * (1.0 / self._config.negative_sampling_ratio)),
            )
            if session.negative_count >= max_negatives:
                return False

            # 확률적 샘플링
            if random.random() > self._config.negative_sampling_ratio:
                return False

            record = self._build_sequence(
                session=session,
                trigger_frame=context.frame_number,
                violation_type="",
                rule_set="",
                label="NEGATIVE",
                offending_player_id=None,
            )
            if record is None:
                return False

            session.records.append(record)
            session.last_negative_frame = context.frame_number
            session.negative_count += 1
            self._total_records += 1
            return True

    def _build_sequence(
        self,
        session: _ExtractionSession,
        trigger_frame: int,
        violation_type: str,
        rule_set: str,
        label: str,
        offending_player_id: int | None,
    ) -> ViolationSequenceRecord | None:
        """시퀀스 레코드 구성."""
        before = self._config.frames_before
        after = self._config.frames_after
        start_frame = trigger_frame - before
        end_frame = trigger_frame + after

        # 프레임 인덱스 → _FrameData 매핑
        frame_map: dict[int, _FrameData] = {
            fd.frame_number: fd for fd in session.frame_history
        }

        frame_indices: list[int] = []
        ball_positions: list[tuple[float, float, float] | None] = []
        offender_kps: list[dict[str, tuple[float, float, float]]] = []
        offender_vels: list[dict[str, float]] = []

        quarter = 1
        game_clock = 0.0
        is_backcourt = False

        for fn in range(start_frame, end_frame + 1):
            frame_indices.append(fn)
            fd = frame_map.get(fn)
            if fd is not None:
                ball_positions.append(fd.ball_position)
                if offending_player_id is not None:
                    offender_kps.append(
                        dict(fd.player_keypoints.get(offending_player_id, {})),
                    )
                    offender_vels.append(
                        dict(fd.player_velocities.get(offending_player_id, {})),
                    )
                else:
                    offender_kps.append({})
                    offender_vels.append({})
                # 트리거 프레임의 게임 상태 사용
                if fn == trigger_frame:
                    quarter = fd.quarter
                    game_clock = fd.game_clock_sec
                    is_backcourt = fd.is_backcourt
            else:
                ball_positions.append(None)
                offender_kps.append({})
                offender_vels.append({})

        return ViolationSequenceRecord(
            trigger_frame=trigger_frame,
            violation_type=violation_type,
            rule_set=rule_set,
            label=label,
            frame_indices=frame_indices,
            ball_positions=ball_positions,
            offender_keypoints=offender_kps,
            offender_velocities=offender_vels,
            offending_player_id=offending_player_id,
            quarter=quarter,
            game_clock_sec=game_clock,
            is_backcourt=is_backcourt,
        )

    # -- 추출 결과 --

    def build_result(self, extraction_id: UUID) -> ExtractionResult | None:
        """추출 결과 빌드."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            metadata = DatasetMetadata(
                dataset_type=DatasetType.VIOLATION_SEQUENCE,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description=(
                    f"바이올레이션 시계열 — "
                    f"위반 {session.violation_count}건, "
                    f"네거티브 {session.negative_count}건"
                ),
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[ViolationSequenceRecord]:
        """레코드 목록 반환."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return []
            return list(session.records)

    def get_extraction_summary(self, extraction_id: UUID) -> dict[str, object] | None:
        """추출 세션 요약."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            return {
                "game_id": session.game_id,
                "total_records": len(session.records),
                "violation_count": session.violation_count,
                "negative_count": session.negative_count,
                "frame_history_size": len(session.frame_history),
            }

    # -- 삭제 / 유틸리티 --

    def delete_extraction(self, extraction_id: UUID) -> bool:
        """추출 세션 삭제."""
        with self._lock:
            session = self._sessions.pop(extraction_id, None)
            if session is None:
                return False
            self._total_records -= len(session.records)
            return True

    def get_stats(self) -> dict[str, object]:
        """전체 통계."""
        with self._lock:
            return {
                "total_extractions": len(self._sessions),
                "total_records": self._total_records,
            }

    def reset(self) -> None:
        """전체 초기화."""
        with self._lock:
            self._sessions.clear()
            self._total_records = 0


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "ViolationSequenceExtractor",
    "ViolationSequenceExtractorConfig",
]

__version__ = "1.0.0"
