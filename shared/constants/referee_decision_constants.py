# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: referee_decision_constants.py
설명: AI 심판 판정 엔진 도메인 상수 정의
      - 판정 신뢰도 등급 (4단계)
      - 파울 등급 (4단계)
      - 접촉 부위 (12종)
      - 바이올레이션 감지 임계치 (12종별)
      - 파울 판정 임계치 (접촉 강도, 실린더 규칙)
      - 멀티앵글 검증 파라미터
      - 판정 일관성 추적 파라미터
      - 리플레이/챌린지 파라미터

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
- FIBA Official Basketball Rules 2024, Art. 33-38 (Contact/Fouls)
- NBA Official Rulebook Rule 12 (Fouls and Penalties)
- FIBA Referee Manual (판정 기준, 접촉 강도 평가)
- NBA Replay Center Protocols

사용처:
- ai_referee/decisions/: 판정 엔진, 신뢰도 평가, 멀티앵글 검증
- ai_referee/violations/: 12종 바이올레이션 감지기
- ai_referee/fouls/: 11종 파울 감지기, 접촉 분석
- ai_referee/fouls/shooting_foul_classifier.py: 슈팅파울 분류
- ai_referee/fouls/flagrant_detector.py: 플래그런트/UF 파울 판정
- ai_referee/fouls/technical_violation_detector.py: 테크니컬 파울 감지
"""

from enum import Enum, unique
from typing import Final

from shared.constants.localization import SupportedLanguage


__version__: str = "1.0.0"


# =============================================================================
# 판정 신뢰도 등급 열거형
# =============================================================================
@unique
class DecisionConfidence(str, Enum):
    """
    AI 심판 판정 신뢰도 등급 열거형 (4단계).

    판정 결과의 확신 수준에 따라 행동이 달라집니다:
    - AUTO_CONFIRM: 자동 확정 (사람 확인 불필요)
    - HIGH: 높은 확신 (기본 확정, 이의 시 리뷰)
    - MODERATE: 보통 확신 (사람 확인 권장)
    - LOW: 낮은 확신 (사람 확인 필수)
    """

    AUTO_CONFIRM = "auto_confirm"   # 자동 확정 (≥95%)
    HIGH = "high"                   # 높은 확신 (85~95%)
    MODERATE = "moderate"           # 보통 확신 (70~85%)
    LOW = "low"                     # 낮은 확신 (<70%)

    def __str__(self) -> str:
        return self.value

    @property
    def requires_human_review(self) -> bool:
        """사람 확인 필요 여부."""
        return self in (DecisionConfidence.MODERATE, DecisionConfidence.LOW)

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 등급명 반환."""
        return _CONFIDENCE_I18N[self].get(
            lang, _CONFIDENCE_I18N[self][SupportedLanguage.KO]
        )


_CONFIDENCE_I18N: dict[DecisionConfidence, dict[SupportedLanguage, str]] = {
    DecisionConfidence.AUTO_CONFIRM: {
        SupportedLanguage.KO: "자동 확정",
        SupportedLanguage.EN: "Auto Confirm",
        SupportedLanguage.JA: "自動確定",
        SupportedLanguage.ZH: "自动确认",
        SupportedLanguage.ES: "Confirmación Automática",
    },
    DecisionConfidence.HIGH: {
        SupportedLanguage.KO: "높은 확신",
        SupportedLanguage.EN: "High Confidence",
        SupportedLanguage.JA: "高確信",
        SupportedLanguage.ZH: "高置信度",
        SupportedLanguage.ES: "Alta Confianza",
    },
    DecisionConfidence.MODERATE: {
        SupportedLanguage.KO: "보통 확신",
        SupportedLanguage.EN: "Moderate Confidence",
        SupportedLanguage.JA: "中確信",
        SupportedLanguage.ZH: "中置信度",
        SupportedLanguage.ES: "Confianza Moderada",
    },
    DecisionConfidence.LOW: {
        SupportedLanguage.KO: "낮은 확신",
        SupportedLanguage.EN: "Low Confidence",
        SupportedLanguage.JA: "低確信",
        SupportedLanguage.ZH: "低置信度",
        SupportedLanguage.ES: "Baja Confianza",
    },
}


