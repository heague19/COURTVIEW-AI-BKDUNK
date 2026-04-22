# -*- coding: utf-8 -*-
"""engine/gpu/ 단위 테스트 (4파일 통합)."""

from __future__ import annotations

import numpy as np
import pytest

from engine.config import CameraConfig, GPUConfig


# =============================================================================
# gpu_manager.py 테스트
# =============================================================================
from engine.gpu.gpu_manager import (
    GPUHealthStatus,
    GPUManager,
    GPUSnapshot,
    VRAMAllocation,
)


class TestGPUHealthStatus:
    """GPUHealthStatus 열거형."""

    def test_member_count(self) -> None:
        assert len(GPUHealthStatus) == 5

    def test_values(self) -> None:
        assert GPUHealthStatus.HEALTHY.value == "healthy"
        assert GPUHealthStatus.CRITICAL.value == "critical"
        assert GPUHealthStatus.UNAVAILABLE.value == "unavailable"


class TestVRAMAllocation:
    """VRAMAllocation frozen dataclass."""

    def test_frozen(self) -> None:
        alloc = VRAMAllocation(name="test", size_mb=100, allocated_at=1.0)
        with pytest.raises(AttributeError):
            alloc.size_mb = 200  # type: ignore[misc]


class TestGPUSnapshot:
    """GPUSnapshot frozen dataclass."""

    def test_frozen(self) -> None:
        snap = GPUSnapshot(
            health=GPUHealthStatus.HEALTHY,
            total_vram_mb=8192,
            used_vram_mb=2000,
            free_vram_mb=6192,
            utilization_pct=24.4,
            temperature_celsius=45.0,
            allocation_count=1,
            is_simulation=True,
            timestamp=0.0,
        )
        assert snap.total_vram_mb == 8192
        assert snap.is_simulation is True
        with pytest.raises(AttributeError):
            snap.total_vram_mb = 0  # type: ignore[misc]


class TestGPUManager:
    """GPUManager 핵심 기능."""

    def _make_manager(self) -> GPUManager:
        cfg = GPUConfig(vram_limit_mb=8192)
        mgr = GPUManager(cfg)
        mgr.initialize()
        return mgr

    def test_initialize(self) -> None:
        mgr = self._make_manager()
        snap = mgr.snapshot()
        assert snap.total_vram_mb > 0

    def test_allocate_and_deallocate(self) -> None:
        mgr = self._make_manager()
        result = mgr.allocate("test_model", 500)
        assert result is True
        freed = mgr.deallocate("test_model")
        assert freed == 500

    def test_allocate_duplicate_replaces(self) -> None:
        """중복 이름 → 기존 해제 후 재할당."""
        mgr = self._make_manager()
        mgr.allocate("model_a", 300)
        result = mgr.allocate("model_a", 500)
        assert result is True

    def test_allocate_exceeds_vram(self) -> None:
        mgr = self._make_manager()
        result = mgr.allocate("huge_model", 99999)
        assert result is False

    def test_deallocate_nonexistent(self) -> None:
        mgr = self._make_manager()
        freed = mgr.deallocate("nonexistent")
        assert freed == 0

    def test_snapshot_type(self) -> None:
        mgr = self._make_manager()
        snap = mgr.snapshot()
        assert isinstance(snap, GPUSnapshot)
        assert isinstance(snap.health, GPUHealthStatus)

    def test_check_thermal(self) -> None:
        mgr = self._make_manager()
        status = mgr.check_thermal()
        assert isinstance(status, GPUHealthStatus)

    def test_vram_utilization(self) -> None:
        mgr = self._make_manager()
        assert mgr.vram_utilization >= 0.0

    def test_shutdown(self) -> None:
        mgr = self._make_manager()
        mgr.shutdown()
        # shutdown 후 재초기화 가능 확인
        mgr.initialize()
        assert mgr.snapshot().total_vram_mb > 0

    def test_module_meta(self) -> None:
        import engine.gpu.gpu_manager as mod
        assert len(mod.__all__) == 4
        assert mod.__version__ == "1.0.0"


# =============================================================================
# cuda_stream_manager.py 테스트
# =============================================================================
from engine.gpu.cuda_stream_manager import (
    CUDAStreamManager,
    StreamID,
    StreamProfile,
    StreamStatus,
)


class TestStreamID:
    """StreamID 열거형."""

    def test_member_count(self) -> None:
        assert len(StreamID) == 2

    def test_values(self) -> None:
        assert StreamID.STAGE1.value == "stage1"
        assert StreamID.STAGE2.value == "stage2"


