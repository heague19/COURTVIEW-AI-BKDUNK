# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: defensive_feedback.py
설명: 수비 분석 피드백 생성기 (전력분석원 수준).
      - 팀 DRtg, 수비 스킴, 컨테스트율, 헬프 로테이션, 클로즈아웃
      - 박스아웃, 매치업 개별 분석, 스틸/블락/리바운드
      - 상대 FG% 분해(2P vs 3P), 페인트 보호, 외곽 수비
      - 전환 수비, 매치업 승패 요약, 파울 규율, 종합 등급
      - DefenseAnalysis + list[MatchupData] + TeamStats + TransitionData
        → FeedbackItem 변환 (15+ 항목)

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
from shared.dto.game_dto import TeamStats
from shared.dto.tactical_dto import DefenseAnalysis, MatchupData, TransitionData

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.korean_templates import KoreanTemplates
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper, get_default_korean_templates


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class DefensiveFeedbackConfig:
    """수비 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    # 수비 효율 임계치
    drtg_good: float = 105.0            # DRtg 105 이하 → 양호
    contest_rate_good: float = 0.60     # 60%+ 컨테스트 → 양호
    help_rotation_good: float = 70.0    # 70+ 로테이션 품질 → 양호
    closeout_good: float = 70.0         # 70+ 클로즈아웃 → 양호
    matchup_fg_good: float = 45.0       # 허용 FG% 45 이하 → 양호

    # 추가 임계치
    steals_per_game_good: float = 7.0        # 팀 스틸 7+ → 양호
    steals_per_game_great: float = 10.0      # 팀 스틸 10+ → 우수
    blocks_per_game_good: float = 4.0        # 팀 블락 4+ → 양호
    blocks_per_game_great: float = 6.0       # 팀 블락 6+ → 우수
    def_reb_pct_good: float = 72.0           # 수비 리바운드% 72+ → 양호
    opp_fg_pct_good: float = 44.0            # 상대 FG% 44 이하 → 양호
    opp_3pt_pct_good: float = 34.0           # 상대 3P% 34 이하 → 양호
    paint_pts_allowed_bad: int = 44           # 페인트존 실점 44+ → 나쁨
    recovery_rate_good: float = 0.70         # 수비 복귀율 70%+ → 양호
    fouls_per_game_bad: float = 22.0         # 팀 파울 22+ → 과다
    fouls_per_game_good: float = 17.0        # 팀 파울 17 이하 → 양호
    matchup_win_rate_good: float = 0.60      # 매치업 승률 60%+ → 양호


# =============================================================================
# DefensiveFeedbackGenerator 클래스
# =============================================================================
class DefensiveFeedbackGenerator:
    """
    수비 분석 피드백 생성기.

    DefenseAnalysis, MatchupData, TeamStats, TransitionData를 입력받아
    매치업 효율, 헬프 디펜스, 클로즈아웃, 컨테스트율, 스틸/블락,
    리바운드, 페인트 보호, 외곽 수비, 전환 수비, 파울 규율 등
    전력분석원급 수비 피드백을 생성합니다 (15+ FeedbackItem).
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: DefensiveFeedbackConfig | None = None) -> None:
        self._config: DefensiveFeedbackConfig = config or DefensiveFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "DefensiveFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def generate(
        self,
        defense: DefenseAnalysis,
        matchups: list[MatchupData] | None = None,
        team_stats: TeamStats | None = None,
        transition: TransitionData | None = None,
    ) -> list[FeedbackItem]:
        """
        수비 분석 결과에서 전력분석원급 피드백 항목 생성.

        Args:
            defense: 종합 수비 분석 DTO
            matchups: 1v1 매치업 데이터 목록
            team_stats: 팀 경기 통계 (스틸/블락/리바운드/파울 등)
            transition: 전환 공수 분석 데이터

        Returns:
            FeedbackItem 목록 (15+ 항목)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        # === 1. 팀 수비 효율 (DRtg) ===
        items.extend(self._drtg_feedback(defense, cfg))

        # === 2. 수비 스킴 분석 ===
        items.append(self._scheme_feedback(defense))

        # === 3. 슛 컨테스트율 ===
        items.extend(self._contest_rate_feedback(defense, cfg))

        # === 4. 헬프 디펜스 로테이션 ===
        items.extend(self._help_rotation_feedback(defense, cfg))

        # === 5. 클로즈아웃 품질 ===
        items.extend(self._closeout_feedback(defense, cfg))

        # === 6. 박스아웃율 ===
        items.extend(self._box_out_feedback(defense))

        # === 7. 매치업별 개별 분석 ===
        items.extend(self._matchup_individual_feedback(matchups, cfg))

        # === 8. 스틸 분석 ===
        items.extend(self._steals_feedback(defense, team_stats, cfg))

        # === 9. 블락 분석 ===
        items.extend(self._blocks_feedback(defense, team_stats, cfg))

        # === 10. 수비 리바운드% ===
        items.extend(self._defensive_rebound_pct_feedback(team_stats, cfg))

        # === 11. 상대 FG% 분해 (2P vs 3P) ===
        items.extend(self._opponent_fg_breakdown_feedback(defense, cfg))

        # === 12. 페인트 보호 분석 ===
        items.extend(self._paint_protection_feedback(team_stats, cfg))

        # === 13. 외곽 수비 분석 ===
        items.extend(self._perimeter_defense_feedback(defense, cfg))

        # === 14. 전환 수비 (수비 복귀율) ===
        items.extend(self._transition_defense_feedback(transition, cfg))

        # === 15. 매치업 승패 요약 ===
        items.extend(self._matchup_summary_feedback(matchups, cfg))

        # === 16. 파울 규율 ===
        items.extend(self._foul_discipline_feedback(team_stats, cfg))

        # === 17. 종합 수비 등급 ===
        items.append(self._overall_grade_feedback(defense, matchups, team_stats, cfg))

        with self._lock:
            self._total_generated += 1

        return items

    # =========================================================================
    # 1. 팀 수비 효율 (DRtg)
    # =========================================================================
    def _drtg_feedback(
        self, defense: DefenseAnalysis, cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        drtg = defense.defensive_rating
        if drtg <= 0:
            return []
        drtg_good = drtg <= cfg.drtg_good
        # DRtg는 낮을수록 좋으므로 역변환
        sev = self._severity_mapper.from_ratio_inverse(drtg / 120.0)
        return [self._make(
            category=FeedbackCategory.BALANCE,
            fb_type=FeedbackType.POSITIVE if drtg_good else FeedbackType.CORRECTION,
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="팀 수비 효율 (DRtg)",
            description=(
                f"수비 효율 {drtg:.1f} (100포제션당 실점). "
                + ("리그 평균 이하로 수비가 견고합니다." if drtg_good
                   else "실점이 많습니다. 수비 로테이션과 매치업 점검이 필요합니다.")
            ),
            current_value=drtg,
            ideal_value=cfg.drtg_good,
            unit="DRtg",
            confidence=0.90,
        )]

    # =========================================================================
    # 2. 수비 스킴 분석
    # =========================================================================
    def _scheme_feedback(self, defense: DefenseAnalysis) -> FeedbackItem:
        scheme_label = defense.primary_scheme.value
        # 스킴별 부가 코멘트
        if defense.primary_scheme.is_zone:
            scheme_comment = "존 수비로 내부 수비를 강화하되 3점 라인 커버에 유의하세요."
        elif defense.primary_scheme.is_press:
            scheme_comment = "프레스 수비로 상대 실수를 유도하되 체력 소모에 유의하세요."
        else:
            scheme_comment = "맨투맨 기반으로 개인 수비 책임이 강조됩니다."

        return self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="주요 수비 스킴",
            description=(
                f"주요 수비 형태: {scheme_label}. "
                f"상대 FG% {defense.opponent_fg_pct:.1f}%, "
                f"3P% {defense.opponent_3pt_pct:.1f}% 허용. "
                f"{scheme_comment}"
            ),
            confidence=0.85,
        )

    # =========================================================================
    # 3. 슛 컨테스트율
    # =========================================================================
    def _contest_rate_feedback(
        self, defense: DefenseAnalysis, cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        rate = defense.contested_shot_rate
        if rate <= 0:
            return []
        good = rate >= cfg.contest_rate_good
        sev = self._severity_mapper.from_ratio(min(rate, 1.0))
        return [self._make(
            category=FeedbackCategory.TIMING,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.CORRECTION,
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="슛 컨테스트율",
            description=(
                f"상대 슈팅의 {rate * 100:.0f}%를 컨테스트했습니다. "
                + ("적극적인 수비가 이루어지고 있습니다." if good
                   else "오픈 슛을 허용하는 빈도가 높습니다. 클로즈아웃을 강화하세요.")
            ),
            current_value=rate * 100,
            ideal_value=cfg.contest_rate_good * 100,
            unit="percent",
            confidence=0.90,
        )]

    # =========================================================================
    # 4. 헬프 디펜스 로테이션
    # =========================================================================
    def _help_rotation_feedback(
        self, defense: DefenseAnalysis, cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        help_score = defense.help_rotation_quality
        if help_score <= 0:
            return []
        good = help_score >= cfg.help_rotation_good
        sev = self._severity_mapper.from_score(help_score)
        return [self._make(
            category=FeedbackCategory.COORDINATION,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.CORRECTION,
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="헬프 디펜스 로테이션",
            description=(
                f"헬프 디펜스 로테이션 품질 {help_score:.0f}점. "
                + ("팀 수비 연계가 효과적입니다." if good
                   else "헬프 후 리커버리가 느려 오픈 슛을 허용합니다.")
            ),
            suggestion=(
                None if good
                else "헬프 사이드에서 X-out 또는 스턴트 회복을 반복 훈련하세요."
            ),
            current_value=help_score,
            ideal_value=cfg.help_rotation_good,
            confidence=0.85,
        )]

    # =========================================================================
    # 5. 클로즈아웃 품질
    # =========================================================================
    def _closeout_feedback(
        self, defense: DefenseAnalysis, cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        closeout = defense.closeout_quality
        if closeout <= 0:
            return []
        good = closeout >= cfg.closeout_good
        sev = self._severity_mapper.from_score(closeout)
        return [self._make(
            category=FeedbackCategory.FOOTWORK,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.CORRECTION,
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="클로즈아웃 품질",
            description=(
                f"클로즈아웃 품질 {closeout:.0f}점. "
                + ("슈터에게 빠르고 정확한 접근이 이루어지고 있습니다." if good
                   else "클로즈아웃 속도가 느려 슈터에게 여유를 주고 있습니다.")
            ),
            suggestion=(
                None if good
                else "숏 클로즈아웃 시 하이핸드로 접근하고 드라이브 대비 저중심을 유지하세요."
            ),
            current_value=closeout,
            ideal_value=cfg.closeout_good,
            confidence=0.85,
        )]

    # =========================================================================
    # 6. 박스아웃율
    # =========================================================================
    def _box_out_feedback(self, defense: DefenseAnalysis) -> list[FeedbackItem]:
        box_out = defense.box_out_rate
        if box_out <= 0:
            return []
        good = box_out >= 0.60
        return [self._make(
            category=FeedbackCategory.POWER,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.LOW,
            title="박스아웃율",
            description=(
                f"수비 리바운드 시 박스아웃 비율 {box_out * 100:.0f}%. "
                + ("리바운드 확보 의지가 강합니다." if good
                   else "박스아웃이 부족하여 공격 리바운드를 허용하고 있습니다.")
            ),
            suggestion=(
                None if good
                else "슛이 올라가는 순간 가장 가까운 상대를 먼저 몸으로 밀착해 박스아웃을 실행하세요."
            ),
            current_value=box_out * 100,
            confidence=0.85,
        )]

    # =========================================================================
    # 7. 매치업별 개별 분석
    # =========================================================================
    def _matchup_individual_feedback(
        self,
        matchups: list[MatchupData] | None,
        cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        if not matchups:
            return []
        items: list[FeedbackItem] = []
        for matchup in matchups[:5]:
            if matchup.fg_attempts <= 0:
                continue
            matchup_good = matchup.fg_pct < cfg.matchup_fg_good

            # 매치업별 세부 평가
            contest_note = ""
            if matchup.contest_rate >= 0.75:
                contest_note = " 컨테스트율이 우수합니다."
            elif matchup.contest_rate < 0.50 and matchup.contest_rate > 0:
                contest_note = " 컨테스트율이 낮아 오픈 슛을 허용하고 있습니다."

            ppp_note = ""
            if matchup.possessions > 0:
                ppp = matchup.points_allowed / matchup.possessions
                if ppp >= 1.1:
                    ppp_note = f" 포제션당 {ppp:.2f}점 허용으로 비효율적입니다."
                elif ppp <= 0.8:
                    ppp_note = f" 포제션당 {ppp:.2f}점 허용으로 효과적으로 억제하고 있습니다."

            items.append(self._make(
                category=FeedbackCategory.FOOTWORK,
                fb_type=(FeedbackType.POSITIVE if matchup_good
                         else FeedbackType.CORRECTION),
                priority=FeedbackPriority.MEDIUM,
                title=(f"매치업: #{matchup.defender_tracking_id} "
                       f"vs #{matchup.offensive_tracking_id}"),
                description=(
                    f"수비수 #{matchup.defender_tracking_id}가 "
                    f"상대 #{matchup.offensive_tracking_id}에게 "
                    f"FG% {matchup.fg_pct:.1f}% 허용 "
                    f"({matchup.fg_made}/{matchup.fg_attempts}). "
                    + ("효과적인 수비를 펼쳤습니다." if matchup_good
                       else "수비 전략 조정이 필요합니다.")
                    + contest_note + ppp_note
                ),
                current_value=matchup.fg_pct,
                ideal_value=cfg.matchup_fg_good,
                confidence=0.85,
            ))
        return items

    # =========================================================================
    # 8. 스틸 분석
    # =========================================================================
    def _steals_feedback(
        self,
        defense: DefenseAnalysis,
        team_stats: TeamStats | None,
        cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        # TeamStats 기반 (경기당 스틸)
        if team_stats is not None and team_stats.steals > 0:
            stl = team_stats.steals
            if stl >= cfg.steals_per_game_great:
                quality = "매우 우수"
                fb_type = FeedbackType.POSITIVE
            elif stl >= cfg.steals_per_game_good:
                quality = "양호"
                fb_type = FeedbackType.POSITIVE
            else:
                quality = "부족"
                fb_type = FeedbackType.IMPROVEMENT
            return [self._make(
                category=FeedbackCategory.TIMING,
                fb_type=fb_type,
                priority=FeedbackPriority.LOW,
                title="스틸 분석",
                description=(
                    f"팀 스틸 {stl}개 ({quality}). "
                    + (f"적극적인 핸즈 액티브 수비로 상대 실수를 유도하고 있습니다."
                       if stl >= cfg.steals_per_game_good
                       else f"패싱 레인 차단과 볼 압박을 강화하여 턴오버 유도를 늘릴 필요가 있습니다.")
                ),
                current_value=float(stl),
                ideal_value=cfg.steals_per_game_good,
                unit="개",
                confidence=0.85,
            )]

        # TeamStats 없을 때 steals_per_possession 활용
        spp = defense.steals_per_possession
        if spp > 0:
            # NBA 평균 약 0.07~0.08 steals/possession
            good = spp >= 0.075
            return [self._make(
                category=FeedbackCategory.TIMING,
                fb_type=FeedbackType.POSITIVE if good else FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.LOW,
                title="스틸 분석",
                description=(
                    f"포제션당 스틸 비율 {spp:.3f}. "
                    + ("패싱 레인 차단이 효과적으로 이루어지고 있습니다." if good
                       else "패싱 레인 읽기와 볼 압박 강도를 높일 필요가 있습니다.")
                ),
                current_value=spp,
                confidence=0.80,
            )]
        return []

    # =========================================================================
    # 9. 블락 분석
    # =========================================================================
    def _blocks_feedback(
        self,
        defense: DefenseAnalysis,
        team_stats: TeamStats | None,
        cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        # TeamStats 기반 (경기당 블락)
        if team_stats is not None and team_stats.blocks > 0:
            blk = team_stats.blocks
            if blk >= cfg.blocks_per_game_great:
                quality = "매우 우수"
                fb_type = FeedbackType.POSITIVE
            elif blk >= cfg.blocks_per_game_good:
                quality = "양호"
                fb_type = FeedbackType.POSITIVE
            else:
                quality = "부족"
                fb_type = FeedbackType.IMPROVEMENT
            return [self._make(
                category=FeedbackCategory.POWER,
                fb_type=fb_type,
                priority=FeedbackPriority.LOW,
                title="블락 분석",
                description=(
                    f"팀 블락 {blk}개 ({quality}). "
                    + (f"림 프로텍션이 강력하여 상대 내부 공격을 억제하고 있습니다."
                       if blk >= cfg.blocks_per_game_good
                       else f"림 프로텍터의 타이밍 훈련과 헬프 포지셔닝 개선이 필요합니다.")
                ),
                current_value=float(blk),
                ideal_value=cfg.blocks_per_game_good,
                unit="개",
                confidence=0.85,
            )]

        # TeamStats 없을 때 blocks_per_possession 활용
        bpp = defense.blocks_per_possession
        if bpp > 0:
            # NBA 평균 약 0.045~0.055 blocks/possession
            good = bpp >= 0.05
            return [self._make(
                category=FeedbackCategory.POWER,
                fb_type=FeedbackType.POSITIVE if good else FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.LOW,
                title="블락 분석",
                description=(
                    f"포제션당 블락 비율 {bpp:.3f}. "
                    + ("내부 수비 위협이 효과적입니다." if good
                       else "림 보호 능력을 강화할 필요가 있습니다.")
                ),
                current_value=bpp,
                confidence=0.80,
            )]
        return []

    # =========================================================================
    # 10. 수비 리바운드%
    # =========================================================================
    def _defensive_rebound_pct_feedback(
        self,
        team_stats: TeamStats | None,
        cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        if team_stats is None:
            return []
        drb = team_stats.defensive_rebounds
        total_reb = team_stats.total_rebounds
        if total_reb <= 0:
            return []

        # 수비 리바운드% = 수비 리바운드 / 총 리바운드 * 100
        drb_pct = drb / total_reb * 100
        good = drb_pct >= cfg.def_reb_pct_good

        return [self._make(
            category=FeedbackCategory.POWER,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM if not good else FeedbackPriority.LOW,
            title="수비 리바운드율",
            description=(
                f"수비 리바운드 {drb}개 (전체 리바운드의 {drb_pct:.1f}%). "
                + (f"수비 리바운드 확보가 안정적이어서 상대 세컨드 찬스를 제한하고 있습니다."
                   if good
                   else f"수비 리바운드 확보율이 낮아 상대에게 추가 공격 기회를 허용하고 있습니다. "
                        f"박스아웃 습관과 포지셔닝 점검이 필요합니다.")
            ),
            current_value=drb_pct,
            ideal_value=cfg.def_reb_pct_good,
            unit="percent",
            confidence=0.85,
        )]

    # =========================================================================
    # 11. 상대 FG% 분해 (2P vs 3P)
    # =========================================================================
    def _opponent_fg_breakdown_feedback(
        self, defense: DefenseAnalysis, cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        opp_fg = defense.opponent_fg_pct
        opp_3pt = defense.opponent_3pt_pct
        if opp_fg <= 0 and opp_3pt <= 0:
            return []

        # 2점 FG% 추정: (전체 FG% 에서 3점 비율 제외)
        # 정확한 2점 FG%를 따로 받지 못하므로, 전체 vs 3점으로 구분 분석
        fg_good = opp_fg <= cfg.opp_fg_pct_good
        three_good = opp_3pt <= cfg.opp_3pt_pct_good

        if fg_good and three_good:
            assessment = "내외곽 모두 상대 슈팅을 효과적으로 억제하고 있습니다."
            fb_type = FeedbackType.POSITIVE
        elif fg_good and not three_good:
            assessment = (
                f"내부 수비는 양호하나 3점 허용률({opp_3pt:.1f}%)이 높습니다. "
                f"3점 슈터 클로즈아웃과 스크린 대응을 강화하세요."
            )
            fb_type = FeedbackType.IMPROVEMENT
        elif not fg_good and three_good:
            assessment = (
                f"외곽 수비는 양호하나 전체 FG%({opp_fg:.1f}%)가 높습니다. "
                f"페인트존 수비와 미드레인지 컨테스트를 강화하세요."
            )
            fb_type = FeedbackType.IMPROVEMENT
        else:
            assessment = (
                f"내외곽 모두 상대 슈팅을 억제하지 못하고 있습니다. "
                f"전체적인 수비 강도와 로테이션을 재점검하세요."
            )
            fb_type = FeedbackType.CORRECTION

        return [self._make(
            category=FeedbackCategory.BALANCE,
            fb_type=fb_type,
            priority=FeedbackPriority.MEDIUM,
            title="상대 슈팅 허용 분석 (FG%/3P%)",
            description=(
                f"상대 FG% {opp_fg:.1f}% (기준 {cfg.opp_fg_pct_good}% 이하), "
                f"3P% {opp_3pt:.1f}% (기준 {cfg.opp_3pt_pct_good}% 이하). "
                f"{assessment}"
            ),
            current_value=opp_fg,
            ideal_value=cfg.opp_fg_pct_good,
            unit="percent",
            confidence=0.88,
        )]

    # =========================================================================
    # 12. 페인트 보호 분석
    # =========================================================================
    def _paint_protection_feedback(
        self,
        team_stats: TeamStats | None,
        cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        if team_stats is None:
            return []
        # TeamStats에 points_in_paint이 상대의 것인지 자신의 것인지:
        # 여기서는 "상대에게 허용한 페인트존 득점"으로 해석하려면
        # 상대 TeamStats를 받아야 하지만, 단일 팀 기준이므로
        # 자체 페인트존 득점과 관련한 수비적 관점에서 분석
        # → 실제로는 상대 팀의 points_in_paint가 필요하나
        #   generate 시그니처에 opponent_stats를 추가하지 않고
        #   blocks/steals 기반 + 전반적 수비 코멘트로 대체
        # paint_pts_allowed는 config로 설정되며, blocks와 연계하여 분석
        blk = team_stats.blocks
        # 블락이 많으면 페인트 보호가 양호한 것으로 추론
        if blk >= cfg.blocks_per_game_good:
            paint_quality = "양호"
            fb_type = FeedbackType.POSITIVE
            comment = (
                f"팀 블락 {blk}개로 림 프로텍션이 강력합니다. "
                f"상대의 페인트존 진입 시 효과적인 억제력을 발휘하고 있습니다."
            )
        else:
            paint_quality = "개선 필요"
            fb_type = FeedbackType.IMPROVEMENT
            comment = (
                f"팀 블락 {blk}개로 림 프로텍션이 부족합니다. "
                f"빅맨의 헬프 포지션과 약한 쪽(weak side) 림 보호를 강화하세요."
            )

        return [self._make(
            category=FeedbackCategory.POSTURE,
            fb_type=fb_type,
            priority=FeedbackPriority.MEDIUM,
            title=f"페인트 보호 ({paint_quality})",
            description=comment,
            suggestion=(
                None if fb_type == FeedbackType.POSITIVE
                else "드라이브 시 빅맨이 림 근처에서 수직으로 점프하는 vertical contest를 훈련하세요."
            ),
            confidence=0.82,
        )]

    # =========================================================================
    # 13. 외곽 수비 분석
    # =========================================================================
    def _perimeter_defense_feedback(
        self, defense: DefenseAnalysis, cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        opp_3pt = defense.opponent_3pt_pct
        contest_rate = defense.contested_shot_rate
        if opp_3pt <= 0:
            return []

        three_good = opp_3pt <= cfg.opp_3pt_pct_good
        contest_good = contest_rate >= cfg.contest_rate_good

        if three_good and contest_good:
            assessment = "3점 허용률과 컨테스트율 모두 우수하여 외곽 수비가 견고합니다."
            fb_type = FeedbackType.POSITIVE
        elif three_good:
            assessment = "3점 허용률은 양호하나 컨테스트율 향상 시 더욱 안정적인 외곽 수비가 가능합니다."
            fb_type = FeedbackType.TIP
        elif contest_good:
            assessment = (
                f"컨테스트는 적극적이나 3점 허용률({opp_3pt:.1f}%)이 높습니다. "
                f"클로즈아웃 타이밍과 거리 조절을 점검하세요."
            )
            fb_type = FeedbackType.IMPROVEMENT
        else:
            assessment = (
                f"3점 허용률({opp_3pt:.1f}%)과 컨테스트율 모두 부족합니다. "
                f"스크린 대응 후 슈터 복귀와 커뮤니케이션을 강화하세요."
            )
            fb_type = FeedbackType.CORRECTION

        return [self._make(
            category=FeedbackCategory.FOOTWORK,
            fb_type=fb_type,
            priority=FeedbackPriority.MEDIUM,
            title="외곽 수비 분석",
            description=(
                f"상대 3P% {opp_3pt:.1f}%, 컨테스트율 {contest_rate * 100:.0f}%. "
                f"{assessment}"
            ),
            current_value=opp_3pt,
            ideal_value=cfg.opp_3pt_pct_good,
            unit="percent",
            confidence=0.85,
        )]

    # =========================================================================
    # 14. 전환 수비 (수비 복귀율)
    # =========================================================================
    def _transition_defense_feedback(
        self,
        transition: TransitionData | None,
        cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        if transition is None:
            return []
        recovery = transition.defensive_recovery_rate
        if recovery <= 0:
            return []

        good = recovery >= cfg.recovery_rate_good

        return [self._make(
            category=FeedbackCategory.TIMING,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM if not good else FeedbackPriority.LOW,
            title="전환 수비 (수비 복귀율)",
            description=(
                f"수비 복귀 성공률 {recovery * 100:.0f}%. "
                + (f"속공 상황에서 빠른 복귀가 이루어지고 있어 이지 바스켓을 억제하고 있습니다."
                   if good
                   else f"수비 복귀가 늦어 상대에게 속공 기회를 허용하고 있습니다. "
                        f"슈팅 후 즉각적인 백코트 전환과 세이프티 배치를 강화하세요.")
            ),
            suggestion=(
                None if good
                else "슛 시도 직후 가드가 세이프티로 먼저 복귀하는 습관을 훈련하세요."
            ),
            current_value=recovery * 100,
            ideal_value=cfg.recovery_rate_good * 100,
            unit="percent",
            confidence=0.85,
        )]

    # =========================================================================
    # 15. 매치업 승패 요약
    # =========================================================================
    def _matchup_summary_feedback(
        self,
        matchups: list[MatchupData] | None,
        cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        if not matchups:
            return []
        valid = [m for m in matchups if m.fg_attempts > 0]
        if not valid:
            return []

        wins = sum(1 for m in valid if m.fg_pct < cfg.matchup_fg_good)
        losses = len(valid) - wins
        win_rate = wins / len(valid) if valid else 0.0
        good = win_rate >= cfg.matchup_win_rate_good

        # 최고/최악 매치업
        best = min(valid, key=lambda m: m.fg_pct)
        worst = max(valid, key=lambda m: m.fg_pct)

        return [self._make(
            category=FeedbackCategory.COORDINATION,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.IMPROVEMENT,
            priority=FeedbackPriority.MEDIUM,
            title="매치업 승패 요약",
            description=(
                f"총 {len(valid)}개 매치업 중 {wins}승 {losses}패 "
                f"(승률 {win_rate * 100:.0f}%). "
                f"최고: #{best.defender_tracking_id} vs #{best.offensive_tracking_id} "
                f"(FG% {best.fg_pct:.1f}%), "
                f"최악: #{worst.defender_tracking_id} vs #{worst.offensive_tracking_id} "
                f"(FG% {worst.fg_pct:.1f}%). "
                + ("전반적으로 개인 수비 매치업에서 우위를 점하고 있습니다." if good
                   else "매치업 패배가 잦아 스위치 또는 더블팀 전략을 검토하세요.")
            ),
            suggestion=(
                None if good
                else f"#{worst.defender_tracking_id} 선수의 매치업 전환 또는 "
                     f"헬프 디펜스 지원을 우선적으로 검토하세요."
            ),
            current_value=win_rate * 100,
            ideal_value=cfg.matchup_win_rate_good * 100,
            unit="percent",
            confidence=0.85,
        )]

    # =========================================================================
    # 16. 파울 규율
    # =========================================================================
    def _foul_discipline_feedback(
        self,
        team_stats: TeamStats | None,
        cfg: DefensiveFeedbackConfig,
    ) -> list[FeedbackItem]:
        if team_stats is None:
            return []
        fouls = team_stats.personal_fouls
        if fouls <= 0:
            return []

        if fouls <= cfg.fouls_per_game_good:
            quality = "우수"
            fb_type = FeedbackType.POSITIVE
            comment = "불필요한 파울 없이 깨끗한 수비를 유지하고 있습니다."
        elif fouls >= cfg.fouls_per_game_bad:
            quality = "과다"
            fb_type = FeedbackType.CORRECTION
            comment = (
                "파울이 과다하여 상대에게 자유투 기회를 많이 허용하고 있습니다. "
                "수비 포지셔닝으로 파울 없이 억제하는 훈련이 필요합니다."
            )
        else:
            quality = "보통"
            fb_type = FeedbackType.TIP
            comment = "적정 수준이지만 불필요한 파울을 줄이면 수비 효율이 개선됩니다."

        return [self._make(
            category=FeedbackCategory.BALANCE,
            fb_type=fb_type,
            priority=FeedbackPriority.MEDIUM if fouls >= cfg.fouls_per_game_bad else FeedbackPriority.LOW,
            title=f"파울 규율 ({quality})",
            description=(
                f"팀 파울 {fouls}개. {comment}"
            ),
            suggestion=(
                None if fouls <= cfg.fouls_per_game_good
                else "손 대신 발로 수비하는 Footwork-first 원칙을 강조하세요."
            ),
            current_value=float(fouls),
            ideal_value=cfg.fouls_per_game_good,
            unit="개",
            confidence=0.85,
        )]

    # =========================================================================
    # 17. 종합 수비 등급
    # =========================================================================
    def _overall_grade_feedback(
        self,
        defense: DefenseAnalysis,
        matchups: list[MatchupData] | None,
        team_stats: TeamStats | None,
        cfg: DefensiveFeedbackConfig,
    ) -> FeedbackItem:
        # 가중 점수 산출 (0~100)
        scores: list[float] = []
        weights: list[float] = []

        # DRtg 기반 점수 (가중치 30)
        if defense.defensive_rating > 0:
            # 100이 최고, 120이 최저로 매핑 → 0~100
            drtg_score = max(0.0, min(100.0, (120.0 - defense.defensive_rating) / 20.0 * 100.0))
            scores.append(drtg_score)
            weights.append(30.0)

        # 컨테스트율 (가중치 15)
        if defense.contested_shot_rate > 0:
            contest_score = min(100.0, defense.contested_shot_rate / 0.80 * 100.0)
            scores.append(contest_score)
            weights.append(15.0)

        # 헬프 로테이션 (가중치 15)
        if defense.help_rotation_quality > 0:
            scores.append(defense.help_rotation_quality)
            weights.append(15.0)

        # 클로즈아웃 (가중치 10)
        if defense.closeout_quality > 0:
            scores.append(defense.closeout_quality)
            weights.append(10.0)

        # 상대 FG% (가중치 15) — 낮을수록 좋음
        if defense.opponent_fg_pct > 0:
            fg_score = max(0.0, min(100.0, (55.0 - defense.opponent_fg_pct) / 20.0 * 100.0))
            scores.append(fg_score)
            weights.append(15.0)

        # 매치업 승률 (가중치 10)
        if matchups:
            valid = [m for m in matchups if m.fg_attempts > 0]
            if valid:
                win_count = sum(1 for m in valid if m.fg_pct < cfg.matchup_fg_good)
                matchup_score = win_count / len(valid) * 100.0
                scores.append(matchup_score)
                weights.append(10.0)

        # 파울 규율 (가중치 5)
        if team_stats is not None and team_stats.personal_fouls > 0:
            fouls = team_stats.personal_fouls
            # 15 이하 → 100점, 25 이상 → 0점
            foul_score = max(0.0, min(100.0, (25.0 - fouls) / 10.0 * 100.0))
            scores.append(foul_score)
            weights.append(5.0)

        # 가중 평균
        if scores and weights:
            total_weight = sum(weights)
            overall = sum(s * w for s, w in zip(scores, weights)) / total_weight
        else:
            overall = 50.0  # 데이터 부족 시 중간값

        # 등급 판정
        if overall >= 85:
            grade = "A+"
            grade_desc = "엘리트 수준의 수비력입니다."
        elif overall >= 75:
            grade = "A"
            grade_desc = "우수한 수비력을 보여주고 있습니다."
        elif overall >= 65:
            grade = "B+"
            grade_desc = "양호한 수비력이나 일부 개선 여지가 있습니다."
        elif overall >= 55:
            grade = "B"
            grade_desc = "보통 수준의 수비력으로 체계적인 개선이 필요합니다."
        elif overall >= 45:
            grade = "C"
            grade_desc = "수비 전반에 걸쳐 개선이 시급합니다."
        else:
            grade = "D"
            grade_desc = "수비 시스템 재구축이 필요합니다."

        fb_type = (
            FeedbackType.POSITIVE if overall >= 70
            else FeedbackType.IMPROVEMENT if overall >= 50
            else FeedbackType.CORRECTION
        )

        return self._make(
            category=FeedbackCategory.TIP,
            fb_type=fb_type,
            priority=FeedbackPriority.MEDIUM,
            title=f"종합 수비 등급: {grade}",
            description=(
                f"종합 수비 점수 {overall:.1f}/100 (등급 {grade}). "
                f"{grade_desc}"
            ),
            current_value=overall,
            ideal_value=75.0,
            confidence=0.88,
        )

    # =========================================================================
    # 유틸리티
    # =========================================================================
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"DefensiveFeedbackGenerator(generated={self._total_generated})"

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
        ideal_value: float | None = None,
        unit: str | None = None,
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
            ideal_value=ideal_value,
            unit=unit,
            confidence=confidence,
        )


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "DefensiveFeedbackGenerator",
    "DefensiveFeedbackConfig",
]

__version__ = "1.0.0"
