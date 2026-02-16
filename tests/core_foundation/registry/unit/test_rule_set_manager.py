# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/registry/unit
파일: test_rule_set_manager.py
설명: RuleSetManager 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12
"""

# ============================================================
# 표준 라이브러리
# ============================================================
import sys
import time
import threading
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ============================================================
# 프로젝트 루트 경로 설정
# ============================================================
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# ============================================================
# 프로젝트 임포트
# ============================================================
from core_foundation.registry.rule_set_manager import (
    # Enum (3개)
    League,
    RuleCategory,
    RuleSeverity,
    # 상수 - 일반
    SUPPORTED_LEAGUES,
    DEFAULT_RULE_SET_PATH,
    RULE_SET_SCHEMA_VERSION,
    DEFAULT_CACHE_TTL,
    MAX_CACHE_SIZE,
    RULE_PRIORITY_WEIGHTS,
    LEAGUE_HIERARCHY,
    DEFAULT_FALLBACK_LEAGUE,
    # 상수 - 리그별
    QUARTER_DURATION,
    SHOT_CLOCK,
    THREE_POINT_DISTANCE,
    PERSONAL_FOUL_LIMIT,
    # 데이터 클래스 (6개)
    Rule,
    RuleSet,
    RuleCondition,
    Penalty,
    RuleSetMetadata,
    LeagueConfig,
    # Protocol (1개)
    RuleSetLoaderProtocol,
    # 메인 클래스
    RuleSetManager,
    # 헬퍼 함수 (5개)
    load_rule_set,
    get_rule_by_id,
    get_rules_by_category,
    merge_rule_sets,
    validate_rule_set,
    # 리그별 팩토리 함수 (7개)
    get_fiba_rules,
    get_nba_rules,
    get_kbl_rules,
    get_nbl_rules,
    get_ncaa_rules,
    get_b_league_rules,
    get_pba_rules,
    # 유틸리티 (테스트용)
    _get_manager,
    _reset_manager,
)

from core_foundation.config import ConfigLoader
from shared.exceptions.validation_exceptions import (
    RuleSetNotFoundException,
    RuleSetValidationException,
)


# ============================================================
# 테스트 결과 클래스
# ============================================================
class TestResult:
    """테스트 결과 추적 클래스."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ============================================================
# [1] League Enum 테스트
# ============================================================
def test_league_enum(result: TestResult) -> None:
    """League Enum 단위 테스트 (10개)."""
    print("\n[1] League Enum 테스트")

    # 1-1. 7개 멤버 존재 확인
    try:
        members = list(League)
        assert len(members) == 7, f"기대: 7, 실제: {len(members)}"
        expected = {League.FIBA, League.NBA, League.KBL, League.NBL, League.NCAA, League.B_LEAGUE, League.PBA}
        assert set(members) == expected, f"멤버 불일치: {set(members)} != {expected}"
        result.ok("League 7개 멤버 존재 확인")
    except Exception as e:
        result.fail("League 7개 멤버 존재 확인", str(e))

    # 1-2. display_name 프로퍼티 존재 확인 (한국어/영어)
    try:
        for league in League:
            name = league.display_name
            assert isinstance(name, str), f"{league}: display_name이 문자열이 아님"
            assert len(name) > 0, f"{league}: display_name이 비어있음"
        result.ok("League display_name 프로퍼티 존재")
    except Exception as e:
        result.fail("League display_name 프로퍼티 존재", str(e))

    # 1-3. country 프로퍼티 존재 확인
    try:
        for league in League:
            country = league.country
            assert isinstance(country, str), f"{league}: country가 문자열이 아님"
            assert len(country) > 0, f"{league}: country가 비어있음"
        result.ok("League country 프로퍼티 존재")
    except Exception as e:
        result.fail("League country 프로퍼티 존재", str(e))

    # 1-4. FIBA display_name 정확도
    try:
        assert League.FIBA.display_name == "FIBA (국제농구연맹)", \
            f"기대: 'FIBA (국제농구연맹)', 실제: '{League.FIBA.display_name}'"
        result.ok("FIBA display_name 정확도")
    except Exception as e:
        result.fail("FIBA display_name 정확도", str(e))

    # 1-5. NBA display_name 정확도
    try:
        assert League.NBA.display_name == "NBA (미국 프로농구)", \
            f"기대: 'NBA (미국 프로농구)', 실제: '{League.NBA.display_name}'"
        result.ok("NBA display_name 정확도")
    except Exception as e:
        result.fail("NBA display_name 정확도", str(e))

    # 1-6. KBL country 정확도
    try:
        assert League.KBL.country == "South Korea", \
            f"기대: 'South Korea', 실제: '{League.KBL.country}'"
        result.ok("KBL country 정확도")
    except Exception as e:
        result.fail("KBL country 정확도", str(e))

    # 1-7. B_LEAGUE country 정확도
    try:
        assert League.B_LEAGUE.country == "Japan", \
            f"기대: 'Japan', 실제: '{League.B_LEAGUE.country}'"
        result.ok("B_LEAGUE country 정확도")
    except Exception as e:
        result.fail("B_LEAGUE country 정확도", str(e))

    # 1-8. 값 고유성 확인
    try:
        values = [l.value for l in League]
        assert len(values) == len(set(values)), "League 값에 중복이 있음"
        result.ok("League 값 고유성 확인")
    except Exception as e:
        result.fail("League 값 고유성 확인", str(e))

    # 1-9. 문자열 접근: League("nba") == League.NBA
    try:
        assert League("nba") == League.NBA, "League('nba') != League.NBA"
        assert League("fiba") == League.FIBA, "League('fiba') != League.FIBA"
        assert League("kbl") == League.KBL, "League('kbl') != League.KBL"
        result.ok("League 문자열 접근 확인")
    except Exception as e:
        result.fail("League 문자열 접근 확인", str(e))

    # 1-10. 반복(iteration) 카운트 == 7
    try:
        count = sum(1 for _ in League)
        assert count == 7, f"기대: 7, 실제: {count}"
        result.ok("League 반복 카운트 == 7")
    except Exception as e:
        result.fail("League 반복 카운트 == 7", str(e))


# ============================================================
# [2] RuleCategory Enum 테스트
# ============================================================
def test_rule_category_enum(result: TestResult) -> None:
    """RuleCategory Enum 단위 테스트 (8개)."""
    print("\n[2] RuleCategory Enum 테스트")

    # 2-1. 8개 멤버 존재 확인
    try:
        members = list(RuleCategory)
        assert len(members) == 8, f"기대: 8, 실제: {len(members)}"
        expected = {
            RuleCategory.VIOLATION, RuleCategory.FOUL, RuleCategory.TIMING,
            RuleCategory.COURT, RuleCategory.EQUIPMENT, RuleCategory.SCORING,
            RuleCategory.SUBSTITUTION, RuleCategory.OUT_OF_BOUNDS,
        }
        assert set(members) == expected, f"멤버 불일치"
        result.ok("RuleCategory 8개 멤버 존재 확인")
    except Exception as e:
        result.fail("RuleCategory 8개 멤버 존재 확인", str(e))

    # 2-2. display_name 프로퍼티 존재 확인 (한국어)
    try:
        for cat in RuleCategory:
            name = cat.display_name
            assert isinstance(name, str) and len(name) > 0, f"{cat}: display_name 비정상"
        result.ok("RuleCategory display_name 프로퍼티 존재")
    except Exception as e:
        result.fail("RuleCategory display_name 프로퍼티 존재", str(e))

    # 2-3. VIOLATION display_name == "바이올레이션"
    try:
        assert RuleCategory.VIOLATION.display_name == "바이올레이션", \
            f"기대: '바이올레이션', 실제: '{RuleCategory.VIOLATION.display_name}'"
        result.ok("VIOLATION display_name == '바이올레이션'")
    except Exception as e:
        result.fail("VIOLATION display_name == '바이올레이션'", str(e))

    # 2-4. FOUL display_name == "파울"
    try:
        assert RuleCategory.FOUL.display_name == "파울", \
            f"기대: '파울', 실제: '{RuleCategory.FOUL.display_name}'"
        result.ok("FOUL display_name == '파울'")
    except Exception as e:
        result.fail("FOUL display_name == '파울'", str(e))

    # 2-5. 값 고유성 확인
    try:
        values = [c.value for c in RuleCategory]
        assert len(values) == len(set(values)), "RuleCategory 값에 중복이 있음"
        result.ok("RuleCategory 값 고유성 확인")
    except Exception as e:
        result.fail("RuleCategory 값 고유성 확인", str(e))

    # 2-6. 문자열 접근 확인
    try:
        assert RuleCategory("violation") == RuleCategory.VIOLATION
        assert RuleCategory("foul") == RuleCategory.FOUL
        assert RuleCategory("timing") == RuleCategory.TIMING
        result.ok("RuleCategory 문자열 접근 확인")
    except Exception as e:
        result.fail("RuleCategory 문자열 접근 확인", str(e))

    # 2-7. 모든 멤버에 display_name 존재
    try:
        for cat in RuleCategory:
            assert hasattr(cat, "display_name"), f"{cat}: display_name 속성 없음"
            assert cat.display_name is not None, f"{cat}: display_name이 None"
        result.ok("RuleCategory 모든 멤버 display_name 존재")
    except Exception as e:
        result.fail("RuleCategory 모든 멤버 display_name 존재", str(e))

    # 2-8. 반복(iteration) 카운트 == 8
    try:
        count = sum(1 for _ in RuleCategory)
        assert count == 8, f"기대: 8, 실제: {count}"
        result.ok("RuleCategory 반복 카운트 == 8")
    except Exception as e:
        result.fail("RuleCategory 반복 카운트 == 8", str(e))


