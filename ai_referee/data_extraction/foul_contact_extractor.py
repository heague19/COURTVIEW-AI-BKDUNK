# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/data_extraction
파일: foul_contact_extractor.py
설명: 접촉 이벤트 + 파울 라벨 쌍 추출기
      - ContactEvent + 최종 파울 라벨 (FoulType 또는 NO_FOUL)
      - 접촉 시점 ±3프레임 키포인트/속도 시계열 포함
      - 콜 + 노파울 접촉 모두 수집 (네거티브 샘플)
      - 파울 감지 모델 재훈련 시 입력→출력 쌍으로 사용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - configs/ai_referee/data_extraction.yaml: foul_contact 섹션
    - ai_referee/fouls/contact_detector.py: ContactEvent
    - ai_referee/rules/base_rule.py: RuleResult, FrameContext
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Any, Final
from uuid import UUID, uuid4

from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
    FoulContactRecord,
)

from ai_referee.fouls.contact_detector import ContactEvent
from ai_referee.rules.base_rule import FrameContext, RuleResult

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_DEFAULT_MAX_EXTRACTIONS: Final[int] = 200
_DEFAULT_MAX_RECORDS: Final[int] = 50000
_DEFAULT_SEQ_FRAMES_BEFORE: Final[int] = 3
_DEFAULT_SEQ_FRAMES_AFTER: Final[int] = 3
_DEFAULT_MIN_IMPACT_NO_FOUL: Final[float] = 5.0


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class FoulContactExtractorConfig:
    """접촉+파울 라벨 추출기 설정."""

    max_extractions: int = _DEFAULT_MAX_EXTRACTIONS
    max_records_per_extraction: int = _DEFAULT_MAX_RECORDS
    sequence_frames_before: int = _DEFAULT_SEQ_FRAMES_BEFORE
    sequence_frames_after: int = _DEFAULT_SEQ_FRAMES_AFTER
    collect_no_foul_contacts: bool = True
    min_impact_for_no_foul: float = _DEFAULT_MIN_IMPACT_NO_FOUL


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _FrameSnapshot:
    """프레임 스냅샷 (키포인트 + 속도)."""
    frame_number: int
    keypoints: dict[int, dict[str, tuple[float, float, float]]]
    velocities: dict[int, dict[str, float]]


@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""
    extraction_id: UUID
    game_id: str
    records: list[FoulContactRecord]
    # 프레임 히스토리 (시계열 추출용)
    frame_history: list[_FrameSnapshot]
    max_history: int


