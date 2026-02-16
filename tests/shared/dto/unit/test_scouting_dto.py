# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_scouting_dto.py

스카우팅/게임플랜 DTO 유닛 테스트
- 모듈 구조 / __all__ / __version__
- OpponentProfile, TendencyReport, WeaknessReport, HeadToHeadRecord
- GamePlan, DefensiveAssignment, PreGameBriefing
- GamePlanExecutionResult
- 필드 수 검증, 기본값, 데이터 입력

Author: COURTVIEW AI Team
Version: 1.0.0
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
    import shared.dto.scouting_dto as m

    r.true("__all__ 존재", hasattr(m, "__all__"))
    r.true("__version__ 존재", hasattr(m, "__version__"))
    r.eq("__version__", m.__version__, "1.0.0")
    r.eq("__all__ 길이", len(m.__all__), 8)

    expected = [
        "OpponentProfile", "TendencyReport", "WeaknessReport", "HeadToHeadRecord",
        "GamePlan", "DefensiveAssignment", "PreGameBriefing", "GamePlanExecutionResult",
    ]
    for name in expected:
        r.true(f"__all__에 {name} 포함", name in m.__all__)
        r.true(f"{name} getattr 가능", hasattr(m, name))


def test_no_legacy_typing(r: TestResult) -> None:
    """legacy typing 미사용 확인"""
    path = _PROJECT_ROOT / "shared" / "dto" / "scouting_dto.py"
    content = path.read_text(encoding="utf-8")
    for legacy in ["Optional[", "List[", "Dict[", "Tuple["]:
        r.false(f"legacy typing '{legacy}' 미사용", legacy in content)


# ==================== 2. OpponentProfile ====================
def test_opponent_profile_defaults(r: TestResult) -> None:
    """OpponentProfile 기본값"""
    from shared.dto.scouting_dto import OpponentProfile

    p = OpponentProfile()
    r.eq("team_id 기본 빈문자열", p.team_id, "")
    r.eq("team_name 기본 빈문자열", p.team_name, "")
    r.eq("games_analyzed 기본 0", p.games_analyzed, 0)
    r.near("offensive_rating 기본 0", p.offensive_rating, 0.0)
    r.near("defensive_rating 기본 0", p.defensive_rating, 0.0)
    r.near("pace 기본 0", p.pace, 0.0)
    r.eq("primary_offense 기본 빈문자열", p.primary_offense, "")
    r.eq("primary_defense 기본 빈문자열", p.primary_defense, "")
    r.eq("key_players 빈 리스트", p.key_players, [])
    r.eq("strengths 빈 리스트", p.strengths, [])
    r.eq("weaknesses 빈 리스트", p.weaknesses, [])


def test_opponent_profile_with_data(r: TestResult) -> None:
    """OpponentProfile 데이터 입력"""
    from shared.dto.scouting_dto import OpponentProfile

    p = OpponentProfile(
        team_id="TEAM_A",
        team_name="Team Alpha",
        games_analyzed=10,
        offensive_rating=112.5,
        defensive_rating=105.3,
        pace=98.2,
        primary_offense="pick_and_roll",
        primary_defense="man_to_man",
        key_players=[
            {"tracking_id": 7, "name": "Player A", "ppg": 25.3},
            {"tracking_id": 23, "name": "Player B", "ppg": 18.7},
        ],
        strengths=["3점 슈팅", "전환 공격"],
        weaknesses=["리바운드", "자유투"],
    )

    r.eq("team_id", p.team_id, "TEAM_A")
    r.eq("games_analyzed", p.games_analyzed, 10)
    r.near("offensive_rating", p.offensive_rating, 112.5)
    r.eq("key_players 수", len(p.key_players), 2)
    r.eq("strengths 수", len(p.strengths), 2)
    r.eq("weaknesses 수", len(p.weaknesses), 2)


