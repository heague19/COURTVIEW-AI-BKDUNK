# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/phase_analysis
파일: shot_phase_analyzer.py
설명: 슈팅 동작 위상 분석기 (Tier 3)
      - SHOOTING 동작을 4단계 위상으로 분해:
        preparation → loading → release → follow_through
      - 각 위상의 시작/종료 프레임, 지속 시간, 핵심 지표 추출
      - 키네틱 체인 순서 검증 (하체→코어→상체→손목)
      - 위상 전환 부드러움 평가
      - PhaseResult DTO 생성 (Tier 4 폼 평가 입력)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

학술 근거:
    - Knudson, D. (1993). "Biomechanics of the Basketball Jump Shot —
      Six Key Teaching Points." J. Physical Education, 64(2), 67-73.
    - Miller, S. & Bartlett, R.M. (1996). "The relationship between
      basketball shooting kinematics, distance and playing position."
      J. Sports Sciences, 14(3), 243-253.
    - Okazaki, V.H.A. & Rodacki, A.L.F. (2012). "Increased distance of
      shooting on basketball jump shot." J. Sports Sci. & Med., 11(2), 231.

참조:
    - motion_analysis/models.py: ShotPhase, PhaseSegment, PhaseResult,
                                  MotionSnapshot, DetectionCandidate
    - configs/analysis/motion_analysis.yaml: phase_analysis.shot_phases

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/dto/motion_dto.py: ActionType

소비자:
    - motion_analysis/form_evaluation/shooting_form_evaluator.py: 폼 평가 입력
    - ai_referee/: 위상 기반 바이올레이션 판정 참조
