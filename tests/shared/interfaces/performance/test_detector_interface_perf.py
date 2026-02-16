# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/interfaces/performance
파일: test_detector_interface_perf.py
설명: detector_interface.py v1.20.0 성능 테스트
      (Enum 접근, 다국어, BoundingBox, DetectionResult, FrameData,
       DetectorMetrics, IDetector 생명주기, 대량 생성 벤치마크)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import gc
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# 테스트 대상 임포트
# =============================================================================
import numpy as np

from shared.constants.localization import SupportedLanguage
from shared.interfaces.detector_interface import (
    DetectionTarget,
    DetectionState,
    PlayerRole,
    ColorFormat,
    PoseKeypoint,
    BodySegment,
    BoundingBox,
    DetectedObject,
    DetectionResult,
    FrameData,
    DetectorMetrics,
    IDetector,
)


# =============================================================================
# 경량 스텁 클래스 (성능 테스트 전용, 외부 import 방지)
# =============================================================================
class _StubDetector(IDetector[dict]):
    """IDetector 경량 스텁 (성능 측정용)."""

    def __init__(self) -> None:
        self._state = DetectionState.UNINITIALIZED
        self._metrics = DetectorMetrics()
        self._targets = [DetectionTarget.PLAYER, DetectionTarget.BALL]

    @property
    def name(self) -> str:
        return "PerfStubDetector"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def supported_targets(self) -> list[DetectionTarget]:
        return self._targets

    @property
    def state(self) -> DetectionState:
        return self._state

    @property
    def metrics(self) -> DetectorMetrics:
        return self._metrics

    def initialize(self, config: dict) -> None:
        self._state = DetectionState.READY

    def detect(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
        targets: list[DetectionTarget] | None = None,
    ) -> DetectionResult:
        obj = DetectedObject(
            target_type=DetectionTarget.PLAYER,
            bounding_box=BoundingBox(x=100.0, y=50.0, width=80.0, height=200.0, confidence=0.92),
        )
        return DetectionResult.success_result(
            objects=[obj],
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            processing_time_ms=5.0,
        )

    def reset(self) -> None:
        self._state = DetectionState.UNINITIALIZED

    def shutdown(self) -> None:
        self._state = DetectionState.SHUTDOWN


# =============================================================================
# 성능 테스트 하네스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.3f}us ({ratio:.1f}% of {limit_us:.0f}us)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.3f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.3f}us (limit: {limit_us:.0f}us)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n  실패:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (마이크로초/반복)."""
    gc.disable()
    try:
        # 워밍업
        warmup = min(iterations, 1000)
        for _ in range(warmup):
            func()

        # 측정
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns → us
    finally:
        gc.enable()


def bench(r: PerfResult, name: str, func, limit_us: float,
          iterations: int = 10000) -> float:
    """벤치마크 실행 헬퍼."""
    elapsed = measure(func, iterations)
    if elapsed < limit_us:
        r.ok(name, elapsed, limit_us)
    else:
        r.fail(name, elapsed, limit_us)
    return elapsed


# =============================================================================
# 테스트용 프레임 + 공통 데이터
# =============================================================================
_FRAME_480 = np.zeros((480, 640, 3), dtype=np.uint8)
_FRAME_SMALL = np.zeros((10, 10, 3), dtype=np.uint8)
_FRAME_GRAY = np.zeros((480, 640), dtype=np.uint8)

_BOX_A = BoundingBox(x=100.0, y=50.0, width=80.0, height=200.0, confidence=0.95)
_BOX_B = BoundingBox(x=120.0, y=60.0, width=80.0, height=200.0, confidence=0.88)
_BOX_NO_OVERLAP = BoundingBox(x=500.0, y=500.0, width=50.0, height=50.0, confidence=0.75)


