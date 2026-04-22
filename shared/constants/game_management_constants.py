# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: game_management_constants.py
설명: 경기 관리(기록원 대체) 도메인 상수 정의
      - 경기 상태 머신 (9상태)
      - 보너스 상태 (3단계)
      - 타임아웃 유형 (3종)
      - 기록지 출력 형식 (6종)
      - 리그별 쿼터 시간, 타임아웃 규칙, 교체 규칙
      - 파울 관리 파라미터
      - 경기 시계 관리 파라미터

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-15
버전: 1.0.0

참조:
- FIBA Official Basketball Rules 2024
- NBA Official Rulebook 2024-25
- KBL 경기 운영 규칙 2024-25

사용처:
- game_analysis/game_management/: 경기 상태, 교체, 파울, 타임아웃, 시계 관리
- game_analysis/game_management/clock_manager.py: 경기/슛 시계
- game_analysis/game_management/foul_manager.py: 파울 누적/보너스
- game_analysis/game_management/timeout_manager.py: 타임아웃 관리
- game_analysis/game_management/substitution_manager.py: 교체 관리
- game_analysis/game_management/official_format_exporter.py: 기록지 출력
- game_analysis/live_workspace/: 실시간 이벤트 검증

주의:
    RuleSet(리그 규정)은 referee_rule_constants.py에서 정의합니다.
    이 파일은 경기 '운영/관리'에 특화된 상수만 정의합니다.

사용 예시:
    >>> from shared.constants.game_management_constants import GameState, BonusStatus
    >>> GameState.LIVE.is_clock_running
    True
    >>> BonusStatus.BONUS.grants_free_throws
    True
"""

from __future__ import annotations


from enum import Enum, unique
from typing import Final

from shared.constants.localization import SupportedLanguage
from shared.constants.referee_rule_constants import RuleSet


# =============================================================================
# 경기 상태 머신 열거형 (9상태)
# =============================================================================
@unique
class GameState(str, Enum):
    """
    경기 상태 머신 열거형 (9상태).

    농구 경기의 전체 진행 상태를 표현합니다.
    clock_manager.py에서 상태 전이를 관리합니다.

    상태 전이 다이어그램:
    PRE_GAME → TIP_OFF → LIVE
    LIVE ↔ DEAD_BALL
    LIVE/DEAD_BALL → TIMEOUT → LIVE
    LIVE/DEAD_BALL → PERIOD_BREAK (쿼터 종료)
    PERIOD_BREAK → LIVE (다음 쿼터 시작)
    PERIOD_BREAK → HALFTIME → LIVE (2Q→3Q)
    4Q 종료 + 동점 → OVERTIME → LIVE
    4Q/OT 종료 + 점수차 → FINAL
    """

    PRE_GAME = "pre_game"           # 경기 전
    TIP_OFF = "tip_off"             # 점프볼 (경기 시작)
    LIVE = "live"                   # 라이브 (경기 시계 진행)
    DEAD_BALL = "dead_ball"         # 데드볼 (시계 정지)
    TIMEOUT = "timeout"             # 타임아웃
    PERIOD_BREAK = "period_break"   # 쿼터 사이 휴식
    HALFTIME = "halftime"           # 하프타임
    OVERTIME = "overtime"           # 연장전 시작
    FINAL = "final"                 # 경기 종료

    def __str__(self) -> str:
        return self.value

    @property
    def is_clock_running(self) -> bool:
        """경기 시계 진행 중 여부."""
        return self == GameState.LIVE

    @property
    def is_game_active(self) -> bool:
        """경기가 진행 중(종료 전) 여부."""
        return self not in (GameState.PRE_GAME, GameState.FINAL)

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 상태명 반환."""
        return _GAME_STATE_I18N[self].get(
            lang, _GAME_STATE_I18N[self][SupportedLanguage.KO]
        )


