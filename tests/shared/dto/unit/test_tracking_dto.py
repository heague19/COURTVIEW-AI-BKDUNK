# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_tracking_dto.py

객체 추적 DTO 유닛 테스트
- 모듈 구조 (__all__, __version__, legacy typing 미사용)
- Enum 3종: TrackState, TrackSource, TrackedObjectType (i18n 5언어)
- dataclass 6종: TrackHistory, KalmanState, Track, TrackAssociation,
                 TrackingResult, MultiViewTrackingResult
- property, 메서드, __post_init__
- mutable default 격리

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

    def is_none(self, name: str, value) -> None:
        if value is None:
            self.ok(name)
        else:
            self.fail(name, f"expected None, got {value!r}")

    def is_not_none(self, name: str, value) -> None:
        if value is not None:
            self.ok(name)
        else:
            self.fail(name, "expected not None")

    def is_instance(self, name: str, obj, cls) -> None:
        if isinstance(obj, cls):
            self.ok(name)
        else:
            self.fail(name, f"expected {cls.__name__}, got {type(obj).__name__}")

    def approx(self, name: str, actual: float, expected: float, tol: float = 1e-6) -> None:
        if abs(actual - expected) < tol:
            self.ok(name)
        else:
            self.fail(name, f"expected ~{expected}, got {actual}")

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
    """__all__, __version__, legacy typing 검증"""
    import shared.dto.tracking_dto as m

    r.true("__all__ 존재", hasattr(m, "__all__"))
    r.true("__version__ 존재", hasattr(m, "__version__"))
    r.eq("__version__", m.__version__, "1.1.0")
    r.eq("__all__ 길이", len(m.__all__), 10)

    expected = [
        "SupportedLanguage",
        "TrackState", "TrackSource", "TrackedObjectType",
        "Track", "TrackHistory", "TrackingResult", "TrackAssociation",
        "KalmanState", "MultiViewTrackingResult",
    ]
    for name in expected:
        r.true(f"__all__에 {name} 포함", name in m.__all__)
        r.true(f"{name} getattr 가능", hasattr(m, name))

    import inspect
    src = inspect.getsource(m)
    r.false("legacy 'Optional[' 미사용", "Optional[" in src)
    r.false("legacy 'List[' 미사용", "List[" in src)
    r.false("legacy 'Dict[' 미사용", "Dict[" in src)
    r.false("legacy 'Tuple[' 미사용", "Tuple[" in src)


# ==================== 2. TrackState Enum ====================
def test_track_state(r: TestResult) -> None:
    """TrackState 열거형 (5멤버, is_active, is_visible, i18n)"""
    from shared.dto.tracking_dto import TrackState
    from shared.constants.localization import SupportedLanguage

    members = list(TrackState)
    r.eq("TrackState 멤버 수", len(members), 5)

    # value
    r.eq("TENTATIVE value", TrackState.TENTATIVE.value, "tentative")
    r.eq("CONFIRMED value", TrackState.CONFIRMED.value, "confirmed")
    r.eq("LOST value", TrackState.LOST.value, "lost")
    r.eq("DELETED value", TrackState.DELETED.value, "deleted")
    r.eq("OCCLUDED value", TrackState.OCCLUDED.value, "occluded")

    # is_active
    r.true("TENTATIVE is_active", TrackState.TENTATIVE.is_active)
    r.true("CONFIRMED is_active", TrackState.CONFIRMED.is_active)
    r.false("LOST is_active", TrackState.LOST.is_active)
    r.false("DELETED is_active", TrackState.DELETED.is_active)
    r.true("OCCLUDED is_active", TrackState.OCCLUDED.is_active)

    # is_visible
    r.true("TENTATIVE is_visible", TrackState.TENTATIVE.is_visible)
    r.true("CONFIRMED is_visible", TrackState.CONFIRMED.is_visible)
    r.false("LOST is_visible", TrackState.LOST.is_visible)
    r.false("OCCLUDED is_visible", TrackState.OCCLUDED.is_visible)

    # i18n (5언어)
    r.eq("CONFIRMED KO", TrackState.CONFIRMED.get_name(SupportedLanguage.KO), "확정")
    r.eq("CONFIRMED EN", TrackState.CONFIRMED.get_name(SupportedLanguage.EN), "Confirmed")
    r.eq("CONFIRMED JA", TrackState.CONFIRMED.get_name(SupportedLanguage.JA), "確定")
    r.eq("CONFIRMED ZH", TrackState.CONFIRMED.get_name(SupportedLanguage.ZH), "已确认")
    r.eq("CONFIRMED ES", TrackState.CONFIRMED.get_name(SupportedLanguage.ES), "Confirmado")

    # to_korean
    r.eq("LOST to_korean", TrackState.LOST.to_korean(), "추적 중단")
    r.eq("OCCLUDED to_korean", TrackState.OCCLUDED.to_korean(), "가려짐")

    # str 서브클래스
    r.is_instance("str 서브클래스", TrackState.TENTATIVE, str)


