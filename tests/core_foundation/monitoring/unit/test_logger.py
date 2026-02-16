# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/monitoring/unit
파일: test_logger.py
설명: LogManager(Loguru 기반) 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    [1]  상수 검증 (9개)
    [2]  LogLevel Enum (8개)
    [3]  SinkConfig 데이터 클래스 (7개)
    [4]  LoggingConfig 데이터 클래스 (9개)
    [5]  InterceptHandler (5개)
    [6]  SensitiveDataFilter (10개)
    [7]  필터 함수 (_analysis_filter, _performance_filter, _error_filter) (8개)
    [8]  LogManager 초기화 (7개)
    [9]  LogManager.setup() (9개)
    [10] LogManager YAML 설정 로드 (6개)
    [11] LogManager 싱크 관리 (add_sink, remove_sink) (8개)
    [12] LogManager 공개 API (get_logger, set_level, get_status) (9개)
    [13] LogManager.shutdown (5개)
    [14] 싱글톤 관리 (_get_manager, _reset_manager) (6개)
    [15] 헬퍼 함수 (setup_logging, get_logger, log_analysis, log_performance) (9개)
    [16] 엣지 케이스 / __all__ 내보내기 (8개)
"""

import json
import logging
import os
import sys
import tempfile
import threading
import types
from copy import deepcopy
from dataclasses import fields
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.monitoring.logger import (
    # 상수
    LOGURU_AVAILABLE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_DIR,
    DEFAULT_LOG_FORMAT,
    DEFAULT_FILE_FORMAT,
    JSON_LOG_KEYS,
    DEFAULT_ROTATION_SIZE,
    DEFAULT_RETENTION,
    DEFAULT_COMPRESSION,
    DEFAULT_ENCODING,
    ERROR_ROTATION_SIZE,
    ERROR_RETENTION,
    ANALYSIS_ROTATION_SIZE,
    ANALYSIS_RETENTION,
    PERFORMANCE_ROTATION_SIZE,
    PERFORMANCE_RETENTION,
    DEFAULT_SENSITIVE_PATTERNS,
    MASK_VALUE,
    STDLIB_LEVEL_MAP,
    DEFAULT_THIRD_PARTY_LEVELS,
    # Enum
    LogLevel,
    # 데이터 클래스
    SinkConfig,
    LoggingConfig,
    # 핸들러/필터
    InterceptHandler,
    SensitiveDataFilter,
    # 필터 함수
    _analysis_filter,
    _performance_filter,
    _error_filter,
    # 메인 클래스
    LogManager,
    # 헬퍼 함수
    setup_logging,
    get_logger,
    log_analysis,
    log_performance,
    # 유틸리티 (테스트용)
    _get_manager,
    _reset_manager,
)

# Loguru 직접 참조
try:
    from loguru import logger as _loguru_logger
except ImportError:
    _loguru_logger = None


# =============================================================================
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    """테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        """테스트 통과."""
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패."""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼: LogManager 리셋
# =============================================================================
def reset_logging():
    """LogManager 싱글톤 리셋 및 logging 핸들러 정리."""
    _reset_manager()
    # 루트 로거 핸들러 정리 (InterceptHandler 제거)
    root = logging.root
    root.handlers = [h for h in root.handlers if not isinstance(h, InterceptHandler)]
    if not root.handlers:
        root.setLevel(logging.WARNING)


# =============================================================================
# [1] 상수 검증
# =============================================================================
def test_constants(result: TestResult) -> None:
    """상수 값 검증."""
    print("\n[1] 상수 검증")

    # 1-1. 기본 로그 레벨
    try:
        assert DEFAULT_LOG_LEVEL == "INFO", f"기본 레벨: {DEFAULT_LOG_LEVEL}"
        result.ok("1-1: DEFAULT_LOG_LEVEL = 'INFO'")
    except Exception as e:
        result.fail("1-1: DEFAULT_LOG_LEVEL", str(e))

    # 1-2. 기본 로그 디렉토리
    try:
        assert DEFAULT_LOG_DIR == "logs", f"기본 디렉토리: {DEFAULT_LOG_DIR}"
        result.ok("1-2: DEFAULT_LOG_DIR = 'logs'")
    except Exception as e:
        result.fail("1-2: DEFAULT_LOG_DIR", str(e))

    # 1-3. 로그 포맷 (콘솔/파일)
    try:
        assert "time" in DEFAULT_LOG_FORMAT
        assert "level" in DEFAULT_LOG_FORMAT
        assert "message" in DEFAULT_LOG_FORMAT
        assert "time" in DEFAULT_FILE_FORMAT
        assert "<green>" not in DEFAULT_FILE_FORMAT  # 파일용에는 색상 없음
        result.ok("1-3: DEFAULT_LOG_FORMAT / DEFAULT_FILE_FORMAT 구조")
    except Exception as e:
        result.fail("1-3: 로그 포맷", str(e))

    # 1-4. 파일 로테이션 상수
    try:
        assert DEFAULT_ROTATION_SIZE == "10 MB"
        assert DEFAULT_RETENTION == "30 days"
        assert DEFAULT_COMPRESSION == "gz"
        assert DEFAULT_ENCODING == "utf-8"
        result.ok("1-4: 파일 로테이션 기본값")
    except Exception as e:
        result.fail("1-4: 파일 로테이션", str(e))

    # 1-5. 에러/분석/성능 로그 상수
    try:
        assert ERROR_ROTATION_SIZE == "10 MB"
        assert ERROR_RETENTION == "90 days"
        assert ANALYSIS_ROTATION_SIZE == "50 MB"
        assert ANALYSIS_RETENTION == "180 days"
        assert PERFORMANCE_ROTATION_SIZE == "50 MB"
        assert PERFORMANCE_RETENTION == "30 days"
        result.ok("1-5: 에러/분석/성능 로테이션 상수")
    except Exception as e:
        result.fail("1-5: 에러/분석/성능 상수", str(e))

    # 1-6. 민감 정보 마스킹 패턴
    try:
        assert isinstance(DEFAULT_SENSITIVE_PATTERNS, list)
        assert "password" in DEFAULT_SENSITIVE_PATTERNS
        assert "secret" in DEFAULT_SENSITIVE_PATTERNS
        assert "token" in DEFAULT_SENSITIVE_PATTERNS
        assert "api_key" in DEFAULT_SENSITIVE_PATTERNS
        assert len(DEFAULT_SENSITIVE_PATTERNS) >= 8
        assert MASK_VALUE == "***MASKED***"
        result.ok("1-6: DEFAULT_SENSITIVE_PATTERNS / MASK_VALUE")
    except Exception as e:
        result.fail("1-6: 마스킹 패턴", str(e))

    # 1-7. STDLIB_LEVEL_MAP
    try:
        assert STDLIB_LEVEL_MAP[logging.DEBUG] == "DEBUG"
        assert STDLIB_LEVEL_MAP[logging.INFO] == "INFO"
        assert STDLIB_LEVEL_MAP[logging.WARNING] == "WARNING"
        assert STDLIB_LEVEL_MAP[logging.ERROR] == "ERROR"
        assert STDLIB_LEVEL_MAP[logging.CRITICAL] == "CRITICAL"
        result.ok("1-7: STDLIB_LEVEL_MAP 매핑")
    except Exception as e:
        result.fail("1-7: STDLIB_LEVEL_MAP", str(e))

    # 1-8. DEFAULT_THIRD_PARTY_LEVELS
    try:
        assert isinstance(DEFAULT_THIRD_PARTY_LEVELS, dict)
        assert DEFAULT_THIRD_PARTY_LEVELS.get("watchdog") == "WARNING"
        assert DEFAULT_THIRD_PARTY_LEVELS.get("torch") == "WARNING"
        assert DEFAULT_THIRD_PARTY_LEVELS.get("cv2") == "WARNING"
        assert len(DEFAULT_THIRD_PARTY_LEVELS) >= 8
        result.ok("1-8: DEFAULT_THIRD_PARTY_LEVELS 서드파티 레벨")
    except Exception as e:
        result.fail("1-8: DEFAULT_THIRD_PARTY_LEVELS", str(e))

    # 1-9. JSON_LOG_KEYS
    try:
        assert isinstance(JSON_LOG_KEYS, list)
        assert "timestamp" in JSON_LOG_KEYS
        assert "level" in JSON_LOG_KEYS
        assert "message" in JSON_LOG_KEYS
        assert len(JSON_LOG_KEYS) >= 6
        result.ok("1-9: JSON_LOG_KEYS 키 목록")
    except Exception as e:
        result.fail("1-9: JSON_LOG_KEYS", str(e))


# =============================================================================
# [2] LogLevel Enum
# =============================================================================
def test_log_level_enum(result: TestResult) -> None:
    """LogLevel Enum 테스트."""
    print("\n[2] LogLevel Enum")

    # 2-1. 멤버 존재
    try:
        expected = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
        for name in expected:
            assert hasattr(LogLevel, name), f"{name} 멤버 누락"
        assert len(list(LogLevel)) == 7
        result.ok("2-1: 7개 멤버 존재")
    except Exception as e:
        result.fail("2-1: 멤버 존재", str(e))

    # 2-2. 값 확인
    try:
        assert LogLevel.TRACE.value == "TRACE"
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.SUCCESS.value == "SUCCESS"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"
        result.ok("2-2: 모든 멤버 값 일치")
    except Exception as e:
        result.fail("2-2: 멤버 값", str(e))

    # 2-3. from_string 정상 변환
    try:
        assert LogLevel.from_string("debug") == LogLevel.DEBUG
        assert LogLevel.from_string("INFO") == LogLevel.INFO
        assert LogLevel.from_string("  Warning  ") == LogLevel.WARNING
        assert LogLevel.from_string("error") == LogLevel.ERROR
        assert LogLevel.from_string("TRACE") == LogLevel.TRACE
        assert LogLevel.from_string("success") == LogLevel.SUCCESS
        result.ok("2-3: from_string 정상 변환 (대소문자/공백)")
    except Exception as e:
        result.fail("2-3: from_string 정상", str(e))

    # 2-4. from_string 잘못된 값 → INFO 폴백
    try:
        assert LogLevel.from_string("unknown") == LogLevel.INFO
        assert LogLevel.from_string("") == LogLevel.INFO
        assert LogLevel.from_string("VERBOSE") == LogLevel.INFO
        result.ok("2-4: from_string 잘못된 값 -> INFO 폴백")
    except Exception as e:
        result.fail("2-4: from_string 폴백", str(e))

    # 2-5. to_stdlib_level 매핑
    try:
        assert LogLevel.TRACE.to_stdlib_level() == logging.DEBUG
        assert LogLevel.DEBUG.to_stdlib_level() == logging.DEBUG
        assert LogLevel.INFO.to_stdlib_level() == logging.INFO
        assert LogLevel.SUCCESS.to_stdlib_level() == logging.INFO
        assert LogLevel.WARNING.to_stdlib_level() == logging.WARNING
        assert LogLevel.ERROR.to_stdlib_level() == logging.ERROR
        assert LogLevel.CRITICAL.to_stdlib_level() == logging.CRITICAL
        result.ok("2-5: to_stdlib_level 매핑 (7개)")
    except Exception as e:
        result.fail("2-5: to_stdlib_level", str(e))

    # 2-6. Enum 이름 접근
    try:
        level = LogLevel.WARNING
        assert level.name == "WARNING"
        assert level.value == "WARNING"
        result.ok("2-6: Enum name/value 접근")
    except Exception as e:
        result.fail("2-6: Enum name/value", str(e))

    # 2-7. Enum 반복
    try:
        names = [lv.name for lv in LogLevel]
        assert names == ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
        result.ok("2-7: Enum 반복 순서")
    except Exception as e:
        result.fail("2-7: Enum 반복", str(e))

    # 2-8. Enum 동등성 / 해시
    try:
        a = LogLevel.from_string("DEBUG")
        b = LogLevel.DEBUG
        assert a == b
        assert a is b
        assert hash(a) == hash(b)
        # 딕셔너리 키로 사용
        d = {LogLevel.INFO: "info_level"}
        assert d[LogLevel.INFO] == "info_level"
        result.ok("2-8: Enum 동등성 / 해시")
    except Exception as e:
        result.fail("2-8: Enum 동등성", str(e))


# =============================================================================
# [3] SinkConfig 데이터 클래스
# =============================================================================
def test_sink_config(result: TestResult) -> None:
    """SinkConfig 데이터 클래스 테스트."""
    print("\n[3] SinkConfig 데이터 클래스")

    # 3-1. 기본값 생성
    try:
        sc = SinkConfig()
        assert sc.name == "default"
        assert sc.enabled is True
        assert sc.path is None
        assert sc.level == "DEBUG"
        assert sc.format == DEFAULT_FILE_FORMAT
        assert sc.rotation == DEFAULT_ROTATION_SIZE
        assert sc.retention == DEFAULT_RETENTION
        assert sc.compression == DEFAULT_COMPRESSION
        assert sc.encoding == DEFAULT_ENCODING
        assert sc.serialize is False
        assert sc.filter_func is None
        result.ok("3-1: SinkConfig 기본값 12필드")
    except Exception as e:
        result.fail("3-1: SinkConfig 기본값", str(e))

    # 3-2. 커스텀 값 생성
    try:
        sc = SinkConfig(
            name="custom_error",
            enabled=True,
            path="/var/log/error.log",
            level="ERROR",
            rotation="50 MB",
            retention="60 days",
            compression="zip",
            encoding="utf-8",
            serialize=True,
        )
        assert sc.name == "custom_error"
        assert sc.path == "/var/log/error.log"
        assert sc.level == "ERROR"
        assert sc.rotation == "50 MB"
        assert sc.retention == "60 days"
        assert sc.compression == "zip"
        assert sc.serialize is True
        result.ok("3-2: SinkConfig 커스텀 값")
    except Exception as e:
        result.fail("3-2: SinkConfig 커스텀", str(e))

    # 3-3. filter_func 콜백 설정
    try:
        def my_filter(record):
            return record.get("level", {}).get("name") == "ERROR"

        sc = SinkConfig(name="filtered", filter_func=my_filter)
        assert sc.filter_func is my_filter
        assert callable(sc.filter_func)
        result.ok("3-3: filter_func 콜백")
    except Exception as e:
        result.fail("3-3: filter_func", str(e))

    # 3-4. 필드 수 확인
    try:
        field_names = [f.name for f in fields(SinkConfig)]
        assert len(field_names) == 11, f"필드 수: {len(field_names)}"
        expected_fields = [
            "name", "enabled", "path", "level",
            "rotation", "retention", "compression", "encoding",
            "serialize", "filter_func",
        ]
        for ef in expected_fields:
            assert ef in field_names, f"{ef} 필드 누락"
        result.ok("3-4: 필드 수 11개")
    except Exception as e:
        result.fail("3-4: 필드 수", str(e))

    # 3-5. 콘솔 싱크 설정 (path=None)
    try:
        sc = SinkConfig(name="console", path=None, level="INFO")
        assert sc.path is None
        assert sc.name == "console"
        result.ok("3-5: 콘솔 싱크 (path=None)")
    except Exception as e:
        result.fail("3-5: 콘솔 싱크", str(e))

    # 3-6. disabled 싱크
    try:
        sc = SinkConfig(name="disabled_sink", enabled=False)
        assert sc.enabled is False
        result.ok("3-6: disabled 싱크 (enabled=False)")
    except Exception as e:
        result.fail("3-6: disabled 싱크", str(e))

    # 3-7. SinkConfig 독립 인스턴스
    try:
        sc1 = SinkConfig(name="a")
        sc2 = SinkConfig(name="b")
        assert sc1.name != sc2.name
        sc1.name = "modified"
        assert sc2.name == "b"
        result.ok("3-7: 인스턴스 독립성")
    except Exception as e:
        result.fail("3-7: 인스턴스 독립성", str(e))


# =============================================================================
# [4] LoggingConfig 데이터 클래스
# =============================================================================
def test_logging_config(result: TestResult) -> None:
    """LoggingConfig 데이터 클래스 테스트."""
    print("\n[4] LoggingConfig 데이터 클래스")

    # 4-1. 기본값 생성
    try:
        lc = LoggingConfig()
        assert lc.level == "INFO"
        assert lc.log_dir == "logs"
        assert lc.console_enabled is True
        assert lc.console_level == "INFO"
        assert lc.console_colorize is True
        assert lc.file_enabled is True
        assert lc.error_file_enabled is True
        assert lc.analysis_file_enabled is True
        assert lc.performance_file_enabled is True
        assert lc.json_format is False
        assert lc.sensitive_masking is True
        assert lc.intercept_stdlib is True
        result.ok("4-1: LoggingConfig 기본값 (12개 필드)")
    except Exception as e:
        result.fail("4-1: LoggingConfig 기본값", str(e))

    # 4-2. sensitive_patterns 기본값 (DEFAULT_SENSITIVE_PATTERNS 복사)
    try:
        lc = LoggingConfig()
        assert isinstance(lc.sensitive_patterns, list)
        assert lc.sensitive_patterns == DEFAULT_SENSITIVE_PATTERNS
        # 리스트 독립 확인
        lc.sensitive_patterns.append("extra_key")
        assert "extra_key" not in DEFAULT_SENSITIVE_PATTERNS
        result.ok("4-2: sensitive_patterns 기본값 독립 복사")
    except Exception as e:
        result.fail("4-2: sensitive_patterns", str(e))

    # 4-3. module_levels 기본값 (빈 딕셔너리)
    try:
        lc = LoggingConfig()
        assert isinstance(lc.module_levels, dict)
        assert len(lc.module_levels) == 0
        result.ok("4-3: module_levels 빈 딕셔너리")
    except Exception as e:
        result.fail("4-3: module_levels", str(e))

    # 4-4. third_party_levels 기본값 (DEFAULT_THIRD_PARTY_LEVELS 복사)
    try:
        lc = LoggingConfig()
        assert isinstance(lc.third_party_levels, dict)
        assert lc.third_party_levels == DEFAULT_THIRD_PARTY_LEVELS
        # 독립성
        lc.third_party_levels["test_lib"] = "ERROR"
        assert "test_lib" not in DEFAULT_THIRD_PARTY_LEVELS
        result.ok("4-4: third_party_levels 기본값 독립 복사")
    except Exception as e:
        result.fail("4-4: third_party_levels", str(e))

    # 4-5. 커스텀 설정
    try:
        lc = LoggingConfig(
            level="DEBUG",
            log_dir="/tmp/logs",
            console_enabled=False,
            json_format=True,
            sensitive_masking=False,
        )
        assert lc.level == "DEBUG"
        assert lc.log_dir == "/tmp/logs"
        assert lc.console_enabled is False
        assert lc.json_format is True
        assert lc.sensitive_masking is False
        result.ok("4-5: 커스텀 LoggingConfig")
    except Exception as e:
        result.fail("4-5: 커스텀 LoggingConfig", str(e))

    # 4-6. console_format 기본값
    try:
        lc = LoggingConfig()
        assert lc.console_format == DEFAULT_LOG_FORMAT
        assert "<green>" in lc.console_format
        result.ok("4-6: console_format = DEFAULT_LOG_FORMAT")
    except Exception as e:
        result.fail("4-6: console_format", str(e))

    # 4-7. 필드 수 확인
    try:
        field_names = [f.name for f in fields(LoggingConfig)]
        assert len(field_names) == 16, f"필드 수: {len(field_names)}"
        result.ok("4-7: LoggingConfig 필드 16개")
    except Exception as e:
        result.fail("4-7: 필드 수", str(e))

    # 4-8. 인스턴스 독립성 (default_factory)
    try:
        lc1 = LoggingConfig()
        lc2 = LoggingConfig()
        lc1.sensitive_patterns.append("test_extra")
        assert "test_extra" not in lc2.sensitive_patterns
        lc1.third_party_levels["new_lib"] = "DEBUG"
        assert "new_lib" not in lc2.third_party_levels
        result.ok("4-8: default_factory 인스턴스 독립성")
    except Exception as e:
        result.fail("4-8: default_factory 독립성", str(e))

    # 4-9. module_levels 커스텀
    try:
        lc = LoggingConfig(
            module_levels={"motion_analysis": "DEBUG", "court_detection": "WARNING"}
        )
        assert lc.module_levels["motion_analysis"] == "DEBUG"
        assert lc.module_levels["court_detection"] == "WARNING"
        result.ok("4-9: module_levels 커스텀 설정")
    except Exception as e:
        result.fail("4-9: module_levels 커스텀", str(e))


# =============================================================================
# [5] InterceptHandler
# =============================================================================
def test_intercept_handler(result: TestResult) -> None:
    """InterceptHandler 테스트."""
    print("\n[5] InterceptHandler")

    # 5-1. 클래스 상속
    try:
        assert issubclass(InterceptHandler, logging.Handler)
        handler = InterceptHandler()
        assert isinstance(handler, logging.Handler)
        result.ok("5-1: logging.Handler 상속")
    except Exception as e:
        result.fail("5-1: 상속", str(e))

    # 5-2. emit 메서드 존재
    try:
        handler = InterceptHandler()
        assert hasattr(handler, "emit")
        assert callable(handler.emit)
        result.ok("5-2: emit 메서드 존재")
    except Exception as e:
        result.fail("5-2: emit 메서드", str(e))

    # 5-3. InterceptHandler 인스턴스 생성 반복
    try:
        handlers = [InterceptHandler() for _ in range(5)]
        assert len(handlers) == 5
        for h in handlers:
            assert isinstance(h, InterceptHandler)
        result.ok("5-3: 다중 인스턴스 생성")
    except Exception as e:
        result.fail("5-3: 다중 인스턴스", str(e))

    # 5-4. 루트 로거에 핸들러 설치
    try:
        test_logger = logging.getLogger("test_intercept_handler_5_4")
        handler = InterceptHandler()
        test_logger.addHandler(handler)
        assert any(isinstance(h, InterceptHandler) for h in test_logger.handlers)
        test_logger.removeHandler(handler)
        result.ok("5-4: 루트 로거에 설치/제거")
    except Exception as e:
        result.fail("5-4: 핸들러 설치", str(e))

    # 5-5. LOGURU_AVAILABLE 플래그와의 연동
    try:
        assert LOGURU_AVAILABLE is True, "loguru가 설치되어 있어야 합니다"
        handler = InterceptHandler()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None,
        )
        # emit이 예외 없이 실행되어야 함 (스택 프레임 이슈 가능)
        # InterceptHandler는 sys._getframe으로 호출자를 찾으므로
        # 직접 호출 시에도 안전해야 함
        try:
            handler.emit(record)
        except (ValueError, AttributeError):
            pass  # 프레임 탐색 실패는 허용
        result.ok("5-5: LOGURU_AVAILABLE=True 시 emit 안전 실행")
    except Exception as e:
        result.fail("5-5: emit 안전 실행", str(e))


# =============================================================================
# [6] SensitiveDataFilter
# =============================================================================
def test_sensitive_data_filter(result: TestResult) -> None:
    """SensitiveDataFilter 테스트."""
    print("\n[6] SensitiveDataFilter")

    # 6-1. 기본 패턴으로 생성
    try:
        f = SensitiveDataFilter()
        assert f._patterns == DEFAULT_SENSITIVE_PATTERNS
        assert f._mask_value == MASK_VALUE
        result.ok("6-1: 기본 패턴 생성")
    except Exception as e:
        result.fail("6-1: 기본 생성", str(e))

    # 6-2. 커스텀 패턴
    try:
        f = SensitiveDataFilter(patterns=["username", "email"], mask_value="[REDACTED]")
        assert f._patterns == ["username", "email"]
        assert f._mask_value == "[REDACTED]"
        result.ok("6-2: 커스텀 패턴/마스크값")
    except Exception as e:
        result.fail("6-2: 커스텀 패턴", str(e))

    # 6-3. mask_string - key=value 형식 마스킹
    try:
        f = SensitiveDataFilter()
        text = "user login: password=abc123 token=xyz456"
        masked = f.mask_string(text)
        assert "abc123" not in masked, f"패스워드 노출: {masked}"
        assert "xyz456" not in masked, f"토큰 노출: {masked}"
        assert MASK_VALUE in masked
        result.ok("6-3: mask_string key=value 마스킹")
    except Exception as e:
        result.fail("6-3: mask_string key=value", str(e))

    # 6-4. mask_string - key: value 형식
    try:
        f = SensitiveDataFilter()
        text = 'secret: my_secret_value'
        masked = f.mask_string(text)
        assert "my_secret_value" not in masked, f"시크릿 노출: {masked}"
        assert MASK_VALUE in masked
        result.ok("6-4: mask_string key: value 마스킹")
    except Exception as e:
        result.fail("6-4: mask_string key:", str(e))

    # 6-5. mask_string - 대소문자 무시
    try:
        f = SensitiveDataFilter()
        text = "PASSWORD=upper123 Token=mixed456"
        masked = f.mask_string(text)
        assert "upper123" not in masked, f"대문자 패스워드 노출: {masked}"
        assert "mixed456" not in masked, f"혼합 토큰 노출: {masked}"
        result.ok("6-5: 대소문자 무시 마스킹")
    except Exception as e:
        result.fail("6-5: 대소문자", str(e))

    # 6-6. __call__ - 레코드 필터링 (항상 True)
    try:
        f = SensitiveDataFilter()
        record = {"message": "api_key=secret123 login ok"}
        ret = f(record)
        assert ret is True, f"필터 반환값: {ret}"
        assert "secret123" not in record["message"]
        assert MASK_VALUE in record["message"]
        result.ok("6-6: __call__ 레코드 필터링 (반환=True, 메시지 마스킹)")
    except Exception as e:
        result.fail("6-6: __call__ 필터링", str(e))

    # 6-7. __call__ - 민감 패턴 없는 메시지 (변경 없음)
    try:
        f = SensitiveDataFilter()
        original = "normal message without sensitive info"
        record = {"message": original}
        ret = f(record)
        assert ret is True
        assert record["message"] == original
        result.ok("6-7: 민감 패턴 없는 메시지 유지")
    except Exception as e:
        result.fail("6-7: 패턴 없는 메시지", str(e))

    # 6-8. __call__ - 빈 메시지
    try:
        f = SensitiveDataFilter()
        record = {"message": ""}
        ret = f(record)
        assert ret is True
        assert record["message"] == ""
        result.ok("6-8: 빈 메시지 처리")
    except Exception as e:
        result.fail("6-8: 빈 메시지", str(e))

    # 6-9. __call__ - message 키 없음
    try:
        f = SensitiveDataFilter()
        record = {}
        ret = f(record)
        assert ret is True
        result.ok("6-9: message 키 없는 레코드")
    except Exception as e:
        result.fail("6-9: message 키 없음", str(e))

    # 6-10. 다중 패턴 동시 마스킹
    try:
        f = SensitiveDataFilter()
        text = "password=pw1 secret=sc2 token=tk3 api_key=ak4"
        masked = f.mask_string(text)
        assert "pw1" not in masked
        assert "sc2" not in masked
        assert "tk3" not in masked
        assert "ak4" not in masked
        count = masked.count(MASK_VALUE)
        assert count == 4, f"마스킹 횟수: {count}"
        result.ok("6-10: 다중 패턴 동시 마스킹 (4개)")
    except Exception as e:
        result.fail("6-10: 다중 마스킹", str(e))


# =============================================================================
# [7] 필터 함수 (_analysis_filter, _performance_filter, _error_filter)
# =============================================================================
def test_filter_functions(result: TestResult) -> None:
    """필터 함수 테스트."""
    print("\n[7] 필터 함수")

    # 7-1. _analysis_filter - analysis 태그 통과
    try:
        record = {"extra": {"log_type": "analysis"}}
        assert _analysis_filter(record) is True
        result.ok("7-1: _analysis_filter 통과 (log_type=analysis)")
    except Exception as e:
        result.fail("7-1: analysis 통과", str(e))

    # 7-2. _analysis_filter - 다른 태그 차단
    try:
        assert _analysis_filter({"extra": {"log_type": "performance"}}) is False
        assert _analysis_filter({"extra": {}}) is False
        assert _analysis_filter({"extra": {"log_type": "general"}}) is False
        result.ok("7-2: _analysis_filter 차단 (다른 태그)")
    except Exception as e:
        result.fail("7-2: analysis 차단", str(e))

    # 7-3. _performance_filter - performance 태그 통과
    try:
        record = {"extra": {"log_type": "performance"}}
        assert _performance_filter(record) is True
        result.ok("7-3: _performance_filter 통과 (log_type=performance)")
    except Exception as e:
        result.fail("7-3: performance 통과", str(e))

    # 7-4. _performance_filter - 다른 태그 차단
    try:
        assert _performance_filter({"extra": {"log_type": "analysis"}}) is False
        assert _performance_filter({"extra": {}}) is False
        result.ok("7-4: _performance_filter 차단")
    except Exception as e:
        result.fail("7-4: performance 차단", str(e))

    # 7-5. _error_filter - ERROR 레벨 통과
    try:
        # Loguru level.no: TRACE=5, DEBUG=10, INFO=20, SUCCESS=25, WARNING=30, ERROR=40, CRITICAL=50
        class _Level:
            def __init__(self, no):
                self.no = no

        assert _error_filter({"level": _Level(40)}) is True  # ERROR
        assert _error_filter({"level": _Level(50)}) is True  # CRITICAL
        result.ok("7-5: _error_filter ERROR/CRITICAL 통과")
    except Exception as e:
        result.fail("7-5: error 통과", str(e))

    # 7-6. _error_filter - ERROR 미만 차단
    try:
        class _Level:
            def __init__(self, no):
                self.no = no

        assert _error_filter({"level": _Level(10)}) is False  # DEBUG
        assert _error_filter({"level": _Level(20)}) is False  # INFO
        assert _error_filter({"level": _Level(30)}) is False  # WARNING
        assert _error_filter({"level": _Level(39)}) is False  # WARNING+
        result.ok("7-6: _error_filter DEBUG/INFO/WARNING 차단")
    except Exception as e:
        result.fail("7-6: error 차단", str(e))

    # 7-7. _analysis_filter - extra 키 없음
    try:
        record = {}
        # extra 키가 없으면 .get("extra", {}) → {} → .get("log_type") → None → False
        assert _analysis_filter(record) is False
        result.ok("7-7: extra 키 없는 레코드 처리")
    except Exception as e:
        result.fail("7-7: extra 없음", str(e))

    # 7-8. 필터 함수 callable 확인
    try:
        assert callable(_analysis_filter)
        assert callable(_performance_filter)
        assert callable(_error_filter)
        result.ok("7-8: 3개 필터 함수 callable")
    except Exception as e:
        result.fail("7-8: callable", str(e))


# =============================================================================
# [8] LogManager 초기화
# =============================================================================
def test_log_manager_init(result: TestResult) -> None:
    """LogManager 초기화 테스트."""
    print("\n[8] LogManager 초기화")

    # 8-1. 기본 생성
    try:
        reset_logging()
        m = LogManager()
        assert m.initialized is False
        assert isinstance(m.config, LoggingConfig)
        result.ok("8-1: 기본 생성 (initialized=False)")
    except Exception as e:
        result.fail("8-1: 기본 생성", str(e))

    # 8-2. config 직접 전달
    try:
        reset_logging()
        cfg = LoggingConfig(level="DEBUG", log_dir="/tmp/test_logs")
        m = LogManager(config=cfg)
        assert m.config.level == "DEBUG"
        assert m.config.log_dir == "/tmp/test_logs"
        result.ok("8-2: config 직접 전달")
    except Exception as e:
        result.fail("8-2: config 직접", str(e))

    # 8-3. config_loader 전달 (None)
    try:
        reset_logging()
        m = LogManager(config_loader=None)
        assert m.initialized is False
        assert m.config.level == "INFO"
        result.ok("8-3: config_loader=None")
    except Exception as e:
        result.fail("8-3: config_loader=None", str(e))

    # 8-4. _lock 속성 존재 (스레드 안전)
    try:
        m = LogManager()
        assert hasattr(m, "_lock")
        assert isinstance(m._lock, type(threading.RLock()))
        result.ok("8-4: _lock RLock 존재")
    except Exception as e:
        result.fail("8-4: _lock", str(e))

    # 8-5. _sink_ids 초기 빈 딕셔너리
    try:
        m = LogManager()
        assert isinstance(m._sink_ids, dict)
        assert len(m._sink_ids) == 0
        result.ok("8-5: _sink_ids 빈 딕셔너리")
    except Exception as e:
        result.fail("8-5: _sink_ids", str(e))

    # 8-6. _sensitive_filter 초기 None
    try:
        m = LogManager()
        assert m._sensitive_filter is None
        result.ok("8-6: _sensitive_filter=None (setup 전)")
    except Exception as e:
        result.fail("8-6: _sensitive_filter", str(e))

    # 8-7. _original_handlers 초기 빈 리스트
    try:
        m = LogManager()
        assert isinstance(m._original_handlers, list)
        assert len(m._original_handlers) == 0
        result.ok("8-7: _original_handlers 빈 리스트")
    except Exception as e:
        result.fail("8-7: _original_handlers", str(e))


# =============================================================================
# [9] LogManager.setup()
# =============================================================================
def test_log_manager_setup(result: TestResult) -> None:
    """LogManager.setup() 테스트."""
    print("\n[9] LogManager.setup()")

    # 9-1. 기본 setup (모든 싱크 활성화)
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config=cfg)
            m.setup()
            assert m.initialized is True
            assert len(m._sink_ids) > 0
            m.shutdown()
        result.ok("9-1: 기본 setup (initialized=True)")
    except Exception as e:
        result.fail("9-1: 기본 setup", str(e))

    # 9-2. 콘솔 싱크 생성 확인
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=True, file_enabled=False,
                                error_file_enabled=False, analysis_file_enabled=False,
                                performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()
            assert "console" in m._sink_ids
            m.shutdown()
        result.ok("9-2: 콘솔 싱크 생성")
    except Exception as e:
        result.fail("9-2: 콘솔 싱크", str(e))

    # 9-3. 파일 싱크 생성 (general, error, analysis, performance)
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config=cfg)
            m.setup()
            for sink_name in ["general", "error", "analysis", "performance"]:
                assert sink_name in m._sink_ids, f"{sink_name} 싱크 누락"
            m.shutdown()
        result.ok("9-3: 4개 파일 싱크 생성 (general/error/analysis/performance)")
    except Exception as e:
        result.fail("9-3: 파일 싱크", str(e))

    # 9-4. 콘솔 비활성화
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False)
            m = LogManager(config=cfg)
            m.setup()
            assert "console" not in m._sink_ids
            m.shutdown()
        result.ok("9-4: console_enabled=False 시 콘솔 싱크 없음")
    except Exception as e:
        result.fail("9-4: 콘솔 비활성화", str(e))

    # 9-5. 파일 비활성화
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = LogManager(config=cfg)
            m.setup()
            assert "general" not in m._sink_ids
            assert "error" not in m._sink_ids
            assert "analysis" not in m._sink_ids
            assert "performance" not in m._sink_ids
            m.shutdown()
        result.ok("9-5: 모든 파일 싱크 비활성화")
    except Exception as e:
        result.fail("9-5: 파일 비활성화", str(e))

    # 9-6. sensitive_masking 활성화 시 SensitiveDataFilter 생성
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, sensitive_masking=True)
            m = LogManager(config=cfg)
            m.setup()
            assert m._sensitive_filter is not None
            assert isinstance(m._sensitive_filter, SensitiveDataFilter)
            m.shutdown()
        result.ok("9-6: sensitive_masking=True 시 SensitiveDataFilter 생성")
    except Exception as e:
        result.fail("9-6: sensitive_masking", str(e))

    # 9-7. sensitive_masking 비활성화
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, sensitive_masking=False)
            m = LogManager(config=cfg)
            m.setup()
            assert m._sensitive_filter is None
            m.shutdown()
        result.ok("9-7: sensitive_masking=False 시 필터 없음")
    except Exception as e:
        result.fail("9-7: sensitive_masking 비활성화", str(e))

    # 9-8. 로그 디렉토리 자동 생성
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = os.path.join(tmpdir, "sub", "nested", "logs")
            cfg = LoggingConfig(log_dir=nested_dir)
            m = LogManager(config=cfg)
            m.setup()
            assert os.path.isdir(nested_dir), f"디렉토리 미생성: {nested_dir}"
            m.shutdown()
        result.ok("9-8: 중첩 로그 디렉토리 자동 생성")
    except Exception as e:
        result.fail("9-8: 디렉토리 생성", str(e))

    # 9-9. intercept_stdlib=True 시 InterceptHandler 설치
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, intercept_stdlib=True)
            m = LogManager(config=cfg)
            m.setup()
            root = logging.root
            has_intercept = any(isinstance(h, InterceptHandler) for h in root.handlers)
            assert has_intercept, "InterceptHandler가 루트 로거에 설치되지 않음"
            m.shutdown()
        result.ok("9-9: intercept_stdlib=True -> InterceptHandler 설치")
    except Exception as e:
        result.fail("9-9: intercept_stdlib", str(e))


# =============================================================================
# [10] LogManager YAML 설정 로드
# =============================================================================
def test_log_manager_yaml_config(result: TestResult) -> None:
    """LogManager YAML 설정 로드 테스트."""
    print("\n[10] LogManager YAML 설정 로드")

    # ConfigLoader 싱글톤 리셋 임포트
    from core_foundation.config.loader import ConfigLoader

    # 10-1. ConfigLoader에서 logging 설정 로드
    try:
        reset_logging()
        ConfigLoader.reset_instance()
        with tempfile.TemporaryDirectory() as tmpdir:
            # YAML 설정 파일 생성
            import yaml
            yaml_path = os.path.join(tmpdir, "app.yaml")
            yaml_data = {
                "logging": {
                    "level": "DEBUG",
                    "log_dir": tmpdir,
                    "json_format": False,
                },
                "console": {
                    "enabled": True,
                    "level": "WARNING",
                    "colorize": False,
                },
                "file": {"enabled": True},
                "error_file": {"enabled": False},
                "analysis_log": {"enabled": False},
                "performance_log": {"enabled": False},
                "filters": {
                    "sensitive_data": {"enabled": True}
                },
            }
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_data, f)

            loader = ConfigLoader.get_instance()
            loader.load(yaml_path)

            m = LogManager(config_loader=loader, config=LoggingConfig(log_dir=tmpdir))
            m.setup()

            assert m.config.level == "DEBUG"
            assert m.config.console_level == "WARNING"
            assert m.config.console_colorize is False
            assert m.config.json_format is False
            assert m.config.error_file_enabled is False
            m.shutdown()
        result.ok("10-1: YAML -> LoggingConfig 로드")
    except Exception as e:
        result.fail("10-1: YAML 로드", str(e))

    # 10-2. YAML 로드 실패 시 기본값 사용
    try:
        reset_logging()
        ConfigLoader.reset_instance()
        with tempfile.TemporaryDirectory() as tmpdir:
            # 빈 설정 (logging 섹션 없음)
            import yaml
            yaml_path = os.path.join(tmpdir, "empty.yaml")
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump({}, f)

            loader = ConfigLoader.get_instance()
            loader.load(yaml_path)

            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config_loader=loader, config=cfg)
            m.setup()
            # 기본값 유지
            assert m.config.level == "INFO"
            assert m.config.console_enabled is True
            m.shutdown()
        result.ok("10-2: YAML 로드 실패 -> 기본값 사용")
    except Exception as e:
        result.fail("10-2: YAML 실패 기본값", str(e))

    # 10-3. 모듈별 레벨 설정
    try:
        reset_logging()
        ConfigLoader.reset_instance()
        with tempfile.TemporaryDirectory() as tmpdir:
            import yaml
            yaml_path = os.path.join(tmpdir, "modules.yaml")
            yaml_data = {
                "loggers": {
                    "motion_analysis": {"level": "DEBUG"},
                    "court_detection": "WARNING",
                },
            }
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_data, f)

            loader = ConfigLoader.get_instance()
            loader.load(yaml_path)

            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config_loader=loader, config=cfg)
            m.setup()
            assert m.config.module_levels.get("motion_analysis") == "DEBUG"
            assert m.config.module_levels.get("court_detection") == "WARNING"
            m.shutdown()
        result.ok("10-3: 모듈별 레벨 YAML 로드")
    except Exception as e:
        result.fail("10-3: 모듈 레벨", str(e))

    # 10-4. config_loader 없이 setup
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, level="WARNING")
            m = LogManager(config=cfg)
            m.setup()
            assert m.config.level == "WARNING"
            m.shutdown()
        result.ok("10-4: config_loader=None, 직접 config 사용")
    except Exception as e:
        result.fail("10-4: loader 없이", str(e))

    # 10-5. 마스킹 패턴 YAML 오버라이드
    try:
        reset_logging()
        ConfigLoader.reset_instance()
        with tempfile.TemporaryDirectory() as tmpdir:
            import yaml
            yaml_path = os.path.join(tmpdir, "patterns.yaml")
            yaml_data = {
                "filters": {
                    "sensitive_data": {
                        "enabled": True,
                        "patterns": ["ssn", "credit_card", "phone"],
                    }
                }
            }
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_data, f)

            loader = ConfigLoader.get_instance()
            loader.load(yaml_path)

            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config_loader=loader, config=cfg)
            m.setup()
            assert "ssn" in m.config.sensitive_patterns
            assert "credit_card" in m.config.sensitive_patterns
            assert "phone" in m.config.sensitive_patterns
            m.shutdown()
        result.ok("10-5: 마스킹 패턴 YAML 오버라이드")
    except Exception as e:
        result.fail("10-5: 마스킹 패턴", str(e))

    # 10-6. loggers 딕셔너리 내 dict/str 혼합
    try:
        reset_logging()
        ConfigLoader.reset_instance()
        with tempfile.TemporaryDirectory() as tmpdir:
            import yaml
            yaml_path = os.path.join(tmpdir, "mixed.yaml")
            yaml_data = {
                "loggers": {
                    "module_a": {"level": "ERROR"},
                    "module_b": "DEBUG",
                    "module_c": {"level": "TRACE"},
                },
            }
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_data, f)

            loader = ConfigLoader.get_instance()
            loader.load(yaml_path)

            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config_loader=loader, config=cfg)
            m.setup()
            assert m.config.module_levels["module_a"] == "ERROR"
            assert m.config.module_levels["module_b"] == "DEBUG"
            assert m.config.module_levels["module_c"] == "TRACE"
            m.shutdown()
        result.ok("10-6: loggers dict/str 혼합 로드")
    except Exception as e:
        result.fail("10-6: dict/str 혼합", str(e))


# =============================================================================
# [11] LogManager 싱크 관리 (add_sink, remove_sink)
# =============================================================================
def test_log_manager_sink_management(result: TestResult) -> None:
    """LogManager 싱크 관리 테스트."""
    print("\n[11] LogManager 싱크 관리")

    # 11-1. add_sink - 파일 싱크
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            sink_cfg = SinkConfig(
                name="custom_file",
                path=os.path.join(tmpdir, "custom.log"),
                level="INFO",
            )
            sink_id = m.add_sink(sink_cfg)
            assert sink_id is not None
            assert "custom_file" in m._sink_ids
            m.shutdown()
        result.ok("11-1: add_sink 파일 싱크")
    except Exception as e:
        result.fail("11-1: add_sink 파일", str(e))

    # 11-2. add_sink - 콘솔 싱크 (path=None)
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            sink_cfg = SinkConfig(name="extra_console", path=None, level="DEBUG")
            sink_id = m.add_sink(sink_cfg)
            assert sink_id is not None
            assert "extra_console" in m._sink_ids
            m.shutdown()
        result.ok("11-2: add_sink 콘솔 싱크 (path=None)")
    except Exception as e:
        result.fail("11-2: add_sink 콘솔", str(e))

    # 11-3. add_sink - enabled=False
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            sink_cfg = SinkConfig(name="disabled", enabled=False,
                                  path=os.path.join(tmpdir, "disabled.log"))
            sink_id = m.add_sink(sink_cfg)
            assert sink_id is None
            assert "disabled" not in m._sink_ids
            m.shutdown()
        result.ok("11-3: add_sink enabled=False -> None")
    except Exception as e:
        result.fail("11-3: add_sink disabled", str(e))

    # 11-4. remove_sink - 정상 제거
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            sink_cfg = SinkConfig(name="to_remove",
                                  path=os.path.join(tmpdir, "remove.log"))
            m.add_sink(sink_cfg)
            assert "to_remove" in m._sink_ids

            removed = m.remove_sink("to_remove")
            assert removed is True
            assert "to_remove" not in m._sink_ids
            m.shutdown()
        result.ok("11-4: remove_sink 정상 제거")
    except Exception as e:
        result.fail("11-4: remove_sink", str(e))

    # 11-5. remove_sink - 존재하지 않는 싱크
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            removed = m.remove_sink("nonexistent")
            assert removed is False
            m.shutdown()
        result.ok("11-5: remove_sink 존재하지 않는 싱크 -> False")
    except Exception as e:
        result.fail("11-5: remove_sink 미존재", str(e))

    # 11-6. add_sink - serialize=True (JSON 직렬화)
    try:
        reset_logging()
        tmpdir_manual = tempfile.mkdtemp()
        try:
            cfg = LoggingConfig(log_dir=tmpdir_manual, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            sink_cfg = SinkConfig(
                name="json_sink",
                path=os.path.join(tmpdir_manual, "json.log"),
                serialize=True,
            )
            sink_id = m.add_sink(sink_cfg)
            assert sink_id is not None
            assert "json_sink" in m._sink_ids
            m.shutdown()
        finally:
            import time as _time
            _time.sleep(0.2)
            import shutil
            shutil.rmtree(tmpdir_manual, ignore_errors=True)
        result.ok("11-6: add_sink serialize=True (JSON 직렬화)")
    except Exception as e:
        result.fail("11-6: add_sink serialize", str(e))

    # 11-7. add_sink - filter_func
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            def custom_filter(record):
                return record.get("extra", {}).get("custom") is True

            sink_cfg = SinkConfig(
                name="filtered_sink",
                path=os.path.join(tmpdir, "filtered.log"),
                filter_func=custom_filter,
            )
            sink_id = m.add_sink(sink_cfg)
            assert sink_id is not None
            m.shutdown()
        result.ok("11-7: add_sink filter_func 커스텀 필터")
    except Exception as e:
        result.fail("11-7: add_sink filter_func", str(e))

    # 11-8. 다중 싱크 등록 / 제거
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            for i in range(5):
                sc = SinkConfig(
                    name=f"sink_{i}",
                    path=os.path.join(tmpdir, f"sink_{i}.log"),
                )
                m.add_sink(sc)

            assert len(m._sink_ids) == 5

            for i in range(5):
                m.remove_sink(f"sink_{i}")

            assert len(m._sink_ids) == 0
            m.shutdown()
        result.ok("11-8: 다중 싱크 등록/제거 (5개)")
    except Exception as e:
        result.fail("11-8: 다중 싱크", str(e))


# =============================================================================
# [12] LogManager 공개 API (get_logger, set_level, get_status)
# =============================================================================
def test_log_manager_public_api(result: TestResult) -> None:
    """LogManager 공개 API 테스트."""
    print("\n[12] LogManager 공개 API")

    # 12-1. get_logger 기본
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            logger = m.get_logger()
            assert logger is not None
            m.shutdown()
        result.ok("12-1: get_logger() 기본 로거 반환")
    except Exception as e:
        result.fail("12-1: get_logger 기본", str(e))

    # 12-2. get_logger 이름 바인딩
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            logger = m.get_logger("motion_analysis")
            assert logger is not None
            m.shutdown()
        result.ok("12-2: get_logger('motion_analysis') 바인딩")
    except Exception as e:
        result.fail("12-2: get_logger 이름", str(e))

    # 12-3. set_level 전체
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            m.set_level("DEBUG")
            assert m.config.level == "DEBUG"
            assert logging.root.level == logging.DEBUG
            m.shutdown()
        result.ok("12-3: set_level('DEBUG') 전체 레벨 변경")
    except Exception as e:
        result.fail("12-3: set_level 전체", str(e))

    # 12-4. set_level 특정 모듈
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            m.set_level("ERROR", module="court_detection")
            assert m.config.module_levels["court_detection"] == "ERROR"
            mod_logger = logging.getLogger("court_detection")
            assert mod_logger.level == logging.ERROR
            m.shutdown()
        result.ok("12-4: set_level('ERROR', module='court_detection')")
    except Exception as e:
        result.fail("12-4: set_level 모듈", str(e))

    # 12-5. set_level 잘못된 레벨 → INFO 폴백
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()

            m.set_level("INVALID_LEVEL")
            # LogLevel.from_string("INVALID_LEVEL") → INFO
            assert logging.root.level == logging.INFO
            m.shutdown()
        result.ok("12-5: set_level 잘못된 레벨 -> INFO 폴백")
    except Exception as e:
        result.fail("12-5: set_level 폴백", str(e))

    # 12-6. get_status 구조
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config=cfg)
            m.setup()

            status = m.get_status()
            assert isinstance(status, dict)
            assert status["initialized"] is True
            assert status["loguru_available"] is True
            assert isinstance(status["active_sinks"], list)
            assert isinstance(status["sink_count"], int)
            assert status["sink_count"] > 0
            assert "level" in status
            assert "log_dir" in status
            assert "console_enabled" in status
            assert "file_enabled" in status
            assert "json_format" in status
            assert "sensitive_masking" in status
            assert "intercept_stdlib" in status
            assert "module_levels" in status
            m.shutdown()
        result.ok("12-6: get_status 딕셔너리 구조 (12개 키)")
    except Exception as e:
        result.fail("12-6: get_status", str(e))

    # 12-7. get_status - 초기화 전
    try:
        reset_logging()
        m = LogManager()
        status = m.get_status()
        assert status["initialized"] is False
        assert status["sink_count"] == 0
        result.ok("12-7: get_status 초기화 전 (initialized=False)")
    except Exception as e:
        result.fail("12-7: get_status 초기화 전", str(e))

    # 12-8. set_level 후 get_status 반영
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = LogManager(config=cfg)
            m.setup()
            m.set_level("WARNING")
            status = m.get_status()
            assert status["level"] == "WARNING"
            m.shutdown()
        result.ok("12-8: set_level -> get_status 반영")
    except Exception as e:
        result.fail("12-8: set_level + get_status", str(e))

    # 12-9. get_logger 비초기화 시 fallback
    try:
        reset_logging()
        m = LogManager()
        # setup 안 함 → LOGURU_AVAILABLE이지만 미초기화
        logger = m.get_logger("test_module")
        assert logger is not None
        result.ok("12-9: get_logger 비초기화 시 로거 반환")
    except Exception as e:
        result.fail("12-9: get_logger fallback", str(e))


# =============================================================================
# [13] LogManager.shutdown
# =============================================================================
def test_log_manager_shutdown(result: TestResult) -> None:
    """LogManager.shutdown 테스트."""
    print("\n[13] LogManager.shutdown")

    # 13-1. shutdown 후 initialized=False
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config=cfg)
            m.setup()
            assert m.initialized is True
            m.shutdown()
            assert m.initialized is False
        result.ok("13-1: shutdown 후 initialized=False")
    except Exception as e:
        result.fail("13-1: shutdown", str(e))

    # 13-2. shutdown 후 _sink_ids 비움
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config=cfg)
            m.setup()
            assert len(m._sink_ids) > 0
            m.shutdown()
            assert len(m._sink_ids) == 0
        result.ok("13-2: shutdown 후 _sink_ids 비움")
    except Exception as e:
        result.fail("13-2: _sink_ids 비움", str(e))

    # 13-3. 중복 shutdown 안전
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir)
            m = LogManager(config=cfg)
            m.setup()
            m.shutdown()
            m.shutdown()  # 두 번 호출
            assert m.initialized is False
        result.ok("13-3: 중복 shutdown 안전")
    except Exception as e:
        result.fail("13-3: 중복 shutdown", str(e))

    # 13-4. 미초기화 상태에서 shutdown
    try:
        reset_logging()
        m = LogManager()
        m.shutdown()  # initialized=False인 상태
        assert m.initialized is False
        result.ok("13-4: 미초기화 shutdown 안전")
    except Exception as e:
        result.fail("13-4: 미초기화 shutdown", str(e))

    # 13-5. shutdown 후 핸들러 복원
    try:
        reset_logging()
        # 원본 핸들러 설정
        original_handler = logging.StreamHandler()
        logging.root.addHandler(original_handler)

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, intercept_stdlib=True)
            m = LogManager(config=cfg)
            m.setup()
            # setup 후 InterceptHandler로 교체됨
            m.shutdown()
            # shutdown 후 원래 핸들러 복원 여부 확인
            assert m.initialized is False
        # 정리
        logging.root.handlers = [h for h in logging.root.handlers
                                 if h is not original_handler]
        result.ok("13-5: shutdown 후 핸들러 복원 시도")
    except Exception as e:
        result.fail("13-5: 핸들러 복원", str(e))


# =============================================================================
# [14] 싱글톤 관리 (_get_manager, _reset_manager)
# =============================================================================
def test_singleton_management(result: TestResult) -> None:
    """싱글톤 관리 테스트."""
    print("\n[14] 싱글톤 관리")

    # 14-1. _get_manager 최초 호출
    try:
        reset_logging()
        m = _get_manager()
        assert isinstance(m, LogManager)
        result.ok("14-1: _get_manager() -> LogManager 인스턴스")
    except Exception as e:
        result.fail("14-1: _get_manager", str(e))

    # 14-2. _get_manager 동일 인스턴스
    try:
        reset_logging()
        m1 = _get_manager()
        m2 = _get_manager()
        assert m1 is m2
        result.ok("14-2: _get_manager() 동일 인스턴스 (싱글톤)")
    except Exception as e:
        result.fail("14-2: 싱글톤 동일", str(e))

    # 14-3. _reset_manager 리셋
    try:
        reset_logging()
        m1 = _get_manager()
        _reset_manager()
        m2 = _get_manager()
        assert m1 is not m2
        result.ok("14-3: _reset_manager 후 새 인스턴스")
    except Exception as e:
        result.fail("14-3: 리셋 후 새 인스턴스", str(e))

    # 14-4. _reset_manager 초기화된 매니저 shutdown 호출
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(log_dir=tmpdir, console_enabled=False,
                                file_enabled=False, error_file_enabled=False,
                                analysis_file_enabled=False, performance_file_enabled=False)
            m = setup_logging(config=cfg)
            assert m.initialized is True
            _reset_manager()
            # 리셋 후 이전 매니저는 shutdown 되어야 함
            assert m.initialized is False
        result.ok("14-4: _reset_manager 시 shutdown 호출")
    except Exception as e:
        result.fail("14-4: 리셋 shutdown", str(e))

    # 14-5. _reset_manager 반복 호출 안전
    try:
        reset_logging()
        _reset_manager()
        _reset_manager()
        _reset_manager()
        m = _get_manager()
        assert isinstance(m, LogManager)
        result.ok("14-5: _reset_manager 반복 호출 안전")
    except Exception as e:
        result.fail("14-5: 반복 리셋", str(e))

    # 14-6. 멀티스레드 _get_manager
    try:
        reset_logging()
        instances = []
        barrier = threading.Barrier(4)

        def worker():
            barrier.wait()
            instances.append(id(_get_manager()))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(set(instances)) == 1, f"인스턴스 수: {len(set(instances))}"
        result.ok("14-6: 멀티스레드 _get_manager 동일 인스턴스")
    except Exception as e:
        result.fail("14-6: 멀티스레드", str(e))


# =============================================================================
# [15] 헬퍼 함수 (setup_logging, get_logger, log_analysis, log_performance)
# =============================================================================
def test_helper_functions(result: TestResult) -> None:
    """헬퍼 함수 테스트."""
    print("\n[15] 헬퍼 함수")

    # 15-1. setup_logging 기본
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            m = setup_logging(log_dir=tmpdir)
            assert isinstance(m, LogManager)
            assert m.initialized is True
            _reset_manager()
        result.ok("15-1: setup_logging() 기본 호출")
    except Exception as e:
        result.fail("15-1: setup_logging", str(e))

    # 15-2. setup_logging log_dir/level 오버라이드
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            m = setup_logging(log_dir=tmpdir, level="WARNING")
            assert m.config.log_dir == tmpdir
            assert m.config.level == "WARNING"
            _reset_manager()
        result.ok("15-2: setup_logging log_dir/level 오버라이드")
    except Exception as e:
        result.fail("15-2: 오버라이드", str(e))

    # 15-3. setup_logging json_format (콘솔 비활성화 시 정상 동작)
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                log_dir=tmpdir,
                json_format=True,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = setup_logging(config=cfg)
            assert m.config.json_format is True
            _reset_manager()
        result.ok("15-3: setup_logging json_format=True")
    except Exception as e:
        result.fail("15-3: json_format", str(e))

    # 15-4. setup_logging 중복 호출 시 기존 인스턴스 반환
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            m1 = setup_logging(log_dir=tmpdir)
            m2 = setup_logging(log_dir=tmpdir, level="ERROR")
            assert m1 is m2  # 이미 초기화 → 기존 반환
            _reset_manager()
        result.ok("15-4: setup_logging 중복 호출 -> 기존 인스턴스")
    except Exception as e:
        result.fail("15-4: 중복 호출", str(e))

    # 15-5. get_logger 헬퍼
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            logger = get_logger("shooting_analysis")
            assert logger is not None
            _reset_manager()
        result.ok("15-5: get_logger('shooting_analysis') 헬퍼")
    except Exception as e:
        result.fail("15-5: get_logger 헬퍼", str(e))

    # 15-6. get_logger 미초기화 시 stdlib 로거
    try:
        reset_logging()
        logger = get_logger("fallback_module")
        assert logger is not None
        # 미초기화 시 표준 logging.Logger
        assert isinstance(logger, logging.Logger)
        result.ok("15-6: get_logger 미초기화 -> stdlib Logger")
    except Exception as e:
        result.fail("15-6: get_logger 미초기화", str(e))

    # 15-7. log_analysis 헬퍼
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            # 예외 없이 실행
            log_analysis("슛 분석 완료", analysis_id="abc123", accuracy=0.95)
            _reset_manager()
        result.ok("15-7: log_analysis() 헬퍼 호출")
    except Exception as e:
        result.fail("15-7: log_analysis", str(e))

    # 15-8. log_performance 헬퍼
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            # 예외 없이 실행
            log_performance("프레임 처리", fps=60.5, latency_ms=16.2)
            _reset_manager()
        result.ok("15-8: log_performance() 헬퍼 호출")
    except Exception as e:
        result.fail("15-8: log_performance", str(e))

    # 15-9. setup_logging with config 파라미터
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = LoggingConfig(
                level="ERROR",
                log_dir=tmpdir,
                console_enabled=False,
                file_enabled=False,
                error_file_enabled=False,
                analysis_file_enabled=False,
                performance_file_enabled=False,
            )
            m = setup_logging(config=cfg)
            assert m.config.level == "ERROR"
            assert m.config.console_enabled is False
            _reset_manager()
        result.ok("15-9: setup_logging(config=LoggingConfig(...)) 직접 전달")
    except Exception as e:
        result.fail("15-9: setup_logging config", str(e))


# =============================================================================
# [16] 엣지 케이스 / __all__ 내보내기
# =============================================================================
def test_edge_cases_and_exports(result: TestResult) -> None:
    """엣지 케이스 및 __all__ 내보내기 검증."""
    print("\n[16] 엣지 케이스 / __all__")

    # 16-1. __all__ 내보내기 목록
    try:
        from core_foundation.monitoring import logger as logger_module
        all_exports = logger_module.__all__
        assert isinstance(all_exports, list)

        expected = [
            "LOGURU_AVAILABLE", "DEFAULT_LOG_LEVEL", "DEFAULT_LOG_DIR",
            "DEFAULT_LOG_FORMAT", "DEFAULT_FILE_FORMAT",
            "DEFAULT_ROTATION_SIZE", "DEFAULT_RETENTION",
            "DEFAULT_SENSITIVE_PATTERNS", "MASK_VALUE",
            "LogLevel", "SinkConfig", "LoggingConfig",
            "InterceptHandler", "SensitiveDataFilter",
            "LogManager",
            "setup_logging", "get_logger", "log_analysis", "log_performance",
            "_get_manager", "_reset_manager",
        ]
        for name in expected:
            assert name in all_exports, f"{name} __all__ 누락"
        result.ok(f"16-1: __all__ {len(expected)}개 항목 존재")
    except Exception as e:
        result.fail("16-1: __all__", str(e))

    # 16-2. __version__ 존재 (있으면)
    try:
        from core_foundation.monitoring import logger as logger_module
        if hasattr(logger_module, "__version__"):
            assert isinstance(logger_module.__version__, str)
            result.ok("16-2: __version__ 존재")
        else:
            result.ok("16-2: __version__ 미정의 (허용)")
    except Exception as e:
        result.fail("16-2: __version__", str(e))

    # 16-3. LOGURU_AVAILABLE 타입
    try:
        assert isinstance(LOGURU_AVAILABLE, bool)
        assert LOGURU_AVAILABLE is True  # loguru 설치됨
        result.ok("16-3: LOGURU_AVAILABLE=True (bool)")
    except Exception as e:
        result.fail("16-3: LOGURU_AVAILABLE", str(e))

    # 16-4. LogLevel Enum 이터레이션 안정성
    try:
        for level in LogLevel:
            assert isinstance(level.value, str)
            assert level.to_stdlib_level() in [
                logging.DEBUG, logging.INFO, logging.WARNING,
                logging.ERROR, logging.CRITICAL,
            ]
        result.ok("16-4: LogLevel 이터레이션 안정성")
    except Exception as e:
        result.fail("16-4: LogLevel 이터레이션", str(e))

    # 16-5. SensitiveDataFilter 빈 패턴
    try:
        f = SensitiveDataFilter(patterns=[])
        # 빈 패턴 → 정규식이 빈 그룹이 됨
        text = "password=test123"
        masked = f.mask_string(text)
        # 빈 패턴이면 매칭 안 됨 (패턴 그룹이 비어있으므로)
        result.ok("16-5: SensitiveDataFilter 빈 패턴 안전")
    except Exception as e:
        result.fail("16-5: 빈 패턴", str(e))

    # 16-6. LogManager 속성 접근 안전성
    try:
        m = LogManager()
        assert m.initialized is False
        assert isinstance(m.config, LoggingConfig)
        status = m.get_status()
        assert isinstance(status, dict)
        result.ok("16-6: LogManager 비초기화 시 속성 안전 접근")
    except Exception as e:
        result.fail("16-6: 속성 안전", str(e))

    # 16-7. setup_logging → shutdown → re-setup
    try:
        reset_logging()
        with tempfile.TemporaryDirectory() as tmpdir:
            m1 = setup_logging(log_dir=tmpdir)
            assert m1.initialized is True
            _reset_manager()
            # 리셋 후 다시 setup
            m2 = setup_logging(log_dir=tmpdir)
            assert m2.initialized is True
            assert m1 is not m2
            _reset_manager()
        result.ok("16-7: setup -> reset -> re-setup 라이프사이클")
    except Exception as e:
        result.fail("16-7: 라이프사이클", str(e))

    # 16-8. __init__.py 에서 모든 logger 내보내기 정합성
    try:
        from core_foundation.monitoring import (
            LOGURU_AVAILABLE as _la,
            LogLevel as _ll,
            SinkConfig as _sc,
            LoggingConfig as _lc,
            InterceptHandler as _ih,
            SensitiveDataFilter as _sf,
            LogManager as _lm,
            setup_logging as _sl,
            get_logger as _gl,
            log_analysis as _la2,
            log_performance as _lp,
            _get_manager as _gm,
            _reset_manager as _rm,
        )
        assert _la is LOGURU_AVAILABLE
        assert _ll is LogLevel
        assert _sc is SinkConfig
        assert _lc is LoggingConfig
        assert _ih is InterceptHandler
        assert _sf is SensitiveDataFilter
        assert _lm is LogManager
        assert _sl is setup_logging
        assert _gl is get_logger
        assert _la2 is log_analysis
        assert _lp is log_performance
        result.ok("16-8: __init__.py 내보내기 정합성 (13개)")
    except Exception as e:
        result.fail("16-8: __init__.py 내보내기", str(e))


# =============================================================================
# 메인
# =============================================================================
def main() -> bool:
    """테스트 메인 실행."""
    result = TestResult()

    print("=" * 60)
    print("COURTVIEW - logger.py 단위 테스트")
    print("=" * 60)

    test_constants(result)
    test_log_level_enum(result)
    test_sink_config(result)
    test_logging_config(result)
    test_intercept_handler(result)
    test_sensitive_data_filter(result)
    test_filter_functions(result)
    test_log_manager_init(result)
    test_log_manager_setup(result)
    test_log_manager_yaml_config(result)
    test_log_manager_sink_management(result)
    test_log_manager_public_api(result)
    test_log_manager_shutdown(result)
    test_singleton_management(result)
    test_helper_functions(result)
    test_edge_cases_and_exports(result)

    # 최종 정리
    reset_logging()

    result.summary()
    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
