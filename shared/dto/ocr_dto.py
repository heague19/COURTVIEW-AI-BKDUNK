# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: ocr_dto.py
설명: OCR 결과 데이터 DTO (Data Transfer Object) 정의
      - OCR 결과, 등번호 인식
      - 멀티뷰 OCR 투표 결과
      - v2.0.0: 다국어(i18n) 지원 추가

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Any, Final
from uuid import UUID, uuid4

from shared.constants.localization import SupportedLanguage
from shared.dto.geometry_dto import BoundingBox, Point2D


# =============================================================================
# i18n 모듈 레벨 캐시
# =============================================================================

_OCR_BACKEND_I18N: Final[dict[str, dict[str, str]]] = {
    "easyocr": {"ko": "EasyOCR (경량)", "en": "EasyOCR (Lightweight)", "ja": "EasyOCR（軽量）", "zh": "EasyOCR（轻量）", "es": "EasyOCR (Ligero)"},
    "paddleocr": {"ko": "PaddleOCR (고정확도)", "en": "PaddleOCR (High Accuracy)", "ja": "PaddleOCR（高精度）", "zh": "PaddleOCR（高精度）", "es": "PaddleOCR (Alta Precisión)"},
    "tesseract": {"ko": "Tesseract (범용)", "en": "Tesseract (General Purpose)", "ja": "Tesseract（汎用）", "zh": "Tesseract（通用）", "es": "Tesseract (Propósito General)"},
    "trocr": {"ko": "TrOCR (트랜스포머)", "en": "TrOCR (Transformer)", "ja": "TrOCR（トランスフォーマー）", "zh": "TrOCR（变换器）", "es": "TrOCR (Transformador)"},
    "custom": {"ko": "커스텀 모델", "en": "Custom Model", "ja": "カスタムモデル", "zh": "自定义模型", "es": "Modelo Personalizado"},
}

_OCR_STATUS_I18N: Final[dict[str, dict[str, str]]] = {
    "success": {"ko": "성공", "en": "Success", "ja": "成功", "zh": "成功", "es": "Éxito"},
    "partial": {"ko": "부분 성공", "en": "Partial Success", "ja": "部分成功", "zh": "部分成功", "es": "Éxito Parcial"},
    "failed": {"ko": "실패", "en": "Failed", "ja": "失敗", "zh": "失败", "es": "Fallido"},
    "low_confidence": {"ko": "낮은 신뢰도", "en": "Low Confidence", "ja": "低信頼度", "zh": "低置信度", "es": "Baja Confianza"},
    "processing": {"ko": "처리 중", "en": "Processing", "ja": "処理中", "zh": "处理中", "es": "Procesando"},
    "skipped": {"ko": "건너뜀", "en": "Skipped", "ja": "スキップ", "zh": "已跳过", "es": "Omitido"},
}


# =============================================================================
# 열거형
# =============================================================================

@unique
class OCRBackend(str, Enum):
    """
    OCR 백엔드 열거형.

    지원되는 OCR 엔진을 정의합니다.
    다국어(i18n) 지원: get_name() 메서드로 5개 언어 지원

    >>> backend = OCRBackend.EASYOCR
    >>> backend.is_lightweight
    True
    """

    # EasyOCR - 경량/빠른 처리
    EASYOCR = "easyocr"

    # PaddleOCR - 높은 정확도
    PADDLEOCR = "paddleocr"

    # Tesseract - 범용 OCR
    TESSERACT = "tesseract"

    # TrOCR - Transformer 기반
    TROCR = "trocr"

    # 커스텀 모델
    CUSTOM = "custom"

    @property
    def supports_korean(self) -> bool:
        """한국어 지원 여부."""
        return self in (
            OCRBackend.EASYOCR,
            OCRBackend.PADDLEOCR,
            OCRBackend.TESSERACT,
        )

    @property
    def is_lightweight(self) -> bool:
        """경량 모델 여부."""
        return self == OCRBackend.EASYOCR

    @property
    def is_transformer_based(self) -> bool:
        """Transformer 기반 모델 여부."""
        return self == OCRBackend.TROCR

    @property
    def to_korean(self) -> str:
        """한글 백엔드명 반환 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 백엔드명 반환 (모듈 레벨 캐시 참조)."""
        entry = _OCR_BACKEND_I18N[self.value]
        return entry.get(lang.value, entry["ko"])


