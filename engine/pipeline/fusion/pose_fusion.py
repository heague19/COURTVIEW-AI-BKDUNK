# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline/fusion
파일: pose_fusion.py
설명: 멀티카메라 포즈 융합 오케스트레이터
      - 각 카메라 뷰의 2D 포즈 추정 결과를 수집
      - MultiViewTriangulator를 호출하여 3D 키포인트 복원
      - 포즈 추정 자체는 pose_estimation/ 모듈이 수행
      - 삼각측량은 infrastructure/multi_camera/ 모듈이 수행
      - engine은 오케스트레이션만 담당

      데이터 흐름:
        8cam 2D 키포인트 (dict[camera_id, PoseEstimationResult])
          → 키포인트별 2뷰+ 수집
          → MultiViewTriangulator.triangulate_batch()
          → 3D 키포인트 (Nx3 array)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - infrastructure/multi_camera/coordinate_transformer.py: MultiViewTriangulator
    - shared/dto/pose_dto.py: PoseEstimationResult (단일 뷰 결과)
    - shared/constants/pose_constants.py: NUM_KEYPOINTS_COCO

소비자:
    - engine/pipeline/frame_pipeline.py: 🔴 FRAME 파이프라인 Stage1 후처리
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING, Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 임포트
# =============================================================================
if TYPE_CHECKING:
    from infrastructure.multi_camera.coordinate_transformer import (
        MultiViewTriangulator,
    )

from shared.constants.pose_constants import NUM_KEYPOINTS_COCO

_logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_FUSION_HISTORY: Final[int] = 200
_MIN_VIEWS_FOR_TRIANGULATION: Final[int] = 2
_MIN_KEYPOINT_CONFIDENCE: Final[float] = 0.3


# =============================================================================
# 입력: 카메라별 2D 포즈
# =============================================================================
@dataclass(slots=True)
class CameraPoseData:
    """
    단일 카메라의 포즈 추정 결과 (간소화).

    Attributes:
        camera_id: 카메라 식별자
        person_id: 선수 식별 ID (트래킹 ID)
        keypoints_2d: 2D 키포인트 좌표 (K, 2) — 픽셀
        keypoint_scores: 키포인트 신뢰도 (K,)
    """

    camera_id: str = ""
    person_id: int = -1
    keypoints_2d: NDArray[np.float32] = field(
        default_factory=lambda: np.zeros((NUM_KEYPOINTS_COCO, 2), dtype=np.float32)
    )
    keypoint_scores: NDArray[np.float32] = field(
        default_factory=lambda: np.zeros(NUM_KEYPOINTS_COCO, dtype=np.float32)
    )


# =============================================================================
# 출력: 3D 포즈
# =============================================================================
@dataclass(slots=True)
class FusedPose3D:
    """
    멀티뷰 삼각측량 3D 포즈 결과.

    Attributes:
        person_id: 선수 식별 ID
        keypoints_3d: 3D 키포인트 좌표 (K, 3) — 미터
        keypoint_confidences: 키포인트 신뢰도 (K,)
        num_views_per_keypoint: 키포인트별 관측 뷰 수 (K,)
        total_views: 관측 카메라 수
    """

    person_id: int = -1
    keypoints_3d: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros((NUM_KEYPOINTS_COCO, 3), dtype=np.float64)
    )
    keypoint_confidences: NDArray[np.float32] = field(
        default_factory=lambda: np.zeros(NUM_KEYPOINTS_COCO, dtype=np.float32)
    )
    num_views_per_keypoint: NDArray[np.int32] = field(
        default_factory=lambda: np.zeros(NUM_KEYPOINTS_COCO, dtype=np.int32)
    )
    total_views: int = 0


# =============================================================================
# 융합 결과
# =============================================================================
@dataclass(slots=True)
class PoseFusionResult:
    """
    포즈 융합 결과.

    Attributes:
        frame_index: 프레임 인덱스
        poses_3d: 선수별 3D 포즈 목록
        num_persons: 추정된 선수 수
        processing_time_ms: 처리 시간 (ms)
    """

    frame_index: int = 0
    poses_3d: list[FusedPose3D] = field(default_factory=list)
    num_persons: int = 0
    processing_time_ms: float = 0.0


