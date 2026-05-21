# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline
파일: frame_pipeline.py
설명: 🔴 FRAME 등급 파이프라인 — 매 프레임 실행 (33ms 이내)
      - Stage1: 4종 감지 멀티뷰 융합 (detection_fusion)
      - Stage1: 포즈 추정 + 멀티뷰 3D 복원 (pose_fusion)
      - Stage1: 트래킹 갱신 + 프레임 간 글로벌 ID (tracking_fusion)
      - Stage2: ViTPose 정밀 포즈 (트리거 조건 충족 시에만)

      데이터 흐름:
        FrameBatch (8cam)
          → DetectionFusion.fuse()     → SceneFusionResult
          → PoseFusion.fuse()          → PoseFusionResult
          → TrackingFusion.fuse()      → TrackingFusionResult
          → FramePipelineResult (통합)

      시간 예산:
        - 총 33ms (30fps 기준, CadenceConfig.frame_budget_ms)
        - detection_fusion: ~15ms
        - pose_fusion: ~10ms
        - tracking_fusion: ~3ms
        - 여유: ~5ms

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/pipeline/fusion/detection_fusion.py: DetectionFusion
    - engine/pipeline/fusion/pose_fusion.py: PoseFusion
    - engine/pipeline/fusion/tracking_fusion.py: TrackingFusion
    - engine/gpu/batch_accumulator.py: FrameBatch
    - engine/config.py: CadenceConfig
    - biomechanics/kinematics/velocity_analyzer.py: calculate_all_velocities
    - biomechanics/kinematics/acceleration_analyzer.py: calculate_all_accelerations
    - biomechanics/kinematics/joint_angle_calculator.py: calculate_all_angles

소비자:
    - engine/orchestrator/cadence_scheduler.py: FRAME cadence 트리거
    - engine/pipeline/event_pipeline.py: 🟠 EVENT 이벤트 감지 입력
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING, Any, Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import CadenceConfig
from engine.pipeline.fusion.detection_fusion import (
    DetectionFusion,
    SceneFusionResult,
)
from engine.pipeline.fusion.pose_fusion import (
    CameraPoseData,
    PoseFusion,
    PoseFusionResult,
)
from engine.pipeline.fusion.tracking_fusion import (
    TrackingFusion,
    TrackingFusionResult,
)

# pose_estimation backend (포즈 백엔드 — DI 주입)
from pose_estimation.backends.base_backend import PoseBackend

# biomechanics kinematics (런타임 직접 호출)
from biomechanics.kinematics.velocity_analyzer import (
    calculate_all_velocities,
    FrameVelocities,
)
from biomechanics.kinematics.acceleration_analyzer import (
    calculate_all_accelerations,
    FrameAccelerations,
)
from biomechanics.kinematics.joint_angle_calculator import (
    calculate_all_joint_angles,
    FrameAngles,
)

# biomechanics dynamics (런타임 직접 호출)
from biomechanics.dynamics.force_estimator import (
    calculate_all_forces,
    FrameForces,
)
from biomechanics.dynamics.balance_analyzer import (
    analyze_balance,
)
from biomechanics.dynamics.energy_analyzer import (
    calculate_frame_energy,
    FrameEnergy,
)
from biomechanics.anthropometry.proportion_calculator import (
    calculate_proportions,
)
from biomechanics.anthropometry.body_segment import BodyModel, create_body_model
from biomechanics.standards.league_standards import (
    get_standard,
    get_angle_tolerance,
    BiomechanicsStandard,
)

# 포즈 후처리: 정규화 + 해부학 검증
from pose_estimation.processing import (
    filter_low_confidence,
)
from pose_estimation.validation import (
    validate_anatomical_constraints,
    ValidationLevel,
)

# 공통 타입
from shared.constants.player_constants import AgeGroup, Gender
from shared.constants.pose_constants import NUM_KEYPOINTS_COCO
from shared.interfaces.detector_interface import BoundingBox

if TYPE_CHECKING:
    from engine.gpu.batch_accumulator import FrameBatch

_logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_PIPELINE_HISTORY: Final[int] = 100


