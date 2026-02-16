# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_occlusion_constants.py

오클루전(가림) 처리 상수 모듈 유닛 테스트
- 오버랩 감지 상수 5개: 값, 타입, 순서 관계
- 깊이 관련 상수 6개: 값, 타입, 순서 관계
- 보간 및 예측 상수 8개: 값, 타입, 논리 관계
- 가시성 판단 상수 6개: 값, 타입, 논리 관계
- 멀티뷰 복구 상수 5개: 값, 타입, 가중치 합
- 오클루전 이벤트 상수 5개: 값, 타입, 논리 관계
- OcclusionType: 7멤버, is_recoverable, typical_duration_frames,
  recommended_strategy, to_korean
- OcclusionSeverity: 5멤버, severity_name, min_overlap, max_overlap,
  overlap_range, is_trackable, needs_recovery, from_overlap, to_korean
- ResolutionStrategy: 7멤버, requires_multiview, requires_history,
  requires_appearance, priority, to_korean
- __all__ 38개 + __version__
- 에지 케이스: identity, hashable, set, iteration order, frozenset/dict
  캐시 완전성, tuple value 불변성, cross-Enum isolation, from_overlap 경계값

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


# ==================== 1. 오버랩 감지 상수 ====================
def test_overlap_constants(r: TestResult) -> None:
    print("\n[1] 오버랩 감지 상수")
    from shared.constants.occlusion_constants import (
        OVERLAP_THRESHOLD,
        SEVERE_OVERLAP_THRESHOLD,
        TOTAL_OVERLAP_THRESHOLD,
        PARTIAL_OVERLAP_MIN_THRESHOLD,
        AREA_OVERLAP_RATIO_THRESHOLD,
    )

    # 값 검증
    r.check("OVERLAP_THRESHOLD = 0.3",
            abs(OVERLAP_THRESHOLD - 0.3) < 1e-9)
    r.check("SEVERE_OVERLAP_THRESHOLD = 0.6",
            abs(SEVERE_OVERLAP_THRESHOLD - 0.6) < 1e-9)
    r.check("TOTAL_OVERLAP_THRESHOLD = 0.8",
            abs(TOTAL_OVERLAP_THRESHOLD - 0.8) < 1e-9)
    r.check("PARTIAL_OVERLAP_MIN_THRESHOLD = 0.15",
            abs(PARTIAL_OVERLAP_MIN_THRESHOLD - 0.15) < 1e-9)
    r.check("AREA_OVERLAP_RATIO_THRESHOLD = 0.5",
            abs(AREA_OVERLAP_RATIO_THRESHOLD - 0.5) < 1e-9)

    # 타입 검증
    r.check("OVERLAP_THRESHOLD float", isinstance(OVERLAP_THRESHOLD, float))
    r.check("SEVERE_OVERLAP_THRESHOLD float", isinstance(SEVERE_OVERLAP_THRESHOLD, float))
    r.check("TOTAL_OVERLAP_THRESHOLD float", isinstance(TOTAL_OVERLAP_THRESHOLD, float))
    r.check("PARTIAL_OVERLAP_MIN_THRESHOLD float",
            isinstance(PARTIAL_OVERLAP_MIN_THRESHOLD, float))
    r.check("AREA_OVERLAP_RATIO_THRESHOLD float",
            isinstance(AREA_OVERLAP_RATIO_THRESHOLD, float))

    # 순서: PARTIAL_OVERLAP_MIN < OVERLAP < AREA_OVERLAP_RATIO < SEVERE_OVERLAP < TOTAL_OVERLAP
    r.check(
        "PARTIAL_MIN < OVERLAP < AREA_RATIO < SEVERE < TOTAL",
        PARTIAL_OVERLAP_MIN_THRESHOLD
        < OVERLAP_THRESHOLD
        < AREA_OVERLAP_RATIO_THRESHOLD
        < SEVERE_OVERLAP_THRESHOLD
        < TOTAL_OVERLAP_THRESHOLD,
        f"순서: {PARTIAL_OVERLAP_MIN_THRESHOLD} < {OVERLAP_THRESHOLD} "
        f"< {AREA_OVERLAP_RATIO_THRESHOLD} < {SEVERE_OVERLAP_THRESHOLD} "
        f"< {TOTAL_OVERLAP_THRESHOLD}",
    )

    # 범위: 모두 0~1 사이
    for name, val in [
        ("OVERLAP_THRESHOLD", OVERLAP_THRESHOLD),
        ("SEVERE_OVERLAP_THRESHOLD", SEVERE_OVERLAP_THRESHOLD),
        ("TOTAL_OVERLAP_THRESHOLD", TOTAL_OVERLAP_THRESHOLD),
        ("PARTIAL_OVERLAP_MIN_THRESHOLD", PARTIAL_OVERLAP_MIN_THRESHOLD),
        ("AREA_OVERLAP_RATIO_THRESHOLD", AREA_OVERLAP_RATIO_THRESHOLD),
    ]:
        r.check(f"{name} 범위 0~1", 0.0 < val <= 1.0, f"값: {val}")


# ==================== 2. 깊이 관련 상수 ====================
def test_depth_constants(r: TestResult) -> None:
    print("\n[2] 깊이 관련 상수")
    from shared.constants.occlusion_constants import (
        DEPTH_DIFFERENCE_THRESHOLD,
        FOREGROUND_BACKGROUND_DEPTH_DIFF_M,
        DEPTH_UNCERTAINTY_TOLERANCE_M,
        DEPTH_SORTING_MIN_DIFF_M,
        MAX_VALID_DEPTH_M,
        MIN_VALID_DEPTH_M,
    )

    # 값 검증
    r.check("DEPTH_DIFFERENCE_THRESHOLD = 0.5",
            abs(DEPTH_DIFFERENCE_THRESHOLD - 0.5) < 1e-9)
    r.check("FOREGROUND_BACKGROUND_DEPTH_DIFF_M = 1.0",
            abs(FOREGROUND_BACKGROUND_DEPTH_DIFF_M - 1.0) < 1e-9)
    r.check("DEPTH_UNCERTAINTY_TOLERANCE_M = 0.3",
            abs(DEPTH_UNCERTAINTY_TOLERANCE_M - 0.3) < 1e-9)
    r.check("DEPTH_SORTING_MIN_DIFF_M = 0.1",
            abs(DEPTH_SORTING_MIN_DIFF_M - 0.1) < 1e-9)
    r.check("MAX_VALID_DEPTH_M = 40.0",
            abs(MAX_VALID_DEPTH_M - 40.0) < 1e-9)
    r.check("MIN_VALID_DEPTH_M = 1.0",
            abs(MIN_VALID_DEPTH_M - 1.0) < 1e-9)

    # 타입 검증
    r.check("DEPTH_DIFFERENCE_THRESHOLD float",
            isinstance(DEPTH_DIFFERENCE_THRESHOLD, float))
    r.check("FOREGROUND_BACKGROUND_DEPTH_DIFF_M float",
            isinstance(FOREGROUND_BACKGROUND_DEPTH_DIFF_M, float))
    r.check("DEPTH_UNCERTAINTY_TOLERANCE_M float",
            isinstance(DEPTH_UNCERTAINTY_TOLERANCE_M, float))
    r.check("DEPTH_SORTING_MIN_DIFF_M float",
            isinstance(DEPTH_SORTING_MIN_DIFF_M, float))
    r.check("MAX_VALID_DEPTH_M float", isinstance(MAX_VALID_DEPTH_M, float))
    r.check("MIN_VALID_DEPTH_M float", isinstance(MIN_VALID_DEPTH_M, float))

    # 순서: DEPTH_SORTING_MIN < DEPTH_UNCERTAINTY < DEPTH_DIFFERENCE < FOREGROUND_BACKGROUND
    r.check(
        "SORTING_MIN < UNCERTAINTY < DIFFERENCE < FOREGROUND_BACKGROUND",
        DEPTH_SORTING_MIN_DIFF_M
        < DEPTH_UNCERTAINTY_TOLERANCE_M
        < DEPTH_DIFFERENCE_THRESHOLD
        < FOREGROUND_BACKGROUND_DEPTH_DIFF_M,
        f"순서: {DEPTH_SORTING_MIN_DIFF_M} < {DEPTH_UNCERTAINTY_TOLERANCE_M} "
        f"< {DEPTH_DIFFERENCE_THRESHOLD} < {FOREGROUND_BACKGROUND_DEPTH_DIFF_M}",
    )

    # MIN < MAX 유효 깊이
    r.check("MIN_VALID_DEPTH < MAX_VALID_DEPTH",
            MIN_VALID_DEPTH_M < MAX_VALID_DEPTH_M)

    # 양수 검증
    for name, val in [
        ("DEPTH_DIFFERENCE_THRESHOLD", DEPTH_DIFFERENCE_THRESHOLD),
        ("FOREGROUND_BACKGROUND_DEPTH_DIFF_M", FOREGROUND_BACKGROUND_DEPTH_DIFF_M),
        ("DEPTH_UNCERTAINTY_TOLERANCE_M", DEPTH_UNCERTAINTY_TOLERANCE_M),
        ("DEPTH_SORTING_MIN_DIFF_M", DEPTH_SORTING_MIN_DIFF_M),
        ("MAX_VALID_DEPTH_M", MAX_VALID_DEPTH_M),
        ("MIN_VALID_DEPTH_M", MIN_VALID_DEPTH_M),
    ]:
        r.check(f"{name} > 0", val > 0.0, f"값: {val}")


