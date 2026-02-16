# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_scene_dto.py

씬 DTO 유닛 테스트
- 모듈 구조 / __all__ / __version__
- SceneStatus Enum: 멤버, is_usable, is_complete, i18n
- ObjectCategory Enum: 멤버, is_person, is_static, is_dynamic, i18n
- SceneObject: 생성, __post_init__, property, distance_to
- CourtModel: 생성, __post_init__, bounds, is_in_court, is_in_three_point_range
- HoopModel: 생성, radius, distance_from
- Scene3D: 생성, players, get_object, get_team_players, get_nearest_player_to_ball
- SceneSnapshot: 생성, property
- SceneTimeline: 생성, get_snapshot_at_frame, get_object_trajectory
- SceneMetadata: 생성, aspect_ratio

Author: COURTVIEW AI Team
Version: 2.0.0
"""

import sys
from dataclasses import fields
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

    def near(self, name: str, actual: float, expected: float, tol: float = 1e-5) -> None:
        if abs(actual - expected) <= tol:
            self.ok(name)
        else:
            self.fail(name, f"expected ~{expected}, got {actual} (tol={tol})")

    def is_none(self, name: str, value) -> None:
        if value is None:
            self.ok(name)
        else:
            self.fail(name, f"expected None, got {value!r}")

    def not_none(self, name: str, value) -> None:
        if value is not None:
            self.ok(name)
        else:
            self.fail(name, "expected not None, got None")

    def isinstance_check(self, name: str, obj, cls) -> None:
        if isinstance(obj, cls):
            self.ok(name)
        else:
            self.fail(name, f"expected {cls.__name__}, got {type(obj).__name__}")

    def ge(self, name: str, actual, minimum) -> None:
        if actual >= minimum:
            self.ok(name)
        else:
            self.fail(name, f"{actual} < {minimum}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. 모듈 구조 ====================
def test_module_structure(r: TestResult) -> None:
    """모듈 기본 구조 검증"""
    import shared.dto.scene_dto as m

    r.true("__all__ 존재", hasattr(m, "__all__"))
    r.true("__version__ 존재", hasattr(m, "__version__"))
    r.eq("__version__", m.__version__, "2.0.0")
    r.eq("__all__ 길이", len(m.__all__), 9)

    expected = [
        "SceneStatus", "ObjectCategory",
        "SceneObject", "CourtModel", "HoopModel",
        "Scene3D", "SceneSnapshot", "SceneTimeline", "SceneMetadata",
    ]
    for name in expected:
        r.true(f"__all__에 {name} 포함", name in m.__all__)
        r.true(f"{name} getattr 가능", hasattr(m, name))


def test_no_legacy_typing(r: TestResult) -> None:
    """legacy typing 미사용 확인"""
    path = _PROJECT_ROOT / "shared" / "dto" / "scene_dto.py"
    content = path.read_text(encoding="utf-8")
    for legacy in ["Optional[", "List[", "Dict[", "Tuple["]:
        r.false(f"legacy typing '{legacy}' 미사용", legacy in content)


# ==================== 2. SceneStatus Enum ====================
def test_scene_status_enum(r: TestResult) -> None:
    """SceneStatus Enum 검증"""
    from shared.dto.scene_dto import SceneStatus
    import enum

    r.true("SceneStatus is Enum", issubclass(SceneStatus, enum.Enum))
    r.true("str Enum", issubclass(SceneStatus, str))

    members = ["COMPLETE", "PARTIAL", "UPDATING", "INITIALIZING", "ERROR"]
    for m in members:
        r.true(f"SceneStatus.{m} 존재", hasattr(SceneStatus, m))
    r.eq("SceneStatus 멤버 수", len(SceneStatus), 5)

    # is_usable
    r.true("COMPLETE.is_usable", SceneStatus.COMPLETE.is_usable)
    r.true("PARTIAL.is_usable", SceneStatus.PARTIAL.is_usable)
    r.false("UPDATING.is_usable", SceneStatus.UPDATING.is_usable)
    r.false("INITIALIZING.is_usable", SceneStatus.INITIALIZING.is_usable)
    r.false("ERROR.is_usable", SceneStatus.ERROR.is_usable)

    # is_complete
    r.true("COMPLETE.is_complete", SceneStatus.COMPLETE.is_complete)
    r.false("PARTIAL.is_complete", SceneStatus.PARTIAL.is_complete)

    # value
    r.eq("COMPLETE.value", SceneStatus.COMPLETE.value, "complete")
    r.eq("ERROR.value", SceneStatus.ERROR.value, "error")


def test_scene_status_i18n(r: TestResult) -> None:
    """SceneStatus i18n 다국어"""
    from shared.dto.scene_dto import SceneStatus
    from shared.constants.localization import SupportedLanguage

    # 한국어
    r.eq("COMPLETE KO", SceneStatus.COMPLETE.get_name(SupportedLanguage.KO), "완전")
    r.eq("ERROR KO", SceneStatus.ERROR.get_name(SupportedLanguage.KO), "오류")

    # 영어
    r.eq("COMPLETE EN", SceneStatus.COMPLETE.get_name(SupportedLanguage.EN), "Complete")
    r.eq("UPDATING EN", SceneStatus.UPDATING.get_name(SupportedLanguage.EN), "Updating")

    # 일본어
    r.eq("COMPLETE JA", SceneStatus.COMPLETE.get_name(SupportedLanguage.JA), "完全")

    # 중국어
    r.eq("COMPLETE ZH", SceneStatus.COMPLETE.get_name(SupportedLanguage.ZH), "完整")

    # 스페인어
    r.eq("COMPLETE ES", SceneStatus.COMPLETE.get_name(SupportedLanguage.ES), "Completo")

    # to_korean 하위 호환성
    r.eq("COMPLETE.to_korean", SceneStatus.COMPLETE.to_korean, "완전")


# ==================== 3. ObjectCategory Enum ====================
def test_object_category_enum(r: TestResult) -> None:
    """ObjectCategory Enum 검증"""
    from shared.dto.scene_dto import ObjectCategory
    import enum

    r.true("ObjectCategory is Enum", issubclass(ObjectCategory, enum.Enum))
    r.true("str Enum", issubclass(ObjectCategory, str))

    members = ["PLAYER", "REFEREE", "COACH", "BALL", "COURT", "HOOP", "BACKBOARD", "BENCH", "UNKNOWN"]
    for m in members:
        r.true(f"ObjectCategory.{m} 존재", hasattr(ObjectCategory, m))
    r.eq("ObjectCategory 멤버 수", len(ObjectCategory), 9)

    # is_person
    r.true("PLAYER.is_person", ObjectCategory.PLAYER.is_person)
    r.true("REFEREE.is_person", ObjectCategory.REFEREE.is_person)
    r.true("COACH.is_person", ObjectCategory.COACH.is_person)
    r.false("BALL.is_person", ObjectCategory.BALL.is_person)
    r.false("COURT.is_person", ObjectCategory.COURT.is_person)

    # is_static
    r.true("COURT.is_static", ObjectCategory.COURT.is_static)
    r.true("HOOP.is_static", ObjectCategory.HOOP.is_static)
    r.true("BACKBOARD.is_static", ObjectCategory.BACKBOARD.is_static)
    r.true("BENCH.is_static", ObjectCategory.BENCH.is_static)
    r.false("PLAYER.is_static", ObjectCategory.PLAYER.is_static)
    r.false("BALL.is_static", ObjectCategory.BALL.is_static)

    # is_dynamic
    r.true("PLAYER.is_dynamic", ObjectCategory.PLAYER.is_dynamic)
    r.true("BALL.is_dynamic", ObjectCategory.BALL.is_dynamic)
    r.false("COURT.is_dynamic", ObjectCategory.COURT.is_dynamic)

    # value
    r.eq("PLAYER.value", ObjectCategory.PLAYER.value, "player")
    r.eq("UNKNOWN.value", ObjectCategory.UNKNOWN.value, "unknown")


def test_object_category_i18n(r: TestResult) -> None:
    """ObjectCategory i18n 다국어"""
    from shared.dto.scene_dto import ObjectCategory
    from shared.constants.localization import SupportedLanguage

    # 한국어
    r.eq("PLAYER KO", ObjectCategory.PLAYER.get_name(SupportedLanguage.KO), "선수")
    r.eq("BALL KO", ObjectCategory.BALL.get_name(SupportedLanguage.KO), "공")
    r.eq("HOOP KO", ObjectCategory.HOOP.get_name(SupportedLanguage.KO), "골대")

    # 영어
    r.eq("PLAYER EN", ObjectCategory.PLAYER.get_name(SupportedLanguage.EN), "Player")
    r.eq("BALL EN", ObjectCategory.BALL.get_name(SupportedLanguage.EN), "Ball")

    # 일본어
    r.eq("PLAYER JA", ObjectCategory.PLAYER.get_name(SupportedLanguage.JA), "選手")

    # 중국어
    r.eq("PLAYER ZH", ObjectCategory.PLAYER.get_name(SupportedLanguage.ZH), "球员")

    # 스페인어
    r.eq("PLAYER ES", ObjectCategory.PLAYER.get_name(SupportedLanguage.ES), "Jugador")

    # to_korean 하위 호환성
    r.eq("PLAYER.to_korean", ObjectCategory.PLAYER.to_korean, "선수")


# ==================== 4. SceneObject ====================
def test_scene_object_creation(r: TestResult) -> None:
    """SceneObject 기본 생성"""
    from shared.dto.scene_dto import SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    obj = SceneObject(
        object_id=1,
        category=ObjectCategory.PLAYER,
        position=Point3D(5.0, 3.0, 0.0),
        confidence=0.95,
        track_id=101,
        team="HOME",
        jersey_number=23,
    )

    r.eq("object_id", obj.object_id, 1)
    r.eq("category", obj.category, ObjectCategory.PLAYER)
    r.not_none("position", obj.position)
    r.near("confidence", obj.confidence, 0.95)
    r.eq("track_id", obj.track_id, 101)
    r.eq("team", obj.team, "HOME")
    r.eq("jersey_number", obj.jersey_number, 23)
    r.eq("attributes 빈 dict", obj.attributes, {})


def test_scene_object_defaults(r: TestResult) -> None:
    """SceneObject 기본값"""
    from shared.dto.scene_dto import SceneObject, ObjectCategory

    obj = SceneObject()
    r.eq("object_id 기본 0", obj.object_id, 0)
    r.eq("category 기본 UNKNOWN", obj.category, ObjectCategory.UNKNOWN)
    r.is_none("position 기본 None", obj.position)
    r.is_none("velocity 기본 None", obj.velocity)
    r.is_none("orientation 기본 None", obj.orientation)
    r.is_none("bbox_3d 기본 None", obj.bbox_3d)
    r.near("confidence 기본 0", obj.confidence, 0.0)
    r.is_none("track_id 기본 None", obj.track_id)
    r.is_none("team 기본 None", obj.team)
    r.is_none("jersey_number 기본 None", obj.jersey_number)


def test_scene_object_post_init(r: TestResult) -> None:
    """SceneObject __post_init__ confidence clamp"""
    from shared.dto.scene_dto import SceneObject

    obj1 = SceneObject(confidence=1.5)
    r.near("confidence clamp max", obj1.confidence, 1.0)

    obj2 = SceneObject(confidence=-0.3)
    r.near("confidence clamp min", obj2.confidence, 0.0)

    obj3 = SceneObject(confidence=0.75)
    r.near("confidence 유지", obj3.confidence, 0.75)


def test_scene_object_properties(r: TestResult) -> None:
    """SceneObject 프로퍼티"""
    from shared.dto.scene_dto import SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    # 유효한 선수 객체
    player = SceneObject(
        category=ObjectCategory.PLAYER,
        position=Point3D(1, 2, 0),
        velocity=(3.0, 4.0, 0.0),
    )
    r.true("is_valid (position 있음)", player.is_valid)
    r.true("is_person", player.is_person)
    r.true("is_player", player.is_player)
    r.false("is_ball", player.is_ball)
    r.true("has_velocity", player.has_velocity)
    r.near("speed 5.0", player.speed, 5.0, tol=1e-4)

    # 공 객체
    ball = SceneObject(category=ObjectCategory.BALL)
    r.false("ball is_player", ball.is_player)
    r.true("ball is_ball", ball.is_ball)
    r.false("ball is_valid (no position)", ball.is_valid)
    r.false("ball has_velocity", ball.has_velocity)
    r.is_none("ball speed None", ball.speed)


def test_scene_object_distance_to(r: TestResult) -> None:
    """SceneObject distance_to"""
    from shared.dto.scene_dto import SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    obj1 = SceneObject(position=Point3D(0, 0, 0))
    obj2 = SceneObject(position=Point3D(3, 4, 0))
    dist = obj1.distance_to(obj2)
    r.not_none("distance_to 결과", dist)
    r.near("distance 5.0", dist, 5.0, tol=1e-4)

    # position 없는 경우
    obj3 = SceneObject()
    r.is_none("distance_to None (no position)", obj1.distance_to(obj3))
    r.is_none("distance_to None (both no position)", obj3.distance_to(obj3))


# ==================== 5. CourtModel ====================
def test_court_model_creation(r: TestResult) -> None:
    """CourtModel 기본 생성"""
    from shared.dto.scene_dto import CourtModel

    court = CourtModel()
    r.near("length 28.0", court.length, 28.0)
    r.near("width 15.0", court.width, 15.0)
    r.near("half_court_line 14.0", court.half_court_line, 14.0)
    r.near("three_point_distance 6.75", court.three_point_distance, 6.75)
    r.near("free_throw_distance 4.6", court.free_throw_distance, 4.6)
    r.near("key_width 4.9", court.key_width, 4.9)
    r.eq("markings 빈 dict", court.markings, {})


def test_court_model_area(r: TestResult) -> None:
    """CourtModel area"""
    from shared.dto.scene_dto import CourtModel

    court = CourtModel()
    r.near("area 420.0", court.area, 420.0)


def test_court_model_bounds(r: TestResult) -> None:
    """CourtModel bounds"""
    from shared.dto.scene_dto import CourtModel

    court = CourtModel()
    min_x, min_y, max_x, max_y = court.bounds
    r.near("min_x -14.0", min_x, -14.0)
    r.near("min_y -7.5", min_y, -7.5)
    r.near("max_x 14.0", max_x, 14.0)
    r.near("max_y 7.5", max_y, 7.5)


def test_court_model_is_in_court(r: TestResult) -> None:
    """CourtModel is_in_court"""
    from shared.dto.scene_dto import CourtModel
    from shared.dto.geometry_dto import Point3D

    court = CourtModel()
    r.true("중심 in court", court.is_in_court(Point3D(0, 0, 0)))
    r.true("코너 in court", court.is_in_court(Point3D(13.9, 7.4, 0)))
    r.false("밖 not in court", court.is_in_court(Point3D(15.0, 0, 0)))
    r.false("밖 not in court Y", court.is_in_court(Point3D(0, 8.0, 0)))


def test_court_model_three_point(r: TestResult) -> None:
    """CourtModel is_in_three_point_range"""
    from shared.dto.scene_dto import CourtModel
    from shared.dto.geometry_dto import Point3D

    court = CourtModel()
    hoop = Point3D(14.0, 0, 3.05)

    # 3점 거리 밖 (7m)
    far = Point3D(7.0, 0, 0)
    r.true("7m 거리 → 3점 범위", court.is_in_three_point_range(far, hoop))

    # 3점 거리 안 (4m)
    close = Point3D(10.0, 0, 0)
    r.false("4m 거리 → 2점 범위", court.is_in_three_point_range(close, hoop))


# ==================== 6. HoopModel ====================
def test_hoop_model_creation(r: TestResult) -> None:
    """HoopModel 기본 생성"""
    from shared.dto.scene_dto import HoopModel

    hoop = HoopModel()
    r.near("height 3.05", hoop.height, 3.05)
    r.near("diameter 0.45", hoop.diameter, 0.45)
    r.near("radius 0.225", hoop.radius, 0.225)
    r.near("backboard_width 1.8", hoop.backboard_width, 1.8)
    r.near("backboard_height 1.05", hoop.backboard_height, 1.05)
    r.true("is_left_side 기본 True", hoop.is_left_side)
    r.is_none("backboard_position 기본 None", hoop.backboard_position)


def test_hoop_model_distance(r: TestResult) -> None:
    """HoopModel distance_from"""
    from shared.dto.scene_dto import HoopModel
    from shared.dto.geometry_dto import Point3D

    hoop = HoopModel(position=Point3D(14.0, 0, 3.05))
    dist = hoop.distance_from(Point3D(8.0, 0, 0))
    r.near("distance 6.0", dist, 6.0, tol=1e-4)


def test_hoop_model_rim_center(r: TestResult) -> None:
    """HoopModel rim_center"""
    from shared.dto.scene_dto import HoopModel
    from shared.dto.geometry_dto import Point3D

    pos = Point3D(14.0, 0, 3.05)
    hoop = HoopModel(position=pos)
    r.eq("rim_center == position", hoop.rim_center, pos)


# ==================== 7. Scene3D ====================
def test_scene3d_creation(r: TestResult) -> None:
    """Scene3D 기본 생성"""
    from shared.dto.scene_dto import Scene3D, SceneStatus
    from uuid import UUID

    scene = Scene3D()
    r.isinstance_check("scene_id UUID", scene.scene_id, UUID)
    r.eq("status 기본 PARTIAL", scene.status, SceneStatus.PARTIAL)
    r.eq("objects 빈 리스트", scene.objects, [])
    r.is_none("court 기본 None", scene.court)
    r.eq("hoops 빈 리스트", scene.hoops, [])
    r.is_none("ball 기본 None", scene.ball)
    r.eq("frame_index 기본 0", scene.frame_index, 0)
    r.eq("camera_count 기본 0", scene.camera_count, 0)
    r.near("confidence 기본 0", scene.confidence, 0.0)


def test_scene3d_post_init(r: TestResult) -> None:
    """Scene3D __post_init__ confidence clamp"""
    from shared.dto.scene_dto import Scene3D

    scene = Scene3D(confidence=1.5)
    r.near("confidence clamp max", scene.confidence, 1.0)


def test_scene3d_properties(r: TestResult) -> None:
    """Scene3D 프로퍼티"""
    from shared.dto.scene_dto import Scene3D, SceneObject, ObjectCategory, SceneStatus
    from shared.dto.geometry_dto import Point3D

    ball = SceneObject(object_id=100, category=ObjectCategory.BALL, position=Point3D(5, 3, 1))
    players = [
        SceneObject(object_id=1, category=ObjectCategory.PLAYER, position=Point3D(4, 3, 0), team="HOME"),
        SceneObject(object_id=2, category=ObjectCategory.PLAYER, position=Point3D(8, 5, 0), team="AWAY"),
        SceneObject(object_id=3, category=ObjectCategory.REFEREE, position=Point3D(7, 0, 0)),
    ]

    scene = Scene3D(
        status=SceneStatus.COMPLETE,
        objects=players,
        ball=ball,
        confidence=0.9,
    )

    r.eq("num_objects 3", scene.num_objects, 3)
    r.eq("num_players 2", scene.num_players, 2)
    r.true("has_ball", scene.has_ball)
    r.true("is_complete", scene.is_complete)


def test_scene3d_get_object(r: TestResult) -> None:
    """Scene3D get_object"""
    from shared.dto.scene_dto import Scene3D, SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    objects = [
        SceneObject(object_id=10, category=ObjectCategory.PLAYER, position=Point3D(1, 1, 0)),
        SceneObject(object_id=20, category=ObjectCategory.BALL, position=Point3D(5, 5, 1)),
    ]
    scene = Scene3D(objects=objects)

    found = scene.get_object(10)
    r.not_none("get_object(10)", found)
    r.eq("found.object_id", found.object_id, 10)
    r.is_none("get_object(99) None", scene.get_object(99))


def test_scene3d_get_objects_by_category(r: TestResult) -> None:
    """Scene3D get_objects_by_category"""
    from shared.dto.scene_dto import Scene3D, SceneObject, ObjectCategory

    objects = [
        SceneObject(object_id=1, category=ObjectCategory.PLAYER),
        SceneObject(object_id=2, category=ObjectCategory.PLAYER),
        SceneObject(object_id=3, category=ObjectCategory.REFEREE),
    ]
    scene = Scene3D(objects=objects)

    players = scene.get_objects_by_category(ObjectCategory.PLAYER)
    r.eq("players 수", len(players), 2)
    refs = scene.get_objects_by_category(ObjectCategory.REFEREE)
    r.eq("referee 수", len(refs), 1)
    coaches = scene.get_objects_by_category(ObjectCategory.COACH)
    r.eq("coach 수", len(coaches), 0)


def test_scene3d_get_team_players(r: TestResult) -> None:
    """Scene3D get_team_players"""
    from shared.dto.scene_dto import Scene3D, SceneObject, ObjectCategory

    objects = [
        SceneObject(object_id=1, category=ObjectCategory.PLAYER, team="HOME"),
        SceneObject(object_id=2, category=ObjectCategory.PLAYER, team="HOME"),
        SceneObject(object_id=3, category=ObjectCategory.PLAYER, team="AWAY"),
    ]
    scene = Scene3D(objects=objects)

    home = scene.get_team_players("HOME")
    r.eq("HOME 선수 2", len(home), 2)
    away = scene.get_team_players("AWAY")
    r.eq("AWAY 선수 1", len(away), 1)
    r.eq("NONE 팀 0", len(scene.get_team_players("NONE")), 0)


def test_scene3d_nearest_player_to_ball(r: TestResult) -> None:
    """Scene3D get_nearest_player_to_ball"""
    from shared.dto.scene_dto import Scene3D, SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    ball = SceneObject(object_id=100, category=ObjectCategory.BALL, position=Point3D(5, 3, 1))
    objects = [
        SceneObject(object_id=1, category=ObjectCategory.PLAYER, position=Point3D(4, 3, 0)),  # 가까움
        SceneObject(object_id=2, category=ObjectCategory.PLAYER, position=Point3D(10, 8, 0)),  # 멀음
    ]
    scene = Scene3D(objects=objects, ball=ball)

    nearest = scene.get_nearest_player_to_ball()
    r.not_none("nearest 존재", nearest)
    r.eq("nearest.object_id", nearest.object_id, 1)

    # 공 없는 경우
    scene_no_ball = Scene3D(objects=objects)
    r.is_none("공 없으면 None", scene_no_ball.get_nearest_player_to_ball())

    # 선수 없는 경우
    scene_no_players = Scene3D(ball=ball)
    r.is_none("선수 없으면 None", scene_no_players.get_nearest_player_to_ball())


# ==================== 8. SceneSnapshot ====================
def test_scene_snapshot(r: TestResult) -> None:
    """SceneSnapshot 기본 생성 및 프로퍼티"""
    from shared.dto.scene_dto import SceneSnapshot, Scene3D, SceneObject, ObjectCategory

    objects = [SceneObject(category=ObjectCategory.PLAYER)]
    scene = Scene3D(objects=objects, ball=SceneObject(category=ObjectCategory.BALL))

    snapshot = SceneSnapshot(
        scene=scene,
        frame_index=100,
        timestamp=3.33,
        processing_time_ms=12.5,
    )

    r.eq("frame_index", snapshot.frame_index, 100)
    r.near("timestamp", snapshot.timestamp, 3.33)
    r.near("processing_time_ms", snapshot.processing_time_ms, 12.5)
    r.eq("num_objects", snapshot.num_objects, 1)
    r.true("has_ball", snapshot.has_ball)


def test_scene_snapshot_defaults(r: TestResult) -> None:
    """SceneSnapshot 기본값"""
    from shared.dto.scene_dto import SceneSnapshot

    snap = SceneSnapshot()
    r.eq("frame_index 기본 0", snap.frame_index, 0)
    r.near("timestamp 기본 0", snap.timestamp, 0.0)
    r.near("processing_time_ms 기본 0", snap.processing_time_ms, 0.0)
    r.eq("num_objects 기본 0", snap.num_objects, 0)
    r.false("has_ball 기본 False", snap.has_ball)


# ==================== 9. SceneTimeline ====================
def test_scene_timeline_creation(r: TestResult) -> None:
    """SceneTimeline 기본 생성"""
    from shared.dto.scene_dto import SceneTimeline
    from uuid import UUID

    tl = SceneTimeline(start_frame=0, end_frame=299, fps=30.0)
    r.isinstance_check("timeline_id UUID", tl.timeline_id, UUID)
    r.eq("start_frame", tl.start_frame, 0)
    r.eq("end_frame", tl.end_frame, 299)
    r.near("fps", tl.fps, 30.0)
    r.eq("num_snapshots 0", tl.num_snapshots, 0)
    r.eq("frame_count 300", tl.frame_count, 300)


def test_scene_timeline_get_snapshot(r: TestResult) -> None:
    """SceneTimeline get_snapshot_at_frame"""
    from shared.dto.scene_dto import SceneTimeline, SceneSnapshot

    snapshots = [
        SceneSnapshot(frame_index=0),
        SceneSnapshot(frame_index=30),
        SceneSnapshot(frame_index=60),
    ]
    tl = SceneTimeline(snapshots=snapshots)

    found = tl.get_snapshot_at_frame(30)
    r.not_none("get_snapshot_at_frame(30)", found)
    r.eq("found.frame_index", found.frame_index, 30)
    r.is_none("get_snapshot_at_frame(15) None", tl.get_snapshot_at_frame(15))


def test_scene_timeline_trajectory(r: TestResult) -> None:
    """SceneTimeline get_object_trajectory"""
    from shared.dto.scene_dto import SceneTimeline, SceneSnapshot, Scene3D, SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    snapshots = []
    for i in range(5):
        obj = SceneObject(object_id=1, category=ObjectCategory.PLAYER, position=Point3D(float(i), float(i), 0))
        scene = Scene3D(objects=[obj])
        snapshots.append(SceneSnapshot(scene=scene, frame_index=i * 30))

    tl = SceneTimeline(snapshots=snapshots)
    trajectory = tl.get_object_trajectory(1)
    r.eq("trajectory 길이 5", len(trajectory), 5)
    r.near("trajectory[0].x", trajectory[0].x, 0.0)
    r.near("trajectory[4].x", trajectory[4].x, 4.0)

    # 없는 객체
    empty = tl.get_object_trajectory(99)
    r.eq("없는 객체 trajectory 빈 리스트", len(empty), 0)


# ==================== 10. SceneMetadata ====================
def test_scene_metadata(r: TestResult) -> None:
    """SceneMetadata 기본 생성 및 프로퍼티"""
    from shared.dto.scene_dto import SceneMetadata

    meta = SceneMetadata()
    r.eq("camera_count 기본 0", meta.camera_count, 0)
    r.near("fps 기본 30.0", meta.fps, 30.0)
    r.eq("resolution 기본 (1920, 1080)", meta.resolution, (1920, 1080))
    r.near("calibration_quality 기본 0", meta.calibration_quality, 0.0)
    r.eq("fusion_method 기본", meta.fusion_method, "triangulation")
    r.not_none("created_at 자동", meta.created_at)
    r.near("aspect_ratio 16:9", meta.aspect_ratio, 1920 / 1080, tol=1e-4)


def test_scene_metadata_aspect_ratio(r: TestResult) -> None:
    """SceneMetadata aspect_ratio 엣지 케이스"""
    from shared.dto.scene_dto import SceneMetadata

    # 4:3
    meta43 = SceneMetadata(resolution=(1024, 768))
    r.near("4:3 aspect_ratio", meta43.aspect_ratio, 1024 / 768, tol=1e-4)

    # height 0 → 0.0
    meta0 = SceneMetadata(resolution=(1920, 0))
    r.near("height 0 → aspect 0", meta0.aspect_ratio, 0.0)


# ==================== 11. dataclass 필드 ====================
def test_dataclass_fields(r: TestResult) -> None:
    """dataclass 필드 수 확인"""
    from shared.dto.scene_dto import (
        SceneObject, CourtModel, HoopModel,
        Scene3D, SceneSnapshot, SceneTimeline, SceneMetadata,
    )

    r.eq("SceneObject 필드 수", len(fields(SceneObject)), 11)
    r.eq("CourtModel 필드 수", len(fields(CourtModel)), 9)
    r.eq("HoopModel 필드 수", len(fields(HoopModel)), 8)
    r.eq("Scene3D 필드 수", len(fields(Scene3D)), 10)
    r.eq("SceneSnapshot 필드 수", len(fields(SceneSnapshot)), 4)
    r.eq("SceneTimeline 필드 수", len(fields(SceneTimeline)), 6)
    r.eq("SceneMetadata 필드 수", len(fields(SceneMetadata)), 7)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("scene_dto.py v2.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)
    test_no_legacy_typing(r)

    print("\n--- SceneStatus Enum ---")
    test_scene_status_enum(r)
    test_scene_status_i18n(r)

    print("\n--- ObjectCategory Enum ---")
    test_object_category_enum(r)
    test_object_category_i18n(r)

    print("\n--- SceneObject ---")
    test_scene_object_creation(r)
    test_scene_object_defaults(r)
    test_scene_object_post_init(r)
    test_scene_object_properties(r)
    test_scene_object_distance_to(r)

    print("\n--- CourtModel ---")
    test_court_model_creation(r)
    test_court_model_area(r)
    test_court_model_bounds(r)
    test_court_model_is_in_court(r)
    test_court_model_three_point(r)

    print("\n--- HoopModel ---")
    test_hoop_model_creation(r)
    test_hoop_model_distance(r)
    test_hoop_model_rim_center(r)

    print("\n--- Scene3D ---")
    test_scene3d_creation(r)
    test_scene3d_post_init(r)
    test_scene3d_properties(r)
    test_scene3d_get_object(r)
    test_scene3d_get_objects_by_category(r)
    test_scene3d_get_team_players(r)
    test_scene3d_nearest_player_to_ball(r)

    print("\n--- SceneSnapshot ---")
    test_scene_snapshot(r)
    test_scene_snapshot_defaults(r)

    print("\n--- SceneTimeline ---")
    test_scene_timeline_creation(r)
    test_scene_timeline_get_snapshot(r)
    test_scene_timeline_trajectory(r)

    print("\n--- SceneMetadata ---")
    test_scene_metadata(r)
    test_scene_metadata_aspect_ratio(r)

    print("\n--- dataclass 필드 ---")
    test_dataclass_fields(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
