# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/resilience/unit
파일: test_circuit_breaker.py
설명: 서킷 브레이커 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-16

테스트 범위:
    [1]  상수 검증 (6개)
    [2]  CircuitState Enum (6개)
    [3]  FailureType Enum (4개)
    [4]  CircuitBreakerConfig 데이터 클래스 (8개)
    [5]  CircuitBreakerStats 데이터 클래스 (9개)
    [6]  RequestRecord / StateChangeEvent (6개)
    [7]  CircuitBreaker 초기화 (7개)
    [8]  CircuitBreaker 상태 전환 (CLOSED→OPEN→HALF_OPEN→CLOSED) (12개)
    [9]  CircuitBreaker 슬라이딩 윈도우 (6개)
    [10] CircuitBreaker 요청 실행 (execute) (8개)
    [11] CircuitBreaker 컨텍스트 매니저 (6개)
    [12] CircuitBreaker 콜백 / 이벤트 (6개)
    [13] CircuitBreaker 관리 메서드 (reset, force_open, force_close) (7개)
    [14] CircuitBreakerRegistry (8개)
    [15] 데코레이터 circuit_protected (6개)
    [16] 헬퍼 함수 (get_circuit_breaker, get_all_circuit_status) (5개)
    [17] __all__ 내보내기 검증 (4개)
    [18] 엣지 케이스 (6개)
