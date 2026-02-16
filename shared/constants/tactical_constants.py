# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: tactical_constants.py
설명: 전술/전략 분석 도메인 상수 정의
      - 세트 플레이 유형 (14종)
      - 전환 공격 페이즈 (3종)
      - 플로어 스페이싱 등급 (5단계)
      - 턴오버 분류 (강제/비강제, 라이브/데드볼)
      - 스크린/픽앤롤 분석 파라미터
      - 속공/전환 속도 임계치
      - 모멘텀/런 감지 기준
      - 스페이싱/매치업/컨테스트 파라미터

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
- NBA Official Stats Tracking Methodology (Second Spectrum)
- Synergy Sports Play Type Classification
- FIBA Technical Manual for Coaches

사용처:
- game_analysis/tactical_analysis/: 공격 전술 분석
- game_analysis/defensive_analysis/: 수비 전술 분석
- game_analysis/spatial_analysis/: 공간 분석
- game_analysis/lineup_analysis/: 라인업 분석
- game_analysis/game_flow/: 경기 흐름 분석
- game_analysis/transition_analysis/: 전환 공수 분석
- game_analysis/play_type_analysis/: 플레이 유형별 분석
- game_analysis/individual_analysis/: 개인 심층 분석

주의:
    DefenseScheme, ActionType, ContestLevel, DribbleType, PassType,
    DefensiveActionType, MovementType 등은 shared/dto 계층에서 정의합니다.
    이 파일은 전술 분석의 '기준값(threshold)'과 '분류 어휘(vocabulary)'만 정의합니다.
"""

from enum import Enum, unique
from typing import Final

from shared.constants.localization import SupportedLanguage


__version__: str = "1.0.0"


# =============================================================================
# 세트 플레이 유형 열거형 (14종)
# =============================================================================
@unique
class SetPlayType(str, Enum):
    """
    세트 플레이 유형 열거형 (14종).

    하프코트 세트 오펜스에서 인식 가능한 플레이 패턴.
    set_play_recognizer.py에서 패턴 매칭의 기준으로 사용됩니다.
    """

    HORN = "horn"                       # 혼 (하이포스트 2인 + 엘보우)
    FLEX = "flex"                       # 플렉스 (스크린-더-스크리너, 연속 백스크린)
    MOTION = "motion"                   # 모션 (5인 연동 패싱 오펜스)
    FLOPPY = "floppy"                   # 플로피 (슈터 양측 스크린 택1)
    PRINCETON = "princeton"             # 프린스턴 (하이포스트 기점 백도어)
    TRIANGLE = "triangle"               # 트라이앵글 (삼각 구조, 포스트 기점)
    PICK_AND_ROLL = "pick_and_roll"     # 픽앤롤 (볼스크린 → 롤맨)
    PICK_AND_POP = "pick_and_pop"       # 픽앤팝 (볼스크린 → 팝아웃)
    ISOLATION = "isolation"             # 아이솔레이션 (1:1)
    POST_UP = "post_up"                 # 포스트업 (로우포스트 1:1)
    DRIBBLE_HAND_OFF = "dribble_hand_off"  # DHO (드리블 핸드오프)
    STAGGER_SCREEN = "stagger_screen"   # 스태거 스크린 (연속 오프볼 스크린)
    SPAIN_PNR = "spain_pnr"             # 스페인 PnR (PnR + 백스크린 콤보)
    ATO_SET = "ato_set"                 # ATO 세트 (타임아웃 후 디자인 플레이)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 플레이 유형명 반환."""
        return _SET_PLAY_I18N[self].get(
            lang, _SET_PLAY_I18N[self][SupportedLanguage.KO]
        )

    @property
    def involves_screen(self) -> bool:
        """스크린 포함 여부."""
        return self in _SCREEN_PLAYS

    @property
    def is_one_on_one(self) -> bool:
        """1:1 플레이 여부."""
        return self in (SetPlayType.ISOLATION, SetPlayType.POST_UP)


