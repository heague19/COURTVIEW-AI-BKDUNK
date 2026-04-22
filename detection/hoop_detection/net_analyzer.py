# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/hoop_detection
파일: net_analyzer.py
설명: Lucas-Kanade 광학 흐름 기반 네트 움직임 분석기
      - 네트 ROI 추출 (림 하단 영역)
      - Lucas-Kanade sparse optical flow 추적
      - 네트 움직임 패턴 분류 (스위시/림인/림아웃)
      - 프레임 간 상태 관리 (골대별 _NetMotionState)
      - 득점 이벤트 생성 + 쿨다운 관리
      - HSV 기반 네트 영역 마스킹

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0

의존성:
    - shared/constants/hoop_constants.py: 네트 분석 상수, 광학 흐름 파라미터
    - shared/interfaces/detector_interface.py: HoopDetection
    - detection/hoop_detection/hoop_detector.py: ScoringType
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.hoop_constants import (
    NET_ANALYSIS_HISTORY_SIZE,
    NET_COLOR_HSV_LOWER,
    NET_COLOR_HSV_UPPER,
    NET_COOLDOWN_FRAMES,
    NET_MAX_AREA_PX,
    NET_MIN_AREA_PX,
    NET_MIN_FRAMES_FOR_ANALYSIS,
    NET_MOTION_DECAY_FACTOR,
    NET_MOTION_THRESHOLD_PX,
    NET_OPTICAL_FLOW_CRITERIA_EPSILON,
    NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT,
    NET_OPTICAL_FLOW_MAX_LEVEL,
    NET_OPTICAL_FLOW_WIN_SIZE,
    NET_RIM_IN_MAX_DURATION_FRAMES,
    NET_RIM_IN_MIN_DISPLACEMENT_PX,
    NET_RIM_IN_OSCILLATION_THRESHOLD,
    NET_RIM_OUT_MAX_DISPLACEMENT_PX,
    NET_RIM_OUT_UPPER_RATIO,
    NET_SCORE_CONFIDENCE_THRESHOLD,
    NET_SWISH_MAX_DURATION_FRAMES,
    NET_SWISH_MIN_DISPLACEMENT_PX,
    NET_SWISH_VERTICAL_RATIO,
)
from shared.interfaces.detector_interface import HoopDetection
from shared.constants.hoop_constants import ScoringType

# =============================================================================
# 모듈 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 네트 ROI: 림 bbox 하단에서 네트 길이만큼 확장
_NET_ROI_EXTEND_RATIO: Final[float] = 1.5  # 림 높이의 1.5배 아래로

# goodFeaturesToTrack 파라미터
_GFT_MAX_CORNERS: Final[int] = 50
_GFT_QUALITY_LEVEL: Final[float] = 0.01
_GFT_MIN_DISTANCE: Final[int] = 7
_GFT_BLOCK_SIZE: Final[int] = 7

# 방향 전환 최소 변위 (노이즈 필터링)
_DIR_CHANGE_MIN_DISPLACEMENT: Final[float] = 2.0


