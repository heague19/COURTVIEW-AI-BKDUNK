# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/interfaces/performance
파일: test_analyzer_interface_perf.py
설명: analyzer_interface.py 성능 테스트 (생성, 프로퍼티, 팩토리, 메트릭 벤치마크)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import gc
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

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
    ComparisonInput,
    IAnalyzer,
    IFrameAnalyzer,
    ISequenceAnalyzer,
)


# =============================================================================
# 경량 스텁 클래스 (성능 테스트 전용, 외부 import 방지)
# =============================================================================
class _StubAnalyzer(IAnalyzer[str, str, dict]):
    """IAnalyzer 경량 스텁 (성능 측정용)."""

    def __init__(self) -> None:
        self._state = AnalyzerState.UNINITIALIZED
        self._metrics = AnalyzerMetrics()

    @property
    def name(self) -> str:
        return "PerfStubAnalyzer"

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
        return AnalysisResult.success_result(
            data=f"analyzed: {input_data}", confidence=0.95,
        )

    def reset(self) -> None:
        self._state = AnalyzerState.UNINITIALIZED

    def shutdown(self) -> None:
        self._state = AnalyzerState.SHUTDOWN


class _StubFrameAnalyzer(IFrameAnalyzer[dict, dict]):
    """IFrameAnalyzer 경량 스텁 (성능 측정용)."""

    def __init__(self) -> None:
        self._state = AnalyzerState.READY
        self._metrics = AnalyzerMetrics()

    @property
    def name(self) -> str:
        return "PerfStubFrameAnalyzer"

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

    def analyze_frame(self, frame: np.ndarray, frame_index: int,
                      timestamp_ms: float) -> AnalysisResult[dict]:
        return AnalysisResult.success_result(data={"ok": True}, confidence=0.9)

    def reset(self) -> None:
        self._state = AnalyzerState.UNINITIALIZED

    def shutdown(self) -> None:
        self._state = AnalyzerState.SHUTDOWN


class _StubSequenceAnalyzer(ISequenceAnalyzer[dict, dict]):
    """ISequenceAnalyzer 경량 스텁 (성능 측정용)."""

    def __init__(self) -> None:
        self._state = AnalyzerState.READY
        self._metrics = AnalyzerMetrics()

    @property
    def name(self) -> str:
        return "PerfStubSequenceAnalyzer"

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

    def analyze_sequence(self, frames: list[np.ndarray],
                         start_frame_index: int, fps: float) -> AnalysisResult[dict]:
        return AnalysisResult.success_result(
            data={"frame_count": len(frames)}, confidence=0.85,
        )

    def reset(self) -> None:
        self._state = AnalyzerState.UNINITIALIZED

    def shutdown(self) -> None:
        self._state = AnalyzerState.SHUTDOWN


# =============================================================================
# 성능 테스트 하네스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.3f}us ({ratio:.1f}% of {limit_us:.0f}us)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.3f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.3f}us (limit: {limit_us:.0f}us)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n  실패:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (마이크로초/반복)."""
    gc.disable()
    try:
        # 워밍업
        warmup = min(iterations, 1000)
        for _ in range(warmup):
            func()

        # 측정
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns → us
    finally:
        gc.enable()


def bench(r: PerfResult, name: str, func, limit_us: float,
          iterations: int = 10000) -> None:
    """벤치마크 실행 헬퍼."""
    elapsed = measure(func, iterations)
    if elapsed < limit_us:
        r.ok(name, elapsed, limit_us)
    else:
        r.fail(name, elapsed, limit_us)


# =============================================================================
# 테스트용 프레임
# =============================================================================
_FRAME_480 = np.zeros((480, 640, 3), dtype=np.uint8)
_FRAME_SMALL = np.zeros((10, 10, 3), dtype=np.uint8)


# =============================================================================
# 1. AnalyzerState 성능
# =============================================================================
def test_analyzer_state_perf(r: PerfResult) -> None:
    """AnalyzerState Enum 접근 성능."""
    # 멤버 접근
    bench(r, "AnalyzerState.READY 접근",
          lambda: AnalyzerState.READY, 1.0, 100000)

    # value 접근
    state = AnalyzerState.PROCESSING
    bench(r, "AnalyzerState.value 접근",
          lambda: state.value, 1.0, 100000)

    # __str__
    bench(r, "str(AnalyzerState) 호출",
          lambda: str(state), 2.0, 100000)

    # is_active 프로퍼티
    bench(r, "is_active 프로퍼티",
          lambda: state.is_active, 2.0, 100000)

    # is_error 프로퍼티
    bench(r, "is_error 프로퍼티",
          lambda: state.is_error, 1.0, 100000)

    # is_terminated 프로퍼티
    bench(r, "is_terminated 프로퍼티",
          lambda: state.is_terminated, 2.0, 100000)

    # to_korean 프로퍼티
    bench(r, "to_korean 프로퍼티",
          lambda: state.to_korean, 5.0, 100000)


