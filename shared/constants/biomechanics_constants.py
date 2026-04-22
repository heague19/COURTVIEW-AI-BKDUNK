# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: biomechanics_constants.py
설명: 생체역학 분석 도메인 상수 정의
      - 신체 세그먼트 모델 (de Leva 1996 인체측정 모델)
      - 관절 가동 범위 (ROM - 임상 표준)
      - 농구 동작별 최적 관절 각도 (슈팅, 드리블, 수비)
      - 이동 속도/가속도 임계치 (연령/성별별)
      - 균형/안정성 파라미터
      - 동역학 힘/충격 임계치

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
- de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment inertia parameters.
  Journal of Biomechanics, 29(9), 1223-1230.
- Winter, D.A. (2009). Biomechanics and Motor Control of Human Movement, 4th Ed.
- ACSM Guidelines for Exercise Testing and Prescription, 11th Ed.
- Knudson, D. (2007). Fundamentals of Biomechanics, 2nd Ed.
- Okazaki, V.H.A. & Rodacki, A.L.F. (2012). Basketball jump shot kinematics.

사용처:
- biomechanics/kinematics/: 관절 각도, 속도, 가속도 분석
- biomechanics/dynamics/: 힘, 에너지, 균형 분석
- biomechanics/anthropometry/: 신체 세그먼트 모델링
- biomechanics/standards/: 연령대별 표준 기준
- motion_analysis/classification/: 동작 분류 기준값
- feedback_system/: 동작 피드백 참조값

사용 예시:
    >>> from shared.constants.biomechanics_constants import BodySegment, MovementIntensity
    >>> BodySegment.UPPER_ARM.is_bilateral
    True
    >>> BodySegment.HEAD.mass_ratio_male
    0.0694
    >>> MovementIntensity.SPRINTING.velocity_range_adult_male
    (5.5, 8.5)
    >>> MovementIntensity.RUNNING.velocity_range_adult_male
    (3.0, 5.5)
"""

from __future__ import annotations


from enum import Enum, unique
from typing import Final

from shared.constants.localization import SupportedLanguage
from shared.constants.player_constants import AgeGroup, Gender


# =============================================================================
# 신체 세그먼트 열거형 (de Leva 1996 모델 기반)
# =============================================================================
@unique
class BodySegment(str, Enum):
    """
    신체 세그먼트 열거형 (10종).

    de Leva (1996) 인체측정 모델 기준 분절.
    양측성 세그먼트(팔, 다리)는 좌/우 구분 없이 단일 정의하며,
    실제 적용 시 좌/우를 구분하여 사용합니다.

    세그먼트 질량비, 길이비, 관성 모멘트는 이 열거형을 키로 참조합니다.
    """

    HEAD = "head"
    NECK = "neck"
    TRUNK_UPPER = "trunk_upper"   # 상부 체간 (어깨~횡격막)
    TRUNK_LOWER = "trunk_lower"   # 하부 체간 (횡격막~골반)
    UPPER_ARM = "upper_arm"       # 상완 (어깨~팔꿈치)
    FOREARM = "forearm"           # 전완 (팔꿈치~손목)
    HAND = "hand"                 # 손 (손목~손끝)
    THIGH = "thigh"               # 대퇴 (골반~무릎)
    SHANK = "shank"               # 하퇴 (무릎~발목)
    FOOT = "foot"                 # 발 (발목~발끝)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 세그먼트명 반환."""
        return _SEGMENT_I18N_MAP[self].get(
            lang, _SEGMENT_I18N_MAP[self][SupportedLanguage.KO]
        )

    @property
    def is_bilateral(self) -> bool:
        """양측성(좌/우 대칭) 세그먼트 여부."""
        return self in _BILATERAL_SEGMENTS

    @property
    def mass_ratio_male(self) -> float:
        """남성 세그먼트 질량비 (전체 체중 대비, de Leva 1996)."""
        return SEGMENT_MASS_RATIO_MALE[self]

    @property
    def mass_ratio_female(self) -> float:
        """여성 세그먼트 질량비 (전체 체중 대비, de Leva 1996)."""
        return SEGMENT_MASS_RATIO_FEMALE[self]


# 양측성 세그먼트 집합
_BILATERAL_SEGMENTS: frozenset[BodySegment] = frozenset({
    BodySegment.UPPER_ARM,
    BodySegment.FOREARM,
    BodySegment.HAND,
    BodySegment.THIGH,
    BodySegment.SHANK,
    BodySegment.FOOT,
})

