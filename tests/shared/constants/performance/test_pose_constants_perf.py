# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_pose_constants_perf.py

포즈 추정 관련 상수 모듈(pose_constants.py v2.1.0) 성능 테스트
- 모듈 임포트 시간
- PoseQuality 프로퍼티 접근 (quality_name, min/max_completeness, is_usable, is_reliable, to_korean)
- PoseQuality.from_completeness() 변환 (경계값, 일반값)
- PoseQuality.get_name() 다국어 조회 (KO, EN, JA, ZH, ES)
- SkeletonType 프로퍼티 접근 (num_keypoints, has_hand_keypoints, has_face_keypoints, to_korean)
- SkeletonType.get_name() 다국어 조회
- JointType 프로퍼티 접근 (is_left, is_right, symmetric_joint, to_korean)
- JointType.get_name() 다국어 조회
- 키포인트 그룹 frozenset 멤버십 테스트 (in 연산)
- COCO 스켈레톤 연결 순회
- 상수 접근 (각도, 신뢰도, 모델 파라미터)
- Enum 이터레이션 (각 Enum별)
- 복합 시나리오 (포즈 분석 파이프라인 시뮬레이션)
- 대량 처리량
- 메모리 사용량

성능 기준:
- 모듈 임포트: < 500ms (1회)
- 프로퍼티 접근: < 1us (inline dict/frozenset 조회)
- get_name() i18n: < 1us
- from_completeness() classmethod: < 2us
- frozenset 멤버십: < 0.5us
- 스켈레톤 연결 순회: < 5us (16개 튜플)
- Enum 순회: < 5us (4~17개 멤버)
- 복합 시나리오: < 50us
- 대량 처리: < 500ms

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


# ==================== 테스트 결과 클래스 ====================
class PerfResult:
    """성능 테스트 결과 수집 및 보고"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name, elapsed_us, limit_us):
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.3f}us ({ratio:.1f}% of {limit_us:.0f}us)")

    def fail(self, name, elapsed_us, limit_us):
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.3f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.3f}us (limit: {limit_us:.0f}us)")

    def info(self, msg):
        print(f"  [INFO] {msg}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")
        return self.failed == 0


def measure(func, iterations=10000):
    """함수 실행 시간 측정 (마이크로초/회, GC 비활성화)"""
    gc.disable()
    try:
        # 워밍업
        for _ in range(min(iterations, 1000)):
            func()

        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns -> us per iteration
    finally:
        gc.enable()


def _check(r, name, elapsed, limit):
    """결과 판정 헬퍼"""
    if elapsed <= limit:
        r.ok(name, elapsed, limit)
    else:
        r.fail(name, elapsed, limit)


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 측정 (< 500ms)"""
    import importlib

    mod_name = "shared.constants.pose_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000  # 500ms = 500,000us

    r.info(f"임포트 시간: {elapsed_us / 1000:.2f}ms")
    _check(r, "모듈 임포트 (cold)", elapsed_us, limit_us)


# ==================== 2. PoseQuality 프로퍼티 접근 ====================
def test_pose_quality_property_access(r: PerfResult) -> None:
    """PoseQuality.quality_name, min/max_completeness, is_usable, is_reliable, to_korean 접근 (< 1us)"""
    from shared.constants.pose_constants import PoseQuality

    limit = 1.0

    # quality_name 프로퍼티
    elapsed_qn_high = measure(lambda: PoseQuality.HIGH.quality_name, iterations=100_000)
    _check(r, "PoseQuality.HIGH.quality_name", elapsed_qn_high, limit)

    elapsed_qn_inv = measure(lambda: PoseQuality.INVALID.quality_name, iterations=100_000)
    _check(r, "PoseQuality.INVALID.quality_name", elapsed_qn_inv, limit)

    # min_completeness / max_completeness 프로퍼티
    elapsed_min = measure(lambda: PoseQuality.HIGH.min_completeness, iterations=100_000)
    _check(r, "PoseQuality.HIGH.min_completeness", elapsed_min, limit)

    elapsed_max = measure(lambda: PoseQuality.LOW.max_completeness, iterations=100_000)
    _check(r, "PoseQuality.LOW.max_completeness", elapsed_max, limit)

    # is_usable 프로퍼티 (Enum 비교)
    elapsed_usable_high = measure(lambda: PoseQuality.HIGH.is_usable, iterations=100_000)
    _check(r, "PoseQuality.HIGH.is_usable", elapsed_usable_high, limit)

    elapsed_usable_inv = measure(lambda: PoseQuality.INVALID.is_usable, iterations=100_000)
    _check(r, "PoseQuality.INVALID.is_usable", elapsed_usable_inv, limit)

    # is_reliable 프로퍼티 (frozenset 멤버십)
    elapsed_rel_high = measure(lambda: PoseQuality.HIGH.is_reliable, iterations=100_000)
    _check(r, "PoseQuality.HIGH.is_reliable", elapsed_rel_high, limit)

    elapsed_rel_low = measure(lambda: PoseQuality.LOW.is_reliable, iterations=100_000)
    _check(r, "PoseQuality.LOW.is_reliable", elapsed_rel_low, limit)

    # to_korean 프로퍼티 (캐시 dict 조회)
    elapsed_ko_med = measure(lambda: PoseQuality.MEDIUM.to_korean, iterations=100_000)
    _check(r, "PoseQuality.MEDIUM.to_korean", elapsed_ko_med, limit)