# ==================== 3. 보간 및 예측 상수 ====================
def test_interpolation_prediction_constants(r: TestResult) -> None:
    print("\n[3] 보간 및 예측 상수")
    from shared.constants.occlusion_constants import (
        INTERPOLATION_MAX_FRAMES,
        LINEAR_INTERPOLATION_MAX_FRAMES,
        SPLINE_INTERPOLATION_MIN_FRAMES,
        PREDICTION_MAX_FRAMES,
        PREDICTION_CONFIDENCE_DECAY,
        INITIAL_PREDICTION_CONFIDENCE,
        MIN_PREDICTION_CONFIDENCE,
        VELOCITY_PREDICTION_MIN_HISTORY,
    )

    # 값 검증
    r.check("INTERPOLATION_MAX_FRAMES = 10",
            INTERPOLATION_MAX_FRAMES == 10)
    r.check("LINEAR_INTERPOLATION_MAX_FRAMES = 5",
            LINEAR_INTERPOLATION_MAX_FRAMES == 5)
    r.check("SPLINE_INTERPOLATION_MIN_FRAMES = 4",
            SPLINE_INTERPOLATION_MIN_FRAMES == 4)
    r.check("PREDICTION_MAX_FRAMES = 15",
            PREDICTION_MAX_FRAMES == 15)
    r.check("PREDICTION_CONFIDENCE_DECAY = 0.9",
            abs(PREDICTION_CONFIDENCE_DECAY - 0.9) < 1e-9)
    r.check("INITIAL_PREDICTION_CONFIDENCE = 0.95",
            abs(INITIAL_PREDICTION_CONFIDENCE - 0.95) < 1e-9)
    r.check("MIN_PREDICTION_CONFIDENCE = 0.3",
            abs(MIN_PREDICTION_CONFIDENCE - 0.3) < 1e-9)
    r.check("VELOCITY_PREDICTION_MIN_HISTORY = 3",
            VELOCITY_PREDICTION_MIN_HISTORY == 3)

    # 타입 검증
    r.check("INTERPOLATION_MAX_FRAMES int",
            isinstance(INTERPOLATION_MAX_FRAMES, int))
    r.check("LINEAR_INTERPOLATION_MAX_FRAMES int",
            isinstance(LINEAR_INTERPOLATION_MAX_FRAMES, int))
    r.check("SPLINE_INTERPOLATION_MIN_FRAMES int",
            isinstance(SPLINE_INTERPOLATION_MIN_FRAMES, int))
    r.check("PREDICTION_MAX_FRAMES int",
            isinstance(PREDICTION_MAX_FRAMES, int))
    r.check("PREDICTION_CONFIDENCE_DECAY float",
            isinstance(PREDICTION_CONFIDENCE_DECAY, float))
    r.check("INITIAL_PREDICTION_CONFIDENCE float",
            isinstance(INITIAL_PREDICTION_CONFIDENCE, float))
    r.check("MIN_PREDICTION_CONFIDENCE float",
            isinstance(MIN_PREDICTION_CONFIDENCE, float))
    r.check("VELOCITY_PREDICTION_MIN_HISTORY int",
            isinstance(VELOCITY_PREDICTION_MIN_HISTORY, int))

    # 논리: LINEAR < INTERPOLATION < PREDICTION
    r.check(
        "LINEAR < INTERPOLATION < PREDICTION (프레임)",
        LINEAR_INTERPOLATION_MAX_FRAMES
        < INTERPOLATION_MAX_FRAMES
        < PREDICTION_MAX_FRAMES,
        f"{LINEAR_INTERPOLATION_MAX_FRAMES} < {INTERPOLATION_MAX_FRAMES} "
        f"< {PREDICTION_MAX_FRAMES}",
    )

    # 논리: MIN_PREDICTION < PREDICTION_DECAY < INITIAL_PREDICTION
    r.check(
        "MIN_PREDICTION < DECAY < INITIAL (신뢰도)",
        MIN_PREDICTION_CONFIDENCE
        < PREDICTION_CONFIDENCE_DECAY
        < INITIAL_PREDICTION_CONFIDENCE,
        f"{MIN_PREDICTION_CONFIDENCE} < {PREDICTION_CONFIDENCE_DECAY} "
        f"< {INITIAL_PREDICTION_CONFIDENCE}",
    )

    # 신뢰도 범위 0~1
    for name, val in [
        ("PREDICTION_CONFIDENCE_DECAY", PREDICTION_CONFIDENCE_DECAY),
        ("INITIAL_PREDICTION_CONFIDENCE", INITIAL_PREDICTION_CONFIDENCE),
        ("MIN_PREDICTION_CONFIDENCE", MIN_PREDICTION_CONFIDENCE),
    ]:
        r.check(f"{name} 범위 0~1", 0.0 < val <= 1.0, f"값: {val}")

    # 양수 프레임
    for name, val in [
        ("INTERPOLATION_MAX_FRAMES", INTERPOLATION_MAX_FRAMES),
        ("LINEAR_INTERPOLATION_MAX_FRAMES", LINEAR_INTERPOLATION_MAX_FRAMES),
        ("SPLINE_INTERPOLATION_MIN_FRAMES", SPLINE_INTERPOLATION_MIN_FRAMES),
        ("PREDICTION_MAX_FRAMES", PREDICTION_MAX_FRAMES),
        ("VELOCITY_PREDICTION_MIN_HISTORY", VELOCITY_PREDICTION_MIN_HISTORY),
    ]:
        r.check(f"{name} > 0", val > 0, f"값: {val}")


# ==================== 4. 가시성 판단 상수 ====================
def test_visibility_constants(r: TestResult) -> None:
    print("\n[4] 가시성 판단 상수")
    from shared.constants.occlusion_constants import (
        KEYPOINT_VISIBILITY_THRESHOLD,
        MIN_VISIBLE_KEYPOINTS_RATIO,
        MIN_VISIBLE_KEYPOINTS_COUNT,
        CRITICAL_KEYPOINTS_MIN_VISIBLE,
        MIN_VISIBLE_BBOX_RATIO,
        FULLY_VISIBLE_BBOX_RATIO,
    )

    # 값 검증
    r.check("KEYPOINT_VISIBILITY_THRESHOLD = 0.5",
            abs(KEYPOINT_VISIBILITY_THRESHOLD - 0.5) < 1e-9)
    r.check("MIN_VISIBLE_KEYPOINTS_RATIO = 0.3",
            abs(MIN_VISIBLE_KEYPOINTS_RATIO - 0.3) < 1e-9)
    r.check("MIN_VISIBLE_KEYPOINTS_COUNT = 5",
            MIN_VISIBLE_KEYPOINTS_COUNT == 5)
    r.check("CRITICAL_KEYPOINTS_MIN_VISIBLE = 2",
            CRITICAL_KEYPOINTS_MIN_VISIBLE == 2)
    r.check("MIN_VISIBLE_BBOX_RATIO = 0.2",
            abs(MIN_VISIBLE_BBOX_RATIO - 0.2) < 1e-9)
    r.check("FULLY_VISIBLE_BBOX_RATIO = 0.9",
            abs(FULLY_VISIBLE_BBOX_RATIO - 0.9) < 1e-9)

    # 타입 검증
    r.check("KEYPOINT_VISIBILITY_THRESHOLD float",
            isinstance(KEYPOINT_VISIBILITY_THRESHOLD, float))
    r.check("MIN_VISIBLE_KEYPOINTS_RATIO float",
            isinstance(MIN_VISIBLE_KEYPOINTS_RATIO, float))
    r.check("MIN_VISIBLE_KEYPOINTS_COUNT int",
            isinstance(MIN_VISIBLE_KEYPOINTS_COUNT, int))
    r.check("CRITICAL_KEYPOINTS_MIN_VISIBLE int",
            isinstance(CRITICAL_KEYPOINTS_MIN_VISIBLE, int))
    r.check("MIN_VISIBLE_BBOX_RATIO float",
            isinstance(MIN_VISIBLE_BBOX_RATIO, float))
    r.check("FULLY_VISIBLE_BBOX_RATIO float",
            isinstance(FULLY_VISIBLE_BBOX_RATIO, float))

    # 논리: MIN_VISIBLE_BBOX < MIN_VISIBLE_KEYPOINTS_RATIO < KEYPOINT_VISIBILITY < FULLY_VISIBLE_BBOX
    r.check(
        "MIN_BBOX < MIN_KP_RATIO < KP_VISIBILITY < FULLY_BBOX",
        MIN_VISIBLE_BBOX_RATIO
        < MIN_VISIBLE_KEYPOINTS_RATIO
        < KEYPOINT_VISIBILITY_THRESHOLD
        < FULLY_VISIBLE_BBOX_RATIO,
        f"{MIN_VISIBLE_BBOX_RATIO} < {MIN_VISIBLE_KEYPOINTS_RATIO} "
        f"< {KEYPOINT_VISIBILITY_THRESHOLD} < {FULLY_VISIBLE_BBOX_RATIO}",
    )

    # CRITICAL < COUNT
    r.check("CRITICAL_MIN < MIN_COUNT",
            CRITICAL_KEYPOINTS_MIN_VISIBLE < MIN_VISIBLE_KEYPOINTS_COUNT)


