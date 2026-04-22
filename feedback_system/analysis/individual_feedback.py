# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: individual_feedback.py
설명: 개인 심층 피드백 생성기.
      - 슈팅 효율, 플레이메이킹, 수비 임팩트, 리바운딩
      - PlayerStats → FeedbackItem 변환
      - 선수별 강점/약점 세부 분석

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
from shared.dto.game_dto import PlayerStats

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.korean_templates import KoreanTemplates
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper, get_default_korean_templates


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class IndividualFeedbackConfig:
    """개인 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 15
    age_group: AgeGroup = AgeGroup.ADULT

    # 효율 기준
    ts_pct_good: float = 55.0           # TS% 55+ → 양호
    ast_to_good: float = 2.0            # AST/TO 2.0+ → 양호
    game_score_good: float = 15.0       # 게임스코어 15+ → 양호


# =============================================================================
# IndividualFeedbackGenerator 클래스
# =============================================================================
class IndividualFeedbackGenerator:
    """
    개인 심층 피드백 생성기.

    PlayerStats를 입력받아 개인 효율, 슈팅, 플레이메이킹,
    수비 임팩트 등의 세부 피드백을 생성합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: IndividualFeedbackConfig | None = None) -> None:
        self._config: IndividualFeedbackConfig = config or IndividualFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "IndividualFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def generate(
        self,
        player: PlayerStats,
    ) -> list[FeedbackItem]:
        """
        선수 통계에서 피드백 항목 생성.

        Args:
            player: 선수 통계 DTO

        Returns:
            FeedbackItem 목록 (최소 10개 이상)
        """
        items: list[FeedbackItem] = []
        cfg = self._config
        jersey = player.player_tracking_id

        # 1. 종합 효율
        game_score = player.calculate_game_score()
        gs_good = game_score >= cfg.game_score_good
        sev = self._severity_mapper.from_score(max(0.0, min(game_score * 3.0, 100.0)))
        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=FeedbackType.POSITIVE if gs_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.HIGH,
            title=f"#{jersey} 종합 효율",
            description=(
                f"게임스코어 {game_score:.1f}. "
                + ("경기에 큰 기여를 했습니다." if gs_good
                   else "효율성 개선이 필요합니다.")
            ),
            current_value=game_score,
            ideal_value=cfg.game_score_good,
            confidence=1.0,
        ))

        # 2. 득점 효율
        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=FeedbackType.POSITIVE if player.points >= 15 else FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title=f"#{jersey} 득점",
            description=(
                f"{player.points}득점 "
                f"({player.field_goals_made}/{player.field_goals_attempted} FG, "
                f"{player.three_pointers_made}/{player.three_pointers_attempted} 3PT). "
                + ("효율적인 득점을 올렸습니다." if player.field_goal_percentage >= 45
                   else "슈팅 효율 개선이 필요합니다.")
            ),
            current_value=float(player.points),
            confidence=1.0,
        ))

        # 3. 트루 슈팅 퍼센티지
        ts_pct = player.calculate_true_shooting_percentage()
        ts_good = ts_pct >= cfg.ts_pct_good
        sev_ts = self._severity_mapper.from_score(ts_pct)
        items.append(FeedbackItem(
            category=FeedbackCategory.RELEASE,
            feedback_type=FeedbackType.POSITIVE if ts_good else FeedbackType.CORRECTION,
            priority=self._severity_to_priority(sev_ts.severity),
            title=f"#{jersey} 트루 슈팅%",
            description=(
                f"TS% {ts_pct:.1f}%. "
                + ("효율적인 슈팅 선택을 하고 있습니다." if ts_good
                   else "슈팅 선택과 위치 개선이 필요합니다.")
            ),
            current_value=ts_pct,
            ideal_value=cfg.ts_pct_good,
            unit="percent",
            confidence=1.0,
        ))

        # 4. 유효 야투율
        efg = player.calculate_effective_field_goal_percentage()
        items.append(FeedbackItem(
            category=FeedbackCategory.POSTURE,
            feedback_type=FeedbackType.POSITIVE if efg >= 50 else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title=f"#{jersey} 유효 야투율",
            description=f"eFG% {efg:.1f}%. "
                        + ("3점슛 활용이 득점 효율을 높이고 있습니다." if efg >= 50
                           else "3점슛 효율이나 빈도를 조정해보세요."),
            current_value=efg,
            unit="percent",
            confidence=1.0,
        ))

        # 5. 플레이메이킹
        ast_to = player.calculate_assist_to_turnover_ratio()
        ast_to_good = ast_to >= cfg.ast_to_good
        items.append(FeedbackItem(
            category=FeedbackCategory.COORDINATION,
            feedback_type=FeedbackType.POSITIVE if ast_to_good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title=f"#{jersey} 플레이메이킹",
            description=(
                f"어시스트 {player.assists}개, 턴오버 {player.turnovers}개 "
                f"(AST/TO: {ast_to:.2f}). "
                + ("볼 핸들링과 판단력이 좋습니다." if ast_to_good
                   else "턴오버를 줄이고 더 안전한 패스를 선택하세요.")
            ),
            current_value=ast_to,
            ideal_value=cfg.ast_to_good,
            confidence=1.0,
        ))

        # 6. 리바운딩
        reb = player.total_rebounds
        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=FeedbackType.POSITIVE if reb >= 7 else FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title=f"#{jersey} 리바운딩",
            description=(
                f"총 리바운드 {reb}개 "
                f"(공격 {player.offensive_rebounds}, 수비 {player.defensive_rebounds}). "
                + ("공격적인 리바운딩이 2차 기회를 만들고 있습니다." if player.offensive_rebounds >= 3
                   else "박스아웃과 포지셔닝에 더 집중하세요." if reb < 5
                   else "안정적인 리바운딩을 보여주고 있습니다.")
            ),
            current_value=float(reb),
            confidence=1.0,
        ))

        # 7. 수비 임팩트
        defensive_actions = player.steals + player.blocks
        items.append(FeedbackItem(
            category=FeedbackCategory.FOOTWORK,
            feedback_type=FeedbackType.POSITIVE if defensive_actions >= 3 else FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title=f"#{jersey} 수비 임팩트",
            description=(
                f"스틸 {player.steals}개, 블락 {player.blocks}개. "
                + ("적극적인 수비로 상대에게 압박을 주고 있습니다." if defensive_actions >= 3
                   else "수비 적극성을 높여 상대의 실수를 유도해보세요.")
            ),
            current_value=float(defensive_actions),
            confidence=1.0,
        ))

        # 8. 파울 관리
        fouls = player.personal_fouls
        foul_ok = fouls <= 3
        items.append(FeedbackItem(
            category=FeedbackCategory.BALL_CONTROL,
            feedback_type=FeedbackType.POSITIVE if foul_ok else FeedbackType.WARNING,
            priority=FeedbackPriority.MEDIUM if foul_ok else FeedbackPriority.HIGH,
            title=f"#{jersey} 파울 관리",
            description=(
                f"파울 {fouls}개. "
                + ("파울 관리가 잘 되고 있습니다." if foul_ok
                   else "파울이 많아 퇴장 위험이 있습니다. 수비 시 몸 사용을 조절하세요.")
            ),
            current_value=float(fouls),
            confidence=1.0,
        ))

        # 9. 플러스/마이너스
        pm = player.plus_minus
        items.append(FeedbackItem(
            category=FeedbackCategory.RHYTHM,
            feedback_type=FeedbackType.POSITIVE if pm >= 0 else FeedbackType.CORRECTION,
            priority=FeedbackPriority.LOW,
            title=f"#{jersey} +/-",
            description=(
                f"+/- {pm:+d}. "
                + ("코트에 있을 때 팀이 더 나은 성과를 보여줍니다." if pm > 5
                   else "코트 기여도가 평균 수준입니다." if pm >= 0
                   else "코트에 있을 때 팀 성과가 저하됩니다. 역할 조정을 검토하세요.")
            ),
            current_value=float(pm),
            confidence=0.85,
        ))

        # 10. 3점슛 분석 (시도가 있는 경우)
        if player.three_pointers_attempted > 0:
            three_pct = player.three_point_percentage
            items.append(FeedbackItem(
                category=FeedbackCategory.RELEASE,
                feedback_type=FeedbackType.POSITIVE if three_pct >= 35 else FeedbackType.CORRECTION,
                priority=FeedbackPriority.MEDIUM,
                title=f"#{jersey} 3점슛",
                description=(
                    f"3점슛 {player.three_pointers_made}/{player.three_pointers_attempted} "
                    f"({three_pct:.1f}%). "
                    + ("3점슛이 팀 공격에 큰 도움이 됩니다." if three_pct >= 35
                       else "3점슛 확률이 낮습니다. 슈팅 위치와 셀렉션을 점검하세요.")
                ),
                current_value=three_pct,
                unit="percent",
                confidence=1.0,
            ))

        # 11. 자유투 효율
        if player.free_throws_attempted > 0:
            ft_pct = player.free_throw_percentage
            ft_good = ft_pct >= 75
            items.append(FeedbackItem(
                category=FeedbackCategory.RELEASE,
                feedback_type=FeedbackType.POSITIVE if ft_good else FeedbackType.CORRECTION,
                priority=FeedbackPriority.MEDIUM,
                title=f"#{jersey} 자유투",
                description=(
                    f"자유투 {player.free_throws_made}/{player.free_throws_attempted} "
                    f"({ft_pct:.1f}%). "
                    + ("안정적인 자유투로 공짜 득점을 잘 챙기고 있습니다." if ft_good
                       else "자유투 성공률이 낮습니다. 루틴과 릴리스 포인트를 점검하세요.")
                ),
                current_value=ft_pct,
                unit="percent",
                confidence=1.0,
            ))

        # 12. 슈팅 선택 밸런스 (2pt vs 3pt)
        if player.field_goals_attempted > 0:
            two_pt_att = player.field_goals_attempted - player.three_pointers_attempted
            three_ratio = player.three_pointers_attempted / player.field_goals_attempted * 100
            items.append(FeedbackItem(
                category=FeedbackCategory.POSTURE,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title=f"#{jersey} 슈팅 선택",
                description=(
                    f"2점슛 {two_pt_att}회 vs 3점슛 {player.three_pointers_attempted}회 "
                    f"(3점 비율 {three_ratio:.0f}%). "
                    + ("3점슛 비중이 높은 외곽 중심 플레이어입니다." if three_ratio >= 50
                       else "근중거리 중심의 슈팅 패턴을 보이고 있습니다." if three_ratio < 25
                       else "균형 잡힌 슈팅 포트폴리오입니다.")
                ),
                current_value=three_ratio,
                unit="percent",
                confidence=0.9,
            ))

        # 13. 효율성 지수 (PIR/EFF)
        eff = player.calculate_efficiency()
        items.append(FeedbackItem(
            category=FeedbackCategory.BALANCE,
            feedback_type=FeedbackType.POSITIVE if eff >= 15 else (
                FeedbackType.TIP if eff >= 5 else FeedbackType.CORRECTION
            ),
            priority=FeedbackPriority.MEDIUM,
            title=f"#{jersey} 효율성 지수",
            description=(
                f"EFF(PIR) {eff:.1f}. "
                + ("매우 높은 효율성으로 경기에 큰 임팩트를 주고 있습니다." if eff >= 20
                   else "양호한 효율성을 보여주고 있습니다." if eff >= 10
                   else "효율성 지수가 낮습니다. 득점 외에도 리바운드, 어시스트 등 다방면 기여가 필요합니다." if eff < 5
                   else "평균적인 효율성입니다. 적극적인 참여로 임팩트를 높여보세요.")
            ),
            current_value=eff,
            confidence=1.0,
        ))

        # 14. 더블더블/트리플더블 마일스톤
        is_dd = player.is_double_double()
        is_td = player.is_triple_double()
        if is_td:
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.HIGH,
                title=f"#{jersey} 트리플-더블",
                description=(
                    f"트리플-더블 달성! {player.points}득점 {player.total_rebounds}리바운드 "
                    f"{player.assists}어시스트. 올라운드 활약이 돋보입니다."
                ),
                confidence=1.0,
            ))
        elif is_dd:
            items.append(FeedbackItem(
                category=FeedbackCategory.COORDINATION,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.HIGH,
                title=f"#{jersey} 더블-더블",
                description=(
                    f"더블-더블 달성! {player.points}득점 {player.total_rebounds}리바운드 "
                    f"{player.assists}어시스트. 다재다능한 활약을 보여주고 있습니다."
                ),
                confidence=1.0,
            ))

        # 15. 득점 구성 분석
        if player.points > 0:
            pts_2pt = (player.field_goals_made - player.three_pointers_made) * 2
            pts_3pt = player.three_pointers_made * 3
            pts_ft = player.free_throws_made
            items.append(FeedbackItem(
                category=FeedbackCategory.POWER,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title=f"#{jersey} 득점 구성",
                description=(
                    f"총 {player.points}점 = 2점슛 {pts_2pt}점 + 3점슛 {pts_3pt}점 "
                    f"+ 자유투 {pts_ft}점. "
                    + ("3점슛 중심의 외곽 득점 패턴입니다." if pts_3pt > pts_2pt
                       else "근거리 공격 중심의 내곽 득점 패턴입니다." if pts_2pt >= pts_3pt * 2
                       else "균형 잡힌 득점 분포를 보이고 있습니다.")
                ),
                current_value=float(player.points),
                confidence=0.9,
            ))

        # 16. 턴오버 부담
        if player.field_goals_attempted > 0:
            usage_approx = player.field_goals_attempted + 0.44 * player.free_throws_attempted + player.turnovers
            tov_rate = player.turnovers / usage_approx * 100 if usage_approx > 0 else 0.0
            tov_ok = tov_rate < 15
            items.append(FeedbackItem(
                category=FeedbackCategory.BALL_CONTROL,
                feedback_type=FeedbackType.POSITIVE if tov_ok else FeedbackType.CORRECTION,
                priority=FeedbackPriority.MEDIUM if tov_ok else FeedbackPriority.HIGH,
                title=f"#{jersey} 턴오버 부담",
                description=(
                    f"턴오버율 {tov_rate:.1f}% ({player.turnovers}개 / 사용 {usage_approx:.0f}회). "
                    + ("볼 관리가 안정적입니다." if tov_ok
                       else "턴오버 비율이 높습니다. 패스 판단을 신중하게 하고 볼 보호에 집중하세요.")
                ),
                current_value=tov_rate,
                unit="percent",
                confidence=0.9,
            ))

        # 17. 공격 리바운드 기여
        orb = player.offensive_rebounds
        items.append(FeedbackItem(
            category=FeedbackCategory.POWER,
            feedback_type=FeedbackType.POSITIVE if orb >= 3 else FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title=f"#{jersey} 공격 리바운드",
            description=(
                f"공격 리바운드 {orb}개. "
                + ("적극적인 오펜시브 리바운드로 세컨드 찬스를 만들고 있습니다." if orb >= 3
                   else "공격 리바운드 참여를 높여 추가 공격 기회를 확보해보세요." if orb < 1
                   else "적절한 수준의 공격 리바운드 참여입니다.")
            ),
            current_value=float(orb),
            confidence=0.9,
        ))

        with self._lock:
            self._total_generated += 1

        return items

    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"IndividualFeedbackGenerator(generated={self._total_generated})"

    @staticmethod
    def _severity_to_priority(severity: FeedbackSeverity) -> FeedbackPriority:
        return FeedbackFormatter.severity_to_priority(severity)


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "IndividualFeedbackGenerator",
    "IndividualFeedbackConfig",
]

__version__ = "1.0.0"
