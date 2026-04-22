# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/pose_estimation/data_extraction/unit
파일: test_wholebody_keypoint_extractor.py
설명: wholebody_keypoint_extractor.py 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0
"""
from __future__ import annotations

import os
import shutil
import tempfile

import numpy as np
import pytest

from pose_estimation.data_extraction.wholebody_keypoint_extractor import (
    CONFIG_KEY_WHOLEBODY_EXTRACTION,
    WholeBodyExtractionConfig,
    WholeBodyExtractionMetadata,
    WholeBodyExtractionSample,
    WholeBodyExtractionStats,
    WholeBodyKeypointExtractor,
)


# ============================================================
# 테스트: 모듈 레벨 상수
# ============================================================
class TestModuleConstants:
    """모듈 상수 테스트."""

    def test_config_key(self) -> None:
        assert CONFIG_KEY_WHOLEBODY_EXTRACTION == "data_extraction.wholebody_extraction"

    def test_version(self) -> None:
        import pose_estimation.data_extraction.wholebody_keypoint_extractor as mod
        assert mod.__version__ == "1.0.0"

    def test_all_exports(self) -> None:
        import pose_estimation.data_extraction.wholebody_keypoint_extractor as mod
        expected = {
            "CONFIG_KEY_WHOLEBODY_EXTRACTION",
            "WholeBodyExtractionConfig",
            "WholeBodyExtractionSample",
            "WholeBodyExtractionStats",
            "WholeBodyExtractionMetadata",
            "WholeBodyKeypointExtractor",
        }
        assert set(mod.__all__) == expected

    def test_subregion_ranges(self) -> None:
        """서브 리전 인덱스 범위 검증."""
        import pose_estimation.data_extraction.wholebody_keypoint_extractor as mod
        assert mod._BODY_RANGE == (0, 17)
        assert mod._FOOT_RANGE == (17, 23)
        assert mod._FACE_RANGE == (23, 91)
        assert mod._LEFT_HAND_RANGE == (91, 112)
        assert mod._RIGHT_HAND_RANGE == (112, 133)
        # 총 133 키포인트
        total = (17 - 0) + (23 - 17) + (91 - 23) + (112 - 91) + (133 - 112)
        assert total == 133

    def test_wholebody_keypoint_names(self) -> None:
        """133개 키포인트 이름 검증."""
        import pose_estimation.data_extraction.wholebody_keypoint_extractor as mod
        assert len(mod._WHOLEBODY_KEYPOINT_NAMES) == 133


# ============================================================
# 테스트: WholeBodyExtractionConfig
# ============================================================
class TestWholeBodyExtractionConfig:
    """WholeBodyExtractionConfig 데이터클래스 테스트."""

    def test_default_values(self) -> None:
        cfg = WholeBodyExtractionConfig()
        assert cfg.enabled is True
        assert cfg.min_detections == 1
        assert cfg.min_detection_confidence == pytest.approx(0.70)
        assert cfg.min_bbox_pixels == 400
        assert cfg.min_visible_keypoints == 40
        assert cfg.min_skeleton_completeness == pytest.approx(0.30)
        assert cfg.buffer_size == 30
        assert cfg.max_total_samples == 3000
        assert cfg.jpeg_quality == 95
        assert cfg.dedup_enabled is True
        # 서브 리전 필터 기본값
        assert cfg.min_body_completeness == pytest.approx(0.60)
        assert cfg.min_hand_completeness == pytest.approx(0.0)
        assert cfg.min_foot_completeness == pytest.approx(0.0)
        assert cfg.min_face_completeness == pytest.approx(0.0)

    def test_frozen(self) -> None:
        cfg = WholeBodyExtractionConfig()
        with pytest.raises(AttributeError):
            cfg.enabled = False  # type: ignore[misc]

    def test_slots(self) -> None:
        cfg = WholeBodyExtractionConfig()
        assert not hasattr(cfg, "__dict__")

    def test_custom_values(self) -> None:
        cfg = WholeBodyExtractionConfig(
            enabled=False,
            min_detections=3,
            min_body_completeness=0.80,
            buffer_size=50,
        )
        assert cfg.enabled is False
        assert cfg.min_detections == 3
        assert cfg.min_body_completeness == pytest.approx(0.80)
        assert cfg.buffer_size == 50

    def test_critical_keypoint_indices(self) -> None:
        cfg = WholeBodyExtractionConfig()
        assert isinstance(cfg.critical_keypoint_indices, tuple)
        assert len(cfg.critical_keypoint_indices) == 6
        # 어깨(5,6), 손목(9,10), 힙(11,12)
        assert 5 in cfg.critical_keypoint_indices
        assert 6 in cfg.critical_keypoint_indices
        assert 9 in cfg.critical_keypoint_indices
        assert 10 in cfg.critical_keypoint_indices
        assert 11 in cfg.critical_keypoint_indices
        assert 12 in cfg.critical_keypoint_indices

    def test_from_config_none(self) -> None:
        cfg = WholeBodyExtractionConfig.from_config(None)
        assert cfg.enabled is True

    def test_from_config_with_loader(self) -> None:
        class MockLoader:
            def get(self, key: str, default: object = None) -> object:
                overrides = {
                    "data_extraction.wholebody_extraction.enabled": False,
                    "data_extraction.wholebody_extraction.quality_filter.min_detections": 3,
                    "data_extraction.wholebody_extraction.subregion_filter.min_body_completeness": 0.80,
                }
                return overrides.get(key, default)

        cfg = WholeBodyExtractionConfig.from_config(MockLoader())
        assert cfg.enabled is False
        assert cfg.min_detections == 3
        assert cfg.min_body_completeness == pytest.approx(0.80)


# ============================================================
# 테스트: WholeBodyExtractionSample
# ============================================================
class TestWholeBodyExtractionSample:
    """WholeBodyExtractionSample 데이터클래스 테스트."""

    def test_default_values(self) -> None:
        sample = WholeBodyExtractionSample()
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
        sample = WholeBodyExtractionSample()
        assert not hasattr(sample, "__dict__")

    def test_mutable(self) -> None:
        sample = WholeBodyExtractionSample()
        sample.sample_id = "wb_test"
        assert sample.sample_id == "wb_test"


# ============================================================
# 테스트: WholeBodyExtractionStats
# ============================================================
class TestWholeBodyExtractionStats:
    """WholeBodyExtractionStats 테스트."""

    def test_default_values(self) -> None:
        stats = WholeBodyExtractionStats()
        assert stats.total_input_frames == 0
        assert stats.total_extracted == 0
        assert stats.rejected_low_body_completeness == 0

    def test_slots(self) -> None:
        stats = WholeBodyExtractionStats()
        assert not hasattr(stats, "__dict__")

    def test_pass_rate_zero(self) -> None:
        stats = WholeBodyExtractionStats()
        assert stats.pass_rate == 0.0

    def test_pass_rate_calculated(self) -> None:
        stats = WholeBodyExtractionStats()
        stats.total_input_frames = 100
        stats.total_extracted = 60
        assert stats.pass_rate == pytest.approx(0.6)

    def test_update_completeness_ewma(self) -> None:
        stats = WholeBodyExtractionStats()
        stats.update_completeness_ewma(0.85)
        assert stats.avg_completeness == pytest.approx(0.85)

    def test_update_subregion_ewma(self) -> None:
        stats = WholeBodyExtractionStats()
        subregion_comp = {
            "body": 0.90,
            "hands_combined": 0.70,
            "foot": 0.60,
            "face": 0.50,
        }
        stats.update_subregion_ewma(subregion_comp)
        assert stats.avg_body_completeness == pytest.approx(0.90)
        assert stats.avg_hand_completeness == pytest.approx(0.70)
        assert stats.avg_foot_completeness == pytest.approx(0.60)
        assert stats.avg_face_completeness == pytest.approx(0.50)

    def test_update_subregion_ewma_subsequent(self) -> None:
        """두 번째 EWMA 업데이트 → 지수 가중."""
        stats = WholeBodyExtractionStats()
        stats.update_subregion_ewma({"body": 0.80, "hands_combined": 0.0, "foot": 0.0, "face": 0.0})
        stats.update_subregion_ewma({"body": 1.0, "hands_combined": 0.0, "foot": 0.0, "face": 0.0})
        # alpha=0.02 → 0.02*1.0 + 0.98*0.80 = 0.804
        assert stats.avg_body_completeness == pytest.approx(0.804, abs=0.001)

    def test_total_rejected_frames(self) -> None:
        stats = WholeBodyExtractionStats()
        stats.rejected_empty_frame = 3
        stats.rejected_too_few_detections = 2
        stats.rejected_keypoints_mismatch = 1
        stats.rejected_few_qualifying = 2
        stats.rejected_duplicate_frame = 1
        assert stats.total_rejected_frames == 9

    def test_total_rejected_persons(self) -> None:
        stats = WholeBodyExtractionStats()
        stats.rejected_not_player = 1
        stats.rejected_low_confidence = 2
        stats.rejected_bad_bbox_size = 1
        stats.rejected_insufficient_keypoints = 3
        stats.rejected_missing_critical = 1
        stats.rejected_low_completeness = 2
        stats.rejected_low_body_completeness = 1
        assert stats.total_rejected_persons == 11

    def test_to_dict(self) -> None:
        stats = WholeBodyExtractionStats()
        stats.total_input_frames = 80
        stats.total_extracted = 40
        d = stats.to_dict()
        assert d["total_input_frames"] == 80
        assert d["total_extracted"] == 40
        assert "frame_rejections" in d
        assert "person_rejections" in d
        assert "quality_distribution" in d
        assert "subregion_avg_completeness" in d
        assert d["pass_rate"] == pytest.approx(0.5)

    def test_quality_distribution(self) -> None:
        stats = WholeBodyExtractionStats()
        stats.quality_excellent = 10
        stats.quality_good = 20
        stats.quality_fair = 15
        d = stats.to_dict()
        assert d["quality_distribution"]["excellent"] == 10
        assert d["quality_distribution"]["good"] == 20
        assert d["quality_distribution"]["fair"] == 15


# ============================================================
# 테스트: WholeBodyExtractionMetadata
# ============================================================
class TestWholeBodyExtractionMetadata:
    """WholeBodyExtractionMetadata 테스트."""

    def test_default_values(self) -> None:
        meta = WholeBodyExtractionMetadata()
        assert meta.session_id == ""
        assert meta.keypoint_format == "coco_wholebody_133"

    def test_slots(self) -> None:
        meta = WholeBodyExtractionMetadata()
        assert not hasattr(meta, "__dict__")

    def test_to_dict(self) -> None:
        meta = WholeBodyExtractionMetadata(
            session_id="wb_test",
            source_game_id="game002",
            total_samples=50,
            total_persons=120,
            avg_completeness=0.78,
        )
        d = meta.to_dict()
        assert d["session_id"] == "wb_test"
        assert d["total_samples"] == 50
        assert d["num_keypoints"] == 133
        assert d["training_target"] == "ViTPose-WholeBody/DWPose"
        assert d["avg_completeness"] == pytest.approx(0.78, abs=0.001)
        # 서브 리전 레이아웃 검증
        assert "subregion_layout" in d
        layout = d["subregion_layout"]
        assert layout["body"]["count"] == 17
        assert layout["foot"]["count"] == 6
        assert layout["face"]["count"] == 68
        assert layout["left_hand"]["count"] == 21
        assert layout["right_hand"]["count"] == 21


# ============================================================
# 테스트: WholeBodyKeypointExtractor (클래스 레벨)
# ============================================================
class TestWholeBodyKeypointExtractor:
    """WholeBodyKeypointExtractor 클래스 테스트."""

    def test_init_default(self) -> None:
        ext = WholeBodyKeypointExtractor()
        assert ext._config is None
        assert ext._initialized is False
        assert ext._buffer == []

    def test_init_with_config(self) -> None:
        cfg = WholeBodyExtractionConfig(buffer_size=10)
        ext = WholeBodyKeypointExtractor(config=cfg)
        assert ext._config is not None
        assert ext._config.buffer_size == 10

    def test_initialize_default_config(self) -> None:
        ext = WholeBodyKeypointExtractor()
        ext.initialize()
        assert ext._initialized is True
        assert ext._config is not None

    def test_initialize_with_config(self) -> None:
        cfg = WholeBodyExtractionConfig(enabled=False, min_body_completeness=0.80)
        ext = WholeBodyKeypointExtractor()
        ext.initialize(config=cfg)
        assert ext._config.enabled is False
        assert ext._config.min_body_completeness == pytest.approx(0.80)

    def test_initialize_creates_session_id(self) -> None:
        ext = WholeBodyKeypointExtractor()
        ext.initialize()
        assert len(ext._session_id) == 16

    def test_initialize_creates_output_dirs(self) -> None:
        tmpdir = tempfile.mkdtemp()
        try:
            cfg = WholeBodyExtractionConfig(local_base_path=tmpdir)
            ext = WholeBodyKeypointExtractor(config=cfg)
            ext.initialize()
            assert os.path.isdir(ext._images_dir)
            assert os.path.isdir(ext._labels_dir)
            assert os.path.isdir(ext._annotations_dir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_extract_before_init_raises(self) -> None:
        """initialize() 전 extract_from_frame 호출 시 에러."""
        ext = WholeBodyKeypointExtractor()
        with pytest.raises(Exception):
            ext.extract_from_frame([], np.zeros((100, 100, 3), dtype=np.uint8), [])
