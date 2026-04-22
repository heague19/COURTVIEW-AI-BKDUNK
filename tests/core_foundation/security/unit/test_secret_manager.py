# -*- coding: utf-8 -*-
"""security/secret_manager.py 단위 테스트."""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import json
import os
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from core_foundation.security.secret_manager import (
    MASK_CHAR,
    MASK_VISIBLE_CHARS,
    MAX_SECRETS,
    NO_EXPIRY,
    SecretEntry,
    SecretManager,
    SecretSource,
    mask_secret,
)


@pytest.fixture(autouse=True)
def reset_manager():
    SecretManager.reset()
    yield
    SecretManager.reset()


# =============================================================================
# SecretSource 검증
# =============================================================================

class TestSecretSource:
    def test_member_count(self):
        assert len(SecretSource) == 3

    def test_values(self):
        assert SecretSource.ENV.value == "env"
        assert SecretSource.FILE.value == "file"
        assert SecretSource.RUNTIME.value == "runtime"

    def test_to_korean(self):
        assert SecretSource.ENV.to_korean() == "환경변수"
        assert SecretSource.FILE.to_korean() == "파일"
        assert SecretSource.RUNTIME.to_korean() == "런타임"


# =============================================================================
# SecretEntry 검증
# =============================================================================

class TestSecretEntry:
    def test_slots(self):
        assert hasattr(SecretEntry, "__slots__")

    def test_creation(self):
        e = SecretEntry(key="api_key", value="abc123", source=SecretSource.ENV)
        assert e.key == "api_key"
        assert e.value == "abc123"

    def test_is_expired_no_expiry(self):
        e = SecretEntry(key="k", value="v", source=SecretSource.RUNTIME, expires_at=0.0)
        assert e.is_expired is False

    def test_masked_value(self):
        e = SecretEntry(key="k", value="abcdefghij", source=SecretSource.RUNTIME)
        masked = e.masked_value
        assert masked.startswith("abc")
        assert masked.endswith("hij")
        assert MASK_CHAR in masked

    def test_repr(self):
        e = SecretEntry(key="api_key", value="secret123", source=SecretSource.ENV)
        text = repr(e)
        assert "api_key" in text
        assert "env" in text
        # 원본 값은 노출되지 않아야 함
        assert "secret123" not in text


# =============================================================================
# mask_secret 함수
# =============================================================================

class TestMaskSecret:
    def test_short_value_fully_masked(self):
        assert mask_secret("abc") == "***"
        assert mask_secret("abcdef") == "******"

    def test_long_value_partially_masked(self):
        result = mask_secret("abcdefghij")
        assert result.startswith("abc")
        assert result.endswith("hij")
        assert len(result) == 10
        assert MASK_CHAR * 4 in result

    def test_empty_value(self):
        assert mask_secret("") == ""

    def test_exact_boundary(self):
        # MASK_VISIBLE_CHARS * 2 = 6
        assert mask_secret("123456") == "******"
        result = mask_secret("1234567")
        assert result == "123*567"


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:
    def test_get_instance(self):
        m1 = SecretManager.get_instance()
        m2 = SecretManager.get_instance()
        assert m1 is m2

    def test_reset(self):
        m1 = SecretManager.get_instance()
        SecretManager.reset()
        m2 = SecretManager.get_instance()
        assert m1 is not m2


# =============================================================================
# 런타임 등록
# =============================================================================

class TestSetAndGet:
    def test_set_and_get(self):
        mgr = SecretManager.get_instance()
        mgr.set("api_key", "my-secret-value")
        assert mgr.get("api_key") == "my-secret-value"

    def test_set_with_description(self):
        mgr = SecretManager.get_instance()
        mgr.set("key", "val", description="테스트 키")
        entry = mgr.get_entry("key")
        assert entry is not None
        assert entry.description == "테스트 키"

    def test_set_overwrite(self):
        mgr = SecretManager.get_instance()
        mgr.set("key", "v1")
        mgr.set("key", "v2")
        assert mgr.get("key") == "v2"
        assert mgr.secret_count == 1

    def test_get_missing_raises(self):
        mgr = SecretManager.get_instance()
        with pytest.raises(KeyError, match="미등록 시크릿"):
            mgr.get("nonexistent")

    def test_get_optional_missing(self):
        mgr = SecretManager.get_instance()
        assert mgr.get_optional("missing") == ""
        assert mgr.get_optional("missing", "default") == "default"

    def test_get_optional_exists(self):
        mgr = SecretManager.get_instance()
        mgr.set("key", "value")
        assert mgr.get_optional("key") == "value"

    def test_has(self):
        mgr = SecretManager.get_instance()
        mgr.set("key", "val")
        assert mgr.has("key") is True
        assert mgr.has("missing") is False

    def test_get_masked(self):
        mgr = SecretManager.get_instance()
        mgr.set("key", "abcdefghij")
        masked = mgr.get_masked("key")
        assert masked.startswith("abc")
        assert "abcdefghij" not in masked

    def test_max_secrets_limit(self):
        mgr = SecretManager.get_instance()
        for i in range(MAX_SECRETS):
            mgr.set(f"key_{i}", f"val_{i}")

        result = mgr.set("overflow", "val")
        assert result is False


