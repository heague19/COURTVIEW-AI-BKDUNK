# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis
파일: models.py
설명: 5-Tier 동작 분석 파이프라인 내부 데이터 모델 정의
      - MotionSnapshot: 프레임 단위 선수 동작 스냅샷 (전 Tier 공통 입력)
      - DetectionCandidate: Tier 1 감지 후보
      - PhaseSegment / PhaseResult: Tier 3 위상 분석 결과
      - FeedbackItem / FormScore / FormEvaluation: Tier 4 폼 평가 결과
      - ComparisonResult: Tier 5 DTW 비교 결과

      이 파일의 모든 클래스는 motion_analysis 모듈 내부 전용이며,
      외부 소비자는 shared/dto/motion_dto.py를 사용한다.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - shared/dto/motion_dto.py: 외부 소비용 DTO (game_analysis 등)
    - shared/constants/pose_constants.py: JointType 열거형
    - configs/analysis/motion_analysis.yaml: 5-Tier 설정
    - configs/analysis/shooting_criteria.yaml: 슈팅 폼 기준
    - configs/analysis/dribble_criteria.yaml: 드리블 폼 기준

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/dto/motion_dto.py: ActionType

소비자:
    - motion_analysis/detection/: Tier 1 감지기 (MotionSnapshot 입력, DetectionCandidate 출력)
    - motion_analysis/classification/: Tier 2 분류기 (DetectionCandidate 소비)
    - motion_analysis/phase_analysis/: Tier 3 위상 분석 (PhaseResult 출력)
    - motion_analysis/form_evaluation/: Tier 4 폼 평가 (FormEvaluation 출력)
    - motion_analysis/comparison/: Tier 5 비교 (ComparisonResult 출력)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType


# =============================================================================
# 위상(Phase) 열거형
# =============================================================================

@unique
class ShotPhase(str, Enum):
    """
    슈팅 동작 위상 (4단계).

    학술 근거:
        Knudson, D. (1993). "Biomechanics of the Basketball Jump Shot —
        Six Key Teaching Points." J. Physical Education, 64(2), 67-73.

    >>> phase = ShotPhase.RELEASE
    >>> phase.value
    'release'
    """

    PREPARATION = "preparation"        # 슛 준비 (캐치/드리블 스탑)
    LOADING = "loading"                # 파워 로딩 (무릎 굽힘, 에너지 축적)
    RELEASE = "release"                # 릴리스 (팔 펴짐, 공 이탈)
    FOLLOW_THROUGH = "follow_through"  # 팔로우 스루 (손목 스냅, 유지)

    def __str__(self) -> str:
        return self.value

    @property
    def order(self) -> int:
        """위상 순서 (0~3)."""
        return _SHOT_PHASE_ORDER[self]


@unique
class DribblePhase(str, Enum):
    """
    드리블 동작 위상 (4단계).

    학술 근거:
        Arias, J.L. et al. (2012). "Review of biomechanical factors in
        basketball ball handling." J. Human Sport & Exercise, 7(1), 318-329.

    >>> phase = DribblePhase.PUSH_DOWN
    >>> phase.value
    'push_down'
    """

    PUSH_DOWN = "push_down"        # 푸시 다운 (손바닥 → 공)
    BALL_CONTACT = "ball_contact"  # 바닥 접촉
    RISE = "rise"                  # 공 상승
    CATCH = "catch"                # 캐치 (공 제어)

    def __str__(self) -> str:
        return self.value

    @property
    def order(self) -> int:
        """위상 순서 (0~3)."""
        return _DRIBBLE_PHASE_ORDER[self]


# --- 위상 순서 매핑 (위 enum의 order 프로퍼티용) ---
_SHOT_PHASE_ORDER: dict[ShotPhase, int] = {
    ShotPhase.PREPARATION: 0,
    ShotPhase.LOADING: 1,
    ShotPhase.RELEASE: 2,
    ShotPhase.FOLLOW_THROUGH: 3,
}

_DRIBBLE_PHASE_ORDER: dict[DribblePhase, int] = {
    DribblePhase.PUSH_DOWN: 0,
    DribblePhase.BALL_CONTACT: 1,
    DribblePhase.RISE: 2,
    DribblePhase.CATCH: 3,
}


