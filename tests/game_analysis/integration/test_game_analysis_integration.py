# -*- coding: utf-8 -*-
"""
game_analysis 통합 테스트 — Phase 1~4 크로스 모듈 시나리오.

시나리오:
1. 루트 __init__.py import 검증 (100 심볼)
2. Phase 1A→1B 연동: game_management → event_detection 이벤트 흐름
3. Phase 1B→1C 연동: event_detection → statistics 스탯 축적
4. Phase 1C→2 연동: statistics → tactical_analysis 전술 분석
5. Phase 2→3 연동: tactical_analysis → highlight + game_record 출력
6. Phase 3→4 연동: game_record → scouting 스카우팅 데이터
7. Phase 4 내부: matchup_analysis 매치업 파이프라인
8. 전체 파이프라인: 이벤트 → 스탯 → 전술 → 하이라이트 → 기록지 → 스카우팅
"""
from __future__ import annotations

import pytest

from shared.constants.game_rule_constants import GameEventType, HighlightType
from shared.constants.event_types import EventType


# =============================================================================
# 시나리오 1: 루트 __init__.py import 검증
# =============================================================================
class TestRootImport:
    """game_analysis 루트 패키지 import 검증."""

    def test_root_import(self):
        import game_analysis
        assert hasattr(game_analysis, "__all__")
        assert len(game_analysis.__all__) == 294

    def test_phase_1a_classes_accessible(self):
        from game_analysis import ClockManager, FoulManager, TimeoutManager
        assert ClockManager is not None
        assert FoulManager is not None
        assert TimeoutManager is not None

    def test_phase_1b_classes_accessible(self):
        from game_analysis import (
            ShotEventDetector, ReboundDetector, PossessionTracker,
        )
        assert ShotEventDetector is not None

    def test_phase_1c_classes_accessible(self):
        from game_analysis import BasicStatsCalculator, FourFactorsCalculator
        assert BasicStatsCalculator is not None
        assert FourFactorsCalculator is not None

    def test_phase_2_classes_accessible(self):
        from game_analysis import ScreenAnalyzer, SetPlayRecognizer
        assert ScreenAnalyzer is not None

    def test_phase_3_classes_accessible(self):
        from game_analysis import (
            HighlightDetector, GameSheetGenerator, PlayByPlayRecorder,
        )
        assert HighlightDetector is not None

    def test_phase_4_classes_accessible(self):
        from game_analysis import (
            OpponentProfiler, MatchupTracker, ContestAnalyzer,
        )
        assert OpponentProfiler is not None


# =============================================================================
# 시나리오 2: Phase 1A → 1B 이벤트 흐름
# =============================================================================
class TestPhase1ATo1B:
    """game_management → event_detection 이벤트 흐름."""

    def test_clock_to_possession(self):
        """클락 매니저 → 점유 추적기 연동."""
        from game_analysis.game_state.game_management.clock_manager import (
            ClockManager,
        )
        from game_analysis.game_state.event_detection.possession_tracker import (
            PossessionTracker, PossessionFrameInput,
        )

        clock = ClockManager()
        pt = PossessionTracker()

        # 클락 시작 → 점유 프레임 입력
        clock.start_game()
        pt.process_frame(PossessionFrameInput(
            frame_index=1,
            timestamp_sec=0.0,
            ball_holder_tracking_id=7,
            ball_holder_team_id="home",
            ball_is_live=True,
            ball_is_controlled=True,
            quarter=1,
            game_clock="10:00",
            confidence=0.90,
        ))

        assert pt.total_possessions >= 0

    def test_foul_manager_to_foul_detector(self):
        """파울 매니저 + 파울 감지기 독립 동작."""
        from game_analysis.game_state.game_management.foul_manager import (
            FoulManager,
        )
        from game_analysis.game_state.event_detection.foul_detector import (
            FoulDetector, FoulInput,
        )

        fm = FoulManager()
        fd = FoulDetector()

        # 파울 감지
        result = fd.detect_foul(FoulInput(
            frame_index=100,
            timestamp_sec=5.0,
            fouling_player_id=7,
            fouling_team_id="home",
            fouled_player_id=23,
            fouled_team_id="away",
            body_overlap_ratio=0.5,
            velocity_change_ms=2.0,
            acceleration_spike_ms2=5.0,
            contact_duration_frames=3,
            quarter=1,
            game_clock="08:30",
            confidence=0.85,
        ))

        # 파울 매니저에 기록
        fm.record_foul(
            team_id="home",
            player_tracking_id=7,
            quarter=1,
            game_clock="08:30",
            foul_type="personal",
        )

        count = fm.get_personal_foul_count(7)
        assert count >= 1


