# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: pace_tempo_feedback.py
설명: 페이스·템포 피드백 생성기.
      - 전환 공격 vs 하프코트 공격 효율 비교 (PPP 기반)
      - 경기 페이스 평가 (전환 빈도, 속공 성공률)
      - 1차·2차 속공 파도 성공률 분석
      - 수비 복귀율 평가 (전환 수비 품질)
      - TransitionData → FeedbackItem 변환

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
from shared.dto.tactical_dto import TransitionData

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class PaceTempoFeedbackConfig:
    """페이스·템포 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # 전환 공격 효율 임계치
    transition_ppp_threshold: float = 1.10      # PPP 1.10 이상 → 양호
    transition_ppp_elite: float = 1.25          # PPP 1.25 이상 → 엘리트
    transition_ppp_poor: float = 0.85           # PPP 0.85 미만 → 부진

    # 하프코트 공격 효율 임계치
    halfcourt_ppp_good: float = 1.00            # PPP 1.00 이상 → 양호
    halfcourt_ppp_elite: float = 1.15           # PPP 1.15 이상 → 엘리트

    # 전환 빈도 임계치 (점유당)
    transition_frequency_high: float = 0.20    # 0.20 이상 → 빠른 팀
    transition_frequency_medium: float = 0.12  # 0.12~0.20 → 혼합
    transition_frequency_low: float = 0.08     # 0.08 미만 → 느린 팀

    # 속공 성공률 임계치
    first_wave_good: float = 0.60              # 1차 속공 성공률 60% 이상 → 양호
    first_wave_elite: float = 0.75             # 75% 이상 → 엘리트
    second_wave_good: float = 0.45            # 2차 속공 성공률 45% 이상 → 양호

    # 수비 복귀율 임계치
    recovery_rate_good: float = 0.75           # 수비 복귀 75% 이상 → 양호
    recovery_rate_elite: float = 0.88          # 88% 이상 → 엘리트
    recovery_rate_poor: float = 0.55           # 55% 미만 → 취약

    # PPP 차이 유의미성 임계치
    ppp_gap_significant: float = 0.15          # 0.15 이상 차이면 유의미


# =============================================================================
# PaceTempoFeedbackGenerator 클래스
# =============================================================================
class PaceTempoFeedbackGenerator:
    """
    페이스·템포 피드백 생성기.

    TransitionData를 입력받아 전환 공격 효율, 속공 성공률,
    하프코트 대비 효율, 수비 복귀율에 대한 페이스 피드백을 생성합니다.

    빠른 템포 팀과 느린 템포 팀 모두에 최적화된 피드백을 제공합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: PaceTempoFeedbackConfig | None = None) -> None:
        self._config: PaceTempoFeedbackConfig = config or PaceTempoFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        """생성기 이름."""
        return "PaceTempoFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        """총 생성 횟수."""
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 피드백 생성
    # -------------------------------------------------------------------------
    def generate(self, transition: TransitionData) -> list[FeedbackItem]:
        """
        전환 공격 데이터에서 페이스·템포 피드백 생성.

        Args:
            transition: 전환 공수 분석 결과 DTO

        Returns:
            FeedbackItem 목록 (전환 효율·페이스·속공·수비 복귀 분석)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        # 1~2: 전환 vs 하프코트 효율 비교
        items.extend(self._analyze_transition_vs_halfcourt(transition, cfg))

        # 3~4: 경기 페이스 평가
        items.extend(self._analyze_pace(transition, cfg))

        # 5~7: 속공 파도 성공률
        items.extend(self._analyze_fast_break_waves(transition, cfg))

        # 8~10: 수비 복귀율
        items.extend(self._analyze_defensive_recovery(transition, cfg))

        # 12: 속공 마무리 효율
        items.extend(self._fast_break_finishing(transition, cfg))

        # 13: 전환 공격 의존도
        items.extend(self._transition_dependency(transition, cfg))

        # 14: 공수 전환 스피드 종합
        items.extend(self._transition_speed_composite(transition, cfg))

        # 15: 전략적 템포 권고
        items.extend(self._strategic_tempo_recommendation(transition, cfg))

        # 16: 전환 공격 종합 평점
        items.append(self._transition_overall_rating(transition, cfg))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 전환 vs 하프코트 효율 비교 (1~2번)
    # -------------------------------------------------------------------------
    def _analyze_transition_vs_halfcourt(
        self,
        t: TransitionData,
        cfg: PaceTempoFeedbackConfig,
    ) -> list[FeedbackItem]:
        """전환 vs 하프코트 PPP 비교 피드백."""
        items: list[FeedbackItem] = []

        # 1. 전환 공격 PPP
        trans_elite = t.transition_ppp >= cfg.transition_ppp_elite
        trans_good = t.transition_ppp >= cfg.transition_ppp_threshold
        trans_poor = t.transition_ppp < cfg.transition_ppp_poor
        sev_trans = self._severity_mapper.from_ratio(t.transition_ppp)
        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=(
                FeedbackType.POSITIVE
                if trans_good
                else (FeedbackType.WARNING if trans_poor else FeedbackType.CORRECTION)
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_trans.severity),
            title="전환 공격 PPP",
            description=(
                f"전환 공격 Points Per Possession(PPP): {t.transition_ppp:.3f}. "
                + (
                    f"PPP {t.transition_ppp:.3f}는 엘리트 수준의 전환 공격 효율입니다. "
                    "빠른 전환으로 높은 퀄리티의 슈팅 기회를 만들고 있습니다."
                    if trans_elite
                    else (
                        f"PPP {t.transition_ppp:.3f}로 전환 공격이 효율적으로 운용됩니다."
                        if trans_good
                        else (
                            f"전환 PPP {t.transition_ppp:.3f}는 매우 낮은 수준입니다. "
                            "속공 마무리 정확도와 슈팅 선택을 전면 점검해야 합니다."
                            if trans_poor
                            else f"전환 PPP {t.transition_ppp:.3f}는 기준치에 미치지 못합니다. "
                                 "속공 마무리 훈련이 필요합니다."
                        )
                    )
                )
            ),
            suggestion=(
                "빠른 볼 업코트와 림 런 선수들의 타이밍 훈련을 강화하세요."
                if not trans_good
                else None
            ),
            current_value=t.transition_ppp,
            ideal_value=cfg.transition_ppp_threshold,
            unit="PPP",
            confidence=0.90,
        ))

        # 2. 하프코트 PPP 및 전환-하프코트 차이
        hc_good = t.halfcourt_ppp >= cfg.halfcourt_ppp_good
        hc_elite = t.halfcourt_ppp >= cfg.halfcourt_ppp_elite
        ppp_gap = t.transition_ppp - t.halfcourt_ppp
        gap_significant = abs(ppp_gap) >= cfg.ppp_gap_significant
        sev_hc = self._severity_mapper.from_ratio(t.halfcourt_ppp)
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE
                if hc_good
                else FeedbackType.CORRECTION
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_hc.severity),
            title="하프코트 PPP 및 전환 대비 효율",
            description=(
                f"하프코트 PPP: {t.halfcourt_ppp:.3f} "
                f"(전환 PPP {t.transition_ppp:.3f}와의 차이: {ppp_gap:+.3f}). "
                + (
                    f"하프코트 세트 오펜스가 엘리트 수준({t.halfcourt_ppp:.3f} PPP)입니다. "
                    "전술적 완성도가 높습니다."
                    if hc_elite
                    else (
                        "하프코트 세트 오펜스가 안정적으로 운용됩니다."
                        if hc_good
                        else "하프코트 세트 오펜스 효율이 낮습니다. "
                             "세트 플레이 다양성과 스페이싱 개선이 필요합니다."
                    )
                )
                + (
                    f" 전환 공격이 하프코트보다 {abs(ppp_gap):.3f} PPP 앞서 "
                    "팀의 강점이 전환 게임에 있음을 보여줍니다."
                    if gap_significant and ppp_gap > 0
                    else (
                        f" 하프코트가 전환보다 {abs(ppp_gap):.3f} PPP 앞서 "
                        "세트 오펜스 중심 팀임을 나타냅니다."
                        if gap_significant and ppp_gap < 0
                        else ""
                    )
                )
            ),
            suggestion=(
                "하프코트 세트 플레이 종류를 늘리고 픽앤롤 마무리 훈련을 추가하세요."
                if not hc_good
                else None
            ),
            current_value=t.halfcourt_ppp,
            ideal_value=cfg.halfcourt_ppp_good,
            unit="PPP",
            confidence=0.88,
        ))

        return items

    # -------------------------------------------------------------------------
    # 경기 페이스 평가 (3~4번)
    # -------------------------------------------------------------------------
    def _analyze_pace(
        self,
        t: TransitionData,
        cfg: PaceTempoFeedbackConfig,
    ) -> list[FeedbackItem]:
        """경기 페이스 평가 피드백."""
        items: list[FeedbackItem] = []
        freq = t.transition_frequency

        # 3. 전환 빈도 (페이스 분류)
        fast_paced = freq >= cfg.transition_frequency_high
        slow_paced = freq < cfg.transition_frequency_low
        mixed = cfg.transition_frequency_low <= freq < cfg.transition_frequency_high
        sev_pace = self._severity_mapper.from_score(
            min(freq / cfg.transition_frequency_high * 100.0, 100.0)
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if fast_paced else
                (FeedbackType.TIP if mixed else FeedbackType.IMPROVEMENT)
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_pace.severity),
            title="경기 페이스 분류",
            description=(
                f"점유당 전환 빈도: {freq:.3f} "
                f"({'고속 페이스' if fast_paced else '혼합 페이스' if mixed else '저속 페이스'}). "
                + (
                    f"전환 빈도 {freq:.3f}는 NBA 평균 상위 25% 수준의 빠른 페이스입니다. "
                    "빠른 템포가 상대 수비 세팅 전에 기회를 만들고 있습니다."
                    if fast_paced
                    else (
                        "균형 잡힌 페이스로 전환과 세트 오펜스를 적절히 혼용합니다."
                        if mixed
                        else "느린 페이스는 세트 오펜스 위주 전략을 의미합니다. "
                             "상대 팀 속도에 맞춰 템포를 조절하는 전략이 필요합니다."
                    )
                )
            ),
            suggestion=(
                "빠른 리바운드 아웃렛 패스와 풀코트 달리기 훈련으로 페이스를 높이세요."
                if slow_paced
                else None
            ),
            current_value=freq,
            ideal_value=cfg.transition_frequency_high,
            unit="빈도/점유",
            confidence=0.85,
        ))

        # 4. 전환 빈도와 효율의 상관 분석
        # 빠른 페이스인데 효율이 낮으면 → 무분별한 속공, 느린 페이스인데 효율이 높으면 → 전술 우수
        if freq > 0:
            pace_efficiency = t.transition_ppp / max(freq, 0.001)
            is_efficient_fast = fast_paced and t.transition_ppp >= cfg.transition_ppp_threshold
            is_reckless_fast = fast_paced and t.transition_ppp < cfg.transition_ppp_poor
            is_quality_slow = slow_paced and t.halfcourt_ppp >= cfg.halfcourt_ppp_elite
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=(
                    FeedbackType.POSITIVE if (is_efficient_fast or is_quality_slow) else
                    (FeedbackType.WARNING if is_reckless_fast else FeedbackType.TIP)
                ),
                priority=(
                    FeedbackPriority.HIGH if is_reckless_fast else FeedbackPriority.MEDIUM
                ),
                title="페이스-효율 상관 분석",
                description=(
                    f"전환 빈도 {freq:.3f}에서 PPP {t.transition_ppp:.3f} 달성 "
                    f"(효율 지수: {pace_efficiency:.2f}). "
                    + (
                        "빠른 페이스에서 높은 효율을 동시에 달성하는 이상적인 상태입니다."
                        if is_efficient_fast
                        else (
                            "빠른 페이스에도 불구하고 전환 효율이 낮습니다. "
                            "속공 선택 기준을 강화하여 무분별한 속공을 줄여야 합니다."
                            if is_reckless_fast
                            else (
                                "느린 페이스에서 하프코트 세트 오펜스를 완벽히 활용합니다."
                                if is_quality_slow
                                else "페이스와 효율 간 균형이 적절한 수준입니다."
                            )
                        )
                    )
                ),
                suggestion=(
                    "속공 기회 판단 기준을 코치와 함께 정의하고, "
                    "수적 우위가 확실할 때만 속공을 실행하도록 훈련하세요."
                    if is_reckless_fast
                    else None
                ),
                current_value=pace_efficiency,
                confidence=0.82,
            ))

        return items

    # -------------------------------------------------------------------------
    # 속공 파도 성공률 (5~7번)
    # -------------------------------------------------------------------------
    def _analyze_fast_break_waves(
        self,
        t: TransitionData,
        cfg: PaceTempoFeedbackConfig,
    ) -> list[FeedbackItem]:
        """속공 1차·2차 파도 성공률 피드백."""
        items: list[FeedbackItem] = []

        # 5. 1차 속공 파도 성공률
        fw_elite = t.first_wave_success_rate >= cfg.first_wave_elite
        fw_good = t.first_wave_success_rate >= cfg.first_wave_good
        sev_fw = self._severity_mapper.from_ratio(t.first_wave_success_rate)
        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=(
                FeedbackType.POSITIVE if fw_good else FeedbackType.CORRECTION
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_fw.severity),
            title="1차 속공 파도 성공률",
            description=(
                f"1차 속공(수비 정렬 전 즉시 공격) 성공률: "
                f"{t.first_wave_success_rate * 100:.1f}%. "
                + (
                    f"1차 속공 {t.first_wave_success_rate * 100:.1f}%는 최상위 수준입니다. "
                    "리바운드 후 즉각적인 전환 능력이 탁월합니다."
                    if fw_elite
                    else (
                        "1차 속공 성공률이 양호합니다. "
                        "빠른 전환으로 고확률 슈팅 기회를 만들고 있습니다."
                        if fw_good
                        else "1차 속공 성공률이 낮습니다. "
                             "리바운드 후 빠른 아웃렛 패스와 림 런 타이밍 훈련이 필요합니다."
                    )
                )
            ),
            suggestion=(
                "리바운드 후 2초 내 아웃렛 패스를 목표로 훈련하세요."
                if not fw_good
                else None
            ),
            current_value=t.first_wave_success_rate * 100.0,
            ideal_value=cfg.first_wave_good * 100.0,
            unit="percent",
            confidence=0.87,
        ))

        # 6. 2차 속공 파도 성공률
        sw_good = t.second_wave_success_rate >= cfg.second_wave_good
        sev_sw = self._severity_mapper.from_ratio(t.second_wave_success_rate)
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if sw_good else FeedbackType.IMPROVEMENT
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_sw.severity),
            title="2차 속공 파도 성공률",
            description=(
                f"2차 속공(수비가 부분 정렬된 상태) 성공률: "
                f"{t.second_wave_success_rate * 100:.1f}%. "
                + (
                    "2차 속공에서도 높은 성공률을 유지합니다. "
                    "중간 단계 전환 공격 실행력이 뛰어납니다."
                    if sw_good
                    else "2차 속공 성공률이 낮습니다. "
                         "수비가 세팅되기 시작할 때의 공격 결정 훈련이 필요합니다."
                )
            ),
            suggestion=(
                "2차 속공에서 빠른 패스 아웃과 코너 3점 옵션을 훈련하세요."
                if not sw_good
                else None
            ),
            current_value=t.second_wave_success_rate * 100.0,
            ideal_value=cfg.second_wave_good * 100.0,
            unit="percent",
            confidence=0.85,
        ))

        # 7. 1차 vs 2차 속공 성공률 차이
        wave_gap = t.first_wave_success_rate - t.second_wave_success_rate
        large_gap = wave_gap > 0.20
        small_gap = wave_gap <= 0.10
        items.append(FeedbackItem(
            category=FeedbackCategory.BODY_ALIGNMENT,
            feedback_type=(
                FeedbackType.POSITIVE if small_gap else
                (FeedbackType.TIP if large_gap else FeedbackType.IMPROVEMENT)
            ),
            priority=FeedbackPriority.LOW,
            title="속공 파도 성공률 격차",
            description=(
                f"1차 vs 2차 속공 성공률 차이: {wave_gap * 100:.1f}%p "
                f"(1차 {t.first_wave_success_rate * 100:.1f}% → "
                f"2차 {t.second_wave_success_rate * 100:.1f}%). "
                + (
                    "1차와 2차 속공 성공률 격차가 작아 전환 공격 전 구간이 일관성 있게 운용됩니다."
                    if small_gap
                    else (
                        f"1차 속공({t.first_wave_success_rate * 100:.1f}%)에 비해 "
                        f"2차 속공({t.second_wave_success_rate * 100:.1f}%)이 급격히 떨어집니다. "
                        "2차 속공 전환 판단력 향상이 필요합니다."
                        if large_gap
                        else "1차·2차 속공 성공률 차이가 정상 범위 내입니다."
                    )
                )
            ),
            current_value=wave_gap * 100.0,
            ideal_value=15.0,
            unit="%p",
            confidence=0.80,
        ))

        return items

    # -------------------------------------------------------------------------
    # 수비 복귀율 분석 (8~10번)
    # -------------------------------------------------------------------------
    def _analyze_defensive_recovery(
        self,
        t: TransitionData,
        cfg: PaceTempoFeedbackConfig,
    ) -> list[FeedbackItem]:
        """수비 복귀율 피드백."""
        items: list[FeedbackItem] = []
        rec = t.defensive_recovery_rate

        # 8. 수비 복귀율 전체
        rec_elite = rec >= cfg.recovery_rate_elite
        rec_good = rec >= cfg.recovery_rate_good
        rec_poor = rec < cfg.recovery_rate_poor
        sev_rec = self._severity_mapper.from_ratio(rec)
        items.append(FeedbackItem(
            category=FeedbackCategory.FOOTWORK,
            feedback_type=(
                FeedbackType.POSITIVE
                if rec_good
                else (FeedbackType.WARNING if rec_poor else FeedbackType.CORRECTION)
            ),
            priority=FeedbackFormatter.severity_to_priority(sev_rec.severity),
            title="수비 복귀율",
            description=(
                f"공격 후 수비 복귀 성공률: {rec * 100:.1f}%. "
                + (
                    f"수비 복귀율 {rec * 100:.1f}%는 최상위 수준입니다. "
                    "공격 후 즉각적인 수비 전환 규율이 탁월합니다."
                    if rec_elite
                    else (
                        "수비 복귀율이 양호합니다. "
                        "상대 속공 허용을 효과적으로 억제하고 있습니다."
                        if rec_good
                        else (
                            f"수비 복귀율 {rec * 100:.1f}%는 위험 수준입니다. "
                            "상대 속공에 무방비로 노출되고 있습니다. "
                            "공격 후 수비 전환 훈련을 최우선으로 강화해야 합니다."
                            if rec_poor
                            else f"수비 복귀율 {rec * 100:.1f}%는 개선이 필요합니다."
                        )
                    )
                )
            ),
            suggestion=(
                "공격 실패 즉시 수비 스프린트를 습관화하는 조건 훈련을 도입하세요."
                if rec_poor
                else (
                    "수비 복귀 속도를 더욱 높이면 상대 1차 속공을 완전히 차단할 수 있습니다."
                    if not rec_good
                    else None
                )
            ),
            current_value=rec * 100.0,
            ideal_value=cfg.recovery_rate_good * 100.0,
            unit="percent",
            confidence=0.90,
        ))

        # 9. 수비 복귀율 vs 상대 속공 허용 위험
        # 복귀율이 낮을수록 상대 1차 속공 허용 위험이 높음
        risk_score = (1.0 - rec) * 100.0
        high_risk = risk_score > 40.0
        items.append(FeedbackItem(
            category=FeedbackCategory.POSTURE,
            feedback_type=(
                FeedbackType.WARNING if high_risk else FeedbackType.POSITIVE
            ),
            priority=(
                FeedbackPriority.HIGH if high_risk else FeedbackPriority.LOW
            ),
            title="속공 허용 위험 지수",
            description=(
                f"속공 허용 위험 지수: {risk_score:.1f}% "
                f"(수비 복귀 실패율 기반). "
                + (
                    f"속공 허용 위험이 {risk_score:.1f}%로 높습니다. "
                    "공격 시 후위 선수들의 수비 준비 자세를 개선해야 합니다."
                    if high_risk
                    else "속공 허용 위험이 낮아 수비 전환이 안정적입니다."
                )
            ),
            suggestion=(
                "공격 중에도 '수비 뒤통수'를 유지하는 1~2명의 수비 보호 선수를 지정하세요."
                if high_risk
                else None
            ),
            current_value=risk_score,
            ideal_value=25.0,
            unit="percent",
            confidence=0.87,
        ))

        # 10. 페이스-수비 복귀 트레이드오프
        # 빠른 페이스 + 낮은 복귀율 = 공격적 전략의 리스크
        freq = t.transition_frequency
        fast_and_risky = (
            freq >= cfg.transition_frequency_high and rec < cfg.recovery_rate_good
        )
        slow_and_safe = (
            freq < cfg.transition_frequency_medium and rec >= cfg.recovery_rate_elite
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.WARNING if fast_and_risky else
                (FeedbackType.POSITIVE if slow_and_safe else FeedbackType.TIP)
            ),
            priority=(
                FeedbackPriority.HIGH if fast_and_risky else FeedbackPriority.LOW
            ),
            title="페이스-수비 균형 평가",
            description=(
                f"전환 빈도 {freq:.3f} vs 수비 복귀율 {rec * 100:.1f}% 균형. "
                + (
                    "빠른 페이스임에도 수비 복귀율이 낮아 상대 속공에 취약합니다. "
                    "공격적 페이스와 수비 책임 간 균형 조정이 필요합니다."
                    if fast_and_risky
                    else (
                        "느린 페이스에서 완벽한 수비 복귀를 유지합니다. "
                        "전술적으로 안정적인 게임 플랜입니다."
                        if slow_and_safe
                        else "페이스와 수비 복귀 간 균형이 적절히 유지되고 있습니다."
                    )
                )
            ),
            suggestion=(
                "빠른 전환 공격 실행 시 수비 커버 선수 1~2명의 역할을 명확히 하세요."
                if fast_and_risky
                else None
            ),
            confidence=0.83,
        ))

        return items

    # -------------------------------------------------------------------------
    # 속공 마무리 효율 (12번)
    # -------------------------------------------------------------------------
    def _fast_break_finishing(
        self,
        t: TransitionData,
        cfg: PaceTempoFeedbackConfig,
    ) -> list[FeedbackItem]:
        """속공 마무리 효율 분석 — 속공 성공률과 PPP 결합."""
        items: list[FeedbackItem] = []

        # 1차·2차 속공 가중 평균 성공률 (1차 60%, 2차 40%)
        weighted_sr = (
            t.first_wave_success_rate * 0.60
            + t.second_wave_success_rate * 0.40
        )
        finishing_quality = weighted_sr * t.transition_ppp
        # 정규화: 0~1 범위 대략 (0.6*1.2 = 0.72 수준이 좋은 편)
        elite_finish = finishing_quality >= 0.65
        good_finish = finishing_quality >= 0.45
        sev = self._severity_mapper.from_ratio(
            min(finishing_quality / 0.72, 1.0)
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=(
                FeedbackType.POSITIVE if good_finish
                else FeedbackType.CORRECTION
            ),
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="속공 마무리 효율",
            description=(
                f"속공 마무리 품질 지수: {finishing_quality:.3f} "
                f"(가중 성공률 {weighted_sr * 100:.1f}% × PPP {t.transition_ppp:.3f}). "
                + (
                    "속공에서 높은 성공률과 높은 득점 효율을 동시에 달성합니다. "
                    "전환 공격의 마무리 능력이 엘리트 수준입니다."
                    if elite_finish
                    else (
                        "속공 마무리 효율이 양호합니다. "
                        "전환 공격에서 안정적인 슈팅 기회를 창출하고 있습니다."
                        if good_finish
                        else "속공 성공률과 PPP가 모두 낮아 마무리 품질 개선이 시급합니다. "
                             "속공 시 슛 선택과 레이업 정확도 훈련을 강화하세요."
                    )
                )
            ),
            suggestion=(
                "속공 마무리 훈련에서 2:1, 3:2 수적 우위 상황 시나리오를 반복 연습하세요."
                if not good_finish
                else None
            ),
            current_value=finishing_quality,
            ideal_value=0.65,
            unit="지수",
            confidence=0.84,
        ))

        return items

    # -------------------------------------------------------------------------
    # 전환 공격 의존도 (13번)
    # -------------------------------------------------------------------------
    def _transition_dependency(
        self,
        t: TransitionData,
        cfg: PaceTempoFeedbackConfig,
    ) -> list[FeedbackItem]:
        """전환 공격 의존도 분석 — 빈도 + 효율 격차 기반."""
        items: list[FeedbackItem] = []
        freq = t.transition_frequency
        ppp_gap = t.transition_ppp - t.halfcourt_ppp

        # 전환 의존도 = 빈도가 높고 전환 PPP >> 하프코트 PPP
        over_reliant = freq >= cfg.transition_frequency_high and ppp_gap >= cfg.ppp_gap_significant
        balanced = not over_reliant and abs(ppp_gap) < cfg.ppp_gap_significant
        halfcourt_reliant = (
            freq < cfg.transition_frequency_low and ppp_gap < -cfg.ppp_gap_significant
        )

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.TIP if over_reliant
                else (
                    FeedbackType.POSITIVE if balanced
                    else (FeedbackType.IMPROVEMENT if halfcourt_reliant else FeedbackType.TIP)
                )
            ),
            priority=(
                FeedbackPriority.HIGH if over_reliant else FeedbackPriority.MEDIUM
            ),
            title="전환 공격 의존도 분석",
            description=(
                f"전환 빈도 {freq:.3f}, PPP 격차(전환-하프코트) {ppp_gap:+.3f}. "
                + (
                    "전환 공격에 과도하게 의존하고 있습니다. "
                    "하프코트 세트 오펜스가 막힐 경우 대안이 부족할 수 있으므로, "
                    "세트 플레이 효율 향상도 병행해야 합니다."
                    if over_reliant
                    else (
                        "전환과 하프코트 공격 간 균형이 잡혀 있습니다. "
                        "상대 전술에 따라 유연하게 게임 플랜을 조정할 수 있는 상태입니다."
                        if balanced
                        else (
                            "하프코트 세트 오펜스 의존도가 높습니다. "
                            "전환 공격 빈도를 높여 다양한 득점 루트를 확보하면 "
                            "상대에게 더 큰 부담을 줄 수 있습니다."
                            if halfcourt_reliant
                            else "공격 스타일이 혼합 형태입니다. "
                                 "전환과 세트 오펜스 비율을 경기 상황에 맞게 조절하세요."
                        )
                    )
                )
            ),
            suggestion=(
                "세트 플레이 패키지(픽앤롤, 아이솔레이션)를 보강하여 전환 차단 시 대안을 확보하세요."
                if over_reliant
                else (
                    "리바운드 후 빠른 아웃렛으로 전환 빈도를 높이세요."
                    if halfcourt_reliant
                    else None
                )
            ),
            current_value=freq,
            confidence=0.82,
        ))

        return items

    # -------------------------------------------------------------------------
    # 공수 전환 스피드 종합 (14번)
    # -------------------------------------------------------------------------
    def _transition_speed_composite(
        self,
        t: TransitionData,
        cfg: PaceTempoFeedbackConfig,
    ) -> list[FeedbackItem]:
        """공수 전환 스피드 종합 — 공격(1차 속공)+수비(복귀율) 양방향."""
        items: list[FeedbackItem] = []

        # 공격 전환 스피드 = 1차 속공 성공률 (빠른 전환일수록 높음)
        # 수비 전환 스피드 = 수비 복귀율
        atk_speed = t.first_wave_success_rate
        def_speed = t.defensive_recovery_rate
        composite = atk_speed * 0.50 + def_speed * 0.50
        score_100 = min(composite / 0.80 * 100.0, 100.0)

        both_good = atk_speed >= cfg.first_wave_good and def_speed >= cfg.recovery_rate_good
        atk_only = atk_speed >= cfg.first_wave_good and def_speed < cfg.recovery_rate_good
        def_only = atk_speed < cfg.first_wave_good and def_speed >= cfg.recovery_rate_good

        sev = self._severity_mapper.from_score(score_100)
        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.POSITIVE if both_good
                else (FeedbackType.IMPROVEMENT if (atk_only or def_only)
                      else FeedbackType.CORRECTION)
            ),
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="공수 전환 스피드 종합",
            description=(
                f"공격 전환력 {atk_speed * 100:.1f}% / "
                f"수비 전환력 {def_speed * 100:.1f}% "
                f"(종합 {score_100:.1f}/100). "
                + (
                    "공수 양방향 전환 스피드가 모두 우수합니다. "
                    "전환 국면에서 상대를 압도할 수 있는 역량을 보유하고 있습니다."
                    if both_good
                    else (
                        "공격 전환은 빠르지만 수비 복귀가 느립니다. "
                        "속공 실패 시 역습에 노출될 위험이 있습니다."
                        if atk_only
                        else (
                            "수비 복귀는 빠르지만 공격 전환이 느립니다. "
                            "리바운드 후 빠른 아웃렛 패스 훈련으로 공격 전환 속도를 높이세요."
                            if def_only
                            else "공수 양방향 전환 스피드 모두 개선이 필요합니다. "
                                 "팀 전체의 체력 훈련과 전환 연습을 강화하세요."
                        )
                    )
                )
            ),
            suggestion=(
                "수비 복귀 스프린트 훈련을 추가하세요."
                if atk_only
                else (
                    "리바운드 후 3초 내 아웃렛 패스를 목표로 설정하세요."
                    if def_only
                    else (
                        "팀 전체 공수 전환 시뮬레이션(5:5 풀코트)을 매 연습 시작에 배치하세요."
                        if not both_good
                        else None
                    )
                )
            ),
            current_value=score_100,
            ideal_value=70.0,
            unit="score",
            confidence=0.83,
        ))

        return items

    # -------------------------------------------------------------------------
    # 전략적 템포 권고 (15번)
    # -------------------------------------------------------------------------
    def _strategic_tempo_recommendation(
        self,
        t: TransitionData,
        cfg: PaceTempoFeedbackConfig,
    ) -> list[FeedbackItem]:
        """전략적 템포 권고 — 모든 지표를 종합한 전략 제안."""
        items: list[FeedbackItem] = []

        # 각 영역 판정
        trans_strong = t.transition_ppp >= cfg.transition_ppp_threshold
        hc_strong = t.halfcourt_ppp >= cfg.halfcourt_ppp_good
        fast_break_strong = t.first_wave_success_rate >= cfg.first_wave_good
        recovery_solid = t.defensive_recovery_rate >= cfg.recovery_rate_good

        strengths = sum([trans_strong, hc_strong, fast_break_strong, recovery_solid])

        # 전략 판정
        if trans_strong and fast_break_strong and recovery_solid:
            strategy = "push_tempo"
            desc_strategy = (
                "전환 공격 효율, 속공 성공률, 수비 복귀율 모두 양호합니다. "
                "적극적으로 빠른 템포를 밀어 상대 수비 세팅 전에 공격하는 전략이 최적입니다."
            )
            suggestion = "매 점유마다 3초 내 전환 공격 가능성을 먼저 확인하는 루틴을 확립하세요."
        elif hc_strong and not trans_strong:
            strategy = "slow_down"
            desc_strategy = (
                "하프코트 세트 오펜스가 강점이나 전환 공격 효율이 낮습니다. "
                "하프코트 세트 플레이를 중심으로 경기를 운용하는 것이 효과적입니다."
            )
            suggestion = "무리한 속공을 자제하고, 하프코트에서 좋은 슈팅 기회를 만드는 데 집중하세요."
        elif trans_strong and not recovery_solid:
            strategy = "selective_push"
            desc_strategy = (
                "전환 공격 효율은 높지만 수비 복귀가 불안정합니다. "
                "수적 우위가 확실한 경우에만 선택적으로 속공을 실행하고, "
                "불확실한 상황에서는 세트 오펜스로 전환하세요."
            )
            suggestion = "속공 실행 기준을 '2명 이상 수적 우위'로 명확하게 설정하세요."
        else:
            strategy = "improve_fundamentals"
            desc_strategy = (
                f"4개 핵심 영역 중 {strengths}개만 양호합니다. "
                "특정 전략을 권고하기보다 전반적인 전환 공수 기본기를 강화해야 합니다."
            )
            suggestion = "전환 공수 기본 훈련(아웃렛 패스, 림런 타이밍, 수비 스프린트)을 우선 실시하세요."

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if strengths >= 3
                else (FeedbackType.TIP if strengths >= 2
                      else FeedbackType.CORRECTION)
            ),
            priority=FeedbackPriority.HIGH,
            title="전략적 템포 권고",
            description=(
                f"전략 유형: {strategy.upper()} "
                f"(강점 {strengths}/4). "
                + desc_strategy
            ),
            suggestion=suggestion,
            confidence=0.85,
        ))

        return items

    # -------------------------------------------------------------------------
    # 전환 공격 종합 평점 (16번)
    # -------------------------------------------------------------------------
    def _transition_overall_rating(
        self,
        t: TransitionData,
        cfg: PaceTempoFeedbackConfig,
    ) -> FeedbackItem:
        """전환 공격 종합 평점 피드백."""
        # 가중 평균 점수 산출 (각 지표 0~100 정규화)
        score_trans_ppp = min(t.transition_ppp / cfg.transition_ppp_elite * 100.0, 100.0)
        score_hc_ppp = min(t.halfcourt_ppp / cfg.halfcourt_ppp_elite * 100.0, 100.0)
        score_fw = min(t.first_wave_success_rate / cfg.first_wave_elite * 100.0, 100.0)
        score_sw = min(t.second_wave_success_rate / cfg.second_wave_good * 100.0, 100.0)
        score_rec = min(t.defensive_recovery_rate / cfg.recovery_rate_elite * 100.0, 100.0)

        # 가중치: 전환 PPP 30%, 하프코트 20%, 1차속공 15%, 2차속공 15%, 수비복귀 20%
        overall = (
            score_trans_ppp * 0.30
            + score_hc_ppp * 0.20
            + score_fw * 0.15
            + score_sw * 0.15
            + score_rec * 0.20
        )
        sev = self._severity_mapper.from_score(overall)
        good = overall >= 65.0

        return FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if good else FeedbackType.CORRECTION
            ),
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="전환·페이스 종합 평점",
            description=(
                f"페이스·템포 종합 점수: {overall:.1f}/100. "
                f"[전환PPP {score_trans_ppp:.0f}점 / "
                f"하프코트 {score_hc_ppp:.0f}점 / "
                f"1차속공 {score_fw:.0f}점 / "
                f"2차속공 {score_sw:.0f}점 / "
                f"수비복귀 {score_rec:.0f}점]. "
                + (
                    f"종합 {overall:.1f}점으로 전반적인 페이스·템포 역량이 우수합니다."
                    if good
                    else f"종합 {overall:.1f}점으로 개선이 필요한 영역이 있습니다. "
                         "점수가 낮은 세부 항목부터 우선적으로 개선하세요."
                )
            ),
            current_value=overall,
            ideal_value=65.0,
            unit="score",
            confidence=0.88,
        )

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        """생성기 상태 초기화."""
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"PaceTempoFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "PaceTempoFeedbackGenerator",
    "PaceTempoFeedbackConfig",
]

__version__ = "1.0.0"
