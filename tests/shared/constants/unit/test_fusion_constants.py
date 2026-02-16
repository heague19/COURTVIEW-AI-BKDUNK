# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_fusion_constants.py

멀티뷰 융합 상수 모듈 유닛 테스트
- 뷰 요구사항 상수: 값, 타입, 논리 관계
- 신뢰도 임계값 상수: 값, 범위, 순서
- 가중치 상수: 값, 합계 검증
- 삼각측량 파라미터: 값, 논리 관계
- 융합 알고리즘 파라미터: 값, 범위
- 충돌 해결 / 3D 재구성 / 뷰 선택 파라미터
- FusionStrategy: 멤버, requires_history, is_probabilistic, default_weight_type, to_korean
- FusionQuality: 멤버, score_range, is_usable, from_score, to_korean
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


# ==================== 1. 뷰 요구사항 상수 ====================
def test_view_requirements(r: TestResult) -> None:
    print("\n[1] 뷰 요구사항 상수")
    from shared.constants.fusion_constants import (
        MIN_VIEWS_FOR_FUSION, RECOMMENDED_VIEWS_FOR_FUSION,
        OPTIMAL_VIEWS_FOR_FUSION, MIN_VIEWS_FOR_TRIANGULATION,
        RECOMMENDED_VIEWS_FOR_TRIANGULATION, MAX_VIEWS_FOR_FUSION,
    )

    # 값 검증
    r.check("MIN_VIEWS = 2", MIN_VIEWS_FOR_FUSION == 2)
    r.check("RECOMMENDED = 3", RECOMMENDED_VIEWS_FOR_FUSION == 3)
    r.check("OPTIMAL = 4", OPTIMAL_VIEWS_FOR_FUSION == 4)
    r.check("MIN_TRIANGULATION = 2", MIN_VIEWS_FOR_TRIANGULATION == 2)
    r.check("RECOMMENDED_TRIANGULATION = 3", RECOMMENDED_VIEWS_FOR_TRIANGULATION == 3)
    r.check("MAX = 6", MAX_VIEWS_FOR_FUSION == 6)

    # 타입
    for name, val in [("MIN", MIN_VIEWS_FOR_FUSION), ("MAX", MAX_VIEWS_FOR_FUSION)]:
        r.check(f"{name} int", isinstance(val, int))

    # 순서 관계
    r.check("MIN ≤ RECOMMENDED ≤ OPTIMAL ≤ MAX",
            MIN_VIEWS_FOR_FUSION <= RECOMMENDED_VIEWS_FOR_FUSION
            <= OPTIMAL_VIEWS_FOR_FUSION <= MAX_VIEWS_FOR_FUSION)

    # 양수
    r.check("모두 양수", all(v > 0 for v in [
        MIN_VIEWS_FOR_FUSION, RECOMMENDED_VIEWS_FOR_FUSION,
        OPTIMAL_VIEWS_FOR_FUSION, MAX_VIEWS_FOR_FUSION]))


# ==================== 2. 신뢰도 임계값 ====================
def test_confidence_thresholds(r: TestResult) -> None:
    print("\n[2] 신뢰도 임계값")
    from shared.constants.fusion_constants import (
        FUSION_CONFIDENCE_THRESHOLD, FUSION_HIGH_CONFIDENCE_THRESHOLD,
        FUSION_LOW_CONFIDENCE_THRESHOLD, TRIANGULATION_CONFIDENCE_THRESHOLD,
        VIEW_DETECTION_MIN_CONFIDENCE, VIEW_DETECTION_WEIGHT_THRESHOLD,
    )

    consts = [
        ("FUSION_CONFIDENCE", FUSION_CONFIDENCE_THRESHOLD, 0.7),
        ("FUSION_HIGH", FUSION_HIGH_CONFIDENCE_THRESHOLD, 0.85),
        ("FUSION_LOW", FUSION_LOW_CONFIDENCE_THRESHOLD, 0.5),
        ("TRIANGULATION", TRIANGULATION_CONFIDENCE_THRESHOLD, 0.8),
        ("VIEW_DET_MIN", VIEW_DETECTION_MIN_CONFIDENCE, 0.5),
        ("VIEW_DET_WEIGHT", VIEW_DETECTION_WEIGHT_THRESHOLD, 0.7),
    ]
    for name, val, expected in consts:
        r.check(f"{name} = {expected}", abs(val - expected) < 1e-9)
        r.check(f"{name} 0~1", 0.0 <= val <= 1.0)

    # 순서
    r.check("LOW < THRESHOLD < HIGH",
            FUSION_LOW_CONFIDENCE_THRESHOLD
            < FUSION_CONFIDENCE_THRESHOLD
            < FUSION_HIGH_CONFIDENCE_THRESHOLD)
    r.check("VIEW_DET_MIN ≤ VIEW_DET_WEIGHT",
            VIEW_DETECTION_MIN_CONFIDENCE <= VIEW_DETECTION_WEIGHT_THRESHOLD)


