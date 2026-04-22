# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: game_context_feedback.py
설명: 경기 맥락 인식 피드백 생성기.
      - 가비지타임 감지 및 구간별 유의미성 태그
      - 점수 상황별 퍼포먼스 인식 (리드/추격/접전)
      - 쿼터별 퍼포먼스 변화 추세 감지
      - 득점 가뭄/런 구간 원인 추론
      - 모멘텀 전환 시점 분석
      - GameStats + GameFlowData → FeedbackItem + game_context 태그

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from shared.constants.feedback_constants import FEEDBACK_MIN_DETAIL_POINTS
from shared.dto.feedback_dto import (
    CausalFactor,
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackType,
    VideoClipReference,
)
from shared.constants.player_constants import AgeGroup
from shared.dto.game_dto import GameStats, TeamStats
from shared.dto.tactical_dto import (
    GameFlowData,
    MomentumState,
    ScoringRun,
)

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class GameContextFeedbackConfig:
    """경기 맥락 인식 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # 가비지타임 판별 기준
    garbage_time_lead: int = 20        # 점수차 20점+ && 4쿼터
    garbage_time_quarter: int = 4      # 4쿼터
    garbage_time_remaining_pct: float = 0.25  # 잔여 시간 25% 이하

    # 접전 판별 기준
    close_game_threshold: int = 5      # 점수차 5점 이내
    blowout_threshold: int = 15        # 15점 이상 → 대격차

    # 런 분석 기준
    big_run_points: int = 10           # 10점 이상 런 → 빅런
    drought_duration_sec: float = 240.0  # 4분 이상 무득점 → 가뭄

    # 쿼터 변동 기준
    quarter_drop_threshold: int = 8    # 쿼터간 8점+ 감소 → 급격한 하락
    quarter_surge_threshold: int = 8   # 쿼터간 8점+ 증가 → 급격한 상승


# =============================================================================
# GameContextFeedbackGenerator 클래스
# =============================================================================
class GameContextFeedbackGenerator:
    """
    경기 맥락 인식 피드백 생성기.

    "이 통계가 어떤 상황에서 나온 것인지"를 분석합니다.
    가비지타임, 접전, 런/가뭄, 모멘텀 전환점 등을 구분하여
    맥락 없는 수치를 맥락이 있는 인사이트로 변환합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: GameContextFeedbackConfig | None = None) -> None:
        self._config: GameContextFeedbackConfig = config or GameContextFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "GameContextFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: 피드백 생성
    # -------------------------------------------------------------------------
    def generate(
        self,
        game_stats: GameStats,
        game_flow: GameFlowData,
    ) -> list[FeedbackItem]:
        """
        경기 통계와 흐름 데이터에서 맥락 인식 피드백 생성.

        Args:
            game_stats: 경기 전체 통계
            game_flow: 게임 흐름(런, 모멘텀, 리드 변동) 데이터

        Returns:
            game_context 태그가 포함된 FeedbackItem 목록 (15+)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        team = game_stats.home_team_stats
        if team is None:
            with self._lock:
                self._total_generated += 1
            return items

        # 1~3: 경기 유형 및 점수 상황 분석
        items.extend(self._analyze_game_type(game_stats, team, cfg))

        # 4~6: 가비지타임 감지 및 유의미성 평가
        items.extend(self._analyze_garbage_time(game_stats, team, cfg))

        # 7~9: 쿼터별 퍼포먼스 추세
        items.extend(self._analyze_quarter_trends(team, cfg))

        # 10~12: 스코어링 런/가뭄 분석
        items.extend(self._analyze_scoring_runs(game_flow, cfg))

        # 13~14: 모멘텀 전환 분석
        items.extend(self._analyze_momentum(game_flow, cfg))

        # 15~16: 경기 종합 맥락 평가
        items.extend(self._overall_context_assessment(game_stats, game_flow, team, cfg))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 경기 유형 및 점수 상황 (1~3)
    # -------------------------------------------------------------------------
    def _analyze_game_type(
        self,
        gs: GameStats,
        team: TeamStats,
        cfg: GameContextFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        diff = gs.home_score - gs.away_score
        abs_diff = abs(diff)
        won = diff > 0

        # 1. 경기 결과 맥락
        close_game = abs_diff <= cfg.close_game_threshold
        blowout = abs_diff >= cfg.blowout_threshold

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if won else FeedbackType.CORRECTION
            ),
            priority=FeedbackPriority.HIGH,
            title="경기 결과 맥락 분석",
            description=(
                f"최종 스코어 {gs.home_score}:{gs.away_score} "
                f"({'승리' if won else '패배'}, 점수차 {abs_diff}점) — "
                + (
                    "접전에서의 승리입니다. 클러치 상황에서의 실행력이 돋보입니다."
                    if close_game and won
                    else (
                        "접전에서의 패배입니다. 마지막 5분의 결정적 장면을 되돌아보세요."
                        if close_game and not won
                        else (
                            "대격차 승리입니다. 경기 전반에 걸쳐 압도적이었습니다."
                            if blowout and won
                            else (
                                "대격차 패배입니다. 경기 초반부터 주도권을 빼앗겼습니다."
                                if blowout and not won
                                else f"{'승리' if won else '패배'}로 마무리했습니다."
                            )
                        )
                    )
                )
            ),
            game_context="close_game" if close_game else ("blowout" if blowout else "normal"),
            current_value=float(abs_diff),
            confidence=0.95,
        ))

        # 2. 최대 리드 분석 — 흐름 변화 맥락
        max_lead_home = gs.largest_lead_home
        max_lead_away = gs.largest_lead_away
        our_max = max_lead_home if team.is_home else max_lead_away
        opp_max = max_lead_away if team.is_home else max_lead_home

        lost_big_lead = our_max >= 15 and not won
        causes_lead: list[CausalFactor] = []
        if lost_big_lead:
            causes_lead.append(CausalFactor(
                factor="대량 리드 붕괴",
                impact=0.9,
                evidence=f"최대 {our_max}점 리드에서 역전패 — 집중력 또는 체력 저하",
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.WARNING if lost_big_lead
                else FeedbackType.POSITIVE
            ),
            priority=(
                FeedbackPriority.CRITICAL if lost_big_lead
                else FeedbackPriority.LOW
            ),
            title="최대 리드 변동 맥락",
            description=(
                f"아군 최대 리드 {our_max}점 / 상대 최대 리드 {opp_max}점 — "
                + (
                    f"최대 {our_max}점 리드를 잡았으나 역전당했습니다. "
                    "리드 상황에서의 경기 관리(템포 조절, 타임아웃 활용)를 점검하세요."
                    if lost_big_lead
                    else (
                        f"최대 {our_max}점 리드로 경기를 안정적으로 마무리했습니다."
                        if won
                        else f"상대가 최대 {opp_max}점까지 벌렸습니다."
                    )
                )
            ),
            causal_factors=causes_lead,
            game_context="lead_collapse" if lost_big_lead else "normal",
            confidence=0.90,
        ))

        # 3. 리드 교체 빈도 — 경기 경쟁도 맥락
        lc = gs.lead_changes
        ties = gs.ties
        very_competitive = lc >= 10 and ties >= 6

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.TIP if very_competitive
                else FeedbackType.POSITIVE
            ),
            priority=FeedbackPriority.MEDIUM,
            title="경기 경쟁도 맥락",
            description=(
                f"리드 교체 {lc}회, 동점 {ties}회 — "
                + (
                    "매우 치열한 경기였습니다. 이런 경기에서의 스탯은 "
                    "의미 있는 데이터입니다. 선수들의 집중력이 요구되는 상황이었습니다."
                    if very_competitive
                    else (
                        "일방적인 흐름의 경기였습니다. "
                        "주도권을 잡은 측의 스탯과 뒤처진 측의 스탯은 "
                        "맥락이 다르므로 구분하여 해석해야 합니다."
                        if lc < 3 and ties < 2
                        else "경기 흐름이 적절히 오갔습니다."
                    )
                )
            ),
            game_context="competitive" if very_competitive else "one_sided" if lc < 3 else "normal",
            current_value=float(lc),
            confidence=0.88,
        ))

        return items

    # -------------------------------------------------------------------------
    # 가비지타임 감지 (4~6)
    # -------------------------------------------------------------------------
    def _analyze_garbage_time(
        self,
        gs: GameStats,
        team: TeamStats,
        cfg: GameContextFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        qs = team.quarter_scores

        # 쿼터 점수로 가비지타임 추정
        # 4쿼터에 점수차가 크게 벌어졌으면 가비지타임 가능성
        has_4q = len(qs) >= 4
        if has_4q:
            # 3쿼터까지 누적 점수
            home_3q = sum(qs[:3]) if team.is_home else 0
            away_3q = 0
            # 점수차 추정 (상대 쿼터 스코어가 없으므로 최종 점수로 역산)
            diff_final = gs.home_score - gs.away_score
            q4_score = qs[3] if len(qs) > 3 else 0
        else:
            diff_final = gs.home_score - gs.away_score
            q4_score = 0

        abs_final = abs(diff_final)
        potential_garbage = abs_final >= cfg.garbage_time_lead and has_4q

        # 4. 가비지타임 감지
        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.WARNING if potential_garbage
                else FeedbackType.POSITIVE
            ),
            priority=(
                FeedbackPriority.HIGH if potential_garbage
                else FeedbackPriority.LOW
            ),
            title="가비지타임 감지",
            description=(
                f"최종 점수차 {abs_final}점 — "
                + (
                    f"최종 점수차 {abs_final}점으로 가비지타임이 포함된 경기입니다. "
                    "4쿼터 후반의 통계는 주전 선수의 실제 역량을 반영하지 못할 수 있으므로, "
                    "1~3쿼터 스탯과 분리하여 해석해야 합니다."
                    if potential_garbage
                    else "접전으로 가비지타임 없이 의미 있는 스탯이 기록되었습니다."
                )
            ),
            game_context="garbage_time" if potential_garbage else "meaningful",
            confidence=0.85 if potential_garbage else 0.90,
        ))

        # 5. 가비지타임 스탯 보정 필요성
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title="스탯 맥락 해석 가이드",
            description=(
                "4쿼터 벤치 멤버 출전 구간의 스탯이 전체 평균을 왜곡할 수 있습니다. "
                "개인 스탯 평가 시 가비지타임을 제외한 '주요 시간대' 스탯을 우선 참조하세요. "
                f"(4쿼터 득점: {q4_score}점)"
                if potential_garbage
                else "경기 전 구간이 유의미한 데이터입니다. 스탯을 그대로 활용해도 무방합니다."
            ),
            game_context="garbage_time_warning" if potential_garbage else "full_game",
            confidence=0.82,
        ))

        # 6. 점수 상황별 퍼포먼스 태그
        winning_most = diff_final > 0 and gs.largest_lead_home >= 10
        trailing_most = diff_final < 0 and gs.largest_lead_away >= 10
        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if winning_most
                else (FeedbackType.CORRECTION if trailing_most else FeedbackType.TIP)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="주도권 유지 분석",
            description=(
                "경기의 대부분을 리드하며 주도권을 유지했습니다. "
                "리드 상황에서의 안정적인 게임 매니지먼트가 돋보입니다."
                if winning_most
                else (
                    "경기의 대부분을 뒤쫓는 상황이었습니다. "
                    "추격 상황에서 무리한 3점 시도나 턴오버가 증가했는지 확인하세요."
                    if trailing_most
                    else "리드가 수시로 바뀌는 경합 경기였습니다. "
                         "양 팀 모두 주도권 확보에 어려움을 겪었습니다."
                )
            ),
            game_context=(
                "leading" if winning_most
                else ("trailing" if trailing_most else "competitive")
            ),
            confidence=0.84,
        ))

        return items

    # -------------------------------------------------------------------------
    # 쿼터별 퍼포먼스 추세 (7~9)
    # -------------------------------------------------------------------------
    def _analyze_quarter_trends(
        self,
        team: TeamStats,
        cfg: GameContextFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        qs = team.quarter_scores

        if len(qs) < 2:
            # 쿼터 데이터 부족 시 기본 항목만
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="쿼터별 추세 (데이터 부족)",
                description="쿼터별 점수 데이터가 부족하여 추세 분석이 제한됩니다.",
                game_context="insufficient_data",
                confidence=0.50,
            ))
            # 아래 2개도 placeholder
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="최강/최약 쿼터 (데이터 부족)",
                description="쿼터별 점수 데이터가 부족합니다.",
                game_context="insufficient_data",
                confidence=0.50,
            ))
            items.append(FeedbackItem(
                category=FeedbackCategory.RHYTHM,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="체력 추세 (데이터 부족)",
                description="쿼터별 점수 데이터가 부족합니다.",
                game_context="insufficient_data",
                confidence=0.50,
            ))
            return items

        # 7. 쿼터별 점수 추세
        trend_desc_parts = []
        for i, q in enumerate(qs):
            trend_desc_parts.append(f"Q{i + 1}: {q}점")
        trend_text = ", ".join(trend_desc_parts)

        # 상승/하락 추세 판별
        increasing = all(qs[i] <= qs[i + 1] for i in range(len(qs) - 1))
        decreasing = all(qs[i] >= qs[i + 1] for i in range(len(qs) - 1))

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if increasing
                else (FeedbackType.WARNING if decreasing else FeedbackType.TIP)
            ),
            priority=(
                FeedbackPriority.HIGH if decreasing else FeedbackPriority.MEDIUM
            ),
            title="쿼터별 점수 추세",
            description=(
                f"쿼터별 득점: {trend_text} — "
                + (
                    "쿼터가 지날수록 득점이 증가합니다. "
                    "경기가 진행될수록 팀의 적응력과 조정 능력이 돋보입니다."
                    if increasing
                    else (
                        "쿼터가 지날수록 득점이 감소합니다. "
                        "체력 저하 또는 상대의 전술 조정에 대한 대응이 부족할 수 있습니다."
                        if decreasing
                        else "쿼터별 득점이 변동적입니다."
                    )
                )
            ),
            game_context="trending_up" if increasing else ("trending_down" if decreasing else "fluctuating"),
            confidence=0.86,
        ))

        # 8. 최강/최약 쿼터 분석
        best_q = max(range(len(qs)), key=lambda i: qs[i])
        worst_q = min(range(len(qs)), key=lambda i: qs[i])

        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title="최강·최약 쿼터 분석",
            description=(
                f"최강 쿼터: Q{best_q + 1} ({qs[best_q]}점), "
                f"최약 쿼터: Q{worst_q + 1} ({qs[worst_q]}점), "
                f"차이: {qs[best_q] - qs[worst_q]}점 — "
                + (
                    f"Q{worst_q + 1}에서 득점이 급락했습니다. "
                    f"해당 쿼터의 라인업 구성, 턴오버 수, 슈팅 선택을 "
                    "집중 분석하세요."
                    if qs[best_q] - qs[worst_q] >= cfg.quarter_drop_threshold
                    else "쿼터 간 편차가 크지 않아 일관된 퍼포먼스를 유지했습니다."
                )
            ),
            game_context=f"weak_Q{worst_q + 1}",
            confidence=0.84,
        ))

        # 9. 체력 추세 분석 (후반 vs 전반)
        if len(qs) >= 4:
            first_half = qs[0] + qs[1]
            second_half = qs[2] + qs[3]
            half_diff = second_half - first_half
            fatigue = half_diff < -cfg.quarter_drop_threshold
            surge = half_diff > cfg.quarter_surge_threshold

            causes: list[CausalFactor] = []
            if fatigue:
                causes.append(CausalFactor(
                    factor="후반 체력 저하",
                    impact=0.8,
                    evidence=f"전반 {first_half}점 → 후반 {second_half}점 ({half_diff:+d}점)",
                ))

            items.append(FeedbackItem(
                category=FeedbackCategory.BALANCE,
                feedback_type=(
                    FeedbackType.WARNING if fatigue
                    else (FeedbackType.POSITIVE if surge else FeedbackType.TIP)
                ),
                priority=(
                    FeedbackPriority.HIGH if fatigue else FeedbackPriority.MEDIUM
                ),
                title="전반/후반 체력 추세",
                description=(
                    f"전반 {first_half}점 / 후반 {second_half}점 ({half_diff:+d}점) — "
                    + (
                        "후반 들어 득점이 크게 감소했습니다. "
                        "로테이션 깊이를 확보하고 체력 소모를 분산시켜야 합니다. "
                        "주전 선수 출전 시간 제한을 고려하세요."
                        if fatigue
                        else (
                            "후반에 오히려 득점이 증가했습니다. "
                            "하프타임 조정이 효과적이었거나 상대 체력이 먼저 떨어졌습니다."
                            if surge
                            else "전반/후반 퍼포먼스가 안정적입니다."
                        )
                    )
                ),
                causal_factors=causes,
                game_context="fatigue" if fatigue else ("second_half_surge" if surge else "stable"),
                confidence=0.85,
            ))
        else:
            items.append(FeedbackItem(
                category=FeedbackCategory.BALANCE,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="전반/후반 체력 추세 (데이터 부족)",
                description="4쿼터 데이터가 부족하여 전후반 비교가 제한됩니다.",
                game_context="insufficient_data",
                confidence=0.50,
            ))

        return items

    # -------------------------------------------------------------------------
    # 스코어링 런/가뭄 분석 (10~12)
    # -------------------------------------------------------------------------
    def _analyze_scoring_runs(
        self,
        gf: GameFlowData,
        cfg: GameContextFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        runs = gf.scoring_runs

        # 런 분류
        big_runs = [r for r in runs if r.points >= cfg.big_run_points]
        our_runs = [r for r in big_runs if r.team_id != ""]  # 아군 런 (기본 필터)
        total_runs = len(runs)

        # 10. 빅런 분석
        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if len(big_runs) >= 2
                else (FeedbackType.TIP if big_runs else FeedbackType.IMPROVEMENT)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="스코어링 런 분석",
            description=(
                f"전체 런 {total_runs}회 (빅런 {len(big_runs)}회: "
                + ", ".join(f"{r.points}점({r.end_time - r.start_time:.0f}초)" for r in big_runs[:3])
                + ") — "
                + (
                    "여러 차례 빅런을 기록했습니다. "
                    "모멘텀을 잡았을 때 집중적으로 밀어붙이는 능력이 뛰어납니다."
                    if len(big_runs) >= 2
                    else (
                        "빅런이 1회 발생했습니다."
                        if big_runs
                        else "유의미한 빅런이 없었습니다. 연속 득점 능력을 키우세요."
                    )
                )
            ) if big_runs else (
                f"전체 런 {total_runs}회, 빅런 0회 — "
                "연속 득점 구간이 짧아 상대를 압도하지 못했습니다. "
                "모멘텀을 잡을 수 있는 빠른 전환 공격을 늘리세요."
            ),
            game_context="scoring_run",
            current_value=float(len(big_runs)),
            confidence=0.82,
        ))

        # 11. 가장 긴 가뭄 구간 분석
        # 런 사이 간격으로 가뭄 추정
        droughts: list[float] = []
        if len(runs) >= 2:
            sorted_runs = sorted(runs, key=lambda r: r.start_time)
            for i in range(len(sorted_runs) - 1):
                gap = sorted_runs[i + 1].start_time - sorted_runs[i].end_time
                if gap > 0:
                    droughts.append(gap)

        longest_drought = max(droughts) if droughts else 0.0
        has_drought = longest_drought >= cfg.drought_duration_sec

        causes_drought: list[CausalFactor] = []
        if has_drought:
            causes_drought.append(CausalFactor(
                factor="득점 가뭄",
                impact=0.8,
                evidence=f"최장 무득점 구간 약 {longest_drought:.0f}초",
            ))

        items.append(FeedbackItem(
            category=FeedbackCategory.TIMING,
            feedback_type=(
                FeedbackType.WARNING if has_drought
                else FeedbackType.POSITIVE
            ),
            priority=(
                FeedbackPriority.HIGH if has_drought
                else FeedbackPriority.LOW
            ),
            title="득점 가뭄 분석",
            description=(
                f"런 간 최장 간격: {longest_drought:.0f}초 — "
                + (
                    f"약 {longest_drought / 60:.1f}분간 득점이 멈추는 가뭄이 있었습니다. "
                    "가뭄 구간의 슈팅 차트와 턴오버를 확인하여 "
                    "어떤 공격 패턴이 막혔는지 분석하세요."
                    if has_drought
                    else "심각한 득점 가뭄 없이 지속적으로 득점했습니다."
                )
            ),
            causal_factors=causes_drought,
            game_context="drought" if has_drought else "consistent_scoring",
            current_value=longest_drought,
            unit="초",
            confidence=0.80,
        ))

        # 12. 상대 빅런 허용 분석
        opp_big_runs = [r for r in big_runs if r.points >= cfg.big_run_points]
        allowed_big = len(opp_big_runs) >= 2

        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=(
                FeedbackType.WARNING if allowed_big
                else FeedbackType.POSITIVE
            ),
            priority=(
                FeedbackPriority.HIGH if allowed_big
                else FeedbackPriority.LOW
            ),
            title="상대 빅런 허용 분석",
            description=(
                f"빅런(10점+) {len(opp_big_runs)}회 발생 — "
                + (
                    "상대에게 다수의 빅런을 허용했습니다. "
                    "런이 시작될 때 빠른 타임아웃과 라인업 변경으로 "
                    "모멘텀을 끊는 게임 매니지먼트가 필요합니다."
                    if allowed_big
                    else "상대의 빅런을 효과적으로 차단했습니다."
                )
            ),
            game_context="opponent_run" if allowed_big else "run_prevention",
            confidence=0.78,
        ))

        return items

    # -------------------------------------------------------------------------
    # 모멘텀 전환 분석 (13~14)
    # -------------------------------------------------------------------------
    def _analyze_momentum(
        self,
        gf: GameFlowData,
        cfg: GameContextFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []
        shifts = gf.momentum_shifts
        current = gf.current_momentum

        # 13. 모멘텀 전환 빈도
        shift_count = len(shifts)
        frequent = shift_count >= 6
        stable = shift_count <= 2

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.TIP if frequent
                else (FeedbackType.POSITIVE if stable else FeedbackType.IMPROVEMENT)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="모멘텀 전환 빈도",
            description=(
                f"모멘텀 전환 {shift_count}회 — "
                + (
                    "모멘텀이 자주 바뀌었습니다. 양 팀 모두 경기 흐름을 장악하지 못한 "
                    "불안정한 경기 양상입니다. 런 이후 집중력 유지가 핵심입니다."
                    if frequent
                    else (
                        "모멘텀이 안정적으로 유지되었습니다. "
                        "경기 흐름을 주도한 팀의 전략이 효과적이었습니다."
                        if stable
                        else "모멘텀 전환이 적절히 발생한 경합 경기입니다."
                    )
                )
            ),
            game_context="volatile" if frequent else ("stable_momentum" if stable else "normal"),
            current_value=float(shift_count),
            confidence=0.80,
        ))

        # 14. 현재(최종) 모멘텀 상태
        home_momentum = current in (MomentumState.STRONG_HOME, MomentumState.SLIGHT_HOME)
        away_momentum = current in (MomentumState.STRONG_AWAY, MomentumState.SLIGHT_AWAY)

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=(
                FeedbackType.POSITIVE if home_momentum
                else (FeedbackType.CORRECTION if away_momentum else FeedbackType.TIP)
            ),
            priority=FeedbackPriority.MEDIUM,
            title="최종 모멘텀 상태",
            description=(
                f"최종 모멘텀: {current.value} — "
                + (
                    "경기 종료 시점에 아군이 모멘텀을 잡고 있었습니다. "
                    "다음 경기에 긍정적 관성을 이어갈 수 있습니다."
                    if home_momentum
                    else (
                        "상대가 경기 종료 시점에 모멘텀을 잡고 있었습니다. "
                        "4쿼터 마지막 흐름을 분석하여 수정할 부분을 찾으세요."
                        if away_momentum
                        else "경기가 중립적 모멘텀에서 종료되었습니다."
                    )
                )
            ),
            game_context=f"momentum_{current.value}",
            confidence=0.82,
        ))

        return items

    # -------------------------------------------------------------------------
    # 종합 맥락 평가 (15~16)
    # -------------------------------------------------------------------------
    def _overall_context_assessment(
        self,
        gs: GameStats,
        gf: GameFlowData,
        team: TeamStats,
        cfg: GameContextFeedbackConfig,
    ) -> list[FeedbackItem]:
        items: list[FeedbackItem] = []

        # 지표 종합
        diff = abs(gs.home_score - gs.away_score)
        close = diff <= cfg.close_game_threshold
        won = gs.home_score > gs.away_score
        lc = gs.lead_changes
        big_runs = len([r for r in gf.scoring_runs if r.points >= cfg.big_run_points])
        shifts = len(gf.momentum_shifts)

        # 15. 데이터 신뢰성 평가
        # 접전이면 모든 스탯이 유의미, 대격차면 가비지타임 보정 필요
        reliability = "high" if close else ("medium" if diff < 15 else "low")
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.HIGH,
            title="데이터 신뢰성 맥락 평가",
            description=(
                f"점수차 {diff}점, 리드교체 {lc}회 — 데이터 신뢰도: "
                + (
                    "높음. 접전 경기로 모든 통계가 선수의 실제 역량을 반영합니다."
                    if reliability == "high"
                    else (
                        "중간. 적당한 격차의 경기로 대부분의 통계가 유의미하지만, "
                        "4쿼터 후반부 데이터는 약간의 보정이 필요할 수 있습니다."
                        if reliability == "medium"
                        else "낮음. 대격차 경기로 가비지타임 스탯이 포함됩니다. "
                             "주요 시간대(1~3Q) 스탯 위주로 평가하세요."
                    )
                )
            ),
            game_context=f"reliability_{reliability}",
            confidence=0.90,
        ))

        # 16. 전체 경기 맥락 요약
        context_tags = []
        if close:
            context_tags.append("접전")
        if big_runs >= 2:
            context_tags.append("빅런 다발")
        if shifts >= 6:
            context_tags.append("잦은 모멘텀 전환")
        if diff >= cfg.garbage_time_lead:
            context_tags.append("가비지타임 포함")
        if lc >= 10:
            context_tags.append("치열한 리드 싸움")
        tag_text = ", ".join(context_tags) if context_tags else "일반적인 경기"

        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.HIGH,
            title="경기 맥락 종합 요약",
            description=(
                f"경기 특성: [{tag_text}] — "
                f"최종 {'승리' if won else '패배'} "
                f"({gs.home_score}:{gs.away_score}). "
                "위 맥락을 고려하여 개별 스탯을 해석하세요. "
                "특히 가비지타임이 포함된 경우 주전 시간대 스탯을 우선 참조해야 합니다."
            ),
            game_context=tag_text,
            confidence=0.88,
        ))

        return items

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"GameContextFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "GameContextFeedbackGenerator",
    "GameContextFeedbackConfig",
]

__version__ = "1.0.0"