# =============================================================================
# 2. AnalyzerState.get_name() 다국어 성능
# =============================================================================
def test_get_name_perf(r: PerfResult) -> None:
    """get_name() 다국어 조회 성능."""
    state = AnalyzerState.READY

    # 한국어 (기본값)
    bench(r, "get_name() 한국어 (기본)",
          lambda: state.get_name(), 5.0, 100000)

    # 영어
    bench(r, "get_name(EN)",
          lambda: state.get_name(SupportedLanguage.EN), 5.0, 100000)

    # 일본어
    bench(r, "get_name(JA)",
          lambda: state.get_name(SupportedLanguage.JA), 5.0, 100000)

    # 모든 상태 순회 (6개)
    bench(r, "전체 상태 get_name(KO) 순회",
          lambda: [s.get_name(SupportedLanguage.KO) for s in AnalyzerState],
          30.0, 50000)


# =============================================================================
# 3. AnalysisResult 생성 성능
# =============================================================================
def test_analysis_result_perf(r: PerfResult) -> None:
    """AnalysisResult 생성 및 팩토리 성능."""
    # 직접 생성 (최소 인수)
    bench(r, "AnalysisResult(success=True) 생성",
          lambda: AnalysisResult(success=True), 10.0, 50000)

    # success_result 팩토리
    bench(r, "AnalysisResult.success_result() 팩토리",
          lambda: AnalysisResult.success_result(
              data={"score": 95}, confidence=0.92,
              processing_time_ms=15.5, frame_index=42,
          ), 15.0, 50000)

    # failure_result 팩토리
    bench(r, "AnalysisResult.failure_result() 팩토리",
          lambda: AnalysisResult.failure_result(
              error_message="오류", error_code="ERR_001",
          ), 10.0, 50000)

    # 전체 인수 생성
    from uuid import uuid4
    uid = uuid4()
    bench(r, "AnalysisResult() 전체 인수",
          lambda: AnalysisResult(
              success=True, result_id=uid, data={"a": 1},
              confidence=0.9, processing_time_ms=10.0,
              frame_index=0, metadata={"k": "v"},
          ), 15.0, 50000)


# =============================================================================
# 4. AnalysisResult 필드 접근 성능
# =============================================================================
def test_analysis_result_access_perf(r: PerfResult) -> None:
    """AnalysisResult 필드 접근 성능."""
    result = AnalysisResult.success_result(
        data={"score": 95}, confidence=0.92,
        processing_time_ms=15.5, frame_index=42,
        metadata={"source": "test"},
    )

    bench(r, "result.success 접근",
          lambda: result.success, 1.0, 100000)

    bench(r, "result.data 접근",
          lambda: result.data, 1.0, 100000)

    bench(r, "result.confidence 접근",
          lambda: result.confidence, 1.0, 100000)

    bench(r, "result.timestamp 접근",
          lambda: result.timestamp, 1.0, 100000)

    bench(r, "result.metadata 접근",
          lambda: result.metadata, 1.0, 100000)


# =============================================================================
# 5. AnalyzerMetrics 성능
# =============================================================================
def test_analyzer_metrics_perf(r: PerfResult) -> None:
    """AnalyzerMetrics 생성 및 업데이트 성능."""
    # 기본 생성
    bench(r, "AnalyzerMetrics() 생성",
          lambda: AnalyzerMetrics(), 5.0, 50000)

    # update() 성공 결과
    m = AnalyzerMetrics()
    r_success = AnalysisResult.success_result(data="ok", confidence=0.9)
    bench(r, "AnalyzerMetrics.update(성공)",
          lambda: m.update(r_success, 10.0), 5.0, 50000)

    # update() 실패 결과
    m2 = AnalyzerMetrics()
    r_fail = AnalysisResult.failure_result(error_message="err")
    bench(r, "AnalyzerMetrics.update(실패)",
          lambda: m2.update(r_fail, 5.0), 5.0, 50000)

    # success_rate 프로퍼티
    m3 = AnalyzerMetrics()
    for _ in range(100):
        m3.update(AnalysisResult.success_result(data="ok", confidence=0.9), 10.0)
    bench(r, "success_rate 프로퍼티 (100회 후)",
          lambda: m3.success_rate, 2.0, 100000)


