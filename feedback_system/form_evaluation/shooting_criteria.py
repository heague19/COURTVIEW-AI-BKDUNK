# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/form_evaluation
파일: shooting_criteria.py
설명: 슈팅 폼 평가 기준 관리 (Tier 4)
      - configs/analysis/shooting_criteria.yaml 로딩
      - 8개 카테고리 × 100점 배분 기준 데이터클래스
      - 연령/실력 수준별 조정 계수 적용
      - 기준 범위 판정 (optimal/acceptable/out_of_range)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

학술 근거:
    - Miller, S. & Bartlett, R. (1996). J. Sports Sciences, 14(3), 243-253.
    - Okazaki, V.H.A. & Rodacki, A.L.F. (2012). J. Sports Sci. & Med., 11, 231.
    - Knudson, D. (1993). J. Physical Education, 64(2), 67-73.

참조:
    - configs/analysis/shooting_criteria.yaml: 기준 데이터
    - motion_analysis/models.py: FormScore, FeedbackItem, FeedbackSeverity

소비자:
    - motion_analysis/form_evaluation/shooting_form_evaluator.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Final

from motion_analysis.models import FeedbackSeverity


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# --- 기본 점수 배분 (100점 만점, shooting_criteria.yaml score_weights) ---
_DEFAULT_SCORE_WEIGHTS: Final[dict[str, float]] = {
    "stance_and_balance": 15.0,
    "ball_position": 10.0,
    "elbow_alignment": 15.0,
    "release_mechanics": 20.0,
    "follow_through": 15.0,
    "arc_and_trajectory": 10.0,
    "body_coordination": 10.0,
    "consistency": 5.0,
}

# --- 기본 조정 계수 ---
_DEFAULT_ADJUSTMENT_FACTORS: Final[dict[str, float]] = {
    "beginner": 1.3,
    "intermediate": 1.1,
    "advanced": 0.95,
    "professional": 0.8,
}


# =============================================================================
# 범위 판정 결과
# =============================================================================

@dataclass(slots=True)
class RangeJudgment:
    """기준 범위 판정 결과.

    측정값이 최적/허용/범위 밖 중 어디에 해당하는지.

    Attributes:
        value: 측정값.
        optimal: 최적값.
        range_min: 허용 최소.
        range_max: 허용 최대.
        deviation: 최적값 대비 편차 (절대값).
        deviation_ratio: 편차 비율 (0~1+).
        severity: 판정 심각도.
    """

    value: float = 0.0
    optimal: float = 0.0
    range_min: float = 0.0
    range_max: float = 0.0
    deviation: float = 0.0
    deviation_ratio: float = 0.0
    severity: FeedbackSeverity = FeedbackSeverity.GOOD

    def __repr__(self) -> str:
        return (
            f"RangeJudgment({self.value:.1f}, "
            f"opt={self.optimal:.1f}, {self.severity.value})"
        )


# =============================================================================
# 카테고리별 기준 데이터클래스
# =============================================================================

@dataclass(slots=True)
class StanceBalanceCriteria:
    """자세/균형 기준 (15점).

    Attributes:
        feet_width_ratio_optimal: 발 너비 비율 최적값.
        feet_width_range: 허용 범위 [min, max].
        shooting_foot_forward_m: 슈팅 발 전진 최적 거리.
        foot_forward_range: 허용 범위.
        knee_bend_deg_optimal: 무릎 굽힘 최적 각도.
        knee_bend_range: 허용 범위.
        weight_dist_optimal: 체중 분배 최적값 (앞발 비율).
        weight_dist_range: 허용 범위.
        trunk_lean_optimal_deg: 몸통 기울기 최적값.
        trunk_lean_max_deg: 최대 허용.
    """

    feet_width_ratio_optimal: float = 1.0
    feet_width_range: tuple[float, float] = (0.8, 1.2)
    shooting_foot_forward_m: float = 0.10
    foot_forward_range: tuple[float, float] = (0.05, 0.20)
    knee_bend_deg_optimal: float = 130.0
    knee_bend_range: tuple[float, float] = (115.0, 145.0)
    weight_dist_optimal: float = 0.55
    weight_dist_range: tuple[float, float] = (0.50, 0.60)
    trunk_lean_optimal_deg: float = 5.0
    trunk_lean_max_deg: float = 15.0


