# -*- coding: utf-8 -*-
"""detector_interface.py v1.20.0 단위 테스트"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import math
from abc import ABC
from dataclasses import fields
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import numpy as np
from shared.constants.localization import SupportedLanguage
from shared.interfaces.detector_interface import (
    DetectionTarget, DetectionState, PlayerRole, ColorFormat,
    PoseKeypoint, BodySegment,
    BoundingBox, DetectedObject, DetectionResult,
    FrameData, DetectorMetrics,
    IDetector, IBallDetector, ICourtDetector, IPlayerDetector,
    IPoseEstimator, IHoopDetector, ITracker,
    IDetectorFactory, ICompositeDetector,
    DetectionCallback,
    BallState, BallDetectionResult, CourtKeypoints, CourtDetectionResult,
    PlayerDetection, PlayerDetectionResult,
    KeypointData, JointAngle, SegmentData,
    PoseEstimation, PoseEstimationResult,
    HoopDetection, HoopDetectionResult,
    TrackingResult, TrackState, TrackerMetrics,
)


# =============================================================================
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    def __init__(self, name: str) -> None:
        self.name = name
        self.passed = 0
        self.failed = 0
        self._section = ""

    def set_section(self, section: str) -> None:
        self._section = section
        print(f"\n{'=' * 60}")
        print(f"  {section}")
        print(f"{'=' * 60}")

    def ok(self, desc: str) -> None:
        self.passed += 1
        print(f"  [PASS] {desc}")

    def fail(self, desc: str) -> None:
        self.failed += 1
        print(f"  [FAIL] {desc}")

    def check(self, condition: bool, desc: str) -> None:
        if condition:
            self.ok(desc)
        else:
            self.fail(desc)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'=' * 60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        print(f"{'=' * 60}")


# =============================================================================
# 5개 언어 리스트
# =============================================================================
ALL_LANGS = [
    SupportedLanguage.KO,
    SupportedLanguage.EN,
    SupportedLanguage.JA,
    SupportedLanguage.ZH,
    SupportedLanguage.ES,
]


# =============================================================================
# 스텁 클래스 정의
# =============================================================================
class StubDetector(IDetector):
    def __init__(self):
        self._state = DetectionState.UNINITIALIZED
        self._metrics = DetectorMetrics()

    @property
    def name(self): return "StubDetector"

    @property
    def version(self): return "1.0.0"

    @property
    def supported_targets(self): return [DetectionTarget.PLAYER]

    @property
    def state(self): return self._state

    @property
    def metrics(self): return self._metrics

    def initialize(self, config): self._state = DetectionState.READY

    def detect(self, frame, frame_index=0, timestamp_ms=0.0, targets=None):
        obj = DetectedObject(DetectionTarget.PLAYER, BoundingBox(10, 20, 100, 200, 0.95))
        return DetectionResult.success_result([obj], frame_index=frame_index)

    def reset(self): self._state = DetectionState.UNINITIALIZED

    def shutdown(self): self._state = DetectionState.SHUTDOWN


class StubBallDetector(IBallDetector):
    def __init__(self):
        self._state = DetectionState.UNINITIALIZED
        self._metrics = DetectorMetrics()

    @property
    def name(self): return "StubBallDetector"

    @property
    def version(self): return "1.0.0"

    @property
    def state(self): return self._state

    @property
    def metrics(self): return self._metrics

    def initialize(self, config): self._state = DetectionState.READY

    def detect(self, frame, frame_index=0, timestamp_ms=0.0, targets=None):
        obj = DetectedObject(DetectionTarget.BALL, BoundingBox(50, 50, 30, 30, 0.90))
        return DetectionResult.success_result([obj], frame_index=frame_index)

    def reset(self): self._state = DetectionState.UNINITIALIZED

    def shutdown(self): self._state = DetectionState.SHUTDOWN

    def detect_ball(self, frame, frame_index=0, timestamp_ms=0.0):
        bs = BallState(position=(65.0, 65.0), radius=15.0)
        return BallDetectionResult(
            success=True, ball_state=bs, frame_index=frame_index,
        )

    def predict_trajectory(self, current_state, time_ahead_ms):
        cx, cy = current_state.position
        return [(cx + 1.0, cy + 2.0), (cx + 2.0, cy + 4.0)]

    def is_ball_in_hoop_region(self, ball_state, hoop_region):
        bx, by = ball_state.position
        return hoop_region.contains_point(bx, by)


class StubCourtDetector(ICourtDetector):
    def __init__(self):
        self._state = DetectionState.UNINITIALIZED
        self._metrics = DetectorMetrics()

    @property
    def name(self): return "StubCourtDetector"

    @property
    def version(self): return "1.0.0"

    @property
    def state(self): return self._state

    @property
    def metrics(self): return self._metrics

    def initialize(self, config): self._state = DetectionState.READY

    def detect(self, frame, frame_index=0, timestamp_ms=0.0, targets=None):
        obj = DetectedObject(DetectionTarget.COURT, BoundingBox(0, 0, 1920, 1080, 0.99))
        return DetectionResult.success_result([obj], frame_index=frame_index)

    def reset(self): self._state = DetectionState.UNINITIALIZED

    def shutdown(self): self._state = DetectionState.SHUTDOWN

    def detect_court(self, frame, frame_index=0, timestamp_ms=0.0):
        kps = CourtKeypoints(corners=[(0, 0), (28, 0), (28, 15), (0, 15)])
        return CourtDetectionResult(
            success=True, keypoints=kps, court_type="full",
            frame_index=frame_index,
        )

    def pixel_to_court(self, pixel_point, homography):
        return (pixel_point[0] / 100.0, pixel_point[1] / 100.0)

    def court_to_pixel(self, court_point, homography):
        return (court_point[0] * 100.0, court_point[1] * 100.0)

    def get_zone_at_position(self, court_position):
        return "paint"


class StubPlayerDetector(IPlayerDetector):
    def __init__(self):
        self._state = DetectionState.UNINITIALIZED
        self._metrics = DetectorMetrics()

    @property
    def name(self): return "StubPlayerDetector"

    @property
    def version(self): return "1.0.0"

    @property
    def state(self): return self._state

    @property
    def metrics(self): return self._metrics

    def initialize(self, config): self._state = DetectionState.READY

    def detect(self, frame, frame_index=0, timestamp_ms=0.0, targets=None):
        obj = DetectedObject(DetectionTarget.PLAYER, BoundingBox(100, 100, 60, 180, 0.92))
        return DetectionResult.success_result([obj], frame_index=frame_index)

    def reset(self): self._state = DetectionState.UNINITIALIZED

    def shutdown(self): self._state = DetectionState.SHUTDOWN

    def detect_players(self, frame, frame_index=0, timestamp_ms=0.0):
        pd = PlayerDetection(
            bounding_box=BoundingBox(100, 100, 60, 180, 0.92),
            role=PlayerRole.PLAYER, player_id=1,
        )
        return PlayerDetectionResult(success=True, players=[pd], frame_index=frame_index)


class StubPoseEstimator(IPoseEstimator):
    def __init__(self):
        self._state = DetectionState.UNINITIALIZED
        self._metrics = DetectorMetrics()

    @property
    def name(self): return "StubPoseEstimator"

    @property
    def version(self): return "1.0.0"

    @property
    def state(self): return self._state

    @property
    def metrics(self): return self._metrics

    def initialize(self, config): self._state = DetectionState.READY

    def detect(self, frame, frame_index=0, timestamp_ms=0.0, targets=None):
        return DetectionResult.success_result([], frame_index=frame_index)

    def reset(self): self._state = DetectionState.UNINITIALIZED

    def shutdown(self): self._state = DetectionState.SHUTDOWN

    def estimate_poses(self, frame, frame_index=0, timestamp_ms=0.0, person_boxes=None):
        kp_data = {
            PoseKeypoint.NOSE: KeypointData(PoseKeypoint.NOSE, 100.0, 50.0, 0.95),
            PoseKeypoint.LEFT_SHOULDER: KeypointData(PoseKeypoint.LEFT_SHOULDER, 80.0, 100.0, 0.90),
            PoseKeypoint.RIGHT_SHOULDER: KeypointData(PoseKeypoint.RIGHT_SHOULDER, 120.0, 100.0, 0.90),
        }
        pose = PoseEstimation(person_id=1, keypoints=kp_data, overall_confidence=0.9)
        return PoseEstimationResult.success_result(
            poses=[pose], frame_index=frame_index, model_name="stub_model",
        )

    def calculate_joint_angles(self, pose):
        return {"left_elbow": JointAngle(
            joint_name="left_elbow", angle_degrees=90.0,
            keypoint_a=PoseKeypoint.LEFT_SHOULDER,
            keypoint_b=PoseKeypoint.LEFT_ELBOW,
            keypoint_c=PoseKeypoint.LEFT_WRIST,
            confidence=0.85,
        )}

    def calculate_body_segments(self, pose):
        return {BodySegment.TORSO: SegmentData(
            segment=BodySegment.TORSO,
            start_keypoint=PoseKeypoint.LEFT_SHOULDER,
            end_keypoint=PoseKeypoint.LEFT_HIP,
            start_position=(80.0, 100.0),
            end_position=(80.0, 200.0),
            length_pixels=100.0,
            angle_degrees=90.0,
            confidence=0.88,
        )}

    def infer_extended_keypoints(self, base_keypoints):
        result = dict(base_keypoints)
        ls = base_keypoints.get(PoseKeypoint.LEFT_SHOULDER)
        rs = base_keypoints.get(PoseKeypoint.RIGHT_SHOULDER)
        if ls and rs:
            nx = (ls.x + rs.x) / 2
            ny = (ls.y + rs.y) / 2
            result[PoseKeypoint.NECK] = KeypointData(
                PoseKeypoint.NECK, nx, ny, min(ls.confidence, rs.confidence),
                is_inferred=True,
            )
        return result

    def get_pose_similarity(self, pose_a, pose_b, comparison_keypoints=None):
        return 0.85

    def normalize_pose(self, pose, reference_segment=BodySegment.TORSO):
        return pose

    def estimate_3d_pose(self, pose_2d, camera_params=None):
        return pose_2d


class StubHoopDetector(IHoopDetector):
    def __init__(self):
        self._state = DetectionState.UNINITIALIZED
        self._metrics = DetectorMetrics()

    @property
    def name(self): return "StubHoopDetector"

    @property
    def version(self): return "1.0.0"

    @property
    def state(self): return self._state

    @property
    def metrics(self): return self._metrics

    def initialize(self, config): self._state = DetectionState.READY

    def detect(self, frame, frame_index=0, timestamp_ms=0.0, targets=None):
        obj = DetectedObject(DetectionTarget.HOOP, BoundingBox(900, 50, 100, 100, 0.97))
        return DetectionResult.success_result([obj], frame_index=frame_index)

    def reset(self): self._state = DetectionState.UNINITIALIZED

    def shutdown(self): self._state = DetectionState.SHUTDOWN

    def detect_hoops(self, frame, frame_index=0, timestamp_ms=0.0):
        hd = HoopDetection(
            bounding_box=BoundingBox(900, 50, 100, 100, 0.97),
            rim_center=(950.0, 100.0), rim_radius=22.5,
        )
        return HoopDetectionResult(success=True, hoops=[hd], frame_index=frame_index)

    def detect_score(self, ball_trajectory, hoop):
        return (True, 0.92)


class StubTracker(ITracker):
    def __init__(self):
        self._state = DetectionState.UNINITIALIZED
        self._tracks: dict[int, TrackState] = {}
        self._next_id = 1

    @property
    def name(self): return "StubTracker"

    @property
    def version(self): return "1.0.0"

    @property
    def state(self): return self._state

    @property
    def active_track_count(self): return len(self._tracks)

    @property
    def total_tracks_created(self): return self._next_id - 1

    def initialize(self, config): self._state = DetectionState.READY

    def update(self, detections, frame=None, frame_index=0, timestamp_ms=0.0):
        tracked = []
        for det in detections:
            det.object_id = self._next_id
            tracked.append(det)
            cx, cy = det.bounding_box.center
            self._tracks[self._next_id] = TrackState(
                track_id=self._next_id, position=(cx, cy),
                is_confirmed=True, bounding_box=det.bounding_box,
            )
            self._next_id += 1
        return TrackingResult.success_result(
            tracked_objects=tracked, new_tracks=len(detections),
            active_tracks=len(self._tracks), frame_index=frame_index,
        )

    def predict(self, time_ahead_ms=0.0):
        return list(self._tracks.values())

    def get_track(self, track_id):
        return self._tracks.get(track_id)

    def get_all_tracks(self, confirmed_only=False):
        if confirmed_only:
            return [t for t in self._tracks.values() if t.is_confirmed]
        return list(self._tracks.values())

    def get_track_history(self, track_id, max_length=None):
        t = self._tracks.get(track_id)
        if not t:
            return []
        hist = [t.position]
        return hist[:max_length] if max_length else hist

    def remove_track(self, track_id):
        if track_id in self._tracks:
            del self._tracks[track_id]
            return True
        return False

    def reset(self):
        self._tracks.clear()
        self._next_id = 1
        self._state = DetectionState.UNINITIALIZED

    def shutdown(self): self._state = DetectionState.SHUTDOWN


class StubDetectorFactory(IDetectorFactory):
    def create(self, config):
        d = StubDetector()
        d.initialize(config)
        return d

    def get_supported_types(self):
        return ["stub"]

    def create_composite(self, detector_configs):
        return StubCompositeDetector()


class StubCompositeDetector(ICompositeDetector):
    def __init__(self):
        self._state = DetectionState.UNINITIALIZED
        self._metrics = DetectorMetrics()
        self._detectors: dict[DetectionTarget, IDetector] = {}

    @property
    def name(self): return "StubCompositeDetector"

    @property
    def version(self): return "1.0.0"

    @property
    def supported_targets(self):
        return [DetectionTarget.PLAYER, DetectionTarget.BALL]

    @property
    def state(self): return self._state

    @property
    def metrics(self): return self._metrics

    def initialize(self, config): self._state = DetectionState.READY

    def detect(self, frame, frame_index=0, timestamp_ms=0.0, targets=None):
        objs = [
            DetectedObject(DetectionTarget.PLAYER, BoundingBox(10, 20, 100, 200, 0.95)),
            DetectedObject(DetectionTarget.BALL, BoundingBox(50, 50, 30, 30, 0.90)),
        ]
        return DetectionResult.success_result(objs, frame_index=frame_index)

    def reset(self): self._state = DetectionState.UNINITIALIZED

    def shutdown(self): self._state = DetectionState.SHUTDOWN

    def get_detector(self, target):
        return self._detectors.get(target)

    def detect_all(self, frame, frame_index=0, timestamp_ms=0.0):
        result = {}
        for tgt in self.supported_targets:
            obj = DetectedObject(tgt, BoundingBox(10, 10, 50, 50, 0.9))
            result[tgt] = DetectionResult.success_result([obj], frame_index=frame_index)
        return result


class StubCallback:
    """DetectionCallback 프로토콜 구현 스텁."""
    def __init__(self):
        self.last_result = None
        self.last_error = None
        self.pending = []

    def on_detection_complete(self, result, context=None):
        self.last_result = result

    def on_detection_error(self, error, frame_info=None):
        self.last_error = error

    def get_pending_detections(self):
        return self.pending


# =============================================================================
# 테스트 함수 정의
# =============================================================================

def test_01_detection_target_members(tr: TestResult) -> None:
    """[1] DetectionTarget - 멤버 값 및 수량"""
    tr.set_section("[1] DetectionTarget - 멤버 값 및 수량")
    members = list(DetectionTarget)
    tr.check(len(members) == 8, f"DetectionTarget 멤버 수 == 8 (실제: {len(members)})")

    expected = {
        "BALL": "ball", "COURT": "court", "HOOP": "hoop", "PLAYER": "player",
        "REFEREE": "referee", "COACH": "coach", "SCOREBOARD": "scoreboard", "LINE": "line",
    }
    for name, val in expected.items():
        member = DetectionTarget[name]
        tr.check(member.value == val, f"DetectionTarget.{name}.value == '{val}'")


def test_02_detection_target_str(tr: TestResult) -> None:
    """[2] DetectionTarget - __str__"""
    tr.set_section("[2] DetectionTarget - __str__")
    for m in DetectionTarget:
        tr.check(str(m) == m.value, f"str(DetectionTarget.{m.name}) == '{m.value}'")


def test_03_detection_target_get_name(tr: TestResult) -> None:
    """[3] DetectionTarget - get_name 다국어"""
    tr.set_section("[3] DetectionTarget - get_name 다국어")
    # 8 멤버 x 5 언어 = 40 non-empty 검사
    for m in DetectionTarget:
        for lang in ALL_LANGS:
            name = m.get_name(lang)
            tr.check(
                isinstance(name, str) and len(name) > 0,
                f"DetectionTarget.{m.name}.get_name({lang.name}) non-empty: '{name}'",
            )

    # 한글 값 검증 (8 checks)
    ko_expected = {
        DetectionTarget.BALL: "농구공", DetectionTarget.COURT: "코트",
        DetectionTarget.HOOP: "골대", DetectionTarget.PLAYER: "선수",
        DetectionTarget.REFEREE: "심판", DetectionTarget.COACH: "코치",
        DetectionTarget.SCOREBOARD: "스코어보드", DetectionTarget.LINE: "코트 라인",
    }
    for m, expected_ko in ko_expected.items():
        tr.check(
            m.get_name(SupportedLanguage.KO) == expected_ko,
            f"DetectionTarget.{m.name} KO == '{expected_ko}'",
        )


def test_04_detection_target_to_korean(tr: TestResult) -> None:
    """[4] DetectionTarget - to_korean"""
    tr.set_section("[4] DetectionTarget - to_korean")
    ko_expected = {
        DetectionTarget.BALL: "농구공", DetectionTarget.COURT: "코트",
        DetectionTarget.HOOP: "골대", DetectionTarget.PLAYER: "선수",
        DetectionTarget.REFEREE: "심판", DetectionTarget.COACH: "코치",
        DetectionTarget.SCOREBOARD: "스코어보드", DetectionTarget.LINE: "코트 라인",
    }
    for m, expected_ko in ko_expected.items():
        tr.check(m.to_korean == expected_ko, f"DetectionTarget.{m.name}.to_korean == '{expected_ko}'")


def test_05_detection_target_is_person_court_element(tr: TestResult) -> None:
    """[5] DetectionTarget - is_person / is_court_element"""
    tr.set_section("[5] DetectionTarget - is_person / is_court_element")
    person_expected = {
        DetectionTarget.BALL: False, DetectionTarget.COURT: False,
        DetectionTarget.HOOP: False, DetectionTarget.PLAYER: True,
        DetectionTarget.REFEREE: True, DetectionTarget.COACH: True,
        DetectionTarget.SCOREBOARD: False, DetectionTarget.LINE: False,
    }
    for m, exp in person_expected.items():
        tr.check(m.is_person == exp, f"DetectionTarget.{m.name}.is_person == {exp}")

    court_expected = {
        DetectionTarget.BALL: False, DetectionTarget.COURT: True,
        DetectionTarget.HOOP: True, DetectionTarget.PLAYER: False,
        DetectionTarget.REFEREE: False, DetectionTarget.COACH: False,
        DetectionTarget.SCOREBOARD: False, DetectionTarget.LINE: True,
    }
    for m, exp in court_expected.items():
        tr.check(m.is_court_element == exp, f"DetectionTarget.{m.name}.is_court_element == {exp}")


def test_06_detection_state_members(tr: TestResult) -> None:
    """[6] DetectionState - 멤버/값/__str__"""
    tr.set_section("[6] DetectionState - 멤버/값/__str__")
    members = list(DetectionState)
    tr.check(len(members) == 6, f"DetectionState 멤버 수 == 6 (실제: {len(members)})")

    expected = {
        "UNINITIALIZED": "uninitialized", "READY": "ready",
        "DETECTING": "detecting", "TRACKING": "tracking",
        "ERROR": "error", "SHUTDOWN": "shutdown",
    }
    for name, val in expected.items():
        member = DetectionState[name]
        tr.check(member.value == val, f"DetectionState.{name}.value == '{val}'")
        tr.check(str(member) == val, f"str(DetectionState.{name}) == '{val}'")


def test_07_detection_state_get_name(tr: TestResult) -> None:
    """[7] DetectionState - get_name 다국어"""
    tr.set_section("[7] DetectionState - get_name 다국어")
    for m in DetectionState:
        for lang in ALL_LANGS:
            name = m.get_name(lang)
            tr.check(
                isinstance(name, str) and len(name) > 0,
                f"DetectionState.{m.name}.get_name({lang.name}) non-empty",
            )


def test_08_detection_state_properties(tr: TestResult) -> None:
    """[8] DetectionState - is_active/is_processing/is_error/is_terminated"""
    tr.set_section("[8] DetectionState - is_active/is_processing/is_error/is_terminated")
    active_expected = {
        DetectionState.UNINITIALIZED: False, DetectionState.READY: True,
        DetectionState.DETECTING: True, DetectionState.TRACKING: True,
        DetectionState.ERROR: False, DetectionState.SHUTDOWN: False,
    }
    for m, exp in active_expected.items():
        tr.check(m.is_active == exp, f"DetectionState.{m.name}.is_active == {exp}")

    processing_expected = {
        DetectionState.UNINITIALIZED: False, DetectionState.READY: False,
        DetectionState.DETECTING: True, DetectionState.TRACKING: True,
        DetectionState.ERROR: False, DetectionState.SHUTDOWN: False,
    }
    for m, exp in processing_expected.items():
        tr.check(m.is_processing == exp, f"DetectionState.{m.name}.is_processing == {exp}")

    error_expected = {
        DetectionState.UNINITIALIZED: False, DetectionState.READY: False,
        DetectionState.DETECTING: False, DetectionState.TRACKING: False,
        DetectionState.ERROR: True, DetectionState.SHUTDOWN: False,
    }
    for m, exp in error_expected.items():
        tr.check(m.is_error == exp, f"DetectionState.{m.name}.is_error == {exp}")

    terminated_expected = {
        DetectionState.UNINITIALIZED: False, DetectionState.READY: False,
        DetectionState.DETECTING: False, DetectionState.TRACKING: False,
        DetectionState.ERROR: True, DetectionState.SHUTDOWN: True,
    }
    for m, exp in terminated_expected.items():
        tr.check(m.is_terminated == exp, f"DetectionState.{m.name}.is_terminated == {exp}")


def test_09_player_role_members(tr: TestResult) -> None:
    """[9] PlayerRole - 멤버/get_name"""
    tr.set_section("[9] PlayerRole - 멤버/get_name")
    members = list(PlayerRole)
    tr.check(len(members) == 5, f"PlayerRole 멤버 수 == 5 (실제: {len(members)})")

    expected_values = {
        "PLAYER": "player", "REFEREE": "referee", "COACH": "coach",
        "STAFF": "staff", "UNKNOWN": "unknown",
    }
    for name, val in expected_values.items():
        tr.check(PlayerRole[name].value == val, f"PlayerRole.{name}.value == '{val}'")

    # get_name 한글/영어 검증 (5 x 2 = 10)
    ko_expected = {
        PlayerRole.PLAYER: "선수", PlayerRole.REFEREE: "심판",
        PlayerRole.COACH: "코치", PlayerRole.STAFF: "스태프",
        PlayerRole.UNKNOWN: "미분류",
    }
    for m, exp_ko in ko_expected.items():
        tr.check(m.get_name(SupportedLanguage.KO) == exp_ko, f"PlayerRole.{m.name} KO == '{exp_ko}'")
        en_name = m.get_name(SupportedLanguage.EN)
        tr.check(len(en_name) > 0, f"PlayerRole.{m.name} EN non-empty: '{en_name}'")


def test_10_player_role_class_id(tr: TestResult) -> None:
    """[10] PlayerRole - from_class_id/to_class_id 라운드트립"""
    tr.set_section("[10] PlayerRole - from_class_id/to_class_id 라운드트립")
    id_map = {0: PlayerRole.PLAYER, 1: PlayerRole.REFEREE, 2: PlayerRole.COACH,
              3: PlayerRole.STAFF, 4: PlayerRole.UNKNOWN}
    # from_class_id 검증 (5)
    for cid, role in id_map.items():
        tr.check(PlayerRole.from_class_id(cid) == role, f"from_class_id({cid}) == {role.name}")

    # to_class_id 검증 (5)
    for cid, role in id_map.items():
        tr.check(role.to_class_id() == cid, f"{role.name}.to_class_id() == {cid}")

    # 라운드트립 (5+2 edge)
    for cid in range(5):
        role = PlayerRole.from_class_id(cid)
        tr.check(role.to_class_id() == cid, f"라운드트립: {cid} -> {role.name} -> {role.to_class_id()}")

    # 범위 밖 class_id
    tr.check(PlayerRole.from_class_id(99) == PlayerRole.UNKNOWN, "from_class_id(99) == UNKNOWN")
    tr.check(PlayerRole.from_class_id(-1) == PlayerRole.UNKNOWN, "from_class_id(-1) == UNKNOWN")


def test_11_color_format_members(tr: TestResult) -> None:
    """[11] ColorFormat - 멤버/get_name/channel_count"""
    tr.set_section("[11] ColorFormat - 멤버/get_name/channel_count")
    members = list(ColorFormat)
    tr.check(len(members) == 5, f"ColorFormat 멤버 수 == 5 (실제: {len(members)})")

    expected = {"RGB": "rgb", "BGR": "bgr", "GRAY": "gray", "RGBA": "rgba", "BGRA": "bgra"}
    for name, val in expected.items():
        tr.check(ColorFormat[name].value == val, f"ColorFormat.{name}.value == '{val}'")

    # get_name 한글 (5)
    for m in ColorFormat:
        ko_name = m.get_name(SupportedLanguage.KO)
        tr.check(len(ko_name) > 0, f"ColorFormat.{m.name} KO non-empty: '{ko_name}'")

    # channel_count (5)
    channel_expected = {
        ColorFormat.RGB: 3, ColorFormat.BGR: 3, ColorFormat.GRAY: 1,
        ColorFormat.RGBA: 4, ColorFormat.BGRA: 4,
    }
    for m, exp_ch in channel_expected.items():
        tr.check(m.channel_count == exp_ch, f"ColorFormat.{m.name}.channel_count == {exp_ch}")


def test_12_color_format_alpha_grayscale(tr: TestResult) -> None:
    """[12] ColorFormat - has_alpha/is_grayscale"""
    tr.set_section("[12] ColorFormat - has_alpha/is_grayscale")
    alpha_expected = {
        ColorFormat.RGB: False, ColorFormat.BGR: False, ColorFormat.GRAY: False,
        ColorFormat.RGBA: True, ColorFormat.BGRA: True,
    }
    for m, exp in alpha_expected.items():
        tr.check(m.has_alpha == exp, f"ColorFormat.{m.name}.has_alpha == {exp}")

    gray_expected = {
        ColorFormat.RGB: False, ColorFormat.BGR: False, ColorFormat.GRAY: True,
        ColorFormat.RGBA: False, ColorFormat.BGRA: False,
    }
    for m, exp in gray_expected.items():
        tr.check(m.is_grayscale == exp, f"ColorFormat.{m.name}.is_grayscale == {exp}")


def test_13_pose_keypoint_members(tr: TestResult) -> None:
    """[13] PoseKeypoint - 멤버 수/COCO vs 확장"""
    tr.set_section("[13] PoseKeypoint - 멤버 수/COCO vs 확장")
    members = list(PoseKeypoint)
    tr.check(len(members) == 24, f"PoseKeypoint 멤버 수 == 24 (실제: {len(members)})")

    # COCO 17
    coco_names = [
        "NOSE", "LEFT_EYE", "RIGHT_EYE", "LEFT_EAR", "RIGHT_EAR",
        "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
        "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP",
        "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
    ]
    for name in coco_names:
        member = PoseKeypoint[name]
        tr.check(member.is_coco_keypoint is True, f"PoseKeypoint.{name}.is_coco_keypoint == True")

    # 확장 7
    ext_names = ["NECK", "MID_SPINE", "PELVIS", "LEFT_HAND", "RIGHT_HAND", "LEFT_FOOT", "RIGHT_FOOT"]
    for name in ext_names:
        member = PoseKeypoint[name]
        tr.check(member.is_extended is True, f"PoseKeypoint.{name}.is_extended == True")


def test_14_pose_keypoint_get_name(tr: TestResult) -> None:
    """[14] PoseKeypoint - get_name 샘플"""
    tr.set_section("[14] PoseKeypoint - get_name 샘플")
    sample = [PoseKeypoint.NOSE, PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_KNEE,
              PoseKeypoint.NECK, PoseKeypoint.PELVIS]
    for m in sample:
        for lang in ALL_LANGS:
            name = m.get_name(lang)
            tr.check(
                isinstance(name, str) and len(name) > 0,
                f"PoseKeypoint.{m.name}.get_name({lang.name}) non-empty: '{name}'",
            )


def test_15_pose_keypoint_coco_index(tr: TestResult) -> None:
    """[15] PoseKeypoint - coco_index"""
    tr.set_section("[15] PoseKeypoint - coco_index")
    coco_indices = {
        PoseKeypoint.NOSE: 0, PoseKeypoint.LEFT_EYE: 1, PoseKeypoint.RIGHT_EYE: 2,
        PoseKeypoint.LEFT_EAR: 3, PoseKeypoint.RIGHT_EAR: 4,
        PoseKeypoint.LEFT_SHOULDER: 5, PoseKeypoint.RIGHT_SHOULDER: 6,
        PoseKeypoint.LEFT_ELBOW: 7, PoseKeypoint.RIGHT_ELBOW: 8,
        PoseKeypoint.LEFT_WRIST: 9, PoseKeypoint.RIGHT_WRIST: 10,
        PoseKeypoint.LEFT_HIP: 11, PoseKeypoint.RIGHT_HIP: 12,
        PoseKeypoint.LEFT_KNEE: 13, PoseKeypoint.RIGHT_KNEE: 14,
        PoseKeypoint.LEFT_ANKLE: 15, PoseKeypoint.RIGHT_ANKLE: 16,
    }
    for kp, idx in coco_indices.items():
        tr.check(kp.coco_index == idx, f"PoseKeypoint.{kp.name}.coco_index == {idx}")

    # 확장 키포인트 None
    ext_names = ["NECK", "MID_SPINE", "PELVIS", "LEFT_HAND", "RIGHT_HAND", "LEFT_FOOT", "RIGHT_FOOT"]
    for name in ext_names:
        member = PoseKeypoint[name]
        tr.check(member.coco_index is None, f"PoseKeypoint.{name}.coco_index is None")


def test_16_pose_keypoint_upper_lower(tr: TestResult) -> None:
    """[16] PoseKeypoint - is_upper_body/is_lower_body"""
    tr.set_section("[16] PoseKeypoint - is_upper_body/is_lower_body")
    upper = {
        PoseKeypoint.NOSE, PoseKeypoint.LEFT_EYE, PoseKeypoint.RIGHT_EYE,
        PoseKeypoint.LEFT_EAR, PoseKeypoint.RIGHT_EAR,
        PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.RIGHT_SHOULDER,
        PoseKeypoint.LEFT_ELBOW, PoseKeypoint.RIGHT_ELBOW,
        PoseKeypoint.LEFT_WRIST, PoseKeypoint.RIGHT_WRIST,
        PoseKeypoint.NECK, PoseKeypoint.MID_SPINE,
        PoseKeypoint.LEFT_HAND, PoseKeypoint.RIGHT_HAND,
    }
    lower = {
        PoseKeypoint.LEFT_HIP, PoseKeypoint.RIGHT_HIP,
        PoseKeypoint.LEFT_KNEE, PoseKeypoint.RIGHT_KNEE,
        PoseKeypoint.LEFT_ANKLE, PoseKeypoint.RIGHT_ANKLE,
        PoseKeypoint.PELVIS,
        PoseKeypoint.LEFT_FOOT, PoseKeypoint.RIGHT_FOOT,
    }
    for m in PoseKeypoint:
        tr.check(
            m.is_upper_body == (m in upper),
            f"PoseKeypoint.{m.name}.is_upper_body == {m in upper}",
        )
        tr.check(
            m.is_lower_body == (m in lower),
            f"PoseKeypoint.{m.name}.is_lower_body == {m in lower}",
        )


def test_17_body_segment_members(tr: TestResult) -> None:
    """[17] BodySegment - 멤버/get_name 샘플"""
    tr.set_section("[17] BodySegment - 멤버/get_name 샘플")
    members = list(BodySegment)
    tr.check(len(members) == 11, f"BodySegment 멤버 수 == 11 (실제: {len(members)})")

    expected_values = {
        "HEAD": "head", "NECK_SPINE": "neck_spine",
        "LEFT_UPPER_ARM": "left_upper_arm", "RIGHT_UPPER_ARM": "right_upper_arm",
        "LEFT_FOREARM": "left_forearm", "RIGHT_FOREARM": "right_forearm",
        "TORSO": "torso",
        "LEFT_THIGH": "left_thigh", "RIGHT_THIGH": "right_thigh",
        "LEFT_SHIN": "left_shin", "RIGHT_SHIN": "right_shin",
    }
    for name, val in expected_values.items():
        tr.check(BodySegment[name].value == val, f"BodySegment.{name}.value == '{val}'")

    # get_name 샘플 (5 멤버 x 2 언어)
    sample = [BodySegment.HEAD, BodySegment.TORSO, BodySegment.LEFT_THIGH,
              BodySegment.LEFT_FOREARM, BodySegment.RIGHT_SHIN]
    for m in sample:
        ko = m.get_name(SupportedLanguage.KO)
        en = m.get_name(SupportedLanguage.EN)
        tr.check(len(ko) > 0, f"BodySegment.{m.name} KO non-empty: '{ko}'")
        tr.check(len(en) > 0, f"BodySegment.{m.name} EN non-empty: '{en}'")


def test_18_body_segment_classification(tr: TestResult) -> None:
    """[18] BodySegment - is_upper_body/is_lower_body/is_arm/is_leg"""
    tr.set_section("[18] BodySegment - is_upper_body/is_lower_body/is_arm/is_leg")
    upper_set = {
        BodySegment.HEAD, BodySegment.NECK_SPINE,
        BodySegment.LEFT_UPPER_ARM, BodySegment.RIGHT_UPPER_ARM,
        BodySegment.LEFT_FOREARM, BodySegment.RIGHT_FOREARM,
        BodySegment.TORSO,
    }
    lower_set = {
        BodySegment.LEFT_THIGH, BodySegment.RIGHT_THIGH,
        BodySegment.LEFT_SHIN, BodySegment.RIGHT_SHIN,
    }
    arm_set = {
        BodySegment.LEFT_UPPER_ARM, BodySegment.RIGHT_UPPER_ARM,
        BodySegment.LEFT_FOREARM, BodySegment.RIGHT_FOREARM,
    }
    leg_set = {
        BodySegment.LEFT_THIGH, BodySegment.RIGHT_THIGH,
        BodySegment.LEFT_SHIN, BodySegment.RIGHT_SHIN,
    }
    for m in BodySegment:
        tr.check(m.is_upper_body == (m in upper_set), f"BodySegment.{m.name}.is_upper_body == {m in upper_set}")
        tr.check(m.is_lower_body == (m in lower_set), f"BodySegment.{m.name}.is_lower_body == {m in lower_set}")
        tr.check(m.is_arm == (m in arm_set), f"BodySegment.{m.name}.is_arm == {m in arm_set}")
        tr.check(m.is_leg == (m in leg_set), f"BodySegment.{m.name}.is_leg == {m in leg_set}")


def test_19_bounding_box_creation(tr: TestResult) -> None:
    """[19] BoundingBox - 생성 및 프로퍼티"""
    tr.set_section("[19] BoundingBox - 생성 및 프로퍼티")
    bb = BoundingBox(10.0, 20.0, 100.0, 200.0, 0.95)
    tr.check(bb.x == 10.0, "bb.x == 10.0")
    tr.check(bb.y == 20.0, "bb.y == 20.0")
    tr.check(bb.width == 100.0, "bb.width == 100.0")
    tr.check(bb.height == 200.0, "bb.height == 200.0")
    tr.check(bb.confidence == 0.95, "bb.confidence == 0.95")
    tr.check(bb.x_center == 60.0, f"bb.x_center == 60.0 (실제: {bb.x_center})")
    tr.check(bb.y_center == 120.0, f"bb.y_center == 120.0 (실제: {bb.y_center})")
    tr.check(bb.center == (60.0, 120.0), f"bb.center == (60.0, 120.0)")
    tr.check(bb.area == 20000.0, f"bb.area == 20000.0 (실제: {bb.area})")
    tr.check(bb.x_max == 110.0, f"bb.x_max == 110.0 (실제: {bb.x_max})")
    tr.check(bb.y_max == 220.0, f"bb.y_max == 220.0 (실제: {bb.y_max})")
    tr.check(bb.xyxy == (10.0, 20.0, 110.0, 220.0), "bb.xyxy 형식 확인")
    tr.check(bb.xywh == (10.0, 20.0, 100.0, 200.0), "bb.xywh 형식 확인")

    # 기본 신뢰도
    bb2 = BoundingBox(0, 0, 50, 50)
    tr.check(bb2.confidence == 0.0, "기본 confidence == 0.0")
    tr.check(bb2.area == 2500.0, "bb2.area == 2500.0")


def test_20_bounding_box_normalize_absolute(tr: TestResult) -> None:
    """[20] BoundingBox - to_normalized/to_absolute"""
    tr.set_section("[20] BoundingBox - to_normalized/to_absolute")
    bb = BoundingBox(100.0, 200.0, 50.0, 100.0, 0.9)
    norm = bb.to_normalized(1000, 1000)
    tr.check(abs(norm.x - 0.1) < 1e-6, f"norm.x == 0.1 (실제: {norm.x})")
    tr.check(abs(norm.y - 0.2) < 1e-6, f"norm.y == 0.2 (실제: {norm.y})")
    tr.check(abs(norm.width - 0.05) < 1e-6, f"norm.width == 0.05 (실제: {norm.width})")
    tr.check(abs(norm.height - 0.1) < 1e-6, f"norm.height == 0.1 (실제: {norm.height})")
    tr.check(norm.confidence == 0.9, "norm.confidence 유지")

    # 라운드트립
    restored = norm.to_absolute(1000, 1000)
    tr.check(abs(restored.x - 100.0) < 1e-4, f"라운드트립 x == 100.0 (실제: {restored.x})")


def test_21_bounding_box_iou(tr: TestResult) -> None:
    """[21] BoundingBox - iou"""
    tr.set_section("[21] BoundingBox - iou")
    bb1 = BoundingBox(0, 0, 100, 100)
    bb2 = BoundingBox(0, 0, 100, 100)
    tr.check(abs(bb1.iou(bb2) - 1.0) < 1e-6, "완전 겹침 IoU == 1.0")

    bb3 = BoundingBox(200, 200, 100, 100)
    tr.check(bb1.iou(bb3) == 0.0, "겹침 없음 IoU == 0.0")

    bb4 = BoundingBox(50, 50, 100, 100)
    iou_val = bb1.iou(bb4)
    # 교집합: (50,50)~(100,100) = 50*50 = 2500
    # 합집합: 10000 + 10000 - 2500 = 17500
    expected_iou = 2500.0 / 17500.0
    tr.check(abs(iou_val - expected_iou) < 1e-6, f"부분 겹침 IoU ~= {expected_iou:.4f} (실제: {iou_val:.4f})")

    # 자기 자신과의 IoU
    tr.check(abs(bb1.iou(bb1) - 1.0) < 1e-6, "자기 자신 IoU == 1.0")

    # 인접하지만 겹침 없음
    bb5 = BoundingBox(100, 0, 100, 100)
    tr.check(bb1.iou(bb5) == 0.0, "인접 (경계 공유) IoU == 0.0")


def test_22_bounding_box_contains_expand(tr: TestResult) -> None:
    """[22] BoundingBox - contains_point/expand"""
    tr.set_section("[22] BoundingBox - contains_point/expand")
    bb = BoundingBox(10, 20, 100, 200)
    tr.check(bb.contains_point(50, 100) is True, "내부 점 포함")
    tr.check(bb.contains_point(10, 20) is True, "좌상단 경계 포함")
    tr.check(bb.contains_point(110, 220) is True, "우하단 경계 포함")
    tr.check(bb.contains_point(5, 100) is False, "왼쪽 외부 미포함")
    tr.check(bb.contains_point(50, 250) is False, "아래 외부 미포함")

    # expand
    expanded = bb.expand(0.2)
    tr.check(expanded.width > bb.width, f"expand 후 너비 증가 ({expanded.width} > {bb.width})")
    tr.check(expanded.height > bb.height, f"expand 후 높이 증가 ({expanded.height} > {bb.height})")
    expected_w = 100.0 * 1.2
    expected_h = 200.0 * 1.2
    tr.check(abs(expanded.width - expected_w) < 1e-6, f"expand 너비 == {expected_w}")
    tr.check(abs(expanded.height - expected_h) < 1e-6, f"expand 높이 == {expected_h}")


def test_23_detected_object(tr: TestResult) -> None:
    """[23] DetectedObject"""
    tr.set_section("[23] DetectedObject")
    bb = BoundingBox(10, 20, 50, 50, 0.93)
    obj = DetectedObject(
        target_type=DetectionTarget.PLAYER, bounding_box=bb,
        object_id=42, class_name="player_home",
    )
    tr.check(obj.target_type == DetectionTarget.PLAYER, "target_type == PLAYER")
    tr.check(obj.confidence == 0.93, "confidence 프로퍼티 == 0.93")
    tr.check(obj.object_id == 42, "object_id == 42")
    tr.check(obj.class_name == "player_home", "class_name == 'player_home'")
    tr.check(isinstance(obj.attributes, dict), "attributes는 dict")


def test_24_detection_result_factory(tr: TestResult) -> None:
    """[24] DetectionResult - success/failure/count"""
    tr.set_section("[24] DetectionResult - success/failure/count")
    obj1 = DetectedObject(DetectionTarget.PLAYER, BoundingBox(10, 10, 50, 50, 0.9))
    obj2 = DetectedObject(DetectionTarget.BALL, BoundingBox(100, 100, 30, 30, 0.85))
    obj3 = DetectedObject(DetectionTarget.PLAYER, BoundingBox(200, 200, 60, 60, 0.70))

    # success_result
    sr = DetectionResult.success_result(
        [obj1, obj2, obj3], frame_index=5, timestamp_ms=100.0,
        processing_time_ms=15.0, metadata={"key": "val"},
    )
    tr.check(sr.success is True, "success_result.success == True")
    tr.check(sr.count == 3, f"success_result.count == 3 (실제: {sr.count})")
    tr.check(sr.frame_index == 5, "frame_index == 5")
    tr.check(sr.timestamp_ms == 100.0, "timestamp_ms == 100.0")
    tr.check(sr.processing_time_ms == 15.0, "processing_time_ms == 15.0")
    tr.check(sr.metadata.get("key") == "val", "metadata 포함")
    tr.check(sr.error_message is None, "error_message is None")

    # failure_result
    fr = DetectionResult.failure_result("test error", frame_index=10)
    tr.check(fr.success is False, "failure_result.success == False")
    tr.check(fr.error_message == "test error", "error_message == 'test error'")
    tr.check(fr.count == 0, "failure count == 0")
    tr.check(fr.frame_index == 10, "failure frame_index == 10")

    # count_by_type
    tr.check(sr.count_by_type(DetectionTarget.PLAYER) == 2, "count_by_type(PLAYER) == 2")
    tr.check(sr.count_by_type(DetectionTarget.BALL) == 1, "count_by_type(BALL) == 1")
    tr.check(sr.count_by_type(DetectionTarget.HOOP) == 0, "count_by_type(HOOP) == 0")


def test_25_detection_result_filter(tr: TestResult) -> None:
    """[25] DetectionResult - filter"""
    tr.set_section("[25] DetectionResult - filter")
    objs = [
        DetectedObject(DetectionTarget.PLAYER, BoundingBox(0, 0, 50, 50, 0.95)),
        DetectedObject(DetectionTarget.PLAYER, BoundingBox(100, 100, 50, 50, 0.60)),
        DetectedObject(DetectionTarget.BALL, BoundingBox(200, 200, 30, 30, 0.88)),
        DetectedObject(DetectionTarget.HOOP, BoundingBox(300, 50, 80, 80, 0.40)),
    ]
    dr = DetectionResult.success_result(objs)

    # filter_by_type
    players = dr.filter_by_type(DetectionTarget.PLAYER)
    tr.check(len(players) == 2, f"filter_by_type(PLAYER) == 2 (실제: {len(players)})")
    balls = dr.filter_by_type(DetectionTarget.BALL)
    tr.check(len(balls) == 1, f"filter_by_type(BALL) == 1 (실제: {len(balls)})")
    hoops = dr.filter_by_type(DetectionTarget.HOOP)
    tr.check(len(hoops) == 1, "filter_by_type(HOOP) == 1")
    referees = dr.filter_by_type(DetectionTarget.REFEREE)
    tr.check(len(referees) == 0, "filter_by_type(REFEREE) == 0")

    # filter_by_confidence
    high_conf = dr.filter_by_confidence(0.85)
    tr.check(len(high_conf) == 2, f"filter_by_confidence(0.85) == 2 (실제: {len(high_conf)})")
    mid_conf = dr.filter_by_confidence(0.50)
    tr.check(len(mid_conf) == 3, f"filter_by_confidence(0.50) == 3 (실제: {len(mid_conf)})")
    ultra = dr.filter_by_confidence(0.99)
    tr.check(len(ultra) == 0, "filter_by_confidence(0.99) == 0")


def test_26_frame_data_from_array(tr: TestResult) -> None:
    """[26] FrameData - from_array/프로퍼티"""
    tr.set_section("[26] FrameData - from_array/프로퍼티")
    frame_arr = np.zeros((480, 640, 3), dtype=np.uint8)
    fd = FrameData.from_array(
        frame_arr, frame_index=10, timestamp_ms=333.3,
        color_format=ColorFormat.BGR, fps=30.0,
        source_path="/test/video.mp4",
        metadata={"key": "val"},
    )
    tr.check(fd.width == 640, f"width == 640 (실제: {fd.width})")
    tr.check(fd.height == 480, f"height == 480 (실제: {fd.height})")
    tr.check(fd.channels == 3, f"channels == 3 (실제: {fd.channels})")
    tr.check(fd.frame_index == 10, "frame_index == 10")
    tr.check(fd.timestamp_ms == 333.3, "timestamp_ms == 333.3")
    tr.check(fd.color_format == ColorFormat.BGR, "color_format == BGR")
    tr.check(fd.fps == 30.0, "fps == 30.0")
    tr.check(fd.source_path == "/test/video.mp4", "source_path 확인")
    tr.check(fd.metadata.get("key") == "val", "metadata 확인")

    # 프로퍼티
    tr.check(fd.resolution == (640, 480), f"resolution == (640, 480)")
    tr.check(fd.shape == (480, 640, 3), f"shape == (480, 640, 3)")
    tr.check(fd.size_bytes == 480 * 640 * 3, f"size_bytes == {480 * 640 * 3}")
    tr.check(abs(fd.aspect_ratio - 640 / 480) < 1e-6, f"aspect_ratio ~= {640 / 480:.4f}")
    tr.check(abs(fd.timestamp_sec - 0.3333) < 1e-3, f"timestamp_sec ~= 0.333")
    tr.check(fd.is_grayscale is False, "is_grayscale == False")

    # 그레이스케일
    gray_arr = np.zeros((240, 320), dtype=np.uint8)
    fd_gray = FrameData.from_array(gray_arr, color_format=ColorFormat.GRAY)
    tr.check(fd_gray.channels == 1, "gray channels == 1")
    tr.check(fd_gray.is_grayscale is True, "gray is_grayscale == True")


def test_27_frame_data_is_valid(tr: TestResult) -> None:
    """[27] FrameData - is_valid"""
    tr.set_section("[27] FrameData - is_valid")
    valid_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    fd_valid = FrameData.from_array(valid_frame, frame_index=0)
    tr.check(fd_valid.is_valid is True, "유효한 프레임 is_valid == True")

    # None 프레임
    fd_none = FrameData(frame=None, frame_index=0, timestamp_ms=0.0, width=0, height=0)
    tr.check(fd_none.is_valid is False, "None 프레임 is_valid == False")

    # 음수 frame_index
    fd_neg = FrameData(frame=valid_frame, frame_index=-1, timestamp_ms=0.0,
                       width=640, height=480)
    tr.check(fd_neg.is_valid is False, "음수 frame_index is_valid == False")

    # 0 크기
    fd_zero = FrameData(frame=None, frame_index=0, timestamp_ms=0.0,
                        width=0, height=0)
    tr.check(fd_zero.is_valid is False, "0 크기 is_valid == False")

    # copy
    fd_copy = fd_valid.copy()
    tr.check(fd_copy.is_valid is True, "copy된 프레임 is_valid == True")


def test_28_detector_metrics(tr: TestResult) -> None:
    """[28] DetectorMetrics"""
    tr.set_section("[28] DetectorMetrics")
    dm = DetectorMetrics()
    tr.check(dm.total_frames_processed == 0, "초기 total_frames_processed == 0")
    tr.check(dm.total_objects_detected == 0, "초기 total_objects_detected == 0")
    tr.check(dm.average_processing_time_ms == 0.0, "초기 average_processing_time_ms == 0.0")
    tr.check(dm.current_fps == 0.0, "초기 current_fps == 0.0")
    tr.check(dm.last_error is None, "초기 last_error is None")
    tr.check(dm.peak_memory_mb == 0.0, "초기 peak_memory_mb == 0.0")

    # update with success
    obj = DetectedObject(DetectionTarget.PLAYER, BoundingBox(10, 20, 100, 200, 0.95))
    sr = DetectionResult.success_result([obj], processing_time_ms=10.0)
    dm.update(sr)
    tr.check(dm.total_frames_processed == 1, "update 후 frames == 1")
    tr.check(dm.total_objects_detected == 1, "update 후 objects == 1")
    tr.check(dm.average_processing_time_ms == 10.0, "average_processing_time == 10.0")
    tr.check(dm.current_fps > 0, f"current_fps > 0 (실제: {dm.current_fps})")
    tr.check(dm.detection_counts.get("player") == 1, "detection_counts['player'] == 1")

    # update with failure
    fr = DetectionResult.failure_result("test error", frame_index=1)
    fr.processing_time_ms = 5.0
    dm.update(fr)
    tr.check(dm.total_frames_processed == 2, "failure update 후 frames == 2")
    tr.check(dm.last_error == "test error", "last_error 설정됨")


def test_29_idetector_abc(tr: TestResult) -> None:
    """[29] IDetector - ABC/validate_frame"""
    tr.set_section("[29] IDetector - ABC/validate_frame")
    tr.check(issubclass(IDetector, ABC), "IDetector은 ABC 서브클래스")

    stub = StubDetector()
    tr.check(stub.name == "StubDetector", "stub.name == 'StubDetector'")
    tr.check(stub.version == "1.0.0", "stub.version == '1.0.0'")
    tr.check(stub.state == DetectionState.UNINITIALIZED, "초기 state == UNINITIALIZED")
    tr.check(DetectionTarget.PLAYER in stub.supported_targets, "PLAYER in supported_targets")

    # initialize
    stub.initialize({})
    tr.check(stub.state == DetectionState.READY, "initialize 후 state == READY")

    # detect
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = stub.detect(frame, frame_index=5)
    tr.check(result.success is True, "detect 성공")
    tr.check(result.count == 1, "detect count == 1")

    # validate_frame
    tr.check(stub.validate_frame(frame) is True, "유효 프레임 validate == True")
    tr.check(stub.validate_frame(None) is False, "None validate == False")
    gray = np.zeros((480, 640), dtype=np.uint8)
    tr.check(stub.validate_frame(gray) is False, "2D 배열 validate == False")

    # reset / shutdown
    stub.reset()
    tr.check(stub.state == DetectionState.UNINITIALIZED, "reset 후 UNINITIALIZED")
    stub.shutdown()
    tr.check(stub.state == DetectionState.SHUTDOWN, "shutdown 후 SHUTDOWN")


def test_30_iball_detector(tr: TestResult) -> None:
    """[30] IBallDetector 스텁"""
    tr.set_section("[30] IBallDetector 스텁")
    bd = StubBallDetector()
    tr.check(bd.supported_targets == [DetectionTarget.BALL], "supported_targets == [BALL]")
    bd.initialize({})

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = bd.detect_ball(frame, frame_index=3)
    tr.check(result.success is True, "detect_ball 성공")
    tr.check(result.ball_state is not None, "ball_state 존재")
    tr.check(result.ball_state.position == (65.0, 65.0), "ball_state position 확인")

    # predict_trajectory
    traj = bd.predict_trajectory(result.ball_state, 100.0)
    tr.check(len(traj) == 2, f"predict_trajectory 길이 == 2 (실제: {len(traj)})")

    # is_ball_in_hoop_region
    hoop_region = BoundingBox(60, 60, 20, 20)
    tr.check(bd.is_ball_in_hoop_region(result.ball_state, hoop_region) is True, "공이 골대 영역 내")


def test_31_icourt_detector(tr: TestResult) -> None:
    """[31] ICourtDetector 스텁"""
    tr.set_section("[31] ICourtDetector 스텁")
    cd = StubCourtDetector()
    targets = cd.supported_targets
    tr.check(DetectionTarget.COURT in targets, "COURT in supported_targets")
    tr.check(DetectionTarget.LINE in targets, "LINE in supported_targets")
    cd.initialize({})

    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    result = cd.detect_court(frame)
    tr.check(result.success is True, "detect_court 성공")
    tr.check(result.keypoints is not None, "keypoints 존재")
    tr.check(result.court_type == "full", "court_type == 'full'")

    zone = cd.get_zone_at_position((5.0, 5.0))
    tr.check(zone == "paint", "get_zone_at_position 결과 확인")


def test_32_iplayer_detector(tr: TestResult) -> None:
    """[32] IPlayerDetector 기본값"""
    tr.set_section("[32] IPlayerDetector 기본값")
    pd = StubPlayerDetector()
    targets = pd.supported_targets
    tr.check(DetectionTarget.PLAYER in targets, "PLAYER in supported_targets")
    tr.check(DetectionTarget.REFEREE in targets, "REFEREE in supported_targets")
    pd.initialize({})

    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    result = pd.detect_players(frame, frame_index=7)
    tr.check(result.success is True, "detect_players 성공")
    tr.check(len(result.players) == 1, f"players 수 == 1 (실제: {len(result.players)})")
    tr.check(result.players[0].role == PlayerRole.PLAYER, "player role == PLAYER")

    # 기본 구현 검증
    teams = pd.assign_teams(result.players, frame)
    tr.check(teams == {}, "assign_teams 기본 구현 == {}")

    handler = pd.identify_ball_handler(result.players, (100.0, 100.0))
    tr.check(handler is None, "identify_ball_handler 기본 구현 == None")

    # PlayerDetection confidence
    tr.check(result.players[0].confidence == 0.92, "PlayerDetection.confidence == 0.92")


def test_33_ipose_estimator(tr: TestResult) -> None:
    """[33] IPoseEstimator 스텁"""
    tr.set_section("[33] IPoseEstimator 스텁")
    pe = StubPoseEstimator()
    tr.check(pe.supported_targets == [DetectionTarget.PLAYER], "supported_targets == [PLAYER]")
    pe.initialize({})

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = pe.estimate_poses(frame)
    tr.check(result.success is True, "estimate_poses 성공")
    tr.check(result.pose_count == 1, "pose_count == 1")
    tr.check(result.model_name == "stub_model", "model_name == 'stub_model'")

    pose = result.poses[0]
    angles = pe.calculate_joint_angles(pose)
    tr.check("left_elbow" in angles, "left_elbow 관절 각도 존재")


def test_34_ihoop_detector(tr: TestResult) -> None:
    """[34] IHoopDetector 스텁"""
    tr.set_section("[34] IHoopDetector 스텁")
    hd = StubHoopDetector()
    tr.check(hd.supported_targets == [DetectionTarget.HOOP], "supported_targets == [HOOP]")
    hd.initialize({})

    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    result = hd.detect_hoops(frame)
    tr.check(result.success is True, "detect_hoops 성공")
    tr.check(len(result.hoops) == 1, f"hoops 수 == 1 (실제: {len(result.hoops)})")
    tr.check(result.hoops[0].rim_center == (950.0, 100.0), "rim_center 확인")

    scored, conf = hd.detect_score([(940, 95), (950, 100)], result.hoops[0])
    tr.check(scored is True, "detect_score == True")
    tr.check(conf > 0.0, f"detect_score confidence > 0 (실제: {conf})")


def test_35_pose_estimation_methods(tr: TestResult) -> None:
    """[35] PoseEstimation 메서드"""
    tr.set_section("[35] PoseEstimation 메서드")
    kp_nose = KeypointData(PoseKeypoint.NOSE, 100.0, 50.0, 0.95)
    kp_ls = KeypointData(PoseKeypoint.LEFT_SHOULDER, 80.0, 100.0, 0.90, is_visible=True)
    kp_le = KeypointData(PoseKeypoint.LEFT_ELBOW, 70.0, 150.0, 0.85, is_visible=False)
    angle = JointAngle("left_elbow", 120.0,
                       PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_ELBOW,
                       PoseKeypoint.LEFT_WRIST, confidence=0.80)
    seg = SegmentData(BodySegment.LEFT_UPPER_ARM,
                      PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_ELBOW,
                      (80.0, 100.0), (70.0, 150.0), 50.99, 78.69)

    pe = PoseEstimation(
        person_id=1,
        keypoints={PoseKeypoint.NOSE: kp_nose, PoseKeypoint.LEFT_SHOULDER: kp_ls,
                   PoseKeypoint.LEFT_ELBOW: kp_le},
        joint_angles={"left_elbow": angle},
        segments={BodySegment.LEFT_UPPER_ARM: seg},
        overall_confidence=0.88,
    )

    tr.check(pe.get_keypoint(PoseKeypoint.NOSE) == kp_nose, "get_keypoint(NOSE) 확인")
    tr.check(pe.get_keypoint(PoseKeypoint.RIGHT_ANKLE) is None, "get_keypoint(없는 키포인트) == None")
    tr.check(pe.get_keypoint_position(PoseKeypoint.NOSE) == (100.0, 50.0), "get_keypoint_position 확인")
    tr.check(pe.get_keypoint_position(PoseKeypoint.RIGHT_HIP) is None, "get_keypoint_position(없는 키포인트) == None")
    tr.check(pe.get_joint_angle("left_elbow") == 120.0, "get_joint_angle('left_elbow') == 120.0")
    tr.check(pe.get_joint_angle("right_elbow") is None, "get_joint_angle(없는 관절) == None")
    tr.check(pe.get_segment_length(BodySegment.LEFT_UPPER_ARM) is not None, "get_segment_length 존재")
    tr.check(pe.visible_keypoint_count == 2, f"visible_keypoint_count == 2 (실제: {pe.visible_keypoint_count})")


def test_36_pose_estimation_result_factory(tr: TestResult) -> None:
    """[36] PoseEstimationResult 팩토리"""
    tr.set_section("[36] PoseEstimationResult 팩토리")
    bb = BoundingBox(10, 20, 100, 200, 0.9)
    pose = PoseEstimation(person_id=1, bounding_box=bb, overall_confidence=0.85)

    # success_result
    sr = PoseEstimationResult.success_result(
        poses=[pose], frame_index=3, model_name="yolo_pose",
    )
    tr.check(sr.success is True, "success == True")
    tr.check(sr.pose_count == 1, "pose_count == 1")
    tr.check(sr.model_name == "yolo_pose", "model_name == 'yolo_pose'")
    tr.check(len(sr.objects) == 1, "objects 생성됨 (bounding_box 있을 때)")

    # get_pose_by_id
    found = sr.get_pose_by_id(1)
    tr.check(found is not None, "get_pose_by_id(1) 찾음")
    tr.check(sr.get_pose_by_id(999) is None, "get_pose_by_id(999) == None")

    # failure_result
    fr = PoseEstimationResult.failure_result("pose error", frame_index=5)
    tr.check(fr.success is False, "failure success == False")
    tr.check(fr.pose_count == 0, "failure pose_count == 0")


def test_37_tracking_result_factory(tr: TestResult) -> None:
    """[37] TrackingResult 팩토리"""
    tr.set_section("[37] TrackingResult 팩토리")
    obj = DetectedObject(DetectionTarget.PLAYER, BoundingBox(10, 20, 50, 100, 0.90), object_id=1)

    # success_result
    sr = TrackingResult.success_result(
        tracked_objects=[obj], new_tracks=1, lost_tracks=0,
        active_tracks=1, frame_index=10, processing_time_ms=5.0,
    )
    tr.check(sr.success is True, "success == True")
    tr.check(len(sr.tracked_objects) == 1, "tracked_objects 수 == 1")
    tr.check(sr.new_tracks == 1, "new_tracks == 1")
    tr.check(sr.active_tracks == 1, "active_tracks == 1")

    # failure_result
    fr = TrackingResult.failure_result("tracking lost", frame_index=11)
    tr.check(fr.success is False, "failure success == False")
    tr.check(fr.error_message == "tracking lost", "error_message 확인")


def test_38_itracker_stub(tr: TestResult) -> None:
    """[38] ITracker 스텁/validate_detections"""
    tr.set_section("[38] ITracker 스텁/validate_detections")
    tracker = StubTracker()
    tr.check(tracker.name == "StubTracker", "name == 'StubTracker'")
    tr.check(tracker.state == DetectionState.UNINITIALIZED, "초기 state == UNINITIALIZED")
    tr.check(tracker.active_track_count == 0, "초기 active_track_count == 0")

    tracker.initialize({})
    det = DetectedObject(DetectionTarget.PLAYER, BoundingBox(100, 100, 50, 50, 0.9))
    result = tracker.update([det], frame_index=0)
    tr.check(result.success is True, "update 성공")
    tr.check(tracker.active_track_count == 1, "active_track_count == 1")
    tr.check(tracker.total_tracks_created == 1, "total_tracks_created == 1")

    # validate_detections
    tr.check(tracker.validate_detections([det]) is True, "유효 탐지 validate == True")
    tr.check(tracker.validate_detections(None) is False, "None validate == False")
    bad_det = DetectedObject(DetectionTarget.PLAYER, BoundingBox(10, 10, 0, 50, 0.5))
    tr.check(tracker.validate_detections([bad_det]) is False, "너비 0 validate == False")


def test_39_tracker_metrics(tr: TestResult) -> None:
    """[39] TrackerMetrics"""
    tr.set_section("[39] TrackerMetrics")
    tm = TrackerMetrics()
    tr.check(tm.total_frames_processed == 0, "초기 frames == 0")
    tr.check(tm.total_tracks_created == 0, "초기 tracks_created == 0")
    tr.check(tm.id_switches == 0, "초기 id_switches == 0")

    obj = DetectedObject(DetectionTarget.PLAYER, BoundingBox(10, 10, 50, 50, 0.9), object_id=1)
    tr_result = TrackingResult.success_result(
        tracked_objects=[obj], new_tracks=1, active_tracks=1,
        processing_time_ms=8.0,
    )
    tm.update(tr_result)
    tr.check(tm.total_frames_processed == 1, "update 후 frames == 1")
    tr.check(tm.total_tracks_created == 1, "update 후 tracks_created == 1")
    tr.check(tm.current_active_tracks == 1, "current_active_tracks == 1")
    tr.check(tm.current_fps > 0, f"current_fps > 0 (실제: {tm.current_fps})")


def test_40_factory_composite(tr: TestResult) -> None:
    """[40] IDetectorFactory/ICompositeDetector 스텁"""
    tr.set_section("[40] IDetectorFactory/ICompositeDetector 스텁")
    factory = StubDetectorFactory()
    types = factory.get_supported_types()
    tr.check("stub" in types, "'stub' in supported_types")

    detector = factory.create({})
    tr.check(detector.state == DetectionState.READY, "factory create -> READY")

    composite = factory.create_composite({})
    tr.check(isinstance(composite, ICompositeDetector), "create_composite -> ICompositeDetector")

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    composite.initialize({})
    all_results = composite.detect_all(frame)
    tr.check(DetectionTarget.PLAYER in all_results, "detect_all에 PLAYER 포함")
    tr.check(DetectionTarget.BALL in all_results, "detect_all에 BALL 포함")


def test_41_detection_callback(tr: TestResult) -> None:
    """[41] DetectionCallback 프로토콜"""
    tr.set_section("[41] DetectionCallback 프로토콜")
    cb = StubCallback()
    result = DetectionResult.success_result([])
    cb.on_detection_complete(result, context={"source": "test"})
    tr.check(cb.last_result is result, "on_detection_complete 호출 확인")

    err = ValueError("test error")
    cb.on_detection_error(err, frame_info=(0, 0.0))
    tr.check(cb.last_error is err, "on_detection_error 호출 확인")

    pending = cb.get_pending_detections()
    tr.check(isinstance(pending, list), "get_pending_detections 반환 타입 list")


def test_42_module_metadata(tr: TestResult) -> None:
    """[42] 모듈 메타데이터 (__version__, __all__)"""
    tr.set_section("[42] 모듈 메타데이터 (__version__, __all__)")
    import shared.interfaces.detector_interface as mod
    tr.check(hasattr(mod, "__version__"), "__version__ 존재")
    tr.check(mod.__version__ == "1.20.0", f"__version__ == '1.20.0' (실제: {mod.__version__})")
    tr.check(hasattr(mod, "__all__"), "__all__ 존재")
    tr.check(len(mod.__all__) == 37, f"__all__ 길이 == 37 (실제: {len(mod.__all__)})")


def test_43_all_exports(tr: TestResult) -> None:
    """[43] __all__ export 검증"""
    tr.set_section("[43] __all__ export 검증")
    import shared.interfaces.detector_interface as mod
    expected_exports = [
        "DetectionTarget", "DetectionState", "PlayerRole", "ColorFormat",
        "BoundingBox", "FrameData", "DetectedObject", "DetectionResult",
        "DetectorMetrics", "IDetector",
        "BallState", "BallDetectionResult", "IBallDetector",
        "CourtKeypoints", "CourtDetectionResult", "ICourtDetector",
        "PlayerDetection", "PlayerDetectionResult", "IPlayerDetector",
        "PoseKeypoint", "BodySegment",
        "KeypointData", "JointAngle", "SegmentData",
        "PoseEstimation", "PoseEstimationResult", "IPoseEstimator",
        "HoopDetection", "HoopDetectionResult", "IHoopDetector",
        "TrackingResult", "TrackState", "ITracker", "TrackerMetrics",
        "IDetectorFactory", "ICompositeDetector",
        "DetectionCallback",
    ]
    for name in expected_exports:
        tr.check(name in mod.__all__, f"'{name}' in __all__")


def test_44_init_integration(tr: TestResult) -> None:
    """[44] __init__.py integration"""
    tr.set_section("[44] __init__.py integration")
    import shared.interfaces as ifaces
    expected = [
        "DetectionTarget", "DetectionState", "PlayerRole", "ColorFormat",
        "BoundingBox", "FrameData", "DetectedObject", "DetectionResult",
        "DetectorMetrics", "IDetector",
        "BallState", "BallDetectionResult", "IBallDetector",
        "CourtKeypoints", "CourtDetectionResult", "ICourtDetector",
        "PlayerDetection", "PlayerDetectionResult", "IPlayerDetector",
        "PoseKeypoint", "BodySegment",
        "KeypointData", "JointAngle", "SegmentData",
        "PoseEstimation", "PoseEstimationResult", "IPoseEstimator",
        "HoopDetection", "HoopDetectionResult", "IHoopDetector",
        "TrackingResult", "TrackState", "ITracker", "TrackerMetrics",
        "IDetectorFactory", "ICompositeDetector",
        "DetectionCallback",
    ]
    for name in expected:
        tr.check(hasattr(ifaces, name), f"shared.interfaces.{name} accessible")


def test_45_edge_cases(tr: TestResult) -> None:
    """[45] 엣지 케이스"""
    tr.set_section("[45] 엣지 케이스")

    # BoundingBox 면적 0
    bb_zero = BoundingBox(10, 20, 0, 0)
    tr.check(bb_zero.area == 0.0, "면적 0 박스")
    tr.check(bb_zero.center == (10.0, 20.0), "면적 0 박스 center == (10, 20)")

    # IoU with zero area
    bb_normal = BoundingBox(0, 0, 100, 100)
    tr.check(bb_normal.iou(bb_zero) == 0.0, "면적 0과 IoU == 0.0")

    # DetectionResult 빈 객체
    empty_result = DetectionResult.success_result([])
    tr.check(empty_result.count == 0, "빈 결과 count == 0")
    tr.check(empty_result.success is True, "빈 결과 success == True")

    # JointAngle angle_radians
    angle = JointAngle("test", 180.0, PoseKeypoint.NOSE, PoseKeypoint.NECK, PoseKeypoint.MID_SPINE)
    tr.check(abs(angle.angle_radians - math.pi) < 1e-6, "180도 == pi 라디안")
    angle_90 = JointAngle("test", 90.0, PoseKeypoint.NOSE, PoseKeypoint.NECK, PoseKeypoint.MID_SPINE)
    tr.check(abs(angle_90.angle_radians - math.pi / 2) < 1e-6, "90도 == pi/2 라디안")

    # KeypointData position_2d / position_3d
    kp_2d = KeypointData(PoseKeypoint.NOSE, 100.0, 50.0, 0.9)
    tr.check(kp_2d.position_2d == (100.0, 50.0), "position_2d 확인")
    tr.check(kp_2d.position_3d is None, "z=None일 때 position_3d == None")

    kp_3d = KeypointData(PoseKeypoint.NOSE, 100.0, 50.0, 0.9, z=200.0)
    tr.check(kp_3d.position_3d == (100.0, 50.0, 200.0), "position_3d 확인")

    # SegmentData midpoint
    seg = SegmentData(
        BodySegment.TORSO, PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_HIP,
        (0.0, 0.0), (100.0, 200.0), 223.6, 63.43,
    )
    mx, my = seg.midpoint
    tr.check(abs(mx - 50.0) < 1e-6, f"midpoint x == 50.0 (실제: {mx})")
    tr.check(abs(my - 100.0) < 1e-6, f"midpoint y == 100.0 (실제: {my})")

    # PoseEstimation keypoint_array shape
    kp_nose = KeypointData(PoseKeypoint.NOSE, 100.0, 50.0, 0.95)
    pe = PoseEstimation(keypoints={PoseKeypoint.NOSE: kp_nose})
    arr = pe.keypoint_array
    tr.check(arr.shape == (17, 3), f"keypoint_array shape == (17, 3) (실제: {arr.shape})")
    tr.check(arr[0, 0] == 100.0, "keypoint_array[0, 0] == 100.0 (NOSE x)")
    tr.check(arr[0, 1] == 50.0, "keypoint_array[0, 1] == 50.0 (NOSE y)")
    tr.check(arr[0, 2] == 0.95, "keypoint_array[0, 2] == 0.95 (NOSE conf)")
    # 나머지는 0
    tr.check(arr[1, 0] == 0.0, "keypoint_array[1, 0] == 0.0 (LEFT_EYE x, 미할당)")

    # FrameData __post_init__ 자동 보정
    arr_frame = np.zeros((100, 200, 3), dtype=np.uint8)
    fd = FrameData(frame=arr_frame, frame_index=0, timestamp_ms=0.0, width=999, height=999)
    tr.check(fd.width == 200, f"__post_init__ width 보정: 200 (실제: {fd.width})")
    tr.check(fd.height == 100, f"__post_init__ height 보정: 100 (실제: {fd.height})")

    # TrackState 데이터클래스
    ts = TrackState(track_id=1, position=(50.0, 50.0), age=10, hits=5,
                    is_confirmed=True, confidence=0.88)
    tr.check(ts.track_id == 1, "TrackState.track_id == 1")
    tr.check(ts.is_confirmed is True, "TrackState.is_confirmed == True")
    tr.check(ts.time_since_update == 0, "기본 time_since_update == 0")

    # BallState 기본값
    bs = BallState(position=(320.0, 240.0))
    tr.check(bs.velocity is None, "BallState 기본 velocity == None")
    tr.check(bs.is_visible is True, "BallState 기본 is_visible == True")
    tr.check(bs.is_in_flight is False, "BallState 기본 is_in_flight == False")
    tr.check(bs.trajectory_points == [], "BallState 기본 trajectory_points == []")

    # CourtKeypoints 기본값
    ckp = CourtKeypoints()
    tr.check(ckp.corners == [], "CourtKeypoints 기본 corners == []")
    tr.check(ckp.center_circle is None, "CourtKeypoints 기본 center_circle == None")

    # HoopDetection 기본값
    hd = HoopDetection(
        bounding_box=BoundingBox(900, 50, 100, 100, 0.97),
        rim_center=(950.0, 100.0), rim_radius=22.5,
    )
    tr.check(hd.backboard_box is None, "HoopDetection 기본 backboard_box == None")
    tr.check(hd.net_visible is False, "HoopDetection 기본 net_visible == False")
    tr.check(hd.hoop_side is None, "HoopDetection 기본 hoop_side == None")

    # PlayerDetection 기본값
    pd = PlayerDetection(bounding_box=BoundingBox(100, 100, 50, 50, 0.85))
    tr.check(pd.role == PlayerRole.UNKNOWN, "PlayerDetection 기본 role == UNKNOWN")
    tr.check(pd.is_ball_handler is False, "PlayerDetection 기본 is_ball_handler == False")

    # BallDetectionResult 기본값
    bdr = BallDetectionResult(success=True)
    tr.check(bdr.ball_state is None, "BallDetectionResult 기본 ball_state == None")
    tr.check(bdr.prediction_confidence == 0.0, "BallDetectionResult 기본 prediction_confidence == 0.0")

    # CourtDetectionResult 기본값
    cdr = CourtDetectionResult(success=True)
    tr.check(cdr.keypoints is None, "CourtDetectionResult 기본 keypoints == None")
    tr.check(cdr.calibration_quality == 0.0, "CourtDetectionResult 기본 calibration_quality == 0.0")

    # HoopDetectionResult 기본값
    hdr = HoopDetectionResult(success=True)
    tr.check(hdr.hoops == [], "HoopDetectionResult 기본 hoops == []")

    # PlayerDetectionResult 기본값
    pdr = PlayerDetectionResult(success=True)
    tr.check(pdr.players == [], "PlayerDetectionResult 기본 players == []")
    tr.check(pdr.team_assignments == {}, "PlayerDetectionResult 기본 team_assignments == {}")

    # ITracker remove_track / get_track
    tracker = StubTracker()
    tracker.initialize({})
    det = DetectedObject(DetectionTarget.PLAYER, BoundingBox(10, 10, 50, 50, 0.9))
    tracker.update([det])
    tr.check(tracker.get_track(1) is not None, "get_track(1) 존재")
    tr.check(tracker.remove_track(1) is True, "remove_track(1) 성공")
    tr.check(tracker.get_track(1) is None, "remove 후 get_track(1) == None")
    tr.check(tracker.remove_track(999) is False, "remove_track(999) == False")

    # ITracker get_all_tracks
    tracker2 = StubTracker()
    tracker2.initialize({})
    det1 = DetectedObject(DetectionTarget.PLAYER, BoundingBox(10, 10, 50, 50, 0.9))
    det2 = DetectedObject(DetectionTarget.PLAYER, BoundingBox(100, 100, 50, 50, 0.85))
    tracker2.update([det1, det2])
    all_tracks = tracker2.get_all_tracks()
    tr.check(len(all_tracks) == 2, f"get_all_tracks 길이 == 2 (실제: {len(all_tracks)})")
    confirmed = tracker2.get_all_tracks(confirmed_only=True)
    tr.check(len(confirmed) == 2, f"confirmed_only 길이 == 2 (실제: {len(confirmed)})")

    # ITracker predict
    predictions = tracker2.predict(time_ahead_ms=100.0)
    tr.check(len(predictions) == 2, f"predict 길이 == 2 (실제: {len(predictions)})")

    # ITracker get_track_history
    history = tracker2.get_track_history(1)
    tr.check(len(history) >= 1, f"get_track_history 길이 >= 1 (실제: {len(history)})")


# =============================================================================
# 메인 함수
# =============================================================================
def main() -> None:
    tr = TestResult("detector_interface.py v1.20.0 단위 테스트")
    print("=" * 60)
    print(f"  {tr.name}")
    print("=" * 60)

    test_01_detection_target_members(tr)
    test_02_detection_target_str(tr)
    test_03_detection_target_get_name(tr)
    test_04_detection_target_to_korean(tr)
    test_05_detection_target_is_person_court_element(tr)
    test_06_detection_state_members(tr)
    test_07_detection_state_get_name(tr)
    test_08_detection_state_properties(tr)
    test_09_player_role_members(tr)
    test_10_player_role_class_id(tr)
    test_11_color_format_members(tr)
    test_12_color_format_alpha_grayscale(tr)
    test_13_pose_keypoint_members(tr)
    test_14_pose_keypoint_get_name(tr)
    test_15_pose_keypoint_coco_index(tr)
    test_16_pose_keypoint_upper_lower(tr)
    test_17_body_segment_members(tr)
    test_18_body_segment_classification(tr)
    test_19_bounding_box_creation(tr)
    test_20_bounding_box_normalize_absolute(tr)
    test_21_bounding_box_iou(tr)
    test_22_bounding_box_contains_expand(tr)
    test_23_detected_object(tr)
    test_24_detection_result_factory(tr)
    test_25_detection_result_filter(tr)
    test_26_frame_data_from_array(tr)
    test_27_frame_data_is_valid(tr)
    test_28_detector_metrics(tr)
    test_29_idetector_abc(tr)
    test_30_iball_detector(tr)
    test_31_icourt_detector(tr)
    test_32_iplayer_detector(tr)
    test_33_ipose_estimator(tr)
    test_34_ihoop_detector(tr)
    test_35_pose_estimation_methods(tr)
    test_36_pose_estimation_result_factory(tr)
    test_37_tracking_result_factory(tr)
    test_38_itracker_stub(tr)
    test_39_tracker_metrics(tr)
    test_40_factory_composite(tr)
    test_41_detection_callback(tr)
    test_42_module_metadata(tr)
    test_43_all_exports(tr)
    test_44_init_integration(tr)
    test_45_edge_cases(tr)

    tr.summary()


if __name__ == "__main__":
    main()
