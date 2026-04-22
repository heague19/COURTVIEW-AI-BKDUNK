# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트 모듈: infrastructure/preprocessing
테스트 파일: test_frame_aligner.py
설명: frame_aligner.py 단위 테스트
      - AlignmentConfig: 기본값, 하드웨어/소프트웨어 동기화 허용 오차, 최소 카메라 클램핑, repr, slots
      - AlignedFrameSet: 기본값, camera_count, camera_ids, is_complete, get_frame, repr, slots
      - AlignmentStats: 기본값, alignment_rate, repr, slots
      - FrameAligner: 프레임 추가, 정렬, 배치, 클리어, 통계 등
      - 모듈 상수 및 Export 검증

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import pytest
import numpy as np

from infrastructure.preprocessing.frame_aligner import (
    AlignedFrameSet,
    AlignmentConfig,
    AlignmentStats,
    FrameAligner,
    MAX_ALIGNMENT_BUFFER,
    __all__ as module_all,
    __version__ as module_version,
)
from shared.dto.video_dto import FrameData, FrameStatus
from shared.constants.camera_constants import (
    HARDWARE_SYNC_JITTER_MS,
    MAX_CAMERAS,
    SOFTWARE_SYNC_JITTER_MS,
    SYNC_TOLERANCE_MS,
)


# =============================================================================
# 테스트 헬퍼
# =============================================================================

def _make_frame(
    index: int,
    timestamp: float,
    camera_id: str = "cam_0",
    status: FrameStatus = FrameStatus.VALID,
) -> FrameData:
    """테스트용 FrameData 생성.

    Args:
        index: 프레임 인덱스
        timestamp: 타임스탬프 (초)
        camera_id: 카메라 ID
        status: 프레임 상태

    Returns:
        FrameData 인스턴스
    """
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    return FrameData(
        image=image,
        index=index,
        timestamp=timestamp,
        status=status,
        camera_id=camera_id,
    )


# =============================================================================
# AlignmentConfig 테스트
# =============================================================================

class TestAlignmentConfig:
    """AlignmentConfig 데이터클래스 단위 테스트."""

    def test_defaults_software_sync(self) -> None:
        """기본값 생성 시 소프트웨어 동기화 설정 확인."""
        config = AlignmentConfig()
        # use_hardware_sync=False 일 때 tolerance_ms >= SOFTWARE_SYNC_JITTER_MS
        assert config.use_hardware_sync is False
        assert config.tolerance_ms >= SOFTWARE_SYNC_JITTER_MS
        assert config.min_cameras_required == 2
        assert config.drop_incomplete is False

    def test_hardware_sync_tolerance(self) -> None:
        """하드웨어 동기화 시 tolerance가 HARDWARE_SYNC_JITTER_MS * 2 이하로 제한."""
        config = AlignmentConfig(
            tolerance_ms=100.0,
            use_hardware_sync=True,
        )
        assert config.tolerance_ms <= HARDWARE_SYNC_JITTER_MS * 2.0

    def test_hardware_sync_small_tolerance(self) -> None:
        """하드웨어 동기화 시 이미 작은 tolerance는 유지."""
        small_tol = HARDWARE_SYNC_JITTER_MS * 0.5
        config = AlignmentConfig(
            tolerance_ms=small_tol,
            use_hardware_sync=True,
        )
        # min(small_tol, HW * 2.0) = small_tol
        assert config.tolerance_ms == small_tol

    def test_software_sync_tolerance(self) -> None:
        """소프트웨어 동기화 시 tolerance가 SOFTWARE_SYNC_JITTER_MS 이상으로 보장."""
        config = AlignmentConfig(
            tolerance_ms=1.0,  # 매우 작은 값
            use_hardware_sync=False,
        )
        assert config.tolerance_ms >= SOFTWARE_SYNC_JITTER_MS

    def test_min_cameras_clamped_lower(self) -> None:
        """min_cameras_required가 1 미만이면 1로 클램핑."""
        config = AlignmentConfig(min_cameras_required=0)
        assert config.min_cameras_required == 1

    def test_min_cameras_clamped_upper(self) -> None:
        """min_cameras_required가 MAX_CAMERAS 초과 시 MAX_CAMERAS로 클램핑."""
        config = AlignmentConfig(min_cameras_required=MAX_CAMERAS + 10)
        assert config.min_cameras_required == MAX_CAMERAS

    def test_min_cameras_valid_range(self) -> None:
        """min_cameras_required가 유효 범위 내 값은 그대로 유지."""
        config = AlignmentConfig(min_cameras_required=4)
        assert config.min_cameras_required == 4

    def test_repr_software(self) -> None:
        """소프트웨어 동기화 repr에 SW 포함."""
        config = AlignmentConfig(use_hardware_sync=False)
        r = repr(config)
        assert "AlignmentConfig" in r
        assert "SW" in r
        assert "tol=" in r
        assert "min_cams=" in r

    def test_repr_hardware(self) -> None:
        """하드웨어 동기화 repr에 HW 포함."""
        config = AlignmentConfig(use_hardware_sync=True)
        r = repr(config)
        assert "HW" in r

    def test_slots(self) -> None:
        """AlignmentConfig에 __slots__가 존재 (dataclass slots=True)."""
        config = AlignmentConfig()
        assert hasattr(config, "__slots__") or not hasattr(config, "__dict__")


