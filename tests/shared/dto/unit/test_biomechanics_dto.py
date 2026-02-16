# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_biomechanics_dto.py

생체역학 분석 DTO 단위 테스트
- __all__ Export 동기화
- typing 모더나이즈 (Dict/List/Tuple 미사용)
- 하드코딩 제거 확인 (상수 참조)
- MotionPhase Enum 적용
- 데이터클래스 생성/프로퍼티/__post_init__
- 물리량 계산 정확도

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import inspect
import math
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ==================== 1. 모듈 임포트 및 Export ====================
def test_module_import(r: TestResult) -> None:
    """모듈 임포트 성공 확인"""
    try:
        from shared.dto.biomechanics_dto import (
            JointKinematics, BodySegmentData, BalanceMetrics,
            EnergyMetrics, ForceEstimate, MotionPatternData,
            AnthropometryData, BiomechanicalFrame, BiomechanicalResult,
        )
        r.ok("9개 클래스 임포트 성공")
    except Exception as e:
        r.fail("모듈 임포트", str(e))


def test_all_exports(r: TestResult) -> None:
    """__all__ export 완전성"""
    from shared.dto import biomechanics_dto
    expected = {
        "JointKinematics", "BodySegmentData", "BalanceMetrics",
        "EnergyMetrics", "ForceEstimate", "MotionPatternData",
        "AnthropometryData", "BiomechanicalFrame", "BiomechanicalResult",
    }
    actual = set(biomechanics_dto.__all__)
    if actual == expected:
        r.ok(f"__all__ = {len(expected)}개 일치")
    else:
        r.fail("__all__ 불일치", f"diff={actual.symmetric_difference(expected)}")


# ==================== 2. typing 모더나이즈 ====================
def test_no_old_typing(r: TestResult) -> None:
    """Dict, List, Tuple 미사용 확인"""
    from shared.dto import biomechanics_dto
    source = inspect.getsource(biomechanics_dto)
    old_types = ["Dict[", "List[", "Tuple["]
    found = [t for t in old_types if t in source]
    if not found:
        r.ok("typing 모더나이즈 완료")
    else:
        r.fail("typing 구형 타입 잔존", str(found))


# ==================== 3. 하드코딩 제거 ====================
def test_no_hardcoded_fast_motion(r: TestResult) -> None:
    """is_fast_motion 내 200.0 하드코딩 제거"""
    from shared.dto.biomechanics_dto import JointKinematics
    src = inspect.getsource(JointKinematics.is_fast_motion.fget)
    if "200.0" in src or "200" in src.split("JOINT_FAST_MOTION")[0]:
        r.fail("is_fast_motion 하드코딩", "200.0 발견")
    else:
        r.ok("is_fast_motion = JOINT_FAST_MOTION_SPEED_CM_S 참조")


def test_no_hardcoded_stability(r: TestResult) -> None:
    """BalanceMetrics.__post_init__ 내 50.0 하드코딩 제거"""
    from shared.dto.biomechanics_dto import BalanceMetrics
    src = inspect.getsource(BalanceMetrics.__post_init__)
    if "50.0" in src:
        r.fail("stability 하드코딩", "50.0 발견")
    else:
        r.ok("stability = STABILITY_INDEX_MIN_STABLE 참조")


def test_no_hardcoded_energy(r: TestResult) -> None:
    """is_high_energy_frame 내 50.0 하드코딩 제거"""
    from shared.dto.biomechanics_dto import BiomechanicalFrame
    src = inspect.getsource(BiomechanicalFrame.is_high_energy_frame.fget)
    if "50.0" in src or "50" in src.split("HIGH_ENERGY")[0]:
        r.fail("high_energy 하드코딩", "50.0 발견")
    else:
        r.ok("high_energy = HIGH_ENERGY_KINETIC_THRESHOLD_J 참조")


