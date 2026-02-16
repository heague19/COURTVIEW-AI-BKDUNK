# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_tactical_constants.py

tactical_constants.py v1.0.0 단위 테스트

테스트 항목:
  [A] SetPlayType 멤버 수, 값, 유일성, isinstance
  [B] SetPlayType.involves_screen (14 멤버 정확)
  [C] SetPlayType.is_one_on_one (14 멤버 정확)
  [D] SetPlayType.get_name() i18n (5개 언어 x 14)
  [E] TransitionPhase 멤버 수, 값, 유일성, isinstance
  [F] TransitionPhase.get_name() i18n (5개 언어 x 3)
  [G] SpacingQuality 멤버 수, 값, 유일성, isinstance
  [H] SpacingQuality.get_name() i18n (5개 언어 x 5)
  [I] TurnoverCategory 멤버 수, 값, 유일성, isinstance
  [J] TurnoverCategory.is_forced (4 멤버 정확)
  [K] TurnoverCategory.is_live_ball (4 멤버 정확)
  [L] TurnoverCategory.get_name() i18n (5개 언어 x 4)
  [M] 스크린/PnR 파라미터 (9개 float 상수)
  [N] 전환 속도 상수 (5개)
  [O] 스페이싱 상수 (7개)
  [P] 모멘텀/런 상수 (6개)
  [Q] 템포 상수 (3개)
  [R] 매치업/수비 상수 (9개)
  [S] 드라이브/오프볼/리바운드/리드관리 상수
  [T] classify_spacing_quality 함수
  [U] classify_transition_phase 함수
  [V] is_scoring_run 함수 및 논리적 일관성

작성자: COURTVIEW AI Team
최종 수정: 2026-02-15
"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.current_section = ""

    def set_section(self, name):
        self.current_section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name, msg=""):
        self.failed += 1
        self.errors.append(f"[{self.current_section}] {name}: {msg}")
        print(f"  [FAIL] {name} - {msg}")

    def check(self, name, condition, msg=""):
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        if self.errors:
            print(f"\n  Errors:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")
        return self.failed == 0


result = TestResult()

# =============================================================================
# 임포트
# =============================================================================
from shared.constants.tactical_constants import (
    # 열거형
    SetPlayType, TransitionPhase, SpacingQuality, TurnoverCategory,
    # 스크린/PnR 파라미터
    SCREEN_CONTACT_DISTANCE_M,
    SCREEN_ANGLE_MIN_DEG, SCREEN_ANGLE_MAX_DEG,
    ROLL_MAN_DIVE_SPEED_MIN, POP_OUT_DISTANCE_MIN_M,
    PNR_DEFENSE_REACTION_TIME_SEC,
    SCREEN_HOLD_TIME_MIN_SEC, SCREEN_HOLD_TIME_MAX_SEC,
    HAND_OFF_PROXIMITY_M,
    # 전환 속도
    PRIMARY_BREAK_MAX_SEC, SECONDARY_BREAK_MAX_SEC,
    DEFENSIVE_TRANSITION_TARGET_SEC, FAST_BREAK_ADVANTAGE_MIN,
    FAST_BREAK_BALL_SPEED_MIN,
    # 스페이싱
    SPACING_MIN_DISTANCE_M, SPACING_OPTIMAL_DISTANCE_M,
    SPACING_COLLAPSED_DISTANCE_M,
    COURT_UTILIZATION_EXCELLENT, COURT_UTILIZATION_GOOD, COURT_UTILIZATION_POOR,
    DRIVE_LANE_MIN_WIDTH_M,
    # 모멘텀/런
    SCORING_RUN_MIN_POINTS, SCORING_RUN_MIN_UNANSWERED,
    MOMENTUM_SHIFT_THRESHOLD, SCORING_DROUGHT_POSSESSIONS,
    MOMENTUM_DECAY_PER_MINUTE, MOMENTUM_TIMEOUT_RESET_FACTOR,
    # 템포
    TEMPO_FAST_THRESHOLD_SEC, TEMPO_SLOW_THRESHOLD_SEC,
    HALFCOURT_SET_TIME_SEC,
    # 매치업/수비
    MATCHUP_ASSIGNMENT_DISTANCE_M, DEFENSIVE_BREAKDOWN_DISTANCE_M,
    CLOSEOUT_START_DISTANCE_M, CLOSEOUT_SUCCESS_DISTANCE_M,
    CLOSEOUT_TARGET_TIME_SEC,
    HELP_DEFENSE_TRIGGER_DISTANCE_M, HELP_RECOVERY_TARGET_SEC,
    SHOT_CONTEST_EFFECTIVE_M, HAND_UP_MIN_ANGLE_DEG,
    # 드라이브
    DRIVE_START_SPEED_MIN, DRIVE_DIRECTION_ANGLE_DEG,
    DRIVE_MIN_DISTANCE_M, DRIVE_END_SPEED_THRESHOLD,
    DRIVE_KICKOUT_MAX_SEC,
    # 오프볼 무브먼트
    CUT_SPEED_MIN, CUT_DIRECTION_ANGLE_DEG,
    SCREEN_EXIT_SPEED_CHANGE, CUT_DIRECTION_CHANGE_MIN_DEG,
    # 리바운드
    BOX_OUT_EFFECTIVE_DISTANCE_M, BOX_OUT_REACTION_TIME_SEC,
    LONG_REBOUND_DISTANCE_M, TIP_CHAIN_MAX_INTERVAL_SEC,
    # 리드 관리
    CLOSE_GAME_MARGIN, BLOWOUT_MARGIN, COMEBACK_MIN_DURATION_SEC,
    # 유틸리티 함수
    classify_spacing_quality, classify_transition_phase, is_scoring_run,
)
import shared.constants.tactical_constants as tc
from shared.constants.localization import SupportedLanguage
from enum import Enum

