# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_tactical_dto.py

전술/분석 DTO 유닛 테스트
- 모듈 구조 (__all__, __version__, legacy typing 미사용)
- Enum 3종: DefenseScheme, MomentumState, TrendDirection
- dataclass 14종: 기본값, 데이터 입력, property
- TacticalAnalysisResult 통합 객체
- dataclass 필드 수 검증
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
    import shared.dto.tactical_dto as m

    r.true("__all__ 존재", hasattr(m, "__all__"))
    r.true("__version__ 존재", hasattr(m, "__version__"))
    r.eq("__version__", m.__version__, "1.1.0")
    r.eq("__all__ 길이", len(m.__all__), 18)

    # 모든 export 접근 가능
    expected = [
        "DefenseScheme", "MomentumState", "TrendDirection",
        "PickAndRollAnalysis", "FastBreakAnalysis", "SetPlayAnalysis", "PassingNetworkData",
        "DefenseAnalysis", "MatchupData",
        "IndividualAnalysis",
        "SpacingData",
        "LineupData",
        "GameFlowData",
        "TransitionData",
        "PlayTypeData",
        "SituationSplitData",
        "ReboundAnalysis",
        "TacticalAnalysisResult",
    ]
    for name in expected:
        r.true(f"__all__에 {name} 포함", name in m.__all__)
        r.true(f"{name} getattr 가능", hasattr(m, name))

    # legacy typing 미사용
    import inspect
    src = inspect.getsource(m)
    r.false("legacy typing 'Optional[' 미사용", "Optional[" in src)
    r.false("legacy typing 'List[' 미사용", "List[" in src)
    r.false("legacy typing 'Dict[' 미사용", "Dict[" in src)
    r.false("legacy typing 'Tuple[' 미사용", "Tuple[" in src)


# ==================== 2. DefenseScheme Enum ====================
def test_defense_scheme(r: TestResult) -> None:
    """DefenseScheme 열거형"""
    from shared.dto.tactical_dto import DefenseScheme

    # 멤버 수
    members = list(DefenseScheme)
    r.eq("DefenseScheme 멤버 수", len(members), 10)

    # str(Enum) == value
    r.eq("MAN_TO_MAN str", str(DefenseScheme.MAN_TO_MAN), "man_to_man")
    r.eq("ZONE_2_3 value", DefenseScheme.ZONE_2_3.value, "zone_2_3")
    r.eq("FULL_COURT_PRESS value", DefenseScheme.FULL_COURT_PRESS.value, "full_court_press")
    r.eq("BOX_AND_ONE value", DefenseScheme.BOX_AND_ONE.value, "box_and_one")
    r.eq("TRIANGLE_AND_TWO value", DefenseScheme.TRIANGLE_AND_TWO.value, "triangle_and_two")

    # is_zone property
    r.false("MAN_TO_MAN is_zone", DefenseScheme.MAN_TO_MAN.is_zone)
    r.true("ZONE_2_3 is_zone", DefenseScheme.ZONE_2_3.is_zone)
    r.true("ZONE_3_2 is_zone", DefenseScheme.ZONE_3_2.is_zone)
    r.true("ZONE_1_3_1 is_zone", DefenseScheme.ZONE_1_3_1.is_zone)
    r.true("ZONE_1_2_2 is_zone", DefenseScheme.ZONE_1_2_2.is_zone)
    r.true("MATCHUP_ZONE is_zone", DefenseScheme.MATCHUP_ZONE.is_zone)
    r.false("FULL_COURT_PRESS is_zone", DefenseScheme.FULL_COURT_PRESS.is_zone)
    r.false("BOX_AND_ONE is_zone", DefenseScheme.BOX_AND_ONE.is_zone)

    # is_press property
    r.false("MAN_TO_MAN is_press", DefenseScheme.MAN_TO_MAN.is_press)
    r.true("FULL_COURT_PRESS is_press", DefenseScheme.FULL_COURT_PRESS.is_press)
    r.true("HALF_COURT_PRESS is_press", DefenseScheme.HALF_COURT_PRESS.is_press)
    r.false("ZONE_2_3 is_press", DefenseScheme.ZONE_2_3.is_press)
    r.false("TRIANGLE_AND_TWO is_press", DefenseScheme.TRIANGLE_AND_TWO.is_press)

    # str Enum 서브클래스
    r.is_instance("str 서브클래스", DefenseScheme.MAN_TO_MAN, str)


