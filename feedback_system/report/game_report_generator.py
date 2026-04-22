# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/report
파일: game_report_generator.py
설명: 경기 종합 리포트 생성기.
      - 경기 분석 결과(GameStats) + 전술(TacticalAnalysisResult) + 심판 → 종합
      - analysis/ 18개 생성기 출력을 수집 → SessionSummary → FeedbackResult 조립
      - CLAUDE.md 5-3 기능 (경기 기록지, 하이라이트, 슛 로케이션 등)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from uuid import UUID, uuid4

from shared.dto.feedback_dto import (
    FeedbackItem,
    FeedbackResult,
    FeedbackSummary,
)
from shared.constants.player_constants import AgeGroup
from shared.dto.game_dto import GameStats, PlayerStats, RefereeDecision, ShotChart
from shared.dto.tactical_dto import (
    DefenseAnalysis,
    GameFlowData,
    IndividualAnalysis,
    LineupData,
    MatchupData,
    SpacingData,
    TacticalAnalysisResult,
    TransitionData,
)
from shared.dto.prediction_dto import ShotQualityPrediction
from shared.dto.scouting_dto import (
    OpponentProfile,
    TendencyReport,
    WeaknessReport,
)

# === 기존 생성기 (8개) ===
from feedback_system.analysis.game_feedback import (
    GameFeedbackConfig,
    GameFeedbackGenerator,
)
from feedback_system.analysis.tactical_feedback import (
    TacticalFeedbackConfig,
    TacticalFeedbackGenerator,
)
from feedback_system.analysis.defensive_feedback import (
    DefensiveFeedbackConfig,
    DefensiveFeedbackGenerator,
)
from feedback_system.analysis.individual_feedback import (
    IndividualFeedbackConfig,
    IndividualFeedbackGenerator,
)
from feedback_system.analysis.spatial_feedback import (
    SpatialFeedbackConfig,
    SpatialFeedbackGenerator,
)
from feedback_system.analysis.lineup_feedback import (
    LineupFeedbackConfig,
    LineupFeedbackGenerator,
)
from feedback_system.analysis.referee_feedback import (
    RefereeFeedbackConfig,
    RefereeFeedbackGenerator,
)
from feedback_system.analysis.visual_feedback_generator import (
    VisualFeedbackConfig,
    VisualFeedbackGenerator,
)

# === 신규 생성기 (7개) ===
from feedback_system.analysis.quarter_momentum_feedback import (
    QuarterMomentumFeedbackConfig,
    QuarterMomentumFeedbackGenerator,
)
from feedback_system.analysis.clutch_feedback import (
    ClutchFeedbackConfig,
    ClutchFeedbackGenerator,
)
from feedback_system.analysis.pace_tempo_feedback import (
    PaceTempoFeedbackConfig,
    PaceTempoFeedbackGenerator,
)
from feedback_system.analysis.shot_quality_feedback import (
    ShotQualityFeedbackConfig,
    ShotQualityFeedbackGenerator,
)
from feedback_system.analysis.opponent_tendency_feedback import (
    OpponentTendencyFeedbackConfig,
    OpponentTendencyFeedbackGenerator,
)
from feedback_system.analysis.rotation_feedback import (
    RotationFeedbackConfig,
    RotationFeedbackGenerator,
)
from feedback_system.analysis.strategic_recommendation_feedback import (
    StrategicRecommendationFeedbackConfig,
    StrategicRecommendationFeedbackGenerator,
)

# === 고급 분석 생성기 (3개) ===
from feedback_system.analysis.causal_feedback import (
    CausalFeedbackConfig,
    CausalFeedbackGenerator,
)
from feedback_system.analysis.game_context_feedback import (
    GameContextFeedbackConfig,
    GameContextFeedbackGenerator,
)
from feedback_system.analysis.scouting_feedback import (
    ScoutingFeedbackConfig,
    ScoutingFeedbackGenerator,
)

