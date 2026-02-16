# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_status_codes_perf.py

상태 코드 상수 모듈 성능 테스트
- 모듈 임포트 시간
- TaskStatus 속성 접근 (is_terminal, is_success, is_failure, is_running, is_pending)
- TaskStatus.to_korean
- AnalysisType.category (lru_cache)
- AnalysisType.to_korean
- AnalysisPhase.progress_percent / to_korean
- ServiceStatus 속성 (is_available, is_healthy, to_korean)
- QueuePriority.to_korean
- Environment 속성 (is_production, is_development, is_testing, to_korean)
- QualityLevel 속성 (description, min_score, max_score, is_usable)
- QualityLevel.from_score classmethod
- TaskType 속성 (is_analysis, is_report, is_learning, to_korean)
- LearningStatus 속성 (is_active, is_terminal, can_trigger_learning, to_korean)
- is_valid_transition 함수
- Enum 순회 (9 Enum, 91 멤버)
- frozenset 멤버십 직접 조회
- dict 캐시 직접 조회
- 복합 시나리오: 작업 생명주기 파이프라인
- 복합 시나리오: 분석 파이프라인
- 메모리 사용량
- 대량 처리

성능 기준:
- 모듈 임포트: < 500ms
- 속성/메서드 접근: < 1us
- QualityLevel.from_score: < 5us
- frozenset/dict 직접 조회: < 1us
- Enum 순회 (91 멤버): < 100us
- 복합 시나리오: < 50us
- 메모리: < 256KB
- 대량 처리 (1000회): < 500ms

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.2f}us ({ratio:.0f}% of {limit_us:.0f}us)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.2f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.2f}us (limit: {limit_us:.0f}us)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")
        return self.failed == 0


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간을 마이크로초(us) 단위로 측정."""
    gc.disable()
    try:
        # 워밍업
        for _ in range(min(iterations, 1000)):
            func()
        # 실제 측정
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


def _check(r: PerfResult, name: str, elapsed: float, limit: float) -> None:
    """측정 결과를 제한 시간과 비교하여 판정."""
    if elapsed <= limit:
        r.ok(name, elapsed, limit)
    else:
        r.fail(name, elapsed, limit)


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import(r: PerfResult) -> None:
    print("\n[1] 모듈 임포트 시간")
    import importlib
    mod_name = "shared.constants.status_codes"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"모듈 임포트: {elapsed_ms:.1f}ms")
    # 제한: 500ms = 500,000us
    _check(r, "모듈 임포트", elapsed_ms * 1000, 500_000)


# ==================== 2. TaskStatus 속성 접근 ====================
def test_task_status_properties(r: PerfResult) -> None:
    print("\n[2] TaskStatus 속성 접근")
    from shared.constants.status_codes import TaskStatus

    # is_terminal: 종료 상태 (frozenset 멤버십)
    ts_completed = TaskStatus.COMPLETED
    elapsed = measure(lambda: ts_completed.is_terminal)
    _check(r, "TaskStatus.is_terminal", elapsed, 1.0)

    # is_success: 성공 상태 (frozenset 멤버십)
    elapsed = measure(lambda: ts_completed.is_success)
    _check(r, "TaskStatus.is_success", elapsed, 1.0)

    # is_failure: 실패 상태 (frozenset 멤버십)
    ts_failed = TaskStatus.FAILED
    elapsed = measure(lambda: ts_failed.is_failure)
    _check(r, "TaskStatus.is_failure", elapsed, 1.0)

    # is_running: 실행 중 (frozenset 멤버십)
    ts_running = TaskStatus.RUNNING
    elapsed = measure(lambda: ts_running.is_running)
    _check(r, "TaskStatus.is_running", elapsed, 1.0)

    # is_pending: 대기 중 (frozenset 멤버십)
    ts_pending = TaskStatus.PENDING
    elapsed = measure(lambda: ts_pending.is_pending)
    _check(r, "TaskStatus.is_pending", elapsed, 1.0)


# ==================== 3. TaskStatus.to_korean ====================
def test_task_status_to_korean(r: PerfResult) -> None:
    print("\n[3] TaskStatus.to_korean")
    from shared.constants.status_codes import TaskStatus

    ts = TaskStatus.RUNNING
    elapsed = measure(lambda: ts.to_korean())
    _check(r, "TaskStatus.to_korean()", elapsed, 1.0)


# ==================== 4. AnalysisType.category (lru_cache) ====================
def test_analysis_type_category(r: PerfResult) -> None:
    print("\n[4] AnalysisType.category (lru_cache)")
    from shared.constants.status_codes import AnalysisType

    at = AnalysisType.TRAINING_SHOOTING
    # 워밍업: lru_cache 채우기
    _ = at.category
    elapsed = measure(lambda: at.category)
    _check(r, "AnalysisType.category (캐시)", elapsed, 1.0)

    # 다른 카테고리 값도 측정
    at_game = AnalysisType.GAME_FULL
    _ = at_game.category
    elapsed_game = measure(lambda: at_game.category)
    _check(r, "AnalysisType.category (game)", elapsed_game, 1.0)


# ==================== 5. AnalysisType.to_korean ====================
def test_analysis_type_to_korean(r: PerfResult) -> None:
    print("\n[5] AnalysisType.to_korean")
    from shared.constants.status_codes import AnalysisType

    at = AnalysisType.GAME_HIGHLIGHTS
    elapsed = measure(lambda: at.to_korean())
    _check(r, "AnalysisType.to_korean()", elapsed, 1.0)


# ==================== 6. AnalysisPhase.progress_percent ====================
def test_analysis_phase_progress(r: PerfResult) -> None:
    print("\n[6] AnalysisPhase.progress_percent")
    from shared.constants.status_codes import AnalysisPhase

    ap = AnalysisPhase.ANALYZING
    elapsed = measure(lambda: ap.progress_percent)
    _check(r, "AnalysisPhase.progress_percent", elapsed, 1.0)


# ==================== 7. AnalysisPhase.to_korean ====================
def test_analysis_phase_to_korean(r: PerfResult) -> None:
    print("\n[7] AnalysisPhase.to_korean")
    from shared.constants.status_codes import AnalysisPhase

    ap = AnalysisPhase.POSE_ESTIMATING
    elapsed = measure(lambda: ap.to_korean())
    _check(r, "AnalysisPhase.to_korean()", elapsed, 1.0)


# ==================== 8. ServiceStatus 속성 ====================
def test_service_status_properties(r: PerfResult) -> None:
    print("\n[8] ServiceStatus 속성")
    from shared.constants.status_codes import ServiceStatus

    # is_available (frozenset 멤버십)
    ss_healthy = ServiceStatus.HEALTHY
    elapsed = measure(lambda: ss_healthy.is_available)
    _check(r, "ServiceStatus.is_available", elapsed, 1.0)

    # is_healthy (직접 비교)
    elapsed = measure(lambda: ss_healthy.is_healthy)
    _check(r, "ServiceStatus.is_healthy", elapsed, 1.0)

    # to_korean (dict 조회)
    elapsed = measure(lambda: ss_healthy.to_korean())
    _check(r, "ServiceStatus.to_korean()", elapsed, 1.0)


# ==================== 9. QueuePriority.to_korean ====================
def test_queue_priority_to_korean(r: PerfResult) -> None:
    print("\n[9] QueuePriority.to_korean")
    from shared.constants.status_codes import QueuePriority

    qp = QueuePriority.NORMAL
    elapsed = measure(lambda: qp.to_korean())
    _check(r, "QueuePriority.to_korean()", elapsed, 1.0)


# ==================== 10. Environment 속성 ====================
def test_environment_properties(r: PerfResult) -> None:
    print("\n[10] Environment 속성")
    from shared.constants.status_codes import Environment

    env_prod = Environment.PRODUCTION
    elapsed = measure(lambda: env_prod.is_production)
    _check(r, "Environment.is_production", elapsed, 1.0)

    env_dev = Environment.DEVELOPMENT
    elapsed = measure(lambda: env_dev.is_development)
    _check(r, "Environment.is_development", elapsed, 1.0)

    env_test = Environment.TESTING
    elapsed = measure(lambda: env_test.is_testing)
    _check(r, "Environment.is_testing", elapsed, 1.0)

    elapsed = measure(lambda: env_prod.to_korean())
    _check(r, "Environment.to_korean()", elapsed, 1.0)


# ==================== 11. QualityLevel 속성 ====================
def test_quality_level_properties(r: PerfResult) -> None:
    print("\n[11] QualityLevel 속성")
    from shared.constants.status_codes import QualityLevel

    ql = QualityLevel.EXCELLENT
    elapsed = measure(lambda: ql.description)
    _check(r, "QualityLevel.description", elapsed, 1.0)

    elapsed = measure(lambda: ql.min_score)
    _check(r, "QualityLevel.min_score", elapsed, 1.0)

    elapsed = measure(lambda: ql.max_score)
    _check(r, "QualityLevel.max_score", elapsed, 1.0)

    elapsed = measure(lambda: ql.is_usable)
    _check(r, "QualityLevel.is_usable", elapsed, 1.0)


# ==================== 12. QualityLevel.from_score ====================
def test_quality_level_from_score(r: PerfResult) -> None:
    print("\n[12] QualityLevel.from_score")
    from shared.constants.status_codes import QualityLevel

    # 다양한 점수 구간 테스트
    elapsed_high = measure(lambda: QualityLevel.from_score(95.0))
    _check(r, "from_score(95.0) EXCELLENT", elapsed_high, 5.0)

    elapsed_mid = measure(lambda: QualityLevel.from_score(65.0))
    _check(r, "from_score(65.0) ACCEPTABLE", elapsed_mid, 5.0)

    elapsed_low = measure(lambda: QualityLevel.from_score(20.0))
    _check(r, "from_score(20.0) UNACCEPTABLE", elapsed_low, 5.0)


# ==================== 13. TaskType 속성 ====================
def test_task_type_properties(r: PerfResult) -> None:
    print("\n[13] TaskType 속성")
    from shared.constants.status_codes import TaskType

    tt_analysis = TaskType.ANALYSIS_TRAINING
    elapsed = measure(lambda: tt_analysis.is_analysis)
    _check(r, "TaskType.is_analysis", elapsed, 1.0)

    tt_report = TaskType.REPORT_WEEKLY
    elapsed = measure(lambda: tt_report.is_report)
    _check(r, "TaskType.is_report", elapsed, 1.0)

    tt_learning = TaskType.LEARNING_TRAINING
    elapsed = measure(lambda: tt_learning.is_learning)
    _check(r, "TaskType.is_learning", elapsed, 1.0)

    elapsed = measure(lambda: tt_analysis.to_korean())
    _check(r, "TaskType.to_korean()", elapsed, 1.0)


# ==================== 14. LearningStatus 속성 ====================
def test_learning_status_properties(r: PerfResult) -> None:
    print("\n[14] LearningStatus 속성")
    from shared.constants.status_codes import LearningStatus

    ls_training = LearningStatus.TRAINING
    elapsed = measure(lambda: ls_training.is_active)
    _check(r, "LearningStatus.is_active", elapsed, 1.0)

    ls_completed = LearningStatus.COMPLETED
    elapsed = measure(lambda: ls_completed.is_terminal)
    _check(r, "LearningStatus.is_terminal", elapsed, 1.0)

    ls_idle = LearningStatus.IDLE
    elapsed = measure(lambda: ls_idle.can_trigger_learning)
    _check(r, "LearningStatus.can_trigger_learning", elapsed, 1.0)

    elapsed = measure(lambda: ls_training.to_korean())
    _check(r, "LearningStatus.to_korean()", elapsed, 1.0)


# ==================== 15. is_valid_transition 함수 ====================
def test_is_valid_transition(r: PerfResult) -> None:
    print("\n[15] is_valid_transition 함수")
    from shared.constants.status_codes import TaskStatus, is_valid_transition

    # 유효한 전이
    elapsed_valid = measure(
        lambda: is_valid_transition(TaskStatus.PENDING, TaskStatus.QUEUED)
    )
    _check(r, "is_valid_transition (유효)", elapsed_valid, 1.0)

    # 무효한 전이
    elapsed_invalid = measure(
        lambda: is_valid_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING)
    )
    _check(r, "is_valid_transition (무효)", elapsed_invalid, 1.0)


# ==================== 16. Enum 순회 (9 Enum, 91 멤버) ====================
def test_enum_iteration(r: PerfResult) -> None:
    print("\n[16] Enum 순회 (9 Enum, 91 멤버)")
    from shared.constants.status_codes import (
        TaskStatus, AnalysisType, AnalysisPhase,
        ServiceStatus, QueuePriority, Environment,
        QualityLevel, TaskType, LearningStatus,
    )

    all_enums = [
        TaskStatus, AnalysisType, AnalysisPhase,
        ServiceStatus, QueuePriority, Environment,
        QualityLevel, TaskType, LearningStatus,
    ]

    def iterate_all():
        total = 0
        for enum_cls in all_enums:
            for _ in enum_cls:
                total += 1
        return total

    elapsed = measure(iterate_all, iterations=1000)
    r.info(f"9 Enum, 총 {iterate_all()} 멤버 순회")
    _check(r, "전체 Enum 순회 (91 멤버)", elapsed, 100.0)


# ==================== 17. frozenset 멤버십 직접 조회 ====================
def test_frozenset_direct_membership(r: PerfResult) -> None:
    print("\n[17] frozenset 멤버십 직접 조회")
    from shared.constants.status_codes import TaskStatus

    # 모듈 내부의 frozenset에 직접 접근 (속성을 통해)
    ts_completed = TaskStatus.COMPLETED
    ts_running = TaskStatus.RUNNING

    # True 케이스: COMPLETED는 terminal
    elapsed_true = measure(lambda: ts_completed.is_terminal)
    _check(r, "frozenset 멤버십 (True)", elapsed_true, 1.0)

    # False 케이스: RUNNING은 terminal이 아님
    elapsed_false = measure(lambda: ts_running.is_terminal)
    _check(r, "frozenset 멤버십 (False)", elapsed_false, 1.0)


# ==================== 18. dict 캐시 직접 조회 ====================
def test_dict_cache_direct_lookup(r: PerfResult) -> None:
    print("\n[18] dict 캐시 직접 조회")
    from shared.constants.status_codes import TaskStatus, AnalysisPhase

    # dict 기반 to_korean 조회
    ts = TaskStatus.PROCESSING
    elapsed_korean = measure(lambda: ts.to_korean())
    _check(r, "dict 캐시 to_korean 조회", elapsed_korean, 1.0)

    # dict 기반 progress_percent 조회
    ap = AnalysisPhase.DETECTING
    elapsed_progress = measure(lambda: ap.progress_percent)
    _check(r, "dict 캐시 progress_percent 조회", elapsed_progress, 1.0)


# ==================== 19. 복합 시나리오: 작업 생명주기 파이프라인 ====================
def test_composite_task_lifecycle(r: PerfResult) -> None:
    print("\n[19] 복합: 작업 생명주기 파이프라인")
    from shared.constants.status_codes import (
        TaskStatus, TaskType, QueuePriority,
        is_valid_transition,
    )

    def task_lifecycle():
        # 작업 유형 확인
        tt = TaskType.ANALYSIS_GAME
        _ = tt.is_analysis
        _ = tt.to_korean()

        # 우선순위 설정
        qp = QueuePriority.HIGH
        _ = qp.to_korean()

        # 상태 전이 시뮬레이션: PENDING -> QUEUED -> STARTED -> RUNNING -> COMPLETED
        transitions = [
            (TaskStatus.PENDING, TaskStatus.QUEUED),
            (TaskStatus.QUEUED, TaskStatus.STARTED),
            (TaskStatus.STARTED, TaskStatus.RUNNING),
            (TaskStatus.RUNNING, TaskStatus.COMPLETED),
        ]
        for from_s, to_s in transitions:
            valid = is_valid_transition(from_s, to_s)
            _ = from_s.to_korean()
            _ = from_s.is_terminal
            _ = from_s.is_running

        # 최종 상태 확인
        final = TaskStatus.COMPLETED
        _ = final.is_terminal
        _ = final.is_success
        _ = final.to_korean()

    elapsed = measure(task_lifecycle, iterations=5000)
    _check(r, "작업 생명주기 파이프라인", elapsed, 50.0)


# ==================== 20. 복합 시나리오: 분석 파이프라인 ====================
def test_composite_analysis_pipeline(r: PerfResult) -> None:
    print("\n[20] 복합: 분석 파이프라인")
    from shared.constants.status_codes import (
        AnalysisType, AnalysisPhase, QualityLevel,
        ServiceStatus, Environment,
    )

    def analysis_pipeline():
        # 환경 확인
        env = Environment.PRODUCTION
        _ = env.is_production
        _ = env.to_korean()

        # 서비스 상태 확인
        ss = ServiceStatus.HEALTHY
        _ = ss.is_available
        _ = ss.is_healthy
        _ = ss.to_korean()

        # 분석 유형 결정
        at = AnalysisType.TRAINING_SHOOTING
        _ = at.category
        _ = at.to_korean()

        # 품질 검사
        ql = QualityLevel.from_score(85.0)
        _ = ql.description
        _ = ql.min_score
        _ = ql.max_score
        _ = ql.is_usable

        # 분석 단계 순회
        phases = [
            AnalysisPhase.INITIALIZED,
            AnalysisPhase.PREPROCESSING,
            AnalysisPhase.DETECTING,
            AnalysisPhase.POSE_ESTIMATING,
            AnalysisPhase.ANALYZING,
            AnalysisPhase.GENERATING_FEEDBACK,
            AnalysisPhase.DONE,
        ]
        for phase in phases:
            _ = phase.progress_percent
            _ = phase.to_korean()

    elapsed = measure(analysis_pipeline, iterations=5000)
    _check(r, "분석 파이프라인", elapsed, 50.0)


# ==================== 21. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    print("\n[21] 메모리 사용량")
    import importlib
    mod_name = "shared.constants.status_codes"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.collect()
    try:
        import tracemalloc
        tracemalloc.start()
        importlib.import_module(mod_name)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_kb = peak_bytes / 1024
        r.info(f"메모리 피크: {peak_kb:.1f}KB")
        _check(r, "메모리 사용량", peak_kb, 256.0)
    except ImportError:
        r.info("tracemalloc 미사용 - 스킵")
        r.ok("메모리 (스킵)", 0, 256.0)


# ==================== 22. 대량 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    print("\n[22] 대량 처리 (1000 반복)")
    from shared.constants.status_codes import (
        TaskStatus, AnalysisType, AnalysisPhase,
        ServiceStatus, QueuePriority, Environment,
        QualityLevel, TaskType, LearningStatus,
        is_valid_transition,
    )

    all_task_statuses = list(TaskStatus)
    all_analysis_types = list(AnalysisType)
    all_analysis_phases = list(AnalysisPhase)
    all_service_statuses = list(ServiceStatus)
    all_queue_priorities = list(QueuePriority)
    all_environments = list(Environment)
    all_quality_levels = list(QualityLevel)
    all_task_types = list(TaskType)
    all_learning_statuses = list(LearningStatus)

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(1000):
        # TaskStatus: 모든 속성 접근
        for ts in all_task_statuses:
            _ = ts.is_terminal
            _ = ts.is_success
            _ = ts.is_failure
            _ = ts.is_running
            _ = ts.is_pending
            _ = ts.to_korean()

        # AnalysisType: category + to_korean
        for at in all_analysis_types:
            _ = at.category
            _ = at.to_korean()

        # AnalysisPhase: progress_percent + to_korean
        for ap in all_analysis_phases:
            _ = ap.progress_percent
            _ = ap.to_korean()

        # ServiceStatus: 모든 속성
        for ss in all_service_statuses:
            _ = ss.is_available
            _ = ss.is_healthy
            _ = ss.to_korean()

        # QueuePriority: to_korean
        for qp in all_queue_priorities:
            _ = qp.to_korean()

        # Environment: 모든 속성
        for env in all_environments:
            _ = env.is_production
            _ = env.is_development
            _ = env.is_testing
            _ = env.to_korean()

        # QualityLevel: 모든 속성
        for ql in all_quality_levels:
            _ = ql.description
            _ = ql.min_score
            _ = ql.max_score
            _ = ql.is_usable

        # TaskType: 모든 속성
        for tt in all_task_types:
            _ = tt.is_analysis
            _ = tt.is_report
            _ = tt.is_learning
            _ = tt.to_korean()

        # LearningStatus: 모든 속성
        for ls in all_learning_statuses:
            _ = ls.is_active
            _ = ls.is_terminal
            _ = ls.can_trigger_learning
            _ = ls.to_korean()

    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_ms = elapsed_ns / 1_000_000
    r.info(f"1K x 91멤버 전체 속성 접근: {elapsed_ms:.1f}ms")
    # 제한: 500ms = 500,000us
    _check(r, "대량 처리 (1000 반복)", elapsed_ms * 1000, 500_000)


def main():
    r = PerfResult()
    test_module_import(r)                  # [1]  측정: 1
    test_task_status_properties(r)         # [2]  측정: 5
    test_task_status_to_korean(r)          # [3]  측정: 1
    test_analysis_type_category(r)         # [4]  측정: 2
    test_analysis_type_to_korean(r)        # [5]  측정: 1
    test_analysis_phase_progress(r)        # [6]  측정: 1
    test_analysis_phase_to_korean(r)       # [7]  측정: 1
    test_service_status_properties(r)      # [8]  측정: 3
    test_queue_priority_to_korean(r)       # [9]  측정: 1
    test_environment_properties(r)         # [10] 측정: 4
    test_quality_level_properties(r)       # [11] 측정: 4
    test_quality_level_from_score(r)       # [12] 측정: 3
    test_task_type_properties(r)           # [13] 측정: 4
    test_learning_status_properties(r)     # [14] 측정: 4
    test_is_valid_transition(r)            # [15] 측정: 2
    test_enum_iteration(r)                 # [16] 측정: 1
    test_frozenset_direct_membership(r)    # [17] 측정: 2
    test_dict_cache_direct_lookup(r)       # [18] 측정: 2
    test_composite_task_lifecycle(r)       # [19] 측정: 1
    test_composite_analysis_pipeline(r)    # [20] 측정: 1
    test_memory_usage(r)                   # [21] 측정: 1
    test_bulk_operations(r)                # [22] 측정: 1
    # 총: 22 테스트 섹션, 45 측정
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
