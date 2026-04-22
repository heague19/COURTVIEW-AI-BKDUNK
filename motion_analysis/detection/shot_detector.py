# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/detection
파일: shot_detector.py
설명: 슈팅 동작 감지기 (Tier 1)
      - 생체역학 데이터에서 슈팅 동작을 감지
      - 손목 위치, 팔꿈치 각도, 릴리스 속도 기반 판별
      - 프레임 시퀀스 분석으로 슈팅 시작/종료 프레임 결정

      학술 근거:
        - Miller, S. & Bartlett, R. (1996). "The Relationship Between Basketball
          Shooting Kinematics, Distance and Playing Position."
          J. Sports Sciences, 14(3), 243-253.
          (슛 릴리스 시 팔꿈치 각도 ~120-170°)
        - Okazaki, V.H.A. & Rodacki, A.L.F. (2012). "Increased distance of
          shooting on basketball jump shot." J. Sports Science & Medicine, 11, 231-237.
          (슬관절 120-140° 준비, 릴리스 속도 ≥3 m/s)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - configs/analysis/motion_analysis.yaml: detection.shot 설정
    - motion_analysis/models.py: MotionSnapshot, DetectionCandidate

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/dto/motion_dto.py: ActionType
    - core_foundation/config/loader.py: ConfigLoader

소비자:
    - motion_analysis/classification/action_classifier.py: 감지 후보 분류
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

# --- 슈팅 감지 기본 임계치 (motion_analysis.yaml 로드 실패 시 폴백) ---
# Miller & Bartlett (1996): 슛 릴리스 시 팔꿈치 ~120-170°
_DEFAULT_WRIST_ABOVE_SHOULDER_M: Final[float] = 0.1    # 손목-어깨 높이차 최소 (m)
_DEFAULT_ELBOW_ANGLE_MIN: Final[float] = 80.0           # 팔꿈치 각도 하한 (도)
_DEFAULT_ELBOW_ANGLE_MAX: Final[float] = 160.0           # 팔꿈치 각도 상한 (도)
_DEFAULT_RELEASE_VELOCITY_MIN: Final[float] = 3.0        # 릴리스 최소 속도 (m/s)
_DEFAULT_MIN_DURATION_FRAMES: Final[int] = 8             # 최소 지속 프레임

# --- 내부 상태 ---
_CM_PER_METER: Final[float] = 100.0  # cm → m 변환용
_MIN_CONFIDENCE_THRESHOLD: Final[float] = 0.3  # 최소 신뢰도 (이하 폐기)
_SMOOTHING_WINDOW: Final[int] = 3  # 스무딩 윈도우 (프레임)


# =============================================================================
# 슈팅 감지 설정
# =============================================================================

@dataclass(slots=True)
class ShotDetectionConfig:
    """
    슈팅 감지 임계치 설정.

    configs/analysis/motion_analysis.yaml의 detection.shot 섹션에서 로드.

    Attributes:
        wrist_above_shoulder_m: 손목이 어깨 위로 올라간 최소 높이 (m)
        elbow_angle_min: 팔꿈치 각도 하한 (도)
        elbow_angle_max: 팔꿈치 각도 상한 (도)
        release_velocity_min_ms: 릴리스 최소 속도 (m/s)
        min_duration_frames: 최소 지속 프레임
    """

    wrist_above_shoulder_m: float = _DEFAULT_WRIST_ABOVE_SHOULDER_M
    elbow_angle_min: float = _DEFAULT_ELBOW_ANGLE_MIN
    elbow_angle_max: float = _DEFAULT_ELBOW_ANGLE_MAX
    release_velocity_min_ms: float = _DEFAULT_RELEASE_VELOCITY_MIN
    min_duration_frames: int = _DEFAULT_MIN_DURATION_FRAMES


# =============================================================================
# 슈팅 감지기
# =============================================================================