# ==================== 3. TrackSource Enum ====================
def test_track_source(r: TestResult) -> None:
    """TrackSource 열거형 (5멤버, i18n)"""
    from shared.dto.tracking_dto import TrackSource
    from shared.constants.localization import SupportedLanguage

    members = list(TrackSource)
    r.eq("TrackSource 멤버 수", len(members), 5)

    r.eq("SINGLE_VIEW value", TrackSource.SINGLE_VIEW.value, "single_view")
    r.eq("MULTI_VIEW value", TrackSource.MULTI_VIEW.value, "multi_view")
    r.eq("RECOVERED value", TrackSource.RECOVERED.value, "recovered")
    r.eq("INTERPOLATED value", TrackSource.INTERPOLATED.value, "interpolated")
    r.eq("MANUAL value", TrackSource.MANUAL.value, "manual")

    # i18n
    r.eq("MULTI_VIEW KO", TrackSource.MULTI_VIEW.get_name(SupportedLanguage.KO), "멀티뷰")
    r.eq("MULTI_VIEW EN", TrackSource.MULTI_VIEW.get_name(SupportedLanguage.EN), "Multi-View")
    r.eq("RECOVERED JA", TrackSource.RECOVERED.get_name(SupportedLanguage.JA), "復旧")
    r.eq("INTERPOLATED ZH", TrackSource.INTERPOLATED.get_name(SupportedLanguage.ZH), "插值")
    r.eq("MANUAL ES", TrackSource.MANUAL.get_name(SupportedLanguage.ES), "Manual")

    r.eq("SINGLE_VIEW to_korean", TrackSource.SINGLE_VIEW.to_korean(), "단일 뷰")


# ==================== 4. TrackedObjectType Enum ====================
def test_tracked_object_type(r: TestResult) -> None:
    """TrackedObjectType 열거형 (5멤버, i18n)"""
    from shared.dto.tracking_dto import TrackedObjectType
    from shared.constants.localization import SupportedLanguage

    members = list(TrackedObjectType)
    r.eq("TrackedObjectType 멤버 수", len(members), 5)

    r.eq("PLAYER value", TrackedObjectType.PLAYER.value, "player")
    r.eq("BALL value", TrackedObjectType.BALL.value, "ball")
    r.eq("REFEREE value", TrackedObjectType.REFEREE.value, "referee")
    r.eq("COACH value", TrackedObjectType.COACH.value, "coach")
    r.eq("UNKNOWN value", TrackedObjectType.UNKNOWN.value, "unknown")

    # i18n
    r.eq("PLAYER KO", TrackedObjectType.PLAYER.get_name(SupportedLanguage.KO), "선수")
    r.eq("PLAYER EN", TrackedObjectType.PLAYER.get_name(SupportedLanguage.EN), "Player")
    r.eq("BALL JA", TrackedObjectType.BALL.get_name(SupportedLanguage.JA), "ボール")
    r.eq("REFEREE ZH", TrackedObjectType.REFEREE.get_name(SupportedLanguage.ZH), "裁判")
    r.eq("COACH ES", TrackedObjectType.COACH.get_name(SupportedLanguage.ES), "Entrenador")

    r.eq("UNKNOWN to_korean", TrackedObjectType.UNKNOWN.to_korean(), "미확인")


# ==================== 5. TrackHistory ====================
def test_track_history_defaults(r: TestResult) -> None:
    """TrackHistory 기본값"""
    from shared.dto.tracking_dto import TrackHistory

    th = TrackHistory()
    r.eq("positions 빈", th.positions, [])
    r.eq("positions_3d 빈", th.positions_3d, [])
    r.eq("timestamps 빈", th.timestamps, [])
    r.eq("bboxes 빈", th.bboxes, [])
    r.eq("confidences 빈", th.confidences, [])
    r.eq("length 0", th.length, 0)
    r.approx("duration 0", th.duration, 0.0)
    r.is_none("last_position None", th.last_position)
    r.is_none("last_position_3d None", th.last_position_3d)
    r.is_none("last_bbox None", th.last_bbox)
    r.approx("average_confidence 0", th.average_confidence, 0.0)


