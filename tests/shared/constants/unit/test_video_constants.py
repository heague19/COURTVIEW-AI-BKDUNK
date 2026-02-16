# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_video_constants.py

비디오 처리 상수 모듈 단위 테스트
- VideoFormat (8 멤버): extension, mime_type, from_extension
- VideoCodec (8 멤버): is_hardware_accelerated, fourcc
- AudioCodec (6 멤버): is_lossy
- ColorSpace (11 멤버): channels
- 동기화/오디오/프레임/길이/파일크기/해상도/비트레이트/지원포맷/프레임추출/버퍼/품질 상수
- 캐시 타입 검증 (frozenset 2, dict 3)
- __all__ Export 동기화 (59개)
- 메타 검증 (버전, 타이핑 현대화)
- 엣지 케이스 (해시/반복/ValueError)

Author: COURTVIEW AI Team
Version: 1.1.0
"""

import io
import sys

# cp949 인코딩 오류 방지
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# =============================================================================
# 임포트
# =============================================================================
import inspect
from enum import Enum

import shared.constants.video_constants as vc
from shared.constants.video_constants import (
    # 동기화
    MAX_SYNC_DRIFT_MS,
    FRAME_SYNC_TOLERANCE_MS,
    AUDIO_SYNC_TOLERANCE_MS,
    FRAME_TIMESTAMP_PRECISION,
    TIMESTAMP_PRECISION_NS,
    # 오디오
    AUDIO_SAMPLE_RATE,
    AUDIO_SAMPLE_RATE_HIGH,
    AUDIO_BIT_DEPTH,
    AUDIO_CHANNELS,
    # 프레임 처리
    MAX_FRAME_DRIFT_MS,
    DEFAULT_FPS,
    ANALYSIS_STANDARD_FPS,
    HIGH_SPEED_ANALYSIS_FPS,
    SLOW_MOTION_FPS,
    INTERPOLATION_THRESHOLD_MS,
    MAX_INTERPOLATION_GAP_MS,
    FRAME_DROP_THRESHOLD_MS,
    # 비디오 길이 제한
    TRAINING_VIDEO_MIN_DURATION_SEC,
    TRAINING_VIDEO_MAX_DURATION_SEC,
    GAME_VIDEO_MIN_DURATION_SEC,
    GAME_VIDEO_MAX_DURATION_SEC,
    HIGHLIGHT_CLIP_MAX_DURATION_SEC,
    HIGHLIGHT_CLIP_MIN_DURATION_SEC,
    # 파일 크기 제한
    MAX_VIDEO_FILE_SIZE_BYTES,
    TRAINING_VIDEO_MAX_SIZE_BYTES,
    GAME_VIDEO_MAX_SIZE_BYTES,
    UPLOAD_CHUNK_SIZE_BYTES,
    # 해상도
    MIN_VIDEO_WIDTH,
    MIN_VIDEO_HEIGHT,
    MAX_VIDEO_WIDTH,
    MAX_VIDEO_HEIGHT,
    STANDARD_RESOLUTIONS,
    ANALYSIS_NORMALIZED_RESOLUTION,
    THUMBNAIL_RESOLUTION,
    # 비트레이트
    MIN_VIDEO_BITRATE_BPS,
    MAX_VIDEO_BITRATE_BPS,
    RECOMMENDED_BITRATES,
    # 열거형
    VideoFormat,
    VideoCodec,
    AudioCodec,
    ColorSpace,
    # 지원 포맷
    SUPPORTED_VIDEO_EXTENSIONS,
    SUPPORTED_VIDEO_MIME_TYPES,
    SUPPORTED_VIDEO_CODECS,
    # 프레임 추출
    DEFAULT_KEYFRAME_INTERVAL_SEC,
    SCENE_CHANGE_THRESHOLD,
    MOTION_DETECTION_THRESHOLD,
    ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES,
    ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES,
    # 버퍼
    FRAME_BUFFER_SIZE,
    DECODE_BUFFER_SIZE,
    PREFETCH_FRAME_COUNT,
    MAX_MEMORY_USAGE_BYTES,
    # 품질
    MIN_VIDEO_QUALITY_SCORE,
    RECOMMENDED_VIDEO_QUALITY_SCORE,
    BLUR_DETECTION_THRESHOLD,
    NOISE_DETECTION_THRESHOLD,
    BRIGHTNESS_MIN_THRESHOLD,
    BRIGHTNESS_MAX_THRESHOLD,
)

# 내부 캐시 임포트
from shared.constants.video_constants import (
    _VIDEO_FORMAT_MIME_TYPE_MAP,
    _VIDEO_CODEC_IS_HARDWARE_ACCELERATED,
    _VIDEO_CODEC_FOURCC_MAP,
    _AUDIO_CODEC_IS_LOSSY,
    _COLOR_SPACE_CHANNELS_MAP,
)


# =============================================================================
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    """테스트 결과 집계 및 출력"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.current_section = ""

    def set_section(self, name: str) -> None:
        self.current_section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, msg: str = "") -> None:
        self.failed += 1
        self.errors.append(f"[{self.current_section}] {name}: {msg}")
        print(f"  [FAIL] {name} - {msg}")

    def check(self, name: str, condition: bool, msg: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        if self.errors:
            print(f"\n  Errors:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")
        return self.failed == 0


# =============================================================================
# 1. VideoFormat 멤버 검증
# =============================================================================
def test_video_format_members(r: TestResult) -> None:
    """VideoFormat 열거형 멤버 존재, 값, 고유성, isinstance 검증"""
    r.set_section("1. VideoFormat 멤버 검증")

    # 멤버 수
    r.check("VideoFormat 멤버 수 == 8", len(VideoFormat) == 8, f"실제: {len(VideoFormat)}")

    # 개별 멤버 존재 및 값
    expected = {
        "MP4": "mp4", "MOV": "mov", "AVI": "avi", "MKV": "mkv",
        "WEBM": "webm", "FLV": "flv", "M4V": "m4v", "TS": "ts",
    }
    for name, value in expected.items():
        member = getattr(VideoFormat, name, None)
        r.check(f"VideoFormat.{name} 존재", member is not None, f"{name} 없음")
        if member is not None:
            r.check(f"VideoFormat.{name}.value == '{value}'", member.value == value, f"실제: {member.value}")

    # isinstance 검증
    for member in VideoFormat:
        r.check(f"VideoFormat.{member.name} isinstance(Enum)", isinstance(member, Enum))

    # 값 고유성
    values = [m.value for m in VideoFormat]
    r.check("VideoFormat 값 고유성", len(values) == len(set(values)), f"중복 발견: {values}")


# =============================================================================
# 2. VideoFormat.extension 검증
# =============================================================================
def test_video_format_extension(r: TestResult) -> None:
    """VideoFormat.extension 프로퍼티 정확성 검증"""
    r.set_section("2. VideoFormat.extension 검증")

    expected = {
        VideoFormat.MP4: ".mp4", VideoFormat.MOV: ".mov", VideoFormat.AVI: ".avi",
        VideoFormat.MKV: ".mkv", VideoFormat.WEBM: ".webm", VideoFormat.FLV: ".flv",
        VideoFormat.M4V: ".m4v", VideoFormat.TS: ".ts",
    }
    for fmt, ext in expected.items():
        r.check(f"{fmt.name}.extension == '{ext}'", fmt.extension == ext, f"실제: {fmt.extension}")

    # 확장자 형식 검증 - 모두 점으로 시작
    for fmt in VideoFormat:
        r.check(f"{fmt.name}.extension 점 시작", fmt.extension.startswith("."),
                f"실제: {fmt.extension}")

    # 확장자 == f".{value}" 공식 검증
    for fmt in VideoFormat:
        r.check(f"{fmt.name}.extension == f'.{{value}}'", fmt.extension == f".{fmt.value}")


# =============================================================================
# 3. VideoFormat.mime_type 검증
# =============================================================================
def test_video_format_mime_type(r: TestResult) -> None:
    """VideoFormat.mime_type 프로퍼티 정확성 검증"""
    r.set_section("3. VideoFormat.mime_type 검증")

    expected = {
        VideoFormat.MP4: "video/mp4",
        VideoFormat.MOV: "video/quicktime",
        VideoFormat.AVI: "video/x-msvideo",
        VideoFormat.MKV: "video/x-matroska",
        VideoFormat.WEBM: "video/webm",
        VideoFormat.FLV: "video/x-flv",
        VideoFormat.M4V: "video/x-m4v",
        VideoFormat.TS: "video/mp2t",
    }
    for fmt, mime in expected.items():
        r.check(f"{fmt.name}.mime_type == '{mime}'", fmt.mime_type == mime, f"실제: {fmt.mime_type}")

    # 타입 검증 - 모두 str
    for fmt in VideoFormat:
        r.check(f"{fmt.name}.mime_type isinstance(str)", isinstance(fmt.mime_type, str))

    # "video/" 접두사 검증
    for fmt in VideoFormat:
        r.check(f"{fmt.name}.mime_type 'video/' 접두사", fmt.mime_type.startswith("video/"),
                f"실제: {fmt.mime_type}")


# =============================================================================
# 4. VideoFormat.from_extension 검증
# =============================================================================
def test_video_format_from_extension(r: TestResult) -> None:
    """VideoFormat.from_extension 클래스메서드 검증"""
    r.set_section("4. VideoFormat.from_extension 검증")

    # 점 포함 소문자
    for fmt in VideoFormat:
        result = VideoFormat.from_extension(f".{fmt.value}")
        r.check(f"from_extension('.{fmt.value}') == {fmt.name}", result == fmt,
                f"실제: {result}")

    # 점 미포함
    for fmt in VideoFormat:
        result = VideoFormat.from_extension(fmt.value)
        r.check(f"from_extension('{fmt.value}') == {fmt.name}", result == fmt,
                f"실제: {result}")

    # 대문자 처리
    r.check("from_extension('.MP4') == MP4", VideoFormat.from_extension(".MP4") == VideoFormat.MP4)
    r.check("from_extension('.MOV') == MOV", VideoFormat.from_extension(".MOV") == VideoFormat.MOV)
    r.check("from_extension('AVI') == AVI", VideoFormat.from_extension("AVI") == VideoFormat.AVI)
    r.check("from_extension('.Mkv') == MKV", VideoFormat.from_extension(".Mkv") == VideoFormat.MKV)

    # 잘못된 확장자 ValueError
    invalid_exts = [".xyz", ".pdf", "unknown", "", ".doc", ".png"]
    for ext in invalid_exts:
        try:
            VideoFormat.from_extension(ext)
            r.fail(f"from_extension('{ext}') ValueError 미발생", "예외 없음")
        except ValueError:
            r.ok(f"from_extension('{ext}') ValueError 발생")
        except Exception as e:
            r.fail(f"from_extension('{ext}') 잘못된 예외", f"{type(e).__name__}: {e}")


# =============================================================================
# 5. VideoCodec 멤버 검증
# =============================================================================
def test_video_codec_members(r: TestResult) -> None:
    """VideoCodec 열거형 멤버 존재, 값, 고유성 검증"""
    r.set_section("5. VideoCodec 멤버 검증")

    r.check("VideoCodec 멤버 수 == 8", len(VideoCodec) == 8, f"실제: {len(VideoCodec)}")

    expected = {
        "H264": "h264", "H265": "h265", "VP8": "vp8", "VP9": "vp9",
        "AV1": "av1", "MPEG4": "mpeg4", "MJPEG": "mjpeg", "PRORES": "prores",
    }
    for name, value in expected.items():
        member = getattr(VideoCodec, name, None)
        r.check(f"VideoCodec.{name} 존재", member is not None, f"{name} 없음")
        if member is not None:
            r.check(f"VideoCodec.{name}.value == '{value}'", member.value == value, f"실제: {member.value}")

    # isinstance 검증
    for member in VideoCodec:
        r.check(f"VideoCodec.{member.name} isinstance(Enum)", isinstance(member, Enum))

    # 값 고유성
    values = [m.value for m in VideoCodec]
    r.check("VideoCodec 값 고유성", len(values) == len(set(values)), f"중복: {values}")


# =============================================================================
# 6. VideoCodec.is_hardware_accelerated 검증
# =============================================================================
def test_video_codec_hardware_accel(r: TestResult) -> None:
    """VideoCodec.is_hardware_accelerated 프로퍼티 정확성 검증"""
    r.set_section("6. VideoCodec.is_hardware_accelerated 검증")

    hw_true = {VideoCodec.H264, VideoCodec.H265, VideoCodec.VP9, VideoCodec.AV1}
    hw_false = {VideoCodec.VP8, VideoCodec.MPEG4, VideoCodec.MJPEG, VideoCodec.PRORES}

    for codec in hw_true:
        r.check(f"{codec.name}.is_hardware_accelerated == True",
                codec.is_hardware_accelerated is True,
                f"실제: {codec.is_hardware_accelerated}")

    for codec in hw_false:
        r.check(f"{codec.name}.is_hardware_accelerated == False",
                codec.is_hardware_accelerated is False,
                f"실제: {codec.is_hardware_accelerated}")

    # 반환 타입 검증
    for codec in VideoCodec:
        r.check(f"{codec.name}.is_hardware_accelerated isinstance(bool)",
                isinstance(codec.is_hardware_accelerated, bool))

    # 가속 4개, 비가속 4개 확인
    accel_count = sum(1 for c in VideoCodec if c.is_hardware_accelerated)
    r.check("하드웨어 가속 코덱 4개", accel_count == 4, f"실제: {accel_count}")


# =============================================================================
# 7. VideoCodec.fourcc 검증
# =============================================================================
def test_video_codec_fourcc(r: TestResult) -> None:
    """VideoCodec.fourcc 프로퍼티 정확성 검증"""
    r.set_section("7. VideoCodec.fourcc 검증")

    expected = {
        VideoCodec.H264: "avc1", VideoCodec.H265: "hvc1",
        VideoCodec.VP8: "VP80", VideoCodec.VP9: "VP90",
        VideoCodec.AV1: "av01", VideoCodec.MPEG4: "mp4v",
        VideoCodec.MJPEG: "MJPG", VideoCodec.PRORES: "apcn",
    }
    for codec, fourcc in expected.items():
        r.check(f"{codec.name}.fourcc == '{fourcc}'", codec.fourcc == fourcc,
                f"실제: {codec.fourcc}")

    # 모든 fourcc 길이 == 4
    for codec in VideoCodec:
        r.check(f"{codec.name}.fourcc 길이 == 4", len(codec.fourcc) == 4,
                f"실제 길이: {len(codec.fourcc)}, 값: {codec.fourcc}")

    # 타입 검증
    for codec in VideoCodec:
        r.check(f"{codec.name}.fourcc isinstance(str)", isinstance(codec.fourcc, str))


# =============================================================================
# 8. AudioCodec 멤버 검증
# =============================================================================
def test_audio_codec_members(r: TestResult) -> None:
    """AudioCodec 열거형 멤버 존재, 값, 고유성 검증"""
    r.set_section("8. AudioCodec 멤버 검증")

    r.check("AudioCodec 멤버 수 == 6", len(AudioCodec) == 6, f"실제: {len(AudioCodec)}")

    expected = {
        "AAC": "aac", "MP3": "mp3", "OPUS": "opus",
        "VORBIS": "vorbis", "PCM": "pcm", "FLAC": "flac",
    }
    for name, value in expected.items():
        member = getattr(AudioCodec, name, None)
        r.check(f"AudioCodec.{name} 존재", member is not None, f"{name} 없음")
        if member is not None:
            r.check(f"AudioCodec.{name}.value == '{value}'", member.value == value, f"실제: {member.value}")

    # isinstance 검증
    for member in AudioCodec:
        r.check(f"AudioCodec.{member.name} isinstance(Enum)", isinstance(member, Enum))

    # 값 고유성
    values = [m.value for m in AudioCodec]
    r.check("AudioCodec 값 고유성", len(values) == len(set(values)), f"중복: {values}")


# =============================================================================
# 9. AudioCodec.is_lossy 검증
# =============================================================================
def test_audio_codec_is_lossy(r: TestResult) -> None:
    """AudioCodec.is_lossy 프로퍼티 정확성 검증"""
    r.set_section("9. AudioCodec.is_lossy 검증")

    lossy_true = {AudioCodec.AAC, AudioCodec.MP3, AudioCodec.OPUS, AudioCodec.VORBIS}
    lossy_false = {AudioCodec.PCM, AudioCodec.FLAC}

    for codec in lossy_true:
        r.check(f"{codec.name}.is_lossy == True", codec.is_lossy is True,
                f"실제: {codec.is_lossy}")

    for codec in lossy_false:
        r.check(f"{codec.name}.is_lossy == False", codec.is_lossy is False,
                f"실제: {codec.is_lossy}")

    # 반환 타입 검증
    for codec in AudioCodec:
        r.check(f"{codec.name}.is_lossy isinstance(bool)", isinstance(codec.is_lossy, bool))

    # 손실 4개, 무손실 2개 확인
    lossy_count = sum(1 for c in AudioCodec if c.is_lossy)
    r.check("손실 압축 코덱 4개", lossy_count == 4, f"실제: {lossy_count}")
    lossless_count = sum(1 for c in AudioCodec if not c.is_lossy)
    r.check("무손실 압축 코덱 2개", lossless_count == 2, f"실제: {lossless_count}")


# =============================================================================
# 10. ColorSpace 멤버 검증
# =============================================================================
def test_color_space_members(r: TestResult) -> None:
    """ColorSpace 열거형 멤버 존재, 값, 고유성 검증"""
    r.set_section("10. ColorSpace 멤버 검증")

    r.check("ColorSpace 멤버 수 == 11", len(ColorSpace) == 11, f"실제: {len(ColorSpace)}")

    expected = {
        "RGB": "rgb", "BGR": "bgr", "RGBA": "rgba", "BGRA": "bgra",
        "GRAY": "gray", "YUV": "yuv", "YUV420P": "yuv420p",
        "YUV422P": "yuv422p", "YUV444P": "yuv444p",
        "NV12": "nv12", "NV21": "nv21",
    }
    for name, value in expected.items():
        member = getattr(ColorSpace, name, None)
        r.check(f"ColorSpace.{name} 존재", member is not None, f"{name} 없음")
        if member is not None:
            r.check(f"ColorSpace.{name}.value == '{value}'", member.value == value, f"실제: {member.value}")

    # isinstance 검증
    for member in ColorSpace:
        r.check(f"ColorSpace.{member.name} isinstance(Enum)", isinstance(member, Enum))

    # 값 고유성
    values = [m.value for m in ColorSpace]
    r.check("ColorSpace 값 고유성", len(values) == len(set(values)), f"중복: {values}")


# =============================================================================
# 11. ColorSpace.channels 검증
# =============================================================================
def test_color_space_channels(r: TestResult) -> None:
    """ColorSpace.channels 프로퍼티 정확성 검증"""
    r.set_section("11. ColorSpace.channels 검증")

    expected = {
        ColorSpace.RGB: 3, ColorSpace.BGR: 3,
        ColorSpace.RGBA: 4, ColorSpace.BGRA: 4,
        ColorSpace.GRAY: 1,
        ColorSpace.YUV: 3, ColorSpace.YUV420P: 3, ColorSpace.YUV422P: 3, ColorSpace.YUV444P: 3,
        ColorSpace.NV12: 3, ColorSpace.NV21: 3,
    }
    for cs, ch in expected.items():
        r.check(f"{cs.name}.channels == {ch}", cs.channels == ch, f"실제: {cs.channels}")

    # 채널 수는 1, 3, 4 중 하나
    valid_channels = {1, 3, 4}
    for cs in ColorSpace:
        r.check(f"{cs.name}.channels in {{1, 3, 4}}", cs.channels in valid_channels,
                f"실제: {cs.channels}")

    # 타입 검증
    for cs in ColorSpace:
        r.check(f"{cs.name}.channels isinstance(int)", isinstance(cs.channels, int))

    # 채널 분포: 1채널=1, 3채널=8, 4채널=2
    ch_1 = sum(1 for cs in ColorSpace if cs.channels == 1)
    ch_3 = sum(1 for cs in ColorSpace if cs.channels == 3)
    ch_4 = sum(1 for cs in ColorSpace if cs.channels == 4)
    r.check("1채널 ColorSpace 1개", ch_1 == 1, f"실제: {ch_1}")
    r.check("3채널 ColorSpace 8개", ch_3 == 8, f"실제: {ch_3}")
    r.check("4채널 ColorSpace 2개", ch_4 == 2, f"실제: {ch_4}")


# =============================================================================
# 12. 동기화 상수 검증
# =============================================================================
def test_sync_constants(r: TestResult) -> None:
    """동기화 관련 상수 정확성 검증"""
    r.set_section("12. 동기화 상수 검증")

    # 정확한 값
    r.check("MAX_SYNC_DRIFT_MS == 50.0", MAX_SYNC_DRIFT_MS == 50.0,
            f"실제: {MAX_SYNC_DRIFT_MS}")
    r.check("FRAME_SYNC_TOLERANCE_MS == 16.67", FRAME_SYNC_TOLERANCE_MS == 16.67,
            f"실제: {FRAME_SYNC_TOLERANCE_MS}")
    r.check("AUDIO_SYNC_TOLERANCE_MS == 40.0", AUDIO_SYNC_TOLERANCE_MS == 40.0,
            f"실제: {AUDIO_SYNC_TOLERANCE_MS}")
    r.check("FRAME_TIMESTAMP_PRECISION == 1000", FRAME_TIMESTAMP_PRECISION == 1000,
            f"실제: {FRAME_TIMESTAMP_PRECISION}")
    r.check("TIMESTAMP_PRECISION_NS == 1_000_000", TIMESTAMP_PRECISION_NS == 1_000_000,
            f"실제: {TIMESTAMP_PRECISION_NS}")

    # 타입 검증
    r.check("MAX_SYNC_DRIFT_MS isinstance(float)", isinstance(MAX_SYNC_DRIFT_MS, float))
    r.check("FRAME_SYNC_TOLERANCE_MS isinstance(float)", isinstance(FRAME_SYNC_TOLERANCE_MS, float))
    r.check("AUDIO_SYNC_TOLERANCE_MS isinstance(float)", isinstance(AUDIO_SYNC_TOLERANCE_MS, float))
    r.check("FRAME_TIMESTAMP_PRECISION isinstance(int)", isinstance(FRAME_TIMESTAMP_PRECISION, int))
    r.check("TIMESTAMP_PRECISION_NS isinstance(int)", isinstance(TIMESTAMP_PRECISION_NS, int))

    # 논리적 관계: 프레임 동기화 < 오디오 동기화 < 최대 드리프트
    r.check("FRAME_SYNC < AUDIO_SYNC < MAX_DRIFT",
            FRAME_SYNC_TOLERANCE_MS < AUDIO_SYNC_TOLERANCE_MS < MAX_SYNC_DRIFT_MS,
            f"{FRAME_SYNC_TOLERANCE_MS} < {AUDIO_SYNC_TOLERANCE_MS} < {MAX_SYNC_DRIFT_MS}")

    # 양수 검증
    r.check("모든 동기화 상수 > 0",
            all(v > 0 for v in [MAX_SYNC_DRIFT_MS, FRAME_SYNC_TOLERANCE_MS,
                                AUDIO_SYNC_TOLERANCE_MS, FRAME_TIMESTAMP_PRECISION,
                                TIMESTAMP_PRECISION_NS]))


# =============================================================================
# 13. 오디오 상수 검증
# =============================================================================
def test_audio_constants(r: TestResult) -> None:
    """오디오 관련 상수 정확성 검증"""
    r.set_section("13. 오디오 상수 검증")

    # 정확한 값
    r.check("AUDIO_SAMPLE_RATE == 44100", AUDIO_SAMPLE_RATE == 44100,
            f"실제: {AUDIO_SAMPLE_RATE}")
    r.check("AUDIO_SAMPLE_RATE_HIGH == 48000", AUDIO_SAMPLE_RATE_HIGH == 48000,
            f"실제: {AUDIO_SAMPLE_RATE_HIGH}")
    r.check("AUDIO_BIT_DEPTH == 16", AUDIO_BIT_DEPTH == 16,
            f"실제: {AUDIO_BIT_DEPTH}")
    r.check("AUDIO_CHANNELS == 2", AUDIO_CHANNELS == 2,
            f"실제: {AUDIO_CHANNELS}")

    # 타입 검증
    r.check("AUDIO_SAMPLE_RATE isinstance(int)", isinstance(AUDIO_SAMPLE_RATE, int))
    r.check("AUDIO_SAMPLE_RATE_HIGH isinstance(int)", isinstance(AUDIO_SAMPLE_RATE_HIGH, int))
    r.check("AUDIO_BIT_DEPTH isinstance(int)", isinstance(AUDIO_BIT_DEPTH, int))
    r.check("AUDIO_CHANNELS isinstance(int)", isinstance(AUDIO_CHANNELS, int))

    # 순서: SAMPLE_RATE < SAMPLE_RATE_HIGH
    r.check("SAMPLE_RATE < SAMPLE_RATE_HIGH",
            AUDIO_SAMPLE_RATE < AUDIO_SAMPLE_RATE_HIGH,
            f"{AUDIO_SAMPLE_RATE} < {AUDIO_SAMPLE_RATE_HIGH}")

    # 양수 검증
    r.check("모든 오디오 상수 > 0",
            all(v > 0 for v in [AUDIO_SAMPLE_RATE, AUDIO_SAMPLE_RATE_HIGH,
                                AUDIO_BIT_DEPTH, AUDIO_CHANNELS]))

    # 스테레오 채널
    r.check("AUDIO_CHANNELS 스테레오(2)", AUDIO_CHANNELS == 2)


# =============================================================================
# 14. 프레임 상수 검증
# =============================================================================
def test_frame_constants(r: TestResult) -> None:
    """프레임 처리 관련 상수 정확성 검증"""
    r.set_section("14. 프레임 상수 검증")

    # 정확한 값
    r.check("MAX_FRAME_DRIFT_MS == 16.67", MAX_FRAME_DRIFT_MS == 16.67,
            f"실제: {MAX_FRAME_DRIFT_MS}")
    r.check("DEFAULT_FPS == 30", DEFAULT_FPS == 30,
            f"실제: {DEFAULT_FPS}")
    r.check("ANALYSIS_STANDARD_FPS == 30", ANALYSIS_STANDARD_FPS == 30,
            f"실제: {ANALYSIS_STANDARD_FPS}")
    r.check("HIGH_SPEED_ANALYSIS_FPS == 60", HIGH_SPEED_ANALYSIS_FPS == 60,
            f"실제: {HIGH_SPEED_ANALYSIS_FPS}")
    r.check("SLOW_MOTION_FPS == 120", SLOW_MOTION_FPS == 120,
            f"실제: {SLOW_MOTION_FPS}")
    r.check("INTERPOLATION_THRESHOLD_MS == 33.33", INTERPOLATION_THRESHOLD_MS == 33.33,
            f"실제: {INTERPOLATION_THRESHOLD_MS}")
    r.check("MAX_INTERPOLATION_GAP_MS == 100.0", MAX_INTERPOLATION_GAP_MS == 100.0,
            f"실제: {MAX_INTERPOLATION_GAP_MS}")
    r.check("FRAME_DROP_THRESHOLD_MS == 50.0", FRAME_DROP_THRESHOLD_MS == 50.0,
            f"실제: {FRAME_DROP_THRESHOLD_MS}")

    # 타입 검증
    r.check("DEFAULT_FPS isinstance(int)", isinstance(DEFAULT_FPS, int))
    r.check("ANALYSIS_STANDARD_FPS isinstance(int)", isinstance(ANALYSIS_STANDARD_FPS, int))
    r.check("HIGH_SPEED_ANALYSIS_FPS isinstance(int)", isinstance(HIGH_SPEED_ANALYSIS_FPS, int))
    r.check("SLOW_MOTION_FPS isinstance(int)", isinstance(SLOW_MOTION_FPS, int))
    r.check("MAX_FRAME_DRIFT_MS isinstance(float)", isinstance(MAX_FRAME_DRIFT_MS, float))
    r.check("INTERPOLATION_THRESHOLD_MS isinstance(float)", isinstance(INTERPOLATION_THRESHOLD_MS, float))

    # 순서: DEFAULT < HIGH_SPEED < SLOW_MOTION
    r.check("DEFAULT_FPS < HIGH_SPEED < SLOW_MOTION",
            DEFAULT_FPS < HIGH_SPEED_ANALYSIS_FPS < SLOW_MOTION_FPS,
            f"{DEFAULT_FPS} < {HIGH_SPEED_ANALYSIS_FPS} < {SLOW_MOTION_FPS}")

    # DEFAULT == ANALYSIS_STANDARD
    r.check("DEFAULT_FPS == ANALYSIS_STANDARD_FPS", DEFAULT_FPS == ANALYSIS_STANDARD_FPS)

    # 보간 임계값 < 최대 보간 간격
    r.check("INTERPOLATION_THRESHOLD < MAX_INTERPOLATION_GAP",
            INTERPOLATION_THRESHOLD_MS < MAX_INTERPOLATION_GAP_MS,
            f"{INTERPOLATION_THRESHOLD_MS} < {MAX_INTERPOLATION_GAP_MS}")

    # 양수 검증
    r.check("모든 프레임 상수 > 0",
            all(v > 0 for v in [MAX_FRAME_DRIFT_MS, DEFAULT_FPS, ANALYSIS_STANDARD_FPS,
                                HIGH_SPEED_ANALYSIS_FPS, SLOW_MOTION_FPS,
                                INTERPOLATION_THRESHOLD_MS, MAX_INTERPOLATION_GAP_MS,
                                FRAME_DROP_THRESHOLD_MS]))


# =============================================================================
# 15. 비디오 길이 제한 상수 검증
# =============================================================================
def test_duration_constants(r: TestResult) -> None:
    """비디오 길이 제한 상수 정확성 검증"""
    r.set_section("15. 비디오 길이 제한 상수 검증")

    # 정확한 값
    r.check("TRAINING_VIDEO_MIN_DURATION_SEC == 3.0",
            TRAINING_VIDEO_MIN_DURATION_SEC == 3.0, f"실제: {TRAINING_VIDEO_MIN_DURATION_SEC}")
    r.check("TRAINING_VIDEO_MAX_DURATION_SEC == 300.0",
            TRAINING_VIDEO_MAX_DURATION_SEC == 300.0, f"실제: {TRAINING_VIDEO_MAX_DURATION_SEC}")
    r.check("GAME_VIDEO_MIN_DURATION_SEC == 60.0",
            GAME_VIDEO_MIN_DURATION_SEC == 60.0, f"실제: {GAME_VIDEO_MIN_DURATION_SEC}")
    r.check("GAME_VIDEO_MAX_DURATION_SEC == 10800.0",
            GAME_VIDEO_MAX_DURATION_SEC == 10800.0, f"실제: {GAME_VIDEO_MAX_DURATION_SEC}")
    r.check("HIGHLIGHT_CLIP_MAX_DURATION_SEC == 30.0",
            HIGHLIGHT_CLIP_MAX_DURATION_SEC == 30.0, f"실제: {HIGHLIGHT_CLIP_MAX_DURATION_SEC}")
    r.check("HIGHLIGHT_CLIP_MIN_DURATION_SEC == 2.0",
            HIGHLIGHT_CLIP_MIN_DURATION_SEC == 2.0, f"실제: {HIGHLIGHT_CLIP_MIN_DURATION_SEC}")

    # 타입 검증
    for name, val in [("TRAINING_MIN", TRAINING_VIDEO_MIN_DURATION_SEC),
                      ("TRAINING_MAX", TRAINING_VIDEO_MAX_DURATION_SEC),
                      ("GAME_MIN", GAME_VIDEO_MIN_DURATION_SEC),
                      ("GAME_MAX", GAME_VIDEO_MAX_DURATION_SEC),
                      ("HIGHLIGHT_MAX", HIGHLIGHT_CLIP_MAX_DURATION_SEC),
                      ("HIGHLIGHT_MIN", HIGHLIGHT_CLIP_MIN_DURATION_SEC)]:
        r.check(f"{name} isinstance(float)", isinstance(val, float))

    # min < max 순서 검증
    r.check("TRAINING min < max",
            TRAINING_VIDEO_MIN_DURATION_SEC < TRAINING_VIDEO_MAX_DURATION_SEC,
            f"{TRAINING_VIDEO_MIN_DURATION_SEC} < {TRAINING_VIDEO_MAX_DURATION_SEC}")
    r.check("GAME min < max",
            GAME_VIDEO_MIN_DURATION_SEC < GAME_VIDEO_MAX_DURATION_SEC,
            f"{GAME_VIDEO_MIN_DURATION_SEC} < {GAME_VIDEO_MAX_DURATION_SEC}")
    r.check("HIGHLIGHT min < max",
            HIGHLIGHT_CLIP_MIN_DURATION_SEC < HIGHLIGHT_CLIP_MAX_DURATION_SEC,
            f"{HIGHLIGHT_CLIP_MIN_DURATION_SEC} < {HIGHLIGHT_CLIP_MAX_DURATION_SEC}")

    # 양수 검증
    r.check("모든 길이 상수 > 0",
            all(v > 0 for v in [TRAINING_VIDEO_MIN_DURATION_SEC, TRAINING_VIDEO_MAX_DURATION_SEC,
                                GAME_VIDEO_MIN_DURATION_SEC, GAME_VIDEO_MAX_DURATION_SEC,
                                HIGHLIGHT_CLIP_MAX_DURATION_SEC, HIGHLIGHT_CLIP_MIN_DURATION_SEC]))

    # 경기 영상이 훈련 영상보다 긴 최대 길이
    r.check("경기 최대 > 훈련 최대",
            GAME_VIDEO_MAX_DURATION_SEC > TRAINING_VIDEO_MAX_DURATION_SEC,
            f"{GAME_VIDEO_MAX_DURATION_SEC} > {TRAINING_VIDEO_MAX_DURATION_SEC}")


# =============================================================================
# 16. 파일 크기 제한 상수 검증
# =============================================================================
def test_file_size_constants(r: TestResult) -> None:
    """파일 크기 제한 상수 정확성 검증"""
    r.set_section("16. 파일 크기 제한 상수 검증")

    # 정확한 값
    r.check("MAX_VIDEO_FILE_SIZE_BYTES == 2GB",
            MAX_VIDEO_FILE_SIZE_BYTES == 2 * 1024 * 1024 * 1024,
            f"실제: {MAX_VIDEO_FILE_SIZE_BYTES}")
    r.check("TRAINING_VIDEO_MAX_SIZE_BYTES == 500MB",
            TRAINING_VIDEO_MAX_SIZE_BYTES == 500 * 1024 * 1024,
            f"실제: {TRAINING_VIDEO_MAX_SIZE_BYTES}")
    r.check("GAME_VIDEO_MAX_SIZE_BYTES == 2GB",
            GAME_VIDEO_MAX_SIZE_BYTES == 2 * 1024 * 1024 * 1024,
            f"실제: {GAME_VIDEO_MAX_SIZE_BYTES}")
    r.check("UPLOAD_CHUNK_SIZE_BYTES == 5MB",
            UPLOAD_CHUNK_SIZE_BYTES == 5 * 1024 * 1024,
            f"실제: {UPLOAD_CHUNK_SIZE_BYTES}")

    # 타입 검증
    r.check("MAX_VIDEO_FILE_SIZE_BYTES isinstance(int)", isinstance(MAX_VIDEO_FILE_SIZE_BYTES, int))
    r.check("TRAINING_VIDEO_MAX_SIZE_BYTES isinstance(int)", isinstance(TRAINING_VIDEO_MAX_SIZE_BYTES, int))
    r.check("GAME_VIDEO_MAX_SIZE_BYTES isinstance(int)", isinstance(GAME_VIDEO_MAX_SIZE_BYTES, int))
    r.check("UPLOAD_CHUNK_SIZE_BYTES isinstance(int)", isinstance(UPLOAD_CHUNK_SIZE_BYTES, int))

    # TRAINING < GAME
    r.check("TRAINING_SIZE < GAME_SIZE",
            TRAINING_VIDEO_MAX_SIZE_BYTES < GAME_VIDEO_MAX_SIZE_BYTES,
            f"{TRAINING_VIDEO_MAX_SIZE_BYTES} < {GAME_VIDEO_MAX_SIZE_BYTES}")

    # TRAINING < MAX
    r.check("TRAINING_SIZE < MAX_VIDEO_SIZE",
            TRAINING_VIDEO_MAX_SIZE_BYTES < MAX_VIDEO_FILE_SIZE_BYTES,
            f"{TRAINING_VIDEO_MAX_SIZE_BYTES} < {MAX_VIDEO_FILE_SIZE_BYTES}")

    # GAME == MAX (둘 다 2GB)
    r.check("GAME_SIZE == MAX_VIDEO_SIZE",
            GAME_VIDEO_MAX_SIZE_BYTES == MAX_VIDEO_FILE_SIZE_BYTES)

    # 청크 크기가 최대 파일 크기보다 작아야 함
    r.check("UPLOAD_CHUNK < MAX_VIDEO_SIZE",
            UPLOAD_CHUNK_SIZE_BYTES < MAX_VIDEO_FILE_SIZE_BYTES)

    # 양수 검증
    r.check("모든 파일 크기 상수 > 0",
            all(v > 0 for v in [MAX_VIDEO_FILE_SIZE_BYTES, TRAINING_VIDEO_MAX_SIZE_BYTES,
                                GAME_VIDEO_MAX_SIZE_BYTES, UPLOAD_CHUNK_SIZE_BYTES]))


# =============================================================================
# 17. 해상도 상수 검증
# =============================================================================
def test_resolution_constants(r: TestResult) -> None:
    """해상도 관련 상수 정확성 검증"""
    r.set_section("17. 해상도 상수 검증")

    # 정확한 값
    r.check("MIN_VIDEO_WIDTH == 480", MIN_VIDEO_WIDTH == 480, f"실제: {MIN_VIDEO_WIDTH}")
    r.check("MIN_VIDEO_HEIGHT == 360", MIN_VIDEO_HEIGHT == 360, f"실제: {MIN_VIDEO_HEIGHT}")
    r.check("MAX_VIDEO_WIDTH == 3840", MAX_VIDEO_WIDTH == 3840, f"실제: {MAX_VIDEO_WIDTH}")
    r.check("MAX_VIDEO_HEIGHT == 2160", MAX_VIDEO_HEIGHT == 2160, f"실제: {MAX_VIDEO_HEIGHT}")
    r.check("ANALYSIS_NORMALIZED_RESOLUTION == (1920, 1080)",
            ANALYSIS_NORMALIZED_RESOLUTION == (1920, 1080), f"실제: {ANALYSIS_NORMALIZED_RESOLUTION}")
    r.check("THUMBNAIL_RESOLUTION == (320, 180)",
            THUMBNAIL_RESOLUTION == (320, 180), f"실제: {THUMBNAIL_RESOLUTION}")

    # MIN < MAX
    r.check("MIN_WIDTH < MAX_WIDTH", MIN_VIDEO_WIDTH < MAX_VIDEO_WIDTH)
    r.check("MIN_HEIGHT < MAX_HEIGHT", MIN_VIDEO_HEIGHT < MAX_VIDEO_HEIGHT)

    # 타입 검증
    r.check("MIN_VIDEO_WIDTH isinstance(int)", isinstance(MIN_VIDEO_WIDTH, int))
    r.check("MAX_VIDEO_WIDTH isinstance(int)", isinstance(MAX_VIDEO_WIDTH, int))
    r.check("ANALYSIS_NORMALIZED_RESOLUTION isinstance(tuple)",
            isinstance(ANALYSIS_NORMALIZED_RESOLUTION, tuple))
    r.check("THUMBNAIL_RESOLUTION isinstance(tuple)", isinstance(THUMBNAIL_RESOLUTION, tuple))

    # STANDARD_RESOLUTIONS 검증
    r.check("STANDARD_RESOLUTIONS isinstance(list)", isinstance(STANDARD_RESOLUTIONS, list))
    r.check("STANDARD_RESOLUTIONS 5개", len(STANDARD_RESOLUTIONS) == 5,
            f"실제: {len(STANDARD_RESOLUTIONS)}")

    expected_resolutions = [
        (640, 480), (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)
    ]
    for i, (expected, actual) in enumerate(zip(expected_resolutions, STANDARD_RESOLUTIONS)):
        r.check(f"STANDARD_RESOLUTIONS[{i}] == {expected}", actual == expected,
                f"실제: {actual}")

    # 해상도 오름차순 정렬 확인
    pixels = [w * h for w, h in STANDARD_RESOLUTIONS]
    r.check("STANDARD_RESOLUTIONS 오름차순 정렬", pixels == sorted(pixels),
            f"픽셀 순서: {pixels}")

    # ANALYSIS_NORMALIZED가 STANDARD에 포함
    r.check("ANALYSIS_NORMALIZED ∈ STANDARD",
            ANALYSIS_NORMALIZED_RESOLUTION in STANDARD_RESOLUTIONS,
            f"{ANALYSIS_NORMALIZED_RESOLUTION}")

    # 모든 표준 해상도가 MIN-MAX 범위 내
    for w, h in STANDARD_RESOLUTIONS:
        r.check(f"해상도 ({w},{h}) MIN-MAX 범위 내",
                MIN_VIDEO_WIDTH <= w <= MAX_VIDEO_WIDTH and MIN_VIDEO_HEIGHT <= h <= MAX_VIDEO_HEIGHT)


# =============================================================================
# 18. 비트레이트 상수 검증
# =============================================================================
def test_bitrate_constants(r: TestResult) -> None:
    """비트레이트 관련 상수 정확성 검증"""
    r.set_section("18. 비트레이트 상수 검증")

    # 정확한 값
    r.check("MIN_VIDEO_BITRATE_BPS == 500_000", MIN_VIDEO_BITRATE_BPS == 500_000,
            f"실제: {MIN_VIDEO_BITRATE_BPS}")
    r.check("MAX_VIDEO_BITRATE_BPS == 50_000_000", MAX_VIDEO_BITRATE_BPS == 50_000_000,
            f"실제: {MAX_VIDEO_BITRATE_BPS}")

    # MIN < MAX
    r.check("MIN_BITRATE < MAX_BITRATE", MIN_VIDEO_BITRATE_BPS < MAX_VIDEO_BITRATE_BPS)

    # 타입 검증
    r.check("MIN_VIDEO_BITRATE_BPS isinstance(int)", isinstance(MIN_VIDEO_BITRATE_BPS, int))
    r.check("MAX_VIDEO_BITRATE_BPS isinstance(int)", isinstance(MAX_VIDEO_BITRATE_BPS, int))

    # RECOMMENDED_BITRATES 검증
    r.check("RECOMMENDED_BITRATES isinstance(dict)", isinstance(RECOMMENDED_BITRATES, dict))
    r.check("RECOMMENDED_BITRATES 5개", len(RECOMMENDED_BITRATES) == 5,
            f"실제: {len(RECOMMENDED_BITRATES)}")

    expected_bitrates = {
        (640, 480): 1_000_000,
        (1280, 720): 2_500_000,
        (1920, 1080): 5_000_000,
        (2560, 1440): 10_000_000,
        (3840, 2160): 20_000_000,
    }
    for res, bitrate in expected_bitrates.items():
        r.check(f"RECOMMENDED_BITRATES[{res}] == {bitrate}",
                RECOMMENDED_BITRATES.get(res) == bitrate,
                f"실제: {RECOMMENDED_BITRATES.get(res)}")

    # 모든 권장 비트레이트가 MIN-MAX 범위 내
    for res, bitrate in RECOMMENDED_BITRATES.items():
        r.check(f"RECOMMENDED[{res}] {MIN_VIDEO_BITRATE_BPS} <= {bitrate} <= {MAX_VIDEO_BITRATE_BPS}",
                MIN_VIDEO_BITRATE_BPS <= bitrate <= MAX_VIDEO_BITRATE_BPS)

    # 해상도가 높을수록 비트레이트 높음
    bitrate_values = list(RECOMMENDED_BITRATES.values())
    r.check("해상도별 비트레이트 오름차순",
            bitrate_values == sorted(bitrate_values),
            f"비트레이트 순서: {bitrate_values}")


# =============================================================================
# 19. 지원 포맷/코덱 frozenset 검증
# =============================================================================
def test_support_frozensets(r: TestResult) -> None:
    """지원 포맷, MIME, 코덱 frozenset 정확성 검증"""
    r.set_section("19. 지원 포맷/코덱 frozenset 검증")

    # SUPPORTED_VIDEO_EXTENSIONS
    r.check("SUPPORTED_VIDEO_EXTENSIONS isinstance(frozenset)",
            isinstance(SUPPORTED_VIDEO_EXTENSIONS, frozenset))
    r.check("SUPPORTED_VIDEO_EXTENSIONS 6개", len(SUPPORTED_VIDEO_EXTENSIONS) == 6,
            f"실제: {len(SUPPORTED_VIDEO_EXTENSIONS)}")
    expected_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
    for ext in expected_exts:
        r.check(f"'{ext}' ∈ SUPPORTED_VIDEO_EXTENSIONS", ext in SUPPORTED_VIDEO_EXTENSIONS)

    # SUPPORTED_VIDEO_MIME_TYPES
    r.check("SUPPORTED_VIDEO_MIME_TYPES isinstance(frozenset)",
            isinstance(SUPPORTED_VIDEO_MIME_TYPES, frozenset))
    r.check("SUPPORTED_VIDEO_MIME_TYPES 6개", len(SUPPORTED_VIDEO_MIME_TYPES) == 6,
            f"실제: {len(SUPPORTED_VIDEO_MIME_TYPES)}")
    expected_mimes = {
        "video/mp4", "video/quicktime", "video/x-msvideo",
        "video/x-matroska", "video/webm", "video/x-m4v",
    }
    for mime in expected_mimes:
        r.check(f"'{mime}' ∈ SUPPORTED_VIDEO_MIME_TYPES", mime in SUPPORTED_VIDEO_MIME_TYPES)

    # SUPPORTED_VIDEO_CODECS
    r.check("SUPPORTED_VIDEO_CODECS isinstance(frozenset)",
            isinstance(SUPPORTED_VIDEO_CODECS, frozenset))
    r.check("SUPPORTED_VIDEO_CODECS 8개", len(SUPPORTED_VIDEO_CODECS) == 8,
            f"실제: {len(SUPPORTED_VIDEO_CODECS)}")
    expected_codecs = {"h264", "h265", "hevc", "avc", "vp8", "vp9", "av1", "mpeg4"}
    for codec in expected_codecs:
        r.check(f"'{codec}' ∈ SUPPORTED_VIDEO_CODECS", codec in SUPPORTED_VIDEO_CODECS)

    # FLV, TS는 SUPPORTED_VIDEO_EXTENSIONS에 미포함 확인
    r.check("'.flv' not in SUPPORTED_VIDEO_EXTENSIONS", ".flv" not in SUPPORTED_VIDEO_EXTENSIONS)
    r.check("'.ts' not in SUPPORTED_VIDEO_EXTENSIONS", ".ts" not in SUPPORTED_VIDEO_EXTENSIONS)


# =============================================================================
# 20. 프레임 추출 상수 검증
# =============================================================================
def test_frame_extraction_constants(r: TestResult) -> None:
    """프레임 추출 관련 상수 정확성 검증"""
    r.set_section("20. 프레임 추출 상수 검증")

    # 정확한 값
    r.check("DEFAULT_KEYFRAME_INTERVAL_SEC == 2.0",
            DEFAULT_KEYFRAME_INTERVAL_SEC == 2.0, f"실제: {DEFAULT_KEYFRAME_INTERVAL_SEC}")
    r.check("SCENE_CHANGE_THRESHOLD == 30.0",
            SCENE_CHANGE_THRESHOLD == 30.0, f"실제: {SCENE_CHANGE_THRESHOLD}")
    r.check("MOTION_DETECTION_THRESHOLD == 25.0",
            MOTION_DETECTION_THRESHOLD == 25.0, f"실제: {MOTION_DETECTION_THRESHOLD}")
    r.check("ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES == 1",
            ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES == 1,
            f"실제: {ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES}")
    r.check("ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES == 15",
            ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES == 15,
            f"실제: {ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES}")

    # 타입 검증
    r.check("DEFAULT_KEYFRAME_INTERVAL_SEC isinstance(float)",
            isinstance(DEFAULT_KEYFRAME_INTERVAL_SEC, float))
    r.check("SCENE_CHANGE_THRESHOLD isinstance(float)",
            isinstance(SCENE_CHANGE_THRESHOLD, float))
    r.check("MOTION_DETECTION_THRESHOLD isinstance(float)",
            isinstance(MOTION_DETECTION_THRESHOLD, float))
    r.check("ADAPTIVE_SAMPLING_MIN isinstance(int)",
            isinstance(ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES, int))
    r.check("ADAPTIVE_SAMPLING_MAX isinstance(int)",
            isinstance(ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES, int))

    # MIN < MAX 간격
    r.check("ADAPTIVE_SAMPLING MIN < MAX",
            ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES < ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES,
            f"{ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES} < {ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES}")

    # 양수 검증
    r.check("모든 프레임 추출 상수 > 0",
            all(v > 0 for v in [DEFAULT_KEYFRAME_INTERVAL_SEC, SCENE_CHANGE_THRESHOLD,
                                MOTION_DETECTION_THRESHOLD, ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES,
                                ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES]))


# =============================================================================
# 21. 버퍼 상수 검증
# =============================================================================
def test_buffer_constants(r: TestResult) -> None:
    """버퍼 관련 상수 정확성 검증"""
    r.set_section("21. 버퍼 상수 검증")

    # 정확한 값
    r.check("FRAME_BUFFER_SIZE == 60", FRAME_BUFFER_SIZE == 60,
            f"실제: {FRAME_BUFFER_SIZE}")
    r.check("DECODE_BUFFER_SIZE == 30", DECODE_BUFFER_SIZE == 30,
            f"실제: {DECODE_BUFFER_SIZE}")
    r.check("PREFETCH_FRAME_COUNT == 10", PREFETCH_FRAME_COUNT == 10,
            f"실제: {PREFETCH_FRAME_COUNT}")
    r.check("MAX_MEMORY_USAGE_BYTES == 2GB",
            MAX_MEMORY_USAGE_BYTES == 2 * 1024 * 1024 * 1024,
            f"실제: {MAX_MEMORY_USAGE_BYTES}")

    # 타입 검증
    r.check("FRAME_BUFFER_SIZE isinstance(int)", isinstance(FRAME_BUFFER_SIZE, int))
    r.check("DECODE_BUFFER_SIZE isinstance(int)", isinstance(DECODE_BUFFER_SIZE, int))
    r.check("PREFETCH_FRAME_COUNT isinstance(int)", isinstance(PREFETCH_FRAME_COUNT, int))
    r.check("MAX_MEMORY_USAGE_BYTES isinstance(int)", isinstance(MAX_MEMORY_USAGE_BYTES, int))

    # 논리적 관계: PREFETCH < DECODE < FRAME_BUFFER
    r.check("PREFETCH < DECODE < FRAME_BUFFER",
            PREFETCH_FRAME_COUNT < DECODE_BUFFER_SIZE < FRAME_BUFFER_SIZE,
            f"{PREFETCH_FRAME_COUNT} < {DECODE_BUFFER_SIZE} < {FRAME_BUFFER_SIZE}")

    # 양수 검증
    r.check("모든 버퍼 상수 > 0",
            all(v > 0 for v in [FRAME_BUFFER_SIZE, DECODE_BUFFER_SIZE,
                                PREFETCH_FRAME_COUNT, MAX_MEMORY_USAGE_BYTES]))


# =============================================================================
# 22. 품질 상수 검증
# =============================================================================
def test_quality_constants(r: TestResult) -> None:
    """품질 관련 상수 정확성 검증"""
    r.set_section("22. 품질 상수 검증")

    # 정확한 값
    r.check("MIN_VIDEO_QUALITY_SCORE == 30.0",
            MIN_VIDEO_QUALITY_SCORE == 30.0, f"실제: {MIN_VIDEO_QUALITY_SCORE}")
    r.check("RECOMMENDED_VIDEO_QUALITY_SCORE == 60.0",
            RECOMMENDED_VIDEO_QUALITY_SCORE == 60.0, f"실제: {RECOMMENDED_VIDEO_QUALITY_SCORE}")
    r.check("BLUR_DETECTION_THRESHOLD == 100.0",
            BLUR_DETECTION_THRESHOLD == 100.0, f"실제: {BLUR_DETECTION_THRESHOLD}")
    r.check("NOISE_DETECTION_THRESHOLD == 50.0",
            NOISE_DETECTION_THRESHOLD == 50.0, f"실제: {NOISE_DETECTION_THRESHOLD}")
    r.check("BRIGHTNESS_MIN_THRESHOLD == 30",
            BRIGHTNESS_MIN_THRESHOLD == 30, f"실제: {BRIGHTNESS_MIN_THRESHOLD}")
    r.check("BRIGHTNESS_MAX_THRESHOLD == 225",
            BRIGHTNESS_MAX_THRESHOLD == 225, f"실제: {BRIGHTNESS_MAX_THRESHOLD}")

    # 타입 검증
    r.check("MIN_VIDEO_QUALITY_SCORE isinstance(float)",
            isinstance(MIN_VIDEO_QUALITY_SCORE, float))
    r.check("RECOMMENDED_VIDEO_QUALITY_SCORE isinstance(float)",
            isinstance(RECOMMENDED_VIDEO_QUALITY_SCORE, float))
    r.check("BLUR_DETECTION_THRESHOLD isinstance(float)",
            isinstance(BLUR_DETECTION_THRESHOLD, float))
    r.check("NOISE_DETECTION_THRESHOLD isinstance(float)",
            isinstance(NOISE_DETECTION_THRESHOLD, float))
    r.check("BRIGHTNESS_MIN_THRESHOLD isinstance(int)",
            isinstance(BRIGHTNESS_MIN_THRESHOLD, int))
    r.check("BRIGHTNESS_MAX_THRESHOLD isinstance(int)",
            isinstance(BRIGHTNESS_MAX_THRESHOLD, int))

    # MIN < RECOMMENDED
    r.check("MIN_QUALITY < RECOMMENDED_QUALITY",
            MIN_VIDEO_QUALITY_SCORE < RECOMMENDED_VIDEO_QUALITY_SCORE,
            f"{MIN_VIDEO_QUALITY_SCORE} < {RECOMMENDED_VIDEO_QUALITY_SCORE}")

    # BRIGHTNESS MIN < MAX
    r.check("BRIGHTNESS_MIN < BRIGHTNESS_MAX",
            BRIGHTNESS_MIN_THRESHOLD < BRIGHTNESS_MAX_THRESHOLD,
            f"{BRIGHTNESS_MIN_THRESHOLD} < {BRIGHTNESS_MAX_THRESHOLD}")

    # 밝기 범위 (0-255 내)
    r.check("BRIGHTNESS_MIN >= 0", BRIGHTNESS_MIN_THRESHOLD >= 0)
    r.check("BRIGHTNESS_MAX <= 255", BRIGHTNESS_MAX_THRESHOLD <= 255)

    # 품질 점수 범위 (0-100)
    r.check("MIN_QUALITY >= 0", MIN_VIDEO_QUALITY_SCORE >= 0)
    r.check("RECOMMENDED_QUALITY <= 100", RECOMMENDED_VIDEO_QUALITY_SCORE <= 100)

    # 양수 검증
    r.check("모든 품질 상수 > 0",
            all(v > 0 for v in [MIN_VIDEO_QUALITY_SCORE, RECOMMENDED_VIDEO_QUALITY_SCORE,
                                BLUR_DETECTION_THRESHOLD, NOISE_DETECTION_THRESHOLD,
                                BRIGHTNESS_MIN_THRESHOLD, BRIGHTNESS_MAX_THRESHOLD]))


# =============================================================================
# 23. __all__ 완전성 검증
# =============================================================================
def test_all_completeness(r: TestResult) -> None:
    """__all__ Export 목록 완전성 검증"""
    r.set_section("23. __all__ 완전성 검증")

    all_list = vc.__all__
    r.check("__all__ isinstance(list)", isinstance(all_list, list))
    r.check("__all__ 59개", len(all_list) == 59, f"실제: {len(all_list)}")

    # 중복 없음
    r.check("__all__ 중복 없음", len(all_list) == len(set(all_list)),
            f"중복: {[x for x in all_list if all_list.count(x) > 1]}")

    # 모든 항목이 모듈에 존재
    missing = [name for name in all_list if not hasattr(vc, name)]
    r.check("__all__ 모든 항목 모듈에 존재", len(missing) == 0,
            f"누락: {missing}")

    # 개별 카테고리 확인
    sync_exports = ["MAX_SYNC_DRIFT_MS", "FRAME_SYNC_TOLERANCE_MS", "AUDIO_SYNC_TOLERANCE_MS",
                    "FRAME_TIMESTAMP_PRECISION", "TIMESTAMP_PRECISION_NS"]
    for name in sync_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    audio_exports = ["AUDIO_SAMPLE_RATE", "AUDIO_SAMPLE_RATE_HIGH", "AUDIO_BIT_DEPTH", "AUDIO_CHANNELS"]
    for name in audio_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    frame_exports = ["MAX_FRAME_DRIFT_MS", "DEFAULT_FPS", "ANALYSIS_STANDARD_FPS",
                     "HIGH_SPEED_ANALYSIS_FPS", "SLOW_MOTION_FPS", "INTERPOLATION_THRESHOLD_MS",
                     "MAX_INTERPOLATION_GAP_MS", "FRAME_DROP_THRESHOLD_MS"]
    for name in frame_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    duration_exports = ["TRAINING_VIDEO_MIN_DURATION_SEC", "TRAINING_VIDEO_MAX_DURATION_SEC",
                        "GAME_VIDEO_MIN_DURATION_SEC", "GAME_VIDEO_MAX_DURATION_SEC",
                        "HIGHLIGHT_CLIP_MAX_DURATION_SEC", "HIGHLIGHT_CLIP_MIN_DURATION_SEC"]
    for name in duration_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    file_size_exports = ["MAX_VIDEO_FILE_SIZE_BYTES", "TRAINING_VIDEO_MAX_SIZE_BYTES",
                         "GAME_VIDEO_MAX_SIZE_BYTES", "UPLOAD_CHUNK_SIZE_BYTES"]
    for name in file_size_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    resolution_exports = ["MIN_VIDEO_WIDTH", "MIN_VIDEO_HEIGHT", "MAX_VIDEO_WIDTH", "MAX_VIDEO_HEIGHT",
                          "STANDARD_RESOLUTIONS", "ANALYSIS_NORMALIZED_RESOLUTION", "THUMBNAIL_RESOLUTION"]
    for name in resolution_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    bitrate_exports = ["MIN_VIDEO_BITRATE_BPS", "MAX_VIDEO_BITRATE_BPS", "RECOMMENDED_BITRATES"]
    for name in bitrate_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    enum_exports = ["VideoFormat", "VideoCodec", "AudioCodec", "ColorSpace"]
    for name in enum_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    support_exports = ["SUPPORTED_VIDEO_EXTENSIONS", "SUPPORTED_VIDEO_MIME_TYPES", "SUPPORTED_VIDEO_CODECS"]
    for name in support_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    extraction_exports = ["DEFAULT_KEYFRAME_INTERVAL_SEC", "SCENE_CHANGE_THRESHOLD",
                          "MOTION_DETECTION_THRESHOLD", "ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES",
                          "ADAPTIVE_SAMPLING_MAX_INTERVAL_FRAMES"]
    for name in extraction_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    buffer_exports = ["FRAME_BUFFER_SIZE", "DECODE_BUFFER_SIZE", "PREFETCH_FRAME_COUNT",
                      "MAX_MEMORY_USAGE_BYTES"]
    for name in buffer_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)

    quality_exports = ["MIN_VIDEO_QUALITY_SCORE", "RECOMMENDED_VIDEO_QUALITY_SCORE",
                       "BLUR_DETECTION_THRESHOLD", "NOISE_DETECTION_THRESHOLD",
                       "BRIGHTNESS_MIN_THRESHOLD", "BRIGHTNESS_MAX_THRESHOLD"]
    for name in quality_exports:
        r.check(f"'{name}' ∈ __all__", name in all_list)


