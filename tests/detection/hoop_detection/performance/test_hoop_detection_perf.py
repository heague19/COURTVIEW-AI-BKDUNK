# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/hoop_detection/performance
파일: test_hoop_detection_perf.py
설명: hoop_detection 모듈 성능 테스트
      - ScoringType / Config 생성 속도
      - _HoopCandidate / _NetMotionState 생성 속도
      - NetAnalyzer 프레임 처리 지연
      - _classify_pattern 판별 지연
      - HoopBboxExtractor 초기화/finalize 지연
      - NetMotionExtractor 초기화/finalize 지연

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from detection.hoop_detection.hoop_detector import (
    HoopDetectorConfig,
    ScoringType,
    _HoopCandidate,
)
from detection.hoop_detection.net_analyzer import (
    NetAnalyzer,
    NetAnalyzerConfig,
    _NetMotionState,
    _ScoringEvent,
)
from shared.interfaces.detector_interface import (
    BoundingBox as InterfaceBBox,
    HoopDetection,
)


# =============================================================================
# 데이터 클래스 생성 성능
# =============================================================================

class TestDataclassCreationPerformance:
    """데이터 클래스 생성 속도."""

    def test_HoopDetectorConfig_생성_1000회(self):
        """HoopDetectorConfig 1000회 생성 < 10ms."""
        start = time.perf_counter()
        for _ in range(1000):
            HoopDetectorConfig()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 10.0, f"HoopDetectorConfig 1000회: {elapsed_ms:.1f}ms > 10ms"

    def test_NetAnalyzerConfig_생성_1000회(self):
        """NetAnalyzerConfig 1000회 생성 < 10ms."""
        start = time.perf_counter()
        for _ in range(1000):
            NetAnalyzerConfig()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 10.0, f"NetAnalyzerConfig 1000회: {elapsed_ms:.1f}ms > 10ms"

    def test_HoopCandidate_생성_10000회(self):
        """_HoopCandidate 10000회 생성 < 50ms."""
        start = time.perf_counter()
        for i in range(10000):
            _HoopCandidate(
                bbox_x=float(i), bbox_y=100.0,
                bbox_w=60.0, bbox_h=40.0,
                yolo_confidence=0.9,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 50.0, f"_HoopCandidate 10000회: {elapsed_ms:.1f}ms > 50ms"

    def test_NetMotionState_생성_10000회(self):
        """_NetMotionState 10000회 생성 < 100ms."""
        start = time.perf_counter()
        for _ in range(10000):
            _NetMotionState()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 100.0, f"_NetMotionState 10000회: {elapsed_ms:.1f}ms > 100ms"

    def test_ScoringEvent_생성_10000회(self):
        """_ScoringEvent 10000회 생성 < 50ms."""
        start = time.perf_counter()
        for _ in range(10000):
            _ScoringEvent(
                scoring_type=ScoringType.SWISH,
                confidence=0.95,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 50.0, f"_ScoringEvent 10000회: {elapsed_ms:.1f}ms > 50ms"

    def test_ScoringType_속성_접근_10000회(self):
        """ScoringType.is_score, korean_name 10000회 < 20ms."""
        types = list(ScoringType)
        start = time.perf_counter()
        for _ in range(10000):
            for st in types:
                _ = st.is_score
                _ = st.korean_name
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 20.0, f"ScoringType 속성 10000회: {elapsed_ms:.1f}ms > 20ms"


# =============================================================================
# _HoopCandidate 연산 성능
# =============================================================================

class TestHoopCandidatePerformance:
    """_HoopCandidate 속성 계산 성능."""

    def test_속성_접근_10000회(self):
        """center/area/aspect_ratio 10000회 < 30ms."""
        c = _HoopCandidate(
            bbox_x=100.0, bbox_y=200.0,
            bbox_w=60.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        start = time.perf_counter()
        for _ in range(10000):
            _ = c.center_x
            _ = c.center_y
            _ = c.area
            _ = c.aspect_ratio
            _ = c.is_rim
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 30.0, f"속성 접근 10000회: {elapsed_ms:.1f}ms > 30ms"

    def test_to_xyxy_10000회(self):
        """to_xyxy 10000회 < 20ms."""
        c = _HoopCandidate(
            bbox_x=100.0, bbox_y=200.0,
            bbox_w=60.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        start = time.perf_counter()
        for _ in range(10000):
            c.to_xyxy()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 20.0, f"to_xyxy 10000회: {elapsed_ms:.1f}ms > 20ms"


# =============================================================================
# _NetMotionState 연산 성능
# =============================================================================

class TestNetMotionStatePerformance:
    """_NetMotionState 연산 성능."""

    def test_reset_motion_10000회(self):
        """reset_motion 10000회 < 20ms."""
        state = _NetMotionState(
            is_active=True,
            accumulated_vertical=25.0,
            accumulated_horizontal=5.0,
            direction_changes=3,
            frame_count=10,
        )
        start = time.perf_counter()
        for _ in range(10000):
            state.reset_motion()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 20.0, f"reset_motion 10000회: {elapsed_ms:.1f}ms > 20ms"

    def test_apply_decay_10000회(self):
        """apply_decay 10000회 < 10ms."""
        state = _NetMotionState(
            accumulated_vertical=100.0,
            accumulated_horizontal=50.0,
        )
        start = time.perf_counter()
        for _ in range(10000):
            state.apply_decay(0.95)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 10.0, f"apply_decay 10000회: {elapsed_ms:.1f}ms > 10ms"

    def test_total_displacement_10000회(self):
        """total_displacement 10000회 < 15ms."""
        state = _NetMotionState(
            accumulated_vertical=15.0,
            accumulated_horizontal=8.0,
        )
        start = time.perf_counter()
        for _ in range(10000):
            _ = state.total_displacement
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 15.0, f"total_displacement 10000회: {elapsed_ms:.1f}ms > 15ms"


# =============================================================================
# NetAnalyzer 성능
# =============================================================================

class TestNetAnalyzerPerformance:
    """NetAnalyzer 처리 성능."""

    def _make_hoop(self, side="left") -> HoopDetection:
        return HoopDetection(
            bounding_box=InterfaceBBox(x=290, y=100, width=60, height=40),
            rim_center=(320.0, 130.0),
            rim_radius=25.0,
            hoop_side=side,
        )

    def test_초기화_종료_1000회(self):
        """초기화/종료 1000회 < 200ms."""
        config = NetAnalyzerConfig()
        analyzer = NetAnalyzer()

        start = time.perf_counter()
        for _ in range(1000):
            analyzer.initialize(config)
            analyzer.shutdown()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 200.0, f"init/shutdown 1000회: {elapsed_ms:.1f}ms > 200ms"

    def test_analyze_100프레임_지연(self):
        """정적 프레임 100회 analyze < 500ms."""
        analyzer = NetAnalyzer()
        analyzer.initialize(NetAnalyzerConfig())
        hoop = self._make_hoop()

        # 추적 가능한 특징이 있는 프레임
        frame = np.full((480, 640, 3), 80, dtype=np.uint8)
        for x in range(300, 345, 5):
            cv2.line(frame, (x, 145), (x, 195), (220, 220, 220), 2)

        start = time.perf_counter()
        for i in range(100):
            analyzer.analyze(frame, hoop, frame_index=i)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 500.0, f"analyze 100프레임: {elapsed_ms:.1f}ms > 500ms"

    def test_classify_pattern_10000회(self):
        """_classify_pattern 10000회 < 100ms."""
        analyzer = NetAnalyzer()
        analyzer.initialize(NetAnalyzerConfig())
        config = NetAnalyzerConfig()

        state = _NetMotionState(
            hoop_side="left",
            is_active=True,
            accumulated_vertical=25.0,
            accumulated_horizontal=2.0,
            direction_changes=0,
            frame_count=8,
        )

        start = time.perf_counter()
        for i in range(10000):
            analyzer._classify_pattern(state, i, None, config)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 100.0, f"classify_pattern 10000회: {elapsed_ms:.1f}ms > 100ms"

    def test_상태_관리_메모리(self):
        """100개 골대 상태 생성 → 메모리 과다 없음."""
        analyzer = NetAnalyzer()
        analyzer.initialize(NetAnalyzerConfig())

        for i in range(100):
            analyzer._get_or_create_state(f"side_{i}")

        all_states = analyzer.get_all_states()
        assert len(all_states) == 100

        # shutdown으로 정리
        analyzer.shutdown()
        assert len(analyzer.get_all_states()) == 0


# =============================================================================
# data_extraction 초기화/종료 성능
# =============================================================================

class TestDataExtractionPerformance:
    """data_extraction 초기화/종료 성능."""

    def test_HoopBboxExtractor_초기화_100회(self, tmp_path):
        """HoopBboxExtractor 초기화 100회 < 500ms."""
        from detection.hoop_detection.data_extraction.hoop_bbox_extractor import (
            HoopBboxExtractor,
            HoopBboxExtractorConfig,
        )

        config = HoopBboxExtractorConfig(
            output_dir=str(tmp_path / "hoop_perf"),
            enabled=True,
        )

        start = time.perf_counter()
        for i in range(100):
            ext = HoopBboxExtractor(config)
            ext.initialize(session_id=f"perf_{i}", game_id="game")
            ext.finalize()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 500.0, f"init/finalize 100회: {elapsed_ms:.1f}ms > 500ms"

    def test_NetMotionExtractor_초기화_100회(self, tmp_path):
        """NetMotionExtractor 초기화 100회 < 500ms."""
        from detection.hoop_detection.data_extraction.net_motion_extractor import (
            NetMotionExtractor,
            NetMotionExtractorConfig,
        )

        config = NetMotionExtractorConfig(
            output_dir=str(tmp_path / "net_perf"),
            enabled=True,
        )

        start = time.perf_counter()
        for i in range(100):
            ext = NetMotionExtractor(config)
            ext.initialize(session_id=f"perf_{i}", game_id="game")
            ext.finalize()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 500.0, f"init/finalize 100회: {elapsed_ms:.1f}ms > 500ms"
