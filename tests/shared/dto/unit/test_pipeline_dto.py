# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_pipeline_dto.py

파이프라인 DTO 유닛 테스트
- __all__ export / __version__ 검증
- VideoSource Enum: 멤버, str 값
- VideoMetadata: frozen, source_path 필수, model_validator
- PipelineOptions: frozen, quality/feedback pattern, model_validator time_range
- BasePipelineRequest: frozen, UUID 자동생성, 기본값
- GameAnalysisRequest: field_validator (경기 타입만 허용)
- RefereeAnalysisRequest: field_validator (심판 타입만 허용)
- PipelineRequest: Union 타입 alias
- PipelineProgress: frozen, 필드
- PipelineResultBase / GameAnalysisResult / RefereeAnalysisResult
- ViolationCounts / FoulCounts: total 프로퍼티
- SyncEventType Enum / BackendSyncPayload

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from uuid import UUID, uuid4

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{test_name}: {detail}" if detail else test_name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def assert_eq(r: TestResult, name: str, actual, expected) -> None:
    if actual == expected:
        r.ok(name)
    else:
        r.fail(name, f"expected={expected!r}, actual={actual!r}")


def assert_true(r: TestResult, name: str, value: bool) -> None:
    if value:
        r.ok(name)
    else:
        r.fail(name, "expected True, got False")


def assert_false(r: TestResult, name: str, value: bool) -> None:
    if not value:
        r.ok(name)
    else:
        r.fail(name, "expected False, got True")


def assert_none(r: TestResult, name: str, value) -> None:
    if value is None:
        r.ok(name)
    else:
        r.fail(name, f"expected None, got {value!r}")


def assert_not_none(r: TestResult, name: str, value) -> None:
    if value is not None:
        r.ok(name)
    else:
        r.fail(name, "expected not None, got None")


def assert_isinstance(r: TestResult, name: str, obj, cls) -> None:
    if isinstance(obj, cls):
        r.ok(name)
    else:
        r.fail(name, f"expected isinstance({cls.__name__}), got {type(obj).__name__}")


def assert_raises(r: TestResult, name: str, exc_type, func) -> None:
    try:
        func()
        r.fail(name, f"expected {exc_type.__name__}, no exception raised")
    except exc_type:
        r.ok(name)
    except Exception as e:
        r.fail(name, f"expected {exc_type.__name__}, got {type(e).__name__}: {e}")


def assert_close(r: TestResult, name: str, actual: float, expected: float, tol: float = 1e-6) -> None:
    if abs(actual - expected) < tol:
        r.ok(name)
    else:
        r.fail(name, f"expected≈{expected}, actual={actual}")


# ==================== [A] __all__ / __version__ ====================
def test_exports(r: TestResult) -> None:
    """__all__ export 검증"""
    import shared.dto.pipeline_dto as mod
    assert_true(r, "__all__ 존재", hasattr(mod, "__all__"))
    assert_eq(r, "__all__ 개수 = 15", len(mod.__all__), 15)

    expected = [
        "VideoSource", "VideoMetadata", "PipelineOptions",
        "BasePipelineRequest", "GameAnalysisRequest", "RefereeAnalysisRequest",
        "PipelineRequest", "PipelineProgress", "PipelineResultBase",
        "GameAnalysisResult", "ViolationCounts", "FoulCounts",
        "RefereeAnalysisResult", "SyncEventType", "BackendSyncPayload",
    ]
    for name in expected:
        assert_true(r, f"__all__에 {name} 포함", name in mod.__all__)
        assert_true(r, f"{name} 접근 가능", hasattr(mod, name))


def test_version(r: TestResult) -> None:
    """__version__ 검증"""
    import shared.dto.pipeline_dto as mod
    assert_true(r, "__version__ 존재", hasattr(mod, "__version__"))
    assert_eq(r, "__version__ = '1.0.0'", mod.__version__, "1.0.0")


# ==================== [B] VideoSource Enum ====================
def test_video_source_members(r: TestResult) -> None:
    """VideoSource Enum 멤버 검증"""
    from shared.dto.pipeline_dto import VideoSource

    expected = ["LOCAL_FILE", "DIRECT_UPLOAD", "STREAM_URL"]
    actual = [m.name for m in VideoSource]
    assert_eq(r, "VideoSource 멤버 수 = 3", len(actual), 3)
    for name in expected:
        assert_true(r, f"VideoSource.{name} 존재", name in actual)

    assert_eq(r, "LOCAL_FILE.value", VideoSource.LOCAL_FILE.value, "local_file")
    assert_eq(r, "DIRECT_UPLOAD.value", VideoSource.DIRECT_UPLOAD.value, "direct_upload")
    assert_eq(r, "STREAM_URL.value", VideoSource.STREAM_URL.value, "stream_url")
    assert_isinstance(r, "str Enum", VideoSource.LOCAL_FILE, str)