# =============================================================================
# AlignedFrameSet 테스트
# =============================================================================

class TestAlignedFrameSet:
    """AlignedFrameSet 데이터클래스 단위 테스트."""

    def test_defaults(self) -> None:
        """기본값 생성 확인."""
        fs = AlignedFrameSet()
        assert fs.reference_timestamp == 0.0
        assert fs.frames == {}
        assert fs.max_drift_ms == 0.0
        assert fs.frame_index == 0

    def test_camera_count_empty(self) -> None:
        """빈 프레임셋의 camera_count는 0."""
        fs = AlignedFrameSet()
        assert fs.camera_count == 0

    def test_camera_count_with_frames(self) -> None:
        """프레임 포함 시 camera_count 반환."""
        frame_a = _make_frame(0, 0.0, "cam_0")
        frame_b = _make_frame(0, 0.0, "cam_1")
        fs = AlignedFrameSet(
            reference_timestamp=0.0,
            frames={"cam_0": frame_a, "cam_1": frame_b},
        )
        assert fs.camera_count == 2

    def test_camera_ids(self) -> None:
        """camera_ids가 올바른 카메라 ID 목록 반환."""
        frame_a = _make_frame(0, 0.0, "cam_0")
        frame_b = _make_frame(0, 0.0, "cam_1")
        fs = AlignedFrameSet(
            frames={"cam_0": frame_a, "cam_1": frame_b},
        )
        ids = fs.camera_ids
        assert "cam_0" in ids
        assert "cam_1" in ids
        assert len(ids) == 2

    def test_is_complete_all_valid(self) -> None:
        """모든 프레임이 유효하면 is_complete == True."""
        frame_a = _make_frame(0, 0.0, "cam_0", FrameStatus.VALID)
        frame_b = _make_frame(0, 0.0, "cam_1", FrameStatus.VALID)
        fs = AlignedFrameSet(
            frames={"cam_0": frame_a, "cam_1": frame_b},
        )
        assert fs.is_complete is True

    def test_is_complete_with_corrupt(self) -> None:
        """손상된 프레임이 있으면 is_complete == False."""
        frame_a = _make_frame(0, 0.0, "cam_0", FrameStatus.VALID)
        frame_b = _make_frame(0, 0.0, "cam_1", FrameStatus.CORRUPT)
        fs = AlignedFrameSet(
            frames={"cam_0": frame_a, "cam_1": frame_b},
        )
        assert fs.is_complete is False

    def test_is_complete_empty(self) -> None:
        """빈 프레임셋의 is_complete는 True (all() on empty)."""
        fs = AlignedFrameSet()
        assert fs.is_complete is True

    def test_get_frame_existing(self) -> None:
        """존재하는 카메라 ID로 프레임 조회 성공."""
        frame_a = _make_frame(5, 1.0, "cam_0")
        fs = AlignedFrameSet(frames={"cam_0": frame_a})
        result = fs.get_frame("cam_0")
        assert result is not None
        assert result.index == 5
        assert result.timestamp == 1.0

    def test_get_frame_missing(self) -> None:
        """존재하지 않는 카메라 ID 조회 시 None 반환."""
        fs = AlignedFrameSet()
        assert fs.get_frame("nonexistent") is None

    def test_repr(self) -> None:
        """repr 형식 확인."""
        fs = AlignedFrameSet(
            reference_timestamp=1.234,
            max_drift_ms=5.6,
        )
        r = repr(fs)
        assert "AlignedFrameSet" in r
        assert "ts=" in r
        assert "cameras=" in r
        assert "drift=" in r

    def test_slots(self) -> None:
        """AlignedFrameSet에 slots가 활성화되어 있는지 확인."""
        fs = AlignedFrameSet()
        assert hasattr(fs, "__slots__") or not hasattr(fs, "__dict__")


