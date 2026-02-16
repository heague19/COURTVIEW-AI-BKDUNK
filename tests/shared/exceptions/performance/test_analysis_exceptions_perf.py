# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/exceptions/performance
파일: test_analysis_exceptions_perf.py
설명: analysis_exceptions.py 성능 테스트 (39개 클래스 생성/직렬화 벤치마크)

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
from shared.exceptions.analysis_exceptions import (
    AnalysisException,
    VideoException,
    VideoFormatException,
    VideoSizeException,
    VideoDurationException,
    VideoDownloadException,
    VideoCorruptedException,
    FrameExtractionException,
    DetectionException,
    PersonNotDetectedException,
    BallNotDetectedException,
    CourtNotDetectedException,
    HoopNotDetectedException,
    MultiplePersonsDetectedException,
    LowConfidenceDetectionException,
    PoseEstimationException,
    InsufficientKeypointsException,
    OcclusionDetectedException,
    MotionAnalysisException,
    ShootingNotDetectedException,
    DribblingNotDetectedException,
    InsufficientDataException,
    ModelException,
    ModelLoadException,
    ModelInferenceException,
    ModelNotFoundException,
    BiomechanicsException,
    JointAngleCalculationException,
    ForceCalculationException,
    GameAnalysisException,
    TeamDetectionException,
    ScoreDetectionException,
    PlayDetectionException,
    RefereeException,
    ViolationDetectionException,
    FoulDetectionException,
    FeedbackGenerationException,
    TemplateNotFoundException,
    RecommendationException,
)


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
        warmup = min(iterations, 1000)
        for _ in range(warmup):
            func()

        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns → us
    finally:
        gc.enable()


def bench(r: PerfResult, name: str, func, limit_us: float, iters: int = 30000) -> None:
    """벤치마크 헬퍼: 측정 + pass/fail 판정."""
    elapsed = measure(func, iters)
    if elapsed < limit_us:
        r.ok(name, elapsed, limit_us)
    else:
        r.fail(name, elapsed, limit_us)


# =============================================================================
# [1] 도메인 기반 클래스 생성 성능
# =============================================================================
def test_domain_base_creation(r: PerfResult) -> None:
    """도메인 기반 클래스 (10개) 기본 생성 성능."""
    limit = 60.0  # us

    bench(r, "AnalysisException()", lambda: AnalysisException(), limit)
    bench(r, "VideoException()", lambda: VideoException(), limit)
    bench(r, "DetectionException()", lambda: DetectionException(), limit)
    bench(r, "PoseEstimationException()", lambda: PoseEstimationException(), limit)
    bench(r, "MotionAnalysisException()", lambda: MotionAnalysisException(), limit)
    bench(r, "ModelException()", lambda: ModelException(), limit)
    bench(r, "BiomechanicsException()", lambda: BiomechanicsException(), limit)
    bench(r, "GameAnalysisException()", lambda: GameAnalysisException(), limit)
    bench(r, "RefereeException()", lambda: RefereeException(), limit)
    bench(r, "FeedbackGenerationException()", lambda: FeedbackGenerationException(), limit)


# =============================================================================
# [2] 비디오 예외 생성 성능
# =============================================================================
def test_video_creation(r: PerfResult) -> None:
    """비디오 예외 클래스 (6개) 생성 성능."""
    limit = 80.0  # us (인수 처리 포함)

    bench(r, "VideoFormatException('wmv')",
          lambda: VideoFormatException("wmv"), limit)
    bench(r, "VideoSizeException(500M, 200M)",
          lambda: VideoSizeException(500_000_000, 200_000_000), limit)
    bench(r, "VideoDurationException(3600, 1800)",
          lambda: VideoDurationException(3600.0, 1800.0), limit)
    bench(r, "VideoDownloadException(url)",
          lambda: VideoDownloadException("https://example.com/v.mp4", 503), limit)
    bench(r, "VideoCorruptedException(path)",
          lambda: VideoCorruptedException("/tmp/bad.mp4", "header"), limit)
    bench(r, "FrameExtractionException(42, 1000)",
          lambda: FrameExtractionException(42, 1000), limit)