# ==================== 3. TendencyReport ====================
def test_tendency_report_defaults(r: TestResult) -> None:
    """TendencyReport 기본값"""
    from shared.dto.scouting_dto import TendencyReport

    t = TendencyReport()
    r.eq("team_id 기본", t.team_id, "")
    r.eq("shot_zone_preferences 빈 dict", t.shot_zone_preferences, {})
    r.eq("play_type_preferences 빈 dict", t.play_type_preferences, {})
    r.near("transition_tendency 기본 0", t.transition_tendency, 0.0)
    r.near("three_point_rate 기본 0", t.three_point_rate, 0.0)
    r.near("paint_attack_rate 기본 0", t.paint_attack_rate, 0.0)
    r.near("right_side_preference 기본 0", t.right_side_preference, 0.0)
    r.near("left_side_preference 기본 0", t.left_side_preference, 0.0)


def test_tendency_report_with_data(r: TestResult) -> None:
    """TendencyReport 데이터 입력"""
    from shared.dto.scouting_dto import TendencyReport

    t = TendencyReport(
        team_id="TEAM_A",
        shot_zone_preferences={"paint_left": 25.0, "mid_right_wing": 15.0, "three_point_top": 20.0},
        play_type_preferences={"pick_and_roll": 35.0, "isolation": 20.0},
        transition_tendency=22.5,
        three_point_rate=38.0,
        paint_attack_rate=30.0,
        right_side_preference=0.55,
        left_side_preference=0.45,
    )

    r.eq("shot_zone_preferences 수", len(t.shot_zone_preferences), 3)
    r.eq("play_type_preferences 수", len(t.play_type_preferences), 2)
    r.near("transition_tendency", t.transition_tendency, 22.5)
    r.near("three_point_rate", t.three_point_rate, 38.0)
    r.near("right_side_preference", t.right_side_preference, 0.55)


# ==================== 4. WeaknessReport ====================
def test_weakness_report_defaults(r: TestResult) -> None:
    """WeaknessReport 기본값"""
    from shared.dto.scouting_dto import WeaknessReport

    w = WeaknessReport()
    r.eq("team_id 기본", w.team_id, "")
    r.eq("defensive_gaps 빈 리스트", w.defensive_gaps, [])
    r.near("transition_weakness_score 기본 0", w.transition_weakness_score, 0.0)
    r.eq("rebounding_weakness 기본 빈문자열", w.rebounding_weakness, "")
    r.eq("matchup_exploits 빈 리스트", w.matchup_exploits, [])
    r.near("three_point_defense_rating 기본 0", w.three_point_defense_rating, 0.0)


def test_weakness_report_with_data(r: TestResult) -> None:
    """WeaknessReport 데이터 입력"""
    from shared.dto.scouting_dto import WeaknessReport

    w = WeaknessReport(
        team_id="TEAM_A",
        defensive_gaps=[
            {"zone": "paint_left", "gap_severity": 0.8, "exploitable_play": "drive"},
        ],
        transition_weakness_score=75.0,
        rebounding_weakness="defensive",
        matchup_exploits=[
            {"player_tracking_id": 12, "weakness_type": "slow_lateral", "severity": 0.9},
        ],
        three_point_defense_rating=42.0,
    )

    r.eq("defensive_gaps 수", len(w.defensive_gaps), 1)
    r.near("transition_weakness_score", w.transition_weakness_score, 75.0)
    r.eq("rebounding_weakness", w.rebounding_weakness, "defensive")
    r.eq("matchup_exploits 수", len(w.matchup_exploits), 1)


# ==================== 5. HeadToHeadRecord ====================
def test_head_to_head_defaults(r: TestResult) -> None:
    """HeadToHeadRecord 기본값"""
    from shared.dto.scouting_dto import HeadToHeadRecord

    h = HeadToHeadRecord()
    r.eq("opponent_id 기본", h.opponent_id, "")
    r.eq("total_games 기본 0", h.total_games, 0)
    r.eq("wins 기본 0", h.wins, 0)
    r.eq("losses 기본 0", h.losses, 0)
    r.near("avg_point_differential 기본 0", h.avg_point_differential, 0.0)
    r.eq("successful_strategies 빈 리스트", h.successful_strategies, [])
    r.eq("failed_strategies 빈 리스트", h.failed_strategies, [])
    r.eq("recent_results 빈 리스트", h.recent_results, [])