# 세그먼트 다국어 이름
_SEGMENT_I18N_MAP: dict[BodySegment, dict[SupportedLanguage, str]] = {
    BodySegment.HEAD: {
        SupportedLanguage.KO: "머리",
        SupportedLanguage.EN: "Head",
        SupportedLanguage.JA: "頭部",
        SupportedLanguage.ZH: "头部",
        SupportedLanguage.ES: "Cabeza",
    },
    BodySegment.NECK: {
        SupportedLanguage.KO: "목",
        SupportedLanguage.EN: "Neck",
        SupportedLanguage.JA: "首",
        SupportedLanguage.ZH: "颈部",
        SupportedLanguage.ES: "Cuello",
    },
    BodySegment.TRUNK_UPPER: {
        SupportedLanguage.KO: "상부 체간",
        SupportedLanguage.EN: "Upper Trunk",
        SupportedLanguage.JA: "上部体幹",
        SupportedLanguage.ZH: "上躯干",
        SupportedLanguage.ES: "Tronco Superior",
    },
    BodySegment.TRUNK_LOWER: {
        SupportedLanguage.KO: "하부 체간",
        SupportedLanguage.EN: "Lower Trunk",
        SupportedLanguage.JA: "下部体幹",
        SupportedLanguage.ZH: "下躯干",
        SupportedLanguage.ES: "Tronco Inferior",
    },
    BodySegment.UPPER_ARM: {
        SupportedLanguage.KO: "상완",
        SupportedLanguage.EN: "Upper Arm",
        SupportedLanguage.JA: "上腕",
        SupportedLanguage.ZH: "上臂",
        SupportedLanguage.ES: "Brazo Superior",
    },
    BodySegment.FOREARM: {
        SupportedLanguage.KO: "전완",
        SupportedLanguage.EN: "Forearm",
        SupportedLanguage.JA: "前腕",
        SupportedLanguage.ZH: "前臂",
        SupportedLanguage.ES: "Antebrazo",
    },
    BodySegment.HAND: {
        SupportedLanguage.KO: "손",
        SupportedLanguage.EN: "Hand",
        SupportedLanguage.JA: "手",
        SupportedLanguage.ZH: "手",
        SupportedLanguage.ES: "Mano",
    },
    BodySegment.THIGH: {
        SupportedLanguage.KO: "대퇴",
        SupportedLanguage.EN: "Thigh",
        SupportedLanguage.JA: "大腿",
        SupportedLanguage.ZH: "大腿",
        SupportedLanguage.ES: "Muslo",
    },
    BodySegment.SHANK: {
        SupportedLanguage.KO: "하퇴",
        SupportedLanguage.EN: "Shank",
        SupportedLanguage.JA: "下腿",
        SupportedLanguage.ZH: "小腿",
        SupportedLanguage.ES: "Pierna Inferior",
    },
    BodySegment.FOOT: {
        SupportedLanguage.KO: "발",
        SupportedLanguage.EN: "Foot",
        SupportedLanguage.JA: "足",
        SupportedLanguage.ZH: "脚",
        SupportedLanguage.ES: "Pie",
    },
}


# =============================================================================
# 동작 페이즈 열거형
# =============================================================================
@unique
class MotionPhase(str, Enum):
    """
    동작 페이즈 열거형 (4단계).

    모든 운동 동작의 범용 페이즈 분류.
    슈팅, 드리블, 점프, 커팅 등 모든 농구 동작에 적용.
    개별 동작의 세부 페이즈는 motion_analysis 레이어에서 정의.
    """

    PREPARATION = "preparation"       # 준비 (와인드업, 스쿼트)
    EXECUTION = "execution"           # 실행 (파워 페이즈, 릴리즈)
    FOLLOW_THROUGH = "follow_through" # 팔로스루 (감속, 마무리)
    RECOVERY = "recovery"             # 회복 (레디 포지션 복귀)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 페이즈명 반환."""
        return _PHASE_I18N_MAP[self].get(
            lang, _PHASE_I18N_MAP[self][SupportedLanguage.KO]
        )


_PHASE_I18N_MAP: dict[MotionPhase, dict[SupportedLanguage, str]] = {
    MotionPhase.PREPARATION: {
        SupportedLanguage.KO: "준비",
        SupportedLanguage.EN: "Preparation",
        SupportedLanguage.JA: "準備",
        SupportedLanguage.ZH: "准备",
        SupportedLanguage.ES: "Preparación",
    },
    MotionPhase.EXECUTION: {
        SupportedLanguage.KO: "실행",
        SupportedLanguage.EN: "Execution",
        SupportedLanguage.JA: "実行",
        SupportedLanguage.ZH: "执行",
        SupportedLanguage.ES: "Ejecución",
    },
    MotionPhase.FOLLOW_THROUGH: {
        SupportedLanguage.KO: "팔로스루",
        SupportedLanguage.EN: "Follow-through",
        SupportedLanguage.JA: "フォロースルー",
        SupportedLanguage.ZH: "跟进",
        SupportedLanguage.ES: "Seguimiento",
    },
    MotionPhase.RECOVERY: {
        SupportedLanguage.KO: "회복",
        SupportedLanguage.EN: "Recovery",
        SupportedLanguage.JA: "回復",
        SupportedLanguage.ZH: "恢复",
        SupportedLanguage.ES: "Recuperación",
    },
}


# =============================================================================
# 이동 강도 열거형 (속도 기반)
# =============================================================================
@unique
class MovementIntensity(str, Enum):
    """
    이동 강도 열거형 (6단계).

    선수 이동 속도를 기반으로 한 운동 강도 분류.
    피로도 분석, 트래킹 스탯, 경기 흐름 분석에 사용.
    """

    STATIONARY = "stationary"   # 정지 (0.0~0.3 m/s)
    WALKING = "walking"         # 걷기 (0.3~1.5 m/s)
    JOGGING = "jogging"         # 조깅 (1.5~3.0 m/s)
    RUNNING = "running"         # 달리기 (3.0~5.5 m/s)
    SPRINTING = "sprinting"     # 전력질주 (5.5~8.5 m/s)
    MAX_EFFORT = "max_effort"   # 최대 출력 (8.5+ m/s)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 강도명 반환."""
        return _INTENSITY_I18N_MAP[self].get(
            lang, _INTENSITY_I18N_MAP[self][SupportedLanguage.KO]
        )

    @property
    def velocity_range_adult_male(self) -> tuple[float, float]:
        """성인 남성 기준 속도 범위 (m/s)."""
        return VELOCITY_THRESHOLDS_ADULT_MALE[self]


