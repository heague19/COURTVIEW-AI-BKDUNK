# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_game_management_constants_perf.py

경기 관리 상수 모듈(game_management_constants.py v1.0.0) 성능 테스트

테스트 범위:
    [A] 모듈 임포트 시간 (< 500ms, cold import 의존성 포함)
    [B] GameState Enum 멤버 접근 (100K 반복 < 500ms)
    [C] BonusStatus Enum 멤버 접근 (100K 반복 < 500ms)
    [D] TimeoutType Enum 멤버 접근 (100K 반복 < 500ms)
    [E] RecordFormat Enum 멤버 접근 (100K 반복 < 500ms)
    [F] Enum i18n get_name() (10K 반복 < 200ms) - 4종 Enum
    [G] VALID_GAME_STATE_TRANSITIONS 조회 (100K 반복 < 500ms)
    [H] 리그 딕셔너리 조회 (100K 반복 < 500ms) - QUARTER_DURATION_SEC, TIMEOUTS_PER_TEAM 등
    [I] is_valid_game_transition 유틸리티 (50K 반복 < 300ms, 전체 조합 < 800ms)
    [J] get_bonus_status 유틸리티 (50K 반복 < 300ms)
    [K] is_foul_trouble 유틸리티 (50K 반복 < 300ms)
    [L] get_total_game_time_sec 유틸리티 (50K 반복 < 300ms)
    [M] 메모리 사용량 (모듈 객체 < 1MB)