# ==================== 3. MomentumState Enum ====================
def test_momentum_state(r: TestResult) -> None:
    """MomentumState 열거형"""
    from shared.dto.tactical_dto import MomentumState

    members = list(MomentumState)
    r.eq("MomentumState 멤버 수", len(members), 5)

    r.eq("STRONG_HOME value", MomentumState.STRONG_HOME.value, "strong_home")
    r.eq("SLIGHT_HOME value", MomentumState.SLIGHT_HOME.value, "slight_home")
    r.eq("NEUTRAL value", MomentumState.NEUTRAL.value, "neutral")
    r.eq("SLIGHT_AWAY value", MomentumState.SLIGHT_AWAY.value, "slight_away")
    r.eq("STRONG_AWAY value", MomentumState.STRONG_AWAY.value, "strong_away")

    r.eq("str(NEUTRAL)", str(MomentumState.NEUTRAL), "neutral")
    r.is_instance("str 서브클래스", MomentumState.NEUTRAL, str)


# ==================== 4. TrendDirection Enum ====================
def test_trend_direction(r: TestResult) -> None:
    """TrendDirection 열거형"""
    from shared.dto.tactical_dto import TrendDirection

    members = list(TrendDirection)
    r.eq("TrendDirection 멤버 수", len(members), 3)

    r.eq("IMPROVING value", TrendDirection.IMPROVING.value, "improving")
    r.eq("STABLE value", TrendDirection.STABLE.value, "stable")
    r.eq("DECLINING value", TrendDirection.DECLINING.value, "declining")

    r.eq("str(STABLE)", str(TrendDirection.STABLE), "stable")
    r.is_instance("str 서브클래스", TrendDirection.IMPROVING, str)


# ==================== 5. PickAndRollAnalysis ====================
def test_pick_and_roll_analysis(r: TestResult) -> None:
    """PickAndRollAnalysis dataclass"""
    from shared.dto.tactical_dto import PickAndRollAnalysis

    # 기본값
    pnr = PickAndRollAnalysis()
    r.eq("total_pnr 기본", pnr.total_pnr, 0)
    r.eq("pnr_ppp 기본", pnr.pnr_ppp, 0.0)
    r.eq("ballhandler_efficiency 기본", pnr.ballhandler_efficiency, 0.0)
    r.eq("roller_efficiency 기본", pnr.roller_efficiency, 0.0)
    r.eq("pop_efficiency 기본", pnr.pop_efficiency, 0.0)
    r.eq("defense_responses 빈 dict", pnr.defense_responses, {})
    r.eq("most_effective_action 기본", pnr.most_effective_action, "")

    # 데이터 입력
    pnr2 = PickAndRollAnalysis(
        total_pnr=45,
        pnr_ppp=1.12,
        ballhandler_efficiency=1.05,
        roller_efficiency=1.25,
        pop_efficiency=0.95,
        defense_responses={"drop": 20, "switch": 15, "hedge": 8, "trap": 2},
        most_effective_action="roll",
    )
    r.eq("total_pnr", pnr2.total_pnr, 45)
    r.eq("pnr_ppp", pnr2.pnr_ppp, 1.12)
    r.eq("defense_responses 수", len(pnr2.defense_responses), 4)
    r.eq("most_effective_action", pnr2.most_effective_action, "roll")


# ==================== 6. FastBreakAnalysis ====================
def test_fast_break_analysis(r: TestResult) -> None:
    """FastBreakAnalysis dataclass"""
    from shared.dto.tactical_dto import FastBreakAnalysis

    fb = FastBreakAnalysis()
    r.eq("total_fast_breaks 기본", fb.total_fast_breaks, 0)
    r.eq("fast_break_ppp 기본", fb.fast_break_ppp, 0.0)
    r.eq("numerical_advantage_counts 빈", fb.numerical_advantage_counts, {})
    r.eq("success_rate_by_advantage 빈", fb.success_rate_by_advantage, {})
    r.eq("average_transition_time_seconds 기본", fb.average_transition_time_seconds, 0.0)

    fb2 = FastBreakAnalysis(
        total_fast_breaks=18,
        fast_break_ppp=1.35,
        numerical_advantage_counts={"2v1": 8, "3v2": 6, "1v0": 4},
        success_rate_by_advantage={"2v1": 0.75, "3v2": 0.67, "1v0": 1.0},
        average_transition_time_seconds=3.2,
    )
    r.eq("total_fast_breaks", fb2.total_fast_breaks, 18)
    r.eq("advantage_counts 수", len(fb2.numerical_advantage_counts), 3)
    r.eq("success_rate 수", len(fb2.success_rate_by_advantage), 3)


