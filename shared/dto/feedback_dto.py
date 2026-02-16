# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: feedback_dto.py
설명: 피드백 및 훈련 추천 관련 DTO 정의
      - 다국어 지원 (i18n)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

from datetime import datetime, timezone
from enum import Enum, unique
from typing import ClassVar, Final
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator

from shared.constants.localization import SupportedLanguage


# =============================================================================
# i18n 모듈 레벨 캐시 (Enum.get_name 메서드 최적화)
# =============================================================================
_FEEDBACK_CATEGORY_I18N: Final[dict[str, dict[SupportedLanguage, str]]] = {
    "posture": {
        SupportedLanguage.KO: "자세", SupportedLanguage.EN: "Posture",
        SupportedLanguage.JA: "姿勢", SupportedLanguage.ZH: "姿势", SupportedLanguage.ES: "Postura",
    },
    "timing": {
        SupportedLanguage.KO: "타이밍", SupportedLanguage.EN: "Timing",
        SupportedLanguage.JA: "タイミング", SupportedLanguage.ZH: "时机", SupportedLanguage.ES: "Tiempo",
    },
    "angle": {
        SupportedLanguage.KO: "각도", SupportedLanguage.EN: "Angle",
        SupportedLanguage.JA: "角度", SupportedLanguage.ZH: "角度", SupportedLanguage.ES: "Ángulo",
    },
    "power": {
        SupportedLanguage.KO: "파워", SupportedLanguage.EN: "Power",
        SupportedLanguage.JA: "パワー", SupportedLanguage.ZH: "力量", SupportedLanguage.ES: "Potencia",
    },
    "balance": {
        SupportedLanguage.KO: "균형", SupportedLanguage.EN: "Balance",
        SupportedLanguage.JA: "バランス", SupportedLanguage.ZH: "平衡", SupportedLanguage.ES: "Equilibrio",
    },
    "coordination": {
        SupportedLanguage.KO: "협응력", SupportedLanguage.EN: "Coordination",
        SupportedLanguage.JA: "協調性", SupportedLanguage.ZH: "协调性", SupportedLanguage.ES: "Coordinación",
    },
    "follow_through": {
        SupportedLanguage.KO: "팔로우 스루", SupportedLanguage.EN: "Follow Through",
        SupportedLanguage.JA: "フォロースルー", SupportedLanguage.ZH: "随球动作", SupportedLanguage.ES: "Seguimiento",
    },
    "footwork": {
        SupportedLanguage.KO: "풋워크", SupportedLanguage.EN: "Footwork",
        SupportedLanguage.JA: "フットワーク", SupportedLanguage.ZH: "步法", SupportedLanguage.ES: "Juego de pies",
    },
    "body_alignment": {
        SupportedLanguage.KO: "신체 정렬", SupportedLanguage.EN: "Body Alignment",
        SupportedLanguage.JA: "ボディアライメント", SupportedLanguage.ZH: "身体对齐", SupportedLanguage.ES: "Alineación corporal",
    },
    "ball_control": {
        SupportedLanguage.KO: "볼 컨트롤", SupportedLanguage.EN: "Ball Control",
        SupportedLanguage.JA: "ボールコントロール", SupportedLanguage.ZH: "控球", SupportedLanguage.ES: "Control del balón",
    },
    "release": {
        SupportedLanguage.KO: "릴리스", SupportedLanguage.EN: "Release",
        SupportedLanguage.JA: "リリース", SupportedLanguage.ZH: "出手", SupportedLanguage.ES: "Lanzamiento",
    },
    "rhythm": {
        SupportedLanguage.KO: "리듬", SupportedLanguage.EN: "Rhythm",
        SupportedLanguage.JA: "リズム", SupportedLanguage.ZH: "节奏", SupportedLanguage.ES: "Ritmo",
    },
    "tip": {
        SupportedLanguage.KO: "팁", SupportedLanguage.EN: "Tip",
        SupportedLanguage.JA: "ヒント", SupportedLanguage.ZH: "提示", SupportedLanguage.ES: "Consejo",
    },
}

_FEEDBACK_PRIORITY_I18N: Final[dict[str, dict[SupportedLanguage, str]]] = {
    "critical": {
        SupportedLanguage.KO: "필수", SupportedLanguage.EN: "Critical",
        SupportedLanguage.JA: "必須", SupportedLanguage.ZH: "关键", SupportedLanguage.ES: "Crítico",
    },
    "high": {
        SupportedLanguage.KO: "높음", SupportedLanguage.EN: "High",
        SupportedLanguage.JA: "高", SupportedLanguage.ZH: "高", SupportedLanguage.ES: "Alto",
    },
    "medium": {
        SupportedLanguage.KO: "보통", SupportedLanguage.EN: "Medium",
        SupportedLanguage.JA: "中", SupportedLanguage.ZH: "中", SupportedLanguage.ES: "Medio",
    },
    "low": {
        SupportedLanguage.KO: "낮음", SupportedLanguage.EN: "Low",
        SupportedLanguage.JA: "低", SupportedLanguage.ZH: "低", SupportedLanguage.ES: "Bajo",
    },
    "optional": {
        SupportedLanguage.KO: "선택", SupportedLanguage.EN: "Optional",
        SupportedLanguage.JA: "任意", SupportedLanguage.ZH: "可选", SupportedLanguage.ES: "Opcional",
    },
}

