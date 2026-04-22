# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/pose_estimation/data_extraction/unit
파일: test_pose_sequence_extractor.py
설명: pose_sequence_extractor.py 단위 테스트

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

from pose_estimation.data_extraction.pose_sequence_extractor import (
    CONFIG_KEY_POSE_SEQUENCE_EXTRACTION,
    PhaseSegment,
    PoseSequenceConfig,
    PoseSequenceExtractor,
    PoseSequenceMetadata,
    PoseSequenceSample,
    PoseSequenceStats,
)


# ============================================================
# 테스트: 모듈 레벨 상수
# ============================================================
class TestModuleConstants:
    """모듈 상수 테스트."""

    def test_config_key(self) -> None:
        assert CONFIG_KEY_POSE_SEQUENCE_EXTRACTION == "data_extraction.pose_sequence_extraction"

    def test_version(self) -> None:
        import pose_estimation.data_extraction.pose_sequence_extractor as mod
        assert mod.__version__ == "1.0.0"

    def test_all_exports(self) -> None:
        import pose_estimation.data_extraction.pose_sequence_extractor as mod
        expected = {
            "CONFIG_KEY_POSE_SEQUENCE_EXTRACTION",
            "PhaseSegment",
            "PoseSequenceConfig",
            "PoseSequenceSample",
            "PoseSequenceStats",
            "PoseSequenceMetadata",
            "PoseSequenceExtractor",
        }
        assert set(mod.__all__) == expected


# ============================================================
# 테스트: PhaseSegment
# ============================================================
class TestPhaseSegment:
    """PhaseSegment 데이터클래스 테스트."""

    def test_creation(self) -> None:
        seg = PhaseSegment(phase_name="preparation", start_frame=0, end_frame=15)
        assert seg.phase_name == "preparation"
        assert seg.start_frame == 0
        assert seg.end_frame == 15

    def test_frozen(self) -> None:
        seg = PhaseSegment(phase_name="execution", start_frame=10, end_frame=20)
        with pytest.raises(AttributeError):
            seg.phase_name = "other"  # type: ignore[misc]

    def test_slots(self) -> None:
        seg = PhaseSegment(phase_name="test", start_frame=0, end_frame=5)
        assert not hasattr(seg, "__dict__")

    def test_equality(self) -> None:
        s1 = PhaseSegment("preparation", 0, 15)
        s2 = PhaseSegment("preparation", 0, 15)
        assert s1 == s2

    def test_inequality(self) -> None:
        s1 = PhaseSegment("preparation", 0, 15)
        s2 = PhaseSegment("execution", 16, 30)
        assert s1 != s2


# ============================================================
# 테스트: PoseSequenceConfig
# ============================================================
class TestPoseSequenceConfig:
    """PoseSequenceConfig 데이터클래스 테스트."""

    def test_default_values(self) -> None:
        cfg = PoseSequenceConfig()
        assert cfg.enabled is True
        assert cfg.min_frames == 10
        assert cfg.max_frames == 150
        assert cfg.buffer_size == 10
        assert cfg.max_total_sequences == 2000
        assert cfg.dedup_enabled is True

    def test_frozen(self) -> None:
        cfg = PoseSequenceConfig()
        with pytest.raises(AttributeError):
            cfg.enabled = False  # type: ignore[misc]

    def test_slots(self) -> None:
        cfg = PoseSequenceConfig()
        assert not hasattr(cfg, "__dict__")

    def test_custom_values(self) -> None:
        cfg = PoseSequenceConfig(
            enabled=False,
            min_frames=16,
            max_frames=60,
            buffer_size=5,
        )
        assert cfg.enabled is False
        assert cfg.min_frames == 16
        assert cfg.max_frames == 60

    def test_valid_action_types(self) -> None:
        cfg = PoseSequenceConfig()
        assert isinstance(cfg.valid_action_types, tuple)
        assert "shooting" in cfg.valid_action_types
        assert "dribbling" in cfg.valid_action_types

    def test_from_config_none(self) -> None:
        cfg = PoseSequenceConfig.from_config(None)
        assert cfg.enabled is True
        assert cfg.min_frames == 10

    def test_from_config_with_loader(self) -> None:
        class MockLoader:
            def get(self, key: str, default: object = None) -> object:
                overrides = {
                    "data_extraction.pose_sequence_extraction.enabled": False,
                    "data_extraction.pose_sequence_extraction.sequence.min_frames": 16,
                }
                return overrides.get(key, default)

        cfg = PoseSequenceConfig.from_config(MockLoader())
        assert cfg.enabled is False
        assert cfg.min_frames == 16


# ============================================================
# 테스트: PoseSequenceSample
# ============================================================
class TestPoseSequenceSample:
    """PoseSequenceSample 데이터클래스 테스트."""

    def test_default_values(self) -> None:
        sample = PoseSequenceSample()
        assert sample.sequence_id == ""
        assert sample.action_type == ""
        assert sample.frame_jpegs == []
        assert sample.keypoints_data == {}
        assert sample.labels_data == {}
        assert sample.frame_count == 0
        assert sample.avg_completeness == 0.0
        assert sample.representative_hash == ""

    def test_slots(self) -> None:
        sample = PoseSequenceSample()
        assert not hasattr(sample, "__dict__")

    def test_mutable(self) -> None:
        sample = PoseSequenceSample()
        sample.sequence_id = "seq123"
        assert sample.sequence_id == "seq123"

    def test_list_default_factory(self) -> None:
        """각 인스턴스 별도 리스트."""
        s1 = PoseSequenceSample()
        s2 = PoseSequenceSample()
        s1.frame_jpegs.append(b"data")
        assert len(s2.frame_jpegs) == 0