# =============================================================================
# [1] DetectionTarget 접근 성능
# =============================================================================
def test_detection_target_access(r: PerfResult) -> None:
    """DetectionTarget Enum 멤버 접근 성능."""
    # 멤버 접근
    bench(r, "DetectionTarget.BALL 접근",
          lambda: DetectionTarget.BALL, 1.0, 100000)

    # .value 접근
    target = DetectionTarget.PLAYER
    bench(r, "DetectionTarget.value 접근",
          lambda: target.value, 1.0, 100000)

    # __str__ 호출
    bench(r, "str(DetectionTarget) 호출",
          lambda: str(target), 2.0, 100000)

    # is_person 프로퍼티
    bench(r, "DetectionTarget.is_person (True)",
          lambda: target.is_person, 2.0, 100000)

    # is_person 프로퍼티 (False 케이스)
    target_ball = DetectionTarget.BALL
    bench(r, "DetectionTarget.is_person (False)",
          lambda: target_ball.is_person, 2.0, 100000)

    # is_court_element 프로퍼티
    target_court = DetectionTarget.COURT
    bench(r, "DetectionTarget.is_court_element (True)",
          lambda: target_court.is_court_element, 2.0, 100000)

    # is_court_element 프로퍼티 (False)
    bench(r, "DetectionTarget.is_court_element (False)",
          lambda: target.is_court_element, 2.0, 100000)


# =============================================================================
# [2] DetectionTarget.get_name() 다국어 성능
# =============================================================================
def test_detection_target_get_name(r: PerfResult) -> None:
    """DetectionTarget.get_name() 다국어 조회 성능 (모듈 레벨 캐시)."""
    target = DetectionTarget.BALL

    # 한국어 (기본값)
    bench(r, "get_name() 한국어 (기본)",
          lambda: target.get_name(), 5.0, 100000)

    # 영어
    bench(r, "get_name(EN)",
          lambda: target.get_name(SupportedLanguage.EN), 5.0, 100000)

    # 일본어
    bench(r, "get_name(JA)",
          lambda: target.get_name(SupportedLanguage.JA), 5.0, 100000)

    # to_korean 프로퍼티
    bench(r, "to_korean 프로퍼티",
          lambda: target.to_korean, 5.0, 100000)

    # 모든 타겟 get_name 순회 (8개)
    bench(r, "전체 8개 타겟 get_name(KO) 순회",
          lambda: [t.get_name(SupportedLanguage.KO) for t in DetectionTarget],
          30.0, 50000)


# =============================================================================
# [3] DetectionState 접근 + get_name 성능
# =============================================================================
def test_detection_state(r: PerfResult) -> None:
    """DetectionState Enum 접근 및 get_name 성능."""
    state = DetectionState.READY

    # 멤버 접근
    bench(r, "DetectionState.READY 접근",
          lambda: DetectionState.READY, 1.0, 100000)

    # .value 접근
    bench(r, "DetectionState.value 접근",
          lambda: state.value, 1.0, 100000)

    # is_active 프로퍼티
    bench(r, "DetectionState.is_active (True)",
          lambda: state.is_active, 2.0, 100000)

    # is_processing 프로퍼티
    detecting = DetectionState.DETECTING
    bench(r, "DetectionState.is_processing (True)",
          lambda: detecting.is_processing, 2.0, 100000)

    # is_error 프로퍼티
    bench(r, "DetectionState.is_error (False)",
          lambda: state.is_error, 1.0, 100000)

    # is_terminated 프로퍼티
    shutdown = DetectionState.SHUTDOWN
    bench(r, "DetectionState.is_terminated (True)",
          lambda: shutdown.is_terminated, 2.0, 100000)

    # get_name KO
    bench(r, "DetectionState.get_name(KO)",
          lambda: state.get_name(SupportedLanguage.KO), 5.0, 100000)

    # 전체 6개 상태 순회 get_name
    bench(r, "전체 6개 상태 get_name(KO) 순회",
          lambda: [s.get_name(SupportedLanguage.KO) for s in DetectionState],
          30.0, 50000)