# ==================== 7. SetPlayAnalysis ====================
def test_set_play_analysis(r: TestResult) -> None:
    """SetPlayAnalysis dataclass"""
    from shared.dto.tactical_dto import SetPlayAnalysis

    sp = SetPlayAnalysis()
    r.eq("detected_plays 빈 리스트", sp.detected_plays, [])
    r.eq("total_set_plays 기본", sp.total_set_plays, 0)
    r.eq("set_play_ppp 기본", sp.set_play_ppp, 0.0)
    r.eq("top_plays 빈 리스트", sp.top_plays, [])

    sp2 = SetPlayAnalysis(
        detected_plays=[
            {"play_name": "horns", "count": 12, "success_rate": 0.67},
            {"play_name": "floppy", "count": 8, "success_rate": 0.75},
        ],
        total_set_plays=20,
        set_play_ppp=1.05,
        top_plays=["horns", "floppy"],
    )
    r.eq("detected_plays 수", len(sp2.detected_plays), 2)
    r.eq("top_plays 수", len(sp2.top_plays), 2)


# ==================== 8. PassingNetworkData ====================
def test_passing_network(r: TestResult) -> None:
    """PassingNetworkData dataclass"""
    from shared.dto.tactical_dto import PassingNetworkData

    pn = PassingNetworkData()
    r.eq("connections 빈 리스트", pn.connections, [])
    r.eq("hockey_assists 기본", pn.hockey_assists, 0)
    r.eq("avg_passes 기본", pn.average_passes_per_possession, 0.0)
    r.eq("ball_movement_rating 기본", pn.ball_movement_rating, 0.0)

    pn2 = PassingNetworkData(
        connections=[
            {"from_tracking_id": 1, "to_tracking_id": 2, "count": 15, "assist_rate": 0.2},
            {"from_tracking_id": 2, "to_tracking_id": 3, "count": 12, "assist_rate": 0.15},
        ],
        hockey_assists=5,
        average_passes_per_possession=4.2,
        ball_movement_rating=78.5,
    )
    r.eq("connections 수", len(pn2.connections), 2)
    r.eq("hockey_assists", pn2.hockey_assists, 5)
    r.eq("ball_movement_rating", pn2.ball_movement_rating, 78.5)


# ==================== 9. DefenseAnalysis ====================
def test_defense_analysis(r: TestResult) -> None:
    """DefenseAnalysis dataclass"""
    from shared.dto.tactical_dto import DefenseAnalysis, DefenseScheme

    da = DefenseAnalysis()
    r.eq("primary_scheme 기본", da.primary_scheme, DefenseScheme.MAN_TO_MAN)
    r.eq("scheme_frequency 빈", da.scheme_frequency, {})
    r.eq("defensive_rating 기본", da.defensive_rating, 0.0)
    r.eq("opponent_fg_pct 기본", da.opponent_fg_pct, 0.0)
    r.eq("opponent_3pt_pct 기본", da.opponent_3pt_pct, 0.0)
    r.eq("contested_shot_rate 기본", da.contested_shot_rate, 0.0)
    r.eq("avg_contest_distance 기본", da.avg_contest_distance, 0.0)
    r.eq("steals_per_possession 기본", da.steals_per_possession, 0.0)
    r.eq("blocks_per_possession 기본", da.blocks_per_possession, 0.0)
    r.eq("help_rotation_quality 기본", da.help_rotation_quality, 0.0)
    r.eq("closeout_quality 기본", da.closeout_quality, 0.0)
    r.eq("box_out_rate 기본", da.box_out_rate, 0.0)

    da2 = DefenseAnalysis(
        primary_scheme=DefenseScheme.ZONE_2_3,
        scheme_frequency={"man_to_man": 60.0, "zone_2_3": 30.0, "full_court_press": 10.0},
        defensive_rating=105.3,
        opponent_fg_pct=0.445,
        contested_shot_rate=0.72,
        help_rotation_quality=85.0,
    )
    r.eq("primary_scheme ZONE_2_3", da2.primary_scheme, DefenseScheme.ZONE_2_3)
    r.eq("scheme_frequency 수", len(da2.scheme_frequency), 3)
    r.eq("defensive_rating", da2.defensive_rating, 105.3)
    r.eq("contested_shot_rate", da2.contested_shot_rate, 0.72)


# ==================== 10. MatchupData ====================
def test_matchup_data(r: TestResult) -> None:
    """MatchupData dataclass"""
    from shared.dto.tactical_dto import MatchupData

    md = MatchupData()
    r.eq("defender_tracking_id 기본", md.defender_tracking_id, 0)
    r.eq("offensive_tracking_id 기본", md.offensive_tracking_id, 0)
    r.eq("possessions 기본", md.possessions, 0)
    r.eq("points_allowed 기본", md.points_allowed, 0)
    r.eq("fg_attempts 기본", md.fg_attempts, 0)
    r.eq("fg_made 기본", md.fg_made, 0)
    r.eq("fg_pct 기본", md.fg_pct, 0.0)
    r.eq("contest_rate 기본", md.contest_rate, 0.0)

    md2 = MatchupData(
        defender_tracking_id=3,
        offensive_tracking_id=12,
        possessions=25,
        points_allowed=18,
        fg_attempts=15,
        fg_made=7,
        fg_pct=0.467,
        contest_rate=0.8,
    )
    r.eq("defender_tracking_id", md2.defender_tracking_id, 3)
    r.eq("offensive_tracking_id", md2.offensive_tracking_id, 12)
    r.eq("possessions", md2.possessions, 25)
    r.eq("fg_pct", md2.fg_pct, 0.467)


