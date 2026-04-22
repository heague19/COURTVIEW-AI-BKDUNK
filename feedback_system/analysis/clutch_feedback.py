# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: clutch_feedback.py
설명: 클러치 상황 피드백 생성기.
      - 개인별 클러치 성능 평가 (4쿼터 잔여 5분, 점수차 5점 이내)
      - 팀 클러치 종합 집계 (FG%, 턴오버, 플러스마이너스)
      - 클러치 FG% vs 정규 시간 비교
      - 클러치 상황 압박 하 턴오버 분석
      - list[IndividualAnalysis] → FeedbackItem 변환

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
from shared.dto.tactical_dto import (
    ClutchStats,
    IndividualAnalysis,
)

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ClutchFeedbackConfig:
    """클러치 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # 클러치 FG% 임계치
    clutch_fg_pct_threshold: float = 0.40    # FG 40% 이상 → 클러치 양호
    clutch_fg_pct_elite: float = 0.50        # FG 50% 이상 → 엘리트 클러치
    clutch_fg_pct_poor: float = 0.30         # FG 30% 미만 → 클러치 취약

    # 클러치 FT% 임계치
    clutch_ft_pct_good: float = 0.75         # FT 75% 이상 → 양호
    clutch_ft_pct_critical: float = 0.60     # FT 60% 미만 → 심각

    # 클러치 턴오버 임계치
    clutch_turnover_max: int = 2             # 2개 이하 → 안정
    clutch_turnover_critical: int = 4        # 4개 이상 → 심각

    # 클러치 +/- 임계치
    clutch_plus_minus_good: int = 3          # +3 이상 → 긍정 기여
    clutch_plus_minus_poor: int = -3         # -3 이하 → 부정 기여

    # 클러치 득점 임계치
    clutch_points_good: int = 4              # 4점 이상 → 클러치 득점 기여
    clutch_points_elite: int = 8             # 8점 이상 → 엘리트 클러치 득점

    # 팀 클러치 집계 기준
    team_clutch_fg_good: float = 0.42        # 팀 클러치 FG% 42% 이상 → 양호
    team_clutch_to_max: float = 3.0          # 팀 클러치 평균 턴오버 3.0 이하 → 양호


# =============================================================================
# ClutchFeedbackGenerator 클래스
# =============================================================================
class ClutchFeedbackGenerator:
    """
    클러치 상황 피드백 생성기.

    IndividualAnalysis 목록을 입력받아 클러치 FG%, 자유투, 턴오버,
    +/- 등을 기반으로 개인별 및 팀 단위 클러치 성능 피드백을 생성합니다.

    클러치 상황은 4쿼터 잔여 5분, 점수차 5점 이내로 정의됩니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: ClutchFeedbackConfig | None = None) -> None:
        self._config: ClutchFeedbackConfig = config or ClutchFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        """생성기 이름."""
        return "ClutchFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        """총 생성 횟수."""
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 피드백 생성
    # -------------------------------------------------------------------------
    def generate(
        self,
        analyses: list[IndividualAnalysis],
    ) -> list[FeedbackItem]:
        """
        개인 심층 분석 목록에서 클러치 피드백 생성.

        Args:
            analyses: 개인 분석 결과 목록 (ClutchStats 보유 선수만 처리)

        Returns:
            FeedbackItem 목록 (개인별 클러치 + 팀 클러치 종합)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        # 클러치 스탯 보유 선수 필터링
        clutch_players = [
            a for a in analyses if a.clutch_stats is not None
        ]

        if not clutch_players:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="클러치 상황 데이터 없음",
                description=(
                    "이번 경기에서 클러치 상황(4쿼터 잔여 5분, 점수차 5점 이내)이 "
                    "발생하지 않았거나 해당 데이터가 수집되지 않았습니다."
                ),
                confidence=0.80,
            ))
            return items

        # 개인별 클러치 피드백
        for analysis in clutch_players:
            items.extend(
                self._analyze_individual_clutch(analysis, cfg)
            )

        # 팀 클러치 종합 피드백
        items.extend(self._analyze_team_clutch(clutch_players, cfg))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 개인 클러치 분석
    # -------------------------------------------------------------------------
    def _analyze_individual_clutch(
        self,
        analysis: IndividualAnalysis,
        cfg: ClutchFeedbackConfig,
    ) -> list[FeedbackItem]:
        """개인 클러치 성능 피드백 생성."""
        items: list[FeedbackItem] = []
        pid = analysis.player_tracking_id
        clutch: ClutchStats = analysis.clutch_stats  # type: ignore[assignment]  # None 필터링 완료

        # 1. 클러치 득점
        pts_elite = clutch.points >= cfg.clutch_points_elite
        pts_good = clutch.points >= cfg.clutch_points_good
        sev_pts = self._severity_mapper.from_score(
            min(clutch.points / max(cfg.clutch_points_elite, 1) * 100.0, 100.0)
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=(
                FeedbackType.POSITIVE
                if pts_good
                else FeedbackType.IMPROVEMENT
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_pts.severity),
            title=f"#{pid} 클러치 득점",
            description=(
                f"클러치 상황 {clutch.points}득점. "
                + (
                    "클러치 상황에서 엘리트 수준의 득점 기여를 했습니다. "
                    "팀의 결정적 순간을 책임지는 선수입니다."
                    if pts_elite
                    else (
                        "클러치 상황에서 안정적인 득점 기여를 했습니다."
                        if pts_good
                        else "클러치 상황에서 득점 기여가 부족했습니다. "
                             "압박 상황에서의 슈팅 훈련이 필요합니다."
                    )
                )
            ),
            suggestion=(
                "클러치 상황 슈팅 기회 창출을 위한 오프볼 무브먼트를 강화하세요."
                if not pts_good
                else None
            ),
            current_value=float(clutch.points),
            ideal_value=float(cfg.clutch_points_good),
            unit="points",
            confidence=0.90,
        ))

        # 2. 클러치 FG%
        fg_elite = clutch.fg_pct >= cfg.clutch_fg_pct_elite
        fg_good = clutch.fg_pct >= cfg.clutch_fg_pct_threshold
        fg_poor = clutch.fg_pct < cfg.clutch_fg_pct_poor
        sev_fg = self._severity_mapper.from_ratio(clutch.fg_pct)
        items.append(FeedbackItem(
            category=FeedbackCategory.RELEASE,
            feedback_type=(
                FeedbackType.POSITIVE
                if fg_good
                else (FeedbackType.WARNING if fg_poor else FeedbackType.CORRECTION)
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_fg.severity),
            title=f"#{pid} 클러치 야투율",
            description=(
                f"클러치 야투율: {clutch.fg_pct * 100:.1f}%. "
                + (
                    f"압박 상황에서도 {clutch.fg_pct * 100:.1f}%의 높은 야투율을 유지합니다. "
                    "클러치 슈터로서의 역량이 뛰어납니다."
                    if fg_elite
                    else (
                        f"클러치 상황에서 {clutch.fg_pct * 100:.1f}%로 안정적인 야투율을 보입니다."
                        if fg_good
                        else (
                            f"클러치 야투율 {clutch.fg_pct * 100:.1f}%는 매우 낮은 수준입니다. "
                            "압박 상황 슈팅 정확도를 우선적으로 개선해야 합니다."
                            if fg_poor
                            else f"클러치 야투율 {clutch.fg_pct * 100:.1f}%로 개선 여지가 있습니다."
                        )
                    )
                )
            ),
            suggestion=(
                "압박 상황에서의 루틴(숨 조절, 발 정렬, 시선 고정)을 체계화하세요."
                if not fg_good
                else None
            ),
            current_value=clutch.fg_pct * 100.0,
            ideal_value=cfg.clutch_fg_pct_threshold * 100.0,
            unit="percent",
            confidence=0.88,
        ))

        # 3. 클러치 자유투
        if clutch.ft_pct > 0.0:
            ft_good = clutch.ft_pct >= cfg.clutch_ft_pct_good
            ft_critical = clutch.ft_pct < cfg.clutch_ft_pct_critical
            sev_ft = self._severity_mapper.from_ratio(clutch.ft_pct)
            items.append(FeedbackItem(
                category=FeedbackCategory.FOLLOW_THROUGH,
                feedback_type=(
                    FeedbackType.POSITIVE
                    if ft_good
                    else (FeedbackType.WARNING if ft_critical else FeedbackType.CORRECTION)
                ),
                priority=FeedbackFormatter.severity_to_priority(sev_ft.severity),
                title=f"#{pid} 클러치 자유투",
                description=(
                    f"클러치 자유투 성공률: {clutch.ft_pct * 100:.1f}%. "
                    + (
                        "클러치 상황에서도 높은 자유투 성공률을 유지합니다. "
                        "심리적 압박을 잘 극복하는 선수입니다."
                        if ft_good
                        else (
                            f"클러치 자유투 {clutch.ft_pct * 100:.1f}%는 위험 수준입니다. "
                            "자유투 실패는 경기를 뒤집는 결정적 실수가 됩니다."
                            if ft_critical
                            else f"클러치 자유투 {clutch.ft_pct * 100:.1f}%는 개선이 필요합니다."
                        )
                    )
                ),
                suggestion=(
                    "자유투 루틴 강화와 압박 상황 시뮬레이션 훈련을 진행하세요."
                    if not ft_good
                    else None
                ),
                current_value=clutch.ft_pct * 100.0,
                ideal_value=cfg.clutch_ft_pct_good * 100.0,
                unit="percent",
                confidence=0.88,
            ))

        # 4. 클러치 턴오버
        to_safe = clutch.turnovers <= cfg.clutch_turnover_max
        to_critical = clutch.turnovers >= cfg.clutch_turnover_critical
        sev_to = self._severity_mapper.from_ratio_inverse(
            clutch.turnovers / max(cfg.clutch_turnover_critical, 1)
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.BALL_CONTROL,
            feedback_type=(
                FeedbackType.POSITIVE
                if to_safe
                else (FeedbackType.WARNING if to_critical else FeedbackType.CORRECTION)
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_to.severity),
            title=f"#{pid} 클러치 턴오버",
            description=(
                f"클러치 상황 턴오버: {clutch.turnovers}개. "
                + (
                    "클러치 상황에서 볼 관리가 안정적입니다. "
                    "압박 하에서도 침착한 판단력을 보였습니다."
                    if to_safe
                    else (
                        f"클러치 턴오버 {clutch.turnovers}개는 매우 위험합니다. "
                        "결정적 순간 볼 소유권 상실은 경기 결과에 직접 영향을 미칩니다."
                        if to_critical
                        else f"클러치 턴오버 {clutch.turnovers}개는 개선이 필요합니다."
                    )
                )
            ),
            suggestion=(
                "클러치 상황에서 무리한 드리블을 줄이고 안전한 패스 옵션을 우선하세요."
                if not to_safe
                else None
            ),
            current_value=float(clutch.turnovers),
            ideal_value=float(cfg.clutch_turnover_max),
            unit="개",
            confidence=0.92,
        ))

        # 5. 클러치 +/-
        pm_good = clutch.plus_minus >= cfg.clutch_plus_minus_good
        pm_poor = clutch.plus_minus <= cfg.clutch_plus_minus_poor
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE
                if pm_good
                else (FeedbackType.WARNING if pm_poor else FeedbackType.TIP)
            ),
            priority=(
                FeedbackPriority.HIGH
                if pm_poor
                else (FeedbackPriority.MEDIUM if pm_good else FeedbackPriority.LOW)
            ),
            title=f"#{pid} 클러치 +/-",
            description=(
                f"클러치 상황 +/-: {clutch.plus_minus:+d}. "
                + (
                    "클러치 상황에서 코트에 있을 때 팀 성과가 크게 향상됩니다. "
                    "결정적 순간 팀에 긍정적 영향을 미치는 핵심 선수입니다."
                    if pm_good
                    else (
                        f"클러치 +/- {clutch.plus_minus:+d}는 심각한 수준입니다. "
                        "결정적 순간 코트 기여도를 전반적으로 재검토해야 합니다."
                        if pm_poor
                        else "클러치 +/-가 중립적입니다. 결정적 순간 팀 기여도를 높이세요."
                    )
                )
            ),
            current_value=float(clutch.plus_minus),
            ideal_value=float(cfg.clutch_plus_minus_good),
            unit="점",
            confidence=0.85,
        ))

        # 6. 온/오프 코트 넷레이팅 차이 (클러치 임팩트와 연계)
        impact = analysis.impact_differential
        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.POSITIVE if impact >= 5.0 else
                (FeedbackType.WARNING if impact <= -5.0 else FeedbackType.TIP)
            ),
            priority=(
                FeedbackPriority.MEDIUM if abs(impact) >= 5.0 else FeedbackPriority.LOW
            ),
            title=f"#{pid} 온/오프코트 임팩트",
            description=(
                f"온코트 넷레이팅: {analysis.on_court_net_rating:+.1f}, "
                f"오프코트: {analysis.off_court_net_rating:+.1f} "
                f"(임팩트 차이: {impact:+.1f}). "
                + (
                    "코트에 있을 때 팀이 현저히 더 나은 성과를 보입니다. "
                    "선수의 존재 자체가 팀 전술에 큰 가치를 더합니다."
                    if impact >= 5.0
                    else (
                        "코트에 있을 때 팀 성과가 저하됩니다. "
                        "역할 재조정과 매치업 분석이 필요합니다."
                        if impact <= -5.0
                        else "온/오프코트 성과 차이가 제한적입니다."
                    )
                )
            ),
            current_value=impact,
            ideal_value=5.0,
            unit="넷레이팅",
            confidence=0.80,
        ))

        return items

    # -------------------------------------------------------------------------
    # 팀 클러치 종합 분석
    # -------------------------------------------------------------------------
    def _analyze_team_clutch(
        self,
        clutch_players: list[IndividualAnalysis],
        cfg: ClutchFeedbackConfig,
    ) -> list[FeedbackItem]:
        """팀 클러치 종합 피드백 생성."""
        items: list[FeedbackItem] = []

        # 유효 클러치 스탯 수집
        valid_clutch = [
            a.clutch_stats
            for a in clutch_players
            if a.clutch_stats is not None
        ]
        n = len(valid_clutch)
        if n == 0:
            return items

        total_pts = sum(c.points for c in valid_clutch)
        avg_fg_pct = sum(c.fg_pct for c in valid_clutch) / n
        total_to = sum(c.turnovers for c in valid_clutch)
        avg_pm = sum(c.plus_minus for c in valid_clutch) / n

        # 7. 팀 클러치 FG% 종합
        team_fg_good = avg_fg_pct >= cfg.team_clutch_fg_good
        sev_team_fg = self._severity_mapper.from_ratio(avg_fg_pct)
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if team_fg_good else FeedbackType.CORRECTION
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_team_fg.severity),
            title="팀 클러치 야투율",
            description=(
                f"팀 클러치 평균 야투율: {avg_fg_pct * 100:.1f}% "
                f"(분석 선수 {n}명 기준). "
                + (
                    "팀 전체가 클러치 상황에서 높은 슈팅 효율을 보입니다. "
                    "강한 클러치 팀 역량을 갖추고 있습니다."
                    if team_fg_good
                    else "팀 클러치 야투율이 기준에 미치지 못합니다. "
                         "클러치 상황 공격 전술과 슈팅 옵션을 재정비하세요."
                )
            ),
            suggestion=(
                "클러치 상황에서 최고 효율 슈터에게 집중적으로 공을 배급하세요."
                if not team_fg_good
                else None
            ),
            current_value=avg_fg_pct * 100.0,
            ideal_value=cfg.team_clutch_fg_good * 100.0,
            unit="percent",
            confidence=0.87,
        ))

        # 8. 팀 클러치 턴오버 합계
        to_safe = total_to <= cfg.clutch_turnover_max * n * 0.5
        items.append(FeedbackItem(
            category=FeedbackCategory.BALL_CONTROL,
            feedback_type=(
                FeedbackType.POSITIVE if to_safe else FeedbackType.WARNING
            ),
            priority=(
                FeedbackPriority.MEDIUM if not to_safe else FeedbackPriority.LOW
            ),
            title="팀 클러치 턴오버 합계",
            description=(
                f"클러치 상황 팀 총 턴오버: {total_to}개 "
                f"(선수당 평균 {total_to / n:.1f}개). "
                + (
                    "팀 전체가 클러치 상황에서 볼 관리를 안정적으로 합니다."
                    if to_safe
                    else "팀 클러치 턴오버가 과도합니다. "
                         "결정적 순간 팀 전체의 볼 관리 훈련이 시급합니다."
                )
            ),
            current_value=float(total_to),
            ideal_value=float(n),
            unit="개",
            confidence=0.88,
        ))

        # 9. 팀 클러치 총득점 기여
        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=(
                FeedbackType.POSITIVE
                if total_pts >= n * cfg.clutch_points_good
                else FeedbackType.IMPROVEMENT
            ),
            priority=FeedbackPriority.HIGH,
            title="팀 클러치 총득점",
            description=(
                f"클러치 상황 팀 총득점: {total_pts}점 "
                f"(선수당 평균 {total_pts / n:.1f}점). "
                + (
                    "팀 전체의 클러치 득점이 우수합니다. "
                    "복수의 선수가 결정적 순간 기여하는 팀 클러치 역량이 뛰어납니다."
                    if total_pts >= n * cfg.clutch_points_good
                    else "팀 클러치 득점이 부족합니다. "
                         "클러치 상황 공격 옵션의 다양화와 선수별 역할 명확화가 필요합니다."
                )
            ),
            current_value=float(total_pts),
            ideal_value=float(n * cfg.clutch_points_good),
            unit="points",
            confidence=0.87,
        ))

        # 10. 팀 클러치 +/- 평균
        pm_good = avg_pm >= cfg.clutch_plus_minus_good
        pm_poor = avg_pm <= cfg.clutch_plus_minus_poor
        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE
                if pm_good
                else (FeedbackType.WARNING if pm_poor else FeedbackType.TIP)
            ),
            priority=(
                FeedbackPriority.HIGH if pm_poor else
                (FeedbackPriority.MEDIUM if pm_good else FeedbackPriority.LOW)
            ),
            title="팀 클러치 +/- 평균",
            description=(
                f"클러치 선수 평균 +/-: {avg_pm:+.1f}. "
                + (
                    "클러치 선수들이 결정적 순간 팀에 긍정적 기여를 합니다. "
                    "클러치 라인업 구성이 효과적입니다."
                    if pm_good
                    else (
                        "클러치 선수 평균 +/-가 심각한 수준입니다. "
                        "클러치 라인업을 전면 재검토해야 합니다."
                        if pm_poor
                        else "클러치 선수들의 +/-가 중립적입니다. "
                             "결정적 순간 기여도 향상이 필요합니다."
                    )
                )
            ),
            current_value=avg_pm,
            ideal_value=float(cfg.clutch_plus_minus_good),
            unit="점",
            confidence=0.83,
        ))

        # 11. 최고 클러치 퍼포머
        items.extend(self._best_clutch_performer(clutch_players))

        # 12. 최악 클러치 퍼포머
        items.extend(self._worst_clutch_performer(clutch_players))

        # 13. 클러치 득점 효율 밸런스
        items.extend(self._clutch_scoring_efficiency(valid_clutch, n, cfg))

        # 14. 클러치 리스크 평가
        items.extend(self._clutch_risk_assessment(valid_clutch, n, cfg))

        # 15. 클러치 종합 등급
        items.extend(self._clutch_overall_grade(
            avg_fg_pct, total_to, avg_pm, n, cfg,
        ))

        return items

    # -------------------------------------------------------------------------
    # 최고 클러치 퍼포머
    # -------------------------------------------------------------------------
    def _best_clutch_performer(
        self,
        players: list[IndividualAnalysis],
    ) -> list[FeedbackItem]:
        """최고 클러치 퍼포머 식별."""
        items: list[FeedbackItem] = []
        if not players:
            return items

        best = max(
            players,
            key=lambda a: (
                (a.clutch_stats.points if a.clutch_stats else 0)
                + (a.clutch_stats.plus_minus if a.clutch_stats else 0)
            ),
        )
        cs = best.clutch_stats
        if cs is None:
            return items

        composite = cs.points + cs.plus_minus
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.POSITIVE,
            priority=FeedbackPriority.HIGH,
            title="최고 클러치 퍼포머",
            description=(
                f"#{best.player_tracking_id}: 클러치 {cs.points}득점, "
                f"FG% {cs.fg_pct * 100:.1f}%, +/- {cs.plus_minus:+d}. "
                f"종합 클러치 지수 {composite:+d}로 팀 내 최고 클러치 퍼포먼스를 보였습니다. "
                "결정적 순간 공을 맡겨야 할 1순위 옵션입니다."
            ),
            current_value=float(composite),
            confidence=0.90,
        ))
        return items

    # -------------------------------------------------------------------------
    # 최악 클러치 퍼포머
    # -------------------------------------------------------------------------
    def _worst_clutch_performer(
        self,
        players: list[IndividualAnalysis],
    ) -> list[FeedbackItem]:
        """가장 부진한 클러치 퍼포머 식별."""
        items: list[FeedbackItem] = []
        if len(players) < 2:
            return items

        worst = min(
            players,
            key=lambda a: (
                (a.clutch_stats.points if a.clutch_stats else 0)
                + (a.clutch_stats.plus_minus if a.clutch_stats else 0)
            ),
        )
        cs = worst.clutch_stats
        if cs is None:
            return items

        composite = cs.points + cs.plus_minus
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.WARNING,
            priority=FeedbackPriority.HIGH,
            title="클러치 부진 선수",
            description=(
                f"#{worst.player_tracking_id}: 클러치 {cs.points}득점, "
                f"FG% {cs.fg_pct * 100:.1f}%, 턴오버 {cs.turnovers}개, "
                f"+/- {cs.plus_minus:+d}. 클러치 상황에서 가장 부진한 성과를 보였습니다. "
                "결정적 순간 역할 재조정 또는 교체 타이밍을 검토해야 합니다."
            ),
            suggestion=(
                f"#{worst.player_tracking_id}를 클러치 상황에서 제한적 역할로 전환하거나, "
                "압박 하 시뮬레이션 훈련을 강화하세요."
            ),
            current_value=float(composite),
            confidence=0.85,
        ))
        return items

    # -------------------------------------------------------------------------
    # 클러치 득점 효율 밸런스
    # -------------------------------------------------------------------------
    def _clutch_scoring_efficiency(
        self,
        clutch_list: list[ClutchStats],
        n: int,
        cfg: ClutchFeedbackConfig,
    ) -> list[FeedbackItem]:
        """클러치 득점량 대비 효율 분석."""
        items: list[FeedbackItem] = []
        if n == 0:
            return items

        total_pts = sum(c.points for c in clutch_list)
        avg_fg = sum(c.fg_pct for c in clutch_list) / n

        # 고득점 저효율 vs 저득점 고효율 분석
        high_volume_low_eff = total_pts >= n * cfg.clutch_points_good and avg_fg < cfg.clutch_fg_pct_threshold
        low_volume_high_eff = total_pts < n * cfg.clutch_points_good and avg_fg >= cfg.clutch_fg_pct_elite

        items.append(FeedbackItem(
            category=FeedbackCategory.RELEASE,
            feedback_type=(
                FeedbackType.WARNING if high_volume_low_eff else
                (FeedbackType.IMPROVEMENT if low_volume_high_eff else FeedbackType.TIP)
            ),
            priority=(
                FeedbackPriority.HIGH if high_volume_low_eff else FeedbackPriority.MEDIUM
            ),
            title="클러치 득점-효율 밸런스",
            description=(
                f"팀 클러치 총득점 {total_pts}점, 평균 야투율 {avg_fg * 100:.1f}%. "
                + (
                    "높은 슈팅 빈도에 비해 야투율이 낮습니다. "
                    "클러치에서 무분별한 슈팅보다 고확률 슈팅 기회를 만드는 전술이 필요합니다."
                    if high_volume_low_eff
                    else (
                        "야투율은 높지만 공격 시도가 적습니다. "
                        "클러치 상황에서 더 적극적인 공격 전개가 필요합니다."
                        if low_volume_high_eff
                        else "클러치 득점량과 효율의 균형이 적절합니다."
                    )
                )
            ),
            confidence=0.85,
        ))

        return items

    # -------------------------------------------------------------------------
    # 클러치 리스크 평가
    # -------------------------------------------------------------------------
    def _clutch_risk_assessment(
        self,
        clutch_list: list[ClutchStats],
        n: int,
        cfg: ClutchFeedbackConfig,
    ) -> list[FeedbackItem]:
        """클러치 상황 리스크 종합 평가."""
        items: list[FeedbackItem] = []
        if n == 0:
            return items

        total_to = sum(c.turnovers for c in clutch_list)
        avg_fg = sum(c.fg_pct for c in clutch_list) / n
        avg_ft = sum(c.ft_pct for c in clutch_list) / n

        # 리스크 스코어: 턴오버 높고 + FG 낮고 + FT 낮으면 고위험
        risk_score = (
            (1.0 - avg_fg) * 40.0
            + (1.0 - avg_ft) * 20.0
            + min(total_to / max(n, 1) / cfg.clutch_turnover_critical, 1.0) * 40.0
        )
        high_risk = risk_score >= 55.0
        low_risk = risk_score < 30.0

        items.append(FeedbackItem(
            category=FeedbackCategory.BALL_CONTROL,
            feedback_type=(
                FeedbackType.WARNING if high_risk else
                (FeedbackType.POSITIVE if low_risk else FeedbackType.IMPROVEMENT)
            ),
            priority=(
                FeedbackPriority.HIGH if high_risk else FeedbackPriority.MEDIUM
            ),
            title="클러치 리스크 지수",
            description=(
                f"클러치 리스크 스코어: {risk_score:.1f}/100 "
                f"(FG% 리스크 {(1.0 - avg_fg) * 40:.0f}, "
                f"FT% 리스크 {(1.0 - avg_ft) * 20:.0f}, "
                f"TO 리스크 {min(total_to / max(n, 1) / cfg.clutch_turnover_critical, 1.0) * 40:.0f}). "
                + (
                    "클러치 리스크가 매우 높습니다. 결정적 순간 경기를 잃을 확률이 높으므로 "
                    "클러치 전술과 인원을 전면 재점검하세요."
                    if high_risk
                    else (
                        "클러치 리스크가 낮아 결정적 순간 안정적인 경기 운영이 가능합니다."
                        if low_risk
                        else "클러치 리스크가 보통 수준입니다. 개별 약점 항목을 집중 개선하세요."
                    )
                )
            ),
            current_value=risk_score,
            ideal_value=30.0,
            unit="score",
            confidence=0.85,
        ))

        return items

    # -------------------------------------------------------------------------
    # 클러치 종합 등급
    # -------------------------------------------------------------------------
    def _clutch_overall_grade(
        self,
        avg_fg: float,
        total_to: int,
        avg_pm: float,
        n: int,
        cfg: ClutchFeedbackConfig,
    ) -> list[FeedbackItem]:
        """클러치 종합 등급 피드백."""
        items: list[FeedbackItem] = []
        if n == 0:
            return items

        # 100점 만점 종합 점수
        fg_score = min(avg_fg / cfg.clutch_fg_pct_elite * 100.0, 100.0) * 0.40
        to_score = max(0.0, (1.0 - total_to / max(n * cfg.clutch_turnover_critical, 1)) * 100.0) * 0.30
        pm_score = min(max((avg_pm + 10) / 20.0 * 100.0, 0.0), 100.0) * 0.30
        overall = fg_score + to_score + pm_score

        if overall >= 75:
            grade, desc_suffix = "A", "팀의 클러치 역량이 엘리트 수준입니다."
        elif overall >= 60:
            grade, desc_suffix = "B", "클러치 역량이 양호합니다. 세부 항목 보강으로 더 강해질 수 있습니다."
        elif overall >= 45:
            grade, desc_suffix = "C", "클러치 역량에 개선이 필요합니다. 약점 항목부터 우선 보강하세요."
        else:
            grade, desc_suffix = "D", "클러치 역량이 심각하게 부족합니다. 전면적인 개선이 시급합니다."

        sev = self._severity_mapper.from_score(max(0.0, min(overall, 100.0)))
        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.POSITIVE if overall >= 60 else FeedbackType.CORRECTION
            ),
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="클러치 종합 등급",
            description=(
                f"클러치 종합 점수: {overall:.1f}/100 (등급: {grade}). "
                f"[야투 {fg_score / 0.40:.0f}점 × 40% / "
                f"턴오버 {to_score / 0.30:.0f}점 × 30% / "
                f"+/- {pm_score / 0.30:.0f}점 × 30%]. "
                + desc_suffix
            ),
            current_value=overall,
            ideal_value=75.0,
            unit="score",
            confidence=0.88,
        ))

        return items

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        """생성기 상태 초기화."""
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"ClutchFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "ClutchFeedbackGenerator",
    "ClutchFeedbackConfig",
]

__version__ = "1.0.0"