from feedback_system.report.session_summary import (
    SessionSummary,
    SessionSummaryConfig,
)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class GameReportConfig:
    """경기 리포트 생성 설정."""

    age_group: AgeGroup = AgeGroup.ADULT
    target_team_id: str | None = None

    # === 종합 점수 5요소 가중치 (합계 1.0) — Phase 15 M4 ===
    efg_weight: float = 0.35             # 유효 야투율
    assist_weight: float = 0.20          # 어시스트율
    turnover_weight: float = 0.20        # 턴오버율 (역)
    rebound_weight: float = 0.15         # 리바운드
    win_weight: float = 0.10             # 승리 보너스

    # === 기존 생성기 설정 ===
    game_feedback_config: GameFeedbackConfig | None = None
    tactical_feedback_config: TacticalFeedbackConfig | None = None
    defensive_feedback_config: DefensiveFeedbackConfig | None = None
    individual_feedback_config: IndividualFeedbackConfig | None = None
    spatial_feedback_config: SpatialFeedbackConfig | None = None
    lineup_feedback_config: LineupFeedbackConfig | None = None
    referee_feedback_config: RefereeFeedbackConfig | None = None
    visual_feedback_config: VisualFeedbackConfig | None = None

    # === 신규 생성기 설정 ===
    quarter_momentum_config: QuarterMomentumFeedbackConfig | None = None
    clutch_config: ClutchFeedbackConfig | None = None
    pace_tempo_config: PaceTempoFeedbackConfig | None = None
    shot_quality_config: ShotQualityFeedbackConfig | None = None
    opponent_tendency_config: OpponentTendencyFeedbackConfig | None = None
    rotation_config: RotationFeedbackConfig | None = None
    strategic_recommendation_config: StrategicRecommendationFeedbackConfig | None = None

    # === 고급 분석 생성기 설정 ===
    causal_config: CausalFeedbackConfig | None = None
    game_context_config: GameContextFeedbackConfig | None = None
    scouting_config: ScoutingFeedbackConfig | None = None

    # === 리포트 설정 ===
    session_summary_config: SessionSummaryConfig | None = None


