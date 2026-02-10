"""
core_foundation/monitoring/logger.py - 엔터프라이즈급 구조화된 로깅

중앙화된 로깅 시스템:
- 구조화된 로깅 (JSON)
- 계층적 로거 관리
- 비동기 로깅 (선택)
- 민감 정보 필터링
- 예외 통합 (CourtViewError)
- 다중 출력 (콘솔, 파일, 회전)

Author: COURTVIEW Team
Version: 1.0.0
"""

import os
import sys
import json
import re
import gzip
import threading
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Union, TextIO
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod
from queue import Queue, Empty
import traceback as tb

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


# ==================== 로그 레벨 ====================
class LogLevel(Enum):
    """
    로그 레벨

    사용 지침:
    - DEBUG: 디버깅 정보 (개발 환경)
    - INFO: 정상 작동 이벤트
    - WARNING: 잠재적 문제
    - ERROR: 복구 가능한 에러
    - CRITICAL: 시스템 중단 에러
    """
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    def __str__(self) -> str:
        return self.name

    def __lt__(self, other) -> bool:
        if isinstance(other, LogLevel):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other) -> bool:
        if isinstance(other, LogLevel):
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other) -> bool:
        if isinstance(other, LogLevel):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other) -> bool:
        if isinstance(other, LogLevel):
            return self.value >= other.value
        return NotImplemented


# ==================== 로그 레코드 ====================
@dataclass
class ExceptionInfo:
    """예외 정보"""
    type: str
    message: str
    code: Optional[str] = None
    traceback: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceInfo:
    """성능 정보"""
    processing_time_ms: Optional[float] = None
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None


@dataclass
class SystemInfo:
    """시스템 정보"""
    hostname: str = field(default_factory=lambda: os.getenv("HOSTNAME", "unknown"))
    pid: int = field(default_factory=os.getpid)
    thread: str = field(default_factory=lambda: threading.current_thread().name)


@dataclass
class LogRecord:
    """
    로그 레코드

    모든 로그 정보를 담는 불변 데이터 구조

    Attributes:
        timestamp: 로그 발생 시각
        level: 로그 레벨
        logger_name: 로거 이름
        message: 로그 메시지
        context: 추가 컨텍스트
        exception: 예외 정보
        performance: 성능 정보
        system: 시스템 정보
    """
    timestamp: datetime
    level: LogLevel
    logger_name: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[ExceptionInfo] = None
    performance: Optional[PerformanceInfo] = None
    system: SystemInfo = field(default_factory=SystemInfo)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        result = {
            "timestamp": self.timestamp.isoformat(),
            "level": str(self.level),
            "logger": self.logger_name,
            "message": self.message,
        }

        if self.context:
            result["context"] = self.context

        if self.exception:
            result["exception"] = asdict(self.exception)

        if self.performance:
            result["performance"] = asdict(self.performance)

        result["system"] = asdict(self.system)

        return result


# ==================== 필터 ====================
class Filter(ABC):
    """필터 추상 클래스"""

    @abstractmethod
    def filter(self, record: LogRecord) -> bool:
        """
        레코드 필터링

        Args:
            record: 로그 레코드

        Returns:
            True면 통과, False면 필터링
        """
        pass


class LevelFilter(Filter):
    """레벨 기반 필터"""

    def __init__(self, min_level: LogLevel):
        """
        Args:
            min_level: 최소 레벨
        """
        self.min_level = min_level

    def filter(self, record: LogRecord) -> bool:
        return record.level >= self.min_level