def test_track_history_add_entry(r: TestResult) -> None:
    """TrackHistory add_entry + properties"""
    from shared.dto.tracking_dto import TrackHistory
    from shared.dto.geometry_dto import Point2D, Point3D, BoundingBox

    th = TrackHistory()
    p1 = Point2D(10.0, 20.0)
    p2 = Point2D(15.0, 25.0)
    p3d = Point3D(1.0, 2.0, 0.0)
    bb = BoundingBox(x=5.0, y=10.0, width=20.0, height=40.0)

    th.add_entry(position=p1, timestamp=0.0, confidence=0.9)
    th.add_entry(position=p2, timestamp=0.5, bbox=bb, confidence=0.95, position_3d=p3d)

    r.eq("length 2", th.length, 2)
    r.approx("duration 0.5", th.duration, 0.5)
    r.eq("last_position", th.last_position, p2)
    r.eq("last_position_3d", th.last_position_3d, p3d)
    r.eq("last_bbox", th.last_bbox, bb)
    r.approx("average_confidence", th.average_confidence, 0.925)
    r.eq("positions_3d 길이 1", len(th.positions_3d), 1)
    r.eq("bboxes 길이 1", len(th.bboxes), 1)


def test_track_history_trim(r: TestResult) -> None:
    """TrackHistory trim"""
    from shared.dto.tracking_dto import TrackHistory
    from shared.dto.geometry_dto import Point2D

    th = TrackHistory()
    for i in range(10):
        th.add_entry(position=Point2D(float(i), 0.0), timestamp=float(i) * 0.1, confidence=0.9)

    r.eq("trim 전 length 10", th.length, 10)
    th.trim(5)
    r.eq("trim 후 length 5", th.length, 5)
    r.approx("trim 후 첫 타임스탬프", th.timestamps[0], 0.5)


def test_track_history_to_trajectory_3d(r: TestResult) -> None:
    """TrackHistory to_trajectory_3d"""
    from shared.dto.tracking_dto import TrackHistory
    from shared.dto.geometry_dto import Point2D, Point3D, Trajectory3D

    th = TrackHistory()
    for i in range(3):
        th.add_entry(
            position=Point2D(float(i), 0.0),
            timestamp=float(i) * 0.1,
            position_3d=Point3D(float(i), 0.0, 0.0),
        )

    traj = th.to_trajectory_3d()
    r.is_instance("Trajectory3D 타입", traj, Trajectory3D)
    r.eq("trajectory points 수", len(traj.points), 3)


# ==================== 6. KalmanState ====================
def test_kalman_state(r: TestResult) -> None:
    """KalmanState dataclass + numpy"""
    import numpy as np
    from shared.dto.tracking_dto import KalmanState
    from shared.dto.geometry_dto import BoundingBox

    ks = KalmanState()
    r.eq("state_dim 기본", ks.state_dim, 8)
    r.eq("measurement_dim 기본", ks.measurement_dim, 4)
    r.eq("mean shape", ks.mean.shape, (8,))
    r.eq("covariance shape", ks.covariance.shape, (8, 8))

    # position, size, velocity
    r.eq("position 기본 (0,0)", ks.position, (0.0, 0.0))
    r.eq("size 기본 (0,0)", ks.size, (0.0, 0.0))
    r.eq("velocity 기본 (0,0)", ks.velocity, (0.0, 0.0))
    r.true("position_uncertainty >= 0", ks.position_uncertainty >= 0.0)

    # 커스텀 상태
    mean = np.array([10.0, 20.0, 0.5, 40.0, 2.0, -1.0, 0.0, 0.0], dtype=np.float64)
    ks2 = KalmanState(mean=mean)
    r.approx("position x", ks2.position[0], 10.0)
    r.approx("position y", ks2.position[1], 20.0)
    r.approx("size a", ks2.size[0], 0.5)
    r.approx("size h", ks2.size[1], 40.0)
    r.approx("velocity vx", ks2.velocity[0], 2.0)
    r.approx("velocity vy", ks2.velocity[1], -1.0)

    # to_bbox
    bbox = ks2.to_bbox()
    r.is_instance("to_bbox BoundingBox", bbox, BoundingBox)
    r.true("bbox width > 0", bbox.width > 0)
    r.true("bbox height > 0", bbox.height > 0)


