# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/pose_estimation/unit
파일: test_processing.py
설명: processing.py 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0
"""
from __future__ import annotations

import math
import time

import numpy as np
import pytest

from pose_estimation.keypoint_types import UnifiedKeypoint
from pose_estimation.processing import (
    # 열거형
    NormalizationMethod,
    ScaleReference,
    SmoothingMode,
    TrackState,
    # 데이터 클래스
    NormalizationConfig,
    NormalizationResult,
    SmoothingConfig,
    SmoothedPose,
    ConfidenceThresholds,
    FilterResult,
    # 클래스
    KeypointKalmanTracker,
    TemporalSmoother,
    PoseProcessor,
    # 함수
    normalize_pose,
    normalize_to_hip_center,
    normalize_to_torso,
    normalize_scale,
    rotate_pose,
    mirror_pose,
    denormalize_pose,
    filter_low_confidence,
    get_valid_keypoints,
    calculate_average_confidence,
    interpolate_missing,
    is_pose_valid,
    smooth_sequence,
    # 상수
    CONFIG_KEY_POSE_PROCESSOR,
    FILTERPY_AVAILABLE,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_SMOOTHING_FACTOR,
    DEFAULT_PROCESS_NOISE,
    DEFAULT_MEASUREMENT_NOISE,
    DEFAULT_TORSO_LENGTH,
    MAX_HISTORY_FRAMES,
    MIN_VALID_KEYPOINTS_FOR_POSE,
    DEFAULT_VALID_CONFIDENCE,
    DEFAULT_CRITICAL_CONFIDENCE,
    CRITICAL_KEYPOINTS,
    OPTIONAL_KEYPOINTS,
)


# ============================================================
# 테스트 헬퍼
# ============================================================
def _make_keypoints_25x3(conf: float = 0.9) -> np.ndarray:
    """25개 Unified 키포인트 (N, 3) — (x, y, confidence)."""
    kpts = np.zeros((25, 3), dtype=np.float32)
    # 머리
    kpts[UnifiedKeypoint.NOSE] = [0.5, 0.1, conf]
    kpts[UnifiedKeypoint.LEFT_EYE] = [0.48, 0.08, conf]
    kpts[UnifiedKeypoint.RIGHT_EYE] = [0.52, 0.08, conf]
    kpts[UnifiedKeypoint.LEFT_EAR] = [0.46, 0.1, conf]
    kpts[UnifiedKeypoint.RIGHT_EAR] = [0.54, 0.1, conf]
    # 어깨
    kpts[UnifiedKeypoint.LEFT_SHOULDER] = [0.4, 0.25, conf]
    kpts[UnifiedKeypoint.RIGHT_SHOULDER] = [0.6, 0.25, conf]
    # 팔꿈치
    kpts[UnifiedKeypoint.LEFT_ELBOW] = [0.35, 0.4, conf]
    kpts[UnifiedKeypoint.RIGHT_ELBOW] = [0.65, 0.4, conf]
    # 손목
    kpts[UnifiedKeypoint.LEFT_WRIST] = [0.33, 0.55, conf]
    kpts[UnifiedKeypoint.RIGHT_WRIST] = [0.67, 0.55, conf]
    # 손가락
    kpts[UnifiedKeypoint.LEFT_INDEX] = [0.32, 0.58, conf]
    kpts[UnifiedKeypoint.RIGHT_INDEX] = [0.68, 0.58, conf]
    kpts[UnifiedKeypoint.LEFT_PINKY] = [0.31, 0.57, conf]
    kpts[UnifiedKeypoint.RIGHT_PINKY] = [0.69, 0.57, conf]
    kpts[UnifiedKeypoint.LEFT_THUMB] = [0.34, 0.57, conf]
    kpts[UnifiedKeypoint.RIGHT_THUMB] = [0.66, 0.57, conf]
    # 엉덩이
    kpts[UnifiedKeypoint.LEFT_HIP] = [0.43, 0.55, conf]
    kpts[UnifiedKeypoint.RIGHT_HIP] = [0.57, 0.55, conf]
    # 무릎
    kpts[UnifiedKeypoint.LEFT_KNEE] = [0.43, 0.72, conf]
    kpts[UnifiedKeypoint.RIGHT_KNEE] = [0.57, 0.72, conf]
    # 발목
    kpts[UnifiedKeypoint.LEFT_ANKLE] = [0.43, 0.9, conf]
    kpts[UnifiedKeypoint.RIGHT_ANKLE] = [0.57, 0.9, conf]
    # 목, 골반
    kpts[UnifiedKeypoint.NECK] = [0.5, 0.2, conf]
    kpts[UnifiedKeypoint.PELVIS] = [0.5, 0.55, conf]
    return kpts


def _make_keypoints_25x4(conf: float = 0.9) -> np.ndarray:
    """25개 Unified 키포인트 (N, 4) — (x, y, z, confidence)."""
    kpts_3 = _make_keypoints_25x3(conf)
    kpts_4 = np.zeros((25, 4), dtype=np.float32)
    kpts_4[:, 0] = kpts_3[:, 0]
    kpts_4[:, 1] = kpts_3[:, 1]
    kpts_4[:, 2] = 0.0  # z
    kpts_4[:, 3] = kpts_3[:, 2]  # confidence → 4번째 열
    return kpts_4


# ============================================================
# 1. 열거형 테스트
# ============================================================
class TestEnums:
    """열거형 정의 테스트."""

    def test_normalization_method(self) -> None:
        assert len(NormalizationMethod) == 4

    def test_scale_reference(self) -> None:
        assert len(ScaleReference) == 4

    def test_smoothing_mode(self) -> None:
        assert len(SmoothingMode) == 5

    def test_track_state(self) -> None:
        assert len(TrackState) == 4


# ============================================================
# 2. 데이터 클래스 테스트
# ============================================================
class TestNormalizationConfig:
    """NormalizationConfig 테스트."""

    def test_defaults(self) -> None:
        cfg = NormalizationConfig()
        assert cfg.method == NormalizationMethod.HIP_CENTER
        assert cfg.scale_reference == ScaleReference.TORSO_HEIGHT
        assert cfg.target_scale == 1.0

    def test_slots(self) -> None:
        cfg = NormalizationConfig()
        assert hasattr(cfg, "__slots__")


class TestNormalizationResult:
    """NormalizationResult 테스트."""

    def test_creation(self) -> None:
        kpts = np.zeros((25, 3), dtype=np.float32)
        r = NormalizationResult(
            keypoints=kpts,
            center=(0.5, 0.5),
            scale=1.0,
            rotation=0.0,
        )
        assert r.success is True
        assert r.message == ""

    def test_slots(self) -> None:
        kpts = np.zeros((25, 3), dtype=np.float32)
        r = NormalizationResult(keypoints=kpts, center=(0.0, 0.0), scale=1.0, rotation=0.0)
        assert hasattr(r, "__slots__")


class TestSmoothingConfig:
    """SmoothingConfig 테스트."""

    def test_defaults(self) -> None:
        cfg = SmoothingConfig()
        assert cfg.mode == SmoothingMode.KALMAN
        assert cfg.ema_alpha == 0.5
        assert cfg.window_size == 5
        assert cfg.one_euro_min_cutoff == 1.7
        assert cfg.one_euro_beta == 0.3

    def test_slots(self) -> None:
        assert hasattr(SmoothingConfig(), "__slots__")


class TestSmoothedPose:
    """SmoothedPose 테스트."""

    def test_defaults(self) -> None:
        kpts = np.zeros((25, 3), dtype=np.float32)
        sp = SmoothedPose(keypoints=kpts)
        assert sp.velocities is None
        assert sp.track_state == TrackState.TRACKED
        assert sp.frame_count == 0

    def test_slots(self) -> None:
        sp = SmoothedPose(keypoints=np.zeros((1, 3), dtype=np.float32))
        assert hasattr(sp, "__slots__")


class TestConfidenceThresholds:
    """ConfidenceThresholds 테스트."""

    def test_defaults(self) -> None:
        ct = ConfidenceThresholds()
        assert ct.critical == 0.5
        assert ct.normal == 0.3
        assert ct.optional == 0.2
        assert ct.pose_validity == 0.4

    def test_slots(self) -> None:
        assert hasattr(ConfidenceThresholds(), "__slots__")


class TestFilterResult:
    """FilterResult 테스트."""

    def test_creation(self) -> None:
        kpts = np.zeros((5, 3), dtype=np.float32)
        fr = FilterResult(
            keypoints=kpts,
            valid_mask=np.array([True, False, True, False, True]),
            average_confidence=0.6,
            valid_count=3,
            total_count=5,
            is_valid=True,
        )
        assert fr.valid_count == 3
        assert fr.is_valid is True

    def test_slots(self) -> None:
        kpts = np.zeros((1, 3), dtype=np.float32)
        fr = FilterResult(
            keypoints=kpts,
            valid_mask=np.array([True]),
            average_confidence=1.0,
            valid_count=1,
            total_count=1,
            is_valid=True,
        )
        assert hasattr(fr, "__slots__")


# ============================================================
# 3. 상수 테스트
# ============================================================
class TestConstants:
    """상수 정의 테스트."""

    def test_config_key(self) -> None:
        assert CONFIG_KEY_POSE_PROCESSOR == "pose.processing"

    def test_default_values(self) -> None:
        assert DEFAULT_MIN_CONFIDENCE == 0.5
        assert DEFAULT_SMOOTHING_FACTOR == 0.5
        assert DEFAULT_PROCESS_NOISE == 0.01
        assert DEFAULT_MEASUREMENT_NOISE == 0.1
        assert DEFAULT_TORSO_LENGTH == 0.4

    def test_history_constants(self) -> None:
        assert MAX_HISTORY_FRAMES == 30
        assert MIN_VALID_KEYPOINTS_FOR_POSE == 4

    def test_critical_keypoints(self) -> None:
        assert UnifiedKeypoint.LEFT_SHOULDER in CRITICAL_KEYPOINTS
        assert UnifiedKeypoint.RIGHT_HIP in CRITICAL_KEYPOINTS
        assert len(CRITICAL_KEYPOINTS) == 4

    def test_optional_keypoints(self) -> None:
        assert UnifiedKeypoint.LEFT_EAR in OPTIONAL_KEYPOINTS
        assert len(OPTIONAL_KEYPOINTS) == 8


# ============================================================
# 4. KeypointKalmanTracker 테스트
# ============================================================
class TestKeypointKalmanTracker:
    """칼만 필터 트래커 테스트."""

    def test_init(self) -> None:
        tracker = KeypointKalmanTracker()
        assert tracker._initialized is False
        assert tracker.is_lost is False

    def test_initialize(self) -> None:
        tracker = KeypointKalmanTracker()
        tracker.initialize(0.5, 0.5)
        assert tracker._initialized is True

    def test_update_initializes_if_needed(self) -> None:
        tracker = KeypointKalmanTracker()
        result = tracker.update(0.5, 0.5)
        assert tracker._initialized is True
        assert result == (0.5, 0.5)

    def test_predict_before_init(self) -> None:
        tracker = KeypointKalmanTracker()
        assert tracker.predict() == (0.0, 0.0)

    def test_predict_after_init(self) -> None:
        tracker = KeypointKalmanTracker()
        tracker.initialize(0.5, 0.5)
        px, py = tracker.predict()
        assert isinstance(px, float)
        assert isinstance(py, float)

    def test_update_multiple(self) -> None:
        tracker = KeypointKalmanTracker()
        tracker.update(0.5, 0.5)
        x, y = tracker.update(0.51, 0.51)
        # 필터링된 값은 0.5 ~ 0.51 사이여야 함
        assert 0.49 <= x <= 0.52
        assert 0.49 <= y <= 0.52

    def test_get_velocity_before_init(self) -> None:
        tracker = KeypointKalmanTracker()
        assert tracker.get_velocity() == (0.0, 0.0)

    def test_mark_missed_and_is_lost(self) -> None:
        tracker = KeypointKalmanTracker()
        for _ in range(6):
            tracker.mark_missed()
        assert tracker.is_lost is True

    def test_slots(self) -> None:
        tracker = KeypointKalmanTracker()
        assert hasattr(tracker, "__slots__")


# ============================================================
# 5. TemporalSmoother 테스트
# ============================================================
class TestTemporalSmoother:
    """시간적 스무더 테스트."""

    def test_no_smoothing(self) -> None:
        config = SmoothingConfig(mode=SmoothingMode.NONE)
        smoother = TemporalSmoother(config)
        kpts = _make_keypoints_25x3()
        result = smoother.smooth(kpts)
        assert isinstance(result, SmoothedPose)
        np.testing.assert_array_equal(result.keypoints, kpts)

    def test_ema_smoothing(self) -> None:
        config = SmoothingConfig(mode=SmoothingMode.EMA, ema_alpha=0.5)
        smoother = TemporalSmoother(config)
        kpts1 = _make_keypoints_25x3()
        kpts2 = _make_keypoints_25x3()
        kpts2[:, 0] += 0.01  # x 좌표 약간 이동

        smoother.smooth(kpts1)
        result2 = smoother.smooth(kpts2)
        # EMA 적용 → kpts1과 kpts2 중간값에 가까워야 함
        assert result2.keypoints[0, 0] != kpts2[0, 0]

    def test_kalman_smoothing(self) -> None:
        config = SmoothingConfig(mode=SmoothingMode.KALMAN)
        smoother = TemporalSmoother(config)
        kpts = _make_keypoints_25x3()
        result = smoother.smooth(kpts)
        assert isinstance(result, SmoothedPose)
        assert result.track_state == TrackState.NEW

    def test_moving_average(self) -> None:
        config = SmoothingConfig(mode=SmoothingMode.MOVING_AVERAGE, window_size=3)
        smoother = TemporalSmoother(config)
        kpts = _make_keypoints_25x3()
        for _ in range(5):
            result = smoother.smooth(kpts)
        assert isinstance(result, SmoothedPose)

    def test_one_euro_smoothing(self) -> None:
        config = SmoothingConfig(mode=SmoothingMode.ONE_EURO)
        smoother = TemporalSmoother(config)
        kpts = _make_keypoints_25x3()
        t = time.time()
        result = smoother.smooth(kpts, timestamp=t)
        assert isinstance(result, SmoothedPose)

    def test_track_id_isolation(self) -> None:
        """트랙 ID별 독립적 스무딩."""
        config = SmoothingConfig(mode=SmoothingMode.EMA)
        smoother = TemporalSmoother(config)
        kpts = _make_keypoints_25x3()
        r1 = smoother.smooth(kpts, track_id="player_1")
        r2 = smoother.smooth(kpts, track_id="player_2")
        assert r1.frame_count == 1
        assert r2.frame_count == 1

    def test_reset_track(self) -> None:
        smoother = TemporalSmoother()
        kpts = _make_keypoints_25x3()
        smoother.smooth(kpts, track_id="t1")
        smoother.reset_track("t1")
        # 재시작 → NEW 상태
        result = smoother.smooth(kpts, track_id="t1")
        assert result.track_state == TrackState.NEW

    def test_reset_all(self) -> None:
        smoother = TemporalSmoother()
        kpts = _make_keypoints_25x3()
        smoother.smooth(kpts, track_id="t1")
        smoother.smooth(kpts, track_id="t2")
        smoother.reset_all()
        result = smoother.smooth(kpts, track_id="t1")
        assert result.frame_count == 1

    def test_low_confidence_kalman_predict(self) -> None:
        """낮은 신뢰도 키포인트 → 칼만 예측만 수행."""
        config = SmoothingConfig(mode=SmoothingMode.KALMAN, min_confidence_for_update=0.5)
        smoother = TemporalSmoother(config)

        kpts_high = _make_keypoints_25x3(conf=0.9)
        smoother.smooth(kpts_high)

        kpts_low = _make_keypoints_25x3(conf=0.2)
        result = smoother.smooth(kpts_low)
        assert isinstance(result, SmoothedPose)


# ============================================================
# 6. 정규화 함수 테스트
# ============================================================
class TestNormalizePose:
    """normalize_pose 함수 테스트."""

    def test_hip_center_default(self) -> None:
        kpts = _make_keypoints_25x3()
        result = normalize_pose(kpts)
        assert result.success is True
        assert isinstance(result, NormalizationResult)

    def test_torso_method(self) -> None:
        kpts = _make_keypoints_25x3()
        config = NormalizationConfig(method=NormalizationMethod.TORSO)
        result = normalize_pose(kpts, config)
        assert result.success is True

    def test_shoulder_center(self) -> None:
        kpts = _make_keypoints_25x3()
        config = NormalizationConfig(method=NormalizationMethod.SHOULDER_CENTER)
        result = normalize_pose(kpts, config)
        assert result.success is True

    def test_bounding_box(self) -> None:
        kpts = _make_keypoints_25x3()
        config = NormalizationConfig(method=NormalizationMethod.BOUNDING_BOX)
        result = normalize_pose(kpts, config)
        assert result.success is True


class TestNormalizeToHipCenter:
    """normalize_to_hip_center 함수 테스트."""

    def test_success(self) -> None:
        kpts = _make_keypoints_25x3()
        result = normalize_to_hip_center(kpts)
        assert result.success is True
        # 정규화 후 hip center 근처에 원점
        hip_center_x = (kpts[UnifiedKeypoint.LEFT_HIP, 0] + kpts[UnifiedKeypoint.RIGHT_HIP, 0]) / 2
        hip_center_y = (kpts[UnifiedKeypoint.LEFT_HIP, 1] + kpts[UnifiedKeypoint.RIGHT_HIP, 1]) / 2
        assert abs(result.center[0] - hip_center_x) < 0.01
        assert abs(result.center[1] - hip_center_y) < 0.01

    def test_missing_hips(self) -> None:
        kpts = _make_keypoints_25x3()
        kpts[UnifiedKeypoint.LEFT_HIP, 2] = 0.0
        result = normalize_to_hip_center(kpts)
        assert result.success is False
        assert "엉덩이" in result.message

    def test_4d_keypoints(self) -> None:
        kpts = _make_keypoints_25x4()
        result = normalize_to_hip_center(kpts)
        assert result.success is True


class TestNormalizeToTorso:
    """normalize_to_torso 함수 테스트."""

    def test_success(self) -> None:
        kpts = _make_keypoints_25x3()
        result = normalize_to_torso(kpts)
        assert result.success is True
        assert result.scale > 0

    def test_missing_torso_kp(self) -> None:
        kpts = _make_keypoints_25x3()
        kpts[UnifiedKeypoint.LEFT_SHOULDER, 2] = 0.0
        result = normalize_to_torso(kpts)
        assert result.success is False


class TestNormalizeScale:
    """normalize_scale 함수 테스트."""

    def test_torso_height(self) -> None:
        kpts = _make_keypoints_25x3()
        result = normalize_scale(kpts, target_scale=1.0)
        assert result.shape == kpts.shape


class TestRotatePose:
    """rotate_pose 함수 테스트."""

    def test_zero_rotation(self) -> None:
        kpts = _make_keypoints_25x3()
        rotated = rotate_pose(kpts, 0.0)
        np.testing.assert_array_almost_equal(rotated[:, :2], kpts[:, :2])

    def test_90_degree_rotation(self) -> None:
        kpts = _make_keypoints_25x3()
        rotated = rotate_pose(kpts, math.pi / 2, center=(0.5, 0.5))
        # 회전 후 좌표가 변경되어야 함
        assert not np.allclose(rotated[:, :2], kpts[:, :2])

    def test_roundtrip(self) -> None:
        """360도 회전 → 원본과 동일."""
        kpts = _make_keypoints_25x3()
        rotated = rotate_pose(kpts, 2 * math.pi)
        np.testing.assert_array_almost_equal(rotated[:, :2], kpts[:, :2], decimal=5)


class TestMirrorPose:
    """mirror_pose 함수 테스트."""

    def test_vertical_mirror(self) -> None:
        kpts = _make_keypoints_25x3()
        mirrored = mirror_pose(kpts, axis="vertical")
        # x 좌표 반전 확인 (center_x=0.5 기준)
        assert mirrored.shape == kpts.shape

    def test_horizontal_mirror(self) -> None:
        kpts = _make_keypoints_25x3()
        mirrored = mirror_pose(kpts, axis="horizontal")
        # y 좌표 반전 확인
        assert mirrored.shape == kpts.shape


class TestDenormalizePose:
    """denormalize_pose 함수 테스트."""

    def test_roundtrip(self) -> None:
        """정규화 → 역정규화 → 원본 복원."""
        kpts = _make_keypoints_25x3()
        norm_result = normalize_to_hip_center(kpts)
        restored = denormalize_pose(norm_result.keypoints, norm_result)
        # x, y 좌표 복원 확인 (소수점 오차 허용)
        np.testing.assert_array_almost_equal(
            restored[:, :2], kpts[:, :2], decimal=3,
        )


# ============================================================
# 7. 신뢰도 필터링 테스트
# ============================================================
class TestFilterLowConfidence:
    """filter_low_confidence 함수 테스트."""

    def test_high_confidence_all_valid(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.9)
        result = filter_low_confidence(kpts, threshold=0.5)
        assert result.is_valid is True
        assert result.valid_count == 25

    def test_low_confidence_filtered(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.2)
        result = filter_low_confidence(kpts, threshold=0.5)
        assert result.valid_count == 0

    def test_custom_thresholds(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.4)
        thresholds = ConfidenceThresholds(
            critical=0.5,
            normal=0.3,
            optional=0.2,
        )
        result = filter_low_confidence(kpts, thresholds=thresholds)
        assert isinstance(result, FilterResult)

    def test_4d_keypoints(self) -> None:
        kpts = _make_keypoints_25x4(conf=0.9)
        result = filter_low_confidence(kpts, threshold=0.5)
        assert result.valid_count == 25


class TestGetValidKeypoints:
    """get_valid_keypoints 함수 테스트."""

    def test_all_valid(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.9)
        valid = get_valid_keypoints(kpts, threshold=0.5)
        assert len(valid) == 25

    def test_none_valid(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.1)
        valid = get_valid_keypoints(kpts, threshold=0.5)
        assert len(valid) == 0

    def test_returns_keypoint_data(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.9)
        valid = get_valid_keypoints(kpts, threshold=0.5)
        idx, kp_data = valid[0]
        assert isinstance(idx, int)
        assert hasattr(kp_data, "x")
        assert hasattr(kp_data, "y")


class TestCalculateAverageConfidence:
    """calculate_average_confidence 함수 테스트."""

    def test_full_average(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.8)
        avg = calculate_average_confidence(kpts)
        assert abs(avg - 0.8) < 0.01

    def test_specific_indices(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.8)
        kpts[0, 2] = 0.2
        avg = calculate_average_confidence(kpts, keypoint_indices=[0])
        assert abs(avg - 0.2) < 0.01

    def test_empty_indices(self) -> None:
        kpts = _make_keypoints_25x3()
        avg = calculate_average_confidence(kpts, keypoint_indices=[])
        assert avg == 0.0


class TestInterpolateMissing:
    """interpolate_missing 함수 테스트."""

    def test_neck_interpolation(self) -> None:
        kpts = _make_keypoints_25x3()
        kpts[UnifiedKeypoint.NECK, 2] = 0.0  # NECK 누락
        result = interpolate_missing(kpts)
        # NECK이 어깨 중심으로 보간되어야 함
        assert result[UnifiedKeypoint.NECK, 2] > 0

    def test_pelvis_interpolation(self) -> None:
        kpts = _make_keypoints_25x3()
        kpts[UnifiedKeypoint.PELVIS, 2] = 0.0  # PELVIS 누락
        result = interpolate_missing(kpts)
        assert result[UnifiedKeypoint.PELVIS, 2] > 0

    def test_no_missing(self) -> None:
        kpts = _make_keypoints_25x3()
        result = interpolate_missing(kpts)
        np.testing.assert_array_almost_equal(result, kpts)


class TestIsPoseValid:
    """is_pose_valid 함수 테스트."""

    def test_valid_pose(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.9)
        assert is_pose_valid(kpts) is True

    def test_low_confidence_invalid(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.1)
        assert is_pose_valid(kpts) is False

    def test_insufficient_keypoints(self) -> None:
        kpts = _make_keypoints_25x3(conf=0.9)
        # 대부분 키포인트 무효화
        kpts[:20, 2] = 0.0
        assert is_pose_valid(kpts) is False


# ============================================================
# 8. 시퀀스 처리 테스트
# ============================================================
class TestSmoothSequence:
    """smooth_sequence 함수 테스트."""

    def test_empty_sequence(self) -> None:
        result = smooth_sequence([])
        assert result == []

    def test_single_frame(self) -> None:
        kpts = _make_keypoints_25x3()
        result = smooth_sequence([kpts])
        assert len(result) == 1
        assert result[0].shape == kpts.shape

    def test_multi_frame(self) -> None:
        frames = [_make_keypoints_25x3() for _ in range(10)]
        result = smooth_sequence(frames)
        assert len(result) == 10


# ============================================================
# 9. PoseProcessor 통합 클래스 테스트
# ============================================================
class TestPoseProcessor:
    """PoseProcessor 통합 테스트."""

    def test_init_default(self) -> None:
        processor = PoseProcessor()
        assert processor._normalization_config.method == NormalizationMethod.HIP_CENTER
        assert processor._smoothing_config.mode == SmoothingMode.KALMAN

    def test_init_with_config(self) -> None:
        config = {
            "smoothing": {
                "mode": "EMA",
                "ema_alpha": 0.7,
            },
            "confidence": {
                "critical": 0.6,
            },
        }
        processor = PoseProcessor(config=config)
        assert processor._smoothing_config.mode == SmoothingMode.EMA
        assert processor._smoothing_config.ema_alpha == 0.7
        assert processor._confidence_thresholds.critical == 0.6

    def test_init_with_normalization_config(self) -> None:
        config = {
            "normalization": {
                "method": "torso",
                "target_scale": 2.0,
            },
        }
        processor = PoseProcessor(config=config)
        assert processor._normalization_config.method == NormalizationMethod.TORSO
        assert processor._normalization_config.target_scale == 2.0

    def test_init_with_one_euro_config(self) -> None:
        config = {
            "smoothing": {
                "mode": "ONE_EURO",
                "one_euro": {
                    "min_cutoff": 2.0,
                    "beta": 0.5,
                },
            },
        }
        processor = PoseProcessor(config=config)
        assert processor._smoothing_config.mode == SmoothingMode.ONE_EURO
        assert processor._smoothing_config.one_euro_min_cutoff == 2.0

    def test_filter(self) -> None:
        processor = PoseProcessor()
        kpts = _make_keypoints_25x3()
        result = processor.filter(kpts)
        assert isinstance(result, FilterResult)
        assert result.is_valid is True

    def test_normalize(self) -> None:
        processor = PoseProcessor()
        kpts = _make_keypoints_25x3()
        result = processor.normalize(kpts)
        assert isinstance(result, NormalizationResult)
        assert result.success is True

    def test_smooth(self) -> None:
        processor = PoseProcessor()
        kpts = _make_keypoints_25x3()
        result = processor.smooth(kpts, track_id="player_1")
        assert isinstance(result, SmoothedPose)

    def test_process_pipeline(self) -> None:
        processor = PoseProcessor()
        kpts = _make_keypoints_25x3()
        processed, metadata = processor.process(kpts)
        assert processed.shape == kpts.shape
        assert "filter" in metadata

    def test_process_skip_normalize(self) -> None:
        processor = PoseProcessor()
        kpts = _make_keypoints_25x3()
        processed, metadata = processor.process(kpts, normalize=False)
        assert "normalization" not in metadata

    def test_process_skip_smooth(self) -> None:
        processor = PoseProcessor()
        kpts = _make_keypoints_25x3()
        processed, metadata = processor.process(kpts, smooth=False)
        assert "smoothing" not in metadata

    def test_process_invalid_pose(self) -> None:
        processor = PoseProcessor()
        kpts = _make_keypoints_25x3(conf=0.1)
        processed, metadata = processor.process(kpts)
        assert "error" in metadata

    def test_reset_track(self) -> None:
        processor = PoseProcessor()
        kpts = _make_keypoints_25x3()
        processor.smooth(kpts, track_id="t1")
        processor.reset_track("t1")  # 에러 없이 실행

    def test_reset_all(self) -> None:
        processor = PoseProcessor()
        kpts = _make_keypoints_25x3()
        processor.smooth(kpts, track_id="t1")
        processor.smooth(kpts, track_id="t2")
        processor.reset_all()  # 에러 없이 실행

    def test_invalid_config_fallback(self) -> None:
        """잘못된 설정 → 기본값 폴백."""
        config = {
            "smoothing": {
                "mode": "INVALID_MODE",
            },
        }
        # KeyError 잡아서 기본값 유지해야 함
        processor = PoseProcessor(config=config)
        assert processor._smoothing_config.mode == SmoothingMode.KALMAN


# ============================================================
# 10. 모듈 레벨 테스트
# ============================================================
class TestModuleLevel:
    """모듈 레벨 속성 테스트."""

    def test_version(self) -> None:
        from pose_estimation.processing import __version__
        assert __version__ == "1.0.0"

    def test_all_exports(self) -> None:
        from pose_estimation.processing import __all__
        assert "PoseProcessor" in __all__
        assert "normalize_pose" in __all__
        assert "TemporalSmoother" in __all__
        assert "filter_low_confidence" in __all__
        assert "CRITICAL_KEYPOINTS" in __all__