# ==================== 3. 가중치 ====================
def test_weights(r: TestResult) -> None:
    print("\n[3] 가중치")
    from shared.constants.fusion_constants import (
        APPEARANCE_WEIGHT, GEOMETRY_WEIGHT, POSITION_WEIGHT,
        TEMPORAL_CONSISTENCY_WEIGHT, VELOCITY_CONSISTENCY_WEIGHT,
        SIZE_CONSISTENCY_WEIGHT,
    )

    # 값
    r.check("APPEARANCE = 0.3", abs(APPEARANCE_WEIGHT - 0.3) < 1e-9)
    r.check("GEOMETRY = 0.5", abs(GEOMETRY_WEIGHT - 0.5) < 1e-9)
    r.check("POSITION = 0.2", abs(POSITION_WEIGHT - 0.2) < 1e-9)
    r.check("TEMPORAL = 0.4", abs(TEMPORAL_CONSISTENCY_WEIGHT - 0.4) < 1e-9)
    r.check("VELOCITY = 0.3", abs(VELOCITY_CONSISTENCY_WEIGHT - 0.3) < 1e-9)
    r.check("SIZE = 0.2", abs(SIZE_CONSISTENCY_WEIGHT - 0.2) < 1e-9)

    # 핵심: 외관+기하학+위치 = 1.0
    total = APPEARANCE_WEIGHT + GEOMETRY_WEIGHT + POSITION_WEIGHT
    r.check("APP+GEO+POS = 1.0", abs(total - 1.0) < 1e-9)

    # 기하학이 가장 큰 가중치
    r.check("GEOMETRY > APPEARANCE > POSITION",
            GEOMETRY_WEIGHT > APPEARANCE_WEIGHT > POSITION_WEIGHT)


# ==================== 4. 삼각측량 파라미터 ====================
def test_triangulation_params(r: TestResult) -> None:
    print("\n[4] 삼각측량 파라미터")
    from shared.constants.fusion_constants import (
        MAX_REPROJECTION_ERROR_PX, RECOMMENDED_REPROJECTION_ERROR_PX,
        TRIANGULATION_MIN_DEPTH_M, TRIANGULATION_MAX_DEPTH_M,
        DEPTH_CONSISTENCY_THRESHOLD_M, MIN_BASELINE_RATIO,
        MIN_RAY_INTERSECTION_ANGLE_DEG,
    )

    r.check("MAX_REPROJ = 5.0px", abs(MAX_REPROJECTION_ERROR_PX - 5.0) < 1e-9)
    r.check("RECOMMENDED_REPROJ = 2.0px", abs(RECOMMENDED_REPROJECTION_ERROR_PX - 2.0) < 1e-9)
    r.check("MIN_DEPTH = 0.5m", abs(TRIANGULATION_MIN_DEPTH_M - 0.5) < 1e-9)
    r.check("MAX_DEPTH = 50.0m", abs(TRIANGULATION_MAX_DEPTH_M - 50.0) < 1e-9)
    r.check("DEPTH_CONSISTENCY = 1.0m", abs(DEPTH_CONSISTENCY_THRESHOLD_M - 1.0) < 1e-9)
    r.check("BASELINE_RATIO = 0.1", abs(MIN_BASELINE_RATIO - 0.1) < 1e-9)
    r.check("RAY_ANGLE = 5.0°", abs(MIN_RAY_INTERSECTION_ANGLE_DEG - 5.0) < 1e-9)

    # 논리 관계
    r.check("RECOMMENDED < MAX 재투영",
            RECOMMENDED_REPROJECTION_ERROR_PX < MAX_REPROJECTION_ERROR_PX)
    r.check("MIN_DEPTH < MAX_DEPTH",
            TRIANGULATION_MIN_DEPTH_M < TRIANGULATION_MAX_DEPTH_M)
    r.check("RAY_ANGLE < 90°", MIN_RAY_INTERSECTION_ANGLE_DEG < 90.0)