# =============================================================================
# [4] PlayerRole 성능
# =============================================================================
def test_player_role(r: PerfResult) -> None:
    """PlayerRole Enum 접근, to_korean, from_class_id, to_class_id 성능."""
    role = PlayerRole.PLAYER

    # to_korean
    bench(r, "PlayerRole.to_korean",
          lambda: role.to_korean, 5.0, 100000)

    # from_class_id (유효)
    bench(r, "PlayerRole.from_class_id(0)",
          lambda: PlayerRole.from_class_id(0), 2.0, 100000)

    # from_class_id (유효하지 않은 ID → UNKNOWN 폴백)
    bench(r, "PlayerRole.from_class_id(99) → UNKNOWN",
          lambda: PlayerRole.from_class_id(99), 2.0, 100000)

    # to_class_id
    bench(r, "PlayerRole.to_class_id()",
          lambda: role.to_class_id(), 2.0, 100000)

    # is_on_court 프로퍼티
    bench(r, "PlayerRole.is_on_court (True)",
          lambda: role.is_on_court, 2.0, 100000)

    # get_name EN
    bench(r, "PlayerRole.get_name(EN)",
          lambda: role.get_name(SupportedLanguage.EN), 5.0, 100000)


# =============================================================================
# [5] ColorFormat 성능
# =============================================================================
def test_color_format(r: PerfResult) -> None:
    """ColorFormat Enum 접근, to_korean, channel_count, has_alpha 성능."""
    fmt_bgr = ColorFormat.BGR
    fmt_rgba = ColorFormat.RGBA

    # to_korean
    bench(r, "ColorFormat.to_korean (BGR)",
          lambda: fmt_bgr.to_korean, 5.0, 100000)

    # channel_count
    bench(r, "ColorFormat.channel_count (BGR → 3)",
          lambda: fmt_bgr.channel_count, 2.0, 100000)

    # channel_count (RGBA → 4)
    bench(r, "ColorFormat.channel_count (RGBA → 4)",
          lambda: fmt_rgba.channel_count, 2.0, 100000)

    # has_alpha (True)
    bench(r, "ColorFormat.has_alpha (RGBA → True)",
          lambda: fmt_rgba.has_alpha, 2.0, 100000)

    # has_alpha (False)
    bench(r, "ColorFormat.has_alpha (BGR → False)",
          lambda: fmt_bgr.has_alpha, 2.0, 100000)

    # is_grayscale
    fmt_gray = ColorFormat.GRAY
    bench(r, "ColorFormat.is_grayscale (GRAY → True)",
          lambda: fmt_gray.is_grayscale, 1.0, 100000)


# =============================================================================
# [6] PoseKeypoint 성능
# =============================================================================
def test_pose_keypoint(r: PerfResult) -> None:
    """PoseKeypoint Enum 접근, to_korean, coco_index, is_upper_body 성능."""
    kp = PoseKeypoint.LEFT_SHOULDER

    # to_korean
    bench(r, "PoseKeypoint.to_korean (LEFT_SHOULDER)",
          lambda: kp.to_korean, 5.0, 100000)

    # coco_index (COCO 키포인트)
    bench(r, "PoseKeypoint.coco_index (LEFT_SHOULDER → 5)",
          lambda: kp.coco_index, 2.0, 100000)

    # coco_index (확장 키포인트 → None)
    kp_ext = PoseKeypoint.NECK
    bench(r, "PoseKeypoint.coco_index (NECK → None)",
          lambda: kp_ext.coco_index, 2.0, 100000)

    # is_coco_keypoint
    bench(r, "PoseKeypoint.is_coco_keypoint (True)",
          lambda: kp.is_coco_keypoint, 3.0, 100000)

    # is_extended (확장 키포인트)
    bench(r, "PoseKeypoint.is_extended (NECK → True)",
          lambda: kp_ext.is_extended, 3.0, 100000)

    # is_upper_body
    bench(r, "PoseKeypoint.is_upper_body (LEFT_SHOULDER → True)",
          lambda: kp.is_upper_body, 2.0, 100000)

    # is_lower_body
    kp_knee = PoseKeypoint.LEFT_KNEE
    bench(r, "PoseKeypoint.is_lower_body (LEFT_KNEE → True)",
          lambda: kp_knee.is_lower_body, 2.0, 100000)

    # get_name EN
    bench(r, "PoseKeypoint.get_name(EN)",
          lambda: kp.get_name(SupportedLanguage.EN), 5.0, 100000)