# =============================================================================
# GameReportGenerator 클래스
# =============================================================================
class GameReportGenerator:
    """
    경기 종합 리포트 생성기.

    경기 통계, 전술 분석, 심판 판정 결과를 종합하여
    FeedbackResult를 조립합니다.
    """

    __slots__ = (
        "_config",
        # 기존 8개
        "_game_gen",
        "_tactical_gen",
        "_defensive_gen",
        "_individual_gen",
        "_spatial_gen",
        "_lineup_gen",
        "_referee_gen",
        "_visual_gen",
        # 신규 7개
        "_quarter_momentum_gen",
        "_clutch_gen",
        "_pace_tempo_gen",
        "_shot_quality_gen",
        "_opponent_tendency_gen",
        "_rotation_gen",
        "_strategic_recommendation_gen",
        # 고급 3개
        "_causal_gen",
        "_game_context_gen",
        "_scouting_gen",
        # 리포트
        "_session_summary",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: GameReportConfig | None = None) -> None:
        cfg = config or GameReportConfig()
        self._config: GameReportConfig = cfg

        # 기존 8개 생성기
        self._game_gen = GameFeedbackGenerator(cfg.game_feedback_config)
        self._tactical_gen = TacticalFeedbackGenerator(cfg.tactical_feedback_config)
        self._defensive_gen = DefensiveFeedbackGenerator(cfg.defensive_feedback_config)
        self._individual_gen = IndividualFeedbackGenerator(cfg.individual_feedback_config)
        self._spatial_gen = SpatialFeedbackGenerator(cfg.spatial_feedback_config)
        self._lineup_gen = LineupFeedbackGenerator(cfg.lineup_feedback_config)
        self._referee_gen = RefereeFeedbackGenerator(cfg.referee_feedback_config)
        self._visual_gen = VisualFeedbackGenerator(cfg.visual_feedback_config)

        # 신규 7개 생성기
        self._quarter_momentum_gen = QuarterMomentumFeedbackGenerator(cfg.quarter_momentum_config)
        self._clutch_gen = ClutchFeedbackGenerator(cfg.clutch_config)
        self._pace_tempo_gen = PaceTempoFeedbackGenerator(cfg.pace_tempo_config)
        self._shot_quality_gen = ShotQualityFeedbackGenerator(cfg.shot_quality_config)
        self._opponent_tendency_gen = OpponentTendencyFeedbackGenerator(cfg.opponent_tendency_config)
        self._rotation_gen = RotationFeedbackGenerator(cfg.rotation_config)
        self._strategic_recommendation_gen = StrategicRecommendationFeedbackGenerator(cfg.strategic_recommendation_config)

        # 고급 3개 생성기
        self._causal_gen = CausalFeedbackGenerator(cfg.causal_config)
        self._game_context_gen = GameContextFeedbackGenerator(cfg.game_context_config)
        self._scouting_gen = ScoutingFeedbackGenerator(cfg.scouting_config)

        # 리포트
        self._session_summary = SessionSummary(cfg.session_summary_config)
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "GameReportGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def generate(
        self,
        *,
        game_stats: GameStats,
        tactical_result: TacticalAnalysisResult | None = None,
        referee_decisions: list[RefereeDecision] | None = None,
        consistency_score: float | None = None,
        shot_chart: ShotChart | None = None,
        shot_predictions: list[ShotQualityPrediction] | None = None,
        game_flow: GameFlowData | None = None,
        opponent: OpponentProfile | None = None,
        tendency: TendencyReport | None = None,
        weakness: WeaknessReport | None = None,
        user_id: str = "",
        task_id: UUID | None = None,
    ) -> FeedbackResult:
        """
        경기 종합 리포트 생성 (18개 생성기 오케스트레이션).

        Args:
            game_stats: 경기 통계
            tactical_result: 전술 분석 종합 결과
            referee_decisions: AI 심판 판정 목록
            consistency_score: 판정 일관성 점수
            shot_chart: 슛 차트 데이터
            shot_predictions: xFG% 예측 데이터
            game_flow: 게임 흐름 데이터 (모멘텀, 스코링런)
            opponent: 상대팀 스카우팅 프로필
            tendency: 상대 경향 보고서
            weakness: 상대 약점 보고서
            user_id: 사용자 ID
            task_id: 분석 태스크 ID

        Returns:
            FeedbackResult (피드백 요약 + 전체 항목)
        """
        cfg = self._config
        tid = task_id or uuid4()
        all_items: list[FeedbackItem] = []

        # =====================================================================
        # 기존 8개 생성기
        # =====================================================================

        # 1. 경기 통계 피드백
        game_items = self._game_gen.generate(
            game_stats=game_stats,
            target_team_id=cfg.target_team_id or "",
        )
        all_items.extend(game_items)

        # 2. 전술 피드백
        if tactical_result is not None:
            tactical_items = self._tactical_gen.generate(tactical_result)
            all_items.extend(tactical_items)

            # 2a. 수비 피드백
            if tactical_result.defense is not None:
                defensive_items = self._defensive_gen.generate(
                    defense=tactical_result.defense,
                    matchups=tactical_result.matchups or None,
                )
                all_items.extend(defensive_items)

            # 2b. 공간 피드백
            if tactical_result.spacing is not None:
                spatial_items = self._spatial_gen.generate(
                    spacing=tactical_result.spacing,
                )
                all_items.extend(spatial_items)

            # 2c. 라인업 피드백
            if tactical_result.lineups:
                lineup_items = self._lineup_gen.generate(
                    lineups=tactical_result.lineups,
                )
                all_items.extend(lineup_items)

        # 3. 개인 선수 피드백
        players = self._collect_players(game_stats, cfg.target_team_id)
        for player in players:
            individual_items = self._individual_gen.generate(player)
            all_items.extend(individual_items)

        # 4. 심판 피드백
        if referee_decisions:
            referee_items = self._referee_gen.generate(
                decisions=referee_decisions,
                consistency_score=consistency_score,
            )
            all_items.extend(referee_items)

        # 5. 시각 피드백 (메타데이터)
        visual_items = self._visual_gen.generate(
            has_shot_data=game_stats.home_team_stats is not None,
            has_tracking_data=tactical_result is not None,
            has_play_data=(
                tactical_result is not None
                and tactical_result.set_plays is not None
            ),
            shot_count=self._count_total_shots(game_stats),
            player_count=self._count_total_players(game_stats),
        )
        all_items.extend(visual_items)

        # =====================================================================
        # 신규 7개 생성기
        # =====================================================================

        # 6. 쿼터 모멘텀 분석
        if game_flow is not None:
            momentum_items = self._quarter_momentum_gen.generate(game_flow)
            all_items.extend(momentum_items)

        # 7. 클러치 분석
        if tactical_result is not None and tactical_result.individual_analyses:
            clutch_items = self._clutch_gen.generate(tactical_result.individual_analyses)
            all_items.extend(clutch_items)

        # 8. 페이스/템포 분석
        if tactical_result is not None and tactical_result.transitions is not None:
            pace_items = self._pace_tempo_gen.generate(tactical_result.transitions)
            all_items.extend(pace_items)

        # 9. 슛 퀄리티 분석
        if shot_chart is not None:
            shot_quality_items = self._shot_quality_gen.generate(
                shot_chart,
                predictions=shot_predictions,
            )
            all_items.extend(shot_quality_items)

        # 10. 상대팀 경향 분석
        if tactical_result is not None:
            opponent_tendency_items = self._opponent_tendency_gen.generate(tactical_result)
            all_items.extend(opponent_tendency_items)

        # 11. 로테이션/벤치 분석
        if tactical_result is not None and tactical_result.lineups:
            rotation_items = self._rotation_gen.generate(
                tactical_result.lineups,
                individual_analyses=tactical_result.individual_analyses,
            )
            all_items.extend(rotation_items)

        # 12. 전략 권고
        if tactical_result is not None:
            strategic_items = self._strategic_recommendation_gen.generate(
                tactical_result, game_stats,
            )
            all_items.extend(strategic_items)

        # =====================================================================
        # 고급 3개 생성기
        # =====================================================================

        # 13. 원인 추론 분석
        causal_items = self._causal_gen.generate(
            game_stats,
            tactical_result or TacticalAnalysisResult(),
        )
        all_items.extend(causal_items)

        # 14. 경기 맥락 분석
        if game_flow is not None:
            context_items = self._game_context_gen.generate(game_stats, game_flow)
            all_items.extend(context_items)

        # 15. 스카우팅 실행도 분석
        if opponent is not None:
            scouting_items = self._scouting_gen.generate(
                game_stats, opponent,
                tendency=tendency,
                weakness=weakness,
            )
            all_items.extend(scouting_items)

        # =====================================================================
        # 세션 요약 + 결과 조립
        # =====================================================================
        summary = self._session_summary.build(
            items=all_items,
            task_id=tid,
            analysis_type="game",
            overall_score=self._calculate_overall_score(game_stats),
        )

        result = FeedbackResult(
            analysis_id=tid,
            user_id=user_id,
            summary=summary,
            feedback_items=all_items,
        )

        with self._lock:
            self._total_generated += 1

        return result

    def _collect_players(
        self,
        game_stats: GameStats,
        target_team_id: str | None,
    ) -> list[PlayerStats]:
        """대상 팀의 선수 목록 수집."""
        if target_team_id and game_stats.away_team_stats:
            if game_stats.away_team_stats.team_id == target_team_id:
                return list(game_stats.away_team_stats.player_stats)
        if game_stats.home_team_stats:
            return list(game_stats.home_team_stats.player_stats)
        return []

    def _count_total_shots(self, game_stats: GameStats) -> int:
        """총 슈팅 시도 횟수 계산."""
        total = 0
        if game_stats.home_team_stats:
            total += game_stats.home_team_stats.field_goals_attempted
        if game_stats.away_team_stats:
            total += game_stats.away_team_stats.field_goals_attempted
        return total

    def _count_total_players(self, game_stats: GameStats) -> int:
        """총 선수 수 계산."""
        count = 0
        if game_stats.home_team_stats:
            count += len(game_stats.home_team_stats.player_stats)
        if game_stats.away_team_stats:
            count += len(game_stats.away_team_stats.player_stats)
        return count

    def _calculate_overall_score(self, game_stats: GameStats) -> float:
        """
        경기 전체 점수 산출 (다면 가중 평균).

        FG%, 어시스트 비율, 턴오버율, 리바운드 비율을 종합하여
        0~100 범위의 경기 수행 점수를 산출합니다.
        """
        team = game_stats.home_team_stats
        if self._config.target_team_id and game_stats.away_team_stats:
            if game_stats.away_team_stats.team_id == self._config.target_team_id:
                team = game_stats.away_team_stats

        if team is None:
            return 50.0

        # 1. eFG% 점수 (가중 0.35) — 리그 평균 ~52%, 우수 ~58%
        efg = team.calculate_effective_field_goal_percentage()
        efg_score = min((efg / 60.0) * 100.0, 100.0)

        # 2. 어시스트율 점수 (가중 0.20) — 리그 평균 ~58%, 우수 ~65%
        ast_pct = team.calculate_assist_percentage()
        ast_score = min((ast_pct / 70.0) * 100.0, 100.0)

        # 3. 턴오버율 역점수 (가중 0.20) — 낮을수록 좋음, 평균 ~13%
        tov_pct = team.calculate_turnover_percentage()
        tov_score = max(100.0 - (tov_pct / 20.0) * 100.0, 0.0)

        # 4. 리바운드 점수 (가중 0.15) — 총 리바운드 기반
        reb_score = min((team.total_rebounds / 50.0) * 100.0, 100.0)

        # 5. 승리 보너스 (가중 0.10)
        win_score = 0.0
        if team.is_home and game_stats.home_score > game_stats.away_score:
            win_score = 100.0
        elif not team.is_home and game_stats.away_score > game_stats.home_score:
            win_score = 100.0
        elif game_stats.home_score == game_stats.away_score:
            win_score = 50.0

        # 5요소 가중 평균 (Config 기반 — Phase 15 M4)
        cfg = self._config
        overall = (
            efg_score * cfg.efg_weight
            + ast_score * cfg.assist_weight
            + tov_score * cfg.turnover_weight
            + reb_score * cfg.rebound_weight
            + win_score * cfg.win_weight
        )
        return round(min(100.0, max(0.0, overall)), 1)

    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"GameReportGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "GameReportGenerator",
    "GameReportConfig",
]

__version__ = "1.0.0"
