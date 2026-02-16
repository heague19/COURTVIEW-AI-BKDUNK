# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/security/unit
파일: test_secret_manager.py
설명: 시크릿 매니저 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-16

테스트 범위:
    [1]  모듈 상수 검증 (6개)
    [2]  SecretProvider Enum (5개)
    [3]  SecretStatus Enum (5개)
    [4]  CacheStatus Enum (5개)
    [5]  예외 클래스 계층 (8개)
    [6]  SecretVersion 데이터 클래스 (5개)
    [7]  SecretInfo 데이터 클래스 (7개)
    [8]  CachedSecret 데이터 클래스 (6개)
    [9]  SecretValidationRule 데이터 클래스 (4개)
    [10] 유틸리티 함수 (_mask, _generate_cache_key) (6개)
    [11] BaseSecretProvider 인터페이스 (4개)
    [12] EnvProvider (8개)
    [13] FileProvider (6개)
    [14] SecretManager 초기화 (6개)
    [15] SecretManager.get / 캐시 (10개)
    [16] SecretManager 관리 API (8개)
    [17] 모듈 레벨 함수 (get_secret, get/set_secret_manager) (6개)
    [18] SecretRotator (6개)
    [19] VaultTokenManager (4개)
    [20] RotationSchedule 데이터 클래스 (3개)
    [21] __all__ 내보내기 검증 (4개)
    [22] 엣지 케이스 (6개)