# =============================================================================
# [A] SetPlayType 멤버 수, 값, 유일성, isinstance
# =============================================================================
result.set_section("[A] SetPlayType 멤버 수, 값, 유일성, isinstance")
result.check("SetPlayType 멤버 수 = 14", len(SetPlayType) == 14, f"실제: {len(SetPlayType)}")

_expected_set_plays = [
    ("HORN", "horn"), ("FLEX", "flex"), ("MOTION", "motion"),
    ("FLOPPY", "floppy"), ("PRINCETON", "princeton"), ("TRIANGLE", "triangle"),
    ("PICK_AND_ROLL", "pick_and_roll"), ("PICK_AND_POP", "pick_and_pop"),
    ("ISOLATION", "isolation"), ("POST_UP", "post_up"),
    ("DRIBBLE_HAND_OFF", "dribble_hand_off"), ("STAGGER_SCREEN", "stagger_screen"),
    ("SPAIN_PNR", "spain_pnr"), ("ATO_SET", "ato_set"),
]
for name, value in _expected_set_plays:
    s = SetPlayType[name]
    result.check(f"SetPlayType.{name} = '{value}'", s.value == value, f"실제: {s.value}")

# 값 유일성
_sp_vals = [s.value for s in SetPlayType]
result.check("SetPlayType 값 유일성", len(_sp_vals) == len(set(_sp_vals)))

# isinstance 검증
for s in SetPlayType:
    result.check(f"SetPlayType.{s.name} isinstance Enum", isinstance(s, Enum))
    result.check(f"SetPlayType.{s.name} isinstance str", isinstance(s, str))

# __str__ 검증
for s in SetPlayType:
    result.check(f"str(SetPlayType.{s.name}) = '{s.value}'", str(s) == s.value, f"실제: {str(s)}")

# =============================================================================
# [B] SetPlayType.involves_screen (14 멤버 정확)
# =============================================================================
result.set_section("[B] SetPlayType.involves_screen")

_expected_involves_screen = {
    "HORN": True, "FLEX": True, "MOTION": False,
    "FLOPPY": True, "PRINCETON": False, "TRIANGLE": False,
    "PICK_AND_ROLL": True, "PICK_AND_POP": True,
    "ISOLATION": False, "POST_UP": False,
    "DRIBBLE_HAND_OFF": True, "STAGGER_SCREEN": True,
    "SPAIN_PNR": True, "ATO_SET": False,
}
for name, expected in _expected_involves_screen.items():
    s = SetPlayType[name]
    result.check(
        f"SetPlayType.{name}.involves_screen = {expected}",
        s.involves_screen is expected,
        f"실제: {s.involves_screen}",
    )

# involves_screen은 bool 타입
for s in SetPlayType:
    result.check(f"SetPlayType.{s.name}.involves_screen bool 타입", isinstance(s.involves_screen, bool))

# 스크린 포함 8개
_screen_count = sum(1 for s in SetPlayType if s.involves_screen)
result.check("involves_screen True 개수 = 8", _screen_count == 8, f"실제: {_screen_count}")

# =============================================================================
# [C] SetPlayType.is_one_on_one (14 멤버 정확)
# =============================================================================
result.set_section("[C] SetPlayType.is_one_on_one")

_expected_is_one_on_one = {
    "HORN": False, "FLEX": False, "MOTION": False,
    "FLOPPY": False, "PRINCETON": False, "TRIANGLE": False,
    "PICK_AND_ROLL": False, "PICK_AND_POP": False,
    "ISOLATION": True, "POST_UP": True,
    "DRIBBLE_HAND_OFF": False, "STAGGER_SCREEN": False,
    "SPAIN_PNR": False, "ATO_SET": False,
}
for name, expected in _expected_is_one_on_one.items():
    s = SetPlayType[name]
    result.check(
        f"SetPlayType.{name}.is_one_on_one = {expected}",
        s.is_one_on_one is expected,
        f"실제: {s.is_one_on_one}",
    )

# is_one_on_one은 bool 타입
for s in SetPlayType:
    result.check(f"SetPlayType.{s.name}.is_one_on_one bool 타입", isinstance(s.is_one_on_one, bool))

# 1:1 플레이 2개
_one_on_one_count = sum(1 for s in SetPlayType if s.is_one_on_one)
result.check("is_one_on_one True 개수 = 2", _one_on_one_count == 2, f"실제: {_one_on_one_count}")

# 1:1 플레이는 스크린 미포함
for s in SetPlayType:
    if s.is_one_on_one:
        result.check(f"is_one_on_one이면 involves_screen=False: {s.name}", not s.involves_screen)