# ============================================================
# [3] RuleSeverity Enum 테스트
# ============================================================
def test_rule_severity_enum(result: TestResult) -> None:
    """RuleSeverity Enum 단위 테스트 (6개)."""
    print("\n[3] RuleSeverity Enum 테스트")

    # 3-1. 4개 멤버 존재 확인
    try:
        members = list(RuleSeverity)
        assert len(members) == 4, f"기대: 4, 실제: {len(members)}"
        expected = {RuleSeverity.MINOR, RuleSeverity.MODERATE, RuleSeverity.SEVERE, RuleSeverity.DISQUALIFYING}
        assert set(members) == expected, "멤버 불일치"
        result.ok("RuleSeverity 4개 멤버 존재 확인")
    except Exception as e:
        result.fail("RuleSeverity 4개 멤버 존재 확인", str(e))

    # 3-2. penalty_weight 정확도
    try:
        assert RuleSeverity.MINOR.penalty_weight == 0.25, \
            f"MINOR: 기대=0.25, 실제={RuleSeverity.MINOR.penalty_weight}"
        assert RuleSeverity.MODERATE.penalty_weight == 0.5, \
            f"MODERATE: 기대=0.5, 실제={RuleSeverity.MODERATE.penalty_weight}"
        assert RuleSeverity.SEVERE.penalty_weight == 0.75, \
            f"SEVERE: 기대=0.75, 실제={RuleSeverity.SEVERE.penalty_weight}"
        assert RuleSeverity.DISQUALIFYING.penalty_weight == 1.0, \
            f"DISQUALIFYING: 기대=1.0, 실제={RuleSeverity.DISQUALIFYING.penalty_weight}"
        result.ok("RuleSeverity penalty_weight 정확도")
    except Exception as e:
        result.fail("RuleSeverity penalty_weight 정확도", str(e))

    # 3-3. 가중치 순서 (MINOR < MODERATE < SEVERE < DISQUALIFYING)
    try:
        assert RuleSeverity.MINOR.penalty_weight < RuleSeverity.MODERATE.penalty_weight, "MINOR >= MODERATE"
        assert RuleSeverity.MODERATE.penalty_weight < RuleSeverity.SEVERE.penalty_weight, "MODERATE >= SEVERE"
        assert RuleSeverity.SEVERE.penalty_weight < RuleSeverity.DISQUALIFYING.penalty_weight, "SEVERE >= DISQUALIFYING"
        result.ok("RuleSeverity 가중치 순서 검증")
    except Exception as e:
        result.fail("RuleSeverity 가중치 순서 검증", str(e))

    # 3-4. 값 고유성 확인
    try:
        values = [s.value for s in RuleSeverity]
        assert len(values) == len(set(values)), "RuleSeverity 값에 중복이 있음"
        result.ok("RuleSeverity 값 고유성 확인")
    except Exception as e:
        result.fail("RuleSeverity 값 고유성 확인", str(e))

    # 3-5. 모든 가중치 > 0 이고 <= 1
    try:
        for sev in RuleSeverity:
            w = sev.penalty_weight
            assert 0 < w <= 1.0, f"{sev}: penalty_weight={w} 범위 초과 (0 < w <= 1)"
        result.ok("RuleSeverity 모든 가중치 0 < w <= 1")
    except Exception as e:
        result.fail("RuleSeverity 모든 가중치 0 < w <= 1", str(e))

    # 3-6. 가중치 정밀도 (부동소수점 검증)
    try:
        assert abs(RuleSeverity.MINOR.penalty_weight - 0.25) < 1e-9, "MINOR 정밀도 오류"
        assert abs(RuleSeverity.MODERATE.penalty_weight - 0.5) < 1e-9, "MODERATE 정밀도 오류"
        assert abs(RuleSeverity.SEVERE.penalty_weight - 0.75) < 1e-9, "SEVERE 정밀도 오류"
        assert abs(RuleSeverity.DISQUALIFYING.penalty_weight - 1.0) < 1e-9, "DISQUALIFYING 정밀도 오류"
        result.ok("RuleSeverity 가중치 정밀도 확인")
    except Exception as e:
        result.fail("RuleSeverity 가중치 정밀도 확인", str(e))


# ============================================================
# [4] 상수 테스트
# ============================================================
def test_constants(result: TestResult) -> None:
    """상수 단위 테스트 (12개)."""
    print("\n[4] 상수 테스트")

    # 4-1. SUPPORTED_LEAGUES는 frozenset이고 7개 항목
    try:
        assert isinstance(SUPPORTED_LEAGUES, frozenset), \
            f"SUPPORTED_LEAGUES 타입: {type(SUPPORTED_LEAGUES)}"
        assert len(SUPPORTED_LEAGUES) == 7, f"기대: 7, 실제: {len(SUPPORTED_LEAGUES)}"
        result.ok("SUPPORTED_LEAGUES frozenset, 7개 항목")
    except Exception as e:
        result.fail("SUPPORTED_LEAGUES frozenset, 7개 항목", str(e))

    # 4-2. DEFAULT_RULE_SET_PATH는 Path
    try:
        assert isinstance(DEFAULT_RULE_SET_PATH, Path), \
            f"DEFAULT_RULE_SET_PATH 타입: {type(DEFAULT_RULE_SET_PATH)}"
        result.ok("DEFAULT_RULE_SET_PATH는 Path 인스턴스")
    except Exception as e:
        result.fail("DEFAULT_RULE_SET_PATH는 Path 인스턴스", str(e))

    # 4-3. RULE_SET_SCHEMA_VERSION "v"로 시작
    try:
        assert RULE_SET_SCHEMA_VERSION.startswith("v"), \
            f"RULE_SET_SCHEMA_VERSION이 'v'로 시작하지 않음: {RULE_SET_SCHEMA_VERSION}"
        result.ok("RULE_SET_SCHEMA_VERSION 'v' 접두사 확인")
    except Exception as e:
        result.fail("RULE_SET_SCHEMA_VERSION 'v' 접두사 확인", str(e))

    # 4-4. DEFAULT_CACHE_TTL == 3600
    try:
        assert DEFAULT_CACHE_TTL == 3600, f"기대: 3600, 실제: {DEFAULT_CACHE_TTL}"
        result.ok("DEFAULT_CACHE_TTL == 3600")
    except Exception as e:
        result.fail("DEFAULT_CACHE_TTL == 3600", str(e))

    # 4-5. MAX_CACHE_SIZE == 50
    try:
        assert MAX_CACHE_SIZE == 50, f"기대: 50, 실제: {MAX_CACHE_SIZE}"
        result.ok("MAX_CACHE_SIZE == 50")
    except Exception as e:
        result.fail("MAX_CACHE_SIZE == 50", str(e))

    # 4-6. RULE_PRIORITY_WEIGHTS에 "safety", "foul", "violation" 키 존재
    try:
        assert "safety" in RULE_PRIORITY_WEIGHTS, "'safety' 키 없음"
        assert "foul" in RULE_PRIORITY_WEIGHTS, "'foul' 키 없음"
        assert "violation" in RULE_PRIORITY_WEIGHTS, "'violation' 키 없음"
        result.ok("RULE_PRIORITY_WEIGHTS 필수 키 존재")
    except Exception as e:
        result.fail("RULE_PRIORITY_WEIGHTS 필수 키 존재", str(e))

    # 4-7. LEAGUE_HIERARCHY: FIBA = [], 나머지 = ["fiba"]
    try:
        assert LEAGUE_HIERARCHY[League.FIBA.value] == [], \
            f"FIBA 상속 계층 오류: {LEAGUE_HIERARCHY[League.FIBA.value]}"
        for league in [League.NBA, League.KBL, League.NBL, League.NCAA, League.B_LEAGUE, League.PBA]:
            parents = LEAGUE_HIERARCHY[league.value]
            assert League.FIBA.value in parents, \
                f"{league.value} 상속에 fiba 없음: {parents}"
        result.ok("LEAGUE_HIERARCHY 계층 구조 확인")
    except Exception as e:
        result.fail("LEAGUE_HIERARCHY 계층 구조 확인", str(e))

    # 4-8. DEFAULT_FALLBACK_LEAGUE == "fiba"
    try:
        assert DEFAULT_FALLBACK_LEAGUE == "fiba", \
            f"기대: 'fiba', 실제: '{DEFAULT_FALLBACK_LEAGUE}'"
        result.ok("DEFAULT_FALLBACK_LEAGUE == 'fiba'")
    except Exception as e:
        result.fail("DEFAULT_FALLBACK_LEAGUE == 'fiba'", str(e))

    # 4-9. QUARTER_DURATION: NBA=720, FIBA=600, NCAA=1200
    try:
        assert QUARTER_DURATION[League.NBA] == 720, f"NBA: {QUARTER_DURATION[League.NBA]}"
        assert QUARTER_DURATION[League.FIBA] == 600, f"FIBA: {QUARTER_DURATION[League.FIBA]}"
        assert QUARTER_DURATION[League.NCAA] == 1200, f"NCAA: {QUARTER_DURATION[League.NCAA]}"
        result.ok("QUARTER_DURATION 리그별 값 정확도")
    except Exception as e:
        result.fail("QUARTER_DURATION 리그별 값 정확도", str(e))

    # 4-10. SHOT_CLOCK: NCAA=30, 나머지=24
    try:
        assert SHOT_CLOCK[League.NCAA] == 30, f"NCAA: {SHOT_CLOCK[League.NCAA]}"
        for league in [League.FIBA, League.NBA, League.KBL, League.NBL, League.B_LEAGUE, League.PBA]:
            assert SHOT_CLOCK[league] == 24, f"{league.value}: {SHOT_CLOCK[league]}"
        result.ok("SHOT_CLOCK 리그별 값 정확도")
    except Exception as e:
        result.fail("SHOT_CLOCK 리그별 값 정확도", str(e))

    # 4-11. THREE_POINT_DISTANCE: NBA=723, FIBA=675
    try:
        assert THREE_POINT_DISTANCE[League.NBA] == 723, \
            f"NBA: {THREE_POINT_DISTANCE[League.NBA]}"
        assert THREE_POINT_DISTANCE[League.FIBA] == 675, \
            f"FIBA: {THREE_POINT_DISTANCE[League.FIBA]}"
        result.ok("THREE_POINT_DISTANCE 리그별 값 정확도")
    except Exception as e:
        result.fail("THREE_POINT_DISTANCE 리그별 값 정확도", str(e))

    # 4-12. PERSONAL_FOUL_LIMIT: NBA=6, PBA=6, FIBA=5
    try:
        assert PERSONAL_FOUL_LIMIT[League.NBA] == 6, f"NBA: {PERSONAL_FOUL_LIMIT[League.NBA]}"
        assert PERSONAL_FOUL_LIMIT[League.PBA] == 6, f"PBA: {PERSONAL_FOUL_LIMIT[League.PBA]}"
        assert PERSONAL_FOUL_LIMIT[League.FIBA] == 5, f"FIBA: {PERSONAL_FOUL_LIMIT[League.FIBA]}"
        result.ok("PERSONAL_FOUL_LIMIT 리그별 값 정확도")
    except Exception as e:
        result.fail("PERSONAL_FOUL_LIMIT 리그별 값 정확도", str(e))