def test_constants_values(r: TestResult) -> None:
    """상수값 일치 확인"""
    from shared.constants.biomechanics_constants import (
        JOINT_FAST_MOTION_SPEED_CM_S,
        STABILITY_INDEX_MIN_STABLE,
        HIGH_ENERGY_KINETIC_THRESHOLD_J,
    )
    ok = True
    if abs(JOINT_FAST_MOTION_SPEED_CM_S - 200.0) > 1e-6:
        r.fail("JOINT_FAST_MOTION_SPEED_CM_S", f"{JOINT_FAST_MOTION_SPEED_CM_S} != 200.0")
        ok = False
    if abs(STABILITY_INDEX_MIN_STABLE - 50.0) > 1e-6:
        r.fail("STABILITY_INDEX_MIN_STABLE", f"{STABILITY_INDEX_MIN_STABLE} != 50.0")
        ok = False
    if abs(HIGH_ENERGY_KINETIC_THRESHOLD_J - 50.0) > 1e-6:
        r.fail("HIGH_ENERGY_KINETIC_THRESHOLD_J", f"{HIGH_ENERGY_KINETIC_THRESHOLD_J} != 50.0")
        ok = False
    if ok:
        r.ok("3개 상수값 전부 일치")


# ==================== 4. MotionPhase Enum 적용 ====================
def test_motion_pattern_phase_enum(r: TestResult) -> None:
    """MotionPatternData.phase가 MotionPhase Enum 타입"""
    from shared.dto.biomechanics_dto import MotionPatternData
    from shared.constants.biomechanics_constants import MotionPhase
    mp = MotionPatternData(
        pattern_type="shooting_preparation",
        phase=MotionPhase.PREPARATION,
        confidence=0.95,
    )
    if mp.phase == MotionPhase.PREPARATION and mp.phase.value == "preparation":
        r.ok("MotionPatternData.phase = MotionPhase.PREPARATION")
    else:
        r.fail("MotionPhase 적용", f"phase={mp.phase}")


def test_motion_pattern_phase_none_default(r: TestResult) -> None:
    """MotionPatternData.phase 기본값 None"""
    from shared.dto.biomechanics_dto import MotionPatternData
    mp = MotionPatternData()
    if mp.phase is None:
        r.ok("MotionPatternData.phase 기본값 = None")
    else:
        r.fail("phase 기본값", f"expected=None, actual={mp.phase}")


def test_motion_phase_all_values(r: TestResult) -> None:
    """MotionPhase 4단계 모두 적용 가능"""
    from shared.dto.biomechanics_dto import MotionPatternData
    from shared.constants.biomechanics_constants import MotionPhase
    for phase in MotionPhase:
        mp = MotionPatternData(phase=phase)
        if mp.phase != phase:
            r.fail(f"MotionPhase.{phase.name}", "할당 실패")
            return
    r.ok(f"MotionPhase {len(list(MotionPhase))}단계 전부 적용 가능")


# ==================== 5. JointKinematics ====================
def test_joint_kinematics_is_fast_motion(r: TestResult) -> None:
    """is_fast_motion 로직"""
    from shared.dto.biomechanics_dto import JointKinematics
    from shared.constants.pose_constants import JointType
    fast = JointKinematics(joint_type=JointType.RIGHT_WRIST, speed=250.0)
    slow = JointKinematics(joint_type=JointType.RIGHT_WRIST, speed=100.0)
    if fast.is_fast_motion and not slow.is_fast_motion:
        r.ok("is_fast_motion: 250=True, 100=False")
    else:
        r.fail("is_fast_motion", f"fast={fast.is_fast_motion}, slow={slow.is_fast_motion}")


def test_joint_kinematics_acceleration_magnitude(r: TestResult) -> None:
    """가속도 크기 3-4-5 삼각형"""
    from shared.dto.biomechanics_dto import JointKinematics
    from shared.constants.pose_constants import JointType
    jk = JointKinematics(joint_type=JointType.RIGHT_ELBOW, acceleration=(3.0, 4.0, 0.0))
    if abs(jk.acceleration_magnitude - 5.0) < 1e-6:
        r.ok("acceleration_magnitude = 5.0 (3-4-5)")
    else:
        r.fail("acceleration_magnitude", f"expected=5.0, actual={jk.acceleration_magnitude}")


