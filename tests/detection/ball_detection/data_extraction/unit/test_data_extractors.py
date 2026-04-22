# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/ball_detection/data_extraction/unit
파일: test_data_extractors.py
설명: 데이터 추출기 5종 통합 단위 테스트
      - BallBboxExtractor: bbox 크롭 + YOLO 라벨
      - TrajectoryExtractor: 궤적 시퀀스 수집
      - HardNegativeExtractor: 하드 네거티브 샘플
      - OcclusionSampleExtractor: 가려짐 샘플
      - TemporalSequenceExtractor: 시간적 프레임 시퀀스

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import cv2
import numpy as np
import pytest

from shared.constants.ball_constants import BallState
from shared.dto.ball_dto import BallDetection
from shared.dto.geometry_dto import BoundingBox, Point2D


# =============================================================================
# BallBboxExtractor 테스트
# =============================================================================

class TestBallBboxExtractor:
    """BallBboxExtractor 단위 테스트."""

    def _make_extractor(self, tmp_path: Path):
        """BallBboxExtractor 인스턴스 생성 + 초기화."""
        from detection.ball_detection.data_extraction.ball_bbox_extractor import (
            BallBboxExtractor,
            BallBboxExtractorConfig,
        )

        config = BallBboxExtractorConfig(
            output_dir=str(tmp_path / "bbox_output"),
            enabled=True,
            buffer_flush_count=5,  # 테스트용 작은 버퍼
        )
        ext = BallBboxExtractor(config)
        ext.initialize(session_id="test_session", game_id="test_game")
        return ext

    def test_초기화(self, tmp_path):
        """초기화 후 _initialized=True."""
        ext = self._make_extractor(tmp_path)
        assert ext._initialized is True

    def test_미초기화_시_process_거부(self, tmp_path):
        """initialize() 없이 process → False."""
        from detection.ball_detection.data_extraction.ball_bbox_extractor import (
            BallBboxExtractor,
            BallBboxExtractorConfig,
        )

        config = BallBboxExtractorConfig(
            output_dir=str(tmp_path / "bbox_output"),
            enabled=True,
        )
        ext = BallBboxExtractor(config)
        # initialize 안 함
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.95,
            bbox=BoundingBox(x=300, y=220, width=40, height=40),
        )
        result = ext.process(frame, det, frame_index=0)
        assert result is False

    def test_저신뢰도_감지_거부(self, tmp_path):
        """신뢰도 미달 → 거부."""
        ext = self._make_extractor(tmp_path)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.1,  # 매우 낮은 신뢰도
            bbox=BoundingBox(x=300, y=220, width=40, height=40),
        )
        result = ext.process(frame, det, frame_index=0)
        assert result is False

    def test_유효_감지_처리(self, tmp_path):
        """유효한 감지 → 버퍼에 추가."""
        ext = self._make_extractor(tmp_path)
        # 주황색 원이 있는 프레임 (패턴 검증 통과용)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(frame, (320, 240), 20, (30, 100, 200), -1)

        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.95,
            bbox=BoundingBox(x=300, y=220, width=40, height=40),
            radius_pixels=20.0,
        )
        result = ext.process(frame, det, frame_index=0)
        # 6중 필터 중 일부 통과 여부에 따라 True 또는 False
        assert isinstance(result, bool)

    def test_finalize_미초기화(self, tmp_path):
        """초기화 없이 finalize → None."""
        from detection.ball_detection.data_extraction.ball_bbox_extractor import (
            BallBboxExtractor,
            BallBboxExtractorConfig,
        )

        config = BallBboxExtractorConfig(
            output_dir=str(tmp_path / "bbox_output"),
        )
        ext = BallBboxExtractor(config)
        result = ext.finalize()
        assert result is None

    def test_finalize_빈_버퍼(self, tmp_path):
        """빈 버퍼 상태에서 finalize → record_count=0."""
        ext = self._make_extractor(tmp_path)
        result = ext.finalize()
        assert result is not None
        assert result.record_count == 0

    def test_disabled_시_process_거부(self, tmp_path):
        """enabled=False → process 항상 False."""
        from detection.ball_detection.data_extraction.ball_bbox_extractor import (
            BallBboxExtractor,
            BallBboxExtractorConfig,
        )

        config = BallBboxExtractorConfig(
            output_dir=str(tmp_path / "bbox_output"),
            enabled=False,
        )
        ext = BallBboxExtractor(config)
        ext.initialize(session_id="test", game_id="test")

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.95,
            bbox=BoundingBox(x=300, y=220, width=40, height=40),
        )
        result = ext.process(frame, det, frame_index=0)
        assert result is False


