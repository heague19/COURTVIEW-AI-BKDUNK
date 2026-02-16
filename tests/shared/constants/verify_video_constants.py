# -*- coding: utf-8 -*-
"""video_constants.py v1.1.0 검증 테스트"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0


def check(name, condition, msg=""):
    global passed, failed
    if condition:
        print(f"[PASS] {name}")
        passed += 1
    else:
        print(f"[FAIL] {name} - {msg}")
        failed += 1


print("=" * 70)
print("video_constants.py v1.1.0 검증 테스트")
print("=" * 70)

# T-01: 모듈 임포트
try:
    from shared.constants.video_constants import (
        VideoFormat, VideoCodec, AudioCodec, ColorSpace,
        MAX_SYNC_DRIFT_MS, DEFAULT_FPS,
        SUPPORTED_VIDEO_EXTENSIONS,
    )
    check("T-01: 모듈 임포트", True)
except Exception as e:
    check("T-01: 모듈 임포트", False, str(e))
    sys.exit(1)

# T-02: __init__.py 호환성
try:
    from shared.constants import (
        VideoFormat, VideoCodec, AudioCodec, ColorSpace,
        MAX_SYNC_DRIFT_MS, DEFAULT_FPS,
    )
    check("T-02: __init__.py 호환성", True)
except Exception as e:
    check("T-02: __init__.py 호환성", False, str(e))

# T-03: VideoFormat 8 멤버
check(
    "T-03: VideoFormat 8 멤버",
    len(VideoFormat) == 8,
    f"실제: {len(VideoFormat)}",
)

# T-04: VideoCodec 8 멤버
check(
    "T-04: VideoCodec 8 멤버",
    len(VideoCodec) == 8,
    f"실제: {len(VideoCodec)}",
)

# T-05: AudioCodec 6 멤버
check(
    "T-05: AudioCodec 6 멤버",
    len(AudioCodec) == 6,
    f"실제: {len(AudioCodec)}",
)

# T-06: ColorSpace 11 멤버
check(
    "T-06: ColorSpace 11 멤버",
    len(ColorSpace) == 11,
    f"실제: {len(ColorSpace)}",
)

# T-07: VideoFormat.extension
check(
    "T-07: VideoFormat.extension",
    VideoFormat.MP4.extension == ".mp4"
    and VideoFormat.MKV.extension == ".mkv"
    and VideoFormat.TS.extension == ".ts",
)

# T-08: VideoFormat.mime_type
check(
    "T-08: VideoFormat.mime_type",
    VideoFormat.MP4.mime_type == "video/mp4"
    and VideoFormat.MOV.mime_type == "video/quicktime"
    and VideoFormat.WEBM.mime_type == "video/webm"
    and all(isinstance(f.mime_type, str) for f in VideoFormat),
)

# T-09: VideoFormat.from_extension
check(
    "T-09: VideoFormat.from_extension",
    VideoFormat.from_extension(".mp4") == VideoFormat.MP4
    and VideoFormat.from_extension("mkv") == VideoFormat.MKV
    and VideoFormat.from_extension(".MOV") == VideoFormat.MOV,
)

# T-10: VideoFormat.from_extension ValueError
try:
    VideoFormat.from_extension(".xyz")
    check("T-10: VideoFormat.from_extension ValueError", False, "예외 미발생")
except ValueError:
    check("T-10: VideoFormat.from_extension ValueError", True)

# T-11: VideoCodec.is_hardware_accelerated
check(
    "T-11: VideoCodec.is_hardware_accelerated",
    VideoCodec.H264.is_hardware_accelerated is True
    and VideoCodec.H265.is_hardware_accelerated is True
    and VideoCodec.VP9.is_hardware_accelerated is True
    and VideoCodec.AV1.is_hardware_accelerated is True
    and VideoCodec.VP8.is_hardware_accelerated is False
    and VideoCodec.MJPEG.is_hardware_accelerated is False
    and VideoCodec.PRORES.is_hardware_accelerated is False,
)

# T-12: VideoCodec.fourcc
check(
    "T-12: VideoCodec.fourcc",
    VideoCodec.H264.fourcc == "avc1"
    and VideoCodec.H265.fourcc == "hvc1"
    and VideoCodec.MJPEG.fourcc == "MJPG"
    and all(isinstance(c.fourcc, str) and len(c.fourcc) == 4 for c in VideoCodec),
)

# T-13: AudioCodec.is_lossy
check(
    "T-13: AudioCodec.is_lossy",
    AudioCodec.AAC.is_lossy is True
    and AudioCodec.MP3.is_lossy is True
    and AudioCodec.OPUS.is_lossy is True
    and AudioCodec.VORBIS.is_lossy is True
    and AudioCodec.PCM.is_lossy is False
    and AudioCodec.FLAC.is_lossy is False,
)

# T-14: ColorSpace.channels
check(
    "T-14: ColorSpace.channels",
    ColorSpace.RGB.channels == 3
    and ColorSpace.RGBA.channels == 4
    and ColorSpace.GRAY.channels == 1
    and ColorSpace.YUV420P.channels == 3
    and all(isinstance(c.channels, int) for c in ColorSpace),
)

# T-15: SUPPORTED_VIDEO_EXTENSIONS frozenset
check(
    "T-15: SUPPORTED_VIDEO_EXTENSIONS",
    isinstance(SUPPORTED_VIDEO_EXTENSIONS, frozenset)
    and ".mp4" in SUPPORTED_VIDEO_EXTENSIONS
    and ".mkv" in SUPPORTED_VIDEO_EXTENSIONS
    and len(SUPPORTED_VIDEO_EXTENSIONS) == 6,
)

# T-16: 해상도 범위 일관성
from shared.constants.video_constants import (
    MIN_VIDEO_WIDTH, MIN_VIDEO_HEIGHT,
    MAX_VIDEO_WIDTH, MAX_VIDEO_HEIGHT,
)
check(
    "T-16: 해상도 범위 일관성",
    MIN_VIDEO_WIDTH < MAX_VIDEO_WIDTH
    and MIN_VIDEO_HEIGHT < MAX_VIDEO_HEIGHT
    and MAX_VIDEO_WIDTH == 3840
    and MAX_VIDEO_HEIGHT == 2160,
)

# T-17: 비디오 길이 범위 일관성
from shared.constants.video_constants import (
    TRAINING_VIDEO_MIN_DURATION_SEC, TRAINING_VIDEO_MAX_DURATION_SEC,
    GAME_VIDEO_MIN_DURATION_SEC, GAME_VIDEO_MAX_DURATION_SEC,
    HIGHLIGHT_CLIP_MIN_DURATION_SEC, HIGHLIGHT_CLIP_MAX_DURATION_SEC,
)
check(
    "T-17: 비디오 길이 범위 일관성",
    TRAINING_VIDEO_MIN_DURATION_SEC < TRAINING_VIDEO_MAX_DURATION_SEC
    and GAME_VIDEO_MIN_DURATION_SEC < GAME_VIDEO_MAX_DURATION_SEC
    and HIGHLIGHT_CLIP_MIN_DURATION_SEC < HIGHLIGHT_CLIP_MAX_DURATION_SEC,
)

# T-18: 비트레이트 범위 일관성
from shared.constants.video_constants import (
    MIN_VIDEO_BITRATE_BPS, MAX_VIDEO_BITRATE_BPS,
    RECOMMENDED_BITRATES,
)
check(
    "T-18: 비트레이트 범위 일관성",
    MIN_VIDEO_BITRATE_BPS < MAX_VIDEO_BITRATE_BPS
    and len(RECOMMENDED_BITRATES) == 5
    and all(MIN_VIDEO_BITRATE_BPS <= v <= MAX_VIDEO_BITRATE_BPS for v in RECOMMENDED_BITRATES.values()),
)

# T-19: __all__ 개수 및 존재 확인
import shared.constants.video_constants as vc
all_list = vc.__all__
all_exist = all(hasattr(vc, name) for name in all_list)
check(
    f"T-19: __all__ {len(all_list)}개 항목 모두 존재",
    all_exist,
    f"개수: {len(all_list)}, 존재: {all_exist}",
)

# T-20: .update() 패턴 부재
import inspect
source = inspect.getsource(vc)
check(
    "T-20: .update() 및 빈 선언 패턴 없음",
    ".update(" not in source
    and "= {}" not in source
    and "= frozenset()" not in source,
)

# T-21: frozenset 캐시 타입 검증
from shared.constants.video_constants import (
    _VIDEO_CODEC_IS_HARDWARE_ACCELERATED,
    _AUDIO_CODEC_IS_LOSSY,
)
check(
    "T-21: 2개 frozenset 캐시 타입",
    isinstance(_VIDEO_CODEC_IS_HARDWARE_ACCELERATED, frozenset)
    and isinstance(_AUDIO_CODEC_IS_LOSSY, frozenset),
)

# T-22: dict 캐시 완전성
from shared.constants.video_constants import (
    _VIDEO_FORMAT_MIME_TYPE_MAP,
    _VIDEO_CODEC_FOURCC_MAP,
    _COLOR_SPACE_CHANNELS_MAP,
)
check(
    "T-22: 3개 dict 캐시 완전성",
    len(_VIDEO_FORMAT_MIME_TYPE_MAP) == len(VideoFormat)
    and len(_VIDEO_CODEC_FOURCC_MAP) == len(VideoCodec)
    and len(_COLOR_SPACE_CHANNELS_MAP) == len(ColorSpace),
)

# T-23: 버전 검증
check("T-23: 버전 1.1.0", vc.__version__ == "1.1.0", f"실제: {vc.__version__}")

print()
print("=" * 70)
print(f"결과: {passed}/{passed + failed} PASS | {failed} FAIL")
print("=" * 70)

if failed > 0:
    sys.exit(1)
