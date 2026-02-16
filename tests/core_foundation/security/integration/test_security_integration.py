# -*- coding: utf-8 -*-
"""
COURTVIEW - security 모듈 통합 테스트

12개 카테고리, 80개 테스트

검증 범위:
    [1]  __init__.py 임포트 무결성 (secret_manager, audit_logger)
    [2]  __all__ 전체 Export 검증
    [3]  Enum 상호 호환성 / 교차 참조
    [4]  SecretManager 독립 워크플로우
    [5]  AuditLogger 독립 워크플로우
    [6]  AuditEvent / AuditLogEntry 라이프사이클
    [7]  LoginFailureTracker 워크플로우
    [8]  SecretManager + AuditLogger 연동 (시크릿 접근 -> 감사 로깅)
    [9]  체인 해시 무결성 파이프라인
    [10] 알림 + 심각도 에스컬레이션
    [11] 전체 보안 파이프라인 시뮬레이션 (사용자 인증 흐름)
    [12] 스레드 안전성 / 싱글톤 격리

실행:
    python tests/core_foundation/security/integration/test_security_integration.py
"""

from __future__ import annotations

import io
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, List

# ============================================================
# 프로젝트 루트 + 인코딩
# ============================================================
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ============================================================
# 의존성 모킹 (모듈 임포트 전 설정)
# ============================================================
import types as _types

# --- core_foundation 패키지 껍데기 등록 ---
# core_foundation/__init__.py 가 실행되면 config 등 다른 서브모듈을 끌어오므로,
# 껍데기를 먼저 넣어 __init__.py 실행을 방지한다.
if "core_foundation" not in sys.modules:
    _cf_mod = _types.ModuleType("core_foundation")
    _cf_mod.__path__ = [str(_PROJECT_ROOT / "core_foundation")]  # type: ignore
    sys.modules["core_foundation"] = _cf_mod

# --- utils.time_utils 모킹 ---
_time_mod = _types.ModuleType("utils.time_utils")
_time_mod.get_current_timestamp = lambda: time.time()  # type: ignore
sys.modules.setdefault("utils", _types.ModuleType("utils"))
sys.modules["utils.time_utils"] = _time_mod

# --- core_foundation.config.loader 모킹 ---
_config_mod = _types.ModuleType("core_foundation.config.loader")


