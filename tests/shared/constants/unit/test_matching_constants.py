# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_matching_constants.py

객체 매칭 상수 모듈 유닛 테스트
- 기본 매칭 가중치: 값, 타입, 합계 검증
- 에피폴라 기하학 임계값: 값, 타입, 순서 관계
- 외관 유사도 임계값: 값, 범위, 순서
- 위치 기반 매칭 임계값: 값, 논리 관계
- 헝가리안 알고리즘 파라미터: 값, 타입
- 크로스뷰 매칭 파라미터: 값, 가중치 합
- 시간적 매칭 파라미터: 값, 타입
- 객체 유형별 매칭 가중치: 튜플 합계 검증
- 농구 경기 특화 파라미터: 값, 논리 관계
- 매칭 품질/신뢰도 임계값: 값, 순서 관계
- 배치 매칭 파라미터: 값, 논리 관계
- 비용 행렬 파라미터: 값, 가중치 합
- MatchingStrategy: 멤버, is_optimal, supports_partial_matching, default_threshold, to_korean
- MatchingStatus: 멤버, is_successful, needs_resolution, can_retry, to_korean
- MatchingTargetType: 멤버, matching_weights, appearance_threshold, to_korean
- __all__ export 완전성
- 에지 케이스

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
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


# ==================== 1. MatchingStrategy 기본 ====================
def test_matching_strategy_basics(r: TestResult) -> None:
    print("\n[1] MatchingStrategy 기본")
    from enum import unique
    from shared.constants.matching_constants import MatchingStrategy

    # 멤버 수
    r.check("7개 멤버", len(MatchingStrategy) == 7)

    # 각 멤버의 이름과 값
    expected = {
        "HUNGARIAN": "hungarian",
        "GREEDY": "greedy",
        "AUCTION": "auction",
        "EPIPOLAR_FIRST": "epipolar_first",
        "APPEARANCE_FIRST": "appearance_first",
        "FUSION": "fusion",
        "HIERARCHICAL": "hierarchical",
    }
    for name, value in expected.items():
        member = MatchingStrategy[name]
        r.check(f"{name} = '{value}'", member.value == value)

    # Enum 타입 확인
    from enum import Enum
    r.check("Enum 서브클래스", issubclass(MatchingStrategy, Enum))

    # @unique 적용 확인 (중복 값 불가 검증)
    values = [m.value for m in MatchingStrategy]
    r.check("@unique (중복 값 없음)", len(values) == len(set(values)))


# ==================== 2. MatchingStrategy.is_optimal ====================
def test_matching_strategy_is_optimal(r: TestResult) -> None:
    print("\n[2] MatchingStrategy.is_optimal")
    from shared.constants.matching_constants import MatchingStrategy

    # 최적해 보장: HUNGARIAN, AUCTION
    optimal = {
        MatchingStrategy.HUNGARIAN: True,
        MatchingStrategy.AUCTION: True,
        MatchingStrategy.GREEDY: False,
        MatchingStrategy.EPIPOLAR_FIRST: False,
        MatchingStrategy.APPEARANCE_FIRST: False,
        MatchingStrategy.FUSION: False,
        MatchingStrategy.HIERARCHICAL: False,
    }
    for member, expected in optimal.items():
        r.check(f"{member.name}.is_optimal = {expected}",
                member.is_optimal == expected)

    # 최적해 멤버 수 = 2
    optimal_count = sum(1 for m in MatchingStrategy if m.is_optimal)
    r.check("최적해 멤버 2개", optimal_count == 2)


# ==================== 3. MatchingStrategy.supports_partial_matching ====================
def test_matching_strategy_supports_partial(r: TestResult) -> None:
    print("\n[3] MatchingStrategy.supports_partial_matching")
    from shared.constants.matching_constants import MatchingStrategy

    partial = {
        MatchingStrategy.GREEDY: True,
        MatchingStrategy.HIERARCHICAL: True,
        MatchingStrategy.FUSION: True,
        MatchingStrategy.HUNGARIAN: False,
        MatchingStrategy.AUCTION: False,
        MatchingStrategy.EPIPOLAR_FIRST: False,
        MatchingStrategy.APPEARANCE_FIRST: False,
    }
    for member, expected in partial.items():
        r.check(f"{member.name}.supports_partial = {expected}",
                member.supports_partial_matching == expected)

    # 부분 매칭 지원 멤버 수 = 3
    partial_count = sum(1 for m in MatchingStrategy if m.supports_partial_matching)
    r.check("부분 매칭 지원 멤버 3개", partial_count == 3)


# ==================== 4. MatchingStrategy.default_threshold ====================
def test_matching_strategy_default_threshold(r: TestResult) -> None:
    print("\n[4] MatchingStrategy.default_threshold")
    from shared.constants.matching_constants import MatchingStrategy

    thresholds = {
        MatchingStrategy.HUNGARIAN: 0.7,
        MatchingStrategy.GREEDY: 0.6,
        MatchingStrategy.AUCTION: 0.7,
        MatchingStrategy.EPIPOLAR_FIRST: 0.65,
        MatchingStrategy.APPEARANCE_FIRST: 0.7,
        MatchingStrategy.FUSION: 0.65,
        MatchingStrategy.HIERARCHICAL: 0.6,
    }
    for member, expected in thresholds.items():
        val = member.default_threshold
        r.check(f"{member.name}.default_threshold = {expected}",
                abs(val - expected) < 1e-9)
        r.check(f"{member.name}.default_threshold float",
                isinstance(val, float))
        r.check(f"{member.name}.default_threshold 0 < x <= 1",
                0.0 < val <= 1.0)


