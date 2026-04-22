# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/hoop_detection/data_extraction/unit
파일: test_data_extractors.py
설명: 데이터 추출기 2종 단위 테스트
      - HoopBboxExtractor: 림/백보드 bbox 크롭 수집
      - NetMotionExtractor: 네트 움직임 시퀀스 수집

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from shared.constants.hoop_constants import (
    HOOP_CLASS_ID_BACKBOARD,
    HOOP_CLASS_ID_RIM,
    HOOP_DETECTION_CONFIDENCE_THRESHOLD,
)
from shared.interfaces.detector_interface import (
    BoundingBox as InterfaceBBox,
    HoopDetection,
)
from detection.hoop_detection.hoop_detector import ScoringType
from detection.hoop_detection.net_analyzer import _ScoringEvent


# =============================================================================
# HoopBboxExtractor 테스트
# =============================================================================

class TestHoopBboxExtractor:
    """HoopBboxExtractor 단위 테스트."""

    def _make_extractor(self, tmp_path: Path):
        """HoopBboxExtractor 인스턴스 생성 + 초기화."""
        from detection.hoop_detection.data_extraction.hoop_bbox_extractor import (
            HoopBboxExtractor,
            HoopBboxExtractorConfig,
        )

        config = HoopBboxExtractorConfig(
            output_dir=str(tmp_path / "hoop_output"),
            enabled=True,
            buffer_flush_count=5,
        )
        ext = HoopBboxExtractor(config)
        ext.initialize(session_id="test_session", game_id="test_game")
        return ext

    def _make_hoop(
        self, x=290.0, y=100.0, w=60.0, h=40.0,
    ) -> HoopDetection:
        return HoopDetection(
            bounding_box=InterfaceBBox(x=x, y=y, width=w, height=h),
            rim_center=(x + w / 2, y + h / 2),
            rim_radius=w / 2,
            hoop_side="left",
        )

    def test_초기화(self, tmp_path):
        """초기화 후 is_initialized=True."""
        ext = self._make_extractor(tmp_path)
        assert ext.is_initialized is True

    def test_미초기화_시_process_거부(self, tmp_path):
        """initialize() 없이 process → False."""
        from detection.hoop_detection.data_extraction.hoop_bbox_extractor import (
            HoopBboxExtractor,
            HoopBboxExtractorConfig,
        )

        config = HoopBboxExtractorConfig(
            output_dir=str(tmp_path / "hoop_output"),
            enabled=True,
        )
        ext = HoopBboxExtractor(config)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        hoop = self._make_hoop()
        result = ext.process(
            frame, hoop,
            confidence=0.95, class_id=HOOP_CLASS_ID_RIM,
            frame_index=0,
        )
        assert result is False

    def test_저신뢰도_거부(self, tmp_path):
        """신뢰도 미달 → 거부."""
        ext = self._make_extractor(tmp_path)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        hoop = self._make_hoop()
        result = ext.process(
            frame, hoop,
            confidence=0.1,
            class_id=HOOP_CLASS_ID_RIM,
            frame_index=0,
        )
        assert result is False

    def test_유효_감지_처리(self, tmp_path):
        """유효한 감지 → 처리 시도."""
        ext = self._make_extractor(tmp_path)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # 림 영역에 색상 추가
        cv2.circle(frame, (320, 120), 25, (30, 100, 230), 3)

        hoop = self._make_hoop()
        result = ext.process(
            frame, hoop,
            confidence=0.95, class_id=HOOP_CLASS_ID_RIM,
            frame_index=0,
        )
        assert isinstance(result, bool)

    def test_finalize_미초기화(self, tmp_path):
        """초기화 없이 finalize → None."""
        from detection.hoop_detection.data_extraction.hoop_bbox_extractor import (
            HoopBboxExtractor,
            HoopBboxExtractorConfig,
        )

        config = HoopBboxExtractorConfig(
            output_dir=str(tmp_path / "hoop_output"),
            enabled=True,
        )
        ext = HoopBboxExtractor(config)
        result = ext.finalize()
        assert result is None

    def test_finalize_빈_세션(self, tmp_path):
        """처리 없이 finalize → record_count=0."""
        ext = self._make_extractor(tmp_path)
        result = ext.finalize()
        assert result is not None
        assert result.record_count == 0

    def test_finalize_후_미초기화(self, tmp_path):
        """finalize 후 is_initialized=False (try/finally 검증)."""
        ext = self._make_extractor(tmp_path)
        ext.finalize()
        assert ext.is_initialized is False

    def test_비활성화(self, tmp_path):
        """enabled=False → 초기화 무시."""
        from detection.hoop_detection.data_extraction.hoop_bbox_extractor import (
            HoopBboxExtractor,
            HoopBboxExtractorConfig,
        )

        config = HoopBboxExtractorConfig(
            output_dir=str(tmp_path / "hoop_output"),
            enabled=False,
        )
        ext = HoopBboxExtractor(config)
        ext.initialize(session_id="test", game_id="test")
        assert ext.is_initialized is False

    def test_total_processed_증가(self, tmp_path):
        """process 호출마다 total_processed 증가."""
        ext = self._make_extractor(tmp_path)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        hoop = self._make_hoop()

        ext.process(frame, hoop, confidence=0.95, class_id=0, frame_index=0)
        ext.process(frame, hoop, confidence=0.95, class_id=0, frame_index=1)

        assert ext.total_processed == 2

    def test_config_slots(self):
        """HoopBboxExtractorConfig slots 적용."""
        from detection.hoop_detection.data_extraction.hoop_bbox_extractor import (
            HoopBboxExtractorConfig,
        )
        config = HoopBboxExtractorConfig()
        assert not hasattr(config, "__dict__")


