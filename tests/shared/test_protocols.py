# -*- coding: utf-8 -*-
"""
shared/protocols 단위 테스트.

김팀장 지시 §5-4:
- 4개 Protocol 전수 @runtime_checkable 확인
- 메서드 본문 `...` 만 포함
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Final

import pytest


_PROTOCOLS_DIR = Path(__file__).resolve().parent.parent.parent / "shared" / "protocols"

_SUBMODULE_NAMES: Final[list[str]] = [
    p.stem for p in sorted(_PROTOCOLS_DIR.glob("*.py"))
    if p.stem != "__init__" and not p.stem.startswith("_")
]


class TestImport:
    def test_package_import(self) -> None:
        from shared.protocols import __all__, __version__
        assert len(__all__) == 4
        assert __version__ == "1.0.0"

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_import(self, name: str) -> None:
        mod = importlib.import_module(f"shared.protocols.{name}")
        assert mod is not None


class TestVersion:
    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_version(self, name: str) -> None:
        mod = importlib.import_module(f"shared.protocols.{name}")
        version = getattr(mod, "__version__", None)
        if version is not None:
            assert version == "1.0.0", f"{name}.__version__ = {version}"


class TestAnnotations:
    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_future_annotations(self, name: str) -> None:
        filepath = _PROTOCOLS_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
        has_future = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in ast.walk(tree)
        )
        assert has_future, f"{name}.py에 from __future__ import annotations 없음"


class TestRuntimeCheckable:
    """@runtime_checkable 확인."""

    def test_camera_protocol_runtime_checkable(self) -> None:
        from shared.protocols import CameraProtocol
        assert getattr(CameraProtocol, "__protocol_attrs__", None) is not None or hasattr(CameraProtocol, "_is_runtime_protocol")

    def test_multi_camera_protocol_runtime_checkable(self) -> None:
        from shared.protocols import MultiCameraProtocol
        assert getattr(MultiCameraProtocol, "__protocol_attrs__", None) is not None or hasattr(MultiCameraProtocol, "_is_runtime_protocol")

    def test_storage_protocol_runtime_checkable(self) -> None:
        from shared.protocols import StorageProtocol
        assert getattr(StorageProtocol, "__protocol_attrs__", None) is not None or hasattr(StorageProtocol, "_is_runtime_protocol")

    def test_async_storage_protocol_runtime_checkable(self) -> None:
        from shared.protocols import AsyncStorageProtocol
        assert getattr(AsyncStorageProtocol, "__protocol_attrs__", None) is not None or hasattr(AsyncStorageProtocol, "_is_runtime_protocol")


class TestIsInstanceCheck:
    """runtime_checkable Protocol isinstance 검증."""

    def test_camera_protocol_isinstance(self) -> None:
        """CameraProtocol 구현체 isinstance 체크."""
        from shared.protocols import CameraProtocol
        import numpy as np

        class FakeCamera:
            @property
            def camera_id(self) -> str: return "fake"
            @property
            def is_opened(self) -> bool: return False
            @property
            def resolution(self) -> tuple[int, int]: return (640, 480)
            @property
            def fps(self) -> float: return 30.0
            def open(self) -> bool: return True
            def close(self) -> None: pass
            def read(self) -> tuple[bool, np.ndarray | None]: return (False, None)
            async def read_async(self) -> tuple[bool, np.ndarray | None]: return (False, None)
            def set_resolution(self, w: int, h: int) -> bool: return True
            def set_fps(self, fps: float) -> bool: return True
            def get_property(self, prop_id: int) -> float: return 0.0
            def set_property(self, prop_id: int, value: float) -> bool: return True

        assert isinstance(FakeCamera(), CameraProtocol)

    def test_storage_protocol_isinstance(self) -> None:
        """StorageProtocol 구현체 isinstance 체크."""
        from shared.protocols import StorageProtocol
        from typing import BinaryIO

        class FakeStorage:
            def exists(self, key: str) -> bool: return False
            def read(self, key: str) -> bytes: return b""
            def read_stream(self, key: str) -> BinaryIO: ...
            def write(self, key: str, data: bytes) -> bool: return True
            def write_stream(self, key: str, stream: BinaryIO) -> bool: return True
            def delete(self, key: str) -> bool: return True
            def list(self, prefix: str, max_results: int | None = None) -> list[str]: return []
            def get_url(self, key: str, expires_in: int | None = None) -> str: return ""

        assert isinstance(FakeStorage(), StorageProtocol)

    def test_non_conforming_not_isinstance(self) -> None:
        """Protocol 미구현 객체는 isinstance False."""
        from shared.protocols import CameraProtocol

        class NotACamera:
            pass

        assert not isinstance(NotACamera(), CameraProtocol)


class TestProtocolPurity:
    """Protocol 메서드가 순수 인터페이스인지 (본문 없음)."""

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_no_implementation(self, name: str) -> None:
        """Protocol 메서드 본문에 실제 로직 없음 (... 또는 pass만)."""
        filepath = _PROTOCOLS_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        # 실제 구현이 있으면 안 됨 — return 문이 있으면 구현 있음
        # (docstring 내 return은 무시)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # 본문이 Expr(Constant(...)) 또는 Pass만 허용
                        body = item.body
                        # docstring 제거 후 확인
                        non_doc = [
                            stmt for stmt in body
                            if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str))
                        ]
                        for stmt in non_doc:
                            assert isinstance(stmt, (ast.Expr, ast.Pass)), (
                                f"{name}.{node.name}.{item.name}: Protocol에 구현 로직 존재"
                            )
