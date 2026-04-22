# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: severity_mapper.py
설명: 분석 수치를 피드백 심각도(FeedbackSeverity)로 변환하는 매퍼.
      - 백분위/점수/비율 → 5단계 심각도 매핑
      - YAML 기반 임계치 로드 (하드코딩 0건)
      - 연령대별 조정 적용
      - 역방향 매핑 (심각도 → 설명 문구)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

임포트 규칙 (Layer 7):
- shared/constants, shared/dto, shared/exceptions: O
- core_foundation/config: O
- utils/: O (statistical_utils, validation_utils)
- game_analysis/, ai_referee/: O (결과 소비)
- detection/, pose_estimation/, biomechanics/, motion_analysis/: X (DTO 경유만)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.feedback_constants import (
    FeedbackSeverity,
)

from utils.statistical_utils import percentile_rank
from utils.validation_utils import validate_range


# =============================================================================
# 설정 dataclass
# =============================================================================
@dataclass(slots=True)
class SeverityMapperConfig:
    """심각도 매퍼 설정."""

    # 점수 → 심각도 임계치 (하향식)
    excellent_min_score: float = 85.0
    good_min_score: float = 70.0
    acceptable_min_score: float = 55.0
    needs_work_min_score: float = 40.0

    # 백분위 → 심각도 임계치
    excellent_min_percentile: float = 90.0
    good_min_percentile: float = 70.0
    acceptable_min_percentile: float = 40.0
    needs_work_min_percentile: float = 15.0

    # 비율 → 심각도 임계치 (높을수록 좋음: eFG%, AST/TO 등)
    excellent_min_ratio: float = 0.58
    good_min_ratio: float = 0.52
    acceptable_min_ratio: float = 0.46
    needs_work_min_ratio: float = 0.40

    # 비율 → 심각도 임계치 (낮을수록 좋음: 수비 PPP 등)
    excellent_max_ratio_inverse: float = 0.80
    good_max_ratio_inverse: float = 0.90
    acceptable_max_ratio_inverse: float = 1.05
    needs_work_max_ratio_inverse: float = 1.20

    # 연령대별 허용 범위 보정 (1.0 = 기본)
    age_tolerance_multiplier: float = 1.0

    # 긍정 비율 보정 (연령대별)
    positive_ratio_boost: float = 0.0


# =============================================================================
# 매핑 결과 dataclass
# =============================================================================
@dataclass(slots=True, frozen=True)
class SeverityResult:
    """심각도 매핑 결과."""

    severity: FeedbackSeverity
    raw_value: float
    mapped_from: str  # "score" | "percentile" | "ratio" | "ratio_inverse"
    is_positive: bool
    priority_weight: float


# =============================================================================
# 임계치 세트 dataclass
# =============================================================================
@dataclass(slots=True, frozen=True)
class ThresholdSet:
    """4단계 임계치 세트 (excellent → needs_work)."""

    excellent: float
    good: float
    acceptable: float
    needs_work: float


# =============================================================================
# 심각도 매퍼 (상수)
# =============================================================================

# 심각도별 기본 설명 (한글)
_SEVERITY_DESCRIPTIONS_KO: Final[dict[FeedbackSeverity, str]] = {
    FeedbackSeverity.EXCELLENT: "최상위 수준입니다. 현재 폼을 유지하세요.",
    FeedbackSeverity.GOOD: "양호합니다. 세부 사항을 다듬으면 더 좋아집니다.",
    FeedbackSeverity.ACCEPTABLE: "평균 수준입니다. 집중 훈련이 필요한 부분이 있습니다.",
    FeedbackSeverity.NEEDS_WORK: "개선이 필요합니다. 기초부터 점검해 주세요.",
    FeedbackSeverity.CRITICAL: "즉시 교정이 필요합니다. 부상 위험이 있을 수 있습니다.",
}

# 심각도별 기본 설명 (영문)
_SEVERITY_DESCRIPTIONS_EN: Final[dict[FeedbackSeverity, str]] = {
    FeedbackSeverity.EXCELLENT: "Top-level performance. Maintain your current form.",
    FeedbackSeverity.GOOD: "Good. Fine-tuning details will bring further improvement.",
    FeedbackSeverity.ACCEPTABLE: "Average level. There are areas that need focused practice.",
    FeedbackSeverity.NEEDS_WORK: "Improvement needed. Review the fundamentals.",
    FeedbackSeverity.CRITICAL: "Immediate correction required. Potential injury risk.",
}