# =============================================================================
# 시나리오 3: Phase 1B → 1C 스탯 축적
# =============================================================================
class TestPhase1BTo1C:
    """event_detection → statistics 스탯 축적."""

    def test_shot_event_to_basic_stats(self):
        """슛 이벤트 감지 → 기본 스탯 업데이트."""
        from game_analysis.game_state.event_detection.shot_event_detector import (
            ShotEventDetector, ShotReleaseInput, ShotResultInput,
        )
        from game_analysis.stats.statistics.basic_stats import (
            BasicStatsCalculator,
        )
        from shared.dto.game_dto import GameEvent

        sd = ShotEventDetector()
        bs = BasicStatsCalculator()

        # 슛 릴리스 감지
        sd.process_release(ShotReleaseInput(
            frame_index=100,
            timestamp_sec=60.0,
            player_tracking_id=7,
            team_id="home",
            wrist_above_shoulder_m=0.3,
            elbow_extension_deg=160.0,
            arm_angular_velocity_degs=500.0,
            ball_distance_to_hoop_m=5.0,
            player_court_x=7.0,
            player_court_y=4.0,
            quarter=1,
            game_clock="08:00",
        ))

        # 슛 결과 감지
        shot_result = sd.process_result(ShotResultInput(
            frame_index=130,
            timestamp_sec=61.0,
            ball_through_hoop=True,
            net_deflection=0.8,
            confidence=0.90,
        ))

        # BasicStatsCalculator는 GameEvent를 process_event로 받음
        # shot_result가 GameEvent라면 직접 전달
        if shot_result is not None:
            bs.process_event(shot_result)

        # 선수 스탯 확인
        stats = bs.get_player_stats(7)
        # 슛이 감지되었다면 스탯이 있어야 함
        if shot_result is not None:
            assert stats is not None

    def test_turnover_to_advanced_stats(self):
        """턴오버 감지 → 고급 스탯 업데이트."""
        from game_analysis.game_state.event_detection.turnover_detector import (
            TurnoverDetector, TurnoverInput,
        )
        from game_analysis.stats.statistics.advanced_stats import (
            AdvancedStatsCalculator, TeamContext,
        )
        from shared.dto.game_dto import PlayerStats

        td = TurnoverDetector()
        adv = AdvancedStatsCalculator()

        # 턴오버 감지
        result = td.detect_turnover(TurnoverInput(
            frame_index=200,
            timestamp_sec=120.0,
            possessor_tracking_id=11,
            possessor_team_id="home",
            gaining_team_id="away",
            was_bad_pass=True,
            quarter=1,
            game_clock="07:15",
            confidence=0.88,
        ))

        # 고급 스탯에서 팀 컨텍스트 설정하고 계산
        ctx = TeamContext(
            team_id="home",
            total_minutes=240.0,
            field_goals_attempted=80,
            free_throws_attempted=20,
            turnovers=12,
            offensive_rebounds=10,
            total_possessions=90,
            points=95,
            opponent_points=88,
        )
        adv.set_team_context("home", ctx)

        # PlayerStats 객체 생성
        ps = PlayerStats(
            player_tracking_id=11,
            team_id="home",
            points=18,
            field_goals_made=7,
            field_goals_attempted=15,
            free_throws_made=3,
            free_throws_attempted=4,
            offensive_rebounds=2,
            defensive_rebounds=5,
            assists=4,
            steals=1,
            blocks=0,
            turnovers=3,
            personal_fouls=2,
        )

        adv_stats = adv.calculate(ps, minutes=32.0)
        assert adv_stats is not None


