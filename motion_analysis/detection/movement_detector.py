# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/detection
파일: movement_detector.py
설명: 이동 동작 감지기 (Tier 1)
      - 무게중심(COM) 속도 기반 이동 유형 감지
      - 스프린트 / 조깅 / 횡이동(사이드 스텝) / 정지 구분
      - 프레임 시퀀스에서 이동 구간 추출

      학술 근거:
        - Ben Abdelkrim, N. et al. (2007). "Time-motion analysis and
          physiological data of elite under-19 basketball players during
          competition." British J. Sports Medicine, 41(2), 69-75.
          (농구 스프린트 ~5-7 m/s, 조깅 ~2-3 m/s)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - configs/analysis/motion_analysis.yaml: detection.movement 설정
    - motion_analysis/models.py: MotionSnapshot, DetectionCandidate

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/dto/motion_dto.py: ActionType

소비자:
    - motion_analysis/classification/action_classifier.py
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import DetectionCandidate, MotionSnapshot


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# --- 이동 감지 기본 임계치 ---
# Ben Abdelkrim et al. (2007): 스프린트 ~5-7 m/s, 조깅 ~2-3 m/s
_DEFAULT_SPRINT_SPEED_MS: Final[float] = 5.0       # 스프린트 임계 속도 (m/s)
_DEFAULT_JOG_SPEED_MS: Final[float] = 2.0           # 조깅 임계 속도 (m/s)
_DEFAULT_LATERAL_SPEED_MS: Final[float] = 1.5       # 횡이동 임계 속도 (m/s)

_CM_PER_METER: Final[float] = 100.0
_MIN_CONFIDENCE: Final[float] = 0.3
_MIN_MOVEMENT_FRAMES: Final[int] = 5    # 최소 이동 지속 프레임
_STAND_SPEED_MS: Final[float] = 0.3      # 정지 판별 속도 (m/s)


# =============================================================================
# 이동 감지 설정
# =============================================================================

@dataclass(slots=True)
class MovementDetectionConfig:
    """
    이동 감지 임계치 설정.

    Attributes:
        sprint_speed_ms: 스프린트 임계 속도 (m/s)
        jog_speed_ms: 조깅 임계 속도 (m/s)
        lateral_speed_ms: 횡이동 임계 속도 (m/s)
    """

    sprint_speed_ms: float = _DEFAULT_SPRINT_SPEED_MS
    jog_speed_ms: float = _DEFAULT_JOG_SPEED_MS
    lateral_speed_ms: float = _DEFAULT_LATERAL_SPEED_MS


# =============================================================================
# 이동 유형 (내부용 — Tier 2에서 세분화)
# =============================================================================

_MOVEMENT_SPRINT: Final[str] = "sprint"
_MOVEMENT_JOG: Final[str] = "jog"
_MOVEMENT_LATERAL: Final[str] = "lateral"
_MOVEMENT_WALK: Final[str] = "walk"
_MOVEMENT_STAND: Final[str] = "stand"


# =============================================================================
# 이동 감지기
# =============================================================================

