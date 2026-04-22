# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection
파일: multiview_tracker.py
설명: 8대 카메라 기반 Geometry Multi-View Player Tracker
      - 카메라별 bbox → 호모그래피 → 코트 좌표 투영
      - 8대 감지를 코트 좌표계에서 DBSCAN 공간 클러스터링
      - 각 클러스터 = 같은 선수 (다른 카메라에서 본 동일 위치)
      - 코트 좌표계 Kalman 트래킹 (시간 연속성)
      - CV-Digit(등번호) + CV-team(팀) → Global Player ID 확정
      - GameState 연동 (교체/쿼터/TO 복귀 시 영구 ID 복구)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0

의존성:
    - 카메라 캘리브레이션 JSON (configs/calibration/cam_*.json)
    - sklearn.cluster.DBSCAN: 공간 클러스터링
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

import numpy as np
from sklearn.cluster import DBSCAN

logger: Final = logging.getLogger(__name__)


# =============================================================================
# 데이터 구조
# =============================================================================

class GameState(Enum):
    """경기 상태 — 트래킹 동작 모드 결정."""
    ACTIVE = "active"          # 정상 경기 중
    PAUSED = "paused"          # 작전타임/쿼터브레이크
    RESUME_WINDOW = "resume"   # 재개 직후 10초 (재식별 고빈도)


@dataclass
class CameraDetection:
    """한 카메라에서의 단일 선수 감지."""
    cam_id: int                      # 1~8
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2) 픽셀
    jersey_number: int | None = None
    jersey_conf: float = 0.0
    team: str | None = None          # "team_a" | "team_b" | "referee"
    team_conf: float = 0.0
    yolo_conf: float = 1.0


@dataclass
class CourtObservation:
    """코트 좌표계로 투영된 관측."""
    cam_id: int
    det_idx: int                     # 카메라 내 감지 인덱스
    court_x: float                   # 미터
    court_y: float
    detection: CameraDetection
    cluster_id: int = -1             # DBSCAN 할당 (노이즈 = -1)


@dataclass
class PlayerTrack:
    """글로벌 Player ID 트랙 — 코트 좌표계."""
    global_id: int
    court_x: float                   # 현재 추정 위치
    court_y: float
    vx: float = 0.0                  # 속도 (m/s)
    vy: float = 0.0
    last_frame: int = 0
    miss_count: int = 0              # 연속 미검출 프레임
    total_hits: int = 0

    # 확정 정보 (Jersey + Team)
    jersey_number: int | None = None
    team: str | None = None
    confirmed: bool = False

    # 관찰 히스토리 (최근 30프레임)
    history_xy: list[tuple[float, float]] = field(default_factory=list)
    # cam별 최근 감지 (라벨 전파용)
    last_cam_detections: dict[int, CameraDetection] = field(default_factory=dict)

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed


# =============================================================================
# 호모그래피 로더 + 투영
# =============================================================================

class CalibrationLoader:
    """카메라별 호모그래피 로드 및 좌표 변환."""

    def __init__(self, calib_dir: str):
        self.calib_dir = calib_dir
        self.homographies: dict[int, np.ndarray] = {}
        self.inverse_homographies: dict[int, np.ndarray] = {}
        self._load_all()

    def _load_all(self) -> None:
        """cam_0.json ~ cam_7.json 로드.
        picker 규약: cam_0 = cam1 영상 → cam_id 1로 저장.
        """
        for i in range(8):
            path = os.path.join(self.calib_dir, f"cam_{i}.json")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            H = np.array(d["homography"], dtype=np.float64)
            Hinv = np.array(d.get("inverse_homography", np.linalg.inv(H).tolist()), dtype=np.float64)
            # picker cam_0 → 영상 cam1 이므로 cam_id = i+1
            self.homographies[i + 1] = H
            self.inverse_homographies[i + 1] = Hinv

    def project_bbox_to_court(
        self,
        cam_id: int,
        bbox: tuple[int, int, int, int],
    ) -> tuple[float, float] | None:
        """bbox 발 위치(하단 중앙) → 코트 좌표 (미터)."""
        H = self.homographies.get(cam_id)
        if H is None:
            return None
        x1, _, x2, y2 = bbox
        foot_x = (x1 + x2) / 2.0
        foot_y = float(y2)
        pt = np.array([foot_x, foot_y, 1.0], dtype=np.float64)
        projected = H @ pt
        projected = projected / projected[2]
        return float(projected[0]), float(projected[1])


