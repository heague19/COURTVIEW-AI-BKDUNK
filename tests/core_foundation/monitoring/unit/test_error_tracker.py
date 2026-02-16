# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/monitoring/unit
파일: test_error_tracker.py
설명: ErrorTracker(에러 추적/집계/통계) 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    [1]  상수 검증 (3개)
    [2]  ErrorSeverity Enum (10개)
    [3]  TrackingCategory Enum (8개)
    [4]  ErrorContext 데이터 클래스 (7개)
    [5]  ErrorRecord 데이터 클래스 (10개)
    [6]  ErrorSummary 데이터 클래스 (5개)
    [7]  ErrorTrend 데이터 클래스 (8개)
    [8]  ErrorTracker 초기화 (6개)
    [9]  ErrorTracker.track / track_exception (10개)
    [10] ErrorTracker._store_record / FIFO (6개)
    [11] ErrorTracker.get_summary (8개)
    [12] ErrorTracker.get_trend (5개)
    [13] ErrorTracker.get_records / get_record_by_id / get_records_by_hash (8개)
    [14] ErrorTracker 유틸리티 (clear, get_count, get_status, enabled) (7개)
    [15] 싱글톤 (_get_tracker, _reset_tracker) (5개)
    [16] 헬퍼 함수 (track_error, get_error_summary) (5개)
    [17] 엣지 케이스 / __all__ (6개)

    총 117개 테스트
