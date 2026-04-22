# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/classification
파일: dribble_classifier.py
설명: 드리블 세부 유형 분류기 (Tier 2)
      - DRIBBLING으로 감지된 후보를 13가지 DribbleType으로 세분화
      - 손 전환 패턴, 공 경로, 신체 회전 등 기반 분류
      - 모든 거리/속도는 torso-length (어깨~엉덩이) 기반 — 카메라 독립

      학술 근거:
        - Arias, J.L. et al. (2012). "Review of biomechanical factors in
          basketball ball handling." J. Human Sport & Exercise, 7(1), 318-329.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - shared/dto/motion_dto.py: DribbleType (13종)
    - configs/analysis/motion_analysis.yaml: classification.dribble_types

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/dto/motion_dto.py: DribbleType

소비자:
    - motion_analysis/phase_analysis/dribble_phase_analyzer.py
    - motion_analysis/form_evaluation/dribble_form_evaluator.py
"""

from __future__ import annotations

import logging
import math
from threading import RLock
from typing import Final

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import DribbleType

from motion_analysis.models import DetectionCandidate, MotionSnapshot


# =============================================================================
# 상수 — 모든 거리/속도는 torso-length 비율 (어깨~엉덩이 = 1.0)
# 실제 성인 torso ≈ 0.5m 기준, 물리 거리 → torso-length 변환
# =============================================================================

logger: Final = logging.getLogger(__name__)

# --- 크로스오버 감지 ---
_CROSSOVER_HAND_SWITCH_FRAMES: Final[int] = 10   # 좌우 전환 최대 프레임
_CROSSOVER_BALL_TRANSFER_RATIO: Final[float] = 0.3  # 무릎 이하

# --- 비하인드 더 백: 손목이 엉덩이 z 기준 torso 10% 뒤 ---
_BEHIND_BACK_WRIST_BEHIND_RATIO: Final[float] = 0.1

# --- 스핀 무브 ---
_SPIN_YAW_CHANGE_DEG: Final[float] = 270.0   # 270° 이상 회전

# --- 헤지테이션 ---
_HESITATION_SPEED_DROP_RATIO: Final[float] = 0.4  # 속도 40% 이하로 감소

# --- 이동 속도 기준 (torso-length/s) ---
_SPEED_DRIBBLE_MIN_TORSO_S: Final[float] = 6.0      # 3.0 m/s / 0.5m
_POWER_DRIBBLE_MAX_TORSO_S: Final[float] = 2.0      # 1.0 m/s / 0.5m

# --- 후방 이동 임계 (torso-length) ---
_BACKWARD_MIN_TORSO: Final[float] = 0.6             # 0.3m / 0.5m
_PULLBACK_MIN_SPEED_TORSO_S: Final[float] = 3.0     # 1.5 m/s / 0.5m
_EURO_STEP_MIN_SPEED_TORSO_S: Final[float] = 4.0    # 2.0 m/s / 0.5m

# --- torso 추정 불가 시 폴백 ---
_DEFAULT_FALLBACK_TORSO_PX: Final[float] = 200.0


# =============================================================================
# 드리블 세부 분류기
# =============================================================================

class DribbleClassifier:
    """
    드리블 세부 유형 분류기.

    DRIBBLING으로 감지된 DetectionCandidate를 받아
    13가지 DribbleType 중 하나로 세분화한다.

    모든 거리/속도는 torso-length 기반 (카메라/해상도 독립).

    분류 기준 (복합 조건 + 우선순위):
        1. 스핀 무브: 몸체 270°+ 회전
        2. 비하인드 더 백: 손목이 엉덩이 뒤로 이동
        3. 비트윈 더 레그: 양 다리 사이 공 통과
        4. 크로스오버: 좌/우 손 전환 + 낮은 공 경로
        5. 헤지테이션: 급정지 → 재가속
        6. 인앤아웃: 안쪽→바깥쪽 페이크
        7. 풀백/스텝백: 후방 이동
        8. 유로스텝: 좌우 교차 스텝 + 드리블
        9. 파워 드리블: 저속
        10. 스피드 드리블: 고속 직선
        11. 컨트롤 드리블: 기본 (위 조건 미충족)

    사용 예:
        >>> classifier = DribbleClassifier()
        >>> dribble_type, conf = classifier.classify(candidate, snapshots)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_lock",)

    def __init__(self) -> None:
        self._lock = RLock()

    # -------------------------------------------------------------------------
    # 핵심 분류 로직
    # -------------------------------------------------------------------------

    def classify(
        self,
        candidate: DetectionCandidate,
        snapshots: list[MotionSnapshot],
    ) -> tuple[DribbleType, float]:
        """드리블 후보를 세부 유형으로 분류한다.

        Args:
            candidate: DRIBBLING DetectionCandidate.
            snapshots: 해당 구간 + 전후 MotionSnapshot.

        Returns:
            (DribbleType, 분류 신뢰도) 튜플.
        """
        with self._lock:
            return self._classify_impl(candidate, snapshots)

    def _classify_impl(
        self,
        candidate: DetectionCandidate,
        snapshots: list[MotionSnapshot],
    ) -> tuple[DribbleType, float]:
        """분류 구현."""
        segment = [
            s for s in snapshots
            if candidate.start_frame <= s.frame_index <= candidate.end_frame
        ]
        if not segment:
            return DribbleType.CONTROL_DRIBBLE, 0.5

        features = self._extract_dribble_features(candidate, segment)
        return self._apply_rules(features)

    def _extract_dribble_features(
        self,
        candidate: DetectionCandidate,
        segment: list[MotionSnapshot],
    ) -> dict[str, float]:
        """드리블 분류용 특성을 추출한다 (체형 비례 단위).

        Args:
            candidate: 감지 후보.
            segment: 구간 내 스냅샷.

        Returns:
            특성 딕셔너리 (torso-length 기반).
        """
        features: dict[str, float] = {}

        # torso 기준 길이 계산
        torso_px = self._compute_avg_torso_length(segment)
        features["torso_length_px"] = torso_px

        # evidence에서 기본 정보
        features["right_hand_ratio"] = candidate.evidence.get("right_hand_ratio", 0.5)
        features["frequency_hz"] = candidate.evidence.get("frequency_hz", 2.5)
        features["bounce_count"] = candidate.evidence.get("bounce_count", 2.0)
        features["duration_frames"] = float(candidate.duration_frames)

        # --- 손 전환 감지 ---
        hand_switches = self._count_hand_switches(segment)
        features["hand_switch_count"] = float(hand_switches)

        # --- 이동 속도 (torso-length/s) ---
        avg_speed = self._estimate_movement_speed(segment, torso_px)
        features["avg_speed_torso_s"] = avg_speed

        # --- 몸체 회전 (yaw 변화, °) ---
        total_yaw_change = self._compute_yaw_change(segment)
        features["total_yaw_change_deg"] = total_yaw_change

        # --- 손목 후방 이동 감지 ---
        wrist_behind_hip = self._detect_wrist_behind_hip(segment, torso_px)
        features["wrist_behind_hip"] = 1.0 if wrist_behind_hip else 0.0

        # --- 다리 사이 공 통과 감지 ---
        between_legs = self._detect_between_legs(segment)
        features["between_legs"] = 1.0 if between_legs else 0.0

        # --- 속도 변화 (헤지테이션 감지) ---
        speed_drop_ratio = self._detect_speed_drop(segment)
        features["speed_drop_ratio"] = speed_drop_ratio

        # --- 후방 이동 감지 (torso-length) ---
        backward_motion = self._detect_backward_motion(segment, torso_px)
        features["backward_motion_torso"] = backward_motion

        return features

    def _apply_rules(
        self,
        features: dict[str, float],
    ) -> tuple[DribbleType, float]:
        """규칙 기반 분류 (torso-length 단위).

        Args:
            features: 추출된 특성.

        Returns:
            (DribbleType, confidence).
        """
        hand_switches = features.get("hand_switch_count", 0.0)
        speed = features.get("avg_speed_torso_s", 0.0)
        yaw_change = features.get("total_yaw_change_deg", 0.0)
        wrist_behind = features.get("wrist_behind_hip", 0.0)
        between_legs = features.get("between_legs", 0.0)
        speed_drop = features.get("speed_drop_ratio", 1.0)
        backward = features.get("backward_motion_torso", 0.0)

        # 1. 스핀 무브: 몸체 대폭 회전
        if yaw_change >= _SPIN_YAW_CHANGE_DEG:
            return DribbleType.SPIN, min(1.0, 0.5 + yaw_change / 720.0)

        # 2. 비하인드 더 백: 손목이 엉덩이 뒤
        if wrist_behind > 0.5:
            return DribbleType.BEHIND_BACK, 0.7

        # 3. 비트윈 더 레그: 다리 사이 공 통과
        if between_legs > 0.5:
            return DribbleType.BETWEEN_LEGS, 0.7

        # 4. 크로스오버: 좌우 손 전환 + 낮은 바운스
        if hand_switches >= 1.0:
            return DribbleType.CROSSOVER, min(1.0, 0.5 + hand_switches / 5.0)

        # 5. 헤지테이션: 급속도 감소
        if speed_drop <= _HESITATION_SPEED_DROP_RATIO:
            return DribbleType.HESITATION, 0.65

        # 6. 인앤아웃: 손 전환 없이 안팎 페이크 (변동 높은 바운스)
        frequency = features.get("frequency_hz", 2.5)
        if frequency >= 3.5 and hand_switches < 1.0:
            return DribbleType.IN_AND_OUT, 0.6

        # 7. 풀백/스텝백: 후방 이동
        if backward >= _BACKWARD_MIN_TORSO:
            if speed >= _PULLBACK_MIN_SPEED_TORSO_S:
                return DribbleType.PULL_BACK, 0.65
            return DribbleType.STEP_BACK, 0.6

        # 8. 유로스텝: 좌우 교차 이동 + 드리블
        if yaw_change >= 90.0 and speed >= _EURO_STEP_MIN_SPEED_TORSO_S:
            return DribbleType.EURO_STEP, 0.6

        # 9. 파워 드리블: 저속 + 낮은 바운스
        if speed < _POWER_DRIBBLE_MAX_TORSO_S:
            return DribbleType.POWER_DRIBBLE, 0.7

        # 10. 스피드 드리블: 고속 직선
        if speed >= _SPEED_DRIBBLE_MIN_TORSO_S:
            return DribbleType.SPEED_DRIBBLE, min(1.0, 0.5 + speed / 14.0)

        # SHAMGOD: 규칙 기반 분류 불가 — 향후 학습 기반 분류 대상
        # 크로스오버와 유사하나 손 전환 방향이 역방향이라
        # 포즈 키포인트만으로는 구분이 어려움 (12/13종 구현)

        # 12. 기본: 컨트롤 드리블
        return DribbleType.CONTROL_DRIBBLE, 0.7

    # -------------------------------------------------------------------------
    # 특성 추출 보조 메서드
    # -------------------------------------------------------------------------

    def _compute_avg_torso_length(self, segment: list[MotionSnapshot]) -> float:
        """어깨~엉덩이 평균 거리를 계산한다 (px).

        좌/우 어깨~엉덩이 y 거리의 전체 프레임 평균.
        추정 불가 시 폴백값 반환.

        Args:
            segment: 구간 스냅샷.

        Returns:
            torso 길이 (px).
        """
        lengths: list[float] = []
        for snap in segment:
            for shoulder, hip in (
                (JointType.RIGHT_SHOULDER, JointType.RIGHT_HIP),
                (JointType.LEFT_SHOULDER, JointType.LEFT_HIP),
            ):
                s_pos = snap.get_position(shoulder)
                h_pos = snap.get_position(hip)
                if s_pos is not None and h_pos is not None:
                    length = abs(s_pos[1] - h_pos[1])
                    if length > 10.0:  # 최소 유효 길이
                        lengths.append(length)

        if lengths:
            return sum(lengths) / len(lengths)
        return _DEFAULT_FALLBACK_TORSO_PX

    def _count_hand_switches(self, segment: list[MotionSnapshot]) -> int:
        """좌/우 손 전환 횟수를 카운트한다.

        각 프레임에서 오른손/왼손 중 속력이 높은 쪽을 활성 손으로 판단.
        활성 손이 바뀌면 전환 1회.

        Args:
            segment: 구간 스냅샷.

        Returns:
            손 전환 횟수.
        """
        switches = 0
        prev_dominant: str | None = None

        for snap in segment:
            r_speed = snap.get_speed(JointType.RIGHT_WRIST)
            l_speed = snap.get_speed(JointType.LEFT_WRIST)

            if r_speed <= 0 and l_speed <= 0:
                continue

            current = "R" if r_speed >= l_speed else "L"

            if prev_dominant is not None and current != prev_dominant:
                switches += 1
            prev_dominant = current

        return switches

    def _estimate_movement_speed(
        self,
        segment: list[MotionSnapshot],
        torso_px: float,
    ) -> float:
        """구간 내 평균 이동 속도를 추정한다 (torso-length/s).

        Args:
            segment: 구간 스냅샷.
            torso_px: torso 기준 길이 (px).

        Returns:
            평균 이동 속도 (torso-length/s).
        """
        if len(segment) < 2:
            return 0.0

        first = segment[0]
        last = segment[-1]

        pos_first = first.com_position
        pos_last = last.com_position

        # 엉덩이 대체
        if pos_first is None or pos_last is None:
            for joint in (JointType.RIGHT_HIP, JointType.LEFT_HIP):
                pf = first.get_position(joint)
                pl = last.get_position(joint)
                if pf and pl:
                    pos_first = pf
                    pos_last = pl
                    break

        if pos_first is None or pos_last is None:
            return 0.0

        dx = pos_last[0] - pos_first[0]
        dz = pos_last[2] - pos_first[2]
        dist_px = (dx * dx + dz * dz) ** 0.5

        dt = (
            max(0.001, last.timestamp - first.timestamp)
            if last.timestamp > 0
            else len(segment) / 30.0
        )
        return (dist_px / torso_px) / dt

    def _compute_yaw_change(self, segment: list[MotionSnapshot]) -> float:
        """구간 내 몸체 yaw 누적 변화를 계산한다 (°).

        Args:
            segment: 구간 스냅샷.

        Returns:
            누적 yaw 변화 (°).
        """
        total_change = 0.0
        prev_yaw: float | None = None

        for snap in segment:
            if snap.body_orientation is None:
                continue

            yaw = snap.body_orientation[2]  # yaw_deg

            if prev_yaw is not None:
                # 각도 차이 (최단 경로, -180~180)
                diff = yaw - prev_yaw
                if diff > 180.0:
                    diff -= 360.0
                elif diff < -180.0:
                    diff += 360.0
                total_change += abs(diff)

            prev_yaw = yaw

        return total_change

    def _detect_wrist_behind_hip(
        self,
        segment: list[MotionSnapshot],
        torso_px: float,
    ) -> bool:
        """손목이 엉덩이 뒤로 이동하는지 감지한다.

        z축: 손목 z < 엉덩이 z - torso * 10%.

        Args:
            segment: 구간 스냅샷.
            torso_px: torso 기준 길이 (px).

        Returns:
            뒤쪽 이동 여부.
        """
        threshold = torso_px * _BEHIND_BACK_WRIST_BEHIND_RATIO
        for snap in segment:
            for wrist, hip in [
                (JointType.RIGHT_WRIST, JointType.RIGHT_HIP),
                (JointType.LEFT_WRIST, JointType.LEFT_HIP),
            ]:
                wrist_pos = snap.get_position(wrist)
                hip_pos = snap.get_position(hip)
                if wrist_pos and hip_pos:
                    # z축: 전방 양수, 손목이 엉덩이보다 뒤(z 작음)
                    if wrist_pos[2] < hip_pos[2] - threshold:
                        return True
        return False

    def _detect_between_legs(self, segment: list[MotionSnapshot]) -> bool:
        """다리 사이 공 통과를 감지한다 (관절 상대 위치 기반).

        손목 x좌표가 좌/우 엉덩이 x좌표 사이에 있으면서
        손목 y좌표가 무릎 높이 이하.

        Args:
            segment: 구간 스냅샷.

        Returns:
            다리 사이 통과 여부.
        """
        for snap in segment:
            l_hip = snap.get_position(JointType.LEFT_HIP)
            r_hip = snap.get_position(JointType.RIGHT_HIP)
            l_knee = snap.get_position(JointType.LEFT_KNEE)
            r_knee = snap.get_position(JointType.RIGHT_KNEE)

            if not (l_hip and r_hip):
                continue

            # 엉덩이 x 범위
            hip_x_min = min(l_hip[0], r_hip[0])
            hip_x_max = max(l_hip[0], r_hip[0])

            # 무릎 높이
            knee_y = 0.0
            knee_count = 0
            if l_knee:
                knee_y += l_knee[1]
                knee_count += 1
            if r_knee:
                knee_y += r_knee[1]
                knee_count += 1
            if knee_count > 0:
                knee_y /= knee_count
            else:
                continue

            for wrist in (JointType.RIGHT_WRIST, JointType.LEFT_WRIST):
                wrist_pos = snap.get_position(wrist)
                if wrist_pos is None:
                    continue

                # 손목이 엉덩이 x 범위 내 + 무릎 높이 이하
                if (
                    hip_x_min <= wrist_pos[0] <= hip_x_max
                    and wrist_pos[1] <= knee_y
                ):
                    return True

        return False

    def _detect_speed_drop(self, segment: list[MotionSnapshot]) -> float:
        """구간 내 최대 속도 대비 최저 속도 비율.

        헤지테이션 감지: 갑자기 속도가 40% 이하로 떨어지는 구간.

        Args:
            segment: 구간 스냅샷.

        Returns:
            최저/최고 속도 비율 (0~1, 낮을수록 급정지).
        """
        speeds: list[float] = []

        for snap in segment:
            for wrist in (JointType.RIGHT_WRIST, JointType.LEFT_WRIST):
                speed = snap.get_speed(wrist)
                if speed > 0:
                    speeds.append(speed)
                    break

        if not speeds or max(speeds) <= 0:
            return 1.0

        return min(speeds) / max(speeds)

    def _detect_backward_motion(
        self,
        segment: list[MotionSnapshot],
        torso_px: float,
    ) -> float:
        """후방 이동 거리를 계산한다 (torso-length).

        Args:
            segment: 구간 스냅샷.
            torso_px: torso 기준 길이 (px).

        Returns:
            후방 이동 거리 (torso-length), 양수=후방.
        """
        if len(segment) < 2:
            return 0.0

        first = segment[0]
        last = segment[-1]

        for joint in (JointType.RIGHT_HIP, JointType.LEFT_HIP):
            pf = first.get_position(joint)
            pl = last.get_position(joint)
            if pf and pl:
                dz = pf[2] - pl[2]  # 후방 = z 감소
                return max(0.0, dz / torso_px)

        return 0.0

    def __repr__(self) -> str:
        return "DribbleClassifier(13 types)"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "DribbleClassifier",
]

__version__ = "1.0.0"
