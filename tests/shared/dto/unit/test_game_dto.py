# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_game_dto.py

경기 분석 DTO 유닛 테스트
- 모듈 구조 (__all__, __version__, Enum re-export)
- Pydantic BaseModel 생성/검증
- 통계 계산 헬퍼 메서드 (EFF, TS%, eFG%, AST/TO, Game Score, Four Factors)
- 시각화 데이터 변환
- AI 심판 DTO (ViolationDetection, FoulDetection, RefereeReport)
- UUID 독립성

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
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

    def fail(self, name: str, msg: str = "") -> None:
        self.failed += 1
        self.errors.append(f"{name}: {msg}")
        print(f"  [FAIL] {name}: {msg}")

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
    """모듈 __all__, __version__, Enum re-export 검증"""
    from shared.dto import game_dto as m

    # __version__
    if m.__version__ == "3.0.0":
        r.ok("__version__ == 3.0.0")
    else:
        r.fail("__version__", f"got {m.__version__}")

    # __all__ 항목 수: 26 (8 Enum + 18 Pydantic)
    if len(m.__all__) == 26:
        r.ok(f"__all__ 항목 수 == 26")
    else:
        r.fail("__all__ 항목 수", f"got {len(m.__all__)}")

    # SupportedLanguage NOT in __all__
    if "SupportedLanguage" not in m.__all__:
        r.ok("SupportedLanguage NOT in __all__")
    else:
        r.fail("SupportedLanguage in __all__", "re-export 제거 필요")

    # Enum re-export 확인
    from shared.constants.game_rule_constants import ShotType as OrigShotType
    if m.ShotType is OrigShotType:
        r.ok("ShotType re-export 일치")
    else:
        r.fail("ShotType re-export", "동일 객체 아님")

    # EventType 별칭 확인
    from shared.constants.game_rule_constants import GameEventType
    if m.EventType is GameEventType:
        r.ok("EventType == GameEventType (별칭)")
    else:
        r.fail("EventType 별칭", "동일 객체 아님")

    # 레거시 typing 없음
    src = Path(m.__file__).read_text(encoding="utf-8")
    if "Dict[" not in src and "List[" not in src and "Tuple[" not in src:
        r.ok("레거시 typing 없음")
    else:
        r.fail("레거시 typing 잔존")


# ==================== 2. PlayerInfo / TeamInfo ====================
def test_player_team_info(r: TestResult) -> None:
    """PlayerInfo, TeamInfo 생성 검증"""
    from shared.dto.game_dto import PlayerInfo, TeamInfo

    p = PlayerInfo(tracking_id=1, jersey_number=23, confidence=0.95)
    if p.tracking_id == 1 and p.jersey_number == 23:
        r.ok("PlayerInfo 생성")
    else:
        r.fail("PlayerInfo", f"tracking_id={p.tracking_id}")

    team = TeamInfo(
        team_name="홈팀",
        is_home=True,
        players=[PlayerInfo(tracking_id=i) for i in range(5)],
    )
    if len(team.players) == 5 and team.is_home is True:
        r.ok("TeamInfo 생성 (5명)")
    else:
        r.fail("TeamInfo", f"players={len(team.players)}")


# ==================== 3. ShotAttempt ====================
def test_shot_attempt(r: TestResult) -> None:
    """ShotAttempt 생성 검증"""
    from shared.dto.game_dto import ShotAttempt, ShotType, ShotResult, CourtZone

    shot = ShotAttempt(
        player_tracking_id=5,
        shot_type=ShotType.JUMP_SHOT,
        result=ShotResult.MADE,
        court_zone=CourtZone.MID_LEFT_WING,
        shot_x=0.3,
        shot_y=0.5,
        frame_number=1500,
        timestamp=50.0,
        points=2,
    )
    if isinstance(shot.shot_id, UUID):
        r.ok("ShotAttempt UUID")
    else:
        r.fail("ShotAttempt UUID", f"type={type(shot.shot_id)}")

    if shot.points == 2 and shot.contest_level == "open":
        r.ok("ShotAttempt 기본값 확인")
    else:
        r.fail("ShotAttempt 기본값", f"points={shot.points}, contest={shot.contest_level}")