class SensitiveDataFilter(Filter):
    """
    민감 정보 필터

    비밀번호, API 키, 토큰 등 자동 마스킹
    """

    # 민감 정보 패턴
    SENSITIVE_KEYS = {
        "password", "passwd", "pwd",
        "api_key", "apikey", "token", "secret",
        "access_token", "refresh_token",
        "private_key", "credentials"
    }

    PATTERNS = {
        # 이메일: u***@example.com
        "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        # 신용카드: ****-****-****-1234
        "card": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
        # API 키: sk-***abc (최소 16자)
        "api_key": re.compile(r'(sk|pk)[-_][a-zA-Z0-9]{16,}'),
    }

    def filter(self, record: LogRecord) -> bool:
        """민감 정보 마스킹 (항상 True 반환)"""
        record.context = self._mask_dict(record.context)
        return True

    def _mask_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """딕셔너리 내 민감 정보 마스킹"""
        masked = {}
        for key, value in data.items():
            # 키가 민감한 경우
            if key.lower() in self.SENSITIVE_KEYS:
                masked[key] = self._mask_value(value)
            # 중첩 딕셔너리
            elif isinstance(value, dict):
                masked[key] = self._mask_dict(value)
            # 문자열 값 패턴 매칭
            elif isinstance(value, str):
                masked[key] = self._mask_string(value)
            else:
                masked[key] = value
        return masked

    def _mask_value(self, value: Any) -> str:
        """값 마스킹"""
        if isinstance(value, str):
            if len(value) <= 4:
                return "***"
            return f"{value[:2]}***{value[-2:]}"
        return "***"

    def _mask_string(self, text: str) -> str:
        """문자열 내 패턴 마스킹"""
        # 이메일
        text = self.PATTERNS["email"].sub(
            lambda m: f"{m.group(0)[0]}***@{m.group(0).split('@')[1]}", text
        )
        # 신용카드
        text = self.PATTERNS["card"].sub("****-****-****-****", text)
        # API 키
        text = self.PATTERNS["api_key"].sub(
            lambda m: f"{m.group(0)[:5]}***{m.group(0)[-3:]}", text
        )
        return text


# ==================== 포맷터 ====================
class Formatter(ABC):
    """포맷터 추상 클래스"""

    @abstractmethod
    def format(self, record: LogRecord) -> str:
        """
        레코드 포맷팅

        Args:
            record: 로그 레코드

        Returns:
            포맷된 문자열
        """
        pass


class JSONFormatter(Formatter):
    """JSON 포맷터"""

    def __init__(self, indent: Optional[int] = None):
        """
        Args:
            indent: JSON 들여쓰기 (None이면 한 줄)
        """
        self.indent = indent

    def format(self, record: LogRecord) -> str:
        """JSON 포맷으로 변환"""
        return json.dumps(record.to_dict(), indent=self.indent, ensure_ascii=False)


class ConsoleFormatter(Formatter):
    """
    콘솔 포맷터

    색상 및 구조화된 출력
    """

    def __init__(
        self,
        colored: bool = True,
        show_context: bool = True,
        max_width: int = 120
    ):
        """
        Args:
            colored: 색상 사용
            show_context: 컨텍스트 표시
            max_width: 최대 너비
        """
        self.colored = colored and COLORAMA_AVAILABLE
        self.show_context = show_context
        self.max_width = max_width

    def format(self, record: LogRecord) -> str:
        """콘솔 포맷으로 변환"""
        # 타임스탬프
        timestamp = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # 레벨 (색상)
        level_str = self._format_level(record.level)

        # 기본 메시지
        base = f"{timestamp} {level_str} {record.logger_name} - {record.message}"

        lines = [base]

        # 컨텍스트
        if self.show_context and record.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in record.context.items())
            if len(ctx_str) > self.max_width - 6:
                ctx_str = ctx_str[:self.max_width - 9] + "..."
            lines.append(f"  └─ {ctx_str}")

        # 예외
        if record.exception:
            exc = record.exception
            exc_line = f"  └─ {exc.type}"
            if exc.code:
                exc_line += f" [{exc.code}]"
            exc_line += f": {exc.message}"
            lines.append(exc_line)

            # 트레이스백 (일부만)
            if exc.traceback:
                tb_lines = exc.traceback.split("\n")[:3]
                for tb_line in tb_lines:
                    if tb_line.strip():
                        lines.append(f"     {tb_line}")

        return "\n".join(lines)

    def _format_level(self, level: LogLevel) -> str:
        """레벨 포맷 (색상)"""
        level_str = f"[{level.name}]"

        if not self.colored:
            return level_str

        if level == LogLevel.DEBUG:
            return f"{Style.DIM}{level_str}{Style.RESET_ALL}"
        elif level == LogLevel.INFO:
            return f"{Fore.GREEN}{level_str}{Style.RESET_ALL}"
        elif level == LogLevel.WARNING:
            return f"{Fore.YELLOW}{level_str}{Style.RESET_ALL}"
        elif level == LogLevel.ERROR:
            return f"{Fore.RED}{level_str}{Style.RESET_ALL}"
        elif level == LogLevel.CRITICAL:
            return f"{Fore.RED}{Style.BRIGHT}{level_str}{Style.RESET_ALL}"

        return level_str