_FEEDBACK_TYPE_I18N: Final[dict[str, dict[SupportedLanguage, str]]] = {
    "correction": {
        SupportedLanguage.KO: "교정", SupportedLanguage.EN: "Correction",
        SupportedLanguage.JA: "修正", SupportedLanguage.ZH: "纠正", SupportedLanguage.ES: "Corrección",
    },
    "improvement": {
        SupportedLanguage.KO: "개선", SupportedLanguage.EN: "Improvement",
        SupportedLanguage.JA: "改善", SupportedLanguage.ZH: "改进", SupportedLanguage.ES: "Mejora",
    },
    "positive": {
        SupportedLanguage.KO: "긍정", SupportedLanguage.EN: "Positive",
        SupportedLanguage.JA: "良好", SupportedLanguage.ZH: "积极", SupportedLanguage.ES: "Positivo",
    },
    "warning": {
        SupportedLanguage.KO: "경고", SupportedLanguage.EN: "Warning",
        SupportedLanguage.JA: "警告", SupportedLanguage.ZH: "警告", SupportedLanguage.ES: "Advertencia",
    },
    "tip": {
        SupportedLanguage.KO: "팁", SupportedLanguage.EN: "Tip",
        SupportedLanguage.JA: "ヒント", SupportedLanguage.ZH: "提示", SupportedLanguage.ES: "Consejo",
    },
}

_BODY_PART_I18N: Final[dict[str, dict[SupportedLanguage, str]]] = {
    "head": {
        SupportedLanguage.KO: "머리", SupportedLanguage.EN: "Head",
        SupportedLanguage.JA: "頭", SupportedLanguage.ZH: "头", SupportedLanguage.ES: "Cabeza",
    },
    "neck": {
        SupportedLanguage.KO: "목", SupportedLanguage.EN: "Neck",
        SupportedLanguage.JA: "首", SupportedLanguage.ZH: "颈", SupportedLanguage.ES: "Cuello",
    },
    "left_shoulder": {
        SupportedLanguage.KO: "왼쪽 어깨", SupportedLanguage.EN: "Left Shoulder",
        SupportedLanguage.JA: "左肩", SupportedLanguage.ZH: "左肩", SupportedLanguage.ES: "Hombro izquierdo",
    },
    "right_shoulder": {
        SupportedLanguage.KO: "오른쪽 어깨", SupportedLanguage.EN: "Right Shoulder",
        SupportedLanguage.JA: "右肩", SupportedLanguage.ZH: "右肩", SupportedLanguage.ES: "Hombro derecho",
    },
    "left_elbow": {
        SupportedLanguage.KO: "왼쪽 팔꿈치", SupportedLanguage.EN: "Left Elbow",
        SupportedLanguage.JA: "左肘", SupportedLanguage.ZH: "左肘", SupportedLanguage.ES: "Codo izquierdo",
    },
    "right_elbow": {
        SupportedLanguage.KO: "오른쪽 팔꿈치", SupportedLanguage.EN: "Right Elbow",
        SupportedLanguage.JA: "右肘", SupportedLanguage.ZH: "右肘", SupportedLanguage.ES: "Codo derecho",
    },
    "left_wrist": {
        SupportedLanguage.KO: "왼쪽 손목", SupportedLanguage.EN: "Left Wrist",
        SupportedLanguage.JA: "左手首", SupportedLanguage.ZH: "左腕", SupportedLanguage.ES: "Muñeca izquierda",
    },
    "right_wrist": {
        SupportedLanguage.KO: "오른쪽 손목", SupportedLanguage.EN: "Right Wrist",
        SupportedLanguage.JA: "右手首", SupportedLanguage.ZH: "右腕", SupportedLanguage.ES: "Muñeca derecha",
    },
    "left_hand": {
        SupportedLanguage.KO: "왼손", SupportedLanguage.EN: "Left Hand",
        SupportedLanguage.JA: "左手", SupportedLanguage.ZH: "左手", SupportedLanguage.ES: "Mano izquierda",
    },
    "right_hand": {
        SupportedLanguage.KO: "오른손", SupportedLanguage.EN: "Right Hand",
        SupportedLanguage.JA: "右手", SupportedLanguage.ZH: "右手", SupportedLanguage.ES: "Mano derecha",
    },
    "chest": {
        SupportedLanguage.KO: "가슴", SupportedLanguage.EN: "Chest",
        SupportedLanguage.JA: "胸", SupportedLanguage.ZH: "胸", SupportedLanguage.ES: "Pecho",
    },
    "spine": {
        SupportedLanguage.KO: "척추", SupportedLanguage.EN: "Spine",
        SupportedLanguage.JA: "背骨", SupportedLanguage.ZH: "脊椎", SupportedLanguage.ES: "Columna",
    },
    "waist": {
        SupportedLanguage.KO: "허리", SupportedLanguage.EN: "Waist",
        SupportedLanguage.JA: "腰", SupportedLanguage.ZH: "腰", SupportedLanguage.ES: "Cintura",
    },
    "hip": {
        SupportedLanguage.KO: "엉덩이", SupportedLanguage.EN: "Hip",
        SupportedLanguage.JA: "腰", SupportedLanguage.ZH: "臀部", SupportedLanguage.ES: "Cadera",
    },
    "left_hip": {
        SupportedLanguage.KO: "왼쪽 골반", SupportedLanguage.EN: "Left Hip",
        SupportedLanguage.JA: "左腰", SupportedLanguage.ZH: "左髋", SupportedLanguage.ES: "Cadera izquierda",
    },
    "right_hip": {
        SupportedLanguage.KO: "오른쪽 골반", SupportedLanguage.EN: "Right Hip",
        SupportedLanguage.JA: "右腰", SupportedLanguage.ZH: "右髋", SupportedLanguage.ES: "Cadera derecha",
    },
    "left_knee": {
        SupportedLanguage.KO: "왼쪽 무릎", SupportedLanguage.EN: "Left Knee",
        SupportedLanguage.JA: "左膝", SupportedLanguage.ZH: "左膝", SupportedLanguage.ES: "Rodilla izquierda",
    },
    "right_knee": {
        SupportedLanguage.KO: "오른쪽 무릎", SupportedLanguage.EN: "Right Knee",
        SupportedLanguage.JA: "右膝", SupportedLanguage.ZH: "右膝", SupportedLanguage.ES: "Rodilla derecha",
    },
    "left_ankle": {
        SupportedLanguage.KO: "왼쪽 발목", SupportedLanguage.EN: "Left Ankle",
        SupportedLanguage.JA: "左足首", SupportedLanguage.ZH: "左踝", SupportedLanguage.ES: "Tobillo izquierdo",
    },
    "right_ankle": {
        SupportedLanguage.KO: "오른쪽 발목", SupportedLanguage.EN: "Right Ankle",
        SupportedLanguage.JA: "右足首", SupportedLanguage.ZH: "右踝", SupportedLanguage.ES: "Tobillo derecho",
    },
    "left_foot": {
        SupportedLanguage.KO: "왼발", SupportedLanguage.EN: "Left Foot",
        SupportedLanguage.JA: "左足", SupportedLanguage.ZH: "左脚", SupportedLanguage.ES: "Pie izquierdo",
    },
    "right_foot": {
        SupportedLanguage.KO: "오른발", SupportedLanguage.EN: "Right Foot",
        SupportedLanguage.JA: "右足", SupportedLanguage.ZH: "右脚", SupportedLanguage.ES: "Pie derecho",
    },
}

