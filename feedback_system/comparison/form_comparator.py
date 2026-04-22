# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/comparison
파일: form_comparator.py
설명: DTW 기반 폼 비교기 (Tier 5)
      - 현재 폼과 레퍼런스 폼(이상적/개인 최고/프로)의 유사도 비교
      - Dynamic Time Warping 알고리즘으로 시계열 정합
      - 신체 비율 정규화 (키/팔 길이 보정)
      - 위상별 세그먼트 유사도 + 주요 차이점 피드백 생성
      - 최소 10개 차이점 피드백 보장

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

학술 근거:
    - Sakoe, H. & Chiba, S. (1978). "Dynamic programming algorithm optimization
      for spoken word recognition." IEEE Trans. ASSP, 26(1), 43-49.
    - Müller, M. (2007). "Information Retrieval for Music and Motion."
      Springer, Chapter 4: DTW.
    - 신체 비율 정규화: de Leva, P. (1996). J. Biomechanics, 29(9), 1223-1230.

참조:
    - motion_analysis/models.py: ComparisonResult, MotionSnapshot, PhaseResult,
                                  PhaseSegment, FeedbackItem, FeedbackSeverity
    - configs/analysis/motion_analysis.yaml: comparison 설정

소비자:
    - feedback_system/: 폼 비교 피드백 반영
    - game_analysis/: 동작 품질 비교 통계
