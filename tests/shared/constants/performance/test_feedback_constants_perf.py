# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_feedback_constants_perf.py

피드백 상수 모듈(feedback_constants.py v1.0.0) 성능 테스트

테스트 범위:
    [A] 모듈 임포트 시간 (< 500ms, cold import 의존성 포함)
    [B] FeedbackSeverity Enum 멤버 접근 (100K < 500ms)
    [C] FeedbackCategory Enum 멤버 접근 (100K < 500ms)
    [D] ReportType Enum 멤버 접근 (100K < 500ms)
    [E] ReportOutputFormat Enum 멤버 접근 (100K < 500ms)
    [F] Enum i18n get_name() 호출 (10K < 200ms)
    [G] FeedbackSeverity property 접근 (100K < 500ms) - is_positive, priority_weight
    [H] FEEDBACK_CATEGORY_PRIORITY dict 조회 (100K < 500ms)
    [I] get_feedback_severity_from_percentile 함수 (50K < 300ms)
    [J] estimate_film_session_duration_min 함수 (50K < 300ms)
    [K] 메모리 사용량 (모듈 객체 < 1MB)

성능 기준:
    - 모듈 임포트: < 500ms (cold import, localization 의존성 포함)
    - Enum 멤버 접근: 100K iterations < 500ms
    - i18n get_name(): 10K iterations < 200ms
    - property 접근: 100K iterations < 500ms
    - Dict 조회: 100K iterations < 500ms
    - 유틸리티 함수: 50K iterations < 300ms
    - 메모리 사용량: < 1MB

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (parents[4]: performance -> constants -> shared -> tests -> PROJECT_ROOT)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 수집 및 보고"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        self.passed += 1
        ratio = elapsed_ms / limit_ms * 100
        print(f"  [PASS] {name}: {elapsed_ms:.4f}ms ({ratio:.1f}% of {limit_ms:.0f}ms)")

    def fail(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_ms:.4f}ms > {limit_ms:.0f}ms")
        print(f"  [FAIL] {name}: {elapsed_ms:.4f}ms (limit: {limit_ms:.0f}ms)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def check(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        """결과 판정 (ms 기준)"""
        if elapsed_ms <= limit_ms:
            self.ok(name, elapsed_ms, limit_ms)
        else:
            self.fail(name, elapsed_ms, limit_ms)

    def check_memory(self, name: str, size_kb: float, limit_kb: float) -> None:
        """메모리 결과 판정 (KB 기준)"""
        if size_kb <= limit_kb:
            self.passed += 1
            ratio = size_kb / limit_kb * 100
            print(f"  [PASS] {name}: {size_kb:.2f}KB ({ratio:.1f}% of {limit_kb:.0f}KB)")
        else:
            self.failed += 1
            self.errors.append(f"{name}: {size_kb:.2f}KB > {limit_kb:.0f}KB")
            print(f"  [FAIL] {name}: {size_kb:.2f}KB (limit: {limit_kb:.0f}KB)")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n목표 미달 항목:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# =============================================================================
# [A] 모듈 임포트 시간 (< 500ms)
# =============================================================================
def test_a_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 측정 (< 500ms, localization 의존성 포함)"""
    import importlib

    mod_name = "shared.constants.feedback_constants"
    # 모듈 캐시에서 제거하여 cold import 측정
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter()
    importlib.import_module(mod_name)
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    r.info(f"임포트 시간: {elapsed_ms:.2f}ms")
    r.check("모듈 임포트 (cold)", elapsed_ms, 500.0)


# =============================================================================
# [B] FeedbackSeverity Enum 멤버 접근 (100K < 500ms)
# =============================================================================
def test_b_feedback_severity_access(r: PerfResult) -> None:
    """FeedbackSeverity Enum 멤버 접근 (100K iterations < 500ms)"""
    from shared.constants.feedback_constants import FeedbackSeverity

    iterations = 100_000

    # FeedbackSeverity 멤버 접근 (5종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = FeedbackSeverity.CRITICAL
        _ = FeedbackSeverity.NEEDS_WORK
        _ = FeedbackSeverity.ACCEPTABLE
        _ = FeedbackSeverity.GOOD
        _ = FeedbackSeverity.EXCELLENT
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FeedbackSeverity 멤버 접근 (100K x 5종)", elapsed_ms, 500.0)


# =============================================================================
# [C] FeedbackCategory Enum 멤버 접근 (100K < 500ms)
# =============================================================================
def test_c_feedback_category_access(r: PerfResult) -> None:
    """FeedbackCategory Enum 멤버 접근 (100K iterations < 500ms)"""
    from shared.constants.feedback_constants import FeedbackCategory

    iterations = 100_000

    # FeedbackCategory 멤버 접근 (8종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = FeedbackCategory.GAME_OVERALL
        _ = FeedbackCategory.TACTICAL
        _ = FeedbackCategory.DEFENSIVE
        _ = FeedbackCategory.INDIVIDUAL
        _ = FeedbackCategory.SPATIAL
        _ = FeedbackCategory.LINEUP
        _ = FeedbackCategory.REFEREE
        _ = FeedbackCategory.VISUAL
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FeedbackCategory 멤버 접근 (100K x 8종)", elapsed_ms, 500.0)


# =============================================================================
# [D] ReportType Enum 멤버 접근 (100K < 500ms)
# =============================================================================
def test_d_report_type_access(r: PerfResult) -> None:
    """ReportType Enum 멤버 접근 (100K iterations < 500ms)"""
    from shared.constants.feedback_constants import ReportType

    iterations = 100_000

    # ReportType 멤버 접근 (6종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = ReportType.SINGLE_GAME
        _ = ReportType.SESSION_SUMMARY
        _ = ReportType.PLAYER_PROGRESS
        _ = ReportType.TEAM_TREND
        _ = ReportType.SCOUTING
        _ = ReportType.PRE_GAME_BRIEFING
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("ReportType 멤버 접근 (100K x 6종)", elapsed_ms, 500.0)


# =============================================================================
# [E] ReportOutputFormat Enum 멤버 접근 (100K < 500ms)
# =============================================================================
def test_e_report_output_format_access(r: PerfResult) -> None:
    """ReportOutputFormat Enum 멤버 접근 (100K iterations < 500ms)"""
    from shared.constants.feedback_constants import ReportOutputFormat

    iterations = 100_000

    # ReportOutputFormat 멤버 접근 (4종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = ReportOutputFormat.HTML
        _ = ReportOutputFormat.JSON
        _ = ReportOutputFormat.PDF
        _ = ReportOutputFormat.TEXT
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("ReportOutputFormat 멤버 접근 (100K x 4종)", elapsed_ms, 500.0)


# =============================================================================
# [F] Enum i18n get_name() 호출 (10K < 200ms)
# =============================================================================
def test_f_enum_i18n_get_name(r: PerfResult) -> None:
    """Enum.get_name() 다국어 조회 (10K iterations < 200ms)"""
    from shared.constants.feedback_constants import (
        FeedbackSeverity,
        FeedbackCategory,
        ReportType,
    )
    from shared.constants.localization import SupportedLanguage

    iterations = 10_000

    # FeedbackSeverity.get_name() 5개 언어 x 5 멤버
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for sev in FeedbackSeverity:
            _ = sev.get_name(SupportedLanguage.KO)
            _ = sev.get_name(SupportedLanguage.EN)
            _ = sev.get_name(SupportedLanguage.JA)
            _ = sev.get_name(SupportedLanguage.ZH)
            _ = sev.get_name(SupportedLanguage.ES)
    elapsed_severity = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FeedbackSeverity.get_name() (10K x 5종 x 5언어)", elapsed_severity, 200.0)

    # FeedbackCategory.get_name() 5개 언어 x 8 카테고리
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for cat in FeedbackCategory:
            _ = cat.get_name(SupportedLanguage.KO)
            _ = cat.get_name(SupportedLanguage.EN)
            _ = cat.get_name(SupportedLanguage.JA)
            _ = cat.get_name(SupportedLanguage.ZH)
            _ = cat.get_name(SupportedLanguage.ES)
    elapsed_category = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FeedbackCategory.get_name() (10K x 8종 x 5언어)", elapsed_category, 200.0)

    # ReportType.get_name() 5개 언어 x 6 유형
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for rt in ReportType:
            _ = rt.get_name(SupportedLanguage.KO)
            _ = rt.get_name(SupportedLanguage.EN)
            _ = rt.get_name(SupportedLanguage.JA)
            _ = rt.get_name(SupportedLanguage.ZH)
            _ = rt.get_name(SupportedLanguage.ES)
    elapsed_report = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("ReportType.get_name() (10K x 6종 x 5언어)", elapsed_report, 200.0)


# =============================================================================
# [G] FeedbackSeverity property 접근 (100K < 500ms) - is_positive, priority_weight
# =============================================================================
def test_g_severity_property_access(r: PerfResult) -> None:
    """FeedbackSeverity.is_positive / .priority_weight 프로퍼티 접근 (100K iterations < 500ms)"""
    from shared.constants.feedback_constants import FeedbackSeverity

    iterations = 100_000

    # is_positive 프로퍼티 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = FeedbackSeverity.CRITICAL.is_positive
        _ = FeedbackSeverity.NEEDS_WORK.is_positive
        _ = FeedbackSeverity.ACCEPTABLE.is_positive
        _ = FeedbackSeverity.GOOD.is_positive
        _ = FeedbackSeverity.EXCELLENT.is_positive
    elapsed_positive = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FeedbackSeverity.is_positive (100K x 5종)", elapsed_positive, 500.0)

    # priority_weight 프로퍼티 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = FeedbackSeverity.CRITICAL.priority_weight
        _ = FeedbackSeverity.NEEDS_WORK.priority_weight
        _ = FeedbackSeverity.ACCEPTABLE.priority_weight
        _ = FeedbackSeverity.GOOD.priority_weight
        _ = FeedbackSeverity.EXCELLENT.priority_weight
    elapsed_weight = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FeedbackSeverity.priority_weight (100K x 5종)", elapsed_weight, 500.0)


# =============================================================================
# [H] FEEDBACK_CATEGORY_PRIORITY dict 조회 (100K < 500ms)
# =============================================================================
def test_h_category_priority_lookup(r: PerfResult) -> None:
    """FEEDBACK_CATEGORY_PRIORITY 딕셔너리 조회 (100K iterations < 500ms)"""
    from shared.constants.feedback_constants import (
        FeedbackCategory,
        FEEDBACK_CATEGORY_PRIORITY,
    )

    iterations = 100_000

    # 단일 키 조회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = FEEDBACK_CATEGORY_PRIORITY[FeedbackCategory.GAME_OVERALL]
    elapsed_single = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FEEDBACK_CATEGORY_PRIORITY 단일 키 조회 (100K)", elapsed_single, 500.0)

    # 전체 카테고리 순회 조회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for cat in FeedbackCategory:
            _ = FEEDBACK_CATEGORY_PRIORITY[cat]
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("FEEDBACK_CATEGORY_PRIORITY 전체 키 순회 (100K x 8종)", elapsed_all, 500.0)


# =============================================================================
# [I] get_feedback_severity_from_percentile 함수 (50K < 300ms)
# =============================================================================
def test_i_severity_from_percentile(r: PerfResult) -> None:
    """get_feedback_severity_from_percentile 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.feedback_constants import get_feedback_severity_from_percentile

    iterations = 50_000

    # 다양한 백분위 입력으로 함수 호출
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_feedback_severity_from_percentile(95.0)
        _ = get_feedback_severity_from_percentile(75.0)
        _ = get_feedback_severity_from_percentile(50.0)
        _ = get_feedback_severity_from_percentile(25.0)
        _ = get_feedback_severity_from_percentile(5.0)
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_feedback_severity_from_percentile (50K x 5개 백분위)", elapsed_ms, 300.0)

    # 경계값 집중 테스트
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_feedback_severity_from_percentile(90.0)
        _ = get_feedback_severity_from_percentile(70.0)
        _ = get_feedback_severity_from_percentile(40.0)
        _ = get_feedback_severity_from_percentile(15.0)
        _ = get_feedback_severity_from_percentile(0.0)
    elapsed_boundary = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_feedback_severity_from_percentile 경계값 (50K x 5개)", elapsed_boundary, 300.0)


# =============================================================================
# [J] estimate_film_session_duration_min 함수 (50K < 300ms)
# =============================================================================
def test_j_film_session_duration(r: PerfResult) -> None:
    """estimate_film_session_duration_min 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.feedback_constants import estimate_film_session_duration_min

    iterations = 50_000

    # 다양한 클립 수 입력으로 함수 호출
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = estimate_film_session_duration_min(1)
        _ = estimate_film_session_duration_min(10)
        _ = estimate_film_session_duration_min(25)
        _ = estimate_film_session_duration_min(50)
        _ = estimate_film_session_duration_min(100)
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("estimate_film_session_duration_min (50K x 5개 클립수)", elapsed_ms, 300.0)

    # 경계값 집중 테스트 (0 클립, MAX 클립, 초과 클립)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = estimate_film_session_duration_min(0)
        _ = estimate_film_session_duration_min(50)
        _ = estimate_film_session_duration_min(150)
    elapsed_boundary = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("estimate_film_session_duration_min 경계값 (50K x 3개)", elapsed_boundary, 300.0)


# =============================================================================
# [K] 메모리 사용량 (모듈 객체 < 1MB)
# =============================================================================
def test_k_memory_footprint(r: PerfResult) -> None:
    """모듈 내 주요 객체 메모리 사용량 (< 1MB = 1024KB)"""
    import sys as _sys
    from shared.constants.feedback_constants import (
        # Enum 클래스
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
        # 리포트 섹션
        SINGLE_GAME_REPORT_SECTIONS,
        REPORT_SECTION_MAX_ITEMS,
        REPORT_KEY_PLAYERS_COUNT,
        REPORT_TOP_N_DEFAULT,
        # 시각 피드백
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
        # 필름 세션
        FILM_SESSION_AVG_CLIP_REVIEW_SEC,
        FILM_SESSION_MAX_CLIPS,
        # 성장 추세
        GROWTH_MIN_GAMES,
        GROWTH_IMPROVING_SLOPE,
        GROWTH_DECLINING_SLOPE,
        REPEATED_MISTAKE_MIN_GAMES,
        IMPROVEMENT_PRIORITY_TOP_N,
    )

    sizes: dict[str, int] = {
        # Enum 클래스
        "FeedbackSeverity (Enum)": _sys.getsizeof(FeedbackSeverity),
        "FeedbackCategory (Enum)": _sys.getsizeof(FeedbackCategory),
        "ReportType (Enum)": _sys.getsizeof(ReportType),
        "ReportOutputFormat (Enum)": _sys.getsizeof(ReportOutputFormat),
        # 피드백 품질 상수
        "FEEDBACK_MIN_DETAIL_POINTS": _sys.getsizeof(FEEDBACK_MIN_DETAIL_POINTS),
        "FEEDBACK_POSITIVE_RATIO_MIN": _sys.getsizeof(FEEDBACK_POSITIVE_RATIO_MIN),
        "FEEDBACK_POSITIVE_RATIO_MAX": _sys.getsizeof(FEEDBACK_POSITIVE_RATIO_MAX),
        "FEEDBACK_MAX_LENGTH_CHARS": _sys.getsizeof(FEEDBACK_MAX_LENGTH_CHARS),
        "FEEDBACK_MIN_LENGTH_CHARS": _sys.getsizeof(FEEDBACK_MIN_LENGTH_CHARS),
        "FEEDBACK_CATEGORY_PRIORITY": _sys.getsizeof(FEEDBACK_CATEGORY_PRIORITY),
        # 리포트 섹션
        "SINGLE_GAME_REPORT_SECTIONS": _sys.getsizeof(SINGLE_GAME_REPORT_SECTIONS),
        "REPORT_SECTION_MAX_ITEMS": _sys.getsizeof(REPORT_SECTION_MAX_ITEMS),
        "REPORT_KEY_PLAYERS_COUNT": _sys.getsizeof(REPORT_KEY_PLAYERS_COUNT),
        "REPORT_TOP_N_DEFAULT": _sys.getsizeof(REPORT_TOP_N_DEFAULT),
        # 시각 피드백
        "HEATMAP_GRID_X": _sys.getsizeof(HEATMAP_GRID_X),
        "HEATMAP_GRID_Y": _sys.getsizeof(HEATMAP_GRID_Y),
        "COURT_DIAGRAM_WIDTH_PX": _sys.getsizeof(COURT_DIAGRAM_WIDTH_PX),
        "COURT_DIAGRAM_HEIGHT_PX": _sys.getsizeof(COURT_DIAGRAM_HEIGHT_PX),
        "SHOT_CHART_MARKER_SIZE_MADE": _sys.getsizeof(SHOT_CHART_MARKER_SIZE_MADE),
        "SHOT_CHART_MARKER_SIZE_MISSED": _sys.getsizeof(SHOT_CHART_MARKER_SIZE_MISSED),
        "TIME_SERIES_MIN_POINTS": _sys.getsizeof(TIME_SERIES_MIN_POINTS),
        "OVERLAY_OPACITY_DEFAULT": _sys.getsizeof(OVERLAY_OPACITY_DEFAULT),
        "OVERLAY_OPACITY_HIGHLIGHT": _sys.getsizeof(OVERLAY_OPACITY_HIGHLIGHT),
        "ANNOTATION_ARROW_WIDTH_PX": _sys.getsizeof(ANNOTATION_ARROW_WIDTH_PX),
        # 필름 세션
        "FILM_SESSION_AVG_CLIP_REVIEW_SEC": _sys.getsizeof(FILM_SESSION_AVG_CLIP_REVIEW_SEC),
        "FILM_SESSION_MAX_CLIPS": _sys.getsizeof(FILM_SESSION_MAX_CLIPS),
        # 성장 추세
        "GROWTH_MIN_GAMES": _sys.getsizeof(GROWTH_MIN_GAMES),
        "GROWTH_IMPROVING_SLOPE": _sys.getsizeof(GROWTH_IMPROVING_SLOPE),
        "GROWTH_DECLINING_SLOPE": _sys.getsizeof(GROWTH_DECLINING_SLOPE),
        "REPEATED_MISTAKE_MIN_GAMES": _sys.getsizeof(REPEATED_MISTAKE_MIN_GAMES),
        "IMPROVEMENT_PRIORITY_TOP_N": _sys.getsizeof(IMPROVEMENT_PRIORITY_TOP_N),
    }

    total_bytes = sum(sizes.values())
    total_kb = total_bytes / 1024
    limit_kb = 1024.0  # 1MB

    print(f"\n  메모리 사용량 (주요 객체):")
    for name, size_bytes in sizes.items():
        print(f"    {name}: {size_bytes} bytes")
    print(f"    {'─' * 40}")
    print(f"    합계: {total_bytes} bytes ({total_kb:.2f}KB)")

    r.check_memory("모듈 주요 객체 메모리 합계", total_kb, limit_kb)

    # tracemalloc 기반 모듈 전체 메모리 측정
    import importlib
    import tracemalloc

    mod_name = "shared.constants.feedback_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    tracemalloc.start()
    importlib.import_module(mod_name)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_kb = peak / 1024
    print(f"\n  tracemalloc 모듈 메모리:")
    print(f"    현재: {current / 1024:.2f}KB")
    print(f"    피크: {peak_kb:.2f}KB")

    r.check_memory("tracemalloc 피크 메모리", peak_kb, limit_kb)


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> int:
    """모든 feedback_constants 성능 테스트 실행."""
    r = PerfResult()

    print("\n" + "=" * 60)
    print("feedback_constants.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- [A] 모듈 임포트 시간 ---")
    test_a_import_time(r)

    print("\n--- [B] FeedbackSeverity Enum 멤버 접근 ---")
    test_b_feedback_severity_access(r)

    print("\n--- [C] FeedbackCategory Enum 멤버 접근 ---")
    test_c_feedback_category_access(r)

    print("\n--- [D] ReportType Enum 멤버 접근 ---")
    test_d_report_type_access(r)

    print("\n--- [E] ReportOutputFormat Enum 멤버 접근 ---")
    test_e_report_output_format_access(r)

    print("\n--- [F] Enum i18n get_name() ---")
    test_f_enum_i18n_get_name(r)

    print("\n--- [G] FeedbackSeverity property 접근 (is_positive, priority_weight) ---")
    test_g_severity_property_access(r)

    print("\n--- [H] FEEDBACK_CATEGORY_PRIORITY dict 조회 ---")
    test_h_category_priority_lookup(r)

    print("\n--- [I] get_feedback_severity_from_percentile 함수 ---")
    test_i_severity_from_percentile(r)

    print("\n--- [J] estimate_film_session_duration_min 함수 ---")
    test_j_film_session_duration(r)

    print("\n--- [K] 메모리 사용량 ---")
    test_k_memory_footprint(r)

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
