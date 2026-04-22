# -*- coding: utf-8 -*-
"""monitoring/logger.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import json
import logging
import threading

import pytest
from pathlib import Path

from core_foundation.monitoring.logger import (
    ComponentLogger,
    DEFAULT_LOG_DIR,
    DEFAULT_LOG_FILE,
    DEFAULT_LOG_FORMAT,
    LogLevel,
    LogManager,
    MAX_LOG_BACKUP_COUNT,
    MAX_LOG_FILE_BYTES,
    MAX_LOGGER_COUNT,
    ROOT_LOGGER_NAME,
    StructuredFormatter,
    get_logger,
)


# =============================================================================
# 테스트 헬퍼
# =============================================================================

class _CaptureHandler(logging.Handler):
    """로그 레코드를 메모리에 캡처하는 테스트용 핸들러."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


# =============================================================================
# 테스트 설정
# =============================================================================

@pytest.fixture(autouse=True)
def reset_log_manager():
    """모든 테스트 전후로 LogManager 초기화."""
    LogManager.reset()
    yield
    LogManager.reset()


# =============================================================================
# LogLevel 검증
# =============================================================================

class TestLogLevel:
    """LogLevel Enum 검증."""

    def test_member_count(self):
        assert len(LogLevel) == 5

    def test_values(self):
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_python_level(self):
        assert LogLevel.DEBUG.python_level == logging.DEBUG
        assert LogLevel.INFO.python_level == logging.INFO
        assert LogLevel.ERROR.python_level == logging.ERROR

    def test_to_korean(self):
        assert LogLevel.DEBUG.to_korean() == "디버그"
        assert LogLevel.INFO.to_korean() == "정보"
        assert LogLevel.WARNING.to_korean() == "경고"
        assert LogLevel.ERROR.to_korean() == "오류"
        assert LogLevel.CRITICAL.to_korean() == "치명적"

    def test_from_string(self):
        assert LogLevel.from_string("info") == LogLevel.INFO
        assert LogLevel.from_string("DEBUG") == LogLevel.DEBUG
        assert LogLevel.from_string(" Warning ") == LogLevel.WARNING

    def test_from_string_invalid(self):
        with pytest.raises(ValueError, match="알 수 없는 로그 레벨"):
            LogLevel.from_string("TRACE")


# =============================================================================
# StructuredFormatter 검증
# =============================================================================

class TestStructuredFormatter:
    """StructuredFormatter 검증."""

    def test_text_format(self):
        formatter = StructuredFormatter(json_mode=False)
        record = logging.LogRecord(
            name="courtview.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="테스트 메시지",
            args=None,
            exc_info=None,
        )
        record.component = "test"  # type: ignore[attr-defined]
        output = formatter.format(record)
        assert "INFO" in output
        assert "test" in output
        assert "테스트 메시지" in output

    def test_json_format(self):
        formatter = StructuredFormatter(json_mode=True)
        record = logging.LogRecord(
            name="courtview.test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=20,
            msg="JSON 로그",
            args=None,
            exc_info=None,
        )
        record.component = "detection.ball"  # type: ignore[attr-defined]
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "WARNING"
        assert data["component"] == "detection.ball"
        assert data["message"] == "JSON 로그"
        assert data["lineno"] == 20

    def test_json_format_with_context(self):
        formatter = StructuredFormatter(json_mode=True)
        record = logging.LogRecord(
            name="courtview.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="컨텍스트 포함",
            args=None,
            exc_info=None,
        )
        record.component = "test"  # type: ignore[attr-defined]
        record.extra_context = {"fps": 60, "camera_id": 1}  # type: ignore[attr-defined]
        output = formatter.format(record)
        data = json.loads(output)
        assert data["context"]["fps"] == 60

    def test_missing_component_uses_name(self):
        formatter = StructuredFormatter(json_mode=False)
        record = logging.LogRecord(
            name="courtview.fallback",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="폴백",
            args=None,
            exc_info=None,
        )
        # component 미설정 → name으로 폴백
        output = formatter.format(record)
        assert "courtview.fallback" in output


# =============================================================================
# ComponentLogger 검증
# =============================================================================