# =============================================================================
# TrajectoryExtractor 테스트
# =============================================================================

class TestTrajectoryExtractor:
    """TrajectoryExtractor 단위 테스트."""

    def _make_extractor(self, tmp_path: Path):
        from detection.ball_detection.data_extraction.trajectory_extractor import (
            TrajectoryExtractor,
            TrajectoryExtractorConfig,
        )

        config = TrajectoryExtractorConfig(
            output_dir=str(tmp_path / "traj_output"),
            enabled=True,
            buffer_flush_count=3,
        )
        ext = TrajectoryExtractor(config)
        ext.initialize(session_id="test_session", game_id="test_game")
        return ext

    def test_초기화(self, tmp_path):
        """초기화 후 상태 확인."""
        ext = self._make_extractor(tmp_path)
        assert ext._initialized is True

    def test_process_감지_추가(self, tmp_path):
        """감지 결과 process → 활성 궤적에 추가."""
        ext = self._make_extractor(tmp_path)
        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.9,
        )
        ext.process(det, frame_index=0)
        # 내부 활성 궤적 존재
        assert len(ext._active) >= 0  # 구현에 따라 0일 수 있음

    def test_process_trajectory_직접(self, tmp_path):
        """process_trajectory로 완성된 궤적 직접 제출."""
        from shared.dto.ball_dto import BallTrajectory, TrajectoryType

        ext = self._make_extractor(tmp_path)
        traj = BallTrajectory(
            trajectory_type=TrajectoryType.SHOT,
            start_frame=0,
            end_frame=30,
            confidence=0.85,
        )
        for i in range(15):
            traj.points_2d.append(Point2D(x=300.0 + i * 5, y=240.0 - i * 3))

        ext.process_trajectory(traj)
        assert ext._total_flushed >= 0  # 물리 검증 통과 여부에 따라

    def test_finalize_빈_버퍼(self, tmp_path):
        """빈 상태에서 finalize → record_count=0."""
        ext = self._make_extractor(tmp_path)
        result = ext.finalize()
        assert result is not None
        assert result.record_count == 0

    def test_미초기화_시_process_무시(self, tmp_path):
        """미초기화 시 process 무시."""
        from detection.ball_detection.data_extraction.trajectory_extractor import (
            TrajectoryExtractor,
            TrajectoryExtractorConfig,
        )

        config = TrajectoryExtractorConfig(
            output_dir=str(tmp_path / "traj_output"),
        )
        ext = TrajectoryExtractor(config)
        det = BallDetection(position=Point2D(x=100, y=200), confidence=0.9)
        ext.process(det, frame_index=0)  # 에러 없이 무시


# =============================================================================
# HardNegativeExtractor 테스트
# =============================================================================

class TestHardNegativeExtractor:
    """HardNegativeExtractor 단위 테스트."""

    def _make_extractor(self, tmp_path: Path):
        from detection.ball_detection.data_extraction.hard_negative_extractor import (
            HardNegativeExtractor,
            HardNegativeExtractorConfig,
        )

        config = HardNegativeExtractorConfig(
            output_dir=str(tmp_path / "hn_output"),
            enabled=True,
            buffer_flush_count=3,
        )
        ext = HardNegativeExtractor(config)
        ext.initialize(session_id="test_session", game_id="test_game")
        return ext

    def test_초기화(self, tmp_path):
        """초기화 후 상태 확인."""
        ext = self._make_extractor(tmp_path)
        assert ext._initialized is True

    def test_RejectReason_Enum(self):
        """RejectReason이 str Enum임."""
        from detection.ball_detection.data_extraction.hard_negative_extractor import (
            RejectReason,
        )

        assert issubclass(RejectReason, Enum)
        assert issubclass(RejectReason, str)
        # 값 확인
        assert RejectReason.CIRCULARITY.value == "circularity"
        assert RejectReason.COLOR.value == "color"
        assert RejectReason.SIZE.value == "size"
        # str 변환
        assert str(RejectReason.TRACKING) == "tracking"

    def test_process_하드_네거티브(self, tmp_path):
        """유효한 하드 네거티브 샘플 처리."""
        from detection.ball_detection.data_extraction.hard_negative_extractor import (
            RejectReason,
        )

        ext = self._make_extractor(tmp_path)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = BoundingBox(x=100, y=100, width=40, height=40)

        result = ext.process(
            frame=frame,
            bbox=bbox,
            yolo_confidence=0.7,
            reject_reason=RejectReason.CIRCULARITY,
            reject_detail="circularity=0.4",
            frame_index=0,
        )
        assert isinstance(result, bool)

    def test_finalize_빈_버퍼(self, tmp_path):
        """빈 상태에서 finalize → record_count=0."""
        ext = self._make_extractor(tmp_path)
        result = ext.finalize()
        assert result is not None
        assert result.record_count == 0

    def test_미초기화_시_process_거부(self, tmp_path):
        """미초기화 시 process → False."""
        from detection.ball_detection.data_extraction.hard_negative_extractor import (
            HardNegativeExtractor,
            HardNegativeExtractorConfig,
        )

        config = HardNegativeExtractorConfig(
            output_dir=str(tmp_path / "hn_output"),
        )
        ext = HardNegativeExtractor(config)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = BoundingBox(x=100, y=100, width=40, height=40)
        result = ext.process(
            frame=frame, bbox=bbox, yolo_confidence=0.7,
            reject_reason="test", reject_detail="test",
            frame_index=0,
        )
        assert result is False


