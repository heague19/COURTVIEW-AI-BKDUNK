# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/multi_camera
파일: camera_config.py
설명: 카메라별 설정 관리
      - CameraConfig: 개별 카메라 설정 (타입, 해상도, FPS, 배치 정보)
      - CameraSetupConfig: 멀티카메라 셋업 전체 설정
      - CameraPlacement: 카메라 물리적 배치 정보
      - 설정 검증 및 기본 프로파일 팩토리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import uuid
from dataclasses import dataclass, field
from typing import Final

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.camera_constants import (
    CAMERA_DISTANCE_MAX_M,
    CAMERA_DISTANCE_MIN_M,
    CAMERA_DISTANCE_OPTIMAL_M,
    CAMERA_FOV_MAX_DEG,
    CAMERA_FOV_MIN_DEG,
    CAMERA_FOV_OPTIMAL_DEG,
    CAMERA_HEIGHT_MAX_M,
    CAMERA_HEIGHT_MIN_M,
    CAMERA_HEIGHT_OPTIMAL_M,
    CameraQualityPreset,
    CameraType,
    DEFAULT_FRAME_RATE,
    DEFAULT_RESOLUTION,
    FRAME_BUFFER_SIZE,
    HARDWARE_SYNC_JITTER_MS,
    MAX_CAMERAS,
    MAX_FRAME_BUFFER_SIZE,
    MAX_FRAME_RATE,
    MAX_RESOLUTION,
    MIN_CAMERAS,
    MIN_FRAME_RATE,
    MIN_RESOLUTION,
    OPTIMAL_CAMERA_COUNT,
    SOFTWARE_SYNC_JITTER_MS,
    SYNC_TOLERANCE_MS,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 카메라 이름 최대 길이
CAMERA_NAME_MAX_LENGTH: Final[int] = 64

# 카메라 소스 경로 최대 길이
CAMERA_SOURCE_MAX_LENGTH: Final[int] = 512

# 카메라 ID 접두사
CAMERA_ID_PREFIX: Final[str] = "cam_"

# 배치 위치 설명 최대 길이
PLACEMENT_LABEL_MAX_LENGTH: Final[int] = 128

# 기본 카메라 이름 포맷
DEFAULT_CAMERA_NAME_FORMAT: Final[str] = "Camera_{index}"

# 셋업 ID 접두사
SETUP_ID_PREFIX: Final[str] = "setup_"


# =============================================================================
# CameraPlacement: 카메라 물리적 배치 정보
# =============================================================================

@dataclass(slots=True)
class CameraPlacement:
    """카메라 물리적 배치 정보.

    코트에 대한 카메라의 물리적 위치, 방향, 시야각 정보.

    Attributes:
        height_m: 카메라 높이 (미터)
        distance_m: 코트 중심까지 거리 (미터)
        angle_deg: 코트 중심 기준 방위각 (도, 0=사이드라인 중앙)
        tilt_deg: 수직 틸트 각도 (도, 0=수평)
        fov_deg: 시야각 (도)
        label: 배치 위치 설명
    """

    height_m: float = CAMERA_HEIGHT_OPTIMAL_M
    distance_m: float = CAMERA_DISTANCE_OPTIMAL_M
    angle_deg: float = 0.0
    tilt_deg: float = -15.0
    fov_deg: float = CAMERA_FOV_OPTIMAL_DEG
    label: str = ""

    def __post_init__(self) -> None:
        """초기화 후 클램핑."""
        self.height_m = max(CAMERA_HEIGHT_MIN_M, min(self.height_m, CAMERA_HEIGHT_MAX_M))
        self.distance_m = max(CAMERA_DISTANCE_MIN_M, min(self.distance_m, CAMERA_DISTANCE_MAX_M))
        self.angle_deg = self.angle_deg % 360.0
        self.fov_deg = max(CAMERA_FOV_MIN_DEG, min(self.fov_deg, CAMERA_FOV_MAX_DEG))
        if len(self.label) > PLACEMENT_LABEL_MAX_LENGTH:
            self.label = self.label[:PLACEMENT_LABEL_MAX_LENGTH]

    @property
    def is_optimal(self) -> bool:
        """최적 배치 범위 내인지 확인."""
        height_ok = abs(self.height_m - CAMERA_HEIGHT_OPTIMAL_M) < 2.0
        distance_ok = abs(self.distance_m - CAMERA_DISTANCE_OPTIMAL_M) < 3.0
        fov_ok = abs(self.fov_deg - CAMERA_FOV_OPTIMAL_DEG) < 15.0
        return height_ok and distance_ok and fov_ok

    def __repr__(self) -> str:
        return (
            f"CameraPlacement(h={self.height_m:.1f}m, "
            f"d={self.distance_m:.1f}m, "
            f"angle={self.angle_deg:.0f}°, "
            f"fov={self.fov_deg:.0f}°, "
            f"label='{self.label}')"
        )


# =============================================================================
# CameraConfig: 개별 카메라 설정
# =============================================================================

@dataclass(slots=True)
class CameraConfig:
    """개별 카메라 설정.

    카메라 한 대의 전체 설정: 타입, 해상도, FPS, 소스 경로, 배치 정보.

    Attributes:
        camera_id: 고유 카메라 ID
        name: 카메라 이름
        camera_type: 카메라 타입 (USB, IP, RTSP, FILE, VIRTUAL)
        source: 소스 경로/URL/인덱스
        resolution: 해상도 (width, height)
        frame_rate: 프레임레이트 (FPS)
        buffer_size: 프레임 버퍼 크기
        placement: 물리적 배치 정보
        enabled: 활성화 여부
        priority: 우선순위 (0=최고, 숫자 클수록 낮음)
        quality_preset: 품질 프리셋 (None이면 수동 설정)
    """

    camera_id: str = ""
    name: str = ""
    camera_type: CameraType = CameraType.USB
    source: str = ""
    resolution: tuple[int, int] = DEFAULT_RESOLUTION
    frame_rate: int = DEFAULT_FRAME_RATE
    buffer_size: int = FRAME_BUFFER_SIZE
    placement: CameraPlacement = field(default_factory=CameraPlacement)
    enabled: bool = True
    priority: int = 0
    quality_preset: CameraQualityPreset | None = None

    def __post_init__(self) -> None:
        """초기화 후 검증 및 기본값 설정."""
        # 카메라 ID 자동 생성
        if not self.camera_id:
            self.camera_id = f"{CAMERA_ID_PREFIX}{uuid.uuid4().hex[:12]}"

        # 이름 클램핑
        if len(self.name) > CAMERA_NAME_MAX_LENGTH:
            self.name = self.name[:CAMERA_NAME_MAX_LENGTH]

        # 소스 클램핑
        if len(self.source) > CAMERA_SOURCE_MAX_LENGTH:
            self.source = self.source[:CAMERA_SOURCE_MAX_LENGTH]

        # 프리셋 적용 (프리셋이 있으면 해상도/FPS 오버라이드)
        if self.quality_preset is not None:
            self.resolution = self.quality_preset.resolution
            self.frame_rate = self.quality_preset.fps

        # 해상도 클램핑
        w = max(MIN_RESOLUTION[0], min(self.resolution[0], MAX_RESOLUTION[0]))
        h = max(MIN_RESOLUTION[1], min(self.resolution[1], MAX_RESOLUTION[1]))
        self.resolution = (w, h)

        # FPS 클램핑
        self.frame_rate = max(MIN_FRAME_RATE, min(self.frame_rate, MAX_FRAME_RATE))

        # 버퍼 크기 클램핑
        self.buffer_size = max(1, min(self.buffer_size, MAX_FRAME_BUFFER_SIZE))

        # 우선순위 클램핑
        self.priority = max(0, min(self.priority, MAX_CAMERAS - 1))

    @property
    def pixel_count(self) -> int:
        """총 픽셀 수."""
        return self.resolution[0] * self.resolution[1]

    @property
    def is_network_camera(self) -> bool:
        """네트워크 카메라 여부."""
        return self.camera_type.is_network

    @property
    def is_file_input(self) -> bool:
        """파일 입력 여부."""
        return self.camera_type == CameraType.FILE

    @property
    def estimated_frame_bytes(self) -> int:
        """프레임당 예상 바이트 수 (BGR 기준)."""
        return self.resolution[0] * self.resolution[1] * 3

    @property
    def estimated_buffer_memory_bytes(self) -> int:
        """버퍼 전체 예상 메모리 (바이트)."""
        return self.estimated_frame_bytes * self.buffer_size

    def validate(self) -> list[str]:
        """설정 유효성 검사.

        Returns:
            오류 메시지 목록 (빈 리스트 = 유효)
        """
        errors: list[str] = []

        if not self.camera_id:
            errors.append("카메라 ID가 비어있습니다")

        if self.camera_type.is_network and not self.source:
            errors.append(f"네트워크 카메라({self.camera_type.value})에 소스 URL이 필요합니다")

        if self.camera_type == CameraType.FILE and not self.source:
            errors.append("파일 입력에 소스 경로가 필요합니다")

        w, h = self.resolution
        if w < MIN_RESOLUTION[0] or h < MIN_RESOLUTION[1]:
            errors.append(
                f"해상도({w}x{h})가 최소({MIN_RESOLUTION[0]}x{MIN_RESOLUTION[1]}) 미만"
            )

        if self.frame_rate < MIN_FRAME_RATE:
            errors.append(f"FPS({self.frame_rate})가 최소({MIN_FRAME_RATE}) 미만")

        return errors

    def __repr__(self) -> str:
        w, h = self.resolution
        return (
            f"CameraConfig(id='{self.camera_id}', "
            f"name='{self.name}', "
            f"type={self.camera_type.value}, "
            f"{w}x{h}@{self.frame_rate}fps, "
            f"enabled={self.enabled})"
        )


# =============================================================================
# SyncConfig: 동기화 설정
# =============================================================================

@dataclass(slots=True)
class SyncConfig:
    """멀티카메라 동기화 설정.

    Attributes:
        tolerance_ms: 동기화 허용 오차 (밀리초)
        use_hardware_sync: 하드웨어 동기화 사용 여부
        master_camera_id: 마스터 카메라 ID (None이면 자동 선택)
    """

    tolerance_ms: float = SYNC_TOLERANCE_MS
    use_hardware_sync: bool = False
    master_camera_id: str | None = None

    def __post_init__(self) -> None:
        """초기화 후 클램핑."""
        # 하드웨어 동기화 시 더 엄격한 허용 오차
        min_tolerance = (
            HARDWARE_SYNC_JITTER_MS if self.use_hardware_sync
            else SOFTWARE_SYNC_JITTER_MS
        )
        max_tolerance = SYNC_TOLERANCE_MS * 3.0
        self.tolerance_ms = max(min_tolerance, min(self.tolerance_ms, max_tolerance))

    @property
    def jitter_limit_ms(self) -> float:
        """지터 한계 (밀리초)."""
        if self.use_hardware_sync:
            return HARDWARE_SYNC_JITTER_MS
        return SOFTWARE_SYNC_JITTER_MS

    def __repr__(self) -> str:
        sync_type = "HW" if self.use_hardware_sync else "SW"
        return (
            f"SyncConfig({sync_type}, "
            f"tolerance={self.tolerance_ms:.1f}ms, "
            f"master={self.master_camera_id or 'auto'})"
        )


# =============================================================================
# CameraSetupConfig: 멀티카메라 셋업 전체 설정
# =============================================================================

@dataclass(slots=True)
class CameraSetupConfig:
    """멀티카메라 셋업 전체 설정.

    4~8대 카메라 시스템의 전체 구성 정보.

    Attributes:
        setup_id: 셋업 고유 ID
        cameras: 카메라 설정 목록
        sync: 동기화 설정
        reference_camera_index: 기준 카메라 인덱스 (좌표 변환 기준)
    """

    setup_id: str = ""
    cameras: list[CameraConfig] = field(default_factory=list)
    sync: SyncConfig = field(default_factory=SyncConfig)
    reference_camera_index: int = 0

    def __post_init__(self) -> None:
        """초기화 후 기본값."""
        if not self.setup_id:
            self.setup_id = f"{SETUP_ID_PREFIX}{uuid.uuid4().hex[:12]}"

    @property
    def camera_count(self) -> int:
        """등록된 카메라 수."""
        return len(self.cameras)

    @property
    def enabled_cameras(self) -> list[CameraConfig]:
        """활성화된 카메라 목록."""
        return [c for c in self.cameras if c.enabled]

    @property
    def enabled_count(self) -> int:
        """활성화된 카메라 수."""
        return len(self.enabled_cameras)

    @property
    def reference_camera(self) -> CameraConfig | None:
        """기준 카메라."""
        if 0 <= self.reference_camera_index < len(self.cameras):
            return self.cameras[self.reference_camera_index]
        return None

    def get_camera_by_id(self, camera_id: str) -> CameraConfig | None:
        """카메라 ID로 설정 조회.

        Args:
            camera_id: 카메라 ID

        Returns:
            카메라 설정 또는 None
        """
        for cam in self.cameras:
            if cam.camera_id == camera_id:
                return cam
        return None

    def get_camera_ids(self) -> list[str]:
        """전체 카메라 ID 목록."""
        return [c.camera_id for c in self.cameras]

    def add_camera(self, config: CameraConfig) -> bool:
        """카메라 추가.

        Args:
            config: 카메라 설정

        Returns:
            추가 성공 여부
        """
        if len(self.cameras) >= MAX_CAMERAS:
            return False

        # ID 중복 확인
        if any(c.camera_id == config.camera_id for c in self.cameras):
            return False

        self.cameras.append(config)
        return True

    def remove_camera(self, camera_id: str) -> bool:
        """카메라 제거.

        Args:
            camera_id: 제거할 카메라 ID

        Returns:
            제거 성공 여부
        """
        for i, cam in enumerate(self.cameras):
            if cam.camera_id == camera_id:
                self.cameras.pop(i)
                # reference_camera_index 조정
                if self.reference_camera_index >= len(self.cameras):
                    self.reference_camera_index = max(0, len(self.cameras) - 1)
                return True
        return False

    def validate(self) -> list[str]:
        """셋업 전체 유효성 검사.

        Returns:
            오류 메시지 목록 (빈 리스트 = 유효)
        """
        errors: list[str] = []

        if not self.cameras:
            errors.append("카메라가 등록되지 않았습니다")
            return errors

        if len(self.cameras) < MIN_CAMERAS:
            errors.append(
                f"카메라 수({len(self.cameras)})가 최소({MIN_CAMERAS}) 미만"
            )

        if len(self.cameras) > MAX_CAMERAS:
            errors.append(
                f"카메라 수({len(self.cameras)})가 최대({MAX_CAMERAS}) 초과"
            )

        # ID 중복 확인
        ids = [c.camera_id for c in self.cameras]
        if len(ids) != len(set(ids)):
            errors.append("카메라 ID 중복이 존재합니다")

        # reference_camera_index 범위 확인
        if self.reference_camera_index < 0 or self.reference_camera_index >= len(self.cameras):
            errors.append(
                f"기준 카메라 인덱스({self.reference_camera_index})가 "
                f"범위(0~{len(self.cameras) - 1})를 벗어남"
            )

        # 개별 카메라 검증
        for i, cam in enumerate(self.cameras):
            cam_errors = cam.validate()
            for err in cam_errors:
                errors.append(f"카메라[{i}] '{cam.name}': {err}")

        # 마스터 카메라 확인
        if self.sync.master_camera_id is not None:
            if not any(c.camera_id == self.sync.master_camera_id for c in self.cameras):
                errors.append(
                    f"마스터 카메라({self.sync.master_camera_id})가 등록된 카메라에 없습니다"
                )

        return errors

    @property
    def total_estimated_memory_bytes(self) -> int:
        """전체 카메라 예상 버퍼 메모리 (바이트)."""
        return sum(c.estimated_buffer_memory_bytes for c in self.enabled_cameras)

    def __repr__(self) -> str:
        return (
            f"CameraSetupConfig(id='{self.setup_id}', "
            f"cameras={self.camera_count}, "
            f"enabled={self.enabled_count}, "
            f"sync={self.sync!r})"
        )


# =============================================================================
# 팩토리 함수
# =============================================================================

def create_default_camera_config(
    index: int,
    camera_type: CameraType = CameraType.USB,
    source: str = "",
    quality_preset: CameraQualityPreset = CameraQualityPreset.HIGH,
) -> CameraConfig:
    """기본 카메라 설정 생성.

    Args:
        index: 카메라 인덱스 (0부터)
        camera_type: 카메라 타입
        source: 소스 경로/URL
        quality_preset: 품질 프리셋

    Returns:
        CameraConfig 인스턴스
    """
    # USB 카메라의 경우 소스가 비어있으면 인덱스 사용
    if camera_type == CameraType.USB and not source:
        source = str(index)

    return CameraConfig(
        name=DEFAULT_CAMERA_NAME_FORMAT.format(index=index),
        camera_type=camera_type,
        source=source,
        quality_preset=quality_preset,
        priority=index,
    )


def create_4camera_setup(
    camera_type: CameraType = CameraType.USB,
    quality_preset: CameraQualityPreset = CameraQualityPreset.HIGH,
    sources: list[str] | None = None,
) -> CameraSetupConfig:
    """4대 카메라 셋업 생성 (코트 4면 배치).

    Args:
        camera_type: 카메라 타입
        quality_preset: 품질 프리셋
        sources: 소스 경로 목록 (4개, None이면 자동)

    Returns:
        CameraSetupConfig 인스턴스
    """
    if sources is None:
        sources = [""] * OPTIMAL_CAMERA_COUNT

    if len(sources) < OPTIMAL_CAMERA_COUNT:
        sources = sources + [""] * (OPTIMAL_CAMERA_COUNT - len(sources))

    # 4대: 0°(사이드1), 90°(엔드1), 180°(사이드2), 270°(엔드2)
    placements = [
        CameraPlacement(angle_deg=0.0, label="사이드라인 1"),
        CameraPlacement(angle_deg=90.0, label="엔드라인 1"),
        CameraPlacement(angle_deg=180.0, label="사이드라인 2"),
        CameraPlacement(angle_deg=270.0, label="엔드라인 2"),
    ]

    cameras: list[CameraConfig] = []
    for i in range(OPTIMAL_CAMERA_COUNT):
        cam = create_default_camera_config(
            index=i,
            camera_type=camera_type,
            source=sources[i],
            quality_preset=quality_preset,
        )
        cam.placement = placements[i]
        cameras.append(cam)

    return CameraSetupConfig(cameras=cameras)


def create_8camera_setup(
    camera_type: CameraType = CameraType.USB,
    quality_preset: CameraQualityPreset = CameraQualityPreset.HIGH,
    sources: list[str] | None = None,
) -> CameraSetupConfig:
    """8대 카메라 셋업 생성 (코트 8방향 배치).

    Args:
        camera_type: 카메라 타입
        quality_preset: 품질 프리셋
        sources: 소스 경로 목록 (8개, None이면 자동)

    Returns:
        CameraSetupConfig 인스턴스
    """
    if sources is None:
        sources = [""] * MAX_CAMERAS

    if len(sources) < MAX_CAMERAS:
        sources = sources + [""] * (MAX_CAMERAS - len(sources))

    # 8대: 45도 간격
    labels = [
        "사이드라인 1", "사이드-엔드 코너 1",
        "엔드라인 1", "사이드-엔드 코너 2",
        "사이드라인 2", "사이드-엔드 코너 3",
        "엔드라인 2", "사이드-엔드 코너 4",
    ]

    cameras: list[CameraConfig] = []
    for i in range(MAX_CAMERAS):
        angle = i * 45.0
        cam = create_default_camera_config(
            index=i,
            camera_type=camera_type,
            source=sources[i],
            quality_preset=quality_preset,
        )
        cam.placement = CameraPlacement(angle_deg=angle, label=labels[i])
        cameras.append(cam)

    return CameraSetupConfig(cameras=cameras)


def create_file_input_setup(
    file_paths: list[str],
    quality_preset: CameraQualityPreset = CameraQualityPreset.HIGH,
) -> CameraSetupConfig:
    """파일 입력 셋업 생성 (녹화 영상 분석용).

    Args:
        file_paths: 영상 파일 경로 목록 (1~8개)
        quality_preset: 품질 프리셋

    Returns:
        CameraSetupConfig 인스턴스
    """
    count = max(1, min(len(file_paths), MAX_CAMERAS))

    cameras: list[CameraConfig] = []
    for i in range(count):
        cam = create_default_camera_config(
            index=i,
            camera_type=CameraType.FILE,
            source=file_paths[i],
            quality_preset=quality_preset,
        )
        cameras.append(cam)

    setup = CameraSetupConfig(cameras=cameras)
    # 파일 입력은 SW 동기화
    setup.sync.use_hardware_sync = False
    return setup


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터 클래스
    "CameraPlacement",
    "CameraConfig",
    "SyncConfig",
    "CameraSetupConfig",
    # 팩토리 함수
    "create_default_camera_config",
    "create_4camera_setup",
    "create_8camera_setup",
    "create_file_input_setup",
    # 상수
    "CAMERA_NAME_MAX_LENGTH",
    "CAMERA_SOURCE_MAX_LENGTH",
    "CAMERA_ID_PREFIX",
    "PLACEMENT_LABEL_MAX_LENGTH",
    "DEFAULT_CAMERA_NAME_FORMAT",
    "SETUP_ID_PREFIX",
]

__version__ = "1.0.0"