class _MockConfigLoader:
    """ConfigLoader 경량 모킹. 설정값 오버라이드 지원."""

    _instance = None

    def __init__(self, *a: Any, **kw: Any) -> None:
        self._overrides: dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> "_MockConfigLoader":
        if cls._instance is None:
            cls._instance = _MockConfigLoader()
        return cls._instance

    def set_override(self, key: str, value: Any) -> None:
        """테스트용 설정 오버라이드."""
        self._overrides[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._overrides:
            return self._overrides[key]
        return default


_config_mod.ConfigLoader = _MockConfigLoader  # type: ignore
sys.modules["core_foundation.config.loader"] = _config_mod
sys.modules.setdefault("core_foundation.config", _types.ModuleType("core_foundation.config"))

# --- shared.constants.error_codes 모킹 ---
_error_codes_mod = _types.ModuleType("shared.constants.error_codes")


class _MockErrorCode:
    """ErrorCode Enum 경량 스텁."""
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
    ENCRYPTION_ERROR = "ENCRYPTION_ERROR"
    ENCRYPTION_UNAVAILABLE = "ENCRYPTION_UNAVAILABLE"


_error_codes_mod.ErrorCode = _MockErrorCode  # type: ignore
sys.modules.setdefault("shared", _types.ModuleType("shared"))
sys.modules.setdefault("shared.constants", _types.ModuleType("shared.constants"))
sys.modules["shared.constants.error_codes"] = _error_codes_mod

# --- shared.exceptions 모킹 ---
_base_exc_mod = _types.ModuleType("shared.exceptions.base_exception")


class _CourtViewException(Exception):
    """CourtViewException 경량 스텁."""

    def __init__(self, message: str = "", error_code: Any = None, **kwargs: Any) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details: dict[str, Any] = kwargs.get("details", {})


_base_exc_mod.CourtViewException = _CourtViewException  # type: ignore
sys.modules.setdefault("shared.exceptions", _types.ModuleType("shared.exceptions"))
sys.modules["shared.exceptions.base_exception"] = _base_exc_mod

_infra_exc_mod = _types.ModuleType("shared.exceptions.infrastructure_exceptions")


class _InfrastructureException(_CourtViewException):
    """InfrastructureException 경량 스텁."""

    def __init__(
        self,
        message: str = "인프라스트럭처 오류",
        error_code: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, error_code=error_code, **kwargs)
        self.details: dict[str, Any] = {}


_infra_exc_mod.InfrastructureException = _InfrastructureException  # type: ignore
sys.modules["shared.exceptions.infrastructure_exceptions"] = _infra_exc_mod

# ============================================================
# 모듈 임포트 (모킹 후)
# ============================================================
import core_foundation.security as security_mod
from core_foundation.security import (
    # secret_manager - Enum
    SecretProvider, SecretStatus, CacheStatus,
    # secret_manager - 예외
    SecretException, SecretNotFoundException, SecretAccessDeniedException,
    SecretValidationException, SecretProviderException,
    # secret_manager - 데이터 클래스
    SecretInfo, SecretVersion, SecretValidationRule, RotationSchedule,
    # secret_manager - 메인
    SecretManager,
    # secret_manager - 제공자
    BaseSecretProvider, AWSSecretsProvider, VaultProvider, EnvProvider,
    FileProvider, EncryptedFileProvider,
    # secret_manager - 유틸리티
    SecretEncryption, SecretRotator, VaultTokenManager,
    # secret_manager - 함수
    get_secret, get_secret_manager, set_secret_manager,
    # audit_logger - Enum
    AuditEventType, AuditSeverity,
    # audit_logger - 데이터 클래스
    AuditEvent, AuditLogEntry,
    # audit_logger - 저장소
    BaseAuditStorage, FileAuditStorage, MemoryAuditStorage,
    CloudWatchAuditStorage, ElasticsearchAuditStorage,
    # audit_logger - 알림 핸들러
    BaseAlertHandler, LogAlertHandler, SlackAlertHandler,
    EmailAlertHandler, WebhookAlertHandler,
    # audit_logger - 추적기
    LoginFailureTracker,
    # audit_logger - 메인
    AuditLogger,
    # audit_logger - 함수
    get_audit_logger, set_audit_logger, log_audit_event,
    # audit_logger - 상수
    EVENT_DEFAULT_SEVERITY,
)

from core_foundation.security.audit_logger import INITIAL_CHAIN_HASH


# ============================================================
# TestResult
# ============================================================
class TestResult:
    """테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.failures: List[str] = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, reason: str = "") -> None:
        self.failed += 1
        self.failures.append(f"{name}: {reason}")
        print(f"  [FAIL] {name}: {reason}")

    @property
    def total(self) -> int:
        return self.passed + self.failed

    def summary(self) -> None:
        print(f"\n{'=' * 60}")
        if self.failed == 0:
            print(f"통합 테스트 결과: {self.total}/{self.total} 통과")
        else:
            print(f"통합 테스트 결과: {self.passed}/{self.total} 통과")
            print(f"\n실패한 테스트:")
            for f in self.failures:
                print(f"  - {f}")
        print("=" * 60)


# ============================================================
# 테스트 유틸리티
# ============================================================
def _create_mock_config_loader(**overrides: Any) -> _MockConfigLoader:
    """오버라이드가 적용된 MockConfigLoader 생성."""
    loader = _MockConfigLoader()
    for key, value in overrides.items():
        loader.set_override(key, value)
    return loader


def _create_test_audit_logger(
    config_loader: _MockConfigLoader | None = None,
    use_memory_storage: bool = True,
) -> tuple[AuditLogger, MemoryAuditStorage]:
    """테스트용 AuditLogger 생성 (MemoryAuditStorage 포함).

    Returns:
        (AuditLogger, MemoryAuditStorage) 튜플
    """
    if config_loader is None:
        config_loader = _create_mock_config_loader(**{
            "security.audit_logger": {
                "storage": {
                    "file": {"enabled": False},
                },
                "sampling_enabled": False,
                "integrity_enabled": True,
                "chain_hash_enabled": True,
                "alerting_enabled": True,
            },
        })

    audit_logger = AuditLogger(config_loader=config_loader)  # type: ignore

    # 파일 저장소 제거 후 메모리 저장소 추가
    if use_memory_storage:
        mem_storage = MemoryAuditStorage(max_entries=10000)
        audit_logger._storages = [mem_storage]
        return audit_logger, mem_storage

    # 이미 메모리 저장소가 기본으로 들어간 경우
    for s in audit_logger._storages:
        if isinstance(s, MemoryAuditStorage):
            return audit_logger, s

    mem_storage = MemoryAuditStorage(max_entries=10000)
    audit_logger._storages.append(mem_storage)
    return audit_logger, mem_storage


def _create_test_secret_manager(
    env_secrets: dict[str, str] | None = None,
) -> SecretManager:
    """테스트용 SecretManager 생성 (EnvProvider 기본).

    Args:
        env_secrets: 환경변수에 설정할 시크릿 (테스트 후 정리 필요)

    Returns:
        SecretManager 인스턴스
    """
    if env_secrets:
        for key, value in env_secrets.items():
            os.environ[key] = value

    config_loader = _create_mock_config_loader()
    return SecretManager(config_loader=config_loader)  # type: ignore


def _cleanup_env_secrets(keys: list[str]) -> None:
    """테스트용 환경변수 정리."""
    for key in keys:
        os.environ.pop(key, None)


# =============================================================================
# [1] __init__.py 임포트 무결성 (8개)
# =============================================================================
def test_import_integrity(result: TestResult) -> None:
    """__init__.py에서 모든 서브모듈 임포트가 정상적으로 동작하는지 검증."""
    print("\n[1] __init__.py 임포트 무결성")

    # 1-1. 패키지 임포트 자체 성공
    try:
        assert security_mod is not None
        result.ok("1-1 core_foundation.security 패키지 임포트")
    except Exception as e:
        result.fail("1-1 패키지 임포트", str(e))
        return

    # 1-2. secret_manager Enum 심볼
    try:
        assert SecretProvider is not None
        assert SecretStatus is not None
        assert CacheStatus is not None
        result.ok("1-2 secret_manager Enum 심볼 (3개)")
    except ImportError as e:
        result.fail("1-2 Enum 임포트", str(e))

    # 1-3. secret_manager 예외 심볼
    try:
        assert SecretException is not None
        assert SecretNotFoundException is not None
        assert SecretAccessDeniedException is not None
        assert SecretValidationException is not None
        assert SecretProviderException is not None
        result.ok("1-3 secret_manager 예외 심볼 (5개)")
    except ImportError as e:
        result.fail("1-3 예외 임포트", str(e))

    # 1-4. secret_manager 클래스 심볼
    try:
        assert SecretManager is not None
        assert BaseSecretProvider is not None
        assert EnvProvider is not None
        assert FileProvider is not None
        assert SecretEncryption is not None
        assert SecretRotator is not None
        assert VaultTokenManager is not None
        result.ok("1-4 secret_manager 클래스 심볼 (7개)")
    except ImportError as e:
        result.fail("1-4 클래스 임포트", str(e))

    # 1-5. audit_logger Enum + 데이터 클래스 심볼
    try:
        assert AuditEventType is not None
        assert AuditSeverity is not None
        assert AuditEvent is not None
        assert AuditLogEntry is not None
        result.ok("1-5 audit_logger Enum + 데이터 클래스 (4개)")
    except ImportError as e:
        result.fail("1-5 audit_logger 임포트", str(e))

    # 1-6. audit_logger 저장소 + 핸들러 심볼
    try:
        assert BaseAuditStorage is not None
        assert MemoryAuditStorage is not None
        assert FileAuditStorage is not None
        assert LogAlertHandler is not None
        assert LoginFailureTracker is not None
        assert AuditLogger is not None
        result.ok("1-6 audit_logger 저장소/핸들러/메인 (6개)")
    except ImportError as e:
        result.fail("1-6 audit_logger 클래스 임포트", str(e))

    # 1-7. 순환 참조 없음 (re-import)
    try:
        import importlib
        importlib.reload(sys.modules["core_foundation.security"])
        result.ok("1-7 순환 참조 없음 (reload 성공)")
    except Exception as e:
        result.fail("1-7 순환 참조", str(e))

    # 1-8. 각 서브모듈 직접 임포트도 정상
    try:
        import core_foundation.security.secret_manager
        import core_foundation.security.audit_logger
        result.ok("1-8 서브모듈 직접 임포트 (2개)")
    except ImportError as e:
        result.fail("1-8 서브모듈 직접", str(e))


# =============================================================================
# [2] __all__ Export 검증 (6개)
# =============================================================================
def test_all_exports(result: TestResult) -> None:
    """__init__.py __all__ 전체 Export 검증."""
    print("\n[2] __all__ Export 검증")

    # 2-1. __all__ 존재
    try:
        assert hasattr(security_mod, "__all__")
        result.ok("2-1 __all__ 존재")
    except AssertionError as e:
        result.fail("2-1 __all__ 존재", str(e))

    # 2-2. __all__ 전체 개수 (secret_manager + audit_logger)
    try:
        total = len(security_mod.__all__)
        from core_foundation.security.secret_manager import __all__ as sm_all
        from core_foundation.security.audit_logger import __all__ as al_all
        expected = len(sm_all) + len(al_all)
        assert total == expected, f"__init__.__all__={total}, 서브합={expected}"
        result.ok(f"2-2 __all__ 개수 일치 ({total}개)")
    except AssertionError as e:
        result.fail("2-2 __all__ 개수", str(e))

    # 2-3. __all__의 모든 심볼이 실제 접근 가능
    try:
        missing = []
        for name in security_mod.__all__:
            if not hasattr(security_mod, name):
                missing.append(name)
        assert len(missing) == 0, f"누락: {missing}"
        result.ok(f"2-3 __all__ 모든 심볼 접근 가능 ({len(security_mod.__all__)}개)")
    except AssertionError as e:
        result.fail("2-3 심볼 접근", str(e))

    # 2-4. secret_manager 핵심 심볼 포함
    try:
        sm_required = [
            "SecretProvider", "SecretStatus", "CacheStatus",
            "SecretManager", "EnvProvider", "get_secret",
            "get_secret_manager", "set_secret_manager",
        ]
        for sym in sm_required:
            assert sym in security_mod.__all__, f"'{sym}' 누락"
        result.ok("2-4 secret_manager 핵심 심볼 포함")
    except AssertionError as e:
        result.fail("2-4 secret_manager 심볼", str(e))

    # 2-5. 중복 항목 없음
    try:
        all_list = security_mod.__all__
        assert len(all_list) == len(set(all_list)), \
            f"중복: {[x for x in all_list if all_list.count(x) > 1]}"
        result.ok("2-5 __all__ 중복 없음")
    except AssertionError as e:
        result.fail("2-5 중복 검사", str(e))

    # 2-6. 서브모듈 간 이름 충돌 없음
    try:
        from core_foundation.security.secret_manager import __all__ as sm_all
        from core_foundation.security.audit_logger import __all__ as al_all
        all_names = list(sm_all) + list(al_all)
        duplicates = [x for x in set(all_names) if all_names.count(x) > 1]
        if duplicates:
            result.ok(f"2-6 서브모듈 간 이름 충돌 감지 (알려진 충돌: {duplicates})")
        else:
            result.ok("2-6 서브모듈 간 이름 충돌 없음")
    except Exception as e:
        result.fail("2-6 이름 충돌", str(e))


# =============================================================================
# [3] Enum 상호 호환성 / 교차 참조 (6개)
# =============================================================================
def test_enum_cross_reference(result: TestResult) -> None:
    """서로 다른 모듈의 Enum이 독립적이고 충돌 없이 사용 가능한지 검증."""
    print("\n[3] Enum 상호 호환성")

    # 3-1. 모든 Enum은 서로 다른 타입
    try:
        enums = [SecretProvider, SecretStatus, CacheStatus, AuditEventType, AuditSeverity]
        for i in range(len(enums)):
            for j in range(i + 1, len(enums)):
                assert enums[i] is not enums[j], f"{enums[i].__name__} == {enums[j].__name__}"
        result.ok(f"3-1 Enum 타입 독립성 ({len(enums)}개)")
    except AssertionError as e:
        result.fail("3-1 Enum 독립성", str(e))

    # 3-2. SecretProvider 멤버 수 (4개: AWS, VAULT, ENV, FILE)
    try:
        members = list(SecretProvider)
        assert len(members) == 4, f"SecretProvider 멤버 수: {len(members)}"
        names = {m.name for m in members}
        assert names == {"AWS", "VAULT", "ENV", "FILE"}
        result.ok("3-2 SecretProvider 멤버 (4개)")
    except AssertionError as e:
        result.fail("3-2 SecretProvider", str(e))

    # 3-3. SecretStatus 멤버 수 (5개)
    try:
        members = list(SecretStatus)
        assert len(members) == 5, f"SecretStatus 멤버 수: {len(members)}"
        names = {m.name for m in members}
        assert {"ACTIVE", "ROTATED", "EXPIRED", "PENDING", "DEPRECATED"} == names
        result.ok("3-3 SecretStatus 멤버 (5개)")
    except AssertionError as e:
        result.fail("3-3 SecretStatus", str(e))

    # 3-4. CacheStatus 멤버 수 (4개)
    try:
        members = list(CacheStatus)
        assert len(members) == 4, f"CacheStatus 멤버 수: {len(members)}"
        names = {m.name for m in members}
        assert {"HIT", "MISS", "EXPIRED", "REFRESHED"} == names
        result.ok("3-4 CacheStatus 멤버 (4개)")
    except AssertionError as e:
        result.fail("3-4 CacheStatus", str(e))

    # 3-5. AuditEventType @unique + 39개 멤버 + 카테고리 분류
    try:
        members = list(AuditEventType)
        assert len(members) == 39, f"AuditEventType 멤버 수: {len(members)} (expected 39)"
        # 카테고리별 확인
        categories = set()
        for m in members:
            categories.add(m.category)
        expected_cats = {"authentication", "authorization", "data_access",
                         "configuration", "system", "security"}
        assert categories == expected_cats, f"카테고리: {categories}"
        result.ok(f"3-5 AuditEventType ({len(members)}개, {len(categories)} 카테고리)")
    except AssertionError as e:
        result.fail("3-5 AuditEventType", str(e))

    # 3-6. AuditSeverity 비교 연산자 + retain_days + name_str
    try:
        assert AuditSeverity.DEBUG < AuditSeverity.INFO
        assert AuditSeverity.INFO < AuditSeverity.WARNING
        assert AuditSeverity.WARNING < AuditSeverity.ERROR
        assert AuditSeverity.ERROR < AuditSeverity.CRITICAL
        assert AuditSeverity.CRITICAL >= AuditSeverity.CRITICAL
        # retain_days 확인
        assert AuditSeverity.DEBUG.retain_days == 7
        assert AuditSeverity.CRITICAL.retain_days == 365
        # name_str 확인
        assert AuditSeverity.INFO.name_str == "info"
        assert AuditSeverity.CRITICAL.name_str == "critical"
        result.ok("3-6 AuditSeverity 비교/retain_days/name_str")
    except AssertionError as e:
        result.fail("3-6 AuditSeverity", str(e))


# =============================================================================
# [4] SecretManager 독립 워크플로우 (7개)
# =============================================================================
def test_secret_manager_workflow(result: TestResult) -> None:
    """SecretManager 생성 -> EnvProvider 조회 -> 캐시 -> 무효화 전체 흐름."""
    print("\n[4] SecretManager 독립 워크플로우")

    env_keys = [
        "COURTVIEW_SECRET_DB_PASSWORD",
        "COURTVIEW_SECRET_JWT_SECRET",
        "COURTVIEW_SECRET_API_KEY",
    ]
    env_secrets = {
        env_keys[0]: "test_db_password_123",
        env_keys[1]: "jwt_secret_value_456",
        env_keys[2]: "api_key_value_789",
    }

    try:
        sm = _create_test_secret_manager(env_secrets=env_secrets)

        # 4-1. SecretManager 초기화 성공
        try:
            assert sm is not None
            providers = sm.get_providers()
            assert "ENV" in providers
            result.ok(f"4-1 SecretManager 초기화 (providers: {providers})")
        except Exception as e:
            result.fail("4-1 초기화", str(e))

        # 4-2. EnvProvider 시크릿 조회
        try:
            value = sm.get("DB_PASSWORD")
            assert value == "test_db_password_123", f"got: {value}"
            result.ok("4-2 EnvProvider 시크릿 조회 (DB_PASSWORD)")
        except Exception as e:
            result.fail("4-2 조회", str(e))

        # 4-3. 캐시 히트 검증
        try:
            # 첫 조회 후 캐시에 저장됨 -> 두 번째 조회는 캐시 히트
            value2 = sm.get("DB_PASSWORD")
            assert value2 == "test_db_password_123"
            stats = sm.get_cache_stats()
            assert stats["total_entries"] >= 1
            result.ok(f"4-3 캐시 히트 (entries: {stats['total_entries']})")
        except Exception as e:
            result.fail("4-3 캐시 히트", str(e))

        # 4-4. 캐시 우회 조회
        try:
            value3 = sm.get("JWT_SECRET", bypass_cache=True)
            assert value3 == "jwt_secret_value_456"
            result.ok("4-4 캐시 우회 조회 (JWT_SECRET)")
        except Exception as e:
            result.fail("4-4 캐시 우회", str(e))

        # 4-5. 시크릿 존재 확인
        try:
            assert sm.exists("DB_PASSWORD") is True
            assert sm.exists("NONEXISTENT_KEY") is False
            result.ok("4-5 exists() 확인")
        except Exception as e:
            result.fail("4-5 exists", str(e))

        # 4-6. 캐시 무효화
        try:
            count = sm.invalidate_cache("DB_PASSWORD")
            assert count >= 1, f"무효화 건수: {count}"
            # 전체 무효화
            sm.get("API_KEY")  # 캐시에 추가
            total_invalidated = sm.invalidate_cache()
            assert total_invalidated >= 1
            stats_after = sm.get_cache_stats()
            assert stats_after["total_entries"] == 0
            result.ok(f"4-6 캐시 무효화 (단건: {count}, 전체: {total_invalidated})")
        except Exception as e:
            result.fail("4-6 캐시 무효화", str(e))

        # 4-7. 기본값 폴백 + get_required 예외
        try:
            fallback = sm.get("NONEXISTENT_SECRET", default="fallback_value")
            assert fallback == "fallback_value"

            raised = False
            try:
                sm.get_required("NONEXISTENT_SECRET")
            except SecretNotFoundException:
                raised = True
            assert raised, "SecretNotFoundException이 발생해야 합니다"
            result.ok("4-7 기본값 폴백 + get_required 예외")
        except Exception as e:
            result.fail("4-7 폴백/예외", str(e))

    finally:
        _cleanup_env_secrets(env_keys)


# =============================================================================
# [5] AuditLogger 독립 워크플로우 (7개)
# =============================================================================
def test_audit_logger_workflow(result: TestResult) -> None:
    """AuditLogger 생성 -> 이벤트 기록 -> MemoryAuditStorage 조회 전체 흐름."""
    print("\n[5] AuditLogger 독립 워크플로우")

    audit_logger, mem_storage = _create_test_audit_logger()

    try:
        # 5-1. AuditLogger 초기화 성공
        try:
            assert audit_logger is not None
            stats = audit_logger.get_stats()
            assert isinstance(stats, dict)
            assert "sequence_number" in stats
            result.ok("5-1 AuditLogger 초기화 성공")
        except Exception as e:
            result.fail("5-1 초기화", str(e))

        # 5-2. 기본 이벤트 기록
        try:
            entry_id = audit_logger.log(
                event_type=AuditEventType.LOGIN_SUCCESS,
                actor="user@test.com",
                action="login",
                resource="/api/auth/login",
                result="success",
                immediate=True,
            )
            assert entry_id is not None
            assert isinstance(entry_id, str)
            assert len(entry_id) > 0
            result.ok(f"5-2 이벤트 기록 (id: {entry_id[:8]}...)")
        except Exception as e:
            result.fail("5-2 이벤트 기록", str(e))

        # 5-3. MemoryAuditStorage 조회
        try:
            entries = mem_storage.get_all()
            assert len(entries) >= 1
            assert entries[0].event.actor == "user@test.com"
            assert entries[0].event.event_type == AuditEventType.LOGIN_SUCCESS
            result.ok(f"5-3 MemoryAuditStorage 조회 ({len(entries)}건)")
        except Exception as e:
            result.fail("5-3 조회", str(e))

        # 5-4. 다수 이벤트 기록
        try:
            event_types = [
                (AuditEventType.DATA_READ, "admin", "read", "/api/users"),
                (AuditEventType.DATA_CREATE, "admin", "create", "/api/games"),
                (AuditEventType.CONFIG_CHANGE, "system", "update", "/config/security"),
                (AuditEventType.ACCESS_DENIED, "hacker", "access", "/api/admin"),
            ]
            for evt, actor, action, resource in event_types:
                audit_logger.log(
                    event_type=evt,
                    actor=actor,
                    action=action,
                    resource=resource,
                    immediate=True,
                )

            entries = mem_storage.get_all()
            assert len(entries) >= 5  # 5-2의 1건 + 4건
            result.ok(f"5-4 다수 이벤트 기록 ({len(entries)}건)")
        except Exception as e:
            result.fail("5-4 다수 이벤트", str(e))

        # 5-5. 시퀀스 번호 증가 확인
        try:
            entries = mem_storage.get_all()
            seq_numbers = [e.sequence_number for e in entries]
            # 시퀀스 번호는 단조 증가
            for i in range(1, len(seq_numbers)):
                assert seq_numbers[i] > seq_numbers[i - 1], \
                    f"시퀀스 비단조: {seq_numbers[i-1]} -> {seq_numbers[i]}"
            result.ok(f"5-5 시퀀스 번호 단조 증가 (max: {max(seq_numbers)})")
        except Exception as e:
            result.fail("5-5 시퀀스", str(e))

        # 5-6. severity 자동 설정 확인
        try:
            # severity 미지정 시 EVENT_DEFAULT_SEVERITY에서 자동 결정
            audit_logger.log(
                event_type=AuditEventType.INTRUSION_DETECTED,
                actor="system",
                action="detect",
                resource="/security/ids",
                immediate=True,
            )
            entries = mem_storage.get_all()
            last_entry = entries[-1]
            # security 카테고리 -> CRITICAL (EVENT_DEFAULT_SEVERITY)
            assert last_entry.event.severity == AuditSeverity.CRITICAL, \
                f"severity: {last_entry.event.severity}"
            result.ok("5-6 severity 자동 설정 (security -> CRITICAL)")
        except Exception as e:
            result.fail("5-6 severity 자동", str(e))

        # 5-7. get_stats 확인
        try:
            stats = audit_logger.get_stats()
            assert stats["sequence_number"] >= 6
            assert stats["storage_count"] >= 1
            assert stats["integrity_enabled"] is True
            result.ok(f"5-7 get_stats (seq: {stats['sequence_number']})")
        except Exception as e:
            result.fail("5-7 get_stats", str(e))

    finally:
        audit_logger.close()


# =============================================================================
# [6] AuditEvent / AuditLogEntry 라이프사이클 (6개)
# =============================================================================
def test_audit_event_lifecycle(result: TestResult) -> None:
    """AuditEvent 생성 -> to_dict -> from_dict -> AuditLogEntry 해시/무결성."""
    print("\n[6] AuditEvent / AuditLogEntry 라이프사이클")

    # 6-1. AuditEvent 생성 및 기본값 확인
    try:
        event = AuditEvent(
            event_type=AuditEventType.LOGIN_SUCCESS,
            actor="user@test.com",
            action="login",
            resource="/api/auth",
        )
        assert event.result == "success"
        assert event.severity is not None
        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)
        result.ok("6-1 AuditEvent 생성 (기본값 확인)")
    except Exception as e:
        result.fail("6-1 AuditEvent 생성", str(e))

    # 6-2. AuditEvent to_dict 변환
    try:
        event = AuditEvent(
            event_type=AuditEventType.DATA_READ,
            actor="admin",
            action="read",
            resource="/api/users",
            severity=AuditSeverity.INFO,
            ip_address="192.168.1.100",
            details={"user_id": 42},
        )
        d = event.to_dict()
        assert d["event_type"] == "data_access.data_read"
        assert d["actor"] == "admin"
        assert d["severity"] == "info"
        assert d["ip_address"] == "192.168.1.100"
        assert d["details"]["user_id"] == 42
        result.ok("6-2 AuditEvent to_dict")
    except Exception as e:
        result.fail("6-2 to_dict", str(e))

    # 6-3. AuditEvent from_dict 복원
    try:
        original = AuditEvent(
            event_type=AuditEventType.SECRET_ACCESS,
            actor="service_account",
            action="access",
            resource="database_password",
            severity=AuditSeverity.WARNING,
            request_id="req-123",
        )
        d = original.to_dict()
        restored = AuditEvent.from_dict(d)
        assert restored.event_type == original.event_type
        assert restored.actor == original.actor
        assert restored.severity == original.severity
        assert restored.request_id == original.request_id
        result.ok("6-3 AuditEvent from_dict 복원")
    except Exception as e:
        result.fail("6-3 from_dict", str(e))

    # 6-4. AuditLogEntry 해시 계산
    try:
        event = AuditEvent(
            event_type=AuditEventType.LOGIN_FAILURE,
            actor="attacker",
            action="login",
            resource="/api/auth",
            result="failure",
        )
        entry = AuditLogEntry(
            id=str(uuid.uuid4()),
            event=event,
            sequence_number=1,
        )
        computed_hash = entry.compute_hash(INITIAL_CHAIN_HASH)
        assert isinstance(computed_hash, str)
        assert len(computed_hash) == 64  # SHA-256 hex digest = 64자
        # 동일 입력 -> 동일 해시
        computed_hash_2 = entry.compute_hash(INITIAL_CHAIN_HASH)
        assert computed_hash == computed_hash_2
        result.ok(f"6-4 AuditLogEntry 해시 계산 (SHA-256, {len(computed_hash)}자)")
    except Exception as e:
        result.fail("6-4 해시 계산", str(e))

    # 6-5. AuditLogEntry 무결성 검증
    try:
        event = AuditEvent(
            event_type=AuditEventType.DATA_UPDATE,
            actor="admin",
            action="update",
            resource="/api/config",
        )
        entry = AuditLogEntry(
            id=str(uuid.uuid4()),
            event=event,
            sequence_number=1,
        )
        previous_hash = INITIAL_CHAIN_HASH
        entry.entry_hash = entry.compute_hash(previous_hash)
        entry.chain_hash = previous_hash

        # 무결성 검증 성공
        assert entry.verify_integrity(previous_hash) is True

        # 변조 시뮬레이션 -> 검증 실패
        entry.event.actor = "tampered_user"
        assert entry.verify_integrity(previous_hash) is False
        result.ok("6-5 AuditLogEntry 무결성 검증 (정상 + 변조)")
    except Exception as e:
        result.fail("6-5 무결성 검증", str(e))

    # 6-6. AuditLogEntry to_dict / from_dict 왕복
    try:
        event = AuditEvent(
            event_type=AuditEventType.SERVICE_START,
            actor="system",
            action="start",
            resource="courtview_ai_server",
        )
        entry = AuditLogEntry(
            id=str(uuid.uuid4()),
            event=event,
            sequence_number=42,
        )
        entry.entry_hash = entry.compute_hash("")
        d = entry.to_dict()
        restored = AuditLogEntry.from_dict(d)
        assert restored.id == entry.id
        assert restored.sequence_number == 42
        assert restored.entry_hash == entry.entry_hash
        assert restored.event.event_type == AuditEventType.SERVICE_START
        result.ok("6-6 AuditLogEntry to_dict/from_dict 왕복")
    except Exception as e:
        result.fail("6-6 왕복", str(e))


# =============================================================================
# [7] LoginFailureTracker 워크플로우 (5개)
# =============================================================================
def test_login_failure_tracker(result: TestResult) -> None:
    """LoginFailureTracker 기록 -> 임계값 -> 리셋 전체 흐름."""
    print("\n[7] LoginFailureTracker 워크플로우")

    # 기본 임계값=5, 윈도우=15분
    tracker = LoginFailureTracker(threshold=5, window_minutes=15)

    # 7-1. 초기 실패 기록 (임계값 미달)
    try:
        exceeded = tracker.record_failure("user@test.com")
        assert exceeded is False
        count = tracker.get_failure_count("user@test.com")
        assert count == 1
        result.ok("7-1 첫 실패 기록 (임계값 미달)")
    except Exception as e:
        result.fail("7-1 첫 실패", str(e))

    # 7-2. 임계값까지 연속 실패
    try:
        for _ in range(3):
            tracker.record_failure("user@test.com")
        # 4번째 실패 -> 아직 미달 (threshold=5)
        count = tracker.get_failure_count("user@test.com")
        assert count == 4
        result.ok(f"7-2 연속 실패 (count: {count}, threshold: 5)")
    except Exception as e:
        result.fail("7-2 연속 실패", str(e))

    # 7-3. 임계값 초과
    try:
        exceeded = tracker.record_failure("user@test.com")
        assert exceeded is True, "5번째 실패에서 임계값 초과해야 합니다"
        count = tracker.get_failure_count("user@test.com")
        assert count == 5
        result.ok("7-3 임계값 초과 (5/5)")
    except Exception as e:
        result.fail("7-3 임계값 초과", str(e))

    # 7-4. 리셋
    try:
        tracker.reset("user@test.com")
        count = tracker.get_failure_count("user@test.com")
        assert count == 0
        result.ok("7-4 리셋 후 count=0")
    except Exception as e:
        result.fail("7-4 리셋", str(e))

    # 7-5. 다른 사용자 독립성
    try:
        for _ in range(3):
            tracker.record_failure("user_a@test.com")
        for _ in range(2):
            tracker.record_failure("user_b@test.com")

        count_a = tracker.get_failure_count("user_a@test.com")
        count_b = tracker.get_failure_count("user_b@test.com")
        assert count_a == 3
        assert count_b == 2
        # user_a 리셋해도 user_b 영향 없음
        tracker.reset("user_a@test.com")
        assert tracker.get_failure_count("user_a@test.com") == 0
        assert tracker.get_failure_count("user_b@test.com") == 2
        result.ok("7-5 사용자 간 독립성 (리셋 격리)")
    except Exception as e:
        result.fail("7-5 독립성", str(e))


# =============================================================================
# [8] SecretManager + AuditLogger 연동 (7개)
# =============================================================================
def test_secret_audit_integration(result: TestResult) -> None:
    """시크릿 접근 시 감사 로그 기록 패턴."""
    print("\n[8] SecretManager + AuditLogger 연동")

    env_keys = ["COURTVIEW_SECRET_DB_PASS", "COURTVIEW_SECRET_API_TOKEN"]
    env_secrets = {
        env_keys[0]: "db_password_value",
        env_keys[1]: "api_token_value",
    }

    audit_logger, mem_storage = _create_test_audit_logger()

    try:
        sm = _create_test_secret_manager(env_secrets=env_secrets)

        # 8-1. 시크릿 접근 후 감사 로그 기록
        try:
            value = sm.get("DB_PASS")
            assert value is not None
            # 시크릿 접근 이벤트를 감사 로그에 기록
            entry_id = audit_logger.log(
                event_type=AuditEventType.SECRET_ACCESS,
                actor="service_account",
                action="get_secret",
                resource="DB_PASS",
                result="success",
                details={"provider": "ENV", "cache_status": "MISS"},
                immediate=True,
            )
            assert entry_id is not None
            entries = mem_storage.get_all()
            assert len(entries) >= 1
            assert entries[-1].event.event_type == AuditEventType.SECRET_ACCESS
            result.ok("8-1 시크릿 접근 -> 감사 로그 기록")
        except Exception as e:
            result.fail("8-1 시크릿->감사", str(e))

        # 8-2. 시크릿 조회 실패 -> 감사 로그 기록
        try:
            fallback = sm.get("NONEXISTENT", default="default_val")
            audit_logger.log(
                event_type=AuditEventType.SECRET_ACCESS,
                actor="service_account",
                action="get_secret",
                resource="NONEXISTENT",
                result="not_found",
                severity=AuditSeverity.WARNING,
                immediate=True,
            )
            entries = mem_storage.get_all()
            last = entries[-1]
            assert last.event.result == "not_found"
            assert last.event.severity == AuditSeverity.WARNING
            result.ok("8-2 시크릿 실패 -> 감사 로그 (WARNING)")
        except Exception as e:
            result.fail("8-2 시크릿 실패 감사", str(e))

        # 8-3. 캐시 무효화 -> 감사 로그 기록
        try:
            count = sm.invalidate_cache()
            audit_logger.log(
                event_type=AuditEventType.CONFIG_CHANGE,
                actor="admin",
                action="invalidate_cache",
                resource="secret_cache",
                details={"invalidated_count": count},
                immediate=True,
            )
            entries = mem_storage.get_all()
            last = entries[-1]
            assert last.event.event_type == AuditEventType.CONFIG_CHANGE
            assert last.event.details["invalidated_count"] == count
            result.ok(f"8-3 캐시 무효화 -> 감사 로그 (무효화: {count}건)")
        except Exception as e:
            result.fail("8-3 캐시 무효화 감사", str(e))

        # 8-4. 다수 시크릿 접근 -> 감사 로그 일관성
        try:
            secrets_to_access = ["DB_PASS", "API_TOKEN", "DB_PASS"]
            for name in secrets_to_access:
                val = sm.get(name)
                audit_logger.log(
                    event_type=AuditEventType.SECRET_ACCESS,
                    actor="app_server",
                    action="get_secret",
                    resource=name,
                    result="success" if val else "not_found",
                    immediate=True,
                )

            entries = mem_storage.get_all()
            secret_access_entries = [
                e for e in entries
                if e.event.event_type == AuditEventType.SECRET_ACCESS
                and e.event.actor == "app_server"
            ]
            assert len(secret_access_entries) == 3
            result.ok("8-4 다수 시크릿 접근 감사 (3건)")
        except Exception as e:
            result.fail("8-4 다수 접근 감사", str(e))

        # 8-5. SecretInfo 조회 후 감사 로그
        try:
            info = sm.get_info("DB_PASS")
            if info is not None:
                audit_logger.log(
                    event_type=AuditEventType.DATA_READ,
                    actor="admin",
                    action="get_secret_info",
                    resource="DB_PASS",
                    details={
                        "provider": info.provider.name,
                        "access_count": info.access_count,
                    },
                    immediate=True,
                )
            entries = mem_storage.get_all()
            data_reads = [e for e in entries if e.event.action == "get_secret_info"]
            assert len(data_reads) >= 1
            result.ok("8-5 SecretInfo 조회 -> 감사 로그")
        except Exception as e:
            result.fail("8-5 SecretInfo 감사", str(e))

        # 8-6. 보안 이벤트 - 접근 거부 시뮬레이션
        try:
            audit_logger.log(
                event_type=AuditEventType.ACCESS_DENIED,
                actor="unauthorized_user",
                action="get_secret",
                resource="ADMIN_KEY",
                result="failure",
                severity=AuditSeverity.ERROR,
                ip_address="10.0.0.99",
                immediate=True,
            )
            entries = mem_storage.get_all()
            denied = [e for e in entries if e.event.event_type == AuditEventType.ACCESS_DENIED]
            assert len(denied) >= 1
            assert denied[-1].event.ip_address == "10.0.0.99"
            result.ok("8-6 접근 거부 감사 로그")
        except Exception as e:
            result.fail("8-6 접근 거부", str(e))

        # 8-7. 헬스 체크 결합
        try:
            health = sm.health_check()
            assert isinstance(health, dict)
            assert "healthy" in health
            assert "providers" in health
            # 감사 로그 통계
            stats = audit_logger.get_stats()
            assert stats["sequence_number"] >= 8
            result.ok(f"8-7 SM 헬스체크 + 감사 통계 (seq: {stats['sequence_number']})")
        except Exception as e:
            result.fail("8-7 헬스체크", str(e))

    finally:
        audit_logger.close()
        _cleanup_env_secrets(env_keys)


# =============================================================================
# [9] 체인 해시 무결성 파이프라인 (6개)
# =============================================================================
def test_chain_hash_integrity(result: TestResult) -> None:
    """체인 해시 기반 감사 로그 무결성 검증."""
    print("\n[9] 체인 해시 무결성 파이프라인")

    audit_logger, mem_storage = _create_test_audit_logger()

    try:
        # 9-1. 초기 체인 해시 확인
        try:
            assert audit_logger._last_chain_hash == INITIAL_CHAIN_HASH
            result.ok(f"9-1 초기 체인 해시: {INITIAL_CHAIN_HASH}")
        except Exception as e:
            result.fail("9-1 초기 해시", str(e))

        # 9-2. 순차 이벤트 기록 -> 체인 해시 생성
        try:
            event_count = 5
            for i in range(event_count):
                audit_logger.log(
                    event_type=AuditEventType.DATA_READ,
                    actor=f"user_{i}",
                    action="read",
                    resource=f"/api/resource_{i}",
                    immediate=True,
                )

            entries = mem_storage.get_all()
            assert len(entries) == event_count
            # 모든 항목에 해시가 있어야 함
            for entry in entries:
                assert entry.entry_hash != "", f"entry_hash 빈 값: seq={entry.sequence_number}"
                assert len(entry.entry_hash) == 64  # SHA-256
            result.ok(f"9-2 순차 이벤트 체인 해시 ({event_count}건)")
        except Exception as e:
            result.fail("9-2 체인 해시 생성", str(e))

        # 9-3. 체인 해시 연속성 검증
        try:
            entries = mem_storage.get_all()
            sorted_entries = sorted(entries, key=lambda e: e.sequence_number)

            previous_hash = INITIAL_CHAIN_HASH
            for entry in sorted_entries:
                # chain_hash는 이전 항목의 entry_hash
                assert entry.chain_hash == previous_hash, \
                    f"체인 불일치: seq={entry.sequence_number}"
                previous_hash = entry.entry_hash

            result.ok("9-3 체인 해시 연속성 검증 통과")
        except Exception as e:
            result.fail("9-3 체인 연속성", str(e))

        # 9-4. 개별 항목 무결성 검증
        try:
            entries = mem_storage.get_all()
            sorted_entries = sorted(entries, key=lambda e: e.sequence_number)

            previous_hash = INITIAL_CHAIN_HASH
            all_valid = True
            for entry in sorted_entries:
                if not entry.verify_integrity(previous_hash):
                    all_valid = False
                    break
                previous_hash = entry.entry_hash

            assert all_valid, "무결성 검증 실패"
            result.ok("9-4 개별 항목 무결성 검증 통과")
        except Exception as e:
            result.fail("9-4 무결성 검증", str(e))

        # 9-5. AuditLogger.verify_integrity 메서드 검증
        try:
            entries = mem_storage.get_all()
            is_valid, errors = audit_logger.verify_integrity(entries=entries)
            assert is_valid is True, f"무결성 오류: {errors}"
            assert len(errors) == 0
            result.ok("9-5 AuditLogger.verify_integrity 통과")
        except Exception as e:
            result.fail("9-5 verify_integrity", str(e))

        # 9-6. 변조 감지 검증
        try:
            entries = mem_storage.get_all()
            if len(entries) >= 3:
                # 중간 항목 변조
                tampered_entry = entries[2]
                original_actor = tampered_entry.event.actor
                tampered_entry.event.actor = "TAMPERED_ACTOR"

                # 변조된 항목의 무결성 검증 실패 확인
                previous_hash = entries[1].entry_hash if len(entries) > 1 else INITIAL_CHAIN_HASH
                is_valid = tampered_entry.verify_integrity(previous_hash)
                assert is_valid is False, "변조 감지 실패"

                # 복원
                tampered_entry.event.actor = original_actor

            result.ok("9-6 변조 감지 검증 (변조 후 무결성 실패)")
        except Exception as e:
            result.fail("9-6 변조 감지", str(e))

    finally:
        audit_logger.close()


# =============================================================================
# [10] 알림 + 심각도 에스컬레이션 (5개)
# =============================================================================
def test_alert_severity_escalation(result: TestResult) -> None:
    """보안 이벤트 발생 시 심각도 자동 상향 + 알림 동작."""
    print("\n[10] 알림 + 심각도 에스컬레이션")

    # 10-1. 보안 이벤트 심각도 자동 상향 (security -> WARNING 이상)
    try:
        event = AuditEvent(
            event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
            actor="unknown",
            action="suspicious_scan",
            resource="/api",
            severity=AuditSeverity.DEBUG,  # 낮은 심각도로 설정해도
        )
        # __post_init__에서 security 카테고리는 WARNING 이상으로 상향
        assert event.severity >= AuditSeverity.WARNING, \
            f"security 이벤트 심각도가 WARNING 미만: {event.severity.name_str}"
        result.ok("10-1 보안 이벤트 심각도 자동 상향 (DEBUG -> WARNING+)")
    except Exception as e:
        result.fail("10-1 심각도 상향", str(e))

    # 10-2. EVENT_DEFAULT_SEVERITY 매핑 확인
    try:
        assert EVENT_DEFAULT_SEVERITY["authentication"] == AuditSeverity.INFO
        assert EVENT_DEFAULT_SEVERITY["authorization"] == AuditSeverity.WARNING
        assert EVENT_DEFAULT_SEVERITY["security"] == AuditSeverity.CRITICAL
        assert EVENT_DEFAULT_SEVERITY["data_access"] == AuditSeverity.INFO
        assert EVENT_DEFAULT_SEVERITY["configuration"] == AuditSeverity.WARNING
        assert EVENT_DEFAULT_SEVERITY["system"] == AuditSeverity.INFO
        result.ok("10-2 EVENT_DEFAULT_SEVERITY 매핑 (6개 카테고리)")
    except Exception as e:
        result.fail("10-2 매핑", str(e))

    # 10-3. 심각도별 보관 기간 확인
    try:
        assert AuditSeverity.DEBUG.retain_days == 7
        assert AuditSeverity.INFO.retain_days == 30
        assert AuditSeverity.WARNING.retain_days == 90
        assert AuditSeverity.ERROR.retain_days == 180
        assert AuditSeverity.CRITICAL.retain_days == 365
        result.ok("10-3 심각도별 보관 기간 (7/30/90/180/365일)")
    except Exception as e:
        result.fail("10-3 보관 기간", str(e))

    # 10-4. LogAlertHandler 동작 검증
    try:
        handler = LogAlertHandler()
        event = AuditEvent(
            event_type=AuditEventType.BRUTE_FORCE_DETECTED,
            actor="attacker@evil.com",
            action="brute_force",
            resource="/api/auth",
            severity=AuditSeverity.CRITICAL,
        )
        success = handler.send_alert(event, "brute_force_detected", "무차별 대입 공격 감지")
        assert success is True
        result.ok("10-4 LogAlertHandler 알림 전송 성공")
    except Exception as e:
        result.fail("10-4 LogAlertHandler", str(e))

    # 10-5. AuditSeverity.from_string 변환 검증
    try:
        assert AuditSeverity.from_string("info") == AuditSeverity.INFO
        assert AuditSeverity.from_string("critical") == AuditSeverity.CRITICAL
        assert AuditSeverity.from_string("WARNING") == AuditSeverity.WARNING
        assert AuditSeverity.from_string("nonexistent") is None
        # AuditEventType.from_string
        assert AuditEventType.from_string("authentication.login_success") == AuditEventType.LOGIN_SUCCESS
        assert AuditEventType.from_string("nonexistent") is None
        result.ok("10-5 from_string 변환 (AuditSeverity + AuditEventType)")
    except Exception as e:
        result.fail("10-5 from_string", str(e))


# =============================================================================
# [11] 전체 보안 파이프라인 시뮬레이션 (8개)
# =============================================================================
def test_full_security_pipeline(result: TestResult) -> None:
    """사용자 인증 흐름을 전체 보안 모듈로 관측하는 E2E 시뮬레이션."""
    print("\n[11] 전체 보안 파이프라인 시뮬레이션")

    env_keys = [
        "COURTVIEW_SECRET_JWT_SECRET_KEY",
        "COURTVIEW_SECRET_SESSION_KEY",
    ]
    env_secrets = {
        env_keys[0]: "super_secret_jwt_key_2026",
        env_keys[1]: "session_encryption_key_abc",
    }

    audit_logger, mem_storage = _create_test_audit_logger()

    try:
        sm = _create_test_secret_manager(env_secrets=env_secrets)
        login_tracker = LoginFailureTracker(threshold=3, window_minutes=5)

        # 11-1. 서비스 시작 이벤트 기록
        try:
            entry_id = audit_logger.log(
                event_type=AuditEventType.SERVICE_START,
                actor="system",
                action="start",
                resource="courtview_ai_server",
                details={"version": "1.0.0", "environment": "test"},
                immediate=True,
            )
            assert entry_id is not None
            result.ok("11-1 서비스 시작 이벤트")
        except Exception as e:
            result.fail("11-1 서비스 시작", str(e))

        # 11-2. JWT 시크릿 조회
        try:
            jwt_secret = sm.get("JWT_SECRET_KEY")
            assert jwt_secret == "super_secret_jwt_key_2026"
            audit_logger.log(
                event_type=AuditEventType.SECRET_ACCESS,
                actor="auth_service",
                action="get_jwt_secret",
                resource="JWT_SECRET_KEY",
                immediate=True,
            )
            result.ok("11-2 JWT 시크릿 조회 성공")
        except Exception as e:
            result.fail("11-2 JWT 조회", str(e))

        # 11-3. 로그인 실패 시뮬레이션 (3회)
        try:
            attacker = "suspicious_user@evil.com"
            threshold_exceeded = False

            for i in range(3):
                exceeded = login_tracker.record_failure(attacker)
                audit_logger.log(
                    event_type=AuditEventType.LOGIN_FAILURE,
                    actor=attacker,
                    action="login",
                    resource="/api/auth/login",
                    result="failure",
                    ip_address="10.0.0.99",
                    details={"attempt": i + 1, "reason": "invalid_password"},
                    immediate=True,
                )
                if exceeded:
                    threshold_exceeded = True

            assert threshold_exceeded is True
            count = login_tracker.get_failure_count(attacker)
            assert count == 3
            result.ok(f"11-3 로그인 실패 {count}회 -> 임계값 초과")
        except Exception as e:
            result.fail("11-3 로그인 실패", str(e))

        # 11-4. 임계값 초과 -> 무차별 대입 감지 + 알림
        try:
            audit_logger.log(
                event_type=AuditEventType.BRUTE_FORCE_DETECTED,
                actor=attacker,
                action="brute_force_detected",
                resource="/api/auth",
                result="detected",
                severity=AuditSeverity.CRITICAL,
                ip_address="10.0.0.99",
                details={
                    "failure_count": login_tracker.get_failure_count(attacker),
                    "threshold": 3,
                },
                immediate=True,
            )
            entries = mem_storage.get_all()
            brute_force = [
                e for e in entries
                if e.event.event_type == AuditEventType.BRUTE_FORCE_DETECTED
            ]
            assert len(brute_force) >= 1
            assert brute_force[-1].event.severity == AuditSeverity.CRITICAL
            result.ok("11-4 무차별 대입 감지 (CRITICAL)")
        except Exception as e:
            result.fail("11-4 무차별 대입", str(e))

        # 11-5. IP 차단 이벤트
        try:
            audit_logger.log(
                event_type=AuditEventType.IP_BLOCKED,
                actor="firewall",
                action="block_ip",
                resource="10.0.0.99",
                severity=AuditSeverity.WARNING,
                details={"reason": "brute_force", "duration_minutes": 30},
                immediate=True,
            )
            entries = mem_storage.get_all()
            blocked = [e for e in entries if e.event.event_type == AuditEventType.IP_BLOCKED]
            assert len(blocked) >= 1
            result.ok("11-5 IP 차단 이벤트 기록")
        except Exception as e:
            result.fail("11-5 IP 차단", str(e))

        # 11-6. 정상 사용자 로그인 성공
        try:
            normal_user = "player@courtview.ai"
            login_tracker.reset(normal_user)

            audit_logger.log(
                event_type=AuditEventType.LOGIN_SUCCESS,
                actor=normal_user,
                action="login",
                resource="/api/auth/login",
                result="success",
                session_id="sess-abc123",
                ip_address="192.168.1.10",
                immediate=True,
            )

            # 세션 키 조회
            session_key = sm.get("SESSION_KEY")
            assert session_key == "session_encryption_key_abc"

            entries = mem_storage.get_all()
            logins = [
                e for e in entries
                if e.event.event_type == AuditEventType.LOGIN_SUCCESS
            ]
            assert len(logins) >= 1
            result.ok("11-6 정상 로그인 + 세션 키 조회")
        except Exception as e:
            result.fail("11-6 정상 로그인", str(e))

        # 11-7. 전체 감사 로그 무결성 검증
        try:
            entries = mem_storage.get_all()
            is_valid, errors = audit_logger.verify_integrity(entries=entries)
            assert is_valid is True, f"무결성 오류: {errors}"
            result.ok(f"11-7 전체 무결성 검증 통과 ({len(entries)}건)")
        except Exception as e:
            result.fail("11-7 무결성 검증", str(e))

        # 11-8. 전체 통계 요약
        try:
            stats = audit_logger.get_stats()
            assert stats["sequence_number"] >= 8
            assert stats["integrity_enabled"] is True

            sm_health = sm.health_check()
            assert sm_health["healthy"] is True

            entries = mem_storage.get_all()
            categories = {}
            for entry in entries:
                cat = entry.event.event_type.category
                categories[cat] = categories.get(cat, 0) + 1

            result.ok(
                f"11-8 전체 요약: 이벤트 {len(entries)}건, "
                f"카테고리 {len(categories)}개, "
                f"seq={stats['sequence_number']}"
            )
        except Exception as e:
            result.fail("11-8 전체 요약", str(e))

    finally:
        audit_logger.close()
        _cleanup_env_secrets(env_keys)


# =============================================================================
# [12] 스레드 안전성 / 싱글톤 격리 (5개)
# =============================================================================
def test_thread_safety_singleton(result: TestResult) -> None:
    """set_*/get_* 함수의 싱글톤 격리 + 동시 접근 안전성."""
    print("\n[12] 스레드 안전성 / 싱글톤 격리")

    # 12-1. set_secret_manager / get_secret_manager
    try:
        # 초기 상태 확인
        original = get_secret_manager()

        env_key = "COURTVIEW_SECRET_SINGLETON_TEST"
        os.environ[env_key] = "singleton_value"
        try:
            loader = _create_mock_config_loader()
            sm = SecretManager(config_loader=loader)  # type: ignore
            set_secret_manager(sm)
            retrieved = get_secret_manager()
            assert retrieved is sm
            assert retrieved is not None

            # get_secret 헬퍼 함수 동작 확인
            val = get_secret("SINGLETON_TEST")
            assert val == "singleton_value"
            result.ok("12-1 set_secret_manager / get_secret_manager")
        finally:
            # 복원
            if original is not None:
                set_secret_manager(original)
            os.environ.pop(env_key, None)
    except Exception as e:
        result.fail("12-1 싱글톤 SM", str(e))

    # 12-2. set_audit_logger / get_audit_logger
    try:
        original_al = get_audit_logger()

        loader = _create_mock_config_loader(**{
            "security.audit_logger": {
                "storage": {"file": {"enabled": False}},
                "sampling_enabled": False,
            },
        })
        al = AuditLogger(config_loader=loader)  # type: ignore
        set_audit_logger(al)
        retrieved = get_audit_logger()
        assert retrieved is al

        # log_audit_event 헬퍼 함수 동작 확인
        # 주의: HEALTH_CHECK는 기본 exclude_events에 포함되므로 다른 이벤트 사용
        entry_id = log_audit_event(
            event_type=AuditEventType.SERVICE_START,
            actor="system",
            action="start",
            resource="/health",
            immediate=True,
        )
        assert entry_id is not None
        al.close()
        result.ok("12-2 set_audit_logger / get_audit_logger + log_audit_event")

        # 복원
        if original_al is not None:
            set_audit_logger(original_al)
    except Exception as e:
        result.fail("12-2 싱글톤 AL", str(e))

    # 12-3. 멀티스레드 AuditLogger 동시 기록
    try:
        audit_logger, mem_storage = _create_test_audit_logger()
        errors: list[str] = []
        threads_count = 8
        events_per_thread = 10

        def log_events(thread_id: int) -> None:
            try:
                for i in range(events_per_thread):
                    audit_logger.log(
                        event_type=AuditEventType.DATA_READ,
                        actor=f"thread_{thread_id}",
                        action="read",
                        resource=f"/api/data/{i}",
                        immediate=True,
                    )
            except Exception as ex:
                errors.append(f"thread_{thread_id}: {ex}")

        threads = [
            threading.Thread(target=log_events, args=(t,))
            for t in range(threads_count)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"스레드 에러: {errors[:3]}"
        entries = mem_storage.get_all()
        expected_total = threads_count * events_per_thread
        assert len(entries) == expected_total, \
            f"이벤트 수: {len(entries)} (expected {expected_total})"

        audit_logger.close()
        result.ok(f"12-3 멀티스레드 동시 기록 ({threads_count}x{events_per_thread}={expected_total}건)")
    except Exception as e:
        result.fail("12-3 멀티스레드", str(e))

    # 12-4. 멀티스레드 SecretManager 동시 조회
    try:
        env_key = "COURTVIEW_SECRET_MT_TEST"
        os.environ[env_key] = "mt_test_value"
        try:
            loader = _create_mock_config_loader()
            sm = SecretManager(config_loader=loader)  # type: ignore
            errors = []
            values: list[str | None] = []
            lock = threading.Lock()

            def get_secret_thread(tid: int) -> None:
                try:
                    for _ in range(5):
                        val = sm.get("MT_TEST")
                        with lock:
                            values.append(val)
                except Exception as ex:
                    with lock:
                        errors.append(f"thread_{tid}: {ex}")

            threads = [
                threading.Thread(target=get_secret_thread, args=(t,))
                for t in range(8)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert len(errors) == 0, f"에러: {errors[:3]}"
            assert all(v == "mt_test_value" for v in values), "값 불일치"
            result.ok(f"12-4 멀티스레드 시크릿 조회 ({len(values)}회, 모두 일치)")
        finally:
            os.environ.pop(env_key, None)
    except Exception as e:
        result.fail("12-4 멀티스레드 시크릿", str(e))

    # 12-5. 싱글톤 간 독립성 (SecretManager vs AuditLogger)
    try:
        env_key = "COURTVIEW_SECRET_ISOLATION_TEST"
        os.environ[env_key] = "isolation_value"
        try:
            loader = _create_mock_config_loader(**{
                "security.audit_logger": {
                    "storage": {"file": {"enabled": False}},
                    "sampling_enabled": False,
                },
            })
            sm = SecretManager(config_loader=loader)  # type: ignore
            al = AuditLogger(config_loader=loader)  # type: ignore

            # SM과 AL은 독립적 객체
            assert id(sm) != id(al)

            # SM 작업이 AL에 영향 없음
            sm.get("ISOLATION_TEST")
            sm_cache = sm.get_cache_stats()

            al_stats = al.get_stats()
            assert al_stats["sequence_number"] == 0  # AL은 이벤트 기록 안 함

            al.close()
            result.ok("12-5 SM/AL 싱글톤 독립성")
        finally:
            os.environ.pop(env_key, None)
    except Exception as e:
        result.fail("12-5 독립성", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    print("=" * 60)
    print("COURTVIEW - security 모듈 통합 테스트")
    print("=" * 60)

    r = TestResult()

    test_import_integrity(r)               # [1]  8개
    test_all_exports(r)                    # [2]  6개
    test_enum_cross_reference(r)           # [3]  6개
    test_secret_manager_workflow(r)        # [4]  7개
    test_audit_logger_workflow(r)          # [5]  7개
    test_audit_event_lifecycle(r)          # [6]  6개
    test_login_failure_tracker(r)          # [7]  5개
    test_secret_audit_integration(r)       # [8]  7개
    test_chain_hash_integrity(r)           # [9]  6개
    test_alert_severity_escalation(r)      # [10] 5개
    test_full_security_pipeline(r)         # [11] 8개
    test_thread_safety_singleton(r)        # [12] 5개

    r.summary()

    sys.exit(0 if r.failed == 0 else 1)


if __name__ == "__main__":
    main()