# ==================== 6. BalanceMetrics ====================
def test_balance_metrics_stability(r: TestResult) -> None:
    """BalanceMetrics.is_stable __post_init__ 로직"""
    from shared.dto.biomechanics_dto import BalanceMetrics
    stable = BalanceMetrics(stability_index=60.0)
    unstable = BalanceMetrics(stability_index=30.0)
    if stable.is_stable and not unstable.is_stable:
        r.ok("is_stable: 60=True, 30=False")
    else:
        r.fail("is_stable", f"60={stable.is_stable}, 30={unstable.is_stable}")


def test_balance_metrics_weight_normalization(r: TestResult) -> None:
    """체중 분배 비율 자동 정규화"""
    from shared.dto.biomechanics_dto import BalanceMetrics
    bm = BalanceMetrics(weight_distribution=(3.0, 7.0))
    left, right = bm.weight_distribution
    if abs(left - 0.3) < 0.01 and abs(right - 0.7) < 0.01:
        r.ok(f"정규화: (3,7) → ({left:.2f},{right:.2f})")
    else:
        r.fail("정규화", f"({left},{right})")


def test_balance_metrics_already_normalized(r: TestResult) -> None:
    """이미 정규화된 값은 변경 없음"""
    from shared.dto.biomechanics_dto import BalanceMetrics
    bm = BalanceMetrics(weight_distribution=(0.6, 0.4))
    left, right = bm.weight_distribution
    if abs(left - 0.6) < 0.01 and abs(right - 0.4) < 0.01:
        r.ok("이미 정규화 → 변경 없음")
    else:
        r.fail("이미 정규화 불일치", f"({left},{right})")


# ==================== 7. EnergyMetrics ====================
def test_energy_total_auto_calc(r: TestResult) -> None:
    """total_energy 자동 계산"""
    from shared.dto.biomechanics_dto import EnergyMetrics
    em = EnergyMetrics(kinetic_energy=100.0, potential_energy=50.0)
    if em.total_energy == 150.0:
        r.ok("total_energy = kinetic + potential = 150.0")
    else:
        r.fail("total_energy", f"expected=150, actual={em.total_energy}")


def test_energy_kinetic_ratio(r: TestResult) -> None:
    """kinetic_ratio 계산"""
    from shared.dto.biomechanics_dto import EnergyMetrics
    em = EnergyMetrics(kinetic_energy=60.0, potential_energy=40.0)
    if abs(em.kinetic_ratio - 0.6) < 1e-6:
        r.ok("kinetic_ratio = 0.6")
    else:
        r.fail("kinetic_ratio", f"expected=0.6, actual={em.kinetic_ratio}")


def test_energy_kinetic_ratio_zero(r: TestResult) -> None:
    """total_energy=0일 때 kinetic_ratio=0"""
    from shared.dto.biomechanics_dto import EnergyMetrics
    em = EnergyMetrics()
    if em.kinetic_ratio == 0.0:
        r.ok("kinetic_ratio = 0.0 (total=0)")
    else:
        r.fail("kinetic_ratio zero", f"actual={em.kinetic_ratio}")


# ==================== 8. ForceEstimate ====================
def test_force_magnitude_auto_calc(r: TestResult) -> None:
    """magnitude 자동 계산"""
    from shared.dto.biomechanics_dto import ForceEstimate
    from shared.constants.pose_constants import JointType
    fe = ForceEstimate(joint_type=JointType.RIGHT_ANKLE, force_vector=(30.0, 40.0, 0.0))
    if abs(fe.magnitude - 50.0) < 1e-6:
        r.ok("magnitude = 50.0 (30-40-0)")
    else:
        r.fail("magnitude", f"expected=50, actual={fe.magnitude}")


def test_force_magnitude_preset(r: TestResult) -> None:
    """magnitude 사전 설정 시 유지"""
    from shared.dto.biomechanics_dto import ForceEstimate
    from shared.constants.pose_constants import JointType
    fe = ForceEstimate(joint_type=JointType.RIGHT_ANKLE, force_vector=(3.0, 4.0, 0.0), magnitude=99.0)
    if fe.magnitude == 99.0:
        r.ok("magnitude 사전 설정 = 99.0 유지")
    else:
        r.fail("magnitude preset", f"expected=99, actual={fe.magnitude}")


