# -*- coding: utf-8 -*-
"""
COURTVIEW Desktop - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: logger.py
설명: Loguru 기반 중앙 로깅 시스템 (Desktop Edition)

작성자: SPOIN_COURTVIEW
버전: 1.0.0
최종 수정: 2026-03-11

주요 기능:
    - Loguru 기반 구조화 로깅 (JSON 지원)
    - 표준 logging 라이브러리 인터셉트 (기존 모듈 호환)
    - 파일 로테이션 (크기/시간 기반)
    - 에러 전용 로그 파일 분리
    - 분석/성능 전용 로그 파일
    - 민감 정보 자동 마스킹
    - 모듈별 로그 레벨 설정
    - ConfigLoader YAML 설정 연동
    - 스레드 안전 설계
    - Singleton 패턴

Desktop Edition 특화:
    - 외부 서비스 연동 제거 (Sentry, CloudWatch, ELK)
    - API 액세스 로그 제거 (Desktop은 API 서버 없음)
    - GPU/분석 성능 로그 포함
    - 로컬 파일 로테이션만 사용
    - Windows 경로 호환

설계 원칙:
    - 순환 참조 방지: ConfigLoader만 의존
    - 스레드 안전: RLock 사용
    - 메모리 효율: 로테이션 + 보관 기간 제한
    - 호환성: 기존 logging.getLogger() 코드 변경 불필요
    - 확장성: 커스텀 싱크 등록 가능

사용 예시:
    # 앱 시작 시 초기화 (1회)
    from core_foundation.monitoring.logger import setup_logging
    setup_logging()

    # 기존 모듈에서는 변경 없이 사용
    import logging
    logger = logging.getLogger(__name__)
    logger.info("이 로그는 자동으로 Loguru로 전달됩니다")

    # Loguru 직접 사용
    from core_foundation.monitoring.logger import get_logger
    log = get_logger("my_module")
    log.info("직접 Loguru 사용")
"""

from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import atexit
import logging
import re
import sys
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

# ============================================================
# 선택적 임포트: Loguru
# ============================================================
try:
    from loguru import logger as _loguru_logger
    LOGURU_AVAILABLE = True
except ImportError:
    _loguru_logger = None
    LOGURU_AVAILABLE = False

# ============================================================
# core_foundation 내부 임포트
# ============================================================
from core_foundation.config.loader import ConfigLoader

# ============================================================
# 표준 로거 (logger.py 자체용, Loguru 초기화 전 사용)
# ============================================================
_module_logger = logging.getLogger(__name__)

# ============================================================
# 상수 정의
# ============================================================
# 기본 로그 레벨
DEFAULT_LOG_LEVEL: str = "INFO"

# 기본 로그 디렉토리
DEFAULT_LOG_DIR: str = "logs"

# 기본 로그 포맷 (Loguru 스타일)
DEFAULT_LOG_FORMAT: str = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

# 파일용 로그 포맷 (색상 없음)
DEFAULT_FILE_FORMAT: str = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{name}:{function}:{line} | "
    "{message}"
)

# JSON 로그 포맷 키
JSON_LOG_KEYS: list[str] = [
    "timestamp", "level", "module", "function", "line", "message",
]

# 파일 로테이션 기본값
DEFAULT_ROTATION_SIZE: str = "10 MB"
DEFAULT_RETENTION: str = "30 days"
DEFAULT_COMPRESSION: str = "gz"
DEFAULT_ENCODING: str = "utf-8"

# 에러 로그 기본값
ERROR_ROTATION_SIZE: str = "10 MB"
ERROR_RETENTION: str = "90 days"

# 분석 로그 기본값
ANALYSIS_ROTATION_SIZE: str = "50 MB"
ANALYSIS_RETENTION: str = "180 days"

# 성능 로그 기본값
PERFORMANCE_ROTATION_SIZE: str = "50 MB"
PERFORMANCE_RETENTION: str = "30 days"

# 민감 정보 마스킹 패턴
DEFAULT_SENSITIVE_PATTERNS: list[str] = [
    "password",
    "secret",
    "token",
    "api_key",
    "access_key",
    "secret_key",
    "credential",
    "private_key",
]