# =============================================================================
# 환경변수 로드
# =============================================================================

class TestLoadFromEnv:
    def test_load_existing_env(self):
        mgr = SecretManager.get_instance()
        with patch.dict(os.environ, {"TEST_API_KEY": "env-secret"}):
            result = mgr.load_from_env("TEST_API_KEY")
            assert result is True
            assert mgr.get("TEST_API_KEY") == "env-secret"

    def test_load_with_alias(self):
        mgr = SecretManager.get_instance()
        with patch.dict(os.environ, {"LONG_VAR_NAME": "val"}):
            mgr.load_from_env("LONG_VAR_NAME", key_alias="short")
            assert mgr.get("short") == "val"

    def test_load_missing_env(self):
        mgr = SecretManager.get_instance()
        result = mgr.load_from_env("NONEXISTENT_VAR_12345")
        assert result is False

    def test_load_missing_required(self):
        mgr = SecretManager.get_instance()
        with pytest.raises(KeyError, match="필수 환경변수"):
            mgr.load_from_env("NONEXISTENT_VAR_12345", required=True)

    def test_load_env_source(self):
        mgr = SecretManager.get_instance()
        with patch.dict(os.environ, {"MY_VAR": "val"}):
            mgr.load_from_env("MY_VAR")
            entry = mgr.get_entry("MY_VAR")
            assert entry is not None
            assert entry.source == SecretSource.ENV


# =============================================================================
# 파일 로드 (dotenv)
# =============================================================================

