# -*- coding: utf-8 -*-
"""
Phase 1A 통합 테스트: game_management 6모듈 연동

시나리오: FIBA 규칙 정규 경기 (4쿼터 + OT) 시뮬레이션
모듈: ClockManager, FoulManager, TimeoutManager,
      SubstitutionManager, RecordCorrector, OfficialFormatExporter

검증 포인트:
  1. 6모듈 동시 운용 시 상태 일관성
  2. 경기 흐름 (팁오프 → 라이브 → 이벤트 → 쿼터 종료 → OT → 최종)
  3. 리그 규칙 (FIBA) 기반 파울/타임아웃/슛클락 연동
  4. 기록 정정 + 무결성 검증
  5. 공식 기록지 생성 (경기 종료 후)
"""

from __future__ import annotations

import json
import pytest
from uuid import uuid4

from shared.constants.game_management_constants import (
    GameState,
    QUARTER_DURATION_SEC,
    OVERTIME_DURATION_SEC,
    REGULAR_PERIODS,
    SHOT_CLOCK_FULL_SEC,
)
from shared.constants.referee_rule_constants import RuleSet
from shared.dto.game_management_dto import (
    ClockState,
    FoulState,
    TimeoutState,
    OnCourtLineup,
    SubstitutionEvent,
    CorrectionRecord,
    CorrectionType,
    OfficialBoxScore,
    PlayerBoxStat,
    GameManagementSnapshot,
)

from game_analysis.game_state.game_management.clock_manager import (
    ClockManager,
    ClockManagerConfig,
)
from game_analysis.game_state.game_management.foul_manager import (
    FoulManager,
    FoulManagerConfig,
)
from game_analysis.game_state.game_management.timeout_manager import (
    TimeoutManager,
    TimeoutManagerConfig,
)
from game_analysis.game_state.game_management.substitution_manager import (
    SubstitutionManager,
    SubstitutionManagerConfig,
)
from game_analysis.game_state.game_management.record_corrector import (
    RecordCorrector,
    RecordCorrectorConfig,
)
from game_analysis.game_state.game_management.official_format_exporter import (
    OfficialFormatExporter,
    OfficialFormatExporterConfig,
)


# =============================================================================
# Fixture: FIBA 경기 매니저 세트
# =============================================================================

class FIBAGameManagers:
    """FIBA 규칙 경기 매니저 6종 묶음."""

    def __init__(self) -> None:
        self.clock = ClockManager(ClockManagerConfig(rule_set=RuleSet.FIBA, fps=30.0))
        self.foul = FoulManager(FoulManagerConfig(rule_set=RuleSet.FIBA))
        self.timeout = TimeoutManager(
            TimeoutManagerConfig(rule_set=RuleSet.FIBA),
            teams=["home", "away"],
        )
        self.sub = SubstitutionManager(SubstitutionManagerConfig())
        self.corrector = RecordCorrector(RecordCorrectorConfig())
        self.exporter = OfficialFormatExporter(
            OfficialFormatExporterConfig(rule_set=RuleSet.FIBA),
        )


@pytest.fixture
def mgrs() -> FIBAGameManagers:
    return FIBAGameManagers()


# =============================================================================
# 통합 시나리오 1: 정규 경기 흐름
# =============================================================================

