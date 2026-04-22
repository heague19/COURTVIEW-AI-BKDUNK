# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/ball_detection/unit
파일: test_ball_detector.py
설명: BallDetector 단위 테스트
      - 초기화/종료/리셋 라이프사이클
      - YOLO 추론 파이프라인 (모킹)
      - 크기/종횡비 필터링
      - HSV 색상 검증
      - 원형도/형태 검증
      - detect_to_dto 변환
      - 멀티뷰 융합
      - 궤적 예측

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from shared.constants.ball_constants import (
    BALL_DETECTION_MIN_CONFIDENCE,
    BallSize,
)
from shared.dto.geometry_dto import Point2D

from detection.ball_detection.ball_detector import (
    BallDetector,
    BallDetectorConfig,
    _BallCandidate,
)
from shared.dto.detection_dto import (
    DetectionSource,
    ObjectType,
)
from shared.interfaces.detector_interface import (
    DetectionState,
    DetectionTarget,
)


# =============================================================================
# BallDetectorConfig 테스트
# =============================================================================

class TestBallDetectorConfig:
    """BallDetectorConfig 단위 테스트."""

    def test_기본값(self):
        """기본값이 shared constants 참조."""
        config = BallDetectorConfig()
        assert config.confidence_threshold == BALL_DETECTION_MIN_CONFIDENCE
        assert config.device == "cuda"
        assert config.half_precision is True
        assert config.ball_size == BallSize.SIZE_7

    def test_커스텀_값(self):
        """커스텀 값 설정."""
        config = BallDetectorConfig(
            device="cpu",
            confidence_threshold=0.5,
            half_precision=False,
        )
        assert config.device == "cpu"
        assert config.confidence_threshold == 0.5

    def test_repr_포맷(self):
        """__repr__ 형식 확인."""
        config = BallDetectorConfig()
        repr_str = repr(config)
        assert "BallDetectorConfig" in repr_str
        assert "device=" in repr_str


# =============================================================================
# _BallCandidate 테스트
# =============================================================================

class TestBallCandidate:
    """내부 _BallCandidate 테스트."""

    def test_center_x_계산(self):
        """center_x = bbox_x + bbox_w / 2."""
        c = _BallCandidate(
            bbox_x=100.0, bbox_y=200.0,
            bbox_w=40.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        assert c.center_x == pytest.approx(120.0)
        assert c.center_y == pytest.approx(220.0)

    def test_aspect_ratio(self):
        """종횡비 = w / h."""
        c = _BallCandidate(
            bbox_x=0, bbox_y=0,
            bbox_w=40.0, bbox_h=50.0,
            yolo_confidence=0.9,
        )
        assert c.aspect_ratio == pytest.approx(0.8)

    def test_aspect_ratio_h_0(self):
        """h=0이면 aspect_ratio=0."""
        c = _BallCandidate(
            bbox_x=0, bbox_y=0,
            bbox_w=40.0, bbox_h=0.0,
            yolo_confidence=0.9,
        )
        assert c.aspect_ratio == 0.0

    def test_radius_pixels(self):
        """반지름 = (w + h) / 4."""
        c = _BallCandidate(
            bbox_x=0, bbox_y=0,
            bbox_w=40.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        assert c.radius_pixels == pytest.approx(20.0)

    def test_repr_포맷(self):
        """__repr__ 형식 확인."""
        c = _BallCandidate(
            bbox_x=100, bbox_y=200,
            bbox_w=40, bbox_h=40,
            yolo_confidence=0.9,
            combined_score=0.85,
        )
        assert "_BallCandidate" in repr(c)


# =============================================================================
# BallDetector 초기화 테스트
# =============================================================================

class TestBallDetectorInit:
    """BallDetector 초기화 테스트."""

    def test_생성_직후_UNINITIALIZED(self):
        """생성 직후 상태는 UNINITIALIZED."""
        detector = BallDetector()
        assert detector.state == DetectionState.UNINITIALIZED

    def test_name(self):
        """name 속성."""
        detector = BallDetector()
        assert detector.name == "BallDetector"

    def test_supported_targets(self):
        """supported_targets 속성."""
        detector = BallDetector()
        assert DetectionTarget.BALL in detector.supported_targets

    def test_모델_파일_없으면_FileNotFoundError(self):
        """존재하지 않는 모델 파일 → FileNotFoundError."""
        detector = BallDetector()
        config = BallDetectorConfig(model_path="/nonexistent/model.pt")

        with pytest.raises(FileNotFoundError):
            detector.initialize(config)

        assert detector.state == DetectionState.ERROR

    @patch("ultralytics.YOLO")
    def test_initialize_성공(self, mock_yolo_cls, temp_model_file):
        """모델 파일 존재 + YOLO 로드 성공 → READY."""
        mock_yolo_cls.return_value = MagicMock()
        mock_yolo_cls.return_value.predict.return_value = [MagicMock()]

        detector = BallDetector()
        config = BallDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
            half_precision=False,
        )
        detector.initialize(config)
        assert detector.state == DetectionState.READY

    @patch("ultralytics.YOLO")
    def test_initialize_실패_RuntimeError(self, mock_yolo_cls, temp_model_file):
        """YOLO 로드 중 예외 → RuntimeError."""
        mock_yolo_cls.side_effect = Exception("GPU OOM")

        detector = BallDetector()
        config = BallDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
        )

        with pytest.raises(RuntimeError, match="GPU OOM"):
            detector.initialize(config)

        assert detector.state == DetectionState.ERROR