# =============================================================================
# [D] SetPlayType.get_name() i18n (5개 언어 x 14)
# =============================================================================
result.set_section("[D] SetPlayType.get_name() i18n")

_expected_set_play_ko = {
    "HORN": "혼", "FLEX": "플렉스", "MOTION": "모션",
    "FLOPPY": "플로피", "PRINCETON": "프린스턴", "TRIANGLE": "트라이앵글",
    "PICK_AND_ROLL": "픽앤롤", "PICK_AND_POP": "픽앤팝",
    "ISOLATION": "아이솔레이션", "POST_UP": "포스트업",
    "DRIBBLE_HAND_OFF": "드리블 핸드오프", "STAGGER_SCREEN": "스태거 스크린",
    "SPAIN_PNR": "스페인 PnR", "ATO_SET": "ATO 세트",
}
for name, korean in _expected_set_play_ko.items():
    s = SetPlayType[name]
    result.check(
        f"SetPlayType.{name}.get_name(KO) = '{korean}'",
        s.get_name(SupportedLanguage.KO) == korean,
        f"실제: '{s.get_name(SupportedLanguage.KO)}'",
    )

# 모든 멤버의 get_name()이 str 타입, 비어있지 않음
for s in SetPlayType:
    for lang in SupportedLanguage:
        val = s.get_name(lang)
        result.check(f"SetPlayType.{s.name}.get_name({lang.name}) str 비어있지 않음",
                     isinstance(val, str) and len(val) > 0, f"실제: '{val}'")

# get_name은 메서드 (호출 가능)
result.check("SetPlayType.get_name 호출 가능", callable(SetPlayType.HORN.get_name))

# 기본 언어 = KO
for s in SetPlayType:
    result.check(f"SetPlayType.{s.name}.get_name() 기본=KO",
                 s.get_name() == s.get_name(SupportedLanguage.KO))

# =============================================================================
# [E] TransitionPhase 멤버 수, 값, 유일성, isinstance
# =============================================================================
result.set_section("[E] TransitionPhase 멤버 수, 값, 유일성, isinstance")
result.check("TransitionPhase 멤버 수 = 3", len(TransitionPhase) == 3, f"실제: {len(TransitionPhase)}")

_expected_transitions = [
    ("PRIMARY_BREAK", "primary_break"),
    ("SECONDARY_BREAK", "secondary_break"),
    ("EARLY_OFFENSE", "early_offense"),
]
for name, value in _expected_transitions:
    t = TransitionPhase[name]
    result.check(f"TransitionPhase.{name} = '{value}'", t.value == value, f"실제: {t.value}")

# 값 유일성
_tp_vals = [t.value for t in TransitionPhase]
result.check("TransitionPhase 값 유일성", len(_tp_vals) == len(set(_tp_vals)))

# isinstance
for t in TransitionPhase:
    result.check(f"TransitionPhase.{t.name} isinstance Enum", isinstance(t, Enum))
    result.check(f"TransitionPhase.{t.name} isinstance str", isinstance(t, str))

# __str__
for t in TransitionPhase:
    result.check(f"str(TransitionPhase.{t.name}) = '{t.value}'", str(t) == t.value)

# =============================================================================
# [F] TransitionPhase.get_name() i18n
# =============================================================================
result.set_section("[F] TransitionPhase.get_name() i18n")

_expected_transition_ko = {
    "PRIMARY_BREAK": "1차 속공",
    "SECONDARY_BREAK": "2차 속공",
    "EARLY_OFFENSE": "얼리 오펜스",
}
for name, korean in _expected_transition_ko.items():
    t = TransitionPhase[name]
    result.check(
        f"TransitionPhase.{name}.get_name(KO) = '{korean}'",
        t.get_name(SupportedLanguage.KO) == korean,
        f"실제: '{t.get_name(SupportedLanguage.KO)}'",
    )

_expected_transition_en = {
    "PRIMARY_BREAK": "Primary Break",
    "SECONDARY_BREAK": "Secondary Break",
    "EARLY_OFFENSE": "Early Offense",
}
for name, english in _expected_transition_en.items():
    t = TransitionPhase[name]
    result.check(
        f"TransitionPhase.{name}.get_name(EN) = '{english}'",
        t.get_name(SupportedLanguage.EN) == english,
        f"실제: '{t.get_name(SupportedLanguage.EN)}'",
    )

# 모든 멤버, 모든 언어 커버리지
for t in TransitionPhase:
    for lang in SupportedLanguage:
        val = t.get_name(lang)
        result.check(f"TransitionPhase.{t.name}.get_name({lang.name}) str 비어있지 않음",
                     isinstance(val, str) and len(val) > 0)

# =============================================================================
# [G] SpacingQuality 멤버 수, 값, 유일성, isinstance
# =============================================================================
result.set_section("[G] SpacingQuality 멤버 수, 값, 유일성, isinstance")
result.check("SpacingQuality 멤버 수 = 5", len(SpacingQuality) == 5, f"실제: {len(SpacingQuality)}")

