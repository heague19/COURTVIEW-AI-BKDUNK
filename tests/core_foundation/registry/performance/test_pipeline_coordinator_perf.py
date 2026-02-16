# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/registry/performance
파일: test_pipeline_coordinator_perf.py
설명: 파이프라인 코디네이터 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12

테스트 범위:
    [P1] Enum 연산 성능 (4개) - PipelineType/StageType/StageStatus/PipelineStatus
    [P2] 데이터 클래스 생성 성능 (4개) - StageConfig/StageResult/PipelineConfig/PipelineProgress/PipelineContext
    [P3] PipelineBuilder 빌드 성능 (3개) - 빌더 생성, 스테이지 추가, 파이프라인 빌드
    [P4] PipelineTemplates 팩토리 성능 (3개) - 다양한 템플릿 생성
    [P5] PipelineCoordinator 기본 성능 (3개) - 코디네이터 생성, 핸들러 등록, 상태 조회
    [P6] CheckpointManager 성능 (3개) - 체크포인트 저장/복원/정리
    [P7] 멀티스레드 동시 접근 (3개) - 동시 생성/조회
    [P8] 메모리 사용량 (3개) - 코디네이터/설정/체크포인트 메모리

    총 26개 테스트
"""

import gc
import json
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.registry.pipeline_coordinator import (
    # Enum (4개)
    PipelineType,
    StageType,
    StageStatus,
    PipelineStatus,
    # 예외 클래스 (4개)
    PipelineException,
    StageExecutionError,
    PipelineTimeoutError,
    PipelineConfigError,
    # 상수 (5개)
    DEFAULT_STAGE_TIMEOUT,
    DEFAULT_PIPELINE_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    MAX_CONCURRENT_PIPELINES,
    # 데이터 클래스 (6개)
    StageConfig,
    StageResult,
    PipelineConfig,
    PipelineProgress,
    CheckpointData,
    PipelineContext,
    # 메인 클래스 (4개)
    CheckpointManager,
    PipelineCoordinator,
    PipelineBuilder,
    PipelineTemplates,
    # 전역 함수 (3개)
    get_coordinator,
    create_pipeline,
    _reset_coordinator,
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


def measure_time_ms(func, iterations: int = 1000) -> float:
    """평균 실행 시간 (밀리초) 측정."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return (elapsed / iterations) * 1000


def get_object_size(obj) -> int:
    """객체 대략적 메모리 크기 (바이트) 측정."""
    return sys.getsizeof(obj)


# 테스트용 비동기 핸들러 (실제 async 함수)
async def _dummy_handler(ctx):
    """테스트용 스테이지 핸들러."""
    return {"result": "ok"}


async def _dummy_handler_alt(ctx):
    """테스트용 대체 스테이지 핸들러."""
    return {"result": "alt_ok"}