# ==================== 5. 멀티뷰 복구 상수 ====================
def test_multiview_constants(r: TestResult) -> None:
    print("\n[5] 멀티뷰 복구 상수")
    from shared.constants.occlusion_constants import (
        CROSS_VIEW_RECOVERY_MIN_VIEWS,
        CROSS_VIEW_RECOVERY_CONFIDENCE,
        CROSS_VIEW_MATCH_DISTANCE_M,
        VIEW_PRIORITY_VISIBILITY_WEIGHT,
        VIEW_PRIORITY_CONFIDENCE_WEIGHT,
    )

    # 값 검증
    r.check("CROSS_VIEW_RECOVERY_MIN_VIEWS = 1",
            CROSS_VIEW_RECOVERY_MIN_VIEWS == 1)
    r.check("CROSS_VIEW_RECOVERY_CONFIDENCE = 0.6",
            abs(CROSS_VIEW_RECOVERY_CONFIDENCE - 0.6) < 1e-9)
    r.check("CROSS_VIEW_MATCH_DISTANCE_M = 0.5",
            abs(CROSS_VIEW_MATCH_DISTANCE_M - 0.5) < 1e-9)
    r.check("VIEW_PRIORITY_VISIBILITY_WEIGHT = 0.6",
            abs(VIEW_PRIORITY_VISIBILITY_WEIGHT - 0.6) < 1e-9)
    r.check("VIEW_PRIORITY_CONFIDENCE_WEIGHT = 0.4",
            abs(VIEW_PRIORITY_CONFIDENCE_WEIGHT - 0.4) < 1e-9)

    # 타입 검증
    r.check("CROSS_VIEW_RECOVERY_MIN_VIEWS int",
            isinstance(CROSS_VIEW_RECOVERY_MIN_VIEWS, int))
    r.check("CROSS_VIEW_RECOVERY_CONFIDENCE float",
            isinstance(CROSS_VIEW_RECOVERY_CONFIDENCE, float))
    r.check("CROSS_VIEW_MATCH_DISTANCE_M float",
            isinstance(CROSS_VIEW_MATCH_DISTANCE_M, float))
    r.check("VIEW_PRIORITY_VISIBILITY_WEIGHT float",
            isinstance(VIEW_PRIORITY_VISIBILITY_WEIGHT, float))
    r.check("VIEW_PRIORITY_CONFIDENCE_WEIGHT float",
            isinstance(VIEW_PRIORITY_CONFIDENCE_WEIGHT, float))

    # 가중치 합 = 1.0
    weight_sum = VIEW_PRIORITY_VISIBILITY_WEIGHT + VIEW_PRIORITY_CONFIDENCE_WEIGHT
    r.check("VIEW_PRIORITY 가중치 합 = 1.0",
            abs(weight_sum - 1.0) < 1e-9,
            f"실제 합: {weight_sum}")

    # 양수 검증
    r.check("CROSS_VIEW_RECOVERY_MIN_VIEWS > 0",
            CROSS_VIEW_RECOVERY_MIN_VIEWS > 0)
    r.check("CROSS_VIEW_MATCH_DISTANCE_M > 0",
            CROSS_VIEW_MATCH_DISTANCE_M > 0.0)


# ==================== 6. 오클루전 이벤트 상수 ====================
def test_occlusion_event_constants(r: TestResult) -> None:
    print("\n[6] 오클루전 이벤트 상수")
    from shared.constants.occlusion_constants import (
        OCCLUSION_START_FRAMES,
        OCCLUSION_END_FRAMES,
        MIN_OCCLUSION_DURATION_FRAMES,
        MAX_OCCLUSION_DURATION_FRAMES,
        OCCLUSION_MERGE_GAP_FRAMES,
    )

    # 값 검증
    r.check("OCCLUSION_START_FRAMES = 2",
            OCCLUSION_START_FRAMES == 2)
    r.check("OCCLUSION_END_FRAMES = 3",
            OCCLUSION_END_FRAMES == 3)
    r.check("MIN_OCCLUSION_DURATION_FRAMES = 2",
            MIN_OCCLUSION_DURATION_FRAMES == 2)
    r.check("MAX_OCCLUSION_DURATION_FRAMES = 45",
            MAX_OCCLUSION_DURATION_FRAMES == 45)
    r.check("OCCLUSION_MERGE_GAP_FRAMES = 3",
            OCCLUSION_MERGE_GAP_FRAMES == 3)

    # 타입 검증
    r.check("OCCLUSION_START_FRAMES int",
            isinstance(OCCLUSION_START_FRAMES, int))
    r.check("OCCLUSION_END_FRAMES int",
            isinstance(OCCLUSION_END_FRAMES, int))
    r.check("MIN_OCCLUSION_DURATION_FRAMES int",
            isinstance(MIN_OCCLUSION_DURATION_FRAMES, int))
    r.check("MAX_OCCLUSION_DURATION_FRAMES int",
            isinstance(MAX_OCCLUSION_DURATION_FRAMES, int))
    r.check("OCCLUSION_MERGE_GAP_FRAMES int",
            isinstance(OCCLUSION_MERGE_GAP_FRAMES, int))

    # 논리: MIN_DURATION <= START < END <= MERGE_GAP << MAX_DURATION
    r.check("MIN_DURATION <= START",
            MIN_OCCLUSION_DURATION_FRAMES <= OCCLUSION_START_FRAMES)
    r.check("START < END",
            OCCLUSION_START_FRAMES < OCCLUSION_END_FRAMES)
    r.check("END <= MERGE_GAP",
            OCCLUSION_END_FRAMES <= OCCLUSION_MERGE_GAP_FRAMES)
    r.check("MERGE_GAP << MAX_DURATION",
            OCCLUSION_MERGE_GAP_FRAMES < MAX_OCCLUSION_DURATION_FRAMES)

    # 양수 검증
    for name, val in [
        ("OCCLUSION_START_FRAMES", OCCLUSION_START_FRAMES),
        ("OCCLUSION_END_FRAMES", OCCLUSION_END_FRAMES),
        ("MIN_OCCLUSION_DURATION_FRAMES", MIN_OCCLUSION_DURATION_FRAMES),
        ("MAX_OCCLUSION_DURATION_FRAMES", MAX_OCCLUSION_DURATION_FRAMES),
        ("OCCLUSION_MERGE_GAP_FRAMES", OCCLUSION_MERGE_GAP_FRAMES),
    ]:
        r.check(f"{name} > 0", val > 0, f"값: {val}")


# ==================== 7. OcclusionType 기본 ====================
def test_occlusion_type_basics(r: TestResult) -> None:
    print("\n[7] OcclusionType 기본")
    from shared.constants.occlusion_constants import OcclusionType
    from enum import Enum

    # 멤버 수
    r.check("OcclusionType 7개 멤버", len(OcclusionType) == 7,
            f"실제: {len(OcclusionType)}")

    # Enum 서브클래스
    r.check("Enum 서브클래스", issubclass(OcclusionType, Enum))

    # 각 멤버 이름/값
    expected = {
        "SELF": "self",
        "INTER_PLAYER": "inter_player",
        "COURT_OBJECT": "court_object",
        "OUT_OF_VIEW": "out_of_view",
        "MOTION_BLUR": "motion_blur",
        "LIGHTING": "lighting",
        "UNKNOWN": "unknown",
    }
    for name, value in expected.items():
        member = OcclusionType[name]
        r.check(f"OcclusionType.{name} = '{value}'", member.value == value)

    # @unique (중복 값 없음)
    values = [m.value for m in OcclusionType]
    r.check("@unique (중복 값 없음)", len(values) == len(set(values)))


# ==================== 8. OcclusionType.is_recoverable ====================
def test_occlusion_type_is_recoverable(r: TestResult) -> None:
    print("\n[8] OcclusionType.is_recoverable")
    from shared.constants.occlusion_constants import OcclusionType

    recoverable_map = {
        OcclusionType.SELF: True,
        OcclusionType.INTER_PLAYER: True,
        OcclusionType.COURT_OBJECT: True,
        OcclusionType.MOTION_BLUR: True,
        OcclusionType.OUT_OF_VIEW: False,
        OcclusionType.LIGHTING: False,
        OcclusionType.UNKNOWN: False,
    }
    for member, expected in recoverable_map.items():
        r.check(f"{member.name}.is_recoverable = {expected}",
                member.is_recoverable is expected)

    # 복구 가능 멤버 수 = 4
    recoverable_count = sum(1 for m in OcclusionType if m.is_recoverable)
    r.check("복구 가능 멤버 4개", recoverable_count == 4,
            f"실제: {recoverable_count}")

    # bool 타입
    for member in OcclusionType:
        r.check(f"{member.name}.is_recoverable bool 타입",
                isinstance(member.is_recoverable, bool))


