# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/live_workspace
파일: live_event_validator.py
설명: AI 감지 이벤트 신뢰도 기반 실시간 검증
      - 신뢰도 임계치 기반 자동 수락/거절/보류 분류
      - 게임 컨텍스트 기반 교차 검증 (데드볼/쿼터 전환 시 득점 불가 등)
      - 이벤트 시퀀스 논리 검증 (슛→리바운드/득점 순서)
      - 검증 이력 + 통계 제공

      Processing Cadence: 🟠 EVENT (<10ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/game_dto.py (GameEvent), shared/constants/game_rule_constants.py
의존성: Phase 1A (game_management 읽기), Phase 1B (event_detection 출력)
소비자: correction_sync.py, manual_event_tagger.py, Phase 2 statistics
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.50
_DEFAULT_HIGH_CONFIDENCE: Final[float] = 0.85
_MAX_PENDING_REVIEWS: Final[int] = 200
_MAX_VALIDATION_HISTORY: Final[int] = 5000

# 이벤트 유형별 최소 신뢰도 오버라이드 (높은 정확도 요구 이벤트)
# GameEventType(str, Enum) — .value는 lowercase (e.g., "shot_made")
_EVENT_MIN_CONFIDENCE: Final[dict[str, float]] = {
    # 득점 관련 — 정확도 중요
    "shot_made": 0.60,
    "free_throw_made": 0.55,
    # 파울 관련 — 오탐 비용 높음
    "personal_foul": 0.65,
    "offensive_foul": 0.70,
    "technical_foul": 0.75,
}

# 데드볼 중 발생 불가 이벤트
_DEAD_BALL_INVALID_EVENTS: Final[frozenset[str]] = frozenset({
    "shot_attempt", "shot_made", "shot_missed",
    "free_throw_attempt", "free_throw_made", "free_throw_missed",
    "steal", "block", "turnover",
})


# =============================================================================
# Enum
# =============================================================================
@unique
class ValidationStatus(Enum):
    """이벤트 검증 상태."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"

    @property
    def is_accepted(self) -> bool:
        return self == ValidationStatus.ACCEPTED

    @property
    def is_final(self) -> bool:
        return self in (ValidationStatus.ACCEPTED, ValidationStatus.REJECTED)


@unique
class RejectionReason(Enum):
    """이벤트 거절 사유."""
    LOW_CONFIDENCE = "low_confidence"
    DEAD_BALL_VIOLATION = "dead_ball_violation"
    SEQUENCE_VIOLATION = "sequence_violation"
    DUPLICATE_EVENT = "duplicate_event"
    INVALID_GAME_STATE = "invalid_game_state"
    MANUAL_REJECTION = "manual_rejection"


# =============================================================================
# 설정 클래스
# =============================================================================
@dataclass(slots=True)
class LiveEventValidatorConfig:
    """
    LiveEventValidator 설정.

    신뢰도 임계치와 검증 정책을 정의합니다.
    """

    # 신뢰도 임계치
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE
    high_confidence_threshold: float = _DEFAULT_HIGH_CONFIDENCE

    # 컨텍스트 검증
    context_validation_enabled: bool = True
    sequence_validation_enabled: bool = True
    duplicate_detection_enabled: bool = True

    # 중복 판정 기준 (동일 이벤트 프레임 차이)
    duplicate_frame_window: int = 15

    # 메모리 가드
    max_pending_reviews: int = _MAX_PENDING_REVIEWS
    max_validation_history: int = _MAX_VALIDATION_HISTORY

    @classmethod
    def from_yaml(cls, cfg: dict) -> LiveEventValidatorConfig:
        """YAML 설정에서 생성."""
        return cls(
            min_confidence=cfg.get("min_confidence", _DEFAULT_MIN_CONFIDENCE),
            high_confidence_threshold=cfg.get(
                "high_confidence_threshold", _DEFAULT_HIGH_CONFIDENCE,
            ),
            context_validation_enabled=cfg.get("context_validation_enabled", True),
            sequence_validation_enabled=cfg.get("sequence_validation_enabled", True),
            duplicate_detection_enabled=cfg.get("duplicate_detection_enabled", True),
            duplicate_frame_window=cfg.get("duplicate_frame_window", 15),
            max_pending_reviews=cfg.get("max_pending_reviews", _MAX_PENDING_REVIEWS),
            max_validation_history=cfg.get(
                "max_validation_history", _MAX_VALIDATION_HISTORY,
            ),
        )


# =============================================================================
# 출력 DTO
# =============================================================================
@dataclass(slots=True)
class ValidationResult:
    """
    이벤트 검증 결과.

    검증 상태, 조정된 신뢰도, 사유를 포함합니다.
    """

    validation_id: UUID
    event: GameEvent
    status: ValidationStatus
    original_confidence: float
    adjusted_confidence: float
    rejection_reason: RejectionReason | None = None
    reason_detail: str = ""
    validated_at: float = 0.0  # timestamp (초)

    @property
    def is_accepted(self) -> bool:
        return self.status == ValidationStatus.ACCEPTED

    @property
    def is_pending(self) -> bool:
        return self.status == ValidationStatus.PENDING_REVIEW


# =============================================================================
# 게임 컨텍스트 (game_management 상태 스냅샷)
# =============================================================================
@dataclass(slots=True)
class GameContext:
    """
    게임 상태 컨텍스트.

    game_management에서 읽어온 현재 게임 상태 스냅샷입니다.
    live_event_validator가 컨텍스트 검증에 사용합니다.
    """

    is_dead_ball: bool = False
    is_timeout: bool = False
    is_halftime: bool = False
    quarter: int = 1
    game_clock_sec: float = 600.0
    home_score: int = 0
    away_score: int = 0
    possession_team_id: str | None = None


# =============================================================================
# LiveEventValidator
# =============================================================================
class LiveEventValidator:
    """
    AI 감지 이벤트 실시간 검증기.

    이벤트 감지 모듈(Phase 1B)의 출력을 실시간으로 검증하여
    자동 수락(높은 신뢰도), 거절(낮은 신뢰도/규칙 위반),
    보류(중간 신뢰도, 사람 확인 필요)로 분류합니다.

    게임 컨텍스트(Phase 1A)를 활용한 교차 검증도 수행합니다.
    """

    def __init__(
        self,
        config: LiveEventValidatorConfig | None = None,
    ) -> None:
        self._config = config or LiveEventValidatorConfig()
        self._lock = RLock()

        # 검증 이력 (최근순)
        self._history: list[ValidationResult] = []
        # 보류 큐 (event_id → ValidationResult)
        self._pending_reviews: dict[UUID, ValidationResult] = {}
        # 최근 이벤트 캐시 (중복 감지용): (event_type_name, player_id) → frame_number
        self._recent_events: dict[tuple[str, int | None], int] = {}
        # 게임 컨텍스트
        self._game_context = GameContext()

        # 통계
        self._stats_accepted: int = 0
        self._stats_rejected: int = 0
        self._stats_pending: int = 0

    # === 속성 ===

    @property
    def name(self) -> str:
        return "LiveEventValidator"

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending_reviews)

    # === 게임 컨텍스트 업데이트 ===

    def update_game_context(self, context: GameContext) -> None:
        """
        게임 상태 컨텍스트 업데이트.

        game_management로부터 읽어온 상태를 반영합니다.

        Args:
            context: 현재 게임 상태 스냅샷
        """
        with self._lock:
            self._game_context = context

    # === 핵심 검증 ===

    def validate_event(self, event: GameEvent) -> ValidationResult:
        """
        단일 이벤트 검증.

        신뢰도 + 컨텍스트 + 시퀀스 규칙을 적용하여 검증합니다.

        Args:
            event: 검증할 GameEvent

        Returns:
            ValidationResult — 검증 결과
        """
        start_time = time.monotonic()

        with self._lock:
            # 1단계: 중복 감지
            if self._config.duplicate_detection_enabled:
                dup_result = self._check_duplicate(event)
                if dup_result is not None:
                    self._record_result(dup_result)
                    return dup_result

            # 2단계: 컨텍스트 검증 (데드볼 등)
            if self._config.context_validation_enabled:
                ctx_result = self._check_context(event)
                if ctx_result is not None:
                    self._record_result(ctx_result)
                    return ctx_result

            # 3단계: 신뢰도 기반 분류
            result = self._classify_by_confidence(event)

            # 4단계: 보류 큐 관리
            if result.status == ValidationStatus.PENDING_REVIEW:
                self._add_to_pending(result)

            # 최근 이벤트 캐시 갱신
            event_key = (event.event_type.value, event.primary_player_id)
            self._recent_events[event_key] = event.frame_number

            self._record_result(result)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        if elapsed_ms > 10.0:
            logger.warning(
                "이벤트 검증 지연: %.1fms (이벤트=%s, 프레임=%d)",
                elapsed_ms, event.event_type.value, event.frame_number,
            )

        return result

    def validate_batch(self, events: list[GameEvent]) -> list[ValidationResult]:
        """
        이벤트 배치 검증.

        Args:
            events: 검증할 GameEvent 리스트

        Returns:
            ValidationResult 리스트
        """
        return [self.validate_event(e) for e in events]

    # === 보류 이벤트 관리 ===

    def get_pending_reviews(self) -> list[ValidationResult]:
        """보류 중인 이벤트 목록 반환 (방어적 복사)."""
        with self._lock:
            return list(self._pending_reviews.values())

    def resolve_review(
        self,
        event_id: UUID,
        accept: bool,
        reason: str = "",
    ) -> ValidationResult | None:
        """
        보류 이벤트 검토 해결.

        사람이 보류 이벤트를 수락 또는 거절합니다.

        Args:
            event_id: 이벤트 ID
            accept: True=수락, False=거절
            reason: 판단 사유

        Returns:
            해결된 ValidationResult 또는 None (해당 이벤트 없음)
        """
        with self._lock:
            pending = self._pending_reviews.pop(event_id, None)
            if pending is None:
                return None

            resolved = ValidationResult(
                validation_id=uuid4(),
                event=pending.event,
                status=(
                    ValidationStatus.ACCEPTED if accept
                    else ValidationStatus.REJECTED
                ),
                original_confidence=pending.original_confidence,
                adjusted_confidence=(
                    pending.original_confidence if accept
                    else pending.original_confidence
                ),
                rejection_reason=(
                    None if accept
                    else RejectionReason.MANUAL_REJECTION
                ),
                reason_detail=reason,
                validated_at=time.time(),
            )

            # 통계 업데이트
            self._stats_pending -= 1
            if accept:
                self._stats_accepted += 1
            else:
                self._stats_rejected += 1

            self._append_history(resolved)
            return resolved

    # === 이력 / 통계 ===

    def get_validation_history(
        self,
        max_count: int = 100,
    ) -> list[ValidationResult]:
        """
        검증 이력 반환 (최근순, 방어적 복사).

        Args:
            max_count: 최대 반환 수

        Returns:
            ValidationResult 리스트
        """
        with self._lock:
            return list(self._history[-max_count:])

    def get_validation_stats(self) -> dict[str, int | float]:
        """
        검증 통계 반환.

        Returns:
            accepted, rejected, pending, total, accept_rate 포함 딕셔너리
        """
        with self._lock:
            total = self._stats_accepted + self._stats_rejected + self._stats_pending
            accept_rate = (
                self._stats_accepted / total if total > 0 else 0.0
            )
            return {
                "accepted": self._stats_accepted,
                "rejected": self._stats_rejected,
                "pending": self._stats_pending,
                "total": total,
                "accept_rate": round(accept_rate, 4),
                "history_size": len(self._history),
            }

    def get_event_history(self) -> list[ValidationResult]:
        """이벤트 이력 반환 (IGameEventDetector 호환)."""
        with self._lock:
            return list(self._history)

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._history.clear()
            self._pending_reviews.clear()
            self._recent_events.clear()
            self._game_context = GameContext()
            self._stats_accepted = 0
            self._stats_rejected = 0
            self._stats_pending = 0

    # === 내부 메서드 ===

    def _check_duplicate(self, event: GameEvent) -> ValidationResult | None:
        """중복 이벤트 감지."""
        event_key = (event.event_type.value, event.primary_player_id)
        prev_frame = self._recent_events.get(event_key)

        if prev_frame is not None:
            frame_diff = abs(event.frame_number - prev_frame)
            if frame_diff <= self._config.duplicate_frame_window:
                return ValidationResult(
                    validation_id=uuid4(),
                    event=event,
                    status=ValidationStatus.REJECTED,
                    original_confidence=event.confidence,
                    adjusted_confidence=0.0,
                    rejection_reason=RejectionReason.DUPLICATE_EVENT,
                    reason_detail=(
                        f"중복 이벤트 감지: {event.event_type.value}, "
                        f"프레임 차이={frame_diff} "
                        f"(임계={self._config.duplicate_frame_window})"
                    ),
                    validated_at=time.time(),
                )
        return None

    def _check_context(self, event: GameEvent) -> ValidationResult | None:
        """게임 컨텍스트 기반 검증."""
        ctx = self._game_context
        event_name = event.event_type.value

        # 데드볼 중 발생 불가 이벤트 검사
        if ctx.is_dead_ball and event_name in _DEAD_BALL_INVALID_EVENTS:
            return ValidationResult(
                validation_id=uuid4(),
                event=event,
                status=ValidationStatus.REJECTED,
                original_confidence=event.confidence,
                adjusted_confidence=0.0,
                rejection_reason=RejectionReason.DEAD_BALL_VIOLATION,
                reason_detail=(
                    f"데드볼 중 발생 불가 이벤트: {event_name}"
                ),
                validated_at=time.time(),
            )

        # 타임아웃/하프타임 중 플레이 이벤트 불가
        if (ctx.is_timeout or ctx.is_halftime) and event_name in _DEAD_BALL_INVALID_EVENTS:
            return ValidationResult(
                validation_id=uuid4(),
                event=event,
                status=ValidationStatus.REJECTED,
                original_confidence=event.confidence,
                adjusted_confidence=0.0,
                rejection_reason=RejectionReason.INVALID_GAME_STATE,
                reason_detail=(
                    f"타임아웃/하프타임 중 발생 불가: {event_name}"
                ),
                validated_at=time.time(),
            )

        return None

    def _classify_by_confidence(self, event: GameEvent) -> ValidationResult:
        """신뢰도 기반 수락/거절/보류 분류."""
        confidence = event.confidence
        event_name = event.event_type.value

        # 이벤트 유형별 최소 신뢰도 (오버라이드)
        min_conf = _EVENT_MIN_CONFIDENCE.get(
            event_name, self._config.min_confidence,
        )
        high_conf = self._config.high_confidence_threshold

        if confidence >= high_conf:
            # 높은 신뢰도 → 자동 수락
            status = ValidationStatus.ACCEPTED
            rejection_reason = None
            detail = f"높은 신뢰도 자동 수락: {confidence:.3f} >= {high_conf:.3f}"
            self._stats_accepted += 1
        elif confidence < min_conf:
            # 낮은 신뢰도 → 자동 거절
            status = ValidationStatus.REJECTED
            rejection_reason = RejectionReason.LOW_CONFIDENCE
            detail = (
                f"낮은 신뢰도 거절: {confidence:.3f} < {min_conf:.3f} "
                f"(이벤트={event_name})"
            )
            self._stats_rejected += 1
        else:
            # 중간 신뢰도 → 보류 (사람 확인 필요)
            status = ValidationStatus.PENDING_REVIEW
            rejection_reason = None
            detail = (
                f"중간 신뢰도 보류: {min_conf:.3f} <= {confidence:.3f} < {high_conf:.3f}"
            )
            self._stats_pending += 1

        return ValidationResult(
            validation_id=uuid4(),
            event=event,
            status=status,
            original_confidence=confidence,
            adjusted_confidence=confidence,
            rejection_reason=rejection_reason,
            reason_detail=detail,
            validated_at=time.time(),
        )

    def _add_to_pending(self, result: ValidationResult) -> None:
        """보류 큐에 추가 (메모리 가드 적용)."""
        if len(self._pending_reviews) >= self._config.max_pending_reviews:
            # 가장 오래된 보류 이벤트 자동 수락 (FIFO)
            oldest_id = next(iter(self._pending_reviews))
            oldest = self._pending_reviews.pop(oldest_id)
            auto_accepted = ValidationResult(
                validation_id=uuid4(),
                event=oldest.event,
                status=ValidationStatus.ACCEPTED,
                original_confidence=oldest.original_confidence,
                adjusted_confidence=oldest.original_confidence,
                reason_detail="보류 큐 초과로 자동 수락",
                validated_at=time.time(),
            )
            self._append_history(auto_accepted)
            self._stats_pending -= 1
            self._stats_accepted += 1

        self._pending_reviews[result.event.event_id] = result

    def _record_result(self, result: ValidationResult) -> None:
        """검증 결과 기록."""
        self._append_history(result)

    def _append_history(self, result: ValidationResult) -> None:
        """이력에 추가 (메모리 가드 적용)."""
        self._history.append(result)
        if len(self._history) > self._config.max_validation_history:
            # 오래된 이력 20% 정리
            trim_count = self._config.max_validation_history // 5
            del self._history[:trim_count]


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "LiveEventValidator",
    "LiveEventValidatorConfig",
    "ValidationResult",
    "ValidationStatus",
    "RejectionReason",
    "GameContext",
]

__version__ = "1.0.0"
