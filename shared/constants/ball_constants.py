# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: ball_constants.py
설명: 농구공 물리 및 검출 관련 상수 정의
      - 농구공 물리적 특성 (크기, 질량, 탄성)
      - 공기역학 파라미터 (항력, 양력, 마그누스 효과)
      - 궤적 예측 및 슛 분석 파라미터
      - 연령대/성별별 공 규격 (FIBA/NBA/KBL 규정)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-02
버전: 1.0.0

참조:
- FIBA 규정: 남자 Size 7, 여자 Size 6
- NBA 규정: Spalding 공식 농구공 (둘레 749-780mm)
- 농구공 물리학: 탄성 계수, 공기역학, 스핀 효과
"""

from enum import Enum, unique
from typing import Final

from shared.constants.localization import SupportedLanguage
from shared.constants.player_constants import AgeGroup


# =============================================================================
# 농구공 물리적 규격 (FIBA/NBA 공식 규정)
# =============================================================================

# 농구공 지름 (미터) - Size 7 (남자 성인), 둘레 중간값(765mm) / π
BASKETBALL_DIAMETER_M: Final[float] = 0.244

# 농구공 반지름 (미터)
BASKETBALL_RADIUS_M: Final[float] = 0.122

# 농구공 둘레 (미터) - FIBA 규정: 749-780mm
BASKETBALL_CIRCUMFERENCE_MIN_M: Final[float] = 0.749
BASKETBALL_CIRCUMFERENCE_MAX_M: Final[float] = 0.780
BASKETBALL_CIRCUMFERENCE_M: Final[float] = 0.765  # 중간값

# 농구공 질량 (킬로그램) - FIBA 규정: 567-650g
BASKETBALL_MASS_KG: Final[float] = 0.62
BASKETBALL_MASS_MIN_KG: Final[float] = 0.567
BASKETBALL_MASS_MAX_KG: Final[float] = 0.650


# =============================================================================
# 연령대/성별별 농구공 규격
# =============================================================================

# Size 7 - 남자 성인/고등학생 (FIBA/NBA)
BALL_SIZE_7_DIAMETER_M: Final[float] = 0.244  # 둘레 중간값(765mm) / π
BALL_SIZE_7_CIRCUMFERENCE_M: Final[float] = 0.765
BALL_SIZE_7_MASS_KG: Final[float] = 0.62

# Size 6 - 여자 성인/고등학생, 남자 중학생 (FIBA/WNBA)
# FIBA 규정 둘레: 724~737mm, 질량: 510~567g
BALL_SIZE_6_DIAMETER_M: Final[float] = 0.232  # 둘레 중간값(730mm) / π
BALL_SIZE_6_CIRCUMFERENCE_M: Final[float] = 0.730  # 중간값 (724+737)/2
BALL_SIZE_6_MASS_KG: Final[float] = 0.54

# Size 5 - 유소년 (초등학생)
# FIBA 규정 둘레: 690~710mm, 질량: 470~500g
BALL_SIZE_5_DIAMETER_M: Final[float] = 0.223  # 둘레 중간값(700mm) / π
BALL_SIZE_5_CIRCUMFERENCE_M: Final[float] = 0.700  # 중간값 (690+710)/2
BALL_SIZE_5_MASS_KG: Final[float] = 0.485  # 중간값 (470+500)/2


# =============================================================================
# 물리 법칙 상수
# =============================================================================

# 중력 가속도 (m/s²)
GRAVITY_ACCELERATION: Final[float] = 9.81

# 공기 밀도 (kg/m³) - 표준 대기압, 20°C
AIR_DENSITY: Final[float] = 1.204

# 공기 저항 계수 (항력 계수, 구체 기준)
# - 레이놀즈 수에 따라 0.1~0.5 범위
AIR_RESISTANCE_COEFFICIENT: Final[float] = 0.47

# 양력 계수 (마그누스 효과)
LIFT_COEFFICIENT: Final[float] = 0.25

# 마그누스 힘 계수
MAGNUS_COEFFICIENT: Final[float] = 0.5

# 농구공 단면적 (m²) - Size 7 기준
BASKETBALL_CROSS_SECTION_AREA: Final[float] = 0.0468  # π * 0.122²


# =============================================================================
# 탄성 및 바운스 상수
# =============================================================================

# 반발 계수 (Coefficient of Restitution)
# - FIBA 규정: 1.8m 높이에서 떨어뜨려 1.2-1.4m 바운스
# - COR = √(반발높이/낙하높이)
# - 최소: √(1.2/1.8) ≈ 0.816, 최대: √(1.4/1.8) ≈ 0.882
COEFFICIENT_OF_RESTITUTION: Final[float] = 0.85  # 중간값 √(1.3/1.8)
COEFFICIENT_OF_RESTITUTION_MIN: Final[float] = 0.816  # √(1.2/1.8)
COEFFICIENT_OF_RESTITUTION_MAX: Final[float] = 0.882  # √(1.4/1.8)

# 바닥 반발 계수 (목재 코트)
FLOOR_RESTITUTION_WOOD: Final[float] = 0.83

# 바닥 반발 계수 (합성 코트)
FLOOR_RESTITUTION_SYNTHETIC: Final[float] = 0.78

# 바닥 반발 계수 (콘크리트 - 야외 코트)
FLOOR_RESTITUTION_CONCRETE: Final[float] = 0.80

# 바닥 반발 계수 (아스팔트 - 야외 코트)
FLOOR_RESTITUTION_ASPHALT: Final[float] = 0.75

# 림 반발 계수 (금속 림)
RIM_RESTITUTION: Final[float] = 0.65

# 백보드 반발 계수 (유리/아크릴)
BACKBOARD_RESTITUTION: Final[float] = 0.60

# 바운스 높이 비율 (FIBA 검증용)
MIN_BOUNCE_HEIGHT_RATIO: Final[float] = 0.667  # 1.2m / 1.8m
MAX_BOUNCE_HEIGHT_RATIO: Final[float] = 0.778  # 1.4m / 1.8m


# =============================================================================
# 스핀 및 회전 상수
# =============================================================================

# 최대 스핀 속도 (rad/s) - 슛팅 시
MAX_SPIN_RATE: Final[float] = 30.0  # 약 287 RPM

# 권장 백스핀 속도 (rad/s) - 슈팅 시
OPTIMAL_BACKSPIN_RATE: Final[float] = 12.5  # 약 120 RPM

# 최소 백스핀 속도 (rad/s) - 효과적인 슈팅
MIN_BACKSPIN_RATE: Final[float] = 6.0  # 약 57 RPM

# 스핀 감소율 (rad/s per second) - 공기 마찰
SPIN_DECAY_RATE: Final[float] = 1.0

# 관성 모멘트 (kg·m²) - 속이 빈 구체
MOMENT_OF_INERTIA: Final[float] = 0.0062  # (2/3) * 0.62 * 0.122²


# =============================================================================
# 속도 범위 상수
# =============================================================================

# 슈팅 초기 속도 범위 (m/s)
SHOT_VELOCITY_MIN: Final[float] = 4.0
SHOT_VELOCITY_MAX: Final[float] = 12.0

# 3점슛 초기 속도 범위 (m/s)
THREE_POINT_VELOCITY_MIN: Final[float] = 7.0
THREE_POINT_VELOCITY_MAX: Final[float] = 12.0

# 자유투 초기 속도 (m/s)
FREE_THROW_VELOCITY_OPTIMAL: Final[float] = 6.5

# 패스 속도 범위 (m/s)
PASS_VELOCITY_MIN: Final[float] = 5.0
PASS_VELOCITY_MAX: Final[float] = 20.0

# 드리블 바운스 속도 (m/s)
DRIBBLE_VELOCITY_AVG: Final[float] = 3.0


# =============================================================================
# 궤적 예측 파라미터
# =============================================================================

# 궤적 예측 시간 간격 (초)
TRAJECTORY_TIME_STEP: Final[float] = 0.01

# 궤적 최대 예측 시간 (초)
TRAJECTORY_MAX_PREDICTION_TIME: Final[float] = 3.0

# 궤적 예측 최소 포인트 수
TRAJECTORY_MIN_POINTS: Final[int] = 5

# 궤적 예측 최대 포인트 수
TRAJECTORY_MAX_POINTS: Final[int] = 300

# 궤적 피팅 최소 R² 값
TRAJECTORY_MIN_R_SQUARED: Final[float] = 0.95

# 포물선 피팅 최소 점 수
PARABOLA_FIT_MIN_POINTS: Final[int] = 10


# =============================================================================
# 슈팅 분석 파라미터
# =============================================================================

# 슈팅 방출 각도 범위 (도)
SHOT_RELEASE_ANGLE_MIN: Final[float] = 40.0
SHOT_RELEASE_ANGLE_MAX: Final[float] = 60.0
SHOT_RELEASE_ANGLE_OPTIMAL: Final[float] = 52.0

# 슈팅 진입 각도 범위 (도)
SHOT_ENTRY_ANGLE_MIN: Final[float] = 35.0
SHOT_ENTRY_ANGLE_MAX: Final[float] = 55.0
SHOT_ENTRY_ANGLE_OPTIMAL: Final[float] = 45.0

# 슈팅 최고점 높이 범위 (미터)
SHOT_APEX_HEIGHT_MIN: Final[float] = 3.5
SHOT_APEX_HEIGHT_MAX: Final[float] = 5.5

# 3점슛 방출 각도 최적값 (도)
THREE_POINT_RELEASE_ANGLE_OPTIMAL: Final[float] = 50.0

# 자유투 방출 각도 최적값 (도)
FREE_THROW_RELEASE_ANGLE_OPTIMAL: Final[float] = 52.0


# =============================================================================
# 농구공 검출 파라미터
# =============================================================================

# 농구공 색상 HSV 범위 (주황색)
BALL_COLOR_HSV_LOWER: Final[tuple[int, int, int]] = (5, 100, 100)
BALL_COLOR_HSV_UPPER: Final[tuple[int, int, int]] = (25, 255, 255)

# 농구공 검출 최소 신뢰도
BALL_DETECTION_MIN_CONFIDENCE: Final[float] = 0.5

# 농구공 검출 높은 신뢰도
BALL_DETECTION_HIGH_CONFIDENCE: Final[float] = 0.8

# 농구공 검출 최소 크기 (픽셀)
BALL_MIN_SIZE_PIXELS: Final[int] = 10

# 농구공 검출 최대 크기 (픽셀)
BALL_MAX_SIZE_PIXELS: Final[int] = 200

# 농구공 원형도 임계값 (0.0~1.0)
BALL_CIRCULARITY_THRESHOLD: Final[float] = 0.7

# 농구공 종횡비 허용 범위
BALL_ASPECT_RATIO_MIN: Final[float] = 0.8
BALL_ASPECT_RATIO_MAX: Final[float] = 1.2

# NMS (Non-Maximum Suppression) IOU 임계값
BALL_DETECTION_IOU_THRESHOLD: Final[float] = 0.45

# 모델 입력 크기 (픽셀, 정사각형)
BALL_DETECTION_INPUT_SIZE: Final[int] = 640

# 단일 프레임 최대 검출 수
BALL_DETECTION_MAX_DETECTIONS: Final[int] = 5

# 커스텀 학습 모델 공 클래스 ID
BALL_DETECTION_CLASS_ID: Final[int] = 0

# COCO 데이터셋 스포츠볼 클래스 ID (폴백용)
BALL_DETECTION_COCO_CLASS_ID: Final[int] = 32

# 프레임 대비 최소 공 크기 비율 (정규화)
BALL_DETECTION_MIN_SIZE_RATIO: Final[float] = 0.005

# 프레임 대비 최대 공 크기 비율 (정규화)
BALL_DETECTION_MAX_SIZE_RATIO: Final[float] = 0.15

# 모션 블러 감지 임계값 (0.0~1.0, 낮을수록 민감)
BALL_MOTION_BLUR_THRESHOLD: Final[float] = 0.3

# 검출 결과 캐시 TTL (초)
BALL_DETECTION_CACHE_TTL_SEC: Final[int] = 300


# =============================================================================
# 공 추적 파라미터
# =============================================================================

# 공 추적 최대 프레임 간격 (공이 보이지 않을 때)
BALL_TRACKING_MAX_MISSING_FRAMES: Final[int] = 15

# 공 추적 최대 이동 거리 (픽셀/프레임)
BALL_TRACKING_MAX_MOVEMENT: Final[float] = 100.0

# 공 위치 스무딩 가중치
BALL_SMOOTHING_WEIGHT: Final[float] = 0.3

# 공 속도 스무딩 가중치
BALL_VELOCITY_SMOOTHING: Final[float] = 0.5

# 연속성 판정 최대 거리 (픽셀)
BALL_MAX_EXPECTED_DISTANCE: Final[float] = 100.0

# 연속성 보너스 가중치
BALL_CONTINUITY_BONUS_WEIGHT: Final[float] = 0.2

# 원형도 보너스 가중치
BALL_CIRCULARITY_BONUS_WEIGHT: Final[float] = 0.1

# 연속 미감지 임계값 (프레임, 약 1초 @30fps)
BALL_CONSECUTIVE_MISS_THRESHOLD: Final[int] = 30

# 다중 스케일 검출 비율 목록
BALL_MULTI_SCALE_FACTORS: Final[tuple[float, ...]] = (0.5, 1.0, 1.5)


# =============================================================================
# 공 트래커 파라미터 (ByteTrack/칼만 필터)
# =============================================================================

# 트랙 최대 수명 (프레임, 미감지 시 트랙 삭제까지)
BALL_TRACKING_MAX_TRACK_AGE: Final[int] = 30

# 트랙 확정 최소 연속 감지 수
BALL_TRACKING_MIN_HITS: Final[int] = 3

# 추적 매칭 IOU 임계값 (검출 NMS와 별도)
BALL_TRACKING_IOU_THRESHOLD: Final[float] = 0.3

# 추적 매칭 최대 거리 (픽셀, 헝가리안 알고리즘용)
BALL_TRACKING_MAX_MATCH_DISTANCE: Final[float] = 150.0

# 궤적 이력 길이 (프레임, 3초 @30fps)
BALL_TRACKING_TRAJECTORY_LENGTH: Final[int] = 90

# 새 트랙 생성 신뢰도 임계값
BALL_TRACKING_NEW_TRACK_THRESH: Final[float] = 0.6

# 트랙 매칭 신뢰도 임계값
BALL_TRACKING_MATCH_THRESH: Final[float] = 0.8

# 매칭 비용 상한
BALL_TRACKING_COST_THRESHOLD: Final[float] = 0.7

# 손실 상태 전환 프레임 수
BALL_TRACKING_LOST_THRESHOLD_FRAMES: Final[int] = 3

# 칼만 필터 프로세스 노이즈
BALL_KALMAN_PROCESS_NOISE: Final[float] = 0.05

# 칼만 필터 측정 노이즈
BALL_KALMAN_MEASUREMENT_NOISE: Final[float] = 0.1

# 추적 캐시 TTL (초)
BALL_TRACKING_CACHE_TTL_SEC: Final[int] = 300

# 기본 공 반지름 (픽셀, 스케일 의존적 추정값)
BALL_DEFAULT_RADIUS_PIXELS: Final[float] = 25.0


# =============================================================================
# 공 검출 물리 시뮬레이션 파라미터 (픽셀 공간)
# =============================================================================

# 비행 판정 속도 임계값 (픽셀/프레임)
BALL_FLIGHT_SPEED_THRESHOLD_PX: Final[float] = 10.0

# 중력 효과 (픽셀/프레임²)
BALL_GRAVITY_EFFECT_PX: Final[float] = 2.0

# 궤적 예측용 중력 가속도 (픽셀/초²)
BALL_GRAVITY_PX_PER_SEC2: Final[float] = 98.0

# 픽셀 공간 공기 저항 계수 (0~1, 1=저항 없음)
BALL_AIR_RESISTANCE_PX: Final[float] = 0.98


# =============================================================================
# 공 상태 분류 파라미터
# =============================================================================

# 정지 상태 속도 임계값 (m/s)
BALL_STATIONARY_VELOCITY_THRESHOLD: Final[float] = 0.5

# 드리블 상태 높이 범위 (미터)
DRIBBLE_HEIGHT_MIN: Final[float] = 0.0
DRIBBLE_HEIGHT_MAX: Final[float] = 1.2

# 슈팅 상태 높이 임계값 (미터)
SHOT_HEIGHT_THRESHOLD: Final[float] = 2.0

# 패스 상태 높이 범위 (미터)
PASS_HEIGHT_MIN: Final[float] = 0.5
PASS_HEIGHT_MAX: Final[float] = 2.5


# =============================================================================
# 공 상태머신 파라미터 (픽셀 공간, ball_state.py용)
# =============================================================================

# 비행 판정 최소 속도 (픽셀/프레임, 검출기 10.0보다 낮아 민감)
BALL_STATE_FLIGHT_SPEED_PX: Final[float] = 8.0

# 바운스 판정 최소 속도 (픽셀/프레임)
BALL_STATE_BOUNCE_SPEED_PX: Final[float] = 3.0

# 굴러가는 판정 최소 속도 (픽셀/프레임)
BALL_STATE_ROLLING_SPEED_PX: Final[float] = 1.5

# 정지/소유 판정 최대 속도 (픽셀/프레임)
BALL_STATE_HELD_SPEED_PX: Final[float] = 1.0

# 선수-공 소유 판정 거리 임계값 (픽셀)
BALL_STATE_POSSESSION_DISTANCE_PX: Final[float] = 80.0

# 루즈볼 최소 거리 (픽셀)
BALL_STATE_LOOSE_BALL_DISTANCE_PX: Final[float] = 150.0

# 슛 릴리즈 최소 속도 (픽셀/프레임)
BALL_STATE_SHOT_RELEASE_MIN_SPEED_PX: Final[float] = 15.0

# 슛 상승 중 높이 변화 판정 (픽셀, 음수 = 위로)
BALL_STATE_SHOT_ARC_MIN_HEIGHT_PX: Final[float] = -5.0

# 슛 하강 중 높이 변화 판정 (픽셀, 양수 = 아래로)
BALL_STATE_SHOT_DESCENT_MIN_HEIGHT_PX: Final[float] = 5.0

# 림 영역 반경 (픽셀)
BALL_STATE_RIM_REGION_RADIUS_PX: Final[float] = 50.0

# 소유권 확정 최소 프레임
BALL_STATE_MIN_POSSESSION_FRAMES: Final[int] = 5

# 최대 비행 프레임 (3초 @30fps)
BALL_STATE_MAX_FLIGHT_FRAMES: Final[int] = 90

# 바운스 감지 윈도우 (프레임)
BALL_STATE_BOUNCE_DETECTION_WINDOW: Final[int] = 3


# =============================================================================
# 농구공 크기 열거형
# =============================================================================

@unique
class BallSize(Enum):
    """
    농구공 크기 열거형.

    연령대/성별별 농구공 규격을 정의합니다.
    FIBA/NBA/KBL 공식 규정 기반.
    """

    # Size 7 - 남자 성인/고등학생
    SIZE_7 = 7

    # Size 6 - 여자 성인, 남자 중학생
    SIZE_6 = 6

    # Size 5 - 유소년 (초등학생)
    SIZE_5 = 5

    @property
    def diameter_m(self) -> float:
        """농구공 지름 (미터)."""
        return _BALL_SIZE_DIAMETER_MAP[self]

    @property
    def circumference_m(self) -> float:
        """농구공 둘레 (미터)."""
        return _BALL_SIZE_CIRCUMFERENCE_MAP[self]

    @property
    def mass_kg(self) -> float:
        """농구공 질량 (킬로그램)."""
        return _BALL_SIZE_MASS_MAP[self]

    @property
    def target_age_groups(self) -> tuple[AgeGroup, ...]:
        """대상 연령대 (성별 구분은 get_name() 참조)."""
        return _BALL_SIZE_AGE_GROUPS_MAP[self]

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 크기명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 농구공 크기명
        """
        return _BALL_SIZE_I18N_MAP[self].get(lang, _BALL_SIZE_I18N_MAP[self][SupportedLanguage.KO])

    def to_korean(self) -> str:
        """한글 크기명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# BallSize용 캐시 딕셔너리 (클래스 정의 후 초기화)
_BALL_SIZE_DIAMETER_MAP: dict[BallSize, float] = {
    BallSize.SIZE_7: BALL_SIZE_7_DIAMETER_M,
    BallSize.SIZE_6: BALL_SIZE_6_DIAMETER_M,
    BallSize.SIZE_5: BALL_SIZE_5_DIAMETER_M,
}

_BALL_SIZE_CIRCUMFERENCE_MAP: dict[BallSize, float] = {
    BallSize.SIZE_7: BALL_SIZE_7_CIRCUMFERENCE_M,
    BallSize.SIZE_6: BALL_SIZE_6_CIRCUMFERENCE_M,
    BallSize.SIZE_5: BALL_SIZE_5_CIRCUMFERENCE_M,
}

_BALL_SIZE_MASS_MAP: dict[BallSize, float] = {
    BallSize.SIZE_7: BALL_SIZE_7_MASS_KG,
    BallSize.SIZE_6: BALL_SIZE_6_MASS_KG,
    BallSize.SIZE_5: BALL_SIZE_5_MASS_KG,
}

_BALL_SIZE_AGE_GROUPS_MAP: dict[BallSize, tuple[AgeGroup, ...]] = {
    BallSize.SIZE_7: (AgeGroup.ADULT, AgeGroup.TEEN),   # 남자 성인 + 남자 고등학생
    BallSize.SIZE_6: (AgeGroup.ADULT, AgeGroup.TEEN),   # 여자 성인 + 남자 중학생
    BallSize.SIZE_5: (AgeGroup.YOUTH,),                  # 유소년 (초등학생)
}

# BallSize 다국어 번역
_BALL_SIZE_I18N_MAP: dict[BallSize, dict[SupportedLanguage, str]] = {
    BallSize.SIZE_7: {
        SupportedLanguage.KO: "사이즈 7 (남자 성인)",
        SupportedLanguage.EN: "Size 7 (Men's)",
        SupportedLanguage.JA: "サイズ7 (男子成人)",
        SupportedLanguage.ZH: "7号球 (成年男子)",
        SupportedLanguage.ES: "Talla 7 (Hombres)",
    },
    BallSize.SIZE_6: {
        SupportedLanguage.KO: "사이즈 6 (여자 성인)",
        SupportedLanguage.EN: "Size 6 (Women's)",
        SupportedLanguage.JA: "サイズ6 (女子成人)",
        SupportedLanguage.ZH: "6号球 (成年女子)",
        SupportedLanguage.ES: "Talla 6 (Mujeres)",
    },
    BallSize.SIZE_5: {
        SupportedLanguage.KO: "사이즈 5 (유소년)",
        SupportedLanguage.EN: "Size 5 (Youth)",
        SupportedLanguage.JA: "サイズ5 (ユース)",
        SupportedLanguage.ZH: "5号球 (青少年)",
        SupportedLanguage.ES: "Talla 5 (Juvenil)",
    },
}


# =============================================================================
# 공 상태 열거형
# =============================================================================

@unique
class BallState(Enum):
    """
    공 상태 열거형.

    농구공의 현재 상태를 정의합니다.
    궤적 예측 및 이벤트 감지에 활용됩니다.
    """

    # 정지 상태
    STATIONARY = "stationary"

    # 드리블 중
    DRIBBLING = "dribbling"

    # 패스 중 (공중)
    PASSING = "passing"

    # 슈팅 중 (공중)
    SHOOTING = "shooting"

    # 리바운드 중
    REBOUNDING = "rebounding"

    # 보유 중 (선수가 잡고 있음)
    HELD = "held"

    # 인바운드
    INBOUND = "inbound"

    # 아웃오브바운드
    OUT_OF_BOUNDS = "out_of_bounds"

    # 추적 불가
    LOST = "lost"

    @property
    def is_in_flight(self) -> bool:
        """공중 비행 상태 여부."""
        return self in _BALL_STATE_IN_FLIGHT

    @property
    def is_controlled(self) -> bool:
        """선수 제어 상태 여부."""
        return self in _BALL_STATE_CONTROLLED

    @property
    def requires_physics(self) -> bool:
        """물리 시뮬레이션 필요 여부."""
        return self in _BALL_STATE_PHYSICS_REQUIRED

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 상태명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 공 상태명
        """
        return _BALL_STATE_I18N_MAP[self].get(lang, _BALL_STATE_I18N_MAP[self][SupportedLanguage.KO])

    def to_korean(self) -> str:
        """한글 상태명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# BallState용 캐시 (frozenset으로 조회 최적화)
_BALL_STATE_IN_FLIGHT: frozenset = frozenset({
    BallState.PASSING,
    BallState.SHOOTING,
    BallState.REBOUNDING,
})

_BALL_STATE_CONTROLLED: frozenset = frozenset({
    BallState.DRIBBLING,
    BallState.HELD,
})

_BALL_STATE_PHYSICS_REQUIRED: frozenset = frozenset({
    BallState.PASSING,
    BallState.SHOOTING,
    BallState.REBOUNDING,
    BallState.DRIBBLING,
})

# BallState 다국어 번역
_BALL_STATE_I18N_MAP: dict[BallState, dict[SupportedLanguage, str]] = {
    BallState.STATIONARY: {
        SupportedLanguage.KO: "정지",
        SupportedLanguage.EN: "Stationary",
        SupportedLanguage.JA: "静止",
        SupportedLanguage.ZH: "静止",
        SupportedLanguage.ES: "Estacionario",
    },
    BallState.DRIBBLING: {
        SupportedLanguage.KO: "드리블",
        SupportedLanguage.EN: "Dribbling",
        SupportedLanguage.JA: "ドリブル",
        SupportedLanguage.ZH: "运球",
        SupportedLanguage.ES: "Driblando",
    },
    BallState.PASSING: {
        SupportedLanguage.KO: "패스",
        SupportedLanguage.EN: "Passing",
        SupportedLanguage.JA: "パス",
        SupportedLanguage.ZH: "传球",
        SupportedLanguage.ES: "Pasando",
    },
    BallState.SHOOTING: {
        SupportedLanguage.KO: "슈팅",
        SupportedLanguage.EN: "Shooting",
        SupportedLanguage.JA: "シュート",
        SupportedLanguage.ZH: "投篮",
        SupportedLanguage.ES: "Tirando",
    },
    BallState.REBOUNDING: {
        SupportedLanguage.KO: "리바운드",
        SupportedLanguage.EN: "Rebounding",
        SupportedLanguage.JA: "リバウンド",
        SupportedLanguage.ZH: "篮板",
        SupportedLanguage.ES: "Reboteando",
    },
    BallState.HELD: {
        SupportedLanguage.KO: "보유",
        SupportedLanguage.EN: "Held",
        SupportedLanguage.JA: "保持",
        SupportedLanguage.ZH: "持球",
        SupportedLanguage.ES: "Sostenido",
    },
    BallState.INBOUND: {
        SupportedLanguage.KO: "인바운드",
        SupportedLanguage.EN: "Inbound",
        SupportedLanguage.JA: "インバウンド",
        SupportedLanguage.ZH: "界内",
        SupportedLanguage.ES: "Saque",
    },
    BallState.OUT_OF_BOUNDS: {
        SupportedLanguage.KO: "아웃오브바운드",
        SupportedLanguage.EN: "Out of Bounds",
        SupportedLanguage.JA: "アウトオブバウンズ",
        SupportedLanguage.ZH: "出界",
        SupportedLanguage.ES: "Fuera de Límites",
    },
    BallState.LOST: {
        SupportedLanguage.KO: "추적 불가",
        SupportedLanguage.EN: "Lost",
        SupportedLanguage.JA: "追跡不可",
        SupportedLanguage.ZH: "丢失",
        SupportedLanguage.ES: "Perdido",
    },
}


# =============================================================================
# 슈팅 유형 열거형
# =============================================================================

@unique
class ShotType(Enum):
    """
    슈팅 유형 열거형.

    농구 슈팅의 종류를 정의합니다.
    각 슈팅 유형별 최적 방출 각도와 속도 정보를 포함합니다.
    """

    # 레이업
    LAYUP = "layup"

    # 덩크
    DUNK = "dunk"

    # 점프슛
    JUMP_SHOT = "jump_shot"

    # 훅샷
    HOOK_SHOT = "hook_shot"

    # 플로터
    FLOATER = "floater"

    # 팁인
    TIP_IN = "tip_in"

    # 풋백
    PUTBACK = "putback"

    # 자유투
    FREE_THROW = "free_throw"

    # 3점슛
    THREE_POINTER = "three_pointer"

    @property
    def typical_release_angle(self) -> float:
        """일반적인 방출 각도 (도)."""
        return _SHOT_TYPE_ANGLE_MAP[self]

    @property
    def typical_velocity(self) -> float:
        """일반적인 초기 속도 (m/s)."""
        return _SHOT_TYPE_VELOCITY_MAP[self]

    @property
    def requires_backspin(self) -> bool:
        """백스핀 필요 여부."""
        return self in _SHOT_TYPE_BACKSPIN_REQUIRED

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 슈팅 유형명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 슈팅 유형명
        """
        return _SHOT_TYPE_I18N_MAP[self].get(lang, _SHOT_TYPE_I18N_MAP[self][SupportedLanguage.KO])

    def to_korean(self) -> str:
        """한글 슈팅 유형 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# ShotType용 캐시 딕셔너리
_SHOT_TYPE_ANGLE_MAP: dict[ShotType, float] = {
    ShotType.LAYUP: 35.0,
    ShotType.DUNK: 90.0,  # 수직 하강
    ShotType.JUMP_SHOT: 52.0,
    ShotType.HOOK_SHOT: 55.0,
    ShotType.FLOATER: 60.0,
    ShotType.TIP_IN: 70.0,
    ShotType.PUTBACK: 65.0,
    ShotType.FREE_THROW: 52.0,
    ShotType.THREE_POINTER: 50.0,
}

_SHOT_TYPE_VELOCITY_MAP: dict[ShotType, float] = {
    ShotType.LAYUP: 4.0,
    ShotType.DUNK: 2.0,
    ShotType.JUMP_SHOT: 7.0,
    ShotType.HOOK_SHOT: 6.5,
    ShotType.FLOATER: 5.5,
    ShotType.TIP_IN: 3.0,
    ShotType.PUTBACK: 4.5,
    ShotType.FREE_THROW: 6.5,
    ShotType.THREE_POINTER: 9.0,
}

_SHOT_TYPE_BACKSPIN_REQUIRED: frozenset = frozenset({
    ShotType.JUMP_SHOT,
    ShotType.FREE_THROW,
    ShotType.THREE_POINTER,
    ShotType.FLOATER,
})

# ShotType 다국어 번역
_SHOT_TYPE_I18N_MAP: dict[ShotType, dict[SupportedLanguage, str]] = {
    ShotType.LAYUP: {
        SupportedLanguage.KO: "레이업",
        SupportedLanguage.EN: "Layup",
        SupportedLanguage.JA: "レイアップ",
        SupportedLanguage.ZH: "上篮",
        SupportedLanguage.ES: "Bandeja",
    },
    ShotType.DUNK: {
        SupportedLanguage.KO: "덩크",
        SupportedLanguage.EN: "Dunk",
        SupportedLanguage.JA: "ダンク",
        SupportedLanguage.ZH: "扣篮",
        SupportedLanguage.ES: "Mate",
    },
    ShotType.JUMP_SHOT: {
        SupportedLanguage.KO: "점프슛",
        SupportedLanguage.EN: "Jump Shot",
        SupportedLanguage.JA: "ジャンプシュート",
        SupportedLanguage.ZH: "跳投",
        SupportedLanguage.ES: "Tiro en Suspensión",
    },
    ShotType.HOOK_SHOT: {
        SupportedLanguage.KO: "훅샷",
        SupportedLanguage.EN: "Hook Shot",
        SupportedLanguage.JA: "フックシュート",
        SupportedLanguage.ZH: "勾手",
        SupportedLanguage.ES: "Gancho",
    },
    ShotType.FLOATER: {
        SupportedLanguage.KO: "플로터",
        SupportedLanguage.EN: "Floater",
        SupportedLanguage.JA: "フローター",
        SupportedLanguage.ZH: "抛投",
        SupportedLanguage.ES: "Flotador",
    },
    ShotType.TIP_IN: {
        SupportedLanguage.KO: "팁인",
        SupportedLanguage.EN: "Tip-In",
        SupportedLanguage.JA: "ティップイン",
        SupportedLanguage.ZH: "补篮",
        SupportedLanguage.ES: "Palmeo",
    },
    ShotType.PUTBACK: {
        SupportedLanguage.KO: "풋백",
        SupportedLanguage.EN: "Putback",
        SupportedLanguage.JA: "プットバック",
        SupportedLanguage.ZH: "二次进攻",
        SupportedLanguage.ES: "Segunda Oportunidad",
    },
    ShotType.FREE_THROW: {
        SupportedLanguage.KO: "자유투",
        SupportedLanguage.EN: "Free Throw",
        SupportedLanguage.JA: "フリースロー",
        SupportedLanguage.ZH: "罚球",
        SupportedLanguage.ES: "Tiro Libre",
    },
    ShotType.THREE_POINTER: {
        SupportedLanguage.KO: "3점슛",
        SupportedLanguage.EN: "Three-Pointer",
        SupportedLanguage.JA: "スリーポイント",
        SupportedLanguage.ZH: "三分球",
        SupportedLanguage.ES: "Triple",
    },
}


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 농구공 물리적 규격 (정의서 필수)
    "BASKETBALL_DIAMETER_M",
    "BASKETBALL_MASS_KG",
    "GRAVITY_ACCELERATION",
    "AIR_RESISTANCE_COEFFICIENT",

    # 농구공 추가 규격
    "BASKETBALL_RADIUS_M",
    "BASKETBALL_CIRCUMFERENCE_MIN_M",
    "BASKETBALL_CIRCUMFERENCE_MAX_M",
    "BASKETBALL_CIRCUMFERENCE_M",
    "BASKETBALL_MASS_MIN_KG",
    "BASKETBALL_MASS_MAX_KG",

    # 연령대/성별별 규격
    "BALL_SIZE_7_DIAMETER_M",
    "BALL_SIZE_7_CIRCUMFERENCE_M",
    "BALL_SIZE_7_MASS_KG",
    "BALL_SIZE_6_DIAMETER_M",
    "BALL_SIZE_6_CIRCUMFERENCE_M",
    "BALL_SIZE_6_MASS_KG",
    "BALL_SIZE_5_DIAMETER_M",
    "BALL_SIZE_5_CIRCUMFERENCE_M",
    "BALL_SIZE_5_MASS_KG",

    # 물리 법칙 상수
    "AIR_DENSITY",
    "LIFT_COEFFICIENT",
    "MAGNUS_COEFFICIENT",
    "BASKETBALL_CROSS_SECTION_AREA",

    # 탄성 및 바운스 상수
    "COEFFICIENT_OF_RESTITUTION",
    "COEFFICIENT_OF_RESTITUTION_MIN",
    "COEFFICIENT_OF_RESTITUTION_MAX",
    "FLOOR_RESTITUTION_WOOD",
    "FLOOR_RESTITUTION_SYNTHETIC",
    "FLOOR_RESTITUTION_CONCRETE",
    "FLOOR_RESTITUTION_ASPHALT",
    "RIM_RESTITUTION",
    "BACKBOARD_RESTITUTION",
    "MIN_BOUNCE_HEIGHT_RATIO",
    "MAX_BOUNCE_HEIGHT_RATIO",

    # 스핀 및 회전 상수
    "MAX_SPIN_RATE",
    "OPTIMAL_BACKSPIN_RATE",
    "MIN_BACKSPIN_RATE",
    "SPIN_DECAY_RATE",
    "MOMENT_OF_INERTIA",

    # 속도 범위 상수
    "SHOT_VELOCITY_MIN",
    "SHOT_VELOCITY_MAX",
    "THREE_POINT_VELOCITY_MIN",
    "THREE_POINT_VELOCITY_MAX",
    "FREE_THROW_VELOCITY_OPTIMAL",
    "PASS_VELOCITY_MIN",
    "PASS_VELOCITY_MAX",
    "DRIBBLE_VELOCITY_AVG",

    # 궤적 예측 파라미터
    "TRAJECTORY_TIME_STEP",
    "TRAJECTORY_MAX_PREDICTION_TIME",
    "TRAJECTORY_MIN_POINTS",
    "TRAJECTORY_MAX_POINTS",
    "TRAJECTORY_MIN_R_SQUARED",
    "PARABOLA_FIT_MIN_POINTS",

    # 슈팅 분석 파라미터
    "SHOT_RELEASE_ANGLE_MIN",
    "SHOT_RELEASE_ANGLE_MAX",
    "SHOT_RELEASE_ANGLE_OPTIMAL",
    "SHOT_ENTRY_ANGLE_MIN",
    "SHOT_ENTRY_ANGLE_MAX",
    "SHOT_ENTRY_ANGLE_OPTIMAL",
    "SHOT_APEX_HEIGHT_MIN",
    "SHOT_APEX_HEIGHT_MAX",
    "THREE_POINT_RELEASE_ANGLE_OPTIMAL",
    "FREE_THROW_RELEASE_ANGLE_OPTIMAL",

    # 농구공 검출 파라미터
    "BALL_COLOR_HSV_LOWER",
    "BALL_COLOR_HSV_UPPER",
    "BALL_DETECTION_MIN_CONFIDENCE",
    "BALL_DETECTION_HIGH_CONFIDENCE",
    "BALL_MIN_SIZE_PIXELS",
    "BALL_MAX_SIZE_PIXELS",
    "BALL_CIRCULARITY_THRESHOLD",
    "BALL_ASPECT_RATIO_MIN",
    "BALL_ASPECT_RATIO_MAX",
    "BALL_DETECTION_IOU_THRESHOLD",
    "BALL_DETECTION_INPUT_SIZE",
    "BALL_DETECTION_MAX_DETECTIONS",
    "BALL_DETECTION_CLASS_ID",
    "BALL_DETECTION_COCO_CLASS_ID",
    "BALL_DETECTION_MIN_SIZE_RATIO",
    "BALL_DETECTION_MAX_SIZE_RATIO",
    "BALL_MOTION_BLUR_THRESHOLD",
    "BALL_DETECTION_CACHE_TTL_SEC",

    # 공 추적 파라미터
    "BALL_TRACKING_MAX_MISSING_FRAMES",
    "BALL_TRACKING_MAX_MOVEMENT",
    "BALL_SMOOTHING_WEIGHT",
    "BALL_VELOCITY_SMOOTHING",
    "BALL_MAX_EXPECTED_DISTANCE",
    "BALL_CONTINUITY_BONUS_WEIGHT",
    "BALL_CIRCULARITY_BONUS_WEIGHT",
    "BALL_CONSECUTIVE_MISS_THRESHOLD",
    "BALL_MULTI_SCALE_FACTORS",

    # 공 트래커 파라미터 (ByteTrack/칼만 필터)
    "BALL_TRACKING_MAX_TRACK_AGE",
    "BALL_TRACKING_MIN_HITS",
    "BALL_TRACKING_IOU_THRESHOLD",
    "BALL_TRACKING_MAX_MATCH_DISTANCE",
    "BALL_TRACKING_TRAJECTORY_LENGTH",
    "BALL_TRACKING_NEW_TRACK_THRESH",
    "BALL_TRACKING_MATCH_THRESH",
    "BALL_TRACKING_COST_THRESHOLD",
    "BALL_TRACKING_LOST_THRESHOLD_FRAMES",
    "BALL_KALMAN_PROCESS_NOISE",
    "BALL_KALMAN_MEASUREMENT_NOISE",
    "BALL_TRACKING_CACHE_TTL_SEC",
    "BALL_DEFAULT_RADIUS_PIXELS",

    # 공 검출 물리 시뮬레이션 파라미터 (픽셀 공간)
    "BALL_FLIGHT_SPEED_THRESHOLD_PX",
    "BALL_GRAVITY_EFFECT_PX",
    "BALL_GRAVITY_PX_PER_SEC2",
    "BALL_AIR_RESISTANCE_PX",

    # 공 상태 분류 파라미터
    "BALL_STATIONARY_VELOCITY_THRESHOLD",
    "DRIBBLE_HEIGHT_MIN",
    "DRIBBLE_HEIGHT_MAX",
    "SHOT_HEIGHT_THRESHOLD",
    "PASS_HEIGHT_MIN",
    "PASS_HEIGHT_MAX",

    # 공 상태머신 파라미터 (픽셀 공간)
    "BALL_STATE_FLIGHT_SPEED_PX",
    "BALL_STATE_BOUNCE_SPEED_PX",
    "BALL_STATE_ROLLING_SPEED_PX",
    "BALL_STATE_HELD_SPEED_PX",
    "BALL_STATE_POSSESSION_DISTANCE_PX",
    "BALL_STATE_LOOSE_BALL_DISTANCE_PX",
    "BALL_STATE_SHOT_RELEASE_MIN_SPEED_PX",
    "BALL_STATE_SHOT_ARC_MIN_HEIGHT_PX",
    "BALL_STATE_SHOT_DESCENT_MIN_HEIGHT_PX",
    "BALL_STATE_RIM_REGION_RADIUS_PX",
    "BALL_STATE_MIN_POSSESSION_FRAMES",
    "BALL_STATE_MAX_FLIGHT_FRAMES",
    "BALL_STATE_BOUNCE_DETECTION_WINDOW",

    # 열거형
    "BallSize",
    "BallState",
    "ShotType",
]

# 모듈 버전 정보
__version__ = "1.0.0"