_MOTION_PHASE_I18N: Final[dict[str, dict[SupportedLanguage, str]]] = {
    "shooting_preparation": {
        SupportedLanguage.KO: "슈팅 준비", SupportedLanguage.EN: "Shooting Preparation",
        SupportedLanguage.JA: "シュート準備", SupportedLanguage.ZH: "投篮准备", SupportedLanguage.ES: "Preparación de tiro",
    },
    "shooting_lift": {
        SupportedLanguage.KO: "공 들어올리기", SupportedLanguage.EN: "Ball Lift",
        SupportedLanguage.JA: "リフト", SupportedLanguage.ZH: "举球", SupportedLanguage.ES: "Elevación",
    },
    "shooting_aim": {
        SupportedLanguage.KO: "조준", SupportedLanguage.EN: "Aiming",
        SupportedLanguage.JA: "エイミング", SupportedLanguage.ZH: "瞄准", SupportedLanguage.ES: "Apuntando",
    },
    "shooting_release": {
        SupportedLanguage.KO: "릴리스", SupportedLanguage.EN: "Release",
        SupportedLanguage.JA: "リリース", SupportedLanguage.ZH: "出手", SupportedLanguage.ES: "Lanzamiento",
    },
    "shooting_follow_through": {
        SupportedLanguage.KO: "팔로우 스루", SupportedLanguage.EN: "Follow Through",
        SupportedLanguage.JA: "フォロースルー", SupportedLanguage.ZH: "随球动作", SupportedLanguage.ES: "Seguimiento",
    },
    "dribble_stance": {
        SupportedLanguage.KO: "드리블 자세", SupportedLanguage.EN: "Dribble Stance",
        SupportedLanguage.JA: "ドリブル姿勢", SupportedLanguage.ZH: "运球姿势", SupportedLanguage.ES: "Postura de dribleo",
    },
    "dribble_push": {
        SupportedLanguage.KO: "공 밀기", SupportedLanguage.EN: "Ball Push",
        SupportedLanguage.JA: "ボールプッシュ", SupportedLanguage.ZH: "推球", SupportedLanguage.ES: "Empuje del balón",
    },
    "dribble_bounce": {
        SupportedLanguage.KO: "바운스", SupportedLanguage.EN: "Bounce",
        SupportedLanguage.JA: "バウンス", SupportedLanguage.ZH: "弹跳", SupportedLanguage.ES: "Rebote",
    },
    "dribble_control": {
        SupportedLanguage.KO: "드리블 컨트롤", SupportedLanguage.EN: "Dribble Control",
        SupportedLanguage.JA: "ドリブルコントロール", SupportedLanguage.ZH: "运球控制", SupportedLanguage.ES: "Control de dribleo",
    },
    "pass_preparation": {
        SupportedLanguage.KO: "패스 준비", SupportedLanguage.EN: "Pass Preparation",
        SupportedLanguage.JA: "パス準備", SupportedLanguage.ZH: "传球准备", SupportedLanguage.ES: "Preparación de pase",
    },
    "pass_execution": {
        SupportedLanguage.KO: "패스 실행", SupportedLanguage.EN: "Pass Execution",
        SupportedLanguage.JA: "パス実行", SupportedLanguage.ZH: "传球执行", SupportedLanguage.ES: "Ejecución de pase",
    },
    "pass_follow_through": {
        SupportedLanguage.KO: "패스 마무리", SupportedLanguage.EN: "Pass Follow Through",
        SupportedLanguage.JA: "パスフォロースルー", SupportedLanguage.ZH: "传球跟随", SupportedLanguage.ES: "Seguimiento de pase",
    },
    "defense_stance": {
        SupportedLanguage.KO: "수비 자세", SupportedLanguage.EN: "Defense Stance",
        SupportedLanguage.JA: "ディフェンス姿勢", SupportedLanguage.ZH: "防守姿势", SupportedLanguage.ES: "Postura defensiva",
    },
    "defense_slide": {
        SupportedLanguage.KO: "수비 슬라이드", SupportedLanguage.EN: "Defense Slide",
        SupportedLanguage.JA: "ディフェンススライド", SupportedLanguage.ZH: "防守滑步", SupportedLanguage.ES: "Deslizamiento defensivo",
    },
    "defense_contest": {
        SupportedLanguage.KO: "슛 방해", SupportedLanguage.EN: "Shot Contest",
        SupportedLanguage.JA: "シュートチェック", SupportedLanguage.ZH: "封盖", SupportedLanguage.ES: "Contestación",
    },
}