# ==================== [C] VideoMetadata ====================
def test_video_metadata_basic(r: TestResult) -> None:
    """VideoMetadata 기본 생성 검증"""
    from shared.dto.pipeline_dto import VideoMetadata, VideoSource

    vm = VideoMetadata(source_path="/path/to/video.mp4")
    assert_eq(r, "기본 source_type = LOCAL_FILE", vm.source_type, VideoSource.LOCAL_FILE)
    assert_eq(r, "source_path 설정", vm.source_path, "/path/to/video.mp4")
    assert_none(r, "기본 filename = None", vm.filename)
    assert_none(r, "기본 duration_seconds = None", vm.duration_seconds)
    assert_none(r, "기본 fps = None", vm.fps)


def test_video_metadata_frozen(r: TestResult) -> None:
    """VideoMetadata frozen 검증"""
    from shared.dto.pipeline_dto import VideoMetadata

    vm = VideoMetadata(source_path="/test.mp4")
    try:
        vm.source_path = "/other.mp4"
        r.fail("VideoMetadata frozen", "mutation 허용됨")
    except Exception:
        r.ok("VideoMetadata frozen")


def test_video_metadata_source_path_required(r: TestResult) -> None:
    """VideoMetadata source_path 필수 검증"""
    from shared.dto.pipeline_dto import VideoMetadata
    from pydantic import ValidationError

    assert_raises(r, "source_path 빈 문자열 거부", ValidationError,
                  lambda: VideoMetadata(source_path=""))
    assert_raises(r, "source_path 공백만 거부", ValidationError,
                  lambda: VideoMetadata(source_path="   "))


def test_video_metadata_stream_url_validation(r: TestResult) -> None:
    """VideoMetadata STREAM_URL 프로토콜 검증"""
    from shared.dto.pipeline_dto import VideoMetadata, VideoSource
    from pydantic import ValidationError

    # 유효한 스트림 URL
    vm_rtsp = VideoMetadata(source_type=VideoSource.STREAM_URL, source_path="rtsp://192.168.1.1/stream")
    assert_eq(r, "rtsp:// 허용", vm_rtsp.source_path, "rtsp://192.168.1.1/stream")

    vm_http = VideoMetadata(source_type=VideoSource.STREAM_URL, source_path="https://example.com/stream")
    assert_eq(r, "https:// 허용", vm_http.source_path, "https://example.com/stream")

    # 잘못된 프로토콜
    assert_raises(r, "STREAM_URL ftp:// 거부", ValidationError,
                  lambda: VideoMetadata(source_type=VideoSource.STREAM_URL, source_path="ftp://server/file"))


def test_video_metadata_full_fields(r: TestResult) -> None:
    """VideoMetadata 전체 필드 검증"""
    from shared.dto.pipeline_dto import VideoMetadata, VideoSource

    vm = VideoMetadata(
        source_type=VideoSource.LOCAL_FILE,
        source_path="/video/game.mp4",
        filename="game.mp4",
        file_size_bytes=1048576,
        duration_seconds=3600.0,
        width=1920, height=1080,
        fps=30.0,
        codec="h264",
    )
    assert_eq(r, "filename", vm.filename, "game.mp4")
    assert_eq(r, "file_size_bytes", vm.file_size_bytes, 1048576)
    assert_close(r, "duration_seconds", vm.duration_seconds, 3600.0)
    assert_eq(r, "width", vm.width, 1920)
    assert_eq(r, "height", vm.height, 1080)
    assert_close(r, "fps", vm.fps, 30.0)
    assert_eq(r, "codec", vm.codec, "h264")


# ==================== [D] PipelineOptions ====================
def test_pipeline_options_defaults(r: TestResult) -> None:
    """PipelineOptions 기본값 검증"""
    from shared.dto.pipeline_dto import PipelineOptions
    from shared.constants.localization import SupportedLanguage

    opts = PipelineOptions()
    assert_eq(r, "기본 quality = 'high'", opts.quality, "high")
    assert_eq(r, "기본 target_fps = 30", opts.target_fps, 30)
    assert_close(r, "기본 detection_confidence = 0.7", opts.detection_confidence, 0.7)
    assert_close(r, "기본 pose_confidence = 0.5", opts.pose_confidence, 0.5)
    assert_close(r, "기본 tracking_iou = 0.3", opts.tracking_iou, 0.3)
    assert_none(r, "기본 start_time = None", opts.start_time)
    assert_none(r, "기본 end_time = None", opts.end_time)
    assert_true(r, "기본 enable_highlight = True", opts.enable_highlight)
    assert_true(r, "기본 enable_feedback = True", opts.enable_feedback)
    assert_true(r, "기본 enable_biomechanics = True", opts.enable_biomechanics)
    assert_eq(r, "기본 feedback_language = KO", opts.feedback_language, SupportedLanguage.KO)
    assert_eq(r, "기본 feedback_detail_level = 'detailed'", opts.feedback_detail_level, "detailed")


