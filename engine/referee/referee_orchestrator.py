# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/referee
파일: referee_orchestrator.py
설명: AI 심판 통합 판정 오케스트레이터
      - ai_referee/rules/rule_loader.py로 리그별 규칙 세트 로딩
      - ai_referee/violations/ 12종 바이올레이션 감지기 직접 연동
      - ai_referee/fouls/ 11종 파울 감지기 직접 연동
      - ai_referee/decisions/ 판정 엔진 6모듈 직접 연동
      - BaseRule.check(context) → RuleResult 수집 → DecisionEngine → FinalDecision

      초기화 흐름:
        1. RuleLoader.load_rules(rule_set) → 리그별 Rules 인스턴스
        2. 12종 ViolationRule + 11종 FoulRule 수집
        3. DecisionEngine(ConfidenceScorer + MultiAngleValidator + ...) 초기화
        4. evaluate(context) → 전 규칙 check() → DecisionEngine.process_results()

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: RefereeConfig
    - ai_referee/rules/base_rule.py: BaseRule, FrameContext, RuleResult
    - ai_referee/rules/rule_loader.py: RuleLoader
    - ai_referee/violations/: 12종 바이올레이션 감지기
    - ai_referee/fouls/: 11종 파울 감지기 + ContactDetector
    - ai_referee/decisions/: DecisionEngine, ConfidenceScorer, MultiAngleValidator,
                             ConsistencyTracker, ReplayManager, DecisionExplainer

소비자:
    - engine/pipeline/event_pipeline.py: 심판 콜백으로 등록
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import RefereeConfig

# 규칙 기반 + 로더
from ai_referee.rules.base_rule import BaseRule, FrameContext, RuleResult
from ai_referee.rules.rule_loader import RuleLoader

# 12종 바이올레이션 감지기
from ai_referee.violations import (
    BackcourtDetector,
    CarryDetector,
    DefensiveThreeSecDetector,
    DoubleDribbleDetector,
    EightSecondDetector,
    FiveSecondDetector,
    GoaltendingDetector,
    KickBallDetector,
    OutOfBoundsDetector,
    ThreeSecondDetector,
    TravelingDetector,
    TwentyFourSecondDetector,
)

# 11종 파울 감지기
from ai_referee.fouls import (
    BlockingFoulDetector,
    ChargingFoulDetector,
    ContactDetector,
    FlagrantDetector,
    FoulSeverityAnalyzer,
    HandCheckDetector,
    HoldingFoulDetector,
    IllegalScreenDetector,
    ReachInDetector,
    ShootingFoulClassifier,
    TechnicalViolationDetector,
)

# 판정 엔진 6모듈
from ai_referee.decisions import (
    ConfidenceScorer,
    ConsistencyTracker,
    DecisionEngine,
    DecisionExplainer,
    FinalDecision,
    MultiAngleValidator,
    ReplayManager,
)

_logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_DECISION_HISTORY: Final[int] = 500


# =============================================================================
# 판정 결과
# =============================================================================
@dataclass(slots=True)
class RefereeResult:
    """
    1프레임 AI 심판 판정 결과.

    Attributes:
        frame_index: 프레임 인덱스
        rule_results: 위반 감지된 규칙 결과 목록
        violations_found: 바이올레이션 감지 수
        fouls_found: 파울 감지 수
        final_decisions: 최종 판정 목록 (DecisionEngine 출력)
        processing_time_ms: 처리 시간 (ms)
    """

    frame_index: int = 0
    rule_results: list[RuleResult] = field(default_factory=list)
    violations_found: int = 0
    fouls_found: int = 0
    final_decisions: list[FinalDecision] = field(default_factory=list)
    processing_time_ms: float = 0.0


