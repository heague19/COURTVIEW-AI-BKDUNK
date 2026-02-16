# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/interfaces/performance
파일: test_game_interface_perf.py
설명: game_interface.py 성능 테스트 (생성, 프로퍼티, 팩토리, 메트릭 벤치마크)

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
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# 테스트 대상 임포트
# =============================================================================
import numpy as np

from shared.constants.localization import SupportedLanguage
from shared.interfaces.game_interface import (
    GameModuleState,
    GameEventResult,
    ValidationResult,
    FusionResult,
    GameModuleMetrics,
    IGameEventDetector,
    IRefereeValidator,
    IMultiViewFusion,
)


# =============================================================================
# 경량 스텁 클래스 (성능 테스트 전용, 외부 import 방지)
# =============================================================================
class _StubEventDetector(IGameEventDetector[dict, dict]):
    """IGameEventDetector 경량 스텁 (성능 측정용)."""

    def __init__(self) -> None:
        self._state = GameModuleState.UNINITIALIZED
        self._metrics = GameModuleMetrics()

    @property
    def name(self) -> str:
        return "PerfStubDetector"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> GameModuleState:
        return self._state

    @property
    def metrics(self) -> GameModuleMetrics:
        return self._metrics

    @property
    def supported_events(self) -> list[str]:
        return ["shot", "foul"]

    def initialize(self, config: dict) -> None:
        self._state = GameModuleState.READY

    def detect_events(
        self, frame: np.ndarray, detections: list[Any],
        tracks: list[Any], poses: list[Any],
        frame_index: int = 0, timestamp_ms: float = 0.0,
    ) -> GameEventResult[list[dict]]:
        return GameEventResult.success_result(
            data=[{"type": "shot"}], confidence=0.9, events_detected=1,
        )

    def get_active_events(self) -> list[dict]:
        return []

    def get_event_history(
        self, event_type: str | None = None,
        start_time_ms: float | None = None,
        end_time_ms: float | None = None, max_count: int = 100,
    ) -> list[dict]:
        return []

    def reset(self) -> None:
        self._state = GameModuleState.UNINITIALIZED

    def shutdown(self) -> None:
        self._state = GameModuleState.SHUTDOWN


class _StubRefereeValidator(IRefereeValidator[dict]):
    """IRefereeValidator 경량 스텁 (성능 측정용)."""

    def __init__(self) -> None:
        self._state = GameModuleState.UNINITIALIZED
        self._metrics = GameModuleMetrics()

    @property
    def name(self) -> str:
        return "PerfStubValidator"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> GameModuleState:
        return self._state

    @property
    def metrics(self) -> GameModuleMetrics:
        return self._metrics

    @property
    def active_rule_set(self) -> str:
        return "fiba"

    @property
    def confidence_threshold(self) -> float:
        return 0.85

    @property
    def consistency_score(self) -> float:
        return 0.9

    def initialize(self, config: dict, rule_set: str = "fiba") -> None:
        self._state = GameModuleState.READY

    def validate_violation(
        self, violation_data: Any, evidence: dict[str, Any],
    ) -> ValidationResult:
        return ValidationResult.confirmed(
            confidence=0.92, rule_reference="FIBA Art.25",
            explanation="확인",
        )

    def validate_foul(
        self, foul_data: Any, evidence: dict[str, Any],
    ) -> ValidationResult:
        return ValidationResult.confirmed(
            confidence=0.88, rule_reference="FIBA Art.33",
            explanation="확인",
        )

    def check_consistency(self, decision: Any, history: list[Any]) -> float:
        return 0.95

    def get_decision_explanation(self, decision: Any, lang: str = "ko") -> str:
        return "설명"

    def reset(self) -> None:
        self._state = GameModuleState.UNINITIALIZED

    def shutdown(self) -> None:
        self._state = GameModuleState.SHUTDOWN