# =============================================================================
# 24. 캐시 타입 및 완전성 검증
# =============================================================================
def test_cache_type_and_completeness(r: TestResult) -> None:
    """내부 캐시 타입 및 완전성 검증"""
    r.set_section("24. 캐시 타입 및 완전성 검증")

    # frozenset 캐시 (2개)
    r.check("_VIDEO_CODEC_IS_HARDWARE_ACCELERATED isinstance(frozenset)",
            isinstance(_VIDEO_CODEC_IS_HARDWARE_ACCELERATED, frozenset))
    r.check("_AUDIO_CODEC_IS_LOSSY isinstance(frozenset)",
            isinstance(_AUDIO_CODEC_IS_LOSSY, frozenset))

    # frozenset 크기
    r.check("_VIDEO_CODEC_IS_HARDWARE_ACCELERATED 크기 == 4",
            len(_VIDEO_CODEC_IS_HARDWARE_ACCELERATED) == 4,
            f"실제: {len(_VIDEO_CODEC_IS_HARDWARE_ACCELERATED)}")
    r.check("_AUDIO_CODEC_IS_LOSSY 크기 == 4",
            len(_AUDIO_CODEC_IS_LOSSY) == 4,
            f"실제: {len(_AUDIO_CODEC_IS_LOSSY)}")

    # dict 캐시 (3개)
    r.check("_VIDEO_FORMAT_MIME_TYPE_MAP isinstance(dict)",
            isinstance(_VIDEO_FORMAT_MIME_TYPE_MAP, dict))
    r.check("_VIDEO_CODEC_FOURCC_MAP isinstance(dict)",
            isinstance(_VIDEO_CODEC_FOURCC_MAP, dict))
    r.check("_COLOR_SPACE_CHANNELS_MAP isinstance(dict)",
            isinstance(_COLOR_SPACE_CHANNELS_MAP, dict))

    # dict 크기 = Enum 멤버 수
    r.check("_VIDEO_FORMAT_MIME_TYPE_MAP 크기 == VideoFormat 수",
            len(_VIDEO_FORMAT_MIME_TYPE_MAP) == len(VideoFormat),
            f"캐시: {len(_VIDEO_FORMAT_MIME_TYPE_MAP)}, Enum: {len(VideoFormat)}")
    r.check("_VIDEO_CODEC_FOURCC_MAP 크기 == VideoCodec 수",
            len(_VIDEO_CODEC_FOURCC_MAP) == len(VideoCodec),
            f"캐시: {len(_VIDEO_CODEC_FOURCC_MAP)}, Enum: {len(VideoCodec)}")
    r.check("_COLOR_SPACE_CHANNELS_MAP 크기 == ColorSpace 수",
            len(_COLOR_SPACE_CHANNELS_MAP) == len(ColorSpace),
            f"캐시: {len(_COLOR_SPACE_CHANNELS_MAP)}, Enum: {len(ColorSpace)}")

    # dict 키가 모든 Enum 멤버 포함
    for fmt in VideoFormat:
        r.check(f"VideoFormat.{fmt.name} ∈ MIME_TYPE_MAP", fmt in _VIDEO_FORMAT_MIME_TYPE_MAP)
    for codec in VideoCodec:
        r.check(f"VideoCodec.{codec.name} ∈ FOURCC_MAP", codec in _VIDEO_CODEC_FOURCC_MAP)
    for cs in ColorSpace:
        r.check(f"ColorSpace.{cs.name} ∈ CHANNELS_MAP", cs in _COLOR_SPACE_CHANNELS_MAP)

    # frozenset 멤버 검증
    r.check("H264 ∈ HW_ACCEL", VideoCodec.H264 in _VIDEO_CODEC_IS_HARDWARE_ACCELERATED)
    r.check("H265 ∈ HW_ACCEL", VideoCodec.H265 in _VIDEO_CODEC_IS_HARDWARE_ACCELERATED)
    r.check("VP9 ∈ HW_ACCEL", VideoCodec.VP9 in _VIDEO_CODEC_IS_HARDWARE_ACCELERATED)
    r.check("AV1 ∈ HW_ACCEL", VideoCodec.AV1 in _VIDEO_CODEC_IS_HARDWARE_ACCELERATED)
    r.check("VP8 not in HW_ACCEL", VideoCodec.VP8 not in _VIDEO_CODEC_IS_HARDWARE_ACCELERATED)

    r.check("AAC ∈ IS_LOSSY", AudioCodec.AAC in _AUDIO_CODEC_IS_LOSSY)
    r.check("MP3 ∈ IS_LOSSY", AudioCodec.MP3 in _AUDIO_CODEC_IS_LOSSY)
    r.check("PCM not in IS_LOSSY", AudioCodec.PCM not in _AUDIO_CODEC_IS_LOSSY)
    r.check("FLAC not in IS_LOSSY", AudioCodec.FLAC not in _AUDIO_CODEC_IS_LOSSY)