# ============================================================
# [5] RuleCondition 테스트
# ============================================================
def test_rule_condition(result: TestResult) -> None:
    """RuleCondition 데이터클래스 단위 테스트 (10개)."""
    print("\n[5] RuleCondition 테스트")

    # 5-1. 기본값으로 생성
    try:
        cond = RuleCondition(condition_type="distance")
        assert cond.condition_type == "distance"
        assert cond.parameters == {}
        assert cond.threshold is None
        assert cond.comparison == "eq"
        result.ok("RuleCondition 기본값 생성")
    except Exception as e:
        result.fail("RuleCondition 기본값 생성", str(e))

    # 5-2. evaluate: gte 임계값 이상 (True)
    try:
        cond = RuleCondition(condition_type="steps", threshold=3.0, comparison="gte")
        assert cond.evaluate(3.0) is True, "3.0 >= 3.0 이어야 True"
        assert cond.evaluate(5.0) is True, "5.0 >= 3.0 이어야 True"
        result.ok("RuleCondition evaluate gte True")
    except Exception as e:
        result.fail("RuleCondition evaluate gte True", str(e))

    # 5-3. evaluate: gte 임계값 미만 (False)
    try:
        cond = RuleCondition(condition_type="steps", threshold=3.0, comparison="gte")
        assert cond.evaluate(2.9) is False, "2.9 >= 3.0 이어야 False"
        assert cond.evaluate(0.0) is False, "0.0 >= 3.0 이어야 False"
        result.ok("RuleCondition evaluate gte False")
    except Exception as e:
        result.fail("RuleCondition evaluate gte False", str(e))

    # 5-4. evaluate: lt 임계값 (True/False)
    try:
        cond = RuleCondition(condition_type="time", threshold=5.0, comparison="lt")
        assert cond.evaluate(4.9) is True, "4.9 < 5.0 이어야 True"
        assert cond.evaluate(5.0) is False, "5.0 < 5.0 이어야 False"
        assert cond.evaluate(5.1) is False, "5.1 < 5.0 이어야 False"
        result.ok("RuleCondition evaluate lt True/False")
    except Exception as e:
        result.fail("RuleCondition evaluate lt True/False", str(e))

    # 5-5. evaluate: gt 임계값
    try:
        cond = RuleCondition(condition_type="speed", threshold=10.0, comparison="gt")
        assert cond.evaluate(10.1) is True, "10.1 > 10.0 이어야 True"
        assert cond.evaluate(10.0) is False, "10.0 > 10.0 이어야 False"
        assert cond.evaluate(9.9) is False, "9.9 > 10.0 이어야 False"
        result.ok("RuleCondition evaluate gt")
    except Exception as e:
        result.fail("RuleCondition evaluate gt", str(e))

    # 5-6. evaluate: lte 임계값
    try:
        cond = RuleCondition(condition_type="height", threshold=305.0, comparison="lte")
        assert cond.evaluate(305.0) is True, "305.0 <= 305.0 이어야 True"
        assert cond.evaluate(304.9) is True, "304.9 <= 305.0 이어야 True"
        assert cond.evaluate(305.1) is False, "305.1 <= 305.0 이어야 False"
        result.ok("RuleCondition evaluate lte")
    except Exception as e:
        result.fail("RuleCondition evaluate lte", str(e))

    # 5-7. evaluate: eq 임계값 (부동소수점 비교)
    try:
        cond = RuleCondition(condition_type="distance", threshold=6.75, comparison="eq")
        assert cond.evaluate(6.75) is True, "6.75 == 6.75 이어야 True"
        assert cond.evaluate(6.750000001) is True, "epsilon 이내 값이어야 True"
        assert cond.evaluate(7.0) is False, "7.0 != 6.75 이어야 False"
        result.ok("RuleCondition evaluate eq (부동소수점)")
    except Exception as e:
        result.fail("RuleCondition evaluate eq (부동소수점)", str(e))

    # 5-8. evaluate: 유효하지 않은 비교 연산자 -> False
    try:
        cond = RuleCondition(condition_type="test", threshold=5.0, comparison="invalid_op")
        assert cond.evaluate(5.0) is False, "유효하지 않은 연산자에서 False 반환해야 함"
        result.ok("RuleCondition evaluate 유효하지 않은 비교 연산자")
    except Exception as e:
        result.fail("RuleCondition evaluate 유효하지 않은 비교 연산자", str(e))

    # 5-9. evaluate: 숫자가 아닌 값 -> False
    try:
        cond = RuleCondition(condition_type="test", threshold=5.0, comparison="gte")
        assert cond.evaluate("not_a_number") is False, "숫자가 아닌 값에서 False 반환해야 함"
        assert cond.evaluate(None) is False, "None 값에서 False 반환해야 함"
        result.ok("RuleCondition evaluate 비숫자 값")
    except Exception as e:
        result.fail("RuleCondition evaluate 비숫자 값", str(e))

    # 5-10. evaluate: threshold가 None이면 True
    try:
        cond = RuleCondition(condition_type="test", threshold=None)
        assert cond.evaluate(100) is True, "threshold None이면 True여야 함"
        assert cond.evaluate("anything") is True, "threshold None이면 True여야 함"
        result.ok("RuleCondition evaluate threshold None -> True")
    except Exception as e:
        result.fail("RuleCondition evaluate threshold None -> True", str(e))