# 마스킹 치환 값
MASK_VALUE: str = "***MASKED***"

# stdlib 로깅 레벨 → Loguru 레벨 매핑
STDLIB_LEVEL_MAP: dict[int, str] = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}

# 기본 서드파티 라이브러리 로그 억제
DEFAULT_THIRD_PARTY_LEVELS: dict[str, str] = {
    "watchdog": "WARNING",
    "pydantic": "WARNING",
    "PIL": "WARNING",
    "torch": "WARNING",
    "ultralytics": "WARNING",
    "cv2": "WARNING",
    "numpy": "WARNING",
    "matplotlib": "WARNING",
    "urllib3": "WARNING",
    "filelock": "WARNING",
}


# ============================================================
# Enum 정의
# ============================================================
class LogLevel(Enum):
    """
    로그 레벨.

    Loguru 및 표준 logging과 호환되는 레벨 정의.

    Attributes:
        TRACE: 최상세 (Loguru 전용)
        DEBUG: 디버그
        INFO: 정보
        SUCCESS: 성공 (Loguru 전용)
        WARNING: 경고
        ERROR: 에러
        CRITICAL: 심각
    """

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_string(cls, level_str: str) -> "LogLevel":
        """문자열에서 LogLevel 변환."""
        normalized = level_str.upper().strip()
        try:
            return cls(normalized)
        except ValueError:
            return cls.INFO

    def to_stdlib_level(self) -> int:
        """표준 logging 레벨로 변환."""
        mapping = {
            "TRACE": logging.DEBUG,
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "SUCCESS": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return mapping.get(self.value, logging.INFO)


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class SinkConfig:
    """
    로그 싱크(출력 대상) 설정.

    Attributes:
        name: 싱크 이름 (식별용)
        enabled: 활성화 여부
        path: 파일 경로 (콘솔이면 None)
        level: 최소 로그 레벨
        format: 로그 포맷
        rotation: 로테이션 설정 (크기 또는 시간, 예: "10 MB", "00:00")
        retention: 보관 기간 (예: "30 days", "10")
        compression: 압축 방식 (예: "gz", "zip")
        encoding: 파일 인코딩
        serialize: JSON 직렬화 여부
        filter_func: 필터 함수 (None이면 필터 없음)
    """

    name: str = "default"
    enabled: bool = True
    path: str | None = None
    level: str = "DEBUG"
    format: str = DEFAULT_FILE_FORMAT
    rotation: str | None = DEFAULT_ROTATION_SIZE
    retention: str | None = DEFAULT_RETENTION
    compression: str | None = DEFAULT_COMPRESSION
    encoding: str = DEFAULT_ENCODING
    serialize: bool = False
    filter_func: Callable | None = None


@dataclass(slots=True)
class LoggingConfig:
    """
    로깅 전체 설정.

    Attributes:
        level: 기본 로그 레벨
        log_dir: 로그 디렉토리 경로
        console_enabled: 콘솔 출력 여부
        console_level: 콘솔 로그 레벨
        console_colorize: 색상 출력 여부
        console_format: 콘솔 포맷
        file_enabled: 파일 출력 여부
        error_file_enabled: 에러 전용 파일 여부
        analysis_file_enabled: 분석 로그 파일 여부
        performance_file_enabled: 성능 로그 파일 여부
        json_format: JSON 포맷 사용 여부
        sensitive_masking: 민감 정보 마스킹 여부
        sensitive_patterns: 마스킹 대상 패턴
        module_levels: 모듈별 로그 레벨
        third_party_levels: 서드파티 라이브러리 로그 레벨
        intercept_stdlib: 표준 logging 인터셉트 여부
    """

    level: str = DEFAULT_LOG_LEVEL
    log_dir: str = DEFAULT_LOG_DIR
    console_enabled: bool = True
    console_level: str = "INFO"
    console_colorize: bool = True
    console_format: str = DEFAULT_LOG_FORMAT
    file_enabled: bool = True
    error_file_enabled: bool = True
    analysis_file_enabled: bool = True
    performance_file_enabled: bool = True
    json_format: bool = False
    sensitive_masking: bool = True
    sensitive_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_SENSITIVE_PATTERNS))
    module_levels: dict[str, str] = field(default_factory=dict)
    third_party_levels: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_THIRD_PARTY_LEVELS)
    )
    intercept_stdlib: bool = True