# ==================== 5. 융합 알고리즘 파라미터 ====================
def test_fusion_algorithm_params(r: TestResult) -> None:
    print("\n[5] 융합 알고리즘 파라미터")
    from shared.constants.fusion_constants import (
        RANSAC_ITERATIONS, RANSAC_INLIER_RATIO_THRESHOLD,
        KALMAN_PROCESS_NOISE_POSITION, KALMAN_PROCESS_NOISE_VELOCITY,
        KALMAN_MEASUREMENT_NOISE, EMA_SMOOTHING_FACTOR,
        MIN_TOTAL_VIEW_WEIGHT,
    )

    r.check("RANSAC_ITER = 100", RANSAC_ITERATIONS == 100)
    r.check("RANSAC_ITER int", isinstance(RANSAC_ITERATIONS, int))
    r.check("RANSAC_INLIER = 0.6", abs(RANSAC_INLIER_RATIO_THRESHOLD - 0.6) < 1e-9)
    r.check("KALMAN_POS = 0.1", abs(KALMAN_PROCESS_NOISE_POSITION - 0.1) < 1e-9)
    r.check("KALMAN_VEL = 0.5", abs(KALMAN_PROCESS_NOISE_VELOCITY - 0.5) < 1e-9)
    r.check("KALMAN_MEAS = 1.0", abs(KALMAN_MEASUREMENT_NOISE - 1.0) < 1e-9)
    r.check("EMA = 0.7", abs(EMA_SMOOTHING_FACTOR - 0.7) < 1e-9)
    r.check("EMA 0~1", 0.0 <= EMA_SMOOTHING_FACTOR <= 1.0)
    r.check("MIN_VIEW_WEIGHT = 0.5", abs(MIN_TOTAL_VIEW_WEIGHT - 0.5) < 1e-9)

    # 칼만 노이즈 관계: 위치 < 속도 (속도가 더 불확실)
    r.check("칼만 POS_NOISE < VEL_NOISE",
            KALMAN_PROCESS_NOISE_POSITION < KALMAN_PROCESS_NOISE_VELOCITY)


# ==================== 6. 충돌/3D/뷰선택 파라미터 ====================
def test_remaining_params(r: TestResult) -> None:
    print("\n[6] 충돌/3D/뷰선택 파라미터")
    from shared.constants.fusion_constants import (
        VIEW_DISAGREEMENT_THRESHOLD_M, VOTING_CONSENSUS_RATIO,
        AMBIGUITY_RESOLUTION_HISTORY_FRAMES,
        MIN_POINTS_FOR_3D_RECONSTRUCTION, VOXEL_SIZE_M,
        MAX_RECONSTRUCTION_DISTANCE_M, POINT_CLOUD_DOWNSAMPLE_DISTANCE_M,
        MIN_VIEW_QUALITY_SCORE, MIN_VISIBILITY_RATIO,
        OPTIMAL_VIEW_ANGLE_MIN_DEG, OPTIMAL_VIEW_ANGLE_MAX_DEG,
        VIEW_REDUNDANCY_ANGLE_DEG,
    )

    # 충돌 해결
    r.check("DISAGREEMENT = 1.0m", abs(VIEW_DISAGREEMENT_THRESHOLD_M - 1.0) < 1e-9)
    r.check("VOTING = 0.5", abs(VOTING_CONSENSUS_RATIO - 0.5) < 1e-9)
    r.check("VOTING 0~1", 0.0 <= VOTING_CONSENSUS_RATIO <= 1.0)
    r.check("HISTORY = 5", AMBIGUITY_RESOLUTION_HISTORY_FRAMES == 5)
    r.check("HISTORY int", isinstance(AMBIGUITY_RESOLUTION_HISTORY_FRAMES, int))

    # 3D 재구성
    r.check("MIN_POINTS = 10", MIN_POINTS_FOR_3D_RECONSTRUCTION == 10)
    r.check("VOXEL = 0.1m", abs(VOXEL_SIZE_M - 0.1) < 1e-9)
    r.check("MAX_RECON = 30.0m", abs(MAX_RECONSTRUCTION_DISTANCE_M - 30.0) < 1e-9)
    r.check("DOWNSAMPLE = 0.05m", abs(POINT_CLOUD_DOWNSAMPLE_DISTANCE_M - 0.05) < 1e-9)
    r.check("DOWNSAMPLE < VOXEL", POINT_CLOUD_DOWNSAMPLE_DISTANCE_M < VOXEL_SIZE_M)

    # 뷰 선택
    r.check("VIEW_QUALITY = 0.3", abs(MIN_VIEW_QUALITY_SCORE - 0.3) < 1e-9)
    r.check("VISIBILITY = 0.5", abs(MIN_VISIBILITY_RATIO - 0.5) < 1e-9)
    r.check("ANGLE_MIN = 30.0°", abs(OPTIMAL_VIEW_ANGLE_MIN_DEG - 30.0) < 1e-9)
    r.check("ANGLE_MAX = 60.0°", abs(OPTIMAL_VIEW_ANGLE_MAX_DEG - 60.0) < 1e-9)
    r.check("REDUNDANCY = 15.0°", abs(VIEW_REDUNDANCY_ANGLE_DEG - 15.0) < 1e-9)
    r.check("ANGLE_MIN < ANGLE_MAX",
            OPTIMAL_VIEW_ANGLE_MIN_DEG < OPTIMAL_VIEW_ANGLE_MAX_DEG)
    r.check("REDUNDANCY < ANGLE_MIN",
            VIEW_REDUNDANCY_ANGLE_DEG < OPTIMAL_VIEW_ANGLE_MIN_DEG)


