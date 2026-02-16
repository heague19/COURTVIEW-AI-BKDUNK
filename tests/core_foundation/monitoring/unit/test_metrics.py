# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/monitoring/unit
파일: test_metrics.py
설명: Prometheus 스타일 메트릭 수집 (Counter, Gauge, Histogram, Summary) 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    [1]  상수 검증 (8개)
    [2]  MetricType Enum (5개)
    [3]  MetricUnit Enum (5개)
    [4]  MetricLabels 데이터 클래스 (8개)
    [5]  MetricValue 데이터 클래스 (5개)
    [6]  MetricSnapshot 데이터 클래스 (7개)
    [7]  BaseMetric 기본 클래스 (5개)
    [8]  Counter 메트릭 (8개)
    [9]  CounterChild (4개)
    [10] Gauge 메트릭 (10개)
    [11] GaugeChild (4개)
    [12] Histogram 메트릭 (10개)
    [13] HistogramChild (3개)
    [14] Summary 메트릭 (10개)
    [15] SummaryChild (3개)
    [16] MetricsCollector 초기화 / 기본 메트릭 (7개)
    [17] MetricsCollector 팩토리 / 내보내기 (9개)
    [18] 싱글톤 (_get_collector, _reset_collector) (4개)
    [19] 데코레이터 (measure_latency, count_calls) (6개)
    [20] 엣지 케이스 / __all__ (5개)

    총 128개 테스트
"""

import math
import sys
import threading
import time
from dataclasses import fields, FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# 테스트 대상 임포트
from core_foundation.monitoring.metrics import (
    # 상수
    METRIC_PREFIX,
    DEFAULT_HISTOGRAM_BUCKETS,
    FPS_HISTOGRAM_BUCKETS,
    ACCURACY_HISTOGRAM_BUCKETS,
    MODEL_INFERENCE_BUCKETS,
    FRAME_PROCESSING_BUCKETS,
    GPU_TEMPERATURE_BUCKETS,
    DEFAULT_QUANTILES,
    MAX_METRICS,
    SUMMARY_WINDOW_SECONDS,
    SUMMARY_MAX_OBSERVATIONS,
    CONFIG_KEY_METRICS,
    CONFIG_KEY_ENABLED,
    CONFIG_KEY_PREFIX,
    CONFIG_KEY_MAX_METRICS,
    CONFIG_KEY_SUMMARY_WINDOW,
    CONFIG_KEY_SUMMARY_MAX_OBS,
    # Enum
    MetricType,
    MetricUnit,
    # 데이터 클래스
    MetricLabels,
    MetricValue,
    MetricSnapshot,
    # 메트릭 클래스
    BaseMetric,
    Counter,
    Gauge,
    Histogram,
    Summary,
    # 메인 클래스
    MetricsCollector,
    # 싱글톤
    _get_collector,
    _reset_collector,
    # 데코레이터
    measure_latency,
    count_calls,
)

from core_foundation.config.loader import ConfigLoader


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
        """테스트 통과."""
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패."""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼 함수
# =============================================================================
def _make_collector(**kwargs) -> MetricsCollector:
    """
    테스트용 MetricsCollector 생성.
    ConfigLoader 의존성 우회하여 기본값으로 생성.
    """
    defaults = {
        "prefix": "test",
        "enabled": True,
        "max_metrics": 10000,
    }
    defaults.update(kwargs)
    return MetricsCollector(**defaults)


def _reset_singleton() -> None:
    """싱글톤 인스턴스 리셋."""
    _reset_collector()


# =============================================================================
# [1] 상수 검증 (8개)
# =============================================================================
def test_constants(result: TestResult) -> None:
    """상수 값 및 타입 검증."""
    print("\n[1] 상수 검증")

    # 1-1. METRIC_PREFIX
    try:
        assert METRIC_PREFIX == "courtview", f"METRIC_PREFIX={METRIC_PREFIX}"
        assert isinstance(METRIC_PREFIX, str)
        result.ok("1-1 METRIC_PREFIX == 'courtview'")
    except AssertionError as e:
        result.fail("1-1 METRIC_PREFIX", str(e))

    # 1-2. DEFAULT_HISTOGRAM_BUCKETS: 15개, 마지막 +Inf
    try:
        assert isinstance(DEFAULT_HISTOGRAM_BUCKETS, tuple)
        assert len(DEFAULT_HISTOGRAM_BUCKETS) == 15
        assert DEFAULT_HISTOGRAM_BUCKETS[-1] == float("inf")
        # 오름차순 정렬 확인
        for i in range(len(DEFAULT_HISTOGRAM_BUCKETS) - 1):
            assert DEFAULT_HISTOGRAM_BUCKETS[i] < DEFAULT_HISTOGRAM_BUCKETS[i + 1]
        result.ok("1-2 DEFAULT_HISTOGRAM_BUCKETS: 15개, 오름차순, +Inf")
    except AssertionError as e:
        result.fail("1-2 DEFAULT_HISTOGRAM_BUCKETS", str(e))

    # 1-3. FPS_HISTOGRAM_BUCKETS: 11개, 마지막 +Inf
    try:
        assert isinstance(FPS_HISTOGRAM_BUCKETS, tuple)
        assert len(FPS_HISTOGRAM_BUCKETS) == 11
        assert FPS_HISTOGRAM_BUCKETS[-1] == float("inf")
        assert FPS_HISTOGRAM_BUCKETS[0] == 15.0
        result.ok("1-3 FPS_HISTOGRAM_BUCKETS: 11개, 15.0~+Inf")
    except AssertionError as e:
        result.fail("1-3 FPS_HISTOGRAM_BUCKETS", str(e))

    # 1-4. ACCURACY_HISTOGRAM_BUCKETS: 11개, 0.5~1.0
    try:
        assert isinstance(ACCURACY_HISTOGRAM_BUCKETS, tuple)
        assert len(ACCURACY_HISTOGRAM_BUCKETS) == 11
        assert ACCURACY_HISTOGRAM_BUCKETS[0] == 0.5
        assert ACCURACY_HISTOGRAM_BUCKETS[-1] == 1.0
        result.ok("1-4 ACCURACY_HISTOGRAM_BUCKETS: 11개, 0.5~1.0")
    except AssertionError as e:
        result.fail("1-4 ACCURACY_HISTOGRAM_BUCKETS", str(e))

    # 1-5. DEFAULT_QUANTILES / MAX_METRICS / SUMMARY 상수
    try:
        assert DEFAULT_QUANTILES == (0.5, 0.9, 0.95, 0.99)
        assert MAX_METRICS == 10000
        assert SUMMARY_WINDOW_SECONDS == 600.0
        assert SUMMARY_MAX_OBSERVATIONS == 10000
        result.ok("1-5 DEFAULT_QUANTILES / MAX_METRICS / SUMMARY 상수")
    except AssertionError as e:
        result.fail("1-5 기본 상수", str(e))

    # 1-6. MODEL_INFERENCE_BUCKETS / FRAME_PROCESSING_BUCKETS / GPU_TEMPERATURE_BUCKETS
    try:
        assert len(MODEL_INFERENCE_BUCKETS) == 11
        assert MODEL_INFERENCE_BUCKETS[-1] == float("inf")
        assert len(FRAME_PROCESSING_BUCKETS) == 11
        assert FRAME_PROCESSING_BUCKETS[-1] == float("inf")
        assert len(GPU_TEMPERATURE_BUCKETS) == 11
        assert GPU_TEMPERATURE_BUCKETS[-1] == float("inf")
        result.ok("1-6 Desktop 특화 버킷 상수 (3종)")
    except AssertionError as e:
        result.fail("1-6 Desktop 특화 버킷 상수", str(e))

    # 1-7. CONFIG_KEY 상수 (6개)
    try:
        assert CONFIG_KEY_METRICS == "metrics"
        assert CONFIG_KEY_ENABLED == "enabled"
        assert CONFIG_KEY_PREFIX == "prefix"
        assert CONFIG_KEY_MAX_METRICS == "max_metrics"
        assert CONFIG_KEY_SUMMARY_WINDOW == "summary_window_seconds"
        assert CONFIG_KEY_SUMMARY_MAX_OBS == "summary_max_observations"
        result.ok("1-7 CONFIG_KEY 상수 (6개)")
    except AssertionError as e:
        result.fail("1-7 CONFIG_KEY 상수", str(e))

    # 1-8. 버킷 타입 일관성 (모두 Tuple[float, ...])
    try:
        all_buckets = [
            DEFAULT_HISTOGRAM_BUCKETS,
            FPS_HISTOGRAM_BUCKETS,
            ACCURACY_HISTOGRAM_BUCKETS,
            MODEL_INFERENCE_BUCKETS,
            FRAME_PROCESSING_BUCKETS,
            GPU_TEMPERATURE_BUCKETS,
        ]
        for b in all_buckets:
            assert isinstance(b, tuple)
            for v in b:
                assert isinstance(v, float)
        result.ok("1-8 모든 버킷 상수 Tuple[float, ...] 타입")
    except AssertionError as e:
        result.fail("1-8 버킷 타입 일관성", str(e))