# =============================================================================
# 시나리오 4: Phase 1C → 2 전술 분석
# =============================================================================
class TestPhase1CTo2:
    """statistics → tactical_analysis 전술 분석."""

    def test_possession_stats_to_pnr(self):
        """점유 스탯 → PnR 분석."""
        from game_analysis.stats.statistics.possession_stats import (
            PossessionStatsCalculator, PossessionResult,
        )
        from game_analysis.analysis.team.tactical_analysis.screen_analyzer import (
            ScreenAnalyzer, PnREventInput,
        )

        ps = PossessionStatsCalculator()
        sa = ScreenAnalyzer()

        # 점유 스탯 계산
        result = ps.process_possession(PossessionResult(
            team_id="home",
            quarter=1,
            points_scored=2,
            duration_sec=15.0,
            end_reason="shot_made",
        ))
        assert result is True

        # PnR 이벤트 분석
        from game_analysis.analysis.team.tactical_analysis.screen_analyzer import PnRCoverageType
        sa.process_pnr_event(PnREventInput(
            team_id="home", handler_id=1, screener_id=5,
            defense_coverage=PnRCoverageType.DROP, points_scored=2,
            resulted_in_shot=True, shot_made=True,
            confidence=0.85,
        ))
        analysis = sa.get_team_pnr_analysis("home")
        assert analysis is not None

    def test_four_factors_to_passing_network(self):
        """Four Factors → 패싱 네트워크 (독립 동작)."""
        from game_analysis.stats.statistics.four_factors import (
            FourFactorsCalculator, FourFactorsInput,
        )
        from game_analysis.analysis.team.tactical_analysis.passing_network import (
            PassingNetworkAnalyzer, PassEventInput,
        )

        ff = FourFactorsCalculator()
        pn = PassingNetworkAnalyzer()

        # Four Factors 계산
        ff_result = ff.calculate(FourFactorsInput(
            team_id="home",
            field_goals_made=35,
            field_goals_attempted=80,
            three_pointers_made=8,
            turnovers=12,
            offensive_rebounds=10,
            opponent_defensive_rebounds=30,
            free_throws_attempted=20,
        ))
        assert ff_result is not None
        assert ff_result.efg_pct > 0

        # 패싱 네트워크에 이벤트 추가
        pn.process_pass(PassEventInput(
            passer_id=1, receiver_id=5, team_id="home",
            resulted_in_assist=True,
            confidence=0.90,
        ))
        analysis = pn.get_team_analysis("home")
        assert analysis is not None


# =============================================================================
# 시나리오 5: Phase 2 → 3 하이라이트 + 기록
# =============================================================================
class TestPhase2To3:
    """tactical_analysis → highlight + game_record 출력."""

    def test_event_to_highlight(self):
        """이벤트 → 하이라이트 감지."""
        from game_analysis.output.highlight.highlight_detector import (
            HighlightDetector, HighlightDetectorConfig, HighlightEventInput,
        )

        # event_scores에 event_key 기본 점수 설정 (YAML 대체)
        cfg = HighlightDetectorConfig(
            event_scores={"shot_made_3pt": 60.0},
            threshold=55.0,
        )
        hd = HighlightDetector(config=cfg)
        candidate = hd.process_event(HighlightEventInput(
            event_id="EVT001",
            event_key="shot_made_3pt",
            team_id="home",
            primary_player_id=7,
            timestamp_sec=2850.0,
            quarter=4,
            game_clock_sec=30.0,
            home_score=85,
            away_score=84,
            is_home_team=True,
            points_scored=3,
            highlight_type=HighlightType.CLUTCH_PLAY,
            confidence=0.92,
        ))
        assert candidate is not None
        assert candidate.base_score > 0

    def test_event_to_pbp(self):
        """이벤트 → 플레이-바이-플레이 기록."""
        from game_analysis.output.game_record.play_by_play import (
            PlayByPlayRecorder, PBPEventInput,
        )

        pbp = PlayByPlayRecorder()
        entry = pbp.record_event(PBPEventInput(
            event_type=GameEventType.SHOT_MADE,
            team_id="home", player_id=7, jersey_number=7,
            quarter=4, game_clock="00:30",
            timestamp_sec=2850.0, points=3,
            home_score=88, away_score=84,
            is_home_team=True, confidence=0.92,
        ))
        assert entry.sequence == 1
        assert entry.is_scoring is True

    def test_game_sheet_accumulation(self):
        """경기 중 스탯 → 게임시트 생성."""
        from game_analysis.output.game_record.game_sheet_generator import (
            GameSheetGenerator, PlayerStatInput,
        )

        gs = GameSheetGenerator()
        gs.update_player_stats(PlayerStatInput(
            player_id=7, team_id="home", jersey_number=7,
            is_starter=True, minutes_played=32.0,
            field_goals_made=8, field_goals_attempted=15,
            three_pointers_made=3, three_pointers_attempted=7,
            free_throws_made=4, free_throws_attempted=5,
            offensive_rebounds=2, defensive_rebounds=6,
            assists=5, steals=2,
            blocks=1, turnovers=3, personal_fouls=2, points=23,
        ))
        sheet = gs.generate()
        assert sheet is not None


