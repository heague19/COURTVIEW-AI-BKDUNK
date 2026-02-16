# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_feedback_constants.py

피드백/리포트 시스템 도메인 상수 모듈 단위 테스트

검증 항목:
  [A] FeedbackSeverity 기본 (5 멤버, str 값, str Enum 상속)
  [B] FeedbackSeverity 프로퍼티 (is_positive, priority_weight)
  [C] FeedbackSeverity i18n (get_name, 5개 언어 x 5 멤버)
  [D] FeedbackCategory 기본 (8 멤버, str 값)
  [E] FeedbackCategory i18n (get_name, 5개 언어 x 8 멤버)
  [F] ReportType 기본 (6 멤버, str 값)
  [G] ReportType i18n (get_name, 5개 언어 x 6 멤버)
  [H] ReportOutputFormat 기본 (4 멤버, str 값)
  [I] 피드백 품질 파라미터 (Final 상수, 범위, 타입)
  [J] FEEDBACK_CATEGORY_PRIORITY (8 카테고리, 값 범위)
  [K] 리포트 섹션 구성 (SINGLE_GAME_REPORT_SECTIONS, 기타 상수)
  [L] 시각 피드백 파라미터 (히트맵, 코트, 슛차트, 오버레이)
  [M] 필름 세션 파라미터 (클립 리뷰, 최대 클립)
  [N] 성장 추세 파라미터 (기울기 임계치, 최소 경기 수)
  [O] get_feedback_severity_from_percentile 경계값
  [P] get_feedback_severity_from_percentile 극단값
  [Q] estimate_film_session_duration_min 기본 계산
  [R] estimate_film_session_duration_min 클립 제한
  [S] Enum identity / hashable / set 사용
  [T] __str__ mixin 검증 (문자열 비교)
  [U] __all__ Export 완전성

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from enum import Enum
from pathlib import Path

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (parents[4]: unit -> constants -> shared -> tests -> PROJECT_ROOT)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants.localization import SupportedLanguage
from shared.constants import feedback_constants as fc
from shared.constants.feedback_constants import (
    # 열거형 (4종)
    FeedbackSeverity,
    FeedbackCategory,
    ReportType,
    ReportOutputFormat,
    # 피드백 품질 상수
    FEEDBACK_MIN_DETAIL_POINTS,
    FEEDBACK_POSITIVE_RATIO_MIN,
    FEEDBACK_POSITIVE_RATIO_MAX,
    FEEDBACK_MAX_LENGTH_CHARS,
    FEEDBACK_MIN_LENGTH_CHARS,
    FEEDBACK_CATEGORY_PRIORITY,
    # 리포트 섹션 상수
    SINGLE_GAME_REPORT_SECTIONS,
    REPORT_SECTION_MAX_ITEMS,
    REPORT_KEY_PLAYERS_COUNT,
    REPORT_TOP_N_DEFAULT,
    # 시각 피드백 상수
    HEATMAP_GRID_X,
    HEATMAP_GRID_Y,
    COURT_DIAGRAM_WIDTH_PX,
    COURT_DIAGRAM_HEIGHT_PX,
    SHOT_CHART_MARKER_SIZE_MADE,
    SHOT_CHART_MARKER_SIZE_MISSED,
    TIME_SERIES_MIN_POINTS,
    OVERLAY_OPACITY_DEFAULT,
    OVERLAY_OPACITY_HIGHLIGHT,
    ANNOTATION_ARROW_WIDTH_PX,
    # 필름 세션 상수
    FILM_SESSION_AVG_CLIP_REVIEW_SEC,
    FILM_SESSION_MAX_CLIPS,
    # 성장 추세 상수
    GROWTH_MIN_GAMES,
    GROWTH_IMPROVING_SLOPE,
    GROWTH_DECLINING_SLOPE,
    REPEATED_MISTAKE_MIN_GAMES,
    IMPROVEMENT_PRIORITY_TOP_N,
    # 유틸리티 함수
    get_feedback_severity_from_percentile,
    estimate_film_session_duration_min,
)