# ==================== 3. PoseQuality.from_completeness() 변환 ====================
def test_pose_quality_from_completeness(r: PerfResult) -> None:
    """PoseQuality.from_completeness() 경계값 및 일반값 변환 (< 2us)"""
    from shared.constants.pose_constants import PoseQuality

    limit = 2.0

    # 경계값: INVALID -> LOW (0.4)
    elapsed_04 = measure(lambda: PoseQuality.from_completeness(0.4), iterations=100_000)
    _check(r, "from_completeness(0.4) 경계 LOW", elapsed_04, limit)

    # 경계값: LOW -> MEDIUM (0.6)
    elapsed_06 = measure(lambda: PoseQuality.from_completeness(0.6), iterations=100_000)
    _check(r, "from_completeness(0.6) 경계 MEDIUM", elapsed_06, limit)

    # 경계값: MEDIUM -> HIGH (0.8)
    elapsed_08 = measure(lambda: PoseQuality.from_completeness(0.8), iterations=100_000)
    _check(r, "from_completeness(0.8) 경계 HIGH", elapsed_08, limit)

    # 일반값: 최저 (0.0) -> INVALID
    elapsed_00 = measure(lambda: PoseQuality.from_completeness(0.0), iterations=100_000)
    _check(r, "from_completeness(0.0) INVALID", elapsed_00, limit)

    # 일반값: 최고 (1.0) -> HIGH
    elapsed_10 = measure(lambda: PoseQuality.from_completeness(1.0), iterations=100_000)
    _check(r, "from_completeness(1.0) HIGH", elapsed_10, limit)

    # 일반값: 중간 (0.5) -> LOW
    elapsed_05 = measure(lambda: PoseQuality.from_completeness(0.5), iterations=100_000)
    _check(r, "from_completeness(0.5) LOW 일반값", elapsed_05, limit)


# ==================== 4. PoseQuality.get_name() 다국어 조회 ====================
def test_pose_quality_get_name_i18n(r: PerfResult) -> None:
    """PoseQuality.get_name() 5개 언어별 조회 (< 1us each)"""
    from shared.constants.pose_constants import PoseQuality
    from shared.constants.localization import SupportedLanguage

    limit = 1.0

    # 한국어 (기본값)
    elapsed_ko = measure(
        lambda: PoseQuality.HIGH.get_name(SupportedLanguage.KO), iterations=100_000
    )
    _check(r, "PoseQuality.get_name(KO)", elapsed_ko, limit)

    # 영어
    elapsed_en = measure(
        lambda: PoseQuality.MEDIUM.get_name(SupportedLanguage.EN), iterations=100_000
    )
    _check(r, "PoseQuality.get_name(EN)", elapsed_en, limit)

    # 일본어
    elapsed_ja = measure(
        lambda: PoseQuality.LOW.get_name(SupportedLanguage.JA), iterations=100_000
    )
    _check(r, "PoseQuality.get_name(JA)", elapsed_ja, limit)

    # 중국어
    elapsed_zh = measure(
        lambda: PoseQuality.INVALID.get_name(SupportedLanguage.ZH), iterations=100_000
    )
    _check(r, "PoseQuality.get_name(ZH)", elapsed_zh, limit)

    # 스페인어
    elapsed_es = measure(
        lambda: PoseQuality.HIGH.get_name(SupportedLanguage.ES), iterations=100_000
    )
    _check(r, "PoseQuality.get_name(ES)", elapsed_es, limit)


# ==================== 5. SkeletonType 프로퍼티 접근 ====================
def test_skeleton_type_property_access(r: PerfResult) -> None:
    """SkeletonType.num_keypoints, has_hand_keypoints, has_face_keypoints, to_korean 접근 (< 1us)"""
    from shared.constants.pose_constants import SkeletonType

    limit = 1.0

    # num_keypoints 프로퍼티 (dict 조회)
    elapsed_mp_kp = measure(lambda: SkeletonType.MEDIAPIPE.num_keypoints, iterations=100_000)
    _check(r, "SkeletonType.MEDIAPIPE.num_keypoints", elapsed_mp_kp, limit)

    elapsed_coco_kp = measure(lambda: SkeletonType.COCO.num_keypoints, iterations=100_000)
    _check(r, "SkeletonType.COCO.num_keypoints", elapsed_coco_kp, limit)

    elapsed_op25_kp = measure(lambda: SkeletonType.OPENPOSE_25.num_keypoints, iterations=100_000)
    _check(r, "SkeletonType.OPENPOSE_25.num_keypoints", elapsed_op25_kp, limit)

    # has_hand_keypoints 프로퍼티 (frozenset 멤버십)
    elapsed_mp_hand = measure(lambda: SkeletonType.MEDIAPIPE.has_hand_keypoints, iterations=100_000)
    _check(r, "SkeletonType.MEDIAPIPE.has_hand_keypoints", elapsed_mp_hand, limit)

    elapsed_coco_hand = measure(lambda: SkeletonType.COCO.has_hand_keypoints, iterations=100_000)
    _check(r, "SkeletonType.COCO.has_hand_keypoints", elapsed_coco_hand, limit)

    # has_face_keypoints 프로퍼티 (frozenset 멤버십)
    elapsed_mp_face = measure(lambda: SkeletonType.MEDIAPIPE.has_face_keypoints, iterations=100_000)
    _check(r, "SkeletonType.MEDIAPIPE.has_face_keypoints", elapsed_mp_face, limit)

    elapsed_coco_face = measure(lambda: SkeletonType.COCO.has_face_keypoints, iterations=100_000)
    _check(r, "SkeletonType.COCO.has_face_keypoints", elapsed_coco_face, limit)

    # to_korean 프로퍼티 (캐시 dict 조회)
    elapsed_custom_ko = measure(lambda: SkeletonType.CUSTOM.to_korean, iterations=100_000)
    _check(r, "SkeletonType.CUSTOM.to_korean", elapsed_custom_ko, limit)