# ==================== 4. ZoneStatistics ====================
def test_zone_statistics(r: TestResult) -> None:
    """ZoneStatistics 검증 (자동보정 포함)"""
    from shared.dto.game_dto import ZoneStatistics, CourtZone

    # 정상 생성
    z = ZoneStatistics(zone=CourtZone.PAINT_CENTER, attempts=10, made=5, percentage=50.0)
    if z.percentage == 50.0:
        r.ok("ZoneStatistics 정상 생성")
    else:
        r.fail("ZoneStatistics", f"percentage={z.percentage}")

    # 자동 보정 (잘못된 percentage → 자동 계산)
    z2 = ZoneStatistics(zone=CourtZone.PAINT_LEFT, attempts=10, made=7, percentage=99.0)
    if abs(z2.percentage - 70.0) < 0.2:
        r.ok("ZoneStatistics 자동 보정 (70%)")
    else:
        r.fail("ZoneStatistics 자동 보정", f"got {z2.percentage}")

    # made > attempts → ValueError
    try:
        ZoneStatistics(zone=CourtZone.PAINT_RIGHT, attempts=5, made=10, percentage=50.0)
        r.fail("ZoneStatistics made>attempts", "예외 미발생")
    except (ValueError, Exception):
        r.ok("ZoneStatistics made>attempts 검증")


# ==================== 5. ShotChart ====================
def test_shot_chart(r: TestResult) -> None:
    """ShotChart 검증 (시각화/핫존/콜드존/eFG/TS)"""
    from shared.dto.game_dto import ShotChart, ShotAttempt, ShotType, ShotResult, CourtZone, ZoneStatistics
    from uuid import uuid4

    # 핫존/콜드존
    chart = ShotChart(
        task_id=uuid4(),
        total_attempts=20,
        total_made=10,
        field_goal_percentage=50.0,
        two_point_made=6,
        two_point_attempts=12,
        three_point_made=4,
        three_point_attempts=8,
        zone_stats={
            CourtZone.THREE_LEFT_CORNER.value: ZoneStatistics(
                zone=CourtZone.THREE_LEFT_CORNER, attempts=5, made=4, percentage=80.0
            ),
            CourtZone.MID_LEFT_WING.value: ZoneStatistics(
                zone=CourtZone.MID_LEFT_WING, attempts=5, made=1, percentage=20.0
            ),
        },
    )
    hot = chart.get_hot_zones(min_attempts=3, min_percentage=50.0)
    if CourtZone.THREE_LEFT_CORNER.value in hot:
        r.ok("get_hot_zones 정상")
    else:
        r.fail("get_hot_zones", f"got {hot}")

    cold = chart.get_cold_zones(min_attempts=3, max_percentage=30.0)
    if CourtZone.MID_LEFT_WING.value in cold:
        r.ok("get_cold_zones 정상")
    else:
        r.fail("get_cold_zones", f"got {cold}")

    # eFG%
    efg = chart.calculate_effective_field_goal_percentage()
    # eFG = (10 + 0.5*4) / 20 * 100 = 60.0
    if abs(efg - 60.0) < 0.1:
        r.ok(f"eFG% == {efg}")
    else:
        r.fail("eFG%", f"expected 60.0, got {efg}")

    # TS%
    ts = chart.calculate_true_shooting_percentage(free_throws_made=5, free_throws_attempted=6)
    # Points = 6*2 + 4*3 + 5 = 12+12+5 = 29
    # Denom = 2*(20 + 0.44*6) = 2*22.64 = 45.28
    # TS = 29/45.28*100 = 64.0
    if ts > 50.0:
        r.ok(f"TS% == {ts}")
    else:
        r.fail("TS%", f"got {ts}")

    # zone_stats 키 검증
    try:
        ShotChart(
            task_id=uuid4(),
            zone_stats={"invalid_zone": ZoneStatistics(zone=CourtZone.PAINT_CENTER, attempts=1, made=0)},
        )
        r.fail("zone_stats 키 검증", "예외 미발생")
    except (ValueError, Exception):
        r.ok("zone_stats 키 검증")


