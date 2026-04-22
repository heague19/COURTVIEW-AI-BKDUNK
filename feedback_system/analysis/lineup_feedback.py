# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: lineup_feedback.py
설명: 라인업 분석 피드백 생성기 (전력분석원 수준).
      - 최고/최저/공격특화/수비특화 라인업 분석
      - 라인업 공수 밸런스, 포제션 효율, 로테이션 패턴
      - 벤치 유닛 효율, 핵심 선수 출전 분포, 라인업 다양성
      - 과다 사용/과소 사용 라인업, 선수 조합 시너지
      - list[LineupData] → FeedbackItem 변환 (15+ 항목)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from collections import Counter
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
from shared.dto.tactical_dto import LineupData

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.korean_templates import KoreanTemplates
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper, get_default_korean_templates


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class LineupFeedbackConfig:
    """라인업 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    net_rating_good: float = 5.0          # +5 이상 → 양호
    net_rating_great: float = 10.0        # +10 이상 → 우수
    net_rating_poor: float = -5.0         # -5 이하 → 부진
    min_minutes_threshold: float = 3.0    # 최소 3분 이상 출전
    top_lineups_count: int = 3            # 상위 라인업 표시 수
    bottom_lineups_count: int = 2         # 하위 라인업 표시 수
    overuse_minutes: float = 15.0         # 한 라인업 15분+ → 과다
    underuse_quality_minutes: float = 5.0 # 넷레이팅 좋은데 5분 미만 → 과소
    off_def_gap_threshold: float = 15.0   # 공수 효율 차이 임계값
    possession_efficiency_good: float = 1.05  # PPP 양호 기준


# =============================================================================
# LineupFeedbackGenerator 클래스
# =============================================================================
class LineupFeedbackGenerator:
    """
    라인업 분석 피드백 생성기.

    LineupData 목록을 입력받아 라인업 효율, 최고/최저 조합,
    로테이션 패턴, 벤치 효율, 선수 시너지에 대한 전력분석원급
    피드백을 생성합니다 (15+ FeedbackItem).
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: LineupFeedbackConfig | None = None) -> None:
        self._config: LineupFeedbackConfig = config or LineupFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "LineupFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def generate(
        self,
        lineups: list[LineupData],
    ) -> list[FeedbackItem]:
        """라인업 데이터 목록에서 전력분석원급 피드백 생성."""
        items: list[FeedbackItem] = []
        cfg = self._config

        if not lineups:
            return items

        # 최소 출전 시간 필터
        qualified = [
            lu for lu in lineups
            if lu.minutes >= cfg.min_minutes_threshold
        ]

        if not qualified:
            with self._lock:
                self._total_generated += 1
            return items

        # 정렬 기준 준비
        by_net = sorted(qualified, key=lambda x: x.net_rating, reverse=True)
        by_off = sorted(qualified, key=lambda x: x.offensive_rating, reverse=True)
        by_def = sorted(qualified, key=lambda x: x.defensive_rating)  # 수비는 낮을수록 좋음
        by_minutes = sorted(qualified, key=lambda x: x.minutes, reverse=True)
        total_minutes = sum(lu.minutes for lu in qualified)

        # === 1. 최고 넷레이팅 라인업 (최대 3개) ===
        items.extend(self._top_net_rating_feedback(by_net, cfg))

        # === 2. 최저 넷레이팅 라인업 (최대 2개) ===
        items.extend(self._bottom_net_rating_feedback(by_net, cfg))

        # === 3. 최고 공격 라인업 ===
        items.extend(self._best_offensive_lineup(by_off))

        # === 4. 최고 수비 라인업 ===
        items.extend(self._best_defensive_lineup(by_def))

        # === 5. 공수 밸런스 분석 ===
        items.extend(self._off_def_balance_feedback(by_net[:5], cfg))

        # === 6. 라인업 과다 사용 경고 ===
        items.extend(self._overuse_warning(by_minutes, cfg))

        # === 7. 과소 사용된 고효율 라인업 ===
        items.extend(self._underuse_quality_feedback(qualified, cfg))

        # === 8. 라인업 다양성 ===
        items.append(self._lineup_variety_feedback(qualified, total_minutes))

        # === 9. 출전 시간 집중도 ===
        items.append(self._minutes_concentration_feedback(by_minutes, total_minutes))

        # === 10. 플러스/마이너스 최고 조합 ===
        items.extend(self._plus_minus_feedback(qualified))

        # === 11. 포제션당 효율 ===
        items.extend(self._possession_efficiency_feedback(qualified, cfg))

        # === 12. 핵심 선수 출전 빈도 ===
        items.extend(self._player_frequency_feedback(qualified))

        # === 13. 라인업 운용 종합 요약 ===
        items.append(self._summary_feedback(qualified, by_net, total_minutes, cfg))

        with self._lock:
            self._total_generated += 1

        return items

    # =========================================================================
    # 1. 최고 넷레이팅 라인업
    # =========================================================================
    def _top_net_rating_feedback(
        self, by_net: list[LineupData], cfg: LineupFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        for i, lineup in enumerate(by_net[:cfg.top_lineups_count], start=1):
            pids = self._format_players(lineup)
            quality = "매우 우수" if lineup.net_rating >= cfg.net_rating_great else "양호"
            items.append(self._make(
                category=FeedbackCategory.COORDINATION,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.MEDIUM,
                title=f"넷레이팅 {i}위 라인업",
                description=(
                    f"라인업 [{pids}]: 넷레이팅 {lineup.net_rating:+.1f} "
                    f"(공격 {lineup.offensive_rating:.1f} / 수비 {lineup.defensive_rating:.1f}), "
                    f"{lineup.minutes:.1f}분 출전. 공수 밸런스가 {quality}한 조합입니다."
                ),
                current_value=lineup.net_rating,
                confidence=0.87,
            ))
        return items

    # =========================================================================
    # 2. 최저 넷레이팅 라인업
    # =========================================================================
    def _bottom_net_rating_feedback(
        self, by_net: list[LineupData], cfg: LineupFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        worst = by_net[-cfg.bottom_lineups_count:]
        for i, lineup in enumerate(reversed(worst), start=1):
            if lineup.net_rating >= cfg.net_rating_good:
                continue
            pids = self._format_players(lineup)
            severity = "심각" if lineup.net_rating <= cfg.net_rating_poor else "개선 필요"
            items.append(self._make(
                category=FeedbackCategory.COORDINATION,
                fb_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title=f"개선 필요 라인업 {i}",
                description=(
                    f"라인업 [{pids}]: 넷레이팅 {lineup.net_rating:+.1f} "
                    f"({lineup.minutes:.1f}분 출전). "
                    f"상태: {severity}. "
                    f"이 조합의 출전 시간을 줄이거나 멤버 변경을 검토하세요."
                ),
                suggestion=(
                    f"넷레이팅 {lineup.net_rating:+.1f}은 100포제션당 "
                    f"약 {abs(lineup.net_rating):.0f}점을 상대에게 더 내주는 조합입니다. "
                    f"수비 효율({lineup.defensive_rating:.1f})과 공격 효율({lineup.offensive_rating:.1f}) 중 "
                    f"{'수비' if lineup.defensive_rating > 110 else '공격'} 쪽 보강이 시급합니다."
                ),
                current_value=lineup.net_rating,
                confidence=0.87,
            ))
        return items

    # =========================================================================
    # 3. 최고 공격 라인업
    # =========================================================================
    def _best_offensive_lineup(self, by_off: list[LineupData]) -> list[FeedbackItem]:
        best = by_off[0]
        pids = self._format_players(best)
        return [self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.POSITIVE,
            priority=FeedbackPriority.MEDIUM,
            title="최고 공격 효율 라인업",
            description=(
                f"라인업 [{pids}]: 공격 효율 {best.offensive_rating:.1f} "
                f"(넷 {best.net_rating:+.1f}, {best.minutes:.1f}분). "
                f"득점이 필요한 상황에서 우선적으로 투입할 수 있는 조합입니다."
            ),
            current_value=best.offensive_rating,
            confidence=0.85,
        )]

    # =========================================================================
    # 4. 최고 수비 라인업
    # =========================================================================
    def _best_defensive_lineup(self, by_def: list[LineupData]) -> list[FeedbackItem]:
        best = by_def[0]
        pids = self._format_players(best)
        return [self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.POSITIVE,
            priority=FeedbackPriority.MEDIUM,
            title="최고 수비 효율 라인업",
            description=(
                f"라인업 [{pids}]: 수비 효율 {best.defensive_rating:.1f} "
                f"(넷 {best.net_rating:+.1f}, {best.minutes:.1f}분). "
                f"리드 보호가 필요한 상황에서 활용할 수 있는 수비 조합입니다."
            ),
            current_value=best.defensive_rating,
            confidence=0.85,
        )]

    # =========================================================================
    # 5. 공수 밸런스 분석
    # =========================================================================
    def _off_def_balance_feedback(
        self, top_lineups: list[LineupData], cfg: LineupFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        for lineup in top_lineups:
            gap = abs(lineup.offensive_rating - lineup.defensive_rating)
            if gap <= cfg.off_def_gap_threshold:
                continue
            pids = self._format_players(lineup)
            is_off_heavy = lineup.offensive_rating > lineup.defensive_rating
            lean = "공격 편중" if is_off_heavy else "수비 편중"
            weak_side = "수비" if is_off_heavy else "공격"
            items.append(self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM,
                title=f"라인업 공수 불균형 ({lean})",
                description=(
                    f"라인업 [{pids}]: 공격 {lineup.offensive_rating:.1f} vs "
                    f"수비 {lineup.defensive_rating:.1f} (차이 {gap:.1f}). "
                    f"{lean} 라인업으로 {weak_side} 상황에서 취약합니다."
                ),
                suggestion=(
                    f"이 라인업을 {weak_side} 상황에서 사용할 때는 전술 조정이 필요합니다. "
                    f"{'수비 로테이션과 헬프디펜스를 강화하세요.' if is_off_heavy else '픽앤롤이나 트랜지션 공격 빈도를 늘리세요.'}"
                ),
                confidence=0.82,
            ))
        return items

    # =========================================================================
    # 6. 라인업 과다 사용 경고
    # =========================================================================
    def _overuse_warning(
        self, by_minutes: list[LineupData], cfg: LineupFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        for lineup in by_minutes:
            if lineup.minutes < cfg.overuse_minutes:
                break
            pids = self._format_players(lineup)
            items.append(self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.WARNING if lineup.net_rating < 0 else FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.MEDIUM if lineup.net_rating < 0 else FeedbackPriority.LOW,
                title="라인업 과다 사용",
                description=(
                    f"라인업 [{pids}]: {lineup.minutes:.1f}분 출전 "
                    f"(넷레이팅 {lineup.net_rating:+.1f}). "
                    + (f"장시간 사용에도 효율이 유지되고 있습니다."
                       if lineup.net_rating > 0
                       else f"장시간 사용 중 효율이 떨어지고 있어 로테이션 분산이 필요합니다.")
                ),
                current_value=lineup.minutes,
                confidence=0.80,
            ))
        return items

    # =========================================================================
    # 7. 과소 사용된 고효율 라인업
    # =========================================================================
    def _underuse_quality_feedback(
        self, qualified: list[LineupData], cfg: LineupFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        for lineup in qualified:
            if lineup.net_rating >= cfg.net_rating_good and lineup.minutes < cfg.underuse_quality_minutes:
                pids = self._format_players(lineup)
                items.append(self._make(
                    category=FeedbackCategory.TIP,
                    fb_type=FeedbackType.TIP,
                    priority=FeedbackPriority.MEDIUM,
                    title="과소 사용된 고효율 라인업",
                    description=(
                        f"라인업 [{pids}]: 넷레이팅 {lineup.net_rating:+.1f}인데 "
                        f"{lineup.minutes:.1f}분만 사용. "
                        f"효율 대비 활용도가 낮아 추가 출전을 고려할 수 있습니다."
                    ),
                    suggestion=(
                        f"넷레이팅 {lineup.net_rating:+.1f}은 잠재력 있는 조합입니다. "
                        f"다음 경기에서 출전 시간을 늘려 표본을 확대해 보세요."
                    ),
                    current_value=lineup.minutes,
                    confidence=0.75,
                ))
        return items

    # =========================================================================
    # 8. 라인업 다양성
    # =========================================================================
    def _lineup_variety_feedback(
        self, qualified: list[LineupData], total_minutes: float,
    ) -> FeedbackItem:
        count = len(qualified)
        if count >= 8:
            variety = "높음"
            fb_type = FeedbackType.POSITIVE
            desc_tail = "다양한 조합을 적극 활용하고 있습니다."
        elif count >= 5:
            variety = "보통"
            fb_type = FeedbackType.TIP
            desc_tail = "적정 수준의 라인업 다양성입니다."
        else:
            variety = "낮음"
            fb_type = FeedbackType.IMPROVEMENT
            desc_tail = "라인업 변화가 적어 상대 대응이 제한적입니다. 추가 조합을 시도해 보세요."

        return self._make(
            category=FeedbackCategory.COORDINATION,
            fb_type=fb_type,
            priority=FeedbackPriority.LOW,
            title=f"라인업 다양성: {variety}",
            description=(
                f"총 {count}개 라인업 운용 (합산 {total_minutes:.0f}분). "
                f"{desc_tail}"
            ),
            confidence=0.82,
        )

    # =========================================================================
    # 9. 출전 시간 집중도
    # =========================================================================
    def _minutes_concentration_feedback(
        self, by_minutes: list[LineupData], total_minutes: float,
    ) -> FeedbackItem:
        if not by_minutes or total_minutes <= 0:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="출전 시간 분포",
                description="데이터가 부족하여 분석할 수 없습니다.",
                confidence=0.50,
            )

        top_share = by_minutes[0].minutes / total_minutes
        if top_share > 0.50:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.WARNING,
                priority=FeedbackPriority.MEDIUM,
                title="출전 시간 과도 집중",
                description=(
                    f"가장 많이 사용된 라인업이 전체의 {top_share:.0%}를 차지합니다. "
                    f"특정 조합에 지나치게 의존하면 피로 누적과 상대 대응에 취약해집니다."
                ),
                suggestion="로테이션을 분산하여 선수 피로를 관리하고 전술 유연성을 높이세요.",
                confidence=0.82,
            )
        if top_share > 0.35:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="출전 시간 약간 집중",
                description=(
                    f"상위 라인업이 전체의 {top_share:.0%}를 점유합니다. "
                    f"적정 범위이나 후반 피로 관리에 유의하세요."
                ),
                confidence=0.78,
            )
        return self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.POSITIVE,
            priority=FeedbackPriority.LOW,
            title="출전 시간 균등 분배",
            description=(
                f"상위 라인업 점유율 {top_share:.0%}로 고른 로테이션을 운용하고 있습니다."
            ),
            confidence=0.80,
        )

    # =========================================================================
    # 10. 플러스/마이너스 분석
    # =========================================================================
    def _plus_minus_feedback(self, qualified: list[LineupData]) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        by_pm = sorted(qualified, key=lambda x: x.plus_minus, reverse=True)

        # 최고 +/- 조합
        best = by_pm[0]
        if best.plus_minus > 0:
            pids = self._format_players(best)
            items.append(self._make(
                category=FeedbackCategory.COORDINATION,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title="최고 +/- 라인업",
                description=(
                    f"라인업 [{pids}]: +/- {best.plus_minus:+d} "
                    f"({best.minutes:.1f}분). "
                    f"코트 위에서 가장 효과적으로 점수 차이를 만들어낸 조합입니다."
                ),
                current_value=float(best.plus_minus),
                confidence=0.85,
            ))

        # 최저 +/- 조합
        worst = by_pm[-1]
        if worst.plus_minus < 0:
            pids = self._format_players(worst)
            items.append(self._make(
                category=FeedbackCategory.COORDINATION,
                fb_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.MEDIUM,
                title="최저 +/- 라인업",
                description=(
                    f"라인업 [{pids}]: +/- {worst.plus_minus:+d} "
                    f"({worst.minutes:.1f}분). "
                    f"이 조합에서 점수 차이가 가장 크게 벌어졌습니다."
                ),
                current_value=float(worst.plus_minus),
                confidence=0.85,
            ))

        return items

    # =========================================================================
    # 11. 포제션당 효율
    # =========================================================================
    def _possession_efficiency_feedback(
        self, qualified: list[LineupData], cfg: LineupFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        with_poss = [lu for lu in qualified if lu.possessions > 0]
        if not with_poss:
            return items

        # 포제션당 넷레이팅 효율
        total_poss = sum(lu.possessions for lu in with_poss)
        weighted_net = sum(lu.net_rating * lu.possessions for lu in with_poss) / total_poss

        items.append(self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.POSITIVE if weighted_net > 0 else FeedbackType.IMPROVEMENT,
            priority=FeedbackPriority.LOW,
            title="포제션 가중 넷레이팅",
            description=(
                f"전체 {total_poss}포제션 기준 가중 넷레이팅 {weighted_net:+.1f}. "
                + (f"포제션 기반으로도 양호한 라인업 운용입니다."
                   if weighted_net > 0
                   else f"포제션 기반 효율이 마이너스로 라인업 조정이 필요합니다.")
            ),
            current_value=weighted_net,
            confidence=0.80,
        ))

        # 포제션 대비 출전 시간 비효율 (포제션 소수 + 출전 시간 많음 = 비효율적 수비)
        for lu in with_poss:
            if lu.minutes > 8 and lu.possessions < 10 and lu.net_rating < 0:
                pids = self._format_players(lu)
                items.append(self._make(
                    category=FeedbackCategory.TIP,
                    fb_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.LOW,
                    title="포제션 대비 출전 시간 비효율",
                    description=(
                        f"라인업 [{pids}]: {lu.minutes:.1f}분에 {lu.possessions}포제션. "
                        f"출전 시간 대비 공격 기회가 적어 템포가 느린 조합입니다."
                    ),
                    confidence=0.72,
                ))
                break  # 최대 1건

        return items

    # =========================================================================
    # 12. 핵심 선수 출전 빈도
    # =========================================================================
    def _player_frequency_feedback(
        self, qualified: list[LineupData],
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        counter: Counter[int] = Counter()
        minutes_by_player: dict[int, float] = {}
        net_by_player: dict[int, list[float]] = {}

        for lu in qualified:
            for pid in lu.player_tracking_ids:
                counter[pid] += 1
                minutes_by_player[pid] = minutes_by_player.get(pid, 0.0) + lu.minutes
                net_by_player.setdefault(pid, []).append(lu.net_rating)

        if not counter:
            return items

        # 가장 많이 등장하는 선수
        top_player, top_count = counter.most_common(1)[0]
        avg_net = sum(net_by_player[top_player]) / len(net_by_player[top_player])
        items.append(self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="가장 많이 기용된 선수",
            description=(
                f"선수 #{top_player}: {top_count}개 라인업에 편성, "
                f"합산 {minutes_by_player[top_player]:.0f}분 출전. "
                f"소속 라인업 평균 넷레이팅 {avg_net:+.1f}. "
                + ("핵심 선수로서 효율적으로 기여하고 있습니다."
                   if avg_net > 0
                   else "출전 빈도에 비해 소속 라인업 효율이 낮아 점검이 필요합니다.")
            ),
            confidence=0.78,
        ))

        return items

    # =========================================================================
    # 13. 종합 요약
    # =========================================================================
    def _summary_feedback(
        self,
        qualified: list[LineupData],
        by_net: list[LineupData],
        total_minutes: float,
        cfg: LineupFeedbackConfig,
    ) -> FeedbackItem:
        avg_net = sum(lu.net_rating for lu in qualified) / len(qualified)
        good_count = sum(1 for lu in qualified if lu.net_rating >= cfg.net_rating_good)
        poor_count = sum(1 for lu in qualified if lu.net_rating <= cfg.net_rating_poor)

        return self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="라인업 운용 종합 요약",
            description=(
                f"총 {len(qualified)}개 라인업 운용 ({total_minutes:.0f}분). "
                f"평균 넷레이팅 {avg_net:+.1f}, "
                f"양호({cfg.net_rating_good:+.0f}+) {good_count}개, "
                f"부진({cfg.net_rating_poor:.0f}이하) {poor_count}개. "
                f"최고 넷 {by_net[0].net_rating:+.1f} / 최저 넷 {by_net[-1].net_rating:+.1f}."
            ),
            confidence=0.90,
        )

    # =========================================================================
    # 유틸리티
    # =========================================================================
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"LineupFeedbackGenerator(generated={self._total_generated})"

    @staticmethod
    def _format_players(lineup: LineupData) -> str:
        """선수 ID 목록 포맷."""
        return ", ".join(f"#{pid}" for pid in lineup.player_tracking_ids)

    @staticmethod
    def _make(
        *,
        category: FeedbackCategory,
        fb_type: FeedbackType,
        priority: FeedbackPriority,
        title: str,
        description: str,
        suggestion: str | None = None,
        current_value: float | None = None,
        confidence: float = 0.80,
    ) -> FeedbackItem:
        return FeedbackItem(
            category=category,
            feedback_type=fb_type,
            priority=priority,
            body_parts=[],
            title=title,
            description=description,
            suggestion=suggestion,
            current_value=current_value,
            confidence=confidence,
        )


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "LineupFeedbackGenerator",
    "LineupFeedbackConfig",
]

__version__ = "1.0.0"