_expected_spacing = [
    ("EXCELLENT", "excellent"), ("GOOD", "good"), ("AVERAGE", "average"),
    ("POOR", "poor"), ("COLLAPSED", "collapsed"),
]
for name, value in _expected_spacing:
    sq = SpacingQuality[name]
    result.check(f"SpacingQuality.{name} = '{value}'", sq.value == value, f"실제: {sq.value}")

# 값 유일성
_sq_vals = [sq.value for sq in SpacingQuality]
result.check("SpacingQuality 값 유일성", len(_sq_vals) == len(set(_sq_vals)))

# isinstance
for sq in SpacingQuality:
    result.check(f"SpacingQuality.{sq.name} isinstance Enum", isinstance(sq, Enum))
    result.check(f"SpacingQuality.{sq.name} isinstance str", isinstance(sq, str))

# __str__
for sq in SpacingQuality:
    result.check(f"str(SpacingQuality.{sq.name}) = '{sq.value}'", str(sq) == sq.value)

# =============================================================================
# [H] SpacingQuality.get_name() i18n
# =============================================================================
result.set_section("[H] SpacingQuality.get_name() i18n")

_expected_spacing_ko = {
    "EXCELLENT": "최적", "GOOD": "양호", "AVERAGE": "보통",
    "POOR": "부족", "COLLAPSED": "밀집",
}
for name, korean in _expected_spacing_ko.items():
    sq = SpacingQuality[name]
    result.check(
        f"SpacingQuality.{name}.get_name(KO) = '{korean}'",
        sq.get_name(SupportedLanguage.KO) == korean,
        f"실제: '{sq.get_name(SupportedLanguage.KO)}'",
    )

_expected_spacing_en = {
    "EXCELLENT": "Excellent", "GOOD": "Good", "AVERAGE": "Average",
    "POOR": "Poor", "COLLAPSED": "Collapsed",
}
for name, english in _expected_spacing_en.items():
    sq = SpacingQuality[name]
    result.check(
        f"SpacingQuality.{name}.get_name(EN) = '{english}'",
        sq.get_name(SupportedLanguage.EN) == english,
        f"실제: '{sq.get_name(SupportedLanguage.EN)}'",
    )

# 모든 멤버, 모든 언어 커버리지
for sq in SpacingQuality:
    for lang in SupportedLanguage:
        val = sq.get_name(lang)
        result.check(f"SpacingQuality.{sq.name}.get_name({lang.name}) str 비어있지 않음",
                     isinstance(val, str) and len(val) > 0)

# =============================================================================
# [I] TurnoverCategory 멤버 수, 값, 유일성, isinstance
# =============================================================================
result.set_section("[I] TurnoverCategory 멤버 수, 값, 유일성, isinstance")
result.check("TurnoverCategory 멤버 수 = 4", len(TurnoverCategory) == 4, f"실제: {len(TurnoverCategory)}")

_expected_turnovers = [
    ("FORCED_LIVE", "forced_live"), ("FORCED_DEAD", "forced_dead"),
    ("UNFORCED_LIVE", "unforced_live"), ("UNFORCED_DEAD", "unforced_dead"),
]
for name, value in _expected_turnovers:
    tc_m = TurnoverCategory[name]
    result.check(f"TurnoverCategory.{name} = '{value}'", tc_m.value == value, f"실제: {tc_m.value}")

# 값 유일성
_tc_vals = [t.value for t in TurnoverCategory]
result.check("TurnoverCategory 값 유일성", len(_tc_vals) == len(set(_tc_vals)))

# isinstance
for t in TurnoverCategory:
    result.check(f"TurnoverCategory.{t.name} isinstance Enum", isinstance(t, Enum))
    result.check(f"TurnoverCategory.{t.name} isinstance str", isinstance(t, str))

# __str__
for t in TurnoverCategory:
    result.check(f"str(TurnoverCategory.{t.name}) = '{t.value}'", str(t) == t.value)

# =============================================================================
# [J] TurnoverCategory.is_forced (4 멤버 정확)
# =============================================================================
result.set_section("[J] TurnoverCategory.is_forced")

_expected_is_forced = {
    "FORCED_LIVE": True, "FORCED_DEAD": True,
    "UNFORCED_LIVE": False, "UNFORCED_DEAD": False,
}
for name, expected in _expected_is_forced.items():
    t = TurnoverCategory[name]
    result.check(
        f"TurnoverCategory.{name}.is_forced = {expected}",
        t.is_forced is expected,
        f"실제: {t.is_forced}",
    )

# is_forced는 bool 타입
for t in TurnoverCategory:
    result.check(f"TurnoverCategory.{t.name}.is_forced bool 타입", isinstance(t.is_forced, bool))

# 강제 2개
_forced_count = sum(1 for t in TurnoverCategory if t.is_forced)
result.check("is_forced True 개수 = 2", _forced_count == 2, f"실제: {_forced_count}")

# =============================================================================
# [K] TurnoverCategory.is_live_ball (4 멤버 정확)
# =============================================================================
result.set_section("[K] TurnoverCategory.is_live_ball")

_expected_is_live_ball = {
    "FORCED_LIVE": True, "FORCED_DEAD": False,
    "UNFORCED_LIVE": True, "UNFORCED_DEAD": False,
}
for name, expected in _expected_is_live_ball.items():
    t = TurnoverCategory[name]
    result.check(
        f"TurnoverCategory.{name}.is_live_ball = {expected}",
        t.is_live_ball is expected,
        f"실제: {t.is_live_ball}",
    )