def test_pipeline_options_quality_pattern(r: TestResult) -> None:
    """PipelineOptions quality 패턴 검증"""
    from shared.dto.pipeline_dto import PipelineOptions
    from pydantic import ValidationError

    for valid_q in ["low", "medium", "high", "ultra"]:
        opts = PipelineOptions(quality=valid_q)
        assert_eq(r, f"quality '{valid_q}' 허용", opts.quality, valid_q)

    assert_raises(r, "quality 'invalid' 거부", ValidationError,
                  lambda: PipelineOptions(quality="invalid"))


def test_pipeline_options_feedback_level_pattern(r: TestResult) -> None:
    """PipelineOptions feedback_detail_level 패턴 검증"""
    from shared.dto.pipeline_dto import PipelineOptions
    from pydantic import ValidationError

    for valid_l in ["simple", "detailed", "technical", "expert"]:
        opts = PipelineOptions(feedback_detail_level=valid_l)
        assert_eq(r, f"feedback_level '{valid_l}' 허용", opts.feedback_detail_level, valid_l)

    assert_raises(r, "feedback_level 'verbose' 거부", ValidationError,
                  lambda: PipelineOptions(feedback_detail_level="verbose"))


def test_pipeline_options_time_range_validation(r: TestResult) -> None:
    """PipelineOptions 시간 범위 검증"""
    from shared.dto.pipeline_dto import PipelineOptions
    from pydantic import ValidationError

    # 유효한 시간 범위
    opts = PipelineOptions(start_time=10.0, end_time=60.0)
    assert_close(r, "start_time 설정", opts.start_time, 10.0)
    assert_close(r, "end_time 설정", opts.end_time, 60.0)

    # end_time <= start_time 거부
    assert_raises(r, "end <= start 거부", ValidationError,
                  lambda: PipelineOptions(start_time=60.0, end_time=30.0))
    assert_raises(r, "end == start 거부", ValidationError,
                  lambda: PipelineOptions(start_time=30.0, end_time=30.0))


def test_pipeline_options_frozen(r: TestResult) -> None:
    """PipelineOptions frozen 검증"""
    from shared.dto.pipeline_dto import PipelineOptions

    opts = PipelineOptions()
    try:
        opts.quality = "low"
        r.fail("PipelineOptions frozen", "mutation 허용됨")
    except Exception:
        r.ok("PipelineOptions frozen")


# ==================== [E] BasePipelineRequest ====================
def test_base_pipeline_request(r: TestResult) -> None:
    """BasePipelineRequest 기본 필드 검증"""
    from shared.dto.pipeline_dto import BasePipelineRequest, VideoMetadata
    from shared.constants.status_codes import AnalysisType

    req = BasePipelineRequest(
        analysis_type=AnalysisType.GAME_FULL,
        video=VideoMetadata(source_path="/game.mp4"),
    )
    assert_isinstance(r, "request_id는 UUID", req.request_id, UUID)
    assert_eq(r, "analysis_type = GAME_FULL", req.analysis_type, AnalysisType.GAME_FULL)
    assert_not_none(r, "video != None", req.video)
    assert_not_none(r, "options 기본값", req.options)
    assert_none(r, "기본 backend_sync_url = None", req.backend_sync_url)
    assert_none(r, "기본 backend_auth_token = None", req.backend_auth_token)
    assert_eq(r, "기본 client_metadata = {}", req.client_metadata, {})
    assert_eq(r, "기본 priority = 5", req.priority, 5)
    assert_not_none(r, "created_at 자동", req.created_at)


def test_base_pipeline_request_frozen(r: TestResult) -> None:
    """BasePipelineRequest frozen 검증"""
    from shared.dto.pipeline_dto import BasePipelineRequest, VideoMetadata
    from shared.constants.status_codes import AnalysisType

    req = BasePipelineRequest(
        analysis_type=AnalysisType.GAME_FULL,
        video=VideoMetadata(source_path="/game.mp4"),
    )
    try:
        req.priority = 1
        r.fail("BasePipelineRequest frozen", "mutation 허용됨")
    except Exception:
        r.ok("BasePipelineRequest frozen")


