# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_motion_dto_perf.py

동작 감지/분류 DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도 (Enum 참조, UUID 포함)
- 프로퍼티 접근 속도 (duration, is_reliable, is_three_pointer 등)
- high_confidence_actions 필터링 속도
- 대량 배치 처리 (ActionClassification×30, MotionDetectionResult)

성능 기준:
- 모듈 임포트: < 500ms (cold)
- dataclass 생성: < 5μs (단순) / < 10μs (UUID)
- 프로퍼티 접근: < 2μs
- 필터링: < 5μs

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {test_name}: {elapsed_us:.2f}μs ({ratio:.0f}% of {limit_us:.0f}μs limit)")

    def fail(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {elapsed_us:.2f}μs > {limit_us:.0f}μs")
        print(f"  [FAIL] {test_name}: {elapsed_us:.2f}μs (limit: {limit_us:.0f}μs)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (μs/회)"""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.motion_dto"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000
    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. dataclass 생성 속도 ====================
def test_motion_feature_vector_creation(r: PerfResult) -> None:
    """MotionFeatureVector 생성 속도"""
    from shared.dto.motion_dto import MotionFeatureVector

    def create():
        MotionFeatureVector(
            posture_features={"elbow": 90.0, "knee": 120.0},
            velocity_features={"wrist": 5.2},
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("MotionFeatureVector 생성", elapsed, limit)
    else:
        r.fail("MotionFeatureVector 생성", elapsed, limit)


def test_action_classification_creation(r: PerfResult) -> None:
    """ActionClassification 생성 속도 (UUID 포함)"""
    from shared.dto.motion_dto import ActionClassification, ActionType

    def create():
        ActionClassification(
            player_tracking_id=3,
            action_type=ActionType.SHOOTING,
            sub_type="jump_shot",
            confidence=0.92,
            start_frame=100, end_frame=130,
            start_time=3.33, end_time=4.33,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("ActionClassification 생성", elapsed, limit)
    else:
        r.fail("ActionClassification 생성", elapsed, limit)


def test_shooting_motion_creation(r: PerfResult) -> None:
    """ShootingMotion 생성 속도"""
    from shared.dto.motion_dto import ShootingMotion, ContestLevel
    from shared.constants.game_rule_constants import ShotType

    def create():
        ShootingMotion(
            player_tracking_id=7,
            shot_type=ShotType.JUMP_SHOT,
            release_angle=52.0,
            release_height=2.45,
            arc_height=0.8,
            release_speed=7.2,
            shot_quality=85.0,
            contest_level=ContestLevel.CONTESTED,
            distance_meters=6.8,
            start_frame=200, end_frame=220,
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("ShootingMotion 생성", elapsed, limit)
    else:
        r.fail("ShootingMotion 생성", elapsed, limit)


def test_dribbling_motion_creation(r: PerfResult) -> None:
    """DribblingMotion 생성 속도"""
    from shared.dto.motion_dto import DribblingMotion, DribbleType

    def create():
        DribblingMotion(
            player_tracking_id=5,
            dribble_type=DribbleType.CROSSOVER,
            hand_used="left",
            bounce_frequency=3.5,
            control_quality=88.0,
            speed=4.2,
            direction_changes=3,
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("DribblingMotion 생성", elapsed, limit)
    else:
        r.fail("DribblingMotion 생성", elapsed, limit)


def test_passing_motion_creation(r: PerfResult) -> None:
    """PassingMotion 생성 속도"""
    from shared.dto.motion_dto import PassingMotion, PassType

    def create():
        PassingMotion(
            passer_tracking_id=1,
            receiver_tracking_id=5,
            pass_type=PassType.LOB,
            ball_speed=8.5,
            distance_meters=6.0,
            accuracy=92.0,
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("PassingMotion 생성", elapsed, limit)
    else:
        r.fail("PassingMotion 생성", elapsed, limit)


def test_defensive_motion_creation(r: PerfResult) -> None:
    """DefensiveMotion 생성 속도"""
    from shared.dto.motion_dto import DefensiveMotion, DefensiveActionType

    def create():
        DefensiveMotion(
            defender_tracking_id=8,
            offensive_player_tracking_id=3,
            action_type=DefensiveActionType.CLOSE_OUT,
            distance_to_player=1.8,
            pressure_level=75.0,
            body_between_basket=True,
            hands_active=True,
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("DefensiveMotion 생성", elapsed, limit)
    else:
        r.fail("DefensiveMotion 생성", elapsed, limit)


def test_movement_motion_creation(r: PerfResult) -> None:
    """MovementMotion 생성 속도"""
    from shared.dto.motion_dto import MovementMotion, MovementType

    def create():
        MovementMotion(
            player_tracking_id=2,
            movement_type=MovementType.SPRINT,
            speed=8.5,
            direction=45.0,
            distance_covered=12.0,
            acceleration_peak=4.5,
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("MovementMotion 생성", elapsed, limit)
    else:
        r.fail("MovementMotion 생성", elapsed, limit)


def test_flopping_detection_creation(r: PerfResult) -> None:
    """FloppingDetection 생성 속도"""
    from shared.dto.motion_dto import FloppingDetection, DeceptionType

    def create():
        FloppingDetection(
            player_tracking_id=5,
            deception_type=DeceptionType.EXAGGERATED_CONTACT,
            confidence=0.88,
            contact_force_estimate=120.5,
            reaction_magnitude=350.0,
            reaction_proportionality=0.35,
            biomechanical_plausibility=0.25,
            center_of_gravity_shift=0.85,
            start_frame=1500,
            end_frame=1530,
            timestamp=50.0,
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("FloppingDetection 생성", elapsed, limit)
    else:
        r.fail("FloppingDetection 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 속도 ====================
def test_action_classification_properties(r: PerfResult) -> None:
    """ActionClassification 프로퍼티 접근 속도"""
    from shared.dto.motion_dto import ActionClassification, ActionType

    ac = ActionClassification(
        action_type=ActionType.SHOOTING,
        confidence=0.92,
        start_frame=100, end_frame=130,
        start_time=3.33, end_time=4.33,
    )

    def access():
        _ = ac.duration_frames
        _ = ac.duration_seconds
        _ = ac.is_reliable

    elapsed = measure(access, 100000)
    per_call = elapsed / 3
    limit = 2.0
    if per_call < limit:
        r.ok("ActionClassification 프로퍼티", per_call, limit)
    else:
        r.fail("ActionClassification 프로퍼티", per_call, limit)


def test_shooting_motion_is_three(r: PerfResult) -> None:
    """ShootingMotion.is_three_pointer 프로퍼티 속도"""
    from shared.dto.motion_dto import ShootingMotion

    sm = ShootingMotion(distance_meters=7.5)

    def access():
        _ = sm.is_three_pointer

    elapsed = measure(access, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("is_three_pointer", elapsed, limit)
    else:
        r.fail("is_three_pointer", elapsed, limit)


def test_motion_detection_result_properties(r: PerfResult) -> None:
    """MotionDetectionResult 프로퍼티 속도"""
    from shared.dto.motion_dto import MotionDetectionResult, ActionClassification, ActionType

    actions = [
        ActionClassification(action_type=ActionType.SHOOTING, confidence=0.95),
        ActionClassification(action_type=ActionType.DRIBBLING, confidence=0.60),
        ActionClassification(action_type=ActionType.PASSING, confidence=0.85),
        ActionClassification(action_type=ActionType.MOVEMENT, confidence=0.40),
        ActionClassification(action_type=ActionType.DEFENSE_STANCE, confidence=0.78),
    ]
    mdr = MotionDetectionResult(actions=actions)

    def access():
        _ = mdr.total_actions
        _ = mdr.high_confidence_actions

    elapsed = measure(access, 100000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("MotionDetectionResult 프로퍼티", per_call, limit)
    else:
        r.fail("MotionDetectionResult 프로퍼티", per_call, limit)


# ==================== 4. 대량 처리 ====================
def test_batch_action_classifications(r: PerfResult) -> None:
    """ActionClassification 30개 배치 생성"""
    from shared.dto.motion_dto import ActionClassification, ActionType

    types = list(ActionType)

    def batch():
        for i in range(30):
            ActionClassification(
                player_tracking_id=i % 10,
                action_type=types[i % len(types)],
                confidence=0.5 + (i % 5) * 0.1,
                start_frame=i * 30,
                end_frame=(i + 1) * 30,
            )

    elapsed = measure(batch, 5000)
    limit = 300.0
    if elapsed < limit:
        r.ok("ActionClassification×30", elapsed, limit)
    else:
        r.fail("ActionClassification×30", elapsed, limit)


def test_full_motion_detection_result(r: PerfResult) -> None:
    """풀 MotionDetectionResult 스냅샷 생성"""
    from shared.dto.motion_dto import (
        MotionDetectionResult, ActionClassification, ActionType,
        ShootingMotion, DribblingMotion, PassingMotion,
        DefensiveMotion, MovementMotion,
    )

    def create():
        actions = [
            ActionClassification(action_type=ActionType.SHOOTING, confidence=0.95),
            ActionClassification(action_type=ActionType.DRIBBLING, confidence=0.80),
            ActionClassification(action_type=ActionType.PASSING, confidence=0.75),
        ]
        MotionDetectionResult(
            frame_index=1000,
            timestamp=33.33,
            actions=actions,
            shooting_motions=[ShootingMotion(distance_meters=7.0)],
            dribbling_motions=[DribblingMotion(), DribblingMotion()],
            passing_motions=[PassingMotion()],
            defensive_motions=[DefensiveMotion()],
            movement_motions=[MovementMotion(), MovementMotion(), MovementMotion()],
            processing_time_ms=5.2,
        )

    elapsed = measure(create, 10000)
    limit = 100.0
    if elapsed < limit:
        r.ok("풀 MotionDetectionResult", elapsed, limit)
    else:
        r.fail("풀 MotionDetectionResult", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("motion_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_motion_feature_vector_creation(r)
    test_action_classification_creation(r)
    test_shooting_motion_creation(r)
    test_dribbling_motion_creation(r)
    test_passing_motion_creation(r)
    test_defensive_motion_creation(r)
    test_movement_motion_creation(r)
    test_flopping_detection_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_action_classification_properties(r)
    test_shooting_motion_is_three(r)
    test_motion_detection_result_properties(r)

    print("\n--- 대량 처리 ---")
    test_batch_action_classifications(r)
    test_full_motion_detection_result(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