# =============================================================================
# [7] BodySegment 성능
# =============================================================================
def test_body_segment(r: PerfResult) -> None:
    """BodySegment Enum 접근, to_korean, is_upper_body, is_arm 성능."""
    seg_arm = BodySegment.LEFT_UPPER_ARM
    seg_leg = BodySegment.LEFT_THIGH

    # to_korean
    bench(r, "BodySegment.to_korean (LEFT_UPPER_ARM)",
          lambda: seg_arm.to_korean, 5.0, 100000)

    # is_upper_body
    bench(r, "BodySegment.is_upper_body (LEFT_UPPER_ARM → True)",
          lambda: seg_arm.is_upper_body, 2.0, 100000)

    # is_lower_body
    bench(r, "BodySegment.is_lower_body (LEFT_THIGH → True)",
          lambda: seg_leg.is_lower_body, 2.0, 100000)

    # is_arm
    bench(r, "BodySegment.is_arm (LEFT_UPPER_ARM → True)",
          lambda: seg_arm.is_arm, 2.0, 100000)

    # is_arm (False)
    bench(r, "BodySegment.is_arm (LEFT_THIGH → False)",
          lambda: seg_leg.is_arm, 2.0, 100000)

    # is_leg
    bench(r, "BodySegment.is_leg (LEFT_THIGH → True)",
          lambda: seg_leg.is_leg, 2.0, 100000)

    # get_name EN
    bench(r, "BodySegment.get_name(EN)",
          lambda: seg_arm.get_name(SupportedLanguage.EN), 5.0, 100000)


# =============================================================================
# [8] BoundingBox 성능
# =============================================================================
def test_bounding_box(r: PerfResult) -> None:
    """BoundingBox 생성, 프로퍼티, IoU, contains_point, expand 성능."""
    # 생성
    bench(r, "BoundingBox() 생성",
          lambda: BoundingBox(x=100.0, y=50.0, width=80.0, height=200.0, confidence=0.95),
          5.0, 100000)

    # center 프로퍼티
    bench(r, "BoundingBox.center 접근",
          lambda: _BOX_A.center, 2.0, 100000)

    # area 프로퍼티
    bench(r, "BoundingBox.area 접근",
          lambda: _BOX_A.area, 1.0, 100000)

    # xyxy 프로퍼티
    bench(r, "BoundingBox.xyxy 접근",
          lambda: _BOX_A.xyxy, 2.0, 100000)

    # xywh 프로퍼티
    bench(r, "BoundingBox.xywh 접근",
          lambda: _BOX_A.xywh, 2.0, 100000)

    # x_center, y_center 개별 접근
    bench(r, "BoundingBox.x_center 접근",
          lambda: _BOX_A.x_center, 1.0, 100000)

    bench(r, "BoundingBox.y_center 접근",
          lambda: _BOX_A.y_center, 1.0, 100000)

    # IoU (겹치는 박스)
    bench(r, "BoundingBox.iou() 겹침",
          lambda: _BOX_A.iou(_BOX_B), 5.0, 100000)

    # IoU (겹치지 않는 박스)
    bench(r, "BoundingBox.iou() 비겹침 → 0.0",
          lambda: _BOX_A.iou(_BOX_NO_OVERLAP), 5.0, 100000)

    # contains_point
    bench(r, "BoundingBox.contains_point() (내부)",
          lambda: _BOX_A.contains_point(120.0, 100.0), 2.0, 100000)

    bench(r, "BoundingBox.contains_point() (외부)",
          lambda: _BOX_A.contains_point(0.0, 0.0), 2.0, 100000)

    # expand
    bench(r, "BoundingBox.expand(0.2) 확장",
          lambda: _BOX_A.expand(0.2), 10.0, 100000)

    # to_normalized
    bench(r, "BoundingBox.to_normalized(1920, 1080)",
          lambda: _BOX_A.to_normalized(1920, 1080), 10.0, 100000)