# ==================== 11. IndividualAnalysis ====================
def test_individual_analysis(r: TestResult) -> None:
    """IndividualAnalysis dataclass + impact_differential property"""
    from shared.dto.tactical_dto import IndividualAnalysis

    ia = IndividualAnalysis()
    r.eq("player_tracking_id 기본", ia.player_tracking_id, 0)
    r.eq("drives 빈", ia.drives, {})
    r.eq("off_ball_movement 빈", ia.off_ball_movement, {})
    r.eq("clutch_stats 빈", ia.clutch_stats, {})
    r.eq("fatigue_indicators 빈", ia.fatigue_indicators, {})
    r.eq("on_court_net_rating 기본", ia.on_court_net_rating, 0.0)
    r.eq("off_court_net_rating 기본", ia.off_court_net_rating, 0.0)

    # impact_differential property
    r.eq("impact_differential 기본 (0-0)", ia.impact_differential, 0.0)

    ia2 = IndividualAnalysis(
        player_tracking_id=7,
        drives={"total": 12, "success_rate": 0.58, "ppd": 1.1},
        off_ball_movement={"screens_set": 8, "cuts": 5},
        clutch_stats={"fg_pct": 0.55, "ft_pct": 0.88},
        fatigue_indicators={"speed_decline_pct": 8.5, "fourth_quarter_drop": 0.12},
        on_court_net_rating=8.5,
        off_court_net_rating=-3.2,
    )
    r.eq("player_tracking_id", ia2.player_tracking_id, 7)
    r.eq("drives 수", len(ia2.drives), 3)
    r.eq("off_ball_movement 수", len(ia2.off_ball_movement), 2)

    # impact_differential = 8.5 - (-3.2) = 11.7
    r.true("impact_differential 양수", abs(ia2.impact_differential - 11.7) < 0.01)


# ==================== 12. SpacingData ====================
def test_spacing_data(r: TestResult) -> None:
    """SpacingData dataclass"""
    from shared.dto.tactical_dto import SpacingData

    sd = SpacingData()
    r.eq("avg_player_spacing 기본", sd.avg_player_spacing, 0.0)
    r.eq("court_utilization_pct 기본", sd.court_utilization_pct, 0.0)
    r.eq("drive_lane_openness 기본", sd.drive_lane_openness, 0.0)
    r.eq("paint_touch_frequency 기본", sd.paint_touch_frequency, 0.0)
    r.eq("three_point_spacing 기본", sd.three_point_spacing, 0.0)

    sd2 = SpacingData(
        avg_player_spacing=4.8,
        court_utilization_pct=72.5,
        drive_lane_openness=65.0,
        paint_touch_frequency=0.45,
        three_point_spacing=3.2,
    )
    r.eq("avg_player_spacing", sd2.avg_player_spacing, 4.8)
    r.eq("court_utilization_pct", sd2.court_utilization_pct, 72.5)


# ==================== 13. LineupData ====================
def test_lineup_data(r: TestResult) -> None:
    """LineupData dataclass"""
    from shared.dto.tactical_dto import LineupData

    ld = LineupData()
    r.eq("lineup_id 기본", ld.lineup_id, "")
    r.eq("player_tracking_ids 빈", ld.player_tracking_ids, [])
    r.eq("minutes 기본", ld.minutes, 0.0)
    r.eq("possessions 기본", ld.possessions, 0)
    r.eq("net_rating 기본", ld.net_rating, 0.0)
    r.eq("offensive_rating 기본", ld.offensive_rating, 0.0)
    r.eq("defensive_rating 기본", ld.defensive_rating, 0.0)
    r.eq("plus_minus 기본", ld.plus_minus, 0)

    ld2 = LineupData(
        lineup_id="L001",
        player_tracking_ids=[1, 2, 3, 4, 5],
        minutes=12.5,
        possessions=28,
        net_rating=15.3,
        offensive_rating=118.5,
        defensive_rating=103.2,
        plus_minus=8,
    )
    r.eq("lineup_id", ld2.lineup_id, "L001")
    r.eq("player_tracking_ids 수", len(ld2.player_tracking_ids), 5)
    r.eq("net_rating", ld2.net_rating, 15.3)
    r.eq("plus_minus", ld2.plus_minus, 8)