_FEEDBACK_SOURCE_I18N: Final[dict[str, dict[SupportedLanguage, str]]] = {
    "user": {
        SupportedLanguage.KO: "사용자", SupportedLanguage.EN: "User",
        SupportedLanguage.JA: "ユーザー", SupportedLanguage.ZH: "用户", SupportedLanguage.ES: "Usuario",
    },
    "system": {
        SupportedLanguage.KO: "시스템", SupportedLanguage.EN: "System",
        SupportedLanguage.JA: "システム", SupportedLanguage.ZH: "系统", SupportedLanguage.ES: "Sistema",
    },
    "auto": {
        SupportedLanguage.KO: "자동 학습", SupportedLanguage.EN: "Auto Learning",
        SupportedLanguage.JA: "自動学習", SupportedLanguage.ZH: "自动学习", SupportedLanguage.ES: "Aprendizaje automático",
    },
    "expert": {
        SupportedLanguage.KO: "전문가", SupportedLanguage.EN: "Expert",
        SupportedLanguage.JA: "専門家", SupportedLanguage.ZH: "专家", SupportedLanguage.ES: "Experto",
    },
    "coach": {
        SupportedLanguage.KO: "코치", SupportedLanguage.EN: "Coach",
        SupportedLanguage.JA: "コーチ", SupportedLanguage.ZH: "教练", SupportedLanguage.ES: "Entrenador",
    },
}