# is_live_ball은 bool 타입
for t in TurnoverCategory:
    result.check(f"TurnoverCategory.{t.name}.is_live_ball bool 타입", isinstance(t.is_live_ball, bool))

# 라이브볼 2개
_live_count = sum(1 for t in TurnoverCategory if t.is_live_ball)
result.check("is_live_ball True 개수 = 2", _live_count == 2, f"실제: {_live_count}")

# 논리적 일관성: FORCED_LIVE만 둘 다 True
for t in TurnoverCategory:
    if t.is_forced and t.is_live_ball:
        result.check(f"is_forced & is_live_ball = FORCED_LIVE: {t.name}", t == TurnoverCategory.FORCED_LIVE)

# =============================================================================
# [L] TurnoverCategory.get_name() i18n
# =============================================================================
result.set_section("[L] TurnoverCategory.get_name() i18n")

_expected_turnover_ko = {
    "FORCED_LIVE": "강제 라이브볼", "FORCED_DEAD": "강제 데드볼",
    "UNFORCED_LIVE": "비강제 라이브볼", "UNFORCED_DEAD": "비강제 데드볼",
}
for name, korean in _expected_turnover_ko.items():
    t = TurnoverCategory[name]
    result.check(
        f"TurnoverCategory.{name}.get_name(KO) = '{korean}'",
        t.get_name(SupportedLanguage.KO) == korean,
        f"실제: '{t.get_name(SupportedLanguage.KO)}'",
    )

_expected_turnover_en = {
    "FORCED_LIVE": "Forced Live Ball", "FORCED_DEAD": "Forced Dead Ball",
    "UNFORCED_LIVE": "Unforced Live Ball", "UNFORCED_DEAD": "Unforced Dead Ball",
}
for name, english in _expected_turnover_en.items():
    t = TurnoverCategory[name]
    result.check(
        f"TurnoverCategory.{name}.get_name(EN) = '{english}'",
        t.get_name(SupportedLanguage.EN) == english,
        f"실제: '{t.get_name(SupportedLanguage.EN)}'",
    )

# 모든 멤버, 모든 언어 커버리지
for t in TurnoverCategory:
    for lang in SupportedLanguage:
        val = t.get_name(lang)
        result.check(f"TurnoverCategory.{t.name}.get_name({lang.name}) str 비어있지 않음",
                     isinstance(val, str) and len(val) > 0)

# =============================================================================
# [M] 스크린/PnR 파라미터 (9개 float 상수)
# =============================================================================
result.set_section("[M] 스크린/PnR 파라미터")

_screen_params = {
    "SCREEN_CONTACT_DISTANCE_M": (SCREEN_CONTACT_DISTANCE_M, 0.5),
    "SCREEN_ANGLE_MIN_DEG": (SCREEN_ANGLE_MIN_DEG, 45.0),
    "SCREEN_ANGLE_MAX_DEG": (SCREEN_ANGLE_MAX_DEG, 135.0),
    "ROLL_MAN_DIVE_SPEED_MIN": (ROLL_MAN_DIVE_SPEED_MIN, 2.0),
    "POP_OUT_DISTANCE_MIN_M": (POP_OUT_DISTANCE_MIN_M, 6.0),
    "PNR_DEFENSE_REACTION_TIME_SEC": (PNR_DEFENSE_REACTION_TIME_SEC, 0.8),
    "SCREEN_HOLD_TIME_MIN_SEC": (SCREEN_HOLD_TIME_MIN_SEC, 0.3),
    "SCREEN_HOLD_TIME_MAX_SEC": (SCREEN_HOLD_TIME_MAX_SEC, 2.0),
    "HAND_OFF_PROXIMITY_M": (HAND_OFF_PROXIMITY_M, 1.0),
}
for name, (val, expected) in _screen_params.items():
    result.check(f"{name} float 타입", isinstance(val, float), f"실제: {type(val)}")
    result.check(f"{name} = {expected}", val == expected, f"실제: {val}")
    result.check(f"{name} > 0", val > 0)

result.check("SCREEN_ANGLE_MIN < MAX", SCREEN_ANGLE_MIN_DEG < SCREEN_ANGLE_MAX_DEG)
result.check("SCREEN_HOLD_TIME_MIN < MAX", SCREEN_HOLD_TIME_MIN_SEC < SCREEN_HOLD_TIME_MAX_SEC)

# =============================================================================
# [N] 전환 속도 상수 (5개)
# =============================================================================
result.set_section("[N] 전환 속도 상수")

result.check("PRIMARY_BREAK_MAX_SEC = 5.0", PRIMARY_BREAK_MAX_SEC == 5.0)
result.check("SECONDARY_BREAK_MAX_SEC = 8.0", SECONDARY_BREAK_MAX_SEC == 8.0)
result.check("DEFENSIVE_TRANSITION_TARGET_SEC = 4.0", DEFENSIVE_TRANSITION_TARGET_SEC == 4.0)
result.check("FAST_BREAK_ADVANTAGE_MIN = 1", FAST_BREAK_ADVANTAGE_MIN == 1)
result.check("FAST_BREAK_BALL_SPEED_MIN = 3.5", FAST_BREAK_BALL_SPEED_MIN == 3.5)