# ==================== 7. Track ====================
def test_track_defaults(r: TestResult) -> None:
    """Track 기본값"""
    from shared.dto.tracking_dto import Track, TrackState, TrackSource, TrackedObjectType, TrackHistory

    t = Track()
    r.eq("track_id 기본", t.track_id, 0)
    r.eq("state 기본", t.state, TrackState.TENTATIVE)
    r.eq("object_type 기본", t.object_type, TrackedObjectType.UNKNOWN)
    r.is_none("bbox 기본 None", t.bbox)
    r.is_none("position 기본 None", t.position)
    r.is_none("position_3d 기본 None", t.position_3d)
    r.approx("confidence 기본", t.confidence, 1.0)
    r.eq("source 기본", t.source, TrackSource.SINGLE_VIEW)
    r.is_instance("history TrackHistory", t.history, TrackHistory)
    r.is_none("kalman_state 기본 None", t.kalman_state)
    r.eq("age 기본", t.age, 0)
    r.eq("hits 기본", t.hits, 0)
    r.eq("time_since_update 기본", t.time_since_update, 0)
    r.eq("attributes 빈 dict", t.attributes, {})


def test_track_post_init(r: TestResult) -> None:
    """Track __post_init__: bbox → position 자동 설정"""
    from shared.dto.tracking_dto import Track
    from shared.dto.geometry_dto import BoundingBox

    bb = BoundingBox(x=10.0, y=20.0, width=30.0, height=40.0)
    t = Track(bbox=bb)
    r.is_not_none("position 자동 설정", t.position)
    r.approx("position.x = center_x", t.position.x, 25.0)
    r.approx("position.y = center_y", t.position.y, 40.0)


def test_track_properties(r: TestResult) -> None:
    """Track properties (is_confirmed, is_active, is_lost, velocity, jersey_number, team)"""
    from shared.dto.tracking_dto import Track, TrackState, KalmanState
    import numpy as np

    # CONFIRMED
    t1 = Track(state=TrackState.CONFIRMED)
    r.true("is_confirmed", t1.is_confirmed)
    r.true("CONFIRMED is_active", t1.is_active)
    r.false("CONFIRMED is_lost", t1.is_lost)

    # LOST
    t2 = Track(state=TrackState.LOST)
    r.false("LOST is_confirmed", t2.is_confirmed)
    r.false("LOST is_active", t2.is_active)
    r.true("LOST is_lost", t2.is_lost)

    # DELETED
    t3 = Track(state=TrackState.DELETED)
    r.true("DELETED is_lost", t3.is_lost)

    # velocity from kalman
    mean = np.array([0, 0, 0, 0, 3.0, 4.0, 0, 0], dtype=np.float64)
    ks = KalmanState(mean=mean)
    t4 = Track(kalman_state=ks)
    vel = t4.velocity
    r.is_not_none("velocity from kalman", vel)
    r.approx("velocity vx", vel[0], 3.0)
    r.approx("velocity vy", vel[1], 4.0)

    # velocity None (no kalman)
    t5 = Track()
    r.is_none("velocity None (no kalman)", t5.velocity)

    # jersey_number, team
    t6 = Track(attributes={"jersey_number": 23, "team": "HOME"})
    r.eq("jersey_number", t6.jersey_number, 23)
    r.eq("team", t6.team, "HOME")

    t7 = Track()
    r.is_none("jersey_number None", t7.jersey_number)
    r.is_none("team None", t7.team)


def test_track_update(r: TestResult) -> None:
    """Track update 메서드"""
    from shared.dto.tracking_dto import Track, TrackState
    from shared.dto.geometry_dto import BoundingBox, Point3D

    t = Track(track_id=1, state=TrackState.CONFIRMED)
    bb = BoundingBox(x=100.0, y=200.0, width=50.0, height=80.0)
    p3d = Point3D(5.0, 3.0, 0.0)

    t.update(bbox=bb, confidence=0.92, timestamp=1.5, position_3d=p3d)

    r.eq("bbox 업데이트", t.bbox, bb)
    r.approx("confidence 업데이트", t.confidence, 0.92)
    r.eq("position_3d 업데이트", t.position_3d, p3d)
    r.eq("hits 1", t.hits, 1)
    r.eq("time_since_update 0", t.time_since_update, 0)
    r.eq("age 1", t.age, 1)
    r.eq("history.length 1", t.history.length, 1)


