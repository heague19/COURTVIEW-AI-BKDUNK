# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_motion_dto.py

동작 감지/분류 DTO 유닛 테스트
- 모듈 구조 (__version__, __all__, typing 모던화)
- 6 Enum: ActionType(11), ContestLevel(4), DribbleType(13),
          PassType(11), DefensiveActionType(11), MovementType(12)
- MotionFeatureVector (5 dict 필드)
- ActionClassification (UUID, duration, is_reliable)
- ShootingMotion (ShotType 참조, is_three_pointer)
- DribblingMotion / PassingMotion / DefensiveMotion / MovementMotion
- MotionDetectionResult (total_actions, high_confidence_actions)

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path
from uuid import UUID

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
            self.fail(name, f"{actual!r} != {expected!r}")

    def true(self, name: str, condition: bool) -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, "condition is False")

    def near(self, name: str, actual: float, expected: float, tol: float = 1e-6) -> None:
        if abs(actual - expected) < tol:
            self.ok(name)
        else:
            self.fail(name, f"{actual} != {expected} (tol={tol})")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ==================== 1. 모듈 구조 ====================
def test_module_structure(r: TestResult) -> None:
    """모듈 메타데이터 및 구조 검증"""
    import shared.dto.motion_dto as mod

    r.eq("__version__ == 1.1.0", mod.__version__, "1.1.0")
    r.eq("__all__ 항목 수 == 16", len(mod.__all__), 16)

    import inspect
    source = inspect.getsource(mod)
    legacy_count = sum(
        source.count(pat) for pat in ["Optional[", "List[", "Dict[", "Tuple[", "Union["]
    )
    r.eq("레거시 typing 없음", legacy_count, 0)
    r.true("typing 임포트 없음", "from typing" not in source)


# ==================== 2. ActionType ====================
def test_action_type(r: TestResult) -> None:
    """ActionType 열거형 검증 (11 members)"""
    from shared.dto.motion_dto import ActionType

    r.eq("ActionType 멤버 수", len(ActionType), 11)
    r.eq("SHOOTING.value", ActionType.SHOOTING.value, "shooting")
    r.eq("DRIBBLING.value", ActionType.DRIBBLING.value, "dribbling")
    r.eq("PASSING.value", ActionType.PASSING.value, "passing")
    r.eq("MOVEMENT.value", ActionType.MOVEMENT.value, "movement")
    r.eq("REBOUNDING.value", ActionType.REBOUNDING.value, "rebounding")
    r.eq("str(DRIVING)", str(ActionType.DRIVING), "driving")
    r.true("str 상속", isinstance(ActionType.CUTTING, str))


# ==================== 3. ContestLevel ====================
def test_contest_level(r: TestResult) -> None:
    """ContestLevel 열거형 검증 (4 members)"""
    from shared.dto.motion_dto import ContestLevel

    r.eq("ContestLevel 멤버 수", len(ContestLevel), 4)
    expected = ["open", "lightly_contested", "contested", "heavily_contested"]
    actual = [m.value for m in ContestLevel]
    r.eq("ContestLevel 값 순서", actual, expected)
    r.eq("str(OPEN)", str(ContestLevel.OPEN), "open")


# ==================== 4. DribbleType ====================
def test_dribble_type(r: TestResult) -> None:
    """DribbleType 열거형 검증 (13 members)"""
    from shared.dto.motion_dto import DribbleType

    r.eq("DribbleType 멤버 수", len(DribbleType), 13)
    r.eq("CROSSOVER.value", DribbleType.CROSSOVER.value, "crossover")
    r.eq("EURO_STEP.value", DribbleType.EURO_STEP.value, "euro_step")
    r.eq("SHAMGOD.value", DribbleType.SHAMGOD.value, "shamgod")
    r.eq("str(SPIN)", str(DribbleType.SPIN), "spin")