_GAME_STATE_I18N: dict[GameState, dict[SupportedLanguage, str]] = {
    GameState.PRE_GAME: {
        SupportedLanguage.KO: "경기 전",
        SupportedLanguage.EN: "Pre-game",
        SupportedLanguage.JA: "試合前",
        SupportedLanguage.ZH: "赛前",
        SupportedLanguage.ES: "Pre-partido",
    },
    GameState.TIP_OFF: {
        SupportedLanguage.KO: "점프볼",
        SupportedLanguage.EN: "Tip-off",
        SupportedLanguage.JA: "ティップオフ",
        SupportedLanguage.ZH: "跳球",
        SupportedLanguage.ES: "Salto Inicial",
    },
    GameState.LIVE: {
        SupportedLanguage.KO: "진행 중",
        SupportedLanguage.EN: "Live",
        SupportedLanguage.JA: "プレー中",
        SupportedLanguage.ZH: "比赛进行中",
        SupportedLanguage.ES: "En Juego",
    },
    GameState.DEAD_BALL: {
        SupportedLanguage.KO: "데드볼",
        SupportedLanguage.EN: "Dead Ball",
        SupportedLanguage.JA: "デッドボール",
        SupportedLanguage.ZH: "死球",
        SupportedLanguage.ES: "Balón Muerto",
    },
    GameState.TIMEOUT: {
        SupportedLanguage.KO: "타임아웃",
        SupportedLanguage.EN: "Timeout",
        SupportedLanguage.JA: "タイムアウト",
        SupportedLanguage.ZH: "暂停",
        SupportedLanguage.ES: "Tiempo Muerto",
    },
    GameState.PERIOD_BREAK: {
        SupportedLanguage.KO: "쿼터 휴식",
        SupportedLanguage.EN: "Period Break",
        SupportedLanguage.JA: "クォーター間休憩",
        SupportedLanguage.ZH: "节间休息",
        SupportedLanguage.ES: "Descanso de Periodo",
    },
    GameState.HALFTIME: {
        SupportedLanguage.KO: "하프타임",
        SupportedLanguage.EN: "Halftime",
        SupportedLanguage.JA: "ハーフタイム",
        SupportedLanguage.ZH: "中场休息",
        SupportedLanguage.ES: "Medio Tiempo",
    },
    GameState.OVERTIME: {
        SupportedLanguage.KO: "연장전",
        SupportedLanguage.EN: "Overtime",
        SupportedLanguage.JA: "延長戦",
        SupportedLanguage.ZH: "加时赛",
        SupportedLanguage.ES: "Prórroga",
    },
    GameState.FINAL: {
        SupportedLanguage.KO: "경기 종료",
        SupportedLanguage.EN: "Final",
        SupportedLanguage.JA: "試合終了",
        SupportedLanguage.ZH: "比赛结束",
        SupportedLanguage.ES: "Final",
    },
}


# =============================================================================
# 유효한 상태 전이 (경기 상태 머신)
# =============================================================================
VALID_GAME_STATE_TRANSITIONS: Final[dict[GameState, frozenset[GameState]]] = {
    GameState.PRE_GAME: frozenset({GameState.TIP_OFF}),
    GameState.TIP_OFF: frozenset({GameState.LIVE}),
    GameState.LIVE: frozenset({
        GameState.DEAD_BALL, GameState.TIMEOUT,
        GameState.PERIOD_BREAK, GameState.FINAL,
    }),
    GameState.DEAD_BALL: frozenset({
        GameState.LIVE, GameState.TIMEOUT,
        GameState.PERIOD_BREAK, GameState.FINAL,
    }),
    GameState.TIMEOUT: frozenset({GameState.LIVE, GameState.DEAD_BALL}),
    GameState.PERIOD_BREAK: frozenset({
        GameState.LIVE, GameState.HALFTIME, GameState.OVERTIME,
    }),
    GameState.HALFTIME: frozenset({GameState.LIVE}),
    GameState.OVERTIME: frozenset({GameState.LIVE}),
    GameState.FINAL: frozenset(),  # 종료 상태 — 전이 없음
}


# =============================================================================
# 보너스 상태 열거형
# =============================================================================
@unique
class BonusStatus(str, Enum):
    """
    팀 파울 보너스 상태 열거형 (3단계).

    팀 파울 누적에 따른 자유투 부여 상태.
    리그별 보너스 전환 기준이 다릅니다.
    """

    NONE = "none"                   # 보너스 없음
    BONUS = "bonus"                 # 보너스 (FIBA: 5번째 팀파울~)
    DOUBLE_BONUS = "double_bonus"   # 더블 보너스 / 페널티 (NBA: 5번째~)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 보너스 상태명 반환."""
        return _BONUS_I18N[self].get(
            lang, _BONUS_I18N[self][SupportedLanguage.KO]
        )

    @property
    def grants_free_throws(self) -> bool:
        """자유투 부여 여부."""
        return self != BonusStatus.NONE


