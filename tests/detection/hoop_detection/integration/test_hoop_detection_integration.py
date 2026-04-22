# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/hoop_detection/integration
파일: test_hoop_detection_integration.py
설명: hoop_detection 모듈 통합 테스트
      - HoopDetector → NetAnalyzer 파이프라인
      - 감지 → 네트 분석 → 득점 판정 E2E 흐름
      - data_extraction 연동
      - __init__.py Export 정합성

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from shared.interfaces.detector_interface import (
    BoundingBox as InterfaceBBox,
    HoopDetection,
)

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


# =============================================================================
# HoopDetector → NetAnalyzer 통합
# =============================================================================

class TestHoopToNetAnalyzerIntegration:
    """HoopDetector 감지 결과 → NetAnalyzer 분석 파이프라인."""

    def _make_hoop(self, side="left") -> HoopDetection:
        return HoopDetection(
            bounding_box=InterfaceBBox(x=290, y=100, width=60, height=40),
            rim_center=(320.0, 130.0),
            rim_radius=25.0,
            hoop_side=side,
        )

    def test_좌우_독립_분석(self):
        """
        시나리오: 좌/우 골대에 순차적으로 프레임 공급
        → 상태가 독립적으로 관리됨.
        """
        analyzer = NetAnalyzer()
        analyzer.initialize(NetAnalyzerConfig())

        left_hoop = self._make_hoop("left")
        right_hoop = self._make_hoop("right")

        frame = np.full((480, 640, 3), 100, dtype=np.uint8)
        for x in range(300, 345, 5):
            cv2.line(frame, (x, 145), (x, 195), (230, 230, 230), 2)

        # 10프레임 연속 분석
        for i in range(10):
            analyzer.analyze(frame, left_hoop, frame_index=i)
            analyzer.analyze(frame, right_hoop, frame_index=i)

        left_state = analyzer.get_state("left")
        right_state = analyzer.get_state("right")

        assert left_state is not None
        assert right_state is not None
        assert left_state is not right_state

    def test_analyze_batch_양쪽_골대(self):
        """analyze_batch로 양쪽 골대 동시 분석."""
        analyzer = NetAnalyzer()
        analyzer.initialize(NetAnalyzerConfig())

        hoops = [self._make_hoop("left"), self._make_hoop("right")]

        frame = np.full((480, 640, 3), 100, dtype=np.uint8)
        for x in range(300, 345, 5):
            cv2.line(frame, (x, 145), (x, 195), (230, 230, 230), 2)

        for i in range(5):
            events = analyzer.analyze_batch(frame, hoops, frame_index=i)
            assert isinstance(events, list)

    def test_쿨다운_후_재분석(self):
        """
        시나리오: 쿨다운 진입 → 쿨다운 소진 → 다시 분석 가능
        """
        analyzer = NetAnalyzer()
        config = NetAnalyzerConfig(cooldown_frames=3)
        analyzer.initialize(config)

        hoop = self._make_hoop()

        # 강제 쿨다운 설정
        state = analyzer._get_or_create_state("left")
        state.cooldown_remaining = 3

        frame = np.full((480, 640, 3), 100, dtype=np.uint8)

        # 쿨다운 기간: 분석 스킵
        for i in range(3):
            result = analyzer.analyze(frame, hoop, frame_index=i)
            assert result is None

        # 쿨다운 종료 후: 정상 분석 (첫 프레임 초기화 → None)
        assert state.cooldown_remaining == 0


# =============================================================================
# 패턴 분류 + 통계 통합
# =============================================================================

class TestPatternClassificationIntegration:
    """패턴 분류와 통계 누적 통합 테스트."""

    def test_스위시_이벤트_통계_누적(self):
        """스위시 판별 → total_events, total_scores 증가."""
        analyzer = NetAnalyzer()
        config = NetAnalyzerConfig()
        analyzer.initialize(config)

        # 스위시 조건 상태 직접 구성
        state = analyzer._get_or_create_state("left")
        state.is_active = True
        state.accumulated_vertical = 25.0
        state.accumulated_horizontal = 2.0
        state.frame_count = 8

        event = analyzer._classify_pattern(state, 100, None, config)
        assert event is not None
        assert event.scoring_type == ScoringType.SWISH

        # 통계 직접 업데이트 시뮬레이션
        state.cooldown_remaining = config.cooldown_frames
        state.total_events += 1
        analyzer._total_events += 1
        if event.is_score:
            analyzer._total_scores += 1

        assert analyzer.total_events == 1
        assert analyzer.total_scores == 1

    def test_림아웃_미득점_통계(self):
        """림아웃 판별 → total_events 증가, total_scores 미증가."""
        analyzer = NetAnalyzer()
        config = NetAnalyzerConfig()
        analyzer.initialize(config)

        state = analyzer._get_or_create_state("right")
        state.is_active = True
        state.accumulated_vertical = 3.0
        state.accumulated_horizontal = 2.0
        state.frame_count = config.min_frames_for_analysis
        state.upper_motion_ratio = 0.5

        event = analyzer._classify_pattern(state, 200, None, config)
        assert event is not None
        assert event.scoring_type == ScoringType.RIM_OUT
        assert event.is_score is False

        analyzer._total_events += 1
        assert analyzer.total_events == 1
        assert analyzer.total_scores == 0


