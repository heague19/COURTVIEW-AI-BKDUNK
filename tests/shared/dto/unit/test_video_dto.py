# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_video_dto.py

비디오 메타데이터 DTO 유닛 테스트
- 모듈 구조 검증 (__all__, __version__)
- Enum 5개: VideoFormat, VideoType, FrameStatus, VideoCodec, AudioCodec
  - 멤버 값/개수, 프로퍼티, i18n(5개 언어), to_korean
- Dataclass 5개: VideoResolution, VideoMetadata, FrameData, VideoSegment, VideoInfo
  - 기본값, 입력값, __post_init__, 프로퍼티, 메서드
- 필드 수 검증, 가변 기본값 격리 검증

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import sys
import io
from dataclasses import fields
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def eq(self, name: str, actual, expected) -> None:
        if actual == expected:
            self.ok(name)
        else:
            self.fail(name, f"expected {expected!r}, got {actual!r}")

    def true(self, name: str, value: bool) -> None:
        if value:
            self.ok(name)
        else:
            self.fail(name, "expected True, got False")

    def false(self, name: str, value: bool) -> None:
        if not value:
            self.ok(name)
        else:
            self.fail(name, "expected False, got True")

    def is_none(self, name: str, value) -> None:
        if value is None:
            self.ok(name)
        else:
            self.fail(name, f"expected None, got {value!r}")

    def is_not_none(self, name: str, value) -> None:
        if value is not None:
            self.ok(name)
        else:
            self.fail(name, "expected not None, got None")

    def is_instance(self, name: str, obj, cls) -> None:
        if isinstance(obj, cls):
            self.ok(name)
        else:
            self.fail(name, f"expected {cls.__name__}, got {type(obj).__name__}")

    def approx(self, name: str, actual: float, expected: float, tol: float = 1e-6) -> None:
        if abs(actual - expected) < tol:
            self.ok(name)
        else:
            self.fail(name, f"expected ~{expected}, got {actual}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==============================================================
# [A] 모듈 구조 검증
# ==============================================================
def test_module_structure(r: TestResult) -> None:
    """__all__, __version__ 검증"""
    from shared.dto.video_dto import __all__, __version__

    r.eq("__version__", __version__, "2.0.0")
    r.eq("__all__ 길이", len(__all__), 10)

    expected_names = [
        "VideoFormat", "VideoType", "FrameStatus", "VideoCodec", "AudioCodec",
        "VideoResolution", "VideoMetadata", "FrameData", "VideoSegment", "VideoInfo",
    ]
    for name in expected_names:
        r.true(f"__all__에 {name} 포함", name in __all__)


# ==============================================================
# [B] VideoFormat Enum
# ==============================================================
def test_video_format_members(r: TestResult) -> None:
    """VideoFormat 멤버 검증"""
    from shared.dto.video_dto import VideoFormat

    r.eq("VideoFormat 멤버 수", len(VideoFormat), 7)
    r.eq("MP4", VideoFormat.MP4.value, "mp4")
    r.eq("AVI", VideoFormat.AVI.value, "avi")
    r.eq("MOV", VideoFormat.MOV.value, "mov")
    r.eq("MKV", VideoFormat.MKV.value, "mkv")
    r.eq("WEBM", VideoFormat.WEBM.value, "webm")
    r.eq("FLV", VideoFormat.FLV.value, "flv")
    r.eq("WMV", VideoFormat.WMV.value, "wmv")


def test_video_format_mime_type(r: TestResult) -> None:
    """VideoFormat.mime_type 프로퍼티"""
    from shared.dto.video_dto import VideoFormat

    r.eq("MP4 MIME", VideoFormat.MP4.mime_type, "video/mp4")
    r.eq("AVI MIME", VideoFormat.AVI.mime_type, "video/x-msvideo")
    r.eq("MOV MIME", VideoFormat.MOV.mime_type, "video/quicktime")
    r.eq("MKV MIME", VideoFormat.MKV.mime_type, "video/x-matroska")
    r.eq("WEBM MIME", VideoFormat.WEBM.mime_type, "video/webm")
    r.eq("FLV MIME", VideoFormat.FLV.mime_type, "video/x-flv")
    r.eq("WMV MIME", VideoFormat.WMV.mime_type, "video/x-ms-wmv")


def test_video_format_extension(r: TestResult) -> None:
    """VideoFormat.extension 프로퍼티"""
    from shared.dto.video_dto import VideoFormat

    r.eq("MP4 확장자", VideoFormat.MP4.extension, ".mp4")
    r.eq("AVI 확장자", VideoFormat.AVI.extension, ".avi")
    r.eq("MKV 확장자", VideoFormat.MKV.extension, ".mkv")


def test_video_format_from_extension(r: TestResult) -> None:
    """VideoFormat.from_extension 클래스메서드"""
    from shared.dto.video_dto import VideoFormat

    r.eq("from mp4", VideoFormat.from_extension("mp4"), VideoFormat.MP4)
    r.eq("from .avi", VideoFormat.from_extension(".avi"), VideoFormat.AVI)
    r.eq("from .MOV (대소문자)", VideoFormat.from_extension(".MOV"), VideoFormat.MOV)
    r.is_none("from .xyz (없음)", VideoFormat.from_extension(".xyz"))
    r.eq("from webm", VideoFormat.from_extension("webm"), VideoFormat.WEBM)


def test_video_format_get_name(r: TestResult) -> None:
    """VideoFormat.get_name (기술적 용어 그대로)"""
    from shared.dto.video_dto import VideoFormat
    from shared.constants.localization import SupportedLanguage

    # VideoFormat은 기술적 용어 → value.upper() 반환
    r.eq("MP4 get_name(KO)", VideoFormat.MP4.get_name(SupportedLanguage.KO), "MP4")
    r.eq("AVI get_name(EN)", VideoFormat.AVI.get_name(SupportedLanguage.EN), "AVI")
    r.eq("MOV get_name(JA)", VideoFormat.MOV.get_name(SupportedLanguage.JA), "MOV")


def test_video_format_str_enum(r: TestResult) -> None:
    """VideoFormat은 str Enum"""
    from shared.dto.video_dto import VideoFormat

    r.is_instance("str 서브클래스", VideoFormat.MP4, str)
    r.eq("str 비교", VideoFormat.MP4, "mp4")


# ==============================================================
# [C] VideoType Enum
# ==============================================================
def test_video_type_members(r: TestResult) -> None:
    """VideoType 멤버 검증"""
    from shared.dto.video_dto import VideoType

    r.eq("VideoType 멤버 수", len(VideoType), 7)
    r.eq("TRAINING", VideoType.TRAINING.value, "training")
    r.eq("GAME", VideoType.GAME.value, "game")
    r.eq("HIGHLIGHT", VideoType.HIGHLIGHT.value, "highlight")
    r.eq("DRILL", VideoType.DRILL.value, "drill")
    r.eq("REFERENCE", VideoType.REFERENCE.value, "reference")
    r.eq("RAW", VideoType.RAW.value, "raw")
    r.eq("PROCESSED", VideoType.PROCESSED.value, "processed")


def test_video_type_to_korean(r: TestResult) -> None:
    """VideoType.to_korean 프로퍼티"""
    from shared.dto.video_dto import VideoType

    r.eq("TRAINING 한글", VideoType.TRAINING.to_korean, "훈련")
    r.eq("GAME 한글", VideoType.GAME.to_korean, "경기")
    r.eq("HIGHLIGHT 한글", VideoType.HIGHLIGHT.to_korean, "하이라이트")
    r.eq("RAW 한글", VideoType.RAW.to_korean, "원본")
    r.eq("PROCESSED 한글", VideoType.PROCESSED.to_korean, "처리됨")


def test_video_type_i18n(r: TestResult) -> None:
    """VideoType.get_name 다국어"""
    from shared.dto.video_dto import VideoType
    from shared.constants.localization import SupportedLanguage

    r.eq("KO 훈련", VideoType.TRAINING.get_name(SupportedLanguage.KO), "훈련")
    r.eq("EN Training", VideoType.TRAINING.get_name(SupportedLanguage.EN), "Training")
    r.eq("JA トレーニング", VideoType.TRAINING.get_name(SupportedLanguage.JA), "トレーニング")
    r.eq("ZH 训练", VideoType.TRAINING.get_name(SupportedLanguage.ZH), "训练")
    r.eq("ES Entrenamiento", VideoType.TRAINING.get_name(SupportedLanguage.ES), "Entrenamiento")

    r.eq("EN Game", VideoType.GAME.get_name(SupportedLanguage.EN), "Game")
    r.eq("JA 試合", VideoType.GAME.get_name(SupportedLanguage.JA), "試合")


# ==============================================================
# [D] FrameStatus Enum
# ==============================================================
def test_frame_status_members(r: TestResult) -> None:
    """FrameStatus 멤버 검증"""
    from shared.dto.video_dto import FrameStatus

    r.eq("FrameStatus 멤버 수", len(FrameStatus), 6)
    r.eq("VALID", FrameStatus.VALID.value, "valid")
    r.eq("CORRUPT", FrameStatus.CORRUPT.value, "corrupt")
    r.eq("SKIPPED", FrameStatus.SKIPPED.value, "skipped")
    r.eq("DUPLICATE", FrameStatus.DUPLICATE.value, "duplicate")
    r.eq("EMPTY", FrameStatus.EMPTY.value, "empty")
    r.eq("INTERPOLATED", FrameStatus.INTERPOLATED.value, "interpolated")


def test_frame_status_is_usable(r: TestResult) -> None:
    """FrameStatus.is_usable 프로퍼티"""
    from shared.dto.video_dto import FrameStatus

    r.true("VALID is_usable", FrameStatus.VALID.is_usable)
    r.true("INTERPOLATED is_usable", FrameStatus.INTERPOLATED.is_usable)
    r.false("CORRUPT is_usable", FrameStatus.CORRUPT.is_usable)
    r.false("SKIPPED is_usable", FrameStatus.SKIPPED.is_usable)
    r.false("DUPLICATE is_usable", FrameStatus.DUPLICATE.is_usable)
    r.false("EMPTY is_usable", FrameStatus.EMPTY.is_usable)


def test_frame_status_to_korean(r: TestResult) -> None:
    """FrameStatus.to_korean 프로퍼티"""
    from shared.dto.video_dto import FrameStatus

    r.eq("VALID 한글", FrameStatus.VALID.to_korean, "유효")
    r.eq("CORRUPT 한글", FrameStatus.CORRUPT.to_korean, "손상")
    r.eq("SKIPPED 한글", FrameStatus.SKIPPED.to_korean, "건너뜀")
    r.eq("EMPTY 한글", FrameStatus.EMPTY.to_korean, "빈 프레임")
    r.eq("INTERPOLATED 한글", FrameStatus.INTERPOLATED.to_korean, "보간됨")


def test_frame_status_i18n(r: TestResult) -> None:
    """FrameStatus.get_name 다국어"""
    from shared.dto.video_dto import FrameStatus
    from shared.constants.localization import SupportedLanguage

    r.eq("KO 유효", FrameStatus.VALID.get_name(SupportedLanguage.KO), "유효")
    r.eq("EN Valid", FrameStatus.VALID.get_name(SupportedLanguage.EN), "Valid")
    r.eq("JA 有効", FrameStatus.VALID.get_name(SupportedLanguage.JA), "有効")
    r.eq("ZH 有效", FrameStatus.VALID.get_name(SupportedLanguage.ZH), "有效")
    r.eq("ES Válido", FrameStatus.VALID.get_name(SupportedLanguage.ES), "Válido")

    r.eq("EN Corrupt", FrameStatus.CORRUPT.get_name(SupportedLanguage.EN), "Corrupt")
    r.eq("JA 補間済み", FrameStatus.INTERPOLATED.get_name(SupportedLanguage.JA), "補間済み")


# ==============================================================
# [E] VideoCodec Enum
# ==============================================================
def test_video_codec_members(r: TestResult) -> None:
    """VideoCodec 멤버 검증"""
    from shared.dto.video_dto import VideoCodec

    r.eq("VideoCodec 멤버 수", len(VideoCodec), 8)
    r.eq("H264", VideoCodec.H264.value, "h264")
    r.eq("H265", VideoCodec.H265.value, "h265")
    r.eq("VP8", VideoCodec.VP8.value, "vp8")
    r.eq("VP9", VideoCodec.VP9.value, "vp9")
    r.eq("AV1", VideoCodec.AV1.value, "av1")
    r.eq("MPEG4", VideoCodec.MPEG4.value, "mpeg4")
    r.eq("MJPEG", VideoCodec.MJPEG.value, "mjpeg")
    r.eq("UNKNOWN", VideoCodec.UNKNOWN.value, "unknown")


def test_video_codec_to_korean(r: TestResult) -> None:
    """VideoCodec.to_korean 프로퍼티"""
    from shared.dto.video_dto import VideoCodec

    r.eq("H264 한글", VideoCodec.H264.to_korean, "H.264")
    r.eq("H265 한글", VideoCodec.H265.to_korean, "H.265 (HEVC)")
    r.eq("UNKNOWN 한글", VideoCodec.UNKNOWN.to_korean, "알 수 없음")


def test_video_codec_i18n(r: TestResult) -> None:
    """VideoCodec.get_name 다국어"""
    from shared.dto.video_dto import VideoCodec
    from shared.constants.localization import SupportedLanguage

    r.eq("KO H.264", VideoCodec.H264.get_name(SupportedLanguage.KO), "H.264")
    r.eq("EN H.264", VideoCodec.H264.get_name(SupportedLanguage.EN), "H.264")
    r.eq("JA 不明", VideoCodec.UNKNOWN.get_name(SupportedLanguage.JA), "不明")
    r.eq("ZH 未知", VideoCodec.UNKNOWN.get_name(SupportedLanguage.ZH), "未知")
    r.eq("ES Desconocido", VideoCodec.UNKNOWN.get_name(SupportedLanguage.ES), "Desconocido")


# ==============================================================
# [F] AudioCodec Enum
# ==============================================================
def test_audio_codec_members(r: TestResult) -> None:
    """AudioCodec 멤버 검증"""
    from shared.dto.video_dto import AudioCodec

    r.eq("AudioCodec 멤버 수", len(AudioCodec), 7)
    r.eq("AAC", AudioCodec.AAC.value, "aac")
    r.eq("MP3", AudioCodec.MP3.value, "mp3")
    r.eq("OPUS", AudioCodec.OPUS.value, "opus")
    r.eq("VORBIS", AudioCodec.VORBIS.value, "vorbis")
    r.eq("PCM", AudioCodec.PCM.value, "pcm")
    r.eq("NONE", AudioCodec.NONE.value, "none")
    r.eq("UNKNOWN", AudioCodec.UNKNOWN.value, "unknown")


def test_audio_codec_to_korean(r: TestResult) -> None:
    """AudioCodec.to_korean 프로퍼티"""
    from shared.dto.video_dto import AudioCodec

    r.eq("AAC 한글", AudioCodec.AAC.to_korean, "AAC")
    r.eq("PCM 한글", AudioCodec.PCM.to_korean, "PCM (무압축)")
    r.eq("NONE 한글", AudioCodec.NONE.to_korean, "없음")
    r.eq("UNKNOWN 한글", AudioCodec.UNKNOWN.to_korean, "알 수 없음")


def test_audio_codec_i18n(r: TestResult) -> None:
    """AudioCodec.get_name 다국어"""
    from shared.dto.video_dto import AudioCodec
    from shared.constants.localization import SupportedLanguage

    r.eq("KO PCM", AudioCodec.PCM.get_name(SupportedLanguage.KO), "PCM (무압축)")
    r.eq("EN PCM", AudioCodec.PCM.get_name(SupportedLanguage.EN), "PCM (Uncompressed)")
    r.eq("JA PCM", AudioCodec.PCM.get_name(SupportedLanguage.JA), "PCM (非圧縮)")
    r.eq("ZH PCM", AudioCodec.PCM.get_name(SupportedLanguage.ZH), "PCM (无压缩)")
    r.eq("ES PCM", AudioCodec.PCM.get_name(SupportedLanguage.ES), "PCM (Sin comprimir)")

    r.eq("KO 없음", AudioCodec.NONE.get_name(SupportedLanguage.KO), "없음")
    r.eq("EN None", AudioCodec.NONE.get_name(SupportedLanguage.EN), "None")
    r.eq("JA なし", AudioCodec.NONE.get_name(SupportedLanguage.JA), "なし")


# ==============================================================
# [G] VideoResolution dataclass
# ==============================================================
def test_video_resolution_basic(r: TestResult) -> None:
    """VideoResolution 기본 생성"""
    from shared.dto.video_dto import VideoResolution

    vr = VideoResolution(width=1920, height=1080)
    r.eq("width", vr.width, 1920)
    r.eq("height", vr.height, 1080)


def test_video_resolution_properties(r: TestResult) -> None:
    """VideoResolution 프로퍼티"""
    from shared.dto.video_dto import VideoResolution

    vr = VideoResolution(width=1920, height=1080)
    r.approx("aspect_ratio", vr.aspect_ratio, 1920 / 1080, tol=0.01)
    r.eq("total_pixels", vr.total_pixels, 1920 * 1080)
    r.true("is_hd", vr.is_hd)
    r.true("is_full_hd", vr.is_full_hd)
    r.false("is_4k", vr.is_4k)


def test_video_resolution_hd_levels(r: TestResult) -> None:
    """HD/FHD/4K 단계별 검증"""
    from shared.dto.video_dto import VideoResolution

    sd = VideoResolution(width=640, height=480)
    r.false("SD is_hd", sd.is_hd)
    r.false("SD is_full_hd", sd.is_full_hd)
    r.false("SD is_4k", sd.is_4k)

    hd = VideoResolution(width=1280, height=720)
    r.true("HD is_hd", hd.is_hd)
    r.false("HD is_full_hd", hd.is_full_hd)

    uhd = VideoResolution(width=3840, height=2160)
    r.true("4K is_4k", uhd.is_4k)
    r.true("4K is_full_hd", uhd.is_full_hd)


def test_video_resolution_to_tuple(r: TestResult) -> None:
    """VideoResolution.to_tuple"""
    from shared.dto.video_dto import VideoResolution

    vr = VideoResolution(width=1920, height=1080)
    r.eq("to_tuple", vr.to_tuple(), (1920, 1080))


def test_video_resolution_str(r: TestResult) -> None:
    """VideoResolution.__str__"""
    from shared.dto.video_dto import VideoResolution

    vr = VideoResolution(width=1920, height=1080)
    r.eq("__str__", str(vr), "1920x1080")


def test_video_resolution_zero_height(r: TestResult) -> None:
    """VideoResolution height=0 경우 aspect_ratio"""
    from shared.dto.video_dto import VideoResolution

    vr = VideoResolution(width=1920, height=0)
    r.approx("aspect_ratio 0", vr.aspect_ratio, 0.0)


def test_video_resolution_field_count(r: TestResult) -> None:
    """VideoResolution 필드 수"""
    from shared.dto.video_dto import VideoResolution

    r.eq("VideoResolution 필드 수", len(fields(VideoResolution)), 2)


# ==============================================================
# [H] VideoMetadata dataclass
# ==============================================================
def test_video_metadata_basic(r: TestResult) -> None:
    """VideoMetadata 기본 생성"""
    from shared.dto.video_dto import VideoMetadata, VideoResolution, VideoCodec, AudioCodec

    res = VideoResolution(width=1920, height=1080)
    vm = VideoMetadata(duration=120.0, fps=30.0, resolution=res)

    r.approx("duration", vm.duration, 120.0)
    r.approx("fps", vm.fps, 30.0)
    r.eq("codec 기본", vm.codec, VideoCodec.H264)
    r.eq("audio_codec 기본", vm.audio_codec, AudioCodec.AAC)
    r.is_none("bitrate 기본", vm.bitrate)
    r.is_none("file_size 기본", vm.file_size)
    r.is_none("creation_time 기본", vm.creation_time)


def test_video_metadata_post_init_total_frames(r: TestResult) -> None:
    """VideoMetadata __post_init__: total_frames 자동 계산"""
    from shared.dto.video_dto import VideoMetadata, VideoResolution

    res = VideoResolution(width=1920, height=1080)
    vm = VideoMetadata(duration=120.0, fps=30.0, resolution=res)
    r.eq("total_frames 자동 계산", vm.total_frames, 3600)

    # total_frames 직접 지정
    vm2 = VideoMetadata(duration=120.0, fps=30.0, resolution=res, total_frames=4000)
    r.eq("total_frames 직접 지정", vm2.total_frames, 4000)


def test_video_metadata_duration_formatted(r: TestResult) -> None:
    """VideoMetadata.duration_formatted"""
    from shared.dto.video_dto import VideoMetadata, VideoResolution

    res = VideoResolution(width=1920, height=1080)
    vm = VideoMetadata(duration=3723.0, fps=30.0, resolution=res)
    r.eq("duration_formatted", vm.duration_formatted, "01:02:03")


def test_video_metadata_duration_timedelta(r: TestResult) -> None:
    """VideoMetadata.duration_timedelta"""
    from datetime import timedelta
    from shared.dto.video_dto import VideoMetadata, VideoResolution

    res = VideoResolution(width=1920, height=1080)
    vm = VideoMetadata(duration=120.0, fps=30.0, resolution=res)
    r.eq("duration_timedelta", vm.duration_timedelta, timedelta(seconds=120))


def test_video_metadata_file_size_mb(r: TestResult) -> None:
    """VideoMetadata.file_size_mb"""
    from shared.dto.video_dto import VideoMetadata, VideoResolution

    res = VideoResolution(width=1920, height=1080)
    vm1 = VideoMetadata(duration=60.0, fps=30.0, resolution=res)
    r.is_none("file_size_mb None", vm1.file_size_mb)

    vm2 = VideoMetadata(duration=60.0, fps=30.0, resolution=res, file_size=10485760)
    r.approx("file_size_mb 10MB", vm2.file_size_mb, 10.0)


def test_video_metadata_frame_to_time(r: TestResult) -> None:
    """VideoMetadata.frame_to_time"""
    from shared.dto.video_dto import VideoMetadata, VideoResolution

    res = VideoResolution(width=1920, height=1080)
    vm = VideoMetadata(duration=120.0, fps=30.0, resolution=res)
    r.approx("frame 0 → 0.0s", vm.frame_to_time(0), 0.0)
    r.approx("frame 30 → 1.0s", vm.frame_to_time(30), 1.0)
    r.approx("frame 150 → 5.0s", vm.frame_to_time(150), 5.0)


def test_video_metadata_time_to_frame(r: TestResult) -> None:
    """VideoMetadata.time_to_frame"""
    from shared.dto.video_dto import VideoMetadata, VideoResolution

    res = VideoResolution(width=1920, height=1080)
    vm = VideoMetadata(duration=120.0, fps=30.0, resolution=res)
    r.eq("0.0s → frame 0", vm.time_to_frame(0.0), 0)
    r.eq("1.0s → frame 30", vm.time_to_frame(1.0), 30)
    r.eq("5.0s → frame 150", vm.time_to_frame(5.0), 150)


def test_video_metadata_zero_fps(r: TestResult) -> None:
    """VideoMetadata fps=0 경우"""
    from shared.dto.video_dto import VideoMetadata, VideoResolution

    res = VideoResolution(width=1920, height=1080)
    vm = VideoMetadata(duration=120.0, fps=0.0, resolution=res)
    r.is_none("total_frames None (fps=0)", vm.total_frames)
    r.approx("frame_to_time 0 (fps=0)", vm.frame_to_time(100), 0.0)
    r.eq("time_to_frame 0 (fps=0)", vm.time_to_frame(5.0), 0)


def test_video_metadata_with_all_fields(r: TestResult) -> None:
    """VideoMetadata 전체 필드 입력"""
    from datetime import datetime
    from shared.dto.video_dto import VideoMetadata, VideoResolution, VideoCodec, AudioCodec

    res = VideoResolution(width=3840, height=2160)
    dt = datetime(2025, 1, 1, 12, 0, 0)
    vm = VideoMetadata(
        duration=600.0, fps=60.0, resolution=res,
        codec=VideoCodec.H265, audio_codec=AudioCodec.OPUS,
        total_frames=36000, bitrate=50000000,
        file_size=3_758_096_384, creation_time=dt,
    )
    r.eq("codec H265", vm.codec, VideoCodec.H265)
    r.eq("audio OPUS", vm.audio_codec, AudioCodec.OPUS)
    r.eq("total_frames", vm.total_frames, 36000)
    r.eq("bitrate", vm.bitrate, 50000000)
    r.eq("creation_time", vm.creation_time, dt)
    r.approx("file_size_mb", vm.file_size_mb, 3584.0, tol=1.0)


def test_video_metadata_field_count(r: TestResult) -> None:
    """VideoMetadata 필드 수"""
    from shared.dto.video_dto import VideoMetadata

    r.eq("VideoMetadata 필드 수", len(fields(VideoMetadata)), 9)


# ==============================================================
# [I] FrameData dataclass
# ==============================================================
def test_frame_data_basic(r: TestResult) -> None:
    """FrameData 기본 생성"""
    import numpy as np
    from shared.dto.video_dto import FrameData, FrameStatus

    img = np.zeros((480, 640, 3), dtype=np.uint8)
    fd = FrameData(image=img, index=0, timestamp=0.0)

    r.eq("index", fd.index, 0)
    r.approx("timestamp", fd.timestamp, 0.0)
    r.eq("status 기본", fd.status, FrameStatus.VALID)
    r.is_none("camera_id 기본", fd.camera_id)


def test_frame_data_properties(r: TestResult) -> None:
    """FrameData 프로퍼티"""
    import numpy as np
    from shared.dto.video_dto import FrameData, VideoResolution

    img = np.zeros((480, 640, 3), dtype=np.uint8)
    fd = FrameData(image=img, index=10, timestamp=0.333)

    r.eq("height", fd.height, 480)
    r.eq("width", fd.width, 640)
    r.eq("channels", fd.channels, 3)
    r.is_instance("resolution", fd.resolution, VideoResolution)
    r.eq("resolution width", fd.resolution.width, 640)
    r.eq("resolution height", fd.resolution.height, 480)
    r.true("is_valid", fd.is_valid)


def test_frame_data_grayscale(r: TestResult) -> None:
    """FrameData 그레이스케일 이미지"""
    import numpy as np
    from shared.dto.video_dto import FrameData

    gray = np.zeros((100, 100), dtype=np.uint8)
    fd = FrameData(image=gray, index=0, timestamp=0.0)
    r.eq("channels (grayscale)", fd.channels, 1)


def test_frame_data_invalid_status(r: TestResult) -> None:
    """FrameData CORRUPT 상태면 is_valid=False"""
    import numpy as np
    from shared.dto.video_dto import FrameData, FrameStatus

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    fd = FrameData(image=img, index=0, timestamp=0.0, status=FrameStatus.CORRUPT)
    r.false("CORRUPT is_valid", fd.is_valid)


def test_frame_data_camera_id(r: TestResult) -> None:
    """FrameData camera_id 입력"""
    import numpy as np
    from shared.dto.video_dto import FrameData

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    fd = FrameData(image=img, index=0, timestamp=0.0, camera_id="cam_01")
    r.eq("camera_id", fd.camera_id, "cam_01")


def test_frame_data_field_count(r: TestResult) -> None:
    """FrameData 필드 수"""
    from shared.dto.video_dto import FrameData

    r.eq("FrameData 필드 수", len(fields(FrameData)), 5)


# ==============================================================
# [J] VideoSegment dataclass
# ==============================================================
def test_video_segment_basic(r: TestResult) -> None:
    """VideoSegment 기본 생성"""
    from shared.dto.video_dto import VideoSegment, VideoType

    vs = VideoSegment(start_time=10.0, end_time=30.0)
    r.approx("start_time", vs.start_time, 10.0)
    r.approx("end_time", vs.end_time, 30.0)
    r.eq("segment_type 기본", vs.segment_type, VideoType.RAW)
    r.is_none("label 기본", vs.label)
    r.approx("confidence 기본", vs.confidence, 1.0)


def test_video_segment_duration(r: TestResult) -> None:
    """VideoSegment.duration 프로퍼티"""
    from shared.dto.video_dto import VideoSegment

    vs = VideoSegment(start_time=10.0, end_time=30.0)
    r.approx("duration", vs.duration, 20.0)


def test_video_segment_midpoint(r: TestResult) -> None:
    """VideoSegment.midpoint 프로퍼티"""
    from shared.dto.video_dto import VideoSegment

    vs = VideoSegment(start_time=10.0, end_time=30.0)
    r.approx("midpoint", vs.midpoint, 20.0)


def test_video_segment_contains_time(r: TestResult) -> None:
    """VideoSegment.contains_time 메서드"""
    from shared.dto.video_dto import VideoSegment

    vs = VideoSegment(start_time=10.0, end_time=30.0)
    r.true("15.0 포함", vs.contains_time(15.0))
    r.true("10.0 경계 포함", vs.contains_time(10.0))
    r.true("30.0 경계 포함", vs.contains_time(30.0))
    r.false("5.0 미포함", vs.contains_time(5.0))
    r.false("35.0 미포함", vs.contains_time(35.0))


def test_video_segment_overlaps(r: TestResult) -> None:
    """VideoSegment.overlaps 메서드"""
    from shared.dto.video_dto import VideoSegment

    vs1 = VideoSegment(start_time=10.0, end_time=30.0)
    vs2 = VideoSegment(start_time=20.0, end_time=40.0)
    vs3 = VideoSegment(start_time=35.0, end_time=50.0)

    r.true("vs1과 vs2 겹침", vs1.overlaps(vs2))
    r.true("vs2와 vs1 겹침", vs2.overlaps(vs1))
    r.false("vs1과 vs3 안겹침", vs1.overlaps(vs3))
    r.true("vs2와 vs3 겹침", vs2.overlaps(vs3))


def test_video_segment_to_frame_range(r: TestResult) -> None:
    """VideoSegment.to_frame_range 메서드"""
    from shared.dto.video_dto import VideoSegment

    vs = VideoSegment(start_time=10.0, end_time=30.0)
    r.eq("to_frame_range 30fps", vs.to_frame_range(30.0), (300, 900))
    r.eq("to_frame_range 60fps", vs.to_frame_range(60.0), (600, 1800))


def test_video_segment_post_init_clamp(r: TestResult) -> None:
    """VideoSegment __post_init__: confidence 클램핑, 시간 검증"""
    from shared.dto.video_dto import VideoSegment

    # confidence 클램핑
    vs1 = VideoSegment(start_time=0.0, end_time=10.0, confidence=1.5)
    r.approx("confidence 1.5 → 1.0", vs1.confidence, 1.0)

    vs2 = VideoSegment(start_time=0.0, end_time=10.0, confidence=-0.5)
    r.approx("confidence -0.5 → 0.0", vs2.confidence, 0.0)

    # start_time 음수
    vs3 = VideoSegment(start_time=-5.0, end_time=10.0)
    r.approx("start_time -5 → 0.0", vs3.start_time, 0.0)

    # end_time < start_time
    vs4 = VideoSegment(start_time=20.0, end_time=10.0)
    r.approx("end_time < start → start", vs4.end_time, 20.0)


def test_video_segment_with_all_fields(r: TestResult) -> None:
    """VideoSegment 전체 필드 입력"""
    from shared.dto.video_dto import VideoSegment, VideoType

    vs = VideoSegment(
        start_time=5.0, end_time=25.0,
        segment_type=VideoType.HIGHLIGHT,
        label="득점 장면",
        confidence=0.92,
    )
    r.eq("segment_type", vs.segment_type, VideoType.HIGHLIGHT)
    r.eq("label", vs.label, "득점 장면")
    r.approx("confidence", vs.confidence, 0.92)


def test_video_segment_field_count(r: TestResult) -> None:
    """VideoSegment 필드 수"""
    from shared.dto.video_dto import VideoSegment

    r.eq("VideoSegment 필드 수", len(fields(VideoSegment)), 5)


# ==============================================================
# [K] VideoInfo dataclass
# ==============================================================
def test_video_info_defaults(r: TestResult) -> None:
    """VideoInfo 기본값"""
    from shared.dto.video_dto import VideoInfo, VideoType
    from uuid import UUID

    vi = VideoInfo()
    r.is_instance("video_id UUID", vi.video_id, UUID)
    r.is_none("file_path 기본", vi.file_path)
    r.is_none("metadata 기본", vi.metadata)
    r.eq("video_type 기본", vi.video_type, VideoType.RAW)
    r.is_none("format 기본", vi.format)
    r.eq("segments 기본 빈 리스트", vi.segments, [])
    r.eq("tags 기본 빈 리스트", vi.tags, [])


def test_video_info_post_init_format_inference(r: TestResult) -> None:
    """VideoInfo __post_init__: file_path에서 format 추론"""
    from shared.dto.video_dto import VideoInfo, VideoFormat

    vi = VideoInfo(file_path=Path("game.mp4"))
    r.eq("format 추론 MP4", vi.format, VideoFormat.MP4)

    vi2 = VideoInfo(file_path=Path("clip.avi"))
    r.eq("format 추론 AVI", vi2.format, VideoFormat.AVI)

    # 알 수 없는 확장자
    vi3 = VideoInfo(file_path=Path("data.xyz"))
    r.is_none("format 추론 실패", vi3.format)

    # format 직접 지정 시 추론하지 않음
    vi4 = VideoInfo(file_path=Path("game.mp4"), format=VideoFormat.MKV)
    r.eq("format 직접 지정 우선", vi4.format, VideoFormat.MKV)


def test_video_info_filename(r: TestResult) -> None:
    """VideoInfo.filename 프로퍼티"""
    from shared.dto.video_dto import VideoInfo

    vi = VideoInfo(file_path=Path("/videos/game_001.mp4"))
    r.eq("filename", vi.filename, "game_001.mp4")

    vi2 = VideoInfo()
    r.is_none("filename None", vi2.filename)


def test_video_info_add_segment(r: TestResult) -> None:
    """VideoInfo.add_segment 메서드"""
    from shared.dto.video_dto import VideoInfo, VideoSegment

    vi = VideoInfo()
    seg1 = VideoSegment(start_time=0.0, end_time=10.0)
    seg2 = VideoSegment(start_time=10.0, end_time=20.0)

    vi.add_segment(seg1)
    r.eq("1개 추가", len(vi.segments), 1)

    vi.add_segment(seg2)
    r.eq("2개 추가", len(vi.segments), 2)


def test_video_info_get_segments_at(r: TestResult) -> None:
    """VideoInfo.get_segments_at 메서드"""
    from shared.dto.video_dto import VideoInfo, VideoSegment

    vi = VideoInfo()
    seg1 = VideoSegment(start_time=0.0, end_time=10.0)
    seg2 = VideoSegment(start_time=5.0, end_time=15.0)
    seg3 = VideoSegment(start_time=20.0, end_time=30.0)
    vi.add_segment(seg1)
    vi.add_segment(seg2)
    vi.add_segment(seg3)

    at_7 = vi.get_segments_at(7.5)
    r.eq("7.5초에 2개 세그먼트", len(at_7), 2)

    at_25 = vi.get_segments_at(25.0)
    r.eq("25초에 1개 세그먼트", len(at_25), 1)

    at_18 = vi.get_segments_at(18.0)
    r.eq("18초에 0개 세그먼트", len(at_18), 0)


def test_video_info_mutable_defaults_isolation(r: TestResult) -> None:
    """VideoInfo 가변 기본값 격리"""
    from shared.dto.video_dto import VideoInfo, VideoSegment

    vi1 = VideoInfo()
    vi2 = VideoInfo()

    vi1.segments.append(VideoSegment(start_time=0.0, end_time=5.0))
    vi1.tags.append("test")

    r.eq("vi2 segments 격리", len(vi2.segments), 0)
    r.eq("vi2 tags 격리", len(vi2.tags), 0)


def test_video_info_field_count(r: TestResult) -> None:
    """VideoInfo 필드 수"""
    from shared.dto.video_dto import VideoInfo

    r.eq("VideoInfo 필드 수", len(fields(VideoInfo)), 7)


def test_video_info_full_composition(r: TestResult) -> None:
    """VideoInfo 풀 구성"""
    from datetime import datetime
    from shared.dto.video_dto import (
        VideoInfo, VideoFormat, VideoType, VideoCodec, AudioCodec,
        VideoResolution, VideoMetadata, VideoSegment,
    )

    res = VideoResolution(width=1920, height=1080)
    meta = VideoMetadata(
        duration=2400.0, fps=30.0, resolution=res,
        codec=VideoCodec.H264, audio_codec=AudioCodec.AAC,
        bitrate=8000000, file_size=2400000000,
        creation_time=datetime(2025, 6, 15, 14, 30, 0),
    )
    segs = [
        VideoSegment(start_time=0.0, end_time=600.0, segment_type=VideoType.GAME, label="1쿼터"),
        VideoSegment(start_time=600.0, end_time=1200.0, segment_type=VideoType.GAME, label="2쿼터"),
    ]
    vi = VideoInfo(
        file_path=Path("games/2025/game_001.mp4"),
        metadata=meta,
        video_type=VideoType.GAME,
        segments=segs,
        tags=["playoffs", "final"],
    )

    r.eq("format 추론", vi.format, VideoFormat.MP4)
    r.eq("filename", vi.filename, "game_001.mp4")
    r.eq("segments 수", len(vi.segments), 2)
    r.eq("tags 수", len(vi.tags), 2)
    r.eq("metadata duration_formatted", vi.metadata.duration_formatted, "00:40:00")
    r.eq("metadata total_frames", vi.metadata.total_frames, 72000)


# ==============================================================
# main
# ==============================================================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("video_dto.py v2.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- [A] 모듈 구조 ---")
    test_module_structure(r)

    print("\n--- [B] VideoFormat Enum ---")
    test_video_format_members(r)
    test_video_format_mime_type(r)
    test_video_format_extension(r)
    test_video_format_from_extension(r)
    test_video_format_get_name(r)
    test_video_format_str_enum(r)

    print("\n--- [C] VideoType Enum ---")
    test_video_type_members(r)
    test_video_type_to_korean(r)
    test_video_type_i18n(r)

    print("\n--- [D] FrameStatus Enum ---")
    test_frame_status_members(r)
    test_frame_status_is_usable(r)
    test_frame_status_to_korean(r)
    test_frame_status_i18n(r)

    print("\n--- [E] VideoCodec Enum ---")
    test_video_codec_members(r)
    test_video_codec_to_korean(r)
    test_video_codec_i18n(r)

    print("\n--- [F] AudioCodec Enum ---")
    test_audio_codec_members(r)
    test_audio_codec_to_korean(r)
    test_audio_codec_i18n(r)

    print("\n--- [G] VideoResolution ---")
    test_video_resolution_basic(r)
    test_video_resolution_properties(r)
    test_video_resolution_hd_levels(r)
    test_video_resolution_to_tuple(r)
    test_video_resolution_str(r)
    test_video_resolution_zero_height(r)
    test_video_resolution_field_count(r)

    print("\n--- [H] VideoMetadata ---")
    test_video_metadata_basic(r)
    test_video_metadata_post_init_total_frames(r)
    test_video_metadata_duration_formatted(r)
    test_video_metadata_duration_timedelta(r)
    test_video_metadata_file_size_mb(r)
    test_video_metadata_frame_to_time(r)
    test_video_metadata_time_to_frame(r)
    test_video_metadata_zero_fps(r)
    test_video_metadata_with_all_fields(r)
    test_video_metadata_field_count(r)

    print("\n--- [I] FrameData ---")
    test_frame_data_basic(r)
    test_frame_data_properties(r)
    test_frame_data_grayscale(r)
    test_frame_data_invalid_status(r)
    test_frame_data_camera_id(r)
    test_frame_data_field_count(r)

    print("\n--- [J] VideoSegment ---")
    test_video_segment_basic(r)
    test_video_segment_duration(r)
    test_video_segment_midpoint(r)
    test_video_segment_contains_time(r)
    test_video_segment_overlaps(r)
    test_video_segment_to_frame_range(r)
    test_video_segment_post_init_clamp(r)
    test_video_segment_with_all_fields(r)
    test_video_segment_field_count(r)

    print("\n--- [K] VideoInfo ---")
    test_video_info_defaults(r)
    test_video_info_post_init_format_inference(r)
    test_video_info_filename(r)
    test_video_info_add_segment(r)
    test_video_info_get_segments_at(r)
    test_video_info_mutable_defaults_isolation(r)
    test_video_info_field_count(r)
    test_video_info_full_composition(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