# ==================== [F] GameAnalysisRequest ====================
def test_game_analysis_request(r: TestResult) -> None:
    """GameAnalysisRequest 생성 및 필드 검증"""
    from shared.dto.pipeline_dto import GameAnalysisRequest, VideoMetadata
    from shared.constants.status_codes import AnalysisType

    req = GameAnalysisRequest(
        analysis_type=AnalysisType.GAME_FULL,
        video=VideoMetadata(source_path="/game.mp4"),
        home_team_id="team_a",
        away_team_id="team_b",
        home_team_name="Eagles",
        away_team_name="Lions",
        venue="서울 체육관",
        league="KBL",
    )
    assert_eq(r, "home_team_id", req.home_team_id, "team_a")
    assert_eq(r, "away_team_id", req.away_team_id, "team_b")
    assert_eq(r, "home_team_name", req.home_team_name, "Eagles")
    assert_eq(r, "venue", req.venue, "서울 체육관")
    assert_eq(r, "league", req.league, "KBL")


def test_game_analysis_request_valid_types(r: TestResult) -> None:
    """GameAnalysisRequest 유효 분석 타입 검증"""
    from shared.dto.pipeline_dto import GameAnalysisRequest, VideoMetadata
    from shared.constants.status_codes import AnalysisType

    for at in [AnalysisType.GAME_FULL, AnalysisType.GAME_HIGHLIGHTS,
               AnalysisType.GAME_STATISTICS, AnalysisType.GAME_SHOT_CHART]:
        req = GameAnalysisRequest(
            analysis_type=at,
            video=VideoMetadata(source_path="/game.mp4"),
        )
        assert_eq(r, f"GameAnalysis {at.name} 허용", req.analysis_type, at)


def test_game_analysis_request_invalid_type(r: TestResult) -> None:
    """GameAnalysisRequest 잘못된 분석 타입 거부"""
    from shared.dto.pipeline_dto import GameAnalysisRequest, VideoMetadata
    from shared.constants.status_codes import AnalysisType
    from pydantic import ValidationError

    assert_raises(r, "REFEREE_FULL 거부", ValidationError,
                  lambda: GameAnalysisRequest(
                      analysis_type=AnalysisType.REFEREE_FULL,
                      video=VideoMetadata(source_path="/game.mp4"),
                  ))
    assert_raises(r, "TRAINING_SHOOTING 거부", ValidationError,
                  lambda: GameAnalysisRequest(
                      analysis_type=AnalysisType.TRAINING_SHOOTING,
                      video=VideoMetadata(source_path="/game.mp4"),
                  ))


# ==================== [G] RefereeAnalysisRequest ====================
def test_referee_analysis_request(r: TestResult) -> None:
    """RefereeAnalysisRequest 생성 및 필드 검증"""
    from shared.dto.pipeline_dto import RefereeAnalysisRequest, VideoMetadata
    from shared.constants.status_codes import AnalysisType
    from shared.constants.referee_rule_constants import RuleSet

    req = RefereeAnalysisRequest(
        video=VideoMetadata(source_path="/game.mp4"),
    )
    # 기본값
    assert_eq(r, "기본 analysis_type = REFEREE_VIOLATION", req.analysis_type, AnalysisType.REFEREE_VIOLATION)
    assert_eq(r, "기본 priority = 3", req.priority, 3)
    assert_eq(r, "기본 rule_set = FIBA", req.rule_set, RuleSet.FIBA)
    assert_eq(r, "기본 sensitivity = 'medium'", req.sensitivity, "medium")
    assert_false(r, "기본 realtime_mode = False", req.realtime_mode)


def test_referee_analysis_request_valid_types(r: TestResult) -> None:
    """RefereeAnalysisRequest 유효 분석 타입 검증"""
    from shared.dto.pipeline_dto import RefereeAnalysisRequest, VideoMetadata
    from shared.constants.status_codes import AnalysisType

    for at in [AnalysisType.REFEREE_FULL, AnalysisType.REFEREE_VIOLATION, AnalysisType.REFEREE_FOUL]:
        req = RefereeAnalysisRequest(
            analysis_type=at,
            video=VideoMetadata(source_path="/game.mp4"),
        )
        assert_eq(r, f"RefereeAnalysis {at.name} 허용", req.analysis_type, at)


def test_referee_analysis_request_invalid_type(r: TestResult) -> None:
    """RefereeAnalysisRequest 잘못된 분석 타입 거부"""
    from shared.dto.pipeline_dto import RefereeAnalysisRequest, VideoMetadata
    from shared.constants.status_codes import AnalysisType
    from pydantic import ValidationError

    assert_raises(r, "GAME_FULL 거부", ValidationError,
                  lambda: RefereeAnalysisRequest(
                      analysis_type=AnalysisType.GAME_FULL,
                      video=VideoMetadata(source_path="/game.mp4"),
                  ))