class TestLoadFromDotenv:
    def test_load_dotenv(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "API_KEY=my-api-key\n"
            "DB_PASS=db-secret\n"
            "# 주석\n"
            "\n"
            "EMPTY_LINE_ABOVE=yes\n",
            encoding="utf-8",
        )

        mgr = SecretManager.get_instance()
        count = mgr.load_from_dotenv(env_file)
        assert count == 3
        assert mgr.get("API_KEY") == "my-api-key"
        assert mgr.get("DB_PASS") == "db-secret"

    def test_load_dotenv_quoted_values(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            'SINGLE=\'hello\'\n'
            'DOUBLE="world"\n',
            encoding="utf-8",
        )

        mgr = SecretManager.get_instance()
        mgr.load_from_dotenv(env_file)
        assert mgr.get("SINGLE") == "hello"
        assert mgr.get("DOUBLE") == "world"

    def test_load_dotenv_missing_file(self):
        mgr = SecretManager.get_instance()
        with pytest.raises(FileNotFoundError):
            mgr.load_from_dotenv(Path("/nonexistent/.env"))

    def test_load_dotenv_source(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n", encoding="utf-8")

        mgr = SecretManager.get_instance()
        mgr.load_from_dotenv(env_file)
        entry = mgr.get_entry("KEY")
        assert entry is not None
        assert entry.source == SecretSource.FILE


# =============================================================================
# 파일 로드 (JSON)
# =============================================================================

class TestLoadFromJson:
    def test_load_json(self, tmp_path: Path):
        json_file = tmp_path / "secrets.json"
        json_file.write_text(
            json.dumps({"api_key": "key123", "db_pass": "pass456"}),
            encoding="utf-8",
        )

        mgr = SecretManager.get_instance()
        count = mgr.load_from_json(json_file)
        assert count == 2
        assert mgr.get("api_key") == "key123"

    def test_load_json_skips_non_string(self, tmp_path: Path):
        json_file = tmp_path / "secrets.json"
        json_file.write_text(
            json.dumps({"key": "value", "number": 123, "list": [1, 2]}),
            encoding="utf-8",
        )

        mgr = SecretManager.get_instance()
        count = mgr.load_from_json(json_file)
        assert count == 1  # 문자열 값만

    def test_load_json_missing_file(self):
        mgr = SecretManager.get_instance()
        with pytest.raises(FileNotFoundError):
            mgr.load_from_json(Path("/nonexistent/secrets.json"))

    def test_load_json_invalid(self, tmp_path: Path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("not valid json", encoding="utf-8")

        mgr = SecretManager.get_instance()
        with pytest.raises(ValueError, match="JSON 파싱 실패"):
            mgr.load_from_json(json_file)

    def test_load_json_non_dict(self, tmp_path: Path):
        json_file = tmp_path / "list.json"
        json_file.write_text("[1, 2, 3]", encoding="utf-8")

        mgr = SecretManager.get_instance()
        with pytest.raises(ValueError, match="딕셔너리"):
            mgr.load_from_json(json_file)


# =============================================================================
# 만료
# =============================================================================

class TestExpiry:
    def test_ttl_expiry(self):
        mgr = SecretManager.get_instance()
        mgr.set("temp", "val", ttl_sec=0.01)

        import time
        time.sleep(0.05)  # Windows timer resolution ~15ms

        with pytest.raises(KeyError, match="만료된 시크릿"):
            mgr.get("temp")

    def test_has_expired(self):
        mgr = SecretManager.get_instance()
        mgr.set("temp", "val", ttl_sec=0.01)

        import time
        time.sleep(0.05)

        assert mgr.has("temp") is False

    def test_cleanup_expired(self):
        mgr = SecretManager.get_instance()
        mgr.set("alive", "val1")
        mgr.set("expired", "val2", ttl_sec=0.01)

        import time
        time.sleep(0.05)

        count = mgr.cleanup_expired()
        assert count == 1
        assert mgr.secret_count == 1

    def test_no_expiry(self):
        mgr = SecretManager.get_instance()
        mgr.set("permanent", "val")
        entry = mgr.get_entry("permanent")
        assert entry is not None
        assert entry.expires_at == NO_EXPIRY
        assert entry.is_expired is False


# =============================================================================
# 제거 / 관리
# =============================================================================

class TestManagement:
    def test_remove(self):
        mgr = SecretManager.get_instance()
        mgr.set("key", "val")
        assert mgr.remove("key") is True
        assert mgr.has("key") is False

    def test_remove_nonexistent(self):
        mgr = SecretManager.get_instance()
        assert mgr.remove("missing") is False

    def test_clear(self):
        mgr = SecretManager.get_instance()
        mgr.set("a", "1")
        mgr.set("b", "2")
        count = mgr.clear()
        assert count == 2
        assert mgr.secret_count == 0

    def test_secret_keys(self):
        mgr = SecretManager.get_instance()
        mgr.set("x", "1")
        mgr.set("y", "2")
        keys = mgr.secret_keys
        assert "x" in keys and "y" in keys

    def test_all_masked(self):
        mgr = SecretManager.get_instance()
        mgr.set("key", "abcdefghij")
        masked = mgr.all_masked()
        assert "key" in masked
        # 원본 노출 금지
        assert "abcdefghij" not in masked["key"]

    def test_get_entry_defensive_copy(self):
        mgr = SecretManager.get_instance()
        mgr.set("key", "original")
        entry = mgr.get_entry("key")
        assert entry is not None
        entry.value = "modified"
        assert mgr.get("key") == "original"

    def test_get_entry_missing(self):
        mgr = SecretManager.get_instance()
        assert mgr.get_entry("missing") is None


# =============================================================================
# 스레드 안전
# =============================================================================

class TestThreadSafety:
    def test_concurrent_set_and_get(self):
        mgr = SecretManager.get_instance()
        errors: list[Exception] = []

        def set_and_get(prefix: str):
            try:
                for i in range(20):
                    key = f"{prefix}_{i}"
                    mgr.set(key, f"val_{key}")
                    mgr.get(key)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=set_and_get, args=(f"t{t}",))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0


# =============================================================================
# repr
# =============================================================================

class TestRepr:
    def test_repr(self):
        mgr = SecretManager.get_instance()
        text = repr(mgr)
        assert "secrets=" in text


# =============================================================================
# 상수 검증
# =============================================================================

class TestConstants:
    def test_max_secrets(self):
        assert MAX_SECRETS == 200

    def test_mask_char(self):
        assert MASK_CHAR == "*"

    def test_mask_visible_chars(self):
        assert MASK_VISIBLE_CHARS == 3

    def test_no_expiry(self):
        assert NO_EXPIRY == 0.0


# =============================================================================
# Export 검증
# =============================================================================

class TestModuleExport:
    def test_all_exists(self):
        import core_foundation.security.secret_manager as mod
        assert hasattr(mod, "__all__")

    def test_all_items_exist(self):
        import core_foundation.security.secret_manager as mod
        for name in mod.__all__:
            assert hasattr(mod, name)

    def test_version(self):
        import core_foundation.security.secret_manager as mod
        assert mod.__version__ == "1.0.0"