# =============================================================================
# 시나리오 6: Phase 3 → 4 스카우팅 데이터
# =============================================================================
class TestPhase3To4:
    """game_record → scouting 스카우팅 데이터."""

    def test_game_data_to_opponent_profile(self):
        """경기 데이터 → 상대팀 프로필."""
        from game_analysis.output.scouting.opponent_profiler import (
            OpponentProfiler, GameDataInput, PlayerSeasonInput,
        )

        op = OpponentProfiler()
        op.set_team_info("OPP001", "Eagles")
        op.add_game(GameDataInput(
            game_id="G001",
            offensive_rating=112.0, defensive_rating=108.0, pace=76.0,
            primary_offense="pick_and_roll", primary_defense="man_to_man",
            fg_pct=0.46, three_pt_pct=0.36, ft_pct=0.78,
            rebounds=43, assists=22, turnovers=14,
            steals=7, blocks=4,
        ))
        op.set_players([
            PlayerSeasonInput(tracking_id=23, name="Star PG", role="PG",
                              ppg=22.0, usage_pct=0.30, minutes_per_game=35.0),
        ])
        profile = op.build_profile()
        assert profile.team_name == "Eagles"
        assert profile.offensive_rating == 112.0
        assert len(profile.key_players) == 1

    def test_scouting_report_pipeline(self):
        """스카우팅 전체 파이프라인: 프로필 → 성향 → 약점 → 전적 → 리포트."""
        from game_analysis.output.scouting.opponent_profiler import (
            OpponentProfiler, GameDataInput,
        )
        from game_analysis.output.scouting.tendency_analyzer import (
            TendencyAnalyzer, ShotRecordInput, PossessionRecordInput,
        )
        from game_analysis.output.scouting.weakness_finder import (
            WeaknessFinder, ZoneDefenseInput, ThreePointDefenseInput,
        )
        from game_analysis.output.scouting.head_to_head_analyzer import (
            HeadToHeadAnalyzer, H2HGameInput,
        )
        from game_analysis.output.scouting.scouting_report_builder import (
            ScoutingReportBuilder,
        )
        from shared.constants.game_rule_constants import CourtZone

        # 1) 프로필
        op = OpponentProfiler()
        op.set_team_info("OPP001", "Eagles")
        op.add_game(GameDataInput(
            offensive_rating=115.0, defensive_rating=105.0, pace=78.0,
            primary_offense="pick_and_roll", primary_defense="man_to_man",
            fg_pct=0.48, three_pt_pct=0.38, rebounds=44, assists=26,
            turnovers=12, steals=8, blocks=5,
        ))
        profile = op.build_profile()

        # 2) 성향
        ta = TendencyAnalyzer()
        ta.set_team_id("OPP001")
        for _ in range(10):
            ta.add_shot(ShotRecordInput(
                zone=CourtZone.THREE_LEFT_WING.value, made=True,
            ))
        for _ in range(5):
            ta.add_possession(PossessionRecordInput(
                play_type="pick_and_roll", is_transition=True,
            ))
        tendency = ta.analyze()

        # 3) 약점
        wf = WeaknessFinder()
        wf.set_team_id("OPP001")
        wf.add_zone_defense(ZoneDefenseInput(
            zone="paint_center", fg_attempts_allowed=20, fg_made_allowed=12,
        ))
        wf.add_three_pt_defense(ThreePointDefenseInput(
            three_pt_attempts_allowed=50, three_pt_made_allowed=20,
        ))
        weakness = wf.find_weaknesses()

        # 4) 전적
        h2h = HeadToHeadAnalyzer()
        h2h.set_opponent_id("OPP001")
        h2h.add_game(H2HGameInput(date="2026-03-01", our_score=90, opponent_score=85))
        h2h.add_game(H2HGameInput(date="2026-02-15", our_score=78, opponent_score=82))
        record = h2h.analyze()

        # 5) 종합 리포트
        rb = ScoutingReportBuilder()
        rb.set_profile(profile)
        rb.set_tendency(tendency)
        rb.set_weakness(weakness)
        rb.set_head_to_head(record)
        report = rb.build()

        assert report.team_name == "Eagles"
        assert report.profile is not None
        assert report.tendency is not None
        assert report.weakness is not None
        assert report.head_to_head is not None
        assert len(report.key_points_ko) > 0
        assert len(report.summary_ko) > 0