# =============================================================================
# 6. ComparisonInput 생성 성능
# =============================================================================
def test_comparison_input_perf(r: PerfResult) -> None:
    """ComparisonInput 생성 성능."""
    ref = _FRAME_SMALL
    tgt = _FRAME_SMALL

    # 최소 인수
    bench(r, "ComparisonInput(ref, tgt) 최소",
          lambda: ComparisonInput(reference=ref, target=tgt), 5.0, 50000)

    # 전체 인수
    bench(r, "ComparisonInput() 전체 인수",
          lambda: ComparisonInput(
              reference=ref, target=tgt,
              reference_metadata={"type": "ref"},
              target_metadata={"type": "tgt"},
          ), 8.0, 50000)


# =============================================================================
# 7. IFrameAnalyzer validate_input 성능
# =============================================================================
def test_frame_validate_perf(r: PerfResult) -> None:
    """IFrameAnalyzer.validate_input() 성능."""
    analyzer = _StubFrameAnalyzer()

    # 유효한 프레임 (480x640)
    bench(r, "validate_input(480x640 BGR) 유효",
          lambda: analyzer.validate_input(_FRAME_480), 3.0, 100000)

    # None 입력
    bench(r, "validate_input(None) 무효",
          lambda: analyzer.validate_input(None), 1.0, 100000)

    # 소형 프레임
    bench(r, "validate_input(10x10 BGR) 유효",
          lambda: analyzer.validate_input(_FRAME_SMALL), 3.0, 100000)

    # 2D 배열 (무효)
    gray = np.zeros((480, 640), dtype=np.uint8)
    bench(r, "validate_input(2D grayscale) 무효",
          lambda: analyzer.validate_input(gray), 3.0, 100000)


# =============================================================================
# 8. ISequenceAnalyzer validate_input 성능
# =============================================================================
def test_sequence_validate_perf(r: PerfResult) -> None:
    """ISequenceAnalyzer.validate_input() 성능."""
    analyzer = _StubSequenceAnalyzer()

    # 유효한 10프레임 시퀀스
    frames_10 = [_FRAME_SMALL for _ in range(10)]
    bench(r, "validate_input(10프레임) 유효",
          lambda: analyzer.validate_input(frames_10), 20.0, 50000)

    # 빈 리스트
    bench(r, "validate_input([]) 무효",
          lambda: analyzer.validate_input([]), 1.0, 100000)

    # None
    bench(r, "validate_input(None) 무효",
          lambda: analyzer.validate_input(None), 1.0, 100000)

    # 30프레임
    frames_30 = [_FRAME_SMALL for _ in range(30)]
    bench(r, "validate_input(30프레임) 유효",
          lambda: analyzer.validate_input(frames_30), 50.0, 50000)


# =============================================================================
# 9. 생명주기 성능 (스텁 기반)
# =============================================================================
def test_lifecycle_perf(r: PerfResult) -> None:
    """분석기 생명주기 (생성→초기화→분석→종료) 성능."""
    # 스텁 생성
    bench(r, "_StubAnalyzer() 생성",
          lambda: _StubAnalyzer(), 15.0, 50000)

    # 초기화
    analyzer = _StubAnalyzer()
    bench(r, "initialize({}) 호출",
          lambda: analyzer.initialize({}), 2.0, 100000)

    # 분석
    analyzer.initialize({})
    bench(r, "analyze('input') 호출",
          lambda: analyzer.analyze("input"), 20.0, 50000)

    # 전체 사이클 (생성→초기화→분석→종료)
    def full_cycle():
        a = _StubAnalyzer()
        a.initialize({})
        a.analyze("data")
        a.shutdown()

    bench(r, "전체 생명주기 (생성→초기화→분석→종료)",
          full_cycle, 50.0, 50000)


