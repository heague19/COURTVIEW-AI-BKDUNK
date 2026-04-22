# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: player_constants.py
설명: 선수 관련 상수 정의 (통합 canonical source)

    - 성별(Gender), 연령대(AgeGroup), 실력 수준(SkillLevel) 열거형
    - YOLO 감지 클래스 ID (선수, 심판, 코치, 스태프)
    - 팀 분류 색상 임계값 (밝기, 피부색, HSV)
    - 유니폼 영역 추출 비율
    - 이미지 정규화 (ImageNet 표준)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
    - configs/detection/player.yaml: 운영 설정 (YAML)
    - detection/player_detection/models.py: 데이터 모델
    - detection/player_detection/team_classifier.py: 팀 분류기

사용처:
    - shared/dto/analysis_dto.py: UserProfile DTO
    - pose_estimation/validation.py: 해부학적 검증
    - infrastructure/validation/schema_validator.py: 스키마 검증

주의:
    Gender, AgeGroup, SkillLevel은 이 파일이 유일한 정의 위치(canonical source)입니다.
    다른 모듈에서 자체 정의하지 말고 반드시 이 파일에서 import하세요.

사용 예시::

    >>> from shared.constants.player_constants import Gender, AgeGroup, SkillLevel
    >>> Gender.MALE.get_name()
    '남성'
    >>> AgeGroup.from_age(15)
    <AgeGroup.TEEN: 'teen'>
    >>> SkillLevel.BEGINNER.feedback_complexity
    'simple'