# =============================================================================
# 25. 메타 검증 (버전, 타이핑 현대화)
# =============================================================================
def test_meta_verification(r: TestResult) -> None:
    """모듈 메타 정보 및 타이핑 현대화 검증"""
    r.set_section("25. 메타 검증 (버전, 타이핑)")

    # 버전
    r.check("__version__ == '1.1.0'", vc.__version__ == "1.1.0", f"실제: {vc.__version__}")
    r.check("__version__ isinstance(str)", isinstance(vc.__version__, str))

    # 소스 코드 분석 - 타이핑 현대화 확인
    source = inspect.getsource(vc)

    # Python 3.9+ 빌트인 타입 사용 확인 (Dict[ -> dict[, Tuple[ -> tuple[ 등)
    r.check("'Dict[' 미사용 (현대화)", "Dict[" not in source,
            "구식 Dict[ 타입힌트 발견")
    r.check("'Tuple[' 미사용 (현대화)", "Tuple[" not in source,
            "구식 Tuple[ 타입힌트 발견")
    r.check("'List[' 미사용 (현대화)", "List[" not in source,
            "구식 List[ 타입힌트 발견")
    r.check("'FrozenSet[' 미사용 (현대화)", "FrozenSet[" not in source,
            "구식 FrozenSet[ 타입힌트 발견")

    # Final 임포트 확인
    r.check("'from typing import Final' 사용", "from typing import Final" in source)

    # @unique 데코레이터 사용 확인
    r.check("@unique 데코레이터 사용", "@unique" in source)

    # 빈 컨테이너 선언 패턴 부재 확인
    r.check("'= {}' 패턴 미사용", "= {}" not in source,
            "빈 dict 선언 후 업데이트 패턴 발견")
    r.check("'= frozenset()' 패턴 미사용", "= frozenset()" not in source,
            "빈 frozenset 선언 후 업데이트 패턴 발견")
    r.check("'.update(' 패턴 미사용", ".update(" not in source,
            "update 패턴 발견")

    # Enum 임포트 확인
    r.check("'from enum import Enum, unique' 사용", "from enum import Enum, unique" in source)