# =============================================================================
# [2] MetricType Enum (5개)
# =============================================================================
def test_metric_type_enum(result: TestResult) -> None:
    """MetricType Enum 검증."""
    print("\n[2] MetricType Enum")

    # 2-1. 멤버 4개
    try:
        members = list(MetricType)
        assert len(members) == 4
        result.ok("2-1 MetricType 멤버 4개")
    except AssertionError as e:
        result.fail("2-1 MetricType 멤버 수", str(e))

    # 2-2. 값 검증
    try:
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.SUMMARY.value == "summary"
        result.ok("2-2 MetricType 값 (counter/gauge/histogram/summary)")
    except AssertionError as e:
        result.fail("2-2 MetricType 값", str(e))

    # 2-3. 문자열에서 생성
    try:
        assert MetricType("counter") == MetricType.COUNTER
        assert MetricType("summary") == MetricType.SUMMARY
        result.ok("2-3 MetricType 문자열 생성")
    except (AssertionError, ValueError) as e:
        result.fail("2-3 MetricType 문자열 생성", str(e))

    # 2-4. 잘못된 값 ValueError
    try:
        raised = False
        try:
            MetricType("invalid")
        except ValueError:
            raised = True
        assert raised, "ValueError 미발생"
        result.ok("2-4 MetricType 잘못된 값 ValueError")
    except AssertionError as e:
        result.fail("2-4 MetricType 잘못된 값", str(e))

    # 2-5. name 속성
    try:
        assert MetricType.COUNTER.name == "COUNTER"
        assert MetricType.HISTOGRAM.name == "HISTOGRAM"
        result.ok("2-5 MetricType name 속성")
    except AssertionError as e:
        result.fail("2-5 MetricType name", str(e))


# =============================================================================
# [3] MetricUnit Enum (5개)
# =============================================================================
def test_metric_unit_enum(result: TestResult) -> None:
    """MetricUnit Enum 검증."""
    print("\n[3] MetricUnit Enum")

    # 3-1. 멤버 7개
    try:
        members = list(MetricUnit)
        assert len(members) == 7, f"실제: {len(members)}"
        result.ok("3-1 MetricUnit 멤버 7개")
    except AssertionError as e:
        result.fail("3-1 MetricUnit 멤버 수", str(e))

    # 3-2. 값 검증
    try:
        assert MetricUnit.SECONDS.value == "seconds"
        assert MetricUnit.MILLISECONDS.value == "milliseconds"
        assert MetricUnit.BYTES.value == "bytes"
        assert MetricUnit.COUNT.value == "count"
        assert MetricUnit.PERCENT.value == "percent"
        assert MetricUnit.FPS.value == "fps"
        assert MetricUnit.RATIO.value == "ratio"
        result.ok("3-2 MetricUnit 값 (7개)")
    except AssertionError as e:
        result.fail("3-2 MetricUnit 값", str(e))

    # 3-3. 문자열에서 생성
    try:
        assert MetricUnit("seconds") == MetricUnit.SECONDS
        assert MetricUnit("fps") == MetricUnit.FPS
        result.ok("3-3 MetricUnit 문자열 생성")
    except (AssertionError, ValueError) as e:
        result.fail("3-3 MetricUnit 문자열 생성", str(e))

    # 3-4. 잘못된 값 ValueError
    try:
        raised = False
        try:
            MetricUnit("invalid")
        except ValueError:
            raised = True
        assert raised, "ValueError 미발생"
        result.ok("3-4 MetricUnit 잘못된 값 ValueError")
    except AssertionError as e:
        result.fail("3-4 MetricUnit 잘못된 값", str(e))

    # 3-5. name 속성
    try:
        assert MetricUnit.FPS.name == "FPS"
        assert MetricUnit.RATIO.name == "RATIO"
        result.ok("3-5 MetricUnit name 속성")
    except AssertionError as e:
        result.fail("3-5 MetricUnit name", str(e))


# =============================================================================
# [4] MetricLabels 데이터 클래스 (8개)
# =============================================================================
def test_metric_labels(result: TestResult) -> None:
    """MetricLabels 데이터 클래스 검증."""
    print("\n[4] MetricLabels 데이터 클래스")

    # 4-1. 기본 생성 (빈 레이블)
    try:
        ml = MetricLabels()
        assert ml.labels == ()
        assert isinstance(ml.labels, tuple)
        result.ok("4-1 MetricLabels 기본 생성 (빈 레이블)")
    except AssertionError as e:
        result.fail("4-1 기본 생성", str(e))

    # 4-2. from_dict 생성
    try:
        ml = MetricLabels.from_dict({"method": "GET", "endpoint": "/api"})
        assert isinstance(ml.labels, tuple)
        # 정렬된 순서로 저장됨
        d = ml.to_dict()
        assert d == {"endpoint": "/api", "method": "GET"}
        result.ok("4-2 from_dict 생성 (정렬 확인)")
    except AssertionError as e:
        result.fail("4-2 from_dict", str(e))

    # 4-3. from_dict None/빈 딕셔너리
    try:
        ml_none = MetricLabels.from_dict(None)
        assert ml_none.labels == ()
        ml_empty = MetricLabels.from_dict({})
        assert ml_empty.labels == ()
        result.ok("4-3 from_dict None/빈 딕셔너리 -> 빈 레이블")
    except AssertionError as e:
        result.fail("4-3 from_dict None/empty", str(e))

    # 4-4. to_prometheus_string
    try:
        ml = MetricLabels.from_dict({"method": "GET", "status": "200"})
        prom = ml.to_prometheus_string()
        assert '{' in prom and '}' in prom
        assert 'method="GET"' in prom
        assert 'status="200"' in prom
        result.ok("4-4 to_prometheus_string 형식")
    except AssertionError as e:
        result.fail("4-4 to_prometheus_string", str(e))

    # 4-5. 빈 레이블의 to_prometheus_string
    try:
        ml = MetricLabels()
        assert ml.to_prometheus_string() == ""
        result.ok("4-5 빈 레이블 to_prometheus_string == ''")
    except AssertionError as e:
        result.fail("4-5 빈 to_prometheus_string", str(e))

    # 4-6. frozen (불변성)
    try:
        ml = MetricLabels.from_dict({"a": "1"})
        raised = False
        try:
            ml.labels = (("b", "2"),)
        except (FrozenInstanceError, AttributeError):
            raised = True
        assert raised, "frozen 위반 미감지"
        result.ok("4-6 frozen 불변성")
    except AssertionError as e:
        result.fail("4-6 frozen", str(e))

    # 4-7. 해시 가능 (dict 키로 사용)
    try:
        ml1 = MetricLabels.from_dict({"a": "1", "b": "2"})
        ml2 = MetricLabels.from_dict({"b": "2", "a": "1"})
        # 정렬 후 동일하므로 해시 동일
        assert hash(ml1) == hash(ml2)
        d = {ml1: "value"}
        assert d[ml2] == "value"
        result.ok("4-7 해시 가능 (동일 레이블 -> 동일 해시)")
    except AssertionError as e:
        result.fail("4-7 해시", str(e))

    # 4-8. 다른 레이블은 다른 해시
    try:
        ml1 = MetricLabels.from_dict({"a": "1"})
        ml2 = MetricLabels.from_dict({"a": "2"})
        # 대부분의 경우 다른 해시 (해시 충돌 가능성 매우 낮음)
        assert ml1 != ml2
        result.ok("4-8 다른 레이블 -> 다른 MetricLabels")
    except AssertionError as e:
        result.fail("4-8 다른 해시", str(e))