# ==================== 9. OcclusionType.typical_duration_frames ====================
def test_occlusion_type_duration(r: TestResult) -> None:
    print("\n[9] OcclusionType.typical_duration_frames")
    from shared.constants.occlusion_constants import OcclusionType

    expected_durations = {
        OcclusionType.SELF: (1, 10),
        OcclusionType.INTER_PLAYER: (3, 30),
        OcclusionType.COURT_OBJECT: (5, 45),
        OcclusionType.OUT_OF_VIEW: (10, 100),
        OcclusionType.MOTION_BLUR: (1, 5),
        OcclusionType.LIGHTING: (5, 60),
        OcclusionType.UNKNOWN: (1, 30),
    }
    for member, expected in expected_durations.items():
        duration = member.typical_duration_frames
        r.check(f"{member.name}.typical_duration = {expected}",
                duration == expected, f"실제: {duration}")
        # tuple 타입
        r.check(f"{member.name} tuple 타입", isinstance(duration, tuple))
        # 길이 2
        r.check(f"{member.name} 길이 2", len(duration) == 2)
        # min < max
        r.check(f"{member.name} min < max", duration[0] < duration[1],
                f"{duration[0]} < {duration[1]}")
        # 양수
        r.check(f"{member.name} 양수 범위", duration[0] > 0 and duration[1] > 0)


# ==================== 10. OcclusionType.recommended_strategy ====================
def test_occlusion_type_recommended_strategy(r: TestResult) -> None:
    print("\n[10] OcclusionType.recommended_strategy (Cross-Enum)")
    from shared.constants.occlusion_constants import (
        OcclusionType, ResolutionStrategy,
    )

    expected_strategies = {
        OcclusionType.SELF: ResolutionStrategy.INTERPOLATION,
        OcclusionType.INTER_PLAYER: ResolutionStrategy.CROSS_VIEW,
        OcclusionType.COURT_OBJECT: ResolutionStrategy.CROSS_VIEW,
        OcclusionType.OUT_OF_VIEW: ResolutionStrategy.PREDICTION,
        OcclusionType.MOTION_BLUR: ResolutionStrategy.INTERPOLATION,
        OcclusionType.LIGHTING: ResolutionStrategy.CROSS_VIEW,
        OcclusionType.UNKNOWN: ResolutionStrategy.PREDICTION,
    }
    for member, expected in expected_strategies.items():
        strategy = member.recommended_strategy
        r.check(f"{member.name} -> {expected.name}",
                strategy == expected,
                f"실제: {strategy}")
        # ResolutionStrategy 타입 확인
        r.check(f"{member.name}.recommended_strategy ResolutionStrategy 타입",
                isinstance(strategy, ResolutionStrategy))

    # 사용된 전략 종류 확인
    used_strategies = set(m.recommended_strategy for m in OcclusionType)
    r.check("사용된 전략: INTERPOLATION, CROSS_VIEW, PREDICTION",
            used_strategies == {
                ResolutionStrategy.INTERPOLATION,
                ResolutionStrategy.CROSS_VIEW,
                ResolutionStrategy.PREDICTION,
            })


# ==================== 11. OcclusionType.to_korean ====================
def test_occlusion_type_korean(r: TestResult) -> None:
    print("\n[11] OcclusionType.to_korean")
    from shared.constants.occlusion_constants import OcclusionType

    korean_map = {
        OcclusionType.SELF: "셀프 오클루전",
        OcclusionType.INTER_PLAYER: "선수 간 오클루전",
        OcclusionType.COURT_OBJECT: "코트 오브젝트 오클루전",
        OcclusionType.OUT_OF_VIEW: "프레임 아웃",
        OcclusionType.MOTION_BLUR: "모션 블러",
        OcclusionType.LIGHTING: "조명 오클루전",
        OcclusionType.UNKNOWN: "미분류",
    }
    for member, expected_kr in korean_map.items():
        result = member.to_korean()
        r.check(f"{member.name} -> '{expected_kr}'",
                result == expected_kr, f"실제: '{result}'")
        r.check(f"{member.name}.to_korean() str 타입",
                isinstance(result, str))
        r.check(f"{member.name}.to_korean() 비어있지 않음",
                len(result) > 0)


# ==================== 12. OcclusionSeverity 기본 ====================
def test_occlusion_severity_basics(r: TestResult) -> None:
    print("\n[12] OcclusionSeverity 기본")
    from shared.constants.occlusion_constants import OcclusionSeverity
    from enum import Enum

    # 멤버 수
    r.check("OcclusionSeverity 5개 멤버", len(OcclusionSeverity) == 5,
            f"실제: {len(OcclusionSeverity)}")

    # Enum 서브클래스
    r.check("Enum 서브클래스", issubclass(OcclusionSeverity, Enum))

    # 각 멤버 이름과 tuple 값
    expected_values = {
        "NONE": ("none", 0.0, 0.0),
        "MINOR": ("minor", 0.0, 0.2),
        "PARTIAL": ("partial", 0.2, 0.5),
        "SEVERE": ("severe", 0.5, 0.8),
        "TOTAL": ("total", 0.8, 1.0),
    }
    for name, value in expected_values.items():
        member = OcclusionSeverity[name]
        r.check(f"OcclusionSeverity.{name}.value = {value}",
                member.value == value, f"실제: {member.value}")

    # @unique (중복 값 없음)
    values = [m.value for m in OcclusionSeverity]
    r.check("@unique (중복 값 없음)", len(values) == len(set(values)))


# ==================== 13. OcclusionSeverity 속성 ====================
def test_occlusion_severity_properties(r: TestResult) -> None:
    print("\n[13] OcclusionSeverity 속성")
    from shared.constants.occlusion_constants import OcclusionSeverity

    # severity_name
    severity_names = {
        OcclusionSeverity.NONE: "none",
        OcclusionSeverity.MINOR: "minor",
        OcclusionSeverity.PARTIAL: "partial",
        OcclusionSeverity.SEVERE: "severe",
        OcclusionSeverity.TOTAL: "total",
    }
    for member, expected in severity_names.items():
        r.check(f"{member.name}.severity_name = '{expected}'",
                member.severity_name == expected)
        r.check(f"{member.name}.severity_name str 타입",
                isinstance(member.severity_name, str))

    # min_overlap
    min_overlaps = {
        OcclusionSeverity.NONE: 0.0,
        OcclusionSeverity.MINOR: 0.0,
        OcclusionSeverity.PARTIAL: 0.2,
        OcclusionSeverity.SEVERE: 0.5,
        OcclusionSeverity.TOTAL: 0.8,
    }
    for member, expected in min_overlaps.items():
        r.check(f"{member.name}.min_overlap = {expected}",
                abs(member.min_overlap - expected) < 1e-9)
        r.check(f"{member.name}.min_overlap float 타입",
                isinstance(member.min_overlap, float))

    # max_overlap
    max_overlaps = {
        OcclusionSeverity.NONE: 0.0,
        OcclusionSeverity.MINOR: 0.2,
        OcclusionSeverity.PARTIAL: 0.5,
        OcclusionSeverity.SEVERE: 0.8,
        OcclusionSeverity.TOTAL: 1.0,
    }
    for member, expected in max_overlaps.items():
        r.check(f"{member.name}.max_overlap = {expected}",
                abs(member.max_overlap - expected) < 1e-9)
        r.check(f"{member.name}.max_overlap float 타입",
                isinstance(member.max_overlap, float))

    # overlap_range
    expected_ranges = {
        OcclusionSeverity.NONE: (0.0, 0.0),
        OcclusionSeverity.MINOR: (0.0, 0.2),
        OcclusionSeverity.PARTIAL: (0.2, 0.5),
        OcclusionSeverity.SEVERE: (0.5, 0.8),
        OcclusionSeverity.TOTAL: (0.8, 1.0),
    }
    for member, expected in expected_ranges.items():
        overlap_range = member.overlap_range
        r.check(f"{member.name}.overlap_range = {expected}",
                overlap_range == expected, f"실제: {overlap_range}")
        r.check(f"{member.name}.overlap_range tuple 타입",
                isinstance(overlap_range, tuple))
        r.check(f"{member.name}.overlap_range 길이 2",
                len(overlap_range) == 2)