# =============================================================================
# 26. 엣지 케이스 검증
# =============================================================================
def test_edge_cases(r: TestResult) -> None:
    """해시, 반복, ValueError 등 엣지 케이스 검증"""
    r.set_section("26. 엣지 케이스 검증")

    # Enum 해시 가능 (frozenset/dict 키로 사용 가능)
    for fmt in VideoFormat:
        try:
            _ = hash(fmt)
            r.ok(f"VideoFormat.{fmt.name} 해시 가능")
        except TypeError:
            r.fail(f"VideoFormat.{fmt.name} 해시 불가")

    for codec in VideoCodec:
        try:
            _ = hash(codec)
            r.ok(f"VideoCodec.{codec.name} 해시 가능")
        except TypeError:
            r.fail(f"VideoCodec.{codec.name} 해시 불가")

    for codec in AudioCodec:
        try:
            _ = hash(codec)
            r.ok(f"AudioCodec.{codec.name} 해시 가능")
        except TypeError:
            r.fail(f"AudioCodec.{codec.name} 해시 불가")

    for cs in ColorSpace:
        try:
            _ = hash(cs)
            r.ok(f"ColorSpace.{cs.name} 해시 가능")
        except TypeError:
            r.fail(f"ColorSpace.{cs.name} 해시 불가")

    # Enum 반복 가능
    r.check("VideoFormat 반복 가능", len(list(VideoFormat)) == 8)
    r.check("VideoCodec 반복 가능", len(list(VideoCodec)) == 8)
    r.check("AudioCodec 반복 가능", len(list(AudioCodec)) == 6)
    r.check("ColorSpace 반복 가능", len(list(ColorSpace)) == 11)

    # frozenset 불변성
    try:
        SUPPORTED_VIDEO_EXTENSIONS.add(".test")  # type: ignore
        r.fail("SUPPORTED_VIDEO_EXTENSIONS 변경 가능", "frozenset에 add 성공")
    except AttributeError:
        r.ok("SUPPORTED_VIDEO_EXTENSIONS 불변 (frozenset)")

    try:
        SUPPORTED_VIDEO_MIME_TYPES.add("test/test")  # type: ignore
        r.fail("SUPPORTED_VIDEO_MIME_TYPES 변경 가능", "frozenset에 add 성공")
    except AttributeError:
        r.ok("SUPPORTED_VIDEO_MIME_TYPES 불변 (frozenset)")

    try:
        SUPPORTED_VIDEO_CODECS.add("test")  # type: ignore
        r.fail("SUPPORTED_VIDEO_CODECS 변경 가능", "frozenset에 add 성공")
    except AttributeError:
        r.ok("SUPPORTED_VIDEO_CODECS 불변 (frozenset)")

    # from_extension 다중 점 처리
    r.check("from_extension('...mp4') == MP4",
            VideoFormat.from_extension("...mp4") == VideoFormat.MP4)

    # 빈 문자열 from_extension ValueError
    try:
        VideoFormat.from_extension("")
        r.fail("from_extension('') ValueError 미발생", "예외 없음")
    except ValueError:
        r.ok("from_extension('') ValueError 발생")


