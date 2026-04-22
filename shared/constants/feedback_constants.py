# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: feedback_constants.py
설명: 피드백/리포트 시스템 도메인 상수 정의
      - 피드백 심각도 (5단계)
      - 피드백 카테고리 (8종)
      - 리포트 유형 (6종)
      - 리포트 출력 형식 (4종)
      - 피드백 우선순위 가중치
      - 리포트 섹션 구성
      - 시각 피드백 파라미터

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
- COURTVIEW 피드백 품질 기준 v1.0
- 스포츠 코칭 피드백 원칙 (Positive-Constructive 비율)

사용처:
- feedback_system/coach/: 동작 폼 코칭 + 생체역학 피드백
- feedback_system/analysis/: 경기/전술/수비/개인/공간/라인업/심판/시각/클러치/모멘텀 등 피드백
- feedback_system/templates/: 템플릿 선택, 포맷팅
- feedback_system/report/: 리포트 생성, 세션 요약, 성장 추세
- game_analysis/film_session/: 티칭 포인트 생성

사용 예시:
    >>> from shared.constants.feedback_constants import FeedbackSeverity
    >>> sev = FeedbackSeverity.GOOD
    >>> sev.is_positive
    True
    >>> sev.get_name(SupportedLanguage.EN)
    'Good'
"""

from __future__ import annotations


from enum import Enum, unique
from typing import Final

from shared.constants.localization import SupportedLanguage


# =============================================================================
# 피드백 심각도 열거형 (5단계)
# =============================================================================
@unique
class FeedbackSeverity(str, Enum):
    """
    피드백 심각도 열거형 (5단계).

    분석 결과를 코칭 피드백으로 변환할 때의 심각도/긴급도 수준.
    severity_mapper.py에서 통계 수치 → 심각도로 매핑합니다.
    """

    CRITICAL = "critical"       # 즉시 개선 필요 (부상 위험, 치명적 전술 실패)
    NEEDS_WORK = "needs_work"   # 개선 필요 (명확한 약점)
    ACCEPTABLE = "acceptable"   # 보통 (리그 평균 수준)
    GOOD = "good"               # 양호 (강점)
    EXCELLENT = "excellent"     # 우수 (최상위 수준)

    def __str__(self) -> str:
        return self.value

    @property
    def is_positive(self) -> bool:
        """긍정적 피드백 여부."""
        return self in (FeedbackSeverity.GOOD, FeedbackSeverity.EXCELLENT)

    @property
    def priority_weight(self) -> float:
        """피드백 우선순위 가중치 (높을수록 먼저 표시)."""
        return _SEVERITY_PRIORITY[self]

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 심각도명 반환."""
        return _SEVERITY_I18N[self].get(
            lang, _SEVERITY_I18N[self][SupportedLanguage.KO]
        )


_SEVERITY_PRIORITY: dict["FeedbackSeverity", float] = {
    FeedbackSeverity.CRITICAL: 1.0,
    FeedbackSeverity.NEEDS_WORK: 0.8,
    FeedbackSeverity.ACCEPTABLE: 0.4,
    FeedbackSeverity.GOOD: 0.3,
    FeedbackSeverity.EXCELLENT: 0.2,
}

_SEVERITY_I18N: dict[FeedbackSeverity, dict[SupportedLanguage, str]] = {
    FeedbackSeverity.CRITICAL: {
        SupportedLanguage.KO: "즉시 개선",
        SupportedLanguage.EN: "Critical",
        SupportedLanguage.JA: "要改善",
        SupportedLanguage.ZH: "急需改进",
        SupportedLanguage.ES: "Crítico",
    },
    FeedbackSeverity.NEEDS_WORK: {
        SupportedLanguage.KO: "개선 필요",
        SupportedLanguage.EN: "Needs Work",
        SupportedLanguage.JA: "改善必要",
        SupportedLanguage.ZH: "需要改进",
        SupportedLanguage.ES: "Necesita Mejora",
    },
    FeedbackSeverity.ACCEPTABLE: {
        SupportedLanguage.KO: "보통",
        SupportedLanguage.EN: "Acceptable",
        SupportedLanguage.JA: "普通",
        SupportedLanguage.ZH: "一般",
        SupportedLanguage.ES: "Aceptable",
    },
    FeedbackSeverity.GOOD: {
        SupportedLanguage.KO: "양호",
        SupportedLanguage.EN: "Good",
        SupportedLanguage.JA: "良好",
        SupportedLanguage.ZH: "良好",
        SupportedLanguage.ES: "Bueno",
    },
    FeedbackSeverity.EXCELLENT: {
        SupportedLanguage.KO: "우수",
        SupportedLanguage.EN: "Excellent",
        SupportedLanguage.JA: "優秀",
        SupportedLanguage.ZH: "优秀",
        SupportedLanguage.ES: "Excelente",
    },
}