def test_referee_sensitivity_pattern(r: TestResult) -> None:
    """RefereeAnalysisRequest sensitivity 패턴 검증"""
    from shared.dto.pipeline_dto import RefereeAnalysisRequest, VideoMetadata
    from pydantic import ValidationError

    for s in ["low", "medium", "high"]:
        req = RefereeAnalysisRequest(
            video=VideoMetadata(source_path="/game.mp4"),
            sensitivity=s,
        )
        assert_eq(r, f"sensitivity '{s}' 허용", req.sensitivity, s)

    assert_raises(r, "sensitivity 'ultra' 거부", ValidationError,
                  lambda: RefereeAnalysisRequest(
                      video=VideoMetadata(source_path="/game.mp4"),
                      sensitivity="ultra",
                  ))


# ==================== [H] PipelineRequest Union ====================
def test_pipeline_request_union(r: TestResult) -> None:
    """PipelineRequest Union 타입 검증"""
    from shared.dto.pipeline_dto import (
        PipelineRequest, GameAnalysisRequest, RefereeAnalysisRequest,
    )
    import types
    import typing

    # Python 3.10+ X | Y → types.UnionType
    args = typing.get_args(PipelineRequest)
    is_union = isinstance(PipelineRequest, (type(typing.Union[int, str]), types.UnionType))
    assert_true(r, "PipelineRequest는 Union", is_union)
    assert_true(r, "GameAnalysisRequest 포함", GameAnalysisRequest in args)
    assert_true(r, "RefereeAnalysisRequest 포함", RefereeAnalysisRequest in args)


# ==================== [I] PipelineProgress ====================
def test_pipeline_progress(r: TestResult) -> None:
    """PipelineProgress 생성 및 필드 검증"""
    from shared.dto.pipeline_dto import PipelineProgress
    from shared.constants.status_codes import TaskStatus, AnalysisPhase

    task_id = uuid4()
    req_id = uuid4()
    pp = PipelineProgress(
        task_id=task_id,
        request_id=req_id,
        status=TaskStatus.RUNNING,
        phase=AnalysisPhase.DETECTING,
        progress_percent=45.5,
        current_frame=1000,
        total_frames=3000,
        processed_frames=1000,
        processing_fps=28.5,
    )
    assert_eq(r, "task_id", pp.task_id, task_id)
    assert_eq(r, "status = RUNNING", pp.status, TaskStatus.RUNNING)
    assert_eq(r, "phase = DETECTING", pp.phase, AnalysisPhase.DETECTING)
    assert_close(r, "progress_percent = 45.5", pp.progress_percent, 45.5)
    assert_eq(r, "current_frame = 1000", pp.current_frame, 1000)
    assert_eq(r, "total_frames = 3000", pp.total_frames, 3000)
    assert_close(r, "processing_fps = 28.5", pp.processing_fps, 28.5)
    assert_not_none(r, "updated_at 자동", pp.updated_at)


def test_pipeline_progress_frozen(r: TestResult) -> None:
    """PipelineProgress frozen 검증"""
    from shared.dto.pipeline_dto import PipelineProgress
    from shared.constants.status_codes import TaskStatus, AnalysisPhase

    pp = PipelineProgress(
        task_id=uuid4(), request_id=uuid4(),
        status=TaskStatus.RUNNING, phase=AnalysisPhase.DETECTING,
    )
    try:
        pp.progress_percent = 50.0
        r.fail("PipelineProgress frozen", "mutation 허용됨")
    except Exception:
        r.ok("PipelineProgress frozen")


# ==================== [J] PipelineResultBase ====================
def test_pipeline_result_base(r: TestResult) -> None:
    """PipelineResultBase 필드 검증"""
    from shared.dto.pipeline_dto import PipelineResultBase
    from shared.constants.status_codes import TaskStatus, AnalysisType

    now = datetime.now(timezone.utc)
    result = PipelineResultBase(
        task_id=uuid4(), request_id=uuid4(),
        analysis_type=AnalysisType.GAME_FULL,
        status=TaskStatus.COMPLETED, success=True,
        started_at=now, completed_at=now,
        processing_time_seconds=120.0,
        total_frames=5400, processed_frames=5400,
        average_fps=45.0,
    )
    assert_true(r, "success = True", result.success)
    assert_close(r, "processing_time = 120", result.processing_time_seconds, 120.0)
    assert_eq(r, "total_frames = 5400", result.total_frames, 5400)
    assert_close(r, "average_fps = 45.0", result.average_fps, 45.0)
    assert_none(r, "기본 result_dir = None", result.result_dir)
    assert_none(r, "기본 error_code = None", result.error_code)