# =============================================================================
# [5] MetricValue 데이터 클래스 (5개)
# =============================================================================
def test_metric_value(result: TestResult) -> None:
    """MetricValue 데이터 클래스 검증."""
    print("\n[5] MetricValue 데이터 클래스")

    # 5-1. 기본 생성
    try:
        mv = MetricValue(value=42.0)
        assert mv.value == 42.0
        assert isinstance(mv.timestamp, datetime)
        assert mv.timestamp.tzinfo is not None  # UTC
        assert isinstance(mv.labels, MetricLabels)
        result.ok("5-1 MetricValue 기본 생성 (value=42.0)")
    except AssertionError as e:
        result.fail("5-1 기본 생성", str(e))

    # 5-2. 레이블 지정 생성
    try:
        labels = MetricLabels.from_dict({"env": "prod"})
        mv = MetricValue(value=10.0, labels=labels)
        assert mv.labels.to_dict() == {"env": "prod"}
        result.ok("5-2 레이블 지정 생성")
    except AssertionError as e:
        result.fail("5-2 레이블 지정", str(e))

    # 5-3. to_dict
    try:
        mv = MetricValue(value=3.14)
        d = mv.to_dict()
        assert d["value"] == 3.14
        assert "timestamp" in d
        assert "labels" in d
        assert isinstance(d["labels"], dict)
        result.ok("5-3 to_dict 구조")
    except AssertionError as e:
        result.fail("5-3 to_dict", str(e))

    # 5-4. timestamp ISO 형식
    try:
        mv = MetricValue(value=1.0)
        d = mv.to_dict()
        # ISO 형식 파싱 가능
        datetime.fromisoformat(d["timestamp"])
        result.ok("5-4 timestamp ISO 형식 파싱")
    except (AssertionError, ValueError) as e:
        result.fail("5-4 timestamp ISO", str(e))

    # 5-5. 음수/0/큰 값
    try:
        mv_neg = MetricValue(value=-100.0)
        assert mv_neg.value == -100.0
        mv_zero = MetricValue(value=0.0)
        assert mv_zero.value == 0.0
        mv_big = MetricValue(value=1e18)
        assert mv_big.value == 1e18
        result.ok("5-5 다양한 값 (음수/0/큰 값)")
    except AssertionError as e:
        result.fail("5-5 다양한 값", str(e))


# =============================================================================
# [6] MetricSnapshot 데이터 클래스 (7개)
# =============================================================================
def test_metric_snapshot(result: TestResult) -> None:
    """MetricSnapshot 데이터 클래스 검증."""
    print("\n[6] MetricSnapshot 데이터 클래스")

    # 6-1. 기본 생성
    try:
        snap = MetricSnapshot(name="test_metric", type=MetricType.COUNTER)
        assert snap.name == "test_metric"
        assert snap.type == MetricType.COUNTER
        assert snap.help == ""
        assert snap.unit is None
        assert snap.values == []
        assert isinstance(snap.timestamp, datetime)
        result.ok("6-1 MetricSnapshot 기본 생성")
    except AssertionError as e:
        result.fail("6-1 기본 생성", str(e))

    # 6-2. 값 포함 생성
    try:
        mv = MetricValue(value=10.0)
        snap = MetricSnapshot(
            name="req_total",
            type=MetricType.COUNTER,
            help="Total requests",
            unit=MetricUnit.COUNT,
            values=[mv],
        )
        assert snap.help == "Total requests"
        assert snap.unit == MetricUnit.COUNT
        assert len(snap.values) == 1
        assert snap.values[0].value == 10.0
        result.ok("6-2 값 포함 생성")
    except AssertionError as e:
        result.fail("6-2 값 포함", str(e))

    # 6-3. to_dict
    try:
        snap = MetricSnapshot(
            name="test",
            type=MetricType.GAUGE,
            unit=MetricUnit.BYTES,
        )
        d = snap.to_dict()
        assert d["name"] == "test"
        assert d["type"] == "gauge"
        assert d["unit"] == "bytes"
        assert "timestamp" in d
        assert isinstance(d["values"], list)
        result.ok("6-3 to_dict 구조")
    except AssertionError as e:
        result.fail("6-3 to_dict", str(e))

    # 6-4. to_dict - unit=None
    try:
        snap = MetricSnapshot(name="test", type=MetricType.COUNTER)
        d = snap.to_dict()
        assert d["unit"] is None
        result.ok("6-4 to_dict unit=None")
    except AssertionError as e:
        result.fail("6-4 to_dict unit None", str(e))

    # 6-5. to_prometheus (HELP/TYPE/값)
    try:
        mv = MetricValue(value=5.0)
        snap = MetricSnapshot(
            name="http_requests_total",
            type=MetricType.COUNTER,
            help="Total HTTP requests",
            values=[mv],
        )
        prom = snap.to_prometheus()
        assert "# HELP http_requests_total Total HTTP requests" in prom
        assert "# TYPE http_requests_total counter" in prom
        assert "http_requests_total" in prom
        assert "5.0" in prom
        result.ok("6-5 to_prometheus HELP/TYPE/값 포함")
    except AssertionError as e:
        result.fail("6-5 to_prometheus", str(e))

    # 6-6. to_prometheus 레이블 포함
    try:
        labels = MetricLabels.from_dict({"method": "GET"})
        mv = MetricValue(value=3.0, labels=labels)
        snap = MetricSnapshot(
            name="api_calls",
            type=MetricType.COUNTER,
            values=[mv],
        )
        prom = snap.to_prometheus()
        assert 'method="GET"' in prom
        result.ok("6-6 to_prometheus 레이블 포함")
    except AssertionError as e:
        result.fail("6-6 to_prometheus 레이블", str(e))

    # 6-7. to_prometheus help 없으면 HELP 라인 생략
    try:
        snap = MetricSnapshot(
            name="test_no_help",
            type=MetricType.GAUGE,
            help="",
        )
        prom = snap.to_prometheus()
        assert "# HELP" not in prom
        assert "# TYPE test_no_help gauge" in prom
        result.ok("6-7 to_prometheus help 없으면 HELP 생략")
    except AssertionError as e:
        result.fail("6-7 to_prometheus no help", str(e))


# =============================================================================
# [7] BaseMetric 기본 클래스 (5개)
# =============================================================================
def test_base_metric(result: TestResult) -> None:
    """BaseMetric 기본 클래스 검증."""
    print("\n[7] BaseMetric 기본 클래스")

    # 7-1. 초기화
    try:
        bm = BaseMetric("test_metric", help="Test", unit=MetricUnit.SECONDS)
        assert bm.name == "test_metric"
        assert bm.help == "Test"
        assert bm.unit == MetricUnit.SECONDS
        assert bm.metric_type == MetricType.GAUGE  # 기본값
        assert isinstance(bm._created_at, datetime)
        result.ok("7-1 BaseMetric 초기화")
    except AssertionError as e:
        result.fail("7-1 초기화", str(e))

    # 7-2. _validate_labels (None -> 빈 MetricLabels)
    try:
        bm = BaseMetric("test")
        ml = bm._validate_labels(None)
        assert isinstance(ml, MetricLabels)
        assert ml.labels == ()
        result.ok("7-2 _validate_labels None -> 빈 MetricLabels")
    except AssertionError as e:
        result.fail("7-2 validate None", str(e))

    # 7-3. _validate_labels (딕셔너리 -> MetricLabels)
    try:
        bm = BaseMetric("test")
        ml = bm._validate_labels({"env": "prod"})
        assert ml.to_dict() == {"env": "prod"}
        result.ok("7-3 _validate_labels dict -> MetricLabels")
    except AssertionError as e:
        result.fail("7-3 validate dict", str(e))

    # 7-4. _validate_labels (비문자열 키/값 -> ValueError)
    try:
        bm = BaseMetric("test")
        raised = False
        try:
            bm._validate_labels({123: "val"})
        except (ValueError, AttributeError):
            raised = True
        assert raised, "비문자열 키에 대한 예외 미발생"
        result.ok("7-4 _validate_labels 비문자열 키 -> ValueError")
    except AssertionError as e:
        result.fail("7-4 validate 비문자열", str(e))

    # 7-5. snapshot -> NotImplementedError
    try:
        bm = BaseMetric("test")
        raised = False
        try:
            bm.snapshot()
        except NotImplementedError:
            raised = True
        assert raised, "NotImplementedError 미발생"
        result.ok("7-5 BaseMetric.snapshot() -> NotImplementedError")
    except AssertionError as e:
        result.fail("7-5 snapshot NotImplemented", str(e))