def test_head_to_head_with_data(r: TestResult) -> None:
    """HeadToHeadRecord 데이터 입력"""
    from shared.dto.scouting_dto import HeadToHeadRecord

    h = HeadToHeadRecord(
        opponent_id="TEAM_B",
        total_games=5,
        wins=3,
        losses=2,
        avg_point_differential=4.5,
        successful_strategies=["zone_defense", "fast_break"],
        failed_strategies=["isolation_heavy"],
        recent_results=[
            {"date": "2026-01-15", "score": "95-88", "outcome": "win"},
            {"date": "2025-12-20", "score": "78-82", "outcome": "loss"},
        ],
    )

    r.eq("total_games", h.total_games, 5)
    r.eq("wins", h.wins, 3)
    r.eq("losses", h.losses, 2)
    r.near("avg_point_differential", h.avg_point_differential, 4.5)
    r.eq("successful_strategies 수", len(h.successful_strategies), 2)
    r.eq("recent_results 수", len(h.recent_results), 2)


# ==================== 6. GamePlan ====================
def test_game_plan_defaults(r: TestResult) -> None:
    """GamePlan 기본값"""
    from shared.dto.scouting_dto import GamePlan
    from uuid import UUID

    g = GamePlan()
    r.isinstance_check("plan_id UUID", g.plan_id, UUID)
    r.eq("opponent_id 기본", g.opponent_id, "")
    r.eq("game_date 기본", g.game_date, "")
    r.eq("offensive_strategies 빈 리스트", g.offensive_strategies, [])
    r.eq("defensive_strategies 빈 리스트", g.defensive_strategies, [])
    r.eq("transition_strategies 빈 리스트", g.transition_strategies, [])
    r.eq("special_situations 빈 리스트", g.special_situations, [])
    r.eq("shot_zone_targets 빈 dict", g.shot_zone_targets, {})
    r.eq("priority_play_types 빈 리스트", g.priority_play_types, [])
    r.not_none("created_at 자동", g.created_at)


def test_game_plan_with_data(r: TestResult) -> None:
    """GamePlan 데이터 입력"""
    from shared.dto.scouting_dto import GamePlan

    g = GamePlan(
        opponent_id="TEAM_B",
        game_date="2026-02-20",
        offensive_strategies=[
            {"strategy": "pick_and_roll_high", "priority": 1, "expected_ppp": 1.15},
            {"strategy": "post_up_mismatch", "priority": 2, "expected_ppp": 1.05},
        ],
        defensive_strategies=[
            {"strategy": "switch_all", "priority": 1},
        ],
        shot_zone_targets={"three_point_corner": 20.0, "paint": 35.0},
        priority_play_types=["pick_and_roll", "spot_up"],
    )

    r.eq("offensive_strategies 수", len(g.offensive_strategies), 2)
    r.eq("defensive_strategies 수", len(g.defensive_strategies), 1)
    r.eq("shot_zone_targets 수", len(g.shot_zone_targets), 2)
    r.eq("priority_play_types 수", len(g.priority_play_types), 2)


# ==================== 7. DefensiveAssignment ====================
def test_defensive_assignment_defaults(r: TestResult) -> None:
    """DefensiveAssignment 기본값"""
    from shared.dto.scouting_dto import DefensiveAssignment

    d = DefensiveAssignment()
    r.eq("assignments 빈 dict", d.assignments, {})
    r.eq("switch_rules 빈 리스트", d.switch_rules, [])
    r.eq("double_team_triggers 빈 리스트", d.double_team_triggers, [])
    r.eq("backup_assignments 빈 dict", d.backup_assignments, {})
    r.is_none("zone_responsibilities 기본 None", d.zone_responsibilities)


def test_defensive_assignment_with_data(r: TestResult) -> None:
    """DefensiveAssignment 데이터 입력"""
    from shared.dto.scouting_dto import DefensiveAssignment

    d = DefensiveAssignment(
        assignments={1: 10, 2: 20, 3: 30, 4: 40, 5: 50},
        switch_rules=[
            {"screen_type": "ball_screen", "action": "switch", "conditions": "guards_only"},
        ],
        double_team_triggers=[
            {"player_tracking_id": 10, "condition": "post_up", "helper_source": "weak_side"},
        ],
        backup_assignments={6: 10, 7: 20},
        zone_responsibilities={1: "left_wing", 2: "right_wing", 3: "top", 4: "left_block", 5: "right_block"},
    )

    r.eq("assignments 5명", len(d.assignments), 5)
    r.eq("switch_rules 수", len(d.switch_rules), 1)
    r.eq("double_team_triggers 수", len(d.double_team_triggers), 1)
    r.eq("backup_assignments 수", len(d.backup_assignments), 2)
    r.not_none("zone_responsibilities 존재", d.zone_responsibilities)
    r.eq("zone_responsibilities 수", len(d.zone_responsibilities), 5)