"""

import io
import json
import os
import sys
import tempfile
import threading
import time
from dataclasses import fields
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# UTF-8 출력 강제
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from core_foundation.security.secret_manager import (
    # 상수
    DEFAULT_CACHE_TTL,
    DEFAULT_REFRESH_THRESHOLD,
    DEFAULT_MAX_CACHE_ENTRIES,
    DEFAULT_ENV_PREFIX,
    DEFAULT_AWS_REGION,
    DEFAULT_MASK_CHAR,
    MASK_VISIBLE_LENGTH,
    # Enum
    SecretProvider,
    SecretStatus,
    CacheStatus,
    # 예외
    SecretException,
    SecretNotFoundException,
    SecretAccessDeniedException,
    SecretValidationException,
    SecretProviderException,
    # 데이터 클래스
    SecretVersion,
    SecretInfo,
    CachedSecret,
    SecretValidationRule,
    RotationSchedule,
    # 클래스
    BaseSecretProvider,
    EnvProvider,
    FileProvider,
    SecretManager,
    SecretRotator,
    VaultTokenManager,
    # 함수
    get_secret,
    get_secret_manager,
    set_secret_manager,
    # 유틸리티
    _mask_secret_name,
    _mask_secret_value,
    _generate_cache_key,
)

from shared.exceptions.infrastructure_exceptions import InfrastructureException


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
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼: SecretManager 생성
# =============================================================================
def _make_manager(**overrides) -> SecretManager:
    """테스트용 SecretManager 생성 (Mock ConfigLoader)."""
    mock_loader = MagicMock()
    mock_loader.get.return_value = overrides.get("config", {})
    return SecretManager(
        config_loader=mock_loader,
        metrics_collector=overrides.get("metrics_collector"),
        error_tracker=overrides.get("error_tracker"),
    )


def _reset_global():
    """전역 인스턴스 리셋."""
    import core_foundation.security.secret_manager as mod
    mod._secret_manager_instance = None


# =============================================================================
# [1] 모듈 상수 검증
# =============================================================================
def test_constants(result: TestResult) -> None:
    """모듈 상수 검증."""
    print("\n[1] 모듈 상수 검증")

    # 1-1
    try:
        assert isinstance(DEFAULT_CACHE_TTL, int), f"int이 아님: {type(DEFAULT_CACHE_TTL)}"
        assert DEFAULT_CACHE_TTL > 0
        result.ok("1-1: DEFAULT_CACHE_TTL 양의 정수")
    except Exception as e:
        result.fail("1-1: DEFAULT_CACHE_TTL", str(e))

    # 1-2
    try:
        assert isinstance(DEFAULT_REFRESH_THRESHOLD, float)
        assert 0.0 < DEFAULT_REFRESH_THRESHOLD <= 1.0
        result.ok("1-2: DEFAULT_REFRESH_THRESHOLD 0~1 범위")
    except Exception as e:
        result.fail("1-2: DEFAULT_REFRESH_THRESHOLD", str(e))

    # 1-3
    try:
        assert isinstance(DEFAULT_MAX_CACHE_ENTRIES, int)
        assert DEFAULT_MAX_CACHE_ENTRIES > 0
        result.ok("1-3: DEFAULT_MAX_CACHE_ENTRIES 양의 정수")
    except Exception as e:
        result.fail("1-3: DEFAULT_MAX_CACHE_ENTRIES", str(e))

    # 1-4
    try:
        assert isinstance(DEFAULT_ENV_PREFIX, str)
        assert len(DEFAULT_ENV_PREFIX) > 0
        result.ok("1-4: DEFAULT_ENV_PREFIX 비어있지 않은 문자열")
    except Exception as e:
        result.fail("1-4: DEFAULT_ENV_PREFIX", str(e))

    # 1-5
    try:
        assert isinstance(DEFAULT_AWS_REGION, str)
        assert len(DEFAULT_AWS_REGION) > 0
        result.ok("1-5: DEFAULT_AWS_REGION 비어있지 않은 문자열")
    except Exception as e:
        result.fail("1-5: DEFAULT_AWS_REGION", str(e))

    # 1-6
    try:
        assert isinstance(DEFAULT_MASK_CHAR, str)
        assert len(DEFAULT_MASK_CHAR) == 1
        assert isinstance(MASK_VISIBLE_LENGTH, int)
        assert MASK_VISIBLE_LENGTH > 0
        result.ok("1-6: 마스킹 상수 정상")
    except Exception as e:
        result.fail("1-6: 마스킹 상수", str(e))


# =============================================================================
# [2] SecretProvider Enum
# =============================================================================
def test_secret_provider(result: TestResult) -> None:
    """SecretProvider Enum 검증."""
    print("\n[2] SecretProvider Enum")

    # 2-1
    try:
        members = list(SecretProvider)
        assert len(members) == 4, f"멤버 수: {len(members)} != 4"
        result.ok("2-1: SecretProvider 멤버 4개")
    except Exception as e:
        result.fail("2-1: SecretProvider 멤버 수", str(e))

    # 2-2
    try:
        expected = {"AWS", "VAULT", "ENV", "FILE"}
        actual = {m.name for m in SecretProvider}
        assert actual == expected, f"차이: {actual.symmetric_difference(expected)}"
        result.ok("2-2: 모든 멤버 이름 확인")
    except Exception as e:
        result.fail("2-2: 멤버 이름", str(e))

    # 2-3
    try:
        assert SecretProvider.AWS != SecretProvider.ENV
        result.ok("2-3: 멤버 고유성")
    except Exception as e:
        result.fail("2-3: 멤버 고유성", str(e))

    # 2-4
    try:
        assert SecretProvider["AWS"] is SecretProvider.AWS
        result.ok("2-4: 이름으로 접근")
    except Exception as e:
        result.fail("2-4: 이름으로 접근", str(e))

    # 2-5
    try:
        for p in SecretProvider:
            assert p.name in {"AWS", "VAULT", "ENV", "FILE"}
        result.ok("2-5: 모든 멤버 순회")
    except Exception as e:
        result.fail("2-5: 멤버 순회", str(e))


# =============================================================================
# [3] SecretStatus Enum
# =============================================================================
def test_secret_status(result: TestResult) -> None:
    """SecretStatus Enum 검증."""
    print("\n[3] SecretStatus Enum")

    # 3-1
    try:
        members = list(SecretStatus)
        assert len(members) == 5, f"멤버 수: {len(members)} != 5"
        result.ok("3-1: SecretStatus 멤버 5개")
    except Exception as e:
        result.fail("3-1: SecretStatus 멤버 수", str(e))

    # 3-2
    try:
        expected = {"ACTIVE", "ROTATED", "EXPIRED", "PENDING", "DEPRECATED"}
        actual = {m.name for m in SecretStatus}
        assert actual == expected
        result.ok("3-2: 모든 멤버 이름 확인")
    except Exception as e:
        result.fail("3-2: 멤버 이름", str(e))

    # 3-3
    try:
        assert SecretStatus.ACTIVE != SecretStatus.EXPIRED
        result.ok("3-3: 멤버 고유성")
    except Exception as e:
        result.fail("3-3: 멤버 고유성", str(e))

    # 3-4
    try:
        assert SecretStatus["ROTATED"] is SecretStatus.ROTATED
        result.ok("3-4: 이름으로 접근")
    except Exception as e:
        result.fail("3-4: 이름으로 접근", str(e))

    # 3-5
    try:
        for s in SecretStatus:
            assert isinstance(s.name, str)
        result.ok("3-5: 모든 멤버 순회")
    except Exception as e:
        result.fail("3-5: 멤버 순회", str(e))


# =============================================================================
# [4] CacheStatus Enum
# =============================================================================
def test_cache_status(result: TestResult) -> None:
    """CacheStatus Enum 검증."""
    print("\n[4] CacheStatus Enum")

    # 4-1
    try:
        members = list(CacheStatus)
        assert len(members) == 4, f"멤버 수: {len(members)} != 4"
        result.ok("4-1: CacheStatus 멤버 4개")
    except Exception as e:
        result.fail("4-1: CacheStatus 멤버 수", str(e))

    # 4-2
    try:
        expected = {"HIT", "MISS", "EXPIRED", "REFRESHED"}
        actual = {m.name for m in CacheStatus}
        assert actual == expected
        result.ok("4-2: 모든 멤버 이름 확인")
    except Exception as e:
        result.fail("4-2: 멤버 이름", str(e))

    # 4-3
    try:
        assert CacheStatus.HIT != CacheStatus.MISS
        result.ok("4-3: 멤버 고유성")
    except Exception as e:
        result.fail("4-3: 멤버 고유성", str(e))

    # 4-4
    try:
        assert CacheStatus["EXPIRED"] is CacheStatus.EXPIRED
        result.ok("4-4: 이름으로 접근")
    except Exception as e:
        result.fail("4-4: 이름으로 접근", str(e))

    # 4-5
    try:
        for c in CacheStatus:
            assert isinstance(c.value, int)
        result.ok("4-5: 모든 멤버 auto() 값")
    except Exception as e:
        result.fail("4-5: auto() 값", str(e))


# =============================================================================
# [5] 예외 클래스 계층
# =============================================================================
def test_exceptions(result: TestResult) -> None:
    """예외 클래스 계층 검증."""
    print("\n[5] 예외 클래스 계층")

    # 5-1
    try:
        assert issubclass(SecretException, InfrastructureException)
        result.ok("5-1: SecretException → InfrastructureException")
    except Exception as e:
        result.fail("5-1: SecretException 상속", str(e))

    # 5-2
    try:
        assert issubclass(SecretNotFoundException, SecretException)
        result.ok("5-2: SecretNotFoundException → SecretException")
    except Exception as e:
        result.fail("5-2: SecretNotFoundException 상속", str(e))

    # 5-3
    try:
        assert issubclass(SecretAccessDeniedException, SecretException)
        result.ok("5-3: SecretAccessDeniedException → SecretException")
    except Exception as e:
        result.fail("5-3: SecretAccessDeniedException 상속", str(e))

    # 5-4
    try:
        assert issubclass(SecretValidationException, SecretException)
        result.ok("5-4: SecretValidationException → SecretException")
    except Exception as e:
        result.fail("5-4: SecretValidationException 상속", str(e))

    # 5-5
    try:
        assert issubclass(SecretProviderException, SecretException)
        result.ok("5-5: SecretProviderException → SecretException")
    except Exception as e:
        result.fail("5-5: SecretProviderException 상속", str(e))

    # 5-6: 예외 인스턴스 생성 + 메시지
    try:
        ex = SecretException(message="테스트 오류")
        assert "테스트 오류" in str(ex)
        result.ok("5-6: SecretException 메시지")
    except Exception as e:
        result.fail("5-6: SecretException 메시지", str(e))

    # 5-7: SecretNotFoundException 기본 메시지
    try:
        ex = SecretNotFoundException()
        assert "찾을 수 없습니다" in str(ex)
        result.ok("5-7: SecretNotFoundException 기본 메시지")
    except Exception as e:
        result.fail("5-7: SecretNotFoundException 기본 메시지", str(e))

    # 5-8: SecretValidationException + validation_errors
    try:
        ex = SecretValidationException(
            validation_errors=["길이 부족", "패턴 불일치"]
        )
        assert "validation_errors" in ex.details
        assert len(ex.details["validation_errors"]) == 2
        result.ok("5-8: SecretValidationException validation_errors")
    except Exception as e:
        result.fail("5-8: validation_errors", str(e))


# =============================================================================
# [6] SecretVersion 데이터 클래스
# =============================================================================
def test_secret_version(result: TestResult) -> None:
    """SecretVersion 데이터 클래스 검증."""
    print("\n[6] SecretVersion 데이터 클래스")

    # 6-1
    try:
        v = SecretVersion(version_id="v1")
        assert v.version_id == "v1"
        assert v.version_stage == "AWSCURRENT"
        assert v.is_current is True
        result.ok("6-1: 기본값 생성")
    except Exception as e:
        result.fail("6-1: 기본값 생성", str(e))

    # 6-2
    try:
        v = SecretVersion(version_id="v2")
        assert isinstance(v.created_at, datetime)
        result.ok("6-2: created_at 자동 설정")
    except Exception as e:
        result.fail("6-2: created_at 자동 설정", str(e))

    # 6-3
    try:
        now = datetime.now(timezone.utc)
        v = SecretVersion(version_id="v3", created_at=now)
        assert v.created_at == now
        result.ok("6-3: 명시적 created_at 보존")
    except Exception as e:
        result.fail("6-3: 명시적 created_at", str(e))

    # 6-4
    try:
        v = SecretVersion(version_id="v4", version_stage="AWSPREVIOUS", is_current=False)
        assert v.version_stage == "AWSPREVIOUS"
        assert v.is_current is False
        result.ok("6-4: 커스텀 속성")
    except Exception as e:
        result.fail("6-4: 커스텀 속성", str(e))

    # 6-5
    try:
        field_names = {f.name for f in fields(SecretVersion)}
        expected = {"version_id", "version_stage", "created_at", "is_current"}
        assert field_names == expected
        result.ok("6-5: 필드 목록 완전")
    except Exception as e:
        result.fail("6-5: 필드 목록", str(e))


# =============================================================================
# [7] SecretInfo 데이터 클래스
# =============================================================================
def test_secret_info(result: TestResult) -> None:
    """SecretInfo 데이터 클래스 검증."""
    print("\n[7] SecretInfo 데이터 클래스")

    # 7-1
    try:
        info = SecretInfo(name="db_password", provider=SecretProvider.ENV)
        assert info.name == "db_password"
        assert info.provider == SecretProvider.ENV
        assert info.status == SecretStatus.ACTIVE
        assert info.access_count == 0
        assert info.cached is False
        result.ok("7-1: 기본값 생성")
    except Exception as e:
        result.fail("7-1: 기본값 생성", str(e))

    # 7-2
    try:
        info = SecretInfo(name="test", provider=SecretProvider.AWS)
        assert isinstance(info.created_at, datetime)
        result.ok("7-2: created_at 자동 설정")
    except Exception as e:
        result.fail("7-2: created_at 자동 설정", str(e))

    # 7-3
    try:
        info = SecretInfo(name="test", provider=SecretProvider.FILE, metadata={"env": "prod"})
        assert info.metadata == {"env": "prod"}
        result.ok("7-3: metadata 필드")
    except Exception as e:
        result.fail("7-3: metadata", str(e))

    # 7-4
    try:
        info = SecretInfo(name="test_secret", provider=SecretProvider.ENV)
        d = info.to_dict()
        assert isinstance(d, dict)
        assert "name" in d
        assert "provider" in d
        assert d["provider"] == "ENV"
        result.ok("7-4: to_dict() 변환")
    except Exception as e:
        result.fail("7-4: to_dict()", str(e))

    # 7-5: to_dict에서 이름 마스킹
    try:
        info = SecretInfo(name="database_password", provider=SecretProvider.ENV)
        d = info.to_dict()
        # 마스킹되어 원래 이름 전체가 나오지 않아야 함
        assert DEFAULT_MASK_CHAR in d["name"]
        result.ok("7-5: to_dict() 이름 마스킹")
    except Exception as e:
        result.fail("7-5: 이름 마스킹", str(e))

    # 7-6: version 포함
    try:
        v = SecretVersion(version_id="v1")
        info = SecretInfo(name="test", provider=SecretProvider.AWS, version=v)
        d = info.to_dict()
        assert d["version"] is not None
        assert d["version"]["version_id"] == "v1"
        result.ok("7-6: to_dict() version 포함")
    except Exception as e:
        result.fail("7-6: version 포함", str(e))

    # 7-7
    try:
        field_names = {f.name for f in fields(SecretInfo)}
        assert "name" in field_names
        assert "provider" in field_names
        assert "access_count" in field_names
        assert "cache_expires_at" in field_names
        assert len(field_names) >= 10
        result.ok("7-7: 필드 10개 이상")
    except Exception as e:
        result.fail("7-7: 필드 수", str(e))


# =============================================================================
# [8] CachedSecret 데이터 클래스
# =============================================================================
def test_cached_secret(result: TestResult) -> None:
    """CachedSecret 데이터 클래스 검증."""
    print("\n[8] CachedSecret 데이터 클래스")

    # 8-1
    try:
        cs = CachedSecret(name="key", value="val", provider=SecretProvider.ENV)
        assert cs.name == "key"
        assert cs.value == "val"
        assert cs.access_count == 0
        result.ok("8-1: 기본 생성")
    except Exception as e:
        result.fail("8-1: 기본 생성", str(e))

    # 8-2: 만료 없음 → is_expired = False
    try:
        cs = CachedSecret(name="k", value="v", provider=SecretProvider.ENV)
        assert cs.is_expired() is False
        result.ok("8-2: expires_at=None → 만료 안 됨")
    except Exception as e:
        result.fail("8-2: 만료 없음", str(e))

    # 8-3: 미래 만료 → is_expired = False
    try:
        cs = CachedSecret(
            name="k", value="v", provider=SecretProvider.ENV,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert cs.is_expired() is False
        result.ok("8-3: 미래 만료 → 만료 안 됨")
    except Exception as e:
        result.fail("8-3: 미래 만료", str(e))

    # 8-4: 과거 만료 → is_expired = True
    try:
        cs = CachedSecret(
            name="k", value="v", provider=SecretProvider.ENV,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        assert cs.is_expired() is True
        result.ok("8-4: 과거 만료 → 만료됨")
    except Exception as e:
        result.fail("8-4: 과거 만료", str(e))

    # 8-5: should_refresh — expires_at None → False
    try:
        cs = CachedSecret(name="k", value="v", provider=SecretProvider.ENV)
        assert cs.should_refresh() is False
        result.ok("8-5: should_refresh(expires_at=None) = False")
    except Exception as e:
        result.fail("8-5: should_refresh None", str(e))

    # 8-6: should_refresh — TTL 80% 경과
    try:
        now = datetime.now(timezone.utc)
        cs = CachedSecret(
            name="k", value="v", provider=SecretProvider.ENV,
            cached_at=now - timedelta(seconds=90),
            expires_at=now + timedelta(seconds=10),
        )
        # total_ttl = 100, elapsed = 90, threshold 0.8 → 90 >= 80 → True
        assert cs.should_refresh(threshold=0.8) is True
        result.ok("8-6: should_refresh(80% 경과) = True")
    except Exception as e:
        result.fail("8-6: should_refresh 80%", str(e))


# =============================================================================
# [9] SecretValidationRule 데이터 클래스
# =============================================================================
def test_validation_rule(result: TestResult) -> None:
    """SecretValidationRule 데이터 클래스 검증."""
    print("\n[9] SecretValidationRule 데이터 클래스")

    # 9-1
    try:
        rule = SecretValidationRule()
        assert rule.min_length is None
        assert rule.max_length is None
        assert rule.pattern is None
        assert rule.required is False
        result.ok("9-1: 기본값 전부 None/False")
    except Exception as e:
        result.fail("9-1: 기본값", str(e))

    # 9-2
    try:
        rule = SecretValidationRule(min_length=8, max_length=128, required=True)
        assert rule.min_length == 8
        assert rule.max_length == 128
        assert rule.required is True
        result.ok("9-2: 커스텀 값 설정")
    except Exception as e:
        result.fail("9-2: 커스텀 값", str(e))

    # 9-3
    try:
        rule = SecretValidationRule(pattern=r"^[A-Za-z0-9]+$")
        assert rule.pattern == r"^[A-Za-z0-9]+$"
        result.ok("9-3: 패턴 설정")
    except Exception as e:
        result.fail("9-3: 패턴", str(e))

    # 9-4
    try:
        field_names = {f.name for f in fields(SecretValidationRule)}
        expected = {"min_length", "max_length", "pattern", "required"}
        assert field_names == expected
        result.ok("9-4: 필드 목록 완전")
    except Exception as e:
        result.fail("9-4: 필드 목록", str(e))


# =============================================================================
# [10] 유틸리티 함수
# =============================================================================
def test_utility_functions(result: TestResult) -> None:
    """유틸리티 함수 검증."""
    print("\n[10] 유틸리티 함수")

    # 10-1: _mask_secret_name — 긴 이름
    try:
        masked = _mask_secret_name("database_password")
        assert DEFAULT_MASK_CHAR in masked
        assert len(masked) > 0
        # 앞 4자 + 마스크 + 뒤 4자
        assert masked.startswith("data")
        assert masked.endswith("word")
        result.ok("10-1: _mask_secret_name 긴 이름")
    except Exception as e:
        result.fail("10-1: 긴 이름 마스킹", str(e))

    # 10-2: _mask_secret_name — 짧은 이름 (전체 마스킹)
    try:
        masked = _mask_secret_name("key")
        assert masked == DEFAULT_MASK_CHAR * 3
        result.ok("10-2: _mask_secret_name 짧은 이름 전체 마스킹")
    except Exception as e:
        result.fail("10-2: 짧은 이름 마스킹", str(e))

    # 10-3: _mask_secret_name — 경계값 (MASK_VISIBLE_LENGTH * 2)
    try:
        # MASK_VISIBLE_LENGTH=4 → 8자 이하는 전체 마스킹
        name = "a" * (MASK_VISIBLE_LENGTH * 2)
        masked = _mask_secret_name(name)
        assert masked == DEFAULT_MASK_CHAR * len(name)
        result.ok("10-3: 경계값 마스킹")
    except Exception as e:
        result.fail("10-3: 경계값 마스킹", str(e))

    # 10-4: _mask_secret_value
    try:
        masked = _mask_secret_value("super_secret_password_123")
        assert DEFAULT_MASK_CHAR in masked
        assert len(masked) <= 8  # min(len, 8) * mask_char
        result.ok("10-4: _mask_secret_value 마스킹")
    except Exception as e:
        result.fail("10-4: 값 마스킹", str(e))

    # 10-5: _mask_secret_value 짧은 값
    try:
        masked = _mask_secret_value("ab")
        assert masked == DEFAULT_MASK_CHAR * 2
        result.ok("10-5: _mask_secret_value 짧은 값")
    except Exception as e:
        result.fail("10-5: 짧은 값 마스킹", str(e))

    # 10-6: _generate_cache_key
    try:
        key = _generate_cache_key("db_pass", SecretProvider.ENV)
        assert key == "ENV:db_pass"
        key2 = _generate_cache_key("db_pass", SecretProvider.AWS)
        assert key2 == "AWS:db_pass"
        assert key != key2
        result.ok("10-6: _generate_cache_key 형식")
    except Exception as e:
        result.fail("10-6: cache_key", str(e))


# =============================================================================
# [11] BaseSecretProvider 인터페이스
# =============================================================================
def test_base_provider(result: TestResult) -> None:
    """BaseSecretProvider 인터페이스 검증."""
    print("\n[11] BaseSecretProvider 인터페이스")

    # 11-1: 추상 클래스 확인
    try:
        from abc import ABC
        assert issubclass(BaseSecretProvider, ABC)
        result.ok("11-1: BaseSecretProvider는 ABC")
    except Exception as e:
        result.fail("11-1: ABC 상속", str(e))

    # 11-2: 직접 인스턴스화 불가
    try:
        raised = False
        try:
            _ = BaseSecretProvider(config={})
        except TypeError:
            raised = True
        assert raised, "TypeError 미발생"
        result.ok("11-2: 직접 인스턴스화 불가")
    except Exception as e:
        result.fail("11-2: 인스턴스화", str(e))

    # 11-3: 필수 추상 메서드 확인
    try:
        abstract_methods = set()
        for cls in BaseSecretProvider.__mro__:
            for attr_name in vars(cls):
                attr = getattr(cls, attr_name, None)
                if getattr(attr, "__isabstractmethod__", False):
                    abstract_methods.add(attr_name)
        expected = {"get_secret", "secret_exists", "provider_type", "is_available"}
        assert expected.issubset(abstract_methods), f"누락: {expected - abstract_methods}"
        result.ok("11-3: 추상 메서드 4개 확인")
    except Exception as e:
        result.fail("11-3: 추상 메서드", str(e))

    # 11-4: _lock 존재 확인 (콘크리트 서브클래스)
    try:
        env = EnvProvider(config={})
        assert hasattr(env, "_lock")
        result.ok("11-4: 서브클래스에 _lock 존재")
    except Exception as e:
        result.fail("11-4: _lock", str(e))


# =============================================================================
# [12] EnvProvider
# =============================================================================
def test_env_provider(result: TestResult) -> None:
    """EnvProvider 검증."""
    print("\n[12] EnvProvider")

    # 12-1: provider_type
    try:
        p = EnvProvider(config={})
        assert p.provider_type == SecretProvider.ENV
        result.ok("12-1: provider_type = ENV")
    except Exception as e:
        result.fail("12-1: provider_type", str(e))

    # 12-2: is_available = True (항상)
    try:
        p = EnvProvider(config={})
        assert p.is_available is True
        result.ok("12-2: is_available = True")
    except Exception as e:
        result.fail("12-2: is_available", str(e))

    # 12-3: 환경변수 시크릿 조회 성공
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}TEST_SECRET_XYZ".upper()
        os.environ[env_key] = "my_secret_value"
        try:
            p = EnvProvider(config={"prefix": DEFAULT_ENV_PREFIX})
            value, version = p.get_secret("test_secret_xyz")
            assert value == "my_secret_value"
            assert version is not None
            assert version.version_id == "env"
            result.ok("12-3: 환경변수 시크릿 조회 성공")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("12-3: 환경변수 조회", str(e))

    # 12-4: 존재하지 않는 시크릿 → SecretNotFoundException
    try:
        p = EnvProvider(config={"prefix": "NONEXIST_PREFIX_"})
        raised = False
        try:
            p.get_secret("nonexistent_key_12345")
        except SecretNotFoundException:
            raised = True
        assert raised
        result.ok("12-4: 미존재 시크릿 → SecretNotFoundException")
    except Exception as e:
        result.fail("12-4: 미존재 시크릿", str(e))

    # 12-5: secret_exists 확인
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}EXISTS_TEST".upper()
        os.environ[env_key] = "yes"
        try:
            p = EnvProvider(config={"prefix": DEFAULT_ENV_PREFIX})
            assert p.secret_exists("EXISTS_TEST") is True
            assert p.secret_exists("DOES_NOT_EXIST_99999") is False
            result.ok("12-5: secret_exists 정상")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("12-5: secret_exists", str(e))

    # 12-6: 커스텀 prefix
    try:
        os.environ["MY_APP_SECRET_DB"] = "db_pass"
        try:
            p = EnvProvider(config={"prefix": "MY_APP_SECRET_"})
            value, _ = p.get_secret("DB")
            assert value == "db_pass"
            result.ok("12-6: 커스텀 prefix 적용")
        finally:
            if "MY_APP_SECRET_DB" in os.environ:
                del os.environ["MY_APP_SECRET_DB"]
    except Exception as e:
        result.fail("12-6: 커스텀 prefix", str(e))

    # 12-7: case_sensitive 설정
    try:
        p = EnvProvider(config={"case_sensitive": False})
        # _get_env_key는 대문자로 변환
        key = p._get_env_key("my_test")
        assert key == key.upper()
        result.ok("12-7: case_sensitive=False → 대문자 변환")
    except Exception as e:
        result.fail("12-7: case_sensitive", str(e))

    # 12-8: 스레드 안전 (RLock)
    try:
        p = EnvProvider(config={})
        assert hasattr(p, "_lock")
        import threading
        assert isinstance(p._lock, type(threading.RLock()))
        result.ok("12-8: 스레드 안전 (RLock)")
    except Exception as e:
        result.fail("12-8: 스레드 안전", str(e))


# =============================================================================
# [13] FileProvider
# =============================================================================
def test_file_provider(result: TestResult) -> None:
    """FileProvider 검증."""
    print("\n[13] FileProvider")

    # 13-1: provider_type
    try:
        p = FileProvider(config={"path": "nonexistent.yaml"})
        assert p.provider_type == SecretProvider.FILE
        result.ok("13-1: provider_type = FILE")
    except Exception as e:
        result.fail("13-1: provider_type", str(e))

    # 13-2: is_available — 파일 없으면 False
    try:
        p = FileProvider(config={"path": "/nonexistent/path/secrets.yaml"})
        assert p.is_available is False
        result.ok("13-2: is_available = False (파일 없음)")
    except Exception as e:
        result.fail("13-2: is_available", str(e))

    # 13-3: JSON 파일에서 시크릿 로드
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"db_pass": "secret123", "api_key": "key456"}, f)
            tmp_path = f.name
        try:
            p = FileProvider(config={"path": tmp_path})
            value, version = p.get_secret("db_pass")
            assert value == "secret123"
            assert version is not None
            result.ok("13-3: JSON 파일 시크릿 로드")
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        result.fail("13-3: JSON 파일", str(e))

    # 13-4: 미존재 키 → SecretNotFoundException
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"a": "1"}, f)
            tmp_path = f.name
        try:
            p = FileProvider(config={"path": tmp_path})
            raised = False
            try:
                p.get_secret("nonexistent")
            except SecretNotFoundException:
                raised = True
            assert raised
            result.ok("13-4: 미존재 키 → SecretNotFoundException")
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        result.fail("13-4: 미존재 키", str(e))

    # 13-5: secret_exists
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"key1": "val1"}, f)
            tmp_path = f.name
        try:
            p = FileProvider(config={"path": tmp_path})
            assert p.secret_exists("key1") is True
            assert p.secret_exists("key2") is False
            result.ok("13-5: secret_exists 정상")
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        result.fail("13-5: secret_exists", str(e))

    # 13-6: 파일 없을 때 get_secret → 빈 로드
    try:
        p = FileProvider(config={"path": "/nonexistent_file.json"})
        raised = False
        try:
            p.get_secret("any_key")
        except SecretNotFoundException:
            raised = True
        assert raised
        result.ok("13-6: 파일 없을 때 SecretNotFoundException")
    except Exception as e:
        result.fail("13-6: 파일 없음", str(e))


# =============================================================================
# [14] SecretManager 초기화
# =============================================================================
def test_secret_manager_init(result: TestResult) -> None:
    """SecretManager 초기화 검증."""
    print("\n[14] SecretManager 초기화")

    # 14-1: 기본 초기화 성공
    try:
        mgr = _make_manager()
        assert mgr is not None
        result.ok("14-1: 기본 초기화 성공")
    except Exception as e:
        result.fail("14-1: 기본 초기화", str(e))

    # 14-2: _providers에 ENV 포함
    try:
        mgr = _make_manager()
        assert SecretProvider.ENV in mgr._providers
        result.ok("14-2: 기본 ENV 제공자 등록")
    except Exception as e:
        result.fail("14-2: ENV 제공자", str(e))

    # 14-3: 캐시 초기 빈 상태
    try:
        mgr = _make_manager()
        assert len(mgr._cache) == 0
        result.ok("14-3: 캐시 초기 빈 상태")
    except Exception as e:
        result.fail("14-3: 캐시 초기화", str(e))

    # 14-4: _lock 존재
    try:
        mgr = _make_manager()
        assert hasattr(mgr, "_lock")
        result.ok("14-4: _lock 존재")
    except Exception as e:
        result.fail("14-4: _lock", str(e))

    # 14-5: get_providers 반환
    try:
        mgr = _make_manager()
        providers = mgr.get_providers()
        assert isinstance(providers, list)
        assert "ENV" in providers
        result.ok("14-5: get_providers() ENV 포함")
    except Exception as e:
        result.fail("14-5: get_providers", str(e))

    # 14-6: health_check 정상
    try:
        mgr = _make_manager()
        health = mgr.health_check()
        assert isinstance(health, dict)
        assert "healthy" in health
        assert "providers" in health
        assert "cache" in health
        result.ok("14-6: health_check 구조 정상")
    except Exception as e:
        result.fail("14-6: health_check", str(e))


# =============================================================================
# [15] SecretManager.get / 캐시
# =============================================================================
def test_secret_manager_get(result: TestResult) -> None:
    """SecretManager.get 및 캐시 검증."""
    print("\n[15] SecretManager.get / 캐시")

    # 15-1: 환경변수 시크릿 조회
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}SM_GET_TEST".upper()
        os.environ[env_key] = "test_value_15_1"
        try:
            mgr = _make_manager()
            value = mgr.get("sm_get_test")
            assert value == "test_value_15_1"
            result.ok("15-1: 환경변수 시크릿 조회")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("15-1: 환경변수 조회", str(e))

    # 15-2: 미존재 시크릿 + default
    try:
        mgr = _make_manager()
        value = mgr.get("nonexistent_xyz_999", default="fallback")
        assert value == "fallback"
        result.ok("15-2: default 폴백")
    except Exception as e:
        result.fail("15-2: default 폴백", str(e))

    # 15-3: 미존재 시크릿, default=None → SecretNotFoundException
    try:
        mgr = _make_manager()
        raised = False
        try:
            mgr.get("nonexistent_xyz_998")
        except SecretNotFoundException:
            raised = True
        assert raised
        result.ok("15-3: default 없음 → SecretNotFoundException")
    except Exception as e:
        result.fail("15-3: SecretNotFoundException", str(e))

    # 15-4: 캐시 히트 확인
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}CACHE_TEST_15_4".upper()
        os.environ[env_key] = "cached_val"
        try:
            mgr = _make_manager()
            # 첫 호출: 캐시 미스 → 제공자 조회
            v1 = mgr.get("cache_test_15_4")
            assert v1 == "cached_val"
            # 두 번째 호출: 캐시 히트
            v2 = mgr.get("cache_test_15_4")
            assert v2 == "cached_val"
            # 캐시에 있는지 확인
            assert len(mgr._cache) >= 1
            result.ok("15-4: 캐시 히트 동작")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("15-4: 캐시 히트", str(e))

    # 15-5: bypass_cache
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}BYPASS_TEST".upper()
        os.environ[env_key] = "original"
        try:
            mgr = _make_manager()
            v1 = mgr.get("bypass_test")
            assert v1 == "original"
            # 값 변경
            os.environ[env_key] = "updated"
            # bypass_cache=True → 새 값
            v2 = mgr.get("bypass_test", bypass_cache=True)
            assert v2 == "updated"
            result.ok("15-5: bypass_cache 동작")
        finally:
            if env_key in os.environ:
                del os.environ[env_key]
    except Exception as e:
        result.fail("15-5: bypass_cache", str(e))

    # 15-6: get_required 성공
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}REQUIRED_TEST".upper()
        os.environ[env_key] = "required_val"
        try:
            mgr = _make_manager()
            v = mgr.get_required("required_test")
            assert v == "required_val"
            result.ok("15-6: get_required 성공")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("15-6: get_required", str(e))

    # 15-7: get_info 조회
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}INFO_TEST".upper()
        os.environ[env_key] = "info_val"
        try:
            mgr = _make_manager()
            mgr.get("info_test")
            info = mgr.get_info("info_test")
            assert info is not None
            assert info.access_count >= 1
            result.ok("15-7: get_info 조회")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("15-7: get_info", str(e))

    # 15-8: invalidate_cache 특정 키
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}INV_TEST".upper()
        os.environ[env_key] = "to_invalidate"
        try:
            mgr = _make_manager()
            mgr.get("inv_test")
            assert len(mgr._cache) >= 1
            count = mgr.invalidate_cache("inv_test")
            assert count >= 1
            result.ok("15-8: invalidate_cache 특정 키")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("15-8: invalidate_cache 특정", str(e))

    # 15-9: invalidate_cache 전체
    try:
        env_key1 = f"{DEFAULT_ENV_PREFIX}INV_ALL_1".upper()
        env_key2 = f"{DEFAULT_ENV_PREFIX}INV_ALL_2".upper()
        os.environ[env_key1] = "v1"
        os.environ[env_key2] = "v2"
        try:
            mgr = _make_manager()
            mgr.get("inv_all_1")
            mgr.get("inv_all_2")
            count = mgr.invalidate_cache()
            assert count >= 2
            assert len(mgr._cache) == 0
            result.ok("15-9: invalidate_cache 전체")
        finally:
            for k in [env_key1, env_key2]:
                if k in os.environ:
                    del os.environ[k]
    except Exception as e:
        result.fail("15-9: invalidate_cache 전체", str(e))

    # 15-10: exists
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}EXISTS_SM_TEST".upper()
        os.environ[env_key] = "y"
        try:
            mgr = _make_manager()
            assert mgr.exists("EXISTS_SM_TEST") is True
            assert mgr.exists("DOES_NOT_EXIST_99") is False
            result.ok("15-10: exists 동작")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("15-10: exists", str(e))


# =============================================================================
# [16] SecretManager 관리 API
# =============================================================================
def test_secret_manager_api(result: TestResult) -> None:
    """SecretManager 관리 API 검증."""
    print("\n[16] SecretManager 관리 API")

    # 16-1: get_cache_stats
    try:
        mgr = _make_manager()
        stats = mgr.get_cache_stats()
        assert isinstance(stats, dict)
        assert "enabled" in stats
        assert "total_entries" in stats
        assert "max_entries" in stats
        assert "ttl_seconds" in stats
        result.ok("16-1: get_cache_stats 구조")
    except Exception as e:
        result.fail("16-1: get_cache_stats", str(e))

    # 16-2: get_cache_stats total_entries 증가
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}STATS_TEST".upper()
        os.environ[env_key] = "stat_val"
        try:
            mgr = _make_manager()
            before = mgr.get_cache_stats()["total_entries"]
            mgr.get("stats_test")
            after = mgr.get_cache_stats()["total_entries"]
            assert after == before + 1
            result.ok("16-2: total_entries 증가")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("16-2: total_entries", str(e))

    # 16-3: get_providers 목록
    try:
        mgr = _make_manager()
        providers = mgr.get_providers()
        assert isinstance(providers, list)
        assert len(providers) >= 1
        result.ok("16-3: get_providers 목록")
    except Exception as e:
        result.fail("16-3: get_providers", str(e))

    # 16-4: health_check healthy=True
    try:
        mgr = _make_manager()
        health = mgr.health_check()
        assert health["healthy"] is True
        assert "ENV" in health["providers"]
        result.ok("16-4: health_check healthy=True")
    except Exception as e:
        result.fail("16-4: health_check healthy", str(e))

    # 16-5: health_check 제공자 상태
    try:
        mgr = _make_manager()
        health = mgr.health_check()
        env_health = health["providers"]["ENV"]
        assert env_health["available"] is True
        assert env_health["healthy"] is True
        result.ok("16-5: health_check 제공자 상태")
    except Exception as e:
        result.fail("16-5: 제공자 상태", str(e))

    # 16-6: _validate_secret 성공 (규칙 없음)
    try:
        mgr = _make_manager()
        # 규칙 없으면 검증 통과
        mgr._validate_secret("any_name", "any_value")
        result.ok("16-6: _validate_secret 규칙 없음 → 통과")
    except Exception as e:
        result.fail("16-6: _validate_secret", str(e))

    # 16-7: _validate_secret 실패 (min_length 위반)
    try:
        mgr = _make_manager()
        mgr._validation_rules["short_secret"] = SecretValidationRule(min_length=10)
        raised = False
        try:
            mgr._validate_secret("short_secret", "abc")
        except SecretValidationException:
            raised = True
        assert raised
        result.ok("16-7: _validate_secret min_length 위반")
    except Exception as e:
        result.fail("16-7: _validate_secret 위반", str(e))

    # 16-8: _validate_secret 패턴 위반
    try:
        mgr = _make_manager()
        mgr._validation_rules["pattern_test"] = SecretValidationRule(
            pattern=r"^[A-Z]+$"
        )
        raised = False
        try:
            mgr._validate_secret("pattern_test", "lowercase")
        except SecretValidationException:
            raised = True
        assert raised
        result.ok("16-8: _validate_secret 패턴 위반")
    except Exception as e:
        result.fail("16-8: 패턴 위반", str(e))


# =============================================================================
# [17] 모듈 레벨 함수
# =============================================================================
def test_module_functions(result: TestResult) -> None:
    """모듈 레벨 함수 검증."""
    print("\n[17] 모듈 레벨 함수")

    # 17-1: get_secret_manager 초기 None
    try:
        _reset_global()
        assert get_secret_manager() is None
        result.ok("17-1: get_secret_manager 초기 None")
    except Exception as e:
        result.fail("17-1: 초기 None", str(e))

    # 17-2: set_secret_manager / get_secret_manager
    try:
        _reset_global()
        mgr = _make_manager()
        set_secret_manager(mgr)
        assert get_secret_manager() is mgr
        result.ok("17-2: set/get_secret_manager")
    except Exception as e:
        result.fail("17-2: set/get", str(e))
    finally:
        _reset_global()

    # 17-3: get_secret 매니저 있을 때
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}MODULE_FUNC_TEST".upper()
        os.environ[env_key] = "module_val"
        try:
            _reset_global()
            mgr = _make_manager()
            set_secret_manager(mgr)
            val = get_secret("module_func_test")
            assert val == "module_val"
            result.ok("17-3: get_secret 매니저 사용")
        finally:
            _reset_global()
            del os.environ[env_key]
    except Exception as e:
        result.fail("17-3: get_secret 매니저", str(e))

    # 17-4: get_secret 매니저 없을 때 환경변수 폴백
    try:
        _reset_global()
        env_key = f"{DEFAULT_ENV_PREFIX}FALLBACK_TEST".upper()
        os.environ[env_key] = "fallback_val"
        try:
            val = get_secret("FALLBACK_TEST")
            assert val == "fallback_val"
            result.ok("17-4: get_secret 환경변수 폴백")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("17-4: 환경변수 폴백", str(e))

    # 17-5: get_secret default 반환
    try:
        _reset_global()
        val = get_secret("nonexistent_key_module_test", default="default_ret")
        assert val == "default_ret"
        result.ok("17-5: get_secret default 반환")
    except Exception as e:
        result.fail("17-5: default 반환", str(e))

    # 17-6: get_secret 없으면 None
    try:
        _reset_global()
        val = get_secret("totally_nonexistent_key_xyz")
        assert val is None
        result.ok("17-6: get_secret 기본 None")
    except Exception as e:
        result.fail("17-6: 기본 None", str(e))


# =============================================================================
# [18] SecretRotator
# =============================================================================
def test_secret_rotator(result: TestResult) -> None:
    """SecretRotator 검증."""
    print("\n[18] SecretRotator")

    # 18-1: 초기화
    try:
        mgr = _make_manager()
        rotator = SecretRotator(secret_manager=mgr)
        assert rotator is not None
        assert rotator._running is False
        result.ok("18-1: SecretRotator 초기화")
    except Exception as e:
        result.fail("18-1: 초기화", str(e))

    # 18-2: add_schedule
    try:
        mgr = _make_manager()
        rotator = SecretRotator(secret_manager=mgr)
        rotator.add_schedule("test_secret", interval_days=30)
        schedules = rotator.get_schedules()
        assert "test_secret" in schedules
        assert schedules["test_secret"].interval_days == 30
        result.ok("18-2: add_schedule 동작")
    except Exception as e:
        result.fail("18-2: add_schedule", str(e))

    # 18-3: remove_schedule
    try:
        mgr = _make_manager()
        rotator = SecretRotator(secret_manager=mgr)
        rotator.add_schedule("to_remove", interval_days=7)
        rotator.remove_schedule("to_remove")
        assert "to_remove" not in rotator.get_schedules()
        result.ok("18-3: remove_schedule 동작")
    except Exception as e:
        result.fail("18-3: remove_schedule", str(e))

    # 18-4: get_next_rotation
    try:
        mgr = _make_manager()
        rotator = SecretRotator(secret_manager=mgr)
        rotator.add_schedule("rot_test", interval_days=14)
        next_rot = rotator.get_next_rotation("rot_test")
        assert isinstance(next_rot, datetime)
        # 14일 후쯤이어야 함
        diff = (next_rot - datetime.now(timezone.utc)).days
        assert 13 <= diff <= 15
        result.ok("18-4: get_next_rotation 14일 후")
    except Exception as e:
        result.fail("18-4: get_next_rotation", str(e))

    # 18-5: start / stop
    try:
        mgr = _make_manager()
        rotator = SecretRotator(secret_manager=mgr, check_interval_seconds=1)
        rotator.start()
        assert rotator._running is True
        rotator.stop()
        assert rotator._running is False
        result.ok("18-5: start/stop 동작")
    except Exception as e:
        result.fail("18-5: start/stop", str(e))

    # 18-6: rotate_now 등록되지 않은 시크릿
    try:
        mgr = _make_manager()
        rotator = SecretRotator(secret_manager=mgr)
        ret = rotator.rotate_now("unregistered_secret")
        assert ret is False
        result.ok("18-6: rotate_now 미등록 → False")
    except Exception as e:
        result.fail("18-6: rotate_now 미등록", str(e))


# =============================================================================
# [19] VaultTokenManager
# =============================================================================
def test_vault_token_manager(result: TestResult) -> None:
    """VaultTokenManager 검증."""
    print("\n[19] VaultTokenManager")

    # 19-1: 초기화
    try:
        mock_provider = MagicMock()
        vtm = VaultTokenManager(vault_provider=mock_provider)
        assert vtm is not None
        assert vtm._running is False
        result.ok("19-1: VaultTokenManager 초기화")
    except Exception as e:
        result.fail("19-1: 초기화", str(e))

    # 19-2: start / stop
    try:
        mock_provider = MagicMock()
        vtm = VaultTokenManager(
            vault_provider=mock_provider,
            check_interval_seconds=1,
        )
        vtm.start()
        assert vtm._running is True
        vtm.stop()
        assert vtm._running is False
        result.ok("19-2: start/stop 동작")
    except Exception as e:
        result.fail("19-2: start/stop", str(e))

    # 19-3: renew_threshold 설정
    try:
        mock_provider = MagicMock()
        vtm = VaultTokenManager(
            vault_provider=mock_provider,
            renew_threshold_seconds=600,
        )
        assert vtm._renew_threshold == 600
        result.ok("19-3: renew_threshold 설정")
    except Exception as e:
        result.fail("19-3: renew_threshold", str(e))

    # 19-4: get_token_ttl (Vault 미사용)
    try:
        mock_provider = MagicMock()
        vtm = VaultTokenManager(vault_provider=mock_provider)
        # VAULT_AVAILABLE = False → None 반환
        ttl = vtm.get_token_ttl()
        # Vault 미설치 환경에서는 None
        assert ttl is None
        result.ok("19-4: get_token_ttl None (Vault 미사용)")
    except Exception as e:
        result.fail("19-4: get_token_ttl", str(e))


# =============================================================================
# [20] RotationSchedule 데이터 클래스
# =============================================================================
def test_rotation_schedule(result: TestResult) -> None:
    """RotationSchedule 데이터 클래스 검증."""
    print("\n[20] RotationSchedule 데이터 클래스")

    # 20-1: 기본 생성
    try:
        schedule = RotationSchedule(secret_name="test_key", interval_days=90)
        assert schedule.secret_name == "test_key"
        assert schedule.interval_days == 90
        assert schedule.enabled is True
        result.ok("20-1: 기본 생성")
    except Exception as e:
        result.fail("20-1: 기본 생성", str(e))

    # 20-2: 훅 함수 설정
    try:
        pre_hook = lambda name: True
        post_hook = lambda old, new: None
        schedule = RotationSchedule(
            secret_name="test_key",
            interval_days=30,
            pre_rotation_hook=pre_hook,
            post_rotation_hook=post_hook,
        )
        assert schedule.pre_rotation_hook is pre_hook
        assert schedule.post_rotation_hook is post_hook
        result.ok("20-2: 훅 함수 설정")
    except Exception as e:
        result.fail("20-2: 훅 함수", str(e))

    # 20-3: 필드 목록
    try:
        field_names = {f.name for f in fields(RotationSchedule)}
        expected = {
            "secret_name", "interval_days", "last_rotated",
            "next_rotation", "rotation_func", "pre_rotation_hook",
            "post_rotation_hook", "enabled",
        }
        assert field_names == expected
        result.ok("20-3: 필드 목록 완전")
    except Exception as e:
        result.fail("20-3: 필드 목록", str(e))


# =============================================================================
# [21] __all__ 내보내기 검증
# =============================================================================
def test_all_exports(result: TestResult) -> None:
    """__all__ 내보내기 검증."""
    print("\n[21] __all__ 내보내기 검증")

    import core_foundation.security.secret_manager as mod
    import core_foundation.security as pkg

    # 21-1: secret_manager.__all__ 존재
    try:
        assert hasattr(mod, "__all__")
        assert isinstance(mod.__all__, list)
        assert len(mod.__all__) >= 20
        result.ok(f"21-1: secret_manager.__all__ = {len(mod.__all__)}개")
    except Exception as e:
        result.fail("21-1: __all__ 존재", str(e))

    # 21-2: __all__ 항목 실제 존재
    try:
        missing = [name for name in mod.__all__ if not hasattr(mod, name)]
        assert len(missing) == 0, f"누락: {missing}"
        result.ok("21-2: __all__ 모든 항목 실제 존재")
    except Exception as e:
        result.fail("21-2: __all__ 항목 존재", str(e))

    # 21-3: __init__.py __all__ 존재
    try:
        assert hasattr(pkg, "__all__")
        assert len(pkg.__all__) >= 26  # secret_manager 26개
        result.ok(f"21-3: __init__.py __all__ = {len(pkg.__all__)}개")
    except Exception as e:
        result.fail("21-3: __init__.py __all__", str(e))

    # 21-4: __init__.py에서 secret_manager 항목 접근 가능
    try:
        assert hasattr(pkg, "SecretProvider")
        assert hasattr(pkg, "SecretManager")
        assert hasattr(pkg, "get_secret")
        assert hasattr(pkg, "SecretEncryption")
        result.ok("21-4: __init__.py 주요 항목 접근 가능")
    except Exception as e:
        result.fail("21-4: __init__.py 항목 접근", str(e))


# =============================================================================
# [22] 엣지 케이스
# =============================================================================
def test_edge_cases(result: TestResult) -> None:
    """엣지 케이스 검증."""
    print("\n[22] 엣지 케이스")

    # 22-1: 빈 문자열 마스킹
    try:
        masked = _mask_secret_name("")
        assert masked == ""
        result.ok("22-1: 빈 문자열 마스킹")
    except Exception as e:
        result.fail("22-1: 빈 문자열", str(e))

    # 22-2: 멀티스레드 캐시 접근
    try:
        env_key = f"{DEFAULT_ENV_PREFIX}MT_TEST".upper()
        os.environ[env_key] = "mt_val"
        try:
            mgr = _make_manager()
            errors = []

            def worker():
                try:
                    for _ in range(50):
                        v = mgr.get("mt_test")
                        if v != "mt_val":
                            errors.append(f"잘못된 값: {v}")
                except Exception as ex:
                    errors.append(str(ex))

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert len(errors) == 0, f"오류: {errors[:3]}"
            result.ok("22-2: 멀티스레드 캐시 접근 안전")
        finally:
            del os.environ[env_key]
    except Exception as e:
        result.fail("22-2: 멀티스레드", str(e))

    # 22-3: 캐시 크기 제한 (LRU 축출)
    try:
        config = {
            "cache": {"enabled": True, "ttl": 300, "max_entries": 3},
            "provider": {"env": {"enabled": True}},
        }
        mock_loader = MagicMock()
        mock_loader.get.return_value = config
        mgr = SecretManager(config_loader=mock_loader)

        for i in range(5):
            env_key = f"{DEFAULT_ENV_PREFIX}LRU_{i}".upper()
            os.environ[env_key] = f"val_{i}"

        try:
            for i in range(5):
                mgr.get(f"lru_{i}")
            # max_entries=3이므로 캐시 크기 최대 3
            assert len(mgr._cache) <= 3
            result.ok("22-3: 캐시 크기 제한 (LRU)")
        finally:
            for i in range(5):
                env_key = f"{DEFAULT_ENV_PREFIX}LRU_{i}".upper()
                if env_key in os.environ:
                    del os.environ[env_key]
    except Exception as e:
        result.fail("22-3: LRU 축출", str(e))

    # 22-4: _generate_cache_key 일관성
    try:
        k1 = _generate_cache_key("same", SecretProvider.ENV)
        k2 = _generate_cache_key("same", SecretProvider.ENV)
        assert k1 == k2
        result.ok("22-4: _generate_cache_key 일관성")
    except Exception as e:
        result.fail("22-4: cache_key 일관성", str(e))

    # 22-5: 예외 세부 정보 (secret_name, provider)
    try:
        ex = SecretException(
            message="테스트",
            secret_name="my_secret_key",
            provider=SecretProvider.AWS,
        )
        assert "secret_name" in ex.details
        assert "provider" in ex.details
        assert ex.details["provider"] == "AWS"
        result.ok("22-5: 예외 세부 정보 포함")
    except Exception as e:
        result.fail("22-5: 예외 세부 정보", str(e))

    # 22-6: SecretInfo.to_dict version=None
    try:
        info = SecretInfo(name="test_no_ver", provider=SecretProvider.ENV)
        d = info.to_dict()
        assert d["version"] is None
        result.ok("22-6: to_dict version=None 처리")
    except Exception as e:
        result.fail("22-6: version=None", str(e))


# =============================================================================
# main
# =============================================================================
def main() -> None:
    """테스트 실행."""
    result = TestResult()

    test_constants(result)
    test_secret_provider(result)
    test_secret_status(result)
    test_cache_status(result)
    test_exceptions(result)
    test_secret_version(result)
    test_secret_info(result)
    test_cached_secret(result)
    test_validation_rule(result)
    test_utility_functions(result)
    test_base_provider(result)
    test_env_provider(result)
    test_file_provider(result)
    test_secret_manager_init(result)
    test_secret_manager_get(result)
    test_secret_manager_api(result)
    test_module_functions(result)
    test_secret_rotator(result)
    test_vault_token_manager(result)
    test_rotation_schedule(result)
    test_all_exports(result)
    test_edge_cases(result)

    result.summary()

    # 전역 상태 리셋
    _reset_global()

    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