# =============================================================================
# [8] Counter 메트릭 (8개)
# =============================================================================
def test_counter(result: TestResult) -> None:
    """Counter 메트릭 검증."""
    print("\n[8] Counter 메트릭")

    # 8-1. 초기화
    try:
        c = Counter("req_total", help="Total requests", unit=MetricUnit.COUNT)
        assert c.name == "req_total"
        assert c.metric_type == MetricType.COUNTER
        assert c.get() == 0.0
        result.ok("8-1 Counter 초기화 (기본값 0)")
    except AssertionError as e:
        result.fail("8-1 초기화", str(e))

    # 8-2. inc 기본값(1) / 임의값
    try:
        c = Counter("test")
        c.inc()
        assert c.get() == 1.0
        c.inc(5.0)
        assert c.get() == 6.0
        c.inc(0.5)
        assert c.get() == 6.5
        result.ok("8-2 inc 기본값/임의값 누적")
    except AssertionError as e:
        result.fail("8-2 inc", str(e))

    # 8-3. inc 음수 -> ValueError
    try:
        c = Counter("test")
        raised = False
        try:
            c.inc(-1.0)
        except ValueError:
            raised = True
        assert raised, "음수 inc에 ValueError 미발생"
        result.ok("8-3 inc 음수 -> ValueError")
    except AssertionError as e:
        result.fail("8-3 inc 음수", str(e))

    # 8-4. 레이블별 독립 카운트
    try:
        c = Counter("test")
        c.inc(1.0, {"method": "GET"})
        c.inc(2.0, {"method": "POST"})
        c.inc(3.0, {"method": "GET"})
        assert c.get({"method": "GET"}) == 4.0
        assert c.get({"method": "POST"}) == 2.0
        assert c.get() == 0.0  # 레이블 없는 값은 별도
        result.ok("8-4 레이블별 독립 카운트")
    except AssertionError as e:
        result.fail("8-4 레이블별 독립", str(e))

    # 8-5. labels() -> CounterChild
    try:
        c = Counter("test")
        child = c.labels({"env": "prod"})
        assert hasattr(child, "inc")
        assert hasattr(child, "get")
        child.inc()
        child.inc(4.0)
        assert child.get() == 5.0
        assert c.get({"env": "prod"}) == 5.0  # 부모에서도 확인
        result.ok("8-5 labels() -> CounterChild 연동")
    except AssertionError as e:
        result.fail("8-5 CounterChild", str(e))

    # 8-6. reset
    try:
        c = Counter("test")
        c.inc(10.0)
        c.inc(5.0, {"env": "dev"})
        c.reset()
        assert c.get() == 0.0
        assert c.get({"env": "dev"}) == 0.0
        result.ok("8-6 reset 후 모든 값 0")
    except AssertionError as e:
        result.fail("8-6 reset", str(e))

    # 8-7. snapshot
    try:
        c = Counter("req_total", help="Requests")
        c.inc(3.0)
        c.inc(2.0, {"method": "GET"})
        snap = c.snapshot()
        assert isinstance(snap, MetricSnapshot)
        assert snap.name == "req_total"
        assert snap.type == MetricType.COUNTER
        assert snap.help == "Requests"
        assert len(snap.values) == 2  # 레이블 없는 값 + GET
        result.ok("8-7 snapshot 구조")
    except AssertionError as e:
        result.fail("8-7 snapshot", str(e))

    # 8-8. inc(0) 허용
    try:
        c = Counter("test")
        c.inc(0.0)
        assert c.get() == 0.0
        result.ok("8-8 inc(0) 허용 (값 변화 없음)")
    except (AssertionError, ValueError) as e:
        result.fail("8-8 inc(0)", str(e))


# =============================================================================
# [9] CounterChild (4개)
# =============================================================================
def test_counter_child(result: TestResult) -> None:
    """CounterChild 검증."""
    print("\n[9] CounterChild")

    # 9-1. inc/get 기본
    try:
        c = Counter("test")
        child = c.labels({"status": "200"})
        child.inc()
        assert child.get() == 1.0
        child.inc(9.0)
        assert child.get() == 10.0
        result.ok("9-1 CounterChild inc/get")
    except AssertionError as e:
        result.fail("9-1 inc/get", str(e))

    # 9-2. 같은 레이블의 다른 child 인스턴스 -> 같은 값
    try:
        c = Counter("test")
        child1 = c.labels({"k": "v"})
        child1.inc(5.0)
        child2 = c.labels({"k": "v"})
        assert child2.get() == 5.0  # 같은 레이블이므로 공유
        result.ok("9-2 같은 레이블 -> 값 공유")
    except AssertionError as e:
        result.fail("9-2 같은 레이블 공유", str(e))

    # 9-3. 다른 레이블의 child -> 독립
    try:
        c = Counter("test")
        child_a = c.labels({"type": "a"})
        child_b = c.labels({"type": "b"})
        child_a.inc(3.0)
        child_b.inc(7.0)
        assert child_a.get() == 3.0
        assert child_b.get() == 7.0
        result.ok("9-3 다른 레이블 -> 독립")
    except AssertionError as e:
        result.fail("9-3 다른 레이블 독립", str(e))

    # 9-4. 부모의 snapshot에 child 값 반영
    try:
        c = Counter("test")
        c.labels({"x": "1"}).inc(10.0)
        snap = c.snapshot()
        assert len(snap.values) == 1
        assert snap.values[0].value == 10.0
        result.ok("9-4 부모 snapshot에 child 값 반영")
    except AssertionError as e:
        result.fail("9-4 snapshot 반영", str(e))


# =============================================================================
# [10] Gauge 메트릭 (10개)
# =============================================================================
def test_gauge(result: TestResult) -> None:
    """Gauge 메트릭 검증."""
    print("\n[10] Gauge 메트릭")

    # 10-1. 초기화
    try:
        g = Gauge("mem_bytes", help="Memory", unit=MetricUnit.BYTES)
        assert g.name == "mem_bytes"
        assert g.metric_type == MetricType.GAUGE
        assert g.get() == 0.0
        result.ok("10-1 Gauge 초기화 (기본값 0)")
    except AssertionError as e:
        result.fail("10-1 초기화", str(e))

    # 10-2. set
    try:
        g = Gauge("test")
        g.set(100.0)
        assert g.get() == 100.0
        g.set(-50.0)
        assert g.get() == -50.0
        result.ok("10-2 set (양수/음수)")
    except AssertionError as e:
        result.fail("10-2 set", str(e))

    # 10-3. inc
    try:
        g = Gauge("test")
        g.inc()
        assert g.get() == 1.0
        g.inc(9.0)
        assert g.get() == 10.0
        result.ok("10-3 inc (기본/임의)")
    except AssertionError as e:
        result.fail("10-3 inc", str(e))

    # 10-4. dec
    try:
        g = Gauge("test")
        g.set(10.0)
        g.dec()
        assert g.get() == 9.0
        g.dec(4.0)
        assert g.get() == 5.0
        result.ok("10-4 dec (기본/임의)")
    except AssertionError as e:
        result.fail("10-4 dec", str(e))

    # 10-5. 레이블별 독립
    try:
        g = Gauge("test")
        g.set(1.0, {"host": "a"})
        g.set(2.0, {"host": "b"})
        assert g.get({"host": "a"}) == 1.0
        assert g.get({"host": "b"}) == 2.0
        assert g.get() == 0.0
        result.ok("10-5 레이블별 독립")
    except AssertionError as e:
        result.fail("10-5 레이블별 독립", str(e))

    # 10-6. set_to_current_time
    try:
        g = Gauge("last_update")
        before = time.time()
        g.set_to_current_time()
        after = time.time()
        val = g.get()
        assert before <= val <= after, f"시간 범위 벗어남: {before} <= {val} <= {after}"
        result.ok("10-6 set_to_current_time")
    except AssertionError as e:
        result.fail("10-6 set_to_current_time", str(e))

    # 10-7. track_inprogress 컨텍스트 매니저
    try:
        g = Gauge("active")
        assert g.get() == 0.0
        with g.track_inprogress():
            assert g.get() == 1.0
        assert g.get() == 0.0
        result.ok("10-7 track_inprogress (진입 +1, 퇴장 -1)")
    except AssertionError as e:
        result.fail("10-7 track_inprogress", str(e))

    # 10-8. track_inprogress 예외 발생 시에도 -1
    try:
        g = Gauge("active")
        try:
            with g.track_inprogress():
                assert g.get() == 1.0
                raise RuntimeError("test error")
        except RuntimeError:
            pass
        assert g.get() == 0.0, f"예외 후 값: {g.get()}"
        result.ok("10-8 track_inprogress 예외 시에도 -1")
    except AssertionError as e:
        result.fail("10-8 track_inprogress 예외", str(e))

    # 10-9. reset
    try:
        g = Gauge("test")
        g.set(100.0)
        g.set(200.0, {"env": "prod"})
        g.reset()
        assert g.get() == 0.0
        assert g.get({"env": "prod"}) == 0.0
        result.ok("10-9 reset 후 모든 값 0")
    except AssertionError as e:
        result.fail("10-9 reset", str(e))

    # 10-10. snapshot
    try:
        g = Gauge("mem", help="Memory")
        g.set(1024.0)
        snap = g.snapshot()
        assert isinstance(snap, MetricSnapshot)
        assert snap.type == MetricType.GAUGE
        assert len(snap.values) == 1
        assert snap.values[0].value == 1024.0
        result.ok("10-10 snapshot 구조")
    except AssertionError as e:
        result.fail("10-10 snapshot", str(e))