# =============================================================================
# [P1] Enum 연산 성능 (4개)
# =============================================================================
def test_p1_enum_performance(result: PerformanceTestResult) -> None:
    """Enum 연산 성능 테스트."""
    print("\n[P1] Enum 연산 성능")

    # P1-1. PipelineType 순회 및 프로퍼티 접근 처리량
    try:
        all_types = list(PipelineType)
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            for pt in all_types:
                _ = pt.value
                _ = pt.category
        elapsed = time.perf_counter() - start
        total_ops = iterations * len(all_types) * 2  # value + category
        ops = total_ops / elapsed
        per_call = (elapsed / total_ops) * 1_000_000
        result.ok(
            "P1-1 PipelineType 순회+프로퍼티 ({0}개 타입)".format(len(all_types)),
            f"{ops:,.0f} ops/sec, {per_call:.2f}us/call",
        )
    except Exception as e:
        result.fail("P1-1 PipelineType 순회+프로퍼티", str(e))

    # P1-2. StageType 순회 및 프로퍼티 접근 처리량
    try:
        all_stages = list(StageType)
        iterations = 20_000
        start = time.perf_counter()
        for _ in range(iterations):
            for st in all_stages:
                _ = st.value
                _ = st.phase
        elapsed = time.perf_counter() - start
        total_ops = iterations * len(all_stages) * 2  # value + phase
        ops = total_ops / elapsed
        per_call = (elapsed / total_ops) * 1_000_000
        result.ok(
            "P1-2 StageType 순회+phase ({0}개 타입)".format(len(all_stages)),
            f"{ops:,.0f} ops/sec, {per_call:.2f}us/call",
        )
    except Exception as e:
        result.fail("P1-2 StageType 순회+phase", str(e))

    # P1-3. StageStatus is_terminal/is_success 처리량
    try:
        all_statuses = list(StageStatus)
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            for ss in all_statuses:
                _ = ss.is_terminal
                _ = ss.is_success
        elapsed = time.perf_counter() - start
        total_ops = iterations * len(all_statuses) * 2
        ops = total_ops / elapsed
        per_call = (elapsed / total_ops) * 1_000_000
        result.ok(
            "P1-3 StageStatus is_terminal/is_success ({0}개 상태)".format(len(all_statuses)),
            f"{ops:,.0f} ops/sec, {per_call:.2f}us/call",
        )
    except Exception as e:
        result.fail("P1-3 StageStatus 프로퍼티", str(e))

    # P1-4. PipelineStatus is_terminal/is_success + Enum 비교 처리량
    try:
        all_pstatus = list(PipelineStatus)
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            for ps in all_pstatus:
                _ = ps.is_terminal
                _ = ps.is_success
                _ = ps == PipelineStatus.COMPLETED
                _ = ps != PipelineStatus.FAILED
        elapsed = time.perf_counter() - start
        total_ops = iterations * len(all_pstatus) * 4
        ops = total_ops / elapsed
        result.ok(
            "P1-4 PipelineStatus 프로퍼티+비교 ({0}개 상태)".format(len(all_pstatus)),
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P1-4 PipelineStatus 프로퍼티+비교", str(e))


# =============================================================================
# [P2] 데이터 클래스 생성 성능 (4개)
# =============================================================================
def test_p2_dataclass_creation(result: PerformanceTestResult) -> None:
    """데이터 클래스 생성 성능 테스트."""
    print("\n[P2] 데이터 클래스 생성 성능")

    # P2-1. StageConfig 생성 처리량
    try:
        ops = measure_ops(
            lambda: StageConfig(
                stage_type=StageType.POSE_ESTIMATION,
                handler=_dummy_handler,
                timeout_seconds=120.0,
                max_retries=3,
                skip_on_failure=False,
                dependencies=[StageType.PERSON_DETECTION],
            ),
            iterations=50_000,
        )
        result.ok("P2-1 StageConfig 생성", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-1 StageConfig 생성", str(e))

    # P2-2. StageResult 생성 + to_dict 처리량
    try:
        now = datetime.now(timezone.utc)

        def create_stage_result():
            sr = StageResult(
                stage_type=StageType.SHOOTING_ANALYSIS,
                status=StageStatus.COMPLETED,
                started_at=now,
                completed_at=now,
                duration_seconds=1.5,
                output={"accuracy": 0.92},
                retry_count=0,
            )
            sr.to_dict()

        ops = measure_ops(create_stage_result, iterations=30_000)
        result.ok("P2-2 StageResult 생성+to_dict", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-2 StageResult 생성+to_dict", str(e))

    # P2-3. PipelineConfig 생성 + stage_count 처리량
    try:
        stages = [
            StageConfig(stage_type=StageType.INITIALIZATION, handler=_dummy_handler),
            StageConfig(stage_type=StageType.VIDEO_DOWNLOAD, handler=_dummy_handler),
            StageConfig(stage_type=StageType.DETECTION, handler=_dummy_handler),
            StageConfig(stage_type=StageType.POSE_ESTIMATION, handler=_dummy_handler),
            StageConfig(stage_type=StageType.SHOOTING_ANALYSIS, handler=_dummy_handler),
        ]

        def create_pipeline_config():
            pc = PipelineConfig(
                pipeline_type=PipelineType.TRAINING_SHOOTING,
                stages=list(stages),
                timeout_seconds=1800.0,
                fail_fast=True,
            )
            _ = pc.stage_count

        ops = measure_ops(create_pipeline_config, iterations=30_000)
        result.ok("P2-3 PipelineConfig 생성+stage_count (5 스테이지)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-3 PipelineConfig 생성", str(e))

    # P2-4. PipelineProgress + PipelineContext 생성 처리량
    try:
        def create_progress_and_context():
            prog = PipelineProgress(
                pipeline_id="test-pipeline-001",
                pipeline_type=PipelineType.GAME_FULL,
                status=PipelineStatus.RUNNING,
                total_stages=10,
                completed_stages=5,
                failed_stages=0,
                skipped_stages=1,
                started_at=datetime.now(timezone.utc),
                elapsed_seconds=30.5,
            )
            ctx = PipelineContext(
                pipeline_id="test-pipeline-001",
                pipeline_type=PipelineType.GAME_FULL,
                input_data={"video_url": "https://example.com/video.mp4"},
                metadata={"user_id": "user-001"},
            )
            return prog, ctx

        ops = measure_ops(create_progress_and_context, iterations=20_000)
        result.ok("P2-4 PipelineProgress+PipelineContext 생성", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P2-4 PipelineProgress+PipelineContext 생성", str(e))


# =============================================================================
# [P3] PipelineBuilder 빌드 성능 (3개)
# =============================================================================
def test_p3_builder_performance(result: PerformanceTestResult) -> None:
    """PipelineBuilder 빌드 성능 테스트."""
    print("\n[P3] PipelineBuilder 빌드 성능")

    # P3-1. PipelineBuilder 생성 처리량
    try:
        ops = measure_ops(
            lambda: PipelineBuilder(PipelineType.TRAINING_SHOOTING),
            iterations=50_000,
        )
        result.ok("P3-1 PipelineBuilder() 생성", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-1 PipelineBuilder 생성", str(e))

    # P3-2. add_stage 체이닝 처리량 (5 스테이지)
    try:
        def build_with_stages():
            builder = PipelineBuilder(PipelineType.TRAINING_SHOOTING)
            builder.add_stage(StageType.INITIALIZATION, handler=_dummy_handler)
            builder.add_stage(StageType.VIDEO_DOWNLOAD, handler=_dummy_handler)
            builder.add_stage(StageType.DETECTION, handler=_dummy_handler)
            builder.add_stage(StageType.POSE_ESTIMATION, handler=_dummy_handler, timeout=120.0)
            builder.add_stage(StageType.SHOOTING_ANALYSIS, handler=_dummy_handler)
            return builder

        ops = measure_ops(build_with_stages, iterations=20_000)
        result.ok("P3-2 add_stage 체이닝 (5 스테이지)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-2 add_stage 체이닝", str(e))

    # P3-3. 전체 빌드 (생성 + 5 스테이지 + 옵션 + build) 처리량
    try:
        def full_build():
            config = (
                PipelineBuilder(PipelineType.TRAINING_SHOOTING)
                .add_stage(StageType.INITIALIZATION, handler=_dummy_handler)
                .add_stage(StageType.VIDEO_DOWNLOAD, handler=_dummy_handler)
                .add_stage(StageType.DETECTION, handler=_dummy_handler)
                .add_stage(StageType.POSE_ESTIMATION, handler=_dummy_handler, timeout=120.0)
                .add_stage(StageType.SHOOTING_ANALYSIS, handler=_dummy_handler)
                .with_timeout(1800)
                .with_fail_fast(True)
                .with_metadata("analysis_type", "shooting")
                .build()
            )
            return config

        ops = measure_ops(full_build, iterations=10_000)
        result.ok("P3-3 전체 빌드 (생성+5스테이지+옵션+build)", f"{ops:,.0f} ops/sec")
    except Exception as e:
        result.fail("P3-3 전체 빌드", str(e))


# =============================================================================
# [P4] PipelineTemplates 팩토리 성능 (3개)
# =============================================================================
def test_p4_templates_performance(result: PerformanceTestResult) -> None:
    """PipelineTemplates 팩토리 성능 테스트."""
    print("\n[P4] PipelineTemplates 팩토리 성능")

    # P4-1. training_shooting 템플릿 생성 처리량
    try:
        ops = measure_ops(
            lambda: PipelineTemplates.training_shooting(),
            iterations=5_000,
        )
        # 생성된 템플릿 검증
        config = PipelineTemplates.training_shooting()
        assert config.pipeline_type == PipelineType.TRAINING_SHOOTING
        assert config.stage_count > 0, f"스테이지 수: {config.stage_count}"
        result.ok(
            "P4-1 training_shooting 템플릿 ({0} 스테이지)".format(config.stage_count),
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P4-1 training_shooting 템플릿", str(e))

    # P4-2. game_full 템플릿 생성 처리량
    try:
        ops = measure_ops(
            lambda: PipelineTemplates.game_full(),
            iterations=5_000,
        )
        config = PipelineTemplates.game_full()
        assert config.pipeline_type == PipelineType.GAME_FULL
        assert config.stage_count > 0
        result.ok(
            "P4-2 game_full 템플릿 ({0} 스테이지)".format(config.stage_count),
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P4-2 game_full 템플릿", str(e))

    # P4-3. 전체 템플릿 5종 순차 생성 처리량
    try:
        def create_all_templates():
            PipelineTemplates.training_shooting()
            PipelineTemplates.training_dribbling()
            PipelineTemplates.training_comparison()
            PipelineTemplates.game_full()
            PipelineTemplates.referee_full()

        ops = measure_ops(create_all_templates, iterations=2_000)
        result.ok("P4-3 전체 5종 템플릿 순차 생성", f"{ops:,.0f} ops/sec (세트 기준)")
    except Exception as e:
        result.fail("P4-3 전체 템플릿 생성", str(e))


# =============================================================================
# [P5] PipelineCoordinator 기본 성능 (3개)
# =============================================================================
def test_p5_coordinator_performance(result: PerformanceTestResult) -> None:
    """PipelineCoordinator 기본 성능 테스트."""
    print("\n[P5] PipelineCoordinator 기본 성능")

    # P5-1. PipelineCoordinator 생성 처리량
    try:
        _reset_coordinator()
        times = []
        for _ in range(20):
            with tempfile.TemporaryDirectory() as tmpdir:
                cm = CheckpointManager(storage_path=tmpdir)
                start = time.perf_counter()
                coord = PipelineCoordinator(checkpoint_manager=cm)
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
        avg = sum(times) / len(times)
        result.ok(
            "P5-1 PipelineCoordinator 생성 (20회 평균)",
            f"{avg:.2f}ms/call",
        )
    except Exception as e:
        result.fail("P5-1 PipelineCoordinator 생성", str(e))

    # P5-2. register_handler / get_handler 처리량
    try:
        _reset_coordinator()
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            coord = PipelineCoordinator(checkpoint_manager=cm)

            # 핸들러 등록 처리량
            stage_types = list(StageType)
            iterations = 10_000
            start = time.perf_counter()
            for i in range(iterations):
                st = stage_types[i % len(stage_types)]
                coord.register_handler(st, _dummy_handler)
            elapsed = time.perf_counter() - start
            register_ops = iterations / elapsed

            # 핸들러 조회 처리량
            iterations_get = 50_000
            start = time.perf_counter()
            for i in range(iterations_get):
                st = stage_types[i % len(stage_types)]
                coord.get_handler(st)
            elapsed = time.perf_counter() - start
            get_ops = iterations_get / elapsed

        result.ok(
            "P5-2 register_handler/get_handler",
            f"등록: {register_ops:,.0f} ops/sec, 조회: {get_ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P5-2 register/get_handler", str(e))

    # P5-3. get_status / active_count 처리량
    try:
        _reset_coordinator()
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            coord = PipelineCoordinator(checkpoint_manager=cm)
            # 핸들러 몇 개 등록하여 상태에 데이터 추가
            for st in [StageType.INITIALIZATION, StageType.DETECTION, StageType.POSE_ESTIMATION]:
                coord.register_handler(st, _dummy_handler)

            # get_status 처리량
            iterations = 20_000
            start = time.perf_counter()
            for _ in range(iterations):
                coord.get_status()
            elapsed = time.perf_counter() - start
            status_ops = iterations / elapsed

            # active_count 프로퍼티 처리량
            iterations_ac = 100_000
            start = time.perf_counter()
            for _ in range(iterations_ac):
                _ = coord.active_count
            elapsed = time.perf_counter() - start
            ac_ops = iterations_ac / elapsed

        result.ok(
            "P5-3 get_status/active_count",
            f"status: {status_ops:,.0f} ops/sec, active_count: {ac_ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P5-3 get_status/active_count", str(e))


# =============================================================================
# [P6] CheckpointManager 성능 (3개)
# =============================================================================
def test_p6_checkpoint_performance(result: PerformanceTestResult) -> None:
    """CheckpointManager 성능 테스트."""
    print("\n[P6] CheckpointManager 성능")

    # P6-1. 체크포인트 저장 처리량
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)

            # 체크포인트 데이터 준비
            checkpoints = []
            for i in range(100):
                cp = CheckpointData(
                    pipeline_id=f"pipeline-{i:04d}",
                    pipeline_type=PipelineType.TRAINING_SHOOTING,
                    completed_stages=[StageType.INITIALIZATION, StageType.VIDEO_DOWNLOAD],
                    current_stage_index=2,
                    stage_outputs={
                        StageType.INITIALIZATION.value: {"status": "ok"},
                        StageType.VIDEO_DOWNLOAD.value: {"frames": 1200},
                    },
                    metadata={"user_id": f"user-{i:04d}", "session": f"sess-{i:04d}"},
                    created_at=datetime.now(timezone.utc),
                )
                checkpoints.append(cp)

            # 저장 처리량 측정
            start = time.perf_counter()
            for cp in checkpoints:
                saved = cm.save(cp)
                assert saved, f"체크포인트 저장 실패: {cp.pipeline_id}"
            elapsed = time.perf_counter() - start
            ops = 100 / elapsed
            per_call_ms = (elapsed / 100) * 1000

        result.ok(
            "P6-1 체크포인트 저장 (100개)",
            f"{ops:,.0f} ops/sec, {per_call_ms:.2f}ms/call",
        )
    except Exception as e:
        result.fail("P6-1 체크포인트 저장", str(e))

    # P6-2. 체크포인트 복원 (load) 처리량
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)

            # 사전 저장
            for i in range(50):
                cp = CheckpointData(
                    pipeline_id=f"pipeline-{i:04d}",
                    pipeline_type=PipelineType.GAME_FULL,
                    completed_stages=[
                        StageType.INITIALIZATION,
                        StageType.VIDEO_DOWNLOAD,
                        StageType.DETECTION,
                    ],
                    current_stage_index=3,
                    stage_outputs={
                        StageType.INITIALIZATION.value: {"ready": True},
                        StageType.VIDEO_DOWNLOAD.value: {"path": "/tmp/video.mp4"},
                        StageType.DETECTION.value: {"objects": 15},
                    },
                    metadata={"user_id": f"user-{i:04d}"},
                    created_at=datetime.now(timezone.utc),
                )
                cm.save(cp)

            # 복원 처리량 측정
            iterations = 200
            start = time.perf_counter()
            for _ in range(iterations // 50):
                for i in range(50):
                    loaded = cm.load(f"pipeline-{i:04d}")
                    assert loaded is not None, f"체크포인트 로드 실패: pipeline-{i:04d}"
            elapsed = time.perf_counter() - start
            ops = iterations / elapsed
            per_call_ms = (elapsed / iterations) * 1000

        result.ok(
            "P6-2 체크포인트 복원 (50개 반복)",
            f"{ops:,.0f} ops/sec, {per_call_ms:.2f}ms/call",
        )
    except Exception as e:
        result.fail("P6-2 체크포인트 복원", str(e))

    # P6-3. 체크포인트 목록 조회 + 삭제 처리량
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)

            # 30개 체크포인트 저장
            for i in range(30):
                cp = CheckpointData(
                    pipeline_id=f"pipeline-{i:04d}",
                    pipeline_type=PipelineType.REFEREE_FULL,
                    completed_stages=[StageType.INITIALIZATION],
                    current_stage_index=1,
                    stage_outputs={StageType.INITIALIZATION.value: {"ok": True}},
                    metadata={},
                    created_at=datetime.now(timezone.utc),
                )
                cm.save(cp)

            # list_checkpoints 처리량
            iterations_list = 1_000
            start = time.perf_counter()
            for _ in range(iterations_list):
                cps = cm.list_checkpoints()
            elapsed = time.perf_counter() - start
            list_ops = iterations_list / elapsed
            assert len(cps) == 30, f"체크포인트 수: {len(cps)} != 30"

            # delete 처리량
            start = time.perf_counter()
            for i in range(30):
                cm.delete(f"pipeline-{i:04d}")
            elapsed = time.perf_counter() - start
            delete_ops = 30 / elapsed if elapsed > 0 else float("inf")

            # 삭제 확인
            remaining = cm.list_checkpoints()
            assert len(remaining) == 0, f"남은 체크포인트: {len(remaining)}"

        result.ok(
            "P6-3 list_checkpoints/delete",
            f"목록: {list_ops:,.0f} ops/sec, 삭제: {delete_ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P6-3 목록/삭제", str(e))


# =============================================================================
# [P7] 멀티스레드 동시 접근 (3개)
# =============================================================================
def test_p7_multithread_performance(result: PerformanceTestResult) -> None:
    """멀티스레드 동시 접근 성능 테스트."""
    print("\n[P7] 멀티스레드 동시 접근")

    # P7-1. PipelineConfig 동시 생성 (4스레드)
    try:
        errors = []
        n_threads = 4
        n_ops = 5_000
        results_list = []

        def config_creator(tid):
            try:
                start = time.perf_counter()
                for i in range(n_ops):
                    pipeline_type = list(PipelineType)[tid % len(list(PipelineType))]
                    config = PipelineConfig(
                        pipeline_type=pipeline_type,
                        stages=[
                            StageConfig(
                                stage_type=StageType.INITIALIZATION,
                                handler=_dummy_handler,
                            ),
                            StageConfig(
                                stage_type=StageType.DETECTION,
                                handler=_dummy_handler,
                            ),
                        ],
                    )
                    _ = config.stage_count
                elapsed = time.perf_counter() - start
                results_list.append(elapsed)
            except Exception as ex:
                errors.append(str(ex))

        barrier = threading.Barrier(n_threads)

        def worker(tid):
            barrier.wait()
            config_creator(tid)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"에러: {errors}"
        total_ops = n_threads * n_ops
        max_elapsed = max(results_list) if results_list else 1
        ops = total_ops / max_elapsed
        result.ok(
            "P7-1 PipelineConfig 동시 생성 (4x{0})".format(n_ops),
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P7-1 PipelineConfig 동시 생성", str(e))

    # P7-2. PipelineCoordinator get_status 동시 접근
    try:
        _reset_coordinator()
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            coord = PipelineCoordinator(checkpoint_manager=cm)
            # 핸들러 등록
            for st in [StageType.INITIALIZATION, StageType.DETECTION, StageType.POSE_ESTIMATION]:
                coord.register_handler(st, _dummy_handler)

            errors = []
            n_threads = 4
            n_ops = 5_000
            results_list = []
            barrier = threading.Barrier(n_threads)

            def status_worker():
                barrier.wait()
                try:
                    start = time.perf_counter()
                    for _ in range(n_ops):
                        coord.get_status()
                    elapsed = time.perf_counter() - start
                    results_list.append(elapsed)
                except Exception as ex:
                    errors.append(str(ex))

            threads = [threading.Thread(target=status_worker) for _ in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

            assert len(errors) == 0, f"에러: {errors}"
            total_ops = n_threads * n_ops
            max_elapsed = max(results_list) if results_list else 1
            ops = total_ops / max_elapsed

        result.ok(
            "P7-2 get_status 4스레드 동시 접근 ({0}x{1})".format(n_threads, n_ops),
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P7-2 get_status 동시 접근", str(e))

    # P7-3. register_handler + get_handler 동시 접근
    try:
        _reset_coordinator()
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            coord = PipelineCoordinator(checkpoint_manager=cm)
            all_stage_types = list(StageType)

            errors = []
            n_threads = 4
            n_ops = 3_000
            results_list = []
            barrier = threading.Barrier(n_threads)

            def handler_worker(tid):
                barrier.wait()
                try:
                    start = time.perf_counter()
                    for i in range(n_ops):
                        st = all_stage_types[i % len(all_stage_types)]
                        if tid % 2 == 0:
                            # 짝수 스레드: 등록
                            coord.register_handler(st, _dummy_handler)
                        else:
                            # 홀수 스레드: 조회
                            coord.get_handler(st)
                    elapsed = time.perf_counter() - start
                    results_list.append(elapsed)
                except Exception as ex:
                    errors.append(str(ex))

            threads = [threading.Thread(target=handler_worker, args=(i,)) for i in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

            assert len(errors) == 0, f"에러: {errors}"
            total_ops = n_threads * n_ops
            max_elapsed = max(results_list) if results_list else 1
            ops = total_ops / max_elapsed

        result.ok(
            "P7-3 register+get_handler 4스레드 동시 접근 ({0}x{1})".format(n_threads, n_ops),
            f"{ops:,.0f} ops/sec",
        )
    except Exception as e:
        result.fail("P7-3 handler 동시 접근", str(e))


# =============================================================================
# [P8] 메모리 사용량 (3개)
# =============================================================================
def test_p8_memory_usage(result: PerformanceTestResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[P8] 메모리 사용량")

    # P8-1. PipelineCoordinator 인스턴스 메모리
    try:
        _reset_coordinator()
        gc.collect()
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            coord = PipelineCoordinator(checkpoint_manager=cm)
            obj_size = get_object_size(coord)
        result.ok(
            "P8-1 PipelineCoordinator 인스턴스 메모리",
            f"~{obj_size}B",
        )
    except Exception as e:
        result.fail("P8-1 PipelineCoordinator 메모리", str(e))

    # P8-2. PipelineConfig 대량 생성 메모리
    try:
        gc.collect()
        configs = []
        for i in range(500):
            config = PipelineConfig(
                pipeline_type=list(PipelineType)[i % len(list(PipelineType))],
                stages=[
                    StageConfig(
                        stage_type=StageType.INITIALIZATION,
                        handler=_dummy_handler,
                    ),
                    StageConfig(
                        stage_type=StageType.VIDEO_DOWNLOAD,
                        handler=_dummy_handler,
                    ),
                    StageConfig(
                        stage_type=StageType.DETECTION,
                        handler=_dummy_handler,
                    ),
                    StageConfig(
                        stage_type=StageType.POSE_ESTIMATION,
                        handler=_dummy_handler,
                    ),
                    StageConfig(
                        stage_type=StageType.SHOOTING_ANALYSIS,
                        handler=_dummy_handler,
                    ),
                ],
                timeout_seconds=1800.0,
                metadata={"index": i},
            )
            configs.append(config)

        sample_size = get_object_size(configs[0])
        result.ok(
            "P8-2 PipelineConfig 500개 메모리 (5 스테이지/각)",
            f"개당 ~{sample_size}B",
        )
    except Exception as e:
        result.fail("P8-2 PipelineConfig 메모리", str(e))

    # P8-3. CheckpointData 대량 생성 메모리
    try:
        gc.collect()
        checkpoints = []
        for i in range(500):
            cp = CheckpointData(
                pipeline_id=f"pipeline-{i:04d}",
                pipeline_type=PipelineType.TRAINING_SHOOTING,
                completed_stages=[
                    StageType.INITIALIZATION,
                    StageType.VIDEO_DOWNLOAD,
                    StageType.DETECTION,
                ],
                current_stage_index=3,
                stage_outputs={
                    StageType.INITIALIZATION.value: {"status": "ok"},
                    StageType.VIDEO_DOWNLOAD.value: {"frames": 1200, "path": "/tmp/test.mp4"},
                    StageType.DETECTION.value: {"persons": 5, "balls": 1, "court": True},
                },
                metadata={
                    "user_id": f"user-{i:04d}",
                    "session": f"sess-{i:04d}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                created_at=datetime.now(timezone.utc),
            )
            checkpoints.append(cp)

        sample_size = get_object_size(checkpoints[0])
        # to_dict 직렬화 크기 확인
        dict_data = checkpoints[0].to_dict()
        json_str = json.dumps(dict_data, ensure_ascii=False)
        json_size = len(json_str.encode("utf-8"))

        result.ok(
            "P8-3 CheckpointData 500개 메모리",
            f"개당 ~{sample_size}B, JSON 직렬화: ~{json_size}B",
        )
    except Exception as e:
        result.fail("P8-3 CheckpointData 메모리", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 성능 테스트 실행."""
    print("=" * 60)
    print("COURTVIEW - pipeline_coordinator.py 성능 테스트")
    print("=" * 60)

    result = PerformanceTestResult()

    # [P1] Enum 연산 성능
    test_p1_enum_performance(result)

    # [P2] 데이터 클래스 생성 성능
    test_p2_dataclass_creation(result)

    # [P3] PipelineBuilder 빌드 성능
    test_p3_builder_performance(result)

    # [P4] PipelineTemplates 팩토리 성능
    test_p4_templates_performance(result)

    # [P5] PipelineCoordinator 기본 성능
    test_p5_coordinator_performance(result)

    # [P6] CheckpointManager 성능
    test_p6_checkpoint_performance(result)

    # [P7] 멀티스레드 동시 접근
    test_p7_multithread_performance(result)

    # [P8] 메모리 사용량
    test_p8_memory_usage(result)

    # 최종 정리
    _reset_coordinator()

    # 요약 출력
    result.summary()

    # 종료 코드
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
