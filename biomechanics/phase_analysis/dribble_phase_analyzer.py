# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/phase_analysis
파일: dribble_phase_analyzer.py
설명: 드리블 동작 위상 분석기 (Tier 3)
      - DRIBBLING 동작을 4단계 위상으로 분해:
        push_down → ball_contact → rise → catch
      - 한 번의 바운스를 1사이클로 분석
      - 복수 바운스 시 사이클별 일관성 평가
      - 손-공 동기화 정확도 평가
      - PhaseResult DTO 생성 (Tier 4 폼 평가 입력)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

학술 근거:
    - Arias, J.L. et al. (2012). "Review of biomechanical factors in
      basketball ball handling." J. Human Sport & Exercise, 7(1), 318-329.
    - Cortis, C. et al. (2011). "Inter-limb coordination, strength,
      jump, and sprint performances following a youth men's basketball
      game." J. Strength & Conditioning Research, 25(1), 135-142.

참조:
    - motion_analysis/models.py: DribblePhase, PhaseSegment, PhaseResult,
                                  MotionSnapshot, DetectionCandidate
    - configs/analysis/motion_analysis.yaml: phase_analysis.dribble_phases

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/dto/motion_dto.py: ActionType

소비자:
    - motion_analysis/form_evaluation/dribble_form_evaluator.py: 폼 평가 입력
