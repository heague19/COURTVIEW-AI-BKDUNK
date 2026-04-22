# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: pose_estimation
파일: keypoint_types.py
설명: 키포인트 정의, 모델 간 매핑, 스켈레톤 연결 정의

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0

포함 내용:
    - COCO 17개 키포인트 (YOLOv8-Pose)
    - MediaPipe 33개 키포인트 (레거시 호환)
    - COCO-WholeBody 133개 키포인트 (ViTPose)
    - 통합 25개 키포인트 (COURTVIEW 표준)
    - 스켈레톤 연결 정의
    - 모델 간 키포인트 매핑
    - 농구 동작별 키포인트 그룹
    - 한글 키포인트 이름

설계 원칙:
    - 순수 정의 모듈 (외부 의존성 없음)
    - IntEnum 사용으로 인덱싱 호환
    - 농구 분석에 최적화된 그룹화
"""
from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
from dataclasses import dataclass
from enum import IntEnum
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray


# ============================================================
# 키포인트 열거형: COCO (17개) - YOLOv8-Pose 사용
# ============================================================
class CocoKeypoint(IntEnum):
    """
    COCO 17개 키포인트 정의.

    YOLOv8-Pose, OpenPose 등에서 사용하는 표준 형식입니다.
    인덱스는 0부터 시작합니다.

    관절 구성:
        - 머리: 코, 눈, 귀 (5개)
        - 상체: 어깨, 팔꿈치, 손목 (6개)
        - 하체: 엉덩이, 무릎, 발목 (6개)
    """
    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10
    LEFT_HIP = 11
    RIGHT_HIP = 12
    LEFT_KNEE = 13
    RIGHT_KNEE = 14
    LEFT_ANKLE = 15
    RIGHT_ANKLE = 16


# ============================================================
# 키포인트 열거형: MediaPipe (33개) - 정밀 분석용
# ============================================================
class MediaPipeKeypoint(IntEnum):
    """
    MediaPipe Pose 33개 키포인트 정의.

    MediaPipe Pose에서 사용하는 형식입니다.
    3D 좌표 (x, y, z)와 가시성(visibility) 제공.

    COCO와 비교:
        - 손가락 끝 (INDEX, PINKY, THUMB) 포함
        - 발 끝 (FOOT_INDEX, HEEL) 포함
        - 입 (MOUTH) 포함
        - 총 33개로 더 정밀한 분석 가능

    z 좌표:
        - 깊이 정보 (카메라 기준)
        - 엉덩이 중심이 원점
        - 음수: 카메라에 가까움
        - 양수: 카메라에서 멀어짐
    """
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


# ============================================================
# 키포인트 열거형: Unified (25개) - COURTVIEW 통합 표준
# ============================================================
class UnifiedKeypoint(IntEnum):
    """
    COURTVIEW 통합 25개 키포인트 정의.

    COCO와 MediaPipe의 공통 부분 + 농구 분석에 필수적인 키포인트를 통합.
    모델 간 호환성을 위한 표준 형식입니다.

    구성:
        - 머리: 코, 눈, 귀 (5개)
        - 상체: 어깨, 팔꿈치, 손목 (6개)
        - 손: 검지, 새끼, 엄지 (6개) - 농구 릴리즈 분석용
        - 하체: 엉덩이, 무릎, 발목 (6개)
        - 척추: 목, 골반 중심 (2개)
    """
    # 머리 (5개)
    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4

    # 상체 - 팔 (6개)
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10

    # 손가락 (6개) - 농구 릴리즈 분석
    LEFT_INDEX = 11
    RIGHT_INDEX = 12
    LEFT_PINKY = 13
    RIGHT_PINKY = 14
    LEFT_THUMB = 15
    RIGHT_THUMB = 16

    # 하체 (6개)
    LEFT_HIP = 17
    RIGHT_HIP = 18
    LEFT_KNEE = 19
    RIGHT_KNEE = 20
    LEFT_ANKLE = 21
    RIGHT_ANKLE = 22

    # 척추 (2개) - 계산 키포인트
    NECK = 23  # 양 어깨 중심
    PELVIS = 24  # 양 엉덩이 중심 (hip center)


# ============================================================
# 키포인트 열거형: WholeBody (133개) - ViTPose WholeBody
# ============================================================
class WholeBodyKeypoint(IntEnum):
    """
    COCO-WholeBody 133개 키포인트 정의.

    ViTPose-WholeBody / DWPose 표준 형식.
    precision_pose_runner에서 사용하는 133kp 포맷.

    구성:
        - Body (0-16): 17개 (COCO 표준)
        - Foot (17-22): 6개 (발가락/발뒤꿈치)
        - Face (23-90): 68개 (dlib 68-point 호환)
        - LeftHand (91-111): 21개 (손가락 관절)
        - RightHand (112-132): 21개 (손가락 관절)
    """
    # ---- Body (0-16) — COCO 17kp ----
    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10
    LEFT_HIP = 11
    RIGHT_HIP = 12
    LEFT_KNEE = 13
    RIGHT_KNEE = 14
    LEFT_ANKLE = 15
    RIGHT_ANKLE = 16

    # ---- Foot (17-22) ----
    LEFT_BIG_TOE = 17
    LEFT_SMALL_TOE = 18
    LEFT_HEEL = 19
    RIGHT_BIG_TOE = 20
    RIGHT_SMALL_TOE = 21
    RIGHT_HEEL = 22

    # ---- Face (23-90): 68개 ----
    # 대표 랜드마크만 명명, 나머지는 정수 인덱스로 접근
    FACE_0 = 23    # 턱 시작 (jaw contour)
    FACE_8 = 31    # 턱 끝 (chin)
    FACE_17 = 40   # 왼쪽 눈썹 시작
    FACE_21 = 44   # 왼쪽 눈썹 끝
    FACE_22 = 45   # 오른쪽 눈썹 시작
    FACE_26 = 49   # 오른쪽 눈썹 끝
    FACE_27 = 50   # 코 시작 (콧대)
    FACE_30 = 53   # 코끝
    FACE_36 = 59   # 왼쪽 눈 안쪽 모서리
    FACE_39 = 62   # 왼쪽 눈 바깥쪽 모서리
    FACE_42 = 65   # 오른쪽 눈 안쪽 모서리
    FACE_45 = 68   # 오른쪽 눈 바깥쪽 모서리
    FACE_48 = 71   # 입 왼쪽 모서리
    FACE_54 = 77   # 입 오른쪽 모서리
    FACE_62 = 85   # 위 입술 안쪽 중앙
    FACE_66 = 89   # 아래 입술 안쪽 중앙
    FACE_67 = 90   # 마지막 얼굴 랜드마크

    # ---- LeftHand (91-111): 21개 ----
    LEFT_HAND_WRIST = 91
    LEFT_HAND_THUMB_CMC = 92
    LEFT_HAND_THUMB_MCP = 93
    LEFT_HAND_THUMB_IP = 94
    LEFT_HAND_THUMB_TIP = 95
    LEFT_HAND_INDEX_MCP = 96
    LEFT_HAND_INDEX_PIP = 97
    LEFT_HAND_INDEX_DIP = 98
    LEFT_HAND_INDEX_TIP = 99
    LEFT_HAND_MIDDLE_MCP = 100
    LEFT_HAND_MIDDLE_PIP = 101
    LEFT_HAND_MIDDLE_DIP = 102
    LEFT_HAND_MIDDLE_TIP = 103
    LEFT_HAND_RING_MCP = 104
    LEFT_HAND_RING_PIP = 105
    LEFT_HAND_RING_DIP = 106
    LEFT_HAND_RING_TIP = 107
    LEFT_HAND_PINKY_MCP = 108
    LEFT_HAND_PINKY_PIP = 109
    LEFT_HAND_PINKY_DIP = 110
    LEFT_HAND_PINKY_TIP = 111

    # ---- RightHand (112-132): 21개 ----
    RIGHT_HAND_WRIST = 112
    RIGHT_HAND_THUMB_CMC = 113
    RIGHT_HAND_THUMB_MCP = 114
    RIGHT_HAND_THUMB_IP = 115
    RIGHT_HAND_THUMB_TIP = 116
    RIGHT_HAND_INDEX_MCP = 117
    RIGHT_HAND_INDEX_PIP = 118
    RIGHT_HAND_INDEX_DIP = 119
    RIGHT_HAND_INDEX_TIP = 120
    RIGHT_HAND_MIDDLE_MCP = 121
    RIGHT_HAND_MIDDLE_PIP = 122
    RIGHT_HAND_MIDDLE_DIP = 123
    RIGHT_HAND_MIDDLE_TIP = 124
    RIGHT_HAND_RING_MCP = 125
    RIGHT_HAND_RING_PIP = 126
    RIGHT_HAND_RING_DIP = 127
    RIGHT_HAND_RING_TIP = 128
    RIGHT_HAND_PINKY_MCP = 129
    RIGHT_HAND_PINKY_PIP = 130
    RIGHT_HAND_PINKY_DIP = 131
    RIGHT_HAND_PINKY_TIP = 132


# ============================================================
# 데이터 클래스: 키포인트 데이터
# ============================================================
@dataclass(frozen=True, slots=True)
class KeypointData:
    """
    단일 키포인트 데이터.

    Attributes:
        x: 정규화된 x 좌표 [0, 1] 또는 픽셀 좌표
        y: 정규화된 y 좌표 [0, 1] 또는 픽셀 좌표
        z: 깊이 정보 (MediaPipe만 지원, 없으면 0.0)
        confidence: 신뢰도 [0, 1]
        visibility: 가시성 [0, 1] (MediaPipe만 지원)

    Note:
        frozen=True로 불변 객체, slots=True로 메모리 최적화
    """
    x: float
    y: float
    z: float = 0.0
    confidence: float = 0.0
    visibility: float = 1.0

    def to_array(self) -> NDArray[np.float32]:
        """NumPy 배열로 변환 (x, y, z, confidence)."""
        return np.array([self.x, self.y, self.z, self.confidence], dtype=np.float32)

    def to_2d(self) -> tuple[float, float]:
        """2D 좌표 튜플 반환."""
        return (self.x, self.y)

    def to_3d(self) -> tuple[float, float, float]:
        """3D 좌표 튜플 반환."""
        return (self.x, self.y, self.z)

    @classmethod
    def from_array(cls, arr: NDArray) -> KeypointData:
        """NumPy 배열에서 생성."""
        if len(arr) >= 4:
            return cls(x=float(arr[0]), y=float(arr[1]), z=float(arr[2]), confidence=float(arr[3]))
        elif len(arr) >= 3:
            return cls(x=float(arr[0]), y=float(arr[1]), confidence=float(arr[2]))
        else:
            return cls(x=float(arr[0]), y=float(arr[1]))


class KeypointPair(NamedTuple):
    """
    스켈레톤 연결 쌍.

    Attributes:
        start: 시작 키포인트 인덱스
        end: 끝 키포인트 인덱스
        name: 연결 이름 (선택)
    """
    start: int
    end: int
    name: str = ""


# ============================================================
# 스켈레톤 연결 정의
# ============================================================

# COCO 17 스켈레톤 연결
COCO_SKELETON: list[tuple[int, int]] = [
    # 머리
    (CocoKeypoint.LEFT_EAR, CocoKeypoint.LEFT_EYE),
    (CocoKeypoint.LEFT_EYE, CocoKeypoint.NOSE),
    (CocoKeypoint.NOSE, CocoKeypoint.RIGHT_EYE),
    (CocoKeypoint.RIGHT_EYE, CocoKeypoint.RIGHT_EAR),
    # 상체
    (CocoKeypoint.LEFT_SHOULDER, CocoKeypoint.RIGHT_SHOULDER),  # 어깨 라인
    (CocoKeypoint.LEFT_SHOULDER, CocoKeypoint.LEFT_ELBOW),
    (CocoKeypoint.LEFT_ELBOW, CocoKeypoint.LEFT_WRIST),
    (CocoKeypoint.RIGHT_SHOULDER, CocoKeypoint.RIGHT_ELBOW),
    (CocoKeypoint.RIGHT_ELBOW, CocoKeypoint.RIGHT_WRIST),
    # 몸통
    (CocoKeypoint.LEFT_SHOULDER, CocoKeypoint.LEFT_HIP),
    (CocoKeypoint.RIGHT_SHOULDER, CocoKeypoint.RIGHT_HIP),
    (CocoKeypoint.LEFT_HIP, CocoKeypoint.RIGHT_HIP),  # 골반 라인
    # 하체
    (CocoKeypoint.LEFT_HIP, CocoKeypoint.LEFT_KNEE),
    (CocoKeypoint.LEFT_KNEE, CocoKeypoint.LEFT_ANKLE),
    (CocoKeypoint.RIGHT_HIP, CocoKeypoint.RIGHT_KNEE),
    (CocoKeypoint.RIGHT_KNEE, CocoKeypoint.RIGHT_ANKLE),
]

# MediaPipe 33 스켈레톤 연결
MEDIAPIPE_SKELETON: list[tuple[int, int]] = [
    # 얼굴
    (MediaPipeKeypoint.NOSE, MediaPipeKeypoint.LEFT_EYE_INNER),
    (MediaPipeKeypoint.LEFT_EYE_INNER, MediaPipeKeypoint.LEFT_EYE),
    (MediaPipeKeypoint.LEFT_EYE, MediaPipeKeypoint.LEFT_EYE_OUTER),
    (MediaPipeKeypoint.LEFT_EYE_OUTER, MediaPipeKeypoint.LEFT_EAR),
    (MediaPipeKeypoint.NOSE, MediaPipeKeypoint.RIGHT_EYE_INNER),
    (MediaPipeKeypoint.RIGHT_EYE_INNER, MediaPipeKeypoint.RIGHT_EYE),
    (MediaPipeKeypoint.RIGHT_EYE, MediaPipeKeypoint.RIGHT_EYE_OUTER),
    (MediaPipeKeypoint.RIGHT_EYE_OUTER, MediaPipeKeypoint.RIGHT_EAR),
    (MediaPipeKeypoint.MOUTH_LEFT, MediaPipeKeypoint.MOUTH_RIGHT),
    # 상체
    (MediaPipeKeypoint.LEFT_SHOULDER, MediaPipeKeypoint.RIGHT_SHOULDER),
    (MediaPipeKeypoint.LEFT_SHOULDER, MediaPipeKeypoint.LEFT_ELBOW),
    (MediaPipeKeypoint.LEFT_ELBOW, MediaPipeKeypoint.LEFT_WRIST),
    (MediaPipeKeypoint.RIGHT_SHOULDER, MediaPipeKeypoint.RIGHT_ELBOW),
    (MediaPipeKeypoint.RIGHT_ELBOW, MediaPipeKeypoint.RIGHT_WRIST),
    # 손
    (MediaPipeKeypoint.LEFT_WRIST, MediaPipeKeypoint.LEFT_PINKY),
    (MediaPipeKeypoint.LEFT_WRIST, MediaPipeKeypoint.LEFT_INDEX),
    (MediaPipeKeypoint.LEFT_WRIST, MediaPipeKeypoint.LEFT_THUMB),
    (MediaPipeKeypoint.LEFT_INDEX, MediaPipeKeypoint.LEFT_PINKY),
    (MediaPipeKeypoint.RIGHT_WRIST, MediaPipeKeypoint.RIGHT_PINKY),
    (MediaPipeKeypoint.RIGHT_WRIST, MediaPipeKeypoint.RIGHT_INDEX),
    (MediaPipeKeypoint.RIGHT_WRIST, MediaPipeKeypoint.RIGHT_THUMB),
    (MediaPipeKeypoint.RIGHT_INDEX, MediaPipeKeypoint.RIGHT_PINKY),
    # 몸통
    (MediaPipeKeypoint.LEFT_SHOULDER, MediaPipeKeypoint.LEFT_HIP),
    (MediaPipeKeypoint.RIGHT_SHOULDER, MediaPipeKeypoint.RIGHT_HIP),
    (MediaPipeKeypoint.LEFT_HIP, MediaPipeKeypoint.RIGHT_HIP),
    # 하체
    (MediaPipeKeypoint.LEFT_HIP, MediaPipeKeypoint.LEFT_KNEE),
    (MediaPipeKeypoint.LEFT_KNEE, MediaPipeKeypoint.LEFT_ANKLE),
    (MediaPipeKeypoint.LEFT_ANKLE, MediaPipeKeypoint.LEFT_HEEL),
    (MediaPipeKeypoint.LEFT_ANKLE, MediaPipeKeypoint.LEFT_FOOT_INDEX),
    (MediaPipeKeypoint.LEFT_HEEL, MediaPipeKeypoint.LEFT_FOOT_INDEX),
    (MediaPipeKeypoint.RIGHT_HIP, MediaPipeKeypoint.RIGHT_KNEE),
    (MediaPipeKeypoint.RIGHT_KNEE, MediaPipeKeypoint.RIGHT_ANKLE),
    (MediaPipeKeypoint.RIGHT_ANKLE, MediaPipeKeypoint.RIGHT_HEEL),
    (MediaPipeKeypoint.RIGHT_ANKLE, MediaPipeKeypoint.RIGHT_FOOT_INDEX),
    (MediaPipeKeypoint.RIGHT_HEEL, MediaPipeKeypoint.RIGHT_FOOT_INDEX),
]

# WholeBody 133 스켈레톤 연결 (Body + Foot 주요 연결)
WHOLEBODY_BODY_SKELETON: list[tuple[int, int]] = [
    # 머리
    (0, 1), (0, 2), (1, 3), (2, 4),
    # 상체
    (5, 6),                          # 어깨 라인
    (5, 7), (7, 9),                  # 왼팔
    (6, 8), (8, 10),                 # 오른팔
    # 몸통
    (5, 11), (6, 12),                # 어깨 → 엉덩이
    (11, 12),                        # 골반 라인
    # 하체
    (11, 13), (13, 15),              # 왼쪽 다리
    (12, 14), (14, 16),              # 오른쪽 다리
    # 발
    (15, 17), (15, 19),              # 왼쪽 발목 → 발가락/발뒤꿈치
    (17, 18),                        # 왼쪽 엄지 → 새끼발가락
    (16, 20), (16, 22),              # 오른쪽 발목 → 발가락/발뒤꿈치
    (20, 21),                        # 오른쪽 엄지 → 새끼발가락
    # 왼손 (손목 → 각 손가락)
    (9, 91),                         # 손목 → 왼손 wrist
    (91, 92), (92, 93), (93, 94), (94, 95),    # 엄지
    (91, 96), (96, 97), (97, 98), (98, 99),    # 검지
    (91, 100), (100, 101), (101, 102), (102, 103),  # 중지
    (91, 104), (104, 105), (105, 106), (106, 107),  # 약지
    (91, 108), (108, 109), (109, 110), (110, 111),  # 새끼
    # 오른손 (손목 → 각 손가락)
    (10, 112),                       # 손목 → 오른손 wrist
    (112, 113), (113, 114), (114, 115), (115, 116),  # 엄지
    (112, 117), (117, 118), (118, 119), (119, 120),  # 검지
    (112, 121), (121, 122), (122, 123), (123, 124),  # 중지
    (112, 125), (125, 126), (126, 127), (127, 128),  # 약지
    (112, 129), (129, 130), (130, 131), (131, 132),  # 새끼
]

# Unified 25 스켈레톤 연결 (KeypointPair 사용)
SKELETON_CONNECTIONS: list[KeypointPair] = [
    # 머리
    KeypointPair(UnifiedKeypoint.LEFT_EAR, UnifiedKeypoint.LEFT_EYE, "왼쪽 귀-눈"),
    KeypointPair(UnifiedKeypoint.LEFT_EYE, UnifiedKeypoint.NOSE, "왼쪽 눈-코"),
    KeypointPair(UnifiedKeypoint.NOSE, UnifiedKeypoint.RIGHT_EYE, "코-오른쪽 눈"),
    KeypointPair(UnifiedKeypoint.RIGHT_EYE, UnifiedKeypoint.RIGHT_EAR, "오른쪽 눈-귀"),
    # 목-어깨
    KeypointPair(UnifiedKeypoint.NOSE, UnifiedKeypoint.NECK, "코-목"),
    KeypointPair(UnifiedKeypoint.NECK, UnifiedKeypoint.LEFT_SHOULDER, "목-왼쪽 어깨"),
    KeypointPair(UnifiedKeypoint.NECK, UnifiedKeypoint.RIGHT_SHOULDER, "목-오른쪽 어깨"),
    KeypointPair(UnifiedKeypoint.LEFT_SHOULDER, UnifiedKeypoint.RIGHT_SHOULDER, "어깨 라인"),
    # 왼팔
    KeypointPair(UnifiedKeypoint.LEFT_SHOULDER, UnifiedKeypoint.LEFT_ELBOW, "왼쪽 상완"),
    KeypointPair(UnifiedKeypoint.LEFT_ELBOW, UnifiedKeypoint.LEFT_WRIST, "왼쪽 전완"),
    KeypointPair(UnifiedKeypoint.LEFT_WRIST, UnifiedKeypoint.LEFT_INDEX, "왼쪽 손-검지"),
    KeypointPair(UnifiedKeypoint.LEFT_WRIST, UnifiedKeypoint.LEFT_PINKY, "왼쪽 손-새끼"),
    KeypointPair(UnifiedKeypoint.LEFT_WRIST, UnifiedKeypoint.LEFT_THUMB, "왼쪽 손-엄지"),
    # 오른팔
    KeypointPair(UnifiedKeypoint.RIGHT_SHOULDER, UnifiedKeypoint.RIGHT_ELBOW, "오른쪽 상완"),
    KeypointPair(UnifiedKeypoint.RIGHT_ELBOW, UnifiedKeypoint.RIGHT_WRIST, "오른쪽 전완"),
    KeypointPair(UnifiedKeypoint.RIGHT_WRIST, UnifiedKeypoint.RIGHT_INDEX, "오른쪽 손-검지"),
    KeypointPair(UnifiedKeypoint.RIGHT_WRIST, UnifiedKeypoint.RIGHT_PINKY, "오른쪽 손-새끼"),
    KeypointPair(UnifiedKeypoint.RIGHT_WRIST, UnifiedKeypoint.RIGHT_THUMB, "오른쪽 손-엄지"),
    # 몸통
    KeypointPair(UnifiedKeypoint.NECK, UnifiedKeypoint.PELVIS, "척추"),
    KeypointPair(UnifiedKeypoint.LEFT_SHOULDER, UnifiedKeypoint.LEFT_HIP, "왼쪽 몸통"),
    KeypointPair(UnifiedKeypoint.RIGHT_SHOULDER, UnifiedKeypoint.RIGHT_HIP, "오른쪽 몸통"),
    KeypointPair(UnifiedKeypoint.PELVIS, UnifiedKeypoint.LEFT_HIP, "골반-왼쪽 엉덩이"),
    KeypointPair(UnifiedKeypoint.PELVIS, UnifiedKeypoint.RIGHT_HIP, "골반-오른쪽 엉덩이"),
    KeypointPair(UnifiedKeypoint.LEFT_HIP, UnifiedKeypoint.RIGHT_HIP, "골반 라인"),
    # 왼쪽 다리
    KeypointPair(UnifiedKeypoint.LEFT_HIP, UnifiedKeypoint.LEFT_KNEE, "왼쪽 허벅지"),
    KeypointPair(UnifiedKeypoint.LEFT_KNEE, UnifiedKeypoint.LEFT_ANKLE, "왼쪽 정강이"),
    # 오른쪽 다리
    KeypointPair(UnifiedKeypoint.RIGHT_HIP, UnifiedKeypoint.RIGHT_KNEE, "오른쪽 허벅지"),
    KeypointPair(UnifiedKeypoint.RIGHT_KNEE, UnifiedKeypoint.RIGHT_ANKLE, "오른쪽 정강이"),
]


# ============================================================
# 신체 부위 그룹
# ============================================================

# 통합 신체 부위별 키포인트
BODY_PARTS: dict[str, frozenset[UnifiedKeypoint]] = {
    "head": frozenset([
        UnifiedKeypoint.NOSE,
        UnifiedKeypoint.LEFT_EYE,
        UnifiedKeypoint.RIGHT_EYE,
        UnifiedKeypoint.LEFT_EAR,
        UnifiedKeypoint.RIGHT_EAR,
    ]),
    "neck": frozenset([
        UnifiedKeypoint.NECK,
    ]),
    "torso": frozenset([
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.NECK,
        UnifiedKeypoint.PELVIS,
    ]),
    "left_arm": frozenset([
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.LEFT_ELBOW,
        UnifiedKeypoint.LEFT_WRIST,
    ]),
    "right_arm": frozenset([
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.RIGHT_ELBOW,
        UnifiedKeypoint.RIGHT_WRIST,
    ]),
    "left_hand": frozenset([
        UnifiedKeypoint.LEFT_WRIST,
        UnifiedKeypoint.LEFT_INDEX,
        UnifiedKeypoint.LEFT_PINKY,
        UnifiedKeypoint.LEFT_THUMB,
    ]),
    "right_hand": frozenset([
        UnifiedKeypoint.RIGHT_WRIST,
        UnifiedKeypoint.RIGHT_INDEX,
        UnifiedKeypoint.RIGHT_PINKY,
        UnifiedKeypoint.RIGHT_THUMB,
    ]),
    "left_leg": frozenset([
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.LEFT_KNEE,
        UnifiedKeypoint.LEFT_ANKLE,
    ]),
    "right_leg": frozenset([
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.RIGHT_KNEE,
        UnifiedKeypoint.RIGHT_ANKLE,
    ]),
}

# 좌우 분류
LEFT_SIDE_KEYPOINTS: frozenset[UnifiedKeypoint] = frozenset([
    UnifiedKeypoint.LEFT_EYE,
    UnifiedKeypoint.LEFT_EAR,
    UnifiedKeypoint.LEFT_SHOULDER,
    UnifiedKeypoint.LEFT_ELBOW,
    UnifiedKeypoint.LEFT_WRIST,
    UnifiedKeypoint.LEFT_INDEX,
    UnifiedKeypoint.LEFT_PINKY,
    UnifiedKeypoint.LEFT_THUMB,
    UnifiedKeypoint.LEFT_HIP,
    UnifiedKeypoint.LEFT_KNEE,
    UnifiedKeypoint.LEFT_ANKLE,
])

RIGHT_SIDE_KEYPOINTS: frozenset[UnifiedKeypoint] = frozenset([
    UnifiedKeypoint.RIGHT_EYE,
    UnifiedKeypoint.RIGHT_EAR,
    UnifiedKeypoint.RIGHT_SHOULDER,
    UnifiedKeypoint.RIGHT_ELBOW,
    UnifiedKeypoint.RIGHT_WRIST,
    UnifiedKeypoint.RIGHT_INDEX,
    UnifiedKeypoint.RIGHT_PINKY,
    UnifiedKeypoint.RIGHT_THUMB,
    UnifiedKeypoint.RIGHT_HIP,
    UnifiedKeypoint.RIGHT_KNEE,
    UnifiedKeypoint.RIGHT_ANKLE,
])

# 상하체 분류
UPPER_BODY_KEYPOINTS: frozenset[UnifiedKeypoint] = frozenset([
    UnifiedKeypoint.NOSE,
    UnifiedKeypoint.LEFT_EYE,
    UnifiedKeypoint.RIGHT_EYE,
    UnifiedKeypoint.LEFT_EAR,
    UnifiedKeypoint.RIGHT_EAR,
    UnifiedKeypoint.NECK,
    UnifiedKeypoint.LEFT_SHOULDER,
    UnifiedKeypoint.RIGHT_SHOULDER,
    UnifiedKeypoint.LEFT_ELBOW,
    UnifiedKeypoint.RIGHT_ELBOW,
    UnifiedKeypoint.LEFT_WRIST,
    UnifiedKeypoint.RIGHT_WRIST,
    UnifiedKeypoint.LEFT_INDEX,
    UnifiedKeypoint.RIGHT_INDEX,
    UnifiedKeypoint.LEFT_PINKY,
    UnifiedKeypoint.RIGHT_PINKY,
    UnifiedKeypoint.LEFT_THUMB,
    UnifiedKeypoint.RIGHT_THUMB,
])

LOWER_BODY_KEYPOINTS: frozenset[UnifiedKeypoint] = frozenset([
    UnifiedKeypoint.PELVIS,
    UnifiedKeypoint.LEFT_HIP,
    UnifiedKeypoint.RIGHT_HIP,
    UnifiedKeypoint.LEFT_KNEE,
    UnifiedKeypoint.RIGHT_KNEE,
    UnifiedKeypoint.LEFT_ANKLE,
    UnifiedKeypoint.RIGHT_ANKLE,
])


# ============================================================
# 농구 특화 그룹
# ============================================================

# 슈팅 팔 관련 키포인트 (오른손잡이 기준)
SHOOTING_ARM_KEYPOINTS: frozenset[UnifiedKeypoint] = frozenset([
    UnifiedKeypoint.RIGHT_SHOULDER,
    UnifiedKeypoint.RIGHT_ELBOW,
    UnifiedKeypoint.RIGHT_WRIST,
    UnifiedKeypoint.RIGHT_INDEX,
    UnifiedKeypoint.RIGHT_PINKY,
    UnifiedKeypoint.RIGHT_THUMB,
])

# 드리블 관련 키포인트
DRIBBLING_KEYPOINTS: frozenset[UnifiedKeypoint] = frozenset([
    UnifiedKeypoint.LEFT_SHOULDER,
    UnifiedKeypoint.RIGHT_SHOULDER,
    UnifiedKeypoint.LEFT_ELBOW,
    UnifiedKeypoint.RIGHT_ELBOW,
    UnifiedKeypoint.LEFT_WRIST,
    UnifiedKeypoint.RIGHT_WRIST,
    UnifiedKeypoint.LEFT_HIP,
    UnifiedKeypoint.RIGHT_HIP,
    UnifiedKeypoint.LEFT_KNEE,
    UnifiedKeypoint.RIGHT_KNEE,
])

# 농구 동작별 키포인트 그룹
BASKETBALL_KEYPOINT_GROUPS: dict[str, frozenset[UnifiedKeypoint]] = {
    # 슛팅 동작 (상체 중심)
    "shooting": frozenset([
        UnifiedKeypoint.NECK,
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.LEFT_ELBOW,
        UnifiedKeypoint.RIGHT_ELBOW,
        UnifiedKeypoint.LEFT_WRIST,
        UnifiedKeypoint.RIGHT_WRIST,
        UnifiedKeypoint.LEFT_INDEX,
        UnifiedKeypoint.RIGHT_INDEX,
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.LEFT_KNEE,
        UnifiedKeypoint.RIGHT_KNEE,
    ]),

    # 릴리즈 포인트 분석 (손/손목 상세)
    "release": frozenset([
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.RIGHT_ELBOW,
        UnifiedKeypoint.RIGHT_WRIST,
        UnifiedKeypoint.RIGHT_INDEX,
        UnifiedKeypoint.RIGHT_PINKY,
        UnifiedKeypoint.RIGHT_THUMB,
    ]),

    # 드리블 동작 (상하체 균형)
    "dribbling": frozenset([
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.LEFT_ELBOW,
        UnifiedKeypoint.RIGHT_ELBOW,
        UnifiedKeypoint.LEFT_WRIST,
        UnifiedKeypoint.RIGHT_WRIST,
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.LEFT_KNEE,
        UnifiedKeypoint.RIGHT_KNEE,
        UnifiedKeypoint.LEFT_ANKLE,
        UnifiedKeypoint.RIGHT_ANKLE,
    ]),

    # 수비 자세 (하체 중심)
    "defense": frozenset([
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.LEFT_KNEE,
        UnifiedKeypoint.RIGHT_KNEE,
        UnifiedKeypoint.LEFT_ANKLE,
        UnifiedKeypoint.RIGHT_ANKLE,
    ]),

    # 점프 분석
    "jumping": frozenset([
        UnifiedKeypoint.PELVIS,
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.LEFT_KNEE,
        UnifiedKeypoint.RIGHT_KNEE,
        UnifiedKeypoint.LEFT_ANKLE,
        UnifiedKeypoint.RIGHT_ANKLE,
    ]),

    # 피벗 동작
    "pivot": frozenset([
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.LEFT_KNEE,
        UnifiedKeypoint.RIGHT_KNEE,
        UnifiedKeypoint.LEFT_ANKLE,
        UnifiedKeypoint.RIGHT_ANKLE,
    ]),

    # 패스 동작
    "passing": frozenset([
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.LEFT_ELBOW,
        UnifiedKeypoint.RIGHT_ELBOW,
        UnifiedKeypoint.LEFT_WRIST,
        UnifiedKeypoint.RIGHT_WRIST,
        UnifiedKeypoint.PELVIS,
    ]),

    # 리바운드 동작
    "rebounding": frozenset([
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.LEFT_ELBOW,
        UnifiedKeypoint.RIGHT_ELBOW,
        UnifiedKeypoint.LEFT_WRIST,
        UnifiedKeypoint.RIGHT_WRIST,
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.LEFT_KNEE,
        UnifiedKeypoint.RIGHT_KNEE,
    ]),
}


# ============================================================
# 모델 간 키포인트 매핑
# ============================================================

# COCO (17) → Unified (25) 매핑
COCO_TO_UNIFIED_MAPPING: dict[CocoKeypoint, UnifiedKeypoint] = {
    CocoKeypoint.NOSE: UnifiedKeypoint.NOSE,
    CocoKeypoint.LEFT_EYE: UnifiedKeypoint.LEFT_EYE,
    CocoKeypoint.RIGHT_EYE: UnifiedKeypoint.RIGHT_EYE,
    CocoKeypoint.LEFT_EAR: UnifiedKeypoint.LEFT_EAR,
    CocoKeypoint.RIGHT_EAR: UnifiedKeypoint.RIGHT_EAR,
    CocoKeypoint.LEFT_SHOULDER: UnifiedKeypoint.LEFT_SHOULDER,
    CocoKeypoint.RIGHT_SHOULDER: UnifiedKeypoint.RIGHT_SHOULDER,
    CocoKeypoint.LEFT_ELBOW: UnifiedKeypoint.LEFT_ELBOW,
    CocoKeypoint.RIGHT_ELBOW: UnifiedKeypoint.RIGHT_ELBOW,
    CocoKeypoint.LEFT_WRIST: UnifiedKeypoint.LEFT_WRIST,
    CocoKeypoint.RIGHT_WRIST: UnifiedKeypoint.RIGHT_WRIST,
    CocoKeypoint.LEFT_HIP: UnifiedKeypoint.LEFT_HIP,
    CocoKeypoint.RIGHT_HIP: UnifiedKeypoint.RIGHT_HIP,
    CocoKeypoint.LEFT_KNEE: UnifiedKeypoint.LEFT_KNEE,
    CocoKeypoint.RIGHT_KNEE: UnifiedKeypoint.RIGHT_KNEE,
    CocoKeypoint.LEFT_ANKLE: UnifiedKeypoint.LEFT_ANKLE,
    CocoKeypoint.RIGHT_ANKLE: UnifiedKeypoint.RIGHT_ANKLE,
}

# MediaPipe (33) → Unified (25) 매핑
MEDIAPIPE_TO_UNIFIED_MAPPING: dict[MediaPipeKeypoint, UnifiedKeypoint] = {
    MediaPipeKeypoint.NOSE: UnifiedKeypoint.NOSE,
    MediaPipeKeypoint.LEFT_EYE: UnifiedKeypoint.LEFT_EYE,
    MediaPipeKeypoint.RIGHT_EYE: UnifiedKeypoint.RIGHT_EYE,
    MediaPipeKeypoint.LEFT_EAR: UnifiedKeypoint.LEFT_EAR,
    MediaPipeKeypoint.RIGHT_EAR: UnifiedKeypoint.RIGHT_EAR,
    MediaPipeKeypoint.LEFT_SHOULDER: UnifiedKeypoint.LEFT_SHOULDER,
    MediaPipeKeypoint.RIGHT_SHOULDER: UnifiedKeypoint.RIGHT_SHOULDER,
    MediaPipeKeypoint.LEFT_ELBOW: UnifiedKeypoint.LEFT_ELBOW,
    MediaPipeKeypoint.RIGHT_ELBOW: UnifiedKeypoint.RIGHT_ELBOW,
    MediaPipeKeypoint.LEFT_WRIST: UnifiedKeypoint.LEFT_WRIST,
    MediaPipeKeypoint.RIGHT_WRIST: UnifiedKeypoint.RIGHT_WRIST,
    MediaPipeKeypoint.LEFT_INDEX: UnifiedKeypoint.LEFT_INDEX,
    MediaPipeKeypoint.RIGHT_INDEX: UnifiedKeypoint.RIGHT_INDEX,
    MediaPipeKeypoint.LEFT_PINKY: UnifiedKeypoint.LEFT_PINKY,
    MediaPipeKeypoint.RIGHT_PINKY: UnifiedKeypoint.RIGHT_PINKY,
    MediaPipeKeypoint.LEFT_THUMB: UnifiedKeypoint.LEFT_THUMB,
    MediaPipeKeypoint.RIGHT_THUMB: UnifiedKeypoint.RIGHT_THUMB,
    MediaPipeKeypoint.LEFT_HIP: UnifiedKeypoint.LEFT_HIP,
    MediaPipeKeypoint.RIGHT_HIP: UnifiedKeypoint.RIGHT_HIP,
    MediaPipeKeypoint.LEFT_KNEE: UnifiedKeypoint.LEFT_KNEE,
    MediaPipeKeypoint.RIGHT_KNEE: UnifiedKeypoint.RIGHT_KNEE,
    MediaPipeKeypoint.LEFT_ANKLE: UnifiedKeypoint.LEFT_ANKLE,
    MediaPipeKeypoint.RIGHT_ANKLE: UnifiedKeypoint.RIGHT_ANKLE,
}

# WholeBody (133) → COCO (17) 매핑 (Body 0-16 동일)
WHOLEBODY_TO_COCO_MAPPING: dict[int, int] = {i: i for i in range(17)}

# WholeBody (133) → Unified (25) 매핑
WHOLEBODY_TO_UNIFIED_MAPPING: dict[int, int] = {
    # Body (0-16) → Unified
    0: 0,    # NOSE
    1: 1,    # LEFT_EYE
    2: 2,    # RIGHT_EYE
    3: 3,    # LEFT_EAR
    4: 4,    # RIGHT_EAR
    5: 5,    # LEFT_SHOULDER
    6: 6,    # RIGHT_SHOULDER
    7: 7,    # LEFT_ELBOW
    8: 8,    # RIGHT_ELBOW
    9: 9,    # LEFT_WRIST
    10: 10,  # RIGHT_WRIST
    11: 17,  # LEFT_HIP → Unified LEFT_HIP
    12: 18,  # RIGHT_HIP → Unified RIGHT_HIP
    13: 19,  # LEFT_KNEE → Unified LEFT_KNEE
    14: 20,  # RIGHT_KNEE → Unified RIGHT_KNEE
    15: 21,  # LEFT_ANKLE → Unified LEFT_ANKLE
    16: 22,  # RIGHT_ANKLE → Unified RIGHT_ANKLE
    # 손가락 끝 → Unified 손가락
    99: 11,   # LEFT_HAND_INDEX_TIP → LEFT_INDEX
    120: 12,  # RIGHT_HAND_INDEX_TIP → RIGHT_INDEX
    111: 13,  # LEFT_HAND_PINKY_TIP → LEFT_PINKY
    132: 14,  # RIGHT_HAND_PINKY_TIP → RIGHT_PINKY
    95: 15,   # LEFT_HAND_THUMB_TIP → LEFT_THUMB
    116: 16,  # RIGHT_HAND_THUMB_TIP → RIGHT_THUMB
}

# Unified (25) → COCO (17) 역매핑 (손가락 등 없음)
UNIFIED_TO_COCO_MAPPING: dict[UnifiedKeypoint, CocoKeypoint | None] = {
    UnifiedKeypoint.NOSE: CocoKeypoint.NOSE,
    UnifiedKeypoint.LEFT_EYE: CocoKeypoint.LEFT_EYE,
    UnifiedKeypoint.RIGHT_EYE: CocoKeypoint.RIGHT_EYE,
    UnifiedKeypoint.LEFT_EAR: CocoKeypoint.LEFT_EAR,
    UnifiedKeypoint.RIGHT_EAR: CocoKeypoint.RIGHT_EAR,
    UnifiedKeypoint.LEFT_SHOULDER: CocoKeypoint.LEFT_SHOULDER,
    UnifiedKeypoint.RIGHT_SHOULDER: CocoKeypoint.RIGHT_SHOULDER,
    UnifiedKeypoint.LEFT_ELBOW: CocoKeypoint.LEFT_ELBOW,
    UnifiedKeypoint.RIGHT_ELBOW: CocoKeypoint.RIGHT_ELBOW,
    UnifiedKeypoint.LEFT_WRIST: CocoKeypoint.LEFT_WRIST,
    UnifiedKeypoint.RIGHT_WRIST: CocoKeypoint.RIGHT_WRIST,
    UnifiedKeypoint.LEFT_INDEX: None,  # COCO에 없음
    UnifiedKeypoint.RIGHT_INDEX: None,
    UnifiedKeypoint.LEFT_PINKY: None,
    UnifiedKeypoint.RIGHT_PINKY: None,
    UnifiedKeypoint.LEFT_THUMB: None,
    UnifiedKeypoint.RIGHT_THUMB: None,
    UnifiedKeypoint.LEFT_HIP: CocoKeypoint.LEFT_HIP,
    UnifiedKeypoint.RIGHT_HIP: CocoKeypoint.RIGHT_HIP,
    UnifiedKeypoint.LEFT_KNEE: CocoKeypoint.LEFT_KNEE,
    UnifiedKeypoint.RIGHT_KNEE: CocoKeypoint.RIGHT_KNEE,
    UnifiedKeypoint.LEFT_ANKLE: CocoKeypoint.LEFT_ANKLE,
    UnifiedKeypoint.RIGHT_ANKLE: CocoKeypoint.RIGHT_ANKLE,
    UnifiedKeypoint.NECK: None,  # COCO에 없음 (계산 필요)
    UnifiedKeypoint.PELVIS: None,  # COCO에 없음 (계산 필요)
}

# Unified (25) → MediaPipe (33) 역매핑
UNIFIED_TO_MEDIAPIPE_MAPPING: dict[UnifiedKeypoint, MediaPipeKeypoint | None] = {
    UnifiedKeypoint.NOSE: MediaPipeKeypoint.NOSE,
    UnifiedKeypoint.LEFT_EYE: MediaPipeKeypoint.LEFT_EYE,
    UnifiedKeypoint.RIGHT_EYE: MediaPipeKeypoint.RIGHT_EYE,
    UnifiedKeypoint.LEFT_EAR: MediaPipeKeypoint.LEFT_EAR,
    UnifiedKeypoint.RIGHT_EAR: MediaPipeKeypoint.RIGHT_EAR,
    UnifiedKeypoint.LEFT_SHOULDER: MediaPipeKeypoint.LEFT_SHOULDER,
    UnifiedKeypoint.RIGHT_SHOULDER: MediaPipeKeypoint.RIGHT_SHOULDER,
    UnifiedKeypoint.LEFT_ELBOW: MediaPipeKeypoint.LEFT_ELBOW,
    UnifiedKeypoint.RIGHT_ELBOW: MediaPipeKeypoint.RIGHT_ELBOW,
    UnifiedKeypoint.LEFT_WRIST: MediaPipeKeypoint.LEFT_WRIST,
    UnifiedKeypoint.RIGHT_WRIST: MediaPipeKeypoint.RIGHT_WRIST,
    UnifiedKeypoint.LEFT_INDEX: MediaPipeKeypoint.LEFT_INDEX,
    UnifiedKeypoint.RIGHT_INDEX: MediaPipeKeypoint.RIGHT_INDEX,
    UnifiedKeypoint.LEFT_PINKY: MediaPipeKeypoint.LEFT_PINKY,
    UnifiedKeypoint.RIGHT_PINKY: MediaPipeKeypoint.RIGHT_PINKY,
    UnifiedKeypoint.LEFT_THUMB: MediaPipeKeypoint.LEFT_THUMB,
    UnifiedKeypoint.RIGHT_THUMB: MediaPipeKeypoint.RIGHT_THUMB,
    UnifiedKeypoint.LEFT_HIP: MediaPipeKeypoint.LEFT_HIP,
    UnifiedKeypoint.RIGHT_HIP: MediaPipeKeypoint.RIGHT_HIP,
    UnifiedKeypoint.LEFT_KNEE: MediaPipeKeypoint.LEFT_KNEE,
    UnifiedKeypoint.RIGHT_KNEE: MediaPipeKeypoint.RIGHT_KNEE,
    UnifiedKeypoint.LEFT_ANKLE: MediaPipeKeypoint.LEFT_ANKLE,
    UnifiedKeypoint.RIGHT_ANKLE: MediaPipeKeypoint.RIGHT_ANKLE,
    UnifiedKeypoint.NECK: None,  # MediaPipe에 없음 (계산 필요)
    UnifiedKeypoint.PELVIS: None,  # MediaPipe에 없음 (계산 필요)
}


# ============================================================
# 대칭 키포인트 쌍
# ============================================================

# Unified 좌우 대칭 쌍
UNIFIED_SYMMETRIC_PAIRS: dict[UnifiedKeypoint, UnifiedKeypoint] = {
    UnifiedKeypoint.LEFT_EYE: UnifiedKeypoint.RIGHT_EYE,
    UnifiedKeypoint.RIGHT_EYE: UnifiedKeypoint.LEFT_EYE,
    UnifiedKeypoint.LEFT_EAR: UnifiedKeypoint.RIGHT_EAR,
    UnifiedKeypoint.RIGHT_EAR: UnifiedKeypoint.LEFT_EAR,
    UnifiedKeypoint.LEFT_SHOULDER: UnifiedKeypoint.RIGHT_SHOULDER,
    UnifiedKeypoint.RIGHT_SHOULDER: UnifiedKeypoint.LEFT_SHOULDER,
    UnifiedKeypoint.LEFT_ELBOW: UnifiedKeypoint.RIGHT_ELBOW,
    UnifiedKeypoint.RIGHT_ELBOW: UnifiedKeypoint.LEFT_ELBOW,
    UnifiedKeypoint.LEFT_WRIST: UnifiedKeypoint.RIGHT_WRIST,
    UnifiedKeypoint.RIGHT_WRIST: UnifiedKeypoint.LEFT_WRIST,
    UnifiedKeypoint.LEFT_INDEX: UnifiedKeypoint.RIGHT_INDEX,
    UnifiedKeypoint.RIGHT_INDEX: UnifiedKeypoint.LEFT_INDEX,
    UnifiedKeypoint.LEFT_PINKY: UnifiedKeypoint.RIGHT_PINKY,
    UnifiedKeypoint.RIGHT_PINKY: UnifiedKeypoint.LEFT_PINKY,
    UnifiedKeypoint.LEFT_THUMB: UnifiedKeypoint.RIGHT_THUMB,
    UnifiedKeypoint.RIGHT_THUMB: UnifiedKeypoint.LEFT_THUMB,
    UnifiedKeypoint.LEFT_HIP: UnifiedKeypoint.RIGHT_HIP,
    UnifiedKeypoint.RIGHT_HIP: UnifiedKeypoint.LEFT_HIP,
    UnifiedKeypoint.LEFT_KNEE: UnifiedKeypoint.RIGHT_KNEE,
    UnifiedKeypoint.RIGHT_KNEE: UnifiedKeypoint.LEFT_KNEE,
    UnifiedKeypoint.LEFT_ANKLE: UnifiedKeypoint.RIGHT_ANKLE,
    UnifiedKeypoint.RIGHT_ANKLE: UnifiedKeypoint.LEFT_ANKLE,
}

# COCO 좌우 대칭 쌍
COCO_SYMMETRIC_PAIRS: dict[CocoKeypoint, CocoKeypoint] = {
    CocoKeypoint.LEFT_EYE: CocoKeypoint.RIGHT_EYE,
    CocoKeypoint.RIGHT_EYE: CocoKeypoint.LEFT_EYE,
    CocoKeypoint.LEFT_EAR: CocoKeypoint.RIGHT_EAR,
    CocoKeypoint.RIGHT_EAR: CocoKeypoint.LEFT_EAR,
    CocoKeypoint.LEFT_SHOULDER: CocoKeypoint.RIGHT_SHOULDER,
    CocoKeypoint.RIGHT_SHOULDER: CocoKeypoint.LEFT_SHOULDER,
    CocoKeypoint.LEFT_ELBOW: CocoKeypoint.RIGHT_ELBOW,
    CocoKeypoint.RIGHT_ELBOW: CocoKeypoint.LEFT_ELBOW,
    CocoKeypoint.LEFT_WRIST: CocoKeypoint.RIGHT_WRIST,
    CocoKeypoint.RIGHT_WRIST: CocoKeypoint.LEFT_WRIST,
    CocoKeypoint.LEFT_HIP: CocoKeypoint.RIGHT_HIP,
    CocoKeypoint.RIGHT_HIP: CocoKeypoint.LEFT_HIP,
    CocoKeypoint.LEFT_KNEE: CocoKeypoint.RIGHT_KNEE,
    CocoKeypoint.RIGHT_KNEE: CocoKeypoint.LEFT_KNEE,
    CocoKeypoint.LEFT_ANKLE: CocoKeypoint.RIGHT_ANKLE,
    CocoKeypoint.RIGHT_ANKLE: CocoKeypoint.LEFT_ANKLE,
}


# ============================================================
# 한글 키포인트 이름
# ============================================================

COCO_KEYPOINT_NAMES_KO: dict[CocoKeypoint, str] = {
    CocoKeypoint.NOSE: "코",
    CocoKeypoint.LEFT_EYE: "왼쪽 눈",
    CocoKeypoint.RIGHT_EYE: "오른쪽 눈",
    CocoKeypoint.LEFT_EAR: "왼쪽 귀",
    CocoKeypoint.RIGHT_EAR: "오른쪽 귀",
    CocoKeypoint.LEFT_SHOULDER: "왼쪽 어깨",
    CocoKeypoint.RIGHT_SHOULDER: "오른쪽 어깨",
    CocoKeypoint.LEFT_ELBOW: "왼쪽 팔꿈치",
    CocoKeypoint.RIGHT_ELBOW: "오른쪽 팔꿈치",
    CocoKeypoint.LEFT_WRIST: "왼쪽 손목",
    CocoKeypoint.RIGHT_WRIST: "오른쪽 손목",
    CocoKeypoint.LEFT_HIP: "왼쪽 엉덩이",
    CocoKeypoint.RIGHT_HIP: "오른쪽 엉덩이",
    CocoKeypoint.LEFT_KNEE: "왼쪽 무릎",
    CocoKeypoint.RIGHT_KNEE: "오른쪽 무릎",
    CocoKeypoint.LEFT_ANKLE: "왼쪽 발목",
    CocoKeypoint.RIGHT_ANKLE: "오른쪽 발목",
}

MEDIAPIPE_KEYPOINT_NAMES_KO: dict[MediaPipeKeypoint, str] = {
    MediaPipeKeypoint.NOSE: "코",
    MediaPipeKeypoint.LEFT_EYE_INNER: "왼쪽 눈 안쪽",
    MediaPipeKeypoint.LEFT_EYE: "왼쪽 눈",
    MediaPipeKeypoint.LEFT_EYE_OUTER: "왼쪽 눈 바깥쪽",
    MediaPipeKeypoint.RIGHT_EYE_INNER: "오른쪽 눈 안쪽",
    MediaPipeKeypoint.RIGHT_EYE: "오른쪽 눈",
    MediaPipeKeypoint.RIGHT_EYE_OUTER: "오른쪽 눈 바깥쪽",
    MediaPipeKeypoint.LEFT_EAR: "왼쪽 귀",
    MediaPipeKeypoint.RIGHT_EAR: "오른쪽 귀",
    MediaPipeKeypoint.MOUTH_LEFT: "입 왼쪽",
    MediaPipeKeypoint.MOUTH_RIGHT: "입 오른쪽",
    MediaPipeKeypoint.LEFT_SHOULDER: "왼쪽 어깨",
    MediaPipeKeypoint.RIGHT_SHOULDER: "오른쪽 어깨",
    MediaPipeKeypoint.LEFT_ELBOW: "왼쪽 팔꿈치",
    MediaPipeKeypoint.RIGHT_ELBOW: "오른쪽 팔꿈치",
    MediaPipeKeypoint.LEFT_WRIST: "왼쪽 손목",
    MediaPipeKeypoint.RIGHT_WRIST: "오른쪽 손목",
    MediaPipeKeypoint.LEFT_PINKY: "왼쪽 새끼손가락",
    MediaPipeKeypoint.RIGHT_PINKY: "오른쪽 새끼손가락",
    MediaPipeKeypoint.LEFT_INDEX: "왼쪽 검지손가락",
    MediaPipeKeypoint.RIGHT_INDEX: "오른쪽 검지손가락",
    MediaPipeKeypoint.LEFT_THUMB: "왼쪽 엄지손가락",
    MediaPipeKeypoint.RIGHT_THUMB: "오른쪽 엄지손가락",
    MediaPipeKeypoint.LEFT_HIP: "왼쪽 엉덩이",
    MediaPipeKeypoint.RIGHT_HIP: "오른쪽 엉덩이",
    MediaPipeKeypoint.LEFT_KNEE: "왼쪽 무릎",
    MediaPipeKeypoint.RIGHT_KNEE: "오른쪽 무릎",
    MediaPipeKeypoint.LEFT_ANKLE: "왼쪽 발목",
    MediaPipeKeypoint.RIGHT_ANKLE: "오른쪽 발목",
    MediaPipeKeypoint.LEFT_HEEL: "왼쪽 발뒤꿈치",
    MediaPipeKeypoint.RIGHT_HEEL: "오른쪽 발뒤꿈치",
    MediaPipeKeypoint.LEFT_FOOT_INDEX: "왼쪽 발끝",
    MediaPipeKeypoint.RIGHT_FOOT_INDEX: "오른쪽 발끝",
}

WHOLEBODY_KEYPOINT_NAMES_KO: dict[int, str] = {
    0: "코", 1: "왼쪽 눈", 2: "오른쪽 눈",
    3: "왼쪽 귀", 4: "오른쪽 귀",
    5: "왼쪽 어깨", 6: "오른쪽 어깨",
    7: "왼쪽 팔꿈치", 8: "오른쪽 팔꿈치",
    9: "왼쪽 손목", 10: "오른쪽 손목",
    11: "왼쪽 엉덩이", 12: "오른쪽 엉덩이",
    13: "왼쪽 무릎", 14: "오른쪽 무릎",
    15: "왼쪽 발목", 16: "오른쪽 발목",
    17: "왼쪽 엄지발가락", 18: "왼쪽 새끼발가락",
    19: "왼쪽 발뒤꿈치", 20: "오른쪽 엄지발가락",
    21: "오른쪽 새끼발가락", 22: "오른쪽 발뒤꿈치",
    91: "왼손 손목", 95: "왼손 엄지 끝",
    99: "왼손 검지 끝", 103: "왼손 중지 끝",
    107: "왼손 약지 끝", 111: "왼손 새끼 끝",
    112: "오른손 손목", 116: "오른손 엄지 끝",
    120: "오른손 검지 끝", 124: "오른손 중지 끝",
    128: "오른손 약지 끝", 132: "오른손 새끼 끝",
}

UNIFIED_KEYPOINT_NAMES_KO: dict[UnifiedKeypoint, str] = {
    UnifiedKeypoint.NOSE: "코",
    UnifiedKeypoint.LEFT_EYE: "왼쪽 눈",
    UnifiedKeypoint.RIGHT_EYE: "오른쪽 눈",
    UnifiedKeypoint.LEFT_EAR: "왼쪽 귀",
    UnifiedKeypoint.RIGHT_EAR: "오른쪽 귀",
    UnifiedKeypoint.LEFT_SHOULDER: "왼쪽 어깨",
    UnifiedKeypoint.RIGHT_SHOULDER: "오른쪽 어깨",
    UnifiedKeypoint.LEFT_ELBOW: "왼쪽 팔꿈치",
    UnifiedKeypoint.RIGHT_ELBOW: "오른쪽 팔꿈치",
    UnifiedKeypoint.LEFT_WRIST: "왼쪽 손목",
    UnifiedKeypoint.RIGHT_WRIST: "오른쪽 손목",
    UnifiedKeypoint.LEFT_INDEX: "왼쪽 검지",
    UnifiedKeypoint.RIGHT_INDEX: "오른쪽 검지",
    UnifiedKeypoint.LEFT_PINKY: "왼쪽 새끼손가락",
    UnifiedKeypoint.RIGHT_PINKY: "오른쪽 새끼손가락",
    UnifiedKeypoint.LEFT_THUMB: "왼쪽 엄지",
    UnifiedKeypoint.RIGHT_THUMB: "오른쪽 엄지",
    UnifiedKeypoint.LEFT_HIP: "왼쪽 엉덩이",
    UnifiedKeypoint.RIGHT_HIP: "오른쪽 엉덩이",
    UnifiedKeypoint.LEFT_KNEE: "왼쪽 무릎",
    UnifiedKeypoint.RIGHT_KNEE: "오른쪽 무릎",
    UnifiedKeypoint.LEFT_ANKLE: "왼쪽 발목",
    UnifiedKeypoint.RIGHT_ANKLE: "오른쪽 발목",
    UnifiedKeypoint.NECK: "목",
    UnifiedKeypoint.PELVIS: "골반 중심",
}


# ============================================================
# 유틸리티 함수
# ============================================================

def get_keypoint_name(
    keypoint: CocoKeypoint | MediaPipeKeypoint | UnifiedKeypoint | WholeBodyKeypoint,
    korean: bool = True,
) -> str:
    """
    키포인트 이름 반환.

    Args:
        keypoint: 키포인트 enum
        korean: True면 한글, False면 영문

    Returns:
        키포인트 이름 문자열

    Example:
        >>> get_keypoint_name(CocoKeypoint.NOSE)
        '코'
        >>> get_keypoint_name(CocoKeypoint.NOSE, korean=False)
        'NOSE'
    """
    if not korean:
        return keypoint.name

    if isinstance(keypoint, CocoKeypoint):
        return COCO_KEYPOINT_NAMES_KO.get(keypoint, keypoint.name)
    elif isinstance(keypoint, WholeBodyKeypoint):
        return WHOLEBODY_KEYPOINT_NAMES_KO.get(int(keypoint), keypoint.name)
    elif isinstance(keypoint, MediaPipeKeypoint):
        return MEDIAPIPE_KEYPOINT_NAMES_KO.get(keypoint, keypoint.name)
    elif isinstance(keypoint, UnifiedKeypoint):
        return UNIFIED_KEYPOINT_NAMES_KO.get(keypoint, keypoint.name)
    else:
        return str(keypoint)


JOINT_DEFINITIONS: dict[str, tuple[UnifiedKeypoint, UnifiedKeypoint, UnifiedKeypoint]] = {
    # 팔 관절
    "left_elbow": (
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.LEFT_ELBOW,
        UnifiedKeypoint.LEFT_WRIST,
    ),
    "right_elbow": (
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.RIGHT_ELBOW,
        UnifiedKeypoint.RIGHT_WRIST,
    ),
    "left_shoulder": (
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.LEFT_ELBOW,
    ),
    "right_shoulder": (
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.RIGHT_ELBOW,
    ),
    # 다리 관절
    "left_knee": (
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.LEFT_KNEE,
        UnifiedKeypoint.LEFT_ANKLE,
    ),
    "right_knee": (
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.RIGHT_KNEE,
        UnifiedKeypoint.RIGHT_ANKLE,
    ),
    "left_hip": (
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.LEFT_KNEE,
    ),
    "right_hip": (
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.RIGHT_KNEE,
    ),
    # 손목
    "left_wrist": (
        UnifiedKeypoint.LEFT_ELBOW,
        UnifiedKeypoint.LEFT_WRIST,
        UnifiedKeypoint.LEFT_INDEX,
    ),
    "right_wrist": (
        UnifiedKeypoint.RIGHT_ELBOW,
        UnifiedKeypoint.RIGHT_WRIST,
        UnifiedKeypoint.RIGHT_INDEX,
    ),
    # 몸통 관절
    "neck": (
        UnifiedKeypoint.NOSE,
        UnifiedKeypoint.NECK,
        UnifiedKeypoint.PELVIS,
    ),
    "torso_left": (
        UnifiedKeypoint.LEFT_SHOULDER,
        UnifiedKeypoint.LEFT_HIP,
        UnifiedKeypoint.LEFT_KNEE,
    ),
    "torso_right": (
        UnifiedKeypoint.RIGHT_SHOULDER,
        UnifiedKeypoint.RIGHT_HIP,
        UnifiedKeypoint.RIGHT_KNEE,
    ),
}


def get_joint_keypoints(joint_name: str) -> tuple[UnifiedKeypoint, UnifiedKeypoint, UnifiedKeypoint]:
    """
    관절을 구성하는 3개의 키포인트 반환.

    관절 각도 계산 시 사용합니다.
    반환 순서: (부모, 관절, 자식)

    Args:
        joint_name: 관절 이름 (예: "left_elbow", "right_knee")

    Returns:
        (부모 키포인트, 관절 키포인트, 자식 키포인트)

    Raises:
        ValueError: 알 수 없는 관절 이름

    Example:
        >>> get_joint_keypoints("left_elbow")
        (UnifiedKeypoint.LEFT_SHOULDER, UnifiedKeypoint.LEFT_ELBOW, UnifiedKeypoint.LEFT_WRIST)
    """
    if joint_name not in JOINT_DEFINITIONS:
        raise ValueError(f"알 수 없는 관절 이름: {joint_name}. 지원: {list(JOINT_DEFINITIONS.keys())}")

    return JOINT_DEFINITIONS[joint_name]


def map_keypoints(
    keypoints: NDArray[np.float32],
    source_format: str,
    target_format: str = "unified",
) -> NDArray[np.float32]:
    """
    키포인트 형식 변환.

    Args:
        keypoints: 소스 키포인트 배열 (N, 3) 또는 (N, 4)
        source_format: 소스 형식 ("coco", "mediapipe")
        target_format: 타겟 형식 ("unified")

    Returns:
        변환된 키포인트 배열

    Example:
        >>> coco_kpts = np.random.rand(17, 3)
        >>> unified_kpts = map_keypoints(coco_kpts, "coco", "unified")
        >>> unified_kpts.shape
        (25, 3)
    """
    if source_format == target_format:
        return keypoints.copy()

    # 결과 배열 초기화
    if target_format == "unified":
        num_keypoints = len(UnifiedKeypoint)
    elif target_format == "coco":
        num_keypoints = len(CocoKeypoint)
    elif target_format == "mediapipe":
        num_keypoints = len(MediaPipeKeypoint)
    elif target_format == "wholebody":
        num_keypoints = 133
    else:
        raise ValueError(f"지원하지 않는 타겟 형식: {target_format}")

    # 입력 차원 확인
    dim = keypoints.shape[1] if len(keypoints.shape) > 1 else 3
    result = np.zeros((num_keypoints, dim), dtype=np.float32)

    # 매핑 수행
    if source_format == "coco" and target_format == "unified":
        for src_kp, dst_kp in COCO_TO_UNIFIED_MAPPING.items():
            if src_kp.value < len(keypoints):
                result[dst_kp.value] = keypoints[src_kp.value]
        # NECK과 PELVIS 계산 (어깨/엉덩이 중점)
        if (keypoints[CocoKeypoint.LEFT_SHOULDER.value][2] > 0 and
                keypoints[CocoKeypoint.RIGHT_SHOULDER.value][2] > 0):
            result[UnifiedKeypoint.NECK.value] = (
                keypoints[CocoKeypoint.LEFT_SHOULDER.value] +
                keypoints[CocoKeypoint.RIGHT_SHOULDER.value]
            ) / 2
        if (keypoints[CocoKeypoint.LEFT_HIP.value][2] > 0 and
                keypoints[CocoKeypoint.RIGHT_HIP.value][2] > 0):
            result[UnifiedKeypoint.PELVIS.value] = (
                keypoints[CocoKeypoint.LEFT_HIP.value] +
                keypoints[CocoKeypoint.RIGHT_HIP.value]
            ) / 2

    elif source_format == "mediapipe" and target_format == "unified":
        for src_kp, dst_kp in MEDIAPIPE_TO_UNIFIED_MAPPING.items():
            if src_kp.value < len(keypoints):
                result[dst_kp.value] = keypoints[src_kp.value]
        # NECK과 PELVIS 계산
        if (keypoints[MediaPipeKeypoint.LEFT_SHOULDER.value][2] > 0 and
                keypoints[MediaPipeKeypoint.RIGHT_SHOULDER.value][2] > 0):
            result[UnifiedKeypoint.NECK.value] = (
                keypoints[MediaPipeKeypoint.LEFT_SHOULDER.value] +
                keypoints[MediaPipeKeypoint.RIGHT_SHOULDER.value]
            ) / 2
        if (keypoints[MediaPipeKeypoint.LEFT_HIP.value][2] > 0 and
                keypoints[MediaPipeKeypoint.RIGHT_HIP.value][2] > 0):
            result[UnifiedKeypoint.PELVIS.value] = (
                keypoints[MediaPipeKeypoint.LEFT_HIP.value] +
                keypoints[MediaPipeKeypoint.RIGHT_HIP.value]
            ) / 2

    elif source_format == "wholebody" and target_format == "unified":
        for wb_idx, uni_idx in WHOLEBODY_TO_UNIFIED_MAPPING.items():
            if wb_idx < len(keypoints):
                result[uni_idx] = keypoints[wb_idx]
        # NECK과 PELVIS 계산
        if (keypoints[5][2] > 0 and keypoints[6][2] > 0):  # 양 어깨
            result[UnifiedKeypoint.NECK.value] = (
                keypoints[5] + keypoints[6]
            ) / 2
        if (keypoints[11][2] > 0 and keypoints[12][2] > 0):  # 양 엉덩이
            result[UnifiedKeypoint.PELVIS.value] = (
                keypoints[11] + keypoints[12]
            ) / 2

    elif source_format == "wholebody" and target_format == "coco":
        for wb_idx, coco_idx in WHOLEBODY_TO_COCO_MAPPING.items():
            if wb_idx < len(keypoints):
                result[coco_idx] = keypoints[wb_idx]

    elif source_format == "unified" and target_format == "coco":
        for unified_kp, coco_kp in UNIFIED_TO_COCO_MAPPING.items():
            if coco_kp is not None and unified_kp.value < len(keypoints):
                result[coco_kp.value] = keypoints[unified_kp.value]

    elif source_format == "unified" and target_format == "mediapipe":
        for unified_kp, mp_kp in UNIFIED_TO_MEDIAPIPE_MAPPING.items():
            if mp_kp is not None and unified_kp.value < len(keypoints):
                result[mp_kp.value] = keypoints[unified_kp.value]

    else:
        raise ValueError(f"지원하지 않는 변환: {source_format} → {target_format}")

    return result


def get_symmetric_keypoint(
    keypoint: CocoKeypoint | MediaPipeKeypoint | UnifiedKeypoint,
) -> CocoKeypoint | MediaPipeKeypoint | UnifiedKeypoint | None:
    """
    대칭 키포인트 반환.

    Args:
        keypoint: 키포인트 enum

    Returns:
        대칭 키포인트 (없으면 None)

    Example:
        >>> get_symmetric_keypoint(UnifiedKeypoint.LEFT_SHOULDER)
        UnifiedKeypoint.RIGHT_SHOULDER
    """
    if isinstance(keypoint, UnifiedKeypoint):
        return UNIFIED_SYMMETRIC_PAIRS.get(keypoint)
    elif isinstance(keypoint, CocoKeypoint):
        return COCO_SYMMETRIC_PAIRS.get(keypoint)
    else:
        return None


def is_keypoint_visible(
    keypoint_data: KeypointData | NDArray | tuple[float, ...],
    confidence_threshold: float = 0.5,
) -> bool:
    """
    키포인트 가시성 확인.

    Args:
        keypoint_data: 키포인트 데이터
        confidence_threshold: 신뢰도 임계값

    Returns:
        가시성 여부

    Example:
        >>> is_keypoint_visible(KeypointData(0.5, 0.5, 0.0, 0.8))
        True
    """
    if isinstance(keypoint_data, KeypointData):
        return keypoint_data.confidence >= confidence_threshold

    if isinstance(keypoint_data, np.ndarray):
        # (x, y, conf) 또는 (x, y, z, conf) 형식
        conf_idx = 2 if len(keypoint_data) == 3 else 3
        return float(keypoint_data[conf_idx]) >= confidence_threshold

    if isinstance(keypoint_data, tuple):
        conf_idx = 2 if len(keypoint_data) == 3 else 3
        return keypoint_data[conf_idx] >= confidence_threshold

    return False


def get_body_part_keypoints(
    part_name: str,
) -> frozenset[UnifiedKeypoint]:
    """
    신체 부위별 키포인트 반환.

    Args:
        part_name: 부위 이름 (예: "head", "left_arm", "torso")

    Returns:
        해당 부위의 키포인트 집합

    Raises:
        ValueError: 알 수 없는 부위 이름

    Example:
        >>> get_body_part_keypoints("left_arm")
        frozenset({UnifiedKeypoint.LEFT_SHOULDER, ...})
    """
    if part_name not in BODY_PARTS:
        raise ValueError(f"알 수 없는 부위 이름: {part_name}. 지원: {list(BODY_PARTS.keys())}")
    return BODY_PARTS[part_name]


def get_basketball_keypoints(
    action_name: str,
) -> frozenset[UnifiedKeypoint]:
    """
    농구 동작별 키포인트 반환.

    Args:
        action_name: 동작 이름 (예: "shooting", "dribbling", "defense")

    Returns:
        해당 동작에 필요한 키포인트 집합

    Raises:
        ValueError: 알 수 없는 동작 이름

    Example:
        >>> get_basketball_keypoints("shooting")
        frozenset({UnifiedKeypoint.RIGHT_SHOULDER, ...})
    """
    if action_name not in BASKETBALL_KEYPOINT_GROUPS:
        raise ValueError(
            f"알 수 없는 동작 이름: {action_name}. 지원: {list(BASKETBALL_KEYPOINT_GROUPS.keys())}"
        )
    return BASKETBALL_KEYPOINT_GROUPS[action_name]


# ============================================================
# 모듈 Export 정의
# ============================================================
__all__ = [
    # =========================================================================
    # 키포인트 열거형
    # =========================================================================
    "CocoKeypoint",
    "MediaPipeKeypoint",
    "UnifiedKeypoint",
    "WholeBodyKeypoint",

    # =========================================================================
    # 키포인트 데이터
    # =========================================================================
    "KeypointData",
    "KeypointPair",

    # =========================================================================
    # 스켈레톤 연결
    # =========================================================================
    "SKELETON_CONNECTIONS",
    "COCO_SKELETON",
    "MEDIAPIPE_SKELETON",
    "WHOLEBODY_BODY_SKELETON",

    # =========================================================================
    # 신체 부위 그룹
    # =========================================================================
    "BODY_PARTS",
    "LEFT_SIDE_KEYPOINTS",
    "RIGHT_SIDE_KEYPOINTS",
    "UPPER_BODY_KEYPOINTS",
    "LOWER_BODY_KEYPOINTS",

    # =========================================================================
    # 농구 특화 그룹
    # =========================================================================
    "BASKETBALL_KEYPOINT_GROUPS",
    "SHOOTING_ARM_KEYPOINTS",
    "DRIBBLING_KEYPOINTS",

    # =========================================================================
    # 모델 간 매핑
    # =========================================================================
    "COCO_TO_UNIFIED_MAPPING",
    "MEDIAPIPE_TO_UNIFIED_MAPPING",
    "WHOLEBODY_TO_COCO_MAPPING",
    "WHOLEBODY_TO_UNIFIED_MAPPING",
    "UNIFIED_TO_COCO_MAPPING",
    "UNIFIED_TO_MEDIAPIPE_MAPPING",

    # =========================================================================
    # 대칭 키포인트
    # =========================================================================
    "UNIFIED_SYMMETRIC_PAIRS",
    "COCO_SYMMETRIC_PAIRS",

    # =========================================================================
    # 한글 키포인트 이름
    # =========================================================================
    "COCO_KEYPOINT_NAMES_KO",
    "MEDIAPIPE_KEYPOINT_NAMES_KO",
    "WHOLEBODY_KEYPOINT_NAMES_KO",
    "UNIFIED_KEYPOINT_NAMES_KO",

    # =========================================================================
    # 관절 정의
    # =========================================================================
    "JOINT_DEFINITIONS",

    # =========================================================================
    # 유틸리티 함수
    # =========================================================================
    "get_keypoint_name",
    "get_joint_keypoints",
    "map_keypoints",
    "get_symmetric_keypoint",
    "is_keypoint_visible",
    "get_body_part_keypoints",
    "get_basketball_keypoints",
]

__version__ = "1.0.0"
