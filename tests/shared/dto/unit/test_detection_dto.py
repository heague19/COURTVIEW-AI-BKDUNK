# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_detection_dto.py

감지 결과 통합 DTO 유닛 테스트
- 모듈 구조 검증 (__all__, typing, i18n 캐시)
- Enum 클래스 (ObjectType, DetectionSource)
- 데이터클래스 (DetectedObject, DetectionConfig, DetectionResult, MultiViewDetectionResult)
- 프로퍼티 및 메서드 검증

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. 모듈 구조 검증 ====================
def test_module_import(r: TestResult) -> None:
    """모듈 임포트 성공 여부"""
    try:
        import shared.dto.detection_dto as mod
        assert hasattr(mod, "__all__")
        assert hasattr(mod, "__version__")
        r.ok("모듈 임포트")
    except Exception as e:
        r.fail("모듈 임포트", str(e))


def test_all_exports(r: TestResult) -> None:
    """__all__ 6개 export 검증 (SupportedLanguage 미포함)"""
    from shared.dto.detection_dto import __all__
    expected = {
        "ObjectType", "DetectionSource",
        "DetectedObject", "DetectionConfig", "DetectionResult",
        "MultiViewDetectionResult",
    }
    actual = set(__all__)
    if actual == expected and "SupportedLanguage" not in actual:
        r.ok(f"__all__ = {len(actual)}개 (SupportedLanguage 미포함)")
    else:
        missing = expected - actual
        extra = actual - expected
        r.fail("__all__", f"missing={missing}, extra={extra}")


def test_version(r: TestResult) -> None:
    """버전 2.0.0 확인"""
    from shared.dto.detection_dto import __version__
    if __version__ == "2.0.0":
        r.ok("__version__ = 2.0.0")
    else:
        r.fail("__version__", f"expected 2.0.0, got {__version__}")


def test_no_legacy_typing(r: TestResult) -> None:
    """Dict/List/Tuple 레거시 typing 미사용 확인"""
    import re
    src = Path(_PROJECT_ROOT / "shared" / "dto" / "detection_dto.py").read_text(encoding="utf-8")
    hits = re.findall(r'\b(Dict\[|List\[|Tuple\[)', src)
    if not hits:
        r.ok("레거시 typing 미사용")
    else:
        r.fail("레거시 typing", f"{len(hits)}건 발견")


def test_i18n_module_cache(r: TestResult) -> None:
    """i18n 모듈 레벨 캐시 2개 존재 확인"""
    import shared.dto.detection_dto as mod
    caches = ["_OBJECT_TYPE_I18N", "_DETECTION_SOURCE_I18N"]
    missing = [c for c in caches if not hasattr(mod, c)]
    if not missing:
        r.ok(f"i18n 모듈 캐시 {len(caches)}개 존재")
    else:
        r.fail("i18n 모듈 캐시", f"미존재: {missing}")


# ==================== 2. ObjectType Enum ====================
def test_object_type_members(r: TestResult) -> None:
    """ObjectType 13개 멤버"""
    from shared.dto.detection_dto import ObjectType
    expected = {
        "PLAYER", "REFEREE", "COACH", "PERSON", "BALL",
        "HOOP", "BACKBOARD", "COURT_LINE", "COURT",
        "THREE_POINT_LINE", "FREE_THROW_LINE", "KEY_AREA", "UNKNOWN",
    }
    actual = {m.name for m in ObjectType}
    if actual == expected:
        r.ok(f"ObjectType 멤버 {len(actual)}개")
    else:
        r.fail("ObjectType 멤버", f"diff={actual.symmetric_difference(expected)}")


def test_object_type_i18n(r: TestResult) -> None:
    """ObjectType.get_name 다국어"""
    from shared.dto.detection_dto import ObjectType
    from shared.constants.localization import SupportedLanguage
    assert ObjectType.PLAYER.get_name(SupportedLanguage.KO) == "선수"
    assert ObjectType.PLAYER.get_name(SupportedLanguage.EN) == "Player"
    assert ObjectType.BALL.get_name(SupportedLanguage.KO) == "공"
    assert ObjectType.HOOP.to_korean == "골대"
    r.ok("ObjectType i18n (KO/EN/to_korean)")