# =============================================================================
# NetMotionExtractor 테스트
# =============================================================================

class TestNetMotionExtractor:
    """NetMotionExtractor 단위 테스트."""

    def _make_extractor(self, tmp_path: Path):
        """NetMotionExtractor 인스턴스 생성 + 초기화."""
        from detection.hoop_detection.data_extraction.net_motion_extractor import (
            NetMotionExtractor,
            NetMotionExtractorConfig,
        )

        config = NetMotionExtractorConfig(
            output_dir=str(tmp_path / "net_motion_output"),
            enabled=True,
            buffer_flush_count=3,
        )
        ext = NetMotionExtractor(config)
        ext.initialize(session_id="test_session", game_id="test_game")
        return ext

    def test_초기화(self, tmp_path):
        """초기화 후 is_initialized=True."""
        ext = self._make_extractor(tmp_path)
        assert ext._initialized is True

    def test_미초기화_시_feed_무시(self, tmp_path):
        """initialize() 없이 feed_frame → 무시."""
        from detection.hoop_detection.data_extraction.net_motion_extractor import (
            NetMotionExtractor,
            NetMotionExtractorConfig,
        )

        config = NetMotionExtractorConfig(
            output_dir=str(tmp_path / "net_motion_output"),
            enabled=True,
        )
        ext = NetMotionExtractor(config)
        gray = np.zeros((64, 64), dtype=np.uint8)
        disp = np.array([0.0, 0.0], dtype=np.float32)
        # 미초기화 → 예외 없이 무시
        ext.feed_frame(gray, disp, frame_index=0)

    def test_finalize_미초기화(self, tmp_path):
        """초기화 없이 finalize → None."""
        from detection.hoop_detection.data_extraction.net_motion_extractor import (
            NetMotionExtractor,
            NetMotionExtractorConfig,
        )

        config = NetMotionExtractorConfig(
            output_dir=str(tmp_path / "net_motion_output"),
            enabled=True,
        )
        ext = NetMotionExtractor(config)
        result = ext.finalize()
        assert result is None

    def test_finalize_빈_세션(self, tmp_path):
        """이벤트 없이 finalize → record_count=0."""
        ext = self._make_extractor(tmp_path)
        result = ext.finalize()
        assert result is not None
        assert result.record_count == 0

    def test_finalize_후_미초기화(self, tmp_path):
        """finalize 후 _initialized=False (try/finally 검증)."""
        ext = self._make_extractor(tmp_path)
        ext.finalize()
        assert ext._initialized is False

    def test_on_event_쿨다운(self, tmp_path):
        """이벤트 수신 시 수집 시작."""
        ext = self._make_extractor(tmp_path)

        # 프레임 몇 개 공급
        gray = np.zeros((64, 64), dtype=np.uint8)
        disp = np.array([0.0, 5.0], dtype=np.float32)
        for i in range(15):
            ext.feed_frame(gray, disp, frame_index=i)

        # 이벤트 발생
        event = _ScoringEvent(
            scoring_type=ScoringType.SWISH,
            confidence=0.9,
            hoop_side="left",
            frame_index=14,
        )
        ext.on_event(event)
        assert ext._total_events >= 1

    def test_비활성화(self, tmp_path):
        """enabled=False → 초기화 무시."""
        from detection.hoop_detection.data_extraction.net_motion_extractor import (
            NetMotionExtractor,
            NetMotionExtractorConfig,
        )

        config = NetMotionExtractorConfig(
            output_dir=str(tmp_path / "net_motion_output"),
            enabled=False,
        )
        ext = NetMotionExtractor(config)
        ext.initialize(session_id="test", game_id="test")
        assert ext._initialized is False

    def test_config_slots(self):
        """NetMotionExtractorConfig slots 적용."""
        from detection.hoop_detection.data_extraction.net_motion_extractor import (
            NetMotionExtractorConfig,
        )
        config = NetMotionExtractorConfig()
        assert not hasattr(config, "__dict__")


# =============================================================================
# __init__.py Export 테스트
# =============================================================================

class TestDataExtractionExport:
    """data_extraction 패키지 export 테스트."""

    def test_init_포함_HoopBboxExtractor(self):
        """HoopBboxExtractor가 __all__에 포함."""
        from detection.hoop_detection.data_extraction import __all__
        assert "HoopBboxExtractor" in __all__

    def test_init_포함_HoopBboxExtractorConfig(self):
        """HoopBboxExtractorConfig가 __all__에 포함."""
        from detection.hoop_detection.data_extraction import __all__
        assert "HoopBboxExtractorConfig" in __all__

    def test_init_포함_NetMotionExtractor(self):
        """NetMotionExtractor가 __all__에 포함."""
        from detection.hoop_detection.data_extraction import __all__
        assert "NetMotionExtractor" in __all__

    def test_init_포함_NetMotionExtractorConfig(self):
        """NetMotionExtractorConfig가 __all__에 포함."""
        from detection.hoop_detection.data_extraction import __all__
        assert "NetMotionExtractorConfig" in __all__

    def test_init_version(self):
        """data_extraction __version__."""
        from detection.hoop_detection import data_extraction
        assert data_extraction.__version__ == "1.0.0"