# =============================================================================
# [9] DetectionResult 성능
# =============================================================================
def test_detection_result(r: PerfResult) -> None:
    """DetectionResult 팩토리, 필터링, count 성능."""
    # 테스트용 DetectedObject 목록
    _objs = [
        DetectedObject(
            target_type=DetectionTarget.PLAYER,
            bounding_box=BoundingBox(x=100.0, y=50.0, width=80.0, height=200.0, confidence=0.92),
        ),
        DetectedObject(
            target_type=DetectionTarget.PLAYER,
            bounding_box=BoundingBox(x=300.0, y=60.0, width=70.0, height=190.0, confidence=0.88),
        ),
        DetectedObject(
            target_type=DetectionTarget.BALL,
            bounding_box=BoundingBox(x=200.0, y=150.0, width=30.0, height=30.0, confidence=0.95),
        ),
        DetectedObject(
            target_type=DetectionTarget.REFEREE,
            bounding_box=BoundingBox(x=400.0, y=70.0, width=60.0, height=180.0, confidence=0.85),
        ),
    ]

    # success_result 팩토리
    bench(r, "DetectionResult.success_result() 팩토리",
          lambda: DetectionResult.success_result(
              objects=_objs, frame_index=0, timestamp_ms=33.3, processing_time_ms=5.0,
          ), 10.0, 50000)

    # failure_result 팩토리
    bench(r, "DetectionResult.failure_result() 팩토리",
          lambda: DetectionResult.failure_result(error_message="탐지 실패"),
          10.0, 50000)

    # filter_by_type
    result = DetectionResult.success_result(objects=_objs, frame_index=0)
    bench(r, "DetectionResult.filter_by_type(PLAYER)",
          lambda: result.filter_by_type(DetectionTarget.PLAYER), 5.0, 100000)

    # filter_by_confidence
    bench(r, "DetectionResult.filter_by_confidence(0.90)",
          lambda: result.filter_by_confidence(0.90), 5.0, 100000)

    # count 프로퍼티
    bench(r, "DetectionResult.count 프로퍼티",
          lambda: result.count, 1.0, 100000)

    # count_by_type
    bench(r, "DetectionResult.count_by_type(PLAYER)",
          lambda: result.count_by_type(DetectionTarget.PLAYER), 5.0, 100000)

    # 직접 생성 (최소 인수)
    bench(r, "DetectionResult(success=True) 최소 생성",
          lambda: DetectionResult(success=True), 5.0, 50000)


# =============================================================================
# [10] FrameData.from_array 성능
# =============================================================================
def test_frame_data(r: PerfResult) -> None:
    """FrameData 생성, from_array, 프로퍼티 접근 성능."""
    # from_array (480x640 BGR)
    bench(r, "FrameData.from_array(480x640 BGR)",
          lambda: FrameData.from_array(
              frame=_FRAME_480, frame_index=0, timestamp_ms=33.3,
              color_format=ColorFormat.BGR, fps=30.0,
          ), 20.0, 50000)

    # from_array (10x10 작은 프레임)
    bench(r, "FrameData.from_array(10x10 BGR)",
          lambda: FrameData.from_array(
              frame=_FRAME_SMALL, frame_index=0, timestamp_ms=0.0,
          ), 20.0, 50000)

    # from_array (그레이스케일)
    bench(r, "FrameData.from_array(480x640 GRAY)",
          lambda: FrameData.from_array(
              frame=_FRAME_GRAY, frame_index=0, timestamp_ms=0.0,
              color_format=ColorFormat.GRAY,
          ), 20.0, 50000)

    # 프로퍼티 접근
    fd = FrameData.from_array(frame=_FRAME_480, frame_index=42, timestamp_ms=1400.0, fps=30.0)

    bench(r, "FrameData.resolution 접근",
          lambda: fd.resolution, 1.0, 100000)

    bench(r, "FrameData.shape 접근",
          lambda: fd.shape, 1.0, 100000)

    bench(r, "FrameData.size_bytes 접근",
          lambda: fd.size_bytes, 2.0, 100000)

    bench(r, "FrameData.aspect_ratio 접근",
          lambda: fd.aspect_ratio, 2.0, 100000)

    bench(r, "FrameData.timestamp_sec 접근",
          lambda: fd.timestamp_sec, 1.0, 100000)

    bench(r, "FrameData.is_grayscale 접근 (False)",
          lambda: fd.is_grayscale, 1.0, 100000)

    bench(r, "FrameData.is_valid 접근",
          lambda: fd.is_valid, 2.0, 100000)