# ==================== 7. FusionStrategy 기본 ====================
def test_fusion_strategy_basics(r: TestResult) -> None:
    print("\n[7] FusionStrategy 기본")
    from shared.constants.fusion_constants import FusionStrategy

    r.check("8개 멤버", len(FusionStrategy) == 8)

    expected = {
        "SIMPLE_AVERAGE": "simple_average",
        "WEIGHTED_AVERAGE": "weighted_average",
        "BAYESIAN": "bayesian",
        "KALMAN_FILTER": "kalman_filter",
        "MAJORITY_VOTING": "majority_voting",
        "HIGHEST_CONFIDENCE": "highest_confidence",
        "RANSAC": "ransac",
        "LEARNED": "learned",
    }
    for name, value in expected.items():
        r.check(f"{name} = '{value}'", FusionStrategy[name].value == value)


# ==================== 8. FusionStrategy 속성 ====================
def test_fusion_strategy_properties(r: TestResult) -> None:
    print("\n[8] FusionStrategy 속성")
    from shared.constants.fusion_constants import FusionStrategy

    # requires_history
    history_true = [FusionStrategy.KALMAN_FILTER, FusionStrategy.LEARNED]
    history_false = [
        FusionStrategy.SIMPLE_AVERAGE, FusionStrategy.WEIGHTED_AVERAGE,
        FusionStrategy.BAYESIAN, FusionStrategy.MAJORITY_VOTING,
        FusionStrategy.HIGHEST_CONFIDENCE, FusionStrategy.RANSAC,
    ]
    for fs in history_true:
        r.check(f"{fs.name}.requires_history = True", fs.requires_history)
    for fs in history_false:
        r.check(f"{fs.name}.requires_history = False", not fs.requires_history)

    # is_probabilistic
    prob_true = [FusionStrategy.BAYESIAN, FusionStrategy.KALMAN_FILTER]
    prob_false = [
        FusionStrategy.SIMPLE_AVERAGE, FusionStrategy.WEIGHTED_AVERAGE,
        FusionStrategy.MAJORITY_VOTING, FusionStrategy.HIGHEST_CONFIDENCE,
        FusionStrategy.RANSAC, FusionStrategy.LEARNED,
    ]
    for fs in prob_true:
        r.check(f"{fs.name}.is_probabilistic = True", fs.is_probabilistic)
    for fs in prob_false:
        r.check(f"{fs.name}.is_probabilistic = False", not fs.is_probabilistic)

    # default_weight_type (전수)
    weight_types = {
        FusionStrategy.SIMPLE_AVERAGE: "uniform",
        FusionStrategy.WEIGHTED_AVERAGE: "confidence",
        FusionStrategy.BAYESIAN: "posterior",
        FusionStrategy.KALMAN_FILTER: "kalman_gain",
        FusionStrategy.MAJORITY_VOTING: "vote_count",
        FusionStrategy.HIGHEST_CONFIDENCE: "max_confidence",
        FusionStrategy.RANSAC: "inlier_count",
        FusionStrategy.LEARNED: "learned_weight",
    }
    for fs, wt in weight_types.items():
        r.check(f"{fs.name}.default_weight_type = '{wt}'",
                fs.default_weight_type == wt)


