# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: ocr_constants.py
설명: OCR (광학 문자 인식) 관련 상수 정의
      - 등번호 인식 파라미터 (농구 유니폼)
      - 텍스트 검출 및 인식 임계값
      - OCR 모델 및 전처리 설정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0

참조:
- CRNN (Convolutional Recurrent Neural Network): 시퀀스 문자 인식
- EAST/CRAFT: 텍스트 검출 알고리즘
- 농구 유니폼 등번호 특성 (FIBA/NBA/KBL 규정)
"""

from enum import Enum, unique
from typing import Final


# =============================================================================
# OCR 신뢰도 임계값
# =============================================================================

# OCR 최소 신뢰도 (0.0~1.0)
# - 이 값 미만의 결과는 무시
MIN_OCR_CONFIDENCE: Final[float] = 0.5

# OCR 높은 신뢰도 임계값
HIGH_OCR_CONFIDENCE: Final[float] = 0.8

# OCR 확정 신뢰도 임계값
CONFIRMED_OCR_CONFIDENCE: Final[float] = 0.9

# OCR 낮은 신뢰도 임계값 (후보 포함용)
LOW_OCR_CONFIDENCE: Final[float] = 0.3


# =============================================================================
# 등번호 범위 상수
# =============================================================================

# 등번호 최소값
JERSEY_NUMBER_MIN: Final[int] = 0

# 등번호 최대값
JERSEY_NUMBER_MAX: Final[int] = 99

# FIBA 규정 등번호 (0-9, 00 제외)
# - FIBA 규정: 4-15번 권장 (5명 선발 + 교체)
FIBA_JERSEY_NUMBERS: Final[tuple[int, ...]] = tuple(range(0, 100))

# NBA 등번호 규정 (00, 0-99)
NBA_JERSEY_NUMBERS: Final[tuple[int, ...]] = tuple(range(0, 100))

# KBL 등번호 규정 (0-99)
KBL_JERSEY_NUMBERS: Final[tuple[int, ...]] = tuple(range(0, 100))


# =============================================================================
# OCR 처리 간격 및 빈도
# =============================================================================

# OCR 수행 간격 (프레임)
# - 매 프레임 수행하면 성능 부담
OCR_FRAME_INTERVAL: Final[int] = 5

# OCR 최소 수행 간격 (프레임)
OCR_MIN_FRAME_INTERVAL: Final[int] = 1

# OCR 최대 수행 간격 (프레임)
OCR_MAX_FRAME_INTERVAL: Final[int] = 30

# 등번호 확정 최소 관측 횟수
MIN_OCR_OBSERVATIONS_FOR_CONFIRMATION: Final[int] = 3

# 등번호 확정 관측 일관성 비율
OCR_CONFIRMATION_CONSISTENCY_RATIO: Final[float] = 0.7


# =============================================================================
# 텍스트 검출 파라미터
# =============================================================================

# 텍스트 검출 최소 신뢰도
TEXT_DETECTION_MIN_CONFIDENCE: Final[float] = 0.5

# 텍스트 영역 최소 면적 (픽셀²)
TEXT_AREA_MIN: Final[int] = 100

# 텍스트 영역 최대 면적 (픽셀²)
TEXT_AREA_MAX: Final[int] = 50000

# 텍스트 영역 최소 높이 (픽셀)
TEXT_HEIGHT_MIN: Final[int] = 10

# 텍스트 영역 최소 너비 (픽셀)
TEXT_WIDTH_MIN: Final[int] = 5

# 텍스트 종횡비 최소값 (너비/높이)
TEXT_ASPECT_RATIO_MIN: Final[float] = 0.2

# 텍스트 종횡비 최대값 (너비/높이)
TEXT_ASPECT_RATIO_MAX: Final[float] = 5.0


# =============================================================================
# 등번호 영역 (ROI) 파라미터
# =============================================================================

# 등번호 ROI 상대 위치 (선수 바운딩 박스 대비)
# - 상의 앞/뒤 중앙에 등번호 위치

# 등번호 ROI 상단 오프셋 (바운딩 박스 높이 대비 비율)
JERSEY_ROI_TOP_OFFSET: Final[float] = 0.15

# 등번호 ROI 하단 오프셋 (바운딩 박스 높이 대비 비율)
JERSEY_ROI_BOTTOM_OFFSET: Final[float] = 0.55

# 등번호 ROI 좌측 오프셋 (바운딩 박스 너비 대비 비율)
JERSEY_ROI_LEFT_OFFSET: Final[float] = 0.2

# 등번호 ROI 우측 오프셋 (바운딩 박스 너비 대비 비율)
JERSEY_ROI_RIGHT_OFFSET: Final[float] = 0.8

# 등번호 영역 확장 비율
JERSEY_ROI_EXPANSION: Final[float] = 1.1


# =============================================================================
# 이미지 전처리 파라미터
# =============================================================================

# OCR 입력 이미지 최소 높이 (픽셀)
OCR_INPUT_MIN_HEIGHT: Final[int] = 32

# OCR 입력 이미지 최대 높이 (픽셀)
OCR_INPUT_MAX_HEIGHT: Final[int] = 128

# OCR 입력 이미지 표준 높이 (픽셀)
OCR_INPUT_STANDARD_HEIGHT: Final[int] = 64

# 그레이스케일 변환 가중치 (R, G, B) - ITU-R BT.601 표준
GRAYSCALE_WEIGHTS: Final[tuple[float, float, float]] = (0.299, 0.587, 0.114)

# 그레이스케일 가중치 합 검증 (ITU-R BT.601: R + G + B = 1.0)
_GRAYSCALE_WEIGHT_SUM: Final[float] = sum(GRAYSCALE_WEIGHTS)
assert abs(_GRAYSCALE_WEIGHT_SUM - 1.0) < 1e-9, (
    f"그레이스케일 가중치 합이 1.0이 아닙니다: {_GRAYSCALE_WEIGHT_SUM}"
)

# 이진화 임계값 (Otsu 사용 시 무시)
BINARIZATION_THRESHOLD: Final[int] = 128

# 적응형 이진화 블록 크기
ADAPTIVE_BINARIZATION_BLOCK_SIZE: Final[int] = 11

# 적응형 이진화 상수
ADAPTIVE_BINARIZATION_CONSTANT: Final[float] = 2.0


# =============================================================================
# 등번호 문자 특성
# =============================================================================

# 등번호 문자 집합 (숫자만)
JERSEY_CHARSET: Final[str] = "0123456789"

# 등번호 최대 자릿수
JERSEY_MAX_DIGITS: Final[int] = 2

# 등번호 최소 자릿수
JERSEY_MIN_DIGITS: Final[int] = 1

# 등번호 폰트 종횡비 범위 (높이/너비)
JERSEY_FONT_ASPECT_RATIO_MIN: Final[float] = 1.2
JERSEY_FONT_ASPECT_RATIO_MAX: Final[float] = 2.5

# 등번호 문자 간격 비율 (문자 너비 대비)
JERSEY_CHAR_SPACING_RATIO: Final[float] = 0.1


# =============================================================================
# 색상 기반 등번호 검출 파라미터
# =============================================================================

# 등번호-배경 대비 최소값
JERSEY_CONTRAST_MIN: Final[float] = 0.3

# 흰색 등번호 HSV 범위
WHITE_TEXT_HSV_LOWER: Final[tuple[int, int, int]] = (0, 0, 180)
WHITE_TEXT_HSV_UPPER: Final[tuple[int, int, int]] = (180, 50, 255)

# 검은색 등번호 HSV 범위
BLACK_TEXT_HSV_LOWER: Final[tuple[int, int, int]] = (0, 0, 0)
BLACK_TEXT_HSV_UPPER: Final[tuple[int, int, int]] = (180, 50, 80)

# 색상 대비 분석 커널 크기
COLOR_CONTRAST_KERNEL_SIZE: Final[int] = 5


# =============================================================================
# OCR 후처리 파라미터
# =============================================================================

# 등번호 유효성 검사 정규식
JERSEY_NUMBER_PATTERN: Final[str] = r"^[0-9]{1,2}$"

# 유사 문자 매핑 (OCR 오류 보정)
SIMILAR_CHAR_MAPPING: Final[dict[str, str]] = {
    "O": "0",
    "o": "0",
    "I": "1",
    "l": "1",
    "Z": "2",
    "z": "2",
    "S": "5",
    "s": "5",
    "B": "8",
    "G": "6",
    "g": "9",
    "q": "9",
}

# NMS (Non-Maximum Suppression) IoU 임계값
OCR_NMS_IOU_THRESHOLD: Final[float] = 0.5

# 동일 등번호 병합 거리 (픽셀)
SAME_NUMBER_MERGE_DISTANCE: Final[float] = 20.0


# =============================================================================
# 시간적 일관성 파라미터
# =============================================================================

# 등번호 이력 유지 프레임 수
JERSEY_HISTORY_MAX_FRAMES: Final[int] = 30

# 등번호 변경 감지 임계값 (연속 프레임)
JERSEY_CHANGE_THRESHOLD_FRAMES: Final[int] = 10

# 등번호 투표 윈도우 크기 (프레임)
JERSEY_VOTING_WINDOW: Final[int] = 15


# =============================================================================
# 배치 처리 파라미터
# =============================================================================

# OCR 배치 크기
OCR_BATCH_SIZE: Final[int] = 16

# OCR 최대 동시 처리 수
OCR_MAX_CONCURRENT: Final[int] = 8

# OCR 타임아웃 (밀리초)
OCR_TIMEOUT_MS: Final[int] = 500


# =============================================================================
# 모델별 파라미터
# =============================================================================

# CRNN 입력 크기 (높이, 너비)
CRNN_INPUT_SIZE: Final[tuple[int, int]] = (32, 100)

# CRNN 숨겨진 레이어 크기
CRNN_HIDDEN_SIZE: Final[int] = 256

# TrOCR 입력 크기 (높이, 너비)
TROCR_INPUT_SIZE: Final[tuple[int, int]] = (384, 384)


# =============================================================================
# OCR 모델 열거형
# =============================================================================

@unique
class OCRModel(Enum):
    """
    OCR 모델 열거형.

    지원되는 OCR 모델을 정의합니다.
    """

    # CRNN (Convolutional Recurrent Neural Network)
    CRNN = "crnn"

    # TrOCR (Transformer-based OCR)
    TROCR = "trocr"

    # EasyOCR
    EASY_OCR = "easy_ocr"

    # PaddleOCR
    PADDLE_OCR = "paddle_ocr"

    # Tesseract OCR
    TESSERACT = "tesseract"

    # 커스텀 모델 (등번호 특화)
    CUSTOM_JERSEY = "custom_jersey"

    @property
    def input_size(self) -> tuple[int, int]:
        """모델별 입력 크기 (높이, 너비)."""
        return _OCR_MODEL_INPUT_SIZE_MAP[self]

    @property
    def supports_batch(self) -> bool:
        """배치 처리 지원 여부."""
        return self in _OCR_MODEL_SUPPORTS_BATCH

    @property
    def is_transformer_based(self) -> bool:
        """트랜스포머 기반 여부."""
        return self == OCRModel.TROCR

    def to_korean(self) -> str:
        """한글 모델명 반환."""
        return _OCR_MODEL_KOREAN_MAP[self]


# -- OCRModel 캐시 (직접 할당) --

_OCR_MODEL_INPUT_SIZE_MAP: dict[OCRModel, tuple[int, int]] = {
    OCRModel.CRNN: CRNN_INPUT_SIZE,
    OCRModel.TROCR: TROCR_INPUT_SIZE,
    OCRModel.EASY_OCR: (64, 256),
    OCRModel.PADDLE_OCR: (48, 320),
    OCRModel.TESSERACT: (32, 128),
    OCRModel.CUSTOM_JERSEY: (64, 128),
}

_OCR_MODEL_KOREAN_MAP: dict[OCRModel, str] = {
    OCRModel.CRNN: "CRNN",
    OCRModel.TROCR: "TrOCR",
    OCRModel.EASY_OCR: "EasyOCR",
    OCRModel.PADDLE_OCR: "PaddleOCR",
    OCRModel.TESSERACT: "Tesseract",
    OCRModel.CUSTOM_JERSEY: "커스텀 등번호 모델",
}

_OCR_MODEL_SUPPORTS_BATCH: frozenset = frozenset({
    OCRModel.CRNN,
    OCRModel.TROCR,
    OCRModel.EASY_OCR,
    OCRModel.PADDLE_OCR,
})


# =============================================================================
# 텍스트 검출 모델 열거형
# =============================================================================

@unique
class TextDetectionModel(Enum):
    """
    텍스트 검출 모델 열거형.

    지원되는 텍스트 검출 모델을 정의합니다.
    """

    # EAST (Efficient and Accurate Scene Text Detector)
    EAST = "east"

    # CRAFT (Character Region Awareness for Text Detection)
    CRAFT = "craft"

    # DBNet (Differentiable Binarization)
    DBNET = "dbnet"

    # PSENet (Progressive Scale Expansion Network)
    PSENET = "psenet"

    # CTPN (Connectionist Text Proposal Network)
    CTPN = "ctpn"

    @property
    def supports_rotated(self) -> bool:
        """회전된 텍스트 지원 여부."""
        return self in _TEXT_DETECTION_SUPPORTS_ROTATED

    @property
    def output_type(self) -> str:
        """출력 형식 (bbox/polygon)."""
        return _TEXT_DETECTION_OUTPUT_MAP[self]

    def to_korean(self) -> str:
        """한글 모델명 반환."""
        return _TEXT_DETECTION_KOREAN_MAP[self]


# -- TextDetectionModel 캐시 (직접 할당) --

_TEXT_DETECTION_OUTPUT_MAP: dict[TextDetectionModel, str] = {
    TextDetectionModel.EAST: "polygon",
    TextDetectionModel.CRAFT: "polygon",
    TextDetectionModel.DBNET: "polygon",
    TextDetectionModel.PSENET: "polygon",
    TextDetectionModel.CTPN: "bbox",
}

_TEXT_DETECTION_KOREAN_MAP: dict[TextDetectionModel, str] = {
    TextDetectionModel.EAST: "EAST",
    TextDetectionModel.CRAFT: "CRAFT",
    TextDetectionModel.DBNET: "DBNet",
    TextDetectionModel.PSENET: "PSENet",
    TextDetectionModel.CTPN: "CTPN",
}

_TEXT_DETECTION_SUPPORTS_ROTATED: frozenset = frozenset({
    TextDetectionModel.EAST,
    TextDetectionModel.CRAFT,
    TextDetectionModel.DBNET,
})


# =============================================================================
# OCR 상태 열거형
# =============================================================================

@unique
class OCRStatus(Enum):
    """
    OCR 상태 열거형.

    OCR 처리 결과의 상태를 정의합니다.
    """

    # 성공적으로 인식됨
    RECOGNIZED = "recognized"

    # 텍스트 검출됨 (인식 대기)
    DETECTED = "detected"

    # 검출 실패
    NOT_DETECTED = "not_detected"

    # 낮은 신뢰도
    LOW_CONFIDENCE = "low_confidence"

    # 유효하지 않은 결과
    INVALID = "invalid"

    # 처리 중
    PROCESSING = "processing"

    # 타임아웃
    TIMEOUT = "timeout"

    @property
    def is_successful(self) -> bool:
        """성공적인 인식 여부."""
        return self == OCRStatus.RECOGNIZED

    @property
    def needs_retry(self) -> bool:
        """재시도 필요 여부."""
        return self in _OCR_STATUS_NEEDS_RETRY

    @property
    def is_terminal(self) -> bool:
        """최종 상태 여부."""
        return self in _OCR_STATUS_IS_TERMINAL

    def to_korean(self) -> str:
        """한글 상태명 반환."""
        return _OCR_STATUS_KOREAN_MAP[self]


# -- OCRStatus 캐시 (직접 할당) --

_OCR_STATUS_KOREAN_MAP: dict[OCRStatus, str] = {
    OCRStatus.RECOGNIZED: "인식됨",
    OCRStatus.DETECTED: "검출됨",
    OCRStatus.NOT_DETECTED: "검출 안됨",
    OCRStatus.LOW_CONFIDENCE: "낮은 신뢰도",
    OCRStatus.INVALID: "유효하지 않음",
    OCRStatus.PROCESSING: "처리 중",
    OCRStatus.TIMEOUT: "시간 초과",
}

_OCR_STATUS_NEEDS_RETRY: frozenset = frozenset({
    OCRStatus.LOW_CONFIDENCE,
    OCRStatus.TIMEOUT,
})

_OCR_STATUS_IS_TERMINAL: frozenset = frozenset({
    OCRStatus.RECOGNIZED,
    OCRStatus.NOT_DETECTED,
    OCRStatus.INVALID,
})


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # OCR 신뢰도 임계값 (정의서 필수)
    "MIN_OCR_CONFIDENCE",
    "JERSEY_NUMBER_MIN",
    "JERSEY_NUMBER_MAX",
    "OCR_FRAME_INTERVAL",

    # OCR 추가 신뢰도 임계값
    "HIGH_OCR_CONFIDENCE",
    "CONFIRMED_OCR_CONFIDENCE",
    "LOW_OCR_CONFIDENCE",

    # 등번호 범위 상수
    "FIBA_JERSEY_NUMBERS",
    "NBA_JERSEY_NUMBERS",
    "KBL_JERSEY_NUMBERS",

    # OCR 처리 간격 및 빈도
    "OCR_MIN_FRAME_INTERVAL",
    "OCR_MAX_FRAME_INTERVAL",
    "MIN_OCR_OBSERVATIONS_FOR_CONFIRMATION",
    "OCR_CONFIRMATION_CONSISTENCY_RATIO",

    # 텍스트 검출 파라미터
    "TEXT_DETECTION_MIN_CONFIDENCE",
    "TEXT_AREA_MIN",
    "TEXT_AREA_MAX",
    "TEXT_HEIGHT_MIN",
    "TEXT_WIDTH_MIN",
    "TEXT_ASPECT_RATIO_MIN",
    "TEXT_ASPECT_RATIO_MAX",

    # 등번호 ROI 파라미터
    "JERSEY_ROI_TOP_OFFSET",
    "JERSEY_ROI_BOTTOM_OFFSET",
    "JERSEY_ROI_LEFT_OFFSET",
    "JERSEY_ROI_RIGHT_OFFSET",
    "JERSEY_ROI_EXPANSION",

    # 이미지 전처리 파라미터
    "OCR_INPUT_MIN_HEIGHT",
    "OCR_INPUT_MAX_HEIGHT",
    "OCR_INPUT_STANDARD_HEIGHT",
    "GRAYSCALE_WEIGHTS",
    "BINARIZATION_THRESHOLD",
    "ADAPTIVE_BINARIZATION_BLOCK_SIZE",
    "ADAPTIVE_BINARIZATION_CONSTANT",

    # 등번호 문자 특성
    "JERSEY_CHARSET",
    "JERSEY_MAX_DIGITS",
    "JERSEY_MIN_DIGITS",
    "JERSEY_FONT_ASPECT_RATIO_MIN",
    "JERSEY_FONT_ASPECT_RATIO_MAX",
    "JERSEY_CHAR_SPACING_RATIO",

    # 색상 기반 검출 파라미터
    "JERSEY_CONTRAST_MIN",
    "WHITE_TEXT_HSV_LOWER",
    "WHITE_TEXT_HSV_UPPER",
    "BLACK_TEXT_HSV_LOWER",
    "BLACK_TEXT_HSV_UPPER",
    "COLOR_CONTRAST_KERNEL_SIZE",

    # OCR 후처리 파라미터
    "JERSEY_NUMBER_PATTERN",
    "SIMILAR_CHAR_MAPPING",
    "OCR_NMS_IOU_THRESHOLD",
    "SAME_NUMBER_MERGE_DISTANCE",

    # 시간적 일관성 파라미터
    "JERSEY_HISTORY_MAX_FRAMES",
    "JERSEY_CHANGE_THRESHOLD_FRAMES",
    "JERSEY_VOTING_WINDOW",

    # 배치 처리 파라미터
    "OCR_BATCH_SIZE",
    "OCR_MAX_CONCURRENT",
    "OCR_TIMEOUT_MS",

    # 모델별 파라미터
    "CRNN_INPUT_SIZE",
    "CRNN_HIDDEN_SIZE",
    "TROCR_INPUT_SIZE",

    # 열거형
    "OCRModel",
    "TextDetectionModel",
    "OCRStatus",
]

# 모듈 버전 정보
__version__ = "1.0.0"