# =============================================================================
# 설정 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class NetAnalyzerConfig:
    """
    네트 분석기 설정.

    Lucas-Kanade 광학 흐름 기반 네트 움직임 분석 파라미터.
    득점 유형 (스위시/림인/림아웃) 판별 기준.

    Attributes:
        history_size: 분석용 프레임 히스토리 크기
        motion_threshold_px: 움직임 감지 임계값 (픽셀)
        score_confidence_threshold: 득점 판정 최소 신뢰도
        min_net_area_px: 네트 영역 최소 면적 (px²)
        max_net_area_px: 네트 영역 최대 면적 (px²)
        optical_flow_win_size: Lucas-Kanade 윈도우 크기
        optical_flow_max_level: 피라미드 최대 레벨
        optical_flow_max_count: 수렴 최대 반복 횟수
        optical_flow_epsilon: 수렴 엡실론
        swish_vertical_ratio: 스위시 수직 움직임 비율
        swish_min_displacement_px: 스위시 최소 수직 변위 (px)
        swish_max_duration_frames: 스위시 최대 지속 프레임
        rim_in_oscillation_threshold: 림인 진동 횟수 임계값
        rim_in_min_displacement_px: 림인 최소 변위 (px)
        rim_in_max_duration_frames: 림인 최대 지속 프레임
        rim_out_max_displacement_px: 림아웃 최대 변위 (px)
        rim_out_upper_ratio: 림아웃 상단 움직임 비율
        motion_decay_factor: 움직임 감쇠 계수
        min_frames_for_analysis: 분석 최소 프레임 수
        cooldown_frames: 득점 판정 후 쿨다운 프레임
    """

    # 기본 분석 파라미터
    history_size: int = NET_ANALYSIS_HISTORY_SIZE
    motion_threshold_px: float = NET_MOTION_THRESHOLD_PX
    score_confidence_threshold: float = NET_SCORE_CONFIDENCE_THRESHOLD
    min_net_area_px: int = NET_MIN_AREA_PX
    max_net_area_px: int = NET_MAX_AREA_PX

    # Lucas-Kanade 광학 흐름 파라미터
    optical_flow_win_size: tuple[int, int] = NET_OPTICAL_FLOW_WIN_SIZE
    optical_flow_max_level: int = NET_OPTICAL_FLOW_MAX_LEVEL
    optical_flow_max_count: int = NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT
    optical_flow_epsilon: float = NET_OPTICAL_FLOW_CRITERIA_EPSILON

    # 스위시 (Swish) 판정 기준
    swish_vertical_ratio: float = NET_SWISH_VERTICAL_RATIO
    swish_min_displacement_px: float = NET_SWISH_MIN_DISPLACEMENT_PX
    swish_max_duration_frames: int = NET_SWISH_MAX_DURATION_FRAMES

    # 림인 (Rim-In) 판정 기준
    rim_in_oscillation_threshold: float = NET_RIM_IN_OSCILLATION_THRESHOLD
    rim_in_min_displacement_px: float = NET_RIM_IN_MIN_DISPLACEMENT_PX
    rim_in_max_duration_frames: int = NET_RIM_IN_MAX_DURATION_FRAMES

    # 림아웃 (Rim-Out) 판정 기준
    rim_out_max_displacement_px: float = NET_RIM_OUT_MAX_DISPLACEMENT_PX
    rim_out_upper_ratio: float = NET_RIM_OUT_UPPER_RATIO

    # 시간적 분석
    motion_decay_factor: float = NET_MOTION_DECAY_FACTOR
    min_frames_for_analysis: int = NET_MIN_FRAMES_FOR_ANALYSIS
    cooldown_frames: int = NET_COOLDOWN_FRAMES

    def __repr__(self) -> str:
        return (
            f"NetAnalyzerConfig(history={self.history_size}, "
            f"motion_thr={self.motion_threshold_px}px, "
            f"score_conf={self.score_confidence_threshold}, "
            f"cooldown={self.cooldown_frames}f)"
        )


# =============================================================================
# 내부 데이터 클래스 — 파이프라인 단계 간 전달용
# =============================================================================