# 스크린 포함 플레이 집합
_SCREEN_PLAYS: frozenset[SetPlayType] = frozenset({
    SetPlayType.HORN,
    SetPlayType.FLEX,
    SetPlayType.FLOPPY,
    SetPlayType.PICK_AND_ROLL,
    SetPlayType.PICK_AND_POP,
    SetPlayType.DRIBBLE_HAND_OFF,
    SetPlayType.STAGGER_SCREEN,
    SetPlayType.SPAIN_PNR,
})

_SET_PLAY_I18N: dict[SetPlayType, dict[SupportedLanguage, str]] = {
    SetPlayType.HORN: {
        SupportedLanguage.KO: "혼",
        SupportedLanguage.EN: "Horn",
        SupportedLanguage.JA: "ホーン",
        SupportedLanguage.ZH: "牛角",
        SupportedLanguage.ES: "Cuerno",
    },
    SetPlayType.FLEX: {
        SupportedLanguage.KO: "플렉스",
        SupportedLanguage.EN: "Flex",
        SupportedLanguage.JA: "フレックス",
        SupportedLanguage.ZH: "弹性",
        SupportedLanguage.ES: "Flex",
    },
    SetPlayType.MOTION: {
        SupportedLanguage.KO: "모션",
        SupportedLanguage.EN: "Motion",
        SupportedLanguage.JA: "モーション",
        SupportedLanguage.ZH: "运动进攻",
        SupportedLanguage.ES: "Movimiento",
    },
    SetPlayType.FLOPPY: {
        SupportedLanguage.KO: "플로피",
        SupportedLanguage.EN: "Floppy",
        SupportedLanguage.JA: "フロッピー",
        SupportedLanguage.ZH: "交叉跑位",
        SupportedLanguage.ES: "Floppy",
    },
    SetPlayType.PRINCETON: {
        SupportedLanguage.KO: "프린스턴",
        SupportedLanguage.EN: "Princeton",
        SupportedLanguage.JA: "プリンストン",
        SupportedLanguage.ZH: "普林斯顿",
        SupportedLanguage.ES: "Princeton",
    },
    SetPlayType.TRIANGLE: {
        SupportedLanguage.KO: "트라이앵글",
        SupportedLanguage.EN: "Triangle",
        SupportedLanguage.JA: "トライアングル",
        SupportedLanguage.ZH: "三角进攻",
        SupportedLanguage.ES: "Triángulo",
    },
    SetPlayType.PICK_AND_ROLL: {
        SupportedLanguage.KO: "픽앤롤",
        SupportedLanguage.EN: "Pick and Roll",
        SupportedLanguage.JA: "ピック&ロール",
        SupportedLanguage.ZH: "挡拆",
        SupportedLanguage.ES: "Pick and Roll",
    },
    SetPlayType.PICK_AND_POP: {
        SupportedLanguage.KO: "픽앤팝",
        SupportedLanguage.EN: "Pick and Pop",
        SupportedLanguage.JA: "ピック&ポップ",
        SupportedLanguage.ZH: "挡拆外弹",
        SupportedLanguage.ES: "Pick and Pop",
    },
    SetPlayType.ISOLATION: {
        SupportedLanguage.KO: "아이솔레이션",
        SupportedLanguage.EN: "Isolation",
        SupportedLanguage.JA: "アイソレーション",
        SupportedLanguage.ZH: "单打",
        SupportedLanguage.ES: "Aislamiento",
    },
    SetPlayType.POST_UP: {
        SupportedLanguage.KO: "포스트업",
        SupportedLanguage.EN: "Post Up",
        SupportedLanguage.JA: "ポストアップ",
        SupportedLanguage.ZH: "背身单打",
        SupportedLanguage.ES: "Poste Bajo",
    },
    SetPlayType.DRIBBLE_HAND_OFF: {
        SupportedLanguage.KO: "드리블 핸드오프",
        SupportedLanguage.EN: "Dribble Hand-Off",
        SupportedLanguage.JA: "ドリブルハンドオフ",
        SupportedLanguage.ZH: "运球交球",
        SupportedLanguage.ES: "Entrega con Dribling",
    },
    SetPlayType.STAGGER_SCREEN: {
        SupportedLanguage.KO: "스태거 스크린",
        SupportedLanguage.EN: "Stagger Screen",
        SupportedLanguage.JA: "スタッガースクリーン",
        SupportedLanguage.ZH: "交错掩护",
        SupportedLanguage.ES: "Pantalla Escalonada",
    },
    SetPlayType.SPAIN_PNR: {
        SupportedLanguage.KO: "스페인 PnR",
        SupportedLanguage.EN: "Spain PnR",
        SupportedLanguage.JA: "スペインPnR",
        SupportedLanguage.ZH: "西班牙挡拆",
        SupportedLanguage.ES: "PnR España",
    },
    SetPlayType.ATO_SET: {
        SupportedLanguage.KO: "ATO 세트",
        SupportedLanguage.EN: "ATO Set",
        SupportedLanguage.JA: "ATOセット",
        SupportedLanguage.ZH: "暂停后战术",
        SupportedLanguage.ES: "Jugada Post-Tiempo",
    },
}


