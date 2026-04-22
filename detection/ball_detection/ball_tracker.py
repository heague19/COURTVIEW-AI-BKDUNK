# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/ball_detection
파일: ball_tracker.py
설명: 농구공 추적기 (Kalman 8D + Hungarian 매칭 + ByteTrack)
      - 8차원 칼만 필터 (cx, cy, w, h, vx, vy, vw, vh)
      - 헝가리안 알고리즘 기반 최적 매칭
      - ByteTrack 2단계 연관 (고신뢰 → 저신뢰)
      - 궤적 이력 관리 + 오클루전 복구
      ※ 멀티뷰 융합은 ball_detector.py에서 처리 완료 후
        단일 감지 결과만 수신 (tracker는 단일 뷰 추적 전담)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/ball_constants.py: 추적 파라미터
    - shared/dto/ball_dto.py: BallDetection, BallTrajectory DTO
    - shared/dto/tracking_dto.py: Track, KalmanState, TrackState DTO
    - shared/dto/geometry_dto.py: Point2D, BoundingBox DTO
    - detection/ball_detection/ball_detector.py: BallDetector
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.ball_constants import (
    BALL_KALMAN_MEASUREMENT_NOISE,
    BALL_KALMAN_PROCESS_NOISE,
    BALL_TRACKING_COST_THRESHOLD,
    BALL_TRACKING_IOU_THRESHOLD,
    BALL_TRACKING_LOST_THRESHOLD_FRAMES,
    BALL_TRACKING_MATCH_THRESH,
    BALL_TRACKING_MAX_MATCH_DISTANCE,
    BALL_TRACKING_MAX_TRACK_AGE,
    BALL_TRACKING_MIN_HITS,
    BALL_TRACKING_NEW_TRACK_THRESH,
    BALL_TRACKING_TRAJECTORY_LENGTH,
)
from shared.dto.ball_dto import BallDetection, BallTrajectory
from shared.dto.geometry_dto import BoundingBox, Point2D
from shared.dto.tracking_dto import (
    KalmanState,
    Track,
    TrackHistory,
    TrackSource,
    TrackState,
    TrackedObjectType,
)

# =============================================================================
# 모듈 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 칼만 필터 상태 차원 (cx, cy, w, h, vx, vy, vw, vh)
_STATE_DIM: Final[int] = 8

# 칼만 필터 측정 차원 (cx, cy, w, h)
_MEASUREMENT_DIM: Final[int] = 4

# 매칭 비용 가중치: 거리 vs IoU
_DISTANCE_WEIGHT: Final[float] = 0.6
_IOU_WEIGHT: Final[float] = 0.4

# 트랙 ID 카운터 최대값 (오버플로 방지)
_MAX_TRACK_ID: Final[int] = 1_000_000


# =============================================================================
# 칼만 필터 (8D 선형)
# =============================================================================

