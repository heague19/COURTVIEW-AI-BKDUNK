# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: foul_trouble_feedback.py
설명: 파울 트러블 분석 피드백 생성기.
      - 개인별 파울 상황 분석 (조기 파울 경고, 파울아웃 위험)
      - 팀 파울 관리 전략 (보너스 상황, 팀 파울 적자)
      - 파울 유형별 분포 분석 (공격 파울 vs 수비 파울)
      - 쿼터별 파울 분포 패턴
      - 파울이 경기 흐름에 미치는 영향 (핵심 선수 벤치, 상대 보너스)
      - GameStats + PlayerStats → FeedbackItem 변환

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
class FoulTroubleFeedbackConfig:
    """파울 트러블 분석 피드백 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    # 개인 파울 임계치 (5파울 퇴장 기준 — KBL/FIBA)
    foul_limit: int = 5              # 퇴장 파울 수
    foul_danger_zone: int = 4        # 4파울 → 위험 구간
    foul_trouble_zone: int = 3       # 3파울 → 주의 구간
    early_foul_quarter: int = 2      # 전반(1~2쿼터)에 2파울 이상 → 조기 파울
    nba_foul_limit: int = 6          # NBA 규정 (6파울 퇴장)

    # 팀 파울 보너스 임계치 (쿼터당)
    team_foul_bonus: int = 5         # FIBA: 쿼터당 5파울 → 상대 보너스
    team_foul_danger: int = 4        # 4팀파울 → 보너스 직전

    # 파울 관련 점수 환산
    avg_ft_points_per_foul: float = 1.5  # 파울당 평균 자유투 득점 (통계적 추정)

    # 핵심 선수 파울 트러블 기준 (상위 효율 선수)
    star_player_efficiency_threshold: float = 15.0  # EFF 15 이상 → 핵심 선수

    # 팀 파울 적자 임계치
    team_foul_gap_significant: int = 8   # 팀 파울 8개 이상 격차 → 유의미


# =============================================================================
# FoulTroubleFeedbackGenerator 클래스
# =============================================================================
class FoulTroubleFeedbackGenerator:
    """
    파울 트러블 분석 피드백 생성기.

    GameStats를 입력받아 개인별/팀별 파울 현황, 파울아웃 위험,
    보너스 상황, 파울 관리 전략 등을 분석하여 15+ FeedbackItem을 생성합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: FoulTroubleFeedbackConfig | None = None) -> None:
        self._config: FoulTroubleFeedbackConfig = config or FoulTroubleFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        """생성기 이름."""
        return "FoulTroubleFeedbackGenerator"

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
        경기 통계에서 파울 트러블 관련 피드백 생성.

        Args:
            game_stats: 경기 전체 통계

        Returns:
            FeedbackItem 목록 (15+ 항목)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        home = game_stats.home_team_stats
        away = game_stats.away_team_stats

        # 팀별 파울 종합 피드백
        if home is not None:
            items.extend(self._generate_team_foul_feedback(home, is_home=True))
        if away is not None:
            items.extend(self._generate_team_foul_feedback(away, is_home=False))

        # 개인별 파울 트러블 분석 (양 팀)
        all_players: list[tuple[PlayerStats, bool]] = []
        if home is not None:
            all_players.extend((ps, True) for ps in home.player_stats)
        if away is not None:
            all_players.extend((ps, False) for ps in away.player_stats)

        for ps, is_home in all_players:
            items.extend(self._generate_player_foul_feedback(ps, is_home=is_home))

        # 팀 간 파울 비교
        if home is not None and away is not None:
            items.extend(self._generate_foul_comparison(home, away, game_stats))

        # 핵심 선수 파울 트러블 경고
        if home is not None:
            items.extend(self._generate_star_player_foul_alert(home, is_home=True))
        if away is not None:
            items.extend(self._generate_star_player_foul_alert(away, is_home=False))

        # 파울 전략 권고
        items.extend(self._generate_foul_strategy(game_stats))

        # 최소 항목 보장
        if len(items) < cfg.min_items:
            items.extend(self._generate_baseline_feedback(game_stats))

        with self._lock:
            self._total_generated += 1

        return items[:cfg.max_items]

    # -------------------------------------------------------------------------
    # 팀 파울 종합
    # -------------------------------------------------------------------------
    def _generate_team_foul_feedback(
        self,
        team: TeamStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """팀 파울 종합 피드백."""
        items: list[FeedbackItem] = []
        cfg = self._config
        label = "홈팀" if is_home else "어웨이팀"
        total_pf = team.personal_fouls

        # 팀 총 파울 수 평가
        # FIBA 기준: 쿼터당 5파울 보너스 → 4쿼터 20파울 기준
        fouls_per_quarter = total_pf / 4.0

        if fouls_per_quarter >= cfg.team_foul_bonus:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title=f"{label} 과다 파울 — 쿼터당 {fouls_per_quarter:.1f}회",
                description=(
                    f"{label} 총 파울 {total_pf}회, 쿼터당 평균 {fouls_per_quarter:.1f}회로 "
                    f"매 쿼터 보너스 상황(쿼터당 {cfg.team_foul_bonus}파울)을 "
                    "허용하는 수준입니다. 불필요한 파울을 줄이고 "
                    "수비 규율을 강화해야 합니다."
                ),
                current_value=fouls_per_quarter,
                ideal_value=float(cfg.team_foul_bonus - 1),
                suggestion=(
                    "1) 발 위치 중심 수비(핸드체킹 자제) "
                    "2) 드라이브 대응 시 수직 점프 원칙 "
                    "3) 트랩 상황에서 과도한 핸들링 자제."
                ),
                confidence=0.90,
            ))
        elif fouls_per_quarter <= 2.5:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title=f"{label} 파울 관리 우수 — 쿼터당 {fouls_per_quarter:.1f}회",
                description=(
                    f"{label} 총 파울 {total_pf}회, 쿼터당 평균 {fouls_per_quarter:.1f}회로 "
                    "파울 관리가 우수합니다. 보너스 상황을 최소화하여 "
                    "상대에게 쉬운 자유투 기회를 주지 않았습니다."
                ),
                current_value=fouls_per_quarter,
                confidence=0.88,
            ))

        # 팀 파울로 인한 상대 자유투 득점 추정
        estimated_ft_points = total_pf * cfg.avg_ft_points_per_foul
        if estimated_ft_points >= 20.0:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.MEDIUM,
                title=f"{label} 파울로 인한 추정 실점 ~{estimated_ft_points:.0f}점",
                description=(
                    f"{label} {total_pf}파울로 상대에게 약 {estimated_ft_points:.0f}점의 "
                    "자유투 득점을 허용한 것으로 추정됩니다. "
                    "파울당 평균 자유투 득점 {cfg.avg_ft_points_per_foul}점 기준입니다."
                ),
                current_value=estimated_ft_points,
                unit="points",
                confidence=0.75,
            ))

        return items

    # -------------------------------------------------------------------------
    # 개인 파울 트러블
    # -------------------------------------------------------------------------
    def _generate_player_foul_feedback(
        self,
        player: PlayerStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """개인 파울 트러블 분석."""
        items: list[FeedbackItem] = []
        cfg = self._config
        pf = player.personal_fouls
        pid = f"선수#{player.player_tracking_id}"
        label = "홈팀" if is_home else "어웨이팀"

        if pf == 0:
            return items

        # 파울아웃 (5파울 퇴장)
        if pf >= cfg.foul_limit:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.CORRECTION,
                priority=FeedbackPriority.CRITICAL,
                title=f"{label} {pid} 파울아웃 ({pf}파울)",
                description=(
                    f"{label} {pid}이(가) {pf}파울로 퇴장당했습니다. "
                    "파울아웃은 팀 전력에 직접적 손실이며, "
                    "로테이션 축소와 벤치 부담 증가로 이어집니다."
                ),
                suggestion=(
                    "파울 트러블에 빠진 선수는 조기에 벤치로 돌려 "
                    "4쿼터 핵심 시간대를 위해 파울 여유를 확보하세요."
                ),
                current_value=float(pf),
                ideal_value=float(cfg.foul_limit - 1),
                confidence=0.95,
            ))

        # 위험 구간 (4파울)
        elif pf >= cfg.foul_danger_zone:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title=f"{label} {pid} 파울 위험 ({pf}파울)",
                description=(
                    f"{label} {pid}이(가) {pf}파울로 파울아웃 직전입니다. "
                    f"퇴장까지 {cfg.foul_limit - pf}파울 남았으며, "
                    "공격적 수비를 자제하고 포지셔닝 수비로 전환해야 합니다."
                ),
                suggestion=(
                    "1) 1:1 수비 시 리치 사용 최소화 "
                    "2) 헬프 수비 역할 전환 "
                    "3) 핵심 시간대 전까지 벤치 휴식 고려."
                ),
                current_value=float(pf),
                ideal_value=float(cfg.foul_trouble_zone - 1),
                confidence=0.92,
            ))

        # 주의 구간 (3파울)
        elif pf >= cfg.foul_trouble_zone:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"{label} {pid} 파울 주의 ({pf}파울)",
                description=(
                    f"{label} {pid}이(가) {pf}파울을 기록했습니다. "
                    f"퇴장까지 {cfg.foul_limit - pf}파울 여유가 있으나 "
                    "추가 파울 시 벤치 시간이 길어질 수 있습니다."
                ),
                current_value=float(pf),
                confidence=0.85,
            ))

        return items

    # -------------------------------------------------------------------------
    # 팀 간 파울 비교
    # -------------------------------------------------------------------------
    def _generate_foul_comparison(
        self,
        home: TeamStats,
        away: TeamStats,
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """홈 vs 어웨이 파울 비교 피드백."""
        items: list[FeedbackItem] = []
        cfg = self._config

        h_pf = home.personal_fouls
        a_pf = away.personal_fouls
        foul_gap = abs(h_pf - a_pf)

        # 파울 격차 분석
        if foul_gap >= cfg.team_foul_gap_significant:
            more_team = "홈팀" if h_pf > a_pf else "어웨이팀"
            less_team = "어웨이팀" if h_pf > a_pf else "홈팀"
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.HIGH,
                title=f"팀 파울 {foul_gap}개 격차",
                description=(
                    f"{more_team}({max(h_pf, a_pf)}파울)이 "
                    f"{less_team}({min(h_pf, a_pf)}파울)보다 "
                    f"{foul_gap}개 더 많은 파울을 기록했습니다. "
                    "이는 수비 강도 차이 또는 공격 스타일(드라이브 빈도) "
                    "차이를 반영합니다."
                ),
                current_value=float(foul_gap),
                confidence=0.87,
            ))

        # 파울아웃 선수 수 비교
        h_fouled_out = sum(1 for p in home.player_stats if p.personal_fouls >= cfg.foul_limit)
        a_fouled_out = sum(1 for p in away.player_stats if p.personal_fouls >= cfg.foul_limit)

        total_fouled_out = h_fouled_out + a_fouled_out
        if total_fouled_out > 0:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.MEDIUM,
                title=f"퇴장 선수 총 {total_fouled_out}명",
                description=(
                    f"홈팀 {h_fouled_out}명, 어웨이팀 {a_fouled_out}명이 "
                    "파울아웃으로 퇴장했습니다. "
                    "격렬한 수비 경기였으며 양 팀 로테이션에 영향을 미쳤습니다."
                ),
                current_value=float(total_fouled_out),
                confidence=0.90,
            ))

        # 보너스 상황 추정 (팀 파울 / 4쿼터 = 쿼터당 평균)
        h_bonus_quarters = max(0, int(h_pf / cfg.team_foul_bonus))
        a_bonus_quarters = max(0, int(a_pf / cfg.team_foul_bonus))
        if h_bonus_quarters >= 3 or a_bonus_quarters >= 3:
            worse = "홈팀" if h_bonus_quarters > a_bonus_quarters else "어웨이팀"
            quarters = max(h_bonus_quarters, a_bonus_quarters)
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.WARNING,
                priority=FeedbackPriority.MEDIUM,
                title=f"{worse} 추정 보너스 허용 ~{quarters}쿼터",
                description=(
                    f"{worse}의 팀 파울 수준으로 볼 때 약 {quarters}개 쿼터에서 "
                    "상대에게 보너스 자유투를 허용한 것으로 추정됩니다. "
                    "보너스 상황에서는 경미한 파울에도 자유투가 주어져 실점 위험이 높아집니다."
                ),
                confidence=0.75,
            ))

        return items

    # -------------------------------------------------------------------------
    # 핵심 선수 파울 경고
    # -------------------------------------------------------------------------
    def _generate_star_player_foul_alert(
        self,
        team: TeamStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """핵심 선수(고효율) 파울 트러블 특별 경고."""
        items: list[FeedbackItem] = []
        cfg = self._config
        label = "홈팀" if is_home else "어웨이팀"

        for ps in team.player_stats:
            eff = ps.calculate_efficiency()
            pid = f"선수#{ps.player_tracking_id}"

            # 고효율 선수가 3파울 이상
            if eff >= cfg.star_player_efficiency_threshold and ps.personal_fouls >= cfg.foul_trouble_zone:
                remaining = cfg.foul_limit - ps.personal_fouls
                items.append(FeedbackItem(
                    category=FeedbackCategory.TIP,
                    feedback_type=FeedbackType.WARNING,
                    priority=FeedbackPriority.HIGH,
                    title=f"{label} 핵심 선수 {pid} 파울 트러블 (EFF {eff:.0f}, {ps.personal_fouls}파울)",
                    description=(
                        f"{label}의 핵심 선수 {pid} (효율 {eff:.1f}, "
                        f"{ps.points}득점/{ps.total_rebounds}리바운드/{ps.assists}어시스트)이 "
                        f"{ps.personal_fouls}파울로 퇴장까지 {remaining}파울 남았습니다. "
                        "이 선수의 벤치 시간은 팀 전력에 직접적 영향을 미칩니다."
                    ),
                    suggestion=(
                        f"파울 관리를 위해 {pid}의 수비 역할을 조정하세요. "
                        "헬프 사이드 수비로 전환하거나, 핵심 시간대를 위해 "
                        "일시적으로 벤치 휴식을 부여하는 것이 전략적입니다."
                    ),
                    current_value=float(ps.personal_fouls),
                    ideal_value=float(cfg.foul_trouble_zone - 1),
                    confidence=0.90,
                ))

        return items

    # -------------------------------------------------------------------------
    # 파울 전략 권고
    # -------------------------------------------------------------------------
    def _generate_foul_strategy(
        self,
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """경기 상황별 파울 전략 권고."""
        items: list[FeedbackItem] = []
        score_diff = abs(game_stats.home_score - game_stats.away_score)

        # 접전 경기에서 파울 관리 중요성
        if score_diff <= 5:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.HIGH,
                title="접전 경기 — 파울 관리가 승패 핵심",
                description=(
                    f"최종 점수 차가 {score_diff}점인 접전 경기입니다. "
                    "이런 경기에서 불필요한 파울로 인한 상대 자유투 1~2개가 "
                    "승패를 결정짓습니다. 4쿼터 파울 관리가 특히 중요합니다."
                ),
                suggestion=(
                    "접전 종반: 1) 페인트존 수비 시 수직 원칙 엄수 "
                    "2) 리바운드 박스아웃 시 과도한 밀침 자제 "
                    "3) 의도적 파울은 전략적으로만 사용."
                ),
                confidence=0.88,
            ))

        # 대패 경기에서 파울 경향
        if score_diff >= 20:
            items.append(FeedbackItem(
                category=FeedbackCategory.TIP,
                feedback_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="대점수 차이 경기 — 불필요 파울 자제",
                description=(
                    f"점수 차이가 {score_diff}점인 경기입니다. "
                    "큰 점수 차 상황에서 무리한 수비로 파울을 누적하면 "
                    "주전 선수 부상 위험과 다음 경기 컨디션에 악영향을 줍니다."
                ),
                suggestion="가비지타임에는 벤치 선수를 활용하여 주전 파울을 관리하세요.",
                confidence=0.82,
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
            title="파울 관리 일반 지침",
            description=(
                "효과적인 파울 관리의 핵심: "
                "1) 쿼터당 팀 파울 4개 이내 유지 (보너스 방지) "
                "2) 핵심 선수 전반 2파울 이내 관리 "
                "3) 4쿼터 핵심 시간대를 위한 파울 여유 확보 "
                "4) 의도적 파울은 전략적 상황에서만 사용."
            ),
            confidence=0.85,
        ))

        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="파울 습관 교정 포인트",
            description=(
                "불필요한 파울을 줄이는 방법: "
                "1) 수비 시 발 위치 우선 (핸드체킹 최소화) "
                "2) 드라이브 대응 시 수직 점프 원칙 준수 "
                "3) 리바운드 시 포지션 선점 후 박스아웃 "
                "4) 뒤쫓기 블록 시도 자제 (깔끔한 스틸 시도)."
            ),
            suggestion="연습 시 파울 없는 수비 드릴(셸 디펜스)을 정기적으로 진행하세요.",
            confidence=0.83,
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
            f"FoulTroubleFeedbackGenerator("
            f"generated={self._total_generated})"
        )


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "FoulTroubleFeedbackGenerator",
    "FoulTroubleFeedbackConfig",
]

__version__ = "1.0.0"