result.check("PRIMARY < SECONDARY", PRIMARY_BREAK_MAX_SEC < SECONDARY_BREAK_MAX_SEC)
result.check("FAST_BREAK_ADVANTAGE_MIN int 타입", isinstance(FAST_BREAK_ADVANTAGE_MIN, int))
result.check("PRIMARY_BREAK_MAX_SEC float 타입", isinstance(PRIMARY_BREAK_MAX_SEC, float))

# =============================================================================
# [O] 스페이싱 상수 (7개)
# =============================================================================
result.set_section("[O] 스페이싱 상수")

result.check("SPACING_MIN_DISTANCE_M = 3.5", SPACING_MIN_DISTANCE_M == 3.5)
result.check("SPACING_OPTIMAL_DISTANCE_M = 4.5", SPACING_OPTIMAL_DISTANCE_M == 4.5)
result.check("SPACING_COLLAPSED_DISTANCE_M = 2.5", SPACING_COLLAPSED_DISTANCE_M == 2.5)
result.check("COURT_UTILIZATION_EXCELLENT = 0.55", COURT_UTILIZATION_EXCELLENT == 0.55)
result.check("COURT_UTILIZATION_GOOD = 0.45", COURT_UTILIZATION_GOOD == 0.45)
result.check("COURT_UTILIZATION_POOR = 0.30", COURT_UTILIZATION_POOR == 0.30)
result.check("DRIVE_LANE_MIN_WIDTH_M = 1.5", DRIVE_LANE_MIN_WIDTH_M == 1.5)

result.check("COLLAPSED < MIN < OPTIMAL",
             SPACING_COLLAPSED_DISTANCE_M < SPACING_MIN_DISTANCE_M < SPACING_OPTIMAL_DISTANCE_M)
result.check("POOR < GOOD < EXCELLENT (코트 활용)",
             COURT_UTILIZATION_POOR < COURT_UTILIZATION_GOOD < COURT_UTILIZATION_EXCELLENT)

# 코트 활용률 범위 (0~1)
for name, val in [
    ("EXCELLENT", COURT_UTILIZATION_EXCELLENT),
    ("GOOD", COURT_UTILIZATION_GOOD),
    ("POOR", COURT_UTILIZATION_POOR),
]:
    result.check(f"COURT_UTILIZATION_{name} ∈ (0, 1)", 0 < val < 1)

# =============================================================================
# [P] 모멘텀/런 상수 (6개)
# =============================================================================
result.set_section("[P] 모멘텀/런 상수")

result.check("SCORING_RUN_MIN_POINTS = 6", SCORING_RUN_MIN_POINTS == 6)
result.check("SCORING_RUN_MIN_UNANSWERED = 3", SCORING_RUN_MIN_UNANSWERED == 3)
result.check("MOMENTUM_SHIFT_THRESHOLD = 8", MOMENTUM_SHIFT_THRESHOLD == 8)
result.check("SCORING_DROUGHT_POSSESSIONS = 5", SCORING_DROUGHT_POSSESSIONS == 5)
result.check("MOMENTUM_DECAY_PER_MINUTE = 0.05", MOMENTUM_DECAY_PER_MINUTE == 0.05)
result.check("MOMENTUM_TIMEOUT_RESET_FACTOR = 0.3", MOMENTUM_TIMEOUT_RESET_FACTOR == 0.3)

result.check("SCORING_RUN_MIN_POINTS int 타입", isinstance(SCORING_RUN_MIN_POINTS, int))
result.check("MOMENTUM_DECAY_PER_MINUTE float 타입", isinstance(MOMENTUM_DECAY_PER_MINUTE, float))
result.check("MOMENTUM_TIMEOUT_RESET_FACTOR ∈ [0, 1]",
             0 <= MOMENTUM_TIMEOUT_RESET_FACTOR <= 1)
result.check("SCORING_RUN < MOMENTUM_SHIFT",
             SCORING_RUN_MIN_POINTS < MOMENTUM_SHIFT_THRESHOLD)

# =============================================================================
# [Q] 템포 상수 (3개)
# =============================================================================
result.set_section("[Q] 템포 상수")

result.check("TEMPO_FAST_THRESHOLD_SEC = 12.0", TEMPO_FAST_THRESHOLD_SEC == 12.0)
result.check("TEMPO_SLOW_THRESHOLD_SEC = 18.0", TEMPO_SLOW_THRESHOLD_SEC == 18.0)
result.check("HALFCOURT_SET_TIME_SEC = 8.0", HALFCOURT_SET_TIME_SEC == 8.0)
result.check("TEMPO_FAST < TEMPO_SLOW", TEMPO_FAST_THRESHOLD_SEC < TEMPO_SLOW_THRESHOLD_SEC)

# =============================================================================
# [R] 매치업/수비 상수 (9개)
# =============================================================================
result.set_section("[R] 매치업/수비 상수")