# =============================================================================
# 피드백 열거형
# =============================================================================

@unique
class FeedbackSeverity(str, Enum):
    """
    피드백 심각도.

    폼 평가 시 항목별 피드백 수준을 나타낸다.
    """

    EXCELLENT = "excellent"  # 우수: 이 부분은 유지
    GOOD = "good"            # 양호: 큰 문제 없음
    WARNING = "warning"      # 주의: 개선 필요
    CRITICAL = "critical"    # 심각: 반드시 교정 필요

    def __str__(self) -> str:
        return self.value

    @property
    def priority(self) -> int:
        """우선순위 (1=최우선 ~ 4=참고)."""
        return _SEVERITY_PRIORITY[self]


@unique
class FormGrade(str, Enum):
    """
    폼 평가 등급.

    100점 만점 기준:
        S: 95+ | A: 85+ | B: 75+ | C: 65+ | D: 50+ | F: <50
    """

    S = "S"  # 95+
    A = "A"  # 85+
    B = "B"  # 75+
    C = "C"  # 65+
    D = "D"  # 50+
    F = "F"  # <50

    def __str__(self) -> str:
        return self.value


_SEVERITY_PRIORITY: dict[FeedbackSeverity, int] = {
    FeedbackSeverity.CRITICAL: 1,
    FeedbackSeverity.WARNING: 2,
    FeedbackSeverity.GOOD: 3,
    FeedbackSeverity.EXCELLENT: 4,
}

# --- 등급 임계치 ---
_GRADE_THRESHOLDS: list[tuple[float, FormGrade]] = [
    (95.0, FormGrade.S),
    (85.0, FormGrade.A),
    (75.0, FormGrade.B),
    (65.0, FormGrade.C),
    (50.0, FormGrade.D),
]


def score_to_grade(score: float) -> FormGrade:
    """점수를 등급으로 변환한다.

    Args:
        score: 0~100 범위의 점수.

    Returns:
        FormGrade 열거형.

    >>> score_to_grade(97.5)
    <FormGrade.S: 'S'>
    >>> score_to_grade(42.0)
    <FormGrade.F: 'F'>
    """
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return FormGrade.F


# =============================================================================
# 입력 데이터: 프레임 단위 동작 스냅샷
# =============================================================================

