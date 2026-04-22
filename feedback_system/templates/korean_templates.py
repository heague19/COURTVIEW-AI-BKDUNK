# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: korean_templates.py
설명: 한국어 피드백 템플릿 오케스트레이터 (Phase 15 H6 분할 후).

      분할된 데이터/엔진 모듈을 통합하여 기존 공개 API를 보존합니다:
      - TemplateEntry, DeviationExpression (from _types)
      - KoreanTemplates (이 파일)
      - TemplateVariationEngine (from variation_engine)
      - 편차 조회 함수 (from deviation_expressions)

      원본 1,630줄 → 오케스트레이터 ~230줄로 축소.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 2.0.0
"""

from __future__ import annotations

from threading import RLock

from shared.constants.feedback_constants import FeedbackSeverity
from shared.constants.player_constants import AgeGroup

# === 공유 dataclass ===
from feedback_system.templates._types import DeviationExpression, TemplateEntry

# === 분할된 데이터 모듈 ===
from feedback_system.templates._form_data import DRIBBLE_TEMPLATES, SHOOTING_TEMPLATES
from feedback_system.templates._pattern_data import (
    COMPARISON_PATTERN_TEMPLATES,
    COMPARISON_TEMPLATES,
    REFEREE_PATTERN_TEMPLATES,
    SCORE_PATTERN_TEMPLATES,
    TACTICAL_PATTERN_TEMPLATES,
    TRAINING_TEMPLATES,
    TREND_PATTERN_TEMPLATES,
    YOUTH_STRIP_PATTERN,
    YOUTH_TERM_SIMPLIFICATIONS,
)

# === 분할된 엔진/함수 모듈 (공개 API 재노출용) ===
from feedback_system.templates.deviation_expressions import (
    get_angle_deviation_text,
    get_balance_deviation_text,
    get_coach_ending,
    get_landing_text,
    get_speed_deviation_text,
)
from feedback_system.templates.variation_engine import TemplateVariationEngine


# =============================================================================
# KoreanTemplates 클래스
# =============================================================================
class KoreanTemplates:
    """
    한국어 피드백 템플릿 제공자.

    슈팅/드리블 폼, 따라하기 비교, 경기/전술/심판 패턴 피드백의
    한국어 텍스트를 중앙 관리합니다.
    """

    __slots__ = ("_lock", "_total_lookups")

    def __init__(self) -> None:
        self._lock: RLock = RLock()
        self._total_lookups: int = 0

    # -------------------------------------------------------------------------
    # 공개 속성
    # -------------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "KoreanTemplates"

    @property
    def total_lookups(self) -> int:
        return self._total_lookups

    # -------------------------------------------------------------------------
    # 슈팅 템플릿 조회
    # -------------------------------------------------------------------------
    def get_shooting_template(
        self,
        phase_key: str,
        point_key: str,
    ) -> TemplateEntry | None:
        """슈팅 폼 피드백 템플릿 조회."""
        phase = SHOOTING_TEMPLATES.get(phase_key)
        if phase is None:
            return None
        entry = phase.get(point_key)
        if entry is not None:
            with self._lock:
                self._total_lookups += 1
        return entry

    # -------------------------------------------------------------------------
    # 드리블 템플릿 조회
    # -------------------------------------------------------------------------
    def get_dribble_template(
        self,
        phase_key: str,
        point_key: str,
    ) -> TemplateEntry | None:
        """드리블 폼 피드백 템플릿 조회."""
        phase = DRIBBLE_TEMPLATES.get(phase_key)
        if phase is None:
            return None
        entry = phase.get(point_key)
        if entry is not None:
            with self._lock:
                self._total_lookups += 1
        return entry

    # -------------------------------------------------------------------------
    # 비교 템플릿 조회
    # -------------------------------------------------------------------------
    def get_comparison_template(self, template_key: str) -> TemplateEntry | None:
        """따라하기 비교 피드백 템플릿 조회."""
        entry = COMPARISON_TEMPLATES.get(template_key)
        if entry is not None:
            with self._lock:
                self._total_lookups += 1
        return entry

    # -------------------------------------------------------------------------
    # 훈련 추천 템플릿 조회
    # -------------------------------------------------------------------------
    def get_training_template(self, template_key: str) -> TemplateEntry | None:
        """훈련 추천 피드백 템플릿 조회."""
        entry = TRAINING_TEMPLATES.get(template_key)
        if entry is not None:
            with self._lock:
                self._total_lookups += 1
        return entry

    # -------------------------------------------------------------------------
    # 패턴 템플릿 포맷팅
    # -------------------------------------------------------------------------
    @staticmethod
    def format_score_pattern(severity: FeedbackSeverity, **kwargs: object) -> str:
        """점수 기반 패턴 피드백 문장 생성."""
        return _safe_format_pattern(SCORE_PATTERN_TEMPLATES, severity.value, **kwargs)

    @staticmethod
    def format_comparison_pattern(pattern_key: str, **kwargs: object) -> str:
        """비교 패턴 피드백 문장 생성 (리그 평균 대비 등)."""
        return _safe_format_pattern(COMPARISON_PATTERN_TEMPLATES, pattern_key, **kwargs)

    @staticmethod
    def format_trend_pattern(trend_key: str, **kwargs: object) -> str:
        """추세 패턴 피드백 문장 생성."""
        return _safe_format_pattern(TREND_PATTERN_TEMPLATES, trend_key, **kwargs)

    @staticmethod
    def format_tactical_pattern(pattern_key: str, **kwargs: object) -> str:
        """전술 패턴 피드백 문장 생성."""
        return _safe_format_pattern(TACTICAL_PATTERN_TEMPLATES, pattern_key, **kwargs)

    @staticmethod
    def format_referee_pattern(pattern_key: str, **kwargs: object) -> str:
        """심판 패턴 피드백 문장 생성."""
        return _safe_format_pattern(REFEREE_PATTERN_TEMPLATES, pattern_key, **kwargs)

    # -------------------------------------------------------------------------
    # 피드백 텍스트 조합 (핵심 메서드)
    # -------------------------------------------------------------------------
    def resolve_feedback_text(
        self,
        template: TemplateEntry,
        severity: FeedbackSeverity,
        age_group: AgeGroup | str = AgeGroup.ADULT,
        **format_kwargs: object,
    ) -> tuple[str, str, str | None]:
        """
        템플릿 + 심각도 + 연령대 → 최종 피드백 텍스트 조합.

        Returns:
            (제목, 설명, 개선 제안 또는 None)
            - 긍정 피드백이면 suggestion은 None
        """
        title = self._safe_format(template.title, **format_kwargs)
        is_positive = severity.is_positive

        if is_positive:
            description = self._safe_format(template.positive, **format_kwargs)
            suggestion = None
        else:
            description = self._safe_format(template.correction, **format_kwargs)
            suggestion = self._safe_format(template.suggestion, **format_kwargs)

        if age_group == "youth":
            title = self._simplify_for_youth(title)
            description = self._simplify_for_youth(description)
            if suggestion is not None:
                suggestion = self._simplify_for_youth(suggestion)

        with self._lock:
            self._total_lookups += 1

        return title, description, suggestion

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        """조회 카운터 초기화."""
        with self._lock:
            self._total_lookups = 0

    def __repr__(self) -> str:
        return f"KoreanTemplates(lookups={self._total_lookups})"

    # -------------------------------------------------------------------------
    # 내부: 안전한 문자열 포맷팅
    # -------------------------------------------------------------------------
    @staticmethod
    def _safe_format(template_str: str, **kwargs: object) -> str:
        """누락된 키가 있어도 원본 플레이스홀더를 유지."""
        try:
            return template_str.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return template_str

    # -------------------------------------------------------------------------
    # 내부: 유소년용 텍스트 간소화
    # -------------------------------------------------------------------------
    @staticmethod
    def _simplify_for_youth(text: str) -> str:
        """
        유소년 (U-12) 대상 텍스트 간소화.

        1. 괄호 안 세부 설명 제거
        2. 전문 용어 → 쉬운 표현 치환
        """
        simplified = YOUTH_STRIP_PATTERN.sub(" ", text).strip()
        for term, replacement in YOUTH_TERM_SIMPLIFICATIONS.items():
            simplified = simplified.replace(term, replacement)
        return simplified

    # -------------------------------------------------------------------------
    # 정적: 가용 템플릿 키 목록 (테스트/검증용)
    # -------------------------------------------------------------------------
    @staticmethod
    def get_shooting_phase_keys() -> tuple[str, ...]:
        """슈팅 단계 키 목록."""
        return tuple(SHOOTING_TEMPLATES.keys())

    @staticmethod
    def get_dribble_phase_keys() -> tuple[str, ...]:
        """드리블 단계 키 목록."""
        return tuple(DRIBBLE_TEMPLATES.keys())

    @staticmethod
    def get_shooting_point_keys(phase_key: str) -> tuple[str, ...]:
        """특정 슈팅 단계의 피드백 포인트 키 목록."""
        phase = SHOOTING_TEMPLATES.get(phase_key, {})
        return tuple(phase.keys())

    @staticmethod
    def get_dribble_point_keys(phase_key: str) -> tuple[str, ...]:
        """특정 드리블 단계의 피드백 포인트 키 목록."""
        phase = DRIBBLE_TEMPLATES.get(phase_key, {})
        return tuple(phase.keys())

    @staticmethod
    def get_comparison_keys() -> tuple[str, ...]:
        """비교 템플릿 키 목록."""
        return tuple(COMPARISON_TEMPLATES.keys())

    @staticmethod
    def get_training_keys() -> tuple[str, ...]:
        """훈련 추천 템플릿 키 목록."""
        return tuple(TRAINING_TEMPLATES.keys())


# =============================================================================
# 내부 헬퍼
# =============================================================================
def _safe_format_pattern(
    pattern_map: dict[str, str],
    key: str,
    **kwargs: object,
) -> str:
    """패턴 맵에서 템플릿 조회 후 안전하게 포맷팅."""
    template = pattern_map.get(key, "")
    if not template:
        return ""
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError, IndexError):
        return template


# =============================================================================
# 모듈 Export (기존 API 보존)
# =============================================================================
__all__ = [
    "KoreanTemplates",
    "TemplateEntry",
    # === 편차 기반 자연어 표현 ===
    "DeviationExpression",
    "get_angle_deviation_text",
    "get_speed_deviation_text",
    "get_balance_deviation_text",
    "get_landing_text",
    "get_coach_ending",
    # === 피드백 변형 엔진 ===
    "TemplateVariationEngine",
]

__version__ = "2.0.0"