# ==================== 6. GameEvent ====================
def test_game_event(r: TestResult) -> None:
    """GameEvent 생성 검증"""
    from shared.dto.game_dto import GameEvent, EventType

    ev = GameEvent(
        event_type=EventType.SHOT_MADE,
        frame_number=100,
        timestamp=3.3,
        points=2,
    )
    if isinstance(ev.event_id, UUID) and ev.points == 2:
        r.ok("GameEvent 생성")
    else:
        r.fail("GameEvent", f"points={ev.points}")


# ==================== 7. HighlightClip / HighlightReel ====================
def test_highlight(r: TestResult) -> None:
    """HighlightClip, HighlightReel 검증"""
    from shared.dto.game_dto import HighlightClip, HighlightReel, HighlightType
    from uuid import uuid4

    clip = HighlightClip(
        highlight_type=HighlightType.SPECTACULAR_DUNK,
        start_frame=100,
        end_frame=200,
        start_time=3.3,
        end_time=6.6,
        duration_seconds=3.3,
        excitement_score=95.0,
    )
    if isinstance(clip.clip_id, UUID):
        r.ok("HighlightClip 생성")
    else:
        r.fail("HighlightClip", f"type={type(clip.clip_id)}")

    # 시간 범위 검증 실패 (end_time <= start_time)
    try:
        HighlightClip(
            highlight_type=HighlightType.MONSTER_BLOCK,
            start_frame=100, end_frame=200,
            start_time=5.0, end_time=3.0,  # 역전
            duration_seconds=2.0,
        )
        r.fail("HighlightClip 시간 검증", "예외 미발생")
    except (ValueError, Exception):
        r.ok("HighlightClip 시간 범위 검증")

    reel = HighlightReel(task_id=uuid4(), clips=[clip], total_clips=1)
    if reel.total_clips == 1:
        r.ok("HighlightReel 생성")
    else:
        r.fail("HighlightReel", f"total_clips={reel.total_clips}")


# ==================== 8. PlayerStats 통계 계산 ====================
def test_player_stats(r: TestResult) -> None:
    """PlayerStats 통계 헬퍼 메서드 검증"""
    from shared.dto.game_dto import PlayerStats

    stats = PlayerStats(
        player_tracking_id=1,
        points=25,
        field_goals_made=10,
        field_goals_attempted=20,
        three_pointers_made=3,
        three_pointers_attempted=8,
        free_throws_made=2,
        free_throws_attempted=3,
        offensive_rebounds=2,
        defensive_rebounds=6,
        total_rebounds=8,
        assists=5,
        turnovers=3,
        steals=2,
        blocks=1,
        personal_fouls=3,
    )

    # EFF = (25+8+5+2+1) - (20-10) - (3-2) - 3 = 41 - 10 - 1 - 3 = 27
    eff = stats.calculate_efficiency()
    if abs(eff - 27.0) < 0.1:
        r.ok(f"EFF == {eff}")
    else:
        r.fail("EFF", f"expected 27, got {eff}")

    # eFG% = (10 + 0.5*3) / 20 * 100 = 57.5
    efg = stats.calculate_effective_field_goal_percentage()
    if abs(efg - 57.5) < 0.1:
        r.ok(f"eFG% == {efg}")
    else:
        r.fail("eFG%", f"expected 57.5, got {efg}")

    # TS% = 25 / (2*(20 + 0.44*3)) * 100 = 25 / (2*21.32) * 100 = 25/42.64*100 = 58.6
    ts = stats.calculate_true_shooting_percentage()
    if 55.0 < ts < 62.0:
        r.ok(f"TS% == {ts}")
    else:
        r.fail("TS%", f"got {ts}")

    # AST/TO = 5/3 = 1.67
    ast_to = stats.calculate_assist_to_turnover_ratio()
    if abs(ast_to - 1.67) < 0.01:
        r.ok(f"AST/TO == {ast_to}")
    else:
        r.fail("AST/TO", f"expected 1.67, got {ast_to}")

    # Game Score
    gs = stats.calculate_game_score()
    if gs > 0:
        r.ok(f"Game Score == {gs}")
    else:
        r.fail("Game Score", f"got {gs}")

    # 더블-더블 (25점 + 8리바운드 → 10 미만이므로 NO)
    # 실제: points=25(10+), rebounds=8(<10) → 1개만 10이상
    if not stats.is_double_double():
        r.ok("더블-더블 아님 (리바운드 8)")
    else:
        r.fail("더블-더블 판정", "25점+8리바 → False여야 함")

    # 더블-더블 YES (points=25, rebounds=12)
    stats2 = PlayerStats(
        player_tracking_id=2,
        points=25, total_rebounds=12,
        field_goals_made=10, field_goals_attempted=20,
    )
    if stats2.is_double_double():
        r.ok("더블-더블 달성 (25점+12리바)")
    else:
        r.fail("더블-더블", "25+12이면 True여야 함")

    # to_box_score_dict
    box = stats.to_box_score_dict()
    if "득점" in box and box["득점"] == 25:
        r.ok("to_box_score_dict KO")
    else:
        r.fail("to_box_score_dict", str(box))