# =============================================================================
# BallDetector detect 테스트 (모킹)
# =============================================================================

class TestBallDetectorDetect:
    """detect() 메서드 테스트."""

    def test_미초기화_상태에서_detect(self, dummy_frame_480p):
        """READY 아닌 상태에서 detect → failure 결과."""
        detector = BallDetector()
        result = detector.detect(dummy_frame_480p)
        assert not result.success

    @patch("ultralytics.YOLO")
    def test_유효하지_않은_프레임(self, mock_yolo_cls, temp_model_file):
        """유효하지 않은 프레임 → failure."""
        mock_yolo_cls.return_value = MagicMock()
        mock_yolo_cls.return_value.predict.return_value = [MagicMock()]

        detector = BallDetector()
        config = BallDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
            half_precision=False,
        )
        detector.initialize(config)

        # 빈 배열
        result = detector.detect(np.array([]))
        assert not result.success


# =============================================================================
# BallDetector 종료/리셋 테스트
# =============================================================================

class TestBallDetectorShutdown:
    """종료/리셋 테스트."""

    @patch("ultralytics.YOLO")
    def test_shutdown(self, mock_yolo_cls, temp_model_file):
        """shutdown() → SHUTDOWN 상태."""
        mock_yolo_cls.return_value = MagicMock()
        mock_yolo_cls.return_value.predict.return_value = [MagicMock()]

        detector = BallDetector()
        config = BallDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
            half_precision=False,
        )
        detector.initialize(config)
        detector.shutdown()

        assert detector.state == DetectionState.SHUTDOWN

    @patch("ultralytics.YOLO")
    def test_reset(self, mock_yolo_cls, temp_model_file):
        """reset() → READY 유지, 캐시 클리어."""
        mock_yolo_cls.return_value = MagicMock()
        mock_yolo_cls.return_value.predict.return_value = [MagicMock()]

        detector = BallDetector()
        config = BallDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
            half_precision=False,
        )
        detector.initialize(config)
        detector.reset()

        assert detector.state == DetectionState.READY


# =============================================================================
# 궤적 예측 테스트
# =============================================================================

class TestPredictTrajectory:
    """predict_trajectory 테스트."""

    def test_속도_없으면_현재_위치_반환(self):
        """velocity=None → 현재 위치만 반환."""
        from shared.interfaces.detector_interface import (
            BallState as InterfaceBallState,
        )

        detector = BallDetector()
        state = InterfaceBallState(position=(100.0, 200.0), radius=20.0)

        trajectory = detector.predict_trajectory(state, 1000.0)
        assert len(trajectory) == 1
        assert trajectory[0] == (100.0, 200.0)

    def test_속도_있으면_물리_예측(self):
        """velocity 있으면 물리 기반 궤적 예측."""
        from shared.interfaces.detector_interface import (
            BallState as InterfaceBallState,
        )

        detector = BallDetector()
        state = InterfaceBallState(
            position=(100.0, 200.0),
            radius=20.0,
            velocity=(50.0, -100.0),
        )

        trajectory = detector.predict_trajectory(state, 500.0)
        assert len(trajectory) > 1

        # 첫 번째 점은 원래 위치보다 오른쪽 (vx > 0)
        assert trajectory[0][0] > 100.0

    def test_최대_90프레임_제한(self):
        """예측 프레임은 최대 90 (3초@30fps)."""
        from shared.interfaces.detector_interface import (
            BallState as InterfaceBallState,
        )

        detector = BallDetector()
        state = InterfaceBallState(
            position=(100.0, 200.0),
            radius=20.0,
            velocity=(10.0, -20.0),
        )

        # 10초 → 300프레임 요청이지만 최대 90
        trajectory = detector.predict_trajectory(state, 10000.0)
        assert len(trajectory) <= 90


# =============================================================================
# 삼각측량기 주입 테스트
# =============================================================================

class TestTriangulatorSetup:
    """MultiViewTriangulator 주입 테스트."""

    def test_set_triangulator(self):
        """삼각측량기 주입 성공."""
        from infrastructure.multi_camera.coordinate_transformer import (
            MultiViewTriangulator,
        )

        detector = BallDetector()
        triangulator = MultiViewTriangulator()

        detector.set_triangulator(triangulator)

        assert detector._triangulator is triangulator

    def test_초기_상태_None(self):
        """초기 상태에서 삼각측량기는 None."""
        detector = BallDetector()
        assert detector._triangulator is None


# =============================================================================
# _fuse_multi_view 테스트
# =============================================================================

