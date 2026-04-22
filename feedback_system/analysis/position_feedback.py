# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: position_feedback.py
설명: 포지션별 맞춤 피드백 생성기.
      - 포지션 추정 (스탯 기반: 가드/포워드/센터)
      - 포지션별 기대 역할 대비 실제 수행 평가
      - 포지션별 핵심 지표 비교 (가드: AST/TO, 포워드: 3P%/REB, 센터: 페인트/블록)
      - 포지션별 맞춤 개선 제안
      - PlayerStats → FeedbackItem 변환

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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
# 포지션 열거형 (내부 추정용)
# =============================================================================
class _EstimatedPosition(str, Enum):
    """스탯 기반 추정 포지션."""
    GUARD = "guard"           # 가드 (PG/SG)
    FORWARD = "forward"       # 포워드 (SF/PF)
    CENTER = "center"         # 센터 (C)


# =============================================================================
# 포지션별 기대 벤치마크
# =============================================================================
@dataclass(slots=True, frozen=True)
class _PositionBenchmark:
    """포지션별 기대 지표."""
    position: _EstimatedPosition
    ast_good: float           # 어시스트 기대 수준
    reb_good: float           # 리바운드 기대 수준
    stl_good: float           # 스틸 기대 수준
    blk_good: float           # 블록 기대 수준
    fg_pct_good: float        # FG% 기대 수준
    to_max: int               # 턴오버 최대 허용
    role_desc: str            # 역할 설명