# ==================== 14. GameFlowData ====================
def test_game_flow_data(r: TestResult) -> None:
    """GameFlowData dataclass"""
    from shared.dto.tactical_dto import GameFlowData, MomentumState

    gf = GameFlowData()
    r.eq("scoring_runs 빈", gf.scoring_runs, [])
    r.eq("momentum_shifts 빈", gf.momentum_shifts, [])
    r.eq("current_momentum 기본", gf.current_momentum, MomentumState.NEUTRAL)
    r.eq("lead_changes 기본", gf.lead_changes, 0)
    r.eq("ties 기본", gf.ties, 0)
    r.eq("largest_lead_home 기본", gf.largest_lead_home, 0)
    r.eq("largest_lead_away 기본", gf.largest_lead_away, 0)
    r.eq("timeout_effectiveness 빈", gf.timeout_effectiveness, {})

    gf2 = GameFlowData(
        scoring_runs=[
            {"team_id": "HOME", "points": 12, "start_time": 120.0, "end_time": 180.0},
            {"team_id": "AWAY", "points": 8, "start_time": 200.0, "end_time": 250.0},
        ],
        momentum_shifts=[
            {"frame": 5000, "from_state": "neutral", "to_state": "strong_home"},
        ],
        current_momentum=MomentumState.STRONG_HOME,
        lead_changes=8,
        ties=5,
        largest_lead_home=15,
        largest_lead_away=10,
        timeout_effectiveness={"pre_timeout_trend": -5.2, "post_timeout_trend": 3.8},
    )
    r.eq("scoring_runs 수", len(gf2.scoring_runs), 2)
    r.eq("momentum_shifts 수", len(gf2.momentum_shifts), 1)
    r.eq("current_momentum", gf2.current_momentum, MomentumState.STRONG_HOME)
    r.eq("lead_changes", gf2.lead_changes, 8)
    r.eq("largest_lead_home", gf2.largest_lead_home, 15)


# ==================== 15. TransitionData ====================
def test_transition_data(r: TestResult) -> None:
    """TransitionData dataclass"""
    from shared.dto.tactical_dto import TransitionData

    td = TransitionData()
    r.eq("transition_ppp 기본", td.transition_ppp, 0.0)
    r.eq("halfcourt_ppp 기본", td.halfcourt_ppp, 0.0)
    r.eq("transition_frequency 기본", td.transition_frequency, 0.0)
    r.eq("first_wave_success_rate 기본", td.first_wave_success_rate, 0.0)
    r.eq("second_wave_success_rate 기본", td.second_wave_success_rate, 0.0)
    r.eq("defensive_recovery_rate 기본", td.defensive_recovery_rate, 0.0)

    td2 = TransitionData(
        transition_ppp=1.22,
        halfcourt_ppp=0.95,
        transition_frequency=0.18,
        first_wave_success_rate=0.72,
        second_wave_success_rate=0.55,
        defensive_recovery_rate=0.85,
    )
    r.eq("transition_ppp", td2.transition_ppp, 1.22)
    r.eq("halfcourt_ppp", td2.halfcourt_ppp, 0.95)
    r.eq("defensive_recovery_rate", td2.defensive_recovery_rate, 0.85)


# ==================== 16. PlayTypeData ====================
def test_play_type_data(r: TestResult) -> None:
    """PlayTypeData dataclass (PlayType Enum 기본값)"""
    from shared.dto.tactical_dto import PlayTypeData
    from shared.constants.game_rule_constants import PlayType

    pt = PlayTypeData()
    r.eq("play_type 기본", pt.play_type, PlayType.HALF_COURT)
    r.eq("frequency 기본", pt.frequency, 0)
    r.eq("ppp 기본", pt.ppp, 0.0)
    r.eq("fg_pct 기본", pt.fg_pct, 0.0)
    r.eq("turnover_rate 기본", pt.turnover_rate, 0.0)
    r.eq("and_one_rate 기본", pt.and_one_rate, 0.0)
    r.eq("foul_drawn_rate 기본", pt.foul_drawn_rate, 0.0)

    pt2 = PlayTypeData(
        play_type=PlayType.TRANSITION,
        frequency=25,
        ppp=1.15,
        fg_pct=0.52,
        turnover_rate=0.12,
        and_one_rate=0.08,
        foul_drawn_rate=0.15,
    )
    r.eq("play_type TRANSITION", pt2.play_type, PlayType.TRANSITION)
    r.eq("frequency", pt2.frequency, 25)
    r.eq("ppp", pt2.ppp, 1.15)
    r.eq("foul_drawn_rate", pt2.foul_drawn_rate, 0.15)