class _StubMultiViewFusion(IMultiViewFusion[dict]):
    """IMultiViewFusion 경량 스텁 (성능 측정용)."""

    def __init__(self) -> None:
        self._state = GameModuleState.UNINITIALIZED
        self._metrics = GameModuleMetrics()

    @property
    def name(self) -> str:
        return "PerfStubFusion"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> GameModuleState:
        return self._state

    @property
    def metrics(self) -> GameModuleMetrics:
        return self._metrics

    @property
    def num_views(self) -> int:
        return 3

    @property
    def calibration_quality(self) -> float:
        return 0.95

    def initialize(self, config: dict, calibrations: list[Any] | None = None) -> None:
        self._state = GameModuleState.READY

    def fuse_detections(
        self, per_view_detections: dict[str, list[Any]],
    ) -> FusionResult[list[Any]]:
        return FusionResult.success_result(data=[], confidence=0.85, num_views_used=3)

    def fuse_poses(
        self, per_view_poses: dict[str, list[Any]],
    ) -> FusionResult[list[Any]]:
        return FusionResult.success_result(data=[], confidence=0.88, num_views_used=3)

    def fuse_trajectories(
        self, per_view_trajectories: dict[str, list[Any]],
    ) -> FusionResult[list[Any]]:
        return FusionResult.success_result(data=[], confidence=0.82, num_views_used=3)

    def triangulate_point(
        self, per_view_points: dict[str, tuple[float, float]],
    ) -> tuple[float, float, float]:
        return (1.0, 2.0, 3.0)

    def reset(self) -> None:
        self._state = GameModuleState.UNINITIALIZED

    def shutdown(self) -> None:
        self._state = GameModuleState.SHUTDOWN


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
# 1. GameModuleState 접근 성능
# =============================================================================
def test_game_module_state_perf(r: PerfResult) -> None:
    """GameModuleState Enum 접근 성능."""
    # 멤버 접근
    bench(r, "GameModuleState.READY 접근",
          lambda: GameModuleState.READY, 1.0, 100000)

    # value 접근
    state = GameModuleState.PROCESSING
    bench(r, "GameModuleState.value 접근",
          lambda: state.value, 1.0, 100000)

    # __str__
    bench(r, "str(GameModuleState) 호출",
          lambda: str(state), 2.0, 100000)

    # is_active 프로퍼티
    bench(r, "is_active 프로퍼티",
          lambda: state.is_active, 2.0, 100000)

    # is_initializing 프로퍼티
    init_state = GameModuleState.INITIALIZING
    bench(r, "is_initializing 프로퍼티",
          lambda: init_state.is_initializing, 1.0, 100000)

    # is_error 프로퍼티
    bench(r, "is_error 프로퍼티",
          lambda: state.is_error, 1.0, 100000)

    # is_terminated 프로퍼티
    bench(r, "is_terminated 프로퍼티",
          lambda: state.is_terminated, 2.0, 100000)

    # can_process 프로퍼티
    bench(r, "can_process 프로퍼티",
          lambda: state.can_process, 2.0, 100000)

    # to_korean 프로퍼티
    bench(r, "to_korean 프로퍼티",
          lambda: state.to_korean, 5.0, 100000)


# =============================================================================
# 2. GameModuleState.get_name() 다국어 성능
# =============================================================================
def test_get_name_perf(r: PerfResult) -> None:
    """get_name() 다국어 조회 성능."""
    state = GameModuleState.READY

    # 한국어 (기본값)
    bench(r, "get_name() 한국어 (기본)",
          lambda: state.get_name(), 5.0, 100000)

    # 영어
    bench(r, "get_name(EN)",
          lambda: state.get_name(SupportedLanguage.EN), 5.0, 100000)

    # 일본어
    bench(r, "get_name(JA)",
          lambda: state.get_name(SupportedLanguage.JA), 5.0, 100000)

    # 모든 상태 순회 (7개)
    bench(r, "전체 상태 get_name(KO) 순회 (7개)",
          lambda: [s.get_name(SupportedLanguage.KO) for s in GameModuleState],
          35.0, 50000)


# =============================================================================
# 3. GameEventResult 생성 성능
# =============================================================================
def test_game_event_result_perf(r: PerfResult) -> None:
    """GameEventResult 생성 및 팩토리 성능."""
    # 직접 생성 (최소 인수)
    bench(r, "GameEventResult(success=True) 생성",
          lambda: GameEventResult(success=True), 10.0, 50000)

    # success_result 팩토리
    bench(r, "GameEventResult.success_result() 팩토리",
          lambda: GameEventResult.success_result(
              data=[{"type": "shot"}], confidence=0.92,
              processing_time_ms=15.5, frame_index=42,
              events_detected=1,
          ), 15.0, 50000)

    # failure_result 팩토리
    bench(r, "GameEventResult.failure_result() 팩토리",
          lambda: GameEventResult.failure_result(
              error_message="오류", error_code="ERR_001",
          ), 10.0, 50000)


