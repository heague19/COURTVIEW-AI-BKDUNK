# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/detection
파일: rebound_detector.py
설명: 리바운드 동작 감지기 (Tier 1)
      - 점프 + 골대 근접 + 팔 위로 뻗기 패턴으로 리바운드 감지
      - COM 수직 변위 기반 점프 감지
      - 모든 거리 임계치는 체형 비례 (torso_length 기준)

      학술 근거:
        - Ziv, G. & Lidor, R. (2009). "Physical attributes, physiological
          characteristics, on-court performances and nutritional strategies
          of female and male basketball players." Sports Medicine, 39(7), 547-568.
          (점프 높이 30-60cm, 리바운드 시 팔 높이)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - configs/analysis/motion_analysis.yaml: detection.rebound 설정
    - motion_analysis/models.py: MotionSnapshot, DetectionCandidate

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/dto/motion_dto.py: ActionType

소비자:
    - motion_analysis/classification/action_classifier.py
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

# --- 리바운드 감지 기본 임계치 (체형 비례 기준) ---
# torso_length = 어깨 y - 엉덩이 y (체형별 자동 적응)
# Ziv & Lidor (2009): 리바운드 점프 30-60cm ≈ 몸통 길이의 50-100%
_DEFAULT_JUMP_HEIGHT_RATIO: Final[float] = 0.25      # 최소 점프: 몸통 길이의 25%
_DEFAULT_PROXIMITY_TORSO_RATIO: Final[float] = 6.0   # 골대 근접: 몸통 길이 × 6 이내
_DEFAULT_ARM_ABOVE_HEAD_RATIO: Final[float] = 1.1    # 손목 > 머리 높이 비율 (관절 상대)
_DEFAULT_FALLBACK_TORSO_PX: Final[float] = 200.0     # 몸통 측정 불가 시 폴백 (px)

_MIN_CONFIDENCE: Final[float] = 0.3
_MIN_REBOUND_FRAMES: Final[int] = 5     # 최소 리바운드 동작 프레임
_MAX_REBOUND_FRAMES: Final[int] = 60    # 최대 리바운드 동작 프레임 (2초@30fps)


# =============================================================================
# 리바운드 감지 설정
# =============================================================================

@dataclass(slots=True)
class ReboundDetectionConfig:
    """
    리바운드 감지 임계치 설정 (체형 비례 기준).

    모든 거리 임계치는 torso_length 대비 비율로 동작하여
    카메라 거리, 해상도, 체형에 무관하게 일관된 감지 성능을 보장한다.

    Attributes:
        jump_height_ratio: 최소 점프 높이 (몸통 길이 대비 비율)
        proximity_torso_ratio: 골대 근접 거리 (몸통 길이 배수)
        arm_above_head_ratio: 손목 높이 / 머리 높이 비율 (1.0+ = 머리 위)
    """

    jump_height_ratio: float = _DEFAULT_JUMP_HEIGHT_RATIO
    proximity_torso_ratio: float = _DEFAULT_PROXIMITY_TORSO_RATIO
    arm_above_head_ratio: float = _DEFAULT_ARM_ABOVE_HEAD_RATIO


# =============================================================================
# 리바운드 감지기
# =============================================================================