# =============================================================================
# 공간 클러스터링 (같은 선수 식별)
# =============================================================================

def cluster_court_observations(
    observations: list[CourtObservation],
    eps_m: float = 1.0,
    min_samples: int = 1,
) -> None:
    """DBSCAN으로 같은 코트 위치의 관측 묶기 (in-place 할당).

    Args:
        observations: 관측 리스트 (cluster_id 필드 업데이트됨)
        eps_m: 같은 선수로 간주할 반경 (미터). 캘리브 오차 고려 1.0m 권장.
        min_samples: DBSCAN 최소 샘플. 단일 카메라 감지도 클러스터 취급 = 1.
    """
    if not observations:
        return
    coords = np.array([[o.court_x, o.court_y] for o in observations], dtype=np.float64)
    clustering = DBSCAN(eps=eps_m, min_samples=min_samples).fit(coords)
    for obs, label in zip(observations, clustering.labels_):
        obs.cluster_id = int(label)


def cluster_centroids(
    observations: list[CourtObservation],
) -> dict[int, tuple[float, float, list[CourtObservation]]]:
    """클러스터 ID별 중심점 + 멤버 관측 반환."""
    groups: dict[int, list[CourtObservation]] = {}
    for obs in observations:
        if obs.cluster_id < 0:
            continue
        groups.setdefault(obs.cluster_id, []).append(obs)

    centroids = {}
    for cid, members in groups.items():
        xs = np.mean([m.court_x for m in members])
        ys = np.mean([m.court_y for m in members])
        centroids[cid] = (float(xs), float(ys), members)
    return centroids


# =============================================================================
# Kalman 필터 (코트 좌표계 위치+속도)
# =============================================================================

class KalmanTrack:
    """단일 트랙 Kalman 필터 — 상태 [x, y, vx, vy]."""

    def __init__(self, init_x: float, init_y: float, dt: float = 1 / 30):
        self.dt = dt
        # 상태: (x, y, vx, vy)
        self.x = np.array([init_x, init_y, 0.0, 0.0], dtype=np.float64)
        # 공분산
        self.P = np.eye(4) * 1.0
        # 상태 전이 (등속도 모델)
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=np.float64)
        # 관측 (x, y만)
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=np.float64)
        # 프로세스 잡음 (1m/s² 수준의 가속 변동)
        self.Q = np.diag([0.1, 0.1, 1.0, 1.0])
        # 관측 잡음 (호모그래피 오차 ~1m 가정)
        self.R = np.diag([1.0, 1.0])

    def predict(self) -> tuple[float, float]:
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return float(self.x[0]), float(self.x[1])

    def update(self, obs_x: float, obs_y: float) -> None:
        z = np.array([obs_x, obs_y], dtype=np.float64)
        y = z - self.H @ self.x  # innovation
        S = self.H @ self.P @ self.H.T + self.R
        # 칼만 이득 — 특이행렬 방어 (LinAlgError 시 예측 상태 유지)
        try:
            K = self.P @ self.H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            logger.warning("KalmanTrack update: 특이행렬, 예측 상태 유지")
            return
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P

    @property
    def position(self) -> tuple[float, float]:
        return float(self.x[0]), float(self.x[1])

    @property
    def velocity(self) -> tuple[float, float]:
        return float(self.x[2]), float(self.x[3])


# =============================================================================
# 메인 트래커
# =============================================================================