# ==================== [K] GameAnalysisResult ====================
def test_game_analysis_result(r: TestResult) -> None:
    """GameAnalysisResult 필드 검증"""
    from shared.dto.pipeline_dto import GameAnalysisResult
    from shared.constants.status_codes import TaskStatus, AnalysisType

    now = datetime.now(timezone.utc)
    result = GameAnalysisResult(
        task_id=uuid4(), request_id=uuid4(),
        analysis_type=AnalysisType.GAME_FULL,
        status=TaskStatus.COMPLETED, success=True,
        started_at=now, completed_at=now,
        processing_time_seconds=300.0,
        total_frames=10800, processed_frames=10800,
        average_fps=36.0,
        home_team_id="team_a", away_team_id="team_b",
        home_score=78, away_score=72,
        total_shots=120, total_baskets=60,
        total_assists=25, total_rebounds=80,
        total_turnovers=15,
    )
    assert_eq(r, "home_score = 78", result.home_score, 78)
    assert_eq(r, "away_score = 72", result.away_score, 72)
    assert_eq(r, "total_shots = 120", result.total_shots, 120)
    assert_eq(r, "total_baskets = 60", result.total_baskets, 60)
    assert_eq(r, "total_assists = 25", result.total_assists, 25)
    assert_eq(r, "total_rebounds = 80", result.total_rebounds, 80)
    assert_eq(r, "total_turnovers = 15", result.total_turnovers, 15)


def test_game_analysis_result_defaults(r: TestResult) -> None:
    """GameAnalysisResult 기본값 검증"""
    from shared.dto.pipeline_dto import GameAnalysisResult
    from shared.constants.status_codes import TaskStatus, AnalysisType

    now = datetime.now(timezone.utc)
    result = GameAnalysisResult(
        task_id=uuid4(), request_id=uuid4(),
        analysis_type=AnalysisType.GAME_FULL,
        status=TaskStatus.COMPLETED, success=True,
        started_at=now, completed_at=now,
        processing_time_seconds=0.0,
        total_frames=0, processed_frames=0, average_fps=0.0,
    )
    assert_eq(r, "기본 home_score = 0", result.home_score, 0)
    assert_eq(r, "기본 away_score = 0", result.away_score, 0)
    assert_eq(r, "기본 total_shots = 0", result.total_shots, 0)
    assert_none(r, "기본 game_stats_id = None", result.game_stats_id)
    assert_none(r, "기본 shot_chart_id = None", result.shot_chart_id)
    assert_none(r, "기본 highlight_reel_id = None", result.highlight_reel_id)


# ==================== [L] ViolationCounts / FoulCounts ====================
def test_violation_counts(r: TestResult) -> None:
    """ViolationCounts 생성 및 total 프로퍼티 검증"""
    from shared.dto.pipeline_dto import ViolationCounts

    # 기본값
    vc_default = ViolationCounts()
    assert_eq(r, "ViolationCounts 기본 total = 0", vc_default.total, 0)

    # 값 설정
    vc = ViolationCounts(
        traveling=3, double_dribble=2, carrying=1,
        three_seconds=4, five_seconds=1, eight_seconds=0,
        shot_clock=2, out_of_bounds=5,
    )
    assert_eq(r, "ViolationCounts total = 18", vc.total, 18)
    assert_eq(r, "traveling = 3", vc.traveling, 3)
    assert_eq(r, "double_dribble = 2", vc.double_dribble, 2)
    assert_eq(r, "shot_clock = 2", vc.shot_clock, 2)


def test_violation_counts_frozen(r: TestResult) -> None:
    """ViolationCounts frozen 검증"""
    from shared.dto.pipeline_dto import ViolationCounts

    vc = ViolationCounts(traveling=1)
    try:
        vc.traveling = 5
        r.fail("ViolationCounts frozen", "mutation 허용됨")
    except Exception:
        r.ok("ViolationCounts frozen")


def test_foul_counts(r: TestResult) -> None:
    """FoulCounts 생성 및 total 프로퍼티 검증"""
    from shared.dto.pipeline_dto import FoulCounts

    # 기본값
    fc_default = FoulCounts()
    assert_eq(r, "FoulCounts 기본 total = 0", fc_default.total, 0)

    # 값 설정
    fc = FoulCounts(personal=10, offensive=3, technical=2, flagrant=1)
    assert_eq(r, "FoulCounts total = 16", fc.total, 16)
    assert_eq(r, "personal = 10", fc.personal, 10)
    assert_eq(r, "offensive = 3", fc.offensive, 3)
    assert_eq(r, "technical = 2", fc.technical, 2)
    assert_eq(r, "flagrant = 1", fc.flagrant, 1)


def test_foul_counts_frozen(r: TestResult) -> None:
    """FoulCounts frozen 검증"""
    from shared.dto.pipeline_dto import FoulCounts

    fc = FoulCounts(personal=5)
    try:
        fc.personal = 10
        r.fail("FoulCounts frozen", "mutation 허용됨")
    except Exception:
        r.ok("FoulCounts frozen")