# =============================================================================
# 추출기
# =============================================================================
class FoulContactExtractor:
    """
    접촉 이벤트 + 파울 라벨 쌍 추출기.

    ContactDetector가 감지한 모든 접촉 이벤트에 대해:
    - 접촉 시점 ±3프레임의 키포인트/속도 시계열 포함
    - 최종 파울 라벨 (FoulType 또는 NO_FOUL)
    - 파울 감지 모델 재훈련 시 핵심 학습 데이터

    사용 예시::

        >>> extractor = FoulContactExtractor()
        >>> eid = extractor.create_extraction("game_001")
        >>> extractor.push_frame(eid, context)  # 매 프레임 호출
        >>> extractor.add_contact(eid, contact_event, rule_result, context)
        True
    """

    __slots__ = ("_config", "_sessions", "_lock", "_total_records")

    def __init__(
        self, config: FoulContactExtractorConfig | None = None,
    ) -> None:
        self._config = config or FoulContactExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "FoulContactExtractor"

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
            f"FoulContactExtractor("
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
            total_seq = (
                self._config.sequence_frames_before
                + 1
                + self._config.sequence_frames_after
            )
            eid = uuid4()
            self._sessions[eid] = _ExtractionSession(
                extraction_id=eid,
                game_id=game_id,
                records=[],
                frame_history=[],
                max_history=total_seq + 10,  # 여유분
            )
            return eid

    def push_frame(self, extraction_id: UUID, context: FrameContext) -> None:
        """
        프레임 스냅샷 저장 (시계열 추출용).

        매 프레임마다 호출하여 키포인트/속도 히스토리를 축적.
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return

            snapshot = _FrameSnapshot(
                frame_number=context.frame_number,
                keypoints=dict(context.player_keypoints),
                velocities=dict(context.joint_velocities),
            )
            session.frame_history.append(snapshot)

            # 히스토리 제한
            if len(session.frame_history) > session.max_history:
                session.frame_history = session.frame_history[-session.max_history:]

    def add_contact(
        self,
        extraction_id: UUID,
        contact: ContactEvent,
        result: RuleResult | None,
        context: FrameContext,
    ) -> bool:
        """
        접촉 이벤트를 파울 라벨과 함께 기록.

        Args:
            extraction_id: 추출 세션 ID
            contact: 접촉 이벤트 (ContactDetector 출력)
            result: 파울 판정 결과 (None이면 NO_FOUL)
            context: 접촉 시점 프레임 컨텍스트

        Returns:
            기록 성공 여부
        """
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                return False

            # 노파울 접촉 필터
            is_foul = result is not None and result.violated
            if not is_foul and not self._config.collect_no_foul_contacts:
                return False
            if not is_foul and contact.impact_accel < self._config.min_impact_for_no_foul:
                return False

            # 키포인트/속도 시계열 추출
            keypoint_seq, velocity_seq = self._extract_sequence(
                session, context.frame_number, contact.offender_id,
            )

            # 파울 라벨
            foul_label = "NO_FOUL"
            severity_grade = ""
            shooting_context = "NONE"
            if is_foul and result is not None:
                if result.foul_type is not None:
                    foul_label = result.foul_type.value
                # severity_grade는 extra에서 가져옴
                severity_grade = str(result.evidence[-1]) if result.evidence else ""
                # 슈팅 컨텍스트
                shooting_ctx = context.extra.get("shooting_foul_type", "")
                if shooting_ctx:
                    shooting_context = str(shooting_ctx)

            # LGP 여부
            lgp = context.extra.get("lgp_established", False)

            # bbox 오버랩
            bbox_overlap = getattr(contact, "bbox_overlap_ratio", 0.0)

            record = FoulContactRecord(
                frame_index=context.frame_number,
                offender_id=contact.offender_id,
                victim_id=contact.victim_id,
                contact_bodies=list(contact.contact_bodies),
                impact_accel=contact.impact_accel,
                bbox_overlap_ratio=bbox_overlap,
                keypoint_sequence=keypoint_seq,
                velocity_sequence=velocity_seq,
                foul_label=foul_label,
                severity_grade=severity_grade,
                shooting_context=shooting_context,
                lgp_established=bool(lgp),
            )

            session.records.append(record)
            self._total_records += 1
            return True

    def _extract_sequence(
        self,
        session: _ExtractionSession,
        current_frame: int,
        player_id: int,
    ) -> tuple[
        list[dict[str, tuple[float, float, float]]],
        list[dict[str, float]],
    ]:
        """접촉 프레임 ±N의 키포인트/속도 시계열 추출."""
        before = self._config.sequence_frames_before
        after = self._config.sequence_frames_after
        target_start = current_frame - before
        target_end = current_frame + after

        keypoint_seq: list[dict[str, tuple[float, float, float]]] = []
        velocity_seq: list[dict[str, float]] = []

        for frame_num in range(target_start, target_end + 1):
            # 히스토리에서 해당 프레임 찾기
            snapshot = None
            for s in session.frame_history:
                if s.frame_number == frame_num:
                    snapshot = s
                    break

            if snapshot is not None:
                kp = snapshot.keypoints.get(player_id, {})
                vel = snapshot.velocities.get(player_id, {})
                keypoint_seq.append(dict(kp))
                velocity_seq.append(dict(vel))
            else:
                # 프레임 없음 — 빈 데이터
                keypoint_seq.append({})
                velocity_seq.append({})

        return keypoint_seq, velocity_seq

    # -- 추출 결과 --

    def build_result(self, extraction_id: UUID) -> ExtractionResult | None:
        """추출 결과 빌드."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            foul_count = sum(
                1 for r in session.records if r.foul_label != "NO_FOUL"
            )
            no_foul_count = len(session.records) - foul_count
            metadata = DatasetMetadata(
                dataset_type=DatasetType.FOUL_CONTACT,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description=(
                    f"접촉+파울 라벨 쌍 — "
                    f"파울 {foul_count}건, 노파울 {no_foul_count}건"
                ),
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[FoulContactRecord]:
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
            foul_count = sum(
                1 for r in session.records if r.foul_label != "NO_FOUL"
            )
            return {
                "game_id": session.game_id,
                "total_records": len(session.records),
                "foul_count": foul_count,
                "no_foul_count": len(session.records) - foul_count,
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
    "FoulContactExtractor",
    "FoulContactExtractorConfig",
]

__version__ = "1.0.0"