_matchup_params = {
    "MATCHUP_ASSIGNMENT_DISTANCE_M": (MATCHUP_ASSIGNMENT_DISTANCE_M, 3.0),
    "DEFENSIVE_BREAKDOWN_DISTANCE_M": (DEFENSIVE_BREAKDOWN_DISTANCE_M, 5.0),
    "CLOSEOUT_START_DISTANCE_M": (CLOSEOUT_START_DISTANCE_M, 3.0),
    "CLOSEOUT_SUCCESS_DISTANCE_M": (CLOSEOUT_SUCCESS_DISTANCE_M, 1.2),
    "CLOSEOUT_TARGET_TIME_SEC": (CLOSEOUT_TARGET_TIME_SEC, 1.0),
    "HELP_DEFENSE_TRIGGER_DISTANCE_M": (HELP_DEFENSE_TRIGGER_DISTANCE_M, 2.5),
    "HELP_RECOVERY_TARGET_SEC": (HELP_RECOVERY_TARGET_SEC, 1.5),
    "SHOT_CONTEST_EFFECTIVE_M": (SHOT_CONTEST_EFFECTIVE_M, 1.5),
    "HAND_UP_MIN_ANGLE_DEG": (HAND_UP_MIN_ANGLE_DEG, 120.0),
}
for name, (val, expected) in _matchup_params.items():
    result.check(f"{name} = {expected}", val == expected, f"실제: {val}")
    result.check(f"{name} float 타입", isinstance(val, float))
    result.check(f"{name} > 0", val > 0)

result.check("CLOSEOUT_SUCCESS < CLOSEOUT_START",
             CLOSEOUT_SUCCESS_DISTANCE_M < CLOSEOUT_START_DISTANCE_M)
result.check("MATCHUP < DEFENSIVE_BREAKDOWN",
             MATCHUP_ASSIGNMENT_DISTANCE_M < DEFENSIVE_BREAKDOWN_DISTANCE_M)

# =============================================================================
# [S] 드라이브/오프볼/리바운드/리드관리 상수
# =============================================================================
result.set_section("[S] 드라이브/오프볼/리바운드/리드관리 상수")

# 드라이브
result.check("DRIVE_START_SPEED_MIN = 2.5", DRIVE_START_SPEED_MIN == 2.5)
result.check("DRIVE_DIRECTION_ANGLE_DEG = 30.0", DRIVE_DIRECTION_ANGLE_DEG == 30.0)
result.check("DRIVE_MIN_DISTANCE_M = 1.5", DRIVE_MIN_DISTANCE_M == 1.5)
result.check("DRIVE_END_SPEED_THRESHOLD = 1.0", DRIVE_END_SPEED_THRESHOLD == 1.0)
result.check("DRIVE_KICKOUT_MAX_SEC = 2.0", DRIVE_KICKOUT_MAX_SEC == 2.0)
result.check("DRIVE_END < DRIVE_START (속도)", DRIVE_END_SPEED_THRESHOLD < DRIVE_START_SPEED_MIN)

# 오프볼
result.check("CUT_SPEED_MIN = 3.0", CUT_SPEED_MIN == 3.0)
result.check("CUT_DIRECTION_ANGLE_DEG = 45.0", CUT_DIRECTION_ANGLE_DEG == 45.0)
result.check("SCREEN_EXIT_SPEED_CHANGE = 1.5", SCREEN_EXIT_SPEED_CHANGE == 1.5)
result.check("CUT_DIRECTION_CHANGE_MIN_DEG = 60.0", CUT_DIRECTION_CHANGE_MIN_DEG == 60.0)

# 리바운드
result.check("BOX_OUT_EFFECTIVE_DISTANCE_M = 1.5", BOX_OUT_EFFECTIVE_DISTANCE_M == 1.5)
result.check("BOX_OUT_REACTION_TIME_SEC = 0.5", BOX_OUT_REACTION_TIME_SEC == 0.5)
result.check("LONG_REBOUND_DISTANCE_M = 4.0", LONG_REBOUND_DISTANCE_M == 4.0)
result.check("TIP_CHAIN_MAX_INTERVAL_SEC = 1.5", TIP_CHAIN_MAX_INTERVAL_SEC == 1.5)

# 리드 관리
result.check("CLOSE_GAME_MARGIN = 5", CLOSE_GAME_MARGIN == 5)
result.check("BLOWOUT_MARGIN = 20", BLOWOUT_MARGIN == 20)
result.check("COMEBACK_MIN_DURATION_SEC = 60.0", COMEBACK_MIN_DURATION_SEC == 60.0)
result.check("CLOSE_GAME_MARGIN int 타입", isinstance(CLOSE_GAME_MARGIN, int))
result.check("BLOWOUT_MARGIN int 타입", isinstance(BLOWOUT_MARGIN, int))
result.check("CLOSE < BLOWOUT", CLOSE_GAME_MARGIN < BLOWOUT_MARGIN)

# =============================================================================
# [T] classify_spacing_quality 함수
# =============================================================================
result.set_section("[T] classify_spacing_quality 함수")