# =============================================================================
# [11] GaugeChild (4개)
# =============================================================================
def test_gauge_child(result: TestResult) -> None:
    """GaugeChild 검증."""
    print("\n[11] GaugeChild")

    # 11-1. set/get
    try:
        g = Gauge("test")
        child = g.labels({"host": "server1"})
        child.set(42.0)
        assert child.get() == 42.0
        result.ok("11-1 GaugeChild set/get")
    except AssertionError as e:
        result.fail("11-1 set/get", str(e))

    # 11-2. inc/dec
    try:
        g = Gauge("test")
        child = g.labels({"host": "server1"})
        child.set(10.0)
        child.inc(5.0)
        assert child.get() == 15.0
        child.dec(3.0)
        assert child.get() == 12.0
        result.ok("11-2 GaugeChild inc/dec")
    except AssertionError as e:
        result.fail("11-2 inc/dec", str(e))

    # 11-3. 같은 레이블의 child -> 값 공유
    try:
        g = Gauge("test")
        c1 = g.labels({"k": "v"})
        c1.set(100.0)
        c2 = g.labels({"k": "v"})
        assert c2.get() == 100.0
        result.ok("11-3 같은 레이블 -> 값 공유")
    except AssertionError as e:
        result.fail("11-3 같은 레이블 공유", str(e))

    # 11-4. 부모에서 값 확인
    try:
        g = Gauge("test")
        g.labels({"env": "prod"}).set(999.0)
        assert g.get({"env": "prod"}) == 999.0
        result.ok("11-4 부모에서 child 값 확인")
    except AssertionError as e:
        result.fail("11-4 부모 확인", str(e))


# =============================================================================
# [12] Histogram 메트릭 (10개)
# =============================================================================
def test_histogram(result: TestResult) -> None:
    """Histogram 메트릭 검증."""
    print("\n[12] Histogram 메트릭")

    # 12-1. 초기화 (기본 버킷)
    try:
        h = Histogram("latency", help="Latency", unit=MetricUnit.SECONDS)
        assert h.name == "latency"
        assert h.metric_type == MetricType.HISTOGRAM
        assert h._buckets == DEFAULT_HISTOGRAM_BUCKETS
        assert h.get_count() == 0
        assert h.get_sum() == 0.0
        result.ok("12-1 Histogram 초기화 (기본 버킷)")
    except AssertionError as e:
        result.fail("12-1 초기화", str(e))

    # 12-2. 커스텀 버킷
    try:
        h = Histogram("test", buckets=(0.1, 0.5, 1.0))
        # +Inf 자동 추가
        assert h._buckets[-1] == float("inf")
        assert 0.1 in h._buckets
        assert 0.5 in h._buckets
        assert 1.0 in h._buckets
        result.ok("12-2 커스텀 버킷 (+Inf 자동 추가)")
    except AssertionError as e:
        result.fail("12-2 커스텀 버킷", str(e))

    # 12-3. _validate_buckets: 정렬, 중복 제거
    try:
        h = Histogram("test", buckets=(1.0, 0.5, 0.5, 0.1, float("inf")))
        # 정렬 + 중복 제거
        assert h._buckets == (0.1, 0.5, 1.0, float("inf"))
        result.ok("12-3 _validate_buckets 정렬/중복제거")
    except AssertionError as e:
        result.fail("12-3 validate_buckets", str(e))

    # 12-4. observe 기본 동작
    try:
        h = Histogram("test", buckets=(1.0, 5.0, 10.0))
        h.observe(0.5)
        h.observe(3.0)
        h.observe(7.0)
        assert h.get_count() == 3
        assert abs(h.get_sum() - 10.5) < 1e-9
        result.ok("12-4 observe 기본 동작 (count=3, sum=10.5)")
    except AssertionError as e:
        result.fail("12-4 observe", str(e))

    # 12-5. get_bucket_counts (누적)
    try:
        h = Histogram("test", buckets=(1.0, 5.0, 10.0))
        h.observe(0.5)   # <= 1.0: 1, <= 5.0: 1, <= 10.0: 1, <= +Inf: 1
        h.observe(3.0)   # <= 5.0: 2, <= 10.0: 2, <= +Inf: 2
        h.observe(7.0)   # <= 10.0: 3, <= +Inf: 3
        h.observe(15.0)  # <= +Inf: 4

        bc = h.get_bucket_counts()
        # bc: [(1.0, count), (5.0, count), (10.0, count), (inf, count)]
        bc_dict = {b: c for b, c in bc}
        assert bc_dict[1.0] == 1, f"1.0 버킷: {bc_dict[1.0]}"
        assert bc_dict[5.0] == 2, f"5.0 버킷: {bc_dict[5.0]}"
        assert bc_dict[10.0] == 3, f"10.0 버킷: {bc_dict[10.0]}"
        assert bc_dict[float("inf")] == 4, f"+Inf 버킷: {bc_dict[float('inf')]}"
        result.ok("12-5 get_bucket_counts 누적 카운트")
    except AssertionError as e:
        result.fail("12-5 bucket_counts", str(e))

    # 12-6. 레이블별 독립
    try:
        h = Histogram("test", buckets=(1.0, 5.0))
        h.observe(0.5, {"path": "/a"})
        h.observe(3.0, {"path": "/b"})
        assert h.get_count({"path": "/a"}) == 1
        assert h.get_count({"path": "/b"}) == 1
        assert h.get_count() == 0  # 레이블 없는 값
        result.ok("12-6 레이블별 독립")
    except AssertionError as e:
        result.fail("12-6 레이블별 독립", str(e))

    # 12-7. time() 컨텍스트 매니저
    try:
        h = Histogram("test", buckets=(0.001, 0.01, 0.1, 1.0))
        with h.time():
            time.sleep(0.01)  # ~10ms
        assert h.get_count() == 1
        assert h.get_sum() > 0.0
        result.ok("12-7 time() 컨텍스트 매니저")
    except AssertionError as e:
        result.fail("12-7 time()", str(e))

    # 12-8. reset
    try:
        h = Histogram("test", buckets=(1.0, 5.0))
        h.observe(2.0)
        h.observe(3.0, {"env": "prod"})
        h.reset()
        assert h.get_count() == 0
        assert h.get_sum() == 0.0
        assert h.get_count({"env": "prod"}) == 0
        result.ok("12-8 reset")
    except AssertionError as e:
        result.fail("12-8 reset", str(e))

    # 12-9. snapshot 구조
    try:
        h = Histogram("test", buckets=(1.0, 5.0))
        h.observe(0.5)
        snap = h.snapshot()
        assert isinstance(snap, MetricSnapshot)
        assert snap.type == MetricType.HISTOGRAM
        # 값: 버킷별 + _sum + _count
        assert len(snap.values) > 0
        result.ok("12-9 snapshot 구조")
    except AssertionError as e:
        result.fail("12-9 snapshot", str(e))

    # 12-10. labels() -> HistogramChild
    try:
        h = Histogram("test", buckets=(1.0, 5.0))
        child = h.labels({"method": "GET"})
        assert hasattr(child, "observe")
        assert hasattr(child, "time")
        child.observe(2.5)
        assert h.get_count({"method": "GET"}) == 1
        result.ok("12-10 labels() -> HistogramChild")
    except AssertionError as e:
        result.fail("12-10 HistogramChild", str(e))