# ==================== 14. OcclusionSeverity.is_trackable / needs_recovery ====================
def test_occlusion_severity_trackable_recovery(r: TestResult) -> None:
    print("\n[14] OcclusionSeverity.is_trackable / needs_recovery")
    from shared.constants.occlusion_constants import OcclusionSeverity

    # is_trackable: NONE/MINOR/PARTIAL -> True, SEVERE/TOTAL -> False
    trackable_map = {
        OcclusionSeverity.NONE: True,
        OcclusionSeverity.MINOR: True,
        OcclusionSeverity.PARTIAL: True,
        OcclusionSeverity.SEVERE: False,
        OcclusionSeverity.TOTAL: False,
    }
    for member, expected in trackable_map.items():
        r.check(f"{member.name}.is_trackable = {expected}",
                member.is_trackable is expected)

    # needs_recovery: PARTIAL/SEVERE/TOTAL -> True, NONE/MINOR -> False
    recovery_map = {
        OcclusionSeverity.NONE: False,
        OcclusionSeverity.MINOR: False,
        OcclusionSeverity.PARTIAL: True,
        OcclusionSeverity.SEVERE: True,
        OcclusionSeverity.TOTAL: True,
    }
    for member, expected in recovery_map.items():
        r.check(f"{member.name}.needs_recovery = {expected}",
                member.needs_recovery is expected)

    # 교차 검증: PARTIAL만 is_trackable + needs_recovery 둘 다 True
    for member in OcclusionSeverity:
        both_true = member.is_trackable and member.needs_recovery
        if member == OcclusionSeverity.PARTIAL:
            r.check(f"{member.name} is_trackable + needs_recovery 둘 다 True",
                    both_true is True)
        else:
            r.check(f"{member.name} is_trackable + needs_recovery 둘 다 True 아님",
                    both_true is False)

    # trackable 멤버 수 = 3
    trackable_count = sum(1 for m in OcclusionSeverity if m.is_trackable)
    r.check("trackable 멤버 3개", trackable_count == 3,
            f"실제: {trackable_count}")

    # needs_recovery 멤버 수 = 3
    recovery_count = sum(1 for m in OcclusionSeverity if m.needs_recovery)
    r.check("needs_recovery 멤버 3개", recovery_count == 3,
            f"실제: {recovery_count}")


# ==================== 15. OcclusionSeverity.from_overlap 경계값 ====================
def test_occlusion_severity_from_overlap(r: TestResult) -> None:
    print("\n[15] OcclusionSeverity.from_overlap 경계값")
    from shared.constants.occlusion_constants import OcclusionSeverity

    # 정확 경계값 테스트
    # NONE 범위=(0.0,0.0)이므로 overlap=0.0은 0.0<=0.0<0.0 False -> MINOR로 분류됨
    boundary_tests = [
        (0.0, OcclusionSeverity.MINOR),
        (0.1, OcclusionSeverity.MINOR),
        (0.2, OcclusionSeverity.PARTIAL),
        (0.3, OcclusionSeverity.PARTIAL),
        (0.5, OcclusionSeverity.SEVERE),
        (0.6, OcclusionSeverity.SEVERE),
        (0.8, OcclusionSeverity.TOTAL),
        (0.9, OcclusionSeverity.TOTAL),
        (1.0, OcclusionSeverity.TOTAL),
    ]
    for overlap, expected in boundary_tests:
        result = OcclusionSeverity.from_overlap(overlap)
        r.check(f"from_overlap({overlap}) -> {expected.name}",
                result == expected,
                f"실제: {result.name}")

    # 경계 직전 값 테스트
    epsilon_tests = [
        (0.19999, OcclusionSeverity.MINOR),
        (0.20001, OcclusionSeverity.PARTIAL),
        (0.49999, OcclusionSeverity.PARTIAL),
        (0.50001, OcclusionSeverity.SEVERE),
        (0.79999, OcclusionSeverity.SEVERE),
        (0.80001, OcclusionSeverity.TOTAL),
    ]
    for overlap, expected in epsilon_tests:
        result = OcclusionSeverity.from_overlap(overlap)
        r.check(f"from_overlap({overlap}) -> {expected.name}",
                result == expected,
                f"실제: {result.name}")

    # 음수 입력 -> clamped to 0.0 -> NONE 범위(0.0,0.0) 통과 -> MINOR
    result_neg = OcclusionSeverity.from_overlap(-0.5)
    r.check("from_overlap(-0.5) -> MINOR (clamped to 0.0)",
            result_neg == OcclusionSeverity.MINOR,
            f"실제: {result_neg.name}")

    result_neg2 = OcclusionSeverity.from_overlap(-100.0)
    r.check("from_overlap(-100.0) -> MINOR (clamped to 0.0)",
            result_neg2 == OcclusionSeverity.MINOR,
            f"실제: {result_neg2.name}")

    # 1.0 초과 입력 -> clamped to 1.0 -> TOTAL
    result_over = OcclusionSeverity.from_overlap(1.5)
    r.check("from_overlap(1.5) -> TOTAL (clamped)",
            result_over == OcclusionSeverity.TOTAL,
            f"실제: {result_over.name}")

    result_over2 = OcclusionSeverity.from_overlap(100.0)
    r.check("from_overlap(100.0) -> TOTAL (clamped)",
            result_over2 == OcclusionSeverity.TOTAL,
            f"실제: {result_over2.name}")

    # 반환 타입 확인
    for overlap in [0.0, 0.1, 0.3, 0.6, 0.9]:
        result = OcclusionSeverity.from_overlap(overlap)
        r.check(f"from_overlap({overlap}) OcclusionSeverity 타입",
                isinstance(result, OcclusionSeverity))


# ==================== 16. OcclusionSeverity.to_korean ====================
def test_occlusion_severity_korean(r: TestResult) -> None:
    print("\n[16] OcclusionSeverity.to_korean")
    from shared.constants.occlusion_constants import OcclusionSeverity

    korean_map = {
        OcclusionSeverity.NONE: "없음",
        OcclusionSeverity.MINOR: "경미",
        OcclusionSeverity.PARTIAL: "부분",
        OcclusionSeverity.SEVERE: "심각",
        OcclusionSeverity.TOTAL: "완전",
    }
    for member, expected_kr in korean_map.items():
        result = member.to_korean()
        r.check(f"{member.name} -> '{expected_kr}'",
                result == expected_kr, f"실제: '{result}'")
        r.check(f"{member.name}.to_korean() str 타입",
                isinstance(result, str))
        r.check(f"{member.name}.to_korean() 비어있지 않음",
                len(result) > 0)


# ==================== 17. ResolutionStrategy 기본 ====================
def test_resolution_strategy_basics(r: TestResult) -> None:
    print("\n[17] ResolutionStrategy 기본")
    from shared.constants.occlusion_constants import ResolutionStrategy
    from enum import Enum

    # 멤버 수
    r.check("ResolutionStrategy 7개 멤버", len(ResolutionStrategy) == 7,
            f"실제: {len(ResolutionStrategy)}")

    # Enum 서브클래스
    r.check("Enum 서브클래스", issubclass(ResolutionStrategy, Enum))

    # 각 멤버 이름/값
    expected = {
        "CROSS_VIEW": "cross_view",
        "INTERPOLATION": "interpolation",
        "PREDICTION": "prediction",
        "KALMAN": "kalman",
        "APPEARANCE_MATCHING": "appearance_matching",
        "HYBRID": "hybrid",
        "NONE": "none",
    }
    for name, value in expected.items():
        member = ResolutionStrategy[name]
        r.check(f"ResolutionStrategy.{name} = '{value}'",
                member.value == value)

    # @unique (중복 값 없음)
    values = [m.value for m in ResolutionStrategy]
    r.check("@unique (중복 값 없음)", len(values) == len(set(values)))


# ==================== 18. ResolutionStrategy.requires_multiview ====================
def test_resolution_strategy_requires_multiview(r: TestResult) -> None:
    print("\n[18] ResolutionStrategy.requires_multiview")
    from shared.constants.occlusion_constants import ResolutionStrategy

    multiview_map = {
        ResolutionStrategy.CROSS_VIEW: True,
        ResolutionStrategy.INTERPOLATION: False,
        ResolutionStrategy.PREDICTION: False,
        ResolutionStrategy.KALMAN: False,
        ResolutionStrategy.APPEARANCE_MATCHING: False,
        ResolutionStrategy.HYBRID: False,
        ResolutionStrategy.NONE: False,
    }
    for member, expected in multiview_map.items():
        r.check(f"{member.name}.requires_multiview = {expected}",
                member.requires_multiview is expected)

    # 멀티뷰 필요 멤버 수 = 1
    mv_count = sum(1 for m in ResolutionStrategy if m.requires_multiview)
    r.check("멀티뷰 필요 멤버 1개", mv_count == 1, f"실제: {mv_count}")


# ==================== 19. ResolutionStrategy.requires_history ====================
def test_resolution_strategy_requires_history(r: TestResult) -> None:
    print("\n[19] ResolutionStrategy.requires_history")
    from shared.constants.occlusion_constants import ResolutionStrategy

    history_map = {
        ResolutionStrategy.INTERPOLATION: True,
        ResolutionStrategy.PREDICTION: True,
        ResolutionStrategy.KALMAN: True,
        ResolutionStrategy.CROSS_VIEW: False,
        ResolutionStrategy.APPEARANCE_MATCHING: False,
        ResolutionStrategy.HYBRID: False,
        ResolutionStrategy.NONE: False,
    }
    for member, expected in history_map.items():
        r.check(f"{member.name}.requires_history = {expected}",
                member.requires_history is expected)

    # 히스토리 필요 멤버 수 = 3
    hist_count = sum(1 for m in ResolutionStrategy if m.requires_history)
    r.check("히스토리 필요 멤버 3개", hist_count == 3, f"실제: {hist_count}")