# =============================================================================
# 파울 등급 열거형
# =============================================================================
@unique
class FoulGrade(str, Enum):
    """
    파울 등급 열거형 (4단계).

    파울의 심각도/유형을 등급화합니다.
    flagrant_detector.py와 foul_severity_analyzer.py에서 사용됩니다.
    """

    NORMAL = "normal"                       # 일반 파울
    FLAGRANT_1 = "flagrant_1"               # 플래그런트 1 (NBA) / UF-C1/C2 (FIBA)
    FLAGRANT_2 = "flagrant_2"               # 플래그런트 2 (NBA) / UF-C3/C4 (FIBA)
    DISQUALIFYING = "disqualifying"         # 실격 파울 (즉시 퇴장)

    def __str__(self) -> str:
        return self.value

    @property
    def results_in_ejection(self) -> bool:
        """즉시 퇴장 여부."""
        return self in (FoulGrade.FLAGRANT_2, FoulGrade.DISQUALIFYING)

    @property
    def grants_free_throws(self) -> bool:
        """자유투 부여 여부 (플래그런트 이상 = 2FT + 점유)."""
        return self != FoulGrade.NORMAL  # 플래그런트 이상은 항상 2FT+공

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 등급명 반환."""
        return _FOUL_GRADE_I18N[self].get(
            lang, _FOUL_GRADE_I18N[self][SupportedLanguage.KO]
        )


_FOUL_GRADE_I18N: dict[FoulGrade, dict[SupportedLanguage, str]] = {
    FoulGrade.NORMAL: {
        SupportedLanguage.KO: "일반 파울",
        SupportedLanguage.EN: "Normal Foul",
        SupportedLanguage.JA: "通常ファウル",
        SupportedLanguage.ZH: "普通犯规",
        SupportedLanguage.ES: "Falta Normal",
    },
    FoulGrade.FLAGRANT_1: {
        SupportedLanguage.KO: "플래그런트 1",
        SupportedLanguage.EN: "Flagrant 1",
        SupportedLanguage.JA: "フレグラント1",
        SupportedLanguage.ZH: "恶意犯规1级",
        SupportedLanguage.ES: "Flagrante 1",
    },
    FoulGrade.FLAGRANT_2: {
        SupportedLanguage.KO: "플래그런트 2",
        SupportedLanguage.EN: "Flagrant 2",
        SupportedLanguage.JA: "フレグラント2",
        SupportedLanguage.ZH: "恶意犯规2级",
        SupportedLanguage.ES: "Flagrante 2",
    },
    FoulGrade.DISQUALIFYING: {
        SupportedLanguage.KO: "실격 파울",
        SupportedLanguage.EN: "Disqualifying Foul",
        SupportedLanguage.JA: "失格ファウル",
        SupportedLanguage.ZH: "取消资格犯规",
        SupportedLanguage.ES: "Falta Descalificante",
    },
}


# =============================================================================
# 접촉 부위 열거형 (12종)
# =============================================================================
@unique
class ContactArea(str, Enum):
    """
    접촉 부위 열거형 (12종).

    파울 판정 시 접촉이 발생한 신체 부위.
    접촉 부위에 따라 파울 유형이 달라집니다.
    """

    HEAD_NECK = "head_neck"           # 머리/목 (위험 접촉)
    SHOULDER = "shoulder"             # 어깨
    CHEST_TORSO = "chest_torso"       # 가슴/체간
    BACK = "back"                     # 등
    UPPER_ARM = "upper_arm"           # 상완
    FOREARM_HAND = "forearm_hand"     # 전완/손 (핸드체크, 리치인)
    HIP_WAIST = "hip_waist"           # 골반/허리 (블로킹/차징)
    THIGH = "thigh"                   # 대퇴
    KNEE = "knee"                     # 무릎 (위험 접촉)
    LOWER_LEG = "lower_leg"          # 하퇴
    FOOT = "foot"                     # 발 (트리핑)
    BALL_HAND = "ball_hand"           # 볼/볼 보유 손 (클린 스틸 vs 파울)

    def __str__(self) -> str:
        return self.value

    @property
    def is_high_risk(self) -> bool:
        """고위험 접촉 부위 여부 (머리/목, 무릎)."""
        return self in (ContactArea.HEAD_NECK, ContactArea.KNEE)

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 부위명 반환."""
        return _CONTACT_AREA_I18N[self].get(
            lang, _CONTACT_AREA_I18N[self][SupportedLanguage.KO]
        )


