# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_dataset_dto_perf.py

데이터셋 DTO 성능 테스트
- 모듈 임포트 시간
- 데이터클래스 인스턴스 생성 속도
- 프로퍼티 접근 속도
- UUID 생성 속도
- 대량 레코드 생성 속도

성능 기준:
- 모듈 임포트: < 500ms (cold)
- 데이터클래스 생성: < 10μs
- 프로퍼티 접근: < 5μs
- UUID 생성: < 10μs

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path

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

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

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


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.dataset_dto"
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


# ==================== 2. 데이터클래스 생성 ====================
def test_shot_trajectory_record_creation(r: PerfResult) -> None:
    """ShotTrajectoryRecord 생성 속도"""
    from shared.dto.dataset_dto import ShotTrajectoryRecord

    pts = [(float(i), float(i), float(i)) for i in range(10)]
    frames = list(range(10))

    def create():
        ShotTrajectoryRecord(
            trajectory_points=pts,
            ball_detected=True,
            shot_result="made",
            frame_indices=frames,
            camera_id="cam_01",
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("ShotTrajectoryRecord 생성", elapsed, limit)
    else:
        r.fail("ShotTrajectoryRecord 생성", elapsed, limit)


def test_player_bbox_record_creation(r: PerfResult) -> None:
    """PlayerBboxRecord 생성 속도"""
    from shared.dto.dataset_dto import PlayerBboxRecord

    def create():
        PlayerBboxRecord(
            bbox=(0.1, 0.2, 0.3, 0.4),
            class_label="player",
            confidence=0.95,
            frame_index=100,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("PlayerBboxRecord 생성", elapsed, limit)
    else:
        r.fail("PlayerBboxRecord 생성", elapsed, limit)


def test_frame_record_creation(r: PerfResult) -> None:
    """FrameRecord 생성 속도"""
    from shared.dto.dataset_dto import FrameRecord

    def create():
        FrameRecord(frame_index=100, camera_id="cam_01")

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("FrameRecord 생성", elapsed, limit)
    else:
        r.fail("FrameRecord 생성", elapsed, limit)


def test_extraction_result_creation(r: PerfResult) -> None:
    """ExtractionResult 생성 속도 (UUID 포함)"""
    from shared.dto.dataset_dto import ExtractionResult

    def create():
        ExtractionResult(game_id="game_001", record_count=1000)

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("ExtractionResult 생성", elapsed, limit)
    else:
        r.fail("ExtractionResult 생성", elapsed, limit)


def test_dataset_metadata_creation(r: PerfResult) -> None:
    """DatasetMetadata 생성 속도 (UUID 포함)"""
    from shared.dto.dataset_dto import DatasetMetadata

    def create():
        DatasetMetadata(total_records=5000)

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("DatasetMetadata 생성", elapsed, limit)
    else:
        r.fail("DatasetMetadata 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_upload_status_is_terminal_speed(r: PerfResult) -> None:
    """UploadStatus.is_terminal 프로퍼티 접근 속도"""
    from shared.dto.dataset_dto import UploadStatus
    status = UploadStatus.COMPLETED

    def access():
        _ = status.is_terminal

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("is_terminal", elapsed, limit)
    else:
        r.fail("is_terminal", elapsed, limit)


def test_s3_uri_speed(r: PerfResult) -> None:
    """ExtractionResult.s3_uri 프로퍼티 접근 속도"""
    from shared.dto.dataset_dto import ExtractionResult, UploadStatus
    res = ExtractionResult(
        s3_bucket="courtview-datasets",
        s3_key="training/data.parquet",
        upload_status=UploadStatus.COMPLETED,
    )

    def access():
        _ = res.s3_uri

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("s3_uri", elapsed, limit)
    else:
        r.fail("s3_uri", elapsed, limit)


# ==================== 4. 대량 레코드 생성 ====================
def test_batch_bbox_records(r: PerfResult) -> None:
    """PlayerBboxRecord 100개 배치 생성"""
    from shared.dto.dataset_dto import PlayerBboxRecord

    def batch():
        for i in range(100):
            PlayerBboxRecord(
                bbox=(0.1, 0.2, 0.05, 0.1),
                class_label="player",
                confidence=0.9,
                frame_index=i,
            )

    elapsed = measure(batch, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("PlayerBboxRecord×100", elapsed, limit)
    else:
        r.fail("PlayerBboxRecord×100", elapsed, limit)


def test_batch_frame_records(r: PerfResult) -> None:
    """FrameRecord 100개 배치 생성"""
    from shared.dto.dataset_dto import FrameRecord

    positions = [(i, float(i) / 10, float(i) / 10) for i in range(10)]

    def batch():
        for i in range(100):
            FrameRecord(
                frame_index=i,
                camera_id="cam_01",
                player_positions=positions,
            )

    elapsed = measure(batch, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("FrameRecord×100", elapsed, limit)
    else:
        r.fail("FrameRecord×100", elapsed, limit)


# ==================== 5. UUID 생성 ====================
def test_uuid_generation_speed(r: PerfResult) -> None:
    """PossessionRecord UUID 포함 생성 속도"""
    from shared.dto.dataset_dto import PossessionRecord

    def create():
        PossessionRecord()

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("PossessionRecord(UUID) 생성", elapsed, limit)
    else:
        r.fail("PossessionRecord(UUID) 생성", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("dataset_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 데이터클래스 생성 ---")
    test_shot_trajectory_record_creation(r)
    test_player_bbox_record_creation(r)
    test_frame_record_creation(r)
    test_extraction_result_creation(r)
    test_dataset_metadata_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_upload_status_is_terminal_speed(r)
    test_s3_uri_speed(r)

    print("\n--- 대량 레코드 ---")
    test_batch_bbox_records(r)
    test_batch_frame_records(r)

    print("\n--- UUID ---")
    test_uuid_generation_speed(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