# 기본 분류 테스트
result.check("6.0m -> EXCELLENT", classify_spacing_quality(6.0) == SpacingQuality.EXCELLENT)
result.check("4.5m -> EXCELLENT (경계)", classify_spacing_quality(4.5) == SpacingQuality.EXCELLENT)
result.check("4.0m -> GOOD", classify_spacing_quality(4.0) == SpacingQuality.GOOD)
result.check("3.5m -> GOOD (경계)", classify_spacing_quality(3.5) == SpacingQuality.GOOD)
result.check("3.0m -> AVERAGE", classify_spacing_quality(3.0) == SpacingQuality.AVERAGE)
result.check("2.5m -> POOR (경계)", classify_spacing_quality(2.5) == SpacingQuality.POOR)
result.check("2.0m -> COLLAPSED", classify_spacing_quality(2.0) == SpacingQuality.COLLAPSED)
result.check("1.0m -> COLLAPSED", classify_spacing_quality(1.0) == SpacingQuality.COLLAPSED)
result.check("0.0m -> COLLAPSED", classify_spacing_quality(0.0) == SpacingQuality.COLLAPSED)

# 반환 타입
result.check("반환 타입 = SpacingQuality", isinstance(classify_spacing_quality(3.0), SpacingQuality))

# 모든 가능한 반환값이 SpacingQuality 멤버
test_distances = [0.5, 1.5, 2.5, 3.0, 3.5, 4.5, 6.0]
for d in test_distances:
    q = classify_spacing_quality(d)
    result.check(f"classify({d}m) ∈ SpacingQuality", isinstance(q, SpacingQuality))

# =============================================================================
# [U] classify_transition_phase 함수
# =============================================================================
result.set_section("[U] classify_transition_phase 함수")

# 기본 분류 테스트
result.check("0.0s -> PRIMARY_BREAK", classify_transition_phase(0.0) == TransitionPhase.PRIMARY_BREAK)
result.check("3.0s -> PRIMARY_BREAK", classify_transition_phase(3.0) == TransitionPhase.PRIMARY_BREAK)
result.check("5.0s -> PRIMARY_BREAK (경계)", classify_transition_phase(5.0) == TransitionPhase.PRIMARY_BREAK)
result.check("5.1s -> SECONDARY_BREAK", classify_transition_phase(5.1) == TransitionPhase.SECONDARY_BREAK)
result.check("8.0s -> SECONDARY_BREAK (경계)", classify_transition_phase(8.0) == TransitionPhase.SECONDARY_BREAK)
result.check("8.1s -> EARLY_OFFENSE", classify_transition_phase(8.1) == TransitionPhase.EARLY_OFFENSE)
result.check("15.0s -> EARLY_OFFENSE", classify_transition_phase(15.0) == TransitionPhase.EARLY_OFFENSE)

# 반환 타입
result.check("반환 타입 = TransitionPhase", isinstance(classify_transition_phase(3.0), TransitionPhase))

# =============================================================================
# [V] is_scoring_run 함수 및 논리적 일관성
# =============================================================================
result.set_section("[V] is_scoring_run 함수 및 논리적 일관성")

# 기본 테스트
result.check("(6, 3) -> True", is_scoring_run(6, 3) is True)
result.check("(10, 5) -> True", is_scoring_run(10, 5) is True)
result.check("(5, 3) -> False (득점 미달)", is_scoring_run(5, 3) is False)
result.check("(6, 2) -> False (무득점 미달)", is_scoring_run(6, 2) is False)
result.check("(0, 0) -> False", is_scoring_run(0, 0) is False)
result.check("(100, 100) -> True (큰 값)", is_scoring_run(100, 100) is True)

# 반환 타입
result.check("반환 타입 = bool", isinstance(is_scoring_run(6, 3), bool))

# 논리적 일관성: Enum 동등성
result.check("SetPlayType.HORN == SetPlayType.HORN", SetPlayType.HORN == SetPlayType.HORN)
result.check("SetPlayType.HORN != SetPlayType.FLEX", SetPlayType.HORN != SetPlayType.FLEX)

# frozenset 불변성 (_SCREEN_PLAYS)
try:
    tc._SCREEN_PLAYS.add(SetPlayType.MOTION)  # type: ignore
    result.fail("frozenset 불변성", "add 성공 (불변이어야 함)")
except AttributeError:
    result.ok("frozenset 불변성 (add 시도 시 AttributeError)")

# Enum(value) 역방향 조회
result.check("SetPlayType('horn') == HORN", SetPlayType("horn") == SetPlayType.HORN)
result.check("TransitionPhase('primary_break') == PRIMARY_BREAK",
             TransitionPhase("primary_break") == TransitionPhase.PRIMARY_BREAK)
result.check("SpacingQuality('excellent') == EXCELLENT",
             SpacingQuality("excellent") == SpacingQuality.EXCELLENT)
result.check("TurnoverCategory('forced_live') == FORCED_LIVE",
             TurnoverCategory("forced_live") == TurnoverCategory.FORCED_LIVE)

# __all__ 존재 및 기본 검증
result.check("__all__ 속성 존재", hasattr(tc, "__all__"))
if hasattr(tc, "__all__"):
    all_exports = tc.__all__
    missing = [name for name in all_exports if not hasattr(tc, name)]
    result.check("모든 __all__ 항목이 모듈에 존재", len(missing) == 0, f"누락: {missing}")

# =============================================================================
sys.exit(0 if result.summary() else 1)