class TestStreamStatus:
    """StreamStatus 열거형."""

    def test_member_count(self) -> None:
        assert len(StreamStatus) == 3


class TestStreamProfile:
    """StreamProfile 데이터 클래스."""

    def test_record_and_avg(self) -> None:
        p = StreamProfile()
        p.record(10.0)
        p.record(20.0)
        assert p.total_executions == 2
        assert p.avg_time_ms == 15.0
        assert p.peak_time_ms == 20.0

    def test_avg_zero_division(self) -> None:
        p = StreamProfile()
        assert p.avg_time_ms == 0.0


class TestCUDAStreamManager:
    """CUDAStreamManager 핵심 기능."""

    def _make_manager(self) -> CUDAStreamManager:
        cfg = GPUConfig()
        mgr = CUDAStreamManager(cfg)
        mgr.initialize()
        return mgr

    def test_initialize(self) -> None:
        mgr = self._make_manager()
        # 초기화 후 begin/end 가능해야 함
        started = mgr.begin_stream(StreamID.STAGE1)
        assert started is True
        mgr.end_stream(StreamID.STAGE1)

    def test_begin_end_stream(self) -> None:
        mgr = self._make_manager()
        started = mgr.begin_stream(StreamID.STAGE1)
        assert started is True
        elapsed = mgr.end_stream(StreamID.STAGE1)
        assert elapsed >= 0.0

    def test_begin_duplicate_returns_false(self) -> None:
        mgr = self._make_manager()
        mgr.begin_stream(StreamID.STAGE1)
        assert mgr.begin_stream(StreamID.STAGE1) is False
        mgr.end_stream(StreamID.STAGE1)

    def test_s1_s2_independent(self) -> None:
        """Stage1 실행 중 Stage2 시작 가능."""
        mgr = self._make_manager()
        mgr.begin_stream(StreamID.STAGE1)
        assert mgr.begin_stream(StreamID.STAGE2) is True
        mgr.end_stream(StreamID.STAGE1)
        mgr.end_stream(StreamID.STAGE2)

    def test_synchronize_all(self) -> None:
        mgr = self._make_manager()
        mgr.synchronize_all()

    def test_shutdown(self) -> None:
        mgr = self._make_manager()
        mgr.shutdown()

    def test_module_meta(self) -> None:
        import engine.gpu.cuda_stream_manager as mod
        assert len(mod.__all__) == 4
        assert mod.__version__ == "1.0.0"


# =============================================================================
# tensorrt_pool.py 테스트
# =============================================================================
from engine.gpu.tensorrt_pool import (
    EngineStatus,
    ModelID,
    TensorRTPool,
)


class TestModelID:
    """ModelID 열거형."""

    def test_member_count(self) -> None:
        assert len(ModelID) == 4

    def test_values(self) -> None:
        assert ModelID.YOLOV8_DET.value == "yolov8_det"
        assert ModelID.VITPOSE_B.value == "vitpose_b"


class TestEngineStatus:
    """EngineStatus 열거형."""

    def test_member_count(self) -> None:
        assert len(EngineStatus) == 5

    def test_values(self) -> None:
        assert EngineStatus.UNLOADED.value == "unloaded"
        assert EngineStatus.READY.value == "ready"


class TestTensorRTPool:
    """TensorRTPool 핵심 기능."""

    def _make_pool(self) -> TensorRTPool:
        gpu_cfg = GPUConfig(vram_limit_mb=8192)
        gpu_mgr = GPUManager(gpu_cfg)
        gpu_mgr.initialize()
        pool = TensorRTPool(config=gpu_cfg, gpu_manager=gpu_mgr)
        pool.initialize()
        return pool

    def test_initialize(self) -> None:
        pool = self._make_pool()
        # 4종 ModelID 전부 엔트리 생성 확인
        for mid in ModelID:
            assert pool.is_model_ready(mid) is False  # 로드 전

    def test_load_model(self) -> None:
        pool = self._make_pool()
        result = pool.load_model(ModelID.YOLOV8_DET)
        assert result is True

    def test_model_status_after_load(self) -> None:
        pool = self._make_pool()
        pool.load_model(ModelID.YOLOV8_DET)
        assert pool.is_model_ready(ModelID.YOLOV8_DET) is True

    def test_unloaded_model_not_ready(self) -> None:
        pool = self._make_pool()
        assert pool.is_model_ready(ModelID.YOLOV8_DET) is False

    def test_get_stream_id_det_stage1(self) -> None:
        pool = self._make_pool()
        s = pool.get_stream_id(ModelID.YOLOV8_DET)
        assert s == StreamID.STAGE1

    def test_get_stream_id_vitpose_stage2(self) -> None:
        pool = self._make_pool()
        s = pool.get_stream_id(ModelID.VITPOSE_B)
        assert s == StreamID.STAGE2

    def test_record_inference(self) -> None:
        pool = self._make_pool()
        pool.load_model(ModelID.YOLOV8_DET)
        pool.record_inference(ModelID.YOLOV8_DET)

    def test_module_meta(self) -> None:
        import engine.gpu.tensorrt_pool as mod
        assert len(mod.__all__) == 4
        assert mod.__version__ == "1.0.0"