# ==================== 핸들러 ====================
class Handler(ABC):
    """핸들러 추상 클래스"""

    def __init__(
        self,
        level: LogLevel = LogLevel.INFO,
        formatter: Optional[Formatter] = None,
        filters: Optional[List[Filter]] = None
    ):
        """
        Args:
            level: 최소 레벨
            formatter: 포맷터
            filters: 필터 리스트
        """
        self.level = level
        self.formatter = formatter or JSONFormatter()
        self.filters = filters or []

    def handle(self, record: LogRecord) -> None:
        """
        레코드 처리

        Args:
            record: 로그 레코드
        """
        # 레벨 체크
        if record.level < self.level:
            return

        # 필터 체크
        for f in self.filters:
            if not f.filter(record):
                return

        # 포맷 및 출력
        formatted = self.formatter.format(record)
        self.emit(formatted)

    @abstractmethod
    def emit(self, message: str) -> None:
        """
        메시지 출력

        Args:
            message: 포맷된 메시지
        """
        pass

    def close(self) -> None:
        """핸들러 종료 (선택)"""
        pass


class ConsoleHandler(Handler):
    """콘솔 핸들러"""

    def __init__(
        self,
        level: LogLevel = LogLevel.INFO,
        colored: bool = True,
        show_context: bool = True,
        stream: TextIO = sys.stderr
    ):
        """
        Args:
            level: 최소 레벨
            colored: 색상 사용
            show_context: 컨텍스트 표시
            stream: 출력 스트림
        """
        formatter = ConsoleFormatter(colored=colored, show_context=show_context)
        super().__init__(level=level, formatter=formatter)
        self.stream = stream

    def emit(self, message: str) -> None:
        """콘솔 출력"""
        try:
            self.stream.write(message + "\n")
            self.stream.flush()
        except Exception:
            # 출력 실패 시 무시 (로깅이 앱을 죽이면 안됨)
            pass


class FileHandler(Handler):
    """파일 핸들러"""

    def __init__(
        self,
        filename: Union[str, Path],
        level: LogLevel = LogLevel.DEBUG,
        mode: str = "a",
        encoding: str = "utf-8",
        format_type: str = "json"
    ):
        """
        Args:
            filename: 파일 경로
            level: 최소 레벨
            mode: 파일 모드 (a=append, w=write)
            encoding: 인코딩
            format_type: 포맷 (json | text)
        """
        formatter = JSONFormatter() if format_type == "json" else ConsoleFormatter(colored=False)
        super().__init__(level=level, formatter=formatter)

        self.filename = Path(filename)
        self.mode = mode
        self.encoding = encoding

        # 디렉토리 생성
        self.filename.parent.mkdir(parents=True, exist_ok=True)

        # 파일 열기
        self.file: Optional[TextIO] = None
        self._open()

    def _open(self) -> None:
        """파일 열기"""
        self.file = open(self.filename, self.mode, encoding=self.encoding)

    def emit(self, message: str) -> None:
        """파일 쓰기"""
        if self.file:
            try:
                self.file.write(message + "\n")
                self.file.flush()
            except Exception:
                pass

    def close(self) -> None:
        """파일 닫기"""
        if self.file:
            self.file.close()
            self.file = None


