# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: strategic_recommendation_feedback.py
설명: 종합 전략 권고 피드백 생성기.
      - 공격 전략 제안, 수비 조정, 매치업 착취, 페이스 조율, 핵심 선수 활용
      - TacticalAnalysisResult + GameStats → FeedbackItem 변환
      - 전 분석 모듈의 결과를 통합하여 고수준 전략적 권고를 도출

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from shared.constants.feedback_constants import (
    FEEDBACK_MIN_DETAIL_POINTS,
    FeedbackSeverity,
)
from shared.dto.feedback_dto import (
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackType,
)
from shared.constants.player_constants import AgeGroup
from shared.dto.game_dto import GameStats, TeamStats
from shared.dto.tactical_dto import (
    DefenseScheme,
    TacticalAnalysisResult,
)

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.korean_templates import KoreanTemplates
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper, get_default_korean_templates


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class StrategicRecommendationFeedbackConfig:
    """종합 전략 권고 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # 점수차 임계치
    min_significant_gap: float = 5.0      # 유의미한 점수차 기준

    # 전략 신뢰도 임계치
    strategy_confidence_threshold: float = 0.70

    # 슈팅 효율 임계치
    efg_good_threshold: float = 53.0      # eFG% 53 이상 → 양호
    efg_poor_threshold: float = 45.0      # eFG% 45 이하 → 부진

    # 턴오버율 임계치
    tov_good_threshold: float = 12.0      # TOV% 12 이하 → 양호
    tov_warning_threshold: float = 18.0   # TOV% 18 이상 → 경보

    # 자유투 비율 임계치 (FTA/FGA)
    ft_rate_good: float = 25.0            # FT Rate 25 이상 → 파울 유도 적극적

    # 3점 비율 임계치
    three_pt_rate_good: float = 36.0      # 3점 시도 비율 36% 이상 → 3점 중심
    three_pt_pct_good: float = 36.0       # 3점 성공률 36% 이상 → 유효

    # 페인트 득점 임계치
    paint_pts_good: float = 44.0          # 페인트 득점 44 이상 → 인사이드 강점

    # 속공 득점 임계치
    fast_break_pts_good: float = 14.0     # 속공 득점 14 이상 → 전환 강점

    # 세컨드 찬스 득점 임계치
    second_chance_pts_good: float = 10.0  # 세컨드 찬스 10 이상 → 리바운드 공세

    # 어시스트율 임계치
    ast_pct_good: float = 55.0            # AST% 55 이상 → 볼 무브 양호

    # 벤치 득점 임계치
    bench_pts_good: float = 20.0          # 벤치 득점 20 이상 → 로테이션 깊이 확보

    # PPP 임계치
    pnr_ppp_weak: float = 0.90            # 픽앤롤 PPP 0.90 이하 → 조정 필요
    transition_ppp_strong: float = 1.15   # 전환 공격 PPP 1.15 이상 → 속공 집중 전략


# =============================================================================
# StrategicRecommendationFeedbackGenerator 클래스
# =============================================================================
class StrategicRecommendationFeedbackGenerator:
    """
    종합 전략 권고 피드백 생성기.

    TacticalAnalysisResult와 GameStats를 통합하여
    공격 전략, 수비 조정, 매치업 착취, 페이스 조율,
    핵심 선수 활용 등 고수준 전략 권고를 생성합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_lock",
        "_total_generated",
    )

    def __init__(
        self,
        config: StrategicRecommendationFeedbackConfig | None = None,
    ) -> None:
        self._config: StrategicRecommendationFeedbackConfig = (
            config or StrategicRecommendationFeedbackConfig()
        )
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "StrategicRecommendationFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def generate(
        self,
        analysis: TacticalAnalysisResult,
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """
        전술 분석 및 경기 통계에서 종합 전략 권고 피드백 생성.

        Args:
            analysis: Phase 3 전술 분석 종합 DTO
            game_stats: 경기 통계 DTO

        Returns:
            FeedbackItem 목록
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        home = game_stats.home_team_stats
        away = game_stats.away_team_stats

        # 1. 경기 점수 상황 분석 (리드/추격 전략)
        items.extend(self._analyze_score_situation(game_stats, cfg))

        # 2. 공격 효율성 종합 진단 (홈팀 기준, 양팀 비교)
        if home is not None:
            items.extend(self._analyze_offensive_strategy(home, away, analysis, cfg))

        # 3. 수비 조정 권고 (상대 공격 대응)
        if analysis.defense is not None:
            items.extend(self._analyze_defensive_adjustment(analysis, away, cfg))

        # 4. 매치업 착취 전략
        if analysis.matchups:
            items.extend(self._analyze_matchup_exploitation(analysis, cfg))

        # 5. 페이스 조율 전략
        if home is not None and away is not None:
            items.extend(self._analyze_pace_control(home, away, analysis, cfg))

        # 6. 4 팩터 기반 전략 권고
        if home is not None and away is not None:
            items.extend(self._analyze_four_factors(home, away, cfg))

        # 7. 리바운드 전술 권고
        if analysis.rebound_analysis is not None:
            items.extend(self._analyze_rebound_strategy(analysis, home, cfg))

        # 8. 클러치 타임 전략
        if game_stats.lead_changes is not None or game_stats.ties is not None:
            items.extend(self._analyze_clutch_strategy(game_stats, analysis, cfg))

        # 9. 전환 공격 활용 전략
        if analysis.transitions is not None:
            items.extend(self._analyze_transition_strategy(analysis, cfg))

        # 10. 세트 플레이 개선 권고
        if analysis.set_plays is not None and analysis.set_plays.total_set_plays > 0:
            items.extend(self._analyze_set_play_recommendation(analysis, cfg))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 1. 경기 점수 상황 분석
    # -------------------------------------------------------------------------
    def _analyze_score_situation(
        self,
        game_stats: GameStats,
        cfg: StrategicRecommendationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """경기 점수 상황 기반 전략 방향 설정."""
        items: list[FeedbackItem] = []

        home_score = game_stats.home_score
        away_score = game_stats.away_score
        gap = abs(home_score - away_score)
        home_leading = home_score > away_score

        if gap >= cfg.min_significant_gap:
            leading_team = "홈팀" if home_leading else "원정팀"
            trailing_team = "원정팀" if home_leading else "홈팀"
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.HIGH,
                title="현재 점수 상황 전략 방향",
                description=(
                    f"현재 스코어 홈 {home_score} : 원정 {away_score} "
                    f"({leading_team} {gap}점 리드). "
                    + (
                        f"{leading_team} 전략: "
                        "리드를 유지하는 방어적 공격 운용이 핵심입니다. "
                        "볼 점유 시간을 늘리고 안전한 포제션을 우선시하세요. "
                        "오펜시브 파울을 피하고 자유투 성공에 집중하세요. "
                        f"{trailing_team} 전략: "
                        "빠른 페이스로 게임을 이끌고 3점슛 기회를 적극 창출하세요. "
                        "수비에서 스틸과 전환 공격으로 빠른 포제션 만회를 노리세요."
                    )
                ),
                suggestion=(
                    f"리드팀: 클락 관리 + 파울 회피 + FT 집중. "
                    f"추격팀: 3점슛 + 트랩 수비 + 빠른 전환."
                ),
                current_value=float(gap),
                ideal_value=0.0,
                confidence=cfg.strategy_confidence_threshold,
            ))
        else:
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title="박빙 경기 전략 방향",
                description=(
                    f"현재 스코어 홈 {home_score} : 원정 {away_score} (차이 {gap}점). "
                    "박빙 상황에서 포제션 가치가 극대화됩니다. "
                    "턴오버를 최소화하고 고확률 슛을 선택하세요. "
                    "수비에서 클린 파울을 피하면서도 적극적인 헬프 수비를 유지하세요. "
                    "타임아웃을 전략적으로 아껴 클러치 타임에 사용하세요."
                ),
                suggestion="턴오버 최소화 + 고확률 슛 선택 + 타임아웃 비축",
                current_value=float(gap),
                confidence=cfg.strategy_confidence_threshold,
            ))

        # 리드 변경/동점 빈도 기반 경기 흐름 분석
        lead_changes = game_stats.lead_changes
        ties = game_stats.ties
        if lead_changes >= 10 or ties >= 5:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title="경기 흐름 변동성 분석",
                description=(
                    f"리드 변경 {lead_changes}회, 동점 {ties}회로 "
                    "매우 유동적인 경기 흐름이 지속되고 있습니다. "
                    "모멘텀 전환점을 정확히 인식하고 "
                    "상대의 런(연속 득점) 시 즉시 타임아웃을 통한 흐름 차단이 중요합니다. "
                    "안정적인 볼 무브먼트로 자멸적 턴오버를 방지하세요."
                ),
                confidence=0.85,
            ))

        return items

    # -------------------------------------------------------------------------
    # 2. 공격 효율성 종합 진단
    # -------------------------------------------------------------------------
    def _analyze_offensive_strategy(
        self,
        home: TeamStats,
        away: TeamStats | None,
        analysis: TacticalAnalysisResult,
        cfg: StrategicRecommendationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """공격 효율성 종합 진단 및 전략 제안."""
        items: list[FeedbackItem] = []

        # 홈팀 eFG% 분석
        efg = home.calculate_effective_field_goal_percentage()
        if efg > 0:
            is_good_efg = efg >= cfg.efg_good_threshold
            is_poor_efg = efg <= cfg.efg_poor_threshold
            sev = self._severity_mapper.from_score(min(efg * 1.2, 100.0))
            items.append(FeedbackItem(
                category=FeedbackCategory.POWER,
                feedback_type=(
                    FeedbackType.POSITIVE if is_good_efg
                    else FeedbackType.CORRECTION if is_poor_efg
                    else FeedbackType.TIP
                ),
                priority=FeedbackFormatter.severity_to_priority(sev.severity),
                title="유효 야투율(eFG%) 기반 공격 전략",
                description=(
                    f"홈팀 eFG% {efg:.1f}%. "
                    + (f"원정팀 eFG% {away.calculate_effective_field_goal_percentage():.1f}%. "
                       if away is not None else "")
                    + (
                        "유효 야투율이 우수합니다. "
                        "현재 슛 셀렉션 패턴(3점슛/페인트 공략 비율)을 유지하고 "
                        "고확률 슛 창출 패턴을 지속하세요."
                        if is_good_efg
                        else
                        "유효 야투율이 낮습니다. "
                        "미드레인지 의존도를 낮추고 림 어택과 코너 3점 기회를 늘리세요. "
                        "페인트 진입 후 파울 유도 또는 킥아웃으로 고효율 슛을 창출하세요."
                        if is_poor_efg
                        else
                        "유효 야투율이 평균 수준입니다. "
                        "픽앤롤 후 롤러 공략 및 코너 3점슛 비중을 높여 효율을 개선하세요."
                    )
                ),
                current_value=efg,
                ideal_value=cfg.efg_good_threshold,
                unit="percent",
                confidence=0.90,
            ))

        # 어시스트율 기반 볼 무브먼트 전략
        ast_pct = home.calculate_assist_percentage()
        if ast_pct > 0:
            is_good_ast = ast_pct >= cfg.ast_pct_good
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.POSITIVE if is_good_ast else FeedbackType.CORRECTION,
                priority=FeedbackPriority.MEDIUM if is_good_ast else FeedbackPriority.HIGH,
                title="어시스트율 기반 팀 공격 전략",
                description=(
                    f"홈팀 어시스트율 {ast_pct:.1f}% "
                    f"(어시스트 {home.assists}회 / 야투 성공 {home.field_goals_made}개). "
                    + (
                        "팀 볼 무브먼트가 원활합니다. "
                        "패스 연계 공격이 개인 고효율 슛으로 연결되고 있습니다. "
                        "오픈 슈터 발굴을 위한 오프볼 무브먼트를 더 강화하세요."
                        if is_good_ast
                        else
                        "어시스트율이 낮아 개인 플레이 의존도가 높습니다. "
                        "볼 공유 의식 강화와 세트 플레이 활용으로 "
                        "팀원을 적극 활용하는 공격 패턴으로 전환하세요. "
                        "드라이브 앤 킥아웃을 통한 오픈 슈터 창출이 핵심입니다."
                    )
                ),
                current_value=ast_pct,
                ideal_value=cfg.ast_pct_good,
                unit="percent",
                confidence=0.88,
            ))

        # 페인트 득점 전략
        paint_pts = home.points_in_paint
        if paint_pts > 0:
            is_strong_inside = paint_pts >= cfg.paint_pts_good
            items.append(FeedbackItem(
                category=FeedbackCategory.POWER,
                feedback_type=FeedbackType.POSITIVE if is_strong_inside else FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title="인사이드(페인트) 공격 전략",
                description=(
                    f"홈팀 페인트 득점 {paint_pts}점. "
                    + (
                        "인사이드 공격이 효과적입니다. "
                        "페인트 진입 후 드라이브 마무리 또는 킥아웃 패스를 통해 "
                        "상대 수비를 지속적으로 붕괴시키세요."
                        if is_strong_inside
                        else
                        "인사이드 공격이 부족합니다. "
                        "포스트업, 드라이브 마무리, 컷 플레이를 통해 "
                        "페인트 공략을 강화하면 상대 수비를 안쪽으로 끌어들여 "
                        "외곽 3점 공간을 확보할 수 있습니다."
                    )
                ),
                current_value=float(paint_pts),
                ideal_value=cfg.paint_pts_good,
                confidence=0.87,
            ))

        # 3점슛 전략
        if home.three_pointers_attempted > 0:
            total_fg_attempts = max(home.field_goals_attempted, 1)
            three_pt_rate = home.three_pointers_attempted / total_fg_attempts * 100
            three_pt_pct = home.three_point_percentage
            is_good_3pt = three_pt_pct >= cfg.three_pt_pct_good
            is_high_rate = three_pt_rate >= cfg.three_pt_rate_good
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=(
                    FeedbackType.POSITIVE if is_good_3pt
                    else FeedbackType.CORRECTION
                ),
                priority=FeedbackPriority.HIGH if not is_good_3pt else FeedbackPriority.MEDIUM,
                title="3점슛 전략 진단",
                description=(
                    f"3점슛 시도 {home.three_pointers_attempted}회 "
                    f"(전체 야투 중 {three_pt_rate:.0f}%), "
                    f"성공 {home.three_pointers_made}개, "
                    f"성공률 {three_pt_pct:.1f}%. "
                    + (
                        "3점슛 효율이 우수합니다. "
                        "오픈 3점 기회를 최대한 활용하고 "
                        "스페이싱을 통한 3점 창출 전술을 유지하세요."
                        if is_good_3pt
                        else
                        "3점슛 성공률이 낮습니다. "
                        + (
                            "3점 시도 빈도는 높지만 성공률이 낮습니다. "
                            "더 오픈된 상황에서만 3점슛을 시도하고 "
                            "드라이브-킥아웃으로 고품질 3점 기회를 만드세요."
                            if is_high_rate
                            else
                            "3점 시도를 늘려 상대 수비 범위를 확장하거나, "
                            "인사이드 공격에 더 집중하여 파울을 유도하는 전략을 병행하세요."
                        )
                    )
                ),
                current_value=three_pt_pct,
                ideal_value=cfg.three_pt_pct_good,
                unit="percent",
                confidence=0.88,
            ))

        # 벤치 득점 기여 전략
        bench_pts = home.bench_points
        if bench_pts > 0:
            is_good_bench = bench_pts >= cfg.bench_pts_good
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE if is_good_bench else FeedbackType.CORRECTION,
                priority=FeedbackPriority.LOW if is_good_bench else FeedbackPriority.MEDIUM,
                title="벤치 득점 기여 전략",
                description=(
                    f"벤치 득점 {bench_pts}점. "
                    + (
                        "벤치 기여가 풍부하여 로테이션 깊이가 확보되어 있습니다. "
                        "후반 스타터 체력 관리가 용이하므로 클러치 타임을 위해 "
                        "핵심 선수 출전 시간을 아껴두세요."
                        if is_good_bench
                        else
                        "벤치 득점이 낮습니다. "
                        "스타터의 체력 소모 부담이 증가할 수 있습니다. "
                        "벤치 선수의 세트 플레이 활용과 자신 있는 슛 옵션을 늘려주세요."
                    )
                ),
                current_value=float(bench_pts),
                ideal_value=cfg.bench_pts_good,
                confidence=0.82,
            ))

        return items

    # -------------------------------------------------------------------------
    # 3. 수비 조정 권고
    # -------------------------------------------------------------------------
    def _analyze_defensive_adjustment(
        self,
        analysis: TacticalAnalysisResult,
        away: TeamStats | None,
        cfg: StrategicRecommendationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """수비 조정 권고."""
        items: list[FeedbackItem] = []
        defense = analysis.defense

        if defense is None:
            return items

        # 상대 터치 빈도 및 스페이싱 기반 수비 조정
        if analysis.spacing is not None:
            spacing = analysis.spacing
            is_wide_spacing = spacing.avg_player_spacing >= 5.0
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.HIGH,
                title="상대 스페이싱 대응 수비 조정",
                description=(
                    f"상대 평균 선수 간격 {spacing.avg_player_spacing:.1f}m, "
                    f"드라이브 레인 개방도 {spacing.drive_lane_openness:.0f}점, "
                    f"3점 라인 스페이싱 {spacing.three_point_spacing:.1f}m. "
                    + (
                        "상대가 넓은 스페이싱으로 수비를 분산시키고 있습니다. "
                        "3점 슈터에 대한 즉각적인 클로즈아웃과 "
                        "픽앤롤 수비 시 스위치 능력이 중요합니다. "
                        "헬프 수비 거리를 유지하여 킥아웃 패스에 대비하세요."
                        if is_wide_spacing
                        else
                        "상대가 좁은 스페이싱으로 인사이드에 집중하고 있습니다. "
                        "페인트 수비를 강화하고 드라이브 경로를 차단하세요. "
                        "이중 블락 전술과 박스아웃 강화로 세컨드 찬스를 억제하세요."
                    )
                ),
                confidence=cfg.strategy_confidence_threshold,
            ))

        # 상대 속공 허용 여부 기반 수비 전환 전략
        if away is not None:
            opp_fast_break = away.fast_break_points
            if opp_fast_break >= 10:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIMING,
                    feedback_type=FeedbackType.CORRECTION,
                    priority=FeedbackPriority.CRITICAL,
                    title="상대 속공 억제 수비 전략",
                    description=(
                        f"상대 속공 득점 {opp_fast_break}점. "
                        "상대 속공 생산이 활발합니다. "
                        "슛 시도 이후 즉각 수비 전환하는 규율이 필요합니다. "
                        "리바운드 후 아웃렛 패스 시작 선수를 반드시 압박하고 "
                        "2명 이상이 속공 방어 위치로 즉시 복귀하세요. "
                        "파울을 감수하더라도 2대0 속공은 반드시 차단하세요."
                    ),
                    current_value=float(opp_fast_break),
                    ideal_value=0.0,
                    confidence=0.90,
                ))

        # 수비 스킴 조정 권고
        scheme = defense.primary_scheme
        drtg = defense.defensive_rating
        if drtg >= 110.0:
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title="수비 스킴 조정 권고",
                description=(
                    f"현재 수비 효율(DRtg) {drtg:.1f}로 실점이 과다합니다. "
                    f"현재 주요 스킴: {scheme.value}. "
                    + self._get_defensive_scheme_adjustment(scheme, drtg)
                ),
                suggestion="수비 스킴 다양화 및 포제션별 수비 설정 변경 검토",
                current_value=drtg,
                ideal_value=100.0,
                unit="DRtg",
                confidence=0.87,
            ))

        # 스틸/블락 활용 전략
        if away is not None:
            opp_tov_pct = away.calculate_turnover_percentage()
            if opp_tov_pct >= 15.0:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIMING,
                    feedback_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.MEDIUM,
                    title="상대 턴오버 유발 수비 전략 강화",
                    description=(
                        f"상대 턴오버율 {opp_tov_pct:.1f}%로 볼 관리가 불안정합니다. "
                        "적극적인 트랩 수비와 패스 라인 차단으로 "
                        "상대 턴오버를 더욱 유발하세요. "
                        "속공 전환 준비를 병행하면 빠른 득점 기회를 얻을 수 있습니다."
                    ),
                    current_value=opp_tov_pct,
                    confidence=0.85,
                ))

        return items

    # -------------------------------------------------------------------------
    # 4. 매치업 착취 전략
    # -------------------------------------------------------------------------
    def _analyze_matchup_exploitation(
        self,
        analysis: TacticalAnalysisResult,
        cfg: StrategicRecommendationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """매치업 착취 전략 도출."""
        items: list[FeedbackItem] = []

        # FG% 허용이 높은 매치업 (상대 수비 약점) 상위 3개
        exploitable = sorted(
            [m for m in analysis.matchups if m.fg_attempts >= 3 and m.fg_pct >= 50.0],
            key=lambda x: x.fg_pct,
            reverse=True,
        )

        for matchup in exploitable[:3]:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title=f"착취 가능 매치업: #{matchup.defender_tracking_id} 수비",
                description=(
                    f"공격수 #{matchup.offensive_tracking_id}가 "
                    f"수비수 #{matchup.defender_tracking_id}를 상대로 "
                    f"FG% {matchup.fg_pct:.1f}% 기록 "
                    f"({matchup.fg_made}/{matchup.fg_attempts}, "
                    f"{matchup.possessions}포제션). "
                    "이 매치업에서 공격수가 우위를 점하고 있습니다. "
                    "아이솔레이션, 픽앤롤 볼핸들러, 포스트업 등을 통해 "
                    "이 매치업을 의도적으로 만들어 내세요."
                ),
                current_value=matchup.fg_pct,
                confidence=cfg.strategy_confidence_threshold,
            ))

        # 컨테스트율이 낮은 수비수 (오픈 슛 허용)
        low_contest = sorted(
            [m for m in analysis.matchups if m.fg_attempts >= 3 and m.contest_rate < 0.40],
            key=lambda x: x.contest_rate,
        )
        for matchup in low_contest[:2]:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"오픈 슛 허용 수비수: #{matchup.defender_tracking_id}",
                description=(
                    f"수비수 #{matchup.defender_tracking_id}: "
                    f"컨테스트율 {matchup.contest_rate * 100:.0f}% "
                    f"({matchup.fg_attempts}회 슛 기회). "
                    "이 수비수는 슈터에게 오픈 슛 기회를 자주 허용합니다. "
                    "해당 수비수와 매치된 슈터에게 볼을 집중시키고 "
                    "드라이브-킥아웃 전술로 오픈 3점을 창출하세요."
                ),
                current_value=matchup.contest_rate * 100,
                confidence=0.85,
            ))

        return items

    # -------------------------------------------------------------------------
    # 5. 페이스 조율 전략
    # -------------------------------------------------------------------------
    def _analyze_pace_control(
        self,
        home: TeamStats,
        away: TeamStats,
        analysis: TacticalAnalysisResult,
        cfg: StrategicRecommendationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """페이스 조율 전략 권고."""
        items: list[FeedbackItem] = []

        # 양팀 페이스 추정
        home_pace = home.calculate_pace(opponent_stats=away)
        away_pace = away.calculate_pace(opponent_stats=home)
        pace_diff = home_pace - away_pace

        # 빠른 페이스 선호 상황 분석
        trans = analysis.transitions
        if trans is not None:
            transition_advantage = (
                trans.transition_ppp >= cfg.transition_ppp_strong
                and trans.transition_frequency >= 0.15
            )

            if transition_advantage:
                items.append(FeedbackItem(
                    category=FeedbackCategory.RHYTHM,
                    feedback_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.HIGH,
                    title="고속 페이스 유지 전략 권고",
                    description=(
                        f"전환 공격 PPP {trans.transition_ppp:.2f} (우수), "
                        f"전환 빈도 {trans.transition_frequency * 100:.0f}%. "
                        f"추정 경기 페이스 홈 {home_pace:.0f} / 원정 {away_pace:.0f}. "
                        "전환 공격 효율이 높습니다. "
                        "빠른 페이스를 유지하여 상대가 하프코트 수비를 세울 기회를 줄이세요. "
                        "리바운드 후 즉각적인 아웃렛과 패스트브레이크 상황을 의도적으로 만드세요."
                    ),
                    suggestion="리바운드 후 3초 이내 속공 전환 훈련 강화",
                    current_value=trans.transition_ppp,
                    confidence=0.88,
                ))
            elif trans.halfcourt_ppp >= 1.05 and trans.transition_ppp < 1.0:
                items.append(FeedbackItem(
                    category=FeedbackCategory.RHYTHM,
                    feedback_type=FeedbackType.TIP,
                    priority=FeedbackPriority.MEDIUM,
                    title="하프코트 페이스 집중 전략 권고",
                    description=(
                        f"하프코트 PPP {trans.halfcourt_ppp:.2f} (전환 PPP {trans.transition_ppp:.2f}보다 높음). "
                        "하프코트 공격이 더 효율적입니다. "
                        "페이스를 낮추고 세트 플레이와 볼 무브먼트를 통한 "
                        "고품질 하프코트 공격에 집중하세요. "
                        "상대의 속공 기회를 줄이는 볼 관리가 핵심입니다."
                    ),
                    suggestion="세트 플레이 비중 확대 + 포제션 관리 훈련",
                    current_value=trans.halfcourt_ppp,
                    confidence=0.87,
                ))

        # 양팀 페이스 차이 기반 전략
        if abs(pace_diff) >= 5.0:
            prefer_fast = pace_diff > 0  # 홈팀이 더 빠른 페이스 선호
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title="페이스 불일치 전략 활용",
                description=(
                    f"홈팀 추정 페이스 {home_pace:.0f}, 원정팀 {away_pace:.0f} "
                    f"(차이 {abs(pace_diff):.0f}포제션). "
                    + (
                        "홈팀이 더 빠른 페이스를 구사하고 있습니다. "
                        "속도 우위를 활용하여 상대가 정비하기 전에 공격하세요. "
                        "수비 전환 후 즉각적인 볼 운반과 얼리 오펜스를 활용하세요."
                        if prefer_fast
                        else
                        "원정팀이 더 빠른 페이스를 구사하고 있습니다. "
                        "홈팀은 페이스를 의도적으로 낮추고 하프코트 공격에 집중하세요. "
                        "볼 점유 시간을 늘리고 상대의 빠른 공격 리듬을 끊으세요."
                    )
                ),
                current_value=abs(pace_diff),
                confidence=0.83,
            ))

        return items

    # -------------------------------------------------------------------------
    # 6. 4 팩터 기반 전략 권고
    # -------------------------------------------------------------------------
    def _analyze_four_factors(
        self,
        home: TeamStats,
        away: TeamStats,
        cfg: StrategicRecommendationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """Dean Oliver 4 팩터 기반 전략 권고."""
        items: list[FeedbackItem] = []

        home_factors = home.get_four_factors(away)
        away_factors = away.get_four_factors(home)

        # 턴오버율 비교 전략
        home_tov = home_factors.get("turnover_percentage", 0.0)
        away_tov = away_factors.get("turnover_percentage", 0.0)
        if home_tov > 0 or away_tov > 0:
            tov_diff = home_tov - away_tov
            items.append(FeedbackItem(
                category=FeedbackCategory.BALL_CONTROL,
                feedback_type=(
                    FeedbackType.CORRECTION if home_tov >= cfg.tov_warning_threshold
                    else FeedbackType.POSITIVE if home_tov <= cfg.tov_good_threshold
                    else FeedbackType.TIP
                ),
                priority=(
                    FeedbackPriority.CRITICAL if home_tov >= cfg.tov_warning_threshold
                    else FeedbackPriority.MEDIUM
                ),
                title="턴오버율 4팩터 전략 분석",
                description=(
                    f"홈팀 TOV% {home_tov:.1f}% vs 원정팀 TOV% {away_tov:.1f}% "
                    f"(차이 {tov_diff:+.1f}%). "
                    + (
                        "홈팀 턴오버율이 심각하게 높습니다. "
                        "볼 보호를 최우선 과제로 삼고 "
                        "고난도 패스와 1대1 상황의 드리블 과다를 줄이세요. "
                        "간단하고 안전한 패스를 선택하는 문화를 강조하세요."
                        if home_tov >= cfg.tov_warning_threshold
                        else
                        "홈팀 볼 관리가 우수합니다. "
                        f"상대 TOV% {away_tov:.1f}%를 더 높이기 위해 "
                        "적극적인 트랩과 패스 라인 차단 수비를 강화하세요."
                        if home_tov <= cfg.tov_good_threshold
                        else
                        "턴오버율이 평균 수준입니다. "
                        "위험한 포제션에서의 볼 관리 집중 훈련이 필요합니다."
                    )
                ),
                current_value=home_tov,
                ideal_value=cfg.tov_good_threshold,
                unit="percent",
                confidence=0.90,
            ))

        # 자유투 비율 전략 (공격적 파울 유도)
        home_ft_rate = home_factors.get("free_throw_rate", 0.0)
        away_ft_rate = away_factors.get("free_throw_rate", 0.0)
        if home_ft_rate > 0 or away_ft_rate > 0:
            items.append(FeedbackItem(
                category=FeedbackCategory.POWER,
                feedback_type=(
                    FeedbackType.POSITIVE if home_ft_rate >= cfg.ft_rate_good
                    else FeedbackType.CORRECTION
                ),
                priority=FeedbackPriority.MEDIUM,
                title="자유투 비율(FT Rate) 전략",
                description=(
                    f"홈팀 FT Rate {home_ft_rate:.1f}% vs 원정팀 {away_ft_rate:.1f}%. "
                    + (
                        "파울 유도가 효과적입니다. "
                        "드라이브 공격과 포스트업으로 상대 수비의 파울을 지속적으로 유도하고 "
                        "자유투 성공률을 높이는 훈련을 병행하세요."
                        if home_ft_rate >= cfg.ft_rate_good
                        else
                        "파울 유도 시도가 부족합니다. "
                        "드라이브 마무리 시 바디 컨택을 활용하고 "
                        "포스트업에서 더 적극적인 파울 유도 동작을 훈련하세요. "
                        "자유투는 경기 후반 점수차를 좁히는 데 핵심적입니다."
                    )
                ),
                current_value=home_ft_rate,
                ideal_value=cfg.ft_rate_good,
                unit="percent",
                confidence=0.87,
            ))

        # 공격 리바운드율 전략
        home_orb_pct = home_factors.get("offensive_rebound_percentage", 0.0)
        away_orb_pct = away_factors.get("offensive_rebound_percentage", 0.0)
        if home_orb_pct > 0 or away_orb_pct > 0:
            orb_diff = home_orb_pct - away_orb_pct
            items.append(FeedbackItem(
                category=FeedbackCategory.POWER,
                feedback_type=(
                    FeedbackType.POSITIVE if home_orb_pct >= 30.0
                    else FeedbackType.CORRECTION if home_orb_pct < 20.0
                    else FeedbackType.TIP
                ),
                priority=(
                    FeedbackPriority.HIGH if home_orb_pct < 20.0
                    else FeedbackPriority.MEDIUM
                ),
                title="공격 리바운드율(ORB%) 전략",
                description=(
                    f"홈팀 ORB% {home_orb_pct:.1f}% vs 원정팀 {away_orb_pct:.1f}% "
                    f"(홈팀 우위 {orb_diff:+.1f}%). "
                    + (
                        "공격 리바운드에서 크게 우위를 점하고 있습니다. "
                        "세컨드 찬스 포인트를 극대화하고 "
                        "오펜시브 리바운드 크래시를 전술적으로 유지하세요."
                        if home_orb_pct >= 30.0
                        else
                        "공격 리바운드 확보가 부족합니다. "
                        "슛 시도 이후 1~2명의 공격 크래시 역할을 고정하고 "
                        "미스 슛의 스크린-아웃 저항 훈련을 강화하세요."
                        if home_orb_pct < 20.0
                        else
                        "공격 리바운드율이 평균 수준입니다. "
                        "롱 리바운드 예측 포지셔닝을 훈련하여 효율을 높이세요."
                    )
                ),
                current_value=home_orb_pct,
                unit="percent",
                confidence=0.87,
            ))

        return items

    # -------------------------------------------------------------------------
    # 7. 리바운드 전술 권고
    # -------------------------------------------------------------------------
    def _analyze_rebound_strategy(
        self,
        analysis: TacticalAnalysisResult,
        home: TeamStats | None,
        cfg: StrategicRecommendationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """리바운드 전술 권고."""
        items: list[FeedbackItem] = []
        reb = analysis.rebound_analysis
        if reb is None:
            return items

        # 세컨드 찬스 전략
        scp = reb.second_chance_points
        scr = reb.second_chance_conversion_rate
        is_good_sc = scp >= cfg.second_chance_pts_good

        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=FeedbackType.POSITIVE if is_good_sc else FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title="세컨드 찬스 전술 권고",
            description=(
                f"세컨드 찬스 득점 {scp}점, "
                f"전환율 {scr * 100:.0f}%, "
                f"공격 리바운드 {reb.offensive_rebounds}개. "
                + (
                    "세컨드 찬스 득점이 효과적입니다. "
                    "공격 크래시 전술을 유지하고 "
                    "미스 슛 후 3점 라인 밖 선수들의 리바운드 포지셔닝을 강화하세요."
                    if is_good_sc
                    else
                    "공격 리바운드 이후 마무리가 부족합니다. "
                    "오펜시브 리바운드 확보 후 빠른 업-앤-언더 또는 "
                    "외곽 리셋 패스를 통한 새로운 공격 전개를 연습하세요."
                )
            ),
            current_value=float(scp),
            ideal_value=cfg.second_chance_pts_good,
            confidence=0.86,
        ))

        return items

    # -------------------------------------------------------------------------
    # 8. 클러치 타임 전략
    # -------------------------------------------------------------------------
    def _analyze_clutch_strategy(
        self,
        game_stats: GameStats,
        analysis: TacticalAnalysisResult,
        cfg: StrategicRecommendationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """클러치 타임 전략 권고."""
        items: list[FeedbackItem] = []

        # 클러치 기여 선수가 있는지 확인
        clutch_players = [
            ind for ind in analysis.individual_analyses
            if ind.clutch_stats is not None and ind.clutch_stats.points > 0
        ]

        if clutch_players:
            best_clutch = max(
                clutch_players,
                key=lambda x: x.clutch_stats.points if x.clutch_stats else 0,
            )
            cs = best_clutch.clutch_stats
            if cs is not None:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIMING,
                    feedback_type=FeedbackType.TIP,
                    priority=FeedbackPriority.CRITICAL,
                    title="클러치 타임 핵심 선수 활용 전략",
                    description=(
                        f"클러치 최다 득점 선수 #{best_clutch.player_tracking_id}: "
                        f"{cs.points}점, FG% {cs.fg_pct * 100:.0f}%, "
                        f"FT% {cs.ft_pct * 100:.0f}%, +/- {cs.plus_minus:+d}. "
                        "클러치 타임에는 이 선수를 중심으로 공격을 전개하세요. "
                        "파울을 유도하는 드라이브, 자유투 획득, "
                        "오픈 미드레인지 점프슛 등 신뢰할 수 있는 옵션을 활용하세요. "
                        "상대도 이 선수를 집중 마크할 것이므로 "
                        "더블팀 시 킥아웃 패스 루트를 사전에 설정하세요."
                    ),
                    suggestion=(
                        f"클러치 세트 플레이: "
                        f"#{best_clutch.player_tracking_id} 아이솔레이션 + "
                        "킥아웃 슈터 3인 배치 + 오펜시브 리바운드 1인 전담"
                    ),
                    confidence=0.88,
                ))

        # 클러치 파울 관리
        home_fouls = (
            game_stats.home_team_stats.personal_fouls
            if game_stats.home_team_stats is not None else 0
        )
        if home_fouls >= 15:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.CRITICAL,
                title="클러치 타임 파울 관리 주의",
                description=(
                    f"홈팀 누적 파울 {home_fouls}개. "
                    "파울 위기 상황에서 수비 시 무리한 접촉을 피하세요. "
                    "클러치 타임 파울 아웃 위험 선수는 교체를 검토하고 "
                    "상대 자유투 상황을 최소화하는 전략적 수비를 유지하세요."
                ),
                current_value=float(home_fouls),
                confidence=0.90,
            ))

        return items

    # -------------------------------------------------------------------------
    # 9. 전환 공격 활용 전략
    # -------------------------------------------------------------------------
    def _analyze_transition_strategy(
        self,
        analysis: TacticalAnalysisResult,
        cfg: StrategicRecommendationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """전환 공격 활용 전략 권고."""
        items: list[FeedbackItem] = []
        trans = analysis.transitions
        if trans is None:
            return items

        if trans.first_wave_success_rate > 0 or trans.second_wave_success_rate > 0:
            first_good = trans.first_wave_success_rate >= 0.65
            second_good = trans.second_wave_success_rate >= 0.45
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=(
                    FeedbackType.POSITIVE if first_good and second_good
                    else FeedbackType.CORRECTION
                ),
                priority=FeedbackPriority.MEDIUM,
                title="속공 1차/2차 파동 활용 전략",
                description=(
                    f"1차 속공 성공률 {trans.first_wave_success_rate * 100:.0f}%, "
                    f"2차 속공 성공률 {trans.second_wave_success_rate * 100:.0f}%. "
                    + (
                        "1, 2차 속공 모두 효율적입니다. "
                        "수비 리바운드 이후 즉각 속공을 시도하고 "
                        "1차 파동 저지 시 2차 파동으로 전환하는 패턴을 훈련하세요."
                        if first_good and second_good
                        else
                        "속공 마무리 효율 개선이 필요합니다. "
                        "수적 우위 상황에서의 결정 속도와 마무리 선택지 훈련이 중요합니다. "
                        "1차 파동 실패 시 즉시 하프코트 공격으로 전환하는 판단력을 강화하세요."
                    )
                ),
                confidence=0.87,
            ))

        return items

    # -------------------------------------------------------------------------
    # 10. 세트 플레이 개선 권고
    # -------------------------------------------------------------------------
    def _analyze_set_play_recommendation(
        self,
        analysis: TacticalAnalysisResult,
        cfg: StrategicRecommendationFeedbackConfig,
    ) -> list[FeedbackItem]:
        """세트 플레이 개선 권고."""
        items: list[FeedbackItem] = []
        sp = analysis.set_plays
        if sp is None or sp.total_set_plays == 0:
            return items

        set_play_ppp = sp.set_play_ppp
        is_good = set_play_ppp >= 0.95
        top_plays = sp.top_plays[:3]

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if is_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.HIGH if not is_good else FeedbackPriority.LOW,
            title="세트 플레이 전략 권고",
            description=(
                f"세트 플레이 {sp.total_set_plays}회 실행, PPP {set_play_ppp:.2f}. "
                + (f"주력 플레이: {', '.join(top_plays)}. " if top_plays else "")
                + (
                    "세트 플레이가 효율적으로 운용되고 있습니다. "
                    "상대 수비 패턴에 따라 1~2개의 대안 세트 플레이를 추가로 준비하세요."
                    if is_good
                    else
                    "세트 플레이 효율 개선이 필요합니다. "
                    "상대 수비가 주요 플레이를 파악하고 있을 가능성이 있습니다. "
                    "플레이 다양화와 타이밍 변화로 상대 수비 예측을 교란하세요. "
                    "세트 플레이 마무리 역할자의 포지셔닝을 재점검하세요."
                )
            ),
            current_value=set_play_ppp,
            ideal_value=0.95,
            unit="PPP",
            confidence=0.87,
        ))

        # 세트 플레이 감지된 플레이별 성공률 분석
        for detected in sorted(
            sp.detected_plays,
            key=lambda d: d.success_rate,
            reverse=True,
        )[:2]:
            if detected.count > 0:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=(
                        FeedbackType.POSITIVE if detected.success_rate >= 0.55
                        else FeedbackType.CORRECTION
                    ),
                    priority=FeedbackPriority.LOW,
                    title=f"세트 플레이 '{detected.play_name}' 분석",
                    description=(
                        f"'{detected.play_name}': "
                        f"{detected.count}회 실행, "
                        f"성공률 {detected.success_rate * 100:.0f}%. "
                        + (
                            "성공률이 높은 핵심 세트 플레이입니다. "
                            "결정적인 포제션에서 우선적으로 활용하세요."
                            if detected.success_rate >= 0.55
                            else
                            "성공률이 낮습니다. "
                            "실행 타이밍, 스크린 각도, 마무리 동선을 재점검하거나 "
                            "유사하지만 변형된 플레이로 대체를 검토하세요."
                        )
                    ),
                    current_value=detected.success_rate * 100,
                    ideal_value=55.0,
                    unit="percent",
                    confidence=0.83,
                ))

        return items

    # -------------------------------------------------------------------------
    # 내부 유틸리티: 수비 스킴 조정 권고
    # -------------------------------------------------------------------------
    @staticmethod
    def _get_defensive_scheme_adjustment(
        scheme: DefenseScheme,
        drtg: float,
    ) -> str:
        """수비 스킴별 조정 권고 문구."""
        adjustments: dict[str, str] = {
            "man_to_man": (
                "맨투맨 수비에서 실점이 많습니다. "
                "스크린 대응 능력이 부족하다면 존 수비 전환을 검토하거나 "
                "스위치 적용 범위를 확대하세요."
            ),
            "zone_2_3": (
                "2-3존이 효율적으로 작동하지 않고 있습니다. "
                "상대가 하이포스트와 코너를 지속적으로 공략 중입니다. "
                "1-3-1 또는 맨투맨으로 전환하여 상대의 리듬을 끊으세요."
            ),
            "zone_3_2": (
                "3-2존이 공략당하고 있습니다. "
                "베이스라인과 로포스트 구역을 집중 보강하거나 "
                "맨투맨으로 전환하여 개별 마크를 강화하세요."
            ),
            "zone_1_3_1": (
                "1-3-1존이 효율을 발휘하지 못하고 있습니다. "
                "코너와 베이스라인 커버리지를 강화하거나 "
                "다른 존 또는 맨투맨으로 전환을 검토하세요."
            ),
            "full_court_press": (
                "풀코트 프레스가 상대에게 돌파당하고 있습니다. "
                "하프코트 수비로 전환하여 체력 소모를 줄이고 "
                "조직적인 하프코트 수비에 집중하세요."
            ),
            "half_court_press": (
                "하프코트 프레스 효율이 낮습니다. "
                "프레스 포지셔닝을 재조정하거나 일반 하프코트 수비로 전환하세요."
            ),
            "matchup_zone": (
                "매치업존이 혼선을 빚고 있습니다. "
                "매치업 전환 기준을 재설정하거나 맨투맨으로 단순화하세요."
            ),
            "box_and_one": (
                "박스 앤 원이 효율적이지 않습니다. "
                "마크된 선수가 다른 선수들을 활용하여 득점 중일 수 있습니다. "
                "전체 맨투맨 또는 존 수비로 전환을 검토하세요."
            ),
            "triangle_and_two": (
                "트라이앵글 앤 투의 커버리지에 공백이 생기고 있습니다. "
                "트라이앵글 수비수의 로테이션을 강화하거나 맨투맨으로 전환하세요."
            ),
        }
        return adjustments.get(
            scheme.value,
            f"현재 수비 스킴({scheme.value})의 취약점을 분석하고 "
            "상대 강점을 차단할 수 있는 조정을 가하세요."
        )

    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return (
            f"StrategicRecommendationFeedbackGenerator("
            f"generated={self._total_generated})"
        )


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "StrategicRecommendationFeedbackGenerator",
    "StrategicRecommendationFeedbackConfig",
]

__version__ = "1.0.0"