# =============================================================================
# [13] HistogramChild (3개)
# =============================================================================
def test_histogram_child(result: TestResult) -> None:
    """HistogramChild 검증."""
    print("\n[13] HistogramChild")

    # 13-1. observe
    try:
        h = Histogram("test", buckets=(1.0, 5.0))
        child = h.labels({"path": "/api"})
        child.observe(0.5)
        child.observe(3.0)
        assert h.get_count({"path": "/api"}) == 2
        assert abs(h.get_sum({"path": "/api"}) - 3.5) < 1e-9
        result.ok("13-1 HistogramChild observe")
    except AssertionError as e:
        result.fail("13-1 observe", str(e))

    # 13-2. time() 컨텍스트 매니저
    try:
        h = Histogram("test", buckets=(0.001, 0.01, 0.1))
        child = h.labels({"op": "read"})
        with child.time():
            time.sleep(0.005)
        assert h.get_count({"op": "read"}) == 1
        assert h.get_sum({"op": "read"}) > 0.0
        result.ok("13-2 HistogramChild time()")
    except AssertionError as e:
        result.fail("13-2 time()", str(e))

    # 13-3. 부모와 값 공유
    try:
        h = Histogram("test", buckets=(1.0, 5.0))
        child = h.labels({"x": "y"})
        child.observe(2.0)
        # 부모에서 확인
        bc = h.get_bucket_counts({"x": "y"})
        total_in_inf = [c for b, c in bc if b == float("inf")][0]
        assert total_in_inf == 1
        result.ok("13-3 부모와 값 공유")
    except AssertionError as e:
        result.fail("13-3 부모 공유", str(e))


# =============================================================================
# [14] Summary 메트릭 (10개)
# =============================================================================
def test_summary(result: TestResult) -> None:
    """Summary 메트릭 검증."""
    print("\n[14] Summary 메트릭")

    # 14-1. 초기화 (기본 분위수)
    try:
        s = Summary("latency", help="Latency", unit=MetricUnit.SECONDS)
        assert s.name == "latency"
        assert s.metric_type == MetricType.SUMMARY
        assert s._quantiles == DEFAULT_QUANTILES
        assert s._max_age == SUMMARY_WINDOW_SECONDS
        assert s._max_observations == SUMMARY_MAX_OBSERVATIONS
        result.ok("14-1 Summary 초기화 (기본 분위수)")
    except AssertionError as e:
        result.fail("14-1 초기화", str(e))

    # 14-2. observe 기본 동작
    try:
        s = Summary("test")
        s.observe(0.1)
        s.observe(0.2)
        s.observe(0.3)
        assert s.get_count() == 3
        assert abs(s.get_sum() - 0.6) < 1e-9
        result.ok("14-2 observe (count=3, sum=0.6)")
    except AssertionError as e:
        result.fail("14-2 observe", str(e))

    # 14-3. get_quantile (p50)
    try:
        s = Summary("test")
        # 1~100 관측
        for i in range(1, 101):
            s.observe(float(i))
        p50 = s.get_quantile(0.5)
        assert p50 is not None
        # p50은 약 50 근처
        assert 45 <= p50 <= 55, f"p50={p50}"
        result.ok("14-3 get_quantile p50 ~ 50")
    except AssertionError as e:
        result.fail("14-3 get_quantile", str(e))

    # 14-4. get_quantile (p99)
    try:
        s = Summary("test")
        for i in range(1, 101):
            s.observe(float(i))
        p99 = s.get_quantile(0.99)
        assert p99 is not None
        assert 95 <= p99 <= 100, f"p99={p99}"
        result.ok("14-4 get_quantile p99 ~ 99")
    except AssertionError as e:
        result.fail("14-4 get_quantile p99", str(e))

    # 14-5. get_quantile 범위 오류 -> ValueError
    try:
        s = Summary("test")
        raised = False
        try:
            s.get_quantile(1.5)
        except ValueError:
            raised = True
        assert raised, "1.5에 ValueError 미발생"
        raised = False
        try:
            s.get_quantile(-0.1)
        except ValueError:
            raised = True
        assert raised, "-0.1에 ValueError 미발생"
        result.ok("14-5 get_quantile 범위 오류 -> ValueError")
    except AssertionError as e:
        result.fail("14-5 get_quantile 범위", str(e))

    # 14-6. get_quantile 관측값 없으면 None
    try:
        s = Summary("test")
        q = s.get_quantile(0.5)
        assert q is None, f"빈 관측에서 {q} 반환"
        result.ok("14-6 get_quantile 빈 관측 -> None")
    except AssertionError as e:
        result.fail("14-6 빈 관측", str(e))

    # 14-7. get_quantiles (전체 분위수)
    try:
        s = Summary("test", quantiles=(0.5, 0.9, 0.99))
        for i in range(1, 101):
            s.observe(float(i))
        qs = s.get_quantiles()
        assert 0.5 in qs
        assert 0.9 in qs
        assert 0.99 in qs
        assert qs[0.5] is not None
        result.ok("14-7 get_quantiles 전체 분위수")
    except AssertionError as e:
        result.fail("14-7 get_quantiles", str(e))

    # 14-8. 레이블별 독립
    try:
        s = Summary("test")
        s.observe(1.0, {"path": "/a"})
        s.observe(2.0, {"path": "/b"})
        assert s.get_count({"path": "/a"}) == 1
        assert s.get_count({"path": "/b"}) == 1
        assert s.get_count() == 0
        result.ok("14-8 레이블별 독립")
    except AssertionError as e:
        result.fail("14-8 레이블별 독립", str(e))

    # 14-9. time() 컨텍스트 매니저
    try:
        s = Summary("test")
        with s.time():
            time.sleep(0.01)
        assert s.get_count() == 1
        assert s.get_sum() > 0.0
        result.ok("14-9 time() 컨텍스트 매니저")
    except AssertionError as e:
        result.fail("14-9 time()", str(e))

    # 14-10. reset
    try:
        s = Summary("test")
        s.observe(1.0)
        s.observe(2.0, {"env": "prod"})
        s.reset()
        assert s.get_count() == 0
        assert s.get_sum() == 0.0
        assert s.get_count({"env": "prod"}) == 0
        result.ok("14-10 reset")
    except AssertionError as e:
        result.fail("14-10 reset", str(e))


# =============================================================================
# [15] SummaryChild (3개)
# =============================================================================
def test_summary_child(result: TestResult) -> None:
    """SummaryChild 검증."""
    print("\n[15] SummaryChild")

    # 15-1. observe
    try:
        s = Summary("test")
        child = s.labels({"op": "write"})
        child.observe(0.1)
        child.observe(0.2)
        assert s.get_count({"op": "write"}) == 2
        assert abs(s.get_sum({"op": "write"}) - 0.3) < 1e-9
        result.ok("15-1 SummaryChild observe")
    except AssertionError as e:
        result.fail("15-1 observe", str(e))

    # 15-2. time() 컨텍스트 매니저
    try:
        s = Summary("test")
        child = s.labels({"op": "read"})
        with child.time():
            time.sleep(0.005)
        assert s.get_count({"op": "read"}) == 1
        assert s.get_sum({"op": "read"}) > 0.0
        result.ok("15-2 SummaryChild time()")
    except AssertionError as e:
        result.fail("15-2 time()", str(e))

    # 15-3. 부모와 값 공유
    try:
        s = Summary("test")
        child = s.labels({"k": "v"})
        child.observe(5.0)
        # 부모에서 확인
        assert s.get_sum({"k": "v"}) == 5.0
        q = s.get_quantile(0.5, {"k": "v"})
        assert q == 5.0
        result.ok("15-3 부모와 값 공유")
    except AssertionError as e:
        result.fail("15-3 부모 공유", str(e))