# =============================================================================
# 파이프라인 결과
# =============================================================================
@dataclass(slots=True)
class FramePipelineResult:
    """
    🔴 FRAME 파이프라인 1사이클 결과.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 프레임 타임스탬프
        detection: 4종 감지 융합 결과
        pose: 포즈 융합 결과 (None = 스킵)
        tracking: 트래킹 융합 결과 (None = 스킵)
        total_objects: 총 감지 객체 수
        total_persons_3d: 3D 복원된 선수 수
        active_tracks: 활성 글로벌 트랙 수
        processing_time_ms: 총 처리 시간 (ms)
        stage_times_ms: 단계별 처리 시간
        budget_exceeded: 시간 예산 초과 여부
    """

    frame_index: int = 0
    timestamp: float = 0.0
    detection: SceneFusionResult | None = None
    pose: PoseFusionResult | None = None
    tracking: TrackingFusionResult | None = None
    # biomechanics 결과 (person_id → 각 결과)
    biomechanics_angles: dict[int, FrameAngles] = field(default_factory=dict)
    biomechanics_velocities: dict[int, FrameVelocities] = field(default_factory=dict)
    biomechanics_accelerations: dict[int, FrameAccelerations] = field(default_factory=dict)
    # dynamics 결과 (person_id → 각 결과)
    biomechanics_forces: dict[int, FrameForces] = field(default_factory=dict)
    biomechanics_energy: dict[int, FrameEnergy] = field(default_factory=dict)
    total_objects: int = 0
    total_persons_3d: int = 0
    active_tracks: int = 0
    # Geometry 기반 멀티뷰 트래커 (영구 ID + 교체/쿼터 대응)
    # {(cam_id, det_idx): global_id} — 카메라별 감지에 할당된 전역 Player ID
    multiview_assignment: dict = field(default_factory=dict)
    multiview_active_count: int = 0
    multiview_confirmed_count: int = 0
    processing_time_ms: float = 0.0
    stage_times_ms: dict[str, float] = field(default_factory=dict)
    budget_exceeded: bool = False


