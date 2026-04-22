# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/classification
파일: shot_classifier.py
설명: 슈팅 세부 유형 분류기 (Tier 2)
      - SHOOTING으로 감지된 후보를 13가지 ShotType으로 세분화
      - 릴리스 높이, 거리(체형 비례), 점프 패턴 등 기반 분류
      - game_rule_constants.ShotType(13종) 사용
      - 모든 거리/속도는 torso-length (어깨~엉덩이) 기반 — 카메라 독립

      학술 근거:
        - Miller & Bartlett (1996): 슛 유형별 운동학적 차이
        - Okazaki & Rodacki (2012): 점프슛 거리별 역학
        - Knudson (1993): 슈팅 역학 6대 교수 포인트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - shared/constants/game_rule_constants.py: ShotType (13종)
    - configs/analysis/motion_analysis.yaml: classification.shot_types

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/constants/game_rule_constants.py: ShotType

소비자:
    - motion_analysis/phase_analysis/shot_phase_analyzer.py
    - motion_analysis/form_evaluation/shooting_form_evaluator.py
"""

from __future__ import annotations

import logging
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import ShotType
from shared.constants.pose_constants import JointType

from motion_analysis.models import DetectionCandidate, MotionSnapshot


# =============================================================================
# 상수 — 모든 거리는 torso-length 비율 (어깨~엉덩이 = 1.0)
# 실제 성인 torso ≈ 0.5m 기준, 물리 거리 → torso-length 변환
# =============================================================================

logger: Final = logging.getLogger(__name__)

# --- 3점 라인 거리 (torso-length) ---
_THREE_POINT_TORSO_RATIO_FIBA: Final[float] = 13.5    # 6.75m / 0.5m
_THREE_POINT_TORSO_RATIO_NBA: Final[float] = 14.5     # 7.24m / 0.5m

# --- 레이업/덩크 거리 (torso-length) ---
_LAYUP_MAX_TORSO_RATIO: Final[float] = 5.0            # 2.5m / 0.5m
_DUNK_MAX_TORSO_RATIO: Final[float] = 3.0             # 1.5m / 0.5m

# --- 릴리스 높이 비율 (키 대비) — 이미 비율 기반 ---
_DUNK_MIN_RELEASE_HEIGHT_RATIO: Final[float] = 1.3    # 덩크: 키의 130%+
_HOOK_SHOT_ARM_ANGLE_MIN: Final[float] = 150.0        # 훅샷: 팔꿈치 거의 펴짐

# --- 페이드어웨이 / 스텝백 ---
_FADEAWAY_TRUNK_LEAN_DEG: Final[float] = 15.0         # 후방 몸통 기울기 (°)
_STEPBACK_DISPLACEMENT_TORSO: Final[float] = 0.6      # 0.3m / 0.5m

# --- 자유투 ---
_FREE_THROW_TORSO_RATIO: Final[float] = 9.2           # 4.6m / 0.5m
_FREE_THROW_TOLERANCE_TORSO: Final[float] = 1.0       # 0.5m / 0.5m

# --- 풀업/캐치앤슛 ---
_PULL_UP_MIN_SPEED_TORSO_S: Final[float] = 3.0        # 1.5 m/s / 0.5m
_CATCH_SHOOT_MAX_PREP_FRAMES: Final[int] = 10         # 캐치앤슛: 준비 10프레임 이내

# --- torso 추정 불가 시 폴백 ---
_DEFAULT_FALLBACK_TORSO_PX: Final[float] = 200.0


# =============================================================================
# 슈팅 세부 분류기
# =============================================================================

class ShotClassifier:
    """
    슈팅 세부 유형 분류기.

    SHOOTING으로 감지된 DetectionCandidate를 받아
    13가지 ShotType 중 하나로 세분화한다.

    모든 거리/속도는 torso-length 기반:
        torso_length = abs(shoulder_y - hip_y)
        거리 = pixel_distance / torso_length → 체형 비례 단위

    분류 기준 (복합 조건 + 우선순위):
        1. 덩크: 릴리스 높이 ≥ 키 130% + 골대 3.0 torso 이내
        2. 팁인: 골대 3.0 torso 이내 + 점프 + 낮은 릴리스
        3. 풋백: 골대 4.0 torso 이내
        4. 레이업: 골대 5.0 torso 이내 + 이동 중
        5. 플로터: 골대 4~8 torso + 이동 중
        6. 훅샷: 팔꿈치 ≥ 150°
        7. 페이드어웨이: 후방 기울기 ≥ 15°
        8. 스텝백: 후방 이동 ≥ 0.6 torso
        9. 자유투: 자유투선 거리 (9.2 ± 1.0 torso) + 정지
        10. 풀업: 이동 ≥ 3.0 torso/s
        11. 캐치앤슛: 준비 10프레임 이내
        12. 3점슛: 13.5 torso+ (FIBA)
        13. 점프슛: 기본

    사용 예:
        >>> classifier = ShotClassifier()
        >>> shot_type, conf = classifier.classify(candidate, snapshots)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_three_point_torso_ratio", "_lock")

    def __init__(
        self,
        three_point_torso_ratio: float = _THREE_POINT_TORSO_RATIO_FIBA,
    ) -> None:
        """ShotClassifier 초기화.

        Args:
            three_point_torso_ratio: 3점 라인 거리 (torso-length 단위, 기본 FIBA 13.5).
        """
        self._three_point_torso_ratio = three_point_torso_ratio
        self._lock = RLock()

    # -------------------------------------------------------------------------
    # 핵심 분류 로직
    # -------------------------------------------------------------------------

    def classify(
        self,
        candidate: DetectionCandidate,
        snapshots: list[MotionSnapshot],
    ) -> tuple[ShotType, float]:
        """슈팅 후보를 세부 유형으로 분류한다.

        Args:
            candidate: SHOOTING DetectionCandidate.
            snapshots: 해당 구간 + 전후 MotionSnapshot.

        Returns:
            (ShotType, 분류 신뢰도) 튜플.
        """
        with self._lock:
            return self._classify_impl(candidate, snapshots)

    def _classify_impl(
        self,
        candidate: DetectionCandidate,
        snapshots: list[MotionSnapshot],
    ) -> tuple[ShotType, float]:
        """분류 구현."""
        segment = [
            s for s in snapshots
            if candidate.start_frame <= s.frame_index <= candidate.end_frame
        ]
        if not segment:
            return ShotType.JUMP_SHOT, 0.5

        features = self._extract_shot_features(candidate, segment, snapshots)
        return self._apply_rules(features)

    def _extract_shot_features(
        self,
        candidate: DetectionCandidate,
        segment: list[MotionSnapshot],
        all_snapshots: list[MotionSnapshot],
    ) -> dict[str, float]:
        """슈팅 분류용 특성을 추출한다 (체형 비례 단위).

        Args:
            candidate: 감지 후보.
            segment: 구간 내 스냅샷.
            all_snapshots: 전체 스냅샷 (전후 컨텍스트).

        Returns:
            특성 딕셔너리 (torso-length 기반).
        """
        features: dict[str, float] = {}

        # torso 기준 길이 계산
        torso_px = self._compute_avg_torso_length(segment)
        features["torso_length_px"] = torso_px

        # --- 골대 거리 (torso-length 단위) ---
        hoop_distances: list[float] = []
        for snap in segment:
            if snap.hoop_position is not None and snap.com_position is not None:
                dx = snap.com_position[0] - snap.hoop_position[0]
                dz = snap.com_position[2] - snap.hoop_position[2]
                dist_px = (dx * dx + dz * dz) ** 0.5
                hoop_distances.append(dist_px / torso_px)

        if hoop_distances:
            features["hoop_distance_torso"] = min(hoop_distances)
        else:
            features["hoop_distance_torso"] = candidate.evidence.get(
                "hoop_distance_torso", 10.0,
            )

        # --- 릴리스 높이 (키 대비 비율) ---
        max_wrist_y = 0.0
        for snap in segment:
            for wrist in (JointType.RIGHT_WRIST, JointType.LEFT_WRIST):
                pos = snap.get_position(wrist)
                if pos is not None:
                    max_wrist_y = max(max_wrist_y, pos[1])

        # 키 추정 (머리~발목 거리, px)
        player_height_px = self._estimate_height_px(segment)
        features["player_height_px"] = player_height_px

        if player_height_px > 0:
            features["release_height_ratio"] = max_wrist_y / player_height_px
        else:
            features["release_height_ratio"] = 0.0

        # --- 팔꿈치 각도 (최대, °) ---
        max_elbow_angle = 0.0
        for snap in segment:
            for elbow in (JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW):
                angle = snap.get_angle(elbow)
                max_elbow_angle = max(max_elbow_angle, angle)
        features["max_elbow_angle_deg"] = max_elbow_angle

        # --- 몸통 기울기 (pitch, 후방 양수) ---
        trunk_pitches: list[float] = []
        for snap in segment:
            if snap.body_orientation is not None:
                trunk_pitches.append(snap.body_orientation[1])  # pitch_deg

        if trunk_pitches:
            features["max_trunk_pitch_deg"] = max(trunk_pitches)
            features["avg_trunk_pitch_deg"] = sum(trunk_pitches) / len(trunk_pitches)
        else:
            features["max_trunk_pitch_deg"] = 0.0
            features["avg_trunk_pitch_deg"] = 0.0

        # --- 슈팅 전 이동 속도 (torso-length/s) ---
        pre_speed = self._get_pre_shot_speed(candidate, all_snapshots, torso_px)
        features["pre_shot_speed_torso_s"] = pre_speed

        # --- 슈팅 전 후방 변위 (torso-length) ---
        backward = self._get_backward_displacement(candidate, all_snapshots, torso_px)
        features["backward_displacement_torso"] = backward

        # --- 준비 시간 (프레임) ---
        features["duration_frames"] = float(candidate.duration_frames)

        # --- 점프 높이 (torso-length 비율) ---
        jump_px = self._estimate_jump_height_px(segment)
        features["jump_height_ratio"] = jump_px / torso_px

        return features

    def _apply_rules(
        self,
        features: dict[str, float],
    ) -> tuple[ShotType, float]:
        """규칙 기반 분류 (우선순위 순, torso-length 단위).

        Args:
            features: 추출된 특성 (체형 비례 단위).

        Returns:
            (ShotType, confidence).
        """
        dist = features.get("hoop_distance_torso", 10.0)
        release_ratio = features.get("release_height_ratio", 0.0)
        elbow_angle = features.get("max_elbow_angle_deg", 0.0)
        trunk_pitch = features.get("max_trunk_pitch_deg", 0.0)
        pre_speed = features.get("pre_shot_speed_torso_s", 0.0)
        backward = features.get("backward_displacement_torso", 0.0)
        jump_ratio = features.get("jump_height_ratio", 0.0)

        # 1. 덩크: 릴리스 높이 키 130%+ + 골대 3.0 torso 이내
        if release_ratio >= _DUNK_MIN_RELEASE_HEIGHT_RATIO and dist <= _DUNK_MAX_TORSO_RATIO:
            return ShotType.DUNK, min(1.0, 0.6 + release_ratio - 1.3)

        # 2. 팁인: 골대 3.0 torso 이내 + 점프 + 낮은 릴리스
        if dist <= _DUNK_MAX_TORSO_RATIO and jump_ratio > 0.05 and release_ratio < 1.2:
            return ShotType.TIP_IN, 0.6

        # 3. 풋백: 골대 4.0 torso 이내
        if dist <= 4.0 and release_ratio < 1.2:
            return ShotType.PUT_BACK, 0.6

        # 4. 레이업: 골대 5.0 torso 이내 + 이동 중
        if dist <= _LAYUP_MAX_TORSO_RATIO and pre_speed >= 2.0:
            return ShotType.LAYUP, min(1.0, 0.5 + pre_speed / 10.0)

        # 5. 플로터: 골대 4~8 torso + 이동 중
        if 4.0 <= dist <= 8.0 and pre_speed >= 2.0:
            return ShotType.FLOATER, 0.65

        # 6. 훅샷: 팔꿈치 크게 펴짐 (측면 슈팅)
        if elbow_angle >= _HOOK_SHOT_ARM_ANGLE_MIN and dist <= 8.0:
            return ShotType.HOOK_SHOT, 0.6

        # 7. 페이드어웨이: 후방 기울기
        if trunk_pitch >= _FADEAWAY_TRUNK_LEAN_DEG:
            return ShotType.FADEAWAY, min(1.0, 0.5 + trunk_pitch / 30.0)

        # 8. 스텝백: 후방 이동
        if backward >= _STEPBACK_DISPLACEMENT_TORSO:
            return ShotType.STEP_BACK, min(1.0, 0.5 + backward / 2.0)

        # 9. 자유투: 자유투선 거리 + 낮은 속도
        ft_min = _FREE_THROW_TORSO_RATIO - _FREE_THROW_TOLERANCE_TORSO
        ft_max = _FREE_THROW_TORSO_RATIO + _FREE_THROW_TOLERANCE_TORSO
        if ft_min <= dist <= ft_max and pre_speed < 1.0:
            return ShotType.FREE_THROW, 0.8

        # 10. 풀업: 드리블 이동 중 급정지 슈팅
        if pre_speed >= _PULL_UP_MIN_SPEED_TORSO_S:
            return ShotType.PULL_UP, min(1.0, 0.5 + pre_speed / 10.0)

        # 11. 캐치앤슛: 짧은 준비 시간 (10프레임 이내)
        duration = features.get("duration_frames", 20.0)
        if duration <= _CATCH_SHOOT_MAX_PREP_FRAMES and pre_speed < 2.0:
            return ShotType.CATCH_AND_SHOOT, 0.65

        # 12. 3점슛: 3점 라인 밖
        if dist >= self._three_point_torso_ratio:
            return ShotType.THREE_POINTER, min(
                1.0, 0.6 + (dist - self._three_point_torso_ratio) / 6.0,
            )

        # 13. 기본: 점프슛
        return ShotType.JUMP_SHOT, 0.7

    # -------------------------------------------------------------------------
    # 보조 메서드
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

    def _estimate_height_px(self, segment: list[MotionSnapshot]) -> float:
        """선수 키를 추정한다 (px).

        머리(NOSE) ~ 발목 중점의 y 거리.

        Args:
            segment: 구간 스냅샷.

        Returns:
            추정 키 (px), 0이면 추정 불가.
        """
        heights: list[float] = []
        for snap in segment:
            nose = snap.get_position(JointType.NOSE)
            l_ankle = snap.get_position(JointType.LEFT_ANKLE)
            r_ankle = snap.get_position(JointType.RIGHT_ANKLE)

            if nose is not None and (l_ankle or r_ankle):
                ankle_y = 0.0
                count = 0
                if l_ankle:
                    ankle_y += l_ankle[1]
                    count += 1
                if r_ankle:
                    ankle_y += r_ankle[1]
                    count += 1
                ankle_y /= count
                h = abs(nose[1] - ankle_y)
                if h > 30.0:  # 최소 30px (유효성)
                    heights.append(h)

        if heights:
            return sum(heights) / len(heights)
        return 0.0

    def _get_pre_shot_speed(
        self,
        candidate: DetectionCandidate,
        all_snapshots: list[MotionSnapshot],
        torso_px: float,
    ) -> float:
        """슈팅 직전 이동 속도를 계산한다 (torso-length/s).

        슈팅 시작 10프레임 전의 COM 변위 기반.

        Args:
            candidate: 감지 후보.
            all_snapshots: 전체 스냅샷.
            torso_px: torso 기준 길이 (px).

        Returns:
            직전 속도 (torso-length/s).
        """
        pre_snaps = [
            s for s in all_snapshots
            if candidate.start_frame - 10 <= s.frame_index < candidate.start_frame
        ]
        if len(pre_snaps) < 2:
            return 0.0

        first = pre_snaps[0]
        last = pre_snaps[-1]

        pos_first = first.com_position
        pos_last = last.com_position

        if pos_first is None or pos_last is None:
            # 엉덩이 대체
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
            else len(pre_snaps) / 30.0
        )
        return (dist_px / torso_px) / dt

    def _get_backward_displacement(
        self,
        candidate: DetectionCandidate,
        all_snapshots: list[MotionSnapshot],
        torso_px: float,
    ) -> float:
        """슈팅 직전 후방 변위를 계산한다 (torso-length).

        Args:
            candidate: 감지 후보.
            all_snapshots: 전체 스냅샷.
            torso_px: torso 기준 길이 (px).

        Returns:
            후방 변위 (torso-length), 양수=후방 이동.
        """
        pre_snaps = [
            s for s in all_snapshots
            if candidate.start_frame - 15 <= s.frame_index < candidate.start_frame
        ]
        if len(pre_snaps) < 2:
            return 0.0

        first = pre_snaps[0]
        last = pre_snaps[-1]

        # 몸체 방향 기준 후방 계산
        if last.body_orientation is not None:
            for joint in (JointType.RIGHT_HIP, JointType.LEFT_HIP):
                pf = first.get_position(joint)
                pl = last.get_position(joint)
                if pf and pl:
                    # z축 변위 (z 감소 = 후방)
                    dz = pf[2] - pl[2]
                    return max(0.0, dz / torso_px)

        return 0.0

    def _estimate_jump_height_px(self, segment: list[MotionSnapshot]) -> float:
        """점프 높이를 추정한다 (px).

        발목 y좌표의 최대~최소 차이.

        Args:
            segment: 구간 스냅샷.

        Returns:
            점프 높이 (px).
        """
        ankle_ys: list[float] = []
        for snap in segment:
            for ankle in (JointType.RIGHT_ANKLE, JointType.LEFT_ANKLE):
                pos = snap.get_position(ankle)
                if pos is not None:
                    ankle_ys.append(pos[1])
                    break  # 한쪽만

        if len(ankle_ys) < 2:
            return 0.0

        return max(ankle_ys) - min(ankle_ys)

    def __repr__(self) -> str:
        return f"ShotClassifier(3pt_torso={self._three_point_torso_ratio})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "ShotClassifier",
]

__version__ = "1.0.0"