class TestFullGameFlow:
    """4쿼터 FIBA 경기 전체 흐름."""

    def test_pregame_to_tipoff(self, mgrs: FIBAGameManagers) -> None:
        """PRE_GAME → TIP_OFF → 라인업 설정."""
        # 라인업 설정
        assert mgrs.sub.set_starting_lineup(
            "home", [1, 2, 3, 4, 5],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )
        assert mgrs.sub.set_starting_lineup(
            "away", [11, 12, 13, 14, 15],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )

        # 경기 시작
        assert mgrs.clock.start_game()
        assert mgrs.clock.state == GameState.TIP_OFF
        assert mgrs.clock.quarter == 1
        assert mgrs.clock.game_clock_sec == QUARTER_DURATION_SEC[RuleSet.FIBA]

        # 두 팀 라인업 확인
        home_lineup = mgrs.sub.get_lineup("home")
        assert home_lineup is not None
        assert set(home_lineup.player_tracking_ids) == {1, 2, 3, 4, 5}

    def test_live_play_with_events(self, mgrs: FIBAGameManagers) -> None:
        """LIVE 상태에서 파울 + 교체 + 타임아웃 연동."""
        # 셋업
        mgrs.sub.set_starting_lineup(
            "home", [1, 2, 3, 4, 5],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )
        mgrs.sub.set_starting_lineup(
            "away", [11, 12, 13, 14, 15],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )
        mgrs.clock.start_game()
        mgrs.clock.transition_to(GameState.LIVE)
        mgrs.clock.set_possession("home")

        # 몇 틱 진행
        for _ in range(60):  # 2초분 (30fps)
            mgrs.clock.tick()
        assert mgrs.clock.game_clock_sec < 600.0

        # 파울 발생 → DEAD_BALL
        mgrs.clock.transition_to(GameState.DEAD_BALL)
        result = mgrs.foul.record_foul(
            team_id="away", player_tracking_id=11,
            quarter=1, game_clock="09:58",
        )
        assert result.personal_foul_count == 1

        # 교체 (파울 트러블 대응)
        sub_result = mgrs.sub.substitute(
            "away", player_in=16, player_out=11,
            frame=61, timestamp=62.0, game_clock="09:58", quarter=1,
            reason="foul_trouble",
        )
        assert sub_result.success
        assert mgrs.sub.is_on_court("away", 16)
        assert not mgrs.sub.is_on_court("away", 11)

        # 타임아웃 사용
        mgrs.clock.transition_to(GameState.LIVE)
        mgrs.clock.transition_to(GameState.TIMEOUT)
        to_result = mgrs.timeout.use_timeout("home", quarter=1, game_clock="09:50")
        assert to_result.success
        assert mgrs.timeout.get_remaining("home", quarter=1) == 1

        # 타임아웃 후 LIVE 복귀
        mgrs.clock.transition_to(GameState.LIVE)
        assert mgrs.clock.is_clock_running

    def test_quarter_transition(self, mgrs: FIBAGameManagers) -> None:
        """1쿼터 종료 → PERIOD_BREAK → 2쿼터 시작."""
        mgrs.sub.set_starting_lineup(
            "home", [1, 2, 3, 4, 5],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )
        mgrs.clock.start_game()
        mgrs.clock.transition_to(GameState.LIVE)

        # 경기 시계 0으로 설정 (쿼터 종료 시뮬레이션)
        mgrs.clock.set_game_clock(0.5)
        mgrs.clock.tick()  # 시계 0 → 쿼터 종료

        # PERIOD_BREAK 전이
        mgrs.clock.transition_to(GameState.PERIOD_BREAK)
        assert mgrs.clock.state == GameState.PERIOD_BREAK

        # stint 종료
        mgrs.sub.close_quarter_stints(
            frame=500, timestamp=600.0, game_clock="00:00", quarter=1,
        )
        assert mgrs.sub.get_total_playing_time(1) == 600.0

        # 2쿼터 시작
        assert mgrs.clock.advance_to_next_period()
        assert mgrs.clock.quarter == 2
        assert mgrs.clock.game_clock_sec == 600.0  # FIBA 10분

        # 2쿼터 stint 재개
        mgrs.sub.resume_quarter_stints(
            frame=501, timestamp=601.0, game_clock="10:00", quarter=2,
        )
        stints = mgrs.sub.get_stints(1)
        assert len(stints) == 2
        assert stints[1].entry_quarter == 2

    def test_foul_accumulation_across_quarters(self, mgrs: FIBAGameManagers) -> None:
        """쿼터별 팀 파울 누적 + 보너스 전환."""
        # 1쿼터 팀 파울 5개 → 보너스 (FIBA: 5팀파울부터 보너스)
        for i in range(5):
            mgrs.foul.record_foul(
                team_id="home",
                player_tracking_id=(i % 5) + 1,
                quarter=1,
                game_clock=f"{9 - i}:00",
            )

        foul_state = mgrs.foul.get_foul_state("home", quarter=1)
        assert foul_state.team_fouls >= 5

        bonus = mgrs.foul.get_bonus_status("home", quarter=1)
        from shared.constants.game_management_constants import BonusStatus
        assert bonus != BonusStatus.NONE

    def test_timeout_half_split_fiba(self, mgrs: FIBAGameManagers) -> None:
        """FIBA 타임아웃: 전반 2개, 후반 3개 독립."""
        # 전반 2개 소진
        mgrs.timeout.use_timeout("home", quarter=1, game_clock="08:00")
        mgrs.timeout.use_timeout("home", quarter=2, game_clock="07:00")

        # 전반 3번째 실패
        r = mgrs.timeout.use_timeout("home", quarter=2, game_clock="03:00")
        assert not r.success

        # 후반은 별도 3개
        r = mgrs.timeout.use_timeout("home", quarter=3, game_clock="09:00")
        assert r.success
        assert r.remaining == 2

    def test_record_correction_and_integrity(self, mgrs: FIBAGameManagers) -> None:
        """기록 정정 + 무결성 검증."""
        event_id = uuid4()
        cid = mgrs.corrector.apply_correction(
            event_id, CorrectionType.SCORE,
            "2점", "3점", "기록원A", "위치 재확인",
        )
        assert cid is not None

        # 체인 확인
        chain = mgrs.corrector.get_correction_chain(event_id)
        assert len(chain) == 1
        assert chain[0].original_value == "2점"

        # 무결성 검증
        # (team_total_score, individual_scores_sum, total_rebounds, total_missed_shots,
        #  player_times_sum_sec, expected_team_time_sec)
        result = mgrs.corrector.run_full_integrity_check(85, 85, 42, 44, 12000.0, 12003.0)
        assert result.is_valid