# ==================== 6. SkeletonType.get_name() 다국어 조회 ====================
def test_skeleton_type_get_name_i18n(r: PerfResult) -> None:
    """SkeletonType.get_name() 5개 언어별 조회 (< 1us each)"""
    from shared.constants.pose_constants import SkeletonType
    from shared.constants.localization import SupportedLanguage

    limit = 1.0

    elapsed_ko = measure(
        lambda: SkeletonType.MEDIAPIPE.get_name(SupportedLanguage.KO), iterations=100_000
    )
    _check(r, "SkeletonType.get_name(KO)", elapsed_ko, limit)

    elapsed_en = measure(
        lambda: SkeletonType.COCO.get_name(SupportedLanguage.EN), iterations=100_000
    )
    _check(r, "SkeletonType.get_name(EN)", elapsed_en, limit)

    elapsed_ja = measure(
        lambda: SkeletonType.OPENPOSE_25.get_name(SupportedLanguage.JA), iterations=100_000
    )
    _check(r, "SkeletonType.get_name(JA)", elapsed_ja, limit)

    elapsed_zh = measure(
        lambda: SkeletonType.HALPE.get_name(SupportedLanguage.ZH), iterations=100_000
    )
    _check(r, "SkeletonType.get_name(ZH)", elapsed_zh, limit)

    elapsed_es = measure(
        lambda: SkeletonType.CUSTOM.get_name(SupportedLanguage.ES), iterations=100_000
    )
    _check(r, "SkeletonType.get_name(ES)", elapsed_es, limit)


# ==================== 7. JointType 프로퍼티 접근 ====================
def test_joint_type_property_access(r: PerfResult) -> None:
    """JointType.is_left, is_right, symmetric_joint, to_korean 접근 (< 1us)"""
    from shared.constants.pose_constants import JointType

    limit = 1.0

    # is_left 프로퍼티 (frozenset 멤버십)
    elapsed_lshoulder_left = measure(lambda: JointType.LEFT_SHOULDER.is_left, iterations=100_000)
    _check(r, "JointType.LEFT_SHOULDER.is_left", elapsed_lshoulder_left, limit)

    elapsed_rshoulder_left = measure(lambda: JointType.RIGHT_SHOULDER.is_left, iterations=100_000)
    _check(r, "JointType.RIGHT_SHOULDER.is_left (False)", elapsed_rshoulder_left, limit)

    # is_right 프로퍼티 (frozenset 멤버십)
    elapsed_relbow_right = measure(lambda: JointType.RIGHT_ELBOW.is_right, iterations=100_000)
    _check(r, "JointType.RIGHT_ELBOW.is_right", elapsed_relbow_right, limit)

    elapsed_nose_right = measure(lambda: JointType.NOSE.is_right, iterations=100_000)
    _check(r, "JointType.NOSE.is_right (False)", elapsed_nose_right, limit)

    # symmetric_joint 프로퍼티 (dict 조회 -> JointType 반환)
    elapsed_sym_lknee = measure(lambda: JointType.LEFT_KNEE.symmetric_joint, iterations=100_000)
    _check(r, "JointType.LEFT_KNEE.symmetric_joint", elapsed_sym_lknee, limit)

    elapsed_sym_nose = measure(lambda: JointType.NOSE.symmetric_joint, iterations=100_000)
    _check(r, "JointType.NOSE.symmetric_joint (self)", elapsed_sym_nose, limit)

    # to_korean 프로퍼티 (캐시 dict 조회)
    elapsed_ko_lwrist = measure(lambda: JointType.LEFT_WRIST.to_korean, iterations=100_000)
    _check(r, "JointType.LEFT_WRIST.to_korean", elapsed_ko_lwrist, limit)

    elapsed_ko_rankle = measure(lambda: JointType.RIGHT_ANKLE.to_korean, iterations=100_000)
    _check(r, "JointType.RIGHT_ANKLE.to_korean", elapsed_ko_rankle, limit)


# ==================== 8. JointType.get_name() 다국어 조회 ====================
def test_joint_type_get_name_i18n(r: PerfResult) -> None:
    """JointType.get_name() 5개 언어별 조회 (< 1us each)"""
    from shared.constants.pose_constants import JointType
    from shared.constants.localization import SupportedLanguage

    limit = 1.0

    elapsed_ko = measure(
        lambda: JointType.LEFT_SHOULDER.get_name(SupportedLanguage.KO), iterations=100_000
    )
    _check(r, "JointType.get_name(KO)", elapsed_ko, limit)

    elapsed_en = measure(
        lambda: JointType.RIGHT_WRIST.get_name(SupportedLanguage.EN), iterations=100_000
    )
    _check(r, "JointType.get_name(EN)", elapsed_en, limit)

    elapsed_ja = measure(
        lambda: JointType.LEFT_KNEE.get_name(SupportedLanguage.JA), iterations=100_000
    )
    _check(r, "JointType.get_name(JA)", elapsed_ja, limit)

    elapsed_zh = measure(
        lambda: JointType.RIGHT_HIP.get_name(SupportedLanguage.ZH), iterations=100_000
    )
    _check(r, "JointType.get_name(ZH)", elapsed_zh, limit)

    elapsed_es = measure(
        lambda: JointType.LEFT_ANKLE.get_name(SupportedLanguage.ES), iterations=100_000
    )
    _check(r, "JointType.get_name(ES)", elapsed_es, limit)