class BallKalmanFilter:
    """
    농구공 전용 8D 칼만 필터.

    상태 벡터: [cx, cy, w, h, vx, vy, vw, vh]
    측정 벡터: [cx, cy, w, h]

    등속도 모델 + 프로세스/측정 노이즈 기반 예측·업데이트.
    """

    __slots__ = (
        "_state_dim",
        "_measurement_dim",
        "_f_matrix",
        "_h_matrix",
        "_q_matrix",
        "_r_matrix",
    )

    def __init__(self) -> None:
        """칼만 필터 초기화."""
        self._state_dim = _STATE_DIM
        self._measurement_dim = _MEASUREMENT_DIM

        # 상태 전이 행렬 F (등속도 모델)
        self._f_matrix = np.eye(_STATE_DIM, dtype=np.float64)
        for i in range(_MEASUREMENT_DIM):
            self._f_matrix[i, i + _MEASUREMENT_DIM] = 1.0

        # 관측 행렬 H
        self._h_matrix = np.eye(
            _MEASUREMENT_DIM, _STATE_DIM, dtype=np.float64,
        )

        # 프로세스 노이즈 Q
        self._q_matrix = np.eye(_STATE_DIM, dtype=np.float64)
        self._q_matrix[:_MEASUREMENT_DIM, :_MEASUREMENT_DIM] *= (
            BALL_KALMAN_PROCESS_NOISE
        )
        self._q_matrix[_MEASUREMENT_DIM:, _MEASUREMENT_DIM:] *= (
            BALL_KALMAN_PROCESS_NOISE * 2.0
        )

        # 측정 노이즈 R
        self._r_matrix = np.eye(
            _MEASUREMENT_DIM, dtype=np.float64,
        ) * BALL_KALMAN_MEASUREMENT_NOISE

    def __repr__(self) -> str:
        return (
            f"BallKalmanFilter("
            f"state_dim={self._state_dim}, "
            f"meas_dim={self._measurement_dim})"
        )

    def initiate(
        self,
        measurement: NDArray[np.float64],
    ) -> KalmanState:
        """
        첫 관측으로 칼만 상태 초기화.

        Args:
            measurement: [cx, cy, w, h]

        Returns:
            초기화된 KalmanState
        """
        mean = np.zeros(_STATE_DIM, dtype=np.float64)
        mean[:_MEASUREMENT_DIM] = measurement

        # 초기 공분산: 위치는 작게, 속도는 크게 (불확실)
        covariance = np.eye(_STATE_DIM, dtype=np.float64)
        covariance[:_MEASUREMENT_DIM, :_MEASUREMENT_DIM] *= (
            BALL_KALMAN_MEASUREMENT_NOISE * 2.0
        )
        covariance[_MEASUREMENT_DIM:, _MEASUREMENT_DIM:] *= 10.0

        return KalmanState(
            mean=mean,
            covariance=covariance,
            state_dim=_STATE_DIM,
            measurement_dim=_MEASUREMENT_DIM,
        )

    def predict(self, state: KalmanState) -> KalmanState:
        """
        상태 예측 (시간 전파).

        Args:
            state: 현재 칼만 상태

        Returns:
            예측된 칼만 상태
        """
        predicted_mean = self._f_matrix @ state.mean
        predicted_covariance = (
            self._f_matrix @ state.covariance @ self._f_matrix.T
            + self._q_matrix
        )

        return KalmanState(
            mean=predicted_mean,
            covariance=predicted_covariance,
            state_dim=_STATE_DIM,
            measurement_dim=_MEASUREMENT_DIM,
        )

    def update(
        self,
        state: KalmanState,
        measurement: NDArray[np.float64],
    ) -> KalmanState:
        """
        관측값으로 상태 업데이트 (보정).

        Args:
            state: 예측된 칼만 상태
            measurement: [cx, cy, w, h]

        Returns:
            보정된 칼만 상태
        """
        # 혁신 (잔차)
        innovation = measurement - self._h_matrix @ state.mean

        # 혁신 공분산
        s_matrix = (
            self._h_matrix @ state.covariance @ self._h_matrix.T
            + self._r_matrix
        )

        # 칼만 이득 — 특이행렬 방어 (LinAlgError 시 예측 상태 유지)
        try:
            kalman_gain = (
                state.covariance @ self._h_matrix.T @ np.linalg.inv(s_matrix)
            )
        except np.linalg.LinAlgError:
            logger.warning("BallKalmanFilter update: 특이행렬, 예측 상태 유지")
            return state

        # 상태 업데이트
        updated_mean = state.mean + kalman_gain @ innovation
        updated_covariance = (
            (np.eye(_STATE_DIM) - kalman_gain @ self._h_matrix)
            @ state.covariance
        )

        return KalmanState(
            mean=updated_mean,
            covariance=updated_covariance,
            state_dim=_STATE_DIM,
            measurement_dim=_MEASUREMENT_DIM,
        )

    def gating_distance(
        self,
        state: KalmanState,
        measurement: NDArray[np.float64],
    ) -> float:
        """
        마할라노비스 거리 (게이팅 거리).

        Args:
            state: 예측된 칼만 상태
            measurement: [cx, cy, w, h]

        Returns:
            마할라노비스 거리
        """
        innovation = measurement - self._h_matrix @ state.mean
        s_matrix = (
            self._h_matrix @ state.covariance @ self._h_matrix.T
            + self._r_matrix
        )

        try:
            s_inv = np.linalg.inv(s_matrix)
            distance = float(innovation.T @ s_inv @ innovation)
            return distance
        except np.linalg.LinAlgError:
            return float("inf")