_CONTACT_AREA_I18N: dict[ContactArea, dict[SupportedLanguage, str]] = {
    ContactArea.HEAD_NECK: {
        SupportedLanguage.KO: "머리/목",
        SupportedLanguage.EN: "Head/Neck",
        SupportedLanguage.JA: "頭部/首",
        SupportedLanguage.ZH: "头颈",
        SupportedLanguage.ES: "Cabeza/Cuello",
    },
    ContactArea.SHOULDER: {
        SupportedLanguage.KO: "어깨",
        SupportedLanguage.EN: "Shoulder",
        SupportedLanguage.JA: "肩",
        SupportedLanguage.ZH: "肩部",
        SupportedLanguage.ES: "Hombro",
    },
    ContactArea.CHEST_TORSO: {
        SupportedLanguage.KO: "가슴/체간",
        SupportedLanguage.EN: "Chest/Torso",
        SupportedLanguage.JA: "胸部/体幹",
        SupportedLanguage.ZH: "胸部/躯干",
        SupportedLanguage.ES: "Pecho/Torso",
    },
    ContactArea.BACK: {
        SupportedLanguage.KO: "등",
        SupportedLanguage.EN: "Back",
        SupportedLanguage.JA: "背中",
        SupportedLanguage.ZH: "背部",
        SupportedLanguage.ES: "Espalda",
    },
    ContactArea.UPPER_ARM: {
        SupportedLanguage.KO: "상완",
        SupportedLanguage.EN: "Upper Arm",
        SupportedLanguage.JA: "上腕",
        SupportedLanguage.ZH: "上臂",
        SupportedLanguage.ES: "Brazo Superior",
    },
    ContactArea.FOREARM_HAND: {
        SupportedLanguage.KO: "전완/손",
        SupportedLanguage.EN: "Forearm/Hand",
        SupportedLanguage.JA: "前腕/手",
        SupportedLanguage.ZH: "前臂/手",
        SupportedLanguage.ES: "Antebrazo/Mano",
    },
    ContactArea.HIP_WAIST: {
        SupportedLanguage.KO: "골반/허리",
        SupportedLanguage.EN: "Hip/Waist",
        SupportedLanguage.JA: "腰/ウエスト",
        SupportedLanguage.ZH: "髋/腰",
        SupportedLanguage.ES: "Cadera/Cintura",
    },
    ContactArea.THIGH: {
        SupportedLanguage.KO: "대퇴",
        SupportedLanguage.EN: "Thigh",
        SupportedLanguage.JA: "大腿",
        SupportedLanguage.ZH: "大腿",
        SupportedLanguage.ES: "Muslo",
    },
    ContactArea.KNEE: {
        SupportedLanguage.KO: "무릎",
        SupportedLanguage.EN: "Knee",
        SupportedLanguage.JA: "膝",
        SupportedLanguage.ZH: "膝盖",
        SupportedLanguage.ES: "Rodilla",
    },
    ContactArea.LOWER_LEG: {
        SupportedLanguage.KO: "하퇴",
        SupportedLanguage.EN: "Lower Leg",
        SupportedLanguage.JA: "下腿",
        SupportedLanguage.ZH: "小腿",
        SupportedLanguage.ES: "Pierna Inferior",
    },
    ContactArea.FOOT: {
        SupportedLanguage.KO: "발",
        SupportedLanguage.EN: "Foot",
        SupportedLanguage.JA: "足",
        SupportedLanguage.ZH: "脚",
        SupportedLanguage.ES: "Pie",
    },
    ContactArea.BALL_HAND: {
        SupportedLanguage.KO: "볼/손",
        SupportedLanguage.EN: "Ball/Hand",
        SupportedLanguage.JA: "ボール/手",
        SupportedLanguage.ZH: "球/手",
        SupportedLanguage.ES: "Balón/Mano",
    },
}