class TestComponentLogger:
    """ComponentLogger 검증."""

    def test_creation(self):
        logger = ComponentLogger("detection.ball")
        assert logger.component == "detection.ball"

    def test_repr(self):
        logger = ComponentLogger("test")
        assert "test" in repr(logger)

    def test_log_levels(self):
        """모든 로그 레벨 메서드 호출."""
        manager = LogManager.get_instance()
        manager.setup(log_level=LogLevel.DEBUG, console_output=False, file_output=False)

        # 캡처용 핸들러 직접 추가
        handler = _CaptureHandler()
        handler.setLevel(logging.DEBUG)
        logging.getLogger(ROOT_LOGGER_NAME).addHandler(handler)

        logger = ComponentLogger("test_levels")
        logger.debug("디버그")
        logger.info("정보")
        logger.warning("경고")
        logger.error("오류")
        logger.critical("치명적")

        assert len(handler.records) == 5
        logging.getLogger(ROOT_LOGGER_NAME).removeHandler(handler)

    def test_default_context(self):
        manager = LogManager.get_instance()
        manager.setup(log_level=LogLevel.DEBUG, console_output=False, file_output=False)

        handler = _CaptureHandler()
        handler.setLevel(logging.DEBUG)
        logging.getLogger(ROOT_LOGGER_NAME).addHandler(handler)

        logger = ComponentLogger("test_ctx", default_context={"env": "local"})
        logger.info("컨텍스트 테스트")

        assert len(handler.records) == 1
        assert handler.records[0].extra_context["env"] == "local"  # type: ignore[attr-defined]
        logging.getLogger(ROOT_LOGGER_NAME).removeHandler(handler)

    def test_set_level(self):
        logger = ComponentLogger("test")
        logger.set_level(LogLevel.ERROR)
        assert logger.level == logging.ERROR

    def test_exception_log(self):
        manager = LogManager.get_instance()
        manager.setup(log_level=LogLevel.DEBUG, console_output=False, file_output=False)

        handler = _CaptureHandler()
        handler.setLevel(logging.DEBUG)
        logging.getLogger(ROOT_LOGGER_NAME).addHandler(handler)

        logger = ComponentLogger("test_exc")
        try:
            raise ValueError("테스트 예외")
        except ValueError:
            logger.exception("예외 발생")

        assert len(handler.records) == 1
        assert handler.records[0].exc_info is not None
        logging.getLogger(ROOT_LOGGER_NAME).removeHandler(handler)


# =============================================================================
# LogManager 검증
# =============================================================================

class TestLogManager:
    """LogManager 검증."""

    def test_singleton(self):
        m1 = LogManager.get_instance()
        m2 = LogManager.get_instance()
        assert m1 is m2

    def test_reset(self):
        m1 = LogManager.get_instance()
        LogManager.reset()
        m2 = LogManager.get_instance()
        assert m1 is not m2

    def test_setup_console_only(self):
        manager = LogManager.get_instance()
        manager.setup(
            log_level=LogLevel.DEBUG,
            console_output=True,
            file_output=False,
        )
        assert manager.is_setup
        assert manager.handler_count == 1  # 콘솔만

    def test_setup_file_only(self, tmp_path):
        manager = LogManager.get_instance()
        manager.setup(
            log_level=LogLevel.INFO,
            log_dir=tmp_path,
            console_output=False,
            file_output=True,
        )
        assert manager.handler_count == 1  # 파일만
        assert manager.log_dir == tmp_path

    def test_setup_both(self, tmp_path):
        manager = LogManager.get_instance()
        manager.setup(
            log_level=LogLevel.INFO,
            log_dir=tmp_path,
            console_output=True,
            file_output=True,
        )
        assert manager.handler_count == 2

    def test_setup_creates_log_dir(self, tmp_path):
        log_dir = tmp_path / "subdir" / "logs"
        manager = LogManager.get_instance()
        manager.setup(
            log_dir=log_dir,
            console_output=False,
            file_output=True,
        )
        assert log_dir.is_dir()

    def test_get_logger(self):
        manager = LogManager.get_instance()
        logger = manager.get_logger("detection.ball")
        assert isinstance(logger, ComponentLogger)
        assert logger.component == "detection.ball"

    def test_get_logger_cached(self):
        manager = LogManager.get_instance()
        l1 = manager.get_logger("test")
        l2 = manager.get_logger("test")
        assert l1 is l2

    def test_logger_count(self):
        manager = LogManager.get_instance()
        manager.get_logger("a")
        manager.get_logger("b")
        assert manager.logger_count == 2

    def test_set_level(self):
        manager = LogManager.get_instance()
        manager.setup(console_output=False, file_output=False)
        manager.set_level(LogLevel.ERROR)
        assert manager.log_level == LogLevel.ERROR

    def test_log_level_property(self):
        manager = LogManager.get_instance()
        assert manager.log_level == LogLevel.INFO  # 기본값

    def test_repr(self):
        manager = LogManager.get_instance()
        r = repr(manager)
        assert "level=INFO" in r

    def test_auto_setup_on_get_logger(self):
        """미설정 상태에서 get_logger 호출 시 자동 설정."""
        manager = LogManager.get_instance()
        assert not manager.is_setup
        _ = manager.get_logger("auto_test")
        assert manager.is_setup


