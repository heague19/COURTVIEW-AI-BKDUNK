# -*- coding: utf-8 -*-
"""
shared/exceptions 단위 테스트.

김팀장 지시 §5-4:
- 주요 예외 인스턴스 생성, 상속 체계, to_dict, ErrorCode 매핑, 보안 마스킹
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Final

import pytest


_EXCEPTIONS_DIR = Path(__file__).resolve().parent.parent.parent / "shared" / "exceptions"

_SUBMODULE_NAMES: Final[list[str]] = [
    p.stem for p in sorted(_EXCEPTIONS_DIR.glob("*.py"))
    if p.stem != "__init__" and not p.stem.startswith("_")
]


class TestImport:
    def test_package_import(self) -> None:
        from shared.exceptions import __all__, __version__
        assert len(__all__) > 0
        assert __version__ == "1.0.0"

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_import(self, name: str) -> None:
        mod = importlib.import_module(f"shared.exceptions.{name}")
        assert mod is not None


class TestVersion:
    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_version(self, name: str) -> None:
        mod = importlib.import_module(f"shared.exceptions.{name}")
        version = getattr(mod, "__version__", None)
        if version is not None:
            assert version == "1.0.0", f"{name}.__version__ = {version}"


class TestAnnotations:
    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_future_annotations(self, name: str) -> None:
        filepath = _EXCEPTIONS_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
        has_future = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in ast.walk(tree)
        )
        assert has_future, f"{name}.py에 from __future__ import annotations 없음"


class TestInheritance:
    """예외 상속 체계 테스트."""

    def test_base_exception(self) -> None:
        from shared.exceptions import CourtViewException
        assert issubclass(CourtViewException, Exception)

    def test_retryable(self) -> None:
        from shared.exceptions import RetryableException, CourtViewException
        assert issubclass(RetryableException, CourtViewException)

    def test_non_retryable(self) -> None:
        from shared.exceptions import NonRetryableException, CourtViewException
        assert issubclass(NonRetryableException, CourtViewException)

    def test_critical(self) -> None:
        from shared.exceptions import CriticalException, CourtViewException
        assert issubclass(CriticalException, CourtViewException)


class TestToDict:
    """to_dict 직렬화 테스트."""

    def test_base_to_dict(self) -> None:
        from shared.exceptions import CourtViewException
        exc = CourtViewException(message="테스트 오류")
        d = exc.to_dict()
        assert "error" in d
        assert d["error"]["message"] == "테스트 오류"

    def test_retryable_to_dict(self) -> None:
        from shared.exceptions import RetryableException
        exc = RetryableException(message="재시도 가능", retry_after=5.0)
        d = exc.to_dict()
        assert d["retry"]["retry_after"] == 5.0


class TestSecurityMasking:
    """보안 마스킹 테스트."""

    def test_validation_password_masking(self) -> None:
        from shared.exceptions import ValidationException
        exc = ValidationException(
            field_name="password",
            field_value="secret123",
        )
        assert exc.details.get("field_value") == "***MASKED***"

    def test_validation_normal_field(self) -> None:
        from shared.exceptions import ValidationException
        exc = ValidationException(
            field_name="username",
            field_value="john",
        )
        assert exc.details.get("field_value") == "john"


class TestNoAlias:
    def test_no_alias_in_init(self) -> None:
        init_path = _EXCEPTIONS_DIR / "__init__.py"
        source = init_path.read_text(encoding="utf-8")
        lines = source.split("\n")
        alias_lines = [
            line.strip() for line in lines
            if " as " in line and not line.strip().startswith("#")
        ]
        assert len(alias_lines) == 0, f"별칭 발견: {alias_lines}"


# =============================================================================
# 기능 테스트: ErrorCode 매핑
# =============================================================================
class TestErrorCodeMapping:
    """예외와 ErrorCode 매핑 검증."""

    def test_video_format_exception_code(self) -> None:
        from shared.exceptions import VideoFormatException
        exc = VideoFormatException(format_received="wmv")
        assert exc.error_code.name == "VIDEO_FORMAT_UNSUPPORTED"

    def test_model_not_found_code(self) -> None:
        from shared.exceptions import ModelNotFoundException
        exc = ModelNotFoundException(model_name="yolov8")
        assert exc.error_code.name == "MODEL_NOT_FOUND"

    def test_gpu_memory_code(self) -> None:
        from shared.exceptions import GPUMemoryException
        exc = GPUMemoryException()
        assert exc.error_code.name == "GPU_MEMORY_ERROR"


# =============================================================================
# 기능 테스트: 예외 체이닝
# =============================================================================
class TestExceptionChaining:
    """예외 체이닝 테스트."""

    def test_cause_chaining(self) -> None:
        from shared.exceptions import CourtViewException
        cause = ValueError("원인 오류")
        exc = CourtViewException(message="래핑 오류", cause=cause)
        assert exc.__cause__ is cause
        d = exc.to_dict(include_traceback=True)
        assert "cause" in d
        assert d["cause"]["type"] == "ValueError"

    def test_with_context_chaining(self) -> None:
        from shared.exceptions import CourtViewException
        exc = CourtViewException(message="테스트")
        result = exc.with_context(request_id="abc", user_id="u1")
        assert result is exc  # 메서드 체이닝
        assert exc.context["request_id"] == "abc"


# =============================================================================
# 기능 테스트: 팩토리 메서드
# =============================================================================
class TestFactoryMethods:
    """팩토리 메서드 검증."""

    def test_gpu_memory_oom_factory(self) -> None:
        from shared.exceptions import GPUMemoryException
        exc = GPUMemoryException.oom_during_inference(
            gpu_id="cuda:0", batch_size=8,
        )
        assert "batch_size" in exc.details
        assert exc.details["batch_size"] == 8

    def test_authentication_token_expired(self) -> None:
        from shared.exceptions import AuthenticationException
        exc = AuthenticationException.token_expired(
            token_type="access_token",
            expired_at="2026-03-25T12:00:00Z",
        )
        assert exc.reason == "token_expired"

    def test_critical_severity(self) -> None:
        from shared.exceptions import CriticalException
        exc = CriticalException(severity=3)
        assert exc.severity == 3
        assert exc.alert_required is True
        d = exc.to_dict()
        assert d["critical"]["severity"] == 3

    def test_retryable_retry_info(self) -> None:
        from shared.exceptions import RetryableException
        exc = RetryableException(retry_after=10.0, max_retries=5)
        d = exc.to_dict()
        assert d["retry"]["retry_after"] == 10.0
        assert d["retry"]["max_retries"] == 5

    def test_to_response_dict_no_traceback(self) -> None:
        """API 응답에 트레이스백 미포함."""
        from shared.exceptions import CourtViewException
        exc = CourtViewException(message="오류", cause=ValueError("원인"))
        resp = exc.to_response_dict()
        assert "traceback" not in resp
        assert resp["success"] is False
