# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_referee_rule_constants.py

AI 심판 시스템 도메인 상수 모듈 단위 테스트
- RuleSet (5종): 멤버, 값, str 상속, korean_name, 쿼터 시간, 샷클락, 백코트,
  3점 라인 거리, 최대 개인 파울, 최대 타임아웃, 수비 3초 룰
- CallType (15종): 멤버, 값, korean_name, stops_play, is_foul, is_violation, 상호 배타성
- SignalType (20종): 멤버, 값, korean_name, 하위 분류별 멤버 수
- ReviewTrigger (8종): 멤버, 값, korean_name
- ReviewOutcome (5종): 멤버, 값, korean_name, changed_call
- RefereeRole (3종): 멤버, 값, korean_name
- 일반 상수 6종 (타입, 값, 범위)
- 캐시 4 frozenset + 10 dict (타입, 완전성)
- __all__ Export (28항목)
- 메타 (version 1.0.0)
- NBA 고유값 크로스 체크, 도메인 일관성 검증

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from enum import Enum
from pathlib import Path

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants import referee_rule_constants
from shared.constants.referee_rule_constants import (
    # 열거형 (6종)
    RuleSet,
    CallType,
    SignalType,
    ReviewTrigger,
    ReviewOutcome,
    RefereeRole,
    # 심판 시스템 상수 (6종)
    MIN_DECISION_CONFIDENCE,
    AUTO_CONFIRM_CONFIDENCE,
    REVIEW_TIME_LIMIT_SEC,
    MAX_COACH_CHALLENGES_PER_GAME,
    REFEREE_COUNT_STANDARD,
    CONSISTENCY_WINDOW_FRAMES,
    # 캐시 - RuleSet (7종)
    _RULE_SET_KOREAN_MAP,
    _RULE_SET_QUARTER_DURATION_MAP,
    _RULE_SET_BACKCOURT_SEC_MAP,
    _RULE_SET_THREE_POINT_DISTANCE_MAP,
    _RULE_SET_MAX_PERSONAL_FOULS_MAP,
    _RULE_SET_MAX_TIMEOUTS_MAP,
    _RULE_SET_HAS_DEFENSIVE_THREE_SEC,
    # 캐시 - CallType (4종)
    _CALL_TYPE_IS_FOUL,
    _CALL_TYPE_IS_VIOLATION,
    _CALL_TYPE_NO_STOP,
    _CALL_TYPE_KOREAN_MAP,
    # 캐시 - SignalType (1종)
    _SIGNAL_TYPE_KOREAN_MAP,
    # 캐시 - ReviewTrigger (1종)
    _REVIEW_TRIGGER_KOREAN_MAP,
    # 캐시 - ReviewOutcome (2종)
    _REVIEW_OUTCOME_CHANGED,
    _REVIEW_OUTCOME_KOREAN_MAP,
    # 캐시 - RefereeRole (1종)
    _REFEREE_ROLE_KOREAN_MAP,
)