# ============================================================
# 표준 logging → Loguru 인터셉트 핸들러
# ============================================================
class InterceptHandler(logging.Handler):
    """
    표준 logging 라이브러리를 Loguru로 리다이렉트하는 핸들러.

    기존 코드에서 `logging.getLogger(__name__)` 방식으로 사용하던 로그를
    변경 없이 Loguru 파이프라인으로 전달합니다.

    참고:
        - logging.basicConfig() 대신 이 핸들러를 루트 로거에 등록
        - Loguru의 싱크 설정이 최종 출력을 결정
    """

    def emit(self, record: logging.LogRecord) -> None:
        """logging.LogRecord를 Loguru로 전달."""
        if not LOGURU_AVAILABLE:
            return

        # Loguru 레벨 결정
        try:
            level = _loguru_logger.level(record.levelname).name
        except ValueError:
            level = STDLIB_LEVEL_MAP.get(record.levelno, "INFO")

        # 호출자 프레임 탐색 (logging 내부 프레임 스킵)
        frame = sys._getframe(6)
        depth = 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# ============================================================
# 민감 정보 마스킹 필터
# ============================================================
class SensitiveDataFilter:
    """
    로그 메시지 내 민감 정보 마스킹.

    지정된 패턴이 포함된 key=value 또는 JSON 형태의 민감 데이터를
    자동으로 마스킹합니다.

    Attributes:
        patterns: 마스킹 대상 키 패턴 (대소문자 무시)
        mask_value: 치환 값
    """

    def __init__(
        self,
        patterns: list[str] | None = None,
        mask_value: str = MASK_VALUE,
    ) -> None:
        """초기화."""
        self._patterns = patterns or DEFAULT_SENSITIVE_PATTERNS
        self._mask_value = mask_value
        # 패턴을 정규식으로 컴파일 (key=value, key: value, "key": "value" 형식)
        pattern_group = "|".join(re.escape(p) for p in self._patterns)
        self._regex = re.compile(
            rf'({pattern_group})'
            rf'(\s*[=:]\s*)'
            rf'(["\']?)([^"\',\s\}}\]]*)\3',
            re.IGNORECASE,
        )

    def __call__(self, record: dict[str, Any]) -> bool:
        """
        Loguru 필터/패치 함수.

        레코드의 메시지를 마스킹 처리합니다.

        Args:
            record: Loguru 레코드 딕셔너리

        Returns:
            True (항상 통과, 메시지만 수정)
        """
        message = record.get("message", "")
        if message and any(p.lower() in message.lower() for p in self._patterns):
            record["message"] = self._regex.sub(
                rf'\1\2\3{self._mask_value}\3',
                message,
            )
        return True

    def mask_string(self, text: str) -> str:
        """문자열 내 민감 정보 마스킹 (유틸리티)."""
        return self._regex.sub(
            rf'\1\2\3{self._mask_value}\3',
            text,
        )


# ============================================================
# 분석/성능 로그 필터
# ============================================================
def _analysis_filter(record: dict[str, Any]) -> bool:
    """분석 로그 필터 - analysis 태그가 있는 로그만 통과."""
    extra = record.get("extra", {})
    return extra.get("log_type") == "analysis"


def _performance_filter(record: dict[str, Any]) -> bool:
    """성능 로그 필터 - performance 태그가 있는 로그만 통과."""
    extra = record.get("extra", {})
    return extra.get("log_type") == "performance"


def _error_filter(record: dict[str, Any]) -> bool:
    """에러 이상 레벨만 통과."""
    return record["level"].no >= 40  # ERROR = 40