def test_object_type_is_person(r: TestResult) -> None:
    """ObjectType.is_person 프로퍼티"""
    from shared.dto.detection_dto import ObjectType
    assert ObjectType.PLAYER.is_person is True
    assert ObjectType.REFEREE.is_person is True
    assert ObjectType.COACH.is_person is True
    assert ObjectType.PERSON.is_person is True
    assert ObjectType.BALL.is_person is False
    assert ObjectType.HOOP.is_person is False
    r.ok("ObjectType is_person")


def test_object_type_is_court_element(r: TestResult) -> None:
    """ObjectType.is_court_element 프로퍼티"""
    from shared.dto.detection_dto import ObjectType
    assert ObjectType.HOOP.is_court_element is True
    assert ObjectType.BACKBOARD.is_court_element is True
    assert ObjectType.COURT.is_court_element is True
    assert ObjectType.THREE_POINT_LINE.is_court_element is True
    assert ObjectType.PLAYER.is_court_element is False
    assert ObjectType.BALL.is_court_element is False
    r.ok("ObjectType is_court_element")


def test_object_type_is_trackable(r: TestResult) -> None:
    """ObjectType.is_trackable 프로퍼티"""
    from shared.dto.detection_dto import ObjectType
    assert ObjectType.PLAYER.is_trackable is True
    assert ObjectType.REFEREE.is_trackable is True
    assert ObjectType.BALL.is_trackable is True
    assert ObjectType.COACH.is_trackable is False
    assert ObjectType.HOOP.is_trackable is False
    r.ok("ObjectType is_trackable")


# ==================== 3. DetectionSource Enum ====================
def test_detection_source_members(r: TestResult) -> None:
    """DetectionSource 15개 멤버"""
    from shared.dto.detection_dto import DetectionSource
    expected = {
        "YOLO", "YOLOV8", "YOLOV9", "YOLO_NAS", "RTDETR", "DETECTRON2",
        "MEDIAPIPE", "OPENPOSE", "MMPOSE",
        "BALL_DETECTOR", "COURT_DETECTOR",
        "MANUAL", "INTERPOLATED", "FUSED", "UNKNOWN",
    }
    actual = {m.name for m in DetectionSource}
    if actual == expected:
        r.ok(f"DetectionSource 멤버 {len(actual)}개")
    else:
        r.fail("DetectionSource 멤버", f"diff={actual.symmetric_difference(expected)}")


def test_detection_source_i18n(r: TestResult) -> None:
    """DetectionSource.get_name 다국어"""
    from shared.dto.detection_dto import DetectionSource
    from shared.constants.localization import SupportedLanguage
    assert DetectionSource.BALL_DETECTOR.get_name(SupportedLanguage.KO) == "공 감지기"
    assert DetectionSource.BALL_DETECTOR.get_name(SupportedLanguage.EN) == "Ball Detector"
    assert DetectionSource.MANUAL.to_korean == "수동 레이블링"
    r.ok("DetectionSource i18n (KO/EN/to_korean)")


def test_detection_source_is_deep_learning(r: TestResult) -> None:
    """DetectionSource.is_deep_learning 프로퍼티"""
    from shared.dto.detection_dto import DetectionSource
    assert DetectionSource.YOLOV8.is_deep_learning is True
    assert DetectionSource.MEDIAPIPE.is_deep_learning is True
    assert DetectionSource.BALL_DETECTOR.is_deep_learning is True
    assert DetectionSource.MANUAL.is_deep_learning is False
    assert DetectionSource.INTERPOLATED.is_deep_learning is False
    r.ok("DetectionSource is_deep_learning")


def test_detection_source_is_pose_model(r: TestResult) -> None:
    """DetectionSource.is_pose_model 프로퍼티"""
    from shared.dto.detection_dto import DetectionSource
    assert DetectionSource.MEDIAPIPE.is_pose_model is True
    assert DetectionSource.OPENPOSE.is_pose_model is True
    assert DetectionSource.MMPOSE.is_pose_model is True
    assert DetectionSource.YOLOV8.is_pose_model is False
    r.ok("DetectionSource is_pose_model")