"""

from __future__ import annotations

# === 표준 라이브러리 ===
from enum import Enum, unique
from typing import Final

# === 프로젝트 모듈 ===
from shared.constants.localization import SupportedLanguage


# =============================================================================
# 성별 열거형 (canonical source)
# =============================================================================
@unique
class Gender(str, Enum):
    """
    성별 열거형.

    분석 시 성별에 따른 생체역학적 기준 적용에 사용됩니다.
    str을 상속하여 직렬화/역직렬화 호환성을 보장합니다.
    """

    MALE = "male"
    FEMALE = "female"

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 성별명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 성별명
        """
        return _GENDER_NAME_MAP[self].get(lang, _GENDER_NAME_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 성별명."""
        return self.get_name(SupportedLanguage.KO)


# -- Gender 캐시 --
_GENDER_NAME_MAP: dict[Gender, dict[SupportedLanguage, str]] = {
    Gender.MALE: {
        SupportedLanguage.KO: "남성",
        SupportedLanguage.EN: "Male",
        SupportedLanguage.JA: "男性",
        SupportedLanguage.ZH: "男性",
        SupportedLanguage.ES: "Masculino",
    },
    Gender.FEMALE: {
        SupportedLanguage.KO: "여성",
        SupportedLanguage.EN: "Female",
        SupportedLanguage.JA: "女性",
        SupportedLanguage.ZH: "女性",
        SupportedLanguage.ES: "Femenino",
    },
}


# =============================================================================
# 연령대 열거형 (canonical source)
# =============================================================================
@unique
class AgeGroup(str, Enum):
    """
    연령대 열거형.

    농구 분석 시 연령대별 기준점 및 권장 장비 크기 결정에 사용됩니다.
    FIBA/KBL 규정에 따른 연령대 구분을 따릅니다.
    """

    YOUTH = "youth"       # 유소년 (6-12세)
    TEEN = "teen"         # 청소년 (13-18세)
    ADULT = "adult"       # 성인 (19-49세)
    SENIOR = "senior"     # 시니어 (50세 이상)

    def __str__(self) -> str:
        return self.value

    @property
    def age_range(self) -> tuple[int, int]:
        """
        연령 범위를 반환합니다.

        Returns:
            (최소 나이, 최대 나이) 튜플
        """
        return _AGE_GROUP_RANGE_MAP[self]

    @classmethod
    def from_age(cls, age: int) -> AgeGroup:
        """
        나이로부터 연령대 결정.

        Args:
            age: 나이

        Returns:
            AgeGroup: 해당하는 연령대
        """
        if not isinstance(age, int) or age < 0:
            return cls.YOUTH
        if age < 13:
            return cls.YOUTH
        elif age < 19:
            return cls.TEEN
        elif age < 50:
            return cls.ADULT
        else:
            return cls.SENIOR

    @property
    def recommended_ball_size(self) -> int:
        """
        권장 농구공 크기를 반환합니다.

        FIBA 규정 기준:
        - 크기 5: 유소년 (둘레 69-71cm, 무게 470-500g)
        - 크기 6: 여성/청소년 (둘레 72-74cm, 무게 510-550g)
        - 크기 7: 성인 남성 (둘레 75-78cm, 무게 567-650g)

        Returns:
            권장 공 크기 (5, 6, 7)
        """
        return _AGE_GROUP_BALL_SIZE_MAP[self]

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 연령대명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 연령대명
        """
        return _AGE_GROUP_NAME_MAP[self].get(lang, _AGE_GROUP_NAME_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 연령대명."""
        return self.get_name(SupportedLanguage.KO)


# -- AgeGroup 캐시 --
_AGE_GROUP_RANGE_MAP: dict[AgeGroup, tuple[int, int]] = {
    AgeGroup.YOUTH: (6, 12),
    AgeGroup.TEEN: (13, 18),
    AgeGroup.ADULT: (19, 49),
    AgeGroup.SENIOR: (50, 99),
}

_AGE_GROUP_BALL_SIZE_MAP: dict[AgeGroup, int] = {
    AgeGroup.YOUTH: 5,
    AgeGroup.TEEN: 6,
    AgeGroup.ADULT: 7,
    AgeGroup.SENIOR: 7,
}

_AGE_GROUP_NAME_MAP: dict[AgeGroup, dict[SupportedLanguage, str]] = {
    AgeGroup.YOUTH: {
        SupportedLanguage.KO: "유소년",
        SupportedLanguage.EN: "Youth",
        SupportedLanguage.JA: "ユース",
        SupportedLanguage.ZH: "青少年",
        SupportedLanguage.ES: "Juvenil",
    },
    AgeGroup.TEEN: {
        SupportedLanguage.KO: "청소년",
        SupportedLanguage.EN: "Teen",
        SupportedLanguage.JA: "ティーン",
        SupportedLanguage.ZH: "青年",
        SupportedLanguage.ES: "Adolescente",
    },
    AgeGroup.ADULT: {
        SupportedLanguage.KO: "성인",
        SupportedLanguage.EN: "Adult",
        SupportedLanguage.JA: "成人",
        SupportedLanguage.ZH: "成人",
        SupportedLanguage.ES: "Adulto",
    },
    AgeGroup.SENIOR: {
        SupportedLanguage.KO: "시니어",
        SupportedLanguage.EN: "Senior",
        SupportedLanguage.JA: "シニア",
        SupportedLanguage.ZH: "老年",
        SupportedLanguage.ES: "Senior",
    },
}


# =============================================================================
# 실력 수준 열거형 (canonical source)
# =============================================================================
@unique
class SkillLevel(str, Enum):
    """
    실력 수준 열거형.

    농구 분석 시 실력 수준에 따른 기준점 및 피드백 난이도 결정에 사용됩니다.
    """

    BEGINNER = "beginner"           # 초보
    INTERMEDIATE = "intermediate"   # 중급
    ADVANCED = "advanced"           # 상급
    PROFESSIONAL = "professional"   # 프로

    def __str__(self) -> str:
        return self.value

    @property
    def numeric_level(self) -> int:
        """
        숫자 등급을 반환합니다 (1-4).

        분석 시 가중치 적용 및 기준점 조정에 사용됩니다.

        Returns:
            1 (초보) ~ 4 (프로)
        """
        return _SKILL_LEVEL_NUMERIC_MAP[self]

    @property
    def feedback_complexity(self) -> str:
        """
        피드백 복잡도를 반환합니다.

        실력 수준에 따라 피드백의 전문성 수준을 결정합니다.

        Returns:
            simple, detailed, technical, expert 중 하나
        """
        return _SKILL_LEVEL_FEEDBACK_MAP[self]

    @property
    def tolerance_factor(self) -> float:
        """
        허용 오차 계수를 반환합니다.

        초보자는 더 넓은 허용 범위, 프로는 엄격한 기준을 적용합니다.
        동작 정확도 분석 시 기준값에 곱하여 사용합니다.

        Returns:
            1.3 (초보) ~ 0.8 (프로)
        """
        return _SKILL_LEVEL_TOLERANCE_MAP[self]

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 실력 수준명 반환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            해당 언어의 실력 수준명
        """
        return _SKILL_LEVEL_NAME_MAP[self].get(lang, _SKILL_LEVEL_NAME_MAP[self][SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 실력 수준명."""
        return self.get_name(SupportedLanguage.KO)


# -- SkillLevel 캐시 --
_SKILL_LEVEL_NUMERIC_MAP: dict[SkillLevel, int] = {
    SkillLevel.BEGINNER: 1,
    SkillLevel.INTERMEDIATE: 2,
    SkillLevel.ADVANCED: 3,
    SkillLevel.PROFESSIONAL: 4,
}

_SKILL_LEVEL_FEEDBACK_MAP: dict[SkillLevel, str] = {
    SkillLevel.BEGINNER: "simple",
    SkillLevel.INTERMEDIATE: "detailed",
    SkillLevel.ADVANCED: "technical",
    SkillLevel.PROFESSIONAL: "expert",
}

_SKILL_LEVEL_TOLERANCE_MAP: dict[SkillLevel, float] = {
    SkillLevel.BEGINNER: 1.3,
    SkillLevel.INTERMEDIATE: 1.1,
    SkillLevel.ADVANCED: 0.95,
    SkillLevel.PROFESSIONAL: 0.8,
}

_SKILL_LEVEL_NAME_MAP: dict[SkillLevel, dict[SupportedLanguage, str]] = {
    SkillLevel.BEGINNER: {
        SupportedLanguage.KO: "초보",
        SupportedLanguage.EN: "Beginner",
        SupportedLanguage.JA: "初心者",
        SupportedLanguage.ZH: "初学者",
        SupportedLanguage.ES: "Principiante",
    },
    SkillLevel.INTERMEDIATE: {
        SupportedLanguage.KO: "중급",
        SupportedLanguage.EN: "Intermediate",
        SupportedLanguage.JA: "中級者",
        SupportedLanguage.ZH: "中级",
        SupportedLanguage.ES: "Intermedio",
    },
    SkillLevel.ADVANCED: {
        SupportedLanguage.KO: "상급",
        SupportedLanguage.EN: "Advanced",
        SupportedLanguage.JA: "上級者",
        SupportedLanguage.ZH: "高级",
        SupportedLanguage.ES: "Avanzado",
    },
    SkillLevel.PROFESSIONAL: {
        SupportedLanguage.KO: "프로",
        SupportedLanguage.EN: "Professional",
        SupportedLanguage.JA: "プロ",
        SupportedLanguage.ZH: "专业",
        SupportedLanguage.ES: "Profesional",
    },
}

# =============================================================================
# YOLO 감지 클래스 ID (COURTVIEW 자체 학습 모델 기준)
# =============================================================================
PLAYER_CLASS_ID_PLAYER: Final[int] = 0    # 선수
PLAYER_CLASS_ID_REFEREE: Final[int] = 1   # 심판
PLAYER_CLASS_ID_COACH: Final[int] = 2     # 코치
PLAYER_CLASS_ID_STAFF: Final[int] = 3     # 스태프
PLAYER_CLASS_ID_UNKNOWN: Final[int] = 4   # 미식별

# COURTVIEW 자체 모델 클래스 수
PLAYER_MODEL_NUM_CLASSES: Final[int] = 5

# 클래스 ID → 이름 매핑
PLAYER_CLASS_NAMES: Final[dict[int, str]] = {
    PLAYER_CLASS_ID_PLAYER: "player",
    PLAYER_CLASS_ID_REFEREE: "referee",
    PLAYER_CLASS_ID_COACH: "coach",
    PLAYER_CLASS_ID_STAFF: "staff",
    PLAYER_CLASS_ID_UNKNOWN: "unknown",
}

# =============================================================================
# 팀 분류 - 밝기 임계값 (Value 채널 기반)
# =============================================================================
TEAM_VALUE_DARK_THRESHOLD: Final[float] = 125.0   # 어두운 유니폼 (홈팀)
TEAM_VALUE_LIGHT_THRESHOLD: Final[float] = 140.0   # 밝은 유니폼 (원정팀)

# =============================================================================
# 팀 분류 - 피부색 제외 HSV 범위
# =============================================================================
TEAM_SKIN_HUE_RANGE: Final[tuple[int, int]] = (0, 25)     # 피부색 Hue 범위
TEAM_SKIN_SAT_RANGE: Final[tuple[int, int]] = (40, 170)   # 피부색 Saturation 범위

# =============================================================================
# 팀 분류 - 딥러닝 모델 기본 설정
# =============================================================================
TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD: Final[float] = 0.7  # 팀 분류 신뢰도 임계값

# =============================================================================
# 이미지 정규화 (ImageNet 표준)
# =============================================================================
NORMALIZE_MEAN: Final[tuple[float, ...]] = (0.485, 0.456, 0.406)
NORMALIZE_STD: Final[tuple[float, ...]] = (0.229, 0.224, 0.225)

# =============================================================================
# 유니폼 영역 (가슴) 크롭 비율
# =============================================================================
CHEST_CROP_Y_START: Final[float] = 0.15   # 상단 15%부터
CHEST_CROP_Y_END: Final[float] = 0.55     # 하단 55%까지
CHEST_CROP_X_START: Final[float] = 0.30   # 좌측 30%부터
CHEST_CROP_X_END: Final[float] = 0.70     # 우측 70%까지

# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 사용자 속성 열거형 (canonical source)
    "Gender",
    "AgeGroup",
    "SkillLevel",
    # YOLO 클래스 ID (COURTVIEW 자체 모델)
    "PLAYER_CLASS_ID_PLAYER",
    "PLAYER_CLASS_ID_REFEREE",
    "PLAYER_CLASS_ID_COACH",
    "PLAYER_CLASS_ID_STAFF",
    "PLAYER_CLASS_ID_UNKNOWN",
    "PLAYER_MODEL_NUM_CLASSES",
    "PLAYER_CLASS_NAMES",
    # 팀 분류 밝기 임계값
    "TEAM_VALUE_DARK_THRESHOLD",
    "TEAM_VALUE_LIGHT_THRESHOLD",
    # 피부색 제외 HSV 범위
    "TEAM_SKIN_HUE_RANGE",
    "TEAM_SKIN_SAT_RANGE",
    # 팀 분류 딥러닝
    "TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD",
    # 이미지 정규화
    "NORMALIZE_MEAN",
    "NORMALIZE_STD",
    # 유니폼 영역 크롭
    "CHEST_CROP_Y_START",
    "CHEST_CROP_Y_END",
    "CHEST_CROP_X_START",
    "CHEST_CROP_X_END",
]

__version__ = "1.0.0"