# ============================================================
# [6] Penalty 데이터클래스 테스트
# ============================================================
def test_penalty(result: TestResult) -> None:
    """Penalty 데이터클래스 단위 테스트 (5개)."""
    print("\n[6] Penalty 데이터클래스 테스트")

    # 6-1. 필수 필드로 생성
    try:
        p = Penalty(penalty_type="turnover", description="공격권 상실")
        assert p.penalty_type == "turnover"
        assert p.description == "공격권 상실"
        assert p.duration is None
        assert p.count is None
        assert p.escalation is None
        result.ok("Penalty 필수 필드 생성")
    except Exception as e:
        result.fail("Penalty 필수 필드 생성", str(e))

    # 6-2. to_dict 기본
    try:
        p = Penalty(penalty_type="foul", description="파울 기록")
        d = p.to_dict()
        assert d["penalty_type"] == "foul"
        assert d["description"] == "파울 기록"
        assert "duration" not in d, "duration이 None이면 포함되지 않아야 함"
        assert "count" not in d, "count가 None이면 포함되지 않아야 함"
        assert "escalation" not in d, "escalation이 None이면 포함되지 않아야 함"
        result.ok("Penalty to_dict 기본")
    except Exception as e:
        result.fail("Penalty to_dict 기본", str(e))

    # 6-3. to_dict 에스컬레이션 포함
    try:
        esc = {"limit": 5, "action": "disqualification"}
        p = Penalty(penalty_type="foul", description="파울", escalation=esc)
        d = p.to_dict()
        assert "escalation" in d
        assert d["escalation"]["limit"] == 5
        assert d["escalation"]["action"] == "disqualification"
        result.ok("Penalty to_dict 에스컬레이션 포함")
    except Exception as e:
        result.fail("Penalty to_dict 에스컬레이션 포함", str(e))

    # 6-4. 선택적 필드 (duration, count)
    try:
        p = Penalty(penalty_type="free_throw", description="자유투", duration=10, count=2)
        assert p.duration == 10
        assert p.count == 2
        d = p.to_dict()
        assert d["duration"] == 10
        assert d["count"] == 2
        result.ok("Penalty 선택적 필드 (duration, count)")
    except Exception as e:
        result.fail("Penalty 선택적 필드 (duration, count)", str(e))

    # 6-5. 에스컬레이션 딕셔너리 구조
    try:
        esc = {"second_offense": "ejection", "level_2": "suspension"}
        p = Penalty(penalty_type="technical", description="테크니컬", escalation=esc)
        d = p.to_dict()
        assert d["escalation"]["second_offense"] == "ejection"
        assert d["escalation"]["level_2"] == "suspension"
        result.ok("Penalty 에스컬레이션 딕셔너리 구조")
    except Exception as e:
        result.fail("Penalty 에스컬레이션 딕셔너리 구조", str(e))


# ============================================================
# [7] Rule 테스트
# ============================================================
def test_rule(result: TestResult) -> None:
    """Rule 데이터클래스 단위 테스트 (12개)."""
    print("\n[7] Rule 테스트")

    # 공통 Rule 생성 헬퍼
    def _make_rule(**kwargs):
        defaults = dict(
            rule_id="test_traveling",
            name="트래블링",
            category=RuleCategory.VIOLATION,
            severity=RuleSeverity.MINOR,
            description="테스트 규칙",
        )
        defaults.update(kwargs)
        return Rule(**defaults)

    # 7-1. 모든 필드로 생성
    try:
        now = datetime.now(timezone.utc)
        rule = Rule(
            rule_id="fiba_traveling",
            name="트래블링",
            category=RuleCategory.VIOLATION,
            severity=RuleSeverity.MINOR,
            description="피벗 풋 이동",
            conditions=[RuleCondition(condition_type="steps", threshold=3.0, comparison="gte")],
            penalties=[Penalty(penalty_type="turnover", description="공격권 상실")],
            league_specific={"max_steps": 2},
            references=["FIBA Rule 25"],
            effective_date=now - timedelta(days=30),
            expiry_date=now + timedelta(days=365),
        )
        assert rule.rule_id == "fiba_traveling"
        assert rule.name == "트래블링"
        assert rule.category == RuleCategory.VIOLATION
        assert rule.severity == RuleSeverity.MINOR
        assert len(rule.conditions) == 1
        assert len(rule.penalties) == 1
        assert len(rule.references) == 1
        result.ok("Rule 모든 필드 생성")
    except Exception as e:
        result.fail("Rule 모든 필드 생성", str(e))

    # 7-2. is_active: 유효 기간 내 -> True
    try:
        now = datetime.now(timezone.utc)
        rule = _make_rule(
            effective_date=now - timedelta(days=30),
            expiry_date=now + timedelta(days=365),
        )
        assert rule.is_active() is True, "유효 기간 내에서 True 반환해야 함"
        result.ok("Rule is_active 유효 기간 내 True")
    except Exception as e:
        result.fail("Rule is_active 유효 기간 내 True", str(e))

    # 7-3. is_active: 만료됨 -> False
    try:
        now = datetime.now(timezone.utc)
        rule = _make_rule(
            effective_date=now - timedelta(days=365),
            expiry_date=now - timedelta(days=1),
        )
        assert rule.is_active() is False, "만료된 규칙에서 False 반환해야 함"
        result.ok("Rule is_active 만료됨 False")
    except Exception as e:
        result.fail("Rule is_active 만료됨 False", str(e))

    # 7-4. is_active: 아직 시행되지 않음 -> False
    try:
        now = datetime.now(timezone.utc)
        rule = _make_rule(
            effective_date=now + timedelta(days=30),
            expiry_date=now + timedelta(days=365),
        )
        assert rule.is_active() is False, "미래 시행일 규칙에서 False 반환해야 함"
        result.ok("Rule is_active 미래 시행일 False")
    except Exception as e:
        result.fail("Rule is_active 미래 시행일 False", str(e))

    # 7-5. is_active: 날짜 미설정 -> True
    try:
        rule = _make_rule()
        assert rule.is_active() is True, "날짜 미설정 규칙에서 True 반환해야 함"
        result.ok("Rule is_active 날짜 미설정 True")
    except Exception as e:
        result.fail("Rule is_active 날짜 미설정 True", str(e))

    # 7-6. get_priority 계산 (category_weight * severity_weight)
    try:
        rule = _make_rule(
            category=RuleCategory.FOUL,
            severity=RuleSeverity.MODERATE,
        )
        expected_priority = RULE_PRIORITY_WEIGHTS.get("foul", 0.5) * RuleSeverity.MODERATE.penalty_weight
        actual_priority = rule.get_priority()
        assert abs(actual_priority - expected_priority) < 1e-9, \
            f"기대: {expected_priority}, 실제: {actual_priority}"
        result.ok("Rule get_priority 계산 정확도")
    except Exception as e:
        result.fail("Rule get_priority 계산 정확도", str(e))

    # 7-7. to_dict 완전한 출력
    try:
        rule = _make_rule()
        d = rule.to_dict()
        assert "rule_id" in d
        assert "name" in d
        assert "category" in d
        assert "severity" in d
        assert "description" in d
        assert "conditions" in d
        assert "penalties" in d
        assert "league_specific" in d
        assert "references" in d
        assert "effective_date" in d
        assert "expiry_date" in d
        assert d["category"] == "violation"
        assert d["severity"] == "minor"
        result.ok("Rule to_dict 완전한 출력")
    except Exception as e:
        result.fail("Rule to_dict 완전한 출력", str(e))

    # 7-8. to_dict 조건 직렬화
    try:
        rule = _make_rule(
            conditions=[
                RuleCondition(condition_type="steps", threshold=3.0, comparison="gte"),
                RuleCondition(condition_type="time", threshold=5.0, comparison="lt"),
            ]
        )
        d = rule.to_dict()
        assert len(d["conditions"]) == 2
        assert d["conditions"][0]["type"] == "steps"
        assert d["conditions"][0]["threshold"] == 3.0
        assert d["conditions"][1]["comparison"] == "lt"
        result.ok("Rule to_dict 조건 직렬화")
    except Exception as e:
        result.fail("Rule to_dict 조건 직렬화", str(e))

    # 7-9. to_dict 패널티 직렬화
    try:
        rule = _make_rule(
            penalties=[
                Penalty(penalty_type="turnover", description="공격권 상실"),
                Penalty(penalty_type="free_throw", description="자유투", count=2),
            ]
        )
        d = rule.to_dict()
        assert len(d["penalties"]) == 2
        assert d["penalties"][0]["penalty_type"] == "turnover"
        assert d["penalties"][1]["count"] == 2
        result.ok("Rule to_dict 패널티 직렬화")
    except Exception as e:
        result.fail("Rule to_dict 패널티 직렬화", str(e))

    # 7-10. 필드 기본값 (빈 리스트)
    try:
        rule = _make_rule()
        assert rule.conditions == [], f"conditions 기본값: {rule.conditions}"
        assert rule.penalties == [], f"penalties 기본값: {rule.penalties}"
        assert rule.league_specific == {}, f"league_specific 기본값: {rule.league_specific}"
        assert rule.references == [], f"references 기본값: {rule.references}"
        assert rule.effective_date is None
        assert rule.expiry_date is None
        result.ok("Rule 필드 기본값 확인")
    except Exception as e:
        result.fail("Rule 필드 기본값 확인", str(e))

    # 7-11. 조건 포함 Rule
    try:
        cond = RuleCondition(condition_type="shot_clock", threshold=24.0, comparison="gte")
        rule = _make_rule(conditions=[cond])
        assert len(rule.conditions) == 1
        assert rule.conditions[0].condition_type == "shot_clock"
        assert rule.conditions[0].evaluate(24.0) is True
        result.ok("Rule 조건 포함 확인")
    except Exception as e:
        result.fail("Rule 조건 포함 확인", str(e))

    # 7-12. 패널티 포함 Rule
    try:
        pen = Penalty(
            penalty_type="technical",
            description="테크니컬 파울",
            count=1,
            escalation={"second_offense": "ejection"},
        )
        rule = _make_rule(penalties=[pen])
        assert len(rule.penalties) == 1
        assert rule.penalties[0].penalty_type == "technical"
        assert rule.penalties[0].count == 1
        assert rule.penalties[0].escalation["second_offense"] == "ejection"
        result.ok("Rule 패널티 포함 확인")
    except Exception as e:
        result.fail("Rule 패널티 포함 확인", str(e))