_INTENSITY_I18N_MAP: dict[MovementIntensity, dict[SupportedLanguage, str]] = {
    MovementIntensity.STATIONARY: {
        SupportedLanguage.KO: "정지",
        SupportedLanguage.EN: "Stationary",
        SupportedLanguage.JA: "静止",
        SupportedLanguage.ZH: "静止",
        SupportedLanguage.ES: "Estacionario",
    },
    MovementIntensity.WALKING: {
        SupportedLanguage.KO: "걷기",
        SupportedLanguage.EN: "Walking",
        SupportedLanguage.JA: "歩行",
        SupportedLanguage.ZH: "步行",
        SupportedLanguage.ES: "Caminar",
    },
    MovementIntensity.JOGGING: {
        SupportedLanguage.KO: "조깅",
        SupportedLanguage.EN: "Jogging",
        SupportedLanguage.JA: "ジョギング",
        SupportedLanguage.ZH: "慢跑",
        SupportedLanguage.ES: "Trotar",
    },
    MovementIntensity.RUNNING: {
        SupportedLanguage.KO: "달리기",
        SupportedLanguage.EN: "Running",
        SupportedLanguage.JA: "ランニング",
        SupportedLanguage.ZH: "跑步",
        SupportedLanguage.ES: "Correr",
    },
    MovementIntensity.SPRINTING: {
        SupportedLanguage.KO: "전력질주",
        SupportedLanguage.EN: "Sprinting",
        SupportedLanguage.JA: "スプリント",
        SupportedLanguage.ZH: "冲刺",
        SupportedLanguage.ES: "Sprint",
    },
    MovementIntensity.MAX_EFFORT: {
        SupportedLanguage.KO: "최대 출력",
        SupportedLanguage.EN: "Max Effort",
        SupportedLanguage.JA: "最大出力",
        SupportedLanguage.ZH: "最大输出",
        SupportedLanguage.ES: "Esfuerzo Máximo",
    },
}


# =============================================================================
# 스탠스(자세) 열거형 — 농구 동작 자세
# =============================================================================
@unique
class StanceType(str, Enum):
    """
    농구 스탠스(자세) 열거형 (8종).

    농구 경기 중 선수의 기본 자세 분류.
    동작 분류 및 자세 분석의 기준 자세로 사용.
    """

    ATHLETIC_READY = "athletic_ready"         # 기본 레디 자세 (무릎 약간 굽힘)
    TRIPLE_THREAT = "triple_threat"           # 트리플 스렛 자세 (공 보유 시)
    DEFENSIVE_STANCE = "defensive_stance"     # 수비 자세 (무릎 굽힘, 넓은 보폭)
    SHOOTING_SET = "shooting_set"             # 슈팅 세트 자세 (무릎 굽힘, 공 위치)
    POST_UP = "post_up"                       # 포스트업 자세 (등 대고 저자세)
    BOXING_OUT = "boxing_out"                 # 박스아웃 자세 (넓은 저자세)
    SPRINT_LEAN = "sprint_lean"               # 전력질주 자세 (전방 경사)
    JUMP_READY = "jump_ready"                 # 점프 준비 자세 (깊은 무릎 굽힘)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 스탠스명 반환."""
        return _STANCE_I18N_MAP[self].get(
            lang, _STANCE_I18N_MAP[self][SupportedLanguage.KO]
        )


_STANCE_I18N_MAP: dict[StanceType, dict[SupportedLanguage, str]] = {
    StanceType.ATHLETIC_READY: {
        SupportedLanguage.KO: "기본 레디 자세",
        SupportedLanguage.EN: "Athletic Ready",
        SupportedLanguage.JA: "アスレチックレディ",
        SupportedLanguage.ZH: "运动准备姿势",
        SupportedLanguage.ES: "Posición Atlética",
    },
    StanceType.TRIPLE_THREAT: {
        SupportedLanguage.KO: "트리플 스렛",
        SupportedLanguage.EN: "Triple Threat",
        SupportedLanguage.JA: "トリプルスレット",
        SupportedLanguage.ZH: "三威胁姿势",
        SupportedLanguage.ES: "Triple Amenaza",
    },
    StanceType.DEFENSIVE_STANCE: {
        SupportedLanguage.KO: "수비 자세",
        SupportedLanguage.EN: "Defensive Stance",
        SupportedLanguage.JA: "ディフェンス姿勢",
        SupportedLanguage.ZH: "防守姿势",
        SupportedLanguage.ES: "Posición Defensiva",
    },
    StanceType.SHOOTING_SET: {
        SupportedLanguage.KO: "슈팅 세트",
        SupportedLanguage.EN: "Shooting Set",
        SupportedLanguage.JA: "シューティングセット",
        SupportedLanguage.ZH: "投篮准备",
        SupportedLanguage.ES: "Posición de Tiro",
    },
    StanceType.POST_UP: {
        SupportedLanguage.KO: "포스트업",
        SupportedLanguage.EN: "Post Up",
        SupportedLanguage.JA: "ポストアップ",
        SupportedLanguage.ZH: "背身单打",
        SupportedLanguage.ES: "Poste Bajo",
    },
    StanceType.BOXING_OUT: {
        SupportedLanguage.KO: "박스아웃",
        SupportedLanguage.EN: "Boxing Out",
        SupportedLanguage.JA: "ボックスアウト",
        SupportedLanguage.ZH: "卡位",
        SupportedLanguage.ES: "Bloqueo de Rebote",
    },
    StanceType.SPRINT_LEAN: {
        SupportedLanguage.KO: "전력질주",
        SupportedLanguage.EN: "Sprint Lean",
        SupportedLanguage.JA: "スプリント",
        SupportedLanguage.ZH: "冲刺姿势",
        SupportedLanguage.ES: "Inclinación de Sprint",
    },
    StanceType.JUMP_READY: {
        SupportedLanguage.KO: "점프 준비",
        SupportedLanguage.EN: "Jump Ready",
        SupportedLanguage.JA: "ジャンプ準備",
        SupportedLanguage.ZH: "起跳准备",
        SupportedLanguage.ES: "Preparación de Salto",
    },
}