# =============================================================================
# [3] 감지 예외 생성 성능
# =============================================================================
def test_detection_creation(r: PerfResult) -> None:
    """감지 예외 클래스 (6개) 생성 성능."""
    limit = 80.0

    bench(r, "PersonNotDetectedException(range)",
          lambda: PersonNotDetectedException((0, 100)), limit)
    bench(r, "BallNotDetectedException(full)",
          lambda: BallNotDetectedException((0, 50), 25, 5), limit)
    bench(r, "CourtNotDetectedException(range)",
          lambda: CourtNotDetectedException((0, 200)), limit)
    bench(r, "HoopNotDetectedException()",
          lambda: HoopNotDetectedException(), limit)
    bench(r, "MultiplePersonsDetectedException(3, 50)",
          lambda: MultiplePersonsDetectedException(3, 50), limit)
    bench(r, "LowConfidenceDetectionException(.35,.7,'ball')",
          lambda: LowConfidenceDetectionException(0.35, 0.7, "ball", 100), limit)


# =============================================================================
# [4] 포즈/동작/모델 예외 생성 성능
# =============================================================================
def test_pose_motion_model_creation(r: PerfResult) -> None:
    """포즈/동작/모델 예외 생성 성능."""
    limit = 80.0

    bench(r, "InsufficientKeypointsException(10, 17)",
          lambda: InsufficientKeypointsException(10, 17, ["ankle"], 42), limit)
    bench(r, "OcclusionDetectedException(['arm'])",
          lambda: OcclusionDetectedException(["left_arm"]), limit)
    bench(r, "ShootingNotDetectedException(500)",
          lambda: ShootingNotDetectedException(500), limit)
    bench(r, "DribblingNotDetectedException(300)",
          lambda: DribblingNotDetectedException(300), limit)
    bench(r, "InsufficientDataException('frames', 10, 30)",
          lambda: InsufficientDataException("frames", 10, 30), limit)
    bench(r, "ModelLoadException('yolo', path)",
          lambda: ModelLoadException("yolov8", "/models/yolov8.pt"), limit)
    bench(r, "ModelInferenceException('pose', shape)",
          lambda: ModelInferenceException("pose", (1, 3, 640, 640)), limit)
    bench(r, "ModelNotFoundException('custom', paths)",
          lambda: ModelNotFoundException("custom", ["/a", "/b"]), limit)


# =============================================================================
# [5] 생체역학/경기/심판/피드백 예외 생성 성능
# =============================================================================
def test_bio_game_ref_fb_creation(r: PerfResult) -> None:
    """생체역학/경기/심판/피드백 예외 생성 성능."""
    limit = 80.0

    bench(r, "JointAngleCalculationException(elbow, 200.5)",
          lambda: JointAngleCalculationException("elbow", 200.5, (0, 180), 55), limit)
    bench(r, "ForceCalculationException(velocity, wrist)",
          lambda: ForceCalculationException("velocity", "wrist", 999.9), limit)
    bench(r, "TeamDetectionException(1, 2)",
          lambda: TeamDetectionException(2, 1), limit)
    bench(r, "ScoreDetectionException(200, 0.45)",
          lambda: ScoreDetectionException(200, 0.45), limit)
    bench(r, "PlayDetectionException(pick_and_roll)",
          lambda: PlayDetectionException("pick_and_roll", (100, 200)), limit)
    bench(r, "ViolationDetectionException(traveling)",
          lambda: ViolationDetectionException("traveling", 150, 0.6), limit)
    bench(r, "FoulDetectionException(personal)",
          lambda: FoulDetectionException("personal", ["p01", "p02"], 300, 0.8), limit)
    bench(r, "TemplateNotFoundException(name)",
          lambda: TemplateNotFoundException("shooting_feedback", "drill", "ko"), limit)
    bench(r, "RecommendationException(drill)",
          lambda: RecommendationException("drill", {"score": 75}), limit)


# =============================================================================
# [6] 직렬화 성능
# =============================================================================
def test_serialization_perf(r: PerfResult) -> None:
    """직렬화 메서드 성능."""
    limit_dict = 30.0
    limit_resp = 20.0

    # 비디오 예외 (상세 정보 多)
    ve = VideoFormatException("wmv")
    bench(r, "VideoFormatException.to_dict()", lambda: ve.to_dict(), limit_dict)
    bench(r, "VideoFormatException.to_response_dict()", lambda: ve.to_response_dict(), limit_resp)

    # 모델 예외 (Retryable + retry 필드)
    me = ModelLoadException("yolo", "/models/yolo.pt")
    bench(r, "ModelLoadException.to_dict()", lambda: me.to_dict(), limit_dict)

    # 감지 예외 (NonRetryable)
    de = PersonNotDetectedException((0, 100))
    bench(r, "PersonNotDetectedException.to_dict()", lambda: de.to_dict(), limit_dict)

    # 복합 예외 (전체 인수)
    ce = JointAngleCalculationException("elbow", 200.5, (0.0, 180.0), 55)
    bench(r, "JointAngleCalculationException.to_dict()", lambda: ce.to_dict(), limit_dict)