"""

import asyncio
import io
import sys
import time
import threading
from copy import deepcopy
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.resilience.circuit_breaker import (
    # Enum
    CircuitState,
    FailureType,
    # 상수
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_SUCCESS_THRESHOLD,
    DEFAULT_OPEN_TIMEOUT,
    DEFAULT_HALF_OPEN_MAX_REQUESTS,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_MINIMUM_REQUESTS,
    # 이벤트 타입
    EVENT_ON_OPEN,
    EVENT_ON_CLOSE,
    EVENT_ON_HALF_OPEN,
    EVENT_ON_SUCCESS,
    EVENT_ON_FAILURE,
    # 설정 키
    CONFIG_KEY_CIRCUIT_BREAKER,
    CONFIG_KEY_ENABLED,
    CONFIG_KEY_DEFAULTS,
    CONFIG_KEY_SERVICES,
    # 데이터 클래스
    CircuitBreakerConfig,
    CircuitBreakerStats,
    RequestRecord,
    StateChangeEvent,
    # 메인 클래스
    CircuitBreaker,
    CircuitBreakerRegistry,
    # 데코레이터
    circuit_protected,
    # 함수
    get_circuit_breaker,
    get_all_circuit_status,
    # 유틸리티 (테스트용)
    _get_registry,
    _reset_registry,
)

from shared.exceptions.infrastructure_exceptions import CircuitBreakerOpenException


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
# 헬퍼: 레지스트리 리셋
# =============================================================================
def reset_all():
    """전역 레지스트리 리셋."""
    _reset_registry()


def _make_circuit(name="test", **config_kwargs) -> CircuitBreaker:
    """테스트용 서킷 브레이커 생성."""
    config = CircuitBreakerConfig(
        failure_threshold=config_kwargs.get("failure_threshold", 3),
        success_threshold=config_kwargs.get("success_threshold", 2),
        open_timeout=config_kwargs.get("open_timeout", 0.1),
        half_open_max_requests=config_kwargs.get("half_open_max_requests", 2),
        window_size=config_kwargs.get("window_size", 60.0),
        minimum_requests=config_kwargs.get("minimum_requests", 3),
    )
    mock_loader = MagicMock()
    mock_loader.get.return_value = {}
    return CircuitBreaker(name=name, config=config, config_loader=mock_loader)


# =============================================================================
# [1] 상수 검증
# =============================================================================
def test_constants(result: TestResult) -> None:
    """상수 값 검증."""
    print("\n[1] 상수 검증")

    # 1-1
    try:
        assert DEFAULT_FAILURE_THRESHOLD == 5
        result.ok("1-1: DEFAULT_FAILURE_THRESHOLD = 5")
    except Exception as e:
        result.fail("1-1: DEFAULT_FAILURE_THRESHOLD", str(e))

    # 1-2
    try:
        assert DEFAULT_SUCCESS_THRESHOLD == 3
        result.ok("1-2: DEFAULT_SUCCESS_THRESHOLD = 3")
    except Exception as e:
        result.fail("1-2: DEFAULT_SUCCESS_THRESHOLD", str(e))

    # 1-3
    try:
        assert DEFAULT_OPEN_TIMEOUT == 30.0
        result.ok("1-3: DEFAULT_OPEN_TIMEOUT = 30.0")
    except Exception as e:
        result.fail("1-3: DEFAULT_OPEN_TIMEOUT", str(e))

    # 1-4
    try:
        assert DEFAULT_HALF_OPEN_MAX_REQUESTS == 3
        result.ok("1-4: DEFAULT_HALF_OPEN_MAX_REQUESTS = 3")
    except Exception as e:
        result.fail("1-4: DEFAULT_HALF_OPEN_MAX_REQUESTS", str(e))

    # 1-5
    try:
        assert DEFAULT_WINDOW_SIZE == 60.0
        result.ok("1-5: DEFAULT_WINDOW_SIZE = 60.0")
    except Exception as e:
        result.fail("1-5: DEFAULT_WINDOW_SIZE", str(e))

    # 1-6
    try:
        assert DEFAULT_MINIMUM_REQUESTS == 10
        assert EVENT_ON_OPEN == "on_open"
        assert EVENT_ON_CLOSE == "on_close"
        assert EVENT_ON_HALF_OPEN == "on_half_open"
        assert CONFIG_KEY_CIRCUIT_BREAKER == "circuit_breaker"
        result.ok("1-6: DEFAULT_MINIMUM_REQUESTS, 이벤트/설정 키 검증")
    except Exception as e:
        result.fail("1-6: 기타 상수", str(e))


# =============================================================================
# [2] CircuitState Enum
# =============================================================================
def test_circuit_state_enum(result: TestResult) -> None:
    """CircuitState Enum 테스트."""
    print("\n[2] CircuitState Enum")

    # 2-1
    try:
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"
        result.ok("2-1: CircuitState 값 검증")
    except Exception as e:
        result.fail("2-1: CircuitState 값", str(e))

    # 2-2
    try:
        assert CircuitState.CLOSED.is_allowing_requests is True
        assert CircuitState.HALF_OPEN.is_allowing_requests is True
        assert CircuitState.OPEN.is_allowing_requests is False
        result.ok("2-2: is_allowing_requests 속성")
    except Exception as e:
        result.fail("2-2: is_allowing_requests", str(e))

    # 2-3
    try:
        assert CircuitState.CLOSED.korean_label == "닫힘"
        assert CircuitState.OPEN.korean_label == "열림"
        assert CircuitState.HALF_OPEN.korean_label == "반열림"
        result.ok("2-3: korean_label 속성")
    except Exception as e:
        result.fail("2-3: korean_label", str(e))

    # 2-4
    try:
        assert issubclass(CircuitState, str)
        assert isinstance(CircuitState.CLOSED, str)
        result.ok("2-4: str Enum 상속")
    except Exception as e:
        result.fail("2-4: str Enum", str(e))

    # 2-5
    try:
        assert len(CircuitState) == 3
        result.ok("2-5: CircuitState 멤버 수 = 3")
    except Exception as e:
        result.fail("2-5: 멤버 수", str(e))

    # 2-6
    try:
        assert CircuitState("closed") == CircuitState.CLOSED
        assert CircuitState("open") == CircuitState.OPEN
        result.ok("2-6: 문자열에서 생성")
    except Exception as e:
        result.fail("2-6: 문자열 생성", str(e))


# =============================================================================
# [3] FailureType Enum
# =============================================================================
def test_failure_type_enum(result: TestResult) -> None:
    """FailureType Enum 테스트."""
    print("\n[3] FailureType Enum")

    # 3-1
    try:
        assert FailureType.EXCEPTION.value == "exception"
        assert FailureType.TIMEOUT.value == "timeout"
        assert FailureType.ERROR_RESPONSE.value == "error_response"
        assert FailureType.REJECTION.value == "rejection"
        result.ok("3-1: FailureType 값 검증")
    except Exception as e:
        result.fail("3-1: FailureType 값", str(e))

    # 3-2
    try:
        assert len(FailureType) == 4
        result.ok("3-2: FailureType 멤버 수 = 4")
    except Exception as e:
        result.fail("3-2: 멤버 수", str(e))

    # 3-3
    try:
        assert issubclass(FailureType, str)
        result.ok("3-3: str Enum 상속")
    except Exception as e:
        result.fail("3-3: str Enum", str(e))

    # 3-4
    try:
        assert FailureType("timeout") == FailureType.TIMEOUT
        result.ok("3-4: 문자열에서 생성")
    except Exception as e:
        result.fail("3-4: 문자열 생성", str(e))


# =============================================================================
# [4] CircuitBreakerConfig 데이터 클래스
# =============================================================================
def test_circuit_breaker_config(result: TestResult) -> None:
    """CircuitBreakerConfig 테스트."""
    print("\n[4] CircuitBreakerConfig 데이터 클래스")

    # 4-1: 기본값
    try:
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.open_timeout == 30.0
        assert config.half_open_max_requests == 3
        assert config.window_size == 60.0
        assert config.minimum_requests == 10
        assert config.timeout is None
        assert config.critical is False
        result.ok("4-1: 기본값 검증")
    except Exception as e:
        result.fail("4-1: 기본값", str(e))

    # 4-2: 커스텀 값
    try:
        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            open_timeout=60.0,
            half_open_max_requests=5,
            window_size=120.0,
            minimum_requests=20,
            timeout=30.0,
            critical=True,
        )
        assert config.failure_threshold == 10
        assert config.critical is True
        result.ok("4-2: 커스텀 값 설정")
    except Exception as e:
        result.fail("4-2: 커스텀 값", str(e))

    # 4-3: failure_threshold < 1 검증
    try:
        raised = False
        try:
            CircuitBreakerConfig(failure_threshold=0)
        except ValueError:
            raised = True
        assert raised, "ValueError 미발생"
        result.ok("4-3: failure_threshold < 1 → ValueError")
    except Exception as e:
        result.fail("4-3: failure_threshold 검증", str(e))

    # 4-4: success_threshold < 1 검증
    try:
        raised = False
        try:
            CircuitBreakerConfig(success_threshold=0)
        except ValueError:
            raised = True
        assert raised, "ValueError 미발생"
        result.ok("4-4: success_threshold < 1 → ValueError")
    except Exception as e:
        result.fail("4-4: success_threshold 검증", str(e))

    # 4-5: open_timeout <= 0 검증
    try:
        raised = False
        try:
            CircuitBreakerConfig(open_timeout=0)
        except ValueError:
            raised = True
        assert raised, "ValueError 미발생"
        result.ok("4-5: open_timeout <= 0 → ValueError")
    except Exception as e:
        result.fail("4-5: open_timeout 검증", str(e))

    # 4-6: half_open_max_requests < 1 검증
    try:
        raised = False
        try:
            CircuitBreakerConfig(half_open_max_requests=0)
        except ValueError:
            raised = True
        assert raised, "ValueError 미발생"
        result.ok("4-6: half_open_max_requests < 1 → ValueError")
    except Exception as e:
        result.fail("4-6: half_open_max_requests 검증", str(e))

    # 4-7: window_size <= 0 검증
    try:
        raised = False
        try:
            CircuitBreakerConfig(window_size=0)
        except ValueError:
            raised = True
        assert raised, "ValueError 미발생"
        result.ok("4-7: window_size <= 0 → ValueError")
    except Exception as e:
        result.fail("4-7: window_size 검증", str(e))

    # 4-8: to_dict 변환
    try:
        config = CircuitBreakerConfig()
        d = config.to_dict()
        assert isinstance(d, dict)
        assert "failure_threshold" in d
        assert "success_threshold" in d
        assert "open_timeout" in d
        assert "critical" in d
        assert d["failure_threshold"] == 5
        result.ok("4-8: to_dict 변환")
    except Exception as e:
        result.fail("4-8: to_dict", str(e))


# =============================================================================
# [5] CircuitBreakerStats 데이터 클래스
# =============================================================================
def test_circuit_breaker_stats(result: TestResult) -> None:
    """CircuitBreakerStats 테스트."""
    print("\n[5] CircuitBreakerStats 데이터 클래스")

    # 5-1: 기본값
    try:
        stats = CircuitBreakerStats()
        assert stats.state == CircuitState.CLOSED
        assert stats.failure_count == 0
        assert stats.success_count == 0
        assert stats.total_requests == 0
        assert stats.consecutive_failures == 0
        result.ok("5-1: 기본값 검증")
    except Exception as e:
        result.fail("5-1: 기본값", str(e))

    # 5-2: failure_rate (0건)
    try:
        stats = CircuitBreakerStats()
        assert stats.failure_rate == 0.0
        assert stats.success_rate == 1.0
        result.ok("5-2: failure_rate / success_rate (0건)")
    except Exception as e:
        result.fail("5-2: failure_rate 0건", str(e))

    # 5-3: failure_rate (3실패 / 7성공)
    try:
        stats = CircuitBreakerStats(failure_count=3, success_count=7)
        assert abs(stats.failure_rate - 0.3) < 1e-9
        assert abs(stats.success_rate - 0.7) < 1e-9
        result.ok("5-3: failure_rate = 0.3, success_rate = 0.7")
    except Exception as e:
        result.fail("5-3: failure_rate 계산", str(e))

    # 5-4: total_failure_rate
    try:
        stats = CircuitBreakerStats(total_requests=100, total_failures=25)
        assert abs(stats.total_failure_rate - 0.25) < 1e-9
        result.ok("5-4: total_failure_rate = 0.25")
    except Exception as e:
        result.fail("5-4: total_failure_rate", str(e))

    # 5-5: total_failure_rate (0건)
    try:
        stats = CircuitBreakerStats()
        assert stats.total_failure_rate == 0.0
        result.ok("5-5: total_failure_rate (0건) = 0.0")
    except Exception as e:
        result.fail("5-5: total_failure_rate 0건", str(e))

    # 5-6: is_healthy
    try:
        stats = CircuitBreakerStats(state=CircuitState.CLOSED)
        assert stats.is_healthy is True
        stats_open = CircuitBreakerStats(state=CircuitState.OPEN)
        assert stats_open.is_healthy is False
        result.ok("5-6: is_healthy 속성")
    except Exception as e:
        result.fail("5-6: is_healthy", str(e))

    # 5-7: to_dict 변환
    try:
        stats = CircuitBreakerStats(
            state=CircuitState.CLOSED,
            failure_count=2,
            success_count=8,
            total_requests=10,
        )
        d = stats.to_dict()
        assert isinstance(d, dict)
        assert d["state"] == "closed"
        assert d["state_label"] == "닫힘"
        assert d["failure_count"] == 2
        assert d["success_count"] == 8
        assert d["is_healthy"] is True
        result.ok("5-7: to_dict 변환")
    except Exception as e:
        result.fail("5-7: to_dict", str(e))

    # 5-8: to_dict 시간 포맷팅
    try:
        now = datetime.now(timezone.utc)
        stats = CircuitBreakerStats(last_failure_time=now, last_success_time=now)
        d = stats.to_dict()
        assert d["last_failure_time"] is not None
        assert d["last_success_time"] is not None
        assert isinstance(d["last_failure_time"], str)
        result.ok("5-8: to_dict 시간 포맷")
    except Exception as e:
        result.fail("5-8: to_dict 시간", str(e))

    # 5-9: to_dict 시간 None
    try:
        stats = CircuitBreakerStats()
        d = stats.to_dict()
        assert d["last_failure_time"] is None
        assert d["last_success_time"] is None
        assert d["last_state_change_time"] is None
        result.ok("5-9: to_dict 시간 None")
    except Exception as e:
        result.fail("5-9: to_dict None", str(e))


# =============================================================================
# [6] RequestRecord / StateChangeEvent
# =============================================================================
def test_request_record_and_state_change_event(result: TestResult) -> None:
    """RequestRecord / StateChangeEvent 테스트."""
    print("\n[6] RequestRecord / StateChangeEvent")

    # 6-1: RequestRecord 생성
    try:
        record = RequestRecord(timestamp=time.monotonic(), success=True, duration_ms=5.0)
        assert record.success is True
        assert record.duration_ms == 5.0
        assert record.failure_type is None
        result.ok("6-1: RequestRecord 성공 기록")
    except Exception as e:
        result.fail("6-1: RequestRecord", str(e))

    # 6-2: RequestRecord 실패
    try:
        record = RequestRecord(
            timestamp=time.monotonic(),
            success=False,
            duration_ms=10.0,
            failure_type=FailureType.TIMEOUT,
        )
        assert record.success is False
        assert record.failure_type == FailureType.TIMEOUT
        result.ok("6-2: RequestRecord 실패 기록")
    except Exception as e:
        result.fail("6-2: RequestRecord 실패", str(e))

    # 6-3: StateChangeEvent 생성
    try:
        event = StateChangeEvent(
            circuit_name="test_circuit",
            previous_state=CircuitState.CLOSED,
            current_state=CircuitState.OPEN,
            reason="실패 임계값 초과",
        )
        assert event.circuit_name == "test_circuit"
        assert event.previous_state == CircuitState.CLOSED
        assert event.current_state == CircuitState.OPEN
        assert isinstance(event.timestamp, datetime)
        result.ok("6-3: StateChangeEvent 생성")
    except Exception as e:
        result.fail("6-3: StateChangeEvent", str(e))

    # 6-4: StateChangeEvent to_dict
    try:
        event = StateChangeEvent(
            circuit_name="test",
            previous_state=CircuitState.OPEN,
            current_state=CircuitState.HALF_OPEN,
            reason="타임아웃 만료",
        )
        d = event.to_dict()
        assert d["circuit_name"] == "test"
        assert d["previous_state"] == "open"
        assert d["current_state"] == "half_open"
        assert d["reason"] == "타임아웃 만료"
        assert isinstance(d["timestamp"], str)
        result.ok("6-4: StateChangeEvent to_dict")
    except Exception as e:
        result.fail("6-4: StateChangeEvent to_dict", str(e))

    # 6-5: StateChangeEvent stats 포함
    try:
        stats = CircuitBreakerStats(failure_count=5)
        event = StateChangeEvent(
            circuit_name="test",
            previous_state=CircuitState.CLOSED,
            current_state=CircuitState.OPEN,
            stats=stats,
        )
        d = event.to_dict()
        assert d["stats"] is not None
        assert d["stats"]["failure_count"] == 5
        result.ok("6-5: StateChangeEvent stats 포함")
    except Exception as e:
        result.fail("6-5: StateChangeEvent stats", str(e))

    # 6-6: StateChangeEvent stats=None
    try:
        event = StateChangeEvent(
            circuit_name="test",
            previous_state=CircuitState.CLOSED,
            current_state=CircuitState.OPEN,
        )
        d = event.to_dict()
        assert d["stats"] is None
        result.ok("6-6: StateChangeEvent stats=None")
    except Exception as e:
        result.fail("6-6: StateChangeEvent stats None", str(e))


# =============================================================================
# [7] CircuitBreaker 초기화
# =============================================================================
def test_circuit_breaker_init(result: TestResult) -> None:
    """CircuitBreaker 초기화 테스트."""
    print("\n[7] CircuitBreaker 초기화")

    # 7-1: 기본 초기화
    try:
        cb = _make_circuit("init_test")
        assert cb.name == "init_test"
        assert cb.is_closed is True
        assert cb.is_open is False
        assert cb.is_half_open is False
        result.ok("7-1: 기본 초기화")
    except Exception as e:
        result.fail("7-1: 기본 초기화", str(e))

    # 7-2: 설정 적용
    try:
        cb = _make_circuit("config_test", failure_threshold=10, open_timeout=5.0)
        assert cb.config.failure_threshold == 10
        assert cb.config.open_timeout == 5.0
        result.ok("7-2: 설정 적용")
    except Exception as e:
        result.fail("7-2: 설정 적용", str(e))

    # 7-3: 상태 CLOSED
    try:
        cb = _make_circuit("state_test")
        assert cb.state == CircuitState.CLOSED
        result.ok("7-3: 초기 상태 CLOSED")
    except Exception as e:
        result.fail("7-3: 초기 상태", str(e))

    # 7-4: stats 초기값
    try:
        cb = _make_circuit("stats_test")
        stats = cb.stats
        assert stats.total_requests == 0
        assert stats.total_failures == 0
        assert stats.total_successes == 0
        result.ok("7-4: stats 초기값")
    except Exception as e:
        result.fail("7-4: stats 초기값", str(e))

    # 7-5: 폴백 핸들러 설정
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        fallback = lambda: "fallback_result"
        cb = CircuitBreaker(
            name="fallback_test",
            config=CircuitBreakerConfig(),
            config_loader=mock_loader,
            fallback=fallback,
        )
        assert cb._fallback is not None
        result.ok("7-5: 폴백 핸들러 설정")
    except Exception as e:
        result.fail("7-5: 폴백 핸들러", str(e))

    # 7-6: 콜백 설정
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        events = []
        callback = lambda evt: events.append(evt)
        cb = CircuitBreaker(
            name="callback_test",
            config=CircuitBreakerConfig(),
            config_loader=mock_loader,
            on_state_change=callback,
        )
        assert len(cb._state_change_callbacks) == 1
        result.ok("7-6: 콜백 설정")
    except Exception as e:
        result.fail("7-6: 콜백 설정", str(e))

    # 7-7: YAML 로드 실패 시 기본값 사용
    try:
        mock_loader = MagicMock()
        mock_loader.get.side_effect = Exception("yaml error")
        cb = CircuitBreaker(name="yaml_fail", config_loader=mock_loader)
        assert cb.config.failure_threshold == DEFAULT_FAILURE_THRESHOLD
        result.ok("7-7: YAML 로드 실패 → 기본값")
    except Exception as e:
        result.fail("7-7: YAML 로드 실패", str(e))


# =============================================================================
# [8] CircuitBreaker 상태 전환
# =============================================================================
def test_circuit_breaker_state_transitions(result: TestResult) -> None:
    """CircuitBreaker 상태 전환 테스트."""
    print("\n[8] CircuitBreaker 상태 전환")

    # 8-1: CLOSED → OPEN (실패 임계값 초과)
    try:
        cb = _make_circuit("transition_1", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        assert cb.state == CircuitState.OPEN
        result.ok("8-1: CLOSED → OPEN (3회 실패)")
    except Exception as e:
        result.fail("8-1: CLOSED→OPEN", str(e))

    # 8-2: OPEN → HALF_OPEN (타임아웃 후)
    try:
        cb = _make_circuit("transition_2", failure_threshold=3, minimum_requests=3, open_timeout=0.05)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        assert cb.state == CircuitState.OPEN
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN
        result.ok("8-2: OPEN → HALF_OPEN (타임아웃 후)")
    except Exception as e:
        result.fail("8-2: OPEN→HALF_OPEN", str(e))

    # 8-3: HALF_OPEN → CLOSED (성공 임계값 충족)
    try:
        cb = _make_circuit("transition_3", failure_threshold=3, minimum_requests=3,
                           success_threshold=2, open_timeout=0.05)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        result.ok("8-3: HALF_OPEN → CLOSED (2회 성공)")
    except Exception as e:
        result.fail("8-3: HALF_OPEN→CLOSED", str(e))

    # 8-4: HALF_OPEN → OPEN (실패 발생)
    try:
        cb = _make_circuit("transition_4", failure_threshold=3, minimum_requests=3, open_timeout=0.05)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure(exception=ConnectionError("fail"))
        assert cb.state == CircuitState.OPEN
        result.ok("8-4: HALF_OPEN → OPEN (실패)")
    except Exception as e:
        result.fail("8-4: HALF_OPEN→OPEN", str(e))

    # 8-5: CLOSED 유지 (실패 < 임계값)
    try:
        cb = _make_circuit("transition_5", failure_threshold=3, minimum_requests=5)
        cb.record_failure(exception=ConnectionError("fail"))
        cb.record_failure(exception=ConnectionError("fail"))
        assert cb.state == CircuitState.CLOSED
        result.ok("8-5: CLOSED 유지 (실패 < 임계값)")
    except Exception as e:
        result.fail("8-5: CLOSED 유지", str(e))

    # 8-6: minimum_requests 미달 시 CLOSED 유지
    try:
        cb = _make_circuit("transition_6", failure_threshold=2, minimum_requests=10)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        # minimum_requests(10) 미달이므로 CLOSED 유지
        assert cb.state == CircuitState.CLOSED
        result.ok("8-6: minimum_requests 미달 → CLOSED 유지")
    except Exception as e:
        result.fail("8-6: minimum_requests 미달", str(e))

    # 8-7: stats.open_count 증가
    try:
        cb = _make_circuit("transition_7", failure_threshold=3, minimum_requests=3, open_timeout=0.05)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        assert cb.stats.open_count == 1
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure(exception=ConnectionError("fail"))
        assert cb.stats.open_count == 2
        result.ok("8-7: open_count 증가")
    except Exception as e:
        result.fail("8-7: open_count", str(e))

    # 8-8: state_change_count 추적
    try:
        cb = _make_circuit("transition_8", failure_threshold=3, minimum_requests=3,
                           success_threshold=2, open_timeout=0.05)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        # CLOSED→OPEN: +1
        time.sleep(0.1)
        _ = cb.state  # OPEN→HALF_OPEN: +1
        cb.record_success()
        cb.record_success()
        # HALF_OPEN→CLOSED: +1
        assert cb.stats.state_change_count == 3
        result.ok("8-8: state_change_count = 3")
    except Exception as e:
        result.fail("8-8: state_change_count", str(e))

    # 8-9: consecutive_failures 리셋
    try:
        cb = _make_circuit("transition_9", failure_threshold=5, minimum_requests=5)
        cb.record_failure(exception=ConnectionError("fail"))
        cb.record_failure(exception=ConnectionError("fail"))
        assert cb.stats.consecutive_failures == 2
        cb.record_success()
        assert cb.stats.consecutive_failures == 0
        result.ok("8-9: consecutive_failures 리셋")
    except Exception as e:
        result.fail("8-9: consecutive_failures 리셋", str(e))

    # 8-10: consecutive_successes 추적
    try:
        cb = _make_circuit("transition_10", failure_threshold=5, minimum_requests=5)
        cb.record_success()
        cb.record_success()
        cb.record_success()
        assert cb.stats.consecutive_successes == 3
        cb.record_failure(exception=ConnectionError("fail"))
        assert cb.stats.consecutive_successes == 0
        result.ok("8-10: consecutive_successes 추적")
    except Exception as e:
        result.fail("8-10: consecutive_successes", str(e))

    # 8-11: total_requests / total_successes / total_failures
    try:
        cb = _make_circuit("transition_11")
        cb.record_success()
        cb.record_success()
        cb.record_failure(exception=ConnectionError("fail"))
        assert cb.stats.total_requests == 3
        assert cb.stats.total_successes == 2
        assert cb.stats.total_failures == 1
        result.ok("8-11: total_requests/successes/failures")
    except Exception as e:
        result.fail("8-11: total 통계", str(e))

    # 8-12: 이중 전환 방지 (이미 OPEN인 상태에서 재전환)
    try:
        cb = _make_circuit("transition_12", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        assert cb.state == CircuitState.OPEN
        initial_open_count = cb.stats.open_count
        cb.force_open("다시 오픈")
        # 이미 OPEN이므로 open_count는 증가하지 않아야 함
        assert cb.stats.open_count == initial_open_count
        result.ok("8-12: 이중 OPEN 전환 방지")
    except Exception as e:
        result.fail("8-12: 이중 전환 방지", str(e))


# =============================================================================
# [9] CircuitBreaker 슬라이딩 윈도우
# =============================================================================
def test_sliding_window(result: TestResult) -> None:
    """슬라이딩 윈도우 테스트."""
    print("\n[9] CircuitBreaker 슬라이딩 윈도우")

    # 9-1: 윈도우에 기록 추가
    try:
        cb = _make_circuit("window_1", window_size=60.0)
        cb.record_success()
        cb.record_failure(exception=ConnectionError("fail"))
        stats = cb.stats
        assert stats.success_count == 1
        assert stats.failure_count == 1
        result.ok("9-1: 윈도우 기록 추가")
    except Exception as e:
        result.fail("9-1: 윈도우 기록", str(e))

    # 9-2: 윈도우 만료 기록 제거
    try:
        cb = _make_circuit("window_2", window_size=0.05)
        cb.record_success()
        cb.record_failure(exception=ConnectionError("fail"))
        time.sleep(0.1)
        stats = cb.stats
        assert stats.success_count == 0
        assert stats.failure_count == 0
        result.ok("9-2: 윈도우 만료 후 기록 제거")
    except Exception as e:
        result.fail("9-2: 윈도우 만료", str(e))

    # 9-3: allow_request (CLOSED)
    try:
        cb = _make_circuit("window_3")
        assert cb.allow_request() is True
        result.ok("9-3: allow_request CLOSED = True")
    except Exception as e:
        result.fail("9-3: allow_request CLOSED", str(e))

    # 9-4: allow_request (OPEN)
    try:
        cb = _make_circuit("window_4", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        assert cb.allow_request() is False
        result.ok("9-4: allow_request OPEN = False")
    except Exception as e:
        result.fail("9-4: allow_request OPEN", str(e))

    # 9-5: allow_request (HALF_OPEN, 제한된 요청)
    try:
        cb = _make_circuit("window_5", failure_threshold=3, minimum_requests=3,
                           half_open_max_requests=2, open_timeout=0.05)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        time.sleep(0.1)
        assert cb.allow_request() is True  # 1번째 요청
        assert cb.allow_request() is True  # 2번째 요청
        assert cb.allow_request() is False  # 3번째 거부
        result.ok("9-5: allow_request HALF_OPEN 제한")
    except Exception as e:
        result.fail("9-5: HALF_OPEN 제한", str(e))

    # 9-6: record_rejection 카운트
    try:
        cb = _make_circuit("window_6", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        cb.record_rejection()
        cb.record_rejection()
        assert cb.stats.total_rejections == 2
        result.ok("9-6: record_rejection 카운트")
    except Exception as e:
        result.fail("9-6: record_rejection", str(e))


# =============================================================================
# [10] CircuitBreaker 요청 실행 (execute)
# =============================================================================
def test_circuit_breaker_execute(result: TestResult) -> None:
    """CircuitBreaker execute 테스트."""
    print("\n[10] CircuitBreaker 요청 실행 (execute)")

    # 10-1: 정상 실행
    try:
        cb = _make_circuit("exec_1")
        value = cb.execute(lambda: 42)
        assert value == 42
        assert cb.stats.total_successes == 1
        result.ok("10-1: 정상 실행 반환값")
    except Exception as e:
        result.fail("10-1: 정상 실행", str(e))

    # 10-2: 예외 전파
    try:
        cb = _make_circuit("exec_2")
        raised = False
        try:
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("test")))
        except ValueError:
            raised = True
        assert raised
        result.ok("10-2: 예외 전파")
    except Exception as e:
        result.fail("10-2: 예외 전파", str(e))

    # 10-3: 서킷 OPEN 시 CircuitBreakerOpenException
    try:
        cb = _make_circuit("exec_3", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        raised = False
        try:
            cb.execute(lambda: 42)
        except CircuitBreakerOpenException:
            raised = True
        assert raised
        result.ok("10-3: OPEN → CircuitBreakerOpenException")
    except Exception as e:
        result.fail("10-3: CircuitBreakerOpenException", str(e))

    # 10-4: 폴백 실행
    try:
        cb = _make_circuit("exec_4", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        value = cb.execute(lambda: 42, fallback=lambda: "fallback")
        assert value == "fallback"
        result.ok("10-4: 폴백 실행")
    except Exception as e:
        result.fail("10-4: 폴백", str(e))

    # 10-5: 인스턴스 폴백
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        config = CircuitBreakerConfig(failure_threshold=3, minimum_requests=3)
        cb = CircuitBreaker(
            name="exec_5",
            config=config,
            config_loader=mock_loader,
            fallback=lambda: "instance_fallback",
        )
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        value = cb.execute(lambda: 42)
        assert value == "instance_fallback"
        result.ok("10-5: 인스턴스 폴백")
    except Exception as e:
        result.fail("10-5: 인스턴스 폴백", str(e))

    # 10-6: 실행 후 duration_ms 기록
    try:
        cb = _make_circuit("exec_6")
        cb.execute(lambda: time.sleep(0.01))
        assert cb.stats.total_successes == 1
        result.ok("10-6: duration_ms 기록")
    except Exception as e:
        result.fail("10-6: duration_ms", str(e))

    # 10-7: excluded_exceptions (실패로 카운트 안됨)
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        config = CircuitBreakerConfig(excluded_exceptions={ValueError})
        cb = CircuitBreaker(name="exec_7", config=config, config_loader=mock_loader)
        cb.record_failure(exception=ValueError("excluded"))
        # excluded이므로 성공으로 처리
        assert cb.stats.total_successes == 1
        assert cb.stats.total_failures == 0
        result.ok("10-7: excluded_exceptions")
    except Exception as e:
        result.fail("10-7: excluded_exceptions", str(e))

    # 10-8: include_exceptions (지정된 예외만 실패)
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        config = CircuitBreakerConfig(include_exceptions={ConnectionError})
        cb = CircuitBreaker(name="exec_8", config=config, config_loader=mock_loader)
        cb.record_failure(exception=ValueError("not_included"))
        # include에 없으므로 성공으로 처리
        assert cb.stats.total_successes == 1
        assert cb.stats.total_failures == 0
        cb.record_failure(exception=ConnectionError("included"))
        assert cb.stats.total_failures == 1
        result.ok("10-8: include_exceptions")
    except Exception as e:
        result.fail("10-8: include_exceptions", str(e))


# =============================================================================
# [11] CircuitBreaker 컨텍스트 매니저
# =============================================================================
def test_circuit_breaker_context_manager(result: TestResult) -> None:
    """CircuitBreaker 컨텍스트 매니저 테스트."""
    print("\n[11] CircuitBreaker 컨텍스트 매니저")

    # 11-1: __enter__ / __exit__ 성공
    try:
        cb = _make_circuit("ctx_1")
        with cb:
            pass
        assert cb.stats.total_successes == 1
        result.ok("11-1: 컨텍스트 매니저 성공")
    except Exception as e:
        result.fail("11-1: 컨텍스트 매니저 성공", str(e))

    # 11-2: __enter__ / __exit__ 실패
    try:
        cb = _make_circuit("ctx_2")
        try:
            with cb:
                raise ValueError("test_error")
        except ValueError:
            pass
        assert cb.stats.total_failures == 1
        result.ok("11-2: 컨텍스트 매니저 실패 기록")
    except Exception as e:
        result.fail("11-2: 컨텍스트 매니저 실패", str(e))

    # 11-3: 서킷 OPEN 시 __enter__에서 예외
    try:
        cb = _make_circuit("ctx_3", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        raised = False
        try:
            with cb:
                pass
        except CircuitBreakerOpenException:
            raised = True
        assert raised
        result.ok("11-3: OPEN → __enter__ 예외")
    except Exception as e:
        result.fail("11-3: OPEN __enter__", str(e))

    # 11-4: __exit__ 예외 전파 (return False)
    try:
        cb = _make_circuit("ctx_4")
        raised = False
        try:
            with cb:
                raise RuntimeError("propagate")
        except RuntimeError as e:
            if str(e) == "propagate":
                raised = True
        assert raised
        result.ok("11-4: __exit__ 예외 전파")
    except Exception as e:
        result.fail("11-4: __exit__ 전파", str(e))

    # 11-5: __call__ 컨텍스트 매니저
    try:
        cb = _make_circuit("ctx_5")
        with cb() as circuit:
            assert circuit is cb
        assert cb.stats.total_successes == 1
        result.ok("11-5: __call__ 컨텍스트 매니저")
    except Exception as e:
        result.fail("11-5: __call__", str(e))

    # 11-6: __call__ OPEN 시 예외
    try:
        cb = _make_circuit("ctx_6", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        raised = False
        try:
            with cb():
                pass
        except CircuitBreakerOpenException:
            raised = True
        assert raised
        result.ok("11-6: __call__ OPEN → 예외")
    except Exception as e:
        result.fail("11-6: __call__ OPEN", str(e))


# =============================================================================
# [12] CircuitBreaker 콜백 / 이벤트
# =============================================================================
def test_circuit_breaker_callbacks(result: TestResult) -> None:
    """콜백 / 이벤트 테스트."""
    print("\n[12] CircuitBreaker 콜백 / 이벤트")

    # 12-1: 상태 변경 콜백 호출
    try:
        events = []
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        config = CircuitBreakerConfig(failure_threshold=3, minimum_requests=3)
        cb = CircuitBreaker(
            name="cb_1",
            config=config,
            config_loader=mock_loader,
            on_state_change=lambda evt: events.append(evt),
        )
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        assert len(events) == 1
        assert events[0].current_state == CircuitState.OPEN
        result.ok("12-1: 상태 변경 콜백 (OPEN)")
    except Exception as e:
        result.fail("12-1: 콜백 OPEN", str(e))

    # 12-2: 콜백 추가
    try:
        cb = _make_circuit("cb_2")
        extra_events = []
        cb.add_state_change_callback(lambda evt: extra_events.append(evt))
        cb.force_open("테스트")
        assert len(extra_events) == 1
        result.ok("12-2: add_state_change_callback")
    except Exception as e:
        result.fail("12-2: 콜백 추가", str(e))

    # 12-3: 콜백 제거
    try:
        cb = _make_circuit("cb_3")
        events = []
        callback = lambda evt: events.append(evt)
        cb.add_state_change_callback(callback)
        removed = cb.remove_state_change_callback(callback)
        assert removed is True
        cb.force_open("테스트")
        assert len(events) == 0
        result.ok("12-3: remove_state_change_callback")
    except Exception as e:
        result.fail("12-3: 콜백 제거", str(e))

    # 12-4: 존재하지 않는 콜백 제거
    try:
        cb = _make_circuit("cb_4")
        removed = cb.remove_state_change_callback(lambda evt: None)
        assert removed is False
        result.ok("12-4: 존재하지 않는 콜백 제거 → False")
    except Exception as e:
        result.fail("12-4: 존재하지 않는 콜백", str(e))

    # 12-5: 콜백 예외 시 로그만 (전파 안됨)
    try:
        cb = _make_circuit("cb_5")
        cb.add_state_change_callback(lambda evt: (_ for _ in ()).throw(RuntimeError("cb fail")))
        # 콜백 오류가 있어도 상태 전환 자체는 성공해야 함
        cb.force_open("테스트")
        assert cb.state == CircuitState.OPEN
        result.ok("12-5: 콜백 예외 시 전파 안됨")
    except Exception as e:
        result.fail("12-5: 콜백 예외", str(e))

    # 12-6: StateChangeEvent 내용 검증
    try:
        events = []
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        config = CircuitBreakerConfig(failure_threshold=3, minimum_requests=3, open_timeout=0.05)
        cb = CircuitBreaker(
            name="cb_6",
            config=config,
            config_loader=mock_loader,
            on_state_change=lambda evt: events.append(evt),
        )
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        time.sleep(0.1)
        _ = cb.state  # HALF_OPEN 전환
        assert len(events) >= 2
        # 첫 번째: CLOSED→OPEN
        assert events[0].previous_state == CircuitState.CLOSED
        assert events[0].current_state == CircuitState.OPEN
        # 두 번째: OPEN→HALF_OPEN
        assert events[1].previous_state == CircuitState.OPEN
        assert events[1].current_state == CircuitState.HALF_OPEN
        result.ok("12-6: StateChangeEvent 내용 검증")
    except Exception as e:
        result.fail("12-6: StateChangeEvent 내용", str(e))


# =============================================================================
# [13] CircuitBreaker 관리 메서드
# =============================================================================
def test_circuit_breaker_management(result: TestResult) -> None:
    """관리 메서드 테스트."""
    print("\n[13] CircuitBreaker 관리 메서드")

    # 13-1: reset
    try:
        cb = _make_circuit("mgmt_1", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.stats.total_requests == 0
        assert cb.stats.total_failures == 0
        result.ok("13-1: reset → CLOSED, 통계 초기화")
    except Exception as e:
        result.fail("13-1: reset", str(e))

    # 13-2: force_open
    try:
        cb = _make_circuit("mgmt_2")
        assert cb.state == CircuitState.CLOSED
        cb.force_open("테스트 오픈")
        assert cb.state == CircuitState.OPEN
        result.ok("13-2: force_open")
    except Exception as e:
        result.fail("13-2: force_open", str(e))

    # 13-3: force_close
    try:
        cb = _make_circuit("mgmt_3")
        cb.force_open("테스트")
        assert cb.state == CircuitState.OPEN
        cb.force_close("테스트 클로즈")
        assert cb.state == CircuitState.CLOSED
        result.ok("13-3: force_close")
    except Exception as e:
        result.fail("13-3: force_close", str(e))

    # 13-4: get_status
    try:
        cb = _make_circuit("mgmt_4")
        status = cb.get_status()
        assert isinstance(status, dict)
        assert status["name"] == "mgmt_4"
        assert status["state"] == "closed"
        assert "config" in status
        assert "stats" in status
        assert "is_healthy" in status
        assert "time_in_current_state" in status
        result.ok("13-4: get_status 반환 구조")
    except Exception as e:
        result.fail("13-4: get_status", str(e))

    # 13-5: get_status.is_healthy
    try:
        cb = _make_circuit("mgmt_5")
        status = cb.get_status()
        assert status["is_healthy"] is True
        cb.force_open("테스트")
        status = cb.get_status()
        assert status["is_healthy"] is False
        result.ok("13-5: get_status.is_healthy")
    except Exception as e:
        result.fail("13-5: is_healthy", str(e))

    # 13-6: get_status.time_in_current_state
    try:
        cb = _make_circuit("mgmt_6")
        time.sleep(0.1)
        status = cb.get_status()
        assert status["time_in_current_state"] >= 0.05, (
            f"time_in_current_state={status['time_in_current_state']:.4f}, 기대값 >= 0.05"
        )
        result.ok("13-6: time_in_current_state")
    except Exception as e:
        result.fail("13-6: time_in_current_state", str(e))

    # 13-7: get_status.state_label
    try:
        cb = _make_circuit("mgmt_7")
        status = cb.get_status()
        assert status["state_label"] == "닫힘"
        result.ok("13-7: state_label = '닫힘'")
    except Exception as e:
        result.fail("13-7: state_label", str(e))


# =============================================================================
# [14] CircuitBreakerRegistry
# =============================================================================
def test_circuit_breaker_registry(result: TestResult) -> None:
    """CircuitBreakerRegistry 테스트."""
    print("\n[14] CircuitBreakerRegistry")

    # 14-1: get_or_create (새 서킷)
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        registry = CircuitBreakerRegistry(config_loader=mock_loader)
        config = CircuitBreakerConfig(failure_threshold=5)
        cb = registry.get_or_create("service_a", config=config)
        assert cb.name == "service_a"
        assert cb.config.failure_threshold == 5
        result.ok("14-1: get_or_create 새 서킷")
    except Exception as e:
        result.fail("14-1: get_or_create", str(e))

    # 14-2: get_or_create (기존 서킷 반환)
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        registry = CircuitBreakerRegistry(config_loader=mock_loader)
        config = CircuitBreakerConfig(failure_threshold=5)
        cb1 = registry.get_or_create("service_b", config=config)
        cb2 = registry.get_or_create("service_b")
        assert cb1 is cb2
        result.ok("14-2: get_or_create 기존 서킷 반환")
    except Exception as e:
        result.fail("14-2: get_or_create 기존", str(e))

    # 14-3: get (존재)
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        registry = CircuitBreakerRegistry(config_loader=mock_loader)
        config = CircuitBreakerConfig()
        registry.get_or_create("service_c", config=config)
        cb = registry.get("service_c")
        assert cb is not None
        result.ok("14-3: get 존재하는 서킷")
    except Exception as e:
        result.fail("14-3: get 존재", str(e))

    # 14-4: get (미존재)
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        registry = CircuitBreakerRegistry(config_loader=mock_loader)
        cb = registry.get("nonexistent")
        assert cb is None
        result.ok("14-4: get 미존재 → None")
    except Exception as e:
        result.fail("14-4: get 미존재", str(e))

    # 14-5: list_all
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        registry = CircuitBreakerRegistry(config_loader=mock_loader)
        config = CircuitBreakerConfig()
        registry.get_or_create("alpha", config=config)
        registry.get_or_create("beta", config=config)
        names = registry.list_all()
        assert "alpha" in names
        assert "beta" in names
        assert len(names) == 2
        result.ok("14-5: list_all")
    except Exception as e:
        result.fail("14-5: list_all", str(e))

    # 14-6: get_all_status
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        registry = CircuitBreakerRegistry(config_loader=mock_loader)
        config = CircuitBreakerConfig()
        registry.get_or_create("svc1", config=config)
        registry.get_or_create("svc2", config=config)
        status = registry.get_all_status()
        assert "svc1" in status
        assert "svc2" in status
        assert "state" in status["svc1"]
        result.ok("14-6: get_all_status")
    except Exception as e:
        result.fail("14-6: get_all_status", str(e))

    # 14-7: reset_all
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        registry = CircuitBreakerRegistry(config_loader=mock_loader)
        config = CircuitBreakerConfig(failure_threshold=3, minimum_requests=3)
        cb = registry.get_or_create("svc_reset", config=config)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))
        assert cb.state == CircuitState.OPEN
        registry.reset_all()
        assert cb.state == CircuitState.CLOSED
        result.ok("14-7: reset_all")
    except Exception as e:
        result.fail("14-7: reset_all", str(e))

    # 14-8: 스레드 안전성
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        registry = CircuitBreakerRegistry(config_loader=mock_loader)
        config = CircuitBreakerConfig()
        errors = []

        def create_circuit(name):
            try:
                registry.get_or_create(name, config=config)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=create_circuit, args=(f"thread_{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(registry.list_all()) == 20
        result.ok("14-8: 레지스트리 스레드 안전성")
    except Exception as e:
        result.fail("14-8: 스레드 안전성", str(e))


# =============================================================================
# [15] 데코레이터 circuit_protected
# =============================================================================
def test_circuit_protected_decorator(result: TestResult) -> None:
    """circuit_protected 데코레이터 테스트."""
    print("\n[15] 데코레이터 circuit_protected")
    reset_all()

    # 15-1: 동기 함수 보호
    try:
        reset_all()

        @circuit_protected("decorator_1", config=CircuitBreakerConfig())
        def sync_func():
            return "result"

        val = sync_func()
        assert val == "result"
        result.ok("15-1: 동기 함수 보호")
    except Exception as e:
        result.fail("15-1: 동기 함수 보호", str(e))

    # 15-2: 동기 함수 예외 전파
    try:
        reset_all()

        @circuit_protected("decorator_2", config=CircuitBreakerConfig())
        def failing_func():
            raise ConnectionError("fail")

        raised = False
        try:
            failing_func()
        except ConnectionError:
            raised = True
        assert raised
        result.ok("15-2: 동기 함수 예외 전파")
    except Exception as e:
        result.fail("15-2: 동기 예외 전파", str(e))

    # 15-3: 폴백 사용
    try:
        reset_all()
        config = CircuitBreakerConfig(failure_threshold=2, minimum_requests=2)

        @circuit_protected("decorator_3", config=config, fallback=lambda: "fb")
        def will_fail():
            raise ConnectionError("fail")

        # 실패시켜서 서킷 열기
        for _ in range(2):
            try:
                will_fail()
            except ConnectionError:
                pass
        # 이제 폴백 반환
        val = will_fail()
        assert val == "fb"
        result.ok("15-3: 폴백 사용")
    except Exception as e:
        result.fail("15-3: 폴백", str(e))

    # 15-4: 비동기 함수 보호
    try:
        reset_all()

        @circuit_protected("decorator_4", config=CircuitBreakerConfig())
        async def async_func():
            return "async_result"

        loop = asyncio.new_event_loop()
        val = loop.run_until_complete(async_func())
        loop.close()
        assert val == "async_result"
        result.ok("15-4: 비동기 함수 보호")
    except Exception as e:
        result.fail("15-4: 비동기 함수", str(e))

    # 15-5: 함수 이름 보존 (wraps)
    try:
        reset_all()

        @circuit_protected("decorator_5", config=CircuitBreakerConfig())
        def named_func():
            """독스트링."""
            return True

        assert named_func.__name__ == "named_func"
        assert "독스트링" in (named_func.__doc__ or "")
        result.ok("15-5: wraps 함수 이름/독스트링 보존")
    except Exception as e:
        result.fail("15-5: wraps", str(e))

    # 15-6: 레지스트리에 등록됨
    try:
        reset_all()

        @circuit_protected("decorator_6", config=CircuitBreakerConfig())
        def reg_func():
            return True

        reg_func()
        registry = _get_registry()
        cb = registry.get("decorator_6")
        assert cb is not None
        result.ok("15-6: 레지스트리 등록 확인")
    except Exception as e:
        result.fail("15-6: 레지스트리 등록", str(e))


# =============================================================================
# [16] 헬퍼 함수
# =============================================================================
def test_helper_functions(result: TestResult) -> None:
    """헬퍼 함수 테스트."""
    print("\n[16] 헬퍼 함수")
    reset_all()

    # 16-1: get_circuit_breaker
    try:
        reset_all()
        config = CircuitBreakerConfig()
        cb = get_circuit_breaker("helper_1", config=config)
        assert cb.name == "helper_1"
        assert cb.state == CircuitState.CLOSED
        result.ok("16-1: get_circuit_breaker")
    except Exception as e:
        result.fail("16-1: get_circuit_breaker", str(e))

    # 16-2: get_circuit_breaker 동일 이름 → 동일 인스턴스
    try:
        cb1 = get_circuit_breaker("helper_1")
        cb2 = get_circuit_breaker("helper_1")
        assert cb1 is cb2
        result.ok("16-2: 동일 이름 → 동일 인스턴스")
    except Exception as e:
        result.fail("16-2: 동일 인스턴스", str(e))

    # 16-3: get_all_circuit_status
    try:
        reset_all()
        config = CircuitBreakerConfig()
        get_circuit_breaker("svc_a", config=config)
        get_circuit_breaker("svc_b", config=config)
        status = get_all_circuit_status()
        assert "svc_a" in status
        assert "svc_b" in status
        result.ok("16-3: get_all_circuit_status")
    except Exception as e:
        result.fail("16-3: get_all_circuit_status", str(e))

    # 16-4: _reset_registry
    try:
        reset_all()
        config = CircuitBreakerConfig()
        get_circuit_breaker("temp", config=config)
        _reset_registry()
        status = get_all_circuit_status()
        assert "temp" not in status
        result.ok("16-4: _reset_registry")
    except Exception as e:
        result.fail("16-4: _reset_registry", str(e))

    # 16-5: _get_registry 싱글톤
    try:
        reset_all()
        r1 = _get_registry()
        r2 = _get_registry()
        assert r1 is r2
        result.ok("16-5: _get_registry 싱글톤")
    except Exception as e:
        result.fail("16-5: _get_registry 싱글톤", str(e))


# =============================================================================
# [17] __all__ 내보내기 검증
# =============================================================================
def test_all_exports(result: TestResult) -> None:
    """__all__ 내보내기 검증."""
    print("\n[17] __all__ 내보내기 검증")

    import core_foundation.resilience.circuit_breaker as cb_module
    import core_foundation.resilience as resilience_pkg

    # 17-1: circuit_breaker 모듈 __all__
    try:
        expected_cb = {
            "CircuitState", "FailureType",
            "DEFAULT_FAILURE_THRESHOLD", "DEFAULT_SUCCESS_THRESHOLD",
            "DEFAULT_OPEN_TIMEOUT", "DEFAULT_HALF_OPEN_MAX_REQUESTS",
            "DEFAULT_WINDOW_SIZE", "DEFAULT_MINIMUM_REQUESTS",
            "CircuitBreakerConfig", "CircuitBreakerStats",
            "RequestRecord", "StateChangeEvent",
            "CircuitBreaker", "CircuitBreakerRegistry",
            "circuit_protected",
            "get_circuit_breaker", "get_all_circuit_status",
            "_get_registry", "_reset_registry",
        }
        actual_cb = set(cb_module.__all__)
        missing = expected_cb - actual_cb
        assert not missing, f"누락: {missing}"
        result.ok("17-1: circuit_breaker __all__ 완전성")
    except Exception as e:
        result.fail("17-1: circuit_breaker __all__", str(e))

    # 17-2: __all__ 항목이 실제 존재
    try:
        for name in cb_module.__all__:
            assert hasattr(cb_module, name), f"{name} 미존재"
        result.ok("17-2: __all__ 항목 실재 확인")
    except Exception as e:
        result.fail("17-2: __all__ 실재", str(e))

    # 17-3: 패키지 __all__에 circuit_breaker 항목 포함
    try:
        pkg_all = set(resilience_pkg.__all__)
        assert "CircuitBreaker" in pkg_all
        assert "CircuitState" in pkg_all
        assert "CircuitBreakerConfig" in pkg_all
        assert "_get_circuit_registry" in pkg_all
        assert "_reset_circuit_registry" in pkg_all
        result.ok("17-3: 패키지 __all__ 포함 확인")
    except Exception as e:
        result.fail("17-3: 패키지 __all__", str(e))

    # 17-4: 버전 확인
    try:
        assert cb_module.__version__ == "1.0.0"
        result.ok("17-4: __version__ = '1.0.0'")
    except Exception as e:
        result.fail("17-4: __version__", str(e))


# =============================================================================
# [18] 엣지 케이스
# =============================================================================
def test_edge_cases(result: TestResult) -> None:
    """엣지 케이스 테스트."""
    print("\n[18] 엣지 케이스")

    # 18-1: 타임아웃 예외 분류
    try:
        cb = _make_circuit("edge_1")
        cb.record_failure(exception=TimeoutError("timeout"))
        assert cb.stats.total_failures == 1
        result.ok("18-1: TimeoutError → 실패 기록")
    except Exception as e:
        result.fail("18-1: TimeoutError", str(e))

    # 18-2: duration_ms 기록
    try:
        cb = _make_circuit("edge_2")
        cb.record_success(duration_ms=100.5)
        assert cb.stats.total_successes == 1
        result.ok("18-2: duration_ms 기록")
    except Exception as e:
        result.fail("18-2: duration_ms", str(e))

    # 18-3: 빈 상태에서 stats
    try:
        cb = _make_circuit("edge_3")
        stats = cb.stats
        assert stats.failure_rate == 0.0
        assert stats.success_rate == 1.0
        result.ok("18-3: 빈 상태 stats")
    except Exception as e:
        result.fail("18-3: 빈 stats", str(e))

    # 18-4: 스레드 안전성 (동시 기록)
    try:
        cb = _make_circuit("edge_4", failure_threshold=100, minimum_requests=100)
        errors = []

        def record_ops():
            try:
                for _ in range(50):
                    cb.record_success()
                    cb.record_failure(exception=ConnectionError("fail"))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=record_ops) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert cb.stats.total_requests == 400  # 4 threads × 100 ops
        result.ok("18-4: 동시 기록 스레드 안전성")
    except Exception as e:
        result.fail("18-4: 스레드 안전성", str(e))

    # 18-5: 비동기 execute
    try:
        cb = _make_circuit("edge_5")

        async def async_op():
            return "async_result"

        loop = asyncio.new_event_loop()
        val = loop.run_until_complete(cb.execute_async(async_op))
        loop.close()
        assert val == "async_result"
        assert cb.stats.total_successes == 1
        result.ok("18-5: 비동기 execute_async")
    except Exception as e:
        result.fail("18-5: async execute", str(e))

    # 18-6: 비동기 execute OPEN + 폴백
    try:
        cb = _make_circuit("edge_6", failure_threshold=3, minimum_requests=3)
        for _ in range(3):
            cb.record_failure(exception=ConnectionError("fail"))

        async def async_op():
            return "should_not_reach"

        async def async_fallback():
            return "async_fb"

        loop = asyncio.new_event_loop()
        val = loop.run_until_complete(cb.execute_async(async_op, fallback=async_fallback))
        loop.close()
        assert val == "async_fb"
        result.ok("18-6: async execute OPEN + 폴백")
    except Exception as e:
        result.fail("18-6: async 폴백", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """테스트 실행."""
    # UTF-8 출력 보장
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("CircuitBreaker 단위 테스트")
    print("=" * 60)

    r = TestResult()

    test_constants(r)
    test_circuit_state_enum(r)
    test_failure_type_enum(r)
    test_circuit_breaker_config(r)
    test_circuit_breaker_stats(r)
    test_request_record_and_state_change_event(r)
    test_circuit_breaker_init(r)
    test_circuit_breaker_state_transitions(r)
    test_sliding_window(r)
    test_circuit_breaker_execute(r)
    test_circuit_breaker_context_manager(r)
    test_circuit_breaker_callbacks(r)
    test_circuit_breaker_management(r)
    test_circuit_breaker_registry(r)
    test_circuit_protected_decorator(r)
    test_helper_functions(r)
    test_all_exports(r)
    test_edge_cases(r)

    r.summary()

    # 정리
    reset_all()


if __name__ == "__main__":
    main()