# =============================================================================
# 인체측정 모델: 세그먼트 질량비 (de Leva 1996)
# =============================================================================
# 전체 체중 대비 각 세그먼트의 질량 비율 (0.0~1.0)
# 양측성 세그먼트는 한쪽 값 (양쪽 합산 시 ×2)
# 참조: de Leva, P. (1996). J. Biomechanics, 29(9), 1223-1230.

SEGMENT_MASS_RATIO_MALE: Final[dict[BodySegment, float]] = {
    BodySegment.HEAD: 0.0694,
    BodySegment.NECK: 0.0138,
    BodySegment.TRUNK_UPPER: 0.2160,
    BodySegment.TRUNK_LOWER: 0.2186,
    BodySegment.UPPER_ARM: 0.0271,       # 한쪽
    BodySegment.FOREARM: 0.0162,          # 한쪽
    BodySegment.HAND: 0.0061,             # 한쪽
    BodySegment.THIGH: 0.1416,            # 한쪽
    BodySegment.SHANK: 0.0433,            # 한쪽
    BodySegment.FOOT: 0.0137,             # 한쪽
}

SEGMENT_MASS_RATIO_FEMALE: Final[dict[BodySegment, float]] = {
    BodySegment.HEAD: 0.0668,
    BodySegment.NECK: 0.0119,
    BodySegment.TRUNK_UPPER: 0.2039,
    BodySegment.TRUNK_LOWER: 0.2218,
    BodySegment.UPPER_ARM: 0.0255,        # 한쪽
    BodySegment.FOREARM: 0.0138,          # 한쪽
    BodySegment.HAND: 0.0056,             # 한쪽
    BodySegment.THIGH: 0.1478,            # 한쪽
    BodySegment.SHANK: 0.0481,            # 한쪽
    BodySegment.FOOT: 0.0129,             # 한쪽
}


# =============================================================================
# 인체측정 모델: 세그먼트 길이비 (신장 대비)
# =============================================================================
# 전체 신장 대비 각 세그먼트 길이 비율 (0.0~1.0)
# 성별 차이가 미미하여 공통값 사용 (Drillis & Contini, 1966)

SEGMENT_LENGTH_RATIO: Final[dict[BodySegment, float]] = {
    BodySegment.HEAD: 0.130,
    BodySegment.NECK: 0.052,
    BodySegment.TRUNK_UPPER: 0.152,
    BodySegment.TRUNK_LOWER: 0.148,
    BodySegment.UPPER_ARM: 0.172,
    BodySegment.FOREARM: 0.157,
    BodySegment.HAND: 0.0575,
    BodySegment.THIGH: 0.232,
    BodySegment.SHANK: 0.247,
    BodySegment.FOOT: 0.0425,
}


# =============================================================================
# 인체측정 모델: 무게중심 근위 비율 (de Leva 1996)
# =============================================================================
# 세그먼트 근위단(proximal end)으로부터 무게중심까지의 거리 / 세그먼트 길이
# 역학 분석 시 토크 계산에 필수

SEGMENT_COM_PROXIMAL_MALE: Final[dict[BodySegment, float]] = {
    BodySegment.HEAD: 0.5002,
    BodySegment.NECK: 0.5002,
    BodySegment.TRUNK_UPPER: 0.4486,
    BodySegment.TRUNK_LOWER: 0.4486,
    BodySegment.UPPER_ARM: 0.5772,
    BodySegment.FOREARM: 0.4574,
    BodySegment.HAND: 0.7900,
    BodySegment.THIGH: 0.4095,
    BodySegment.SHANK: 0.4459,
    BodySegment.FOOT: 0.4415,
}

SEGMENT_COM_PROXIMAL_FEMALE: Final[dict[BodySegment, float]] = {
    BodySegment.HEAD: 0.4841,
    BodySegment.NECK: 0.4841,
    BodySegment.TRUNK_UPPER: 0.4964,
    BodySegment.TRUNK_LOWER: 0.4964,
    BodySegment.UPPER_ARM: 0.5754,
    BodySegment.FOREARM: 0.4559,
    BodySegment.HAND: 0.7474,
    BodySegment.THIGH: 0.3612,
    BodySegment.SHANK: 0.4416,
    BodySegment.FOOT: 0.4014,
}


# =============================================================================
# 인체측정 모델: 회전 반경비 (de Leva 1996)
# =============================================================================
# 무게중심 기준 회전 반경 / 세그먼트 길이 (관성 모멘트 계산용)

SEGMENT_GYRATION_RADIUS_MALE: Final[dict[BodySegment, float]] = {
    BodySegment.HEAD: 0.303,
    BodySegment.NECK: 0.303,
    BodySegment.TRUNK_UPPER: 0.372,
    BodySegment.TRUNK_LOWER: 0.372,
    BodySegment.UPPER_ARM: 0.285,
    BodySegment.FOREARM: 0.276,
    BodySegment.HAND: 0.288,
    BodySegment.THIGH: 0.329,
    BodySegment.SHANK: 0.302,
    BodySegment.FOOT: 0.257,
}

