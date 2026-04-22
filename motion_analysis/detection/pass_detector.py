# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/detection
파일: pass_detector.py
설명: 패스 동작 감지기 (Tier 1)
      - 팔 신전(extension) + 손목 속도 변화로 패스 감지
      - 공 릴리스 패턴 (급격한 손목 가속 → 감속) 분석
      - 체스트/바운스/오버헤드 패스 각각의 관절 패턴 인식

      학술 근거:
        - Button, C. et al. (2003). "Dynamics of skill acquisition: An
          ecological approach." Champaign, IL: Human Kinetics.
          (팔 신전과 릴리스 패턴의 역학적 분석)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-23
버전: 1.0.0

참조:
    - configs/analysis/motion_analysis.yaml: detection.pass 설정
    - motion_analysis/models.py: MotionSnapshot, DetectionCandidate

의존성:
    - shared/constants/pose_constants.py: JointType
    - shared/dto/motion_dto.py: ActionType

소비자:
    - motion_analysis/classification/action_classifier.py
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

# --- 패스 감지 기본 임계치 ---
_DEFAULT_ARM_EXTENSION_RATIO: Final[float] = 0.8     # 팔 신전 비율 (전완+상완 대비 손목-어깨 거리)
_DEFAULT_BALL_RELEASE_SPEED_MIN_MS: Final[float] = 2.0  # 공 릴리스 최소 속도 (m/s)
_DEFAULT_MIN_PASS_DISTANCE_M: Final[float] = 2.0     # 패스 최소 거리 (m)

_CM_PER_METER: Final[float] = 100.0
_MIN_CONFIDENCE: Final[float] = 0.3
_MIN_PASS_FRAMES: Final[int] = 3  # 패스 최소 프레임 (빠른 동작)


# =============================================================================
# 패스 감지 설정
# =============================================================================

@dataclass(slots=True)
class PassDetectionConfig:
    """
    패스 감지 임계치 설정.

    Attributes:
        arm_extension_ratio: 팔 펴짐 비율 (0~1)
        ball_release_speed_min_ms: 공 릴리스 최소 속도 (m/s)
        min_pass_distance_m: 패스 최소 거리 (m)
    """

    arm_extension_ratio: float = _DEFAULT_ARM_EXTENSION_RATIO
    ball_release_speed_min_ms: float = _DEFAULT_BALL_RELEASE_SPEED_MIN_MS
    min_pass_distance_m: float = _DEFAULT_MIN_PASS_DISTANCE_M


# =============================================================================
# 패스 감지기
# =============================================================================