# =============================================================================
# 피드백 카테고리 열거형 (8종)
# =============================================================================
@unique
class FeedbackCategory(str, Enum):
    """
    피드백 카테고리 열거형 (8종).

    피드백 생성기별 카테고리 매핑.
    """

    GAME_OVERALL = "game_overall"       # 경기 종합
    TACTICAL = "tactical"               # 공격 전술
    DEFENSIVE = "defensive"             # 수비 분석
    INDIVIDUAL = "individual"           # 개인 심층
    SPATIAL = "spatial"                 # 공간 분석
    LINEUP = "lineup"                   # 라인업 분석
    REFEREE = "referee"                 # AI 심판 판정
    VISUAL = "visual"                   # 시각 피드백

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 카테고리명 반환."""
        return _FEEDBACK_CAT_I18N[self].get(
            lang, _FEEDBACK_CAT_I18N[self][SupportedLanguage.KO]
        )


_FEEDBACK_CAT_I18N: dict[FeedbackCategory, dict[SupportedLanguage, str]] = {
    FeedbackCategory.GAME_OVERALL: {
        SupportedLanguage.KO: "경기 종합",
        SupportedLanguage.EN: "Game Overall",
        SupportedLanguage.JA: "試合総合",
        SupportedLanguage.ZH: "比赛综合",
        SupportedLanguage.ES: "Resumen del Partido",
    },
    FeedbackCategory.TACTICAL: {
        SupportedLanguage.KO: "공격 전술",
        SupportedLanguage.EN: "Offensive Tactics",
        SupportedLanguage.JA: "攻撃戦術",
        SupportedLanguage.ZH: "进攻战术",
        SupportedLanguage.ES: "Tácticas Ofensivas",
    },
    FeedbackCategory.DEFENSIVE: {
        SupportedLanguage.KO: "수비 분석",
        SupportedLanguage.EN: "Defensive Analysis",
        SupportedLanguage.JA: "守備分析",
        SupportedLanguage.ZH: "防守分析",
        SupportedLanguage.ES: "Análisis Defensivo",
    },
    FeedbackCategory.INDIVIDUAL: {
        SupportedLanguage.KO: "개인 심층",
        SupportedLanguage.EN: "Individual Analysis",
        SupportedLanguage.JA: "個人分析",
        SupportedLanguage.ZH: "个人分析",
        SupportedLanguage.ES: "Análisis Individual",
    },
    FeedbackCategory.SPATIAL: {
        SupportedLanguage.KO: "공간 분석",
        SupportedLanguage.EN: "Spatial Analysis",
        SupportedLanguage.JA: "空間分析",
        SupportedLanguage.ZH: "空间分析",
        SupportedLanguage.ES: "Análisis Espacial",
    },
    FeedbackCategory.LINEUP: {
        SupportedLanguage.KO: "라인업 분석",
        SupportedLanguage.EN: "Lineup Analysis",
        SupportedLanguage.JA: "ラインナップ分析",
        SupportedLanguage.ZH: "阵容分析",
        SupportedLanguage.ES: "Análisis de Alineación",
    },
    FeedbackCategory.REFEREE: {
        SupportedLanguage.KO: "심판 판정",
        SupportedLanguage.EN: "Referee Decisions",
        SupportedLanguage.JA: "審判判定",
        SupportedLanguage.ZH: "裁判判罚",
        SupportedLanguage.ES: "Decisiones Arbitrales",
    },
    FeedbackCategory.VISUAL: {
        SupportedLanguage.KO: "시각 피드백",
        SupportedLanguage.EN: "Visual Feedback",
        SupportedLanguage.JA: "ビジュアルフィードバック",
        SupportedLanguage.ZH: "视觉反馈",
        SupportedLanguage.ES: "Retroalimentación Visual",
    },
}


# =============================================================================
# 리포트 유형 열거형 (6종)
# =============================================================================
@unique
class ReportType(str, Enum):
    """
    리포트 유형 열거형 (6종).
    """

    SINGLE_GAME = "single_game"             # 단일 경기 리포트
    SESSION_SUMMARY = "session_summary"     # 세션(당일 복수 경기) 요약
    PLAYER_PROGRESS = "player_progress"     # 선수 성장 추세
    TEAM_TREND = "team_trend"               # 팀 시즌 추세
    SCOUTING = "scouting"                   # 스카우팅 리포트
    PRE_GAME_BRIEFING = "pre_game_briefing" # 경기 전 브리핑

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 리포트 유형명 반환."""
        return _REPORT_TYPE_I18N[self].get(
            lang, _REPORT_TYPE_I18N[self][SupportedLanguage.KO]
        )