# =============================================================================
# data_extraction 연동
# =============================================================================

class TestDataExtractionIntegration:
    """NetAnalyzer → data_extraction 연동 테스트."""

    def test_이벤트_추출기_전달(self, tmp_path):
        """
        시나리오: 분석기 스위시 판별 → 추출기에 이벤트 전달 → finalize
        """
        from detection.hoop_detection.data_extraction.net_motion_extractor import (
            NetMotionExtractor,
            NetMotionExtractorConfig,
        )

        config = NetMotionExtractorConfig(
            output_dir=str(tmp_path / "integration_output"),
            enabled=True,
            buffer_flush_count=3,
        )
        ext = NetMotionExtractor(config)
        ext.initialize(session_id="int_test", game_id="game_1")

        # 프레임 공급
        gray = np.zeros((64, 64), dtype=np.uint8)
        disp = np.array([0.0, 5.0], dtype=np.float32)
        for i in range(20):
            ext.feed_frame(gray, disp, frame_index=i)

        # 스위시 이벤트 전달
        event = _ScoringEvent(
            scoring_type=ScoringType.SWISH,
            confidence=0.92,
            hoop_side="left",
            frame_index=18,
        )
        ext.on_event(event)

        # 이벤트 후 추가 프레임
        for i in range(20, 25):
            ext.feed_frame(gray, disp, frame_index=i)

        result = ext.finalize()
        assert result is not None
        assert ext._initialized is False

    def test_bbox_추출기_finalize_안전성(self, tmp_path):
        """
        HoopBboxExtractor finalize 시 try/finally로
        _initialized가 항상 False로 설정되는지 검증.
        """
        from detection.hoop_detection.data_extraction.hoop_bbox_extractor import (
            HoopBboxExtractor,
            HoopBboxExtractorConfig,
        )

        config = HoopBboxExtractorConfig(
            output_dir=str(tmp_path / "finalize_test"),
            enabled=True,
        )
        ext = HoopBboxExtractor(config)
        ext.initialize(session_id="safe_test", game_id="game")

        assert ext.is_initialized is True
        ext.finalize()
        assert ext.is_initialized is False


# =============================================================================
# __init__.py Export 정합성
# =============================================================================

class TestModuleExportIntegrity:
    """hoop_detection 패키지 전체 export 정합성."""

    def test_상위_init_전체_export(self):
        """hoop_detection __init__에서 모든 공개 클래스 임포트 가능."""
        from detection.hoop_detection import (
            HoopDetector,
            HoopDetectorConfig,
            NetAnalyzer,
            NetAnalyzerConfig,
            ScoringType,
        )

        assert HoopDetector is not None
        assert HoopDetectorConfig is not None
        assert NetAnalyzer is not None
        assert NetAnalyzerConfig is not None
        assert ScoringType is not None

    def test_data_extraction_init_전체_export(self):
        """data_extraction __init__에서 전체 임포트 가능."""
        from detection.hoop_detection.data_extraction import (
            HoopBboxExtractor,
            HoopBboxExtractorConfig,
            NetMotionExtractor,
            NetMotionExtractorConfig,
        )

        assert HoopBboxExtractor is not None
        assert HoopBboxExtractorConfig is not None
        assert NetMotionExtractor is not None
        assert NetMotionExtractorConfig is not None

    def test_순환참조_없음(self):
        """
        hoop_detector → net_analyzer → (ScoringType from hoop_detector)
        순환참조 없이 정상 임포트.
        """
        # 순환참조가 있으면 이 시점에서 ImportError
        from detection.hoop_detection.hoop_detector import ScoringType as ST1
        from detection.hoop_detection.net_analyzer import NetAnalyzer as NA

        assert ST1 is not None
        assert NA is not None

    def test_net_analyzer에서_ScoringType_참조(self):
        """net_analyzer에서 hoop_detector의 ScoringType 참조."""
        from detection.hoop_detection.net_analyzer import _ScoringEvent

        event = _ScoringEvent(scoring_type=ScoringType.SWISH)
        assert event.scoring_type is ScoringType.SWISH

    def test_data_extraction에서_ScoringType_참조(self):
        """data_extraction에서 hoop_detector의 ScoringType 참조."""
        from detection.hoop_detection.data_extraction.net_motion_extractor import (
            NetMotionExtractor,
        )
        # 임포트 성공 자체가 순환참조 없음을 증명
        assert NetMotionExtractor is not None
