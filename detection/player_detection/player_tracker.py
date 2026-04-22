# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection
파일: player_tracker.py
설명: 칼만 필터 기반 선수 추적기
      - 칼만 필터 상태 예측 + 보정
      - 헝가리안 알고리즘 최적 할당
      - IoU + 외관 유사도 복합 비용 행렬
      - 트랙 생성/확정/삭제 수명 주기 관리
      - 크로스뷰 트랙 연결 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/matching_constants.py: 매칭 가중치
    - shared/dto/tracking_dto.py: Track
    - detection/player_detection/models.py: PlayerTrackerConfig, _PlayerCandidate, _TrackState
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import threading
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment

# =============================================================================
# 프로젝트 모듈
# =============================================================================
from shared.constants.matching_constants import (
    APPEARANCE_WEIGHT,
    GEOMETRY_WEIGHT,
)
from detection.player_detection.models import (
    PlayerTrackerConfig,
    _PlayerCandidate,
    _TrackState,
)

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 모듈 상수
# =============================================================================

# 칼만 필터 상태 벡터 차원: [x, y, w, h, vx, vy, vw, vh]
_STATE_DIM: Final[int] = 8

# 칼만 필터 측정 벡터 차원: [x, y, w, h]
_MEASUREMENT_DIM: Final[int] = 4

# 비용 행렬에서 매칭 불가 표시
_UNMATCHED_COST: Final[float] = 1e5

# IoU 기반 비용의 최대 허용값
_MAX_IOU_COST: Final[float] = 0.7

# 외관 유사도 없이 IoU만 사용할 때의 가중치
_IOU_ONLY_WEIGHT: Final[float] = 1.0


# =============================================================================
# 칼만 필터
# =============================================================================