# =============================================================================
# 포즈 융합 오케스트레이터
# =============================================================================
class PoseFusion:
    """
    멀티카메라 포즈 융합 오케스트레이터.

    person_id별로 2D 키포인트를 그룹핑하고,
    MultiViewTriangulator에 위임하여 3D 키포인트를 복원합니다.

    Attributes:
        _triangulator: 삼각측량기 (DI 주입)
        _min_views: 삼각측량 최소 뷰 수
        _min_confidence: 키포인트 최소 신뢰도
        _history: 융합 이력
        _total_fusions: 총 융합 횟수
        _lock: 스레드 안전 잠금
    """

    __slots__ = (
        "_triangulator",
        "_min_views",
        "_min_confidence",
        "_history",
        "_total_fusions",
        "_lock",
    )

    def __init__(
        self,
        min_views: int = 1,
        min_confidence: float = _MIN_KEYPOINT_CONFIDENCE,
    ) -> None:
        self._triangulator: MultiViewTriangulator | None = None
        self._min_views: int = min_views
        self._min_confidence: float = min_confidence
        self._history: list[PoseFusionResult] = []
        self._total_fusions: int = 0
        self._lock: RLock = RLock()

    def set_triangulator(self, triangulator: MultiViewTriangulator) -> None:
        """삼각측량기 주입."""
        self._triangulator = triangulator
        _logger.info("MultiViewTriangulator 주입 완료")

    # =========================================================================
    # 융합 실행
    # =========================================================================
    def fuse(
        self,
        camera_poses: list[CameraPoseData],
        frame_index: int = 0,
    ) -> PoseFusionResult:
        """
        멀티카메라 2D 포즈를 3D로 융합.

        Args:
            camera_poses: 카메라별 2D 포즈 목록
            frame_index: 프레임 인덱스

        Returns:
            PoseFusionResult: 3D 포즈 결과
        """
        t0 = time.perf_counter()

        # person_id별 그룹핑
        person_groups: dict[int, list[CameraPoseData]] = {}
        for pose in camera_poses:
            if pose.person_id < 0:
                continue
            person_groups.setdefault(pose.person_id, []).append(pose)

        # 선수별 3D 복원
        poses_3d: list[FusedPose3D] = []
        for person_id, group in person_groups.items():
            fused = self._fuse_person(person_id, group)
            if fused is not None:
                poses_3d.append(fused)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        result = PoseFusionResult(
            frame_index=frame_index,
            poses_3d=poses_3d,
            num_persons=len(poses_3d),
            processing_time_ms=elapsed_ms,
        )

        with self._lock:
            self._total_fusions += 1
            self._history.append(result)
            if len(self._history) > _MAX_FUSION_HISTORY:
                self._history = self._history[-_MAX_FUSION_HISTORY:]

        return result

    # =========================================================================
    # 내부: 선수 1명의 멀티뷰 3D 복원
    # =========================================================================
    def _fuse_person(
        self,
        person_id: int,
        group: list[CameraPoseData],
    ) -> FusedPose3D | None:
        """선수 1명에 대해 멀티뷰 2D→3D 복원."""
        if len(group) < self._min_views:
            return None

        num_kp = NUM_KEYPOINTS_COCO
        kp_3d = np.zeros((num_kp, 3), dtype=np.float64)
        kp_conf = np.zeros(num_kp, dtype=np.float32)
        kp_views = np.zeros(num_kp, dtype=np.int32)

        # 키포인트별로 유효한 2D 관측 수집
        for kp_idx in range(num_kp):
            valid_observations: list[tuple[str, NDArray[np.float32]]] = []

            for pose in group:
                score = float(pose.keypoint_scores[kp_idx])
                if score >= self._min_confidence:
                    valid_observations.append(
                        (pose.camera_id, pose.keypoints_2d[kp_idx])
                    )

            kp_views[kp_idx] = len(valid_observations)

            if len(valid_observations) < self._min_views:
                # 삼각측량 불가 — 가중 평균 pseudo-3D (z=0)
                if valid_observations:
                    coords = np.array(
                        [obs[1] for obs in valid_observations], dtype=np.float64
                    )
                    kp_3d[kp_idx, :2] = coords.mean(axis=0)
                    kp_conf[kp_idx] = 0.3  # 저신뢰
                continue

            # 삼각측량 가능
            if self._triangulator is not None:
                try:
                    camera_ids = [obs[0] for obs in valid_observations]
                    points_2d = np.array(
                        [obs[1] for obs in valid_observations], dtype=np.float64
                    )
                    point_3d = self._triangulator.triangulate(
                        camera_ids=camera_ids,
                        points_2d=points_2d,
                    )
                    kp_3d[kp_idx] = point_3d
                    # 신뢰도 = 뷰 수 비례
                    kp_conf[kp_idx] = min(
                        1.0, len(valid_observations) / max(self._min_views, 1)
                    )
                except Exception:
                    # 삼각측량 실패 → 가중 평균 폴백
                    coords = np.array(
                        [obs[1] for obs in valid_observations], dtype=np.float64
                    )
                    kp_3d[kp_idx, :2] = coords.mean(axis=0)
                    kp_conf[kp_idx] = 0.4
            else:
                # 삼각측량기 미주입 → 가중 평균 pseudo-3D
                coords = np.array(
                    [obs[1] for obs in valid_observations], dtype=np.float64
                )
                kp_3d[kp_idx, :2] = coords.mean(axis=0)
                kp_conf[kp_idx] = min(
                    0.7, len(valid_observations) / max(self._min_views, 1) * 0.5
                )

        return FusedPose3D(
            person_id=person_id,
            keypoints_3d=kp_3d,
            keypoint_confidences=kp_conf,
            num_views_per_keypoint=kp_views,
            total_views=len(group),
        )

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def total_fusions(self) -> int:
        """총 융합 횟수."""
        return self._total_fusions

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._history.clear()
            self._total_fusions = 0

    def __repr__(self) -> str:
        return (
            f"PoseFusion(fusions={self._total_fusions}, "
            f"min_views={self._min_views})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "CameraPoseData",
    "FusedPose3D",
    "PoseFusionResult",
    "PoseFusion",
]

__version__ = "1.0.0"