# =============================================================================
# 테스트 결과 추적기
# =============================================================================
class TestResult:
    """테스트 결과 집계 및 출력 유틸리티."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, detail)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# =============================================================================
# [A] FeedbackSeverity 기본 (5 멤버, str 값)
# =============================================================================
def test_a_feedback_severity_basics(r: TestResult) -> None:
    """[A] FeedbackSeverity Enum 기본 속성 검증."""
    print("\n[A] FeedbackSeverity 기본 (5 멤버, str 값)")

    # 멤버 수 검증
    members = list(FeedbackSeverity)
    r.check("FeedbackSeverity 멤버 수 = 5", len(members) == 5, f"실제: {len(members)}")

    # 각 멤버의 이름-값 매핑 검증
    expected_members = {
        "CRITICAL": "critical",
        "NEEDS_WORK": "needs_work",
        "ACCEPTABLE": "acceptable",
        "GOOD": "good",
        "EXCELLENT": "excellent",
    }

    for name, value in expected_members.items():
        member = FeedbackSeverity[name]
        r.check(
            f"FeedbackSeverity.{name} == '{value}'",
            member.value == value,
            f"expected='{value}', actual='{member.value}'",
        )

    # str 상속 검증
    r.check("FeedbackSeverity는 str 상속",
            issubclass(FeedbackSeverity, str),
            f"MRO: {FeedbackSeverity.__mro__}")

    # Enum 상속 검증
    r.check("FeedbackSeverity는 Enum 상속",
            issubclass(FeedbackSeverity, Enum),
            f"MRO: {FeedbackSeverity.__mro__}")


# =============================================================================
# [B] FeedbackSeverity 프로퍼티 (is_positive, priority_weight)
# =============================================================================
def test_b_feedback_severity_properties(r: TestResult) -> None:
    """[B] FeedbackSeverity 프로퍼티 검증."""
    print("\n[B] FeedbackSeverity 프로퍼티 (is_positive, priority_weight)")

    # is_positive: GOOD, EXCELLENT만 True
    positive_expected = {FeedbackSeverity.GOOD, FeedbackSeverity.EXCELLENT}
    positive_actual = {m for m in FeedbackSeverity if m.is_positive}
    r.check("is_positive = {GOOD, EXCELLENT}",
            positive_actual == positive_expected,
            f"차이: {positive_actual.symmetric_difference(positive_expected)}")

    not_positive_expected = {FeedbackSeverity.CRITICAL, FeedbackSeverity.NEEDS_WORK, FeedbackSeverity.ACCEPTABLE}
    not_positive_actual = {m for m in FeedbackSeverity if not m.is_positive}
    r.check("is_positive=False = {CRITICAL, NEEDS_WORK, ACCEPTABLE}",
            not_positive_actual == not_positive_expected)

    # priority_weight: 모든 멤버 float, 0.0~1.0 범위
    for member in FeedbackSeverity:
        w = member.priority_weight
        r.check(f"{member.name}.priority_weight = {w} (float, 0~1)",
                isinstance(w, float) and 0.0 <= w <= 1.0,
                f"타입: {type(w)}, 값: {w}")

    # 구체적인 값 검증
    r.check("CRITICAL.priority_weight = 1.0",
            FeedbackSeverity.CRITICAL.priority_weight == 1.0)
    r.check("NEEDS_WORK.priority_weight = 0.8",
            FeedbackSeverity.NEEDS_WORK.priority_weight == 0.8)
    r.check("ACCEPTABLE.priority_weight = 0.4",
            FeedbackSeverity.ACCEPTABLE.priority_weight == 0.4)
    r.check("GOOD.priority_weight = 0.3",
            FeedbackSeverity.GOOD.priority_weight == 0.3)
    r.check("EXCELLENT.priority_weight = 0.2",
            FeedbackSeverity.EXCELLENT.priority_weight == 0.2)

    # 단조 감소 검증 (CRITICAL > NEEDS_WORK > ACCEPTABLE > GOOD > EXCELLENT)
    weights = [m.priority_weight for m in FeedbackSeverity]
    monotonic = all(weights[i] > weights[i + 1] for i in range(len(weights) - 1))
    r.check("priority_weight 단조 감소 (심각→우수)", monotonic, f"순서: {weights}")


# =============================================================================
# [C] FeedbackSeverity i18n (get_name)
# =============================================================================
def test_c_feedback_severity_i18n(r: TestResult) -> None:
    """[C] FeedbackSeverity i18n 검증."""
    print("\n[C] FeedbackSeverity i18n (5개 언어 x 5 멤버 = 25)")

    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing = []

    for member in FeedbackSeverity:
        for lang in all_languages:
            try:
                name = member.get_name(lang)
                if isinstance(name, str) and len(name) > 0:
                    total_entries += 1
                else:
                    missing.append(f"{member.name}/{lang.name}")
            except (KeyError, AttributeError):
                missing.append(f"{member.name}/{lang.name}")

    r.check(f"i18n 전체 엔트리 = {total_entries}/25",
            total_entries == 25 and len(missing) == 0,
            f"누락: {missing}")

    # 대표 번역 검증
    r.check("CRITICAL KO = '즉시 개선'",
            FeedbackSeverity.CRITICAL.get_name(SupportedLanguage.KO) == "즉시 개선")
    r.check("CRITICAL EN = 'Critical'",
            FeedbackSeverity.CRITICAL.get_name(SupportedLanguage.EN) == "Critical")
    r.check("GOOD KO = '양호'",
            FeedbackSeverity.GOOD.get_name(SupportedLanguage.KO) == "양호")
    r.check("EXCELLENT EN = 'Excellent'",
            FeedbackSeverity.EXCELLENT.get_name(SupportedLanguage.EN) == "Excellent")
    r.check("NEEDS_WORK JA = '改善必要'",
            FeedbackSeverity.NEEDS_WORK.get_name(SupportedLanguage.JA) == "改善必要")
    r.check("ACCEPTABLE ZH = '一般'",
            FeedbackSeverity.ACCEPTABLE.get_name(SupportedLanguage.ZH) == "一般")
    r.check("EXCELLENT ES = 'Excelente'",
            FeedbackSeverity.EXCELLENT.get_name(SupportedLanguage.ES) == "Excelente")

    # 기본 인자 (lang 미지정 시 KO)
    default_name = FeedbackSeverity.GOOD.get_name()
    r.check("get_name() 기본 = KO ('양호')",
            default_name == "양호",
            f"실제: {default_name}")


# =============================================================================
# [D] FeedbackCategory 기본 (8 멤버, str 값)
# =============================================================================
def test_d_feedback_category_basics(r: TestResult) -> None:
    """[D] FeedbackCategory Enum 기본 속성 검증."""
    print("\n[D] FeedbackCategory 기본 (8 멤버, str 값)")

    members = list(FeedbackCategory)
    r.check("FeedbackCategory 멤버 수 = 8", len(members) == 8, f"실제: {len(members)}")

    expected = {
        "GAME_OVERALL": "game_overall",
        "TACTICAL": "tactical",
        "DEFENSIVE": "defensive",
        "INDIVIDUAL": "individual",
        "SPATIAL": "spatial",
        "LINEUP": "lineup",
        "REFEREE": "referee",
        "VISUAL": "visual",
    }

    for name, value in expected.items():
        member = FeedbackCategory[name]
        r.check(f"FeedbackCategory.{name} == '{value}'",
                member.value == value,
                f"expected='{value}', actual='{member.value}'")

    r.check("FeedbackCategory는 str 상속", issubclass(FeedbackCategory, str))
    r.check("FeedbackCategory는 Enum 상속", issubclass(FeedbackCategory, Enum))


# =============================================================================
# [E] FeedbackCategory i18n
# =============================================================================
def test_e_feedback_category_i18n(r: TestResult) -> None:
    """[E] FeedbackCategory i18n 검증."""
    print("\n[E] FeedbackCategory i18n (5개 언어 x 8 멤버 = 40)")

    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing = []

    for member in FeedbackCategory:
        for lang in all_languages:
            try:
                name = member.get_name(lang)
                if isinstance(name, str) and len(name) > 0:
                    total_entries += 1
                else:
                    missing.append(f"{member.name}/{lang.name}")
            except (KeyError, AttributeError):
                missing.append(f"{member.name}/{lang.name}")

    r.check(f"i18n 전체 엔트리 = {total_entries}/40",
            total_entries == 40 and len(missing) == 0,
            f"누락: {missing}")

    # 대표 번역 검증
    r.check("GAME_OVERALL KO = '경기 종합'",
            FeedbackCategory.GAME_OVERALL.get_name(SupportedLanguage.KO) == "경기 종합")
    r.check("TACTICAL EN = 'Offensive Tactics'",
            FeedbackCategory.TACTICAL.get_name(SupportedLanguage.EN) == "Offensive Tactics")
    r.check("DEFENSIVE JA = '守備分析'",
            FeedbackCategory.DEFENSIVE.get_name(SupportedLanguage.JA) == "守備分析")
    r.check("REFEREE ES = 'Decisiones Arbitrales'",
            FeedbackCategory.REFEREE.get_name(SupportedLanguage.ES) == "Decisiones Arbitrales")
    r.check("VISUAL ZH = '视觉反馈'",
            FeedbackCategory.VISUAL.get_name(SupportedLanguage.ZH) == "视觉反馈")

    # 기본 인자 (KO)
    default_name = FeedbackCategory.SPATIAL.get_name()
    r.check("get_name() 기본 = KO ('공간 분석')",
            default_name == "공간 분석",
            f"실제: {default_name}")


# =============================================================================
# [F] ReportType 기본 (6 멤버, str 값)
# =============================================================================
def test_f_report_type_basics(r: TestResult) -> None:
    """[F] ReportType Enum 기본 속성 검증."""
    print("\n[F] ReportType 기본 (6 멤버, str 값)")

    members = list(ReportType)
    r.check("ReportType 멤버 수 = 6", len(members) == 6, f"실제: {len(members)}")

    expected = {
        "SINGLE_GAME": "single_game",
        "SESSION_SUMMARY": "session_summary",
        "PLAYER_PROGRESS": "player_progress",
        "TEAM_TREND": "team_trend",
        "SCOUTING": "scouting",
        "PRE_GAME_BRIEFING": "pre_game_briefing",
    }

    for name, value in expected.items():
        member = ReportType[name]
        r.check(f"ReportType.{name} == '{value}'",
                member.value == value,
                f"expected='{value}', actual='{member.value}'")

    r.check("ReportType은 str 상속", issubclass(ReportType, str))
    r.check("ReportType은 Enum 상속", issubclass(ReportType, Enum))


# =============================================================================
# [G] ReportType i18n
# =============================================================================
def test_g_report_type_i18n(r: TestResult) -> None:
    """[G] ReportType i18n 검증."""
    print("\n[G] ReportType i18n (5개 언어 x 6 멤버 = 30)")

    all_languages = list(SupportedLanguage)
    total_entries = 0
    missing = []

    for member in ReportType:
        for lang in all_languages:
            try:
                name = member.get_name(lang)
                if isinstance(name, str) and len(name) > 0:
                    total_entries += 1
                else:
                    missing.append(f"{member.name}/{lang.name}")
            except (KeyError, AttributeError):
                missing.append(f"{member.name}/{lang.name}")

    r.check(f"i18n 전체 엔트리 = {total_entries}/30",
            total_entries == 30 and len(missing) == 0,
            f"누락: {missing}")

    # 대표 번역 검증
    r.check("SINGLE_GAME KO = '단일 경기 리포트'",
            ReportType.SINGLE_GAME.get_name(SupportedLanguage.KO) == "단일 경기 리포트")
    r.check("SESSION_SUMMARY EN = 'Session Summary'",
            ReportType.SESSION_SUMMARY.get_name(SupportedLanguage.EN) == "Session Summary")
    r.check("PLAYER_PROGRESS JA = '選手成長推移'",
            ReportType.PLAYER_PROGRESS.get_name(SupportedLanguage.JA) == "選手成長推移")
    r.check("SCOUTING ZH = '球探报告'",
            ReportType.SCOUTING.get_name(SupportedLanguage.ZH) == "球探报告")
    r.check("PRE_GAME_BRIEFING ES = 'Briefing Pre-partido'",
            ReportType.PRE_GAME_BRIEFING.get_name(SupportedLanguage.ES) == "Briefing Pre-partido")


# =============================================================================
# [H] ReportOutputFormat 기본 (4 멤버, str 값)
# =============================================================================
def test_h_report_output_format_basics(r: TestResult) -> None:
    """[H] ReportOutputFormat Enum 기본 속성 검증."""
    print("\n[H] ReportOutputFormat 기본 (4 멤버, str 값)")

    members = list(ReportOutputFormat)
    r.check("ReportOutputFormat 멤버 수 = 4", len(members) == 4, f"실제: {len(members)}")

    expected = {
        "HTML": "html",
        "JSON": "json",
        "PDF": "pdf",
        "TEXT": "text",
    }

    for name, value in expected.items():
        member = ReportOutputFormat[name]
        r.check(f"ReportOutputFormat.{name} == '{value}'",
                member.value == value,
                f"expected='{value}', actual='{member.value}'")

    r.check("ReportOutputFormat은 str 상속", issubclass(ReportOutputFormat, str))
    r.check("ReportOutputFormat은 Enum 상속", issubclass(ReportOutputFormat, Enum))

    # __str__ 동작
    r.check("str(HTML) == 'html'", str(ReportOutputFormat.HTML) == "html")
    r.check("str(JSON) == 'json'", str(ReportOutputFormat.JSON) == "json")
    r.check("str(PDF) == 'pdf'", str(ReportOutputFormat.PDF) == "pdf")
    r.check("str(TEXT) == 'text'", str(ReportOutputFormat.TEXT) == "text")


# =============================================================================
# [I] 피드백 품질 파라미터
# =============================================================================
def test_i_feedback_quality_params(r: TestResult) -> None:
    """[I] 피드백 품질 파라미터 검증."""
    print("\n[I] 피드백 품질 파라미터")

    # FEEDBACK_MIN_DETAIL_POINTS: int >= 10
    r.check("FEEDBACK_MIN_DETAIL_POINTS 타입 int",
            isinstance(FEEDBACK_MIN_DETAIL_POINTS, int))
    r.check("FEEDBACK_MIN_DETAIL_POINTS >= 10 (CLAUDE.md #15)",
            FEEDBACK_MIN_DETAIL_POINTS >= 10,
            f"실제: {FEEDBACK_MIN_DETAIL_POINTS}")
    r.check("FEEDBACK_MIN_DETAIL_POINTS = 10",
            FEEDBACK_MIN_DETAIL_POINTS == 10,
            f"실제: {FEEDBACK_MIN_DETAIL_POINTS}")

    # FEEDBACK_POSITIVE_RATIO_MIN/MAX: float 범위
    r.check("FEEDBACK_POSITIVE_RATIO_MIN 타입 float",
            isinstance(FEEDBACK_POSITIVE_RATIO_MIN, float))
    r.check("FEEDBACK_POSITIVE_RATIO_MAX 타입 float",
            isinstance(FEEDBACK_POSITIVE_RATIO_MAX, float))
    r.check("0 < POSITIVE_RATIO_MIN < POSITIVE_RATIO_MAX <= 1",
            0.0 < FEEDBACK_POSITIVE_RATIO_MIN < FEEDBACK_POSITIVE_RATIO_MAX <= 1.0,
            f"MIN={FEEDBACK_POSITIVE_RATIO_MIN}, MAX={FEEDBACK_POSITIVE_RATIO_MAX}")
    r.check("POSITIVE_RATIO_MIN = 0.60", FEEDBACK_POSITIVE_RATIO_MIN == 0.60)
    r.check("POSITIVE_RATIO_MAX = 0.85", FEEDBACK_POSITIVE_RATIO_MAX == 0.85)

    # FEEDBACK_MAX/MIN_LENGTH_CHARS: int
    r.check("FEEDBACK_MAX_LENGTH_CHARS 타입 int",
            isinstance(FEEDBACK_MAX_LENGTH_CHARS, int))
    r.check("FEEDBACK_MIN_LENGTH_CHARS 타입 int",
            isinstance(FEEDBACK_MIN_LENGTH_CHARS, int))
    r.check("MIN_LENGTH < MAX_LENGTH",
            FEEDBACK_MIN_LENGTH_CHARS < FEEDBACK_MAX_LENGTH_CHARS,
            f"MIN={FEEDBACK_MIN_LENGTH_CHARS}, MAX={FEEDBACK_MAX_LENGTH_CHARS}")
    r.check("MAX_LENGTH = 2000", FEEDBACK_MAX_LENGTH_CHARS == 2000)
    r.check("MIN_LENGTH = 100", FEEDBACK_MIN_LENGTH_CHARS == 100)


# =============================================================================
# [J] FEEDBACK_CATEGORY_PRIORITY
# =============================================================================
def test_j_feedback_category_priority(r: TestResult) -> None:
    """[J] FEEDBACK_CATEGORY_PRIORITY 검증."""
    print("\n[J] FEEDBACK_CATEGORY_PRIORITY (8 카테고리)")

    # 타입 검증
    r.check("FEEDBACK_CATEGORY_PRIORITY 타입 dict",
            isinstance(FEEDBACK_CATEGORY_PRIORITY, dict))

    # 8개 카테고리 전부 포함
    r.check("FEEDBACK_CATEGORY_PRIORITY 키 수 = 8",
            len(FEEDBACK_CATEGORY_PRIORITY) == 8,
            f"실제: {len(FEEDBACK_CATEGORY_PRIORITY)}")

    # 키가 FeedbackCategory 전체와 일치
    expected_keys = set(FeedbackCategory)
    actual_keys = set(FEEDBACK_CATEGORY_PRIORITY.keys())
    r.check("키 = FeedbackCategory 전체",
            actual_keys == expected_keys,
            f"차이: {actual_keys.symmetric_difference(expected_keys)}")

    # 모든 값이 float, 0.0~1.0 범위
    for cat, priority in FEEDBACK_CATEGORY_PRIORITY.items():
        r.check(f"{cat.name} 우선순위 = {priority} (float, 0~1)",
                isinstance(priority, float) and 0.0 <= priority <= 1.0,
                f"타입: {type(priority)}, 값: {priority}")

    # 구체적 값 검증
    r.check("GAME_OVERALL = 1.0",
            FEEDBACK_CATEGORY_PRIORITY[FeedbackCategory.GAME_OVERALL] == 1.0)
    r.check("TACTICAL = 0.9",
            FEEDBACK_CATEGORY_PRIORITY[FeedbackCategory.TACTICAL] == 0.9)
    r.check("DEFENSIVE = 0.9",
            FEEDBACK_CATEGORY_PRIORITY[FeedbackCategory.DEFENSIVE] == 0.9)
    r.check("INDIVIDUAL = 0.85",
            FEEDBACK_CATEGORY_PRIORITY[FeedbackCategory.INDIVIDUAL] == 0.85)
    r.check("VISUAL = 0.5 (최저)",
            FEEDBACK_CATEGORY_PRIORITY[FeedbackCategory.VISUAL] == 0.5)


# =============================================================================
# [K] 리포트 섹션 구성
# =============================================================================
def test_k_report_sections(r: TestResult) -> None:
    """[K] 리포트 섹션 구성 검증."""
    print("\n[K] 리포트 섹션 구성")

    # SINGLE_GAME_REPORT_SECTIONS
    r.check("SINGLE_GAME_REPORT_SECTIONS 타입 list",
            isinstance(SINGLE_GAME_REPORT_SECTIONS, list))
    r.check("SINGLE_GAME_REPORT_SECTIONS 비어있지 않음",
            len(SINGLE_GAME_REPORT_SECTIONS) > 0)
    r.check("SINGLE_GAME_REPORT_SECTIONS 10개 섹션",
            len(SINGLE_GAME_REPORT_SECTIONS) == 10,
            f"실제: {len(SINGLE_GAME_REPORT_SECTIONS)}")

    # 모든 항목 문자열
    r.check("모든 섹션이 비어있지 않은 문자열",
            all(isinstance(s, str) and len(s) > 0 for s in SINGLE_GAME_REPORT_SECTIONS))

    # 중복 없음
    r.check("섹션 중복 없음",
            len(SINGLE_GAME_REPORT_SECTIONS) == len(set(SINGLE_GAME_REPORT_SECTIONS)))

    # 개별 섹션 존재 확인
    expected_sections = [
        "game_summary", "team_comparison", "four_factors",
        "key_players", "shot_chart", "play_type_breakdown",
        "defensive_analysis", "game_flow", "lineup_analysis",
        "coaching_points",
    ]
    for section in expected_sections:
        r.check(f"'{section}' in SINGLE_GAME_REPORT_SECTIONS",
                section in SINGLE_GAME_REPORT_SECTIONS,
                f"'{section}' 누락")

    # 순서 검증 (game_summary 첫 번째, coaching_points 마지막)
    r.check("첫 번째 섹션 = 'game_summary'",
            SINGLE_GAME_REPORT_SECTIONS[0] == "game_summary")
    r.check("마지막 섹션 = 'coaching_points'",
            SINGLE_GAME_REPORT_SECTIONS[-1] == "coaching_points")

    # 기타 리포트 상수
    r.check("REPORT_SECTION_MAX_ITEMS = 15",
            REPORT_SECTION_MAX_ITEMS == 15, f"실제: {REPORT_SECTION_MAX_ITEMS}")
    r.check("REPORT_KEY_PLAYERS_COUNT = 5",
            REPORT_KEY_PLAYERS_COUNT == 5, f"실제: {REPORT_KEY_PLAYERS_COUNT}")
    r.check("REPORT_TOP_N_DEFAULT = 5",
            REPORT_TOP_N_DEFAULT == 5, f"실제: {REPORT_TOP_N_DEFAULT}")


# =============================================================================
# [L] 시각 피드백 파라미터
# =============================================================================
def test_l_visual_feedback_params(r: TestResult) -> None:
    """[L] 시각 피드백 파라미터 검증."""
    print("\n[L] 시각 피드백 파라미터")

    # 히트맵 격자
    r.check("HEATMAP_GRID_X = 50", HEATMAP_GRID_X == 50)
    r.check("HEATMAP_GRID_Y = 47", HEATMAP_GRID_Y == 47)

    # 코트 다이어그램
    r.check("COURT_DIAGRAM_WIDTH_PX = 940", COURT_DIAGRAM_WIDTH_PX == 940)
    r.check("COURT_DIAGRAM_HEIGHT_PX = 500", COURT_DIAGRAM_HEIGHT_PX == 500)
    r.check("코트 가로 > 세로 (농구 코트 비율)",
            COURT_DIAGRAM_WIDTH_PX > COURT_DIAGRAM_HEIGHT_PX)

    # 슛 차트 마커
    r.check("SHOT_CHART_MARKER_SIZE_MADE = 8", SHOT_CHART_MARKER_SIZE_MADE == 8)
    r.check("SHOT_CHART_MARKER_SIZE_MISSED = 6", SHOT_CHART_MARKER_SIZE_MISSED == 6)
    r.check("성공 마커 > 실패 마커",
            SHOT_CHART_MARKER_SIZE_MADE > SHOT_CHART_MARKER_SIZE_MISSED)

    # 시계열
    r.check("TIME_SERIES_MIN_POINTS = 5", TIME_SERIES_MIN_POINTS == 5)

    # 오버레이 투명도
    r.check("OVERLAY_OPACITY_DEFAULT = 0.6", OVERLAY_OPACITY_DEFAULT == 0.6)
    r.check("OVERLAY_OPACITY_HIGHLIGHT = 0.8", OVERLAY_OPACITY_HIGHLIGHT == 0.8)
    r.check("HIGHLIGHT > DEFAULT",
            OVERLAY_OPACITY_HIGHLIGHT > OVERLAY_OPACITY_DEFAULT)

    # 주석 화살표
    r.check("ANNOTATION_ARROW_WIDTH_PX = 2", ANNOTATION_ARROW_WIDTH_PX == 2)


# =============================================================================
# [M] 필름 세션 파라미터
# =============================================================================
def test_m_film_session_params(r: TestResult) -> None:
    """[M] 필름 세션 파라미터 검증."""
    print("\n[M] 필름 세션 파라미터")

    r.check("FILM_SESSION_AVG_CLIP_REVIEW_SEC = 45",
            FILM_SESSION_AVG_CLIP_REVIEW_SEC == 45)
    r.check("FILM_SESSION_MAX_CLIPS = 50",
            FILM_SESSION_MAX_CLIPS == 50)
    r.check("타입 int (AVG)", isinstance(FILM_SESSION_AVG_CLIP_REVIEW_SEC, int))
    r.check("타입 int (MAX)", isinstance(FILM_SESSION_MAX_CLIPS, int))
    r.check("AVG > 0", FILM_SESSION_AVG_CLIP_REVIEW_SEC > 0)
    r.check("MAX > 0", FILM_SESSION_MAX_CLIPS > 0)


# =============================================================================
# [N] 성장 추세 파라미터
# =============================================================================
def test_n_growth_params(r: TestResult) -> None:
    """[N] 성장 추세 파라미터 검증."""
    print("\n[N] 성장 추세 파라미터")

    r.check("GROWTH_MIN_GAMES = 5", GROWTH_MIN_GAMES == 5)
    r.check("GROWTH_IMPROVING_SLOPE = 0.02", GROWTH_IMPROVING_SLOPE == 0.02)
    r.check("GROWTH_DECLINING_SLOPE = -0.02", GROWTH_DECLINING_SLOPE == -0.02)
    r.check("IMPROVING > 0", GROWTH_IMPROVING_SLOPE > 0)
    r.check("DECLINING < 0", GROWTH_DECLINING_SLOPE < 0)
    r.check("대칭 (|IMPROVING| == |DECLINING|)",
            abs(GROWTH_IMPROVING_SLOPE + GROWTH_DECLINING_SLOPE) < 1e-9)
    r.check("REPEATED_MISTAKE_MIN_GAMES = 3", REPEATED_MISTAKE_MIN_GAMES == 3)
    r.check("IMPROVEMENT_PRIORITY_TOP_N = 5", IMPROVEMENT_PRIORITY_TOP_N == 5)

    # 타입 검증
    r.check("GROWTH_MIN_GAMES 타입 int", isinstance(GROWTH_MIN_GAMES, int))
    r.check("GROWTH_IMPROVING_SLOPE 타입 float", isinstance(GROWTH_IMPROVING_SLOPE, float))
    r.check("GROWTH_DECLINING_SLOPE 타입 float", isinstance(GROWTH_DECLINING_SLOPE, float))
    r.check("REPEATED_MISTAKE_MIN_GAMES 타입 int", isinstance(REPEATED_MISTAKE_MIN_GAMES, int))
    r.check("IMPROVEMENT_PRIORITY_TOP_N 타입 int", isinstance(IMPROVEMENT_PRIORITY_TOP_N, int))


# =============================================================================
# [O] get_feedback_severity_from_percentile 경계값
# =============================================================================
def test_o_severity_from_percentile_boundaries(r: TestResult) -> None:
    """[O] get_feedback_severity_from_percentile 경계값 검증."""
    print("\n[O] get_feedback_severity_from_percentile 경계값")

    # 경계값 검증
    boundary_tests = [
        (100.0, FeedbackSeverity.EXCELLENT, "100 -> EXCELLENT"),
        (95.0, FeedbackSeverity.EXCELLENT, "95 -> EXCELLENT"),
        (90.0, FeedbackSeverity.EXCELLENT, "90 -> EXCELLENT"),
        (89.9, FeedbackSeverity.GOOD, "89.9 -> GOOD"),
        (75.0, FeedbackSeverity.GOOD, "75 -> GOOD"),
        (70.0, FeedbackSeverity.GOOD, "70 -> GOOD"),
        (69.9, FeedbackSeverity.ACCEPTABLE, "69.9 -> ACCEPTABLE"),
        (50.0, FeedbackSeverity.ACCEPTABLE, "50 -> ACCEPTABLE"),
        (40.0, FeedbackSeverity.ACCEPTABLE, "40 -> ACCEPTABLE"),
        (39.9, FeedbackSeverity.NEEDS_WORK, "39.9 -> NEEDS_WORK"),
        (25.0, FeedbackSeverity.NEEDS_WORK, "25 -> NEEDS_WORK"),
        (15.0, FeedbackSeverity.NEEDS_WORK, "15 -> NEEDS_WORK"),
        (14.9, FeedbackSeverity.CRITICAL, "14.9 -> CRITICAL"),
        (5.0, FeedbackSeverity.CRITICAL, "5 -> CRITICAL"),
        (0.0, FeedbackSeverity.CRITICAL, "0 -> CRITICAL"),
    ]

    for percentile, expected, desc in boundary_tests:
        actual = get_feedback_severity_from_percentile(percentile)
        r.check(desc, actual == expected,
                f"기대: {expected.name}, 실제: {actual.name}")


# =============================================================================
# [P] get_feedback_severity_from_percentile 극단값
# =============================================================================
def test_p_severity_from_percentile_extremes(r: TestResult) -> None:
    """[P] get_feedback_severity_from_percentile 극단값 검증."""
    print("\n[P] get_feedback_severity_from_percentile 극단값")

    # 반환 타입 항상 FeedbackSeverity
    for val in [0.0, 15.0, 40.0, 70.0, 90.0, 100.0]:
        result = get_feedback_severity_from_percentile(val)
        r.check(f"percentile={val} 반환 타입 FeedbackSeverity",
                isinstance(result, FeedbackSeverity),
                f"실제 타입: {type(result)}")

    # 연속 구간 검증 (0~100 1단위 순회)
    prev_severity = None
    transitions = 0
    for p in range(101):
        s = get_feedback_severity_from_percentile(float(p))
        if prev_severity is not None and s != prev_severity:
            transitions += 1
        prev_severity = s

    r.check("0~100 구간에서 정확히 4번 전환 (5 등급)",
            transitions == 4,
            f"실제 전환 횟수: {transitions}")


# =============================================================================
# [Q] estimate_film_session_duration_min 기본 계산
# =============================================================================
def test_q_estimate_duration_basic(r: TestResult) -> None:
    """[Q] estimate_film_session_duration_min 기본 계산 검증."""
    print("\n[Q] estimate_film_session_duration_min 기본 계산")

    # 0 클립
    r.check("0 클립 = 0.0분", estimate_film_session_duration_min(0) == 0.0)

    # 1 클립
    expected_1 = FILM_SESSION_AVG_CLIP_REVIEW_SEC / 60.0
    r.check(f"1 클립 = {expected_1}분",
            abs(estimate_film_session_duration_min(1) - expected_1) < 1e-9)

    # 10 클립
    expected_10 = (10 * FILM_SESSION_AVG_CLIP_REVIEW_SEC) / 60.0
    r.check(f"10 클립 = {expected_10}분",
            abs(estimate_film_session_duration_min(10) - expected_10) < 1e-9)

    # 반환 타입
    r.check("반환 타입 float", isinstance(estimate_film_session_duration_min(5), float))

    # 양수 결과 (클립 수 > 0)
    r.check("5 클립 -> 양수", estimate_film_session_duration_min(5) > 0)


# =============================================================================
# [R] estimate_film_session_duration_min 클립 제한
# =============================================================================
def test_r_estimate_duration_clip_limit(r: TestResult) -> None:
    """[R] estimate_film_session_duration_min 클립 제한 검증."""
    print("\n[R] estimate_film_session_duration_min 클립 제한")

    max_clips = FILM_SESSION_MAX_CLIPS
    expected_max = (max_clips * FILM_SESSION_AVG_CLIP_REVIEW_SEC) / 60.0

    # 정확히 최대 클립
    r.check(f"{max_clips} 클립 (최대) = {expected_max}분",
            abs(estimate_film_session_duration_min(max_clips) - expected_max) < 1e-9)

    # 초과 클립 -> 최대치로 제한
    over_max = max_clips + 50
    r.check(f"{over_max} 클립 (초과) = {expected_max}분 (최대치 제한)",
            abs(estimate_film_session_duration_min(over_max) - expected_max) < 1e-9)

    # 매우 큰 값 -> 여전히 최대치
    r.check("10000 클립 = 최대치",
            abs(estimate_film_session_duration_min(10000) - expected_max) < 1e-9)

    # max_clips 미만은 다른 값
    below = max_clips - 1
    expected_below = (below * FILM_SESSION_AVG_CLIP_REVIEW_SEC) / 60.0
    r.check(f"{below} 클립 < 최대치 (서로 다른 값)",
            estimate_film_session_duration_min(below) < expected_max)
    r.check(f"{below} 클립 = {expected_below}분",
            abs(estimate_film_session_duration_min(below) - expected_below) < 1e-9)


# =============================================================================
# [S] Enum identity / hashable / set 사용
# =============================================================================
def test_s_enum_identity_and_hashing(r: TestResult) -> None:
    """[S] Enum identity, hashable, set 사용 검증."""
    print("\n[S] Enum identity / hashable / set 사용")

    # identity (is)
    r.check("FeedbackSeverity.CRITICAL is FeedbackSeverity.CRITICAL",
            FeedbackSeverity.CRITICAL is FeedbackSeverity.CRITICAL)
    r.check("FeedbackCategory.TACTICAL is FeedbackCategory.TACTICAL",
            FeedbackCategory.TACTICAL is FeedbackCategory.TACTICAL)
    r.check("ReportType.SINGLE_GAME is ReportType.SINGLE_GAME",
            ReportType.SINGLE_GAME is ReportType.SINGLE_GAME)
    r.check("ReportOutputFormat.HTML is ReportOutputFormat.HTML",
            ReportOutputFormat.HTML is ReportOutputFormat.HTML)

    # hashable (set에 넣을 수 있음)
    severity_set = set(FeedbackSeverity)
    r.check("FeedbackSeverity set 크기 = 5",
            len(severity_set) == 5, f"실제: {len(severity_set)}")

    category_set = set(FeedbackCategory)
    r.check("FeedbackCategory set 크기 = 8",
            len(category_set) == 8, f"실제: {len(category_set)}")

    report_set = set(ReportType)
    r.check("ReportType set 크기 = 6",
            len(report_set) == 6, f"실제: {len(report_set)}")

    format_set = set(ReportOutputFormat)
    r.check("ReportOutputFormat set 크기 = 4",
            len(format_set) == 4, f"실제: {len(format_set)}")

    # dict 키로 사용 가능
    d = {FeedbackSeverity.CRITICAL: "test"}
    r.check("Enum을 dict 키로 사용 가능", FeedbackSeverity.CRITICAL in d)


# =============================================================================
# [T] __str__ mixin 검증
# =============================================================================
def test_t_str_mixin(r: TestResult) -> None:
    """[T] __str__ mixin으로 문자열 비교 가능 검증."""
    print("\n[T] __str__ mixin 검증 (문자열 비교)")

    # FeedbackSeverity 문자열 비교
    r.check("FeedbackSeverity.CRITICAL == 'critical'",
            FeedbackSeverity.CRITICAL == "critical")
    r.check("FeedbackSeverity.GOOD == 'good'",
            FeedbackSeverity.GOOD == "good")

    # FeedbackCategory 문자열 비교
    r.check("FeedbackCategory.TACTICAL == 'tactical'",
            FeedbackCategory.TACTICAL == "tactical")
    r.check("FeedbackCategory.REFEREE == 'referee'",
            FeedbackCategory.REFEREE == "referee")

    # ReportType 문자열 비교
    r.check("ReportType.SINGLE_GAME == 'single_game'",
            ReportType.SINGLE_GAME == "single_game")
    r.check("ReportType.SCOUTING == 'scouting'",
            ReportType.SCOUTING == "scouting")

    # ReportOutputFormat 문자열 비교
    r.check("ReportOutputFormat.HTML == 'html'",
            ReportOutputFormat.HTML == "html")
    r.check("ReportOutputFormat.PDF == 'pdf'",
            ReportOutputFormat.PDF == "pdf")

    # str() 메서드 (명시적)
    r.check("str(FeedbackSeverity.EXCELLENT) == 'excellent'",
            str(FeedbackSeverity.EXCELLENT) == "excellent")
    r.check("str(FeedbackCategory.VISUAL) == 'visual'",
            str(FeedbackCategory.VISUAL) == "visual")


# =============================================================================
# [U] __all__ Export 완전성
# =============================================================================
def test_u_all_exports(r: TestResult) -> None:
    """[U] __all__ export 완전성 검증."""
    print("\n[U] __all__ Export 완전성")

    all_exports = fc.__all__
    r.check("__all__ 리스트 존재", isinstance(all_exports, list) and len(all_exports) > 0)

    # 총 항목 수
    r.check("__all__ 총 항목 수 = 34",
            len(all_exports) == 34,
            f"실제: {len(all_exports)}")

    # 중복 없음
    r.check("__all__ 중복 없음",
            len(all_exports) == len(set(all_exports)),
            f"중복: {[x for x in all_exports if all_exports.count(x) > 1]}")

    # 모든 항목이 실제 모듈 속성
    missing_attrs = [name for name in all_exports if not hasattr(fc, name)]
    r.check("모든 __all__ 항목이 모듈 속성으로 존재",
            len(missing_attrs) == 0,
            f"누락: {missing_attrs}")

    # 카테고리별 확인
    expected_categories = {
        "열거형": ["FeedbackSeverity", "FeedbackCategory", "ReportType", "ReportOutputFormat"],
        "품질상수": ["FEEDBACK_MIN_DETAIL_POINTS", "FEEDBACK_POSITIVE_RATIO_MIN",
                   "FEEDBACK_POSITIVE_RATIO_MAX", "FEEDBACK_MAX_LENGTH_CHARS",
                   "FEEDBACK_MIN_LENGTH_CHARS", "FEEDBACK_CATEGORY_PRIORITY"],
        "리포트": ["SINGLE_GAME_REPORT_SECTIONS", "REPORT_SECTION_MAX_ITEMS",
                  "REPORT_KEY_PLAYERS_COUNT", "REPORT_TOP_N_DEFAULT"],
        "시각": ["HEATMAP_GRID_X", "HEATMAP_GRID_Y",
                "COURT_DIAGRAM_WIDTH_PX", "COURT_DIAGRAM_HEIGHT_PX",
                "SHOT_CHART_MARKER_SIZE_MADE", "SHOT_CHART_MARKER_SIZE_MISSED",
                "TIME_SERIES_MIN_POINTS",
                "OVERLAY_OPACITY_DEFAULT", "OVERLAY_OPACITY_HIGHLIGHT",
                "ANNOTATION_ARROW_WIDTH_PX"],
        "필름": ["FILM_SESSION_AVG_CLIP_REVIEW_SEC", "FILM_SESSION_MAX_CLIPS"],
        "성장": ["GROWTH_MIN_GAMES", "GROWTH_IMPROVING_SLOPE", "GROWTH_DECLINING_SLOPE",
                "REPEATED_MISTAKE_MIN_GAMES", "IMPROVEMENT_PRIORITY_TOP_N"],
        "유틸리티": ["get_feedback_severity_from_percentile", "estimate_film_session_duration_min"],
        "버전": ["__version__"],
    }

    for category_name, items in expected_categories.items():
        for item in items:
            r.check(f"[{category_name}] '{item}' in __all__",
                    item in all_exports,
                    f"'{item}' 누락")

    # __version__
    r.check("__version__ = '1.0.0'", fc.__version__ == "1.0.0", f"실제: {fc.__version__}")


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """모든 유닛 테스트 실행."""
    print("=" * 60)
    print("feedback_constants.py 유닛 테스트")
    print("=" * 60)

    r = TestResult()

    # [A] FeedbackSeverity 기본
    test_a_feedback_severity_basics(r)

    # [B] FeedbackSeverity 프로퍼티
    test_b_feedback_severity_properties(r)

    # [C] FeedbackSeverity i18n
    test_c_feedback_severity_i18n(r)

    # [D] FeedbackCategory 기본
    test_d_feedback_category_basics(r)

    # [E] FeedbackCategory i18n
    test_e_feedback_category_i18n(r)

    # [F] ReportType 기본
    test_f_report_type_basics(r)

    # [G] ReportType i18n
    test_g_report_type_i18n(r)

    # [H] ReportOutputFormat 기본
    test_h_report_output_format_basics(r)

    # [I] 피드백 품질 파라미터
    test_i_feedback_quality_params(r)

    # [J] FEEDBACK_CATEGORY_PRIORITY
    test_j_feedback_category_priority(r)

    # [K] 리포트 섹션 구성
    test_k_report_sections(r)

    # [L] 시각 피드백 파라미터
    test_l_visual_feedback_params(r)

    # [M] 필름 세션 파라미터
    test_m_film_session_params(r)

    # [N] 성장 추세 파라미터
    test_n_growth_params(r)

    # [O] severity_from_percentile 경계값
    test_o_severity_from_percentile_boundaries(r)

    # [P] severity_from_percentile 극단값
    test_p_severity_from_percentile_extremes(r)

    # [Q] estimate_duration 기본
    test_q_estimate_duration_basic(r)

    # [R] estimate_duration 클립 제한
    test_r_estimate_duration_clip_limit(r)

    # [S] Enum identity / hashable
    test_s_enum_identity_and_hashing(r)

    # [T] __str__ mixin
    test_t_str_mixin(r)

    # [U] __all__ Export
    test_u_all_exports(r)

    r.summary()
    sys.exit(0 if r.failed == 0 else 1)


if __name__ == "__main__":
    main()