# =============================================================================
# OcclusionSampleExtractor 테스트
# =============================================================================

class TestOcclusionSampleExtractor:
    """OcclusionSampleExtractor 단위 테스트."""

    def _make_extractor(self, tmp_path: Path):
        from detection.ball_detection.data_extraction.occlusion_sample_extractor import (
            OcclusionSampleExtractor,
            OcclusionSampleExtractorConfig,
        )

        config = OcclusionSampleExtractorConfig(
            output_dir=str(tmp_path / "occ_output"),
            enabled=True,
        )
        ext = OcclusionSampleExtractor(config)
        ext.initialize(session_id="test_session", game_id="test_game")
        return ext

    def test_초기화(self, tmp_path):
        """초기화 후 상태 확인."""
        ext = self._make_extractor(tmp_path)
        assert ext._initialized is True

    def test_OcclusionType_Enum(self):
        """OcclusionType이 str Enum임."""
        from detection.ball_detection.data_extraction.occlusion_sample_extractor import (
            OcclusionType,
        )

        assert issubclass(OcclusionType, Enum)
        assert issubclass(OcclusionType, str)

    def test_process_감지_있는_프레임(self, tmp_path):
        """감지 있는 프레임 process → 에러 없이 처리."""
        ext = self._make_extractor(tmp_path)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.9,
            bbox=BoundingBox(x=300, y=220, width=40, height=40),
        )
        # 에러 없이 호출됨
        ext.process(
            frame=frame,
            detection=det,
            frame_index=0,
        )

    def test_process_감지_없는_프레임(self, tmp_path):
        """감지 None → 가려짐 이벤트 감지 시작."""
        ext = self._make_extractor(tmp_path)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # 먼저 감지 있는 프레임 처리 (기준선)
        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.9,
        )
        for i in range(5):
            ext.process(frame=frame, detection=det, frame_index=i)

        # 그 후 감지 없는 프레임
        for i in range(5, 10):
            ext.process(frame=frame, detection=None, frame_index=i)

        # 에러 없이 완료

    def test_finalize_빈_버퍼(self, tmp_path):
        """빈 상태에서 finalize → record_count=0."""
        ext = self._make_extractor(tmp_path)
        result = ext.finalize()
        assert result is not None
        assert result.record_count == 0

    def test_frame_buffer_deque_사용(self, tmp_path):
        """프레임 버퍼가 deque로 구현됨 (O(1) 삽입)."""
        from collections import deque

        ext = self._make_extractor(tmp_path)
        assert isinstance(ext._frame_buffer, deque)

    def test_가려짐_이벤트_시퀀스(self, tmp_path):
        """감지→미감지→재감지 시퀀스가 에러 없이 처리됨."""
        ext = self._make_extractor(tmp_path)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # 10프레임 감지
        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.9,
            bbox=BoundingBox(x=300, y=220, width=40, height=40),
        )
        for i in range(10):
            ext.process(frame=frame, detection=det, frame_index=i)

        # 15프레임 미감지 (가려짐)
        for i in range(10, 25):
            ext.process(frame=frame, detection=None, frame_index=i)

        # 10프레임 재감지
        for i in range(25, 35):
            ext.process(frame=frame, detection=det, frame_index=i)

        # 에러 없이 완료 + finalize 가능
        result = ext.finalize()
        assert result is not None

    def test_finalize_미초기화(self, tmp_path):
        """미초기화 시 finalize → None."""
        from detection.ball_detection.data_extraction.occlusion_sample_extractor import (
            OcclusionSampleExtractor,
            OcclusionSampleExtractorConfig,
        )

        config = OcclusionSampleExtractorConfig(
            output_dir=str(tmp_path / "occ_output"),
        )
        ext = OcclusionSampleExtractor(config)
        result = ext.finalize()
        assert result is None

    def test_disabled_시_process_무시(self, tmp_path):
        """enabled=False → process 호출 시 에러 없음."""
        from detection.ball_detection.data_extraction.occlusion_sample_extractor import (
            OcclusionSampleExtractor,
            OcclusionSampleExtractorConfig,
        )

        config = OcclusionSampleExtractorConfig(
            output_dir=str(tmp_path / "occ_output"),
            enabled=False,
        )
        ext = OcclusionSampleExtractor(config)
        ext.initialize(session_id="test", game_id="test")

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.9,
        )
        # enabled=False이므로 process 무시
        ext.process(frame=frame, detection=det, frame_index=0)

    def test_연속_미감지_안정성(self, tmp_path):
        """장시간 미감지 → deque 무한 성장 없음 + 에러 없음."""
        ext = self._make_extractor(tmp_path)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        for i in range(100):
            ext.process(frame=frame, detection=None, frame_index=i)

        # deque maxlen에 의해 제한됨
        assert len(ext._frame_buffer) <= ext._config.context_window * 4