"""

from __future__ import annotations

import logging
import math
from threading import RLock
from typing import Final

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import ActionType

from motion_analysis.models import (
    ComparisonResult,
    FeedbackItem,
    FeedbackSeverity,
    MotionSnapshot,
    PhaseResult,
    PhaseSegment,
)


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 유사도 기준 (configs/analysis/motion_analysis.yaml comparison 참조)
_DEFAULT_SIMILARITY_THRESHOLD: Final[float] = 0.7
_DEFAULT_REFERENCE_SOURCE: Final[str] = "ideal_form"
_DEFAULT_NORMALIZE: Final[bool] = True

# DTW 제약 — Sakoe-Chiba band 비율 (전체 길이 대비)
_DEFAULT_BAND_RATIO: Final[float] = 0.25

# 최소 차이점 피드백 수 (CLAUDE.md #15: 최소 10개)
_MIN_DIFFERENCE_COUNT: Final[int] = 10

# --- 특징 벡터 추출 대상 관절 ---
# 슈팅/드리블 공통 핵심 관절 (상체 6 + 하체 4 = 10관절)
_FEATURE_JOINTS: Final[tuple[JointType, ...]] = (
    JointType.RIGHT_SHOULDER,
    JointType.LEFT_SHOULDER,
    JointType.RIGHT_ELBOW,
    JointType.LEFT_ELBOW,
    JointType.RIGHT_WRIST,
    JointType.LEFT_WRIST,
    JointType.RIGHT_HIP,
    JointType.LEFT_HIP,
    JointType.RIGHT_KNEE,
    JointType.LEFT_KNEE,
)

# 각도 + 속도 = 관절당 2차원 → 10관절 × 2 = 20차원 특징 벡터
_FEATURES_PER_JOINT: Final[int] = 2  # (angle, speed)
_FEATURE_DIM: Final[int] = len(_FEATURE_JOINTS) * _FEATURES_PER_JOINT

# 각도/속도 정규화 범위 (min-max 스케일링용)
_ANGLE_RANGE: Final[tuple[float, float]] = (0.0, 180.0)   # 도
_SPEED_RANGE: Final[tuple[float, float]] = (0.0, 500.0)    # cm/s

# 유사도 → 피드백 심각도 매핑
_SIMILARITY_EXCELLENT: Final[float] = 0.85
_SIMILARITY_GOOD: Final[float] = 0.70
_SIMILARITY_WARNING: Final[float] = 0.50

# 위상 한글 명칭 매핑
_PHASE_NAMES_KO: Final[dict[str, str]] = {
    "preparation": "슈팅 준비",
    "loading": "파워 로딩",
    "release": "릴리스",
    "follow_through": "팔로우 스루",
    "push_down": "푸시 다운",
    "ball_contact": "바닥 접촉",
    "rise": "공 상승",
    "catch": "캐치",
}

# 관절 한글 명칭 매핑
_JOINT_NAMES_KO: Final[dict[JointType, str]] = {
    JointType.RIGHT_SHOULDER: "오른쪽 어깨",
    JointType.LEFT_SHOULDER: "왼쪽 어깨",
    JointType.RIGHT_ELBOW: "오른쪽 팔꿈치",
    JointType.LEFT_ELBOW: "왼쪽 팔꿈치",
    JointType.RIGHT_WRIST: "오른쪽 손목",
    JointType.LEFT_WRIST: "왼쪽 손목",
    JointType.RIGHT_HIP: "오른쪽 엉덩이",
    JointType.LEFT_HIP: "왼쪽 엉덩이",
    JointType.RIGHT_KNEE: "오른쪽 무릎",
    JointType.LEFT_KNEE: "왼쪽 무릎",
}


# =============================================================================
# DTW 폼 비교기
# =============================================================================

class FormComparator:
    """
    DTW 기반 폼 비교기 (Tier 5).

    현재 동작의 관절 시계열(각도+속도)을 레퍼런스와 DTW로 정합하여
    유사도를 산출하고, 위상별 세그먼트 유사도와 주요 차이점을 보고한다.

    비교 흐름:
        1. MotionSnapshot 시퀀스 → 특징 벡터 시계열 추출
        2. 신체 비율 정규화 (선택)
        3. DTW 거리 산출 (Sakoe-Chiba band 제약)
        4. 거리 → 유사도 변환 (0~1, 1=완벽 일치)
        5. 위상별 세그먼트 분할 비교
        6. 주요 차이점 식별 → FeedbackItem 최소 10개 생성

    사용 예:
        >>> comparator = FormComparator()
        >>> result = comparator.compare(
        ...     current_snapshots, reference_snapshots,
        ...     current_phases, reference_phases,
        ...     action_type=ActionType.SHOOTING,
        ... )
        >>> print(result.similarity_score, result.segment_similarities)

    스레드 안전: RLock 기반.
    """

    __slots__ = (
        "_similarity_threshold",
        "_reference_source",
        "_normalize",
        "_band_ratio",
        "_lock",
    )

    def __init__(
        self,
        similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
        reference_source: str = _DEFAULT_REFERENCE_SOURCE,
        normalize: bool = _DEFAULT_NORMALIZE,
        band_ratio: float = _DEFAULT_BAND_RATIO,
    ) -> None:
        """FormComparator 초기화.

        Args:
            similarity_threshold: 유사도 기준 (0~1).
            reference_source: 비교 대상 ("ideal_form"/"personal_best"/"pro_player").
            normalize: 신체 비율 정규화 적용 여부.
            band_ratio: Sakoe-Chiba band 비율 (0~1, 전체 길이 대비).
        """
        self._similarity_threshold = max(0.0, min(1.0, similarity_threshold))
        self._reference_source = reference_source
        self._normalize = normalize
        self._band_ratio = max(0.05, min(1.0, band_ratio))
        self._lock = RLock()

    @classmethod
    def from_yaml(cls, config: dict) -> FormComparator:
        """YAML 설정에서 생성.

        Args:
            config: motion_analysis.yaml의 comparison 섹션 딕셔너리.

        Returns:
            FormComparator 인스턴스.
        """
        comparison = config.get("comparison", config)

        threshold = float(comparison.get(
            "similarity_threshold", _DEFAULT_SIMILARITY_THRESHOLD,
        ))
        ref_source = str(comparison.get(
            "reference_source", _DEFAULT_REFERENCE_SOURCE,
        ))
        normalize = bool(comparison.get(
            "normalize_body_proportions", _DEFAULT_NORMALIZE,
        ))
        band = float(comparison.get("band_ratio", _DEFAULT_BAND_RATIO))

        return cls(
            similarity_threshold=threshold,
            reference_source=ref_source,
            normalize=normalize,
            band_ratio=band,
        )

    # -------------------------------------------------------------------------
    # 핵심 비교 로직
    # -------------------------------------------------------------------------

    def compare(
        self,
        current_snapshots: list[MotionSnapshot],
        reference_snapshots: list[MotionSnapshot],
        current_phases: PhaseResult | None = None,
        reference_phases: PhaseResult | None = None,
        action_type: ActionType = ActionType.SHOOTING,
        player_tracking_id: int = 0,
        reference_source: str | None = None,
    ) -> ComparisonResult:
        """두 폼의 유사도를 DTW로 비교한다.

        Args:
            current_snapshots: 현재 동작 MotionSnapshot 시퀀스.
            reference_snapshots: 레퍼런스 MotionSnapshot 시퀀스.
            current_phases: 현재 동작 위상 결과 (위상별 비교 시 필요).
            reference_phases: 레퍼런스 위상 결과.
            action_type: 동작 유형.
            player_tracking_id: 선수 트래킹 ID.
            reference_source: 비교 대상 (None이면 초기값 사용).

        Returns:
            ComparisonResult (유사도 0~1, 위상별 유사도, 차이점 피드백).
        """
        with self._lock:
            return self._compare_impl(
                current_snapshots,
                reference_snapshots,
                current_phases,
                reference_phases,
                action_type,
                player_tracking_id,
                reference_source or self._reference_source,
            )

    def _compare_impl(
        self,
        current_snapshots: list[MotionSnapshot],
        reference_snapshots: list[MotionSnapshot],
        current_phases: PhaseResult | None,
        reference_phases: PhaseResult | None,
        action_type: ActionType,
        player_tracking_id: int,
        reference_source: str,
    ) -> ComparisonResult:
        """비교 구현."""
        # 빈 시퀀스 방어
        if len(current_snapshots) < 2 or len(reference_snapshots) < 2:
            logger.warning(
                "비교 불가: 현재 %d, 레퍼런스 %d 프레임 (최소 2 필요)",
                len(current_snapshots),
                len(reference_snapshots),
            )
            return ComparisonResult(
                action_type=action_type,
                player_tracking_id=player_tracking_id,
                similarity_score=0.0,
                reference_source=reference_source,
                normalized=self._normalize,
                dtw_distance=float("inf"),
            )

        # 1. 특징 벡터 추출
        current_features = self._extract_features(current_snapshots)
        reference_features = self._extract_features(reference_snapshots)

        # 2. 신체 비율 정규화 (위치 기반 보정)
        if self._normalize:
            current_features = self._normalize_features(
                current_features, current_snapshots,
            )
            reference_features = self._normalize_features(
                reference_features, reference_snapshots,
            )

        # 3. DTW 전체 유사도
        dtw_dist = self._compute_dtw(current_features, reference_features)
        overall_similarity = self._distance_to_similarity(
            dtw_dist, len(current_features), len(reference_features),
        )

        # 4. 위상별 세그먼트 유사도
        segment_sims: dict[str, float] = {}
        if current_phases is not None and reference_phases is not None:
            segment_sims = self._compare_phases(
                current_snapshots,
                reference_snapshots,
                current_phases,
                reference_phases,
            )

        # 5. 주요 차이점 식별
        key_diffs = self._identify_differences(
            current_snapshots,
            reference_snapshots,
            current_features,
            reference_features,
            current_phases,
            action_type,
        )

        return ComparisonResult(
            action_type=action_type,
            player_tracking_id=player_tracking_id,
            similarity_score=overall_similarity,
            reference_source=reference_source,
            segment_similarities=segment_sims,
            key_differences=key_diffs,
            normalized=self._normalize,
            dtw_distance=dtw_dist,
        )

    # -------------------------------------------------------------------------
    # 특징 벡터 추출
    # -------------------------------------------------------------------------

    @staticmethod
    def _extract_features(
        snapshots: list[MotionSnapshot],
    ) -> list[list[float]]:
        """MotionSnapshot 시퀀스에서 특징 벡터 시계열을 추출한다.

        각 프레임 → 20차원 벡터 (10관절 × [각도, 속도]).
        Min-max 정규화로 0~1 범위로 스케일링.

        Args:
            snapshots: MotionSnapshot 시퀀스.

        Returns:
            list[list[float]] — (T, 20) 형태의 특징 벡터 시계열.
        """
        features: list[list[float]] = []

        for snap in snapshots:
            vec: list[float] = []

            for joint in _FEATURE_JOINTS:
                # 각도 (0~180° → 0~1)
                angle = snap.get_angle(joint, default=90.0)
                angle_norm = max(0.0, min(1.0,
                    (angle - _ANGLE_RANGE[0]) / (_ANGLE_RANGE[1] - _ANGLE_RANGE[0]),
                ))

                # 속도 (0~500 cm/s → 0~1)
                speed = snap.get_speed(joint, default=0.0)
                speed_norm = max(0.0, min(1.0,
                    (speed - _SPEED_RANGE[0]) / (_SPEED_RANGE[1] - _SPEED_RANGE[0]),
                ))

                vec.append(angle_norm)
                vec.append(speed_norm)

            features.append(vec)

        return features

    @staticmethod
    def _normalize_features(
        features: list[list[float]],
        snapshots: list[MotionSnapshot],
    ) -> list[list[float]]:
        """신체 비율 기반 정규화.

        선수의 팔 길이(어깨-팔꿈치-손목 거리)를 기준 비율로 보정하여
        체격 차이에 의한 속도 편차를 완화한다.

        de Leva (1996) 기준: 성인 남성 팔 길이 ≈ 60cm(어깨~손목).
        비율 = 실측 팔 길이 / 기준 팔 길이.
        속도 차원만 보정 (각도는 신체 비율에 무관).

        Args:
            features: 특징 벡터 시계열.
            snapshots: 원본 스냅샷 (팔 길이 추출용).

        Returns:
            보정된 특징 벡터 시계열.
        """
        # 기준 팔 길이 (cm) — de Leva (1996) 성인 남성 평균
        reference_arm_length_cm: float = 60.0

        # 실측 팔 길이 산출: 첫 번째 유효 스냅샷에서 추출
        measured_arm = _measure_arm_length(snapshots)

        if measured_arm <= 0.0:
            # 측정 불가 → 보정 없이 반환
            return features

        scale = reference_arm_length_cm / measured_arm

        # 속도 차원(홀수 인덱스)만 보정
        normalized: list[list[float]] = []
        for vec in features:
            new_vec = list(vec)
            for i in range(1, len(new_vec), 2):  # 인덱스 1, 3, 5, ... = 속도
                new_vec[i] = max(0.0, min(1.0, new_vec[i] * scale))
            normalized.append(new_vec)

        return normalized

    # -------------------------------------------------------------------------
    # DTW 핵심 알고리즘
    # -------------------------------------------------------------------------

    def _compute_dtw(
        self,
        seq_a: list[list[float]],
        seq_b: list[list[float]],
    ) -> float:
        """Sakoe-Chiba band 제약 DTW 거리를 산출한다.

        Sakoe & Chiba (1978) 알고리즘.
        비용 함수: 유클리드 거리 (L2 norm).

        시간 복잡도: O(n × w), w = band_width.
        공간 복잡도: O(n × w) (full matrix 대신 band만 유지 가능하나
                     구현 명확성을 위해 full matrix 사용).

        Args:
            seq_a: 시퀀스 A (T_a, D).
            seq_b: 시퀀스 B (T_b, D).

        Returns:
            DTW 누적 거리 (정규화: 경로 길이로 나눔).
        """
        n = len(seq_a)
        m = len(seq_b)

        if n == 0 or m == 0:
            return float("inf")

        # Sakoe-Chiba band 폭 산출
        band_width = max(1, int(max(n, m) * self._band_ratio))

        # DP 테이블 초기화 (inf로 채움)
        # cost[i][j] = seq_a[i]와 seq_b[j]까지의 최소 누적 비용
        inf = float("inf")
        cost: list[list[float]] = [[inf] * m for _ in range(n)]

        # 시작점
        cost[0][0] = _euclidean_distance(seq_a[0], seq_b[0])

        # 첫 행 초기화 (band 내)
        for j in range(1, min(m, band_width + 1)):
            cost[0][j] = cost[0][j - 1] + _euclidean_distance(seq_a[0], seq_b[j])

        # 첫 열 초기화 (band 내)
        for i in range(1, min(n, band_width + 1)):
            cost[i][0] = cost[i - 1][0] + _euclidean_distance(seq_a[i], seq_b[0])

        # DP 채우기 (band 제약)
        for i in range(1, n):
            j_start = max(1, i - band_width)
            j_end = min(m, i + band_width + 1)

            for j in range(j_start, j_end):
                d = _euclidean_distance(seq_a[i], seq_b[j])

                candidates = [inf, inf, inf]
                if i > 0 and j > 0:
                    candidates[0] = cost[i - 1][j - 1]   # 대각선
                if i > 0:
                    candidates[1] = cost[i - 1][j]        # 수직
                if j > 0:
                    candidates[2] = cost[i][j - 1]         # 수평

                cost[i][j] = d + min(candidates)

        # 정규화: 총 경로 길이로 나눔
        total_dist = cost[n - 1][m - 1]
        path_length = n + m  # 근사 경로 길이

        if path_length == 0:
            return 0.0

        return total_dist / path_length

    @staticmethod
    def _distance_to_similarity(
        dtw_distance: float,
        len_a: int,
        len_b: int,
    ) -> float:
        """DTW 거리를 유사도(0~1)로 변환한다.

        가우시안 커널 기반 변환:
            similarity = exp(-dtw_distance² / (2 × σ²))
            σ = 0.5 (경험적 파라미터)

        Args:
            dtw_distance: DTW 정규화 거리.
            len_a: 시퀀스 A 길이.
            len_b: 시퀀스 B 길이.

        Returns:
            유사도 (0~1, 1=완벽 일치).
        """
        if dtw_distance == float("inf") or dtw_distance < 0:
            return 0.0

        # σ: 정규화된 거리 기준 스케일 파라미터
        # 20차원 특징 벡터에서 정규화 거리 0.5 → 유사도 ~0.60
        sigma = 0.5
        similarity = math.exp(-(dtw_distance ** 2) / (2.0 * sigma * sigma))

        return max(0.0, min(1.0, similarity))

    # -------------------------------------------------------------------------
    # 위상별 비교
    # -------------------------------------------------------------------------

    def _compare_phases(
        self,
        current_snapshots: list[MotionSnapshot],
        reference_snapshots: list[MotionSnapshot],
        current_phases: PhaseResult,
        reference_phases: PhaseResult,
    ) -> dict[str, float]:
        """위상별 세그먼트 유사도를 산출한다.

        현재/레퍼런스의 동일 위상끼리 DTW 비교.

        Args:
            current_snapshots: 현재 동작 스냅샷.
            reference_snapshots: 레퍼런스 스냅샷.
            current_phases: 현재 위상 결과.
            reference_phases: 레퍼런스 위상 결과.

        Returns:
            위상명 → 유사도 (0~1) 딕셔너리.
        """
        segment_sims: dict[str, float] = {}

        for cur_phase in current_phases.phases:
            ref_phase = reference_phases.get_phase(cur_phase.phase_name)
            if ref_phase is None:
                # 레퍼런스에 해당 위상 없음 → 비교 불가
                continue

            # 위상 구간 스냅샷 추출
            cur_segment = _extract_phase_snapshots(
                current_snapshots, cur_phase,
            )
            ref_segment = _extract_phase_snapshots(
                reference_snapshots, ref_phase,
            )

            if len(cur_segment) < 1 or len(ref_segment) < 1:
                segment_sims[cur_phase.phase_name] = 0.0
                continue

            # 특징 추출 + DTW
            cur_feat = self._extract_features(cur_segment)
            ref_feat = self._extract_features(ref_segment)

            dist = self._compute_dtw(cur_feat, ref_feat)
            sim = self._distance_to_similarity(
                dist, len(cur_feat), len(ref_feat),
            )

            segment_sims[cur_phase.phase_name] = round(sim, 4)

        return segment_sims

    # -------------------------------------------------------------------------
    # 차이점 식별 + 피드백 생성
    # -------------------------------------------------------------------------

    def _identify_differences(
        self,
        current_snapshots: list[MotionSnapshot],
        reference_snapshots: list[MotionSnapshot],
        current_features: list[list[float]],
        reference_features: list[list[float]],
        current_phases: PhaseResult | None,
        action_type: ActionType,
    ) -> list[FeedbackItem]:
        """주요 차이점을 식별하고 FeedbackItem으로 변환한다.

        관절별 평균 편차 분석 → 가장 편차가 큰 관절/위상 순으로 피드백.
        최소 10개 보장.

        Args:
            current_snapshots: 현재 동작 스냅샷.
            reference_snapshots: 레퍼런스 스냅샷.
            current_features: 현재 특징 벡터.
            reference_features: 레퍼런스 특징 벡터.
            current_phases: 현재 위상 결과 (위상 정보 포함).
            action_type: 동작 유형.

        Returns:
            FeedbackItem 목록 (최소 10개).
        """
        feedback: list[FeedbackItem] = []

        # --- (A) 관절별 평균 편차 분석 ---
        joint_diffs = self._compute_joint_diffs(
            current_snapshots, reference_snapshots,
        )

        # 편차 기준 내림차순 정렬
        sorted_joints = sorted(
            joint_diffs.items(),
            key=lambda x: x[1][0] + x[1][1],  # 각도편차 + 속도편차
            reverse=True,
        )

        priority = 1
        for joint, (angle_diff, speed_diff) in sorted_joints:
            joint_name = _JOINT_NAMES_KO.get(joint, str(joint))

            # 각도 편차 피드백
            if angle_diff > 5.0:  # 5° 이상 차이
                severity = self._diff_to_severity(angle_diff, 5.0, 15.0, 30.0)
                feedback.append(FeedbackItem(
                    category="comparison_angle",
                    severity=severity,
                    message_ko=(
                        f"{joint_name} 각도가 레퍼런스 대비 "
                        f"{angle_diff:.1f}° 차이납니다. "
                        f"레퍼런스 동작을 참고하여 교정하세요."
                    ),
                    current_value=angle_diff,
                    optimal_value=0.0,
                    improvement_priority=min(5, priority),
                ))
                priority += 1

            # 속도 편차 피드백
            if speed_diff > 20.0:  # 20 cm/s 이상 차이
                severity = self._diff_to_severity(speed_diff, 20.0, 50.0, 100.0)
                feedback.append(FeedbackItem(
                    category="comparison_speed",
                    severity=severity,
                    message_ko=(
                        f"{joint_name} 움직임 속도가 레퍼런스 대비 "
                        f"{speed_diff:.0f} cm/s 차이납니다. "
                        f"동작의 속도감을 조절하세요."
                    ),
                    current_value=speed_diff,
                    optimal_value=0.0,
                    improvement_priority=min(5, priority),
                ))
                priority += 1

        # --- (B) 위상별 차이점 ---
        if current_phases is not None:
            phase_feedback = self._generate_phase_feedback(
                current_snapshots, reference_snapshots, current_phases,
            )
            feedback.extend(phase_feedback)

        # --- (C) 전체 동작 리듬 차이 ---
        rhythm_fb = self._generate_rhythm_feedback(
            current_snapshots, reference_snapshots, action_type,
        )
        feedback.extend(rhythm_fb)

        # --- (D) 최소 10개 보장 ---
        if len(feedback) < _MIN_DIFFERENCE_COUNT:
            supplementary = self._generate_supplementary_differences(
                current_snapshots,
                reference_snapshots,
                _MIN_DIFFERENCE_COUNT - len(feedback),
                action_type,
            )
            feedback.extend(supplementary)

        return feedback

    @staticmethod
    def _compute_joint_diffs(
        current: list[MotionSnapshot],
        reference: list[MotionSnapshot],
    ) -> dict[JointType, tuple[float, float]]:
        """관절별 평균 편차를 산출한다.

        현재/레퍼런스의 프레임별 평균을 비교하여
        각도/속도 각각의 절대 편차를 산출.

        Args:
            current: 현재 동작 스냅샷.
            reference: 레퍼런스 스냅샷.

        Returns:
            JointType → (평균 각도 편차°, 평균 속도 편차 cm/s).
        """
        diffs: dict[JointType, tuple[float, float]] = {}

        for joint in _FEATURE_JOINTS:
            # 현재 동작 평균
            cur_angles = [s.get_angle(joint, 90.0) for s in current]
            cur_speeds = [s.get_speed(joint, 0.0) for s in current]
            cur_avg_angle = sum(cur_angles) / len(cur_angles) if cur_angles else 90.0
            cur_avg_speed = sum(cur_speeds) / len(cur_speeds) if cur_speeds else 0.0

            # 레퍼런스 평균
            ref_angles = [s.get_angle(joint, 90.0) for s in reference]
            ref_speeds = [s.get_speed(joint, 0.0) for s in reference]
            ref_avg_angle = sum(ref_angles) / len(ref_angles) if ref_angles else 90.0
            ref_avg_speed = sum(ref_speeds) / len(ref_speeds) if ref_speeds else 0.0

            angle_diff = abs(cur_avg_angle - ref_avg_angle)
            speed_diff = abs(cur_avg_speed - ref_avg_speed)

            diffs[joint] = (angle_diff, speed_diff)

        return diffs

    def _generate_phase_feedback(
        self,
        current_snapshots: list[MotionSnapshot],
        reference_snapshots: list[MotionSnapshot],
        current_phases: PhaseResult,
    ) -> list[FeedbackItem]:
        """위상별 지속 시간 및 타이밍 차이 피드백.

        Args:
            current_snapshots: 현재 동작 스냅샷.
            reference_snapshots: 레퍼런스 스냅샷.
            current_phases: 현재 위상 결과.

        Returns:
            위상 관련 FeedbackItem 목록.
        """
        feedback: list[FeedbackItem] = []

        total_cur = len(current_snapshots)
        total_ref = len(reference_snapshots)

        if total_cur == 0 or total_ref == 0:
            return feedback

        for phase_seg in current_phases.phases:
            phase_ko = _PHASE_NAMES_KO.get(
                phase_seg.phase_name, phase_seg.phase_name,
            )

            # 위상 비율: 현재 동작에서 이 위상이 차지하는 비율
            cur_ratio = phase_seg.duration_frames / total_cur if total_cur > 0 else 0.0

            # 이상적 비율 추정 (레퍼런스 전체 기준 균등 — 4위상)
            # 실제로는 레퍼런스에도 위상 정보가 있어야 정밀하지만,
            # 레퍼런스 위상이 없는 경우를 대비한 대안 로직
            ideal_ratio = 1.0 / max(1, current_phases.phase_count)
            ratio_diff = abs(cur_ratio - ideal_ratio)

            if ratio_diff > 0.15:  # 15%p 이상 차이
                if cur_ratio > ideal_ratio:
                    msg = (
                        f"'{phase_ko}' 위상이 전체 동작의 "
                        f"{cur_ratio * 100:.0f}%로 너무 길어요. "
                        f"레퍼런스 비율({ideal_ratio * 100:.0f}%)에 맞추세요."
                    )
                else:
                    msg = (
                        f"'{phase_ko}' 위상이 전체 동작의 "
                        f"{cur_ratio * 100:.0f}%로 너무 짧아요. "
                        f"충분한 시간을 확보하세요."
                    )

                feedback.append(FeedbackItem(
                    category="comparison_phase_timing",
                    severity=FeedbackSeverity.WARNING,
                    message_ko=msg,
                    current_value=cur_ratio * 100,
                    optimal_value=ideal_ratio * 100,
                    improvement_priority=3,
                ))

        return feedback

    @staticmethod
    def _generate_rhythm_feedback(
        current_snapshots: list[MotionSnapshot],
        reference_snapshots: list[MotionSnapshot],
        action_type: ActionType,
    ) -> list[FeedbackItem]:
        """전체 동작 리듬(속도 변화 패턴) 차이 피드백.

        현재/레퍼런스의 전체 속도 프로파일(손목 속도 시계열)을
        비교하여 리듬 차이를 분석한다.

        Args:
            current_snapshots: 현재 동작 스냅샷.
            reference_snapshots: 레퍼런스 스냅샷.
            action_type: 동작 유형.

        Returns:
            리듬 관련 FeedbackItem 목록.
        """
        feedback: list[FeedbackItem] = []

        if len(current_snapshots) < 3 or len(reference_snapshots) < 3:
            return feedback

        # 손목 속도 피크 비교 (주된 동작 손 — 양손 중 속도 높은 쪽 자동 선택)
        right_speeds = [s.get_speed(JointType.RIGHT_WRIST, 0.0) for s in current_snapshots]
        left_speeds = [s.get_speed(JointType.LEFT_WRIST, 0.0) for s in current_snapshots]
        dominant_wrist = (
            JointType.RIGHT_WRIST
            if max(right_speeds, default=0.0) >= max(left_speeds, default=0.0)
            else JointType.LEFT_WRIST
        )

        cur_speeds = [s.get_speed(dominant_wrist, 0.0) for s in current_snapshots]
        ref_speeds = [s.get_speed(dominant_wrist, 0.0) for s in reference_snapshots]

        cur_peak = max(cur_speeds) if cur_speeds else 0.0
        ref_peak = max(ref_speeds) if ref_speeds else 0.0

        peak_diff = abs(cur_peak - ref_peak)
        if peak_diff > 30.0:  # 30 cm/s 이상 차이
            if cur_peak < ref_peak:
                msg = (
                    f"동작의 최고 속도({cur_peak:.0f} cm/s)가 "
                    f"레퍼런스({ref_peak:.0f} cm/s) 대비 "
                    f"느립니다. 동작의 폭발력을 키우세요."
                )
            else:
                msg = (
                    f"동작의 최고 속도({cur_peak:.0f} cm/s)가 "
                    f"레퍼런스({ref_peak:.0f} cm/s) 대비 "
                    f"빠릅니다. 정확성과 속도의 균형을 맞추세요."
                )

            feedback.append(FeedbackItem(
                category="comparison_rhythm",
                severity=(
                    FeedbackSeverity.WARNING
                    if peak_diff > 50.0
                    else FeedbackSeverity.GOOD
                ),
                message_ko=msg,
                current_value=cur_peak,
                optimal_value=ref_peak,
                improvement_priority=2,
            ))

        # 속도 변동 패턴 (CV 비교)
        cur_mean = sum(cur_speeds) / len(cur_speeds)
        ref_mean = sum(ref_speeds) / len(ref_speeds)

        if cur_mean > 0:
            cur_std = (
                sum((s - cur_mean) ** 2 for s in cur_speeds) / len(cur_speeds)
            ) ** 0.5
            cur_cv = cur_std / cur_mean
        else:
            cur_cv = 0.0

        if ref_mean > 0:
            ref_std = (
                sum((s - ref_mean) ** 2 for s in ref_speeds) / len(ref_speeds)
            ) ** 0.5
            ref_cv = ref_std / ref_mean
        else:
            ref_cv = 0.0

        cv_diff = abs(cur_cv - ref_cv)
        if cv_diff > 0.2:  # CV 차이 0.2 이상
            if cur_cv > ref_cv:
                msg = (
                    "동작 리듬이 레퍼런스보다 불안정합니다. "
                    f"속도 변동계수: 현재 {cur_cv:.2f} vs "
                    f"레퍼런스 {ref_cv:.2f}. "
                    "일관된 리듬으로 동작하세요."
                )
            else:
                msg = (
                    "동작 리듬이 레퍼런스보다 단조롭습니다. "
                    f"속도 변동계수: 현재 {cur_cv:.2f} vs "
                    f"레퍼런스 {ref_cv:.2f}. "
                    "완급 조절을 추가하세요."
                )

            feedback.append(FeedbackItem(
                category="comparison_rhythm",
                severity=FeedbackSeverity.WARNING,
                message_ko=msg,
                current_value=cur_cv,
                optimal_value=ref_cv,
                improvement_priority=3,
            ))

        return feedback

    @staticmethod
    def _generate_supplementary_differences(
        current_snapshots: list[MotionSnapshot],
        reference_snapshots: list[MotionSnapshot],
        count: int,
        action_type: ActionType,
    ) -> list[FeedbackItem]:
        """최소 피드백 수 보장을 위한 보충 피드백 생성.

        기본 분석에서 부족한 피드백 수를 보충한다.
        안정성, 자세 대칭, 무게중심 등 추가 항목을 분석.

        Args:
            current_snapshots: 현재 동작 스냅샷.
            reference_snapshots: 레퍼런스 스냅샷.
            count: 추가 필요 개수.
            action_type: 동작 유형.

        Returns:
            보충 FeedbackItem 목록.
        """
        supplementary: list[FeedbackItem] = []

        if count <= 0:
            return supplementary

        # 1. 안정성 비교
        cur_stabilities = [s.stability_index for s in current_snapshots]
        ref_stabilities = [s.stability_index for s in reference_snapshots]

        cur_avg_stab = (
            sum(cur_stabilities) / len(cur_stabilities)
            if cur_stabilities else 0.0
        )
        ref_avg_stab = (
            sum(ref_stabilities) / len(ref_stabilities)
            if ref_stabilities else 0.0
        )

        stab_diff = abs(cur_avg_stab - ref_avg_stab)
        if stab_diff > 5.0:
            supplementary.append(FeedbackItem(
                category="comparison_stability",
                severity=(
                    FeedbackSeverity.WARNING
                    if cur_avg_stab < ref_avg_stab
                    else FeedbackSeverity.GOOD
                ),
                message_ko=(
                    f"안정성 지수: 현재 {cur_avg_stab:.1f} vs "
                    f"레퍼런스 {ref_avg_stab:.1f}. "
                    + (
                        "하체 안정성을 강화하세요."
                        if cur_avg_stab < ref_avg_stab
                        else "안정성이 우수합니다."
                    )
                ),
                current_value=cur_avg_stab,
                optimal_value=ref_avg_stab,
                improvement_priority=4,
            ))

        # 2. 좌우 대칭성 비교 (어깨 높이 차)
        sym_pairs = [
            (JointType.RIGHT_SHOULDER, JointType.LEFT_SHOULDER, "어깨"),
            (JointType.RIGHT_HIP, JointType.LEFT_HIP, "엉덩이"),
            (JointType.RIGHT_KNEE, JointType.LEFT_KNEE, "무릎"),
        ]

        for r_joint, l_joint, name in sym_pairs:
            if len(supplementary) >= count:
                break

            cur_diffs_y: list[float] = []
            for s in current_snapshots:
                r_pos = s.get_position(r_joint)
                l_pos = s.get_position(l_joint)
                if r_pos is not None and l_pos is not None:
                    cur_diffs_y.append(abs(r_pos[1] - l_pos[1]))

            avg_asym = (
                sum(cur_diffs_y) / len(cur_diffs_y)
                if cur_diffs_y else 0.0
            )

            if avg_asym > 3.0:  # 3cm 이상 비대칭
                supplementary.append(FeedbackItem(
                    category="comparison_symmetry",
                    severity=FeedbackSeverity.WARNING,
                    message_ko=(
                        f"좌우 {name} 높이 차이가 평균 {avg_asym:.1f}cm입니다. "
                        f"좌우 균형을 맞추세요."
                    ),
                    current_value=avg_asym,
                    optimal_value=0.0,
                    improvement_priority=4,
                ))

        # 3. 동작 범위(ROM) 비교
        rom_joints = [
            (JointType.RIGHT_ELBOW, "오른쪽 팔꿈치"),
            (JointType.RIGHT_KNEE, "오른쪽 무릎"),
            (JointType.RIGHT_SHOULDER, "오른쪽 어깨"),
        ]

        for joint, name in rom_joints:
            if len(supplementary) >= count:
                break

            cur_angles = [s.get_angle(joint, 90.0) for s in current_snapshots]
            ref_angles = [s.get_angle(joint, 90.0) for s in reference_snapshots]

            cur_rom = max(cur_angles) - min(cur_angles) if cur_angles else 0.0
            ref_rom = max(ref_angles) - min(ref_angles) if ref_angles else 0.0

            rom_diff = abs(cur_rom - ref_rom)
            if rom_diff > 10.0:  # ROM 차이 10° 이상
                supplementary.append(FeedbackItem(
                    category="comparison_rom",
                    severity=(
                        FeedbackSeverity.WARNING
                        if cur_rom < ref_rom
                        else FeedbackSeverity.GOOD
                    ),
                    message_ko=(
                        f"{name} 동작 범위(ROM): "
                        f"현재 {cur_rom:.0f}° vs 레퍼런스 {ref_rom:.0f}°. "
                        + (
                            "동작 범위를 넓히세요."
                            if cur_rom < ref_rom
                            else "동작 범위가 충분합니다."
                        )
                    ),
                    current_value=cur_rom,
                    optimal_value=ref_rom,
                    improvement_priority=4,
                ))

        # 4. 동작 유형별 추가 피드백
        if len(supplementary) < count:
            if action_type == ActionType.SHOOTING:
                supplementary.append(FeedbackItem(
                    category="comparison_general",
                    severity=FeedbackSeverity.GOOD,
                    message_ko=(
                        "레퍼런스 슈팅 폼과의 비교를 완료했습니다. "
                        "주요 차이점을 우선순위 순서대로 개선하세요."
                    ),
                    current_value=0.0,
                    optimal_value=0.0,
                    improvement_priority=5,
                ))
            elif action_type == ActionType.DRIBBLING:
                supplementary.append(FeedbackItem(
                    category="comparison_general",
                    severity=FeedbackSeverity.GOOD,
                    message_ko=(
                        "레퍼런스 드리블 폼과의 비교를 완료했습니다. "
                        "핵심 차이점을 집중적으로 연습하세요."
                    ),
                    current_value=0.0,
                    optimal_value=0.0,
                    improvement_priority=5,
                ))
            else:
                supplementary.append(FeedbackItem(
                    category="comparison_general",
                    severity=FeedbackSeverity.GOOD,
                    message_ko=(
                        "레퍼런스 동작과의 비교를 완료했습니다. "
                        "차이점을 확인하고 교정 훈련에 반영하세요."
                    ),
                    current_value=0.0,
                    optimal_value=0.0,
                    improvement_priority=5,
                ))

        # 5. 나머지 채우기 (전체 정리 피드백)
        while len(supplementary) < count:
            idx = len(supplementary)
            supplementary.append(FeedbackItem(
                category="comparison_summary",
                severity=FeedbackSeverity.GOOD,
                message_ko=(
                    f"추가 비교 항목 #{idx + 1}: "
                    "반복 훈련을 통해 레퍼런스 동작과의 차이를 줄여나가세요."
                ),
                current_value=0.0,
                optimal_value=0.0,
                improvement_priority=5,
            ))

        return supplementary[:count]

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------

    @staticmethod
    def _diff_to_severity(
        diff: float,
        good_threshold: float,
        warning_threshold: float,
        critical_threshold: float,
    ) -> FeedbackSeverity:
        """편차를 심각도로 변환한다.

        Args:
            diff: 편차값.
            good_threshold: GOOD 기준 (이하).
            warning_threshold: WARNING 기준 (이하).
            critical_threshold: CRITICAL 기준 (이상).

        Returns:
            FeedbackSeverity.
        """
        if diff >= critical_threshold:
            return FeedbackSeverity.CRITICAL
        if diff >= warning_threshold:
            return FeedbackSeverity.WARNING
        if diff >= good_threshold:
            return FeedbackSeverity.GOOD
        return FeedbackSeverity.EXCELLENT

    def __repr__(self) -> str:
        return (
            f"FormComparator(threshold={self._similarity_threshold:.2f}, "
            f"ref={self._reference_source}, "
            f"normalize={self._normalize})"
        )


# =============================================================================
# 모듈 수준 유틸리티 함수
# =============================================================================

def _euclidean_distance(vec_a: list[float], vec_b: list[float]) -> float:
    """두 벡터 간 유클리드 거리.

    Args:
        vec_a: 벡터 A.
        vec_b: 벡터 B.

    Returns:
        L2 거리.
    """
    dim = min(len(vec_a), len(vec_b))
    total = 0.0
    for i in range(dim):
        d = vec_a[i] - vec_b[i]
        total += d * d
    return math.sqrt(total)


def _measure_arm_length(snapshots: list[MotionSnapshot]) -> float:
    """스냅샷에서 오른팔 길이를 측정한다.

    어깨→팔꿈치 + 팔꿈치→손목 거리의 평균.

    Args:
        snapshots: MotionSnapshot 시퀀스.

    Returns:
        팔 길이 (cm), 측정 불가 시 0.0.
    """
    measurements: list[float] = []

    for snap in snapshots:
        shoulder = snap.get_position(JointType.RIGHT_SHOULDER)
        elbow = snap.get_position(JointType.RIGHT_ELBOW)
        wrist = snap.get_position(JointType.RIGHT_WRIST)

        if shoulder is None or elbow is None or wrist is None:
            continue

        # 어깨→팔꿈치 거리
        upper = math.sqrt(
            (shoulder[0] - elbow[0]) ** 2
            + (shoulder[1] - elbow[1]) ** 2
            + (shoulder[2] - elbow[2]) ** 2
        )
        # 팔꿈치→손목 거리
        lower = math.sqrt(
            (elbow[0] - wrist[0]) ** 2
            + (elbow[1] - wrist[1]) ** 2
            + (elbow[2] - wrist[2]) ** 2
        )

        arm_length = upper + lower
        if arm_length > 0:
            measurements.append(arm_length)

        # 최대 10개 샘플로 충분
        if len(measurements) >= 10:
            break

    if not measurements:
        return 0.0

    return sum(measurements) / len(measurements)


def _extract_phase_snapshots(
    snapshots: list[MotionSnapshot],
    phase: PhaseSegment,
) -> list[MotionSnapshot]:
    """위상 구간에 해당하는 스냅샷을 추출한다.

    Args:
        snapshots: 전체 스냅샷 시퀀스.
        phase: 위상 세그먼트.

    Returns:
        해당 위상 구간의 스냅샷 리스트.
    """
    return [
        s for s in snapshots
        if phase.start_frame <= s.frame_index <= phase.end_frame
    ]


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "FormComparator",
]

__version__ = "1.0.0"