# =============================================================================
# 파일 로깅 검증
# =============================================================================

class TestFileLogging:
    """파일 로깅 검증."""

    def test_log_to_file(self, tmp_path):
        manager = LogManager.get_instance()
        manager.setup(
            log_level=LogLevel.DEBUG,
            log_dir=tmp_path,
            log_file="test.log",
            console_output=False,
            file_output=True,
        )

        logger = manager.get_logger("file_test")
        logger.info("파일 로그 테스트")

        # 핸들러 플러시
        for handler in logging.getLogger(ROOT_LOGGER_NAME).handlers:
            handler.flush()

        log_file = tmp_path / "test.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "파일 로그 테스트" in content

    def test_json_log_to_file(self, tmp_path):
        manager = LogManager.get_instance()
        manager.setup(
            log_level=LogLevel.DEBUG,
            log_dir=tmp_path,
            log_file="json.log",
            json_mode=True,
            console_output=False,
            file_output=True,
        )

        logger = manager.get_logger("json_test")
        logger.info("JSON 파일 테스트", key="value")

        for handler in logging.getLogger(ROOT_LOGGER_NAME).handlers:
            handler.flush()

        log_file = tmp_path / "json.log"
        content = log_file.read_text(encoding="utf-8")
        data = json.loads(content.strip())
        assert data["message"] == "JSON 파일 테스트"
        assert data["context"]["key"] == "value"


# =============================================================================
# 편의 함수 검증
# =============================================================================

class TestGetLogger:
    """get_logger 편의 함수 검증."""

    def test_get_logger_function(self):
        logger = get_logger("convenience_test")
        assert isinstance(logger, ComponentLogger)
        assert logger.component == "convenience_test"

    def test_get_logger_with_context(self):
        logger = get_logger("ctx_test", default_context={"ver": "1.0"})
        assert logger.component == "ctx_test"


# =============================================================================
# 스레드 안전 검증
# =============================================================================

class TestThreadSafety:
    """스레드 안전 검증."""

    def test_concurrent_logger_creation(self):
        manager = LogManager.get_instance()
        manager.setup(console_output=False, file_output=False)

        loggers: list[ComponentLogger] = []
        errors: list[Exception] = []

        def create_logger(idx: int) -> None:
            try:
                lg = manager.get_logger(f"thread_{idx}")
                loggers.append(lg)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=create_logger, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert manager.logger_count == 20


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    """상수 검증."""

    def test_root_logger_name(self):
        assert ROOT_LOGGER_NAME == "courtview"

    def test_max_log_file_bytes(self):
        assert MAX_LOG_FILE_BYTES == 10 * 1024 * 1024

    def test_max_backup_count(self):
        assert MAX_LOG_BACKUP_COUNT == 5

    def test_max_logger_count(self):
        assert MAX_LOGGER_COUNT == 200


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    """__all__ 및 __version__ 검증."""

    def test_all_exists(self):
        import core_foundation.monitoring.logger as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.monitoring.logger as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name} in __all__ but not in module"

    def test_version(self):
        import core_foundation.monitoring.logger as mod
        assert mod.__version__ == "1.0.0"