# ==================== 17. SituationSplitData ====================
def test_situation_split_data(r: TestResult) -> None:
    """SituationSplitData dataclass"""
    from shared.dto.tactical_dto import SituationSplitData

    ss = SituationSplitData()
    r.eq("split_name 기본", ss.split_name, "")
    r.eq("minutes 기본", ss.minutes, 0.0)
    r.eq("offensive_rating 기본", ss.offensive_rating, 0.0)
    r.eq("defensive_rating 기본", ss.defensive_rating, 0.0)
    r.eq("net_rating 기본", ss.net_rating, 0.0)
    r.eq("fg_pct 기본", ss.fg_pct, 0.0)
    r.eq("turnover_rate 기본", ss.turnover_rate, 0.0)

    ss2 = SituationSplitData(
        split_name="Q4_leading",
        minutes=8.5,
        offensive_rating=112.0,
        defensive_rating=102.5,
        net_rating=9.5,
        fg_pct=0.48,
        turnover_rate=0.10,
    )
    r.eq("split_name", ss2.split_name, "Q4_leading")
    r.eq("minutes", ss2.minutes, 8.5)
    r.eq("net_rating", ss2.net_rating, 9.5)


# ==================== 18. ReboundAnalysis ====================
def test_rebound_analysis(r: TestResult) -> None:
    """ReboundAnalysis dataclass (15 fields)"""
    from shared.dto.tactical_dto import ReboundAnalysis

    # 기본값
    ra = ReboundAnalysis()
    r.eq("total_rebounds 기본", ra.total_rebounds, 0)
    r.eq("offensive_rebounds 기본", ra.offensive_rebounds, 0)
    r.eq("defensive_rebounds 기본", ra.defensive_rebounds, 0)
    r.eq("contested_rebounds 기본", ra.contested_rebounds, 0)
    r.eq("uncontested_rebounds 기본", ra.uncontested_rebounds, 0)
    r.eq("team_rebounds 기본", ra.team_rebounds, 0)
    r.eq("box_out_attempts 기본", ra.box_out_attempts, 0)
    r.eq("box_out_success_rate 기본", ra.box_out_success_rate, 0.0)
    r.eq("second_chance_points 기본", ra.second_chance_points, 0)
    r.eq("second_chance_conversion_rate 기본", ra.second_chance_conversion_rate, 0.0)
    r.eq("rebound_positioning 빈 리스트", ra.rebound_positioning, [])
    r.eq("crash_rate 기본", ra.crash_rate, 0.0)
    r.eq("fast_break_after_rebound_rate 기본", ra.fast_break_after_rebound_rate, 0.0)
    r.eq("long_rebound_rate 기본", ra.long_rebound_rate, 0.0)
    r.eq("tip_out_rate 기본", ra.tip_out_rate, 0.0)

    # 데이터 입력
    ra2 = ReboundAnalysis(
        total_rebounds=45,
        offensive_rebounds=12,
        defensive_rebounds=28,
        contested_rebounds=20,
        uncontested_rebounds=20,
        team_rebounds=5,
        box_out_attempts=35,
        box_out_success_rate=0.68,
        second_chance_points=14,
        second_chance_conversion_rate=0.42,
        rebound_positioning=[
            {"player_tracking_id": 5, "position": "paint", "contest_type": "box_out"},
            {"player_tracking_id": 7, "position": "elbow", "contest_type": "crash"},
        ],
        crash_rate=0.35,
        fast_break_after_rebound_rate=0.22,
        long_rebound_rate=0.15,
        tip_out_rate=0.08,
    )
    r.eq("total_rebounds", ra2.total_rebounds, 45)
    r.eq("offensive_rebounds", ra2.offensive_rebounds, 12)
    r.eq("defensive_rebounds", ra2.defensive_rebounds, 28)
    r.eq("contested_rebounds", ra2.contested_rebounds, 20)
    r.eq("box_out_attempts", ra2.box_out_attempts, 35)
    r.eq("box_out_success_rate", ra2.box_out_success_rate, 0.68)
    r.eq("second_chance_points", ra2.second_chance_points, 14)
    r.eq("rebound_positioning 수", len(ra2.rebound_positioning), 2)
    r.eq("crash_rate", ra2.crash_rate, 0.35)
    r.eq("fast_break_after_rebound_rate", ra2.fast_break_after_rebound_rate, 0.22)
    r.eq("long_rebound_rate", ra2.long_rebound_rate, 0.15)
    r.eq("tip_out_rate", ra2.tip_out_rate, 0.08)

    # 필드 수
    from dataclasses import fields
    r.eq("ReboundAnalysis 필드 수", len(fields(ReboundAnalysis)), 15)

    # mutable 격리
    ra3 = ReboundAnalysis()
    r.true("rebound_positioning 독립", ra.rebound_positioning is not ra3.rebound_positioning)