_REPORT_TYPE_I18N: dict[ReportType, dict[SupportedLanguage, str]] = {
    ReportType.SINGLE_GAME: {
        SupportedLanguage.KO: "단일 경기 리포트",
        SupportedLanguage.EN: "Single Game Report",
        SupportedLanguage.JA: "単一試合レポート",
        SupportedLanguage.ZH: "单场比赛报告",
        SupportedLanguage.ES: "Informe de Partido",
    },
    ReportType.SESSION_SUMMARY: {
        SupportedLanguage.KO: "세션 요약",
        SupportedLanguage.EN: "Session Summary",
        SupportedLanguage.JA: "セッション要約",
        SupportedLanguage.ZH: "场次摘要",
        SupportedLanguage.ES: "Resumen de Sesión",
    },
    ReportType.PLAYER_PROGRESS: {
        SupportedLanguage.KO: "선수 성장 추세",
        SupportedLanguage.EN: "Player Progress",
        SupportedLanguage.JA: "選手成長推移",
        SupportedLanguage.ZH: "球员进步趋势",
        SupportedLanguage.ES: "Progreso del Jugador",
    },
    ReportType.TEAM_TREND: {
        SupportedLanguage.KO: "팀 시즌 추세",
        SupportedLanguage.EN: "Team Trend",
        SupportedLanguage.JA: "チームシーズン推移",
        SupportedLanguage.ZH: "球队趋势",
        SupportedLanguage.ES: "Tendencia del Equipo",
    },
    ReportType.SCOUTING: {
        SupportedLanguage.KO: "스카우팅 리포트",
        SupportedLanguage.EN: "Scouting Report",
        SupportedLanguage.JA: "スカウティングレポート",
        SupportedLanguage.ZH: "球探报告",
        SupportedLanguage.ES: "Informe de Scout",
    },
    ReportType.PRE_GAME_BRIEFING: {
        SupportedLanguage.KO: "경기 전 브리핑",
        SupportedLanguage.EN: "Pre-game Briefing",
        SupportedLanguage.JA: "試合前ブリーフィング",
        SupportedLanguage.ZH: "赛前简报",
        SupportedLanguage.ES: "Briefing Pre-partido",
    },
}


# =============================================================================
# 리포트 출력 형식 열거형 (4종)
# =============================================================================
@unique
class ReportOutputFormat(str, Enum):
    """리포트 출력 형식 열거형 (4종)."""

    HTML = "html"
    JSON = "json"
    PDF = "pdf"
    TEXT = "text"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 피드백 품질 파라미터
# =============================================================================

# 피드백당 최소 세부 동작 수 (CLAUDE.md #15: 최소 10개 이상)
FEEDBACK_MIN_DETAIL_POINTS: Final[int] = 10

# 긍정/건설적 피드백 비율 (Positive:Constructive)
# 코칭 과학 권장 비율 3:1 ~ 5:1 (긍정 3~5 : 건설적 1)
FEEDBACK_POSITIVE_RATIO_MIN: Final[float] = 0.60   # 긍정 최소 60%
FEEDBACK_POSITIVE_RATIO_MAX: Final[float] = 0.85   # 긍정 최대 85%

# 피드백 최대 길이 (문자 수)
FEEDBACK_MAX_LENGTH_CHARS: Final[int] = 2000

# 피드백 최소 길이 (문자 수)
FEEDBACK_MIN_LENGTH_CHARS: Final[int] = 100

# 피드백 카테고리별 우선순위 가중치
FEEDBACK_CATEGORY_PRIORITY: Final[dict[FeedbackCategory, float]] = {
    FeedbackCategory.GAME_OVERALL: 1.0,
    FeedbackCategory.TACTICAL: 0.9,
    FeedbackCategory.DEFENSIVE: 0.9,
    FeedbackCategory.INDIVIDUAL: 0.85,
    FeedbackCategory.SPATIAL: 0.7,
    FeedbackCategory.LINEUP: 0.75,
    FeedbackCategory.REFEREE: 0.6,
    FeedbackCategory.VISUAL: 0.5,
}


# =============================================================================
# 리포트 섹션 구성
# =============================================================================

# 단일 경기 리포트 기본 섹션 순서
SINGLE_GAME_REPORT_SECTIONS: Final[tuple[str, ...]] = (
    "game_summary",           # 경기 요약 (스코어, 주요 스탯)
    "team_comparison",        # 팀 비교 (기본/고급 스탯)
    "four_factors",           # Four Factors 분석
    "key_players",            # 핵심 선수 (MVP, 최고/최저 성과)
    "shot_chart",             # 슛 차트
    "play_type_breakdown",    # 플레이 유형별 분석
    "defensive_analysis",     # 수비 분석
    "game_flow",              # 경기 흐름 (모멘텀, 런)
    "lineup_analysis",        # 라인업 분석
    "coaching_points",        # 코칭 포인트 (개선/강점)
)

