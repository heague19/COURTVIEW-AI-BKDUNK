# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_video_constants_perf.py

비디오 상수 모듈 성능 테스트
- 모듈 임포트 시간
- VideoFormat.extension / mime_type / from_extension 접근
- VideoCodec.is_hardware_accelerated / fourcc 접근
- AudioCodec.is_lossy 접근
- ColorSpace.channels 접근
- Enum 순회 (4개 Enum, 33 멤버)
- frozenset 멤버십 직접 조회
- dict 캐시 직접 조회
- Final 상수 직접 접근
- 복합 시나리오 (비디오 처리 파이프라인, 포맷 검증, 코덱 선택)
- 메모리 사용량
- 대량 연산 처리

성능 기준:
- 모듈 임포트: < 500ms
- Enum 프로퍼티: < 1μs ~ 5μs
- frozenset 멤버십: < 1μs
- dict 캐시 조회: < 1μs
- Final 상수 접근: < 1μs
- Enum 순회 (33 멤버): < 30μs
- 복합 파이프라인: < 50μs
- 포맷 검증: < 30μs
- 코덱 선택: < 20μs
- 메모리: < 256KB
- 대량 처리 (1000 iter): < 500ms

Author: COURTVIEW AI Team
Version: 1.1.0
"""

import gc
import io
import sys
import time
from pathlib import Path

# cp949 인코딩 오류 방지
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# ==================== 테스트 결과 클래스 ====================
class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.2f}us ({ratio:.0f}% of {limit_us:.0f}us)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.2f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.2f}us (limit: {limit_us:.0f}us)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")
        return self.failed == 0


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (마이크로초/회, GC 비활성화)"""
    gc.disable()
    try:
        # 워밍업
        for _ in range(min(iterations, 1000)):
            func()

        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns -> us per iteration
    finally:
        gc.enable()


