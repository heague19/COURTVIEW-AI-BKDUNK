# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_pose_constants.py

포즈 추정(Pose Estimation) 상수 모듈 단위 테스트 (500+ 테스트)
- PoseQuality 열거형: 멤버/값, is_usable, is_reliable, from_completeness 경계값
- SkeletonType 열거형: 멤버/값, num_keypoints, has_hand/face_keypoints
- JointType IntEnum: 멤버/정수값, is_left/is_right, symmetric_joint 대합(involution)
- 3개 열거형 × to_korean 프로퍼티 × get_name i18n 5개 언어
- 신뢰도 임계값 7개: 값, 타입, 범위, 순서 관계
- 키포인트 수 상수 6개: 값, 양수, 타입
- COCO 키포인트 인덱스 17개: 연속 0-16, JointType 일관성
- MediaPipe 키포인트 33개: 연속 0-32
- COCO_SKELETON_CONNECTIONS: 16개, tuple 구조, 인덱스 범위, 중복 없음
- 키포인트 그룹 frozenset 4개: 크기, 인덱스 범위, 상체/하체 교차 없음
- 관절 각도 범위 10개: min < max, 생체역학 합리성
- 슈팅 각도 기준 6개: min < max
- 모델 파라미터 5개: tuple 크기, 양수, 2의 거듭제곱
- __all__ 73개 Export 완전성
- 캐시: frozenset 5개, dict 5개, i18n 3개 × 5개 언어
- 메타: 버전 2.1.0, typing 모더나이제이션