# ==================== 9. TeamStats 통계 계산 ====================
def test_team_stats(r: TestResult) -> None:
    """TeamStats 통계 헬퍼 메서드 검증"""
    from shared.dto.game_dto import TeamStats
    from shared.constants.localization import SupportedLanguage

    team = TeamStats(
        final_score=85,
        field_goals_made=30,
        field_goals_attempted=70,
        three_pointers_made=8,
        three_pointers_attempted=20,
        free_throws_made=17,
        free_throws_attempted=22,
        offensive_rebounds=10,
        defensive_rebounds=25,
        total_rebounds=35,
        assists=20,
        turnovers=12,
        steals=8,
        blocks=4,
    )

    # eFG%
    efg = team.calculate_effective_field_goal_percentage()
    # (30 + 0.5*8) / 70 * 100 = 34/70*100 = 48.6
    if abs(efg - 48.6) < 0.1:
        r.ok(f"팀 eFG% == {efg}")
    else:
        r.fail("팀 eFG%", f"expected 48.6, got {efg}")

    # TOV%
    tov = team.calculate_turnover_percentage()
    # 12 / (70 + 0.44*22 + 12) * 100 = 12 / 91.68 * 100 = 13.1
    if 12.0 < tov < 14.0:
        r.ok(f"팀 TOV% == {tov}")
    else:
        r.fail("팀 TOV%", f"got {tov}")

    # AST%
    ast_pct = team.calculate_assist_percentage()
    # 20/30*100 = 66.7
    if abs(ast_pct - 66.7) < 0.1:
        r.ok(f"팀 AST% == {ast_pct}")
    else:
        r.fail("팀 AST%", f"got {ast_pct}")

    # Four Factors
    ff = team.get_four_factors()
    if "efg_percentage" in ff and "turnover_percentage" in ff:
        r.ok("Four Factors 키 확인")
    else:
        r.fail("Four Factors", str(ff))

    # 득점 분포
    bd = team.get_scoring_breakdown()
    if "two_point" in bd and "three_point" in bd and "special" in bd:
        r.ok("득점 분포 키 확인")
    else:
        r.fail("득점 분포", str(bd))

    # to_summary_dict EN
    summary = team.to_summary_dict(SupportedLanguage.EN)
    if "FG" in summary:
        r.ok("to_summary_dict EN")
    else:
        r.fail("to_summary_dict EN", str(summary))

    # Pace
    pace = team.calculate_pace(game_minutes=48.0)
    if pace > 0:
        r.ok(f"Pace == {pace}")
    else:
        r.fail("Pace", f"got {pace}")

    # ORtg
    ortg = team.calculate_offensive_rating(possessions=80)
    # 85/80*100 = 106.3
    if abs(ortg - 106.3) < 0.1:
        r.ok(f"ORtg == {ortg}")
    else:
        r.fail("ORtg", f"expected 106.3, got {ortg}")