# ==================== 4. DetectedObject ====================
def test_detected_object_defaults(r: TestResult) -> None:
    """DetectedObject 기본값"""
    from shared.dto.detection_dto import DetectedObject, ObjectType, DetectionSource
    obj = DetectedObject()
    assert obj.object_id == 0
    assert obj.object_type == ObjectType.UNKNOWN
    assert obj.bbox is None
    assert obj.confidence == 0.0
    assert obj.source == DetectionSource.UNKNOWN
    assert obj.position is None
    assert obj.class_id == -1
    assert obj.track_id is None
    assert obj.attributes == {}
    assert obj.mask is None
    assert obj.features is None
    r.ok("DetectedObject 기본값")


def test_detected_object_confidence_clamp(r: TestResult) -> None:
    """DetectedObject confidence 클램핑 (0.0~1.0)"""
    from shared.dto.detection_dto import DetectedObject
    high = DetectedObject(confidence=1.5)
    assert high.confidence == 1.0
    low = DetectedObject(confidence=-0.5)
    assert low.confidence == 0.0
    normal = DetectedObject(confidence=0.85)
    assert normal.confidence == 0.85
    r.ok("DetectedObject confidence 클램핑")


def test_detected_object_auto_position(r: TestResult) -> None:
    """DetectedObject bbox 설정 시 position 자동 계산"""
    from shared.dto.detection_dto import DetectedObject, ObjectType
    from shared.dto.geometry_dto import BoundingBox
    bbox = BoundingBox(x=100, y=200, width=50, height=60)
    obj = DetectedObject(
        object_type=ObjectType.PLAYER,
        bbox=bbox,
        confidence=0.9,
    )
    assert obj.position is not None
    # center = (x + width/2, y + height/2)
    assert obj.position.x == bbox.center.x
    assert obj.position.y == bbox.center.y
    r.ok("DetectedObject auto position")


def test_detected_object_is_valid(r: TestResult) -> None:
    """DetectedObject.is_valid 프로퍼티"""
    from shared.dto.detection_dto import DetectedObject
    from shared.dto.geometry_dto import BoundingBox
    # 유효: bbox + confidence > 0
    valid = DetectedObject(
        bbox=BoundingBox(x=10, y=10, width=50, height=50),
        confidence=0.8,
    )
    assert valid.is_valid is True
    # 무효: bbox 없음
    no_bbox = DetectedObject(confidence=0.9)
    assert no_bbox.is_valid is False
    # 무효: confidence 0
    zero_conf = DetectedObject(
        bbox=BoundingBox(x=10, y=10, width=50, height=50),
        confidence=0.0,
    )
    assert zero_conf.is_valid is False
    r.ok("DetectedObject is_valid")


def test_detected_object_type_checks(r: TestResult) -> None:
    """DetectedObject is_person_type, is_ball, is_trackable"""
    from shared.dto.detection_dto import DetectedObject, ObjectType
    player = DetectedObject(object_type=ObjectType.PLAYER)
    assert player.is_person_type is True
    assert player.is_ball is False
    assert player.is_trackable is True

    ball = DetectedObject(object_type=ObjectType.BALL)
    assert ball.is_ball is True
    assert ball.is_person_type is False

    hoop = DetectedObject(object_type=ObjectType.HOOP)
    assert hoop.is_trackable is False
    r.ok("DetectedObject type checks")


def test_detected_object_area(r: TestResult) -> None:
    """DetectedObject.area 프로퍼티"""
    from shared.dto.detection_dto import DetectedObject
    from shared.dto.geometry_dto import BoundingBox
    obj = DetectedObject(bbox=BoundingBox(x=0, y=0, width=100, height=50))
    assert obj.area == 100 * 50
    no_bbox = DetectedObject()
    assert no_bbox.area == 0.0
    r.ok("DetectedObject area")