@dataclass(slots=True)
class MotionSnapshot:
    """
    프레임 단위 선수 동작 스냅샷.

    biomechanics(Layer 3) + detection(Layer 1) 출력을 통합한 단일 구조체.
    모든 Tier 1 감지기(shot/dribble/pass/movement/rebound)의 공통 입력.

    joint_angles, joint_speeds 등은 biomechanics 모듈의 FrameAngles,
    JointVelocity 등에서 추출한 스칼라 값으로, 내부 사용에 최적화되어 있다.

    좌표 단위:
        - 위치: cm (biomechanics 기준)
        - 각도: deg
        - 속도: cm/s
        - 각속도: deg/s

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프 (초)
        player_tracking_id: 선수 트래킹 ID
        joint_angles: 관절별 각도 (도, JointType → angle_deg)
        joint_speeds: 관절별 속력 (cm/s, JointType → speed)
        joint_angular_velocities: 관절별 각속도 (deg/s)
        joint_positions: 관절별 3D 위치 (cm, JointType → (x, y, z))
        body_orientation: 몸체 방위 (roll, pitch, yaw) 도
        com_position: 무게중심 (x, y, z) cm
        stability_index: 안정성 지수 (0~100)
        ball_position: 공 위치 (x, y, z) cm — detection 출력
        court_position: 코트 상 정규화 좌표 (0~1)
        hoop_position: 골대 위치 (x, y, z) cm
    """

    frame_index: int = 0
    timestamp: float = 0.0
    player_tracking_id: int = 0

    # === 관절 데이터 (biomechanics/kinematics 출력) ===
    # JointType → 스칼라 값으로 평탄화
    joint_angles: dict[JointType, float] = field(default_factory=dict)
    joint_speeds: dict[JointType, float] = field(default_factory=dict)
    joint_angular_velocities: dict[JointType, float] = field(default_factory=dict)
    joint_positions: dict[JointType, tuple[float, float, float]] = field(
        default_factory=dict,
    )

    # === 몸체 상태 ===
    body_orientation: tuple[float, float, float] | None = None
    com_position: tuple[float, float, float] | None = None
    stability_index: float = 0.0

    # === 외부 참조 (detection 출력) ===
    ball_position: tuple[float, float, float] | None = None
    court_position: tuple[float, float] | None = None
    hoop_position: tuple[float, float, float] | None = None

    def get_angle(self, joint: JointType, default: float = 0.0) -> float:
        """관절 각도 조회 (안전 접근).

        Args:
            joint: 관절 유형.
            default: 없을 때 기본값.

        Returns:
            관절 각도 (도).
        """
        return self.joint_angles.get(joint, default)

    def get_speed(self, joint: JointType, default: float = 0.0) -> float:
        """관절 속력 조회 (안전 접근).

        Args:
            joint: 관절 유형.
            default: 없을 때 기본값.

        Returns:
            관절 속력 (cm/s).
        """
        return self.joint_speeds.get(joint, default)

    def get_position(
        self,
        joint: JointType,
    ) -> tuple[float, float, float] | None:
        """관절 3D 위치 조회.

        Args:
            joint: 관절 유형.

        Returns:
            (x, y, z) cm 또는 None (키포인트 없음).
        """
        return self.joint_positions.get(joint)

    def get_relative_height(
        self,
        joint_a: JointType,
        joint_b: JointType,
    ) -> float | None:
        """두 관절의 y축 상대 높이차 (cm).

        joint_a가 joint_b보다 높으면 양수.

        Args:
            joint_a: 비교 관절 A.
            joint_b: 비교 관절 B (기준).

        Returns:
            높이차 (cm) 또는 None.
        """
        pos_a = self.joint_positions.get(joint_a)
        pos_b = self.joint_positions.get(joint_b)
        if pos_a is None or pos_b is None:
            return None
        # y축: 위로 양수 규약 (biomechanics 좌표계)
        return pos_a[1] - pos_b[1]

    def get_distance_3d(
        self,
        joint_a: JointType,
        joint_b: JointType,
    ) -> float | None:
        """두 관절 간 3D 유클리드 거리 (cm).

        Args:
            joint_a: 관절 A.
            joint_b: 관절 B.

        Returns:
            거리 (cm) 또는 None.
        """
        pos_a = self.joint_positions.get(joint_a)
        pos_b = self.joint_positions.get(joint_b)
        if pos_a is None or pos_b is None:
            return None
        dx = pos_a[0] - pos_b[0]
        dy = pos_a[1] - pos_b[1]
        dz = pos_a[2] - pos_b[2]
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    @property
    def has_upper_body(self) -> bool:
        """상체 관절 (어깨+팔꿈치+손목) 존재 여부."""
        required = {
            JointType.LEFT_SHOULDER, JointType.RIGHT_SHOULDER,
            JointType.LEFT_ELBOW, JointType.RIGHT_ELBOW,
            JointType.LEFT_WRIST, JointType.RIGHT_WRIST,
        }
        return required.issubset(self.joint_positions.keys())

    @property
    def has_lower_body(self) -> bool:
        """하체 관절 (엉덩이+무릎+발목) 존재 여부."""
        required = {
            JointType.LEFT_HIP, JointType.RIGHT_HIP,
            JointType.LEFT_KNEE, JointType.RIGHT_KNEE,
            JointType.LEFT_ANKLE, JointType.RIGHT_ANKLE,
        }
        return required.issubset(self.joint_positions.keys())

    @property
    def has_full_body(self) -> bool:
        """전신 관절 존재 여부."""
        return self.has_upper_body and self.has_lower_body

    def __repr__(self) -> str:
        n_angles = len(self.joint_angles)
        n_positions = len(self.joint_positions)
        return (
            f"MotionSnapshot(frame={self.frame_index}, "
            f"player={self.player_tracking_id}, "
            f"angles={n_angles}, positions={n_positions})"
        )


# =============================================================================
# Tier 1 출력: 동작 감지 후보
# =============================================================================