# ==================== 20. ResolutionStrategy.requires_appearance ====================
def test_resolution_strategy_requires_appearance(r: TestResult) -> None:
    print("\n[20] ResolutionStrategy.requires_appearance")
    from shared.constants.occlusion_constants import ResolutionStrategy

    appearance_map = {
        ResolutionStrategy.APPEARANCE_MATCHING: True,
        ResolutionStrategy.HYBRID: True,
        ResolutionStrategy.CROSS_VIEW: False,
        ResolutionStrategy.INTERPOLATION: False,
        ResolutionStrategy.PREDICTION: False,
        ResolutionStrategy.KALMAN: False,
        ResolutionStrategy.NONE: False,
    }
    for member, expected in appearance_map.items():
        r.check(f"{member.name}.requires_appearance = {expected}",
                member.requires_appearance is expected)

    # 외관 필요 멤버 수 = 2
    app_count = sum(1 for m in ResolutionStrategy if m.requires_appearance)
    r.check("외관 필요 멤버 2개", app_count == 2, f"실제: {app_count}")


# ==================== 21. ResolutionStrategy.priority ====================
def test_resolution_strategy_priority(r: TestResult) -> None:
    print("\n[21] ResolutionStrategy.priority")
    from shared.constants.occlusion_constants import ResolutionStrategy

    priority_map = {
        ResolutionStrategy.CROSS_VIEW: 1,
        ResolutionStrategy.KALMAN: 2,
        ResolutionStrategy.INTERPOLATION: 3,
        ResolutionStrategy.PREDICTION: 4,
        ResolutionStrategy.APPEARANCE_MATCHING: 5,
        ResolutionStrategy.HYBRID: 6,
        ResolutionStrategy.NONE: 99,
    }
    for member, expected in priority_map.items():
        r.check(f"{member.name}.priority = {expected}",
                member.priority == expected,
                f"실제: {member.priority}")
        r.check(f"{member.name}.priority int 타입",
                isinstance(member.priority, int))

    # 우선순위 값 유일성 (NONE 제외, 각 전략마다 고유한 우선순위)
    non_none = [m for m in ResolutionStrategy if m != ResolutionStrategy.NONE]
    priorities = [m.priority for m in non_none]
    r.check("우선순위 값 유일 (NONE 제외, 6개)",
            len(priorities) == len(set(priorities)),
            f"실제: {priorities}")

    # 우선순위 기준 정렬 시 CROSS_VIEW가 1순위
    sorted_by_priority = sorted(non_none, key=lambda m: m.priority)
    r.check("우선순위 정렬 1위 = CROSS_VIEW",
            sorted_by_priority[0] == ResolutionStrategy.CROSS_VIEW)
    r.check("우선순위 정렬 2위 = KALMAN",
            sorted_by_priority[1] == ResolutionStrategy.KALMAN)
    r.check("우선순위 정렬 마지막 = HYBRID",
            sorted_by_priority[-1] == ResolutionStrategy.HYBRID)

    # NONE은 가장 낮은 우선순위
    r.check("NONE 우선순위 최저 (99)",
            ResolutionStrategy.NONE.priority == 99)
    r.check("NONE 우선순위 > 모든 다른 전략",
            all(ResolutionStrategy.NONE.priority > m.priority
                for m in ResolutionStrategy if m != ResolutionStrategy.NONE))


# ==================== 22. ResolutionStrategy.to_korean ====================
def test_resolution_strategy_korean(r: TestResult) -> None:
    print("\n[22] ResolutionStrategy.to_korean")
    from shared.constants.occlusion_constants import ResolutionStrategy

    korean_map = {
        ResolutionStrategy.CROSS_VIEW: "크로스뷰 복구",
        ResolutionStrategy.INTERPOLATION: "보간",
        ResolutionStrategy.PREDICTION: "예측",
        ResolutionStrategy.KALMAN: "칼만 필터",
        ResolutionStrategy.APPEARANCE_MATCHING: "외관 매칭",
        ResolutionStrategy.HYBRID: "하이브리드",
        ResolutionStrategy.NONE: "없음",
    }
    for member, expected_kr in korean_map.items():
        result = member.to_korean()
        r.check(f"{member.name} -> '{expected_kr}'",
                result == expected_kr, f"실제: '{result}'")
        r.check(f"{member.name}.to_korean() str 타입",
                isinstance(result, str))
        r.check(f"{member.name}.to_korean() 비어있지 않음",
                len(result) > 0)


# ==================== 23. __all__ export 완전성 ====================
def test_all_exports(r: TestResult) -> None:
    print("\n[23] __all__ export 완전성")
    import shared.constants.occlusion_constants as module

    r.check("__all__ 존재", hasattr(module, "__all__"))
    r.check("__all__ 38개", len(module.__all__) == 38,
            f"실제: {len(module.__all__)}개")

    # 중복 없음
    r.check("__all__ 중복 없음",
            len(module.__all__) == len(set(module.__all__)))

    # 모든 export가 실제 존재
    for name in module.__all__:
        r.check(f"'{name}' 존재", hasattr(module, name))

    # 35개 상수 포함 확인
    expected_constants = [
        # 오버랩 감지
        "OVERLAP_THRESHOLD", "SEVERE_OVERLAP_THRESHOLD",
        "TOTAL_OVERLAP_THRESHOLD", "PARTIAL_OVERLAP_MIN_THRESHOLD",
        "AREA_OVERLAP_RATIO_THRESHOLD",
        # 깊이 관련
        "DEPTH_DIFFERENCE_THRESHOLD", "FOREGROUND_BACKGROUND_DEPTH_DIFF_M",
        "DEPTH_UNCERTAINTY_TOLERANCE_M", "DEPTH_SORTING_MIN_DIFF_M",
        "MAX_VALID_DEPTH_M", "MIN_VALID_DEPTH_M",
        # 보간 및 예측
        "INTERPOLATION_MAX_FRAMES", "LINEAR_INTERPOLATION_MAX_FRAMES",
        "SPLINE_INTERPOLATION_MIN_FRAMES", "PREDICTION_MAX_FRAMES",
        "PREDICTION_CONFIDENCE_DECAY", "INITIAL_PREDICTION_CONFIDENCE",
        "MIN_PREDICTION_CONFIDENCE", "VELOCITY_PREDICTION_MIN_HISTORY",
        # 가시성 판단
        "KEYPOINT_VISIBILITY_THRESHOLD", "MIN_VISIBLE_KEYPOINTS_RATIO",
        "MIN_VISIBLE_KEYPOINTS_COUNT", "CRITICAL_KEYPOINTS_MIN_VISIBLE",
        "MIN_VISIBLE_BBOX_RATIO", "FULLY_VISIBLE_BBOX_RATIO",
        # 멀티뷰 복구
        "CROSS_VIEW_RECOVERY_MIN_VIEWS", "CROSS_VIEW_RECOVERY_CONFIDENCE",
        "CROSS_VIEW_MATCH_DISTANCE_M", "VIEW_PRIORITY_VISIBILITY_WEIGHT",
        "VIEW_PRIORITY_CONFIDENCE_WEIGHT",
        # 오클루전 이벤트
        "OCCLUSION_START_FRAMES", "OCCLUSION_END_FRAMES",
        "MIN_OCCLUSION_DURATION_FRAMES", "MAX_OCCLUSION_DURATION_FRAMES",
        "OCCLUSION_MERGE_GAP_FRAMES",
    ]
    for name in expected_constants:
        r.check(f"'{name}' in __all__", name in module.__all__)

    # 3개 Enum 포함 확인
    r.check("'OcclusionType' in __all__", "OcclusionType" in module.__all__)
    r.check("'OcclusionSeverity' in __all__", "OcclusionSeverity" in module.__all__)
    r.check("'ResolutionStrategy' in __all__", "ResolutionStrategy" in module.__all__)


# ==================== 24. __version__ ====================
def test_version(r: TestResult) -> None:
    print("\n[24] __version__")
    import shared.constants.occlusion_constants as module

    r.check("__version__ 존재", hasattr(module, "__version__"))
    r.check("__version__ = '1.1.0'", module.__version__ == "1.1.0",
            f"실제: {module.__version__}")
    r.check("__version__ str 타입", isinstance(module.__version__, str))


