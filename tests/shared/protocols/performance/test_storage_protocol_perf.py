# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/protocols/performance
파일: test_storage_protocol_perf.py
설명: storage_protocol.py 성능 테스트
      - Protocol isinstance 검사 성능 측정
      - 메서드 호출 오버헤드 측정
      - 스트림 처리 성능 측정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import io
import sys
import time
from pathlib import Path
from typing import AsyncIterator

# UTF-8 인코딩 강제 설정 (cp949 에러 방지)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 설정 (depth=4: tests/shared/protocols/performance)
_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# =============================================================================
# 내부 의존성 (Internal Dependencies)
# =============================================================================
from dataclasses import dataclass
from shared.protocols.storage_protocol import (
    StorageProtocol,
    AsyncStorageProtocol,
    __all__,
    __version__,
)


# =============================================================================
# 성능 테스트 결과 데이터클래스
# =============================================================================

@dataclass
class PerfResult:
    """성능 테스트 결과."""
    section: str
    name: str
    passed: bool
    elapsed_ms: float
    limit_ms: float
    message: str = ""


# =============================================================================
# 전역 변수
# =============================================================================

results: list[PerfResult] = []
total_pass = 0
total_fail = 0


# =============================================================================
# 스텁 클래스 (성능 테스트용 경량 구현체)
# =============================================================================

class _StubStorage:
    """동기 스토리지 프로토콜 스텁 (완전 구현)."""

    def exists(self, key: str) -> bool:
        """파일 존재 여부 확인."""
        return True

    def read(self, key: str) -> bytes:
        """파일 읽기."""
        return b"test data"

    def read_stream(self, key: str) -> io.BytesIO:
        """파일 스트림 읽기."""
        return io.BytesIO(b"test data")

    def write(self, key: str, data: bytes) -> bool:
        """파일 쓰기."""
        return True

    def write_stream(self, key: str, stream: io.BytesIO) -> bool:
        """파일 스트림 쓰기."""
        return True

    def delete(self, key: str) -> bool:
        """파일 삭제."""
        return True

    def list(self, prefix: str, max_results: int | None = None) -> list[str]:
        """파일 목록 조회."""
        return ["file1.mp4", "file2.mp4", "file3.mp4"]

    def get_url(self, key: str, expires_in: int | None = None) -> str:
        """파일 URL 조회."""
        return f"https://s3.amazonaws.com/courtview/{key}"


class _StubAsyncStorage:
    """비동기 스토리지 프로토콜 스텁 (완전 구현)."""

    async def exists(self, key: str) -> bool:
        """파일 존재 여부 확인 (비동기)."""
        return True

    async def read(self, key: str) -> bytes:
        """파일 읽기 (비동기)."""
        return b"async test data"

    async def read_stream(self, key: str) -> AsyncIterator[bytes]:
        """파일 스트림 읽기 (비동기)."""
        yield b"chunk1"
        yield b"chunk2"
        yield b"chunk3"

    async def write(self, key: str, data: bytes) -> bool:
        """파일 쓰기 (비동기)."""
        return True

    async def write_stream(
        self,
        key: str,
        stream: AsyncIterator[bytes],
    ) -> bool:
        """파일 스트림 쓰기 (비동기)."""
        async for _ in stream:
            pass
        return True

    async def delete(self, key: str) -> bool:
        """파일 삭제 (비동기)."""
        return True

    async def list(
        self,
        prefix: str,
        max_results: int | None = None,
    ) -> AsyncIterator[str]:
        """파일 목록 조회 (비동기 이터레이터)."""
        yield "file1.mp4"
        yield "file2.mp4"
        yield "file3.mp4"

    async def get_url(
        self,
        key: str,
        expires_in: int | None = None,
    ) -> str:
        """파일 URL 조회 (비동기)."""
        return f"https://s3.amazonaws.com/courtview/{key}"


class _PartialStub:
    """부분 구현 스텁 (isinstance 체크 실패용)."""

    def exists(self, key: str) -> bool:
        """exists만 구현."""
        return True


# =============================================================================
# 성능 테스트 헬퍼 함수
# =============================================================================

def run_perf(section: str, name: str, test_fn, limit_ms: float):
    """
    성능 테스트 실행 및 결과 기록.

    Args:
        section: 테스트 섹션
        name: 테스트 이름
        test_fn: 테스트 함수
        limit_ms: 제한 시간 (밀리초)
    """
    global total_pass, total_fail
    try:
        start = time.perf_counter()
        test_fn()
        elapsed = (time.perf_counter() - start) * 1000
        passed = elapsed < limit_ms
        results.append(PerfResult(section, name, passed, elapsed, limit_ms))
        if passed:
            total_pass += 1
        else:
            total_fail += 1
            results[-1].message = f"{elapsed:.3f}ms > {limit_ms:.1f}ms"
    except Exception as e:
        results.append(PerfResult(section, name, False, 0.0, limit_ms, str(e)))
        total_fail += 1


# =============================================================================
# [A] Import 성능 테스트
# =============================================================================