# =============================================================================
# [11] DetectorMetrics.update 성능
# =============================================================================
def test_detector_metrics(r: PerfResult) -> None:
    """DetectorMetrics 생성, update(성공/실패) 성능."""
    # 기본 생성
    bench(r, "DetectorMetrics() 생성",
          lambda: DetectorMetrics(), 5.0, 50000)

    # 성공 결과 업데이트 (객체 포함)
    _success_objs = [
        DetectedObject(
            target_type=DetectionTarget.PLAYER,
            bounding_box=BoundingBox(x=100.0, y=50.0, width=80.0, height=200.0, confidence=0.92),
        ),
        DetectedObject(
            target_type=DetectionTarget.BALL,
            bounding_box=BoundingBox(x=200.0, y=150.0, width=30.0, height=30.0, confidence=0.95),
        ),
    ]
    _success_result = DetectionResult.success_result(
        objects=_success_objs, frame_index=0, processing_time_ms=5.0,
    )

    m1 = DetectorMetrics()
    bench(r, "DetectorMetrics.update(성공, 2객체)",
          lambda: m1.update(_success_result), 5.0, 50000)

    # 실패 결과 업데이트
    _fail_result = DetectionResult.failure_result(error_message="프레임 처리 실패")
    m2 = DetectorMetrics()
    bench(r, "DetectorMetrics.update(실패)",
          lambda: m2.update(_fail_result), 5.0, 50000)

    # 100회 업데이트 후 프로퍼티 접근
    m3 = DetectorMetrics()
    for _ in range(100):
        m3.update(_success_result)
    bench(r, "total_frames_processed (100회 후)",
          lambda: m3.total_frames_processed, 1.0, 100000)

    bench(r, "average_processing_time_ms (100회 후)",
          lambda: m3.average_processing_time_ms, 1.0, 100000)

    bench(r, "current_fps (100회 후)",
          lambda: m3.current_fps, 1.0, 100000)

    bench(r, "average_confidence (100회 후)",
          lambda: m3.average_confidence, 1.0, 100000)


# =============================================================================
# [12] IDetector.validate_frame 성능
# =============================================================================
def test_validate_frame(r: PerfResult) -> None:
    """IDetector.validate_frame() 유효/무효 프레임 성능."""
    detector = _StubDetector()

    # 유효한 프레임 (480x640 BGR)
    bench(r, "validate_frame(480x640 BGR) 유효",
          lambda: detector.validate_frame(_FRAME_480), 3.0, 100000)

    # 유효한 프레임 (10x10 BGR)
    bench(r, "validate_frame(10x10 BGR) 유효",
          lambda: detector.validate_frame(_FRAME_SMALL), 3.0, 100000)

    # 무효: 그레이스케일 (2D ndim)
    bench(r, "validate_frame(2D grayscale) 무효",
          lambda: detector.validate_frame(_FRAME_GRAY), 3.0, 100000)

    # 무효: None
    bench(r, "validate_frame(None) 무효",
          lambda: detector.validate_frame(None), 1.0, 100000)


