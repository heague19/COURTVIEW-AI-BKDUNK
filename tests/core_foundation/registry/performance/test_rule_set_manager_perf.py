# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/registry/performance
파일: test_rule_set_manager_perf.py
설명: RuleSetManager 규칙 세트 로딩/캐싱 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12

테스트 범위:
    [P1] Enum 연산 성능 (3개)
         - League/RuleCategory/RuleSeverity 반복, 비교, 프로퍼티
    [P2] 데이터 클래스 생성 성능 (4개)
         - Rule, RuleCondition, Penalty, RuleSet, RuleSetMetadata 생성
    [P3] RuleCondition.evaluate 성능 (3개)
         - 단순 비교, 복합 조건, 배치 평가
    [P4] RuleSetManager 규칙 로드/조회 성능 (4개)
         - get_rule_set, get_rule, get_rules_by_category, FIBA 폴백
    [P5] 캐시 성능 (3개)
         - 캐시 히트 처리량, 캐시 미스 + 재로드, TTL 만료
    [P6] 팩토리 함수 성능 (3개)
         - get_fiba_rules, get_nba_rules, 전체 리그, LeagueConfig 생성
    [P7] 멀티스레드 동시 접근 (3개)
         - 동시 규칙 로딩, 규칙 조회, 혼합 연산
    [P8] 메모리 사용량 (3개)
         - 단일 매니저, 전체 리그 로드, Rule 배치

    총 26개 테스트
"""

import gc
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config import ConfigLoader
from core_foundation.registry.rule_set_manager import (
    # Enum
    League,
    RuleCategory,
    RuleSeverity,
    # 상수
    SUPPORTED_LEAGUES,
    DEFAULT_RULE_SET_PATH,
    RULE_SET_SCHEMA_VERSION,
    DEFAULT_CACHE_TTL,
    MAX_CACHE_SIZE,
    RULE_PRIORITY_WEIGHTS,
    LEAGUE_HIERARCHY,
    DEFAULT_FALLBACK_LEAGUE,
    # 데이터 클래스
    Rule,
    RuleSet,
    RuleCondition,
    Penalty,
    RuleSetMetadata,
    LeagueConfig,
    # Protocol
    RuleSetLoaderProtocol,
    # 메인 클래스
    RuleSetManager,
    # 헬퍼 함수
    load_rule_set,
    get_rule_by_id,
    get_rules_by_category,
    merge_rule_sets,
    validate_rule_set,
    # 팩토리 함수
    get_fiba_rules,
    get_nba_rules,
    get_kbl_rules,
    get_nbl_rules,
    get_ncaa_rules,
    get_b_league_rules,
    get_pba_rules,
    # 전역 함수
    _get_manager,
    _reset_manager,
)


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerformanceTestResult:
    """성능 테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.metrics = []

    def ok(self, test_name: str, metric: str = "") -> None:
        """테스트 통과."""
        self.passed += 1
        line = f"  [PASS] {test_name}"
        if metric:
            line += f"  |  {metric}"
            self.metrics.append(f"{test_name}: {metric}")
        print(line)

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패."""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.metrics:
            print(f"\n주요 성능 지표:")
            for m in self.metrics:
                print(f"  - {m}")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼 함수
# =============================================================================
def measure_ops(func, iterations: int = 10000) -> float:
    """초당 연산 수 측정."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return iterations / elapsed if elapsed > 0 else float("inf")


def get_object_size(obj) -> int:
    """객체 대략적 메모리 크기 (바이트) 측정."""
    return sys.getsizeof(obj)


def _make_manager(**kwargs) -> RuleSetManager:
    """테스트용 RuleSetManager 생성."""
    config_loader = ConfigLoader()
    return RuleSetManager(config_loader, **kwargs)