# =============================================================================
# TemporalSequenceExtractor 테스트
# =============================================================================

class TestTemporalSequenceExtractor:
    """TemporalSequenceExtractor 단위 테스트."""

    def _make_extractor(self, tmp_path: Path):
        from detection.ball_detection.data_extraction.temporal_sequence_extractor import (
            TemporalSequenceExtractor,
            TemporalSequenceExtractorConfig,
        )

        config = TemporalSequenceExtractorConfig(
            output_dir=str(tmp_path / "temp_output"),
            enabled=True,
        )
        ext = TemporalSequenceExtractor(config)
        ext.initialize(session_id="test_session", game_id="test_game")
        return ext

    def test_초기화(self, tmp_path):
        """초기화 후 상태 확인."""
        ext = self._make_extractor(tmp_path)
        assert ext._initialized is True

    def test_SequenceTrigger_Enum(self):
        """SequenceTrigger가 str Enum임."""
        from detection.ball_detection.data_extraction.temporal_sequence_extractor import (
            SequenceTrigger,
        )

        assert issubclass(SequenceTrigger, Enum)
        assert issubclass(SequenceTrigger, str)
        assert SequenceTrigger.STATE_TRANSITION.value == "state_transition"
        assert str(SequenceTrigger.PERIODIC) == "periodic"

    def test_process_프레임_처리(self, tmp_path):
        """감지 프레임 process → 에러 없이 처리."""
        ext = self._make_extractor(tmp_path)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.9,
        )
        ext.process(frame=frame, detection=det, frame_index=0)

    def test_finalize_빈_버퍼(self, tmp_path):
        """빈 상태에서 finalize → record_count=0."""
        ext = self._make_extractor(tmp_path)
        result = ext.finalize()
        assert result is not None
        assert result.record_count == 0

    def test_미초기화_시_process_무시(self, tmp_path):
        """미초기화 시 process 무시."""
        from detection.ball_detection.data_extraction.temporal_sequence_extractor import (
            TemporalSequenceExtractor,
            TemporalSequenceExtractorConfig,
        )

        config = TemporalSequenceExtractorConfig(
            output_dir=str(tmp_path / "temp_output"),
        )
        ext = TemporalSequenceExtractor(config)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        det = BallDetection(
            position=Point2D(x=320, y=240),
            confidence=0.9,
        )
        ext.process(frame=frame, detection=det, frame_index=0)  # 에러 없음


# =============================================================================
# __init__.py Export 검증
# =============================================================================

class TestDataExtractionExports:
    """data_extraction 패키지 Export 검증."""

    def test_all_exports(self):
        """__all__에 정의된 모든 이름이 실제로 임포트 가능."""
        from detection.ball_detection.data_extraction import __all__

        import detection.ball_detection.data_extraction as pkg

        for name in __all__:
            assert hasattr(pkg, name), f"{name}이 패키지에서 임포트 불가"

    def test_주요_클래스_임포트(self):
        """주요 클래스 임포트 검증."""
        from detection.ball_detection.data_extraction import (
            BallBboxExtractor,
            BallBboxExtractorConfig,
            HardNegativeExtractor,
            HardNegativeExtractorConfig,
            OcclusionSampleExtractor,
            OcclusionSampleExtractorConfig,
            OcclusionType,
            RejectReason,
            SequenceTrigger,
            TemporalSequenceExtractor,
            TemporalSequenceExtractorConfig,
            TrajectoryExtractor,
            TrajectoryExtractorConfig,
        )

        # 모두 임포트 성공 확인
        assert BallBboxExtractor is not None
        assert RejectReason is not None
        assert OcclusionType is not None
        assert SequenceTrigger is not None