# =============================================================================
# 판정 신뢰도 임계치
# =============================================================================

# 자동 확정 최소 신뢰도
DECISION_AUTO_CONFIRM_THRESHOLD: Final[float] = 0.95

# 높은 확신 최소 신뢰도
DECISION_HIGH_CONFIDENCE_THRESHOLD: Final[float] = 0.85

# 보통 확신 최소 신뢰도
DECISION_MODERATE_CONFIDENCE_THRESHOLD: Final[float] = 0.70

# 최소 판정 가능 신뢰도 (이하면 "판정 불가")
DECISION_MIN_ACTIONABLE_THRESHOLD: Final[float] = 0.50


# =============================================================================
# 바이올레이션 감지 임계치
# =============================================================================

# --- 트래블링 ---
# 피벗풋 이탈 감지 임계치 (미터, 피벗풋 위치 변화)
TRAVELING_PIVOT_DISPLACEMENT_M: Final[float] = 0.15

# 개더 후 허용 스텝 수
TRAVELING_MAX_STEPS_AFTER_GATHER: Final[int] = 2

# --- 더블 드리블 ---
# 드리블 중단 판정 시간 (초, 손에 볼 체류)
DOUBLE_DRIBBLE_HOLD_TIME_SEC: Final[float] = 0.3

# --- 캐리(팜잉) ---
# 손바닥 각도 임계치 (도, 볼 아래 회전 감지)
CARRY_PALM_ANGLE_THRESHOLD_DEG: Final[float] = 135.0

# 캐리 판정 볼 체류 시간 (초)
CARRY_BALL_REST_TIME_SEC: Final[float] = 0.15

# --- 킥볼 ---
# 발 의도성 판별 — 발 이동 속도 임계치 (m/s, 의도적 차기)
KICK_BALL_FOOT_VELOCITY_MIN: Final[float] = 1.5

# --- 3초 위반 (공격) ---
# 페인트존 체류 시간 임계치 (초)
THREE_SECOND_OFFENSE_THRESHOLD_SEC: Final[float] = 3.0

# 3초 카운터 리셋 조건: 페인트 외부 이탈 최소 거리 (미터)
THREE_SECOND_EXIT_DISTANCE_M: Final[float] = 0.5

# --- 3초 위반 (수비, NBA 전용) ---
# 마크맨 근접 거리 (미터, 이 거리 이내면 3초 면제)
DEFENSIVE_THREE_SEC_MARKING_DISTANCE_M: Final[float] = 0.91  # ~arm's length (3ft)

# --- 5초 위반 ---
# 인바운드 5초 (초)
FIVE_SECOND_INBOUND_SEC: Final[float] = 5.0

# 밀접 수비 5초 (FIBA, 초) — 공 보유자가 정상 플레이 시도 안 할 때
FIVE_SECOND_HELD_BALL_SEC: Final[float] = 5.0

# --- 8초 위반 ---
# 백코트 → 프론트코트 전진 제한 시간 (초)
EIGHT_SECOND_BACKCOURT_SEC: Final[float] = 8.0

# --- 골텐딩/인터페어런스 ---
# 공 하강 궤도 판정 — 최소 하강 속도 (m/s, 음수)
GOALTENDING_MIN_DESCENT_SPEED: Final[float] = -0.5

