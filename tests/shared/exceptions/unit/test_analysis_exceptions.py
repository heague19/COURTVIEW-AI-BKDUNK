# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/exceptions/unit
파일: test_analysis_exceptions.py
설명: analysis_exceptions.py 단위 테스트 (39개 클래스, 10개 도메인)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# 테스트 대상 임포트
# =============================================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.base_exception import (
    CourtViewException,
    RetryableException,
    NonRetryableException,
)
from shared.exceptions.analysis_exceptions import (
    # 분석 기본
    AnalysisException,
    # 비디오 (7개)
    VideoException,
    VideoFormatException,
    VideoSizeException,
    VideoDurationException,
    VideoDownloadException,
    VideoCorruptedException,
    FrameExtractionException,
    # 감지 (7개)
    DetectionException,
    PersonNotDetectedException,
    BallNotDetectedException,
    CourtNotDetectedException,
    HoopNotDetectedException,
    MultiplePersonsDetectedException,
    LowConfidenceDetectionException,
    # 포즈 (3개)
    PoseEstimationException,
    InsufficientKeypointsException,
    OcclusionDetectedException,
    # 동작 (4개)
    MotionAnalysisException,
    ShootingNotDetectedException,
    DribblingNotDetectedException,
    InsufficientDataException,
    # 모델 (4개)
    ModelException,
    ModelLoadException,
    ModelInferenceException,
    ModelNotFoundException,
    # 생체역학 (3개)
    BiomechanicsException,
    JointAngleCalculationException,
    ForceCalculationException,
    # 경기 (4개)
    GameAnalysisException,
    TeamDetectionException,
    ScoreDetectionException,
    PlayDetectionException,
    # 심판 (3개)
    RefereeException,
    ViolationDetectionException,
    FoulDetectionException,
    # 피드백 (3개)
    FeedbackGenerationException,
    TemplateNotFoundException,
    RecommendationException,
)


