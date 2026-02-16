# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_game_management_dto.py

경기 관리 DTO 유닛 테스트
- 모듈 구조 (버전, __all__, typing, 의존성)
- Enum 멤버 (GameState, BonusStatus, CorrectionType)
- GameState 프로퍼티 (is_active, is_break)
- dataclass 인스턴스 생성 및 기본값
- OnCourtLineup 프로퍼티 (player_count, is_valid)
- FoulState.is_foul_trouble 메서드
- ClockState 프로퍼티 (game_clock_display, is_end_of_quarter, is_shot_clock_low)
- OfficialBoxScore.winner 프로퍼티
- GameManagementSnapshot 통합 확인
- UUID 독립성

Author: COURTVIEW AI Team
Version: 1.0.0
"""

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

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{test_name}: {detail}" if detail else test_name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

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
    """모듈 구조 검증"""
    import shared.dto.game_management_dto as mod

    # 버전
    if mod.__version__ == "1.0.0":
        r.ok("__version__ == 1.0.0")
    else:
        r.fail("__version__", f"got {mod.__version__}")

    # __all__ 항목 수
    if len(mod.__all__) == 11:
        r.ok("__all__ 항목 수 == 11")
    else:
        r.fail("__all__ 수", f"got {len(mod.__all__)}")

    # 레거시 typing 미사용 확인
    source_path = Path(mod.__file__)
    source = source_path.read_text(encoding="utf-8")
    legacy = []
    for kw in ["Dict[", "List[", "Tuple[", "Optional["]:
        if kw in source:
            legacy.append(kw)
    if not legacy:
        r.ok("레거시 typing 없음")
    else:
        r.fail("레거시 typing", str(legacy))

    # typing에서 Any만 임포트
    import_line = [l for l in source.splitlines() if l.startswith("from typing import")]
    if len(import_line) == 1 and "Any" in import_line[0]:
        r.ok("typing에서 Any만 임포트")
    else:
        r.fail("typing import", str(import_line))

    # RuleSet 의존성 확인
    from shared.constants.referee_rule_constants import RuleSet as ConstRuleSet
    if mod.GameManagementSnapshot.__dataclass_fields__["rule_set"].default == ConstRuleSet.FIBA:
        r.ok("RuleSet 의존성 정상 (FIBA 기본)")
    else:
        r.fail("RuleSet 의존성", "FIBA 기본값 불일치")


# ==================== 2. GameState Enum ====================
def test_game_state(r: TestResult) -> None:
    """GameState Enum 검증"""
    from shared.dto.game_management_dto import GameState

    # 멤버 수
    if len(GameState) == 9:
        r.ok("GameState 멤버 수 == 9")
    else:
        r.fail("GameState 멤버 수", f"got {len(GameState)}")

    # is_active 프로퍼티
    active_states = [s for s in GameState if s.is_active]
    expected_active = {GameState.LIVE, GameState.DEAD_BALL, GameState.OVERTIME}
    if set(active_states) == expected_active:
        r.ok("is_active: LIVE, DEAD_BALL, OVERTIME")
    else:
        r.fail("is_active", f"got {active_states}")

    # is_break 프로퍼티
    break_states = [s for s in GameState if s.is_break]
    expected_break = {GameState.TIMEOUT, GameState.HALFTIME, GameState.SUSPENDED}
    if set(break_states) == expected_break:
        r.ok("is_break: TIMEOUT, HALFTIME, SUSPENDED")
    else:
        r.fail("is_break", f"got {break_states}")

    # str 변환
    if str(GameState.LIVE) == "live":
        r.ok("str(GameState.LIVE) == 'live'")
    else:
        r.fail("str(GameState)", f"got {str(GameState.LIVE)}")


# ==================== 3. BonusStatus Enum ====================
def test_bonus_status(r: TestResult) -> None:
    """BonusStatus Enum 검증"""
    from shared.dto.game_management_dto import BonusStatus

    if len(BonusStatus) == 3:
        r.ok("BonusStatus 멤버 수 == 3")
    else:
        r.fail("BonusStatus 멤버 수", f"got {len(BonusStatus)}")

    if BonusStatus.DOUBLE_BONUS.value == "double_bonus":
        r.ok("BonusStatus.DOUBLE_BONUS == 'double_bonus'")
    else:
        r.fail("BonusStatus.DOUBLE_BONUS", f"got {BonusStatus.DOUBLE_BONUS.value}")


# ==================== 4. CorrectionType Enum ====================
def test_correction_type(r: TestResult) -> None:
    """CorrectionType Enum 검증"""
    from shared.dto.game_management_dto import CorrectionType

    if len(CorrectionType) == 6:
        r.ok("CorrectionType 멤버 수 == 6")
    else:
        r.fail("CorrectionType 멤버 수", f"got {len(CorrectionType)}")

    expected = {"score", "player", "time", "event_type", "event_delete", "event_add"}
    actual = {ct.value for ct in CorrectionType}
    if actual == expected:
        r.ok("CorrectionType 값 집합 일치")
    else:
        r.fail("CorrectionType 값", f"diff: {actual.symmetric_difference(expected)}")


# ==================== 5. OnCourtLineup ====================
def test_on_court_lineup(r: TestResult) -> None:
    """OnCourtLineup dataclass 검증"""
    from shared.dto.game_management_dto import OnCourtLineup

    # 5인 라인업
    lineup = OnCourtLineup(
        team_id="team_a",
        player_tracking_ids=[1, 2, 3, 4, 5],
        lineup_start_frame=0,
        lineup_start_time=0.0,
        lineup_start_game_clock="10:00",
    )
    if lineup.player_count == 5:
        r.ok("OnCourtLineup.player_count == 5")
    else:
        r.fail("player_count", f"got {lineup.player_count}")

    if lineup.is_valid:
        r.ok("OnCourtLineup.is_valid (5인)")
    else:
        r.fail("is_valid", "5인인데 False")

    # 4인 라인업 (유효하지 않음)
    lineup4 = OnCourtLineup(player_tracking_ids=[1, 2, 3, 4])
    if not lineup4.is_valid:
        r.ok("OnCourtLineup.is_valid == False (4인)")
    else:
        r.fail("is_valid", "4인인데 True")

    # 빈 라인업
    empty = OnCourtLineup()
    if empty.player_count == 0 and empty.team_id == "":
        r.ok("OnCourtLineup 기본값 (빈)")
    else:
        r.fail("기본값", f"count={empty.player_count}, team={empty.team_id}")


# ==================== 6. SubstitutionEvent ====================
def test_substitution_event(r: TestResult) -> None:
    """SubstitutionEvent dataclass 검증"""
    from shared.dto.game_management_dto import SubstitutionEvent

    sub = SubstitutionEvent(
        team_id="team_a",
        player_in_tracking_id=6,
        player_out_tracking_id=3,
        frame_number=5000,
        timestamp=166.7,
        game_clock="07:13",
        quarter=2,
        reason="fatigue",
        initiated_by="coach",
    )

    if isinstance(sub.substitution_id, UUID):
        r.ok("SubstitutionEvent UUID 자동 생성")
    else:
        r.fail("UUID", f"got {type(sub.substitution_id)}")

    if sub.player_in_tracking_id == 6 and sub.player_out_tracking_id == 3:
        r.ok("교체 선수 IN=6, OUT=3")
    else:
        r.fail("교체 선수", f"in={sub.player_in_tracking_id}, out={sub.player_out_tracking_id}")

    # 기본값
    default_sub = SubstitutionEvent()
    if default_sub.quarter == 1 and default_sub.initiated_by == "coach":
        r.ok("SubstitutionEvent 기본값 (quarter=1, coach)")
    else:
        r.fail("기본값", f"q={default_sub.quarter}, by={default_sub.initiated_by}")


# ==================== 7. FoulState ====================
def test_foul_state(r: TestResult) -> None:
    """FoulState dataclass 검증"""
    from shared.dto.game_management_dto import FoulState, BonusStatus

    fs = FoulState(
        team_id="team_a",
        quarter=2,
        team_fouls=5,
        bonus_status=BonusStatus.BONUS,
        player_fouls={1: 3, 2: 4, 3: 1},
        disqualified_players=[],
        foul_limit=5,
    )

    # is_foul_trouble: player 2 (4개 >= limit-1=4)
    if fs.is_foul_trouble(2):
        r.ok("is_foul_trouble(2) == True (4개, limit=5)")
    else:
        r.fail("is_foul_trouble(2)", "4개인데 False")

    # player 3: 1개 < 4
    if not fs.is_foul_trouble(3):
        r.ok("is_foul_trouble(3) == False (1개)")
    else:
        r.fail("is_foul_trouble(3)", "1개인데 True")

    # 존재하지 않는 선수 → 0개 → False
    if not fs.is_foul_trouble(99):
        r.ok("is_foul_trouble(99) == False (미등록)")
    else:
        r.fail("is_foul_trouble(99)", "미등록인데 True")

    # NBA 파울 리밋 (6)
    fs_nba = FoulState(player_fouls={10: 5}, foul_limit=6)
    if fs_nba.is_foul_trouble(10):
        r.ok("NBA foul_limit=6, 5개 → 트러블")
    else:
        r.fail("NBA foul trouble", "5/6인데 False")


# ==================== 8. TimeoutState ====================
def test_timeout_state(r: TestResult) -> None:
    """TimeoutState dataclass 검증"""
    from shared.dto.game_management_dto import TimeoutState

    ts = TimeoutState(
        team_id="team_b",
        timeouts_remaining=3,
        timeouts_used=2,
        timeout_history=[
            {"quarter": 1, "game_clock": "05:30", "duration_seconds": 60},
            {"quarter": 2, "game_clock": "08:00", "duration_seconds": 30},
        ],
        last_timeout_game_clock="08:00",
    )

    if ts.timeouts_remaining == 3 and ts.timeouts_used == 2:
        r.ok("TimeoutState 잔여=3, 사용=2")
    else:
        r.fail("TimeoutState", f"rem={ts.timeouts_remaining}, used={ts.timeouts_used}")

    if len(ts.timeout_history) == 2:
        r.ok("timeout_history 2건")
    else:
        r.fail("timeout_history", f"got {len(ts.timeout_history)}")


# ==================== 9. ClockState ====================
def test_clock_state(r: TestResult) -> None:
    """ClockState dataclass 검증"""
    from shared.dto.game_management_dto import ClockState, GameState

    # 기본값 (FIBA 10분)
    cs = ClockState()
    if cs.game_clock_seconds == 600.0:
        r.ok("ClockState 기본 600초 (FIBA 10분)")
    else:
        r.fail("기본 시간", f"got {cs.game_clock_seconds}")

    if cs.game_clock_display == "10:00":
        r.ok("game_clock_display == '10:00'")
    else:
        r.fail("game_clock_display", f"got {cs.game_clock_display}")

    # 커스텀 시간
    cs2 = ClockState(game_clock_seconds=125.5, shot_clock_seconds=5.0, quarter=3, game_state=GameState.LIVE)
    if cs2.game_clock_display == "02:05":
        r.ok("game_clock_display '02:05' (125.5초)")
    else:
        r.fail("game_clock_display", f"got {cs2.game_clock_display}")

    # is_end_of_quarter (2분 미만)
    if not cs2.is_end_of_quarter:
        r.ok("is_end_of_quarter == False (125.5초)")
    else:
        r.fail("is_end_of_quarter", "125.5초인데 True")

    cs3 = ClockState(game_clock_seconds=90.0)
    if cs3.is_end_of_quarter:
        r.ok("is_end_of_quarter == True (90초)")
    else:
        r.fail("is_end_of_quarter", "90초인데 False")

    # is_shot_clock_low (7초 미만)
    if cs2.is_shot_clock_low:
        r.ok("is_shot_clock_low == True (5.0초)")
    else:
        r.fail("is_shot_clock_low", "5.0초인데 False")

    cs4 = ClockState(shot_clock_seconds=10.0)
    if not cs4.is_shot_clock_low:
        r.ok("is_shot_clock_low == False (10.0초)")
    else:
        r.fail("is_shot_clock_low", "10.0초인데 True")


# ==================== 10. CorrectionRecord ====================
def test_correction_record(r: TestResult) -> None:
    """CorrectionRecord dataclass 검증"""
    from shared.dto.game_management_dto import CorrectionRecord, CorrectionType
    from datetime import datetime, timezone

    cr = CorrectionRecord(
        correction_type=CorrectionType.SCORE,
        original_value="2",
        corrected_value="3",
        corrected_by="scorer_001",
        reason="3점슛을 2점으로 잘못 기록",
    )

    if isinstance(cr.correction_id, UUID):
        r.ok("CorrectionRecord UUID 자동 생성")
    else:
        r.fail("UUID", f"got {type(cr.correction_id)}")

    if cr.correction_type == CorrectionType.SCORE:
        r.ok("correction_type == SCORE")
    else:
        r.fail("correction_type", f"got {cr.correction_type}")

    if cr.corrected_at.tzinfo == timezone.utc:
        r.ok("corrected_at UTC")
    else:
        r.fail("corrected_at timezone", f"got {cr.corrected_at.tzinfo}")


# ==================== 11. OfficialBoxScore ====================
def test_official_box_score(r: TestResult) -> None:
    """OfficialBoxScore dataclass 검증"""
    from shared.dto.game_management_dto import OfficialBoxScore

    # 홈 승리
    box = OfficialBoxScore(
        format_type="FIBA",
        game_id="game_001",
        home_team="Seoul SK",
        away_team="Busan KT",
        final_score=(85, 78),
        quarter_scores=[(22, 18), (20, 22), (25, 17), (18, 21)],
    )

    if box.winner == "Seoul SK":
        r.ok("winner == 'Seoul SK' (85>78)")
    else:
        r.fail("winner", f"got '{box.winner}'")

    # 어웨이 승리
    box2 = OfficialBoxScore(
        home_team="A", away_team="B",
        final_score=(70, 80),
    )
    if box2.winner == "B":
        r.ok("winner == 'B' (70<80)")
    else:
        r.fail("winner", f"got '{box2.winner}'")

    # 동점
    box3 = OfficialBoxScore(
        home_team="A", away_team="B",
        final_score=(75, 75),
    )
    if box3.winner == "":
        r.ok("winner == '' (동점)")
    else:
        r.fail("winner", f"got '{box3.winner}'")


# ==================== 12. GameManagementSnapshot ====================
def test_game_management_snapshot(r: TestResult) -> None:
    """GameManagementSnapshot dataclass 검증"""
    from shared.dto.game_management_dto import (
        GameManagementSnapshot, ClockState, OnCourtLineup,
        FoulState, TimeoutState, GameState, BonusStatus,
    )
    from shared.constants.referee_rule_constants import RuleSet

    clock = ClockState(
        game_clock_seconds=300.0, shot_clock_seconds=18.0,
        quarter=2, game_state=GameState.LIVE,
    )
    home_lineup = OnCourtLineup(
        team_id="home", player_tracking_ids=[1, 2, 3, 4, 5],
    )
    away_lineup = OnCourtLineup(
        team_id="away", player_tracking_ids=[6, 7, 8, 9, 10],
    )
    home_fouls = FoulState(team_id="home", quarter=2, team_fouls=3, bonus_status=BonusStatus.NONE)
    away_fouls = FoulState(team_id="away", quarter=2, team_fouls=5, bonus_status=BonusStatus.BONUS)

    snap = GameManagementSnapshot(
        frame_number=9000,
        timestamp=300.0,
        clock=clock,
        home_lineup=home_lineup,
        away_lineup=away_lineup,
        home_foul_state=home_fouls,
        away_foul_state=away_fouls,
        score=(42, 38),
        rule_set=RuleSet.FIBA,
    )

    if isinstance(snap.snapshot_id, UUID):
        r.ok("GameManagementSnapshot UUID 자동 생성")
    else:
        r.fail("UUID", f"got {type(snap.snapshot_id)}")

    if snap.clock.game_clock_display == "05:00":
        r.ok("snapshot.clock.game_clock_display == '05:00'")
    else:
        r.fail("clock display", f"got {snap.clock.game_clock_display}")

    if snap.home_lineup.is_valid and snap.away_lineup.is_valid:
        r.ok("양팀 라인업 유효 (5인)")
    else:
        r.fail("라인업 유효성", "False")

    if snap.score == (42, 38):
        r.ok("score == (42, 38)")
    else:
        r.fail("score", f"got {snap.score}")

    if snap.rule_set == RuleSet.FIBA:
        r.ok("rule_set == RuleSet.FIBA")
    else:
        r.fail("rule_set", f"got {snap.rule_set}")

    # 기본값 스냅샷
    default_snap = GameManagementSnapshot()
    if default_snap.clock is None and default_snap.home_lineup is None:
        r.ok("기본 스냅샷 None 필드 확인")
    else:
        r.fail("기본 스냅샷", "None이 아님")


# ==================== 13. UUID 독립성 ====================
def test_uuid_independence(r: TestResult) -> None:
    """UUID 독립성 검증"""
    from shared.dto.game_management_dto import (
        SubstitutionEvent, CorrectionRecord, GameManagementSnapshot,
    )

    uuids = set()
    for _ in range(10):
        s = SubstitutionEvent()
        c = CorrectionRecord()
        g = GameManagementSnapshot()
        uuids.update([s.substitution_id, c.correction_id, c.original_event_id, g.snapshot_id])

    if len(uuids) == 40:
        r.ok(f"UUID {len(uuids)}개 모두 고유")
    else:
        r.fail("UUID 독립성", f"고유 수: {len(uuids)}/40")


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("game_management_dto.py v1.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)

    print("\n--- GameState ---")
    test_game_state(r)

    print("\n--- BonusStatus ---")
    test_bonus_status(r)

    print("\n--- CorrectionType ---")
    test_correction_type(r)

    print("\n--- OnCourtLineup ---")
    test_on_court_lineup(r)

    print("\n--- SubstitutionEvent ---")
    test_substitution_event(r)

    print("\n--- FoulState ---")
    test_foul_state(r)

    print("\n--- TimeoutState ---")
    test_timeout_state(r)

    print("\n--- ClockState ---")
    test_clock_state(r)

    print("\n--- CorrectionRecord ---")
    test_correction_record(r)

    print("\n--- OfficialBoxScore ---")
    test_official_box_score(r)

    print("\n--- GameManagementSnapshot ---")
    test_game_management_snapshot(r)

    print("\n--- UUID 독립성 ---")
    test_uuid_independence(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