# =============================================================================
# 전환 공격 페이즈 열거형
# =============================================================================
@unique
class TransitionPhase(str, Enum):
    """
    전환 공격 페이즈 열거형 (3종).

    점유 전환 후 공격 전개 단계 분류.
    """

    PRIMARY_BREAK = "primary_break"     # 1차 속공 (수적 우위)
    SECONDARY_BREAK = "secondary_break" # 2차 속공 (얼리 진입)
    EARLY_OFFENSE = "early_offense"     # 얼리 오펜스 (전환 → 세트 과도기)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 페이즈명 반환."""
        return _TRANSITION_I18N[self].get(
            lang, _TRANSITION_I18N[self][SupportedLanguage.KO]
        )


_TRANSITION_I18N: dict[TransitionPhase, dict[SupportedLanguage, str]] = {
    TransitionPhase.PRIMARY_BREAK: {
        SupportedLanguage.KO: "1차 속공",
        SupportedLanguage.EN: "Primary Break",
        SupportedLanguage.JA: "ファーストブレイク",
        SupportedLanguage.ZH: "一次快攻",
        SupportedLanguage.ES: "Contraataque Primario",
    },
    TransitionPhase.SECONDARY_BREAK: {
        SupportedLanguage.KO: "2차 속공",
        SupportedLanguage.EN: "Secondary Break",
        SupportedLanguage.JA: "セカンダリーブレイク",
        SupportedLanguage.ZH: "二次快攻",
        SupportedLanguage.ES: "Contraataque Secundario",
    },
    TransitionPhase.EARLY_OFFENSE: {
        SupportedLanguage.KO: "얼리 오펜스",
        SupportedLanguage.EN: "Early Offense",
        SupportedLanguage.JA: "アーリーオフェンス",
        SupportedLanguage.ZH: "早期进攻",
        SupportedLanguage.ES: "Ataque Temprano",
    },
}


# =============================================================================
# 플로어 스페이싱 등급 열거형
# =============================================================================
@unique
class SpacingQuality(str, Enum):
    """
    플로어 스페이싱 등급 열거형 (5단계).

    5인 선수 간의 코트 활용도/간격 품질 평가.
    """

    EXCELLENT = "excellent"     # 최적 간격
    GOOD = "good"               # 양호
    AVERAGE = "average"         # 보통
    POOR = "poor"               # 부족
    COLLAPSED = "collapsed"     # 밀집 (스페이싱 붕괴)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 등급명 반환."""
        return _SPACING_I18N[self].get(
            lang, _SPACING_I18N[self][SupportedLanguage.KO]
        )


