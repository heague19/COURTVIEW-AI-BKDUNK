# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/classification
파일: action_classifier.py
설명: 동작 분류기 (Tier 2)
      - Tier 1 감지기(5종)의 DetectionCandidate를 종합하여 최종 동작 분류
      - 11가지 ActionType 중 최적 분류 결정
      - 동시 감지 시 우선순위/신뢰도 기반 충돌 해소
      - ActionClassification DTO 생성

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - shared/dto/motion_dto.py: ActionType, ActionClassification, MotionFeatureVector
    - motion_analysis/models.py: DetectionCandidate, MotionSnapshot
    - configs/analysis/motion_analysis.yaml: classification 설정

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/dto/motion_dto.py: ActionType, ActionClassification, MotionFeatureVector

소비자:
    - motion_analysis/classification/shot_classifier.py: SHOOTING 세부 분류
    - motion_analysis/classification/dribble_classifier.py: DRIBBLING 세부 분류
    - motion_analysis/phase_analysis/: Tier 3 위상 분석
"""

from __future__ import annotations

import logging
from threading import RLock
from typing import Final

from shared.constants.pose_constants import JointType
from shared.dto.motion_dto import (
    ActionClassification,
    ActionType,
    MotionFeatureVector,
)

from motion_analysis.models import DetectionCandidate, MotionSnapshot


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# --- 기본 분류 임계치 ---
_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.6  # 최소 분류 신뢰도

# --- 동작 유형 우선순위 (동시 감지 시 우선 분류) ---
# 구체적 동작이 일반 이동보다 우선
_ACTION_PRIORITY: Final[dict[ActionType, int]] = {
    ActionType.SHOOTING: 1,     # 최우선 (이벤트 핵심)
    ActionType.BLOCKING: 2,     # 슛 블록
    ActionType.REBOUNDING: 3,   # 리바운드
    ActionType.PASSING: 4,      # 패스
    ActionType.DRIBBLING: 5,    # 드리블
    ActionType.DRIVING: 6,      # 드라이브
    ActionType.SCREEN_SET: 7,   # 스크린
    ActionType.SCREEN_USE: 8,
    ActionType.CUTTING: 9,      # 커팅
    ActionType.DEFENSE_STANCE: 10,  # 수비
    ActionType.MOVEMENT: 11,    # 일반 이동 (최하위)
}


# =============================================================================
# 동작 분류기
# =============================================================================

class ActionClassifier:
    """
    동작 분류기 (Tier 2).

    Tier 1 감지기(5종)에서 생성된 DetectionCandidate 목록을 받아
    최종 ActionClassification을 결정한다.

    역할:
        1. 중복/겹침 해소: 동일 프레임 구간에 여러 후보가 감지된 경우
           우선순위 + 신뢰도 기반으로 하나를 선택
        2. 특징 벡터 구성: MotionSnapshot 시퀀스에서 MotionFeatureVector 추출
        3. ActionClassification DTO 생성: game_analysis에서 소비하는 최종 형태

    사용 예:
        >>> classifier = ActionClassifier()
        >>> classifications = classifier.classify(candidates, snapshots)
        >>> for cls in classifications:
        ...     print(cls.action_type, cls.confidence)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_min_confidence", "_lock")

    def __init__(self, min_confidence: float = _DEFAULT_MIN_CONFIDENCE) -> None:
        """ActionClassifier 초기화.

        Args:
            min_confidence: 최소 분류 신뢰도 (이하 폐기).
        """
        self._min_confidence = min_confidence
        self._lock = RLock()

    @classmethod
    def from_yaml(cls, config_dict: dict) -> ActionClassifier:
        """YAML 설정에서 생성.

        Args:
            config_dict: classification 섹션 딕셔너리.

        Returns:
            ActionClassifier 인스턴스.
        """
        return cls(
            min_confidence=float(config_dict.get(
                "min_classification_confidence", _DEFAULT_MIN_CONFIDENCE,
            )),
        )

    # -------------------------------------------------------------------------
    # 핵심 분류 로직
    # -------------------------------------------------------------------------

    def classify(
        self,
        candidates: list[DetectionCandidate],
        snapshots: list[MotionSnapshot],
    ) -> list[ActionClassification]:
        """감지 후보를 최종 동작 분류로 변환한다.

        Args:
            candidates: Tier 1 감지기 출력 (5종 통합).
            snapshots: 해당 구간의 MotionSnapshot 시퀀스.

        Returns:
            최종 ActionClassification 목록 (시간순, 겹침 해소됨).
        """
        with self._lock:
            return self._classify_impl(candidates, snapshots)

    def _classify_impl(
        self,
        candidates: list[DetectionCandidate],
        snapshots: list[MotionSnapshot],
    ) -> list[ActionClassification]:
        """분류 구현."""
        if not candidates:
            return []

        # 1. 신뢰도 필터링
        filtered = [c for c in candidates if c.confidence >= self._min_confidence]
        if not filtered:
            return []

        # 2. 시간순 정렬
        filtered.sort(key=lambda c: c.start_frame)

        # 3. 겹침 해소
        resolved = self._resolve_overlaps(filtered)

        # 4. ActionClassification DTO 생성
        classifications: list[ActionClassification] = []
        for candidate in resolved:
            classification = self._build_classification(candidate, snapshots)
            classifications.append(classification)

        return classifications

    def _resolve_overlaps(
        self,
        candidates: list[DetectionCandidate],
    ) -> list[DetectionCandidate]:
        """겹치는 후보를 해소한다.

        동일 프레임 구간에 여러 감지가 있으면:
            1. 우선순위(ActionType별)로 비교
            2. 동일 우선순위면 신뢰도로 비교
            3. 높은 쪽 유지, 낮은 쪽 폐기

        Args:
            candidates: 시간순 정렬된 후보 목록.

        Returns:
            겹침이 해소된 후보 목록.
        """
        if len(candidates) <= 1:
            return list(candidates)

        result: list[DetectionCandidate] = [candidates[0]]

        for candidate in candidates[1:]:
            prev = result[-1]

            # 겹침 확인
            if self._is_overlapping(prev, candidate):
                # 우선순위 비교
                winner = self._select_winner(prev, candidate)
                result[-1] = winner
            else:
                result.append(candidate)

        return result

    def _is_overlapping(
        self,
        a: DetectionCandidate,
        b: DetectionCandidate,
    ) -> bool:
        """두 후보의 프레임 구간이 겹치는지 확인한다.

        50% 이상 겹치면 충돌로 판단.

        Args:
            a: 후보 A (이전).
            b: 후보 B (이후).

        Returns:
            겹침 여부.
        """
        overlap_start = max(a.start_frame, b.start_frame)
        overlap_end = min(a.end_frame, b.end_frame)
        overlap_frames = max(0, overlap_end - overlap_start)

        if overlap_frames == 0:
            return False

        # 짧은 쪽 기준 50% 이상 겹치면 충돌
        shorter = min(a.duration_frames, b.duration_frames)
        if shorter <= 0:
            return False

        return overlap_frames / shorter >= 0.5

    def _select_winner(
        self,
        a: DetectionCandidate,
        b: DetectionCandidate,
    ) -> DetectionCandidate:
        """두 겹치는 후보 중 승자를 선택한다.

        기준:
            1. 우선순위가 높은(숫자 작은) 동작 유형
            2. 동일 우선순위면 신뢰도가 높은 쪽

        Args:
            a: 후보 A.
            b: 후보 B.

        Returns:
            승자 후보.
        """
        pri_a = _ACTION_PRIORITY.get(a.action_type, 99)
        pri_b = _ACTION_PRIORITY.get(b.action_type, 99)

        if pri_a < pri_b:
            return a
        if pri_b < pri_a:
            return b

        # 동일 우선순위 → 신뢰도
        return a if a.confidence >= b.confidence else b

    def _build_classification(
        self,
        candidate: DetectionCandidate,
        snapshots: list[MotionSnapshot],
    ) -> ActionClassification:
        """DetectionCandidate → ActionClassification 변환.

        특징 벡터(MotionFeatureVector)를 구간 내 스냅샷에서 추출.

        Args:
            candidate: 감지 후보.
            snapshots: 전체 스냅샷.

        Returns:
            ActionClassification DTO.
        """
        # 특징 벡터 추출
        features = self._extract_features(candidate, snapshots)

        return ActionClassification(
            player_tracking_id=candidate.player_tracking_id,
            action_type=candidate.action_type,
            sub_type=None,  # shot_classifier / dribble_classifier에서 세부 분류
            confidence=candidate.confidence,
            start_frame=candidate.start_frame,
            end_frame=candidate.end_frame,
            start_time=candidate.start_time,
            end_time=candidate.end_time,
            features=features,
        )

    def _extract_features(
        self,
        candidate: DetectionCandidate,
        snapshots: list[MotionSnapshot],
    ) -> MotionFeatureVector:
        """구간 내 스냅샷에서 MotionFeatureVector를 추출한다.

        evidence 딕셔너리 + 스냅샷 통계를 기반으로
        5개 카테고리(posture/velocity/acceleration/trajectory/contact)의
        특징을 구성한다.

        Args:
            candidate: 감지 후보.
            snapshots: 전체 스냅샷.

        Returns:
            MotionFeatureVector.
        """
        # 구간 내 스냅샷 필터
        segment_snaps = [
            s for s in snapshots
            if candidate.start_frame <= s.frame_index <= candidate.end_frame
        ]

        posture: dict[str, float] = {}
        velocity: dict[str, float] = {}
        acceleration: dict[str, float] = {}
        trajectory: dict[str, float] = {}
        contact: dict[str, bool] = {}

        if not segment_snaps:
            return MotionFeatureVector(
                posture_features=posture,
                velocity_features=velocity,
                acceleration_features=acceleration,
                trajectory_features=trajectory,
                contact_features=contact,
            )

        # --- 자세 특징: 주요 관절 각도 평균 ---
        angle_joints = [
            JointType.RIGHT_ELBOW, JointType.LEFT_ELBOW,
            JointType.RIGHT_KNEE, JointType.LEFT_KNEE,
            JointType.RIGHT_SHOULDER, JointType.LEFT_SHOULDER,
        ]
        for joint in angle_joints:
            angles = [
                s.get_angle(joint) for s in segment_snaps
                if s.get_angle(joint) > 0
            ]
            if angles:
                posture[f"avg_{joint.name.lower()}_deg"] = sum(angles) / len(angles)

        # 안정성 평균
        stabilities = [s.stability_index for s in segment_snaps if s.stability_index > 0]
        if stabilities:
            posture["avg_stability"] = sum(stabilities) / len(stabilities)

        # --- 속도 특징: 손목/발목 속도 ---
        speed_joints = [
            JointType.RIGHT_WRIST, JointType.LEFT_WRIST,
            JointType.RIGHT_ANKLE, JointType.LEFT_ANKLE,
        ]
        for joint in speed_joints:
            speeds = [
                s.get_speed(joint) for s in segment_snaps
                if s.get_speed(joint) > 0
            ]
            if speeds:
                velocity[f"avg_{joint.name.lower()}_cms"] = sum(speeds) / len(speeds)
                velocity[f"max_{joint.name.lower()}_cms"] = max(speeds)

        # --- 궤적 특징: 이동 방향/거리 ---
        if len(segment_snaps) >= 2:
            first = segment_snaps[0]
            last = segment_snaps[-1]
            for joint in (JointType.RIGHT_HIP, JointType.LEFT_HIP):
                pos_first = first.get_position(joint)
                pos_last = last.get_position(joint)
                if pos_first and pos_last:
                    dx = pos_last[0] - pos_first[0]
                    dz = pos_last[2] - pos_first[2]
                    displacement = (dx * dx + dz * dz) ** 0.5
                    trajectory[f"displacement_{joint.name.lower()}_cm"] = displacement
                    break  # 한쪽만

        trajectory["duration_frames"] = float(candidate.duration_frames)

        # --- evidence 정보 추가 ---
        for key, val in candidate.evidence.items():
            if key.startswith("wrist_") or key.startswith("elbow_"):
                posture[f"evidence_{key}"] = val
            elif key.endswith("_ms") or key.endswith("_cms"):
                velocity[f"evidence_{key}"] = val

        # --- 공 접촉 ---
        has_ball = any(s.ball_position is not None for s in segment_snaps)
        contact["ball_visible"] = has_ball

        return MotionFeatureVector(
            posture_features=posture,
            velocity_features=velocity,
            acceleration_features=acceleration,
            trajectory_features=trajectory,
            contact_features=contact,
        )

    @property
    def min_confidence(self) -> float:
        """최소 분류 신뢰도."""
        return self._min_confidence

    def __repr__(self) -> str:
        return f"ActionClassifier(min_conf={self._min_confidence})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "ActionClassifier",
]

__version__ = "1.0.0"
