# -*- coding: utf-8 -*-
"""
player_detection/jersey_ocr.py 단위 테스트.
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.constants.player_constants import (
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
)
from detection.player_detection.models import (
    JerseyOCRConfig,
    _JerseyRegion,
    _PlayerCandidate,
)
from detection.player_detection.jersey_ocr import JerseyOCR


# =============================================================================
# 초기화 / 종료
# =============================================================================

class Test_JerseyOCR_초기화:

    def test_초기화_전_상태(self) -> None:
        ocr = JerseyOCR()
        assert ocr.is_initialized is False

    def test_초기화_후_상태(self) -> None:
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        assert ocr.is_initialized is True
        assert ocr.total_recognized == 0

    def test_종료(self) -> None:
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        ocr.shutdown()
        assert ocr.is_initialized is False


# =============================================================================
# 인식
# =============================================================================

class Test_JerseyOCR_인식:

    def test_초기화_전_인식_안전(self) -> None:
        ocr = JerseyOCR()
        c = _PlayerCandidate(
            bbox_x=100, bbox_y=100, bbox_w=80, bbox_h=200,
            yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
        )
        result = ocr.recognize(c, np.zeros((480, 640, 3), dtype=np.uint8))
        assert result.number is None

    def test_심판은_인식_제외(self) -> None:
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        c = _PlayerCandidate(
            bbox_x=100, bbox_y=100, bbox_w=80, bbox_h=200,
            yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_REFEREE,
        )
        result = ocr.recognize(c, np.zeros((480, 640, 3), dtype=np.uint8))
        assert result.number is None

    def test_작은_bbox_인식_실패(self) -> None:
        """너무 작은 bbox → ROI 추출 실패."""
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        c = _PlayerCandidate(
            bbox_x=0, bbox_y=0, bbox_w=10, bbox_h=10,
            yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
        )
        result = ocr.recognize(c, np.zeros((480, 640, 3), dtype=np.uint8))
        assert result.number is None

    def test_형태학적_분석_폴백(self) -> None:
        """YOLO 모델 또는 형태학적 분석으로 동작."""
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        # 충분히 큰 bbox
        c = _PlayerCandidate(
            bbox_x=100, bbox_y=50, bbox_w=150, bbox_h=350,
            yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_PLAYER,
        )
        # 결과는 None 또는 유효한 숫자 (형태학적 분석은 불확실)
        result = ocr.recognize(
            c, np.zeros((480, 640, 3), dtype=np.uint8),
        )
        assert isinstance(result, _JerseyRegion)


# =============================================================================
# 확정 등번호
# =============================================================================

class Test_JerseyOCR_확정:

    def test_확정_번호_조회_없음(self) -> None:
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        assert ocr.get_confirmed_number(1) is None

    def test_전체_확정_조회(self) -> None:
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        assert ocr.get_all_confirmed() == {}


# =============================================================================
# 이력 관리
# =============================================================================

class Test_JerseyOCR_이력:

    def test_트랙_삭제(self) -> None:
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        # 존재하지 않는 트랙 삭제 → 에러 없음
        ocr.remove_track(999)

    def test_리셋(self) -> None:
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        ocr.reset()
        assert ocr.total_recognized == 0
        assert ocr.total_confirmed == 0


# =============================================================================
# 유효성 검증
# =============================================================================

class Test_JerseyOCR_유효성:

    def test_유효한_등번호(self) -> None:
        num, conf = JerseyOCR._validate_number("23", [0.9, 0.8])
        assert num == 23
        assert conf == pytest.approx(0.85)

    def test_빈_문자열(self) -> None:
        num, conf = JerseyOCR._validate_number("", [])
        assert num is None

    def test_범위_초과(self) -> None:
        num, conf = JerseyOCR._validate_number("100", [0.9, 0.9, 0.9])
        assert num is None

    def test_문자_포함(self) -> None:
        num, conf = JerseyOCR._validate_number("2A", [0.9, 0.9])
        assert num is None


# =============================================================================
# repr
# =============================================================================

class Test_JerseyOCR_repr:

    def test_repr(self) -> None:
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        r = repr(ocr)
        assert "JerseyOCR" in r
        assert "YOLO" in r or "morphological" in r