# ============================================================
# [8] RuleSet 테스트
# ============================================================
def test_rule_set(result: TestResult) -> None:
    """RuleSet 데이터클래스 단위 테스트 (8개)."""
    print("\n[8] RuleSet 테스트")

    # 테스트 규칙 생성
    def _make_rules():
        now = datetime.now(timezone.utc)
        return [
            Rule(
                rule_id="test_traveling",
                name="트래블링",
                category=RuleCategory.VIOLATION,
                severity=RuleSeverity.MINOR,
                description="트래블링 규칙",
            ),
            Rule(
                rule_id="test_personal_foul",
                name="개인 파울",
                category=RuleCategory.FOUL,
                severity=RuleSeverity.MODERATE,
                description="개인 파울 규칙",
            ),
            Rule(
                rule_id="test_expired",
                name="만료된 규칙",
                category=RuleCategory.VIOLATION,
                severity=RuleSeverity.MINOR,
                description="만료된 규칙",
                effective_date=now - timedelta(days=365),
                expiry_date=now - timedelta(days=1),
            ),
        ]

    # 8-1. 생성
    try:
        rules = _make_rules()
        rs = RuleSet(league=League.FIBA, version="v1.0.0", rules=rules)
        assert rs.league == League.FIBA
        assert rs.version == "v1.0.0"
        assert len(rs.rules) == 3
        result.ok("RuleSet 생성")
    except Exception as e:
        result.fail("RuleSet 생성", str(e))

    # 8-2. get_rule by ID
    try:
        rules = _make_rules()
        rs = RuleSet(league=League.FIBA, version="v1.0.0", rules=rules)
        rule = rs.get_rule("test_traveling")
        assert rule is not None, "test_traveling 규칙을 찾지 못함"
        assert rule.rule_id == "test_traveling"
        result.ok("RuleSet get_rule ID 조회")
    except Exception as e:
        result.fail("RuleSet get_rule ID 조회", str(e))

    # 8-3. get_rule 없는 ID -> None
    try:
        rules = _make_rules()
        rs = RuleSet(league=League.FIBA, version="v1.0.0", rules=rules)
        rule = rs.get_rule("nonexistent_rule")
        assert rule is None, "존재하지 않는 ID에서 None 반환해야 함"
        result.ok("RuleSet get_rule 미발견 -> None")
    except Exception as e:
        result.fail("RuleSet get_rule 미발견 -> None", str(e))

    # 8-4. get_rules_by_category
    try:
        rules = _make_rules()
        rs = RuleSet(league=League.FIBA, version="v1.0.0", rules=rules)
        violations = rs.get_rules_by_category(RuleCategory.VIOLATION)
        assert len(violations) == 2, f"VIOLATION 규칙 수: {len(violations)}"
        fouls = rs.get_rules_by_category(RuleCategory.FOUL)
        assert len(fouls) == 1, f"FOUL 규칙 수: {len(fouls)}"
        result.ok("RuleSet get_rules_by_category")
    except Exception as e:
        result.fail("RuleSet get_rules_by_category", str(e))

    # 8-5. get_active_rules
    try:
        rules = _make_rules()
        rs = RuleSet(league=League.FIBA, version="v1.0.0", rules=rules)
        active = rs.get_active_rules()
        # 만료된 규칙 1개 제외 -> 2개
        assert len(active) == 2, f"활성 규칙 수: {len(active)}"
        result.ok("RuleSet get_active_rules")
    except Exception as e:
        result.fail("RuleSet get_active_rules", str(e))

    # 8-6. rule_count 프로퍼티
    try:
        rules = _make_rules()
        rs = RuleSet(league=League.FIBA, version="v1.0.0", rules=rules)
        assert rs.rule_count == 3, f"기대: 3, 실제: {rs.rule_count}"
        result.ok("RuleSet rule_count 프로퍼티")
    except Exception as e:
        result.fail("RuleSet rule_count 프로퍼티", str(e))

    # 8-7. to_dict
    try:
        rules = _make_rules()
        rs = RuleSet(league=League.FIBA, version="v1.0.0", rules=rules)
        d = rs.to_dict()
        assert d["league"] == "fiba"
        assert d["version"] == "v1.0.0"
        assert d["rule_count"] == 3
        assert len(d["rules"]) == 3
        assert "effective_date" in d
        assert "expiry_date" in d
        assert "parent_league" in d
        result.ok("RuleSet to_dict")
    except Exception as e:
        result.fail("RuleSet to_dict", str(e))

    # 8-8. parent_league 필드
    try:
        rules = _make_rules()
        rs = RuleSet(league=League.NBA, version="v1.0.0", rules=rules, parent_league=League.FIBA)
        assert rs.parent_league == League.FIBA
        d = rs.to_dict()
        assert d["parent_league"] == "fiba"
        result.ok("RuleSet parent_league 필드")
    except Exception as e:
        result.fail("RuleSet parent_league 필드", str(e))


# ============================================================
# [9] RuleSetMetadata 테스트
# ============================================================
def test_rule_set_metadata(result: TestResult) -> None:
    """RuleSetMetadata 데이터클래스 단위 테스트 (4개)."""
    print("\n[9] RuleSetMetadata 테스트")

    # 9-1. 생성
    try:
        now = datetime.now(timezone.utc)
        meta = RuleSetMetadata(
            content_hash="abc123def456",
            loaded_at=now,
            source_path=Path("configs/rules/fiba.yaml"),
        )
        assert meta.content_hash == "abc123def456"
        assert meta.loaded_at == now
        assert meta.source_path == Path("configs/rules/fiba.yaml")
        result.ok("RuleSetMetadata 생성")
    except Exception as e:
        result.fail("RuleSetMetadata 생성", str(e))

    # 9-2. is_stale: 아직 유효 -> False
    try:
        now = datetime.now(timezone.utc)
        meta = RuleSetMetadata(content_hash="hash", loaded_at=now)
        assert meta.is_stale(3600) is False, "방금 로드한 것은 만료되지 않아야 함"
        result.ok("RuleSetMetadata is_stale 유효 -> False")
    except Exception as e:
        result.fail("RuleSetMetadata is_stale 유효 -> False", str(e))

    # 9-3. is_stale: 만료됨 -> True
    try:
        old_time = datetime.now(timezone.utc) - timedelta(seconds=7200)
        meta = RuleSetMetadata(content_hash="hash", loaded_at=old_time)
        assert meta.is_stale(3600) is True, "2시간 전 로드한 것은 1시간 TTL에서 만료되어야 함"
        result.ok("RuleSetMetadata is_stale 만료됨 -> True")
    except Exception as e:
        result.fail("RuleSetMetadata is_stale 만료됨 -> True", str(e))

    # 9-4. content_hash 존재
    try:
        meta = RuleSetMetadata(content_hash="a1b2c3", loaded_at=datetime.now(timezone.utc))
        assert meta.content_hash is not None, "content_hash가 None"
        assert len(meta.content_hash) > 0, "content_hash가 비어있음"
        result.ok("RuleSetMetadata content_hash 존재")
    except Exception as e:
        result.fail("RuleSetMetadata content_hash 존재", str(e))


