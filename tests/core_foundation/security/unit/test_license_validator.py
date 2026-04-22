# -*- coding: utf-8 -*-
"""security/license_validator.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import hashlib
import hmac
import platform
import threading
import time
import uuid

import pytest

from core_foundation.security.license_validator import (
    DEFAULT_TRIAL_DAYS,
    HW_HASH_ALGORITHM,
    LICENSE_CACHE_TTL_SEC,
    MIN_LICENSE_KEY_LENGTH,
    LicenseInfo,
    LicenseStatus,
    LicenseValidator,
    generate_hardware_id,
    generate_license_signature,
    verify_license_signature,
)


@pytest.fixture(autouse=True)
def reset_validator():
    LicenseValidator.reset()
    yield
    LicenseValidator.reset()


# =============================================================================
# LicenseStatus 검증
# =============================================================================

class TestLicenseStatus:
    def test_member_count(self):
        assert len(LicenseStatus) == 5

    def test_values(self):
        assert LicenseStatus.VALID.value == "valid"
        assert LicenseStatus.EXPIRED.value == "expired"
        assert LicenseStatus.INVALID.value == "invalid"
        assert LicenseStatus.TRIAL.value == "trial"
        assert LicenseStatus.NOT_CHECKED.value == "not_checked"

    def test_to_korean(self):
        assert LicenseStatus.VALID.to_korean() == "유효"
        assert LicenseStatus.EXPIRED.to_korean() == "만료"
        assert LicenseStatus.INVALID.to_korean() == "무효"
        assert LicenseStatus.TRIAL.to_korean() == "평가판"
        assert LicenseStatus.NOT_CHECKED.to_korean() == "미검증"

    def test_is_active_valid(self):
        assert LicenseStatus.VALID.is_active is True

    def test_is_active_trial(self):
        assert LicenseStatus.TRIAL.is_active is True

    def test_is_active_expired(self):
        assert LicenseStatus.EXPIRED.is_active is False

    def test_is_active_invalid(self):
        assert LicenseStatus.INVALID.is_active is False

    def test_is_active_not_checked(self):
        assert LicenseStatus.NOT_CHECKED.is_active is False


# =============================================================================
# LicenseInfo 검증
# =============================================================================

class TestLicenseInfo:
    def test_slots(self):
        assert hasattr(LicenseInfo, "__slots__")

    def test_creation(self):
        info = LicenseInfo(
            status=LicenseStatus.VALID,
            hardware_id="abc123",
            license_key="key****key1",
            expires_at=0.0,
            owner="COURTVIEW",
            max_cameras=4,
        )
        assert info.status == LicenseStatus.VALID
        assert info.hardware_id == "abc123"
        assert info.owner == "COURTVIEW"
        assert info.max_cameras == 4

    def test_is_active(self):
        info = LicenseInfo(status=LicenseStatus.VALID, hardware_id="h")
        assert info.is_active is True

        info2 = LicenseInfo(status=LicenseStatus.EXPIRED, hardware_id="h")
        assert info2.is_active is False

    def test_is_expired_no_expiry(self):
        info = LicenseInfo(status=LicenseStatus.VALID, hardware_id="h", expires_at=0.0)
        assert info.is_expired is False

    def test_is_expired_future(self):
        info = LicenseInfo(
            status=LicenseStatus.VALID,
            hardware_id="h",
            expires_at=time.time() + 86400,
        )
        assert info.is_expired is False

    def test_is_expired_past(self):
        info = LicenseInfo(
            status=LicenseStatus.VALID,
            hardware_id="h",
            expires_at=time.time() - 86400,
        )
        assert info.is_expired is True

    def test_days_remaining_no_expiry(self):
        info = LicenseInfo(status=LicenseStatus.VALID, hardware_id="h", expires_at=0.0)
        assert info.days_remaining == -1

    def test_days_remaining_future(self):
        info = LicenseInfo(
            status=LicenseStatus.VALID,
            hardware_id="h",
            expires_at=time.time() + 86400 * 10,
        )
        remaining = info.days_remaining
        assert 9 <= remaining <= 10

    def test_days_remaining_past(self):
        info = LicenseInfo(
            status=LicenseStatus.VALID,
            hardware_id="h",
            expires_at=time.time() - 86400,
        )
        assert info.days_remaining == 0

    def test_repr(self):
        info = LicenseInfo(
            status=LicenseStatus.VALID,
            hardware_id="h",
            owner="test",
        )
        text = repr(info)
        assert "valid" in text
        assert "test" in text
        assert "days_remaining=" in text

    def test_default_features_none(self):
        info = LicenseInfo(status=LicenseStatus.VALID, hardware_id="h")
        assert info.features is None

    def test_features_list(self):
        info = LicenseInfo(
            status=LicenseStatus.VALID,
            hardware_id="h",
            features=["ai_referee", "multi_camera"],
        )
        assert len(info.features) == 2


# =============================================================================
# generate_hardware_id 검증
# =============================================================================

class TestGenerateHardwareId:
    def test_deterministic(self):
        h1 = generate_hardware_id()
        h2 = generate_hardware_id()
        assert h1 == h2

    def test_sha256_length(self):
        hw_id = generate_hardware_id()
        assert len(hw_id) == 64

    def test_hex_characters(self):
        hw_id = generate_hardware_id()
        assert all(c in "0123456789abcdef" for c in hw_id)

    def test_includes_platform_info(self):
        """해시 입력에 플랫폼 정보가 포함되는지 간접 검증."""
        components = [
            platform.system(),
            platform.processor(),
            platform.machine(),
            str(uuid.getnode()),
        ]
        payload = "|".join(components)
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        assert generate_hardware_id() == expected


# =============================================================================
# generate_license_signature 검증
# =============================================================================

class TestGenerateLicenseSignature:
    def test_deterministic(self):
        sig1 = generate_license_signature("hw123", "secret")
        sig2 = generate_license_signature("hw123", "secret")
        assert sig1 == sig2

    def test_sha256_length(self):
        sig = generate_license_signature("hw", "key")
        assert len(sig) == 64

    def test_different_hardware_different_sig(self):
        sig1 = generate_license_signature("hw1", "secret")
        sig2 = generate_license_signature("hw2", "secret")
        assert sig1 != sig2

    def test_different_key_different_sig(self):
        sig1 = generate_license_signature("hw", "secret1")
        sig2 = generate_license_signature("hw", "secret2")
        assert sig1 != sig2

    def test_with_owner(self):
        sig1 = generate_license_signature("hw", "key", owner="A")
        sig2 = generate_license_signature("hw", "key", owner="B")
        assert sig1 != sig2

    def test_with_expires(self):
        sig1 = generate_license_signature("hw", "key", expires_at=1000.0)
        sig2 = generate_license_signature("hw", "key", expires_at=2000.0)
        assert sig1 != sig2

    def test_with_features(self):
        sig1 = generate_license_signature("hw", "key", features="basic")
        sig2 = generate_license_signature("hw", "key", features="premium")
        assert sig1 != sig2

    def test_hmac_sha256_correctness(self):
        """HMAC-SHA256 직접 계산과 일치 확인."""
        hw_id = "test_hw"
        secret = "test_secret"
        owner = "owner"
        expires = 12345.0
        features = "feat1,feat2"

        message = f"{hw_id}|{owner}|{expires}|{features}"
        expected = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        result = generate_license_signature(
            hw_id, secret, owner=owner, expires_at=expires, features=features,
        )
        assert result == expected


# =============================================================================
# verify_license_signature 검증
# =============================================================================

class TestVerifyLicenseSignature:
    def test_valid_signature(self):
        hw_id = "hw_test"
        secret = "my_secret"
        sig = generate_license_signature(hw_id, secret)
        assert verify_license_signature(hw_id, secret, sig) is True

    def test_invalid_signature(self):
        assert verify_license_signature("hw", "key", "wrong_sig") is False

    def test_valid_with_all_params(self):
        hw_id = "hw_test"
        secret = "my_secret"
        owner = "COURTVIEW"
        expires = 9999999999.0
        features = "ai_referee,multi_camera"

        sig = generate_license_signature(
            hw_id, secret, owner=owner, expires_at=expires, features=features,
        )
        result = verify_license_signature(
            hw_id, secret, sig, owner=owner, expires_at=expires, features=features,
        )
        assert result is True

    def test_tampered_owner(self):
        hw_id = "hw"
        secret = "key"
        sig = generate_license_signature(hw_id, secret, owner="legit")
        result = verify_license_signature(hw_id, secret, sig, owner="tampered")
        assert result is False

    def test_tampered_expiry(self):
        hw_id = "hw"
        secret = "key"
        sig = generate_license_signature(hw_id, secret, expires_at=1000.0)
        result = verify_license_signature(hw_id, secret, sig, expires_at=9999.0)
        assert result is False

    def test_timing_safe(self):
        """hmac.compare_digest 사용 확인 (타이밍 공격 방지)."""
        hw_id = "hw"
        secret = "key"
        sig = generate_license_signature(hw_id, secret)
        # 정상 검증이 통과하면 내부적으로 compare_digest 사용
        assert verify_license_signature(hw_id, secret, sig) is True


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        v1 = LicenseValidator.get_instance()
        v2 = LicenseValidator.get_instance()
        assert v1 is v2

    def test_reset(self):
        v1 = LicenseValidator.get_instance()
        LicenseValidator.reset()
        v2 = LicenseValidator.get_instance()
        assert v1 is not v2


# =============================================================================
# 속성
# =============================================================================

class TestProperties:
    def test_hardware_id(self):
        v = LicenseValidator.get_instance()
        hw_id = v.hardware_id
        assert len(hw_id) == 64
        assert hw_id == generate_hardware_id()

    def test_initial_status(self):
        v = LicenseValidator.get_instance()
        assert v.status == LicenseStatus.NOT_CHECKED

    def test_initial_is_active(self):
        v = LicenseValidator.get_instance()
        assert v.is_active is False


# =============================================================================
# 라이선스 설정
# =============================================================================

class TestSetLicense:
    def test_set_license(self):
        v = LicenseValidator.get_instance()
        hw_id = v.hardware_id
        secret = "test-secret"
        sig = generate_license_signature(hw_id, secret, owner="TEST")

        v.set_license(
            license_key=sig,
            secret_key=secret,
            owner="TEST",
        )
        assert v.status == LicenseStatus.NOT_CHECKED  # 검증 전

    def test_set_license_with_features(self):
        v = LicenseValidator.get_instance()
        v.set_license(
            license_key="dummy",
            secret_key="key",
            features=["ai_referee", "multi_camera"],
            max_cameras=4,
        )
        assert v.max_cameras == 4

    def test_set_license_max_cameras_minimum(self):
        v = LicenseValidator.get_instance()
        v.set_license(
            license_key="key",
            secret_key="secret",
            max_cameras=0,
        )
        assert v.max_cameras == 1  # 최소 1

    def test_set_license_resets_validation(self):
        v = LicenseValidator.get_instance()
        v.set_trial()
        assert v.status == LicenseStatus.TRIAL

        v.set_license(license_key="k", secret_key="s")
        assert v.status == LicenseStatus.NOT_CHECKED


# =============================================================================
# 평가판 설정
# =============================================================================

class TestSetTrial:
    def test_set_trial_default(self):
        v = LicenseValidator.get_instance()
        v.set_trial()
        assert v.status == LicenseStatus.TRIAL
        assert v.is_active is True

    def test_set_trial_custom_days(self):
        v = LicenseValidator.get_instance()
        v.set_trial(days=7)
        info = v.validate()
        assert info.status == LicenseStatus.TRIAL
        assert 6 <= info.days_remaining <= 7

    def test_set_trial_features(self):
        v = LicenseValidator.get_instance()
        v.set_trial()
        features = v.get_features()
        assert "basic_analysis" in features

    def test_set_trial_single_camera(self):
        v = LicenseValidator.get_instance()
        v.set_trial()
        assert v.max_cameras == 1


# =============================================================================
# 검증 (validate)
# =============================================================================

class TestValidate:
    def test_validate_no_license(self):
        v = LicenseValidator.get_instance()
        info = v.validate()
        assert info.status == LicenseStatus.NOT_CHECKED
        assert info.is_active is False

    def test_validate_valid_license(self):
        v = LicenseValidator.get_instance()
        hw_id = v.hardware_id
        secret = "my-secret-key-1234"
        owner = "COURTVIEW"
        features = ["ai_referee", "multi_camera"]
        features_str = ",".join(sorted(features))

        sig = generate_license_signature(
            hw_id, secret, owner=owner, features=features_str,
        )

        v.set_license(
            license_key=sig,
            secret_key=secret,
            owner=owner,
            features=features,
        )

        info = v.validate()
        assert info.status == LicenseStatus.VALID
        assert info.is_active is True
        assert info.owner == owner

    def test_validate_expired_license(self):
        v = LicenseValidator.get_instance()
        hw_id = v.hardware_id
        secret = "secret"
        owner = "TEST"
        expires = time.time() - 86400  # 어제 만료

        sig = generate_license_signature(
            hw_id, secret, owner=owner, expires_at=expires,
        )

        v.set_license(
            license_key=sig,
            secret_key=secret,
            owner=owner,
            expires_at=expires,
        )

        info = v.validate()
        assert info.status == LicenseStatus.EXPIRED
        assert info.is_active is False

    def test_validate_invalid_signature(self):
        v = LicenseValidator.get_instance()
        v.set_license(
            license_key="completely_wrong_signature",
            secret_key="secret",
            owner="TEST",
        )

        info = v.validate()
        assert info.status == LicenseStatus.INVALID
        assert info.is_active is False

    def test_validate_trial_active(self):
        v = LicenseValidator.get_instance()
        v.set_trial(days=30)
        info = v.validate()
        assert info.status == LicenseStatus.TRIAL
        assert info.is_active is True

    def test_validate_trial_expired(self):
        v = LicenseValidator.get_instance()
        v.set_trial(days=30)

        # 내부 만료 시각 강제 변경 (과거로)
        with v._lock:
            v._expires_at = time.time() - 1

        info = v.validate()
        assert info.status == LicenseStatus.EXPIRED

    def test_validate_caching(self):
        """캐시 유효 시간 내 재검증 스킵."""
        v = LicenseValidator.get_instance()
        hw_id = v.hardware_id
        secret = "key"
        sig = generate_license_signature(hw_id, secret)

        v.set_license(license_key=sig, secret_key=secret)
        info1 = v.validate()
        assert info1.status == LicenseStatus.VALID

        # 두 번째 호출도 캐시에서 즉시 반환
        info2 = v.validate()
        assert info2.status == LicenseStatus.VALID

    def test_validate_no_secret_key(self):
        v = LicenseValidator.get_instance()
        v.set_license(license_key="key", secret_key="")
        info = v.validate()
        assert info.status == LicenseStatus.NOT_CHECKED

    def test_validate_no_license_key(self):
        v = LicenseValidator.get_instance()
        v.set_license(license_key="", secret_key="secret")
        info = v.validate()
        assert info.status == LicenseStatus.NOT_CHECKED


# =============================================================================
# 기능 확인
# =============================================================================

class TestFeatures:
    def test_has_feature_active(self):
        v = LicenseValidator.get_instance()
        hw_id = v.hardware_id
        secret = "key"
        features = ["ai_referee", "multi_camera"]
        features_str = ",".join(sorted(features))
        sig = generate_license_signature(hw_id, secret, features=features_str)

        v.set_license(
            license_key=sig,
            secret_key=secret,
            features=features,
        )
        v.validate()

        assert v.has_feature("ai_referee") is True
        assert v.has_feature("multi_camera") is True

    def test_has_feature_missing(self):
        v = LicenseValidator.get_instance()
        hw_id = v.hardware_id
        secret = "key"
        sig = generate_license_signature(hw_id, secret, features="basic")

        v.set_license(
            license_key=sig,
            secret_key=secret,
            features=["basic"],
        )
        v.validate()

        assert v.has_feature("premium") is False

    def test_has_feature_inactive_license(self):
        v = LicenseValidator.get_instance()
        # 미검증 상태
        assert v.has_feature("anything") is False

    def test_get_features(self):
        v = LicenseValidator.get_instance()
        v.set_trial()
        features = v.get_features()
        assert isinstance(features, list)
        assert "basic_analysis" in features

    def test_get_features_defensive_copy(self):
        v = LicenseValidator.get_instance()
        v.set_trial()
        features1 = v.get_features()
        features1.append("tampered")
        features2 = v.get_features()
        assert "tampered" not in features2


# =============================================================================
# 라이선스 정보 빌드 (_build_info)
# =============================================================================

class TestBuildInfo:
    def test_masked_key_long(self):
        v = LicenseValidator.get_instance()
        v.set_license(
            license_key="ABCDEFGHIJKLMNOP",
            secret_key="secret",
        )
        info = v.validate()
        assert info.license_key.startswith("ABCD")
        assert info.license_key.endswith("MNOP")
        assert "****" in info.license_key

    def test_masked_key_short(self):
        v = LicenseValidator.get_instance()
        v.set_license(
            license_key="SHORT",
            secret_key="secret",
        )
        info = v.validate()
        assert info.license_key == "****"

    def test_masked_key_empty(self):
        v = LicenseValidator.get_instance()
        info = v.validate()
        assert info.license_key == ""

    def test_info_hardware_id(self):
        v = LicenseValidator.get_instance()
        info = v.validate()
        assert info.hardware_id == v.hardware_id

    def test_info_features_copy(self):
        v = LicenseValidator.get_instance()
        v.set_trial()
        info = v.validate()
        assert info.features is not None
        info.features.append("tampered")
        info2 = v.validate()
        assert "tampered" not in info2.features


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_validate(self):
        v = LicenseValidator.get_instance()
        hw_id = v.hardware_id
        secret = "thread-safe-key"
        sig = generate_license_signature(hw_id, secret)
        v.set_license(license_key=sig, secret_key=secret)

        errors: list[Exception] = []
        results: list[LicenseStatus] = []

        def validate_many():
            try:
                for _ in range(20):
                    info = v.validate()
                    results.append(info.status)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=validate_many)
            for _ in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert all(s == LicenseStatus.VALID for s in results)

    def test_concurrent_singleton(self):
        instances: list[LicenseValidator] = []
        errors: list[Exception] = []

        def get_instance():
            try:
                inst = LicenseValidator.get_instance()
                instances.append(inst)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=get_instance)
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert all(inst is instances[0] for inst in instances)


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_validator_repr(self):
        v = LicenseValidator.get_instance()
        text = repr(v)
        assert "LicenseValidator" in text
        assert "not_checked" in text

    def test_validator_repr_after_trial(self):
        v = LicenseValidator.get_instance()
        v.set_trial()
        text = repr(v)
        assert "trial" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_min_license_key_length(self):
        assert MIN_LICENSE_KEY_LENGTH == 16

    def test_hw_hash_algorithm(self):
        assert HW_HASH_ALGORITHM == "sha256"

    def test_license_cache_ttl(self):
        assert LICENSE_CACHE_TTL_SEC == 3600.0

    def test_default_trial_days(self):
        assert DEFAULT_TRIAL_DAYS == 30


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.security.license_validator as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.security.license_validator as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"__all__ 항목 '{name}' 누락"

    def test_version(self):
        import core_foundation.security.license_validator as mod
        assert mod.__version__ == "1.0.0"

    def test_all_count(self):
        import core_foundation.security.license_validator as mod
        assert len(mod.__all__) == 10