# ==================== 19. TacticalAnalysisResult (종합) ====================
def test_tactical_analysis_result_defaults(r: TestResult) -> None:
    """TacticalAnalysisResult 기본값"""
    from shared.dto.tactical_dto import TacticalAnalysisResult
    from uuid import UUID
    from datetime import datetime

    tar = TacticalAnalysisResult()
    r.is_instance("result_id UUID", tar.result_id, UUID)
    r.eq("game_id 기본", tar.game_id, "")
    r.is_none("pick_and_roll 기본 None", tar.pick_and_roll)
    r.is_none("fast_break 기본 None", tar.fast_break)
    r.is_none("set_plays 기본 None", tar.set_plays)
    r.is_none("passing_network 기본 None", tar.passing_network)
    r.is_none("defense 기본 None", tar.defense)
    r.eq("matchups 빈 리스트", tar.matchups, [])
    r.eq("individual_analyses 빈 리스트", tar.individual_analyses, [])
    r.is_none("spacing 기본 None", tar.spacing)
    r.eq("lineups 빈 리스트", tar.lineups, [])
    r.is_none("game_flow 기본 None", tar.game_flow)
    r.is_none("transitions 기본 None", tar.transitions)
    r.eq("play_types 빈 리스트", tar.play_types, [])
    r.eq("situation_splits 빈 리스트", tar.situation_splits, [])
    r.is_none("rebound_analysis 기본 None", tar.rebound_analysis)
    r.is_instance("created_at datetime", tar.created_at, datetime)


def test_tactical_analysis_result_full(r: TestResult) -> None:
    """TacticalAnalysisResult 풀 데이터"""
    from shared.dto.tactical_dto import (
        TacticalAnalysisResult,
        PickAndRollAnalysis, FastBreakAnalysis, SetPlayAnalysis, PassingNetworkData,
        DefenseAnalysis, MatchupData,
        IndividualAnalysis,
        SpacingData,
        LineupData,
        GameFlowData, MomentumState,
        TransitionData,
        PlayTypeData,
        SituationSplitData,
        ReboundAnalysis,
    )

    tar = TacticalAnalysisResult(
        game_id="GAME_001",
        pick_and_roll=PickAndRollAnalysis(total_pnr=30, pnr_ppp=1.1),
        fast_break=FastBreakAnalysis(total_fast_breaks=15),
        set_plays=SetPlayAnalysis(total_set_plays=20),
        passing_network=PassingNetworkData(hockey_assists=5),
        defense=DefenseAnalysis(defensive_rating=105.0),
        matchups=[
            MatchupData(defender_tracking_id=1, offensive_tracking_id=11, possessions=20),
            MatchupData(defender_tracking_id=2, offensive_tracking_id=12, possessions=18),
        ],
        individual_analyses=[
            IndividualAnalysis(player_tracking_id=1, on_court_net_rating=10.0),
        ],
        spacing=SpacingData(avg_player_spacing=4.5),
        lineups=[
            LineupData(lineup_id="L001", player_tracking_ids=[1, 2, 3, 4, 5]),
        ],
        game_flow=GameFlowData(current_momentum=MomentumState.STRONG_HOME, lead_changes=8),
        transitions=TransitionData(transition_ppp=1.2),
        play_types=[
            PlayTypeData(frequency=30, ppp=1.05),
        ],
        situation_splits=[
            SituationSplitData(split_name="Q4_close", net_rating=5.5),
        ],
        rebound_analysis=ReboundAnalysis(total_rebounds=42, offensive_rebounds=10),
    )

    r.eq("game_id", tar.game_id, "GAME_001")
    r.is_not_none("pick_and_roll", tar.pick_and_roll)
    r.eq("pick_and_roll.total_pnr", tar.pick_and_roll.total_pnr, 30)
    r.is_not_none("fast_break", tar.fast_break)
    r.is_not_none("set_plays", tar.set_plays)
    r.is_not_none("passing_network", tar.passing_network)
    r.is_not_none("defense", tar.defense)
    r.eq("matchups 수", len(tar.matchups), 2)
    r.eq("individual_analyses 수", len(tar.individual_analyses), 1)
    r.is_not_none("spacing", tar.spacing)
    r.eq("lineups 수", len(tar.lineups), 1)
    r.is_not_none("game_flow", tar.game_flow)
    r.eq("game_flow.lead_changes", tar.game_flow.lead_changes, 8)
    r.is_not_none("transitions", tar.transitions)
    r.eq("play_types 수", len(tar.play_types), 1)
    r.eq("situation_splits 수", len(tar.situation_splits), 1)
    r.is_not_none("rebound_analysis", tar.rebound_analysis)
    r.eq("rebound_analysis.total_rebounds", tar.rebound_analysis.total_rebounds, 42)
    r.eq("rebound_analysis.offensive_rebounds", tar.rebound_analysis.offensive_rebounds, 10)