SEGMENT_GYRATION_RADIUS_FEMALE: Final[dict[BodySegment, float]] = {
    BodySegment.HEAD: 0.271,
    BodySegment.NECK: 0.271,
    BodySegment.TRUNK_UPPER: 0.357,
    BodySegment.TRUNK_LOWER: 0.357,
    BodySegment.UPPER_ARM: 0.278,
    BodySegment.FOREARM: 0.261,
    BodySegment.HAND: 0.244,
    BodySegment.THIGH: 0.369,
    BodySegment.SHANK: 0.271,
    BodySegment.FOOT: 0.299,
}


# =============================================================================
# 관절 가동 범위 (ROM) — 임상 표준 (ACSM)
# =============================================================================
# 딕셔너리 키: "관절_동작" 문자열
# 값: (최소각도, 최대각도) in degrees
# 참조: American College of Sports Medicine (ACSM) Guidelines

JOINT_ROM_NORMAL: Final[dict[str, tuple[float, float]]] = {
    # 어깨 관절
    "shoulder_flexion": (0.0, 180.0),
    "shoulder_extension": (0.0, 60.0),
    "shoulder_abduction": (0.0, 180.0),
    "shoulder_adduction": (0.0, 45.0),
    "shoulder_internal_rotation": (0.0, 70.0),
    "shoulder_external_rotation": (0.0, 90.0),
    # 팔꿈치 관절
    "elbow_flexion": (0.0, 150.0),
    "elbow_extension": (0.0, 0.0),        # 0 = 완전 신전
    "elbow_pronation": (0.0, 80.0),
    "elbow_supination": (0.0, 80.0),
    # 손목 관절
    "wrist_flexion": (0.0, 80.0),
    "wrist_extension": (0.0, 70.0),
    "wrist_radial_deviation": (0.0, 20.0),
    "wrist_ulnar_deviation": (0.0, 30.0),
    # 고관절
    "hip_flexion": (0.0, 120.0),
    "hip_extension": (0.0, 30.0),
    "hip_abduction": (0.0, 45.0),
    "hip_adduction": (0.0, 30.0),
    "hip_internal_rotation": (0.0, 45.0),
    "hip_external_rotation": (0.0, 45.0),
    # 무릎 관절
    "knee_flexion": (0.0, 135.0),
    "knee_extension": (0.0, 0.0),         # 0 = 완전 신전
    # 발목 관절
    "ankle_dorsiflexion": (0.0, 20.0),
    "ankle_plantarflexion": (0.0, 50.0),
    "ankle_inversion": (0.0, 35.0),
    "ankle_eversion": (0.0, 20.0),
    # 척추
    "spine_flexion": (0.0, 80.0),
    "spine_extension": (0.0, 30.0),
    "spine_lateral_flexion": (0.0, 35.0),
    "spine_rotation": (0.0, 45.0),
}


# =============================================================================
# 농구 슈팅 동작: 최적 관절 각도 (도 단위)
# =============================================================================
# 기반: Okazaki & Rodacki (2012), Knudson (2007) 슈팅 역학 연구
# 값: (최소 적정각도, 최대 적정각도) — 이 범위 내가 "양호"

SHOOTING_OPTIMAL_ANGLES: Final[dict[str, tuple[float, float]]] = {
    # 릴리즈 시점 (Execution 페이즈)
    "release_shoulder_flexion": (85.0, 105.0),     # 어깨 굴곡
    "release_elbow_angle": (150.0, 170.0),         # 팔꿈치 (거의 완전 신전)
    "release_wrist_flexion": (40.0, 65.0),         # 손목 스냅
    "release_guide_hand_separation": (15.0, 45.0), # 가이드핸드 분리 각도
    # 세트 자세 (Preparation 페이즈)
    "set_knee_flexion": (100.0, 135.0),            # 무릎 굽힘 (파워 생성)
    "set_hip_flexion": (155.0, 175.0),             # 골반 (거의 직립)
    "set_elbow_angle": (70.0, 100.0),              # 세트 포지션 팔꿈치
    "set_shoulder_flexion": (45.0, 70.0),           # 세트 포지션 어깨
    # 팔로스루 (Follow-through 페이즈)
    "followthrough_wrist_flexion": (60.0, 85.0),   # 스냅 완료
    "followthrough_elbow_angle": (165.0, 180.0),   # 완전 신전
    # 공 궤적 관련
    "ball_release_angle": (48.0, 55.0),            # 공 발사 각도 (수평 대비)
}


# =============================================================================
# 농구 수비 자세: 최적 관절 각도
# =============================================================================

DEFENSIVE_STANCE_ANGLES: Final[dict[str, tuple[float, float]]] = {
    "knee_flexion": (90.0, 135.0),           # 무릎 굽힘
    "hip_flexion": (130.0, 160.0),           # 골반 굽힘
    "ankle_dorsiflexion": (5.0, 20.0),       # 발목 배굴
    "trunk_forward_lean": (5.0, 20.0),       # 체간 전방 경사 (도)
    "stance_width_shoulder_ratio": (1.2, 1.8), # 보폭/어깨너비 비율
}


# =============================================================================
# 드리블 자세: 최적 관절 각도
# =============================================================================

