# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/security/performance
파일: test_secret_manager_perf.py
설명: 시크릿 매니저 성능 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-16

테스트 범위:
    [1] Enum 연산 성능 (3개)
    [2] 데이터클래스 생성 성능 (3개)
    [3] 유틸리티 함수 성능 (3개)
    [4] 예외 클래스 생성 성능 (3개)
    [5] EnvProvider 성능 (3개)
    [6] FileProvider 성능 (3개)
    [7] SecretManager 초기화 성능 (3개)
    [8] SecretManager.get 캐시 성능 (4개)
    [9] SecretManager API 성능 (3개)
    [10] 멀티스레드 동시 접근 (4개)
    [11] 메모리 사용량 (3개)
    [12] to_dict / 직렬화 성능 (3개)
"""

import io
import json
import os
import sys
import tempfile
import time
import threading
import tracemalloc
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.security.secret_manager import (
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
    # 데이터클래스
    SecretVersion,
    SecretInfo,
    CachedSecret,
    SecretValidationRule,
    RotationSchedule,
    # 유틸리티
    _mask_secret_name,
    _mask_secret_value,
    _generate_cache_key,
    # 제공자
    EnvProvider,
    FileProvider,
    # 메인 클래스
    SecretManager,
    # 상수
    DEFAULT_CACHE_TTL,
    DEFAULT_ENV_PREFIX,
    DEFAULT_MASK_CHAR,
    MASK_VISIBLE_LENGTH,
)


# =============================================================================
# 성능 테스트 결과 클래스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 저장."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.metrics = []

    def ok(self, test_name: str, metric: str = "") -> None:
        self.passed += 1
        msg = f"  [PASS] {test_name}"
        if metric:
            msg += f" | {metric}"
            self.metrics.append(f"{test_name}: {metric}")
        print(msg)

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.metrics:
            print(f"\n성능 메트릭:")
            for m in self.metrics:
                print(f"  - {m}")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼
# =============================================================================
def _make_manager(**kwargs) -> SecretManager:
    """테스트용 SecretManager 생성 (EnvProvider 기반)."""
    mock_loader = MagicMock()
    mock_loader.get.return_value = kwargs.get("config", {})
    return SecretManager(
        config_loader=mock_loader,
        metrics_collector=kwargs.get("metrics_collector"),
        error_tracker=kwargs.get("error_tracker"),
    )


# =============================================================================
# [1] Enum 연산 성능
# =============================================================================
def test_enum_perf(result: PerfResult) -> None:
    """Enum 연산 성능."""
    print("\n[1] Enum 연산 성능")

    # 1-1: SecretProvider 멤버 접근
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = SecretProvider.AWS
            _ = SecretProvider.VAULT
            _ = SecretProvider.ENV
            _ = SecretProvider.FILE
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 4) * 1000  # μs
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-1: SecretProvider 멤버 접근 (400K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-1: SecretProvider", str(e))

    # 1-2: SecretStatus/CacheStatus 멤버 접근
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = SecretStatus.ACTIVE
            _ = SecretStatus.ROTATED
            _ = SecretStatus.EXPIRED
            _ = CacheStatus.HIT
            _ = CacheStatus.MISS
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 5) * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-2: SecretStatus/CacheStatus 접근 (500K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-2: SecretStatus/CacheStatus", str(e))

    # 1-3: Enum .name / .value 속성
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = SecretProvider.AWS.name
            _ = SecretProvider.AWS.value
            _ = SecretStatus.ACTIVE.name
            _ = CacheStatus.HIT.name
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 4) * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("1-3: Enum .name/.value (400K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("1-3: Enum 속성", str(e))


# =============================================================================
# [2] 데이터클래스 생성 성능
# =============================================================================
def test_dataclass_creation_perf(result: PerfResult) -> None:
    """데이터클래스 생성 성능."""
    print("\n[2] 데이터클래스 생성 성능")

    # 2-1: SecretVersion 생성
    try:
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = SecretVersion(
                version_id=f"v{i}",
                version_stage="AWSCURRENT",
                is_current=True,
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 2000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-1: SecretVersion 생성 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-1: SecretVersion", str(e))

    # 2-2: SecretInfo 생성
    try:
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = SecretInfo(
                name=f"secret_{i}",
                provider=SecretProvider.ENV,
                status=SecretStatus.ACTIVE,
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 2000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-2: SecretInfo 생성 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-2: SecretInfo", str(e))

    # 2-3: CachedSecret 생성
    try:
        iterations = 10_000
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=300)
        start = time.perf_counter()
        for i in range(iterations):
            _ = CachedSecret(
                name=f"secret_{i}",
                value=f"value_{i}",
                provider=SecretProvider.ENV,
                cached_at=now,
                expires_at=expires,
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 2000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("2-3: CachedSecret 생성 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("2-3: CachedSecret", str(e))


# =============================================================================
# [3] 유틸리티 함수 성능
# =============================================================================
def test_utility_perf(result: PerfResult) -> None:
    """유틸리티 함수 성능."""
    print("\n[3] 유틸리티 함수 성능")

    # 3-1: _mask_secret_name
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = _mask_secret_name("database_password")
            _ = _mask_secret_name("jwt_secret_key")
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 2) * 1000
        assert elapsed < 1000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-1: _mask_secret_name (200K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-1: _mask_secret_name", str(e))

    # 3-2: _mask_secret_value
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = _mask_secret_value("super_secret_value_12345")
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-2: _mask_secret_value (100K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-2: _mask_secret_value", str(e))

    # 3-3: _generate_cache_key
    try:
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = _generate_cache_key("database_password", SecretProvider.ENV)
            _ = _generate_cache_key("api_key", SecretProvider.AWS)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 2) * 1000
        assert elapsed < 1000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("3-3: _generate_cache_key (200K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("3-3: _generate_cache_key", str(e))


# =============================================================================
# [4] 예외 클래스 생성 성능
# =============================================================================
def test_exception_perf(result: PerfResult) -> None:
    """예외 클래스 생성 성능."""
    print("\n[4] 예외 클래스 생성 성능")

    # 4-1: SecretException 생성
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = SecretException(
                message="테스트 오류",
                secret_name="db_password",
                provider=SecretProvider.ENV,
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-1: SecretException 생성 (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-1: SecretException", str(e))

    # 4-2: SecretNotFoundException 생성
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = SecretNotFoundException(
                message="찾을 수 없음",
                secret_name="missing_key",
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-2: SecretNotFoundException (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-2: SecretNotFoundException", str(e))

    # 4-3: SecretValidationException 생성
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = SecretValidationException(
                message="유효성 실패",
                validation_errors=["최소 길이 미달", "패턴 불일치"],
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("4-3: SecretValidationException (10K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("4-3: SecretValidationException", str(e))


# =============================================================================
# [5] EnvProvider 성능
# =============================================================================
def test_env_provider_perf(result: PerfResult) -> None:
    """EnvProvider 성능."""
    print("\n[5] EnvProvider 성능")

    # 환경변수 설정
    for i in range(100):
        os.environ[f"COURTVIEW_SECRET_PERF_KEY_{i}"] = f"value_{i}"

    provider = EnvProvider({"prefix": "COURTVIEW_SECRET_PERF_"})

    # 5-1: get_secret 성능
    try:
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            provider.get_secret(f"KEY_{i % 100}")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-1: EnvProvider.get_secret (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("5-1: get_secret", str(e))

    # 5-2: secret_exists 성능
    try:
        iterations = 50_000
        start = time.perf_counter()
        for i in range(iterations):
            provider.secret_exists(f"KEY_{i % 100}")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-2: EnvProvider.secret_exists (50K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("5-2: secret_exists", str(e))

    # 5-3: is_available 속성
    try:
        iterations = 200_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = provider.is_available
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 500, f"너무 느림: {elapsed:.1f}ms"
        result.ok("5-3: is_available (200K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("5-3: is_available", str(e))

    # 정리
    for i in range(100):
        os.environ.pop(f"COURTVIEW_SECRET_PERF_KEY_{i}", None)


# =============================================================================
# [6] FileProvider 성능
# =============================================================================
def test_file_provider_perf(result: PerfResult) -> None:
    """FileProvider 성능."""
    print("\n[6] FileProvider 성능")

    # 임시 JSON 파일 생성
    secrets_data = {f"file_key_{i}": f"file_value_{i}" for i in range(200)}
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(secrets_data, tmp)
    tmp.close()

    try:
        provider = FileProvider({"path": tmp.name})

        # 6-1: get_secret 성능 (첫 로드 포함)
        try:
            iterations = 10_000
            start = time.perf_counter()
            for i in range(iterations):
                provider.get_secret(f"file_key_{i % 200}")
            elapsed = (time.perf_counter() - start) * 1000
            ops_sec = iterations / (elapsed / 1000)
            assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
            result.ok("6-1: FileProvider.get_secret (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
        except Exception as e:
            result.fail("6-1: get_secret", str(e))

        # 6-2: secret_exists 성능
        try:
            iterations = 50_000
            start = time.perf_counter()
            for i in range(iterations):
                provider.secret_exists(f"file_key_{i % 200}")
            elapsed = (time.perf_counter() - start) * 1000
            ops_sec = iterations / (elapsed / 1000)
            assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
            result.ok("6-2: FileProvider.secret_exists (50K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
        except Exception as e:
            result.fail("6-2: secret_exists", str(e))

        # 6-3: provider_type / is_available 속성
        # is_available은 Path.exists() 호출 → 파일시스템 I/O 포함
        try:
            iterations = 10_000
            start = time.perf_counter()
            for _ in range(iterations):
                _ = provider.provider_type
                _ = provider.is_available
            elapsed = (time.perf_counter() - start) * 1000
            per_op = elapsed / (iterations * 2) * 1000
            assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
            result.ok("6-3: 속성 접근 (20K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
        except Exception as e:
            result.fail("6-3: 속성 접근", str(e))
    finally:
        os.unlink(tmp.name)


# =============================================================================
# [7] SecretManager 초기화 성능
# =============================================================================
def test_manager_init_perf(result: PerfResult) -> None:
    """SecretManager 초기화 성능."""
    print("\n[7] SecretManager 초기화 성능")

    # 7-1: 기본 설정 초기화
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        iterations = 500
        start = time.perf_counter()
        for _ in range(iterations):
            _ = SecretManager(config_loader=mock_loader)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("7-1: 기본 초기화 (500)", f"{elapsed:.1f}ms, {per_op:.1f}μs/op")
    except Exception as e:
        result.fail("7-1: 기본 초기화", str(e))

    # 7-2: 커스텀 설정 포함 초기화
    try:
        mock_loader = MagicMock()
        mock_loader.get.return_value = {
            "provider": {
                "default": "env",
                "env": {"enabled": True, "prefix": "COURTVIEW_SECRET_"},
            },
            "cache": {"enabled": True, "ttl": 600},
        }
        iterations = 200
        start = time.perf_counter()
        for _ in range(iterations):
            _ = SecretManager(config_loader=mock_loader)
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("7-2: 커스텀 설정 초기화 (200)", f"{elapsed:.1f}ms, {per_op:.1f}μs/op")
    except Exception as e:
        result.fail("7-2: 커스텀 설정", str(e))

    # 7-3: 속성 접근 속도
    try:
        mgr = _make_manager()
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = mgr.get_providers()
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("7-3: get_providers (50K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("7-3: get_providers", str(e))


# =============================================================================
# [8] SecretManager.get 캐시 성능
# =============================================================================
def test_manager_get_cache_perf(result: PerfResult) -> None:
    """SecretManager.get 캐시 성능."""
    print("\n[8] SecretManager.get 캐시 성능")

    # 환경변수 설정
    for i in range(50):
        os.environ[f"COURTVIEW_SECRET_CACHE_PERF_{i}"] = f"cached_value_{i}"

    mgr = _make_manager()

    # 사전 캐싱
    for i in range(50):
        mgr.get(f"CACHE_PERF_{i}")

    # 8-1: 캐시 히트 성능
    try:
        iterations = 10_000
        start = time.perf_counter()
        for i in range(iterations):
            mgr.get(f"CACHE_PERF_{i % 50}")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-1: 캐시 히트 (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("8-1: 캐시 히트", str(e))

    # 8-2: bypass_cache 성능
    try:
        iterations = 5_000
        start = time.perf_counter()
        for i in range(iterations):
            mgr.get(f"CACHE_PERF_{i % 50}", bypass_cache=True)
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 10000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-2: bypass_cache (5K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("8-2: bypass_cache", str(e))

    # 8-3: 기본값 폴백 성능
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            mgr.get("nonexistent_secret_xyz", default="fallback")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 10000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-3: default 폴백 (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("8-3: default 폴백", str(e))

    # 8-4: invalidate_cache 성능
    try:
        iterations = 5_000
        start = time.perf_counter()
        for _ in range(iterations):
            mgr.invalidate_cache("CACHE_PERF_0")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("8-4: invalidate_cache 단일 (5K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("8-4: invalidate_cache", str(e))

    # 정리
    for i in range(50):
        os.environ.pop(f"COURTVIEW_SECRET_CACHE_PERF_{i}", None)


# =============================================================================
# [9] SecretManager API 성능
# =============================================================================
def test_manager_api_perf(result: PerfResult) -> None:
    """SecretManager API 성능."""
    print("\n[9] SecretManager API 성능")

    os.environ["COURTVIEW_SECRET_API_TEST_KEY"] = "api_test_value"
    mgr = _make_manager()
    mgr.get("API_TEST_KEY")

    # 9-1: get_info 성능
    try:
        iterations = 50_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = mgr.get_info("API_TEST_KEY")
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("9-1: get_info (50K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("9-1: get_info", str(e))

    # 9-2: get_cache_stats 성능
    try:
        iterations = 10_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = mgr.get_cache_stats()
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("9-2: get_cache_stats (10K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("9-2: get_cache_stats", str(e))

    # 9-3: health_check 성능
    try:
        iterations = 5_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = mgr.health_check()
        elapsed = (time.perf_counter() - start) * 1000
        ops_sec = iterations / (elapsed / 1000)
        assert elapsed < 5000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("9-3: health_check (5K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("9-3: health_check", str(e))

    os.environ.pop("COURTVIEW_SECRET_API_TEST_KEY", None)


# =============================================================================
# [10] 멀티스레드 동시 접근
# =============================================================================
def test_multithread_perf(result: PerfResult) -> None:
    """멀티스레드 동시 접근 성능."""
    print("\n[10] 멀티스레드 동시 접근")

    # 환경변수 설정
    for i in range(20):
        os.environ[f"COURTVIEW_SECRET_MT_{i}"] = f"mt_value_{i}"

    mgr = _make_manager()
    # 사전 캐싱
    for i in range(20):
        mgr.get(f"MT_{i}")

    # 10-1: 4스레드 캐시 히트
    try:
        ops_per_thread = 5_000
        errors = []

        def cache_worker():
            try:
                for i in range(ops_per_thread):
                    mgr.get(f"MT_{i % 20}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=cache_worker) for _ in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 4
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0, f"에러: {errors}"
        result.ok("10-1: 4스레드 캐시 히트 (20K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("10-1: 4스레드 캐시", str(e))

    # 10-2: 8스레드 혼합 (get + get_info + exists)
    try:
        ops_per_thread = 2_000
        errors = []

        def mixed_worker():
            try:
                for i in range(ops_per_thread):
                    key = f"MT_{i % 20}"
                    if i % 3 == 0:
                        mgr.get_info(key)
                    elif i % 3 == 1:
                        mgr.exists(key)
                    else:
                        mgr.get(key)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=mixed_worker) for _ in range(8)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 8
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0, f"에러: {errors}"
        result.ok("10-2: 8스레드 혼합 (16K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("10-2: 8스레드 혼합", str(e))

    # 10-3: 4스레드 invalidate_cache 경합
    try:
        ops_per_thread = 2_000
        errors = []

        def invalidate_worker():
            try:
                for i in range(ops_per_thread):
                    if i % 2 == 0:
                        mgr.invalidate_cache(f"MT_{i % 20}")
                    else:
                        mgr.get(f"MT_{i % 20}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=invalidate_worker) for _ in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 4
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0, f"에러: {errors}"
        result.ok("10-3: 4스레드 invalidate+get (8K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("10-3: invalidate 경합", str(e))

    # 10-4: 4스레드 get_cache_stats 경합
    try:
        ops_per_thread = 5_000
        errors = []

        def stats_worker():
            try:
                for _ in range(ops_per_thread):
                    _ = mgr.get_cache_stats()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=stats_worker) for _ in range(4)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = (time.perf_counter() - start) * 1000
        total_ops = ops_per_thread * 4
        ops_sec = total_ops / (elapsed / 1000)
        assert len(errors) == 0, f"에러: {errors}"
        result.ok("10-4: 4스레드 cache_stats (20K)", f"{elapsed:.1f}ms, {ops_sec:.0f} ops/s")
    except Exception as e:
        result.fail("10-4: cache_stats 경합", str(e))

    # 정리
    for i in range(20):
        os.environ.pop(f"COURTVIEW_SECRET_MT_{i}", None)


# =============================================================================
# [11] 메모리 사용량
# =============================================================================
def test_memory_usage(result: PerfResult) -> None:
    """메모리 사용량 테스트."""
    print("\n[11] 메모리 사용량")

    # 11-1: SecretManager 인스턴스 메모리
    try:
        tracemalloc.start()
        mock_loader = MagicMock()
        mock_loader.get.return_value = {}
        managers = []
        for _ in range(50):
            managers.append(SecretManager(config_loader=mock_loader))
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_instance_kb = current / 50 / 1024
        assert per_instance_kb < 100, f"인스턴스당 메모리 과다: {per_instance_kb:.1f}KB"
        result.ok("11-1: 50개 인스턴스 메모리", f"총: {current/1024:.1f}KB, 인스턴스당: {per_instance_kb:.1f}KB")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("11-1: 인스턴스 메모리", str(e))

    # 11-2: CachedSecret 대량 캐시 메모리
    try:
        tracemalloc.start()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=300)
        cache = {}
        for i in range(1_000):
            cache[f"key_{i}"] = CachedSecret(
                name=f"secret_{i}",
                value=f"value_{i}" * 10,
                provider=SecretProvider.ENV,
                cached_at=now,
                expires_at=expires,
            )
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_item = current / 1_000
        assert current / 1024 < 2048, f"캐시 메모리 과다: {current/1024:.1f}KB"
        result.ok("11-2: 1K CachedSecret 메모리", f"총: {current/1024:.1f}KB, 개당: {per_item:.0f}B")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("11-2: 캐시 메모리", str(e))

    # 11-3: SecretInfo 메모리
    try:
        tracemalloc.start()
        infos = []
        for i in range(1_000):
            infos.append(SecretInfo(
                name=f"secret_{i}",
                provider=SecretProvider.ENV,
                status=SecretStatus.ACTIVE,
            ))
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        per_item = current / 1_000
        result.ok("11-3: 1K SecretInfo 메모리", f"총: {current/1024:.1f}KB, 개당: {per_item:.0f}B")
    except Exception as e:
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        result.fail("11-3: SecretInfo 메모리", str(e))


# =============================================================================
# [12] to_dict / 직렬화 성능
# =============================================================================
def test_serialization_perf(result: PerfResult) -> None:
    """직렬화 성능."""
    print("\n[12] to_dict / 직렬화 성능")

    # 12-1: SecretInfo.to_dict
    try:
        info = SecretInfo(
            name="database_password",
            provider=SecretProvider.ENV,
            status=SecretStatus.ACTIVE,
            version=SecretVersion(version_id="v1"),
            access_count=100,
            cached=True,
        )
        iterations = 20_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = info.to_dict()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-1: SecretInfo.to_dict (20K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("12-1: SecretInfo.to_dict", str(e))

    # 12-2: CachedSecret.is_expired + should_refresh
    try:
        now = datetime.now(timezone.utc)
        cached = CachedSecret(
            name="test",
            value="val",
            provider=SecretProvider.ENV,
            cached_at=now,
            expires_at=now + timedelta(seconds=300),
        )
        iterations = 100_000
        start = time.perf_counter()
        for _ in range(iterations):
            _ = cached.is_expired()
            _ = cached.should_refresh()
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / (iterations * 2) * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-2: is_expired+should_refresh (200K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("12-2: 캐시 검사", str(e))

    # 12-3: RotationSchedule 생성
    try:
        iterations = 50_000
        start = time.perf_counter()
        for i in range(iterations):
            _ = RotationSchedule(
                secret_name=f"key_{i % 100}",
                interval_days=30,
                enabled=True,
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_op = elapsed / iterations * 1000
        assert elapsed < 3000, f"너무 느림: {elapsed:.1f}ms"
        result.ok("12-3: RotationSchedule 생성 (50K)", f"{elapsed:.1f}ms, {per_op:.3f}μs/op")
    except Exception as e:
        result.fail("12-3: RotationSchedule", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """성능 테스트 실행."""
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=" * 60)
    print("SecretManager 성능 테스트")
    print("=" * 60)

    r = PerfResult()

    test_enum_perf(r)
    test_dataclass_creation_perf(r)
    test_utility_perf(r)
    test_exception_perf(r)
    test_env_provider_perf(r)
    test_file_provider_perf(r)
    test_manager_init_perf(r)
    test_manager_get_cache_perf(r)
    test_manager_api_perf(r)
    test_multithread_perf(r)
    test_memory_usage(r)
    test_serialization_perf(r)

    r.summary()


if __name__ == "__main__":
    main()
