# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: opponent_tendency_feedback.py
설명: 상대팀 경향성 분석 피드백 생성기.
      - 상대 공격 패턴 식별, 수비 취약점 분석, 착취 가능한 플레이 유형,
        상황별 취약 구간 도출
      - TacticalAnalysisResult → FeedbackItem 변환

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
    DefenseAnalysis,
    PlayTypeData,
    SituationSplitData,
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
class OpponentTendencyFeedbackConfig:
    """상대팀 경향성 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # PPP 임계치
    weakness_threshold_ppp: float = 0.85    # 이하 → 상대 취약 플레이 유형
    strength_threshold_ppp: float = 1.15    # 이상 → 상대 강점 플레이 유형

    # 수비 효율 임계치
    drtg_weak_threshold: float = 110.0      # DRtg 110 이상 → 수비 취약
    drtg_strong_threshold: float = 100.0    # DRtg 100 이하 → 수비 강점

    # 상대 FG% 임계치
    opponent_fg_weak: float = 50.0          # 허용 FG% 50 초과 → 수비 취약
    opponent_fg_strong: float = 42.0        # 허용 FG% 42 이하 → 수비 강점

    # 상황별 네트레이팅 취약 임계치
    situation_net_weak: float = -5.0        # 넷레이팅 -5 이하 → 취약 상황

    # 최소 빈도 (플레이 유형 피드백 생성 기준)
    min_play_frequency: int = 3

    # 컨테스트율 임계치
    low_contest_rate: float = 0.45          # 45% 미만 → 오픈 슛 허용 경향


# =============================================================================
# OpponentTendencyFeedbackGenerator 클래스
# =============================================================================
class OpponentTendencyFeedbackGenerator:
    """
    상대팀 경향성 분석 피드백 생성기.

    TacticalAnalysisResult를 입력받아 상대팀의 공격 패턴, 수비 취약점,
    착취 가능한 플레이 유형, 상황별 취약 구간을 분석하여
    전략적 피드백을 생성합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: OpponentTendencyFeedbackConfig | None = None) -> None:
        self._config: OpponentTendencyFeedbackConfig = config or OpponentTendencyFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "OpponentTendencyFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def generate(
        self,
        analysis: TacticalAnalysisResult,
    ) -> list[FeedbackItem]:
        """
        전술 분석 결과에서 상대팀 경향성 피드백 생성.

        Args:
            analysis: Phase 3 전술 분석 종합 DTO

        Returns:
            FeedbackItem 목록
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        # 1. 상대 수비 스킴 및 전반적 수비 효율 분석
        if analysis.defense is not None:
            items.extend(self._analyze_defense(analysis.defense, cfg))

        # 2. 플레이 유형별 취약/강점 분석
        if analysis.play_types:
            items.extend(self._analyze_play_types(analysis.play_types, cfg))

        # 3. 상황별 취약 구간 분석
        if analysis.situation_splits:
            items.extend(self._analyze_situation_splits(analysis.situation_splits, cfg))

        # 4. 픽앤롤 수비 대응 패턴 분석
        if analysis.pick_and_roll is not None and analysis.pick_and_roll.total_pnr > 0:
            items.extend(self._analyze_pnr_defense_response(analysis, cfg))

        # 5. 속공 허용 패턴 분석
        if analysis.fast_break is not None and analysis.fast_break.total_fast_breaks > 0:
            items.extend(self._analyze_fast_break_tendency(analysis, cfg))

        # 6. 리바운드 허용 취약점 분석
        if analysis.rebound_analysis is not None:
            items.extend(self._analyze_rebound_vulnerability(analysis, cfg))

        # 7. 패싱 네트워크 기반 공격 루트 분석
        if analysis.passing_network is not None:
            items.extend(self._analyze_passing_network_tendency(analysis, cfg))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 수비 분석
    # -------------------------------------------------------------------------
    def _analyze_defense(
        self,
        defense: DefenseAnalysis,
        cfg: OpponentTendencyFeedbackConfig,
    ) -> list[FeedbackItem]:
        """수비 효율 및 스킴 분석."""
        items: list[FeedbackItem] = []

        # 1-1. 팀 수비 효율 평가
        drtg = defense.defensive_rating
        if drtg > 0:
            is_weak = drtg >= cfg.drtg_weak_threshold
            is_strong = drtg <= cfg.drtg_strong_threshold
            # DRtg는 낮을수록 좋음 → 역방향 매핑
            sev = self._severity_mapper.from_ratio_inverse(drtg / 120.0)
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=(
                    FeedbackType.WARNING if is_weak
                    else FeedbackType.POSITIVE if is_strong
                    else FeedbackType.TIP
                ),
                priority=FeedbackFormatter.severity_to_priority(sev.severity),
                title="상대 수비 효율 (DRtg) 경향",
                description=(
                    f"상대팀 수비 효율(DRtg) {drtg:.1f}. "
                    + (
                        "상대 수비가 취약합니다. 적극적인 공격 시도로 고효율 포제션을 창출하세요. "
                        "빠른 전환 공격과 포스트 공격을 통해 수비 압박을 가하세요."
                        if is_weak
                        else
                        "상대 수비가 견고합니다. 고정 공격 패턴을 탈피하고 "
                        "다양한 스크린 전술 및 오프볼 무브먼트로 수비 균형을 무너뜨리세요."
                        if is_strong
                        else
                        "상대 수비가 평균 수준입니다. 수비 약점을 집중 공략하는 세트 플레이를 준비하세요."
                    )
                ),
                current_value=drtg,
                ideal_value=cfg.drtg_strong_threshold,
                unit="DRtg",
                confidence=0.88,
            ))

        # 1-2. 상대 허용 FG% 분석
        opp_fg = defense.opponent_fg_pct
        if opp_fg > 0:
            is_weak_fg = opp_fg >= cfg.opponent_fg_weak
            is_strong_fg = opp_fg <= cfg.opponent_fg_strong
            sev = self._severity_mapper.from_ratio_inverse(opp_fg / 100.0)
            items.append(FeedbackItem(
                category=FeedbackCategory.POWER,
                feedback_type=(
                    FeedbackType.WARNING if is_weak_fg
                    else FeedbackType.POSITIVE if is_strong_fg
                    else FeedbackType.TIP
                ),
                priority=FeedbackFormatter.severity_to_priority(sev.severity),
                title="상대 허용 야투율 경향",
                description=(
                    f"상대팀이 허용하는 야투율 {opp_fg:.1f}%. "
                    f"3점 허용율 {defense.opponent_3pt_pct:.1f}%. "
                    + (
                        "높은 허용 야투율은 수비 압박이 약함을 시사합니다. "
                        "페인트 진입 및 미드레인지 공격을 활성화하세요."
                        if is_weak_fg
                        else
                        "낮은 허용 야투율로 상대 수비가 강합니다. "
                        "파울 유도와 오펜시브 리바운드로 세컨드 찬스를 노리세요."
                        if is_strong_fg
                        else
                        "허용 야투율이 평균 수준입니다. "
                        "3점슛 기회 창출에 집중하여 효율을 높이세요."
                    )
                ),
                current_value=opp_fg,
                ideal_value=cfg.opponent_fg_weak,
                unit="percent",
                confidence=0.88,
            ))

        # 1-3. 컨테스트율 분석 (오픈 슛 허용 경향)
        contest_rate = defense.contested_shot_rate
        if contest_rate > 0:
            is_low_contest = contest_rate < cfg.low_contest_rate
            sev = self._severity_mapper.from_ratio(min(contest_rate, 1.0))
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.WARNING if is_low_contest else FeedbackType.TIP,
                priority=FeedbackPriority.HIGH if is_low_contest else FeedbackPriority.LOW,
                title="상대 슛 컨테스트율 경향",
                description=(
                    f"상대팀 슛 컨테스트율 {contest_rate * 100:.0f}%. "
                    + (
                        f"오픈 슛 허용 빈도가 높습니다 (컨테스트율 {contest_rate * 100:.0f}%). "
                        "3점 라인 주변 공간을 활용한 스페이싱 공격이 유효합니다. "
                        "코너 3점 및 윙 3점 기회를 적극적으로 창출하세요."
                        if is_low_contest
                        else
                        f"상대팀이 {contest_rate * 100:.0f}%의 슛을 컨테스트합니다. "
                        "빠른 볼 무브먼트로 컨테스트 전에 릴리스하거나 "
                        "드라이브 앤 킥으로 오픈 슈터를 찾으세요."
                    )
                ),
                current_value=contest_rate * 100,
                confidence=0.85,
            ))

        # 1-4. 헬프 디펜스 로테이션 취약점
        help_quality = defense.help_rotation_quality
        if help_quality > 0:
            is_weak_help = help_quality < 55.0
            sev = self._severity_mapper.from_score(help_quality)
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.WARNING if is_weak_help else FeedbackType.TIP,
                priority=FeedbackPriority.HIGH if is_weak_help else FeedbackPriority.MEDIUM,
                title="상대 헬프 디펜스 로테이션 취약점",
                description=(
                    f"상대 헬프 디펜스 로테이션 품질 {help_quality:.0f}점. "
                    + (
                        "헬프 디펜스 로테이션이 느립니다. "
                        "드라이브 후 킥아웃 패스, 포스트 더블팀 유도 후 외곽 패스, "
                        "픽앤롤 롤러로의 빠른 전달이 효과적입니다."
                        if is_weak_help
                        else
                        "상대 헬프 디펜스 로테이션이 견고합니다. "
                        "헬프 디펜더를 유인한 뒤 스킵 패스로 약점을 공략하세요."
                    )
                ),
                current_value=help_quality,
                confidence=0.82,
            ))

        # 1-5. 수비 스킴 기반 공략 전술 제안
        scheme = defense.primary_scheme
        scheme_freq = defense.scheme_frequency
        dominant_scheme = (
            max(scheme_freq, key=lambda k: scheme_freq[k])
            if scheme_freq else scheme.value
        )
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title="상대 수비 스킴 공략 방안",
            description=(
                f"상대 주요 수비 스킴: {scheme.value} "
                f"(가장 빈번한 스킴: {dominant_scheme}). "
                + self._get_scheme_attack_tip(scheme.value)
            ),
            suggestion=self._get_scheme_attack_suggestion(scheme.value),
            confidence=0.85,
        ))

        # 1-6. 클로즈아웃 품질 기반 3점 공략 가능성
        closeout = defense.closeout_quality
        if closeout > 0:
            is_slow_closeout = closeout < 55.0
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.WARNING if is_slow_closeout else FeedbackType.TIP,
                priority=FeedbackPriority.HIGH if is_slow_closeout else FeedbackPriority.LOW,
                title="상대 클로즈아웃 대응 경향",
                description=(
                    f"상대 클로즈아웃 품질 {closeout:.0f}점. "
                    + (
                        "클로즈아웃이 느려 3점 슈터에게 여유가 주어집니다. "
                        "스페이싱 공격과 핸드오프 동작 이후 3점 슛 시도가 유효합니다. "
                        "드라이브 시 킥아웃 패스를 받을 슈터를 코너에 배치하세요."
                        if is_slow_closeout
                        else
                        "상대 클로즈아웃이 빠릅니다. "
                        "클로즈아웃 방향을 반대로 이용한 드라이브 진입을 노리세요."
                    )
                ),
                current_value=closeout,
                confidence=0.82,
            ))

        return items

    # -------------------------------------------------------------------------
    # 플레이 유형 분석
    # -------------------------------------------------------------------------
    def _analyze_play_types(
        self,
        play_types: list[PlayTypeData],
        cfg: OpponentTendencyFeedbackConfig,
    ) -> list[FeedbackItem]:
        """플레이 유형별 취약/강점 분석."""
        items: list[FeedbackItem] = []

        # 빈도 기준 필터링 및 정렬
        qualified = [
            pt for pt in play_types
            if pt.frequency >= cfg.min_play_frequency
        ]
        if not qualified:
            return items

        # PPP 기준 취약 플레이 유형 (착취 가능)
        weak_plays = sorted(
            [pt for pt in qualified if pt.ppp <= cfg.weakness_threshold_ppp],
            key=lambda x: x.ppp,
        )
        # PPP 기준 강점 플레이 유형 (경계 필요)
        strong_plays = sorted(
            [pt for pt in qualified if pt.ppp >= cfg.strength_threshold_ppp],
            key=lambda x: x.ppp,
            reverse=True,
        )

        # 취약 플레이 유형 (최대 3개)
        for pt in weak_plays[:3]:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title=f"상대 취약 플레이: {pt.play_type.value}",
                description=(
                    f"상대팀 '{pt.play_type.value}' 플레이 유형에서 "
                    f"PPP {pt.ppp:.2f}, FG% {pt.fg_pct * 100:.1f}%, "
                    f"턴오버율 {pt.turnover_rate * 100:.1f}% ({pt.frequency}회 시도). "
                    f"이 플레이 유형에서 상대는 효율적이지 않습니다. "
                    f"상대가 이 패턴으로 진입 시 집중 수비를 배치하여 "
                    f"낮은 효율의 슛 또는 턴오버를 유도하세요."
                ),
                current_value=pt.ppp,
                ideal_value=cfg.weakness_threshold_ppp,
                unit="PPP",
                confidence=0.85,
            ))

        # 강점 플레이 유형 (최대 3개) — 우리가 경계해야 할 상대 강점
        for pt in strong_plays[:3]:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title=f"상대 강점 플레이 경계: {pt.play_type.value}",
                description=(
                    f"상대팀 '{pt.play_type.value}' 플레이 유형에서 "
                    f"PPP {pt.ppp:.2f}, FG% {pt.fg_pct * 100:.1f}%, "
                    f"파울 유도율 {pt.foul_drawn_rate * 100:.1f}% ({pt.frequency}회 시도). "
                    f"상대의 핵심 공격 무기로 이 패턴에 대한 수비 대응책을 사전에 준비하세요. "
                    f"앤드원 비율 {pt.and_one_rate * 100:.1f}%로 파울 관리도 중요합니다."
                ),
                current_value=pt.ppp,
                ideal_value=cfg.strength_threshold_ppp,
                unit="PPP",
                confidence=0.85,
            ))

        # 턴오버율이 높은 플레이 유형 (수비에서 스틸 기회)
        high_to_plays = sorted(
            [pt for pt in qualified if pt.turnover_rate >= 0.20],
            key=lambda x: x.turnover_rate,
            reverse=True,
        )
        for pt in high_to_plays[:2]:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"상대 턴오버 유발 플레이: {pt.play_type.value}",
                description=(
                    f"상대팀 '{pt.play_type.value}' 패턴에서 "
                    f"턴오버율 {pt.turnover_rate * 100:.1f}% ({pt.frequency}회 시도). "
                    f"이 패턴 진입 시 적극적인 인터셉트 포지셔닝으로 "
                    f"속공 기회를 만들어 낼 수 있습니다."
                ),
                current_value=pt.turnover_rate * 100,
                unit="percent",
                confidence=0.82,
            ))

        return items

    # -------------------------------------------------------------------------
    # 상황별 취약 구간 분석
    # -------------------------------------------------------------------------
    def _analyze_situation_splits(
        self,
        situation_splits: list[SituationSplitData],
        cfg: OpponentTendencyFeedbackConfig,
    ) -> list[FeedbackItem]:
        """상황별 취약 구간 분석."""
        items: list[FeedbackItem] = []

        # 최소 출전 시간 필터 (0분 데이터 제외)
        qualified = [s for s in situation_splits if s.minutes > 0]
        if not qualified:
            return items

        # 넷레이팅 기준 취약 상황 (상대에게 불리한 상황 = 우리에게 유리)
        weak_situations = [
            s for s in qualified
            if s.net_rating <= cfg.situation_net_weak
        ]

        for split in sorted(weak_situations, key=lambda x: x.net_rating)[:4]:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title=f"상대 취약 상황: {split.split_name}",
                description=(
                    f"'{split.split_name}' 상황에서 "
                    f"넷레이팅 {split.net_rating:+.1f} "
                    f"(공격 {split.offensive_rating:.1f} / 수비 {split.defensive_rating:.1f}). "
                    f"출전 시간 {split.minutes:.1f}분, FG% {split.fg_pct * 100:.1f}%, "
                    f"턴오버율 {split.turnover_rate * 100:.1f}%. "
                    f"이 상황에서 상대는 취약합니다. "
                    f"해당 상황을 의도적으로 만들거나 유사 상황이 발생할 경우 "
                    f"공격 강도를 높이세요."
                ),
                current_value=split.net_rating,
                ideal_value=0.0,
                confidence=0.84,
            ))

        # 상대가 강한 상황 (우리가 조심해야 할 구간)
        strong_situations = [
            s for s in qualified
            if s.net_rating >= 8.0
        ]
        for split in sorted(strong_situations, key=lambda x: x.net_rating, reverse=True)[:2]:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title=f"상대 강세 상황 주의: {split.split_name}",
                description=(
                    f"'{split.split_name}' 상황에서 상대 넷레이팅 {split.net_rating:+.1f}. "
                    f"공격 효율 {split.offensive_rating:.1f}, 수비 효율 {split.defensive_rating:.1f}. "
                    f"이 상황에서 상대는 강합니다. "
                    f"볼 점유를 늦추고 안전한 포제션 관리를 통해 "
                    f"상대의 강점이 발휘되는 상황을 최소화하세요."
                ),
                current_value=split.net_rating,
                confidence=0.84,
            ))

        return items

    # -------------------------------------------------------------------------
    # 픽앤롤 수비 대응 패턴
    # -------------------------------------------------------------------------
    def _analyze_pnr_defense_response(
        self,
        analysis: TacticalAnalysisResult,
        cfg: OpponentTendencyFeedbackConfig,
    ) -> list[FeedbackItem]:
        """픽앤롤 수비 대응 패턴 분석."""
        items: list[FeedbackItem] = []
        pnr = analysis.pick_and_roll
        if pnr is None:
            return items

        defense_responses = pnr.defense_responses
        if not defense_responses:
            return items

        # 가장 빈번한 수비 대응 방법
        dominant_response = max(defense_responses, key=lambda k: defense_responses[k])
        dominant_count = defense_responses[dominant_response]
        total_responses = sum(defense_responses.values())
        dominant_pct = (dominant_count / total_responses * 100) if total_responses > 0 else 0.0

        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title="상대 픽앤롤 수비 대응 패턴",
            description=(
                f"상대 픽앤롤 수비 주요 대응: '{dominant_response}' "
                f"({dominant_pct:.0f}%, {dominant_count}/{total_responses}회). "
                + self._get_pnr_counter_tip(dominant_response)
            ),
            suggestion=self._get_pnr_counter_suggestion(dominant_response),
            confidence=0.85,
        ))

        return items

    # -------------------------------------------------------------------------
    # 속공 허용 패턴
    # -------------------------------------------------------------------------
    def _analyze_fast_break_tendency(
        self,
        analysis: TacticalAnalysisResult,
        cfg: OpponentTendencyFeedbackConfig,
    ) -> list[FeedbackItem]:
        """속공 허용 패턴 분석."""
        items: list[FeedbackItem] = []
        fb = analysis.fast_break
        if fb is None:
            return items

        transitions = analysis.transitions
        if transitions is None:
            return items

        # 수비 복귀율 분석
        recovery_rate = transitions.defensive_recovery_rate
        is_weak_recovery = recovery_rate < 0.65

        if is_weak_recovery:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title="상대 수비 복귀율 취약점",
                description=(
                    f"상대 수비 복귀율 {recovery_rate * 100:.0f}%. "
                    f"속공 전환 시 수비 복귀가 늦습니다. "
                    f"리바운드 후 즉각적인 전진 패스 또는 드리블 전환으로 "
                    f"수적 우위 속공 상황을 자주 만들어 내세요. "
                    f"속공 PPP {fb.fast_break_ppp:.2f}, "
                    f"평균 전환 시간 {fb.average_transition_time_seconds:.1f}초."
                ),
                current_value=recovery_rate * 100,
                unit="percent",
                confidence=0.85,
            ))

        # 속공 허용 횟수 대비 우리의 속공 기회
        if fb.total_fast_breaks >= 5:
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title="상대 속공 허용 빈도 분석",
                description=(
                    f"상대팀 총 속공 {fb.total_fast_breaks}회, "
                    f"속공 PPP {fb.fast_break_ppp:.2f}. "
                    + (
                        "속공 빈도가 높은 팀입니다. "
                        "리바운드 후 전환 방어에 집중하고, "
                        "턴오버 이후 빠른 백코트 귀환을 철저히 준비하세요."
                        if fb.total_fast_breaks >= 10
                        else
                        "속공 빈도가 중간 수준입니다. "
                        "속공 전환 방어 준비를 유지하면서 "
                        "리바운드 후 빠른 아웃렛 패스로 역속공 기회를 포착하세요."
                    )
                ),
                current_value=float(fb.total_fast_breaks),
                confidence=0.82,
            ))

        return items

    # -------------------------------------------------------------------------
    # 리바운드 취약점 분석
    # -------------------------------------------------------------------------
    def _analyze_rebound_vulnerability(
        self,
        analysis: TacticalAnalysisResult,
        cfg: OpponentTendencyFeedbackConfig,
    ) -> list[FeedbackItem]:
        """리바운드 전술 취약점 분석."""
        items: list[FeedbackItem] = []
        reb = analysis.rebound_analysis
        if reb is None:
            return items

        total = reb.total_rebounds
        if total == 0:
            return items

        # 공격 리바운드 취약 (박스아웃 부재)
        if reb.box_out_success_rate < 0.55 and reb.box_out_attempts > 0:
            items.append(FeedbackItem(
                category=FeedbackCategory.POWER,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title="상대 박스아웃 취약점",
                description=(
                    f"상대 박스아웃 성공률 {reb.box_out_success_rate * 100:.0f}% "
                    f"({reb.box_out_attempts}회 시도). "
                    f"공격 리바운드 크래시율 {reb.crash_rate * 100:.0f}%. "
                    "상대 박스아웃이 약합니다. "
                    "슛 시도 이후 공격 리바운드 크래시를 적극적으로 시도하여 "
                    f"세컨드 찬스 포인트를 얻으세요. "
                    f"(세컨드 찬스 전환율 {reb.second_chance_conversion_rate * 100:.0f}%)"
                ),
                current_value=reb.box_out_success_rate * 100,
                confidence=0.84,
            ))

        # 속공 전환 후 수비 리바운드 경향
        if reb.fast_break_after_rebound_rate > 0.35:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIMING,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.HIGH,
                title="상대 리바운드 후 속공 전환 경계",
                description=(
                    f"상대팀 수비 리바운드 이후 속공 전환율 "
                    f"{reb.fast_break_after_rebound_rate * 100:.0f}%. "
                    "리바운드 이후 즉각적인 속공 전환이 빠른 팀입니다. "
                    "슛 시도 이후 2~3명이 리바운드 포지셔닝 대신 "
                    "수비 전환 준비를 유지하여 역속공을 방어하세요."
                ),
                current_value=reb.fast_break_after_rebound_rate * 100,
                unit="percent",
                confidence=0.83,
            ))

        return items

    # -------------------------------------------------------------------------
    # 패싱 네트워크 경향 분석
    # -------------------------------------------------------------------------
    def _analyze_passing_network_tendency(
        self,
        analysis: TacticalAnalysisResult,
        cfg: OpponentTendencyFeedbackConfig,
    ) -> list[FeedbackItem]:
        """패싱 네트워크 기반 공격 루트 분석."""
        items: list[FeedbackItem] = []
        pn = analysis.passing_network
        if pn is None:
            return items

        ball_movement = pn.ball_movement_rating
        avg_passes = pn.average_passes_per_possession

        # 볼 무브먼트 평가
        if ball_movement > 0:
            is_high_movement = ball_movement >= 75.0
            is_low_movement = ball_movement < 50.0

            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=(
                    FeedbackType.CORRECTION if is_high_movement
                    else FeedbackType.WARNING if is_low_movement
                    else FeedbackType.TIP
                ),
                priority=(
                    FeedbackPriority.HIGH if is_high_movement
                    else FeedbackPriority.MEDIUM
                ),
                title="상대 볼 무브먼트 경향",
                description=(
                    f"상대 볼 무브먼트 점수 {ball_movement:.0f}점, "
                    f"포제션당 평균 패스 {avg_passes:.1f}회. "
                    + (
                        "볼 무브먼트가 활발한 팀입니다. "
                        "패스 선상에 대한 인터셉트 포지셔닝과 "
                        "볼 이동 경로를 예측한 핸즈업 수비를 강화하세요."
                        if is_high_movement
                        else
                        "볼 무브먼트가 단조롭고 개인 의존도가 높습니다. "
                        "주요 볼 핸들러를 조기에 압박하여 개인 돌파를 차단하고 "
                        "팀 수비 연계로 고립시키세요."
                        if is_low_movement
                        else
                        "볼 무브먼트가 평균 수준입니다. "
                        "패스 흐름을 끊는 기습적 더블팀과 트래핑을 병행하세요."
                    )
                ),
                current_value=ball_movement,
                confidence=0.83,
            ))

        # 주요 패싱 연결 분석
        if pn.connections:
            # 패스 횟수 기준 상위 연결
            top_connections = sorted(
                pn.connections, key=lambda c: c.count, reverse=True
            )[:3]
            if top_connections:
                conn_desc = ", ".join(
                    f"#{c.from_tracking_id}→#{c.to_tracking_id}({c.count}회)"
                    for c in top_connections
                )
                items.append(FeedbackItem(
                    category=FeedbackCategory.COORDINATION,
                    feedback_type=FeedbackType.TIP,
                    priority=FeedbackPriority.MEDIUM,
                    title="상대 주요 패싱 루트",
                    description=(
                        f"상대팀 주요 패싱 연결: {conn_desc}. "
                        "이 패싱 라인을 차단하면 상대 공격 흐름이 크게 저하됩니다. "
                        "수비 포지셔닝 시 해당 패스 경로를 우선적으로 차단하세요."
                    ),
                    confidence=0.80,
                ))

        return items

    # -------------------------------------------------------------------------
    # 내부 유틸리티: 수비 스킴 공략 팁
    # -------------------------------------------------------------------------
    @staticmethod
    def _get_scheme_attack_tip(scheme_value: str) -> str:
        """수비 스킴별 공략 전술 설명."""
        tips: dict[str, str] = {
            "man_to_man": (
                "맨투맨 수비 대응: 스크린 활용 후 컷, 백도어 컷, 오버로드 전술이 유효합니다. "
                "수비수를 스크린으로 묶은 뒤 오픈 슈터를 찾으세요."
            ),
            "zone_2_3": (
                "2-3존 수비 대응: 하이포스트 점령 및 코너 3점 공략이 핵심입니다. "
                "엘보우 지점에서 패스를 받아 코너 슈터를 찾거나 드라이브로 중앙을 공략하세요."
            ),
            "zone_3_2": (
                "3-2존 수비 대응: 로포스트 및 중앙 페인트 진입이 효과적입니다. "
                "3-2존의 취약점인 하이포스트와 양 사이드 베이스라인 구역을 활용하세요."
            ),
            "zone_1_3_1": (
                "1-3-1존 수비 대응: 코너와 베이스라인 공략이 핵심입니다. "
                "빠른 볼 무브먼트로 미들 라인 수비수를 이동시킨 뒤 코너 오픈 슛을 노리세요."
            ),
            "zone_1_2_2": (
                "1-2-2존 수비 대응: 엘보우 지점과 단거리 미드레인지가 취약합니다. "
                "하이포스트에서 받아 사이드로 드라이브하거나 엘보우 점프슛을 활용하세요."
            ),
            "matchup_zone": (
                "매치업존 수비 대응: 상대의 스위칭 패턴을 파악하고 "
                "불일치(미스매치)가 생기는 순간을 포착하세요. "
                "오프볼 무브먼트로 매치업을 혼란시키는 것이 중요합니다."
            ),
            "full_court_press": (
                "풀코트 프레스 대응: 침착한 볼 핸들링과 빠른 아웃렛 패스가 핵심입니다. "
                "프레스를 돌파하면 수적 우위의 속공 기회가 생깁니다. "
                "장패스 활용과 중간 지역 수신자 배치를 준비하세요."
            ),
            "half_court_press": (
                "하프코트 프레스 대응: 볼 운반 시 사이드라인을 피하고 "
                "중앙 패스 루트를 활용하세요. "
                "프레스 트랩에 걸리지 않도록 세 번째 패스 루트를 항상 준비하세요."
            ),
            "box_and_one": (
                "박스 앤 원 수비 대응: 마크된 핵심 선수의 스크린을 적극 활용하여 "
                "나머지 4인의 존 수비 취약점을 공략하세요. "
                "코너 및 미드레인지 슛을 주된 옵션으로 준비하세요."
            ),
            "triangle_and_two": (
                "트라이앵글 앤 투 수비 대응: 마크된 두 선수가 적극적인 스크린 역할을 맡고 "
                "나머지 3인이 트라이앵글 존 취약점(코너, 엘보우)을 공략하세요."
            ),
        }
        return tips.get(scheme_value, "상대 수비 스킴을 분석하여 취약점을 공략하는 세트 플레이를 준비하세요.")

    @staticmethod
    def _get_scheme_attack_suggestion(scheme_value: str) -> str:
        """수비 스킴별 핵심 전략 제안."""
        suggestions: dict[str, str] = {
            "man_to_man": "스크린-컷 콤보, 백도어 컷, 포스트업 후 킥아웃 패스 활용",
            "zone_2_3": "하이포스트 점령 + 코너 3점 + 엘보우 드라이브",
            "zone_3_2": "로포스트 진입 + 베이스라인 컷 + 하이포스트 경유 공격",
            "zone_1_3_1": "빠른 볼 회전 + 코너 3점 + 베이스라인 플래시",
            "zone_1_2_2": "엘보우 점프슛 + 하이포스트 플래시 + 드라이브 공략",
            "matchup_zone": "오프볼 무브먼트로 미스매치 창출 후 포스트업 또는 픽앤롤",
            "full_court_press": "장패스 + 빠른 아웃렛 + 중간 릴레이어 배치로 압박 돌파",
            "half_court_press": "중앙 공간 활용 + 사이드라인 회피 + 역트랩 역이용",
            "box_and_one": "마크 선수의 스크린 무브 + 4인 패싱으로 존 취약점 공략",
            "triangle_and_two": "마크 2인 스크린 활용 + 3인 패싱 삼각형으로 공략",
        }
        return suggestions.get(scheme_value, "상대 스킴의 약점 구역에 집중적인 패스와 컷으로 공략")

    @staticmethod
    def _get_pnr_counter_tip(response: str) -> str:
        """픽앤롤 수비 대응에 따른 역이용 전술."""
        tips: dict[str, str] = {
            "drop": (
                "드롭 커버리지 시 볼핸들러의 미드레인지 점프슛(엘보우 점퍼)이 유효합니다. "
                "드롭 수비수가 페인트에 물려 있을 때 미드레인지 공간이 열립니다."
            ),
            "switch": (
                "스위치 수비 시 미스매치를 찾아 포스트업을 적극 활용하세요. "
                "큰 선수가 작은 수비수를 마크할 경우 즉시 포스트업으로 전환하세요."
            ),
            "hedge": (
                "헤지 수비 시 롤러(스크리너)의 다이브가 공간이 열립니다. "
                "헤지 나온 수비수를 우회하는 드라이브 또는 롤러로의 즉각 패스를 활용하세요."
            ),
            "trap": (
                "트랩 수비 시 볼핸들러를 향한 더블팀을 역이용하세요. "
                "더블팀이 올 때 사전 약속된 킥아웃 패스로 오픈 슈터를 찾으세요."
            ),
        }
        return tips.get(response, "픽앤롤 수비 대응 패턴을 분석하여 역이용 전술을 준비하세요.")

    @staticmethod
    def _get_pnr_counter_suggestion(response: str) -> str:
        """픽앤롤 수비 대응에 따른 핵심 제안."""
        suggestions: dict[str, str] = {
            "drop": "볼핸들러 미드레인지 점프슛(엘보우) 집중 훈련",
            "switch": "미스매치 발생 즉시 포스트업 전환 약속 플레이 준비",
            "hedge": "롤러 즉각 패스 + 헤지 우회 드라이브 연습",
            "trap": "더블팀 킥아웃 패스 루트 세 가지 이상 준비",
        }
        return suggestions.get(response, "픽앤롤 역이용 플레이를 세트 플레이로 준비")

    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"OpponentTendencyFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "OpponentTendencyFeedbackGenerator",
    "OpponentTendencyFeedbackConfig",
]

__version__ = "1.0.0"