# =============================================================================
# AI 심판 오케스트레이터
# =============================================================================
class RefereeOrchestrator:
    """
    AI 심판 통합 판정 오케스트레이터.

    initialize()에서 RuleLoader로 리그별 규칙을 로딩하고,
    evaluate()에서 전 규칙의 check()를 호출한 뒤 DecisionEngine에 위임합니다.
    """

    __slots__ = (
        "_config",
        "_rule_loader",
        "_all_rules",
        "_decision_engine",
        "_history",
        "_total_evaluations",
        "_total_violations",
        "_total_fouls",
        "_initialized",
        "_lock",
    )

    def __init__(self, config: RefereeConfig | None = None) -> None:
        self._config = config or RefereeConfig()
        self._rule_loader: RuleLoader | None = None
        self._all_rules: list[BaseRule] = []
        self._decision_engine: DecisionEngine | None = None
        self._history: list[RefereeResult] = []
        self._total_evaluations: int = 0
        self._total_violations: int = 0
        self._total_fouls: int = 0
        self._initialized: bool = False
        self._lock: RLock = RLock()

    # =========================================================================
    # 초기화
    # =========================================================================
    def initialize(self) -> None:
        """
        AI 심판 시스템 초기화.

        1. RuleLoader로 리그별 규칙 세트 로딩
        2. BaseRule 인스턴스 수집
        3. DecisionEngine 초기화
        """
        with self._lock:
            if self._initialized:
                return

            rule_set = self._config.rule_set

            # 1. 규칙 로더
            self._rule_loader = RuleLoader()

            # 2. 리그별 규칙 세트 로딩
            try:
                league_rules = self._rule_loader.load_rules(rule_set)
                _logger.info(
                    "규칙 세트 로딩: %s (%s)",
                    rule_set.value, type(league_rules).__name__,
                )
            except Exception:
                _logger.exception("규칙 로딩 실패: %s", rule_set.value)
                return

            # 3. BaseRule 인스턴스 수집
            self._collect_rules(league_rules)

            # 4. DecisionEngine 초기화
            self._decision_engine = DecisionEngine(
                rule_set=rule_set,
                confidence_scorer=ConfidenceScorer(rule_set=rule_set),
                multi_angle_validator=MultiAngleValidator(rule_set=rule_set),
                consistency_tracker=ConsistencyTracker(rule_set=rule_set),
                decision_explainer=DecisionExplainer(rule_set=rule_set),
                replay_manager=ReplayManager(rule_set=rule_set),
            )

            self._initialized = True
            _logger.info(
                "AI 심판 초기화 완료: %d 규칙 로드", len(self._all_rules),
            )

    def _collect_rules(self, league_rules: object) -> None:
        """리그 규칙 세트 기반으로 ViolationRule/FoulRule 인스턴스 수집."""
        rule_set = self._config.rule_set

        # 1. league_rules 속성 중 BaseRule 인스턴스 수집 (이미 있으면)
        for attr_name in dir(league_rules):
            if attr_name.startswith("_"):
                continue
            attr = getattr(league_rules, attr_name, None)
            if isinstance(attr, BaseRule):
                self._all_rules.append(attr)

        # 2. 리그 규칙 세트 없으면 12종 violation + 11종 foul 직접 인스턴스화
        if not self._all_rules:
            self._all_rules = self._instantiate_all_rules(rule_set)

        _logger.info(
            "규칙 수집 완료: %d종 (violations + fouls)", len(self._all_rules),
        )

    @staticmethod
    def _instantiate_all_rules(rule_set: object) -> list[BaseRule]:
        """12종 ViolationRule + 11종 FoulRule 인스턴스 생성."""
        import importlib

        rules: list[BaseRule] = []

        # 12종 ViolationRule
        _VIOLATION_MODULES = [
            ("ai_referee.violations.traveling_detector", "TravelingDetector"),
            ("ai_referee.violations.double_dribble_detector", "DoubleDribbleDetector"),
            ("ai_referee.violations.carry_detector", "CarryDetector"),
            ("ai_referee.violations.kick_ball_detector", "KickBallDetector"),
            ("ai_referee.violations.three_second_detector", "ThreeSecondDetector"),
            ("ai_referee.violations.defensive_three_sec_detector", "DefensiveThreeSecDetector"),
            ("ai_referee.violations.five_second_detector", "FiveSecondDetector"),
            ("ai_referee.violations.eight_second_detector", "EightSecondDetector"),
            ("ai_referee.violations.backcourt_detector", "BackcourtDetector"),
            ("ai_referee.violations.out_of_bounds_detector", "OutOfBoundsDetector"),
            ("ai_referee.violations.goaltending_detector", "GoaltendingDetector"),
            ("ai_referee.violations.twenty_four_second_detector", "TwentyFourSecondDetector"),
        ]

        # 11종 FoulRule
        _FOUL_MODULES = [
            ("ai_referee.fouls.contact_detector", "ContactDetector"),
            ("ai_referee.fouls.blocking_foul_detector", "BlockingFoulDetector"),
            ("ai_referee.fouls.charging_foul_detector", "ChargingFoulDetector"),
            ("ai_referee.fouls.hand_check_detector", "HandCheckDetector"),
            ("ai_referee.fouls.holding_foul_detector", "HoldingFoulDetector"),
            ("ai_referee.fouls.illegal_screen_detector", "IllegalScreenDetector"),
            ("ai_referee.fouls.reach_in_detector", "ReachInDetector"),
            ("ai_referee.fouls.foul_severity_analyzer", "FoulSeverityAnalyzer"),
            ("ai_referee.fouls.flagrant_detector", "FlagrantDetector"),
            ("ai_referee.fouls.shooting_foul_classifier", "ShootingFoulClassifier"),
            ("ai_referee.fouls.technical_violation_detector", "TechnicalViolationDetector"),
        ]

        for module_path, class_name in _VIOLATION_MODULES + _FOUL_MODULES:
            try:
                mod = importlib.import_module(module_path)
                cls_obj = getattr(mod, class_name)
                instance = cls_obj(rule_set=rule_set)
                rules.append(instance)
            except Exception:
                _logger.debug("규칙 생성 스킵: %s.%s", module_path, class_name)

        return rules

    def shutdown(self) -> None:
        """AI 심판 종료."""
        with self._lock:
            self._all_rules.clear()
            self._decision_engine = None
            self._initialized = False
            _logger.info("AI 심판 종료")

    # =========================================================================
    # 판정 실행
    # =========================================================================
    def evaluate(self, context: FrameContext) -> RefereeResult:
        """
        1프레임 AI 심판 판정.

        Args:
            context: 프레임 컨텍스트 (선수 위치, 공, 키포인트 등)

        Returns:
            RefereeResult
        """
        if not self._initialized:
            return RefereeResult()

        t0 = time.perf_counter()
        violated_results: list[RuleResult] = []
        violations = 0
        fouls = 0

        # 1. 전 규칙 평가
        for rule in self._all_rules:
            try:
                result = rule.check(context)
                if result.violated and result.confidence >= self._config.min_confidence:
                    violated_results.append(result)
                    if hasattr(result, "violation_type") and result.violation_type:
                        violations += 1
                    if hasattr(result, "foul_type") and result.foul_type:
                        fouls += 1
            except Exception:
                _logger.exception("규칙 평가 오류: %s", type(rule).__name__)

        # 2. DecisionEngine 위임
        final_decisions: list[FinalDecision] = []
        if self._decision_engine is not None and violated_results:
            try:
                final_decisions = self._decision_engine.process_results(
                    violated_results, context,
                )
            except Exception:
                _logger.exception("DecisionEngine 처리 오류")

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        result = RefereeResult(
            frame_index=getattr(context, "frame_index", 0),
            rule_results=violated_results,
            violations_found=violations,
            fouls_found=fouls,
            final_decisions=final_decisions,
            processing_time_ms=elapsed_ms,
        )

        with self._lock:
            self._total_evaluations += 1
            self._total_violations += violations
            self._total_fouls += fouls
            self._history.append(result)
            if len(self._history) > _MAX_DECISION_HISTORY:
                self._history = self._history[-_MAX_DECISION_HISTORY:]

        return result

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def total_evaluations(self) -> int:
        """총 평가 횟수."""
        return self._total_evaluations

    @property
    def total_violations(self) -> int:
        """총 바이올레이션 수."""
        return self._total_violations

    @property
    def total_fouls(self) -> int:
        """총 파울 수."""
        return self._total_fouls

    @property
    def num_rules(self) -> int:
        """등록된 규칙 수."""
        return len(self._all_rules)

    def reset(self) -> None:
        """이력 초기화 (규칙/엔진 유지)."""
        with self._lock:
            self._history.clear()
            self._total_evaluations = 0
            self._total_violations = 0
            self._total_fouls = 0

    def __repr__(self) -> str:
        return (
            f"RefereeOrchestrator("
            f"rules={self.num_rules}, "
            f"evals={self._total_evaluations}, "
            f"initialized={self._initialized})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "RefereeResult",
    "RefereeOrchestrator",
]

__version__ = "1.0.0"