class MultiViewPlayerTracker:
    """8대 카메라 Geometry 기반 글로벌 Player ID 트래커."""

    def __init__(
        self,
        calib_dir: str,
        cluster_eps_m: float = 1.0,
        max_miss_frames: int = 60,   # 2초 (30fps 기준)
        dt: float = 1.0 / 30,
        match_max_dist_m: float = 3.0,
    ):
        self.loader = CalibrationLoader(calib_dir)
        self.cluster_eps_m = cluster_eps_m
        self.max_miss_frames = max_miss_frames
        self.dt = dt
        self.match_max_dist_m = match_max_dist_m

        self.tracks: dict[int, PlayerTrack] = {}
        self.kalman: dict[int, KalmanTrack] = {}
        self.next_id: int = 1

        self.game_state: GameState = GameState.ACTIVE
        self.resume_frames_left: int = 0

        # Jersey+Team 확정된 영구 ID 매핑
        # ("team_a", 23) → global_id
        self.permanent_id_map: dict[tuple[str, int], int] = {}

    # -------------------------------------------------------------------------
    # Game State 제어
    # -------------------------------------------------------------------------

    def set_game_state(self, state: GameState) -> None:
        """게임 상태 변경. PAUSED → ACTIVE 전환 시 재식별 윈도우 발동."""
        prev = self.game_state
        self.game_state = state
        if prev == GameState.PAUSED and state == GameState.ACTIVE:
            self.game_state = GameState.RESUME_WINDOW
            self.resume_frames_left = int(10 / self.dt)  # 10초

    def _tick_resume_window(self) -> None:
        if self.game_state == GameState.RESUME_WINDOW:
            self.resume_frames_left -= 1
            if self.resume_frames_left <= 0:
                self.game_state = GameState.ACTIVE

    # -------------------------------------------------------------------------
    # 프레임 업데이트
    # -------------------------------------------------------------------------

    def update(
        self,
        frame_idx: int,
        detections_per_cam: dict[int, list[CameraDetection]],
    ) -> dict[tuple[int, int], int]:
        """매 프레임 트래커 업데이트.

        Args:
            frame_idx: 프레임 번호
            detections_per_cam: {cam_id: [CameraDetection, ...]}

        Returns:
            {(cam_id, det_idx): global_player_id}
        """
        # 1. Kalman 예측 (모든 기존 트랙)
        predicted_positions = {}
        for gid, kf in self.kalman.items():
            predicted_positions[gid] = kf.predict()

        # 2. 모든 카메라 감지를 코트 좌표로 투영
        observations: list[CourtObservation] = []
        for cam_id, dets in detections_per_cam.items():
            for det_idx, det in enumerate(dets):
                court = self.loader.project_bbox_to_court(cam_id, det.bbox)
                if court is None:
                    continue
                cx, cy = court
                # 코트 영역 밖 ±2m 이상 제외 (호모그래피 오차 방어)
                if cx < -2 or cx > 30 or cy < -2 or cy > 17:
                    continue
                observations.append(CourtObservation(
                    cam_id=cam_id, det_idx=det_idx,
                    court_x=cx, court_y=cy, detection=det,
                ))

        # 3. 공간 클러스터링 → 같은 선수 묶기
        cluster_court_observations(observations, eps_m=self.cluster_eps_m)
        centroids = cluster_centroids(observations)

        # 4. 클러스터 ↔ 기존 트랙 매칭 (Hungarian)
        matches, unmatched_clusters, unmatched_tracks = self._match_clusters_to_tracks(
            centroids, predicted_positions,
        )

        # 5. 매칭된 트랙 업데이트
        for cluster_id, track_id in matches:
            cx, cy, members = centroids[cluster_id]
            self._update_track(track_id, cx, cy, members, frame_idx)

        # 6. 미매칭 클러스터 → 신규 트랙
        new_cluster_to_track: dict[int, int] = {}
        for cluster_id in unmatched_clusters:
            cx, cy, members = centroids[cluster_id]
            new_id = self._create_track(cx, cy, members, frame_idx)
            new_cluster_to_track[cluster_id] = new_id

        # 7. 미매칭 트랙 → miss_count 증가
        for track_id in unmatched_tracks:
            tr = self.tracks.get(track_id)
            if tr is not None:
                tr.miss_count += 1

        # 8. Jersey + Team 확정 처리
        self._confirm_identities()

        # 9. 죽은 트랙 제거
        self._cleanup_dead_tracks()

        # 10. 관측 → global_id 매핑 반환
        result: dict[tuple[int, int], int] = {}
        cluster_to_track = {cid: tid for cid, tid in matches}
        cluster_to_track.update(new_cluster_to_track)
        for obs in observations:
            if obs.cluster_id < 0:
                continue
            gid = cluster_to_track.get(obs.cluster_id)
            if gid is not None:
                result[(obs.cam_id, obs.det_idx)] = gid

        self._tick_resume_window()
        return result

    # -------------------------------------------------------------------------
    # 매칭 — Hungarian 없이 간단한 greedy (클러스터 ↔ 트랙)
    # -------------------------------------------------------------------------

    def _match_clusters_to_tracks(
        self,
        centroids: dict[int, tuple[float, float, list[CourtObservation]]],
        predicted_positions: dict[int, tuple[float, float]],
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        """클러스터와 예측 위치 기반 greedy 매칭.

        Returns:
            (matched: [(cluster_id, track_id), ...], unmatched_clusters, unmatched_tracks)
        """
        max_dist_m = self.match_max_dist_m
        if not centroids or not predicted_positions:
            return [], list(centroids.keys()), list(predicted_positions.keys())

        # 거리 행렬 구성
        cluster_ids = list(centroids.keys())
        track_ids = list(predicted_positions.keys())
        pairs = []
        for ci in cluster_ids:
            cx, cy, _ = centroids[ci]
            for ti in track_ids:
                tx, ty = predicted_positions[ti]
                d = np.sqrt((cx - tx) ** 2 + (cy - ty) ** 2)
                if d <= max_dist_m:
                    pairs.append((d, ci, ti))

        pairs.sort()
        matched: list[tuple[int, int]] = []
        used_clusters: set[int] = set()
        used_tracks: set[int] = set()
        for _, ci, ti in pairs:
            if ci in used_clusters or ti in used_tracks:
                continue
            matched.append((ci, ti))
            used_clusters.add(ci)
            used_tracks.add(ti)

        unmatched_clusters = [c for c in cluster_ids if c not in used_clusters]
        unmatched_tracks = [t for t in track_ids if t not in used_tracks]
        return matched, unmatched_clusters, unmatched_tracks

    # -------------------------------------------------------------------------
    # 트랙 생성/갱신/삭제
    # -------------------------------------------------------------------------

    def _create_track(
        self,
        cx: float,
        cy: float,
        members: list[CourtObservation],
        frame_idx: int,
    ) -> int:
        # Jersey + Team 이미 관찰됐으면 영구 ID 재사용
        jersey, team = self._best_jersey_team(members)
        if jersey is not None and team is not None:
            key = (team, jersey)
            if key in self.permanent_id_map:
                gid = self.permanent_id_map[key]
                # 살아있는 트랙이면 위치 업데이트로 재활용
                if gid in self.tracks:
                    self._update_track(gid, cx, cy, members, frame_idx)
                    return gid
                # 이전에 cleanup된 영구 ID → 같은 gid로 트랙 재부활
                # (교체/쿼터/TO 복귀 시 ID 연속성 보존의 핵심)
                tr = PlayerTrack(
                    global_id=gid, court_x=cx, court_y=cy,
                    last_frame=frame_idx, total_hits=1,
                    jersey_number=jersey, team=team, confirmed=True,
                )
                self.tracks[gid] = tr
                self.kalman[gid] = KalmanTrack(cx, cy, dt=self.dt)
                self._apply_observations(tr, members)
                return gid

        # 새 ID
        gid = self.next_id
        self.next_id += 1
        tr = PlayerTrack(
            global_id=gid, court_x=cx, court_y=cy,
            last_frame=frame_idx, total_hits=1,
        )
        self.tracks[gid] = tr
        self.kalman[gid] = KalmanTrack(cx, cy, dt=self.dt)
        self._apply_observations(tr, members)
        return gid

    def _update_track(
        self,
        track_id: int,
        cx: float,
        cy: float,
        members: list[CourtObservation],
        frame_idx: int,
    ) -> None:
        tr = self.tracks.get(track_id)
        if tr is None:
            return
        kf = self.kalman.get(track_id)
        if kf is not None:
            kf.update(cx, cy)
            tr.court_x, tr.court_y = kf.position
            tr.vx, tr.vy = kf.velocity
        else:
            tr.court_x, tr.court_y = cx, cy

        tr.last_frame = frame_idx
        tr.miss_count = 0
        tr.total_hits += 1
        tr.history_xy.append((tr.court_x, tr.court_y))
        if len(tr.history_xy) > 30:
            tr.history_xy.pop(0)

        self._apply_observations(tr, members)

    def _apply_observations(
        self,
        tr: PlayerTrack,
        members: list[CourtObservation],
    ) -> None:
        """관측에서 jersey/team 정보 갱신."""
        for m in members:
            tr.last_cam_detections[m.cam_id] = m.detection

        jersey, team = self._best_jersey_team(members)
        if jersey is not None:
            tr.jersey_number = jersey
        if team is not None:
            tr.team = team

    @staticmethod
    def _best_jersey_team(
        members: list[CourtObservation],
    ) -> tuple[int | None, str | None]:
        """여러 카메라 관찰 중 confidence 최고 jersey/team 선택."""
        best_j = None
        best_j_conf = 0.0
        best_t = None
        best_t_conf = 0.0
        for m in members:
            det = m.detection
            if det.jersey_number is not None and det.jersey_conf > best_j_conf:
                best_j = det.jersey_number
                best_j_conf = det.jersey_conf
            if det.team is not None and det.team_conf > best_t_conf:
                best_t = det.team
                best_t_conf = det.team_conf
        return best_j, best_t

    def _confirm_identities(self) -> None:
        """Jersey + Team 둘 다 확보된 트랙 확정 + 영구 ID 매핑."""
        for gid, tr in self.tracks.items():
            if tr.jersey_number is not None and tr.team is not None and not tr.confirmed:
                tr.confirmed = True
                self.permanent_id_map[(tr.team, tr.jersey_number)] = gid

    def _cleanup_dead_tracks(self) -> None:
        """오랜 미검출 트랙 제거 (단, 확정된 트랙은 paused 시 유지)."""
        to_remove = []
        for gid, tr in self.tracks.items():
            # paused 상태에서는 확정 트랙은 영구 유지
            if self.game_state == GameState.PAUSED and tr.confirmed:
                continue
            if tr.miss_count >= self.max_miss_frames:
                to_remove.append(gid)
        for gid in to_remove:
            self.tracks.pop(gid, None)
            self.kalman.pop(gid, None)

    # -------------------------------------------------------------------------
    # 조회 API
    # -------------------------------------------------------------------------

    def active_tracks(self) -> list[PlayerTrack]:
        return [t for t in self.tracks.values() if t.miss_count < 5]

    def all_tracks(self) -> list[PlayerTrack]:
        return list(self.tracks.values())

    def get_camera_detections(
        self,
        global_id: int,
    ) -> dict[int, CameraDetection]:
        """한 선수가 각 카메라에서 어떻게 보이는지 (라벨 전파 핵심)."""
        tr = self.tracks.get(global_id)
        if tr is None:
            return {}
        return dict(tr.last_cam_detections)

    def reset(self) -> None:
        """모든 트랙/영구 ID/Kalman 상태 초기화 (경기 종료 시 호출)."""
        self.tracks.clear()
        self.kalman.clear()
        self.permanent_id_map.clear()
        self.next_id = 1
        self.game_state = GameState.ACTIVE
        self.resume_frames_left = 0


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "CalibrationLoader",
    "CameraDetection",
    "CourtObservation",
    "GameState",
    "KalmanTrack",
    "MultiViewPlayerTracker",
    "PlayerTrack",
    "cluster_centroids",
    "cluster_court_observations",
]

__version__ = "1.0.0"