@dataclass(slots=True)
class _NetMotionState:
    """
    네트 움직임 추적 상태 (내부용).

    Lucas-Kanade 광학 흐름 분석의 프레임 간 상태를 유지.
    net_analyzer 내부에서 골대별로 관리.

    Attributes:
        hoop_side: 골대 방향 ("left" 또는 "right")
        is_active: 움직임 활성 상태 (임계값 초과 중)
        motion_start_frame: 현재 움직임 시작 프레임
        accumulated_vertical: 누적 수직 변위 (px, 양수=하향)
        accumulated_horizontal: 누적 수평 변위 (px)
        direction_changes: 수직 방향 전환 횟수 (진동 카운트)
        peak_displacement: 최대 순간 변위 (px)
        upper_motion_ratio: 상단 영역 움직임 비율 (0.0~1.0)
        frame_count: 현재 움직임 지속 프레임 수
        prev_gray: 이전 프레임 그레이스케일 (광학 흐름 기준점)
        prev_points: 이전 프레임 추적 포인트
        displacement_history: 프레임별 변위 이력 (제한 크기 deque)
        cooldown_remaining: 득점 판정 후 남은 쿨다운 프레임
        total_events: 누적 이벤트 감지 수
    """

    hoop_side: str = "left"
    is_active: bool = False
    motion_start_frame: int = 0
    accumulated_vertical: float = 0.0
    accumulated_horizontal: float = 0.0
    direction_changes: int = 0
    peak_displacement: float = 0.0
    upper_motion_ratio: float = 0.0
    frame_count: int = 0

    # 광학 흐름 상태 (NDArray는 field(default=None)으로 설정)
    prev_gray: NDArray[np.uint8] | None = None
    prev_points: NDArray[np.float32] | None = None

    # 변위 이력 (제한 크기)
    displacement_history: deque[float] = field(
        default_factory=lambda: deque(maxlen=NET_ANALYSIS_HISTORY_SIZE),
    )

    # 쿨다운
    cooldown_remaining: int = 0

    # 통계
    total_events: int = 0

    def reset_motion(self) -> None:
        """현재 움직임 상태 초기화 (쿨다운 진입 시 호출)."""
        self.is_active = False
        self.motion_start_frame = 0
        self.accumulated_vertical = 0.0
        self.accumulated_horizontal = 0.0
        self.direction_changes = 0
        self.peak_displacement = 0.0
        self.upper_motion_ratio = 0.0
        self.frame_count = 0

    def apply_decay(self, factor: float) -> None:
        """누적 변위에 감쇠 적용 (비활성 프레임에서 호출)."""
        self.accumulated_vertical *= factor
        self.accumulated_horizontal *= factor

    @property
    def total_displacement(self) -> float:
        """누적 총 변위 크기 (px)."""
        return (
            self.accumulated_vertical ** 2
            + self.accumulated_horizontal ** 2
        ) ** 0.5

    @property
    def vertical_ratio(self) -> float:
        """수직 움직임 비율 (0.0~1.0). 1.0에 가까울수록 수직 지배적."""
        total = self.total_displacement
        if total <= 0.0:
            return 0.0
        return abs(self.accumulated_vertical) / total

    def __repr__(self) -> str:
        status = "active" if self.is_active else "idle"
        return (
            f"_NetMotionState({self.hoop_side}, {status}, "
            f"vert={self.accumulated_vertical:.1f}px, "
            f"changes={self.direction_changes}, "
            f"frames={self.frame_count})"
        )


@dataclass(slots=True)
class _ScoringEvent:
    """
    득점 판정 결과 (내부용).

    net_analyzer에서 생성하여 상위 파이프라인에 전달.

    Attributes:
        scoring_type: 득점 유형
        confidence: 판정 신뢰도 (0.0~1.0)
        hoop_side: 골대 방향 ("left" / "right")
        frame_index: 판정 시점 프레임
        vertical_displacement: 수직 변위 (px)
        horizontal_displacement: 수평 변위 (px)
        oscillation_count: 진동 횟수
        duration_frames: 움직임 지속 프레임
        camera_id: 카메라 식별자
    """

    scoring_type: ScoringType = ScoringType.UNKNOWN
    confidence: float = 0.0
    hoop_side: str = "left"
    frame_index: int = 0
    vertical_displacement: float = 0.0
    horizontal_displacement: float = 0.0
    oscillation_count: int = 0
    duration_frames: int = 0
    camera_id: str | None = None

    @property
    def is_score(self) -> bool:
        """득점 성공 여부."""
        return self.scoring_type.is_score

    def __repr__(self) -> str:
        return (
            f"_ScoringEvent({self.scoring_type.value}, "
            f"conf={self.confidence:.3f}, side={self.hoop_side}, "
            f"frame={self.frame_index})"
        )


# =============================================================================
# 네트 분석기
# =============================================================================