# 림 실린더 반경 (미터, 이 안에 볼이 있으면 인터페어런스 후보)
RIM_CYLINDER_RADIUS_M: Final[float] = 0.225

# --- 아웃오브바운즈 ---
# 라인 밟음 판정 여유 (미터, 발 중심~라인 거리)
OUT_OF_BOUNDS_MARGIN_M: Final[float] = 0.05


# =============================================================================
# 파울 판정 임계치
# =============================================================================

# 블로킹/차징 판정 — 수비자 위치 확립 기준
# 수비자가 접촉 전 이 시간(초) 이상 고정 = 차징, 미만 = 블로킹
CHARGE_BLOCK_SET_TIME_SEC: Final[float] = 0.3

# 수비자 발 고정 판정 — 발 위치 변화 임계치 (미터)
DEFENDER_FEET_SET_DISPLACEMENT_M: Final[float] = 0.10

# 리치인 파울 — 팔 신전 속도 임계치 (m/s, 볼 방향 빠른 팔 동작)
REACH_IN_ARM_SPEED_THRESHOLD: Final[float] = 2.0

# 핸드체크 — 접촉 지속 시간 임계치 (초)
HAND_CHECK_DURATION_THRESHOLD_SEC: Final[float] = 0.5

# 홀딩 — 상대 이동 제한 감지 (상대 속도 감소율 %)
HOLDING_SPEED_REDUCTION_PCT: Final[float] = 0.30

# 일리걸 스크린 — 스크리너 이동 감지 (접촉 시 이동 속도 m/s)
ILLEGAL_SCREEN_MOVEMENT_THRESHOLD: Final[float] = 0.5

# 접촉 강도 점수 — 플래그런트 1 기준
FLAGRANT_1_SEVERITY_SCORE: Final[float] = 0.65

# 접촉 강도 점수 — 플래그런트 2 기준
FLAGRANT_2_SEVERITY_SCORE: Final[float] = 0.85

# 볼 관련성 점수 — 이 미만이면 "볼 플레이 시도 없음" (UF 판정 근거)
BALL_RELATEDNESS_THRESHOLD: Final[float] = 0.30

# 와인드업 모션 감지 — 팔 각속도 임계치 (°/s)
WINDUP_ANGULAR_VELOCITY_THRESHOLD: Final[float] = 500.0


# =============================================================================
# 슈팅파울 분류 파라미터
# =============================================================================

# 슛 모션 시작 판정 — 팔 상향 속도 임계치 (m/s)
SHOOTING_MOTION_START_SPEED: Final[float] = 1.0

# 슛 릴리즈 판정 — 공 손 분리 거리 (미터)
SHOT_RELEASE_SEPARATION_M: Final[float] = 0.10

# 개더-투-슛 전환 최대 시간 (초)
GATHER_TO_SHOT_MAX_SEC: Final[float] = 0.5

# 바스켓 카운트(앤드원) — 릴리즈 후 공 림 통과 최대 시간 (초)
AND_ONE_MAX_FLIGHT_TIME_SEC: Final[float] = 3.0


# =============================================================================
# 테크니컬 파울 감지 파라미터 (영상 감지 가능 항목만)
# =============================================================================

# 림 매달리기 최대 허용 시간 (초)
RIM_HANGING_MAX_SEC: Final[float] = 2.0

# 림 매달리기 위험 회피 면제 — 아래에 사람 존재 시 면제 판정 거리 (미터)
RIM_HANGING_SAFETY_RADIUS_M: Final[float] = 1.5

# 지연행위 — 데드볼 후 볼 반환 최대 시간 (초)
DELAY_OF_GAME_MAX_SEC: Final[float] = 5.0

# 코트 인원 초과 감지 — 한 팀 최대 인원 (정규)
MAX_PLAYERS_ON_COURT_PER_TEAM: Final[int] = 5


# =============================================================================
# 멀티앵글 검증 파라미터
# =============================================================================

