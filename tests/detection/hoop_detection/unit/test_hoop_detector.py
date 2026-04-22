# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/hoop_detection/unit
파일: test_hoop_detector.py
설명: HoopDetector 단위 테스트
      - ScoringType 열거형
      - HoopDetectorConfig 설정 클래스
      - _HoopCandidate 내부 데이터 클래스
      - HoopDetector 초기화/종료/리셋 라이프사이클
      - detect 파이프라인 (YOLO 모킹)
      - 캐싱 로직 (정적 객체 최적화)
      - detect_score 궤적 기반 득점 판정
      - 멀티뷰 융합

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from shared.constants.hoop_constants import (
    HOOP_BACKBOARD_ASPECT_RATIO_MAX,
    HOOP_BACKBOARD_ASPECT_RATIO_MIN,
    HOOP_CLASS_ID_BACKBOARD,
    HOOP_CLASS_ID_RIM,
    HOOP_DETECTION_CONFIDENCE_THRESHOLD,
    HOOP_DETECTION_FREQUENCY_FRAMES,
    HOOP_SCORING_MIN_TRAJECTORY_POINTS,
)
from shared.interfaces.detector_interface import (
    DetectionState,
    DetectionTarget,
)

from detection.hoop_detection.hoop_detector import (
    HoopDetector,
    HoopDetectorConfig,
    ScoringType,
    _HoopCandidate,
)


# =============================================================================
# ScoringType 열거형 테스트
# =============================================================================

class TestScoringType:
    """ScoringType 열거형 단위 테스트."""

    def test_값_정의(self):
        """4개 득점 유형이 정의되어 있어야 한다."""
        assert ScoringType.SWISH.value == "swish"
        assert ScoringType.RIM_IN.value == "rim_in"
        assert ScoringType.RIM_OUT.value == "rim_out"
        assert ScoringType.UNKNOWN.value == "unknown"

    def test_is_score_스위시(self):
        """스위시는 득점."""
        assert ScoringType.SWISH.is_score is True

    def test_is_score_림인(self):
        """림인은 득점."""
        assert ScoringType.RIM_IN.is_score is True

    def test_is_score_림아웃(self):
        """림아웃은 미득점."""
        assert ScoringType.RIM_OUT.is_score is False

    def test_is_score_미판별(self):
        """미판별은 미득점."""
        assert ScoringType.UNKNOWN.is_score is False

    def test_korean_name_스위시(self):
        """한글명 '스위시'."""
        assert ScoringType.SWISH.korean_name == "스위시"

    def test_korean_name_림인(self):
        """한글명 '림인'."""
        assert ScoringType.RIM_IN.korean_name == "림인"

    def test_korean_name_림아웃(self):
        """한글명 '림아웃'."""
        assert ScoringType.RIM_OUT.korean_name == "림아웃"

    def test_korean_name_미판별(self):
        """한글명 '미판별'."""
        assert ScoringType.UNKNOWN.korean_name == "미판별"

    def test_unique_값(self):
        """모든 값이 고유해야 한다."""
        values = [e.value for e in ScoringType]
        assert len(values) == len(set(values))

    def test_멤버_수(self):
        """정확히 4개 멤버."""
        assert len(ScoringType) == 4


# =============================================================================
# HoopDetectorConfig 테스트
# =============================================================================