# =============================================================================
# 27. Enum 총 멤버 수 교차 검증
# =============================================================================
def test_enum_total_member_count(r: TestResult) -> None:
    """4개 Enum 총 멤버 수 = 33 검증"""
    r.set_section("27. Enum 총 멤버 수 교차 검증")

    total = len(VideoFormat) + len(VideoCodec) + len(AudioCodec) + len(ColorSpace)
    r.check("4개 Enum 총 멤버 수 == 33", total == 33, f"실제: {total}")

    # 각 Enum이 Enum 서브클래스인지 확인
    r.check("VideoFormat issubclass(Enum)", issubclass(VideoFormat, Enum))
    r.check("VideoCodec issubclass(Enum)", issubclass(VideoCodec, Enum))
    r.check("AudioCodec issubclass(Enum)", issubclass(AudioCodec, Enum))
    r.check("ColorSpace issubclass(Enum)", issubclass(ColorSpace, Enum))

    # 각 Enum의 name/value 속성 검증
    for fmt in VideoFormat:
        r.check(f"VideoFormat.{fmt.name}.name 일치", fmt.name == fmt.name)
        r.check(f"VideoFormat.{fmt.name} value 타입 str", isinstance(fmt.value, str))
    for codec in VideoCodec:
        r.check(f"VideoCodec.{codec.name} value 타입 str", isinstance(codec.value, str))
    for codec in AudioCodec:
        r.check(f"AudioCodec.{codec.name} value 타입 str", isinstance(codec.value, str))
    for cs in ColorSpace:
        r.check(f"ColorSpace.{cs.name} value 타입 str", isinstance(cs.value, str))


