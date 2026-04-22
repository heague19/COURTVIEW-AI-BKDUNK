# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: logger.py
설명: 중앙 로깅 엔진 — 표준 logging 기반 구조화 로깅
      - 컴포넌트별 로거 생성 (계층적 네이밍)
      - JSON 구조화 로그 포맷터
      - 콘솔 + 파일 핸들러 (회전 로그)
      - 컨텍스트 주입 (컴포넌트, 요청 ID 등)
      - 로그 레벨 동적 변경
      - 스레드 안전 (logging 모듈 내장)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import json
import logging
import logging.handlers
import os
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path
from typing import Any, ClassVar, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 기본 로그 디렉토리
DEFAULT_LOG_DIR: Final[str] = "logs"

# 기본 로그 파일명
DEFAULT_LOG_FILE: Final[str] = "courtview.log"

# 로그 파일 최대 크기 (10MB)
MAX_LOG_FILE_BYTES: Final[int] = 10 * 1024 * 1024

# 로그 파일 백업 수
MAX_LOG_BACKUP_COUNT: Final[int] = 5

# 루트 로거 이름
ROOT_LOGGER_NAME: Final[str] = "courtview"

# 로거 최대 생성 수 (메모리 성장 방지)
MAX_LOGGER_COUNT: Final[int] = 200

# 기본 로그 포맷
DEFAULT_LOG_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(component)s | %(message)s"
)

# JSON 로그 포맷 키
_JSON_KEYS: Final[tuple[str, ...]] = (
    "timestamp", "level", "component", "message",
    "module", "funcName", "lineno",
)


# =============================================================================
# 로그 레벨 열거형
# =============================================================================

@unique
class LogLevel(Enum):
    """로그 레벨 열거형."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def python_level(self) -> int:
        """Python logging 레벨 정수값."""
        return _LOG_LEVEL_MAP[self]

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _LOG_LEVEL_KOREAN_MAP[self]

    @classmethod
    def from_string(cls, value: str) -> LogLevel:
        """문자열에서 로그 레벨 파싱. 대소문자 무시."""
        normalized = value.strip().upper()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(
            f"알 수 없는 로그 레벨: '{value}'. "
            f"허용값: {[m.value for m in cls]}"
        )


_LOG_LEVEL_MAP: Final[dict[LogLevel, int]] = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
    LogLevel.CRITICAL: logging.CRITICAL,
}

_LOG_LEVEL_KOREAN_MAP: Final[dict[LogLevel, str]] = {
    LogLevel.DEBUG: "디버그",
    LogLevel.INFO: "정보",
    LogLevel.WARNING: "경고",
    LogLevel.ERROR: "오류",
    LogLevel.CRITICAL: "치명적",
}


# =============================================================================
# 구조화 로그 포맷터
# =============================================================================

class StructuredFormatter(logging.Formatter):
    """JSON 구조화 로그 포맷터.

    로그 레코드를 JSON 형식으로 변환한다.
    사람이 읽기 쉬운 텍스트 포맷도 지원.

    Attributes:
        json_mode: True이면 JSON 출력, False이면 텍스트 출력
    """

    def __init__(self, *, json_mode: bool = False, fmt: str | None = None) -> None:
        """StructuredFormatter 초기화.

        Args:
            json_mode: JSON 형식 출력 여부
            fmt: 텍스트 모드용 포맷 문자열 (None이면 기본 포맷)
        """
        super().__init__(fmt=fmt or DEFAULT_LOG_FORMAT)
        self._json_mode = json_mode

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드 포맷팅.

        Args:
            record: 로그 레코드

        Returns:
            포맷팅된 문자열
        """
        # 컴포넌트 기본값 주입
        if not hasattr(record, "component"):
            record.component = record.name  # type: ignore[attr-defined]

        if self._json_mode:
            return self._format_json(record)
        return super().format(record)

    def _format_json(self, record: logging.LogRecord) -> str:
        """JSON 형식 포맷팅."""
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "component": getattr(record, "component", record.name),
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }

        # 예외 정보
        if record.exc_info and record.exc_info[1] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        # 추가 컨텍스트 (extra 필드)
        extra = getattr(record, "extra_context", None)
        if extra and isinstance(extra, dict):
            log_data["context"] = extra

        return json.dumps(log_data, ensure_ascii=False, default=str)


# =============================================================================
# 컴포넌트 로거 래퍼
# =============================================================================