# =============================================================================
# [13] 생명주기 성능 (생성 → 초기화 → 탐지 → 종료)
# =============================================================================
def test_lifecycle(r: PerfResult) -> None:
    """_StubDetector 생명주기 (생성→초기화→탐지→종료) 성능."""
    # 스텁 생성
    bench(r, "_StubDetector() 생성",
          lambda: _StubDetector(), 15.0, 50000)

    # 초기화
    det = _StubDetector()
    bench(r, "initialize({}) 호출",
          lambda: det.initialize({}), 2.0, 100000)

    # 탐지 (detect 호출)
    det.initialize({})
    bench(r, "detect(frame) 호출",
          lambda: det.detect(_FRAME_SMALL, 0, 0.0), 20.0, 50000)

    # 종료
    bench(r, "shutdown() 호출",
          lambda: det.shutdown(), 2.0, 100000)

    # 전체 사이클 (생성 → 초기화 → 탐지 → 종료)
    def full_cycle():
        d = _StubDetector()
        d.initialize({})
        d.detect(_FRAME_SMALL, 0, 0.0)
        d.shutdown()

    bench(r, "전체 생명주기 (생성→초기화→탐지→종료)",
          full_cycle, 50.0, 50000)

    # 상태 전이 확인 접근
    det2 = _StubDetector()
    det2.initialize({})
    bench(r, "state 프로퍼티 접근",
          lambda: det2.state, 1.0, 100000)

    bench(r, "metrics 프로퍼티 접근",
          lambda: det2.metrics, 1.0, 100000)

    bench(r, "supported_targets 프로퍼티 접근",
          lambda: det2.supported_targets, 1.0, 100000)


# =============================================================================
# [14] 대량 객체 생성 성능
# =============================================================================
def test_bulk_creation(r: PerfResult) -> None:
    """대량 객체 생성 성능 (스루풋 확인)."""
    # 1000개 BoundingBox 생성
    def create_1000_bbox():
        return [
            BoundingBox(
                x=float(i * 10), y=float(i * 5),
                width=80.0, height=200.0,
                confidence=0.9 + (i % 10) * 0.01,
            )
            for i in range(1000)
        ]

    elapsed_bbox = measure(create_1000_bbox, 100)
    r.info(f"1000개 BoundingBox 생성: {elapsed_bbox:.1f}us (={elapsed_bbox/1000:.3f}us/개)")
    if elapsed_bbox < 20000.0:  # 20ms 이내
        r.ok("1000개 BoundingBox 생성 (< 20ms)", elapsed_bbox, 20000.0)
    else:
        r.fail("1000개 BoundingBox 생성 (< 20ms)", elapsed_bbox, 20000.0)

    # 1000개 DetectedObject 생성
    def create_1000_detected():
        targets = list(DetectionTarget)
        return [
            DetectedObject(
                target_type=targets[i % len(targets)],
                bounding_box=BoundingBox(
                    x=float(i * 10), y=float(i * 5),
                    width=80.0, height=200.0,
                    confidence=0.85 + (i % 15) * 0.01,
                ),
                object_id=i,
            )
            for i in range(1000)
        ]

    elapsed_det = measure(create_1000_detected, 100)
    r.info(f"1000개 DetectedObject 생성: {elapsed_det:.1f}us (={elapsed_det/1000:.3f}us/개)")
    if elapsed_det < 20000.0:  # 20ms 이내
        r.ok("1000개 DetectedObject 생성 (< 20ms)", elapsed_det, 20000.0)
    else:
        r.fail("1000개 DetectedObject 생성 (< 20ms)", elapsed_det, 20000.0)

    # 1000개 DetectionResult 생성 (각 빈 결과)
    def create_1000_result():
        return [
            DetectionResult.success_result(
                objects=[], frame_index=i, processing_time_ms=5.0,
            )
            for i in range(1000)
        ]

    elapsed_res = measure(create_1000_result, 100)
    r.info(f"1000개 DetectionResult 생성: {elapsed_res:.1f}us (={elapsed_res/1000:.3f}us/개)")
    if elapsed_res < 15000.0:  # 15ms 이내
        r.ok("1000개 DetectionResult 생성 (< 15ms)", elapsed_res, 15000.0)
    else:
        r.fail("1000개 DetectionResult 생성 (< 15ms)", elapsed_res, 15000.0)

    # 1000개 DetectorMetrics 업데이트
    m = DetectorMetrics()
    _objs_for_update = [
        DetectedObject(
            target_type=DetectionTarget.PLAYER,
            bounding_box=BoundingBox(x=100.0, y=50.0, width=80.0, height=200.0, confidence=0.92),
        ),
    ]
    _results_for_update = [
        DetectionResult.success_result(
            objects=_objs_for_update, frame_index=i, processing_time_ms=5.0,
        )
        for i in range(1000)
    ]

    def update_1000():
        for result in _results_for_update:
            m.update(result)

    elapsed_upd = measure(update_1000, 100)
    r.info(f"1000개 DetectorMetrics.update: {elapsed_upd:.1f}us (={elapsed_upd/1000:.3f}us/개)")
    if elapsed_upd < 15000.0:  # 15ms 이내
        r.ok("1000개 DetectorMetrics.update (< 15ms)", elapsed_upd, 15000.0)
    else:
        r.fail("1000개 DetectorMetrics.update (< 15ms)", elapsed_upd, 15000.0)

    # 대량 IoU 계산 (1000쌍)
    boxes = create_1000_bbox()

    def iou_1000():
        for i in range(999):
            boxes[i].iou(boxes[i + 1])

    elapsed_iou = measure(iou_1000, 100)
    r.info(f"1000쌍 IoU 계산: {elapsed_iou:.1f}us (={elapsed_iou/1000:.3f}us/쌍)")
    if elapsed_iou < 15000.0:  # 15ms 이내
        r.ok("1000쌍 IoU 계산 (< 15ms)", elapsed_iou, 15000.0)
    else:
        r.fail("1000쌍 IoU 계산 (< 15ms)", elapsed_iou, 15000.0)

    # 대량 filter_by_type (100객체 결과에서)
    mixed_objs = create_1000_detected()[:100]
    big_result = DetectionResult.success_result(objects=mixed_objs, frame_index=0)

    bench(r, "filter_by_type (100객체 → PLAYER)",
          lambda: big_result.filter_by_type(DetectionTarget.PLAYER), 20.0, 50000)

    bench(r, "filter_by_confidence (100객체, >=0.90)",
          lambda: big_result.filter_by_confidence(0.90), 20.0, 50000)