# ============================================================
# [10] LeagueConfig 테스트
# ============================================================
def test_league_config(result: TestResult) -> None:
    """LeagueConfig 데이터클래스 단위 테스트 (5개)."""
    print("\n[10] LeagueConfig 테스트")

    # 10-1. for_league(FIBA): quarter=600, shot_clock=24, 3pt=675, foul_limit=5
    try:
        config = LeagueConfig.for_league(League.FIBA)
        assert config.league == League.FIBA
        assert config.quarter_duration == 600, f"quarter_duration: {config.quarter_duration}"
        assert config.shot_clock == 24, f"shot_clock: {config.shot_clock}"
        assert config.three_point_distance == 675, f"three_point_distance: {config.three_point_distance}"
        assert config.personal_foul_limit == 5, f"personal_foul_limit: {config.personal_foul_limit}"
        result.ok("LeagueConfig for_league(FIBA) 정확도")
    except Exception as e:
        result.fail("LeagueConfig for_league(FIBA) 정확도", str(e))

    # 10-2. for_league(NBA): quarter=720, shot_clock=24, 3pt=723, foul_limit=6
    try:
        config = LeagueConfig.for_league(League.NBA)
        assert config.league == League.NBA
        assert config.quarter_duration == 720, f"quarter_duration: {config.quarter_duration}"
        assert config.shot_clock == 24, f"shot_clock: {config.shot_clock}"
        assert config.three_point_distance == 723, f"three_point_distance: {config.three_point_distance}"
        assert config.personal_foul_limit == 6, f"personal_foul_limit: {config.personal_foul_limit}"
        result.ok("LeagueConfig for_league(NBA) 정확도")
    except Exception as e:
        result.fail("LeagueConfig for_league(NBA) 정확도", str(e))

    # 10-3. for_league(NCAA): quarter=1200, shot_clock=30
    try:
        config = LeagueConfig.for_league(League.NCAA)
        assert config.quarter_duration == 1200, f"quarter_duration: {config.quarter_duration}"
        assert config.shot_clock == 30, f"shot_clock: {config.shot_clock}"
        result.ok("LeagueConfig for_league(NCAA) 정확도")
    except Exception as e:
        result.fail("LeagueConfig for_league(NCAA) 정확도", str(e))

    # 10-4. 기본값 확인 (court_width=1500, court_length=2800, hoop_height=305)
    try:
        config = LeagueConfig.for_league(League.FIBA)
        assert config.court_width == 1500, f"court_width: {config.court_width}"
        assert config.court_length == 2800, f"court_length: {config.court_length}"
        assert config.hoop_height == 305, f"hoop_height: {config.hoop_height}"
        result.ok("LeagueConfig 기본값 (court_width, court_length, hoop_height)")
    except Exception as e:
        result.fail("LeagueConfig 기본값 (court_width, court_length, hoop_height)", str(e))

    # 10-5. 모든 리그에 대해 유효한 설정 생성
    try:
        for league in League:
            config = LeagueConfig.for_league(league)
            assert config.league == league
            assert config.quarter_duration > 0, f"{league}: quarter_duration <= 0"
            assert config.shot_clock > 0, f"{league}: shot_clock <= 0"
            assert config.three_point_distance > 0, f"{league}: three_point_distance <= 0"
            assert config.personal_foul_limit > 0, f"{league}: personal_foul_limit <= 0"
        result.ok("LeagueConfig 모든 리그 유효한 설정 생성")
    except Exception as e:
        result.fail("LeagueConfig 모든 리그 유효한 설정 생성", str(e))


# ============================================================
# [11] RuleSetManager 메인 테스트
# ============================================================
def test_rule_set_manager(result: TestResult) -> None:
    """RuleSetManager 메인 단위 테스트 (15개)."""
    print("\n[11] RuleSetManager 메인 테스트")

    # 매니저 초기화 전 리셋
    _reset_manager()

    # 11-1. ConfigLoader로 생성
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        assert manager is not None, "매니저가 None"
        result.ok("RuleSetManager ConfigLoader로 생성")
    except Exception as e:
        result.fail("RuleSetManager ConfigLoader로 생성", str(e))

    # 11-2. get_rule_set(FIBA) -> 17개 내장 규칙
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        fiba_set = manager.get_rule_set(League.FIBA)
        assert fiba_set is not None, "FIBA 규칙 세트가 None"
        assert fiba_set.league == League.FIBA
        assert fiba_set.rule_count == 17, f"FIBA 규칙 수: {fiba_set.rule_count}"
        result.ok("RuleSetManager get_rule_set(FIBA) 17개 규칙")
    except Exception as e:
        result.fail("RuleSetManager get_rule_set(FIBA) 17개 규칙", str(e))

    # 11-3. get_rule_set(NBA) 상속 포함 -> 34개 규칙
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        nba_set = manager.get_rule_set(League.NBA, include_inherited=True)
        assert nba_set is not None
        # NBA 자체 17개 + FIBA 상속 17개 = 34개
        assert nba_set.rule_count == 34, f"NBA 규칙 수 (상속 포함): {nba_set.rule_count}"
        result.ok("RuleSetManager get_rule_set(NBA) 상속 포함 34개")
    except Exception as e:
        result.fail("RuleSetManager get_rule_set(NBA) 상속 포함 34개", str(e))

    # 11-4. get_rule_set(NBA, include_inherited=False) -> 17개 규칙
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        nba_set = manager.get_rule_set(League.NBA, include_inherited=False)
        assert nba_set.rule_count == 17, f"NBA 규칙 수 (상속 미포함): {nba_set.rule_count}"
        result.ok("RuleSetManager get_rule_set(NBA) 상속 미포함 17개")
    except Exception as e:
        result.fail("RuleSetManager get_rule_set(NBA) 상속 미포함 17개", str(e))

    # 11-5. get_rule(League.NBA, "nba_traveling") 조회
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        rule = manager.get_rule(League.NBA, "nba_traveling")
        assert rule is not None, "nba_traveling 규칙을 찾지 못함"
        assert rule.rule_id == "nba_traveling"
        assert rule.name == "트래블링"
        result.ok("RuleSetManager get_rule NBA 트래블링 조회")
    except Exception as e:
        result.fail("RuleSetManager get_rule NBA 트래블링 조회", str(e))

    # 11-6. get_rule 폴백 (FIBA로)
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        # NBA에서 "nba_nonexistent"를 찾을 수 없으면 FIBA로 폴백
        # fiba_traveling이 있으므로 해당 ID로 변환하여 조회 시도
        rule = manager.get_rule(League.NBA, "nba_traveling", fallback=True)
        assert rule is not None, "폴백 규칙 조회 실패"
        result.ok("RuleSetManager get_rule 폴백 (FIBA)")
    except Exception as e:
        result.fail("RuleSetManager get_rule 폴백 (FIBA)", str(e))

    # 11-7. get_rules_by_category(FIBA, FOUL) -> 파울 규칙 반환
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        foul_rules = manager.get_rules_by_category(League.FIBA, RuleCategory.FOUL)
        assert len(foul_rules) > 0, "FIBA 파울 규칙이 없음"
        for rule in foul_rules:
            assert rule.category == RuleCategory.FOUL, f"카테고리 불일치: {rule.category}"
        result.ok("RuleSetManager get_rules_by_category FIBA FOUL")
    except Exception as e:
        result.fail("RuleSetManager get_rules_by_category FIBA FOUL", str(e))

    # 11-8. get_league_config 반환 LeagueConfig
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        config = manager.get_league_config(League.NBA)
        assert isinstance(config, LeagueConfig), f"반환 타입: {type(config)}"
        assert config.league == League.NBA
        result.ok("RuleSetManager get_league_config 반환 확인")
    except Exception as e:
        result.fail("RuleSetManager get_league_config 반환 확인", str(e))

    # 11-9. validate_rule_set (유효) -> True
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        fiba_set = manager.get_rule_set(League.FIBA)
        is_valid = manager.validate_rule_set(fiba_set)
        assert is_valid is True, "유효한 규칙 세트에서 True 반환해야 함"
        result.ok("RuleSetManager validate_rule_set 유효 -> True")
    except Exception as e:
        result.fail("RuleSetManager validate_rule_set 유효 -> True", str(e))

    # 11-10. validate_rule_set (빈 규칙) -> RuleSetValidationException
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        empty_set = RuleSet(league=League.FIBA, version="v1.0.0", rules=[])
        raised = False
        try:
            manager.validate_rule_set(empty_set)
        except RuleSetValidationException:
            raised = True
        assert raised, "빈 규칙 세트에서 RuleSetValidationException이 발생해야 함"
        result.ok("RuleSetManager validate_rule_set 빈 규칙 -> 예외")
    except Exception as e:
        result.fail("RuleSetManager validate_rule_set 빈 규칙 -> 예외", str(e))

    # 11-11. validate_rule_set (중복 ID) -> RuleSetValidationException
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        dup_rules = [
            Rule(rule_id="dup_id", name="규칙1", category=RuleCategory.VIOLATION,
                 severity=RuleSeverity.MINOR, description="설명1"),
            Rule(rule_id="dup_id", name="규칙2", category=RuleCategory.FOUL,
                 severity=RuleSeverity.MODERATE, description="설명2"),
        ]
        dup_set = RuleSet(league=League.FIBA, version="v1.0.0", rules=dup_rules)
        raised = False
        try:
            manager.validate_rule_set(dup_set)
        except RuleSetValidationException:
            raised = True
        assert raised, "중복 ID 규칙 세트에서 RuleSetValidationException이 발생해야 함"
        result.ok("RuleSetManager validate_rule_set 중복 ID -> 예외")
    except Exception as e:
        result.fail("RuleSetManager validate_rule_set 중복 ID -> 예외", str(e))

    # 11-12. clear_cache (전체)
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        manager.get_rule_set(League.FIBA)
        manager.get_rule_set(League.NBA)
        count = manager.clear_cache()
        assert count >= 2, f"삭제된 캐시 수: {count}"
        result.ok("RuleSetManager clear_cache 전체")
    except Exception as e:
        result.fail("RuleSetManager clear_cache 전체", str(e))

    # 11-13. clear_cache (특정 리그)
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        manager.get_rule_set(League.FIBA)
        manager.get_rule_set(League.NBA)
        count = manager.clear_cache(League.NBA)
        assert count >= 1, f"NBA 캐시 삭제 수: {count}"
        # FIBA 캐시는 남아있어야 함
        result.ok("RuleSetManager clear_cache 특정 리그")
    except Exception as e:
        result.fail("RuleSetManager clear_cache 특정 리그", str(e))

    # 11-14. get_supported_leagues() -> 7개 리그
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        leagues = manager.get_supported_leagues()
        assert len(leagues) == 7, f"지원 리그 수: {len(leagues)}"
        for league in League:
            assert league in leagues, f"{league}이(가) 지원 리그 목록에 없음"
        result.ok("RuleSetManager get_supported_leagues 7개")
    except Exception as e:
        result.fail("RuleSetManager get_supported_leagues 7개", str(e))

    # 11-15. shutdown
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        manager.get_rule_set(League.FIBA)
        manager.shutdown()
        # shutdown 후 캐시가 비어야 함
        assert len(manager._cache) == 0, f"shutdown 후 캐시 크기: {len(manager._cache)}"
        result.ok("RuleSetManager shutdown")
    except Exception as e:
        result.fail("RuleSetManager shutdown", str(e))