def test_detected_object_attributes(r: TestResult) -> None:
    """DetectedObject team, jersey_number 프로퍼티"""
    from shared.dto.detection_dto import DetectedObject, ObjectType
    obj = DetectedObject(
        object_type=ObjectType.PLAYER,
        attributes={"team": "home", "jersey_number": 23},
    )
    assert obj.team == "home"
    assert obj.jersey_number == 23
    # 속성 없으면 None
    empty = DetectedObject()
    assert empty.team is None
    assert empty.jersey_number is None
    r.ok("DetectedObject team/jersey_number")


def test_detected_object_iou(r: TestResult) -> None:
    """DetectedObject.iou_with() 계산"""
    from shared.dto.detection_dto import DetectedObject
    from shared.dto.geometry_dto import BoundingBox
    obj1 = DetectedObject(bbox=BoundingBox(x=0, y=0, width=100, height=100))
    obj2 = DetectedObject(bbox=BoundingBox(x=50, y=50, width=100, height=100))
    iou = obj1.iou_with(obj2)
    assert 0.0 < iou < 1.0
    # bbox 없으면 0.0
    no_bbox = DetectedObject()
    assert obj1.iou_with(no_bbox) == 0.0
    r.ok("DetectedObject iou_with()")


def test_detected_object_distance(r: TestResult) -> None:
    """DetectedObject.distance_to() 계산"""
    from shared.dto.detection_dto import DetectedObject
    from shared.dto.geometry_dto import BoundingBox
    obj1 = DetectedObject(bbox=BoundingBox(x=0, y=0, width=10, height=10), confidence=0.9)
    obj2 = DetectedObject(bbox=BoundingBox(x=30, y=40, width=10, height=10), confidence=0.9)
    dist = obj1.distance_to(obj2)
    assert dist > 0
    # position 없으면 inf
    no_pos = DetectedObject()
    assert obj1.distance_to(no_pos) == float('inf')
    r.ok("DetectedObject distance_to()")


# ==================== 5. DetectionConfig ====================
def test_detection_config_defaults(r: TestResult) -> None:
    """DetectionConfig 기본값"""
    from shared.dto.detection_dto import DetectionConfig, ObjectType
    cfg = DetectionConfig()
    assert cfg.confidence_threshold == 0.5
    assert cfg.nms_threshold == 0.45
    assert cfg.max_detections == 100
    assert cfg.input_size == (640, 640)
    assert cfg.device == "cuda"
    assert cfg.batch_size == 1
    assert cfg.half_precision is False
    # 기본 타겟 자동 설정
    assert ObjectType.PLAYER in cfg.target_types
    assert ObjectType.BALL in cfg.target_types
    assert ObjectType.REFEREE in cfg.target_types
    r.ok("DetectionConfig 기본값")


def test_detection_config_threshold_clamp(r: TestResult) -> None:
    """DetectionConfig 임계값 클램핑"""
    from shared.dto.detection_dto import DetectionConfig
    cfg = DetectionConfig(confidence_threshold=1.5, nms_threshold=-0.1)
    assert cfg.confidence_threshold == 1.0
    assert cfg.nms_threshold == 0.0
    r.ok("DetectionConfig 임계값 클램핑")


def test_detection_config_should_detect(r: TestResult) -> None:
    """DetectionConfig.should_detect() 메서드"""
    from shared.dto.detection_dto import DetectionConfig, ObjectType
    cfg = DetectionConfig(target_types=[ObjectType.PLAYER, ObjectType.BALL])
    assert cfg.should_detect(ObjectType.PLAYER) is True
    assert cfg.should_detect(ObjectType.BALL) is True
    assert cfg.should_detect(ObjectType.HOOP) is False
    r.ok("DetectionConfig should_detect()")


def test_detection_config_to_dict(r: TestResult) -> None:
    """DetectionConfig.to_dict() 변환"""
    from shared.dto.detection_dto import DetectionConfig
    cfg = DetectionConfig()
    d = cfg.to_dict()
    assert isinstance(d, dict)
    assert d["confidence_threshold"] == 0.5
    assert d["device"] == "cuda"
    assert isinstance(d["target_types"], list)
    assert len(d) == 10
    r.ok("DetectionConfig to_dict()")


