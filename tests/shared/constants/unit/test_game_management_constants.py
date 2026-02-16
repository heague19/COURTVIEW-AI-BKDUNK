# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_game_management_constants.py

경기 관리(기록원 대체) 도메인 상수 모듈 단위 테스트

테스트 항목:
  [A] GameState Enum 기본 (9멤버, str 값, str/Enum 상속)
  [B] GameState.is_clock_running / is_game_active 프로퍼티
  [C] GameState.get_name() i18n (5개 언어)
  [D] BonusStatus Enum 기본 (3멤버, str 값)
  [E] BonusStatus.grants_free_throws 프로퍼티
  [F] BonusStatus.get_name() i18n (5개 언어)
  [G] TimeoutType Enum 기본 (3멤버, str 값)
  [H] TimeoutType.get_name() i18n (5개 언어)
  [I] RecordFormat Enum 기본 (6멤버, str 값)
  [J] VALID_GAME_STATE_TRANSITIONS 완전성 및 정확성
  [K] 리그별 딕셔너리 (8개) 키 커버리지 (5 RuleSet)
  [L] 타임아웃 규칙 상수 값 검증
  [M] 쿼터/경기 시간 상수 값 검증
  [N] 파울 관리 상수 값 검증
  [O] 교체 관리 상수 값 검증
  [P] 슛클락 상수 값 검증
  [Q] 기록 무결성 상수 값 검증
  [R] is_valid_game_transition 유틸리티 함수
  [S] get_bonus_status 유틸리티 함수
  [T] is_foul_trouble 유틸리티 함수
  [U] get_total_game_time_sec 유틸리티 함수
  [V] __all__ Export 목록 (31항목)

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from enum import Enum
from pathlib import Path

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (parents[4]: unit -> constants -> shared -> tests -> PROJECT_ROOT)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants.localization import SupportedLanguage
from shared.constants.referee_rule_constants import RuleSet
from shared.constants import game_management_constants
from shared.constants.game_management_constants import (
    # 열거형 (4종)
    GameState,
    BonusStatus,
    TimeoutType,
    RecordFormat,
    # 상태 전이
    VALID_GAME_STATE_TRANSITIONS,
    # 타임아웃 규칙
    TIMEOUTS_PER_TEAM,
    TIMEOUT_DURATION_SEC,
    FIBA_FIRST_HALF_MAX_TIMEOUTS,
    FIBA_SECOND_HALF_MAX_TIMEOUTS,
    NBA_OT_ADDITIONAL_TIMEOUTS,
    # 쿼터/경기 시간
    QUARTER_DURATION_SEC,
    OVERTIME_DURATION_SEC,
    REGULAR_PERIODS,
    HALFTIME_BREAK_SEC,
    PERIOD_BREAK_SEC,
    # 파울 관리
    TEAM_FOUL_BONUS_THRESHOLD,
    NBA_DOUBLE_BONUS_THRESHOLD,
    FOUL_TROUBLE_WARNING_OFFSET,
    FOUL_OUT_RISK_THRESHOLD,
    # 교체 관리
    MIN_PLAYING_TIME_FOR_DNP,
    SUBSTITUTION_MIN_STAY_SEC,
    BENCH_AREA_DISTANCE_FROM_SIDELINE_M,
    # 슛클락
    SHOT_CLOCK_FULL_SEC,
    SHOT_CLOCK_RESET_OFFENSIVE_REBOUND,
    SHOT_CLOCK_RESET_FOUL,
    # 기록 무결성
    SCORE_INTEGRITY_MAX_DIFF,
    REBOUND_INTEGRITY_TOLERANCE,
    PLAYING_TIME_TOLERANCE_SEC,
    # 유틸리티 함수
    is_valid_game_transition,
    get_bonus_status,
    is_foul_trouble,
    get_total_game_time_sec,
)