class ComponentLogger:
    """컴포넌트별 로거 래퍼.

    Python logging.Logger를 감싸서 컴포넌트 이름과
    컨텍스트 자동 주입을 제공한다.

    사용 예시::

        logger = ComponentLogger("detection.ball")
        logger.info("공 감지 시작", fps=60, camera_id=1)
        logger.error("감지 실패", exc_info=True)
    """

    __slots__ = ("_logger", "_component", "_default_context")

    def __init__(
        self,
        component: str,
        *,
        default_context: dict[str, Any] | None = None,
    ) -> None:
        """ComponentLogger 초기화.

        Args:
            component: 컴포넌트 이름 (예: "detection.ball")
            default_context: 모든 로그에 자동 포함할 컨텍스트
        """
        self._component = component
        self._logger = logging.getLogger(f"{ROOT_LOGGER_NAME}.{component}")
        self._default_context = default_context or {}

    def debug(self, msg: str, **kwargs: Any) -> None:
        """DEBUG 레벨 로그."""
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        """INFO 레벨 로그."""
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        """WARNING 레벨 로그."""
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        """ERROR 레벨 로그."""
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:
        """CRITICAL 레벨 로그."""
        self._log(logging.CRITICAL, msg, **kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:
        """ERROR 레벨 + 예외 스택 트레이스."""
        kwargs["exc_info"] = True
        self._log(logging.ERROR, msg, **kwargs)

    @property
    def component(self) -> str:
        """컴포넌트 이름."""
        return self._component

    @property
    def level(self) -> int:
        """현재 유효 로그 레벨."""
        return self._logger.getEffectiveLevel()

    def set_level(self, level: LogLevel) -> None:
        """로그 레벨 설정.

        Args:
            level: 설정할 로그 레벨
        """
        self._logger.setLevel(level.python_level)

    def _log(self, level: int, msg: str, **kwargs: Any) -> None:
        """내부 로그 기록.

        exc_info를 제외한 모든 kwargs를 컨텍스트로 처리.
        """
        exc_info = kwargs.pop("exc_info", False)

        # 컨텍스트 병합 (기본 + 호출 시점)
        context = {**self._default_context, **kwargs} if kwargs else self._default_context

        extra: dict[str, Any] = {
            "component": self._component,
        }
        if context:
            extra["extra_context"] = context

        self._logger.log(level, msg, exc_info=exc_info, extra=extra)

    def __repr__(self) -> str:
        return f"ComponentLogger(component='{self._component}')"


# =============================================================================
# 핵심 클래스: LogManager
# =============================================================================

class LogManager:
    """중앙 로그 관리자.

    애플리케이션 전체의 로깅 설정을 관리한다.
    루트 로거 설정, 핸들러 추가/제거, 컴포넌트 로거 생성을 담당.

    스레드 안전:
        - logging 모듈 자체가 스레드 안전
        - 로거 생성/관리는 RLock 추가 보호

    사용 예시::

        # 앱 시작 시 초기화
        manager = LogManager.get_instance()
        manager.setup(
            log_level=LogLevel.INFO,
            log_dir="logs",
            json_mode=False,
        )

        # 컴포넌트 로거 생성
        logger = manager.get_logger("detection.ball")
        logger.info("감지 시작", camera_count=4)
    """

    _instance: ClassVar[LogManager | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self) -> None:
        """LogManager 초기화."""
        self._lock = threading.RLock()
        self._root_logger = logging.getLogger(ROOT_LOGGER_NAME)
        self._loggers: dict[str, ComponentLogger] = {}
        self._setup_done = False
        self._log_level = LogLevel.INFO
        self._json_mode = False
        self._log_dir: Path | None = None

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> LogManager:
        """Singleton 인스턴스 획득."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Singleton 초기화 (테스트용)."""
        with cls._class_lock:
            if cls._instance is not None:
                # 기존 핸들러 정리
                instance = cls._instance
                root = instance._root_logger
                for handler in root.handlers[:]:
                    handler.close()
                    root.removeHandler(handler)
                instance._loggers.clear()
                instance._setup_done = False
            cls._instance = None

    # =========================================================================
    # 설정
    # =========================================================================

    def setup(
        self,
        *,
        log_level: LogLevel = LogLevel.INFO,
        log_dir: str | Path | None = None,
        log_file: str = DEFAULT_LOG_FILE,
        json_mode: bool = False,
        console_output: bool = True,
        file_output: bool = True,
        max_file_bytes: int = MAX_LOG_FILE_BYTES,
        backup_count: int = MAX_LOG_BACKUP_COUNT,
    ) -> None:
        """로깅 시스템 설정.

        Args:
            log_level: 로그 레벨
            log_dir: 로그 파일 디렉토리 (None이면 기본 디렉토리)
            log_file: 로그 파일명
            json_mode: JSON 구조화 로그 여부
            console_output: 콘솔 출력 여부
            file_output: 파일 출력 여부
            max_file_bytes: 로그 파일 최대 크기 (bytes)
            backup_count: 백업 파일 수
        """
        with self._lock:
            # 기존 핸들러 제거
            for handler in self._root_logger.handlers[:]:
                handler.close()
                self._root_logger.removeHandler(handler)

            self._log_level = log_level
            self._json_mode = json_mode
            self._root_logger.setLevel(log_level.python_level)

            # 전파 방지 (courtview 로거가 root Python 로거로 전파되지 않도록)
            self._root_logger.propagate = False

            # 포맷터 생성
            formatter = StructuredFormatter(json_mode=json_mode)

            # 콘솔 핸들러
            if console_output:
                console_handler = logging.StreamHandler(sys.stderr)
                console_handler.setLevel(log_level.python_level)
                console_handler.setFormatter(formatter)
                self._root_logger.addHandler(console_handler)

            # 파일 핸들러
            if file_output:
                resolved_dir = Path(log_dir) if log_dir else self._default_log_dir()
                resolved_dir.mkdir(parents=True, exist_ok=True)
                self._log_dir = resolved_dir

                file_path = resolved_dir / log_file
                file_handler = logging.handlers.RotatingFileHandler(
                    filename=str(file_path),
                    maxBytes=max_file_bytes,
                    backupCount=backup_count,
                    encoding="utf-8",
                )
                file_handler.setLevel(log_level.python_level)
                file_handler.setFormatter(formatter)
                self._root_logger.addHandler(file_handler)

            self._setup_done = True

    # =========================================================================
    # 로거 관리
    # =========================================================================

    def get_logger(
        self,
        component: str,
        *,
        default_context: dict[str, Any] | None = None,
    ) -> ComponentLogger:
        """컴포넌트 로거 획득.

        동일 컴포넌트 이름으로 재요청 시 기존 로거 반환.

        Args:
            component: 컴포넌트 이름 (예: "detection.ball")
            default_context: 기본 컨텍스트

        Returns:
            ComponentLogger 인스턴스

        Raises:
            ValueError: 로거 최대 수 초과
        """
        with self._lock:
            if component in self._loggers:
                return self._loggers[component]

            if len(self._loggers) >= MAX_LOGGER_COUNT:
                raise ValueError(
                    f"로거 최대 생성 수 초과: {MAX_LOGGER_COUNT}"
                )

            # 미설정 상태면 기본 설정 적용
            if not self._setup_done:
                self.setup()

            logger = ComponentLogger(
                component,
                default_context=default_context,
            )
            self._loggers[component] = logger
            return logger

    def set_level(self, level: LogLevel) -> None:
        """전체 로그 레벨 변경.

        Args:
            level: 새 로그 레벨
        """
        with self._lock:
            self._log_level = level
            self._root_logger.setLevel(level.python_level)
            for handler in self._root_logger.handlers:
                handler.setLevel(level.python_level)

    @property
    def log_level(self) -> LogLevel:
        """현재 로그 레벨."""
        return self._log_level

    @property
    def is_setup(self) -> bool:
        """설정 완료 여부."""
        return self._setup_done

    @property
    def logger_count(self) -> int:
        """생성된 로거 수."""
        with self._lock:
            return len(self._loggers)

    @property
    def handler_count(self) -> int:
        """등록된 핸들러 수."""
        return len(self._root_logger.handlers)

    @property
    def log_dir(self) -> Path | None:
        """로그 디렉토리 경로."""
        return self._log_dir

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    @staticmethod
    def _default_log_dir() -> Path:
        """기본 로그 디렉토리 해석."""
        project_root = Path(__file__).resolve().parent.parent.parent
        return project_root / DEFAULT_LOG_DIR

    def __repr__(self) -> str:
        return (
            f"LogManager("
            f"level={self._log_level.value}, "
            f"loggers={self.logger_count}, "
            f"handlers={self.handler_count}, "
            f"json={self._json_mode})"
        )


# =============================================================================
# 편의 함수 — 모듈 레벨 로거 빠른 생성
# =============================================================================

def get_logger(
    component: str,
    *,
    default_context: dict[str, Any] | None = None,
) -> ComponentLogger:
    """컴포넌트 로거 편의 생성 함수.

    LogManager.get_instance().get_logger()의 축약형.

    Args:
        component: 컴포넌트 이름
        default_context: 기본 컨텍스트

    Returns:
        ComponentLogger
    """
    return LogManager.get_instance().get_logger(
        component,
        default_context=default_context,
    )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "LogLevel",
    # 포맷터
    "StructuredFormatter",
    # 로거
    "ComponentLogger",
    # 관리자
    "LogManager",
    # 편의 함수
    "get_logger",
    # 상수
    "DEFAULT_LOG_DIR",
    "DEFAULT_LOG_FILE",
    "MAX_LOG_FILE_BYTES",
    "MAX_LOG_BACKUP_COUNT",
    "ROOT_LOGGER_NAME",
    "MAX_LOGGER_COUNT",
    "DEFAULT_LOG_FORMAT",
]

__version__ = "1.0.0"