# ==================== 9. FusionStrategy 한글 ====================
def test_fusion_strategy_korean(r: TestResult) -> None:
    print("\n[9] FusionStrategy 한글")
    from shared.constants.fusion_constants import FusionStrategy

    korean = {
        FusionStrategy.SIMPLE_AVERAGE: "단순 평균",
        FusionStrategy.WEIGHTED_AVERAGE: "가중 평균",
        FusionStrategy.BAYESIAN: "베이지안 융합",
        FusionStrategy.KALMAN_FILTER: "칼만 필터",
        FusionStrategy.MAJORITY_VOTING: "다수결 투표",
        FusionStrategy.HIGHEST_CONFIDENCE: "최고 신뢰도 선택",
        FusionStrategy.RANSAC: "RANSAC",
        FusionStrategy.LEARNED: "학습 기반",
    }
    for fs, kr in korean.items():
        r.check(f"{fs.name} → '{kr}'", fs.to_korean() == kr)


# ==================== 10. FusionQuality 기본 ====================
def test_fusion_quality_basics(r: TestResult) -> None:
    print("\n[10] FusionQuality 기본")
    from shared.constants.fusion_constants import FusionQuality

    r.check("5개 멤버", len(FusionQuality) == 5)

    expected = {
        "EXCELLENT": ("excellent", 0.9, 1.0),
        "GOOD": ("good", 0.75, 0.9),
        "ACCEPTABLE": ("acceptable", 0.6, 0.75),
        "POOR": ("poor", 0.4, 0.6),
        "FAILED": ("failed", 0.0, 0.4),
    }
    for name, (level, mn, mx) in expected.items():
        fq = FusionQuality[name]
        r.check(f"{name}.level_name = '{level}'", fq.level_name == level)
        r.check(f"{name}.min_score = {mn}", abs(fq.min_score - mn) < 1e-9)
        r.check(f"{name}.max_score = {mx}", abs(fq.max_score - mx) < 1e-9)
        r.check(f"{name}.score_range", fq.score_range == (mn, mx))


# ==================== 11. FusionQuality.is_usable ====================
def test_fusion_quality_usable(r: TestResult) -> None:
    print("\n[11] FusionQuality.is_usable")
    from shared.constants.fusion_constants import FusionQuality

    usable = [FusionQuality.EXCELLENT, FusionQuality.GOOD, FusionQuality.ACCEPTABLE]
    not_usable = [FusionQuality.POOR, FusionQuality.FAILED]

    for fq in usable:
        r.check(f"{fq.name} is_usable", fq.is_usable)
    for fq in not_usable:
        r.check(f"{fq.name} !is_usable", not fq.is_usable)


# ==================== 12. FusionQuality.from_score ====================
def test_fusion_quality_from_score(r: TestResult) -> None:
    print("\n[12] FusionQuality.from_score")
    from shared.constants.fusion_constants import FusionQuality

    # 경계값 테스트
    boundary_tests = [
        (1.0, FusionQuality.EXCELLENT),
        (0.9, FusionQuality.EXCELLENT),
        (0.899, FusionQuality.GOOD),
        (0.75, FusionQuality.GOOD),
        (0.749, FusionQuality.ACCEPTABLE),
        (0.6, FusionQuality.ACCEPTABLE),
        (0.599, FusionQuality.POOR),
        (0.4, FusionQuality.POOR),
        (0.399, FusionQuality.FAILED),
        (0.0, FusionQuality.FAILED),
    ]
    for score, expected in boundary_tests:
        result = FusionQuality.from_score(score)
        r.check(f"from_score({score}) = {expected.name}", result == expected)

    # 범위 밖 → ValueError
    for invalid_score in [-0.01, -1.0, 1.01, 2.0]:
        try:
            FusionQuality.from_score(invalid_score)
            r.fail(f"from_score({invalid_score}) ValueError")
        except ValueError:
            r.ok(f"from_score({invalid_score}) ValueError")


# ==================== 13. FusionQuality 한글 ====================
def test_fusion_quality_korean(r: TestResult) -> None:
    print("\n[13] FusionQuality 한글")
    from shared.constants.fusion_constants import FusionQuality

    korean = {
        FusionQuality.EXCELLENT: "우수",
        FusionQuality.GOOD: "양호",
        FusionQuality.ACCEPTABLE: "허용",
        FusionQuality.POOR: "저조",
        FusionQuality.FAILED: "실패",
    }
    for fq, kr in korean.items():
        r.check(f"{fq.name} → '{kr}'", fq.to_korean() == kr)


