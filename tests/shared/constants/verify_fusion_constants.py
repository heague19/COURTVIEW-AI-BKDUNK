# -*- coding: utf-8 -*-
"""
tests/verify_fusion_constants.py

fusion_constants.py 전수 검증 테스트
- typing 현대화 확인 (Dict/Tuple 미사용)
- Final 상수 값/타입/범위 전수 검증
- FusionStrategy Enum 멤버/속성/한글/캐시
- FusionQuality Enum 멤버/속성/from_score/한글/캐시
- 가중치 합 검증 (외관+기하학+위치=1.0)
- __all__ 완전성
- __init__.py 재수출

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
        print(f"검증 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== A. typing 현대화 ====================
def test_typing_modernization(r: TestResult) -> None:
    print("\n[A] typing 현대화")
    src = Path(_PROJECT_ROOT / "shared" / "constants" / "fusion_constants.py")
    text = src.read_text(encoding="utf-8")

    # 주석 제외 후 검사
    code_lines = []
    for line in text.splitlines():
        code_part = line.split("#")[0]
        code_lines.append(code_part)
    code_only = "\n".join(code_lines)

    r.check("Dict[ 미사용", "Dict[" not in code_only)
    r.check("Tuple[ 미사용", "Tuple[" not in code_only)
    r.check("List[ 미사용", "List[" not in code_only)
    r.check("FrozenSet[ 미사용", "FrozenSet[" not in code_only)
    r.check("from typing import Final만", "from typing import Final" in text)


# ==================== B. 뷰 요구사항 상수 ====================
def test_view_requirement_constants(r: TestResult) -> None:
    print("\n[B] 뷰 요구사항 상수")
    from shared.constants.fusion_constants import (
        MIN_VIEWS_FOR_FUSION, RECOMMENDED_VIEWS_FOR_FUSION,
        OPTIMAL_VIEWS_FOR_FUSION, MIN_VIEWS_FOR_TRIANGULATION,
        RECOMMENDED_VIEWS_FOR_TRIANGULATION, MAX_VIEWS_FOR_FUSION,
    )

    consts = {
        "MIN_VIEWS_FOR_FUSION": (MIN_VIEWS_FOR_FUSION, int, 2),
        "RECOMMENDED_VIEWS_FOR_FUSION": (RECOMMENDED_VIEWS_FOR_FUSION, int, 3),
        "OPTIMAL_VIEWS_FOR_FUSION": (OPTIMAL_VIEWS_FOR_FUSION, int, 4),
        "MIN_VIEWS_FOR_TRIANGULATION": (MIN_VIEWS_FOR_TRIANGULATION, int, 2),
        "RECOMMENDED_VIEWS_FOR_TRIANGULATION": (RECOMMENDED_VIEWS_FOR_TRIANGULATION, int, 3),
        "MAX_VIEWS_FOR_FUSION": (MAX_VIEWS_FOR_FUSION, int, 6),
    }
    for name, (val, typ, expected) in consts.items():
        r.check(f"{name} 타입={typ.__name__}", isinstance(val, typ))
        r.check(f"{name} = {expected}", val == expected)

    # 논리적 관계
    r.check("MIN ≤ RECOMMENDED ≤ OPTIMAL ≤ MAX",
            MIN_VIEWS_FOR_FUSION <= RECOMMENDED_VIEWS_FOR_FUSION
            <= OPTIMAL_VIEWS_FOR_FUSION <= MAX_VIEWS_FOR_FUSION)
    r.check("TRIANGULATION MIN ≤ RECOMMENDED",
            MIN_VIEWS_FOR_TRIANGULATION <= RECOMMENDED_VIEWS_FOR_TRIANGULATION)


# ==================== C. 신뢰도 임계값 상수 ====================
def test_confidence_threshold_constants(r: TestResult) -> None:
    print("\n[C] 신뢰도 임계값 상수")
    from shared.constants.fusion_constants import (
        FUSION_CONFIDENCE_THRESHOLD, FUSION_HIGH_CONFIDENCE_THRESHOLD,
        FUSION_LOW_CONFIDENCE_THRESHOLD, TRIANGULATION_CONFIDENCE_THRESHOLD,
        VIEW_DETECTION_MIN_CONFIDENCE, VIEW_DETECTION_WEIGHT_THRESHOLD,
    )

    consts = {
        "FUSION_CONFIDENCE_THRESHOLD": (FUSION_CONFIDENCE_THRESHOLD, 0.7),
        "FUSION_HIGH_CONFIDENCE_THRESHOLD": (FUSION_HIGH_CONFIDENCE_THRESHOLD, 0.85),
        "FUSION_LOW_CONFIDENCE_THRESHOLD": (FUSION_LOW_CONFIDENCE_THRESHOLD, 0.5),
        "TRIANGULATION_CONFIDENCE_THRESHOLD": (TRIANGULATION_CONFIDENCE_THRESHOLD, 0.8),
        "VIEW_DETECTION_MIN_CONFIDENCE": (VIEW_DETECTION_MIN_CONFIDENCE, 0.5),
        "VIEW_DETECTION_WEIGHT_THRESHOLD": (VIEW_DETECTION_WEIGHT_THRESHOLD, 0.7),
    }
    for name, (val, expected) in consts.items():
        r.check(f"{name} float 타입", isinstance(val, float))
        r.check(f"{name} = {expected}", abs(val - expected) < 1e-9)
        r.check(f"{name} 0~1 범위", 0.0 <= val <= 1.0)

    # 논리적 관계
    r.check("LOW < THRESHOLD < HIGH",
            FUSION_LOW_CONFIDENCE_THRESHOLD < FUSION_CONFIDENCE_THRESHOLD
            < FUSION_HIGH_CONFIDENCE_THRESHOLD)


# ==================== D. 가중치 상수 ====================
def test_weight_constants(r: TestResult) -> None:
    print("\n[D] 가중치 상수")
    from shared.constants.fusion_constants import (
        APPEARANCE_WEIGHT, GEOMETRY_WEIGHT, POSITION_WEIGHT,
        TEMPORAL_CONSISTENCY_WEIGHT, VELOCITY_CONSISTENCY_WEIGHT,
        SIZE_CONSISTENCY_WEIGHT,
    )

    weights = {
        "APPEARANCE_WEIGHT": (APPEARANCE_WEIGHT, 0.3),
        "GEOMETRY_WEIGHT": (GEOMETRY_WEIGHT, 0.5),
        "POSITION_WEIGHT": (POSITION_WEIGHT, 0.2),
        "TEMPORAL_CONSISTENCY_WEIGHT": (TEMPORAL_CONSISTENCY_WEIGHT, 0.4),
        "VELOCITY_CONSISTENCY_WEIGHT": (VELOCITY_CONSISTENCY_WEIGHT, 0.3),
        "SIZE_CONSISTENCY_WEIGHT": (SIZE_CONSISTENCY_WEIGHT, 0.2),
    }
    for name, (val, expected) in weights.items():
        r.check(f"{name} float 타입", isinstance(val, float))
        r.check(f"{name} = {expected}", abs(val - expected) < 1e-9)
        r.check(f"{name} 0~1 범위", 0.0 <= val <= 1.0)

    # 핵심 검증: 외관+기하학+위치 = 1.0
    weight_sum = APPEARANCE_WEIGHT + GEOMETRY_WEIGHT + POSITION_WEIGHT
    r.check("외관+기하학+위치 합 = 1.0", abs(weight_sum - 1.0) < 1e-9,
            f"실제: {weight_sum}")


# ==================== E. 삼각측량 파라미터 ====================
def test_triangulation_parameters(r: TestResult) -> None:
    print("\n[E] 삼각측량 파라미터")
    from shared.constants.fusion_constants import (
        MAX_REPROJECTION_ERROR_PX, RECOMMENDED_REPROJECTION_ERROR_PX,
        TRIANGULATION_MIN_DEPTH_M, TRIANGULATION_MAX_DEPTH_M,
        DEPTH_CONSISTENCY_THRESHOLD_M, MIN_BASELINE_RATIO,
        MIN_RAY_INTERSECTION_ANGLE_DEG,
    )

    params = {
        "MAX_REPROJECTION_ERROR_PX": (MAX_REPROJECTION_ERROR_PX, 5.0),
        "RECOMMENDED_REPROJECTION_ERROR_PX": (RECOMMENDED_REPROJECTION_ERROR_PX, 2.0),
        "TRIANGULATION_MIN_DEPTH_M": (TRIANGULATION_MIN_DEPTH_M, 0.5),
        "TRIANGULATION_MAX_DEPTH_M": (TRIANGULATION_MAX_DEPTH_M, 50.0),
        "DEPTH_CONSISTENCY_THRESHOLD_M": (DEPTH_CONSISTENCY_THRESHOLD_M, 1.0),
        "MIN_BASELINE_RATIO": (MIN_BASELINE_RATIO, 0.1),
        "MIN_RAY_INTERSECTION_ANGLE_DEG": (MIN_RAY_INTERSECTION_ANGLE_DEG, 5.0),
    }
    for name, (val, expected) in params.items():
        r.check(f"{name} float 타입", isinstance(val, float))
        r.check(f"{name} = {expected}", abs(val - expected) < 1e-9)
        r.check(f"{name} > 0", val > 0)

    # 논리적 관계
    r.check("RECOMMENDED < MAX 재투영 오차",
            RECOMMENDED_REPROJECTION_ERROR_PX < MAX_REPROJECTION_ERROR_PX)
    r.check("MIN_DEPTH < MAX_DEPTH",
            TRIANGULATION_MIN_DEPTH_M < TRIANGULATION_MAX_DEPTH_M)


# ==================== F. 융합 알고리즘 파라미터 ====================
def test_fusion_algorithm_parameters(r: TestResult) -> None:
    print("\n[F] 융합 알고리즘 파라미터")
    from shared.constants.fusion_constants import (
        RANSAC_ITERATIONS, RANSAC_INLIER_RATIO_THRESHOLD,
        KALMAN_PROCESS_NOISE_POSITION, KALMAN_PROCESS_NOISE_VELOCITY,
        KALMAN_MEASUREMENT_NOISE, EMA_SMOOTHING_FACTOR,
        MIN_TOTAL_VIEW_WEIGHT,
    )

    r.check("RANSAC_ITERATIONS int", isinstance(RANSAC_ITERATIONS, int))
    r.check("RANSAC_ITERATIONS = 100", RANSAC_ITERATIONS == 100)
    r.check("RANSAC_INLIER_RATIO = 0.6", abs(RANSAC_INLIER_RATIO_THRESHOLD - 0.6) < 1e-9)
    r.check("KALMAN_PROCESS_NOISE_POSITION = 0.1", abs(KALMAN_PROCESS_NOISE_POSITION - 0.1) < 1e-9)
    r.check("KALMAN_PROCESS_NOISE_VELOCITY = 0.5", abs(KALMAN_PROCESS_NOISE_VELOCITY - 0.5) < 1e-9)
    r.check("KALMAN_MEASUREMENT_NOISE = 1.0", abs(KALMAN_MEASUREMENT_NOISE - 1.0) < 1e-9)
    r.check("EMA_SMOOTHING_FACTOR = 0.7", abs(EMA_SMOOTHING_FACTOR - 0.7) < 1e-9)
    r.check("EMA 0~1 범위", 0.0 <= EMA_SMOOTHING_FACTOR <= 1.0)
    r.check("MIN_TOTAL_VIEW_WEIGHT = 0.5", abs(MIN_TOTAL_VIEW_WEIGHT - 0.5) < 1e-9)


# ==================== G. 충돌 해결 / 3D 재구성 / 뷰 선택 ====================
def test_remaining_constants(r: TestResult) -> None:
    print("\n[G] 충돌 해결 / 3D 재구성 / 뷰 선택")
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
    r.check("VIEW_DISAGREEMENT = 1.0", abs(VIEW_DISAGREEMENT_THRESHOLD_M - 1.0) < 1e-9)
    r.check("VOTING_CONSENSUS = 0.5", abs(VOTING_CONSENSUS_RATIO - 0.5) < 1e-9)
    r.check("AMBIGUITY_HISTORY int", isinstance(AMBIGUITY_RESOLUTION_HISTORY_FRAMES, int))
    r.check("AMBIGUITY_HISTORY = 5", AMBIGUITY_RESOLUTION_HISTORY_FRAMES == 5)

    # 3D 재구성
    r.check("MIN_POINTS int", isinstance(MIN_POINTS_FOR_3D_RECONSTRUCTION, int))
    r.check("MIN_POINTS = 10", MIN_POINTS_FOR_3D_RECONSTRUCTION == 10)
    r.check("VOXEL_SIZE = 0.1", abs(VOXEL_SIZE_M - 0.1) < 1e-9)
    r.check("MAX_RECONSTRUCTION = 30.0", abs(MAX_RECONSTRUCTION_DISTANCE_M - 30.0) < 1e-9)
    r.check("DOWNSAMPLE = 0.05", abs(POINT_CLOUD_DOWNSAMPLE_DISTANCE_M - 0.05) < 1e-9)
    r.check("DOWNSAMPLE < VOXEL", POINT_CLOUD_DOWNSAMPLE_DISTANCE_M < VOXEL_SIZE_M)

    # 뷰 선택
    r.check("MIN_VIEW_QUALITY = 0.3", abs(MIN_VIEW_QUALITY_SCORE - 0.3) < 1e-9)
    r.check("MIN_VISIBILITY = 0.5", abs(MIN_VISIBILITY_RATIO - 0.5) < 1e-9)
    r.check("OPTIMAL_ANGLE_MIN = 30.0", abs(OPTIMAL_VIEW_ANGLE_MIN_DEG - 30.0) < 1e-9)
    r.check("OPTIMAL_ANGLE_MAX = 60.0", abs(OPTIMAL_VIEW_ANGLE_MAX_DEG - 60.0) < 1e-9)
    r.check("VIEW_REDUNDANCY = 15.0", abs(VIEW_REDUNDANCY_ANGLE_DEG - 15.0) < 1e-9)
    r.check("OPTIMAL MIN < MAX",
            OPTIMAL_VIEW_ANGLE_MIN_DEG < OPTIMAL_VIEW_ANGLE_MAX_DEG)
    r.check("REDUNDANCY < OPTIMAL MIN",
            VIEW_REDUNDANCY_ANGLE_DEG < OPTIMAL_VIEW_ANGLE_MIN_DEG)


# ==================== H. FusionStrategy Enum ====================
def test_fusion_strategy(r: TestResult) -> None:
    print("\n[H] FusionStrategy Enum")
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
        fs = FusionStrategy[name]
        r.check(f"{name} = '{value}'", fs.value == value)

    # requires_history
    r.check("KALMAN_FILTER.requires_history", FusionStrategy.KALMAN_FILTER.requires_history)
    r.check("LEARNED.requires_history", FusionStrategy.LEARNED.requires_history)
    r.check("SIMPLE_AVERAGE !requires_history", not FusionStrategy.SIMPLE_AVERAGE.requires_history)
    r.check("BAYESIAN !requires_history", not FusionStrategy.BAYESIAN.requires_history)

    # is_probabilistic
    r.check("BAYESIAN.is_probabilistic", FusionStrategy.BAYESIAN.is_probabilistic)
    r.check("KALMAN_FILTER.is_probabilistic", FusionStrategy.KALMAN_FILTER.is_probabilistic)
    r.check("RANSAC !is_probabilistic", not FusionStrategy.RANSAC.is_probabilistic)

    # default_weight_type
    weight_types = {
        "SIMPLE_AVERAGE": "uniform",
        "WEIGHTED_AVERAGE": "confidence",
        "BAYESIAN": "posterior",
        "KALMAN_FILTER": "kalman_gain",
        "MAJORITY_VOTING": "vote_count",
        "HIGHEST_CONFIDENCE": "max_confidence",
        "RANSAC": "inlier_count",
        "LEARNED": "learned_weight",
    }
    for name, wt in weight_types.items():
        r.check(f"{name}.default_weight_type = '{wt}'",
                FusionStrategy[name].default_weight_type == wt)

    # to_korean
    korean_map = {
        "SIMPLE_AVERAGE": "단순 평균",
        "WEIGHTED_AVERAGE": "가중 평균",
        "BAYESIAN": "베이지안 융합",
        "KALMAN_FILTER": "칼만 필터",
        "MAJORITY_VOTING": "다수결 투표",
        "HIGHEST_CONFIDENCE": "최고 신뢰도 선택",
        "RANSAC": "RANSAC",
        "LEARNED": "학습 기반",
    }
    for name, kr in korean_map.items():
        r.check(f"{name}.to_korean() = '{kr}'",
                FusionStrategy[name].to_korean() == kr)


# ==================== I. FusionQuality Enum ====================
def test_fusion_quality(r: TestResult) -> None:
    print("\n[I] FusionQuality Enum")
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
        r.check(f"{name}.score_range = ({mn}, {mx})",
                fq.score_range == (mn, mx))

    # is_usable
    r.check("EXCELLENT is_usable", FusionQuality.EXCELLENT.is_usable)
    r.check("GOOD is_usable", FusionQuality.GOOD.is_usable)
    r.check("ACCEPTABLE is_usable", FusionQuality.ACCEPTABLE.is_usable)
    r.check("POOR !is_usable", not FusionQuality.POOR.is_usable)
    r.check("FAILED !is_usable", not FusionQuality.FAILED.is_usable)

    # from_score
    r.check("from_score(1.0) = EXCELLENT", FusionQuality.from_score(1.0) == FusionQuality.EXCELLENT)
    r.check("from_score(0.95) = EXCELLENT", FusionQuality.from_score(0.95) == FusionQuality.EXCELLENT)
    r.check("from_score(0.9) = EXCELLENT", FusionQuality.from_score(0.9) == FusionQuality.EXCELLENT)
    r.check("from_score(0.89) = GOOD", FusionQuality.from_score(0.89) == FusionQuality.GOOD)
    r.check("from_score(0.75) = GOOD", FusionQuality.from_score(0.75) == FusionQuality.GOOD)
    r.check("from_score(0.74) = ACCEPTABLE", FusionQuality.from_score(0.74) == FusionQuality.ACCEPTABLE)
    r.check("from_score(0.6) = ACCEPTABLE", FusionQuality.from_score(0.6) == FusionQuality.ACCEPTABLE)
    r.check("from_score(0.59) = POOR", FusionQuality.from_score(0.59) == FusionQuality.POOR)
    r.check("from_score(0.4) = POOR", FusionQuality.from_score(0.4) == FusionQuality.POOR)
    r.check("from_score(0.39) = FAILED", FusionQuality.from_score(0.39) == FusionQuality.FAILED)
    r.check("from_score(0.0) = FAILED", FusionQuality.from_score(0.0) == FusionQuality.FAILED)

    # from_score 범위 밖
    try:
        FusionQuality.from_score(-0.1)
        r.fail("from_score(-0.1) ValueError")
    except ValueError:
        r.ok("from_score(-0.1) ValueError")

    try:
        FusionQuality.from_score(1.1)
        r.fail("from_score(1.1) ValueError")
    except ValueError:
        r.ok("from_score(1.1) ValueError")

    # to_korean
    korean = {
        "EXCELLENT": "우수",
        "GOOD": "양호",
        "ACCEPTABLE": "허용",
        "POOR": "저조",
        "FAILED": "실패",
    }
    for name, kr in korean.items():
        r.check(f"{name}.to_korean() = '{kr}'",
                FusionQuality[name].to_korean() == kr)


# ==================== J. __all__ ====================
def test_all_exports(r: TestResult) -> None:
    print("\n[J] __all__")
    import shared.constants.fusion_constants as module

    r.check("__all__ 존재", hasattr(module, "__all__"))
    r.check("__all__ 46개", len(module.__all__) == 46, f"실제: {len(module.__all__)}")

    # 모든 __all__ 멤버가 실제 모듈에 존재
    for name in module.__all__:
        r.check(f"'{name}' 모듈 내 존재", hasattr(module, name))


# ==================== K. __init__.py 재수출 ====================
def test_init_reexports(r: TestResult) -> None:
    print("\n[K] __init__.py 재수출")
    from shared.constants import (
        FusionStrategy, FusionQuality,
        MIN_VIEWS_FOR_TRIANGULATION,
        FUSION_CONFIDENCE_THRESHOLD,
        TRIANGULATION_MAX_DEPTH_M,
    )
    from shared.constants.fusion_constants import (
        FusionStrategy as FS_orig,
        FusionQuality as FQ_orig,
    )

    r.check("FusionStrategy identity", FusionStrategy is FS_orig)
    r.check("FusionQuality identity", FusionQuality is FQ_orig)
    r.check("MIN_VIEWS_FOR_TRIANGULATION", MIN_VIEWS_FOR_TRIANGULATION == 2)
    r.check("FUSION_CONFIDENCE_THRESHOLD", abs(FUSION_CONFIDENCE_THRESHOLD - 0.7) < 1e-9)
    r.check("TRIANGULATION_MAX_DEPTH_M", abs(TRIANGULATION_MAX_DEPTH_M - 50.0) < 1e-9)


# ==================== L. 점수 범위 연속성 ====================
def test_quality_score_continuity(r: TestResult) -> None:
    print("\n[L] FusionQuality 점수 범위 연속성")
    from shared.constants.fusion_constants import FusionQuality

    # 모든 점수 범위가 연속적이고 겹치지 않는지 확인
    levels = list(FusionQuality)
    # 높은 순으로 정렬 (EXCELLENT → FAILED)
    levels_sorted = sorted(levels, key=lambda q: q.max_score, reverse=True)

    for i in range(len(levels_sorted) - 1):
        current = levels_sorted[i]
        next_level = levels_sorted[i + 1]
        r.check(f"{current.name}.min = {next_level.name}.max",
                abs(current.min_score - next_level.max_score) < 1e-9)

    # 전체 범위 0.0~1.0
    r.check("최소값 0.0", abs(levels_sorted[-1].min_score - 0.0) < 1e-9)
    r.check("최대값 1.0", abs(levels_sorted[0].max_score - 1.0) < 1e-9)


def main():
    r = TestResult()
    test_typing_modernization(r)          # A
    test_view_requirement_constants(r)    # B
    test_confidence_threshold_constants(r)  # C
    test_weight_constants(r)              # D
    test_triangulation_parameters(r)      # E
    test_fusion_algorithm_parameters(r)   # F
    test_remaining_constants(r)           # G
    test_fusion_strategy(r)               # H
    test_fusion_quality(r)                # I
    test_all_exports(r)                   # J
    test_init_reexports(r)                # K
    test_quality_score_continuity(r)      # L
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