# ==================== 6. DetectionResult ====================
def test_detection_result_defaults(r: TestResult) -> None:
    """DetectionResult 기본값"""
    from shared.dto.detection_dto import DetectionResult, DetectionSource
    res = DetectionResult()
    assert res.frame_index == 0
    assert res.objects == []
    assert res.source == DetectionSource.UNKNOWN
    assert res.num_objects == 0
    assert res.camera_id is None
    r.ok("DetectionResult 기본값")


def test_detection_result_counts(r: TestResult) -> None:
    """DetectionResult 카운트 프로퍼티"""
    from shared.dto.detection_dto import DetectionResult, DetectedObject, ObjectType
    from shared.dto.geometry_dto import BoundingBox
    bbox = BoundingBox(x=10, y=10, width=50, height=50)
    res = DetectionResult(objects=[
        DetectedObject(object_id=1, object_type=ObjectType.PLAYER, bbox=bbox, confidence=0.9),
        DetectedObject(object_id=2, object_type=ObjectType.PLAYER, bbox=bbox, confidence=0.85),
        DetectedObject(object_id=3, object_type=ObjectType.REFEREE, bbox=bbox, confidence=0.8),
        DetectedObject(object_id=4, object_type=ObjectType.BALL, bbox=bbox, confidence=0.95),
    ])
    assert res.num_objects == 4
    assert res.num_persons == 3  # PLAYER×2 + REFEREE
    assert res.num_players == 2
    assert res.has_ball is True
    r.ok("DetectionResult 카운트 프로퍼티")


def test_detection_result_ball_detection(r: TestResult) -> None:
    """DetectionResult.ball_detection 프로퍼티"""
    from shared.dto.detection_dto import DetectionResult, DetectedObject, ObjectType
    from shared.dto.geometry_dto import BoundingBox
    bbox = BoundingBox(x=10, y=10, width=30, height=30)
    ball = DetectedObject(object_id=1, object_type=ObjectType.BALL, bbox=bbox, confidence=0.95)
    res = DetectionResult(objects=[ball])
    assert res.ball_detection is not None
    assert res.ball_detection.object_id == 1
    # 공 없는 경우
    res2 = DetectionResult()
    assert res2.ball_detection is None
    assert res2.has_ball is False
    r.ok("DetectionResult ball_detection")


def test_detection_result_average_confidence(r: TestResult) -> None:
    """DetectionResult.average_confidence 프로퍼티"""
    from shared.dto.detection_dto import DetectionResult, DetectedObject
    res = DetectionResult(objects=[
        DetectedObject(confidence=0.8),
        DetectedObject(confidence=0.9),
        DetectedObject(confidence=1.0),
    ])
    assert abs(res.average_confidence - 0.9) < 1e-9
    # 빈 경우
    empty = DetectionResult()
    assert empty.average_confidence == 0.0
    r.ok("DetectionResult average_confidence")


def test_detection_result_get_methods(r: TestResult) -> None:
    """DetectionResult 조회 메서드"""
    from shared.dto.detection_dto import DetectionResult, DetectedObject, ObjectType
    from shared.dto.geometry_dto import BoundingBox
    bbox = BoundingBox(x=0, y=0, width=50, height=50)
    p1 = DetectedObject(object_id=1, object_type=ObjectType.PLAYER, bbox=bbox, confidence=0.9)
    p2 = DetectedObject(object_id=2, object_type=ObjectType.PLAYER, bbox=bbox, confidence=0.7)
    ref = DetectedObject(object_id=3, object_type=ObjectType.REFEREE, bbox=bbox, confidence=0.85)
    res = DetectionResult(objects=[p1, p2, ref])

    # get_objects_by_type
    players = res.get_objects_by_type(ObjectType.PLAYER)
    assert len(players) == 2
    # get_players / get_referees
    assert len(res.get_players()) == 2
    assert len(res.get_referees()) == 1
    # get_object_by_id
    found = res.get_object_by_id(2)
    assert found is not None and found.object_id == 2
    assert res.get_object_by_id(99) is None
    # filter_by_confidence
    high = res.filter_by_confidence(0.85)
    assert len(high) == 2
    r.ok("DetectionResult get/filter 메서드")