# ==================== 5. MatchingStrategy.to_korean ====================
def test_matching_strategy_korean(r: TestResult) -> None:
    print("\n[5] MatchingStrategy.to_korean")
    from shared.constants.matching_constants import MatchingStrategy

    korean = {
        MatchingStrategy.HUNGARIAN: "헝가리안 알고리즘",
        MatchingStrategy.GREEDY: "그리디 매칭",
        MatchingStrategy.AUCTION: "경매 알고리즘",
        MatchingStrategy.EPIPOLAR_FIRST: "에피폴라 우선",
        MatchingStrategy.APPEARANCE_FIRST: "외관 우선",
        MatchingStrategy.FUSION: "융합 매칭",
        MatchingStrategy.HIERARCHICAL: "계층적 매칭",
    }
    for member, expected_kr in korean.items():
        r.check(f"{member.name} -> '{expected_kr}'",
                member.to_korean() == expected_kr)
        # 반환 타입 확인
        r.check(f"{member.name}.to_korean() str 타입",
                isinstance(member.to_korean(), str))


# ==================== 6. MatchingStatus 기본 ====================
def test_matching_status_basics(r: TestResult) -> None:
    print("\n[6] MatchingStatus 기본")
    from shared.constants.matching_constants import MatchingStatus
    from enum import Enum

    # 멤버 수
    r.check("7개 멤버", len(MatchingStatus) == 7)

    # 각 멤버의 이름과 값
    expected = {
        "MATCHED": "matched",
        "UNMATCHED": "unmatched",
        "AMBIGUOUS": "ambiguous",
        "CONFLICTED": "conflicted",
        "BELOW_THRESHOLD": "below_threshold",
        "GEOMETRY_VIOLATED": "geometry_violated",
        "TEMPORAL_INCONSISTENT": "temporal_inconsistent",
    }
    for name, value in expected.items():
        member = MatchingStatus[name]
        r.check(f"{name} = '{value}'", member.value == value)

    # Enum 타입 확인
    r.check("Enum 서브클래스", issubclass(MatchingStatus, Enum))

    # @unique 적용 확인
    values = [m.value for m in MatchingStatus]
    r.check("@unique (중복 값 없음)", len(values) == len(set(values)))


# ==================== 7. MatchingStatus 속성 ====================
def test_matching_status_properties(r: TestResult) -> None:
    print("\n[7] MatchingStatus 속성")
    from shared.constants.matching_constants import MatchingStatus

    # is_successful: MATCHED만 True
    for member in MatchingStatus:
        expected = (member == MatchingStatus.MATCHED)
        r.check(f"{member.name}.is_successful = {expected}",
                member.is_successful == expected)

    # needs_resolution: AMBIGUOUS, CONFLICTED
    needs_resolution = {
        MatchingStatus.MATCHED: False,
        MatchingStatus.UNMATCHED: False,
        MatchingStatus.AMBIGUOUS: True,
        MatchingStatus.CONFLICTED: True,
        MatchingStatus.BELOW_THRESHOLD: False,
        MatchingStatus.GEOMETRY_VIOLATED: False,
        MatchingStatus.TEMPORAL_INCONSISTENT: False,
    }
    for member, expected in needs_resolution.items():
        r.check(f"{member.name}.needs_resolution = {expected}",
                member.needs_resolution == expected)

    # can_retry: BELOW_THRESHOLD, TEMPORAL_INCONSISTENT
    can_retry = {
        MatchingStatus.MATCHED: False,
        MatchingStatus.UNMATCHED: False,
        MatchingStatus.AMBIGUOUS: False,
        MatchingStatus.CONFLICTED: False,
        MatchingStatus.BELOW_THRESHOLD: True,
        MatchingStatus.GEOMETRY_VIOLATED: False,
        MatchingStatus.TEMPORAL_INCONSISTENT: True,
    }
    for member, expected in can_retry.items():
        r.check(f"{member.name}.can_retry = {expected}",
                member.can_retry == expected)

    # needs_resolution 멤버 수 = 2
    nr_count = sum(1 for m in MatchingStatus if m.needs_resolution)
    r.check("needs_resolution 멤버 2개", nr_count == 2)

    # can_retry 멤버 수 = 2
    cr_count = sum(1 for m in MatchingStatus if m.can_retry)
    r.check("can_retry 멤버 2개", cr_count == 2)


# ==================== 8. MatchingStatus.to_korean ====================
def test_matching_status_korean(r: TestResult) -> None:
    print("\n[8] MatchingStatus.to_korean")
    from shared.constants.matching_constants import MatchingStatus

    korean = {
        MatchingStatus.MATCHED: "매칭됨",
        MatchingStatus.UNMATCHED: "매칭 없음",
        MatchingStatus.AMBIGUOUS: "모호함",
        MatchingStatus.CONFLICTED: "충돌",
        MatchingStatus.BELOW_THRESHOLD: "임계값 미달",
        MatchingStatus.GEOMETRY_VIOLATED: "기하학 위반",
        MatchingStatus.TEMPORAL_INCONSISTENT: "시간적 불일치",
    }
    for member, expected_kr in korean.items():
        r.check(f"{member.name} -> '{expected_kr}'",
                member.to_korean() == expected_kr)


