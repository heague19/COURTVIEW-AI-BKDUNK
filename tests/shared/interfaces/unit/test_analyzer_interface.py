# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/interfaces/unit
파일: test_analyzer_interface.py
설명: analyzer_interface.py 단위 테스트 (10개 export, 전체 메서드/프로퍼티 검증)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
from abc import ABC
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# 테스트 대상 임포트
# =============================================================================
import numpy as np

from shared.constants.localization import SupportedLanguage
from shared.interfaces.analyzer_interface import (
    AnalyzerState,
    AnalysisResult,
    AnalyzerMetrics,
    IAnalyzer,
    IFrameAnalyzer,
    ISequenceAnalyzer,
    IStreamAnalyzer,
    IComparisonAnalyzer,
    ComparisonInput,
    IAnalyzerFactory,
    __version__,
)


# =============================================================================
# 테스트 하네스
# =============================================================================
class TestResult:
    """단위 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.section = ""

    def set_section(self, name: str) -> None:
        self.section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, msg: str = "") -> None:
        self.failed += 1
        detail = f" - {msg}" if msg else ""
        print(f"  [FAIL] {name}{detail}")

    def check(self, name: str, condition: bool, msg: str = "") -> None:
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
# 구체 스텁 클래스 (ABC 검증용)
# =============================================================================
class StubAnalyzer(IAnalyzer[str, str, dict]):
    """IAnalyzer 구체 구현 스텁."""

    def __init__(self) -> None:
        self._state = AnalyzerState.UNINITIALIZED
        self._metrics = AnalyzerMetrics()

    @property
    def name(self) -> str:
        return "StubAnalyzer"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> AnalyzerState:
        return self._state

    @property
    def metrics(self) -> AnalyzerMetrics:
        return self._metrics

    def initialize(self, config: dict) -> None:
        self._state = AnalyzerState.READY

    def analyze(self, input_data: str) -> AnalysisResult[str]:
        self._state = AnalyzerState.PROCESSING
        result = AnalysisResult.success_result(
            data=f"analyzed: {input_data}",
            confidence=0.95,
        )
        self._state = AnalyzerState.READY
        return result

    def reset(self) -> None:
        self._state = AnalyzerState.UNINITIALIZED
        self._metrics = AnalyzerMetrics()

    def shutdown(self) -> None:
        self._state = AnalyzerState.SHUTDOWN


class StubFrameAnalyzer(IFrameAnalyzer[dict, dict]):
    """IFrameAnalyzer 구체 구현 스텁."""

    def __init__(self) -> None:
        self._state = AnalyzerState.READY
        self._metrics = AnalyzerMetrics()

    @property
    def name(self) -> str:
        return "StubFrameAnalyzer"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> AnalyzerState:
        return self._state

    @property
    def metrics(self) -> AnalyzerMetrics:
        return self._metrics

    def initialize(self, config: dict) -> None:
        self._state = AnalyzerState.READY

    def analyze_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp_ms: float,
    ) -> AnalysisResult[dict]:
        return AnalysisResult.success_result(
            data={"shape": list(frame.shape), "frame_idx": frame_index},
            confidence=0.9,
            frame_index=frame_index,
        )

    def reset(self) -> None:
        self._state = AnalyzerState.UNINITIALIZED

    def shutdown(self) -> None:
        self._state = AnalyzerState.SHUTDOWN


class StubSequenceAnalyzer(ISequenceAnalyzer[dict, dict]):
    """ISequenceAnalyzer 구체 구현 스텁."""

    def __init__(self) -> None:
        self._state = AnalyzerState.READY
        self._metrics = AnalyzerMetrics()

    @property
    def name(self) -> str:
        return "StubSequenceAnalyzer"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> AnalyzerState:
        return self._state

    @property
    def metrics(self) -> AnalyzerMetrics:
        return self._metrics

    @property
    def min_sequence_length(self) -> int:
        return 5

    @property
    def max_sequence_length(self) -> int:
        return 300

    def initialize(self, config: dict) -> None:
        self._state = AnalyzerState.READY

    def analyze_sequence(
        self,
        frames: list[np.ndarray],
        start_frame_index: int,
        fps: float,
    ) -> AnalysisResult[dict]:
        return AnalysisResult.success_result(
            data={"frame_count": len(frames), "fps": fps},
            confidence=0.85,
        )

    def reset(self) -> None:
        self._state = AnalyzerState.UNINITIALIZED

    def shutdown(self) -> None:
        self._state = AnalyzerState.SHUTDOWN


class StubStreamAnalyzer(IStreamAnalyzer[dict, dict]):
    """IStreamAnalyzer 구체 구현 스텁."""

    def __init__(self) -> None:
        self._state = AnalyzerState.READY
        self._metrics = AnalyzerMetrics()
        self._streaming = False
        self._buffer: list[np.ndarray] = []

    @property
    def name(self) -> str:
        return "StubStreamAnalyzer"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> AnalyzerState:
        return self._state

    @property
    def metrics(self) -> AnalyzerMetrics:
        return self._metrics

    @property
    def buffer_size(self) -> int:
        return 30

    @property
    def is_streaming(self) -> bool:
        return self._streaming

    def initialize(self, config: dict) -> None:
        self._state = AnalyzerState.READY

    def analyze(self, input_data: np.ndarray) -> AnalysisResult[dict]:
        return AnalysisResult.success_result(data={"analyzed": True})

    def start_stream(self) -> None:
        self._streaming = True
        self._state = AnalyzerState.PROCESSING

    def stop_stream(self) -> None:
        self._streaming = False
        self._state = AnalyzerState.READY

    def push_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp_ms: float,
    ) -> AnalysisResult[dict] | None:
        self._buffer.append(frame)
        if len(self._buffer) >= self.buffer_size:
            self._buffer.clear()
            return AnalysisResult.success_result(
                data={"batch_processed": True},
                confidence=0.88,
            )
        return None

    def flush(self) -> list[AnalysisResult[dict]]:
        results = []
        if self._buffer:
            results.append(AnalysisResult.success_result(
                data={"flushed_frames": len(self._buffer)},
            ))
            self._buffer.clear()
        return results

    def reset(self) -> None:
        self._buffer.clear()
        self._streaming = False
        self._state = AnalyzerState.UNINITIALIZED

    def shutdown(self) -> None:
        self._buffer.clear()
        self._streaming = False
        self._state = AnalyzerState.SHUTDOWN


class StubComparisonAnalyzer(IComparisonAnalyzer[np.ndarray, dict, dict]):
    """IComparisonAnalyzer 구체 구현 스텁."""

    def __init__(self) -> None:
        self._state = AnalyzerState.READY
        self._metrics = AnalyzerMetrics()

    @property
    def name(self) -> str:
        return "StubComparisonAnalyzer"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> AnalyzerState:
        return self._state

    @property
    def metrics(self) -> AnalyzerMetrics:
        return self._metrics

    def initialize(self, config: dict) -> None:
        self._state = AnalyzerState.READY

    def compare(
        self,
        reference: np.ndarray,
        target: np.ndarray,
    ) -> AnalysisResult[dict]:
        sim = self.calculate_similarity(reference, target)
        return AnalysisResult.success_result(
            data={"similarity": sim},
            confidence=sim,
        )

    def calculate_similarity(
        self,
        reference: np.ndarray,
        target: np.ndarray,
    ) -> float:
        if reference.shape != target.shape:
            return 0.0
        diff = np.mean(np.abs(reference.astype(float) - target.astype(float)))
        return max(0.0, 1.0 - diff / 255.0)

    def reset(self) -> None:
        self._state = AnalyzerState.UNINITIALIZED

    def shutdown(self) -> None:
        self._state = AnalyzerState.SHUTDOWN


class StubAnalyzerFactory(IAnalyzerFactory[dict]):
    """IAnalyzerFactory 구체 구현 스텁."""

    def create(self, config: dict) -> IAnalyzer:
        return StubAnalyzer()

    def get_supported_types(self) -> list[str]:
        return ["frame", "sequence", "stream"]


# =============================================================================
# 유틸: 테스트용 프레임 생성
# =============================================================================
def make_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """BGR 테스트 프레임 생성."""
    return np.zeros((h, w, 3), dtype=np.uint8)


# =============================================================================
# 1. AnalyzerState 테스트
# =============================================================================
def test_analyzer_state_members(t: TestResult) -> None:
    """AnalyzerState 멤버 값 및 수량 검증."""
    members = list(AnalyzerState)
    t.check("멤버 수 = 6", len(members) == 6, f"실제: {len(members)}")

    expected = {
        "UNINITIALIZED": "uninitialized",
        "READY": "ready",
        "PROCESSING": "processing",
        "PAUSED": "paused",
        "ERROR": "error",
        "SHUTDOWN": "shutdown",
    }
    for name, value in expected.items():
        state = AnalyzerState[name]
        t.check(f"{name} = '{value}'", state.value == value)


def test_analyzer_state_str(t: TestResult) -> None:
    """AnalyzerState __str__ 테스트."""
    for state in AnalyzerState:
        t.check(f"str({state.name}) = value",
                str(state) == state.value)


def test_analyzer_state_str_enum(t: TestResult) -> None:
    """AnalyzerState가 str, Enum 동시 상속 검증."""
    t.check("str 상속", issubclass(AnalyzerState, str))
    t.check("Enum 상속", issubclass(AnalyzerState, Enum))
    # str이므로 문자열 연산 가능
    t.check("문자열 upper() 가능",
            AnalyzerState.READY.upper() == "READY")
    t.check("문자열 startswith() 가능",
            AnalyzerState.PROCESSING.startswith("proc"))


def test_analyzer_state_get_name(t: TestResult) -> None:
    """AnalyzerState.get_name() 다국어 테스트."""
    # 한국어 기본값
    t.check("READY 한국어 = '준비 완료'",
            AnalyzerState.READY.get_name() == "준비 완료")
    t.check("ERROR 한국어 = '오류'",
            AnalyzerState.ERROR.get_name(SupportedLanguage.KO) == "오류")

    # 영어
    t.check("READY 영어 = 'Ready'",
            AnalyzerState.READY.get_name(SupportedLanguage.EN) == "Ready")
    t.check("PROCESSING 영어 = 'Processing'",
            AnalyzerState.PROCESSING.get_name(SupportedLanguage.EN) == "Processing")

    # 일본어
    t.check("PAUSED 일본어 = '一時停止'",
            AnalyzerState.PAUSED.get_name(SupportedLanguage.JA) == "一時停止")

    # 중국어
    t.check("SHUTDOWN 중국어 = '已关闭'",
            AnalyzerState.SHUTDOWN.get_name(SupportedLanguage.ZH) == "已关闭")

    # 스페인어
    t.check("UNINITIALIZED 스페인어 = 'Sin inicializar'",
            AnalyzerState.UNINITIALIZED.get_name(SupportedLanguage.ES) == "Sin inicializar")

    # 모든 상태 × 모든 언어 조합 누락 없음
    for state in AnalyzerState:
        for lang in [SupportedLanguage.KO, SupportedLanguage.EN,
                     SupportedLanguage.JA, SupportedLanguage.ZH,
                     SupportedLanguage.ES]:
            name = state.get_name(lang)
            t.check(f"get_name({state.name}, {lang.value}) 비어있지 않음",
                    isinstance(name, str) and len(name) > 0)


def test_analyzer_state_to_korean(t: TestResult) -> None:
    """AnalyzerState.to_korean 프로퍼티 테스트."""
    expected_ko = {
        AnalyzerState.UNINITIALIZED: "초기화 전",
        AnalyzerState.READY: "준비 완료",
        AnalyzerState.PROCESSING: "처리 중",
        AnalyzerState.PAUSED: "일시 정지",
        AnalyzerState.ERROR: "오류",
        AnalyzerState.SHUTDOWN: "종료됨",
    }
    for state, ko_name in expected_ko.items():
        t.check(f"{state.name}.to_korean = '{ko_name}'",
                state.to_korean == ko_name)


def test_analyzer_state_is_active(t: TestResult) -> None:
    """AnalyzerState.is_active 프로퍼티 테스트."""
    t.check("READY.is_active = True", AnalyzerState.READY.is_active is True)
    t.check("PROCESSING.is_active = True", AnalyzerState.PROCESSING.is_active is True)
    t.check("PAUSED.is_active = True", AnalyzerState.PAUSED.is_active is True)
    t.check("UNINITIALIZED.is_active = False", AnalyzerState.UNINITIALIZED.is_active is False)
    t.check("ERROR.is_active = False", AnalyzerState.ERROR.is_active is False)
    t.check("SHUTDOWN.is_active = False", AnalyzerState.SHUTDOWN.is_active is False)


def test_analyzer_state_is_error(t: TestResult) -> None:
    """AnalyzerState.is_error 프로퍼티 테스트."""
    t.check("ERROR.is_error = True", AnalyzerState.ERROR.is_error is True)
    for state in AnalyzerState:
        if state != AnalyzerState.ERROR:
            t.check(f"{state.name}.is_error = False", state.is_error is False)


def test_analyzer_state_is_terminated(t: TestResult) -> None:
    """AnalyzerState.is_terminated 프로퍼티 테스트."""
    t.check("SHUTDOWN.is_terminated = True",
            AnalyzerState.SHUTDOWN.is_terminated is True)
    t.check("ERROR.is_terminated = True",
            AnalyzerState.ERROR.is_terminated is True)
    t.check("READY.is_terminated = False",
            AnalyzerState.READY.is_terminated is False)
    t.check("PROCESSING.is_terminated = False",
            AnalyzerState.PROCESSING.is_terminated is False)
    t.check("PAUSED.is_terminated = False",
            AnalyzerState.PAUSED.is_terminated is False)
    t.check("UNINITIALIZED.is_terminated = False",
            AnalyzerState.UNINITIALIZED.is_terminated is False)


# =============================================================================
# 2. AnalysisResult 테스트
# =============================================================================
def test_analysis_result_success_factory(t: TestResult) -> None:
    """AnalysisResult.success_result() 팩토리 테스트."""
    r = AnalysisResult.success_result(
        data={"score": 95},
        confidence=0.92,
        processing_time_ms=15.5,
        frame_index=42,
        metadata={"source": "test"},
    )
    t.check("success = True", r.success is True)
    t.check("data 설정됨", r.data == {"score": 95})
    t.check("confidence = 0.92", r.confidence == 0.92)
    t.check("processing_time_ms = 15.5", r.processing_time_ms == 15.5)
    t.check("frame_index = 42", r.frame_index == 42)
    t.check("metadata 설정됨", r.metadata == {"source": "test"})
    t.check("error_message = None", r.error_message is None)
    t.check("error_code = None", r.error_code is None)


def test_analysis_result_failure_factory(t: TestResult) -> None:
    """AnalysisResult.failure_result() 팩토리 테스트."""
    r = AnalysisResult.failure_result(
        error_message="분석 실패",
        error_code="ANALYSIS_ERROR",
        metadata={"retry": True},
    )
    t.check("success = False", r.success is False)
    t.check("data = None", r.data is None)
    t.check("error_message 설정됨", r.error_message == "분석 실패")
    t.check("error_code 설정됨", r.error_code == "ANALYSIS_ERROR")
    t.check("confidence = 0.0 (기본값)", r.confidence == 0.0)
    t.check("metadata 설정됨", r.metadata == {"retry": True})


def test_analysis_result_defaults(t: TestResult) -> None:
    """AnalysisResult 기본값 테스트."""
    r = AnalysisResult(success=True)
    t.check("result_id 기본값 = None", r.result_id is None)
    t.check("data 기본값 = None", r.data is None)
    t.check("error_message 기본값 = None", r.error_message is None)
    t.check("error_code 기본값 = None", r.error_code is None)
    t.check("confidence 기본값 = 0.0", r.confidence == 0.0)
    t.check("processing_time_ms 기본값 = 0.0", r.processing_time_ms == 0.0)
    t.check("frame_index 기본값 = None", r.frame_index is None)
    t.check("timestamp 타입 = datetime", isinstance(r.timestamp, datetime))
    t.check("timestamp UTC timezone",
            r.timestamp.tzinfo == timezone.utc)
    t.check("metadata 기본값 = 빈 dict", r.metadata == {})


def test_analysis_result_metadata_isolation(t: TestResult) -> None:
    """AnalysisResult metadata 인스턴스 간 격리 테스트."""
    r1 = AnalysisResult(success=True)
    r2 = AnalysisResult(success=True)
    r1.metadata["key"] = "value"
    t.check("metadata 인스턴스 격리",
            "key" not in r2.metadata,
            "r2.metadata에 r1의 값이 침투함")

    # success_result metadata=None → 빈 dict
    r3 = AnalysisResult.success_result(data="test")
    t.check("metadata=None → 빈 dict",
            r3.metadata == {} and r3.metadata is not None)


def test_analysis_result_fields(t: TestResult) -> None:
    """AnalysisResult 필드 수 검증."""
    field_names = [f.name for f in fields(AnalysisResult)]
    expected = [
        "success", "result_id", "data", "error_message", "error_code",
        "confidence", "processing_time_ms", "frame_index", "timestamp", "metadata",
    ]
    t.check(f"필드 수 = {len(expected)}", len(field_names) == len(expected),
            f"실제: {len(field_names)}")
    for name in expected:
        t.check(f"필드 '{name}' 존재", name in field_names)


# =============================================================================
# 3. AnalyzerMetrics 테스트
# =============================================================================
def test_analyzer_metrics_defaults(t: TestResult) -> None:
    """AnalyzerMetrics 기본값 테스트."""
    m = AnalyzerMetrics()
    t.check("total_processed = 0", m.total_processed == 0)
    t.check("successful_count = 0", m.successful_count == 0)
    t.check("failed_count = 0", m.failed_count == 0)
    t.check("total_processing_time_ms = 0.0", m.total_processing_time_ms == 0.0)
    t.check("average_processing_time_ms = 0.0", m.average_processing_time_ms == 0.0)
    t.check("average_confidence = 0.0", m.average_confidence == 0.0)
    t.check("peak_memory_mb = 0.0", m.peak_memory_mb == 0.0)
    t.check("current_fps = 0.0", m.current_fps == 0.0)
    t.check("last_error = None", m.last_error is None)
    t.check("last_error_time = None", m.last_error_time is None)


def test_analyzer_metrics_update_success(t: TestResult) -> None:
    """AnalyzerMetrics.update() 성공 결과 업데이트 테스트."""
    m = AnalyzerMetrics()

    # 첫 번째 성공 결과
    r1 = AnalysisResult.success_result(data="ok", confidence=0.9)
    m.update(r1, processing_time_ms=10.0)

    t.check("1회 후 total_processed = 1", m.total_processed == 1)
    t.check("1회 후 successful_count = 1", m.successful_count == 1)
    t.check("1회 후 failed_count = 0", m.failed_count == 0)
    t.check("1회 후 average_confidence = 0.9",
            abs(m.average_confidence - 0.9) < 1e-9)
    t.check("1회 후 average_processing_time_ms = 10.0",
            abs(m.average_processing_time_ms - 10.0) < 1e-9)
    t.check("1회 후 current_fps = 100.0",
            abs(m.current_fps - 100.0) < 1e-6)

    # 두 번째 성공 결과
    r2 = AnalysisResult.success_result(data="ok2", confidence=0.8)
    m.update(r2, processing_time_ms=20.0)

    t.check("2회 후 total_processed = 2", m.total_processed == 2)
    t.check("2회 후 successful_count = 2", m.successful_count == 2)
    # 이동 평균: (0.9 * 1 + 0.8) / 2 = 0.85
    t.check("2회 후 average_confidence = 0.85",
            abs(m.average_confidence - 0.85) < 1e-9)
    # 평균 처리 시간: (10 + 20) / 2 = 15.0
    t.check("2회 후 average_processing_time_ms = 15.0",
            abs(m.average_processing_time_ms - 15.0) < 1e-9)
    # FPS: 1000 / 15 = 66.666...
    t.check("2회 후 current_fps ≈ 66.67",
            abs(m.current_fps - 1000.0 / 15.0) < 1e-3)


def test_analyzer_metrics_update_failure(t: TestResult) -> None:
    """AnalyzerMetrics.update() 실패 결과 업데이트 테스트."""
    m = AnalyzerMetrics()

    r_fail = AnalysisResult.failure_result(error_message="오류 발생")
    m.update(r_fail, processing_time_ms=5.0)

    t.check("실패 후 total_processed = 1", m.total_processed == 1)
    t.check("실패 후 successful_count = 0", m.successful_count == 0)
    t.check("실패 후 failed_count = 1", m.failed_count == 1)
    t.check("실패 후 last_error = '오류 발생'",
            m.last_error == "오류 발생")
    t.check("실패 후 last_error_time 설정됨",
            isinstance(m.last_error_time, datetime))
    t.check("실패 후 last_error_time UTC",
            m.last_error_time.tzinfo == timezone.utc)
    # 실패 시 average_confidence 변하지 않음 (successful_count = 0)
    t.check("실패만 → average_confidence = 0.0",
            m.average_confidence == 0.0)


def test_analyzer_metrics_success_rate(t: TestResult) -> None:
    """AnalyzerMetrics.success_rate 프로퍼티 테스트."""
    m = AnalyzerMetrics()

    # 0/0 = 0.0
    t.check("처리 없음 → success_rate = 0.0",
            m.success_rate == 0.0)

    # 3 성공, 1 실패
    for _ in range(3):
        m.update(AnalysisResult.success_result(data="ok", confidence=0.9), 10.0)
    m.update(AnalysisResult.failure_result(error_message="err"), 10.0)

    t.check("3/4 → success_rate = 0.75",
            abs(m.success_rate - 0.75) < 1e-9)


def test_analyzer_metrics_fps_zero_time(t: TestResult) -> None:
    """AnalyzerMetrics FPS 계산 - 0ms 처리 시간 안전성."""
    m = AnalyzerMetrics()
    r = AnalysisResult.success_result(data="ok", confidence=1.0)
    m.update(r, processing_time_ms=0.0)
    # average_processing_time_ms = 0.0 → FPS 업데이트 안 됨 (0으로 나누기 방지)
    t.check("0ms 처리 시 current_fps = 0.0 (나눗셈 안전)",
            m.current_fps == 0.0)


# =============================================================================
# 4. IAnalyzer 테스트
# =============================================================================
def test_ianalyzer_abc(t: TestResult) -> None:
    """IAnalyzer ABC 검증."""
    t.check("IAnalyzer는 ABC", issubclass(IAnalyzer, ABC))

    # 구체 클래스로 인스턴스화
    analyzer = StubAnalyzer()
    t.check("StubAnalyzer 생성 가능", isinstance(analyzer, IAnalyzer))
    t.check("name = 'StubAnalyzer'", analyzer.name == "StubAnalyzer")
    t.check("version = '1.0.0'", analyzer.version == "1.0.0")
    t.check("초기 state = UNINITIALIZED",
            analyzer.state == AnalyzerState.UNINITIALIZED)


def test_ianalyzer_lifecycle(t: TestResult) -> None:
    """IAnalyzer 생명주기 테스트."""
    analyzer = StubAnalyzer()

    # 초기화
    analyzer.initialize({})
    t.check("initialize 후 state = READY",
            analyzer.state == AnalyzerState.READY)

    # 분석
    result = analyzer.analyze("test_input")
    t.check("analyze 결과 success = True", result.success is True)
    t.check("analyze 결과 data 포함",
            result.data == "analyzed: test_input")
    t.check("analyze 후 state = READY",
            analyzer.state == AnalyzerState.READY)

    # 리셋
    analyzer.reset()
    t.check("reset 후 state = UNINITIALIZED",
            analyzer.state == AnalyzerState.UNINITIALIZED)

    # 종료
    analyzer.initialize({})
    analyzer.shutdown()
    t.check("shutdown 후 state = SHUTDOWN",
            analyzer.state == AnalyzerState.SHUTDOWN)


def test_ianalyzer_validate_input(t: TestResult) -> None:
    """IAnalyzer.validate_input() 기본 구현 테스트."""
    analyzer = StubAnalyzer()
    t.check("validate_input(None) = False",
            analyzer.validate_input(None) is False)
    t.check("validate_input('data') = True",
            analyzer.validate_input("data") is True)
    t.check("validate_input(0) = True",
            analyzer.validate_input(0) is True)
    t.check("validate_input('') = True (빈 문자열은 not None)",
            analyzer.validate_input("") is True)


def test_ianalyzer_metrics_instance(t: TestResult) -> None:
    """IAnalyzer.metrics 프로퍼티 테스트."""
    analyzer = StubAnalyzer()
    t.check("metrics 반환 타입 = AnalyzerMetrics",
            isinstance(analyzer.metrics, AnalyzerMetrics))


# =============================================================================
# 5. IFrameAnalyzer 테스트
# =============================================================================
def test_iframe_analyzer_inheritance(t: TestResult) -> None:
    """IFrameAnalyzer 상속 관계 테스트."""
    t.check("IFrameAnalyzer는 IAnalyzer 상속",
            issubclass(IFrameAnalyzer, IAnalyzer))

    analyzer = StubFrameAnalyzer()
    t.check("StubFrameAnalyzer는 IFrameAnalyzer",
            isinstance(analyzer, IFrameAnalyzer))
    t.check("StubFrameAnalyzer는 IAnalyzer",
            isinstance(analyzer, IAnalyzer))


def test_iframe_analyzer_analyze_frame(t: TestResult) -> None:
    """IFrameAnalyzer.analyze_frame() 테스트."""
    analyzer = StubFrameAnalyzer()
    frame = make_frame(480, 640)

    result = analyzer.analyze_frame(frame, frame_index=10, timestamp_ms=333.3)
    t.check("analyze_frame 성공", result.success is True)
    t.check("frame_index 전달됨",
            result.data["frame_idx"] == 10)
    t.check("shape 전달됨",
            result.data["shape"] == [480, 640, 3])


def test_iframe_analyzer_analyze_delegates(t: TestResult) -> None:
    """IFrameAnalyzer.analyze()가 analyze_frame(frame_index=0)으로 위임."""
    analyzer = StubFrameAnalyzer()
    frame = make_frame()

    result = analyzer.analyze(frame)
    t.check("analyze → analyze_frame 위임 성공", result.success is True)
    t.check("analyze → frame_index = 0",
            result.data["frame_idx"] == 0)


def test_iframe_analyzer_validate_input(t: TestResult) -> None:
    """IFrameAnalyzer.validate_input() 테스트."""
    analyzer = StubFrameAnalyzer()

    # 유효한 BGR 프레임
    valid_frame = make_frame()
    t.check("유효한 BGR 프레임 → True",
            analyzer.validate_input(valid_frame) is True)

    # None
    t.check("None → False",
            analyzer.validate_input(None) is False)

    # ndarray 아닌 타입
    t.check("list → False",
            analyzer.validate_input([[1, 2, 3]]) is False)

    # 2D 배열 (grayscale)
    gray = np.zeros((480, 640), dtype=np.uint8)
    t.check("2D (grayscale) → False",
            analyzer.validate_input(gray) is False)

    # 4채널 (RGBA)
    rgba = np.zeros((480, 640, 4), dtype=np.uint8)
    t.check("4채널 (RGBA) → False",
            analyzer.validate_input(rgba) is False)

    # 1채널
    single = np.zeros((480, 640, 1), dtype=np.uint8)
    t.check("1채널 → False",
            analyzer.validate_input(single) is False)

    # 올바른 3채널
    bgr = np.zeros((100, 100, 3), dtype=np.uint8)
    t.check("소형 3채널 → True",
            analyzer.validate_input(bgr) is True)


# =============================================================================
# 6. ISequenceAnalyzer 테스트
# =============================================================================
def test_isequence_analyzer_inheritance(t: TestResult) -> None:
    """ISequenceAnalyzer 상속 관계 테스트."""
    t.check("ISequenceAnalyzer는 IAnalyzer 상속",
            issubclass(ISequenceAnalyzer, IAnalyzer))

    analyzer = StubSequenceAnalyzer()
    t.check("StubSequenceAnalyzer는 ISequenceAnalyzer",
            isinstance(analyzer, ISequenceAnalyzer))


def test_isequence_analyzer_properties(t: TestResult) -> None:
    """ISequenceAnalyzer min/max_sequence_length 테스트."""
    analyzer = StubSequenceAnalyzer()
    t.check("min_sequence_length = 5", analyzer.min_sequence_length == 5)
    t.check("max_sequence_length = 300", analyzer.max_sequence_length == 300)


def test_isequence_analyzer_analyze_sequence(t: TestResult) -> None:
    """ISequenceAnalyzer.analyze_sequence() 테스트."""
    analyzer = StubSequenceAnalyzer()
    frames = [make_frame() for _ in range(10)]

    result = analyzer.analyze_sequence(frames, start_frame_index=0, fps=30.0)
    t.check("analyze_sequence 성공", result.success is True)
    t.check("frame_count = 10",
            result.data["frame_count"] == 10)
    t.check("fps = 30.0",
            result.data["fps"] == 30.0)


def test_isequence_analyzer_analyze_delegates(t: TestResult) -> None:
    """ISequenceAnalyzer.analyze()가 analyze_sequence(start_frame_index=0, fps=30)으로 위임."""
    analyzer = StubSequenceAnalyzer()
    frames = [make_frame() for _ in range(10)]

    result = analyzer.analyze(frames)
    t.check("analyze → analyze_sequence 위임 성공", result.success is True)
    t.check("기본 fps = 30.0", result.data["fps"] == 30.0)


def test_isequence_analyzer_validate_input(t: TestResult) -> None:
    """ISequenceAnalyzer.validate_input() 테스트."""
    analyzer = StubSequenceAnalyzer()

    # None
    t.check("None → False",
            analyzer.validate_input(None) is False)

    # 빈 리스트
    t.check("빈 리스트 → False",
            analyzer.validate_input([]) is False)

    # 최소 길이 미달 (min=5, 제공=3)
    short = [make_frame() for _ in range(3)]
    t.check("3프레임 (min=5 미달) → False",
            analyzer.validate_input(short) is False)

    # 최대 길이 초과 (max=300, 제공=301)
    # 최소 프레임으로 메모리 절약
    too_long = [np.zeros((1, 1, 3), dtype=np.uint8) for _ in range(301)]
    t.check("301프레임 (max=300 초과) → False",
            analyzer.validate_input(too_long) is False)

    # 정확히 min 길이
    exact_min = [make_frame(10, 10) for _ in range(5)]
    t.check("5프레임 (min=5 정확) → True",
            analyzer.validate_input(exact_min) is True)

    # ndarray 아닌 항목 포함
    mixed = [make_frame(10, 10)] * 4 + ["not_array"]
    t.check("비 ndarray 포함 → False",
            analyzer.validate_input(mixed) is False)

    # 2D 프레임 포함
    bad_dim = [make_frame(10, 10)] * 4 + [np.zeros((10, 10), dtype=np.uint8)]
    t.check("2D 프레임 포함 → False",
            analyzer.validate_input(bad_dim) is False)


# =============================================================================
# 7. IStreamAnalyzer 테스트
# =============================================================================
def test_istream_analyzer_inheritance(t: TestResult) -> None:
    """IStreamAnalyzer 상속 관계 테스트."""
    t.check("IStreamAnalyzer는 IAnalyzer 상속",
            issubclass(IStreamAnalyzer, IAnalyzer))

    analyzer = StubStreamAnalyzer()
    t.check("StubStreamAnalyzer는 IStreamAnalyzer",
            isinstance(analyzer, IStreamAnalyzer))


def test_istream_analyzer_lifecycle(t: TestResult) -> None:
    """IStreamAnalyzer 스트리밍 생명주기 테스트."""
    analyzer = StubStreamAnalyzer()

    t.check("초기 is_streaming = False", analyzer.is_streaming is False)
    t.check("buffer_size = 30", analyzer.buffer_size == 30)

    analyzer.start_stream()
    t.check("start_stream 후 is_streaming = True", analyzer.is_streaming is True)
    t.check("start_stream 후 state = PROCESSING",
            analyzer.state == AnalyzerState.PROCESSING)

    analyzer.stop_stream()
    t.check("stop_stream 후 is_streaming = False", analyzer.is_streaming is False)
    t.check("stop_stream 후 state = READY",
            analyzer.state == AnalyzerState.READY)


def test_istream_analyzer_push_frame(t: TestResult) -> None:
    """IStreamAnalyzer.push_frame() 버퍼링 테스트."""
    analyzer = StubStreamAnalyzer()
    analyzer.start_stream()

    frame = make_frame(10, 10)
    # buffer_size = 30 → 29개 push하면 None 반환
    for i in range(29):
        result = analyzer.push_frame(frame, frame_index=i, timestamp_ms=float(i))
        if i < 28:
            t.check(f"push_frame[{i}] 버퍼 미충족 → None",
                    result is None) if i == 0 else None  # 첫 번째만 체크
    # 마지막 push에서 None 확인 (29번째, 인덱스 28)
    t.check("push_frame[28] 버퍼 미충족 → None",
            result is None)

    # 30번째 push → 결과 반환
    result_30 = analyzer.push_frame(frame, frame_index=29, timestamp_ms=29.0)
    t.check("push_frame[29] 버퍼 충족 → 결과 반환",
            result_30 is not None and result_30.success is True)
    t.check("batch_processed = True",
            result_30.data["batch_processed"] is True)


def test_istream_analyzer_flush(t: TestResult) -> None:
    """IStreamAnalyzer.flush() 테스트."""
    analyzer = StubStreamAnalyzer()
    analyzer.start_stream()

    # 빈 버퍼 flush
    empty_results = analyzer.flush()
    t.check("빈 버퍼 flush → 빈 리스트", len(empty_results) == 0)

    # 일부 프레임 push 후 flush
    frame = make_frame(10, 10)
    for i in range(5):
        analyzer.push_frame(frame, frame_index=i, timestamp_ms=float(i))

    flush_results = analyzer.flush()
    t.check("5프레임 flush → 결과 1개", len(flush_results) == 1)
    t.check("flush 결과 성공", flush_results[0].success is True)
    t.check("flush 결과 flushed_frames = 5",
            flush_results[0].data["flushed_frames"] == 5)

    # flush 후 다시 flush → 빈 리스트
    empty_after = analyzer.flush()
    t.check("재 flush → 빈 리스트", len(empty_after) == 0)


# =============================================================================
# 8. ComparisonInput 테스트
# =============================================================================
def test_comparison_input_creation(t: TestResult) -> None:
    """ComparisonInput 생성 테스트."""
    ref = make_frame(10, 10)
    tgt = make_frame(10, 10)
    ci = ComparisonInput(
        reference=ref,
        target=tgt,
        reference_metadata={"type": "정답"},
        target_metadata={"type": "사용자"},
    )
    t.check("reference 설정됨", ci.reference is ref)
    t.check("target 설정됨", ci.target is tgt)
    t.check("reference_metadata 설정됨",
            ci.reference_metadata == {"type": "정답"})
    t.check("target_metadata 설정됨",
            ci.target_metadata == {"type": "사용자"})


def test_comparison_input_defaults(t: TestResult) -> None:
    """ComparisonInput 기본값 테스트."""
    ci = ComparisonInput(reference="ref", target="tgt")
    t.check("reference_metadata 기본값 = 빈 dict",
            ci.reference_metadata == {})
    t.check("target_metadata 기본값 = 빈 dict",
            ci.target_metadata == {})


def test_comparison_input_metadata_isolation(t: TestResult) -> None:
    """ComparisonInput metadata 인스턴스 간 격리 테스트."""
    ci1 = ComparisonInput(reference="a", target="b")
    ci2 = ComparisonInput(reference="c", target="d")
    ci1.reference_metadata["x"] = 1
    t.check("metadata 인스턴스 격리",
            "x" not in ci2.reference_metadata)


# =============================================================================
# 9. IComparisonAnalyzer 테스트
# =============================================================================
def test_icomparison_analyzer_inheritance(t: TestResult) -> None:
    """IComparisonAnalyzer 상속 관계 테스트."""
    t.check("IComparisonAnalyzer는 IAnalyzer 상속",
            issubclass(IComparisonAnalyzer, IAnalyzer))

    analyzer = StubComparisonAnalyzer()
    t.check("StubComparisonAnalyzer는 IComparisonAnalyzer",
            isinstance(analyzer, IComparisonAnalyzer))


def test_icomparison_analyzer_compare(t: TestResult) -> None:
    """IComparisonAnalyzer.compare() 테스트."""
    analyzer = StubComparisonAnalyzer()
    ref = np.full((10, 10, 3), 100, dtype=np.uint8)
    tgt = np.full((10, 10, 3), 100, dtype=np.uint8)

    result = analyzer.compare(ref, tgt)
    t.check("동일 이미지 compare 성공", result.success is True)
    t.check("동일 이미지 similarity = 1.0",
            abs(result.data["similarity"] - 1.0) < 1e-9)


def test_icomparison_analyzer_similarity(t: TestResult) -> None:
    """IComparisonAnalyzer.calculate_similarity() 테스트."""
    analyzer = StubComparisonAnalyzer()

    # 동일 이미지
    same = np.full((10, 10, 3), 128, dtype=np.uint8)
    t.check("동일 이미지 유사도 = 1.0",
            abs(analyzer.calculate_similarity(same, same) - 1.0) < 1e-9)

    # 완전 다른 이미지
    black = np.zeros((10, 10, 3), dtype=np.uint8)
    white = np.full((10, 10, 3), 255, dtype=np.uint8)
    sim = analyzer.calculate_similarity(black, white)
    t.check("흑백 유사도 = 0.0", abs(sim - 0.0) < 1e-9)

    # shape 불일치
    small = np.zeros((5, 5, 3), dtype=np.uint8)
    big = np.zeros((10, 10, 3), dtype=np.uint8)
    t.check("shape 불일치 유사도 = 0.0",
            analyzer.calculate_similarity(small, big) == 0.0)


def test_icomparison_analyzer_analyze_delegates(t: TestResult) -> None:
    """IComparisonAnalyzer.analyze()가 compare()로 위임."""
    analyzer = StubComparisonAnalyzer()
    ref = np.full((10, 10, 3), 50, dtype=np.uint8)
    tgt = np.full((10, 10, 3), 50, dtype=np.uint8)

    ci = ComparisonInput(reference=ref, target=tgt)
    result = analyzer.analyze(ci)
    t.check("analyze(ComparisonInput) → compare 위임 성공",
            result.success is True)
    t.check("analyze 결과 similarity = 1.0",
            abs(result.data["similarity"] - 1.0) < 1e-9)


# =============================================================================
# 10. IAnalyzerFactory 테스트
# =============================================================================
def test_ianalyzer_factory_abc(t: TestResult) -> None:
    """IAnalyzerFactory ABC 검증."""
    t.check("IAnalyzerFactory는 ABC", issubclass(IAnalyzerFactory, ABC))


def test_ianalyzer_factory_create(t: TestResult) -> None:
    """IAnalyzerFactory.create() 테스트."""
    factory = StubAnalyzerFactory()
    analyzer = factory.create({})
    t.check("create() 반환 타입 = IAnalyzer",
            isinstance(analyzer, IAnalyzer))
    t.check("create() 반환 이름 = StubAnalyzer",
            analyzer.name == "StubAnalyzer")


def test_ianalyzer_factory_supported_types(t: TestResult) -> None:
    """IAnalyzerFactory.get_supported_types() 테스트."""
    factory = StubAnalyzerFactory()
    types = factory.get_supported_types()
    t.check("get_supported_types() 반환 타입 = list",
            isinstance(types, list))
    t.check("3개 타입 지원",
            len(types) == 3)
    t.check("'frame' 포함", "frame" in types)
    t.check("'sequence' 포함", "sequence" in types)
    t.check("'stream' 포함", "stream" in types)


# =============================================================================
# 11. 모듈 메타데이터 검증
# =============================================================================
def test_module_metadata(t: TestResult) -> None:
    """모듈 메타데이터 검증."""
    import shared.interfaces.analyzer_interface as mod

    t.check("__version__ = '1.0.0'",
            mod.__version__ == "1.0.0")
    t.check("__all__ 길이 = 10",
            len(mod.__all__) == 10, f"실제: {len(mod.__all__)}")

    expected = {
        "AnalyzerState", "AnalysisResult", "AnalyzerMetrics",
        "IAnalyzer", "IFrameAnalyzer", "ISequenceAnalyzer",
        "IStreamAnalyzer", "IComparisonAnalyzer",
        "ComparisonInput", "IAnalyzerFactory",
    }
    t.check("__all__ 내용 일치",
            set(mod.__all__) == expected,
            f"차이: {set(mod.__all__) ^ expected}")


def test_all_exports_importable(t: TestResult) -> None:
    """__all__ 모든 항목 import 가능 검증."""
    import shared.interfaces.analyzer_interface as mod

    for name in mod.__all__:
        obj = getattr(mod, name, None)
        t.check(f"export '{name}' 존재",
                obj is not None)
        t.check(f"export '{name}' 은 type 또는 class",
                isinstance(obj, type))


# =============================================================================
# 12. 엣지 케이스
# =============================================================================
def test_edge_cases(t: TestResult) -> None:
    """엣지 케이스 테스트."""
    # AnalyzerState 문자열 비교
    t.check("AnalyzerState == 문자열 값",
            AnalyzerState.READY == "ready")
    t.check("AnalyzerState != 다른 문자열",
            AnalyzerState.READY != "processing")

    # AnalysisResult 타입 Generic (런타임에는 영향 없음)
    r_int = AnalysisResult.success_result(data=42)
    t.check("Generic[int] → data = 42", r_int.data == 42)

    r_list = AnalysisResult.success_result(data=[1, 2, 3])
    t.check("Generic[list] → data = [1,2,3]", r_list.data == [1, 2, 3])

    # AnalyzerMetrics 다수 업데이트 후 정확도 (누적 오차 확인)
    m = AnalyzerMetrics()
    for i in range(100):
        r = AnalysisResult.success_result(data="ok", confidence=0.9)
        m.update(r, processing_time_ms=10.0)
    t.check("100회 업데이트 후 average_confidence ≈ 0.9",
            abs(m.average_confidence - 0.9) < 1e-6)
    t.check("100회 업데이트 후 success_rate = 1.0",
            abs(m.success_rate - 1.0) < 1e-9)

    # ComparisonInput Generic (다양한 타입)
    ci_str = ComparisonInput(reference="a", target="b")
    t.check("ComparisonInput[str] 생성 가능",
            ci_str.reference == "a" and ci_str.target == "b")

    # IFrameAnalyzer validate_input: 4D 배열
    analyzer = StubFrameAnalyzer()
    arr_4d = np.zeros((1, 480, 640, 3), dtype=np.uint8)
    t.check("4D 배열 → False (ndim != 3)",
            analyzer.validate_input(arr_4d) is False)


# =============================================================================
# 메인
# =============================================================================
def main() -> None:
    t = TestResult()
    print("\n" + "=" * 60)
    print("  analyzer_interface.py v1.0.0 단위 테스트")
    print("=" * 60)

    # 1. AnalyzerState
    t.set_section("[1] AnalyzerState - 멤버 값 및 수량")
    test_analyzer_state_members(t)

    t.set_section("[2] AnalyzerState - __str__")
    test_analyzer_state_str(t)

    t.set_section("[3] AnalyzerState - str,Enum 상속")
    test_analyzer_state_str_enum(t)

    t.set_section("[4] AnalyzerState - get_name() 다국어")
    test_analyzer_state_get_name(t)

    t.set_section("[5] AnalyzerState - to_korean")
    test_analyzer_state_to_korean(t)

    t.set_section("[6] AnalyzerState - is_active")
    test_analyzer_state_is_active(t)

    t.set_section("[7] AnalyzerState - is_error")
    test_analyzer_state_is_error(t)

    t.set_section("[8] AnalyzerState - is_terminated")
    test_analyzer_state_is_terminated(t)

    # 2. AnalysisResult
    t.set_section("[9] AnalysisResult - success_result()")
    test_analysis_result_success_factory(t)

    t.set_section("[10] AnalysisResult - failure_result()")
    test_analysis_result_failure_factory(t)

    t.set_section("[11] AnalysisResult - 기본값")
    test_analysis_result_defaults(t)

    t.set_section("[12] AnalysisResult - metadata 격리")
    test_analysis_result_metadata_isolation(t)

    t.set_section("[13] AnalysisResult - 필드 수")
    test_analysis_result_fields(t)

    # 3. AnalyzerMetrics
    t.set_section("[14] AnalyzerMetrics - 기본값")
    test_analyzer_metrics_defaults(t)

    t.set_section("[15] AnalyzerMetrics - update() 성공")
    test_analyzer_metrics_update_success(t)

    t.set_section("[16] AnalyzerMetrics - update() 실패")
    test_analyzer_metrics_update_failure(t)

    t.set_section("[17] AnalyzerMetrics - success_rate")
    test_analyzer_metrics_success_rate(t)

    t.set_section("[18] AnalyzerMetrics - FPS 0ms 안전성")
    test_analyzer_metrics_fps_zero_time(t)

    # 4. IAnalyzer
    t.set_section("[19] IAnalyzer - ABC 검증")
    test_ianalyzer_abc(t)

    t.set_section("[20] IAnalyzer - 생명주기")
    test_ianalyzer_lifecycle(t)

    t.set_section("[21] IAnalyzer - validate_input()")
    test_ianalyzer_validate_input(t)

    t.set_section("[22] IAnalyzer - metrics 프로퍼티")
    test_ianalyzer_metrics_instance(t)

    # 5. IFrameAnalyzer
    t.set_section("[23] IFrameAnalyzer - 상속 관계")
    test_iframe_analyzer_inheritance(t)

    t.set_section("[24] IFrameAnalyzer - analyze_frame()")
    test_iframe_analyzer_analyze_frame(t)

    t.set_section("[25] IFrameAnalyzer - analyze() 위임")
    test_iframe_analyzer_analyze_delegates(t)

    t.set_section("[26] IFrameAnalyzer - validate_input()")
    test_iframe_analyzer_validate_input(t)

    # 6. ISequenceAnalyzer
    t.set_section("[27] ISequenceAnalyzer - 상속 관계")
    test_isequence_analyzer_inheritance(t)

    t.set_section("[28] ISequenceAnalyzer - 프로퍼티")
    test_isequence_analyzer_properties(t)

    t.set_section("[29] ISequenceAnalyzer - analyze_sequence()")
    test_isequence_analyzer_analyze_sequence(t)

    t.set_section("[30] ISequenceAnalyzer - analyze() 위임")
    test_isequence_analyzer_analyze_delegates(t)

    t.set_section("[31] ISequenceAnalyzer - validate_input()")
    test_isequence_analyzer_validate_input(t)

    # 7. IStreamAnalyzer
    t.set_section("[32] IStreamAnalyzer - 상속 관계")
    test_istream_analyzer_inheritance(t)

    t.set_section("[33] IStreamAnalyzer - 스트리밍 생명주기")
    test_istream_analyzer_lifecycle(t)

    t.set_section("[34] IStreamAnalyzer - push_frame() 버퍼링")
    test_istream_analyzer_push_frame(t)

    t.set_section("[35] IStreamAnalyzer - flush()")
    test_istream_analyzer_flush(t)

    # 8. ComparisonInput
    t.set_section("[36] ComparisonInput - 생성")
    test_comparison_input_creation(t)

    t.set_section("[37] ComparisonInput - 기본값")
    test_comparison_input_defaults(t)

    t.set_section("[38] ComparisonInput - metadata 격리")
    test_comparison_input_metadata_isolation(t)

    # 9. IComparisonAnalyzer
    t.set_section("[39] IComparisonAnalyzer - 상속 관계")
    test_icomparison_analyzer_inheritance(t)

    t.set_section("[40] IComparisonAnalyzer - compare()")
    test_icomparison_analyzer_compare(t)

    t.set_section("[41] IComparisonAnalyzer - calculate_similarity()")
    test_icomparison_analyzer_similarity(t)

    t.set_section("[42] IComparisonAnalyzer - analyze() 위임")
    test_icomparison_analyzer_analyze_delegates(t)

    # 10. IAnalyzerFactory
    t.set_section("[43] IAnalyzerFactory - ABC 검증")
    test_ianalyzer_factory_abc(t)

    t.set_section("[44] IAnalyzerFactory - create()")
    test_ianalyzer_factory_create(t)

    t.set_section("[45] IAnalyzerFactory - get_supported_types()")
    test_ianalyzer_factory_supported_types(t)

    # 11. 모듈 메타데이터
    t.set_section("[46] 모듈 메타데이터 검증")
    test_module_metadata(t)

    t.set_section("[47] __all__ export import 검증")
    test_all_exports_importable(t)

    # 12. 엣지 케이스
    t.set_section("[48] 엣지 케이스")
    test_edge_cases(t)

    sys.exit(0 if t.summary() else 1)


if __name__ == "__main__":
    main()