DRIBBLING_STANCE_ANGLES: Final[dict[str, tuple[float, float]]] = {
    "knee_flexion": (100.0, 140.0),
    "hip_flexion": (145.0, 170.0),
    "shoulder_flexion": (15.0, 45.0),          # 드리블 손 어깨
    "elbow_angle": (90.0, 140.0),             # 드리블 손 팔꿈치
    "wrist_extension": (10.0, 35.0),          # 푸시 다운 시 손목
    "trunk_forward_lean": (5.0, 15.0),        # 체간 전방 경사
}


# =============================================================================
# 점프/착지 동작: 참조 각도
# =============================================================================

JUMP_LANDING_ANGLES: Final[dict[str, tuple[float, float]]] = {
    # 점프 이륙 시
    "takeoff_knee_flexion": (110.0, 145.0),        # 파워 포지션
    "takeoff_ankle_plantarflexion": (30.0, 45.0),  # 발목 신전
    "takeoff_hip_flexion": (150.0, 175.0),
    # 정상 착지 (부상 예방 범위)
    "landing_knee_flexion": (30.0, 60.0),          # 초기 접지
    "landing_knee_flexion_peak": (80.0, 120.0),    # 최대 흡수
    "landing_hip_flexion": (130.0, 165.0),
    # 위험 착지 (부상 위험 — 이 범위 이탈 시 경고)
    "landing_valgus_threshold": (0.0, 10.0),       # 무릎 외반 허용 범위 (도)
}


# =============================================================================
# 이동 속도 임계치 (m/s) — 성인 남성 기준
# =============================================================================
# 농구 선수의 이동 강도 분류 기준값
# 참조: NBA/FIBA 트래킹 데이터 기반 (Second Spectrum, STATS)

VELOCITY_THRESHOLDS_ADULT_MALE: Final[dict[MovementIntensity, tuple[float, float]]] = {
    MovementIntensity.STATIONARY: (0.0, 0.3),
    MovementIntensity.WALKING: (0.3, 1.5),
    MovementIntensity.JOGGING: (1.5, 3.0),
    MovementIntensity.RUNNING: (3.0, 5.5),
    MovementIntensity.SPRINTING: (5.5, 8.5),
    MovementIntensity.MAX_EFFORT: (8.5, 12.0),
}

VELOCITY_THRESHOLDS_ADULT_FEMALE: Final[dict[MovementIntensity, tuple[float, float]]] = {
    MovementIntensity.STATIONARY: (0.0, 0.3),
    MovementIntensity.WALKING: (0.3, 1.4),
    MovementIntensity.JOGGING: (1.4, 2.7),
    MovementIntensity.RUNNING: (2.7, 5.0),
    MovementIntensity.SPRINTING: (5.0, 7.8),
    MovementIntensity.MAX_EFFORT: (7.8, 11.0),
}


# =============================================================================
# 연령대별 속도 보정 계수 (성인 = 1.0 기준)
# =============================================================================
# 성인 남성 기준 속도 임계치에 이 계수를 곱하여 연령대별 적용
# 참조: ACSM 체력 기준, 발달체육학 문헌

AGE_VELOCITY_FACTOR: Final[dict[AgeGroup, float]] = {
    AgeGroup.YOUTH: 0.65,    # 유소년 (6-12세): 성인의 ~65%
    AgeGroup.TEEN: 0.85,     # 청소년 (13-18세): 성인의 ~85%
    AgeGroup.ADULT: 1.00,    # 성인 (19-49세): 기준
    AgeGroup.SENIOR: 0.78,   # 시니어 (50세+): 성인의 ~78%
}

# 성별 속도 보정 계수 (남성 = 1.0 기준)
GENDER_VELOCITY_FACTOR: Final[dict[Gender, float]] = {
    Gender.MALE: 1.00,
    Gender.FEMALE: 0.90,
}


# =============================================================================
# 가속도 임계치 (m/s²) — 동작 분류 기준
# =============================================================================

# 일반 방향 전환 가속도
ACCELERATION_NORMAL_MIN: Final[float] = 2.0
ACCELERATION_NORMAL_MAX: Final[float] = 5.0

# 빠른 방향 전환 가속도
ACCELERATION_QUICK_MIN: Final[float] = 5.0
ACCELERATION_QUICK_MAX: Final[float] = 10.0

# 개별 관절 빠른 동작 속력 임계치 (cm/s)
# 슛 릴리스, 패스 동작 등에서 개별 관절(손목, 팔꿈치 등)의 빠른 움직임 판정 기준
# 참조: Okazaki & Rodacki (2012) — 슈팅 손 릴리스 속도 200+ cm/s
JOINT_FAST_MOTION_SPEED_CM_S: Final[float] = 200.0

# 폭발적 가속도 (스프린트 시작, 풀업 점퍼, 크로스오버)
ACCELERATION_EXPLOSIVE_THRESHOLD: Final[float] = 10.0

# 급제동 감속도 (음수 방향, 절대값으로 사용)
DECELERATION_HARD_STOP_THRESHOLD: Final[float] = 8.0


# =============================================================================
# 각속도 임계치 (°/s) — 슈팅/동작 분석
# =============================================================================

# 슈팅 팔꿈치 신전 각속도 (릴리즈 시)
SHOOTING_ELBOW_ANGULAR_VELOCITY: Final[tuple[float, float]] = (1200.0, 1800.0)

# 슈팅 손목 스냅 각속도 (릴리즈 시)
SHOOTING_WRIST_ANGULAR_VELOCITY: Final[tuple[float, float]] = (400.0, 800.0)

# 슈팅 시 골반 회전 각속도
SHOOTING_HIP_ROTATION_VELOCITY: Final[tuple[float, float]] = (100.0, 300.0)

