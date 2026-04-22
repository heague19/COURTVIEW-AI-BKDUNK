# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/pose_estimation/unit
파일: test_keypoint_types.py
설명: keypoint_types.py 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0
"""
from __future__ import annotations

import numpy as np
import pytest

from pose_estimation.keypoint_types import (
    # 열거형
    CocoKeypoint,
    MediaPipeKeypoint,
    UnifiedKeypoint,
    WholeBodyKeypoint,
    # 데이터 클래스
    KeypointData,
    KeypointPair,
    # 스켈레톤 연결
    COCO_SKELETON,
    MEDIAPIPE_SKELETON,
    WHOLEBODY_BODY_SKELETON,
    SKELETON_CONNECTIONS,
    # 신체 부위 그룹
    BODY_PARTS,
    LEFT_SIDE_KEYPOINTS,
    RIGHT_SIDE_KEYPOINTS,
    UPPER_BODY_KEYPOINTS,
    LOWER_BODY_KEYPOINTS,
    # 농구 특화 그룹
    BASKETBALL_KEYPOINT_GROUPS,
    SHOOTING_ARM_KEYPOINTS,
    DRIBBLING_KEYPOINTS,
    # 매핑
    COCO_TO_UNIFIED_MAPPING,
    MEDIAPIPE_TO_UNIFIED_MAPPING,
    WHOLEBODY_TO_COCO_MAPPING,
    WHOLEBODY_TO_UNIFIED_MAPPING,
    UNIFIED_TO_COCO_MAPPING,
    UNIFIED_TO_MEDIAPIPE_MAPPING,
    # 대칭 쌍
    UNIFIED_SYMMETRIC_PAIRS,
    COCO_SYMMETRIC_PAIRS,
    # 한글 이름
    COCO_KEYPOINT_NAMES_KO,
    MEDIAPIPE_KEYPOINT_NAMES_KO,
    WHOLEBODY_KEYPOINT_NAMES_KO,
    UNIFIED_KEYPOINT_NAMES_KO,
    # 관절 정의
    JOINT_DEFINITIONS,
    # 유틸리티 함수
    get_keypoint_name,
    get_joint_keypoints,
    map_keypoints,
    get_symmetric_keypoint,
    is_keypoint_visible,
    get_body_part_keypoints,
    get_basketball_keypoints,
)


# ============================================================
# 1. 열거형 테스트
# ============================================================
class TestCocoKeypoint:
    """COCO 17개 키포인트 열거형 테스트."""

    def test_count(self) -> None:
        assert len(CocoKeypoint) == 17

    def test_nose_is_zero(self) -> None:
        assert CocoKeypoint.NOSE == 0

    def test_right_ankle_is_16(self) -> None:
        assert CocoKeypoint.RIGHT_ANKLE == 16

    def test_is_int_enum(self) -> None:
        assert isinstance(CocoKeypoint.NOSE, int)

    def test_indexing(self) -> None:
        """IntEnum은 배열 인덱싱에 직접 사용 가능."""
        arr = np.zeros(17)
        arr[CocoKeypoint.NOSE] = 1.0
        assert arr[0] == 1.0


class TestMediaPipeKeypoint:
    """MediaPipe 33개 키포인트 열거형 테스트."""

    def test_count(self) -> None:
        assert len(MediaPipeKeypoint) == 33

    def test_first_last(self) -> None:
        assert MediaPipeKeypoint.NOSE == 0
        assert MediaPipeKeypoint.RIGHT_FOOT_INDEX == 32


class TestUnifiedKeypoint:
    """Unified 25개 키포인트 열거형 테스트."""

    def test_count(self) -> None:
        assert len(UnifiedKeypoint) == 25

    def test_neck_pelvis_at_end(self) -> None:
        """NECK과 PELVIS는 계산 키포인트로 마지막에 위치."""
        assert UnifiedKeypoint.NECK == 23
        assert UnifiedKeypoint.PELVIS == 24

    def test_finger_keypoints(self) -> None:
        """농구 릴리즈 분석용 손가락 키포인트 존재."""
        assert UnifiedKeypoint.LEFT_INDEX == 11
        assert UnifiedKeypoint.RIGHT_INDEX == 12
        assert UnifiedKeypoint.LEFT_PINKY == 13
        assert UnifiedKeypoint.RIGHT_PINKY == 14
        assert UnifiedKeypoint.LEFT_THUMB == 15
        assert UnifiedKeypoint.RIGHT_THUMB == 16


class TestWholeBodyKeypoint:
    """WholeBody 133개 키포인트 열거형 테스트."""

    def test_body_range(self) -> None:
        """Body 0-16은 COCO 표준과 동일."""
        assert WholeBodyKeypoint.NOSE == 0
        assert WholeBodyKeypoint.RIGHT_ANKLE == 16

    def test_foot_range(self) -> None:
        """Foot 17-22."""
        assert WholeBodyKeypoint.LEFT_BIG_TOE == 17
        assert WholeBodyKeypoint.RIGHT_HEEL == 22

    def test_hand_range(self) -> None:
        """LeftHand 91-111, RightHand 112-132."""
        assert WholeBodyKeypoint.LEFT_HAND_WRIST == 91
        assert WholeBodyKeypoint.LEFT_HAND_PINKY_TIP == 111
        assert WholeBodyKeypoint.RIGHT_HAND_WRIST == 112
        assert WholeBodyKeypoint.RIGHT_HAND_PINKY_TIP == 132

    def test_face_landmarks(self) -> None:
        """Face 23-90 대표 랜드마크."""
        assert WholeBodyKeypoint.FACE_0 == 23
        assert WholeBodyKeypoint.FACE_67 == 90


# ============================================================
# 2. 데이터 클래스 테스트
# ============================================================
class TestKeypointData:
    """KeypointData 데이터 클래스 테스트."""

    def test_creation(self) -> None:
        kd = KeypointData(x=0.5, y=0.3, z=0.1, confidence=0.9)
        assert kd.x == 0.5
        assert kd.y == 0.3
        assert kd.z == 0.1
        assert kd.confidence == 0.9
        assert kd.visibility == 1.0  # 기본값

    def test_defaults(self) -> None:
        kd = KeypointData(x=0.5, y=0.3)
        assert kd.z == 0.0
        assert kd.confidence == 0.0
        assert kd.visibility == 1.0

    def test_frozen(self) -> None:
        """frozen=True로 불변."""
        kd = KeypointData(x=0.5, y=0.3)
        with pytest.raises(AttributeError):
            kd.x = 1.0  # type: ignore[misc]

    def test_to_array(self) -> None:
        kd = KeypointData(x=0.5, y=0.3, z=0.1, confidence=0.9)
        arr = kd.to_array()
        assert arr.dtype == np.float32
        assert len(arr) == 4
        np.testing.assert_allclose(arr, [0.5, 0.3, 0.1, 0.9], atol=1e-6)

    def test_to_2d(self) -> None:
        kd = KeypointData(x=0.5, y=0.3)
        assert kd.to_2d() == (0.5, 0.3)

    def test_to_3d(self) -> None:
        kd = KeypointData(x=0.5, y=0.3, z=0.1)
        assert kd.to_3d() == (0.5, 0.3, 0.1)

    def test_from_array_4d(self) -> None:
        arr = np.array([0.5, 0.3, 0.1, 0.9])
        kd = KeypointData.from_array(arr)
        assert kd.x == pytest.approx(0.5)
        assert kd.y == pytest.approx(0.3)
        assert kd.z == pytest.approx(0.1)
        assert kd.confidence == pytest.approx(0.9)

    def test_from_array_3d(self) -> None:
        arr = np.array([0.5, 0.3, 0.8])
        kd = KeypointData.from_array(arr)
        assert kd.x == pytest.approx(0.5)
        assert kd.confidence == pytest.approx(0.8)

    def test_from_array_2d(self) -> None:
        arr = np.array([0.5, 0.3])
        kd = KeypointData.from_array(arr)
        assert kd.x == pytest.approx(0.5)
        assert kd.y == pytest.approx(0.3)


class TestKeypointPair:
    """KeypointPair NamedTuple 테스트."""

    def test_creation(self) -> None:
        pair = KeypointPair(start=0, end=1, name="코-눈")
        assert pair.start == 0
        assert pair.end == 1
        assert pair.name == "코-눈"

    def test_default_name(self) -> None:
        pair = KeypointPair(start=5, end=6)
        assert pair.name == ""

    def test_unpacking(self) -> None:
        pair = KeypointPair(start=0, end=1, name="test")
        s, e, n = pair
        assert s == 0
        assert e == 1
        assert n == "test"


# ============================================================
# 3. 스켈레톤 연결 테스트
# ============================================================
class TestSkeletonConnections:
    """스켈레톤 연결 정의 테스트."""

    def test_coco_skeleton_count(self) -> None:
        assert len(COCO_SKELETON) == 16

    def test_coco_skeleton_elements_are_tuples(self) -> None:
        for conn in COCO_SKELETON:
            assert isinstance(conn, tuple)
            assert len(conn) == 2

    def test_mediapipe_skeleton_count(self) -> None:
        assert len(MEDIAPIPE_SKELETON) == 35

    def test_wholebody_skeleton_has_hand_connections(self) -> None:
        """WholeBody 스켈레톤에 손가락 연결 포함."""
        hand_connections = [(s, e) for s, e in WHOLEBODY_BODY_SKELETON if s >= 91 or e >= 91]
        assert len(hand_connections) > 0

    def test_unified_skeleton_uses_keypointpair(self) -> None:
        for conn in SKELETON_CONNECTIONS:
            assert isinstance(conn, KeypointPair)

    def test_unified_skeleton_count(self) -> None:
        assert len(SKELETON_CONNECTIONS) == 28


# ============================================================
# 4. 신체 부위 그룹 테스트
# ============================================================
class TestBodyParts:
    """신체 부위 그룹 테스트."""

    def test_all_parts_present(self) -> None:
        expected_parts = {
            "head", "neck", "torso",
            "left_arm", "right_arm",
            "left_hand", "right_hand",
            "left_leg", "right_leg",
        }
        assert set(BODY_PARTS.keys()) == expected_parts

    def test_parts_use_frozenset(self) -> None:
        for part_keypoints in BODY_PARTS.values():
            assert isinstance(part_keypoints, frozenset)

    def test_left_right_disjoint_except_center(self) -> None:
        """좌우 키포인트는 중심선 키포인트와 겹치지 않음."""
        center_keypoints = {UnifiedKeypoint.NOSE, UnifiedKeypoint.NECK, UnifiedKeypoint.PELVIS}
        assert LEFT_SIDE_KEYPOINTS.isdisjoint(center_keypoints)
        assert RIGHT_SIDE_KEYPOINTS.isdisjoint(center_keypoints)

    def test_left_right_symmetric_count(self) -> None:
        assert len(LEFT_SIDE_KEYPOINTS) == len(RIGHT_SIDE_KEYPOINTS)

    def test_upper_lower_cover_all(self) -> None:
        """상하체 합치면 전체 25개."""
        all_kps = UPPER_BODY_KEYPOINTS | LOWER_BODY_KEYPOINTS
        assert len(all_kps) == 25


# ============================================================
# 5. 농구 특화 그룹 테스트
# ============================================================
class TestBasketballGroups:
    """농구 특화 키포인트 그룹 테스트."""

    def test_all_actions_present(self) -> None:
        expected = {"shooting", "release", "dribbling", "defense", "jumping", "pivot", "passing", "rebounding"}
        assert set(BASKETBALL_KEYPOINT_GROUPS.keys()) == expected

    def test_shooting_includes_arms(self) -> None:
        shooting = BASKETBALL_KEYPOINT_GROUPS["shooting"]
        assert UnifiedKeypoint.LEFT_ELBOW in shooting
        assert UnifiedKeypoint.RIGHT_ELBOW in shooting

    def test_release_is_right_hand(self) -> None:
        """릴리즈는 오른손잡이 기준."""
        release = BASKETBALL_KEYPOINT_GROUPS["release"]
        assert UnifiedKeypoint.RIGHT_WRIST in release
        assert UnifiedKeypoint.RIGHT_INDEX in release
        assert UnifiedKeypoint.RIGHT_THUMB in release

    def test_shooting_arm_keypoints(self) -> None:
        assert UnifiedKeypoint.RIGHT_SHOULDER in SHOOTING_ARM_KEYPOINTS
        assert UnifiedKeypoint.RIGHT_WRIST in SHOOTING_ARM_KEYPOINTS

    def test_dribbling_keypoints(self) -> None:
        assert UnifiedKeypoint.LEFT_WRIST in DRIBBLING_KEYPOINTS
        assert UnifiedKeypoint.RIGHT_WRIST in DRIBBLING_KEYPOINTS


# ============================================================
# 6. 매핑 테스트
# ============================================================
class TestMappings:
    """모델 간 키포인트 매핑 테스트."""

    def test_coco_to_unified_covers_all_17(self) -> None:
        assert len(COCO_TO_UNIFIED_MAPPING) == 17

    def test_mediapipe_to_unified_has_finger_mappings(self) -> None:
        assert MediaPipeKeypoint.LEFT_INDEX in MEDIAPIPE_TO_UNIFIED_MAPPING
        assert MEDIAPIPE_TO_UNIFIED_MAPPING[MediaPipeKeypoint.LEFT_INDEX] == UnifiedKeypoint.LEFT_INDEX

    def test_wholebody_to_coco_identity(self) -> None:
        """WholeBody 0-16은 COCO와 동일 매핑."""
        for i in range(17):
            assert WHOLEBODY_TO_COCO_MAPPING[i] == i

    def test_wholebody_to_unified_finger_tips(self) -> None:
        """WholeBody 손가락 끝 → Unified 손가락."""
        assert WHOLEBODY_TO_UNIFIED_MAPPING[99] == UnifiedKeypoint.LEFT_INDEX.value
        assert WHOLEBODY_TO_UNIFIED_MAPPING[120] == UnifiedKeypoint.RIGHT_INDEX.value

    def test_unified_to_coco_none_for_fingers(self) -> None:
        """Unified 손가락은 COCO에 없으므로 None."""
        assert UNIFIED_TO_COCO_MAPPING[UnifiedKeypoint.LEFT_INDEX] is None
        assert UNIFIED_TO_COCO_MAPPING[UnifiedKeypoint.NECK] is None

    def test_unified_to_mediapipe_none_for_computed(self) -> None:
        """NECK/PELVIS는 MediaPipe에 없으므로 None."""
        assert UNIFIED_TO_MEDIAPIPE_MAPPING[UnifiedKeypoint.NECK] is None
        assert UNIFIED_TO_MEDIAPIPE_MAPPING[UnifiedKeypoint.PELVIS] is None


# ============================================================
# 7. 대칭 쌍 테스트
# ============================================================
class TestSymmetricPairs:
    """대칭 키포인트 쌍 테스트."""

    def test_unified_symmetric_is_reflexive(self) -> None:
        """A→B이면 B→A."""
        for kp_a, kp_b in UNIFIED_SYMMETRIC_PAIRS.items():
            assert UNIFIED_SYMMETRIC_PAIRS[kp_b] == kp_a

    def test_coco_symmetric_is_reflexive(self) -> None:
        for kp_a, kp_b in COCO_SYMMETRIC_PAIRS.items():
            assert COCO_SYMMETRIC_PAIRS[kp_b] == kp_a

    def test_center_keypoints_not_in_symmetric(self) -> None:
        """중심선 키포인트(NOSE, NECK, PELVIS)는 대칭 쌍에 없음."""
        assert UnifiedKeypoint.NOSE not in UNIFIED_SYMMETRIC_PAIRS
        assert UnifiedKeypoint.NECK not in UNIFIED_SYMMETRIC_PAIRS
        assert UnifiedKeypoint.PELVIS not in UNIFIED_SYMMETRIC_PAIRS


# ============================================================
# 8. 한글 이름 테스트
# ============================================================
class TestKoreanNames:
    """한글 키포인트 이름 테스트."""

    def test_coco_names_complete(self) -> None:
        assert len(COCO_KEYPOINT_NAMES_KO) == 17

    def test_mediapipe_names_complete(self) -> None:
        assert len(MEDIAPIPE_KEYPOINT_NAMES_KO) == 33

    def test_unified_names_complete(self) -> None:
        assert len(UNIFIED_KEYPOINT_NAMES_KO) == 25

    def test_nose_korean(self) -> None:
        assert COCO_KEYPOINT_NAMES_KO[CocoKeypoint.NOSE] == "코"

    def test_neck_korean(self) -> None:
        assert UNIFIED_KEYPOINT_NAMES_KO[UnifiedKeypoint.NECK] == "목"


# ============================================================
# 9. 관절 정의 테스트
# ============================================================
class TestJointDefinitions:
    """JOINT_DEFINITIONS 모듈 레벨 상수 테스트."""

    def test_is_module_level(self) -> None:
        """함수 내부가 아닌 모듈 레벨 상수."""
        assert isinstance(JOINT_DEFINITIONS, dict)

    def test_all_joints_present(self) -> None:
        expected = {
            "left_elbow", "right_elbow",
            "left_shoulder", "right_shoulder",
            "left_knee", "right_knee",
            "left_hip", "right_hip",
            "left_wrist", "right_wrist",
            "neck", "torso_left", "torso_right",
        }
        assert set(JOINT_DEFINITIONS.keys()) == expected

    def test_each_joint_has_three_keypoints(self) -> None:
        for joint_name, (parent, joint, child) in JOINT_DEFINITIONS.items():
            assert isinstance(parent, UnifiedKeypoint), f"{joint_name} parent"
            assert isinstance(joint, UnifiedKeypoint), f"{joint_name} joint"
            assert isinstance(child, UnifiedKeypoint), f"{joint_name} child"


# ============================================================
# 10. 유틸리티 함수 테스트
# ============================================================
class TestGetKeypointName:
    """get_keypoint_name 함수 테스트."""

    def test_coco_korean(self) -> None:
        assert get_keypoint_name(CocoKeypoint.NOSE) == "코"

    def test_coco_english(self) -> None:
        assert get_keypoint_name(CocoKeypoint.NOSE, korean=False) == "NOSE"

    def test_unified_korean(self) -> None:
        assert get_keypoint_name(UnifiedKeypoint.NECK) == "목"

    def test_mediapipe_korean(self) -> None:
        assert get_keypoint_name(MediaPipeKeypoint.LEFT_EAR) == "왼쪽 귀"

    def test_wholebody_korean(self) -> None:
        result = get_keypoint_name(WholeBodyKeypoint.NOSE)
        assert result == "코"


class TestGetJointKeypoints:
    """get_joint_keypoints 함수 테스트."""

    def test_left_elbow(self) -> None:
        parent, joint, child = get_joint_keypoints("left_elbow")
        assert parent == UnifiedKeypoint.LEFT_SHOULDER
        assert joint == UnifiedKeypoint.LEFT_ELBOW
        assert child == UnifiedKeypoint.LEFT_WRIST

    def test_right_knee(self) -> None:
        parent, joint, child = get_joint_keypoints("right_knee")
        assert parent == UnifiedKeypoint.RIGHT_HIP
        assert joint == UnifiedKeypoint.RIGHT_KNEE
        assert child == UnifiedKeypoint.RIGHT_ANKLE

    def test_invalid_joint_raises(self) -> None:
        with pytest.raises(ValueError, match="알 수 없는 관절 이름"):
            get_joint_keypoints("invalid_joint")


class TestMapKeypoints:
    """map_keypoints 함수 테스트."""

    def test_coco_to_unified(self) -> None:
        coco_kpts = np.ones((17, 3), dtype=np.float32)
        # 신뢰도를 모두 1.0으로 설정 (3번째 열)
        result = map_keypoints(coco_kpts, "coco", "unified")
        assert result.shape == (25, 3)
        # NOSE → NOSE (index 0)
        np.testing.assert_allclose(result[0], [1.0, 1.0, 1.0])

    def test_coco_to_unified_neck_pelvis(self) -> None:
        """NECK/PELVIS는 어깨/엉덩이 중점으로 계산."""
        coco_kpts = np.zeros((17, 3), dtype=np.float32)
        # 양 어깨 설정 (LEFT_SHOULDER=5, RIGHT_SHOULDER=6)
        coco_kpts[5] = [0.3, 0.5, 1.0]
        coco_kpts[6] = [0.7, 0.5, 1.0]
        # 양 엉덩이 (LEFT_HIP=11, RIGHT_HIP=12)
        coco_kpts[11] = [0.4, 0.8, 1.0]
        coco_kpts[12] = [0.6, 0.8, 1.0]

        result = map_keypoints(coco_kpts, "coco", "unified")
        # NECK (index 23) = 양 어깨 중점
        np.testing.assert_allclose(result[23], [0.5, 0.5, 1.0], atol=1e-5)
        # PELVIS (index 24) = 양 엉덩이 중점
        np.testing.assert_allclose(result[24], [0.5, 0.8, 1.0], atol=1e-5)

    def test_same_format_returns_copy(self) -> None:
        kpts = np.ones((17, 3), dtype=np.float32)
        result = map_keypoints(kpts, "coco", "coco")
        np.testing.assert_array_equal(result, kpts)
        # 복사본이므로 원본과 메모리 공유하지 않음
        result[0, 0] = 99.0
        assert kpts[0, 0] == 1.0

    def test_wholebody_to_unified(self) -> None:
        wb_kpts = np.zeros((133, 3), dtype=np.float32)
        wb_kpts[0] = [0.5, 0.5, 1.0]  # NOSE
        wb_kpts[5] = [0.3, 0.5, 1.0]  # LEFT_SHOULDER
        wb_kpts[6] = [0.7, 0.5, 1.0]  # RIGHT_SHOULDER
        result = map_keypoints(wb_kpts, "wholebody", "unified")
        assert result.shape == (25, 3)
        np.testing.assert_allclose(result[0], [0.5, 0.5, 1.0], atol=1e-5)

    def test_invalid_target_raises(self) -> None:
        kpts = np.ones((17, 3), dtype=np.float32)
        with pytest.raises(ValueError, match="지원하지 않는 타겟 형식"):
            map_keypoints(kpts, "coco", "invalid")

    def test_invalid_conversion_raises(self) -> None:
        kpts = np.ones((17, 3), dtype=np.float32)
        with pytest.raises(ValueError, match="지원하지 않는 변환"):
            map_keypoints(kpts, "coco", "mediapipe")


class TestGetSymmetricKeypoint:
    """get_symmetric_keypoint 함수 테스트."""

    def test_unified_symmetric(self) -> None:
        result = get_symmetric_keypoint(UnifiedKeypoint.LEFT_SHOULDER)
        assert result == UnifiedKeypoint.RIGHT_SHOULDER

    def test_coco_symmetric(self) -> None:
        result = get_symmetric_keypoint(CocoKeypoint.LEFT_EYE)
        assert result == CocoKeypoint.RIGHT_EYE

    def test_center_returns_none(self) -> None:
        result = get_symmetric_keypoint(UnifiedKeypoint.NOSE)
        assert result is None


class TestIsKeypointVisible:
    """is_keypoint_visible 함수 테스트."""

    def test_keypointdata_visible(self) -> None:
        kd = KeypointData(x=0.5, y=0.5, confidence=0.8)
        assert is_keypoint_visible(kd) is True

    def test_keypointdata_not_visible(self) -> None:
        kd = KeypointData(x=0.5, y=0.5, confidence=0.3)
        assert is_keypoint_visible(kd) is False

    def test_ndarray_3d(self) -> None:
        arr = np.array([0.5, 0.5, 0.8])
        assert is_keypoint_visible(arr) is True

    def test_ndarray_4d(self) -> None:
        arr = np.array([0.5, 0.5, 0.0, 0.2])
        assert is_keypoint_visible(arr) is False

    def test_tuple_3d(self) -> None:
        assert is_keypoint_visible((0.5, 0.5, 0.9)) is True

    def test_custom_threshold(self) -> None:
        kd = KeypointData(x=0.5, y=0.5, confidence=0.6)
        assert is_keypoint_visible(kd, confidence_threshold=0.7) is False
        assert is_keypoint_visible(kd, confidence_threshold=0.5) is True


class TestGetBodyPartKeypoints:
    """get_body_part_keypoints 함수 테스트."""

    def test_head(self) -> None:
        result = get_body_part_keypoints("head")
        assert UnifiedKeypoint.NOSE in result
        assert len(result) == 5

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="알 수 없는 부위 이름"):
            get_body_part_keypoints("chest")


class TestGetBasketballKeypoints:
    """get_basketball_keypoints 함수 테스트."""

    def test_shooting(self) -> None:
        result = get_basketball_keypoints("shooting")
        assert isinstance(result, frozenset)
        assert UnifiedKeypoint.RIGHT_WRIST in result

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="알 수 없는 동작 이름"):
            get_basketball_keypoints("dunking")


# ============================================================
# 11. 모듈 레벨 테스트
# ============================================================
class TestModuleLevel:
    """모듈 레벨 속성 테스트."""

    def test_version(self) -> None:
        from pose_estimation.keypoint_types import __version__
        assert __version__ == "1.0.0"

    def test_all_exports(self) -> None:
        from pose_estimation.keypoint_types import __all__
        assert "CocoKeypoint" in __all__
        assert "UnifiedKeypoint" in __all__
        assert "JOINT_DEFINITIONS" in __all__
        assert "get_keypoint_name" in __all__
        assert "map_keypoints" in __all__