_SPACING_I18N: dict[SpacingQuality, dict[SupportedLanguage, str]] = {
    SpacingQuality.EXCELLENT: {
        SupportedLanguage.KO: "최적",
        SupportedLanguage.EN: "Excellent",
        SupportedLanguage.JA: "最適",
        SupportedLanguage.ZH: "最佳",
        SupportedLanguage.ES: "Excelente",
    },
    SpacingQuality.GOOD: {
        SupportedLanguage.KO: "양호",
        SupportedLanguage.EN: "Good",
        SupportedLanguage.JA: "良好",
        SupportedLanguage.ZH: "良好",
        SupportedLanguage.ES: "Bueno",
    },
    SpacingQuality.AVERAGE: {
        SupportedLanguage.KO: "보통",
        SupportedLanguage.EN: "Average",
        SupportedLanguage.JA: "普通",
        SupportedLanguage.ZH: "一般",
        SupportedLanguage.ES: "Promedio",
    },
    SpacingQuality.POOR: {
        SupportedLanguage.KO: "부족",
        SupportedLanguage.EN: "Poor",
        SupportedLanguage.JA: "不足",
        SupportedLanguage.ZH: "较差",
        SupportedLanguage.ES: "Pobre",
    },
    SpacingQuality.COLLAPSED: {
        SupportedLanguage.KO: "밀집",
        SupportedLanguage.EN: "Collapsed",
        SupportedLanguage.JA: "密集",
        SupportedLanguage.ZH: "拥挤",
        SupportedLanguage.ES: "Colapsado",
    },
}