# ==================== 8. PreGameBriefing ====================
def test_pre_game_briefing_defaults(r: TestResult) -> None:
    """PreGameBriefing 기본값"""
    from shared.dto.scouting_dto import PreGameBriefing
    from uuid import UUID

    b = PreGameBriefing()
    r.isinstance_check("briefing_id UUID", b.briefing_id, UUID)
    r.is_none("opponent_profile 기본 None", b.opponent_profile)
    r.is_none("tendency_report 기본 None", b.tendency_report)
    r.is_none("weakness_report 기본 None", b.weakness_report)
    r.is_none("head_to_head 기본 None", b.head_to_head)
    r.is_none("game_plan 기본 None", b.game_plan)
    r.is_none("defensive_assignment 기본 None", b.defensive_assignment)
    r.eq("key_matchups 빈 리스트", b.key_matchups, [])
    r.eq("executive_summary 기본 빈문자열", b.executive_summary, "")
    r.not_none("created_at 자동", b.created_at)


def test_pre_game_briefing_with_components(r: TestResult) -> None:
    """PreGameBriefing 구성 요소 조합"""
    from shared.dto.scouting_dto import (
        PreGameBriefing, OpponentProfile, TendencyReport,
        WeaknessReport, HeadToHeadRecord, GamePlan, DefensiveAssignment,
    )

    b = PreGameBriefing(
        opponent_profile=OpponentProfile(team_id="TEAM_B", team_name="Beta"),
        tendency_report=TendencyReport(team_id="TEAM_B"),
        weakness_report=WeaknessReport(team_id="TEAM_B"),
        head_to_head=HeadToHeadRecord(opponent_id="TEAM_B", total_games=3, wins=2, losses=1),
        game_plan=GamePlan(opponent_id="TEAM_B"),
        defensive_assignment=DefensiveAssignment(assignments={1: 10}),
        key_matchups=[{"our_player": 1, "their_player": 10, "advantage_score": 0.7}],
        executive_summary="TEAM_B 상대 zone defense 전환 공격 집중",
    )

    r.not_none("opponent_profile 존재", b.opponent_profile)
    r.eq("opponent_profile.team_id", b.opponent_profile.team_id, "TEAM_B")
    r.not_none("tendency_report 존재", b.tendency_report)
    r.not_none("weakness_report 존재", b.weakness_report)
    r.not_none("head_to_head 존재", b.head_to_head)
    r.eq("head_to_head.wins", b.head_to_head.wins, 2)
    r.not_none("game_plan 존재", b.game_plan)
    r.not_none("defensive_assignment 존재", b.defensive_assignment)
    r.eq("key_matchups 수", len(b.key_matchups), 1)
    r.true("executive_summary 비어있지 않음", len(b.executive_summary) > 0)


# ==================== 9. GamePlanExecutionResult ====================
def test_execution_result_defaults(r: TestResult) -> None:
    """GamePlanExecutionResult 기본값"""
    from shared.dto.scouting_dto import GamePlanExecutionResult
    from uuid import UUID

    e = GamePlanExecutionResult()
    r.isinstance_check("plan_id UUID", e.plan_id, UUID)
    r.eq("strategy_execution 빈 리스트", e.strategy_execution, [])
    r.near("overall_adherence_rate 기본 0", e.overall_adherence_rate, 0.0)
    r.eq("quarter_trends 빈 리스트", e.quarter_trends, [])
    r.eq("deviations 빈 리스트", e.deviations, [])
    r.eq("plan_vs_actual_ppp 빈 dict", e.plan_vs_actual_ppp, {})


