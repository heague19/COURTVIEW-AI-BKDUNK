# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/protocols
파일: storage_protocol.py
설명: 스토리지 프로토콜 정의 (typing.Protocol)
      - 동기/비동기 스토리지 접근을 위한 프로토콜
      - S3, 로컬 파일 시스템, 메모리 스토리지 지원
      - CLAUDE.md #28 S3/파일 지원 준수

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
from typing import (
    AsyncIterator,
    BinaryIO,
    Protocol,
    runtime_checkable,
)


# =============================================================================
# 스토리지 프로토콜 (동기)
# =============================================================================

@runtime_checkable
class StorageProtocol(Protocol):
    """
    스토리지 프로토콜 (동기 방식).

    파일/객체 스토리지 접근을 위한 표준 인터페이스입니다.
    S3, 로컬 파일 시스템, 메모리 스토리지 등에서 구현됩니다.

    Methods:
        exists: 파일 존재 여부 확인
        read: 파일 읽기 (바이트)
        read_stream: 파일 읽기 (스트림)
        write: 파일 쓰기 (바이트)
        write_stream: 파일 쓰기 (스트림)
        delete: 파일 삭제
        list: 경로의 파일 목록 조회
        get_url: 파일 URL 조회 (서명된 URL 또는 로컬 경로)

    Example:
        >>> class S3Storage:
        ...     def exists(self, key: str) -> bool: ...
        ...     def read(self, key: str) -> bytes: ...
        ...     # ... 기타 메서드 구현
        >>> storage: StorageProtocol = S3Storage()
        >>> isinstance(storage, StorageProtocol)
        True
    """

    def exists(self, key: str) -> bool:
        """
        파일/객체 존재 여부 확인.

        Args:
            key: 파일 키 (S3 키 또는 로컬 경로)

        Returns:
            존재 여부
        """
        ...

    def read(self, key: str) -> bytes:
        """
        파일/객체 읽기 (바이트).

        Args:
            key: 파일 키

        Returns:
            파일 내용 (바이트)

        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
            IOError: 읽기 실패
        """
        ...

    def read_stream(self, key: str) -> BinaryIO:
        """
        파일/객체 읽기 (스트림).

        대용량 파일의 경우 스트림으로 읽어 메모리 사용을 최적화합니다.

        Args:
            key: 파일 키

        Returns:
            바이너리 스트림

        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
            IOError: 읽기 실패
        """
        ...

    def write(self, key: str, data: bytes) -> bool:
        """
        파일/객체 쓰기 (바이트).

        Args:
            key: 파일 키
            data: 쓸 데이터

        Returns:
            성공 여부
        """
        ...

    def write_stream(self, key: str, stream: BinaryIO) -> bool:
        """
        파일/객체 쓰기 (스트림).

        대용량 파일의 경우 스트림으로 작성하여 메모리 사용을 최적화합니다.

        Args:
            key: 파일 키
            stream: 바이너리 스트림

        Returns:
            성공 여부
        """
        ...

    def delete(self, key: str) -> bool:
        """
        파일/객체 삭제.

        Args:
            key: 파일 키

        Returns:
            성공 여부 (존재하지 않는 파일 삭제 시도도 True 반환)
        """
        ...

    def list(self, prefix: str, max_results: int | None = None) -> list[str]:
        """
        경로의 파일/객체 목록 조회.

        Args:
            prefix: 경로 접두사 (S3 prefix 또는 디렉토리 경로)
            max_results: 최대 결과 수 (None이면 무제한)

        Returns:
            파일 키 목록
        """
        ...

    def get_url(
        self,
        key: str,
        expires_in: int | None = None,
    ) -> str:
        """
        파일 URL 조회.

        S3의 경우 서명된 URL을, 로컬의 경우 파일 경로를 반환합니다.

        Args:
            key: 파일 키
            expires_in: URL 만료 시간 (초). S3에서만 유효. None이면 기본값 사용.

        Returns:
            파일 URL 또는 경로
        """
        ...


# =============================================================================
# 비동기 스토리지 프로토콜
# =============================================================================

@runtime_checkable
class AsyncStorageProtocol(Protocol):
    """
    비동기 스토리지 프로토콜.

    고성능 비동기 파일/객체 스토리지 접근을 위한 인터페이스입니다.
    멀티카메라 환경에서 동시 파일 처리에 유용합니다.

    Methods:
        exists: 파일 존재 여부 확인 (비동기)
        read: 파일 읽기 (비동기)
        read_stream: 파일 스트림 읽기 (비동기)
        write: 파일 쓰기 (비동기)
        delete: 파일 삭제 (비동기)
        list: 파일 목록 조회 (비동기 이터레이터)
        get_url: 파일 URL 조회 (비동기)

    Example:
        >>> class AsyncS3Storage:
        ...     async def exists(self, key: str) -> bool: ...
        ...     async def read(self, key: str) -> bytes: ...
        ...     # ... 기타 메서드 구현
        >>> async_storage: AsyncStorageProtocol = AsyncS3Storage()
    """

    async def exists(self, key: str) -> bool:
        """
        파일/객체 존재 여부 확인 (비동기).

        Args:
            key: 파일 키

        Returns:
            존재 여부
        """
        ...

    async def read(self, key: str) -> bytes:
        """
        파일/객체 읽기 (비동기).

        Args:
            key: 파일 키

        Returns:
            파일 내용 (바이트)

        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
            IOError: 읽기 실패
        """
        ...

    async def read_stream(self, key: str) -> AsyncIterator[bytes]:
        """
        파일/객체 스트림 읽기 (비동기).

        대용량 파일을 청크 단위로 비동기 읽기합니다.

        Args:
            key: 파일 키

        Yields:
            파일 청크 (바이트)

        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
            IOError: 읽기 실패
        """
        ...

    async def write(self, key: str, data: bytes) -> bool:
        """
        파일/객체 쓰기 (비동기).

        Args:
            key: 파일 키
            data: 쓸 데이터

        Returns:
            성공 여부
        """
        ...

    async def write_stream(
        self,
        key: str,
        stream: AsyncIterator[bytes],
    ) -> bool:
        """
        파일/객체 스트림 쓰기 (비동기).

        대용량 파일을 청크 단위로 비동기 쓰기합니다.

        Args:
            key: 파일 키
            stream: 비동기 바이트 스트림

        Returns:
            성공 여부
        """
        ...

    async def delete(self, key: str) -> bool:
        """
        파일/객체 삭제 (비동기).

        Args:
            key: 파일 키

        Returns:
            성공 여부
        """
        ...

    async def list(
        self,
        prefix: str,
        max_results: int | None = None,
    ) -> AsyncIterator[str]:
        """
        경로의 파일/객체 목록 조회 (비동기 이터레이터).

        Args:
            prefix: 경로 접두사
            max_results: 최대 결과 수

        Yields:
            파일 키
        """
        ...

    async def get_url(
        self,
        key: str,
        expires_in: int | None = None,
    ) -> str:
        """
        파일 URL 조회 (비동기).

        Args:
            key: 파일 키
            expires_in: URL 만료 시간 (초)

        Returns:
            파일 URL 또는 경로
        """
        ...


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    "StorageProtocol",
    "AsyncStorageProtocol",
]

# 모듈 버전 정보
__version__ = "1.0.0"
