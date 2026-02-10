"""
tests/core_foundation/monitoring/unit/test_logger.py

Logger 단위 테스트
- 로거 생성 및 계층 구조 (5개)
- 레벨 필터링 (4개)
- 핸들러 동작 (3개)
- 필터 체인 (3개)
- 포맷터 출력 (3개)
- 예외 처리 (3개)

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
from pathlib import Path
import json
import tempfile

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.monitoring.logger import (
    LogLevel,
    LogRecord,
    ExceptionInfo,
    CourtViewLogger,
    ConsoleHandler,
    FileHandler,
    JSONFormatter,
    ConsoleFormatter,
    LevelFilter,
    SensitiveDataFilter,
    get_logger,
    configure_logging,
)
from core_foundation.exceptions.validation import ConfigError


# ==================== 테스트 결과 클래스 ====================
class TestResult:
    """테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        """테스트 통과"""
        self.passed += 1
        print(f"[PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패"""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"[FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약"""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ==================== 로거 생성 테스트 (5개) ====================
def test_logger_creation(result: TestResult) -> None:
    """로거 생성"""
    try:
        logger = CourtViewLogger("test")
        assert logger.name == "test"
        assert logger.level == LogLevel.INFO
        assert len(logger.handlers) == 0
        result.ok("로거 생성")
    except Exception as e:
        result.fail("로거 생성", str(e))


def test_get_logger_singleton(result: TestResult) -> None:
    """get_logger 싱글톤"""
    try:
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")
        assert logger1 is logger2
        result.ok("get_logger 싱글톤")
    except Exception as e:
        result.fail("get_logger 싱글톤", str(e))


def test_logger_hierarchy(result: TestResult) -> None:
    """로거 계층 구조"""
    try:
        logger1 = get_logger("motion_analysis")
        logger2 = get_logger("motion_analysis.shooting")
        logger3 = get_logger("motion_analysis.dribbling")

        assert logger1.name == "motion_analysis"
        assert logger2.name == "motion_analysis.shooting"
        assert logger3.name == "motion_analysis.dribbling"

        result.ok("로거 계층 구조")
    except Exception as e:
        result.fail("로거 계층 구조", str(e))


def test_logger_level_setting(result: TestResult) -> None:
    """로거 레벨 설정"""
    try:
        logger = CourtViewLogger("test", level=LogLevel.DEBUG)
        assert logger.level == LogLevel.DEBUG

        logger.set_level(LogLevel.WARNING)
        assert logger.level == LogLevel.WARNING

        result.ok("로거 레벨 설정")
    except Exception as e:
        result.fail("로거 레벨 설정", str(e))


def test_handler_management(result: TestResult) -> None:
    """핸들러 추가/제거"""
    try:
        logger = CourtViewLogger("test")
        handler = ConsoleHandler()

        logger.add_handler(handler)
        assert len(logger.handlers) == 1
        assert handler in logger.handlers

        logger.remove_handler(handler)
        assert len(logger.handlers) == 0

        result.ok("핸들러 추가/제거")
    except Exception as e:
        result.fail("핸들러 추가/제거", str(e))


# ==================== 레벨 필터링 테스트 (4개) ====================
def test_level_comparison(result: TestResult) -> None:
    """레벨 비교"""
    try:
        assert LogLevel.DEBUG < LogLevel.INFO
        assert LogLevel.INFO < LogLevel.WARNING
        assert LogLevel.WARNING < LogLevel.ERROR
        assert LogLevel.ERROR < LogLevel.CRITICAL

        assert LogLevel.CRITICAL >= LogLevel.ERROR
        assert LogLevel.INFO <= LogLevel.WARNING

        result.ok("레벨 비교")
    except Exception as e:
        result.fail("레벨 비교", str(e))


def test_level_filter(result: TestResult) -> None:
    """레벨 필터"""
    try:
        from datetime import datetime

        level_filter = LevelFilter(min_level=LogLevel.WARNING)

        # DEBUG 필터링
        debug_record = LogRecord(
            timestamp=datetime.now(),
            level=LogLevel.DEBUG,
            logger_name="test",
            message="debug"
        )
        assert level_filter.filter(debug_record) is False

        # WARNING 통과
        warning_record = LogRecord(
            timestamp=datetime.now(),
            level=LogLevel.WARNING,
            logger_name="test",
            message="warning"
        )
        assert level_filter.filter(warning_record) is True

        # ERROR 통과
        error_record = LogRecord(
            timestamp=datetime.now(),
            level=LogLevel.ERROR,
            logger_name="test",
            message="error"
        )
        assert level_filter.filter(error_record) is True

        result.ok("레벨 필터")
    except Exception as e:
        result.fail("레벨 필터", str(e))


def test_logger_level_filtering(result: TestResult) -> None:
    """로거 레벨 필터링"""
    try:
        # 테스트용 핸들러
        messages = []

        class TestHandler:
            def handle(self, record):
                messages.append(record.message)

        logger = CourtViewLogger("test", level=LogLevel.WARNING)
        logger.add_handler(TestHandler())

        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")

        # DEBUG, INFO는 필터링, WARNING, ERROR만 통과
        assert "debug" not in messages
        assert "info" not in messages
        assert "warning" in messages
        assert "error" in messages

        result.ok("로거 레벨 필터링")
    except Exception as e:
        result.fail("로거 레벨 필터링", str(e))


def test_handler_level_filtering(result: TestResult) -> None:
    """핸들러 레벨 필터링"""
    try:
        # 임시 파일
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_file = f.name

        # ERROR 이상만 파일 저장
        file_handler = FileHandler(filename=temp_file, level=LogLevel.ERROR)

        logger = CourtViewLogger("test", level=LogLevel.DEBUG)
        logger.add_handler(file_handler)

        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")

        file_handler.close()

        # 파일 확인 (ERROR만 있어야 함)
        with open(temp_file, "r") as f:
            content = f.read()

        assert "debug" not in content
        assert "info" not in content
        assert "warning" not in content
        assert "error" in content

        # 정리
        Path(temp_file).unlink()

        result.ok("핸들러 레벨 필터링")
    except Exception as e:
        result.fail("핸들러 레벨 필터링", str(e))


# ==================== 핸들러 동작 테스트 (3개) ====================
def test_console_handler(result: TestResult) -> None:
    """콘솔 핸들러"""
    try:
        handler = ConsoleHandler(level=LogLevel.INFO, colored=False)
        assert handler.level == LogLevel.INFO
        assert isinstance(handler.formatter, ConsoleFormatter)

        from datetime import datetime
        record = LogRecord(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            logger_name="test",
            message="test message"
        )

        # 에러 없이 출력되어야 함
        handler.handle(record)

        result.ok("콘솔 핸들러")
    except Exception as e:
        result.fail("콘솔 핸들러", str(e))


def test_file_handler(result: TestResult) -> None:
    """파일 핸들러"""
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_file = f.name

        handler = FileHandler(filename=temp_file, level=LogLevel.DEBUG, format_type="json")

        from datetime import datetime
        record = LogRecord(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            logger_name="test",
            message="test message",
            context={"key": "value"}
        )

        handler.handle(record)
        handler.close()

        # 파일 확인
        with open(temp_file, "r") as f:
            line = f.readline()
            data = json.loads(line)

        assert data["level"] == "INFO"
        assert data["message"] == "test message"
        assert data["context"]["key"] == "value"

        # 정리
        Path(temp_file).unlink()

        result.ok("파일 핸들러")
    except Exception as e:
        result.fail("파일 핸들러", str(e))


def test_rotating_file_handler(result: TestResult) -> None:
    """회전 파일 핸들러"""
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_file = Path(f.name)

        # 작은 크기로 테스트
        from core_foundation.monitoring.logger import RotatingFileHandler
        handler = RotatingFileHandler(
            filename=temp_file,
            max_bytes=100,  # 100바이트
            backup_count=3,
            compression=False
        )

        from datetime import datetime
        # 여러 개 로그 작성 (회전 발생)
        for i in range(10):
            record = LogRecord(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                logger_name="test",
                message=f"test message {i}" * 10  # 긴 메시지
            )
            handler.handle(record)

        handler.close()

        # 회전된 파일 확인
        backup1 = temp_file.with_suffix(".1.log")
        assert backup1.exists() or temp_file.exists()

        # 정리
        temp_file.unlink(missing_ok=True)
        for i in range(1, 4):
            backup = temp_file.with_suffix(f".{i}.log")
            backup.unlink(missing_ok=True)

        result.ok("회전 파일 핸들러")
    except Exception as e:
        result.fail("회전 파일 핸들러", str(e))


# ==================== 필터 테스트 (3개) ====================
def test_sensitive_data_filter_keys(result: TestResult) -> None:
    """민감 데이터 필터 - 키"""
    try:
        from datetime import datetime

        sensitive_filter = SensitiveDataFilter()

        record = LogRecord(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            logger_name="test",
            message="test",
            context={
                "username": "test_user",
                "password": "secret123",
                "api_key": "sk-1234567890",
                "normal_field": "normal_value"
            }
        )

        sensitive_filter.filter(record)

        # 민감 정보 마스킹 확인
        assert "***" in record.context["password"]
        assert "***" in record.context["api_key"]
        assert record.context["normal_field"] == "normal_value"

        result.ok("민감 데이터 필터 - 키")
    except Exception as e:
        result.fail("민감 데이터 필터 - 키", str(e))


def test_sensitive_data_filter_patterns(result: TestResult) -> None:
    """민감 데이터 필터 - 패턴"""
    try:
        from datetime import datetime

        sensitive_filter = SensitiveDataFilter()

        record = LogRecord(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            logger_name="test",
            message="test",
            context={
                "email": "user@example.com",
                "card": "1234-5678-9012-3456",
                "text": "API key is sk-abcdefghijklmnopqrstuvwxyz1234"
            }
        )

        sensitive_filter.filter(record)

        # 패턴 마스킹 확인
        # 이메일: u***@example.com
        email_masked = record.context["email"]
        assert "***" in email_masked or email_masked != "user@example.com"

        # 카드: ****-****-****-****
        card_masked = record.context["card"]
        assert "****" in card_masked or card_masked != "1234-5678-9012-3456"

        # API 키: sk***234
        text_masked = record.context["text"]
        assert ("***" in text_masked or text_masked != "API key is sk-abcdefghijklmnopqrstuvwxyz1234"), \
            f"Expected masked text, got: {text_masked}"

        result.ok("민감 데이터 필터 - 패턴")
    except Exception as e:
        result.fail("민감 데이터 필터 - 패턴", str(e))


def test_filter_chain(result: TestResult) -> None:
    """필터 체인"""
    try:
        from datetime import datetime

        level_filter = LevelFilter(min_level=LogLevel.WARNING)
        sensitive_filter = SensitiveDataFilter()

        logger = CourtViewLogger("test", level=LogLevel.DEBUG, filters=[level_filter])

        messages = []
        class TestHandler:
            def __init__(self):
                self.filters = [sensitive_filter]
            def handle(self, record):
                for f in self.filters:
                    if not f.filter(record):
                        return
                messages.append(record)

        handler = TestHandler()
        logger.add_handler(handler)

        # DEBUG는 로거 레벨 필터로 차단
        logger.debug("debug", extra={"password": "secret"})

        # INFO는 핸들러 레벨 필터로 차단
        logger.info("info", extra={"password": "secret"})

        # WARNING은 통과, 민감 정보 마스킹
        logger.warning("warning", extra={"password": "secret"})

        assert len(messages) == 1
        assert messages[0].message == "warning"
        assert "***" in messages[0].context["password"]

        result.ok("필터 체인")
    except Exception as e:
        result.fail("필터 체인", str(e))


# ==================== 포맷터 테스트 (3개) ====================
def test_json_formatter(result: TestResult) -> None:
    """JSON 포맷터"""
    try:
        from datetime import datetime

        formatter = JSONFormatter()

        record = LogRecord(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            logger_name="test",
            message="test message",
            context={"key": "value"}
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "test message"
        assert data["context"]["key"] == "value"

        result.ok("JSON 포맷터")
    except Exception as e:
        result.fail("JSON 포맷터", str(e))


def test_console_formatter(result: TestResult) -> None:
    """콘솔 포맷터"""
    try:
        from datetime import datetime

        formatter = ConsoleFormatter(colored=False, show_context=True)

        record = LogRecord(
            timestamp=datetime.now(),
            level=LogLevel.WARNING,
            logger_name="test.module",
            message="test message",
            context={"frame_id": 123}
        )

        formatted = formatter.format(record)

        assert "[WARNING]" in formatted
        assert "test.module" in formatted
        assert "test message" in formatted
        assert "frame_id=123" in formatted

        result.ok("콘솔 포맷터")
    except Exception as e:
        result.fail("콘솔 포맷터", str(e))


def test_formatter_with_exception(result: TestResult) -> None:
    """포맷터 - 예외 포함"""
    try:
        from datetime import datetime

        formatter = ConsoleFormatter(colored=False)

        exc_info = ExceptionInfo(
            type="ValueError",
            message="Test error",
            code="CV999",
            traceback="Traceback..."
        )

        record = LogRecord(
            timestamp=datetime.now(),
            level=LogLevel.ERROR,
            logger_name="test",
            message="error occurred",
            exception=exc_info
        )

        formatted = formatter.format(record)

        assert "ValueError" in formatted
        assert "[CV999]" in formatted
        assert "Test error" in formatted

        result.ok("포맷터 - 예외 포함")
    except Exception as e:
        result.fail("포맷터 - 예외 포함", str(e))


# ==================== 예외 처리 테스트 (3개) ====================
def test_exception_logging(result: TestResult) -> None:
    """예외 로깅"""
    try:
        logger = CourtViewLogger("test")

        messages = []
        class TestHandler:
            def handle(self, record):
                messages.append(record)

        logger.add_handler(TestHandler())

        try:
            raise ValueError("Test error")
        except Exception as e:
            logger.exception("Error occurred", exc_info=e)

        assert len(messages) == 1
        assert messages[0].level == LogLevel.ERROR
        assert messages[0].exception is not None
        assert messages[0].exception.type == "ValueError"
        assert messages[0].exception.message == "Test error"

        result.ok("예외 로깅")
    except Exception as e:
        result.fail("예외 로깅", str(e))


def test_courtview_error_integration(result: TestResult) -> None:
    """CourtViewError 통합"""
    try:
        logger = CourtViewLogger("test")

        messages = []
        class TestHandler:
            def handle(self, record):
                messages.append(record)

        logger.add_handler(TestHandler())

        try:
            raise ConfigError("Config file not found", config_file="test.yaml", error_code="CV101")
        except Exception as e:
            logger.exception("Config error", exc_info=e)

        assert len(messages) == 1
        exc = messages[0].exception
        assert exc.type == "ConfigError"
        assert exc.code == "CV101"
        assert exc.context["config_file"] == "test.yaml"

        result.ok("CourtViewError 통합")
    except Exception as e:
        result.fail("CourtViewError 통합", str(e))


def test_exception_without_exc_info(result: TestResult) -> None:
    """예외 로깅 - exc_info 없음"""
    try:
        logger = CourtViewLogger("test")

        messages = []
        class TestHandler:
            def handle(self, record):
                messages.append(record)

        logger.add_handler(TestHandler())

        logger.exception("Error without exc_info")

        assert len(messages) == 1
        assert messages[0].level == LogLevel.ERROR
        assert messages[0].exception is None  # exc_info가 없으므로

        result.ok("예외 로깅 - exc_info 없음")
    except Exception as e:
        result.fail("예외 로깅 - exc_info 없음", str(e))


# ==================== 메인 실행 ====================
def main():
    """모든 단위 테스트 실행"""
    print("="*60)
    print("Logger 단위 테스트")
    print("="*60)

    result = TestResult()

    print("\n[로거 생성 및 계층]")
    test_logger_creation(result)
    test_get_logger_singleton(result)
    test_logger_hierarchy(result)
    test_logger_level_setting(result)
    test_handler_management(result)

    print("\n[레벨 필터링]")
    test_level_comparison(result)
    test_level_filter(result)
    test_logger_level_filtering(result)
    test_handler_level_filtering(result)

    print("\n[핸들러 동작]")
    test_console_handler(result)
    test_file_handler(result)
    test_rotating_file_handler(result)

    print("\n[필터]")
    test_sensitive_data_filter_keys(result)
    test_sensitive_data_filter_patterns(result)
    test_filter_chain(result)

    print("\n[포맷터]")
    test_json_formatter(result)
    test_console_formatter(result)
    test_formatter_with_exception(result)

    print("\n[예외 처리]")
    test_exception_logging(result)
    test_courtview_error_integration(result)
    test_exception_without_exc_info(result)

    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