# =============================================================================
# 공 추적기 설정
# =============================================================================

@dataclass(slots=True)
class BallTrackerConfig:
    """
    공 추적기 설정.

    Attributes:
        max_age: 미감지 시 트랙 유지 최대 프레임
        min_hits: 트랙 확정 최소 연속 감지 수
        iou_threshold: 매칭 IoU 임계값
        max_match_distance: 헝가리안 최대 매칭 거리 (픽셀)
        high_confidence_threshold: 1단계 매칭 신뢰도 임계값
        new_track_threshold: 새 트랙 생성 신뢰도 임계값
        cost_threshold: 매칭 비용 상한
        trajectory_length: 궤적 이력 최대 길이 (프레임)
    """

    max_age: int = BALL_TRACKING_MAX_TRACK_AGE
    min_hits: int = BALL_TRACKING_MIN_HITS
    iou_threshold: float = BALL_TRACKING_IOU_THRESHOLD
    max_match_distance: float = BALL_TRACKING_MAX_MATCH_DISTANCE
    high_confidence_threshold: float = BALL_TRACKING_MATCH_THRESH
    new_track_threshold: float = BALL_TRACKING_NEW_TRACK_THRESH
    cost_threshold: float = BALL_TRACKING_COST_THRESHOLD
    trajectory_length: int = BALL_TRACKING_TRAJECTORY_LENGTH

    def __repr__(self) -> str:
        return (
            f"BallTrackerConfig(max_age={self.max_age}, "
            f"min_hits={self.min_hits}, "
            f"max_dist={self.max_match_distance})"
        )


# =============================================================================
# 내부 트랙 (칼만 상태 내장)
# =============================================================================

@dataclass(slots=True)
class _InternalTrack:
    """
    내부 트랙 (칼만 필터 상태 내장).

    Track DTO와 분리된 내부 추적 상태.
    """

    track_id: int
    kalman_state: KalmanState
    state: TrackState = TrackState.TENTATIVE
    hits: int = 1
    age: int = 1
    time_since_update: int = 0
    confidence: float = 0.0
    trajectory: deque[tuple[float, float]] = field(
        default_factory=lambda: deque(maxlen=BALL_TRACKING_TRAJECTORY_LENGTH),
    )

    @property
    def position(self) -> tuple[float, float]:
        """현재 위치 (cx, cy)."""
        return self.kalman_state.position

    @property
    def velocity(self) -> tuple[float, float]:
        """현재 속도 (vx, vy)."""
        return self.kalman_state.velocity

    @property
    def predicted_bbox(self) -> tuple[float, float, float, float]:
        """예측 bbox (cx, cy, w, h)."""
        m = self.kalman_state.mean
        return (float(m[0]), float(m[1]), float(m[2]), float(m[3]))

    @property
    def is_confirmed(self) -> bool:
        """확정 트랙 여부."""
        return self.state == TrackState.CONFIRMED

    def __repr__(self) -> str:
        cx, cy = self.position
        return (
            f"_InternalTrack(id={self.track_id}, "
            f"pos=({cx:.1f}, {cy:.1f}), "
            f"state={self.state.value}, "
            f"hits={self.hits}, age={self.age})"
        )


# =============================================================================
# 공 추적기 (ByteTrack + Hungarian)
# =============================================================================

