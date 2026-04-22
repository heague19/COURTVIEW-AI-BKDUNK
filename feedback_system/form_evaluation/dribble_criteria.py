# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/form_evaluation
파일: dribble_criteria.py
설명: 드리블 폼 평가 기준 관리 (Tier 4)
      - configs/analysis/dribble_criteria.yaml 로딩
      - 8개 카테고리 × 100점 배분 기준 데이터클래스
      - 드리블 유형별 추가 기준 (crossover, behind_the_back 등)
      - 연령/실력 수준별 조정 계수 적용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

학술 근거:
    - Arias, J.L. et al. (2012). J. Human Sport & Exercise, 7(1), 318-329.
    - Cortis, C. et al. (2011). J. Strength & Conditioning Research, 25(1).

참조:
    - configs/analysis/dribble_criteria.yaml: 기준 데이터
    - motion_analysis/form_evaluation/shooting_criteria.py: RangeJudgment 재사용

소비자:
    - motion_analysis/form_evaluation/dribble_form_evaluator.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Final

from motion_analysis.models import FeedbackSeverity
from feedback_system.form_evaluation.shooting_criteria import RangeJudgment


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# --- 기본 점수 배분 (100점 만점, dribble_criteria.yaml score_weights) ---
_DEFAULT_SCORE_WEIGHTS: Final[dict[str, float]] = {
    "hand_position": 15.0,
    "ball_control": 20.0,
    "body_posture": 15.0,
    "head_and_vision": 10.0,
    "rhythm_and_timing": 15.0,
    "protection": 10.0,
    "transition": 10.0,
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
# 카테고리별 기준 데이터클래스
# =============================================================================

@dataclass(slots=True)
class HandPositionCriteria:
    """손 위치/자세 기준 (15점).

    Attributes:
        finger_spread_optimal: 손가락 펼침 비율 최적값.
        finger_spread_range: 허용 범위.
        wrist_angle_push_optimal_deg: 푸시 다운 시 손목 각도.
        wrist_angle_push_range: 허용 범위.
        wrist_angle_catch_optimal_deg: 캐치 시 손목 각도.
        wrist_angle_catch_range: 허용 범위.
    """

    finger_spread_optimal: float = 0.85
    finger_spread_range: tuple[float, float] = (0.7, 1.0)
    wrist_angle_push_optimal_deg: float = 45.0
    wrist_angle_push_range: tuple[float, float] = (30.0, 60.0)
    wrist_angle_catch_optimal_deg: float = 30.0
    wrist_angle_catch_range: tuple[float, float] = (15.0, 50.0)


@dataclass(slots=True)
class BallControlCriteria:
    """볼 컨트롤 기준 (20점).

    Attributes:
        speed_dribble_height_ratio: 빠른 드리블 높이 비율.
        control_dribble_height_ratio: 컨트롤 드리블 높이 비율.
        power_dribble_height_ratio: 파워 드리블 높이 비율.
        height_variation: 높이 허용 변동.
        bounce_lateral_m: 바운스 옆 오프셋.
        bounce_forward_m: 바운스 앞 오프셋.
        contact_time_optimal: 공-손 접촉 시간 비율.
        contact_time_min: 최소 접촉 시간 비율.
        speed_cv_excellent: 속도 변동계수 우수 기준.
        speed_cv_good: 양호 기준.
        speed_cv_acceptable: 허용 기준.
    """

    speed_dribble_height_ratio: float = 0.4
    control_dribble_height_ratio: float = 0.5
    power_dribble_height_ratio: float = 0.3
    height_variation: float = 0.15
    bounce_lateral_m: float = 0.2
    bounce_forward_m: float = 0.3
    contact_time_optimal: float = 0.6
    contact_time_min: float = 0.4
    speed_cv_excellent: float = 0.1
    speed_cv_good: float = 0.2
    speed_cv_acceptable: float = 0.3


@dataclass(slots=True)
class BodyPostureCriteria:
    """신체 자세 기준 (15점).

    Attributes:
        knee_bend_optimal_deg: 무릎 굽힘 최적.
        knee_bend_range: 허용 범위.
        back_angle_optimal_deg: 등 기울기 최적.
        back_angle_range: 허용 범위.
        cog_ratio_optimal: 무게중심 높이 비율 최적.
        cog_ratio_range: 허용 범위.
        shoulder_level_max_deg: 어깨 수평 편차 최대.
        feet_width_optimal: 발 간격 비율 최적.
        feet_width_range: 허용 범위.
    """

    knee_bend_optimal_deg: float = 120.0
    knee_bend_range: tuple[float, float] = (100.0, 140.0)
    back_angle_optimal_deg: float = 15.0
    back_angle_range: tuple[float, float] = (5.0, 25.0)
    cog_ratio_optimal: float = 0.50
    cog_ratio_range: tuple[float, float] = (0.40, 0.55)
    shoulder_level_max_deg: float = 5.0
    feet_width_optimal: float = 1.1
    feet_width_range: tuple[float, float] = (0.9, 1.3)


@dataclass(slots=True)
class HeadVisionCriteria:
    """고개/시야 기준 (10점).

    Attributes:
        head_down_max_deg: 고개 숙임 최대 허용 각도.
    """

    head_down_max_deg: float = 15.0


@dataclass(slots=True)
class RhythmTimingCriteria:
    """리듬/타이밍 기준 (15점).

    Attributes:
        basic_freq_optimal_hz: 기본 드리블 빈도 최적.
        basic_freq_range: 허용 범위.
        speed_freq_optimal_hz: 스피드 드리블 빈도 최적.
        speed_freq_range: 허용 범위.
        crossover_freq_optimal_hz: 크로스오버 빈도 최적.
        crossover_freq_range: 허용 범위.
        rhythm_std_excellent_ms: 리듬 표준편차 우수.
        rhythm_std_good_ms: 양호.
        rhythm_std_acceptable_ms: 허용.
        pace_change_optimal: 변속 비율 최적.
        pace_change_min: 최소.
    """

    basic_freq_optimal_hz: float = 2.5
    basic_freq_range: tuple[float, float] = (1.5, 4.0)
    speed_freq_optimal_hz: float = 3.5
    speed_freq_range: tuple[float, float] = (2.5, 5.0)
    crossover_freq_optimal_hz: float = 3.0
    crossover_freq_range: tuple[float, float] = (2.0, 4.5)
    rhythm_std_excellent_ms: float = 30.0
    rhythm_std_good_ms: float = 50.0
    rhythm_std_acceptable_ms: float = 80.0
    pace_change_optimal: float = 1.5
    pace_change_min: float = 1.2


@dataclass(slots=True)
class ProtectionCriteria:
    """볼 프로텍션 기준 (10점).

    Attributes:
        off_arm_angle_optimal_deg: 비드리블 팔 각도 최적.
        off_arm_angle_range: 허용 범위.
        body_ball_distance_optimal_m: 몸-공 거리 최적.
        body_ball_distance_max_m: 최대 허용.
        ball_exposure_max_ratio: 공 노출 최대 비율.
    """

    off_arm_angle_optimal_deg: float = 90.0
    off_arm_angle_range: tuple[float, float] = (60.0, 120.0)
    body_ball_distance_optimal_m: float = 0.3
    body_ball_distance_max_m: float = 0.6
    ball_exposure_max_ratio: float = 0.4


@dataclass(slots=True)
class TransitionCriteria:
    """전환 동작 기준 (10점).

    Attributes:
        dribble_to_shot_excellent: 드리블→슛 전환 우수 프레임.
        dribble_to_shot_good: 양호.
        dribble_to_shot_acceptable: 허용.
        dribble_to_pass_excellent: 드리블→패스 전환 우수.
        dribble_to_pass_good: 양호.
        dribble_to_pass_acceptable: 허용.
        hand_switch_excellent: 좌우 전환 우수.
        hand_switch_good: 양호.
        hand_switch_acceptable: 허용.
    """

    dribble_to_shot_excellent: int = 8
    dribble_to_shot_good: int = 12
    dribble_to_shot_acceptable: int = 18
    dribble_to_pass_excellent: int = 6
    dribble_to_pass_good: int = 10
    dribble_to_pass_acceptable: int = 15
    hand_switch_excellent: int = 4
    hand_switch_good: int = 8
    hand_switch_acceptable: int = 12


@dataclass(slots=True)
class TechniqueSpecificCriteria:
    """드리블 유형별 추가 기준.

    Attributes:
        crossover_height_ratio: 크로스오버 볼 이동 높이.
        crossover_angle_deg: 교차 각도.
        crossover_symmetry: 좌우 대칭.
        behind_back_clearance_m: 비하인드 패스 여유 거리.
        between_legs_stride_ratio: 비트윈레그 보폭 비율.
        spin_rotation_degs: 스핀무브 회전 목표.
    """

    crossover_height_ratio: float = 0.3
    crossover_angle_deg: float = 45.0
    crossover_symmetry: float = 0.9
    behind_back_clearance_m: float = 0.1
    between_legs_stride_ratio: float = 1.3
    spin_rotation_degs: float = 360.0


# =============================================================================
# 드리블 기준 통합 관리자
# =============================================================================

@dataclass(slots=True)
class DribbleCriteria:
    """
    드리블 폼 평가 기준 통합 관리자.

    configs/analysis/dribble_criteria.yaml의 전체 설정을 로딩하여
    8개 카테고리별 기준 + 유형별 기준 + 조정 계수를 관리한다.

    사용 예:
        >>> criteria = DribbleCriteria.from_yaml(yaml_dict)
        >>> judgment = criteria.judge_range(120.0,
        ...     criteria.posture.knee_bend_optimal_deg,
        ...     criteria.posture.knee_bend_range)

    Attributes:
        score_weights: 카테고리별 점수 배분.
        hand: 손 위치 기준.
        ball_control: 볼 컨트롤 기준.
        posture: 신체 자세 기준.
        head: 고개/시야 기준.
        rhythm: 리듬/타이밍 기준.
        protection: 볼 프로텍션 기준.
        transition: 전환 동작 기준.
        technique: 유형별 추가 기준.
        adjustment_factors: 실력 수준별 조정 계수.
    """

    score_weights: dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_SCORE_WEIGHTS))
    hand: HandPositionCriteria = field(default_factory=HandPositionCriteria)
    ball_control: BallControlCriteria = field(default_factory=BallControlCriteria)
    posture: BodyPostureCriteria = field(default_factory=BodyPostureCriteria)
    head: HeadVisionCriteria = field(default_factory=HeadVisionCriteria)
    rhythm: RhythmTimingCriteria = field(default_factory=RhythmTimingCriteria)
    protection: ProtectionCriteria = field(default_factory=ProtectionCriteria)
    transition: TransitionCriteria = field(default_factory=TransitionCriteria)
    technique: TechniqueSpecificCriteria = field(default_factory=TechniqueSpecificCriteria)
    adjustment_factors: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_ADJUSTMENT_FACTORS),
    )

    @classmethod
    def from_yaml(cls, config: dict) -> DribbleCriteria:
        """YAML 딕셔너리에서 DribbleCriteria를 생성한다.

        Args:
            config: dribble_criteria.yaml 전체 딕셔너리.

        Returns:
            DribbleCriteria 인스턴스.
        """
        # 점수 배분
        weights = config.get("score_weights", {})
        score_w = dict(_DEFAULT_SCORE_WEIGHTS)
        for key in score_w:
            if key in weights:
                score_w[key] = float(weights[key])

        hand = cls._parse_hand(config.get("hand_position", {}))
        ball = cls._parse_ball_control(config.get("ball_control", {}))
        posture = cls._parse_posture(config.get("body_posture", {}))
        head = cls._parse_head(config.get("head_and_vision", {}))
        rhythm = cls._parse_rhythm(config.get("rhythm_and_timing", {}))
        prot = cls._parse_protection(config.get("protection", {}))
        trans = cls._parse_transition(config.get("transition", {}))
        tech = cls._parse_technique(config.get("technique_specific", {}))

        adj = config.get("adjustment_factors", {})
        factors = dict(_DEFAULT_ADJUSTMENT_FACTORS)
        for key in factors:
            if key in adj:
                factors[key] = float(adj[key])

        return cls(
            score_weights=score_w,
            hand=hand,
            ball_control=ball,
            posture=posture,
            head=head,
            rhythm=rhythm,
            protection=prot,
            transition=trans,
            technique=tech,
            adjustment_factors=factors,
        )

    # -------------------------------------------------------------------------
    # 범위 판정 (ShootingCriteria.judge_range 재사용 패턴)
    # -------------------------------------------------------------------------

    @staticmethod
    def judge_range(
        value: float,
        optimal: float,
        acceptable_range: tuple[float, float],
        adjustment: float = 1.0,
    ) -> RangeJudgment:
        """측정값의 기준 범위 판정.

        Args:
            value: 측정값.
            optimal: 최적값.
            acceptable_range: 허용 범위.
            adjustment: 조정 계수.

        Returns:
            RangeJudgment.
        """
        range_center = (acceptable_range[0] + acceptable_range[1]) / 2
        half_width = (acceptable_range[1] - acceptable_range[0]) / 2
        adjusted_half = half_width * adjustment
        adj_min = range_center - adjusted_half
        adj_max = range_center + adjusted_half

        deviation = abs(value - optimal)
        opt_abs = abs(optimal) if optimal != 0 else 1.0
        deviation_ratio = deviation / opt_abs

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
    def judge_cv(cv: float, excellent: float, good: float, acceptable: float) -> FeedbackSeverity:
        """변동계수(CV)를 등급 판정한다.

        Args:
            cv: 변동계수.
            excellent: 우수 기준.
            good: 양호 기준.
            acceptable: 허용 기준.

        Returns:
            FeedbackSeverity.
        """
        if cv <= excellent:
            return FeedbackSeverity.EXCELLENT
        elif cv <= good:
            return FeedbackSeverity.GOOD
        elif cv <= acceptable:
            return FeedbackSeverity.WARNING
        else:
            return FeedbackSeverity.CRITICAL

    def get_adjustment(self, skill_level: str) -> float:
        """실력 수준별 조정 계수.

        Args:
            skill_level: 실력 수준 키.

        Returns:
            조정 계수.
        """
        return self.adjustment_factors.get(skill_level, 1.0)

    # -------------------------------------------------------------------------
    # YAML 파싱 헬퍼
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_hand(cfg: dict) -> HandPositionCriteria:
        """hand_position 섹션 파싱."""
        c = HandPositionCriteria()
        if not cfg:
            return c

        fs = cfg.get("finger_spread_ratio", {})
        c.finger_spread_optimal = float(fs.get("optimal", c.finger_spread_optimal))
        r = fs.get("acceptable_range", list(c.finger_spread_range))
        c.finger_spread_range = (float(r[0]), float(r[1]))

        wa = cfg.get("wrist_angle_deg", {})
        pd = wa.get("push_down", {})
        c.wrist_angle_push_optimal_deg = float(pd.get("optimal", c.wrist_angle_push_optimal_deg))
        r = pd.get("acceptable_range", list(c.wrist_angle_push_range))
        c.wrist_angle_push_range = (float(r[0]), float(r[1]))

        ca = wa.get("catch", {})
        c.wrist_angle_catch_optimal_deg = float(ca.get("optimal", c.wrist_angle_catch_optimal_deg))
        r = ca.get("acceptable_range", list(c.wrist_angle_catch_range))
        c.wrist_angle_catch_range = (float(r[0]), float(r[1]))

        return c

    @staticmethod
    def _parse_ball_control(cfg: dict) -> BallControlCriteria:
        """ball_control 섹션 파싱."""
        c = BallControlCriteria()
        if not cfg:
            return c

        h = cfg.get("height", {})
        c.speed_dribble_height_ratio = float(h.get("speed_dribble_ratio", c.speed_dribble_height_ratio))
        c.control_dribble_height_ratio = float(h.get("control_dribble_ratio", c.control_dribble_height_ratio))
        c.power_dribble_height_ratio = float(h.get("power_dribble_ratio", c.power_dribble_height_ratio))
        c.height_variation = float(h.get("acceptable_variation", c.height_variation))

        bp = cfg.get("bounce_position", {})
        c.bounce_lateral_m = float(bp.get("lateral_offset_m", c.bounce_lateral_m))
        c.bounce_forward_m = float(bp.get("forward_offset_m", c.bounce_forward_m))

        ct = cfg.get("contact_time_ratio", {})
        c.contact_time_optimal = float(ct.get("optimal", c.contact_time_optimal))
        c.contact_time_min = float(ct.get("min_required", c.contact_time_min))

        sc = cfg.get("speed_consistency_cv", {})
        c.speed_cv_excellent = float(sc.get("excellent", c.speed_cv_excellent))
        c.speed_cv_good = float(sc.get("good", c.speed_cv_good))
        c.speed_cv_acceptable = float(sc.get("acceptable", c.speed_cv_acceptable))

        return c

    @staticmethod
    def _parse_posture(cfg: dict) -> BodyPostureCriteria:
        """body_posture 섹션 파싱."""
        c = BodyPostureCriteria()
        if not cfg:
            return c

        kb = cfg.get("knee_bend_deg", {})
        c.knee_bend_optimal_deg = float(kb.get("optimal", c.knee_bend_optimal_deg))
        r = kb.get("acceptable_range", list(c.knee_bend_range))
        c.knee_bend_range = (float(r[0]), float(r[1]))

        ba = cfg.get("back_angle_deg", {})
        c.back_angle_optimal_deg = float(ba.get("optimal", c.back_angle_optimal_deg))
        r = ba.get("acceptable_range", list(c.back_angle_range))
        c.back_angle_range = (float(r[0]), float(r[1]))

        cg = cfg.get("center_of_gravity_ratio", {})
        c.cog_ratio_optimal = float(cg.get("optimal", c.cog_ratio_optimal))
        r = cg.get("acceptable_range", list(c.cog_ratio_range))
        c.cog_ratio_range = (float(r[0]), float(r[1]))

        sl = cfg.get("shoulder_level_deviation_deg", {})
        c.shoulder_level_max_deg = float(
            sl.get("max_allowed", c.shoulder_level_max_deg)
            if isinstance(sl, dict)
            else sl or c.shoulder_level_max_deg
        )

        fw = cfg.get("feet_width_ratio", {})
        c.feet_width_optimal = float(fw.get("optimal", c.feet_width_optimal))
        r = fw.get("acceptable_range", list(c.feet_width_range))
        c.feet_width_range = (float(r[0]), float(r[1]))

        return c

    @staticmethod
    def _parse_head(cfg: dict) -> HeadVisionCriteria:
        """head_and_vision 섹션 파싱."""
        c = HeadVisionCriteria()
        if not cfg:
            return c

        ha = cfg.get("head_angle_deg", {})
        c.head_down_max_deg = float(
            ha.get("max_down_tilt", c.head_down_max_deg)
            if isinstance(ha, dict)
            else c.head_down_max_deg
        )
        return c

    @staticmethod
    def _parse_rhythm(cfg: dict) -> RhythmTimingCriteria:
        """rhythm_and_timing 섹션 파싱."""
        c = RhythmTimingCriteria()
        if not cfg:
            return c

        fq = cfg.get("frequency_hz", {})
        basic = fq.get("basic", {})
        c.basic_freq_optimal_hz = float(basic.get("optimal", c.basic_freq_optimal_hz))
        r = basic.get("acceptable_range", list(c.basic_freq_range))
        c.basic_freq_range = (float(r[0]), float(r[1]))

        speed = fq.get("speed", {})
        c.speed_freq_optimal_hz = float(speed.get("optimal", c.speed_freq_optimal_hz))
        r = speed.get("acceptable_range", list(c.speed_freq_range))
        c.speed_freq_range = (float(r[0]), float(r[1]))

        cross = fq.get("crossover", {})
        c.crossover_freq_optimal_hz = float(cross.get("optimal", c.crossover_freq_optimal_hz))
        r = cross.get("acceptable_range", list(c.crossover_freq_range))
        c.crossover_freq_range = (float(r[0]), float(r[1]))

        rs = cfg.get("rhythm_std_ms", {})
        c.rhythm_std_excellent_ms = float(rs.get("excellent", c.rhythm_std_excellent_ms))
        c.rhythm_std_good_ms = float(rs.get("good", c.rhythm_std_good_ms))
        c.rhythm_std_acceptable_ms = float(rs.get("acceptable", c.rhythm_std_acceptable_ms))

        pc = cfg.get("pace_change_ratio", {})
        c.pace_change_optimal = float(pc.get("optimal", c.pace_change_optimal))
        c.pace_change_min = float(pc.get("min_required", c.pace_change_min))

        return c

    @staticmethod
    def _parse_protection(cfg: dict) -> ProtectionCriteria:
        """protection 섹션 파싱."""
        c = ProtectionCriteria()
        if not cfg:
            return c

        oa = cfg.get("off_arm_angle_deg", {})
        c.off_arm_angle_optimal_deg = float(oa.get("optimal", c.off_arm_angle_optimal_deg))
        r = oa.get("acceptable_range", list(c.off_arm_angle_range))
        c.off_arm_angle_range = (float(r[0]), float(r[1]))

        bd = cfg.get("body_ball_distance_m", {})
        c.body_ball_distance_optimal_m = float(bd.get("optimal", c.body_ball_distance_optimal_m))
        c.body_ball_distance_max_m = float(bd.get("max_allowed", c.body_ball_distance_max_m))

        be = cfg.get("ball_exposure_ratio", {})
        c.ball_exposure_max_ratio = float(
            be.get("max_allowed", c.ball_exposure_max_ratio)
            if isinstance(be, dict)
            else be or c.ball_exposure_max_ratio
        )

        return c

    @staticmethod
    def _parse_transition(cfg: dict) -> TransitionCriteria:
        """transition 섹션 파싱."""
        c = TransitionCriteria()
        if not cfg:
            return c

        ds = cfg.get("dribble_to_shot_frames", {})
        c.dribble_to_shot_excellent = int(ds.get("excellent", c.dribble_to_shot_excellent))
        c.dribble_to_shot_good = int(ds.get("good", c.dribble_to_shot_good))
        c.dribble_to_shot_acceptable = int(ds.get("acceptable", c.dribble_to_shot_acceptable))

        dp = cfg.get("dribble_to_pass_frames", {})
        c.dribble_to_pass_excellent = int(dp.get("excellent", c.dribble_to_pass_excellent))
        c.dribble_to_pass_good = int(dp.get("good", c.dribble_to_pass_good))
        c.dribble_to_pass_acceptable = int(dp.get("acceptable", c.dribble_to_pass_acceptable))

        hs = cfg.get("hand_switch_frames", {})
        c.hand_switch_excellent = int(hs.get("excellent", c.hand_switch_excellent))
        c.hand_switch_good = int(hs.get("good", c.hand_switch_good))
        c.hand_switch_acceptable = int(hs.get("acceptable", c.hand_switch_acceptable))

        return c

    @staticmethod
    def _parse_technique(cfg: dict) -> TechniqueSpecificCriteria:
        """technique_specific 섹션 파싱."""
        c = TechniqueSpecificCriteria()
        if not cfg:
            return c

        co = cfg.get("crossover", {})
        c.crossover_height_ratio = float(co.get("ball_transfer_height_ratio", c.crossover_height_ratio))
        c.crossover_angle_deg = float(co.get("cross_angle_deg", c.crossover_angle_deg))
        c.crossover_symmetry = float(co.get("timing_symmetry", c.crossover_symmetry))

        bb = cfg.get("behind_the_back", {})
        c.behind_back_clearance_m = float(bb.get("ball_path_clearance_m", c.behind_back_clearance_m))

        bl = cfg.get("between_the_legs", {})
        c.between_legs_stride_ratio = float(bl.get("stride_width_ratio", c.between_legs_stride_ratio))

        sm = cfg.get("spin_move", {})
        c.spin_rotation_degs = float(sm.get("rotation_speed_degs", c.spin_rotation_degs))

        return c

    def __repr__(self) -> str:
        total = sum(self.score_weights.values())
        return f"DribbleCriteria(8 categories, {total:.0f}pts)"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "DribbleCriteria",
]

__version__ = "1.0.0"