# ==================== 9. MatchingTargetType 기본 ====================
def test_matching_target_type_basics(r: TestResult) -> None:
    print("\n[9] MatchingTargetType 기본")
    from shared.constants.matching_constants import MatchingTargetType
    from enum import Enum

    # 멤버 수
    r.check("6개 멤버", len(MatchingTargetType) == 6)

    # 각 멤버의 이름과 값
    expected = {
        "PLAYER": "player",
        "BALL": "ball",
        "REFEREE": "referee",
        "COACH": "coach",
        "PERSON": "person",
        "OTHER": "other",
    }
    for name, value in expected.items():
        member = MatchingTargetType[name]
        r.check(f"{name} = '{value}'", member.value == value)

    # Enum 타입
    r.check("Enum 서브클래스", issubclass(MatchingTargetType, Enum))

    # @unique 적용 확인
    values = [m.value for m in MatchingTargetType]
    r.check("@unique (중복 값 없음)", len(values) == len(set(values)))


# ==================== 10. MatchingTargetType.matching_weights ====================
def test_matching_target_type_weights(r: TestResult) -> None:
    print("\n[10] MatchingTargetType.matching_weights")
    from shared.constants.matching_constants import MatchingTargetType

    weights = {
        MatchingTargetType.PLAYER: (0.35, 0.45, 0.20),
        MatchingTargetType.BALL: (0.15, 0.60, 0.25),
        MatchingTargetType.REFEREE: (0.40, 0.40, 0.20),
        MatchingTargetType.COACH: (0.35, 0.45, 0.20),
        MatchingTargetType.PERSON: (0.30, 0.50, 0.20),
        MatchingTargetType.OTHER: (0.20, 0.60, 0.20),
    }
    for member, expected in weights.items():
        w = member.matching_weights
        r.check(f"{member.name}.matching_weights = {expected}",
                all(abs(a - b) < 1e-9 for a, b in zip(w, expected)))
        # 튜플 길이 = 3
        r.check(f"{member.name} 튜플 길이 3", len(w) == 3)
        # 합계 = 1.0
        r.check(f"{member.name} 가중치 합 = 1.0",
                abs(sum(w) - 1.0) < 1e-9,
                f"실제 합: {sum(w)}")
        # 타입
        r.check(f"{member.name} tuple 타입", isinstance(w, tuple))


# ==================== 11. MatchingTargetType.appearance_threshold ====================
def test_matching_target_type_appearance(r: TestResult) -> None:
    print("\n[11] MatchingTargetType.appearance_threshold")
    from shared.constants.matching_constants import MatchingTargetType

    thresholds = {
        MatchingTargetType.PLAYER: 0.65,
        MatchingTargetType.BALL: 0.50,
        MatchingTargetType.REFEREE: 0.70,
        MatchingTargetType.COACH: 0.65,
        MatchingTargetType.PERSON: 0.60,
        MatchingTargetType.OTHER: 0.55,
    }
    for member, expected in thresholds.items():
        val = member.appearance_threshold
        r.check(f"{member.name}.appearance_threshold = {expected}",
                abs(val - expected) < 1e-9)
        r.check(f"{member.name} float 타입", isinstance(val, float))
        r.check(f"{member.name} 0 < x <= 1", 0.0 < val <= 1.0)


# ==================== 12. MatchingTargetType.to_korean ====================
def test_matching_target_type_korean(r: TestResult) -> None:
    print("\n[12] MatchingTargetType.to_korean")
    from shared.constants.matching_constants import MatchingTargetType

    korean = {
        MatchingTargetType.PLAYER: "선수",
        MatchingTargetType.BALL: "농구공",
        MatchingTargetType.REFEREE: "심판",
        MatchingTargetType.COACH: "코치",
        MatchingTargetType.PERSON: "일반인",
        MatchingTargetType.OTHER: "기타",
    }
    for member, expected_kr in korean.items():
        r.check(f"{member.name} -> '{expected_kr}'",
                member.to_korean() == expected_kr)


# ==================== 13. 기본 매칭 가중치 상수 ====================
def test_basic_weight_constants(r: TestResult) -> None:
    print("\n[13] 기본 매칭 가중치 상수")
    from shared.constants.matching_constants import (
        APPEARANCE_WEIGHT, GEOMETRY_WEIGHT, POSITION_WEIGHT,
    )

    # 값 검증
    r.check("APPEARANCE_WEIGHT = 0.3", abs(APPEARANCE_WEIGHT - 0.3) < 1e-9)
    r.check("GEOMETRY_WEIGHT = 0.5", abs(GEOMETRY_WEIGHT - 0.5) < 1e-9)
    r.check("POSITION_WEIGHT = 0.2", abs(POSITION_WEIGHT - 0.2) < 1e-9)

    # 타입 검증
    r.check("APPEARANCE_WEIGHT float", isinstance(APPEARANCE_WEIGHT, float))
    r.check("GEOMETRY_WEIGHT float", isinstance(GEOMETRY_WEIGHT, float))
    r.check("POSITION_WEIGHT float", isinstance(POSITION_WEIGHT, float))

    # 합계 = 1.0 (모듈 내 assert와 동일 검증)
    total = APPEARANCE_WEIGHT + GEOMETRY_WEIGHT + POSITION_WEIGHT
    r.check("기본 가중치 합 = 1.0", abs(total - 1.0) < 1e-9,
            f"실제 합: {total}")

    # 기하학이 가장 큰 가중치
    r.check("GEOMETRY > APPEARANCE > POSITION",
            GEOMETRY_WEIGHT > APPEARANCE_WEIGHT > POSITION_WEIGHT)


