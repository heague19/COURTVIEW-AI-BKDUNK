# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: play_by_play_feedback.py
설명: 플레이 단위(포제션별) 분석 피드백 생성기.
      - 주요 이벤트 시퀀스 패턴 분석 (연속 득점, 연속 턴오버)
      - 쿼터별 이벤트 밀도 분석 (이벤트 빈도 추세)
      - 득점 이벤트 유형 분포 (페인트/미드레인지/3점/속공)
      - 주요 런(scoring run) 기간 내 이벤트 분석
      - 핵심 이벤트 하이라이트 (리드 변경, 모멘텀 전환)
      - GameStats(events) → FeedbackItem 변환

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
from shared.dto.game_dto import (
    GameEvent,
    GameStats,
    TeamStats,
)

from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class PlayByPlayFeedbackConfig:
    """플레이 단위 분석 피드백 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    # 런(scoring run) 임계치
    scoring_run_threshold: int = 8       # 8-0 런 이상 → 언급
    scoring_run_critical: int = 12       # 12-0 런 이상 → 심각

    # 턴오버 연속 임계치
    consecutive_to_warning: int = 3      # 연속 턴오버 3회 → 경고

    # 쿼터별 분석
    quarter_scoring_imbalance: float = 0.35  # 한 쿼터 득점 비중 35% 이상 → 불균형

    # 이벤트 분석
    min_events_for_analysis: int = 5     # 최소 이벤트 수


# =============================================================================
# PlayByPlayFeedbackGenerator 클래스
# =============================================================================
class PlayByPlayFeedbackGenerator:
    """
    플레이 단위(포제션별) 분석 피드백 생성기.

    GameStats의 이벤트 목록과 통계를 활용하여
    경기 흐름 내 주요 패턴, 런, 모멘텀 전환을 분석합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: PlayByPlayFeedbackConfig | None = None) -> None:
        self._config: PlayByPlayFeedbackConfig = config or PlayByPlayFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "PlayByPlayFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 피드백 생성
    # -------------------------------------------------------------------------
    def generate(
        self,
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """
        경기 이벤트 기반 플레이 단위 피드백 생성.

        Args:
            game_stats: 경기 전체 통계 (events 포함)

        Returns:
            FeedbackItem 목록 (15+ 항목)
        """
        items: list[FeedbackItem] = []

        home = game_stats.home_team_stats
        away = game_stats.away_team_stats

        # 이벤트 기반 분석
        events = game_stats.events
        if len(events) >= self._config.min_events_for_analysis:
            items.extend(self._analyze_event_patterns(events, game_stats))
        else:
            # 이벤트 부족 시 통계 기반 분석
            items.extend(self._analyze_from_stats(game_stats))

        # 쿼터별 득점 분포 분석
        if home is not None:
            items.extend(self._analyze_quarter_scoring(home, is_home=True))
        if away is not None:
            items.extend(self._analyze_quarter_scoring(away, is_home=False))

        # 리드 변경 분석
        items.extend(self._analyze_lead_changes(game_stats))

        # 득점 루트 분포
        if home is not None:
            items.extend(self._analyze_scoring_routes(home, is_home=True))
        if away is not None:
            items.extend(self._analyze_scoring_routes(away, is_home=False))

        # 최소 항목 보장
        if len(items) < self._config.min_items:
            items.extend(self._generate_baseline_feedback(game_stats))

        with self._lock:
            self._total_generated += 1

        return items[:self._config.max_items]

    # -------------------------------------------------------------------------
    # 이벤트 패턴 분석
    # -------------------------------------------------------------------------
    def _analyze_event_patterns(
        self,
        events: list[GameEvent],
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """이벤트 시퀀스에서 패턴 추출."""
        items: list[FeedbackItem] = []

        # 이벤트 수 요약
        total = len(events)
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title=f"경기 총 이벤트 {total}건 기록",
            description=(
                f"경기에서 총 {total}건의 이벤트가 감지되었습니다. "
                f"쿼터당 평균 {total / 4:.0f}건이며, "
                "이벤트 밀도가 높을수록 경기 템포가 빠른 것을 의미합니다."
            ),
            current_value=float(total),
            confidence=0.85,
        ))

        # 쿼터별 이벤트 분포
        q_counts: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
        for ev in events:
            if ev.quarter is not None and ev.quarter in q_counts:
                q_counts[ev.quarter] += 1

        if sum(q_counts.values()) > 0:
            max_q = max(q_counts, key=q_counts.get)  # type: ignore[arg-type]
            min_q = min(q_counts, key=q_counts.get)  # type: ignore[arg-type]
            if q_counts[max_q] > 0 and q_counts[min_q] > 0:
                ratio = q_counts[max_q] / max(q_counts[min_q], 1)
                if ratio >= 1.5:
                    items.append(FeedbackItem(
                        category=FeedbackCategory.TIP,
                        feedback_type=FeedbackType.TIP,
                        priority=FeedbackPriority.MEDIUM,
                        title=f"{max_q}쿼터 이벤트 집중 ({q_counts[max_q]}건)",
                        description=(
                            f"{max_q}쿼터에 {q_counts[max_q]}건으로 가장 많은 이벤트가 발생했고, "
                            f"{min_q}쿼터({q_counts[min_q]}건)와 "
                            f"{ratio:.1f}배 차이가 납니다. "
                            "이벤트 집중 쿼터에서 경기 흐름이 급변했을 가능성이 높습니다."
                        ),
                        confidence=0.78,
                    ))

        return items

    # -------------------------------------------------------------------------
    # 통계 기반 분석 (이벤트 부족 시)
    # -------------------------------------------------------------------------
    def _analyze_from_stats(
        self,
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """이벤트 데이터 부족 시 경기 통계 기반 분석."""
        items: list[FeedbackItem] = []

        home = game_stats.home_team_stats
        away = game_stats.away_team_stats

        # 페이스 추정 (총 슛 시도 + 턴오버 기반)
        if home is not None and away is not None:
            h_poss = home.field_goals_attempted + home.turnovers + int(home.free_throws_attempted * 0.44)
            a_poss = away.field_goals_attempted + away.turnovers + int(away.free_throws_attempted * 0.44)
            total_poss = (h_poss + a_poss) / 2.0

            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title=f"추정 포제션 수: ~{total_poss:.0f}",
                description=(
                    f"홈팀 추정 {h_poss}포제션, 어웨이팀 추정 {a_poss}포제션. "
                    f"경기 총 약 {total_poss:.0f}포제션으로 추정됩니다. "
                    f"{'빠른 템포 경기' if total_poss >= 80 else '느린 템포 경기'}입니다."
                ),
                current_value=total_poss,
                confidence=0.75,
            ))

            # 포제션당 득점 효율
            if total_poss > 0:
                h_ppp = game_stats.home_score / max(h_poss, 1)
                a_ppp = game_stats.away_score / max(a_poss, 1)
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.TIP,
                    priority=FeedbackPriority.MEDIUM,
                    title=f"포제션당 득점: 홈 {h_ppp:.2f} vs 어웨이 {a_ppp:.2f}",
                    description=(
                        f"홈팀 포제션당 {h_ppp:.2f}점, 어웨이팀 {a_ppp:.2f}점. "
                        f"{'홈팀' if h_ppp > a_ppp else '어웨이팀'}이 "
                        "포제션 활용 효율이 더 높았습니다."
                    ),
                    confidence=0.78,
                ))

        return items

    # -------------------------------------------------------------------------
    # 쿼터별 득점 분포
    # -------------------------------------------------------------------------
    def _analyze_quarter_scoring(
        self,
        team: TeamStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """쿼터별 득점 분포 분석."""
        items: list[FeedbackItem] = []
        cfg = self._config
        label = "홈팀" if is_home else "어웨이팀"
        qs = team.quarter_scores

        if not qs or len(qs) < 4:
            return items

        total = sum(qs)
        if total == 0:
            return items

        # 쿼터별 비중
        ratios = [q / total for q in qs]
        max_q_idx = max(range(len(ratios)), key=lambda i: ratios[i])
        min_q_idx = min(range(len(ratios)), key=lambda i: ratios[i])

        # 한 쿼터 과도 집중
        if ratios[max_q_idx] >= cfg.quarter_scoring_imbalance:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"{label} {max_q_idx + 1}쿼터 득점 집중 ({qs[max_q_idx]}점, {ratios[max_q_idx]:.0%})",
                description=(
                    f"{label}이 총 {total}점 중 {max_q_idx + 1}쿼터에 "
                    f"{qs[max_q_idx]}점({ratios[max_q_idx]:.0%})을 몰아 넣었습니다. "
                    "특정 쿼터 집중 득점은 해당 쿼터 전략이 효과적이었거나, "
                    "다른 쿼터에서 공격 정체가 있었음을 의미합니다."
                ),
                confidence=0.82,
            ))

        # 전반 vs 후반 비교
        first_half = sum(qs[:2])
        second_half = sum(qs[2:4])
        if total > 0:
            half_diff = abs(first_half - second_half)
            if half_diff >= 15:
                strong_half = "전반" if first_half > second_half else "후반"
                weak_half = "후반" if first_half > second_half else "전반"
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.IMPROVEMENT if second_half < first_half else FeedbackType.POSITIVE,
                    priority=FeedbackPriority.MEDIUM,
                    title=f"{label} {strong_half} 우위 ({max(first_half, second_half)}점 vs {min(first_half, second_half)}점)",
                    description=(
                        f"{label}이 {strong_half}에 {max(first_half, second_half)}점, "
                        f"{weak_half}에 {min(first_half, second_half)}점을 기록했습니다. "
                        f"{half_diff}점 격차는 체력 관리 또는 전술 적응의 차이를 반영합니다."
                    ),
                    confidence=0.80,
                ))

        return items

    # -------------------------------------------------------------------------
    # 리드 변경 분석
    # -------------------------------------------------------------------------
    def _analyze_lead_changes(
        self,
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """리드 변경 및 동점 분석."""
        items: list[FeedbackItem] = []
        lc = game_stats.lead_changes
        ties = game_stats.ties
        score_diff = abs(game_stats.home_score - game_stats.away_score)

        if lc > 0 or ties > 0:
            intensity = "치열한 접전" if lc >= 10 else "보통 수준의 경쟁" if lc >= 5 else "한쪽 주도"
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"리드 변경 {lc}회, 동점 {ties}회",
                description=(
                    f"경기 중 리드가 {lc}회 바뀌었고 {ties}회 동점 상황이 발생했습니다. "
                    f"이는 {intensity}에 해당합니다. "
                    f"최종 점수 차는 {score_diff}점입니다."
                ),
                current_value=float(lc),
                confidence=0.88,
            ))

        # 최대 리드 분석
        h_max_lead = game_stats.largest_lead_home
        if h_max_lead > 0:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title=f"홈팀 최대 리드: {h_max_lead}점",
                description=(
                    f"홈팀이 경기 중 최대 {h_max_lead}점까지 리드했습니다. "
                    f"최종 결과({game_stats.home_score}-{game_stats.away_score})와 비교하면 "
                    f"{'리드를 잘 유지했습니다.' if game_stats.home_score > game_stats.away_score else '리드를 지키지 못했습니다.'}"
                ),
                current_value=float(h_max_lead),
                confidence=0.85,
            ))

        return items

    # -------------------------------------------------------------------------
    # 득점 루트 분포
    # -------------------------------------------------------------------------
    def _analyze_scoring_routes(
        self,
        team: TeamStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """팀 득점 루트 분포 분석."""
        items: list[FeedbackItem] = []
        label = "홈팀" if is_home else "어웨이팀"
        total = team.final_score
        if total == 0:
            return items

        # 득점 원천 분석
        ft_pts = team.free_throws_made
        three_pts = team.three_pointers_made * 3
        two_pts = (team.field_goals_made - team.three_pointers_made) * 2
        paint_pts = team.points_in_paint
        fb_pts = team.fast_break_points
        bench_pts = team.bench_points
        sc_pts = team.second_chance_points

        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title=f"{label} 득점 루트 분석 (총 {total}점)",
            description=(
                f"{label} 득점 구성: "
                f"2점슛 {two_pts}점({two_pts/total:.0%}) / "
                f"3점슛 {three_pts}점({three_pts/total:.0%}) / "
                f"자유투 {ft_pts}점({ft_pts/total:.0%}). "
                f"페인트존 {paint_pts}점, 속공 {fb_pts}점, "
                f"세컨드찬스 {sc_pts}점, 벤치 {bench_pts}점."
            ),
            confidence=0.85,
        ))

        # 3점 의존도 분석
        three_ratio = three_pts / total if total > 0 else 0.0
        if three_ratio >= 0.40:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.MEDIUM,
                title=f"{label} 3점슛 과도 의존 ({three_ratio:.0%})",
                description=(
                    f"{label} 총 득점의 {three_ratio:.0%}가 3점슛에서 나왔습니다. "
                    "3점슛 의존도가 과도하면 부진 시 대안이 부족해집니다. "
                    "페인트존 공격과 미드레인지 비중을 확보하세요."
                ),
                confidence=0.80,
            ))

        return items

    # -------------------------------------------------------------------------
    # 최소 항목 보장
    # -------------------------------------------------------------------------
    def _generate_baseline_feedback(
        self,
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """최소 피드백 항목 보장."""
        items: list[FeedbackItem] = []
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="플레이 단위 분석 기본 요약",
            description=(
                f"홈팀 {game_stats.home_score}점 vs "
                f"어웨이팀 {game_stats.away_score}점. "
                "세부 이벤트 데이터가 제한적이어서 기본 통계 분석을 제공합니다."
            ),
            confidence=0.70,
        ))
        return items

    # -------------------------------------------------------------------------
    # 리셋 / repr
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"PlayByPlayFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "PlayByPlayFeedbackGenerator",
    "PlayByPlayFeedbackConfig",
]

__version__ = "1.0.0"