# ==================== 9. 키포인트 그룹 frozenset 멤버십 테스트 ====================
def test_keypoint_group_membership(r: PerfResult) -> None:
    """frozenset 멤버십 (in 연산) 성능 (< 0.5us)"""
    from shared.constants.pose_constants import (
        SHOOTING_CRITICAL_KEYPOINTS,
        DRIBBLING_CRITICAL_KEYPOINTS,
        UPPER_BODY_KEYPOINTS,
        LOWER_BODY_KEYPOINTS,
    )

    limit = 0.5

    # SHOOTING_CRITICAL_KEYPOINTS (10개 멤버) - 존재하는 키포인트
    elapsed_shoot_in = measure(lambda: 5 in SHOOTING_CRITICAL_KEYPOINTS, iterations=100_000)
    _check(r, "5 in SHOOTING_CRITICAL_KEYPOINTS (True)", elapsed_shoot_in, limit)

    # SHOOTING_CRITICAL_KEYPOINTS - 존재하지 않는 키포인트
    elapsed_shoot_out = measure(lambda: 0 in SHOOTING_CRITICAL_KEYPOINTS, iterations=100_000)
    _check(r, "0 in SHOOTING_CRITICAL_KEYPOINTS (False)", elapsed_shoot_out, limit)

    # DRIBBLING_CRITICAL_KEYPOINTS (8개 멤버) - 존재하는 키포인트
    elapsed_drib_in = measure(lambda: 9 in DRIBBLING_CRITICAL_KEYPOINTS, iterations=100_000)
    _check(r, "9 in DRIBBLING_CRITICAL_KEYPOINTS (True)", elapsed_drib_in, limit)

    # DRIBBLING_CRITICAL_KEYPOINTS - 존재하지 않는 키포인트
    elapsed_drib_out = measure(lambda: 0 in DRIBBLING_CRITICAL_KEYPOINTS, iterations=100_000)
    _check(r, "0 in DRIBBLING_CRITICAL_KEYPOINTS (False)", elapsed_drib_out, limit)

    # UPPER_BODY_KEYPOINTS (9개 멤버)
    elapsed_upper_in = measure(lambda: 7 in UPPER_BODY_KEYPOINTS, iterations=100_000)
    _check(r, "7 in UPPER_BODY_KEYPOINTS (True)", elapsed_upper_in, limit)

    # LOWER_BODY_KEYPOINTS (6개 멤버)
    elapsed_lower_in = measure(lambda: 13 in LOWER_BODY_KEYPOINTS, iterations=100_000)
    _check(r, "13 in LOWER_BODY_KEYPOINTS (True)", elapsed_lower_in, limit)

    elapsed_lower_out = measure(lambda: 5 in LOWER_BODY_KEYPOINTS, iterations=100_000)
    _check(r, "5 in LOWER_BODY_KEYPOINTS (False)", elapsed_lower_out, limit)


# ==================== 10. COCO 스켈레톤 연결 순회 ====================
def test_coco_skeleton_connections_traversal(r: PerfResult) -> None:
    """COCO 스켈레톤 연결 16개 튜플 순회 (< 5us)"""
    from shared.constants.pose_constants import COCO_SKELETON_CONNECTIONS, NUM_COCO_CONNECTIONS

    limit = 5.0

    # 전체 연결 순회 (16개 튜플)
    def traverse_connections():
        for start, end in COCO_SKELETON_CONNECTIONS:
            _ = start
            _ = end

    elapsed_traverse = measure(traverse_connections, iterations=100_000)
    _check(r, "COCO_SKELETON_CONNECTIONS 순회 (16개)", elapsed_traverse, limit)

    # NUM_COCO_CONNECTIONS 상수 접근
    limit_const = 0.5
    elapsed_num = measure(lambda: NUM_COCO_CONNECTIONS, iterations=100_000)
    _check(r, "NUM_COCO_CONNECTIONS 접근", elapsed_num, limit_const)

    # 연결 튜플 인덱싱 (특정 연결 접근)
    limit_index = 1.0
    elapsed_idx = measure(lambda: COCO_SKELETON_CONNECTIONS[0], iterations=100_000)
    _check(r, "COCO_SKELETON_CONNECTIONS[0] 인덱싱", elapsed_idx, limit_index)

    elapsed_idx_last = measure(lambda: COCO_SKELETON_CONNECTIONS[-1], iterations=100_000)
    _check(r, "COCO_SKELETON_CONNECTIONS[-1] 인덱싱", elapsed_idx_last, limit_index)