def test_a1_import_storage_protocol():
    """storage_protocol 모듈 import 성능."""
    for _ in range(100):
        import shared.protocols.storage_protocol  # noqa: F401


def test_a2_import_shared_protocols():
    """shared.protocols 패키지 import 성능."""
    for _ in range(100):
        import shared.protocols  # noqa: F401


# =============================================================================
# [B] Protocol 클래스 접근 성능 테스트
# =============================================================================

def test_b1_access_storage_protocol():
    """StorageProtocol 클래스 접근 10,000회."""
    for _ in range(10000):
        _ = StorageProtocol


def test_b2_access_async_storage_protocol():
    """AsyncStorageProtocol 클래스 접근 10,000회."""
    for _ in range(10000):
        _ = AsyncStorageProtocol


# =============================================================================
# [C] isinstance - StorageProtocol 테스트
# =============================================================================

def test_c1_isinstance_valid_stub():
    """유효한 스텁 10,000× isinstance (StorageProtocol)."""
    stub = _StubStorage()
    for _ in range(10000):
        _ = isinstance(stub, StorageProtocol)


def test_c2_isinstance_object():
    """object() 10,000× isinstance - negative (StorageProtocol)."""
    obj = object()
    for _ in range(10000):
        _ = isinstance(obj, StorageProtocol)


def test_c3_isinstance_partial_stub():
    """부분 스텁 10,000× isinstance - negative (StorageProtocol)."""
    partial = _PartialStub()
    for _ in range(10000):
        _ = isinstance(partial, StorageProtocol)


# =============================================================================
# [D] isinstance - AsyncStorageProtocol 테스트
# =============================================================================

def test_d1_isinstance_async_valid_stub():
    """유효한 비동기 스텁 10,000× isinstance (AsyncStorageProtocol)."""
    async_stub = _StubAsyncStorage()
    for _ in range(10000):
        _ = isinstance(async_stub, AsyncStorageProtocol)


def test_d2_isinstance_async_object():
    """object() 10,000× isinstance - negative (AsyncStorageProtocol)."""
    obj = object()
    for _ in range(10000):
        _ = isinstance(obj, AsyncStorageProtocol)


def test_d3_isinstance_async_partial_stub():
    """부분 스텁 10,000× isinstance - negative (AsyncStorageProtocol)."""
    partial = _PartialStub()
    for _ in range(10000):
        _ = isinstance(partial, AsyncStorageProtocol)


# =============================================================================
# [E] 스텁 인스턴스화 성능 테스트
# =============================================================================

def test_e1_instantiate_stub_storage():
    """_StubStorage 생성 10,000회."""
    for _ in range(10000):
        _ = _StubStorage()


def test_e2_instantiate_stub_async_storage():
    """_StubAsyncStorage 생성 10,000회."""
    for _ in range(10000):
        _ = _StubAsyncStorage()


# =============================================================================
# [F] 동기 메서드 호출 성능 테스트
# =============================================================================

def test_f1_sync_method_exists():
    """exists() 메서드 호출 10,000회."""
    stub = _StubStorage()
    for _ in range(10000):
        _ = stub.exists("test.mp4")


def test_f2_sync_method_read():
    """read() 메서드 호출 10,000회."""
    stub = _StubStorage()
    for _ in range(10000):
        _ = stub.read("test.mp4")


def test_f3_sync_method_read_stream():
    """read_stream() 메서드 호출 10,000회."""
    stub = _StubStorage()
    for _ in range(10000):
        _ = stub.read_stream("test.mp4")


def test_f4_sync_method_write():
    """write() 메서드 호출 10,000회."""
    stub = _StubStorage()
    data = b"test data"
    for _ in range(10000):
        _ = stub.write("test.mp4", data)


def test_f5_sync_method_write_stream():
    """write_stream() 메서드 호출 10,000회."""
    stub = _StubStorage()
    stream = io.BytesIO(b"test data")
    for _ in range(10000):
        _ = stub.write_stream("test.mp4", stream)


def test_f6_sync_method_delete():
    """delete() 메서드 호출 10,000회."""
    stub = _StubStorage()
    for _ in range(10000):
        _ = stub.delete("test.mp4")


def test_f7_sync_method_list():
    """list() 메서드 호출 10,000회."""
    stub = _StubStorage()
    for _ in range(10000):
        _ = stub.list("videos/", max_results=100)


def test_f8_sync_method_get_url():
    """get_url() 메서드 호출 10,000회."""
    stub = _StubStorage()
    for _ in range(10000):
        _ = stub.get_url("test.mp4", expires_in=3600)


# =============================================================================
# [G] BytesIO 통합 성능 테스트
# =============================================================================

def test_g1_read_stream_and_read_data():
    """read_stream() + 데이터 읽기 1,000회."""
    stub = _StubStorage()
    for _ in range(1000):
        stream = stub.read_stream("test.mp4")
        _ = stream.read()


def test_g2_write_stream_with_bytesio():
    """write_stream() + BytesIO 1,000회."""
    stub = _StubStorage()
    for _ in range(1000):
        stream = io.BytesIO(b"test data for write")
        _ = stub.write_stream("test.mp4", stream)


