# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: error_codes.py
설명: 시스템 전체 에러 코드 정의 - 모든 예외 및 에러 응답에서 사용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0

참조:
    - shared/exceptions/: CourtViewException 계열이 ErrorCode 참조
    - core_foundation/resilience/: 서킷 브레이커, 재시도 로직에서 RETRYABLE_ERRORS 활용
    - infrastructure/: 스토리지/캐시/카메라 모듈에서 5xxx 에러 발생
    - configs/base/: 에러 코드 매핑 설정

사용 예시:
    >>> from shared.constants.error_codes import ErrorCategory, ErrorCode
    >>> cat = ErrorCategory.from_code(5001)
    >>> cat.description
    '인프라 에러'
    >>> err = ErrorCode.from_code(5001)
    >>> err.message
    '데이터베이스 연결에 실패했습니다'
    >>> err.is_retryable()
    True
    >>> err.http_status
    503
"""

from __future__ import annotations

# === 표준 라이브러리 ===
from enum import Enum, unique
from typing import Final


# =============================================================================
# 에러 카테고리 열거형 (PHASE_01 정의서 준수)
# =============================================================================

@unique
class ErrorCategory(Enum):
    """
    에러 카테고리 분류 열거형.

    에러 코드 범위에 따른 카테고리 분류를 제공하며,
    에러 코드로부터 해당 카테고리를 조회할 수 있습니다.

    Attributes:
        start: 카테고리 시작 코드
        end: 카테고리 종료 코드
        description: 카테고리 설명
    """

    GENERAL = (1000, 1999, "일반 에러")
    AUTHENTICATION = (2000, 2999, "인증/권한 에러")
    VALIDATION = (3000, 3999, "입력 검증 에러")
    BUSINESS = (4000, 4999, "비즈니스 로직 에러")
    INFRASTRUCTURE = (5000, 5999, "인프라 에러")
    EXTERNAL = (6000, 6999, "외부 서비스 에러")
    ANALYSIS = (7000, 7999, "분석 엔진 에러")
    REFEREE = (8000, 8999, "AI 심판 에러")
    SYSTEM = (9000, 9999, "시스템 에러")

    def __init__(self, start: int, end: int, description: str) -> None:
        """에러 카테고리 초기화."""
        self._start = start
        self._end = end
        self._description = description

    @property
    def start(self) -> int:
        """카테고리 시작 코드."""
        return self._start

    @property
    def end(self) -> int:
        """카테고리 종료 코드."""
        return self._end

    @property
    def description(self) -> str:
        """카테고리 설명."""
        return self._description

    def contains(self, code: int) -> bool:
        """해당 코드가 이 카테고리에 속하는지 확인."""
        return self._start <= code <= self._end

    @classmethod
    def from_code(cls, code: int) -> "ErrorCategory":
        """
        에러 코드로 카테고리 조회.

        Args:
            code: 에러 코드 번호

        Returns:
            해당 ErrorCategory enum

        Raises:
            ValueError: 존재하지 않는 코드 범위인 경우
        """
        for category in cls:
            if category.contains(code):
                return category
        raise ValueError(f"알 수 없는 에러 코드 범위: {code}")

    def to_dict(self) -> dict[str, object]:
        """딕셔너리로 변환."""
        return {
            "category": self.name,
            "start": self._start,
            "end": self._end,
            "description": self._description,
        }

    def __str__(self) -> str:
        """문자열 표현."""
        return f"{self.name}({self._start}-{self._end}): {self._description}"

    def __repr__(self) -> str:
        """객체 표현."""
        return f"ErrorCategory.{self.name}(start={self._start}, end={self._end})"


# =============================================================================
# 에러 코드 열거형
# =============================================================================

@unique
class ErrorCode(Enum):
    """
    시스템 에러 코드 열거형.

    에러 코드 체계:
    - 1xxx: 일반 에러
    - 2xxx: 인증/권한 에러
    - 3xxx: 입력 검증 에러
    - 4xxx: 비즈니스 로직 에러
    - 5xxx: 인프라 에러
    - 6xxx: 외부 서비스 에러
    - 7xxx: 분석 엔진 에러
    - 8xxx: AI 심판 에러
    - 9xxx: 시스템 에러

    Attributes:
        code: 에러 코드 (정수)
        message: 기본 에러 메시지 (한글)
        http_status: 대응하는 HTTP 상태 코드
    """

    # ==================== 1xxx: 일반 에러 ====================

    UNKNOWN_ERROR = (1000, "알 수 없는 오류가 발생했습니다", 500)
    INTERNAL_ERROR = (1001, "내부 서버 오류가 발생했습니다", 500)
    NOT_IMPLEMENTED = (1002, "아직 구현되지 않은 기능입니다", 501)
    SERVICE_UNAVAILABLE = (1003, "서비스를 일시적으로 사용할 수 없습니다", 503)
    TIMEOUT_ERROR = (1004, "요청 처리 시간이 초과되었습니다", 504)
    RATE_LIMIT_EXCEEDED = (1005, "요청 한도를 초과했습니다", 429)

    # ==================== 2xxx: 인증/권한 에러 ====================

    AUTHENTICATION_REQUIRED = (2000, "인증이 필요합니다", 401)
    AUTHENTICATION_FAILED = (2001, "인증에 실패했습니다", 401)
    TOKEN_EXPIRED = (2002, "토큰이 만료되었습니다", 401)
    TOKEN_INVALID = (2003, "유효하지 않은 토큰입니다", 401)
    PERMISSION_DENIED = (2004, "권한이 없습니다", 403)
    API_KEY_INVALID = (2005, "유효하지 않은 API 키입니다", 401)
    API_KEY_EXPIRED = (2006, "API 키가 만료되었습니다", 401)

    # ==================== 3xxx: 입력 검증 에러 ====================

    VALIDATION_ERROR = (3000, "입력 데이터 검증에 실패했습니다", 400)
    INVALID_REQUEST = (3001, "잘못된 요청입니다", 400)
    MISSING_REQUIRED_FIELD = (3002, "필수 필드가 누락되었습니다", 400)
    INVALID_FIELD_TYPE = (3003, "필드 타입이 올바르지 않습니다", 400)
    INVALID_FIELD_VALUE = (3004, "필드 값이 유효하지 않습니다", 400)
    INVALID_JSON_FORMAT = (3005, "JSON 형식이 올바르지 않습니다", 400)
    INVALID_DATE_FORMAT = (3006, "날짜 형식이 올바르지 않습니다", 400)
    VALUE_OUT_OF_RANGE = (3007, "값이 허용 범위를 벗어났습니다", 400)
    STRING_TOO_LONG = (3008, "문자열이 너무 깁니다", 400)
    STRING_TOO_SHORT = (3009, "문자열이 너무 짧습니다", 400)
    INVALID_ENUM_VALUE = (3010, "유효하지 않은 열거형 값입니다", 400)

    # URL 검증 에러 (3011-3019)
    URL_VALIDATION_ERROR = (3011, "URL 검증에 실패했습니다", 400)
    URL_INVALID_FORMAT = (3012, "유효하지 않은 URL 형식입니다", 400)
    URL_INVALID_SCHEME = (3013, "허용되지 않은 URL 스킴입니다", 400)
    URL_BLOCKED_HOST = (3014, "차단된 호스트입니다", 403)
    URL_PRIVATE_IP = (3015, "내부 IP 주소에 대한 접근이 차단되었습니다", 403)
    URL_TOO_LONG = (3016, "URL 길이가 너무 깁니다", 400)

    # 보안 에러 (3020-3029)
    SECURITY_ERROR = (3020, "보안 검사에 실패했습니다", 403)
    SSRF_DETECTED = (3021, "SSRF 공격이 감지되었습니다", 403)
    DNS_REBINDING_DETECTED = (3022, "DNS 리바인딩 공격이 감지되었습니다", 403)
    ENCRYPTION_ERROR = (3023, "암호화/복호화에 실패했습니다", 500)
    ENCRYPTION_UNAVAILABLE = (3024, "암호화 라이브러리를 사용할 수 없습니다", 500)

    # 파일 포맷 에러 (3030-3039)
    FORMAT_DETECTION_ERROR = (3030, "파일 포맷 감지에 실패했습니다", 400)
    UNSUPPORTED_FORMAT = (3031, "지원하지 않는 파일 포맷입니다", 400)
    CORRUPTED_FILE = (3032, "파일이 손상되었습니다", 400)
    INVALID_MAGIC_BYTES = (3033, "유효하지 않은 파일 시그니처입니다", 400)
    FORMAT_MISMATCH = (3034, "파일 확장자와 실제 포맷이 일치하지 않습니다", 400)

    # 포맷 검증 에러 (3040-3059)
    FORMAT_VALIDATION_ERROR = (3040, "포맷 검증에 실패했습니다", 400)
    FORMAT_NOT_ALLOWED = (3041, "허용되지 않은 포맷입니다", 400)
    CODEC_NOT_SUPPORTED = (3042, "지원하지 않는 코덱입니다", 400)
    BITRATE_OUT_OF_RANGE = (3043, "비트레이트가 허용 범위를 벗어났습니다", 400)
    CONTAINER_FORMAT_ERROR = (3044, "컨테이너 포맷 오류입니다", 400)

    # 해상도 에러 (3050-3059)
    RESOLUTION_ERROR = (3050, "해상도 검증에 실패했습니다", 400)
    RESOLUTION_TOO_LOW = (3051, "해상도가 너무 낮습니다", 400)
    RESOLUTION_TOO_HIGH = (3052, "해상도가 너무 높습니다", 400)
    RESOLUTION_NOT_SUPPORTED = (3053, "지원하지 않는 해상도입니다", 400)
    ASPECT_RATIO_NOT_SUPPORTED = (3054, "지원하지 않는 화면 비율입니다", 400)

    # FPS/Duration 에러 (3060-3069)
    FPS_ERROR = (3060, "FPS 검증에 실패했습니다", 400)
    FPS_TOO_LOW = (3061, "FPS가 너무 낮습니다", 400)
    FPS_TOO_HIGH = (3062, "FPS가 너무 높습니다", 400)
    DURATION_TOO_SHORT = (3063, "영상 길이가 너무 짧습니다", 400)
    DURATION_TOO_LONG = (3064, "영상 길이가 너무 깁니다", 400)

    # 데이터 품질 에러 (3070-3089)
    DATA_QUALITY_ERROR = (3070, "데이터 품질 검사에 실패했습니다", 400)
    LOW_QUALITY_ERROR = (3071, "데이터 품질이 최소 기준에 미달합니다", 400)
    BRIGHTNESS_TOO_LOW = (3072, "영상 밝기가 너무 낮습니다", 400)
    BRIGHTNESS_TOO_HIGH = (3073, "영상 밝기가 너무 높습니다", 400)
    CONTRAST_TOO_LOW = (3074, "영상 대비가 너무 낮습니다", 400)
    NOISE_TOO_HIGH = (3075, "영상 노이즈가 너무 높습니다", 400)
    BLUR_TOO_HIGH = (3076, "영상이 너무 흐릿합니다", 400)
    SHARPNESS_TOO_LOW = (3077, "영상 선명도가 너무 낮습니다", 400)
    COLOR_SATURATION_ERROR = (3078, "색상 채도가 부적절합니다", 400)
    EXPOSURE_ERROR = (3079, "노출 상태가 부적절합니다", 400)
    MOTION_BLUR_DETECTED = (3080, "움직임 블러가 감지되었습니다", 400)
    COMPRESSION_ARTIFACT = (3081, "압축 아티팩트가 감지되었습니다", 400)
    QUALITY_CHECK_FAILED = (3082, "품질 검사를 완료할 수 없습니다", 500)

    # ==================== 4xxx: 비즈니스 로직 에러 ====================

    RESOURCE_NOT_FOUND = (4000, "리소스를 찾을 수 없습니다", 404)
    RESOURCE_ALREADY_EXISTS = (4001, "리소스가 이미 존재합니다", 409)
    RESOURCE_CONFLICT = (4002, "리소스 충돌이 발생했습니다", 409)
    OPERATION_NOT_ALLOWED = (4003, "허용되지 않은 작업입니다", 405)
    PRECONDITION_FAILED = (4004, "사전 조건이 충족되지 않았습니다", 412)
    QUOTA_EXCEEDED = (4005, "할당량을 초과했습니다", 429)

    # ==================== 5xxx: 인프라 에러 ====================

    # 데이터베이스 에러 (5000-5099)
    DATABASE_ERROR = (5000, "데이터베이스 오류가 발생했습니다", 500)
    DATABASE_CONNECTION_FAILED = (5001, "데이터베이스 연결에 실패했습니다", 503)
    DATABASE_QUERY_FAILED = (5002, "데이터베이스 쿼리 실행에 실패했습니다", 500)
    DATABASE_TRANSACTION_FAILED = (5003, "데이터베이스 트랜잭션에 실패했습니다", 500)
    DATABASE_TIMEOUT = (5004, "데이터베이스 쿼리 시간이 초과되었습니다", 504)
    DATABASE_INTEGRITY_ERROR = (5005, "데이터베이스 무결성 제약 조건 위반입니다", 409)
    DATABASE_RECORD_NOT_FOUND = (5006, "데이터베이스 레코드를 찾을 수 없습니다", 404)

    # 캐시 에러 (5100-5199)
    CACHE_ERROR = (5100, "캐시 오류가 발생했습니다", 500)
    CACHE_CONNECTION_FAILED = (5101, "캐시 서버 연결에 실패했습니다", 503)
    CACHE_OPERATION_FAILED = (5102, "캐시 작업에 실패했습니다", 500)
    CACHE_KEY_NOT_FOUND = (5103, "캐시 키를 찾을 수 없습니다", 404)
    CACHE_SERIALIZATION_ERROR = (5104, "캐시 직렬화/역직렬화에 실패했습니다", 500)

    # 큐 에러 (5200-5299)
    QUEUE_ERROR = (5200, "큐 오류가 발생했습니다", 500)
    QUEUE_CONNECTION_FAILED = (5201, "큐 서버 연결에 실패했습니다", 503)
    QUEUE_PUBLISH_FAILED = (5202, "메시지 발행에 실패했습니다", 500)
    QUEUE_CONSUME_FAILED = (5203, "메시지 소비에 실패했습니다", 500)
    QUEUE_TIMEOUT = (5204, "큐 작업 시간이 초과되었습니다", 504)

    # 스토리지 에러 (5300-5349)
    STORAGE_ERROR = (5300, "스토리지 오류가 발생했습니다", 500)
    STORAGE_CONNECTION_FAILED = (5301, "스토리지 연결에 실패했습니다", 503)
    STORAGE_UPLOAD_FAILED = (5302, "파일 업로드에 실패했습니다", 500)
    STORAGE_DOWNLOAD_FAILED = (5303, "파일 다운로드에 실패했습니다", 500)
    STORAGE_DELETE_FAILED = (5304, "파일 삭제에 실패했습니다", 500)
    STORAGE_FILE_NOT_FOUND = (5305, "파일을 찾을 수 없습니다", 404)
    STORAGE_QUOTA_EXCEEDED = (5306, "스토리지 할당량을 초과했습니다", 507)
    STORAGE_PERMISSION_DENIED = (5307, "스토리지 접근 권한이 없습니다", 403)

    # 스트림 에러 (5350-5399)
    STREAM_ERROR = (5350, "스트림 오류가 발생했습니다", 500)
    STREAM_CONNECTION_FAILED = (5351, "스트림 연결에 실패했습니다", 503)
    STREAM_DISCONNECTED = (5352, "스트림 연결이 끊어졌습니다", 503)
    STREAM_TIMEOUT = (5353, "스트림 응답 시간이 초과되었습니다", 504)
    STREAM_INVALID_SOURCE = (5354, "유효하지 않은 스트림 소스입니다", 400)
    STREAM_UNSUPPORTED_TYPE = (5355, "지원하지 않는 스트림 타입입니다", 400)
    STREAM_BUFFER_OVERFLOW = (5356, "스트림 버퍼가 초과되었습니다", 500)
    STREAM_DECODE_ERROR = (5357, "스트림 디코딩에 실패했습니다", 500)
    STREAM_FRAME_ERROR = (5358, "프레임 처리에 실패했습니다", 500)
    STREAM_AUTHENTICATION_FAILED = (5359, "스트림 인증에 실패했습니다", 401)

    # 인프라 공통 에러 (5400-5499)
    INFRASTRUCTURE_ERROR = (5400, "인프라 오류가 발생했습니다", 500)
    CIRCUIT_BREAKER_OPEN = (5401, "서킷 브레이커가 열린 상태입니다", 503)

    # 모델 레지스트리 에러 (5500-5599)
    MODEL_ALREADY_EXISTS = (5502, "모델이 이미 등록되어 있습니다", 409)
    MODEL_TYPE_NOT_SUPPORTED = (5504, "지원하지 않는 모델 타입입니다", 400)
    MODEL_PATH_NOT_FOUND = (5505, "모델 경로를 찾을 수 없습니다", 404)

    # 서비스 레지스트리 에러 (5600-5699)
    SERVICE_REGISTRY_ERROR = (5600, "서비스 레지스트리 오류가 발생했습니다", 500)
    SERVICE_ALREADY_EXISTS = (5601, "서비스가 이미 존재합니다", 409)
    SERVICE_NOT_AVAILABLE = (5602, "서비스를 사용할 수 없습니다", 503)
    SERVICE_CLASS_NOT_FOUND = (5603, "서비스 클래스를 찾을 수 없습니다", 404)

    # 파이프라인 에러 (5700-5799)
    PIPELINE_ERROR = (5700, "파이프라인 오류가 발생했습니다", 500)
    PIPELINE_CONFIG_NOT_FOUND = (5701, "파이프라인 설정을 찾을 수 없습니다", 404)
    STAGE_EXECUTION_FAILED = (5702, "스테이지 실행에 실패했습니다", 500)

    # 디코딩 에러 (5800-5849)
    DECODING_ERROR = (5800, "비디오 디코딩에 실패했습니다", 500)
    DECODING_INIT_FAILED = (5801, "디코더 초기화에 실패했습니다", 500)
    DECODING_FRAME_FAILED = (5802, "프레임 디코딩에 실패했습니다", 500)
    DECODING_SEEK_FAILED = (5803, "비디오 탐색에 실패했습니다", 500)
    DECODING_EOF = (5804, "비디오 끝에 도달했습니다", 200)
    CODEC_ERROR = (5810, "코덱 오류가 발생했습니다", 500)
    CODEC_NOT_FOUND = (5811, "코덱을 찾을 수 없습니다", 400)
    CODEC_INIT_FAILED = (5812, "코덱 초기화에 실패했습니다", 500)
    CORRUPTED_VIDEO = (5820, "비디오 파일이 손상되었습니다", 400)
    CORRUPTED_FRAME = (5821, "프레임이 손상되었습니다", 500)
    HARDWARE_ACCEL_ERROR = (5830, "하드웨어 가속 오류가 발생했습니다", 500)
    HARDWARE_ACCEL_NOT_AVAILABLE = (5831, "하드웨어 가속을 사용할 수 없습니다", 400)

    # 프레임 추출 에러 (5840-5859)
    FRAME_EXTRACTION_ERROR = (5840, "프레임 추출에 실패했습니다", 500)
    FRAME_EXTRACTION_INIT_FAILED = (5841, "프레임 추출기 초기화에 실패했습니다", 500)
    FRAME_EXTRACTION_TIMEOUT = (5842, "프레임 추출 시간이 초과되었습니다", 504)
    END_OF_STREAM = (5843, "스트림 끝에 도달했습니다", 200)
    KEYFRAME_DETECTION_FAILED = (5844, "키프레임 감지에 실패했습니다", 500)
    SCENE_CHANGE_DETECTION_FAILED = (5845, "장면 전환 감지에 실패했습니다", 500)
    FRAME_BUFFER_OVERFLOW = (5846, "프레임 버퍼가 초과되었습니다", 500)
    INVALID_FRAME_RANGE = (5847, "유효하지 않은 프레임 범위입니다", 400)

    # 비디오 정규화 에러 (5860-5879)
    NORMALIZATION_ERROR = (5860, "비디오 정규화에 실패했습니다", 500)
    NORMALIZATION_INIT_FAILED = (5861, "정규화기 초기화에 실패했습니다", 500)
    VIDEO_RESOLUTION_CONVERSION_ERROR = (5862, "해상도 변환에 실패했습니다", 500)
    INVALID_TARGET_RESOLUTION = (5863, "유효하지 않은 목표 해상도입니다", 400)
    UNSUPPORTED_TARGET_RESOLUTION = (5864, "지원하지 않는 목표 해상도입니다", 400)
    FPS_CONVERSION_ERROR = (5865, "FPS 변환에 실패했습니다", 500)
    INVALID_FPS = (5866, "유효하지 않은 FPS입니다", 400)
    ASPECT_RATIO_ERROR = (5867, "종횡비 변환에 실패했습니다", 500)
    INVALID_ASPECT_RATIO = (5868, "유효하지 않은 종횡비입니다", 400)
    INTERPOLATION_ERROR = (5869, "보간 처리에 실패했습니다", 500)
    COLOR_SPACE_CONVERSION_ERROR = (5870, "색공간 변환에 실패했습니다", 500)
    FORMAT_CONVERSION_ERROR = (5871, "포맷 변환에 실패했습니다", 500)

    # 비디오 분류 에러 (5880-5899)
    CLASSIFICATION_ERROR = (5880, "비디오 분류에 실패했습니다", 500)
    CLASSIFICATION_INIT_FAILED = (5881, "분류기 초기화에 실패했습니다", 500)
    CLASSIFICATION_TIMEOUT = (5882, "분류 시간이 초과되었습니다", 504)
    CLASSIFICATION_LOW_CONFIDENCE = (5883, "분류 신뢰도가 너무 낮습니다", 400)
    CLASSIFICATION_AMBIGUOUS = (5884, "분류 결과가 모호합니다", 400)
    CLASSIFICATION_UNSUPPORTED_FORMAT = (5885, "분류를 지원하지 않는 형식입니다", 400)
    CLASSIFICATION_FEATURE_EXTRACTION_FAILED = (5886, "특성 추출에 실패했습니다", 500)
    CLASSIFICATION_INVALID_VIDEO = (5887, "분류에 적합하지 않은 비디오입니다", 400)
    TRAINING_TYPE_DETECTION_FAILED = (5888, "훈련 유형 감지에 실패했습니다", 500)
    GAME_TYPE_DETECTION_FAILED = (5889, "경기 유형 감지에 실패했습니다", 500)

    # 적응형 샘플링 에러 (5890-5899)
    SAMPLING_ERROR = (5890, "프레임 샘플링에 실패했습니다", 500)
    SAMPLING_INIT_FAILED = (5891, "샘플러 초기화에 실패했습니다", 500)
    SAMPLING_CONFIG_INVALID = (5892, "샘플링 설정이 유효하지 않습니다", 400)
    MOTION_ANALYSIS_FAILED = (5893, "움직임 분석에 실패했습니다", 500)
    OPTICAL_FLOW_FAILED = (5894, "옵티컬 플로우 계산에 실패했습니다", 500)
    SAMPLING_RATE_INVALID = (5895, "샘플링 레이트가 유효하지 않습니다", 400)
    INSUFFICIENT_FRAMES = (5896, "샘플링할 프레임이 부족합니다", 400)
    SAMPLING_TIMEOUT = (5897, "샘플링 시간이 초과되었습니다", 504)

    # 카메라 에러 (5900-5999)
    CAMERA_ERROR = (5900, "카메라 오류가 발생했습니다", 500)
    CONNECTION_ERROR = (5901, "카메라 연결에 실패했습니다", 503)
    CAMERA_DISCONNECTED = (5902, "카메라 연결이 끊어졌습니다", 503)
    CAMERA_TIMEOUT = (5903, "카메라 응답 시간이 초과되었습니다", 504)
    CAMERA_NOT_FOUND = (5904, "카메라를 찾을 수 없습니다", 404)
    CAMERA_NOT_REGISTERED = (5905, "등록되지 않은 카메라입니다", 404)
    CAMERA_ALREADY_REGISTERED = (5906, "이미 등록된 카메라입니다", 409)
    CAMERA_MAX_EXCEEDED = (5907, "최대 카메라 수를 초과했습니다", 400)
    CAMERA_CALIBRATION_FAILED = (5908, "카메라 캘리브레이션에 실패했습니다", 500)
    CAMERA_FRAME_ERROR = (5909, "카메라 프레임 처리에 실패했습니다", 500)
    CAMERA_PROTOCOL_ERROR = (5910, "카메라 프로토콜 오류입니다", 500)
    CAMERA_SESSION_ERROR = (5911, "카메라 세션 오류입니다", 500)

    # GPU/Desktop 하드웨어 에러 (5920-5939)
    GPU_ERROR = (5920, "GPU 오류가 발생했습니다", 500)
    GPU_MEMORY_ERROR = (5921, "GPU 메모리 오류가 발생했습니다", 500)
    GPU_MEMORY_ALLOCATION_FAILED = (5922, "GPU 메모리 할당에 실패했습니다", 500)
    GPU_MEMORY_FRAGMENTATION = (5923, "GPU 메모리 단편화가 발생했습니다", 500)
    CUDA_ERROR = (5924, "CUDA 런타임 오류가 발생했습니다", 500)
    CUDA_DEVICE_NOT_FOUND = (5925, "CUDA 장치를 찾을 수 없습니다", 400)
    CUDA_DRIVER_ERROR = (5926, "CUDA 드라이버 오류가 발생했습니다", 500)
    GPU_TEMPERATURE_CRITICAL = (5927, "GPU 온도가 임계치를 초과했습니다", 503)
    GPU_POWER_LIMIT_EXCEEDED = (5928, "GPU 전력 한계를 초과했습니다", 503)
    GPU_COMPUTE_CAPABILITY_LOW = (5929, "GPU 컴퓨팅 능력이 부족합니다", 400)
    TENSORRT_ERROR = (5930, "TensorRT 엔진 오류가 발생했습니다", 500)
    MODEL_OPTIMIZATION_FAILED = (5931, "모델 GPU 최적화에 실패했습니다", 500)

    # 멀티카메라 동기화 에러 (5940-5959)
    MULTI_CAMERA_ERROR = (5940, "멀티카메라 시스템 오류가 발생했습니다", 500)
    CAMERA_SYNC_ERROR = (5941, "카메라 동기화에 실패했습니다", 500)
    CAMERA_TIMESTAMP_DRIFT = (5942, "카메라 타임스탬프 드리프트가 발생했습니다", 500)
    CAMERA_FRAME_DROP = (5943, "카메라 프레임 드롭이 발생했습니다", 500)
    CAMERA_SYNC_LOSS = (5944, "카메라 동기화가 완전히 손실되었습니다", 503)
    CAMERA_BUFFER_OVERFLOW = (5945, "카메라 프레임 버퍼가 초과되었습니다", 500)
    CAMERA_GENLOCK_FAILED = (5946, "카메라 Genlock 동기화에 실패했습니다", 500)
    MULTI_VIEW_CALIBRATION_FAILED = (5947, "멀티뷰 캘리브레이션에 실패했습니다", 500)
    COORDINATE_TRANSFORM_FAILED = (5948, "3D 좌표 변환에 실패했습니다", 500)

    # ==================== 6xxx: 외부 서비스 에러 ====================

    EXTERNAL_SERVICE_ERROR = (6000, "외부 서비스 오류가 발생했습니다", 502)
    EXTERNAL_SERVICE_TIMEOUT = (6001, "외부 서비스 응답 시간이 초과되었습니다", 504)
    EXTERNAL_SERVICE_UNAVAILABLE = (6002, "외부 서비스를 사용할 수 없습니다", 503)
    WEBHOOK_DELIVERY_FAILED = (6003, "웹훅 전송에 실패했습니다", 500)

    # ==================== 7xxx: 분석 엔진 에러 ====================

    # 분석 기본 에러 (7000-7099)
    ANALYSIS_ERROR = (7000, "분석 중 오류가 발생했습니다", 500)
    ANALYSIS_TIMEOUT = (7001, "분석 시간이 초과되었습니다", 504)
    ANALYSIS_CANCELLED = (7002, "분석이 취소되었습니다", 499)

    # 비디오 처리 에러 (7100-7199)
    VIDEO_ERROR = (7100, "비디오 처리 중 오류가 발생했습니다", 500)
    VIDEO_FORMAT_UNSUPPORTED = (7101, "지원하지 않는 비디오 형식입니다", 400)
    VIDEO_TOO_LARGE = (7102, "비디오 파일이 너무 큽니다", 413)
    VIDEO_TOO_LONG = (7103, "비디오 길이가 너무 깁니다", 400)
    VIDEO_CORRUPTED = (7104, "비디오 파일이 손상되었습니다", 400)
    VIDEO_DOWNLOAD_FAILED = (7105, "비디오 다운로드에 실패했습니다", 500)
    FRAME_EXTRACTION_FAILED = (7106, "프레임 추출에 실패했습니다", 500)

    # 감지 에러 (7200-7299)
    DETECTION_ERROR = (7200, "감지 중 오류가 발생했습니다", 500)
    DETECTION_NO_PERSON = (7201, "영상에서 사람을 감지할 수 없습니다", 400)
    DETECTION_NO_BALL = (7202, "영상에서 공을 감지할 수 없습니다", 400)
    DETECTION_NO_COURT = (7203, "영상에서 코트를 감지할 수 없습니다", 400)
    DETECTION_NO_HOOP = (7204, "영상에서 골대를 감지할 수 없습니다", 400)
    DETECTION_MULTIPLE_PERSONS = (7205, "여러 명이 감지되어 분석할 수 없습니다", 400)
    DETECTION_LOW_CONFIDENCE = (7206, "감지 신뢰도가 너무 낮습니다", 400)

    # 포즈 추정 에러 (7300-7399)
    POSE_ESTIMATION_ERROR = (7300, "포즈 추정 중 오류가 발생했습니다", 500)
    POSE_ESTIMATION_FAILED = (7301, "포즈 추정에 실패했습니다", 500)
    POSE_INSUFFICIENT_KEYPOINTS = (7302, "키포인트가 부족합니다", 400)
    POSE_OCCLUSION_DETECTED = (7303, "신체 일부가 가려져 있습니다", 400)

    # 생체역학 에러 (7400-7499)
    BIOMECHANICS_ERROR = (7400, "생체역학 분석 중 오류가 발생했습니다", 500)
    BIOMECHANICS_INVALID_ANGLE = (7401, "관절 각도가 유효하지 않습니다", 400)
    BIOMECHANICS_INVALID_VELOCITY = (7402, "속도 값이 유효하지 않습니다", 400)

    # 동작 분석 에러 (7500-7599)
    MOTION_ANALYSIS_ERROR = (7500, "동작 분석 중 오류가 발생했습니다", 500)
    MOTION_NOT_DETECTED = (7501, "분석할 동작을 감지할 수 없습니다", 400)
    MOTION_INSUFFICIENT_DATA = (7502, "분석을 위한 데이터가 부족합니다", 400)
    SHOOTING_NOT_DETECTED = (7510, "슈팅 동작을 감지할 수 없습니다", 400)
    DRIBBLING_NOT_DETECTED = (7511, "드리블 동작을 감지할 수 없습니다", 400)

    # 경기 분석 에러 (7600-7699)
    GAME_ANALYSIS_ERROR = (7600, "경기 분석 중 오류가 발생했습니다", 500)
    GAME_INSUFFICIENT_DURATION = (7601, "영상 길이가 너무 짧습니다", 400)

    # 모델 에러 (7700-7799)
    MODEL_ERROR = (7700, "모델 오류가 발생했습니다", 500)
    MODEL_LOAD_FAILED = (7701, "모델 로드에 실패했습니다", 500)
    MODEL_INFERENCE_FAILED = (7702, "모델 추론에 실패했습니다", 500)
    MODEL_NOT_FOUND = (7703, "모델을 찾을 수 없습니다", 404)
    MODEL_VERSION_MISMATCH = (7704, "모델 버전이 일치하지 않습니다", 400)
    MODEL_VERSION_NOT_FOUND = (7705, "모델 버전을 찾을 수 없습니다", 404)
    MODEL_NOT_INITIALIZED = (7706, "모델이 초기화되지 않았습니다", 500)
    MODEL_INITIALIZATION_FAILED = (7707, "모델 초기화에 실패했습니다", 500)

    # 학습 시스템 에러 (7800-7899)
    LEARNING_ERROR = (7800, "학습 시스템 오류가 발생했습니다", 500)
    PATTERN_LEARNING_FAILED = (7801, "패턴 학습에 실패했습니다", 500)
    FEEDBACK_COLLECTION_FAILED = (7802, "피드백 수집에 실패했습니다", 500)
    MODEL_ADAPTATION_FAILED = (7803, "모델 적응에 실패했습니다", 500)
    LEARNING_SCHEDULER_ERROR = (7804, "학습 스케줄러 오류가 발생했습니다", 500)
    PROFILE_LEARNING_FAILED = (7805, "프로필 학습에 실패했습니다", 500)
    VALIDATION_SPLIT_ERROR = (7806, "데이터 분할에 실패했습니다", 500)
    ACTIVE_LEARNING_ERROR = (7807, "능동 학습에 실패했습니다", 500)
    LEARNING_HISTORY_ERROR = (7808, "학습 이력 관리에 실패했습니다", 500)
    INCREMENTAL_TRAINING_ERROR = (7809, "점진적 학습에 실패했습니다", 500)
    FEEDBACK_INTEGRATION_ERROR = (7810, "피드백 통합에 실패했습니다", 500)
    PERFORMANCE_TRACKING_ERROR = (7811, "성능 추적에 실패했습니다", 500)
    CHECKPOINT_ERROR = (7812, "체크포인트 처리에 실패했습니다", 500)
    ROLLBACK_ERROR = (7813, "롤백에 실패했습니다", 500)
    THRESHOLD_ADJUSTMENT_ERROR = (7814, "임계값 조정에 실패했습니다", 500)
    ACCURACY_MONITOR_ERROR = (7815, "정확도 모니터링에 실패했습니다", 500)
    DRIFT_DETECTION_ERROR = (7816, "드리프트 감지에 실패했습니다", 500)
    CALIBRATION_ERROR = (7817, "캘리브레이션에 실패했습니다", 500)
    EVALUATION_ERROR = (7818, "모델 평가에 실패했습니다", 500)
    DATA_AUGMENTATION_ERROR = (7819, "데이터 증강에 실패했습니다", 500)
    FEATURE_STORE_ERROR = (7820, "피처 스토어 오류가 발생했습니다", 500)
    LABELING_ERROR = (7821, "레이블링에 실패했습니다", 500)
    EXPERIMENT_TRACKING_ERROR = (7822, "실험 추적에 실패했습니다", 500)
    AB_TEST_ERROR = (7823, "A/B 테스트 오류가 발생했습니다", 500)
    EXPLANATION_ERROR = (7824, "모델 설명 생성에 실패했습니다", 500)

    # ==================== 8xxx: AI 심판 에러 ====================

    REFEREE_ERROR = (8000, "AI 심판 판정 중 오류가 발생했습니다", 500)
    REFEREE_RULE_NOT_FOUND = (8001, "규칙을 찾을 수 없습니다", 404)
    REFEREE_INVALID_RULE_SET = (8002, "유효하지 않은 규칙 세트입니다", 400)
    REFEREE_INSUFFICIENT_DATA = (8003, "판정을 위한 데이터가 부족합니다", 400)
    REFEREE_LOW_CONFIDENCE = (8004, "판정 신뢰도가 너무 낮습니다", 400)

    # 규칙 세트 관리 에러 (8005-8099)
    RULE_SET_NOT_FOUND = (8005, "규칙 세트를 찾을 수 없습니다", 404)
    RULE_SET_VALIDATION_ERROR = (8006, "규칙 세트 검증에 실패했습니다", 400)
    RULE_SET_VERSION_MISMATCH = (8007, "규칙 세트 버전이 일치하지 않습니다", 400)
    RULE_SET_LOAD_ERROR = (8008, "규칙 세트 로드에 실패했습니다", 500)
    RULE_SET_SCHEMA_ERROR = (8009, "규칙 세트 스키마가 유효하지 않습니다", 400)

    # ==================== 9xxx: 시스템 에러 ====================

    # 설정 에러 (9000-9099)
    CONFIGURATION_ERROR = (9000, "설정 오류가 발생했습니다", 500)
    CONFIGURATION_NOT_FOUND = (9001, "설정 파일을 찾을 수 없습니다", 500)
    CONFIGURATION_INVALID = (9002, "설정 값이 유효하지 않습니다", 500)
    CONFIGURATION_LOAD_FAILED = (9003, "설정 로드에 실패했습니다", 500)

    # 초기화/종료 에러 (9100-9199)
    INITIALIZATION_ERROR = (9100, "초기화 중 오류가 발생했습니다", 500)
    SHUTDOWN_ERROR = (9101, "종료 중 오류가 발생했습니다", 500)

    # 의존성 에러 (9200-9299)
    DEPENDENCY_ERROR = (9200, "의존성 오류가 발생했습니다", 500)
    CIRCULAR_DEPENDENCY = (9201, "순환 의존성이 감지되었습니다", 500)
    MISSING_DEPENDENCY = (9202, "필수 의존성이 누락되었습니다", 500)

    def __init__(self, code: int, message: str, http_status: int) -> None:
        """에러 코드 초기화."""
        self._code = code
        self._message = message
        self._http_status = http_status

    @property
    def code(self) -> int:
        """에러 코드 반환."""
        return self._code

    @property
    def message(self) -> str:
        """기본 에러 메시지 반환."""
        return self._message

    @property
    def http_status(self) -> int:
        """HTTP 상태 코드 반환."""
        return self._http_status

    @property
    def category(self) -> ErrorCategory:
        """에러 카테고리 반환."""
        return ErrorCategory.from_code(self._code)

    def to_dict(self) -> dict[str, object]:
        """딕셔너리로 변환."""
        return {
            "error_code": self.name,
            "code": self._code,
            "message": self._message,
            "http_status": self._http_status,
            "category": self.category.name,
        }

    @classmethod
    def from_code(cls, code: int) -> "ErrorCode":
        """
        코드 번호로 ErrorCode 조회 (O(1) 성능).

        Args:
            code: 에러 코드 번호

        Returns:
            해당 ErrorCode enum

        Raises:
            ValueError: 존재하지 않는 코드인 경우
        """
        if code in ERROR_CODE_LOOKUP:
            return ERROR_CODE_LOOKUP[code]
        raise ValueError(f"알 수 없는 에러 코드: {code}")

    @classmethod
    def get_by_category(cls, category: ErrorCategory) -> tuple["ErrorCode", ...]:
        """
        특정 카테고리에 속하는 모든 에러 코드 조회.

        Args:
            category: 에러 카테고리

        Returns:
            해당 카테고리의 모든 ErrorCode 튜플
        """
        return tuple(
            error for error in cls
            if category.contains(error.code)
        )

    def is_retryable(self) -> bool:
        """
        재시도 가능 여부 판단.

        5xx 서버 에러 중 일부와 타임아웃 에러는 재시도 가능.
        frozenset[ErrorCode] 기반 O(1) 멤버십 테스트.

        Returns:
            bool: 재시도 가능 여부
        """
        return self in RETRYABLE_ERRORS

    def is_client_error(self) -> bool:
        """클라이언트 에러(4xx) 여부 확인."""
        return 400 <= self._http_status < 500

    def is_server_error(self) -> bool:
        """서버 에러(5xx) 여부 확인."""
        return 500 <= self._http_status < 600

    def __str__(self) -> str:
        """문자열 표현."""
        return f"[{self._code}] {self._message}"

    def __repr__(self) -> str:
        """객체 표현."""
        return f"ErrorCode.{self.name}(code={self._code}, http_status={self._http_status})"


# =============================================================================
# ErrorCode 캐시 (직접 할당, 모듈 로드 시 O(1) 접근)
# =============================================================================

# 코드 번호 → ErrorCode 조회 캐시
ERROR_CODE_LOOKUP: Final[dict[int, ErrorCode]] = {
    error.code: error for error in ErrorCode
}

# 재시도 가능 에러 코드 집합 - frozenset[ErrorCode]로 타입 안전성 보장
# 5xx 서버 에러 중 일시적 장애, 타임아웃, 연결 실패 등 재시도로 복구 가능한 에러
RETRYABLE_ERRORS: Final[frozenset[ErrorCode]] = frozenset({
    ErrorCode.TIMEOUT_ERROR,                # 1004: 요청 타임아웃
    ErrorCode.SERVICE_UNAVAILABLE,          # 1003: 서비스 일시 불가
    ErrorCode.DATABASE_TIMEOUT,             # 5004: DB 타임아웃
    ErrorCode.DATABASE_CONNECTION_FAILED,   # 5001: DB 연결 실패
    ErrorCode.CACHE_CONNECTION_FAILED,      # 5101: 캐시 연결 실패
    ErrorCode.QUEUE_CONNECTION_FAILED,      # 5201: 큐 연결 실패
    ErrorCode.QUEUE_TIMEOUT,               # 5204: 큐 타임아웃
    ErrorCode.STORAGE_CONNECTION_FAILED,    # 5301: 스토리지 연결 실패
    ErrorCode.STREAM_CONNECTION_FAILED,     # 5351: 스트림 연결 실패
    ErrorCode.STREAM_DISCONNECTED,          # 5352: 스트림 연결 끊김
    ErrorCode.STREAM_TIMEOUT,              # 5353: 스트림 타임아웃
    ErrorCode.CONNECTION_ERROR,             # 5901: 카메라 연결 실패
    ErrorCode.CAMERA_DISCONNECTED,          # 5902: 카메라 연결 끊김
    ErrorCode.CAMERA_TIMEOUT,              # 5903: 카메라 타임아웃
    ErrorCode.EXTERNAL_SERVICE_TIMEOUT,     # 6001: 외부 서비스 타임아웃
    ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE, # 6002: 외부 서비스 불가
    ErrorCode.CIRCUIT_BREAKER_OPEN,         # 5401: 서킷 브레이커 열림
    ErrorCode.ANALYSIS_TIMEOUT,             # 7001: 분석 타임아웃
    # GPU/Desktop (메모리, 온도, 전력은 자원 해제/쿨다운 후 재시도 가능)
    ErrorCode.GPU_MEMORY_ERROR,             # 5921: GPU 메모리 오류
    ErrorCode.GPU_MEMORY_ALLOCATION_FAILED, # 5922: GPU 메모리 할당 실패
    ErrorCode.GPU_MEMORY_FRAGMENTATION,     # 5923: GPU 메모리 단편화
    ErrorCode.GPU_TEMPERATURE_CRITICAL,     # 5927: GPU 온도 임계
    ErrorCode.GPU_POWER_LIMIT_EXCEEDED,     # 5928: GPU 전력 한계
    ErrorCode.MODEL_OPTIMIZATION_FAILED,    # 5931: 모델 최적화 실패
    # 멀티카메라 동기화 (프레임 드롭, 동기화, 버퍼는 재동기화 후 재시도 가능)
    ErrorCode.CAMERA_SYNC_ERROR,            # 5941: 카메라 동기화 실패
    ErrorCode.CAMERA_TIMESTAMP_DRIFT,       # 5942: 타임스탬프 드리프트
    ErrorCode.CAMERA_FRAME_DROP,            # 5943: 프레임 드롭
    ErrorCode.CAMERA_BUFFER_OVERFLOW,       # 5945: 버퍼 오버플로우
})


# =============================================================================
# CriticalException 심각도 범위 (base_exception.py 참조)
# =============================================================================

# 심각도 최소값 (낮을수록 덜 심각)
CRITICAL_SEVERITY_MIN: Final[int] = 1

# 심각도 최대값 (높을수록 더 심각 — 시스템 중단/알림 필수)
CRITICAL_SEVERITY_MAX: Final[int] = 5

# 심각도 기본값 (알림 발송 필수 수준)
CRITICAL_SEVERITY_DEFAULT: Final[int] = 5


# =============================================================================
# 에러 코드 카테고리별 그룹 (하위 호환성 및 편의성)
# =============================================================================

GENERAL_ERRORS: Final[tuple[ErrorCode, ...]] = (
    ErrorCode.UNKNOWN_ERROR,
    ErrorCode.INTERNAL_ERROR,
    ErrorCode.NOT_IMPLEMENTED,
    ErrorCode.SERVICE_UNAVAILABLE,
    ErrorCode.TIMEOUT_ERROR,
    ErrorCode.RATE_LIMIT_EXCEEDED,
)

AUTH_ERRORS: Final[tuple[ErrorCode, ...]] = (
    ErrorCode.AUTHENTICATION_REQUIRED,
    ErrorCode.AUTHENTICATION_FAILED,
    ErrorCode.TOKEN_EXPIRED,
    ErrorCode.TOKEN_INVALID,
    ErrorCode.PERMISSION_DENIED,
    ErrorCode.API_KEY_INVALID,
    ErrorCode.API_KEY_EXPIRED,
)

VALIDATION_ERRORS: Final[tuple[ErrorCode, ...]] = (
    ErrorCode.VALIDATION_ERROR,
    ErrorCode.INVALID_REQUEST,
    ErrorCode.MISSING_REQUIRED_FIELD,
    ErrorCode.INVALID_FIELD_TYPE,
    ErrorCode.INVALID_FIELD_VALUE,
    ErrorCode.INVALID_JSON_FORMAT,
    ErrorCode.INVALID_DATE_FORMAT,
    ErrorCode.VALUE_OUT_OF_RANGE,
    ErrorCode.STRING_TOO_LONG,
    ErrorCode.STRING_TOO_SHORT,
    ErrorCode.INVALID_ENUM_VALUE,
    # URL 검증
    ErrorCode.URL_VALIDATION_ERROR,
    ErrorCode.URL_INVALID_FORMAT,
    ErrorCode.URL_INVALID_SCHEME,
    ErrorCode.URL_BLOCKED_HOST,
    ErrorCode.URL_PRIVATE_IP,
    ErrorCode.URL_TOO_LONG,
    # 보안
    ErrorCode.SECURITY_ERROR,
    ErrorCode.SSRF_DETECTED,
    ErrorCode.DNS_REBINDING_DETECTED,
    ErrorCode.ENCRYPTION_ERROR,
    ErrorCode.ENCRYPTION_UNAVAILABLE,
    # 파일 포맷
    ErrorCode.FORMAT_DETECTION_ERROR,
    ErrorCode.UNSUPPORTED_FORMAT,
    ErrorCode.CORRUPTED_FILE,
    ErrorCode.INVALID_MAGIC_BYTES,
    ErrorCode.FORMAT_MISMATCH,
    # 포맷 검증
    ErrorCode.FORMAT_VALIDATION_ERROR,
    ErrorCode.FORMAT_NOT_ALLOWED,
    ErrorCode.CODEC_NOT_SUPPORTED,
    ErrorCode.BITRATE_OUT_OF_RANGE,
    ErrorCode.CONTAINER_FORMAT_ERROR,
    # 해상도
    ErrorCode.RESOLUTION_ERROR,
    ErrorCode.RESOLUTION_TOO_LOW,
    ErrorCode.RESOLUTION_TOO_HIGH,
    ErrorCode.RESOLUTION_NOT_SUPPORTED,
    ErrorCode.ASPECT_RATIO_NOT_SUPPORTED,
    # FPS/Duration
    ErrorCode.FPS_ERROR,
    ErrorCode.FPS_TOO_LOW,
    ErrorCode.FPS_TOO_HIGH,
    ErrorCode.DURATION_TOO_SHORT,
    ErrorCode.DURATION_TOO_LONG,
    # 데이터 품질
    ErrorCode.DATA_QUALITY_ERROR,
    ErrorCode.LOW_QUALITY_ERROR,
    ErrorCode.BRIGHTNESS_TOO_LOW,
    ErrorCode.BRIGHTNESS_TOO_HIGH,
    ErrorCode.CONTRAST_TOO_LOW,
    ErrorCode.NOISE_TOO_HIGH,
    ErrorCode.BLUR_TOO_HIGH,
    ErrorCode.SHARPNESS_TOO_LOW,
    ErrorCode.COLOR_SATURATION_ERROR,
    ErrorCode.EXPOSURE_ERROR,
    ErrorCode.MOTION_BLUR_DETECTED,
    ErrorCode.COMPRESSION_ARTIFACT,
    ErrorCode.QUALITY_CHECK_FAILED,
)

BUSINESS_ERRORS: Final[tuple[ErrorCode, ...]] = (
    ErrorCode.RESOURCE_NOT_FOUND,
    ErrorCode.RESOURCE_ALREADY_EXISTS,
    ErrorCode.RESOURCE_CONFLICT,
    ErrorCode.OPERATION_NOT_ALLOWED,
    ErrorCode.PRECONDITION_FAILED,
    ErrorCode.QUOTA_EXCEEDED,
)

INFRASTRUCTURE_ERRORS: Final[tuple[ErrorCode, ...]] = (
    # 데이터베이스
    ErrorCode.DATABASE_ERROR,
    ErrorCode.DATABASE_CONNECTION_FAILED,
    ErrorCode.DATABASE_QUERY_FAILED,
    ErrorCode.DATABASE_TRANSACTION_FAILED,
    ErrorCode.DATABASE_TIMEOUT,
    ErrorCode.DATABASE_INTEGRITY_ERROR,
    ErrorCode.DATABASE_RECORD_NOT_FOUND,
    # 캐시
    ErrorCode.CACHE_ERROR,
    ErrorCode.CACHE_CONNECTION_FAILED,
    ErrorCode.CACHE_OPERATION_FAILED,
    ErrorCode.CACHE_KEY_NOT_FOUND,
    ErrorCode.CACHE_SERIALIZATION_ERROR,
    # 큐
    ErrorCode.QUEUE_ERROR,
    ErrorCode.QUEUE_CONNECTION_FAILED,
    ErrorCode.QUEUE_PUBLISH_FAILED,
    ErrorCode.QUEUE_CONSUME_FAILED,
    ErrorCode.QUEUE_TIMEOUT,
    # 스토리지
    ErrorCode.STORAGE_ERROR,
    ErrorCode.STORAGE_CONNECTION_FAILED,
    ErrorCode.STORAGE_UPLOAD_FAILED,
    ErrorCode.STORAGE_DOWNLOAD_FAILED,
    ErrorCode.STORAGE_DELETE_FAILED,
    ErrorCode.STORAGE_FILE_NOT_FOUND,
    ErrorCode.STORAGE_QUOTA_EXCEEDED,
    ErrorCode.STORAGE_PERMISSION_DENIED,
    # 스트림
    ErrorCode.STREAM_ERROR,
    ErrorCode.STREAM_CONNECTION_FAILED,
    ErrorCode.STREAM_DISCONNECTED,
    ErrorCode.STREAM_TIMEOUT,
    ErrorCode.STREAM_INVALID_SOURCE,
    ErrorCode.STREAM_UNSUPPORTED_TYPE,
    ErrorCode.STREAM_BUFFER_OVERFLOW,
    ErrorCode.STREAM_DECODE_ERROR,
    ErrorCode.STREAM_FRAME_ERROR,
    ErrorCode.STREAM_AUTHENTICATION_FAILED,
    # 인프라 공통
    ErrorCode.INFRASTRUCTURE_ERROR,
    ErrorCode.CIRCUIT_BREAKER_OPEN,
    # 모델 레지스트리
    ErrorCode.MODEL_ALREADY_EXISTS,
    ErrorCode.MODEL_TYPE_NOT_SUPPORTED,
    ErrorCode.MODEL_PATH_NOT_FOUND,
    # 서비스 레지스트리
    ErrorCode.SERVICE_REGISTRY_ERROR,
    ErrorCode.SERVICE_ALREADY_EXISTS,
    ErrorCode.SERVICE_NOT_AVAILABLE,
    ErrorCode.SERVICE_CLASS_NOT_FOUND,
    # 파이프라인
    ErrorCode.PIPELINE_ERROR,
    ErrorCode.PIPELINE_CONFIG_NOT_FOUND,
    ErrorCode.STAGE_EXECUTION_FAILED,
    # 디코딩
    ErrorCode.DECODING_ERROR,
    ErrorCode.DECODING_INIT_FAILED,
    ErrorCode.DECODING_FRAME_FAILED,
    ErrorCode.DECODING_SEEK_FAILED,
    ErrorCode.DECODING_EOF,
    ErrorCode.CODEC_ERROR,
    ErrorCode.CODEC_NOT_FOUND,
    ErrorCode.CODEC_INIT_FAILED,
    ErrorCode.CORRUPTED_VIDEO,
    ErrorCode.CORRUPTED_FRAME,
    ErrorCode.HARDWARE_ACCEL_ERROR,
    ErrorCode.HARDWARE_ACCEL_NOT_AVAILABLE,
    # 프레임 추출
    ErrorCode.FRAME_EXTRACTION_ERROR,
    ErrorCode.FRAME_EXTRACTION_INIT_FAILED,
    ErrorCode.FRAME_EXTRACTION_TIMEOUT,
    ErrorCode.END_OF_STREAM,
    ErrorCode.KEYFRAME_DETECTION_FAILED,
    ErrorCode.SCENE_CHANGE_DETECTION_FAILED,
    ErrorCode.FRAME_BUFFER_OVERFLOW,
    ErrorCode.INVALID_FRAME_RANGE,
    # 비디오 정규화
    ErrorCode.NORMALIZATION_ERROR,
    ErrorCode.NORMALIZATION_INIT_FAILED,
    ErrorCode.VIDEO_RESOLUTION_CONVERSION_ERROR,
    ErrorCode.INVALID_TARGET_RESOLUTION,
    ErrorCode.UNSUPPORTED_TARGET_RESOLUTION,
    ErrorCode.FPS_CONVERSION_ERROR,
    ErrorCode.INVALID_FPS,
    ErrorCode.ASPECT_RATIO_ERROR,
    ErrorCode.INVALID_ASPECT_RATIO,
    ErrorCode.INTERPOLATION_ERROR,
    ErrorCode.COLOR_SPACE_CONVERSION_ERROR,
    ErrorCode.FORMAT_CONVERSION_ERROR,
    # 비디오 분류
    ErrorCode.CLASSIFICATION_ERROR,
    ErrorCode.CLASSIFICATION_INIT_FAILED,
    ErrorCode.CLASSIFICATION_TIMEOUT,
    ErrorCode.CLASSIFICATION_LOW_CONFIDENCE,
    ErrorCode.CLASSIFICATION_AMBIGUOUS,
    ErrorCode.CLASSIFICATION_UNSUPPORTED_FORMAT,
    ErrorCode.CLASSIFICATION_FEATURE_EXTRACTION_FAILED,
    ErrorCode.CLASSIFICATION_INVALID_VIDEO,
    ErrorCode.TRAINING_TYPE_DETECTION_FAILED,
    ErrorCode.GAME_TYPE_DETECTION_FAILED,
    # 적응형 샘플링
    ErrorCode.SAMPLING_ERROR,
    ErrorCode.SAMPLING_INIT_FAILED,
    ErrorCode.SAMPLING_CONFIG_INVALID,
    ErrorCode.MOTION_ANALYSIS_FAILED,
    ErrorCode.OPTICAL_FLOW_FAILED,
    ErrorCode.SAMPLING_RATE_INVALID,
    ErrorCode.INSUFFICIENT_FRAMES,
    ErrorCode.SAMPLING_TIMEOUT,
    # 카메라
    ErrorCode.CAMERA_ERROR,
    ErrorCode.CONNECTION_ERROR,
    ErrorCode.CAMERA_DISCONNECTED,
    ErrorCode.CAMERA_TIMEOUT,
    ErrorCode.CAMERA_NOT_FOUND,
    ErrorCode.CAMERA_NOT_REGISTERED,
    ErrorCode.CAMERA_ALREADY_REGISTERED,
    ErrorCode.CAMERA_MAX_EXCEEDED,
    ErrorCode.CAMERA_CALIBRATION_FAILED,
    ErrorCode.CAMERA_FRAME_ERROR,
    ErrorCode.CAMERA_PROTOCOL_ERROR,
    ErrorCode.CAMERA_SESSION_ERROR,
    # GPU/Desktop 하드웨어
    ErrorCode.GPU_ERROR,
    ErrorCode.GPU_MEMORY_ERROR,
    ErrorCode.GPU_MEMORY_ALLOCATION_FAILED,
    ErrorCode.GPU_MEMORY_FRAGMENTATION,
    ErrorCode.CUDA_ERROR,
    ErrorCode.CUDA_DEVICE_NOT_FOUND,
    ErrorCode.CUDA_DRIVER_ERROR,
    ErrorCode.GPU_TEMPERATURE_CRITICAL,
    ErrorCode.GPU_POWER_LIMIT_EXCEEDED,
    ErrorCode.GPU_COMPUTE_CAPABILITY_LOW,
    ErrorCode.TENSORRT_ERROR,
    ErrorCode.MODEL_OPTIMIZATION_FAILED,
    # 멀티카메라 동기화
    ErrorCode.MULTI_CAMERA_ERROR,
    ErrorCode.CAMERA_SYNC_ERROR,
    ErrorCode.CAMERA_TIMESTAMP_DRIFT,
    ErrorCode.CAMERA_FRAME_DROP,
    ErrorCode.CAMERA_SYNC_LOSS,
    ErrorCode.CAMERA_BUFFER_OVERFLOW,
    ErrorCode.CAMERA_GENLOCK_FAILED,
    ErrorCode.MULTI_VIEW_CALIBRATION_FAILED,
    ErrorCode.COORDINATE_TRANSFORM_FAILED,
)

EXTERNAL_ERRORS: Final[tuple[ErrorCode, ...]] = (
    ErrorCode.EXTERNAL_SERVICE_ERROR,
    ErrorCode.EXTERNAL_SERVICE_TIMEOUT,
    ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE,
    ErrorCode.WEBHOOK_DELIVERY_FAILED,
)

ANALYSIS_ERRORS: Final[tuple[ErrorCode, ...]] = (
    # 기본 분석
    ErrorCode.ANALYSIS_ERROR,
    ErrorCode.ANALYSIS_TIMEOUT,
    ErrorCode.ANALYSIS_CANCELLED,
    # 비디오
    ErrorCode.VIDEO_ERROR,
    ErrorCode.VIDEO_FORMAT_UNSUPPORTED,
    ErrorCode.VIDEO_TOO_LARGE,
    ErrorCode.VIDEO_TOO_LONG,
    ErrorCode.VIDEO_CORRUPTED,
    ErrorCode.VIDEO_DOWNLOAD_FAILED,
    ErrorCode.FRAME_EXTRACTION_FAILED,
    # 감지
    ErrorCode.DETECTION_ERROR,
    ErrorCode.DETECTION_NO_PERSON,
    ErrorCode.DETECTION_NO_BALL,
    ErrorCode.DETECTION_NO_COURT,
    ErrorCode.DETECTION_NO_HOOP,
    ErrorCode.DETECTION_MULTIPLE_PERSONS,
    ErrorCode.DETECTION_LOW_CONFIDENCE,
    # 포즈
    ErrorCode.POSE_ESTIMATION_ERROR,
    ErrorCode.POSE_ESTIMATION_FAILED,
    ErrorCode.POSE_INSUFFICIENT_KEYPOINTS,
    ErrorCode.POSE_OCCLUSION_DETECTED,
    # 생체역학
    ErrorCode.BIOMECHANICS_ERROR,
    ErrorCode.BIOMECHANICS_INVALID_ANGLE,
    ErrorCode.BIOMECHANICS_INVALID_VELOCITY,
    # 동작 분석
    ErrorCode.MOTION_ANALYSIS_ERROR,
    ErrorCode.MOTION_NOT_DETECTED,
    ErrorCode.MOTION_INSUFFICIENT_DATA,
    ErrorCode.SHOOTING_NOT_DETECTED,
    ErrorCode.DRIBBLING_NOT_DETECTED,
    # 경기 분석
    ErrorCode.GAME_ANALYSIS_ERROR,
    ErrorCode.GAME_INSUFFICIENT_DURATION,
    # 모델
    ErrorCode.MODEL_ERROR,
    ErrorCode.MODEL_LOAD_FAILED,
    ErrorCode.MODEL_INFERENCE_FAILED,
    ErrorCode.MODEL_NOT_FOUND,
    ErrorCode.MODEL_VERSION_MISMATCH,
    ErrorCode.MODEL_VERSION_NOT_FOUND,
    ErrorCode.MODEL_NOT_INITIALIZED,
    ErrorCode.MODEL_INITIALIZATION_FAILED,
    # 학습 시스템
    ErrorCode.LEARNING_ERROR,
    ErrorCode.PATTERN_LEARNING_FAILED,
    ErrorCode.FEEDBACK_COLLECTION_FAILED,
    ErrorCode.MODEL_ADAPTATION_FAILED,
    ErrorCode.LEARNING_SCHEDULER_ERROR,
    ErrorCode.PROFILE_LEARNING_FAILED,
    ErrorCode.VALIDATION_SPLIT_ERROR,
    ErrorCode.ACTIVE_LEARNING_ERROR,
    ErrorCode.LEARNING_HISTORY_ERROR,
    ErrorCode.INCREMENTAL_TRAINING_ERROR,
    ErrorCode.FEEDBACK_INTEGRATION_ERROR,
    ErrorCode.PERFORMANCE_TRACKING_ERROR,
    ErrorCode.CHECKPOINT_ERROR,
    ErrorCode.ROLLBACK_ERROR,
    ErrorCode.THRESHOLD_ADJUSTMENT_ERROR,
    ErrorCode.ACCURACY_MONITOR_ERROR,
    ErrorCode.DRIFT_DETECTION_ERROR,
    ErrorCode.CALIBRATION_ERROR,
    ErrorCode.EVALUATION_ERROR,
    ErrorCode.DATA_AUGMENTATION_ERROR,
    ErrorCode.FEATURE_STORE_ERROR,
    ErrorCode.LABELING_ERROR,
    ErrorCode.EXPERIMENT_TRACKING_ERROR,
    ErrorCode.AB_TEST_ERROR,
    ErrorCode.EXPLANATION_ERROR,
)

REFEREE_ERRORS: Final[tuple[ErrorCode, ...]] = (
    ErrorCode.REFEREE_ERROR,
    ErrorCode.REFEREE_RULE_NOT_FOUND,
    ErrorCode.REFEREE_INVALID_RULE_SET,
    ErrorCode.REFEREE_INSUFFICIENT_DATA,
    ErrorCode.REFEREE_LOW_CONFIDENCE,
    # 규칙 세트 관리 에러
    ErrorCode.RULE_SET_NOT_FOUND,
    ErrorCode.RULE_SET_VALIDATION_ERROR,
    ErrorCode.RULE_SET_VERSION_MISMATCH,
    ErrorCode.RULE_SET_LOAD_ERROR,
    ErrorCode.RULE_SET_SCHEMA_ERROR,
)

CONFIGURATION_ERRORS: Final[tuple[ErrorCode, ...]] = (
    ErrorCode.CONFIGURATION_ERROR,
    ErrorCode.CONFIGURATION_NOT_FOUND,
    ErrorCode.CONFIGURATION_INVALID,
    ErrorCode.CONFIGURATION_LOAD_FAILED,
)

SYSTEM_ERRORS: Final[tuple[ErrorCode, ...]] = (
    # 설정
    ErrorCode.CONFIGURATION_ERROR,
    ErrorCode.CONFIGURATION_NOT_FOUND,
    ErrorCode.CONFIGURATION_INVALID,
    ErrorCode.CONFIGURATION_LOAD_FAILED,
    # 초기화/종료
    ErrorCode.INITIALIZATION_ERROR,
    ErrorCode.SHUTDOWN_ERROR,
    # 의존성
    ErrorCode.DEPENDENCY_ERROR,
    ErrorCode.CIRCULAR_DEPENDENCY,
    ErrorCode.MISSING_DEPENDENCY,
)


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 에러 카테고리 (정의서 필수 항목)
    "ErrorCategory",
    # 에러 코드 (정의서 필수 항목)
    "ErrorCode",
    # 캐시 (O(1) 조회)
    "ERROR_CODE_LOOKUP",
    "RETRYABLE_ERRORS",
    # CriticalException 심각도 범위
    "CRITICAL_SEVERITY_MIN",
    "CRITICAL_SEVERITY_MAX",
    "CRITICAL_SEVERITY_DEFAULT",
    # 카테고리별 그룹 (하위 호환성)
    "GENERAL_ERRORS",
    "AUTH_ERRORS",
    "VALIDATION_ERRORS",
    "BUSINESS_ERRORS",
    "INFRASTRUCTURE_ERRORS",
    "EXTERNAL_ERRORS",
    "ANALYSIS_ERRORS",
    "REFEREE_ERRORS",
    "CONFIGURATION_ERRORS",
    "SYSTEM_ERRORS",
]

# 모듈 버전 정보
__version__ = "1.0.0"