# ==================== 5. PassType ====================
def test_pass_type(r: TestResult) -> None:
    """PassType 열거형 검증 (11 members)"""
    from shared.dto.motion_dto import PassType

    r.eq("PassType 멤버 수", len(PassType), 11)
    r.eq("CHEST.value", PassType.CHEST.value, "chest")
    r.eq("LOB.value", PassType.LOB.value, "lob")
    r.eq("NO_LOOK.value", PassType.NO_LOOK.value, "no_look")
    r.eq("POCKET.value", PassType.POCKET.value, "pocket")


# ==================== 6. DefensiveActionType ====================
def test_defensive_action_type(r: TestResult) -> None:
    """DefensiveActionType 열거형 검증 (11 members)"""
    from shared.dto.motion_dto import DefensiveActionType

    r.eq("DefensiveActionType 멤버 수", len(DefensiveActionType), 11)
    r.eq("ON_BALL.value", DefensiveActionType.ON_BALL.value, "on_ball")
    r.eq("CLOSE_OUT.value", DefensiveActionType.CLOSE_OUT.value, "close_out")
    r.eq("HEDGE.value", DefensiveActionType.HEDGE.value, "hedge")
    r.eq("DROP.value", DefensiveActionType.DROP.value, "drop")


# ==================== 7. MovementType ====================
def test_movement_type(r: TestResult) -> None:
    """MovementType 열거형 검증 (12 members)"""
    from shared.dto.motion_dto import MovementType

    r.eq("MovementType 멤버 수", len(MovementType), 12)
    r.eq("SPRINT.value", MovementType.SPRINT.value, "sprint")
    r.eq("V_CUT.value", MovementType.V_CUT.value, "v_cut")
    r.eq("POST_UP.value", MovementType.POST_UP.value, "post_up")
    r.eq("STAND.value", MovementType.STAND.value, "stand")


# ==================== 8. DeceptionType ====================
def test_deception_type(r: TestResult) -> None:
    """DeceptionType 열거형 검증 (8 members)"""
    from shared.dto.motion_dto import DeceptionType

    r.eq("DeceptionType 멤버 수", len(DeceptionType), 8)
    r.eq("FLOP.value", DeceptionType.FLOP.value, "flop")
    r.eq("EXAGGERATED_CONTACT.value", DeceptionType.EXAGGERATED_CONTACT.value, "exaggerated_contact")
    r.eq("HEAD_SNAP.value", DeceptionType.HEAD_SNAP.value, "head_snap")
    r.eq("FAKE_INJURY.value", DeceptionType.FAKE_INJURY.value, "fake_injury")
    r.eq("PUMP_FAKE_DRAW.value", DeceptionType.PUMP_FAKE_DRAW.value, "pump_fake_draw")
    r.eq("KICK_OUT.value", DeceptionType.KICK_OUT.value, "kick_out")
    r.eq("CHARGE_FLOP.value", DeceptionType.CHARGE_FLOP.value, "charge_flop")
    r.eq("RECKLESS_UNDERCUT.value", DeceptionType.RECKLESS_UNDERCUT.value, "reckless_undercut")
    r.eq("str(FLOP)", str(DeceptionType.FLOP), "flop")
    r.true("str 상속", isinstance(DeceptionType.HEAD_SNAP, str))