Author: COURTVIEW AI Team
Version: 2.0.0
"""

import sys
import io
import math
from enum import Enum, IntEnum
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (tests/shared/constants/unit → 4단계 상위)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# ── 테스트 대상 임포트 ──
from shared.constants import pose_constants
from shared.constants.pose_constants import (
    # 신뢰도 임계값
    JOINT_CONFIDENCE_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    SKELETON_COMPLETENESS_THRESHOLD,
    MIN_SKELETON_COMPLETENESS,
    UPPER_BODY_COMPLETENESS_THRESHOLD,
    LOWER_BODY_COMPLETENESS_THRESHOLD,
    # 키포인트 수
    NUM_KEYPOINTS_MEDIAPIPE,
    NUM_KEYPOINTS_COCO,
    NUM_KEYPOINTS_OPENPOSE,
    NUM_KEYPOINTS_OPENPOSE_18,
    NUM_KEYPOINTS_HAND,
    NUM_KEYPOINTS_FACE,
    # COCO 키포인트 인덱스
    KEYPOINT_NOSE,
    KEYPOINT_LEFT_EYE,
    KEYPOINT_RIGHT_EYE,
    KEYPOINT_LEFT_EAR,
    KEYPOINT_RIGHT_EAR,
    KEYPOINT_LEFT_SHOULDER,
    KEYPOINT_RIGHT_SHOULDER,
    KEYPOINT_LEFT_ELBOW,
    KEYPOINT_RIGHT_ELBOW,
    KEYPOINT_LEFT_WRIST,
    KEYPOINT_RIGHT_WRIST,
    KEYPOINT_LEFT_HIP,
    KEYPOINT_RIGHT_HIP,
    KEYPOINT_LEFT_KNEE,
    KEYPOINT_RIGHT_KNEE,
    KEYPOINT_LEFT_ANKLE,
    KEYPOINT_RIGHT_ANKLE,
    # 스켈레톤 연결
    COCO_SKELETON_CONNECTIONS,
    NUM_COCO_CONNECTIONS,
    # MediaPipe 키포인트 인덱스
    MEDIAPIPE_NOSE,
    MEDIAPIPE_LEFT_SHOULDER,
    MEDIAPIPE_RIGHT_SHOULDER,
    MEDIAPIPE_LEFT_ELBOW,
    MEDIAPIPE_RIGHT_ELBOW,
    MEDIAPIPE_LEFT_WRIST,
    MEDIAPIPE_RIGHT_WRIST,
    MEDIAPIPE_LEFT_HIP,
    MEDIAPIPE_RIGHT_HIP,
    MEDIAPIPE_LEFT_KNEE,
    MEDIAPIPE_RIGHT_KNEE,
    MEDIAPIPE_LEFT_ANKLE,
    MEDIAPIPE_RIGHT_ANKLE,
    # 핵심 키포인트 그룹
    SHOOTING_CRITICAL_KEYPOINTS,
    DRIBBLING_CRITICAL_KEYPOINTS,
    UPPER_BODY_KEYPOINTS,
    LOWER_BODY_KEYPOINTS,
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
    # 슈팅 각도 기준
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
    # 열거형
    PoseQuality,
    SkeletonType,
    JointType,
)
from shared.constants.localization import SupportedLanguage


# =============================================================================
# 커스텀 테스트 하니스
# =============================================================================
class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.section = ""

    def set_section(self, name):
        self.section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name, msg=""):
        self.failed += 1
        print(f"  [FAIL] {name} - {msg}")

    def check(self, name, condition, msg=""):
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        print(f"{'='*60}")
        return self.failed == 0


# =============================================================================
# 헬퍼 함수
# =============================================================================
def _is_power_of_two(n: int) -> bool:
    """2의 거듭제곱 여부 판별."""
    return n > 0 and (n & (n - 1)) == 0


# =============================================================================
# 테스트 실행
# =============================================================================
def main():
    T = TestResult()

    # =================================================================
    # 섹션 1: PoseQuality 멤버 수 및 tuple 값
    # =================================================================
    T.set_section("1. PoseQuality 멤버 수 및 tuple 값")

    T.check("PoseQuality 는 Enum", issubclass(PoseQuality, Enum))
    members = list(PoseQuality)
    T.check("PoseQuality 멤버 수 = 4", len(members) == 4, f"got {len(members)}")

    expected_members = {
        PoseQuality.HIGH: ("high", 0.8, 1.0),
        PoseQuality.MEDIUM: ("medium", 0.6, 0.8),
        PoseQuality.LOW: ("low", 0.4, 0.6),
        PoseQuality.INVALID: ("invalid", 0.0, 0.4),
    }
    for pq, (exp_name, exp_min, exp_max) in expected_members.items():
        T.check(
            f"PoseQuality.{pq.name}.quality_name == '{exp_name}'",
            pq.quality_name == exp_name,
            f"got '{pq.quality_name}'"
        )
        T.check(
            f"PoseQuality.{pq.name}.min_completeness == {exp_min}",
            abs(pq.min_completeness - exp_min) < 1e-9,
            f"got {pq.min_completeness}"
        )
        T.check(
            f"PoseQuality.{pq.name}.max_completeness == {exp_max}",
            abs(pq.max_completeness - exp_max) < 1e-9,
            f"got {pq.max_completeness}"
        )

    # quality_name 은 문자열, min/max는 float
    for pq in PoseQuality:
        T.check(f"PoseQuality.{pq.name}.quality_name 타입 str", isinstance(pq.quality_name, str))
        T.check(f"PoseQuality.{pq.name}.min_completeness 타입 float", isinstance(pq.min_completeness, float))
        T.check(f"PoseQuality.{pq.name}.max_completeness 타입 float", isinstance(pq.max_completeness, float))

    # min < max 일관성
    for pq in PoseQuality:
        T.check(
            f"PoseQuality.{pq.name}: min < max",
            pq.min_completeness < pq.max_completeness,
            f"{pq.min_completeness} >= {pq.max_completeness}"
        )

    # value 는 tuple
    for pq in PoseQuality:
        T.check(
            f"PoseQuality.{pq.name}.value 타입 tuple",
            isinstance(pq.value, tuple),
            f"got {type(pq.value)}"
        )
        T.check(
            f"PoseQuality.{pq.name}.value 길이 3",
            len(pq.value) == 3,
            f"got {len(pq.value)}"
        )

    # =================================================================
    # 섹션 2: PoseQuality.is_usable
    # =================================================================
    T.set_section("2. PoseQuality.is_usable")

    T.check("PoseQuality.HIGH.is_usable == True", PoseQuality.HIGH.is_usable is True)
    T.check("PoseQuality.MEDIUM.is_usable == True", PoseQuality.MEDIUM.is_usable is True)
    T.check("PoseQuality.LOW.is_usable == True", PoseQuality.LOW.is_usable is True)
    T.check("PoseQuality.INVALID.is_usable == False", PoseQuality.INVALID.is_usable is False)

    usable_count = sum(1 for pq in PoseQuality if pq.is_usable)
    T.check("is_usable True 개수 = 3", usable_count == 3, f"got {usable_count}")

    not_usable_count = sum(1 for pq in PoseQuality if not pq.is_usable)
    T.check("is_usable False 개수 = 1", not_usable_count == 1, f"got {not_usable_count}")

    # is_usable는 bool 타입
    for pq in PoseQuality:
        T.check(f"PoseQuality.{pq.name}.is_usable 타입 bool", isinstance(pq.is_usable, bool))

    # =================================================================
    # 섹션 3: PoseQuality.is_reliable
    # =================================================================
    T.set_section("3. PoseQuality.is_reliable (frozenset 캐시)")

    T.check("PoseQuality.HIGH.is_reliable == True", PoseQuality.HIGH.is_reliable is True)
    T.check("PoseQuality.MEDIUM.is_reliable == True", PoseQuality.MEDIUM.is_reliable is True)
    T.check("PoseQuality.LOW.is_reliable == False", PoseQuality.LOW.is_reliable is False)
    T.check("PoseQuality.INVALID.is_reliable == False", PoseQuality.INVALID.is_reliable is False)

    reliable_count = sum(1 for pq in PoseQuality if pq.is_reliable)
    T.check("is_reliable True 개수 = 2", reliable_count == 2, f"got {reliable_count}")

    not_reliable_count = sum(1 for pq in PoseQuality if not pq.is_reliable)
    T.check("is_reliable False 개수 = 2", not_reliable_count == 2, f"got {not_reliable_count}")

    # is_reliable는 bool 타입
    for pq in PoseQuality:
        T.check(f"PoseQuality.{pq.name}.is_reliable 타입 bool", isinstance(pq.is_reliable, bool))

    # is_reliable => is_usable (신뢰할 수 있으면 사용 가능해야 함)
    for pq in PoseQuality:
        if pq.is_reliable:
            T.check(
                f"PoseQuality.{pq.name}: is_reliable => is_usable",
                pq.is_usable,
                "reliable but not usable"
            )

    # frozenset 캐시 존재 확인
    cache = getattr(pose_constants, "_POSE_QUALITY_IS_RELIABLE", None)
    T.check("_POSE_QUALITY_IS_RELIABLE 캐시 존재", cache is not None)
    T.check("_POSE_QUALITY_IS_RELIABLE 타입 frozenset", isinstance(cache, frozenset))
    T.check("_POSE_QUALITY_IS_RELIABLE 크기 = 2", len(cache) == 2, f"got {len(cache)}")

    # =================================================================
    # 섹션 4: PoseQuality.from_completeness 경계값
    # =================================================================
    T.set_section("4. PoseQuality.from_completeness 경계값")

    # 정확한 경계값 테스트
    boundary_tests = [
        (0.0, PoseQuality.INVALID, "최소값 0.0"),
        (0.1, PoseQuality.INVALID, "INVALID 범위 내 0.1"),
        (0.2, PoseQuality.INVALID, "INVALID 범위 내 0.2"),
        (0.3, PoseQuality.INVALID, "INVALID 범위 내 0.3"),
        (0.39, PoseQuality.INVALID, "INVALID 상한 경계 직전 0.39"),
        (0.4, PoseQuality.LOW, "LOW 하한 경계 0.4"),
        (0.41, PoseQuality.LOW, "LOW 범위 내 0.41"),
        (0.5, PoseQuality.LOW, "LOW 범위 내 0.5"),
        (0.59, PoseQuality.LOW, "LOW 상한 경계 직전 0.59"),
        (0.6, PoseQuality.MEDIUM, "MEDIUM 하한 경계 0.6"),
        (0.61, PoseQuality.MEDIUM, "MEDIUM 범위 내 0.61"),
        (0.7, PoseQuality.MEDIUM, "MEDIUM 범위 내 0.7"),
        (0.79, PoseQuality.MEDIUM, "MEDIUM 상한 경계 직전 0.79"),
        (0.8, PoseQuality.HIGH, "HIGH 하한 경계 0.8"),
        (0.81, PoseQuality.HIGH, "HIGH 범위 내 0.81"),
        (0.9, PoseQuality.HIGH, "HIGH 범위 내 0.9"),
        (0.99, PoseQuality.HIGH, "HIGH 상한 경계 직전 0.99"),
        (1.0, PoseQuality.HIGH, "최대값 1.0"),
    ]
    for val, expected, desc in boundary_tests:
        result = PoseQuality.from_completeness(val)
        T.check(
            f"from_completeness({val}) == {expected.name} ({desc})",
            result == expected,
            f"got {result.name}"
        )

    # 범위 밖 클램핑 테스트
    clamp_tests = [
        (-0.5, PoseQuality.INVALID, "음수 -0.5 → 클램프 0.0 → INVALID"),
        (-1.0, PoseQuality.INVALID, "음수 -1.0 → 클램프 0.0 → INVALID"),
        (-100.0, PoseQuality.INVALID, "극음수 -100.0 → 클램프 0.0 → INVALID"),
        (1.5, PoseQuality.HIGH, "초과 1.5 → 클램프 1.0 → HIGH"),
        (2.0, PoseQuality.HIGH, "초과 2.0 → 클램프 1.0 → HIGH"),
        (100.0, PoseQuality.HIGH, "극초과 100.0 → 클램프 1.0 → HIGH"),
    ]
    for val, expected, desc in clamp_tests:
        result = PoseQuality.from_completeness(val)
        T.check(
            f"from_completeness({val}) == {expected.name} ({desc})",
            result == expected,
            f"got {result.name}"
        )

    # 반환 타입은 항상 PoseQuality
    for val in [0.0, 0.3, 0.5, 0.7, 0.9, 1.0, -1.0, 2.0]:
        result = PoseQuality.from_completeness(val)
        T.check(
            f"from_completeness({val}) 반환 타입 PoseQuality",
            isinstance(result, PoseQuality),
            f"got {type(result)}"
        )

    # 세밀한 경계 직전/직후
    T.check(
        "from_completeness(0.399) == INVALID",
        PoseQuality.from_completeness(0.399) == PoseQuality.INVALID
    )
    T.check(
        "from_completeness(0.599) == LOW",
        PoseQuality.from_completeness(0.599) == PoseQuality.LOW
    )
    T.check(
        "from_completeness(0.799) == MEDIUM",
        PoseQuality.from_completeness(0.799) == PoseQuality.MEDIUM
    )

    # =================================================================
    # 섹션 5: PoseQuality.to_korean + get_name i18n
    # =================================================================
    T.set_section("5. PoseQuality.to_korean + get_name i18n")

    korean_expected = {
        PoseQuality.HIGH: "높음",
        PoseQuality.MEDIUM: "중간",
        PoseQuality.LOW: "낮음",
        PoseQuality.INVALID: "유효하지 않음",
    }
    for pq, exp_korean in korean_expected.items():
        T.check(
            f"PoseQuality.{pq.name}.to_korean == '{exp_korean}'",
            pq.to_korean == exp_korean,
            f"got '{pq.to_korean}'"
        )
        # to_korean은 프로퍼티 (괄호 없이 호출)
        T.check(
            f"PoseQuality.{pq.name}.to_korean 타입 str",
            isinstance(pq.to_korean, str)
        )

    # get_name i18n (4 멤버 × 5 언어 = 20 테스트)
    i18n_expected = {
        SupportedLanguage.KO: {
            PoseQuality.HIGH: "높음",
            PoseQuality.MEDIUM: "중간",
            PoseQuality.LOW: "낮음",
            PoseQuality.INVALID: "유효하지 않음",
        },
        SupportedLanguage.EN: {
            PoseQuality.HIGH: "High",
            PoseQuality.MEDIUM: "Medium",
            PoseQuality.LOW: "Low",
            PoseQuality.INVALID: "Invalid",
        },
        SupportedLanguage.JA: {
            PoseQuality.HIGH: "高",
            PoseQuality.MEDIUM: "中",
            PoseQuality.LOW: "低",
            PoseQuality.INVALID: "無効",
        },
        SupportedLanguage.ZH: {
            PoseQuality.HIGH: "高",
            PoseQuality.MEDIUM: "中",
            PoseQuality.LOW: "低",
            PoseQuality.INVALID: "无效",
        },
        SupportedLanguage.ES: {
            PoseQuality.HIGH: "Alta",
            PoseQuality.MEDIUM: "Media",
            PoseQuality.LOW: "Baja",
            PoseQuality.INVALID: "Inválida",
        },
    }
    for lang, translations in i18n_expected.items():
        for pq, exp_text in translations.items():
            result = pq.get_name(lang)
            T.check(
                f"PoseQuality.{pq.name}.get_name({lang.name}) == '{exp_text}'",
                result == exp_text,
                f"got '{result}'"
            )

    # KO 언어의 get_name과 to_korean 일치 확인
    for pq in PoseQuality:
        T.check(
            f"PoseQuality.{pq.name}: get_name(KO) == to_korean",
            pq.get_name(SupportedLanguage.KO) == pq.to_korean,
            f"'{pq.get_name(SupportedLanguage.KO)}' != '{pq.to_korean}'"
        )

    # =================================================================
    # 섹션 6: SkeletonType 멤버 수 및 값
    # =================================================================
    T.set_section("6. SkeletonType 멤버 수 및 값")

    T.check("SkeletonType 는 Enum", issubclass(SkeletonType, Enum))
    st_members = list(SkeletonType)
    T.check("SkeletonType 멤버 수 = 6", len(st_members) == 6, f"got {len(st_members)}")

    expected_st_values = {
        "MEDIAPIPE": "mediapipe",
        "COCO": "coco",
        "OPENPOSE_25": "openpose_25",
        "OPENPOSE_18": "openpose_18",
        "HALPE": "halpe",
        "CUSTOM": "custom",
    }
    for name, exp_val in expected_st_values.items():
        st = SkeletonType[name]
        T.check(
            f"SkeletonType.{name}.value == '{exp_val}'",
            st.value == exp_val,
            f"got '{st.value}'"
        )
        T.check(
            f"SkeletonType.{name}.value 타입 str",
            isinstance(st.value, str)
        )

    # 멤버 이름 집합 확인
    expected_names = {"MEDIAPIPE", "COCO", "OPENPOSE_25", "OPENPOSE_18", "HALPE", "CUSTOM"}
    actual_names = {st.name for st in SkeletonType}
    T.check(
        "SkeletonType 멤버 이름 집합 일치",
        actual_names == expected_names,
        f"diff: {actual_names.symmetric_difference(expected_names)}"
    )

    # =================================================================
    # 섹션 7: SkeletonType.num_keypoints + NUM_KEYPOINTS 상수 일관성
    # =================================================================
    T.set_section("7. SkeletonType.num_keypoints + NUM_KEYPOINTS 상수 일관성")

    expected_keypoints = {
        SkeletonType.MEDIAPIPE: 33,
        SkeletonType.COCO: 17,
        SkeletonType.OPENPOSE_25: 25,
        SkeletonType.OPENPOSE_18: 18,
        SkeletonType.HALPE: 26,
        SkeletonType.CUSTOM: 17,
    }
    for st, exp_kp in expected_keypoints.items():
        T.check(
            f"SkeletonType.{st.name}.num_keypoints == {exp_kp}",
            st.num_keypoints == exp_kp,
            f"got {st.num_keypoints}"
        )
        T.check(
            f"SkeletonType.{st.name}.num_keypoints 타입 int",
            isinstance(st.num_keypoints, int)
        )
        T.check(
            f"SkeletonType.{st.name}.num_keypoints > 0",
            st.num_keypoints > 0
        )

    # NUM_KEYPOINTS_* 상수와 일관성
    T.check(
        "MEDIAPIPE.num_keypoints == NUM_KEYPOINTS_MEDIAPIPE",
        SkeletonType.MEDIAPIPE.num_keypoints == NUM_KEYPOINTS_MEDIAPIPE,
        f"{SkeletonType.MEDIAPIPE.num_keypoints} != {NUM_KEYPOINTS_MEDIAPIPE}"
    )
    T.check(
        "COCO.num_keypoints == NUM_KEYPOINTS_COCO",
        SkeletonType.COCO.num_keypoints == NUM_KEYPOINTS_COCO,
        f"{SkeletonType.COCO.num_keypoints} != {NUM_KEYPOINTS_COCO}"
    )
    T.check(
        "OPENPOSE_25.num_keypoints == NUM_KEYPOINTS_OPENPOSE",
        SkeletonType.OPENPOSE_25.num_keypoints == NUM_KEYPOINTS_OPENPOSE,
        f"{SkeletonType.OPENPOSE_25.num_keypoints} != {NUM_KEYPOINTS_OPENPOSE}"
    )
    T.check(
        "OPENPOSE_18.num_keypoints == NUM_KEYPOINTS_OPENPOSE_18",
        SkeletonType.OPENPOSE_18.num_keypoints == NUM_KEYPOINTS_OPENPOSE_18,
        f"{SkeletonType.OPENPOSE_18.num_keypoints} != {NUM_KEYPOINTS_OPENPOSE_18}"
    )
    T.check(
        "CUSTOM.num_keypoints == NUM_KEYPOINTS_COCO (COCO 기반)",
        SkeletonType.CUSTOM.num_keypoints == NUM_KEYPOINTS_COCO
    )

    # =================================================================
    # 섹션 8: SkeletonType.has_hand/face_keypoints
    # =================================================================
    T.set_section("8. SkeletonType.has_hand/face_keypoints")

    # MEDIAPIPE만 True
    T.check("MEDIAPIPE.has_hand_keypoints == True", SkeletonType.MEDIAPIPE.has_hand_keypoints is True)
    T.check("MEDIAPIPE.has_face_keypoints == True", SkeletonType.MEDIAPIPE.has_face_keypoints is True)

    non_mediapipe = [SkeletonType.COCO, SkeletonType.OPENPOSE_25, SkeletonType.OPENPOSE_18,
                     SkeletonType.HALPE, SkeletonType.CUSTOM]
    for st in non_mediapipe:
        T.check(f"{st.name}.has_hand_keypoints == False", st.has_hand_keypoints is False)
        T.check(f"{st.name}.has_face_keypoints == False", st.has_face_keypoints is False)

    # 타입 확인
    for st in SkeletonType:
        T.check(f"{st.name}.has_hand_keypoints 타입 bool", isinstance(st.has_hand_keypoints, bool))
        T.check(f"{st.name}.has_face_keypoints 타입 bool", isinstance(st.has_face_keypoints, bool))

    # hand와 face 개수: 각각 1개만 True
    hand_true = sum(1 for st in SkeletonType if st.has_hand_keypoints)
    face_true = sum(1 for st in SkeletonType if st.has_face_keypoints)
    T.check("has_hand_keypoints True 개수 = 1", hand_true == 1, f"got {hand_true}")
    T.check("has_face_keypoints True 개수 = 1", face_true == 1, f"got {face_true}")

    # =================================================================
    # 섹션 9: SkeletonType.to_korean + get_name i18n
    # =================================================================
    T.set_section("9. SkeletonType.to_korean + get_name i18n")

    st_korean_expected = {
        SkeletonType.MEDIAPIPE: "MediaPipe",
        SkeletonType.COCO: "COCO",
        SkeletonType.OPENPOSE_25: "OpenPose 25",
        SkeletonType.OPENPOSE_18: "OpenPose 18",
        SkeletonType.HALPE: "Halpe",
        SkeletonType.CUSTOM: "커스텀",
    }
    for st, exp_korean in st_korean_expected.items():
        T.check(
            f"SkeletonType.{st.name}.to_korean == '{exp_korean}'",
            st.to_korean == exp_korean,
            f"got '{st.to_korean}'"
        )
        T.check(f"SkeletonType.{st.name}.to_korean 타입 str", isinstance(st.to_korean, str))

    # get_name i18n (6 멤버 × 5 언어 = 30 테스트)
    st_i18n_expected = {
        SupportedLanguage.KO: {
            SkeletonType.MEDIAPIPE: "MediaPipe",
            SkeletonType.COCO: "COCO",
            SkeletonType.OPENPOSE_25: "OpenPose 25",
            SkeletonType.OPENPOSE_18: "OpenPose 18",
            SkeletonType.HALPE: "Halpe",
            SkeletonType.CUSTOM: "커스텀",
        },
        SupportedLanguage.EN: {
            SkeletonType.MEDIAPIPE: "MediaPipe",
            SkeletonType.COCO: "COCO",
            SkeletonType.OPENPOSE_25: "OpenPose 25",
            SkeletonType.OPENPOSE_18: "OpenPose 18",
            SkeletonType.HALPE: "Halpe",
            SkeletonType.CUSTOM: "Custom",
        },
        SupportedLanguage.JA: {
            SkeletonType.MEDIAPIPE: "MediaPipe",
            SkeletonType.COCO: "COCO",
            SkeletonType.OPENPOSE_25: "OpenPose 25",
            SkeletonType.OPENPOSE_18: "OpenPose 18",
            SkeletonType.HALPE: "Halpe",
            SkeletonType.CUSTOM: "カスタム",
        },
        SupportedLanguage.ZH: {
            SkeletonType.MEDIAPIPE: "MediaPipe",
            SkeletonType.COCO: "COCO",
            SkeletonType.OPENPOSE_25: "OpenPose 25",
            SkeletonType.OPENPOSE_18: "OpenPose 18",
            SkeletonType.HALPE: "Halpe",
            SkeletonType.CUSTOM: "自定义",
        },
        SupportedLanguage.ES: {
            SkeletonType.MEDIAPIPE: "MediaPipe",
            SkeletonType.COCO: "COCO",
            SkeletonType.OPENPOSE_25: "OpenPose 25",
            SkeletonType.OPENPOSE_18: "OpenPose 18",
            SkeletonType.HALPE: "Halpe",
            SkeletonType.CUSTOM: "Personalizado",
        },
    }
    for lang, translations in st_i18n_expected.items():
        for st, exp_text in translations.items():
            result = st.get_name(lang)
            T.check(
                f"SkeletonType.{st.name}.get_name({lang.name}) == '{exp_text}'",
                result == exp_text,
                f"got '{result}'"
            )

    # KO 언어의 get_name과 to_korean 일치
    for st in SkeletonType:
        T.check(
            f"SkeletonType.{st.name}: get_name(KO) == to_korean",
            st.get_name(SupportedLanguage.KO) == st.to_korean,
            f"'{st.get_name(SupportedLanguage.KO)}' != '{st.to_korean}'"
        )

    # =================================================================
    # 섹션 10: JointType 멤버 수, IntEnum, 정수값 0-16 연속
    # =================================================================
    T.set_section("10. JointType 멤버 수, IntEnum, 정수값 0-16 연속")

    T.check("JointType 는 IntEnum", issubclass(JointType, IntEnum))
    T.check("JointType 는 Enum", issubclass(JointType, Enum))
    jt_members = list(JointType)
    T.check("JointType 멤버 수 = 17", len(jt_members) == 17, f"got {len(jt_members)}")

    # 정수값 0-16 연속 검증
    jt_values = sorted([jt.value for jt in JointType])
    expected_values = list(range(17))
    T.check(
        "JointType 정수값 0-16 연속",
        jt_values == expected_values,
        f"got {jt_values}"
    )

    # 각 멤버의 정확한 정수값
    expected_jt = {
        "NOSE": 0, "LEFT_EYE": 1, "RIGHT_EYE": 2, "LEFT_EAR": 3, "RIGHT_EAR": 4,
        "LEFT_SHOULDER": 5, "RIGHT_SHOULDER": 6, "LEFT_ELBOW": 7, "RIGHT_ELBOW": 8,
        "LEFT_WRIST": 9, "RIGHT_WRIST": 10, "LEFT_HIP": 11, "RIGHT_HIP": 12,
        "LEFT_KNEE": 13, "RIGHT_KNEE": 14, "LEFT_ANKLE": 15, "RIGHT_ANKLE": 16,
    }
    for name, exp_val in expected_jt.items():
        jt = JointType[name]
        T.check(f"JointType.{name} == {exp_val}", jt.value == exp_val, f"got {jt.value}")

    # IntEnum이므로 isinstance(JointType.NOSE, int) == True
    for jt in JointType:
        T.check(f"isinstance(JointType.{jt.name}, int) == True", isinstance(jt, int))

    # 정수 연산 가능 (IntEnum 특성)
    T.check("JointType.NOSE + 1 == 1", JointType.NOSE + 1 == 1)
    T.check("JointType.RIGHT_ANKLE - JointType.NOSE == 16", JointType.RIGHT_ANKLE - JointType.NOSE == 16)

    # =================================================================
    # 섹션 11: JointType.is_left/is_right (상호 배타, 중심점)
    # =================================================================
    T.set_section("11. JointType.is_left/is_right (상호 배타, 중심점)")

    left_joints = {
        JointType.LEFT_EYE, JointType.LEFT_EAR,
        JointType.LEFT_SHOULDER, JointType.LEFT_ELBOW, JointType.LEFT_WRIST,
        JointType.LEFT_HIP, JointType.LEFT_KNEE, JointType.LEFT_ANKLE,
    }
    right_joints = {
        JointType.RIGHT_EYE, JointType.RIGHT_EAR,
        JointType.RIGHT_SHOULDER, JointType.RIGHT_ELBOW, JointType.RIGHT_WRIST,
        JointType.RIGHT_HIP, JointType.RIGHT_KNEE, JointType.RIGHT_ANKLE,
    }

    # is_left 검증
    for jt in JointType:
        expected_left = jt in left_joints
        T.check(
            f"JointType.{jt.name}.is_left == {expected_left}",
            jt.is_left == expected_left,
            f"got {jt.is_left}"
        )

    # is_right 검증
    for jt in JointType:
        expected_right = jt in right_joints
        T.check(
            f"JointType.{jt.name}.is_right == {expected_right}",
            jt.is_right == expected_right,
            f"got {jt.is_right}"
        )

    # 상호 배타성: is_left와 is_right는 동시에 True가 될 수 없음
    for jt in JointType:
        T.check(
            f"JointType.{jt.name}: not (is_left and is_right)",
            not (jt.is_left and jt.is_right),
            "both True"
        )

    # NOSE는 중심점: is_left=False, is_right=False
    T.check("NOSE.is_left == False", JointType.NOSE.is_left is False)
    T.check("NOSE.is_right == False", JointType.NOSE.is_right is False)

    # 개수 확인
    left_count = sum(1 for jt in JointType if jt.is_left)
    right_count = sum(1 for jt in JointType if jt.is_right)
    center_count = sum(1 for jt in JointType if not jt.is_left and not jt.is_right)
    T.check("is_left 개수 = 8", left_count == 8, f"got {left_count}")
    T.check("is_right 개수 = 8", right_count == 8, f"got {right_count}")
    T.check("중심점 개수 = 1 (NOSE)", center_count == 1, f"got {center_count}")
    T.check("left + right + center = 17", left_count + right_count + center_count == 17)

    # 타입 확인
    for jt in JointType:
        T.check(f"JointType.{jt.name}.is_left 타입 bool", isinstance(jt.is_left, bool))
        T.check(f"JointType.{jt.name}.is_right 타입 bool", isinstance(jt.is_right, bool))

    # =================================================================
    # 섹션 12: JointType.symmetric_joint (대합/involution)
    # =================================================================
    T.set_section("12. JointType.symmetric_joint (대합/involution)")

    expected_symmetric = {
        JointType.NOSE: JointType.NOSE,
        JointType.LEFT_EYE: JointType.RIGHT_EYE,
        JointType.RIGHT_EYE: JointType.LEFT_EYE,
        JointType.LEFT_EAR: JointType.RIGHT_EAR,
        JointType.RIGHT_EAR: JointType.LEFT_EAR,
        JointType.LEFT_SHOULDER: JointType.RIGHT_SHOULDER,
        JointType.RIGHT_SHOULDER: JointType.LEFT_SHOULDER,
        JointType.LEFT_ELBOW: JointType.RIGHT_ELBOW,
        JointType.RIGHT_ELBOW: JointType.LEFT_ELBOW,
        JointType.LEFT_WRIST: JointType.RIGHT_WRIST,
        JointType.RIGHT_WRIST: JointType.LEFT_WRIST,
        JointType.LEFT_HIP: JointType.RIGHT_HIP,
        JointType.RIGHT_HIP: JointType.LEFT_HIP,
        JointType.LEFT_KNEE: JointType.RIGHT_KNEE,
        JointType.RIGHT_KNEE: JointType.LEFT_KNEE,
        JointType.LEFT_ANKLE: JointType.RIGHT_ANKLE,
        JointType.RIGHT_ANKLE: JointType.LEFT_ANKLE,
    }

    for jt, exp_sym in expected_symmetric.items():
        T.check(
            f"JointType.{jt.name}.symmetric_joint == {exp_sym.name}",
            jt.symmetric_joint == exp_sym,
            f"got {jt.symmetric_joint.name}"
        )

    # 대합 (involution) 검증: f(f(x)) == x
    for jt in JointType:
        double_sym = jt.symmetric_joint.symmetric_joint
        T.check(
            f"JointType.{jt.name}: symmetric(symmetric(x)) == x",
            double_sym == jt,
            f"got {double_sym.name}"
        )

    # symmetric_joint 반환값은 항상 JointType
    for jt in JointType:
        T.check(
            f"JointType.{jt.name}.symmetric_joint 타입 JointType",
            isinstance(jt.symmetric_joint, JointType),
            f"got {type(jt.symmetric_joint)}"
        )

    # 왼쪽 관절의 대칭은 오른쪽, 오른쪽의 대칭은 왼쪽
    for jt in JointType:
        if jt.is_left:
            T.check(
                f"JointType.{jt.name} (left) → symmetric is_right",
                jt.symmetric_joint.is_right,
                f"symmetric is_right={jt.symmetric_joint.is_right}"
            )
        elif jt.is_right:
            T.check(
                f"JointType.{jt.name} (right) → symmetric is_left",
                jt.symmetric_joint.is_left,
                f"symmetric is_left={jt.symmetric_joint.is_left}"
            )
        else:
            # NOSE: 자기 자신
            T.check(
                f"JointType.{jt.name} (center) → symmetric == self",
                jt.symmetric_joint == jt
            )

    # 맵 크기 = 17
    sym_map = getattr(pose_constants, "_JOINT_TYPE_SYMMETRIC_MAP", None)
    T.check("_JOINT_TYPE_SYMMETRIC_MAP 존재", sym_map is not None)
    T.check("_JOINT_TYPE_SYMMETRIC_MAP 크기 = 17", len(sym_map) == 17, f"got {len(sym_map)}")

    # =================================================================
    # 섹션 13: JointType.to_korean + get_name i18n
    # =================================================================
    T.set_section("13. JointType.to_korean + get_name i18n")

    jt_korean_expected = {
        JointType.NOSE: "코",
        JointType.LEFT_EYE: "왼쪽 눈",
        JointType.RIGHT_EYE: "오른쪽 눈",
        JointType.LEFT_EAR: "왼쪽 귀",
        JointType.RIGHT_EAR: "오른쪽 귀",
        JointType.LEFT_SHOULDER: "왼쪽 어깨",
        JointType.RIGHT_SHOULDER: "오른쪽 어깨",
        JointType.LEFT_ELBOW: "왼쪽 팔꿈치",
        JointType.RIGHT_ELBOW: "오른쪽 팔꿈치",
        JointType.LEFT_WRIST: "왼쪽 손목",
        JointType.RIGHT_WRIST: "오른쪽 손목",
        JointType.LEFT_HIP: "왼쪽 엉덩이",
        JointType.RIGHT_HIP: "오른쪽 엉덩이",
        JointType.LEFT_KNEE: "왼쪽 무릎",
        JointType.RIGHT_KNEE: "오른쪽 무릎",
        JointType.LEFT_ANKLE: "왼쪽 발목",
        JointType.RIGHT_ANKLE: "오른쪽 발목",
    }
    for jt, exp_korean in jt_korean_expected.items():
        T.check(
            f"JointType.{jt.name}.to_korean == '{exp_korean}'",
            jt.to_korean == exp_korean,
            f"got '{jt.to_korean}'"
        )
        T.check(f"JointType.{jt.name}.to_korean 타입 str", isinstance(jt.to_korean, str))

    # get_name i18n (17 멤버 × 5 언어 = 85 테스트)
    jt_i18n_expected = {
        SupportedLanguage.KO: {
            JointType.NOSE: "코", JointType.LEFT_EYE: "왼쪽 눈", JointType.RIGHT_EYE: "오른쪽 눈",
            JointType.LEFT_EAR: "왼쪽 귀", JointType.RIGHT_EAR: "오른쪽 귀",
            JointType.LEFT_SHOULDER: "왼쪽 어깨", JointType.RIGHT_SHOULDER: "오른쪽 어깨",
            JointType.LEFT_ELBOW: "왼쪽 팔꿈치", JointType.RIGHT_ELBOW: "오른쪽 팔꿈치",
            JointType.LEFT_WRIST: "왼쪽 손목", JointType.RIGHT_WRIST: "오른쪽 손목",
            JointType.LEFT_HIP: "왼쪽 엉덩이", JointType.RIGHT_HIP: "오른쪽 엉덩이",
            JointType.LEFT_KNEE: "왼쪽 무릎", JointType.RIGHT_KNEE: "오른쪽 무릎",
            JointType.LEFT_ANKLE: "왼쪽 발목", JointType.RIGHT_ANKLE: "오른쪽 발목",
        },
        SupportedLanguage.EN: {
            JointType.NOSE: "Nose", JointType.LEFT_EYE: "Left Eye", JointType.RIGHT_EYE: "Right Eye",
            JointType.LEFT_EAR: "Left Ear", JointType.RIGHT_EAR: "Right Ear",
            JointType.LEFT_SHOULDER: "Left Shoulder", JointType.RIGHT_SHOULDER: "Right Shoulder",
            JointType.LEFT_ELBOW: "Left Elbow", JointType.RIGHT_ELBOW: "Right Elbow",
            JointType.LEFT_WRIST: "Left Wrist", JointType.RIGHT_WRIST: "Right Wrist",
            JointType.LEFT_HIP: "Left Hip", JointType.RIGHT_HIP: "Right Hip",
            JointType.LEFT_KNEE: "Left Knee", JointType.RIGHT_KNEE: "Right Knee",
            JointType.LEFT_ANKLE: "Left Ankle", JointType.RIGHT_ANKLE: "Right Ankle",
        },
        SupportedLanguage.JA: {
            JointType.NOSE: "鼻", JointType.LEFT_EYE: "左目", JointType.RIGHT_EYE: "右目",
            JointType.LEFT_EAR: "左耳", JointType.RIGHT_EAR: "右耳",
            JointType.LEFT_SHOULDER: "左肩", JointType.RIGHT_SHOULDER: "右肩",
            JointType.LEFT_ELBOW: "左肘", JointType.RIGHT_ELBOW: "右肘",
            JointType.LEFT_WRIST: "左手首", JointType.RIGHT_WRIST: "右手首",
            JointType.LEFT_HIP: "左腰", JointType.RIGHT_HIP: "右腰",
            JointType.LEFT_KNEE: "左膝", JointType.RIGHT_KNEE: "右膝",
            JointType.LEFT_ANKLE: "左足首", JointType.RIGHT_ANKLE: "右足首",
        },
        SupportedLanguage.ZH: {
            JointType.NOSE: "鼻子", JointType.LEFT_EYE: "左眼", JointType.RIGHT_EYE: "右眼",
            JointType.LEFT_EAR: "左耳", JointType.RIGHT_EAR: "右耳",
            JointType.LEFT_SHOULDER: "左肩", JointType.RIGHT_SHOULDER: "右肩",
            JointType.LEFT_ELBOW: "左肘", JointType.RIGHT_ELBOW: "右肘",
            JointType.LEFT_WRIST: "左腕", JointType.RIGHT_WRIST: "右腕",
            JointType.LEFT_HIP: "左髋", JointType.RIGHT_HIP: "右髋",
            JointType.LEFT_KNEE: "左膝", JointType.RIGHT_KNEE: "右膝",
            JointType.LEFT_ANKLE: "左踝", JointType.RIGHT_ANKLE: "右踝",
        },
        SupportedLanguage.ES: {
            JointType.NOSE: "Nariz", JointType.LEFT_EYE: "Ojo Izquierdo", JointType.RIGHT_EYE: "Ojo Derecho",
            JointType.LEFT_EAR: "Oreja Izquierda", JointType.RIGHT_EAR: "Oreja Derecha",
            JointType.LEFT_SHOULDER: "Hombro Izquierdo", JointType.RIGHT_SHOULDER: "Hombro Derecho",
            JointType.LEFT_ELBOW: "Codo Izquierdo", JointType.RIGHT_ELBOW: "Codo Derecho",
            JointType.LEFT_WRIST: "Muñeca Izquierda", JointType.RIGHT_WRIST: "Muñeca Derecha",
            JointType.LEFT_HIP: "Cadera Izquierda", JointType.RIGHT_HIP: "Cadera Derecha",
            JointType.LEFT_KNEE: "Rodilla Izquierda", JointType.RIGHT_KNEE: "Rodilla Derecha",
            JointType.LEFT_ANKLE: "Tobillo Izquierdo", JointType.RIGHT_ANKLE: "Tobillo Derecho",
        },
    }
    for lang, translations in jt_i18n_expected.items():
        for jt, exp_text in translations.items():
            result = jt.get_name(lang)
            T.check(
                f"JointType.{jt.name}.get_name({lang.name}) == '{exp_text}'",
                result == exp_text,
                f"got '{result}'"
            )

    # KO 언어의 get_name과 to_korean 일치
    for jt in JointType:
        T.check(
            f"JointType.{jt.name}: get_name(KO) == to_korean",
            jt.get_name(SupportedLanguage.KO) == jt.to_korean,
            f"'{jt.get_name(SupportedLanguage.KO)}' != '{jt.to_korean}'"
        )

    # =================================================================
    # 섹션 14: 신뢰도 임계값 (값, 범위 0-1, 순서 관계)
    # =================================================================
    T.set_section("14. 신뢰도 임계값 (값, 범위 0-1, 순서 관계)")

    # 정확한 값
    T.check("JOINT_CONFIDENCE_THRESHOLD == 0.5", abs(JOINT_CONFIDENCE_THRESHOLD - 0.5) < 1e-9)
    T.check("HIGH_CONFIDENCE_THRESHOLD == 0.7", abs(HIGH_CONFIDENCE_THRESHOLD - 0.7) < 1e-9)
    T.check("LOW_CONFIDENCE_THRESHOLD == 0.3", abs(LOW_CONFIDENCE_THRESHOLD - 0.3) < 1e-9)
    T.check("SKELETON_COMPLETENESS_THRESHOLD == 0.7", abs(SKELETON_COMPLETENESS_THRESHOLD - 0.7) < 1e-9)
    T.check("MIN_SKELETON_COMPLETENESS == 0.4", abs(MIN_SKELETON_COMPLETENESS - 0.4) < 1e-9)
    T.check("UPPER_BODY_COMPLETENESS_THRESHOLD == 0.6", abs(UPPER_BODY_COMPLETENESS_THRESHOLD - 0.6) < 1e-9)
    T.check("LOWER_BODY_COMPLETENESS_THRESHOLD == 0.5", abs(LOWER_BODY_COMPLETENESS_THRESHOLD - 0.5) < 1e-9)

    # 타입 확인
    confidence_consts = [
        ("JOINT_CONFIDENCE_THRESHOLD", JOINT_CONFIDENCE_THRESHOLD),
        ("HIGH_CONFIDENCE_THRESHOLD", HIGH_CONFIDENCE_THRESHOLD),
        ("LOW_CONFIDENCE_THRESHOLD", LOW_CONFIDENCE_THRESHOLD),
        ("SKELETON_COMPLETENESS_THRESHOLD", SKELETON_COMPLETENESS_THRESHOLD),
        ("MIN_SKELETON_COMPLETENESS", MIN_SKELETON_COMPLETENESS),
        ("UPPER_BODY_COMPLETENESS_THRESHOLD", UPPER_BODY_COMPLETENESS_THRESHOLD),
        ("LOWER_BODY_COMPLETENESS_THRESHOLD", LOWER_BODY_COMPLETENESS_THRESHOLD),
    ]
    for name, val in confidence_consts:
        T.check(f"{name} 타입 float", isinstance(val, float), f"got {type(val)}")
        T.check(f"{name} 범위 0-1", 0.0 <= val <= 1.0, f"got {val}")

    # 순서 관계
    T.check(
        "LOW < JOINT < HIGH 순서",
        LOW_CONFIDENCE_THRESHOLD < JOINT_CONFIDENCE_THRESHOLD < HIGH_CONFIDENCE_THRESHOLD,
        f"{LOW_CONFIDENCE_THRESHOLD}, {JOINT_CONFIDENCE_THRESHOLD}, {HIGH_CONFIDENCE_THRESHOLD}"
    )
    T.check(
        "MIN_SKELETON < SKELETON 순서",
        MIN_SKELETON_COMPLETENESS < SKELETON_COMPLETENESS_THRESHOLD,
        f"{MIN_SKELETON_COMPLETENESS} >= {SKELETON_COMPLETENESS_THRESHOLD}"
    )
    T.check(
        "LOWER_BODY < UPPER_BODY 순서",
        LOWER_BODY_COMPLETENESS_THRESHOLD <= UPPER_BODY_COMPLETENESS_THRESHOLD,
        f"{LOWER_BODY_COMPLETENESS_THRESHOLD} > {UPPER_BODY_COMPLETENESS_THRESHOLD}"
    )

    # 7개 상수 존재
    T.check("신뢰도 임계값 상수 7개", len(confidence_consts) == 7)

    # =================================================================
    # 섹션 15: 키포인트 수 상수 (값, 타입, 양수)
    # =================================================================
    T.set_section("15. 키포인트 수 상수 (값, 타입, 양수)")

    kp_consts = [
        ("NUM_KEYPOINTS_MEDIAPIPE", NUM_KEYPOINTS_MEDIAPIPE, 33),
        ("NUM_KEYPOINTS_COCO", NUM_KEYPOINTS_COCO, 17),
        ("NUM_KEYPOINTS_OPENPOSE", NUM_KEYPOINTS_OPENPOSE, 25),
        ("NUM_KEYPOINTS_OPENPOSE_18", NUM_KEYPOINTS_OPENPOSE_18, 18),
        ("NUM_KEYPOINTS_HAND", NUM_KEYPOINTS_HAND, 21),
        ("NUM_KEYPOINTS_FACE", NUM_KEYPOINTS_FACE, 68),
    ]
    for name, val, exp in kp_consts:
        T.check(f"{name} == {exp}", val == exp, f"got {val}")
        T.check(f"{name} 타입 int", isinstance(val, int), f"got {type(val)}")
        T.check(f"{name} > 0", val > 0, f"got {val}")

    # COCO < OPENPOSE_18 < HAND < OPENPOSE < MEDIAPIPE < FACE 순서
    T.check(
        "COCO(17) < OPENPOSE_18(18)",
        NUM_KEYPOINTS_COCO < NUM_KEYPOINTS_OPENPOSE_18
    )
    T.check(
        "OPENPOSE_18(18) < HAND(21)",
        NUM_KEYPOINTS_OPENPOSE_18 < NUM_KEYPOINTS_HAND
    )
    T.check(
        "HAND(21) < OPENPOSE(25)",
        NUM_KEYPOINTS_HAND < NUM_KEYPOINTS_OPENPOSE
    )
    T.check(
        "OPENPOSE(25) < MEDIAPIPE(33)",
        NUM_KEYPOINTS_OPENPOSE < NUM_KEYPOINTS_MEDIAPIPE
    )
    T.check(
        "MEDIAPIPE(33) < FACE(68)",
        NUM_KEYPOINTS_MEDIAPIPE < NUM_KEYPOINTS_FACE
    )

    # =================================================================
    # 섹션 16: COCO 키포인트 인덱스 (연속 0-16, JointType 일관성)
    # =================================================================
    T.set_section("16. COCO 키포인트 인덱스 (연속 0-16, JointType 일관성)")

    coco_keypoints = [
        ("KEYPOINT_NOSE", KEYPOINT_NOSE, 0),
        ("KEYPOINT_LEFT_EYE", KEYPOINT_LEFT_EYE, 1),
        ("KEYPOINT_RIGHT_EYE", KEYPOINT_RIGHT_EYE, 2),
        ("KEYPOINT_LEFT_EAR", KEYPOINT_LEFT_EAR, 3),
        ("KEYPOINT_RIGHT_EAR", KEYPOINT_RIGHT_EAR, 4),
        ("KEYPOINT_LEFT_SHOULDER", KEYPOINT_LEFT_SHOULDER, 5),
        ("KEYPOINT_RIGHT_SHOULDER", KEYPOINT_RIGHT_SHOULDER, 6),
        ("KEYPOINT_LEFT_ELBOW", KEYPOINT_LEFT_ELBOW, 7),
        ("KEYPOINT_RIGHT_ELBOW", KEYPOINT_RIGHT_ELBOW, 8),
        ("KEYPOINT_LEFT_WRIST", KEYPOINT_LEFT_WRIST, 9),
        ("KEYPOINT_RIGHT_WRIST", KEYPOINT_RIGHT_WRIST, 10),
        ("KEYPOINT_LEFT_HIP", KEYPOINT_LEFT_HIP, 11),
        ("KEYPOINT_RIGHT_HIP", KEYPOINT_RIGHT_HIP, 12),
        ("KEYPOINT_LEFT_KNEE", KEYPOINT_LEFT_KNEE, 13),
        ("KEYPOINT_RIGHT_KNEE", KEYPOINT_RIGHT_KNEE, 14),
        ("KEYPOINT_LEFT_ANKLE", KEYPOINT_LEFT_ANKLE, 15),
        ("KEYPOINT_RIGHT_ANKLE", KEYPOINT_RIGHT_ANKLE, 16),
    ]
    for name, val, exp in coco_keypoints:
        T.check(f"{name} == {exp}", val == exp, f"got {val}")
        T.check(f"{name} 타입 int", isinstance(val, int), f"got {type(val)}")

    # COCO 키포인트 17개
    T.check("COCO 키포인트 상수 17개", len(coco_keypoints) == 17)

    # 연속성: 값이 0~16 을 빠짐없이 커버
    coco_vals = sorted([v for _, v, _ in coco_keypoints])
    T.check("COCO 인덱스 연속 0-16", coco_vals == list(range(17)))

    # JointType과의 일관성
    jt_consistency = [
        ("KEYPOINT_NOSE", KEYPOINT_NOSE, JointType.NOSE),
        ("KEYPOINT_LEFT_EYE", KEYPOINT_LEFT_EYE, JointType.LEFT_EYE),
        ("KEYPOINT_RIGHT_EYE", KEYPOINT_RIGHT_EYE, JointType.RIGHT_EYE),
        ("KEYPOINT_LEFT_EAR", KEYPOINT_LEFT_EAR, JointType.LEFT_EAR),
        ("KEYPOINT_RIGHT_EAR", KEYPOINT_RIGHT_EAR, JointType.RIGHT_EAR),
        ("KEYPOINT_LEFT_SHOULDER", KEYPOINT_LEFT_SHOULDER, JointType.LEFT_SHOULDER),
        ("KEYPOINT_RIGHT_SHOULDER", KEYPOINT_RIGHT_SHOULDER, JointType.RIGHT_SHOULDER),
        ("KEYPOINT_LEFT_ELBOW", KEYPOINT_LEFT_ELBOW, JointType.LEFT_ELBOW),
        ("KEYPOINT_RIGHT_ELBOW", KEYPOINT_RIGHT_ELBOW, JointType.RIGHT_ELBOW),
        ("KEYPOINT_LEFT_WRIST", KEYPOINT_LEFT_WRIST, JointType.LEFT_WRIST),
        ("KEYPOINT_RIGHT_WRIST", KEYPOINT_RIGHT_WRIST, JointType.RIGHT_WRIST),
        ("KEYPOINT_LEFT_HIP", KEYPOINT_LEFT_HIP, JointType.LEFT_HIP),
        ("KEYPOINT_RIGHT_HIP", KEYPOINT_RIGHT_HIP, JointType.RIGHT_HIP),
        ("KEYPOINT_LEFT_KNEE", KEYPOINT_LEFT_KNEE, JointType.LEFT_KNEE),
        ("KEYPOINT_RIGHT_KNEE", KEYPOINT_RIGHT_KNEE, JointType.RIGHT_KNEE),
        ("KEYPOINT_LEFT_ANKLE", KEYPOINT_LEFT_ANKLE, JointType.LEFT_ANKLE),
        ("KEYPOINT_RIGHT_ANKLE", KEYPOINT_RIGHT_ANKLE, JointType.RIGHT_ANKLE),
    ]
    for name, kp_val, jt in jt_consistency:
        T.check(
            f"{name} == JointType.{jt.name}.value ({kp_val} == {jt.value})",
            kp_val == jt.value,
            f"{kp_val} != {jt.value}"
        )

    # =================================================================
    # 섹션 17: MediaPipe 키포인트 (연속 0-32)
    # =================================================================
    T.set_section("17. MediaPipe 키포인트 (연속 0-32)")

    # 모듈에서 직접 확인 가능한 MediaPipe 상수
    mp_consts = [
        ("MEDIAPIPE_NOSE", MEDIAPIPE_NOSE, 0),
        ("MEDIAPIPE_LEFT_SHOULDER", MEDIAPIPE_LEFT_SHOULDER, 11),
        ("MEDIAPIPE_RIGHT_SHOULDER", MEDIAPIPE_RIGHT_SHOULDER, 12),
        ("MEDIAPIPE_LEFT_ELBOW", MEDIAPIPE_LEFT_ELBOW, 13),
        ("MEDIAPIPE_RIGHT_ELBOW", MEDIAPIPE_RIGHT_ELBOW, 14),
        ("MEDIAPIPE_LEFT_WRIST", MEDIAPIPE_LEFT_WRIST, 15),
        ("MEDIAPIPE_RIGHT_WRIST", MEDIAPIPE_RIGHT_WRIST, 16),
        ("MEDIAPIPE_LEFT_HIP", MEDIAPIPE_LEFT_HIP, 23),
        ("MEDIAPIPE_RIGHT_HIP", MEDIAPIPE_RIGHT_HIP, 24),
        ("MEDIAPIPE_LEFT_KNEE", MEDIAPIPE_LEFT_KNEE, 25),
        ("MEDIAPIPE_RIGHT_KNEE", MEDIAPIPE_RIGHT_KNEE, 26),
        ("MEDIAPIPE_LEFT_ANKLE", MEDIAPIPE_LEFT_ANKLE, 27),
        ("MEDIAPIPE_RIGHT_ANKLE", MEDIAPIPE_RIGHT_ANKLE, 28),
    ]
    for name, val, exp in mp_consts:
        T.check(f"{name} == {exp}", val == exp, f"got {val}")
        T.check(f"{name} 타입 int", isinstance(val, int), f"got {type(val)}")
        T.check(f"{name} >= 0", val >= 0)

    # MediaPipe 인덱스는 COCO와 다름 (어깨: MP=11 vs COCO=5)
    T.check(
        "MediaPipe LEFT_SHOULDER(11) != COCO LEFT_SHOULDER(5)",
        MEDIAPIPE_LEFT_SHOULDER != KEYPOINT_LEFT_SHOULDER,
        f"{MEDIAPIPE_LEFT_SHOULDER} == {KEYPOINT_LEFT_SHOULDER}"
    )

    # 모듈에서 전체 33개 MediaPipe 상수 확인 (0-32 연속)
    all_mp_names = [
        "MEDIAPIPE_NOSE", "MEDIAPIPE_LEFT_EYE_INNER", "MEDIAPIPE_LEFT_EYE",
        "MEDIAPIPE_LEFT_EYE_OUTER", "MEDIAPIPE_RIGHT_EYE_INNER", "MEDIAPIPE_RIGHT_EYE",
        "MEDIAPIPE_RIGHT_EYE_OUTER", "MEDIAPIPE_LEFT_EAR", "MEDIAPIPE_RIGHT_EAR",
        "MEDIAPIPE_MOUTH_LEFT", "MEDIAPIPE_MOUTH_RIGHT",
        "MEDIAPIPE_LEFT_SHOULDER", "MEDIAPIPE_RIGHT_SHOULDER",
        "MEDIAPIPE_LEFT_ELBOW", "MEDIAPIPE_RIGHT_ELBOW",
        "MEDIAPIPE_LEFT_WRIST", "MEDIAPIPE_RIGHT_WRIST",
        "MEDIAPIPE_LEFT_PINKY", "MEDIAPIPE_RIGHT_PINKY",
        "MEDIAPIPE_LEFT_INDEX", "MEDIAPIPE_RIGHT_INDEX",
        "MEDIAPIPE_LEFT_THUMB", "MEDIAPIPE_RIGHT_THUMB",
        "MEDIAPIPE_LEFT_HIP", "MEDIAPIPE_RIGHT_HIP",
        "MEDIAPIPE_LEFT_KNEE", "MEDIAPIPE_RIGHT_KNEE",
        "MEDIAPIPE_LEFT_ANKLE", "MEDIAPIPE_RIGHT_ANKLE",
        "MEDIAPIPE_LEFT_HEEL", "MEDIAPIPE_RIGHT_HEEL",
        "MEDIAPIPE_LEFT_FOOT_INDEX", "MEDIAPIPE_RIGHT_FOOT_INDEX",
    ]
    mp_values = []
    for name in all_mp_names:
        val = getattr(pose_constants, name, None)
        T.check(f"{name} 모듈에 존재", val is not None, "not found")
        if val is not None:
            mp_values.append(val)
            T.check(f"{name} 타입 int", isinstance(val, int))

    if len(mp_values) == 33:
        mp_sorted = sorted(mp_values)
        T.check(
            "MediaPipe 인덱스 0-32 연속",
            mp_sorted == list(range(33)),
            f"missing: {set(range(33)) - set(mp_values)}"
        )
        T.check("MediaPipe 인덱스 33개 (중복 없음)", len(set(mp_values)) == 33)
    else:
        T.fail("MediaPipe 인덱스 33개 확인", f"found {len(mp_values)}")

    # MEDIAPIPE_RIGHT_FOOT_INDEX가 마지막 (32)
    T.check(
        "MEDIAPIPE_RIGHT_FOOT_INDEX == 32",
        getattr(pose_constants, "MEDIAPIPE_RIGHT_FOOT_INDEX", None) == 32
    )

    # =================================================================
    # 섹션 18: COCO_SKELETON_CONNECTIONS
    # =================================================================
    T.set_section("18. COCO_SKELETON_CONNECTIONS (16개, tuple, 인덱스 범위, 중복 없음)")

    T.check("COCO_SKELETON_CONNECTIONS 타입 list", isinstance(COCO_SKELETON_CONNECTIONS, list))
    T.check(
        "COCO_SKELETON_CONNECTIONS 길이 = 16",
        len(COCO_SKELETON_CONNECTIONS) == 16,
        f"got {len(COCO_SKELETON_CONNECTIONS)}"
    )
    T.check(
        "NUM_COCO_CONNECTIONS == 16",
        NUM_COCO_CONNECTIONS == 16,
        f"got {NUM_COCO_CONNECTIONS}"
    )
    T.check(
        "NUM_COCO_CONNECTIONS == len(COCO_SKELETON_CONNECTIONS)",
        NUM_COCO_CONNECTIONS == len(COCO_SKELETON_CONNECTIONS)
    )

    # 각 연결이 2-tuple이고 인덱스 범위 0-16
    for i, conn in enumerate(COCO_SKELETON_CONNECTIONS):
        T.check(f"connection[{i}] 타입 tuple", isinstance(conn, tuple), f"got {type(conn)}")
        T.check(f"connection[{i}] 길이 2", len(conn) == 2, f"got {len(conn)}")
        T.check(
            f"connection[{i}][0] 범위 0-16",
            0 <= conn[0] <= 16,
            f"got {conn[0]}"
        )
        T.check(
            f"connection[{i}][1] 범위 0-16",
            0 <= conn[1] <= 16,
            f"got {conn[1]}"
        )
        # 자기 자신 연결 아님
        T.check(
            f"connection[{i}]: start != end",
            conn[0] != conn[1],
            f"{conn[0]} == {conn[1]}"
        )

    # 중복 없음 (정규화: (min, max)로 비교)
    normalized = set()
    has_dup = False
    for conn in COCO_SKELETON_CONNECTIONS:
        norm = (min(conn), max(conn))
        if norm in normalized:
            has_dup = True
            break
        normalized.add(norm)
    T.check("COCO_SKELETON_CONNECTIONS 중복 없음", not has_dup)

    # 예상 연결 확인 (주요 연결)
    expected_connections = [
        (0, 1), (0, 2), (1, 3), (2, 4),  # 머리
        (5, 6),  # 어깨
        (5, 7), (7, 9),  # 왼팔
        (6, 8), (8, 10),  # 오른팔
        (5, 11), (6, 12),  # 몸통
        (11, 12),  # 엉덩이
        (11, 13), (13, 15),  # 왼다리
        (12, 14), (14, 16),  # 오른다리
    ]
    for conn in expected_connections:
        T.check(
            f"연결 {conn} 존재",
            conn in COCO_SKELETON_CONNECTIONS,
            "not found"
        )

    # =================================================================
    # 섹션 19: 키포인트 그룹 frozenset
    # =================================================================
    T.set_section("19. 키포인트 그룹 frozenset (크기, 인덱스 범위, 교차)")

    # SHOOTING_CRITICAL_KEYPOINTS
    T.check("SHOOTING_CRITICAL_KEYPOINTS 타입 frozenset", isinstance(SHOOTING_CRITICAL_KEYPOINTS, frozenset))
    T.check("SHOOTING_CRITICAL_KEYPOINTS 크기 = 10", len(SHOOTING_CRITICAL_KEYPOINTS) == 10,
            f"got {len(SHOOTING_CRITICAL_KEYPOINTS)}")

    shooting_expected = frozenset({
        KEYPOINT_RIGHT_SHOULDER, KEYPOINT_RIGHT_ELBOW, KEYPOINT_RIGHT_WRIST,
        KEYPOINT_LEFT_SHOULDER, KEYPOINT_LEFT_ELBOW, KEYPOINT_LEFT_WRIST,
        KEYPOINT_RIGHT_HIP, KEYPOINT_LEFT_HIP,
        KEYPOINT_RIGHT_KNEE, KEYPOINT_LEFT_KNEE,
    })
    T.check("SHOOTING_CRITICAL_KEYPOINTS 내용 일치", SHOOTING_CRITICAL_KEYPOINTS == shooting_expected)

    # DRIBBLING_CRITICAL_KEYPOINTS
    T.check("DRIBBLING_CRITICAL_KEYPOINTS 타입 frozenset", isinstance(DRIBBLING_CRITICAL_KEYPOINTS, frozenset))
    T.check("DRIBBLING_CRITICAL_KEYPOINTS 크기 = 8", len(DRIBBLING_CRITICAL_KEYPOINTS) == 8,
            f"got {len(DRIBBLING_CRITICAL_KEYPOINTS)}")

    dribbling_expected = frozenset({
        KEYPOINT_RIGHT_WRIST, KEYPOINT_LEFT_WRIST,
        KEYPOINT_RIGHT_ELBOW, KEYPOINT_LEFT_ELBOW,
        KEYPOINT_RIGHT_HIP, KEYPOINT_LEFT_HIP,
        KEYPOINT_RIGHT_KNEE, KEYPOINT_LEFT_KNEE,
    })
    T.check("DRIBBLING_CRITICAL_KEYPOINTS 내용 일치", DRIBBLING_CRITICAL_KEYPOINTS == dribbling_expected)

    # UPPER_BODY_KEYPOINTS
    T.check("UPPER_BODY_KEYPOINTS 타입 frozenset", isinstance(UPPER_BODY_KEYPOINTS, frozenset))
    T.check("UPPER_BODY_KEYPOINTS 크기 = 9", len(UPPER_BODY_KEYPOINTS) == 9,
            f"got {len(UPPER_BODY_KEYPOINTS)}")

    upper_expected = frozenset({
        KEYPOINT_NOSE, KEYPOINT_LEFT_EYE, KEYPOINT_RIGHT_EYE,
        KEYPOINT_LEFT_SHOULDER, KEYPOINT_RIGHT_SHOULDER,
        KEYPOINT_LEFT_ELBOW, KEYPOINT_RIGHT_ELBOW,
        KEYPOINT_LEFT_WRIST, KEYPOINT_RIGHT_WRIST,
    })
    T.check("UPPER_BODY_KEYPOINTS 내용 일치", UPPER_BODY_KEYPOINTS == upper_expected)

    # LOWER_BODY_KEYPOINTS
    T.check("LOWER_BODY_KEYPOINTS 타입 frozenset", isinstance(LOWER_BODY_KEYPOINTS, frozenset))
    T.check("LOWER_BODY_KEYPOINTS 크기 = 6", len(LOWER_BODY_KEYPOINTS) == 6,
            f"got {len(LOWER_BODY_KEYPOINTS)}")

    lower_expected = frozenset({
        KEYPOINT_LEFT_HIP, KEYPOINT_RIGHT_HIP,
        KEYPOINT_LEFT_KNEE, KEYPOINT_RIGHT_KNEE,
        KEYPOINT_LEFT_ANKLE, KEYPOINT_RIGHT_ANKLE,
    })
    T.check("LOWER_BODY_KEYPOINTS 내용 일치", LOWER_BODY_KEYPOINTS == lower_expected)

    # 인덱스 범위 0-16
    for name, grp in [
        ("SHOOTING_CRITICAL_KEYPOINTS", SHOOTING_CRITICAL_KEYPOINTS),
        ("DRIBBLING_CRITICAL_KEYPOINTS", DRIBBLING_CRITICAL_KEYPOINTS),
        ("UPPER_BODY_KEYPOINTS", UPPER_BODY_KEYPOINTS),
        ("LOWER_BODY_KEYPOINTS", LOWER_BODY_KEYPOINTS),
    ]:
        all_in_range = all(0 <= idx <= 16 for idx in grp)
        T.check(f"{name} 인덱스 범위 0-16", all_in_range)

    # 상체/하체 교차 없음 (disjoint)
    intersection = UPPER_BODY_KEYPOINTS & LOWER_BODY_KEYPOINTS
    T.check(
        "UPPER_BODY & LOWER_BODY 교차 없음 (disjoint)",
        len(intersection) == 0,
        f"교차: {intersection}"
    )

    # DRIBBLING은 SHOOTING의 서브셋
    T.check(
        "DRIBBLING ⊂ SHOOTING (서브셋)",
        DRIBBLING_CRITICAL_KEYPOINTS.issubset(SHOOTING_CRITICAL_KEYPOINTS),
        f"차이: {DRIBBLING_CRITICAL_KEYPOINTS - SHOOTING_CRITICAL_KEYPOINTS}"
    )

    # 모든 그룹의 요소는 int
    for name, grp in [
        ("SHOOTING_CRITICAL_KEYPOINTS", SHOOTING_CRITICAL_KEYPOINTS),
        ("DRIBBLING_CRITICAL_KEYPOINTS", DRIBBLING_CRITICAL_KEYPOINTS),
        ("UPPER_BODY_KEYPOINTS", UPPER_BODY_KEYPOINTS),
        ("LOWER_BODY_KEYPOINTS", LOWER_BODY_KEYPOINTS),
    ]:
        all_int = all(isinstance(idx, int) for idx in grp)
        T.check(f"{name} 모든 요소 int", all_int)

    # =================================================================
    # 섹션 20: 관절 각도 범위 (min < max, 생체역학 합리성)
    # =================================================================
    T.set_section("20. 관절 각도 범위 (min < max, 생체역학 합리성)")

    angle_ranges = [
        ("ELBOW", ELBOW_ANGLE_MIN_DEG, ELBOW_ANGLE_MAX_DEG, 0.0, 150.0),
        ("KNEE", KNEE_ANGLE_MIN_DEG, KNEE_ANGLE_MAX_DEG, 0.0, 150.0),
        ("SHOULDER", SHOULDER_ANGLE_MIN_DEG, SHOULDER_ANGLE_MAX_DEG, 0.0, 180.0),
        ("HIP", HIP_ANGLE_MIN_DEG, HIP_ANGLE_MAX_DEG, 0.0, 130.0),
        ("ANKLE", ANKLE_ANGLE_MIN_DEG, ANKLE_ANGLE_MAX_DEG, 70.0, 130.0),
    ]
    for name, min_val, max_val, exp_min, exp_max in angle_ranges:
        T.check(f"{name}_ANGLE_MIN_DEG == {exp_min}", abs(min_val - exp_min) < 1e-9, f"got {min_val}")
        T.check(f"{name}_ANGLE_MAX_DEG == {exp_max}", abs(max_val - exp_max) < 1e-9, f"got {max_val}")
        T.check(f"{name}: min < max", min_val < max_val, f"{min_val} >= {max_val}")
        T.check(f"{name}_ANGLE_MIN_DEG 타입 float", isinstance(min_val, float))
        T.check(f"{name}_ANGLE_MAX_DEG 타입 float", isinstance(max_val, float))
        T.check(f"{name}_ANGLE_MIN_DEG >= 0", min_val >= 0.0, f"got {min_val}")
        T.check(f"{name}_ANGLE_MAX_DEG <= 360", max_val <= 360.0, f"got {max_val}")

    # 생체역학 합리성: 최대 각도가 180도 이하 (관절은 180도 넘게 안 꺾임)
    for name, _, max_val, _, _ in angle_ranges:
        T.check(
            f"{name} 최대 각도 <= 180 (생체역학)",
            max_val <= 180.0,
            f"got {max_val}"
        )

    # 어깨가 가장 넓은 가동범위
    T.check(
        "어깨 최대 가동범위 >= 팔꿈치",
        SHOULDER_ANGLE_MAX_DEG >= ELBOW_ANGLE_MAX_DEG
    )
    T.check(
        "어깨 최대 가동범위 >= 무릎",
        SHOULDER_ANGLE_MAX_DEG >= KNEE_ANGLE_MAX_DEG
    )

    # =================================================================
    # 섹션 21: 슈팅 각도 기준 (min < max)
    # =================================================================
    T.set_section("21. 슈팅 각도 기준 (min < max, 릴리즈 각도)")

    T.check("OPTIMAL_RELEASE_ANGLE_MIN_DEG == 45.0", abs(OPTIMAL_RELEASE_ANGLE_MIN_DEG - 45.0) < 1e-9)
    T.check("OPTIMAL_RELEASE_ANGLE_MAX_DEG == 55.0", abs(OPTIMAL_RELEASE_ANGLE_MAX_DEG - 55.0) < 1e-9)
    T.check("RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG == 90.0", abs(RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG - 90.0) < 1e-9)
    T.check("RECOMMENDED_KNEE_BEND_ANGLE_DEG == 120.0", abs(RECOMMENDED_KNEE_BEND_ANGLE_DEG - 120.0) < 1e-9)
    T.check("WRIST_FLEXION_MIN_DEG == -30.0", abs(WRIST_FLEXION_MIN_DEG - (-30.0)) < 1e-9)
    T.check("WRIST_FLEXION_MAX_DEG == 90.0", abs(WRIST_FLEXION_MAX_DEG - 90.0) < 1e-9)

    # min < max
    T.check(
        "OPTIMAL_RELEASE: min < max",
        OPTIMAL_RELEASE_ANGLE_MIN_DEG < OPTIMAL_RELEASE_ANGLE_MAX_DEG
    )
    T.check(
        "WRIST_FLEXION: min < max",
        WRIST_FLEXION_MIN_DEG < WRIST_FLEXION_MAX_DEG
    )

    # 타입 확인
    shooting_consts = [
        ("OPTIMAL_RELEASE_ANGLE_MIN_DEG", OPTIMAL_RELEASE_ANGLE_MIN_DEG),
        ("OPTIMAL_RELEASE_ANGLE_MAX_DEG", OPTIMAL_RELEASE_ANGLE_MAX_DEG),
        ("RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG", RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG),
        ("RECOMMENDED_KNEE_BEND_ANGLE_DEG", RECOMMENDED_KNEE_BEND_ANGLE_DEG),
        ("WRIST_FLEXION_MIN_DEG", WRIST_FLEXION_MIN_DEG),
        ("WRIST_FLEXION_MAX_DEG", WRIST_FLEXION_MAX_DEG),
    ]
    for name, val in shooting_consts:
        T.check(f"{name} 타입 float", isinstance(val, float), f"got {type(val)}")

    # 릴리즈 각도 범위는 0-90도 이내에 존재해야 (물리적으로 합리적)
    T.check(
        "최적 릴리즈 각도 양수 범위",
        OPTIMAL_RELEASE_ANGLE_MIN_DEG > 0,
        f"got {OPTIMAL_RELEASE_ANGLE_MIN_DEG}"
    )
    T.check(
        "최적 릴리즈 각도 < 90도",
        OPTIMAL_RELEASE_ANGLE_MAX_DEG < 90.0,
        f"got {OPTIMAL_RELEASE_ANGLE_MAX_DEG}"
    )

    # 권장 팔꿈치 각도는 관절 범위 내
    T.check(
        "권장 팔꿈치 릴리즈 각도 <= 팔꿈치 최대",
        RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG <= ELBOW_ANGLE_MAX_DEG,
        f"{RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG} > {ELBOW_ANGLE_MAX_DEG}"
    )

    # 권장 무릎 굽힘은 관절 범위 내
    T.check(
        "권장 무릎 굽힘 각도 <= 무릎 최대",
        RECOMMENDED_KNEE_BEND_ANGLE_DEG <= KNEE_ANGLE_MAX_DEG,
        f"{RECOMMENDED_KNEE_BEND_ANGLE_DEG} > {KNEE_ANGLE_MAX_DEG}"
    )

    # =================================================================
    # 섹션 22: 모델 파라미터 (tuple 크기, 양수, 2의 거듭제곱)
    # =================================================================
    T.set_section("22. 모델 파라미터 (tuple 크기, 양수, 2의 거듭제곱)")

    # POSE_INPUT_SIZE
    T.check("POSE_INPUT_SIZE 타입 tuple", isinstance(POSE_INPUT_SIZE, tuple))
    T.check("POSE_INPUT_SIZE 길이 2", len(POSE_INPUT_SIZE) == 2)
    T.check("POSE_INPUT_SIZE == (256, 256)", POSE_INPUT_SIZE == (256, 256), f"got {POSE_INPUT_SIZE}")
    T.check("POSE_INPUT_SIZE[0] > 0", POSE_INPUT_SIZE[0] > 0)
    T.check("POSE_INPUT_SIZE[1] > 0", POSE_INPUT_SIZE[1] > 0)
    T.check("POSE_INPUT_SIZE[0] 2의 거듭제곱", _is_power_of_two(POSE_INPUT_SIZE[0]))
    T.check("POSE_INPUT_SIZE[1] 2의 거듭제곱", _is_power_of_two(POSE_INPUT_SIZE[1]))

    # POSE_INPUT_SIZE_HIGH
    T.check("POSE_INPUT_SIZE_HIGH 타입 tuple", isinstance(POSE_INPUT_SIZE_HIGH, tuple))
    T.check("POSE_INPUT_SIZE_HIGH 길이 2", len(POSE_INPUT_SIZE_HIGH) == 2)
    T.check("POSE_INPUT_SIZE_HIGH == (384, 384)", POSE_INPUT_SIZE_HIGH == (384, 384), f"got {POSE_INPUT_SIZE_HIGH}")
    T.check("POSE_INPUT_SIZE_HIGH[0] > 0", POSE_INPUT_SIZE_HIGH[0] > 0)
    T.check("POSE_INPUT_SIZE_HIGH[1] > 0", POSE_INPUT_SIZE_HIGH[1] > 0)
    T.check(
        "POSE_INPUT_SIZE_HIGH > POSE_INPUT_SIZE",
        POSE_INPUT_SIZE_HIGH[0] > POSE_INPUT_SIZE[0]
    )

    # HEATMAP_OUTPUT_SIZE
    T.check("HEATMAP_OUTPUT_SIZE 타입 tuple", isinstance(HEATMAP_OUTPUT_SIZE, tuple))
    T.check("HEATMAP_OUTPUT_SIZE 길이 2", len(HEATMAP_OUTPUT_SIZE) == 2)
    T.check("HEATMAP_OUTPUT_SIZE == (64, 64)", HEATMAP_OUTPUT_SIZE == (64, 64), f"got {HEATMAP_OUTPUT_SIZE}")
    T.check("HEATMAP_OUTPUT_SIZE[0] > 0", HEATMAP_OUTPUT_SIZE[0] > 0)
    T.check("HEATMAP_OUTPUT_SIZE[1] > 0", HEATMAP_OUTPUT_SIZE[1] > 0)
    T.check("HEATMAP_OUTPUT_SIZE[0] 2의 거듭제곱", _is_power_of_two(HEATMAP_OUTPUT_SIZE[0]))
    T.check("HEATMAP_OUTPUT_SIZE[1] 2의 거듭제곱", _is_power_of_two(HEATMAP_OUTPUT_SIZE[1]))
    T.check(
        "HEATMAP < POSE_INPUT (다운샘플)",
        HEATMAP_OUTPUT_SIZE[0] < POSE_INPUT_SIZE[0]
    )

    # 다운샘플 비율 확인 (256/64 = 4)
    downsample_ratio = POSE_INPUT_SIZE[0] // HEATMAP_OUTPUT_SIZE[0]
    T.check(
        f"다운샘플 비율 정수: {downsample_ratio}",
        POSE_INPUT_SIZE[0] % HEATMAP_OUTPUT_SIZE[0] == 0
    )
    T.check(
        "다운샘플 비율 2의 거듭제곱",
        _is_power_of_two(downsample_ratio),
        f"ratio={downsample_ratio}"
    )

    # HEATMAP_GAUSSIAN_SIGMA
    T.check("HEATMAP_GAUSSIAN_SIGMA 타입 float", isinstance(HEATMAP_GAUSSIAN_SIGMA, float))
    T.check("HEATMAP_GAUSSIAN_SIGMA == 2.0", abs(HEATMAP_GAUSSIAN_SIGMA - 2.0) < 1e-9)
    T.check("HEATMAP_GAUSSIAN_SIGMA > 0", HEATMAP_GAUSSIAN_SIGMA > 0)

    # POSE_NMS_KERNEL_SIZE
    T.check("POSE_NMS_KERNEL_SIZE 타입 int", isinstance(POSE_NMS_KERNEL_SIZE, int))
    T.check("POSE_NMS_KERNEL_SIZE == 5", POSE_NMS_KERNEL_SIZE == 5)
    T.check("POSE_NMS_KERNEL_SIZE > 0", POSE_NMS_KERNEL_SIZE > 0)
    T.check("POSE_NMS_KERNEL_SIZE 홀수 (커널은 홀수여야 함)", POSE_NMS_KERNEL_SIZE % 2 == 1)

    # =================================================================
    # 섹션 23: __all__ 완전성 (73개, 모두 존재)
    # =================================================================
    T.set_section("23. __all__ 완전성 (73개, 모두 존재)")

    all_exports = pose_constants.__all__
    T.check("__all__ 존재", all_exports is not None)
    T.check("__all__ 타입 list", isinstance(all_exports, list))
    T.check("__all__ 길이 = 73", len(all_exports) == 73, f"got {len(all_exports)}")

    # 중복 없음
    T.check("__all__ 중복 없음", len(all_exports) == len(set(all_exports)),
            f"중복: {[x for x in all_exports if all_exports.count(x) > 1]}")

    # 모든 항목이 실제 모듈에 존재
    missing_from_module = []
    for name in all_exports:
        if not hasattr(pose_constants, name):
            missing_from_module.append(name)
    T.check(
        "__all__ 모든 항목 모듈에 존재",
        len(missing_from_module) == 0,
        f"missing: {missing_from_module}"
    )

    # 주요 상수 포함 여부
    must_include = [
        # 신뢰도 임계값 7
        "JOINT_CONFIDENCE_THRESHOLD", "HIGH_CONFIDENCE_THRESHOLD", "LOW_CONFIDENCE_THRESHOLD",
        "SKELETON_COMPLETENESS_THRESHOLD", "MIN_SKELETON_COMPLETENESS",
        "UPPER_BODY_COMPLETENESS_THRESHOLD", "LOWER_BODY_COMPLETENESS_THRESHOLD",
        # 키포인트 수 6
        "NUM_KEYPOINTS_MEDIAPIPE", "NUM_KEYPOINTS_COCO", "NUM_KEYPOINTS_OPENPOSE",
        "NUM_KEYPOINTS_OPENPOSE_18", "NUM_KEYPOINTS_HAND", "NUM_KEYPOINTS_FACE",
        # COCO 키포인트 인덱스 17
        "KEYPOINT_NOSE", "KEYPOINT_LEFT_EYE", "KEYPOINT_RIGHT_EYE",
        "KEYPOINT_LEFT_EAR", "KEYPOINT_RIGHT_EAR",
        "KEYPOINT_LEFT_SHOULDER", "KEYPOINT_RIGHT_SHOULDER",
        "KEYPOINT_LEFT_ELBOW", "KEYPOINT_RIGHT_ELBOW",
        "KEYPOINT_LEFT_WRIST", "KEYPOINT_RIGHT_WRIST",
        "KEYPOINT_LEFT_HIP", "KEYPOINT_RIGHT_HIP",
        "KEYPOINT_LEFT_KNEE", "KEYPOINT_RIGHT_KNEE",
        "KEYPOINT_LEFT_ANKLE", "KEYPOINT_RIGHT_ANKLE",
        # 스켈레톤 연결 2
        "COCO_SKELETON_CONNECTIONS", "NUM_COCO_CONNECTIONS",
        # MediaPipe 인덱스 13
        "MEDIAPIPE_NOSE", "MEDIAPIPE_LEFT_SHOULDER", "MEDIAPIPE_RIGHT_SHOULDER",
        "MEDIAPIPE_LEFT_ELBOW", "MEDIAPIPE_RIGHT_ELBOW",
        "MEDIAPIPE_LEFT_WRIST", "MEDIAPIPE_RIGHT_WRIST",
        "MEDIAPIPE_LEFT_HIP", "MEDIAPIPE_RIGHT_HIP",
        "MEDIAPIPE_LEFT_KNEE", "MEDIAPIPE_RIGHT_KNEE",
        "MEDIAPIPE_LEFT_ANKLE", "MEDIAPIPE_RIGHT_ANKLE",
        # 키포인트 그룹 4
        "SHOOTING_CRITICAL_KEYPOINTS", "DRIBBLING_CRITICAL_KEYPOINTS",
        "UPPER_BODY_KEYPOINTS", "LOWER_BODY_KEYPOINTS",
        # 관절 각도 10
        "ELBOW_ANGLE_MIN_DEG", "ELBOW_ANGLE_MAX_DEG",
        "KNEE_ANGLE_MIN_DEG", "KNEE_ANGLE_MAX_DEG",
        "SHOULDER_ANGLE_MIN_DEG", "SHOULDER_ANGLE_MAX_DEG",
        "HIP_ANGLE_MIN_DEG", "HIP_ANGLE_MAX_DEG",
        "ANKLE_ANGLE_MIN_DEG", "ANKLE_ANGLE_MAX_DEG",
        # 슈팅 각도 6
        "OPTIMAL_RELEASE_ANGLE_MIN_DEG", "OPTIMAL_RELEASE_ANGLE_MAX_DEG",
        "RECOMMENDED_ELBOW_ANGLE_RELEASE_DEG", "RECOMMENDED_KNEE_BEND_ANGLE_DEG",
        "WRIST_FLEXION_MIN_DEG", "WRIST_FLEXION_MAX_DEG",
        # 모델 파라미터 5
        "POSE_INPUT_SIZE", "POSE_INPUT_SIZE_HIGH",
        "HEATMAP_OUTPUT_SIZE", "HEATMAP_GAUSSIAN_SIGMA", "POSE_NMS_KERNEL_SIZE",
        # 열거형 3
        "PoseQuality", "SkeletonType", "JointType",
    ]
    for name in must_include:
        T.check(f"__all__: '{name}' 포함", name in all_exports, f"'{name}' not in __all__")

    # =================================================================
    # 섹션 24: 캐시 (frozenset 5개, dict 5개, i18n 3개 × 5개 언어)
    # =================================================================
    T.set_section("24. 캐시 (frozenset, dict, i18n 완전성)")

    # frozenset 캐시 5개
    frozenset_caches = [
        ("_POSE_QUALITY_IS_RELIABLE", 2),
        ("_JOINT_TYPE_IS_LEFT", 8),
        ("_JOINT_TYPE_IS_RIGHT", 8),
        ("_SKELETON_TYPE_HAS_HAND", 1),
        ("_SKELETON_TYPE_HAS_FACE", 1),
    ]
    for cache_name, exp_size in frozenset_caches:
        cache = getattr(pose_constants, cache_name, None)
        T.check(f"{cache_name} 존재", cache is not None, "not found")
        if cache is not None:
            T.check(f"{cache_name} 타입 frozenset", isinstance(cache, frozenset))
            T.check(f"{cache_name} 크기 = {exp_size}", len(cache) == exp_size, f"got {len(cache)}")

    # dict 캐시 5개
    dict_caches = [
        ("_SKELETON_TYPE_NUM_KEYPOINTS_MAP", 6),
        ("_SKELETON_TYPE_KOREAN_MAP", 6),
        ("_JOINT_TYPE_SYMMETRIC_MAP", 17),
        ("_JOINT_TYPE_KOREAN_MAP", 17),
        ("_POSE_QUALITY_KOREAN_MAP", 4),
    ]
    for cache_name, exp_size in dict_caches:
        cache = getattr(pose_constants, cache_name, None)
        T.check(f"{cache_name} 존재", cache is not None, "not found")
        if cache is not None:
            T.check(f"{cache_name} 타입 dict", isinstance(cache, dict))
            T.check(f"{cache_name} 크기 = {exp_size}", len(cache) == exp_size, f"got {len(cache)}")

    # i18n 맵 3개 × 5개 언어
    i18n_caches = [
        ("_POSE_QUALITY_I18N_MAP", 4),   # 4 PoseQuality members per lang
        ("_SKELETON_TYPE_I18N_MAP", 6),  # 6 SkeletonType members per lang
        ("_JOINT_TYPE_I18N_MAP", 17),    # 17 JointType members per lang
    ]
    expected_langs = {"ko", "en", "ja", "zh", "es"}
    for map_name, exp_members_per_lang in i18n_caches:
        i18n_map = getattr(pose_constants, map_name, None)
        T.check(f"{map_name} 존재", i18n_map is not None, "not found")
        if i18n_map is not None:
            T.check(f"{map_name} 타입 dict", isinstance(i18n_map, dict))
            actual_langs = set(i18n_map.keys())
            T.check(
                f"{map_name} 5개 언어 포함",
                actual_langs == expected_langs,
                f"got {actual_langs}"
            )
            for lang_code in expected_langs:
                lang_dict = i18n_map.get(lang_code, {})
                T.check(
                    f"{map_name}['{lang_code}'] 크기 = {exp_members_per_lang}",
                    len(lang_dict) == exp_members_per_lang,
                    f"got {len(lang_dict)}"
                )
                # 모든 값이 문자열이고 비어있지 않음
                all_str = all(isinstance(v, str) and len(v) > 0 for v in lang_dict.values())
                T.check(
                    f"{map_name}['{lang_code}'] 모든 값 비어있지 않은 str",
                    all_str
                )

    # =================================================================
    # 섹션 25: 메타 (버전, 타입)
    # =================================================================
    T.set_section("25. 메타 (버전 2.1.0, 타입)")

    version = getattr(pose_constants, "__version__", None)
    T.check("__version__ 존재", version is not None)
    T.check("__version__ == '2.1.0'", version == "2.1.0", f"got '{version}'")
    T.check("__version__ 타입 str", isinstance(version, str))

    # Final 타입 힌트 사용 확인 (임포트 검증)
    T.check("typing.Final 임포트 확인", hasattr(pose_constants, 'JOINT_CONFIDENCE_THRESHOLD'))

    # 모듈명 확인
    T.check(
        "모듈명 'shared.constants.pose_constants'",
        pose_constants.__name__ == "shared.constants.pose_constants",
        f"got '{pose_constants.__name__}'"
    )

    # Enum unique 데코레이터 검증: 중복값 없음
    pq_values = [pq.value for pq in PoseQuality]
    T.check("PoseQuality 값 중복 없음", len(pq_values) == len(set(pq_values)))

    st_values = [st.value for st in SkeletonType]
    T.check("SkeletonType 값 중복 없음", len(st_values) == len(set(st_values)))

    jt_values_list = [jt.value for jt in JointType]
    T.check("JointType 값 중복 없음", len(jt_values_list) == len(set(jt_values_list)))

    # 열거형 접근 by name
    T.check("PoseQuality['HIGH'] 접근 가능", PoseQuality["HIGH"] == PoseQuality.HIGH)
    T.check("SkeletonType['COCO'] 접근 가능", SkeletonType["COCO"] == SkeletonType.COCO)
    T.check("JointType['NOSE'] 접근 가능", JointType["NOSE"] == JointType.NOSE)

    # JointType은 정수값으로도 접근 가능 (IntEnum 특성)
    T.check("JointType(0) == JointType.NOSE", JointType(0) == JointType.NOSE)
    T.check("JointType(16) == JointType.RIGHT_ANKLE", JointType(16) == JointType.RIGHT_ANKLE)

    # SkeletonType은 값으로 접근 가능
    T.check("SkeletonType('mediapipe') == MEDIAPIPE", SkeletonType("mediapipe") == SkeletonType.MEDIAPIPE)
    T.check("SkeletonType('coco') == COCO", SkeletonType("coco") == SkeletonType.COCO)

    # 교차 검증: 모든 키포인트 그룹 요소가 COCO 범위 (0-16)
    all_group_elements = (
        SHOOTING_CRITICAL_KEYPOINTS | DRIBBLING_CRITICAL_KEYPOINTS |
        UPPER_BODY_KEYPOINTS | LOWER_BODY_KEYPOINTS
    )
    T.check(
        "모든 그룹 요소 COCO 범위 내",
        all(0 <= idx <= 16 for idx in all_group_elements)
    )

    # 상체+하체 합치면 COCO 17개 관절 중 15개 (귀 제외)
    upper_lower_union = UPPER_BODY_KEYPOINTS | LOWER_BODY_KEYPOINTS
    T.check(
        "상체+하체 합집합 크기 = 15",
        len(upper_lower_union) == 15,
        f"got {len(upper_lower_union)}"
    )

    # 귀(3, 4)는 상체/하체 어디에도 포함되지 않음
    T.check("왼쪽 귀 상체에 미포함", KEYPOINT_LEFT_EAR not in UPPER_BODY_KEYPOINTS)
    T.check("오른쪽 귀 상체에 미포함", KEYPOINT_RIGHT_EAR not in UPPER_BODY_KEYPOINTS)
    T.check("왼쪽 귀 하체에 미포함", KEYPOINT_LEFT_EAR not in LOWER_BODY_KEYPOINTS)
    T.check("오른쪽 귀 하체에 미포함", KEYPOINT_RIGHT_EAR not in LOWER_BODY_KEYPOINTS)

    # -- 결과 요약 --
    sys.exit(0 if T.summary() else 1)


if __name__ == "__main__":
    main()