# ==================== 25. frozenset 캐시 완전성 ====================
def test_frozenset_caches(r: TestResult) -> None:
    print("\n[25] frozenset 캐시 완전성")
    from shared.constants.occlusion_constants import (
        OcclusionType, OcclusionSeverity, ResolutionStrategy,
        _OCCLUSION_TYPE_IS_RECOVERABLE,
        _OCCLUSION_SEVERITY_IS_TRACKABLE,
        _OCCLUSION_SEVERITY_NEEDS_RECOVERY,
        _RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW,
        _RESOLUTION_STRATEGY_REQUIRES_HISTORY,
        _RESOLUTION_STRATEGY_REQUIRES_APPEARANCE,
    )

    # 타입 검증
    r.check("_OCCLUSION_TYPE_IS_RECOVERABLE frozenset",
            isinstance(_OCCLUSION_TYPE_IS_RECOVERABLE, frozenset))
    r.check("_OCCLUSION_SEVERITY_IS_TRACKABLE frozenset",
            isinstance(_OCCLUSION_SEVERITY_IS_TRACKABLE, frozenset))
    r.check("_OCCLUSION_SEVERITY_NEEDS_RECOVERY frozenset",
            isinstance(_OCCLUSION_SEVERITY_NEEDS_RECOVERY, frozenset))
    r.check("_RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW frozenset",
            isinstance(_RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW, frozenset))
    r.check("_RESOLUTION_STRATEGY_REQUIRES_HISTORY frozenset",
            isinstance(_RESOLUTION_STRATEGY_REQUIRES_HISTORY, frozenset))
    r.check("_RESOLUTION_STRATEGY_REQUIRES_APPEARANCE frozenset",
            isinstance(_RESOLUTION_STRATEGY_REQUIRES_APPEARANCE, frozenset))

    # 크기 검증
    r.check("_OCCLUSION_TYPE_IS_RECOVERABLE 4개",
            len(_OCCLUSION_TYPE_IS_RECOVERABLE) == 4)
    r.check("_OCCLUSION_SEVERITY_IS_TRACKABLE 3개",
            len(_OCCLUSION_SEVERITY_IS_TRACKABLE) == 3)
    r.check("_OCCLUSION_SEVERITY_NEEDS_RECOVERY 3개",
            len(_OCCLUSION_SEVERITY_NEEDS_RECOVERY) == 3)
    r.check("_RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW 1개",
            len(_RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW) == 1)
    r.check("_RESOLUTION_STRATEGY_REQUIRES_HISTORY 3개",
            len(_RESOLUTION_STRATEGY_REQUIRES_HISTORY) == 3)
    r.check("_RESOLUTION_STRATEGY_REQUIRES_APPEARANCE 2개",
            len(_RESOLUTION_STRATEGY_REQUIRES_APPEARANCE) == 2)

    # 멤버십 검증
    r.check("SELF in _IS_RECOVERABLE",
            OcclusionType.SELF in _OCCLUSION_TYPE_IS_RECOVERABLE)
    r.check("INTER_PLAYER in _IS_RECOVERABLE",
            OcclusionType.INTER_PLAYER in _OCCLUSION_TYPE_IS_RECOVERABLE)
    r.check("COURT_OBJECT in _IS_RECOVERABLE",
            OcclusionType.COURT_OBJECT in _OCCLUSION_TYPE_IS_RECOVERABLE)
    r.check("MOTION_BLUR in _IS_RECOVERABLE",
            OcclusionType.MOTION_BLUR in _OCCLUSION_TYPE_IS_RECOVERABLE)
    r.check("OUT_OF_VIEW not in _IS_RECOVERABLE",
            OcclusionType.OUT_OF_VIEW not in _OCCLUSION_TYPE_IS_RECOVERABLE)

    r.check("NONE in _IS_TRACKABLE",
            OcclusionSeverity.NONE in _OCCLUSION_SEVERITY_IS_TRACKABLE)
    r.check("MINOR in _IS_TRACKABLE",
            OcclusionSeverity.MINOR in _OCCLUSION_SEVERITY_IS_TRACKABLE)
    r.check("PARTIAL in _IS_TRACKABLE",
            OcclusionSeverity.PARTIAL in _OCCLUSION_SEVERITY_IS_TRACKABLE)
    r.check("SEVERE not in _IS_TRACKABLE",
            OcclusionSeverity.SEVERE not in _OCCLUSION_SEVERITY_IS_TRACKABLE)

    r.check("PARTIAL in _NEEDS_RECOVERY",
            OcclusionSeverity.PARTIAL in _OCCLUSION_SEVERITY_NEEDS_RECOVERY)
    r.check("SEVERE in _NEEDS_RECOVERY",
            OcclusionSeverity.SEVERE in _OCCLUSION_SEVERITY_NEEDS_RECOVERY)
    r.check("TOTAL in _NEEDS_RECOVERY",
            OcclusionSeverity.TOTAL in _OCCLUSION_SEVERITY_NEEDS_RECOVERY)
    r.check("NONE not in _NEEDS_RECOVERY",
            OcclusionSeverity.NONE not in _OCCLUSION_SEVERITY_NEEDS_RECOVERY)

    r.check("CROSS_VIEW in _REQUIRES_MULTIVIEW",
            ResolutionStrategy.CROSS_VIEW in _RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW)
    r.check("INTERPOLATION not in _REQUIRES_MULTIVIEW",
            ResolutionStrategy.INTERPOLATION not in _RESOLUTION_STRATEGY_REQUIRES_MULTIVIEW)

    r.check("INTERPOLATION in _REQUIRES_HISTORY",
            ResolutionStrategy.INTERPOLATION in _RESOLUTION_STRATEGY_REQUIRES_HISTORY)
    r.check("PREDICTION in _REQUIRES_HISTORY",
            ResolutionStrategy.PREDICTION in _RESOLUTION_STRATEGY_REQUIRES_HISTORY)
    r.check("KALMAN in _REQUIRES_HISTORY",
            ResolutionStrategy.KALMAN in _RESOLUTION_STRATEGY_REQUIRES_HISTORY)

    r.check("APPEARANCE_MATCHING in _REQUIRES_APPEARANCE",
            ResolutionStrategy.APPEARANCE_MATCHING in _RESOLUTION_STRATEGY_REQUIRES_APPEARANCE)
    r.check("HYBRID in _REQUIRES_APPEARANCE",
            ResolutionStrategy.HYBRID in _RESOLUTION_STRATEGY_REQUIRES_APPEARANCE)


# ==================== 26. dict 캐시 완전성 ====================
def test_dict_caches(r: TestResult) -> None:
    print("\n[26] dict 캐시 완전성")
    from shared.constants.occlusion_constants import (
        OcclusionType, OcclusionSeverity, ResolutionStrategy,
        _OCCLUSION_TYPE_DURATION_MAP,
        _OCCLUSION_TYPE_KOREAN_MAP,
        _OCCLUSION_TYPE_STRATEGY_MAP,
        _OCCLUSION_SEVERITY_KOREAN_MAP,
        _RESOLUTION_STRATEGY_PRIORITY_MAP,
        _RESOLUTION_STRATEGY_KOREAN_MAP,
    )

    # 타입 검증
    r.check("_OCCLUSION_TYPE_DURATION_MAP dict",
            isinstance(_OCCLUSION_TYPE_DURATION_MAP, dict))
    r.check("_OCCLUSION_TYPE_KOREAN_MAP dict",
            isinstance(_OCCLUSION_TYPE_KOREAN_MAP, dict))
    r.check("_OCCLUSION_TYPE_STRATEGY_MAP dict",
            isinstance(_OCCLUSION_TYPE_STRATEGY_MAP, dict))
    r.check("_OCCLUSION_SEVERITY_KOREAN_MAP dict",
            isinstance(_OCCLUSION_SEVERITY_KOREAN_MAP, dict))
    r.check("_RESOLUTION_STRATEGY_PRIORITY_MAP dict",
            isinstance(_RESOLUTION_STRATEGY_PRIORITY_MAP, dict))
    r.check("_RESOLUTION_STRATEGY_KOREAN_MAP dict",
            isinstance(_RESOLUTION_STRATEGY_KOREAN_MAP, dict))

    # 키 개수 = Enum 멤버 수 (완전성)
    r.check("_DURATION_MAP 7개 키",
            len(_OCCLUSION_TYPE_DURATION_MAP) == len(OcclusionType),
            f"실제: {len(_OCCLUSION_TYPE_DURATION_MAP)}")
    r.check("_TYPE_KOREAN_MAP 7개 키",
            len(_OCCLUSION_TYPE_KOREAN_MAP) == len(OcclusionType),
            f"실제: {len(_OCCLUSION_TYPE_KOREAN_MAP)}")
    r.check("_STRATEGY_MAP 7개 키",
            len(_OCCLUSION_TYPE_STRATEGY_MAP) == len(OcclusionType),
            f"실제: {len(_OCCLUSION_TYPE_STRATEGY_MAP)}")
    r.check("_SEVERITY_KOREAN_MAP 5개 키",
            len(_OCCLUSION_SEVERITY_KOREAN_MAP) == len(OcclusionSeverity),
            f"실제: {len(_OCCLUSION_SEVERITY_KOREAN_MAP)}")
    r.check("_PRIORITY_MAP 7개 키",
            len(_RESOLUTION_STRATEGY_PRIORITY_MAP) == len(ResolutionStrategy),
            f"실제: {len(_RESOLUTION_STRATEGY_PRIORITY_MAP)}")
    r.check("_STRATEGY_KOREAN_MAP 7개 키",
            len(_RESOLUTION_STRATEGY_KOREAN_MAP) == len(ResolutionStrategy),
            f"실제: {len(_RESOLUTION_STRATEGY_KOREAN_MAP)}")

    # 모든 Enum 멤버가 키에 존재
    for m in OcclusionType:
        r.check(f"_DURATION_MAP에 {m.name} 존재",
                m in _OCCLUSION_TYPE_DURATION_MAP)
        r.check(f"_TYPE_KOREAN_MAP에 {m.name} 존재",
                m in _OCCLUSION_TYPE_KOREAN_MAP)
        r.check(f"_STRATEGY_MAP에 {m.name} 존재",
                m in _OCCLUSION_TYPE_STRATEGY_MAP)

    for m in OcclusionSeverity:
        r.check(f"_SEVERITY_KOREAN_MAP에 {m.name} 존재",
                m in _OCCLUSION_SEVERITY_KOREAN_MAP)

    for m in ResolutionStrategy:
        r.check(f"_PRIORITY_MAP에 {m.name} 존재",
                m in _RESOLUTION_STRATEGY_PRIORITY_MAP)
        r.check(f"_STRATEGY_KOREAN_MAP에 {m.name} 존재",
                m in _RESOLUTION_STRATEGY_KOREAN_MAP)

    # _STRATEGY_MAP 값이 모두 ResolutionStrategy 타입
    for m in OcclusionType:
        r.check(f"_STRATEGY_MAP[{m.name}] ResolutionStrategy 타입",
                isinstance(_OCCLUSION_TYPE_STRATEGY_MAP[m], ResolutionStrategy))