# =============================================================================
# AlignmentStats 테스트
# =============================================================================

class TestAlignmentStats:
    """AlignmentStats 데이터클래스 단위 테스트."""

    def test_defaults(self) -> None:
        """기본값 확인."""
        stats = AlignmentStats()
        assert stats.sets_created == 0
        assert stats.frames_aligned == 0
        assert stats.frames_dropped == 0
        assert stats.avg_drift_ms == 0.0
        assert stats.max_drift_ms == 0.0

    def test_alignment_rate_zero(self) -> None:
        """aligned + dropped == 0 일 때 alignment_rate == 0.0."""
        stats = AlignmentStats()
        assert stats.alignment_rate == 0.0

    def test_alignment_rate_all_aligned(self) -> None:
        """전부 정렬됐을 때 alignment_rate == 1.0."""
        stats = AlignmentStats(frames_aligned=100, frames_dropped=0)
        assert stats.alignment_rate == pytest.approx(1.0)

    def test_alignment_rate_partial(self) -> None:
        """부분 정렬 시 alignment_rate 계산 검증."""
        stats = AlignmentStats(frames_aligned=80, frames_dropped=20)
        assert stats.alignment_rate == pytest.approx(0.8)

    def test_repr(self) -> None:
        """repr 형식 확인."""
        stats = AlignmentStats(
            sets_created=5,
            frames_aligned=100,
            frames_dropped=10,
            avg_drift_ms=2.5,
        )
        r = repr(stats)
        assert "AlignmentStats" in r
        assert "sets=5" in r
        assert "aligned=100" in r
        assert "dropped=10" in r
        assert "avg_drift=" in r

    def test_slots(self) -> None:
        """AlignmentStats에 slots가 활성화되어 있는지 확인."""
        stats = AlignmentStats()
        assert hasattr(stats, "__slots__") or not hasattr(stats, "__dict__")


# =============================================================================
# FrameAligner 테스트
# =============================================================================