# =============================================================================
# [7] 대량 생성 성능 (39개 클래스 연속 생성)
# =============================================================================
def test_bulk_creation(r: PerfResult) -> None:
    """39개 예외 클래스 연속 생성 성능."""
    def create_all():
        AnalysisException()
        VideoException()
        VideoFormatException("wmv")
        VideoSizeException(500_000_000, 200_000_000)
        VideoDurationException(3600.0, 1800.0)
        VideoDownloadException("https://x.com/v.mp4", 503)
        VideoCorruptedException("/tmp/b.mp4", "header")
        FrameExtractionException(42, 1000)
        DetectionException()
        PersonNotDetectedException()
        BallNotDetectedException()
        CourtNotDetectedException()
        HoopNotDetectedException()
        MultiplePersonsDetectedException(3)
        LowConfidenceDetectionException(0.3, 0.7, "ball")
        PoseEstimationException()
        InsufficientKeypointsException(10, 17)
        OcclusionDetectedException(["arm"])
        MotionAnalysisException()
        ShootingNotDetectedException()
        DribblingNotDetectedException()
        InsufficientDataException("frames", 10, 30)
        ModelException()
        ModelLoadException("yolo")
        ModelInferenceException("pose")
        ModelNotFoundException("custom")
        BiomechanicsException()
        JointAngleCalculationException("elbow")
        ForceCalculationException("velocity")
        GameAnalysisException()
        TeamDetectionException()
        ScoreDetectionException()
        PlayDetectionException()
        RefereeException()
        ViolationDetectionException()
        FoulDetectionException()
        FeedbackGenerationException()
        TemplateNotFoundException("tmpl")
        RecommendationException("drill")

    elapsed = measure(create_all, 10000)
    limit = 2500.0  # 39개 × ~60us = ~2340us, 여유 포함
    if elapsed < limit:
        r.ok("39개 클래스 연속 생성", elapsed, limit)
    else:
        r.fail("39개 클래스 연속 생성", elapsed, limit)


# =============================================================================
# [8] raise/catch 성능
# =============================================================================
def test_raise_catch_perf(r: PerfResult) -> None:
    """raise/catch 성능."""
    limit = 100.0

    def raise_video_format():
        try:
            raise VideoFormatException("wmv")
        except Exception:
            pass

    bench(r, "raise + catch VideoFormatException", raise_video_format, limit)

    def raise_model_load():
        try:
            raise ModelLoadException("yolo")
        except Exception:
            pass

    bench(r, "raise + catch ModelLoadException", raise_model_load, limit)

    def raise_person_not_detected():
        try:
            raise PersonNotDetectedException()
        except Exception:
            pass

    bench(r, "raise + catch PersonNotDetectedException", raise_person_not_detected, limit)


# =============================================================================
# [9] __str__ 성능
# =============================================================================
def test_str_perf(r: PerfResult) -> None:
    """__str__ 성능."""
    limit = 15.0

    ve = VideoFormatException("wmv")
    bench(r, "str(VideoFormatException)", lambda: str(ve), limit)

    me = ModelLoadException("yolo")
    bench(r, "str(ModelLoadException)", lambda: str(me), limit)

    je = JointAngleCalculationException("elbow", 200.5, (0, 180))
    bench(r, "str(JointAngleCalculationException)", lambda: str(je), limit)


# =============================================================================
# 메인
# =============================================================================
def main() -> int:
    r = PerfResult()
    print("\n" + "=" * 60)
    print("  analysis_exceptions.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- [1] 도메인 기반 클래스 생성 ---")
    test_domain_base_creation(r)

    print("\n--- [2] 비디오 예외 생성 ---")
    test_video_creation(r)

    print("\n--- [3] 감지 예외 생성 ---")
    test_detection_creation(r)

    print("\n--- [4] 포즈/동작/모델 예외 생성 ---")
    test_pose_motion_model_creation(r)

    print("\n--- [5] 생체역학/경기/심판/피드백 예외 생성 ---")
    test_bio_game_ref_fb_creation(r)

    print("\n--- [6] 직렬화 성능 ---")
    test_serialization_perf(r)

    print("\n--- [7] 대량 생성 (39개 연속) ---")
    test_bulk_creation(r)

    print("\n--- [8] raise/catch 성능 ---")
    test_raise_catch_perf(r)

    print("\n--- [9] __str__ 성능 ---")
    test_str_perf(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(main())