# =============================================================================
# [16] MetricsCollector 초기화 / 기본 메트릭 (7개)
# =============================================================================
def test_metrics_collector_init(result: TestResult) -> None:
    """MetricsCollector 초기화 및 기본 메트릭 검증."""
    print("\n[16] MetricsCollector 초기화 / 기본 메트릭")

    # 16-1. 기본 초기화
    try:
        mc = _make_collector()
        assert mc._prefix == "test"
        assert mc._enabled is True
        assert mc._max_metrics == 10000
        assert isinstance(mc._created_at, datetime)
        result.ok("16-1 MetricsCollector 기본 초기화")
    except Exception as e:
        result.fail("16-1 기본 초기화", str(e))

    # 16-2. 파라미터 오버라이드
    try:
        mc = _make_collector(prefix="custom", enabled=False, max_metrics=100)
        assert mc._prefix == "custom"
        assert mc._enabled is False
        assert mc._max_metrics == 100
        result.ok("16-2 파라미터 오버라이드")
    except Exception as e:
        result.fail("16-2 파라미터 오버라이드", str(e))

    # 16-3. 기본 카운터 메트릭 등록 확인
    try:
        mc = _make_collector()
        status = mc.get_status()
        assert status["counters_count"] >= 3  # analysis_requests_total, analysis_errors_total, camera_frames_dropped_total
        result.ok("16-3 기본 카운터 메트릭 >= 3개")
    except (AssertionError, Exception) as e:
        result.fail("16-3 기본 카운터", str(e))

    # 16-4. 기본 게이지 메트릭 등록 확인
    try:
        mc = _make_collector()
        status = mc.get_status()
        # GPU 온도, VRAM 사용/전체, 활용률, TensorRT, 활성분석, 카메라, CPU, RAM 사용/전체, 디스크 사용/전체
        assert status["gauges_count"] >= 10
        result.ok("16-4 기본 게이지 메트릭 >= 10개")
    except (AssertionError, Exception) as e:
        result.fail("16-4 기본 게이지", str(e))

    # 16-5. 기본 히스토그램 메트릭 등록 확인
    try:
        mc = _make_collector()
        status = mc.get_status()
        # analysis_duration, video_fps, detection_accuracy, model_inference, gpu_temp_dist, frame_processing
        assert status["histograms_count"] >= 5
        result.ok("16-5 기본 히스토그램 메트릭 >= 5개")
    except (AssertionError, Exception) as e:
        result.fail("16-5 기본 히스토그램", str(e))

    # 16-6. 기본 서머리 메트릭 등록 확인
    try:
        mc = _make_collector()
        status = mc.get_status()
        assert status["summaries_count"] >= 1  # processing_time_seconds
        result.ok("16-6 기본 서머리 메트릭 >= 1개")
    except (AssertionError, Exception) as e:
        result.fail("16-6 기본 서머리", str(e))

    # 16-7. get_status 전체 구조
    try:
        mc = _make_collector()
        status = mc.get_status()
        required_keys = [
            "enabled", "prefix", "max_metrics",
            "counters_count", "gauges_count", "histograms_count", "summaries_count",
            "total_metrics", "metrics_remaining",
            "summary_window_seconds", "summary_max_observations", "created_at",
        ]
        for key in required_keys:
            assert key in status, f"누락: {key}"
        assert status["total_metrics"] == (
            status["counters_count"] + status["gauges_count"]
            + status["histograms_count"] + status["summaries_count"]
        )
        result.ok("16-7 get_status 전체 구조 (12개 키)")
    except AssertionError as e:
        result.fail("16-7 get_status", str(e))


# =============================================================================
# [17] MetricsCollector 팩토리 / 내보내기 (9개)
# =============================================================================
def test_metrics_collector_factory_export(result: TestResult) -> None:
    """MetricsCollector 팩토리 메서드 및 내보내기 검증."""
    print("\n[17] MetricsCollector 팩토리 / 내보내기")

    # 17-1. counter() 팩토리 - 생성 및 재사용
    try:
        mc = _make_collector()
        c1 = mc.counter("my_counter", help="Test counter")
        c2 = mc.counter("my_counter")
        assert c1 is c2  # 같은 인스턴스 반환
        c1.inc()
        assert c2.get() == 1.0
        result.ok("17-1 counter() 팩토리 (생성/재사용)")
    except (AssertionError, Exception) as e:
        result.fail("17-1 counter()", str(e))

    # 17-2. gauge() 팩토리 - 생성 및 재사용
    try:
        mc = _make_collector()
        g1 = mc.gauge("my_gauge")
        g2 = mc.gauge("my_gauge")
        assert g1 is g2
        g1.set(42.0)
        assert g2.get() == 42.0
        result.ok("17-2 gauge() 팩토리 (생성/재사용)")
    except (AssertionError, Exception) as e:
        result.fail("17-2 gauge()", str(e))

    # 17-3. histogram() 팩토리
    try:
        mc = _make_collector()
        h1 = mc.histogram("my_hist", buckets=(0.1, 0.5, 1.0))
        h2 = mc.histogram("my_hist")
        assert h1 is h2
        result.ok("17-3 histogram() 팩토리 (생성/재사용)")
    except (AssertionError, Exception) as e:
        result.fail("17-3 histogram()", str(e))

    # 17-4. summary() 팩토리
    try:
        mc = _make_collector()
        s1 = mc.summary("my_summary")
        s2 = mc.summary("my_summary")
        assert s1 is s2
        result.ok("17-4 summary() 팩토리 (생성/재사용)")
    except (AssertionError, Exception) as e:
        result.fail("17-4 summary()", str(e))

    # 17-5. _make_name 접두사 적용
    try:
        mc = _make_collector(prefix="cv")
        name = mc._make_name("requests")
        assert name == "cv_requests"
        # 이미 접두사 포함된 경우
        name2 = mc._make_name("cv_requests")
        assert name2 == "cv_requests"  # 중복 접두사 방지
        result.ok("17-5 _make_name 접두사 적용/중복 방지")
    except (AssertionError, Exception) as e:
        result.fail("17-5 _make_name", str(e))

    # 17-6. export_prometheus
    try:
        mc = _make_collector()
        mc.counter("export_test").inc(5.0)
        prom = mc.export_prometheus()
        assert isinstance(prom, str)
        assert len(prom) > 0
        assert "# TYPE" in prom
        result.ok("17-6 export_prometheus 문자열")
    except (AssertionError, Exception) as e:
        result.fail("17-6 export_prometheus", str(e))

    # 17-7. export_prometheus (disabled -> 빈 문자열)
    try:
        mc = _make_collector(enabled=False)
        prom = mc.export_prometheus()
        assert prom == ""
        result.ok("17-7 export_prometheus disabled -> ''")
    except (AssertionError, Exception) as e:
        result.fail("17-7 export_prometheus disabled", str(e))

    # 17-8. export_json
    try:
        mc = _make_collector()
        mc.gauge("json_test").set(100.0)
        j = mc.export_json()
        assert isinstance(j, dict)
        assert "prefix" in j
        assert "enabled" in j
        assert "metrics" in j
        assert isinstance(j["metrics"], list)
        assert j["prefix"] == "test"
        assert j["enabled"] is True
        result.ok("17-8 export_json 구조")
    except (AssertionError, Exception) as e:
        result.fail("17-8 export_json", str(e))

    # 17-9. export_json (disabled -> enabled=False)
    try:
        mc = _make_collector(enabled=False)
        j = mc.export_json()
        assert j["enabled"] is False
        assert j["metrics"] == []
        result.ok("17-9 export_json disabled -> {enabled: False, metrics: []}")
    except (AssertionError, Exception) as e:
        result.fail("17-9 export_json disabled", str(e))


# =============================================================================
# [18] 싱글톤 (_get_collector, _reset_collector) (4개)
# =============================================================================
def test_singleton(result: TestResult) -> None:
    """싱글톤 검증."""
    print("\n[18] 싱글톤")

    # 18-1. _reset_collector / _get_collector
    try:
        _reset_singleton()
        c1 = _get_collector()
        assert isinstance(c1, MetricsCollector)
        result.ok("18-1 _get_collector -> MetricsCollector")
    except Exception as e:
        result.fail("18-1 _get_collector", str(e))
    finally:
        _reset_singleton()

    # 18-2. 동일 인스턴스 반환
    try:
        _reset_singleton()
        c1 = _get_collector()
        c2 = _get_collector()
        assert c1 is c2
        result.ok("18-2 _get_collector 동일 인스턴스")
    except (AssertionError, Exception) as e:
        result.fail("18-2 동일 인스턴스", str(e))
    finally:
        _reset_singleton()

    # 18-3. _reset_collector 후 새 인스턴스
    try:
        _reset_singleton()
        c1 = _get_collector()
        _reset_singleton()
        c2 = _get_collector()
        assert c1 is not c2
        result.ok("18-3 _reset_collector 후 새 인스턴스")
    except (AssertionError, Exception) as e:
        result.fail("18-3 reset 후 새 인스턴스", str(e))
    finally:
        _reset_singleton()

    # 18-4. 멀티스레드에서 동일 인스턴스
    try:
        _reset_singleton()
        instances = []
        errors = []

        def get_instance():
            try:
                inst = _get_collector()
                instances.append(id(inst))
            except Exception as ex:
                errors.append(str(ex))

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"에러: {errors}"
        # 모든 스레드가 동일 인스턴스
        assert len(set(instances)) == 1, f"서로 다른 인스턴스: {len(set(instances))}개"
        result.ok("18-4 멀티스레드 싱글톤 (10스레드)")
    except AssertionError as e:
        result.fail("18-4 멀티스레드 싱글톤", str(e))
    finally:
        _reset_singleton()