# ==================== 11. 상수 접근 (각도, 신뢰도, 모델 파라미터) ====================
def test_constant_access(r: PerfResult) -> None:
    """신뢰도 임계값, 각도 범위, 모델 파라미터 접근 (< 0.5us)"""
    from shared.constants.pose_constants import (
        # 신뢰도 임계값
        JOINT_CONFIDENCE_THRESHOLD,
        HIGH_CONFIDENCE_THRESHOLD,
        LOW_CONFIDENCE_THRESHOLD,
        SKELETON_COMPLETENESS_THRESHOLD,
        MIN_SKELETON_COMPLETENESS,
        UPPER_BODY_COMPLETENESS_THRESHOLD,
        LOWER_BODY_COMPLETENESS_THRESHOLD,
        # 관절 각도 범위
        ELBOW_ANGLE_MIN_DEG,
        ELBOW_ANGLE_MAX_DEG,
        KNEE_ANGLE_MIN_DEG,
        KNEE_ANGLE_MAX_DEG,
        SHOULDER_ANGLE_MIN_DEG,
        SHOULDER_ANGLE_MAX_DEG,
        HIP_ANGLE_MIN_DEG,
        HIP_ANGLE_MAX_DEG,
        ANKLE_ANGLE_MIN_DEG,
        ANKLE_ANGLE_MAX_DEG,
        # 슈팅 각도
        OPTIMAL_RELEASE_ANGLE_MIN_DEG,
        OPTIMAL_RELEASE_ANGLE_MAX_DEG,
        RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG,
        RECOMMENDED_KNEE_BEND_ANGLE_DEG,
        WRIST_FLEXION_MIN_DEG,
        WRIST_FLEXION_MAX_DEG,
        # 모델 파라미터
        POSE_INPUT_SIZE,
        POSE_INPUT_SIZE_HIGH,
        HEATMAP_OUTPUT_SIZE,
        HEATMAP_GAUSSIAN_SIGMA,
        POSE_NMS_KERNEL_SIZE,
    )

    limit = 0.5

    # 신뢰도 임계값 접근 (7개 상수 일괄)
    def access_confidence_thresholds():
        _ = JOINT_CONFIDENCE_THRESHOLD
        _ = HIGH_CONFIDENCE_THRESHOLD
        _ = LOW_CONFIDENCE_THRESHOLD
        _ = SKELETON_COMPLETENESS_THRESHOLD
        _ = MIN_SKELETON_COMPLETENESS
        _ = UPPER_BODY_COMPLETENESS_THRESHOLD
        _ = LOWER_BODY_COMPLETENESS_THRESHOLD

    elapsed_conf = measure(access_confidence_thresholds, iterations=100_000)
    per_conf = elapsed_conf / 7
    _check(r, "신뢰도 임계값 상수 접근 (7개 평균)", per_conf, limit)

    # 관절 각도 범위 접근 (10개 상수 일괄)
    def access_angle_ranges():
        _ = ELBOW_ANGLE_MIN_DEG
        _ = ELBOW_ANGLE_MAX_DEG
        _ = KNEE_ANGLE_MIN_DEG
        _ = KNEE_ANGLE_MAX_DEG
        _ = SHOULDER_ANGLE_MIN_DEG
        _ = SHOULDER_ANGLE_MAX_DEG
        _ = HIP_ANGLE_MIN_DEG
        _ = HIP_ANGLE_MAX_DEG
        _ = ANKLE_ANGLE_MIN_DEG
        _ = ANKLE_ANGLE_MAX_DEG

    elapsed_angle = measure(access_angle_ranges, iterations=100_000)
    per_angle = elapsed_angle / 10
    _check(r, "관절 각도 범위 상수 접근 (10개 평균)", per_angle, limit)

    # 슈팅 각도 기준 접근 (6개 상수 일괄)
    def access_shooting_angles():
        _ = OPTIMAL_RELEASE_ANGLE_MIN_DEG
        _ = OPTIMAL_RELEASE_ANGLE_MAX_DEG
        _ = RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG
        _ = RECOMMENDED_KNEE_BEND_ANGLE_DEG
        _ = WRIST_FLEXION_MIN_DEG
        _ = WRIST_FLEXION_MAX_DEG

    elapsed_shoot = measure(access_shooting_angles, iterations=100_000)
    per_shoot = elapsed_shoot / 6
    _check(r, "슈팅 각도 기준 상수 접근 (6개 평균)", per_shoot, limit)

    # 모델 파라미터 접근 (5개 상수 일괄)
    def access_model_params():
        _ = POSE_INPUT_SIZE
        _ = POSE_INPUT_SIZE_HIGH
        _ = HEATMAP_OUTPUT_SIZE
        _ = HEATMAP_GAUSSIAN_SIGMA
        _ = POSE_NMS_KERNEL_SIZE

    elapsed_model = measure(access_model_params, iterations=100_000)
    per_model = elapsed_model / 5
    _check(r, "모델 파라미터 상수 접근 (5개 평균)", per_model, limit)

    # 튜플 인덱싱 (POSE_INPUT_SIZE 등)
    def access_tuple_index():
        _ = POSE_INPUT_SIZE[0]
        _ = POSE_INPUT_SIZE[1]
        _ = HEATMAP_OUTPUT_SIZE[0]
        _ = HEATMAP_OUTPUT_SIZE[1]

    elapsed_tuple = measure(access_tuple_index, iterations=100_000)
    per_tuple = elapsed_tuple / 4
    _check(r, "모델 파라미터 튜플 인덱싱 (4개 평균)", per_tuple, limit)