# ==================== 10. GameStats ====================
def test_game_stats(r: TestResult) -> None:
    """GameStats 생성 검증"""
    from shared.dto.game_dto import GameStats
    from uuid import uuid4

    gs = GameStats(
        task_id=uuid4(),
        home_score=85,
        away_score=80,
        lead_changes=12,
        ties=5,
    )
    if isinstance(gs.stats_id, UUID) and gs.home_score == 85:
        r.ok("GameStats 생성")
    else:
        r.fail("GameStats", f"home_score={gs.home_score}")

    if gs.created_at.tzinfo is not None:
        r.ok("GameStats created_at UTC")
    else:
        r.fail("GameStats created_at", "tzinfo is None")


# ==================== 11. AI 심판 DTO ====================
def test_ai_referee_dto(r: TestResult) -> None:
    """ViolationEvent, FoulEvent, RefereeDecision 등 AI 심판 DTO 검증"""
    from shared.dto.game_dto import (
        ViolationEvent, FoulEvent, RefereeDecision,
        ReviewSuggestion, ViolationDetection, FoulDetection,
        RefereeReport, EventType, ViolationType, FoulType,
    )
    from uuid import uuid4

    # ViolationEvent
    ve = ViolationEvent(
        event_id="ve_001",
        event_type=EventType.TURNOVER,
        frame_number=500,
        timestamp=16.7,
        violation_type=ViolationType.TRAVELING,
        confidence=0.85,
    )
    if ve.violation_type == ViolationType.TRAVELING:
        r.ok("ViolationEvent 생성")
    else:
        r.fail("ViolationEvent", f"type={ve.violation_type}")

    # FoulEvent
    fe = FoulEvent(
        event_id="fe_001",
        event_type=EventType.PERSONAL_FOUL,
        frame_number=600,
        timestamp=20.0,
        foul_type=FoulType.PERSONAL,
        free_throws=2,
    )
    if fe.free_throws == 2:
        r.ok("FoulEvent 생성 (자유투 2개)")
    else:
        r.fail("FoulEvent", f"free_throws={fe.free_throws}")

    # RefereeDecision
    rd = RefereeDecision(
        decision_id="rd_001",
        frame_number=500,
        timestamp=16.7,
        decision_type="violation",
        violation_event=ve,
        confidence=0.85,
    )
    if rd.violation_event is not None and rd.foul_event is None:
        r.ok("RefereeDecision (violation)")
    else:
        r.fail("RefereeDecision", "violation/foul 상태 불일치")

    # ReviewSuggestion
    rs = ReviewSuggestion(
        suggestion_id="rs_001",
        frame_number=500,
        timestamp=16.7,
        reason="접촉 여부 확인 필요",
        priority="high",
    )
    if rs.priority == "high":
        r.ok("ReviewSuggestion 생성")
    else:
        r.fail("ReviewSuggestion", f"priority={rs.priority}")

    # ViolationDetection
    vd = ViolationDetection(
        violation_type=ViolationType.DOUBLE_DRIBBLE,
        player_tracking_id=3,
        frame_number=700,
        timestamp=23.3,
        confidence=0.9,
    )
    if isinstance(vd.detection_id, UUID):
        r.ok("ViolationDetection UUID")
    else:
        r.fail("ViolationDetection UUID")

    # FoulDetection
    fd = FoulDetection(
        foul_type=FoulType.FLAGRANT_1,
        fouler_tracking_id=7,
        frame_number=800,
        timestamp=26.7,
        confidence=0.88,
        free_throws_awarded=2,
    )
    if fd.free_throws_awarded == 2:
        r.ok("FoulDetection 생성")
    else:
        r.fail("FoulDetection", f"ft={fd.free_throws_awarded}")

    # RefereeReport
    rr = RefereeReport(
        task_id=uuid4(),
        rule_set="FIBA",
        violations=[vd],
        total_violations=1,
        fouls=[fd],
        total_fouls=1,
    )
    if rr.total_violations == 1 and rr.total_fouls == 1:
        r.ok("RefereeReport 생성")
    else:
        r.fail("RefereeReport", f"v={rr.total_violations}, f={rr.total_fouls}")