# 멀티앵글 크로스체크 최소 카메라 수
MULTI_ANGLE_MIN_CAMERAS: Final[int] = 2

# 멀티앵글 일치 임계치 (카메라 간 판정 일치율)
MULTI_ANGLE_AGREEMENT_THRESHOLD: Final[float] = 0.75

# 카메라 간 판정 불일치 시 최대 허용 편차 (초, 시점 차이)
MULTI_ANGLE_TIME_TOLERANCE_SEC: Final[float] = 0.05

# 최적 앵글 선정 — 시야각 확보 최소 각도 차이 (도)
OPTIMAL_ANGLE_MIN_SEPARATION_DEG: Final[float] = 30.0


# =============================================================================
# 판정 일관성 추적 파라미터
# =============================================================================

# 일관성 윈도우 (최근 N개 유사 이벤트와 비교)
CONSISTENCY_COMPARISON_WINDOW: Final[int] = 10

# 일관성 이탈 임계치 (동일 강도 접촉에서 다른 판정 비율)
CONSISTENCY_DEVIATION_THRESHOLD: Final[float] = 0.20

# 콜 레벨 캘리브레이션 — 초기 학습 구간 (경기 시작 후 접촉 횟수)
CALL_LEVEL_CALIBRATION_EVENTS: Final[int] = 15

# 판정 이력 기반 접촉 강도 빈 폭 (점수 단위)
SEVERITY_BIN_WIDTH: Final[float] = 0.10


# =============================================================================
# 리플레이/챌린지 파라미터
# =============================================================================

# 리플레이 검토 최대 시간 (초)
REPLAY_MAX_REVIEW_TIME_SEC: Final[int] = 120

# 코치 챌린지 성공 시 추가 챌린지 부여
CHALLENGE_SUCCESS_REFUND: Final[bool] = True

# 챌린지 가능한 최소 남은 시간 (초, 4Q/OT)
CHALLENGE_MIN_REMAINING_SEC: Final[int] = 0  # 항상 가능


# =============================================================================
# 유틸리티 함수
# =============================================================================

def classify_decision_confidence(confidence: float) -> DecisionConfidence:
    """
    신뢰도 수치로 판정 등급 분류.

    Args:
        confidence: 신뢰도 (0.0~1.0)

    Returns:
        DecisionConfidence 등급
    """
    if confidence >= DECISION_AUTO_CONFIRM_THRESHOLD:
        return DecisionConfidence.AUTO_CONFIRM
    elif confidence >= DECISION_HIGH_CONFIDENCE_THRESHOLD:
        return DecisionConfidence.HIGH
    elif confidence >= DECISION_MODERATE_CONFIDENCE_THRESHOLD:
        return DecisionConfidence.MODERATE
    else:
        return DecisionConfidence.LOW


def classify_foul_grade(
    severity_score: float, ball_relatedness: float
) -> FoulGrade:
    """
    접촉 강도와 볼 관련성으로 파울 등급 분류.

    Args:
        severity_score: 접촉 강도 점수 (0.0~1.0)
        ball_relatedness: 볼 관련성 점수 (0.0~1.0)

    Returns:
        FoulGrade 등급
    """
    if severity_score >= FLAGRANT_2_SEVERITY_SCORE:
        return FoulGrade.FLAGRANT_2
    elif (severity_score >= FLAGRANT_1_SEVERITY_SCORE
          or ball_relatedness < BALL_RELATEDNESS_THRESHOLD):
        return FoulGrade.FLAGRANT_1
    else:
        return FoulGrade.NORMAL