class ReboundDetector:
    """
    리바운드 동작 감지기 (체형 비례 기준).

    프레임 시퀀스를 분석하여 리바운드 동작 후보를 감지한다.

    감지 기준 (3가지 조건 복합, 관절 상대 위치 기반):
        1. 점프: 발목 수직 변위 ≥ torso_length × jump_height_ratio
        2. 골대 근접: 선수-골대 거리 ≤ torso_length × proximity_torso_ratio
        3. 팔 위로 뻗기: 손목 높이 ≥ 머리 높이 × arm_above_head_ratio

    사용 예:
        >>> detector = ReboundDetector()
        >>> candidates = detector.detect(snapshots)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_config", "_lock")

    def __init__(self, config: ReboundDetectionConfig | None = None) -> None:
        self._config = config or ReboundDetectionConfig()
        self._lock = RLock()

    @classmethod
    def from_yaml(cls, config_dict: dict) -> ReboundDetector:
        """YAML 설정에서 생성.

        Args:
            config_dict: detection.rebound 섹션 딕셔너리.

        Returns:
            ReboundDetector 인스턴스.
        """
        cfg = ReboundDetectionConfig(
            jump_height_ratio=float(config_dict.get(
                "jump_height_ratio", _DEFAULT_JUMP_HEIGHT_RATIO,
            )),
            proximity_torso_ratio=float(config_dict.get(
                "proximity_torso_ratio", _DEFAULT_PROXIMITY_TORSO_RATIO,
            )),
            arm_above_head_ratio=float(config_dict.get(
                "arm_above_head_ratio", _DEFAULT_ARM_ABOVE_HEAD_RATIO,
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
        """프레임 시퀀스에서 리바운드 동작을 감지한다.

        Args:
            snapshots: 프레임 순서 MotionSnapshot 목록 (단일 선수).

        Returns:
            감지된 리바운드 후보 목록 (시간순).
        """
        with self._lock:
            return self._detect_impl(snapshots)

    def _detect_impl(
        self,
        snapshots: list[MotionSnapshot],
    ) -> list[DetectionCandidate]:
        """감지 구현."""
        if len(snapshots) < _MIN_REBOUND_FRAMES:
            return []

        # 체형 기준 단위 계산 (전 프레임 평균 torso_length)
        torso_length = self._compute_avg_torso_length(snapshots)

        # 점프 구간 감지
        jump_segments = self._find_jump_segments(snapshots, torso_length)

        candidates: list[DetectionCandidate] = []
        for seg_start, seg_end, jump_height_ratio in jump_segments:
            candidate = self._evaluate_rebound(
                snapshots, seg_start, seg_end,
                jump_height_ratio, torso_length,
            )
            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _compute_avg_torso_length(
        self,
        snapshots: list[MotionSnapshot],
    ) -> float:
        """전체 시퀀스의 평균 몸통 길이를 계산한다.

        Args:
            snapshots: 스냅샷 목록.

        Returns:
            평균 torso_length (px). 측정 불가 시 폴백값.
        """
        torso_sum = 0.0
        torso_count = 0

        for snap in snapshots:
            # 좌/우 평균
            for shoulder_jt, hip_jt in [
                (JointType.LEFT_SHOULDER, JointType.LEFT_HIP),
                (JointType.RIGHT_SHOULDER, JointType.RIGHT_HIP),
            ]:
                shoulder = snap.get_position(shoulder_jt)
                hip = snap.get_position(hip_jt)
                if shoulder is not None and hip is not None:
                    length = abs(shoulder[1] - hip[1])
                    if length > 20.0:  # 비정상적으로 작은 값 필터
                        torso_sum += length
                        torso_count += 1

        if torso_count == 0:
            return _DEFAULT_FALLBACK_TORSO_PX

        return torso_sum / torso_count

    def _find_jump_segments(
        self,
        snapshots: list[MotionSnapshot],
        torso_length: float,
    ) -> list[tuple[int, int, float]]:
        """점프 구간을 감지한다.

        발목 y좌표의 상승→하강 패턴으로 점프를 식별.
        임계치는 torso_length × jump_height_ratio (체형 비례).

        Args:
            snapshots: 스냅샷 목록.
            torso_length: 평균 몸통 길이 (px).

        Returns:
            (시작 인덱스, 종료 인덱스, 점프 높이 비율) 목록.
        """
        segments: list[tuple[int, int, float]] = []

        # 발목 높이 시계열 추출
        heights = self._extract_ankle_heights(snapshots)

        valid_heights = [h for h in heights if h is not None]
        if not valid_heights:
            return segments

        baseline = min(valid_heights)

        # 점프 임계치: 몸통 길이 × ratio (체형 비례)
        threshold_px = torso_length * self._config.jump_height_ratio
        in_jump = False
        jump_start = 0
        peak_height = 0.0

        for i, h in enumerate(heights):
            if h is None:
                continue

            elevation = h - baseline

            if not in_jump:
                # 점프 시작: 임계치의 50% 이상 상승
                if elevation >= threshold_px * 0.5:
                    in_jump = True
                    jump_start = max(0, i - 2)
                    peak_height = elevation
            else:
                if elevation > peak_height:
                    peak_height = elevation

                # 점프 종료: 임계치의 30% 아래로 복귀
                if elevation < threshold_px * 0.3:
                    jump_end = min(len(heights) - 1, i + 2)
                    duration = jump_end - jump_start

                    if (
                        peak_height >= threshold_px
                        and _MIN_REBOUND_FRAMES <= duration <= _MAX_REBOUND_FRAMES
                    ):
                        # 점프 높이를 몸통 대비 비율로 저장
                        jump_ratio = peak_height / max(torso_length, 1.0)
                        segments.append((jump_start, jump_end, jump_ratio))

                    in_jump = False
                    peak_height = 0.0

        return segments

    def _extract_ankle_heights(
        self,
        snapshots: list[MotionSnapshot],
    ) -> list[float | None]:
        """발목 중점 y좌표를 추출한다.

        COM이 있으면 COM y좌표, 없으면 좌/우 발목 평균.

        Args:
            snapshots: 스냅샷 목록.

        Returns:
            프레임별 높이 (px) 또는 None.
        """
        heights: list[float | None] = []

        for snap in snapshots:
            if snap.com_position is not None:
                heights.append(snap.com_position[1])
                continue

            left_ankle = snap.get_position(JointType.LEFT_ANKLE)
            right_ankle = snap.get_position(JointType.RIGHT_ANKLE)

            if left_ankle is not None and right_ankle is not None:
                heights.append((left_ankle[1] + right_ankle[1]) / 2.0)
            elif left_ankle is not None:
                heights.append(left_ankle[1])
            elif right_ankle is not None:
                heights.append(right_ankle[1])
            else:
                heights.append(None)

        return heights

    def _evaluate_rebound(
        self,
        snapshots: list[MotionSnapshot],
        seg_start: int,
        seg_end: int,
        jump_height_ratio: float,
        torso_length: float,
    ) -> DetectionCandidate | None:
        """점프 구간이 리바운드인지 평가한다.

        3가지 조건 검증:
            1. 점프 높이 ≥ threshold (이미 충족)
            2. 골대 근접 (구간 중 1회 이상)
            3. 팔 위로 뻗기 (구간 중 1회 이상)

        Args:
            snapshots: 전체 스냅샷.
            seg_start: 점프 구간 시작.
            seg_end: 점프 구간 종료.
            jump_height_ratio: 점프 높이 (몸통 대비 비율).
            torso_length: 평균 몸통 길이 (px).

        Returns:
            DetectionCandidate 또는 None.
        """
        proximity_score, min_dist_ratio = self._check_hoop_proximity(
            snapshots, seg_start, seg_end, torso_length,
        )

        arm_above_score, max_arm_ratio = self._check_arms_above_head(
            snapshots, seg_start, seg_end,
        )

        confidence = self._compute_confidence(
            jump_height_ratio, proximity_score, arm_above_score,
        )

        if confidence < _MIN_CONFIDENCE:
            return None

        start_snap = snapshots[seg_start]
        end_snap = snapshots[min(seg_end, len(snapshots) - 1)]

        evidence: dict[str, float] = {
            "jump_height_torso_ratio": jump_height_ratio,
            "proximity_torso_ratio": min_dist_ratio,
            "arm_above_head_ratio": max_arm_ratio,
            "proximity_score": proximity_score,
            "arm_above_score": arm_above_score,
            "duration_frames": float(seg_end - seg_start + 1),
        }

        return DetectionCandidate(
            action_type=ActionType.REBOUNDING,
            confidence=confidence,
            start_frame=start_snap.frame_index,
            end_frame=end_snap.frame_index,
            start_time=start_snap.timestamp,
            end_time=end_snap.timestamp,
            player_tracking_id=start_snap.player_tracking_id,
            evidence=evidence,
        )

    def _check_hoop_proximity(
        self,
        snapshots: list[MotionSnapshot],
        seg_start: int,
        seg_end: int,
        torso_length: float,
    ) -> tuple[float, float]:
        """구간 내 골대 근접도를 확인한다 (체형 비례).

        Args:
            snapshots: 스냅샷.
            seg_start: 시작.
            seg_end: 종료.
            torso_length: 평균 몸통 길이 (px).

        Returns:
            (근접 점수 0~1, 최소 거리 torso 비율).
        """
        min_dist_px = float("inf")
        hoop_found = False

        for i in range(seg_start, min(seg_end + 1, len(snapshots))):
            snap = snapshots[i]

            if snap.hoop_position is None:
                continue

            hoop_found = True

            # 선수 위치 (COM 또는 엉덩이 중점)
            player_pos = snap.com_position
            if player_pos is None:
                left_hip = snap.get_position(JointType.LEFT_HIP)
                right_hip = snap.get_position(JointType.RIGHT_HIP)
                if left_hip and right_hip:
                    player_pos = (
                        (left_hip[0] + right_hip[0]) / 2.0,
                        (left_hip[1] + right_hip[1]) / 2.0,
                        (left_hip[2] + right_hip[2]) / 2.0,
                    )

            if player_pos is None:
                continue

            # 수평 거리 (코트 평면 xz)
            dx = player_pos[0] - snap.hoop_position[0]
            dz = player_pos[2] - snap.hoop_position[2]
            dist_px = (dx * dx + dz * dz) ** 0.5

            min_dist_px = min(min_dist_px, dist_px)

        if not hoop_found:
            # 골대 위치 미제공 → 조건 무시 (0.5 기본 점수)
            return 0.5, 0.0

        if min_dist_px == float("inf"):
            return 0.0, 0.0

        # 거리를 몸통 길이 대비 비율로 변환
        dist_ratio = min_dist_px / max(torso_length, 1.0)
        threshold_ratio = self._config.proximity_torso_ratio

        if dist_ratio <= threshold_ratio:
            score = 1.0
        else:
            excess = dist_ratio - threshold_ratio
            score = max(0.0, 1.0 - excess / threshold_ratio)

        return score, dist_ratio

    def _check_arms_above_head(
        self,
        snapshots: list[MotionSnapshot],
        seg_start: int,
        seg_end: int,
    ) -> tuple[float, float]:
        """구간 내 팔 위로 뻗기를 확인한다.

        양쪽 손목 중 하나라도 머리(NOSE) 높이 × ratio 이상이면 충족.
        이미 관절 상대 비율이므로 수정 불필요.

        Args:
            snapshots: 스냅샷.
            seg_start: 시작.
            seg_end: 종료.

        Returns:
            (팔 뻗기 점수 0~1, 최대 비율).
        """
        max_ratio = 0.0
        checked = False

        for i in range(seg_start, min(seg_end + 1, len(snapshots))):
            snap = snapshots[i]

            nose_pos = snap.get_position(JointType.NOSE)
            if nose_pos is None:
                continue

            head_height = nose_pos[1]
            if head_height <= 0:
                continue

            checked = True

            for wrist in (JointType.RIGHT_WRIST, JointType.LEFT_WRIST):
                wrist_pos = snap.get_position(wrist)
                if wrist_pos is None:
                    continue

                ratio = wrist_pos[1] / head_height
                max_ratio = max(max_ratio, ratio)

        if not checked:
            return 0.3, 0.0

        threshold = self._config.arm_above_head_ratio
        if max_ratio >= threshold:
            score = 1.0
        elif max_ratio >= 1.0:
            score = 0.5 + 0.5 * ((max_ratio - 1.0) / max(threshold - 1.0, 0.01))
        else:
            score = max(0.0, max_ratio / max(threshold, 0.01))

        return score, max_ratio

    def _compute_confidence(
        self,
        jump_height_ratio: float,
        proximity_score: float,
        arm_above_score: float,
    ) -> float:
        """리바운드 감지 신뢰도를 계산한다.

        가중치:
            - 점프 높이: 0.35 (필수 조건)
            - 골대 근접: 0.35 (리바운드 위치)
            - 팔 뻗기: 0.30 (리바운드 동작)

        Args:
            jump_height_ratio: 점프 높이 (몸통 대비 비율).
            proximity_score: 골대 근접 점수 (0~1).
            arm_above_score: 팔 뻗기 점수 (0~1).

        Returns:
            신뢰도 (0~1).
        """
        threshold = self._config.jump_height_ratio
        if jump_height_ratio >= threshold:
            jump_score = min(1.0, jump_height_ratio / max(threshold, 0.01))
        else:
            jump_score = jump_height_ratio / max(threshold, 0.01)

        return (
            jump_score * 0.35
            + proximity_score * 0.35
            + arm_above_score * 0.30
        )

    @property
    def config(self) -> ReboundDetectionConfig:
        """현재 설정 반환."""
        return self._config

    def __repr__(self) -> str:
        return (
            f"ReboundDetector("
            f"jump≥torso×{self._config.jump_height_ratio}, "
            f"hoop≤torso×{self._config.proximity_torso_ratio}, "
            f"arm≥{self._config.arm_above_head_ratio}x)"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "ReboundDetectionConfig",
    "ReboundDetector",
]

__version__ = "1.0.0"