# =============================================================================
# 통합 시나리오 2: 연장전 + 경기 종료
# =============================================================================

class TestOvertimeAndFinal:
    """연장전 진입 + 경기 종료 + 기록지 생성."""

    def test_overtime_entry(self, mgrs: FIBAGameManagers) -> None:
        """정규시간 종료 → OT 진입 → OT 타임아웃 부여."""
        mgrs.clock.start_game()
        mgrs.clock.transition_to(GameState.LIVE)
        mgrs.clock.transition_to(GameState.PERIOD_BREAK)

        # OT 진입
        assert mgrs.clock.transition_to(GameState.OVERTIME)
        assert mgrs.clock.is_overtime
        assert mgrs.clock.overtime_number == 1
        assert mgrs.clock.game_clock_sec == float(OVERTIME_DURATION_SEC)
        assert mgrs.clock.quarter == REGULAR_PERIODS + 1

        # OT 타임아웃 부여
        mgrs.timeout.grant_overtime_timeouts("home")
        mgrs.timeout.grant_overtime_timeouts("away")
        assert mgrs.timeout.get_remaining("home", quarter=5) == 1
        assert mgrs.timeout.get_remaining("away", quarter=5) == 1

    def test_game_over_final(self, mgrs: FIBAGameManagers) -> None:
        """FINAL 상태 전이 → is_game_over."""
        mgrs.clock.start_game()
        mgrs.clock.transition_to(GameState.LIVE)
        mgrs.clock.transition_to(GameState.FINAL)
        assert mgrs.clock.is_game_over
        assert not mgrs.clock.transition_to(GameState.LIVE)

    def test_box_score_after_game(self, mgrs: FIBAGameManagers) -> None:
        """경기 종료 후 공식 기록지 생성."""
        players = [
            PlayerBoxStat(
                player_tracking_id=i, name=f"선수{i}",
                minutes=float(25 + i), points=10 + i * 2,
                rebounds=3 + i, assists=2 + i,
                steals=i % 3, blocks=i % 2,
                turnovers=1, fouls=2,
                fg_made=4 + i, fg_attempts=10 + i,
                three_made=1, three_attempts=3,
                ft_made=2, ft_attempts=2,
                plus_minus=i - 3,
            )
            for i in range(1, 11)
        ]

        box = mgrs.exporter.build_box_score(
            game_id="INTEG001",
            date="2026-03-24",
            venue="통합테스트 아레나",
            home_team="Home",
            away_team="Away",
            final_score=(88, 82),
            quarter_scores=[(22, 20), (20, 22), (24, 20), (22, 20)],
            player_stats=players,
            officials=["심판A", "심판B", "심판C"],
        )
        assert isinstance(box, OfficialBoxScore)
        assert box.winner == "Home"
        assert len(box.player_stats) == 10

        # 포맷 변환
        data = mgrs.exporter.format_box_score(box)
        assert data["format"] == "fiba_boxscore"
        assert data["final_score"]["home"] == 88

        # JSON 직렬화
        json_str = mgrs.exporter.to_json(box)
        parsed = json.loads(json_str)
        assert parsed["game_id"] == "INTEG001"

        # XML 직렬화
        xml_str = mgrs.exporter.to_xml(box)
        assert "<game_id>INTEG001</game_id>" in xml_str

    def test_team_stats_calculation(self, mgrs: FIBAGameManagers) -> None:
        """팀 통계 산출 — 선수 합산 일치."""
        players = [
            PlayerBoxStat(
                player_tracking_id=1, name="A",
                minutes=30.0, points=20, rebounds=5, assists=4,
                steals=2, blocks=1, turnovers=3, fouls=3,
                fg_made=8, fg_attempts=15, three_made=2, three_attempts=5,
                ft_made=2, ft_attempts=3, plus_minus=10,
            ),
            PlayerBoxStat(
                player_tracking_id=2, name="B",
                minutes=28.0, points=15, rebounds=7, assists=3,
                steals=1, blocks=2, turnovers=2, fouls=2,
                fg_made=6, fg_attempts=12, three_made=1, three_attempts=4,
                ft_made=2, ft_attempts=2, plus_minus=5,
            ),
        ]
        ts = mgrs.exporter.calculate_team_stats(players)
        assert ts.rebounds == 12  # 5 + 7
        assert ts.assists == 7   # 4 + 3
        assert ts.steals == 3
        assert ts.blocks == 3