# =============================================================================
# 28. 상수 상호 일관성 검증
# =============================================================================
def test_cross_constant_consistency(r: TestResult) -> None:
    """상수 간 상호 일관성 검증"""
    r.set_section("28. 상수 상호 일관성 검증")

    # SUPPORTED_VIDEO_EXTENSIONS의 각 확장자가 VideoFormat에 대응
    for ext in SUPPORTED_VIDEO_EXTENSIONS:
        try:
            fmt = VideoFormat.from_extension(ext)
            r.ok(f"SUPPORTED ext '{ext}' -> VideoFormat.{fmt.name}")
        except ValueError:
            r.fail(f"SUPPORTED ext '{ext}' -> VideoFormat 변환 실패")

    # SUPPORTED_VIDEO_MIME_TYPES가 VideoFormat mime_type과 일치하는지
    format_mimes = {fmt.mime_type for fmt in VideoFormat}
    for mime in SUPPORTED_VIDEO_MIME_TYPES:
        r.check(f"SUPPORTED mime '{mime}' ∈ VideoFormat.mime_type set",
                mime in format_mimes,
                f"VideoFormat에 없는 MIME: {mime}")

    # FRAME_SYNC_TOLERANCE_MS == MAX_FRAME_DRIFT_MS (둘 다 1프레임@60fps)
    r.check("FRAME_SYNC_TOLERANCE == MAX_FRAME_DRIFT",
            FRAME_SYNC_TOLERANCE_MS == MAX_FRAME_DRIFT_MS,
            f"{FRAME_SYNC_TOLERANCE_MS} vs {MAX_FRAME_DRIFT_MS}")

    # FRAME_DROP_THRESHOLD_MS == MAX_SYNC_DRIFT_MS
    r.check("FRAME_DROP_THRESHOLD == MAX_SYNC_DRIFT",
            FRAME_DROP_THRESHOLD_MS == MAX_SYNC_DRIFT_MS,
            f"{FRAME_DROP_THRESHOLD_MS} vs {MAX_SYNC_DRIFT_MS}")

    # THUMBNAIL 해상도 < MIN 해상도
    r.check("THUMBNAIL 너비 < MIN_WIDTH",
            THUMBNAIL_RESOLUTION[0] < MIN_VIDEO_WIDTH,
            f"썸네일: {THUMBNAIL_RESOLUTION[0]}, 최소: {MIN_VIDEO_WIDTH}")

    # MAX_MEMORY_USAGE == MAX_VIDEO_FILE_SIZE (둘 다 2GB)
    r.check("MAX_MEMORY == MAX_VIDEO_FILE_SIZE",
            MAX_MEMORY_USAGE_BYTES == MAX_VIDEO_FILE_SIZE_BYTES,
            f"{MAX_MEMORY_USAGE_BYTES} vs {MAX_VIDEO_FILE_SIZE_BYTES}")