# =============================================================================
# 테스트 하네스
# =============================================================================
class TestResult:
    """단위 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.section = ""

    def set_section(self, name: str) -> None:
        self.section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, msg: str = "") -> None:
        self.failed += 1
        detail = f" - {msg}" if msg else ""
        print(f"  [FAIL] {name}{detail}")

    def check(self, name: str, condition: bool, msg: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        print(f"{'='*60}")
        return self.failed == 0


# =============================================================================
# [A] 모듈 메타데이터
# =============================================================================
def test_module_metadata(t: TestResult) -> None:
    """모듈 메타데이터 검증."""
    import shared.exceptions.analysis_exceptions as mod

    t.check("__version__ = '1.0.0'",
            mod.__version__ == "1.0.0")
    t.check("__all__ 길이 = 39",
            len(mod.__all__) == 39,
            f"got {len(mod.__all__)}")

    # 모든 export 존재 확인
    for name in mod.__all__:
        obj = getattr(mod, name, None)
        t.check(f"export '{name}' 존재 및 클래스",
                obj is not None and isinstance(obj, type))


# =============================================================================
# [B] AnalysisException 기본 테스트
# =============================================================================
def test_analysis_exception(t: TestResult) -> None:
    """AnalysisException 기본 테스트."""
    # 기본 생성
    e = AnalysisException()
    t.check("기본 error_code = ANALYSIS_ERROR",
            e.error_code == ErrorCode.ANALYSIS_ERROR)
    t.check("기본 message",
            e.message == "분석 중 오류가 발생했습니다")
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))

    # analysis_type 설정
    e2 = AnalysisException(analysis_type="training")
    t.check("analysis_type → details에 추가",
            e2.details.get("analysis_type") == "training")

    # analysis_type None
    e3 = AnalysisException()
    t.check("analysis_type None → details에 미포함",
            "analysis_type" not in e3.details)


# =============================================================================
# [C] 비디오 예외 (7개)
# =============================================================================
def test_video_exception(t: TestResult) -> None:
    """VideoException 테스트."""
    e = VideoException()
    t.check("기본 error_code = VIDEO_ERROR",
            e.error_code == ErrorCode.VIDEO_ERROR)
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))

    e2 = VideoException(video_id="vid01", video_path="/tmp/test.mp4")
    t.check("video_id 속성",
            e2.video_id == "vid01")
    t.check("video_path 속성",
            e2.video_path == "/tmp/test.mp4")
    t.check("details에 video_id",
            e2.details.get("video_id") == "vid01")
    t.check("details에 video_path",
            e2.details.get("video_path") == "/tmp/test.mp4")


def test_video_format_exception(t: TestResult) -> None:
    """VideoFormatException 테스트."""
    e = VideoFormatException("wmv")
    t.check("error_code = VIDEO_FORMAT_UNSUPPORTED",
            e.error_code == ErrorCode.VIDEO_FORMAT_UNSUPPORTED)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 형식명 포함",
            "wmv" in e.message)
    t.check("details.format_received",
            e.details["format_received"] == "wmv")
    t.check("기본 supported_formats 4종",
            len(e.details["supported_formats"]) == 4)

    # 커스텀 supported
    e2 = VideoFormatException("flv", supported_formats=["mp4", "avi"])
    t.check("커스텀 supported_formats",
            e2.details["supported_formats"] == ["mp4", "avi"])


def test_video_size_exception(t: TestResult) -> None:
    """VideoSizeException 테스트."""
    e = VideoSizeException(size_bytes=500_000_000, max_size_bytes=200_000_000)
    t.check("error_code = VIDEO_TOO_LARGE",
            e.error_code == ErrorCode.VIDEO_TOO_LARGE)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("details.size_bytes",
            e.details["size_bytes"] == 500_000_000)
    t.check("details.max_size_bytes",
            e.details["max_size_bytes"] == 200_000_000)
    t.check("size_mb 계산 정확",
            abs(e.details["size_mb"] - 476.84) < 1.0)
    t.check("message에 MB 표시",
            "MB" in e.message)


def test_video_duration_exception(t: TestResult) -> None:
    """VideoDurationException 테스트."""
    e = VideoDurationException(duration_seconds=3600.5, max_duration_seconds=1800.0)
    t.check("error_code = VIDEO_TOO_LONG",
            e.error_code == ErrorCode.VIDEO_TOO_LONG)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("details.duration_seconds",
            e.details["duration_seconds"] == 3600.5)
    t.check("details.max_duration_seconds",
            e.details["max_duration_seconds"] == 1800.0)
    t.check("message에 초 표시",
            "3600.5초" in e.message)


def test_video_download_exception(t: TestResult) -> None:
    """VideoDownloadException 테스트."""
    e = VideoDownloadException(video_url="https://example.com/video.mp4", status_code=503)
    t.check("error_code = VIDEO_DOWNLOAD_FAILED",
            e.error_code == ErrorCode.VIDEO_DOWNLOAD_FAILED)
    t.check("RetryableException 상속",
            isinstance(e, RetryableException))
    t.check("기본 retry_after = 5.0",
            e.retry_after == 5.0)
    t.check("details.video_url",
            e.details["video_url"] == "https://example.com/video.mp4")
    t.check("details.status_code = 503",
            e.details["status_code"] == 503)
    t.check("message에 URL 포함",
            "example.com" in e.message)


def test_video_corrupted_exception(t: TestResult) -> None:
    """VideoCorruptedException 테스트."""
    e = VideoCorruptedException(video_path="/tmp/bad.mp4", corruption_type="header")
    t.check("error_code = VIDEO_CORRUPTED",
            e.error_code == ErrorCode.VIDEO_CORRUPTED)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("details.corruption_type = header",
            e.details["corruption_type"] == "header")
    t.check("details.video_path",
            e.details["video_path"] == "/tmp/bad.mp4")


def test_frame_extraction_exception(t: TestResult) -> None:
    """FrameExtractionException 테스트."""
    e = FrameExtractionException(frame_number=42, total_frames=1000)
    t.check("error_code = FRAME_EXTRACTION_FAILED",
            e.error_code == ErrorCode.FRAME_EXTRACTION_FAILED)
    t.check("RetryableException 상속",
            isinstance(e, RetryableException))
    t.check("message에 프레임 번호 포함",
            "42" in e.message)
    t.check("details.frame_number = 42",
            e.details["frame_number"] == 42)
    t.check("details.total_frames = 1000",
            e.details["total_frames"] == 1000)

    # frame_number None → 일반 메시지
    e2 = FrameExtractionException()
    t.check("frame_number None → 일반 메시지",
            "프레임 추출에 실패" in e2.message and "None" not in e2.message)


# =============================================================================
# [D] 감지 예외 (7개)
# =============================================================================
def test_detection_exception(t: TestResult) -> None:
    """DetectionException 테스트."""
    e = DetectionException()
    t.check("기본 error_code = DETECTION_ERROR",
            e.error_code == ErrorCode.DETECTION_ERROR)
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))

    e2 = DetectionException(frame_number=10, detection_type="person")
    t.check("frame_number 속성",
            e2.frame_number == 10)
    t.check("detection_type 속성",
            e2.detection_type == "person")
    t.check("details에 frame_number",
            e2.details["frame_number"] == 10)


def test_person_not_detected(t: TestResult) -> None:
    """PersonNotDetectedException 테스트."""
    e = PersonNotDetectedException(frame_range=(0, 100))
    t.check("error_code = DETECTION_NO_PERSON",
            e.error_code == ErrorCode.DETECTION_NO_PERSON)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message 한글",
            "사람" in e.message)
    t.check("details.frame_range",
            e.details["frame_range"] == (0, 100))

    # frame_range None
    e2 = PersonNotDetectedException()
    t.check("frame_range None → details None",
            not e2.details)


def test_ball_not_detected(t: TestResult) -> None:
    """BallNotDetectedException 테스트."""
    e = BallNotDetectedException(
        frame_range=(10, 50), frame_index=25, consecutive_misses=5
    )
    t.check("error_code = DETECTION_NO_BALL",
            e.error_code == ErrorCode.DETECTION_NO_BALL)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("frame_index 속성",
            e.frame_index == 25)
    t.check("consecutive_misses 속성",
            e.consecutive_misses == 5)
    t.check("details.frame_range",
            e.details["frame_range"] == (10, 50))
    t.check("details.frame_index",
            e.details["frame_index"] == 25)
    t.check("details.consecutive_misses",
            e.details["consecutive_misses"] == 5)

    # 커스텀 message
    e2 = BallNotDetectedException(message="커스텀 메시지")
    t.check("커스텀 message 사용",
            e2.message == "커스텀 메시지")

    # 기본 message (message=None)
    e3 = BallNotDetectedException()
    t.check("기본 message에 '농구공' 포함",
            "농구공" in e3.message)


def test_court_not_detected(t: TestResult) -> None:
    """CourtNotDetectedException 테스트."""
    e = CourtNotDetectedException(frame_range=(0, 200))
    t.check("error_code = DETECTION_NO_COURT",
            e.error_code == ErrorCode.DETECTION_NO_COURT)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 '코트' 포함",
            "코트" in e.message)


def test_hoop_not_detected(t: TestResult) -> None:
    """HoopNotDetectedException 테스트."""
    e = HoopNotDetectedException()
    t.check("error_code = DETECTION_NO_HOOP",
            e.error_code == ErrorCode.DETECTION_NO_HOOP)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 '골대' 포함",
            "골대" in e.message)


def test_multiple_persons_detected(t: TestResult) -> None:
    """MultiplePersonsDetectedException 테스트."""
    e = MultiplePersonsDetectedException(person_count=3, frame_number=50)
    t.check("error_code = DETECTION_MULTIPLE_PERSONS",
            e.error_code == ErrorCode.DETECTION_MULTIPLE_PERSONS)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 인원 수 포함",
            "3명" in e.message)
    t.check("details.person_count",
            e.details["person_count"] == 3)
    t.check("details.frame_number",
            e.details["frame_number"] == 50)


def test_low_confidence_detection(t: TestResult) -> None:
    """LowConfidenceDetectionException 테스트."""
    e = LowConfidenceDetectionException(
        confidence=0.35, min_confidence=0.7, detection_type="ball", frame_number=100
    )
    t.check("error_code = DETECTION_LOW_CONFIDENCE",
            e.error_code == ErrorCode.DETECTION_LOW_CONFIDENCE)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("details.confidence = 0.35",
            e.details["confidence"] == 0.35)
    t.check("details.min_confidence = 0.7",
            e.details["min_confidence"] == 0.7)
    t.check("details.detection_type = ball",
            e.details["detection_type"] == "ball")
    t.check("message에 퍼센트 포함",
            "%" in e.message)


# =============================================================================
# [E] 포즈 추정 예외 (3개)
# =============================================================================
def test_pose_estimation_exception(t: TestResult) -> None:
    """PoseEstimationException 테스트."""
    e = PoseEstimationException()
    t.check("기본 error_code = POSE_ESTIMATION_ERROR",
            e.error_code == ErrorCode.POSE_ESTIMATION_ERROR)
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))

    e2 = PoseEstimationException(frame_number=77)
    t.check("frame_number 속성",
            e2.frame_number == 77)
    t.check("details.frame_number",
            e2.details["frame_number"] == 77)


def test_insufficient_keypoints(t: TestResult) -> None:
    """InsufficientKeypointsException 테스트."""
    e = InsufficientKeypointsException(
        detected_keypoints=10,
        required_keypoints=17,
        missing_keypoints=["left_ankle", "right_ankle"],
        frame_number=42,
    )
    t.check("error_code = POSE_INSUFFICIENT_KEYPOINTS",
            e.error_code == ErrorCode.POSE_INSUFFICIENT_KEYPOINTS)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 수치 포함",
            "10/17" in e.message)
    t.check("details.missing_keypoints",
            e.details["missing_keypoints"] == ["left_ankle", "right_ankle"])


def test_occlusion_detected(t: TestResult) -> None:
    """OcclusionDetectedException 테스트."""
    e = OcclusionDetectedException(
        occluded_parts=["left_arm", "torso"], frame_number=33
    )
    t.check("error_code = POSE_OCCLUSION_DETECTED",
            e.error_code == ErrorCode.POSE_OCCLUSION_DETECTED)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 신체부위 나열",
            "left_arm" in e.message and "torso" in e.message)
    t.check("details.occluded_parts",
            e.details["occluded_parts"] == ["left_arm", "torso"])


# =============================================================================
# [F] 동작 분석 예외 (4개)
# =============================================================================
def test_motion_analysis_exception(t: TestResult) -> None:
    """MotionAnalysisException 테스트."""
    e = MotionAnalysisException()
    t.check("기본 error_code = MOTION_ANALYSIS_ERROR",
            e.error_code == ErrorCode.MOTION_ANALYSIS_ERROR)
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))

    e2 = MotionAnalysisException(motion_type="shooting")
    t.check("motion_type 속성",
            e2.motion_type == "shooting")
    t.check("details에 motion_type",
            e2.details["motion_type"] == "shooting")


def test_shooting_not_detected(t: TestResult) -> None:
    """ShootingNotDetectedException 테스트."""
    e = ShootingNotDetectedException(analyzed_frames=500)
    t.check("error_code = SHOOTING_NOT_DETECTED",
            e.error_code == ErrorCode.SHOOTING_NOT_DETECTED)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 '슈팅' 포함",
            "슈팅" in e.message)
    t.check("details.analyzed_frames = 500",
            e.details["analyzed_frames"] == 500)

    # analyzed_frames None
    e2 = ShootingNotDetectedException()
    t.check("analyzed_frames None → details None",
            not e2.details)


def test_dribbling_not_detected(t: TestResult) -> None:
    """DribblingNotDetectedException 테스트."""
    e = DribblingNotDetectedException(analyzed_frames=300)
    t.check("error_code = DRIBBLING_NOT_DETECTED",
            e.error_code == ErrorCode.DRIBBLING_NOT_DETECTED)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 '드리블' 포함",
            "드리블" in e.message)


def test_insufficient_data(t: TestResult) -> None:
    """InsufficientDataException 테스트."""
    e = InsufficientDataException(
        data_type="frames", received=10, required=30
    )
    t.check("error_code = MOTION_INSUFFICIENT_DATA",
            e.error_code == ErrorCode.MOTION_INSUFFICIENT_DATA)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 수치 포함",
            "10/30" in e.message)
    t.check("details.data_type = frames",
            e.details["data_type"] == "frames")


# =============================================================================
# [G] 모델 예외 (4개)
# =============================================================================
def test_model_exception(t: TestResult) -> None:
    """ModelException 테스트."""
    e = ModelException()
    t.check("기본 error_code = MODEL_ERROR",
            e.error_code == ErrorCode.MODEL_ERROR)
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))

    e2 = ModelException(model_name="yolov8", model_version="1.0")
    t.check("model_name 속성",
            e2.model_name == "yolov8")
    t.check("model_version 속성",
            e2.model_version == "1.0")
    t.check("details에 model_name",
            e2.details["model_name"] == "yolov8")


def test_model_load_exception(t: TestResult) -> None:
    """ModelLoadException 테스트."""
    e = ModelLoadException(model_name="yolov8", model_path="/models/yolov8.pt")
    t.check("error_code = MODEL_LOAD_FAILED",
            e.error_code == ErrorCode.MODEL_LOAD_FAILED)
    t.check("RetryableException 상속",
            isinstance(e, RetryableException))
    t.check("retry_after = 3.0",
            e.retry_after == 3.0)
    t.check("message에 모델명 포함",
            "yolov8" in e.message)
    t.check("details.model_path",
            e.details["model_path"] == "/models/yolov8.pt")


def test_model_inference_exception(t: TestResult) -> None:
    """ModelInferenceException 테스트."""
    e = ModelInferenceException(
        model_name="pose_model", input_shape=(1, 3, 640, 640)
    )
    t.check("error_code = MODEL_INFERENCE_FAILED",
            e.error_code == ErrorCode.MODEL_INFERENCE_FAILED)
    t.check("RetryableException 상속",
            isinstance(e, RetryableException))
    t.check("retry_after = 1.0",
            e.retry_after == 1.0)
    t.check("details.input_shape",
            e.details["input_shape"] == (1, 3, 640, 640))


def test_model_not_found_exception(t: TestResult) -> None:
    """ModelNotFoundException 테스트."""
    e = ModelNotFoundException(
        model_name="custom_model",
        searched_paths=["/models", "/cache/models"]
    )
    t.check("error_code = MODEL_NOT_FOUND",
            e.error_code == ErrorCode.MODEL_NOT_FOUND)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 모델명 포함",
            "custom_model" in e.message)
    t.check("details.searched_paths",
            e.details["searched_paths"] == ["/models", "/cache/models"])


# =============================================================================
# [H] 생체역학 예외 (3개)
# =============================================================================
def test_biomechanics_exception(t: TestResult) -> None:
    """BiomechanicsException 테스트."""
    e = BiomechanicsException()
    t.check("기본 error_code = BIOMECHANICS_ERROR",
            e.error_code == ErrorCode.BIOMECHANICS_ERROR)
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))

    e2 = BiomechanicsException(joint_name="knee", calculation_type="angle")
    t.check("joint_name 속성",
            e2.joint_name == "knee")
    t.check("calculation_type 속성",
            e2.calculation_type == "angle")


def test_joint_angle_calculation(t: TestResult) -> None:
    """JointAngleCalculationException 테스트."""
    e = JointAngleCalculationException(
        joint_name="elbow",
        angle_value=200.5,
        valid_range=(0.0, 180.0),
        frame_number=55,
    )
    t.check("error_code = BIOMECHANICS_INVALID_ANGLE",
            e.error_code == ErrorCode.BIOMECHANICS_INVALID_ANGLE)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 관절명 포함",
            "elbow" in e.message)
    t.check("message에 각도값 포함",
            "200.5" in e.message)
    t.check("message에 유효범위 포함",
            "0.0" in e.message and "180.0" in e.message)

    # angle_value / valid_range 없을 때
    e2 = JointAngleCalculationException(joint_name="knee")
    t.check("angle_value None → 범위 표시 없음",
            "°" not in e2.message)


def test_force_calculation(t: TestResult) -> None:
    """ForceCalculationException 테스트."""
    e = ForceCalculationException(
        calculation_type="velocity",
        body_part="wrist",
        calculated_value=999.9,
    )
    t.check("error_code = BIOMECHANICS_INVALID_VELOCITY",
            e.error_code == ErrorCode.BIOMECHANICS_INVALID_VELOCITY)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 계산유형 포함",
            "velocity" in e.message)
    t.check("message에 신체부위 포함",
            "wrist" in e.message)

    # body_part None
    e2 = ForceCalculationException(calculation_type="acceleration")
    t.check("body_part None → 괄호 없음",
            "(" not in e2.message)


# =============================================================================
# [I] 경기 분석 예외 (4개)
# =============================================================================
def test_game_analysis_exception(t: TestResult) -> None:
    """GameAnalysisException 테스트."""
    e = GameAnalysisException()
    t.check("기본 error_code = GAME_ANALYSIS_ERROR",
            e.error_code == ErrorCode.GAME_ANALYSIS_ERROR)
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))

    e2 = GameAnalysisException(game_id="g001", quarter=2)
    t.check("game_id 속성",
            e2.game_id == "g001")
    t.check("quarter 속성",
            e2.quarter == 2)
    t.check("details에 game_id",
            e2.details["game_id"] == "g001")
    t.check("details에 quarter",
            e2.details["quarter"] == 2)


def test_team_detection_exception(t: TestResult) -> None:
    """TeamDetectionException 테스트."""
    e = TeamDetectionException(detected_teams=1, expected_teams=2)
    t.check("error_code = GAME_ANALYSIS_ERROR",
            e.error_code == ErrorCode.GAME_ANALYSIS_ERROR)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 팀 수 포함",
            "1개" in e.message and "2개" in e.message)

    # detected_teams None
    e2 = TeamDetectionException()
    t.check("detected_teams None → 안내 메시지",
            "유니폼" in e2.message)


def test_score_detection_exception(t: TestResult) -> None:
    """ScoreDetectionException 테스트."""
    e = ScoreDetectionException(frame_number=200, detection_confidence=0.45)
    t.check("error_code = GAME_ANALYSIS_ERROR",
            e.error_code == ErrorCode.GAME_ANALYSIS_ERROR)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("details.frame_number = 200",
            e.details["frame_number"] == 200)
    t.check("details.detection_confidence = 0.45",
            e.details["detection_confidence"] == 0.45)


def test_play_detection_exception(t: TestResult) -> None:
    """PlayDetectionException 테스트."""
    e = PlayDetectionException(play_type="pick_and_roll", frame_range=(100, 200))
    t.check("error_code = GAME_ANALYSIS_ERROR",
            e.error_code == ErrorCode.GAME_ANALYSIS_ERROR)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 플레이 유형 포함",
            "pick_and_roll" in e.message)

    # play_type None
    e2 = PlayDetectionException()
    t.check("play_type None → 일반 메시지",
            "경기 플레이" in e2.message)


# =============================================================================
# [J] 심판 예외 (3개)
# =============================================================================
def test_referee_exception(t: TestResult) -> None:
    """RefereeException 테스트."""
    e = RefereeException()
    t.check("기본 error_code = REFEREE_ERROR",
            e.error_code == ErrorCode.REFEREE_ERROR)
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))

    e2 = RefereeException(rule_set="FIBA", rule_id="art33.1")
    t.check("rule_set 속성",
            e2.rule_set == "FIBA")
    t.check("rule_id 속성",
            e2.rule_id == "art33.1")
    t.check("details에 rule_set",
            e2.details["rule_set"] == "FIBA")
    t.check("details에 rule_id",
            e2.details["rule_id"] == "art33.1")


def test_violation_detection_exception(t: TestResult) -> None:
    """ViolationDetectionException 테스트."""
    e = ViolationDetectionException(
        violation_type="traveling", frame_number=150, confidence=0.6
    )
    t.check("error_code = REFEREE_ERROR",
            e.error_code == ErrorCode.REFEREE_ERROR)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 바이올레이션 유형 포함",
            "traveling" in e.message)
    t.check("details.confidence = 0.6",
            e.details["confidence"] == 0.6)

    # violation_type None
    e2 = ViolationDetectionException()
    t.check("violation_type None → 일반 메시지",
            "바이올레이션 감지에 실패" in e2.message)


def test_foul_detection_exception(t: TestResult) -> None:
    """FoulDetectionException 테스트."""
    e = FoulDetectionException(
        foul_type="personal",
        player_ids=["p01", "p02"],
        frame_number=300,
        confidence=0.8,
    )
    t.check("error_code = REFEREE_ERROR",
            e.error_code == ErrorCode.REFEREE_ERROR)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 파울 유형 포함",
            "personal" in e.message)
    t.check("details.player_ids",
            e.details["player_ids"] == ["p01", "p02"])

    # foul_type None
    e2 = FoulDetectionException()
    t.check("foul_type None → 일반 메시지",
            "파울 감지에 실패" in e2.message)


# =============================================================================
# [K] 피드백 생성 예외 (3개)
# =============================================================================
def test_feedback_generation_exception(t: TestResult) -> None:
    """FeedbackGenerationException 테스트."""
    e = FeedbackGenerationException()
    t.check("기본 error_code = ANALYSIS_ERROR",
            e.error_code == ErrorCode.ANALYSIS_ERROR)
    t.check("CourtViewException 상속",
            isinstance(e, CourtViewException))

    e2 = FeedbackGenerationException(
        feedback_type="shooting", analysis_id="a001"
    )
    t.check("feedback_type 속성",
            e2.feedback_type == "shooting")
    t.check("analysis_id 속성",
            e2.analysis_id == "a001")


def test_template_not_found(t: TestResult) -> None:
    """TemplateNotFoundException 테스트."""
    e = TemplateNotFoundException(
        template_name="shooting_feedback",
        template_type="drill",
        locale="ko",
    )
    t.check("error_code = ANALYSIS_ERROR",
            e.error_code == ErrorCode.ANALYSIS_ERROR)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 템플릿명 포함",
            "shooting_feedback" in e.message)
    t.check("details.template_type = drill",
            e.details["template_type"] == "drill")
    t.check("details.locale = ko",
            e.details["locale"] == "ko")


def test_recommendation_exception(t: TestResult) -> None:
    """RecommendationException 테스트."""
    e = RecommendationException(
        recommendation_type="drill",
        analysis_results={"score": 75},
    )
    t.check("error_code = ANALYSIS_ERROR",
            e.error_code == ErrorCode.ANALYSIS_ERROR)
    t.check("NonRetryableException 상속",
            isinstance(e, NonRetryableException))
    t.check("message에 추천 유형 포함",
            "drill" in e.message)
    t.check("details.has_analysis_results = True",
            e.details["has_analysis_results"] is True)

    # analysis_results None
    e2 = RecommendationException(recommendation_type="plan")
    t.check("analysis_results None → has_analysis_results False",
            e2.details["has_analysis_results"] is False)


# =============================================================================
# [L] 상속 계층 종합 검증
# =============================================================================
def test_inheritance_hierarchy(t: TestResult) -> None:
    """전체 상속 계층 검증."""
    # 도메인 기반 클래스 → CourtViewException
    domain_bases = [
        (AnalysisException, "AnalysisException"),
        (VideoException, "VideoException"),
        (DetectionException, "DetectionException"),
        (PoseEstimationException, "PoseEstimationException"),
        (MotionAnalysisException, "MotionAnalysisException"),
        (ModelException, "ModelException"),
        (BiomechanicsException, "BiomechanicsException"),
        (GameAnalysisException, "GameAnalysisException"),
        (RefereeException, "RefereeException"),
        (FeedbackGenerationException, "FeedbackGenerationException"),
    ]
    for cls, name in domain_bases:
        t.check(f"{name} → CourtViewException",
                issubclass(cls, CourtViewException))

    # Retryable 클래스 (4개)
    retryable_classes = [
        VideoDownloadException,
        FrameExtractionException,
        ModelLoadException,
        ModelInferenceException,
    ]
    for cls in retryable_classes:
        t.check(f"{cls.__name__} → RetryableException",
                issubclass(cls, RetryableException))

    # NonRetryable 클래스 (25개)
    non_retryable_classes = [
        VideoFormatException, VideoSizeException, VideoDurationException,
        VideoCorruptedException,
        PersonNotDetectedException, BallNotDetectedException,
        CourtNotDetectedException, HoopNotDetectedException,
        MultiplePersonsDetectedException, LowConfidenceDetectionException,
        InsufficientKeypointsException, OcclusionDetectedException,
        ShootingNotDetectedException, DribblingNotDetectedException,
        InsufficientDataException,
        ModelNotFoundException,
        JointAngleCalculationException, ForceCalculationException,
        TeamDetectionException, ScoreDetectionException,
        PlayDetectionException,
        ViolationDetectionException, FoulDetectionException,
        TemplateNotFoundException, RecommendationException,
    ]
    for cls in non_retryable_classes:
        t.check(f"{cls.__name__} → NonRetryableException",
                issubclass(cls, NonRetryableException))

    t.check("Retryable 클래스 수 = 4",
            len(retryable_classes) == 4)
    t.check("NonRetryable 클래스 수 = 25",
            len(non_retryable_classes) == 25)


# =============================================================================
# [M] raise/catch 교차 검증
# =============================================================================
def test_cross_domain_catch(t: TestResult) -> None:
    """교차 도메인 catch 테스트."""
    # 비디오 예외 → CourtViewException으로 catch
    try:
        raise VideoFormatException("flv")
    except CourtViewException as e:
        t.check("VideoFormatException → CourtViewException catch",
                isinstance(e, VideoFormatException))

    # 모델 예외 → RetryableException으로 catch
    try:
        raise ModelLoadException("yolo")
    except RetryableException as e:
        t.check("ModelLoadException → RetryableException catch",
                isinstance(e, ModelLoadException))

    # 감지 예외 → NonRetryableException으로 catch
    try:
        raise PersonNotDetectedException()
    except NonRetryableException as e:
        t.check("PersonNotDetectedException → NonRetryableException catch",
                isinstance(e, PersonNotDetectedException))

    # 모든 예외 → Exception으로 catch
    try:
        raise BiomechanicsException()
    except Exception as e:
        t.check("BiomechanicsException → Exception catch",
                isinstance(e, BiomechanicsException))


# =============================================================================
# [N] to_dict / to_response_dict 검증
# =============================================================================
def test_serialization(t: TestResult) -> None:
    """직렬화 메서드 검증."""
    # Retryable → to_dict에 retry 포함
    e1 = VideoDownloadException(
        video_url="https://test.com/v.mp4", status_code=500
    )
    d1 = e1.to_dict()
    t.check("RetryableException to_dict에 retry 키",
            "retry" in d1)
    t.check("retry.retry_after = 5.0",
            d1["retry"]["retry_after"] == 5.0)

    # NonRetryable → to_dict에 retryable: False
    e2 = PersonNotDetectedException(frame_range=(0, 50))
    d2 = e2.to_dict()
    t.check("NonRetryableException to_dict에 retryable 키",
            "retryable" in d2)
    t.check("retryable = False",
            d2["retryable"] is False)

    # to_response_dict
    e3 = VideoFormatException("wmv")
    rd = e3.to_response_dict()
    t.check("to_response_dict success = False",
            rd["success"] is False)
    t.check("to_response_dict에 error 포함",
            "error" in rd)
    t.check("to_response_dict에 traceback 미포함",
            "traceback" not in rd)


# =============================================================================
# 메인
# =============================================================================
def main() -> None:
    t = TestResult()
    print("\n" + "=" * 60)
    print("  analysis_exceptions.py v1.0.0 단위 테스트")
    print("=" * 60)

    t.set_section("[A] 모듈 메타데이터")
    test_module_metadata(t)

    t.set_section("[B] AnalysisException 기본")
    test_analysis_exception(t)

    t.set_section("[C-1] VideoException")
    test_video_exception(t)
    t.set_section("[C-2] VideoFormatException")
    test_video_format_exception(t)
    t.set_section("[C-3] VideoSizeException")
    test_video_size_exception(t)
    t.set_section("[C-4] VideoDurationException")
    test_video_duration_exception(t)
    t.set_section("[C-5] VideoDownloadException")
    test_video_download_exception(t)
    t.set_section("[C-6] VideoCorruptedException")
    test_video_corrupted_exception(t)
    t.set_section("[C-7] FrameExtractionException")
    test_frame_extraction_exception(t)

    t.set_section("[D-1] DetectionException")
    test_detection_exception(t)
    t.set_section("[D-2] PersonNotDetectedException")
    test_person_not_detected(t)
    t.set_section("[D-3] BallNotDetectedException")
    test_ball_not_detected(t)
    t.set_section("[D-4] CourtNotDetectedException")
    test_court_not_detected(t)
    t.set_section("[D-5] HoopNotDetectedException")
    test_hoop_not_detected(t)
    t.set_section("[D-6] MultiplePersonsDetectedException")
    test_multiple_persons_detected(t)
    t.set_section("[D-7] LowConfidenceDetectionException")
    test_low_confidence_detection(t)

    t.set_section("[E-1] PoseEstimationException")
    test_pose_estimation_exception(t)
    t.set_section("[E-2] InsufficientKeypointsException")
    test_insufficient_keypoints(t)
    t.set_section("[E-3] OcclusionDetectedException")
    test_occlusion_detected(t)

    t.set_section("[F-1] MotionAnalysisException")
    test_motion_analysis_exception(t)
    t.set_section("[F-2] ShootingNotDetectedException")
    test_shooting_not_detected(t)
    t.set_section("[F-3] DribblingNotDetectedException")
    test_dribbling_not_detected(t)
    t.set_section("[F-4] InsufficientDataException")
    test_insufficient_data(t)

    t.set_section("[G-1] ModelException")
    test_model_exception(t)
    t.set_section("[G-2] ModelLoadException")
    test_model_load_exception(t)
    t.set_section("[G-3] ModelInferenceException")
    test_model_inference_exception(t)
    t.set_section("[G-4] ModelNotFoundException")
    test_model_not_found_exception(t)

    t.set_section("[H-1] BiomechanicsException")
    test_biomechanics_exception(t)
    t.set_section("[H-2] JointAngleCalculationException")
    test_joint_angle_calculation(t)
    t.set_section("[H-3] ForceCalculationException")
    test_force_calculation(t)

    t.set_section("[I-1] GameAnalysisException")
    test_game_analysis_exception(t)
    t.set_section("[I-2] TeamDetectionException")
    test_team_detection_exception(t)
    t.set_section("[I-3] ScoreDetectionException")
    test_score_detection_exception(t)
    t.set_section("[I-4] PlayDetectionException")
    test_play_detection_exception(t)

    t.set_section("[J-1] RefereeException")
    test_referee_exception(t)
    t.set_section("[J-2] ViolationDetectionException")
    test_violation_detection_exception(t)
    t.set_section("[J-3] FoulDetectionException")
    test_foul_detection_exception(t)

    t.set_section("[K-1] FeedbackGenerationException")
    test_feedback_generation_exception(t)
    t.set_section("[K-2] TemplateNotFoundException")
    test_template_not_found(t)
    t.set_section("[K-3] RecommendationException")
    test_recommendation_exception(t)

    t.set_section("[L] 상속 계층 종합 검증")
    test_inheritance_hierarchy(t)

    t.set_section("[M] 교차 도메인 catch")
    test_cross_domain_catch(t)

    t.set_section("[N] 직렬화 검증")
    test_serialization(t)

    sys.exit(0 if t.summary() else 1)


if __name__ == "__main__":
    main()