# =============================================================================
# [H] __all__ 및 __version__ 접근 성능 테스트
# =============================================================================

def test_h1_access_all():
    """__all__ 접근 10,000회."""
    for _ in range(10000):
        _ = __all__


def test_h2_access_version():
    """__version__ 접근 10,000회."""
    for _ in range(10000):
        _ = __version__


# =============================================================================
# 메인 실행 (전체 성능 테스트)
# =============================================================================

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  storage_protocol.py 성능 테스트 시작")
    print(f"{'='*60}")

    # [A] Import 성능 테스트 (2개, 100ms)
    run_perf("A", "Import storage_protocol 모듈 100회", test_a1_import_storage_protocol, 100.0)
    run_perf("A", "Import shared.protocols 패키지 100회", test_a2_import_shared_protocols, 100.0)

    # [B] Protocol 클래스 접근 성능 (2개, 1ms)
    run_perf("B", "StorageProtocol 클래스 접근 10,000회", test_b1_access_storage_protocol, 1.0)
    run_perf("B", "AsyncStorageProtocol 클래스 접근 10,000회", test_b2_access_async_storage_protocol, 1.0)

    # [C] isinstance - StorageProtocol (3개, 100ms)
    run_perf("C", "유효한 스텁 10,000× isinstance (StorageProtocol)", test_c1_isinstance_valid_stub, 100.0)
    run_perf("C", "object() 10,000× isinstance - negative (StorageProtocol)", test_c2_isinstance_object, 100.0)
    run_perf("C", "부분 스텁 10,000× isinstance - negative (StorageProtocol)", test_c3_isinstance_partial_stub, 100.0)

    # [D] isinstance - AsyncStorageProtocol (3개, 100ms)
    run_perf("D", "유효한 비동기 스텁 10,000× isinstance (AsyncStorageProtocol)", test_d1_isinstance_async_valid_stub, 100.0)
    run_perf("D", "object() 10,000× isinstance - negative (AsyncStorageProtocol)", test_d2_isinstance_async_object, 100.0)
    run_perf("D", "부분 스텁 10,000× isinstance - negative (AsyncStorageProtocol)", test_d3_isinstance_async_partial_stub, 100.0)

    # [E] 스텁 인스턴스화 (2개, 5ms)
    run_perf("E", "_StubStorage 생성 10,000회", test_e1_instantiate_stub_storage, 5.0)
    run_perf("E", "_StubAsyncStorage 생성 10,000회", test_e2_instantiate_stub_async_storage, 5.0)

    # [F] 동기 메서드 호출 (8개, 5ms)
    run_perf("F", "exists() 메서드 호출 10,000회", test_f1_sync_method_exists, 5.0)
    run_perf("F", "read() 메서드 호출 10,000회", test_f2_sync_method_read, 5.0)
    run_perf("F", "read_stream() 메서드 호출 10,000회", test_f3_sync_method_read_stream, 5.0)
    run_perf("F", "write() 메서드 호출 10,000회", test_f4_sync_method_write, 5.0)
    run_perf("F", "write_stream() 메서드 호출 10,000회", test_f5_sync_method_write_stream, 5.0)
    run_perf("F", "delete() 메서드 호출 10,000회", test_f6_sync_method_delete, 5.0)
    run_perf("F", "list() 메서드 호출 10,000회", test_f7_sync_method_list, 5.0)
    run_perf("F", "get_url() 메서드 호출 10,000회", test_f8_sync_method_get_url, 5.0)

    # [G] BytesIO 통합 (2개, 10ms)
    run_perf("G", "read_stream() + 데이터 읽기 1,000회", test_g1_read_stream_and_read_data, 10.0)
    run_perf("G", "write_stream() + BytesIO 1,000회", test_g2_write_stream_with_bytesio, 10.0)

    # [H] __all__ 및 __version__ 접근 (2개, 1ms)
    run_perf("H", "__all__ 접근 10,000회", test_h1_access_all, 1.0)
    run_perf("H", "__version__ 접근 10,000회", test_h2_access_version, 1.0)

    # 결과 출력
    current_section = ""
    for r in results:
        if r.section != current_section:
            current_section = r.section
            print(f"\n{'='*60}")
            print(f"  섹션 {current_section}")
            print(f"{'='*60}")
        status = "PASS" if r.passed else "FAIL"
        pct = (r.elapsed_ms / r.limit_ms * 100) if r.limit_ms > 0 else 0
        print(f"  [{status}] {r.name}")
        print(f"         {r.elapsed_ms:.3f}ms / {r.limit_ms:.1f}ms ({pct:.1f}%)")
        if not r.passed:
            print(f"         → {r.message}")

    # 최종 결과 요약
    print(f"\n{'='*60}")
    print(f"  storage_protocol.py 성능 테스트 최종 결과")
    print(f"{'='*60}")
    print(f"  총 테스트: {total_pass + total_fail}")
    print(f"  PASS: {total_pass}")
    print(f"  FAIL: {total_fail}")
    print(f"{'='*60}")

    if total_fail > 0:
        sys.exit(1)