@dataclass(slots=True)
class DetectionCandidate:
    """
    동작 감지 후보 (Tier 1 출력).

    shot_detector, dribble_detector, pass_detector, movement_detector,
    rebound_detector에서 생성. Tier 2 분류기에 전달.

    evidence에는 감지 근거가 되는 측정값이 포함된다:
        - shot: {"wrist_above_shoulder_m": 0.15, "elbow_angle_deg": 125.0, ...}
        - dribble: {"hand_below_hip_ratio": 0.45, "frequency_hz": 3.2, ...}
        - pass: {"arm_extension_ratio": 0.85, "release_speed_ms": 4.5, ...}
        - movement: {"com_speed_ms": 5.2, "direction_deg": 45.0, ...}
        - rebound: {"jump_height_m": 0.25, "proximity_to_hoop_m": 2.1, ...}

    Attributes:
        action_type: 감지된 동작 유형
        confidence: 감지 신뢰도 (0~1)
        start_frame: 시작 프레임
        end_frame: 종료 프레임
        start_time: 시작 시간 (초)
        end_time: 종료 시간 (초)
        player_tracking_id: 선수 트래킹 ID
        evidence: 감지 근거 측정값
    """

    action_type: ActionType = ActionType.MOVEMENT
    confidence: float = 0.0
    start_frame: int = 0
    end_frame: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    player_tracking_id: int = 0
    evidence: dict[str, float] = field(default_factory=dict)

    @property
    def duration_frames(self) -> int:
        """동작 지속 프레임 수."""
        return max(0, self.end_frame - self.start_frame)

    @property
    def duration_seconds(self) -> float:
        """동작 지속 시간 (초)."""
        return max(0.0, self.end_time - self.start_time)

    @property
    def is_reliable(self) -> bool:
        """신뢰할 수 있는 감지 여부 (0.6 이상)."""
        return self.confidence >= 0.6

    def __repr__(self) -> str:
        return (
            f"DetectionCandidate({self.action_type.value}, "
            f"conf={self.confidence:.2f}, "
            f"frames={self.start_frame}-{self.end_frame})"
        )


# =============================================================================
# Tier 3 출력: 위상 분석
# =============================================================================

@dataclass(slots=True)
class PhaseSegment:
    """
    동작 위상의 단일 세그먼트.

    슈팅 또는 드리블 한 사이클 내 하나의 위상 구간.
    key_metrics에는 해당 위상에서 측정된 핵심 지표가 포함된다.

    Attributes:
        phase_name: 위상 이름 (ShotPhase/DribblePhase의 value)
        start_frame: 시작 프레임
        end_frame: 종료 프레임
        duration_frames: 지속 프레임 수
        key_metrics: 위상별 핵심 지표
        quality: 품질 평가 (0~1, 1=완벽)
    """

    phase_name: str = ""
    start_frame: int = 0
    end_frame: int = 0
    duration_frames: int = 0
    key_metrics: dict[str, float] = field(default_factory=dict)
    quality: float = 0.0

    @property
    def is_valid(self) -> bool:
        """유효한 위상 여부 (최소 1프레임)."""
        return self.duration_frames >= 1

    def __repr__(self) -> str:
        return (
            f"PhaseSegment({self.phase_name}, "
            f"frames={self.start_frame}-{self.end_frame}, "
            f"q={self.quality:.2f})"
        )


@dataclass(slots=True)
class PhaseResult:
    """
    동작 위상 분석 종합 결과 (Tier 3 출력).

    하나의 동작(슈팅/드리블)에 대한 전체 위상 분석 결과.
    폼 평가(Tier 4)의 입력으로 사용된다.

    Attributes:
        action_type: 동작 유형 (SHOOTING 또는 DRIBBLING)
        player_tracking_id: 선수 트래킹 ID
        phases: 위상 세그먼트 목록 (시간순)
        total_duration_frames: 전체 동작 지속 프레임 수
        kinetic_chain_score: 키네틱 체인 순서 정확도 (0~1)
        transition_smoothness: 위상 전환 부드러움 (0~1)
        start_frame: 전체 동작 시작 프레임
        end_frame: 전체 동작 종료 프레임
    """

    action_type: ActionType = ActionType.SHOOTING
    player_tracking_id: int = 0
    phases: list[PhaseSegment] = field(default_factory=list)
    total_duration_frames: int = 0
    kinetic_chain_score: float = 0.0
    transition_smoothness: float = 0.0
    start_frame: int = 0
    end_frame: int = 0

    @property
    def phase_count(self) -> int:
        """위상 수."""
        return len(self.phases)

    @property
    def is_complete(self) -> bool:
        """모든 위상이 존재하는지 여부 (4단계 완성)."""
        return self.phase_count >= 4

    def get_phase(self, phase_name: str) -> PhaseSegment | None:
        """이름으로 위상 검색.

        Args:
            phase_name: 위상 이름 (예: "release").

        Returns:
            PhaseSegment 또는 None.
        """
        for phase in self.phases:
            if phase.phase_name == phase_name:
                return phase
        return None

    @property
    def average_quality(self) -> float:
        """전체 위상 평균 품질 (0~1)."""
        if not self.phases:
            return 0.0
        return sum(p.quality for p in self.phases) / len(self.phases)

    def __repr__(self) -> str:
        return (
            f"PhaseResult({self.action_type.value}, "
            f"phases={self.phase_count}, "
            f"chain={self.kinetic_chain_score:.2f})"
        )