성능 기준:
    - 모듈 임포트: < 500ms (cold import, localization + referee_rule_constants 의존성 포함)
    - Enum 멤버 접근: 100K iterations < 500ms
    - i18n get_name(): 10K iterations < 200ms
    - Dict 조회: 100K iterations < 500ms
    - 유틸리티 함수: 50K iterations < 300ms (전체 조합 9x9 = 81콜/iter: < 800ms)
    - 메모리 사용량: < 1MB

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (parents[4]: performance -> constants -> shared -> tests -> PROJECT_ROOT)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 수집 및 보고"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        self.passed += 1
        ratio = elapsed_ms / limit_ms * 100
        print(f"  [PASS] {name}: {elapsed_ms:.4f}ms ({ratio:.1f}% of {limit_ms:.0f}ms)")

    def fail(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_ms:.4f}ms > {limit_ms:.0f}ms")
        print(f"  [FAIL] {name}: {elapsed_ms:.4f}ms (limit: {limit_ms:.0f}ms)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def check(self, name: str, elapsed_ms: float, limit_ms: float) -> None:
        """결과 판정 (ms 기준)"""
        if elapsed_ms <= limit_ms:
            self.ok(name, elapsed_ms, limit_ms)
        else:
            self.fail(name, elapsed_ms, limit_ms)

    def check_memory(self, name: str, size_kb: float, limit_kb: float) -> None:
        """메모리 결과 판정 (KB 기준)"""
        if size_kb <= limit_kb:
            self.passed += 1
            ratio = size_kb / limit_kb * 100
            print(f"  [PASS] {name}: {size_kb:.2f}KB ({ratio:.1f}% of {limit_kb:.0f}KB)")
        else:
            self.failed += 1
            self.errors.append(f"{name}: {size_kb:.2f}KB > {limit_kb:.0f}KB")
            print(f"  [FAIL] {name}: {size_kb:.2f}KB (limit: {limit_kb:.0f}KB)")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n목표 미달 항목:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# =============================================================================
# [A] 모듈 임포트 시간 (< 500ms, cold import 의존성 포함)
# =============================================================================
def test_a_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 측정 (< 500ms, localization/referee_rule_constants 의존성 포함)"""
    import importlib

    mod_name = "shared.constants.game_management_constants"
    # 의존 모듈도 제거하여 cold import 측정
    deps_to_clear = [
        mod_name,
    ]
    for dep in deps_to_clear:
        if dep in sys.modules:
            del sys.modules[dep]

    gc.disable()
    start = time.perf_counter()
    importlib.import_module(mod_name)
    elapsed_ms = (time.perf_counter() - start) * 1000
    gc.enable()

    r.info(f"임포트 시간: {elapsed_ms:.2f}ms")
    r.check("모듈 임포트 (cold)", elapsed_ms, 500.0)


# =============================================================================
# [B] GameState Enum 멤버 접근 (100K 반복 < 500ms)
# =============================================================================
def test_b_game_state_enum_access(r: PerfResult) -> None:
    """GameState Enum 멤버 접근 (100K iterations < 500ms)"""
    from shared.constants.game_management_constants import GameState

    iterations = 100_000

    # GameState 멤버 접근 (9종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = GameState.PRE_GAME
        _ = GameState.TIP_OFF
        _ = GameState.LIVE
        _ = GameState.DEAD_BALL
        _ = GameState.TIMEOUT
        _ = GameState.PERIOD_BREAK
        _ = GameState.HALFTIME
        _ = GameState.OVERTIME
        _ = GameState.FINAL
    elapsed_member = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("GameState 멤버 접근 (100K x 9종)", elapsed_member, 500.0)

    # is_clock_running 프로퍼티 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = GameState.LIVE.is_clock_running
        _ = GameState.DEAD_BALL.is_clock_running
        _ = GameState.TIMEOUT.is_clock_running
        _ = GameState.FINAL.is_clock_running
    elapsed_clock = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("GameState.is_clock_running (100K x 4종)", elapsed_clock, 500.0)

    # is_game_active 프로퍼티 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = GameState.PRE_GAME.is_game_active
        _ = GameState.LIVE.is_game_active
        _ = GameState.HALFTIME.is_game_active
        _ = GameState.FINAL.is_game_active
    elapsed_active = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("GameState.is_game_active (100K x 4종)", elapsed_active, 500.0)


# =============================================================================
# [C] BonusStatus Enum 멤버 접근 (100K 반복 < 500ms)
# =============================================================================
def test_c_bonus_status_enum_access(r: PerfResult) -> None:
    """BonusStatus Enum 멤버 접근 (100K iterations < 500ms)"""
    from shared.constants.game_management_constants import BonusStatus

    iterations = 100_000

    # BonusStatus 멤버 접근 (3종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = BonusStatus.NONE
        _ = BonusStatus.BONUS
        _ = BonusStatus.DOUBLE_BONUS
    elapsed_member = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("BonusStatus 멤버 접근 (100K x 3종)", elapsed_member, 500.0)

    # grants_free_throws 프로퍼티 접근
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = BonusStatus.NONE.grants_free_throws
        _ = BonusStatus.BONUS.grants_free_throws
        _ = BonusStatus.DOUBLE_BONUS.grants_free_throws
    elapsed_ft = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("BonusStatus.grants_free_throws (100K x 3종)", elapsed_ft, 500.0)


# =============================================================================
# [D] TimeoutType Enum 멤버 접근 (100K 반복 < 500ms)
# =============================================================================
def test_d_timeout_type_enum_access(r: PerfResult) -> None:
    """TimeoutType Enum 멤버 접근 (100K iterations < 500ms)"""
    from shared.constants.game_management_constants import TimeoutType

    iterations = 100_000

    # TimeoutType 멤버 접근 (3종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = TimeoutType.FULL
        _ = TimeoutType.TWENTY_SECOND
        _ = TimeoutType.OFFICIAL
    elapsed_member = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("TimeoutType 멤버 접근 (100K x 3종)", elapsed_member, 500.0)


# =============================================================================
# [E] RecordFormat Enum 멤버 접근 (100K 반복 < 500ms)
# =============================================================================
def test_e_record_format_enum_access(r: PerfResult) -> None:
    """RecordFormat Enum 멤버 접근 (100K iterations < 500ms)"""
    from shared.constants.game_management_constants import RecordFormat

    iterations = 100_000

    # RecordFormat 멤버 접근 (6종)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = RecordFormat.FIBA_BOXSCORE
        _ = RecordFormat.NBA_BOXSCORE
        _ = RecordFormat.KBL_BOXSCORE
        _ = RecordFormat.NBL_BOXSCORE
        _ = RecordFormat.JSON_FEED
        _ = RecordFormat.XML_FEED
    elapsed_member = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("RecordFormat 멤버 접근 (100K x 6종)", elapsed_member, 500.0)


# =============================================================================
# [F] Enum i18n get_name() (10K 반복 < 200ms) - 4종 Enum
# =============================================================================
def test_f_enum_i18n_get_name(r: PerfResult) -> None:
    """Enum.get_name() 다국어 조회 (10K iterations < 200ms)"""
    from shared.constants.game_management_constants import (
        GameState,
        BonusStatus,
        TimeoutType,
    )
    from shared.constants.localization import SupportedLanguage

    iterations = 10_000

    # GameState.get_name() 5개 언어 x 9 상태
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for state in GameState:
            _ = state.get_name(SupportedLanguage.KO)
            _ = state.get_name(SupportedLanguage.EN)
            _ = state.get_name(SupportedLanguage.JA)
            _ = state.get_name(SupportedLanguage.ZH)
            _ = state.get_name(SupportedLanguage.ES)
    elapsed_state_i18n = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("GameState.get_name() (10K x 9종 x 5언어)", elapsed_state_i18n, 200.0)

    # BonusStatus.get_name() 5개 언어 x 3 상태
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for bonus in BonusStatus:
            _ = bonus.get_name(SupportedLanguage.KO)
            _ = bonus.get_name(SupportedLanguage.EN)
            _ = bonus.get_name(SupportedLanguage.JA)
            _ = bonus.get_name(SupportedLanguage.ZH)
            _ = bonus.get_name(SupportedLanguage.ES)
    elapsed_bonus_i18n = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("BonusStatus.get_name() (10K x 3종 x 5언어)", elapsed_bonus_i18n, 200.0)

    # TimeoutType.get_name() 5개 언어 x 3 유형
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for tt in TimeoutType:
            _ = tt.get_name(SupportedLanguage.KO)
            _ = tt.get_name(SupportedLanguage.EN)
            _ = tt.get_name(SupportedLanguage.JA)
            _ = tt.get_name(SupportedLanguage.ZH)
            _ = tt.get_name(SupportedLanguage.ES)
    elapsed_timeout_i18n = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("TimeoutType.get_name() (10K x 3종 x 5언어)", elapsed_timeout_i18n, 200.0)


# =============================================================================
# [G] VALID_GAME_STATE_TRANSITIONS 조회 (100K 반복 < 500ms)
# =============================================================================
def test_g_state_transitions_lookup(r: PerfResult) -> None:
    """경기 상태 전이 딕셔너리 조회 (100K iterations < 500ms)"""
    from shared.constants.game_management_constants import (
        GameState,
        VALID_GAME_STATE_TRANSITIONS,
    )

    iterations = 100_000

    # 단일 키 조회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = VALID_GAME_STATE_TRANSITIONS[GameState.LIVE]
    elapsed_single = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("VALID_GAME_STATE_TRANSITIONS 단일 조회 (100K)", elapsed_single, 500.0)

    # 전체 상태 순회 조회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for state in GameState:
            _ = VALID_GAME_STATE_TRANSITIONS[state]
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("VALID_GAME_STATE_TRANSITIONS 전체 조회 (100K x 9종)", elapsed_all, 500.0)

    # frozenset 멤버십 검사 (in 연산)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = GameState.DEAD_BALL in VALID_GAME_STATE_TRANSITIONS[GameState.LIVE]
        _ = GameState.FINAL in VALID_GAME_STATE_TRANSITIONS[GameState.LIVE]
        _ = GameState.LIVE in VALID_GAME_STATE_TRANSITIONS[GameState.TIMEOUT]
    elapsed_membership = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("frozenset 멤버십 검사 (100K x 3건)", elapsed_membership, 500.0)


# =============================================================================
# [H] 리그 딕셔너리 조회 (100K 반복 < 500ms) - QUARTER_DURATION_SEC, TIMEOUTS_PER_TEAM 등
# =============================================================================
def test_h_league_dict_lookups(r: PerfResult) -> None:
    """리그별 설정 딕셔너리 조회 (100K iterations < 500ms)"""
    from shared.constants.game_management_constants import (
        QUARTER_DURATION_SEC,
        TIMEOUTS_PER_TEAM,
        TIMEOUT_DURATION_SEC,
        HALFTIME_BREAK_SEC,
        PERIOD_BREAK_SEC,
        TEAM_FOUL_BONUS_THRESHOLD,
        SHOT_CLOCK_RESET_OFFENSIVE_REBOUND,
        SHOT_CLOCK_RESET_FOUL,
    )
    from shared.constants.referee_rule_constants import RuleSet

    iterations = 100_000

    # QUARTER_DURATION_SEC 조회 (5개 리그)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = QUARTER_DURATION_SEC[RuleSet.FIBA]
        _ = QUARTER_DURATION_SEC[RuleSet.NBA]
        _ = QUARTER_DURATION_SEC[RuleSet.KBL]
        _ = QUARTER_DURATION_SEC[RuleSet.NBL]
        _ = QUARTER_DURATION_SEC[RuleSet.EUROLEAGUE]
    elapsed_quarter = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("QUARTER_DURATION_SEC 조회 (100K x 5리그)", elapsed_quarter, 500.0)

    # TIMEOUTS_PER_TEAM 조회 (5개 리그)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = TIMEOUTS_PER_TEAM[RuleSet.FIBA]
        _ = TIMEOUTS_PER_TEAM[RuleSet.NBA]
        _ = TIMEOUTS_PER_TEAM[RuleSet.KBL]
        _ = TIMEOUTS_PER_TEAM[RuleSet.NBL]
        _ = TIMEOUTS_PER_TEAM[RuleSet.EUROLEAGUE]
    elapsed_timeouts = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("TIMEOUTS_PER_TEAM 조회 (100K x 5리그)", elapsed_timeouts, 500.0)

    # TIMEOUT_DURATION_SEC 조회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = TIMEOUT_DURATION_SEC[RuleSet.FIBA]
        _ = TIMEOUT_DURATION_SEC[RuleSet.NBA]
        _ = TIMEOUT_DURATION_SEC[RuleSet.KBL]
    elapsed_to_dur = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("TIMEOUT_DURATION_SEC 조회 (100K x 3리그)", elapsed_to_dur, 500.0)

    # HALFTIME_BREAK_SEC + PERIOD_BREAK_SEC 조회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = HALFTIME_BREAK_SEC[RuleSet.FIBA]
        _ = HALFTIME_BREAK_SEC[RuleSet.NBA]
        _ = PERIOD_BREAK_SEC[RuleSet.FIBA]
        _ = PERIOD_BREAK_SEC[RuleSet.NBA]
    elapsed_breaks = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("HALFTIME/PERIOD_BREAK_SEC 조회 (100K x 4키)", elapsed_breaks, 500.0)

    # TEAM_FOUL_BONUS_THRESHOLD 조회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = TEAM_FOUL_BONUS_THRESHOLD[RuleSet.FIBA]
        _ = TEAM_FOUL_BONUS_THRESHOLD[RuleSet.NBA]
        _ = TEAM_FOUL_BONUS_THRESHOLD[RuleSet.KBL]
    elapsed_foul_th = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("TEAM_FOUL_BONUS_THRESHOLD 조회 (100K x 3리그)", elapsed_foul_th, 500.0)

    # SHOT_CLOCK_RESET 딕셔너리 조회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = SHOT_CLOCK_RESET_OFFENSIVE_REBOUND[RuleSet.FIBA]
        _ = SHOT_CLOCK_RESET_OFFENSIVE_REBOUND[RuleSet.NBA]
        _ = SHOT_CLOCK_RESET_FOUL[RuleSet.FIBA]
        _ = SHOT_CLOCK_RESET_FOUL[RuleSet.NBA]
    elapsed_shot_clock = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("SHOT_CLOCK_RESET 조회 (100K x 4키)", elapsed_shot_clock, 500.0)


# =============================================================================
# [I] is_valid_game_transition 유틸리티 (50K 반복 < 300ms)
# =============================================================================
def test_i_is_valid_game_transition(r: PerfResult) -> None:
    """is_valid_game_transition 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.game_management_constants import GameState, is_valid_game_transition

    iterations = 50_000

    # 유효한 전이 (LIVE -> DEAD_BALL)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = is_valid_game_transition(GameState.LIVE, GameState.DEAD_BALL)
    elapsed_valid = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_valid_game_transition (유효 전이, 50K)", elapsed_valid, 300.0)

    # 무효한 전이 (PRE_GAME -> FINAL)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = is_valid_game_transition(GameState.PRE_GAME, GameState.FINAL)
    elapsed_invalid = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_valid_game_transition (무효 전이, 50K)", elapsed_invalid, 300.0)

    # 전체 상태 조합 순회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for src in GameState:
            for tgt in GameState:
                _ = is_valid_game_transition(src, tgt)
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_valid_game_transition (전체 조합 9x9, 50K)", elapsed_all, 800.0)


# =============================================================================
# [J] get_bonus_status 유틸리티 (50K 반복 < 300ms)
# =============================================================================
def test_j_get_bonus_status(r: PerfResult) -> None:
    """get_bonus_status 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.game_management_constants import get_bonus_status
    from shared.constants.referee_rule_constants import RuleSet

    iterations = 50_000

    # FIBA: 팀파울 3회 (보너스 없음)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_bonus_status(3, RuleSet.FIBA)
    elapsed_none = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_bonus_status (FIBA, 보너스 없음, 50K)", elapsed_none, 300.0)

    # FIBA: 팀파울 5회 (보너스)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_bonus_status(5, RuleSet.FIBA)
    elapsed_bonus = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_bonus_status (FIBA, 보너스, 50K)", elapsed_bonus, 300.0)

    # NBA: 팀파울 10회 (더블 보너스)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_bonus_status(10, RuleSet.NBA)
    elapsed_double = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_bonus_status (NBA, 더블보너스, 50K)", elapsed_double, 300.0)

    # 전체 리그 x 대표 파울 수 순회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for rule in (RuleSet.FIBA, RuleSet.NBA, RuleSet.KBL, RuleSet.NBL, RuleSet.EUROLEAGUE):
            _ = get_bonus_status(2, rule)
            _ = get_bonus_status(5, rule)
            _ = get_bonus_status(8, rule)
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_bonus_status (전체 리그 x 3단계, 50K)", elapsed_all, 300.0)


# =============================================================================
# [K] is_foul_trouble 유틸리티 (50K 반복 < 300ms)
# =============================================================================
def test_k_is_foul_trouble(r: PerfResult) -> None:
    """is_foul_trouble 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.game_management_constants import is_foul_trouble
    from shared.constants.referee_rule_constants import RuleSet

    iterations = 50_000

    # FIBA: 개인파울 4회 (파울 트러블)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = is_foul_trouble(4, RuleSet.FIBA)
    elapsed_trouble = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_foul_trouble (FIBA, 트러블, 50K)", elapsed_trouble, 300.0)

    # NBA: 개인파울 3회 (안전)
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = is_foul_trouble(3, RuleSet.NBA)
    elapsed_safe = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_foul_trouble (NBA, 안전, 50K)", elapsed_safe, 300.0)

    # 전체 리그 x 다양한 파울 수 순회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for rule in (RuleSet.FIBA, RuleSet.NBA, RuleSet.KBL, RuleSet.NBL, RuleSet.EUROLEAGUE):
            _ = is_foul_trouble(2, rule)
            _ = is_foul_trouble(4, rule)
            _ = is_foul_trouble(5, rule)
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("is_foul_trouble (전체 리그 x 3단계, 50K)", elapsed_all, 300.0)


# =============================================================================
# [L] get_total_game_time_sec 유틸리티 (50K 반복 < 300ms)
# =============================================================================
def test_l_get_total_game_time_sec(r: PerfResult) -> None:
    """get_total_game_time_sec 유틸리티 함수 (50K iterations < 300ms)"""
    from shared.constants.game_management_constants import get_total_game_time_sec
    from shared.constants.referee_rule_constants import RuleSet

    iterations = 50_000

    # FIBA 정규 경기 시간
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_total_game_time_sec(RuleSet.FIBA)
    elapsed_fiba = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_total_game_time_sec (FIBA, 50K)", elapsed_fiba, 300.0)

    # NBA 정규 경기 시간
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        _ = get_total_game_time_sec(RuleSet.NBA)
    elapsed_nba = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_total_game_time_sec (NBA, 50K)", elapsed_nba, 300.0)

    # 전체 리그 순회
    gc.disable()
    start = time.perf_counter()
    for _ in range(iterations):
        for rule in (RuleSet.FIBA, RuleSet.NBA, RuleSet.KBL, RuleSet.NBL, RuleSet.EUROLEAGUE):
            _ = get_total_game_time_sec(rule)
    elapsed_all = (time.perf_counter() - start) * 1000
    gc.enable()

    r.check("get_total_game_time_sec (전체 리그, 50K)", elapsed_all, 300.0)


# =============================================================================
# [M] 메모리 사용량 (모듈 객체 < 1MB)
# =============================================================================
def test_m_memory_footprint(r: PerfResult) -> None:
    """모듈 내 주요 객체 메모리 사용량 (< 1MB = 1024KB)"""
    import sys as _sys
    from shared.constants.game_management_constants import (
        # Enum 클래스
        GameState,
        BonusStatus,
        TimeoutType,
        RecordFormat,
        # 상태 전이
        VALID_GAME_STATE_TRANSITIONS,
        # 타임아웃 규칙
        TIMEOUTS_PER_TEAM,
        TIMEOUT_DURATION_SEC,
        # 쿼터/경기 시간
        QUARTER_DURATION_SEC,
        HALFTIME_BREAK_SEC,
        PERIOD_BREAK_SEC,
        # 파울 관리
        TEAM_FOUL_BONUS_THRESHOLD,
        # 슛클락
        SHOT_CLOCK_RESET_OFFENSIVE_REBOUND,
        SHOT_CLOCK_RESET_FOUL,
    )

    sizes: dict[str, int] = {
        # Enum 클래스
        "GameState (Enum)": _sys.getsizeof(GameState),
        "BonusStatus (Enum)": _sys.getsizeof(BonusStatus),
        "TimeoutType (Enum)": _sys.getsizeof(TimeoutType),
        "RecordFormat (Enum)": _sys.getsizeof(RecordFormat),
        # 상태 전이
        "VALID_GAME_STATE_TRANSITIONS": _sys.getsizeof(VALID_GAME_STATE_TRANSITIONS),
        # 타임아웃 규칙
        "TIMEOUTS_PER_TEAM": _sys.getsizeof(TIMEOUTS_PER_TEAM),
        "TIMEOUT_DURATION_SEC": _sys.getsizeof(TIMEOUT_DURATION_SEC),
        # 쿼터/경기 시간
        "QUARTER_DURATION_SEC": _sys.getsizeof(QUARTER_DURATION_SEC),
        "HALFTIME_BREAK_SEC": _sys.getsizeof(HALFTIME_BREAK_SEC),
        "PERIOD_BREAK_SEC": _sys.getsizeof(PERIOD_BREAK_SEC),
        # 파울 관리
        "TEAM_FOUL_BONUS_THRESHOLD": _sys.getsizeof(TEAM_FOUL_BONUS_THRESHOLD),
        # 슛클락
        "SHOT_CLOCK_RESET_OFFENSIVE_REBOUND": _sys.getsizeof(SHOT_CLOCK_RESET_OFFENSIVE_REBOUND),
        "SHOT_CLOCK_RESET_FOUL": _sys.getsizeof(SHOT_CLOCK_RESET_FOUL),
    }

    total_bytes = sum(sizes.values())
    total_kb = total_bytes / 1024
    limit_kb = 1024.0  # 1MB

    print(f"\n  메모리 사용량 (주요 객체):")
    for name, size_bytes in sizes.items():
        print(f"    {name}: {size_bytes} bytes")
    print(f"    {'─' * 40}")
    print(f"    합계: {total_bytes} bytes ({total_kb:.2f}KB)")

    r.check_memory("모듈 주요 객체 메모리 합계", total_kb, limit_kb)

    # tracemalloc 기반 모듈 전체 메모리 측정
    import importlib
    import tracemalloc

    mod_name = "shared.constants.game_management_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    tracemalloc.start()
    importlib.import_module(mod_name)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_kb = peak / 1024
    print(f"\n  tracemalloc 모듈 메모리:")
    print(f"    현재: {current / 1024:.2f}KB")
    print(f"    피크: {peak_kb:.2f}KB")

    r.check_memory("tracemalloc 피크 메모리", peak_kb, limit_kb)


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> int:
    """모든 game_management_constants 성능 테스트 실행."""
    r = PerfResult()

    print("\n" + "=" * 60)
    print("game_management_constants.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- [A] 모듈 임포트 시간 ---")
    test_a_import_time(r)

    print("\n--- [B] GameState Enum 멤버 접근 ---")
    test_b_game_state_enum_access(r)

    print("\n--- [C] BonusStatus Enum 멤버 접근 ---")
    test_c_bonus_status_enum_access(r)

    print("\n--- [D] TimeoutType Enum 멤버 접근 ---")
    test_d_timeout_type_enum_access(r)

    print("\n--- [E] RecordFormat Enum 멤버 접근 ---")
    test_e_record_format_enum_access(r)

    print("\n--- [F] Enum i18n get_name() ---")
    test_f_enum_i18n_get_name(r)

    print("\n--- [G] VALID_GAME_STATE_TRANSITIONS 조회 ---")
    test_g_state_transitions_lookup(r)

    print("\n--- [H] 리그 딕셔너리 조회 ---")
    test_h_league_dict_lookups(r)

    print("\n--- [I] is_valid_game_transition ---")
    test_i_is_valid_game_transition(r)

    print("\n--- [J] get_bonus_status ---")
    test_j_get_bonus_status(r)

    print("\n--- [K] is_foul_trouble ---")
    test_k_is_foul_trouble(r)

    print("\n--- [L] get_total_game_time_sec ---")
    test_l_get_total_game_time_sec(r)

    print("\n--- [M] 메모리 사용량 ---")
    test_m_memory_footprint(r)

    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