# ==================== 12. UUID 독립성 ====================
def test_uuid_independence(r: TestResult) -> None:
    """UUID 인스턴스 독립성 검증"""
    from shared.dto.game_dto import ShotAttempt, ShotType, ShotResult, CourtZone

    shots = [
        ShotAttempt(
            player_tracking_id=1,
            shot_type=ShotType.JUMP_SHOT,
            result=ShotResult.MADE,
            court_zone=CourtZone.PAINT_CENTER,
            shot_x=0.0, shot_y=0.0,
            frame_number=i * 100,
            timestamp=float(i),
        )
        for i in range(10)
    ]
    ids = {str(s.shot_id) for s in shots}
    if len(ids) == 10:
        r.ok("UUID 10개 모두 고유")
    else:
        r.fail("UUID 독립성", f"고유 {len(ids)}/10")


# ==================== 13. to_visualization_data ====================
def test_to_visualization_data(r: TestResult) -> None:
    """ShotChart.to_visualization_data 검증"""
    from shared.dto.game_dto import ShotChart, ShotAttempt, ShotType, ShotResult, CourtZone, ZoneStatistics
    from shared.constants.localization import SupportedLanguage
    from uuid import uuid4

    shots = [
        ShotAttempt(
            player_tracking_id=1,
            shot_type=ShotType.LAYUP,
            result=ShotResult.MADE,
            court_zone=CourtZone.PAINT_CENTER,
            shot_x=0.0, shot_y=0.1,
            frame_number=100,
            timestamp=3.3,
            points=2,
        ),
        ShotAttempt(
            player_tracking_id=1,
            shot_type=ShotType.THREE_POINTER,
            result=ShotResult.MISSED,
            court_zone=CourtZone.THREE_CENTER,
            shot_x=0.0, shot_y=0.8,
            frame_number=200,
            timestamp=6.6,
            points=0,
        ),
    ]
    chart = ShotChart(
        task_id=uuid4(),
        total_attempts=2,
        total_made=1,
        field_goal_percentage=50.0,
        shots=shots,
        zone_stats={
            CourtZone.PAINT_CENTER.value: ZoneStatistics(
                zone=CourtZone.PAINT_CENTER, attempts=1, made=1, percentage=100.0, points=2,
            ),
        },
    )

    viz = chart.to_visualization_data(SupportedLanguage.EN)
    if "summary" in viz and "shot_points" in viz and "zone_efficiency" in viz:
        r.ok("to_visualization_data 키 구조")
    else:
        r.fail("to_visualization_data", str(viz.keys()))

    if len(viz["shot_points"]) == 2:
        r.ok("shot_points 2개")
    else:
        r.fail("shot_points 수", f"got {len(viz['shot_points'])}")

    # shot_points 첫 번째 항목에 made=True (ShotResult.MADE.is_successful)
    if viz["shot_points"][0]["made"] is True:
        r.ok("shot_points[0].made == True")
    else:
        r.fail("shot_points[0].made", f"got {viz['shot_points'][0]['made']}")


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("game_dto.py v3.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)

    print("\n--- PlayerInfo / TeamInfo ---")
    test_player_team_info(r)

    print("\n--- ShotAttempt ---")
    test_shot_attempt(r)

    print("\n--- ZoneStatistics ---")
    test_zone_statistics(r)

    print("\n--- ShotChart ---")
    test_shot_chart(r)

    print("\n--- GameEvent ---")
    test_game_event(r)

    print("\n--- Highlight ---")
    test_highlight(r)

    print("\n--- PlayerStats ---")
    test_player_stats(r)

    print("\n--- TeamStats ---")
    test_team_stats(r)

    print("\n--- GameStats ---")
    test_game_stats(r)

    print("\n--- AI 심판 DTO ---")
    test_ai_referee_dto(r)

    print("\n--- UUID 독립성 ---")
    test_uuid_independence(r)

    print("\n--- to_visualization_data ---")
    test_to_visualization_data(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