# ==================== 14. FusionQuality 점수 범위 연속성 ====================
def test_quality_score_continuity(r: TestResult) -> None:
    print("\n[14] 점수 범위 연속성")
    from shared.constants.fusion_constants import FusionQuality

    levels = sorted(FusionQuality, key=lambda q: q.max_score, reverse=True)

    # 인접 레벨의 min/max가 연속적
    for i in range(len(levels) - 1):
        curr = levels[i]
        nxt = levels[i + 1]
        r.check(f"{curr.name}.min = {nxt.name}.max",
                abs(curr.min_score - nxt.max_score) < 1e-9)

    # 전체 범위
    r.check("최솟값 0.0", abs(levels[-1].min_score - 0.0) < 1e-9)
    r.check("최댓값 1.0", abs(levels[0].max_score - 1.0) < 1e-9)

    # 각 레벨 min < max
    for fq in FusionQuality:
        r.check(f"{fq.name}: min < max", fq.min_score < fq.max_score)


# ==================== 15. __all__ export ====================
def test_all_exports(r: TestResult) -> None:
    print("\n[15] __all__ export")
    import shared.constants.fusion_constants as module

    r.check("__all__ 존재", hasattr(module, "__all__"))
    r.check("__all__ 46개", len(module.__all__) == 46)

    # 모든 export가 실제 존재
    for name in module.__all__:
        r.check(f"'{name}' 존재", hasattr(module, name))

    # Enum도 포함
    r.check("FusionStrategy in __all__", "FusionStrategy" in module.__all__)
    r.check("FusionQuality in __all__", "FusionQuality" in module.__all__)


# ==================== 16. 에지 케이스 ====================
def test_edge_cases(r: TestResult) -> None:
    print("\n[16] 에지 케이스")
    from shared.constants.fusion_constants import FusionStrategy, FusionQuality

    # identity
    r.check("FusionStrategy identity",
            FusionStrategy.BAYESIAN is FusionStrategy.BAYESIAN)
    r.check("FusionQuality identity",
            FusionQuality.EXCELLENT is FusionQuality.EXCELLENT)

    # 동등 비교
    r.check("같은 전략 ==", FusionStrategy.RANSAC == FusionStrategy.RANSAC)
    r.check("다른 전략 !=", FusionStrategy.RANSAC != FusionStrategy.BAYESIAN)

    # 해시 가능
    d = {FusionStrategy.BAYESIAN: "test", FusionQuality.EXCELLENT: "hi"}
    r.check("dict 키 사용", d[FusionStrategy.BAYESIAN] == "test")
    r.check("FusionQuality dict 키", d[FusionQuality.EXCELLENT] == "hi")

    # set
    s = set(FusionStrategy)
    r.check("FusionStrategy set 8개", len(s) == 8)
    sq = set(FusionQuality)
    r.check("FusionQuality set 5개", len(sq) == 5)

    # KALMAN_FILTER: requires_history AND is_probabilistic
    kf = FusionStrategy.KALMAN_FILTER
    r.check("KALMAN: history AND probabilistic",
            kf.requires_history and kf.is_probabilistic)

    # BAYESIAN: is_probabilistic AND NOT requires_history
    bay = FusionStrategy.BAYESIAN
    r.check("BAYESIAN: prob AND NOT history",
            bay.is_probabilistic and not bay.requires_history)

    # from_score 경계값 정밀
    r.check("from_score(0.9) = EXCELLENT",
            FusionQuality.from_score(0.9) == FusionQuality.EXCELLENT)
    r.check("from_score(0.8999...) = GOOD",
            FusionQuality.from_score(0.8999999) == FusionQuality.GOOD)


def main():
    r = TestResult()
    test_view_requirements(r)           # 1
    test_confidence_thresholds(r)       # 2
    test_weights(r)                     # 3
    test_triangulation_params(r)        # 4
    test_fusion_algorithm_params(r)     # 5
    test_remaining_params(r)            # 6
    test_fusion_strategy_basics(r)      # 7
    test_fusion_strategy_properties(r)  # 8
    test_fusion_strategy_korean(r)      # 9
    test_fusion_quality_basics(r)       # 10
    test_fusion_quality_usable(r)       # 11
    test_fusion_quality_from_score(r)   # 12
    test_fusion_quality_korean(r)       # 13
    test_quality_score_continuity(r)    # 14
    test_all_exports(r)                 # 15
    test_edge_cases(r)                  # 16
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
