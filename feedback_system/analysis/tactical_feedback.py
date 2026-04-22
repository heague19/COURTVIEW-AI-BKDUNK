# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: tactical_feedback.py
설명: 공격 전술 피드백 생성기.
      - 픽앤롤 효율, 속공, 세트 플레이, 패싱 네트워크, 전환 공격
      - 핸들러/롤러 분할, 속공 빈도, 전환 vs 하프코트 PPP 갭
      - 아이솔레이션, 포스트업, 스팟업 효율
      - 패스-어시스트 비율, 탑 패서 연결, 오펜시브 레이팅
      - 플레이 유형 다양성 지수, 최고/최저 플레이 비교
      - TacticalAnalysisResult → FeedbackItem 변환
      - 연령대별 전술 용어 복잡도 조정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

import math
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
from shared.dto.tactical_dto import TacticalAnalysisResult

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.korean_templates import KoreanTemplates
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper, get_default_korean_templates


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class TacticalFeedbackConfig:
    """전술 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    # 전술 효율 임계치
    pnr_ppp_good: float = 1.0         # PPP 1.0 이상 → 양호
    fast_break_ppp_good: float = 1.1  # 속공 PPP 1.1 이상 → 양호
    set_play_ppp_good: float = 0.95   # 세트 플레이 PPP 0.95+ → 양호
    ball_movement_good: float = 70.0  # 볼 무브먼트 70+ → 양호
    transition_ppp_good: float = 1.1  # 전환 공격 PPP 1.1+ → 양호

    # 추가 임계치 (확장 분석)
    isolation_ppp_good: float = 0.90  # 아이솔레이션 PPP 0.90+ → 양호
    post_up_ppp_good: float = 0.95   # 포스트업 PPP 0.95+ → 양호
    spot_up_ppp_good: float = 1.05   # 스팟업 PPP 1.05+ → 양호
    pass_assist_ratio_good: float = 0.30  # 패스→어시스트 전환 30%+ → 양호
    transition_frequency_good: float = 0.20  # 전환 빈도 20%+ → 양호
    ppp_gap_warning: float = 0.15    # 전환-하프코트 PPP 갭 0.15+ → 권장 전환 증가
    diversity_index_good: float = 0.60  # 플레이 다양성 지수 0.60+ → 양호 (Shannon 기반)


# =============================================================================
# TacticalFeedbackGenerator 클래스
# =============================================================================
class TacticalFeedbackGenerator:
    """
    공격 전술 피드백 생성기.

    TacticalAnalysisResult를 입력받아 픽앤롤, 속공, 세트 플레이,
    패싱 네트워크, 전환 공격 등의 전술 피드백을 생성합니다.

    17개 분석 카테고리:
     1. 픽앤롤 효율
     2. 속공 효율
     3. 세트 플레이 효율
     4. 볼 무브먼트 / 패싱 네트워크
     5. 플레이 유형별 효율
     6. 전환 공격 효율
     7. PnR 핸들러 vs 롤러 분할
     8. 속공 빈도율
     9. 전환 vs 하프코트 PPP 갭
    10. 아이솔레이션 효율
    11. 포스트업 효율
    12. 스팟업 / 캐치앤슛 효율
    13. 패스 → 어시스트 비율
    14. 탑 패서 연결
    15. 오펜시브 레이팅 개요
    16. 플레이 유형 다양성 지수
    17. 최고 / 최저 플레이 비교
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: TacticalFeedbackConfig | None = None) -> None:
        self._config: TacticalFeedbackConfig = config or TacticalFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "TacticalFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def generate(
        self,
        analysis: TacticalAnalysisResult,
    ) -> list[FeedbackItem]:
        """
        전술 분석 결과에서 피드백 항목 목록 생성.

        Args:
            analysis: Phase 3 전술 분석 종합 DTO

        Returns:
            FeedbackItem 목록 (최대 25개)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        # 1. 픽앤롤 효율
        self._analyze_pick_and_roll(analysis, items, cfg)

        # 2. 속공 효율
        self._analyze_fast_break(analysis, items, cfg)

        # 3. 세트 플레이 효율
        self._analyze_set_plays(analysis, items, cfg)

        # 4. 볼 무브먼트 / 패싱 네트워크
        self._analyze_ball_movement(analysis, items, cfg)

        # 5. 플레이 유형별 효율
        self._analyze_play_types(analysis, items)

        # 6. 전환 공격 효율
        self._analyze_transitions(analysis, items, cfg)

        # 7. PnR 핸들러 vs 롤러 분할
        self._analyze_pnr_handler_roller_split(analysis, items)

        # 8. 속공 빈도율
        self._analyze_fast_break_frequency(analysis, items, cfg)

        # 9. 전환 vs 하프코트 PPP 갭
        self._analyze_transition_halfcourt_gap(analysis, items, cfg)

        # 10. 아이솔레이션 효율
        self._analyze_isolation(analysis, items, cfg)

        # 11. 포스트업 효율
        self._analyze_post_up(analysis, items, cfg)

        # 12. 스팟업 / 캐치앤슛 효율
        self._analyze_spot_up(analysis, items, cfg)

        # 13. 패스 → 어시스트 비율
        self._analyze_pass_assist_ratio(analysis, items, cfg)

        # 14. 탑 패서 연결
        self._analyze_top_passer_connection(analysis, items)

        # 15. 오펜시브 레이팅 개요
        self._analyze_offensive_rating(analysis, items)

        # 16. 플레이 유형 다양성 지수
        self._analyze_play_type_diversity(analysis, items, cfg)

        # 17. 최고 / 최저 플레이 비교
        self._analyze_best_worst_play_type(analysis, items)

        # 최대 항목 수 제한
        items = items[: cfg.max_items]

        with self._lock:
            self._total_generated += 1

        return items

    # =========================================================================
    # 1. 픽앤롤 효율
    # =========================================================================
    def _analyze_pick_and_roll(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """픽앤롤 종합 효율 피드백."""
        if analysis.pick_and_roll is None or analysis.pick_and_roll.total_pnr <= 0:
            return
        pnr = analysis.pick_and_roll
        pnr_good = pnr.pnr_ppp >= cfg.pnr_ppp_good
        sev = self._severity_mapper.from_ratio(
            min(pnr.pnr_ppp / 1.2, 1.0),
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if pnr_good else FeedbackType.CORRECTION,
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="픽앤롤 효율",
            description=(
                f"픽앤롤 {pnr.total_pnr}회 실행, PPP {pnr.pnr_ppp:.2f}. "
                + (f"볼핸들러 효율 {pnr.ballhandler_efficiency:.2f}, "
                   f"롤러 효율 {pnr.roller_efficiency:.2f}. "
                   "픽앤롤이 효과적으로 운용되고 있습니다." if pnr_good
                   else "픽앤롤 마무리 효율이 부족합니다. "
                        "수비 대응 패턴을 분석하여 액션을 다양화하세요.")
            ),
            current_value=pnr.pnr_ppp,
            ideal_value=cfg.pnr_ppp_good,
            confidence=0.90,
        ))

    # =========================================================================
    # 2. 속공 효율
    # =========================================================================
    def _analyze_fast_break(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """속공 종합 효율 피드백."""
        if analysis.fast_break is None or analysis.fast_break.total_fast_breaks <= 0:
            return
        fb = analysis.fast_break
        fb_good = fb.fast_break_ppp >= cfg.fast_break_ppp_good
        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=FeedbackType.POSITIVE if fb_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="속공 효율",
            description=(
                f"속공 {fb.total_fast_breaks}회 실행, PPP {fb.fast_break_ppp:.2f}. "
                f"평균 전환 시간 {fb.average_transition_time_seconds:.1f}초. "
                + ("빠른 전환으로 효율적인 득점을 올리고 있습니다." if fb_good
                   else "속공 마무리 정확도를 높이세요.")
            ),
            current_value=fb.fast_break_ppp,
            ideal_value=cfg.fast_break_ppp_good,
            confidence=0.90,
        ))

    # =========================================================================
    # 3. 세트 플레이 효율
    # =========================================================================
    def _analyze_set_plays(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """세트 플레이 종합 효율 피드백."""
        if analysis.set_plays is None or analysis.set_plays.total_set_plays <= 0:
            return
        sp = analysis.set_plays
        sp_good = sp.set_play_ppp >= cfg.set_play_ppp_good
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if sp_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="세트 플레이 효율",
            description=(
                f"세트 플레이 {sp.total_set_plays}회 실행, PPP {sp.set_play_ppp:.2f}. "
                + (f"주력 플레이: {', '.join(sp.top_plays[:3])}." if sp.top_plays
                   else "")
                + (" 세트 플레이가 잘 운용되고 있습니다." if sp_good
                   else " 세트 플레이 성공률 향상이 필요합니다.")
            ),
            current_value=sp.set_play_ppp,
            ideal_value=cfg.set_play_ppp_good,
            confidence=0.85,
        ))

    # =========================================================================
    # 4. 볼 무브먼트 / 패싱 네트워크
    # =========================================================================
    def _analyze_ball_movement(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """볼 무브먼트 평점 기반 피드백."""
        if analysis.passing_network is None:
            return
        pn = analysis.passing_network
        bm_good = pn.ball_movement_rating >= cfg.ball_movement_good
        sev = self._severity_mapper.from_score(pn.ball_movement_rating)
        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=FeedbackType.POSITIVE if bm_good else FeedbackType.CORRECTION,
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="볼 무브먼트",
            description=(
                f"볼 무브먼트 점수 {pn.ball_movement_rating:.0f}점, "
                f"점유당 평균 {pn.average_passes_per_possession:.1f}회 패스. "
                + ("팀 패싱이 원활하게 이루어지고 있습니다." if bm_good
                   else "패스 횟수가 적어 개인 플레이에 의존하고 있습니다.")
            ),
            current_value=pn.ball_movement_rating,
            ideal_value=cfg.ball_movement_good,
            confidence=0.85,
        ))

    # =========================================================================
    # 5. 플레이 유형별 효율
    # =========================================================================
    def _analyze_play_types(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
    ) -> None:
        """플레이 유형별 PPP 기반 효율 피드백."""
        for pt_data in analysis.play_types[:5]:
            if pt_data.frequency <= 0:
                continue
            sev = self._severity_mapper.from_ratio(
                min(pt_data.ppp / 1.2, 1.0),
            )
            fb_type = (FeedbackType.POSITIVE
                       if sev.severity.is_positive else FeedbackType.CORRECTION)
            desc = self._templates.format_tactical_pattern(
                "strength" if sev.severity.is_positive else "weakness",
                tactic_name=pt_data.play_type.value,
                value=pt_data.ppp,
                unit=" PPP",
            )
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=fb_type,
                priority=FeedbackFormatter.severity_to_priority(sev.severity),
                title=f"{pt_data.play_type.value} 효율",
                description=(
                    desc if desc
                    else f"{pt_data.play_type.value}: {pt_data.ppp:.2f} PPP "
                         f"({pt_data.frequency}회, FG% {pt_data.fg_pct:.1f}%)"
                ),
                current_value=pt_data.ppp,
                confidence=0.85,
            ))

    # =========================================================================
    # 6. 전환 공격 효율
    # =========================================================================
    def _analyze_transitions(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """전환 공격 PPP 기반 피드백."""
        if analysis.transitions is None:
            return
        trans = analysis.transitions
        trans_good = trans.transition_ppp >= cfg.transition_ppp_good
        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=FeedbackType.POSITIVE if trans_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="전환 공격 효율",
            description=(
                f"전환 공격 PPP {trans.transition_ppp:.2f} "
                f"(하프코트 PPP {trans.halfcourt_ppp:.2f}). "
                + ("전환 공격이 하프코트보다 효율적으로 작동합니다." if trans_good
                   else "전환 공격 마무리 개선이 필요합니다.")
            ),
            current_value=trans.transition_ppp,
            ideal_value=cfg.transition_ppp_good,
            confidence=0.85,
        ))

    # =========================================================================
    # 7. PnR 핸들러 vs 롤러 분할
    # =========================================================================
    def _analyze_pnr_handler_roller_split(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
    ) -> None:
        """픽앤롤 볼핸들러/롤러/팝 효율 분할 피드백."""
        if analysis.pick_and_roll is None or analysis.pick_and_roll.total_pnr <= 0:
            return
        pnr = analysis.pick_and_roll
        handler_eff = pnr.ballhandler_efficiency
        roller_eff = pnr.roller_efficiency
        pop_eff = pnr.pop_efficiency

        # 핸들러와 롤러 효율 차이 분석
        gap = abs(handler_eff - roller_eff)
        dominant = "볼핸들러" if handler_eff >= roller_eff else "롤러"
        weaker = "롤러" if handler_eff >= roller_eff else "볼핸들러"
        weaker_eff = min(handler_eff, roller_eff)

        # 팝 효율이 0보다 큰 경우 포함
        pop_desc = ""
        if pop_eff > 0.0:
            pop_desc = f" 팝 효율 {pop_eff:.2f}."

        if gap < 0.15:
            # 균형적
            fb_type = FeedbackType.POSITIVE
            desc = (
                f"핸들러 효율 {handler_eff:.2f}, 롤러 효율 {roller_eff:.2f}로 "
                f"균형 잡힌 픽앤롤 운용입니다.{pop_desc}"
            )
        else:
            # 불균형
            fb_type = FeedbackType.CORRECTION
            desc = (
                f"핸들러 효율 {handler_eff:.2f}, 롤러 효율 {roller_eff:.2f}로 "
                f"{dominant} 의존도가 높습니다. {weaker} 마무리 옵션을 "
                f"강화하세요.{pop_desc}"
            )

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=fb_type,
            priority=FeedbackPriority.MEDIUM,
            title="PnR 핸들러/롤러 분할",
            description=desc,
            current_value=weaker_eff,
            confidence=0.85,
        ))

    # =========================================================================
    # 8. 속공 빈도율
    # =========================================================================
    def _analyze_fast_break_frequency(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """속공 빈도율 (전체 점유 대비) 피드백."""
        if analysis.transitions is None:
            return
        trans = analysis.transitions
        freq = trans.transition_frequency
        if freq <= 0.0:
            return

        freq_good = freq >= cfg.transition_frequency_good
        freq_pct = freq * 100.0

        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=FeedbackType.POSITIVE if freq_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.LOW if freq_good else FeedbackPriority.MEDIUM,
            title="속공 빈도율",
            description=(
                f"전체 점유 중 전환 공격 빈도 {freq_pct:.1f}%. "
                + (f"적극적인 전환 공격으로 빠른 득점 기회를 만들고 있습니다."
                   if freq_good
                   else f"전환 공격 빈도가 낮습니다(목표 {cfg.transition_frequency_good * 100:.0f}%+). "
                        "리바운드 후 빠른 아웃렛 패스를 통해 속공 기회를 늘리세요.")
            ),
            current_value=freq,
            ideal_value=cfg.transition_frequency_good,
            confidence=0.80,
        ))

    # =========================================================================
    # 9. 전환 vs 하프코트 PPP 갭
    # =========================================================================
    def _analyze_transition_halfcourt_gap(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """전환 공격 PPP와 하프코트 PPP 간 격차 분석 피드백."""
        if analysis.transitions is None:
            return
        trans = analysis.transitions
        # 전환 또는 하프코트 PPP가 0이면 유의미한 비교 불가
        if trans.transition_ppp <= 0.0 and trans.halfcourt_ppp <= 0.0:
            return

        gap = trans.transition_ppp - trans.halfcourt_ppp

        if gap >= cfg.ppp_gap_warning:
            # 전환이 하프코트보다 확실히 좋음 → 전환 증가 권장
            fb_type = FeedbackType.POSITIVE
            desc = (
                f"전환 공격 PPP({trans.transition_ppp:.2f})가 "
                f"하프코트 PPP({trans.halfcourt_ppp:.2f})보다 {gap:.2f} 높습니다. "
                "전환 공격 기회를 늘려 득점 효율을 극대화하세요."
            )
            priority = FeedbackPriority.MEDIUM
        elif gap <= -cfg.ppp_gap_warning:
            # 하프코트가 전환보다 좋음 → 하프코트 유지
            fb_type = FeedbackType.CORRECTION
            desc = (
                f"하프코트 PPP({trans.halfcourt_ppp:.2f})가 "
                f"전환 PPP({trans.transition_ppp:.2f})보다 {abs(gap):.2f} 높습니다. "
                "전환 공격 마무리 개선 또는 하프코트 셋업 활용을 늘리세요."
            )
            priority = FeedbackPriority.MEDIUM
        else:
            # 균형적
            fb_type = FeedbackType.POSITIVE
            desc = (
                f"전환 PPP({trans.transition_ppp:.2f})와 "
                f"하프코트 PPP({trans.halfcourt_ppp:.2f})가 균형적입니다. "
                "공격 상황에 따라 유연하게 운용하세요."
            )
            priority = FeedbackPriority.LOW

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=fb_type,
            priority=priority,
            title="전환 vs 하프코트 PPP 갭",
            description=desc,
            current_value=gap,
            confidence=0.80,
        ))

    # =========================================================================
    # 10. 아이솔레이션 효율
    # =========================================================================
    def _analyze_isolation(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """아이솔레이션 플레이 전용 심화 피드백."""
        iso = self._find_play_type(analysis, "isolation")
        if iso is None or iso.frequency <= 0:
            return

        iso_good = iso.ppp >= cfg.isolation_ppp_good
        to_desc = ""
        if iso.turnover_rate > 0.0:
            to_desc = f" 턴오버율 {iso.turnover_rate * 100:.1f}%."

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if iso_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="아이솔레이션 효율",
            description=(
                f"아이솔레이션 {iso.frequency}회, PPP {iso.ppp:.2f}, "
                f"FG% {iso.fg_pct:.1f}%.{to_desc} "
                + ("1대1 상황에서 효율적인 득점을 보이고 있습니다." if iso_good
                   else "아이솔레이션 효율이 낮습니다. 킥아웃이나 픽 활용으로 "
                        "수비 압박을 분산시키는 것을 권장합니다.")
            ),
            current_value=iso.ppp,
            ideal_value=cfg.isolation_ppp_good,
            confidence=0.85,
        ))

    # =========================================================================
    # 11. 포스트업 효율
    # =========================================================================
    def _analyze_post_up(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """포스트업 플레이 전용 심화 피드백."""
        post = self._find_play_type(analysis, "post_up")
        if post is None or post.frequency <= 0:
            return

        post_good = post.ppp >= cfg.post_up_ppp_good
        foul_desc = ""
        if post.foul_drawn_rate > 0.0:
            foul_desc = f" 파울 유도율 {post.foul_drawn_rate * 100:.1f}%."

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if post_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="포스트업 효율",
            description=(
                f"포스트업 {post.frequency}회, PPP {post.ppp:.2f}, "
                f"FG% {post.fg_pct:.1f}%.{foul_desc} "
                + ("포스트 공격이 효과적으로 이루어지고 있습니다." if post_good
                   else "포스트업 효율이 낮습니다. 더블팀 대응 킥아웃이나 "
                        "페이크 활용으로 마무리 효율을 높이세요.")
            ),
            current_value=post.ppp,
            ideal_value=cfg.post_up_ppp_good,
            confidence=0.85,
        ))

    # =========================================================================
    # 12. 스팟업 / 캐치앤슛 효율
    # =========================================================================
    def _analyze_spot_up(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """스팟업 (캐치앤슛) 플레이 전용 심화 피드백."""
        spot = self._find_play_type(analysis, "spot_up")
        if spot is None or spot.frequency <= 0:
            return

        spot_good = spot.ppp >= cfg.spot_up_ppp_good

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if spot_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="스팟업/캐치앤슛 효율",
            description=(
                f"스팟업 {spot.frequency}회, PPP {spot.ppp:.2f}, "
                f"FG% {spot.fg_pct:.1f}%. "
                + ("캐치앤슛 상황에서 안정적인 슈팅을 보이고 있습니다." if spot_good
                   else "캐치앤슛 효율이 낮습니다. 슈팅 준비 자세와 "
                        "볼을 받기 전 발 세팅을 점검하세요.")
            ),
            current_value=spot.ppp,
            ideal_value=cfg.spot_up_ppp_good,
            confidence=0.85,
        ))

    # =========================================================================
    # 13. 패스 → 어시스트 비율
    # =========================================================================
    def _analyze_pass_assist_ratio(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """패싱 네트워크에서 패스 → 어시스트 전환 비율 피드백."""
        if analysis.passing_network is None:
            return
        pn = analysis.passing_network
        if not pn.connections:
            return

        total_passes = sum(c.count for c in pn.connections)
        if total_passes <= 0:
            return

        # 어시스트 건수 추정: 각 연결의 (횟수 × 어시스트 비율) 합산
        total_assists = sum(c.count * c.assist_rate for c in pn.connections)
        assist_ratio = total_assists / total_passes

        ratio_good = assist_ratio >= cfg.pass_assist_ratio_good

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if ratio_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="패스→어시스트 전환율",
            description=(
                f"총 {total_passes}회 패스 중 약 {total_assists:.0f}회 어시스트 "
                f"(전환율 {assist_ratio * 100:.1f}%). "
                + ("패스가 효과적으로 득점으로 연결되고 있습니다." if ratio_good
                   else "패스가 득점으로 이어지는 비율이 낮습니다. "
                        "슛 레디 상태의 동료에게 정확한 패스를 제공하세요.")
            ),
            current_value=assist_ratio,
            ideal_value=cfg.pass_assist_ratio_good,
            confidence=0.80,
        ))

    # =========================================================================
    # 14. 탑 패서 연결
    # =========================================================================
    def _analyze_top_passer_connection(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
    ) -> None:
        """패싱 네트워크에서 가장 생산적인 패싱 연결 피드백."""
        if analysis.passing_network is None:
            return
        pn = analysis.passing_network
        if not pn.connections:
            return

        # 어시스트 기여도 기준 정렬 (count × assist_rate)
        sorted_conns = sorted(
            pn.connections,
            key=lambda c: c.count * c.assist_rate,
            reverse=True,
        )
        top = sorted_conns[0]
        productivity = top.count * top.assist_rate

        if productivity <= 0.0:
            return

        # 세컨드 어시스트(하키 어시스트) 정보 부가
        hockey_desc = ""
        if pn.hockey_assists > 0:
            hockey_desc = f" 세컨드 어시스트(하키 어시스트) {pn.hockey_assists}회."

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE,
            priority=FeedbackPriority.LOW,
            title="탑 패서 연결",
            description=(
                f"선수 #{top.from_tracking_id} → #{top.to_tracking_id} 연결이 "
                f"가장 생산적입니다 (패스 {top.count}회, 어시스트율 "
                f"{top.assist_rate * 100:.0f}%).{hockey_desc} "
                "이 연결을 전술적으로 적극 활용하세요."
            ),
            current_value=productivity,
            confidence=0.75,
        ))

    # =========================================================================
    # 15. 오펜시브 레이팅 개요
    # =========================================================================
    def _analyze_offensive_rating(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
    ) -> None:
        """라인업 데이터로부터 팀 오펜시브 레이팅 산출 피드백."""
        if not analysis.lineups:
            return

        # 점유 가중 평균 오펜시브 레이팅 산출
        total_poss = sum(lu.possessions for lu in analysis.lineups)
        if total_poss <= 0:
            return

        weighted_ortg = sum(
            lu.offensive_rating * lu.possessions for lu in analysis.lineups
        ) / total_poss

        # NBA 평균 ORtg 약 110, 좋으면 115+, 나쁘면 105-
        ortg_good = weighted_ortg >= 110.0
        sev = self._severity_mapper.from_score(
            min(max((weighted_ortg - 90.0) * 2.5, 0.0), 100.0),
        )

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if ortg_good else FeedbackType.CORRECTION,
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="오펜시브 레이팅",
            description=(
                f"팀 오펜시브 레이팅 {weighted_ortg:.1f} "
                f"(100 점유 기준, {len(analysis.lineups)}개 라인업 가중 평균). "
                + ("리그 평균 이상의 공격 효율을 기록하고 있습니다." if ortg_good
                   else "공격 효율이 리그 평균 이하입니다. "
                        "턴오버 감소와 슛 선택 개선이 필요합니다.")
            ),
            current_value=weighted_ortg,
            ideal_value=110.0,
            confidence=0.80,
        ))

    # =========================================================================
    # 16. 플레이 유형 다양성 지수
    # =========================================================================
    def _analyze_play_type_diversity(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
        cfg: TacticalFeedbackConfig,
    ) -> None:
        """Shannon 엔트로피 기반 플레이 다양성 지수 피드백."""
        active_plays = [pt for pt in analysis.play_types if pt.frequency > 0]
        if len(active_plays) < 2:
            return

        total_freq = sum(pt.frequency for pt in active_plays)
        if total_freq <= 0:
            return

        # Shannon 엔트로피 계산 → 정규화 (0~1)
        entropy = 0.0
        for pt in active_plays:
            p = pt.frequency / total_freq
            if p > 0.0:
                entropy -= p * math.log2(p)

        max_entropy = math.log2(len(active_plays))
        diversity_index = entropy / max_entropy if max_entropy > 0.0 else 0.0

        diverse = diversity_index >= cfg.diversity_index_good

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if diverse else FeedbackType.CORRECTION,
            priority=FeedbackPriority.LOW if diverse else FeedbackPriority.MEDIUM,
            title="플레이 다양성 지수",
            description=(
                f"플레이 유형 다양성 지수 {diversity_index:.2f} "
                f"({len(active_plays)}개 유형 운용). "
                + ("다양한 공격 옵션을 활용하여 수비 예측을 어렵게 만들고 있습니다."
                   if diverse
                   else "특정 플레이 유형에 편중되어 있습니다. "
                        "다양한 공격 패턴을 활용하여 수비 대응을 분산시키세요.")
            ),
            current_value=diversity_index,
            ideal_value=cfg.diversity_index_good,
            confidence=0.80,
        ))

    # =========================================================================
    # 17. 최고 / 최저 플레이 비교
    # =========================================================================
    def _analyze_best_worst_play_type(
        self,
        analysis: TacticalAnalysisResult,
        items: list[FeedbackItem],
    ) -> None:
        """PPP 기준 최고 효율 / 최저 효율 플레이 비교 피드백."""
        active_plays = [pt for pt in analysis.play_types if pt.frequency > 0]
        if len(active_plays) < 2:
            return

        sorted_by_ppp = sorted(active_plays, key=lambda pt: pt.ppp, reverse=True)
        best = sorted_by_ppp[0]
        worst = sorted_by_ppp[-1]

        ppp_gap = best.ppp - worst.ppp
        if ppp_gap < 0.01:
            # 모든 플레이 효율이 거의 동일하면 스킵
            return

        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.CORRECTION if ppp_gap >= 0.30 else FeedbackType.POSITIVE,
            priority=FeedbackPriority.MEDIUM if ppp_gap >= 0.30 else FeedbackPriority.LOW,
            title="최고/최저 플레이 비교",
            description=(
                f"최고 효율: {best.play_type.value}({best.ppp:.2f} PPP, "
                f"{best.frequency}회), "
                f"최저 효율: {worst.play_type.value}({worst.ppp:.2f} PPP, "
                f"{worst.frequency}회). "
                f"효율 격차 {ppp_gap:.2f}. "
                + (f"{worst.play_type.value} 플레이의 마무리 효율을 집중 개선하거나 "
                   f"{best.play_type.value} 활용 빈도를 높이세요."
                   if ppp_gap >= 0.30
                   else "플레이 유형 간 효율 편차가 작아 균형적인 공격을 운용하고 있습니다.")
            ),
            current_value=ppp_gap,
            confidence=0.80,
        ))

    # =========================================================================
    # 유틸리티
    # =========================================================================
    @staticmethod
    def _find_play_type(
        analysis: TacticalAnalysisResult,
        play_type_value: str,
    ) -> object | None:
        """play_types 목록에서 특정 play_type.value에 해당하는 PlayTypeData 반환."""
        for pt in analysis.play_types:
            if pt.play_type.value == play_type_value:
                return pt
        return None

    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"TacticalFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "TacticalFeedbackGenerator",
    "TacticalFeedbackConfig",
]

__version__ = "1.0.0"