"""

import hashlib
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import fields
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# 테스트 대상 임포트
from core_foundation.monitoring.error_tracker import (
    # 상수
    MAX_ERROR_RECORDS,
    MAX_ERROR_HASHES,
    AGGREGATION_WINDOW_SIZE,
    # Enum
    ErrorSeverity,
    TrackingCategory,
    # 데이터 클래스
    ErrorContext,
    ErrorRecord,
    ErrorSummary,
    ErrorTrend,
    # 메인 클래스
    ErrorTracker,
    # 싱글톤
    _get_tracker,
    _reset_tracker,
    # 헬퍼 함수
    track_error,
    get_error_summary,
)

# shared 의존성
from shared.constants.error_codes import ErrorCode, ErrorCategory
from shared.exceptions.base_exception import (
    CourtViewException,
    RetryableException,
    NonRetryableException,
    CriticalException,
)

# core_foundation 의존성
from core_foundation.config.loader import ConfigLoader


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
# 헬퍼: 싱글톤 리셋
# =============================================================================
def reset_tracker():
    """ErrorTracker 싱글톤 리셋."""
    _reset_tracker()


# =============================================================================
# [1] 상수 검증
# =============================================================================
def test_constants(result: TestResult) -> None:
    """상수 값 검증."""
    print("\n[1] 상수 검증")

    # 1-1. MAX_ERROR_RECORDS
    try:
        assert isinstance(MAX_ERROR_RECORDS, int), f"타입: {type(MAX_ERROR_RECORDS)}"
        assert MAX_ERROR_RECORDS == 10000, f"값: {MAX_ERROR_RECORDS}"
        result.ok("1-1: MAX_ERROR_RECORDS = 10000")
    except Exception as e:
        result.fail("1-1: MAX_ERROR_RECORDS", str(e))

    # 1-2. MAX_ERROR_HASHES
    try:
        assert isinstance(MAX_ERROR_HASHES, int), f"타입: {type(MAX_ERROR_HASHES)}"
        assert MAX_ERROR_HASHES == 5000, f"값: {MAX_ERROR_HASHES}"
        result.ok("1-2: MAX_ERROR_HASHES = 5000")
    except Exception as e:
        result.fail("1-2: MAX_ERROR_HASHES", str(e))

    # 1-3. AGGREGATION_WINDOW_SIZE
    try:
        assert isinstance(AGGREGATION_WINDOW_SIZE, int)
        assert AGGREGATION_WINDOW_SIZE == 60, f"값: {AGGREGATION_WINDOW_SIZE}"
        result.ok("1-3: AGGREGATION_WINDOW_SIZE = 60")
    except Exception as e:
        result.fail("1-3: AGGREGATION_WINDOW_SIZE", str(e))


# =============================================================================
# [2] ErrorSeverity Enum
# =============================================================================
def test_error_severity(result: TestResult) -> None:
    """ErrorSeverity Enum 검증."""
    print("\n[2] ErrorSeverity Enum")

    # 2-1. 멤버 5개 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    try:
        members = list(ErrorSeverity)
        assert len(members) == 5, f"멤버 수: {len(members)}"
        expected_names = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        actual_names = [m.name for m in members]
        assert actual_names == expected_names, f"멤버명: {actual_names}"
        result.ok("2-1: 멤버 5개 (DEBUG~CRITICAL)")
    except Exception as e:
        result.fail("2-1: 멤버 확인", str(e))

    # 2-2. 값 확인 (10, 20, 30, 40, 50)
    try:
        assert ErrorSeverity.DEBUG.value == 10
        assert ErrorSeverity.INFO.value == 20
        assert ErrorSeverity.WARNING.value == 30
        assert ErrorSeverity.ERROR.value == 40
        assert ErrorSeverity.CRITICAL.value == 50
        result.ok("2-2: 값 (10, 20, 30, 40, 50)")
    except Exception as e:
        result.fail("2-2: 값 확인", str(e))

    # 2-3. from_logging_level - 경계값 테스트
    try:
        assert ErrorSeverity.from_logging_level(5) == ErrorSeverity.DEBUG
        assert ErrorSeverity.from_logging_level(10) == ErrorSeverity.DEBUG
        assert ErrorSeverity.from_logging_level(15) == ErrorSeverity.INFO
        assert ErrorSeverity.from_logging_level(20) == ErrorSeverity.INFO
        assert ErrorSeverity.from_logging_level(25) == ErrorSeverity.WARNING
        assert ErrorSeverity.from_logging_level(30) == ErrorSeverity.WARNING
        assert ErrorSeverity.from_logging_level(35) == ErrorSeverity.ERROR
        assert ErrorSeverity.from_logging_level(40) == ErrorSeverity.ERROR
        assert ErrorSeverity.from_logging_level(50) == ErrorSeverity.CRITICAL
        assert ErrorSeverity.from_logging_level(100) == ErrorSeverity.CRITICAL
        result.ok("2-3: from_logging_level 경계값")
    except Exception as e:
        result.fail("2-3: from_logging_level", str(e))

    # 2-4. from_exception - CriticalException
    try:
        exc = CriticalException(ErrorCode.INTERNAL_ERROR, "심각한 오류")
        sev = ErrorSeverity.from_exception(exc)
        assert sev == ErrorSeverity.CRITICAL, f"결과: {sev}"
        result.ok("2-4: from_exception(CriticalException) = CRITICAL")
    except Exception as e:
        result.fail("2-4: from_exception(CriticalException)", str(e))

    # 2-5. from_exception - NonRetryableException
    try:
        exc = NonRetryableException(ErrorCode.VALIDATION_ERROR, "검증 실패")
        sev = ErrorSeverity.from_exception(exc)
        assert sev == ErrorSeverity.ERROR, f"결과: {sev}"
        result.ok("2-5: from_exception(NonRetryableException) = ERROR")
    except Exception as e:
        result.fail("2-5: from_exception(NonRetryableException)", str(e))

    # 2-6. from_exception - RetryableException
    try:
        exc = RetryableException(ErrorCode.SERVICE_UNAVAILABLE, "재시도 가능")
        sev = ErrorSeverity.from_exception(exc)
        assert sev == ErrorSeverity.WARNING, f"결과: {sev}"
        result.ok("2-6: from_exception(RetryableException) = WARNING")
    except Exception as e:
        result.fail("2-6: from_exception(RetryableException)", str(e))

    # 2-7. from_exception - CourtViewException (기본)
    try:
        exc = CourtViewException(ErrorCode.UNKNOWN_ERROR, "기본 에러")
        sev = ErrorSeverity.from_exception(exc)
        assert sev == ErrorSeverity.ERROR, f"결과: {sev}"
        result.ok("2-7: from_exception(CourtViewException) = ERROR")
    except Exception as e:
        result.fail("2-7: from_exception(CourtViewException)", str(e))

    # 2-8. from_exception - 일반 Exception
    try:
        exc = ValueError("일반 에러")
        sev = ErrorSeverity.from_exception(exc)
        assert sev == ErrorSeverity.ERROR, f"결과: {sev}"
        result.ok("2-8: from_exception(ValueError) = ERROR")
    except Exception as e:
        result.fail("2-8: from_exception(ValueError)", str(e))

    # 2-9. __lt__ 비교 연산자
    try:
        assert ErrorSeverity.DEBUG < ErrorSeverity.INFO
        assert ErrorSeverity.INFO < ErrorSeverity.WARNING
        assert ErrorSeverity.WARNING < ErrorSeverity.ERROR
        assert ErrorSeverity.ERROR < ErrorSeverity.CRITICAL
        assert not (ErrorSeverity.CRITICAL < ErrorSeverity.DEBUG)
        # NotImplemented 반환 (다른 타입)
        assert ErrorSeverity.DEBUG.__lt__("other") is NotImplemented
        result.ok("2-9: __lt__ 비교 연산자")
    except Exception as e:
        result.fail("2-9: __lt__", str(e))

    # 2-10. __le__ 비교 연산자
    try:
        assert ErrorSeverity.DEBUG <= ErrorSeverity.DEBUG
        assert ErrorSeverity.DEBUG <= ErrorSeverity.INFO
        assert not (ErrorSeverity.CRITICAL <= ErrorSeverity.DEBUG)
        # NotImplemented 반환 (다른 타입)
        assert ErrorSeverity.DEBUG.__le__(42) is NotImplemented
        result.ok("2-10: __le__ 비교 연산자")
    except Exception as e:
        result.fail("2-10: __le__", str(e))


# =============================================================================
# [3] TrackingCategory Enum
# =============================================================================
def test_tracking_category(result: TestResult) -> None:
    """TrackingCategory Enum 검증."""
    print("\n[3] TrackingCategory Enum")

    # 3-1. 멤버 16개
    try:
        members = list(TrackingCategory)
        assert len(members) == 16, f"멤버 수: {len(members)}"
        expected = [
            "GENERAL", "AUTHENTICATION", "VALIDATION", "BUSINESS",
            "INFRASTRUCTURE", "EXTERNAL", "ANALYSIS", "DETECTION",
            "POSE", "BIOMECHANICS", "MOTION", "GAME",
            "REFEREE", "MODEL", "CONFIGURATION", "SYSTEM",
        ]
        actual = [m.name for m in members]
        assert actual == expected, f"멤버: {actual}"
        result.ok("3-1: 멤버 16개")
    except Exception as e:
        result.fail("3-1: 멤버 확인", str(e))

    # 3-2. 값 확인 (문자열)
    try:
        assert TrackingCategory.GENERAL.value == "general"
        assert TrackingCategory.AUTHENTICATION.value == "authentication"
        assert TrackingCategory.SYSTEM.value == "system"
        result.ok("3-2: 값 (문자열)")
    except Exception as e:
        result.fail("3-2: 값 확인", str(e))

    # 3-3. from_error_code - 1xxx~6xxx 범위
    try:
        assert TrackingCategory.from_error_code(ErrorCode.UNKNOWN_ERROR) == TrackingCategory.GENERAL
        assert TrackingCategory.from_error_code(ErrorCode.AUTHENTICATION_REQUIRED) == TrackingCategory.AUTHENTICATION
        assert TrackingCategory.from_error_code(ErrorCode.VALIDATION_ERROR) == TrackingCategory.VALIDATION
        assert TrackingCategory.from_error_code(ErrorCode.RESOURCE_NOT_FOUND) == TrackingCategory.BUSINESS
        assert TrackingCategory.from_error_code(ErrorCode.DATABASE_ERROR) == TrackingCategory.INFRASTRUCTURE
        assert TrackingCategory.from_error_code(ErrorCode.EXTERNAL_SERVICE_ERROR) == TrackingCategory.EXTERNAL
        result.ok("3-3: from_error_code (1xxx~6xxx)")
    except Exception as e:
        result.fail("3-3: from_error_code (1xxx~6xxx)", str(e))

    # 3-4. from_error_code - 7xxx 세분화 (분석 엔진)
    try:
        # 7000-7199: ANALYSIS
        assert TrackingCategory.from_error_code(ErrorCode.ANALYSIS_ERROR) == TrackingCategory.ANALYSIS
        # 7200-7299: DETECTION
        assert TrackingCategory.from_error_code(ErrorCode.DETECTION_ERROR) == TrackingCategory.DETECTION
        # 7300-7399: POSE
        assert TrackingCategory.from_error_code(ErrorCode.POSE_ESTIMATION_ERROR) == TrackingCategory.POSE
        # 7400-7499: BIOMECHANICS
        assert TrackingCategory.from_error_code(ErrorCode.BIOMECHANICS_ERROR) == TrackingCategory.BIOMECHANICS
        # 7500-7599: MOTION
        assert TrackingCategory.from_error_code(ErrorCode.MOTION_ANALYSIS_ERROR) == TrackingCategory.MOTION
        # 7600-7699: GAME
        assert TrackingCategory.from_error_code(ErrorCode.GAME_ANALYSIS_ERROR) == TrackingCategory.GAME
        # 7700-7999: MODEL
        assert TrackingCategory.from_error_code(ErrorCode.MODEL_ERROR) == TrackingCategory.MODEL
        result.ok("3-4: from_error_code (7xxx 세분화)")
    except Exception as e:
        result.fail("3-4: from_error_code (7xxx)", str(e))

    # 3-5. from_error_code - 8xxx (AI 심판)
    try:
        assert TrackingCategory.from_error_code(ErrorCode.REFEREE_ERROR) == TrackingCategory.REFEREE
        assert TrackingCategory.from_error_code(ErrorCode.REFEREE_RULE_NOT_FOUND) == TrackingCategory.REFEREE
        result.ok("3-5: from_error_code (8xxx REFEREE)")
    except Exception as e:
        result.fail("3-5: from_error_code (8xxx)", str(e))

    # 3-6. from_error_code - 9xxx (시스템)
    try:
        # 9000-9099: CONFIGURATION
        assert TrackingCategory.from_error_code(ErrorCode.CONFIGURATION_ERROR) == TrackingCategory.CONFIGURATION
        # 9100+: SYSTEM
        assert TrackingCategory.from_error_code(ErrorCode.INITIALIZATION_ERROR) == TrackingCategory.SYSTEM
        assert TrackingCategory.from_error_code(ErrorCode.DEPENDENCY_ERROR) == TrackingCategory.SYSTEM
        result.ok("3-6: from_error_code (9xxx)")
    except Exception as e:
        result.fail("3-6: from_error_code (9xxx)", str(e))

    # 3-7. from_error_code - VIDEO 에러 (7100-7199 = ANALYSIS)
    try:
        assert TrackingCategory.from_error_code(ErrorCode.VIDEO_ERROR) == TrackingCategory.ANALYSIS
        assert TrackingCategory.from_error_code(ErrorCode.VIDEO_CORRUPTED) == TrackingCategory.ANALYSIS
        result.ok("3-7: from_error_code (VIDEO = ANALYSIS)")
    except Exception as e:
        result.fail("3-7: from_error_code (VIDEO)", str(e))

    # 3-8. from_error_code - LEARNING 에러 (7800+ = MODEL)
    try:
        assert TrackingCategory.from_error_code(ErrorCode.LEARNING_ERROR) == TrackingCategory.MODEL
        result.ok("3-8: from_error_code (LEARNING = MODEL)")
    except Exception as e:
        result.fail("3-8: from_error_code (LEARNING)", str(e))


# =============================================================================
# [4] ErrorContext 데이터 클래스
# =============================================================================
def test_error_context(result: TestResult) -> None:
    """ErrorContext 데이터 클래스 검증."""
    print("\n[4] ErrorContext 데이터 클래스")

    # 4-1. 필드 수 (10개)
    try:
        ctx_fields = fields(ErrorContext)
        assert len(ctx_fields) == 10, f"필드 수: {len(ctx_fields)}"
        expected_names = [
            "request_id", "user_id", "session_id", "analysis_id",
            "video_id", "endpoint", "method", "ip_address",
            "user_agent", "extra",
        ]
        actual_names = [f.name for f in ctx_fields]
        assert actual_names == expected_names, f"필드: {actual_names}"
        result.ok("4-1: 필드 10개")
    except Exception as e:
        result.fail("4-1: 필드 수", str(e))

    # 4-2. 기본값 (모두 None 또는 {})
    try:
        ctx = ErrorContext()
        assert ctx.request_id is None
        assert ctx.user_id is None
        assert ctx.session_id is None
        assert ctx.analysis_id is None
        assert ctx.video_id is None
        assert ctx.endpoint is None
        assert ctx.method is None
        assert ctx.ip_address is None
        assert ctx.user_agent is None
        assert ctx.extra == {}
        result.ok("4-2: 기본값 (None / {})")
    except Exception as e:
        result.fail("4-2: 기본값", str(e))

    # 4-3. 값 설정
    try:
        ctx = ErrorContext(
            request_id="req-001",
            user_id="user-001",
            session_id="sess-001",
            analysis_id="ana-001",
            video_id="vid-001",
            endpoint="/api/analyze",
            method="POST",
            ip_address="192.168.1.1",
            user_agent="COURTVIEW/1.0",
            extra={"key": "value"},
        )
        assert ctx.request_id == "req-001"
        assert ctx.user_id == "user-001"
        assert ctx.endpoint == "/api/analyze"
        assert ctx.extra == {"key": "value"}
        result.ok("4-3: 값 설정")
    except Exception as e:
        result.fail("4-3: 값 설정", str(e))

    # 4-4. to_dict - None 제거
    try:
        ctx = ErrorContext(request_id="req-001", user_id="user-001")
        d = ctx.to_dict()
        assert "request_id" in d
        assert "user_id" in d
        # None인 필드는 제외
        assert "session_id" not in d
        assert "endpoint" not in d
        result.ok("4-4: to_dict (None 제거)")
    except Exception as e:
        result.fail("4-4: to_dict", str(e))

    # 4-5. to_dict - extra 병합
    try:
        ctx = ErrorContext(request_id="req-001", extra={"debug": True})
        d = ctx.to_dict()
        assert d["request_id"] == "req-001"
        assert d["extra"] == {"debug": True}
        result.ok("4-5: to_dict (extra 병합)")
    except Exception as e:
        result.fail("4-5: to_dict extra", str(e))

    # 4-6. from_dict - 알려진 키 분리
    try:
        data = {
            "request_id": "req-002",
            "user_id": "user-002",
            "endpoint": "/api/test",
            "unknown_key": "unknown_value",
        }
        ctx = ErrorContext.from_dict(data)
        assert ctx.request_id == "req-002"
        assert ctx.user_id == "user-002"
        assert ctx.endpoint == "/api/test"
        # unknown_key는 extra에 들어감
        assert "unknown_key" in ctx.extra
        assert ctx.extra["unknown_key"] == "unknown_value"
        result.ok("4-6: from_dict (알려진 키 분리)")
    except Exception as e:
        result.fail("4-6: from_dict", str(e))

    # 4-7. from_dict - extra 키 병합
    try:
        data = {
            "request_id": "req-003",
            "extra": {"existing": "data"},
            "new_field": "new_value",
        }
        ctx = ErrorContext.from_dict(data)
        assert ctx.request_id == "req-003"
        assert "existing" in ctx.extra
        assert "new_field" in ctx.extra
        result.ok("4-7: from_dict (extra + unknown 병합)")
    except Exception as e:
        result.fail("4-7: from_dict extra 병합", str(e))


# =============================================================================
# [5] ErrorRecord 데이터 클래스
# =============================================================================
def test_error_record(result: TestResult) -> None:
    """ErrorRecord 데이터 클래스 검증."""
    print("\n[5] ErrorRecord 데이터 클래스")

    # 5-1. 필드 수 (14개)
    try:
        rec_fields = fields(ErrorRecord)
        assert len(rec_fields) == 14, f"필드 수: {len(rec_fields)}"
        expected_names = [
            "id", "error_hash", "exception_type", "error_code",
            "error_name", "message", "severity", "category",
            "traceback", "context", "occurred_at", "is_retryable",
            "is_critical", "tags",
        ]
        actual_names = [f.name for f in rec_fields]
        assert actual_names == expected_names, f"필드: {actual_names}"
        result.ok("5-1: 필드 14개")
    except Exception as e:
        result.fail("5-1: 필드 수", str(e))

    # 5-2. 기본값
    try:
        record = ErrorRecord()
        # id: UUID 형식
        assert len(record.id) == 36, f"ID 길이: {len(record.id)}"
        uuid.UUID(record.id)  # UUID 유효성
        # error_hash: __post_init__에서 자동 생성
        assert len(record.error_hash) == 16, f"해시 길이: {len(record.error_hash)}"
        assert record.exception_type == ""
        assert record.error_code is None
        assert record.error_name == ""
        assert record.message == ""
        assert record.severity == ErrorSeverity.ERROR
        assert record.category == TrackingCategory.GENERAL
        assert record.traceback == ""
        assert isinstance(record.context, ErrorContext)
        assert isinstance(record.occurred_at, datetime)
        assert record.is_retryable is False
        assert record.is_critical is False
        assert record.tags == []
        result.ok("5-2: 기본값")
    except Exception as e:
        result.fail("5-2: 기본값", str(e))

    # 5-3. __post_init__ - error_hash 자동 생성
    try:
        record = ErrorRecord(exception_type="ValueError", message="테스트 에러")
        assert record.error_hash != ""
        assert len(record.error_hash) == 16  # MD5의 처음 16자
        result.ok("5-3: __post_init__ 해시 자동 생성")
    except Exception as e:
        result.fail("5-3: __post_init__", str(e))

    # 5-4. _generate_hash - 동일 에러 동일 해시
    try:
        r1 = ErrorRecord(exception_type="ValueError", error_name="TEST", message="same error")
        r2 = ErrorRecord(exception_type="ValueError", error_name="TEST", message="same error")
        assert r1.error_hash == r2.error_hash, "동일 에러의 해시가 달라짐"
        result.ok("5-4: 동일 에러 동일 해시")
    except Exception as e:
        result.fail("5-4: 동일 해시", str(e))

    # 5-5. _generate_hash - 다른 에러 다른 해시
    try:
        r1 = ErrorRecord(exception_type="ValueError", message="error A")
        r2 = ErrorRecord(exception_type="TypeError", message="error B")
        assert r1.error_hash != r2.error_hash, "다른 에러인데 해시가 같음"
        result.ok("5-5: 다른 에러 다른 해시")
    except Exception as e:
        result.fail("5-5: 다른 해시", str(e))

    # 5-6. _normalize_traceback - 파일명/라인 추출
    try:
        tb_text = (
            'Traceback (most recent call last):\n'
            '  File "test.py", line 10, in test_func\n'
            '    result = func()\n'
            '  File "module.py", line 20, in func\n'
            '    raise ValueError("error")\n'
            'ValueError: error'
        )
        record = ErrorRecord(traceback=tb_text)
        normalized = record._normalize_traceback()
        assert 'File "test.py"' in normalized
        assert 'File "module.py"' in normalized
        result.ok("5-6: _normalize_traceback")
    except Exception as e:
        result.fail("5-6: _normalize_traceback", str(e))

    # 5-7. _normalize_traceback - 빈 traceback
    try:
        record = ErrorRecord(traceback="")
        normalized = record._normalize_traceback()
        assert normalized == "", f"결과: '{normalized}'"
        result.ok("5-7: _normalize_traceback (빈 traceback)")
    except Exception as e:
        result.fail("5-7: _normalize_traceback 빈", str(e))

    # 5-8. to_dict
    try:
        record = ErrorRecord(
            exception_type="ValueError",
            error_code=ErrorCode.VALIDATION_ERROR,
            error_name="VALIDATION_ERROR",
            message="검증 실패",
            severity=ErrorSeverity.ERROR,
            category=TrackingCategory.VALIDATION,
            is_retryable=False,
            is_critical=False,
            tags=["test"],
        )
        d = record.to_dict()
        assert d["exception_type"] == "ValueError"
        assert d["error_code"] == 3000  # VALIDATION_ERROR 코드
        assert d["error_name"] == "VALIDATION_ERROR"
        assert d["message"] == "검증 실패"
        assert d["severity"] == "ERROR"
        assert d["category"] == "validation"
        assert isinstance(d["occurred_at"], str)  # ISO 포맷
        assert d["is_retryable"] is False
        assert d["is_critical"] is False
        assert d["tags"] == ["test"]
        result.ok("5-8: to_dict")
    except Exception as e:
        result.fail("5-8: to_dict", str(e))

    # 5-9. from_exception - CourtViewException
    try:
        exc = CourtViewException(
            ErrorCode.ANALYSIS_ERROR,
            "분석 오류",
            details={"video_id": "v001"},
            context={"user_id": "u001"},
        )
        try:
            raise exc
        except CourtViewException as caught_exc:
            record = ErrorRecord.from_exception(caught_exc, tags=["analysis"])

        assert record.exception_type == "CourtViewException"
        assert record.error_code == ErrorCode.ANALYSIS_ERROR
        assert record.error_name == "ANALYSIS_ERROR"
        assert record.message == "분석 오류"
        assert record.severity == ErrorSeverity.ERROR
        assert record.category == TrackingCategory.ANALYSIS
        assert record.is_retryable is False
        assert record.is_critical is False
        assert record.tags == ["analysis"]
        # 컨텍스트 병합 확인
        assert "user_id" in record.context.extra
        assert "details" in record.context.extra
        result.ok("5-9: from_exception(CourtViewException)")
    except Exception as e:
        result.fail("5-9: from_exception(CourtViewException)", str(e))

    # 5-10. from_exception - 일반 Exception
    try:
        exc = ValueError("일반 에러 메시지")
        try:
            raise exc
        except ValueError as caught_exc:
            record = ErrorRecord.from_exception(caught_exc)

        assert record.exception_type == "ValueError"
        assert record.error_code == ErrorCode.UNKNOWN_ERROR
        assert record.error_name == "ValueError"
        assert record.message == "일반 에러 메시지"
        assert record.severity == ErrorSeverity.ERROR
        assert record.traceback != ""  # 스택 트레이스 존재
        result.ok("5-10: from_exception(ValueError)")
    except Exception as e:
        result.fail("5-10: from_exception(ValueError)", str(e))


# =============================================================================
# [6] ErrorSummary 데이터 클래스
# =============================================================================
def test_error_summary(result: TestResult) -> None:
    """ErrorSummary 데이터 클래스 검증."""
    print("\n[6] ErrorSummary 데이터 클래스")

    # 6-1. 필드 수 (9개)
    try:
        summary_fields = fields(ErrorSummary)
        assert len(summary_fields) == 9, f"필드 수: {len(summary_fields)}"
        expected_names = [
            "period_start", "period_end", "total_count", "unique_count",
            "by_severity", "by_category", "by_error_code", "top_errors",
            "error_rate",
        ]
        actual_names = [f.name for f in summary_fields]
        assert actual_names == expected_names, f"필드: {actual_names}"
        result.ok("6-1: 필드 9개")
    except Exception as e:
        result.fail("6-1: 필드 수", str(e))

    # 6-2. 기본값
    try:
        summary = ErrorSummary()
        assert isinstance(summary.period_start, datetime)
        assert isinstance(summary.period_end, datetime)
        assert summary.total_count == 0
        assert summary.unique_count == 0
        assert summary.by_severity == {}
        assert summary.by_category == {}
        assert summary.by_error_code == {}
        assert summary.top_errors == []
        assert summary.error_rate == 0.0
        result.ok("6-2: 기본값")
    except Exception as e:
        result.fail("6-2: 기본값", str(e))

    # 6-3. to_dict
    try:
        now = datetime.now(timezone.utc)
        summary = ErrorSummary(
            period_start=now - timedelta(hours=1),
            period_end=now,
            total_count=10,
            unique_count=5,
            by_severity={"ERROR": 8, "WARNING": 2},
            by_category={"general": 6, "validation": 4},
            by_error_code={"UNKNOWN_ERROR": 3},
            top_errors=[("hash1", 5, "에러 메시지")],
            error_rate=0.167,
        )
        d = summary.to_dict()
        assert isinstance(d["period_start"], str)
        assert d["total_count"] == 10
        assert d["unique_count"] == 5
        assert d["by_severity"] == {"ERROR": 8, "WARNING": 2}
        # top_errors 구조 확인
        assert len(d["top_errors"]) == 1
        assert d["top_errors"][0]["hash"] == "hash1"
        assert d["top_errors"][0]["count"] == 5
        assert d["error_rate"] == 0.17  # round(0.167, 2)
        result.ok("6-3: to_dict")
    except Exception as e:
        result.fail("6-3: to_dict", str(e))

    # 6-4. to_dict - 빈 top_errors
    try:
        summary = ErrorSummary()
        d = summary.to_dict()
        assert d["top_errors"] == []
        assert d["total_count"] == 0
        result.ok("6-4: to_dict (빈 데이터)")
    except Exception as e:
        result.fail("6-4: to_dict 빈", str(e))

    # 6-5. to_dict - error_rate 반올림
    try:
        summary = ErrorSummary(error_rate=1.23456)
        d = summary.to_dict()
        assert d["error_rate"] == 1.23, f"error_rate: {d['error_rate']}"
        result.ok("6-5: to_dict error_rate 반올림")
    except Exception as e:
        result.fail("6-5: error_rate 반올림", str(e))


# =============================================================================
# [7] ErrorTrend 데이터 클래스
# =============================================================================
def test_error_trend(result: TestResult) -> None:
    """ErrorTrend 데이터 클래스 검증."""
    print("\n[7] ErrorTrend 데이터 클래스")

    # 7-1. 필드 수 (5개)
    try:
        trend_fields = fields(ErrorTrend)
        assert len(trend_fields) == 5, f"필드 수: {len(trend_fields)}"
        expected_names = [
            "time_slots", "counts", "slot_duration_minutes",
            "trend_direction", "change_percentage",
        ]
        actual_names = [f.name for f in trend_fields]
        assert actual_names == expected_names, f"필드: {actual_names}"
        result.ok("7-1: 필드 5개")
    except Exception as e:
        result.fail("7-1: 필드 수", str(e))

    # 7-2. 기본값
    try:
        trend = ErrorTrend()
        assert trend.time_slots == []
        assert trend.counts == []
        assert trend.slot_duration_minutes == 5
        assert trend.trend_direction == "stable"
        assert trend.change_percentage == 0.0
        result.ok("7-2: 기본값")
    except Exception as e:
        result.fail("7-2: 기본값", str(e))

    # 7-3. to_dict
    try:
        trend = ErrorTrend(
            time_slots=["2026-01-01T00:00:00+00:00"],
            counts=[5],
            slot_duration_minutes=10,
            trend_direction="increasing",
            change_percentage=50.123,
        )
        d = trend.to_dict()
        assert d["time_slots"] == ["2026-01-01T00:00:00+00:00"]
        assert d["counts"] == [5]
        assert d["slot_duration_minutes"] == 10
        assert d["trend_direction"] == "increasing"
        assert d["change_percentage"] == 50.12  # round(50.123, 2)
        result.ok("7-3: to_dict")
    except Exception as e:
        result.fail("7-3: to_dict", str(e))

    # 7-4. calculate_trend - 빈 레코드
    try:
        trend = ErrorTrend.calculate_trend([], slot_minutes=5, window_hours=1)
        assert trend.trend_direction == "stable"
        assert trend.change_percentage == 0.0
        # 슬롯 수 = (1시간 * 60분) / 5분 = 12개
        assert len(trend.time_slots) == 12
        assert all(c == 0 for c in trend.counts)
        result.ok("7-4: calculate_trend (빈 레코드)")
    except Exception as e:
        result.fail("7-4: calculate_trend 빈", str(e))

    # 7-5. calculate_trend - 증가 추세 (후반부에만 에러)
    try:
        now = datetime.now(timezone.utc)
        # 후반 30분에만 에러 배치
        records = []
        for i in range(10):
            record = ErrorRecord(
                exception_type="TestError",
                message=f"에러 {i}",
                occurred_at=now - timedelta(minutes=5),
            )
            records.append(record)

        trend = ErrorTrend.calculate_trend(records, slot_minutes=5, window_hours=1)
        assert trend.trend_direction == "increasing", f"방향: {trend.trend_direction}"
        result.ok("7-5: calculate_trend (증가 추세)")
    except Exception as e:
        result.fail("7-5: calculate_trend 증가", str(e))

    # 7-6. calculate_trend - 감소 추세 (전반부에만 에러)
    try:
        now = datetime.now(timezone.utc)
        records = []
        for i in range(10):
            record = ErrorRecord(
                exception_type="TestError",
                message=f"에러 {i}",
                occurred_at=now - timedelta(minutes=55),
            )
            records.append(record)

        trend = ErrorTrend.calculate_trend(records, slot_minutes=5, window_hours=1)
        assert trend.trend_direction == "decreasing", f"방향: {trend.trend_direction}"
        result.ok("7-6: calculate_trend (감소 추세)")
    except Exception as e:
        result.fail("7-6: calculate_trend 감소", str(e))

    # 7-7. calculate_trend - 안정 추세 (전반부 == 후반부)
    try:
        now = datetime.now(timezone.utc)
        records = []
        # 전반부와 후반부 균등 배치
        for i in range(5):
            records.append(ErrorRecord(
                exception_type="TestError",
                message=f"에러 {i}",
                occurred_at=now - timedelta(minutes=50),  # 전반부
            ))
        for i in range(5):
            records.append(ErrorRecord(
                exception_type="TestError",
                message=f"에러 {i+5}",
                occurred_at=now - timedelta(minutes=10),  # 후반부
            ))

        trend = ErrorTrend.calculate_trend(records, slot_minutes=5, window_hours=1)
        assert trend.trend_direction == "stable", f"방향: {trend.trend_direction}"
        result.ok("7-7: calculate_trend (안정 추세)")
    except Exception as e:
        result.fail("7-7: calculate_trend 안정", str(e))

    # 7-8. calculate_trend - 슬롯 수 계산
    try:
        trend = ErrorTrend.calculate_trend([], slot_minutes=10, window_hours=2)
        # 슬롯 수 = (2 * 60) / 10 = 12개
        assert len(trend.time_slots) == 12, f"슬롯 수: {len(trend.time_slots)}"
        assert len(trend.counts) == 12
        assert trend.slot_duration_minutes == 10
        result.ok("7-8: calculate_trend 슬롯 수 계산")
    except Exception as e:
        result.fail("7-8: 슬롯 수 계산", str(e))


# =============================================================================
# [8] ErrorTracker 초기화
# =============================================================================
def test_tracker_init(result: TestResult) -> None:
    """ErrorTracker 초기화 검증."""
    print("\n[8] ErrorTracker 초기화")
    reset_tracker()

    # 8-1. 기본 초기화
    try:
        tracker = ErrorTracker()
        assert tracker._enabled is True
        assert tracker._max_records == MAX_ERROR_RECORDS
        assert isinstance(tracker._records, deque)
        assert tracker._records.maxlen == MAX_ERROR_RECORDS
        assert len(tracker._records) == 0
        result.ok("8-1: 기본 초기화")
    except Exception as e:
        result.fail("8-1: 기본 초기화", str(e))

    # 8-2. 커스텀 max_records
    try:
        tracker = ErrorTracker(max_records=100)
        assert tracker._max_records == 100
        assert tracker._records.maxlen == 100
        result.ok("8-2: 커스텀 max_records=100")
    except Exception as e:
        result.fail("8-2: 커스텀 max_records", str(e))

    # 8-3. disabled 상태
    try:
        tracker = ErrorTracker(enabled=False)
        assert tracker._enabled is False
        assert tracker.enabled is False
        result.ok("8-3: disabled 상태")
    except Exception as e:
        result.fail("8-3: disabled", str(e))

    # 8-4. 내부 자료구조 초기화
    try:
        tracker = ErrorTracker()
        assert isinstance(tracker._error_hashes, dict)
        assert len(tracker._error_hashes) == 0
        assert len(tracker._error_counts) == 0
        assert len(tracker._error_messages) == 0
        assert isinstance(tracker._lock, type(threading.RLock()))
        result.ok("8-4: 내부 자료구조")
    except Exception as e:
        result.fail("8-4: 내부 자료구조", str(e))

    # 8-5. ConfigLoader 주입
    try:
        loader = ConfigLoader.get_instance()
        tracker = ErrorTracker(config_loader=loader)
        assert tracker._config_loader is loader
        result.ok("8-5: ConfigLoader 주입")
    except Exception as e:
        result.fail("8-5: ConfigLoader 주입", str(e))

    # 8-6. ConfigLoader 미주입 (싱글톤 사용)
    try:
        tracker = ErrorTracker()
        assert tracker._config_loader is not None
        result.ok("8-6: ConfigLoader 미주입 (싱글톤)")
    except Exception as e:
        result.fail("8-6: ConfigLoader 미주입", str(e))


# =============================================================================
# [9] ErrorTracker.track / track_exception
# =============================================================================
def test_tracker_track(result: TestResult) -> None:
    """ErrorTracker.track / track_exception 검증."""
    print("\n[9] ErrorTracker.track / track_exception")
    reset_tracker()

    # 9-1. 일반 Exception 추적
    try:
        tracker = ErrorTracker(max_records=1000)
        exc = ValueError("테스트 에러")
        try:
            raise exc
        except ValueError as e:
            record = tracker.track(e)

        assert isinstance(record, ErrorRecord)
        assert record.exception_type == "ValueError"
        assert record.message == "테스트 에러"
        assert len(tracker._records) == 1
        result.ok("9-1: 일반 Exception 추적")
    except Exception as e:
        result.fail("9-1: Exception 추적", str(e))

    # 9-2. CourtViewException 추적
    try:
        tracker = ErrorTracker(max_records=1000)
        exc = CourtViewException(
            ErrorCode.ANALYSIS_ERROR, "분석 실패",
            details={"video_id": "v001"},
        )
        try:
            raise exc
        except CourtViewException as e:
            record = tracker.track(e)

        assert record.error_code == ErrorCode.ANALYSIS_ERROR
        assert record.error_name == "ANALYSIS_ERROR"
        assert record.category == TrackingCategory.ANALYSIS
        result.ok("9-2: CourtViewException 추적")
    except Exception as e:
        result.fail("9-2: CourtViewException 추적", str(e))

    # 9-3. RetryableException 플래그
    try:
        tracker = ErrorTracker(max_records=1000)
        exc = RetryableException(ErrorCode.SERVICE_UNAVAILABLE, "재시도 필요")
        try:
            raise exc
        except RetryableException as e:
            record = tracker.track(e)

        assert record.is_retryable is True
        assert record.severity == ErrorSeverity.WARNING
        result.ok("9-3: RetryableException 플래그")
    except Exception as e:
        result.fail("9-3: RetryableException", str(e))

    # 9-4. CriticalException 플래그
    try:
        tracker = ErrorTracker(max_records=1000)
        exc = CriticalException(ErrorCode.INTERNAL_ERROR, "심각한 오류")
        try:
            raise exc
        except CriticalException as e:
            record = tracker.track(e)

        assert record.is_critical is True
        assert record.severity == ErrorSeverity.CRITICAL
        result.ok("9-4: CriticalException 플래그")
    except Exception as e:
        result.fail("9-4: CriticalException", str(e))

    # 9-5. 컨텍스트 전달 (dict)
    try:
        tracker = ErrorTracker(max_records=1000)
        exc = ValueError("에러")
        try:
            raise exc
        except ValueError as e:
            record = tracker.track(e, context={"user_id": "u001", "endpoint": "/test"})

        assert record.context.user_id == "u001"
        assert record.context.endpoint == "/test"
        result.ok("9-5: 컨텍스트 전달 (dict)")
    except Exception as e:
        result.fail("9-5: 컨텍스트 dict", str(e))

    # 9-6. 컨텍스트 전달 (ErrorContext)
    try:
        tracker = ErrorTracker(max_records=1000)
        ctx = ErrorContext(request_id="req-001", analysis_id="ana-001")
        exc = ValueError("에러")
        try:
            raise exc
        except ValueError as e:
            record = tracker.track(e, context=ctx)

        assert record.context.request_id == "req-001"
        assert record.context.analysis_id == "ana-001"
        result.ok("9-6: 컨텍스트 전달 (ErrorContext)")
    except Exception as e:
        result.fail("9-6: 컨텍스트 ErrorContext", str(e))

    # 9-7. 심각도 수동 지정
    try:
        tracker = ErrorTracker(max_records=1000)
        exc = ValueError("에러")
        try:
            raise exc
        except ValueError as e:
            record = tracker.track(e, severity=ErrorSeverity.CRITICAL)

        assert record.severity == ErrorSeverity.CRITICAL
        result.ok("9-7: 심각도 수동 지정")
    except Exception as e:
        result.fail("9-7: 심각도 수동", str(e))

    # 9-8. 태그 전달
    try:
        tracker = ErrorTracker(max_records=1000)
        exc = ValueError("에러")
        try:
            raise exc
        except ValueError as e:
            record = tracker.track(e, tags=["analysis", "video"])

        assert record.tags == ["analysis", "video"]
        result.ok("9-8: 태그 전달")
    except Exception as e:
        result.fail("9-8: 태그", str(e))

    # 9-9. disabled 상태에서 추적
    try:
        tracker = ErrorTracker(max_records=1000, enabled=False)
        exc = ValueError("비활성 에러")
        try:
            raise exc
        except ValueError as e:
            record = tracker.track(e)

        assert isinstance(record, ErrorRecord)
        # 비활성 상태에서는 레코드가 저장되지 않음
        assert len(tracker._records) == 0
        result.ok("9-9: disabled 상태 (저장 안 됨)")
    except Exception as e:
        result.fail("9-9: disabled 추적", str(e))

    # 9-10. track_exception (sys.exc_info 형식)
    try:
        tracker = ErrorTracker(max_records=1000)
        exc = ValueError("exc_info 테스트")
        try:
            raise exc
        except ValueError as e:
            import sys as _sys
            exc_type, exc_value, exc_tb = _sys.exc_info()
            record = tracker.track_exception(exc_type, exc_value, exc_tb, context={"test": True})

        assert record.exception_type == "ValueError"
        assert record.message == "exc_info 테스트"
        result.ok("9-10: track_exception (sys.exc_info)")
    except Exception as e:
        result.fail("9-10: track_exception", str(e))


# =============================================================================
# [10] ErrorTracker._store_record / FIFO
# =============================================================================
def test_tracker_store_fifo(result: TestResult) -> None:
    """ErrorTracker FIFO 저장소 검증."""
    print("\n[10] ErrorTracker._store_record / FIFO")
    reset_tracker()

    # 10-1. deque maxlen 동작
    try:
        tracker = ErrorTracker(max_records=5)
        for i in range(7):
            exc = ValueError(f"에러 {i}")
            try:
                raise exc
            except ValueError as e:
                tracker.track(e)

        assert len(tracker._records) == 5, f"레코드 수: {len(tracker._records)}"
        # 가장 오래된 것(0, 1)은 제거되고 2~6만 남음
        messages = [r.message for r in tracker._records]
        assert "에러 2" in messages[0], f"첫 메시지: {messages[0]}"
        assert "에러 6" in messages[-1], f"마지막 메시지: {messages[-1]}"
        result.ok("10-1: deque maxlen FIFO")
    except Exception as e:
        result.fail("10-1: FIFO", str(e))

    # 10-2. 해시 카운트 업데이트
    try:
        tracker = ErrorTracker(max_records=1000)
        # 동일 에러 3번
        for _ in range(3):
            record = ErrorRecord(
                exception_type="ValueError",
                error_name="TEST",
                message="같은 에러",
            )
            tracker.track(record)

        # 해시가 하나이고 카운트 3
        assert len(tracker._error_counts) == 1
        hash_key = list(tracker._error_counts.keys())[0]
        assert tracker._error_counts[hash_key] == 3
        result.ok("10-2: 해시 카운트 업데이트")
    except Exception as e:
        result.fail("10-2: 해시 카운트", str(e))

    # 10-3. 해시 정리 (FIFO로 오래된 레코드 제거 시)
    try:
        tracker = ErrorTracker(max_records=3)
        # 서로 다른 에러 5개 추가 (maxlen=3이므로 앞 2개 제거됨)
        records_added = []
        for i in range(5):
            record = ErrorRecord(
                exception_type=f"Error{i}",
                error_name=f"ERR_{i}",
                message=f"에러 {i}",
            )
            tracker.track(record)
            records_added.append(record)

        assert len(tracker._records) == 3
        # 카운트가 0이 된 해시는 정리됨
        remaining_hashes = set(r.error_hash for r in tracker._records)
        for h in remaining_hashes:
            assert h in tracker._error_counts
        result.ok("10-3: 해시 정리")
    except Exception as e:
        result.fail("10-3: 해시 정리", str(e))

    # 10-4. ErrorRecord 직접 전달
    try:
        tracker = ErrorTracker(max_records=1000)
        record = ErrorRecord(
            exception_type="DirectError",
            message="직접 전달 레코드",
            severity=ErrorSeverity.WARNING,
        )
        returned = tracker.track(record)

        assert returned is record
        assert len(tracker._records) == 1
        assert tracker._records[0].message == "직접 전달 레코드"
        result.ok("10-4: ErrorRecord 직접 전달")
    except Exception as e:
        result.fail("10-4: ErrorRecord 직접 전달", str(e))

    # 10-5. 메시지 저장 (100자 제한)
    try:
        tracker = ErrorTracker(max_records=1000)
        long_msg = "A" * 200
        record = ErrorRecord(
            exception_type="LongError",
            message=long_msg,
        )
        tracker.track(record)

        stored_msg = tracker._error_messages[record.error_hash]
        assert len(stored_msg) == 100, f"저장 메시지 길이: {len(stored_msg)}"
        result.ok("10-5: 메시지 저장 (100자 제한)")
    except Exception as e:
        result.fail("10-5: 메시지 100자", str(e))

    # 10-6. _log_error 호출 (심각도별 로깅 레벨)
    try:
        tracker = ErrorTracker(max_records=1000)
        # CRITICAL, ERROR, WARNING, INFO, DEBUG 각각 추적
        for sev in ErrorSeverity:
            record = ErrorRecord(
                exception_type="TestError",
                message=f"{sev.name} 에러",
                severity=sev,
            )
            tracker.track(record)

        assert len(tracker._records) == 5
        result.ok("10-6: _log_error 심각도별 로깅")
    except Exception as e:
        result.fail("10-6: _log_error", str(e))


# =============================================================================
# [11] ErrorTracker.get_summary
# =============================================================================
def test_tracker_get_summary(result: TestResult) -> None:
    """ErrorTracker.get_summary 검증."""
    print("\n[11] ErrorTracker.get_summary")
    reset_tracker()

    # 에러 데이터 준비
    tracker = ErrorTracker(max_records=1000)
    now = datetime.now(timezone.utc)

    # 다양한 에러 추가
    errors_data = [
        ("ValueError", ErrorCode.VALIDATION_ERROR, ErrorSeverity.ERROR, TrackingCategory.VALIDATION),
        ("ValueError", ErrorCode.VALIDATION_ERROR, ErrorSeverity.ERROR, TrackingCategory.VALIDATION),
        ("TypeError", ErrorCode.UNKNOWN_ERROR, ErrorSeverity.WARNING, TrackingCategory.GENERAL),
        ("RuntimeError", ErrorCode.ANALYSIS_ERROR, ErrorSeverity.CRITICAL, TrackingCategory.ANALYSIS),
        ("IOError", ErrorCode.DATABASE_ERROR, ErrorSeverity.ERROR, TrackingCategory.INFRASTRUCTURE),
    ]
    for exc_type, code, sev, cat in errors_data:
        record = ErrorRecord(
            exception_type=exc_type,
            error_code=code,
            error_name=code.name,
            message=f"{exc_type} 에러",
            severity=sev,
            category=cat,
            occurred_at=now - timedelta(minutes=30),
        )
        tracker.track(record)

    # 11-1. 기본 요약
    try:
        summary = tracker.get_summary(hours=24)
        assert summary.total_count == 5, f"전체: {summary.total_count}"
        assert isinstance(summary.period_start, datetime)
        assert isinstance(summary.period_end, datetime)
        result.ok("11-1: 기본 요약 (5개)")
    except Exception as e:
        result.fail("11-1: 기본 요약", str(e))

    # 11-2. 고유 에러 수
    try:
        summary = tracker.get_summary(hours=24)
        # 5개 레코드이지만 동일한 에러가 2개 있으므로 고유 수는 4 이하
        assert summary.unique_count <= 5
        assert summary.unique_count >= 1
        result.ok("11-2: 고유 에러 수")
    except Exception as e:
        result.fail("11-2: 고유 에러 수", str(e))

    # 11-3. by_severity
    try:
        summary = tracker.get_summary(hours=24)
        assert "ERROR" in summary.by_severity
        assert summary.by_severity["ERROR"] == 3  # ValueError*2 + IOError
        assert summary.by_severity.get("WARNING", 0) == 1
        assert summary.by_severity.get("CRITICAL", 0) == 1
        result.ok("11-3: by_severity")
    except Exception as e:
        result.fail("11-3: by_severity", str(e))

    # 11-4. by_category
    try:
        summary = tracker.get_summary(hours=24)
        assert "validation" in summary.by_category
        assert summary.by_category["validation"] == 2
        assert "general" in summary.by_category
        assert "analysis" in summary.by_category
        result.ok("11-4: by_category")
    except Exception as e:
        result.fail("11-4: by_category", str(e))

    # 11-5. min_severity 필터
    try:
        summary = tracker.get_summary(hours=24, min_severity=ErrorSeverity.ERROR)
        # ERROR(3) + CRITICAL(1) = 4
        assert summary.total_count == 4, f"전체: {summary.total_count}"
        result.ok("11-5: min_severity 필터")
    except Exception as e:
        result.fail("11-5: min_severity", str(e))

    # 11-6. category 필터
    try:
        summary = tracker.get_summary(hours=24, category=TrackingCategory.VALIDATION)
        assert summary.total_count == 2, f"전체: {summary.total_count}"
        result.ok("11-6: category 필터")
    except Exception as e:
        result.fail("11-6: category 필터", str(e))

    # 11-7. top_errors
    try:
        summary = tracker.get_summary(hours=24)
        assert len(summary.top_errors) <= 10  # 최대 10개
        if summary.top_errors:
            # 가장 많이 발생한 에러가 첫 번째
            top_hash, top_count, top_msg = summary.top_errors[0]
            assert top_count >= 1
            assert isinstance(top_hash, str)
            assert isinstance(top_msg, str)
        result.ok("11-7: top_errors")
    except Exception as e:
        result.fail("11-7: top_errors", str(e))

    # 11-8. error_rate (분당)
    try:
        summary = tracker.get_summary(hours=1)
        # 1시간 = 60분, 5개 에러 -> 5/60 = 0.0833...
        assert summary.error_rate > 0, f"에러율: {summary.error_rate}"
        expected_rate = 5 / 60
        assert abs(summary.error_rate - expected_rate) < 0.01
        result.ok("11-8: error_rate (분당)")
    except Exception as e:
        result.fail("11-8: error_rate", str(e))


# =============================================================================
# [12] ErrorTracker.get_trend
# =============================================================================
def test_tracker_get_trend(result: TestResult) -> None:
    """ErrorTracker.get_trend 검증."""
    print("\n[12] ErrorTracker.get_trend")
    reset_tracker()

    # 12-1. 빈 추적기
    try:
        tracker = ErrorTracker(max_records=1000)
        trend = tracker.get_trend(hours=1, slot_minutes=5)
        assert trend.trend_direction == "stable"
        assert len(trend.time_slots) == 12  # 60분 / 5분
        result.ok("12-1: 빈 추적기")
    except Exception as e:
        result.fail("12-1: 빈 추적기", str(e))

    # 12-2. 에러 데이터로 추세 확인
    try:
        tracker = ErrorTracker(max_records=1000)
        now = datetime.now(timezone.utc)
        # 최근 10분에 에러 집중 (증가 추세)
        for i in range(10):
            record = ErrorRecord(
                exception_type="TestError",
                message=f"에러 {i}",
                occurred_at=now - timedelta(minutes=3),
            )
            tracker.track(record)

        trend = tracker.get_trend(hours=1, slot_minutes=5)
        assert trend.trend_direction == "increasing", f"방향: {trend.trend_direction}"
        result.ok("12-2: 에러 데이터 추세")
    except Exception as e:
        result.fail("12-2: 추세 확인", str(e))

    # 12-3. category 필터
    try:
        tracker = ErrorTracker(max_records=1000)
        now = datetime.now(timezone.utc)
        # VALIDATION 에러
        record = ErrorRecord(
            exception_type="ValError",
            message="검증 에러",
            category=TrackingCategory.VALIDATION,
            occurred_at=now - timedelta(minutes=5),
        )
        tracker.track(record)
        # GENERAL 에러
        record2 = ErrorRecord(
            exception_type="GenError",
            message="일반 에러",
            category=TrackingCategory.GENERAL,
            occurred_at=now - timedelta(minutes=5),
        )
        tracker.track(record2)

        # VALIDATION만 필터
        trend = tracker.get_trend(hours=1, category=TrackingCategory.VALIDATION)
        total = sum(trend.counts)
        assert total == 1, f"VALIDATION 에러 수: {total}"
        result.ok("12-3: category 필터")
    except Exception as e:
        result.fail("12-3: category 필터", str(e))

    # 12-4. slot_minutes 변경
    try:
        tracker = ErrorTracker(max_records=1000)
        trend = tracker.get_trend(hours=1, slot_minutes=10)
        assert len(trend.time_slots) == 6  # 60분 / 10분
        assert trend.slot_duration_minutes == 10
        result.ok("12-4: slot_minutes 변경")
    except Exception as e:
        result.fail("12-4: slot_minutes", str(e))

    # 12-5. hours 변경
    try:
        tracker = ErrorTracker(max_records=1000)
        trend = tracker.get_trend(hours=2, slot_minutes=5)
        assert len(trend.time_slots) == 24  # 120분 / 5분
        result.ok("12-5: hours 변경")
    except Exception as e:
        result.fail("12-5: hours 변경", str(e))


# =============================================================================
# [13] ErrorTracker.get_records / get_record_by_id / get_records_by_hash
# =============================================================================
def test_tracker_get_records(result: TestResult) -> None:
    """ErrorTracker 레코드 조회 검증."""
    print("\n[13] ErrorTracker.get_records / get_record_by_id / get_records_by_hash")
    reset_tracker()

    tracker = ErrorTracker(max_records=1000)
    now = datetime.now(timezone.utc)
    stored_records = []

    # 테스트 데이터 추가
    for i in range(10):
        record = ErrorRecord(
            exception_type=f"Error{i % 3}",
            error_name=f"ERR_{i % 3}",
            message=f"에러 메시지 {i}",
            severity=ErrorSeverity.ERROR if i % 2 == 0 else ErrorSeverity.WARNING,
            category=TrackingCategory.VALIDATION if i < 5 else TrackingCategory.GENERAL,
            occurred_at=now - timedelta(minutes=i * 10),
        )
        tracker.track(record)
        stored_records.append(record)

    # 13-1. 기본 조회 (최신순 정렬)
    try:
        records = tracker.get_records()
        assert len(records) == 10
        # 최신순 정렬 확인
        for i in range(len(records) - 1):
            assert records[i].occurred_at >= records[i + 1].occurred_at
        result.ok("13-1: 기본 조회 (최신순)")
    except Exception as e:
        result.fail("13-1: 기본 조회", str(e))

    # 13-2. limit / offset 페이징
    try:
        page1 = tracker.get_records(limit=3, offset=0)
        page2 = tracker.get_records(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        # 페이지 간 중복 없음
        page1_ids = {r.id for r in page1}
        page2_ids = {r.id for r in page2}
        assert len(page1_ids & page2_ids) == 0
        result.ok("13-2: 페이징 (limit/offset)")
    except Exception as e:
        result.fail("13-2: 페이징", str(e))

    # 13-3. severity 필터
    try:
        error_records = tracker.get_records(severity=ErrorSeverity.ERROR)
        for r in error_records:
            assert r.severity == ErrorSeverity.ERROR
        assert len(error_records) == 5  # 짝수 인덱스 0,2,4,6,8
        result.ok("13-3: severity 필터")
    except Exception as e:
        result.fail("13-3: severity 필터", str(e))

    # 13-4. category 필터
    try:
        val_records = tracker.get_records(category=TrackingCategory.VALIDATION)
        for r in val_records:
            assert r.category == TrackingCategory.VALIDATION
        assert len(val_records) == 5  # i < 5
        result.ok("13-4: category 필터")
    except Exception as e:
        result.fail("13-4: category 필터", str(e))

    # 13-5. since 필터
    try:
        since_time = now - timedelta(minutes=35)
        recent = tracker.get_records(since=since_time)
        for r in recent:
            assert r.occurred_at >= since_time
        # i=0,1,2,3 -> 0분전, 10분전, 20분전, 30분전 = 4개
        assert len(recent) == 4, f"레코드 수: {len(recent)}"
        result.ok("13-5: since 필터")
    except Exception as e:
        result.fail("13-5: since 필터", str(e))

    # 13-6. get_record_by_id
    try:
        target = stored_records[3]
        found = tracker.get_record_by_id(target.id)
        assert found is not None
        assert found.id == target.id
        assert found.message == target.message
        result.ok("13-6: get_record_by_id")
    except Exception as e:
        result.fail("13-6: get_record_by_id", str(e))

    # 13-7. get_record_by_id - 존재하지 않는 ID
    try:
        found = tracker.get_record_by_id("non-existent-id")
        assert found is None
        result.ok("13-7: get_record_by_id (없는 ID)")
    except Exception as e:
        result.fail("13-7: get_record_by_id 없는 ID", str(e))

    # 13-8. get_records_by_hash
    try:
        target_hash = stored_records[0].error_hash
        hash_records = tracker.get_records_by_hash(target_hash)
        assert len(hash_records) >= 1
        for r in hash_records:
            assert r.error_hash == target_hash
        result.ok("13-8: get_records_by_hash")
    except Exception as e:
        result.fail("13-8: get_records_by_hash", str(e))


# =============================================================================
# [14] ErrorTracker 유틸리티
# =============================================================================
def test_tracker_utility(result: TestResult) -> None:
    """ErrorTracker 유틸리티 메서드 검증."""
    print("\n[14] ErrorTracker 유틸리티")
    reset_tracker()

    # 14-1. clear
    try:
        tracker = ErrorTracker(max_records=1000)
        for i in range(5):
            record = ErrorRecord(exception_type="TestError", message=f"에러 {i}")
            tracker.track(record)

        assert len(tracker._records) == 5
        tracker.clear()
        assert len(tracker._records) == 0
        assert len(tracker._error_hashes) == 0
        assert len(tracker._error_counts) == 0
        assert len(tracker._error_messages) == 0
        result.ok("14-1: clear")
    except Exception as e:
        result.fail("14-1: clear", str(e))

    # 14-2. get_count - 전체
    try:
        tracker = ErrorTracker(max_records=1000)
        for i in range(5):
            record = ErrorRecord(
                exception_type="TestError",
                message=f"에러 {i}",
                severity=ErrorSeverity.ERROR if i < 3 else ErrorSeverity.WARNING,
            )
            tracker.track(record)

        assert tracker.get_count() == 5
        result.ok("14-2: get_count (전체)")
    except Exception as e:
        result.fail("14-2: get_count 전체", str(e))

    # 14-3. get_count - severity 필터
    try:
        count = tracker.get_count(severity=ErrorSeverity.ERROR)
        assert count == 3, f"ERROR 수: {count}"
        count_warn = tracker.get_count(severity=ErrorSeverity.WARNING)
        assert count_warn == 2, f"WARNING 수: {count_warn}"
        result.ok("14-3: get_count (severity 필터)")
    except Exception as e:
        result.fail("14-3: get_count severity", str(e))

    # 14-4. get_count - category 필터
    try:
        tracker2 = ErrorTracker(max_records=1000)
        for i in range(3):
            tracker2.track(ErrorRecord(
                exception_type="TestError", message=f"val {i}",
                category=TrackingCategory.VALIDATION,
            ))
        for i in range(2):
            tracker2.track(ErrorRecord(
                exception_type="TestError", message=f"gen {i}",
                category=TrackingCategory.GENERAL,
            ))

        count_val = tracker2.get_count(category=TrackingCategory.VALIDATION)
        assert count_val == 3, f"VALIDATION 수: {count_val}"
        count_gen = tracker2.get_count(category=TrackingCategory.GENERAL)
        assert count_gen == 2, f"GENERAL 수: {count_gen}"
        result.ok("14-4: get_count (category 필터)")
    except Exception as e:
        result.fail("14-4: get_count category", str(e))

    # 14-5. get_status
    try:
        tracker3 = ErrorTracker(max_records=500)
        for i in range(3):
            tracker3.track(ErrorRecord(exception_type=f"Error{i}", message=f"에러 {i}"))

        status = tracker3.get_status()
        assert status["enabled"] is True
        assert status["total_records"] == 3
        assert status["max_records"] == 500
        assert isinstance(status["unique_errors"], int)
        result.ok("14-5: get_status")
    except Exception as e:
        result.fail("14-5: get_status", str(e))

    # 14-6. enabled property getter
    try:
        tracker4 = ErrorTracker(enabled=True)
        assert tracker4.enabled is True
        tracker5 = ErrorTracker(enabled=False)
        assert tracker5.enabled is False
        result.ok("14-6: enabled property getter")
    except Exception as e:
        result.fail("14-6: enabled getter", str(e))

    # 14-7. enabled property setter
    try:
        tracker6 = ErrorTracker(enabled=True)
        assert tracker6.enabled is True
        tracker6.enabled = False
        assert tracker6.enabled is False
        tracker6.enabled = True
        assert tracker6.enabled is True
        result.ok("14-7: enabled property setter")
    except Exception as e:
        result.fail("14-7: enabled setter", str(e))


# =============================================================================
# [15] 싱글톤 (_get_tracker, _reset_tracker)
# =============================================================================
def test_singleton(result: TestResult) -> None:
    """싱글톤 관리 검증."""
    print("\n[15] 싱글톤")
    reset_tracker()

    # 15-1. _get_tracker 첫 호출
    try:
        tracker1 = _get_tracker()
        assert isinstance(tracker1, ErrorTracker)
        result.ok("15-1: _get_tracker 첫 호출")
    except Exception as e:
        result.fail("15-1: _get_tracker", str(e))

    # 15-2. _get_tracker 동일 인스턴스
    try:
        tracker1 = _get_tracker()
        tracker2 = _get_tracker()
        assert tracker1 is tracker2, "동일 인스턴스가 아님"
        result.ok("15-2: 동일 인스턴스")
    except Exception as e:
        result.fail("15-2: 동일 인스턴스", str(e))

    # 15-3. _reset_tracker
    try:
        tracker1 = _get_tracker()
        _reset_tracker()
        tracker2 = _get_tracker()
        assert tracker1 is not tracker2, "리셋 후 동일 인스턴스"
        result.ok("15-3: _reset_tracker")
    except Exception as e:
        result.fail("15-3: _reset_tracker", str(e))

    # 15-4. 리셋 후 깨끗한 상태
    try:
        tracker = _get_tracker()
        tracker.track(ErrorRecord(exception_type="Test", message="테스트"))
        assert len(tracker._records) == 1

        _reset_tracker()
        new_tracker = _get_tracker()
        assert len(new_tracker._records) == 0
        result.ok("15-4: 리셋 후 깨끗한 상태")
    except Exception as e:
        result.fail("15-4: 리셋 후 상태", str(e))

    # 15-5. 멀티스레드 동시 접근
    try:
        _reset_tracker()
        instances = []
        barrier = threading.Barrier(4)

        def get_instance():
            barrier.wait()
            instances.append(id(_get_tracker()))

        threads = [threading.Thread(target=get_instance) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # 모든 스레드가 동일 인스턴스 참조
        assert len(set(instances)) == 1, f"인스턴스 수: {len(set(instances))}"
        result.ok("15-5: 멀티스레드 동시 접근")
    except Exception as e:
        result.fail("15-5: 멀티스레드", str(e))
    finally:
        reset_tracker()


# =============================================================================
# [16] 헬퍼 함수 (track_error, get_error_summary)
# =============================================================================
def test_helper_functions(result: TestResult) -> None:
    """헬퍼 함수 검증."""
    print("\n[16] 헬퍼 함수")
    reset_tracker()

    # 16-1. track_error - Exception
    try:
        exc = ValueError("헬퍼 테스트")
        try:
            raise exc
        except ValueError as e:
            record = track_error(e)

        assert isinstance(record, ErrorRecord)
        assert record.exception_type == "ValueError"
        result.ok("16-1: track_error(Exception)")
    except Exception as e:
        result.fail("16-1: track_error", str(e))

    # 16-2. track_error - 컨텍스트/심각도/태그
    try:
        exc = TypeError("타입 에러")
        try:
            raise exc
        except TypeError as e:
            record = track_error(
                e,
                context={"user_id": "u001"},
                severity=ErrorSeverity.CRITICAL,
                tags=["urgent"],
            )

        assert record.severity == ErrorSeverity.CRITICAL
        assert record.tags == ["urgent"]
        assert record.context.user_id == "u001"
        result.ok("16-2: track_error (컨텍스트/심각도/태그)")
    except Exception as e:
        result.fail("16-2: track_error 옵션", str(e))

    # 16-3. track_error - ErrorRecord 직접 전달
    try:
        record = ErrorRecord(
            exception_type="DirectError",
            message="직접 전달",
        )
        returned = track_error(record)
        assert returned.exception_type == "DirectError"
        result.ok("16-3: track_error(ErrorRecord)")
    except Exception as e:
        result.fail("16-3: track_error ErrorRecord", str(e))

    # 16-4. get_error_summary
    try:
        summary = get_error_summary(hours=24)
        assert isinstance(summary, ErrorSummary)
        assert summary.total_count >= 3  # 이전 테스트에서 추가한 레코드들
        result.ok("16-4: get_error_summary")
    except Exception as e:
        result.fail("16-4: get_error_summary", str(e))

    # 16-5. get_error_summary - 필터
    try:
        summary = get_error_summary(hours=24, min_severity=ErrorSeverity.CRITICAL)
        assert isinstance(summary, ErrorSummary)
        # CRITICAL만 필터
        for sev_name, count in summary.by_severity.items():
            if count > 0:
                sev = ErrorSeverity[sev_name]
                assert sev >= ErrorSeverity.CRITICAL
        result.ok("16-5: get_error_summary (필터)")
    except Exception as e:
        result.fail("16-5: get_error_summary 필터", str(e))

    reset_tracker()


# =============================================================================
# [17] 엣지 케이스 / __all__
# =============================================================================
def test_edge_cases(result: TestResult) -> None:
    """엣지 케이스 및 __all__ 검증."""
    print("\n[17] 엣지 케이스 / __all__")
    reset_tracker()

    # 17-1. __all__ 내보내기 목록 (13개)
    try:
        import core_foundation.monitoring.error_tracker as et_module
        all_exports = et_module.__all__
        assert len(all_exports) == 13, f"__all__ 수: {len(all_exports)}"
        expected = [
            "ErrorSeverity", "ErrorCategory", "TrackingCategory",
            "MAX_ERROR_RECORDS", "MAX_ERROR_HASHES", "AGGREGATION_WINDOW_SIZE",
            "ErrorRecord", "ErrorSummary", "ErrorTrend", "ErrorContext",
            "ErrorTracker", "track_error", "get_error_summary",
        ]
        for name in expected:
            assert name in all_exports, f"누락: {name}"
        result.ok("17-1: __all__ (13개)")
    except Exception as e:
        result.fail("17-1: __all__", str(e))

    # 17-2. ErrorCategory re-export
    try:
        import core_foundation.monitoring.error_tracker as et_module
        # ErrorCategory는 shared.constants.error_codes에서 re-export
        assert hasattr(et_module, "ErrorCategory")
        assert et_module.ErrorCategory is ErrorCategory
        result.ok("17-2: ErrorCategory re-export")
    except Exception as e:
        result.fail("17-2: ErrorCategory re-export", str(e))

    # 17-3. ErrorRecord - 큰 메시지 해시 (100자 잘림)
    try:
        long_msg = "X" * 500
        r1 = ErrorRecord(exception_type="Test", message=long_msg)
        r2 = ErrorRecord(exception_type="Test", message=long_msg)
        assert r1.error_hash == r2.error_hash
        # 해시 생성 시 message[:100] 사용
        short_msg = "X" * 100
        r3 = ErrorRecord(exception_type="Test", message=short_msg)
        assert r1.error_hash == r3.error_hash, "메시지 100자 잘림 확인"
        result.ok("17-3: 큰 메시지 해시 (100자 잘림)")
    except Exception as e:
        result.fail("17-3: 큰 메시지 해시", str(e))

    # 17-4. ErrorRecord - error_hash 미리 지정
    try:
        record = ErrorRecord(
            error_hash="custom_hash_12345",
            exception_type="Test",
            message="커스텀 해시",
        )
        # error_hash가 이미 있으면 __post_init__에서 덮어쓰지 않음
        assert record.error_hash == "custom_hash_12345"
        result.ok("17-4: error_hash 미리 지정")
    except Exception as e:
        result.fail("17-4: error_hash 미리 지정", str(e))

    # 17-5. ErrorTracker - 스레드 안전 (동시 추적)
    try:
        tracker = ErrorTracker(max_records=10000)
        barrier = threading.Barrier(4)
        errors_per_thread = 100

        def track_many():
            barrier.wait()
            for i in range(errors_per_thread):
                record = ErrorRecord(
                    exception_type="ThreadError",
                    message=f"스레드 에러 {i}",
                )
                tracker.track(record)

        threads = [threading.Thread(target=track_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        expected = 4 * errors_per_thread
        assert len(tracker._records) == expected, f"레코드: {len(tracker._records)} (기대: {expected})"
        result.ok("17-5: 스레드 안전 (동시 추적)")
    except Exception as e:
        result.fail("17-5: 스레드 안전", str(e))

    # 17-6. ErrorContext.from_dict - 빈 딕셔너리
    try:
        ctx = ErrorContext.from_dict({})
        assert ctx.request_id is None
        assert ctx.extra == {}
        result.ok("17-6: ErrorContext.from_dict (빈 딕셔너리)")
    except Exception as e:
        result.fail("17-6: from_dict 빈", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 테스트 실행."""
    print("=" * 60)
    print("ErrorTracker 단위 테스트")
    print("=" * 60)

    result = TestResult()

    test_constants(result)
    test_error_severity(result)
    test_tracking_category(result)
    test_error_context(result)
    test_error_record(result)
    test_error_summary(result)
    test_error_trend(result)
    test_tracker_init(result)
    test_tracker_track(result)
    test_tracker_store_fifo(result)
    test_tracker_get_summary(result)
    test_tracker_get_trend(result)
    test_tracker_get_records(result)
    test_tracker_utility(result)
    test_singleton(result)
    test_helper_functions(result)
    test_edge_cases(result)

    result.summary()


if __name__ == "__main__":
    main()