"""

from __future__ import annotations

import logging
from threading import RLock
from typing import Final

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    DetectionCandidate,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
    ShotPhase,
)


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# --- 위상별 전형적 지속 프레임 범위 (30fps 기준) ---
# Knudson (1993): 슈팅 전체 ~0.5-1.0초
_DEFAULT_PHASE_DURATION: Final[dict[ShotPhase, tuple[int, int]]] = {
    ShotPhase.PREPARATION: (5, 15),     # ~0.17-0.50초
    ShotPhase.LOADING: (3, 10),         # ~0.10-0.33초
    ShotPhase.RELEASE: (2, 6),          # ~0.07-0.20초
    ShotPhase.FOLLOW_THROUGH: (5, 15),  # ~0.17-0.50초
}

# --- 위상 전환 감지 임계치 ---
# 무릎 각도: 로딩 시 ~100-130° (Miller & Bartlett, 1996)
_KNEE_FLEXION_THRESHOLD_DEG: Final[float] = 140.0  # 이 이하 → 로딩 중
# 팔꿈치: 릴리스 시 ~150-170° (팔 펴짐)
_ELBOW_EXTENSION_THRESHOLD_DEG: Final[float] = 150.0
# 손목 속도: 릴리스 감지 기준 (cm/s → m/s 변환 주의, 내부는 cm/s)
_WRIST_RELEASE_SPEED_CMS: Final[float] = 250.0  # 2.5 m/s = 250 cm/s
# 손목-어깨 높이차: 릴리스 판정 최소값 (cm)
_WRIST_ABOVE_SHOULDER_CM: Final[float] = 5.0
# 팔로우 스루: 손목 속도 감소 기준 (cm/s)
_FOLLOWTHROUGH_DECEL_CMS: Final[float] = 100.0

# --- 키네틱 체인 검증 관절 순서 ---
# 정상 체인: 무릎 → 엉덩이 → 어깨 → 팔꿈치 → 손목
_KINETIC_CHAIN_JOINTS: Final[list[JointType]] = [
    JointType.RIGHT_KNEE,
    JointType.RIGHT_HIP,
    JointType.RIGHT_SHOULDER,
    JointType.RIGHT_ELBOW,
    JointType.RIGHT_WRIST,
]

# --- 위상별 가중치 (품질 평가) ---
_PHASE_QUALITY_WEIGHTS: Final[dict[ShotPhase, float]] = {
    ShotPhase.PREPARATION: 0.15,
    ShotPhase.LOADING: 0.25,
    ShotPhase.RELEASE: 0.40,
    ShotPhase.FOLLOW_THROUGH: 0.20,
}


# =============================================================================
# 슈팅 위상 분석기
# =============================================================================

class ShotPhaseAnalyzer:
    """
    슈팅 동작 위상 분석기 (Tier 3).

    SHOOTING으로 분류된 DetectionCandidate와 해당 구간의
    MotionSnapshot 시퀀스를 입력받아, 4단계 위상으로 분해한다.

    역할:
        1. 위상 경계 감지: 관절 각도/속도 변화 패턴으로 전환점 식별
        2. 위상 지속 시간 검증: 전형적 범위 대비 평가
        3. 핵심 지표 추출: 위상별 측정값 (각도, 속도, 높이차 등)
        4. 키네틱 체인 평가: 하체→상체 에너지 전달 순서 검증
        5. 전환 부드러움 평가: 위상 간 연속성

    사용 예:
        >>> analyzer = ShotPhaseAnalyzer()
        >>> result = analyzer.analyze(candidate, snapshots)
        >>> for phase in result.phases:
        ...     print(phase.phase_name, phase.duration_frames)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_phase_durations", "_lock")

    def __init__(
        self,
        phase_durations: dict[ShotPhase, tuple[int, int]] | None = None,
    ) -> None:
        """ShotPhaseAnalyzer 초기화.

        Args:
            phase_durations: 위상별 전형적 프레임 범위 오버라이드.
        """
        self._phase_durations = phase_durations or dict(_DEFAULT_PHASE_DURATION)
        self._lock = RLock()

    @classmethod
    def from_yaml(cls, config_dict: dict) -> ShotPhaseAnalyzer:
        """YAML 설정에서 생성.

        Args:
            config_dict: phase_analysis.shot_phases 섹션.

        Returns:
            ShotPhaseAnalyzer 인스턴스.
        """
        durations: dict[ShotPhase, tuple[int, int]] = {}
        phases_list = config_dict.get("shot_phases", [])
        for phase_cfg in phases_list:
            name = phase_cfg.get("name", "")
            try:
                shot_phase = ShotPhase(name)
            except ValueError:
                continue
            dur = phase_cfg.get("typical_duration_frames", [3, 10])
            durations[shot_phase] = (int(dur[0]), int(dur[1]))

        return cls(phase_durations=durations if durations else None)

    # -------------------------------------------------------------------------
    # 핵심 분석 로직
    # -------------------------------------------------------------------------

    def analyze(
        self,
        candidate: DetectionCandidate,
        snapshots: list[MotionSnapshot],
    ) -> PhaseResult:
        """슈팅 동작을 4단계 위상으로 분석한다.

        Args:
            candidate: SHOOTING DetectionCandidate.
            snapshots: 해당 구간의 MotionSnapshot 시퀀스.

        Returns:
            PhaseResult (4단계 위상 + 키네틱 체인 + 전환 부드러움).
        """
        with self._lock:
            return self._analyze_impl(candidate, snapshots)

    def _analyze_impl(
        self,
        candidate: DetectionCandidate,
        snapshots: list[MotionSnapshot],
    ) -> PhaseResult:
        """분석 구현."""
        # 구간 내 스냅샷 필터
        segment = [
            s for s in snapshots
            if candidate.start_frame <= s.frame_index <= candidate.end_frame
        ]

        if len(segment) < 4:
            # 최소 4프레임 필요 (위상당 1프레임)
            return self._empty_result(candidate)

        # 1. 위상 경계 감지
        boundaries = self._detect_phase_boundaries(segment)

        # 2. PhaseSegment 생성
        phases = self._build_phase_segments(segment, boundaries)

        # 3. 키네틱 체인 평가
        chain_score = self._evaluate_kinetic_chain(segment)

        # 4. 위상 전환 부드러움 평가
        smoothness = self._evaluate_transition_smoothness(segment, boundaries)

        # 5. 전체 지속 프레임
        total_frames = candidate.duration_frames

        return PhaseResult(
            action_type=ActionType.SHOOTING,
            player_tracking_id=candidate.player_tracking_id,
            phases=phases,
            total_duration_frames=total_frames,
            kinetic_chain_score=chain_score,
            transition_smoothness=smoothness,
            start_frame=candidate.start_frame,
            end_frame=candidate.end_frame,
        )

    # -------------------------------------------------------------------------
    # 위상 경계 감지
    # -------------------------------------------------------------------------

    def _detect_phase_boundaries(
        self,
        segment: list[MotionSnapshot],
    ) -> list[int]:
        """위상 전환 프레임 인덱스를 감지한다.

        반환값: [loading_start, release_start, followthrough_start]
        (preparation_start는 항상 segment[0])

        감지 기준:
            - preparation → loading: 무릎 굽힘 시작 (각도 < 140°)
            - loading → release: 팔꿈치 펴짐 시작 (각도 > 150°)
              또는 손목이 어깨 위로 올라가는 시점
            - release → follow_through: 손목 속도 피크 후 감속

        Args:
            segment: 시간순 정렬된 MotionSnapshot.

        Returns:
            [loading_idx, release_idx, followthrough_idx] (segment 내 인덱스).
        """
        n = len(segment)

        # --- loading 시작: 무릎 굽힘 감지 ---
        loading_idx = self._find_loading_start(segment)

        # --- release 시작: 팔꿈치 펴짐 + 손목 상승 ---
        release_idx = self._find_release_start(segment, loading_idx)

        # --- follow_through 시작: 손목 속도 피크 후 ---
        followthrough_idx = self._find_followthrough_start(segment, release_idx)

        # 경계 보정: 순서 보장
        loading_idx = max(1, min(loading_idx, n - 3))
        release_idx = max(loading_idx + 1, min(release_idx, n - 2))
        followthrough_idx = max(release_idx + 1, min(followthrough_idx, n - 1))

        return [loading_idx, release_idx, followthrough_idx]

    def _find_loading_start(self, segment: list[MotionSnapshot]) -> int:
        """로딩 위상 시작점을 찾는다 (무릎 굽힘 시작).

        무릎 각도가 _KNEE_FLEXION_THRESHOLD_DEG 이하로 내려가는
        첫 프레임을 감지한다.

        Args:
            segment: MotionSnapshot 시퀀스.

        Returns:
            segment 내 인덱스.
        """
        for i, snap in enumerate(segment):
            if i == 0:
                continue

            # 양쪽 무릎 중 하나라도 굽히기 시작하면
            r_knee = snap.get_angle(JointType.RIGHT_KNEE)
            l_knee = snap.get_angle(JointType.LEFT_KNEE)

            knee_angle = min(r_knee, l_knee) if r_knee > 0 and l_knee > 0 else max(r_knee, l_knee)

            if 0 < knee_angle < _KNEE_FLEXION_THRESHOLD_DEG:
                return i

        # 감지 실패: 전체 구간의 25% 지점
        return max(1, len(segment) // 4)

    def _find_release_start(
        self,
        segment: list[MotionSnapshot],
        loading_start: int,
    ) -> int:
        """릴리스 위상 시작점을 찾는다.

        두 가지 조건 중 하나 충족:
            1. 팔꿈치 각도 ≥ 150° (팔 펴짐)
            2. 손목이 어깨 위 5cm 이상

        Args:
            segment: MotionSnapshot 시퀀스.
            loading_start: 로딩 시작 인덱스.

        Returns:
            segment 내 인덱스.
        """
        search_start = loading_start + 1

        for i in range(search_start, len(segment)):
            snap = segment[i]

            # 팔꿈치 펴짐 확인
            r_elbow = snap.get_angle(JointType.RIGHT_ELBOW)
            l_elbow = snap.get_angle(JointType.LEFT_ELBOW)
            elbow_ext = max(r_elbow, l_elbow)

            if elbow_ext >= _ELBOW_EXTENSION_THRESHOLD_DEG:
                return i

            # 손목-어깨 높이차 확인
            for side in (
                (JointType.RIGHT_WRIST, JointType.RIGHT_SHOULDER),
                (JointType.LEFT_WRIST, JointType.LEFT_SHOULDER),
            ):
                height_diff = snap.get_relative_height(side[0], side[1])
                if height_diff is not None and height_diff >= _WRIST_ABOVE_SHOULDER_CM:
                    return i

        # 감지 실패: loading_start와 끝의 중간
        return max(search_start, (loading_start + len(segment)) // 2)

    def _find_followthrough_start(
        self,
        segment: list[MotionSnapshot],
        release_start: int,
    ) -> int:
        """팔로우 스루 시작점을 찾는다 (릴리스 후 감속).

        손목 속도가 피크 후 _FOLLOWTHROUGH_DECEL_CMS 이하로
        내려가는 시점.

        Args:
            segment: MotionSnapshot 시퀀스.
            release_start: 릴리스 시작 인덱스.

        Returns:
            segment 내 인덱스.
        """
        search_start = release_start + 1
        peak_speed = 0.0
        peak_found = False

        for i in range(search_start, len(segment)):
            snap = segment[i]

            # 양손 중 최대 속도
            r_wrist_spd = snap.get_speed(JointType.RIGHT_WRIST)
            l_wrist_spd = snap.get_speed(JointType.LEFT_WRIST)
            wrist_speed = max(r_wrist_spd, l_wrist_spd)

            if wrist_speed > peak_speed:
                peak_speed = wrist_speed
                peak_found = True
            elif peak_found and wrist_speed < _FOLLOWTHROUGH_DECEL_CMS:
                return i

        # 감지 실패: release 이후 50% 지점
        remaining = len(segment) - release_start
        return min(len(segment) - 1, release_start + max(1, remaining // 2))

    # -------------------------------------------------------------------------
    # PhaseSegment 생성
    # -------------------------------------------------------------------------

    def _build_phase_segments(
        self,
        segment: list[MotionSnapshot],
        boundaries: list[int],
    ) -> list[PhaseSegment]:
        """위상 세그먼트를 생성한다.

        Args:
            segment: MotionSnapshot 시퀀스.
            boundaries: [loading_idx, release_idx, followthrough_idx].

        Returns:
            4개의 PhaseSegment 목록.
        """
        loading_idx, release_idx, ft_idx = boundaries

        # 위상별 프레임 범위
        ranges = [
            (ShotPhase.PREPARATION, 0, loading_idx),
            (ShotPhase.LOADING, loading_idx, release_idx),
            (ShotPhase.RELEASE, release_idx, ft_idx),
            (ShotPhase.FOLLOW_THROUGH, ft_idx, len(segment)),
        ]

        phases: list[PhaseSegment] = []
        for phase_enum, start_idx, end_idx in ranges:
            phase_snaps = segment[start_idx:end_idx]
            if not phase_snaps:
                phase_snaps = [segment[min(start_idx, len(segment) - 1)]]

            start_frame = phase_snaps[0].frame_index
            end_frame = phase_snaps[-1].frame_index
            duration = max(1, end_frame - start_frame)

            # 핵심 지표 추출
            metrics = self._extract_phase_metrics(phase_enum, phase_snaps)

            # 품질 평가
            quality = self._evaluate_phase_quality(phase_enum, phase_snaps, duration)

            phases.append(PhaseSegment(
                phase_name=phase_enum.value,
                start_frame=start_frame,
                end_frame=end_frame,
                duration_frames=duration,
                key_metrics=metrics,
                quality=quality,
            ))

        return phases

    def _extract_phase_metrics(
        self,
        phase: ShotPhase,
        snaps: list[MotionSnapshot],
    ) -> dict[str, float]:
        """위상별 핵심 지표를 추출한다.

        Args:
            phase: 위상 유형.
            snaps: 해당 위상의 스냅샷.

        Returns:
            지표 딕셔너리.
        """
        metrics: dict[str, float] = {}

        if phase == ShotPhase.PREPARATION:
            # 안정성, 초기 무릎 각도
            stabilities = [s.stability_index for s in snaps if s.stability_index > 0]
            if stabilities:
                metrics["avg_stability"] = sum(stabilities) / len(stabilities)

            knee_angles = self._get_avg_joint_angle(snaps, JointType.RIGHT_KNEE)
            if knee_angles > 0:
                metrics["initial_knee_angle_deg"] = knee_angles

        elif phase == ShotPhase.LOADING:
            # 최소 무릎 각도 (최대 굽힘), 엉덩이 각도
            knee_angles = [
                min(s.get_angle(JointType.RIGHT_KNEE),
                    s.get_angle(JointType.LEFT_KNEE))
                for s in snaps
                if s.get_angle(JointType.RIGHT_KNEE) > 0
                or s.get_angle(JointType.LEFT_KNEE) > 0
            ]
            if knee_angles:
                valid = [k for k in knee_angles if k > 0]
                if valid:
                    metrics["min_knee_angle_deg"] = min(valid)
                    metrics["avg_knee_angle_deg"] = sum(valid) / len(valid)

            hip_angles = self._get_avg_joint_angle(snaps, JointType.RIGHT_HIP)
            if hip_angles > 0:
                metrics["avg_hip_angle_deg"] = hip_angles

        elif phase == ShotPhase.RELEASE:
            # 팔꿈치 최대 각도, 손목 최대 속도, 손목-어깨 높이차
            elbow_max = 0.0
            wrist_max_speed = 0.0
            max_wrist_height = 0.0

            for s in snaps:
                r_elbow = s.get_angle(JointType.RIGHT_ELBOW)
                l_elbow = s.get_angle(JointType.LEFT_ELBOW)
                elbow_max = max(elbow_max, r_elbow, l_elbow)

                r_wrist_spd = s.get_speed(JointType.RIGHT_WRIST)
                l_wrist_spd = s.get_speed(JointType.LEFT_WRIST)
                wrist_max_speed = max(wrist_max_speed, r_wrist_spd, l_wrist_spd)

                for wrist, shoulder in (
                    (JointType.RIGHT_WRIST, JointType.RIGHT_SHOULDER),
                    (JointType.LEFT_WRIST, JointType.LEFT_SHOULDER),
                ):
                    h = s.get_relative_height(wrist, shoulder)
                    if h is not None:
                        max_wrist_height = max(max_wrist_height, h)

            if elbow_max > 0:
                metrics["max_elbow_angle_deg"] = elbow_max
            if wrist_max_speed > 0:
                metrics["max_wrist_speed_cms"] = wrist_max_speed
            if max_wrist_height > 0:
                metrics["max_wrist_above_shoulder_cm"] = max_wrist_height

        elif phase == ShotPhase.FOLLOW_THROUGH:
            # 손목 속도 감소율, 팔꿈치 유지 각도
            if len(snaps) >= 2:
                first_speeds = []
                last_speeds = []
                for wrist in (JointType.RIGHT_WRIST, JointType.LEFT_WRIST):
                    s0 = snaps[0].get_speed(wrist)
                    s1 = snaps[-1].get_speed(wrist)
                    if s0 > 0:
                        first_speeds.append(s0)
                    if s1 >= 0:
                        last_speeds.append(s1)

                if first_speeds and last_speeds:
                    initial = max(first_speeds)
                    final = max(last_speeds) if last_speeds else 0.0
                    if initial > 0:
                        metrics["speed_decay_ratio"] = 1.0 - (final / initial)

            elbow_angles = []
            for s in snaps:
                r = s.get_angle(JointType.RIGHT_ELBOW)
                l = s.get_angle(JointType.LEFT_ELBOW)
                if r > 0:
                    elbow_angles.append(r)
                if l > 0:
                    elbow_angles.append(l)
            if elbow_angles:
                metrics["avg_elbow_hold_deg"] = sum(elbow_angles) / len(elbow_angles)

        return metrics

    def _evaluate_phase_quality(
        self,
        phase: ShotPhase,
        snaps: list[MotionSnapshot],
        duration: int,
    ) -> float:
        """위상 품질을 평가한다 (0~1).

        기준:
            - 지속 시간이 전형적 범위 내인지
            - 핵심 관절 데이터가 존재하는지
            - 위상별 특정 기준 충족 여부

        Args:
            phase: 위상 유형.
            snaps: 해당 위상의 스냅샷.
            duration: 지속 프레임 수.

        Returns:
            품질 점수 (0~1).
        """
        score = 0.0
        checks = 0

        # 1. 지속 시간 적합성 (0 또는 1)
        min_dur, max_dur = self._phase_durations.get(phase, (2, 15))
        if min_dur <= duration <= max_dur:
            score += 1.0
        elif duration > 0:
            # 범위 밖이면 거리에 비례 감점
            if duration < min_dur:
                score += max(0.0, 1.0 - (min_dur - duration) / min_dur)
            else:
                score += max(0.0, 1.0 - (duration - max_dur) / max_dur)
        checks += 1

        # 2. 관절 데이터 존재율
        data_ratio = self._compute_data_availability(snaps)
        score += data_ratio
        checks += 1

        # 3. 위상별 특정 기준
        phase_score = self._phase_specific_quality(phase, snaps)
        score += phase_score
        checks += 1

        return min(1.0, score / checks) if checks > 0 else 0.0

    def _phase_specific_quality(
        self,
        phase: ShotPhase,
        snaps: list[MotionSnapshot],
    ) -> float:
        """위상별 특정 품질 기준 평가.

        Args:
            phase: 위상 유형.
            snaps: 해당 위상의 스냅샷.

        Returns:
            0~1 점수.
        """
        if phase == ShotPhase.PREPARATION:
            # 안정성 지수 평균 ≥ 50 → 양호
            stabilities = [s.stability_index for s in snaps if s.stability_index > 0]
            if stabilities:
                avg = sum(stabilities) / len(stabilities)
                return min(1.0, avg / 70.0)
            return 0.5  # 데이터 없으면 중립

        elif phase == ShotPhase.LOADING:
            # 무릎 굽힘 존재 확인
            for s in snaps:
                r_knee = s.get_angle(JointType.RIGHT_KNEE)
                l_knee = s.get_angle(JointType.LEFT_KNEE)
                knee = min(r_knee, l_knee) if r_knee > 0 and l_knee > 0 else max(r_knee, l_knee)
                if 0 < knee < _KNEE_FLEXION_THRESHOLD_DEG:
                    return 1.0
            return 0.3

        elif phase == ShotPhase.RELEASE:
            # 팔꿈치 펴짐 + 손목 속도 존재
            has_extension = False
            has_speed = False
            for s in snaps:
                r_elbow = s.get_angle(JointType.RIGHT_ELBOW)
                l_elbow = s.get_angle(JointType.LEFT_ELBOW)
                if max(r_elbow, l_elbow) >= _ELBOW_EXTENSION_THRESHOLD_DEG:
                    has_extension = True

                r_spd = s.get_speed(JointType.RIGHT_WRIST)
                l_spd = s.get_speed(JointType.LEFT_WRIST)
                if max(r_spd, l_spd) >= _WRIST_RELEASE_SPEED_CMS:
                    has_speed = True

            score = 0.0
            if has_extension:
                score += 0.5
            if has_speed:
                score += 0.5
            return score

        elif phase == ShotPhase.FOLLOW_THROUGH:
            # 최소 2프레임 이상 유지
            if len(snaps) >= 2:
                return 0.8
            return 0.4

        return 0.5

    # -------------------------------------------------------------------------
    # 키네틱 체인 평가
    # -------------------------------------------------------------------------

    def _evaluate_kinetic_chain(
        self,
        segment: list[MotionSnapshot],
    ) -> float:
        """키네틱 체인 순서를 평가한다.

        정상적인 슈팅 키네틱 체인:
            무릎 → 엉덩이 → 어깨 → 팔꿈치 → 손목
            (하체에서 상체로 순차적 에너지 전달)

        각 관절의 최대 속도 도달 프레임을 추출하고,
        순서가 올바르면 높은 점수를 부여한다.

        Args:
            segment: MotionSnapshot 시퀀스.

        Returns:
            키네틱 체인 점수 (0~1).
        """
        if len(segment) < 3:
            return 0.5  # 데이터 부족

        # 각 관절의 최대 속도 도달 프레임 인덱스
        peak_frames: list[tuple[JointType, int]] = []

        for joint in _KINETIC_CHAIN_JOINTS:
            max_speed = 0.0
            max_idx = 0
            for i, snap in enumerate(segment):
                speed = snap.get_speed(joint)
                if speed > max_speed:
                    max_speed = speed
                    max_idx = i
            if max_speed > 0:
                peak_frames.append((joint, max_idx))

        if len(peak_frames) < 3:
            return 0.5  # 충분한 데이터 없음

        # 순서 쌍 비교: 앞 관절이 뒤 관절보다 먼저(또는 같이) 피크 → 정상
        correct_pairs = 0
        total_pairs = 0

        for i in range(len(peak_frames) - 1):
            for j in range(i + 1, len(peak_frames)):
                total_pairs += 1
                if peak_frames[i][1] <= peak_frames[j][1]:
                    correct_pairs += 1

        if total_pairs == 0:
            return 0.5

        return correct_pairs / total_pairs

    # -------------------------------------------------------------------------
    # 전환 부드러움 평가
    # -------------------------------------------------------------------------

    def _evaluate_transition_smoothness(
        self,
        segment: list[MotionSnapshot],
        boundaries: list[int],
    ) -> float:
        """위상 전환의 부드러움을 평가한다.

        전환 지점에서 관절 속도의 급격한 변화(jerk)가 작을수록
        부드러운 전환으로 판단.

        Args:
            segment: MotionSnapshot 시퀀스.
            boundaries: 전환 프레임 인덱스.

        Returns:
            부드러움 점수 (0~1).
        """
        if len(segment) < 4:
            return 0.5

        smoothness_scores: list[float] = []

        for boundary_idx in boundaries:
            if boundary_idx <= 0 or boundary_idx >= len(segment) - 1:
                continue

            # 전환점 전후 속도 변화율 측정
            before = segment[boundary_idx - 1]
            at_boundary = segment[boundary_idx]
            after = segment[min(boundary_idx + 1, len(segment) - 1)]

            # 주요 관절 속도 변화
            jerks: list[float] = []
            for joint in (JointType.RIGHT_WRIST, JointType.RIGHT_ELBOW,
                          JointType.RIGHT_SHOULDER):
                v_before = before.get_speed(joint)
                v_at = at_boundary.get_speed(joint)
                v_after = after.get_speed(joint)

                if v_before > 0 or v_at > 0 or v_after > 0:
                    # 2차 차분 (가가속도 근사)
                    jerk = abs((v_after - v_at) - (v_at - v_before))
                    max_speed = max(v_before, v_at, v_after, 1.0)
                    # 정규화 (속도 대비 변화율)
                    normalized_jerk = jerk / max_speed
                    jerks.append(normalized_jerk)

            if jerks:
                avg_jerk = sum(jerks) / len(jerks)
                # 낮은 jerk = 높은 부드러움
                transition_score = max(0.0, 1.0 - avg_jerk)
                smoothness_scores.append(transition_score)

        if not smoothness_scores:
            return 0.5

        return sum(smoothness_scores) / len(smoothness_scores)

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------

    def _get_avg_joint_angle(
        self,
        snaps: list[MotionSnapshot],
        joint: JointType,
    ) -> float:
        """스냅샷 시퀀스에서 관절 각도 평균을 구한다.

        Args:
            snaps: MotionSnapshot 시퀀스.
            joint: 관절 유형.

        Returns:
            평균 각도 (0이면 데이터 없음).
        """
        angles = [s.get_angle(joint) for s in snaps if s.get_angle(joint) > 0]
        if not angles:
            return 0.0
        return sum(angles) / len(angles)

    def _compute_data_availability(
        self,
        snaps: list[MotionSnapshot],
    ) -> float:
        """스냅샷의 관절 데이터 가용률을 계산한다.

        상체 관절(어깨, 팔꿈치, 손목) 6개 중 존재하는 비율.

        Args:
            snaps: MotionSnapshot 시퀀스.

        Returns:
            가용률 (0~1).
        """
        if not snaps:
            return 0.0

        required_joints = {
            JointType.RIGHT_SHOULDER, JointType.LEFT_SHOULDER,
            JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW,
            JointType.RIGHT_WRIST, JointType.LEFT_WRIST,
        }

        total_checks = len(snaps) * len(required_joints)
        available = 0

        for snap in snaps:
            for joint in required_joints:
                if joint in snap.joint_positions:
                    available += 1

        return available / total_checks if total_checks > 0 else 0.0

    def _empty_result(self, candidate: DetectionCandidate) -> PhaseResult:
        """데이터 부족 시 빈 PhaseResult를 생성한다.

        Args:
            candidate: 원본 DetectionCandidate.

        Returns:
            빈 PhaseResult.
        """
        return PhaseResult(
            action_type=ActionType.SHOOTING,
            player_tracking_id=candidate.player_tracking_id,
            phases=[],
            total_duration_frames=candidate.duration_frames,
            kinetic_chain_score=0.0,
            transition_smoothness=0.0,
            start_frame=candidate.start_frame,
            end_frame=candidate.end_frame,
        )

    def __repr__(self) -> str:
        return f"ShotPhaseAnalyzer(phases=4)"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "ShotPhaseAnalyzer",
]

__version__ = "1.0.0"