def is_action_reviewable(
    confidence: float, is_scoring_play: bool = False
) -> bool:
    """
    해당 판정이 리뷰 대상인지 판별.

    Args:
        confidence: 판정 신뢰도
        is_scoring_play: 득점 관련 플레이 여부

    Returns:
        리뷰 대상 여부
    """
    threshold = DECISION_MODERATE_CONFIDENCE_THRESHOLD
    if is_scoring_play:
        threshold = DECISION_HIGH_CONFIDENCE_THRESHOLD
    return confidence < threshold


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__: list[str] = [
    # 버전
    "__version__",
    # 열거형
    "DecisionConfidence",
    "FoulGrade",
    "ContactArea",
    # 판정 신뢰도 임계치
    "DECISION_AUTO_CONFIRM_THRESHOLD",
    "DECISION_HIGH_CONFIDENCE_THRESHOLD",
    "DECISION_MODERATE_CONFIDENCE_THRESHOLD",
    "DECISION_MIN_ACTIONABLE_THRESHOLD",
    # 바이올레이션 감지 임계치
    "TRAVELING_PIVOT_DISPLACEMENT_M",
    "TRAVELING_MAX_STEPS_AFTER_GATHER",
    "DOUBLE_DRIBBLE_HOLD_TIME_SEC",
    "CARRY_PALM_ANGLE_THRESHOLD_DEG",
    "CARRY_BALL_REST_TIME_SEC",
    "KICK_BALL_FOOT_VELOCITY_MIN",
    "THREE_SECOND_OFFENSE_THRESHOLD_SEC",
    "THREE_SECOND_EXIT_DISTANCE_M",
    "DEFENSIVE_THREE_SEC_MARKING_DISTANCE_M",
    "FIVE_SECOND_INBOUND_SEC",
    "FIVE_SECOND_HELD_BALL_SEC",
    "EIGHT_SECOND_BACKCOURT_SEC",
    "GOALTENDING_MIN_DESCENT_SPEED",
    "RIM_CYLINDER_RADIUS_M",
    "OUT_OF_BOUNDS_MARGIN_M",
    # 파울 판정 임계치
    "CHARGE_BLOCK_SET_TIME_SEC",
    "DEFENDER_FEET_SET_DISPLACEMENT_M",
    "REACH_IN_ARM_SPEED_THRESHOLD",
    "HAND_CHECK_DURATION_THRESHOLD_SEC",
    "HOLDING_SPEED_REDUCTION_PCT",
    "ILLEGAL_SCREEN_MOVEMENT_THRESHOLD",
    "FLAGRANT_1_SEVERITY_SCORE",
    "FLAGRANT_2_SEVERITY_SCORE",
    "BALL_RELATEDNESS_THRESHOLD",
    "WINDUP_ANGULAR_VELOCITY_THRESHOLD",
    # 슈팅파울 분류
    "SHOOTING_MOTION_START_SPEED",
    "SHOT_RELEASE_SEPARATION_M",
    "GATHER_TO_SHOT_MAX_SEC",
    "AND_ONE_MAX_FLIGHT_TIME_SEC",
    # 테크니컬 파울
    "RIM_HANGING_MAX_SEC",
    "RIM_HANGING_SAFETY_RADIUS_M",
    "DELAY_OF_GAME_MAX_SEC",
    "MAX_PLAYERS_ON_COURT_PER_TEAM",
    # 멀티앵글 검증
    "MULTI_ANGLE_MIN_CAMERAS",
    "MULTI_ANGLE_AGREEMENT_THRESHOLD",
    "MULTI_ANGLE_TIME_TOLERANCE_SEC",
    "OPTIMAL_ANGLE_MIN_SEPARATION_DEG",
    # 판정 일관성
    "CONSISTENCY_COMPARISON_WINDOW",
    "CONSISTENCY_DEVIATION_THRESHOLD",
    "CALL_LEVEL_CALIBRATION_EVENTS",
    "SEVERITY_BIN_WIDTH",
    # 리플레이/챌린지
    "REPLAY_MAX_REVIEW_TIME_SEC",
    "CHALLENGE_SUCCESS_REFUND",
    "CHALLENGE_MIN_REMAINING_SEC",
    # 유틸리티 함수
    "classify_decision_confidence",
    "classify_foul_grade",
    "is_action_reviewable",
]
