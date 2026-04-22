# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/rules
파일: base_rule.py
설명: 규칙 추상 클래스 + 공통 인터페이스
      - BaseRule: 모든 규칙의 ABC (applies_to / evaluate)
      - ViolationRule: 바이올레이션 규칙 베이스 (12종)
      - FoulRule: 파울 규칙 베이스 (11종)
      - RuleResult: 규칙 평가 결과 (confidence + 근거)
      - RuleCategory: 규칙 카테고리 (VIOLATION / FOUL / TECHNICAL)
      - FrameContext: 프레임 단위 입력 데이터 컨테이너

      리그별 규칙 클래스(fiba_rules, nba_rules 등)가 이 ABC를 상속합니다.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - shared/constants/referee_rule_constants.py: RuleSet, CallType
    - shared/constants/game_rule_constants.py: ViolationType, FoulType
    - shared/constants/referee_decision_constants.py: ContactArea, DecisionConfidence
    - configs/ai_referee/*.yaml: 리그별 규칙 + 임계치
"""

from __future__ import annotations

# === 표준 라이브러리 ===
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID, uuid4

# === 프로젝트 모듈 ===
from shared.constants.game_rule_constants import FoulType, ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

if TYPE_CHECKING:
    pass

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.50


# =============================================================================
# Enum
# =============================================================================
@unique
class RuleCategory(str, Enum):
    """
    규칙 카테고리.

    규칙이 바이올레이션인지 파울인지 테크니컬인지 분류합니다.
    """

    VIOLATION = "violation"
    FOUL = "foul"
    TECHNICAL = "technical"

    def __str__(self) -> str:
        return self.value

    @property
    def display_name_ko(self) -> str:
        """한글 표시명."""
        names = {
            "violation": "바이올레이션",
            "foul": "파울",
            "technical": "테크니컬",
        }
        return names.get(self.value, self.value)

    @property
    def stops_play(self) -> bool:
        """경기 중단 여부 (모든 판정은 경기를 중단)."""
        return True


@unique
class PenaltyType(str, Enum):
    """
    페널티 유형.

    규칙 위반 시 적용되는 페널티 종류입니다.
    """

    TURNOVER = "turnover"                   # 공격권 전환 (바이올레이션)
    FREE_THROWS = "free_throws"             # 자유투
    FREE_THROWS_AND_POSSESSION = "free_throws_and_possession"  # FT + 점유
    JUMP_BALL = "jump_ball"                 # 점프볼 (헬드볼 등)
    TECHNICAL_FREE_THROW = "technical_free_throw"  # 테크니컬 FT (1구 + 점유)
    EJECTION = "ejection"                   # 퇴장
    NONE = "none"                           # 페널티 없음 (어드밴티지 등)

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 데이터 클래스
# =============================================================================
@dataclass(slots=True)
class FrameContext:
    """
    프레임 단위 입력 컨텍스트.

    violations/fouls detector가 규칙 평가에 필요한 데이터를 담는 컨테이너.
    하위 레이어(detection, pose, biomechanics, motion, game_analysis)의
    출력을 DTO 기반으로 전달받습니다.
    """

    frame_number: int = 0
    timestamp: float = 0.0                   # 영상 내 시간 (초)
    fps: float = 30.0                        # 영상 FPS (LGP/지속프레임 계산 기준)

    # 경기 상태 (game_management)
    quarter: int = 1
    game_clock_sec: float = 600.0
    shot_clock_sec: float = 24.0
    is_dead_ball: bool = False
    is_live_ball: bool = True
    possession_team_id: str | None = None

    # 선수 위치 (detection)
    player_positions: dict[int, tuple[float, float]] = field(default_factory=dict)

    # 공 위치 (detection)
    ball_position: tuple[float, float, float] | None = None  # (x, y, z)
    ball_possession_player_id: int | None = None

    # 키포인트 (pose_estimation) — player_id → dict[str, (x, y, z)]
    player_keypoints: dict[int, dict[str, tuple[float, float, float]]] = field(
        default_factory=dict,
    )

    # 관절 속도/가속도 (biomechanics)
    joint_velocities: dict[int, dict[str, float]] = field(default_factory=dict)
    joint_accelerations: dict[int, dict[str, float]] = field(default_factory=dict)

    # 동작 분류 (motion_analysis)
    player_actions: dict[int, str] = field(default_factory=dict)

    # 코트 정보
    court_boundaries: dict[str, float] = field(default_factory=dict)
    paint_zone_bounds: dict[str, float] = field(default_factory=dict)
    half_court_x: float = 0.0

    # 추가 데이터 (확장용)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuleResult:
    """
    규칙 평가 결과.

    단일 규칙에 대한 평가 결과로, 위반 여부, 신뢰도, 근거를 포함합니다.
    violations/fouls detector가 반환하는 표준 출력 형식입니다.
    """

    result_id: UUID = field(default_factory=uuid4)

    # 위반 판정
    violated: bool = False
    confidence: float = 0.0                  # 0.0~1.0

    # 규칙 정보
    rule_id: str = ""                        # "FIBA-25.1" 형식
    rule_set: RuleSet = RuleSet.FIBA
    category: RuleCategory = RuleCategory.VIOLATION
    call_type: CallType = CallType.NO_CALL

    # 위반 세부 (바이올레이션 또는 파울 유형)
    violation_type: ViolationType | None = None
    foul_type: FoulType | None = None

    # 프레임 정보
    frame_number: int = 0
    start_frame: int = 0                     # 위반 시작 프레임
    end_frame: int = 0                       # 위반 종료 프레임

    # 관련 선수
    offending_player_id: int | None = None   # 위반 선수
    victim_player_id: int | None = None      # 피해 선수

    # 페널티
    penalty: PenaltyType = PenaltyType.NONE
    free_throws_awarded: int = 0
    possession_change: bool = False

    # 근거
    rule_reference: str = ""                 # "FIBA Rule 25.1.1" 형식
    description: str = ""                    # 판정 설명 (한글)
    evidence: list[str] = field(default_factory=list)  # 근거 목록

    # 타임스탬프
    evaluated_at: float = 0.0                # 평가 시점 (time.time())

    @property
    def is_violation(self) -> bool:
        return self.category == RuleCategory.VIOLATION and self.violated

    @property
    def is_foul(self) -> bool:
        return self.category == RuleCategory.FOUL and self.violated

    @property
    def frame_range(self) -> tuple[int, int]:
        """위반 프레임 범위."""
        return (self.start_frame, self.end_frame)


@dataclass(slots=True)
class RuleParameters:
    """
    규칙 파라미터.

    YAML에서 로딩된 규칙별 임계치/설정값을 담는 컨테이너입니다.
    """

    rule_id: str = ""
    rule_reference: str = ""
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE
    parameters: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """파라미터 값 조회 (중첩 키 지원: 'a.b.c')."""
        keys = key.split(".")
        current: Any = self.parameters
        for k in keys:
            if isinstance(current, dict):
                current = current.get(k)
                if current is None:
                    return default
            else:
                return default
        return current

    def get_float(self, key: str, default: float = 0.0) -> float:
        """float 파라미터 조회."""
        val = self.get(key, default)
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    def get_int(self, key: str, default: int = 0) -> int:
        """int 파라미터 조회."""
        val = self.get(key, default)
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """bool 파라미터 조회."""
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        return default


# =============================================================================
# BaseRule ABC
# =============================================================================
class BaseRule(ABC):
    """
    규칙 추상 클래스.

    모든 바이올레이션/파울 규칙의 기반 클래스입니다.
    리그별 규칙 클래스(FIBARules, NBARules 등)가 이 ABC를 상속하여
    리그별 규칙 세트를 구성합니다.

    각 규칙은 다음 인터페이스를 구현합니다:
      - applies_to(context): 이 규칙이 적용되는 상황인지 판정
      - evaluate(context): 규칙 위반 여부 평가 → RuleResult 반환
    """

    def __init__(
        self,
        rule_id: str,
        rule_set: RuleSet,
        category: RuleCategory,
        call_type: CallType,
        *,
        rule_reference: str = "",
        description: str = "",
        parameters: RuleParameters | None = None,
    ) -> None:
        self._rule_id = rule_id
        self._rule_set = rule_set
        self._category = category
        self._call_type = call_type
        self._rule_reference = rule_reference
        self._description = description
        self._parameters = parameters or RuleParameters(rule_id=rule_id)
        self._lock = RLock()

        # 평가 이력 (통계/디버깅용)
        self._eval_count: int = 0
        self._violation_count: int = 0
        self._last_result: RuleResult | None = None

        # 규칙 활성화 플래그
        self._enabled: bool = True

    # === 속성 ===

    @property
    def rule_id(self) -> str:
        """규칙 ID (예: 'FIBA-25.1')."""
        return self._rule_id

    @property
    def rule_set(self) -> RuleSet:
        """적용 리그."""
        return self._rule_set

    @property
    def category(self) -> RuleCategory:
        """규칙 카테고리."""
        return self._category

    @property
    def call_type(self) -> CallType:
        """판정 유형."""
        return self._call_type

    @property
    def rule_reference(self) -> str:
        """규정 참조 (예: 'FIBA Rule 25.1')."""
        return self._rule_reference

    @property
    def description(self) -> str:
        """규칙 설명."""
        return self._description

    @property
    def parameters(self) -> RuleParameters:
        """규칙 파라미터."""
        return self._parameters

    @property
    def enabled(self) -> bool:
        """규칙 활성화 여부."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def min_confidence(self) -> float:
        """최소 신뢰도 임계치."""
        return self._parameters.min_confidence

    # === 추상 메서드 ===

    @abstractmethod
    def applies_to(self, context: FrameContext) -> bool:
        """
        이 규칙이 적용되는 상황인지 판정.

        데드볼/타임아웃 등 적용 불가 상황을 빠르게 필터링합니다.

        Args:
            context: 프레임 단위 입력 데이터

        Returns:
            True면 evaluate() 호출, False면 스킵
        """

    @abstractmethod
    def evaluate(self, context: FrameContext) -> RuleResult:
        """
        규칙 위반 여부 평가.

        프레임 데이터를 분석하여 위반 여부와 신뢰도를 반환합니다.

        Args:
            context: 프레임 단위 입력 데이터

        Returns:
            RuleResult — 위반 여부, 신뢰도, 근거 포함
        """

    # === 공통 메서드 ===

    def check(self, context: FrameContext) -> RuleResult:
        """
        규칙 검사 (applies_to + evaluate 통합).

        비활성화 또는 적용 불가 상황이면 NO_CALL 결과를 반환합니다.
        활성화 + 적용 가능이면 evaluate()를 호출합니다.

        Args:
            context: 프레임 단위 입력 데이터

        Returns:
            RuleResult
        """
        # 비활성화 규칙
        if not self._enabled:
            return self._no_call_result(context, "규칙 비활성화")

        # 적용 불가 상황
        if not self.applies_to(context):
            return self._no_call_result(context, "적용 불가 상황")

        # 평가 실행
        result = self.evaluate(context)

        # 통계 업데이트
        with self._lock:
            self._eval_count += 1
            if result.violated:
                self._violation_count += 1
            self._last_result = result

        return result

    def update_parameters(self, params: RuleParameters) -> None:
        """
        규칙 파라미터 업데이트.

        YAML 리로드 시 런타임에 파라미터를 갱신합니다.

        Args:
            params: 새 파라미터
        """
        with self._lock:
            self._parameters = params
            logger.debug(
                "규칙 파라미터 업데이트: rule_id=%s, min_conf=%.2f",
                self._rule_id, params.min_confidence,
            )

    def get_stats(self) -> dict[str, int | float | str]:
        """
        규칙 평가 통계 반환.

        Returns:
            eval_count, violation_count, violation_rate 등 딕셔너리
        """
        with self._lock:
            rate = (
                self._violation_count / self._eval_count
                if self._eval_count > 0
                else 0.0
            )
            return {
                "rule_id": self._rule_id,
                "rule_set": self._rule_set.value,
                "category": self._category.value,
                "enabled": self._enabled,
                "eval_count": self._eval_count,
                "violation_count": self._violation_count,
                "violation_rate": round(rate, 4),
            }

    def reset(self) -> None:
        """통계 초기화."""
        with self._lock:
            self._eval_count = 0
            self._violation_count = 0
            self._last_result = None

    # === 내부 헬퍼 ===

    def _no_call_result(self, context: FrameContext, reason: str) -> RuleResult:
        """NO_CALL 결과 생성."""
        return RuleResult(
            violated=False,
            confidence=0.0,
            rule_id=self._rule_id,
            rule_set=self._rule_set,
            category=self._category,
            call_type=CallType.NO_CALL,
            frame_number=context.frame_number,
            start_frame=context.frame_number,
            end_frame=context.frame_number,
            rule_reference=self._rule_reference,
            description=reason,
            evaluated_at=time.time(),
        )

    def _make_result(
        self,
        context: FrameContext,
        *,
        violated: bool,
        confidence: float,
        description: str = "",
        evidence: list[str] | None = None,
        offending_player_id: int | None = None,
        victim_player_id: int | None = None,
        start_frame: int | None = None,
        end_frame: int | None = None,
        violation_type: ViolationType | None = None,
        foul_type: FoulType | None = None,
        penalty: PenaltyType = PenaltyType.NONE,
        free_throws_awarded: int = 0,
        possession_change: bool = False,
    ) -> RuleResult:
        """표준 RuleResult 생성 헬퍼."""
        return RuleResult(
            violated=violated,
            confidence=min(max(confidence, 0.0), 1.0),
            rule_id=self._rule_id,
            rule_set=self._rule_set,
            category=self._category,
            call_type=self._call_type if violated else CallType.NO_CALL,
            violation_type=violation_type,
            foul_type=foul_type,
            frame_number=context.frame_number,
            start_frame=start_frame if start_frame is not None else context.frame_number,
            end_frame=end_frame if end_frame is not None else context.frame_number,
            offending_player_id=offending_player_id,
            victim_player_id=victim_player_id,
            penalty=penalty,
            free_throws_awarded=free_throws_awarded,
            possession_change=possession_change,
            rule_reference=self._rule_reference,
            description=description or self._description,
            evidence=evidence or [],
            evaluated_at=time.time(),
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"rule_id={self._rule_id!r}, "
            f"rule_set={self._rule_set.value}, "
            f"category={self._category.value}, "
            f"enabled={self._enabled})"
        )


# =============================================================================
# ViolationRule — 바이올레이션 규칙 베이스
# =============================================================================
class ViolationRule(BaseRule):
    """
    바이올레이션 규칙 베이스.

    접촉 없는 규칙 위반 12종의 공통 베이스입니다.
    violations/ 디렉토리의 detector 클래스들이 이 클래스를 상속합니다.

    페널티: 기본적으로 공격권 전환 (TURNOVER)
    """

    def __init__(
        self,
        rule_id: str,
        rule_set: RuleSet,
        call_type: CallType,
        violation_type: ViolationType,
        *,
        rule_reference: str = "",
        description: str = "",
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=rule_id,
            rule_set=rule_set,
            category=RuleCategory.VIOLATION,
            call_type=call_type,
            rule_reference=rule_reference,
            description=description,
            parameters=parameters,
        )
        self._violation_type = violation_type

    @property
    def violation_type(self) -> ViolationType:
        """바이올레이션 유형."""
        return self._violation_type

    def _make_violation_result(
        self,
        context: FrameContext,
        *,
        violated: bool,
        confidence: float,
        description: str = "",
        evidence: list[str] | None = None,
        offending_player_id: int | None = None,
        start_frame: int | None = None,
        end_frame: int | None = None,
    ) -> RuleResult:
        """바이올레이션 전용 결과 생성 헬퍼."""
        return self._make_result(
            context,
            violated=violated,
            confidence=confidence,
            description=description,
            evidence=evidence,
            offending_player_id=offending_player_id,
            start_frame=start_frame,
            end_frame=end_frame,
            violation_type=self._violation_type,
            penalty=PenaltyType.TURNOVER if violated else PenaltyType.NONE,
            possession_change=violated,
        )


# =============================================================================
# FoulRule — 파울 규칙 베이스
# =============================================================================
class FoulRule(BaseRule):
    """
    파울 규칙 베이스.

    접촉 기반 파울 11종의 공통 베이스입니다.
    fouls/ 디렉토리의 detector 클래스들이 이 클래스를 상속합니다.

    페널티: 파울 유형/상황에 따라 FT 부여, 점유 전환 등
    """

    def __init__(
        self,
        rule_id: str,
        rule_set: RuleSet,
        call_type: CallType,
        foul_type: FoulType,
        *,
        rule_reference: str = "",
        description: str = "",
        parameters: RuleParameters | None = None,
        default_free_throws: int = 0,
    ) -> None:
        super().__init__(
            rule_id=rule_id,
            rule_set=rule_set,
            category=RuleCategory.FOUL,
            call_type=call_type,
            rule_reference=rule_reference,
            description=description,
            parameters=parameters,
        )
        self._foul_type = foul_type
        self._default_free_throws = default_free_throws

    @property
    def foul_type(self) -> FoulType:
        """파울 유형."""
        return self._foul_type

    @property
    def default_free_throws(self) -> int:
        """기본 자유투 수."""
        return self._default_free_throws

    def _make_foul_result(
        self,
        context: FrameContext,
        *,
        violated: bool,
        confidence: float,
        description: str = "",
        evidence: list[str] | None = None,
        offending_player_id: int | None = None,
        victim_player_id: int | None = None,
        start_frame: int | None = None,
        end_frame: int | None = None,
        free_throws_awarded: int | None = None,
        possession_change: bool = False,
        penalty: PenaltyType | None = None,
    ) -> RuleResult:
        """파울 전용 결과 생성 헬퍼."""
        if free_throws_awarded is None:
            free_throws_awarded = self._default_free_throws if violated else 0

        if penalty is None:
            if violated and free_throws_awarded > 0:
                penalty = PenaltyType.FREE_THROWS
            elif violated:
                penalty = PenaltyType.TURNOVER
            else:
                penalty = PenaltyType.NONE

        return self._make_result(
            context,
            violated=violated,
            confidence=confidence,
            description=description,
            evidence=evidence,
            offending_player_id=offending_player_id,
            victim_player_id=victim_player_id,
            start_frame=start_frame,
            end_frame=end_frame,
            foul_type=self._foul_type,
            penalty=penalty,
            free_throws_awarded=free_throws_awarded,
            possession_change=possession_change,
        )


# =============================================================================
# Export
# =============================================================================
__all__ = [
    # Enum
    "RuleCategory",
    "PenaltyType",
    # 데이터 클래스
    "FrameContext",
    "RuleResult",
    "RuleParameters",
    # 규칙 ABC
    "BaseRule",
    "ViolationRule",
    "FoulRule",
]

__version__ = "1.0.0"