# =============================================================================
# 4. ValidationResult 생성 성능
# =============================================================================
def test_validation_result_perf(r: PerfResult) -> None:
    """ValidationResult 생성 및 팩토리 성능."""
    # 직접 생성 (최소 인수)
    bench(r, "ValidationResult(is_valid=True) 생성",
          lambda: ValidationResult(is_valid=True), 10.0, 50000)

    # confirmed 팩토리
    bench(r, "ValidationResult.confirmed() 팩토리",
          lambda: ValidationResult.confirmed(
              confidence=0.92, rule_reference="FIBA Art.25",
              explanation="트래블링 확인",
              processing_time_ms=5.0, evidence_quality=0.88,
          ), 15.0, 50000)

    # rejected 팩토리
    bench(r, "ValidationResult.rejected() 팩토리",
          lambda: ValidationResult.rejected(
              confidence=0.75, explanation="증거 불충분",
          ), 10.0, 50000)


# =============================================================================
# 5. FusionResult 생성 성능
# =============================================================================
def test_fusion_result_perf(r: PerfResult) -> None:
    """FusionResult 생성 및 팩토리 성능."""
    # 직접 생성 (최소 인수)
    bench(r, "FusionResult(success=True) 생성",
          lambda: FusionResult(success=True), 10.0, 50000)

    # success_result 팩토리 (전체 인수)
    bench(r, "FusionResult.success_result() 팩토리",
          lambda: FusionResult.success_result(
              data=[], confidence=0.88,
              processing_time_ms=25.0, num_views_used=3,
              num_views_rejected=1, fusion_quality=0.92,
          ), 15.0, 50000)

    # failure_result 팩토리
    bench(r, "FusionResult.failure_result() 팩토리",
          lambda: FusionResult.failure_result(error_message="뷰 부족"),
          10.0, 50000)


# =============================================================================
# 6. 필드 접근 성능
# =============================================================================
def test_field_access_perf(r: PerfResult) -> None:
    """결과 객체 필드 접근 성능."""
    ger = GameEventResult.success_result(
        data=[{"type": "shot"}], confidence=0.92,
        processing_time_ms=15.5, frame_index=42,
        metadata={"source": "test"},
    )
    bench(r, "GameEventResult.success 접근",
          lambda: ger.success, 1.0, 100000)
    bench(r, "GameEventResult.data 접근",
          lambda: ger.data, 1.0, 100000)
    bench(r, "GameEventResult.events_detected 접근",
          lambda: ger.events_detected, 1.0, 100000)

    vr = ValidationResult.confirmed(
        confidence=0.92, rule_reference="FIBA Art.25", explanation="확인",
    )
    bench(r, "ValidationResult.is_valid 접근",
          lambda: vr.is_valid, 1.0, 100000)
    bench(r, "ValidationResult.evidence_quality 접근",
          lambda: vr.evidence_quality, 1.0, 100000)

    fr = FusionResult.success_result(data=[], confidence=0.88, num_views_used=3)
    bench(r, "FusionResult.num_views_used 접근",
          lambda: fr.num_views_used, 1.0, 100000)
    bench(r, "FusionResult.fusion_quality 접근",
          lambda: fr.fusion_quality, 1.0, 100000)


# =============================================================================
# 7. GameModuleMetrics 성능
# =============================================================================
def test_game_module_metrics_perf(r: PerfResult) -> None:
    """GameModuleMetrics 생성 및 업데이트 성능."""
    # 기본 생성
    bench(r, "GameModuleMetrics() 생성",
          lambda: GameModuleMetrics(), 5.0, 50000)

    # update_from_event_result (성공)
    m = GameModuleMetrics()
    r_success = GameEventResult.success_result(data=[], confidence=0.9)
    bench(r, "update_from_event_result(성공)",
          lambda: m.update_from_event_result(r_success, 10.0), 5.0, 50000)

    # update_from_event_result (실패)
    m2 = GameModuleMetrics()
    r_fail = GameEventResult.failure_result(error_message="err")
    bench(r, "update_from_event_result(실패)",
          lambda: m2.update_from_event_result(r_fail, 5.0), 5.0, 50000)

    # update_from_validation_result
    m3 = GameModuleMetrics()
    vr = ValidationResult.confirmed(
        confidence=0.92, rule_reference="FIBA", explanation="ok",
    )
    bench(r, "update_from_validation_result()",
          lambda: m3.update_from_validation_result(vr, 4.0), 5.0, 50000)

    # update_from_fusion_result
    m4 = GameModuleMetrics()
    fr = FusionResult.success_result(data=[], confidence=0.85, num_views_used=3)
    bench(r, "update_from_fusion_result()",
          lambda: m4.update_from_fusion_result(fr, 20.0), 5.0, 50000)

    # success_rate 프로퍼티
    m5 = GameModuleMetrics()
    for _ in range(100):
        m5.update_from_event_result(
            GameEventResult.success_result(data=[], confidence=0.9), 10.0)
    bench(r, "success_rate 프로퍼티 (100회 후)",
          lambda: m5.success_rate, 2.0, 100000)


