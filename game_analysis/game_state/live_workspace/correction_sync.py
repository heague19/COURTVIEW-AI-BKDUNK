# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/live_workspace
파일: correction_sync.py
설명: 보정 동기화 + 증분 재계산 트리거
      - AI 이벤트와 수동 보정의 동기화
      - 보정 발생 시 영향 받는 모듈에 재계산 트리거 발행
      - 보정 이력 관리 (원본/수정 이벤트 쌍 추적)
      - 재계산 트리거 큐 관리 (Phase 2 statistics 등이 소비)

      Processing Cadence: 🟠 EVENT (<10ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/game_dto.py (GameEvent)
의존성: live_event_validator.py, manual_event_tagger.py
소비자: Phase 2 statistics (증분 재계산), Phase 3+ (캐시 무효화)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.game_dto import GameEvent

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_CORRECTION_HISTORY: Final[int] = 2000
_MAX_PENDING_TRIGGERS: Final[int] = 500
_MAX_AFFECTED_MODULES: Final[int] = 30


# =============================================================================
# Enum
# =============================================================================
@unique
class CorrectionType(Enum):
    """보정 유형."""
    EVENT_ADDED = "event_added"             # 수동 이벤트 추가
    EVENT_REMOVED = "event_removed"         # 이벤트 삭제 (오탐 제거)
    EVENT_MODIFIED = "event_modified"       # 이벤트 필드 수정
    CONFIDENCE_ADJUSTED = "confidence_adjusted"  # 신뢰도 조정
    EVENT_RECLASSIFIED = "event_reclassified"    # 이벤트 유형 재분류

    @property
    def requires_stat_recalc(self) -> bool:
        """통계 재계산이 필요한 보정인지."""
        return self in (
            CorrectionType.EVENT_ADDED,
            CorrectionType.EVENT_REMOVED,
            CorrectionType.EVENT_MODIFIED,
            CorrectionType.EVENT_RECLASSIFIED,
        )

    @property
    def display_name_ko(self) -> str:
        """한글 표시명."""
        names = {
            "event_added": "이벤트 추가",
            "event_removed": "이벤트 삭제",
            "event_modified": "이벤트 수정",
            "confidence_adjusted": "신뢰도 조정",
            "event_reclassified": "이벤트 재분류",
        }
        return names.get(self.value, self.value)


@unique
class RecalcScope(Enum):
    """재계산 범위."""
    INCREMENTAL = "incremental"   # 영향 받는 이벤트만 증분 재계산
    QUARTER = "quarter"           # 해당 쿼터 전체 재계산
    FULL_GAME = "full_game"       # 경기 전체 재계산

    @property
    def priority(self) -> int:
        """재계산 우선순위 (낮을수록 긴급)."""
        priorities = {
            "incremental": 2,
            "quarter": 1,
            "full_game": 0,
        }
        return priorities.get(self.value, 2)


@unique
class TriggerStatus(Enum):
    """트리거 상태."""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    EXPIRED = "expired"


# =============================================================================
# 설정 클래스
# =============================================================================
@dataclass(slots=True)
class CorrectionSyncConfig:
    """
    CorrectionSync 설정.

    보정 동기화 + 재계산 트리거 정책을 정의합니다.
    """

    max_correction_history: int = _MAX_CORRECTION_HISTORY
    max_pending_triggers: int = _MAX_PENDING_TRIGGERS

    # 재계산 정책
    auto_trigger_enabled: bool = True
    default_recalc_scope: RecalcScope = RecalcScope.INCREMENTAL

    # 트리거 만료 (초) — 소비자가 수신하지 않으면 만료
    trigger_expiry_sec: float = 60.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> CorrectionSyncConfig:
        """YAML 설정에서 생성."""
        scope_str = cfg.get("default_recalc_scope", "incremental")
        try:
            scope = RecalcScope(scope_str)
        except ValueError:
            logger.warning(
                "알 수 없는 재계산 범위 '%s', INCREMENTAL 기본 적용", scope_str,
            )
            scope = RecalcScope.INCREMENTAL

        return cls(
            max_correction_history=cfg.get(
                "max_correction_history", _MAX_CORRECTION_HISTORY,
            ),
            max_pending_triggers=cfg.get(
                "max_pending_triggers", _MAX_PENDING_TRIGGERS,
            ),
            auto_trigger_enabled=cfg.get("auto_trigger_enabled", True),
            default_recalc_scope=scope,
            trigger_expiry_sec=cfg.get("trigger_expiry_sec", 60.0),
        )


# =============================================================================
# 출력 DTO
# =============================================================================
@dataclass(slots=True)
class CorrectionRecord:
    """
    보정 기록.

    원본 이벤트와 보정된 이벤트의 쌍을 추적합니다.
    """

    correction_id: UUID
    correction_type: CorrectionType
    original_event: GameEvent | None  # 추가의 경우 None
    corrected_event: GameEvent | None  # 삭제의 경우 None
    reason: str = ""
    corrector_id: str = ""
    quarter: int | None = None
    created_at: float = 0.0

    @property
    def event_id(self) -> UUID | None:
        """관련 이벤트 ID."""
        if self.corrected_event is not None:
            return self.corrected_event.event_id
        if self.original_event is not None:
            return self.original_event.event_id
        return None


@dataclass(slots=True)
class RecalcTrigger:
    """
    재계산 트리거.

    보정 발생 시 Phase 2+ 모듈에 재계산을 알립니다.
    """

    trigger_id: UUID
    correction_id: UUID
    scope: RecalcScope
    status: TriggerStatus = TriggerStatus.PENDING
    affected_event_ids: list[UUID] = field(default_factory=list)
    affected_quarters: list[int] = field(default_factory=list)
    target_modules: list[str] = field(default_factory=list)
    created_at: float = 0.0
    acknowledged_at: float | None = None

    @property
    def is_pending(self) -> bool:
        return self.status == TriggerStatus.PENDING

    @property
    def is_expired(self) -> bool:
        return self.status == TriggerStatus.EXPIRED


# =============================================================================
# 영향 모듈 매핑 — 보정 유형별 재계산 대상
# =============================================================================
_AFFECTED_MODULES: Final[dict[str, list[str]]] = {
    # GameEventType(str, Enum) — .value는 lowercase (e.g., "shot_made")
    # 득점 관련 이벤트 → 통계 + 슛 차트 + 게임 기록
    "shot_made": ["statistics", "shot_location", "game_record", "highlight"],
    "shot_missed": ["statistics", "shot_location", "game_record"],
    "shot_attempt": ["statistics", "shot_location"],
    "free_throw_made": ["statistics", "game_record"],
    "free_throw_missed": ["statistics", "game_record"],
    # 이벤트 관련 → 통계 + 전술
    "assist": ["statistics", "game_record"],
    "offensive_rebound": ["statistics", "game_record"],
    "defensive_rebound": ["statistics", "game_record"],
    "steal": ["statistics", "game_record"],
    "block": ["statistics", "game_record"],
    "turnover": ["statistics", "game_record"],
    # 파울 관련 → 게임 관리 + 통계
    "personal_foul": ["statistics", "game_record"],
    "offensive_foul": ["statistics", "game_record"],
    "technical_foul": ["statistics", "game_record"],
}


# =============================================================================
# CorrectionSync
# =============================================================================
class CorrectionSync:
    """
    보정 동기화 관리자.

    AI 이벤트와 수동 보정 사이의 동기화를 관리하고,
    보정 발생 시 영향 받는 모듈에 재계산 트리거를 발행합니다.

    Phase 2 statistics 등의 소비 모듈은 pending trigger를
    폴링하여 증분 재계산을 수행합니다.
    """

    def __init__(
        self,
        config: CorrectionSyncConfig | None = None,
    ) -> None:
        self._config = config or CorrectionSyncConfig()
        self._lock = RLock()

        # 보정 이력
        self._corrections: list[CorrectionRecord] = []
        # 재계산 트리거 큐 (trigger_id → RecalcTrigger)
        self._triggers: dict[UUID, RecalcTrigger] = {}

        # 통계
        self._stats_corrections: int = 0
        self._stats_triggers_issued: int = 0
        self._stats_triggers_acknowledged: int = 0

    # === 속성 ===

    @property
    def name(self) -> str:
        return "CorrectionSync"

    @property
    def pending_trigger_count(self) -> int:
        with self._lock:
            return sum(
                1 for t in self._triggers.values()
                if t.status == TriggerStatus.PENDING
            )

    # === 보정 기록 ===

    def record_correction(
        self,
        correction_type: CorrectionType,
        original_event: GameEvent | None = None,
        corrected_event: GameEvent | None = None,
        *,
        reason: str = "",
        corrector_id: str = "",
    ) -> CorrectionRecord:
        """
        보정 기록 + 재계산 트리거 발행.

        Args:
            correction_type: 보정 유형
            original_event: 원본 이벤트 (추가의 경우 None)
            corrected_event: 보정된 이벤트 (삭제의 경우 None)
            reason: 보정 사유
            corrector_id: 보정자 ID

        Returns:
            CorrectionRecord — 보정 기록
        """
        # 쿼터 추출
        quarter = None
        ref_event = corrected_event or original_event
        if ref_event is not None:
            quarter = ref_event.quarter

        record = CorrectionRecord(
            correction_id=uuid4(),
            correction_type=correction_type,
            original_event=original_event,
            corrected_event=corrected_event,
            reason=reason,
            corrector_id=corrector_id,
            quarter=quarter,
            created_at=time.time(),
        )

        with self._lock:
            # 보정 이력 추가
            self._corrections.append(record)
            self._stats_corrections += 1

            # 메모리 가드
            if len(self._corrections) > self._config.max_correction_history:
                trim = self._config.max_correction_history // 5
                del self._corrections[:trim]

            # 자동 재계산 트리거 발행
            if (
                self._config.auto_trigger_enabled
                and correction_type.requires_stat_recalc
            ):
                self._issue_trigger(record)

        logger.info(
            "보정 기록: type=%s, event_id=%s, reason=%s",
            correction_type.value,
            record.event_id,
            reason[:50],
        )
        return record

    # === 트리거 관리 ===

    def get_pending_triggers(
        self,
        module_name: str | None = None,
    ) -> list[RecalcTrigger]:
        """
        대기 중인 재계산 트리거 조회.

        소비 모듈이 폴링하여 재계산 대상을 확인합니다.

        Args:
            module_name: 특정 모듈 필터 (None=전체)

        Returns:
            RecalcTrigger 리스트 (우선순위순)
        """
        now = time.time()
        with self._lock:
            # 만료 처리
            self._expire_old_triggers(now)

            pending = [
                t for t in self._triggers.values()
                if t.status == TriggerStatus.PENDING
            ]

            if module_name is not None:
                pending = [
                    t for t in pending
                    if module_name in t.target_modules
                ]

            # 우선순위 정렬 (낮을수록 긴급)
            pending.sort(key=lambda t: t.scope.priority)
            return pending

    def acknowledge_trigger(self, trigger_id: UUID) -> bool:
        """
        트리거 수신 확인.

        소비 모듈이 트리거를 수신했음을 알립니다.

        Args:
            trigger_id: 트리거 ID

        Returns:
            성공 여부
        """
        with self._lock:
            trigger = self._triggers.get(trigger_id)
            if trigger is None or trigger.status != TriggerStatus.PENDING:
                return False

            trigger.status = TriggerStatus.ACKNOWLEDGED
            trigger.acknowledged_at = time.time()
            self._stats_triggers_acknowledged += 1
            return True

    def complete_trigger(self, trigger_id: UUID) -> bool:
        """
        트리거 완료 처리.

        소비 모듈이 재계산을 완료했음을 알립니다.

        Args:
            trigger_id: 트리거 ID

        Returns:
            성공 여부
        """
        with self._lock:
            trigger = self._triggers.get(trigger_id)
            if trigger is None:
                return False

            trigger.status = TriggerStatus.COMPLETED
            return True

    # === 조회 ===

    def get_corrections(
        self,
        event_id: UUID | None = None,
        max_count: int = 100,
    ) -> list[CorrectionRecord]:
        """
        보정 이력 조회.

        Args:
            event_id: 특정 이벤트 필터 (None=전체)
            max_count: 최대 반환 수

        Returns:
            CorrectionRecord 리스트
        """
        with self._lock:
            if event_id is not None:
                filtered = [
                    c for c in self._corrections
                    if c.event_id == event_id
                ]
                return filtered[-max_count:]
            return list(self._corrections[-max_count:])

    def get_correction_stats(self) -> dict[str, int | float]:
        """
        보정 통계 반환.

        Returns:
            corrections, triggers_issued, triggers_acknowledged 등 딕셔너리
        """
        with self._lock:
            pending_count = sum(
                1 for t in self._triggers.values()
                if t.status == TriggerStatus.PENDING
            )
            by_type: dict[str, int] = {}
            for c in self._corrections:
                key = c.correction_type.value
                by_type[key] = by_type.get(key, 0) + 1

            return {
                "total_corrections": self._stats_corrections,
                "triggers_issued": self._stats_triggers_issued,
                "triggers_acknowledged": self._stats_triggers_acknowledged,
                "triggers_pending": pending_count,
                "corrections_by_type": by_type,
                "history_size": len(self._corrections),
            }

    def get_event_history(self) -> list[CorrectionRecord]:
        """이벤트 이력 반환 (호환 인터페이스)."""
        with self._lock:
            return list(self._corrections)

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._corrections.clear()
            self._triggers.clear()
            self._stats_corrections = 0
            self._stats_triggers_issued = 0
            self._stats_triggers_acknowledged = 0

    # === 내부 메서드 ===

    def _issue_trigger(self, record: CorrectionRecord) -> None:
        """재계산 트리거 발행."""
        # 영향 모듈 결정
        ref_event = record.corrected_event or record.original_event
        event_type_name = ref_event.event_type.value if ref_event else ""
        target_modules = list(
            _AFFECTED_MODULES.get(event_type_name, ["statistics"]),
        )

        # 영향 이벤트 ID
        affected_ids: list[UUID] = []
        if record.original_event is not None:
            affected_ids.append(record.original_event.event_id)
        if (
            record.corrected_event is not None
            and record.corrected_event.event_id not in affected_ids
        ):
            affected_ids.append(record.corrected_event.event_id)

        # 쿼터 정보
        affected_quarters: list[int] = []
        if record.quarter is not None:
            affected_quarters.append(record.quarter)

        trigger = RecalcTrigger(
            trigger_id=uuid4(),
            correction_id=record.correction_id,
            scope=self._config.default_recalc_scope,
            affected_event_ids=affected_ids,
            affected_quarters=affected_quarters,
            target_modules=target_modules,
            created_at=time.time(),
        )

        # 메모리 가드
        if len(self._triggers) >= self._config.max_pending_triggers:
            # 완료/만료된 트리거 정리
            self._cleanup_triggers()
            # 그래도 초과하면 가장 오래된 pending 제거
            if len(self._triggers) >= self._config.max_pending_triggers:
                oldest_id = next(
                    (tid for tid, t in self._triggers.items()
                     if t.status == TriggerStatus.PENDING),
                    None,
                )
                if oldest_id is not None:
                    self._triggers[oldest_id].status = TriggerStatus.EXPIRED
                    del self._triggers[oldest_id]

        self._triggers[trigger.trigger_id] = trigger
        self._stats_triggers_issued += 1

    def _expire_old_triggers(self, now: float) -> None:
        """만료된 트리거 상태 변경."""
        expiry = self._config.trigger_expiry_sec
        for trigger in self._triggers.values():
            if (
                trigger.status == TriggerStatus.PENDING
                and (now - trigger.created_at) > expiry
            ):
                trigger.status = TriggerStatus.EXPIRED

    def _cleanup_triggers(self) -> None:
        """완료/만료 트리거 정리."""
        to_remove = [
            tid for tid, t in self._triggers.items()
            if t.status in (TriggerStatus.COMPLETED, TriggerStatus.EXPIRED)
        ]
        for tid in to_remove:
            del self._triggers[tid]


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "CorrectionSync",
    "CorrectionSyncConfig",
    "CorrectionRecord",
    "CorrectionType",
    "RecalcTrigger",
    "RecalcScope",
    "TriggerStatus",
]

__version__ = "1.0.0"