@dataclass(slots=True)
class BallPositionCriteria:
    """공 위치/셋 포인트 기준 (10점).

    Attributes:
        set_point_height_optimal: 셋 포인트 높이 비율 (머리 대비).
        set_point_height_range: 허용 범위.
        lateral_offset_max_m: 좌우 편차 최대 허용.
    """

    set_point_height_optimal: float = 0.95
    set_point_height_range: tuple[float, float] = (0.85, 1.05)
    lateral_offset_max_m: float = 0.10


@dataclass(slots=True)
class ElbowAlignmentCriteria:
    """팔꿈치 정렬 기준 (15점).

    Attributes:
        set_angle_optimal_deg: 셋 포지션 팔꿈치 각도.
        set_angle_range: 허용 범위.
        vertical_alignment_max_deg: 수직 정렬 편차 최대.
        elbow_flare_max_deg: 팔꿈치 외전 최대.
        release_angle_optimal_deg: 릴리스 시 팔꿈치 각도.
        release_angle_range: 허용 범위.
    """

    set_angle_optimal_deg: float = 90.0
    set_angle_range: tuple[float, float] = (75.0, 105.0)
    vertical_alignment_max_deg: float = 10.0
    elbow_flare_max_deg: float = 15.0
    release_angle_optimal_deg: float = 160.0
    release_angle_range: tuple[float, float] = (145.0, 175.0)


@dataclass(slots=True)
class ReleaseMechanicsCriteria:
    """릴리스 메커닉 기준 (20점).

    Attributes:
        release_angle_optimal_deg: 릴리스 각도 (수평 대비).
        release_angle_range: 허용 범위.
        release_height_ratio_optimal: 릴리스 높이 (키 대비).
        release_height_range: 허용 범위.
        wrist_snap_angular_vel_optimal: 손목 스냅 각속도 (deg/s).
        wrist_snap_range: 허용 범위.
        release_timing_window_frames: 릴리스 타이밍 허용 오차 (프레임).
        backspin_rpm_optimal: 백스핀 RPM.
        backspin_range: 허용 범위.
    """

    release_angle_optimal_deg: float = 52.0
    release_angle_range: tuple[float, float] = (40.0, 60.0)
    release_height_ratio_optimal: float = 1.15
    release_height_range: tuple[float, float] = (1.05, 1.30)
    wrist_snap_angular_vel_optimal: float = 800.0
    wrist_snap_range: tuple[float, float] = (500.0, 1200.0)
    release_timing_window_frames: int = 3
    backspin_rpm_optimal: float = 120.0
    backspin_range: tuple[float, float] = (60.0, 180.0)


@dataclass(slots=True)
class FollowThroughCriteria:
    """팔로우 스루 기준 (15점).

    Attributes:
        arm_extension_optimal: 팔 신전 비율.
        arm_extension_min: 최소 신전.
        wrist_flexion_optimal_deg: 손목 꺾임 최적 각도.
        wrist_flexion_range: 허용 범위.
        hold_duration_optimal_frames: 유지 시간 최적값.
        hold_duration_min_frames: 최소 유지.
        finger_deviation_max_deg: 손가락 방향 편차 최대.
    """

    arm_extension_optimal: float = 0.95
    arm_extension_min: float = 0.85
    wrist_flexion_optimal_deg: float = 60.0
    wrist_flexion_range: tuple[float, float] = (40.0, 80.0)
    hold_duration_optimal_frames: int = 15
    hold_duration_min_frames: int = 8
    finger_deviation_max_deg: float = 15.0


@dataclass(slots=True)
class ArcTrajectoryCriteria:
    """궤적/아크 기준 (10점).

    Attributes:
        entry_angle_optimal_deg: 림 진입 각도.
        entry_angle_range: 허용 범위.
        arc_height_optimal_m: 아크 높이 (림 위).
        arc_height_range: 허용 범위.
        lateral_deviation_max_m: 좌우 편차 최대.
    """

    entry_angle_optimal_deg: float = 45.0
    entry_angle_range: tuple[float, float] = (38.0, 55.0)
    arc_height_optimal_m: float = 0.6
    arc_height_range: tuple[float, float] = (0.3, 1.2)
    lateral_deviation_max_m: float = 0.15