# ==================== 12. Enum 이터레이션 ====================
def test_enum_iteration(r: PerfResult) -> None:
    """각 Enum별 순회 성능 (< 5us)"""
    from shared.constants.pose_constants import PoseQuality, SkeletonType, JointType

    limit = 5.0

    # PoseQuality (4개 멤버)
    def iterate_pose_quality():
        for pq in PoseQuality:
            _ = pq.value

    elapsed_pq = measure(iterate_pose_quality, iterations=100_000)
    _check(r, "PoseQuality 순회 (4개 멤버)", elapsed_pq, limit)

    # SkeletonType (6개 멤버)
    def iterate_skeleton_type():
        for st in SkeletonType:
            _ = st.value

    elapsed_st = measure(iterate_skeleton_type, iterations=100_000)
    _check(r, "SkeletonType 순회 (6개 멤버)", elapsed_st, limit)

    # JointType (17개 멤버 - IntEnum)
    limit_joint = 10.0  # 17개로 멤버가 많으므로 한도 상향
    def iterate_joint_type():
        for jt in JointType:
            _ = jt.value

    elapsed_jt = measure(iterate_joint_type, iterations=100_000)
    _check(r, "JointType 순회 (17개 멤버)", elapsed_jt, limit_joint)

    # JointType 순회 + 프로퍼티 접근 (is_left 등)
    limit_joint_prop = 20.0
    def iterate_joint_with_props():
        for jt in JointType:
            _ = jt.is_left
            _ = jt.is_right

    elapsed_jt_prop = measure(iterate_joint_with_props, iterations=50_000)
    _check(r, "JointType 순회 + is_left/is_right (17개)", elapsed_jt_prop, limit_joint_prop)

    # 전체 Enum 순회 (4+6+17 = 27개 멤버 합산)
    limit_all = 15.0
    def iterate_all():
        for pq in PoseQuality:
            _ = pq.value
        for st in SkeletonType:
            _ = st.value
        for jt in JointType:
            _ = jt.value

    elapsed_all = measure(iterate_all, iterations=100_000)
    _check(r, "전체 Enum 순회 (27개 멤버)", elapsed_all, limit_all)


# ==================== 13. 복합 시나리오 (포즈 분석 파이프라인 시뮬레이션) ====================
def test_composite_pose_analysis_pipeline(r: PerfResult) -> None:
    """복합 시나리오: 포즈 분석 파이프라인 시뮬레이션 (< 50us)"""
    from shared.constants.pose_constants import (
        PoseQuality, SkeletonType, JointType,
        JOINT_CONFIDENCE_THRESHOLD, HIGH_CONFIDENCE_THRESHOLD,
        SKELETON_COMPLETENESS_THRESHOLD,
        SHOOTING_CRITICAL_KEYPOINTS, DRIBBLING_CRITICAL_KEYPOINTS,
        UPPER_BODY_KEYPOINTS, LOWER_BODY_KEYPOINTS,
        COCO_SKELETON_CONNECTIONS,
        ELBOW_ANGLE_MIN_DEG, ELBOW_ANGLE_MAX_DEG,
        KNEE_ANGLE_MIN_DEG, KNEE_ANGLE_MAX_DEG,
        OPTIMAL_RELEASE_ANGLE_MIN_DEG, OPTIMAL_RELEASE_ANGLE_MAX_DEG,
        POSE_INPUT_SIZE, HEATMAP_OUTPUT_SIZE,
        KEYPOINT_LEFT_SHOULDER, KEYPOINT_RIGHT_SHOULDER,
        KEYPOINT_LEFT_ELBOW, KEYPOINT_RIGHT_ELBOW,
    )
    from shared.constants.localization import SupportedLanguage

    limit = 50.0

    def pose_analysis_pipeline():
        # 1. 스켈레톤 타입 결정 및 키포인트 수 확인
        skel_type = SkeletonType.COCO
        num_kp = skel_type.num_keypoints
        has_hand = skel_type.has_hand_keypoints
        skel_name = skel_type.to_korean

        # 2. 입력 크기 및 히트맵 확인
        input_h, input_w = POSE_INPUT_SIZE
        heatmap_h, heatmap_w = HEATMAP_OUTPUT_SIZE

        # 3. 포즈 품질 판별 (완전성 기반)
        quality = PoseQuality.from_completeness(0.75)
        is_usable = quality.is_usable
        is_reliable = quality.is_reliable
        quality_name = quality.quality_name
        quality_ko = quality.to_korean

        # 4. 슈팅 분석용 핵심 키포인트 확인
        left_shoulder_needed = KEYPOINT_LEFT_SHOULDER in SHOOTING_CRITICAL_KEYPOINTS
        right_elbow_needed = KEYPOINT_RIGHT_ELBOW in SHOOTING_CRITICAL_KEYPOINTS

        # 5. 드리블 분석용 키포인트 확인
        left_elbow_drib = KEYPOINT_LEFT_ELBOW in DRIBBLING_CRITICAL_KEYPOINTS

        # 6. 상/하체 키포인트 그룹 확인
        shoulder_upper = KEYPOINT_LEFT_SHOULDER in UPPER_BODY_KEYPOINTS
        shoulder_lower = KEYPOINT_LEFT_SHOULDER in LOWER_BODY_KEYPOINTS

        # 7. 스켈레톤 연결 순회 (스켈레톤 드로잉 시뮬레이션)
        for start_kp, end_kp in COCO_SKELETON_CONNECTIONS:
            _ = start_kp + end_kp

        # 8. 관절 각도 범위 확인
        elbow_range = ELBOW_ANGLE_MAX_DEG - ELBOW_ANGLE_MIN_DEG
        knee_range = KNEE_ANGLE_MAX_DEG - KNEE_ANGLE_MIN_DEG

        # 9. 릴리즈 각도 판별
        test_angle = 50.0
        is_optimal = OPTIMAL_RELEASE_ANGLE_MIN_DEG <= test_angle <= OPTIMAL_RELEASE_ANGLE_MAX_DEG

        # 10. 신뢰도 판별
        test_conf = 0.65
        is_valid = test_conf >= JOINT_CONFIDENCE_THRESHOLD
        is_high = test_conf >= HIGH_CONFIDENCE_THRESHOLD

        # 11. JointType 대칭 관절 조회
        sym = JointType.LEFT_SHOULDER.symmetric_joint
        is_left = JointType.LEFT_KNEE.is_left

        # 12. 다국어 이름 조회
        joint_name_en = JointType.LEFT_WRIST.get_name(SupportedLanguage.EN)
        quality_name_en = quality.get_name(SupportedLanguage.EN)

    elapsed = measure(pose_analysis_pipeline, iterations=50_000)
    _check(r, "포즈 분석 파이프라인 시뮬레이션", elapsed, limit)