# =============================================================================
# Tier 4 출력: 피드백 및 폼 평가
# =============================================================================

@dataclass(slots=True)
class FeedbackItem:
    """
    개별 피드백 항목.

    폼 평가에서 생성되는 세부 피드백.
    각 평가 카테고리별 최소 10개 이상의 피드백이 생성된다.

    Attributes:
        category: 카테고리 (예: "elbow_alignment", "release_mechanics")
        severity: 심각도
        message_ko: 한글 피드백 메시지
        current_value: 현재 측정값
        optimal_value: 최적 기준값
        improvement_priority: 개선 우선순위 (1=최우선 ~ 5=참고)
    """

    category: str = ""
    severity: FeedbackSeverity = FeedbackSeverity.GOOD
    message_ko: str = ""
    current_value: float = 0.0
    optimal_value: float = 0.0
    improvement_priority: int = 3

    @property
    def deviation(self) -> float:
        """기준값 대비 편차 (절대값)."""
        return abs(self.current_value - self.optimal_value)

    @property
    def deviation_ratio(self) -> float:
        """기준값 대비 편차 비율 (0~∞)."""
        if self.optimal_value == 0.0:
            return 0.0
        return abs(self.current_value - self.optimal_value) / abs(self.optimal_value)

    def __repr__(self) -> str:
        return (
            f"FeedbackItem({self.category}, "
            f"{self.severity.value}, "
            f"p={self.improvement_priority})"
        )


@dataclass(slots=True)
class FormScore:
    """
    단일 폼 평가 카테고리 점수.

    슈팅 8카테고리, 드리블 8카테고리 각각에 대한 점수.
    sub_scores에는 카테고리 내 세부 항목 점수가 포함된다.

    Attributes:
        category: 카테고리 명 (예: "stance_and_balance")
        max_score: 배점 (예: 15.0)
        score: 획득 점수
        sub_scores: 세부 항목 점수
        feedback_items: 관련 피드백 목록
    """

    category: str = ""
    max_score: float = 0.0
    score: float = 0.0
    sub_scores: dict[str, float] = field(default_factory=dict)
    feedback_items: list[FeedbackItem] = field(default_factory=list)

    @property
    def percentage(self) -> float:
        """달성률 (0~100)."""
        if self.max_score <= 0.0:
            return 0.0
        return min(100.0, (self.score / self.max_score) * 100.0)

    @property
    def loss(self) -> float:
        """감점량."""
        return max(0.0, self.max_score - self.score)

    def __repr__(self) -> str:
        return (
            f"FormScore({self.category}, "
            f"{self.score:.1f}/{self.max_score:.1f})"
        )