def _check(r: PerfResult, name: str, elapsed: float, limit: float) -> None:
    """성능 결과 판정 헬퍼"""
    if elapsed <= limit:
        r.ok(name, elapsed, limit)
    else:
        r.fail(name, elapsed, limit)


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 (< 500ms)"""
    print("\n[1] 모듈 임포트")
    import importlib

    mod_name = "shared.constants.video_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 500.0
    r.info(f"모듈 임포트: {elapsed_ms:.1f}ms")
    # 밀리초를 마이크로초로 변환하여 통일된 단위로 판정
    _check(r, "모듈 임포트", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 2. VideoFormat.extension ====================
def test_video_format_extension(r: PerfResult) -> None:
    """VideoFormat.extension 프로퍼티 접근 (< 1us)"""
    print("\n[2] VideoFormat.extension")
    from shared.constants.video_constants import VideoFormat

    _check(r, "VideoFormat.MP4.extension",
           measure(lambda: VideoFormat.MP4.extension), 1.0)
    _check(r, "VideoFormat.MKV.extension",
           measure(lambda: VideoFormat.MKV.extension), 1.0)


# ==================== 3. VideoFormat.mime_type ====================
def test_video_format_mime_type(r: PerfResult) -> None:
    """VideoFormat.mime_type dict 캐시 조회 (< 1us)"""
    print("\n[3] VideoFormat.mime_type")
    from shared.constants.video_constants import VideoFormat

    _check(r, "VideoFormat.MP4.mime_type",
           measure(lambda: VideoFormat.MP4.mime_type), 1.0)
    _check(r, "VideoFormat.WEBM.mime_type",
           measure(lambda: VideoFormat.WEBM.mime_type), 1.0)


# ==================== 4. VideoFormat.from_extension ====================
def test_video_format_from_extension(r: PerfResult) -> None:
    """VideoFormat.from_extension classmethod (< 5us)"""
    print("\n[4] VideoFormat.from_extension")
    from shared.constants.video_constants import VideoFormat

    # 점 포함 확장자
    _check(r, "from_extension('.mp4')",
           measure(lambda: VideoFormat.from_extension(".mp4")), 5.0)
    # 점 미포함 확장자
    _check(r, "from_extension('mkv')",
           measure(lambda: VideoFormat.from_extension("mkv")), 5.0)
    # 끝에 위치한 멤버 (순회 최악 케이스)
    _check(r, "from_extension('.ts')",
           measure(lambda: VideoFormat.from_extension(".ts")), 5.0)


# ==================== 5. VideoCodec.is_hardware_accelerated ====================
def test_video_codec_hw_accel(r: PerfResult) -> None:
    """VideoCodec.is_hardware_accelerated frozenset 멤버십 (< 1us)"""
    print("\n[5] VideoCodec.is_hardware_accelerated")
    from shared.constants.video_constants import VideoCodec

    # True 케이스 (멤버 포함)
    _check(r, "H264.is_hardware_accelerated (True)",
           measure(lambda: VideoCodec.H264.is_hardware_accelerated), 1.0)
    # False 케이스 (멤버 미포함)
    _check(r, "MJPEG.is_hardware_accelerated (False)",
           measure(lambda: VideoCodec.MJPEG.is_hardware_accelerated), 1.0)


# ==================== 6. VideoCodec.fourcc ====================
def test_video_codec_fourcc(r: PerfResult) -> None:
    """VideoCodec.fourcc dict 캐시 조회 (< 1us)"""
    print("\n[6] VideoCodec.fourcc")
    from shared.constants.video_constants import VideoCodec

    _check(r, "H264.fourcc",
           measure(lambda: VideoCodec.H264.fourcc), 1.0)
    _check(r, "PRORES.fourcc",
           measure(lambda: VideoCodec.PRORES.fourcc), 1.0)


# ==================== 7. AudioCodec.is_lossy ====================
def test_audio_codec_is_lossy(r: PerfResult) -> None:
    """AudioCodec.is_lossy frozenset 멤버십 (< 1us)"""
    print("\n[7] AudioCodec.is_lossy")
    from shared.constants.video_constants import AudioCodec

    # 손실 코덱 (True)
    _check(r, "AAC.is_lossy (True)",
           measure(lambda: AudioCodec.AAC.is_lossy), 1.0)
    # 무손실 코덱 (False)
    _check(r, "FLAC.is_lossy (False)",
           measure(lambda: AudioCodec.FLAC.is_lossy), 1.0)


# ==================== 8. ColorSpace.channels ====================
def test_color_space_channels(r: PerfResult) -> None:
    """ColorSpace.channels dict 캐시 조회 (< 1us)"""
    print("\n[8] ColorSpace.channels")
    from shared.constants.video_constants import ColorSpace

    _check(r, "RGB.channels (3)",
           measure(lambda: ColorSpace.RGB.channels), 1.0)
    _check(r, "GRAY.channels (1)",
           measure(lambda: ColorSpace.GRAY.channels), 1.0)
    _check(r, "RGBA.channels (4)",
           measure(lambda: ColorSpace.RGBA.channels), 1.0)


# ==================== 9. Enum 순회 (4 Enums, 33 멤버) ====================
def test_enum_iteration(r: PerfResult) -> None:
    """4개 Enum 전체 순회 - 33 멤버 (< 30us)"""
    print("\n[9] Enum 순회 (33 멤버)")
    from shared.constants.video_constants import (
        VideoFormat, VideoCodec, AudioCodec, ColorSpace,
    )

    elapsed = measure(lambda: (
        list(VideoFormat), list(VideoCodec),
        list(AudioCodec), list(ColorSpace),
    ))
    total_members = len(VideoFormat) + len(VideoCodec) + len(AudioCodec) + len(ColorSpace)
    r.info(f"총 멤버 수: {total_members}")
    _check(r, "4개 Enum 순회 (33 멤버)", elapsed, 30.0)


# ==================== 10. frozenset 멤버십 직접 조회 ====================
def test_frozenset_direct_membership(r: PerfResult) -> None:
    """내부 frozenset 캐시 직접 멤버십 조회 (< 1us)"""
    print("\n[10] frozenset 멤버십 직접 조회")
    from shared.constants.video_constants import VideoCodec, AudioCodec

    # video_constants 내부 frozenset 직접 접근
    import shared.constants.video_constants as vc_mod
    hw_set = vc_mod._VIDEO_CODEC_IS_HARDWARE_ACCELERATED
    lossy_set = vc_mod._AUDIO_CODEC_IS_LOSSY

    # 하드웨어 가속 frozenset - 포함 조회
    _check(r, "_VIDEO_CODEC_IS_HARDWARE_ACCELERATED in (H265)",
           measure(lambda: VideoCodec.H265 in hw_set), 1.0)
    # 하드웨어 가속 frozenset - 미포함 조회
    _check(r, "_VIDEO_CODEC_IS_HARDWARE_ACCELERATED in (MPEG4)",
           measure(lambda: VideoCodec.MPEG4 in hw_set), 1.0)
    # 손실 코덱 frozenset - 포함 조회
    _check(r, "_AUDIO_CODEC_IS_LOSSY in (MP3)",
           measure(lambda: AudioCodec.MP3 in lossy_set), 1.0)
    # 손실 코덱 frozenset - 미포함 조회
    _check(r, "_AUDIO_CODEC_IS_LOSSY in (PCM)",
           measure(lambda: AudioCodec.PCM in lossy_set), 1.0)


# ==================== 11. dict 캐시 직접 조회 ====================
def test_dict_cache_direct_lookup(r: PerfResult) -> None:
    """내부 dict 캐시 직접 조회 (< 1us)"""
    print("\n[11] dict 캐시 직접 조회")
    from shared.constants.video_constants import VideoFormat, VideoCodec, ColorSpace

    import shared.constants.video_constants as vc_mod
    mime_map = vc_mod._VIDEO_FORMAT_MIME_TYPE_MAP
    fourcc_map = vc_mod._VIDEO_CODEC_FOURCC_MAP
    channels_map = vc_mod._COLOR_SPACE_CHANNELS_MAP

    _check(r, "_VIDEO_FORMAT_MIME_TYPE_MAP[MOV]",
           measure(lambda: mime_map[VideoFormat.MOV]), 1.0)
    _check(r, "_VIDEO_CODEC_FOURCC_MAP[VP9]",
           measure(lambda: fourcc_map[VideoCodec.VP9]), 1.0)
    _check(r, "_COLOR_SPACE_CHANNELS_MAP[YUV420P]",
           measure(lambda: channels_map[ColorSpace.YUV420P]), 1.0)


# ==================== 12. Final 상수 직접 접근 ====================
def test_final_constant_access(r: PerfResult) -> None:
    """Final 상수 직접 접근 (< 1us)"""
    print("\n[12] Final 상수 직접 접근")
    from shared.constants.video_constants import (
        DEFAULT_FPS,
        ANALYSIS_STANDARD_FPS,
        MAX_VIDEO_FILE_SIZE_BYTES,
        FRAME_BUFFER_SIZE,
        MIN_VIDEO_QUALITY_SCORE,
    )

    elapsed = measure(lambda: (
        DEFAULT_FPS,
        ANALYSIS_STANDARD_FPS,
        MAX_VIDEO_FILE_SIZE_BYTES,
        FRAME_BUFFER_SIZE,
        MIN_VIDEO_QUALITY_SCORE,
    ))
    _check(r, "Final 상수 5개 접근", elapsed, 1.0)

    # 추가: 해상도/비트레이트 관련 상수
    from shared.constants.video_constants import (
        STANDARD_RESOLUTIONS,
        RECOMMENDED_BITRATES,
        ANALYSIS_NORMALIZED_RESOLUTION,
    )
    elapsed2 = measure(lambda: (
        STANDARD_RESOLUTIONS,
        RECOMMENDED_BITRATES,
        ANALYSIS_NORMALIZED_RESOLUTION,
    ))
    _check(r, "컬렉션 Final 상수 3개 접근", elapsed2, 1.0)


# ==================== 13. 복합: 비디오 처리 파이프라인 ====================
def test_composite_video_pipeline(r: PerfResult) -> None:
    """비디오 처리 파이프라인 복합 시나리오 (< 50us)"""
    print("\n[13] 복합: 비디오 처리 파이프라인")
    from shared.constants.video_constants import (
        VideoFormat, VideoCodec, AudioCodec, ColorSpace,
        DEFAULT_FPS, ANALYSIS_STANDARD_FPS,
        ANALYSIS_NORMALIZED_RESOLUTION,
        SUPPORTED_VIDEO_EXTENSIONS,
        MAX_VIDEO_FILE_SIZE_BYTES,
        FRAME_BUFFER_SIZE,
    )

    def pipeline():
        """비디오 입력 검증 -> 코덱 확인 -> 색상 공간 -> 프레임 설정"""
        # 1단계: 포맷 검증
        fmt = VideoFormat.MP4
        ext = fmt.extension
        mime = fmt.mime_type
        valid_ext = ext in SUPPORTED_VIDEO_EXTENSIONS

        # 2단계: 코덱 확인
        codec = VideoCodec.H264
        hw_accel = codec.is_hardware_accelerated
        fourcc = codec.fourcc

        # 3단계: 오디오 코덱 확인
        audio = AudioCodec.AAC
        lossy = audio.is_lossy

        # 4단계: 색상 공간 결정
        cs = ColorSpace.YUV420P
        ch = cs.channels

        # 5단계: 프레임 설정
        fps = DEFAULT_FPS
        std_fps = ANALYSIS_STANDARD_FPS
        res = ANALYSIS_NORMALIZED_RESOLUTION
        buf = FRAME_BUFFER_SIZE
        max_size = MAX_VIDEO_FILE_SIZE_BYTES

        return (ext, mime, valid_ext, hw_accel, fourcc,
                lossy, ch, fps, std_fps, res, buf, max_size)

    elapsed = measure(pipeline)
    _check(r, "비디오 처리 파이프라인", elapsed, 50.0)


# ==================== 14. 복합: 포맷 검증 ====================
def test_composite_format_validation(r: PerfResult) -> None:
    """포맷 검증 복합 시나리오 (< 30us)"""
    print("\n[14] 복합: 포맷 검증")
    from shared.constants.video_constants import (
        VideoFormat,
        SUPPORTED_VIDEO_EXTENSIONS,
        SUPPORTED_VIDEO_MIME_TYPES,
        MIN_VIDEO_WIDTH, MIN_VIDEO_HEIGHT,
        MAX_VIDEO_WIDTH, MAX_VIDEO_HEIGHT,
        MIN_VIDEO_BITRATE_BPS, MAX_VIDEO_BITRATE_BPS,
    )

    def validate_format():
        """입력 파일 포맷 검증 파이프라인"""
        # 확장자로 포맷 확인
        fmt = VideoFormat.from_extension(".mp4")
        ext = fmt.extension
        mime = fmt.mime_type

        # 지원 여부 확인
        ext_ok = ext in SUPPORTED_VIDEO_EXTENSIONS
        mime_ok = mime in SUPPORTED_VIDEO_MIME_TYPES

        # 해상도 범위 확인 (1920x1080 가정)
        w, h = 1920, 1080
        res_ok = (MIN_VIDEO_WIDTH <= w <= MAX_VIDEO_WIDTH and
                  MIN_VIDEO_HEIGHT <= h <= MAX_VIDEO_HEIGHT)

        # 비트레이트 범위 확인 (5Mbps 가정)
        bitrate = 5_000_000
        br_ok = MIN_VIDEO_BITRATE_BPS <= bitrate <= MAX_VIDEO_BITRATE_BPS

        return ext_ok, mime_ok, res_ok, br_ok

    elapsed = measure(validate_format)
    _check(r, "포맷 검증 파이프라인", elapsed, 30.0)


# ==================== 15. 복합: 코덱 선택 ====================
def test_composite_codec_selection(r: PerfResult) -> None:
    """코덱 선택 복합 시나리오 (< 20us)"""
    print("\n[15] 복합: 코덱 선택")
    from shared.constants.video_constants import (
        VideoCodec, AudioCodec, ColorSpace,
    )

    def select_codec():
        """최적 코덱 조합 선택 파이프라인"""
        # 하드웨어 가속 가능한 코덱 필터링
        hw_codecs = [c for c in VideoCodec if c.is_hardware_accelerated]

        # 각 코덱의 fourcc 수집
        fourcc_list = [c.fourcc for c in hw_codecs]

        # 손실 오디오 코덱 필터링
        lossy_audio = [a for a in AudioCodec if a.is_lossy]

        # 3채널 색상 공간 필터링
        rgb_spaces = [cs for cs in ColorSpace if cs.channels == 3]

        return hw_codecs, fourcc_list, lossy_audio, rgb_spaces

    elapsed = measure(select_codec)
    _check(r, "코덱 선택 파이프라인", elapsed, 20.0)


# ==================== 16. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 (< 256KB)"""
    print("\n[16] 메모리 사용량")
    import importlib

    mod_name = "shared.constants.video_constants"

    # 모듈 언로드 후 재측정
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.collect()

    try:
        import tracemalloc
        tracemalloc.start()
        importlib.import_module(mod_name)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_kb = peak_bytes / 1024
        limit_kb = 256.0
        r.info(f"메모리: {peak_kb:.1f}KB")
        _check(r, "메모리 사용량 (KB)", peak_kb, limit_kb)
    except ImportError:
        r.info("tracemalloc 사용 불가 - 스킵")
        r.ok("메모리 사용량 (스킵)", 0, 256.0)