# ==================== 9. AnthropometryData ====================
def test_bmi_calculation(r: TestResult) -> None:
    """BMI 계산 정확성"""
    from shared.dto.biomechanics_dto import AnthropometryData
    anthro = AnthropometryData(height_cm=185.0, weight_kg=80.0)
    expected_bmi = 80.0 / (1.85 ** 2)
    if abs(anthro.bmi - expected_bmi) < 0.01:
        r.ok(f"BMI = {anthro.bmi:.2f}")
    else:
        r.fail("BMI", f"expected={expected_bmi:.2f}, actual={anthro.bmi:.2f}")


def test_bmi_zero_height(r: TestResult) -> None:
    """height=0일 때 BMI=0"""
    from shared.dto.biomechanics_dto import AnthropometryData
    anthro = AnthropometryData(height_cm=0.0, weight_kg=80.0)
    if anthro.bmi == 0.0:
        r.ok("BMI = 0.0 (height=0)")
    else:
        r.fail("BMI zero", f"actual={anthro.bmi}")


def test_ape_index(r: TestResult) -> None:
    """에이프 인덱스 계산"""
    from shared.dto.biomechanics_dto import AnthropometryData
    anthro = AnthropometryData(height_cm=185.0, arm_span_cm=192.0)
    if abs(anthro.ape_index - 7.0) < 1e-6:
        r.ok("ape_index = 7.0cm (192-185)")
    else:
        r.fail("ape_index", f"expected=7.0, actual={anthro.ape_index}")


# ==================== 10. BiomechanicalFrame ====================
def test_frame_max_joint_speed(r: TestResult) -> None:
    """max_joint_speed 계산"""
    from shared.dto.biomechanics_dto import BiomechanicalFrame, JointKinematics
    from shared.constants.pose_constants import JointType
    frame = BiomechanicalFrame(
        joint_kinematics={
            JointType.RIGHT_WRIST: JointKinematics(joint_type=JointType.RIGHT_WRIST, speed=300.0),
            JointType.RIGHT_ELBOW: JointKinematics(joint_type=JointType.RIGHT_ELBOW, speed=150.0),
        }
    )
    if frame.max_joint_speed == 300.0:
        r.ok("max_joint_speed = 300.0")
    else:
        r.fail("max_joint_speed", f"actual={frame.max_joint_speed}")


def test_frame_max_joint_speed_empty(r: TestResult) -> None:
    """빈 frame의 max_joint_speed=0"""
    from shared.dto.biomechanics_dto import BiomechanicalFrame
    frame = BiomechanicalFrame()
    if frame.max_joint_speed == 0.0:
        r.ok("max_joint_speed = 0.0 (empty)")
    else:
        r.fail("max_joint_speed empty", f"actual={frame.max_joint_speed}")


def test_frame_is_high_energy(r: TestResult) -> None:
    """is_high_energy_frame 로직"""
    from shared.dto.biomechanics_dto import BiomechanicalFrame, EnergyMetrics
    high = BiomechanicalFrame(energy=EnergyMetrics(kinetic_energy=80.0))
    low = BiomechanicalFrame(energy=EnergyMetrics(kinetic_energy=20.0))
    none_ = BiomechanicalFrame()
    if high.is_high_energy_frame and not low.is_high_energy_frame and not none_.is_high_energy_frame:
        r.ok("is_high_energy_frame: 80=True, 20=False, None=False")
    else:
        r.fail("is_high_energy", f"80={high.is_high_energy_frame}, 20={low.is_high_energy_frame}")


# ==================== 11. BiomechanicalResult ====================
def test_result_frame_count(r: TestResult) -> None:
    """frame_count 프로퍼티"""
    from shared.dto.biomechanics_dto import BiomechanicalResult, BiomechanicalFrame
    result = BiomechanicalResult(frames=[BiomechanicalFrame(timestamp=i * 0.033) for i in range(30)])
    if result.frame_count == 30:
        r.ok("frame_count = 30")
    else:
        r.fail("frame_count", f"actual={result.frame_count}")