def test_track_mark_missed(r: TestResult) -> None:
    """Track mark_missed 메서드"""
    from shared.dto.tracking_dto import Track

    t = Track()
    t.mark_missed()
    r.eq("time_since_update 1", t.time_since_update, 1)
    r.eq("age 1", t.age, 1)
    t.mark_missed()
    r.eq("time_since_update 2", t.time_since_update, 2)
    r.eq("age 2", t.age, 2)


# ==================== 8. TrackAssociation ====================
def test_track_association(r: TestResult) -> None:
    """TrackAssociation dataclass + combined_score"""
    from shared.dto.tracking_dto import TrackAssociation

    ta = TrackAssociation(track_id=1, detection_index=3)
    r.eq("track_id", ta.track_id, 1)
    r.eq("detection_index", ta.detection_index, 3)
    r.approx("cost 기본", ta.cost, 0.0)
    r.approx("iou 기본", ta.iou, 0.0)
    r.approx("appearance_similarity 기본", ta.appearance_similarity, 0.0)
    r.approx("combined_score 기본 0", ta.combined_score, 0.0)

    ta2 = TrackAssociation(
        track_id=2, detection_index=5,
        cost=0.3, iou=0.8, appearance_similarity=0.9,
    )
    # combined = 0.8*0.5 + 0.9*0.5 = 0.85
    r.approx("combined_score 0.85", ta2.combined_score, 0.85)


# ==================== 9. TrackingResult ====================
def test_tracking_result_defaults(r: TestResult) -> None:
    """TrackingResult 기본값"""
    from shared.dto.tracking_dto import TrackingResult

    tr = TrackingResult()
    r.eq("frame_index 기본", tr.frame_index, 0)
    r.approx("timestamp 기본", tr.timestamp, 0.0)
    r.eq("tracks 빈", tr.tracks, [])
    r.eq("new_tracks 빈", tr.new_tracks, [])
    r.eq("deleted_tracks 빈", tr.deleted_tracks, [])
    r.eq("associations 빈", tr.associations, [])
    r.approx("processing_time 기본", tr.processing_time, 0.0)
    r.is_none("camera_id 기본 None", tr.camera_id)
    r.eq("num_tracks 0", tr.num_tracks, 0)


def test_tracking_result_methods(r: TestResult) -> None:
    """TrackingResult properties & methods"""
    from shared.dto.tracking_dto import TrackingResult, Track, TrackState, TrackedObjectType

    tracks = [
        Track(track_id=1, state=TrackState.CONFIRMED, object_type=TrackedObjectType.PLAYER),
        Track(track_id=2, state=TrackState.TENTATIVE, object_type=TrackedObjectType.PLAYER),
        Track(track_id=3, state=TrackState.LOST, object_type=TrackedObjectType.BALL),
        Track(track_id=4, state=TrackState.CONFIRMED, object_type=TrackedObjectType.REFEREE),
    ]
    tr = TrackingResult(frame_index=100, timestamp=3.33, tracks=tracks)

    r.eq("num_tracks", tr.num_tracks, 4)
    r.eq("active_tracks 수", len(tr.active_tracks), 3)  # CONFIRMED, TENTATIVE, (not LOST)
    r.eq("confirmed_tracks 수", len(tr.confirmed_tracks), 2)

    # get_track
    found = tr.get_track(2)
    r.is_not_none("get_track(2)", found)
    r.eq("get_track(2).track_id", found.track_id, 2)
    r.is_none("get_track(99)", tr.get_track(99))

    # get_tracks_by_type
    players = tr.get_tracks_by_type(TrackedObjectType.PLAYER)
    r.eq("players 수", len(players), 2)
    balls = tr.get_tracks_by_type(TrackedObjectType.BALL)
    r.eq("balls 수", len(balls), 1)