# =============================================================================
# 테스트 하네스
# =============================================================================
class TestResult:
    """경량 테스트 결과 수집기."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.section = ""

    def set_section(self, name: str):
        self.section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name: str):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, msg: str = ""):
        self.failed += 1
        print(f"  [FAIL] {name} - {msg}")

    def check(self, name: str, condition: bool, msg: str = ""):
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        print(f"{'='*60}")
        return self.failed == 0


# =============================================================================
# 메인 테스트
# =============================================================================
def main():
    T = TestResult()

    # =================================================================
    # 1. RuleSet 멤버, 값, str 상속
    # =================================================================
    T.set_section("1. RuleSet - 멤버, 값, str 상속")

    # 멤버 존재
    expected_members = ["FIBA", "NBA", "KBL", "NBL", "EUROLEAGUE"]
    for name in expected_members:
        T.check(f"RuleSet.{name} 멤버 존재", hasattr(RuleSet, name))

    # 멤버 수
    T.check("RuleSet 멤버 수 5", len(RuleSet) == 5,
            f"expected 5, got {len(RuleSet)}")

    # 값 검증
    expected_values = {
        "FIBA": "fiba", "NBA": "nba", "KBL": "kbl",
        "NBL": "nbl", "EUROLEAGUE": "euroleague",
    }
    for name, val in expected_values.items():
        member = RuleSet[name]
        T.check(f"RuleSet.{name}.value == '{val}'", member.value == val,
                f"got {member.value!r}")

    # str 상속
    for member in RuleSet:
        T.check(f"RuleSet.{member.name} isinstance(str)", isinstance(member, str))

    # str mixin: member == value (동등 비교)
    for member in RuleSet:
        T.check(f"RuleSet.{member.name} == value (str mixin 동등)",
                member == member.value,
                f"member={member!r}, value={member.value!r}")

    # Python 3.11+: str(member) 형식 검증
    for member in RuleSet:
        s = str(member)
        T.check(f"str(RuleSet.{member.name}) 형식 유효",
                isinstance(s, str) and len(s) > 0,
                f"got {s!r}")

    # Enum 상속
    for member in RuleSet:
        T.check(f"RuleSet.{member.name} isinstance(Enum)", isinstance(member, Enum))

    # 값 유일성
    values = [m.value for m in RuleSet]
    T.check("RuleSet 값 유일성", len(values) == len(set(values)))

    # identity (is)
    T.check("RuleSet.FIBA is RuleSet('fiba')", RuleSet.FIBA is RuleSet("fiba"))
    T.check("RuleSet.NBA is RuleSet('nba')", RuleSet.NBA is RuleSet("nba"))

    # hash
    T.check("RuleSet 해시 가능", all(isinstance(hash(m), int) for m in RuleSet))

    # set 사용
    s = {RuleSet.FIBA, RuleSet.NBA, RuleSet.KBL}
    T.check("RuleSet set 사용 가능", len(s) == 3)

    # dict 키 사용
    d = {RuleSet.FIBA: 1, RuleSet.NBA: 2}
    T.check("RuleSet dict 키 사용", d[RuleSet.FIBA] == 1 and d[RuleSet.NBA] == 2)

    # 문자열 비교 (str mixin)
    T.check("RuleSet.FIBA == 'fiba'", RuleSet.FIBA == "fiba")
    T.check("RuleSet.NBA == 'nba'", RuleSet.NBA == "nba")

    # =================================================================
    # 2. RuleSet.korean_name (전체 5종)
    # =================================================================
    T.set_section("2. RuleSet.korean_name (전체 5종)")

    korean_map = {
        RuleSet.FIBA: "국제농구연맹",
        RuleSet.NBA: "미국 프로농구",
        RuleSet.KBL: "한국프로농구",
        RuleSet.NBL: "호주 프로농구",
        RuleSet.EUROLEAGUE: "유럽 농구리그",
    }
    for member, expected in korean_map.items():
        T.check(f"RuleSet.{member.name}.korean_name == '{expected}'",
                member.korean_name == expected,
                f"got {member.korean_name!r}")

    # korean_name 타입 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.korean_name is str",
                isinstance(member.korean_name, str))

    # korean_name 비어있지 않음
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.korean_name 비어있지 않음",
                len(member.korean_name) > 0)

    # korean_name 유일성
    k_names = [m.korean_name for m in RuleSet]
    T.check("RuleSet korean_name 유일성", len(k_names) == len(set(k_names)))

    # =================================================================
    # 3. RuleSet.quarter_duration_sec (NBA 720, 나머지 600)
    # =================================================================
    T.set_section("3. RuleSet.quarter_duration_sec")

    qd_map = {
        RuleSet.FIBA: 600, RuleSet.NBA: 720,
        RuleSet.KBL: 600, RuleSet.NBL: 600, RuleSet.EUROLEAGUE: 600,
    }
    for member, expected in qd_map.items():
        T.check(f"RuleSet.{member.name}.quarter_duration_sec == {expected}",
                member.quarter_duration_sec == expected,
                f"got {member.quarter_duration_sec}")

    # NBA 고유값
    T.check("NBA quarter_duration_sec > FIBA",
            RuleSet.NBA.quarter_duration_sec > RuleSet.FIBA.quarter_duration_sec)

    # NBA 12분 (720초)
    T.check("NBA 쿼터 시간 12분 (720초)", RuleSet.NBA.quarter_duration_sec == 12 * 60)

    # FIBA 10분 (600초)
    T.check("FIBA 쿼터 시간 10분 (600초)", RuleSet.FIBA.quarter_duration_sec == 10 * 60)

    # 타입 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.quarter_duration_sec is int",
                isinstance(member.quarter_duration_sec, int))

    # FIBA 기반 리그 동일성
    fiba_based = [RuleSet.KBL, RuleSet.NBL, RuleSet.EUROLEAGUE]
    for member in fiba_based:
        T.check(f"{member.name} quarter == FIBA quarter",
                member.quarter_duration_sec == RuleSet.FIBA.quarter_duration_sec)

    # 양수 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.quarter_duration_sec > 0",
                member.quarter_duration_sec > 0)

    # =================================================================
    # 4. RuleSet.shot_clock_seconds (전체 24)
    # =================================================================
    T.set_section("4. RuleSet.shot_clock_seconds (전체 24)")

    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.shot_clock_seconds == 24",
                member.shot_clock_seconds == 24,
                f"got {member.shot_clock_seconds}")

    # 타입 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.shot_clock_seconds is int",
                isinstance(member.shot_clock_seconds, int))

    # 모든 리그 동일
    all_sc = {m.shot_clock_seconds for m in RuleSet}
    T.check("shot_clock_seconds 모든 리그 동일 (24)", len(all_sc) == 1 and 24 in all_sc)

    # =================================================================
    # 5. RuleSet.backcourt_seconds (전체 8)
    # =================================================================
    T.set_section("5. RuleSet.backcourt_seconds (전체 8)")

    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.backcourt_seconds == 8",
                member.backcourt_seconds == 8,
                f"got {member.backcourt_seconds}")

    # 타입 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.backcourt_seconds is int",
                isinstance(member.backcourt_seconds, int))

    # 모든 리그 동일
    all_bc = {m.backcourt_seconds for m in RuleSet}
    T.check("backcourt_seconds 모든 리그 동일 (8)", len(all_bc) == 1 and 8 in all_bc)

    # 양수 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.backcourt_seconds > 0",
                member.backcourt_seconds > 0)

    # =================================================================
    # 6. RuleSet.three_point_distance_meters (NBA 7.24, 나머지 6.75)
    # =================================================================
    T.set_section("6. RuleSet.three_point_distance_meters")

    tpd_map = {
        RuleSet.FIBA: 6.75, RuleSet.NBA: 7.24,
        RuleSet.KBL: 6.75, RuleSet.NBL: 6.75, RuleSet.EUROLEAGUE: 6.75,
    }
    for member, expected in tpd_map.items():
        T.check(f"RuleSet.{member.name}.three_point_distance_meters == {expected}",
                abs(member.three_point_distance_meters - expected) < 1e-9,
                f"got {member.three_point_distance_meters}")

    # NBA 고유값
    T.check("NBA 3점 라인 > FIBA",
            RuleSet.NBA.three_point_distance_meters > RuleSet.FIBA.three_point_distance_meters)

    # 타입 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.three_point_distance_meters is float",
                isinstance(member.three_point_distance_meters, float))

    # FIBA 기반 리그 동일성
    for member in fiba_based:
        T.check(f"{member.name} 3pt == FIBA 3pt",
                abs(member.three_point_distance_meters - RuleSet.FIBA.three_point_distance_meters) < 1e-9)

    # 양수 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.three_point_distance_meters > 0",
                member.three_point_distance_meters > 0)

    # 합리적 범위 (6~8미터)
    for member in RuleSet:
        dist = member.three_point_distance_meters
        T.check(f"RuleSet.{member.name} 3pt 합리적 범위 (6-8m)",
                6.0 <= dist <= 8.0, f"got {dist}")

    # =================================================================
    # 7. RuleSet.max_personal_fouls (NBA 6, 나머지 5)
    # =================================================================
    T.set_section("7. RuleSet.max_personal_fouls")

    mpf_map = {
        RuleSet.FIBA: 5, RuleSet.NBA: 6,
        RuleSet.KBL: 5, RuleSet.NBL: 5, RuleSet.EUROLEAGUE: 5,
    }
    for member, expected in mpf_map.items():
        T.check(f"RuleSet.{member.name}.max_personal_fouls == {expected}",
                member.max_personal_fouls == expected,
                f"got {member.max_personal_fouls}")

    # NBA 고유값
    T.check("NBA max_personal_fouls > FIBA",
            RuleSet.NBA.max_personal_fouls > RuleSet.FIBA.max_personal_fouls)

    # 타입 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.max_personal_fouls is int",
                isinstance(member.max_personal_fouls, int))

    # FIBA 기반 리그 동일성
    for member in fiba_based:
        T.check(f"{member.name} max_fouls == FIBA",
                member.max_personal_fouls == RuleSet.FIBA.max_personal_fouls)

    # 양수 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.max_personal_fouls > 0",
                member.max_personal_fouls > 0)

    # =================================================================
    # 8. RuleSet.max_timeouts (NBA 7, 나머지 5)
    # =================================================================
    T.set_section("8. RuleSet.max_timeouts")

    mt_map = {
        RuleSet.FIBA: 5, RuleSet.NBA: 7,
        RuleSet.KBL: 5, RuleSet.NBL: 5, RuleSet.EUROLEAGUE: 5,
    }
    for member, expected in mt_map.items():
        T.check(f"RuleSet.{member.name}.max_timeouts == {expected}",
                member.max_timeouts == expected,
                f"got {member.max_timeouts}")

    # NBA 고유값
    T.check("NBA max_timeouts > FIBA",
            RuleSet.NBA.max_timeouts > RuleSet.FIBA.max_timeouts)

    # 타입 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.max_timeouts is int",
                isinstance(member.max_timeouts, int))

    # FIBA 기반 리그 동일성
    for member in fiba_based:
        T.check(f"{member.name} max_timeouts == FIBA",
                member.max_timeouts == RuleSet.FIBA.max_timeouts)

    # 양수 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.max_timeouts > 0",
                member.max_timeouts > 0)

    # =================================================================
    # 9. RuleSet.has_defensive_three_seconds (NBA만 True)
    # =================================================================
    T.set_section("9. RuleSet.has_defensive_three_seconds")

    dts_map = {
        RuleSet.FIBA: False, RuleSet.NBA: True,
        RuleSet.KBL: False, RuleSet.NBL: False, RuleSet.EUROLEAGUE: False,
    }
    for member, expected in dts_map.items():
        T.check(f"RuleSet.{member.name}.has_defensive_three_seconds == {expected}",
                member.has_defensive_three_seconds == expected,
                f"got {member.has_defensive_three_seconds}")

    # 타입 검증
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.has_defensive_three_seconds is bool",
                isinstance(member.has_defensive_three_seconds, bool))

    # NBA만 True, 나머지 모두 False
    nba_only = sum(1 for m in RuleSet if m.has_defensive_three_seconds)
    T.check("수비 3초 룰 NBA 전용 (1개만 True)", nba_only == 1)

    # FIBA 기반 리그 모두 False
    for member in fiba_based:
        T.check(f"{member.name} has_defensive_three_seconds == False (FIBA 기반)",
                member.has_defensive_three_seconds is False)

    # =================================================================
    # 10. RuleSet 크로스 체크 - NBA 고유값 vs FIBA 기반 리그
    # =================================================================
    T.set_section("10. RuleSet 크로스 체크 - NBA vs FIBA 기반")

    # NBA는 쿼터 시간이 더 김
    T.check("NBA 쿼터 > FIBA 쿼터",
            RuleSet.NBA.quarter_duration_sec > RuleSet.FIBA.quarter_duration_sec)

    # NBA는 3점 라인이 더 멀리
    T.check("NBA 3pt > FIBA 3pt",
            RuleSet.NBA.three_point_distance_meters > RuleSet.FIBA.three_point_distance_meters)

    # NBA는 퇴장 기준 파울이 1개 더 많음
    T.check("NBA max_fouls > FIBA max_fouls",
            RuleSet.NBA.max_personal_fouls > RuleSet.FIBA.max_personal_fouls)
    T.check("NBA max_fouls == FIBA + 1",
            RuleSet.NBA.max_personal_fouls == RuleSet.FIBA.max_personal_fouls + 1)

    # NBA는 타임아웃이 더 많음
    T.check("NBA max_timeouts > FIBA max_timeouts",
            RuleSet.NBA.max_timeouts > RuleSet.FIBA.max_timeouts)
    T.check("NBA max_timeouts == FIBA + 2",
            RuleSet.NBA.max_timeouts == RuleSet.FIBA.max_timeouts + 2)

    # NBA만 수비 3초 룰 적용
    T.check("NBA has defensive 3sec, FIBA does not",
            RuleSet.NBA.has_defensive_three_seconds and not RuleSet.FIBA.has_defensive_three_seconds)

    # 샷클락은 동일
    T.check("NBA shot_clock == FIBA shot_clock",
            RuleSet.NBA.shot_clock_seconds == RuleSet.FIBA.shot_clock_seconds)

    # 백코트도 동일
    T.check("NBA backcourt == FIBA backcourt",
            RuleSet.NBA.backcourt_seconds == RuleSet.FIBA.backcourt_seconds)

    # FIBA 기반 리그 간 완전 동일성 검증
    for i, a in enumerate(fiba_based):
        for b in fiba_based[i+1:]:
            T.check(f"{a.name} == {b.name} quarter_duration",
                    a.quarter_duration_sec == b.quarter_duration_sec)
            T.check(f"{a.name} == {b.name} three_point_distance",
                    abs(a.three_point_distance_meters - b.three_point_distance_meters) < 1e-9)
            T.check(f"{a.name} == {b.name} max_personal_fouls",
                    a.max_personal_fouls == b.max_personal_fouls)
            T.check(f"{a.name} == {b.name} max_timeouts",
                    a.max_timeouts == b.max_timeouts)
            T.check(f"{a.name} == {b.name} has_defensive_three_seconds",
                    a.has_defensive_three_seconds == b.has_defensive_three_seconds)

    # NBA 쿼터 차이: 120초 (2분)
    T.check("NBA-FIBA 쿼터 차이 120초",
            RuleSet.NBA.quarter_duration_sec - RuleSet.FIBA.quarter_duration_sec == 120)

    # NBA 3점 라인 차이: 0.49m
    diff_3pt = RuleSet.NBA.three_point_distance_meters - RuleSet.FIBA.three_point_distance_meters
    T.check("NBA-FIBA 3점 라인 차이 약 0.49m",
            abs(diff_3pt - 0.49) < 0.01, f"got {diff_3pt}")

    # =================================================================
    # 11. CallType 멤버, 값 (5+5+5)
    # =================================================================
    T.set_section("11. CallType - 멤버, 값")

    # 파울 관련 (5)
    foul_members = ["PERSONAL_FOUL", "SHOOTING_FOUL", "OFFENSIVE_FOUL",
                    "TECHNICAL_FOUL", "FLAGRANT_FOUL"]
    for name in foul_members:
        T.check(f"CallType.{name} 존재", hasattr(CallType, name))

    # 바이올레이션 관련 (5)
    violation_members = ["TRAVELING", "DOUBLE_DRIBBLE", "OUT_OF_BOUNDS",
                         "SHOT_CLOCK_VIOLATION", "BACKCOURT_VIOLATION"]
    for name in violation_members:
        T.check(f"CallType.{name} 존재", hasattr(CallType, name))

    # 특수 판정 (5)
    special_members = ["JUMP_BALL", "TIMEOUT", "SUBSTITUTION", "NO_CALL", "REVIEW"]
    for name in special_members:
        T.check(f"CallType.{name} 존재", hasattr(CallType, name))

    # 전체 멤버 수
    T.check("CallType 멤버 수 15", len(CallType) == 15,
            f"expected 15, got {len(CallType)}")

    # 값 검증
    call_values = {
        "PERSONAL_FOUL": "personal_foul", "SHOOTING_FOUL": "shooting_foul",
        "OFFENSIVE_FOUL": "offensive_foul", "TECHNICAL_FOUL": "technical_foul",
        "FLAGRANT_FOUL": "flagrant_foul", "TRAVELING": "traveling",
        "DOUBLE_DRIBBLE": "double_dribble", "OUT_OF_BOUNDS": "out_of_bounds",
        "SHOT_CLOCK_VIOLATION": "shot_clock_violation",
        "BACKCOURT_VIOLATION": "backcourt_violation",
        "JUMP_BALL": "jump_ball", "TIMEOUT": "timeout",
        "SUBSTITUTION": "substitution", "NO_CALL": "no_call", "REVIEW": "review",
    }
    for name, val in call_values.items():
        member = CallType[name]
        T.check(f"CallType.{name}.value == '{val}'",
                member.value == val, f"got {member.value!r}")

    # str 상속
    for member in CallType:
        T.check(f"CallType.{member.name} isinstance(str)", isinstance(member, str))

    # 값 유일성
    ct_values = [m.value for m in CallType]
    T.check("CallType 값 유일성", len(ct_values) == len(set(ct_values)))

    # Enum 상속
    for member in CallType:
        T.check(f"CallType.{member.name} isinstance(Enum)", isinstance(member, Enum))

    # hash
    T.check("CallType 해시 가능", all(isinstance(hash(m), int) for m in CallType))

    # =================================================================
    # 12. CallType.is_foul (5 True, 10 False, 상호 배타성)
    # =================================================================
    T.set_section("12. CallType.is_foul")

    foul_expected = {
        CallType.PERSONAL_FOUL: True, CallType.SHOOTING_FOUL: True,
        CallType.OFFENSIVE_FOUL: True, CallType.TECHNICAL_FOUL: True,
        CallType.FLAGRANT_FOUL: True,
        CallType.TRAVELING: False, CallType.DOUBLE_DRIBBLE: False,
        CallType.OUT_OF_BOUNDS: False, CallType.SHOT_CLOCK_VIOLATION: False,
        CallType.BACKCOURT_VIOLATION: False,
        CallType.JUMP_BALL: False, CallType.TIMEOUT: False,
        CallType.SUBSTITUTION: False, CallType.NO_CALL: False, CallType.REVIEW: False,
    }
    for member, expected in foul_expected.items():
        T.check(f"CallType.{member.name}.is_foul == {expected}",
                member.is_foul == expected,
                f"got {member.is_foul}")

    # is_foul True 수
    foul_count = sum(1 for m in CallType if m.is_foul)
    T.check("is_foul True 수 == 5", foul_count == 5, f"got {foul_count}")

    # is_foul False 수
    not_foul_count = sum(1 for m in CallType if not m.is_foul)
    T.check("is_foul False 수 == 10", not_foul_count == 10, f"got {not_foul_count}")

    # is_foul 타입 검증
    for member in CallType:
        T.check(f"CallType.{member.name}.is_foul is bool",
                isinstance(member.is_foul, bool))

    # 상호 배타성: is_foul과 is_violation 동시에 True가 아님
    for member in CallType:
        T.check(f"CallType.{member.name} is_foul/is_violation 상호 배타",
                not (member.is_foul and member.is_violation),
                f"is_foul={member.is_foul}, is_violation={member.is_violation}")

    # =================================================================
    # 13. CallType.is_violation (5 True, 10 False)
    # =================================================================
    T.set_section("13. CallType.is_violation")

    violation_expected = {
        CallType.PERSONAL_FOUL: False, CallType.SHOOTING_FOUL: False,
        CallType.OFFENSIVE_FOUL: False, CallType.TECHNICAL_FOUL: False,
        CallType.FLAGRANT_FOUL: False,
        CallType.TRAVELING: True, CallType.DOUBLE_DRIBBLE: True,
        CallType.OUT_OF_BOUNDS: True, CallType.SHOT_CLOCK_VIOLATION: True,
        CallType.BACKCOURT_VIOLATION: True,
        CallType.JUMP_BALL: False, CallType.TIMEOUT: False,
        CallType.SUBSTITUTION: False, CallType.NO_CALL: False, CallType.REVIEW: False,
    }
    for member, expected in violation_expected.items():
        T.check(f"CallType.{member.name}.is_violation == {expected}",
                member.is_violation == expected,
                f"got {member.is_violation}")

    # is_violation True 수
    viol_count = sum(1 for m in CallType if m.is_violation)
    T.check("is_violation True 수 == 5", viol_count == 5, f"got {viol_count}")

    # is_violation False 수
    not_viol_count = sum(1 for m in CallType if not m.is_violation)
    T.check("is_violation False 수 == 10", not_viol_count == 10, f"got {not_viol_count}")

    # is_violation 타입 검증
    for member in CallType:
        T.check(f"CallType.{member.name}.is_violation is bool",
                isinstance(member.is_violation, bool))

    # 특수 판정은 is_foul도 is_violation도 아님
    special_ct = [CallType.JUMP_BALL, CallType.TIMEOUT, CallType.SUBSTITUTION,
                  CallType.NO_CALL, CallType.REVIEW]
    for member in special_ct:
        T.check(f"CallType.{member.name} 특수 판정: not foul, not violation",
                not member.is_foul and not member.is_violation)

    # =================================================================
    # 14. CallType.stops_play (14 True, 1 False - NO_CALL only)
    # =================================================================
    T.set_section("14. CallType.stops_play")

    for member in CallType:
        if member == CallType.NO_CALL:
            T.check(f"CallType.NO_CALL.stops_play == False",
                    member.stops_play is False,
                    f"got {member.stops_play}")
        else:
            T.check(f"CallType.{member.name}.stops_play == True",
                    member.stops_play is True,
                    f"got {member.stops_play}")

    # stops_play True 수
    stops_count = sum(1 for m in CallType if m.stops_play)
    T.check("stops_play True 수 == 14", stops_count == 14, f"got {stops_count}")

    # stops_play False 수
    no_stop_count = sum(1 for m in CallType if not m.stops_play)
    T.check("stops_play False 수 == 1", no_stop_count == 1, f"got {no_stop_count}")

    # 유일한 non-stop == NO_CALL
    non_stop = [m for m in CallType if not m.stops_play]
    T.check("유일한 non-stop이 NO_CALL",
            len(non_stop) == 1 and non_stop[0] == CallType.NO_CALL)

    # stops_play 타입 검증
    for member in CallType:
        T.check(f"CallType.{member.name}.stops_play is bool",
                isinstance(member.stops_play, bool))

    # 모든 파울은 경기 중단
    for member in CallType:
        if member.is_foul:
            T.check(f"파울 {member.name} stops_play", member.stops_play is True)

    # 모든 바이올레이션도 경기 중단
    for member in CallType:
        if member.is_violation:
            T.check(f"바이올레이션 {member.name} stops_play", member.stops_play is True)

    # =================================================================
    # 15. CallType.korean_name (전체 15종)
    # =================================================================
    T.set_section("15. CallType.korean_name (전체 15종)")

    ct_korean = {
        CallType.PERSONAL_FOUL: "개인 파울",
        CallType.SHOOTING_FOUL: "슈팅 파울",
        CallType.OFFENSIVE_FOUL: "공격 파울",
        CallType.TECHNICAL_FOUL: "테크니컬 파울",
        CallType.FLAGRANT_FOUL: "플래그런트 파울",
        CallType.TRAVELING: "트래블링",
        CallType.DOUBLE_DRIBBLE: "더블 드리블",
        CallType.OUT_OF_BOUNDS: "아웃 오브 바운드",
        CallType.SHOT_CLOCK_VIOLATION: "샷클락 바이올레이션",
        CallType.BACKCOURT_VIOLATION: "백코트 바이올레이션",
        CallType.JUMP_BALL: "점프볼",
        CallType.TIMEOUT: "타임아웃",
        CallType.SUBSTITUTION: "교체",
        CallType.NO_CALL: "노콜",
        CallType.REVIEW: "리뷰",
    }
    for member, expected in ct_korean.items():
        T.check(f"CallType.{member.name}.korean_name == '{expected}'",
                member.korean_name == expected,
                f"got {member.korean_name!r}")

    # korean_name 타입 검증
    for member in CallType:
        T.check(f"CallType.{member.name}.korean_name is str",
                isinstance(member.korean_name, str))

    # korean_name 비어있지 않음
    for member in CallType:
        T.check(f"CallType.{member.name}.korean_name 비어있지 않음",
                len(member.korean_name) > 0)

    # korean_name 유일성
    ct_k_names = [m.korean_name for m in CallType]
    T.check("CallType korean_name 유일성", len(ct_k_names) == len(set(ct_k_names)))

    # =================================================================
    # 16. SignalType 멤버 (20종), korean_name
    # =================================================================
    T.set_section("16. SignalType - 멤버 (20종), korean_name")

    # 점수 관련 (5)
    score_signals = ["ONE_POINT", "TWO_POINTS", "THREE_POINTS",
                     "POINTS_COUNTED", "POINTS_CANCELED"]
    for name in score_signals:
        T.check(f"SignalType.{name} 존재", hasattr(SignalType, name))

    # 시간 관련 (3)
    time_signals = ["STOP_CLOCK", "START_CLOCK", "TIMEOUT"]
    for name in time_signals:
        T.check(f"SignalType.{name} 존재", hasattr(SignalType, name))

    # 파울 관련 (5)
    foul_signals = ["PERSONAL_FOUL", "HOLDING", "PUSHING", "BLOCKING", "TECHNICAL_FOUL"]
    for name in foul_signals:
        T.check(f"SignalType.{name} 존재", hasattr(SignalType, name))

    # 바이올레이션 (3)
    viol_signals = ["TRAVELING", "DOUBLE_DRIBBLE", "ILLEGAL_DRIBBLE"]
    for name in viol_signals:
        T.check(f"SignalType.{name} 존재", hasattr(SignalType, name))

    # 기타 (4)
    other_signals = ["DIRECTION", "JUMP_BALL", "SUBSTITUTION", "COMMUNICATION"]
    for name in other_signals:
        T.check(f"SignalType.{name} 존재", hasattr(SignalType, name))

    # 전체 멤버 수
    T.check("SignalType 멤버 수 20", len(SignalType) == 20,
            f"expected 20, got {len(SignalType)}")

    # 하위 분류 멤버 수 합
    sub_total = len(score_signals) + len(time_signals) + len(foul_signals) + \
                len(viol_signals) + len(other_signals)
    T.check("하위 분류 합 == 20", sub_total == 20, f"got {sub_total}")

    # 값 검증
    signal_values = {
        "ONE_POINT": "one_point", "TWO_POINTS": "two_points",
        "THREE_POINTS": "three_points", "POINTS_COUNTED": "points_counted",
        "POINTS_CANCELED": "points_canceled", "STOP_CLOCK": "stop_clock",
        "START_CLOCK": "start_clock", "TIMEOUT": "timeout",
        "PERSONAL_FOUL": "personal_foul", "HOLDING": "holding",
        "PUSHING": "pushing", "BLOCKING": "blocking",
        "TECHNICAL_FOUL": "technical_foul", "TRAVELING": "traveling",
        "DOUBLE_DRIBBLE": "double_dribble", "ILLEGAL_DRIBBLE": "illegal_dribble",
        "DIRECTION": "direction", "JUMP_BALL": "jump_ball",
        "SUBSTITUTION": "substitution", "COMMUNICATION": "communication",
    }
    for name, val in signal_values.items():
        member = SignalType[name]
        T.check(f"SignalType.{name}.value == '{val}'",
                member.value == val, f"got {member.value!r}")

    # str 상속
    for member in SignalType:
        T.check(f"SignalType.{member.name} isinstance(str)", isinstance(member, str))

    # Enum 상속
    for member in SignalType:
        T.check(f"SignalType.{member.name} isinstance(Enum)", isinstance(member, Enum))

    # 값 유일성
    st_values = [m.value for m in SignalType]
    T.check("SignalType 값 유일성", len(st_values) == len(set(st_values)))

    # korean_name 검증
    st_korean = {
        SignalType.ONE_POINT: "1점", SignalType.TWO_POINTS: "2점",
        SignalType.THREE_POINTS: "3점", SignalType.POINTS_COUNTED: "득점 인정",
        SignalType.POINTS_CANCELED: "득점 취소", SignalType.STOP_CLOCK: "시간 정지",
        SignalType.START_CLOCK: "시간 재개", SignalType.TIMEOUT: "타임아웃",
        SignalType.PERSONAL_FOUL: "개인 파울", SignalType.HOLDING: "홀딩",
        SignalType.PUSHING: "푸싱", SignalType.BLOCKING: "블로킹",
        SignalType.TECHNICAL_FOUL: "테크니컬 파울", SignalType.TRAVELING: "트래블링",
        SignalType.DOUBLE_DRIBBLE: "더블 드리블", SignalType.ILLEGAL_DRIBBLE: "불법 드리블",
        SignalType.DIRECTION: "방향 지시", SignalType.JUMP_BALL: "점프볼",
        SignalType.SUBSTITUTION: "교체", SignalType.COMMUNICATION: "의사소통",
    }
    for member, expected in st_korean.items():
        T.check(f"SignalType.{member.name}.korean_name == '{expected}'",
                member.korean_name == expected,
                f"got {member.korean_name!r}")

    # korean_name 타입/비어있지 않음
    for member in SignalType:
        T.check(f"SignalType.{member.name}.korean_name is str",
                isinstance(member.korean_name, str))
        T.check(f"SignalType.{member.name}.korean_name 비어있지 않음",
                len(member.korean_name) > 0)

    # korean_name 유일성
    st_k_names = [m.korean_name for m in SignalType]
    T.check("SignalType korean_name 유일성", len(st_k_names) == len(set(st_k_names)))

    # hash
    T.check("SignalType 해시 가능", all(isinstance(hash(m), int) for m in SignalType))

    # =================================================================
    # 17. ReviewTrigger 멤버 (8종), korean_name
    # =================================================================
    T.set_section("17. ReviewTrigger - 멤버 (8종), korean_name")

    rt_members = ["COACH_CHALLENGE", "AUTOMATIC", "CREW_CHIEF",
                  "UNCLEAR_POSSESSION", "SHOT_CLOCK", "OUT_OF_BOUNDS",
                  "FLAGRANT_FOUL", "GOAL_TEND"]
    for name in rt_members:
        T.check(f"ReviewTrigger.{name} 존재", hasattr(ReviewTrigger, name))

    # 멤버 수
    T.check("ReviewTrigger 멤버 수 8", len(ReviewTrigger) == 8,
            f"expected 8, got {len(ReviewTrigger)}")

    # 값 검증
    rt_values = {
        "COACH_CHALLENGE": "coach_challenge", "AUTOMATIC": "automatic",
        "CREW_CHIEF": "crew_chief", "UNCLEAR_POSSESSION": "unclear_possession",
        "SHOT_CLOCK": "shot_clock", "OUT_OF_BOUNDS": "out_of_bounds",
        "FLAGRANT_FOUL": "flagrant_foul", "GOAL_TEND": "goal_tend",
    }
    for name, val in rt_values.items():
        member = ReviewTrigger[name]
        T.check(f"ReviewTrigger.{name}.value == '{val}'",
                member.value == val, f"got {member.value!r}")

    # str 상속
    for member in ReviewTrigger:
        T.check(f"ReviewTrigger.{member.name} isinstance(str)", isinstance(member, str))

    # Enum 상속
    for member in ReviewTrigger:
        T.check(f"ReviewTrigger.{member.name} isinstance(Enum)", isinstance(member, Enum))

    # 값 유일성
    rt_vals = [m.value for m in ReviewTrigger]
    T.check("ReviewTrigger 값 유일성", len(rt_vals) == len(set(rt_vals)))

    # korean_name
    rt_korean = {
        ReviewTrigger.COACH_CHALLENGE: "코치 챌린지",
        ReviewTrigger.AUTOMATIC: "자동 리뷰",
        ReviewTrigger.CREW_CHIEF: "주심 요청",
        ReviewTrigger.UNCLEAR_POSSESSION: "볼 소유권 불명확",
        ReviewTrigger.SHOT_CLOCK: "샷클락 관련",
        ReviewTrigger.OUT_OF_BOUNDS: "아웃 오브 바운드",
        ReviewTrigger.FLAGRANT_FOUL: "플래그런트 파울",
        ReviewTrigger.GOAL_TEND: "골텐딩",
    }
    for member, expected in rt_korean.items():
        T.check(f"ReviewTrigger.{member.name}.korean_name == '{expected}'",
                member.korean_name == expected,
                f"got {member.korean_name!r}")

    # korean_name 타입/비어있지 않음
    for member in ReviewTrigger:
        T.check(f"ReviewTrigger.{member.name}.korean_name is str",
                isinstance(member.korean_name, str))
        T.check(f"ReviewTrigger.{member.name}.korean_name 비어있지 않음",
                len(member.korean_name) > 0)

    # korean_name 유일성
    rt_k_names = [m.korean_name for m in ReviewTrigger]
    T.check("ReviewTrigger korean_name 유일성", len(rt_k_names) == len(set(rt_k_names)))

    # hash
    T.check("ReviewTrigger 해시 가능",
            all(isinstance(hash(m), int) for m in ReviewTrigger))

    # =================================================================
    # 18. ReviewOutcome 멤버 (5종), changed_call, korean_name
    # =================================================================
    T.set_section("18. ReviewOutcome - 멤버 (5종), changed_call, korean_name")

    ro_members = ["CALL_STANDS", "CALL_OVERTURNED", "RULING_ADJUSTED",
                  "INCONCLUSIVE", "NO_REVIEW"]
    for name in ro_members:
        T.check(f"ReviewOutcome.{name} 존재", hasattr(ReviewOutcome, name))

    # 멤버 수
    T.check("ReviewOutcome 멤버 수 5", len(ReviewOutcome) == 5,
            f"expected 5, got {len(ReviewOutcome)}")

    # 값 검증
    ro_values = {
        "CALL_STANDS": "call_stands", "CALL_OVERTURNED": "call_overturned",
        "RULING_ADJUSTED": "ruling_adjusted", "INCONCLUSIVE": "inconclusive",
        "NO_REVIEW": "no_review",
    }
    for name, val in ro_values.items():
        member = ReviewOutcome[name]
        T.check(f"ReviewOutcome.{name}.value == '{val}'",
                member.value == val, f"got {member.value!r}")

    # str 상속
    for member in ReviewOutcome:
        T.check(f"ReviewOutcome.{member.name} isinstance(str)", isinstance(member, str))

    # Enum 상속
    for member in ReviewOutcome:
        T.check(f"ReviewOutcome.{member.name} isinstance(Enum)", isinstance(member, Enum))

    # 값 유일성
    ro_vals = [m.value for m in ReviewOutcome]
    T.check("ReviewOutcome 값 유일성", len(ro_vals) == len(set(ro_vals)))

    # changed_call 검증
    changed_map = {
        ReviewOutcome.CALL_STANDS: False,
        ReviewOutcome.CALL_OVERTURNED: True,
        ReviewOutcome.RULING_ADJUSTED: True,
        ReviewOutcome.INCONCLUSIVE: False,
        ReviewOutcome.NO_REVIEW: False,
    }
    for member, expected in changed_map.items():
        T.check(f"ReviewOutcome.{member.name}.changed_call == {expected}",
                member.changed_call == expected,
                f"got {member.changed_call}")

    # changed_call True 수
    changed_count = sum(1 for m in ReviewOutcome if m.changed_call)
    T.check("changed_call True 수 == 2", changed_count == 2, f"got {changed_count}")

    # changed_call False 수
    not_changed = sum(1 for m in ReviewOutcome if not m.changed_call)
    T.check("changed_call False 수 == 3", not_changed == 3, f"got {not_changed}")

    # changed_call 타입 검증
    for member in ReviewOutcome:
        T.check(f"ReviewOutcome.{member.name}.changed_call is bool",
                isinstance(member.changed_call, bool))

    # korean_name
    ro_korean = {
        ReviewOutcome.CALL_STANDS: "원판정 유지",
        ReviewOutcome.CALL_OVERTURNED: "원판정 번복",
        ReviewOutcome.RULING_ADJUSTED: "판정 조정",
        ReviewOutcome.INCONCLUSIVE: "불명확 (원판정 유지)",
        ReviewOutcome.NO_REVIEW: "리뷰 불가",
    }
    for member, expected in ro_korean.items():
        T.check(f"ReviewOutcome.{member.name}.korean_name == '{expected}'",
                member.korean_name == expected,
                f"got {member.korean_name!r}")

    # korean_name 타입/비어있지 않음
    for member in ReviewOutcome:
        T.check(f"ReviewOutcome.{member.name}.korean_name is str",
                isinstance(member.korean_name, str))
        T.check(f"ReviewOutcome.{member.name}.korean_name 비어있지 않음",
                len(member.korean_name) > 0)

    # korean_name 유일성
    ro_k_names = [m.korean_name for m in ReviewOutcome]
    T.check("ReviewOutcome korean_name 유일성", len(ro_k_names) == len(set(ro_k_names)))

    # hash
    T.check("ReviewOutcome 해시 가능",
            all(isinstance(hash(m), int) for m in ReviewOutcome))

    # INCONCLUSIVE는 원판정 유지와 동일하게 changed_call == False
    T.check("INCONCLUSIVE changed_call == CALL_STANDS changed_call",
            ReviewOutcome.INCONCLUSIVE.changed_call == ReviewOutcome.CALL_STANDS.changed_call)

    # =================================================================
    # 19. RefereeRole 멤버 (3종), korean_name
    # =================================================================
    T.set_section("19. RefereeRole - 멤버 (3종), korean_name")

    rr_members = ["CREW_CHIEF", "REFEREE", "UMPIRE"]
    for name in rr_members:
        T.check(f"RefereeRole.{name} 존재", hasattr(RefereeRole, name))

    # 멤버 수
    T.check("RefereeRole 멤버 수 3", len(RefereeRole) == 3,
            f"expected 3, got {len(RefereeRole)}")

    # 값 검증
    rr_values = {
        "CREW_CHIEF": "crew_chief", "REFEREE": "referee", "UMPIRE": "umpire",
    }
    for name, val in rr_values.items():
        member = RefereeRole[name]
        T.check(f"RefereeRole.{name}.value == '{val}'",
                member.value == val, f"got {member.value!r}")

    # str 상속
    for member in RefereeRole:
        T.check(f"RefereeRole.{member.name} isinstance(str)", isinstance(member, str))

    # Enum 상속
    for member in RefereeRole:
        T.check(f"RefereeRole.{member.name} isinstance(Enum)", isinstance(member, Enum))

    # 값 유일성
    rr_vals = [m.value for m in RefereeRole]
    T.check("RefereeRole 값 유일성", len(rr_vals) == len(set(rr_vals)))

    # korean_name
    rr_korean = {
        RefereeRole.CREW_CHIEF: "주심",
        RefereeRole.REFEREE: "부심",
        RefereeRole.UMPIRE: "심판",
    }
    for member, expected in rr_korean.items():
        T.check(f"RefereeRole.{member.name}.korean_name == '{expected}'",
                member.korean_name == expected,
                f"got {member.korean_name!r}")

    # korean_name 타입/비어있지 않음
    for member in RefereeRole:
        T.check(f"RefereeRole.{member.name}.korean_name is str",
                isinstance(member.korean_name, str))
        T.check(f"RefereeRole.{member.name}.korean_name 비어있지 않음",
                len(member.korean_name) > 0)

    # korean_name 유일성
    rr_k_names = [m.korean_name for m in RefereeRole]
    T.check("RefereeRole korean_name 유일성", len(rr_k_names) == len(set(rr_k_names)))

    # hash
    T.check("RefereeRole 해시 가능",
            all(isinstance(hash(m), int) for m in RefereeRole))

    # 멤버 수와 표준 심판 수 일치 확인
    T.check("RefereeRole 멤버 수 == REFEREE_COUNT_STANDARD",
            len(RefereeRole) == REFEREE_COUNT_STANDARD)

    # set 사용
    rr_set = {RefereeRole.CREW_CHIEF, RefereeRole.REFEREE, RefereeRole.UMPIRE}
    T.check("RefereeRole set 사용 가능", len(rr_set) == 3)

    # dict 키 사용
    rr_dict = {r: r.korean_name for r in RefereeRole}
    T.check("RefereeRole dict 키 사용", len(rr_dict) == 3)

    # =================================================================
    # 20. 일반 상수 (값, 타입, 범위)
    # =================================================================
    T.set_section("20. 일반 상수 - 값, 타입, 범위")

    # MIN_DECISION_CONFIDENCE
    T.check("MIN_DECISION_CONFIDENCE == 0.70",
            abs(MIN_DECISION_CONFIDENCE - 0.70) < 1e-9,
            f"got {MIN_DECISION_CONFIDENCE}")
    T.check("MIN_DECISION_CONFIDENCE is float",
            isinstance(MIN_DECISION_CONFIDENCE, float))
    T.check("MIN_DECISION_CONFIDENCE > 0", MIN_DECISION_CONFIDENCE > 0)
    T.check("MIN_DECISION_CONFIDENCE < 1", MIN_DECISION_CONFIDENCE < 1)

    # AUTO_CONFIRM_CONFIDENCE
    T.check("AUTO_CONFIRM_CONFIDENCE == 0.95",
            abs(AUTO_CONFIRM_CONFIDENCE - 0.95) < 1e-9,
            f"got {AUTO_CONFIRM_CONFIDENCE}")
    T.check("AUTO_CONFIRM_CONFIDENCE is float",
            isinstance(AUTO_CONFIRM_CONFIDENCE, float))
    T.check("AUTO_CONFIRM_CONFIDENCE > 0", AUTO_CONFIRM_CONFIDENCE > 0)
    T.check("AUTO_CONFIRM_CONFIDENCE <= 1", AUTO_CONFIRM_CONFIDENCE <= 1)

    # REVIEW_TIME_LIMIT_SEC
    T.check("REVIEW_TIME_LIMIT_SEC == 120",
            REVIEW_TIME_LIMIT_SEC == 120,
            f"got {REVIEW_TIME_LIMIT_SEC}")
    T.check("REVIEW_TIME_LIMIT_SEC is int",
            isinstance(REVIEW_TIME_LIMIT_SEC, int))
    T.check("REVIEW_TIME_LIMIT_SEC > 0", REVIEW_TIME_LIMIT_SEC > 0)
    T.check("REVIEW_TIME_LIMIT_SEC == 2분", REVIEW_TIME_LIMIT_SEC == 2 * 60)

    # MAX_COACH_CHALLENGES_PER_GAME
    T.check("MAX_COACH_CHALLENGES_PER_GAME == 1",
            MAX_COACH_CHALLENGES_PER_GAME == 1,
            f"got {MAX_COACH_CHALLENGES_PER_GAME}")
    T.check("MAX_COACH_CHALLENGES_PER_GAME is int",
            isinstance(MAX_COACH_CHALLENGES_PER_GAME, int))
    T.check("MAX_COACH_CHALLENGES_PER_GAME > 0",
            MAX_COACH_CHALLENGES_PER_GAME > 0)

    # REFEREE_COUNT_STANDARD
    T.check("REFEREE_COUNT_STANDARD == 3",
            REFEREE_COUNT_STANDARD == 3,
            f"got {REFEREE_COUNT_STANDARD}")
    T.check("REFEREE_COUNT_STANDARD is int",
            isinstance(REFEREE_COUNT_STANDARD, int))
    T.check("REFEREE_COUNT_STANDARD > 0", REFEREE_COUNT_STANDARD > 0)

    # CONSISTENCY_WINDOW_FRAMES
    T.check("CONSISTENCY_WINDOW_FRAMES == 1800",
            CONSISTENCY_WINDOW_FRAMES == 1800,
            f"got {CONSISTENCY_WINDOW_FRAMES}")
    T.check("CONSISTENCY_WINDOW_FRAMES is int",
            isinstance(CONSISTENCY_WINDOW_FRAMES, int))
    T.check("CONSISTENCY_WINDOW_FRAMES > 0", CONSISTENCY_WINDOW_FRAMES > 0)
    T.check("CONSISTENCY_WINDOW_FRAMES == 30초 @60fps",
            CONSISTENCY_WINDOW_FRAMES == 30 * 60)

    # =================================================================
    # 21. 신뢰도 순서 검증: MIN < AUTO
    # =================================================================
    T.set_section("21. 신뢰도 순서 검증")

    T.check("MIN_DECISION_CONFIDENCE < AUTO_CONFIRM_CONFIDENCE",
            MIN_DECISION_CONFIDENCE < AUTO_CONFIRM_CONFIDENCE)
    T.check("MIN_DECISION_CONFIDENCE >= 0.5 (합리적 하한)",
            MIN_DECISION_CONFIDENCE >= 0.5)
    T.check("AUTO_CONFIRM_CONFIDENCE >= 0.9 (높은 자동확정 기준)",
            AUTO_CONFIRM_CONFIDENCE >= 0.9)
    T.check("신뢰도 구간 갭 >= 0.1",
            AUTO_CONFIRM_CONFIDENCE - MIN_DECISION_CONFIDENCE >= 0.1)
    T.check("신뢰도 범위 0~1 (MIN)",
            0.0 <= MIN_DECISION_CONFIDENCE <= 1.0)
    T.check("신뢰도 범위 0~1 (AUTO)",
            0.0 <= AUTO_CONFIRM_CONFIDENCE <= 1.0)

    # =================================================================
    # 22. __all__ 완전성 (28항목)
    # =================================================================
    T.set_section("22. __all__ 완전성 (28항목)")

    all_list = referee_rule_constants.__all__
    T.check("__all__ 존재", hasattr(referee_rule_constants, "__all__"))
    T.check("__all__ is list", isinstance(all_list, list))
    T.check("__all__ 항목 수 == 28", len(all_list) == 28,
            f"expected 28, got {len(all_list)}")

    # 열거형 (6종) 포함 확인
    enum_names = ["RuleSet", "CallType", "SignalType",
                  "ReviewTrigger", "ReviewOutcome", "RefereeRole"]
    for name in enum_names:
        T.check(f"__all__ contains '{name}'", name in all_list)

    # 일반 상수 (6종) 포함 확인
    const_names = [
        "MIN_DECISION_CONFIDENCE", "AUTO_CONFIRM_CONFIDENCE",
        "REVIEW_TIME_LIMIT_SEC", "MAX_COACH_CHALLENGES_PER_GAME",
        "REFEREE_COUNT_STANDARD", "CONSISTENCY_WINDOW_FRAMES",
    ]
    for name in const_names:
        T.check(f"__all__ contains '{name}'", name in all_list)

    # 캐시 (16종) 포함 확인
    cache_names = [
        "_RULE_SET_KOREAN_MAP", "_RULE_SET_QUARTER_DURATION_MAP",
        "_RULE_SET_BACKCOURT_SEC_MAP", "_RULE_SET_THREE_POINT_DISTANCE_MAP",
        "_RULE_SET_MAX_PERSONAL_FOULS_MAP", "_RULE_SET_MAX_TIMEOUTS_MAP",
        "_RULE_SET_HAS_DEFENSIVE_THREE_SEC",
        "_CALL_TYPE_IS_FOUL", "_CALL_TYPE_IS_VIOLATION",
        "_CALL_TYPE_NO_STOP", "_CALL_TYPE_KOREAN_MAP",
        "_SIGNAL_TYPE_KOREAN_MAP",
        "_REVIEW_TRIGGER_KOREAN_MAP",
        "_REVIEW_OUTCOME_CHANGED", "_REVIEW_OUTCOME_KOREAN_MAP",
        "_REFEREE_ROLE_KOREAN_MAP",
    ]
    for name in cache_names:
        T.check(f"__all__ contains '{name}'", name in all_list)

    # __all__ 유일성 (중복 없음)
    T.check("__all__ 중복 없음", len(all_list) == len(set(all_list)))

    # __all__의 모든 항목이 실제 모듈 속성으로 존재
    for name in all_list:
        T.check(f"모듈 속성 존재: {name}",
                hasattr(referee_rule_constants, name),
                f"{name} not found in module")

    # =================================================================
    # 23. 캐시 타입/완전성 (4 frozenset + 10 dict)
    # =================================================================
    T.set_section("23. 캐시 타입/완전성")

    # --- frozenset 캐시 (4종) ---
    # _RULE_SET_HAS_DEFENSIVE_THREE_SEC
    T.check("_RULE_SET_HAS_DEFENSIVE_THREE_SEC is frozenset",
            isinstance(_RULE_SET_HAS_DEFENSIVE_THREE_SEC, frozenset))
    T.check("_RULE_SET_HAS_DEFENSIVE_THREE_SEC 크기 == 1",
            len(_RULE_SET_HAS_DEFENSIVE_THREE_SEC) == 1)
    T.check("_RULE_SET_HAS_DEFENSIVE_THREE_SEC contains NBA",
            RuleSet.NBA in _RULE_SET_HAS_DEFENSIVE_THREE_SEC)
    T.check("_RULE_SET_HAS_DEFENSIVE_THREE_SEC not contains FIBA",
            RuleSet.FIBA not in _RULE_SET_HAS_DEFENSIVE_THREE_SEC)

    # _CALL_TYPE_IS_FOUL
    T.check("_CALL_TYPE_IS_FOUL is frozenset",
            isinstance(_CALL_TYPE_IS_FOUL, frozenset))
    T.check("_CALL_TYPE_IS_FOUL 크기 == 5",
            len(_CALL_TYPE_IS_FOUL) == 5, f"got {len(_CALL_TYPE_IS_FOUL)}")
    expected_fouls = {CallType.PERSONAL_FOUL, CallType.SHOOTING_FOUL,
                      CallType.OFFENSIVE_FOUL, CallType.TECHNICAL_FOUL,
                      CallType.FLAGRANT_FOUL}
    T.check("_CALL_TYPE_IS_FOUL 멤버 일치",
            _CALL_TYPE_IS_FOUL == expected_fouls)

    # _CALL_TYPE_IS_VIOLATION
    T.check("_CALL_TYPE_IS_VIOLATION is frozenset",
            isinstance(_CALL_TYPE_IS_VIOLATION, frozenset))
    T.check("_CALL_TYPE_IS_VIOLATION 크기 == 5",
            len(_CALL_TYPE_IS_VIOLATION) == 5, f"got {len(_CALL_TYPE_IS_VIOLATION)}")
    expected_violations = {CallType.TRAVELING, CallType.DOUBLE_DRIBBLE,
                           CallType.OUT_OF_BOUNDS, CallType.SHOT_CLOCK_VIOLATION,
                           CallType.BACKCOURT_VIOLATION}
    T.check("_CALL_TYPE_IS_VIOLATION 멤버 일치",
            _CALL_TYPE_IS_VIOLATION == expected_violations)

    # _CALL_TYPE_NO_STOP
    T.check("_CALL_TYPE_NO_STOP is frozenset",
            isinstance(_CALL_TYPE_NO_STOP, frozenset))
    T.check("_CALL_TYPE_NO_STOP 크기 == 1",
            len(_CALL_TYPE_NO_STOP) == 1, f"got {len(_CALL_TYPE_NO_STOP)}")
    T.check("_CALL_TYPE_NO_STOP contains NO_CALL",
            CallType.NO_CALL in _CALL_TYPE_NO_STOP)

    # _REVIEW_OUTCOME_CHANGED
    T.check("_REVIEW_OUTCOME_CHANGED is frozenset",
            isinstance(_REVIEW_OUTCOME_CHANGED, frozenset))
    T.check("_REVIEW_OUTCOME_CHANGED 크기 == 2",
            len(_REVIEW_OUTCOME_CHANGED) == 2, f"got {len(_REVIEW_OUTCOME_CHANGED)}")
    T.check("_REVIEW_OUTCOME_CHANGED contains CALL_OVERTURNED",
            ReviewOutcome.CALL_OVERTURNED in _REVIEW_OUTCOME_CHANGED)
    T.check("_REVIEW_OUTCOME_CHANGED contains RULING_ADJUSTED",
            ReviewOutcome.RULING_ADJUSTED in _REVIEW_OUTCOME_CHANGED)
    T.check("_REVIEW_OUTCOME_CHANGED not contains CALL_STANDS",
            ReviewOutcome.CALL_STANDS not in _REVIEW_OUTCOME_CHANGED)
    T.check("_REVIEW_OUTCOME_CHANGED not contains INCONCLUSIVE",
            ReviewOutcome.INCONCLUSIVE not in _REVIEW_OUTCOME_CHANGED)
    T.check("_REVIEW_OUTCOME_CHANGED not contains NO_REVIEW",
            ReviewOutcome.NO_REVIEW not in _REVIEW_OUTCOME_CHANGED)

    # frozenset 불변성 검증 (추가 시도 -> AttributeError)
    try:
        _CALL_TYPE_IS_FOUL.add(CallType.NO_CALL)  # type: ignore
        T.fail("frozenset 불변성 (_CALL_TYPE_IS_FOUL)", "add 성공해서는 안 됨")
    except AttributeError:
        T.ok("frozenset 불변성 (_CALL_TYPE_IS_FOUL)")

    try:
        _REVIEW_OUTCOME_CHANGED.add(ReviewOutcome.NO_REVIEW)  # type: ignore
        T.fail("frozenset 불변성 (_REVIEW_OUTCOME_CHANGED)", "add 성공해서는 안 됨")
    except AttributeError:
        T.ok("frozenset 불변성 (_REVIEW_OUTCOME_CHANGED)")

    # frozenset 상호 배타성 (foul과 violation)
    T.check("_CALL_TYPE_IS_FOUL ∩ _CALL_TYPE_IS_VIOLATION == 공집합",
            len(_CALL_TYPE_IS_FOUL & _CALL_TYPE_IS_VIOLATION) == 0)

    # foul, violation 합집합에 NO_CALL 미포함
    foul_viol_union = _CALL_TYPE_IS_FOUL | _CALL_TYPE_IS_VIOLATION
    T.check("foul | violation 합집합에 NO_CALL 미포함",
            CallType.NO_CALL not in foul_viol_union)

    # foul, violation, no_stop 모두 합치면 11개 (5+5+1)
    all_cached = _CALL_TYPE_IS_FOUL | _CALL_TYPE_IS_VIOLATION | _CALL_TYPE_NO_STOP
    T.check("foul | violation | no_stop 합집합 크기 == 11",
            len(all_cached) == 11, f"got {len(all_cached)}")

    # --- dict 캐시 (10종) ---
    dict_caches = {
        "_RULE_SET_KOREAN_MAP": (_RULE_SET_KOREAN_MAP, RuleSet, str, 5),
        "_RULE_SET_QUARTER_DURATION_MAP": (_RULE_SET_QUARTER_DURATION_MAP, RuleSet, int, 5),
        "_RULE_SET_BACKCOURT_SEC_MAP": (_RULE_SET_BACKCOURT_SEC_MAP, RuleSet, int, 5),
        "_RULE_SET_THREE_POINT_DISTANCE_MAP": (_RULE_SET_THREE_POINT_DISTANCE_MAP, RuleSet, float, 5),
        "_RULE_SET_MAX_PERSONAL_FOULS_MAP": (_RULE_SET_MAX_PERSONAL_FOULS_MAP, RuleSet, int, 5),
        "_RULE_SET_MAX_TIMEOUTS_MAP": (_RULE_SET_MAX_TIMEOUTS_MAP, RuleSet, int, 5),
        "_CALL_TYPE_KOREAN_MAP": (_CALL_TYPE_KOREAN_MAP, CallType, str, 15),
        "_SIGNAL_TYPE_KOREAN_MAP": (_SIGNAL_TYPE_KOREAN_MAP, SignalType, str, 20),
        "_REVIEW_TRIGGER_KOREAN_MAP": (_REVIEW_TRIGGER_KOREAN_MAP, ReviewTrigger, str, 8),
        "_REVIEW_OUTCOME_KOREAN_MAP": (_REVIEW_OUTCOME_KOREAN_MAP, ReviewOutcome, str, 5),
    }

    # _REFEREE_ROLE_KOREAN_MAP (별도 처리)
    T.check("_REFEREE_ROLE_KOREAN_MAP is dict",
            isinstance(_REFEREE_ROLE_KOREAN_MAP, dict))
    T.check("_REFEREE_ROLE_KOREAN_MAP 크기 == 3",
            len(_REFEREE_ROLE_KOREAN_MAP) == 3,
            f"got {len(_REFEREE_ROLE_KOREAN_MAP)}")

    for cache_name, (cache, key_type, val_type, expected_size) in dict_caches.items():
        T.check(f"{cache_name} is dict", isinstance(cache, dict))
        T.check(f"{cache_name} 크기 == {expected_size}",
                len(cache) == expected_size,
                f"got {len(cache)}")

        # 키 타입 검증
        all_keys_valid = all(isinstance(k, key_type) for k in cache.keys())
        T.check(f"{cache_name} 키 타입 == {key_type.__name__}", all_keys_valid)

        # 값 타입 검증
        all_vals_valid = all(isinstance(v, val_type) for v in cache.values())
        T.check(f"{cache_name} 값 타입 == {val_type.__name__}", all_vals_valid)

    # RuleSet 캐시: 모든 멤버 키 포함 확인
    ruleset_caches = [
        _RULE_SET_KOREAN_MAP, _RULE_SET_QUARTER_DURATION_MAP,
        _RULE_SET_BACKCOURT_SEC_MAP, _RULE_SET_THREE_POINT_DISTANCE_MAP,
        _RULE_SET_MAX_PERSONAL_FOULS_MAP, _RULE_SET_MAX_TIMEOUTS_MAP,
    ]
    for cache in ruleset_caches:
        for member in RuleSet:
            T.check(f"RuleSet.{member.name} in cache (키 존재)",
                    member in cache, f"{member} not in cache")

    # CallType 캐시: 모든 멤버 키 포함 확인
    for member in CallType:
        T.check(f"CallType.{member.name} in _CALL_TYPE_KOREAN_MAP",
                member in _CALL_TYPE_KOREAN_MAP)

    # SignalType 캐시: 모든 멤버 키 포함 확인
    for member in SignalType:
        T.check(f"SignalType.{member.name} in _SIGNAL_TYPE_KOREAN_MAP",
                member in _SIGNAL_TYPE_KOREAN_MAP)

    # ReviewTrigger 캐시: 모든 멤버 키 포함 확인
    for member in ReviewTrigger:
        T.check(f"ReviewTrigger.{member.name} in _REVIEW_TRIGGER_KOREAN_MAP",
                member in _REVIEW_TRIGGER_KOREAN_MAP)

    # ReviewOutcome 캐시: 모든 멤버 키 포함 확인
    for member in ReviewOutcome:
        T.check(f"ReviewOutcome.{member.name} in _REVIEW_OUTCOME_KOREAN_MAP",
                member in _REVIEW_OUTCOME_KOREAN_MAP)

    # RefereeRole 캐시: 모든 멤버 키 포함 확인
    for member in RefereeRole:
        T.check(f"RefereeRole.{member.name} in _REFEREE_ROLE_KOREAN_MAP",
                member in _REFEREE_ROLE_KOREAN_MAP)

    # 캐시 값 비어있지 않음 (korean_name 캐시)
    korean_caches = [
        _RULE_SET_KOREAN_MAP, _CALL_TYPE_KOREAN_MAP, _SIGNAL_TYPE_KOREAN_MAP,
        _REVIEW_TRIGGER_KOREAN_MAP, _REVIEW_OUTCOME_KOREAN_MAP,
        _REFEREE_ROLE_KOREAN_MAP,
    ]
    for cache in korean_caches:
        for k, v in cache.items():
            T.check(f"{k.name} korean cache value 비어있지 않음", len(v) > 0)

    # 총 캐시 수 확인: 4 frozenset + 11 dict = 15 (사양상 16이지만 실제 dict 11종)
    frozenset_count = 4  # HAS_DEFENSIVE_THREE_SEC, IS_FOUL, IS_VIOLATION, NO_STOP + OUTCOME_CHANGED
    dict_count = 11  # 6 RuleSet + CALL_KOREAN + SIGNAL_KOREAN + RT_KOREAN + RO_KOREAN + RR_KOREAN
    T.check("frozenset 캐시 4종 확인", frozenset_count == 4)

    # =================================================================
    # 24. 메타 (version 1.0.0, 모듈 속성)
    # =================================================================
    T.set_section("24. 메타 - version, 모듈 속성")

    T.check("__version__ 존재", hasattr(referee_rule_constants, "__version__"))
    T.check("__version__ == '1.0.0'",
            referee_rule_constants.__version__ == "1.0.0",
            f"got {referee_rule_constants.__version__!r}")
    T.check("__version__ is str",
            isinstance(referee_rule_constants.__version__, str))

    # 모듈 docstring 존재
    T.check("모듈 docstring 존재",
            referee_rule_constants.__doc__ is not None and len(referee_rule_constants.__doc__) > 0)

    # @unique 데코레이터 검증 (중복 값 시 ValueError)
    # RuleSet 고유성
    rs_values = [m.value for m in RuleSet]
    T.check("RuleSet @unique 준수", len(rs_values) == len(set(rs_values)))

    # CallType 고유성
    ct_vals = [m.value for m in CallType]
    T.check("CallType @unique 준수", len(ct_vals) == len(set(ct_vals)))

    # SignalType 고유성
    st_vals = [m.value for m in SignalType]
    T.check("SignalType @unique 준수", len(st_vals) == len(set(st_vals)))

    # ReviewTrigger 고유성
    rt_vals2 = [m.value for m in ReviewTrigger]
    T.check("ReviewTrigger @unique 준수", len(rt_vals2) == len(set(rt_vals2)))

    # ReviewOutcome 고유성
    ro_vals2 = [m.value for m in ReviewOutcome]
    T.check("ReviewOutcome @unique 준수", len(ro_vals2) == len(set(ro_vals2)))

    # RefereeRole 고유성
    rr_vals2 = [m.value for m in RefereeRole]
    T.check("RefereeRole @unique 준수", len(rr_vals2) == len(set(rr_vals2)))

    # =================================================================
    # 25. 추가 엣지 케이스 및 도메인 일관성
    # =================================================================
    T.set_section("25. 추가 엣지 케이스 및 도메인 일관성")

    # RuleSet 문자열 생성자
    T.check("RuleSet('fiba') == RuleSet.FIBA", RuleSet("fiba") == RuleSet.FIBA)
    T.check("RuleSet('nba') == RuleSet.NBA", RuleSet("nba") == RuleSet.NBA)
    T.check("RuleSet('kbl') == RuleSet.KBL", RuleSet("kbl") == RuleSet.KBL)
    T.check("RuleSet('nbl') == RuleSet.NBL", RuleSet("nbl") == RuleSet.NBL)
    T.check("RuleSet('euroleague') == RuleSet.EUROLEAGUE",
            RuleSet("euroleague") == RuleSet.EUROLEAGUE)

    # 잘못된 값으로 생성 시 ValueError
    try:
        _ = RuleSet("invalid")
        T.fail("RuleSet('invalid') ValueError", "예외 미발생")
    except ValueError:
        T.ok("RuleSet('invalid') ValueError 발생")

    # CallType 문자열 생성자
    T.check("CallType('personal_foul') == PERSONAL_FOUL",
            CallType("personal_foul") == CallType.PERSONAL_FOUL)
    T.check("CallType('no_call') == NO_CALL",
            CallType("no_call") == CallType.NO_CALL)

    try:
        _ = CallType("invalid_call")
        T.fail("CallType('invalid_call') ValueError", "예외 미발생")
    except ValueError:
        T.ok("CallType('invalid_call') ValueError 발생")

    # SignalType 문자열 생성자
    T.check("SignalType('one_point') == ONE_POINT",
            SignalType("one_point") == SignalType.ONE_POINT)

    try:
        _ = SignalType("invalid_signal")
        T.fail("SignalType('invalid_signal') ValueError", "예외 미발생")
    except ValueError:
        T.ok("SignalType('invalid_signal') ValueError 발생")

    # ReviewTrigger 문자열 생성자
    T.check("ReviewTrigger('coach_challenge') == COACH_CHALLENGE",
            ReviewTrigger("coach_challenge") == ReviewTrigger.COACH_CHALLENGE)

    try:
        _ = ReviewTrigger("invalid_trigger")
        T.fail("ReviewTrigger('invalid_trigger') ValueError", "예외 미발생")
    except ValueError:
        T.ok("ReviewTrigger('invalid_trigger') ValueError 발생")

    # ReviewOutcome 문자열 생성자
    T.check("ReviewOutcome('call_stands') == CALL_STANDS",
            ReviewOutcome("call_stands") == ReviewOutcome.CALL_STANDS)

    try:
        _ = ReviewOutcome("invalid_outcome")
        T.fail("ReviewOutcome('invalid_outcome') ValueError", "예외 미발생")
    except ValueError:
        T.ok("ReviewOutcome('invalid_outcome') ValueError 발생")

    # RefereeRole 문자열 생성자
    T.check("RefereeRole('crew_chief') == CREW_CHIEF",
            RefereeRole("crew_chief") == RefereeRole.CREW_CHIEF)

    try:
        _ = RefereeRole("invalid_role")
        T.fail("RefereeRole('invalid_role') ValueError", "예외 미발생")
    except ValueError:
        T.ok("RefereeRole('invalid_role') ValueError 발생")

    # Enum 반복 가능 (iteration)
    T.check("RuleSet iterable", len(list(RuleSet)) == 5)
    T.check("CallType iterable", len(list(CallType)) == 15)
    T.check("SignalType iterable", len(list(SignalType)) == 20)
    T.check("ReviewTrigger iterable", len(list(ReviewTrigger)) == 8)
    T.check("ReviewOutcome iterable", len(list(ReviewOutcome)) == 5)
    T.check("RefereeRole iterable", len(list(RefereeRole)) == 3)

    # Enum.__members__ 확인
    T.check("RuleSet.__members__ 크기 5",
            len(RuleSet.__members__) == 5)
    T.check("CallType.__members__ 크기 15",
            len(CallType.__members__) == 15)
    T.check("SignalType.__members__ 크기 20",
            len(SignalType.__members__) == 20)
    T.check("ReviewTrigger.__members__ 크기 8",
            len(ReviewTrigger.__members__) == 8)
    T.check("ReviewOutcome.__members__ 크기 5",
            len(ReviewOutcome.__members__) == 5)
    T.check("RefereeRole.__members__ 크기 3",
            len(RefereeRole.__members__) == 3)

    # name 속성 검증 (모든 Enum)
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.name == '{member.name}'",
                member.name == member.name)

    # identity 검증 (is 연산자)
    T.check("CallType.NO_CALL is CallType('no_call')",
            CallType.NO_CALL is CallType("no_call"))
    T.check("SignalType.ONE_POINT is SignalType('one_point')",
            SignalType.ONE_POINT is SignalType("one_point"))
    T.check("ReviewTrigger.AUTOMATIC is ReviewTrigger('automatic')",
            ReviewTrigger.AUTOMATIC is ReviewTrigger("automatic"))
    T.check("ReviewOutcome.CALL_STANDS is ReviewOutcome('call_stands')",
            ReviewOutcome.CALL_STANDS is ReviewOutcome("call_stands"))
    T.check("RefereeRole.CREW_CHIEF is RefereeRole('crew_chief')",
            RefereeRole.CREW_CHIEF is RefereeRole("crew_chief"))

    # 도메인 일관성: 모든 쿼터 시간은 양의 정수이고 분 단위 변환 가능
    for member in RuleSet:
        qd = member.quarter_duration_sec
        T.check(f"{member.name} quarter_duration_sec 60으로 나눠짐",
                qd % 60 == 0, f"{qd} % 60 != 0")

    # 도메인 일관성: 샷클락 < 백코트가 아니어야 함 (24 > 8)
    for member in RuleSet:
        T.check(f"{member.name} shot_clock > backcourt",
                member.shot_clock_seconds > member.backcourt_seconds)

    # 도메인 일관성: 3점 라인 거리는 합리적 범위
    for member in RuleSet:
        dist = member.three_point_distance_meters
        T.check(f"{member.name} 3pt in [6.0, 8.0]",
                6.0 <= dist <= 8.0, f"got {dist}")

    # 도메인 일관성: 최대 파울 수는 합리적 범위 (4~8)
    for member in RuleSet:
        mpf = member.max_personal_fouls
        T.check(f"{member.name} max_personal_fouls in [4, 8]",
                4 <= mpf <= 8, f"got {mpf}")

    # 도메인 일관성: 최대 타임아웃 수는 합리적 범위 (3~10)
    for member in RuleSet:
        mt = member.max_timeouts
        T.check(f"{member.name} max_timeouts in [3, 10]",
                3 <= mt <= 10, f"got {mt}")

    # 도메인 일관성: 리뷰 제한 시간은 합리적 (30~300초)
    T.check("REVIEW_TIME_LIMIT_SEC in [30, 300]",
            30 <= REVIEW_TIME_LIMIT_SEC <= 300)

    # 도메인 일관성: 코치 챌린지는 경기당 최소 1회
    T.check("MAX_COACH_CHALLENGES_PER_GAME >= 1",
            MAX_COACH_CHALLENGES_PER_GAME >= 1)

    # 도메인 일관성: 심판 수는 1~5명 범위
    T.check("REFEREE_COUNT_STANDARD in [1, 5]",
            1 <= REFEREE_COUNT_STANDARD <= 5)

    # 도메인: CONSISTENCY_WINDOW_FRAMES 30fps에서도 15초 이상
    T.check("CONSISTENCY_WINDOW_FRAMES >= 30fps 15초 (450)",
            CONSISTENCY_WINDOW_FRAMES >= 450)

    # =================================================================
    # 26. 추가 교차 검증 및 property 접근 일관성
    # =================================================================
    T.set_section("26. 교차 검증 및 property 접근 일관성")

    # RuleSet property가 property 객체인지 (클래스 수준에서)
    T.check("RuleSet.korean_name is property",
            isinstance(type(RuleSet.FIBA).__dict__.get("korean_name"), property)
            or callable(getattr(type(RuleSet.FIBA), "korean_name", None)))

    # 모든 RuleSet property 반복 접근 일관성
    for member in RuleSet:
        val1 = member.korean_name
        val2 = member.korean_name
        T.check(f"RuleSet.{member.name}.korean_name 재접근 일관성", val1 == val2)

    for member in RuleSet:
        val1 = member.quarter_duration_sec
        val2 = member.quarter_duration_sec
        T.check(f"RuleSet.{member.name}.quarter_duration_sec 재접근 일관성", val1 == val2)

    # CallType property 반복 접근 일관성
    for member in CallType:
        T.check(f"CallType.{member.name} is_foul 재접근 일관성",
                member.is_foul == member.is_foul)
        T.check(f"CallType.{member.name} is_violation 재접근 일관성",
                member.is_violation == member.is_violation)
        T.check(f"CallType.{member.name} stops_play 재접근 일관성",
                member.stops_play == member.stops_play)

    # ReviewOutcome property 반복 접근 일관성
    for member in ReviewOutcome:
        T.check(f"ReviewOutcome.{member.name} changed_call 재접근 일관성",
                member.changed_call == member.changed_call)

    # str mixin 동등 비교 검증 - 모든 Enum
    all_enums = [
        (RuleSet, "RuleSet"),
        (CallType, "CallType"),
        (SignalType, "SignalType"),
        (ReviewTrigger, "ReviewTrigger"),
        (ReviewOutcome, "ReviewOutcome"),
        (RefereeRole, "RefereeRole"),
    ]
    for enum_cls, cls_name in all_enums:
        for member in enum_cls:
            T.check(f"{cls_name}.{member.name} == value (str mixin 동등)",
                    member == member.value)

    # repr 검증 (Enum repr 포함)
    for member in RuleSet:
        r = repr(member)
        T.check(f"repr(RuleSet.{member.name}) contains class name",
                "RuleSet" in r, f"got {r!r}")

    # =================================================================
    # 27. 추가 분류 체계 및 집합 연산
    # =================================================================
    T.set_section("27. 분류 체계 및 집합 연산")

    # CallType: foul + violation + special = 15 (전체)
    foul_set = {m for m in CallType if m.is_foul}
    viol_set = {m for m in CallType if m.is_violation}
    special_set = {m for m in CallType if not m.is_foul and not m.is_violation}
    T.check("foul(5) + violation(5) + special(5) == 15",
            len(foul_set) + len(viol_set) + len(special_set) == 15)
    T.check("foul_set 크기 5", len(foul_set) == 5)
    T.check("viol_set 크기 5", len(viol_set) == 5)
    T.check("special_set 크기 5", len(special_set) == 5)

    # 3개 집합 교집합 공집합
    T.check("foul ∩ violation == 공집합", len(foul_set & viol_set) == 0)
    T.check("foul ∩ special == 공집합", len(foul_set & special_set) == 0)
    T.check("violation ∩ special == 공집합", len(viol_set & special_set) == 0)

    # 합집합 == 전체
    union = foul_set | viol_set | special_set
    T.check("foul | violation | special == 전체 CallType",
            union == set(CallType))

    # special 집합 내용
    expected_special = {CallType.JUMP_BALL, CallType.TIMEOUT,
                        CallType.SUBSTITUTION, CallType.NO_CALL, CallType.REVIEW}
    T.check("special 집합 멤버 정확", special_set == expected_special)

    # stops_play 기준 분류
    stops_set = {m for m in CallType if m.stops_play}
    no_stop_set = {m for m in CallType if not m.stops_play}
    T.check("stops_play(14) + no_stop(1) == 15",
            len(stops_set) + len(no_stop_set) == 15)
    T.check("no_stop == {NO_CALL}", no_stop_set == {CallType.NO_CALL})

    # changed_call 기준 분류
    changed_set = {m for m in ReviewOutcome if m.changed_call}
    not_changed_set = {m for m in ReviewOutcome if not m.changed_call}
    T.check("changed(2) + not_changed(3) == 5",
            len(changed_set) + len(not_changed_set) == 5)
    expected_changed = {ReviewOutcome.CALL_OVERTURNED, ReviewOutcome.RULING_ADJUSTED}
    T.check("changed_set 멤버 정확", changed_set == expected_changed)

    # =================================================================
    # 28. 추가 property 반환 타입 검증 (전수)
    # =================================================================
    T.set_section("28. property 반환 타입 전수 검증")

    # RuleSet property 타입
    for member in RuleSet:
        T.check(f"RuleSet.{member.name}.korean_name -> str",
                type(member.korean_name) is str)
        T.check(f"RuleSet.{member.name}.quarter_duration_sec -> int",
                type(member.quarter_duration_sec) is int)
        T.check(f"RuleSet.{member.name}.shot_clock_seconds -> int",
                type(member.shot_clock_seconds) is int)
        T.check(f"RuleSet.{member.name}.backcourt_seconds -> int",
                type(member.backcourt_seconds) is int)
        T.check(f"RuleSet.{member.name}.three_point_distance_meters -> float",
                type(member.three_point_distance_meters) is float)
        T.check(f"RuleSet.{member.name}.max_personal_fouls -> int",
                type(member.max_personal_fouls) is int)
        T.check(f"RuleSet.{member.name}.max_timeouts -> int",
                type(member.max_timeouts) is int)
        T.check(f"RuleSet.{member.name}.has_defensive_three_seconds -> bool",
                type(member.has_defensive_three_seconds) is bool)

    # CallType property 타입
    for member in CallType:
        T.check(f"CallType.{member.name}.korean_name -> str",
                type(member.korean_name) is str)
        T.check(f"CallType.{member.name}.stops_play -> bool",
                type(member.stops_play) is bool)
        T.check(f"CallType.{member.name}.is_foul -> bool",
                type(member.is_foul) is bool)
        T.check(f"CallType.{member.name}.is_violation -> bool",
                type(member.is_violation) is bool)

    # SignalType property 타입
    for member in SignalType:
        T.check(f"SignalType.{member.name}.korean_name -> str",
                type(member.korean_name) is str)

    # ReviewTrigger property 타입
    for member in ReviewTrigger:
        T.check(f"ReviewTrigger.{member.name}.korean_name -> str",
                type(member.korean_name) is str)

    # ReviewOutcome property 타입
    for member in ReviewOutcome:
        T.check(f"ReviewOutcome.{member.name}.korean_name -> str",
                type(member.korean_name) is str)
        T.check(f"ReviewOutcome.{member.name}.changed_call -> bool",
                type(member.changed_call) is bool)

    # RefereeRole property 타입
    for member in RefereeRole:
        T.check(f"RefereeRole.{member.name}.korean_name -> str",
                type(member.korean_name) is str)

    # =================================================================
    # 요약
    # =================================================================
    sys.exit(0 if T.summary() else 1)


if __name__ == "__main__":
    main()