# =============================================================================
# 테스트 결과 추적기
# =============================================================================
class TestResult:
    """테스트 결과 집계 및 출력 유틸리티."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, detail)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# =============================================================================
# [A] GameState Enum 기본 (9멤버, str 값, str/Enum 상속)
# =============================================================================
def test_a_game_state_basics(r: TestResult) -> None:
    """GameState Enum 기본 속성 검증."""
    print("\n[A] GameState 기본 (9멤버, str 값)")
    print("-" * 50)

    members = list(GameState)
    r.check("GameState 멤버 수 = 9", len(members) == 9, f"실제: {len(members)}")

    expected_members = {
        "PRE_GAME": "pre_game", "TIP_OFF": "tip_off", "LIVE": "live",
        "DEAD_BALL": "dead_ball", "TIMEOUT": "timeout",
        "PERIOD_BREAK": "period_break", "HALFTIME": "halftime",
        "OVERTIME": "overtime", "FINAL": "final",
    }

    for name, value in expected_members.items():
        member = GameState[name]
        r.check(f"GameState.{name} == '{value}'",
                member.value == value,
                f"expected='{value}', actual='{member.value}'")

    # str 상속 검증
    r.check("GameState은 str 상속", issubclass(GameState, str),
            f"MRO: {GameState.__mro__}")
    r.check("GameState은 Enum 상속", issubclass(GameState, Enum),
            f"MRO: {GameState.__mro__}")

    # 문자열 비교 가능 검증
    r.check("GameState.LIVE == 'live' (str 비교)",
            GameState.LIVE == "live", "str mixin 동작 실패")

    # str() 변환 검증
    r.check("str(GameState.FINAL) == 'final'",
            str(GameState.FINAL) == "final",
            f"실제: {str(GameState.FINAL)}")


# =============================================================================
# [B] GameState.is_clock_running / is_game_active 프로퍼티
# =============================================================================
def test_b_game_state_properties(r: TestResult) -> None:
    """GameState 프로퍼티 검증."""
    print("\n[B] GameState is_clock_running / is_game_active")
    print("-" * 50)

    # is_clock_running: LIVE만 True
    for gs in GameState:
        expected = (gs == GameState.LIVE)
        r.check(f"is_clock_running({gs.name}) = {expected}",
                gs.is_clock_running == expected,
                f"실제: {gs.is_clock_running}")

    # is_game_active: PRE_GAME, FINAL만 False
    inactive_states = {GameState.PRE_GAME, GameState.FINAL}
    for gs in GameState:
        expected = gs not in inactive_states
        r.check(f"is_game_active({gs.name}) = {expected}",
                gs.is_game_active == expected,
                f"실제: {gs.is_game_active}")


# =============================================================================
# [C] GameState.get_name() i18n (5개 언어)
# =============================================================================
def test_c_game_state_i18n(r: TestResult) -> None:
    """GameState i18n 다국어 이름 검증."""
    print("\n[C] GameState i18n (5개 언어)")
    print("-" * 50)

    all_langs = list(SupportedLanguage)
    r.check("SupportedLanguage 5개 언어 존재", len(all_langs) == 5,
            f"실제: {len(all_langs)}")

    for gs in GameState:
        for lang in all_langs:
            name_val = gs.get_name(lang)
            r.check(f"GameState.{gs.name}.get_name({lang.name}) 존재",
                    isinstance(name_val, str) and len(name_val) > 0,
                    f"실제: {name_val!r}")

    # 특정 값 검증
    r.check("GameState.LIVE KO = '진행 중'",
            GameState.LIVE.get_name(SupportedLanguage.KO) == "진행 중")
    r.check("GameState.LIVE EN = 'Live'",
            GameState.LIVE.get_name(SupportedLanguage.EN) == "Live")
    r.check("GameState.FINAL KO = '경기 종료'",
            GameState.FINAL.get_name(SupportedLanguage.KO) == "경기 종료")
    r.check("GameState.HALFTIME EN = 'Halftime'",
            GameState.HALFTIME.get_name(SupportedLanguage.EN) == "Halftime")


# =============================================================================
# [D] BonusStatus Enum 기본 (3멤버, str 값)
# =============================================================================
def test_d_bonus_status_basics(r: TestResult) -> None:
    """BonusStatus Enum 기본 속성 검증."""
    print("\n[D] BonusStatus 기본 (3멤버)")
    print("-" * 50)

    members = list(BonusStatus)
    r.check("BonusStatus 멤버 수 = 3", len(members) == 3, f"실제: {len(members)}")

    expected = {"NONE": "none", "BONUS": "bonus", "DOUBLE_BONUS": "double_bonus"}
    for name, value in expected.items():
        r.check(f"BonusStatus.{name} == '{value}'",
                BonusStatus[name].value == value,
                f"실제: {BonusStatus[name].value}")

    r.check("BonusStatus은 str 상속", issubclass(BonusStatus, str))
    r.check("BonusStatus은 Enum 상속", issubclass(BonusStatus, Enum))
    r.check("BonusStatus.NONE == 'none' (str 비교)",
            BonusStatus.NONE == "none")


# =============================================================================
# [E] BonusStatus.grants_free_throws 프로퍼티
# =============================================================================
def test_e_bonus_status_grants_free_throws(r: TestResult) -> None:
    """BonusStatus grants_free_throws 프로퍼티 검증."""
    print("\n[E] BonusStatus grants_free_throws")
    print("-" * 50)

    r.check("NONE: grants_free_throws = False",
            not BonusStatus.NONE.grants_free_throws)
    r.check("BONUS: grants_free_throws = True",
            BonusStatus.BONUS.grants_free_throws)
    r.check("DOUBLE_BONUS: grants_free_throws = True",
            BonusStatus.DOUBLE_BONUS.grants_free_throws)

    # 자유투 부여 멤버 수 = 2
    granting = [bs for bs in BonusStatus if bs.grants_free_throws]
    r.check("자유투 부여 멤버 수 = 2", len(granting) == 2,
            f"실제: {len(granting)}")


# =============================================================================
# [F] BonusStatus.get_name() i18n (5개 언어)
# =============================================================================
def test_f_bonus_status_i18n(r: TestResult) -> None:
    """BonusStatus i18n 다국어 이름 검증."""
    print("\n[F] BonusStatus i18n (5개 언어)")
    print("-" * 50)

    all_langs = list(SupportedLanguage)
    for bs in BonusStatus:
        for lang in all_langs:
            name_val = bs.get_name(lang)
            r.check(f"BonusStatus.{bs.name}.get_name({lang.name}) 존재",
                    isinstance(name_val, str) and len(name_val) > 0,
                    f"실제: {name_val!r}")

    # 특정 값 검증
    r.check("BonusStatus.NONE KO = '보너스 없음'",
            BonusStatus.NONE.get_name(SupportedLanguage.KO) == "보너스 없음")
    r.check("BonusStatus.BONUS EN = 'Bonus'",
            BonusStatus.BONUS.get_name(SupportedLanguage.EN) == "Bonus")
    r.check("BonusStatus.DOUBLE_BONUS EN = 'Double Bonus'",
            BonusStatus.DOUBLE_BONUS.get_name(SupportedLanguage.EN) == "Double Bonus")


# =============================================================================
# [G] TimeoutType Enum 기본 (3멤버, str 값)
# =============================================================================
def test_g_timeout_type_basics(r: TestResult) -> None:
    """TimeoutType Enum 기본 속성 검증."""
    print("\n[G] TimeoutType 기본 (3멤버)")
    print("-" * 50)

    members = list(TimeoutType)
    r.check("TimeoutType 멤버 수 = 3", len(members) == 3, f"실제: {len(members)}")

    expected = {"FULL": "full", "TWENTY_SECOND": "twenty_second", "OFFICIAL": "official"}
    for name, value in expected.items():
        r.check(f"TimeoutType.{name} == '{value}'",
                TimeoutType[name].value == value,
                f"실제: {TimeoutType[name].value}")

    r.check("TimeoutType은 str 상속", issubclass(TimeoutType, str))
    r.check("str(TimeoutType.FULL) == 'full'",
            str(TimeoutType.FULL) == "full")


# =============================================================================
# [H] TimeoutType.get_name() i18n (5개 언어)
# =============================================================================
def test_h_timeout_type_i18n(r: TestResult) -> None:
    """TimeoutType i18n 다국어 이름 검증."""
    print("\n[H] TimeoutType i18n (5개 언어)")
    print("-" * 50)

    all_langs = list(SupportedLanguage)
    for tt in TimeoutType:
        for lang in all_langs:
            name_val = tt.get_name(lang)
            r.check(f"TimeoutType.{tt.name}.get_name({lang.name}) 존재",
                    isinstance(name_val, str) and len(name_val) > 0,
                    f"실제: {name_val!r}")

    # 특정 값 검증
    r.check("TimeoutType.FULL KO = '풀 타임아웃'",
            TimeoutType.FULL.get_name(SupportedLanguage.KO) == "풀 타임아웃")
    r.check("TimeoutType.TWENTY_SECOND EN = '20-second Timeout'",
            TimeoutType.TWENTY_SECOND.get_name(SupportedLanguage.EN) == "20-second Timeout")
    r.check("TimeoutType.OFFICIAL EN = 'Official Timeout'",
            TimeoutType.OFFICIAL.get_name(SupportedLanguage.EN) == "Official Timeout")


# =============================================================================
# [I] RecordFormat Enum 기본 (6멤버, str 값)
# =============================================================================
def test_i_record_format_basics(r: TestResult) -> None:
    """RecordFormat Enum 기본 속성 검증."""
    print("\n[I] RecordFormat 기본 (6멤버)")
    print("-" * 50)

    members = list(RecordFormat)
    r.check("RecordFormat 멤버 수 = 6", len(members) == 6, f"실제: {len(members)}")

    expected = {
        "FIBA_BOXSCORE": "fiba_boxscore", "NBA_BOXSCORE": "nba_boxscore",
        "KBL_BOXSCORE": "kbl_boxscore", "NBL_BOXSCORE": "nbl_boxscore",
        "JSON_FEED": "json_feed", "XML_FEED": "xml_feed",
    }
    for name, value in expected.items():
        r.check(f"RecordFormat.{name} == '{value}'",
                RecordFormat[name].value == value,
                f"실제: {RecordFormat[name].value}")

    r.check("RecordFormat은 str 상속", issubclass(RecordFormat, str))
    r.check("RecordFormat은 Enum 상속", issubclass(RecordFormat, Enum))

    # hashable 검증
    rf_set = set(RecordFormat)
    r.check("RecordFormat hashable (set 사용 가능)",
            len(rf_set) == 6, f"실제: {len(rf_set)}")

    # identity 검증
    r.check("RecordFormat.JSON_FEED is RecordFormat.JSON_FEED",
            RecordFormat.JSON_FEED is RecordFormat.JSON_FEED)


# =============================================================================
# [J] VALID_GAME_STATE_TRANSITIONS 완전성 및 정확성
# =============================================================================
def test_j_state_transitions(r: TestResult) -> None:
    """VALID_GAME_STATE_TRANSITIONS 상태 전이 맵 검증."""
    print("\n[J] VALID_GAME_STATE_TRANSITIONS")
    print("-" * 50)

    # 모든 GameState가 키로 존재
    all_states = set(GameState)
    r.check("전이 맵 키 = 9 (모든 GameState)",
            set(VALID_GAME_STATE_TRANSITIONS.keys()) == all_states)

    # 모든 값이 frozenset
    r.check("모든 값이 frozenset",
            all(isinstance(v, frozenset) for v in VALID_GAME_STATE_TRANSITIONS.values()))

    # 개별 전이 검증
    transitions = {
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
        GameState.FINAL: frozenset(),
    }

    for state, expected_targets in transitions.items():
        actual = VALID_GAME_STATE_TRANSITIONS[state]
        r.check(f"전이 {state.name} -> {set(t.name for t in expected_targets)}",
                actual == expected_targets,
                f"실제: {set(t.name for t in actual)}")

    # 전이 대상이 모두 유효한 GameState
    all_targets = set()
    for targets in VALID_GAME_STATE_TRANSITIONS.values():
        all_targets.update(targets)
    r.check("모든 전이 대상이 유효한 GameState",
            all_targets.issubset(all_states))

    # FINAL에서 나가는 전이 없음
    r.check("FINAL 종료 상태 (전이 0개)",
            len(VALID_GAME_STATE_TRANSITIONS[GameState.FINAL]) == 0)


# =============================================================================
# [K] 리그별 딕셔너리 (8개) 키 커버리지 (5 RuleSet)
# =============================================================================
def test_k_league_dict_keys(r: TestResult) -> None:
    """리그별 딕셔너리 키 검증 (5개 RuleSet)."""
    print("\n[K] 리그별 딕셔너리 키 커버리지")
    print("-" * 50)

    expected_keys = {RuleSet.FIBA, RuleSet.NBA, RuleSet.KBL, RuleSet.NBL, RuleSet.EUROLEAGUE}

    league_dicts = {
        "TIMEOUTS_PER_TEAM": TIMEOUTS_PER_TEAM,
        "TIMEOUT_DURATION_SEC": TIMEOUT_DURATION_SEC,
        "QUARTER_DURATION_SEC": QUARTER_DURATION_SEC,
        "HALFTIME_BREAK_SEC": HALFTIME_BREAK_SEC,
        "PERIOD_BREAK_SEC": PERIOD_BREAK_SEC,
        "TEAM_FOUL_BONUS_THRESHOLD": TEAM_FOUL_BONUS_THRESHOLD,
        "SHOT_CLOCK_RESET_OFFENSIVE_REBOUND": SHOT_CLOCK_RESET_OFFENSIVE_REBOUND,
        "SHOT_CLOCK_RESET_FOUL": SHOT_CLOCK_RESET_FOUL,
    }

    for dict_name, d in league_dicts.items():
        actual_keys = set(d.keys())
        r.check(f"{dict_name}: 5개 RuleSet 키 보유",
                actual_keys == expected_keys,
                f"누락: {expected_keys - actual_keys}")

    # 모든 값이 int 타입
    for dict_name, d in league_dicts.items():
        all_int = all(isinstance(v, int) for v in d.values())
        r.check(f"{dict_name}: 모든 값이 int", all_int)


# =============================================================================
# [L] 타임아웃 규칙 상수 값 검증
# =============================================================================
def test_l_timeout_rules(r: TestResult) -> None:
    """타임아웃 규칙 상수 값 검증."""
    print("\n[L] 타임아웃 규칙 상수 값")
    print("-" * 50)

    # 타임아웃 수
    r.check("FIBA 타임아웃 수 = 5", TIMEOUTS_PER_TEAM[RuleSet.FIBA] == 5)
    r.check("NBA 타임아웃 수 = 7", TIMEOUTS_PER_TEAM[RuleSet.NBA] == 7)
    r.check("KBL 타임아웃 수 = 5", TIMEOUTS_PER_TEAM[RuleSet.KBL] == 5)

    # 타임아웃 시간
    r.check("FIBA 타임아웃 60초", TIMEOUT_DURATION_SEC[RuleSet.FIBA] == 60)
    r.check("NBA 타임아웃 75초", TIMEOUT_DURATION_SEC[RuleSet.NBA] == 75)

    # FIBA 전반/후반 타임아웃 제한
    r.check("FIBA 전반 최대 타임아웃 = 2",
            FIBA_FIRST_HALF_MAX_TIMEOUTS == 2)
    r.check("FIBA 후반 최대 타임아웃 = 3",
            FIBA_SECOND_HALF_MAX_TIMEOUTS == 3)
    r.check("FIBA 전반+후반 = 5",
            FIBA_FIRST_HALF_MAX_TIMEOUTS + FIBA_SECOND_HALF_MAX_TIMEOUTS == 5)

    # NBA OT 추가 타임아웃
    r.check("NBA OT 추가 타임아웃 = 2", NBA_OT_ADDITIONAL_TIMEOUTS == 2)

    # 타입 검증
    r.check("FIBA_FIRST_HALF_MAX_TIMEOUTS int 타입",
            isinstance(FIBA_FIRST_HALF_MAX_TIMEOUTS, int))
    r.check("NBA_OT_ADDITIONAL_TIMEOUTS int 타입",
            isinstance(NBA_OT_ADDITIONAL_TIMEOUTS, int))


# =============================================================================
# [M] 쿼터/경기 시간 상수 값 검증
# =============================================================================
def test_m_quarter_time(r: TestResult) -> None:
    """쿼터/경기 시간 상수 값 검증."""
    print("\n[M] 쿼터/경기 시간 상수")
    print("-" * 50)

    # 쿼터 시간
    r.check("FIBA 쿼터 = 600초 (10분)", QUARTER_DURATION_SEC[RuleSet.FIBA] == 600)
    r.check("NBA 쿼터 = 720초 (12분)", QUARTER_DURATION_SEC[RuleSet.NBA] == 720)
    r.check("KBL 쿼터 = 600초", QUARTER_DURATION_SEC[RuleSet.KBL] == 600)
    r.check("NBL 쿼터 = 600초", QUARTER_DURATION_SEC[RuleSet.NBL] == 600)
    r.check("EUROLEAGUE 쿼터 = 600초", QUARTER_DURATION_SEC[RuleSet.EUROLEAGUE] == 600)

    # 연장전 시간 (공통)
    r.check("연장전 시간 = 300초 (5분)", OVERTIME_DURATION_SEC == 300)
    r.check("OVERTIME_DURATION_SEC int 타입", isinstance(OVERTIME_DURATION_SEC, int))

    # 정규 쿼터 수
    r.check("정규 쿼터 수 = 4", REGULAR_PERIODS == 4)

    # 하프타임 휴식
    r.check("FIBA 하프타임 = 900초 (15분)", HALFTIME_BREAK_SEC[RuleSet.FIBA] == 900)
    r.check("NBA 하프타임 = 900초 (15분)", HALFTIME_BREAK_SEC[RuleSet.NBA] == 900)

    # 쿼터 간 휴식
    r.check("FIBA 쿼터간 휴식 = 120초 (2분)", PERIOD_BREAK_SEC[RuleSet.FIBA] == 120)
    r.check("NBA 쿼터간 휴식 = 130초 (2분 10초)", PERIOD_BREAK_SEC[RuleSet.NBA] == 130)


# =============================================================================
# [N] 파울 관리 상수 값 검증
# =============================================================================
def test_n_foul_management(r: TestResult) -> None:
    """파울 관리 상수 값 검증."""
    print("\n[N] 파울 관리 상수")
    print("-" * 50)

    # 보너스 전환 임계값
    r.check("FIBA 보너스 임계값 = 4", TEAM_FOUL_BONUS_THRESHOLD[RuleSet.FIBA] == 4)
    r.check("NBA 보너스 임계값 = 4", TEAM_FOUL_BONUS_THRESHOLD[RuleSet.NBA] == 4)

    # NBA 더블보너스 임계값
    r.check("NBA 더블보너스 임계값 = 10", NBA_DOUBLE_BONUS_THRESHOLD == 10)
    r.check("NBA_DOUBLE_BONUS_THRESHOLD int 타입",
            isinstance(NBA_DOUBLE_BONUS_THRESHOLD, int))

    # 파울 트러블 경고 오프셋
    r.check("파울 트러블 경고 오프셋 = 1", FOUL_TROUBLE_WARNING_OFFSET == 1)

    # 파울아웃 리스크 임계치
    r.check("파울아웃 리스크 임계치 = 1.2", FOUL_OUT_RISK_THRESHOLD == 1.2)
    r.check("FOUL_OUT_RISK_THRESHOLD float 타입",
            isinstance(FOUL_OUT_RISK_THRESHOLD, float))

    # 모든 리그 보너스 임계값이 양의 정수
    for rs in RuleSet:
        val = TEAM_FOUL_BONUS_THRESHOLD[rs]
        r.check(f"{rs.name} 보너스 임계값 > 0",
                isinstance(val, int) and val > 0,
                f"실제: {val}")


# =============================================================================
# [O] 교체 관리 상수 값 검증
# =============================================================================
def test_o_substitution(r: TestResult) -> None:
    """교체 관리 상수 값 검증."""
    print("\n[O] 교체 관리 상수")
    print("-" * 50)

    r.check("MIN_PLAYING_TIME_FOR_DNP = 0.0", MIN_PLAYING_TIME_FOR_DNP == 0.0)
    r.check("MIN_PLAYING_TIME_FOR_DNP float 타입",
            isinstance(MIN_PLAYING_TIME_FOR_DNP, float))

    r.check("SUBSTITUTION_MIN_STAY_SEC = 20.0", SUBSTITUTION_MIN_STAY_SEC == 20.0)
    r.check("SUBSTITUTION_MIN_STAY_SEC float 타입",
            isinstance(SUBSTITUTION_MIN_STAY_SEC, float))
    r.check("SUBSTITUTION_MIN_STAY_SEC > 0", SUBSTITUTION_MIN_STAY_SEC > 0)

    r.check("BENCH_AREA_DISTANCE_FROM_SIDELINE_M = 3.0",
            BENCH_AREA_DISTANCE_FROM_SIDELINE_M == 3.0)
    r.check("BENCH_AREA_DISTANCE_FROM_SIDELINE_M float 타입",
            isinstance(BENCH_AREA_DISTANCE_FROM_SIDELINE_M, float))
    r.check("BENCH_AREA_DISTANCE_FROM_SIDELINE_M > 0",
            BENCH_AREA_DISTANCE_FROM_SIDELINE_M > 0)


# =============================================================================
# [P] 슛클락 상수 값 검증
# =============================================================================
def test_p_shot_clock(r: TestResult) -> None:
    """슛클락 상수 값 검증."""
    print("\n[P] 슛클락 상수")
    print("-" * 50)

    r.check("SHOT_CLOCK_FULL_SEC = 24", SHOT_CLOCK_FULL_SEC == 24)
    r.check("SHOT_CLOCK_FULL_SEC int 타입", isinstance(SHOT_CLOCK_FULL_SEC, int))

    # 공격 리바운드 후 리셋값 (모든 리그 14초)
    for rs in RuleSet:
        val = SHOT_CLOCK_RESET_OFFENSIVE_REBOUND[rs]
        r.check(f"{rs.name} 공격리바운드 리셋 = 14초", val == 14,
                f"실제: {val}")

    # 파울 후 리셋값 (모든 리그 14초)
    for rs in RuleSet:
        val = SHOT_CLOCK_RESET_FOUL[rs]
        r.check(f"{rs.name} 파울 후 리셋 = 14초", val == 14,
                f"실제: {val}")

    # 리셋값 < 기본값
    for rs in RuleSet:
        r.check(f"{rs.name} 리셋값 < 기본값",
                SHOT_CLOCK_RESET_OFFENSIVE_REBOUND[rs] < SHOT_CLOCK_FULL_SEC)


# =============================================================================
# [Q] 기록 무결성 상수 값 검증
# =============================================================================
def test_q_record_integrity(r: TestResult) -> None:
    """기록 무결성 상수 값 검증."""
    print("\n[Q] 기록 무결성 상수")
    print("-" * 50)

    r.check("SCORE_INTEGRITY_MAX_DIFF = 0", SCORE_INTEGRITY_MAX_DIFF == 0)
    r.check("SCORE_INTEGRITY_MAX_DIFF int 타입",
            isinstance(SCORE_INTEGRITY_MAX_DIFF, int))

    r.check("REBOUND_INTEGRITY_TOLERANCE = 3", REBOUND_INTEGRITY_TOLERANCE == 3)
    r.check("REBOUND_INTEGRITY_TOLERANCE int 타입",
            isinstance(REBOUND_INTEGRITY_TOLERANCE, int))
    r.check("REBOUND_INTEGRITY_TOLERANCE >= 0", REBOUND_INTEGRITY_TOLERANCE >= 0)

    r.check("PLAYING_TIME_TOLERANCE_SEC = 5.0", PLAYING_TIME_TOLERANCE_SEC == 5.0)
    r.check("PLAYING_TIME_TOLERANCE_SEC float 타입",
            isinstance(PLAYING_TIME_TOLERANCE_SEC, float))
    r.check("PLAYING_TIME_TOLERANCE_SEC >= 0", PLAYING_TIME_TOLERANCE_SEC >= 0)


# =============================================================================
# [R] is_valid_game_transition 유틸리티 함수
# =============================================================================
def test_r_is_valid_game_transition(r: TestResult) -> None:
    """is_valid_game_transition 함수 검증."""
    print("\n[R] is_valid_game_transition 유틸리티 함수")
    print("-" * 50)

    # 유효한 전이
    valid_transitions = [
        (GameState.PRE_GAME, GameState.TIP_OFF),
        (GameState.TIP_OFF, GameState.LIVE),
        (GameState.LIVE, GameState.DEAD_BALL),
        (GameState.LIVE, GameState.TIMEOUT),
        (GameState.LIVE, GameState.PERIOD_BREAK),
        (GameState.LIVE, GameState.FINAL),
        (GameState.DEAD_BALL, GameState.LIVE),
        (GameState.DEAD_BALL, GameState.TIMEOUT),
        (GameState.DEAD_BALL, GameState.PERIOD_BREAK),
        (GameState.DEAD_BALL, GameState.FINAL),
        (GameState.TIMEOUT, GameState.LIVE),
        (GameState.TIMEOUT, GameState.DEAD_BALL),
        (GameState.PERIOD_BREAK, GameState.LIVE),
        (GameState.PERIOD_BREAK, GameState.HALFTIME),
        (GameState.PERIOD_BREAK, GameState.OVERTIME),
        (GameState.HALFTIME, GameState.LIVE),
        (GameState.OVERTIME, GameState.LIVE),
    ]

    for current, target in valid_transitions:
        r.check(f"{current.name} -> {target.name} = True",
                is_valid_game_transition(current, target))

    # 무효한 전이
    invalid_transitions = [
        (GameState.PRE_GAME, GameState.LIVE),
        (GameState.PRE_GAME, GameState.FINAL),
        (GameState.FINAL, GameState.LIVE),
        (GameState.FINAL, GameState.PRE_GAME),
        (GameState.LIVE, GameState.PRE_GAME),
        (GameState.TIP_OFF, GameState.TIMEOUT),
        (GameState.HALFTIME, GameState.FINAL),
        (GameState.OVERTIME, GameState.FINAL),
    ]

    for current, target in invalid_transitions:
        r.check(f"{current.name} -> {target.name} = False",
                not is_valid_game_transition(current, target))

    # 자기 자신으로의 전이 (모든 상태에서 불가)
    for gs in GameState:
        r.check(f"{gs.name} -> {gs.name} (자기 전이) = False",
                not is_valid_game_transition(gs, gs))


# =============================================================================
# [S] get_bonus_status 유틸리티 함수
# =============================================================================
def test_s_get_bonus_status(r: TestResult) -> None:
    """get_bonus_status 함수 검증."""
    print("\n[S] get_bonus_status 유틸리티 함수")
    print("-" * 50)

    # FIBA 계열 (임계값 4, 더블보너스 없음)
    for rs in [RuleSet.FIBA, RuleSet.KBL, RuleSet.NBL, RuleSet.EUROLEAGUE]:
        r.check(f"{rs.name} 파울 0 -> NONE",
                get_bonus_status(0, rs) == BonusStatus.NONE)
        r.check(f"{rs.name} 파울 4 -> NONE",
                get_bonus_status(4, rs) == BonusStatus.NONE)
        r.check(f"{rs.name} 파울 5 -> BONUS",
                get_bonus_status(5, rs) == BonusStatus.BONUS)
        r.check(f"{rs.name} 파울 10 -> BONUS (더블보너스 없음)",
                get_bonus_status(10, rs) == BonusStatus.BONUS)

    # NBA (임계값 4, 10번째부터 더블보너스)
    r.check("NBA 파울 0 -> NONE",
            get_bonus_status(0, RuleSet.NBA) == BonusStatus.NONE)
    r.check("NBA 파울 4 -> NONE",
            get_bonus_status(4, RuleSet.NBA) == BonusStatus.NONE)
    r.check("NBA 파울 5 -> BONUS",
            get_bonus_status(5, RuleSet.NBA) == BonusStatus.BONUS)
    r.check("NBA 파울 9 -> BONUS",
            get_bonus_status(9, RuleSet.NBA) == BonusStatus.BONUS)
    r.check("NBA 파울 10 -> DOUBLE_BONUS",
            get_bonus_status(10, RuleSet.NBA) == BonusStatus.DOUBLE_BONUS)
    r.check("NBA 파울 15 -> DOUBLE_BONUS",
            get_bonus_status(15, RuleSet.NBA) == BonusStatus.DOUBLE_BONUS)


# =============================================================================
# [T] is_foul_trouble 유틸리티 함수
# =============================================================================
def test_t_is_foul_trouble(r: TestResult) -> None:
    """is_foul_trouble 함수 검증."""
    print("\n[T] is_foul_trouble 유틸리티 함수")
    print("-" * 50)

    # FIBA: max_personal_fouls=5, 오프셋 1 -> 4개부터 트러블
    for fouls in range(0, 4):
        r.check(f"FIBA 파울 {fouls} -> False",
                not is_foul_trouble(fouls, RuleSet.FIBA))
    r.check("FIBA 파울 4 -> True (5-1=4)",
            is_foul_trouble(4, RuleSet.FIBA))
    r.check("FIBA 파울 5 -> True",
            is_foul_trouble(5, RuleSet.FIBA))

    # NBA: max_personal_fouls=6, 오프셋 1 -> 5개부터 트러블
    for fouls in range(0, 5):
        r.check(f"NBA 파울 {fouls} -> False",
                not is_foul_trouble(fouls, RuleSet.NBA))
    r.check("NBA 파울 5 -> True (6-1=5)",
            is_foul_trouble(5, RuleSet.NBA))
    r.check("NBA 파울 6 -> True",
            is_foul_trouble(6, RuleSet.NBA))

    # KBL (FIBA 준용)
    r.check("KBL 파울 3 -> False", not is_foul_trouble(3, RuleSet.KBL))
    r.check("KBL 파울 4 -> True", is_foul_trouble(4, RuleSet.KBL))


# =============================================================================
# [U] get_total_game_time_sec 유틸리티 함수
# =============================================================================
def test_u_get_total_game_time_sec(r: TestResult) -> None:
    """get_total_game_time_sec 함수 검증."""
    print("\n[U] get_total_game_time_sec 유틸리티 함수")
    print("-" * 50)

    expected_times = {
        RuleSet.FIBA: 2400,       # 600 * 4 = 2400초 (40분)
        RuleSet.NBA: 2880,        # 720 * 4 = 2880초 (48분)
        RuleSet.KBL: 2400,
        RuleSet.NBL: 2400,
        RuleSet.EUROLEAGUE: 2400,
    }

    for rs, expected_sec in expected_times.items():
        actual = get_total_game_time_sec(rs)
        r.check(f"{rs.name} 총 경기 시간 = {expected_sec}초",
                actual == expected_sec,
                f"실제: {actual}")

    # 반환값 타입 검증
    r.check("반환값 int 타입",
            isinstance(get_total_game_time_sec(RuleSet.FIBA), int))

    # QUARTER_DURATION_SEC * REGULAR_PERIODS 공식 검증
    for rs in RuleSet:
        expected = QUARTER_DURATION_SEC[rs] * REGULAR_PERIODS
        r.check(f"{rs.name} 공식 일치 (쿼터시간*4)",
                get_total_game_time_sec(rs) == expected)


# =============================================================================
# [V] __all__ Export 목록 (31항목)
# =============================================================================
def test_v_all_exports(r: TestResult) -> None:
    """__all__ Export 목록 검증."""
    print("\n[V] __all__ Export 목록")
    print("-" * 50)

    expected_exports = {
        "__version__",
        "GameState", "BonusStatus", "TimeoutType", "RecordFormat",
        "VALID_GAME_STATE_TRANSITIONS",
        "TIMEOUTS_PER_TEAM", "TIMEOUT_DURATION_SEC",
        "FIBA_FIRST_HALF_MAX_TIMEOUTS", "FIBA_SECOND_HALF_MAX_TIMEOUTS",
        "NBA_OT_ADDITIONAL_TIMEOUTS",
        "QUARTER_DURATION_SEC", "OVERTIME_DURATION_SEC",
        "REGULAR_PERIODS", "HALFTIME_BREAK_SEC", "PERIOD_BREAK_SEC",
        "TEAM_FOUL_BONUS_THRESHOLD", "NBA_DOUBLE_BONUS_THRESHOLD",
        "FOUL_TROUBLE_WARNING_OFFSET", "FOUL_OUT_RISK_THRESHOLD",
        "MIN_PLAYING_TIME_FOR_DNP", "SUBSTITUTION_MIN_STAY_SEC",
        "BENCH_AREA_DISTANCE_FROM_SIDELINE_M",
        "SHOT_CLOCK_FULL_SEC", "SHOT_CLOCK_RESET_OFFENSIVE_REBOUND",
        "SHOT_CLOCK_RESET_FOUL",
        "SCORE_INTEGRITY_MAX_DIFF", "REBOUND_INTEGRITY_TOLERANCE",
        "PLAYING_TIME_TOLERANCE_SEC",
        "is_valid_game_transition", "get_bonus_status",
        "is_foul_trouble", "get_total_game_time_sec",
    }

    r.check("__all__ 속성 존재", hasattr(game_management_constants, "__all__"))

    actual_all = set(game_management_constants.__all__)
    r.check(f"__all__ 항목 수 = {len(expected_exports)}",
            len(actual_all) == len(expected_exports),
            f"실제: {len(actual_all)}")

    missing = expected_exports - actual_all
    extra = actual_all - expected_exports
    r.check("__all__ 누락 항목 없음", len(missing) == 0,
            f"누락: {missing}")
    r.check("__all__ 초과 항목 없음", len(extra) == 0,
            f"초과: {extra}")

    # __all__ 각 항목이 실제 모듈에 존재
    for name in game_management_constants.__all__:
        r.check(f"'{name}' 모듈에 실제 존재",
                hasattr(game_management_constants, name))

    # __version__ 검증
    r.check("__version__ = '1.0.0'",
            game_management_constants.__version__ == "1.0.0",
            f"실제: {game_management_constants.__version__}")


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    print("=" * 60)
    print("game_management_constants.py 유닛 테스트")
    print("=" * 60)

    r = TestResult()

    test_a_game_state_basics(r)
    test_b_game_state_properties(r)
    test_c_game_state_i18n(r)
    test_d_bonus_status_basics(r)
    test_e_bonus_status_grants_free_throws(r)
    test_f_bonus_status_i18n(r)
    test_g_timeout_type_basics(r)
    test_h_timeout_type_i18n(r)
    test_i_record_format_basics(r)
    test_j_state_transitions(r)
    test_k_league_dict_keys(r)
    test_l_timeout_rules(r)
    test_m_quarter_time(r)
    test_n_foul_management(r)
    test_o_substitution(r)
    test_p_shot_clock(r)
    test_q_record_integrity(r)
    test_r_is_valid_game_transition(r)
    test_s_get_bonus_status(r)
    test_t_is_foul_trouble(r)
    test_u_get_total_game_time_sec(r)
    test_v_all_exports(r)

    r.summary()
    sys.exit(0 if r.failed == 0 else 1)


if __name__ == "__main__":
    main()