# ==================== [M] RefereeAnalysisResult ====================
def test_referee_analysis_result(r: TestResult) -> None:
    """RefereeAnalysisResult 생성 및 프로퍼티 검증"""
    from shared.dto.pipeline_dto import (
        RefereeAnalysisResult, ViolationCounts, FoulCounts,
    )
    from shared.constants.status_codes import TaskStatus, AnalysisType
    from shared.constants.referee_rule_constants import RuleSet

    now = datetime.now(timezone.utc)
    vc = ViolationCounts(traveling=3, double_dribble=2, shot_clock=1)
    fc = FoulCounts(personal=8, offensive=2, technical=1, flagrant=0)

    result = RefereeAnalysisResult(
        task_id=uuid4(), request_id=uuid4(),
        analysis_type=AnalysisType.REFEREE_FULL,
        status=TaskStatus.COMPLETED, success=True,
        started_at=now, completed_at=now,
        processing_time_seconds=180.0,
        total_frames=5400, processed_frames=5400,
        average_fps=30.0,
        rule_set=RuleSet.FIBA,
        violation_counts=vc,
        foul_counts=fc,
        average_confidence=0.87,
    )
    assert_eq(r, "total_violations = 6", result.total_violations, 6)
    assert_eq(r, "total_fouls = 11", result.total_fouls, 11)
    assert_eq(r, "rule_set = FIBA", result.rule_set, RuleSet.FIBA)
    assert_close(r, "average_confidence = 0.87", result.average_confidence, 0.87)


def test_referee_analysis_result_defaults(r: TestResult) -> None:
    """RefereeAnalysisResult 기본 중첩 모델 검증"""
    from shared.dto.pipeline_dto import RefereeAnalysisResult
    from shared.constants.status_codes import TaskStatus, AnalysisType
    from shared.constants.referee_rule_constants import RuleSet

    now = datetime.now(timezone.utc)
    result = RefereeAnalysisResult(
        task_id=uuid4(), request_id=uuid4(),
        analysis_type=AnalysisType.REFEREE_FULL,
        status=TaskStatus.COMPLETED, success=True,
        started_at=now, completed_at=now,
        processing_time_seconds=0.0,
        total_frames=0, processed_frames=0, average_fps=0.0,
        rule_set=RuleSet.NBA,
    )
    assert_eq(r, "기본 violation_counts.total = 0", result.violation_counts.total, 0)
    assert_eq(r, "기본 foul_counts.total = 0", result.foul_counts.total, 0)
    assert_eq(r, "기본 total_violations = 0", result.total_violations, 0)
    assert_eq(r, "기본 total_fouls = 0", result.total_fouls, 0)


# ==================== [N] SyncEventType Enum ====================
def test_sync_event_type(r: TestResult) -> None:
    """SyncEventType Enum 검증"""
    from shared.dto.pipeline_dto import SyncEventType

    expected = ["ANALYSIS_COMPLETED", "ANALYSIS_FAILED"]
    actual = [m.name for m in SyncEventType]
    assert_eq(r, "SyncEventType 멤버 수 = 2", len(actual), 2)
    for name in expected:
        assert_true(r, f"SyncEventType.{name} 존재", name in actual)

    assert_eq(r, "COMPLETED.value", SyncEventType.ANALYSIS_COMPLETED.value, "analysis.completed")
    assert_eq(r, "FAILED.value", SyncEventType.ANALYSIS_FAILED.value, "analysis.failed")

    # __str__ 검증
    assert_eq(r, "__str__ COMPLETED", str(SyncEventType.ANALYSIS_COMPLETED), "analysis.completed")
    assert_isinstance(r, "str Enum", SyncEventType.ANALYSIS_COMPLETED, str)


# ==================== [O] BackendSyncPayload ====================
def test_backend_sync_payload(r: TestResult) -> None:
    """BackendSyncPayload 생성 및 필드 검증"""
    from shared.dto.pipeline_dto import BackendSyncPayload, SyncEventType
    from shared.constants.status_codes import TaskStatus, AnalysisType

    now = datetime.now(timezone.utc)
    task_id = uuid4()
    req_id = uuid4()

    payload = BackendSyncPayload(
        event_type=SyncEventType.ANALYSIS_COMPLETED,
        task_id=task_id, request_id=req_id,
        analysis_type=AnalysisType.GAME_FULL,
        success=True, status=TaskStatus.COMPLETED,
        processing_time_seconds=120.0,
        completed_at=now,
        summary={"home_score": 78, "away_score": 72},
        client_metadata={"user_id": "user_001"},
    )
    assert_eq(r, "event_type = COMPLETED", payload.event_type, SyncEventType.ANALYSIS_COMPLETED)
    assert_eq(r, "task_id 일치", payload.task_id, task_id)
    assert_true(r, "success = True", payload.success)
    assert_close(r, "processing_time = 120.0", payload.processing_time_seconds, 120.0)
    assert_eq(r, "summary 설정", payload.summary, {"home_score": 78, "away_score": 72})
    assert_eq(r, "client_metadata", payload.client_metadata, {"user_id": "user_001"})