# =============================================================================
# FRAME 파이프라인
# =============================================================================
class FramePipeline:
    """
    🔴 FRAME 등급 파이프라인.

    매 프레임(33ms) 실행되는 핵심 분석 루프.
    3개 fusion 모듈을 순차 호출하고 시간 예산을 모니터링합니다.

    Attributes:
        _detection_fusion: 감지 융합 오케스트레이터
        _pose_fusion: 포즈 융합 오케스트레이터
        _tracking_fusion: 트래킹 융합 오케스트레이터
        _cadence_config: Cadence 설정
        _history: 파이프라인 이력
        _total_frames: 총 처리 프레임 수
        _budget_exceeded_count: 시간 예산 초과 횟수
        _lock: 스레드 안전 잠금
    """

    __slots__ = (
        "_detection_fusion",
        "_pose_fusion",
        "_tracking_fusion",
        "_multiview_tracker",       # MultiViewPlayerTracker | None — 선수 전용 멀티뷰 통합
        "_cadence_config",
        "_pose_backends",           # list[PoseBackend] — stage1/stage2 백엔드
        "_age_group",               # AgeGroup — 경기 연령대 (유소년/청소년/성인/시니어)
        "_gender",                  # Gender — 경기 성별
        "_bio_standard",            # BiomechanicsStandard — 연령/성별 기반 기준표
        "_kp_cache",                # dict[int, NDArray] — person_id → 이전 3D 키포인트
        "_vel_cache",               # dict[int, FrameVelocities] — person_id → 이전 속도
        "_angles_cache",            # dict[int, FrameAngles] — person_id → 이전 각도
        "_last_frame_timestamp",    # float — 이전 프레임 타임스탬프 (dt 계산용)
        "_history",
        "_total_frames",
        "_budget_exceeded_count",
        "_lock",
    )

    def __init__(
        self,
        detection_fusion: DetectionFusion,
        pose_fusion: PoseFusion,
        tracking_fusion: TrackingFusion,
        cadence_config: CadenceConfig | None = None,
        pose_backends: list[PoseBackend] | None = None,
        age_group: AgeGroup = AgeGroup.ADULT,
        gender: Gender = Gender.MALE,
        multiview_tracker: Any = None,
    ) -> None:
        self._detection_fusion = detection_fusion
        self._pose_fusion = pose_fusion
        self._tracking_fusion = tracking_fusion
        self._multiview_tracker = multiview_tracker
        self._cadence_config = cadence_config or CadenceConfig()
        self._pose_backends: list[PoseBackend] = pose_backends or []
        self._age_group: AgeGroup = age_group
        self._gender: Gender = gender
        self._bio_standard: BiomechanicsStandard = get_standard(age_group, gender)
        self._kp_cache: dict[int, NDArray[np.float64]] = {}
        self._vel_cache: dict[int, FrameVelocities] = {}
        self._angles_cache: dict[int, FrameAngles] = {}
        self._last_frame_timestamp: float = 0.0
        self._history: list[FramePipelineResult] = []
        self._total_frames: int = 0
        self._budget_exceeded_count: int = 0
        self._lock: RLock = RLock()

    # =========================================================================
    # 파이프라인 실행
    # =========================================================================
    def process_frame(
        self,
        frames: dict[str, NDArray[np.uint8]],
        frame_index: int = 0,
        timestamp: float = 0.0,
    ) -> FramePipelineResult:
        """
        1프레임 분석 파이프라인 실행.

        Args:
            frames: {camera_id: frame_array} 딕셔너리
            frame_index: 프레임 인덱스
            timestamp: 프레임 타임스탬프

        Returns:
            FramePipelineResult: 통합 결과
        """
        t0 = time.perf_counter()
        stage_times: dict[str, float] = {}
        budget_ms = self._cadence_config.frame_budget_ms

        # Plan E STEP 2 (2026-05-13): 파이프라인 진입 — frame_ingestion 으로부터 수신
        try:
            from infrastructure.diagnostics.flow_logger import log_flow
            log_flow(
                "PIPE-IN",
                "frame_pipeline 수신 #%d → %d 카메라 프레임 → detection_fusion 호출",
                frame_index, len(frames),
            )
        except Exception:
            pass

        # ===== PIPE 1️⃣ 데이터 수신 (50f 주기) =====
        verbose_pipe = (frame_index % 50 == 0)
        if verbose_pipe:
            _shapes = ", ".join(
                f"{cid}={f.shape[1]}x{f.shape[0]}"
                for cid, f in frames.items()
            ) if frames else "(빈)"
            _logger.info(
                "[PIPE F#%d] 1️⃣ 데이터 수신 → %d 카메라 [%s] ts=%.3f",
                frame_index, len(frames), _shapes, timestamp,
            )

        # === Stage1: 감지 융합 ===
        t_det = time.perf_counter()
        detection_result = self._detection_fusion.fuse(
            frames, frame_index=frame_index, timestamp=timestamp,
        )
        stage_times["detection_fusion"] = (time.perf_counter() - t_det) * 1000.0
        # Plan E STEP 2 (2026-05-13): 감지 결과 흐름
        try:
            from infrastructure.diagnostics.flow_logger import log_flow as _lf
            _pr = getattr(detection_result, "player_result", None)
            _br = getattr(detection_result, "ball_result", None)
            _hr = getattr(detection_result, "hoop_result", None)
            _np = len(getattr(_pr, "fused_objects", []) or []) if _pr else 0
            _nb = len(getattr(_br, "fused_objects", []) or []) if _br else 0
            _nh = len(getattr(_hr, "fused_objects", []) or []) if _hr else 0
            _lf(
                "DET",
                "detection_fusion 결과 수신 #%d → player=%d ball=%d hoop=%d (%.1fms) → pose_fusion 호출",
                frame_index, _np, _nb, _nh, stage_times["detection_fusion"],
            )
        except Exception:
            pass
        if verbose_pipe:
            # detection_result 구조 — player/ball/hoop 카운트
            try:
                pr = getattr(detection_result, "player_result", None)
                br = getattr(detection_result, "ball_result", None)
                hr = getattr(detection_result, "hoop_result", None)
                np_ = len(getattr(pr, "fused_objects", []) or []) if pr else -1
                nb_ = len(getattr(br, "fused_objects", []) or []) if br else -1
                nh_ = len(getattr(hr, "fused_objects", []) or []) if hr else -1
                _logger.info(
                    "[PIPE F#%d] 2️⃣ detection_fusion 완료 %.1fms → "
                    "player_fused=%d ball_fused=%d hoop_fused=%d",
                    frame_index, stage_times["detection_fusion"],
                    np_, nb_, nh_,
                )
            except Exception:
                pass

        # === Stage1: 포즈 추정 (backends 실제 추론) + 멀티뷰 3D 융합 ===
        t_pose = time.perf_counter()
        camera_poses = self._run_pose_backends(frames, detection_result, frame_index)
        pose_result = self._pose_fusion.fuse(camera_poses, frame_index=frame_index)
        stage_times["pose_fusion"] = (time.perf_counter() - t_pose) * 1000.0

        # === Stage1.5: 포즈 후처리 (저신뢰 필터링 + 해부학 검증) ===
        if pose_result is not None and pose_result.poses_3d:
            valid_poses = []
            for pose_3d in pose_result.poses_3d:
                kp = pose_3d.keypoints_3d.astype(np.float32)
                # 저신뢰 키포인트 필터링
                try:
                    filtered = filter_low_confidence(
                        kp, threshold=0.3,
                    )
                    if filtered is not None:
                        kp = filtered.keypoints if hasattr(filtered, "keypoints") else kp
                except Exception:
                    pass
                # 해부학적 유효성 검증
                try:
                    validation = validate_anatomical_constraints(
                        kp, level=ValidationLevel.BASIC,
                    )
                    if validation.is_valid:
                        valid_poses.append(pose_3d)
                    else:
                        _logger.debug(
                            "포즈 해부학 검증 실패 person=%d (violations=%d)",
                            pose_3d.person_id, len(validation.violations),
                        )
                except Exception:
                    # 검증 실패해도 포즈는 유지 (데이터 손실 방지)
                    valid_poses.append(pose_3d)
            # 유효한 포즈만 사용 (전체 실패 시 원본 유지)
            if valid_poses:
                pose_result.poses_3d = valid_poses

        # === Stage1: 트래킹 융합 ===
        t_track = time.perf_counter()
        tracking_result: TrackingFusionResult | None = None
        fused_players = self._extract_players_for_tracking(detection_result)
        if fused_players:
            tracking_result = self._tracking_fusion.fuse(
                fused_players, frame_index=frame_index,
            )
        stage_times["tracking_fusion"] = (time.perf_counter() - t_track) * 1000.0

        # === Stage1: 멀티뷰 Geometry 트래커 (영구 Player ID) ===
        mv_assignment: dict = {}
        mv_active = 0
        mv_confirmed = 0
        if self._multiview_tracker is not None and detection_result is not None:
            t_mv = time.perf_counter()
            try:
                dets_per_cam = self._group_detections_by_camera(detection_result)
                if dets_per_cam:
                    mv_assignment = self._multiview_tracker.update(
                        frame_index, dets_per_cam,
                    )
                    active_tracks = self._multiview_tracker.active_tracks()
                    mv_active = len(active_tracks)
                    mv_confirmed = sum(1 for t in active_tracks if t.confirmed)
            except Exception:
                _logger.exception("MultiViewPlayerTracker.update 실패")
            stage_times["multiview_tracker"] = (time.perf_counter() - t_mv) * 1000.0

        # === Stage2: Biomechanics (3D 포즈 기반 관절 각도·속도·가속도) ===
        t_bio = time.perf_counter()
        angles_per_person: dict[int, FrameAngles] = {}
        velocities_per_person: dict[int, FrameVelocities] = {}
        accelerations_per_person: dict[int, FrameAccelerations] = {}

        if pose_result is not None and pose_result.poses_3d:
            # dt: 이전 프레임과의 경과 시간 (최소 1/60s 보정)
            dt = (
                max(timestamp - self._last_frame_timestamp, 1.0 / 60.0)
                if self._last_frame_timestamp > 0.0
                else 1.0 / 30.0
            )

            for pose_3d in pose_result.poses_3d:
                pid = pose_3d.person_id
                kp_3d = pose_3d.keypoints_3d.astype(np.float64)  # (K, 3)

                # 관절 각도
                angles: FrameAngles | None = None
                try:
                    angles = calculate_all_joint_angles(kp_3d)
                    angles_per_person[pid] = angles
                except Exception:
                    _logger.debug("관절 각도 계산 실패 person_id=%d", pid)

                # 속도 (이전 프레임 3D 키포인트 필요)
                if pid in self._kp_cache:
                    kp_prev = self._kp_cache[pid]
                    angles_prev = self._angles_cache.get(pid)
                    try:
                        velocities = calculate_all_velocities(
                            kp_prev, kp_3d, dt,
                            angles_prev=angles_prev,
                            angles_curr=angles,
                            age_group=self._age_group,
                            gender=self._gender,
                        )
                        velocities_per_person[pid] = velocities

                        # 가속도 (이전 프레임 속도 필요)
                        if pid in self._vel_cache:
                            try:
                                accelerations = calculate_all_accelerations(
                                    self._vel_cache[pid], velocities,
                                )
                                accelerations_per_person[pid] = accelerations
                            except Exception:
                                _logger.debug("가속도 계산 실패 person_id=%d", pid)

                        self._vel_cache[pid] = velocities
                    except Exception:
                        _logger.debug("속도 계산 실패 person_id=%d", pid)

                # 캐시 갱신
                self._kp_cache[pid] = kp_3d
                if angles is not None:
                    self._angles_cache[pid] = angles

        # 타임스탬프 갱신
        if timestamp > 0.0:
            self._last_frame_timestamp = timestamp
        stage_times["biomechanics_kinematics"] = (time.perf_counter() - t_bio) * 1000.0

        # === Stage3: Dynamics (힘/에너지/균형 — 가속도 기반) ===
        t_dyn = time.perf_counter()
        forces_per_person: dict[int, FrameForces] = {}
        energy_per_person: dict[int, FrameEnergy] = {}

        if pose_result is not None and pose_result.poses_3d:
            for pose_3d in pose_result.poses_3d:
                pid = pose_3d.person_id
                kp_3d = pose_3d.keypoints_3d.astype(np.float64)

                # 체형 모델 생성
                # 단일 카메라(pseudo-3D, 픽셀 좌표)일 때는 기본값 사용
                # 멀티카메라(실제 3D, 미터 좌표)일 때는 proportions 기반
                body_model: BodyModel | None = None
                try:
                    is_real_3d = pose_3d.total_views >= 2
                    if is_real_3d and kp_3d.shape[0] >= 25:
                        proportions = calculate_proportions(kp_3d)
                        est_height = proportions.estimated_height_m * 100.0
                        if 90.0 <= est_height <= 240.0:
                            body_model = create_body_model(height_cm=est_height)
                    if body_model is None:
                        body_model = create_body_model()  # 기본값 (175cm, 75kg)
                except Exception:
                    body_model = create_body_model()

                # 힘 추정 (가속도 + 체형 모델)
                if pid in accelerations_per_person:
                    try:
                        forces = calculate_all_forces(
                            body_model=body_model,
                            frame_accelerations=accelerations_per_person[pid],
                        )
                        forces_per_person[pid] = forces
                    except Exception:
                        _logger.debug("힘 추정 실패 person_id=%d", pid)

                # 에너지 분석
                if pid in velocities_per_person and body_model is not None:
                    try:
                        energy = calculate_frame_energy(
                            body_model,
                            velocities_per_person[pid],
                            kp_3d,
                        )
                        energy_per_person[pid] = energy
                    except Exception:
                        _logger.debug("에너지 분석 실패 person_id=%d", pid)

                # 균형 분석
                if body_model is not None:
                    try:
                        analyze_balance(kp_3d, body_model)
                    except Exception:
                        pass

        stage_times["biomechanics_dynamics"] = (time.perf_counter() - t_dyn) * 1000.0

        # === 결과 통합 ===
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        exceeded = elapsed_ms > budget_ms

        result = FramePipelineResult(
            frame_index=frame_index,
            timestamp=timestamp,
            detection=detection_result,
            pose=pose_result,
            tracking=tracking_result,
            biomechanics_angles=angles_per_person,
            biomechanics_velocities=velocities_per_person,
            biomechanics_accelerations=accelerations_per_person,
            biomechanics_forces=forces_per_person,
            biomechanics_energy=energy_per_person,
            total_objects=detection_result.total_fused_objects if detection_result else 0,
            total_persons_3d=pose_result.num_persons if pose_result else 0,
            active_tracks=(
                len(tracking_result.active_tracks) if tracking_result else 0
            ),
            multiview_assignment=mv_assignment,
            multiview_active_count=mv_active,
            multiview_confirmed_count=mv_confirmed,
            processing_time_ms=elapsed_ms,
            stage_times_ms=stage_times,
            budget_exceeded=exceeded,
        )

        # 이력 기록
        with self._lock:
            self._total_frames += 1
            if exceeded:
                self._budget_exceeded_count += 1
                if self._budget_exceeded_count % 10 == 1:
                    _logger.warning(
                        "FRAME 예산 초과: %.1fms > %.1fms (frame=%d, 누적=%d)",
                        elapsed_ms, budget_ms, frame_index,
                        self._budget_exceeded_count,
                    )
                # F1 진단 (2026-05-14): budget 초과 시 stage 별 소요 시간 출력 (silence-immune).
                # 어느 stage 가 병목인지 즉시 식별. 첫 5회 + 30회마다 1회 throttle.
                try:
                    from infrastructure.diagnostics.flow_logger import log_flow
                    _sorted = sorted(stage_times.items(), key=lambda kv: -kv[1])
                    _summary = " ".join(f"{k}={v:.0f}ms" for k, v in _sorted)
                    log_flow(
                        "STAGE-TIME",
                        "frame#%d total=%.0fms (>%.0fms): %s",
                        frame_index, elapsed_ms, budget_ms, _summary,
                        first_n=5, every=30,
                    )
                except Exception:
                    pass
            self._history.append(result)
            if len(self._history) > _MAX_PIPELINE_HISTORY:
                self._history = self._history[-_MAX_PIPELINE_HISTORY:]

        # ===== PIPE 3️⃣ 결과 반환 (50f 주기) =====
        if verbose_pipe:
            _logger.info(
                "[PIPE F#%d] 3️⃣ process_frame 결과 반환 → 총 %.1fms "
                "(stages=%s) %s",
                frame_index, elapsed_ms,
                {k: round(v, 1) for k, v in stage_times.items()},
                "⚠ 예산초과" if exceeded else "✓",
            )

        return result

    # =========================================================================
    # 내부: detection 결과 → tracking 입력 변환
    # =========================================================================
    def _extract_players_for_tracking(
        self, detection: SceneFusionResult,
    ) -> list[dict[str, float]]:
        """SceneFusionResult에서 선수 bbox + team_id 추출 → TrackingFusion 입력."""
        if detection is None or detection.player_result is None:
            return []

        # TeamAwareTracker 결과 (TeamTrackResult 목록)
        team_results = []
        if self._detection_fusion is not None:
            team_results = getattr(self._detection_fusion, "team_track_results", []) or []

        # TeamTrackResult → 중심점 기반 매핑 준비
        # TeamTrackResult.track: _TrackState (bbox_x, bbox_y, bbox_w, bbox_h)
        # TeamTrackResult.team: Team enum (TEAM_A, TEAM_B, UNKNOWN)
        team_centers: list[tuple[float, float, str]] = []
        for tr in team_results:
            t = getattr(tr, "track", None)
            if t is None:
                continue
            cx = getattr(t, "bbox_x", 0.0) + getattr(t, "bbox_w", 0.0) / 2
            cy = getattr(t, "bbox_y", 0.0) + getattr(t, "bbox_h", 0.0) / 2
            team_enum = getattr(tr, "team", None)
            team_id = team_enum.value if team_enum is not None else ""
            team_centers.append((cx, cy, team_id))

        players: list[dict[str, Any]] = []
        for obj in detection.player_result.fused_objects:
            if obj.bbox is None:
                continue
            bbox = obj.bbox
            ox = float(bbox.x + bbox.width / 2)
            oy = float(bbox.y + bbox.height / 2)
            entry: dict[str, Any] = {
                "x1": float(bbox.x),
                "y1": float(bbox.y),
                "x2": float(bbox.x + bbox.width),
                "y2": float(bbox.y + bbox.height),
            }
            # 가장 가까운 TeamTrackResult 매칭 (중심점 거리)
            best_dist = 999999.0
            best_team = ""
            for tcx, tcy, tid in team_centers:
                d = (ox - tcx) ** 2 + (oy - tcy) ** 2
                if d < best_dist:
                    best_dist = d
                    best_team = tid
            if best_dist < 10000 and best_team:  # 100px 이내 매칭
                entry["team_id"] = best_team
            players.append(entry)
        return players

    # =========================================================================
    # 내부: detection 결과 → MultiViewPlayerTracker 입력 변환
    # =========================================================================
    def _group_detections_by_camera(
        self, detection: SceneFusionResult,
    ) -> dict:
        """SceneFusionResult.player_result → {cam_id: list[CameraDetection]}.

        `DetectedObject.attributes`에서 camera_id/team/jersey_number를 읽어
        `CameraDetection` 구조체로 변환. 카메라별로 그룹화.
        """
        from detection.player_detection.multiview_tracker import CameraDetection

        if detection is None or detection.player_result is None:
            return {}

        result: dict[int, list] = {}
        for det_idx, obj in enumerate(detection.player_result.fused_objects):
            if obj.bbox is None:
                continue
            attrs = obj.attributes or {}
            cam_id_raw = attrs.get("camera_id")
            if cam_id_raw is None:
                continue
            # "cam_0" / "cam0" / "1" / int 등 다양한 포맷 → int
            try:
                if isinstance(cam_id_raw, int):
                    cam_id = cam_id_raw
                else:
                    s = str(cam_id_raw).replace("cam_", "").replace("cam", "")
                    cam_id = int(s)
            except (ValueError, TypeError):
                continue

            bbox = obj.bbox
            x1 = int(bbox.x)
            y1 = int(bbox.y)
            x2 = int(bbox.x + bbox.width)
            y2 = int(bbox.y + bbox.height)

            cam_det = CameraDetection(
                cam_id=cam_id,
                bbox=(x1, y1, x2, y2),
                jersey_number=attrs.get("jersey_number"),
                jersey_conf=float(attrs.get("jersey_conf", 0.0)),
                team=attrs.get("team"),
                team_conf=float(attrs.get("team_confidence", 0.0)),
                yolo_conf=float(obj.confidence),
            )
            result.setdefault(cam_id, []).append(cam_det)
        return result

    # =========================================================================
    # 내부: 포즈 backends 추론 → CameraPoseData 변환
    # =========================================================================
    def _run_pose_backends(
        self,
        frames: dict[str, NDArray[np.uint8]],
        detection: SceneFusionResult | None,
        frame_index: int,
    ) -> list[CameraPoseData]:
        """
        pose backends(YOLOv8-Pose / ViTPose)로 각 카메라 프레임 추론.

        Stage1 backend(index 0)를 기본으로 사용.
        detection에서 카메라별 선수 bbox를 추출해 top-down 추론 수행.

        Returns:
            list[CameraPoseData]: 멀티뷰 2D 포즈 (3D 융합 입력)
        """
        if not self._pose_backends:
            return []

        # Stage1 백엔드만 매 프레임 사용 (Stage2는 별도 트리거)
        backend = self._pose_backends[0]
        if not backend.is_loaded:
            return []

        camera_poses: list[CameraPoseData] = []

        for cam_id, frame_array in frames.items():
            # YOLOv8-Pose: full-image 1회 추론 (자체 감지 + 포즈 동시 처리)
            # top-down per-object crop 방식은 85회 개별 GPU 추론 → 성능 병목
            # bottom-up full-image 방식: 카메라당 1회 추론으로 모든 선수 포즈 동시 추출
            try:
                # infer(frame, person_boxes=None) → YOLO 자체 감지 모드 사용
                keypoints_list = backend.infer(frame_array, None)
            except Exception:
                _logger.debug("포즈 추론 실패 cam=%s frame=%d", cam_id, frame_index)
                continue

            for person_idx, kp_array in enumerate(keypoints_list):
                if kp_array is None or kp_array.ndim != 2:
                    continue
                # (K, 3) → 2D 좌표 + 점수 분리
                k = min(kp_array.shape[0], NUM_KEYPOINTS_COCO)
                kp_2d = np.zeros((NUM_KEYPOINTS_COCO, 2), dtype=np.float32)
                scores = np.zeros(NUM_KEYPOINTS_COCO, dtype=np.float32)
                kp_2d[:k] = kp_array[:k, :2].astype(np.float32)
                if kp_array.shape[1] >= 3:
                    scores[:k] = kp_array[:k, 2].astype(np.float32)
                else:
                    scores[:k] = 1.0

                camera_poses.append(CameraPoseData(
                    camera_id=cam_id,
                    person_id=person_idx,   # 트래킹 연동 전 임시 인덱스
                    keypoints_2d=kp_2d,
                    keypoint_scores=scores,
                ))

        return camera_poses

    # =========================================================================
    # 내부: 카메라별 선수 BoundingBox 추출
    # =========================================================================
    def _extract_bboxes_for_camera(
        self,
        detection: SceneFusionResult | None,
        cam_id: str,
    ) -> list[BoundingBox]:
        """해당 카메라의 선수 BoundingBox 목록 반환."""
        if detection is None or detection.player_result is None:
            return []

        # 1. view_results에서 카메라별 결과 조회 (멀티뷰 개별 모드)
        view = detection.player_result.view_results.get(cam_id)
        if view is not None and hasattr(view, "objects") and view.objects:
            return [
                obj.bbox
                for obj in view.objects
                if obj.bbox is not None and getattr(obj, "is_person_type", True)
            ]

        # 2. fused_objects에서 추출 (CV-BBox 통합 모드 — view_results 비어있음)
        # 카메라 ID 필터 또는 전체 반환
        results = []
        for obj in detection.player_result.fused_objects:
            bbox = getattr(obj, "bbox", None)
            if bbox is None:
                continue
            # camera_id가 있으면 해당 카메라만, 없으면 전체
            obj_cam = getattr(obj, "camera_id", None)
            if obj_cam is not None and obj_cam != cam_id:
                continue
            results.append(bbox)

        return results

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def total_frames(self) -> int:
        """총 처리 프레임 수."""
        return self._total_frames

    @property
    def budget_exceeded_count(self) -> int:
        """시간 예산 초과 횟수."""
        return self._budget_exceeded_count

    @property
    def budget_exceeded_ratio(self) -> float:
        """시간 예산 초과 비율 (0.0~1.0)."""
        if self._total_frames == 0:
            return 0.0
        return self._budget_exceeded_count / self._total_frames

    @property
    def avg_processing_time_ms(self) -> float:
        """평균 처리 시간 (ms)."""
        with self._lock:
            if not self._history:
                return 0.0
            return sum(r.processing_time_ms for r in self._history) / len(self._history)

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._history.clear()
            self._total_frames = 0
            self._budget_exceeded_count = 0
        self._kp_cache.clear()
        self._vel_cache.clear()
        self._angles_cache.clear()
        self._last_frame_timestamp = 0.0
        self._detection_fusion.reset()
        self._pose_fusion.reset()
        self._tracking_fusion.reset()
        _logger.info("FramePipeline 초기화 완료")

    def __repr__(self) -> str:
        return (
            f"FramePipeline(frames={self._total_frames}, "
            f"avg_ms={self.avg_processing_time_ms:.1f}, "
            f"exceeded={self._budget_exceeded_count})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "FramePipelineResult",
    "FramePipeline",
]

__version__ = "1.0.0"