# =============================================================================
# 시나리오 7: Phase 4 matchup_analysis 파이프라인
# =============================================================================
class TestPhase4Matchup:
    """matchup_analysis 내부 파이프라인."""

    def test_tracker_to_evaluator(self):
        """매치업 추적 → 평가 파이프라인."""
        from game_analysis.output.matchup_analysis.matchup_tracker import (
            MatchupTracker, MatchupTrackerConfig, MatchupEventInput,
        )
        from game_analysis.output.matchup_analysis.contest_analyzer import (
            ContestAnalyzer, ContestEventInput,
        )
        from game_analysis.output.matchup_analysis.matchup_evaluator import (
            MatchupEvaluator,
        )

        # 매치업 추적
        mt = MatchupTracker(config=MatchupTrackerConfig(min_possessions_for_report=3))
        for i in range(10):
            mt.record_matchup(MatchupEventInput(
                defender_tracking_id=1, offensive_tracking_id=10,
                points_allowed=2 if i % 3 == 0 else 0,
                fg_attempted=True,
                fg_made=(i % 3 == 0),
                was_contested=(i % 2 == 0),
            ))

        matchups = mt.get_all_matchups()
        assert len(matchups) >= 1

        # 컨테스트 분석
        ca = ContestAnalyzer()
        for i in range(10):
            ca.record_contest(ContestEventInput(
                defender_tracking_id=1, shooter_tracking_id=10,
                contest_distance_m=0.5 + i * 0.2,
                shot_made=(i % 3 == 0),
            ))

        # 매치업 평가
        me = MatchupEvaluator()
        me.set_matchup_data(matchups)
        me.set_player_positions({10: "PG"})
        evals = me.evaluate_all()
        assert len(evals) >= 1
        assert evals[0].grade > 0

        # 추천
        recs = me.recommend_matchups([10])
        assert len(recs) >= 1