# =============================================================================
# 29. VideoFormat 각 멤버 접근 통합 검증
# =============================================================================
def test_video_format_integrated(r: TestResult) -> None:
    """VideoFormat 각 멤버의 extension, mime_type, from_extension 통합 검증"""
    r.set_section("29. VideoFormat 통합 검증")

    for fmt in VideoFormat:
        # extension 접근
        ext = fmt.extension
        r.check(f"{fmt.name}: extension 타입 str", isinstance(ext, str))

        # mime_type 접근
        mime = fmt.mime_type
        r.check(f"{fmt.name}: mime_type 타입 str", isinstance(mime, str))

        # from_extension 왕복 검증
        roundtrip = VideoFormat.from_extension(ext)
        r.check(f"{fmt.name}: from_extension(extension) 왕복 일치", roundtrip == fmt,
                f"'{ext}' -> {roundtrip} != {fmt}")

        # from_extension(value) 검증
        from_val = VideoFormat.from_extension(fmt.value)
        r.check(f"{fmt.name}: from_extension(value) 일치", from_val == fmt)


# =============================================================================
# 30. 상수 범위 경계값 검증
# =============================================================================
def test_boundary_values(r: TestResult) -> None:
    """상수의 경계값 및 합리성 검증"""
    r.set_section("30. 상수 범위 경계값 검증")

    # FPS는 1 이상이어야 함
    r.check("DEFAULT_FPS >= 1", DEFAULT_FPS >= 1)
    r.check("HIGH_SPEED_ANALYSIS_FPS >= 1", HIGH_SPEED_ANALYSIS_FPS >= 1)
    r.check("SLOW_MOTION_FPS >= 1", SLOW_MOTION_FPS >= 1)

    # 비디오 길이는 0보다 커야 함
    r.check("TRAINING_MIN > 0", TRAINING_VIDEO_MIN_DURATION_SEC > 0)
    r.check("GAME_MIN > 0", GAME_VIDEO_MIN_DURATION_SEC > 0)
    r.check("HIGHLIGHT_MIN > 0", HIGHLIGHT_CLIP_MIN_DURATION_SEC > 0)

    # 파일 크기 합리성 (최소 1MB 이상)
    r.check("UPLOAD_CHUNK_SIZE >= 1MB", UPLOAD_CHUNK_SIZE_BYTES >= 1024 * 1024)

    # 해상도 합리성
    r.check("MIN_WIDTH >= 320", MIN_VIDEO_WIDTH >= 320)
    r.check("MIN_HEIGHT >= 240", MIN_VIDEO_HEIGHT >= 240)
    r.check("MAX_WIDTH <= 7680 (8K)", MAX_VIDEO_WIDTH <= 7680)
    r.check("MAX_HEIGHT <= 4320 (8K)", MAX_VIDEO_HEIGHT <= 4320)

    # 비트레이트 합리성
    r.check("MIN_BITRATE >= 100Kbps", MIN_VIDEO_BITRATE_BPS >= 100_000)
    r.check("MAX_BITRATE <= 100Mbps", MAX_VIDEO_BITRATE_BPS <= 100_000_000)

    # 품질 점수 범위
    r.check("MIN_QUALITY_SCORE >= 0", MIN_VIDEO_QUALITY_SCORE >= 0)
    r.check("RECOMMENDED_QUALITY_SCORE <= 100", RECOMMENDED_VIDEO_QUALITY_SCORE <= 100)

    # 버퍼 합리성
    r.check("FRAME_BUFFER >= 10", FRAME_BUFFER_SIZE >= 10)
    r.check("DECODE_BUFFER >= 5", DECODE_BUFFER_SIZE >= 5)
    r.check("PREFETCH >= 1", PREFETCH_FRAME_COUNT >= 1)

    # 키프레임 간격 합리성
    r.check("KEYFRAME_INTERVAL >= 0.5초", DEFAULT_KEYFRAME_INTERVAL_SEC >= 0.5)

    # 샘플링 간격 합리성
    r.check("ADAPTIVE_MIN >= 1", ADAPTIVE_SAMPLING_MIN_INTERVAL_FRAMES >= 1)