# 리포트 섹션당 최대 항목 수
REPORT_SECTION_MAX_ITEMS: Final[int] = 15

# 리포트 핵심 선수 표시 수
REPORT_KEY_PLAYERS_COUNT: Final[int] = 5

# 리포트 "Top N" 기본값
REPORT_TOP_N_DEFAULT: Final[int] = 5


# =============================================================================
# 시각 피드백 파라미터
# =============================================================================

# 히트맵 해상도 (격자 수, 하프코트 기준)
HEATMAP_GRID_X: Final[int] = 50
HEATMAP_GRID_Y: Final[int] = 47

# 코트 다이어그램 기본 해상도 (픽셀)
COURT_DIAGRAM_WIDTH_PX: Final[int] = 940
COURT_DIAGRAM_HEIGHT_PX: Final[int] = 500

# 슛 차트 마커 크기 (픽셀)
SHOT_CHART_MARKER_SIZE_MADE: Final[int] = 8
SHOT_CHART_MARKER_SIZE_MISSED: Final[int] = 6

# 시계열 차트 최소 데이터 포인트
TIME_SERIES_MIN_POINTS: Final[int] = 5

# 오버레이 투명도 (0.0~1.0)
OVERLAY_OPACITY_DEFAULT: Final[float] = 0.6
OVERLAY_OPACITY_HIGHLIGHT: Final[float] = 0.8

# 주석 화살표 두께 (픽셀)
ANNOTATION_ARROW_WIDTH_PX: Final[int] = 2

# 필름 세션 — 클립당 평균 리뷰 시간 추정 (초)
FILM_SESSION_AVG_CLIP_REVIEW_SEC: Final[int] = 45

# 필름 세션 — 최대 클립 수
FILM_SESSION_MAX_CLIPS: Final[int] = 50


# =============================================================================
# 성장 추세 분석 파라미터
# =============================================================================

# 성장 판정 최소 경기 수
GROWTH_MIN_GAMES: Final[int] = 5

# 성장 방향 판정 — 기울기 임계치
GROWTH_IMPROVING_SLOPE: Final[float] = 0.02
GROWTH_DECLINING_SLOPE: Final[float] = -0.02

# 반복 실수 패턴 감지 — 최소 연속 경기 수
REPEATED_MISTAKE_MIN_GAMES: Final[int] = 3

# 개선 우선순위 — "이번 주 Top N" 항목 수
IMPROVEMENT_PRIORITY_TOP_N: Final[int] = 5


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 열거형
    "FeedbackSeverity",
    "FeedbackCategory",
    "ReportType",
    "ReportOutputFormat",
    # 피드백 품질
    "FEEDBACK_MIN_DETAIL_POINTS",
    "FEEDBACK_POSITIVE_RATIO_MIN",
    "FEEDBACK_POSITIVE_RATIO_MAX",
    "FEEDBACK_MAX_LENGTH_CHARS",
    "FEEDBACK_MIN_LENGTH_CHARS",
    "FEEDBACK_CATEGORY_PRIORITY",
    # 리포트 섹션
    "SINGLE_GAME_REPORT_SECTIONS",
    "REPORT_SECTION_MAX_ITEMS",
    "REPORT_KEY_PLAYERS_COUNT",
    "REPORT_TOP_N_DEFAULT",
    # 시각 피드백
    "HEATMAP_GRID_X",
    "HEATMAP_GRID_Y",
    "COURT_DIAGRAM_WIDTH_PX",
    "COURT_DIAGRAM_HEIGHT_PX",
    "SHOT_CHART_MARKER_SIZE_MADE",
    "SHOT_CHART_MARKER_SIZE_MISSED",
    "TIME_SERIES_MIN_POINTS",
    "OVERLAY_OPACITY_DEFAULT",
    "OVERLAY_OPACITY_HIGHLIGHT",
    "ANNOTATION_ARROW_WIDTH_PX",
    # 필름 세션
    "FILM_SESSION_AVG_CLIP_REVIEW_SEC",
    "FILM_SESSION_MAX_CLIPS",
    # 성장 추세
    "GROWTH_MIN_GAMES",
    "GROWTH_IMPROVING_SLOPE",
    "GROWTH_DECLINING_SLOPE",
    "REPEATED_MISTAKE_MIN_GAMES",
    "IMPROVEMENT_PRIORITY_TOP_N",
]

# 모듈 버전 정보
__version__ = "1.0.0"