def test_result_duration(r: TestResult) -> None:
    """duration_seconds 계산"""
    from shared.dto.biomechanics_dto import BiomechanicalResult, BiomechanicalFrame
    frames = [BiomechanicalFrame(timestamp=i * 0.1) for i in range(10)]
    result = BiomechanicalResult(frames=frames)
    expected = 0.9  # 0.0 ~ 0.9
    if abs(result.duration_seconds - expected) < 1e-6:
        r.ok(f"duration_seconds = {expected}")
    else:
        r.fail("duration_seconds", f"expected={expected}, actual={result.duration_seconds}")


def test_result_average_stability(r: TestResult) -> None:
    """average_stability 계산"""
    from shared.dto.biomechanics_dto import BiomechanicalResult, BiomechanicalFrame, BalanceMetrics
    frames = [
        BiomechanicalFrame(balance=BalanceMetrics(stability_index=60.0)),
        BiomechanicalFrame(balance=BalanceMetrics(stability_index=80.0)),
        BiomechanicalFrame(),  # balance=None → 제외
    ]
    result = BiomechanicalResult(frames=frames)
    expected = (60.0 + 80.0) / 2
    if abs(result.average_stability - expected) < 1e-6:
        r.ok(f"average_stability = {expected} (None 제외)")
    else:
        r.fail("average_stability", f"expected={expected}, actual={result.average_stability}")


def test_result_peak_speed(r: TestResult) -> None:
    """peak_speed 계산"""
    from shared.dto.biomechanics_dto import (
        BiomechanicalResult, BiomechanicalFrame, JointKinematics,
    )
    from shared.constants.pose_constants import JointType
    frames = [
        BiomechanicalFrame(joint_kinematics={
            JointType.RIGHT_WRIST: JointKinematics(joint_type=JointType.RIGHT_WRIST, speed=s)
        })
        for s in [100.0, 300.0, 200.0]
    ]
    result = BiomechanicalResult(frames=frames)
    if result.peak_speed == 300.0:
        r.ok("peak_speed = 300.0")
    else:
        r.fail("peak_speed", f"actual={result.peak_speed}")


def test_result_uuid_uniqueness(r: TestResult) -> None:
    """result_id UUID 고유성"""
    from shared.dto.biomechanics_dto import BiomechanicalResult
    ids = {BiomechanicalResult().result_id for _ in range(100)}
    if len(ids) == 100:
        r.ok("UUID 100개 전부 고유")
    else:
        r.fail("UUID", f"100개 중 {len(ids)}개 고유")


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("biomechanics_dto.py v1.1.0 단위 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 및 Export ---")
    test_module_import(r)
    test_all_exports(r)

    print("\n--- typing 모더나이즈 ---")
    test_no_old_typing(r)

    print("\n--- 하드코딩 제거 ---")
    test_no_hardcoded_fast_motion(r)
    test_no_hardcoded_stability(r)
    test_no_hardcoded_energy(r)
    test_constants_values(r)

    print("\n--- MotionPhase Enum ---")
    test_motion_pattern_phase_enum(r)
    test_motion_pattern_phase_none_default(r)
    test_motion_phase_all_values(r)

    print("\n--- JointKinematics ---")
    test_joint_kinematics_is_fast_motion(r)
    test_joint_kinematics_acceleration_magnitude(r)

    print("\n--- BalanceMetrics ---")
    test_balance_metrics_stability(r)
    test_balance_metrics_weight_normalization(r)
    test_balance_metrics_already_normalized(r)

    print("\n--- EnergyMetrics ---")
    test_energy_total_auto_calc(r)
    test_energy_kinetic_ratio(r)
    test_energy_kinetic_ratio_zero(r)

    print("\n--- ForceEstimate ---")
    test_force_magnitude_auto_calc(r)
    test_force_magnitude_preset(r)

    print("\n--- AnthropometryData ---")
    test_bmi_calculation(r)
    test_bmi_zero_height(r)
    test_ape_index(r)

    print("\n--- BiomechanicalFrame ---")
    test_frame_max_joint_speed(r)
    test_frame_max_joint_speed_empty(r)
    test_frame_is_high_energy(r)

    print("\n--- BiomechanicalResult ---")
    test_result_frame_count(r)
    test_result_duration(r)
    test_result_average_stability(r)
    test_result_peak_speed(r)
    test_result_uuid_uniqueness(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