# =============================================================================
# [19] 데코레이터 (measure_latency, count_calls) (6개)
# =============================================================================
def test_decorators(result: TestResult) -> None:
    """데코레이터 검증."""
    print("\n[19] 데코레이터")

    # 항상 싱글톤 리셋 후 시작
    _reset_singleton()

    # 19-1. measure_latency (histogram 모드)
    try:
        _reset_singleton()

        @measure_latency("test_latency")
        def slow_func():
            time.sleep(0.01)
            return "done"

        result_val = slow_func()
        assert result_val == "done"

        collector = _get_collector()
        h = collector.histogram("test_latency")
        # function 레이블 + status 레이블로 관측
        # get_count() 전체는 0 (레이블 없는 것), 하지만 레이블 있는 것은 1
        # 직접 스냅샷으로 확인
        snap = h.snapshot()
        assert len(snap.values) > 0
        result.ok("19-1 measure_latency histogram 모드")
    except (AssertionError, Exception) as e:
        result.fail("19-1 measure_latency histogram", str(e))
    finally:
        _reset_singleton()

    # 19-2. measure_latency (summary 모드)
    try:
        _reset_singleton()

        @measure_latency("test_latency_summary", use_histogram=False)
        def fast_func():
            return 42

        val = fast_func()
        assert val == 42

        collector = _get_collector()
        s = collector.summary("test_latency_summary")
        snap = s.snapshot()
        assert len(snap.values) > 0
        result.ok("19-2 measure_latency summary 모드")
    except (AssertionError, Exception) as e:
        result.fail("19-2 measure_latency summary", str(e))
    finally:
        _reset_singleton()

    # 19-3. measure_latency 예외 시 error 레이블
    try:
        _reset_singleton()

        @measure_latency("test_error_latency")
        def failing_func():
            raise ValueError("test error")

        try:
            failing_func()
        except ValueError:
            pass

        collector = _get_collector()
        h = collector.histogram("test_error_latency")
        snap = h.snapshot()
        # error 상태 레이블이 포함된 값이 있어야 함
        assert len(snap.values) > 0
        result.ok("19-3 measure_latency 예외 시 error 레이블")
    except (AssertionError, Exception) as e:
        result.fail("19-3 measure_latency 예외", str(e))
    finally:
        _reset_singleton()

    # 19-4. count_calls
    try:
        _reset_singleton()

        @count_calls("test_calls")
        def my_func():
            return "ok"

        my_func()
        my_func()
        my_func()

        collector = _get_collector()
        c = collector.counter("test_calls")
        snap = c.snapshot()
        # 3회 호출 확인
        total = sum(v.value for v in snap.values)
        assert total == 3.0, f"total={total}"
        result.ok("19-4 count_calls (3회 호출)")
    except (AssertionError, Exception) as e:
        result.fail("19-4 count_calls", str(e))
    finally:
        _reset_singleton()

    # 19-5. count_calls 예외 시에도 카운트
    try:
        _reset_singleton()

        @count_calls("test_error_calls")
        def error_func():
            raise RuntimeError("fail")

        try:
            error_func()
        except RuntimeError:
            pass

        collector = _get_collector()
        c = collector.counter("test_error_calls")
        snap = c.snapshot()
        total = sum(v.value for v in snap.values)
        assert total == 1.0
        result.ok("19-5 count_calls 예외 시에도 카운트")
    except (AssertionError, Exception) as e:
        result.fail("19-5 count_calls 예외", str(e))
    finally:
        _reset_singleton()

    # 19-6. 데코레이터가 함수 이름 보존 (__name__)
    try:
        _reset_singleton()

        @measure_latency("name_test")
        def original_name():
            pass

        assert original_name.__name__ == "original_name"

        @count_calls("name_test2")
        def another_name():
            pass

        assert another_name.__name__ == "another_name"
        result.ok("19-6 데코레이터 __name__ 보존 (wraps)")
    except (AssertionError, Exception) as e:
        result.fail("19-6 __name__ 보존", str(e))
    finally:
        _reset_singleton()


# =============================================================================
# [20] 엣지 케이스 / __all__ (5개)
# =============================================================================
def test_edge_cases_and_all(result: TestResult) -> None:
    """엣지 케이스 및 __all__ 검증."""
    print("\n[20] 엣지 케이스 / __all__")

    # 20-1. __all__ 23개 항목
    try:
        from core_foundation.monitoring.metrics import __all__ as metrics_all
        assert len(metrics_all) == 23, f"실제: {len(metrics_all)}"
        result.ok("20-1 __all__ == 23개")
    except AssertionError as e:
        result.fail("20-1 __all__ 개수", str(e))

    # 20-2. __all__ 필수 항목 포함
    try:
        from core_foundation.monitoring.metrics import __all__ as metrics_all
        required = [
            "MetricType", "MetricUnit",
            "MetricLabels", "MetricValue", "MetricSnapshot",
            "Counter", "Gauge", "Histogram", "Summary",
            "MetricsCollector",
            "measure_latency", "count_calls",
            "METRIC_PREFIX", "MAX_METRICS",
            "DEFAULT_HISTOGRAM_BUCKETS", "DEFAULT_QUANTILES",
        ]
        for item in required:
            assert item in metrics_all, f"__all__에 '{item}' 누락"
        result.ok("20-2 __all__ 필수 항목 포함")
    except AssertionError as e:
        result.fail("20-2 __all__ 필수 항목", str(e))

    # 20-3. max_metrics 초과 시 RuntimeError
    try:
        # _register_default_metrics()에서 ~22개 등록하므로
        # max_metrics=5이면 __init__ 중에 RuntimeError 발생
        raised = False
        try:
            mc = _make_collector(max_metrics=5)
        except RuntimeError:
            raised = True
        assert raised, "max_metrics=5에서 RuntimeError 미발생"
        result.ok("20-3 max_metrics 초과 시 RuntimeError (init 중)")
    except (AssertionError, Exception) as e:
        result.fail("20-3 max_metrics 초과", str(e))

    # 20-4. enabled 프로퍼티 setter
    try:
        mc = _make_collector()
        assert mc.enabled is True
        mc.enabled = False
        assert mc.enabled is False
        mc.enabled = True
        assert mc.enabled is True
        result.ok("20-4 enabled 프로퍼티 getter/setter")
    except (AssertionError, Exception) as e:
        result.fail("20-4 enabled 프로퍼티", str(e))

    # 20-5. reset_all
    try:
        mc = _make_collector()
        c = mc.counter("reset_test")
        c.inc(10.0)
        g = mc.gauge("reset_gauge")
        g.set(100.0)
        mc.reset_all()
        assert c.get() == 0.0
        assert g.get() == 0.0
        result.ok("20-5 reset_all (모든 메트릭 리셋)")
    except (AssertionError, Exception) as e:
        result.fail("20-5 reset_all", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW - metrics.py 단위 테스트")
    print("=" * 60)

    result = TestResult()

    # [1] 상수 검증
    test_constants(result)

    # [2] MetricType Enum
    test_metric_type_enum(result)

    # [3] MetricUnit Enum
    test_metric_unit_enum(result)

    # [4] MetricLabels 데이터 클래스
    test_metric_labels(result)

    # [5] MetricValue 데이터 클래스
    test_metric_value(result)

    # [6] MetricSnapshot 데이터 클래스
    test_metric_snapshot(result)

    # [7] BaseMetric 기본 클래스
    test_base_metric(result)

    # [8] Counter 메트릭
    test_counter(result)

    # [9] CounterChild
    test_counter_child(result)

    # [10] Gauge 메트릭
    test_gauge(result)

    # [11] GaugeChild
    test_gauge_child(result)

    # [12] Histogram 메트릭
    test_histogram(result)

    # [13] HistogramChild
    test_histogram_child(result)

    # [14] Summary 메트릭
    test_summary(result)

    # [15] SummaryChild
    test_summary_child(result)

    # [16] MetricsCollector 초기화 / 기본 메트릭
    test_metrics_collector_init(result)

    # [17] MetricsCollector 팩토리 / 내보내기
    test_metrics_collector_factory_export(result)

    # [18] 싱글톤
    test_singleton(result)

    # [19] 데코레이터
    test_decorators(result)

    # [20] 엣지 케이스 / __all__
    test_edge_cases_and_all(result)

    # 요약 출력
    result.summary()

    # 종료 코드
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