# =============================================================================
# 턴오버 분류 열거형
# =============================================================================
@unique
class TurnoverCategory(str, Enum):
    """
    턴오버 분류 열거형 (4종).

    턴오버의 원인별 대분류.
    세부 18종 턴오버 유형은 event_detection에서 분류합니다.
    """

    FORCED_LIVE = "forced_live"         # 강제 + 라이브볼 (스틸 → 속공 가능)
    FORCED_DEAD = "forced_dead"         # 강제 + 데드볼 (파울 드로잉, 바이올레이션 유도)
    UNFORCED_LIVE = "unforced_live"     # 비강제 + 라이브볼 (핸들링 실수)
    UNFORCED_DEAD = "unforced_dead"     # 비강제 + 데드볼 (스텝 실수, 시간 초과)

    def __str__(self) -> str:
        return self.value

    @property
    def is_forced(self) -> bool:
        """수비에 의한 강제 턴오버 여부."""
        return self in (TurnoverCategory.FORCED_LIVE, TurnoverCategory.FORCED_DEAD)

    @property
    def is_live_ball(self) -> bool:
        """라이브볼 턴오버 여부 (즉시 속공 가능)."""
        return self in (TurnoverCategory.FORCED_LIVE, TurnoverCategory.UNFORCED_LIVE)

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 분류명 반환."""
        return _TURNOVER_I18N[self].get(
            lang, _TURNOVER_I18N[self][SupportedLanguage.KO]
        )


_TURNOVER_I18N: dict[TurnoverCategory, dict[SupportedLanguage, str]] = {
    TurnoverCategory.FORCED_LIVE: {
        SupportedLanguage.KO: "강제 라이브볼",
        SupportedLanguage.EN: "Forced Live Ball",
        SupportedLanguage.JA: "強制ライブボール",
        SupportedLanguage.ZH: "强制活球",
        SupportedLanguage.ES: "Forzado Balón Vivo",
    },
    TurnoverCategory.FORCED_DEAD: {
        SupportedLanguage.KO: "강제 데드볼",
        SupportedLanguage.EN: "Forced Dead Ball",
        SupportedLanguage.JA: "強制デッドボール",
        SupportedLanguage.ZH: "强制死球",
        SupportedLanguage.ES: "Forzado Balón Muerto",
    },
    TurnoverCategory.UNFORCED_LIVE: {
        SupportedLanguage.KO: "비강제 라이브볼",
        SupportedLanguage.EN: "Unforced Live Ball",
        SupportedLanguage.JA: "非強制ライブボール",
        SupportedLanguage.ZH: "非强制活球",
        SupportedLanguage.ES: "No Forzado Balón Vivo",
    },
    TurnoverCategory.UNFORCED_DEAD: {
        SupportedLanguage.KO: "비강제 데드볼",
        SupportedLanguage.EN: "Unforced Dead Ball",
        SupportedLanguage.JA: "非強制デッドボール",
        SupportedLanguage.ZH: "非强制死球",
        SupportedLanguage.ES: "No Forzado Balón Muerto",
    },
}


# =============================================================================
# 스크린/픽앤롤 분석 파라미터
# =============================================================================

# 볼스크린 유효 거리 (스크리너와 디펜더 사이, 미터)
SCREEN_CONTACT_DISTANCE_M: Final[float] = 0.5

# 스크린 앵글 유효 범위 (스크리너 정면 기준, 도)
SCREEN_ANGLE_MIN_DEG: Final[float] = 45.0
SCREEN_ANGLE_MAX_DEG: Final[float] = 135.0

# 롤맨 다이브 속도 임계치 (m/s, 스크린 후 림 방향)
ROLL_MAN_DIVE_SPEED_MIN: Final[float] = 2.0

# 팝아웃 거리 임계치 (스크린 후 3점 라인 밖으로, 미터)
POP_OUT_DISTANCE_MIN_M: Final[float] = 6.0

# PnR 수비 반응 시간 임계치 (스크린 접촉 후, 초)
PNR_DEFENSE_REACTION_TIME_SEC: Final[float] = 0.8

# 스크린 지속 시간 임계치 (초)
SCREEN_HOLD_TIME_MIN_SEC: Final[float] = 0.3
SCREEN_HOLD_TIME_MAX_SEC: Final[float] = 2.0

# 핸드오프 거리 임계치 (미터)
HAND_OFF_PROXIMITY_M: Final[float] = 1.0


# =============================================================================
# 전환 속도 임계치 (초)
# =============================================================================

# 1차 속공 최대 시간 (점유 시작 ~ 슛)
PRIMARY_BREAK_MAX_SEC: Final[float] = 5.0

# 2차 속공 최대 시간
SECONDARY_BREAK_MAX_SEC: Final[float] = 8.0

# 수비 복귀 목표 시간 (초, 점유 전환 후 5인 하프코트 내 복귀)
DEFENSIVE_TRANSITION_TARGET_SEC: Final[float] = 4.0

# 속공 수적 우위 판정 기준 (공격인원 - 수비인원)
FAST_BREAK_ADVANTAGE_MIN: Final[int] = 1

# 속공 시 공 전진 최소 속도 (m/s)
FAST_BREAK_BALL_SPEED_MIN: Final[float] = 3.5


# =============================================================================
# 플로어 스페이싱 파라미터
# =============================================================================

# 선수 간 최소 적정 간격 (미터)
SPACING_MIN_DISTANCE_M: Final[float] = 3.5

# 선수 간 최적 간격 (미터)
SPACING_OPTIMAL_DISTANCE_M: Final[float] = 4.5

# 선수 간 밀집 판정 거리 (미터, 이하면 밀집)
SPACING_COLLAPSED_DISTANCE_M: Final[float] = 2.5

# 코트 활용률 계산 — 볼록 껍질(convex hull) 면적 기준
# 전체 하프코트 면적 대비 5인 볼록껍질 비율
COURT_UTILIZATION_EXCELLENT: Final[float] = 0.55   # 55% 이상
COURT_UTILIZATION_GOOD: Final[float] = 0.45        # 45% 이상
COURT_UTILIZATION_POOR: Final[float] = 0.30        # 30% 미만

# 드라이브 레인 확보 최소 폭 (미터, 림까지 경로에 수비자 없는 폭)
DRIVE_LANE_MIN_WIDTH_M: Final[float] = 1.5


# =============================================================================
# 모멘텀/런 감지 파라미터
# =============================================================================

# 스코어링 런 판정 기준
SCORING_RUN_MIN_POINTS: Final[int] = 6     # 최소 6-0 런 이상
SCORING_RUN_MIN_UNANSWERED: Final[int] = 3  # 최소 3회 연속 무득점

# 모멘텀 변동 감지 — 연속 득점/실점 패턴
MOMENTUM_SHIFT_THRESHOLD: Final[int] = 8    # 8점 이상 런 = 모멘텀 전환

# 득점 가뭄 판정 (연속 무득점 점유 횟수)
SCORING_DROUGHT_POSSESSIONS: Final[int] = 5

# 모멘텀 감쇠 계수 (시간 경과에 따른 모멘텀 자연 감소)
MOMENTUM_DECAY_PER_MINUTE: Final[float] = 0.05

# 타임아웃 후 모멘텀 리셋 비율 (0.0=완전 리셋, 1.0=유지)
MOMENTUM_TIMEOUT_RESET_FACTOR: Final[float] = 0.3


# =============================================================================
# 템포 분석 파라미터 (점유당 시간 기준)
# =============================================================================

# 빠른 템포 (점유당 평균 시간, 초)
TEMPO_FAST_THRESHOLD_SEC: Final[float] = 12.0

# 느린 템포
TEMPO_SLOW_THRESHOLD_SEC: Final[float] = 18.0

# 하프코트 세팅 완료 판정 (점유 시작 후, 초)
HALFCOURT_SET_TIME_SEC: Final[float] = 8.0


# =============================================================================
# 매치업/수비 분석 파라미터
# =============================================================================

# 매치업 배정 거리 임계치 (미터, 이 거리 내 가장 가까운 수비자 = 매치업)
MATCHUP_ASSIGNMENT_DISTANCE_M: Final[float] = 3.0

# 수비 이탈 판정 거리 (미터, 매치업 상대와의 거리가 이 이상이면 이탈)
DEFENSIVE_BREAKDOWN_DISTANCE_M: Final[float] = 5.0

# 클로즈아웃 시작 거리 (미터, 수비자가 이 거리 밖에서 접근 시작)
CLOSEOUT_START_DISTANCE_M: Final[float] = 3.0

# 클로즈아웃 성공 거리 (미터, 이 거리 이내 도착 = 성공적 클로즈아웃)
CLOSEOUT_SUCCESS_DISTANCE_M: Final[float] = 1.2

# 클로즈아웃 목표 도착 시간 (초)
CLOSEOUT_TARGET_TIME_SEC: Final[float] = 1.0

# 헬프 수비 트리거 거리 (미터, 드라이버가 이 거리 내 페인트 진입 시)
HELP_DEFENSE_TRIGGER_DISTANCE_M: Final[float] = 2.5

# 헬프 수비 후 리커버리 목표 시간 (초)
HELP_RECOVERY_TARGET_SEC: Final[float] = 1.5

# 슛 컨테스트 유효 거리 (미터, 슈터와 수비자)
SHOT_CONTEST_EFFECTIVE_M: Final[float] = 1.5

# 핸드업(손 올림) 인식 최소 각도 (팔꿈치 이상 올림, 도)
HAND_UP_MIN_ANGLE_DEG: Final[float] = 120.0


# =============================================================================
# 드라이브 분석 파라미터
# =============================================================================

# 드라이브 시작 판정 속도 (m/s, 볼핸들러가 이 속도 이상으로 림 방향 이동)
DRIVE_START_SPEED_MIN: Final[float] = 2.5

# 드라이브 방향 판정 각도 (림 방향 ±30도 이내)
DRIVE_DIRECTION_ANGLE_DEG: Final[float] = 30.0

# 드라이브 최소 거리 (미터, 이 이상 전진해야 드라이브로 인정)
DRIVE_MIN_DISTANCE_M: Final[float] = 1.5

# 드라이브 종료 판정 (속도 감소 또는 킥아웃/슛/패스)
DRIVE_END_SPEED_THRESHOLD: Final[float] = 1.0

# 드라이브 킥아웃 최대 시간 (드라이브 종료 후, 초)
DRIVE_KICKOUT_MAX_SEC: Final[float] = 2.0


# =============================================================================
# 오프볼 무브먼트 패턴 파라미터
# =============================================================================

# 커팅 속도 임계치 (m/s, 이 속도 이상 = 적극적 컷)
CUT_SPEED_MIN: Final[float] = 3.0

# 커팅 림 방향 최대 각도 (도)
CUT_DIRECTION_ANGLE_DEG: Final[float] = 45.0

# 스크린 사용 후 커터의 속도 변화 감지 (m/s 증가)
SCREEN_EXIT_SPEED_CHANGE: Final[float] = 1.5

# V-Cut / L-Cut 방향 변환 각도 (도, 최소 이 이상 변환해야 유효)
CUT_DIRECTION_CHANGE_MIN_DEG: Final[float] = 60.0


# =============================================================================
# 리바운드 분석 파라미터
# =============================================================================

# 박스아웃 유효 거리 (수비자 ~ 공격자, 미터)
BOX_OUT_EFFECTIVE_DISTANCE_M: Final[float] = 1.5

# 박스아웃 시작 시점 (슛 릴리즈 후, 초)
BOX_OUT_REACTION_TIME_SEC: Final[float] = 0.5

# 장거리 리바운드 거리 기준 (미터, 림으로부터)
LONG_REBOUND_DISTANCE_M: Final[float] = 4.0

# 팁 체인 최대 간격 (초, 연속 팁 인정 최대 시간)
TIP_CHAIN_MAX_INTERVAL_SEC: Final[float] = 1.5


# =============================================================================
# 리드 관리 분석 파라미터
# =============================================================================

# 접전 판정 점수차 (이하)
CLOSE_GAME_MARGIN: Final[int] = 5

# 블로우아웃 판정 점수차 (이상)
BLOWOUT_MARGIN: Final[int] = 20

# 역전 구간 감지 최소 지속 시간 (초)
COMEBACK_MIN_DURATION_SEC: Final[float] = 60.0


# =============================================================================
# 유틸리티 함수
# =============================================================================

def classify_spacing_quality(avg_player_distance_m: float) -> SpacingQuality:
    """
    평균 선수 간 거리로 스페이싱 등급 분류.

    Args:
        avg_player_distance_m: 5인 선수 간 평균 거리 (미터)

    Returns:
        SpacingQuality 등급
    """
    if avg_player_distance_m >= SPACING_OPTIMAL_DISTANCE_M:
        return SpacingQuality.EXCELLENT
    elif avg_player_distance_m >= SPACING_MIN_DISTANCE_M:
        return SpacingQuality.GOOD
    elif avg_player_distance_m >= SPACING_COLLAPSED_DISTANCE_M + 0.5:
        return SpacingQuality.AVERAGE
    elif avg_player_distance_m >= SPACING_COLLAPSED_DISTANCE_M:
        return SpacingQuality.POOR
    else:
        return SpacingQuality.COLLAPSED


def classify_transition_phase(time_since_possession_sec: float) -> TransitionPhase:
    """
    점유 경과 시간으로 전환 공격 페이즈 분류.

    Args:
        time_since_possession_sec: 점유 시작 후 경과 시간 (초)

    Returns:
        TransitionPhase 페이즈
    """
    if time_since_possession_sec <= PRIMARY_BREAK_MAX_SEC:
        return TransitionPhase.PRIMARY_BREAK
    elif time_since_possession_sec <= SECONDARY_BREAK_MAX_SEC:
        return TransitionPhase.SECONDARY_BREAK
    else:
        return TransitionPhase.EARLY_OFFENSE


def is_scoring_run(
    team_points_unanswered: int, opponent_consecutive_scoreless: int
) -> bool:
    """
    스코어링 런 판정.

    Args:
        team_points_unanswered: 팀 연속 무응답 득점
        opponent_consecutive_scoreless: 상대 연속 무득점 점유 횟수

    Returns:
        스코어링 런 여부
    """
    return (
        team_points_unanswered >= SCORING_RUN_MIN_POINTS
        and opponent_consecutive_scoreless >= SCORING_RUN_MIN_UNANSWERED
    )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__: list[str] = [
    # 버전
    "__version__",
    # 열거형
    "SetPlayType",
    "TransitionPhase",
    "SpacingQuality",
    "TurnoverCategory",
    # 스크린/PnR 파라미터
    "SCREEN_CONTACT_DISTANCE_M",
    "SCREEN_ANGLE_MIN_DEG",
    "SCREEN_ANGLE_MAX_DEG",
    "ROLL_MAN_DIVE_SPEED_MIN",
    "POP_OUT_DISTANCE_MIN_M",
    "PNR_DEFENSE_REACTION_TIME_SEC",
    "SCREEN_HOLD_TIME_MIN_SEC",
    "SCREEN_HOLD_TIME_MAX_SEC",
    "HAND_OFF_PROXIMITY_M",
    # 전환 속도 임계치
    "PRIMARY_BREAK_MAX_SEC",
    "SECONDARY_BREAK_MAX_SEC",
    "DEFENSIVE_TRANSITION_TARGET_SEC",
    "FAST_BREAK_ADVANTAGE_MIN",
    "FAST_BREAK_BALL_SPEED_MIN",
    # 스페이싱 파라미터
    "SPACING_MIN_DISTANCE_M",
    "SPACING_OPTIMAL_DISTANCE_M",
    "SPACING_COLLAPSED_DISTANCE_M",
    "COURT_UTILIZATION_EXCELLENT",
    "COURT_UTILIZATION_GOOD",
    "COURT_UTILIZATION_POOR",
    "DRIVE_LANE_MIN_WIDTH_M",
    # 모멘텀/런 파라미터
    "SCORING_RUN_MIN_POINTS",
    "SCORING_RUN_MIN_UNANSWERED",
    "MOMENTUM_SHIFT_THRESHOLD",
    "SCORING_DROUGHT_POSSESSIONS",
    "MOMENTUM_DECAY_PER_MINUTE",
    "MOMENTUM_TIMEOUT_RESET_FACTOR",
    # 템포 파라미터
    "TEMPO_FAST_THRESHOLD_SEC",
    "TEMPO_SLOW_THRESHOLD_SEC",
    "HALFCOURT_SET_TIME_SEC",
    # 매치업/수비 파라미터
    "MATCHUP_ASSIGNMENT_DISTANCE_M",
    "DEFENSIVE_BREAKDOWN_DISTANCE_M",
    "CLOSEOUT_START_DISTANCE_M",
    "CLOSEOUT_SUCCESS_DISTANCE_M",
    "CLOSEOUT_TARGET_TIME_SEC",
    "HELP_DEFENSE_TRIGGER_DISTANCE_M",
    "HELP_RECOVERY_TARGET_SEC",
    "SHOT_CONTEST_EFFECTIVE_M",
    "HAND_UP_MIN_ANGLE_DEG",
    # 드라이브 파라미터
    "DRIVE_START_SPEED_MIN",
    "DRIVE_DIRECTION_ANGLE_DEG",
    "DRIVE_MIN_DISTANCE_M",
    "DRIVE_END_SPEED_THRESHOLD",
    "DRIVE_KICKOUT_MAX_SEC",
    # 오프볼 무브먼트 파라미터
    "CUT_SPEED_MIN",
    "CUT_DIRECTION_ANGLE_DEG",
    "SCREEN_EXIT_SPEED_CHANGE",
    "CUT_DIRECTION_CHANGE_MIN_DEG",
    # 리바운드 파라미터
    "BOX_OUT_EFFECTIVE_DISTANCE_M",
    "BOX_OUT_REACTION_TIME_SEC",
    "LONG_REBOUND_DISTANCE_M",
    "TIP_CHAIN_MAX_INTERVAL_SEC",
    # 리드 관리 파라미터
    "CLOSE_GAME_MARGIN",
    "BLOWOUT_MARGIN",
    "COMEBACK_MIN_DURATION_SEC",
    # 유틸리티 함수
    "classify_spacing_quality",
    "classify_transition_phase",
    "is_scoring_run",
]