_BENCHMARKS: dict[_EstimatedPosition, _PositionBenchmark] = {
    _EstimatedPosition.GUARD: _PositionBenchmark(
        position=_EstimatedPosition.GUARD,
        ast_good=5.0, reb_good=3.0, stl_good=1.5, blk_good=0.3,
        fg_pct_good=42.0, to_max=3,
        role_desc="코트 매니저로서 공격 조직, 볼 핸들링, 수비 압박이 핵심",
    ),
    _EstimatedPosition.FORWARD: _PositionBenchmark(
        position=_EstimatedPosition.FORWARD,
        ast_good=2.5, reb_good=6.0, stl_good=1.0, blk_good=0.7,
        fg_pct_good=44.0, to_max=2,
        role_desc="양방향 활약(득점+리바운드), 3점슛 스페이싱, 수비 전환이 핵심",
    ),
    _EstimatedPosition.CENTER: _PositionBenchmark(
        position=_EstimatedPosition.CENTER,
        ast_good=1.5, reb_good=8.0, stl_good=0.5, blk_good=1.5,
        fg_pct_good=50.0, to_max=2,
        role_desc="페인트존 지배(리바운드+블록), 림 프로텍션, 픽앤롤 마무리가 핵심",
    ),
}


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class PositionFeedbackConfig:
    """포지션별 맞춤 피드백 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    # 포지션 추정 기준
    guard_ast_threshold: float = 3.0    # AST 3+ → 가드 유력
    center_reb_threshold: float = 6.0   # REB 6+ → 센터 유력
    center_blk_threshold: float = 1.0   # BLK 1+ → 센터 보조 지표

    # 최소 출장 기준 (의미 있는 분석을 위한 최소 기여)
    min_contribution: int = 5           # 득점+리바운드+어시스트 합산 5 이상


# =============================================================================
# PositionFeedbackGenerator 클래스
# =============================================================================
class PositionFeedbackGenerator:
    """
    포지션별 맞춤 피드백 생성기.

    PlayerStats 기반으로 포지션을 추정하고,
    포지션별 기대 역할 대비 실제 수행을 평가하여 맞춤 피드백을 생성합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: PositionFeedbackConfig | None = None) -> None:
        self._config: PositionFeedbackConfig = config or PositionFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "PositionFeedbackGenerator"

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
        경기 통계에서 포지션별 맞춤 피드백 생성.

        Args:
            game_stats: 경기 전체 통계

        Returns:
            FeedbackItem 목록 (15+ 항목)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        # 양 팀 선수 수집
        all_players: list[tuple[PlayerStats, bool]] = []
        if game_stats.home_team_stats is not None:
            all_players.extend((ps, True) for ps in game_stats.home_team_stats.player_stats)
        if game_stats.away_team_stats is not None:
            all_players.extend((ps, False) for ps in game_stats.away_team_stats.player_stats)

        # 최소 기여 선수만 분석
        for ps, is_home in all_players:
            contribution = ps.points + ps.total_rebounds + ps.assists
            if contribution >= cfg.min_contribution:
                pos = self._estimate_position(ps)
                items.extend(self._evaluate_position_performance(ps, pos, is_home=is_home))

        # 팀 포지션 밸런스 분석
        if game_stats.home_team_stats is not None:
            items.extend(self._analyze_team_position_balance(
                game_stats.home_team_stats, is_home=True,
            ))

        # 최소 항목 보장
        if len(items) < cfg.min_items:
            items.extend(self._generate_baseline_feedback())

        with self._lock:
            self._total_generated += 1

        return items[:cfg.max_items]

    # -------------------------------------------------------------------------
    # 포지션 추정
    # -------------------------------------------------------------------------
    def _estimate_position(self, player: PlayerStats) -> _EstimatedPosition:
        """스탯 기반 포지션 추정."""
        cfg = self._config

        # 센터 판별: 리바운드 높고 블록 높음
        if (player.total_rebounds >= cfg.center_reb_threshold
                and player.blocks >= cfg.center_blk_threshold):
            return _EstimatedPosition.CENTER

        # 가드 판별: 어시스트 높음
        if player.assists >= cfg.guard_ast_threshold:
            return _EstimatedPosition.GUARD

        # 센터 판별 (리바운드만으로)
        if player.total_rebounds >= cfg.center_reb_threshold:
            return _EstimatedPosition.CENTER

        # 기본: 포워드
        return _EstimatedPosition.FORWARD

    # -------------------------------------------------------------------------
    # 포지션별 수행 평가
    # -------------------------------------------------------------------------
    def _evaluate_position_performance(
        self,
        player: PlayerStats,
        position: _EstimatedPosition,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """포지션별 기대 역할 대비 실제 수행 평가."""
        items: list[FeedbackItem] = []
        bm = _BENCHMARKS[position]
        pid = f"선수#{player.player_tracking_id}"
        label = "홈팀" if is_home else "어웨이팀"
        pos_name = {"guard": "가드", "forward": "포워드", "center": "센터"}[position.value]

        # 포지션 판별 결과
        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title=f"{label} {pid} — 추정 포지션: {pos_name}",
            description=(
                f"{label} {pid}의 스탯 프로필(AST {player.assists}, REB {player.total_rebounds}, "
                f"BLK {player.blocks})을 기반으로 {pos_name} 역할로 추정됩니다. "
                f"{pos_name}의 핵심 역할: {bm.role_desc}"
            ),
            confidence=0.75,
        ))

        # 어시스트 평가
        if position == _EstimatedPosition.GUARD:
            if player.assists >= bm.ast_good:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    title=f"{pid} 가드 어시스트 우수 ({player.assists}개)",
                    description=(
                        f"{pid}이 {player.assists}어시스트로 가드 역할을 충실히 수행했습니다. "
                        f"기대 수준({bm.ast_good}개) 이상의 공격 조직력을 보였습니다."
                    ),
                    current_value=float(player.assists),
                    ideal_value=bm.ast_good,
                    confidence=0.82,
                ))
            elif player.assists < bm.ast_good * 0.5:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.MEDIUM,
                    title=f"{pid} 가드 어시스트 부족 ({player.assists}개)",
                    description=(
                        f"{pid}이 {player.assists}어시스트로 가드 기대 수준({bm.ast_good}개)에 "
                        "크게 미달합니다. 개인 득점에 치우치거나 팀 동료 활용이 부족합니다."
                    ),
                    suggestion="픽앤롤 후 롤맨 패스, 드라이브 킥아웃 패스 빈도를 높이세요.",
                    current_value=float(player.assists),
                    ideal_value=bm.ast_good,
                    confidence=0.80,
                ))

        # 리바운드 평가 (포워드/센터)
        if position in (_EstimatedPosition.FORWARD, _EstimatedPosition.CENTER):
            if player.total_rebounds >= bm.reb_good:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    title=f"{pid} {pos_name} 리바운드 우수 ({player.total_rebounds}개)",
                    description=(
                        f"{pid}이 {player.total_rebounds}리바운드로 "
                        f"{pos_name} 기대 수준({bm.reb_good}개) 이상의 보드 장악력을 보였습니다."
                    ),
                    current_value=float(player.total_rebounds),
                    ideal_value=bm.reb_good,
                    confidence=0.82,
                ))
            elif player.total_rebounds < bm.reb_good * 0.5:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.IMPROVEMENT,
                    priority=FeedbackPriority.MEDIUM,
                    title=f"{pid} {pos_name} 리바운드 부족 ({player.total_rebounds}개)",
                    description=(
                        f"{pid}이 {player.total_rebounds}리바운드로 "
                        f"{pos_name} 기대 수준({bm.reb_good}개)에 크게 미달합니다. "
                        "박스아웃 적극성과 포지셔닝 개선이 필요합니다."
                    ),
                    suggestion="리바운드 포지셔닝과 박스아웃 타이밍 훈련에 집중하세요.",
                    current_value=float(player.total_rebounds),
                    ideal_value=bm.reb_good,
                    confidence=0.80,
                ))

        # 블록 평가 (센터)
        if position == _EstimatedPosition.CENTER:
            if player.blocks >= bm.blk_good:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    title=f"{pid} 센터 림 프로텍션 우수 ({player.blocks}블록)",
                    description=(
                        f"{pid}이 {player.blocks}블록으로 페인트존 수비 역할을 "
                        "효과적으로 수행했습니다. 상대 페인트존 공격을 억제하는 데 기여했습니다."
                    ),
                    current_value=float(player.blocks),
                    ideal_value=bm.blk_good,
                    confidence=0.82,
                ))

        # 턴오버 평가
        if player.turnovers > bm.to_max:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.MEDIUM,
                title=f"{pid} {pos_name} 턴오버 과다 ({player.turnovers}개)",
                description=(
                    f"{pid}이 {player.turnovers}턴오버로 {pos_name} 허용 수준({bm.to_max}개)을 "
                    "초과했습니다. 볼 보호와 의사결정 개선이 필요합니다."
                ),
                current_value=float(player.turnovers),
                ideal_value=float(bm.to_max),
                confidence=0.82,
            ))

        # FG% 평가
        if player.field_goals_attempted >= 5:
            fg = player.field_goal_percentage
            if fg >= bm.fg_pct_good:
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.POSITIVE,
                    priority=FeedbackPriority.LOW,
                    title=f"{pid} {pos_name} 슈팅 효율 우수 (FG {fg:.1f}%)",
                    description=(
                        f"{pid}의 FG% {fg:.1f}%로 {pos_name} 기대 수준({bm.fg_pct_good}%) 이상입니다."
                    ),
                    current_value=fg,
                    ideal_value=bm.fg_pct_good,
                    unit="percent",
                    confidence=0.80,
                ))

        return items

    # -------------------------------------------------------------------------
    # 팀 포지션 밸런스
    # -------------------------------------------------------------------------
    def _analyze_team_position_balance(
        self,
        team: TeamStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """팀 내 포지션 밸런스 분석."""
        items: list[FeedbackItem] = []
        label = "홈팀" if is_home else "어웨이팀"

        pos_counts: dict[str, int] = {"guard": 0, "forward": 0, "center": 0}
        for ps in team.player_stats:
            contribution = ps.points + ps.total_rebounds + ps.assists
            if contribution >= self._config.min_contribution:
                pos = self._estimate_position(ps)
                pos_counts[pos.value] += 1

        total_active = sum(pos_counts.values())
        if total_active >= 3:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title=f"{label} 포지션 분포: 가드 {pos_counts['guard']} / 포워드 {pos_counts['forward']} / 센터 {pos_counts['center']}",
                description=(
                    f"{label} 활약 선수 {total_active}명의 포지션 분포입니다. "
                    "균형 잡힌 포지션 활용이 전술 다양성의 기반입니다."
                ),
                confidence=0.72,
            ))

        return items

    # -------------------------------------------------------------------------
    # 최소 항목 보장
    # -------------------------------------------------------------------------
    def _generate_baseline_feedback(self) -> list[FeedbackItem]:
        """최소 피드백 항목 보장."""
        items: list[FeedbackItem] = []
        for pos, bm in _BENCHMARKS.items():
            pos_name = {"guard": "가드", "forward": "포워드", "center": "센터"}[pos.value]
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title=f"[포지션 가이드] {pos_name} 핵심 역할",
                description=f"{pos_name}: {bm.role_desc}",
                confidence=0.75,
            ))
        return items

    # -------------------------------------------------------------------------
    # 리셋 / repr
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"PositionFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "PositionFeedbackGenerator",
    "PositionFeedbackConfig",
]

__version__ = "1.0.0"