# ==================== 27. 에지 케이스 ====================
def test_edge_cases(r: TestResult) -> None:
    print("\n[27] 에지 케이스")
    from shared.constants.occlusion_constants import (
        OcclusionType, OcclusionSeverity, ResolutionStrategy,
    )

    # --- Enum identity ---
    r.check("OcclusionType.SELF is OcclusionType.SELF",
            OcclusionType.SELF is OcclusionType.SELF)
    r.check("OcclusionSeverity.NONE is OcclusionSeverity.NONE",
            OcclusionSeverity.NONE is OcclusionSeverity.NONE)
    r.check("ResolutionStrategy.CROSS_VIEW is ResolutionStrategy.CROSS_VIEW",
            ResolutionStrategy.CROSS_VIEW is ResolutionStrategy.CROSS_VIEW)

    # --- Enum hashable ---
    d = {
        OcclusionType.SELF: "self",
        OcclusionSeverity.NONE: "none",
        ResolutionStrategy.CROSS_VIEW: "cv",
    }
    r.check("OcclusionType dict 키 사용",
            d[OcclusionType.SELF] == "self")
    r.check("OcclusionSeverity dict 키 사용",
            d[OcclusionSeverity.NONE] == "none")
    r.check("ResolutionStrategy dict 키 사용",
            d[ResolutionStrategy.CROSS_VIEW] == "cv")

    # --- Enum set ---
    type_set = set(OcclusionType)
    r.check("OcclusionType set 7개", len(type_set) == 7)
    sev_set = set(OcclusionSeverity)
    r.check("OcclusionSeverity set 5개", len(sev_set) == 5)
    strat_set = set(ResolutionStrategy)
    r.check("ResolutionStrategy set 7개", len(strat_set) == 7)

    # --- Enum iteration order ---
    type_names = [m.name for m in OcclusionType]
    expected_type_order = [
        "SELF", "INTER_PLAYER", "COURT_OBJECT", "OUT_OF_VIEW",
        "MOTION_BLUR", "LIGHTING", "UNKNOWN",
    ]
    r.check("OcclusionType 순서 일치",
            type_names == expected_type_order,
            f"실제: {type_names}")

    sev_names = [m.name for m in OcclusionSeverity]
    expected_sev_order = ["NONE", "MINOR", "PARTIAL", "SEVERE", "TOTAL"]
    r.check("OcclusionSeverity 순서 일치",
            sev_names == expected_sev_order,
            f"실제: {sev_names}")

    strat_names = [m.name for m in ResolutionStrategy]
    expected_strat_order = [
        "CROSS_VIEW", "INTERPOLATION", "PREDICTION", "KALMAN",
        "APPEARANCE_MATCHING", "HYBRID", "NONE",
    ]
    r.check("ResolutionStrategy 순서 일치",
            strat_names == expected_strat_order,
            f"실제: {strat_names}")

    # --- len() ---
    r.check("len(OcclusionType) = 7", len(OcclusionType) == 7)
    r.check("len(OcclusionSeverity) = 5", len(OcclusionSeverity) == 5)
    r.check("len(ResolutionStrategy) = 7", len(ResolutionStrategy) == 7)

    # --- _value2member_map_ ---
    r.check("'self' in OcclusionType._value2member_map_",
            "self" in OcclusionType._value2member_map_)
    r.check("ResolutionStrategy('cross_view') 접근",
            ResolutionStrategy("cross_view") == ResolutionStrategy.CROSS_VIEW)

    # --- Cross-Enum 격리 ---
    r.check("OcclusionType.SELF != OcclusionSeverity.NONE",
            OcclusionType.SELF != OcclusionSeverity.NONE)
    r.check("OcclusionType.UNKNOWN != ResolutionStrategy.NONE",
            OcclusionType.UNKNOWN != ResolutionStrategy.NONE)
    r.check("OcclusionSeverity.NONE != ResolutionStrategy.NONE",
            OcclusionSeverity.NONE != ResolutionStrategy.NONE)

    # --- OcclusionSeverity tuple value 불변성 ---
    for member in OcclusionSeverity:
        try:
            member.value[0] = "changed"  # type: ignore
            r.fail(f"{member.name}.value 불변성 (TypeError 미발생)")
        except TypeError:
            r.ok(f"{member.name}.value 불변성 (TypeError 발생)")

    # --- OcclusionSeverity overlap_range 불변성 ---
    for member in OcclusionSeverity:
        try:
            member.overlap_range[0] = 999.0  # type: ignore
            r.fail(f"{member.name}.overlap_range 불변성 (TypeError 미발생)")
        except TypeError:
            r.ok(f"{member.name}.overlap_range 불변성 (TypeError 발생)")

    # --- typical_duration_frames 불변성 ---
    for member in OcclusionType:
        try:
            member.typical_duration_frames[0] = 999  # type: ignore
            r.fail(f"{member.name}.typical_duration 불변성 (TypeError 미발생)")
        except TypeError:
            r.ok(f"{member.name}.typical_duration 불변성 (TypeError 발생)")

    # --- OcclusionSeverity 연속 범위 (빈 구간 없음) ---
    # NONE~TOTAL까지 범위가 0.0~1.0을 연속 커버하는지 검증
    severities = list(OcclusionSeverity)
    # 첫 번째 비-NONE 멤버(MINOR)의 min_overlap은 0.0
    r.check("MINOR.min_overlap = NONE.min_overlap (= 0.0)",
            abs(OcclusionSeverity.MINOR.min_overlap
                - OcclusionSeverity.NONE.min_overlap) < 1e-9)
    # 각 멤버의 max_overlap = 다음 멤버의 min_overlap (연속성)
    for i in range(1, len(severities) - 1):
        curr = severities[i]
        nxt = severities[i + 1]
        r.check(f"{curr.name}.max_overlap = {nxt.name}.min_overlap (연속)",
                abs(curr.max_overlap - nxt.min_overlap) < 1e-9,
                f"{curr.max_overlap} vs {nxt.min_overlap}")
    # 마지막 멤버(TOTAL)의 max_overlap = 1.0
    r.check("TOTAL.max_overlap = 1.0",
            abs(OcclusionSeverity.TOTAL.max_overlap - 1.0) < 1e-9)

    # --- ResolutionStrategy 요구사항 상호 배타성 ---
    # requires_multiview=True인 멤버는 requires_history=False이어야 함 (역도 부분적 성립)
    for m in ResolutionStrategy:
        if m.requires_multiview:
            r.check(f"{m.name}: multiview=True -> history=False",
                    m.requires_history is False)
        if m.requires_appearance:
            r.check(f"{m.name}: appearance=True -> multiview=False",
                    m.requires_multiview is False)

    # --- .update() 패턴 부재 확인 ---
    import inspect
    import shared.constants.occlusion_constants as module
    source = inspect.getsource(module)
    r.check(".update() 패턴 없음", ".update(" not in source)
    r.check("= {} 빈 선언 없음", "= {}" not in source)
    r.check("= frozenset() 빈 선언 없음", "= frozenset()" not in source)


def main():
    r = TestResult()
    test_overlap_constants(r)                        # 1
    test_depth_constants(r)                          # 2
    test_interpolation_prediction_constants(r)       # 3
    test_visibility_constants(r)                     # 4
    test_multiview_constants(r)                      # 5
    test_occlusion_event_constants(r)                # 6
    test_occlusion_type_basics(r)                    # 7
    test_occlusion_type_is_recoverable(r)            # 8
    test_occlusion_type_duration(r)                  # 9
    test_occlusion_type_recommended_strategy(r)      # 10
    test_occlusion_type_korean(r)                    # 11
    test_occlusion_severity_basics(r)                # 12
    test_occlusion_severity_properties(r)            # 13
    test_occlusion_severity_trackable_recovery(r)    # 14
    test_occlusion_severity_from_overlap(r)          # 15
    test_occlusion_severity_korean(r)                # 16
    test_resolution_strategy_basics(r)               # 17
    test_resolution_strategy_requires_multiview(r)   # 18
    test_resolution_strategy_requires_history(r)     # 19
    test_resolution_strategy_requires_appearance(r)  # 20
    test_resolution_strategy_priority(r)             # 21
    test_resolution_strategy_korean(r)               # 22
    test_all_exports(r)                              # 23
    test_version(r)                                  # 24
    test_frozenset_caches(r)                         # 25
    test_dict_caches(r)                              # 26
    test_edge_cases(r)                               # 27
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