# ==================== 19. dataclass 필드 수 ====================
def test_field_counts(r: TestResult) -> None:
    """각 dataclass의 필드 수 검증"""
    from dataclasses import fields
    from shared.dto.tactical_dto import (
        PickAndRollAnalysis, FastBreakAnalysis, SetPlayAnalysis, PassingNetworkData,
        DefenseAnalysis, MatchupData,
        IndividualAnalysis,
        SpacingData,
        LineupData,
        GameFlowData,
        TransitionData,
        PlayTypeData,
        SituationSplitData,
        ReboundAnalysis,
        TacticalAnalysisResult,
    )

    r.eq("PickAndRollAnalysis 필드 수", len(fields(PickAndRollAnalysis)), 7)
    r.eq("FastBreakAnalysis 필드 수", len(fields(FastBreakAnalysis)), 5)
    r.eq("SetPlayAnalysis 필드 수", len(fields(SetPlayAnalysis)), 4)
    r.eq("PassingNetworkData 필드 수", len(fields(PassingNetworkData)), 4)
    r.eq("DefenseAnalysis 필드 수", len(fields(DefenseAnalysis)), 12)
    r.eq("MatchupData 필드 수", len(fields(MatchupData)), 8)
    r.eq("IndividualAnalysis 필드 수", len(fields(IndividualAnalysis)), 7)
    r.eq("SpacingData 필드 수", len(fields(SpacingData)), 5)
    r.eq("LineupData 필드 수", len(fields(LineupData)), 8)
    r.eq("GameFlowData 필드 수", len(fields(GameFlowData)), 8)
    r.eq("TransitionData 필드 수", len(fields(TransitionData)), 6)
    r.eq("PlayTypeData 필드 수", len(fields(PlayTypeData)), 7)
    r.eq("SituationSplitData 필드 수", len(fields(SituationSplitData)), 7)
    r.eq("ReboundAnalysis 필드 수", len(fields(ReboundAnalysis)), 15)
    r.eq("TacticalAnalysisResult 필드 수", len(fields(TacticalAnalysisResult)), 17)


# ==================== 20. mutable default 격리 ====================
def test_mutable_default_isolation(r: TestResult) -> None:
    """mutable default 필드 격리"""
    from shared.dto.tactical_dto import PickAndRollAnalysis, TacticalAnalysisResult

    # PickAndRollAnalysis
    p1 = PickAndRollAnalysis()
    p2 = PickAndRollAnalysis()
    p1.defense_responses["drop"] = 10
    r.eq("p1.defense_responses 수", len(p1.defense_responses), 1)
    r.eq("p2.defense_responses 수 (격리)", len(p2.defense_responses), 0)

    # TacticalAnalysisResult
    t1 = TacticalAnalysisResult()
    t2 = TacticalAnalysisResult()
    t1.matchups.append("test")
    r.eq("t1.matchups 수", len(t1.matchups), 1)
    r.eq("t2.matchups 수 (격리)", len(t2.matchups), 0)


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("tactical_dto.py v1.1.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)

    print("\n--- DefenseScheme Enum ---")
    test_defense_scheme(r)

    print("\n--- MomentumState Enum ---")
    test_momentum_state(r)

    print("\n--- TrendDirection Enum ---")
    test_trend_direction(r)

    print("\n--- PickAndRollAnalysis ---")
    test_pick_and_roll_analysis(r)

    print("\n--- FastBreakAnalysis ---")
    test_fast_break_analysis(r)

    print("\n--- SetPlayAnalysis ---")
    test_set_play_analysis(r)

    print("\n--- PassingNetworkData ---")
    test_passing_network(r)

    print("\n--- DefenseAnalysis ---")
    test_defense_analysis(r)

    print("\n--- MatchupData ---")
    test_matchup_data(r)

    print("\n--- IndividualAnalysis ---")
    test_individual_analysis(r)

    print("\n--- SpacingData ---")
    test_spacing_data(r)

    print("\n--- LineupData ---")
    test_lineup_data(r)

    print("\n--- GameFlowData ---")
    test_game_flow_data(r)

    print("\n--- TransitionData ---")
    test_transition_data(r)

    print("\n--- PlayTypeData ---")
    test_play_type_data(r)

    print("\n--- SituationSplitData ---")
    test_situation_split_data(r)

    print("\n--- ReboundAnalysis ---")
    test_rebound_analysis(r)

    print("\n--- TacticalAnalysisResult 기본값 ---")
    test_tactical_analysis_result_defaults(r)

    print("\n--- TacticalAnalysisResult 풀 데이터 ---")
    test_tactical_analysis_result_full(r)

    print("\n--- dataclass 필드 수 ---")
    test_field_counts(r)

    print("\n--- mutable default 격리 ---")
    test_mutable_default_isolation(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