class BallTracker:
    """
    농구공 추적기.

    ByteTrack 2단계 연관 + 헝가리안 최적 매칭 + 칼만 8D 예측.
    ball_detector에서 멀티뷰 융합 완료된 단일 감지 결과를 추적합니다.

    파이프라인 (매 프레임):
        1. 기존 트랙 칼만 예측
        2. 1단계 매칭: 고신뢰 감지 ↔ 트랙 (헝가리안)
        3. 2단계 매칭: 저신뢰 감지 ↔ 미매칭 트랙 (헝가리안)
        4. 매칭된 트랙 칼만 업데이트
        5. 미매칭 감지 → 새 트랙 생성
        6. 미매칭 트랙 → 상태 전이 (LOST → DELETED)
        7. 궤적 이력 업데이트

    사용 예시::

        >>> tracker = BallTracker()
        >>> tracker.initialize(BallTrackerConfig())
        >>> detections = [BallDetection(position=Point2D(100, 200), confidence=0.9)]
        >>> tracks = tracker.update(detections, frame_index=0)
    """

    def __init__(self) -> None:
        """공 추적기 초기화."""
        self._lock = threading.RLock()
        self._config: BallTrackerConfig | None = None
        self._kalman = BallKalmanFilter()
        self._tracks: list[_InternalTrack] = []
        self._next_track_id: int = 1
        self._frame_count: int = 0
        logger.info("BallTracker 인스턴스 생성")

    def __repr__(self) -> str:
        track_count = len(self._tracks)
        confirmed = sum(1 for t in self._tracks if t.is_confirmed)
        return (
            f"BallTracker("
            f"tracks={track_count}, "
            f"confirmed={confirmed}, "
            f"frame={self._frame_count})"
        )

    def initialize(self, config: BallTrackerConfig) -> None:
        """
        추적기 초기화.

        Args:
            config: 추적기 설정
        """
        with self._lock:
            self._config = config
            self._tracks.clear()
            self._next_track_id = 1
            self._frame_count = 0
            logger.info("BallTracker 초기화 완료: %s", config)

    def update(
        self,
        detections: list[BallDetection],
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> list[Track]:
        """
        프레임 단위 추적 업데이트.

        ByteTrack 2단계 연관 + 헝가리안 매칭.

        Args:
            detections: 현재 프레임 감지 결과 목록
            frame_index: 프레임 인덱스
            timestamp_ms: 타임스탬프 (밀리초)

        Returns:
            현재 활성 트랙 DTO 목록
        """
        if self._config is None:
            logger.error("추적기가 초기화되지 않았습니다")
            return []

        with self._lock:
            self._frame_count += 1
            config = self._config

            # 1단계: 기존 트랙 칼만 예측
            for track in self._tracks:
                track.kalman_state = self._kalman.predict(track.kalman_state)
                track.age += 1

            # 유효 감지만 필터링
            valid_detections = [
                d for d in detections
                if d.position is not None and d.confidence > 0
            ]

            if not valid_detections:
                # 감지 없음 → 모든 트랙 미매칭 처리
                self._handle_unmatched_tracks(
                    list(range(len(self._tracks))),
                )
                return self._export_tracks(timestamp_ms)

            # 감지를 측정 벡터로 변환
            measurements = self._detections_to_measurements(valid_detections)

            # 고/저 신뢰도 분리 (ByteTrack 2단계)
            high_indices: list[int] = []
            low_indices: list[int] = []
            for i, det in enumerate(valid_detections):
                if det.confidence >= config.high_confidence_threshold:
                    high_indices.append(i)
                else:
                    low_indices.append(i)

            track_indices = list(range(len(self._tracks)))

            # 2단계: 1차 매칭 (고신뢰 감지 ↔ 전체 트랙)
            matched_1st, unmatched_dets_1st, unmatched_tracks_1st = (
                self._hungarian_match(
                    high_indices,
                    track_indices,
                    measurements,
                    config.cost_threshold,
                )
            )

            # 3단계: 2차 매칭 (저신뢰 감지 ↔ 미매칭 트랙)
            matched_2nd, unmatched_dets_2nd, unmatched_tracks_final = (
                self._hungarian_match(
                    low_indices,
                    unmatched_tracks_1st,
                    measurements,
                    config.cost_threshold * 1.2,  # 저신뢰는 비용 허용 확대
                )
            )

            # 4단계: 매칭된 트랙 칼만 업데이트
            all_matched = matched_1st + matched_2nd
            for det_idx, track_idx in all_matched:
                det = valid_detections[det_idx]
                track = self._tracks[track_idx]

                track.kalman_state = self._kalman.update(
                    track.kalman_state,
                    measurements[det_idx],
                )
                track.hits += 1
                track.time_since_update = 0
                track.confidence = det.confidence

                # 트랙 상태 전이 (TENTATIVE → CONFIRMED)
                if (
                    track.state == TrackState.TENTATIVE
                    and track.hits >= config.min_hits
                ):
                    track.state = TrackState.CONFIRMED

                if track.state == TrackState.OCCLUDED:
                    track.state = TrackState.CONFIRMED

                # 궤적 이력 추가
                cx, cy = track.position
                track.trajectory.append((cx, cy))

            # 5단계: 미매칭 감지 → 새 트랙 생성
            all_unmatched_dets = unmatched_dets_1st + unmatched_dets_2nd
            for det_idx in all_unmatched_dets:
                det = valid_detections[det_idx]
                if det.confidence >= config.new_track_threshold:
                    self._create_track(det, measurements[det_idx])

            # 6단계: 미매칭 트랙 → 상태 전이
            self._handle_unmatched_tracks(unmatched_tracks_final)

            # 7단계: 삭제 대상 제거
            self._tracks = [
                t for t in self._tracks
                if t.state != TrackState.DELETED
            ]

            return self._export_tracks(timestamp_ms)

    def get_active_tracks(self) -> list[Track]:
        """활성 트랙 목록 반환."""
        with self._lock:
            return [
                self._internal_to_dto(t, 0.0)
                for t in self._tracks
                if t.state.is_active
            ]

    def get_best_track(self) -> Track | None:
        """최선(최고 신뢰도) 확정 트랙 반환."""
        with self._lock:
            confirmed = [
                t for t in self._tracks if t.is_confirmed
            ]
            if not confirmed:
                return None
            best = max(confirmed, key=lambda t: t.confidence)
            return self._internal_to_dto(best, 0.0)

    def get_trajectory(self, track_id: int) -> BallTrajectory | None:
        """
        특정 트랙의 궤적을 BallTrajectory DTO로 반환.

        Args:
            track_id: 트랙 ID

        Returns:
            BallTrajectory DTO 또는 None
        """
        with self._lock:
            for t in self._tracks:
                if t.track_id == track_id:
                    trajectory = BallTrajectory(
                        start_frame=max(0, self._frame_count - t.age),
                        end_frame=self._frame_count,
                        confidence=t.confidence,
                    )
                    for px, py in t.trajectory:
                        trajectory.points_2d.append(Point2D(x=px, y=py))
                    return trajectory
            return None

    def reset(self) -> None:
        """추적기 상태 초기화."""
        with self._lock:
            self._tracks.clear()
            self._next_track_id = 1
            self._frame_count = 0
            logger.info("BallTracker 상태 초기화 완료")

    # =========================================================================
    # 내부 메서드: 헝가리안 매칭
    # =========================================================================

    def _hungarian_match(
        self,
        detection_indices: list[int],
        track_indices: list[int],
        measurements: list[NDArray[np.float64]],
        cost_limit: float,
    ) -> tuple[
        list[tuple[int, int]],
        list[int],
        list[int],
    ]:
        """
        헝가리안 알고리즘 기반 최적 매칭.

        비용 행렬 = 거리 비용 * 0.6 + IoU 비용 * 0.4.

        Args:
            detection_indices: 매칭 대상 감지 인덱스
            track_indices: 매칭 대상 트랙 인덱스
            measurements: 전체 감지 측정 벡터
            cost_limit: 매칭 비용 상한

        Returns:
            (매칭 쌍, 미매칭 감지, 미매칭 트랙)
        """
        if not detection_indices or not track_indices:
            return [], list(detection_indices), list(track_indices)

        n_dets = len(detection_indices)
        n_tracks = len(track_indices)

        # 비용 행렬 구성
        cost_matrix = np.full(
            (n_dets, n_tracks), fill_value=1e6, dtype=np.float64,
        )

        for i, det_idx in enumerate(detection_indices):
            meas = measurements[det_idx]
            det_cx, det_cy, det_w, det_h = meas

            for j, trk_idx in enumerate(track_indices):
                track = self._tracks[trk_idx]
                trk_cx, trk_cy, trk_w, trk_h = track.predicted_bbox

                # 유클리드 거리 비용 (정규화)
                dist = np.sqrt(
                    (det_cx - trk_cx) ** 2 + (det_cy - trk_cy) ** 2,
                )

                if dist > self._config.max_match_distance:
                    continue  # 거리 게이팅

                dist_cost = dist / self._config.max_match_distance

                # IoU 비용
                iou = self._compute_iou(
                    det_cx, det_cy, det_w, det_h,
                    trk_cx, trk_cy, trk_w, trk_h,
                )
                iou_cost = 1.0 - iou

                # 가중합 비용
                cost = (
                    dist_cost * _DISTANCE_WEIGHT
                    + iou_cost * _IOU_WEIGHT
                )
                cost_matrix[i, j] = cost

        # 헝가리안 알고리즘 (scipy.optimize.linear_sum_assignment)
        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        matched: list[tuple[int, int]] = []
        unmatched_dets = set(range(n_dets))
        unmatched_tracks = set(range(n_tracks))

        for r, c in zip(row_indices, col_indices):
            if cost_matrix[r, c] > cost_limit:
                continue  # 비용 초과 → 매칭 거부

            det_idx = detection_indices[r]
            trk_idx = track_indices[c]
            matched.append((det_idx, trk_idx))
            unmatched_dets.discard(r)
            unmatched_tracks.discard(c)

        unmatched_det_indices = [
            detection_indices[i] for i in sorted(unmatched_dets)
        ]
        unmatched_trk_indices = [
            track_indices[j] for j in sorted(unmatched_tracks)
        ]

        return matched, unmatched_det_indices, unmatched_trk_indices

    # =========================================================================
    # 내부 메서드: IoU 계산
    # =========================================================================

    @staticmethod
    def _compute_iou(
        cx1: float, cy1: float, w1: float, h1: float,
        cx2: float, cy2: float, w2: float, h2: float,
    ) -> float:
        """
        두 bbox의 IoU 계산 (중심 좌표 + 크기 형식).

        Args:
            cx1, cy1, w1, h1: 첫 번째 bbox
            cx2, cy2, w2, h2: 두 번째 bbox

        Returns:
            IoU 값 (0.0 ~ 1.0)
        """
        # 중심 → xyxy 변환
        x1_min = cx1 - w1 / 2.0
        y1_min = cy1 - h1 / 2.0
        x1_max = cx1 + w1 / 2.0
        y1_max = cy1 + h1 / 2.0

        x2_min = cx2 - w2 / 2.0
        y2_min = cy2 - h2 / 2.0
        x2_max = cx2 + w2 / 2.0
        y2_max = cy2 + h2 / 2.0

        # 교집합
        inter_x1 = max(x1_min, x2_min)
        inter_y1 = max(y1_min, y2_min)
        inter_x2 = min(x1_max, x2_max)
        inter_y2 = min(y1_max, y2_max)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0

        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area1 = w1 * h1
        area2 = w2 * h2
        union_area = area1 + area2 - inter_area

        if union_area <= 0:
            return 0.0

        return inter_area / union_area

    # =========================================================================
    # 내부 메서드: 감지 → 측정 벡터 변환
    # =========================================================================

    @staticmethod
    def _detections_to_measurements(
        detections: list[BallDetection],
    ) -> list[NDArray[np.float64]]:
        """
        BallDetection 목록을 칼만 측정 벡터로 변환.

        Args:
            detections: 감지 목록

        Returns:
            측정 벡터 목록 [cx, cy, w, h]
        """
        measurements: list[NDArray[np.float64]] = []

        for det in detections:
            if det.position is None:
                continue

            cx = det.position.x
            cy = det.position.y

            # bbox가 있으면 크기 사용, 없으면 반지름 기반 추정
            if det.bbox is not None:
                w = det.bbox.x2 - det.bbox.x1 if hasattr(det.bbox, 'x2') else det.radius_pixels * 2.0
                h = det.bbox.y2 - det.bbox.y1 if hasattr(det.bbox, 'y2') else det.radius_pixels * 2.0
            else:
                w = det.radius_pixels * 2.0
                h = det.radius_pixels * 2.0

            measurements.append(
                np.array([cx, cy, w, h], dtype=np.float64),
            )

        return measurements

    # =========================================================================
    # 내부 메서드: 트랙 생성/삭제
    # =========================================================================

    def _create_track(
        self,
        detection: BallDetection,
        measurement: NDArray[np.float64],
    ) -> _InternalTrack:
        """
        새 트랙 생성.

        Args:
            detection: 감지 결과
            measurement: 칼만 측정 벡터

        Returns:
            생성된 내부 트랙
        """
        kalman_state = self._kalman.initiate(measurement)

        track = _InternalTrack(
            track_id=self._next_track_id,
            kalman_state=kalman_state,
            confidence=detection.confidence,
            trajectory=deque(maxlen=self._config.trajectory_length),
        )

        cx, cy = track.position
        track.trajectory.append((cx, cy))

        self._tracks.append(track)
        self._next_track_id += 1

        # 오버플로 방지
        if self._next_track_id > _MAX_TRACK_ID:
            self._next_track_id = 1

        return track

    def _handle_unmatched_tracks(
        self,
        unmatched_indices: list[int],
    ) -> None:
        """
        미매칭 트랙 상태 전이.

        TENTATIVE/CONFIRMED → LOST → DELETED 순서.

        Args:
            unmatched_indices: 미매칭 트랙 인덱스 목록
        """
        config = self._config

        for idx in unmatched_indices:
            if idx >= len(self._tracks):
                continue

            track = self._tracks[idx]
            track.time_since_update += 1

            if track.state == TrackState.TENTATIVE:
                # 확정 전 미감지 → 즉시 삭제
                track.state = TrackState.DELETED

            elif track.state == TrackState.CONFIRMED:
                if track.time_since_update >= BALL_TRACKING_LOST_THRESHOLD_FRAMES:
                    track.state = TrackState.OCCLUDED

            elif track.state == TrackState.OCCLUDED:
                if track.time_since_update >= config.max_age:
                    track.state = TrackState.DELETED

    # =========================================================================
    # 내부 메서드: DTO 변환
    # =========================================================================

    def _internal_to_dto(
        self,
        track: _InternalTrack,
        timestamp: float,
    ) -> Track:
        """
        내부 트랙 → Track DTO 변환.

        Args:
            track: 내부 트랙
            timestamp: 현재 타임스탬프

        Returns:
            Track DTO
        """
        cx, cy, w, h = track.predicted_bbox

        bbox = BoundingBox(
            x=cx - w / 2.0,
            y=cy - h / 2.0,
            width=w,
            height=h,
        )

        history = TrackHistory()
        for px, py in track.trajectory:
            history.positions.append(Point2D(x=px, y=py))

        return Track(
            track_id=track.track_id,
            state=track.state,
            object_type=TrackedObjectType.BALL,
            bbox=bbox,
            position=Point2D(x=cx, y=cy),
            confidence=track.confidence,
            source=TrackSource.SINGLE_VIEW,
            history=history,
            kalman_state=track.kalman_state,
            age=track.age,
            hits=track.hits,
            time_since_update=track.time_since_update,
            attributes={
                "velocity": track.velocity,
            },
        )

    def _export_tracks(self, timestamp_ms: float) -> list[Track]:
        """활성 트랙을 DTO 목록으로 반환."""
        timestamp = timestamp_ms / 1000.0
        return [
            self._internal_to_dto(t, timestamp)
            for t in self._tracks
            if t.state.is_active
        ]


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # 칼만 필터
    "BallKalmanFilter",

    # 설정
    "BallTrackerConfig",

    # 추적기
    "BallTracker",
]

# 모듈 버전 정보
__version__ = "1.0.0"