# =============================================================================
# 10. AnalysisResult + AnalyzerMetrics 통합 성능
# =============================================================================
def test_result_metrics_combined_perf(r: PerfResult) -> None:
    """AnalysisResult 생성 + AnalyzerMetrics 업데이트 연속 성능."""
    m = AnalyzerMetrics()

    def create_and_update():
        result = AnalysisResult.success_result(data="ok", confidence=0.9)
        m.update(result, 10.0)

    bench(r, "AnalysisResult 생성 + AnalyzerMetrics 업데이트",
          create_and_update, 20.0, 50000)

    # 실패 케이스
    m2 = AnalyzerMetrics()

    def create_fail_and_update():
        result = AnalysisResult.failure_result(error_message="err")
        m2.update(result, 5.0)

    bench(r, "failure_result 생성 + AnalyzerMetrics 업데이트",
          create_fail_and_update, 20.0, 50000)


# =============================================================================
# 11. Enum 조회 비교 (by name vs by value)
# =============================================================================
def test_enum_lookup_perf(r: PerfResult) -> None:
    """AnalyzerState Enum 조회 방식 비교."""
    # 이름으로 조회
    bench(r, "AnalyzerState['READY'] (이름 조회)",
          lambda: AnalyzerState["READY"], 2.0, 100000)

    # 값으로 조회
    bench(r, "AnalyzerState('ready') (값 조회)",
          lambda: AnalyzerState("ready"), 3.0, 100000)

    # in 연산
    bench(r, "'ready' in AnalyzerState._value2member_map_",
          lambda: "ready" in AnalyzerState._value2member_map_, 1.0, 100000)

    # iteration
    bench(r, "list(AnalyzerState) 순회",
          lambda: list(AnalyzerState), 3.0, 100000)


# =============================================================================
# 12. 메모리 관련: 대량 AnalysisResult 생성
# =============================================================================
def test_bulk_creation_perf(r: PerfResult) -> None:
    """대량 객체 생성 성능 (스루풋 확인)."""
    # 1000개 AnalysisResult 생성
    def create_1000():
        return [AnalysisResult.success_result(data=i, confidence=0.9)
                for i in range(1000)]

    elapsed = measure(create_1000, 100)
    r.info(f"1000개 AnalysisResult 생성: {elapsed:.1f}us (={elapsed/1000:.3f}us/개)")
    if elapsed < 15000.0:  # 15ms 이내
        r.ok("1000개 AnalysisResult 생성 (< 15ms)", elapsed, 15000.0)
    else:
        r.fail("1000개 AnalysisResult 생성 (< 15ms)", elapsed, 15000.0)

    # 1000개 AnalyzerMetrics 업데이트
    m = AnalyzerMetrics()
    results = create_1000()

    def update_1000():
        for result in results:
            m.update(result, 10.0)

    elapsed = measure(update_1000, 100)
    r.info(f"1000개 AnalyzerMetrics.update: {elapsed:.1f}us (={elapsed/1000:.3f}us/개)")
    if elapsed < 10000.0:  # 10ms 이내
        r.ok("1000개 AnalyzerMetrics 업데이트 (< 10ms)", elapsed, 10000.0)
    else:
        r.fail("1000개 AnalyzerMetrics 업데이트 (< 10ms)", elapsed, 10000.0)


# =============================================================================
# 메인
# =============================================================================
def main() -> int:
    r = PerfResult()
    print("\n" + "=" * 60)
    print("  analyzer_interface.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- [1] AnalyzerState 접근 성능 ---")
    test_analyzer_state_perf(r)

    print("\n--- [2] AnalyzerState.get_name() 다국어 성능 ---")
    test_get_name_perf(r)

    print("\n--- [3] AnalysisResult 생성 성능 ---")
    test_analysis_result_perf(r)

    print("\n--- [4] AnalysisResult 필드 접근 성능 ---")
    test_analysis_result_access_perf(r)

    print("\n--- [5] AnalyzerMetrics 성능 ---")
    test_analyzer_metrics_perf(r)

    print("\n--- [6] ComparisonInput 생성 성능 ---")
    test_comparison_input_perf(r)

    print("\n--- [7] IFrameAnalyzer validate_input 성능 ---")
    test_frame_validate_perf(r)

    print("\n--- [8] ISequenceAnalyzer validate_input 성능 ---")
    test_sequence_validate_perf(r)

    print("\n--- [9] 생명주기 성능 ---")
    test_lifecycle_perf(r)

    print("\n--- [10] AnalysisResult + AnalyzerMetrics 통합 ---")
    test_result_metrics_combined_perf(r)

    print("\n--- [11] Enum 조회 방식 비교 ---")
    test_enum_lookup_perf(r)

    print("\n--- [12] 대량 객체 생성 ---")
    test_bulk_creation_perf(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(main())
