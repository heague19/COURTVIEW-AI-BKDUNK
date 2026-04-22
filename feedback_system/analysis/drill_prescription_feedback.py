# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: drill_prescription_feedback.py
설명: 구체적 드릴 처방 피드백 생성기.
      - 분석 결과 기반 개인 맞춤형 훈련 드릴 추천
      - 약점 영역별 교정 드릴 (슈팅/드리블/수비/피니시/자유투)
      - 연령대/스킬 레벨별 난이도 조정
      - 드릴별 기대 효과 및 수행 시간 제시
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
# 드릴 정의 — 과학적 훈련 처방
# =============================================================================
@dataclass(slots=True, frozen=True)
class DrillSpec:
    """개별 드릴 사양."""
    name: str               # 드릴명
    category: str            # 카테고리 (shooting/dribbling/defense/finishing/free_throw/conditioning)
    description: str         # 수행 방법
    duration_min: int        # 권장 수행 시간 (분)
    repetitions: str         # 반복 횟수/세트
    target_weakness: str     # 타겟 약점
    expected_effect: str     # 기대 효과
    difficulty: str          # easy/medium/hard


# 슈팅 교정 드릴
_SHOOTING_DRILLS: tuple[DrillSpec, ...] = (
    DrillSpec(
        name="포름 슈팅 (Form Shooting)",
        category="shooting", difficulty="easy",
        description="골대 정면 1.5m 거리에서 한 손(슈팅 핸드)만 사용하여 10회×3세트. 팔꿈치 정렬과 릴리스 포인트에 집중.",
        duration_min=10, repetitions="10회×3세트",
        target_weakness="슈팅 폼 불안정",
        expected_effect="릴리스 일관성 향상, 아크 높이 안정화",
    ),
    DrillSpec(
        name="미들레인지 스팟업 (Mid-Range Spot-Up)",
        category="shooting", difficulty="medium",
        description="엘보-프리스로 라인-윙 5개 스팟에서 각 5회씩 슈팅. 캐치 후 0.5초 이내 릴리스 목표.",
        duration_min=15, repetitions="5스팟×5회",
        target_weakness="미드레인지 성공률 저하",
        expected_effect="캐치앤슛 속도 및 미드레인지 FG% 향상",
    ),
    DrillSpec(
        name="3점 무브먼트 슈팅 (3PT Movement)",
        category="shooting", difficulty="hard",
        description="스크린 시뮬레이션 후 3점 라인 5개 스팟 이동 슈팅. 파트너 패스 → 캐치 → 슛. 각 스팟 3회.",
        duration_min=15, repetitions="5스팟×3회",
        target_weakness="3점슛 성공률 저하",
        expected_effect="오프스크린 3점 정확도 및 풋워크 향상",
    ),
)

# 드리블/핸들링 드릴
_DRIBBLE_DRILLS: tuple[DrillSpec, ...] = (
    DrillSpec(
        name="풀코트 드리블 서킷 (Full-Court Circuit)",
        category="dribbling", difficulty="medium",
        description="풀코트를 크로스오버-비하인드더백-인앤아웃 순서로 왕복. 고개를 들고 전방 주시.",
        duration_min=10, repetitions="왕복 5회",
        target_weakness="볼 핸들링 불안정",
        expected_effect="드리블 컨트롤 및 시야 확보 향상",
    ),
    DrillSpec(
        name="프레셔 핸들링 (Pressure Handling)",
        category="dribbling", difficulty="hard",
        description="1:1 수비 압박 하에서 하프코트 진입 연습. 수비수는 80% 강도로 압박. 10회 시도.",
        duration_min=10, repetitions="10회",
        target_weakness="턴오버 과다 / 볼 로스",
        expected_effect="수비 압박 하 볼 보호 및 의사결정 향상",
    ),
)

# 수비 드릴
_DEFENSE_DRILLS: tuple[DrillSpec, ...] = (
    DrillSpec(
        name="클로즈아웃 & 리커버 (Closeout & Recover)",
        category="defense", difficulty="medium",
        description="3점 라인 수비수가 페인트에서 슈터에게 클로즈아웃 → 드라이브 대응 → 리커버. 10회×3세트.",
        duration_min=12, repetitions="10회×3세트",
        target_weakness="수비 컨테스트율 저하",
        expected_effect="클로즈아웃 스피드 및 수비 전환 능력 향상",
    ),
    DrillSpec(
        name="셸 디펜스 (Shell Defense)",
        category="defense", difficulty="medium",
        description="4:4 하프코트 수비 로테이션 연습. 볼 이동에 따라 헬프-리커버 포지셔닝. 5분간 연속.",
        duration_min=15, repetitions="5분×3세트",
        target_weakness="헬프 수비 로테이션 미흡",
        expected_effect="팀 수비 의사소통 및 로테이션 향상",
    ),
)