# ==================== 7. MultiViewDetectionResult ====================
def test_multi_view_defaults(r: TestResult) -> None:
    """MultiViewDetectionResult 기본값"""
    from shared.dto.detection_dto import MultiViewDetectionResult
    mv = MultiViewDetectionResult()
    assert mv.frame_index == 0
    assert mv.view_results == {}
    assert mv.fused_objects == []
    assert mv.num_views == 0
    assert mv.num_fused_objects == 0
    assert mv.total_detections == 0
    r.ok("MultiViewDetectionResult 기본값")


def test_multi_view_with_views(r: TestResult) -> None:
    """MultiViewDetectionResult 뷰 결과 포함"""
    from shared.dto.detection_dto import (
        MultiViewDetectionResult, DetectionResult, DetectedObject, ObjectType,
    )
    from shared.dto.geometry_dto import BoundingBox
    bbox = BoundingBox(x=0, y=0, width=50, height=50)
    view1 = DetectionResult(objects=[
        DetectedObject(object_type=ObjectType.PLAYER, bbox=bbox, confidence=0.9),
        DetectedObject(object_type=ObjectType.BALL, bbox=bbox, confidence=0.95),
    ])
    view2 = DetectionResult(objects=[
        DetectedObject(object_type=ObjectType.PLAYER, bbox=bbox, confidence=0.85),
    ])
    fused_player = DetectedObject(object_type=ObjectType.PLAYER, bbox=bbox, confidence=0.92)

    mv = MultiViewDetectionResult(
        view_results={"cam_1": view1, "cam_2": view2},
        fused_objects=[fused_player],
    )
    assert mv.num_views == 2
    assert mv.total_detections == 3
    assert mv.num_fused_objects == 1
    assert mv.get_view_result("cam_1") is view1
    assert mv.get_view_result("cam_3") is None
    assert len(mv.get_fused_players()) == 1
    r.ok("MultiViewDetectionResult 뷰 결과")


# ==================== 8. mutable default 독립성 ====================
def test_mutable_default_independence(r: TestResult) -> None:
    """field(default_factory=...) 인스턴스 독립성"""
    from shared.dto.detection_dto import DetectedObject, DetectionResult
    a = DetectedObject()
    b = DetectedObject()
    a.attributes["key"] = "val"
    assert "key" not in b.attributes

    r1 = DetectionResult()
    r2 = DetectionResult()
    r1.objects.append(DetectedObject())
    assert len(r2.objects) == 0
    r.ok("mutable default 독립성")


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("detection_dto.py v2.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_import(r)
    test_all_exports(r)
    test_version(r)
    test_no_legacy_typing(r)
    test_i18n_module_cache(r)

    print("\n--- ObjectType ---")
    test_object_type_members(r)
    test_object_type_i18n(r)
    test_object_type_is_person(r)
    test_object_type_is_court_element(r)
    test_object_type_is_trackable(r)

    print("\n--- DetectionSource ---")
    test_detection_source_members(r)
    test_detection_source_i18n(r)
    test_detection_source_is_deep_learning(r)
    test_detection_source_is_pose_model(r)

    print("\n--- DetectedObject ---")
    test_detected_object_defaults(r)
    test_detected_object_confidence_clamp(r)
    test_detected_object_auto_position(r)
    test_detected_object_is_valid(r)
    test_detected_object_type_checks(r)
    test_detected_object_area(r)
    test_detected_object_attributes(r)
    test_detected_object_iou(r)
    test_detected_object_distance(r)

    print("\n--- DetectionConfig ---")
    test_detection_config_defaults(r)
    test_detection_config_threshold_clamp(r)
    test_detection_config_should_detect(r)
    test_detection_config_to_dict(r)

    print("\n--- DetectionResult ---")
    test_detection_result_defaults(r)
    test_detection_result_counts(r)
    test_detection_result_ball_detection(r)
    test_detection_result_average_confidence(r)
    test_detection_result_get_methods(r)

    print("\n--- MultiViewDetectionResult ---")
    test_multi_view_defaults(r)
    test_multi_view_with_views(r)

    print("\n--- 독립성 ---")
    test_mutable_default_independence(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