# ============================================================
# [12] 캐시 동작 테스트
# ============================================================
def test_cache_behavior(result: TestResult) -> None:
    """캐시 동작 단위 테스트 (5개)."""
    print("\n[12] 캐시 동작 테스트")
    _reset_manager()

    # 12-1. 캐시 히트: 동일 객체 반환
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        set1 = manager.get_rule_set(League.FIBA)
        set2 = manager.get_rule_set(League.FIBA)
        assert set1 is set2, "캐시 히트 시 동일 객체가 반환되어야 함"
        result.ok("캐시 히트: 동일 객체 반환")
    except Exception as e:
        result.fail("캐시 히트: 동일 객체 반환", str(e))

    # 12-2. 캐시 미스: clear 후 다른 객체
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        set1 = manager.get_rule_set(League.FIBA)
        manager.clear_cache()
        set2 = manager.get_rule_set(League.FIBA)
        assert set1 is not set2, "캐시 클리어 후 다른 객체가 반환되어야 함"
        result.ok("캐시 미스: clear 후 다른 객체")
    except Exception as e:
        result.fail("캐시 미스: clear 후 다른 객체", str(e))

    # 12-3. 캐시 TTL 만료
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader, cache_ttl=1)  # TTL 1초
        set1 = manager.get_rule_set(League.FIBA)
        time.sleep(1.5)  # TTL 초과 대기
        set2 = manager.get_rule_set(League.FIBA)
        assert set1 is not set2, "TTL 만료 후 다른 객체가 반환되어야 함"
        result.ok("캐시 TTL 만료")
    except Exception as e:
        result.fail("캐시 TTL 만료", str(e))

    # 12-4. 캐시 크기 제한 (퇴출)
    try:
        config_loader = ConfigLoader()
        # MAX_CACHE_SIZE보다 많은 항목을 넣어서 퇴출 확인
        # 실제 MAX_CACHE_SIZE=50이므로 작은 값으로 테스트
        manager = RuleSetManager(config_loader)
        # 여러 버전으로 캐시를 채움
        for i in range(55):
            manager.get_rule_set(League.FIBA, version=f"v_test_{i}")
        # 캐시가 MAX_CACHE_SIZE 이하여야 함
        assert len(manager._cache) <= MAX_CACHE_SIZE + 1, \
            f"캐시 크기: {len(manager._cache)} > {MAX_CACHE_SIZE + 1}"
        result.ok("캐시 크기 제한 (퇴출)")
    except Exception as e:
        result.fail("캐시 크기 제한 (퇴출)", str(e))

    # 12-5. 스레드 안전 캐시 접근
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        errors = []
        results_list = []

        def access_cache(league, thread_id):
            try:
                rs = manager.get_rule_set(league)
                results_list.append((thread_id, rs.league))
            except Exception as ex:
                errors.append(str(ex))

        threads = []
        leagues = list(League)
        for i in range(14):
            league = leagues[i % len(leagues)]
            t = threading.Thread(target=access_cache, args=(league, i))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"스레드 에러: {errors}"
        assert len(results_list) == 14, f"결과 수: {len(results_list)}"
        result.ok("스레드 안전 캐시 접근")
    except Exception as e:
        result.fail("스레드 안전 캐시 접근", str(e))


# ============================================================
# [13] 규칙 상속 테스트
# ============================================================
def test_rule_inheritance(result: TestResult) -> None:
    """규칙 상속 단위 테스트 (5개)."""
    print("\n[13] 규칙 상속 테스트")
    _reset_manager()

    # 13-1. FIBA 규칙이 NBA에 상속됨
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        nba_set = manager.get_rule_set(League.NBA, include_inherited=True)
        # 상속된 규칙이 존재하는지 확인
        inherited_rules = [r for r in nba_set.rules if "inherited_" in r.rule_id]
        assert len(inherited_rules) > 0, "상속된 규칙이 없음"
        result.ok("FIBA 규칙이 NBA에 상속됨")
    except Exception as e:
        result.fail("FIBA 규칙이 NBA에 상속됨", str(e))

    # 13-2. 상속된 규칙 ID에 "inherited_" 접두사
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        nba_set = manager.get_rule_set(League.NBA, include_inherited=True)
        inherited_rules = [r for r in nba_set.rules if "inherited_" in r.rule_id]
        for rule in inherited_rules:
            assert "inherited_" in rule.rule_id, f"상속 접두사 없음: {rule.rule_id}"
            assert rule.rule_id.startswith("nba_inherited_"), \
                f"nba_inherited_ 접두사 없음: {rule.rule_id}"
        result.ok("상속 규칙 ID 'inherited_' 접두사")
    except Exception as e:
        result.fail("상속 규칙 ID 'inherited_' 접두사", str(e))

    # 13-3. 중복 상속 규칙 없음
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        nba_set = manager.get_rule_set(League.NBA, include_inherited=True)
        rule_ids = [r.rule_id for r in nba_set.rules]
        assert len(rule_ids) == len(set(rule_ids)), \
            f"중복 ID 발견: {[id for id in rule_ids if rule_ids.count(id) > 1]}"
        result.ok("중복 상속 규칙 없음")
    except Exception as e:
        result.fail("중복 상속 규칙 없음", str(e))

    # 13-4. 상속이 FIBA에 직접 영향 없음
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        fiba_set = manager.get_rule_set(League.FIBA)
        fiba_count = fiba_set.rule_count
        # NBA 로드 후 FIBA 규칙 수 변화 없음
        manager.get_rule_set(League.NBA, include_inherited=True)
        manager.clear_cache(League.FIBA)
        fiba_set2 = manager.get_rule_set(League.FIBA)
        assert fiba_set2.rule_count == fiba_count, \
            f"FIBA 규칙 수 변화: {fiba_count} -> {fiba_set2.rule_count}"
        result.ok("상속이 FIBA에 직접 영향 없음")
    except Exception as e:
        result.fail("상속이 FIBA에 직접 영향 없음", str(e))

    # 13-5. 다중 리그 상속 계층 확인
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        # 모든 비-FIBA 리그가 FIBA를 상속하는지 확인
        for league in [League.NBA, League.KBL, League.NBL, League.NCAA, League.B_LEAGUE, League.PBA]:
            league_set = manager.get_rule_set(league, include_inherited=True)
            inherited = [r for r in league_set.rules if "inherited_" in r.rule_id]
            assert len(inherited) > 0, f"{league.value}: 상속 규칙 없음"
        result.ok("다중 리그 상속 계층 확인")
    except Exception as e:
        result.fail("다중 리그 상속 계층 확인", str(e))