def test_backend_sync_payload_frozen(r: TestResult) -> None:
    """BackendSyncPayload frozen 검증"""
    from shared.dto.pipeline_dto import BackendSyncPayload, SyncEventType
    from shared.constants.status_codes import TaskStatus, AnalysisType

    now = datetime.now(timezone.utc)
    payload = BackendSyncPayload(
        task_id=uuid4(), request_id=uuid4(),
        analysis_type=AnalysisType.GAME_FULL,
        success=True, status=TaskStatus.COMPLETED,
        processing_time_seconds=0.0, completed_at=now,
    )
    try:
        payload.success = False
        r.fail("BackendSyncPayload frozen", "mutation 허용됨")
    except Exception:
        r.ok("BackendSyncPayload frozen")


def test_backend_sync_payload_defaults(r: TestResult) -> None:
    """BackendSyncPayload 기본값 검증"""
    from shared.dto.pipeline_dto import BackendSyncPayload, SyncEventType
    from shared.constants.status_codes import TaskStatus, AnalysisType

    now = datetime.now(timezone.utc)
    payload = BackendSyncPayload(
        task_id=uuid4(), request_id=uuid4(),
        analysis_type=AnalysisType.GAME_FULL,
        success=True, status=TaskStatus.COMPLETED,
        processing_time_seconds=0.0, completed_at=now,
    )
    assert_eq(r, "기본 event_type = COMPLETED", payload.event_type, SyncEventType.ANALYSIS_COMPLETED)
    assert_none(r, "기본 summary = None", payload.summary)
    assert_none(r, "기본 error_code = None", payload.error_code)
    assert_none(r, "기본 error_message = None", payload.error_message)
    assert_eq(r, "기본 client_metadata = {}", payload.client_metadata, {})


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("pipeline_dto.py v1.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- [A] __all__ / __version__ ---")
    test_exports(r)
    test_version(r)

    print("\n--- [B] VideoSource Enum ---")
    test_video_source_members(r)

    print("\n--- [C] VideoMetadata ---")
    test_video_metadata_basic(r)
    test_video_metadata_frozen(r)
    test_video_metadata_source_path_required(r)
    test_video_metadata_stream_url_validation(r)
    test_video_metadata_full_fields(r)

    print("\n--- [D] PipelineOptions ---")
    test_pipeline_options_defaults(r)
    test_pipeline_options_quality_pattern(r)
    test_pipeline_options_feedback_level_pattern(r)
    test_pipeline_options_time_range_validation(r)
    test_pipeline_options_frozen(r)

    print("\n--- [E] BasePipelineRequest ---")
    test_base_pipeline_request(r)
    test_base_pipeline_request_frozen(r)

    print("\n--- [F] GameAnalysisRequest ---")
    test_game_analysis_request(r)
    test_game_analysis_request_valid_types(r)
    test_game_analysis_request_invalid_type(r)

    print("\n--- [G] RefereeAnalysisRequest ---")
    test_referee_analysis_request(r)
    test_referee_analysis_request_valid_types(r)
    test_referee_analysis_request_invalid_type(r)
    test_referee_sensitivity_pattern(r)

    print("\n--- [H] PipelineRequest Union ---")
    test_pipeline_request_union(r)

    print("\n--- [I] PipelineProgress ---")
    test_pipeline_progress(r)
    test_pipeline_progress_frozen(r)

    print("\n--- [J] PipelineResultBase ---")
    test_pipeline_result_base(r)

    print("\n--- [K] GameAnalysisResult ---")
    test_game_analysis_result(r)
    test_game_analysis_result_defaults(r)

    print("\n--- [L] ViolationCounts / FoulCounts ---")
    test_violation_counts(r)
    test_violation_counts_frozen(r)
    test_foul_counts(r)
    test_foul_counts_frozen(r)

    print("\n--- [M] RefereeAnalysisResult ---")
    test_referee_analysis_result(r)
    test_referee_analysis_result_defaults(r)

    print("\n--- [N] SyncEventType ---")
    test_sync_event_type(r)

    print("\n--- [O] BackendSyncPayload ---")
    test_backend_sync_payload(r)
    test_backend_sync_payload_frozen(r)
    test_backend_sync_payload_defaults(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
