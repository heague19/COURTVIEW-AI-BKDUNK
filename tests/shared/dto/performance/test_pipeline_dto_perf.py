# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_pipeline_dto_perf.py

파이프라인 DTO 성능 테스트
- 모듈 임포트 시간
- Pydantic 모델 인스턴스 생성 속도
- 프로퍼티 접근 속도 (ViolationCounts.total, FoulCounts.total)
- field_validator / model_validator 포함 생성 속도
- 대량 배치 처리

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {test_name}: {elapsed_us:.2f}μs ({ratio:.0f}% of {limit_us:.0f}μs limit)")

    def fail(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {elapsed_us:.2f}μs > {limit_us:.0f}μs")
        print(f"  [FAIL] {test_name}: {elapsed_us:.2f}μs (limit: {limit_us:.0f}μs)")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (μs/회)"""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.pipeline_dto"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000
    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. Pydantic 모델 생성 ====================
def test_video_metadata_creation(r: PerfResult) -> None:
    """VideoMetadata 생성 속도 (model_validator 포함)"""
    from shared.dto.pipeline_dto import VideoMetadata, VideoSource

    def create():
        VideoMetadata(
            source_type=VideoSource.LOCAL_FILE,
            source_path="/video/game.mp4",
            filename="game.mp4",
            duration_seconds=3600.0,
            width=1920, height=1080, fps=30.0,
        )

    elapsed = measure(create, 20000)
    limit = 50.0
    if elapsed < limit:
        r.ok("VideoMetadata 생성", elapsed, limit)
    else:
        r.fail("VideoMetadata 생성", elapsed, limit)


def test_pipeline_options_creation(r: PerfResult) -> None:
    """PipelineOptions 생성 속도"""
    from shared.dto.pipeline_dto import PipelineOptions

    def create():
        PipelineOptions(
            quality="high",
            target_fps=30,
            detection_confidence=0.7,
            start_time=10.0, end_time=60.0,
        )

    elapsed = measure(create, 20000)
    limit = 50.0
    if elapsed < limit:
        r.ok("PipelineOptions 생성", elapsed, limit)
    else:
        r.fail("PipelineOptions 생성", elapsed, limit)


def test_game_analysis_request_creation(r: PerfResult) -> None:
    """GameAnalysisRequest 생성 속도 (field_validator 포함)"""
    from shared.dto.pipeline_dto import GameAnalysisRequest, VideoMetadata
    from shared.constants.status_codes import AnalysisType

    vm = VideoMetadata(source_path="/game.mp4")

    def create():
        GameAnalysisRequest(
            analysis_type=AnalysisType.GAME_FULL,
            video=vm,
            home_team_id="team_a",
            away_team_id="team_b",
        )

    elapsed = measure(create, 10000)
    limit = 100.0
    if elapsed < limit:
        r.ok("GameAnalysisRequest 생성", elapsed, limit)
    else:
        r.fail("GameAnalysisRequest 생성", elapsed, limit)


def test_referee_analysis_request_creation(r: PerfResult) -> None:
    """RefereeAnalysisRequest 생성 속도"""
    from shared.dto.pipeline_dto import RefereeAnalysisRequest, VideoMetadata
    from shared.constants.referee_rule_constants import RuleSet

    vm = VideoMetadata(source_path="/game.mp4")

    def create():
        RefereeAnalysisRequest(
            video=vm,
            rule_set=RuleSet.FIBA,
            sensitivity="high",
        )

    elapsed = measure(create, 10000)
    limit = 100.0
    if elapsed < limit:
        r.ok("RefereeAnalysisRequest 생성", elapsed, limit)
    else:
        r.fail("RefereeAnalysisRequest 생성", elapsed, limit)


def test_pipeline_progress_creation(r: PerfResult) -> None:
    """PipelineProgress 생성 속도"""
    from shared.dto.pipeline_dto import PipelineProgress
    from shared.constants.status_codes import TaskStatus, AnalysisPhase

    tid = uuid4()
    rid = uuid4()

    def create():
        PipelineProgress(
            task_id=tid, request_id=rid,
            status=TaskStatus.RUNNING,
            phase=AnalysisPhase.DETECTING,
            progress_percent=55.0,
            current_frame=2000, total_frames=5000,
        )

    elapsed = measure(create, 20000)
    limit = 50.0
    if elapsed < limit:
        r.ok("PipelineProgress 생성", elapsed, limit)
    else:
        r.fail("PipelineProgress 생성", elapsed, limit)


def test_violation_counts_creation(r: PerfResult) -> None:
    """ViolationCounts 생성 속도"""
    from shared.dto.pipeline_dto import ViolationCounts

    def create():
        ViolationCounts(
            traveling=3, double_dribble=2, carrying=1,
            three_seconds=4, shot_clock=2, out_of_bounds=5,
        )

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("ViolationCounts 생성", elapsed, limit)
    else:
        r.fail("ViolationCounts 생성", elapsed, limit)


def test_foul_counts_creation(r: PerfResult) -> None:
    """FoulCounts 생성 속도"""
    from shared.dto.pipeline_dto import FoulCounts

    def create():
        FoulCounts(personal=10, offensive=3, technical=2, flagrant=1)

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("FoulCounts 생성", elapsed, limit)
    else:
        r.fail("FoulCounts 생성", elapsed, limit)


def test_backend_sync_payload_creation(r: PerfResult) -> None:
    """BackendSyncPayload 생성 속도"""
    from shared.dto.pipeline_dto import BackendSyncPayload, SyncEventType
    from shared.constants.status_codes import TaskStatus, AnalysisType

    now = datetime.now(timezone.utc)
    tid = uuid4()
    rid = uuid4()

    def create():
        BackendSyncPayload(
            task_id=tid, request_id=rid,
            analysis_type=AnalysisType.GAME_FULL,
            success=True, status=TaskStatus.COMPLETED,
            processing_time_seconds=120.0,
            completed_at=now,
            summary={"score": 78},
        )

    elapsed = measure(create, 20000)
    limit = 50.0
    if elapsed < limit:
        r.ok("BackendSyncPayload 생성", elapsed, limit)
    else:
        r.fail("BackendSyncPayload 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_violation_foul_total_property(r: PerfResult) -> None:
    """ViolationCounts/FoulCounts total 프로퍼티 속도"""
    from shared.dto.pipeline_dto import ViolationCounts, FoulCounts

    vc = ViolationCounts(traveling=3, double_dribble=2, carrying=1, three_seconds=4)
    fc = FoulCounts(personal=10, offensive=3, technical=2, flagrant=1)

    def access():
        _ = vc.total
        _ = fc.total

    elapsed = measure(access, 100000)
    per_call = elapsed / 2
    limit = 2.0
    if per_call < limit:
        r.ok("total 프로퍼티", per_call, limit)
    else:
        r.fail("total 프로퍼티", per_call, limit)


def test_referee_result_properties(r: PerfResult) -> None:
    """RefereeAnalysisResult total_violations/total_fouls 프로퍼티 속도"""
    from shared.dto.pipeline_dto import (
        RefereeAnalysisResult, ViolationCounts, FoulCounts,
    )
    from shared.constants.status_codes import TaskStatus, AnalysisType
    from shared.constants.referee_rule_constants import RuleSet

    now = datetime.now(timezone.utc)
    result = RefereeAnalysisResult(
        task_id=uuid4(), request_id=uuid4(),
        analysis_type=AnalysisType.REFEREE_FULL,
        status=TaskStatus.COMPLETED, success=True,
        started_at=now, completed_at=now,
        processing_time_seconds=180.0,
        total_frames=5400, processed_frames=5400, average_fps=30.0,
        rule_set=RuleSet.FIBA,
        violation_counts=ViolationCounts(traveling=3, double_dribble=2),
        foul_counts=FoulCounts(personal=8, offensive=2),
    )

    def access():
        _ = result.total_violations
        _ = result.total_fouls

    elapsed = measure(access, 100000)
    per_call = elapsed / 2
    limit = 2.0
    if per_call < limit:
        r.ok("RefereeResult 프로퍼티", per_call, limit)
    else:
        r.fail("RefereeResult 프로퍼티", per_call, limit)


# ==================== 4. 대량 처리 ====================
def test_batch_progress_updates(r: PerfResult) -> None:
    """PipelineProgress 20개 배치 생성"""
    from shared.dto.pipeline_dto import PipelineProgress
    from shared.constants.status_codes import TaskStatus, AnalysisPhase

    tid = uuid4()
    rid = uuid4()
    phases = list(AnalysisPhase)

    def batch():
        for i in range(20):
            PipelineProgress(
                task_id=tid, request_id=rid,
                status=TaskStatus.RUNNING,
                phase=phases[i % len(phases)],
                progress_percent=i * 5.0,
                current_frame=i * 100,
                total_frames=2000,
            )

    elapsed = measure(batch, 2000)
    limit = 1500.0
    if elapsed < limit:
        r.ok("PipelineProgress×20", elapsed, limit)
    else:
        r.fail("PipelineProgress×20", elapsed, limit)


def test_full_game_result_snapshot(r: PerfResult) -> None:
    """풀 GameAnalysisResult 스냅샷 생성"""
    from shared.dto.pipeline_dto import GameAnalysisResult
    from shared.constants.status_codes import TaskStatus, AnalysisType

    now = datetime.now(timezone.utc)

    def create():
        GameAnalysisResult(
            task_id=uuid4(), request_id=uuid4(),
            analysis_type=AnalysisType.GAME_FULL,
            status=TaskStatus.COMPLETED, success=True,
            started_at=now, completed_at=now,
            processing_time_seconds=300.0,
            total_frames=10800, processed_frames=10800,
            average_fps=36.0,
            home_team_id="team_a", away_team_id="team_b",
            home_score=78, away_score=72,
            total_shots=120, total_baskets=60,
            total_assists=25, total_rebounds=80,
            total_turnovers=15,
        )

    elapsed = measure(create, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("풀 GameAnalysisResult", elapsed, limit)
    else:
        r.fail("풀 GameAnalysisResult", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("pipeline_dto.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- Pydantic 모델 생성 ---")
    test_video_metadata_creation(r)
    test_pipeline_options_creation(r)
    test_game_analysis_request_creation(r)
    test_referee_analysis_request_creation(r)
    test_pipeline_progress_creation(r)
    test_violation_counts_creation(r)
    test_foul_counts_creation(r)
    test_backend_sync_payload_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_violation_foul_total_property(r)
    test_referee_result_properties(r)

    print("\n--- 대량 처리 ---")
    test_batch_progress_updates(r)
    test_full_game_result_snapshot(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
