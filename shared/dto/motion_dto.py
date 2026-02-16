# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: motion_dto.py
설명: 동작 감지/분류 결과 DTO (Data Transfer Object) 정의
      - Layer 4 (motion_analysis) 모듈의 출력 데이터 구조
      - 11가지 동작 유형 분류 결과
      - 슈팅(13유형), 드리블(13유형), 패스(11유형), 수비(11유형), 이동(12유형) 상세

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
    - motion_analysis/classification/: 동작 분류 모듈
    - motion_analysis/shooting/: 슈팅 감지
    - motion_analysis/dribbling/: 드리블 감지
    - motion_analysis/passing/: 패스 감지
    - motion_analysis/defense/: 수비 동작 감지
    - motion_analysis/movement/: 이동 동작 감지

의존성:
    - shared/constants/game_rule_constants.py: ShotType (슛 유형 열거형)
    - shared/constants/pose_constants.py: JointType (관절 열거형)

소비자:
    - game_analysis/event_detection/: 이벤트 감지 시 동작 분류 결과 활용
    - game_analysis/statistics/: 통계 집계 시 동작별 분류 참조
"""

from dataclasses import dataclass, field
from enum import Enum, unique

from uuid import UUID, uuid4

from shared.constants.game_rule_constants import ShotType


# =============================================================================
# 동작 분류 열거형
# =============================================================================

@unique
class ActionType(str, Enum):
    """
    동작 유형 열거형.

    motion_analysis/classification/action_classifier.py에서 분류하는 11가지 동작.
    경기 분석 전용 (Desktop): 훈련 폼 평가 제외.
    """

    SHOOTING = "shooting"          # 슈팅 (슛 동작 전체)
    DRIBBLING = "dribbling"        # 드리블
    PASSING = "passing"            # 패스
    DEFENSE_STANCE = "defense_stance"  # 수비 자세/슬라이드
    SCREEN_SET = "screen_set"      # 스크린 세팅
    SCREEN_USE = "screen_use"      # 스크린 사용 (컬/페이드)
    CUTTING = "cutting"            # 커팅 (V컷/L컷/백도어)
    DRIVING = "driving"            # 드라이브 (림 어택)
    REBOUNDING = "rebounding"      # 리바운딩 (점프/착지)
    BLOCKING = "blocking"          # 블로킹 (슛 블록 시도)
    MOVEMENT = "movement"          # 일반 이동 (달리기/걷기/대기)

    def __str__(self) -> str:
        return self.value


@unique
class ContestLevel(str, Enum):
    """슛 컨테스트 수준."""

    OPEN = "open"                          # 개방 (수비수 1.8m 이상)
    LIGHTLY_CONTESTED = "lightly_contested"  # 약한 컨테스트 (1.2~1.8m)
    CONTESTED = "contested"                # 컨테스트 (0.6~1.2m)
    HEAVILY_CONTESTED = "heavily_contested"  # 강한 컨테스트 (0.6m 미만)

    def __str__(self) -> str:
        return self.value


@unique
class DribbleType(str, Enum):
    """드리블 유형 (13종)."""

    CROSSOVER = "crossover"            # 크로스오버
    BETWEEN_LEGS = "between_legs"      # 사타구니 드리블
    BEHIND_BACK = "behind_back"        # 비하인드 더 백
    SPIN = "spin"                      # 스핀 무브
    HESITATION = "hesitation"          # 헤지테이션
    IN_AND_OUT = "in_and_out"          # 인앤아웃
    PULL_BACK = "pull_back"            # 풀백
    STEP_BACK = "step_back"            # 스텝백 (드리블)
    SHAMGOD = "shamgod"                # 샴갓
    EURO_STEP = "euro_step"            # 유로스텝
    POWER_DRIBBLE = "power_dribble"    # 파워 드리블 (포스트업)
    SPEED_DRIBBLE = "speed_dribble"    # 스피드 드리블 (오픈코트)
    CONTROL_DRIBBLE = "control_dribble"  # 컨트롤 드리블 (하프코트)

    def __str__(self) -> str:
        return self.value


@unique
class PassType(str, Enum):
    """패스 유형 (11종)."""

    CHEST = "chest"            # 체스트 패스
    BOUNCE = "bounce"          # 바운스 패스
    OVERHEAD = "overhead"      # 오버헤드 패스
    BASEBALL = "baseball"      # 베이스볼 패스 (원핸드 롱)
    LOB = "lob"                # 로브 패스 (앨리웁)
    BEHIND_BACK = "behind_back"  # 비하인드 백 패스
    NO_LOOK = "no_look"        # 노룩 패스
    OUTLET = "outlet"          # 아웃렛 패스 (리바운드 후)
    SKIP = "skip"              # 스킵 패스 (사이드 투 사이드)
    POCKET = "pocket"          # 포켓 패스 (PnR 핸들러→롤러)
    TOUCH = "touch"            # 터치 패스 (원터치 중계)

    def __str__(self) -> str:
        return self.value


@unique
class DefensiveActionType(str, Enum):
    """수비 동작 유형 (11종)."""

    ON_BALL = "on_ball"          # 온볼 수비
    OFF_BALL = "off_ball"        # 오프볼 수비
    HELP = "help"                # 헬프 수비
    CLOSE_OUT = "close_out"      # 클로즈아웃
    CONTEST = "contest"          # 슛 컨테스트
    BLOCK_ATTEMPT = "block_attempt"  # 블록 시도
    STEAL_ATTEMPT = "steal_attempt"  # 스틸 시도
    BOX_OUT = "box_out"          # 박스아웃
    HEDGE = "hedge"              # 헤지 (PnR 수비)
    ICE = "ice"                  # 아이스/다운 (PnR 수비)
    DROP = "drop"                # 드롭 (PnR 수비)

    def __str__(self) -> str:
        return self.value


@unique
class MovementType(str, Enum):
    """이동 동작 유형 (12종)."""

    SPRINT = "sprint"              # 전력 질주
    JOG = "jog"                    # 조깅
    WALK = "walk"                  # 걷기
    BACKPEDAL = "backpedal"        # 뒷걸음
    LATERAL_SLIDE = "lateral_slide"  # 사이드 스텝
    V_CUT = "v_cut"                # V컷
    L_CUT = "l_cut"                # L컷
    CURL = "curl"                  # 컬 (스크린 활용)
    FLARE = "flare"                # 페이드/플레어 (스크린 활용)
    SEAL = "seal"                  # 씰 (포지션 확보)
    POST_UP = "post_up"            # 포스트업 포지셔닝
    STAND = "stand"                # 정지 (대기)

    def __str__(self) -> str:
        return self.value


@unique
class DeceptionType(str, Enum):
    """기만/플로핑 행위 유형 (8종)."""

    FLOP = "flop"                            # 접촉 없이 넘어짐
    EXAGGERATED_CONTACT = "exaggerated_contact"  # 접촉 대비 과장된 반응
    HEAD_SNAP = "head_snap"                  # 머리 스냅백 (접촉과 무관한 급격한 머리 움직임)
    FAKE_INJURY = "fake_injury"              # 부상 위장 (시간 지연 목적)
    PUMP_FAKE_DRAW = "pump_fake_draw"        # 펌프페이크로 수비자 파울 유도
    KICK_OUT = "kick_out"                    # 슛 시 비정상적 다리 내밀기
    CHARGE_FLOP = "charge_flop"              # 차지 판정 유도 과장 반응
    RECKLESS_UNDERCUT = "reckless_undercut"  # 슈터 착지 지점 하부 침범

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 특징 벡터
# =============================================================================

@dataclass
class MotionFeatureVector:
    """
    동작 특징 벡터.

    motion_analysis/classification/feature_extractor.py에서 추출.
    관절 포즈, 속도, 가속도, 궤적, 공 접촉 정보를 종합한 특징.
    action_classifier에 입력으로 전달.
    """

    # 자세 특징 (관절 각도, 상대 위치 등)
    posture_features: dict[str, float] = field(default_factory=dict)
    # 속도 특징 (손목/발목/무게중심 속도 등)
    velocity_features: dict[str, float] = field(default_factory=dict)
    # 가속도 특징 (급가속/급정지 여부 등)
    acceleration_features: dict[str, float] = field(default_factory=dict)
    # 궤적 특징 (이동 방향, 경로 곡률 등)
    trajectory_features: dict[str, float] = field(default_factory=dict)
    # 공 접촉 특징 (공과 손의 거리, 공 상태 등)
    contact_features: dict[str, bool] = field(default_factory=dict)


# =============================================================================
# 동작 분류 결과
# =============================================================================

@dataclass
class ActionClassification:
    """
    동작 분류 결과.

    motion_analysis/classification/action_classifier.py의 최종 출력.
    한 선수의 특정 시간 구간에서 감지된 동작.
    """

    classification_id: UUID = field(default_factory=uuid4)
    player_tracking_id: int = 0
    # 동작 유형
    action_type: ActionType = ActionType.MOVEMENT
    # 세부 분류 (DribbleType, PassType 등의 value 문자열)
    sub_type: str | None = None
    # 분류 신뢰도 (0~1)
    confidence: float = 0.0
    # 프레임 범위
    start_frame: int = 0
    end_frame: int = 0
    # 시간 범위 (초)
    start_time: float = 0.0
    end_time: float = 0.0
    # 추출된 특징 벡터 (디버깅/재학습용)
    features: MotionFeatureVector | None = None

    @property
    def duration_frames(self) -> int:
        """동작 지속 프레임 수."""
        return max(0, self.end_frame - self.start_frame)

    @property
    def duration_seconds(self) -> float:
        """동작 지속 시간 (초)."""
        return max(0.0, self.end_time - self.start_time)

    @property
    def is_reliable(self) -> bool:
        """신뢰할 수 있는 분류 여부 (0.7 이상)."""
        return self.confidence >= 0.7


# =============================================================================
# 세부 동작 DTO
# =============================================================================

@dataclass
class ShootingMotion:
    """
    슈팅 동작 상세 결과.

    motion_analysis/shooting/shooting_detector.py에서 감지.
    슛 모션의 릴리스 각도, 높이, 속도, 아크, 컨테스트 수준 등을 담는다.
    game_analysis/event_detection/shot_event_detector에서 ShotAttempt 생성 시 참조.
    """

    player_tracking_id: int = 0
    shot_type: ShotType = ShotType.JUMP_SHOT
    # 릴리스 포인트
    release_angle: float = 0.0  # 릴리스 각도 (도, 수평 기준)
    release_height: float = 0.0  # 릴리스 높이 (m, 지면 기준)
    arc_height: float = 0.0  # 아크 최고점 (m, 릴리스 기준)
    release_speed: float = 0.0  # 릴리스 속도 (m/s)
    # 슛 품질 (종합 점수 0~100)
    shot_quality: float = 0.0
    # 수비 컨테스트
    contest_level: ContestLevel = ContestLevel.OPEN
    # 거리/위치
    distance_meters: float = 0.0
    court_x: float = 0.0  # 정규화 코트 좌표 (-1~1)
    court_y: float = 0.0
    # 프레임 범위
    start_frame: int = 0
    end_frame: int = 0

    @property
    def is_three_pointer(self) -> bool:
        """3점슛 여부."""
        return self.distance_meters >= 6.75  # FIBA 3점 라인


@dataclass
class DribblingMotion:
    """
    드리블 동작 상세 결과.

    motion_analysis/dribbling/dribble_detector.py에서 감지.
    """

    player_tracking_id: int = 0
    dribble_type: DribbleType = DribbleType.CONTROL_DRIBBLE
    hand_used: str = "right"  # left/right
    # 드리블 특성
    bounce_frequency: float = 0.0  # 바운스 빈도 (Hz)
    ball_height_variation: float = 0.0  # 공 높이 변동 (cm)
    control_quality: float = 0.0  # 컨트롤 품질 (0~100)
    speed: float = 0.0  # 이동 속도 (m/s)
    direction_changes: int = 0  # 방향 전환 횟수
    # 프레임 범위
    start_frame: int = 0
    end_frame: int = 0


@dataclass
class PassingMotion:
    """
    패스 동작 상세 결과.

    motion_analysis/passing/pass_detector.py에서 감지.
    """

    passer_tracking_id: int = 0
    receiver_tracking_id: int | None = None
    pass_type: PassType = PassType.CHEST
    # 패스 특성
    ball_speed: float = 0.0  # 공 속도 (m/s)
    trajectory_arc: float = 0.0  # 궤적 아크 (도)
    distance_meters: float = 0.0  # 패스 거리 (m)
    accuracy: float = 0.0  # 정확도 (0~100)
    release_time_ms: float = 0.0  # 릴리스까지 소요 시간 (ms)
    # 프레임 범위
    start_frame: int = 0
    end_frame: int = 0


@dataclass
class DefensiveMotion:
    """
    수비 동작 상세 결과.

    motion_analysis/defense/defense_detector.py에서 감지.
    """

    defender_tracking_id: int = 0
    offensive_player_tracking_id: int | None = None
    action_type: DefensiveActionType = DefensiveActionType.ON_BALL
    # 수비 특성
    distance_to_player: float = 0.0  # 공격수까지 거리 (m)
    pressure_level: float = 0.0  # 압박 수준 (0~100)
    body_between_basket: bool = False  # 바스켓과 공격수 사이 위치 여부
    hands_active: bool = False  # 손 활성 여부 (컨테스트/스틸 시도)
    # 프레임 범위
    start_frame: int = 0
    end_frame: int = 0


@dataclass
class MovementMotion:
    """
    이동 동작 상세 결과.

    motion_analysis/movement/movement_detector.py에서 감지.
    """

    player_tracking_id: int = 0
    movement_type: MovementType = MovementType.STAND
    # 이동 특성
    speed: float = 0.0  # 속도 (m/s)
    direction: float = 0.0  # 이동 방향 (도, 0~360)
    distance_covered: float = 0.0  # 이동 거리 (m)
    acceleration_peak: float = 0.0  # 최대 가속도 (m/s²)
    # 프레임 범위
    start_frame: int = 0
    end_frame: int = 0


@dataclass
class FloppingDetection:
    """
    플로핑/기만 행위 감지 결과.

    motion_analysis/deception/flopping_detector.py에서 감지.
    생체역학적 타당성과 접촉 대비 반응 비율로 판별.
    """

    player_tracking_id: int = 0
    deception_type: DeceptionType = DeceptionType.FLOP
    confidence: float = 0.0  # 감지 신뢰도 (0.0~1.0)
    # 접촉 분석
    contact_force_estimate: float = 0.0      # 추정 접촉 강도 (0.0~1.0)
    reaction_magnitude: float = 0.0          # 실제 반응 크기 (0.0~1.0)
    reaction_proportionality: float = 0.0    # 접촉 대비 반응 비율 (>1.5 = 과장 의심)
    # 생체역학 분석
    biomechanical_plausibility: float = 0.0  # 생체역학적 타당성 (0.0~1.0, 1.0=자연스러움)
    center_of_gravity_shift: float = 0.0     # 무게중심 이동량 (m)
    # 프레임 범위
    start_frame: int = 0
    end_frame: int = 0
    timestamp: float = 0.0


# =============================================================================
# 종합 결과
# =============================================================================

@dataclass
class MotionDetectionResult:
    """
    프레임/구간 단위 동작 감지 종합 결과.

    motion_analysis 파이프라인의 최종 출력.
    game_analysis/event_detection에서 소비.
    """

    frame_index: int = 0
    timestamp: float = 0.0  # 초
    # 분류된 동작 목록
    actions: list[ActionClassification] = field(default_factory=list)
    # 세부 동작별 결과
    shooting_motions: list[ShootingMotion] = field(default_factory=list)
    dribbling_motions: list[DribblingMotion] = field(default_factory=list)
    passing_motions: list[PassingMotion] = field(default_factory=list)
    defensive_motions: list[DefensiveMotion] = field(default_factory=list)
    movement_motions: list[MovementMotion] = field(default_factory=list)
    # 기만 행위 감지
    flopping_detections: list[FloppingDetection] = field(default_factory=list)
    # 처리 시간 (ms)
    processing_time_ms: float = 0.0

    @property
    def total_actions(self) -> int:
        """감지된 총 동작 수."""
        return len(self.actions)

    @property
    def high_confidence_actions(self) -> list[ActionClassification]:
        """고신뢰도 동작 목록 (0.7 이상)."""
        return [a for a in self.actions if a.is_reliable]


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 열거형
    "ActionType",
    "ContestLevel",
    "DribbleType",
    "PassType",
    "DefensiveActionType",
    "MovementType",
    "DeceptionType",
    # 특징 벡터
    "MotionFeatureVector",
    # 동작 분류 결과
    "ActionClassification",
    # 세부 동작
    "ShootingMotion",
    "DribblingMotion",
    "PassingMotion",
    "DefensiveMotion",
    "MovementMotion",
    "FloppingDetection",
    # 종합 결과
    "MotionDetectionResult",
]

__version__ = "1.0.0"