# =============================================================================
# 피드백 분류 열거형
# =============================================================================
@unique
class FeedbackCategory(str, Enum):
    """
    피드백 카테고리.

    다국어 지원을 위해 get_name(lang) 메서드를 제공합니다.
    """

    POSTURE = "posture"  # 자세
    TIMING = "timing"  # 타이밍
    ANGLE = "angle"  # 각도
    POWER = "power"  # 힘/파워
    BALANCE = "balance"  # 균형
    COORDINATION = "coordination"  # 협응력
    FOLLOW_THROUGH = "follow_through"  # 팔로우 스루
    FOOTWORK = "footwork"  # 풋워크
    BODY_ALIGNMENT = "body_alignment"  # 신체 정렬
    BALL_CONTROL = "ball_control"  # 볼 컨트롤
    RELEASE = "release"  # 릴리스
    RHYTHM = "rhythm"  # 리듬
    TIP = "tip"  # 팁/조언

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 카테고리명 반환 (모듈 레벨 캐시 참조)."""
        entry = _FEEDBACK_CATEGORY_I18N[self.value]
        return entry.get(lang, entry[SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 카테고리명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


@unique
class FeedbackPriority(str, Enum):
    """
    피드백 우선순위.

    다국어 지원을 위해 get_name(lang) 메서드를 제공합니다.
    """

    CRITICAL = "critical"  # 필수 개선 (심각한 문제)
    HIGH = "high"  # 높은 우선순위
    MEDIUM = "medium"  # 중간 우선순위
    LOW = "low"  # 낮은 우선순위
    OPTIONAL = "optional"  # 선택적 개선

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 우선순위명 반환 (모듈 레벨 캐시 참조)."""
        entry = _FEEDBACK_PRIORITY_I18N[self.value]
        return entry.get(lang, entry[SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 우선순위명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


@unique
class FeedbackType(str, Enum):
    """
    피드백 타입.

    다국어 지원을 위해 get_name(lang) 메서드를 제공합니다.
    """

    CORRECTION = "correction"  # 교정 필요
    IMPROVEMENT = "improvement"  # 개선 제안
    POSITIVE = "positive"  # 긍정적 피드백
    WARNING = "warning"  # 경고 (부상 위험 등)
    TIP = "tip"  # 팁/조언

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 타입명 반환 (모듈 레벨 캐시 참조)."""
        entry = _FEEDBACK_TYPE_I18N[self.value]
        return entry.get(lang, entry[SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 타입명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


@unique
class BodyPart(str, Enum):
    """
    신체 부위.

    다국어 지원을 위해 get_name(lang) 메서드를 제공합니다.
    """

    # 상체
    HEAD = "head"
    NECK = "neck"
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"
    LEFT_ELBOW = "left_elbow"
    RIGHT_ELBOW = "right_elbow"
    LEFT_WRIST = "left_wrist"
    RIGHT_WRIST = "right_wrist"
    LEFT_HAND = "left_hand"
    RIGHT_HAND = "right_hand"
    # 몸통
    CHEST = "chest"
    SPINE = "spine"
    WAIST = "waist"
    HIP = "hip"
    # 하체
    LEFT_HIP = "left_hip"
    RIGHT_HIP = "right_hip"
    LEFT_KNEE = "left_knee"
    RIGHT_KNEE = "right_knee"
    LEFT_ANKLE = "left_ankle"
    RIGHT_ANKLE = "right_ankle"
    LEFT_FOOT = "left_foot"
    RIGHT_FOOT = "right_foot"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 신체 부위명 반환 (모듈 레벨 캐시 참조)."""
        entry = _BODY_PART_I18N[self.value]
        return entry.get(lang, entry[SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 신체 부위명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


@unique
class MotionPhase(str, Enum):
    """
    동작 단계.

    다국어 지원을 위해 get_name(lang) 메서드를 제공합니다.
    """

    # 슈팅 단계
    SHOOTING_PREPARATION = "shooting_preparation"  # 준비 자세
    SHOOTING_LIFT = "shooting_lift"  # 들어올리기
    SHOOTING_AIM = "shooting_aim"  # 조준
    SHOOTING_RELEASE = "shooting_release"  # 릴리스
    SHOOTING_FOLLOW_THROUGH = "shooting_follow_through"  # 팔로우 스루
    # 드리블 단계
    DRIBBLE_STANCE = "dribble_stance"  # 드리블 자세
    DRIBBLE_PUSH = "dribble_push"  # 공 밀기
    DRIBBLE_BOUNCE = "dribble_bounce"  # 바운스
    DRIBBLE_CONTROL = "dribble_control"  # 컨트롤
    # 패스 단계
    PASS_PREPARATION = "pass_preparation"  # 패스 준비
    PASS_EXECUTION = "pass_execution"  # 패스 실행
    PASS_FOLLOW_THROUGH = "pass_follow_through"  # 패스 마무리
    # 수비 단계
    DEFENSE_STANCE = "defense_stance"  # 수비 자세
    DEFENSE_SLIDE = "defense_slide"  # 수비 슬라이드
    DEFENSE_CONTEST = "defense_contest"  # 슛 방해

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 동작 단계명 반환 (모듈 레벨 캐시 참조)."""
        entry = _MOTION_PHASE_I18N[self.value]
        return entry.get(lang, entry[SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 동작 단계명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# =============================================================================
# 세부 피드백 DTO
# =============================================================================
class FeedbackItem(BaseModel):
    """
    개별 피드백 항목.

    동작의 특정 부분에 대한 세부 피드백입니다.
    """

    feedback_id: UUID = Field(default_factory=uuid4, description="피드백 ID")
    category: FeedbackCategory = Field(..., description="피드백 카테고리")
    feedback_type: FeedbackType = Field(..., description="피드백 타입")
    priority: FeedbackPriority = Field(..., description="우선순위")

    # 관련 신체 부위 및 동작 단계
    body_parts: list[BodyPart] = Field(default_factory=list, description="관련 신체 부위")
    motion_phase: MotionPhase | None = Field(default=None, description="관련 동작 단계")

    # 피드백 내용
    title: str = Field(..., min_length=1, max_length=100, description="피드백 제목")
    description: str = Field(..., min_length=1, max_length=1000, description="피드백 상세 설명")
    suggestion: str | None = Field(default=None, max_length=500, description="개선 제안")

    # 측정값 정보
    current_value: float | None = Field(default=None, description="현재 측정값")
    ideal_value: float | None = Field(default=None, description="이상적 값")
    tolerance_range: tuple[float, float] | None = Field(default=None, description="허용 범위 (min, max)")
    unit: str | None = Field(default=None, description="측정 단위 (degrees, cm, seconds 등)")

    # 신뢰도 및 프레임 정보
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="피드백 신뢰도")
    start_frame: int | None = Field(default=None, ge=0, description="시작 프레임")
    end_frame: int | None = Field(default=None, ge=0, description="종료 프레임")
    timestamp_start: float | None = Field(default=None, ge=0, description="시작 시간 (초)")
    timestamp_end: float | None = Field(default=None, ge=0, description="종료 시간 (초)")

    # 시각화 참조
    visualization_url: HttpUrl | None = Field(default=None, description="피드백 시각화 이미지 URL")

    @field_validator("tolerance_range")
    @classmethod
    def validate_tolerance_range(cls, v: tuple[float, float] | None) -> tuple[float, float] | None:
        """허용 범위 검증."""
        if v is not None:
            if v[0] >= v[1]:
                raise ValueError("허용 범위의 최소값은 최대값보다 작아야 합니다")
        return v


class MotionScore(BaseModel):
    """
    동작 점수 DTO.

    개별 동작의 세부 점수 및 평가입니다.
    """

    score_id: UUID = Field(default_factory=uuid4, description="점수 ID")
    motion_type: str = Field(..., description="동작 유형 (shooting, dribbling 등)")
    motion_index: int = Field(..., ge=0, description="동작 인덱스 (n번째 동작)")

    # 종합 점수
    overall_score: float = Field(..., ge=0.0, le=100.0, description="종합 점수")

    # 세부 점수
    posture_score: float = Field(default=0.0, ge=0.0, le=100.0, description="자세 점수")
    timing_score: float = Field(default=0.0, ge=0.0, le=100.0, description="타이밍 점수")
    accuracy_score: float = Field(default=0.0, ge=0.0, le=100.0, description="정확도 점수")
    power_score: float = Field(default=0.0, ge=0.0, le=100.0, description="파워 점수")
    balance_score: float = Field(default=0.0, ge=0.0, le=100.0, description="균형 점수")
    consistency_score: float = Field(default=0.0, ge=0.0, le=100.0, description="일관성 점수")

    # 동작별 추가 점수 (슈팅 전용)
    release_angle_score: float | None = Field(default=None, ge=0.0, le=100.0, description="릴리스 각도 점수")
    arc_score: float | None = Field(default=None, ge=0.0, le=100.0, description="슛 궤적 점수")
    follow_through_score: float | None = Field(default=None, ge=0.0, le=100.0, description="팔로우 스루 점수")

    # 동작별 추가 점수 (드리블 전용)
    control_score: float | None = Field(default=None, ge=0.0, le=100.0, description="컨트롤 점수")
    speed_score: float | None = Field(default=None, ge=0.0, le=100.0, description="속도 점수")
    protection_score: float | None = Field(default=None, ge=0.0, le=100.0, description="볼 보호 점수")

    # 프레임 정보
    start_frame: int = Field(..., ge=0, description="시작 프레임")
    end_frame: int = Field(..., ge=0, description="종료 프레임")

    # 관련 피드백
    feedback_items: list[FeedbackItem] = Field(default_factory=list, description="관련 피드백 목록")

    # 결과 (슈팅의 경우)
    success: bool | None = Field(default=None, description="성공 여부 (골인 등)")


class MotionComparison(BaseModel):
    """
    동작 비교 DTO.

    따라하기 훈련에서 정답 동작과 사용자 동작을 비교합니다.
    """

    comparison_id: UUID = Field(default_factory=uuid4, description="비교 ID")

    # 비교 대상
    reference_motion_id: str = Field(..., description="기준(정답) 동작 ID")
    user_motion_index: int = Field(..., ge=0, description="사용자 동작 인덱스")

    # 전체 유사도
    overall_similarity: float = Field(..., ge=0.0, le=100.0, description="전체 유사도 (%)")

    # 단계별 유사도
    phase_similarities: dict[str, float] = Field(default_factory=dict, description="단계별 유사도")

    # 관절별 유사도
    joint_similarities: dict[str, float] = Field(default_factory=dict, description="관절별 유사도")

    # 주요 차이점
    major_differences: list[FeedbackItem] = Field(default_factory=list, description="주요 차이점 피드백")

    # 타이밍 비교
    timing_difference_seconds: float = Field(default=0.0, description="타이밍 차이 (초)")

    # 추천 개선 사항
    improvement_suggestions: list[str] = Field(default_factory=list, description="개선 제안 목록")


# =============================================================================
# 피드백 요약 DTO
# =============================================================================
class FeedbackSummary(BaseModel):
    """
    피드백 요약 DTO.

    분석 결과의 전체 피드백 요약입니다.
    """

    # -------------------------------------------------------------------------
    # 등급 임계값 설정 (configs/feedback/priorities.yaml과 동기화)
    # 참조: configs/feedback/priorities.yaml → score_thresholds
    # -------------------------------------------------------------------------
    GRADE_THRESHOLDS: ClassVar[dict[str, int]] = {
        "S": 95,  # 95점 이상: S등급
        "A": 85,  # 85점 이상: A등급
        "B": 70,  # 70점 이상: B등급
        "C": 55,  # 55점 이상: C등급
        "D": 40,  # 40점 이상: D등급
        "F": 0,   # 40점 미만: F등급
    }

    summary_id: UUID = Field(default_factory=uuid4, description="요약 ID")
    task_id: UUID = Field(..., description="태스크 ID")
    analysis_type: str = Field(..., description="분석 유형")

    # 전체 점수
    overall_score: float = Field(..., ge=0.0, le=100.0, description="종합 점수")
    grade: str = Field(..., pattern="^(S|A|B|C|D|F)$", description="등급")

    # 점수 분포
    score_distribution: dict[str, float] = Field(default_factory=dict, description="카테고리별 점수")

    # 동작 점수 목록
    motion_scores: list[MotionScore] = Field(default_factory=list, description="동작별 점수")

    # 강점 및 약점
    strengths: list[str] = Field(default_factory=list, description="강점 목록 (최대 5개)")
    weaknesses: list[str] = Field(default_factory=list, description="약점 목록 (최대 5개)")

    # 우선순위별 피드백 요약
    critical_feedbacks: list[FeedbackItem] = Field(default_factory=list, description="필수 개선 피드백")
    high_priority_feedbacks: list[FeedbackItem] = Field(default_factory=list, description="높은 우선순위 피드백")
    medium_priority_feedbacks: list[FeedbackItem] = Field(default_factory=list, description="중간 우선순위 피드백")
    low_priority_feedbacks: list[FeedbackItem] = Field(default_factory=list, description="낮은 우선순위 피드백")

    # 피드백 통계
    total_feedback_count: int = Field(default=0, ge=0, description="전체 피드백 수")
    positive_feedback_count: int = Field(default=0, ge=0, description="긍정적 피드백 수")
    correction_feedback_count: int = Field(default=0, ge=0, description="교정 피드백 수")

    # 시간 정보
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시간 (UTC)",
    )

    @field_validator("strengths", "weaknesses")
    @classmethod
    def validate_list_length(cls, v: list[str]) -> list[str]:
        """리스트 길이 제한 검증."""
        if len(v) > 5:
            return v[:5]
        return v

    @classmethod
    def calculate_grade(cls, score: float) -> str:
        """
        점수에 따른 등급 계산.

        GRADE_THRESHOLDS 클래스 변수를 참조하여 등급을 결정합니다.
        임계값은 configs/feedback/priorities.yaml과 동기화되어야 합니다.

        Args:
            score: 0.0 ~ 100.0 범위의 점수

        Returns:
            등급 문자열 (S, A, B, C, D, F 중 하나)

        Examples:
            >>> FeedbackSummary.calculate_grade(96.5)
            'S'
            >>> FeedbackSummary.calculate_grade(75.0)
            'B'
        """
        thresholds = cls.GRADE_THRESHOLDS
        if score >= thresholds["S"]:
            return "S"
        elif score >= thresholds["A"]:
            return "A"
        elif score >= thresholds["B"]:
            return "B"
        elif score >= thresholds["C"]:
            return "C"
        elif score >= thresholds["D"]:
            return "D"
        else:
            return "F"


# =============================================================================
# 훈련 추천 DTO
# =============================================================================
class TrainingRecommendation(BaseModel):
    """
    훈련 추천 DTO.

    분석 결과를 기반으로 한 개인 맞춤 훈련 추천입니다.
    """

    recommendation_id: UUID = Field(default_factory=uuid4, description="추천 ID")
    task_id: UUID = Field(..., description="분석 태스크 ID")

    # 추천 훈련 정보
    training_type: str = Field(..., description="훈련 유형")
    training_name: str = Field(..., description="훈련명")
    training_description: str = Field(..., description="훈련 설명")

    # 목표
    target_improvement: list[str] = Field(default_factory=list, description="목표 개선 영역")
    expected_benefit: str = Field(..., description="기대 효과")

    # 우선순위 및 난이도
    priority: int = Field(default=5, ge=1, le=10, description="우선순위 (1=최고)")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard|expert)$", description="난이도")
    estimated_duration_minutes: int = Field(default=15, ge=5, le=120, description="예상 소요 시간 (분)")

    # 참조 영상
    reference_video_id: str | None = Field(default=None, description="참조 영상 ID")
    reference_video_url: HttpUrl | None = Field(default=None, description="참조 영상 URL")

    # 추천 근거
    recommendation_reason: str = Field(..., description="추천 이유")
    related_weakness: str | None = Field(default=None, description="관련된 약점")
    related_feedback_ids: list[UUID] = Field(default_factory=list, description="관련 피드백 ID 목록")


class TrainingPlan(BaseModel):
    """
    훈련 계획 DTO.

    주간/월간 훈련 계획을 포함합니다.
    """

    plan_id: UUID = Field(default_factory=uuid4, description="계획 ID")
    user_id: str = Field(..., description="사용자 ID")

    # 기간 정보
    start_date: datetime = Field(..., description="시작일")
    end_date: datetime = Field(..., description="종료일")
    plan_type: str = Field(default="weekly", pattern="^(daily|weekly|monthly)$", description="계획 유형")

    # 추천 훈련 목록
    recommendations: list[TrainingRecommendation] = Field(default_factory=list, description="추천 훈련 목록")

    # 목표
    primary_goal: str = Field(..., description="주요 목표")
    secondary_goals: list[str] = Field(default_factory=list, description="부가 목표")

    # 일정별 훈련
    daily_schedule: dict[str, list[str]] = Field(default_factory=dict, description="일별 훈련 스케줄")

    # 총 훈련 시간
    total_duration_minutes: int = Field(default=0, ge=0, description="총 훈련 시간 (분)")

    # 생성 정보
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시간 (UTC)",
    )
    created_from_analysis_ids: list[UUID] = Field(default_factory=list, description="기반 분석 ID 목록")


# =============================================================================
# 진행 추적 DTO
# =============================================================================
class ProgressMetric(BaseModel):
    """
    진행 지표 DTO.

    시간에 따른 진행 상황을 추적합니다.
    """

    metric_id: UUID = Field(default_factory=uuid4, description="지표 ID")
    user_id: str = Field(..., description="사용자 ID")
    metric_type: str = Field(..., description="지표 유형")
    metric_name: str = Field(..., description="지표명")

    # 측정값
    value: float = Field(..., description="측정값")
    unit: str = Field(..., description="단위")

    # 이전 값과 비교
    previous_value: float | None = Field(default=None, description="이전 측정값")
    change_amount: float | None = Field(default=None, description="변화량")
    change_percent: float | None = Field(default=None, description="변화율 (%)")
    trend: str | None = Field(default=None, pattern="^(improving|stable|declining)$", description="추세")

    # 시간 정보
    measured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="측정 시간 (UTC)",
    )
    analysis_task_id: UUID | None = Field(default=None, description="관련 분석 태스크 ID")


class ProgressReport(BaseModel):
    """
    진행 보고서 DTO.

    주간/월간 진행 보고서입니다.
    """

    report_id: UUID = Field(default_factory=uuid4, description="보고서 ID")
    user_id: str = Field(..., description="사용자 ID")
    report_type: str = Field(default="weekly", pattern="^(daily|weekly|monthly)$", description="보고서 유형")

    # 기간 정보
    period_start: datetime = Field(..., description="기간 시작")
    period_end: datetime = Field(..., description="기간 종료")

    # 활동 요약
    total_training_sessions: int = Field(default=0, ge=0, description="총 훈련 세션 수")
    total_training_minutes: int = Field(default=0, ge=0, description="총 훈련 시간 (분)")
    total_motions_analyzed: int = Field(default=0, ge=0, description="분석된 동작 수")

    # 점수 추이
    average_score: float = Field(default=0.0, ge=0.0, le=100.0, description="평균 점수")
    best_score: float = Field(default=0.0, ge=0.0, le=100.0, description="최고 점수")
    worst_score: float = Field(default=0.0, ge=0.0, le=100.0, description="최저 점수")
    score_trend: str = Field(default="stable", pattern="^(improving|stable|declining)$", description="점수 추세")

    # 카테고리별 점수
    category_scores: dict[str, float] = Field(default_factory=dict, description="카테고리별 평균 점수")
    category_trends: dict[str, str] = Field(default_factory=dict, description="카테고리별 추세")

    # 주요 개선 사항
    improvements: list[str] = Field(default_factory=list, description="개선된 영역")
    areas_needing_work: list[str] = Field(default_factory=list, description="추가 개선 필요 영역")

    # 성취
    achievements: list[str] = Field(default_factory=list, description="성취 항목")

    # 다음 주 추천
    next_period_recommendations: list[TrainingRecommendation] = Field(default_factory=list, description="다음 기간 추천")

    # 진행 지표
    progress_metrics: list[ProgressMetric] = Field(default_factory=list, description="진행 지표 목록")

    # 시간 정보
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시간 (UTC)",
    )

    # 참조
    analysis_task_ids: list[UUID] = Field(default_factory=list, description="포함된 분석 태스크 ID 목록")


# =============================================================================
# 피드백 소스 열거형 (학습 시스템용)
# =============================================================================
@unique
class FeedbackSource(str, Enum):
    """
    피드백 소스.

    다국어 지원을 위해 get_name(lang) 메서드를 제공합니다.
    """

    USER = "user"  # 사용자 직접 입력
    SYSTEM = "system"  # 시스템 자동 생성
    AUTO = "auto"  # 자동 학습에 의한 생성
    EXPERT = "expert"  # 전문가 피드백
    COACH = "coach"  # 코치 피드백

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 소스명 반환 (모듈 레벨 캐시 참조)."""
        entry = _FEEDBACK_SOURCE_I18N[self.value]
        return entry.get(lang, entry[SupportedLanguage.KO])

    @property
    def to_korean(self) -> str:
        """한글 소스명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# =============================================================================
# 사용자 피드백 DTO (학습 시스템용)
# =============================================================================
class UserFeedback(BaseModel):
    """
    사용자 피드백 DTO.

    사용자가 분석 결과에 대해 제공하는 피드백입니다.
    학습 시스템에서 모델 개선에 활용됩니다.
    """

    feedback_id: UUID = Field(default_factory=uuid4, description="피드백 ID")
    user_id: str = Field(..., description="사용자 ID")
    analysis_id: UUID = Field(..., description="분석 ID")

    # 피드백 내용
    source: FeedbackSource = Field(default=FeedbackSource.USER, description="피드백 소스")
    rating: int = Field(..., ge=1, le=5, description="평점 (1-5)")
    is_accurate: bool | None = Field(default=None, description="분석 정확도 동의 여부")
    comment: str | None = Field(default=None, max_length=1000, description="상세 코멘트")

    # 특정 피드백 항목에 대한 반응
    feedback_item_id: UUID | None = Field(default=None, description="특정 피드백 항목 ID")
    is_helpful: bool | None = Field(default=None, description="도움이 되었는지 여부")
    correction_suggestion: str | None = Field(default=None, max_length=500, description="수정 제안")

    # 메타데이터
    device_type: str | None = Field(default=None, description="디바이스 타입")
    app_version: str | None = Field(default=None, description="앱 버전")

    # 시간 정보
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시간 (UTC)",
    )


# =============================================================================
# 피드백 효과 측정 DTO (학습 시스템용)
# =============================================================================
class FeedbackEffectiveness(BaseModel):
    """
    피드백 효과 측정 DTO.

    제공된 피드백이 사용자의 실력 향상에 얼마나 기여했는지 측정합니다.
    """

    effectiveness_id: UUID = Field(default_factory=uuid4, description="효과 측정 ID")
    user_id: str = Field(..., description="사용자 ID")
    feedback_item_id: UUID = Field(..., description="피드백 항목 ID")

    # 효과 측정
    before_score: float = Field(..., ge=0.0, le=100.0, description="피드백 전 점수")
    after_score: float = Field(..., ge=0.0, le=100.0, description="피드백 후 점수")
    improvement: float = Field(..., description="향상도 (점수 차이)")
    improvement_rate: float = Field(..., description="향상률 (%)")

    # 적용 횟수
    practice_count: int = Field(default=0, ge=0, description="연습 횟수")
    application_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="피드백 적용률")

    # 효과 등급
    effectiveness_grade: str = Field(
        default="C",
        pattern="^(S|A|B|C|D|F)$",
        description="효과 등급 (S, A, B, C, D, F)",
    )

    # 기간 정보
    measurement_period_days: int = Field(default=7, ge=1, description="측정 기간 (일)")
    first_analysis_id: UUID = Field(..., description="첫 번째 분석 ID")
    last_analysis_id: UUID = Field(..., description="마지막 분석 ID")

    # 시간 정보
    measured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="측정 시간 (UTC)",
    )

    @classmethod
    def calculate_grade(cls, improvement_rate: float) -> str:
        """
        향상률에 따른 효과 등급 계산.

        Args:
            improvement_rate: 향상률 (%)

        Returns:
            효과 등급 (S, A, B, C, D, F)
        """
        if improvement_rate >= 20.0:
            return "S"
        elif improvement_rate >= 15.0:
            return "A"
        elif improvement_rate >= 10.0:
            return "B"
        elif improvement_rate >= 5.0:
            return "C"
        elif improvement_rate >= 0.0:
            return "D"
        else:
            return "F"


# =============================================================================
# 피드백 결과 DTO (학습 시스템 통합용)
# =============================================================================
class FeedbackResult(BaseModel):
    """
    피드백 결과 DTO.

    분석 결과에 대한 전체 피드백 정보를 담습니다.
    학습 시스템에서 사용하는 통합 결과 객체입니다.
    """

    result_id: UUID = Field(default_factory=uuid4, description="결과 ID")
    analysis_id: UUID = Field(..., description="분석 ID")
    user_id: str = Field(..., description="사용자 ID")

    # 피드백 요약
    summary: FeedbackSummary | None = Field(default=None, description="피드백 요약")

    # 세부 피드백 목록
    feedback_items: list[FeedbackItem] = Field(default_factory=list, description="피드백 항목 목록")

    # 동작별 점수
    motion_scores: list[MotionScore] = Field(default_factory=list, description="동작별 점수")

    # 비교 결과 (따라하기 훈련용)
    comparisons: list[MotionComparison] = Field(default_factory=list, description="비교 결과")

    # 훈련 추천
    recommendations: list[TrainingRecommendation] = Field(default_factory=list, description="훈련 추천")

    # 사용자 피드백 수집
    user_feedbacks: list[UserFeedback] = Field(default_factory=list, description="사용자 피드백")

    # 효과 측정
    effectiveness_metrics: list[FeedbackEffectiveness] = Field(default_factory=list, description="효과 측정")

    # 시간 정보
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시간 (UTC)",
    )

    @property
    def overall_score(self) -> float:
        """전체 점수."""
        if self.summary:
            return self.summary.overall_score
        return 0.0

    @property
    def grade(self) -> str:
        """등급."""
        if self.summary:
            return self.summary.grade
        return "F"

    @property
    def feedback_count(self) -> int:
        """피드백 수."""
        return len(self.feedback_items)


# =============================================================================
# 피드백 DTO 모듈 익스포트
# =============================================================================
__all__ = [
    # 열거형
    "FeedbackCategory",
    "FeedbackPriority",
    "FeedbackType",
    "BodyPart",
    "MotionPhase",
    "FeedbackSource",
    # 세부 피드백
    "FeedbackItem",
    "MotionScore",
    "MotionComparison",
    # 피드백 요약
    "FeedbackSummary",
    # 훈련 추천
    "TrainingRecommendation",
    "TrainingPlan",
    # 진행 추적
    "ProgressMetric",
    "ProgressReport",
    # 학습 시스템용
    "UserFeedback",
    "FeedbackEffectiveness",
    "FeedbackResult",
]

# 모듈 버전 정보
__version__ = "1.0.0"