class TestFrameAligner:
    """FrameAligner 핵심 클래스 단위 테스트."""

    # -------------------------------------------------------------------------
    # 생성 및 기본 속성
    # -------------------------------------------------------------------------

    def test_creation_with_camera_ids(self) -> None:
        """카메라 ID 목록으로 생성."""
        aligner = FrameAligner(["cam_0", "cam_1", "cam_2"])
        assert aligner.camera_count == 3
        assert set(aligner.camera_ids) == {"cam_0", "cam_1", "cam_2"}

    def test_creation_truncates_to_max_cameras(self) -> None:
        """MAX_CAMERAS 초과 카메라는 잘림."""
        many_cams = [f"cam_{i}" for i in range(MAX_CAMERAS + 5)]
        aligner = FrameAligner(many_cams)
        assert aligner.camera_count == MAX_CAMERAS

    def test_creation_with_custom_config(self) -> None:
        """커스텀 AlignmentConfig 적용."""
        config = AlignmentConfig(
            tolerance_ms=50.0,
            use_hardware_sync=False,
            min_cameras_required=3,
        )
        aligner = FrameAligner(["cam_0", "cam_1", "cam_2"], config)
        assert aligner.config.min_cameras_required == 3

    def test_initial_stats(self) -> None:
        """초기 통계값 확인."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        stats = aligner.stats
        assert stats.sets_created == 0
        assert stats.frames_aligned == 0
        assert stats.frames_dropped == 0

    # -------------------------------------------------------------------------
    # add_frame
    # -------------------------------------------------------------------------

    def test_add_frame_valid_camera(self) -> None:
        """등록된 카메라에 프레임 추가 성공."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        frame = _make_frame(0, 0.0, "cam_0")
        result = aligner.add_frame("cam_0", frame)
        assert result is True
        assert aligner.buffer_sizes["cam_0"] == 1

    def test_add_frame_invalid_camera(self) -> None:
        """등록되지 않은 카메라에 프레임 추가 실패."""
        aligner = FrameAligner(["cam_0"])
        frame = _make_frame(0, 0.0, "cam_99")
        result = aligner.add_frame("cam_99", frame)
        assert result is False

    def test_add_frame_buffer_overflow(self) -> None:
        """MAX_ALIGNMENT_BUFFER 초과 시 가장 오래된 프레임 드롭."""
        aligner = FrameAligner(["cam_0"])

        # 버퍼를 MAX_ALIGNMENT_BUFFER까지 채움
        for i in range(MAX_ALIGNMENT_BUFFER):
            frame = _make_frame(i, float(i) * 0.033, "cam_0")
            aligner.add_frame("cam_0", frame)

        assert aligner.buffer_sizes["cam_0"] == MAX_ALIGNMENT_BUFFER

        # 추가 하나 더 → 오래된 것 드롭
        overflow_frame = _make_frame(MAX_ALIGNMENT_BUFFER, 999.0, "cam_0")
        aligner.add_frame("cam_0", overflow_frame)

        assert aligner.buffer_sizes["cam_0"] == MAX_ALIGNMENT_BUFFER
        # 드롭된 프레임이 통계에 반영
        stats = aligner.stats
        assert stats.frames_dropped >= 1

    def test_add_multiple_frames(self) -> None:
        """여러 프레임 순차 추가."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        for i in range(5):
            aligner.add_frame("cam_0", _make_frame(i, float(i) * 0.033, "cam_0"))
            aligner.add_frame("cam_1", _make_frame(i, float(i) * 0.033, "cam_1"))
        assert aligner.buffer_sizes["cam_0"] == 5
        assert aligner.buffer_sizes["cam_1"] == 5

    # -------------------------------------------------------------------------
    # try_align
    # -------------------------------------------------------------------------

    def test_try_align_empty_buffers(self) -> None:
        """빈 버퍼에서 try_align은 None 반환."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        result = aligner.try_align()
        assert result is None

    def test_try_align_within_tolerance(self) -> None:
        """tolerance 이내 프레임 → AlignedFrameSet 반환."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        ts = 1.0
        # 두 카메라의 타임스탬프 차이를 매우 작게 설정
        aligner.add_frame("cam_0", _make_frame(0, ts, "cam_0"))
        aligner.add_frame("cam_1", _make_frame(0, ts + 0.001, "cam_1"))

        result = aligner.try_align()
        assert result is not None
        assert isinstance(result, AlignedFrameSet)
        assert result.camera_count == 2
        assert "cam_0" in result.camera_ids
        assert "cam_1" in result.camera_ids

    def test_try_align_outside_tolerance(self) -> None:
        """tolerance 밖 프레임 → None 반환 (기준 카메라만 매치)."""
        # 하드웨어 동기화로 tolerance를 매우 엄격하게 설정
        config = AlignmentConfig(
            tolerance_ms=0.5,
            use_hardware_sync=True,
            min_cameras_required=2,
        )
        aligner = FrameAligner(["cam_0", "cam_1"], config)

        # 시간 차이를 tolerance보다 훨씬 크게
        aligner.add_frame("cam_0", _make_frame(0, 1.0, "cam_0"))
        aligner.add_frame("cam_1", _make_frame(0, 10.0, "cam_1"))

        result = aligner.try_align()
        # cam_1은 tolerance 밖이므로 매치 안됨 → 최소 2개 미달 → None
        assert result is None

    def test_try_align_partial_cameras(self) -> None:
        """min_cameras_required 미만의 카메라만 데이터 있을 때 None."""
        config = AlignmentConfig(min_cameras_required=3)
        aligner = FrameAligner(["cam_0", "cam_1", "cam_2"], config)

        # cam_0에만 프레임 추가
        aligner.add_frame("cam_0", _make_frame(0, 1.0, "cam_0"))
        result = aligner.try_align()
        assert result is None

    def test_try_align_partial_cameras_meets_min(self) -> None:
        """min_cameras_required를 만족하는 부분 집합 → 성공."""
        config = AlignmentConfig(min_cameras_required=2)
        aligner = FrameAligner(["cam_0", "cam_1", "cam_2"], config)

        ts = 1.0
        aligner.add_frame("cam_0", _make_frame(0, ts, "cam_0"))
        aligner.add_frame("cam_1", _make_frame(0, ts + 0.001, "cam_1"))
        # cam_2는 비어있음

        result = aligner.try_align()
        assert result is not None
        assert result.camera_count >= 2

    def test_try_align_updates_stats(self) -> None:
        """정렬 성공 시 통계 갱신."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        ts = 1.0
        aligner.add_frame("cam_0", _make_frame(0, ts, "cam_0"))
        aligner.add_frame("cam_1", _make_frame(0, ts + 0.002, "cam_1"))

        result = aligner.try_align()
        assert result is not None

        stats = aligner.stats
        assert stats.sets_created == 1
        assert stats.frames_aligned == 2
        assert stats.avg_drift_ms >= 0.0

    def test_try_align_max_drift(self) -> None:
        """정렬 세트의 max_drift_ms가 올바르게 계산."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        ts = 1.0
        drift_sec = 0.005  # 5ms
        aligner.add_frame("cam_0", _make_frame(0, ts, "cam_0"))
        aligner.add_frame("cam_1", _make_frame(0, ts + drift_sec, "cam_1"))

        result = aligner.try_align()
        assert result is not None
        assert result.max_drift_ms == pytest.approx(drift_sec * 1000.0, abs=0.5)

    def test_try_align_consumes_frames(self) -> None:
        """정렬 후 사용된 프레임이 버퍼에서 제거."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        ts = 1.0
        aligner.add_frame("cam_0", _make_frame(0, ts, "cam_0"))
        aligner.add_frame("cam_1", _make_frame(0, ts, "cam_1"))

        result = aligner.try_align()
        assert result is not None

        # 버퍼가 비었는지 확인
        assert aligner.buffer_sizes["cam_0"] == 0
        assert aligner.buffer_sizes["cam_1"] == 0

    def test_try_align_frame_index_increments(self) -> None:
        """연속 정렬 시 frame_index 증가."""
        aligner = FrameAligner(["cam_0", "cam_1"])

        for i in range(3):
            ts = float(i)
            aligner.add_frame("cam_0", _make_frame(i, ts, "cam_0"))
            aligner.add_frame("cam_1", _make_frame(i, ts, "cam_1"))
            result = aligner.try_align()
            assert result is not None
            assert result.frame_index == i + 1

    # -------------------------------------------------------------------------
    # align_batch
    # -------------------------------------------------------------------------

    def test_align_batch_multiple_sets(self) -> None:
        """align_batch로 여러 세트 일괄 생성."""
        aligner = FrameAligner(["cam_0", "cam_1"])

        for i in range(5):
            ts = float(i)
            aligner.add_frame("cam_0", _make_frame(i, ts, "cam_0"))
            aligner.add_frame("cam_1", _make_frame(i, ts + 0.001, "cam_1"))

        results = aligner.align_batch(max_sets=10)
        assert len(results) >= 1
        for r in results:
            assert isinstance(r, AlignedFrameSet)

    def test_align_batch_empty_returns_empty(self) -> None:
        """빈 버퍼에서 align_batch → 빈 리스트."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        results = aligner.align_batch()
        assert results == []

    def test_align_batch_max_sets_limit(self) -> None:
        """align_batch가 max_sets 제한을 초과하지 않음."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        for i in range(20):
            ts = float(i) * 0.1
            aligner.add_frame("cam_0", _make_frame(i, ts, "cam_0"))
            aligner.add_frame("cam_1", _make_frame(i, ts, "cam_1"))

        results = aligner.align_batch(max_sets=3)
        assert len(results) <= 3

    # -------------------------------------------------------------------------
    # clear / clear_camera
    # -------------------------------------------------------------------------

    def test_clear_returns_dropped_count(self) -> None:
        """clear가 드롭된 프레임 수 반환."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        for i in range(5):
            aligner.add_frame("cam_0", _make_frame(i, float(i), "cam_0"))
        for i in range(3):
            aligner.add_frame("cam_1", _make_frame(i, float(i), "cam_1"))

        dropped = aligner.clear()
        assert dropped == 8  # 5 + 3

    def test_clear_empties_all_buffers(self) -> None:
        """clear 후 모든 버퍼가 비어있음."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        aligner.add_frame("cam_0", _make_frame(0, 0.0, "cam_0"))
        aligner.add_frame("cam_1", _make_frame(0, 0.0, "cam_1"))

        aligner.clear()
        for size in aligner.buffer_sizes.values():
            assert size == 0

    def test_clear_camera_specific(self) -> None:
        """clear_camera로 특정 카메라만 클리어."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        aligner.add_frame("cam_0", _make_frame(0, 0.0, "cam_0"))
        aligner.add_frame("cam_0", _make_frame(1, 0.033, "cam_0"))
        aligner.add_frame("cam_1", _make_frame(0, 0.0, "cam_1"))

        dropped = aligner.clear_camera("cam_0")
        assert dropped == 2
        assert aligner.buffer_sizes["cam_0"] == 0
        assert aligner.buffer_sizes["cam_1"] == 1

    def test_clear_camera_invalid_id(self) -> None:
        """존재하지 않는 카메라 클리어 시 0 반환."""
        aligner = FrameAligner(["cam_0"])
        dropped = aligner.clear_camera("nonexistent")
        assert dropped == 0

    # -------------------------------------------------------------------------
    # buffer_sizes
    # -------------------------------------------------------------------------

    def test_buffer_sizes_property(self) -> None:
        """buffer_sizes가 카메라별 버퍼 크기 딕셔너리 반환."""
        aligner = FrameAligner(["cam_0", "cam_1", "cam_2"])
        aligner.add_frame("cam_0", _make_frame(0, 0.0, "cam_0"))
        aligner.add_frame("cam_0", _make_frame(1, 0.033, "cam_0"))
        aligner.add_frame("cam_2", _make_frame(0, 0.0, "cam_2"))

        sizes = aligner.buffer_sizes
        assert sizes["cam_0"] == 2
        assert sizes["cam_1"] == 0
        assert sizes["cam_2"] == 1

    # -------------------------------------------------------------------------
    # reset_stats
    # -------------------------------------------------------------------------

    def test_reset_stats(self) -> None:
        """reset_stats 후 통계가 초기화."""
        aligner = FrameAligner(["cam_0", "cam_1"])

        # 정렬을 한 번 수행하여 통계 생성
        ts = 1.0
        aligner.add_frame("cam_0", _make_frame(0, ts, "cam_0"))
        aligner.add_frame("cam_1", _make_frame(0, ts, "cam_1"))
        aligner.try_align()

        assert aligner.stats.sets_created > 0

        aligner.reset_stats()
        stats = aligner.stats
        assert stats.sets_created == 0
        assert stats.frames_aligned == 0
        assert stats.frames_dropped == 0
        assert stats.avg_drift_ms == 0.0
        assert stats.max_drift_ms == 0.0

    # -------------------------------------------------------------------------
    # repr
    # -------------------------------------------------------------------------

    def test_repr(self) -> None:
        """FrameAligner repr 형식 확인."""
        aligner = FrameAligner(["cam_0", "cam_1"])
        r = repr(aligner)
        assert "FrameAligner" in r
        assert "cameras=" in r
        assert "tol=" in r
        assert "sets=" in r


# =============================================================================
# 상수 검증
# =============================================================================

class TestFrameAlignerConstants:
    """모듈 상수 값 검증."""

    def test_max_alignment_buffer(self) -> None:
        """MAX_ALIGNMENT_BUFFER 값 확인."""
        assert MAX_ALIGNMENT_BUFFER == 120
        assert isinstance(MAX_ALIGNMENT_BUFFER, int)

    pass


# =============================================================================
# 모듈 Export 검증
# =============================================================================

class TestFrameAlignerModuleExports:
    """모듈 __all__ 및 __version__ 검증."""

    def test_all_contains_classes(self) -> None:
        """__all__에 핵심 클래스 포함."""
        assert "FrameAligner" in module_all
        assert "AlignmentConfig" in module_all
        assert "AlignedFrameSet" in module_all
        assert "AlignmentStats" in module_all

    def test_all_contains_constants(self) -> None:
        """__all__에 상수 포함."""
        assert "MAX_ALIGNMENT_BUFFER" in module_all

    def test_version(self) -> None:
        """모듈 버전 확인."""
        assert module_version == "1.0.0"