# =============================================================================
# 시나리오 8: 전체 파이프라인 (E2E)
# =============================================================================
class TestFullPipeline:
    """이벤트 → 스탯 → 전술 → 하이라이트 → 기록지 → 리포트."""

    def test_end_to_end(self):
        """경기 시뮬레이션 E2E."""
        from game_analysis.game_state.game_management.clock_manager import ClockManager
        from game_analysis.game_state.event_detection.shot_event_detector import (
            ShotEventDetector, ShotReleaseInput, ShotResultInput,
        )
        from game_analysis.stats.statistics.basic_stats import BasicStatsCalculator
        from game_analysis.output.highlight.highlight_detector import (
            HighlightDetector, HighlightEventInput,
        )
        from game_analysis.output.game_record.play_by_play import (
            PlayByPlayRecorder, PBPEventInput,
        )
        from game_analysis.output.game_record.game_report_builder import (
            GameReportBuilder, ReportTeamData, ReportPlayerData,
        )

        # Phase 1A: 경기 시작
        clock = ClockManager()
        clock.start_game()

        # Phase 1B: 슛 이벤트
        sd = ShotEventDetector()
        sd.process_release(ShotReleaseInput(
            frame_index=100,
            timestamp_sec=60.0,
            player_tracking_id=7,
            team_id="home",
            wrist_above_shoulder_m=0.3,
            elbow_extension_deg=160.0,
            arm_angular_velocity_degs=500.0,
            ball_distance_to_hoop_m=7.0,
            player_court_x=7.0,
            player_court_y=4.0,
            quarter=1,
            game_clock="09:00",
        ))
        shot_result = sd.process_result(ShotResultInput(
            frame_index=130,
            timestamp_sec=61.0,
            ball_through_hoop=True,
            net_deflection=0.8,
            confidence=0.92,
        ))

        # Phase 1C: 스탯 업데이트
        bs = BasicStatsCalculator()
        if shot_result is not None:
            bs.process_event(shot_result)

        # Phase 3: 하이라이트 평가
        from game_analysis.output.highlight.highlight_detector import HighlightDetectorConfig
        hd = HighlightDetector(config=HighlightDetectorConfig(
            event_scores={"shot_made_3pt": 60.0},
            threshold=55.0,
        ))
        candidate = hd.process_event(HighlightEventInput(
            event_id="EVT001",
            event_key="shot_made_3pt",
            team_id="home",
            primary_player_id=7,
            timestamp_sec=60.0,
            quarter=1,
            game_clock_sec=540.0,
            home_score=3,
            away_score=0,
            is_home_team=True,
            points_scored=3,
            highlight_type=HighlightType.THREE_POINTER,
            confidence=0.92,
        ))
        assert candidate is not None

        # Phase 3: PBP 기록
        pbp = PlayByPlayRecorder()
        entry = pbp.record_event(PBPEventInput(
            event_type=GameEventType.SHOT_MADE,
            team_id="home", player_id=7, jersey_number=7,
            quarter=1, game_clock="09:00",
            timestamp_sec=60.0, points=3,
            home_score=3, away_score=0,
            is_home_team=True, confidence=0.92,
        ))
        assert entry.sequence == 1

        # Phase 3: 게임 리포트
        rb = GameReportBuilder()
        rb.set_meta(game_date="2026-03-24", venue="Seoul Arena", league="KBL")
        rb.set_team_data(
            home=ReportTeamData(
                team_id="home", team_name="Tigers", final_score=85,
                quarter_scores=[22, 20, 25, 18],
                efg_percentage=52.0, tov_percentage=12.0,
                oreb_percentage=30.0, ft_rate=25.0,
            ),
            away=ReportTeamData(
                team_id="away", team_name="Eagles", final_score=80,
                quarter_scores=[20, 22, 18, 20],
                efg_percentage=48.0, tov_percentage=15.0,
                oreb_percentage=25.0, ft_rate=20.0,
            ),
        )
        rb.set_players(
            home_players=[ReportPlayerData(
                player_id=7, team_id="home", jersey_number=7,
                is_starter=True, points=23, rebounds=8,
                assists=5, game_score=20.0,
            )],
            away_players=[],
        )
        rb.set_pbp_summary(total=120, scoring=45)
        rb.set_game_flow(lead_changes=7, ties=4)
        report = rb.build()

        assert report.game_date == "2026-03-24"
        assert report.home_team.final_score == 85
        assert report.mvp_player_id == 7
        assert report.total_events == 120

        # JSON 출력 검증
        json_result = rb.build_json()
        assert json_result["meta"]["game_date"] == "2026-03-24"
        assert json_result["score"]["home"] == 85