# ============================================================
# 메인 클래스: LogManager
# ============================================================
class LogManager:
    """
    중앙 로그 관리자.

    Loguru 기반 로깅 시스템을 초기화하고 관리합니다.
    Singleton 패턴으로 애플리케이션 전체에서 하나의 인스턴스를 공유합니다.

    주요 기능:
        - Loguru 싱크 설정 (콘솔, 파일, 에러, 분석, 성능)
        - 표준 logging 인터셉트 설치
        - 모듈별 로그 레벨 관리
        - 민감 정보 마스킹
        - 런타임 레벨 변경

    Attributes:
        config: 로깅 설정
        initialized: 초기화 완료 여부

    Example:
        >>> manager = LogManager(config_loader)
        >>> manager.setup()
        >>> log = manager.get_logger("my_module")
        >>> log.info("Hello from Desktop!")
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        config: LoggingConfig | None = None,
    ) -> None:
        """
        LogManager 초기화.

        Args:
            config_loader: 설정 로더 (None이면 싱글톤 사용)
            config: 직접 설정 (None이면 YAML에서 로드)
        """
        self._config_loader = config_loader
        self._config = config or LoggingConfig()
        self._lock = threading.RLock()
        self._initialized = False
        self._sink_ids: dict[str, int] = {}  # 싱크 이름 → Loguru 싱크 ID
        self._sensitive_filter: SensitiveDataFilter | None = None
        self._original_handlers: list[logging.Handler] = []

    @property
    def initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    def __repr__(self) -> str:
        """LogManager 인스턴스 표현."""
        return (
            f"LogManager(initialized={self._initialized}, "
            f"level={self._config.level!r}, "
            f"sinks={list(self._sink_ids.keys())})"
        )

    @property
    def config(self) -> LoggingConfig:
        """현재 로깅 설정."""
        return self._config

    def setup(self) -> None:
        """
        로깅 시스템 초기화.

        1. YAML 설정 로드 (config_loader 사용 시)
        2. Loguru 싱크 초기화 (기존 싱크 제거)
        3. 콘솔 싱크 설정
        4. 파일 싱크 설정 (일반, 에러, 분석, 성능)
        5. 민감 정보 마스킹 설정
        6. 표준 logging 인터셉트 설치
        7. 모듈별 로그 레벨 설정
        """
        with self._lock:
            if not LOGURU_AVAILABLE:
                _module_logger.warning(
                    "Loguru가 설치되지 않았습니다. 표준 logging만 사용합니다. "
                    "설치: pip install loguru"
                )
                self._setup_stdlib_fallback()
                self._initialized = True
                return

            # 1. YAML 설정 로드
            if self._config_loader:
                self._load_config_from_yaml()

            # 2. 기존 Loguru 싱크 모두 제거
            _loguru_logger.remove()
            self._sink_ids.clear()

            # 3. 민감 정보 필터 설정
            if self._config.sensitive_masking:
                self._sensitive_filter = SensitiveDataFilter(
                    patterns=self._config.sensitive_patterns,
                )

            # 4. 로그 디렉토리 생성
            log_dir = Path(self._config.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)

            # 5. 콘솔 싱크
            if self._config.console_enabled:
                self._add_console_sink()

            # 6. 파일 싱크
            if self._config.file_enabled:
                self._add_file_sink(
                    name="general",
                    path=str(log_dir / "courtview.log"),
                    level="DEBUG",
                    rotation=DEFAULT_ROTATION_SIZE,
                    retention=DEFAULT_RETENTION,
                )

            # 7. 에러 전용 파일 싱크
            if self._config.error_file_enabled:
                self._add_file_sink(
                    name="error",
                    path=str(log_dir / "courtview_error.log"),
                    level="ERROR",
                    rotation=ERROR_ROTATION_SIZE,
                    retention=ERROR_RETENTION,
                    filter_func=_error_filter,
                )

            # 8. 분석 로그 파일 싱크
            if self._config.analysis_file_enabled:
                self._add_file_sink(
                    name="analysis",
                    path=str(log_dir / "analysis.log"),
                    level="INFO",
                    rotation=ANALYSIS_ROTATION_SIZE,
                    retention=ANALYSIS_RETENTION,
                    filter_func=_analysis_filter,
                )

            # 9. 성능 로그 파일 싱크
            if self._config.performance_file_enabled:
                self._add_file_sink(
                    name="performance",
                    path=str(log_dir / "performance.log"),
                    level="INFO",
                    rotation=PERFORMANCE_ROTATION_SIZE,
                    retention=PERFORMANCE_RETENTION,
                    filter_func=_performance_filter,
                )

            # 10. 표준 logging 인터셉트
            if self._config.intercept_stdlib:
                self._install_intercept()

            # 11. 모듈별 로그 레벨 설정
            self._apply_module_levels()

            # 12. 서드파티 라이브러리 레벨 설정
            self._apply_third_party_levels()

            # 종료 시 정리 등록
            atexit.register(self.shutdown)

            self._initialized = True
            _loguru_logger.info(
                f"LogManager 초기화 완료 "
                f"(log_dir={self._config.log_dir}, "
                f"level={self._config.level}, "
                f"sinks={list(self._sink_ids.keys())})"
            )

    def _load_config_from_yaml(self) -> None:
        """ConfigLoader에서 로깅 설정 로드."""
        try:
            loader = self._config_loader or ConfigLoader.get_instance()

            self._config.level = loader.get_str(
                "logging.level", self._config.level
            )
            self._config.log_dir = loader.get_str(
                "logging.log_dir", self._config.log_dir
            )
            self._config.json_format = loader.get_bool(
                "logging.json_format", self._config.json_format
            )
            self._config.console_enabled = loader.get_bool(
                "console.enabled", self._config.console_enabled
            )
            self._config.console_level = loader.get_str(
                "console.level", self._config.console_level
            )
            self._config.console_colorize = loader.get_bool(
                "console.colorize", self._config.console_colorize
            )
            self._config.file_enabled = loader.get_bool(
                "file.enabled", self._config.file_enabled
            )
            self._config.error_file_enabled = loader.get_bool(
                "error_file.enabled", self._config.error_file_enabled
            )
            self._config.analysis_file_enabled = loader.get_bool(
                "analysis_log.enabled", self._config.analysis_file_enabled
            )
            self._config.performance_file_enabled = loader.get_bool(
                "performance_log.enabled", self._config.performance_file_enabled
            )
            self._config.sensitive_masking = loader.get_bool(
                "filters.sensitive_data.enabled", self._config.sensitive_masking
            )

            # 마스킹 패턴
            patterns = loader.get_list(
                "filters.sensitive_data.patterns", None
            )
            if patterns:
                self._config.sensitive_patterns = patterns

            # 모듈별 레벨
            loggers_config = loader.get_dict("loggers", {})
            if isinstance(loggers_config, dict):
                for module_name, level_config in loggers_config.items():
                    if isinstance(level_config, dict):
                        level = level_config.get("level", "INFO")
                    else:
                        level = str(level_config)
                    self._config.module_levels[module_name] = level

        except Exception as e:
            _module_logger.warning(f"로깅 설정 YAML 로드 실패, 기본값 사용: {e}")

    def _add_console_sink(self) -> None:
        """콘솔 싱크 추가."""
        sink_format = self._config.console_format
        # serialize=True 시 Loguru가 포맷을 무시하므로 기본 포맷 유지
        # (Loguru는 format=None을 거부하므로 항상 유효한 문자열 전달)

        patched_filter = self._sensitive_filter if self._config.sensitive_masking else None

        sink_id = _loguru_logger.add(
            sys.stderr,
            level=self._config.console_level,
            format=sink_format,
            colorize=self._config.console_colorize,
            serialize=self._config.json_format,
            filter=patched_filter,
        )
        self._sink_ids["console"] = sink_id

    def _add_file_sink(
        self,
        name: str,
        path: str,
        level: str = "DEBUG",
        rotation: str | None = None,
        retention: str | None = None,
        filter_func: Callable | None = None,
    ) -> None:
        """파일 싱크 추가."""
        # 민감 정보 필터와 사용자 필터 결합
        combined_filter = None
        if self._config.sensitive_masking and filter_func:
            # 두 필터 모두 적용
            sensitive = self._sensitive_filter

            def combined_filter(record: dict[str, Any]) -> bool:
                return sensitive(record) and filter_func(record)
        elif self._config.sensitive_masking:
            combined_filter = self._sensitive_filter
        elif filter_func:
            combined_filter = filter_func

        file_format = DEFAULT_FILE_FORMAT
        # serialize=True 시 Loguru가 포맷을 무시하므로 기본 포맷 유지
        # (Loguru는 format=None을 거부하므로 항상 유효한 문자열 전달)

        sink_id = _loguru_logger.add(
            path,
            level=level,
            format=file_format,
            rotation=rotation,
            retention=retention,
            compression=DEFAULT_COMPRESSION,
            encoding=DEFAULT_ENCODING,
            serialize=self._config.json_format,
            filter=combined_filter,
            enqueue=True,  # 스레드 안전 비동기 쓰기
        )
        self._sink_ids[name] = sink_id

    def _install_intercept(self) -> None:
        """표준 logging → Loguru 인터셉트 설치."""
        # 루트 로거의 기존 핸들러 백업 및 교체
        root_logger = logging.root
        self._original_handlers = list(root_logger.handlers)

        # 기존 핸들러 제거
        root_logger.handlers.clear()

        # InterceptHandler 설치
        root_logger.addHandler(InterceptHandler())

        # 루트 로거 레벨을 DEBUG로 설정 (Loguru가 최종 필터링)
        root_logger.setLevel(logging.DEBUG)

    def _apply_module_levels(self) -> None:
        """모듈별 로그 레벨 적용 (표준 logging 로거에)."""
        for module_name, level_str in self._config.module_levels.items():
            level = LogLevel.from_string(level_str)
            stdlib_logger = logging.getLogger(module_name)
            stdlib_logger.setLevel(level.to_stdlib_level())

    def _apply_third_party_levels(self) -> None:
        """서드파티 라이브러리 로그 레벨 적용."""
        for lib_name, level_str in self._config.third_party_levels.items():
            level = LogLevel.from_string(level_str)
            stdlib_logger = logging.getLogger(lib_name)
            stdlib_logger.setLevel(level.to_stdlib_level())

    def _setup_stdlib_fallback(self) -> None:
        """Loguru가 없을 때 표준 logging 기본 설정."""
        log_dir = Path(self._config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # 기본 포맷
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - "
            "[%(filename)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 루트 로거 설정
        root_logger = logging.root
        root_logger.setLevel(logging.DEBUG)

        # 콘솔 핸들러
        if self._config.console_enabled:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(
                getattr(logging, self._config.console_level, logging.INFO)
            )
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        # 파일 핸들러
        if self._config.file_enabled:
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                str(log_dir / "courtview.log"),
                maxBytes=10 * 1024 * 1024,
                backupCount=10,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            # 에러 전용
            if self._config.error_file_enabled:
                error_handler = RotatingFileHandler(
                    str(log_dir / "courtview_error.log"),
                    maxBytes=10 * 1024 * 1024,
                    backupCount=30,
                    encoding="utf-8",
                )
                error_handler.setLevel(logging.ERROR)
                error_handler.setFormatter(formatter)
                root_logger.addHandler(error_handler)

    # --------------------------------------------------------
    # 공개 API
    # --------------------------------------------------------
    def get_logger(self, name: str | None = None) -> Any:
        """
        이름이 바인딩된 Loguru 로거 반환.

        Args:
            name: 모듈/컴포넌트 이름 (None이면 기본 로거)

        Returns:
            Loguru logger (bind된) 또는 표준 logging.Logger (fallback)
        """
        if LOGURU_AVAILABLE:
            if name:
                return _loguru_logger.bind(name=name)
            return _loguru_logger
        else:
            return logging.getLogger(name or "courtview")

    def set_level(self, level: str, module: str | None = None) -> None:
        """
        로그 레벨 런타임 변경.

        Args:
            level: 새 로그 레벨 (예: "DEBUG", "INFO")
            module: 대상 모듈 (None이면 전체)
        """
        with self._lock:
            log_level = LogLevel.from_string(level)

            if module:
                # 특정 모듈
                self._config.module_levels[module] = level
                stdlib_logger = logging.getLogger(module)
                stdlib_logger.setLevel(log_level.to_stdlib_level())
            else:
                # 전체
                self._config.level = level
                logging.root.setLevel(log_level.to_stdlib_level())

    def add_sink(self, sink_config: SinkConfig) -> int | None:
        """
        커스텀 싱크 추가.

        Args:
            sink_config: 싱크 설정

        Returns:
            싱크 ID (제거 시 사용) 또는 None
        """
        if not LOGURU_AVAILABLE or not sink_config.enabled:
            return None

        with self._lock:
            # serialize=True 시 Loguru가 포맷을 무시하므로 기본 포맷 유지
            # (Loguru는 format=None을 거부하므로 항상 유효한 문자열 전달)
            if sink_config.path:
                # 파일 싱크
                sink_id = _loguru_logger.add(
                    sink_config.path,
                    level=sink_config.level,
                    format=sink_config.format,
                    rotation=sink_config.rotation,
                    retention=sink_config.retention,
                    compression=sink_config.compression,
                    encoding=sink_config.encoding,
                    serialize=sink_config.serialize,
                    filter=sink_config.filter_func,
                    enqueue=True,
                )
            else:
                # 콘솔 싱크
                sink_id = _loguru_logger.add(
                    sys.stderr,
                    level=sink_config.level,
                    format=sink_config.format,
                    serialize=sink_config.serialize,
                    filter=sink_config.filter_func,
                )

            self._sink_ids[sink_config.name] = sink_id
            return sink_id

    def remove_sink(self, name: str) -> bool:
        """
        싱크 제거.

        Args:
            name: 싱크 이름

        Returns:
            제거 성공 여부
        """
        if not LOGURU_AVAILABLE:
            return False

        with self._lock:
            sink_id = self._sink_ids.pop(name, None)
            if sink_id is not None:
                try:
                    _loguru_logger.remove(sink_id)
                    return True
                except ValueError:
                    return False
            return False

    def get_status(self) -> dict[str, Any]:
        """
        로깅 시스템 상태 조회.

        Returns:
            상태 딕셔너리
        """
        return {
            "initialized": self._initialized,
            "loguru_available": LOGURU_AVAILABLE,
            "level": self._config.level,
            "log_dir": self._config.log_dir,
            "active_sinks": list(self._sink_ids.keys()),
            "sink_count": len(self._sink_ids),
            "console_enabled": self._config.console_enabled,
            "file_enabled": self._config.file_enabled,
            "json_format": self._config.json_format,
            "sensitive_masking": self._config.sensitive_masking,
            "intercept_stdlib": self._config.intercept_stdlib,
            "module_levels": dict(self._config.module_levels),
        }

    def shutdown(self) -> None:
        """
        로깅 시스템 종료 (리소스 정리).

        모든 싱크를 플러시하고 제거합니다.
        표준 logging 핸들러를 원래 상태로 복원합니다.
        """
        with self._lock:
            if not self._initialized:
                return

            if LOGURU_AVAILABLE:
                # 모든 싱크 제거 (완료 대기)
                _loguru_logger.complete()
                _loguru_logger.remove()
                self._sink_ids.clear()

            # 표준 logging 핸들러 복원
            root_logger = logging.root
            root_logger.handlers.clear()
            for handler in self._original_handlers:
                root_logger.addHandler(handler)

            self._initialized = False


# ============================================================
# 싱글톤 인스턴스 관리
# ============================================================
_manager_instance: LogManager | None = None
_manager_lock: threading.Lock = threading.Lock()


def _get_manager() -> LogManager:
    """전역 LogManager 인스턴스 반환."""
    global _manager_instance

    if _manager_instance is None:
        with _manager_lock:
            if _manager_instance is None:
                _manager_instance = LogManager()

    return _manager_instance


def _reset_manager() -> None:
    """전역 LogManager 인스턴스 리셋 (테스트용)."""
    global _manager_instance

    with _manager_lock:
        if _manager_instance and _manager_instance.initialized:
            _manager_instance.shutdown()
        _manager_instance = None


# ============================================================
# 헬퍼 함수
# ============================================================
def setup_logging(
    config_loader: ConfigLoader | None = None,
    config: LoggingConfig | None = None,
    log_dir: str | None = None,
    level: str | None = None,
    json_format: bool = False,
) -> LogManager:
    """
    로깅 시스템 초기화 헬퍼 함수.

    애플리케이션 시작 시 1회 호출합니다.
    이미 초기화된 경우 기존 인스턴스를 반환합니다.

    Args:
        config_loader: 설정 로더 (None이면 기본값 사용)
        config: 직접 설정 (None이면 YAML에서 로드)
        log_dir: 로그 디렉토리 경로 (config보다 우선)
        level: 기본 로그 레벨 (config보다 우선)
        json_format: JSON 포맷 사용 여부

    Returns:
        LogManager 인스턴스

    Example:
        >>> setup_logging()  # 기본값
        >>> setup_logging(log_dir="./my_logs", level="DEBUG")
        >>> setup_logging(config_loader=my_loader, json_format=True)
    """
    global _manager_instance

    with _manager_lock:
        if _manager_instance and _manager_instance.initialized:
            return _manager_instance

        # 설정 구성
        if config is None:
            config = LoggingConfig()

        # 오버라이드 적용
        if log_dir:
            config.log_dir = log_dir
        if level:
            config.level = level
        if json_format:
            config.json_format = True

        _manager_instance = LogManager(
            config_loader=config_loader,
            config=config,
        )
        _manager_instance.setup()

        return _manager_instance


def get_logger(name: str | None = None) -> Any:
    """
    로거 인스턴스 반환 헬퍼 함수.

    LogManager가 초기화되지 않은 경우 표준 logging.Logger를 반환합니다.

    Args:
        name: 모듈/컴포넌트 이름

    Returns:
        Loguru logger 또는 표준 logging.Logger

    Example:
        >>> log = get_logger("motion_analysis.shooting")
        >>> log.info("슛 분석 시작")
    """
    manager = _get_manager()
    if manager.initialized:
        return manager.get_logger(name)

    # 미초기화 시 표준 로거 반환
    return logging.getLogger(name or "courtview")


def log_analysis(message: str, **kwargs: Any) -> None:
    """
    분석 로그 기록 헬퍼.

    analysis.log에 기록됩니다.

    Args:
        message: 로그 메시지
        **kwargs: 추가 컨텍스트 (analysis_id, video_id 등)

    Example:
        >>> log_analysis("슛 분석 완료", analysis_id="abc123", accuracy=0.95)
    """
    if LOGURU_AVAILABLE:
        _loguru_logger.bind(log_type="analysis", **kwargs).info(message)
    else:
        logging.getLogger("courtview.analysis").info(f"{message} | {kwargs}")


def log_performance(message: str, **kwargs: Any) -> None:
    """
    성능 로그 기록 헬퍼.

    performance.log에 기록됩니다.

    Args:
        message: 로그 메시지
        **kwargs: 메트릭 정보 (fps, latency_ms, memory_mb 등)

    Example:
        >>> log_performance("프레임 처리", fps=60.5, latency_ms=16.2)
    """
    if LOGURU_AVAILABLE:
        _loguru_logger.bind(log_type="performance", **kwargs).info(message)
    else:
        logging.getLogger("courtview.performance").info(f"{message} | {kwargs}")


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # 상수
    "LOGURU_AVAILABLE",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_LOG_DIR",
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_FILE_FORMAT",
    "DEFAULT_ROTATION_SIZE",
    "DEFAULT_RETENTION",
    "DEFAULT_SENSITIVE_PATTERNS",
    "MASK_VALUE",
    # Enum
    "LogLevel",
    # 데이터 클래스
    "SinkConfig",
    "LoggingConfig",
    # 핸들러/필터
    "InterceptHandler",
    "SensitiveDataFilter",
    # 메인 클래스
    "LogManager",
    # 헬퍼 함수
    "setup_logging",
    "get_logger",
    "log_analysis",
    "log_performance",
    # 유틸리티 (테스트용)
    "_get_manager",
    "_reset_manager",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