# =============================================================================
# batch_accumulator.py 테스트
# =============================================================================
from engine.gpu.batch_accumulator import (
    BatchAccumulator,
    FrameBatch,
    FrameMeta,
)


class TestFrameMeta:
    """FrameMeta frozen dataclass."""

    def test_frozen(self) -> None:
        meta = FrameMeta(
            camera_id=0,
            frame_number=1,
            timestamp=1.0,
            width=1920,
            height=1080,
        )
        with pytest.raises(AttributeError):
            meta.camera_id = 1  # type: ignore[misc]

    def test_fields(self) -> None:
        meta = FrameMeta(camera_id=2, frame_number=10, timestamp=0.33, width=640, height=480)
        assert meta.camera_id == 2
        assert meta.frame_number == 10


class TestBatchAccumulator:
    """BatchAccumulator 핵심 기능."""

    def _make_accumulator(self, num_cameras: int = 4) -> BatchAccumulator:
        cfg = CameraConfig(num_cameras=num_cameras, analysis_width=640, analysis_height=480)
        return BatchAccumulator(cfg)

    def _make_frame(self, w: int = 640, h: int = 480) -> np.ndarray:
        return np.zeros((h, w, 3), dtype=np.uint8)

    def _make_meta(self, cam_id: int, fn: int = 1, ts: float = 0.0) -> FrameMeta:
        return FrameMeta(camera_id=cam_id, frame_number=fn, timestamp=ts, width=640, height=480)

    def test_add_frame_incomplete(self) -> None:
        """카메라 수 미달 → None."""
        acc = self._make_accumulator(num_cameras=4)
        result = acc.add_frame(self._make_frame(), self._make_meta(0))
        assert result is None

    def test_add_frame_complete(self) -> None:
        """모든 카메라 프레임 도착 → FrameBatch."""
        acc = self._make_accumulator(num_cameras=2)
        acc.add_frame(self._make_frame(), self._make_meta(0))
        batch = acc.add_frame(self._make_frame(), self._make_meta(1))
        assert batch is not None
        assert isinstance(batch, FrameBatch)
        assert batch.frames.shape[0] == 2

    def test_camera_id_sorted(self) -> None:
        """배치 내 프레임은 camera_id 순 정렬."""
        acc = self._make_accumulator(num_cameras=3)
        acc.add_frame(self._make_frame(), self._make_meta(2))
        acc.add_frame(self._make_frame(), self._make_meta(0))
        batch = acc.add_frame(self._make_frame(), self._make_meta(1))
        assert batch is not None
        ids = [m.camera_id for m in batch.metas]
        assert ids == [0, 1, 2]

    def test_duplicate_camera_flush(self) -> None:
        """중복 camera_id → 기존 배치 flush + drop."""
        acc = self._make_accumulator(num_cameras=2)
        acc.add_frame(self._make_frame(), self._make_meta(0, fn=1))
        acc.add_frame(self._make_frame(), self._make_meta(0, fn=2, ts=0.033))
        assert acc.total_dropped >= 1

    def test_flush(self) -> None:
        """불완전 배치 강제 반환."""
        acc = self._make_accumulator(num_cameras=4)
        acc.add_frame(self._make_frame(), self._make_meta(0))
        acc.add_frame(self._make_frame(), self._make_meta(1))
        batch = acc.flush()
        assert batch is not None
        assert batch.frames.shape[0] == 2
        assert batch.is_complete is False

    def test_flush_empty(self) -> None:
        """대기 프레임 없으면 None."""
        acc = self._make_accumulator(num_cameras=4)
        assert acc.flush() is None

    def test_reset(self) -> None:
        acc = self._make_accumulator(num_cameras=2)
        acc.add_frame(self._make_frame(), self._make_meta(0))
        acc.reset()
        assert acc.pending_count == 0
        assert acc.total_batches == 0

    def test_module_meta(self) -> None:
        import engine.gpu.batch_accumulator as mod
        assert len(mod.__all__) == 3
        assert mod.__version__ == "1.0.0"