"""

from __future__ import annotations

import logging
from threading import RLock
from typing import Final

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    DetectionCandidate,
    DribblePhase,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
)


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# --- 위상별 전형적 지속 프레임 범위 (30fps 기준) ---
# Arias et al. (2012): 드리블 1사이클 ~0.2-0.5초
_DEFAULT_PHASE_DURATION: Final[dict[DribblePhase, tuple[int, int]]] = {
    DribblePhase.PUSH_DOWN: (2, 5),      # ~0.07-0.17초
    DribblePhase.BALL_CONTACT: (1, 3),   # ~0.03-0.10초
    DribblePhase.RISE: (2, 5),           # ~0.07-0.17초
    DribblePhase.CATCH: (1, 3),          # ~0.03-0.10초
}

# --- 위상 전환 감지 임계치 ---
# 손목 하강 속도: push_down 감지 (cm/s, 아래로 음수이므로 절대값)
_WRIST_DOWNWARD_SPEED_CMS: Final[float] = 80.0
# 손목 최저점 감지: ball_contact 판정
_WRIST_LOWEST_TOLERANCE_CM: Final[float] = 5.0
# 손목 상승 속도: rise 감지 (cm/s)
_WRIST_UPWARD_SPEED_CMS: Final[float] = 60.0
# 손목 감속: catch 판정 — 상승 후 속도가 이 이하로 감소
_WRIST_CATCH_DECEL_CMS: Final[float] = 40.0
# 손목-엉덩이 높이 비율: 드리블 높이 기준
_HAND_HIP_HEIGHT_RATIO: Final[float] = 0.8

# --- 사이클 일관성 가중치 ---
_CONSISTENCY_WEIGHT: Final[float] = 0.30  # 전체 평가 중 일관성 비중


# =============================================================================
# 드리블 위상 분석기
# =============================================================================

class DribblePhaseAnalyzer:
    """
    드리블 동작 위상 분석기 (Tier 3).

    DRIBBLING으로 분류된 DetectionCandidate와 해당 구간의
    MotionSnapshot 시퀀스를 입력받아, 바운스 사이클별
    4단계 위상으로 분해한다.

    역할:
        1. 바운스 사이클 감지: 손목 y좌표의 하강→최저→상승→안정 패턴
        2. 위상 경계 감지: 각 사이클 내 4단계 전환점 식별
        3. 핵심 지표 추출: 위상별 손목 높이/속도/제어 지표
        4. 사이클 일관성 평가: 반복 동작의 타이밍 균일성
        5. 대표 사이클 선택: 최고 품질 사이클을 PhaseResult로 출력

    사용 예:
        >>> analyzer = DribblePhaseAnalyzer()
        >>> result = analyzer.analyze(candidate, snapshots)
        >>> for phase in result.phases:
        ...     print(phase.phase_name, phase.duration_frames)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_phase_durations", "_lock")

    def __init__(
        self,
        phase_durations: dict[DribblePhase, tuple[int, int]] | None = None,
    ) -> None:
        """DribblePhaseAnalyzer 초기화.

        Args:
            phase_durations: 위상별 전형적 프레임 범위 오버라이드.
        """
        self._phase_durations = phase_durations or dict(_DEFAULT_PHASE_DURATION)
        self._lock = RLock()

    @classmethod
    def from_yaml(cls, config_dict: dict) -> DribblePhaseAnalyzer:
        """YAML 설정에서 생성.

        Args:
            config_dict: phase_analysis.dribble_phases 섹션.

        Returns:
            DribblePhaseAnalyzer 인스턴스.
        """
        durations: dict[DribblePhase, tuple[int, int]] = {}
        phases_list = config_dict.get("dribble_phases", [])
        for phase_cfg in phases_list:
            name = phase_cfg.get("name", "")
            try:
                dribble_phase = DribblePhase(name)
            except ValueError:
                continue
            dur = phase_cfg.get("typical_duration_frames", [2, 5])
            durations[dribble_phase] = (int(dur[0]), int(dur[1]))

        return cls(phase_durations=durations if durations else None)

    # -------------------------------------------------------------------------
    # 핵심 분석 로직
    # -------------------------------------------------------------------------

    def analyze(
        self,
        candidate: DetectionCandidate,
        snapshots: list[MotionSnapshot],
    ) -> PhaseResult:
        """드리블 동작을 위상 분석한다.

        복수 바운스가 있을 경우, 모든 사이클을 분석한 뒤
        가장 품질이 높은 사이클을 대표 PhaseResult로 반환한다.

        Args:
            candidate: DRIBBLING DetectionCandidate.
            snapshots: 해당 구간의 MotionSnapshot 시퀀스.

        Returns:
            PhaseResult (4단계 위상 + 일관성 + 부드러움).
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
            return self._empty_result(candidate)

        # 1. 활성 손 결정 (더 빠른 쪽)
        active_wrist = self._determine_active_hand(segment)

        # 2. 바운스 사이클 감지
        cycles = self._detect_bounce_cycles(segment, active_wrist)

        if not cycles:
            # 사이클 감지 실패: 전체를 단일 사이클로 취급
            cycles = [self._fallback_single_cycle(segment)]

        # 3. 사이클별 위상 분석
        cycle_results: list[list[PhaseSegment]] = []
        for cycle_start, cycle_end in cycles:
            cycle_snaps = segment[cycle_start:cycle_end + 1]
            if len(cycle_snaps) >= 2:
                phases = self._analyze_single_cycle(cycle_snaps, active_wrist)
                cycle_results.append(phases)

        if not cycle_results:
            return self._empty_result(candidate)

        # 4. 대표 사이클 선택 (최고 평균 품질)
        best_idx = 0
        best_quality = 0.0
        for i, phases in enumerate(cycle_results):
            avg_q = sum(p.quality for p in phases) / len(phases) if phases else 0.0
            if avg_q > best_quality:
                best_quality = avg_q
                best_idx = i

        best_phases = cycle_results[best_idx]

        # 5. 사이클 일관성 평가
        consistency = self._evaluate_cycle_consistency(cycle_results)

        # 6. 전환 부드러움
        smoothness = self._evaluate_transition_smoothness(best_phases)

        return PhaseResult(
            action_type=ActionType.DRIBBLING,
            player_tracking_id=candidate.player_tracking_id,
            phases=best_phases,
            total_duration_frames=candidate.duration_frames,
            kinetic_chain_score=consistency,
            transition_smoothness=smoothness,
            start_frame=candidate.start_frame,
            end_frame=candidate.end_frame,
        )

    # -------------------------------------------------------------------------
    # 활성 손 결정
    # -------------------------------------------------------------------------

    def _determine_active_hand(
        self,
        segment: list[MotionSnapshot],
    ) -> JointType:
        """드리블 활성 손(손목)을 결정한다.

        전체 구간에서 평균 속도가 높은 쪽을 활성 손으로 판단.

        Args:
            segment: MotionSnapshot 시퀀스.

        Returns:
            JointType.RIGHT_WRIST 또는 LEFT_WRIST.
        """
        right_total = 0.0
        left_total = 0.0
        count = 0

        for snap in segment:
            r_spd = snap.get_speed(JointType.RIGHT_WRIST)
            l_spd = snap.get_speed(JointType.LEFT_WRIST)
            right_total += r_spd
            left_total += l_spd
            count += 1

        if count == 0:
            return JointType.RIGHT_WRIST

        return (
            JointType.RIGHT_WRIST
            if right_total >= left_total
            else JointType.LEFT_WRIST
        )

    # -------------------------------------------------------------------------
    # 바운스 사이클 감지
    # -------------------------------------------------------------------------

    def _detect_bounce_cycles(
        self,
        segment: list[MotionSnapshot],
        active_wrist: JointType,
    ) -> list[tuple[int, int]]:
        """바운스 사이클(극소점 기반)을 감지한다.

        손목 y좌표의 극소점(valley)을 바운스 바닥으로 간주.
        연속 두 극소점 사이를 하나의 사이클로 정의.

        Args:
            segment: MotionSnapshot 시퀀스.
            active_wrist: 활성 손목 관절.

        Returns:
            [(start_idx, end_idx), ...] 사이클 목록.
        """
        # 손목 y좌표 시퀀스 추출
        y_coords: list[float] = []
        for snap in segment:
            pos = snap.get_position(active_wrist)
            if pos is not None:
                y_coords.append(pos[1])
            else:
                # 위치 없으면 이전값 유지
                y_coords.append(y_coords[-1] if y_coords else 0.0)

        if len(y_coords) < 4:
            return []

        # 극소점 찾기 (valley: y[i] < y[i-1] and y[i] < y[i+1])
        valleys: list[int] = []
        for i in range(1, len(y_coords) - 1):
            if y_coords[i] < y_coords[i - 1] and y_coords[i] <= y_coords[i + 1]:
                valleys.append(i)

        if len(valleys) < 2:
            # 극소점 1개 이하: 전체를 단일 사이클
            return []

        # 연속 valley 쌍을 사이클로 매핑
        # 사이클 경계: valley 중간의 극대점(peak)을 기준으로 분할
        cycles: list[tuple[int, int]] = []
        for v in range(len(valleys) - 1):
            # 사이클: valley[v]의 약간 이전 ~ valley[v+1]의 약간 이후
            start = max(0, valleys[v] - 1)
            end = min(len(segment) - 1, valleys[v + 1] + 1)
            if end - start >= 3:
                cycles.append((start, end))

        return cycles

    def _fallback_single_cycle(
        self,
        segment: list[MotionSnapshot],
    ) -> tuple[int, int]:
        """사이클 감지 실패 시 전체를 단일 사이클로.

        Args:
            segment: MotionSnapshot 시퀀스.

        Returns:
            (0, len-1).
        """
        return (0, len(segment) - 1)

    # -------------------------------------------------------------------------
    # 단일 사이클 위상 분석
    # -------------------------------------------------------------------------

    def _analyze_single_cycle(
        self,
        cycle_snaps: list[MotionSnapshot],
        active_wrist: JointType,
    ) -> list[PhaseSegment]:
        """단일 바운스 사이클을 4단계 위상으로 분석한다.

        손목 y좌표 프로파일:
            catch(높음) → push_down(하강) → ball_contact(최저) → rise(상승) → catch(높음)

        Args:
            cycle_snaps: 사이클 내 스냅샷.
            active_wrist: 활성 손목.

        Returns:
            4개의 PhaseSegment (순서: push_down, ball_contact, rise, catch).
        """
        n = len(cycle_snaps)
        if n < 2:
            return self._minimal_phases(cycle_snaps)

        # 손목 y좌표
        y_vals = []
        for s in cycle_snaps:
            pos = s.get_position(active_wrist)
            y_vals.append(pos[1] if pos else 0.0)

        # 최저점(ball_contact) 인덱스
        min_idx = 0
        min_y = y_vals[0]
        for i, y in enumerate(y_vals):
            if y < min_y:
                min_y = y
                min_idx = i

        # 위상 경계 결정
        # push_down: 시작 ~ 최저점 직전
        # ball_contact: 최저점 (1~3 프레임)
        # rise: 최저점 직후 ~ 마지막 직전
        # catch: 마지막 부분

        contact_start = max(0, min_idx - 1)
        contact_end = min(n - 1, min_idx + 1)

        # 각 위상 프레임 범위
        pd_start = 0
        pd_end = max(0, contact_start - 1) if contact_start > 0 else 0

        rise_start = min(n - 1, contact_end + 1)
        rise_end = max(rise_start, n - 2)

        catch_start = min(n - 1, rise_end + 1) if rise_end < n - 1 else n - 1
        catch_end = n - 1

        # PhaseSegment 생성
        phase_defs = [
            (DribblePhase.PUSH_DOWN, pd_start, pd_end),
            (DribblePhase.BALL_CONTACT, contact_start, contact_end),
            (DribblePhase.RISE, rise_start, rise_end),
            (DribblePhase.CATCH, catch_start, catch_end),
        ]

        phases: list[PhaseSegment] = []
        for phase_enum, s_idx, e_idx in phase_defs:
            phase_snaps = cycle_snaps[s_idx:e_idx + 1]
            if not phase_snaps:
                phase_snaps = [cycle_snaps[min(s_idx, n - 1)]]

            start_frame = phase_snaps[0].frame_index
            end_frame = phase_snaps[-1].frame_index
            duration = max(1, end_frame - start_frame)

            metrics = self._extract_phase_metrics(
                phase_enum, phase_snaps, active_wrist,
            )
            quality = self._evaluate_phase_quality(
                phase_enum, phase_snaps, duration, active_wrist,
            )

            phases.append(PhaseSegment(
                phase_name=phase_enum.value,
                start_frame=start_frame,
                end_frame=end_frame,
                duration_frames=duration,
                key_metrics=metrics,
                quality=quality,
            ))

        return phases

    def _minimal_phases(
        self,
        cycle_snaps: list[MotionSnapshot],
    ) -> list[PhaseSegment]:
        """최소 데이터로 4위상을 생성한다 (폴백).

        Args:
            cycle_snaps: 스냅샷 (1~2개).

        Returns:
            4개의 빈 PhaseSegment.
        """
        frame = cycle_snaps[0].frame_index if cycle_snaps else 0
        return [
            PhaseSegment(
                phase_name=phase.value,
                start_frame=frame,
                end_frame=frame,
                duration_frames=0,
                key_metrics={},
                quality=0.0,
            )
            for phase in DribblePhase
        ]

    # -------------------------------------------------------------------------
    # 위상별 지표 추출
    # -------------------------------------------------------------------------

    def _extract_phase_metrics(
        self,
        phase: DribblePhase,
        snaps: list[MotionSnapshot],
        active_wrist: JointType,
    ) -> dict[str, float]:
        """위상별 핵심 지표를 추출한다.

        Args:
            phase: 위상 유형.
            snaps: 해당 위상의 스냅샷.
            active_wrist: 활성 손목.

        Returns:
            지표 딕셔너리.
        """
        metrics: dict[str, float] = {}
        active_shoulder = (
            JointType.RIGHT_SHOULDER
            if active_wrist == JointType.RIGHT_WRIST
            else JointType.LEFT_SHOULDER
        )
        active_elbow = (
            JointType.RIGHT_ELBOW
            if active_wrist == JointType.RIGHT_WRIST
            else JointType.LEFT_ELBOW
        )

        if phase == DribblePhase.PUSH_DOWN:
            # 손목 하강 속도, 팔꿈치 각도
            speeds = [s.get_speed(active_wrist) for s in snaps
                      if s.get_speed(active_wrist) > 0]
            if speeds:
                metrics["avg_wrist_speed_cms"] = sum(speeds) / len(speeds)
                metrics["max_wrist_speed_cms"] = max(speeds)

            elbow_angles = [s.get_angle(active_elbow) for s in snaps
                            if s.get_angle(active_elbow) > 0]
            if elbow_angles:
                metrics["avg_elbow_angle_deg"] = sum(elbow_angles) / len(elbow_angles)

        elif phase == DribblePhase.BALL_CONTACT:
            # 손목 최저 높이, 공 위치 (있으면)
            wrist_heights: list[float] = []
            for s in snaps:
                pos = s.get_position(active_wrist)
                if pos is not None:
                    wrist_heights.append(pos[1])

            if wrist_heights:
                metrics["min_wrist_height_cm"] = min(wrist_heights)

            # 공-손목 거리 (공 위치가 있을 때)
            for s in snaps:
                if s.ball_position is not None:
                    wrist_pos = s.get_position(active_wrist)
                    if wrist_pos is not None:
                        dx = s.ball_position[0] - wrist_pos[0]
                        dy = s.ball_position[1] - wrist_pos[1]
                        dz = s.ball_position[2] - wrist_pos[2]
                        dist = (dx * dx + dy * dy + dz * dz) ** 0.5
                        metrics["ball_hand_distance_cm"] = dist
                        break

        elif phase == DribblePhase.RISE:
            # 손목 상승 속도
            speeds = [s.get_speed(active_wrist) for s in snaps
                      if s.get_speed(active_wrist) > 0]
            if speeds:
                metrics["avg_rise_speed_cms"] = sum(speeds) / len(speeds)

            # 손목 높이 변화
            if len(snaps) >= 2:
                first_pos = snaps[0].get_position(active_wrist)
                last_pos = snaps[-1].get_position(active_wrist)
                if first_pos and last_pos:
                    metrics["height_gain_cm"] = last_pos[1] - first_pos[1]

        elif phase == DribblePhase.CATCH:
            # 손목 안정화 속도, 손목-어깨 높이차
            speeds = [s.get_speed(active_wrist) for s in snaps
                      if s.get_speed(active_wrist) >= 0]
            if speeds:
                metrics["final_wrist_speed_cms"] = speeds[-1] if speeds else 0.0

            for s in snaps:
                h = s.get_relative_height(active_wrist, active_shoulder)
                if h is not None:
                    metrics["wrist_shoulder_diff_cm"] = h
                    break

            # 안정성
            stabilities = [s.stability_index for s in snaps if s.stability_index > 0]
            if stabilities:
                metrics["avg_stability"] = sum(stabilities) / len(stabilities)

        return metrics

    # -------------------------------------------------------------------------
    # 위상 품질 평가
    # -------------------------------------------------------------------------

    def _evaluate_phase_quality(
        self,
        phase: DribblePhase,
        snaps: list[MotionSnapshot],
        duration: int,
        active_wrist: JointType,
    ) -> float:
        """위상 품질을 평가한다 (0~1).

        Args:
            phase: 위상 유형.
            snaps: 해당 위상의 스냅샷.
            duration: 지속 프레임 수.
            active_wrist: 활성 손목.

        Returns:
            품질 점수 (0~1).
        """
        score = 0.0
        checks = 0

        # 1. 지속 시간 적합성
        min_dur, max_dur = self._phase_durations.get(phase, (1, 5))
        if min_dur <= duration <= max_dur:
            score += 1.0
        elif duration > 0:
            if duration < min_dur:
                score += max(0.0, 1.0 - (min_dur - duration) / max(min_dur, 1))
            else:
                score += max(0.0, 1.0 - (duration - max_dur) / max(max_dur, 1))
        checks += 1

        # 2. 데이터 존재율
        data_count = sum(
            1 for s in snaps
            if s.get_position(active_wrist) is not None
        )
        data_ratio = data_count / len(snaps) if snaps else 0.0
        score += data_ratio
        checks += 1

        # 3. 위상별 특정 기준
        phase_score = self._phase_specific_quality(phase, snaps, active_wrist)
        score += phase_score
        checks += 1

        return min(1.0, score / checks) if checks > 0 else 0.0

    def _phase_specific_quality(
        self,
        phase: DribblePhase,
        snaps: list[MotionSnapshot],
        active_wrist: JointType,
    ) -> float:
        """위상별 특정 품질 기준.

        Args:
            phase: 위상 유형.
            snaps: 스냅샷.
            active_wrist: 활성 손목.

        Returns:
            0~1 점수.
        """
        if phase == DribblePhase.PUSH_DOWN:
            # 손목 하강 동작 존재 (속도 > 0)
            has_motion = any(
                s.get_speed(active_wrist) >= _WRIST_DOWNWARD_SPEED_CMS
                for s in snaps
            )
            return 1.0 if has_motion else 0.4

        elif phase == DribblePhase.BALL_CONTACT:
            # 손목이 엉덩이 이하 높이에 도달
            active_hip = (
                JointType.RIGHT_HIP
                if active_wrist == JointType.RIGHT_WRIST
                else JointType.LEFT_HIP
            )
            for s in snaps:
                h = s.get_relative_height(active_wrist, active_hip)
                if h is not None and h < 0:
                    return 1.0
            return 0.5

        elif phase == DribblePhase.RISE:
            # 상승 동작 존재
            if len(snaps) >= 2:
                first_pos = snaps[0].get_position(active_wrist)
                last_pos = snaps[-1].get_position(active_wrist)
                if first_pos and last_pos and last_pos[1] > first_pos[1]:
                    return 1.0
            return 0.4

        elif phase == DribblePhase.CATCH:
            # 속도 감속 (안정화)
            speeds = [s.get_speed(active_wrist) for s in snaps]
            if len(speeds) >= 2 and speeds[0] > 0:
                if speeds[-1] < speeds[0]:
                    return 0.9
            return 0.5

        return 0.5

    # -------------------------------------------------------------------------
    # 사이클 일관성 평가
    # -------------------------------------------------------------------------

    def _evaluate_cycle_consistency(
        self,
        cycle_results: list[list[PhaseSegment]],
    ) -> float:
        """복수 바운스 사이클의 일관성을 평가한다.

        각 사이클의 총 지속 프레임을 비교하여
        변동계수(CV)가 낮을수록 일관성이 높다.

        Args:
            cycle_results: 사이클별 PhaseSegment 목록.

        Returns:
            일관성 점수 (0~1).
        """
        if len(cycle_results) <= 1:
            return 0.7  # 단일 사이클: 일관성 판단 불가 → 중립

        # 사이클별 총 지속 프레임
        durations: list[int] = []
        for phases in cycle_results:
            total = sum(p.duration_frames for p in phases)
            if total > 0:
                durations.append(total)

        if len(durations) < 2:
            return 0.7

        # 변동계수 (CV = std / mean)
        mean_dur = sum(durations) / len(durations)
        if mean_dur <= 0:
            return 0.5

        variance = sum((d - mean_dur) ** 2 for d in durations) / len(durations)
        std_dur = variance ** 0.5
        cv = std_dur / mean_dur

        # CV < 0.1 → 매우 일관 (1.0)
        # CV > 0.5 → 불일관 (0.0)
        if cv <= 0.1:
            return 1.0
        elif cv >= 0.5:
            return 0.0
        else:
            return 1.0 - (cv - 0.1) / 0.4

    # -------------------------------------------------------------------------
    # 전환 부드러움
    # -------------------------------------------------------------------------

    def _evaluate_transition_smoothness(
        self,
        phases: list[PhaseSegment],
    ) -> float:
        """위상 전환 부드러움을 평가한다.

        인접 위상 간 품질 차이가 작을수록 부드러운 전환.

        Args:
            phases: PhaseSegment 목록.

        Returns:
            부드러움 점수 (0~1).
        """
        if len(phases) < 2:
            return 0.5

        quality_diffs: list[float] = []
        for i in range(len(phases) - 1):
            diff = abs(phases[i].quality - phases[i + 1].quality)
            quality_diffs.append(diff)

        if not quality_diffs:
            return 0.5

        avg_diff = sum(quality_diffs) / len(quality_diffs)
        # 차이 0 → 1.0, 차이 1.0 → 0.0
        return max(0.0, 1.0 - avg_diff)

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------

    def _empty_result(self, candidate: DetectionCandidate) -> PhaseResult:
        """데이터 부족 시 빈 PhaseResult를 생성한다.

        Args:
            candidate: 원본 DetectionCandidate.

        Returns:
            빈 PhaseResult.
        """
        return PhaseResult(
            action_type=ActionType.DRIBBLING,
            player_tracking_id=candidate.player_tracking_id,
            phases=[],
            total_duration_frames=candidate.duration_frames,
            kinetic_chain_score=0.0,
            transition_smoothness=0.0,
            start_frame=candidate.start_frame,
            end_frame=candidate.end_frame,
        )

    def __repr__(self) -> str:
        return f"DribblePhaseAnalyzer(phases=4)"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "DribblePhaseAnalyzer",
]

__version__ = "1.0.0"