# =============================================================================
# 통합 시나리오 3: 멀티모듈 상태 일관성
# =============================================================================

class TestCrossModuleConsistency:
    """6모듈 간 상태 일관성 검증."""

    def test_substitution_playing_time_matches_clock(
        self, mgrs: FIBAGameManagers,
    ) -> None:
        """교체 시 출전시간 == 시계 경과 시간."""
        mgrs.sub.set_starting_lineup(
            "home", [1, 2, 3, 4, 5],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )
        mgrs.clock.start_game()
        mgrs.clock.transition_to(GameState.LIVE)

        # 120초 경과 시뮬레이션 (직접 설정)
        mgrs.clock.set_game_clock(480.0)  # 600 - 120 = 480

        # 교체: 선수 5 → 6
        mgrs.sub.substitute(
            "home", player_in=6, player_out=5,
            frame=3600, timestamp=120.0, game_clock="08:00", quarter=1,
        )
        assert mgrs.sub.get_total_playing_time(5) == 120.0

    def test_foul_out_triggers_substitution_need(
        self, mgrs: FIBAGameManagers,
    ) -> None:
        """FIBA 5파울 퇴장 → 교체 필요."""
        mgrs.sub.set_starting_lineup(
            "home", [1, 2, 3, 4, 5],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )

        # 선수 3에게 5번 파울 (FIBA 퇴장)
        for i in range(5):
            result = mgrs.foul.record_foul(
                team_id="home", player_tracking_id=3,
                quarter=((i // 2) % 4) + 1,
                game_clock=f"{9 - i}:00",
            )

        # 퇴장 확인
        assert result.is_ejected

        # 교체 실행
        sub_result = mgrs.sub.substitute(
            "home", player_in=8, player_out=3,
            frame=500, timestamp=300.0, game_clock="05:00", quarter=3,
        )
        assert sub_result.success
        assert not mgrs.sub.is_on_court("home", 3)
        assert mgrs.sub.is_on_court("home", 8)

    def test_correction_after_events(self, mgrs: FIBAGameManagers) -> None:
        """이벤트 기록 후 정정 → 최종값 확인."""
        event_id = uuid4()
        # 원래: 2점 기록
        mgrs.corrector.apply_correction(
            event_id, CorrectionType.SCORE, "2점", "3점",
            "기록원A", "3점 라인 밖 확인",
        )
        # 재정정: 다시 2점으로
        mgrs.corrector.apply_correction(
            event_id, CorrectionType.SCORE, "3점", "2점",
            "기록원B", "비디오 리뷰 결과 라인 밟음",
        )

        assert mgrs.corrector.get_latest_value(event_id) == "2점"
        assert mgrs.corrector.get_correction_count() == 2

    def test_all_modules_reset(self, mgrs: FIBAGameManagers) -> None:
        """전체 모듈 리셋 → 초기 상태 복원."""
        # 데이터 축적
        mgrs.sub.set_starting_lineup(
            "home", [1, 2, 3, 4, 5],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )
        mgrs.clock.start_game()
        mgrs.clock.transition_to(GameState.LIVE)
        mgrs.foul.record_foul(
            team_id="home", player_tracking_id=1, quarter=1, game_clock="09:00",
        )
        mgrs.timeout.use_timeout("home", quarter=1, game_clock="08:00")
        mgrs.corrector.apply_correction(
            uuid4(), CorrectionType.SCORE, "a", "b",
        )

        # 리셋
        mgrs.clock.reset()
        mgrs.foul.reset()
        mgrs.timeout.reset()
        mgrs.sub.reset()
        mgrs.corrector.reset()

        # 초기 상태 확인
        assert mgrs.clock.state == GameState.PRE_GAME
        assert mgrs.clock.quarter == 1
        assert mgrs.foul.get_foul_state("home", quarter=1).team_fouls == 0
        assert mgrs.timeout.get_remaining("home", quarter=1) == 2
        assert mgrs.sub.get_lineup("home") is None
        assert mgrs.corrector.get_correction_count() == 0


# =============================================================================
# 통합 시나리오 4: NBA 규칙 경기
# =============================================================================

class TestNBAGameFlow:
    """NBA 규칙 경기 — FIBA와 다른 규칙 검증."""

    @pytest.fixture
    def nba_mgrs(self) -> FIBAGameManagers:
        m = FIBAGameManagers.__new__(FIBAGameManagers)
        m.clock = ClockManager(ClockManagerConfig(rule_set=RuleSet.NBA, fps=30.0))
        m.foul = FoulManager(FoulManagerConfig(rule_set=RuleSet.NBA))
        m.timeout = TimeoutManager(
            TimeoutManagerConfig(rule_set=RuleSet.NBA),
            teams=["home", "away"],
        )
        m.sub = SubstitutionManager()
        m.corrector = RecordCorrector()
        m.exporter = OfficialFormatExporter(
            OfficialFormatExporterConfig(rule_set=RuleSet.NBA),
        )
        return m

    def test_nba_quarter_duration(self, nba_mgrs: FIBAGameManagers) -> None:
        """NBA 12분 쿼터."""
        nba_mgrs.clock.start_game()
        assert nba_mgrs.clock.game_clock_sec == 720.0  # 12분

    def test_nba_6_fouls_foul_out(self, nba_mgrs: FIBAGameManagers) -> None:
        """NBA 6파울 퇴장 (FIBA는 5)."""
        for i in range(5):
            result = nba_mgrs.foul.record_foul(
                team_id="home", player_tracking_id=1,
                quarter=(i % 4) + 1, game_clock=f"{11 - i}:00",
            )
        assert not result.is_ejected  # 5파울 아직 퇴장 아님

        result = nba_mgrs.foul.record_foul(
            team_id="home", player_tracking_id=1,
            quarter=4, game_clock="05:00",
        )
        assert result.is_ejected  # 6파울 퇴장

    def test_nba_7_unified_timeouts(self, nba_mgrs: FIBAGameManagers) -> None:
        """NBA 7개 통합 타임아웃."""
        for i in range(7):
            r = nba_mgrs.timeout.use_timeout(
                "home", quarter=(i % 4) + 1, game_clock=f"{11 - i}:00",
            )
        assert r.remaining == 0
        r_fail = nba_mgrs.timeout.use_timeout("home", quarter=4, game_clock="01:00")
        assert not r_fail.success

    def test_nba_box_score_format(self, nba_mgrs: FIBAGameManagers) -> None:
        """NBA 기록지 포맷."""
        players = [
            PlayerBoxStat(
                player_tracking_id=1, name="Star",
                minutes=36.0, points=30, rebounds=8, assists=6,
                steals=2, blocks=1, turnovers=3, fouls=2,
                fg_made=12, fg_attempts=22, three_made=3, three_attempts=8,
                ft_made=3, ft_attempts=4, plus_minus=15,
            ),
        ]
        box = nba_mgrs.exporter.build_box_score(
            game_id="NBA001", date="2026-03-24", venue="NBA Arena",
            home_team="LAL", away_team="BOS",
            final_score=(110, 105),
            quarter_scores=[(28, 26), (25, 30), (30, 24), (27, 25)],
            player_stats=players,
        )
        data = nba_mgrs.exporter.format_box_score(box)
        assert data["format"] == "nba_boxscore"
        assert "min_display" in data["players"][0]


# =============================================================================
# 통합 시나리오 5: 전체 경기 시뮬레이션 (스모크 테스트)
# =============================================================================

class TestFullGameSimulation:
    """4쿼터 전체 시뮬레이션 — 모듈 안정성 스모크."""

    def test_four_quarter_smoke(self, mgrs: FIBAGameManagers) -> None:
        """4쿼터 + 이벤트 50건 + 교체 20건 — 모듈 충돌 없음."""
        # 라인업
        mgrs.sub.set_starting_lineup(
            "home", [1, 2, 3, 4, 5],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )
        mgrs.sub.set_starting_lineup(
            "away", [11, 12, 13, 14, 15],
            frame=0, timestamp=0.0, game_clock="10:00", quarter=1,
        )

        mgrs.clock.start_game()
        frame = 0
        timestamp = 0.0

        for q in range(1, 5):
            # 쿼터 시작
            mgrs.clock.transition_to(GameState.LIVE)
            mgrs.clock.set_possession("home" if q % 2 == 1 else "away")

            # 이벤트 시뮬레이션
            for ev in range(12):
                frame += 1
                timestamp += 5.0

                # 매 3이벤트마다 파울
                if ev % 3 == 0:
                    mgrs.foul.record_foul(
                        team_id="away" if ev % 2 == 0 else "home",
                        player_tracking_id=(ev % 5) + (11 if ev % 2 == 0 else 1),
                        quarter=q,
                        game_clock=f"{9 - ev}:00",
                    )

                # 매 6이벤트마다 교체 (home만)
                if ev % 6 == 0 and ev > 0:
                    on_court = mgrs.sub.get_lineup("home")
                    if on_court:
                        p_out = on_court.player_tracking_ids[0]
                        p_in = 50 + frame  # 항상 새 선수 ID
                        mgrs.sub.substitute(
                            "home", player_in=p_in, player_out=p_out,
                            frame=frame, timestamp=timestamp,
                            game_clock=f"{9 - ev}:00", quarter=q,
                        )

            # 쿼터 종료
            mgrs.clock.transition_to(GameState.DEAD_BALL)
            if q < 4:
                mgrs.clock.transition_to(GameState.PERIOD_BREAK)
                mgrs.sub.close_quarter_stints(
                    frame=frame, timestamp=timestamp,
                    game_clock="00:00", quarter=q,
                )
                mgrs.clock.advance_to_next_period()
                mgrs.sub.resume_quarter_stints(
                    frame=frame + 1, timestamp=timestamp + 1.0,
                    game_clock="10:00", quarter=q + 1,
                )

        # 경기 종료
        mgrs.clock.transition_to(GameState.FINAL)
        assert mgrs.clock.is_game_over

        # 기록 정정 1건
        mgrs.corrector.apply_correction(
            uuid4(), CorrectionType.SCORE, "2점", "3점",
        )
        assert mgrs.corrector.get_correction_count() == 1

        # 교체 이력 확인 (최소 1건 이상)
        history = mgrs.sub.get_substitution_history()
        assert len(history) >= 1

        # 타임아웃 상태 확인
        state = mgrs.timeout.get_timeout_state("home", quarter=1)
        assert isinstance(state, TimeoutState)