# =============================================================================
# 8. IGameEventDetector validate_input 성능
# =============================================================================
def test_detector_validate_perf(r: PerfResult) -> None:
    """IGameEventDetector.validate_input() 성능."""
    detector = _StubEventDetector()

    # 유효한 프레임 (480x640)
    bench(r, "validate_input(480x640 BGR) 유효",
          lambda: detector.validate_input(_FRAME_480), 3.0, 100000)

    # None 입력
    bench(r, "validate_input(None) 무효",
          lambda: detector.validate_input(None), 1.0, 100000)

    # 소형 프레임
    bench(r, "validate_input(10x10 BGR) 유효",
          lambda: detector.validate_input(_FRAME_SMALL), 3.0, 100000)

    # 2D 배열 (무효)
    gray = np.zeros((480, 640), dtype=np.uint8)
    bench(r, "validate_input(2D grayscale) 무효",
          lambda: detector.validate_input(gray), 3.0, 100000)


# =============================================================================
# 9. 생명주기 성능 (스텁 기반)
# =============================================================================
def test_lifecycle_perf(r: PerfResult) -> None:
    """모듈 생명주기 (생성→초기화→처리→종료) 성능."""
    # 이벤트 감지기 생성
    bench(r, "_StubEventDetector() 생성",
          lambda: _StubEventDetector(), 15.0, 50000)

    # 심판 검증기 생성
    bench(r, "_StubRefereeValidator() 생성",
          lambda: _StubRefereeValidator(), 15.0, 50000)

    # 멀티뷰 융합기 생성
    bench(r, "_StubMultiViewFusion() 생성",
          lambda: _StubMultiViewFusion(), 15.0, 50000)

    # 이벤트 감지기 전체 사이클
    def detector_cycle():
        d = _StubEventDetector()
        d.initialize({})
        d.detect_events(_FRAME_SMALL, [], [], [], 0, 0.0)
        d.shutdown()

    bench(r, "이벤트 감지기 전체 사이클",
          detector_cycle, 60.0, 50000)

    # 심판 검증기 전체 사이클
    def validator_cycle():
        v = _StubRefereeValidator()
        v.initialize({})
        v.validate_violation({}, {})
        v.shutdown()

    bench(r, "심판 검증기 전체 사이클",
          validator_cycle, 60.0, 50000)

    # 멀티뷰 융합기 전체 사이클
    def fusion_cycle():
        f = _StubMultiViewFusion()
        f.initialize({})
        f.fuse_detections({"cam1": [], "cam2": []})
        f.shutdown()

    bench(r, "멀티뷰 융합기 전체 사이클",
          fusion_cycle, 60.0, 50000)


# =============================================================================
# 10. 결과 + 메트릭 통합 성능
# =============================================================================
def test_result_metrics_combined_perf(r: PerfResult) -> None:
    """결과 생성 + 메트릭 업데이트 연속 성능."""
    # 이벤트 결과 + 메트릭
    m1 = GameModuleMetrics()

    def event_create_and_update():
        result = GameEventResult.success_result(data=[], confidence=0.9)
        m1.update_from_event_result(result, 10.0)

    bench(r, "GameEventResult 생성 + 메트릭 업데이트",
          event_create_and_update, 20.0, 50000)

    # 검증 결과 + 메트릭
    m2 = GameModuleMetrics()

    def validation_create_and_update():
        result = ValidationResult.confirmed(
            confidence=0.92, rule_reference="FIBA", explanation="ok",
        )
        m2.update_from_validation_result(result, 5.0)

    bench(r, "ValidationResult 생성 + 메트릭 업데이트",
          validation_create_and_update, 20.0, 50000)

    # 융합 결과 + 메트릭
    m3 = GameModuleMetrics()

    def fusion_create_and_update():
        result = FusionResult.success_result(data=[], confidence=0.85, num_views_used=3)
        m3.update_from_fusion_result(result, 20.0)

    bench(r, "FusionResult 생성 + 메트릭 업데이트",
          fusion_create_and_update, 20.0, 50000)


