# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_pose_dto.py

포즈 DTO 유닛 테스트
- 모듈 메타데이터 (__version__, __all__)
- Enum re-export (JointType, SkeletonType, PoseQuality)
- Keypoint 생성/프로퍼티/메서드
- JointAngle 생성/프로퍼티/메서드/i18n
- Skeleton2D 생성/프로퍼티/메서드
- Skeleton3D 생성/프로퍼티/메서드
- PoseEstimationResult 생성/프로퍼티/메서드

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import math
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

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

    def eq(self, name: str, actual, expected) -> None:
        if actual == expected:
            self.ok(name)
        else:
            self.fail(name, f"expected {expected!r}, got {actual!r}")

    def true(self, name: str, value: bool) -> None:
        if value:
            self.ok(name)
        else:
            self.fail(name, "expected True")

    def false(self, name: str, value: bool) -> None:
        if not value:
            self.ok(name)
        else:
            self.fail(name, "expected False")

    def none(self, name: str, value) -> None:
        if value is None:
            self.ok(name)
        else:
            self.fail(name, f"expected None, got {value!r}")

    def not_none(self, name: str, value) -> None:
        if value is not None:
            self.ok(name)
        else:
            self.fail(name, "expected not None")

    def approx(self, name: str, actual: float, expected: float, tol: float = 0.01) -> None:
        if abs(actual - expected) < tol:
            self.ok(name)
        else:
            self.fail(name, f"expected ~{expected}, got {actual}")

    def isinstance_check(self, name: str, obj, cls) -> None:
        if isinstance(obj, cls):
            self.ok(name)
        else:
            self.fail(name, f"expected {cls.__name__}, got {type(obj).__name__}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. 모듈 메타데이터 ====================
def test_module_metadata(r: TestResult) -> None:
    """모듈 메타데이터 검증"""
    import shared.dto.pose_dto as m

    r.eq("__version__", m.__version__, "2.0.0")
    r.eq("__all__ 길이", len(m.__all__), 8)

    expected_exports = [
        "JointType", "SkeletonType", "PoseQuality",
        "Keypoint", "JointAngle",
        "Skeleton2D", "Skeleton3D", "PoseEstimationResult",
    ]
    for name in expected_exports:
        r.true(f"__all__에 {name} 포함", name in m.__all__)
        r.true(f"{name} 접근 가능", hasattr(m, name))


# ==================== 2. Enum re-export ====================
def test_enum_reexports(r: TestResult) -> None:
    """Enum re-export 검증"""
    from shared.dto.pose_dto import JointType, SkeletonType, PoseQuality
    from shared.constants.pose_constants import (
        JointType as OrigJointType,
        SkeletonType as OrigSkeletonType,
        PoseQuality as OrigPoseQuality,
    )

    # 동일 클래스인지
    r.true("JointType is same", JointType is OrigJointType)
    r.true("SkeletonType is same", SkeletonType is OrigSkeletonType)
    r.true("PoseQuality is same", PoseQuality is OrigPoseQuality)

    # 주요 멤버
    r.not_none("JointType.NOSE", JointType.NOSE)
    r.not_none("JointType.LEFT_SHOULDER", JointType.LEFT_SHOULDER)
    r.not_none("JointType.RIGHT_ELBOW", JointType.RIGHT_ELBOW)
    r.not_none("SkeletonType.COCO", SkeletonType.COCO)
    r.not_none("PoseQuality.HIGH", PoseQuality.HIGH)
    r.not_none("PoseQuality.MEDIUM", PoseQuality.MEDIUM)
    r.not_none("PoseQuality.LOW", PoseQuality.LOW)
    r.not_none("PoseQuality.INVALID", PoseQuality.INVALID)


# ==================== 3. Keypoint ====================
def test_keypoint_creation(r: TestResult) -> None:
    """Keypoint 기본 생성"""
    from shared.dto.pose_dto import Keypoint, JointType

    # 기본값
    kp = Keypoint()
    r.approx("기본 x", kp.x, 0.0)
    r.approx("기본 y", kp.y, 0.0)
    r.none("기본 z", kp.z)
    r.approx("기본 confidence", kp.confidence, 0.0)
    r.eq("기본 visibility", kp.visibility, 1)
    r.none("기본 joint_type", kp.joint_type)
    r.true("is_dataclass", is_dataclass(kp))

    # 전체 필드
    kp2 = Keypoint(
        x=100.5, y=200.3, z=50.0,
        confidence=0.95, visibility=1,
        joint_type=JointType.NOSE,
    )
    r.approx("x=100.5", kp2.x, 100.5)
    r.approx("y=200.3", kp2.y, 200.3)
    r.approx("z=50.0", kp2.z, 50.0)
    r.approx("confidence=0.95", kp2.confidence, 0.95)
    r.eq("joint_type=NOSE", kp2.joint_type, JointType.NOSE)


def test_keypoint_confidence_clamp(r: TestResult) -> None:
    """Keypoint confidence 클램핑"""
    from shared.dto.pose_dto import Keypoint

    kp_over = Keypoint(confidence=1.5)
    r.approx("confidence > 1 → 1.0", kp_over.confidence, 1.0)

    kp_under = Keypoint(confidence=-0.3)
    r.approx("confidence < 0 → 0.0", kp_under.confidence, 0.0)


def test_keypoint_properties(r: TestResult) -> None:
    """Keypoint 프로퍼티"""
    from shared.dto.pose_dto import Keypoint
    from shared.constants.pose_constants import JOINT_CONFIDENCE_THRESHOLD

    # is_valid (threshold 이상)
    kp_valid = Keypoint(confidence=JOINT_CONFIDENCE_THRESHOLD + 0.01)
    r.true("is_valid (above threshold)", kp_valid.is_valid)

    kp_invalid = Keypoint(confidence=JOINT_CONFIDENCE_THRESHOLD - 0.01)
    r.false("is_valid (below threshold)", kp_invalid.is_valid)

    # is_visible
    kp_vis = Keypoint(confidence=0.9, visibility=1)
    r.true("is_visible (vis=1, valid)", kp_vis.is_visible)

    kp_hidden = Keypoint(confidence=0.9, visibility=0)
    r.false("is_visible (vis=0)", kp_hidden.is_visible)

    kp_low = Keypoint(confidence=0.01, visibility=1)
    r.false("is_visible (low confidence)", kp_low.is_visible)

    # has_depth
    kp_3d = Keypoint(z=10.0)
    r.true("has_depth (z=10)", kp_3d.has_depth)

    kp_2d = Keypoint()
    r.false("has_depth (z=None)", kp_2d.has_depth)

    # position_2d
    kp = Keypoint(x=10.0, y=20.0)
    r.eq("position_2d", kp.position_2d, (10.0, 20.0))

    # position_3d
    kp3 = Keypoint(x=1.0, y=2.0, z=3.0)
    r.eq("position_3d (with z)", kp3.position_3d, (1.0, 2.0, 3.0))

    kp_no_z = Keypoint(x=1.0, y=2.0)
    r.none("position_3d (no z)", kp_no_z.position_3d)


def test_keypoint_conversion(r: TestResult) -> None:
    """Keypoint → Point2D/Point3D 변환"""
    from shared.dto.pose_dto import Keypoint
    from shared.dto.geometry_dto import Point2D, Point3D

    kp = Keypoint(x=10.0, y=20.0, z=30.0, confidence=0.9)

    p2d = kp.to_point2d()
    r.isinstance_check("to_point2d() → Point2D", p2d, Point2D)
    r.approx("Point2D.x", p2d.x, 10.0)
    r.approx("Point2D.y", p2d.y, 20.0)

    p3d = kp.to_point3d()
    r.not_none("to_point3d() → not None", p3d)
    r.isinstance_check("to_point3d() → Point3D", p3d, Point3D)
    r.approx("Point3D.z", p3d.z, 30.0)

    # z=None → None
    kp_no_z = Keypoint(x=1.0, y=2.0)
    r.none("to_point3d() (no z) → None", kp_no_z.to_point3d())


def test_keypoint_distance(r: TestResult) -> None:
    """Keypoint 거리 계산"""
    from shared.dto.pose_dto import Keypoint

    kp1 = Keypoint(x=0.0, y=0.0, z=0.0)
    kp2 = Keypoint(x=3.0, y=4.0, z=0.0)

    # 2D 거리
    d2d = kp1.distance_to(kp2)
    r.approx("2D distance (3,4,5)", d2d, 5.0)

    # 3D 거리
    kp3 = Keypoint(x=0.0, y=0.0, z=0.0)
    kp4 = Keypoint(x=1.0, y=2.0, z=2.0)
    d3d = kp3.distance_to_3d(kp4)
    r.not_none("3D distance not None", d3d)
    r.approx("3D distance (1,2,2)=3", d3d, 3.0)

    # z=None → None
    kp5 = Keypoint(x=0.0, y=0.0)
    kp6 = Keypoint(x=1.0, y=1.0, z=1.0)
    r.none("3D distance (no z) → None", kp5.distance_to_3d(kp6))


# ==================== 4. JointAngle ====================
def test_joint_angle_creation(r: TestResult) -> None:
    """JointAngle 기본 생성"""
    from shared.dto.pose_dto import JointAngle, JointType

    ja = JointAngle(joint=JointType.RIGHT_ELBOW)
    r.eq("joint", ja.joint, JointType.RIGHT_ELBOW)
    r.none("parent_joint default", ja.parent_joint)
    r.none("child_joint default", ja.child_joint)
    r.approx("angle_deg default", ja.angle_deg, 0.0)
    r.approx("confidence default", ja.confidence, 1.0)
    r.true("is_valid default", ja.is_valid)

    # 전체 필드
    ja2 = JointAngle(
        joint=JointType.RIGHT_ELBOW,
        parent_joint=JointType.RIGHT_SHOULDER,
        child_joint=JointType.RIGHT_WRIST,
        angle_deg=90.0,
        confidence=0.85,
    )
    r.eq("parent_joint", ja2.parent_joint, JointType.RIGHT_SHOULDER)
    r.eq("child_joint", ja2.child_joint, JointType.RIGHT_WRIST)
    r.approx("angle_deg=90", ja2.angle_deg, 90.0)
    r.approx("confidence=0.85", ja2.confidence, 0.85)


def test_joint_angle_clamp(r: TestResult) -> None:
    """JointAngle 클램핑/정규화"""
    from shared.dto.pose_dto import JointAngle, JointType

    # confidence 클램핑
    ja_over = JointAngle(joint=JointType.NOSE, confidence=2.0)
    r.approx("confidence > 1 → 1.0", ja_over.confidence, 1.0)

    ja_under = JointAngle(joint=JointType.NOSE, confidence=-1.0)
    r.approx("confidence < 0 → 0.0", ja_under.confidence, 0.0)

    # angle_deg 정규화 (음수 → 절대값, 0~180 클램핑)
    ja_neg = JointAngle(joint=JointType.NOSE, angle_deg=-45.0)
    r.approx("angle_deg=-45 → 45", ja_neg.angle_deg, 45.0)

    ja_over_angle = JointAngle(joint=JointType.NOSE, angle_deg=200.0)
    r.approx("angle_deg=200 → 180", ja_over_angle.angle_deg, 180.0)


def test_joint_angle_properties(r: TestResult) -> None:
    """JointAngle 프로퍼티"""
    from shared.dto.pose_dto import JointAngle, JointType

    # angle_rad
    ja90 = JointAngle(joint=JointType.NOSE, angle_deg=90.0)
    r.approx("angle_rad (90°)", ja90.angle_rad, math.pi / 2, tol=0.001)

    ja180 = JointAngle(joint=JointType.NOSE, angle_deg=180.0)
    r.approx("angle_rad (180°)", ja180.angle_rad, math.pi, tol=0.001)

    # is_flexed (< 90)
    ja_flex = JointAngle(joint=JointType.NOSE, angle_deg=45.0)
    r.true("is_flexed (45°)", ja_flex.is_flexed)

    ja_not_flex = JointAngle(joint=JointType.NOSE, angle_deg=90.0)
    r.false("is_flexed (90°)", ja_not_flex.is_flexed)

    # is_extended (>= 135)
    ja_ext = JointAngle(joint=JointType.NOSE, angle_deg=150.0)
    r.true("is_extended (150°)", ja_ext.is_extended)

    ja_not_ext = JointAngle(joint=JointType.NOSE, angle_deg=134.0)
    r.false("is_extended (134°)", ja_not_ext.is_extended)

    # is_in_range
    ja_range = JointAngle(joint=JointType.NOSE, angle_deg=100.0)
    r.true("is_in_range(80, 120)", ja_range.is_in_range(80.0, 120.0))
    r.false("is_in_range(110, 130)", ja_range.is_in_range(110.0, 130.0))


def test_joint_angle_i18n(r: TestResult) -> None:
    """JointAngle i18n get_description()"""
    from shared.dto.pose_dto import JointAngle, JointType
    from shared.constants.localization import SupportedLanguage

    # 굽힘 (< 90)
    ja_flex = JointAngle(joint=JointType.RIGHT_ELBOW, angle_deg=45.0)
    desc_ko = ja_flex.get_description(SupportedLanguage.KO)
    r.true("KO 굽힘 contains 굽힘", "굽힘" in desc_ko)
    r.true("KO 굽힘 contains 45.0°", "45.0°" in desc_ko)

    desc_en = ja_flex.get_description(SupportedLanguage.EN)
    r.true("EN flexed contains Flexed", "Flexed" in desc_en)

    desc_ja = ja_flex.get_description(SupportedLanguage.JA)
    r.true("JA flexed contains 屈曲", "屈曲" in desc_ja)

    # 중립 (90~134)
    ja_neutral = JointAngle(joint=JointType.LEFT_KNEE, angle_deg=100.0)
    desc_ko_n = ja_neutral.get_description(SupportedLanguage.KO)
    r.true("KO 중립 contains 중립", "중립" in desc_ko_n)

    desc_en_n = ja_neutral.get_description(SupportedLanguage.EN)
    r.true("EN neutral contains Neutral", "Neutral" in desc_en_n)

    # 펼침 (>= 135)
    ja_ext = JointAngle(joint=JointType.RIGHT_KNEE, angle_deg=170.0)
    desc_ko_e = ja_ext.get_description(SupportedLanguage.KO)
    r.true("KO 펼침 contains 펼침", "펼침" in desc_ko_e)

    desc_zh = ja_ext.get_description(SupportedLanguage.ZH)
    r.true("ZH extended contains 伸展", "伸展" in desc_zh)

    desc_es = ja_ext.get_description(SupportedLanguage.ES)
    r.true("ES extended contains Extendido", "Extendido" in desc_es)

    # to_korean_description (하위호환)
    ko_desc = ja_flex.to_korean_description
    r.true("to_korean_description contains 굽힘", "굽힘" in ko_desc)


def test_joint_angle_default_joint_name(r: TestResult) -> None:
    """JointAngle 기본 관절명 (joint=None 시나리오 - 커버리지)"""
    from shared.dto.pose_dto import JointAngle, JointType
    from shared.constants.localization import SupportedLanguage

    # _get_default_joint_name 직접 테스트
    ja = JointAngle(joint=JointType.NOSE, angle_deg=90.0)

    ko = ja._get_default_joint_name(SupportedLanguage.KO)
    r.eq("기본 관절명 KO", ko, "관절")

    en = ja._get_default_joint_name(SupportedLanguage.EN)
    r.eq("기본 관절명 EN", en, "Joint")

    ja_name = ja._get_default_joint_name(SupportedLanguage.JA)
    r.eq("기본 관절명 JA", ja_name, "関節")

    zh = ja._get_default_joint_name(SupportedLanguage.ZH)
    r.eq("기본 관절명 ZH", zh, "关节")

    es = ja._get_default_joint_name(SupportedLanguage.ES)
    r.eq("기본 관절명 ES", es, "Articulación")


# ==================== 5. Skeleton2D ====================
def _make_keypoints(n: int = 17, confidence: float = 0.9):
    """테스트용 키포인트 생성 헬퍼"""
    from shared.dto.pose_dto import Keypoint, JointType

    keypoints = []
    joint_types = list(JointType)
    for i in range(n):
        jt = joint_types[i] if i < len(joint_types) else None
        keypoints.append(Keypoint(
            x=float(i * 10), y=float(i * 5),
            confidence=confidence,
            visibility=1,
            joint_type=jt,
        ))
    return keypoints


def test_skeleton2d_creation(r: TestResult) -> None:
    """Skeleton2D 기본 생성"""
    from shared.dto.pose_dto import Skeleton2D, SkeletonType, PoseQuality

    # 기본값
    sk = Skeleton2D()
    r.eq("기본 keypoints", len(sk.keypoints), 0)
    r.eq("기본 skeleton_type", sk.skeleton_type, SkeletonType.COCO)
    r.approx("기본 confidence", sk.confidence, 0.0)
    r.none("기본 bbox", sk.bbox)
    r.none("기본 person_id", sk.person_id)
    r.eq("기본 quality (empty)", sk.quality, PoseQuality.INVALID)
    r.eq("기본 frame_index", sk.frame_index, 0)
    r.none("기본 timestamp", sk.timestamp)


def test_skeleton2d_auto_quality(r: TestResult) -> None:
    """Skeleton2D __post_init__ 자동 품질 계산"""
    from shared.dto.pose_dto import Skeleton2D, PoseQuality

    # 전체 17 키포인트, 높은 신뢰도 → 높은 품질
    kps = _make_keypoints(17, confidence=0.95)
    sk = Skeleton2D(keypoints=kps)
    r.true("자동 품질 != INVALID", sk.quality != PoseQuality.INVALID)

    # 낮은 신뢰도 키포인트
    kps_low = _make_keypoints(17, confidence=0.01)
    sk_low = Skeleton2D(keypoints=kps_low)
    # quality는 completeness 기반이므로 낮은 completeness → 낮은 품질
    # completeness = valid/total. confidence 0.01 < threshold이면 invalid keypoints
    # 결과: quality는 POOR 이하


def test_skeleton2d_properties(r: TestResult) -> None:
    """Skeleton2D 프로퍼티"""
    from shared.dto.pose_dto import Skeleton2D

    kps = _make_keypoints(17, confidence=0.9)
    sk = Skeleton2D(keypoints=kps)

    r.eq("num_keypoints", sk.num_keypoints, 17)
    r.eq("num_valid_keypoints", sk.num_valid_keypoints, 17)
    r.approx("completeness (17/17)", sk.completeness, 1.0)
    r.approx("average_confidence", sk.average_confidence, 0.9)
    r.true("is_valid", sk.is_valid)

    # valid_keypoints 리스트
    valid = sk.valid_keypoints
    r.eq("valid_keypoints 길이", len(valid), 17)

    # 빈 스켈레톤
    sk_empty = Skeleton2D()
    r.approx("빈 completeness", sk_empty.completeness, 0.0)
    r.approx("빈 average_confidence", sk_empty.average_confidence, 0.0)


def test_skeleton2d_get_keypoint(r: TestResult) -> None:
    """Skeleton2D get_keypoint / get_keypoint_position"""
    from shared.dto.pose_dto import Skeleton2D, JointType

    kps = _make_keypoints(17, confidence=0.9)
    sk = Skeleton2D(keypoints=kps)

    # get_keypoint
    kp_nose = sk.get_keypoint(JointType.NOSE)
    r.not_none("get_keypoint(NOSE)", kp_nose)
    r.approx("NOSE x=0", kp_nose.x, 0.0)

    # 인덱스 기반 조회
    kp_shoulder = sk.get_keypoint(JointType.LEFT_SHOULDER)
    r.not_none("get_keypoint(LEFT_SHOULDER)", kp_shoulder)

    # 범위 밖
    from shared.dto.pose_dto import JointType as JT
    # JointType은 COCO 17 관절이므로 17 이상은 없음
    # 대신 빈 스켈레톤에서 조회
    sk_empty = Skeleton2D()
    r.none("빈 스켈레톤 get_keypoint", sk_empty.get_keypoint(JointType.NOSE))

    # get_keypoint_position
    pos = sk.get_keypoint_position(JointType.NOSE)
    r.not_none("get_keypoint_position(NOSE)", pos)
    r.eq("position tuple", pos, (0.0, 0.0))

    # invalid keypoint → None
    kps_low = _make_keypoints(17, confidence=0.01)
    sk_low = Skeleton2D(keypoints=kps_low)
    r.none("get_keypoint_position (low conf)", sk_low.get_keypoint_position(JointType.NOSE))


def test_skeleton2d_calculate_angle(r: TestResult) -> None:
    """Skeleton2D 각도 계산"""
    from shared.dto.pose_dto import Skeleton2D, Keypoint, JointType

    # 직각 (90°) 만들기: parent(0,1), joint(0,0), child(1,0)
    kps = [Keypoint(x=0.0, y=0.0, confidence=0.0) for _ in range(17)]

    # JointType 값이 인덱스로 사용되므로 적절한 인덱스에 배치
    elbow_idx = int(JointType.RIGHT_ELBOW)
    shoulder_idx = int(JointType.RIGHT_SHOULDER)
    wrist_idx = int(JointType.RIGHT_WRIST)

    kps[shoulder_idx] = Keypoint(x=0.0, y=100.0, confidence=0.9)
    kps[elbow_idx] = Keypoint(x=0.0, y=0.0, confidence=0.9)
    kps[wrist_idx] = Keypoint(x=100.0, y=0.0, confidence=0.9)

    sk = Skeleton2D(keypoints=kps)

    # 직접 계산
    angle = sk.calculate_angle(
        JointType.RIGHT_ELBOW,
        JointType.RIGHT_SHOULDER,
        JointType.RIGHT_WRIST,
    )
    r.not_none("각도 계산 결과", angle)
    r.approx("직각 90°", angle.angle_deg, 90.0, tol=1.0)
    r.eq("joint type", angle.joint, JointType.RIGHT_ELBOW)
    r.eq("parent_joint", angle.parent_joint, JointType.RIGHT_SHOULDER)
    r.eq("child_joint", angle.child_joint, JointType.RIGHT_WRIST)

    # invalid keypoint → None
    kps_bad = [Keypoint(x=0.0, y=0.0, confidence=0.01) for _ in range(17)]
    sk_bad = Skeleton2D(keypoints=kps_bad)
    r.none("low conf → None", sk_bad.calculate_angle(
        JointType.RIGHT_ELBOW, JointType.RIGHT_SHOULDER, JointType.RIGHT_WRIST
    ))

    # 빈 스켈레톤 → None
    sk_empty = Skeleton2D()
    r.none("빈 스켈레톤 → None", sk_empty.calculate_angle(
        JointType.RIGHT_ELBOW, JointType.RIGHT_SHOULDER, JointType.RIGHT_WRIST
    ))


def test_skeleton2d_elbow_knee_angle(r: TestResult) -> None:
    """Skeleton2D calculate_elbow_angle / calculate_knee_angle"""
    from shared.dto.pose_dto import Skeleton2D, Keypoint, JointType

    kps = [Keypoint(x=0.0, y=0.0, confidence=0.9) for _ in range(17)]

    # 팔꿈치 직각 (right)
    elbow_idx = int(JointType.RIGHT_ELBOW)
    shoulder_idx = int(JointType.RIGHT_SHOULDER)
    wrist_idx = int(JointType.RIGHT_WRIST)
    kps[shoulder_idx] = Keypoint(x=0.0, y=100.0, confidence=0.9)
    kps[elbow_idx] = Keypoint(x=0.0, y=0.0, confidence=0.9)
    kps[wrist_idx] = Keypoint(x=100.0, y=0.0, confidence=0.9)

    # 무릎 직각 (right)
    knee_idx = int(JointType.RIGHT_KNEE)
    hip_idx = int(JointType.RIGHT_HIP)
    ankle_idx = int(JointType.RIGHT_ANKLE)
    kps[hip_idx] = Keypoint(x=0.0, y=100.0, confidence=0.9)
    kps[knee_idx] = Keypoint(x=0.0, y=0.0, confidence=0.9)
    kps[ankle_idx] = Keypoint(x=100.0, y=0.0, confidence=0.9)

    sk = Skeleton2D(keypoints=kps)

    elbow_angle = sk.calculate_elbow_angle("right")
    r.not_none("elbow_angle right", elbow_angle)
    r.approx("elbow 90°", elbow_angle.angle_deg, 90.0, tol=1.0)

    knee_angle = sk.calculate_knee_angle("right")
    r.not_none("knee_angle right", knee_angle)
    r.approx("knee 90°", knee_angle.angle_deg, 90.0, tol=1.0)

    # left side
    l_elbow_idx = int(JointType.LEFT_ELBOW)
    l_shoulder_idx = int(JointType.LEFT_SHOULDER)
    l_wrist_idx = int(JointType.LEFT_WRIST)
    kps[l_shoulder_idx] = Keypoint(x=0.0, y=100.0, confidence=0.9)
    kps[l_elbow_idx] = Keypoint(x=0.0, y=0.0, confidence=0.9)
    kps[l_wrist_idx] = Keypoint(x=100.0, y=0.0, confidence=0.9)

    l_knee_idx = int(JointType.LEFT_KNEE)
    l_hip_idx = int(JointType.LEFT_HIP)
    l_ankle_idx = int(JointType.LEFT_ANKLE)
    kps[l_hip_idx] = Keypoint(x=0.0, y=100.0, confidence=0.9)
    kps[l_knee_idx] = Keypoint(x=0.0, y=0.0, confidence=0.9)
    kps[l_ankle_idx] = Keypoint(x=100.0, y=0.0, confidence=0.9)

    sk2 = Skeleton2D(keypoints=kps)

    elbow_left = sk2.calculate_elbow_angle("left")
    r.not_none("elbow_angle left", elbow_left)
    r.approx("left elbow 90°", elbow_left.angle_deg, 90.0, tol=1.0)

    knee_left = sk2.calculate_knee_angle("left")
    r.not_none("knee_angle left", knee_left)
    r.approx("left knee 90°", knee_left.angle_deg, 90.0, tol=1.0)


def test_skeleton2d_connections(r: TestResult) -> None:
    """Skeleton2D get_skeleton_connections"""
    from shared.dto.pose_dto import Skeleton2D

    kps = _make_keypoints(17, confidence=0.9)
    sk = Skeleton2D(keypoints=kps)

    conns = sk.get_skeleton_connections()
    r.true("connections > 0", len(conns) > 0)
    # 각 연결은 (Keypoint, Keypoint) 튜플
    r.eq("connection tuple len", len(conns[0]), 2)

    # 빈 스켈레톤
    sk_empty = Skeleton2D()
    r.eq("빈 connections", len(sk_empty.get_skeleton_connections()), 0)


def test_skeleton2d_to_numpy(r: TestResult) -> None:
    """Skeleton2D to_numpy"""
    import numpy as np
    from shared.dto.pose_dto import Skeleton2D

    kps = _make_keypoints(17, confidence=0.9)
    sk = Skeleton2D(keypoints=kps)

    arr = sk.to_numpy()
    r.eq("shape", arr.shape, (17, 3))
    r.eq("dtype", arr.dtype, np.float32)
    r.approx("arr[0,0] = x", float(arr[0, 0]), 0.0)
    r.approx("arr[0,2] = conf", float(arr[0, 2]), 0.9)

    # 빈 스켈레톤
    sk_empty = Skeleton2D()
    arr_e = sk_empty.to_numpy()
    r.eq("빈 shape", arr_e.shape, (0, 3))


def test_skeleton2d_is_reliable(r: TestResult) -> None:
    """Skeleton2D is_reliable 프로퍼티"""
    from shared.dto.pose_dto import Skeleton2D, PoseQuality

    # EXCELLENT quality → reliable
    kps = _make_keypoints(17, confidence=0.99)
    sk = Skeleton2D(keypoints=kps)
    # quality 자동 계산됨 — completeness=1.0 → EXCELLENT
    r.true("is_reliable (high conf)", sk.is_reliable)

    # INVALID → not reliable
    sk_empty = Skeleton2D()
    r.false("is_reliable (empty)", sk_empty.is_reliable)


# ==================== 6. Skeleton3D ====================
def _make_3d_keypoints(n: int = 17, confidence: float = 0.9):
    """3D 키포인트 생성 헬퍼"""
    from shared.dto.pose_dto import Keypoint, JointType

    keypoints = []
    joint_types = list(JointType)
    for i in range(n):
        jt = joint_types[i] if i < len(joint_types) else None
        keypoints.append(Keypoint(
            x=float(i * 10), y=float(i * 5), z=float(i * 2),
            confidence=confidence,
            visibility=1,
            joint_type=jt,
        ))
    return keypoints


def test_skeleton3d_creation(r: TestResult) -> None:
    """Skeleton3D 기본 생성"""
    from shared.dto.pose_dto import Skeleton3D, SkeletonType, PoseQuality

    sk = Skeleton3D()
    r.eq("기본 keypoints", len(sk.keypoints), 0)
    r.eq("기본 skeleton_type", sk.skeleton_type, SkeletonType.COCO)
    r.none("기본 root_position", sk.root_position)
    r.none("기본 person_id", sk.person_id)
    r.eq("기본 quality", sk.quality, PoseQuality.INVALID)
    r.none("기본 camera_id", sk.camera_id)
    r.false("기본 is_triangulated", sk.is_triangulated)


def test_skeleton3d_auto_quality_and_root(r: TestResult) -> None:
    """Skeleton3D __post_init__ 자동 품질 + 루트 위치 계산"""
    from shared.dto.pose_dto import Skeleton3D, PoseQuality, JointType

    kps = _make_3d_keypoints(17, confidence=0.95)
    sk = Skeleton3D(keypoints=kps)

    # 자동 품질 계산
    r.true("quality != INVALID", sk.quality != PoseQuality.INVALID)

    # 루트 위치 자동 계산 (LEFT_HIP + RIGHT_HIP 평균)
    left_hip_idx = int(JointType.LEFT_HIP)
    right_hip_idx = int(JointType.RIGHT_HIP)
    expected_x = (kps[left_hip_idx].x + kps[right_hip_idx].x) / 2
    expected_y = (kps[left_hip_idx].y + kps[right_hip_idx].y) / 2
    expected_z = (kps[left_hip_idx].z + kps[right_hip_idx].z) / 2

    r.not_none("root_position 자동 계산", sk.root_position)
    r.approx("root x", sk.root_position.x, expected_x)
    r.approx("root y", sk.root_position.y, expected_y)
    r.approx("root z", sk.root_position.z, expected_z)


def test_skeleton3d_properties(r: TestResult) -> None:
    """Skeleton3D 프로퍼티"""
    from shared.dto.pose_dto import Skeleton3D

    kps = _make_3d_keypoints(17, confidence=0.9)
    sk = Skeleton3D(keypoints=kps)

    r.eq("num_keypoints", sk.num_keypoints, 17)
    r.eq("num_valid_keypoints", sk.num_valid_keypoints, 17)
    r.approx("completeness", sk.completeness, 1.0)
    r.true("is_valid", sk.is_valid)

    # valid_keypoints (3D 좌표 포함만)
    valid = sk.valid_keypoints
    r.eq("valid_keypoints len", len(valid), 17)


def test_skeleton3d_get_keypoint(r: TestResult) -> None:
    """Skeleton3D get_keypoint / get_keypoint_position_3d"""
    from shared.dto.pose_dto import Skeleton3D, JointType

    kps = _make_3d_keypoints(17, confidence=0.9)
    sk = Skeleton3D(keypoints=kps)

    # get_keypoint
    kp = sk.get_keypoint(JointType.NOSE)
    r.not_none("get_keypoint(NOSE)", kp)

    # get_keypoint_position_3d
    pos = sk.get_keypoint_position_3d(JointType.NOSE)
    r.not_none("position_3d not None", pos)
    r.eq("position_3d is tuple[3]", len(pos), 3)

    # 빈 스켈레톤
    sk_empty = Skeleton3D()
    r.none("빈 get_keypoint", sk_empty.get_keypoint(JointType.NOSE))
    r.none("빈 get_keypoint_position_3d", sk_empty.get_keypoint_position_3d(JointType.NOSE))


def test_skeleton3d_calculate_angle_3d(r: TestResult) -> None:
    """Skeleton3D 3D 각도 계산"""
    from shared.dto.pose_dto import Skeleton3D, Keypoint, JointType

    kps = [Keypoint(x=0.0, y=0.0, z=0.0, confidence=0.9) for _ in range(17)]

    # 직각 (90°) in 3D: parent(0,0,1), joint(0,0,0), child(1,0,0)
    elbow_idx = int(JointType.RIGHT_ELBOW)
    shoulder_idx = int(JointType.RIGHT_SHOULDER)
    wrist_idx = int(JointType.RIGHT_WRIST)

    kps[shoulder_idx] = Keypoint(x=0.0, y=0.0, z=100.0, confidence=0.9)
    kps[elbow_idx] = Keypoint(x=0.0, y=0.0, z=0.0, confidence=0.9)
    kps[wrist_idx] = Keypoint(x=100.0, y=0.0, z=0.0, confidence=0.9)

    sk = Skeleton3D(keypoints=kps)

    angle = sk.calculate_angle_3d(
        JointType.RIGHT_ELBOW,
        JointType.RIGHT_SHOULDER,
        JointType.RIGHT_WRIST,
    )
    r.not_none("3D 각도 결과", angle)
    r.approx("3D 직각 90°", angle.angle_deg, 90.0, tol=1.0)

    # z=None → None
    kps_no_z = [Keypoint(x=0.0, y=0.0, confidence=0.9) for _ in range(17)]
    sk_no_z = Skeleton3D(keypoints=kps_no_z)
    r.none("z=None → None", sk_no_z.calculate_angle_3d(
        JointType.RIGHT_ELBOW, JointType.RIGHT_SHOULDER, JointType.RIGHT_WRIST
    ))


def test_skeleton3d_to_numpy(r: TestResult) -> None:
    """Skeleton3D to_numpy"""
    import numpy as np
    from shared.dto.pose_dto import Skeleton3D

    kps = _make_3d_keypoints(17, confidence=0.9)
    sk = Skeleton3D(keypoints=kps)

    arr = sk.to_numpy()
    r.eq("shape (17,4)", arr.shape, (17, 4))
    r.eq("dtype float32", arr.dtype, np.float32)
    r.approx("arr[1,2] = z", float(arr[1, 2]), 2.0)

    # 빈 스켈레톤
    sk_empty = Skeleton3D()
    arr_e = sk_empty.to_numpy()
    r.eq("빈 shape (0,4)", arr_e.shape, (0, 4))


def test_skeleton3d_to_skeleton_2d(r: TestResult) -> None:
    """Skeleton3D → Skeleton2D 변환"""
    from shared.dto.pose_dto import Skeleton3D, Skeleton2D

    kps = _make_3d_keypoints(17, confidence=0.9)
    sk3d = Skeleton3D(
        keypoints=kps, person_id=5, frame_index=100,
    )

    sk2d = sk3d.to_skeleton_2d()
    r.isinstance_check("to_skeleton_2d → Skeleton2D", sk2d, Skeleton2D)
    r.eq("keypoints 수 유지", len(sk2d.keypoints), 17)
    r.none("z 제거됨", sk2d.keypoints[0].z)
    r.eq("person_id 유지", sk2d.person_id, 5)
    r.eq("frame_index 유지", sk2d.frame_index, 100)
    r.approx("x 유지", sk2d.keypoints[1].x, 10.0)


# ==================== 7. PoseEstimationResult ====================
def test_pose_result_creation(r: TestResult) -> None:
    """PoseEstimationResult 기본 생성"""
    from shared.dto.pose_dto import PoseEstimationResult

    pr = PoseEstimationResult()
    r.eq("기본 frame_index", pr.frame_index, 0)
    r.approx("기본 timestamp", pr.timestamp, 0.0)
    r.eq("기본 skeletons_2d", len(pr.skeletons_2d), 0)
    r.eq("기본 skeletons_3d", len(pr.skeletons_3d), 0)
    r.eq("기본 num_persons", pr.num_persons, 0)
    r.none("기본 camera_id", pr.camera_id)
    r.eq("기본 model_name", pr.model_name, "mediapipe")


def test_pose_result_auto_num_persons(r: TestResult) -> None:
    """PoseEstimationResult __post_init__ 자동 인원 수"""
    from shared.dto.pose_dto import PoseEstimationResult, Skeleton2D

    kps = _make_keypoints(17, confidence=0.9)
    sk1 = Skeleton2D(keypoints=kps, person_id=1)
    sk2 = Skeleton2D(keypoints=kps, person_id=2)

    pr = PoseEstimationResult(skeletons_2d=[sk1, sk2])
    r.eq("auto num_persons=2", pr.num_persons, 2)

    # 명시적 설정
    pr2 = PoseEstimationResult(skeletons_2d=[sk1], num_persons=5)
    r.eq("명시적 num_persons=5", pr2.num_persons, 5)


def test_pose_result_properties(r: TestResult) -> None:
    """PoseEstimationResult 프로퍼티"""
    from shared.dto.pose_dto import PoseEstimationResult, Skeleton2D, Skeleton3D

    kps_2d = _make_keypoints(17, confidence=0.9)
    kps_3d = _make_3d_keypoints(17, confidence=0.9)

    sk2d = Skeleton2D(keypoints=kps_2d, person_id=1)
    sk3d = Skeleton3D(keypoints=kps_3d, person_id=1)

    pr = PoseEstimationResult(
        skeletons_2d=[sk2d],
        skeletons_3d=[sk3d],
    )

    r.true("has_3d", pr.has_3d)
    r.eq("valid_skeletons_2d", len(pr.valid_skeletons_2d), 1)
    r.eq("valid_skeletons_3d", len(pr.valid_skeletons_3d), 1)
    r.true("average_quality > 0", pr.average_quality > 0)

    # has_3d = False
    pr_no3d = PoseEstimationResult(skeletons_2d=[sk2d])
    r.false("has_3d (no 3d)", pr_no3d.has_3d)

    # 빈 결과
    pr_empty = PoseEstimationResult()
    r.approx("빈 average_quality", pr_empty.average_quality, 0.0)


def test_pose_result_get_skeleton(r: TestResult) -> None:
    """PoseEstimationResult get_skeleton_2d / get_skeleton_3d"""
    from shared.dto.pose_dto import PoseEstimationResult, Skeleton2D, Skeleton3D

    kps_2d = _make_keypoints(17, confidence=0.9)
    kps_3d = _make_3d_keypoints(17, confidence=0.9)

    sk2d_1 = Skeleton2D(keypoints=kps_2d, person_id=1)
    sk2d_2 = Skeleton2D(keypoints=kps_2d, person_id=2)
    sk3d_1 = Skeleton3D(keypoints=kps_3d, person_id=1)

    pr = PoseEstimationResult(
        skeletons_2d=[sk2d_1, sk2d_2],
        skeletons_3d=[sk3d_1],
    )

    # get_skeleton_2d
    found_2d = pr.get_skeleton_2d(1)
    r.not_none("get_skeleton_2d(1)", found_2d)
    r.eq("person_id=1", found_2d.person_id, 1)

    found_2d_2 = pr.get_skeleton_2d(2)
    r.not_none("get_skeleton_2d(2)", found_2d_2)
    r.eq("person_id=2", found_2d_2.person_id, 2)

    r.none("get_skeleton_2d(999)", pr.get_skeleton_2d(999))

    # get_skeleton_3d
    found_3d = pr.get_skeleton_3d(1)
    r.not_none("get_skeleton_3d(1)", found_3d)
    r.none("get_skeleton_3d(999)", pr.get_skeleton_3d(999))


# ==================== 8. 타입 검증 ====================
def test_modern_typing(r: TestResult) -> None:
    """모던 typing 검증 (Optional/Dict/List/Tuple 미사용)"""
    with open(Path(_PROJECT_ROOT) / "shared" / "dto" / "pose_dto.py", "r", encoding="utf-8") as f:
        content = f.read()

    # TYPE_CHECKING은 허용
    import_line = None
    for line in content.split("\n"):
        if line.startswith("from typing import"):
            import_line = line
            break

    r.not_none("typing import 존재", import_line)
    r.true("TYPE_CHECKING만 임포트", "TYPE_CHECKING" in import_line)
    r.false("Any 미포함", "Any" in import_line and "Any" != "TYPE_CHECKING")

    # 레거시 패턴 없음
    r.false("Optional[ 미사용", "Optional[" in content)
    r.false("Dict[ 미사용", "Dict[" in content)
    r.false("List[ 미사용", "List[" in content)
    r.false("Tuple[ 미사용", "Tuple[" in content)

    # 모던 패턴 사용
    r.true("list[ 사용", "list[" in content)
    r.true("tuple[ 사용", "tuple[" in content)
    r.true("| None 사용", "| None" in content)


def test_no_unused_imports(r: TestResult) -> None:
    """미사용 임포트 제거 검증"""
    with open(Path(_PROJECT_ROOT) / "shared" / "dto" / "pose_dto.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 제거 대상 확인
    r.false("uuid 미임포트", "from uuid import" in content)
    r.false("timezone 미임포트", "timezone" in content.split("from datetime")[0] if "from datetime" in content else content)

    # NUM_KEYPOINTS_COCO 미임포트
    r.false("NUM_KEYPOINTS_COCO 미임포트", "NUM_KEYPOINTS_COCO" in content)


# ==================== 9. 엣지 케이스 ====================
def test_skeleton2d_zero_norm_angle(r: TestResult) -> None:
    """Skeleton2D 각도 계산 시 영벡터 → None"""
    from shared.dto.pose_dto import Skeleton2D, Keypoint, JointType

    kps = [Keypoint(x=0.0, y=0.0, confidence=0.9) for _ in range(17)]
    # 모든 점이 같은 위치 → 벡터 norm=0
    sk = Skeleton2D(keypoints=kps)
    angle = sk.calculate_angle(
        JointType.RIGHT_ELBOW, JointType.RIGHT_SHOULDER, JointType.RIGHT_WRIST,
    )
    r.none("영벡터 → None", angle)


def test_skeleton3d_zero_norm_angle(r: TestResult) -> None:
    """Skeleton3D 3D 각도 계산 시 영벡터 → None"""
    from shared.dto.pose_dto import Skeleton3D, Keypoint, JointType

    kps = [Keypoint(x=5.0, y=5.0, z=5.0, confidence=0.9) for _ in range(17)]
    sk = Skeleton3D(keypoints=kps)
    angle = sk.calculate_angle_3d(
        JointType.RIGHT_ELBOW, JointType.RIGHT_SHOULDER, JointType.RIGHT_WRIST,
    )
    r.none("3D 영벡터 → None", angle)


def test_skeleton3d_no_root_when_no_z(r: TestResult) -> None:
    """Skeleton3D 루트 계산 불가 (z=None)"""
    from shared.dto.pose_dto import Skeleton3D, Keypoint

    # z=None 키포인트
    kps = [Keypoint(x=float(i), y=float(i), confidence=0.9) for i in range(17)]
    sk = Skeleton3D(keypoints=kps)
    r.none("z=None → root=None", sk.root_position)


def test_keypoint_boundary_values(r: TestResult) -> None:
    """Keypoint 경계값"""
    from shared.dto.pose_dto import Keypoint

    # 음수 좌표
    kp_neg = Keypoint(x=-100.0, y=-200.0, z=-50.0, confidence=0.5)
    r.approx("음수 x", kp_neg.x, -100.0)
    r.approx("음수 y", kp_neg.y, -200.0)
    r.approx("음수 z", kp_neg.z, -50.0)

    # 큰 좌표
    kp_big = Keypoint(x=10000.0, y=20000.0, confidence=1.0)
    r.approx("큰 x", kp_big.x, 10000.0)

    # confidence 정확히 경계
    kp_0 = Keypoint(confidence=0.0)
    r.approx("confidence=0", kp_0.confidence, 0.0)
    kp_1 = Keypoint(confidence=1.0)
    r.approx("confidence=1", kp_1.confidence, 1.0)


def test_joint_angle_boundary(r: TestResult) -> None:
    """JointAngle 경계값"""
    from shared.dto.pose_dto import JointAngle, JointType

    # 0도
    ja_0 = JointAngle(joint=JointType.NOSE, angle_deg=0.0)
    r.approx("0도", ja_0.angle_deg, 0.0)
    r.true("0도 is_flexed", ja_0.is_flexed)
    r.false("0도 is_extended", ja_0.is_extended)

    # 180도
    ja_180 = JointAngle(joint=JointType.NOSE, angle_deg=180.0)
    r.approx("180도", ja_180.angle_deg, 180.0)
    r.false("180도 is_flexed", ja_180.is_flexed)
    r.true("180도 is_extended", ja_180.is_extended)

    # 정확히 135도
    ja_135 = JointAngle(joint=JointType.NOSE, angle_deg=135.0)
    r.true("135도 is_extended", ja_135.is_extended)
    r.false("135도 is_flexed", ja_135.is_flexed)

    # 정확히 90도
    ja_90 = JointAngle(joint=JointType.NOSE, angle_deg=90.0)
    r.false("90도 is_flexed", ja_90.is_flexed)
    r.false("90도 is_extended", ja_90.is_extended)


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("pose_dto.py v2.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 메타데이터 ---")
    test_module_metadata(r)

    print("\n--- Enum re-export ---")
    test_enum_reexports(r)

    print("\n--- Keypoint ---")
    test_keypoint_creation(r)
    test_keypoint_confidence_clamp(r)
    test_keypoint_properties(r)
    test_keypoint_conversion(r)
    test_keypoint_distance(r)

    print("\n--- JointAngle ---")
    test_joint_angle_creation(r)
    test_joint_angle_clamp(r)
    test_joint_angle_properties(r)
    test_joint_angle_i18n(r)
    test_joint_angle_default_joint_name(r)

    print("\n--- Skeleton2D ---")
    test_skeleton2d_creation(r)
    test_skeleton2d_auto_quality(r)
    test_skeleton2d_properties(r)
    test_skeleton2d_get_keypoint(r)
    test_skeleton2d_calculate_angle(r)
    test_skeleton2d_elbow_knee_angle(r)
    test_skeleton2d_connections(r)
    test_skeleton2d_to_numpy(r)
    test_skeleton2d_is_reliable(r)

    print("\n--- Skeleton3D ---")
    test_skeleton3d_creation(r)
    test_skeleton3d_auto_quality_and_root(r)
    test_skeleton3d_properties(r)
    test_skeleton3d_get_keypoint(r)
    test_skeleton3d_calculate_angle_3d(r)
    test_skeleton3d_to_numpy(r)
    test_skeleton3d_to_skeleton_2d(r)

    print("\n--- PoseEstimationResult ---")
    test_pose_result_creation(r)
    test_pose_result_auto_num_persons(r)
    test_pose_result_properties(r)
    test_pose_result_get_skeleton(r)

    print("\n--- 타입 검증 ---")
    test_modern_typing(r)
    test_no_unused_imports(r)

    print("\n--- 엣지 케이스 ---")
    test_skeleton2d_zero_norm_angle(r)
    test_skeleton3d_zero_norm_angle(r)
    test_skeleton3d_no_root_when_no_z(r)
    test_keypoint_boundary_values(r)
    test_joint_angle_boundary(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
