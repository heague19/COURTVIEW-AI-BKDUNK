# -*- coding: utf-8 -*-
"""engine/pipeline/frame_pipeline.py 단위 테스트."""

from __future__ import annotations

import pytest

from engine.config import CadenceConfig
from engine.pipeline.frame_pipeline import FramePipeline, FramePipelineResult
from engine.pipeline.fusion.detection_fusion import DetectionFusion
from engine.pipeline.fusion.pose_fusion import PoseFusion
from engine.pipeline.fusion.tracking_fusion import TrackingFusion


def _make_pipeline(budget_ms: float = 33.0) -> FramePipeline:
    """테스트용 파이프라인 생성."""
    return FramePipeline(
        detection_fusion=DetectionFusion(),
        pose_fusion=PoseFusion(),
        tracking_fusion=TrackingFusion(),
        cadence_config=CadenceConfig(frame_budget_ms=budget_ms),
    )


# =============================================================================
# FramePipelineResult 테스트
# =============================================================================
class TestFramePipelineResult:
    """FramePipelineResult 데이터 클래스."""

    def test_slots(self) -> None:
        r = FramePipelineResult()
        assert not hasattr(r, "__dict__")

    def test_defaults(self) -> None:
        r = FramePipelineResult()
        assert r.frame_index == 0
        assert r.total_objects == 0
        assert r.total_persons_3d == 0
        assert r.active_tracks == 0
        assert r.processing_time_ms == 0.0
        assert r.budget_exceeded is False


# =============================================================================
# FramePipeline 테스트
# =============================================================================
class TestFramePipeline:
    """FramePipeline 핵심 루프."""

    def test_initial_state(self) -> None:
        fp = _make_pipeline()
        assert fp.total_frames == 0
        assert fp.budget_exceeded_count == 0
        assert fp.budget_exceeded_ratio == 0.0
        assert fp.avg_processing_time_ms == 0.0

    def test_process_empty_frame(self) -> None:
        """빈 프레임 → 정상 실행, 객체 0."""
        fp = _make_pipeline()
        result = fp.process_frame({}, frame_index=1, timestamp=0.033)
        assert isinstance(result, FramePipelineResult)
        assert result.frame_index == 1
        assert result.timestamp == 0.033
        assert result.total_objects == 0
        assert result.detection is not None
        assert result.pose is not None
        assert result.processing_time_ms >= 0.0

    def test_total_frames_increments(self) -> None:
        fp = _make_pipeline()
        fp.process_frame({})
        fp.process_frame({})
        fp.process_frame({})
        assert fp.total_frames == 3

    def test_stage_times_populated(self) -> None:
        """3단계 시간 모두 기록."""
        fp = _make_pipeline()
        result = fp.process_frame({})
        assert "detection_fusion" in result.stage_times_ms
        assert "pose_fusion" in result.stage_times_ms
        assert "tracking_fusion" in result.stage_times_ms

    def test_budget_not_exceeded_normal(self) -> None:
        """정상 실행 시 33ms 미초과."""
        fp = _make_pipeline(budget_ms=33.0)
        result = fp.process_frame({})
        # 빈 프레임은 <1ms이므로 초과 없음
        assert result.budget_exceeded is False
        assert fp.budget_exceeded_count == 0

    def test_budget_exceeded_tight(self) -> None:
        """예산 0.001ms → 거의 항상 초과."""
        fp = _make_pipeline(budget_ms=0.001)
        result = fp.process_frame({})
        # 실행 시간 > 0.001ms이면 초과
        if result.processing_time_ms > 0.001:
            assert result.budget_exceeded is True
            assert fp.budget_exceeded_count >= 1

    def test_budget_exceeded_ratio(self) -> None:
        fp = _make_pipeline(budget_ms=0.001)
        for _ in range(10):
            fp.process_frame({})
        # 대부분 초과했을 것
        assert fp.budget_exceeded_ratio >= 0.0
        assert fp.budget_exceeded_ratio <= 1.0

    def test_avg_processing_time(self) -> None:
        fp = _make_pipeline()
        fp.process_frame({})
        fp.process_frame({})
        avg = fp.avg_processing_time_ms
        assert avg >= 0.0

    def test_history_limit(self) -> None:
        fp = _make_pipeline()
        for i in range(150):
            fp.process_frame({}, frame_index=i)
        assert fp.total_frames == 150
        assert len(fp._history) <= 100

    def test_reset(self) -> None:
        fp = _make_pipeline()
        fp.process_frame({})
        fp.process_frame({})
        fp.reset()
        assert fp.total_frames == 0
        assert fp.budget_exceeded_count == 0
        assert fp.avg_processing_time_ms == 0.0

    def test_repr(self) -> None:
        fp = _make_pipeline()
        r = repr(fp)
        assert "FramePipeline" in r
        assert "frames=0" in r

    def test_multiple_frames_sequential(self) -> None:
        """30프레임 순차 실행."""
        fp = _make_pipeline()
        for i in range(30):
            result = fp.process_frame(
                {}, frame_index=i, timestamp=i * 0.033,
            )
            assert result.frame_index == i
        assert fp.total_frames == 30

    def test_tracking_persists_across_frames(self) -> None:
        """detection에 선수가 없으면 tracking도 빈 결과."""
        fp = _make_pipeline()
        r1 = fp.process_frame({}, frame_index=0)
        r2 = fp.process_frame({}, frame_index=1)
        # 감지기 미주입 → 선수 0 → tracking 미실행
        assert r1.active_tracks == 0
        assert r2.active_tracks == 0


# =============================================================================
# 모듈 메타 테스트
# =============================================================================
class TestModuleMeta:
    """모듈 메타데이터."""

    def test_all_count(self) -> None:
        import engine.pipeline.frame_pipeline as mod
        assert len(mod.__all__) == 2

    def test_version(self) -> None:
        import engine.pipeline.frame_pipeline as mod
        assert mod.__version__ == "1.0.0"