@dataclass(slots=True)
class FormEvaluation:
    """
    폼 평가 종합 결과 (Tier 4 출력).

    슈팅 또는 드리블 동작에 대한 전체 폼 평가 결과.
    shared/dto/motion_dto.py의 ShootingMotion.shot_quality 등에 반영된다.

    Attributes:
        action_type: 동작 유형 (SHOOTING 또는 DRIBBLING)
        player_tracking_id: 선수 트래킹 ID
        raw_score: 원점수 (0~100)
        category_scores: 카테고리별 점수 목록
        feedback_items: 전체 피드백 목록 (최소 10개)
        adjustment_factor: 연령/실력 조정 계수 (0.8~1.3)
        adjusted_score: 조정 후 점수 (0~100으로 클램핑)
    """

    action_type: ActionType = ActionType.SHOOTING
    player_tracking_id: int = 0
    raw_score: float = 0.0
    category_scores: list[FormScore] = field(default_factory=list)
    feedback_items: list[FeedbackItem] = field(default_factory=list)
    adjustment_factor: float = 1.0
    adjusted_score: float = 0.0

    @property
    def grade(self) -> FormGrade:
        """점수 기반 등급."""
        return score_to_grade(self.adjusted_score)

    @property
    def critical_feedback_count(self) -> int:
        """심각 수준 피드백 수."""
        return sum(
            1 for f in self.feedback_items
            if f.severity == FeedbackSeverity.CRITICAL
        )

    @property
    def warning_feedback_count(self) -> int:
        """주의 수준 피드백 수."""
        return sum(
            1 for f in self.feedback_items
            if f.severity == FeedbackSeverity.WARNING
        )

    @property
    def top_improvements(self) -> list[FeedbackItem]:
        """최우선 개선 항목 (priority 1~2)."""
        return sorted(
            [f for f in self.feedback_items if f.improvement_priority <= 2],
            key=lambda f: f.improvement_priority,
        )

    def __repr__(self) -> str:
        return (
            f"FormEvaluation({self.action_type.value}, "
            f"score={self.adjusted_score:.1f}, "
            f"grade={self.grade.value}, "
            f"feedback={len(self.feedback_items)})"
        )


# =============================================================================
# Tier 5 출력: 폼 비교
# =============================================================================

@dataclass(slots=True)
class ComparisonResult:
    """
    폼 비교 결과 (Tier 5 출력).

    DTW(Dynamic Time Warping) 기반 폼 유사도 비교.
    이상적 폼, 개인 최고, 프로 선수 대비 비교 가능.

    Attributes:
        action_type: 동작 유형
        player_tracking_id: 선수 트래킹 ID
        similarity_score: 전체 유사도 (0~1, 1=완벽 일치)
        reference_source: 비교 대상 ("ideal_form", "personal_best", "pro_player")
        segment_similarities: 위상별 유사도
        key_differences: 주요 차이점 피드백
        normalized: 신체 비율 정규화 적용 여부
        dtw_distance: DTW 원시 거리값 (디버깅용)
    """

    action_type: ActionType = ActionType.SHOOTING
    player_tracking_id: int = 0
    similarity_score: float = 0.0
    reference_source: str = "ideal_form"
    segment_similarities: dict[str, float] = field(default_factory=dict)
    key_differences: list[FeedbackItem] = field(default_factory=list)
    normalized: bool = True
    dtw_distance: float = 0.0

    @property
    def is_similar(self) -> bool:
        """유사도 기준 충족 여부 (70% 이상)."""
        return self.similarity_score >= 0.7

    @property
    def weakest_phase(self) -> str | None:
        """가장 유사도가 낮은 위상."""
        if not self.segment_similarities:
            return None
        return min(
            self.segment_similarities,
            key=self.segment_similarities.get,  # type: ignore[arg-type]
        )

    @property
    def strongest_phase(self) -> str | None:
        """가장 유사도가 높은 위상."""
        if not self.segment_similarities:
            return None
        return max(
            self.segment_similarities,
            key=self.segment_similarities.get,  # type: ignore[arg-type]
        )

    def __repr__(self) -> str:
        return (
            f"ComparisonResult({self.action_type.value}, "
            f"sim={self.similarity_score:.2f}, "
            f"ref={self.reference_source})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # 위상 열거형
    "ShotPhase",
    "DribblePhase",
    # 피드백 열거형
    "FeedbackSeverity",
    "FormGrade",
    # 유틸리티 함수
    "score_to_grade",
    # 입력 데이터
    "MotionSnapshot",
    # Tier 1 출력
    "DetectionCandidate",
    # Tier 3 출력
    "PhaseSegment",
    "PhaseResult",
    # Tier 4 출력
    "FeedbackItem",
    "FormScore",
    "FormEvaluation",
    # Tier 5 출력
    "ComparisonResult",
]

__version__ = "1.0.0"