# ==================== 10. MultiViewTrackingResult ====================
def test_multi_view_tracking_result(r: TestResult) -> None:
    """MultiViewTrackingResult dataclass"""
    from shared.dto.tracking_dto import MultiViewTrackingResult, TrackingResult, Track, TrackState

    mvtr = MultiViewTrackingResult()
    r.eq("frame_index 기본", mvtr.frame_index, 0)
    r.eq("view_results 빈", mvtr.view_results, {})
    r.eq("fused_tracks 빈", mvtr.fused_tracks, [])
    r.eq("num_views 0", mvtr.num_views, 0)
    r.eq("num_fused_tracks 0", mvtr.num_fused_tracks, 0)

    # 데이터 입력
    tr1 = TrackingResult(frame_index=100, camera_id="cam1")
    tr2 = TrackingResult(frame_index=100, camera_id="cam2")
    fused = [Track(track_id=1, state=TrackState.CONFIRMED)]

    mvtr2 = MultiViewTrackingResult(
        frame_index=100,
        timestamp=3.33,
        view_results={"cam1": tr1, "cam2": tr2},
        fused_tracks=fused,
        processing_time=0.015,
    )

    r.eq("num_views 2", mvtr2.num_views, 2)
    r.eq("num_fused_tracks 1", mvtr2.num_fused_tracks, 1)

    # get_view_result
    result = mvtr2.get_view_result("cam1")
    r.is_not_none("get_view_result cam1", result)
    r.eq("cam1 camera_id", result.camera_id, "cam1")
    r.is_none("get_view_result cam3", mvtr2.get_view_result("cam3"))


# ==================== 11. dataclass 필드 수 ====================
def test_field_counts(r: TestResult) -> None:
    """각 dataclass 필드 수 검증"""
    from dataclasses import fields
    from shared.dto.tracking_dto import (
        TrackHistory, KalmanState, Track, TrackAssociation,
        TrackingResult, MultiViewTrackingResult,
    )

    r.eq("TrackHistory 필드 수", len(fields(TrackHistory)), 5)
    r.eq("KalmanState 필드 수", len(fields(KalmanState)), 4)
    r.eq("Track 필드 수", len(fields(Track)), 14)
    r.eq("TrackAssociation 필드 수", len(fields(TrackAssociation)), 5)
    r.eq("TrackingResult 필드 수", len(fields(TrackingResult)), 8)
    r.eq("MultiViewTrackingResult 필드 수", len(fields(MultiViewTrackingResult)), 5)


# ==================== 12. mutable default 격리 ====================
def test_mutable_default_isolation(r: TestResult) -> None:
    """mutable default 필드 격리"""
    from shared.dto.tracking_dto import Track, TrackingResult

    # Track attributes
    t1 = Track()
    t2 = Track()
    t1.attributes["jersey_number"] = 23
    r.eq("t1.attributes 수", len(t1.attributes), 1)
    r.eq("t2.attributes 수 (격리)", len(t2.attributes), 0)

    # TrackingResult tracks
    tr1 = TrackingResult()
    tr2 = TrackingResult()
    tr1.tracks.append("test")
    r.eq("tr1.tracks 수", len(tr1.tracks), 1)
    r.eq("tr2.tracks 수 (격리)", len(tr2.tracks), 0)


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("tracking_dto.py v1.1.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)

    print("\n--- TrackState Enum ---")
    test_track_state(r)

    print("\n--- TrackSource Enum ---")
    test_track_source(r)

    print("\n--- TrackedObjectType Enum ---")
    test_tracked_object_type(r)

    print("\n--- TrackHistory 기본값 ---")
    test_track_history_defaults(r)

    print("\n--- TrackHistory add_entry ---")
    test_track_history_add_entry(r)

    print("\n--- TrackHistory trim ---")
    test_track_history_trim(r)

    print("\n--- TrackHistory to_trajectory_3d ---")
    test_track_history_to_trajectory_3d(r)

    print("\n--- KalmanState ---")
    test_kalman_state(r)

    print("\n--- Track 기본값 ---")
    test_track_defaults(r)

    print("\n--- Track __post_init__ ---")
    test_track_post_init(r)

    print("\n--- Track properties ---")
    test_track_properties(r)

    print("\n--- Track update ---")
    test_track_update(r)

    print("\n--- Track mark_missed ---")
    test_track_mark_missed(r)

    print("\n--- TrackAssociation ---")
    test_track_association(r)

    print("\n--- TrackingResult 기본값 ---")
    test_tracking_result_defaults(r)

    print("\n--- TrackingResult methods ---")
    test_tracking_result_methods(r)

    print("\n--- MultiViewTrackingResult ---")
    test_multi_view_tracking_result(r)

    print("\n--- dataclass 필드 수 ---")
    test_field_counts(r)

    print("\n--- mutable default 격리 ---")
    test_mutable_default_isolation(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