# ==================== 14. 대량 처리량 ====================
def test_bulk_operations(r: PerfResult) -> None:
    """대량 처리량: 1,000회 반복 (3개 Enum 전체 프로퍼티 + 상수) (< 500ms)"""
    from shared.constants.pose_constants import (
        PoseQuality, SkeletonType, JointType,
        JOINT_CONFIDENCE_THRESHOLD, HIGH_CONFIDENCE_THRESHOLD,
        LOW_CONFIDENCE_THRESHOLD, SKELETON_COMPLETENESS_THRESHOLD,
        SHOOTING_CRITICAL_KEYPOINTS, DRIBBLING_CRITICAL_KEYPOINTS,
        UPPER_BODY_KEYPOINTS, LOWER_BODY_KEYPOINTS,
        COCO_SKELETON_CONNECTIONS, NUM_COCO_CONNECTIONS,
        ELBOW_ANGLE_MIN_DEG, ELBOW_ANGLE_MAX_DEG,
        KNEE_ANGLE_MIN_DEG, KNEE_ANGLE_MAX_DEG,
        SHOULDER_ANGLE_MIN_DEG, SHOULDER_ANGLE_MAX_DEG,
        OPTIMAL_RELEASE_ANGLE_MIN_DEG, OPTIMAL_RELEASE_ANGLE_MAX_DEG,
        POSE_INPUT_SIZE, HEATMAP_OUTPUT_SIZE,
        HEATMAP_GAUSSIAN_SIGMA, POSE_NMS_KERNEL_SIZE,
    )
    from shared.constants.localization import SupportedLanguage

    iterations = 1_000

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        # PoseQuality 전체 프로퍼티 + i18n
        for pq in PoseQuality:
            _ = pq.quality_name
            _ = pq.min_completeness
            _ = pq.max_completeness
            _ = pq.is_usable
            _ = pq.is_reliable
            _ = pq.to_korean
            _ = pq.get_name(SupportedLanguage.EN)

        # PoseQuality.from_completeness 경계값
        _ = PoseQuality.from_completeness(0.0)
        _ = PoseQuality.from_completeness(0.4)
        _ = PoseQuality.from_completeness(0.6)
        _ = PoseQuality.from_completeness(0.8)
        _ = PoseQuality.from_completeness(1.0)

        # SkeletonType 전체 프로퍼티 + i18n
        for st in SkeletonType:
            _ = st.num_keypoints
            _ = st.has_hand_keypoints
            _ = st.has_face_keypoints
            _ = st.to_korean
            _ = st.get_name(SupportedLanguage.EN)

        # JointType 전체 프로퍼티 (17개 멤버)
        for jt in JointType:
            _ = jt.is_left
            _ = jt.is_right
            _ = jt.symmetric_joint
            _ = jt.to_korean

        # JointType i18n (대표 5개)
        _ = JointType.NOSE.get_name(SupportedLanguage.KO)
        _ = JointType.LEFT_SHOULDER.get_name(SupportedLanguage.EN)
        _ = JointType.RIGHT_KNEE.get_name(SupportedLanguage.JA)
        _ = JointType.LEFT_WRIST.get_name(SupportedLanguage.ZH)
        _ = JointType.RIGHT_ANKLE.get_name(SupportedLanguage.ES)

        # frozenset 멤버십 테스트
        _ = 5 in SHOOTING_CRITICAL_KEYPOINTS
        _ = 9 in DRIBBLING_CRITICAL_KEYPOINTS
        _ = 7 in UPPER_BODY_KEYPOINTS
        _ = 13 in LOWER_BODY_KEYPOINTS
        _ = 0 in SHOOTING_CRITICAL_KEYPOINTS
        _ = 16 in LOWER_BODY_KEYPOINTS

        # 스켈레톤 연결 순회
        for s, e in COCO_SKELETON_CONNECTIONS:
            _ = s + e
        _ = NUM_COCO_CONNECTIONS

        # 상수 접근
        _ = JOINT_CONFIDENCE_THRESHOLD
        _ = HIGH_CONFIDENCE_THRESHOLD
        _ = LOW_CONFIDENCE_THRESHOLD
        _ = SKELETON_COMPLETENESS_THRESHOLD
        _ = ELBOW_ANGLE_MIN_DEG
        _ = ELBOW_ANGLE_MAX_DEG
        _ = KNEE_ANGLE_MIN_DEG
        _ = KNEE_ANGLE_MAX_DEG
        _ = SHOULDER_ANGLE_MIN_DEG
        _ = SHOULDER_ANGLE_MAX_DEG
        _ = OPTIMAL_RELEASE_ANGLE_MIN_DEG
        _ = OPTIMAL_RELEASE_ANGLE_MAX_DEG
        _ = POSE_INPUT_SIZE[0]
        _ = POSE_INPUT_SIZE[1]
        _ = HEATMAP_OUTPUT_SIZE[0]
        _ = HEATMAP_GAUSSIAN_SIGMA
        _ = POSE_NMS_KERNEL_SIZE

    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 500.0

    r.info(f"1,000회 반복 (3개 Enum + ~70개 상수 전체) 처리 시간: {elapsed_ms:.2f}ms")
    _check(r, f"대량 처리량 ({iterations:,}회 x 3 Enum + 상수)", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 15. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 측정"""
    import sys as _sys
    from shared.constants.pose_constants import (
        PoseQuality, SkeletonType, JointType,
        SHOOTING_CRITICAL_KEYPOINTS, DRIBBLING_CRITICAL_KEYPOINTS,
        UPPER_BODY_KEYPOINTS, LOWER_BODY_KEYPOINTS,
        COCO_SKELETON_CONNECTIONS,
        POSE_INPUT_SIZE, POSE_INPUT_SIZE_HIGH,
        HEATMAP_OUTPUT_SIZE,
    )

    sizes = {
        "PoseQuality (Enum)": _sys.getsizeof(PoseQuality),
        "SkeletonType (Enum)": _sys.getsizeof(SkeletonType),
        "JointType (IntEnum)": _sys.getsizeof(JointType),
        "SHOOTING_CRITICAL_KEYPOINTS (frozenset)": _sys.getsizeof(SHOOTING_CRITICAL_KEYPOINTS),
        "DRIBBLING_CRITICAL_KEYPOINTS (frozenset)": _sys.getsizeof(DRIBBLING_CRITICAL_KEYPOINTS),
        "UPPER_BODY_KEYPOINTS (frozenset)": _sys.getsizeof(UPPER_BODY_KEYPOINTS),
        "LOWER_BODY_KEYPOINTS (frozenset)": _sys.getsizeof(LOWER_BODY_KEYPOINTS),
        "COCO_SKELETON_CONNECTIONS (list)": _sys.getsizeof(COCO_SKELETON_CONNECTIONS),
        "POSE_INPUT_SIZE (tuple)": _sys.getsizeof(POSE_INPUT_SIZE),
        "POSE_INPUT_SIZE_HIGH (tuple)": _sys.getsizeof(POSE_INPUT_SIZE_HIGH),
        "HEATMAP_OUTPUT_SIZE (tuple)": _sys.getsizeof(HEATMAP_OUTPUT_SIZE),
    }
    total = sum(sizes.values())

    print(f"\n  메모리 사용량:")
    for k, v in sizes.items():
        print(f"    {k}: {v} bytes")
    print(f"    TOTAL: {total/1024:.1f}KB")

    # 메모리 측정은 항상 PASS (정보 목적)
    r.passed += 1


# ==================== 실행 ====================
def main():
    perf = PerfResult()
    print("\n" + "=" * 60)
    print("pose_constants.py v2.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 1. 모듈 임포트 ---")
    test_module_import(perf)

    print("\n--- 2. PoseQuality 프로퍼티 접근 ---")
    test_pose_quality_property_access(perf)

    print("\n--- 3. PoseQuality.from_completeness() 변환 ---")
    test_pose_quality_from_completeness(perf)

    print("\n--- 4. PoseQuality.get_name() 다국어 ---")
    test_pose_quality_get_name_i18n(perf)

    print("\n--- 5. SkeletonType 프로퍼티 접근 ---")
    test_skeleton_type_property_access(perf)

    print("\n--- 6. SkeletonType.get_name() 다국어 ---")
    test_skeleton_type_get_name_i18n(perf)

    print("\n--- 7. JointType 프로퍼티 접근 ---")
    test_joint_type_property_access(perf)

    print("\n--- 8. JointType.get_name() 다국어 ---")
    test_joint_type_get_name_i18n(perf)

    print("\n--- 9. 키포인트 그룹 frozenset 멤버십 ---")
    test_keypoint_group_membership(perf)

    print("\n--- 10. COCO 스켈레톤 연결 순회 ---")
    test_coco_skeleton_connections_traversal(perf)

    print("\n--- 11. 상수 접근 (각도, 신뢰도, 모델 파라미터) ---")
    test_constant_access(perf)

    print("\n--- 12. Enum 이터레이션 ---")
    test_enum_iteration(perf)

    print("\n--- 13. 복합 시나리오 ---")
    test_composite_pose_analysis_pipeline(perf)

    print("\n--- 14. 대량 처리량 ---")
    test_bulk_operations(perf)

    print("\n--- 15. 메모리 사용량 ---")
    test_memory_usage(perf)

    perf.summary()
    return 0 if perf.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