class TestHoopDetectorConfig:
    """HoopDetectorConfig 단위 테스트."""

    def test_기본값_상수_참조(self):
        """기본값이 shared constants를 참조해야 한다."""
        config = HoopDetectorConfig()
        assert config.confidence_threshold == HOOP_DETECTION_CONFIDENCE_THRESHOLD
        assert config.detection_frequency == HOOP_DETECTION_FREQUENCY_FRAMES
        assert config.backboard_aspect_min == HOOP_BACKBOARD_ASPECT_RATIO_MIN
        assert config.backboard_aspect_max == HOOP_BACKBOARD_ASPECT_RATIO_MAX

    def test_기본_장치(self):
        """기본 장치는 cuda."""
        config = HoopDetectorConfig()
        assert config.device == "cuda"
        assert config.half_precision is True

    def test_기본_모델_경로(self):
        """기본 모델 경로가 COURTVIEW_hoop.pt."""
        config = HoopDetectorConfig()
        assert "COURTVIEW_hoop.pt" in config.model_path

    def test_커스텀_값(self):
        """커스텀 값 설정."""
        config = HoopDetectorConfig(
            device="cpu",
            confidence_threshold=0.5,
            detection_frequency=5,
        )
        assert config.device == "cpu"
        assert config.confidence_threshold == 0.5
        assert config.detection_frequency == 5

    def test_멀티뷰_기본_비활성(self):
        """멀티뷰는 기본 비활성."""
        config = HoopDetectorConfig()
        assert config.enable_multi_view is False
        assert config.min_triangulation_views == 2

    def test_hough_기본_활성(self):
        """Hough Circle 보조는 기본 활성."""
        config = HoopDetectorConfig()
        assert config.enable_hough_fallback is True

    def test_색상_검증_기본_활성(self):
        """색상 검증은 기본 활성."""
        config = HoopDetectorConfig()
        assert config.enable_color_validation is True

    def test_repr_포맷(self):
        """__repr__ 형식 확인."""
        config = HoopDetectorConfig()
        repr_str = repr(config)
        assert "HoopDetectorConfig" in repr_str
        assert "device=" in repr_str
        assert "fp16=" in repr_str

    def test_slots_적용(self):
        """slots=True가 적용되어 __dict__ 없어야 한다."""
        config = HoopDetectorConfig()
        assert not hasattr(config, "__dict__")


# =============================================================================
# _HoopCandidate 테스트
# =============================================================================