@unique
class OCRStatus(str, Enum):
    """
    OCR 상태 열거형.

    OCR 처리 결과 상태를 정의합니다.
    다국어(i18n) 지원: get_name() 메서드로 5개 언어 지원
    """

    # 성공 - 완전히 인식됨
    SUCCESS = "success"

    # 부분 성공 - 일부만 인식됨
    PARTIAL = "partial"

    # 실패 - 인식 실패
    FAILED = "failed"

    # 낮은 신뢰도 - 인식되었으나 신뢰도 낮음
    LOW_CONFIDENCE = "low_confidence"

    # 처리 중
    PROCESSING = "processing"

    # 건너뜀 - 처리하지 않음
    SKIPPED = "skipped"

    @property
    def is_successful(self) -> bool:
        """성공적인 결과인지."""
        return self in (OCRStatus.SUCCESS, OCRStatus.PARTIAL)

    @property
    def is_usable(self) -> bool:
        """사용 가능한 결과인지."""
        return self in (OCRStatus.SUCCESS, OCRStatus.PARTIAL, OCRStatus.LOW_CONFIDENCE)

    @property
    def is_final(self) -> bool:
        """최종 상태인지 (처리 중이 아닌지)."""
        return self != OCRStatus.PROCESSING

    @property
    def to_korean(self) -> str:
        """한글 상태명 반환 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 상태명 반환 (모듈 레벨 캐시 참조)."""
        entry = _OCR_STATUS_I18N[self.value]
        return entry.get(lang.value, entry["ko"])


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class OCRResult:
    """
    OCR 결과.

    단일 OCR 인식 결과입니다.

    Attributes:
        text: 인식된 텍스트
        confidence: 인식 신뢰도
        bbox: 텍스트 영역 바운딩 박스
        status: OCR 상태
        backend: 사용된 OCR 백엔드
        language: 감지된 언어
        frame_index: 프레임 인덱스
        camera_id: 카메라 ID
        processing_time_ms: 처리 시간 (밀리초)
        raw_output: 원본 출력 (선택적)
    """

    text: str = ""
    confidence: float = 0.0
    bbox: BoundingBox | None = None
    status: OCRStatus = OCRStatus.FAILED
    backend: OCRBackend = OCRBackend.EASYOCR
    language: str = "en"
    frame_index: int = 0
    camera_id: str | None = None
    processing_time_ms: float = 0.0
    raw_output: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.text = self.text.strip()

    @property
    def is_valid(self) -> bool:
        """유효한 결과인지."""
        return self.status.is_usable and len(self.text) > 0

    @property
    def is_numeric(self) -> bool:
        """숫자만 포함하는지."""
        return self.text.isdigit()

    @property
    def is_high_confidence(self) -> bool:
        """높은 신뢰도인지."""
        return self.confidence >= 0.8

    @property
    def text_length(self) -> int:
        """텍스트 길이."""
        return len(self.text)

    def as_integer(self) -> int | None:
        """정수로 변환 (가능한 경우)."""
        try:
            return int(self.text)
        except ValueError:
            return None


@dataclass(slots=True)
class JerseyNumber:
    """
    등번호.

    선수 등번호 인식 결과입니다.

    Attributes:
        number: 등번호 (0-99)
        confidence: 인식 신뢰도
        source: 인식 소스 (front, back)
        ocr_result: 원본 OCR 결과
        person_id: 연관된 인물 ID
        frame_index: 프레임 인덱스
        camera_id: 카메라 ID
        bbox: 등번호 영역 바운딩 박스
        is_confirmed: 확정된 등번호인지
        confirmation_count: 확정에 필요한 인식 횟수
    """

    number: int = -1
    confidence: float = 0.0
    source: str = "unknown"  # front, back, side
    ocr_result: OCRResult | None = None
    person_id: int | None = None
    frame_index: int = 0
    camera_id: str | None = None
    bbox: BoundingBox | None = None
    is_confirmed: bool = False
    confirmation_count: int = 0

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def is_valid(self) -> bool:
        """유효한 등번호인지."""
        return 0 <= self.number <= 99

    @property
    def is_high_confidence(self) -> bool:
        """높은 신뢰도인지."""
        return self.confidence >= 0.8

    @property
    def is_double_digit(self) -> bool:
        """두 자리 등번호인지."""
        return self.number >= 10

    @property
    def is_single_digit(self) -> bool:
        """한 자리 등번호인지."""
        return 0 <= self.number <= 9

    @property
    def display_number(self) -> str:
        """표시용 등번호 문자열."""
        if self.number < 0:
            return "??"
        return str(self.number)

    def matches(self, other: "JerseyNumber") -> bool:
        """다른 등번호와 일치하는지."""
        if not self.is_valid or not other.is_valid:
            return False
        return self.number == other.number