# 패스 동작 팔 각속도 (체스트패스 기준)
PASSING_ARM_ANGULAR_VELOCITY: Final[tuple[float, float]] = (500.0, 1200.0)


# =============================================================================
# 균형/안정성 파라미터
# =============================================================================

# 안정성 지수 임계치 (0~100 스케일)
# 동적 안정성 지수가 이 값 이상이면 "안정" 판정
# 참조: 슛/수비 스탠스 유지, 착지 안정성 평가에 활용
STABILITY_INDEX_MIN_STABLE: Final[float] = 50.0

# 압력중심(COP) 동요 임계치 (cm) — 정적 균형
COP_SWAY_STABLE_THRESHOLD_CM: Final[float] = 3.0
COP_SWAY_UNSTABLE_THRESHOLD_CM: Final[float] = 6.0

# 착지 후 안정화 시간 임계치 (초)
STABILIZATION_TIME_GOOD_S: Final[float] = 0.3
STABILIZATION_TIME_ACCEPTABLE_S: Final[float] = 0.5
STABILIZATION_TIME_POOR_S: Final[float] = 1.0

# 지지 기저면 폭 (어깨 너비 대비 비율)
BASE_OF_SUPPORT_MIN_RATIO: Final[float] = 0.8   # 좁은 스탠스
BASE_OF_SUPPORT_OPTIMAL_RATIO: Final[float] = 1.2  # 적정 스탠스
BASE_OF_SUPPORT_MAX_RATIO: Final[float] = 2.0   # 넓은 스탠스

# 무게중심(COM) 높이 변화율 임계치 (점프/착지 감지)
COM_HEIGHT_CHANGE_JUMP_THRESHOLD: Final[float] = 0.15   # 신장의 15% 이상 상승 = 점프
COM_HEIGHT_CHANGE_LANDING_THRESHOLD: Final[float] = 0.10  # 신장의 10% 이상 하강 = 착지


# =============================================================================
# 동역학: 힘/충격 임계치
# =============================================================================

# 수직 지면반력 최대 배수 (체중의 N배)
VERTICAL_GRF_WALKING_BW: Final[float] = 1.2       # 걷기 시
VERTICAL_GRF_RUNNING_BW: Final[float] = 2.5       # 달리기 시
VERTICAL_GRF_JUMP_LANDING_BW: Final[float] = 5.0  # 점프 착지 시
VERTICAL_GRF_MAX_SAFE_BW: Final[float] = 7.0      # 안전 상한 (이상 = 부상 위험)

# 착지 충격 흡수 시간 임계치 (초)
LANDING_IMPACT_ABSORPTION_GOOD_S: Final[float] = 0.08    # 양호 (≥80ms)
LANDING_IMPACT_ABSORPTION_POOR_S: Final[float] = 0.04    # 불량 (<40ms, 부상 위험)

# 접촉 힘 임계치 (파울 감지 보조, 체중의 N배)
CONTACT_FORCE_LIGHT_BW: Final[float] = 0.3        # 경미 접촉
CONTACT_FORCE_MODERATE_BW: Final[float] = 0.8     # 보통 접촉
CONTACT_FORCE_HEAVY_BW: Final[float] = 1.5        # 강한 접촉 (파울 의심)
CONTACT_FORCE_EXCESSIVE_BW: Final[float] = 3.0    # 과도한 접촉 (플래그런트 의심)


# =============================================================================
# 에너지 소비 파라미터
# =============================================================================

# 기초 대사율 (kcal/kg/min) — 운동 강도별
ENERGY_RATE_STATIONARY: Final[float] = 0.017       # 정지
ENERGY_RATE_WALKING: Final[float] = 0.057          # 걷기
ENERGY_RATE_JOGGING: Final[float] = 0.110          # 조깅
ENERGY_RATE_RUNNING: Final[float] = 0.168          # 달리기
ENERGY_RATE_SPRINTING: Final[float] = 0.252        # 전력질주

# 농구 경기 평균 에너지 소비율 (kcal/kg/min)
ENERGY_RATE_BASKETBALL_GAME: Final[float] = 0.123

# 고에너지 프레임 판정 운동 에너지 임계치 (J)
# 슛 릴리스, 점프, 빠른 방향전환 등 고강도 동작의 운동 에너지 기준
# 참조: 농구 점프 시 평균 운동 에너지 50~150J (체중 80kg, 점프 높이 0.3~0.6m 기준)
HIGH_ENERGY_KINETIC_THRESHOLD_J: Final[float] = 50.0


# =============================================================================
# 연령대별 인체측정 보정 계수
# =============================================================================
# 성인(ADULT) 기준값에 대한 보정 비율
# 세그먼트 질량비와 길이비는 발달 단계에 따라 변함
# 참조: Jensen (1989), Pavol et al. (2002) 소아 인체측정 연구

# 연령대별 체간 대 하지 질량비 보정 (성인 = 1.0)
AGE_TRUNK_MASS_FACTOR: Final[dict[AgeGroup, float]] = {
    AgeGroup.YOUTH: 1.08,    # 유소년: 상대적으로 큰 머리/체간 비율
    AgeGroup.TEEN: 1.03,     # 청소년: 거의 성인 수준
    AgeGroup.ADULT: 1.00,
    AgeGroup.SENIOR: 1.05,   # 시니어: 근감소로 상대적 체간 비율 증가
}