# =============================================================================
# [P1] Enum 연산 성능 (3개)
# =============================================================================
def test_p1_enum_performance(result: PerformanceTestResult) -> None:
    """League/RuleCategory/RuleSeverity Enum 연산 성능."""
    print("\n[P1] Enum 연산 성능")

    # P1-1. Enum 반복 (iteration) 처리량
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            for _ in League:
                pass
            for _ in RuleCategory:
                pass
            for _ in RuleSeverity:
                pass
        elapsed = time.perf_counter() - start
        total_enums = len(list(League)) + len(list(RuleCategory)) + len(list(RuleSeverity))
        ops = (iterations * total_enums) / elapsed
        per_call_us = (elapsed / (iterations * 3)) * 1_000_000
        result.ok(
            "P1-1 Enum 3종 반복 처리량",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/iteration",
        )
    except Exception as e:
        result.fail("P1-1 Enum 반복", str(e))

    # P1-2. Enum 비교 연산 처리량
    try:
        league_a = League.FIBA
        league_b = League.NBA
        cat_a = RuleCategory.FOUL
        cat_b = RuleCategory.VIOLATION
        sev_a = RuleSeverity.MINOR
        sev_b = RuleSeverity.SEVERE

        iterations = 500_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = league_a == league_b
            _ = league_a == League.FIBA
            _ = cat_a != cat_b
            _ = sev_a == sev_b
        elapsed = time.perf_counter() - start
        ops = (iterations * 4) / elapsed
        result.ok(
            "P1-2 Enum 비교 연산",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P1-2 Enum 비교", str(e))

    # P1-3. Enum 프로퍼티 접근 처리량
    try:
        all_leagues = list(League)
        all_categories = list(RuleCategory)
        all_severities = list(RuleSeverity)

        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            for lg in all_leagues:
                _ = lg.display_name
                _ = lg.country
            for cat in all_categories:
                _ = cat.display_name
            for sev in all_severities:
                _ = sev.penalty_weight
        elapsed = time.perf_counter() - start
        # 각 반복: 7 league * 2 + 8 category * 1 + 4 severity * 1 = 26 프로퍼티 접근
        total_accesses = iterations * (len(all_leagues) * 2 + len(all_categories) + len(all_severities))
        ops = total_accesses / elapsed
        result.ok(
            "P1-3 Enum 프로퍼티 접근",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P1-3 Enum 프로퍼티", str(e))


# =============================================================================
# [P2] 데이터 클래스 생성 성능 (4개)
# =============================================================================
def test_p2_dataclass_creation(result: PerformanceTestResult) -> None:
    """데이터 클래스 생성 성능."""
    print("\n[P2] 데이터 클래스 생성 성능")

    # P2-1. RuleCondition 생성 처리량
    try:
        ops = measure_ops(
            lambda: RuleCondition(
                condition_type="steps_without_dribble",
                threshold=3.0,
                comparison="gte",
            ),
            iterations=100_000,
        )
        per_call_us = (1.0 / ops) * 1_000_000 if ops > 0 else float("inf")
        result.ok(
            "P2-1 RuleCondition 생성",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P2-1 RuleCondition 생성", str(e))

    # P2-2. Penalty 생성 처리량
    try:
        ops = measure_ops(
            lambda: Penalty(
                penalty_type="turnover",
                description="공격권 상실",
                count=2,
                escalation={"limit": 5, "action": "disqualification"},
            ),
            iterations=100_000,
        )
        per_call_us = (1.0 / ops) * 1_000_000 if ops > 0 else float("inf")
        result.ok(
            "P2-2 Penalty 생성",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P2-2 Penalty 생성", str(e))

    # P2-3. Rule 생성 (전체 필드 포함)
    try:
        conditions = [
            RuleCondition(condition_type="steps", threshold=3.0, comparison="gte"),
        ]
        penalties = [
            Penalty(penalty_type="turnover", description="공격권 상실"),
        ]

        ops = measure_ops(
            lambda: Rule(
                rule_id="test_traveling",
                name="트래블링",
                category=RuleCategory.VIOLATION,
                severity=RuleSeverity.MINOR,
                description="드리블 없이 3보 이상 이동",
                conditions=conditions,
                penalties=penalties,
                league_specific={"shot_clock": 24},
                references=["FIBA Rule 25"],
            ),
            iterations=50_000,
        )
        per_call_us = (1.0 / ops) * 1_000_000 if ops > 0 else float("inf")
        result.ok(
            "P2-3 Rule 생성 (전체 필드)",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P2-3 Rule 생성", str(e))

    # P2-4. RuleSetMetadata + RuleSet 생성
    try:
        rules = [
            Rule(
                rule_id=f"test_rule_{i}",
                name=f"규칙_{i}",
                category=RuleCategory.VIOLATION,
                severity=RuleSeverity.MINOR,
                description=f"테스트 규칙 {i}",
            )
            for i in range(5)
        ]

        def create_ruleset():
            meta = RuleSetMetadata(
                content_hash="abc123def456",
                loaded_at=datetime.now(timezone.utc),
            )
            return RuleSet(
                league=League.FIBA,
                version=RULE_SET_SCHEMA_VERSION,
                rules=rules,
                metadata=meta,
            )

        ops = measure_ops(create_ruleset, iterations=30_000)
        per_call_us = (1.0 / ops) * 1_000_000 if ops > 0 else float("inf")
        result.ok(
            "P2-4 RuleSetMetadata + RuleSet 생성",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P2-4 RuleSet 생성", str(e))


# =============================================================================
# [P3] RuleCondition.evaluate 성능 (3개)
# =============================================================================
def test_p3_evaluate_performance(result: PerformanceTestResult) -> None:
    """RuleCondition.evaluate 성능."""
    print("\n[P3] RuleCondition.evaluate 성능")

    # P3-1. 단순 비교 (gte) 처리량
    try:
        cond = RuleCondition(
            condition_type="steps_without_dribble",
            threshold=3.0,
            comparison="gte",
        )
        ops = measure_ops(lambda: cond.evaluate(5.0), iterations=200_000)
        per_call_us = (1.0 / ops) * 1_000_000 if ops > 0 else float("inf")
        result.ok(
            "P3-1 evaluate 단순 비교 (gte)",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P3-1 evaluate 단순 비교", str(e))

    # P3-2. 다양한 비교 연산자 처리량
    try:
        conditions = [
            RuleCondition(condition_type="t", threshold=10.0, comparison="gt"),
            RuleCondition(condition_type="t", threshold=10.0, comparison="lt"),
            RuleCondition(condition_type="t", threshold=10.0, comparison="eq"),
            RuleCondition(condition_type="t", threshold=10.0, comparison="gte"),
            RuleCondition(condition_type="t", threshold=10.0, comparison="lte"),
        ]
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            for c in conditions:
                c.evaluate(8.5)
        elapsed = time.perf_counter() - start
        ops = (iterations * len(conditions)) / elapsed
        result.ok(
            "P3-2 evaluate 5개 연산자 순회",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P3-2 evaluate 다양한 연산자", str(e))

    # P3-3. 배치 평가 (Rule의 모든 조건 평가)
    try:
        rule = Rule(
            rule_id="batch_test",
            name="배치 테스트",
            category=RuleCategory.TIMING,
            severity=RuleSeverity.MINOR,
            description="배치 평가 테스트",
            conditions=[
                RuleCondition(condition_type="shot_clock", threshold=24.0, comparison="gte"),
                RuleCondition(condition_type="backcourt_time", threshold=8.0, comparison="gte"),
                RuleCondition(condition_type="paint_time", threshold=3.0, comparison="gte"),
            ],
        )

        def batch_evaluate():
            results = []
            for cond in rule.conditions:
                results.append(cond.evaluate(25.0))
            return all(results)

        ops = measure_ops(batch_evaluate, iterations=100_000)
        result.ok(
            "P3-3 배치 평가 (3 조건 Rule)",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P3-3 배치 평가", str(e))


# =============================================================================
# [P4] RuleSetManager 규칙 로드/조회 성능 (4개)
# =============================================================================
def test_p4_manager_load_query(result: PerformanceTestResult) -> None:
    """RuleSetManager 규칙 로드/조회 성능."""
    print("\n[P4] RuleSetManager 규칙 로드/조회 성능")

    # P4-1. get_rule_set 초기 로드 (7개 리그)
    try:
        times = []
        for league in League:
            manager = _make_manager()
            start = time.perf_counter()
            rs = manager.get_rule_set(league)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
            manager.shutdown()

        avg_ms = sum(times) / len(times)
        max_ms = max(times)
        result.ok(
            "P4-1 get_rule_set 초기 로드 (7리그 평균)",
            f"평균 {avg_ms:.2f}ms, 최대 {max_ms:.2f}ms",
        )
    except Exception as e:
        result.fail("P4-1 get_rule_set 초기 로드", str(e))

    # P4-2. get_rule 개별 규칙 조회 처리량 (캐시 활성)
    try:
        manager = _make_manager()
        # 캐시 사전 로드
        manager.get_rule_set(League.FIBA)

        ops = measure_ops(
            lambda: manager.get_rule(League.FIBA, "fiba_traveling"),
            iterations=10_000,
        )
        manager.shutdown()
        result.ok(
            "P4-2 get_rule 조회 (캐시 히트)",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P4-2 get_rule 조회", str(e))

    # P4-3. get_rules_by_category 카테고리별 조회 처리량
    try:
        manager = _make_manager()
        # 캐시 사전 로드
        manager.get_rule_set(League.FIBA)

        categories = list(RuleCategory)

        def query_by_category():
            for cat in categories:
                manager.get_rules_by_category(League.FIBA, cat)

        ops = measure_ops(query_by_category, iterations=5_000)
        total_ops = ops * len(categories)
        manager.shutdown()
        result.ok(
            "P4-3 get_rules_by_category (전 카테고리)",
            f"{total_ops:,.0f} ops/sec (카테고리당)",
        )
    except Exception as e:
        result.fail("P4-3 get_rules_by_category", str(e))

    # P4-4. FIBA 폴백 조회 처리량
    try:
        manager = _make_manager()
        # NBA와 FIBA 모두 캐시에 로드
        manager.get_rule_set(League.NBA)
        manager.get_rule_set(League.FIBA)

        # NBA에 없는 규칙을 FIBA 폴백으로 조회
        ops = measure_ops(
            lambda: manager.get_rule(League.NBA, "nba_nonexistent_rule", fallback=True),
            iterations=5_000,
        )
        manager.shutdown()
        result.ok(
            "P4-4 FIBA 폴백 조회",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P4-4 FIBA 폴백 조회", str(e))


# =============================================================================
# [P5] 캐시 성능 (3개)
# =============================================================================
def test_p5_cache_performance(result: PerformanceTestResult) -> None:
    """캐시 성능."""
    print("\n[P5] 캐시 성능")

    # P5-1. 캐시 히트 처리량
    try:
        manager = _make_manager()
        # 캐시 사전 로드
        manager.get_rule_set(League.FIBA)

        # 캐시 히트: 동일 규칙 세트를 반복 조회
        ops = measure_ops(
            lambda: manager.get_rule_set(League.FIBA),
            iterations=50_000,
        )
        per_call_us = (1.0 / ops) * 1_000_000 if ops > 0 else float("inf")
        manager.shutdown()
        result.ok(
            "P5-1 캐시 히트 처리량",
            f"{ops:,.0f} ops/sec, {per_call_us:.2f}us/call",
        )
    except Exception as e:
        result.fail("P5-1 캐시 히트", str(e))

    # P5-2. 캐시 미스 + 재로드 성능
    try:
        manager = _make_manager()
        iterations = 200
        times = []

        for _ in range(iterations):
            manager.clear_cache(League.FIBA)
            start = time.perf_counter()
            manager.get_rule_set(League.FIBA)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)

        avg_ms = sum(times) / len(times)
        manager.shutdown()
        result.ok(
            "P5-2 캐시 미스 + 재로드 (200회 평균)",
            f"{avg_ms:.3f}ms/call",
        )
    except Exception as e:
        result.fail("P5-2 캐시 미스", str(e))

    # P5-3. TTL 만료 후 재로드 성능
    try:
        # TTL 1초로 설정
        manager = _make_manager(cache_ttl=1)

        # 초기 로드
        manager.get_rule_set(League.FIBA)

        # TTL 만료 대기
        time.sleep(1.2)

        # 만료 후 재로드 시간 측정
        times = []
        for _ in range(10):
            start = time.perf_counter()
            manager.get_rule_set(League.FIBA)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
            time.sleep(1.2)  # 다시 만료 대기

        avg_ms = sum(times) / len(times)
        manager.shutdown()
        result.ok(
            "P5-3 TTL 만료 후 재로드 (10회 평균)",
            f"{avg_ms:.3f}ms/call",
        )
    except Exception as e:
        result.fail("P5-3 TTL 만료", str(e))


# =============================================================================
# [P6] 팩토리 함수 성능 (3개)
# =============================================================================
def test_p6_factory_performance(result: PerformanceTestResult) -> None:
    """팩토리 함수 성능."""
    print("\n[P6] 팩토리 함수 성능")

    # P6-1. get_fiba_rules / get_nba_rules 처리량
    try:
        _reset_manager()

        # 최초 로드 시간 측정 (get_fiba_rules)
        start = time.perf_counter()
        fiba = get_fiba_rules()
        fiba_load_ms = (time.perf_counter() - start) * 1000

        # 캐시 히트 상태에서 처리량 측정
        ops_fiba = measure_ops(lambda: get_fiba_rules(), iterations=10_000)

        _reset_manager()

        start = time.perf_counter()
        nba = get_nba_rules()
        nba_load_ms = (time.perf_counter() - start) * 1000

        ops_nba = measure_ops(lambda: get_nba_rules(), iterations=10_000)

        _reset_manager()
        result.ok(
            "P6-1 get_fiba_rules / get_nba_rules",
            f"FIBA 초기: {fiba_load_ms:.2f}ms, 캐시: {ops_fiba:,.0f} ops/sec | "
            f"NBA 초기: {nba_load_ms:.2f}ms, 캐시: {ops_nba:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P6-1 팩토리 함수", str(e))
        _reset_manager()

    # P6-2. 전체 7개 리그 팩토리 순차 로드 시간
    try:
        _reset_manager()
        factory_funcs = [
            ("FIBA", get_fiba_rules),
            ("NBA", get_nba_rules),
            ("KBL", get_kbl_rules),
            ("NBL", get_nbl_rules),
            ("NCAA", get_ncaa_rules),
            ("B.League", get_b_league_rules),
            ("PBA", get_pba_rules),
        ]

        start = time.perf_counter()
        for name, func in factory_funcs:
            func()
        total_ms = (time.perf_counter() - start) * 1000

        _reset_manager()
        result.ok(
            "P6-2 전체 7개 리그 순차 로드",
            f"총 {total_ms:.2f}ms, 평균 {total_ms / 7:.2f}ms/리그",
        )
    except Exception as e:
        result.fail("P6-2 전체 리그 로드", str(e))
        _reset_manager()

    # P6-3. LeagueConfig.for_league 생성 처리량
    try:
        all_leagues = list(League)

        def create_all_configs():
            for lg in all_leagues:
                LeagueConfig.for_league(lg)

        ops = measure_ops(create_all_configs, iterations=20_000)
        total_ops = ops * len(all_leagues)
        result.ok(
            "P6-3 LeagueConfig.for_league (7리그)",
            f"{total_ops:,.0f} ops/sec (리그당)",
        )
    except Exception as e:
        result.fail("P6-3 LeagueConfig 생성", str(e))


# =============================================================================
# [P7] 멀티스레드 동시 접근 (3개)
# =============================================================================
def test_p7_multithread_performance(result: PerformanceTestResult) -> None:
    """멀티스레드 동시 접근 성능."""
    print("\n[P7] 멀티스레드 동시 접근")

    # P7-1. 동시 규칙 세트 로딩 (4스레드 x 7리그)
    try:
        manager = _make_manager()
        errors = []
        n_threads = 4
        n_ops_per_thread = 50
        barrier = threading.Barrier(n_threads)
        thread_times = []

        def load_worker(tid):
            try:
                barrier.wait(timeout=5)
                leagues = list(League)
                start = time.perf_counter()
                for i in range(n_ops_per_thread):
                    league = leagues[i % len(leagues)]
                    manager.get_rule_set(league)
                elapsed = time.perf_counter() - start
                thread_times.append(elapsed)
            except Exception as ex:
                errors.append(f"thread_{tid}: {ex}")

        threads = [threading.Thread(target=load_worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"에러 발생: {errors}"
        total_ops = n_threads * n_ops_per_thread
        max_elapsed = max(thread_times) if thread_times else 1
        ops = total_ops / max_elapsed
        manager.shutdown()
        result.ok(
            f"P7-1 동시 규칙 로딩 ({n_threads}스레드 x {n_ops_per_thread}회)",
            f"{ops:,.0f} ops/sec, 에러: 0",
        )
    except Exception as e:
        result.fail("P7-1 동시 규칙 로딩", str(e))

    # P7-2. 동시 규칙 조회 (4스레드)
    try:
        manager = _make_manager()
        # 모든 리그 사전 로드
        for league in League:
            manager.get_rule_set(league)

        errors = []
        n_threads = 4
        n_ops_per_thread = 500
        barrier = threading.Barrier(n_threads)
        thread_times = []

        rule_ids_per_league = {
            League.FIBA: "fiba_traveling",
            League.NBA: "nba_traveling",
            League.KBL: "kbl_personal_foul",
            League.NBL: "nbl_three_point",
        }
        query_leagues = list(rule_ids_per_league.keys())

        def query_worker(tid):
            try:
                barrier.wait(timeout=5)
                start = time.perf_counter()
                for i in range(n_ops_per_thread):
                    lg = query_leagues[i % len(query_leagues)]
                    rid = rule_ids_per_league[lg]
                    manager.get_rule(lg, rid)
                elapsed = time.perf_counter() - start
                thread_times.append(elapsed)
            except Exception as ex:
                errors.append(f"thread_{tid}: {ex}")

        threads = [threading.Thread(target=query_worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"에러 발생: {errors}"
        total_ops = n_threads * n_ops_per_thread
        max_elapsed = max(thread_times) if thread_times else 1
        ops = total_ops / max_elapsed
        manager.shutdown()
        result.ok(
            f"P7-2 동시 규칙 조회 ({n_threads}스레드 x {n_ops_per_thread}회)",
            f"{ops:,.0f} ops/sec, 에러: 0",
        )
    except Exception as e:
        result.fail("P7-2 동시 규칙 조회", str(e))

    # P7-3. 혼합 연산 (로드 + 조회 + 카테고리 조회 + clear)
    try:
        manager = _make_manager()
        errors = []
        n_threads = 4
        n_ops_per_thread = 100
        barrier = threading.Barrier(n_threads)
        thread_times = []

        def mixed_worker(tid):
            try:
                barrier.wait(timeout=5)
                leagues = list(League)
                cats = list(RuleCategory)
                start = time.perf_counter()
                for i in range(n_ops_per_thread):
                    lg = leagues[i % len(leagues)]
                    cat = cats[i % len(cats)]
                    op = i % 4
                    if op == 0:
                        manager.get_rule_set(lg)
                    elif op == 1:
                        manager.get_rule(lg, f"{lg.value}_traveling")
                    elif op == 2:
                        manager.get_rules_by_category(lg, cat)
                    else:
                        manager.get_league_config(lg)
                elapsed = time.perf_counter() - start
                thread_times.append(elapsed)
            except Exception as ex:
                errors.append(f"thread_{tid}: {ex}")

        threads = [threading.Thread(target=mixed_worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"에러 발생: {errors}"
        total_ops = n_threads * n_ops_per_thread
        max_elapsed = max(thread_times) if thread_times else 1
        ops = total_ops / max_elapsed
        manager.shutdown()
        result.ok(
            f"P7-3 혼합 연산 ({n_threads}스레드 x {n_ops_per_thread}회)",
            f"{ops:,.0f} ops/sec, 에러: 0",
        )
    except Exception as e:
        result.fail("P7-3 혼합 연산", str(e))


# =============================================================================
# [P8] 메모리 사용량 (3개)
# =============================================================================
def test_p8_memory_usage(result: PerformanceTestResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[P8] 메모리 사용량")

    # P8-1. 단일 RuleSetManager 인스턴스 메모리
    try:
        gc.collect()
        manager = _make_manager()
        manager_size = get_object_size(manager)

        # 내부 _builtin_rules 딕셔너리 크기
        builtin_size = get_object_size(manager._builtin_rules)

        # 캐시 딕셔너리 크기
        cache_size = get_object_size(manager._cache)

        total_base = manager_size + builtin_size + cache_size
        manager.shutdown()
        result.ok(
            "P8-1 RuleSetManager 인스턴스 메모리",
            f"manager: {manager_size}B, builtin_rules: {builtin_size}B, "
            f"cache: {cache_size}B, 합계: ~{total_base}B",
        )
    except Exception as e:
        result.fail("P8-1 매니저 메모리", str(e))

    # P8-2. 전체 7개 리그 로드 후 메모리
    try:
        gc.collect()
        manager = _make_manager()

        # 모든 리그 로드
        rule_counts = {}
        for league in League:
            rs = manager.get_rule_set(league)
            rule_counts[league.value] = rs.rule_count

        # 캐시된 RuleSet 크기 측정
        total_rules = sum(rule_counts.values())
        cache_keys = len(manager._cache)

        # 개별 Rule 크기 샘플링
        sample_set = manager.get_rule_set(League.FIBA)
        if sample_set.rules:
            sample_rule_size = get_object_size(sample_set.rules[0])
        else:
            sample_rule_size = 0

        estimated_total_kb = (sample_rule_size * total_rules) / 1024

        manager.shutdown()
        result.ok(
            "P8-2 전체 리그 로드 후 메모리",
            f"총 규칙: {total_rules}개, 캐시 키: {cache_keys}개, "
            f"Rule 개당: ~{sample_rule_size}B, 추정 총합: ~{estimated_total_kb:.1f}KB",
        )
    except Exception as e:
        result.fail("P8-2 전체 리그 메모리", str(e))

    # P8-3. Rule 대량 생성 메모리 효율
    try:
        gc.collect()
        rules = []
        for i in range(1000):
            rule = Rule(
                rule_id=f"perf_rule_{i}",
                name=f"성능 테스트 규칙 {i}",
                category=RuleCategory.VIOLATION,
                severity=RuleSeverity.MINOR,
                description=f"성능 테스트용 규칙 설명 {i}",
                conditions=[
                    RuleCondition(
                        condition_type="test",
                        threshold=float(i),
                        comparison="gte",
                    ),
                ],
                penalties=[
                    Penalty(
                        penalty_type="turnover",
                        description="공격권 상실",
                    ),
                ],
            )
            rules.append(rule)

        sample_size = get_object_size(rules[0])
        list_size = get_object_size(rules)
        estimated_total_kb = (sample_size * 1000 + list_size) / 1024
        result.ok(
            "P8-3 Rule 1000개 배치 메모리",
            f"Rule 개당: ~{sample_size}B, 리스트: ~{list_size}B, "
            f"추정 총합: ~{estimated_total_kb:.1f}KB",
        )
    except Exception as e:
        result.fail("P8-3 Rule 배치 메모리", str(e))


# =============================================================================
# [추가] Rule/RuleSet 유틸리티 메서드 성능 (2개)
# =============================================================================
def test_p_extra_utility_performance(result: PerformanceTestResult) -> None:
    """Rule/RuleSet 유틸리티 메서드 성능."""
    print("\n[추가] Rule/RuleSet 유틸리티 메서드 성능")

    # E-1. Rule.to_dict 처리량
    try:
        rule = Rule(
            rule_id="fiba_traveling",
            name="트래블링",
            category=RuleCategory.VIOLATION,
            severity=RuleSeverity.MINOR,
            description="드리블 없이 3보 이상 이동",
            conditions=[
                RuleCondition(condition_type="steps", threshold=3.0, comparison="gte"),
            ],
            penalties=[
                Penalty(penalty_type="turnover", description="공격권 상실"),
            ],
            references=["FIBA Rule 25"],
        )
        ops = measure_ops(lambda: rule.to_dict(), iterations=50_000)
        result.ok(
            "E-1 Rule.to_dict 처리량",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("E-1 Rule.to_dict", str(e))

    # E-2. Rule.get_priority / Rule.is_active 처리량
    try:
        rule = Rule(
            rule_id="test_priority",
            name="우선순위 테스트",
            category=RuleCategory.FOUL,
            severity=RuleSeverity.SEVERE,
            description="우선순위 테스트",
        )

        def priority_and_active():
            rule.get_priority()
            rule.is_active()

        ops = measure_ops(priority_and_active, iterations=100_000)
        result.ok(
            "E-2 Rule.get_priority + is_active",
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("E-2 get_priority/is_active", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 성능 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW - rule_set_manager.py 성능 테스트")
    print("=" * 60)

    result = PerformanceTestResult()

    # [P1] Enum 연산 성능
    test_p1_enum_performance(result)

    # [P2] 데이터 클래스 생성 성능
    test_p2_dataclass_creation(result)

    # [P3] RuleCondition.evaluate 성능
    test_p3_evaluate_performance(result)

    # [P4] RuleSetManager 규칙 로드/조회 성능
    test_p4_manager_load_query(result)

    # [P5] 캐시 성능
    test_p5_cache_performance(result)

    # [P6] 팩토리 함수 성능
    test_p6_factory_performance(result)

    # [P7] 멀티스레드 동시 접근
    test_p7_multithread_performance(result)

    # [P8] 메모리 사용량
    test_p8_memory_usage(result)

    # [추가] 유틸리티 메서드 성능
    test_p_extra_utility_performance(result)

    # 전역 매니저 정리
    _reset_manager()

    # 요약 출력
    result.summary()

    # 종료 코드
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