# ==================== 17. 대량 연산 처리 ====================
def test_bulk_operations(r: PerfResult) -> None:
    """1000회 반복 대량 연산 (< 500ms)"""
    print("\n[17] 대량 연산 처리 (1000 iterations)")
    from shared.constants.video_constants import (
        VideoFormat, VideoCodec, AudioCodec, ColorSpace,
    )

    formats = list(VideoFormat)
    codecs = list(VideoCodec)
    audio_codecs = list(AudioCodec)
    color_spaces = list(ColorSpace)

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(1000):
        # 모든 VideoFormat 프로퍼티
        for f in formats:
            _ = f.extension
            _ = f.mime_type

        # 모든 VideoCodec 프로퍼티
        for c in codecs:
            _ = c.is_hardware_accelerated
            _ = c.fourcc

        # 모든 AudioCodec 프로퍼티
        for a in audio_codecs:
            _ = a.is_lossy

        # 모든 ColorSpace 프로퍼티
        for cs in color_spaces:
            _ = cs.channels

    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 500.0
    r.info(f"1000회 전체 프로퍼티 순회: {elapsed_ms:.1f}ms")
    # 밀리초를 마이크로초로 변환하여 통일된 단위 판정
    _check(r, "대량 연산 (1000 iter)", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 실행 ====================
def main() -> int:
    print("=" * 60)
    print("비디오 상수 모듈 (video_constants.py) 성능 테스트")
    print("=" * 60)

    r = PerfResult()

    test_module_import_time(r)              # [1]  1 측정
    test_video_format_extension(r)          # [2]  2 측정
    test_video_format_mime_type(r)          # [3]  2 측정
    test_video_format_from_extension(r)     # [4]  3 측정
    test_video_codec_hw_accel(r)            # [5]  2 측정
    test_video_codec_fourcc(r)              # [6]  2 측정
    test_audio_codec_is_lossy(r)            # [7]  2 측정
    test_color_space_channels(r)            # [8]  3 측정
    test_enum_iteration(r)                  # [9]  1 측정
    test_frozenset_direct_membership(r)     # [10] 4 측정
    test_dict_cache_direct_lookup(r)        # [11] 3 측정
    test_final_constant_access(r)           # [12] 2 측정
    test_composite_video_pipeline(r)        # [13] 1 측정
    test_composite_format_validation(r)     # [14] 1 측정
    test_composite_codec_selection(r)       # [15] 1 측정
    test_memory_usage(r)                    # [16] 1 측정
    test_bulk_operations(r)                 # [17] 1 측정
    # 총: 17 테스트 함수, 32 측정

    all_passed = r.summary()
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