# ==================== 14. 나머지 전체 상수 ====================
def test_all_remaining_constants(r: TestResult) -> None:
    print("\n[14] 나머지 전체 상수")
    from shared.constants.matching_constants import (
        # 에피폴라 기하학 임계값
        DEFAULT_EPIPOLAR_THRESHOLD, STRICT_EPIPOLAR_THRESHOLD,
        RELAXED_EPIPOLAR_THRESHOLD, MAX_EPIPOLAR_DISTANCE,
        EPIPOLAR_LINE_SAMPLES,
        # 외관 유사도 임계값
        DEFAULT_APPEARANCE_THRESHOLD, HIGH_APPEARANCE_THRESHOLD,
        LOW_APPEARANCE_THRESHOLD, IDENTITY_APPEARANCE_THRESHOLD,
        COLOR_HISTOGRAM_THRESHOLD, TEXTURE_SIMILARITY_THRESHOLD,
        # 위치 기반 매칭 임계값
        POSITION_2D_THRESHOLD, POSITION_3D_THRESHOLD,
        POSITION_3D_STRICT_THRESHOLD, VELOCITY_PREDICTION_WEIGHT,
        MAX_POSITION_PREDICTION_FRAMES,
        # 헝가리안 알고리즘 파라미터
        HUNGARIAN_MAX_COST, HUNGARIAN_COST_SCALE,
        MIN_MATCHING_COST_THRESHOLD, OPTIMAL_ASSIGNMENT_MAX_ITER,
        # 크로스뷰 매칭 파라미터
        CROSS_VIEW_MIN_CAMERAS, CROSS_VIEW_CONSISTENCY_RATIO,
        CROSS_VIEW_MAX_CANDIDATES, CROSS_VIEW_VOTE_WEIGHT_QUALITY,
        CROSS_VIEW_VOTE_WEIGHT_DISTANCE,
        # 시간적 매칭 파라미터
        TEMPORAL_MATCHING_WINDOW, TEMPORAL_SYNC_TOLERANCE_MS,
        TEMPORAL_CONSISTENCY_WEIGHT, MAX_FRAME_TIME_DIFF,
        # 객체 유형별 매칭 가중치
        PLAYER_MATCHING_WEIGHTS, BALL_MATCHING_WEIGHTS,
        REFEREE_MATCHING_WEIGHTS,
        # 농구 경기 특화 파라미터
        SAME_TEAM_APPEARANCE_BOOST, DIFFERENT_TEAM_APPEARANCE_PENALTY,
        JERSEY_NUMBER_MATCH_BONUS, JERSEY_NUMBER_MISMATCH_PENALTY,
        COURT_ZONE_MATCHING_WEIGHT,
        # 매칭 품질 및 신뢰도 임계값
        MIN_MATCH_CONFIDENCE, HIGH_MATCH_CONFIDENCE,
        AMBIGUOUS_MATCH_DIFF, CONFIRMED_MATCH_CONFIDENCE,
        MATCH_CACHE_VALIDITY_FRAMES,
        # 배치 매칭 파라미터
        BATCH_MATCHING_MAX_OBJECTS, BATCH_MATCHING_CHUNK_SIZE,
        PARALLEL_MATCHING_THREADS,
        # 비용 행렬 계산 파라미터
        COST_MATRIX_APPEARANCE_WEIGHT, COST_MATRIX_GEOMETRY_WEIGHT,
        COST_MATRIX_TEMPORAL_WEIGHT, COST_NORMALIZATION_EPS,
    )

    # --- 에피폴라 기하학 임계값 ---
    print("  [에피폴라 기하학]")
    r.check("DEFAULT_EPIPOLAR = 3.0", abs(DEFAULT_EPIPOLAR_THRESHOLD - 3.0) < 1e-9)
    r.check("STRICT_EPIPOLAR = 1.5", abs(STRICT_EPIPOLAR_THRESHOLD - 1.5) < 1e-9)
    r.check("RELAXED_EPIPOLAR = 5.0", abs(RELAXED_EPIPOLAR_THRESHOLD - 5.0) < 1e-9)
    r.check("MAX_EPIPOLAR = 10.0", abs(MAX_EPIPOLAR_DISTANCE - 10.0) < 1e-9)
    r.check("EPIPOLAR_SAMPLES = 100", EPIPOLAR_LINE_SAMPLES == 100)
    r.check("EPIPOLAR_SAMPLES int", isinstance(EPIPOLAR_LINE_SAMPLES, int))
    # 순서: STRICT < DEFAULT < RELAXED < MAX
    r.check("STRICT < DEFAULT < RELAXED < MAX",
            STRICT_EPIPOLAR_THRESHOLD < DEFAULT_EPIPOLAR_THRESHOLD
            < RELAXED_EPIPOLAR_THRESHOLD < MAX_EPIPOLAR_DISTANCE)

    # --- 외관 유사도 임계값 ---
    print("  [외관 유사도]")
    r.check("DEFAULT_APPEARANCE = 0.7", abs(DEFAULT_APPEARANCE_THRESHOLD - 0.7) < 1e-9)
    r.check("HIGH_APPEARANCE = 0.85", abs(HIGH_APPEARANCE_THRESHOLD - 0.85) < 1e-9)
    r.check("LOW_APPEARANCE = 0.5", abs(LOW_APPEARANCE_THRESHOLD - 0.5) < 1e-9)
    r.check("IDENTITY_APPEARANCE = 0.95", abs(IDENTITY_APPEARANCE_THRESHOLD - 0.95) < 1e-9)
    r.check("COLOR_HISTOGRAM = 0.6", abs(COLOR_HISTOGRAM_THRESHOLD - 0.6) < 1e-9)
    r.check("TEXTURE_SIMILARITY = 0.5", abs(TEXTURE_SIMILARITY_THRESHOLD - 0.5) < 1e-9)
    # 순서: LOW < COLOR <= DEFAULT < HIGH < IDENTITY
    r.check("LOW < COLOR <= DEFAULT < HIGH < IDENTITY",
            LOW_APPEARANCE_THRESHOLD < COLOR_HISTOGRAM_THRESHOLD
            <= DEFAULT_APPEARANCE_THRESHOLD < HIGH_APPEARANCE_THRESHOLD
            < IDENTITY_APPEARANCE_THRESHOLD)

    # --- 위치 기반 매칭 임계값 ---
    print("  [위치 기반]")
    r.check("POSITION_2D = 50.0", abs(POSITION_2D_THRESHOLD - 50.0) < 1e-9)
    r.check("POSITION_3D = 0.5", abs(POSITION_3D_THRESHOLD - 0.5) < 1e-9)
    r.check("POSITION_3D_STRICT = 0.2", abs(POSITION_3D_STRICT_THRESHOLD - 0.2) < 1e-9)
    r.check("VELOCITY_PREDICTION = 0.7", abs(VELOCITY_PREDICTION_WEIGHT - 0.7) < 1e-9)
    r.check("MAX_PREDICTION_FRAMES = 5", MAX_POSITION_PREDICTION_FRAMES == 5)
    r.check("MAX_PREDICTION_FRAMES int", isinstance(MAX_POSITION_PREDICTION_FRAMES, int))
    # STRICT < 3D
    r.check("POSITION_3D_STRICT < POSITION_3D",
            POSITION_3D_STRICT_THRESHOLD < POSITION_3D_THRESHOLD)

    # --- 헝가리안 알고리즘 파라미터 ---
    print("  [헝가리안 알고리즘]")
    r.check("HUNGARIAN_MAX_COST = 1e6", abs(HUNGARIAN_MAX_COST - 1e6) < 1e-3)
    r.check("HUNGARIAN_COST_SCALE = 1000.0", abs(HUNGARIAN_COST_SCALE - 1000.0) < 1e-9)
    r.check("MIN_MATCHING_COST = 0.8", abs(MIN_MATCHING_COST_THRESHOLD - 0.8) < 1e-9)
    r.check("OPTIMAL_MAX_ITER = 1000", OPTIMAL_ASSIGNMENT_MAX_ITER == 1000)
    r.check("OPTIMAL_MAX_ITER int", isinstance(OPTIMAL_ASSIGNMENT_MAX_ITER, int))
    r.check("HUNGARIAN_MAX_COST float", isinstance(HUNGARIAN_MAX_COST, float))
    r.check("HUNGARIAN_COST_SCALE float", isinstance(HUNGARIAN_COST_SCALE, float))

    # --- 크로스뷰 매칭 파라미터 ---
    print("  [크로스뷰 매칭]")
    r.check("CROSS_VIEW_MIN_CAMERAS = 2", CROSS_VIEW_MIN_CAMERAS == 2)
    r.check("CROSS_VIEW_MIN_CAMERAS int", isinstance(CROSS_VIEW_MIN_CAMERAS, int))
    r.check("CROSS_VIEW_CONSISTENCY = 0.7", abs(CROSS_VIEW_CONSISTENCY_RATIO - 0.7) < 1e-9)
    r.check("CROSS_VIEW_MAX_CANDIDATES = 5", CROSS_VIEW_MAX_CANDIDATES == 5)
    r.check("CROSS_VIEW_MAX_CANDIDATES int", isinstance(CROSS_VIEW_MAX_CANDIDATES, int))
    r.check("VOTE_WEIGHT_QUALITY = 0.6", abs(CROSS_VIEW_VOTE_WEIGHT_QUALITY - 0.6) < 1e-9)
    r.check("VOTE_WEIGHT_DISTANCE = 0.4", abs(CROSS_VIEW_VOTE_WEIGHT_DISTANCE - 0.4) < 1e-9)
    # QUALITY + DISTANCE = 1.0
    vote_sum = CROSS_VIEW_VOTE_WEIGHT_QUALITY + CROSS_VIEW_VOTE_WEIGHT_DISTANCE
    r.check("QUALITY + DISTANCE = 1.0", abs(vote_sum - 1.0) < 1e-9,
            f"실제 합: {vote_sum}")

    # --- 시간적 매칭 파라미터 ---
    print("  [시간적 매칭]")
    r.check("TEMPORAL_WINDOW = 10", TEMPORAL_MATCHING_WINDOW == 10)
    r.check("TEMPORAL_WINDOW int", isinstance(TEMPORAL_MATCHING_WINDOW, int))
    r.check("TEMPORAL_SYNC = 33.0ms", abs(TEMPORAL_SYNC_TOLERANCE_MS - 33.0) < 1e-9)
    r.check("TEMPORAL_CONSISTENCY = 0.3", abs(TEMPORAL_CONSISTENCY_WEIGHT - 0.3) < 1e-9)
    r.check("MAX_FRAME_TIME_DIFF = 0.1", abs(MAX_FRAME_TIME_DIFF - 0.1) < 1e-9)

    # --- 객체 유형별 매칭 가중치 ---
    print("  [객체 유형별 가중치]")
    r.check("PLAYER_WEIGHTS = (0.35, 0.45, 0.20)",
            all(abs(a - b) < 1e-9 for a, b in
                zip(PLAYER_MATCHING_WEIGHTS, (0.35, 0.45, 0.20))))
    r.check("BALL_WEIGHTS = (0.15, 0.60, 0.25)",
            all(abs(a - b) < 1e-9 for a, b in
                zip(BALL_MATCHING_WEIGHTS, (0.15, 0.60, 0.25))))
    r.check("REFEREE_WEIGHTS = (0.40, 0.40, 0.20)",
            all(abs(a - b) < 1e-9 for a, b in
                zip(REFEREE_MATCHING_WEIGHTS, (0.40, 0.40, 0.20))))
    # 각 튜플 합 = 1.0
    for name, weights in [("PLAYER", PLAYER_MATCHING_WEIGHTS),
                          ("BALL", BALL_MATCHING_WEIGHTS),
                          ("REFEREE", REFEREE_MATCHING_WEIGHTS)]:
        r.check(f"{name}_WEIGHTS 합 = 1.0",
                abs(sum(weights) - 1.0) < 1e-9,
                f"실제 합: {sum(weights)}")
        r.check(f"{name}_WEIGHTS tuple 타입", isinstance(weights, tuple))
        r.check(f"{name}_WEIGHTS 길이 3", len(weights) == 3)

    # --- 농구 경기 특화 파라미터 ---
    print("  [농구 경기 특화]")
    r.check("SAME_TEAM_BOOST = 0.1", abs(SAME_TEAM_APPEARANCE_BOOST - 0.1) < 1e-9)
    r.check("DIFFERENT_TEAM_PENALTY = 0.2", abs(DIFFERENT_TEAM_APPEARANCE_PENALTY - 0.2) < 1e-9)
    r.check("JERSEY_MATCH_BONUS = 0.3", abs(JERSEY_NUMBER_MATCH_BONUS - 0.3) < 1e-9)
    r.check("JERSEY_MISMATCH_PENALTY = 0.5", abs(JERSEY_NUMBER_MISMATCH_PENALTY - 0.5) < 1e-9)
    r.check("COURT_ZONE_WEIGHT = 0.1", abs(COURT_ZONE_MATCHING_WEIGHT - 0.1) < 1e-9)
    # MISMATCH > BONUS (불일치 페널티가 일치 보너스보다 엄격)
    r.check("MISMATCH_PENALTY > MATCH_BONUS",
            JERSEY_NUMBER_MISMATCH_PENALTY > JERSEY_NUMBER_MATCH_BONUS)

    # --- 매칭 품질 및 신뢰도 임계값 ---
    print("  [매칭 품질/신뢰도]")
    r.check("MIN_CONFIDENCE = 0.5", abs(MIN_MATCH_CONFIDENCE - 0.5) < 1e-9)
    r.check("HIGH_CONFIDENCE = 0.85", abs(HIGH_MATCH_CONFIDENCE - 0.85) < 1e-9)
    r.check("AMBIGUOUS_DIFF = 0.1", abs(AMBIGUOUS_MATCH_DIFF - 0.1) < 1e-9)
    r.check("CONFIRMED_CONFIDENCE = 0.9", abs(CONFIRMED_MATCH_CONFIDENCE - 0.9) < 1e-9)
    r.check("CACHE_VALIDITY = 5", MATCH_CACHE_VALIDITY_FRAMES == 5)
    r.check("CACHE_VALIDITY int", isinstance(MATCH_CACHE_VALIDITY_FRAMES, int))
    # MIN < HIGH < CONFIRMED
    r.check("MIN < HIGH < CONFIRMED",
            MIN_MATCH_CONFIDENCE < HIGH_MATCH_CONFIDENCE < CONFIRMED_MATCH_CONFIDENCE)

    # --- 배치 매칭 파라미터 ---
    print("  [배치 매칭]")
    r.check("BATCH_MAX = 100", BATCH_MATCHING_MAX_OBJECTS == 100)
    r.check("BATCH_MAX int", isinstance(BATCH_MATCHING_MAX_OBJECTS, int))
    r.check("BATCH_CHUNK = 20", BATCH_MATCHING_CHUNK_SIZE == 20)
    r.check("BATCH_CHUNK int", isinstance(BATCH_MATCHING_CHUNK_SIZE, int))
    r.check("PARALLEL_THREADS = 4", PARALLEL_MATCHING_THREADS == 4)
    r.check("PARALLEL_THREADS int", isinstance(PARALLEL_MATCHING_THREADS, int))
    # CHUNK < MAX
    r.check("CHUNK < MAX", BATCH_MATCHING_CHUNK_SIZE < BATCH_MATCHING_MAX_OBJECTS)

    # --- 비용 행렬 계산 파라미터 ---
    print("  [비용 행렬]")
    r.check("COST_APPEARANCE = 0.3", abs(COST_MATRIX_APPEARANCE_WEIGHT - 0.3) < 1e-9)
    r.check("COST_GEOMETRY = 0.4", abs(COST_MATRIX_GEOMETRY_WEIGHT - 0.4) < 1e-9)
    r.check("COST_TEMPORAL = 0.3", abs(COST_MATRIX_TEMPORAL_WEIGHT - 0.3) < 1e-9)
    r.check("COST_EPS = 1e-6", abs(COST_NORMALIZATION_EPS - 1e-6) < 1e-12)
    # 비용 행렬 가중치 합 = 1.0
    cost_sum = (COST_MATRIX_APPEARANCE_WEIGHT + COST_MATRIX_GEOMETRY_WEIGHT
                + COST_MATRIX_TEMPORAL_WEIGHT)
    r.check("비용 행렬 가중치 합 = 1.0", abs(cost_sum - 1.0) < 1e-9,
            f"실제 합: {cost_sum}")