# =============================================================================
# 31. 모듈 레벨 속성 검증
# =============================================================================
def test_module_level_attributes(r: TestResult) -> None:
    """모듈 레벨 속성 (docstring, 클래스, 변수) 검증"""
    r.set_section("31. 모듈 레벨 속성 검증")

    # 모듈 docstring 존재
    r.check("모듈 docstring 존재", vc.__doc__ is not None and len(vc.__doc__) > 0)

    # __version__ 존재
    r.check("__version__ 존재", hasattr(vc, "__version__"))

    # __all__ 존재
    r.check("__all__ 존재", hasattr(vc, "__all__"))

    # 4개 Enum 클래스 존재
    r.check("VideoFormat 클래스 존재", hasattr(vc, "VideoFormat"))
    r.check("VideoCodec 클래스 존재", hasattr(vc, "VideoCodec"))
    r.check("AudioCodec 클래스 존재", hasattr(vc, "AudioCodec"))
    r.check("ColorSpace 클래스 존재", hasattr(vc, "ColorSpace"))

    # 5개 내부 캐시 존재
    r.check("_VIDEO_FORMAT_MIME_TYPE_MAP 존재", hasattr(vc, "_VIDEO_FORMAT_MIME_TYPE_MAP"))
    r.check("_VIDEO_CODEC_IS_HARDWARE_ACCELERATED 존재",
            hasattr(vc, "_VIDEO_CODEC_IS_HARDWARE_ACCELERATED"))
    r.check("_VIDEO_CODEC_FOURCC_MAP 존재", hasattr(vc, "_VIDEO_CODEC_FOURCC_MAP"))
    r.check("_AUDIO_CODEC_IS_LOSSY 존재", hasattr(vc, "_AUDIO_CODEC_IS_LOSSY"))
    r.check("_COLOR_SPACE_CHANNELS_MAP 존재", hasattr(vc, "_COLOR_SPACE_CHANNELS_MAP"))


# =============================================================================
# 32. RECOMMENDED_BITRATES 키-STANDARD_RESOLUTIONS 일치 검증
# =============================================================================
def test_bitrate_resolution_alignment(r: TestResult) -> None:
    """RECOMMENDED_BITRATES 키와 STANDARD_RESOLUTIONS 일치 검증"""
    r.set_section("32. 비트레이트-해상도 정렬 검증")

    # RECOMMENDED_BITRATES 키가 STANDARD_RESOLUTIONS와 정확히 일치
    bitrate_resolutions = set(RECOMMENDED_BITRATES.keys())
    standard_resolutions = set(STANDARD_RESOLUTIONS)
    r.check("BITRATE 키 == STANDARD_RESOLUTIONS",
            bitrate_resolutions == standard_resolutions,
            f"차이: {bitrate_resolutions.symmetric_difference(standard_resolutions)}")

    # 각 STANDARD_RESOLUTION에 대한 RECOMMENDED_BITRATE 존재
    for res in STANDARD_RESOLUTIONS:
        r.check(f"해상도 {res}에 대한 권장 비트레이트 존재",
                res in RECOMMENDED_BITRATES,
                f"{res} 누락")

    # 해상도 순서와 비트레이트 순서 일치
    prev_bitrate = 0
    for res in STANDARD_RESOLUTIONS:
        current_bitrate = RECOMMENDED_BITRATES[res]
        r.check(f"해상도 {res} 비트레이트 ({current_bitrate}) > 이전 ({prev_bitrate})",
                current_bitrate > prev_bitrate)
        prev_bitrate = current_bitrate


# =============================================================================
# 33. Enum 이름으로 접근 검증
# =============================================================================
def test_enum_access_by_name_and_value(r: TestResult) -> None:
    """Enum 이름/값 접근 검증"""
    r.set_section("33. Enum 이름/값 접근 검증")

    # VideoFormat 이름 접근
    r.check("VideoFormat['MP4'] == MP4", VideoFormat["MP4"] == VideoFormat.MP4)
    r.check("VideoFormat('mp4') == MP4", VideoFormat("mp4") == VideoFormat.MP4)
    r.check("VideoFormat['TS'] == TS", VideoFormat["TS"] == VideoFormat.TS)
    r.check("VideoFormat('ts') == TS", VideoFormat("ts") == VideoFormat.TS)

    # VideoCodec 이름 접근
    r.check("VideoCodec['H264'] == H264", VideoCodec["H264"] == VideoCodec.H264)
    r.check("VideoCodec('h264') == H264", VideoCodec("h264") == VideoCodec.H264)
    r.check("VideoCodec['PRORES'] == PRORES", VideoCodec["PRORES"] == VideoCodec.PRORES)

    # AudioCodec 이름 접근
    r.check("AudioCodec['AAC'] == AAC", AudioCodec["AAC"] == AudioCodec.AAC)
    r.check("AudioCodec('aac') == AAC", AudioCodec("aac") == AudioCodec.AAC)
    r.check("AudioCodec['FLAC'] == FLAC", AudioCodec["FLAC"] == AudioCodec.FLAC)

    # ColorSpace 이름 접근
    r.check("ColorSpace['RGB'] == RGB", ColorSpace["RGB"] == ColorSpace.RGB)
    r.check("ColorSpace('rgb') == RGB", ColorSpace("rgb") == ColorSpace.RGB)
    r.check("ColorSpace['NV21'] == NV21", ColorSpace["NV21"] == ColorSpace.NV21)

    # 잘못된 이름 접근 KeyError
    try:
        _ = VideoFormat["INVALID"]
        r.fail("VideoFormat['INVALID'] KeyError 미발생", "예외 없음")
    except KeyError:
        r.ok("VideoFormat['INVALID'] KeyError 발생")

    # 잘못된 값 접근 ValueError
    try:
        _ = VideoCodec("invalid_codec")
        r.fail("VideoCodec('invalid_codec') ValueError 미발생", "예외 없음")
    except ValueError:
        r.ok("VideoCodec('invalid_codec') ValueError 발생")

    try:
        _ = AudioCodec("wav")
        r.fail("AudioCodec('wav') ValueError 미발생", "예외 없음")
    except ValueError:
        r.ok("AudioCodec('wav') ValueError 발생")

    try:
        _ = ColorSpace("cmyk")
        r.fail("ColorSpace('cmyk') ValueError 미발생", "예외 없음")
    except ValueError:
        r.ok("ColorSpace('cmyk') ValueError 발생")


# =============================================================================
# 34. SUPPORTED 세트 상호 포함 관계 검증
# =============================================================================
def test_supported_set_relationships(r: TestResult) -> None:
    """SUPPORTED 세트 간 상호 포함 관계 검증"""
    r.set_section("34. SUPPORTED 세트 상호 관계 검증")

    # SUPPORTED_VIDEO_EXTENSIONS에 있는 확장자의 MIME도 SUPPORTED에 포함
    for ext in SUPPORTED_VIDEO_EXTENSIONS:
        fmt = VideoFormat.from_extension(ext)
        mime = fmt.mime_type
        r.check(f"'{ext}' MIME '{mime}' ∈ SUPPORTED_MIME_TYPES",
                mime in SUPPORTED_VIDEO_MIME_TYPES,
                f"'{mime}' not in SUPPORTED_VIDEO_MIME_TYPES")

    # SUPPORTED_VIDEO_CODECS의 모든 항목이 str
    for codec_name in SUPPORTED_VIDEO_CODECS:
        r.check(f"SUPPORTED codec '{codec_name}' isinstance(str)",
                isinstance(codec_name, str))

    # SUPPORTED 세트가 불변(frozenset)
    r.check("EXTENSIONS frozenset", isinstance(SUPPORTED_VIDEO_EXTENSIONS, frozenset))
    r.check("MIME_TYPES frozenset", isinstance(SUPPORTED_VIDEO_MIME_TYPES, frozenset))
    r.check("CODECS frozenset", isinstance(SUPPORTED_VIDEO_CODECS, frozenset))

    # 확장자가 모두 점으로 시작
    for ext in SUPPORTED_VIDEO_EXTENSIONS:
        r.check(f"확장자 '{ext}' 점으로 시작", ext.startswith("."))

    # MIME가 모두 video/ 로 시작
    for mime in SUPPORTED_VIDEO_MIME_TYPES:
        r.check(f"MIME '{mime}' 'video/' 접두사", mime.startswith("video/"))


# =============================================================================
# 35. Enum 동등성 및 식별성 검증
# =============================================================================
def test_enum_equality_identity(r: TestResult) -> None:
    """Enum 멤버 동등성(==) 및 식별성(is) 검증"""
    r.set_section("35. Enum 동등성/식별성 검증")

    # 같은 멤버 동등성 및 식별성
    r.check("VideoFormat.MP4 == VideoFormat.MP4", VideoFormat.MP4 == VideoFormat.MP4)
    r.check("VideoFormat.MP4 is VideoFormat.MP4", VideoFormat.MP4 is VideoFormat.MP4)

    r.check("VideoCodec.H264 == VideoCodec.H264", VideoCodec.H264 == VideoCodec.H264)
    r.check("VideoCodec.H264 is VideoCodec.H264", VideoCodec.H264 is VideoCodec.H264)

    r.check("AudioCodec.AAC == AudioCodec.AAC", AudioCodec.AAC == AudioCodec.AAC)
    r.check("AudioCodec.AAC is AudioCodec.AAC", AudioCodec.AAC is AudioCodec.AAC)

    r.check("ColorSpace.RGB == ColorSpace.RGB", ColorSpace.RGB == ColorSpace.RGB)
    r.check("ColorSpace.RGB is ColorSpace.RGB", ColorSpace.RGB is ColorSpace.RGB)

    # 다른 멤버 비동등성
    r.check("VideoFormat.MP4 != VideoFormat.MOV", VideoFormat.MP4 != VideoFormat.MOV)
    r.check("VideoCodec.H264 != VideoCodec.H265", VideoCodec.H264 != VideoCodec.H265)
    r.check("AudioCodec.AAC != AudioCodec.FLAC", AudioCodec.AAC != AudioCodec.FLAC)
    r.check("ColorSpace.RGB != ColorSpace.BGR", ColorSpace.RGB != ColorSpace.BGR)

    # set/dict 키로 사용 가능
    fmt_set = {VideoFormat.MP4, VideoFormat.MOV, VideoFormat.MP4}
    r.check("VideoFormat set에 중복 제거", len(fmt_set) == 2, f"실제: {len(fmt_set)}")

    codec_dict = {VideoCodec.H264: "avc", VideoCodec.H265: "hevc"}
    r.check("VideoCodec dict 키로 사용", len(codec_dict) == 2)


# =============================================================================
# main
# =============================================================================
def main() -> int:
    r = TestResult()

    test_video_format_members(r)          # 1
    test_video_format_extension(r)        # 2
    test_video_format_mime_type(r)        # 3
    test_video_format_from_extension(r)   # 4
    test_video_codec_members(r)           # 5
    test_video_codec_hardware_accel(r)    # 6
    test_video_codec_fourcc(r)            # 7
    test_audio_codec_members(r)           # 8
    test_audio_codec_is_lossy(r)          # 9
    test_color_space_members(r)           # 10
    test_color_space_channels(r)          # 11
    test_sync_constants(r)               # 12
    test_audio_constants(r)              # 13
    test_frame_constants(r)              # 14
    test_duration_constants(r)           # 15
    test_file_size_constants(r)          # 16
    test_resolution_constants(r)         # 17
    test_bitrate_constants(r)            # 18
    test_support_frozensets(r)           # 19
    test_frame_extraction_constants(r)   # 20
    test_buffer_constants(r)             # 21
    test_quality_constants(r)            # 22
    test_all_completeness(r)             # 23
    test_cache_type_and_completeness(r)  # 24
    test_meta_verification(r)            # 25
    test_edge_cases(r)                   # 26
    test_enum_total_member_count(r)      # 27
    test_cross_constant_consistency(r)   # 28
    test_video_format_integrated(r)      # 29
    test_boundary_values(r)              # 30
    test_module_level_attributes(r)      # 31
    test_bitrate_resolution_alignment(r) # 32
    test_enum_access_by_name_and_value(r)  # 33
    test_supported_set_relationships(r)  # 34
    test_enum_equality_identity(r)       # 35

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(1 if main() > 0 else 0)
