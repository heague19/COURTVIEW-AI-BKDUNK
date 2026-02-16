# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/resilience/unit
파일: test_retry_mechanism.py
설명: 재시도 메커니즘 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-16

테스트 범위:
    [1]  상수 검증 (6개)
    [2]  BackoffStrategy Enum (5개)
    [3]  RetryOutcome Enum (5개)
    [4]  RetryConfig 데이터 클래스 (10개)
    [5]  RetryAttempt / RetryResult 데이터 클래스 (8개)
    [6]  calculate_backoff 함수 (10개)
    [7]  _is_retryable 함수 (6개)
    [8]  RetryMechanism 초기화 (5개)
    [9]  RetryMechanism.execute 동기 실행 (10개)
    [10] RetryMechanism.execute_with_result (6개)
    [11] RetryMechanism 비동기 실행 (6개)
    [12] 콜백 (on_retry, on_success, on_failure) (8개)
    [13] 데코레이터 retry / async_retry (8개)
    [14] 헬퍼 함수 (create/get/register) (6개)
    [15] 레지스트리 (_RetryRegistry) (6개)
    [16] __all__ 내보내기 검증 (4개)
    [17] 엣지 케이스 (6개)
"""

import asyncio
import io
import random
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.resilience.retry_mechanism import (
    # Enum
    BackoffStrategy,
    RetryOutcome,
    # 상수
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_INITIAL_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_EXPONENTIAL_BASE,
    DEFAULT_JITTER_FACTOR,
    DEFAULT_TIMEOUT,
    MIN_DELAY,
    MAX_DELAY_CAP,
    MIN_JITTER_FACTOR,
    MAX_JITTER_FACTOR,
    # 데이터 클래스
    RetryConfig,
    RetryAttempt,
    RetryResult,
    # 메인 클래스
    RetryMechanism,
    # 데코레이터
    retry,
    async_retry,
    # 함수
    calculate_backoff,
    create_retry_mechanism,
    get_retry_mechanism,
    register_retry_mechanism,
    # 내부 함수
    _is_retryable,
    _calculate_backoff_from_config,
    # 유틸리티 (테스트용)
    _reset_registry,
)

from shared.exceptions.base_exception import RetryableException
from shared.exceptions.infrastructure_exceptions import TimeoutException


# =============================================================================
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    """테스트 결과 저장."""

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


# =============================================================================
# [1] 상수 검증
# =============================================================================
def test_constants(result: TestResult) -> None:
    """상수 값 검증."""
    print("\n[1] 상수 검증")

    # 1-1
    try:
        assert DEFAULT_MAX_ATTEMPTS == 3
        result.ok("1-1: DEFAULT_MAX_ATTEMPTS = 3")
    except Exception as e:
        result.fail("1-1: DEFAULT_MAX_ATTEMPTS", str(e))

    # 1-2
    try:
        assert DEFAULT_INITIAL_DELAY == 1.0
        result.ok("1-2: DEFAULT_INITIAL_DELAY = 1.0")
    except Exception as e:
        result.fail("1-2: DEFAULT_INITIAL_DELAY", str(e))

    # 1-3
    try:
        assert DEFAULT_MAX_DELAY == 30.0
        result.ok("1-3: DEFAULT_MAX_DELAY = 30.0")
    except Exception as e:
        result.fail("1-3: DEFAULT_MAX_DELAY", str(e))

    # 1-4
    try:
        assert DEFAULT_EXPONENTIAL_BASE == 2.0
        result.ok("1-4: DEFAULT_EXPONENTIAL_BASE = 2.0")
    except Exception as e:
        result.fail("1-4: DEFAULT_EXPONENTIAL_BASE", str(e))

    # 1-5
    try:
        assert DEFAULT_JITTER_FACTOR == 0.1
        result.ok("1-5: DEFAULT_JITTER_FACTOR = 0.1")
    except Exception as e:
        result.fail("1-5: DEFAULT_JITTER_FACTOR", str(e))

    # 1-6
    try:
        assert MIN_DELAY == 0.001
        assert MAX_DELAY_CAP == 300.0
        assert MIN_JITTER_FACTOR == 0.0
        assert MAX_JITTER_FACTOR == 1.0
        assert DEFAULT_TIMEOUT == 60.0
        result.ok("1-6: MIN/MAX 제한 상수")
    except Exception as e:
        result.fail("1-6: 제한 상수", str(e))


# =============================================================================
# [2] BackoffStrategy Enum
# =============================================================================
def test_backoff_strategy_enum(result: TestResult) -> None:
    """BackoffStrategy Enum 테스트."""
    print("\n[2] BackoffStrategy Enum")

    # 2-1
    try:
        assert len(BackoffStrategy) == 4
        result.ok("2-1: BackoffStrategy 멤버 수 = 4")
    except Exception as e:
        result.fail("2-1: 멤버 수", str(e))

    # 2-2
    try:
        members = {s.name for s in BackoffStrategy}
        assert "CONSTANT" in members
        assert "LINEAR" in members
        assert "EXPONENTIAL" in members
        assert "DECORRELATED_JITTER" in members
        result.ok("2-2: 전략 멤버 이름")
    except Exception as e:
        result.fail("2-2: 멤버 이름", str(e))

    # 2-3
    try:
        assert BackoffStrategy.CONSTANT.korean_label == "고정"
        assert BackoffStrategy.LINEAR.korean_label == "선형"
        assert BackoffStrategy.EXPONENTIAL.korean_label == "지수"
        assert BackoffStrategy.DECORRELATED_JITTER.korean_label == "디코릴레이티드 지터"
        result.ok("2-3: korean_label 속성")
    except Exception as e:
        result.fail("2-3: korean_label", str(e))

    # 2-4
    try:
        assert BackoffStrategy["EXPONENTIAL"] == BackoffStrategy.EXPONENTIAL
        result.ok("2-4: 이름으로 접근")
    except Exception as e:
        result.fail("2-4: 이름 접근", str(e))

    # 2-5
    try:
        from enum import auto
        # auto() 값은 정수
        assert isinstance(BackoffStrategy.CONSTANT.value, int)
        result.ok("2-5: auto() 정수 값")
    except Exception as e:
        result.fail("2-5: auto() 값", str(e))


# =============================================================================
# [3] RetryOutcome Enum
# =============================================================================
def test_retry_outcome_enum(result: TestResult) -> None:
    """RetryOutcome Enum 테스트."""
    print("\n[3] RetryOutcome Enum")

    # 3-1
    try:
        assert len(RetryOutcome) == 5
        result.ok("3-1: RetryOutcome 멤버 수 = 5")
    except Exception as e:
        result.fail("3-1: 멤버 수", str(e))

    # 3-2
    try:
        members = {o.name for o in RetryOutcome}
        expected = {"SUCCESS", "EXHAUSTED", "NON_RETRYABLE", "TIMEOUT", "CANCELLED"}
        assert members == expected
        result.ok("3-2: 전체 멤버")
    except Exception as e:
        result.fail("3-2: 멤버", str(e))

    # 3-3
    try:
        assert RetryOutcome["SUCCESS"] == RetryOutcome.SUCCESS
        result.ok("3-3: 이름으로 접근")
    except Exception as e:
        result.fail("3-3: 이름 접근", str(e))

    # 3-4
    try:
        assert isinstance(RetryOutcome.SUCCESS.value, int)
        result.ok("3-4: auto() 정수 값")
    except Exception as e:
        result.fail("3-4: auto() 값", str(e))

    # 3-5
    try:
        # 각 멤버는 고유한 값
        values = [o.value for o in RetryOutcome]
        assert len(values) == len(set(values))
        result.ok("3-5: 고유한 값")
    except Exception as e:
        result.fail("3-5: 고유 값", str(e))


# =============================================================================
# [4] RetryConfig 데이터 클래스
# =============================================================================
def test_retry_config(result: TestResult) -> None:
    """RetryConfig 테스트."""
    print("\n[4] RetryConfig 데이터 클래스")

    # 4-1: 기본값
    try:
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert config.initial_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter_enabled is True
        assert config.jitter_factor == 0.1
        assert config.timeout is None
        assert config.log_retries is True
        result.ok("4-1: 기본값 검증")
    except Exception as e:
        result.fail("4-1: 기본값", str(e))

    # 4-2: 커스텀 값
    try:
        config = RetryConfig(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.LINEAR,
            initial_delay=0.5,
            max_delay=10.0,
            jitter_enabled=False,
        )
        assert config.max_attempts == 5
        assert config.backoff_strategy == BackoffStrategy.LINEAR
        assert config.jitter_enabled is False
        result.ok("4-2: 커스텀 값")
    except Exception as e:
        result.fail("4-2: 커스텀 값", str(e))

    # 4-3: max_attempts < 1 → ValueError
    try:
        raised = False
        try:
            RetryConfig(max_attempts=0)
        except ValueError:
            raised = True
        assert raised
        result.ok("4-3: max_attempts < 1 → ValueError")
    except Exception as e:
        result.fail("4-3: max_attempts 검증", str(e))

    # 4-4: initial_delay < MIN_DELAY → ValueError
    try:
        raised = False
        try:
            RetryConfig(initial_delay=0.0)
        except ValueError:
            raised = True
        assert raised
        result.ok("4-4: initial_delay < MIN_DELAY → ValueError")
    except Exception as e:
        result.fail("4-4: initial_delay 검증", str(e))

    # 4-5: max_delay < initial_delay → ValueError
    try:
        raised = False
        try:
            RetryConfig(initial_delay=5.0, max_delay=1.0)
        except ValueError:
            raised = True
        assert raised
        result.ok("4-5: max_delay < initial_delay → ValueError")
    except Exception as e:
        result.fail("4-5: max_delay 검증", str(e))

    # 4-6: exponential_base < 1.0 → ValueError
    try:
        raised = False
        try:
            RetryConfig(exponential_base=0.5)
        except ValueError:
            raised = True
        assert raised
        result.ok("4-6: exponential_base < 1.0 → ValueError")
    except Exception as e:
        result.fail("4-6: exponential_base 검증", str(e))

    # 4-7: jitter_factor 범위 초과 → ValueError
    try:
        raised = False
        try:
            RetryConfig(jitter_factor=1.5)
        except ValueError:
            raised = True
        assert raised
        result.ok("4-7: jitter_factor > 1.0 → ValueError")
    except Exception as e:
        result.fail("4-7: jitter_factor 검증", str(e))

    # 4-8: max_delay > MAX_DELAY_CAP → 자동 제한
    try:
        config = RetryConfig(max_delay=500.0)
        assert config.max_delay == MAX_DELAY_CAP
        result.ok("4-8: max_delay > 300 → 자동 제한")
    except Exception as e:
        result.fail("4-8: max_delay 제한", str(e))

    # 4-9: to_dict
    try:
        config = RetryConfig()
        d = config.to_dict()
        assert isinstance(d, dict)
        assert d["max_attempts"] == 3
        assert d["backoff_strategy"] == "EXPONENTIAL"
        assert "initial_delay" in d
        assert "jitter_enabled" in d
        result.ok("4-9: to_dict 변환")
    except Exception as e:
        result.fail("4-9: to_dict", str(e))

    # 4-10: retryable_exceptions 기본값
    try:
        config = RetryConfig()
        assert RetryableException in config.retryable_exceptions
        assert ConnectionError in config.retryable_exceptions
        assert TimeoutError in config.retryable_exceptions
        result.ok("4-10: retryable_exceptions 기본값")
    except Exception as e:
        result.fail("4-10: retryable_exceptions", str(e))


# =============================================================================
# [5] RetryAttempt / RetryResult 데이터 클래스
# =============================================================================
def test_retry_attempt_and_result(result: TestResult) -> None:
    """RetryAttempt / RetryResult 테스트."""
    print("\n[5] RetryAttempt / RetryResult 데이터 클래스")

    # 5-1: RetryAttempt 생성
    try:
        now = datetime.now(timezone.utc)
        attempt = RetryAttempt(
            attempt_number=1,
            start_time=now,
            duration_ms=50.0,
            success=True,
        )
        assert attempt.attempt_number == 1
        assert attempt.success is True
        assert attempt.duration_ms == 50.0
        assert attempt.delay_before == 0.0
        result.ok("5-1: RetryAttempt 생성")
    except Exception as e:
        result.fail("5-1: RetryAttempt", str(e))

    # 5-2: RetryAttempt to_dict
    try:
        now = datetime.now(timezone.utc)
        attempt = RetryAttempt(
            attempt_number=2,
            start_time=now,
            end_time=now,
            duration_ms=100.0,
            success=False,
            exception=ConnectionError("conn_err"),
            delay_before=1.5,
        )
        d = attempt.to_dict()
        assert d["attempt_number"] == 2
        assert d["success"] is False
        assert d["exception_type"] == "ConnectionError"
        assert d["exception_message"] == "conn_err"
        assert d["delay_before"] == 1.5
        result.ok("5-2: RetryAttempt to_dict")
    except Exception as e:
        result.fail("5-2: to_dict", str(e))

    # 5-3: RetryAttempt exception=None
    try:
        now = datetime.now(timezone.utc)
        attempt = RetryAttempt(attempt_number=1, start_time=now, success=True)
        d = attempt.to_dict()
        assert d["exception_type"] is None
        assert d["exception_message"] is None
        result.ok("5-3: exception=None → None")
    except Exception as e:
        result.fail("5-3: exception None", str(e))

    # 5-4: RetryResult 성공
    try:
        rr = RetryResult(
            outcome=RetryOutcome.SUCCESS,
            success=True,
            value=42,
            total_attempts=1,
        )
        assert rr.success is True
        assert rr.value == 42
        assert rr.outcome == RetryOutcome.SUCCESS
        result.ok("5-4: RetryResult 성공")
    except Exception as e:
        result.fail("5-4: RetryResult 성공", str(e))

    # 5-5: RetryResult 실패
    try:
        exc = ConnectionError("failed")
        rr = RetryResult(
            outcome=RetryOutcome.EXHAUSTED,
            success=False,
            final_exception=exc,
            total_attempts=3,
        )
        assert rr.success is False
        assert rr.final_exception is exc
        assert rr.outcome == RetryOutcome.EXHAUSTED
        result.ok("5-5: RetryResult 실패")
    except Exception as e:
        result.fail("5-5: RetryResult 실패", str(e))

    # 5-6: RetryResult to_dict
    try:
        rr = RetryResult(
            outcome=RetryOutcome.SUCCESS,
            success=True,
            value="ok",
            total_attempts=2,
            total_duration_ms=150.0,
            total_delay_ms=50.0,
        )
        d = rr.to_dict()
        assert d["outcome"] == "SUCCESS"
        assert d["success"] is True
        assert d["total_attempts"] == 2
        assert d["total_duration_ms"] == 150.0
        assert d["total_delay_ms"] == 50.0
        result.ok("5-6: RetryResult to_dict")
    except Exception as e:
        result.fail("5-6: to_dict", str(e))

    # 5-7: RetryResult.attempts 리스트
    try:
        now = datetime.now(timezone.utc)
        rr = RetryResult(outcome=RetryOutcome.SUCCESS, success=True)
        rr.attempts.append(RetryAttempt(attempt_number=1, start_time=now))
        rr.attempts.append(RetryAttempt(attempt_number=2, start_time=now))
        d = rr.to_dict()
        assert len(d["attempts"]) == 2
        result.ok("5-7: attempts 리스트")
    except Exception as e:
        result.fail("5-7: attempts", str(e))

    # 5-8: RetryResult final_exception=None
    try:
        rr = RetryResult(outcome=RetryOutcome.SUCCESS, success=True)
        d = rr.to_dict()
        assert d["final_exception_type"] is None
        assert d["final_exception_message"] is None
        result.ok("5-8: final_exception=None")
    except Exception as e:
        result.fail("5-8: final_exception None", str(e))


# =============================================================================
# [6] calculate_backoff 함수
# =============================================================================
def test_calculate_backoff(result: TestResult) -> None:
    """calculate_backoff 함수 테스트."""
    print("\n[6] calculate_backoff 함수")

    # 6-1: CONSTANT 전략
    try:
        d1 = calculate_backoff(1, BackoffStrategy.CONSTANT, 1.0, 30.0, jitter_enabled=False)
        d2 = calculate_backoff(5, BackoffStrategy.CONSTANT, 1.0, 30.0, jitter_enabled=False)
        assert d1 == 1.0
        assert d2 == 1.0
        result.ok("6-1: CONSTANT 전략 (고정)")
    except Exception as e:
        result.fail("6-1: CONSTANT", str(e))

    # 6-2: LINEAR 전략
    try:
        d1 = calculate_backoff(1, BackoffStrategy.LINEAR, 1.0, 30.0, jitter_enabled=False)
        d3 = calculate_backoff(3, BackoffStrategy.LINEAR, 1.0, 30.0, jitter_enabled=False)
        assert d1 == 1.0
        assert d3 == 3.0
        result.ok("6-2: LINEAR 전략 (선형)")
    except Exception as e:
        result.fail("6-2: LINEAR", str(e))

    # 6-3: EXPONENTIAL 전략
    try:
        d1 = calculate_backoff(1, BackoffStrategy.EXPONENTIAL, 1.0, 30.0, 2.0, jitter_enabled=False)
        d2 = calculate_backoff(2, BackoffStrategy.EXPONENTIAL, 1.0, 30.0, 2.0, jitter_enabled=False)
        d3 = calculate_backoff(3, BackoffStrategy.EXPONENTIAL, 1.0, 30.0, 2.0, jitter_enabled=False)
        assert d1 == 1.0   # 1.0 * 2^0
        assert d2 == 2.0   # 1.0 * 2^1
        assert d3 == 4.0   # 1.0 * 2^2
        result.ok("6-3: EXPONENTIAL 전략 (지수)")
    except Exception as e:
        result.fail("6-3: EXPONENTIAL", str(e))

    # 6-4: max_delay 제한
    try:
        d = calculate_backoff(10, BackoffStrategy.EXPONENTIAL, 1.0, 5.0, 2.0, jitter_enabled=False)
        assert d == 5.0
        result.ok("6-4: max_delay 제한")
    except Exception as e:
        result.fail("6-4: max_delay", str(e))

    # 6-5: 지터 적용
    try:
        random.seed(42)
        d_jitter = calculate_backoff(
            1, BackoffStrategy.CONSTANT, 1.0, 30.0,
            jitter_enabled=True, jitter_factor=0.5,
        )
        # 지터: 1.0 * (1 - 0.5) ~ 1.0 * (1 + 0.5) = 0.5 ~ 1.5
        assert 0.5 <= d_jitter <= 1.5
        result.ok("6-5: 지터 적용 (0.5~1.5)")
    except Exception as e:
        result.fail("6-5: 지터", str(e))

    # 6-6: 지터 비활성화
    try:
        d = calculate_backoff(1, BackoffStrategy.CONSTANT, 2.0, 30.0, jitter_enabled=False)
        assert d == 2.0
        result.ok("6-6: 지터 비활성화 → 정확한 값")
    except Exception as e:
        result.fail("6-6: 지터 비활성화", str(e))

    # 6-7: DECORRELATED_JITTER 전략
    try:
        random.seed(42)
        d = calculate_backoff(
            1, BackoffStrategy.DECORRELATED_JITTER, 1.0, 30.0,
            previous_delay=1.0,
        )
        # random_between(1.0, 3.0) → 1.0~3.0
        assert 1.0 <= d <= 3.0
        result.ok("6-7: DECORRELATED_JITTER 전략")
    except Exception as e:
        result.fail("6-7: DECORRELATED_JITTER", str(e))

    # 6-8: DECORRELATED_JITTER previous_delay=None
    try:
        random.seed(42)
        d = calculate_backoff(
            1, BackoffStrategy.DECORRELATED_JITTER, 1.0, 30.0,
            previous_delay=None,
        )
        # previous_delay → initial_delay=1.0, random(1.0, 3.0)
        assert 1.0 <= d <= 3.0
        result.ok("6-8: DECORRELATED_JITTER previous_delay=None")
    except Exception as e:
        result.fail("6-8: previous_delay None", str(e))

    # 6-9: attempt < 1 → 0.0
    try:
        d = calculate_backoff(0, BackoffStrategy.EXPONENTIAL, 1.0, 30.0)
        assert d == 0.0
        result.ok("6-9: attempt < 1 → 0.0")
    except Exception as e:
        result.fail("6-9: attempt 0", str(e))

    # 6-10: _calculate_backoff_from_config
    try:
        config = RetryConfig(
            backoff_strategy=BackoffStrategy.CONSTANT,
            initial_delay=2.0,
            max_delay=30.0,
            jitter_enabled=False,
        )
        d = _calculate_backoff_from_config(1, config)
        assert d == 2.0
        result.ok("6-10: _calculate_backoff_from_config")
    except Exception as e:
        result.fail("6-10: from_config", str(e))


# =============================================================================
# [7] _is_retryable 함수
# =============================================================================
def test_is_retryable(result: TestResult) -> None:
    """_is_retryable 함수 테스트."""
    print("\n[7] _is_retryable 함수")

    # 7-1: retryable 예외
    try:
        assert _is_retryable(
            ConnectionError("conn"),
            (ConnectionError, TimeoutError),
            (),
        ) is True
        result.ok("7-1: ConnectionError → retryable")
    except Exception as e:
        result.fail("7-1: retryable", str(e))

    # 7-2: non_retryable 우선
    try:
        assert _is_retryable(
            ConnectionError("conn"),
            (ConnectionError,),
            (ConnectionError,),
        ) is False
        result.ok("7-2: non_retryable 우선")
    except Exception as e:
        result.fail("7-2: non_retryable 우선", str(e))

    # 7-3: 미포함 예외 → False
    try:
        assert _is_retryable(
            ValueError("val"),
            (ConnectionError,),
            (),
        ) is False
        result.ok("7-3: ValueError (미포함) → False")
    except Exception as e:
        result.fail("7-3: 미포함", str(e))

    # 7-4: RetryableException 하위 클래스
    try:
        # TimeoutException은 RetryableException 하위
        exc = TimeoutException(message="test", timeout_seconds=5.0, operation="op")
        assert _is_retryable(exc, (), ()) is True
        result.ok("7-4: RetryableException 하위 → True")
    except Exception as e:
        result.fail("7-4: RetryableException 하위", str(e))

    # 7-5: non_retryable에 RetryableException 하위 등록
    try:
        exc = TimeoutException(message="test", timeout_seconds=5.0, operation="op")
        assert _is_retryable(exc, (), (TimeoutException,)) is False
        result.ok("7-5: non_retryable에 등록 → False")
    except Exception as e:
        result.fail("7-5: non_retryable 등록", str(e))

    # 7-6: 빈 튜플 → 기본적으로 False
    try:
        assert _is_retryable(ValueError("v"), (), ()) is False
        result.ok("7-6: 빈 튜플 → False")
    except Exception as e:
        result.fail("7-6: 빈 튜플", str(e))


# =============================================================================
# [8] RetryMechanism 초기화
# =============================================================================
def test_retry_mechanism_init(result: TestResult) -> None:
    """RetryMechanism 초기화 테스트."""
    print("\n[8] RetryMechanism 초기화")

    # 8-1: 기본 초기화
    try:
        rm = RetryMechanism()
        assert rm.name == "default"
        assert rm.config.max_attempts == 3
        result.ok("8-1: 기본 초기화")
    except Exception as e:
        result.fail("8-1: 기본 초기화", str(e))

    # 8-2: 이름 지정
    try:
        rm = RetryMechanism(name="custom")
        assert rm.name == "custom"
        result.ok("8-2: 이름 지정")
    except Exception as e:
        result.fail("8-2: 이름", str(e))

    # 8-3: 커스텀 설정
    try:
        config = RetryConfig(max_attempts=5, backoff_strategy=BackoffStrategy.LINEAR)
        rm = RetryMechanism(config=config)
        assert rm.config.max_attempts == 5
        assert rm.config.backoff_strategy == BackoffStrategy.LINEAR
        result.ok("8-3: 커스텀 설정")
    except Exception as e:
        result.fail("8-3: 커스텀 설정", str(e))

    # 8-4: config 속성
    try:
        config = RetryConfig(max_attempts=7)
        rm = RetryMechanism(config=config)
        assert rm.config is config
        result.ok("8-4: config 속성")
    except Exception as e:
        result.fail("8-4: config", str(e))

    # 8-5: metrics_collector 없이 정상 동작
    try:
        rm = RetryMechanism(metrics_collector=None)
        val = rm.execute(lambda: 42)
        assert val == 42
        result.ok("8-5: metrics_collector=None")
    except Exception as e:
        result.fail("8-5: metrics None", str(e))


# =============================================================================
# [9] RetryMechanism.execute 동기 실행
# =============================================================================
def test_retry_mechanism_execute(result: TestResult) -> None:
    """RetryMechanism.execute 동기 실행 테스트."""
    print("\n[9] RetryMechanism.execute 동기 실행")

    # 9-1: 첫 시도에서 성공
    try:
        config = RetryConfig(max_attempts=3, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        val = rm.execute(lambda: "success")
        assert val == "success"
        result.ok("9-1: 첫 시도 성공")
    except Exception as e:
        result.fail("9-1: 첫 시도 성공", str(e))

    # 9-2: 재시도 후 성공
    try:
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("fail")
            return "recovered"

        config = RetryConfig(max_attempts=5, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        val = rm.execute(flaky)
        assert val == "recovered"
        assert call_count[0] == 3
        result.ok("9-2: 재시도 후 성공 (3번째)")
    except Exception as e:
        result.fail("9-2: 재시도 후 성공", str(e))

    # 9-3: 재시도 소진 → 마지막 예외 발생
    try:
        config = RetryConfig(max_attempts=3, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        raised = False
        try:
            rm.execute(lambda: (_ for _ in ()).throw(ConnectionError("always_fail")))
        except ConnectionError:
            raised = True
        assert raised
        result.ok("9-3: 재시도 소진 → 예외")
    except Exception as e:
        result.fail("9-3: 소진 예외", str(e))

    # 9-4: 재시도 불가 예외 → 즉시 실패
    try:
        call_count = [0]

        def non_retryable():
            call_count[0] += 1
            raise ValueError("non_retryable")

        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.001,
            max_delay=0.01,
            retryable_exceptions=(ConnectionError,),
            jitter_enabled=False,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        raised = False
        try:
            rm.execute(non_retryable)
        except ValueError:
            raised = True
        assert raised
        assert call_count[0] == 1  # 재시도 없이 즉시 실패
        result.ok("9-4: 재시도 불가 → 즉시 실패")
    except Exception as e:
        result.fail("9-4: 재시도 불가", str(e))

    # 9-5: config_override
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        call_count = [0]

        def counting():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("fail")
            return "ok"

        override = RetryConfig(max_attempts=5, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        val = rm.execute(counting, config_override=override)
        assert val == "ok"
        result.ok("9-5: config_override 적용")
    except Exception as e:
        result.fail("9-5: config_override", str(e))

    # 9-6: 인수 전달
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        val = rm.execute(lambda x, y: x + y, 3, 4)
        assert val == 7
        result.ok("9-6: 인수 전달 (3+4=7)")
    except Exception as e:
        result.fail("9-6: 인수 전달", str(e))

    # 9-7: 키워드 인수 전달
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        val = rm.execute(lambda a=0, b=0: a * b, a=5, b=6)
        assert val == 30
        result.ok("9-7: 키워드 인수 전달")
    except Exception as e:
        result.fail("9-7: 키워드 인수", str(e))

    # 9-8: 타임아웃 초과
    try:
        config = RetryConfig(
            max_attempts=10,
            timeout=0.05,
            initial_delay=0.03,
            max_delay=0.03,
            jitter_enabled=False,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)

        def slow_fail():
            raise ConnectionError("fail")

        raised = False
        try:
            rm.execute(slow_fail)
        except (TimeoutException, ConnectionError):
            raised = True
        assert raised
        result.ok("9-8: 타임아웃 초과")
    except Exception as e:
        result.fail("9-8: 타임아웃", str(e))

    # 9-9: non_retryable_exceptions
    try:
        call_count = [0]

        def raising():
            call_count[0] += 1
            raise ConnectionError("conn")

        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.001,
            max_delay=0.01,
            non_retryable_exceptions=(ConnectionError,),
            jitter_enabled=False,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        raised = False
        try:
            rm.execute(raising)
        except ConnectionError:
            raised = True
        assert raised
        assert call_count[0] == 1
        result.ok("9-9: non_retryable_exceptions 즉시 실패")
    except Exception as e:
        result.fail("9-9: non_retryable", str(e))

    # 9-10: max_attempts=1 → 재시도 없음
    try:
        call_count = [0]

        def counting():
            call_count[0] += 1
            raise ConnectionError("fail")

        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        raised = False
        try:
            rm.execute(counting)
        except ConnectionError:
            raised = True
        assert raised
        assert call_count[0] == 1
        result.ok("9-10: max_attempts=1 → 한 번만 실행")
    except Exception as e:
        result.fail("9-10: max_attempts=1", str(e))


# =============================================================================
# [10] RetryMechanism.execute_with_result
# =============================================================================
def test_execute_with_result(result: TestResult) -> None:
    """execute_with_result 테스트."""
    print("\n[10] RetryMechanism.execute_with_result")

    # 10-1: 성공 결과
    try:
        config = RetryConfig(max_attempts=3, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        rr = rm.execute_with_result(lambda: "ok")
        assert rr.success is True
        assert rr.value == "ok"
        assert rr.outcome == RetryOutcome.SUCCESS
        assert rr.total_attempts == 1
        result.ok("10-1: 성공 결과")
    except Exception as e:
        result.fail("10-1: 성공", str(e))

    # 10-2: 실패 결과 (EXHAUSTED)
    try:
        config = RetryConfig(max_attempts=2, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        rr = rm.execute_with_result(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        assert rr.success is False
        assert rr.outcome == RetryOutcome.EXHAUSTED
        assert rr.total_attempts == 2
        assert rr.final_exception is not None
        result.ok("10-2: 실패 결과 (EXHAUSTED)")
    except Exception as e:
        result.fail("10-2: EXHAUSTED", str(e))

    # 10-3: NON_RETRYABLE
    try:
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.001,
            max_delay=0.01,
            retryable_exceptions=(ConnectionError,),
            jitter_enabled=False,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        rr = rm.execute_with_result(lambda: (_ for _ in ()).throw(ValueError("non_retry")))
        assert rr.success is False
        assert rr.outcome == RetryOutcome.NON_RETRYABLE
        assert rr.total_attempts == 1
        result.ok("10-3: NON_RETRYABLE")
    except Exception as e:
        result.fail("10-3: NON_RETRYABLE", str(e))

    # 10-4: attempts 기록
    try:
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("fail")
            return "ok"

        config = RetryConfig(max_attempts=5, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        rr = rm.execute_with_result(flaky)
        assert len(rr.attempts) == 3
        assert rr.attempts[0].success is False
        assert rr.attempts[1].success is False
        assert rr.attempts[2].success is True
        result.ok("10-4: attempts 기록")
    except Exception as e:
        result.fail("10-4: attempts", str(e))

    # 10-5: total_duration_ms / total_delay_ms
    try:
        config = RetryConfig(max_attempts=3, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        rr = rm.execute_with_result(lambda: "fast")
        assert rr.total_duration_ms >= 0
        assert rr.end_time is not None
        result.ok("10-5: duration/delay 기록")
    except Exception as e:
        result.fail("10-5: duration", str(e))

    # 10-6: to_dict
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        rr = rm.execute_with_result(lambda: "val")
        d = rr.to_dict()
        assert d["outcome"] == "SUCCESS"
        assert d["success"] is True
        assert isinstance(d["attempts"], list)
        result.ok("10-6: RetryResult to_dict")
    except Exception as e:
        result.fail("10-6: to_dict", str(e))


# =============================================================================
# [11] RetryMechanism 비동기 실행
# =============================================================================
def test_retry_mechanism_async(result: TestResult) -> None:
    """RetryMechanism 비동기 실행 테스트."""
    print("\n[11] RetryMechanism 비동기 실행")

    loop = asyncio.new_event_loop()

    # 11-1: 비동기 첫 시도 성공
    try:
        config = RetryConfig(max_attempts=3, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)

        async def async_ok():
            return "async_ok"

        val = loop.run_until_complete(rm.execute_async(async_ok))
        assert val == "async_ok"
        result.ok("11-1: 비동기 첫 시도 성공")
    except Exception as e:
        result.fail("11-1: async 성공", str(e))

    # 11-2: 비동기 재시도 후 성공
    try:
        call_count = [0]

        async def async_flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("fail")
            return "recovered"

        config = RetryConfig(max_attempts=5, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        val = loop.run_until_complete(rm.execute_async(async_flaky))
        assert val == "recovered"
        assert call_count[0] == 3
        result.ok("11-2: 비동기 재시도 후 성공")
    except Exception as e:
        result.fail("11-2: async 재시도", str(e))

    # 11-3: 비동기 소진 → 예외
    try:
        async def async_fail():
            raise ConnectionError("always")

        config = RetryConfig(max_attempts=2, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        rm = RetryMechanism(config=config)
        raised = False
        try:
            loop.run_until_complete(rm.execute_async(async_fail))
        except ConnectionError:
            raised = True
        assert raised
        result.ok("11-3: 비동기 소진 → 예외")
    except Exception as e:
        result.fail("11-3: async 소진", str(e))

    # 11-4: execute_async_with_result
    try:
        async def async_val():
            return 99

        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        rr = loop.run_until_complete(rm.execute_async_with_result(async_val))
        assert rr.success is True
        assert rr.value == 99
        result.ok("11-4: execute_async_with_result")
    except Exception as e:
        result.fail("11-4: async_with_result", str(e))

    # 11-5: 비동기 NON_RETRYABLE
    try:
        async def async_non_retry():
            raise ValueError("not retryable")

        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.001,
            max_delay=0.01,
            retryable_exceptions=(ConnectionError,),
            jitter_enabled=False,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        rr = loop.run_until_complete(rm.execute_async_with_result(async_non_retry))
        assert rr.success is False
        assert rr.outcome == RetryOutcome.NON_RETRYABLE
        result.ok("11-5: 비동기 NON_RETRYABLE")
    except Exception as e:
        result.fail("11-5: async NON_RETRYABLE", str(e))

    # 11-6: per_attempt_timeout
    try:
        async def async_slow():
            await asyncio.sleep(10)
            return "never"

        config = RetryConfig(
            max_attempts=2,
            initial_delay=0.001,
            max_delay=0.01,
            per_attempt_timeout=0.01,
            jitter_enabled=False,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        rr = loop.run_until_complete(rm.execute_async_with_result(async_slow))
        assert rr.success is False
        result.ok("11-6: per_attempt_timeout")
    except Exception as e:
        result.fail("11-6: per_attempt_timeout", str(e))

    loop.close()


# =============================================================================
# [12] 콜백
# =============================================================================
def test_callbacks(result: TestResult) -> None:
    """콜백 테스트."""
    print("\n[12] 콜백 (on_retry, on_success, on_failure)")

    # 12-1: on_success 콜백
    try:
        success_calls = []
        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.001,
            max_delay=0.01,
            on_success=lambda attempt, ms: success_calls.append((attempt, ms)),
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        rm.execute(lambda: "ok")
        assert len(success_calls) == 1
        assert success_calls[0][0] == 1
        result.ok("12-1: on_success 콜백")
    except Exception as e:
        result.fail("12-1: on_success", str(e))

    # 12-2: on_retry 콜백
    try:
        retry_calls = []
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("fail")
            return "ok"

        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.001,
            max_delay=0.01,
            jitter_enabled=False,
            on_retry=lambda attempt, exc, delay: retry_calls.append((attempt, type(exc).__name__)),
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        rm.execute(flaky)
        assert len(retry_calls) == 2  # 시도 1, 2에서 콜백
        assert retry_calls[0][1] == "ConnectionError"
        result.ok("12-2: on_retry 콜백")
    except Exception as e:
        result.fail("12-2: on_retry", str(e))

    # 12-3: on_failure 콜백
    try:
        failure_calls = []
        config = RetryConfig(
            max_attempts=2,
            initial_delay=0.001,
            max_delay=0.01,
            jitter_enabled=False,
            on_failure=lambda attempts, exc: failure_calls.append((attempts, type(exc).__name__)),
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        try:
            rm.execute(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        assert len(failure_calls) == 1
        assert failure_calls[0][0] == 2
        result.ok("12-3: on_failure 콜백")
    except Exception as e:
        result.fail("12-3: on_failure", str(e))

    # 12-4: on_success 예외 시 전파 안됨
    try:
        def bad_cb(attempt, ms):
            raise RuntimeError("cb error")

        config = RetryConfig(
            max_attempts=1,
            initial_delay=0.001,
            max_delay=0.01,
            on_success=bad_cb,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        val = rm.execute(lambda: "ok")
        assert val == "ok"
        result.ok("12-4: on_success 예외 → 전파 안됨")
    except Exception as e:
        result.fail("12-4: on_success 예외", str(e))

    # 12-5: on_retry 예외 시 전파 안됨
    try:
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("fail")
            return "ok"

        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.001,
            max_delay=0.01,
            jitter_enabled=False,
            on_retry=lambda a, e, d: (_ for _ in ()).throw(RuntimeError("cb")),
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        val = rm.execute(flaky)
        assert val == "ok"
        result.ok("12-5: on_retry 예외 → 전파 안됨")
    except Exception as e:
        result.fail("12-5: on_retry 예외", str(e))

    # 12-6: on_failure 예외 시 전파 안됨
    try:
        config = RetryConfig(
            max_attempts=1,
            initial_delay=0.001,
            max_delay=0.01,
            on_failure=lambda a, e: (_ for _ in ()).throw(RuntimeError("cb")),
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        raised = False
        try:
            rm.execute(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            raised = True
        assert raised
        result.ok("12-6: on_failure 예외 → 전파 안됨")
    except Exception as e:
        result.fail("12-6: on_failure 예외", str(e))

    # 12-7: 성공 시 on_failure 미호출
    try:
        failure_calls = []
        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.001,
            max_delay=0.01,
            on_failure=lambda a, e: failure_calls.append(a),
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        rm.execute(lambda: "ok")
        assert len(failure_calls) == 0
        result.ok("12-7: 성공 시 on_failure 미호출")
    except Exception as e:
        result.fail("12-7: 성공 시 미호출", str(e))

    # 12-8: on_retry 마지막 시도에서 미호출
    try:
        retry_calls = []
        config = RetryConfig(
            max_attempts=2,
            initial_delay=0.001,
            max_delay=0.01,
            jitter_enabled=False,
            on_retry=lambda a, e, d: retry_calls.append(a),
            log_retries=False,
        )
        rm = RetryMechanism(config=config)
        try:
            rm.execute(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        # 마지막 시도(2)에서는 on_retry 미호출 (더 재시도할 게 없으므로)
        assert len(retry_calls) == 1
        assert retry_calls[0] == 1
        result.ok("12-8: on_retry 마지막 시도 미호출")
    except Exception as e:
        result.fail("12-8: 마지막 시도", str(e))


# =============================================================================
# [13] 데코레이터 retry / async_retry
# =============================================================================
def test_decorators(result: TestResult) -> None:
    """데코레이터 테스트."""
    print("\n[13] 데코레이터 retry / async_retry")

    # 13-1: @retry 기본
    try:
        @retry(max_attempts=3, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        def simple():
            return "simple_result"

        val = simple()
        assert val == "simple_result"
        result.ok("13-1: @retry 기본")
    except Exception as e:
        result.fail("13-1: @retry 기본", str(e))

    # 13-2: @retry 재시도
    try:
        call_count = [0]

        @retry(max_attempts=5, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("fail")
            return "ok"

        val = flaky()
        assert val == "ok"
        assert call_count[0] == 3
        result.ok("13-2: @retry 재시도")
    except Exception as e:
        result.fail("13-2: @retry 재시도", str(e))

    # 13-3: @retry 함수 이름 보존
    try:
        @retry(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        def named_func():
            """독스트링."""
            return True

        assert named_func.__name__ == "named_func"
        assert "독스트링" in (named_func.__doc__ or "")
        result.ok("13-3: @retry 이름/독스트링 보존")
    except Exception as e:
        result.fail("13-3: wraps", str(e))

    # 13-4: @retry _retry_mechanism 속성
    try:
        @retry(max_attempts=3, initial_delay=0.001, max_delay=0.01, log_retries=False)
        def with_mechanism():
            return True

        assert hasattr(with_mechanism, "_retry_mechanism")
        assert isinstance(with_mechanism._retry_mechanism, RetryMechanism)
        result.ok("13-4: _retry_mechanism 속성")
    except Exception as e:
        result.fail("13-4: _retry_mechanism", str(e))

    # 13-5: @retry _original_func 속성
    try:
        @retry(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        def orig_func():
            return "orig"

        assert hasattr(orig_func, "_original_func")
        assert orig_func._original_func() == "orig"
        result.ok("13-5: _original_func 속성")
    except Exception as e:
        result.fail("13-5: _original_func", str(e))

    # 13-6: @async_retry 기본
    try:
        @async_retry(max_attempts=3, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        async def async_simple():
            return "async_result"

        loop = asyncio.new_event_loop()
        val = loop.run_until_complete(async_simple())
        loop.close()
        assert val == "async_result"
        result.ok("13-6: @async_retry 기본")
    except Exception as e:
        result.fail("13-6: @async_retry", str(e))

    # 13-7: @async_retry 재시도
    try:
        call_count = [0]

        @async_retry(max_attempts=5, initial_delay=0.001, max_delay=0.01, jitter_enabled=False, log_retries=False)
        async def async_flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("fail")
            return "recovered"

        loop = asyncio.new_event_loop()
        val = loop.run_until_complete(async_flaky())
        loop.close()
        assert val == "recovered"
        result.ok("13-7: @async_retry 재시도")
    except Exception as e:
        result.fail("13-7: @async_retry 재시도", str(e))

    # 13-8: 단일 예외 클래스를 튜플로 변환
    try:
        @retry(
            max_attempts=1,
            initial_delay=0.001,
            max_delay=0.01,
            retryable_exceptions=ConnectionError,  # 단일 클래스
            log_retries=False,
        )
        def single_exc():
            return True

        val = single_exc()
        assert val is True
        result.ok("13-8: 단일 예외 → 튜플 변환")
    except Exception as e:
        result.fail("13-8: 단일 예외 변환", str(e))


# =============================================================================
# [14] 헬퍼 함수
# =============================================================================
def test_helper_functions(result: TestResult) -> None:
    """헬퍼 함수 테스트."""
    print("\n[14] 헬퍼 함수")
    _reset_registry()

    # 14-1: register_retry_mechanism
    try:
        _reset_registry()
        config = RetryConfig(max_attempts=5)
        rm = RetryMechanism(config=config, name="helper_1")
        register_retry_mechanism("helper_1", rm)
        result.ok("14-1: register_retry_mechanism")
    except Exception as e:
        result.fail("14-1: register", str(e))

    # 14-2: get_retry_mechanism (존재)
    try:
        found = get_retry_mechanism("helper_1")
        assert found is not None
        assert found.name == "helper_1"
        result.ok("14-2: get_retry_mechanism 존재")
    except Exception as e:
        result.fail("14-2: get 존재", str(e))

    # 14-3: get_retry_mechanism (미존재)
    try:
        _reset_registry()
        found = get_retry_mechanism("nonexistent")
        assert found is None
        result.ok("14-3: get_retry_mechanism 미존재 → None")
    except Exception as e:
        result.fail("14-3: get 미존재", str(e))

    # 14-4: create_retry_mechanism
    try:
        rm = create_retry_mechanism(name="created")
        assert rm.name == "created"
        assert rm.config.max_attempts == DEFAULT_MAX_ATTEMPTS
        result.ok("14-4: create_retry_mechanism")
    except Exception as e:
        result.fail("14-4: create", str(e))

    # 14-5: create_retry_mechanism with overrides
    try:
        rm = create_retry_mechanism(name="overridden", max_attempts=7)
        assert rm.config.max_attempts == 7
        result.ok("14-5: create_retry_mechanism with overrides")
    except Exception as e:
        result.fail("14-5: overrides", str(e))

    # 14-6: _reset_registry
    try:
        _reset_registry()
        config = RetryConfig()
        rm = RetryMechanism(config=config, name="temp")
        register_retry_mechanism("temp", rm)
        assert get_retry_mechanism("temp") is not None
        _reset_registry()
        assert get_retry_mechanism("temp") is None
        result.ok("14-6: _reset_registry")
    except Exception as e:
        result.fail("14-6: reset", str(e))


# =============================================================================
# [15] 레지스트리 (_RetryRegistry)
# =============================================================================
def test_retry_registry(result: TestResult) -> None:
    """_RetryRegistry 테스트."""
    print("\n[15] 레지스트리 (_RetryRegistry)")
    _reset_registry()

    from core_foundation.resilience.retry_mechanism import _RetryRegistry, _registry

    # 15-1: 싱글톤 패턴
    try:
        r1 = _RetryRegistry()
        r2 = _RetryRegistry()
        assert r1 is r2
        result.ok("15-1: 싱글톤 패턴")
    except Exception as e:
        result.fail("15-1: 싱글톤", str(e))

    # 15-2: get_or_create
    try:
        _reset_registry()
        rm = _registry.get_or_create("svc_a")
        assert rm.name == "svc_a"
        result.ok("15-2: get_or_create")
    except Exception as e:
        result.fail("15-2: get_or_create", str(e))

    # 15-3: get_or_create 중복 → 동일 인스턴스
    try:
        rm1 = _registry.get_or_create("svc_a")
        rm2 = _registry.get_or_create("svc_a")
        assert rm1 is rm2
        result.ok("15-3: get_or_create 중복 → 동일")
    except Exception as e:
        result.fail("15-3: 중복", str(e))

    # 15-4: unregister
    try:
        _registry.get_or_create("to_remove")
        _registry.unregister("to_remove")
        assert _registry.get("to_remove") is None
        result.ok("15-4: unregister")
    except Exception as e:
        result.fail("15-4: unregister", str(e))

    # 15-5: list_all
    try:
        _reset_registry()
        _registry.get_or_create("x")
        _registry.get_or_create("y")
        names = _registry.list_all()
        assert "x" in names
        assert "y" in names
        result.ok("15-5: list_all")
    except Exception as e:
        result.fail("15-5: list_all", str(e))

    # 15-6: clear
    try:
        _registry.clear()
        assert len(_registry.list_all()) == 0
        result.ok("15-6: clear")
    except Exception as e:
        result.fail("15-6: clear", str(e))


# =============================================================================
# [16] __all__ 내보내기 검증
# =============================================================================
def test_all_exports(result: TestResult) -> None:
    """__all__ 내보내기 검증."""
    print("\n[16] __all__ 내보내기 검증")

    import core_foundation.resilience.retry_mechanism as rm_module
    import core_foundation.resilience as resilience_pkg

    # 16-1: retry_mechanism __all__
    try:
        expected = {
            "BackoffStrategy", "RetryOutcome",
            "DEFAULT_MAX_ATTEMPTS", "DEFAULT_INITIAL_DELAY",
            "DEFAULT_MAX_DELAY", "DEFAULT_EXPONENTIAL_BASE",
            "DEFAULT_JITTER_FACTOR",
            "RetryConfig", "RetryAttempt", "RetryResult",
            "RetryMechanism",
            "retry", "async_retry",
            "calculate_backoff", "create_retry_mechanism",
            "get_retry_mechanism", "register_retry_mechanism",
            "_reset_registry",
        }
        actual = set(rm_module.__all__)
        missing = expected - actual
        assert not missing, f"누락: {missing}"
        result.ok("16-1: retry_mechanism __all__ 완전성")
    except Exception as e:
        result.fail("16-1: __all__", str(e))

    # 16-2: __all__ 항목 실재
    try:
        for name in rm_module.__all__:
            assert hasattr(rm_module, name), f"{name} 미존재"
        result.ok("16-2: __all__ 항목 실재 확인")
    except Exception as e:
        result.fail("16-2: 실재", str(e))

    # 16-3: 패키지 __all__
    try:
        pkg_all = set(resilience_pkg.__all__)
        assert "RetryMechanism" in pkg_all
        assert "BackoffStrategy" in pkg_all
        assert "RetryConfig" in pkg_all
        assert "_reset_retry_registry" in pkg_all
        result.ok("16-3: 패키지 __all__ 포함 확인")
    except Exception as e:
        result.fail("16-3: 패키지 __all__", str(e))

    # 16-4: 버전
    try:
        assert rm_module.__version__ == "1.0.0"
        result.ok("16-4: __version__ = '1.0.0'")
    except Exception as e:
        result.fail("16-4: __version__", str(e))


# =============================================================================
# [17] 엣지 케이스
# =============================================================================
def test_edge_cases(result: TestResult) -> None:
    """엣지 케이스 테스트."""
    print("\n[17] 엣지 케이스")

    # 17-1: 스레드 안전성
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        results = []
        errors = []

        def worker(i):
            try:
                val = rm.execute(lambda: i * 2)
                results.append(val)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(results) == 20
        result.ok("17-1: 스레드 안전성 (20 스레드)")
    except Exception as e:
        result.fail("17-1: 스레드 안전성", str(e))

    # 17-2: 빈 함수
    try:
        config = RetryConfig(max_attempts=1, initial_delay=0.001, max_delay=0.01, log_retries=False)
        rm = RetryMechanism(config=config)
        val = rm.execute(lambda: None)
        assert val is None
        result.ok("17-2: None 반환")
    except Exception as e:
        result.fail("17-2: None 반환", str(e))

    # 17-3: 백오프 음수 방지 (큰 지터)
    try:
        d = calculate_backoff(
            1, BackoffStrategy.CONSTANT, 0.01, 30.0,
            jitter_enabled=True, jitter_factor=1.0,
        )
        assert d >= MIN_DELAY
        result.ok("17-3: 음수 방지 (MIN_DELAY)")
    except Exception as e:
        result.fail("17-3: 음수 방지", str(e))

    # 17-4: EXPONENTIAL 큰 시도 번호
    try:
        d = calculate_backoff(100, BackoffStrategy.EXPONENTIAL, 1.0, 10.0, 2.0, jitter_enabled=False)
        assert d == 10.0  # max_delay 제한
        result.ok("17-4: EXPONENTIAL 큰 시도 → max_delay")
    except Exception as e:
        result.fail("17-4: EXPONENTIAL 큰 시도", str(e))

    # 17-5: RetryConfig.from_yaml 실패 시 기본값
    try:
        config = RetryConfig.from_yaml()
        assert config.max_attempts == DEFAULT_MAX_ATTEMPTS
        result.ok("17-5: from_yaml 실패 → 기본값")
    except Exception as e:
        result.fail("17-5: from_yaml", str(e))

    # 17-6: TIMEOUT 결과
    try:
        config = RetryConfig(
            max_attempts=100,
            timeout=0.01,
            initial_delay=0.005,
            max_delay=0.005,
            jitter_enabled=False,
            log_retries=False,
        )
        rm = RetryMechanism(config=config)

        def slow():
            time.sleep(0.005)
            raise ConnectionError("fail")

        rr = rm.execute_with_result(slow)
        # 타임아웃 또는 소진
        assert rr.success is False
        result.ok("17-6: 타임아웃 결과")
    except Exception as e:
        result.fail("17-6: 타임아웃", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """테스트 실행."""
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("RetryMechanism 단위 테스트")
    print("=" * 60)

    r = TestResult()

    test_constants(r)
    test_backoff_strategy_enum(r)
    test_retry_outcome_enum(r)
    test_retry_config(r)
    test_retry_attempt_and_result(r)
    test_calculate_backoff(r)
    test_is_retryable(r)
    test_retry_mechanism_init(r)
    test_retry_mechanism_execute(r)
    test_execute_with_result(r)
    test_retry_mechanism_async(r)
    test_callbacks(r)
    test_decorators(r)
    test_helper_functions(r)
    test_retry_registry(r)
    test_all_exports(r)
    test_edge_cases(r)

    r.summary()

    _reset_registry()


if __name__ == "__main__":
    main()