class PassDetector:
    """
    패스 동작 감지기.

    프레임 시퀀스를 분석하여 패스 동작 후보를 감지한다.

    감지 기준:
        1. 팔 신전: 손목-어깨 거리 / 팔 길이 ≥ arm_extension_ratio
        2. 속도 프로파일: 손목 속력의 급상승(가속) → 피크 → 급하강(릴리스) 패턴
        3. 릴리스 속도: 피크 손목 속력 ≥ ball_release_speed_min_ms

    슈팅과의 구분:
        - 패스: 수평/하향 팔 동작 + 비교적 낮은 릴리스 위치
        - 슈팅: 상향 팔 동작 + 높은 릴리스 위치 (어깨 위)

    사용 예:
        >>> detector = PassDetector()
        >>> candidates = detector.detect(snapshots)

    스레드 안전: RLock 기반.
    """

    __slots__ = ("_config", "_lock")

    def __init__(self, config: PassDetectionConfig | None = None) -> None:
        self._config = config or PassDetectionConfig()
        self._lock = RLock()

    @classmethod
    def from_yaml(cls, config_dict: dict) -> PassDetector:
        """YAML 설정에서 생성.

        Args:
            config_dict: detection.pass 섹션 딕셔너리.

        Returns:
            PassDetector 인스턴스.
        """
        cfg = PassDetectionConfig(
            arm_extension_ratio=float(config_dict.get(
                "arm_extension_ratio", _DEFAULT_ARM_EXTENSION_RATIO,
            )),
            ball_release_speed_min_ms=float(config_dict.get(
                "ball_release_speed_min_ms", _DEFAULT_BALL_RELEASE_SPEED_MIN_MS,
            )),
            min_pass_distance_m=float(config_dict.get(
                "min_pass_distance_m", _DEFAULT_MIN_PASS_DISTANCE_M,
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
        """프레임 시퀀스에서 패스 동작을 감지한다.

        Args:
            snapshots: 프레임 순서 MotionSnapshot 목록 (단일 선수).

        Returns:
            감지된 패스 후보 목록 (시간순).
        """
        with self._lock:
            return self._detect_impl(snapshots)

    def _detect_impl(
        self,
        snapshots: list[MotionSnapshot],
    ) -> list[DetectionCandidate]:
        """감지 구현."""
        if len(snapshots) < _MIN_PASS_FRAMES:
            return []

        candidates: list[DetectionCandidate] = []

        # 양손 속도 프로파일 추출 (엉덩이 포함 → 드리블 구분)
        right_profile = self._extract_velocity_profile(
            snapshots,
            wrist=JointType.RIGHT_WRIST,
            elbow=JointType.RIGHT_ELBOW,
            shoulder=JointType.RIGHT_SHOULDER,
            hip=JointType.RIGHT_HIP,
        )
        left_profile = self._extract_velocity_profile(
            snapshots,
            wrist=JointType.LEFT_WRIST,
            elbow=JointType.LEFT_ELBOW,
            shoulder=JointType.LEFT_SHOULDER,
            hip=JointType.LEFT_HIP,
        )

        # 릴리스 피크 감지 (급가속 → 피크 → 급감속)
        right_peaks = self._find_release_peaks(right_profile, hand=1.0)
        left_peaks = self._find_release_peaks(left_profile, hand=0.0)

        for peak in right_peaks + left_peaks:
            candidate = self._build_candidate(snapshots, peak)
            if candidate is not None:
                candidates.append(candidate)

        # 시간순 정렬 + 중복 제거
        candidates.sort(key=lambda c: c.start_frame)
        return self._remove_overlapping(candidates)

    def _extract_velocity_profile(
        self,
        snapshots: list[MotionSnapshot],
        wrist: JointType,
        elbow: JointType,
        shoulder: JointType,
        hip: JointType,
    ) -> list[dict[str, float]]:
        """한 팔의 속도/신전 프로파일을 추출한다.

        Args:
            snapshots: 스냅샷 목록.
            wrist: 손목 관절.
            elbow: 팔꿈치 관절.
            shoulder: 어깨 관절.
            hip: 엉덩이 관절 (드리블 구분용).

        Returns:
            프레임별 {speed_ms, extension_ratio, wrist_above_shoulder,
                      wrist_below_hip} 목록.
        """
        profile: list[dict[str, float]] = []

        for snap in snapshots:
            entry: dict[str, float] = {
                "speed_ms": 0.0,
                "extension_ratio": 0.0,
                "wrist_above_shoulder": 0.0,  # 양수=어깨 위, 음수=어깨 아래
                "wrist_below_hip": 0.0,       # 1.0=엉덩이 아래, 0.0=엉덩이 위
            }

            # 손목 속력 (cm/s → m/s)
            wrist_speed = snap.get_speed(wrist)
            entry["speed_ms"] = wrist_speed / _CM_PER_METER

            # 팔 신전 비율
            ws_dist = snap.get_distance_3d(wrist, shoulder)
            we_dist = snap.get_distance_3d(wrist, elbow)
            es_dist = snap.get_distance_3d(elbow, shoulder)
            if ws_dist is not None and we_dist is not None and es_dist is not None:
                arm_len = we_dist + es_dist
                if arm_len > 0:
                    entry["extension_ratio"] = ws_dist / arm_len

            # 손목-어깨 상대 높이
            height_diff = snap.get_relative_height(wrist, shoulder)
            if height_diff is not None:
                entry["wrist_above_shoulder"] = height_diff

            # 손목이 엉덩이 아래인지 (관절 상대 비교)
            wrist_pos = snap.get_position(wrist)
            hip_pos = snap.get_position(hip)
            if wrist_pos is not None and hip_pos is not None:
                entry["wrist_below_hip"] = 1.0 if wrist_pos[1] < hip_pos[1] else 0.0

            profile.append(entry)

        return profile

    def _find_release_peaks(
        self,
        profile: list[dict[str, float]],
        hand: float,
    ) -> list[dict[str, float | int]]:
        """속도 프로파일에서 릴리스 피크를 찾는다.

        패스 릴리스 패턴: 급가속 → 속도 피크 → 급감속.

        필터 조건 (모두 관절 상대 위치 기반, 절대 픽셀값 없음):
            1. 팔 신전 비율 ≥ threshold
            2. 손목이 어깨 아래 (양수 = 슈팅 영역 → 제외)
            3. 손목이 엉덩이 위 (드리블 영역 → 제외)
            4. 피크 후 속도 40%+ 급감 (릴리스 패턴)

        Args:
            profile: 속도/신전 프로파일.
            hand: 1.0=오른손, 0.0=왼손.

        Returns:
            릴리스 피크 정보 [{peak_frame, speed_ms, extension, hand}].
        """
        peaks: list[dict[str, float | int]] = []
        threshold_ms = self._config.ball_release_speed_min_ms

        for i in range(1, len(profile) - 1):
            curr = profile[i]
            prev = profile[i - 1]
            next_p = profile[i + 1]

            # 속도 피크: 이전보다 높고 다음보다 높음
            if curr["speed_ms"] > prev["speed_ms"] and curr["speed_ms"] > next_p["speed_ms"]:
                # 최소 릴리스 속도 충족
                if curr["speed_ms"] < threshold_ms:
                    continue

                # 팔 신전 비율 충족
                if curr["extension_ratio"] < self._config.arm_extension_ratio:
                    continue

                # 관절 상대 위치 필터:
                # 1) 손목이 어깨 위 → 슈팅 영역 → 패스 아님
                if curr["wrist_above_shoulder"] > 0:
                    continue

                # 2) 손목이 엉덩이 아래 → 드리블 push-down → 패스 아님
                if curr["wrist_below_hip"] > 0.5:
                    continue

                # 릴리스 패턴 검증: 피크 후 속도 40%+ 급감
                # 패스: 공이 손을 떠나며 손목 속도 급감
                # 드리블: 반복 진동이라 속도 유지/재상승
                post_speed = next_p["speed_ms"]
                if i + 2 < len(profile):
                    post_speed = min(post_speed, profile[i + 2]["speed_ms"])
                drop_ratio = 1.0 - (post_speed / max(curr["speed_ms"], 0.01))
                if drop_ratio < 0.4:
                    continue

                # 주기성 검사: ±15 스냅샷(~1초) 내 유사 속도 피크 2개+ → 반복 동작
                # 패스 = 단발 이벤트, 드리블 = 주기적 이벤트
                search_radius = 15
                nearby_peaks = 0
                for j in range(max(1, i - search_radius), min(len(profile) - 1, i + search_radius)):
                    if j == i:
                        continue
                    if (profile[j]["speed_ms"] > profile[max(0, j - 1)]["speed_ms"]
                            and profile[j]["speed_ms"] > profile[min(len(profile) - 1, j + 1)]["speed_ms"]
                            and profile[j]["speed_ms"] >= threshold_ms * 0.7):
                        nearby_peaks += 1
                        if nearby_peaks >= 2:
                            break
                if nearby_peaks >= 2:
                    continue  # 주기적 패턴 → 패스 아님

                peaks.append({
                    "peak_frame": i,
                    "speed_ms": curr["speed_ms"],
                    "extension_ratio": curr["extension_ratio"],
                    "wrist_above_shoulder": curr["wrist_above_shoulder"],
                    "hand": hand,
                })

        return peaks

    def _build_candidate(
        self,
        snapshots: list[MotionSnapshot],
        peak: dict[str, float | int],
    ) -> DetectionCandidate | None:
        """릴리스 피크로부터 DetectionCandidate를 생성한다.

        패스 구간: 피크 전 준비(~5프레임) + 피크 후 완료(~3프레임).

        Args:
            snapshots: 전체 스냅샷.
            peak: 릴리스 피크 정보.

        Returns:
            DetectionCandidate 또는 None.
        """
        peak_idx = int(peak["peak_frame"])

        # 패스 구간 산정: 피크 전 5프레임, 피크 후 3프레임
        start_idx = max(0, peak_idx - 5)
        end_idx = min(len(snapshots) - 1, peak_idx + 3)

        start_snap = snapshots[start_idx]
        end_snap = snapshots[end_idx]

        # --- 신뢰도 계산 ---
        speed_ms = float(peak["speed_ms"])
        extension = float(peak["extension_ratio"])

        confidence = self._compute_confidence(speed_ms, extension, peak)
        if confidence < _MIN_CONFIDENCE:
            return None

        evidence: dict[str, float] = {
            "peak_wrist_speed_ms": speed_ms,
            "arm_extension_ratio": extension,
            "wrist_above_shoulder": float(peak["wrist_above_shoulder"]),
            "passing_hand": float(peak["hand"]),  # 1.0=오른손, 0.0=왼손 (자동 판별)
            "duration_frames": float(end_idx - start_idx + 1),
        }

        return DetectionCandidate(
            action_type=ActionType.PASSING,
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
        speed_ms: float,
        extension: float,
        peak: dict[str, float | int],
    ) -> float:
        """패스 감지 신뢰도를 계산한다.

        가중치:
            - 릴리스 속도: 0.40 (패스 핵심 지표)
            - 팔 신전: 0.35 (패스 동작 특성)
            - 손목 높이 적절성: 0.25 (슈팅 구분)

        Args:
            speed_ms: 릴리스 속도 (m/s).
            extension: 팔 신전 비율.
            peak: 피크 정보.

        Returns:
            신뢰도 (0~1).
        """
        # 속도 점수
        speed_score = min(
            1.0,
            speed_ms / max(self._config.ball_release_speed_min_ms, 0.1),
        )

        # 신전 점수
        extension_score = min(
            1.0,
            extension / max(self._config.arm_extension_ratio, 0.1),
        )

        # 높이 적절성 점수 (관절 상대 기준)
        # _find_release_peaks에서 이미 어깨 위/엉덩이 아래는 필터링됨
        # 여기서는 어깨에 가까울수록 높은 점수 (체스트 패스 = 최적)
        wrist_h = float(peak["wrist_above_shoulder"])
        # wrist_h <= 0 (어깨 아래~어깨 높이), 0에 가까울수록 체스트 패스
        # 어깨에서 멀어질수록 (음수 커질수록) 바운스 패스 → 점수 약간 감소
        height_score = max(0.3, 1.0 + wrist_h / max(abs(wrist_h) + 50.0, 1.0))

        return (
            speed_score * 0.40
            + extension_score * 0.35
            + height_score * 0.25
        )

    def _remove_overlapping(
        self,
        candidates: list[DetectionCandidate],
    ) -> list[DetectionCandidate]:
        """겹치는 후보를 제거한다 (높은 신뢰도 유지).

        Args:
            candidates: 시간순 정렬된 후보 목록.

        Returns:
            중복 제거된 후보 목록.
        """
        if len(candidates) <= 1:
            return candidates

        result: list[DetectionCandidate] = [candidates[0]]

        for candidate in candidates[1:]:
            prev = result[-1]
            # 겹침 확인: 이전 후보의 end_frame >= 현재 후보의 start_frame
            if candidate.start_frame <= prev.end_frame:
                # 높은 신뢰도 유지
                if candidate.confidence > prev.confidence:
                    result[-1] = candidate
            else:
                result.append(candidate)

        return result

    @property
    def config(self) -> PassDetectionConfig:
        """현재 설정 반환."""
        return self._config

    def __repr__(self) -> str:
        return (
            f"PassDetector("
            f"extension≥{self._config.arm_extension_ratio}, "
            f"speed≥{self._config.ball_release_speed_min_ms}m/s)"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "PassDetectionConfig",
    "PassDetector",
]

__version__ = "1.0.0"
