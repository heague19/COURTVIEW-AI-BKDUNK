# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: prediction_dto.py
설명: 예측 모델 결과 DTO (Data Transfer Object) 정의
      - Layer 5 Phase 2 (predictive_models) 출력 데이터 구조
      - 승리 확률 (WP), 기대 점유 가치 (EPV), 슛 품질 (xFG%), 라인업 예측

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
    - game_analysis/predictive_models/win_probability.py
    - game_analysis/predictive_models/expected_possession_value.py
    - game_analysis/predictive_models/shot_quality_model.py
    - game_analysis/predictive_models/lineup_projection.py

의존성:
    - shared/constants/game_rule_constants.py: CourtZone

소비자:
    - game_analysis/coaching_intelligence/: 코칭 추천 시 승리확률/EPV 참조
    - game_analysis/game_flow/: 모멘텀 분석 시 WP 변화 활용
    - game_analysis/report_generation/: 리포트에 예측 데이터 포함
"""

from __future__ import annotations

from dataclasses import dataclass, field

from uuid import UUID, uuid4

from shared.constants.game_rule_constants import CourtZone


# =============================================================================
# 승리 확률 (Win Probability)
# =============================================================================

@dataclass(slots=True)
class WinProbability:
    """
    실시간 승리 확률 데이터.

    game_analysis/predictive_models/win_probability.py에서 산출.
    경기 상태(점수차, 잔여시간, 점유, 모멘텀)를 종합하여 예측.

    활용:
        - 클러치 상황 자동 식별 (WP 40~60%)
        - WPA(Win Probability Added): 각 플레이의 승리 기여도
        - coaching_intelligence: 타임아웃 추천 시 참조

    >>> wp = WinProbability(home_wp=55.0)
    >>> wp.is_clutch_time
    True
    """

    home_wp: float = 50.0  # 홈팀 승리 확률 (0~100%)
    away_wp: float = 50.0  # 원정팀 승리 확률 (0~100%)
    # WP 시계열 (game_seconds, home_wp)
    wp_curve: list[tuple[float, float]] = field(default_factory=list)
    # 마지막 플레이의 WPA (Win Probability Added)
    last_play_wpa: float = 0.0
    # 클러치 상황 여부 (WP 40~60%)
    is_clutch_time: bool = False
    # 레버리지 인덱스 (1.0 = 평균, >2.0 = 높은 중요도)
    leverage_index: float = 1.0
    # 현재 프레임/시계
    frame_number: int = 0
    game_clock: str = ""

    def __post_init__(self) -> None:
        self.away_wp = 100.0 - self.home_wp
        self.is_clutch_time = 40.0 <= self.home_wp <= 60.0


# =============================================================================
# 기대 점유 가치 (Expected Possession Value)
# =============================================================================

@dataclass(slots=True)
class ExpectedPossessionValue:
    """
    기대 점유 가치 (EPV) 데이터.

    game_analysis/predictive_models/expected_possession_value.py에서 산출.
    현재 점유 상황에서 기대되는 득점 가치를 실시간으로 계산.

    활용:
        - 의사결정 품질 평가 (실제 행동 vs 최적 행동)
        - 패스/슛/드라이브 옵션별 기대값 비교
        - coaching_intelligence: 전술 추천
    """

    # 현재 EPV (0~3, 기대 득점)
    current_epv: float = 0.0
    # 패스 옵션별 EPV (target_tracking_id, epv, improvement)
    pass_options: list[dict[str, float]] = field(default_factory=list)
    # 슛 옵션 EPV
    shot_option_epv: float = 0.0
    # 드라이브 옵션 EPV
    drive_option_epv: float = 0.0
    # 최적 행동
    optimal_action: str = ""  # "pass_to_3", "shoot", "drive"
    # 의사결정 품질 (-1 ~ +1, 실제 EPV - 최적 EPV 차이)
    decision_quality: float = 0.0
    # 점유 ID
    possession_id: UUID | None = None
    # 프레임
    frame_number: int = 0

    @property
    def best_option_epv(self) -> float:
        """가장 높은 옵션 EPV."""
        options = [self.shot_option_epv, self.drive_option_epv]
        if self.pass_options:
            options.extend(opt.get("epv", 0.0) for opt in self.pass_options)
        return max(options) if options else 0.0


# =============================================================================
# 슛 품질 예측 (xFG%)
# =============================================================================

@dataclass(slots=True)
class ShotQualityPrediction:
    """
    슛 품질 예측 (xFG%) 데이터.

    game_analysis/predictive_models/shot_quality_model.py에서 산출.
    슛 위치, 수비 거리, 컨테스트, 슛 유형 등을 종합하여 기대 성공률 예측.

    활용:
        - 슈팅 스킬 지표 (actual FG% - xFG%): 양수 = 슈팅 능력 우수
        - shot_chart: 기대 대비 실제 성적 비교
        - coaching_intelligence: 슛 셀렉션 평가
    """

    # 기대 성공률 (0~100%)
    xfg_pct: float = 0.0
    # 슛 위치 (정규화 코트 좌표)
    shot_location: tuple[float, float] = (0.0, 0.0)
    # 코트 존
    court_zone: CourtZone = CourtZone.PAINT_LEFT
    # 수비 관련
    defender_distance_m: float = 0.0  # 가장 가까운 수비수까지 거리 (m)
    hand_contest: bool = False  # 손으로 컨테스트 여부
    # 슛 유형 (ShotType.value 문자열)
    shot_type: str = ""
    # 슈팅 스킬 인덱스 (실제 FG% - xFG%, 양수 = 우수)
    shooting_skill_index: float = 0.0
    # 선수/슛 식별
    player_tracking_id: int = 0
    shot_id: UUID | None = None


# =============================================================================
# 라인업 예측
# =============================================================================

@dataclass(slots=True)
class LineupProjection:
    """
    라인업 성능 예측 데이터.

    game_analysis/predictive_models/lineup_projection.py에서 산출.
    5인 조합의 예상 넷레이팅, 공수 효율을 예측.

    활용:
        - coaching_intelligence/substitution_optimizer: 교체 최적화
        - coaching_intelligence/endgame_strategist: 엔드게임 라인업 선택
    """

    # 라인업 구성 (5인 tracking IDs)
    lineup_players: list[int] = field(default_factory=list)
    # 예측 효율
    predicted_net_rating: float = 0.0  # 100 possession당 점수 차이
    predicted_offensive_rating: float = 0.0  # 100 possession당 득점
    predicted_defensive_rating: float = 0.0  # 100 possession당 실점
    # 샘플 크기 (분)
    sample_minutes: float = 0.0
    # 매치업 품질 (현재 상대 라인업 대비, -1~+1)
    matchup_quality: float = 0.0
    # 피로도 반영 여부
    fatigue_adjusted: bool = False


# =============================================================================
# 종합 예측 스냅샷
# =============================================================================

@dataclass(slots=True)
class PredictionSnapshot:
    """
    특정 시점의 종합 예측 스냅샷.

    모든 예측 모델의 결과를 하나의 시점으로 묶은 것.
    coaching_intelligence에서 의사결정 지원 시 사용.
    """

    snapshot_id: UUID = field(default_factory=uuid4)
    frame_number: int = 0
    timestamp: float = 0.0  # 초
    game_clock: str = ""
    quarter: int = 1
    # 각 모델 결과
    win_probability: WinProbability | None = None
    epv: ExpectedPossessionValue | None = None
    current_lineup_projection: LineupProjection | None = None


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "WinProbability",
    "ExpectedPossessionValue",
    "ShotQualityPrediction",
    "LineupProjection",
    "PredictionSnapshot",
]

# 모듈 버전 정보
__version__ = "1.0.0"