class RotatingFileHandler(Handler):
    """
    회전 파일 핸들러

    크기 기반 회전 + 압축
    """

    def __init__(
        self,
        filename: Union[str, Path],
        max_bytes: int = 100 * 1024 * 1024,  # 100MB
        backup_count: int = 10,
        level: LogLevel = LogLevel.DEBUG,
        compression: bool = True,
        encoding: str = "utf-8"
    ):
        """
        Args:
            filename: 파일 경로
            max_bytes: 최대 크기 (바이트)
            backup_count: 백업 개수
            level: 최소 레벨
            compression: 압축 여부
            encoding: 인코딩
        """
        formatter = JSONFormatter()
        super().__init__(level=level, formatter=formatter)

        self.filename = Path(filename)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.compression = compression
        self.encoding = encoding

        # 디렉토리 생성
        self.filename.parent.mkdir(parents=True, exist_ok=True)

        # 파일 열기
        self.file: Optional[TextIO] = None
        self._open()

    def _open(self) -> None:
        """파일 열기"""
        self.file = open(self.filename, "a", encoding=self.encoding)

    def emit(self, message: str) -> None:
        """파일 쓰기 (회전 체크)"""
        if not self.file:
            return

        try:
            # 크기 체크
            if self.file.tell() >= self.max_bytes:
                self._rotate()

            self.file.write(message + "\n")
            self.file.flush()
        except Exception:
            pass

    def _rotate(self) -> None:
        """파일 회전"""
        # 현재 파일 닫기
        if self.file:
            self.file.close()

        # 백업 이동 (역순)
        for i in range(self.backup_count - 1, 0, -1):
            src = self._get_backup_name(i)
            dst = self._get_backup_name(i + 1)
            if src.exists():
                dst.unlink(missing_ok=True)
                src.rename(dst)

        # 현재 파일 → 백업 1
        backup1 = self._get_backup_name(1)
        if self.filename.exists():
            backup1.unlink(missing_ok=True)
            self.filename.rename(backup1)

            # 압축
            if self.compression:
                self._compress(backup1)

        # 새 파일 열기
        self._open()

    def _get_backup_name(self, index: int) -> Path:
        """백업 파일명"""
        return self.filename.with_suffix(f".{index}{self.filename.suffix}")

    def _compress(self, file_path: Path) -> None:
        """파일 압축 (gzip)"""
        try:
            compressed = file_path.with_suffix(file_path.suffix + ".gz")
            with open(file_path, "rb") as f_in:
                with gzip.open(compressed, "wb") as f_out:
                    f_out.writelines(f_in)
            file_path.unlink()
        except Exception:
            pass

    def close(self) -> None:
        """파일 닫기"""
        if self.file:
            self.file.close()
            self.file = None


# ==================== 로거 ====================
class CourtViewLogger:
    """
    COURTVIEW 로거

    계층적 로거 시스템의 노드

    Features:
    - 레벨별 로깅 메서드
    - 다중 핸들러
    - 필터 체인
    - 예외 통합
    - 성능 측정

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
        >>> logger.error("Processing failed", extra={"frame_id": 123})
    """

    def __init__(
        self,
        name: str,
        level: LogLevel = LogLevel.INFO,
        handlers: Optional[List[Handler]] = None,
        filters: Optional[List[Filter]] = None
    ):
        """
        Args:
            name: 로거 이름
            level: 최소 레벨
            handlers: 핸들러 리스트
            filters: 필터 리스트
        """
        self.name = name
        self.level = level
        self.handlers = handlers or []
        self.filters = filters or []

    def debug(self, message: str, **kwargs) -> None:
        """DEBUG 로그"""
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """INFO 로그"""
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """WARNING 로그"""
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """ERROR 로그"""
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """CRITICAL 로그"""
        self._log(LogLevel.CRITICAL, message, **kwargs)

    def exception(self, message: str, exc_info: Optional[Exception] = None, **kwargs) -> None:
        """
        예외 로그 (ERROR 레벨)

        Args:
            message: 메시지
            exc_info: 예외 객체
            **kwargs: 추가 컨텍스트
        """
        # CourtViewError 자동 처리
        if exc_info:
            exception_info = self._extract_exception(exc_info)
            kwargs.setdefault("exception", exception_info)

        self._log(LogLevel.ERROR, message, **kwargs)

    def _log(self, level: LogLevel, message: str, **kwargs) -> None:
        """
        실제 로깅 처리

        Args:
            level: 로그 레벨
            message: 메시지
            **kwargs: extra, exception, performance 등
        """
        # 레벨 체크
        if level < self.level:
            return

        # 레코드 생성
        record = LogRecord(
            timestamp=datetime.now(),
            level=level,
            logger_name=self.name,
            message=message,
            context=kwargs.get("extra", {}),
            exception=kwargs.get("exception"),
            performance=kwargs.get("performance")
        )

        # 필터 체크
        for f in self.filters:
            if not f.filter(record):
                return

        # 핸들러 처리
        for handler in self.handlers:
            handler.handle(record)

    def _extract_exception(self, exc: Exception) -> ExceptionInfo:
        """
        예외 정보 추출

        CourtViewError는 자동으로 컨텍스트 추출

        Args:
            exc: 예외 객체

        Returns:
            ExceptionInfo
        """
        exc_type = type(exc).__name__
        exc_message = str(exc)
        exc_code = None
        exc_context = {}

        # CourtViewError 처리
        if hasattr(exc, "error_code"):
            exc_code = exc.error_code
        if hasattr(exc, "context"):
            exc_context = exc.context

        # 트레이스백
        exc_traceback = "".join(tb.format_exception(type(exc), exc, exc.__traceback__))

        return ExceptionInfo(
            type=exc_type,
            message=exc_message,
            code=exc_code,
            traceback=exc_traceback,
            context=exc_context
        )

    def add_handler(self, handler: Handler) -> None:
        """핸들러 추가"""
        self.handlers.append(handler)

    def remove_handler(self, handler: Handler) -> None:
        """핸들러 제거"""
        if handler in self.handlers:
            self.handlers.remove(handler)

    def set_level(self, level: LogLevel) -> None:
        """레벨 설정"""
        self.level = level