_BONUS_I18N: dict[BonusStatus, dict[SupportedLanguage, str]] = {
    BonusStatus.NONE: {
        SupportedLanguage.KO: "보너스 없음",
        SupportedLanguage.EN: "No Bonus",
        SupportedLanguage.JA: "ボーナスなし",
        SupportedLanguage.ZH: "无罚球",
        SupportedLanguage.ES: "Sin Bonificación",
    },
    BonusStatus.BONUS: {
        SupportedLanguage.KO: "보너스",
        SupportedLanguage.EN: "Bonus",
        SupportedLanguage.JA: "ボーナス",
        SupportedLanguage.ZH: "罚球",
        SupportedLanguage.ES: "Bonificación",
    },
    BonusStatus.DOUBLE_BONUS: {
        SupportedLanguage.KO: "더블 보너스",
        SupportedLanguage.EN: "Double Bonus",
        SupportedLanguage.JA: "ダブルボーナス",
        SupportedLanguage.ZH: "双倍罚球",
        SupportedLanguage.ES: "Doble Bonificación",
    },
}


# =============================================================================
# 타임아웃 유형 열거형
# =============================================================================
@unique
class TimeoutType(str, Enum):
    """
    타임아웃 유형 열거형 (3종).

    리그에 따라 사용 가능한 타임아웃 유형이 다릅니다.
    """

    FULL = "full"                   # 풀 타임아웃 (60~75초)
    TWENTY_SECOND = "twenty_second" # 20초 타임아웃 (NBA 구 규칙)
    OFFICIAL = "official"           # 공식 타임아웃 (TV, 방송 타임아웃)

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 타임아웃 유형명 반환."""
        return _TIMEOUT_TYPE_I18N[self].get(
            lang, _TIMEOUT_TYPE_I18N[self][SupportedLanguage.KO]
        )


_TIMEOUT_TYPE_I18N: dict[TimeoutType, dict[SupportedLanguage, str]] = {
    TimeoutType.FULL: {
        SupportedLanguage.KO: "풀 타임아웃",
        SupportedLanguage.EN: "Full Timeout",
        SupportedLanguage.JA: "フルタイムアウト",
        SupportedLanguage.ZH: "完整暂停",
        SupportedLanguage.ES: "Tiempo Completo",
    },
    TimeoutType.TWENTY_SECOND: {
        SupportedLanguage.KO: "20초 타임아웃",
        SupportedLanguage.EN: "20-second Timeout",
        SupportedLanguage.JA: "20秒タイムアウト",
        SupportedLanguage.ZH: "20秒暂停",
        SupportedLanguage.ES: "Tiempo de 20 Segundos",
    },
    TimeoutType.OFFICIAL: {
        SupportedLanguage.KO: "공식 타임아웃",
        SupportedLanguage.EN: "Official Timeout",
        SupportedLanguage.JA: "オフィシャルタイムアウト",
        SupportedLanguage.ZH: "官方暂停",
        SupportedLanguage.ES: "Tiempo Oficial",
    },
}


# =============================================================================
# 공식 기록 형식 열거형
# =============================================================================
@unique
class RecordFormat(str, Enum):
    """
    공식 기록지 출력 형식 열거형 (6종).
    """

    FIBA_BOXSCORE = "fiba_boxscore"     # FIBA 공식 박스스코어
    NBA_BOXSCORE = "nba_boxscore"       # NBA 공식 박스스코어
    KBL_BOXSCORE = "kbl_boxscore"       # KBL 공식 기록지
    NBL_BOXSCORE = "nbl_boxscore"       # NBL 공식 기록지
    JSON_FEED = "json_feed"             # JSON 실시간 데이터 피드
    XML_FEED = "xml_feed"               # XML 실시간 데이터 피드

    def __str__(self) -> str:
        return self.value

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 기록 형식명 반환."""
        return _RECORD_FORMAT_I18N[self].get(
            lang, _RECORD_FORMAT_I18N[self][SupportedLanguage.KO]
        )

    def to_korean(self) -> str:
        """한글 기록 형식명 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


_RECORD_FORMAT_I18N: dict[RecordFormat, dict[SupportedLanguage, str]] = {
    RecordFormat.FIBA_BOXSCORE: {
        SupportedLanguage.KO: "FIBA 박스스코어",
        SupportedLanguage.EN: "FIBA Box Score",
        SupportedLanguage.JA: "FIBAボックススコア",
        SupportedLanguage.ZH: "FIBA技术统计",
        SupportedLanguage.ES: "Estadísticas FIBA",
    },
    RecordFormat.NBA_BOXSCORE: {
        SupportedLanguage.KO: "NBA 박스스코어",
        SupportedLanguage.EN: "NBA Box Score",
        SupportedLanguage.JA: "NBAボックススコア",
        SupportedLanguage.ZH: "NBA技术统计",
        SupportedLanguage.ES: "Estadísticas NBA",
    },
    RecordFormat.KBL_BOXSCORE: {
        SupportedLanguage.KO: "KBL 기록지",
        SupportedLanguage.EN: "KBL Box Score",
        SupportedLanguage.JA: "KBLボックススコア",
        SupportedLanguage.ZH: "KBL技术统计",
        SupportedLanguage.ES: "Estadísticas KBL",
    },
    RecordFormat.NBL_BOXSCORE: {
        SupportedLanguage.KO: "NBL 기록지",
        SupportedLanguage.EN: "NBL Box Score",
        SupportedLanguage.JA: "NBLボックススコア",
        SupportedLanguage.ZH: "NBL技术统计",
        SupportedLanguage.ES: "Estadísticas NBL",
    },
    RecordFormat.JSON_FEED: {
        SupportedLanguage.KO: "JSON 데이터 피드",
        SupportedLanguage.EN: "JSON Data Feed",
        SupportedLanguage.JA: "JSONデータフィード",
        SupportedLanguage.ZH: "JSON数据源",
        SupportedLanguage.ES: "Fuente de Datos JSON",
    },
    RecordFormat.XML_FEED: {
        SupportedLanguage.KO: "XML 데이터 피드",
        SupportedLanguage.EN: "XML Data Feed",
        SupportedLanguage.JA: "XMLデータフィード",
        SupportedLanguage.ZH: "XML数据源",
        SupportedLanguage.ES: "Fuente de Datos XML",
    },
}


# =============================================================================
# 리그별 타임아웃 규칙
# =============================================================================

# 리그별 팀 타임아웃 수 (레귤러 타임)
TIMEOUTS_PER_TEAM: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 5,          # FIBA: 전반 2개, 후반 3개 (미사용 이월 불가)
    RuleSet.NBA: 7,           # NBA: 전체 7개 (75초 통합)
    RuleSet.KBL: 5,           # KBL: FIBA 준용
    RuleSet.NBL: 5,           # NBL: FIBA 준용
    RuleSet.EUROLEAGUE: 5,    # 유로리그: FIBA 준용
}

# 리그별 타임아웃 시간 (초)
TIMEOUT_DURATION_SEC: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 60,
    RuleSet.NBA: 75,
    RuleSet.KBL: 60,
    RuleSet.NBL: 60,
    RuleSet.EUROLEAGUE: 60,
}

# FIBA 전반 최대 타임아웃 수
FIBA_FIRST_HALF_MAX_TIMEOUTS: Final[int] = 2

# FIBA 후반 최대 타임아웃 수
FIBA_SECOND_HALF_MAX_TIMEOUTS: Final[int] = 3

# NBA OT 추가 타임아웃 수
NBA_OT_ADDITIONAL_TIMEOUTS: Final[int] = 2


# =============================================================================
# 리그별 쿼터/경기 시간 (초)
# =============================================================================

# 쿼터 시간 (초) — referee_rule_constants.RuleSet.quarter_duration_sec 와 동일하나
# 경기 관리 맥락에서 직접 참조 편의를 위해 재정의
QUARTER_DURATION_SEC: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 600,        # 10분
    RuleSet.NBA: 720,         # 12분
    RuleSet.KBL: 600,         # 10분
    RuleSet.NBL: 600,         # 10분
    RuleSet.EUROLEAGUE: 600,  # 10분
}

# 연장전 시간 (초) — 모든 리그 공통 5분
OVERTIME_DURATION_SEC: Final[int] = 300

# 쿼터 수 (정규)
REGULAR_PERIODS: Final[int] = 4

# 하프타임 휴식 (초)
HALFTIME_BREAK_SEC: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 900,        # 15분 (대회에 따라 20분)
    RuleSet.NBA: 900,         # 15분 (TV 방송 시 18분)
    RuleSet.KBL: 900,
    RuleSet.NBL: 900,
    RuleSet.EUROLEAGUE: 900,
}

# 쿼터 간 휴식 (초)
PERIOD_BREAK_SEC: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 120,        # 2분
    RuleSet.NBA: 130,         # 2분 10초
    RuleSet.KBL: 120,
    RuleSet.NBL: 120,
    RuleSet.EUROLEAGUE: 120,
}


# =============================================================================
# 파울 관리 파라미터
# =============================================================================

# 리그별 보너스 전환 팀파울 수 (쿼터당)
TEAM_FOUL_BONUS_THRESHOLD: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 4,          # 5번째 팀파울부터 보너스
    RuleSet.NBA: 4,           # 5번째 팀파울부터 보너스
    RuleSet.KBL: 4,
    RuleSet.NBL: 4,
    RuleSet.EUROLEAGUE: 4,
}

# NBA 더블 보너스 (페널티) 전환 팀파울 수
NBA_DOUBLE_BONUS_THRESHOLD: Final[int] = 10  # 쿼터 10번째 팀파울부터 (실제 운용 없음, 4Q 규칙)

# 파울 트러블 경고 기준 (퇴장 기준 - N개)
FOUL_TROUBLE_WARNING_OFFSET: Final[int] = 1  # 퇴장 기준 - 1개에 경고

# 파울아웃 리스크 시간 가중치 (남은 시간 대비 파울 수)
# 파울아웃 리스크 = (현재 파울 / 퇴장 기준) / (남은 시간 / 전체 시간)
# 이 값 이상이면 높은 리스크
FOUL_OUT_RISK_THRESHOLD: Final[float] = 1.2


# =============================================================================
# 교체 관리 파라미터
# =============================================================================

# 최소 출전 시간 판정 기준 (분, DNP-CD 판정)
MIN_PLAYING_TIME_FOR_DNP: Final[float] = 0.0

# 교체 후 최소 체류 시간 (초, 즉시 재교체 방지 — 리그 규정은 아니나 합리적 하한)
SUBSTITUTION_MIN_STAY_SEC: Final[float] = 20.0

# 벤치 영역 감지 좌표 범위 (코트 외부, 미터 — 코트 사이드라인 기준)
BENCH_AREA_DISTANCE_FROM_SIDELINE_M: Final[float] = 3.0


# =============================================================================
# 슛클락 관련 파라미터
# =============================================================================

# 슛클락 기본값 (초) — 모든 리그 공통
SHOT_CLOCK_FULL_SEC: Final[int] = 24

# 슛클락 리셋값 (공격 리바운드 후)
SHOT_CLOCK_RESET_OFFENSIVE_REBOUND: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 14,         # FIBA: 14초로 리셋
    RuleSet.NBA: 14,          # NBA: 14초로 리셋 (2018-19부터)
    RuleSet.KBL: 14,
    RuleSet.NBL: 14,
    RuleSet.EUROLEAGUE: 14,
}

# 슛클락 리셋값 (파울/바이올레이션 후 공격 유지 시)
SHOT_CLOCK_RESET_FOUL: Final[dict[RuleSet, int]] = {
    RuleSet.FIBA: 14,         # FIBA: 14초 또는 남은 시간 중 큰 값
    RuleSet.NBA: 14,          # NBA: 14초 또는 남은 시간 중 큰 값
    RuleSet.KBL: 14,
    RuleSet.NBL: 14,
    RuleSet.EUROLEAGUE: 14,
}


# =============================================================================
# 기록 무결성 검증 파라미터
# =============================================================================

# 최대 허용 스코어 차이 (기록 합산 vs 실제 스코어)
SCORE_INTEGRITY_MAX_DIFF: Final[int] = 0

# 리바운드 무결성 (총 리바운드 ≈ 총 미스샷, 허용 차이)
REBOUND_INTEGRITY_TOLERANCE: Final[int] = 3

# 출전 시간 합계 오차 허용 범위 (초)
PLAYING_TIME_TOLERANCE_SEC: Final[float] = 5.0


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 열거형
    "GameState",
    "BonusStatus",
    "TimeoutType",
    "RecordFormat",
    # 상태 전이
    "VALID_GAME_STATE_TRANSITIONS",
    # 타임아웃 규칙
    "TIMEOUTS_PER_TEAM",
    "TIMEOUT_DURATION_SEC",
    "FIBA_FIRST_HALF_MAX_TIMEOUTS",
    "FIBA_SECOND_HALF_MAX_TIMEOUTS",
    "NBA_OT_ADDITIONAL_TIMEOUTS",
    # 쿼터/경기 시간
    "QUARTER_DURATION_SEC",
    "OVERTIME_DURATION_SEC",
    "REGULAR_PERIODS",
    "HALFTIME_BREAK_SEC",
    "PERIOD_BREAK_SEC",
    # 파울 관리
    "TEAM_FOUL_BONUS_THRESHOLD",
    "NBA_DOUBLE_BONUS_THRESHOLD",
    "FOUL_TROUBLE_WARNING_OFFSET",
    "FOUL_OUT_RISK_THRESHOLD",
    # 교체 관리
    "MIN_PLAYING_TIME_FOR_DNP",
    "SUBSTITUTION_MIN_STAY_SEC",
    "BENCH_AREA_DISTANCE_FROM_SIDELINE_M",
    # 슛클락
    "SHOT_CLOCK_FULL_SEC",
    "SHOT_CLOCK_RESET_OFFENSIVE_REBOUND",
    "SHOT_CLOCK_RESET_FOUL",
    # 기록 무결성
    "SCORE_INTEGRITY_MAX_DIFF",
    "REBOUND_INTEGRITY_TOLERANCE",
    "PLAYING_TIME_TOLERANCE_SEC",
    # 유틸리티 함수
    "is_valid_game_transition",
    "get_bonus_status",
    "is_foul_trouble",
]


# =============================================================================
# 유틸리티 함수
# =============================================================================


def is_valid_game_transition(current: GameState, target: GameState) -> bool:
    """게임 상태 전이 유효성 검증.

    VALID_GAME_STATE_TRANSITIONS 딕셔너리 기반으로
    현재 상태에서 목표 상태로 전환 가능한지 확인한다.

    Args:
        current: 현재 게임 상태.
        target: 목표 게임 상태.

    Returns:
        전환 가능하면 True, 불가능하면 False.
    """
    allowed = VALID_GAME_STATE_TRANSITIONS.get(current, frozenset())
    return target in allowed


def get_bonus_status(
    team_fouls: int,
    rule_set: RuleSet = RuleSet.FIBA,
) -> BonusStatus:
    """팀 파울 수로 보너스 상태를 판정한다.

    Args:
        team_fouls: 해당 쿼터의 팀 파울 수.
        rule_set: 적용 규칙셋.

    Returns:
        BonusStatus (NONE / BONUS / DOUBLE_BONUS).
    """
    threshold = TEAM_FOUL_BONUS_THRESHOLD.get(rule_set, 4)

    # NBA 더블 보너스 체크
    if rule_set == RuleSet.NBA and team_fouls >= NBA_DOUBLE_BONUS_THRESHOLD:
        return BonusStatus.DOUBLE_BONUS

    if team_fouls > threshold:
        return BonusStatus.BONUS

    return BonusStatus.NONE


def is_foul_trouble(
    personal_fouls: int,
    rule_set: RuleSet = RuleSet.FIBA,
) -> bool:
    """선수가 파울 트러블 상태인지 판별한다.

    퇴장 기준에서 FOUL_TROUBLE_WARNING_OFFSET 이내이면 트러블.

    Args:
        personal_fouls: 해당 선수의 개인 파울 수.
        rule_set: 적용 규칙셋.

    Returns:
        파울 트러블이면 True.
    """
    foul_out_limit = rule_set.max_personal_fouls
    return personal_fouls >= (foul_out_limit - FOUL_TROUBLE_WARNING_OFFSET)


# 모듈 버전 정보
__version__ = "1.0.0"
