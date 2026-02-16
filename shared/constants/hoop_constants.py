# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: hoop_constants.py
설명: 골대(림/백보드/네트) 검출 및 분석 상수 정의

    골대 물리 규격은 court_constants.py에서 관리합니다.
    이 파일은 검출 알고리즘, 색상 필터, 득점 판정,
    네트 분석 등의 파라미터를 정의합니다.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0

참조:
    - court_constants.py: HOOP_HEIGHT_M, HOOP_DIAMETER_M,
      BACKBOARD_WIDTH_M, BACKBOARD_HEIGHT_M 등 물리 규격
    - configs/detection/hoop.yaml: 운영 설정 (YAML)
"""

from typing import Final

__version__: str = "1.0.0"

# =============================================================================
# 골대 검출 기본 파라미터
# =============================================================================
# YOLO 모델 기본 설정
HOOP_DETECTION_CONFIDENCE_THRESHOLD: Final[float] = 0.6
HOOP_DETECTION_IOU_THRESHOLD: Final[float] = 0.5
HOOP_DETECTION_INPUT_SIZE: Final[int] = 640
HOOP_DETECTION_MAX_DETECTIONS: Final[int] = 4  # 양쪽 골대 × 2 (림, 백보드)

# 감지 클래스 ID (커스텀 학습 모델 기준)
HOOP_CLASS_ID_RIM: Final[int] = 0
HOOP_CLASS_ID_BACKBOARD: Final[int] = 1
HOOP_CLASS_ID_NET: Final[int] = 2

# =============================================================================
# 유소년 규격 보조 (court_constants에 없는 검출 전용)
# =============================================================================
# 유소년 백보드 규격 (검출 크기 판별용)
HOOP_YOUTH_BACKBOARD_WIDTH_M: Final[float] = 1.20
HOOP_YOUTH_BACKBOARD_HEIGHT_M: Final[float] = 0.90

# 림 직경 (인치 단위 - 미국 규격 참조용)
HOOP_RIM_DIAMETER_IN: Final[int] = 18

# 네트 길이 (검출 영역 계산용)
HOOP_NET_LENGTH_M: Final[float] = 0.40

# =============================================================================
# Hough Circle 파라미터 (림 원형 감지 - Fallback)
# =============================================================================
HOOP_HOUGH_DP: Final[float] = 1.2         # 역해상도 비율
HOOP_HOUGH_MIN_DIST: Final[int] = 50      # 원 중심 간 최소 거리 (픽셀)
HOOP_HOUGH_PARAM1: Final[int] = 100       # Canny 에지 상한값
HOOP_HOUGH_PARAM2: Final[int] = 30        # 누적기 임계값
HOOP_HOUGH_MIN_RADIUS: Final[int] = 20    # 최소 반지름 (픽셀)
HOOP_HOUGH_MAX_RADIUS: Final[int] = 100   # 최대 반지름 (픽셀)

# =============================================================================
# 림 색상 HSV 범위 (오렌지 림 필터)
# =============================================================================
HOOP_RIM_HSV_LOWER: Final[tuple[int, int, int]] = (5, 100, 100)
HOOP_RIM_HSV_UPPER: Final[tuple[int, int, int]] = (25, 255, 255)

# =============================================================================
# 백보드 검출 파라미터
# =============================================================================
HOOP_BACKBOARD_ASPECT_RATIO_MIN: Final[float] = 1.5  # 백보드 종횡비 하한
HOOP_BACKBOARD_ASPECT_RATIO_MAX: Final[float] = 2.0  # 백보드 종횡비 상한

# =============================================================================
# 득점 판정 파라미터
# =============================================================================
HOOP_SCORING_PASSING_ZONE_RATIO: Final[float] = 0.8   # 림 반경의 80%
HOOP_SCORING_HEIGHT_TOLERANCE_M: Final[float] = 0.3    # 높이 허용 오차 (미터)
HOOP_SCORING_CONFIDENCE_THRESHOLD: Final[float] = 0.85  # 득점 판정 신뢰도 임계값
HOOP_SCORING_MIN_TRAJECTORY_POINTS: Final[int] = 5     # 궤적 판정 최소 포인트

# =============================================================================
# 캐시 및 성능 파라미터
# =============================================================================
HOOP_CACHE_TTL_SEC: Final[int] = 300        # 골대 캐시 TTL (5분)
HOOP_POSITION_CACHE_TTL_SEC: Final[int] = 5  # 위치 캐시 TTL (5초)
HOOP_DETECTION_FREQUENCY_FRAMES: Final[int] = 10  # 전체 감지 주기 (프레임)

# =============================================================================
# 네트 분석 기본 파라미터
# =============================================================================
NET_ANALYSIS_HISTORY_SIZE: Final[int] = 30       # 분석용 프레임 히스토리 크기
NET_MOTION_THRESHOLD_PX: Final[float] = 5.0      # 움직임 감지 임계값 (픽셀)
NET_SCORE_CONFIDENCE_THRESHOLD: Final[float] = 0.85  # 득점 판정 신뢰도
NET_MIN_AREA_PX: Final[int] = 500               # 최소 네트 영역 (픽셀²)
NET_MAX_AREA_PX: Final[int] = 50000             # 최대 네트 영역 (픽셀²)

# =============================================================================
# 광학 흐름 파라미터 (Lucas-Kanade)
# =============================================================================
NET_OPTICAL_FLOW_WIN_SIZE: Final[tuple[int, int]] = (21, 21)
NET_OPTICAL_FLOW_MAX_LEVEL: Final[int] = 3
NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT: Final[int] = 30
NET_OPTICAL_FLOW_CRITERIA_EPSILON: Final[float] = 0.01

# =============================================================================
# 네트 움직임 패턴 분석 (득점 유형 판별)
# =============================================================================
# 스위시 (Swish) - 공이 네트만 통과
NET_SWISH_VERTICAL_RATIO: Final[float] = 0.8     # 수직 움직임 비율 80% 이상
NET_SWISH_MIN_DISPLACEMENT_PX: Final[float] = 20.0  # 최소 수직 변위 (픽셀)
NET_SWISH_MAX_DURATION_FRAMES: Final[int] = 10    # 최대 지속 프레임

# 림인 (Rim-In) - 공이 림에 맞고 들어감
NET_RIM_IN_OSCILLATION_THRESHOLD: Final[float] = 3.0  # 진동 횟수 임계값
NET_RIM_IN_MIN_DISPLACEMENT_PX: Final[float] = 15.0   # 최소 변위 (픽셀)
NET_RIM_IN_MAX_DURATION_FRAMES: Final[int] = 20        # 최대 지속 프레임

# 림아웃 (Rim-Out) - 공이 림에 맞고 빠짐
NET_RIM_OUT_MAX_DISPLACEMENT_PX: Final[float] = 10.0  # 최대 변위 (작은 움직임)
NET_RIM_OUT_UPPER_RATIO: Final[float] = 0.3           # 상단 30%에서만 움직임

# =============================================================================
# 네트 색상 HSV 범위 (일반적으로 흰색 네트)
# =============================================================================
NET_COLOR_HSV_LOWER: Final[tuple[int, int, int]] = (0, 0, 200)
NET_COLOR_HSV_UPPER: Final[tuple[int, int, int]] = (180, 50, 255)

# =============================================================================
# 시간적 분석 파라미터
# =============================================================================
NET_MOTION_DECAY_FACTOR: Final[float] = 0.95  # 움직임 감쇠 계수
NET_MIN_FRAMES_FOR_ANALYSIS: Final[int] = 3    # 분석 최소 프레임 수
NET_COOLDOWN_FRAMES: Final[int] = 15           # 득점 판정 후 쿨다운

# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 골대 검출 기본 파라미터
    "HOOP_DETECTION_CONFIDENCE_THRESHOLD",
    "HOOP_DETECTION_IOU_THRESHOLD",
    "HOOP_DETECTION_INPUT_SIZE",
    "HOOP_DETECTION_MAX_DETECTIONS",
    "HOOP_CLASS_ID_RIM",
    "HOOP_CLASS_ID_BACKBOARD",
    "HOOP_CLASS_ID_NET",
    # 유소년 규격 보조
    "HOOP_YOUTH_BACKBOARD_WIDTH_M",
    "HOOP_YOUTH_BACKBOARD_HEIGHT_M",
    "HOOP_RIM_DIAMETER_IN",
    "HOOP_NET_LENGTH_M",
    # Hough Circle 파라미터
    "HOOP_HOUGH_DP",
    "HOOP_HOUGH_MIN_DIST",
    "HOOP_HOUGH_PARAM1",
    "HOOP_HOUGH_PARAM2",
    "HOOP_HOUGH_MIN_RADIUS",
    "HOOP_HOUGH_MAX_RADIUS",
    # 림 색상 HSV
    "HOOP_RIM_HSV_LOWER",
    "HOOP_RIM_HSV_UPPER",
    # 백보드 검출
    "HOOP_BACKBOARD_ASPECT_RATIO_MIN",
    "HOOP_BACKBOARD_ASPECT_RATIO_MAX",
    # 득점 판정
    "HOOP_SCORING_PASSING_ZONE_RATIO",
    "HOOP_SCORING_HEIGHT_TOLERANCE_M",
    "HOOP_SCORING_CONFIDENCE_THRESHOLD",
    "HOOP_SCORING_MIN_TRAJECTORY_POINTS",
    # 캐시 및 성능
    "HOOP_CACHE_TTL_SEC",
    "HOOP_POSITION_CACHE_TTL_SEC",
    "HOOP_DETECTION_FREQUENCY_FRAMES",
    # 네트 분석 기본
    "NET_ANALYSIS_HISTORY_SIZE",
    "NET_MOTION_THRESHOLD_PX",
    "NET_SCORE_CONFIDENCE_THRESHOLD",
    "NET_MIN_AREA_PX",
    "NET_MAX_AREA_PX",
    # 광학 흐름
    "NET_OPTICAL_FLOW_WIN_SIZE",
    "NET_OPTICAL_FLOW_MAX_LEVEL",
    "NET_OPTICAL_FLOW_CRITERIA_MAX_COUNT",
    "NET_OPTICAL_FLOW_CRITERIA_EPSILON",
    # 네트 움직임 패턴 - 스위시
    "NET_SWISH_VERTICAL_RATIO",
    "NET_SWISH_MIN_DISPLACEMENT_PX",
    "NET_SWISH_MAX_DURATION_FRAMES",
    # 네트 움직임 패턴 - 림인
    "NET_RIM_IN_OSCILLATION_THRESHOLD",
    "NET_RIM_IN_MIN_DISPLACEMENT_PX",
    "NET_RIM_IN_MAX_DURATION_FRAMES",
    # 네트 움직임 패턴 - 림아웃
    "NET_RIM_OUT_MAX_DISPLACEMENT_PX",
    "NET_RIM_OUT_UPPER_RATIO",
    # 네트 색상 HSV
    "NET_COLOR_HSV_LOWER",
    "NET_COLOR_HSV_UPPER",
    # 시간적 분석
    "NET_MOTION_DECAY_FACTOR",
    "NET_MIN_FRAMES_FOR_ANALYSIS",
    "NET_COOLDOWN_FRAMES",
]