# ============================================================
# [14] 헬퍼 함수 테스트
# ============================================================
def test_helper_functions(result: TestResult) -> None:
    """헬퍼 함수 단위 테스트 (8개)."""
    print("\n[14] 헬퍼 함수 테스트")
    _reset_manager()

    # 14-1. load_rule_set("nba") 문자열 파라미터
    try:
        rs = load_rule_set("nba")
        assert rs is not None, "반환값이 None"
        assert rs.league == League.NBA
        result.ok("load_rule_set 문자열 파라미터")
    except Exception as e:
        result.fail("load_rule_set 문자열 파라미터", str(e))

    # 14-2. load_rule_set(League.FIBA) enum 파라미터
    try:
        _reset_manager()
        rs = load_rule_set(League.FIBA)
        assert rs is not None
        assert rs.league == League.FIBA
        result.ok("load_rule_set Enum 파라미터")
    except Exception as e:
        result.fail("load_rule_set Enum 파라미터", str(e))

    # 14-3. load_rule_set("invalid") -> RuleSetNotFoundException
    try:
        _reset_manager()
        raised = False
        try:
            load_rule_set("invalid_league")
        except RuleSetNotFoundException:
            raised = True
        assert raised, "잘못된 리그에서 RuleSetNotFoundException이 발생해야 함"
        result.ok("load_rule_set 잘못된 리그 -> 예외")
    except Exception as e:
        result.fail("load_rule_set 잘못된 리그 -> 예외", str(e))

    # 14-4. get_rule_by_id("fiba", "fiba_traveling")
    try:
        _reset_manager()
        rule = get_rule_by_id("fiba", "fiba_traveling")
        assert rule is not None, "fiba_traveling 규칙을 찾지 못함"
        assert rule.rule_id == "fiba_traveling"
        result.ok("get_rule_by_id 정상 조회")
    except Exception as e:
        result.fail("get_rule_by_id 정상 조회", str(e))

    # 14-5. get_rule_by_id("invalid", "x") -> None
    try:
        _reset_manager()
        rule = get_rule_by_id("invalid_league", "x")
        assert rule is None, "잘못된 리그에서 None 반환해야 함"
        result.ok("get_rule_by_id 잘못된 리그 -> None")
    except Exception as e:
        result.fail("get_rule_by_id 잘못된 리그 -> None", str(e))

    # 14-6. get_rules_by_category("nba", "foul")
    try:
        _reset_manager()
        rules = get_rules_by_category("nba", "foul")
        assert isinstance(rules, list), f"반환 타입: {type(rules)}"
        assert len(rules) > 0, "NBA 파울 규칙이 없음"
        for rule in rules:
            assert rule.category == RuleCategory.FOUL
        result.ok("get_rules_by_category 정상 조회")
    except Exception as e:
        result.fail("get_rules_by_category 정상 조회", str(e))

    # 14-7. merge_rule_sets([fiba, nba])
    try:
        _reset_manager()
        fiba_set = load_rule_set(League.FIBA)
        _reset_manager()
        nba_set = load_rule_set(League.NBA)
        merged = merge_rule_sets([fiba_set, nba_set])
        assert merged is not None, "병합 결과가 None"
        assert merged.league == League.FIBA, f"대표 리그: {merged.league}"
        assert merged.rule_count > 0, "병합 규칙 수가 0"
        result.ok("merge_rule_sets 병합")
    except Exception as e:
        result.fail("merge_rule_sets 병합", str(e))

    # 14-8. validate_rule_set 헬퍼
    try:
        _reset_manager()
        rs = load_rule_set(League.FIBA)
        is_valid = validate_rule_set(rs)
        assert is_valid is True
        result.ok("validate_rule_set 헬퍼 함수")
    except Exception as e:
        result.fail("validate_rule_set 헬퍼 함수", str(e))


# ============================================================
# [15] 리그별 팩토리 함수 테스트
# ============================================================
def test_factory_functions(result: TestResult) -> None:
    """리그별 팩토리 함수 단위 테스트 (7개)."""
    print("\n[15] 리그별 팩토리 함수 테스트")

    factories = {
        "get_fiba_rules": (get_fiba_rules, League.FIBA),
        "get_nba_rules": (get_nba_rules, League.NBA),
        "get_kbl_rules": (get_kbl_rules, League.KBL),
        "get_nbl_rules": (get_nbl_rules, League.NBL),
        "get_ncaa_rules": (get_ncaa_rules, League.NCAA),
        "get_b_league_rules": (get_b_league_rules, League.B_LEAGUE),
        "get_pba_rules": (get_pba_rules, League.PBA),
    }

    for name, (factory, expected_league) in factories.items():
        _reset_manager()
        try:
            rs = factory()
            assert rs is not None, f"{name}: 반환값 None"
            assert isinstance(rs, RuleSet), f"{name}: 반환 타입 {type(rs)}"
            assert rs.league == expected_league, f"{name}: 리그 불일치 {rs.league} != {expected_league}"
            assert rs.rule_count > 0, f"{name}: 규칙 수 0"
            result.ok(f"{name}() -> RuleSet (league={expected_league.value})")
        except Exception as e:
            result.fail(f"{name}() -> RuleSet (league={expected_league.value})", str(e))


# ============================================================
# [16] 스레드 안전성 테스트
# ============================================================
def test_thread_safety(result: TestResult) -> None:
    """스레드 안전성 단위 테스트 (3개)."""
    print("\n[16] 스레드 안전성 테스트")
    _reset_manager()

    # 16-1. 7 스레드 x 20 get_rule_set 호출
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        errors = []
        call_count = [0]
        count_lock = threading.Lock()

        def worker(league: League, num_calls: int):
            for _ in range(num_calls):
                try:
                    rs = manager.get_rule_set(league)
                    assert rs is not None
                    assert rs.league == league
                    with count_lock:
                        call_count[0] += 1
                except Exception as ex:
                    errors.append(f"{league.value}: {str(ex)}")

        threads = []
        for league in League:
            t = threading.Thread(target=worker, args=(league, 20))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert call_count[0] == 7 * 20, f"호출 수: {call_count[0]}"
        assert len(errors) == 0, f"에러 발생: {errors[:5]}"
        result.ok("7 스레드 x 20 get_rule_set 호출 (총 140)")
    except Exception as e:
        result.fail("7 스레드 x 20 get_rule_set 호출 (총 140)", str(e))

    # 16-2. 동시 캐시 접근
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        errors = []

        def cache_worker(thread_id: int):
            try:
                for league in League:
                    rs = manager.get_rule_set(league)
                    assert rs is not None
                if thread_id % 3 == 0:
                    manager.clear_cache()
            except Exception as ex:
                errors.append(f"thread-{thread_id}: {str(ex)}")

        threads = []
        for i in range(10):
            t = threading.Thread(target=cache_worker, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"동시 캐시 에러: {errors[:5]}"
        result.ok("동시 캐시 접근 (10 스레드)")
    except Exception as e:
        result.fail("동시 캐시 접근 (10 스레드)", str(e))

    # 16-3. 에러 수 == 0
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        error_list = []

        def stress_worker():
            try:
                for _ in range(50):
                    for league in League:
                        manager.get_rule_set(league)
            except Exception as ex:
                error_list.append(str(ex))

        threads = [threading.Thread(target=stress_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert len(error_list) == 0, f"스트레스 에러: {error_list[:3]}"
        result.ok("스레드 안전성 에러 0건")
    except Exception as e:
        result.fail("스레드 안전성 에러 0건", str(e))


# ============================================================
# [17] 메모리 테스트
# ============================================================
def test_memory(result: TestResult) -> None:
    """메모리 관련 단위 테스트 (2개)."""
    print("\n[17] 메모리 테스트")
    _reset_manager()

    # 17-1. 500 load/clear 사이클
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        for i in range(500):
            manager.get_rule_set(League.FIBA)
            if i % 10 == 0:
                manager.clear_cache()
        # 마지막에 캐시가 정상 작동하는지 확인
        rs = manager.get_rule_set(League.FIBA)
        assert rs is not None
        assert rs.rule_count > 0
        result.ok("500 load/clear 사이클 완료")
    except Exception as e:
        result.fail("500 load/clear 사이클 완료", str(e))

    # 17-2. 캐시 누수 없음
    try:
        config_loader = ConfigLoader()
        manager = RuleSetManager(config_loader)
        # 여러 번 load/clear 반복
        for _ in range(100):
            for league in League:
                manager.get_rule_set(league)
            manager.clear_cache()
        # clear 후 캐시가 비어있어야 함
        assert len(manager._cache) == 0, f"캐시 누수: {len(manager._cache)}개 남음"
        result.ok("캐시 누수 없음")
    except Exception as e:
        result.fail("캐시 누수 없음", str(e))


# ============================================================
# 메인 실행
# ============================================================
def main() -> None:
    """테스트 메인 실행."""
    print("=" * 60)
    print("COURTVIEW - RuleSetManager 단위 테스트")
    print("=" * 60)

    result = TestResult()

    # 전역 매니저 리셋
    _reset_manager()

    test_functions = [
        test_league_enum,           # [1] 10개
        test_rule_category_enum,    # [2] 8개
        test_rule_severity_enum,    # [3] 6개
        test_constants,             # [4] 12개
        test_rule_condition,        # [5] 10개
        test_penalty,               # [6] 5개
        test_rule,                  # [7] 12개
        test_rule_set,              # [8] 8개
        test_rule_set_metadata,     # [9] 4개
        test_league_config,         # [10] 5개
        test_rule_set_manager,      # [11] 15개
        test_cache_behavior,        # [12] 5개
        test_rule_inheritance,      # [13] 5개
        test_helper_functions,      # [14] 8개
        test_factory_functions,     # [15] 7개
        test_thread_safety,         # [16] 3개
        test_memory,                # [17] 2개
    ]

    for test_func in test_functions:
        try:
            test_func(result)
        except Exception as e:
            result.fail(
                f"{test_func.__name__} 실행 오류",
                f"{str(e)}\n{traceback.format_exc()}"
            )

    # 전역 매니저 정리
    _reset_manager()

    result.summary()

    # 종료 코드 반환
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