# 피니시 드릴
_FINISHING_DRILLS: tuple[DrillSpec, ...] = (
    DrillSpec(
        name="미키 드릴 (Mikan Drill)",
        category="finishing", difficulty="easy",
        description="골대 양쪽에서 교대 레이업 30초간 연속 수행. 왼손/오른손 동일 비율.",
        duration_min=8, repetitions="30초×5세트",
        target_weakness="페인트존 피니시 부족",
        expected_effect="양손 레이업 정확도 및 터치 감각 향상",
    ),
    DrillSpec(
        name="컨택 피니시 (Contact Finish)",
        category="finishing", difficulty="hard",
        description="파트너가 패드로 물리적 컨택 시뮬레이션. 드라이브 → 컨택 → 피니시. 좌우 각 5회.",
        duration_min=10, repetitions="좌우 5회×3세트",
        target_weakness="컨택 시 피니시 실패",
        expected_effect="and-one 변환율 및 파울 유도 능력 향상",
    ),
)

# 자유투 드릴
_FREE_THROW_DRILLS: tuple[DrillSpec, ...] = (
    DrillSpec(
        name="루틴 자유투 50 (Routine FT 50)",
        category="free_throw", difficulty="easy",
        description="동일한 사전 루틴(드리블 2회, 호흡, 시선 고정)으로 자유투 50개 연속. 성공률 기록.",
        duration_min=15, repetitions="50회",
        target_weakness="자유투 성공률 저하",
        expected_effect="자유투 루틴 일관성 및 성공률 향상",
    ),
    DrillSpec(
        name="피로 자유투 (Fatigue FT)",
        category="free_throw", difficulty="medium",
        description="전력 질주 왕복 후 즉시 자유투 2개 세트. 경기 후반 피로 상태 시뮬레이션. 10세트.",
        duration_min=20, repetitions="10세트×2회",
        target_weakness="4쿼터 자유투 부진",
        expected_effect="피로 상황에서의 자유투 안정성 향상",
    ),
)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class DrillPrescriptionFeedbackConfig:
    """드릴 처방 피드백 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    # 약점 판별 임계치
    fg_pct_weak: float = 40.0        # FG 40% 미만 → 슈팅 드릴 필요
    three_pt_pct_weak: float = 30.0  # 3P 30% 미만 → 3점 드릴 필요
    ft_pct_weak: float = 70.0        # FT 70% 미만 → 자유투 드릴 필요
    turnover_high: int = 4           # TO 4개 이상 → 핸들링 드릴 필요
    foul_high: int = 4               # PF 4개 이상 → 수비 드릴 필요

    # 팀 약점 판별
    team_fg_pct_weak: float = 42.0
    team_ft_pct_weak: float = 70.0
    team_to_high: int = 16           # 팀 턴오버 16개 이상


# =============================================================================
# DrillPrescriptionFeedbackGenerator 클래스
# =============================================================================
class DrillPrescriptionFeedbackGenerator:
    """
    구체적 드릴 처방 피드백 생성기.

    GameStats를 입력받아 팀/개인 약점을 식별하고,
    각 약점에 맞는 구체적 훈련 드릴을 처방합니다.
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: DrillPrescriptionFeedbackConfig | None = None) -> None:
        self._config: DrillPrescriptionFeedbackConfig = config or DrillPrescriptionFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "DrillPrescriptionFeedbackGenerator"

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
        경기 통계 기반 드릴 처방 피드백 생성.

        Args:
            game_stats: 경기 전체 통계

        Returns:
            FeedbackItem 목록 (15+ 항목)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        home = game_stats.home_team_stats
        away = game_stats.away_team_stats

        # 팀 약점 기반 드릴 처방
        if home is not None:
            items.extend(self._prescribe_team_drills(home, is_home=True))
        if away is not None:
            items.extend(self._prescribe_team_drills(away, is_home=False))

        # 개인 약점 기반 드릴 처방 (양 팀)
        all_players: list[tuple[PlayerStats, bool]] = []
        if home is not None:
            all_players.extend((ps, True) for ps in home.player_stats)
        if away is not None:
            all_players.extend((ps, False) for ps in away.player_stats)

        for ps, is_home in all_players:
            items.extend(self._prescribe_player_drills(ps, is_home=is_home))

        # 종합 훈련 계획 권고
        items.extend(self._generate_training_plan_summary(game_stats))

        # 최소 항목 보장
        if len(items) < cfg.min_items:
            items.extend(self._generate_baseline_drills())

        with self._lock:
            self._total_generated += 1

        return items[:cfg.max_items]

    # -------------------------------------------------------------------------
    # 팀 드릴 처방
    # -------------------------------------------------------------------------
    def _prescribe_team_drills(
        self,
        team: TeamStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """팀 약점 기반 드릴 처방."""
        items: list[FeedbackItem] = []
        cfg = self._config
        label = "홈팀" if is_home else "어웨이팀"

        # 슈팅 약점 → 슈팅 드릴
        fg_pct = team.field_goal_percentage
        if fg_pct < cfg.team_fg_pct_weak and team.field_goals_attempted > 0:
            drill = _SHOOTING_DRILLS[0]  # 포름 슈팅
            items.append(self._drill_to_feedback(
                drill, label,
                weakness_desc=f"{label} FG% {fg_pct:.1f}%로 팀 슈팅 효율 부족",
                priority=FeedbackPriority.HIGH,
            ))
            drill2 = _SHOOTING_DRILLS[1]  # 미들레인지 스팟업
            items.append(self._drill_to_feedback(
                drill2, label,
                weakness_desc=f"{label} 미드레인지 효율 개선 필요",
                priority=FeedbackPriority.MEDIUM,
            ))

        # 3점슛 약점
        tpp = team.three_point_percentage
        if tpp < cfg.three_pt_pct_weak and team.three_pointers_attempted >= 10:
            drill = _SHOOTING_DRILLS[2]
            items.append(self._drill_to_feedback(
                drill, label,
                weakness_desc=f"{label} 3P% {tpp:.1f}%로 3점 효율 부족",
                priority=FeedbackPriority.HIGH,
            ))

        # 자유투 약점
        ft_pct = team.free_throw_percentage
        if ft_pct < cfg.team_ft_pct_weak and team.free_throws_attempted >= 8:
            drill = _FREE_THROW_DRILLS[0]
            items.append(self._drill_to_feedback(
                drill, label,
                weakness_desc=f"{label} FT% {ft_pct:.1f}%로 자유투 개선 필요",
                priority=FeedbackPriority.MEDIUM,
            ))

        # 턴오버 과다
        if team.turnovers >= cfg.team_to_high:
            drill = _DRIBBLE_DRILLS[1]  # 프레셔 핸들링
            items.append(self._drill_to_feedback(
                drill, label,
                weakness_desc=f"{label} 턴오버 {team.turnovers}개 — 볼 보호 훈련 필요",
                priority=FeedbackPriority.HIGH,
            ))

        # 수비 (상대 FG% 높을 때) — 팀 파울 과다 시 수비 드릴
        if team.personal_fouls >= 20:
            drill = _DEFENSE_DRILLS[1]  # 셸 디펜스
            items.append(self._drill_to_feedback(
                drill, label,
                weakness_desc=f"{label} 팀 파울 {team.personal_fouls}개 — 수비 규율 훈련 필요",
                priority=FeedbackPriority.MEDIUM,
            ))

        return items

    # -------------------------------------------------------------------------
    # 개인 드릴 처방
    # -------------------------------------------------------------------------
    def _prescribe_player_drills(
        self,
        player: PlayerStats,
        *,
        is_home: bool,
    ) -> list[FeedbackItem]:
        """개인 선수 약점 기반 드릴 처방."""
        items: list[FeedbackItem] = []
        cfg = self._config
        pid = f"선수#{player.player_tracking_id}"
        label = "홈팀" if is_home else "어웨이팀"

        # FG% 부진 선수
        if player.field_goals_attempted >= 5 and player.field_goal_percentage < cfg.fg_pct_weak:
            drill = _SHOOTING_DRILLS[0]
            items.append(self._drill_to_feedback(
                drill, f"{label} {pid}",
                weakness_desc=f"FG% {player.field_goal_percentage:.1f}% — 슈팅 교정 필요",
                priority=FeedbackPriority.HIGH,
            ))

        # 턴오버 과다 선수
        if player.turnovers >= cfg.turnover_high:
            drill = _DRIBBLE_DRILLS[0]
            items.append(self._drill_to_feedback(
                drill, f"{label} {pid}",
                weakness_desc=f"턴오버 {player.turnovers}개 — 볼 핸들링 훈련 필요",
                priority=FeedbackPriority.MEDIUM,
            ))

        # 파울 과다 선수
        if player.personal_fouls >= cfg.foul_high:
            drill = _DEFENSE_DRILLS[0]
            items.append(self._drill_to_feedback(
                drill, f"{label} {pid}",
                weakness_desc=f"파울 {player.personal_fouls}개 — 수비 자세 교정 필요",
                priority=FeedbackPriority.MEDIUM,
            ))

        # 자유투 부진 선수
        if player.free_throws_attempted >= 4 and player.free_throw_percentage < cfg.ft_pct_weak:
            drill = _FREE_THROW_DRILLS[0]
            items.append(self._drill_to_feedback(
                drill, f"{label} {pid}",
                weakness_desc=f"FT% {player.free_throw_percentage:.1f}% — 자유투 루틴 개선 필요",
                priority=FeedbackPriority.MEDIUM,
            ))

        return items

    # -------------------------------------------------------------------------
    # 드릴 → FeedbackItem 변환
    # -------------------------------------------------------------------------
    def _drill_to_feedback(
        self,
        drill: DrillSpec,
        target: str,
        *,
        weakness_desc: str,
        priority: FeedbackPriority,
    ) -> FeedbackItem:
        """DrillSpec을 FeedbackItem으로 변환."""
        return FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.IMPROVEMENT,
            priority=priority,
            title=f"[드릴 처방] {target}: {drill.name}",
            description=(
                f"약점: {weakness_desc}\n"
                f"드릴: {drill.name} ({drill.difficulty})\n"
                f"방법: {drill.description}\n"
                f"분량: {drill.repetitions} / {drill.duration_min}분"
            ),
            suggestion=f"기대 효과: {drill.expected_effect}",
            confidence=0.85,
        )

    # -------------------------------------------------------------------------
    # 종합 훈련 계획
    # -------------------------------------------------------------------------
    def _generate_training_plan_summary(
        self,
        game_stats: GameStats,
    ) -> list[FeedbackItem]:
        """종합 훈련 계획 권고."""
        items: list[FeedbackItem] = []

        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.MEDIUM,
            title="[훈련 계획] 경기 후 추천 훈련 순서",
            description=(
                "경기 분석 기반 훈련 우선순위: "
                "1) 경기 다음 날: 슈팅 교정 드릴 (피로 낮을 때 기술 교정) "
                "2) 2일 차: 체력 회복 + 자유투 루틴 50개 "
                "3) 3일 차: 수비 드릴 + 팀 전술 연습 "
                "4) 경기 전날: 가벼운 슈팅 → 게임 시뮬레이션."
            ),
            suggestion="훈련 강도는 경기 후 48시간 내 70% 이하로 유지하세요.",
            confidence=0.80,
        ))

        items.append(FeedbackItem(
            category=FeedbackCategory.TIP,
            feedback_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="[훈련 원칙] 약점 교정 vs 강점 강화 비율",
            description=(
                "코칭 과학 권장 비율 — 약점 교정 60% : 강점 강화 40%. "
                "약점만 반복 훈련하면 선수 자신감이 저하됩니다. "
                "강점 영역 성공 경험을 함께 제공해야 효과적입니다."
            ),
            confidence=0.82,
        ))

        return items

    # -------------------------------------------------------------------------
    # 최소 항목 보장
    # -------------------------------------------------------------------------
    def _generate_baseline_drills(self) -> list[FeedbackItem]:
        """최소 피드백 항목 보장."""
        items: list[FeedbackItem] = []

        # 각 카테고리에서 기본 드릴 하나씩
        for drill_set, desc in [
            (_SHOOTING_DRILLS, "슈팅 기본"),
            (_DRIBBLE_DRILLS, "핸들링 기본"),
            (_DEFENSE_DRILLS, "수비 기본"),
            (_FINISHING_DRILLS, "피니시 기본"),
            (_FREE_THROW_DRILLS, "자유투 기본"),
        ]:
            drill = drill_set[0]
            items.append(self._drill_to_feedback(
                drill, "전체",
                weakness_desc=f"{desc} 역량 유지/향상",
                priority=FeedbackPriority.LOW,
            ))

        return items

    # -------------------------------------------------------------------------
    # 리셋 / repr
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"DrillPrescriptionFeedbackGenerator(generated={self._total_generated})"


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "DrillPrescriptionFeedbackGenerator",
    "DrillPrescriptionFeedbackConfig",
    "DrillSpec",
]

__version__ = "1.0.0"