class MovementDetector:
    """
    이동 동작 감지기.

    프레임 시퀀스의 무게중심(COM) 또는 엉덩이 중점 속도를 분석하여
    이동 동작을 감지한다.

    감지 기준 (Ben Abdelkrim et al., 2007):
        - 스프린트: COM 속도 ≥ 5.0 m/s
        - 조깅: 2.0 ≤ COM 속도 < 5.0 m/s
        - 횡이동: 좌우 속도 성분 ≥ 1.5 m/s + 전후 성분 < 조깅
        - 걷기: 0.3 ≤ COM 속도 < 2.0 m/s
        - 정지: COM 속도 < 0.3 m/s

    이동 방향 계산: 연속 COM 위치 변화로 이동 방향 (0~360도) 추정.

    사용 예:
        >>> detector = MovementDetector()
        >>> candidates = detector.detect(snapshots)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_config", "_lock")

    def __init__(self, config: MovementDetectionConfig | None = None) -> None:
        self._config = config or MovementDetectionConfig()
        self._lock = RLock()

    @classmethod
    def from_yaml(cls, config_dict: dict) -> MovementDetector:
        """YAML 설정에서 생성.

        Args:
            config_dict: detection.movement 섹션 딕셔너리.

        Returns:
            MovementDetector 인스턴스.
        """
        cfg = MovementDetectionConfig(
            sprint_speed_ms=float(config_dict.get(
                "sprint_speed_threshold_ms", _DEFAULT_SPRINT_SPEED_MS,
            )),
            jog_speed_ms=float(config_dict.get(
                "jog_speed_threshold_ms", _DEFAULT_JOG_SPEED_MS,
            )),
            lateral_speed_ms=float(config_dict.get(
                "lateral_movement_threshold_ms", _DEFAULT_LATERAL_SPEED_MS,
            )),
        )
        return cls(config=cfg)

    # -------------------------------------------------------------------------
    # 핵심 감지 로직
    # -------------------------------------------------------------------------

    def detect(
        self,
        snapshots: list[MotionSnapshot],
    ) -> list[DetectionCandidate]:
        """프레임 시퀀스에서 이동 동작을 감지한다.

        Args:
            snapshots: 프레임 순서 MotionSnapshot 목록 (단일 선수).

        Returns:
            감지된 이동 후보 목록 (시간순).
        """
        with self._lock:
            return self._detect_impl(snapshots)

    def _detect_impl(
        self,
        snapshots: list[MotionSnapshot],
    ) -> list[DetectionCandidate]:
        """감지 구현."""
        if len(snapshots) < _MIN_MOVEMENT_FRAMES:
            return []

        # COM 속도 프로파일 추출
        velocity_profile = self._compute_velocity_profile(snapshots)

        # 프레임별 이동 유형 분류
        frame_types = self._classify_frames(velocity_profile)

        # 연속 동일 유형 구간 추출
        segments = self._extract_segments(frame_types)

        # 후보 생성
        candidates: list[DetectionCandidate] = []
        for seg_type, seg_start, seg_end in segments:
            candidate = self._build_candidate(
                snapshots, velocity_profile, seg_type, seg_start, seg_end,
            )
            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _compute_velocity_profile(
        self,
        snapshots: list[MotionSnapshot],
    ) -> list[dict[str, float]]:
        """COM 기반 속도 프로파일을 계산한다.

        COM이 없으면 좌/우 엉덩이 중점을 사용.
        연속 프레임 간 위치 변화로 속도 계산.

        Args:
            snapshots: 스냅샷 목록.

        Returns:
            프레임별 {speed_ms, vx_ms, vy_ms, direction_deg} 목록.
        """
        profile: list[dict[str, float]] = []

        # COM 또는 엉덩이 중점 위치 추출
        positions: list[tuple[float, float, float] | None] = []
        for snap in snapshots:
            pos = self._get_com_or_hip_center(snap)
            positions.append(pos)

        # 첫 프레임은 속도 0
        profile.append({
            "speed_ms": 0.0, "vx_ms": 0.0, "vy_ms": 0.0,
            "vz_ms": 0.0, "direction_deg": 0.0,
        })

        fps_estimate = 30.0  # 기본 fps
        for i in range(1, len(snapshots)):
            entry: dict[str, float] = {
                "speed_ms": 0.0, "vx_ms": 0.0, "vy_ms": 0.0,
                "vz_ms": 0.0, "direction_deg": 0.0,
            }

            curr_pos = positions[i]
            prev_pos = positions[i - 1]

            if curr_pos is not None and prev_pos is not None:
                # 프레임 간 dt (초)
                dt = 1.0 / fps_estimate
                if snapshots[i].timestamp > 0 and snapshots[i - 1].timestamp > 0:
                    dt = max(
                        1e-6,
                        snapshots[i].timestamp - snapshots[i - 1].timestamp,
                    )

                # 변위 (cm)
                dx = curr_pos[0] - prev_pos[0]
                dy = curr_pos[1] - prev_pos[1]
                dz = curr_pos[2] - prev_pos[2]

                # 속도 (cm/s → m/s)
                vx = dx / dt / _CM_PER_METER
                vy = dy / dt / _CM_PER_METER
                vz = dz / dt / _CM_PER_METER

                # 수평 속력 (코트 평면: x, z)
                speed_horizontal = (vx * vx + vz * vz) ** 0.5

                # 이동 방향 (0~360도, 0=+x 방향)
                direction = 0.0
                if abs(vx) > 1e-6 or abs(vz) > 1e-6:
                    direction = math.degrees(math.atan2(vz, vx)) % 360.0

                entry["speed_ms"] = speed_horizontal
                entry["vx_ms"] = vx
                entry["vy_ms"] = vy
                entry["vz_ms"] = vz
                entry["direction_deg"] = direction

            profile.append(entry)

        return profile

    def _get_com_or_hip_center(
        self,
        snap: MotionSnapshot,
    ) -> tuple[float, float, float] | None:
        """COM 또는 엉덩이 중점을 반환한다.

        Args:
            snap: 프레임 스냅샷.

        Returns:
            (x, y, z) cm 또는 None.
        """
        # COM 우선
        if snap.com_position is not None:
            return snap.com_position

        # 엉덩이 중점 대체
        left_hip = snap.get_position(JointType.LEFT_HIP)
        right_hip = snap.get_position(JointType.RIGHT_HIP)

        if left_hip is not None and right_hip is not None:
            return (
                (left_hip[0] + right_hip[0]) / 2.0,
                (left_hip[1] + right_hip[1]) / 2.0,
                (left_hip[2] + right_hip[2]) / 2.0,
            )

        return left_hip or right_hip

    def _classify_frames(
        self,
        velocity_profile: list[dict[str, float]],
    ) -> list[str]:
        """프레임별 이동 유형을 분류한다.

        Args:
            velocity_profile: 속도 프로파일.

        Returns:
            프레임별 이동 유형 문자열 목록.
        """
        types: list[str] = []

        for entry in velocity_profile:
            speed = entry["speed_ms"]
            vx = entry["vx_ms"]
            vz = entry["vz_ms"]

            if speed < _STAND_SPEED_MS:
                types.append(_MOVEMENT_STAND)
            elif speed >= self._config.sprint_speed_ms:
                types.append(_MOVEMENT_SPRINT)
            elif speed >= self._config.jog_speed_ms:
                # 횡이동 확인: 좌우 성분이 전후 성분보다 큰 경우
                lateral_component = abs(vx)
                forward_component = abs(vz)
                if (
                    lateral_component >= self._config.lateral_speed_ms
                    and lateral_component > forward_component
                ):
                    types.append(_MOVEMENT_LATERAL)
                else:
                    types.append(_MOVEMENT_JOG)
            elif speed >= _STAND_SPEED_MS:
                # 횡이동 (느린 속도에서도 횡 성분 우세)
                lateral_component = abs(vx)
                forward_component = abs(vz)
                if (
                    lateral_component >= self._config.lateral_speed_ms
                    and lateral_component > forward_component
                ):
                    types.append(_MOVEMENT_LATERAL)
                else:
                    types.append(_MOVEMENT_WALK)
            else:
                types.append(_MOVEMENT_STAND)

        return types

    def _extract_segments(
        self,
        frame_types: list[str],
    ) -> list[tuple[str, int, int]]:
        """연속 동일 유형 구간을 추출한다.

        정지(stand)는 감지 대상에서 제외.

        Args:
            frame_types: 프레임별 이동 유형.

        Returns:
            (유형, 시작 인덱스, 종료 인덱스) 목록.
        """
        segments: list[tuple[str, int, int]] = []
        if not frame_types:
            return segments

        seg_type = frame_types[0]
        seg_start = 0

        for i in range(1, len(frame_types)):
            if frame_types[i] != seg_type:
                # 구간 종료
                duration = i - seg_start
                if seg_type != _MOVEMENT_STAND and duration >= _MIN_MOVEMENT_FRAMES:
                    segments.append((seg_type, seg_start, i - 1))
                seg_type = frame_types[i]
                seg_start = i

        # 마지막 구간
        duration = len(frame_types) - seg_start
        if seg_type != _MOVEMENT_STAND and duration >= _MIN_MOVEMENT_FRAMES:
            segments.append((seg_type, seg_start, len(frame_types) - 1))

        return segments

    def _build_candidate(
        self,
        snapshots: list[MotionSnapshot],
        velocity_profile: list[dict[str, float]],
        movement_type: str,
        seg_start: int,
        seg_end: int,
    ) -> DetectionCandidate | None:
        """이동 구간에서 DetectionCandidate를 생성한다.

        Args:
            snapshots: 전체 스냅샷.
            velocity_profile: 속도 프로파일.
            movement_type: 이동 유형.
            seg_start: 구간 시작.
            seg_end: 구간 종료.

        Returns:
            DetectionCandidate 또는 None.
        """
        if seg_start >= len(snapshots) or seg_end >= len(snapshots):
            return None

        start_snap = snapshots[seg_start]
        end_snap = snapshots[seg_end]

        # 구간 내 평균/최대 속도
        speeds = [
            velocity_profile[i]["speed_ms"]
            for i in range(seg_start, seg_end + 1)
            if i < len(velocity_profile)
        ]
        if not speeds:
            return None

        avg_speed = sum(speeds) / len(speeds)
        max_speed = max(speeds)

        # 구간 내 주 이동 방향
        directions = [
            velocity_profile[i]["direction_deg"]
            for i in range(seg_start, seg_end + 1)
            if i < len(velocity_profile) and velocity_profile[i]["speed_ms"] > _STAND_SPEED_MS
        ]
        avg_direction = 0.0
        if directions:
            # 원형 평균 (각도)
            sin_sum = sum(math.sin(math.radians(d)) for d in directions)
            cos_sum = sum(math.cos(math.radians(d)) for d in directions)
            avg_direction = math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0

        # 이동 거리 추정 (COM 시작→끝 변위, m)
        distance_m = self._estimate_distance(snapshots, seg_start, seg_end)

        # --- 신뢰도 ---
        confidence = self._compute_confidence(movement_type, avg_speed, max_speed, speeds)
        if confidence < _MIN_CONFIDENCE:
            return None

        evidence: dict[str, float] = {
            "avg_speed_ms": avg_speed,
            "max_speed_ms": max_speed,
            "direction_deg": avg_direction,
            "distance_m": distance_m,
            "duration_frames": float(seg_end - seg_start + 1),
            "movement_sub_type": {
                _MOVEMENT_SPRINT: 1.0,
                _MOVEMENT_JOG: 2.0,
                _MOVEMENT_LATERAL: 3.0,
                _MOVEMENT_WALK: 4.0,
            }.get(movement_type, 0.0),
        }

        return DetectionCandidate(
            action_type=ActionType.MOVEMENT,
            confidence=confidence,
            start_frame=start_snap.frame_index,
            end_frame=end_snap.frame_index,
            start_time=start_snap.timestamp,
            end_time=end_snap.timestamp,
            player_tracking_id=start_snap.player_tracking_id,
            evidence=evidence,
        )

    def _estimate_distance(
        self,
        snapshots: list[MotionSnapshot],
        seg_start: int,
        seg_end: int,
    ) -> float:
        """구간 내 이동 거리를 추정한다 (m).

        시작/끝 COM 직선 거리.

        Args:
            snapshots: 스냅샷.
            seg_start: 시작 인덱스.
            seg_end: 종료 인덱스.

        Returns:
            이동 거리 (m).
        """
        start_pos = self._get_com_or_hip_center(snapshots[seg_start])
        end_pos = self._get_com_or_hip_center(snapshots[seg_end])

        if start_pos is None or end_pos is None:
            return 0.0

        dx = end_pos[0] - start_pos[0]
        dy = end_pos[1] - start_pos[1]
        dz = end_pos[2] - start_pos[2]
        distance_cm = (dx * dx + dy * dy + dz * dz) ** 0.5
        return distance_cm / _CM_PER_METER

    def _compute_confidence(
        self,
        movement_type: str,
        avg_speed: float,
        max_speed: float,
        speeds: list[float],
    ) -> float:
        """이동 감지 신뢰도를 계산한다.

        가중치:
            - 속도 일관성: 0.40 (구간 내 속도 변동 적을수록 확실)
            - 속도 적합성: 0.35 (유형별 임계값 초과 정도)
            - 지속 시간: 0.25 (긴 구간일수록 확실)

        Args:
            movement_type: 이동 유형.
            avg_speed: 평균 속도.
            max_speed: 최대 속도.
            speeds: 속도 목록.

        Returns:
            신뢰도 (0~1).
        """
        # 속도 일관성 (변동계수 기반, 낮을수록 일관적)
        if avg_speed > 0 and len(speeds) > 1:
            variance = sum((s - avg_speed) ** 2 for s in speeds) / len(speeds)
            std_dev = variance ** 0.5
            cv = std_dev / avg_speed
            consistency_score = max(0.0, 1.0 - cv)
        else:
            consistency_score = 0.5

        # 속도 적합성 (유형별 임계값 기준)
        if movement_type == _MOVEMENT_SPRINT:
            speed_score = min(1.0, avg_speed / max(self._config.sprint_speed_ms, 0.1))
        elif movement_type == _MOVEMENT_JOG:
            speed_score = min(1.0, avg_speed / max(self._config.jog_speed_ms, 0.1))
        elif movement_type == _MOVEMENT_LATERAL:
            speed_score = min(1.0, avg_speed / max(self._config.lateral_speed_ms, 0.1))
        else:
            speed_score = min(1.0, avg_speed / max(_STAND_SPEED_MS, 0.1))

        # 지속 시간 점수 (5프레임=0.5, 15프레임=0.9, 30+=1.0)
        duration_score = min(1.0, len(speeds) / 30.0) * 0.8 + 0.2

        return (
            consistency_score * 0.40
            + speed_score * 0.35
            + duration_score * 0.25
        )

    @property
    def config(self) -> MovementDetectionConfig:
        """현재 설정 반환."""
        return self._config

    def __repr__(self) -> str:
        return (
            f"MovementDetector("
            f"sprint≥{self._config.sprint_speed_ms}m/s, "
            f"jog≥{self._config.jog_speed_ms}m/s, "
            f"lateral≥{self._config.lateral_speed_ms}m/s)"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "MovementDetectionConfig",
    "MovementDetector",
]

__version__ = "1.0.0"