# ==================== 로거 팩토리 ====================
_loggers: Dict[str, CourtViewLogger] = {}
_lock = threading.Lock()
_default_handlers: Optional[List[Handler]] = None


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    handlers: Optional[List[Handler]] = None,
    enable_console: bool = True,
    log_file: Optional[Union[str, Path]] = None,
    rotating: bool = True
) -> None:
    """
    전역 로깅 설정

    Args:
        level: 기본 레벨
        handlers: 커스텀 핸들러
        enable_console: 콘솔 출력
        log_file: 로그 파일 경로
        rotating: 회전 로그 사용

    Examples:
        >>> configure_logging(
        ...     level=LogLevel.INFO,
        ...     log_file="logs/courtview.log",
        ...     rotating=True
        ... )
    """
    global _default_handlers

    _default_handlers = []

    # 커스텀 핸들러
    if handlers:
        _default_handlers.extend(handlers)
        return

    # 콘솔 핸들러
    if enable_console:
        _default_handlers.append(
            ConsoleHandler(level=level, colored=True, show_context=True)
        )

    # 파일 핸들러
    if log_file:
        if rotating:
            _default_handlers.append(
                RotatingFileHandler(
                    filename=log_file,
                    max_bytes=100 * 1024 * 1024,
                    backup_count=10,
                    level=LogLevel.DEBUG
                )
            )
        else:
            _default_handlers.append(
                FileHandler(filename=log_file, level=LogLevel.DEBUG)
            )


def get_logger(name: str) -> CourtViewLogger:
    """
    로거 팩토리

    계층적 로거 생성 (Singleton per name)

    Args:
        name: 로거 이름 (__name__ 권장)

    Returns:
        CourtViewLogger 인스턴스

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("Started")
    """
    with _lock:
        if name not in _loggers:
            # 기본 핸들러 설정 (없으면 콘솔만)
            if _default_handlers is None:
                configure_logging(enable_console=True)

            # 민감 정보 필터 자동 추가
            filters = [SensitiveDataFilter()]

            _loggers[name] = CourtViewLogger(
                name=name,
                level=LogLevel.INFO,
                handlers=_default_handlers,
                filters=filters
            )

        return _loggers[name]


# ==================== Export ====================
__all__ = [
    # 레벨
    "LogLevel",
    # 레코드
    "LogRecord",
    "ExceptionInfo",
    "PerformanceInfo",
    "SystemInfo",
    # 필터
    "Filter",
    "LevelFilter",
    "SensitiveDataFilter",
    # 포맷터
    "Formatter",
    "JSONFormatter",
    "ConsoleFormatter",
    # 핸들러
    "Handler",
    "ConsoleHandler",
    "FileHandler",
    "RotatingFileHandler",
    # 로거
    "CourtViewLogger",
    "get_logger",
    "configure_logging",
]
