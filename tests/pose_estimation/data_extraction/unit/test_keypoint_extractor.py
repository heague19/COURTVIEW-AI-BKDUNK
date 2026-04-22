# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/pose_estimation/data_extraction/unit
파일: test_keypoint_extractor.py
설명: keypoint_extractor.py 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0
"""
from __future__ import annotations

import importlib
import os
import shutil
import tempfile

import numpy as np
import pytest

from pose_estimation.data_extraction.keypoint_extractor import (
    CONFIG_KEY_KEYPOINT_EXTRACTION,
    KeypointExtractionConfig,
    KeypointExtractionMetadata,
    KeypointExtractionSample,
    KeypointExtractionStats,
    KeypointExtractor,
)


# ============================================================
# 테스트: 모듈 레벨 상수
# ============================================================
class TestModuleConstants:
    """모듈 상수 테스트."""

    def test_config_key(self) -> None:
        assert CONFIG_KEY_KEYPOINT_EXTRACTION == "data_extraction.keypoint_extraction"

    def test_version(self) -> None:
        import pose_estimation.data_extraction.keypoint_extractor as mod
        assert mod.__version__ == "1.0.0"

    def test_all_exports(self) -> None:
        import pose_estimation.data_extraction.keypoint_extractor as mod
        expected = {
            "CONFIG_KEY_KEYPOINT_EXTRACTION",
            "KeypointExtractionConfig",
            "KeypointExtractionSample",
            "KeypointExtractionStats",
            "KeypointExtractionMetadata",
            "KeypointExtractor",
        }
        assert set(mod.__all__) == expected


# ============================================================
# 테스트: KeypointExtractionConfig
# ============================================================
class TestKeypointExtractionConfig:
    """KeypointExtractionConfig 데이터클래스 테스트."""

    def test_default_values(self) -> None:
        cfg = KeypointExtractionConfig()
        assert cfg.enabled is True
        assert cfg.min_detections == 1
        assert cfg.min_detection_confidence == pytest.approx(0.70)
        assert cfg.min_bbox_pixels == 400
        assert cfg.min_visible_keypoints == 8
        assert cfg.buffer_size == 50
        assert cfg.max_total_samples == 5000
        assert cfg.jpeg_quality == 95
        assert cfg.max_long_side == 1280
        assert cfg.dedup_enabled is True
        assert cfg.similarity_threshold == 5
        assert cfg.max_cache_size == 2000

    def test_frozen(self) -> None:
        cfg = KeypointExtractionConfig()
        with pytest.raises(AttributeError):
            cfg.enabled = False  # type: ignore[misc]

    def test_slots(self) -> None:
        cfg = KeypointExtractionConfig()
        assert not hasattr(cfg, "__dict__")

    def test_custom_values(self) -> None:
        cfg = KeypointExtractionConfig(
            enabled=False,
            min_detections=3,
            buffer_size=100,
            max_total_samples=10000,
        )
        assert cfg.enabled is False
        assert cfg.min_detections == 3
        assert cfg.buffer_size == 100
        assert cfg.max_total_samples == 10000

    def test_critical_keypoint_indices(self) -> None:
        cfg = KeypointExtractionConfig()
        assert isinstance(cfg.critical_keypoint_indices, tuple)
        assert len(cfg.critical_keypoint_indices) == 4
        # 5, 6, 11, 12 = left/right shoulder + left/right hip
        assert 5 in cfg.critical_keypoint_indices
        assert 6 in cfg.critical_keypoint_indices
        assert 11 in cfg.critical_keypoint_indices
        assert 12 in cfg.critical_keypoint_indices

    def test_from_config_none(self) -> None:
        """config_loader=None → 기본값 반환."""
        cfg = KeypointExtractionConfig.from_config(None)
        assert cfg.enabled is True
        assert cfg.min_detections == 1

    def test_from_config_with_loader(self) -> None:
        """Mock ConfigLoader로 설정 로드."""
        class MockLoader:
            def get(self, key: str, default: object = None) -> object:
                overrides = {
                    "data_extraction.keypoint_extraction.enabled": False,
                    "data_extraction.keypoint_extraction.quality_filter.min_detections": 5,
                }
                return overrides.get(key, default)

        cfg = KeypointExtractionConfig.from_config(MockLoader())
        assert cfg.enabled is False
        assert cfg.min_detections == 5


# ============================================================
# 테스트: KeypointExtractionSample
# ============================================================
class TestKeypointExtractionSample:
    """KeypointExtractionSample 데이터클래스 테스트."""

    def test_default_values(self) -> None:
        sample = KeypointExtractionSample()
        assert sample.sample_id == ""
        assert sample.image_data == b""
        assert sample.yolo_label == ""
        assert sample.annotation_data == {}
        assert sample.frame_index == 0
        assert sample.timestamp_ms == 0.0
        assert sample.person_count == 0
        assert sample.avg_completeness == 0.0
        assert sample.image_hash == ""

    def test_slots(self) -> None:
        sample = KeypointExtractionSample()
        assert not hasattr(sample, "__dict__")

    def test_mutable(self) -> None:
        sample = KeypointExtractionSample()
        sample.sample_id = "abc123"
        assert sample.sample_id == "abc123"

    def test_annotation_data_default_factory(self) -> None:
        """각 인스턴스 별도 dict."""
        s1 = KeypointExtractionSample()
        s2 = KeypointExtractionSample()
        s1.annotation_data["key"] = "value"
        assert "key" not in s2.annotation_data


# ============================================================
# 테스트: KeypointExtractionStats
# ============================================================
class TestKeypointExtractionStats:
    """KeypointExtractionStats 테스트."""

    def test_default_values(self) -> None:
        stats = KeypointExtractionStats()
        assert stats.total_input_frames == 0
        assert stats.total_extracted == 0
        assert stats.total_flushed == 0

    def test_slots(self) -> None:
        stats = KeypointExtractionStats()
        assert not hasattr(stats, "__dict__")

    def test_pass_rate_zero(self) -> None:
        stats = KeypointExtractionStats()
        assert stats.pass_rate == 0.0

    def test_pass_rate_calculated(self) -> None:
        stats = KeypointExtractionStats()
        stats.total_input_frames = 100
        stats.total_extracted = 75
        assert stats.pass_rate == pytest.approx(0.75)

    def test_avg_completeness(self) -> None:
        stats = KeypointExtractionStats()
        assert stats.avg_completeness == 0.0

    def test_update_completeness_ewma_first(self) -> None:
        """첫 번째 EWMA 업데이트 → 입력값 직접 설정."""
        stats = KeypointExtractionStats()
        stats.update_completeness_ewma(0.85)
        assert stats.avg_completeness == pytest.approx(0.85)

    def test_update_completeness_ewma_subsequent(self) -> None:
        """두 번째 이후 EWMA → 지수 가중 평균."""
        stats = KeypointExtractionStats()
        stats.update_completeness_ewma(0.80)
        stats.update_completeness_ewma(1.0)
        # alpha=0.02 → 0.02*1.0 + 0.98*0.80 = 0.804
        assert stats.avg_completeness == pytest.approx(0.804, abs=0.001)

    def test_total_rejected_frames(self) -> None:
        stats = KeypointExtractionStats()
        stats.rejected_empty_frame = 5
        stats.rejected_too_few_detections = 3
        stats.rejected_keypoints_mismatch = 2
        stats.rejected_few_qualifying = 1
        stats.rejected_duplicate_frame = 4
        assert stats.total_rejected_frames == 15

    def test_total_rejected_persons(self) -> None:
        stats = KeypointExtractionStats()
        stats.rejected_not_player = 2
        stats.rejected_low_confidence = 3
        stats.rejected_bad_bbox_size = 1
        stats.rejected_insufficient_keypoints = 4
        stats.rejected_missing_critical = 2
        stats.rejected_low_completeness = 1
        assert stats.total_rejected_persons == 13

    def test_to_dict(self) -> None:
        stats = KeypointExtractionStats()
        stats.total_input_frames = 50
        stats.total_extracted = 30
        d = stats.to_dict()
        assert d["total_input_frames"] == 50
        assert d["total_extracted"] == 30
        assert "frame_rejections" in d
        assert "person_rejections" in d
        assert "quality_distribution" in d
        assert d["pass_rate"] == pytest.approx(0.6)


# ============================================================
# 테스트: KeypointExtractionMetadata
# ============================================================
class TestKeypointExtractionMetadata:
    """KeypointExtractionMetadata 테스트."""

    def test_default_values(self) -> None:
        meta = KeypointExtractionMetadata()
        assert meta.session_id == ""
        assert meta.keypoint_format == "coco_17"
        assert meta.output_directory == ""

    def test_slots(self) -> None:
        meta = KeypointExtractionMetadata()
        assert not hasattr(meta, "__dict__")

    def test_to_dict(self) -> None:
        meta = KeypointExtractionMetadata(
            session_id="test123",
            source_game_id="game001",
            total_samples=100,
            total_persons=250,
            avg_completeness=0.876,
        )
        d = meta.to_dict()
        assert d["session_id"] == "test123"
        assert d["source_game_id"] == "game001"
        assert d["total_samples"] == 100
        assert d["num_keypoints"] == 17
        assert d["training_target"] == "YOLOv8-Pose"
        assert d["avg_completeness"] == pytest.approx(0.876, abs=0.001)


# ============================================================
# 테스트: KeypointExtractor (클래스 레벨)
# ============================================================
class TestKeypointExtractor:
    """KeypointExtractor 클래스 테스트."""

    def test_init_default(self) -> None:
        ext = KeypointExtractor()
        assert ext._config is None
        assert ext._initialized is False
        assert ext._buffer == []

    def test_init_with_config(self) -> None:
        cfg = KeypointExtractionConfig(buffer_size=10)
        ext = KeypointExtractor(config=cfg)
        assert ext._config is not None
        assert ext._config.buffer_size == 10

    def test_initialize_default_config(self) -> None:
        ext = KeypointExtractor()
        ext.initialize()
        assert ext._initialized is True
        assert ext._config is not None
        assert ext._config.enabled is True

    def test_initialize_with_config(self) -> None:
        cfg = KeypointExtractionConfig(enabled=False, buffer_size=5)
        ext = KeypointExtractor()
        ext.initialize(config=cfg)
        assert ext._config.enabled is False
        assert ext._config.buffer_size == 5

    def test_initialize_creates_session_id(self) -> None:
        ext = KeypointExtractor()
        ext.initialize()
        assert len(ext._session_id) == 16

    def test_initialize_creates_output_dirs(self) -> None:
        tmpdir = tempfile.mkdtemp()
        try:
            cfg = KeypointExtractionConfig(local_base_path=tmpdir)
            ext = KeypointExtractor(config=cfg)
            ext.initialize()
            assert os.path.isdir(ext._images_dir)
            assert os.path.isdir(ext._labels_dir)
            assert os.path.isdir(ext._annotations_dir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_stats_property(self) -> None:
        ext = KeypointExtractor()
        ext.initialize()
        stats = ext._stats
        assert isinstance(stats, KeypointExtractionStats)
        assert stats.total_input_frames == 0

    def test_double_initialize_safe(self) -> None:
        """두 번 초기화해도 에러 없음."""
        ext = KeypointExtractor()
        ext.initialize()
        sid1 = ext._session_id
        ext._initialized = False
        ext.initialize()
        # 새 세션 ID 생성
        assert ext._session_id != sid1

    def test_extract_before_init_raises(self) -> None:
        """initialize() 전 extract_from_frame 호출 시 에러."""
        ext = KeypointExtractor()
        with pytest.raises(Exception):
            ext.extract_from_frame([], np.zeros((100, 100, 3), dtype=np.uint8), [])