class ShotDetector:
    """
    슈팅 동작 감지기.

    프레임 시퀀스(list[MotionSnapshot])를 분석하여 슈팅 동작 후보를 감지한다.

    감지 기준:
        1. 손목 위치: 슈팅 손 손목이 어깨 높이 + threshold 이상
        2. 팔꿈치 각도: elbow_angle_min ~ elbow_angle_max 범위
        3. 릴리스 속도: 손목 속력 ≥ release_velocity_min (m/s)
        4. 지속 시간: 연속 min_duration_frames 이상 조건 충족

    양손 독립 감지: 좌/우 각각 평가 후 높은 신뢰도 채택.

    사용 예:
        >>> detector = ShotDetector()
        >>> candidates = detector.detect(snapshots)
        >>> for c in candidates:
        ...     print(c.action_type, c.confidence)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_config", "_lock")

    def __init__(self, config: ShotDetectionConfig | None = None) -> None:
        """ShotDetector 초기화.

        Args:
            config: 슈팅 감지 설정. None이면 기본값 사용.
        """
        self._config = config or ShotDetectionConfig()
        self._lock = RLock()

    # -------------------------------------------------------------------------
    # 설정 로드
    # -------------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, config_dict: dict) -> ShotDetector:
        """YAML 설정 딕셔너리에서 생성.

        Args:
            config_dict: detection.shot 섹션 딕셔너리.
                예: {"wrist_above_shoulder_threshold": 0.1,
                     "elbow_angle_range": [80, 160], ...}

        Returns:
            ShotDetector 인스턴스.
        """
        elbow_range = config_dict.get("elbow_angle_range", [
            _DEFAULT_ELBOW_ANGLE_MIN, _DEFAULT_ELBOW_ANGLE_MAX,
        ])
        cfg = ShotDetectionConfig(
            wrist_above_shoulder_m=float(config_dict.get(
                "wrist_above_shoulder_threshold",
                _DEFAULT_WRIST_ABOVE_SHOULDER_M,
            )),
            elbow_angle_min=float(elbow_range[0]),
            elbow_angle_max=float(elbow_range[1]),
            release_velocity_min_ms=float(config_dict.get(
                "release_velocity_min_ms",
                _DEFAULT_RELEASE_VELOCITY_MIN,
            )),
            min_duration_frames=int(config_dict.get(
                "min_duration_frames",
                _DEFAULT_MIN_DURATION_FRAMES,
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
        """프레임 시퀀스에서 슈팅 동작을 감지한다.

        Args:
            snapshots: 프레임 순서 MotionSnapshot 목록 (단일 선수).
                       최소 min_duration_frames 이상 필요.

        Returns:
            감지된 슈팅 후보 목록 (시간순).
        """
        with self._lock:
            return self._detect_impl(snapshots)

    def _detect_impl(
        self,
        snapshots: list[MotionSnapshot],
    ) -> list[DetectionCandidate]:
        """감지 구현 (락 내부)."""
        if len(snapshots) < self._config.min_duration_frames:
            return []

        candidates: list[DetectionCandidate] = []

        # 프레임별 슈팅 점수 계산 (좌/우 독립)
        frame_scores = self._compute_frame_scores(snapshots)

        # 연속 구간 추출
        segments = self._extract_segments(frame_scores, snapshots)

        for seg_start, seg_end, seg_scores in segments:
            candidate = self._build_candidate(
                snapshots, seg_start, seg_end, seg_scores,
            )
            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _compute_frame_scores(
        self,
        snapshots: list[MotionSnapshot],
    ) -> list[dict[str, float]]:
        """프레임별 슈팅 조건 점수를 계산한다.

        각 프레임에서 4가지 조건의 충족 정도를 0~1 점수로 평가:
            1. wrist_elevation: 손목 높이 (어깨 기준)
            2. elbow_angle: 팔꿈치 각도 범위 충족도
            3. wrist_velocity: 손목 속력 (릴리스 속도)
            4. arm_extension: 팔 신전 비율

        Returns:
            프레임별 점수 딕셔너리 목록.
        """
        scores: list[dict[str, float]] = []

        for snap in snapshots:
            best_score = self._evaluate_best_arm(snap)
            scores.append(best_score)

        return scores

    def _evaluate_best_arm(
        self,
        snap: MotionSnapshot,
    ) -> dict[str, float]:
        """좌/우 팔 중 슈팅 가능성이 높은 쪽을 평가한다.

        Args:
            snap: 단일 프레임 스냅샷.

        Returns:
            가장 높은 점수의 평가 결과.
        """
        # 오른쪽 팔 평가
        right_score = self._evaluate_arm(
            snap,
            wrist=JointType.RIGHT_WRIST,
            elbow=JointType.RIGHT_ELBOW,
            shoulder=JointType.RIGHT_SHOULDER,
        )

        # 왼쪽 팔 평가
        left_score = self._evaluate_arm(
            snap,
            wrist=JointType.LEFT_WRIST,
            elbow=JointType.LEFT_ELBOW,
            shoulder=JointType.LEFT_SHOULDER,
        )

        # 종합 점수가 높은 쪽 선택
        right_total = sum(right_score.values())
        left_total = sum(left_score.values())

        # 양손 중 점수 높은 쪽을 슈팅핸드로 자동 선택 (왼손잡이 자동 대응)
        if right_total >= left_total:
            right_score["dominant_hand"] = 1.0   # 오른손 슈팅
            right_score["shooting_hand"] = 1.0   # 명시적 태그
            return right_score
        left_score["dominant_hand"] = 0.0        # 왼손 슈팅
        left_score["shooting_hand"] = 0.0        # 명시적 태그
        return left_score

    def _evaluate_arm(
        self,
        snap: MotionSnapshot,
        wrist: JointType,
        elbow: JointType,
        shoulder: JointType,
    ) -> dict[str, float]:
        """한쪽 팔의 슈팅 조건 충족도를 평가한다.

        Args:
            snap: 프레임 스냅샷.
            wrist: 손목 관절 타입.
            elbow: 팔꿈치 관절 타입.
            shoulder: 어깨 관절 타입.

        Returns:
            4가지 조건별 점수 (0~1).
        """
        result: dict[str, float] = {
            "wrist_elevation": 0.0,
            "elbow_angle": 0.0,
            "wrist_velocity": 0.0,
            "arm_extension": 0.0,
        }

        # --- 1) 손목 높이 (어깨 대비) ---
        height_diff = snap.get_relative_height(wrist, shoulder)
        if height_diff is not None:
            # height_diff: cm, threshold: m → cm으로 변환
            threshold_cm = self._config.wrist_above_shoulder_m * _CM_PER_METER
            if height_diff > 0:
                # 어깨 위에 있을수록 높은 점수
                result["wrist_elevation"] = min(
                    1.0,
                    height_diff / max(threshold_cm, 1.0),
                )

        # --- 2) 팔꿈치 각도 ---
        elbow_angle = snap.get_angle(elbow)
        if elbow_angle > 0:
            if self._config.elbow_angle_min <= elbow_angle <= self._config.elbow_angle_max:
                # 범위 내: 중앙에 가까울수록 높은 점수
                mid = (self._config.elbow_angle_min + self._config.elbow_angle_max) / 2.0
                half_range = (self._config.elbow_angle_max - self._config.elbow_angle_min) / 2.0
                deviation = abs(elbow_angle - mid)
                result["elbow_angle"] = max(0.0, 1.0 - deviation / max(half_range, 1.0))
            else:
                # 범위 밖: 경계에서 멀수록 낮은 점수
                if elbow_angle < self._config.elbow_angle_min:
                    dist = self._config.elbow_angle_min - elbow_angle
                else:
                    dist = elbow_angle - self._config.elbow_angle_max
                result["elbow_angle"] = max(0.0, 1.0 - dist / 45.0)

        # --- 3) 손목 속력 (릴리스 속도) ---
        wrist_speed_cms = snap.get_speed(wrist)
        if wrist_speed_cms > 0:
            # cm/s → m/s 변환
            wrist_speed_ms = wrist_speed_cms / _CM_PER_METER
            threshold_ms = self._config.release_velocity_min_ms
            result["wrist_velocity"] = min(1.0, wrist_speed_ms / max(threshold_ms, 0.1))

        # --- 4) 팔 신전 비율 (손목-어깨 거리 / 팔 길이 추정) ---
        wrist_shoulder_dist = snap.get_distance_3d(wrist, shoulder)
        wrist_elbow_dist = snap.get_distance_3d(wrist, elbow)
        elbow_shoulder_dist = snap.get_distance_3d(elbow, shoulder)

        if (
            wrist_shoulder_dist is not None
            and wrist_elbow_dist is not None
            and elbow_shoulder_dist is not None
        ):
            arm_length = wrist_elbow_dist + elbow_shoulder_dist
            if arm_length > 0:
                extension_ratio = wrist_shoulder_dist / arm_length
                # 슈팅 시 팔 신전 비율 0.7~0.95가 일반적
                result["arm_extension"] = min(1.0, max(0.0, extension_ratio))

        return result

    def _extract_segments(
        self,
        frame_scores: list[dict[str, float]],
        snapshots: list[MotionSnapshot],
    ) -> list[tuple[int, int, list[dict[str, float]]]]:
        """연속 조건 충족 구간을 추출한다.

        슈팅 조건을 일정 수준 이상 연속 충족하는 프레임 구간을 찾는다.

        Args:
            frame_scores: 프레임별 점수.
            snapshots: 프레임 스냅샷 목록.

        Returns:
            (시작 인덱스, 종료 인덱스, 구간 점수) 튜플 목록.
        """
        min_frames = self._config.min_duration_frames
        # 슈팅 프레임 판별: wrist_elevation > 0 + elbow_angle > 0 (최소 2개 조건 충족)
        threshold_score = 0.5  # 종합 4조건 중 평균 0.5 이상

        segments: list[tuple[int, int, list[dict[str, float]]]] = []
        seg_start: int | None = None
        seg_scores: list[dict[str, float]] = []

        for i, score in enumerate(frame_scores):
            # 필수 조건: 손목이 어깨 위에 있어야 슈팅 프레임으로 인정
            # 드리블/패스/이동 중에는 손목이 어깨 아래 → 즉시 탈락
            wrist_elev = score.get("wrist_elevation", 0.0)
            if wrist_elev <= 0.0:
                if seg_start is not None and len(seg_scores) >= min_frames:
                    segments.append((seg_start, i - 1, seg_scores))
                seg_start = None
                seg_scores = []
                continue

            # dominant_hand 제외한 4개 조건 평균
            condition_keys = ("wrist_elevation", "elbow_angle", "wrist_velocity", "arm_extension")
            avg = sum(score.get(k, 0.0) for k in condition_keys) / len(condition_keys)

            if avg >= threshold_score:
                if seg_start is None:
                    seg_start = i
                    seg_scores = []
                seg_scores.append(score)
            else:
                if seg_start is not None and len(seg_scores) >= min_frames:
                    segments.append((seg_start, i - 1, seg_scores))
                seg_start = None
                seg_scores = []

        # 마지막 구간
        if seg_start is not None and len(seg_scores) >= min_frames:
            segments.append((seg_start, len(frame_scores) - 1, seg_scores))

        return segments

    def _build_candidate(
        self,
        snapshots: list[MotionSnapshot],
        seg_start: int,
        seg_end: int,
        seg_scores: list[dict[str, float]],
    ) -> DetectionCandidate | None:
        """감지 구간으로부터 DetectionCandidate를 생성한다.

        Args:
            snapshots: 전체 스냅샷 목록.
            seg_start: 구간 시작 인덱스.
            seg_end: 구간 종료 인덱스.
            seg_scores: 구간 내 프레임별 점수.

        Returns:
            DetectionCandidate 또는 None (신뢰도 미달).
        """
        if seg_start >= len(snapshots) or seg_end >= len(snapshots):
            return None

        start_snap = snapshots[seg_start]
        end_snap = snapshots[seg_end]

        # --- 종합 신뢰도 계산 ---
        confidence = self._compute_confidence(seg_scores)
        if confidence < _MIN_CONFIDENCE_THRESHOLD:
            return None

        # --- 감지 근거(evidence) 수집: 구간 내 피크값 ---
        evidence = self._collect_evidence(snapshots, seg_start, seg_end, seg_scores)

        return DetectionCandidate(
            action_type=ActionType.SHOOTING,
            confidence=confidence,
            start_frame=start_snap.frame_index,
            end_frame=end_snap.frame_index,
            start_time=start_snap.timestamp,
            end_time=end_snap.timestamp,
            player_tracking_id=start_snap.player_tracking_id,
            evidence=evidence,
        )

    def _compute_confidence(
        self,
        seg_scores: list[dict[str, float]],
    ) -> float:
        """구간 종합 신뢰도를 계산한다.

        4가지 조건의 가중 평균을 구간 전체에 대해 계산.

        가중치:
            - wrist_elevation: 0.30 (필수 조건)
            - elbow_angle: 0.25 (슈팅 폼 핵심)
            - wrist_velocity: 0.25 (릴리스 감지)
            - arm_extension: 0.20 (보조 지표)

        Args:
            seg_scores: 구간 내 프레임별 점수.

        Returns:
            종합 신뢰도 (0~1).
        """
        if not seg_scores:
            return 0.0

        weights: dict[str, float] = {
            "wrist_elevation": 0.30,
            "elbow_angle": 0.25,
            "wrist_velocity": 0.25,
            "arm_extension": 0.20,
        }

        total_weighted = 0.0
        for score in seg_scores:
            frame_weighted = sum(
                score.get(k, 0.0) * w for k, w in weights.items()
            )
            total_weighted += frame_weighted

        avg_confidence = total_weighted / len(seg_scores)

        # 피크 프레임 보정: 최고 점수 프레임이 0.7 이상이면 +0.1 보너스
        peak_scores = [
            sum(s.get(k, 0.0) * w for k, w in weights.items())
            for s in seg_scores
        ]
        peak_max = max(peak_scores) if peak_scores else 0.0
        if peak_max >= 0.7:
            avg_confidence = min(1.0, avg_confidence + 0.1)

        return min(1.0, max(0.0, avg_confidence))

    def _collect_evidence(
        self,
        snapshots: list[MotionSnapshot],
        seg_start: int,
        seg_end: int,
        seg_scores: list[dict[str, float]],
    ) -> dict[str, float]:
        """감지 구간의 핵심 근거를 수집한다.

        피크 프레임(가장 높은 점수)에서의 실제 측정값을 기록.

        Args:
            snapshots: 전체 스냅샷.
            seg_start: 구간 시작.
            seg_end: 구간 종료.
            seg_scores: 구간 점수.

        Returns:
            감지 근거 딕셔너리.
        """
        evidence: dict[str, float] = {}

        # 피크 프레임 찾기
        peak_idx = 0
        peak_val = 0.0
        for i, score in enumerate(seg_scores):
            total = sum(
                score.get(k, 0.0)
                for k in ("wrist_elevation", "elbow_angle", "wrist_velocity", "arm_extension")
            )
            if total > peak_val:
                peak_val = total
                peak_idx = i

        snap_idx = seg_start + peak_idx
        if snap_idx >= len(snapshots):
            return evidence

        peak_snap = snapshots[snap_idx]

        # 손목-어깨 높이차 (m)
        for wrist, shoulder, label in [
            (JointType.RIGHT_WRIST, JointType.RIGHT_SHOULDER, "R"),
            (JointType.LEFT_WRIST, JointType.LEFT_SHOULDER, "L"),
        ]:
            height_diff = peak_snap.get_relative_height(wrist, shoulder)
            if height_diff is not None and height_diff > 0:
                evidence[f"wrist_above_shoulder_m_{label}"] = height_diff / _CM_PER_METER
                break  # 높은 쪽만

        # 팔꿈치 각도 (도)
        for elbow, label in [
            (JointType.RIGHT_ELBOW, "R"),
            (JointType.LEFT_ELBOW, "L"),
        ]:
            angle = peak_snap.get_angle(elbow)
            if angle > 0:
                evidence[f"elbow_angle_deg_{label}"] = angle

        # 손목 속력 (m/s)
        for wrist, label in [
            (JointType.RIGHT_WRIST, "R"),
            (JointType.LEFT_WRIST, "L"),
        ]:
            speed_cms = peak_snap.get_speed(wrist)
            if speed_cms > 0:
                evidence[f"wrist_speed_ms_{label}"] = speed_cms / _CM_PER_METER

        # 지속 프레임 수
        evidence["duration_frames"] = float(seg_end - seg_start + 1)

        # 구간 평균 점수
        evidence["avg_score"] = peak_val / 4.0 if peak_val > 0 else 0.0

        return evidence

    @property
    def config(self) -> ShotDetectionConfig:
        """현재 설정 반환."""
        return self._config

    def __repr__(self) -> str:
        return (
            f"ShotDetector("
            f"wrist_threshold={self._config.wrist_above_shoulder_m}m, "
            f"elbow=[{self._config.elbow_angle_min}-{self._config.elbow_angle_max}]deg, "
            f"release_vel={self._config.release_velocity_min_ms}m/s)"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "ShotDetectionConfig",
    "ShotDetector",
]

__version__ = "1.0.0"