class NetAnalyzer:
    """
    Lucas-Kanade 광학 흐름 기반 네트 움직임 분석기.

    네트의 움직임 패턴을 분석하여 득점 유형을 판별합니다:
    - 스위시 (Swish): 수직 지배적 + 짧은 지속시간
    - 림인 (Rim-In): 진동 패턴 + 중간 지속시간
    - 림아웃 (Rim-Out): 미약한 움직임 + 상단 편중

    파이프라인:
        1. 림 하단 네트 ROI 추출
        2. HSV 기반 네트 영역 마스킹 (흰색 네트)
        3. goodFeaturesToTrack으로 추적 포인트 생성
        4. Lucas-Kanade optical flow 계산
        5. 움직임 벡터 집계 (수직/수평/변위/진동)
        6. 패턴 분류 → 득점 유형 판정

    사용 예시::

        >>> config = NetAnalyzerConfig()
        >>> analyzer = NetAnalyzer()
        >>> analyzer.initialize(config)
        >>> event = analyzer.analyze(frame, hoop, frame_index=0)
        >>> if event is not None and event.is_score:
        ...     print(f"득점! {event.scoring_type.korean_name}")
    """

    def __init__(self) -> None:
        """네트 분석기 초기화."""
        self._lock = threading.RLock()
        self._config: NetAnalyzerConfig | None = None
        self._is_initialized: bool = False

        # 골대별 상태 관리 (key: hoop_side)
        self._states: dict[str, _NetMotionState] = {}

        # 누적 통계
        self._total_events: int = 0
        self._total_scores: int = 0

        logger.info("NetAnalyzer 인스턴스 생성")

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._is_initialized

    @property
    def total_events(self) -> int:
        """누적 이벤트 수."""
        return self._total_events

    @property
    def total_scores(self) -> int:
        """누적 득점 수."""
        return self._total_scores

    def initialize(self, config: NetAnalyzerConfig) -> None:
        """
        분석기 초기화.

        Args:
            config: 네트 분석기 설정
        """
        with self._lock:
            self._config = config
            self._states.clear()
            self._total_events = 0
            self._total_scores = 0
            self._is_initialized = True
            logger.info("NetAnalyzer 초기화 완료: %s", repr(config))

    def shutdown(self) -> None:
        """분석기 종료 및 리소스 해제."""
        with self._lock:
            self._states.clear()
            self._is_initialized = False
            self._config = None
            logger.info("NetAnalyzer 종료 완료")

    def reset(self) -> None:
        """분석기 상태 초기화 (설정 유지)."""
        with self._lock:
            self._states.clear()
            self._total_events = 0
            self._total_scores = 0
            logger.info("NetAnalyzer 상태 초기화 완료")

    # =========================================================================
    # 핵심 분석 메서드
    # =========================================================================

    def analyze(
        self,
        frame: np.ndarray,
        hoop: HoopDetection,
        frame_index: int = 0,
        camera_id: str | None = None,
    ) -> _ScoringEvent | None:
        """
        단일 프레임에서 네트 움직임 분석.

        Args:
            frame: BGR 이미지 (H, W, 3)
            hoop: 골대 감지 결과 (HoopDetection)
            frame_index: 프레임 인덱스
            camera_id: 카메라 식별자

        Returns:
            _ScoringEvent: 득점 이벤트 (판정 완료 시), None (진행 중/미감지)
        """
        if not self._is_initialized:
            return None

        with self._lock:
            config = self._config
            side = hoop.hoop_side or "unknown"

            # 골대별 상태 가져오기/생성
            state = self._get_or_create_state(side)

            # 쿨다운 중이면 감소만 하고 반환
            if state.cooldown_remaining > 0:
                state.cooldown_remaining -= 1
                return None

            # 1단계: 네트 ROI 추출 (offset은 현재 미사용 — 광학 흐름은 ROI 상대 좌표)
            net_roi, _ = self._extract_net_roi(frame, hoop)
            if net_roi is None:
                return None

            # 2단계: 그레이스케일 변환
            gray = cv2.cvtColor(net_roi, cv2.COLOR_BGR2GRAY)

            # 3단계: 광학 흐름 계산
            displacement = self._compute_optical_flow(gray, state)

            if displacement is None:
                # 첫 프레임 — 추적 포인트 초기화만
                return None

            dx, dy, peak = displacement

            # 4단계: 움직임 상태 업데이트
            event = self._update_motion_state(
                state, dx, dy, peak, frame_index, camera_id, config,
            )

            return event

    def analyze_batch(
        self,
        frame: np.ndarray,
        hoops: list[HoopDetection],
        frame_index: int = 0,
        camera_id: str | None = None,
    ) -> list[_ScoringEvent]:
        """
        단일 프레임에서 모든 골대의 네트 움직임 분석.

        Args:
            frame: BGR 이미지
            hoops: 골대 감지 결과 목록
            frame_index: 프레임 인덱스
            camera_id: 카메라 식별자

        Returns:
            이벤트 목록 (판정 완료된 것만)
        """
        events: list[_ScoringEvent] = []
        for hoop in hoops:
            event = self.analyze(frame, hoop, frame_index, camera_id)
            if event is not None:
                events.append(event)
        return events

    # =========================================================================
    # 내부: 상태 관리
    # =========================================================================

    def _get_or_create_state(self, side: str) -> _NetMotionState:
        """
        골대별 움직임 상태 가져오기 또는 생성.

        Args:
            side: 골대 방향 ("left" / "right")

        Returns:
            _NetMotionState 인스턴스
        """
        if side not in self._states:
            self._states[side] = _NetMotionState(hoop_side=side)
        return self._states[side]

    # =========================================================================
    # 내부: 네트 ROI 추출
    # =========================================================================

    def _extract_net_roi(
        self,
        frame: np.ndarray,
        hoop: HoopDetection,
    ) -> tuple[NDArray[np.uint8] | None, tuple[int, int]]:
        """
        림 하단 네트 영역 ROI 추출.

        림 bbox 하단에서 네트 길이만큼 아래로 확장한 영역을 추출합니다.

        Args:
            frame: BGR 이미지
            hoop: 골대 감지 결과

        Returns:
            (네트 ROI 이미지, (x_offset, y_offset)) 또는 (None, (0, 0))
        """
        h, w = frame.shape[:2]
        bb = hoop.bounding_box

        # 림 bbox 하단에서 네트 영역 계산
        rim_bottom = int(bb.y + bb.height)
        net_height = int(bb.height * _NET_ROI_EXTEND_RATIO)

        # 네트 ROI 좌표
        x1 = max(0, int(bb.x))
        y1 = max(0, rim_bottom)
        x2 = min(w, int(bb.x + bb.width))
        y2 = min(h, rim_bottom + net_height)

        roi_w = x2 - x1
        roi_h = y2 - y1

        if roi_w < 5 or roi_h < 5:
            return None, (0, 0)

        # 면적 검증
        config = self._config
        area = roi_w * roi_h
        if area < config.min_net_area_px or area > config.max_net_area_px:
            return None, (0, 0)

        return frame[y1:y2, x1:x2].copy(), (x1, y1)

    # =========================================================================
    # 내부: 광학 흐름 계산
    # =========================================================================

    def _compute_optical_flow(
        self,
        gray: NDArray[np.uint8],
        state: _NetMotionState,
    ) -> tuple[float, float, float] | None:
        """
        Lucas-Kanade sparse optical flow 계산.

        이전 프레임의 추적 포인트에서 현재 프레임으로의 이동량을 계산합니다.

        Args:
            gray: 현재 프레임 그레이스케일 (네트 ROI)
            state: 네트 움직임 상태

        Returns:
            (평균 dx, 평균 dy, 최대 변위) 또는 None (첫 프레임)
        """
        config = self._config

        if state.prev_gray is None or state.prev_points is None:
            # 첫 프레임 — 추적 포인트 초기화
            state.prev_gray = gray
            state.prev_points = self._detect_feature_points(gray)
            return None

        prev_points = state.prev_points
        if prev_points is None or len(prev_points) == 0:
            # 추적 포인트 없음 → 재초기화
            state.prev_gray = gray
            state.prev_points = self._detect_feature_points(gray)
            return None

        # Lucas-Kanade 광학 흐름 계산
        criteria = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            config.optical_flow_max_count,
            config.optical_flow_epsilon,
        )

        next_points, status, _ = cv2.calcOpticalFlowPyrLK(
            state.prev_gray,
            gray,
            prev_points,
            None,
            winSize=config.optical_flow_win_size,
            maxLevel=config.optical_flow_max_level,
            criteria=criteria,
        )

        if next_points is None or status is None:
            state.prev_gray = gray
            state.prev_points = self._detect_feature_points(gray)
            return None

        # 유효한 포인트만 필터링
        valid = status.flatten() == 1
        if not np.any(valid):
            state.prev_gray = gray
            state.prev_points = self._detect_feature_points(gray)
            return None

        good_prev = prev_points[valid]
        good_next = next_points[valid]

        # 변위 벡터 계산
        displacements = good_next - good_prev  # (N, 1, 2) or (N, 2)
        if displacements.ndim == 3:
            displacements = displacements.reshape(-1, 2)

        # 평균 변위
        mean_dx = float(np.mean(displacements[:, 0]))
        mean_dy = float(np.mean(displacements[:, 1]))

        # 최대 변위 크기
        magnitudes = np.sqrt(
            displacements[:, 0] ** 2 + displacements[:, 1] ** 2,
        )
        peak = float(np.max(magnitudes))

        # 상태 갱신
        state.prev_gray = gray

        # 추적 포인트 주기적 갱신 (drift 방지)
        if len(good_next) < _GFT_MAX_CORNERS // 2:
            state.prev_points = self._detect_feature_points(gray)
        else:
            state.prev_points = good_next.reshape(-1, 1, 2).astype(np.float32)

        return mean_dx, mean_dy, peak

    def _detect_feature_points(
        self,
        gray: NDArray[np.uint8],
    ) -> NDArray[np.float32] | None:
        """
        goodFeaturesToTrack으로 추적 포인트 검출.

        Args:
            gray: 그레이스케일 이미지

        Returns:
            추적 포인트 배열 (N, 1, 2) 또는 None
        """
        points = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=_GFT_MAX_CORNERS,
            qualityLevel=_GFT_QUALITY_LEVEL,
            minDistance=_GFT_MIN_DISTANCE,
            blockSize=_GFT_BLOCK_SIZE,
        )
        return points

    # =========================================================================
    # 내부: 움직임 상태 업데이트 + 패턴 판별
    # =========================================================================

    def _update_motion_state(
        self,
        state: _NetMotionState,
        dx: float,
        dy: float,
        peak: float,
        frame_index: int,
        camera_id: str | None,
        config: NetAnalyzerConfig,
    ) -> _ScoringEvent | None:
        """
        움직임 상태 업데이트 및 패턴 판별.

        Args:
            state: 네트 움직임 상태
            dx: 평균 수평 변위
            dy: 평균 수직 변위 (양수=하향)
            peak: 최대 순간 변위
            frame_index: 프레임 인덱스
            camera_id: 카메라 식별자
            config: 분석기 설정

        Returns:
            _ScoringEvent 또는 None
        """
        magnitude = (dx ** 2 + dy ** 2) ** 0.5

        # 변위 이력 저장
        state.displacement_history.append(magnitude)

        # 움직임 감지 여부
        motion_detected = magnitude >= config.motion_threshold_px

        if motion_detected:
            if not state.is_active:
                # 움직임 시작
                state.is_active = True
                state.motion_start_frame = frame_index
                state.accumulated_vertical = 0.0
                state.accumulated_horizontal = 0.0
                state.direction_changes = 0
                state.peak_displacement = 0.0
                state.frame_count = 0

            # 누적 변위 갱신
            prev_vert = state.accumulated_vertical
            state.accumulated_vertical += dy
            state.accumulated_horizontal += dx
            state.peak_displacement = max(state.peak_displacement, peak)
            state.frame_count += 1

            # 방향 전환 감지 (수직)
            if abs(dy) >= _DIR_CHANGE_MIN_DISPLACEMENT:
                if prev_vert != 0.0 and (
                    (prev_vert > 0 and dy < 0) or
                    (prev_vert < 0 and dy > 0)
                ):
                    state.direction_changes += 1

            # 상단 움직임 비율 계산
            # (네트 ROI 상단 30% 영역에서의 움직임 비중)
            if state.frame_count > 0:
                recent = list(state.displacement_history)
                if len(recent) >= 2:
                    upper_count = sum(
                        1 for d in recent[-state.frame_count:]
                        if d > 0 and d < config.motion_threshold_px * 2
                    )
                    state.upper_motion_ratio = upper_count / max(state.frame_count, 1)

        elif state.is_active:
            # 움직임 종료 → 패턴 판별
            if state.frame_count >= config.min_frames_for_analysis:
                event = self._classify_pattern(state, frame_index, camera_id, config)
                if event is not None:
                    # 이벤트 발생 → 쿨다운 진입
                    state.cooldown_remaining = config.cooldown_frames
                    state.total_events += 1
                    self._total_events += 1
                    if event.is_score:
                        self._total_scores += 1
                    state.reset_motion()
                    return event

            # 최소 프레임 미달 → 노이즈로 판단, 초기화
            state.reset_motion()

        else:
            # 비활성 상태 → 감쇠
            state.apply_decay(config.motion_decay_factor)

        # 최대 지속 프레임 초과 시 강제 판정
        if state.is_active:
            max_duration = max(
                config.swish_max_duration_frames,
                config.rim_in_max_duration_frames,
            )
            if state.frame_count > max_duration * 2:
                # 너무 오래 지속 → 비정상, 초기화
                state.reset_motion()

        return None

    def _classify_pattern(
        self,
        state: _NetMotionState,
        frame_index: int,
        camera_id: str | None,
        config: NetAnalyzerConfig,
    ) -> _ScoringEvent | None:
        """
        네트 움직임 패턴 분류.

        수집된 움직임 데이터로 스위시/림인/림아웃을 판별합니다.

        판별 우선순위:
            1. 스위시: 수직 비율 ≥ 0.8, 변위 ≥ 20px, 지속 ≤ 10f
            2. 림인: 진동 ≥ 3회, 변위 ≥ 15px, 지속 ≤ 20f
            3. 림아웃: 변위 < 10px, 상단 비율 ≥ 0.3

        Args:
            state: 네트 움직임 상태
            frame_index: 프레임 인덱스
            camera_id: 카메라 식별자
            config: 분석기 설정

        Returns:
            _ScoringEvent 또는 None (판별 불가)
        """
        v_ratio = state.vertical_ratio
        total_disp = state.total_displacement
        vert_disp = abs(state.accumulated_vertical)
        oscillations = state.direction_changes
        duration = state.frame_count

        scoring_type = ScoringType.UNKNOWN
        confidence = 0.0

        # === 스위시 판별 ===
        if (
            v_ratio >= config.swish_vertical_ratio
            and vert_disp >= config.swish_min_displacement_px
            and duration <= config.swish_max_duration_frames
        ):
            scoring_type = ScoringType.SWISH
            # 신뢰도: 수직 비율 + 변위 크기 + 짧은 지속시간
            v_score = min(1.0, v_ratio / 1.0)
            d_score = min(1.0, vert_disp / (config.swish_min_displacement_px * 2))
            t_score = max(0.0, 1.0 - duration / config.swish_max_duration_frames)
            confidence = 0.4 * v_score + 0.4 * d_score + 0.2 * t_score

        # === 림인 판별 ===
        elif (
            oscillations >= config.rim_in_oscillation_threshold
            and total_disp >= config.rim_in_min_displacement_px
            and duration <= config.rim_in_max_duration_frames
        ):
            scoring_type = ScoringType.RIM_IN
            # 신뢰도: 진동 횟수 + 변위 + 지속시간
            osc_score = min(1.0, oscillations / (config.rim_in_oscillation_threshold * 2))
            d_score = min(1.0, total_disp / (config.rim_in_min_displacement_px * 2))
            t_score = max(0.0, 1.0 - duration / config.rim_in_max_duration_frames)
            confidence = 0.4 * osc_score + 0.4 * d_score + 0.2 * t_score

        # === 림아웃 판별 ===
        elif (
            total_disp <= config.rim_out_max_displacement_px
            and state.upper_motion_ratio >= config.rim_out_upper_ratio
            and duration >= config.min_frames_for_analysis
        ):
            scoring_type = ScoringType.RIM_OUT
            # 신뢰도: 작은 변위 + 상단 편중
            small_disp_score = max(0.0, 1.0 - total_disp / config.rim_out_max_displacement_px)
            upper_score = min(1.0, state.upper_motion_ratio / 0.5)
            confidence = 0.5 * small_disp_score + 0.5 * upper_score

        else:
            # 판별 불가
            return None

        # 최소 신뢰도 미달 시 무시
        if confidence < config.score_confidence_threshold * 0.5:
            return None

        return _ScoringEvent(
            scoring_type=scoring_type,
            confidence=confidence,
            hoop_side=state.hoop_side,
            frame_index=frame_index,
            vertical_displacement=state.accumulated_vertical,
            horizontal_displacement=state.accumulated_horizontal,
            oscillation_count=oscillations,
            duration_frames=duration,
            camera_id=camera_id,
        )

    # =========================================================================
    # 공개 상태 조회
    # =========================================================================

    def get_state(self, side: str) -> _NetMotionState | None:
        """
        특정 골대의 네트 움직임 상태 조회.

        Args:
            side: 골대 방향 ("left" / "right")

        Returns:
            _NetMotionState 또는 None
        """
        return self._states.get(side)

    def get_all_states(self) -> dict[str, _NetMotionState]:
        """
        모든 골대의 네트 움직임 상태 조회.

        Returns:
            {side: _NetMotionState} 딕셔너리 (방어적 복사)
        """
        return dict(self._states)

    # =========================================================================
    # repr
    # =========================================================================

    def __repr__(self) -> str:
        states_str = ", ".join(
            f"{s}: {'active' if st.is_active else 'idle'}"
            for s, st in self._states.items()
        )
        return (
            f"NetAnalyzer(initialized={self._is_initialized}, "
            f"events={self._total_events}, scores={self._total_scores}, "
            f"states=[{states_str}])"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "NetAnalyzer",
    "NetAnalyzerConfig",
]

__version__: str = "1.0.0"