@dataclass(slots=True)
class BodyCoordinationCriteria:
    """신체 협응 기준 (10점).

    Attributes:
        sequence_timing_tolerance_frames: 키네틱 체인 타이밍 오차 허용.
        jump_height_min_m: 점프슛 최소 점프 높이.
        free_throw_jump_max_m: 자유투 최대 점프 높이.
        three_point_jump_min_m: 3점슛 최소 점프 높이.
    """

    sequence_timing_tolerance_frames: int = 2
    jump_height_min_m: float = 0.10
    free_throw_jump_max_m: float = 0.05
    three_point_jump_min_m: float = 0.08


# =============================================================================
# 슈팅 기준 통합 관리자
# =============================================================================

@dataclass(slots=True)
class ShootingCriteria:
    """
    슈팅 폼 평가 기준 통합 관리자.

    configs/analysis/shooting_criteria.yaml의 전체 설정을 로딩하여
    8개 카테고리별 기준 + 점수 배분 + 조정 계수를 관리한다.

    사용 예:
        >>> criteria = ShootingCriteria.from_yaml(yaml_dict)
        >>> judgment = criteria.judge_range(90.0, criteria.elbow.set_angle_optimal_deg,
        ...                                 criteria.elbow.set_angle_range)

    Attributes:
        score_weights: 카테고리별 점수 배분.
        stance: 자세/균형 기준.
        ball_position: 공 위치 기준.
        elbow: 팔꿈치 정렬 기준.
        release: 릴리스 메커닉 기준.
        follow_through: 팔로우 스루 기준.
        arc: 궤적/아크 기준.
        coordination: 신체 협응 기준.
        adjustment_factors: 실력 수준별 조정 계수.
    """

    score_weights: dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_SCORE_WEIGHTS))
    stance: StanceBalanceCriteria = field(default_factory=StanceBalanceCriteria)
    ball_position: BallPositionCriteria = field(default_factory=BallPositionCriteria)
    elbow: ElbowAlignmentCriteria = field(default_factory=ElbowAlignmentCriteria)
    release: ReleaseMechanicsCriteria = field(default_factory=ReleaseMechanicsCriteria)
    follow_through: FollowThroughCriteria = field(default_factory=FollowThroughCriteria)
    arc: ArcTrajectoryCriteria = field(default_factory=ArcTrajectoryCriteria)
    coordination: BodyCoordinationCriteria = field(default_factory=BodyCoordinationCriteria)
    adjustment_factors: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_ADJUSTMENT_FACTORS),
    )

    @classmethod
    def from_yaml(cls, config: dict) -> ShootingCriteria:
        """YAML 딕셔너리에서 ShootingCriteria를 생성한다.

        Args:
            config: shooting_criteria.yaml 전체 딕셔너리.

        Returns:
            ShootingCriteria 인스턴스.
        """
        # 점수 배분
        weights = config.get("score_weights", {})
        score_w = dict(_DEFAULT_SCORE_WEIGHTS)
        for key in score_w:
            if key in weights:
                score_w[key] = float(weights[key])

        # 카테고리별 파싱
        stance = cls._parse_stance(config.get("stance_and_balance", {}))
        ball_pos = cls._parse_ball_position(config.get("ball_position", {}))
        elbow = cls._parse_elbow(config.get("elbow_alignment", {}))
        release = cls._parse_release(config.get("release_mechanics", {}))
        ft = cls._parse_follow_through(config.get("follow_through", {}))
        arc = cls._parse_arc(config.get("arc_and_trajectory", {}))
        coord = cls._parse_coordination(config.get("body_coordination", {}))

        # 조정 계수
        adj = config.get("adjustment_factors", {})
        factors = dict(_DEFAULT_ADJUSTMENT_FACTORS)
        for key in factors:
            if key in adj:
                factors[key] = float(adj[key])

        return cls(
            score_weights=score_w,
            stance=stance,
            ball_position=ball_pos,
            elbow=elbow,
            release=release,
            follow_through=ft,
            arc=arc,
            coordination=coord,
            adjustment_factors=factors,
        )

    # -------------------------------------------------------------------------
    # 범위 판정
    # -------------------------------------------------------------------------

    @staticmethod
    def judge_range(
        value: float,
        optimal: float,
        acceptable_range: tuple[float, float],
        adjustment: float = 1.0,
    ) -> RangeJudgment:
        """측정값의 기준 범위 판정.

        adjustment는 실력 수준별 조정 계수로,
        acceptable_range를 확장/축소한다.

        Args:
            value: 측정값.
            optimal: 최적값.
            acceptable_range: 허용 범위 (min, max).
            adjustment: 조정 계수 (1.0=기본, 1.3=초보 허용 확대).

        Returns:
            RangeJudgment.
        """
        # 조정된 범위
        range_center = (acceptable_range[0] + acceptable_range[1]) / 2
        half_width = (acceptable_range[1] - acceptable_range[0]) / 2
        adjusted_half = half_width * adjustment
        adj_min = range_center - adjusted_half
        adj_max = range_center + adjusted_half

        deviation = abs(value - optimal)
        opt_abs = abs(optimal) if optimal != 0 else 1.0
        deviation_ratio = deviation / opt_abs

        # 판정
        if deviation_ratio <= 0.05:
            severity = FeedbackSeverity.EXCELLENT
        elif adj_min <= value <= adj_max:
            severity = FeedbackSeverity.GOOD
        elif (adj_min - half_width * 0.5) <= value <= (adj_max + half_width * 0.5):
            severity = FeedbackSeverity.WARNING
        else:
            severity = FeedbackSeverity.CRITICAL

        return RangeJudgment(
            value=value,
            optimal=optimal,
            range_min=adj_min,
            range_max=adj_max,
            deviation=deviation,
            deviation_ratio=deviation_ratio,
            severity=severity,
        )

    @staticmethod
    def judge_max(
        value: float,
        max_allowed: float,
        adjustment: float = 1.0,
    ) -> RangeJudgment:
        """최대 허용값 기준 판정.

        Args:
            value: 측정값.
            max_allowed: 최대 허용값.
            adjustment: 조정 계수.

        Returns:
            RangeJudgment.
        """
        adj_max = max_allowed * adjustment
        deviation = max(0.0, value - adj_max)

        if value <= adj_max * 0.5:
            severity = FeedbackSeverity.EXCELLENT
        elif value <= adj_max:
            severity = FeedbackSeverity.GOOD
        elif value <= adj_max * 1.5:
            severity = FeedbackSeverity.WARNING
        else:
            severity = FeedbackSeverity.CRITICAL

        return RangeJudgment(
            value=value,
            optimal=0.0,
            range_min=0.0,
            range_max=adj_max,
            deviation=deviation,
            deviation_ratio=deviation / adj_max if adj_max > 0 else 0.0,
            severity=severity,
        )

    def get_adjustment(self, skill_level: str) -> float:
        """실력 수준별 조정 계수를 반환한다.

        Args:
            skill_level: "beginner", "intermediate", "advanced", "professional".

        Returns:
            조정 계수 (기본 1.0).
        """
        return self.adjustment_factors.get(skill_level, 1.0)

    # -------------------------------------------------------------------------
    # YAML 파싱 헬퍼
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_stance(cfg: dict) -> StanceBalanceCriteria:
        """stance_and_balance 섹션 파싱."""
        c = StanceBalanceCriteria()
        if not cfg:
            return c

        fw = cfg.get("feet_width_ratio", {})
        c.feet_width_ratio_optimal = float(fw.get("optimal", c.feet_width_ratio_optimal))
        r = fw.get("acceptable_range", list(c.feet_width_range))
        c.feet_width_range = (float(r[0]), float(r[1]))

        sf = cfg.get("shooting_foot_forward_m", {})
        c.shooting_foot_forward_m = float(sf.get("optimal", c.shooting_foot_forward_m))
        r = sf.get("acceptable_range", list(c.foot_forward_range))
        c.foot_forward_range = (float(r[0]), float(r[1]))

        kb = cfg.get("knee_bend_angle_deg", {})
        c.knee_bend_deg_optimal = float(kb.get("optimal", c.knee_bend_deg_optimal))
        r = kb.get("acceptable_range", list(c.knee_bend_range))
        c.knee_bend_range = (float(r[0]), float(r[1]))

        wd = cfg.get("weight_distribution_ratio", {})
        c.weight_dist_optimal = float(wd.get("optimal", c.weight_dist_optimal))
        r = wd.get("acceptable_range", list(c.weight_dist_range))
        c.weight_dist_range = (float(r[0]), float(r[1]))

        tl = cfg.get("trunk_lean_deg", {})
        c.trunk_lean_optimal_deg = float(tl.get("optimal", c.trunk_lean_optimal_deg))
        c.trunk_lean_max_deg = float(tl.get("max_allowed", c.trunk_lean_max_deg))

        return c

    @staticmethod
    def _parse_ball_position(cfg: dict) -> BallPositionCriteria:
        """ball_position 섹션 파싱."""
        c = BallPositionCriteria()
        if not cfg:
            return c

        sp = cfg.get("set_point_height_ratio", {})
        c.set_point_height_optimal = float(sp.get("optimal", c.set_point_height_optimal))
        r = sp.get("acceptable_range", list(c.set_point_height_range))
        c.set_point_height_range = (float(r[0]), float(r[1]))

        lo = cfg.get("set_point_lateral_offset_m", {})
        c.lateral_offset_max_m = float(lo.get("max_deviation", c.lateral_offset_max_m))

        return c

    @staticmethod
    def _parse_elbow(cfg: dict) -> ElbowAlignmentCriteria:
        """elbow_alignment 섹션 파싱."""
        c = ElbowAlignmentCriteria()
        if not cfg:
            return c

        sa = cfg.get("set_angle_deg", {})
        c.set_angle_optimal_deg = float(sa.get("optimal", c.set_angle_optimal_deg))
        r = sa.get("acceptable_range", list(c.set_angle_range))
        c.set_angle_range = (float(r[0]), float(r[1]))

        va = cfg.get("vertical_alignment_deviation_deg", {})
        c.vertical_alignment_max_deg = float(
            va.get("max_allowed", c.vertical_alignment_max_deg)
            if isinstance(va, dict)
            else va or c.vertical_alignment_max_deg
        )

        ef = cfg.get("elbow_flare_deg", {})
        c.elbow_flare_max_deg = float(
            ef.get("max_allowed", c.elbow_flare_max_deg)
            if isinstance(ef, dict)
            else ef or c.elbow_flare_max_deg
        )

        ra = cfg.get("release_angle_deg", {})
        c.release_angle_optimal_deg = float(ra.get("optimal", c.release_angle_optimal_deg))
        r = ra.get("acceptable_range", list(c.release_angle_range))
        c.release_angle_range = (float(r[0]), float(r[1]))

        return c

    @staticmethod
    def _parse_release(cfg: dict) -> ReleaseMechanicsCriteria:
        """release_mechanics 섹션 파싱."""
        c = ReleaseMechanicsCriteria()
        if not cfg:
            return c

        ra = cfg.get("release_angle_deg", {})
        c.release_angle_optimal_deg = float(ra.get("optimal", c.release_angle_optimal_deg))
        r = ra.get("acceptable_range", list(c.release_angle_range))
        c.release_angle_range = (float(r[0]), float(r[1]))

        rh = cfg.get("release_height_ratio", {})
        c.release_height_ratio_optimal = float(rh.get("optimal", c.release_height_ratio_optimal))
        r = rh.get("acceptable_range", list(c.release_height_range))
        c.release_height_range = (float(r[0]), float(r[1]))

        ws = cfg.get("wrist_snap_angular_velocity_degs", {})
        c.wrist_snap_angular_vel_optimal = float(
            ws.get("optimal", c.wrist_snap_angular_vel_optimal)
            if isinstance(ws, dict)
            else ws or c.wrist_snap_angular_vel_optimal
        )
        if isinstance(ws, dict):
            r = ws.get("acceptable_range", list(c.wrist_snap_range))
            c.wrist_snap_range = (float(r[0]), float(r[1]))

        rt = cfg.get("release_timing", {})
        c.release_timing_window_frames = int(
            rt.get("acceptable_window_frames", c.release_timing_window_frames)
            if isinstance(rt, dict)
            else c.release_timing_window_frames
        )

        bs = cfg.get("backspin_rate_rpm", {})
        c.backspin_rpm_optimal = float(
            bs.get("optimal", c.backspin_rpm_optimal)
            if isinstance(bs, dict)
            else bs or c.backspin_rpm_optimal
        )
        if isinstance(bs, dict):
            r = bs.get("acceptable_range", list(c.backspin_range))
            c.backspin_range = (float(r[0]), float(r[1]))

        return c

    @staticmethod
    def _parse_follow_through(cfg: dict) -> FollowThroughCriteria:
        """follow_through 섹션 파싱."""
        c = FollowThroughCriteria()
        if not cfg:
            return c

        ae = cfg.get("arm_extension_ratio", {})
        c.arm_extension_optimal = float(
            ae.get("optimal", c.arm_extension_optimal)
            if isinstance(ae, dict)
            else ae or c.arm_extension_optimal
        )
        if isinstance(ae, dict):
            c.arm_extension_min = float(ae.get("min_required", c.arm_extension_min))

        wf = cfg.get("wrist_flexion_deg", {})
        c.wrist_flexion_optimal_deg = float(wf.get("optimal", c.wrist_flexion_optimal_deg))
        r = wf.get("acceptable_range", list(c.wrist_flexion_range))
        c.wrist_flexion_range = (float(r[0]), float(r[1]))

        hd = cfg.get("hold_duration_frames", {})
        c.hold_duration_optimal_frames = int(
            hd.get("optimal", c.hold_duration_optimal_frames)
            if isinstance(hd, dict)
            else hd or c.hold_duration_optimal_frames
        )
        if isinstance(hd, dict):
            c.hold_duration_min_frames = int(
                hd.get("min_required", c.hold_duration_min_frames),
            )

        c.finger_deviation_max_deg = float(
            cfg.get("finger_deviation_max_deg", c.finger_deviation_max_deg),
        )

        return c

    @staticmethod
    def _parse_arc(cfg: dict) -> ArcTrajectoryCriteria:
        """arc_and_trajectory 섹션 파싱."""
        c = ArcTrajectoryCriteria()
        if not cfg:
            return c

        ea = cfg.get("entry_angle_deg", {})
        c.entry_angle_optimal_deg = float(ea.get("optimal", c.entry_angle_optimal_deg))
        r = ea.get("acceptable_range", list(c.entry_angle_range))
        c.entry_angle_range = (float(r[0]), float(r[1]))

        ah = cfg.get("arc_height_above_rim_m", {})
        c.arc_height_optimal_m = float(ah.get("optimal", c.arc_height_optimal_m))
        r = ah.get("acceptable_range", list(c.arc_height_range))
        c.arc_height_range = (float(r[0]), float(r[1]))

        ld = cfg.get("lateral_deviation_m", {})
        c.lateral_deviation_max_m = float(
            ld.get("max_allowed", c.lateral_deviation_max_m)
            if isinstance(ld, dict)
            else ld or c.lateral_deviation_max_m
        )

        return c

    @staticmethod
    def _parse_coordination(cfg: dict) -> BodyCoordinationCriteria:
        """body_coordination 섹션 파싱."""
        c = BodyCoordinationCriteria()
        if not cfg:
            return c

        c.sequence_timing_tolerance_frames = int(
            cfg.get("sequence_timing_tolerance_frames",
                     c.sequence_timing_tolerance_frames),
        )

        jh = cfg.get("jump_height_m", {})
        c.jump_height_min_m = float(jh.get("jump_shot_min", c.jump_height_min_m))
        c.free_throw_jump_max_m = float(jh.get("free_throw_max", c.free_throw_jump_max_m))
        c.three_point_jump_min_m = float(jh.get("three_point_min", c.three_point_jump_min_m))

        return c

    def __repr__(self) -> str:
        total = sum(self.score_weights.values())
        return f"ShootingCriteria(8 categories, {total:.0f}pts)"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "ShootingCriteria",
    "RangeJudgment",
]

__version__ = "1.0.0"