# ==================== 9. FloppingDetection ====================
def test_flopping_detection(r: TestResult) -> None:
    """FloppingDetection 데이터클래스 검증 (11 fields)"""
    from shared.dto.motion_dto import FloppingDetection, DeceptionType

    # 기본값
    fd = FloppingDetection()
    r.eq("player_tracking_id 기본", fd.player_tracking_id, 0)
    r.eq("deception_type 기본", fd.deception_type, DeceptionType.FLOP)
    r.eq("confidence 기본", fd.confidence, 0.0)
    r.eq("contact_force_estimate 기본", fd.contact_force_estimate, 0.0)
    r.eq("reaction_magnitude 기본", fd.reaction_magnitude, 0.0)
    r.eq("reaction_proportionality 기본", fd.reaction_proportionality, 0.0)
    r.eq("biomechanical_plausibility 기본", fd.biomechanical_plausibility, 0.0)
    r.eq("center_of_gravity_shift 기본", fd.center_of_gravity_shift, 0.0)
    r.eq("start_frame 기본", fd.start_frame, 0)
    r.eq("end_frame 기본", fd.end_frame, 0)
    r.eq("timestamp 기본", fd.timestamp, 0.0)

    # 전체 인자
    fd2 = FloppingDetection(
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
    r.eq("player_tracking_id", fd2.player_tracking_id, 5)
    r.eq("deception_type EXAGGERATED", fd2.deception_type, DeceptionType.EXAGGERATED_CONTACT)
    r.near("confidence", fd2.confidence, 0.88)
    r.near("contact_force_estimate", fd2.contact_force_estimate, 120.5)
    r.near("reaction_magnitude", fd2.reaction_magnitude, 350.0)
    r.near("biomechanical_plausibility", fd2.biomechanical_plausibility, 0.25)
    r.eq("start_frame", fd2.start_frame, 1500)
    r.eq("end_frame", fd2.end_frame, 1530)
    r.near("timestamp", fd2.timestamp, 50.0)

    # 필드 수
    from dataclasses import fields
    r.eq("FloppingDetection 필드 수", len(fields(FloppingDetection)), 11)


# ==================== 10. MotionFeatureVector ====================
def test_motion_feature_vector(r: TestResult) -> None:
    """MotionFeatureVector 데이터클래스 검증"""
    from shared.dto.motion_dto import MotionFeatureVector

    # 기본값
    fv = MotionFeatureVector()
    r.eq("posture_features 빈 dict", fv.posture_features, {})
    r.eq("velocity_features 빈 dict", fv.velocity_features, {})
    r.eq("acceleration_features 빈 dict", fv.acceleration_features, {})
    r.eq("trajectory_features 빈 dict", fv.trajectory_features, {})
    r.eq("contact_features 빈 dict", fv.contact_features, {})

    # dict 독립성
    fv2 = MotionFeatureVector()
    r.true("posture_features 독립", fv.posture_features is not fv2.posture_features)

    # 값 채우기
    fv3 = MotionFeatureVector(
        posture_features={"elbow_angle": 90.0, "knee_angle": 120.0},
        velocity_features={"wrist_speed": 5.2},
        contact_features={"ball_in_hand": True},
    )
    r.near("elbow_angle", fv3.posture_features["elbow_angle"], 90.0)
    r.true("ball_in_hand", fv3.contact_features["ball_in_hand"])


# ==================== 9. ActionClassification ====================
def test_action_classification(r: TestResult) -> None:
    """ActionClassification 데이터클래스 검증"""
    from shared.dto.motion_dto import ActionClassification, ActionType, MotionFeatureVector

    # 기본값
    ac = ActionClassification()
    r.true("classification_id는 UUID", isinstance(ac.classification_id, UUID))
    r.eq("기본 action_type", ac.action_type, ActionType.MOVEMENT)
    r.true("sub_type is None", ac.sub_type is None)
    r.eq("기본 confidence", ac.confidence, 0.0)
    r.true("features is None", ac.features is None)

    # 프로퍼티 테스트
    ac2 = ActionClassification(
        player_tracking_id=3,
        action_type=ActionType.SHOOTING,
        sub_type="jump_shot",
        confidence=0.92,
        start_frame=100, end_frame=130,
        start_time=3.33, end_time=4.33,
    )
    r.eq("duration_frames", ac2.duration_frames, 30)
    r.near("duration_seconds", ac2.duration_seconds, 1.0)
    r.true("is_reliable (0.92)", ac2.is_reliable)

    # 낮은 신뢰도
    ac3 = ActionClassification(confidence=0.5)
    r.true("is_reliable False (0.5)", not ac3.is_reliable)

    # 경계값: 0.7 정확히
    ac4 = ActionClassification(confidence=0.7)
    r.true("is_reliable True (0.7)", ac4.is_reliable)

    # duration: start > end → 0
    ac5 = ActionClassification(start_frame=100, end_frame=50, start_time=5.0, end_time=3.0)
    r.eq("duration_frames 음수→0", ac5.duration_frames, 0)
    r.near("duration_seconds 음수→0", ac5.duration_seconds, 0.0)

    # features 연결
    fv = MotionFeatureVector(posture_features={"angle": 45.0})
    ac6 = ActionClassification(features=fv)
    r.true("features 연결됨", ac6.features is not None)
    r.near("features.posture angle", ac6.features.posture_features["angle"], 45.0)

    # UUID 독립성
    ac7 = ActionClassification()
    r.true("UUID 독립성", ac.classification_id != ac7.classification_id)


# ==================== 10. ShootingMotion ====================
def test_shooting_motion(r: TestResult) -> None:
    """ShootingMotion 데이터클래스 검증"""
    from shared.dto.motion_dto import ShootingMotion, ContestLevel
    from shared.constants.game_rule_constants import ShotType

    # 기본값
    sm = ShootingMotion()
    r.eq("기본 shot_type", sm.shot_type, ShotType.JUMP_SHOT)
    r.eq("기본 contest_level", sm.contest_level, ContestLevel.OPEN)
    r.eq("기본 release_angle", sm.release_angle, 0.0)

    # 3점슛 판정
    sm2 = ShootingMotion(distance_meters=7.5)
    r.true("is_three_pointer (7.5m)", sm2.is_three_pointer)

    sm3 = ShootingMotion(distance_meters=6.74)
    r.true("not three_pointer (6.74m)", not sm3.is_three_pointer)

    # 경계값 6.75m
    sm4 = ShootingMotion(distance_meters=6.75)
    r.true("is_three_pointer (6.75m 경계)", sm4.is_three_pointer)

    # 전체 인자
    sm5 = ShootingMotion(
        player_tracking_id=7,
        shot_type=ShotType.LAYUP,
        release_angle=52.0,
        release_height=2.45,
        arc_height=0.8,
        release_speed=7.2,
        shot_quality=85.0,
        contest_level=ContestLevel.CONTESTED,
        distance_meters=1.5,
        court_x=0.3, court_y=-0.8,
        start_frame=200, end_frame=220,
    )
    r.eq("shot_type LAYUP", sm5.shot_type, ShotType.LAYUP)
    r.near("release_angle", sm5.release_angle, 52.0)
    r.near("shot_quality", sm5.shot_quality, 85.0)
    r.true("not three (1.5m)", not sm5.is_three_pointer)


# ==================== 11. DribblingMotion ====================
def test_dribbling_motion(r: TestResult) -> None:
    """DribblingMotion 데이터클래스 검증"""
    from shared.dto.motion_dto import DribblingMotion, DribbleType

    dm = DribblingMotion()
    r.eq("기본 dribble_type", dm.dribble_type, DribbleType.CONTROL_DRIBBLE)
    r.eq("기본 hand_used", dm.hand_used, "right")

    dm2 = DribblingMotion(
        player_tracking_id=5,
        dribble_type=DribbleType.CROSSOVER,
        hand_used="left",
        bounce_frequency=3.5,
        ball_height_variation=25.0,
        control_quality=88.0,
        speed=4.2,
        direction_changes=3,
        start_frame=500, end_frame=560,
    )
    r.eq("dribble_type CROSSOVER", dm2.dribble_type, DribbleType.CROSSOVER)
    r.eq("hand_used left", dm2.hand_used, "left")
    r.near("bounce_frequency", dm2.bounce_frequency, 3.5)
    r.eq("direction_changes", dm2.direction_changes, 3)


# ==================== 12. PassingMotion ====================
def test_passing_motion(r: TestResult) -> None:
    """PassingMotion 데이터클래스 검증"""
    from shared.dto.motion_dto import PassingMotion, PassType

    pm = PassingMotion()
    r.eq("기본 pass_type", pm.pass_type, PassType.CHEST)
    r.true("receiver_tracking_id is None", pm.receiver_tracking_id is None)

    pm2 = PassingMotion(
        passer_tracking_id=1,
        receiver_tracking_id=5,
        pass_type=PassType.LOB,
        ball_speed=8.5,
        trajectory_arc=45.0,
        distance_meters=6.0,
        accuracy=92.0,
        release_time_ms=280.0,
        start_frame=300, end_frame=330,
    )
    r.eq("pass_type LOB", pm2.pass_type, PassType.LOB)
    r.eq("receiver_tracking_id", pm2.receiver_tracking_id, 5)
    r.near("ball_speed", pm2.ball_speed, 8.5)
    r.near("accuracy", pm2.accuracy, 92.0)


# ==================== 13. DefensiveMotion ====================
def test_defensive_motion(r: TestResult) -> None:
    """DefensiveMotion 데이터클래스 검증"""
    from shared.dto.motion_dto import DefensiveMotion, DefensiveActionType

    dfm = DefensiveMotion()
    r.eq("기본 action_type", dfm.action_type, DefensiveActionType.ON_BALL)
    r.true("offensive_player is None", dfm.offensive_player_tracking_id is None)
    r.true("body_between_basket False", not dfm.body_between_basket)
    r.true("hands_active False", not dfm.hands_active)

    dfm2 = DefensiveMotion(
        defender_tracking_id=8,
        offensive_player_tracking_id=3,
        action_type=DefensiveActionType.CLOSE_OUT,
        distance_to_player=1.8,
        pressure_level=75.0,
        body_between_basket=True,
        hands_active=True,
        start_frame=400, end_frame=430,
    )
    r.eq("action_type CLOSE_OUT", dfm2.action_type, DefensiveActionType.CLOSE_OUT)
    r.near("distance_to_player", dfm2.distance_to_player, 1.8)
    r.true("body_between_basket", dfm2.body_between_basket)


# ==================== 14. MovementMotion ====================
def test_movement_motion(r: TestResult) -> None:
    """MovementMotion 데이터클래스 검증"""
    from shared.dto.motion_dto import MovementMotion, MovementType

    mm = MovementMotion()
    r.eq("기본 movement_type", mm.movement_type, MovementType.STAND)
    r.eq("기본 speed", mm.speed, 0.0)

    mm2 = MovementMotion(
        player_tracking_id=2,
        movement_type=MovementType.SPRINT,
        speed=8.5,
        direction=45.0,
        distance_covered=12.0,
        acceleration_peak=4.5,
        start_frame=100, end_frame=200,
    )
    r.eq("movement_type SPRINT", mm2.movement_type, MovementType.SPRINT)
    r.near("speed", mm2.speed, 8.5)
    r.near("direction", mm2.direction, 45.0)
    r.near("acceleration_peak", mm2.acceleration_peak, 4.5)


# ==================== 15. MotionDetectionResult ====================
def test_motion_detection_result(r: TestResult) -> None:
    """MotionDetectionResult 데이터클래스 검증"""
    from shared.dto.motion_dto import (
        MotionDetectionResult, ActionClassification, ActionType,
        ShootingMotion, DribblingMotion, PassingMotion,
        DefensiveMotion, MovementMotion,
        FloppingDetection, DeceptionType,
    )

    # 기본값
    mdr = MotionDetectionResult()
    r.eq("기본 frame_index", mdr.frame_index, 0)
    r.eq("기본 actions 빈 리스트", mdr.actions, [])
    r.eq("기본 flopping_detections 빈 리스트", mdr.flopping_detections, [])
    r.eq("total_actions (빈)", mdr.total_actions, 0)
    r.eq("high_confidence_actions (빈)", mdr.high_confidence_actions, [])

    # actions 채우기
    a1 = ActionClassification(action_type=ActionType.SHOOTING, confidence=0.95)
    a2 = ActionClassification(action_type=ActionType.DRIBBLING, confidence=0.60)
    a3 = ActionClassification(action_type=ActionType.PASSING, confidence=0.85)

    flop1 = FloppingDetection(
        player_tracking_id=3, deception_type=DeceptionType.HEAD_SNAP, confidence=0.82,
    )
    flop2 = FloppingDetection(
        player_tracking_id=7, deception_type=DeceptionType.CHARGE_FLOP, confidence=0.75,
    )

    mdr2 = MotionDetectionResult(
        frame_index=1000,
        timestamp=33.33,
        actions=[a1, a2, a3],
        shooting_motions=[ShootingMotion()],
        dribbling_motions=[DribblingMotion()],
        passing_motions=[PassingMotion()],
        defensive_motions=[DefensiveMotion(), DefensiveMotion()],
        movement_motions=[MovementMotion()],
        flopping_detections=[flop1, flop2],
        processing_time_ms=5.2,
    )
    r.eq("total_actions", mdr2.total_actions, 3)
    r.eq("high_confidence 수", len(mdr2.high_confidence_actions), 2)
    r.eq("shooting_motions 수", len(mdr2.shooting_motions), 1)
    r.eq("defensive_motions 수", len(mdr2.defensive_motions), 2)
    r.eq("flopping_detections 수", len(mdr2.flopping_detections), 2)
    r.eq("flopping[0] type", mdr2.flopping_detections[0].deception_type, DeceptionType.HEAD_SNAP)
    r.near("processing_time_ms", mdr2.processing_time_ms, 5.2)

    # high_confidence 내용 확인
    high = mdr2.high_confidence_actions
    types = {a.action_type for a in high}
    r.true("SHOOTING in high_confidence", ActionType.SHOOTING in types)
    r.true("PASSING in high_confidence", ActionType.PASSING in types)
    r.true("DRIBBLING not in high (0.6)", ActionType.DRIBBLING not in types)

    # 리스트 독립성
    mdr3 = MotionDetectionResult()
    r.true("actions 독립", mdr.actions is not mdr3.actions)


# ==================== 16. __all__ Export 검증 ====================
def test_all_exports(r: TestResult) -> None:
    """__all__에 정의된 모든 클래스 임포트 가능 검증"""
    import shared.dto.motion_dto as mod

    for name in mod.__all__:
        obj = getattr(mod, name, None)
        r.true(f"export {name} 존재", obj is not None)


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("motion_dto.py v1.1.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)

    print("\n--- ActionType ---")
    test_action_type(r)

    print("\n--- ContestLevel ---")
    test_contest_level(r)

    print("\n--- DribbleType ---")
    test_dribble_type(r)

    print("\n--- PassType ---")
    test_pass_type(r)

    print("\n--- DefensiveActionType ---")
    test_defensive_action_type(r)

    print("\n--- MovementType ---")
    test_movement_type(r)

    print("\n--- DeceptionType ---")
    test_deception_type(r)

    print("\n--- FloppingDetection ---")
    test_flopping_detection(r)

    print("\n--- MotionFeatureVector ---")
    test_motion_feature_vector(r)

    print("\n--- ActionClassification ---")
    test_action_classification(r)

    print("\n--- ShootingMotion ---")
    test_shooting_motion(r)

    print("\n--- DribblingMotion ---")
    test_dribbling_motion(r)

    print("\n--- PassingMotion ---")
    test_passing_motion(r)

    print("\n--- DefensiveMotion ---")
    test_defensive_motion(r)

    print("\n--- MovementMotion ---")
    test_movement_motion(r)

    print("\n--- MotionDetectionResult ---")
    test_motion_detection_result(r)

    print("\n--- __all__ Export ---")
    test_all_exports(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
