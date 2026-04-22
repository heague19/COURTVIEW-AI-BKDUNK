# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/detection
파일: dribble_detector.py
설명: 드리블 동작 감지기 (Tier 1)
      - 생체역학 데이터에서 드리블 동작을 감지
      - 손 위치(엉덩이 아래), 수직 진동, 드리블 빈도 기반 판별
      - 연속 바운스 패턴 분석으로 드리블 구간 결정
      - 모든 임계치는 체형 비례 (torso_length = 어깨-엉덩이 거리)

      학술 근거:
        - Arias, J.L. et al. (2012). "Review of biomechanical factors in
          basketball ball handling." J. Human Sport & Exercise, 7(1), 318-329.
          (드리블 시 손 위치, 볼 컨트롤 빈도 1~5 Hz)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - configs/analysis/motion_analysis.yaml: detection.dribble 설정
    - motion_analysis/models.py: MotionSnapshot, DetectionCandidate

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/dto/motion_dto.py: ActionType

소비자:
    - motion_analysis/classification/action_classifier.py
    - motion_analysis/classification/dribble_classifier.py
"""

from __future__ import annotations

import logging
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

# --- 드리블 감지 기본 임계치 (체형 비례 기준) ---
# Arias et al. (2012): 드리블 빈도 1~5 Hz
# torso_length = 어깨 y - 엉덩이 y (체형별 자동 적응)
_DEFAULT_OSCILLATION_RATIO: Final[float] = 0.15       # 최소 진동: 몸통 길이의 15%
_DEFAULT_FREQUENCY_MIN_HZ: Final[float] = 1.0         # 드리블 빈도 하한 (Hz)
_DEFAULT_FREQUENCY_MAX_HZ: Final[float] = 5.0         # 드리블 빈도 상한 (Hz)
_DEFAULT_MIN_CONSECUTIVE_BOUNCES: Final[int] = 2       # 최소 연속 바운스
_DEFAULT_FALLBACK_TORSO_PX: Final[float] = 200.0       # 몸통 측정 불가 시 폴백 (px)

_MIN_CONFIDENCE: Final[float] = 0.3


# =============================================================================
# 드리블 감지 설정
# =============================================================================

@dataclass(slots=True)
class DribbleDetectionConfig:
    """
    드리블 감지 임계치 설정 (체형 비례 기반).

    configs/analysis/motion_analysis.yaml의 detection.dribble 섹션에서 로드.
    모든 거리/진동 임계치는 torso_length 대비 비율로 동작하여
    카메라 거리, 해상도, 체형에 무관하게 일관된 감지 성능을 보장한다.

    Attributes:
        oscillation_ratio: 최소 진동 크기 (몸통 길이 대비 비율, 0~1)
        frequency_min_hz: 드리블 빈도 하한 (Hz)
        frequency_max_hz: 드리블 빈도 상한 (Hz)
        min_consecutive_bounces: 최소 연속 바운스 수
    """

    oscillation_ratio: float = _DEFAULT_OSCILLATION_RATIO
    frequency_min_hz: float = _DEFAULT_FREQUENCY_MIN_HZ
    frequency_max_hz: float = _DEFAULT_FREQUENCY_MAX_HZ
    min_consecutive_bounces: int = _DEFAULT_MIN_CONSECUTIVE_BOUNCES


# =============================================================================
# 드리블 감지기
# =============================================================================

class DribbleDetector:
    """
    드리블 동작 감지기 (체형 비례 기반).

    프레임 시퀀스를 분석하여 드리블 동작 후보를 감지한다.

    감지 기준 (물리적 / 체형 비례):
        1. 손 위치: 손목 y < 엉덩이 y (Y-up 좌표계에서 손이 엉덩이 아래)
        2. 수직 진동: 진폭 ≥ torso_length × oscillation_ratio (체형 비례)
        3. 바운스 빈도: 1~5 Hz 범위 (Arias et al., 2012)
        4. 연속성: min_consecutive_bounces 이상 바운스 감지

    양손 독립 감지: 좌/우 각각 평가하여 바운스 패턴 분석.

    사용 예:
        >>> detector = DribbleDetector()
        >>> candidates = detector.detect(snapshots)
        >>> for c in candidates:
        ...     print(c.action_type, c.confidence)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_config", "_lock")

    def __init__(self, config: DribbleDetectionConfig | None = None) -> None:
        self._config = config or DribbleDetectionConfig()
        self._lock = RLock()

    @classmethod
    def from_yaml(cls, config_dict: dict) -> DribbleDetector:
        """YAML 설정에서 생성.

        Args:
            config_dict: detection.dribble 섹션 딕셔너리.

        Returns:
            DribbleDetector 인스턴스.
        """
        freq_range = config_dict.get("frequency_range_hz", [
            _DEFAULT_FREQUENCY_MIN_HZ, _DEFAULT_FREQUENCY_MAX_HZ,
        ])
        cfg = DribbleDetectionConfig(
            oscillation_ratio=float(config_dict.get(
                "oscillation_ratio", _DEFAULT_OSCILLATION_RATIO,
            )),
            frequency_min_hz=float(freq_range[0]),
            frequency_max_hz=float(freq_range[1]),
            min_consecutive_bounces=int(config_dict.get(
                "min_consecutive_bounces", _DEFAULT_MIN_CONSECUTIVE_BOUNCES,
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
        """프레임 시퀀스에서 드리블 동작을 감지한다.

        Args:
            snapshots: 프레임 순서 MotionSnapshot 목록 (단일 선수).

        Returns:
            감지된 드리블 후보 목록 (시간순).
        """
        with self._lock:
            return self._detect_impl(snapshots)

    def _detect_impl(
        self,
        snapshots: list[MotionSnapshot],
    ) -> list[DetectionCandidate]:
        """감지 구현."""
        if len(snapshots) < 3:
            return []

        candidates: list[DetectionCandidate] = []

        # 좌/우 각각 바운스 패턴 분석 (어깨 포함 → 체형 비례 계산)
        right_bounces = self._find_bounces(
            snapshots,
            wrist=JointType.RIGHT_WRIST,
            hip=JointType.RIGHT_HIP,
            shoulder=JointType.RIGHT_SHOULDER,
        )
        left_bounces = self._find_bounces(
            snapshots,
            wrist=JointType.LEFT_WRIST,
            hip=JointType.LEFT_HIP,
            shoulder=JointType.LEFT_SHOULDER,
        )

        # 바운스 구간을 드리블 세그먼트로 병합
        all_bounces = self._merge_bounces(right_bounces, left_bounces)

        for bounce_group in all_bounces:
            candidate = self._build_candidate(snapshots, bounce_group)
            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _find_bounces(
        self,
        snapshots: list[MotionSnapshot],
        wrist: JointType,
        hip: JointType,
        shoulder: JointType,
    ) -> list[dict[str, float | int]]:
        """한 손의 바운스 패턴을 감지한다.

        손목 y좌표의 로컬 최솟값(바운스 최저점)을 찾아 바운스를 식별.
        바운스 조건 (체형 비례):
            1. 손목 y < 엉덩이 y (물리적 사실: 드리블 시 손이 엉덩이 아래)
            2. y좌표가 로컬 최솟값 (내려갔다가 올라감 = 바운스 최저점)
            3. 진폭 ≥ torso_length × oscillation_ratio (체형 비례 임계치)

        Args:
            snapshots: 프레임 스냅샷.
            wrist: 손목 관절.
            hip: 엉덩이 관절.
            shoulder: 어깨 관절 (몸통 길이 계산용).

        Returns:
            바운스 정보 목록 [{frame_index, y_min, amplitude, hand}].
        """
        bounces: list[dict[str, float | int]] = []
        # 양손 독립 분석: 1.0=오른손, 0.0=왼손 (자동 판별, 주손 하드코딩 없음)
        hand_label = 1.0 if wrist == JointType.RIGHT_WRIST else 0.0

        # 관절 y좌표 시퀀스 추출
        wrist_heights: list[float | None] = []
        hip_heights: list[float | None] = []
        shoulder_heights: list[float | None] = []

        for snap in snapshots:
            wrist_pos = snap.get_position(wrist)
            hip_pos = snap.get_position(hip)
            shoulder_pos = snap.get_position(shoulder)
            wrist_heights.append(wrist_pos[1] if wrist_pos else None)
            hip_heights.append(hip_pos[1] if hip_pos else None)
            shoulder_heights.append(shoulder_pos[1] if shoulder_pos else None)

        for i in range(1, len(wrist_heights) - 1):
            curr_y = wrist_heights[i]
            prev_y = wrist_heights[i - 1]
            next_y = wrist_heights[i + 1]
            hip_y = hip_heights[i]
            shoulder_y = shoulder_heights[i]

            if curr_y is None or prev_y is None or next_y is None or hip_y is None:
                continue

            # 몸통 길이 (체형 비례 기준 단위)
            if shoulder_y is not None:
                torso_length = abs(shoulder_y - hip_y)
            else:
                torso_length = _DEFAULT_FALLBACK_TORSO_PX

            # 안전 하한: torso_length가 비정상적으로 작으면 폴백
            if torso_length < 20.0:
                torso_length = _DEFAULT_FALLBACK_TORSO_PX

            # 로컬 최솟값 (이전보다 낮고 다음보다 낮음 = 바운스 최저점)
            if curr_y < prev_y and curr_y < next_y:
                # 물리적 조건: 손목이 엉덩이 아래 (Y-up: 낮은 Y = 낮은 위치)
                if curr_y < hip_y:
                    # 진폭: 체형 비례 기준 (torso_length × ratio)
                    amplitude = max(prev_y - curr_y, next_y - curr_y)
                    min_amplitude = torso_length * self._config.oscillation_ratio
                    if amplitude >= min_amplitude:
                        bounces.append({
                            "frame_index": i,
                            "y_min": curr_y,
                            "amplitude": amplitude,
                            "hand": hand_label,
                        })

        return bounces

    def _merge_bounces(
        self,
        right_bounces: list[dict[str, float | int]],
        left_bounces: list[dict[str, float | int]],
    ) -> list[list[dict[str, float | int]]]:
        """좌/우 바운스를 병합하여 드리블 그룹을 생성한다.

        연속된 바운스를 하나의 드리블 세그먼트로 묶는다.
        빈도 기반: 바운스 간 간격이 frequency_range 내면 연속.

        Args:
            right_bounces: 오른손 바운스.
            left_bounces: 왼손 바운스.

        Returns:
            드리블 그룹 목록 (각 그룹은 연속 바운스 목록).
        """
        # 전체 바운스를 프레임 순으로 정렬
        all_bounces = sorted(
            right_bounces + left_bounces,
            key=lambda b: b["frame_index"],
        )

        if len(all_bounces) < self._config.min_consecutive_bounces:
            return []

        # 연속 바운스 그룹화
        groups: list[list[dict[str, float | int]]] = []
        current_group: list[dict[str, float | int]] = [all_bounces[0]]

        for i in range(1, len(all_bounces)):
            prev_frame = int(current_group[-1]["frame_index"])
            curr_frame = int(all_bounces[i]["frame_index"])
            gap_frames = curr_frame - prev_frame

            # 프레임 간격이 빈도 범위에 맞는지 확인 (30fps 기준)
            # frequency_max_hz → 최소 간격 = fps / freq_max
            # frequency_min_hz → 최대 간격 = fps / freq_min
            # 30fps 기준으로 계산하되, 2배 허용
            min_gap = max(1, int(30.0 / self._config.frequency_max_hz / 2))
            max_gap = int(30.0 / self._config.frequency_min_hz * 2)

            if min_gap <= gap_frames <= max_gap:
                current_group.append(all_bounces[i])
            else:
                if len(current_group) >= self._config.min_consecutive_bounces:
                    groups.append(current_group)
                current_group = [all_bounces[i]]

        if len(current_group) >= self._config.min_consecutive_bounces:
            groups.append(current_group)

        return groups

    def _build_candidate(
        self,
        snapshots: list[MotionSnapshot],
        bounce_group: list[dict[str, float | int]],
    ) -> DetectionCandidate | None:
        """바운스 그룹으로부터 DetectionCandidate를 생성한다.

        Args:
            snapshots: 전체 스냅샷.
            bounce_group: 연속 바운스 목록.

        Returns:
            DetectionCandidate 또는 None.
        """
        if not bounce_group:
            return None

        first_bounce = bounce_group[0]
        last_bounce = bounce_group[-1]

        start_idx = int(first_bounce["frame_index"])
        end_idx = int(last_bounce["frame_index"])

        # 시작/종료 여유 프레임 (바운스 전후 포함)
        start_idx = max(0, start_idx - 2)
        end_idx = min(len(snapshots) - 1, end_idx + 2)

        start_snap = snapshots[start_idx]
        end_snap = snapshots[end_idx]

        # --- 드리블 빈도 계산 (Hz) ---
        bounce_count = len(bounce_group)
        duration_frames = end_idx - start_idx + 1
        fps_estimate = 30.0  # 기본 fps
        if duration_frames > 0 and bounce_count >= 2:
            duration_sec = duration_frames / fps_estimate
            frequency_hz = bounce_count / max(duration_sec, 0.01)
        else:
            frequency_hz = 0.0

        # --- 평균 진동 크기 ---
        avg_amplitude = sum(
            float(b["amplitude"]) for b in bounce_group
        ) / max(bounce_count, 1)

        # --- 주 사용 손 ---
        right_count = sum(1 for b in bounce_group if float(b["hand"]) == 1.0)

        # --- 신뢰도 계산 ---
        confidence = self._compute_confidence(
            bounce_count, frequency_hz, avg_amplitude,
        )

        if confidence < _MIN_CONFIDENCE:
            return None

        evidence: dict[str, float] = {
            "bounce_count": float(bounce_count),
            "frequency_hz": frequency_hz,
            "avg_amplitude_px": avg_amplitude,
            "duration_frames": float(duration_frames),
            "right_hand_ratio": right_count / max(bounce_count, 1),
        }

        return DetectionCandidate(
            action_type=ActionType.DRIBBLING,
            confidence=confidence,
            start_frame=start_snap.frame_index,
            end_frame=end_snap.frame_index,
            start_time=start_snap.timestamp,
            end_time=end_snap.timestamp,
            player_tracking_id=start_snap.player_tracking_id,
            evidence=evidence,
        )

    def _compute_confidence(
        self,
        bounce_count: int,
        frequency_hz: float,
        avg_amplitude: float,
    ) -> float:
        """드리블 신뢰도를 계산한다.

        가중치:
            - 바운스 수: 0.35 (연속성 강할수록 확실)
            - 빈도 적합성: 0.35 (1~5 Hz 범위 내)
            - 진동 크기: 0.30 (충분한 상하 운동)

        Args:
            bounce_count: 바운스 수.
            frequency_hz: 드리블 빈도 (Hz).
            avg_amplitude: 평균 진동 크기 (px).

        Returns:
            신뢰도 (0~1).
        """
        # 바운스 수 점수 (2→0.5, 5→0.8, 10+→1.0)
        bounce_score = min(1.0, bounce_count / 10.0) * 0.8 + 0.2 * min(
            1.0, bounce_count / self._config.min_consecutive_bounces,
        )

        # 빈도 적합성 점수 (범위 내: 1.0, 범위 밖: 감소)
        if self._config.frequency_min_hz <= frequency_hz <= self._config.frequency_max_hz:
            freq_score = 1.0
        elif frequency_hz < self._config.frequency_min_hz:
            freq_score = max(0.0, frequency_hz / max(self._config.frequency_min_hz, 0.1))
        else:
            overshoot = frequency_hz - self._config.frequency_max_hz
            freq_score = max(0.0, 1.0 - overshoot / self._config.frequency_max_hz)

        # 진동 크기 점수: amplitude > 0이면 기본 0.5, 큰 진폭일수록 증가
        # (이미 _find_bounces에서 체형 비례 필터를 통과했으므로 기본 점수 부여)
        amplitude_score = min(1.0, 0.5 + avg_amplitude / max(avg_amplitude * 2.0, 1.0))

        return (
            bounce_score * 0.35
            + freq_score * 0.35
            + amplitude_score * 0.30
        )

    @property
    def config(self) -> DribbleDetectionConfig:
        """현재 설정 반환."""
        return self._config

    def __repr__(self) -> str:
        return (
            f"DribbleDetector("
            f"osc_ratio={self._config.oscillation_ratio}, "
            f"freq=[{self._config.frequency_min_hz}-{self._config.frequency_max_hz}]Hz, "
            f"bounces≥{self._config.min_consecutive_bounces})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "DribbleDetectionConfig",
    "DribbleDetector",
]

__version__ = "1.0.0"