# ==================== 15. __all__ export ====================
def test_all_exports(r: TestResult) -> None:
    print("\n[15] __all__ export")
    import shared.constants.matching_constants as module

    r.check("__all__ 존재", hasattr(module, "__all__"))
    r.check("__all__ 55개", len(module.__all__) == 55,
            f"실제: {len(module.__all__)}개")

    # 중복 없음
    r.check("__all__ 중복 없음", len(module.__all__) == len(set(module.__all__)))

    # 모든 export가 실제 존재
    for name in module.__all__:
        r.check(f"'{name}' 존재", hasattr(module, name))

    # 3개 Enum 포함 확인
    r.check("MatchingStrategy in __all__", "MatchingStrategy" in module.__all__)
    r.check("MatchingStatus in __all__", "MatchingStatus" in module.__all__)
    r.check("MatchingTargetType in __all__", "MatchingTargetType" in module.__all__)

    # __version__ 확인
    r.check("__version__ 존재", hasattr(module, "__version__"))
    r.check("__version__ = '1.1.0'", module.__version__ == "1.1.0")


# ==================== 16. 에지 케이스 ====================
def test_edge_cases(r: TestResult) -> None:
    print("\n[16] 에지 케이스")
    from shared.constants.matching_constants import (
        MatchingStrategy, MatchingStatus, MatchingTargetType,
        PLAYER_MATCHING_WEIGHTS, BALL_MATCHING_WEIGHTS, REFEREE_MATCHING_WEIGHTS,
    )

    # --- Enum identity ---
    r.check("MatchingStrategy identity (HUNGARIAN is HUNGARIAN)",
            MatchingStrategy.HUNGARIAN is MatchingStrategy.HUNGARIAN)
    r.check("MatchingStatus identity (MATCHED is MATCHED)",
            MatchingStatus.MATCHED is MatchingStatus.MATCHED)
    r.check("MatchingTargetType identity (PLAYER is PLAYER)",
            MatchingTargetType.PLAYER is MatchingTargetType.PLAYER)

    # --- Enum hashable ---
    d = {
        MatchingStrategy.HUNGARIAN: "hung",
        MatchingStatus.MATCHED: "ok",
        MatchingTargetType.PLAYER: "plr",
    }
    r.check("Strategy dict 키 사용", d[MatchingStrategy.HUNGARIAN] == "hung")
    r.check("Status dict 키 사용", d[MatchingStatus.MATCHED] == "ok")
    r.check("TargetType dict 키 사용", d[MatchingTargetType.PLAYER] == "plr")

    # --- Enum iteration order ---
    strategy_names = [m.name for m in MatchingStrategy]
    expected_order = ["HUNGARIAN", "GREEDY", "AUCTION", "EPIPOLAR_FIRST",
                      "APPEARANCE_FIRST", "FUSION", "HIERARCHICAL"]
    r.check("MatchingStrategy 순서 일치", strategy_names == expected_order)

    status_names = [m.name for m in MatchingStatus]
    expected_status_order = ["MATCHED", "UNMATCHED", "AMBIGUOUS", "CONFLICTED",
                             "BELOW_THRESHOLD", "GEOMETRY_VIOLATED",
                             "TEMPORAL_INCONSISTENT"]
    r.check("MatchingStatus 순서 일치", status_names == expected_status_order)

    target_names = [m.name for m in MatchingTargetType]
    expected_target_order = ["PLAYER", "BALL", "REFEREE", "COACH", "PERSON", "OTHER"]
    r.check("MatchingTargetType 순서 일치", target_names == expected_target_order)

    # --- len() ---
    r.check("len(MatchingStrategy) = 7", len(MatchingStrategy) == 7)
    r.check("len(MatchingStatus) = 7", len(MatchingStatus) == 7)
    r.check("len(MatchingTargetType) = 6", len(MatchingTargetType) == 6)

    # --- _value2member_map_ ---
    r.check("Strategy 'hungarian' in _value2member_map_",
            "hungarian" in MatchingStrategy._value2member_map_)
    r.check("Status 'matched' in _value2member_map_",
            "matched" in MatchingStatus._value2member_map_)
    r.check("TargetType 'player' in _value2member_map_",
            "player" in MatchingTargetType._value2member_map_)

    # --- set ---
    strat_set = set(MatchingStrategy)
    r.check("MatchingStrategy set 7개", len(strat_set) == 7)
    status_set = set(MatchingStatus)
    r.check("MatchingStatus set 7개", len(status_set) == 7)
    target_set = set(MatchingTargetType)
    r.check("MatchingTargetType set 6개", len(target_set) == 6)

    # --- frozenset 캐시 멤버십 ---
    import shared.constants.matching_constants as module
    # is_optimal 캐시
    optimal_cache = module._MATCHING_STRATEGY_IS_OPTIMAL
    r.check("_IS_OPTIMAL frozenset 타입", isinstance(optimal_cache, frozenset))
    r.check("HUNGARIAN in _IS_OPTIMAL", MatchingStrategy.HUNGARIAN in optimal_cache)
    r.check("AUCTION in _IS_OPTIMAL", MatchingStrategy.AUCTION in optimal_cache)
    r.check("GREEDY not in _IS_OPTIMAL", MatchingStrategy.GREEDY not in optimal_cache)

    # supports_partial 캐시
    partial_cache = module._MATCHING_STRATEGY_SUPPORTS_PARTIAL
    r.check("_SUPPORTS_PARTIAL frozenset 타입", isinstance(partial_cache, frozenset))
    r.check("GREEDY in _SUPPORTS_PARTIAL", MatchingStrategy.GREEDY in partial_cache)
    r.check("HIERARCHICAL in _SUPPORTS_PARTIAL",
            MatchingStrategy.HIERARCHICAL in partial_cache)
    r.check("FUSION in _SUPPORTS_PARTIAL", MatchingStrategy.FUSION in partial_cache)

    # needs_resolution 캐시
    resolution_cache = module._MATCHING_STATUS_NEEDS_RESOLUTION
    r.check("_NEEDS_RESOLUTION frozenset 타입", isinstance(resolution_cache, frozenset))
    r.check("AMBIGUOUS in _NEEDS_RESOLUTION",
            MatchingStatus.AMBIGUOUS in resolution_cache)
    r.check("CONFLICTED in _NEEDS_RESOLUTION",
            MatchingStatus.CONFLICTED in resolution_cache)

    # can_retry 캐시
    retry_cache = module._MATCHING_STATUS_CAN_RETRY
    r.check("_CAN_RETRY frozenset 타입", isinstance(retry_cache, frozenset))
    r.check("BELOW_THRESHOLD in _CAN_RETRY",
            MatchingStatus.BELOW_THRESHOLD in retry_cache)
    r.check("TEMPORAL_INCONSISTENT in _CAN_RETRY",
            MatchingStatus.TEMPORAL_INCONSISTENT in retry_cache)

    # --- dict 캐시 완전성 ---
    threshold_map = module._MATCHING_STRATEGY_THRESHOLD_MAP
    r.check("threshold_map dict 타입", isinstance(threshold_map, dict))
    r.check("threshold_map 7개 키", len(threshold_map) == 7)
    for m in MatchingStrategy:
        r.check(f"threshold_map에 {m.name} 존재", m in threshold_map)

    korean_strategy_map = module._MATCHING_STRATEGY_KOREAN_MAP
    r.check("korean_strategy_map 7개 키", len(korean_strategy_map) == 7)
    for m in MatchingStrategy:
        r.check(f"korean_strategy_map에 {m.name} 존재", m in korean_strategy_map)

    korean_status_map = module._MATCHING_STATUS_KOREAN_MAP
    r.check("korean_status_map 7개 키", len(korean_status_map) == 7)
    for m in MatchingStatus:
        r.check(f"korean_status_map에 {m.name} 존재", m in korean_status_map)

    target_weights_map = module._MATCHING_TARGET_WEIGHTS_MAP
    r.check("target_weights_map 6개 키", len(target_weights_map) == 6)
    for m in MatchingTargetType:
        r.check(f"target_weights_map에 {m.name} 존재", m in target_weights_map)

    target_appearance_map = module._MATCHING_TARGET_APPEARANCE_THRESHOLD_MAP
    r.check("target_appearance_map 6개 키", len(target_appearance_map) == 6)
    for m in MatchingTargetType:
        r.check(f"target_appearance_map에 {m.name} 존재", m in target_appearance_map)

    target_korean_map = module._MATCHING_TARGET_KOREAN_MAP
    r.check("target_korean_map 6개 키", len(target_korean_map) == 6)
    for m in MatchingTargetType:
        r.check(f"target_korean_map에 {m.name} 존재", m in target_korean_map)

    # --- Cross-Enum 격리 ---
    # 서로 다른 Enum 간 비교는 False
    r.check("MatchingStrategy != MatchingStatus",
            MatchingStrategy.HUNGARIAN != MatchingStatus.MATCHED)
    r.check("MatchingStatus != MatchingTargetType",
            MatchingStatus.MATCHED != MatchingTargetType.PLAYER)
    r.check("MatchingStrategy != MatchingTargetType",
            MatchingStrategy.HUNGARIAN != MatchingTargetType.PLAYER)

    # --- 튜플 불변성 ---
    # 튜플은 불변이므로 항목 변경 시도 시 TypeError
    for name, weights in [("PLAYER", PLAYER_MATCHING_WEIGHTS),
                          ("BALL", BALL_MATCHING_WEIGHTS),
                          ("REFEREE", REFEREE_MATCHING_WEIGHTS)]:
        try:
            weights[0] = 999.0  # type: ignore
            r.fail(f"{name}_WEIGHTS 불변성 (TypeError 미발생)")
        except TypeError:
            r.ok(f"{name}_WEIGHTS 불변성 (TypeError 발생)")

    # --- MATCHED만 is_successful + 나머지 조합 상호 배타성 ---
    # is_successful, needs_resolution, can_retry 동시 True인 경우 없어야 함
    for m in MatchingStatus:
        flags = (m.is_successful, m.needs_resolution, m.can_retry)
        true_count = sum(flags)
        r.check(f"{m.name} 상태 플래그 최대 1개 True (실제: {true_count})",
                true_count <= 1)


def main():
    r = TestResult()
    test_matching_strategy_basics(r)              # 1
    test_matching_strategy_is_optimal(r)           # 2
    test_matching_strategy_supports_partial(r)     # 3
    test_matching_strategy_default_threshold(r)    # 4
    test_matching_strategy_korean(r)               # 5
    test_matching_status_basics(r)                 # 6
    test_matching_status_properties(r)             # 7
    test_matching_status_korean(r)                 # 8
    test_matching_target_type_basics(r)            # 9
    test_matching_target_type_weights(r)           # 10
    test_matching_target_type_appearance(r)        # 11
    test_matching_target_type_korean(r)            # 12
    test_basic_weight_constants(r)                 # 13
    test_all_remaining_constants(r)                # 14
    test_all_exports(r)                            # 15
    test_edge_cases(r)                             # 16
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