@dataclass(slots=True)
class JerseyNumberVote:
    """
    등번호 투표.

    멀티뷰에서 등번호 투표 결과입니다.

    Attributes:
        number: 등번호
        votes: 투표 수
        total_confidence: 총 신뢰도 합계
        sources: 투표 소스 목록 [(camera_id, confidence), ...]
    """

    number: int = -1
    votes: int = 0
    total_confidence: float = 0.0
    sources: list[tuple[str, float]] = field(default_factory=list)

    @property
    def average_confidence(self) -> float:
        """평균 신뢰도."""
        if self.votes == 0:
            return 0.0
        return self.total_confidence / self.votes

    # 상태 변이 로직 이관: add_vote → detection/ocr/ 서비스 레이어


@dataclass(slots=True)
class MultiViewOCRResult:
    """
    멀티뷰 OCR 결과.

    여러 카메라 뷰의 OCR 결과를 융합합니다.

    Attributes:
        person_id: 인물 ID
        votes: 등번호별 투표 결과
        final_number: 최종 결정된 등번호
        final_confidence: 최종 신뢰도
        view_results: 뷰별 OCR 결과
        is_unanimous: 만장일치 여부
        processing_time_ms: 처리 시간 (밀리초)
    """

    person_id: int = 0
    votes: dict[int, JerseyNumberVote] = field(default_factory=dict)
    final_number: int | None = None
    final_confidence: float = 0.0
    view_results: dict[str, JerseyNumber] = field(default_factory=dict)
    is_unanimous: bool = False
    processing_time_ms: float = 0.0

    @property
    def num_views(self) -> int:
        """뷰 수."""
        return len(self.view_results)

    @property
    def num_candidates(self) -> int:
        """후보 등번호 수."""
        return len(self.votes)

    @property
    def has_result(self) -> bool:
        """결과가 있는지."""
        return self.final_number is not None

    @property
    def winning_margin(self) -> int:
        """1위와 2위 투표 차이."""
        if len(self.votes) < 2:
            return self.votes[self.final_number].votes if self.final_number in self.votes else 0
        sorted_votes = sorted(
            self.votes.values(),
            key=lambda v: v.votes,
            reverse=True
        )
        return sorted_votes[0].votes - sorted_votes[1].votes

    # 비즈니스 로직 이관 완료: add_result, resolve, to_jersey_number
    # → detection/ocr/ 서비스 레이어


@dataclass(slots=True)
class OCRAnalysisResult:
    """
    OCR 분석 결과.

    프레임의 전체 OCR 분석 결과입니다.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        ocr_results: OCR 결과 목록
        jersey_numbers: 등번호 목록
        processing_time_ms: 처리 시간 (밀리초)
        camera_id: 카메라 ID
    """

    frame_index: int = 0
    timestamp: float = 0.0
    ocr_results: list[OCRResult] = field(default_factory=list)
    jersey_numbers: list[JerseyNumber] = field(default_factory=list)
    processing_time_ms: float = 0.0
    camera_id: str | None = None

    @property
    def num_detections(self) -> int:
        """OCR 감지 수."""
        return len(self.ocr_results)

    @property
    def num_jersey_numbers(self) -> int:
        """인식된 등번호 수."""
        return len(self.jersey_numbers)

    @property
    def valid_jersey_numbers(self) -> list[JerseyNumber]:
        """유효한 등번호 목록."""
        return [jn for jn in self.jersey_numbers if jn.is_valid]

    @property
    def average_confidence(self) -> float:
        """평균 신뢰도."""
        if not self.jersey_numbers:
            return 0.0
        return sum(jn.confidence for jn in self.jersey_numbers) / len(self.jersey_numbers)

    def get_jersey_number(self, person_id: int) -> JerseyNumber | None:
        """인물 ID로 등번호 조회."""
        for jn in self.jersey_numbers:
            if jn.person_id == person_id:
                return jn
        return None


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수 - v2.0.0 업데이트)
# =============================================================================

__all__ = [
    # Enum (DTO 고유)
    "OCRBackend",
    "OCRStatus",

    # 데이터 클래스
    "OCRResult",
    "JerseyNumber",
    "JerseyNumberVote",
    "MultiViewOCRResult",
    "OCRAnalysisResult",
]

# 모듈 버전 정보
__version__ = "1.0.0"
