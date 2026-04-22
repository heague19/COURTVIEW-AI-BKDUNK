# -*- coding: utf-8 -*-
"""
tests/detection/player_detection/unit/test_jersey_ocr_batch.py
JerseyOCR.recognize_batch_multi_frame 단위 테스트.

검증 대상 (모델 없이 구조적 동작):
  - 빈 입력
  - 미초기화 상태
  - 확정된 번호 스킵 (YOLO 호출 회피)
  - 결과 길이 == 입력 길이
  - 결과 순서 보존
  - 카메라 섞인 입력 처리
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from detection.player_detection.jersey_ocr import JerseyOCR, _JerseyRegion
from detection.player_detection.models import JerseyOCRConfig, _PlayerCandidate
from shared.constants.player_constants import PLAYER_CLASS_ID_PLAYER


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def frame_1080p() -> np.ndarray:
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


@pytest.fixture
def candidate_factory():
    def make(
        bbox_x: float = 100.0,
        bbox_y: float = 200.0,
        bbox_w: float = 80.0,
        bbox_h: float = 200.0,
        cam_id: str = "cam_0",
        class_id: int = PLAYER_CLASS_ID_PLAYER,
    ) -> _PlayerCandidate:
        return _PlayerCandidate(
            bbox_x=bbox_x,
            bbox_y=bbox_y,
            bbox_w=bbox_w,
            bbox_h=bbox_h,
            yolo_confidence=0.85,
            class_id=class_id,
            combined_score=0.82,
            camera_id=cam_id,
            frame_index=0,
        )
    return make


@pytest.fixture
def uninit_ocr() -> JerseyOCR:
    """미초기화 상태."""
    return JerseyOCR()


@pytest.fixture
def minimal_ocr() -> JerseyOCR:
    """YOLO 모델 없이 초기화 상태만 진입."""
    ocr = JerseyOCR()
    ocr._initialized = True
    ocr._config = JerseyOCRConfig()
    ocr._digit_model = None  # YOLO 미로드 → 형태학적 폴백
    ocr._cls_model = None
    return ocr


# =============================================================================
# 기본 동작
# =============================================================================

class TestRecognizeBatchMultiFrameBasics:
    def test_empty_input_returns_empty(self, minimal_ocr):
        result = minimal_ocr.recognize_batch_multi_frame([])
        assert result == []

    def test_uninitialized_returns_empty_regions(self, uninit_ocr, candidate_factory, frame_1080p):
        """미초기화 상태면 n개의 빈 _JerseyRegion 반환."""
        pairs = [(candidate_factory(), frame_1080p)] * 3
        result = uninit_ocr.recognize_batch_multi_frame(pairs)
        assert len(result) == 3
        assert all(isinstance(r, _JerseyRegion) for r in result)

    def test_result_length_matches_input(self, minimal_ocr, candidate_factory, frame_1080p):
        pairs = [(candidate_factory(), frame_1080p) for _ in range(5)]
        result = minimal_ocr.recognize_batch_multi_frame(pairs)
        assert len(result) == 5

    def test_order_preserved(self, minimal_ocr, candidate_factory, frame_1080p):
        """서로 다른 bbox_x로 식별 → 결과 순서 입력과 일치."""
        pairs = [
            (candidate_factory(bbox_x=100.0), frame_1080p),
            (candidate_factory(bbox_x=500.0), frame_1080p),
            (candidate_factory(bbox_x=900.0), frame_1080p),
        ]
        result = minimal_ocr.recognize_batch_multi_frame(pairs)
        assert len(result) == 3
        # 각 결과 region의 source_bbox_x가 입력 순서 유지
        assert result[0].source_bbox_x == pytest.approx(100.0)
        assert result[1].source_bbox_x == pytest.approx(500.0)
        assert result[2].source_bbox_x == pytest.approx(900.0)


# =============================================================================
# 확정된 번호 스킵 (최적화 경로)
# =============================================================================

class TestConfirmedNumberShortcut:
    def test_confirmed_skips_yolo_call(self, candidate_factory, frame_1080p):
        """_confirmed_numbers에 tid가 있으면 YOLO 모델 호출 없이 즉시 반환."""
        ocr = JerseyOCR()
        ocr._initialized = True
        ocr._config = JerseyOCRConfig()
        mock_model = MagicMock()
        ocr._digit_model = mock_model
        ocr._cls_model = None
        # tid=42 → 23번 확정
        ocr._confirmed_numbers = {42: 23}

        pairs = [(candidate_factory(), frame_1080p)]
        result = ocr.recognize_batch_multi_frame(pairs, track_ids=[42])

        assert len(result) == 1
        assert result[0].number == 23
        assert result[0].confidence == 1.0
        mock_model.predict.assert_not_called()  # YOLO 호출 건너뜀

    def test_mixed_confirmed_and_new(self, candidate_factory, frame_1080p):
        """일부는 확정, 일부는 신규 → 확정만 shortcut."""
        ocr = JerseyOCR()
        ocr._initialized = True
        ocr._config = JerseyOCRConfig()
        ocr._digit_model = None
        ocr._cls_model = None
        ocr._confirmed_numbers = {100: 7}

        pairs = [
            (candidate_factory(bbox_x=50.0), frame_1080p),   # 신규
            (candidate_factory(bbox_x=500.0), frame_1080p),  # 확정된 tid
        ]
        result = ocr.recognize_batch_multi_frame(pairs, track_ids=[None, 100])

        assert len(result) == 2
        # 확정 tid=100의 경우
        assert result[1].number == 7
        assert result[1].confidence == 1.0


# =============================================================================
# 비선수 클래스 처리
# =============================================================================

class TestNonPlayerSkipped:
    def test_non_player_class_not_recognized(self, minimal_ocr, candidate_factory, frame_1080p):
        """심판/코치 클래스는 인식 대상 아님."""
        non_player_cand = candidate_factory(class_id=2)  # referee
        pairs = [(non_player_cand, frame_1080p)]
        result = minimal_ocr.recognize_batch_multi_frame(pairs)
        assert len(result) == 1
        # 빈 region 반환
        assert result[0].number is None


# =============================================================================
# track_ids 매개변수
# =============================================================================

class TestTrackIds:
    def test_none_track_ids_default(self, minimal_ocr, candidate_factory, frame_1080p):
        """track_ids=None이면 내부에서 [None]*n 생성됨 → 에러 안 남."""
        pairs = [(candidate_factory(), frame_1080p) for _ in range(3)]
        result = minimal_ocr.recognize_batch_multi_frame(pairs, track_ids=None)
        assert len(result) == 3

    def test_track_ids_length_mismatch_shorter(
        self, minimal_ocr, candidate_factory, frame_1080p,
    ):
        """track_ids가 pairs보다 짧아도 안전 — 부족한 건 None 처리."""
        pairs = [(candidate_factory(), frame_1080p) for _ in range(3)]
        result = minimal_ocr.recognize_batch_multi_frame(pairs, track_ids=[1])
        assert len(result) == 3  # 결과는 입력 길이 유지


# =============================================================================
# 백워드 호환: recognize_batch (단일 프레임)
# =============================================================================

class TestRecognizeBatchBackwardCompat:
    def test_single_frame_batch_delegates(self, minimal_ocr, candidate_factory, frame_1080p):
        """recognize_batch는 내부에서 recognize_batch_multi_frame 호출."""
        candidates = [candidate_factory(bbox_x=i * 100.0) for i in range(3)]
        result = minimal_ocr.recognize_batch(candidates, frame_1080p)
        assert len(result) == 3