# 연령대별 사지 길이 보정 계수 (성인 = 1.0)
AGE_LIMB_LENGTH_FACTOR: Final[dict[AgeGroup, float]] = {
    AgeGroup.YOUTH: 0.85,    # 유소년: 짧은 사지 (비율적)
    AgeGroup.TEEN: 0.95,     # 청소년: 사지 급성장
    AgeGroup.ADULT: 1.00,
    AgeGroup.SENIOR: 0.98,   # 시니어: 미미한 척추 단축
}


# =============================================================================
# 농구 동작별 관절 각도 적정 범위 (연령대별)
# =============================================================================
# 유소년/청소년은 성인 최적 범위에서 허용 범위를 넓혀 적용
# 값: 최적 범위의 양쪽 허용 마진 (도)

AGE_ANGLE_TOLERANCE: Final[dict[AgeGroup, float]] = {
    AgeGroup.YOUTH: 15.0,    # 유소년: ±15° 추가 허용
    AgeGroup.TEEN: 8.0,      # 청소년: ±8° 추가 허용
    AgeGroup.ADULT: 0.0,     # 성인: 최적 범위 그대로
    AgeGroup.SENIOR: 10.0,   # 시니어: ±10° 추가 허용
}


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 버전
    "__version__",
    # 열거형
    "BodySegment",
    "MotionPhase",
    "MovementIntensity",
    "StanceType",
    # 인체측정 모델: 질량비 (de Leva 1996)
    "SEGMENT_MASS_RATIO_MALE",
    "SEGMENT_MASS_RATIO_FEMALE",
    # 인체측정 모델: 길이비
    "SEGMENT_LENGTH_RATIO",
    # 인체측정 모델: 무게중심 근위 비율
    "SEGMENT_COM_PROXIMAL_MALE",
    "SEGMENT_COM_PROXIMAL_FEMALE",
    # 인체측정 모델: 회전 반경비
    "SEGMENT_GYRATION_RADIUS_MALE",
    "SEGMENT_GYRATION_RADIUS_FEMALE",
    # 관절 가동 범위 (ROM)
    "JOINT_ROM_NORMAL",
    # 농구 슈팅 최적 각도
    "SHOOTING_OPTIMAL_ANGLES",
    # 수비/드리블 자세 각도
    "DEFENSIVE_STANCE_ANGLES",
    "DRIBBLING_STANCE_ANGLES",
    # 점프/착지 참조 각도
    "JUMP_LANDING_ANGLES",
    # 이동 속도 임계치
    "VELOCITY_THRESHOLDS_ADULT_MALE",
    "VELOCITY_THRESHOLDS_ADULT_FEMALE",
    "AGE_VELOCITY_FACTOR",
    "GENDER_VELOCITY_FACTOR",
    # 관절 속력 임계치
    "JOINT_FAST_MOTION_SPEED_CM_S",
    # 가속도 임계치
    "ACCELERATION_NORMAL_MIN",
    "ACCELERATION_NORMAL_MAX",
    "ACCELERATION_QUICK_MIN",
    "ACCELERATION_QUICK_MAX",
    "ACCELERATION_EXPLOSIVE_THRESHOLD",
    "DECELERATION_HARD_STOP_THRESHOLD",
    # 각속도 임계치
    "SHOOTING_ELBOW_ANGULAR_VELOCITY",
    "SHOOTING_WRIST_ANGULAR_VELOCITY",
    "SHOOTING_HIP_ROTATION_VELOCITY",
    "PASSING_ARM_ANGULAR_VELOCITY",
    # 균형/안정성
    "STABILITY_INDEX_MIN_STABLE",
    "COP_SWAY_STABLE_THRESHOLD_CM",
    "COP_SWAY_UNSTABLE_THRESHOLD_CM",
    "STABILIZATION_TIME_GOOD_S",
    "STABILIZATION_TIME_ACCEPTABLE_S",
    "STABILIZATION_TIME_POOR_S",
    "BASE_OF_SUPPORT_MIN_RATIO",
    "BASE_OF_SUPPORT_OPTIMAL_RATIO",
    "BASE_OF_SUPPORT_MAX_RATIO",
    "COM_HEIGHT_CHANGE_JUMP_THRESHOLD",
    "COM_HEIGHT_CHANGE_LANDING_THRESHOLD",
    # 동역학: 지면반력/충격
    "VERTICAL_GRF_WALKING_BW",
    "VERTICAL_GRF_RUNNING_BW",
    "VERTICAL_GRF_JUMP_LANDING_BW",
    "VERTICAL_GRF_MAX_SAFE_BW",
    "LANDING_IMPACT_ABSORPTION_GOOD_S",
    "LANDING_IMPACT_ABSORPTION_POOR_S",
    # 접촉 힘 임계치
    "CONTACT_FORCE_LIGHT_BW",
    "CONTACT_FORCE_MODERATE_BW",
    "CONTACT_FORCE_HEAVY_BW",
    "CONTACT_FORCE_EXCESSIVE_BW",
    # 에너지 소비
    "ENERGY_RATE_STATIONARY",
    "ENERGY_RATE_WALKING",
    "ENERGY_RATE_JOGGING",
    "ENERGY_RATE_RUNNING",
    "ENERGY_RATE_SPRINTING",
    "ENERGY_RATE_BASKETBALL_GAME",
    "HIGH_ENERGY_KINETIC_THRESHOLD_J",
    # 연령대별 보정 계수
    "AGE_TRUNK_MASS_FACTOR",
    "AGE_LIMB_LENGTH_FACTOR",
    "AGE_ANGLE_TOLERANCE",
]

# 모듈 버전 정보
__version__ = "1.0.0"