# =============================================================================
# 11. Enum 조회 비교
# =============================================================================
def test_enum_lookup_perf(r: PerfResult) -> None:
    """GameModuleState Enum 조회 방식 비교."""
    # 이름으로 조회
    bench(r, "GameModuleState['READY'] (이름 조회)",
          lambda: GameModuleState["READY"], 2.0, 100000)

    # 값으로 조회
    bench(r, "GameModuleState('ready') (값 조회)",
          lambda: GameModuleState("ready"), 3.0, 100000)

    # in 연산
    bench(r, "'ready' in _value2member_map_",
          lambda: "ready" in GameModuleState._value2member_map_, 1.0, 100000)

    # iteration
    bench(r, "list(GameModuleState) 순회",
          lambda: list(GameModuleState), 3.0, 100000)


# =============================================================================
# 12. 대량 객체 생성
# =============================================================================
def test_bulk_creation_perf(r: PerfResult) -> None:
    """대량 객체 생성 성능 (스루풋 확인)."""
    # 1000개 GameEventResult 생성
    def create_1000_events():
        return [GameEventResult.success_result(data=i, confidence=0.9)
                for i in range(1000)]

    elapsed = measure(create_1000_events, 100)
    r.info(f"1000개 GameEventResult 생성: {elapsed:.1f}us (={elapsed/1000:.3f}us/개)")
    if elapsed < 15000.0:
        r.ok("1000개 GameEventResult 생성 (< 15ms)", elapsed, 15000.0)
    else:
        r.fail("1000개 GameEventResult 생성 (< 15ms)", elapsed, 15000.0)

    # 1000개 ValidationResult 생성
    def create_1000_validations():
        return [ValidationResult.confirmed(
            confidence=0.9, rule_reference="FIBA", explanation="ok",
        ) for _ in range(1000)]

    elapsed = measure(create_1000_validations, 100)
    r.info(f"1000개 ValidationResult 생성: {elapsed:.1f}us (={elapsed/1000:.3f}us/개)")
    if elapsed < 15000.0:
        r.ok("1000개 ValidationResult 생성 (< 15ms)", elapsed, 15000.0)
    else:
        r.fail("1000개 ValidationResult 생성 (< 15ms)", elapsed, 15000.0)

    # 1000개 메트릭 업데이트
    m = GameModuleMetrics()
    results = create_1000_events()

    def update_1000():
        for result in results:
            m.update_from_event_result(result, 10.0)

    elapsed = measure(update_1000, 100)
    r.info(f"1000개 메트릭 업데이트: {elapsed:.1f}us (={elapsed/1000:.3f}us/개)")
    if elapsed < 10000.0:
        r.ok("1000개 메트릭 업데이트 (< 10ms)", elapsed, 10000.0)
    else:
        r.fail("1000개 메트릭 업데이트 (< 10ms)", elapsed, 10000.0)


# =============================================================================
# 메인
# =============================================================================
def main() -> int:
    r = PerfResult()
    print("\n" + "=" * 60)
    print("  game_interface.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- [1] GameModuleState 접근 성능 ---")
    test_game_module_state_perf(r)

    print("\n--- [2] GameModuleState.get_name() 다국어 성능 ---")
    test_get_name_perf(r)

    print("\n--- [3] GameEventResult 생성 성능 ---")
    test_game_event_result_perf(r)

    print("\n--- [4] ValidationResult 생성 성능 ---")
    test_validation_result_perf(r)

    print("\n--- [5] FusionResult 생성 성능 ---")
    test_fusion_result_perf(r)

    print("\n--- [6] 필드 접근 성능 ---")
    test_field_access_perf(r)

    print("\n--- [7] GameModuleMetrics 성능 ---")
    test_game_module_metrics_perf(r)

    print("\n--- [8] IGameEventDetector validate_input 성능 ---")
    test_detector_validate_perf(r)

    print("\n--- [9] 생명주기 성능 ---")
    test_lifecycle_perf(r)

    print("\n--- [10] 결과 + 메트릭 통합 성능 ---")
    test_result_metrics_combined_perf(r)

    print("\n--- [11] Enum 조회 방식 비교 ---")
    test_enum_lookup_perf(r)

    print("\n--- [12] 대량 객체 생성 ---")
    test_bulk_creation_perf(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(main())
