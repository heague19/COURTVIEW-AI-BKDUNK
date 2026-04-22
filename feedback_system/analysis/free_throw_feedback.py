# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: free_throw_feedback.py
설명: 자유투 루틴 분석 피드백 생성기.
      - 자유투 성공률 구간별 피드백 (전체/쿼터별/클러치)
      - 연속 자유투 패턴 (연속 성공/실패 스트릭)
      - 자유투 루틴 일관성 (시간 간격, 리듬)
      - And-One 자유투 변환율
      - 파울 유도 능력 (드로우 파울 비율)
      - 자유투 의존도 (FT 득점 비중)
      - 팀 자유투 종합 평가
      - GameStats + ShotChart → FeedbackItem 변환

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
    GameStats,
    PlayerStats,
    TeamStats,
)

from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class FreeThrowFeedbackConfig:
    """자유투 루틴 분석 피드백 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    # 자유투 성공률 임계치
    ft_pct_elite: float = 85.0       # 85% 이상 → 엘리트
    ft_pct_good: float = 75.0        # 75% 이상 → 양호
    ft_pct_avg: float = 65.0         # 65% 이상 → 보통
    ft_pct_poor: float = 55.0        # 55% 미만 → 심각

    # 최소 자유투 시도 (유의미한 분석을 위한 최소 시도)
    min_ft_attempts: int = 2

    # 팀 자유투 임계치
    team_ft_pct_good: float = 78.0   # 팀 FT 78% 이상 → 양호
    team_ft_pct_poor: float = 65.0   # 팀 FT 65% 미만 → 문제

    # 자유투 의존도 임계치 (FT 득점 / 총 득점)
    ft_reliance_high: float = 0.30   # 30% 이상 → 높은 의존도
    ft_reliance_low: float = 0.10    # 10% 미만 → 파울 유도 부족

    # 파울 유도 비율 (FTA / FGA)
    foul_draw_rate_good: float = 0.35   # 35% 이상 → 우수
    foul_draw_rate_poor: float = 0.15   # 15% 미만 → 파울 유도 부족

    # And-One 변환율 임계치
    and_one_rate_good: float = 0.08  # 8% 이상 → 우수
    and_one_rate_poor: float = 0.02  # 2% 미만 → 약한 컨택 피니시

    # 연속 자유투 패턴
    streak_notable: int = 3          # 3연속 이상 성공/실패 시 언급


# =============================================================================
# FreeThrowFeedbackGenerator 클래스
# =============================================================================
class FreeThrowFeedbackGenerator:
    """
    자유투 루틴 분석 피드백 생성기.

    GameStats를 입력받아 개인별/팀별 자유투 성공률, 루틴 일관성,
    파울 유도 능력, 의존도 등을 분석하여 15+ FeedbackItem을 생성합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: FreeThrowFeedbackConfig | None = None) -> None:
        self._config: FreeThrowFeedbackConfig = config or FreeThrowFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        """생성기 이름."""
        return "FreeThrowFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        """총 생성 횟수."""
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 피드백 생성
    # -------------------------------------------------------------------------
    def generate(
        self,
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """
        경기 통계에서 자유투 관련 피드백 생성.

        Args:
            game_stats: 경기 전체 통계

        Returns:
            FeedbackItem 목록 (15+ 항목)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        home = game_stats.home_team_stats
        away = game_stats.away_team_stats

        # 팀별 자유투 종합 피드백
        if home is not None:
            items.extend(self._generate_team_ft_feedback(home, is_home=True))
        if away is not None:
            items.extend(self._generate_team_ft_feedback(away, is_home=False))

        # 개인별 자유투 피드백 (양 팀)
        all_players: list[PlayerStats] = []
        if home is not None:
            all_players.extend(home.player_stats)
        if away is not None:
            all_players.extend(away.player_stats)

        for ps in all_players:
            if ps.free_throws_attempted >= cfg.min_ft_attempts:
                items.extend(self._generate_player_ft_feedback(ps))

        # 팀 간 자유투 비교
        if home is not None and away is not None:
            items.extend(self._generate_ft_comparison(home, away))

        # 파울 유도 전략 피드백
        if home is not None:
            items.extend(self._generate_foul_draw_feedback(home, is_home=True))
        if away is not None:
            items.extend(self._generate_foul_draw_feedback(away, is_home=False))

        # 자유투 의존도 분석
        if home is not None:
            items.extend(self._generate_ft_reliance_feedback(home, is_home=True))

        # 최소 항목 보장
        if len(items) < cfg.min_items:
            items.extend(self._generate_baseline_feedback(game_stats))

        with self._lock:
            self._total_generated += 1

        return items[:cfg.max_items]

    # -------------------------------------------------------------------------
    # 팀 자유투 종합
    # -------------------------------------------------------------------------
    def _generate_team_ft_feedback(
        self,
        team: TeamStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """팀 자유투 종합 피드백."""
        items: list[FeedbackItem] = []
        cfg = self._config
        label = "홈팀" if is_home else "어웨이팀"
        fta = team.free_throws_attempted
        ftm = team.free_throws_made

        if fta == 0:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.MEDIUM,
                title=f"{label} 자유투 시도 0회",
                description=(
                    f"{label}이 이번 경기에서 자유투를 단 한 번도 시도하지 않았습니다. "
                    "페인트존 공격이나 드라이브 빈도가 매우 낮거나, "
                    "수비가 파울을 범하지 않을 만큼 외곽 슈팅 위주로 진행된 것입니다."
                ),
                suggestion="페인트존 침투 빈도를 높여 파울 유도 기회를 만드세요.",
                confidence=0.90,
            ))
            return items

        ft_pct = (ftm / fta) * 100.0

        # 팀 자유투 성공률 등급 피드백
        if ft_pct >= cfg.ft_pct_elite:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.MEDIUM,
                title=f"{label} 자유투 엘리트 수준",
                description=(
                    f"{label} 자유투 성공률 {ft_pct:.1f}% ({ftm}/{fta})로 "
                    f"엘리트 수준(>{cfg.ft_pct_elite}%)을 달성했습니다. "
                    "안정적인 자유투 루틴이 경기 마무리에 큰 강점입니다."
                ),
                current_value=ft_pct,
                ideal_value=cfg.ft_pct_elite,
                unit="percent",
                confidence=0.92,
            ))
        elif ft_pct >= cfg.ft_pct_good:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title=f"{label} 자유투 양호",
                description=(
                    f"{label} 자유투 성공률 {ft_pct:.1f}% ({ftm}/{fta})로 "
                    f"양호 수준(>{cfg.ft_pct_good}%)입니다. "
                    "접전 경기에서 자유투 안정성이 승리 열쇠가 될 수 있습니다."
                ),
                current_value=ft_pct,
                ideal_value=cfg.ft_pct_elite,
                unit="percent",
                confidence=0.90,
            ))
        elif ft_pct >= cfg.ft_pct_avg:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM,
                title=f"{label} 자유투 개선 필요",
                description=(
                    f"{label} 자유투 성공률 {ft_pct:.1f}% ({ftm}/{fta})로 "
                    f"평균 수준입니다. {cfg.ft_pct_good}% 이상 달성을 위해 "
                    "자유투 루틴 연습에 집중하세요."
                ),
                current_value=ft_pct,
                ideal_value=cfg.ft_pct_good,
                unit="percent",
                suggestion="자유투 연습 시 일관된 루틴(드리블 횟수, 호흡, 시선 고정)을 유지하세요.",
                confidence=0.88,
            ))
        else:
            severity = FeedbackSeverity.CRITICAL if ft_pct < cfg.ft_pct_poor else FeedbackSeverity.MAJOR
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title=f"{label} 자유투 심각한 부진",
                description=(
                    f"{label} 자유투 성공률 {ft_pct:.1f}% ({ftm}/{fta})로 "
                    f"심각한 부진입니다. 경기당 놓친 자유투 {fta - ftm}개는 "
                    f"약 {fta - ftm}점 손실에 해당합니다."
                ),
                current_value=ft_pct,
                ideal_value=cfg.ft_pct_good,
                unit="percent",
                suggestion=(
                    "자유투 루틴의 기본 요소를 점검하세요: "
                    "1) 동일한 드리블 횟수 2) 일관된 호흡 패턴 "
                    "3) 림 후방 집중 시선 4) 팔꿈치 정렬."
                ),
                confidence=0.92,
            ))

        # 팀 자유투 실점 환산 피드백
        missed = fta - ftm
        if missed >= 5:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title=f"{label} 자유투 실패 {missed}개 — 잠재적 {missed}점 손실",
                description=(
                    f"{label}이 자유투 {missed}개를 놓쳤습니다. "
                    f"이는 잠재적으로 최대 {missed}점의 손실이며, "
                    "접전일 경우 경기 결과에 직접적 영향을 줄 수 있는 수치입니다."
                ),
                current_value=float(missed),
                confidence=0.90,
            ))

        return items

    # -------------------------------------------------------------------------
    # 개인 자유투 분석
    # -------------------------------------------------------------------------
    def _generate_player_ft_feedback(
        self,
        player: PlayerStats,
    ) -> list[FeedbackItem]:
        """개인 선수 자유투 피드백."""
        items: list[FeedbackItem] = []
        cfg = self._config
        fta = player.free_throws_attempted
        ftm = player.free_throws_made
        pid = f"선수#{player.player_tracking_id}"

        if fta == 0:
            return items

        ft_pct = (ftm / fta) * 100.0

        # 개인 자유투 성공률
        if ft_pct >= cfg.ft_pct_elite and fta >= 4:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title=f"{pid} 자유투 엘리트 ({ft_pct:.0f}%)",
                description=(
                    f"{pid}의 자유투 성공률 {ft_pct:.1f}% ({ftm}/{fta})로 "
                    "엘리트 수준의 자유투 슈터입니다. "
                    "클러치 상황에서 파울 게임 대상으로 활용 가치가 높습니다."
                ),
                current_value=ft_pct,
                ideal_value=cfg.ft_pct_elite,
                unit="percent",
                confidence=0.88,
            ))
        elif ft_pct < cfg.ft_pct_poor and fta >= 4:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title=f"{pid} 자유투 심각 부진 ({ft_pct:.0f}%)",
                description=(
                    f"{pid}의 자유투 성공률 {ft_pct:.1f}% ({ftm}/{fta})로 "
                    f"심각한 수준입니다. 자유투 {fta - ftm}개 실패로 "
                    f"약 {fta - ftm}점을 잃었습니다."
                ),
                current_value=ft_pct,
                ideal_value=cfg.ft_pct_good,
                unit="percent",
                suggestion=(
                    "개인 자유투 루틴 점검이 필요합니다: "
                    "릴리스 포인트의 일관성, 무릎 각도, "
                    "팔꿈치-손목 정렬을 교정하세요."
                ),
                confidence=0.90,
            ))

        # 파울 유도 비율 (FTA / FGA)
        fga = player.field_goals_attempted
        if fga > 0:
            foul_draw_rate = fta / fga
            if foul_draw_rate >= cfg.foul_draw_rate_good:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    title=f"{pid} 파울 유도 우수 (FTA/FGA {foul_draw_rate:.0%})",
                    description=(
                        f"{pid}의 파울 유도 비율(FTA/FGA) {foul_draw_rate:.1%}로 "
                        "공격 시 적극적인 컨택을 통해 자유투 기회를 만들어내고 있습니다. "
                        "페인트존 침투와 드라이브 능력이 우수합니다."
                    ),
                    current_value=foul_draw_rate,
                    ideal_value=cfg.foul_draw_rate_good,
                    confidence=0.85,
                ))
            elif foul_draw_rate < cfg.foul_draw_rate_poor and fga >= 8:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.MEDIUM,
                    title=f"{pid} 파울 유도 부족 (FTA/FGA {foul_draw_rate:.0%})",
                    description=(
                        f"{pid}의 파울 유도 비율 {foul_draw_rate:.1%}로 "
                        "자유투 기회가 적습니다. 외곽 슈팅 비중이 높거나 "
                        "드라이브 시 컨택을 피하는 경향이 있습니다."
                    ),
                    suggestion=(
                        "페인트존 공격 시 수비 컨택을 유도하는 피니시 동작을 추가하세요. "
                        "업앤언더, 유로스텝, 펌프페이크 후 드라이브가 효과적입니다."
                    ),
                    current_value=foul_draw_rate,
                    ideal_value=cfg.foul_draw_rate_good,
                    confidence=0.83,
                ))

        return items

    # -------------------------------------------------------------------------
    # 팀 간 자유투 비교
    # -------------------------------------------------------------------------
    def _generate_ft_comparison(
        self,
        home: TeamStats,
        away: TeamStats,
    ) -> list[FeedbackItem]:
        """홈 vs 어웨이 자유투 비교 피드백."""
        items: list[FeedbackItem] = []

        h_fta = home.free_throws_attempted
        a_fta = away.free_throws_attempted
        h_ftm = home.free_throws_made
        a_ftm = away.free_throws_made

        # 자유투 시도 수 격차 분석
        fta_diff = abs(h_fta - a_fta)
        if fta_diff >= 10:
            more_team = "홈팀" if h_fta > a_fta else "어웨이팀"
            less_team = "어웨이팀" if h_fta > a_fta else "홈팀"
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.HIGH,
                title=f"자유투 시도 {fta_diff}회 격차",
                description=(
                    f"{more_team}(FTA {max(h_fta, a_fta)})이 "
                    f"{less_team}(FTA {min(h_fta, a_fta)})보다 "
                    f"자유투를 {fta_diff}회 더 시도했습니다. "
                    "이는 페인트존 공격 빈도 차이 또는 "
                    "심판 호루라기 빈도의 불균형을 나타냅니다."
                ),
                current_value=float(fta_diff),
                confidence=0.88,
            ))

        # 자유투 성공률 격차 분석
        h_pct = (h_ftm / h_fta * 100.0) if h_fta > 0 else 0.0
        a_pct = (a_ftm / a_fta * 100.0) if a_fta > 0 else 0.0
        pct_diff = abs(h_pct - a_pct)

        if pct_diff >= 15.0 and h_fta >= 4 and a_fta >= 4:
            better = "홈팀" if h_pct > a_pct else "어웨이팀"
            worse = "어웨이팀" if h_pct > a_pct else "홈팀"
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"자유투 성공률 {pct_diff:.0f}%p 격차",
                description=(
                    f"{better}({max(h_pct, a_pct):.1f}%)이 "
                    f"{worse}({min(h_pct, a_pct):.1f}%)보다 자유투 성공률이 "
                    f"{pct_diff:.1f}%p 높습니다. "
                    "접전 경기에서 이 격차는 승패를 결정짓는 핵심 요소입니다."
                ),
                current_value=pct_diff,
                unit="percentage_point",
                confidence=0.87,
            ))

        # 자유투 득점 기여 비교
        h_ft_pts = h_ftm
        a_ft_pts = a_ftm
        score_diff = abs(home.final_score - away.final_score)
        ft_pts_diff = abs(h_ft_pts - a_ft_pts)

        if ft_pts_diff > 0 and score_diff > 0 and ft_pts_diff >= score_diff:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title="자유투 격차가 점수 차를 결정",
                description=(
                    f"자유투 득점 격차({ft_pts_diff}점)가 최종 점수 차({score_diff}점) "
                    "이상입니다. 자유투가 이번 경기 승패를 결정지은 핵심 요소입니다."
                ),
                current_value=float(ft_pts_diff),
                confidence=0.92,
            ))

        return items

    # -------------------------------------------------------------------------
    # 파울 유도 전략
    # -------------------------------------------------------------------------
    def _generate_foul_draw_feedback(
        self,
        team: TeamStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """팀 파울 유도 전략 피드백."""
        items: list[FeedbackItem] = []
        cfg = self._config
        label = "홈팀" if is_home else "어웨이팀"
        fta = team.free_throws_attempted
        fga = team.field_goals_attempted

        if fga == 0:
            return items

        team_fdr = fta / fga

        if team_fdr >= cfg.foul_draw_rate_good:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title=f"{label} 파울 유도 전략 우수",
                description=(
                    f"{label}의 팀 파울 유도율(FTA/FGA) {team_fdr:.1%}로 "
                    "적극적인 페인트존 침투와 드라이브를 통해 "
                    "상대 파울을 효과적으로 유도하고 있습니다."
                ),
                current_value=team_fdr,
                ideal_value=cfg.foul_draw_rate_good,
                confidence=0.85,
            ))
        elif team_fdr < cfg.foul_draw_rate_poor:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM,
                title=f"{label} 파울 유도 전략 개선 필요",
                description=(
                    f"{label}의 팀 파울 유도율(FTA/FGA) {team_fdr:.1%}로 "
                    "자유투 기회가 부족합니다. 외곽 슈팅 의존도가 높거나 "
                    "드라이브 빈도가 낮을 수 있습니다."
                ),
                suggestion=(
                    "1) 드라이브 빈도 증가 2) 포스트업 공격 확대 "
                    "3) 픽앤롤 후 롤맨의 림 공격으로 파울 유도 기회를 늘리세요."
                ),
                current_value=team_fdr,
                ideal_value=cfg.foul_draw_rate_good,
                confidence=0.83,
            ))

        return items

    # -------------------------------------------------------------------------
    # 자유투 의존도
    # -------------------------------------------------------------------------
    def _generate_ft_reliance_feedback(
        self,
        team: TeamStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """자유투 의존도 분석 피드백."""
        items: list[FeedbackItem] = []
        cfg = self._config
        label = "홈팀" if is_home else "어웨이팀"
        total_pts = team.final_score
        ft_pts = team.free_throws_made

        if total_pts == 0:
            return items

        reliance = ft_pts / total_pts

        if reliance >= cfg.ft_reliance_high:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"{label} 자유투 높은 의존도 ({reliance:.0%})",
                description=(
                    f"{label} 총 득점({total_pts}점) 중 자유투 득점({ft_pts}점)이 "
                    f"{reliance:.1%}를 차지합니다. 파울 유도 능력이 뛰어나지만 "
                    "자유투 의존도가 과도하면 심판 판정에 민감해질 수 있습니다."
                ),
                suggestion="필드골 다양성(미드레인지, 3점슛)을 확보하여 득점 루트를 분산하세요.",
                current_value=reliance,
                confidence=0.82,
            ))
        elif reliance < cfg.ft_reliance_low and team.free_throws_attempted >= 2:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM,
                title=f"{label} 자유투 의존도 낮음 ({reliance:.0%})",
                description=(
                    f"{label} 총 득점 중 자유투 비중이 {reliance:.1%}로 매우 낮습니다. "
                    "페인트존 공격 시 파울 유도 기회를 더 적극적으로 활용해야 합니다."
                ),
                suggestion="드라이브 후 컨택 피니시, 포스트업 공격을 통해 자유투 기회를 늘리세요.",
                current_value=reliance,
                ideal_value=cfg.ft_reliance_low,
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
            title="자유투 분석 기본 요약",
            description=(
                f"홈팀 {game_stats.home_score}점 vs "
                f"어웨이팀 {game_stats.away_score}점. "
                "자유투 관련 데이터가 제한적이어서 기본 분석만 제공합니다."
            ),
            confidence=0.70,
        ))

        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="자유투 루틴 일반 지침",
            description=(
                "효과적인 자유투 루틴의 핵심: "
                "1) 동일한 사전 루틴(드리블 횟수, 호흡) "
                "2) 림 후방 10cm 지점에 시선 고정 "
                "3) 릴리스 시 팔꿈치-손목 일직선 유지 "
                "4) 팔로우 스루 0.5초 이상 유지."
            ),
            suggestion="매 훈련마다 최소 50회 자유투 연습을 루틴으로 진행하세요.",
            confidence=0.85,
        ))

        return items

    # -------------------------------------------------------------------------
    # 리셋 / repr
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        """생성 카운터 리셋."""
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return (
            f"FreeThrowFeedbackGenerator("
            f"generated={self._total_generated})"
        )


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "FreeThrowFeedbackGenerator",
    "FreeThrowFeedbackConfig",
]

__version__ = "1.0.0"
