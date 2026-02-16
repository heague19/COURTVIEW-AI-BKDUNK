# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/protocols
파일: camera_protocol.py
설명: 카메라 프로토콜 정의 (typing.Protocol)
      - CameraProtocol: 단일 카메라 접근 프로토콜
      - MultiCameraProtocol: 멀티카메라 동기화 프로토콜
      - USB, IP, RTSP, 파일 소스 지원
      - 프레임 캡처 및 설정 관리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.1.0
"""

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
from typing import (
    AsyncIterator,
    Iterator,
    Protocol,
    runtime_checkable,
)

# =============================================================================
# 서드파티 라이브러리 (Third-party)
# =============================================================================
import numpy as np
from numpy.typing import NDArray


# =============================================================================
# 카메라 프로토콜 (단일)
# =============================================================================

@runtime_checkable
class CameraProtocol(Protocol):
    """
    카메라 프로토콜.

    단일 카메라 접근을 위한 표준 인터페이스입니다.
    USB, IP, RTSP, 파일 입력 등에서 구현됩니다.

    Properties:
        camera_id: 카메라 고유 식별자
        is_opened: 카메라 열림 상태
        resolution: 현재 해상도 (width, height)
        fps: 현재 프레임 레이트

    Methods:
        open: 카메라 열기
        close: 카메라 닫기
        read: 프레임 읽기 (동기)
        read_async: 프레임 읽기 (비동기)
        set_resolution: 해상도 설정
        set_fps: FPS 설정
        get_property: 속성 조회
        set_property: 속성 설정

    Example:
        >>> class USBCamera:
        ...     @property
        ...     def camera_id(self) -> str: return "usb_0"
        ...     def open(self) -> bool: ...
        ...     # ... 기타 메서드 구현
        >>> camera: CameraProtocol = USBCamera()
        >>> isinstance(camera, CameraProtocol)
        True
    """

    @property
    def camera_id(self) -> str:
        """
        카메라 고유 식별자.

        Returns:
            카메라 ID 문자열
        """
        ...

    @property
    def is_opened(self) -> bool:
        """
        카메라 열림 상태.

        Returns:
            열림 여부
        """
        ...

    @property
    def resolution(self) -> tuple[int, int]:
        """
        현재 해상도.

        Returns:
            (width, height) 튜플
        """
        ...

    @property
    def fps(self) -> float:
        """
        현재 프레임 레이트.

        Returns:
            초당 프레임 수
        """
        ...

    def open(self) -> bool:
        """
        카메라 열기.

        카메라 장치에 연결하고 프레임 캡처를 준비합니다.

        Returns:
            성공 여부
        """
        ...

    def close(self) -> None:
        """
        카메라 닫기.

        카메라 장치 연결을 해제하고 리소스를 정리합니다.
        """
        ...

    def read(self) -> tuple[bool, NDArray[np.uint8] | None]:
        """
        프레임 읽기 (동기).

        다음 프레임을 읽어 반환합니다.

        Returns:
            (성공 여부, 프레임 이미지) 튜플
            - 성공: (True, ndarray of shape (H, W, 3) BGR)
            - 실패: (False, None)
        """
        ...

    async def read_async(self) -> tuple[bool, NDArray[np.uint8] | None]:
        """
        프레임 읽기 (비동기).

        다음 프레임을 비동기로 읽어 반환합니다.
        I/O 블로킹을 방지하고 동시 처리에 유리합니다.

        Returns:
            (성공 여부, 프레임 이미지) 튜플
        """
        ...

    def set_resolution(self, width: int, height: int) -> bool:
        """
        해상도 설정.

        Args:
            width: 너비 (픽셀)
            height: 높이 (픽셀)

        Returns:
            성공 여부
        """
        ...

    def set_fps(self, fps: float) -> bool:
        """
        FPS 설정.

        Args:
            fps: 목표 프레임 레이트

        Returns:
            성공 여부
        """
        ...

    def get_property(self, prop_id: int) -> float:
        """
        카메라 속성 조회.

        OpenCV VideoCapture 속성 ID를 사용합니다.

        Args:
            prop_id: 속성 ID (cv2.CAP_PROP_*)

        Returns:
            속성 값
        """
        ...

    def set_property(self, prop_id: int, value: float) -> bool:
        """
        카메라 속성 설정.

        Args:
            prop_id: 속성 ID
            value: 설정할 값

        Returns:
            성공 여부
        """
        ...


# =============================================================================
# 멀티카메라 프로토콜
# =============================================================================

@runtime_checkable
class MultiCameraProtocol(Protocol):
    """
    멀티카메라 프로토콜.

    여러 카메라를 동시에 관리하고 동기화된 프레임을 제공하는 인터페이스입니다.
    멀티뷰 3D 분석에서 사용됩니다.

    Properties:
        camera_ids: 등록된 카메라 ID 목록
        num_cameras: 카메라 수
        is_synced: 동기화 활성화 여부

    Methods:
        add_camera: 카메라 추가
        remove_camera: 카메라 제거
        get_camera: 카메라 조회
        open_all: 모든 카메라 열기
        close_all: 모든 카메라 닫기
        read_sync: 동기화된 프레임 읽기
        read_sync_async: 동기화된 프레임 읽기 (비동기)
        set_sync_tolerance: 동기화 허용 오차 설정
        iter_sync: 동기화된 프레임 이터레이터

    Example:
        >>> class MultiCameraSystem:
        ...     @property
        ...     def camera_ids(self) -> list[str]: ...
        ...     def read_sync(self) -> dict[str, NDArray]: ...
        >>> multi_cam: MultiCameraProtocol = MultiCameraSystem()
    """

    @property
    def camera_ids(self) -> list[str]:
        """
        등록된 카메라 ID 목록.

        Returns:
            카메라 ID 리스트
        """
        ...

    @property
    def num_cameras(self) -> int:
        """
        등록된 카메라 수.

        Returns:
            카메라 개수
        """
        ...

    @property
    def is_synced(self) -> bool:
        """
        동기화 활성화 여부.

        Returns:
            동기화 모드 활성화 여부
        """
        ...

    def add_camera(
        self,
        camera_id: str,
        camera: CameraProtocol,
    ) -> bool:
        """
        카메라 추가.

        Args:
            camera_id: 카메라 식별자
            camera: 카메라 인스턴스

        Returns:
            성공 여부
        """
        ...

    def remove_camera(self, camera_id: str) -> bool:
        """
        카메라 제거.

        Args:
            camera_id: 카메라 식별자

        Returns:
            성공 여부
        """
        ...

    def get_camera(self, camera_id: str) -> CameraProtocol | None:
        """
        카메라 조회.

        Args:
            camera_id: 카메라 식별자

        Returns:
            카메라 인스턴스 또는 None
        """
        ...

    def open_all(self) -> dict[str, bool]:
        """
        모든 카메라 열기.

        Returns:
            {camera_id: 성공 여부} 딕셔너리
        """
        ...

    def close_all(self) -> None:
        """
        모든 카메라 닫기.
        """
        ...

    def read_sync(
        self,
        timeout_ms: int | None = None,
    ) -> tuple[bool, dict[str, NDArray[np.uint8] | None]]:
        """
        동기화된 프레임 읽기.

        모든 카메라에서 동시에 (또는 지정된 허용 오차 내에서)
        프레임을 캡처합니다.

        Args:
            timeout_ms: 타임아웃 (밀리초). None이면 기본값 사용.

        Returns:
            (성공 여부, {camera_id: 프레임}) 튜플
            - 일부 카메라 실패 시 해당 프레임은 None
        """
        ...

    async def read_sync_async(
        self,
        timeout_ms: int | None = None,
    ) -> tuple[bool, dict[str, NDArray[np.uint8] | None]]:
        """
        동기화된 프레임 읽기 (비동기).

        비동기로 모든 카메라에서 동기화된 프레임을 캡처합니다.

        Args:
            timeout_ms: 타임아웃 (밀리초)

        Returns:
            (성공 여부, {camera_id: 프레임}) 튜플
        """
        ...

    def set_sync_tolerance(self, tolerance_ms: float) -> None:
        """
        동기화 허용 오차 설정.

        여러 카메라의 프레임 타임스탬프 차이 허용 범위를 설정합니다.

        Args:
            tolerance_ms: 허용 오차 (밀리초)
        """
        ...

    def iter_sync(
        self,
        max_frames: int | None = None,
    ) -> Iterator[dict[str, NDArray[np.uint8]]]:
        """
        동기화된 프레임 이터레이터 (동기).

        Args:
            max_frames: 최대 프레임 수. None이면 무한.

        Yields:
            {camera_id: 프레임} 딕셔너리
        """
        ...

    async def iter_sync_async(
        self,
        max_frames: int | None = None,
    ) -> AsyncIterator[dict[str, NDArray[np.uint8]]]:
        """
        동기화된 프레임 이터레이터 (비동기).

        Args:
            max_frames: 최대 프레임 수

        Yields:
            {camera_id: 프레임} 딕셔너리
        """
        ...


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    "CameraProtocol",
    "MultiCameraProtocol",
]

# 모듈 버전 정보
__version__ = "1.1.0"