class TestHoopCandidate:
    """내부 _HoopCandidate 테스트."""

    def test_center_좌표(self):
        """center_x, center_y 계산."""
        c = _HoopCandidate(
            bbox_x=100.0, bbox_y=200.0,
            bbox_w=60.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        assert c.center_x == pytest.approx(130.0)
        assert c.center_y == pytest.approx(220.0)

    def test_aspect_ratio(self):
        """종횡비 = w / h."""
        c = _HoopCandidate(
            bbox_x=0, bbox_y=0,
            bbox_w=60.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        assert c.aspect_ratio == pytest.approx(1.5)

    def test_aspect_ratio_h_0(self):
        """h=0이면 aspect_ratio=0."""
        c = _HoopCandidate(
            bbox_x=0, bbox_y=0,
            bbox_w=60.0, bbox_h=0.0,
            yolo_confidence=0.9,
        )
        assert c.aspect_ratio == 0.0

    def test_area(self):
        """면적 = w * h."""
        c = _HoopCandidate(
            bbox_x=0, bbox_y=0,
            bbox_w=60.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        assert c.area == pytest.approx(2400.0)

    def test_area_음수_방지(self):
        """음수 크기 → area = 0."""
        c = _HoopCandidate(
            bbox_x=0, bbox_y=0,
            bbox_w=-10.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        assert c.area == 0.0

    def test_is_rim_기본(self):
        """기본 class_id는 RIM."""
        c = _HoopCandidate(
            bbox_x=0, bbox_y=0,
            bbox_w=60.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        assert c.is_rim is True
        assert c.is_backboard is False

    def test_is_backboard(self):
        """class_id=BACKBOARD."""
        c = _HoopCandidate(
            bbox_x=0, bbox_y=0,
            bbox_w=100.0, bbox_h=50.0,
            yolo_confidence=0.85,
            class_id=HOOP_CLASS_ID_BACKBOARD,
        )
        assert c.is_rim is False
        assert c.is_backboard is True

    def test_to_xyxy(self):
        """xywh → xyxy 변환."""
        c = _HoopCandidate(
            bbox_x=100.0, bbox_y=200.0,
            bbox_w=60.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        x1, y1, x2, y2 = c.to_xyxy()
        assert x1 == pytest.approx(100.0)
        assert y1 == pytest.approx(200.0)
        assert x2 == pytest.approx(160.0)
        assert y2 == pytest.approx(240.0)

    def test_repr_림(self):
        """림 후보 repr에 'rim' 포함."""
        c = _HoopCandidate(
            bbox_x=100.0, bbox_y=200.0,
            bbox_w=60.0, bbox_h=40.0,
            yolo_confidence=0.9,
        )
        assert "rim" in repr(c)

    def test_repr_백보드(self):
        """백보드 후보 repr에 'backboard' 포함."""
        c = _HoopCandidate(
            bbox_x=100.0, bbox_y=200.0,
            bbox_w=100.0, bbox_h=50.0,
            yolo_confidence=0.85,
            class_id=HOOP_CLASS_ID_BACKBOARD,
        )
        assert "backboard" in repr(c)

    def test_slots_적용(self):
        """slots=True 적용."""
        c = _HoopCandidate(
            bbox_x=0, bbox_y=0, bbox_w=10, bbox_h=10,
            yolo_confidence=0.9,
        )
        assert not hasattr(c, "__dict__")


# =============================================================================
# HoopDetector 인스턴스 생성 테스트
# =============================================================================

class TestHoopDetectorInit:
    """HoopDetector 초기화 테스트."""

    def test_인스턴스_생성(self):
        """생성 후 UNINITIALIZED 상태."""
        det = HoopDetector()
        assert det.state == DetectionState.UNINITIALIZED
        assert det.name == "HoopDetector"

    def test_지원_타겟(self):
        """지원하는 감지 대상은 HOOP."""
        det = HoopDetector()
        assert DetectionTarget.HOOP in det.supported_targets

    def test_버전(self):
        """버전이 문자열."""
        det = HoopDetector()
        assert isinstance(det.version, str)
        assert det.version == "1.0.0"

    def test_메트릭_초기값(self):
        """메트릭 초기값은 빈 DetectorMetrics."""
        det = HoopDetector()
        assert det.metrics is not None

    def test_캐시_초기_비어있음(self):
        """초기에는 캐시된 골대 없음."""
        det = HoopDetector()
        assert det.get_cached_hoops() == []

    @patch("ultralytics.YOLO")
    def test_initialize_모델_로드(self, mock_yolo_cls, temp_model_file):
        """모델 파일이 존재하면 READY 상태로 전이."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [MagicMock(boxes=None)]
        mock_yolo_cls.return_value = mock_model

        det = HoopDetector()
        config = HoopDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
            half_precision=False,
        )
        det.initialize(config)

        assert det.state == DetectionState.READY

    def test_initialize_파일_미존재(self):
        """모델 파일이 없으면 FileNotFoundError."""
        det = HoopDetector()
        config = HoopDetectorConfig(
            model_path="/nonexistent/model.pt",
        )
        with pytest.raises(FileNotFoundError):
            det.initialize(config)
        assert det.state == DetectionState.ERROR

    @patch("ultralytics.YOLO")
    def test_shutdown(self, mock_yolo_cls, temp_model_file):
        """shutdown 후 SHUTDOWN 상태."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [MagicMock(boxes=None)]
        mock_yolo_cls.return_value = mock_model

        det = HoopDetector()
        config = HoopDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
            half_precision=False,
        )
        det.initialize(config)
        det.shutdown()

        assert det.state == DetectionState.SHUTDOWN
        assert det.get_cached_hoops() == []

    @patch("ultralytics.YOLO")
    def test_reset(self, mock_yolo_cls, temp_model_file):
        """reset 후 캐시 비우고 READY 유지."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [MagicMock(boxes=None)]
        mock_yolo_cls.return_value = mock_model

        det = HoopDetector()
        config = HoopDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
            half_precision=False,
        )
        det.initialize(config)
        det.reset()

        assert det.state == DetectionState.READY
        assert det.get_cached_hoops() == []

    def test_repr(self):
        """__repr__ 형식 확인."""
        det = HoopDetector()
        repr_str = repr(det)
        assert "HoopDetector" in repr_str
        assert "state=" in repr_str


# =============================================================================
# detect 파이프라인 테스트
# =============================================================================

class TestHoopDetectorDetect:
    """HoopDetector.detect() 단위 테스트."""

    def test_미초기화_시_실패(self, dummy_frame_480p):
        """초기화 안 된 상태에서 detect → failure."""
        det = HoopDetector()
        result = det.detect(dummy_frame_480p, frame_index=0)
        assert result.success is False

    @patch("ultralytics.YOLO")
    def test_유효_프레임_감지(self, mock_yolo_cls, temp_model_file, mock_yolo_with_rim):
        """유효한 프레임에서 감지 → success."""
        mock_yolo_cls.return_value = MagicMock()
        mock_yolo_cls.return_value.predict.return_value = [MagicMock(boxes=None)]

        det = HoopDetector()
        config = HoopDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
            half_precision=False,
        )
        det.initialize(config)

        # 이제 실제 predict 결과를 교체
        det._model = mock_yolo_with_rim

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = det.detect(frame, frame_index=0)

        assert result.success is True

    def test_빈_프레임_유효성(self):
        """None 프레임 → validate 실패."""
        det = HoopDetector()
        # validate_frame은 None에 대해 False 반환
        assert det.validate_frame(None) is False

    def test_2D_프레임_유효성(self):
        """2차원 프레임(그레이스케일) → validate 실패."""
        det = HoopDetector()
        gray = np.zeros((480, 640), dtype=np.uint8)
        assert det.validate_frame(gray) is False


# =============================================================================
# 캐싱 로직 테스트
# =============================================================================

class TestHoopDetectorCaching:
    """정적 객체 캐싱 로직 테스트."""

    @patch("ultralytics.YOLO")
    def test_캐시_주기(self, mock_yolo_cls, temp_model_file):
        """detection_frequency 간격 확인."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [MagicMock(boxes=None)]
        mock_yolo_cls.return_value = mock_model

        det = HoopDetector()
        config = HoopDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
            half_precision=False,
            detection_frequency=10,
        )
        det.initialize(config)

        # _should_run_full_detection: 첫 호출은 항상 True
        assert det._should_run_full_detection(0) is True

        # 캐시 세팅 (첫 감지 이후 상태 시뮬레이션)
        det._last_full_detection_frame = 0
        det._cached_candidates = [MagicMock()]

        # frame_index=5 → 10 미만 → False (캐시 히트)
        assert det._should_run_full_detection(5) is False

        # frame_index=10 → 10 이상 → True (재감지)
        assert det._should_run_full_detection(10) is True

    @patch("ultralytics.YOLO")
    def test_캐시_비어있으면_감지(self, mock_yolo_cls, temp_model_file):
        """캐시가 비어있으면 무조건 감지."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [MagicMock(boxes=None)]
        mock_yolo_cls.return_value = mock_model

        det = HoopDetector()
        config = HoopDetectorConfig(
            model_path=str(temp_model_file),
            device="cpu",
            half_precision=False,
        )
        det.initialize(config)
        det._last_full_detection_frame = 0
        det._cached_candidates = []

        assert det._should_run_full_detection(1) is True


# =============================================================================
# detect_score 궤적 기반 테스트
# =============================================================================

class TestDetectScore:
    """detect_score() 궤적 기반 득점 판정 테스트."""

    def _make_detector(self):
        det = HoopDetector()
        det._config = HoopDetectorConfig()
        return det

    def _make_hoop(self, cx=320.0, cy=130.0, r=25.0):
        from shared.interfaces.detector_interface import (
            BoundingBox as IBBox,
            HoopDetection,
        )
        return HoopDetection(
            bounding_box=IBBox(x=cx - r, y=cy - r, width=r * 2, height=r * 2),
            rim_center=(cx, cy),
            rim_radius=r,
            hoop_side="left",
        )

    def test_궤적_부족_시_미득점(self):
        """최소 궤적 포인트 미만 → (False, 0.0)."""
        det = self._make_detector()
        hoop = self._make_hoop()
        # 최소 포인트보다 적은 궤적
        short_traj = [(320.0, 100.0)] * (HOOP_SCORING_MIN_TRAJECTORY_POINTS - 1)
        is_score, conf = det.detect_score(short_traj, hoop)
        assert is_score is False
        assert conf == 0.0

    def test_림_통과_궤적_득점(self):
        """공이 림 위→아래로 통과하는 궤적 → 득점."""
        det = self._make_detector()
        hoop = self._make_hoop(cx=320.0, cy=130.0, r=25.0)

        # 공이 위에서 림 중심을 통과하여 아래로 빠지는 궤적
        trajectory = [
            (320.0, 80.0),   # 림 위
            (320.0, 100.0),  # 림 위 접근
            (320.0, 120.0),  # 통과 영역 진입
            (320.0, 130.0),  # 림 중심
            (320.0, 140.0),  # 통과 영역 통과
            (320.0, 160.0),  # 림 아래 (exited_below)
            (320.0, 180.0),  # 더 아래
        ]
        is_score, conf = det.detect_score(trajectory, hoop)
        assert is_score is True
        assert conf > 0.0

    def test_림_못_통과_궤적(self):
        """공이 림에 닿지 않는 궤적 → 미득점."""
        det = self._make_detector()
        hoop = self._make_hoop(cx=320.0, cy=130.0, r=25.0)

        # 림 영역에 전혀 진입하지 않는 궤적
        trajectory = [
            (100.0, 80.0),
            (100.0, 100.0),
            (100.0, 130.0),
            (100.0, 160.0),
            (100.0, 180.0),
            (100.0, 200.0),
        ]
        is_score, conf = det.detect_score(trajectory, hoop)
        assert is_score is False

    def test_빈_궤적(self):
        """빈 궤적 → 미득점."""
        det = self._make_detector()
        hoop = self._make_hoop()
        is_score, conf = det.detect_score([], hoop)
        assert is_score is False
        assert conf == 0.0


# =============================================================================
# __all__ / __version__ Export 테스트
# =============================================================================

class TestExport:
    """모듈 export 정합성 테스트."""

    def test_hoop_detector_all(self):
        """hoop_detector.py __all__ 정의."""
        from detection.hoop_detection import hoop_detector
        assert "HoopDetector" in hoop_detector.__all__

    def test_hoop_detector_version(self):
        """hoop_detector.py __version__."""
        from detection.hoop_detection import hoop_detector
        assert hoop_detector.__version__ == "1.0.0"

    def test_init_all_포함_HoopDetector(self):
        """__init__.py __all__에 HoopDetector 포함."""
        from detection import hoop_detection
        assert "HoopDetector" in hoop_detection.__all__

    def test_init_all_포함_HoopDetectorConfig(self):
        """__init__.py __all__에 HoopDetectorConfig 포함."""
        from detection import hoop_detection
        assert "HoopDetectorConfig" in hoop_detection.__all__

    def test_init_all_포함_ScoringType(self):
        """__init__.py __all__에 ScoringType 포함."""
        from detection import hoop_detection
        assert "ScoringType" in hoop_detection.__all__

    def test_init_version(self):
        """__init__.py __version__."""
        from detection import hoop_detection
        assert hoop_detection.__version__ == "1.0.0"