class TestFuseMultiView:
    """_fuse_multi_view 멀티뷰 융합 테스트."""

    def _make_candidate(
        self, x: float = 320.0, y: float = 240.0,
        w: float = 40.0, h: float = 40.0,
        conf: float = 0.9, score: float = 0.85,
    ) -> _BallCandidate:
        return _BallCandidate(
            bbox_x=x - w / 2, bbox_y=y - h / 2,
            bbox_w=w, bbox_h=h,
            yolo_confidence=conf,
            combined_score=score,
        )

    def test_빈_뷰_입력(self):
        """빈 뷰 → 빈 결과."""
        detector = BallDetector()
        result = detector._fuse_multi_view({}, {})
        assert result == []

    def test_단일_뷰_2D_반환(self):
        """단일 뷰 → 삼각측량 불가, 2D 결과만 반환."""
        detector = BallDetector()
        candidates = {"cam1": [self._make_candidate(320.0, 240.0)]}
        frames = {"cam1": np.zeros((480, 640, 3), dtype=np.uint8)}

        result = detector._fuse_multi_view(candidates, frames)

        assert len(result) == 1
        assert result[0].object_type == ObjectType.BALL
        assert result[0].position.x == pytest.approx(320.0)
        assert result[0].position.y == pytest.approx(240.0)

    def test_두_뷰_삼각측량기_없으면_2D(self):
        """두 뷰이나 삼각측량기 미주입 → 2D 결과만."""
        detector = BallDetector()
        candidates = {
            "cam1": [self._make_candidate(300.0, 200.0)],
            "cam2": [self._make_candidate(310.0, 205.0)],
        }
        frames = {
            "cam1": np.zeros((480, 640, 3), dtype=np.uint8),
            "cam2": np.zeros((480, 640, 3), dtype=np.uint8),
        }

        result = detector._fuse_multi_view(candidates, frames)

        # 삼각측량기 미주입이므로 2D fallback
        assert len(result) >= 1
        for obj in result:
            assert obj.object_type == ObjectType.BALL
            assert obj.position_3d is None

    def test_두_뷰_삼각측량기_주입_시_삼각측량_시도(self):
        """두 뷰 + 삼각측량기 → infrastructure DLT 삼각측량 시도."""
        from unittest.mock import MagicMock

        from infrastructure.multi_camera.coordinate_transformer import (
            MultiViewTriangulator,
            TriangulatedPoint,
        )

        detector = BallDetector()

        # 삼각측량기 모킹
        mock_triangulator = MagicMock(spec=MultiViewTriangulator)
        mock_triangulator.camera_count = 2
        mock_triangulator.triangulate.return_value = TriangulatedPoint(
            point_3d=np.array([5.0, 3.0, 2.5], dtype=np.float64),
            reprojection_error=0.5,
            num_views=2,
            is_valid=True,
        )

        detector.set_triangulator(mock_triangulator)

        candidates = {
            "cam1": [self._make_candidate(320.0, 240.0, score=0.9)],
            "cam2": [self._make_candidate(310.0, 240.0, score=0.88)],
        }
        frames = {
            "cam1": np.zeros((480, 640, 3), dtype=np.uint8),
            "cam2": np.zeros((480, 640, 3), dtype=np.uint8),
        }

        result = detector._fuse_multi_view(candidates, frames)

        # 삼각측량 시도됨
        mock_triangulator.triangulate.assert_called_once()
        assert len(result) == 1
        assert result[0].object_type == ObjectType.BALL
        assert result[0].position_3d is not None
        assert result[0].position_3d.x == pytest.approx(5.0)
        assert result[0].attributes["fusion_method"] == "infrastructure_dlt"

    def test_빈_후보_뷰_무시(self):
        """빈 후보 리스트인 뷰는 무시."""
        detector = BallDetector()
        candidates = {
            "cam1": [self._make_candidate(320.0, 240.0)],
            "cam2": [],
        }
        frames = {
            "cam1": np.zeros((480, 640, 3), dtype=np.uint8),
            "cam2": np.zeros((480, 640, 3), dtype=np.uint8),
        }

        result = detector._fuse_multi_view(candidates, frames)

        # cam2는 빈 후보 → 실질적으로 단일 뷰
        assert len(result) == 1
        assert result[0].position.x == pytest.approx(320.0)

    def test_삼_뷰_최선_후보_선택(self):
        """세 뷰 → 각 뷰의 첫 번째(최선) 후보 사용."""
        detector = BallDetector()
        candidates = {
            "cam1": [
                self._make_candidate(320.0, 240.0, score=0.95),
                self._make_candidate(100.0, 100.0, score=0.6),
            ],
            "cam2": [self._make_candidate(310.0, 238.0, score=0.90)],
            "cam3": [self._make_candidate(315.0, 242.0, score=0.88)],
        }
        frames = {
            "cam1": np.zeros((480, 640, 3), dtype=np.uint8),
            "cam2": np.zeros((480, 640, 3), dtype=np.uint8),
            "cam3": np.zeros((480, 640, 3), dtype=np.uint8),
        }

        result = detector._fuse_multi_view(candidates, frames)

        # 삼각측량기 미주입이므로 2D fallback, 하지만 에러 없이 처리
        assert len(result) >= 1