# =============================================================================
# 메인
# =============================================================================
def main() -> int:
    r = PerfResult()
    print("\n" + "=" * 60)
    print("  detector_interface.py v1.20.0 성능 테스트")
    print("=" * 60)

    print("\n--- [1] DetectionTarget 접근 성능 ---")
    test_detection_target_access(r)

    print("\n--- [2] DetectionTarget.get_name() 다국어 성능 ---")
    test_detection_target_get_name(r)

    print("\n--- [3] DetectionState 접근 + get_name 성능 ---")
    test_detection_state(r)

    print("\n--- [4] PlayerRole 성능 ---")
    test_player_role(r)

    print("\n--- [5] ColorFormat 성능 ---")
    test_color_format(r)

    print("\n--- [6] PoseKeypoint 성능 ---")
    test_pose_keypoint(r)

    print("\n--- [7] BodySegment 성능 ---")
    test_body_segment(r)

    print("\n--- [8] BoundingBox 성능 ---")
    test_bounding_box(r)

    print("\n--- [9] DetectionResult 성능 ---")
    test_detection_result(r)

    print("\n--- [10] FrameData.from_array 성능 ---")
    test_frame_data(r)

    print("\n--- [11] DetectorMetrics.update 성능 ---")
    test_detector_metrics(r)

    print("\n--- [12] IDetector.validate_frame 성능 ---")
    test_validate_frame(r)

    print("\n--- [13] 생명주기 성능 ---")
    test_lifecycle(r)

    print("\n--- [14] 대량 객체 생성 ---")
    test_bulk_creation(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(main())