class _KalmanFilter:
    """
    선형 칼만 필터 (bbox 추적용).

    상태 벡터: [cx, cy, w, h, vx, vy, vw, vh]
    측정 벡터: [cx, cy, w, h]

    등속 운동 모델을 가정합니다.
    """

    __slots__ = ("_F", "_H", "_Q", "_R", "_P_init")

    def __init__(self) -> None:
        dt = 1.0

        # 상태 전이 행렬 F (8×8)
        self._F = np.eye(_STATE_DIM, dtype=np.float64)
        for i in range(_MEASUREMENT_DIM):
            self._F[i, i + _MEASUREMENT_DIM] = dt

        # 측정 행렬 H (4×8)
        self._H = np.eye(_MEASUREMENT_DIM, _STATE_DIM, dtype=np.float64)

        # 프로세스 노이즈 Q
        self._Q = np.eye(_STATE_DIM, dtype=np.float64)
        self._Q[:_MEASUREMENT_DIM, :_MEASUREMENT_DIM] *= 1.0
        self._Q[_MEASUREMENT_DIM:, _MEASUREMENT_DIM:] *= 0.01

        # 측정 노이즈 R
        self._R = np.eye(_MEASUREMENT_DIM, dtype=np.float64) * 1.0

        # 초기 공분산 P
        self._P_init = np.eye(_STATE_DIM, dtype=np.float64)
        self._P_init[_MEASUREMENT_DIM:, _MEASUREMENT_DIM:] *= 10.0

    def initiate(self, measurement: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """
        트랙 초기화.

        Args:
            measurement: [cx, cy, w, h]

        Returns:
            (상태 벡터, 공분산 행렬)
        """
        state = np.zeros(_STATE_DIM, dtype=np.float64)
        state[:_MEASUREMENT_DIM] = measurement
        # 속도 = 0
        covariance = self._P_init.copy()
        return state, covariance

    def predict(
        self,
        state: NDArray[np.float64],
        covariance: NDArray[np.float64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """
        상태 예측 (시간 전파).

        Args:
            state: 이전 상태
            covariance: 이전 공분산

        Returns:
            (예측 상태, 예측 공분산)
        """
        predicted_state = self._F @ state
        predicted_cov = self._F @ covariance @ self._F.T + self._Q
        return predicted_state, predicted_cov

    def update(
        self,
        state: NDArray[np.float64],
        covariance: NDArray[np.float64],
        measurement: NDArray[np.float64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """
        측정값으로 상태 보정.

        Args:
            state: 예측 상태
            covariance: 예측 공분산
            measurement: 측정값 [cx, cy, w, h]

        Returns:
            (보정 상태, 보정 공분산)
        """
        # 혁신 (innovation)
        innovation = measurement - self._H @ state

        # 혁신 공분산
        S = self._H @ covariance @ self._H.T + self._R

        # 칼만 이득 — 특이행렬 방어 (LinAlgError 시 예측 상태 유지)
        try:
            K = covariance @ self._H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            logger.warning("_KalmanFilter update: 특이행렬, 예측 상태 유지")
            return state, covariance

        # 상태 보정
        updated_state = state + K @ innovation

        # 공분산 보정 (Joseph form)
        I_KH = np.eye(_STATE_DIM) - K @ self._H
        updated_cov = I_KH @ covariance

        return updated_state, updated_cov


# =============================================================================
# 선수 추적기
# =============================================================================

class PlayerTracker:
    """
    칼만 필터 + 헝가리안 매칭 선수 추적기.

    매 프레임 감지 결과를 기존 트랙과 매칭하여
    연속적인 선수 추적을 수행합니다.

    파이프라인 (per frame):
        1. 기존 트랙 칼만 예측 (시간 전파)
        2. 비용 행렬 구축 (IoU + 외관 유사도)
        3. 헝가리안 최적 할당
        4. 매칭된 트랙 → 칼만 보정
        5. 미매칭 감지 → 신규 트랙 생성
        6. 미매칭 트랙 → 생존 카운터 감소
        7. 사망 트랙 제거

    사용 예시::

        >>> config = PlayerTrackerConfig()
        >>> tracker = PlayerTracker()
        >>> tracker.initialize(config)
        >>> tracks = tracker.update(candidates, frame_index=0)
    """

    def __init__(self) -> None:
        """추적기 초기화."""
        self._lock = threading.RLock()
        self._config: PlayerTrackerConfig | None = None
        self._initialized: bool = False

        self._kf = _KalmanFilter()
        self._tracks: dict[int, _TrackState] = {}
        self._next_track_id: int = 1

        # 외관 특징 캐시 (track_id → feature)
        self._appearance_features: dict[int, NDArray[np.float64]] = {}

        # 통계
        self._total_frames: int = 0
        self._total_tracks_created: int = 0

        logger.info("PlayerTracker 인스턴스 생성")

    # =========================================================================
    # 공개 속성
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def active_track_count(self) -> int:
        """현재 활성 트랙 수."""
        return len(self._tracks)

    @property
    def confirmed_tracks(self) -> list[_TrackState]:
        """확정 트랙 목록."""
        return [t for t in self._tracks.values() if t.is_confirmed]

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    def initialize(self, config: PlayerTrackerConfig) -> None:
        """
        추적기 초기화.

        Args:
            config: 추적 설정
        """
        with self._lock:
            self._config = config
            self._tracks.clear()
            self._appearance_features.clear()
            self._next_track_id = 1
            self._total_frames = 0
            self._total_tracks_created = 0
            self._initialized = True
            logger.info("PlayerTracker 초기화 완료: %r", config)

    def shutdown(self) -> None:
        """추적기 종료."""
        with self._lock:
            self._tracks.clear()
            self._appearance_features.clear()
            self._initialized = False
            logger.info(
                "PlayerTracker 종료: 프레임=%d, 생성=%d",
                self._total_frames,
                self._total_tracks_created,
            )

    def reset(self) -> None:
        """추적 상태 초기화 (설정 유지)."""
        with self._lock:
            self._tracks.clear()
            self._appearance_features.clear()
            self._next_track_id = 1
            self._total_frames = 0
            self._total_tracks_created = 0

    # =========================================================================
    # 프레임 업데이트
    # =========================================================================

    @staticmethod
    def extract_color_features(
        candidates: list[_PlayerCandidate],
        frame: NDArray[np.uint8] | None = None,
    ) -> list[NDArray[np.float64] | None]:
        """
        선수 상체 HSV 색상 히스토그램 추출 (겹침 시 ID 스왑 방지용).

        GPU 불필요. 각 후보의 상체 60% 영역에서 피부색 제외 후
        HSV 히스토그램을 L2 정규화하여 반환합니다.

        Args:
            candidates: 감지 후보 목록
            frame: BGR 이미지 (None이면 빈 feature 반환)

        Returns:
            각 후보의 정규화된 HSV 히스토그램 (48D) 또는 None
        """
        if frame is None:
            return [None] * len(candidates)

        import cv2 as _cv2

        fh, fw = frame.shape[:2]
        features: list[NDArray[np.float64] | None] = []

        # 피부색 HSV 범위
        skin_lo = np.array([5, 30, 60], dtype=np.uint8)
        skin_hi = np.array([25, 180, 255], dtype=np.uint8)

        for cand in candidates:
            try:
                # 상체 60% 크롭
                x1 = max(0, int(cand.bbox_x))
                y1 = max(0, int(cand.bbox_y))
                x2 = min(fw, int(cand.bbox_x + cand.bbox_w))
                y2 = min(fh, int(cand.bbox_y + cand.bbox_h * 0.6))

                if x2 - x1 < 10 or y2 - y1 < 10:
                    features.append(None)
                    continue

                crop = frame[y1:y2, x1:x2]
                hsv = _cv2.cvtColor(crop, _cv2.COLOR_BGR2HSV)

                # 피부색 제외 마스크
                skin_mask = _cv2.inRange(hsv, skin_lo, skin_hi)
                uniform_mask = _cv2.bitwise_not(skin_mask)

                if _cv2.countNonZero(uniform_mask) < 50:
                    features.append(None)
                    continue

                # HSV 히스토그램 (H:16bin + S:16bin + V:16bin = 48D)
                h_hist = _cv2.calcHist([hsv], [0], uniform_mask, [16], [0, 180]).flatten()
                s_hist = _cv2.calcHist([hsv], [1], uniform_mask, [16], [0, 256]).flatten()
                v_hist = _cv2.calcHist([hsv], [2], uniform_mask, [16], [0, 256]).flatten()
                hist = np.concatenate([h_hist, s_hist, v_hist]).astype(np.float64)

                # L2 정규화
                norm = np.linalg.norm(hist)
                if norm > 1e-6:
                    hist /= norm

                features.append(hist)

            except Exception:
                features.append(None)

        return features

    def update(
        self,
        candidates: list[_PlayerCandidate],
        frame_index: int = 0,
        features: list[NDArray[np.float64] | None] | None = None,
        frame: NDArray[np.uint8] | None = None,
    ) -> list[_TrackState]:
        """
        프레임 업데이트: 감지 → 매칭 → 트랙 관리.

        Args:
            candidates: 현재 프레임 감지 후보
            frame_index: 프레임 인덱스
            features: 각 후보의 외관 특징 (없으면 자동 추출 시도)
            frame: BGR 이미지 (features 미제공 시 색상 히스토그램 자동 추출)

        Returns:
            확정 트랙 목록 (_TrackState)
        """
        # features 미제공 + frame 있으면 자동 추출
        if features is None and frame is not None:
            features = self.extract_color_features(candidates, frame)
        if not self._initialized or self._config is None:
            return []

        with self._lock:
            config = self._config
            self._total_frames += 1

            # 1. 칼만 예측
            self._predict_all()

            # 1.5. 겹침 감지 — 외형 가중치 동적 조정용
            overlapping_ids = self._detect_overlapping_tracks(iou_threshold=0.1)

            # 2. 비용 행렬 구축 + 헝가리안 매칭
            matched, unmatched_dets, unmatched_trks = self._associate(
                candidates, features, config,
                overlapping_track_ids=overlapping_ids,
            )

            # 3. 매칭된 트랙 보정
            for det_idx, track_id in matched:
                self._update_track(
                    track_id,
                    candidates[det_idx],
                    features[det_idx] if features else None,
                )

            # 4. 미매칭 감지 → 신규 트랙
            for det_idx in unmatched_dets:
                self._create_track(
                    candidates[det_idx],
                    features[det_idx] if features else None,
                )

            # 5. 미매칭 트랙 → 생존 카운터
            for track_id in unmatched_trks:
                track = self._tracks.get(track_id)
                if track is not None:
                    track.time_since_update += 1

            # 6. 사망 트랙 제거
            self._remove_dead_tracks(config)

            # 확정 트랙만 반환
            return [t for t in self._tracks.values() if t.is_confirmed]

    # =========================================================================
    # 내부 메서드 — 겹침 감지
    # =========================================================================

    def _detect_overlapping_tracks(
        self, iou_threshold: float = 0.15,
    ) -> set[int]:
        """
        겹치는 트랙 쌍 감지 → 예측 전용 모드 전환.

        두 트랙의 예측 bbox IoU가 임계값 이상이면
        두 트랙 모두 매칭에서 제외하고 Kalman 예측만 사용합니다.

        Args:
            iou_threshold: 겹침 판정 IoU 임계값

        Returns:
            겹침으로 동결된 트랙 ID 집합
        """
        frozen: set[int] = set()
        track_ids = list(self._tracks.keys())

        for i in range(len(track_ids)):
            for j in range(i + 1, len(track_ids)):
                t1 = self._tracks[track_ids[i]]
                t2 = self._tracks[track_ids[j]]

                # 두 트랙 간 IoU 계산
                iou = self._track_iou(t1, t2)
                if iou > iou_threshold:
                    frozen.add(track_ids[i])
                    frozen.add(track_ids[j])

        return frozen

    @staticmethod
    def _center_distance_cost(
        candidate: _PlayerCandidate, track: _TrackState,
    ) -> float:
        """중심점 거리 기반 비용 (0~1). 가까울수록 낮은 비용."""
        dx = candidate.center_x - (track.bbox_x + track.bbox_w / 2)
        dy = candidate.center_y - (track.bbox_y + track.bbox_h / 2)
        dist = (dx ** 2 + dy ** 2) ** 0.5
        # 200px 이상이면 비용 1.0
        return min(1.0, dist / 200.0)

    @staticmethod
    def _track_iou(t1: _TrackState, t2: _TrackState) -> float:
        """두 트랙 bbox 간 IoU."""
        x1 = max(t1.bbox_x, t2.bbox_x)
        y1 = max(t1.bbox_y, t2.bbox_y)
        x2 = min(t1.bbox_x + t1.bbox_w, t2.bbox_x + t2.bbox_w)
        y2 = min(t1.bbox_y + t1.bbox_h, t2.bbox_y + t2.bbox_h)

        if x2 <= x1 or y2 <= y1:
            return 0.0

        inter = (x2 - x1) * (y2 - y1)
        area1 = t1.bbox_w * t1.bbox_h
        area2 = t2.bbox_w * t2.bbox_h
        union = area1 + area2 - inter

        return inter / max(union, 1e-6)

    def _is_in_frozen_zone(
        self, candidate: _PlayerCandidate, frozen_ids: set[int],
    ) -> bool:
        """감지가 겹침 트랙 영역 내에 있는지 확인."""
        if not frozen_ids:
            return False

        cx = candidate.center_x
        cy = candidate.center_y

        for tid in frozen_ids:
            track = self._tracks.get(tid)
            if track is None:
                continue
            tcx = track.bbox_x + track.bbox_w / 2
            tcy = track.bbox_y + track.bbox_h / 2
            dist = ((cx - tcx) ** 2 + (cy - tcy) ** 2) ** 0.5
            # 트랙 대각선 길이의 50% 이내면 겹침 영역
            diag = (track.bbox_w ** 2 + track.bbox_h ** 2) ** 0.5
            if dist < diag * 0.5:
                return True
        return False

    # =========================================================================
    # 내부 메서드 — 칼만 예측
    # =========================================================================

    def _predict_all(self) -> None:
        """모든 트랙에 대해 칼만 예측 수행."""
        for track in self._tracks.values():
            if track.state is not None and track.covariance is not None:
                predicted_state, predicted_cov = self._kf.predict(
                    track.state, track.covariance,
                )
                track.state = predicted_state
                track.covariance = predicted_cov

                # 예측 bbox 갱신
                track.bbox_x = float(predicted_state[0]) - float(predicted_state[2]) / 2.0
                track.bbox_y = float(predicted_state[1]) - float(predicted_state[3]) / 2.0
                track.bbox_w = max(1.0, float(predicted_state[2]))
                track.bbox_h = max(1.0, float(predicted_state[3]))

    # =========================================================================
    # 내부 메서드 — 매칭
    # =========================================================================

    def _associate(
        self,
        candidates: list[_PlayerCandidate],
        features: list[NDArray[np.float64] | None] | None,
        config: PlayerTrackerConfig,
        overlapping_track_ids: set[int] | None = None,
    ) -> tuple[
        list[tuple[int, int]],  # matched: (det_idx, track_id)
        list[int],              # unmatched detections
        list[int],              # unmatched tracks
    ]:
        """
        비용 행렬 구축 + 헝가리안 매칭.

        겹침 중인 트랙은 외형 가중치를 강화하여
        색상으로 올바른 감지에 매칭합니다.

        Args:
            candidates: 감지 후보
            features: 외관 특징 (optional)
            config: 설정
            overlapping_track_ids: 겹침 중인 트랙 ID (외형 가중치 강화)

        Returns:
            (매칭 목록, 미매칭 감지 인덱스, 미매칭 트랙 ID)
        """
        overlapping = overlapping_track_ids or set()
        track_ids = list(self._tracks.keys())
        num_dets = len(candidates)
        num_trks = len(track_ids)

        if num_dets == 0:
            return [], [], list(track_ids)
        if num_trks == 0:
            return [], list(range(num_dets)), []

        # 비용 행렬 (num_dets × num_trks)
        cost_matrix = np.full(
            (num_dets, num_trks),
            _UNMATCHED_COST,
            dtype=np.float64,
        )

        for d in range(num_dets):
            for t in range(num_trks):
                track = self._tracks[track_ids[t]]

                # IoU 비용
                iou_val = self._compute_iou(candidates[d], track)
                iou_cost = 1.0 - iou_val

                # 외관 유사도 비용
                app_cost = 1.0
                if features is not None and features[d] is not None:
                    track_feat = self._appearance_features.get(track_ids[t])
                    if track_feat is not None:
                        sim = float(np.dot(features[d], track_feat))
                        app_cost = 1.0 - max(0.0, sim)

                # 복합 비용: 겹침 여부에 따라 가중치 동적 조정
                is_overlapping = track_ids[t] in overlapping
                if features is not None and features[d] is not None:
                    if is_overlapping:
                        # 겹침 중: 외형 60% + IoU 20% + 위치 20%
                        # → 색상으로 구분해야 스위칭 방지
                        combined = (
                            0.20 * iou_cost
                            + 0.60 * app_cost
                            + 0.20 * self._center_distance_cost(candidates[d], track)
                        )
                    else:
                        # 평소: 설정값 사용
                        combined = (
                            config.geometry_weight * iou_cost
                            + config.appearance_weight * app_cost
                        )
                else:
                    combined = iou_cost

                # 임계값 초과 → 매칭 불가 (겹침 중에는 IoU 기준 완화)
                max_cost = 0.9 if is_overlapping else _MAX_IOU_COST
                if iou_cost > max_cost:
                    combined = _UNMATCHED_COST

                cost_matrix[d, t] = combined

        # 헝가리안 알고리즘
        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        matched: list[tuple[int, int]] = []
        unmatched_dets = set(range(num_dets))
        unmatched_trks = set(track_ids)

        for d, t in zip(row_indices, col_indices):
            if cost_matrix[d, t] >= _UNMATCHED_COST:
                continue

            tid = track_ids[t]
            matched.append((d, tid))
            unmatched_dets.discard(d)
            unmatched_trks.discard(tid)

        return matched, sorted(unmatched_dets), sorted(unmatched_trks)

    @staticmethod
    def _compute_iou(
        candidate: _PlayerCandidate,
        track: _TrackState,
    ) -> float:
        """
        후보 bbox와 트랙 bbox의 IoU 계산.

        Args:
            candidate: 감지 후보
            track: 트랙 상태

        Returns:
            IoU (0.0~1.0)
        """
        # 후보 xyxy
        ax1 = candidate.bbox_x
        ay1 = candidate.bbox_y
        ax2 = candidate.bbox_x + candidate.bbox_w
        ay2 = candidate.bbox_y + candidate.bbox_h

        # 트랙 xyxy
        bx1 = track.bbox_x
        by1 = track.bbox_y
        bx2 = track.bbox_x + track.bbox_w
        by2 = track.bbox_y + track.bbox_h

        # 교집합
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        # 합집합
        area_a = max(0.0, candidate.bbox_w * candidate.bbox_h)
        area_b = max(0.0, track.bbox_w * track.bbox_h)
        union_area = area_a + area_b - inter_area

        if union_area <= 0.0:
            return 0.0

        return inter_area / union_area

    # =========================================================================
    # 내부 메서드 — 트랙 관리
    # =========================================================================

    def _create_track(
        self,
        candidate: _PlayerCandidate,
        feature: NDArray[np.float64] | None,
    ) -> int:
        """
        신규 트랙 생성.

        Args:
            candidate: 감지 후보
            feature: 외관 특징 (optional)

        Returns:
            새 track_id
        """
        tid = self._next_track_id
        self._next_track_id += 1

        # 칼만 초기화 (측정: [cx, cy, w, h])
        measurement = np.array(
            [candidate.center_x, candidate.center_y,
             candidate.bbox_w, candidate.bbox_h],
            dtype=np.float64,
        )
        state, covariance = self._kf.initiate(measurement)

        track = _TrackState(
            track_id=tid,
            bbox_x=candidate.bbox_x,
            bbox_y=candidate.bbox_y,
            bbox_w=candidate.bbox_w,
            bbox_h=candidate.bbox_h,
            state=state,
            covariance=covariance,
            age=1,
            hits=1,
            time_since_update=0,
            class_id=candidate.class_id,
            confidence=candidate.combined_score,
        )

        self._tracks[tid] = track

        if feature is not None:
            self._appearance_features[tid] = feature.copy()

        self._total_tracks_created += 1
        return tid

    def _update_track(
        self,
        track_id: int,
        candidate: _PlayerCandidate,
        feature: NDArray[np.float64] | None,
    ) -> None:
        """
        매칭된 트랙 보정.

        Args:
            track_id: 트랙 ID
            candidate: 매칭된 감지 후보
            feature: 외관 특징 (optional)
        """
        track = self._tracks.get(track_id)
        if track is None or track.state is None or track.covariance is None:
            return

        # 칼만 보정
        measurement = np.array(
            [candidate.center_x, candidate.center_y,
             candidate.bbox_w, candidate.bbox_h],
            dtype=np.float64,
        )
        updated_state, updated_cov = self._kf.update(
            track.state, track.covariance, measurement,
        )

        track.state = updated_state
        track.covariance = updated_cov
        track.bbox_x = candidate.bbox_x
        track.bbox_y = candidate.bbox_y
        track.bbox_w = candidate.bbox_w
        track.bbox_h = candidate.bbox_h
        track.age += 1
        track.hits += 1
        track.time_since_update = 0
        track.confidence = candidate.combined_score
        track.class_id = candidate.class_id

        # 외관 특징 업데이트 (EMA)
        if feature is not None:
            old_feat = self._appearance_features.get(track_id)
            if old_feat is not None:
                momentum = 0.9
                blended = momentum * old_feat + (1.0 - momentum) * feature
                norm = float(np.linalg.norm(blended))
                if norm > 1e-12:
                    blended /= norm
                self._appearance_features[track_id] = blended
            else:
                self._appearance_features[track_id] = feature.copy()

    def _remove_dead_tracks(self, config: PlayerTrackerConfig) -> None:
        """사망 트랙 제거."""
        dead_ids: list[int] = []
        for tid, track in self._tracks.items():
            if track.time_since_update > config.max_age:
                dead_ids.append(tid)

        for tid in dead_ids:
            del self._tracks[tid]
            self._appearance_features.pop(tid, None)

    # =========================================================================
    # 외부 인터페이스
    # =========================================================================

    def get_track(self, track_id: int) -> _TrackState | None:
        """
        트랙 조회.

        Args:
            track_id: 트랙 ID

        Returns:
            _TrackState (없으면 None)
        """
        return self._tracks.get(track_id)

    def get_all_tracks(self) -> list[_TrackState]:
        """모든 활성 트랙 목록."""
        return list(self._tracks.values())

    def set_appearance_feature(
        self,
        track_id: int,
        feature: NDArray[np.float64],
    ) -> None:
        """
        외부에서 외관 특징 주입.

        Args:
            track_id: 트랙 ID
            feature: L2 정규화 특징 벡터
        """
        with self._lock:
            if track_id in self._tracks:
                self._appearance_features[track_id] = feature.copy()

    def __repr__(self) -> str:
        confirmed = len([t for t in self._tracks.values() if t.is_confirmed])
        return (
            f"PlayerTracker(active={len(self._tracks)}, "
            f"confirmed={confirmed}, "
            f"created={self._total_tracks_created})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "PlayerTracker",
    "PlayerTrackerConfig",
]

__version__: str = "1.0.0"