def test_execution_result_with_data(r: TestResult) -> None:
    """GamePlanExecutionResult 데이터 입력"""
    from shared.dto.scouting_dto import GamePlanExecutionResult

    e = GamePlanExecutionResult(
        strategy_execution=[
            {"strategy": "pick_and_roll", "executed": True, "frequency": 35.0, "efficiency": 1.12},
            {"strategy": "isolation", "executed": True, "frequency": 15.0, "efficiency": 0.85},
        ],
        overall_adherence_rate=78.5,
        quarter_trends=[82.0, 75.0, 80.0, 72.0],
        deviations=[
            {"strategy": "post_up", "deviation_type": "underused", "impact": -0.05},
        ],
        plan_vs_actual_ppp={"pick_and_roll": 0.03, "isolation": -0.15},
    )

    r.eq("strategy_execution 수", len(e.strategy_execution), 2)
    r.near("overall_adherence_rate", e.overall_adherence_rate, 78.5)
    r.eq("quarter_trends 4쿼터", len(e.quarter_trends), 4)
    r.eq("deviations 수", len(e.deviations), 1)
    r.eq("plan_vs_actual_ppp 수", len(e.plan_vs_actual_ppp), 2)


# ==================== 10. dataclass 필드 수 ====================
def test_dataclass_fields(r: TestResult) -> None:
    """dataclass 필드 수 확인"""
    from shared.dto.scouting_dto import (
        OpponentProfile, TendencyReport, WeaknessReport, HeadToHeadRecord,
        GamePlan, DefensiveAssignment, PreGameBriefing, GamePlanExecutionResult,
    )

    r.eq("OpponentProfile 필드 수", len(fields(OpponentProfile)), 11)
    r.eq("TendencyReport 필드 수", len(fields(TendencyReport)), 8)
    r.eq("WeaknessReport 필드 수", len(fields(WeaknessReport)), 6)
    r.eq("HeadToHeadRecord 필드 수", len(fields(HeadToHeadRecord)), 8)
    r.eq("GamePlan 필드 수", len(fields(GamePlan)), 10)
    r.eq("DefensiveAssignment 필드 수", len(fields(DefensiveAssignment)), 5)
    r.eq("PreGameBriefing 필드 수", len(fields(PreGameBriefing)), 10)
    r.eq("GamePlanExecutionResult 필드 수", len(fields(GamePlanExecutionResult)), 6)


# ==================== 11. 독립 인스턴스 (mutable default 격리) ====================
def test_mutable_default_isolation(r: TestResult) -> None:
    """mutable default 필드 격리 확인"""
    from shared.dto.scouting_dto import OpponentProfile

    p1 = OpponentProfile()
    p2 = OpponentProfile()

    p1.strengths.append("3점 슈팅")
    r.eq("p1.strengths 수 1", len(p1.strengths), 1)
    r.eq("p2.strengths 수 0 (격리)", len(p2.strengths), 0)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("scouting_dto.py v1.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)
    test_no_legacy_typing(r)

    print("\n--- OpponentProfile ---")
    test_opponent_profile_defaults(r)
    test_opponent_profile_with_data(r)

    print("\n--- TendencyReport ---")
    test_tendency_report_defaults(r)
    test_tendency_report_with_data(r)

    print("\n--- WeaknessReport ---")
    test_weakness_report_defaults(r)
    test_weakness_report_with_data(r)

    print("\n--- HeadToHeadRecord ---")
    test_head_to_head_defaults(r)
    test_head_to_head_with_data(r)

    print("\n--- GamePlan ---")
    test_game_plan_defaults(r)
    test_game_plan_with_data(r)

    print("\n--- DefensiveAssignment ---")
    test_defensive_assignment_defaults(r)
    test_defensive_assignment_with_data(r)

    print("\n--- PreGameBriefing ---")
    test_pre_game_briefing_defaults(r)
    test_pre_game_briefing_with_components(r)

    print("\n--- GamePlanExecutionResult ---")
    test_execution_result_defaults(r)
    test_execution_result_with_data(r)

    print("\n--- dataclass 필드 ---")
    test_dataclass_fields(r)

    print("\n--- mutable default 격리 ---")
    test_mutable_default_isolation(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