# ============================================================
# 테스트: PoseSequenceStats
# ============================================================
class TestPoseSequenceStats:
    """PoseSequenceStats 테스트."""

    def test_default_values(self) -> None:
        stats = PoseSequenceStats()
        assert stats.total_input_sequences == 0
        assert stats.total_extracted == 0

    def test_slots(self) -> None:
        stats = PoseSequenceStats()
        assert not hasattr(stats, "__dict__")

    def test_pass_rate_zero(self) -> None:
        stats = PoseSequenceStats()
        assert stats.pass_rate == 0.0

    def test_pass_rate_calculated(self) -> None:
        stats = PoseSequenceStats()
        stats.total_input_sequences = 50
        stats.total_extracted = 30
        assert stats.pass_rate == pytest.approx(0.6)

    def test_update_completeness_ewma_first(self) -> None:
        stats = PoseSequenceStats()
        stats.update_completeness_ewma(0.90)
        assert stats.avg_completeness == pytest.approx(0.90)

    def test_update_completeness_ewma_subsequent(self) -> None:
        stats = PoseSequenceStats()
        stats.update_completeness_ewma(0.80)
        stats.update_completeness_ewma(1.0)
        # alpha=0.02 → 0.02*1.0 + 0.98*0.80 = 0.804
        assert stats.avg_completeness == pytest.approx(0.804, abs=0.001)

    def test_total_rejected(self) -> None:
        stats = PoseSequenceStats()
        stats.rejected_length_mismatch = 2
        stats.rejected_empty_sequence = 3
        stats.rejected_too_few_frames = 1
        stats.rejected_too_many_frames = 1
        stats.rejected_invalid_action = 2
        stats.rejected_invalid_phases = 1
        stats.rejected_low_valid_ratio = 0
        stats.rejected_low_avg_completeness = 0
        stats.rejected_duplicate = 0
        assert stats.total_rejected == 10

    def test_to_dict(self) -> None:
        stats = PoseSequenceStats()
        stats.total_input_sequences = 40
        stats.total_extracted = 20
        d = stats.to_dict()
        assert d["total_input_sequences"] == 40
        assert d["total_extracted"] == 20
        assert "rejections" in d
        assert "frame_stats" in d
        assert "action_distribution" in d
        assert d["pass_rate"] == pytest.approx(0.5)


# ============================================================
# 테스트: PoseSequenceMetadata
# ============================================================
class TestPoseSequenceMetadata:
    """PoseSequenceMetadata 테스트."""

    def test_default_values(self) -> None:
        meta = PoseSequenceMetadata()
        assert meta.session_id == ""
        assert meta.keypoint_format == "coco_17"

    def test_slots(self) -> None:
        meta = PoseSequenceMetadata()
        assert not hasattr(meta, "__dict__")

    def test_to_dict(self) -> None:
        meta = PoseSequenceMetadata(
            session_id="test_seq",
            source_game_id="game001",
            total_sequences=50,
            total_frames=600,
            avg_completeness=0.91,
        )
        d = meta.to_dict()
        assert d["session_id"] == "test_seq"
        assert d["total_sequences"] == 50
        assert d["total_frames"] == 600
        assert d["training_target"] == "LSTM/Transformer/ST-GCN"
        assert d["avg_completeness"] == pytest.approx(0.91, abs=0.001)


# ============================================================
# 테스트: PoseSequenceExtractor (클래스 레벨)
# ============================================================
class TestPoseSequenceExtractor:
    """PoseSequenceExtractor 클래스 테스트."""

    def test_init_default(self) -> None:
        ext = PoseSequenceExtractor()
        assert ext._config is None
        assert ext._initialized is False
        assert ext._buffer == []

    def test_init_with_config(self) -> None:
        cfg = PoseSequenceConfig(buffer_size=5)
        ext = PoseSequenceExtractor(config=cfg)
        assert ext._config is not None
        assert ext._config.buffer_size == 5

    def test_initialize_default_config(self) -> None:
        ext = PoseSequenceExtractor()
        ext.initialize()
        assert ext._initialized is True
        assert ext._config is not None

    def test_initialize_with_config(self) -> None:
        cfg = PoseSequenceConfig(enabled=False)
        ext = PoseSequenceExtractor()
        ext.initialize(config=cfg)
        assert ext._config.enabled is False

    def test_initialize_creates_session_id(self) -> None:
        ext = PoseSequenceExtractor()
        ext.initialize()
        assert len(ext._session_id) == 16

    def test_initialize_creates_output_dirs(self) -> None:
        tmpdir = tempfile.mkdtemp()
        try:
            cfg = PoseSequenceConfig(local_base_path=tmpdir)
            ext = PoseSequenceExtractor(config=cfg)
            ext.initialize()
            assert os.path.isdir(ext._output_dir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_extract_before_init_raises(self) -> None:
        """initialize() 전 extract_sequence 호출 시 에러."""
        ext = PoseSequenceExtractor()
        with pytest.raises(Exception):
            ext.extract_sequence(
                frames=[np.zeros((100, 100, 3), dtype=np.uint8)],
                keypoints_per_frame=[np.zeros((17, 3), dtype=np.float32)],
                action_type="shooting",
            )