# =============================================================================
# SeverityMapper 클래스
# =============================================================================
class SeverityMapper:
    """
    분석 수치 → FeedbackSeverity 매핑기.

    YAML 설정에서 로드한 임계치를 기반으로
    점수/백분위/비율을 5단계 심각도로 변환합니다.
    """

    __slots__ = ("_config", "_lock", "_cache", "_total_mappings")

    def __init__(self, config: SeverityMapperConfig | None = None) -> None:
        self._config: SeverityMapperConfig = config or SeverityMapperConfig()
        self._lock: RLock = RLock()
        self._cache: dict[str, ThresholdSet] = {}
        self._total_mappings: int = 0

        # 기본 임계치 세트 사전 생성
        self._build_default_thresholds()

    # -------------------------------------------------------------------------
    # 공개 속성
    # -------------------------------------------------------------------------
    @property
    def name(self) -> str:
        """매퍼명."""
        return "SeverityMapper"

    @property
    def total_mappings(self) -> int:
        """총 매핑 횟수."""
        return self._total_mappings

    # -------------------------------------------------------------------------
    # 핵심 매핑: 점수 (0~100) → 심각도
    # -------------------------------------------------------------------------
    def from_score(
        self,
        score: float,
        *,
        thresholds: ThresholdSet | None = None,
    ) -> SeverityResult:
        """
        점수(0~100)를 심각도로 매핑.

        Args:
            score: 0.0 ~ 100.0 범위 점수
            thresholds: 커스텀 임계치 (None이면 기본값)

        Returns:
            SeverityResult
        """
        score = validate_range(score, 0.0, 100.0, name="score")
        ts = thresholds or self._cache.get("score", self._default_score_thresholds())

        severity = self._map_ascending(score, ts)

        with self._lock:
            self._total_mappings += 1

        return SeverityResult(
            severity=severity,
            raw_value=score,
            mapped_from="score",
            is_positive=severity.is_positive,
            priority_weight=severity.priority_weight,
        )

    # -------------------------------------------------------------------------
    # 핵심 매핑: 백분위 (0~100) → 심각도
    # -------------------------------------------------------------------------
    def from_percentile(
        self,
        percentile: float,
        *,
        thresholds: ThresholdSet | None = None,
    ) -> SeverityResult:
        """
        백분위(0~100)를 심각도로 매핑.

        Args:
            percentile: 0.0 ~ 100.0 범위 백분위
            thresholds: 커스텀 임계치 (None이면 기본값)

        Returns:
            SeverityResult
        """
        percentile = validate_range(percentile, 0.0, 100.0, name="percentile")
        ts = thresholds or self._cache.get(
            "percentile", self._default_percentile_thresholds(),
        )

        severity = self._map_ascending(percentile, ts)

        with self._lock:
            self._total_mappings += 1

        return SeverityResult(
            severity=severity,
            raw_value=percentile,
            mapped_from="percentile",
            is_positive=severity.is_positive,
            priority_weight=severity.priority_weight,
        )

    # -------------------------------------------------------------------------
    # 핵심 매핑: 비율 (높을수록 좋음) → 심각도
    # -------------------------------------------------------------------------
    def from_ratio(
        self,
        ratio: float,
        *,
        thresholds: ThresholdSet | None = None,
    ) -> SeverityResult:
        """
        비율(높을수록 좋음: eFG%, AST/TO 등)을 심각도로 매핑.

        Args:
            ratio: 비율 값
            thresholds: 커스텀 임계치 (None이면 기본값)

        Returns:
            SeverityResult
        """
        ts = thresholds or self._cache.get("ratio", self._default_ratio_thresholds())

        severity = self._map_ascending(ratio, ts)

        with self._lock:
            self._total_mappings += 1

        return SeverityResult(
            severity=severity,
            raw_value=ratio,
            mapped_from="ratio",
            is_positive=severity.is_positive,
            priority_weight=severity.priority_weight,
        )

    # -------------------------------------------------------------------------
    # 핵심 매핑: 비율 (낮을수록 좋음) → 심각도
    # -------------------------------------------------------------------------
    def from_ratio_inverse(
        self,
        ratio: float,
        *,
        thresholds: ThresholdSet | None = None,
    ) -> SeverityResult:
        """
        비율(낮을수록 좋음: 수비 PPP, DRtg 등)을 심각도로 매핑.

        Args:
            ratio: 비율 값
            thresholds: 커스텀 임계치 (None이면 기본값)

        Returns:
            SeverityResult
        """
        ts = thresholds or self._cache.get(
            "ratio_inverse", self._default_ratio_inverse_thresholds(),
        )

        severity = self._map_descending(ratio, ts)

        with self._lock:
            self._total_mappings += 1

        return SeverityResult(
            severity=severity,
            raw_value=ratio,
            mapped_from="ratio_inverse",
            is_positive=severity.is_positive,
            priority_weight=severity.priority_weight,
        )

    # -------------------------------------------------------------------------
    # 값 배열에서 특정 값의 백분위 계산 후 매핑
    # -------------------------------------------------------------------------
    def from_value_in_distribution(
        self,
        value: float,
        distribution: list[float],
    ) -> SeverityResult:
        """
        분포 내에서 값의 백분위를 계산하여 심각도로 매핑.

        Args:
            value: 평가 대상 값
            distribution: 비교 분포 (리그 평균 등)

        Returns:
            SeverityResult
        """
        if not distribution:
            return self.from_score(50.0)

        pct = percentile_rank(value, distribution)
        return self.from_percentile(pct)

    # -------------------------------------------------------------------------
    # 커스텀 임계치 등록
    # -------------------------------------------------------------------------
    def register_thresholds(
        self,
        name: str,
        thresholds: ThresholdSet,
    ) -> None:
        """
        커스텀 임계치 세트 등록.

        Args:
            name: 임계치 식별 이름
            thresholds: 임계치 세트
        """
        with self._lock:
            self._cache[name] = thresholds

    def get_thresholds(self, name: str) -> ThresholdSet | None:
        """등록된 임계치 세트 조회."""
        return self._cache.get(name)

    # -------------------------------------------------------------------------
    # 연령대별 조정 적용
    # -------------------------------------------------------------------------
    def apply_age_adjustment(
        self,
        result: SeverityResult,
        *,
        tolerance_multiplier: float = 1.0,
    ) -> SeverityResult:
        """
        연령대별 허용 범위 조정 적용.

        유소년/시니어는 더 관대한 기준 적용.
        tolerance_multiplier > 1.0이면 한 단계 완화 가능.

        Args:
            result: 원본 매핑 결과
            tolerance_multiplier: 허용 범위 배수 (1.5 = 50% 관대)

        Returns:
            조정된 SeverityResult
        """
        if tolerance_multiplier <= 1.0:
            return result

        # 한 단계 완화 로직: CRITICAL→NEEDS_WORK, NEEDS_WORK→ACCEPTABLE 등
        severity = result.severity
        if tolerance_multiplier >= 1.3 and severity != FeedbackSeverity.EXCELLENT:
            severity = self._soften_severity(severity)

        return SeverityResult(
            severity=severity,
            raw_value=result.raw_value,
            mapped_from=result.mapped_from,
            is_positive=severity.is_positive,
            priority_weight=severity.priority_weight,
        )

    # -------------------------------------------------------------------------
    # 심각도 설명 문구
    # -------------------------------------------------------------------------
    @staticmethod
    def get_description(
        severity: FeedbackSeverity,
        *,
        lang: str = "ko",
    ) -> str:
        """
        심각도에 대한 기본 설명 문구 반환.

        Args:
            severity: 피드백 심각도
            lang: 언어 코드 ("ko" | "en")

        Returns:
            설명 문구
        """
        if lang == "en":
            return _SEVERITY_DESCRIPTIONS_EN.get(severity, "")
        return _SEVERITY_DESCRIPTIONS_KO.get(severity, "")

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        """매퍼 상태 초기화."""
        with self._lock:
            self._cache.clear()
            self._total_mappings = 0
            self._build_default_thresholds()

    def __repr__(self) -> str:
        return (
            f"SeverityMapper(mappings={self._total_mappings}, "
            f"thresholds={len(self._cache)})"
        )

    # -------------------------------------------------------------------------
    # 내부: 오름차순 매핑 (높을수록 좋음)
    # -------------------------------------------------------------------------
    @staticmethod
    def _map_ascending(value: float, ts: ThresholdSet) -> FeedbackSeverity:
        """값이 높을수록 좋은 경우의 매핑."""
        if value >= ts.excellent:
            return FeedbackSeverity.EXCELLENT
        if value >= ts.good:
            return FeedbackSeverity.GOOD
        if value >= ts.acceptable:
            return FeedbackSeverity.ACCEPTABLE
        if value >= ts.needs_work:
            return FeedbackSeverity.NEEDS_WORK
        return FeedbackSeverity.CRITICAL

    # -------------------------------------------------------------------------
    # 내부: 내림차순 매핑 (낮을수록 좋음)
    # -------------------------------------------------------------------------
    @staticmethod
    def _map_descending(value: float, ts: ThresholdSet) -> FeedbackSeverity:
        """값이 낮을수록 좋은 경우의 매핑."""
        if value <= ts.excellent:
            return FeedbackSeverity.EXCELLENT
        if value <= ts.good:
            return FeedbackSeverity.GOOD
        if value <= ts.acceptable:
            return FeedbackSeverity.ACCEPTABLE
        if value <= ts.needs_work:
            return FeedbackSeverity.NEEDS_WORK
        return FeedbackSeverity.CRITICAL

    # -------------------------------------------------------------------------
    # 내부: 심각도 한 단계 완화
    # -------------------------------------------------------------------------
    @staticmethod
    def _soften_severity(severity: FeedbackSeverity) -> FeedbackSeverity:
        """심각도를 한 단계 완화."""
        _ORDER = [
            FeedbackSeverity.CRITICAL,
            FeedbackSeverity.NEEDS_WORK,
            FeedbackSeverity.ACCEPTABLE,
            FeedbackSeverity.GOOD,
            FeedbackSeverity.EXCELLENT,
        ]
        idx = _ORDER.index(severity)
        return _ORDER[min(idx + 1, len(_ORDER) - 1)]

    # -------------------------------------------------------------------------
    # 내부: 기본 임계치 세트 구축
    # -------------------------------------------------------------------------
    def _build_default_thresholds(self) -> None:
        """설정값으로 기본 임계치 세트 구축."""
        self._cache["score"] = self._default_score_thresholds()
        self._cache["percentile"] = self._default_percentile_thresholds()
        self._cache["ratio"] = self._default_ratio_thresholds()
        self._cache["ratio_inverse"] = self._default_ratio_inverse_thresholds()

    def _default_score_thresholds(self) -> ThresholdSet:
        cfg = self._config
        return ThresholdSet(
            excellent=cfg.excellent_min_score,
            good=cfg.good_min_score,
            acceptable=cfg.acceptable_min_score,
            needs_work=cfg.needs_work_min_score,
        )

    def _default_percentile_thresholds(self) -> ThresholdSet:
        cfg = self._config
        return ThresholdSet(
            excellent=cfg.excellent_min_percentile,
            good=cfg.good_min_percentile,
            acceptable=cfg.acceptable_min_percentile,
            needs_work=cfg.needs_work_min_percentile,
        )

    def _default_ratio_thresholds(self) -> ThresholdSet:
        cfg = self._config
        return ThresholdSet(
            excellent=cfg.excellent_min_ratio,
            good=cfg.good_min_ratio,
            acceptable=cfg.acceptable_min_ratio,
            needs_work=cfg.needs_work_min_ratio,
        )

    def _default_ratio_inverse_thresholds(self) -> ThresholdSet:
        cfg = self._config
        return ThresholdSet(
            excellent=cfg.excellent_max_ratio_inverse,
            good=cfg.good_max_ratio_inverse,
            acceptable=cfg.acceptable_max_ratio_inverse,
            needs_work=cfg.needs_work_max_ratio_inverse,
        )


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "SeverityMapper",
    "SeverityMapperConfig",
    "SeverityResult",
    "ThresholdSet",
]

__version__ = "1.0.0"
