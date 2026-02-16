# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_video_dto_perf.py

비디오 메타데이터 DTO 성능 테스트
- 모듈 임포트 시간
- Enum 접근/i18n 속도
- dataclass 생성 속도
- VideoMetadata frame_to_time/time_to_frame
- VideoSegment contains_time/overlaps
- VideoInfo get_segments_at
- 대량 배치 처리

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {test_name}: {elapsed_us:.2f}μs ({ratio:.0f}% of {limit_us:.0f}μs limit)")

    def fail(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {elapsed_us:.2f}μs > {limit_us:.0f}μs")
        print(f"  [FAIL] {test_name}: {elapsed_us:.2f}μs (limit: {limit_us:.0f}μs)")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (μs/회)"""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.video_dto"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000
    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. Enum 접근/i18n ====================
def test_video_format_mime_type(r: PerfResult) -> None:
    """VideoFormat.mime_type 프로퍼티"""
    from shared.dto.video_dto import VideoFormat

    def access():
        _ = VideoFormat.MP4.mime_type

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("VideoFormat.mime_type", elapsed, limit)
    else:
        r.fail("VideoFormat.mime_type", elapsed, limit)


def test_video_format_from_extension(r: PerfResult) -> None:
    """VideoFormat.from_extension"""
    from shared.dto.video_dto import VideoFormat

    def access():
        VideoFormat.from_extension(".mp4")

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("VideoFormat.from_extension", elapsed, limit)
    else:
        r.fail("VideoFormat.from_extension", elapsed, limit)


def test_video_type_i18n(r: PerfResult) -> None:
    """VideoType.get_name(KO)"""
    from shared.dto.video_dto import VideoType
    from shared.constants.localization import SupportedLanguage

    def access():
        VideoType.TRAINING.get_name(SupportedLanguage.KO)

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("VideoType.get_name(KO)", elapsed, limit)
    else:
        r.fail("VideoType.get_name(KO)", elapsed, limit)


def test_frame_status_is_usable(r: PerfResult) -> None:
    """FrameStatus.is_usable 프로퍼티"""
    from shared.dto.video_dto import FrameStatus

    def access():
        _ = FrameStatus.VALID.is_usable

    elapsed = measure(access, 100000)
    limit = 3.0
    if elapsed < limit:
        r.ok("FrameStatus.is_usable", elapsed, limit)
    else:
        r.fail("FrameStatus.is_usable", elapsed, limit)


# ==================== 3. dataclass 생성 ====================
def test_video_resolution_creation(r: PerfResult) -> None:
    """VideoResolution 생성"""
    from shared.dto.video_dto import VideoResolution

    def create():
        VideoResolution(width=1920, height=1080)

    elapsed = measure(create, 50000)
    limit = 5.0
    if elapsed < limit:
        r.ok("VideoResolution 생성", elapsed, limit)
    else:
        r.fail("VideoResolution 생성", elapsed, limit)


def test_video_metadata_creation(r: PerfResult) -> None:
    """VideoMetadata 생성 (__post_init__ 포함)"""
    from shared.dto.video_dto import VideoMetadata, VideoResolution

    res = VideoResolution(width=1920, height=1080)

    def create():
        VideoMetadata(duration=120.0, fps=30.0, resolution=res)

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("VideoMetadata 생성", elapsed, limit)
    else:
        r.fail("VideoMetadata 생성", elapsed, limit)


def test_frame_data_creation(r: PerfResult) -> None:
    """FrameData 생성"""
    import numpy as np
    from shared.dto.video_dto import FrameData

    img = np.zeros((480, 640, 3), dtype=np.uint8)

    def create():
        FrameData(image=img, index=0, timestamp=0.0)

    elapsed = measure(create, 50000)
    limit = 5.0
    if elapsed < limit:
        r.ok("FrameData 생성", elapsed, limit)
    else:
        r.fail("FrameData 생성", elapsed, limit)


def test_video_segment_creation(r: PerfResult) -> None:
    """VideoSegment 생성 (__post_init__ 포함)"""
    from shared.dto.video_dto import VideoSegment

    def create():
        VideoSegment(start_time=10.0, end_time=30.0, confidence=0.85)

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("VideoSegment 생성", elapsed, limit)
    else:
        r.fail("VideoSegment 생성", elapsed, limit)


def test_video_info_creation(r: PerfResult) -> None:
    """VideoInfo 생성 (__post_init__ 포함)"""
    from shared.dto.video_dto import VideoInfo

    def create():
        VideoInfo(file_path=Path("game.mp4"))

    elapsed = measure(create, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("VideoInfo 생성", elapsed, limit)
    else:
        r.fail("VideoInfo 생성", elapsed, limit)


# ==================== 4. 메서드 성능 ====================
def test_metadata_frame_to_time(r: PerfResult) -> None:
    """VideoMetadata.frame_to_time"""
    from shared.dto.video_dto import VideoMetadata, VideoResolution

    res = VideoResolution(width=1920, height=1080)
    vm = VideoMetadata(duration=120.0, fps=30.0, resolution=res)

    def convert():
        vm.frame_to_time(1500)

    elapsed = measure(convert, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("frame_to_time", elapsed, limit)
    else:
        r.fail("frame_to_time", elapsed, limit)


def test_segment_contains_time(r: PerfResult) -> None:
    """VideoSegment.contains_time"""
    from shared.dto.video_dto import VideoSegment

    seg = VideoSegment(start_time=10.0, end_time=30.0)

    def check():
        seg.contains_time(15.0)

    elapsed = measure(check, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("contains_time", elapsed, limit)
    else:
        r.fail("contains_time", elapsed, limit)


def test_segment_overlaps(r: PerfResult) -> None:
    """VideoSegment.overlaps"""
    from shared.dto.video_dto import VideoSegment

    seg1 = VideoSegment(start_time=10.0, end_time=30.0)
    seg2 = VideoSegment(start_time=20.0, end_time=40.0)

    def check():
        seg1.overlaps(seg2)

    elapsed = measure(check, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("overlaps", elapsed, limit)
    else:
        r.fail("overlaps", elapsed, limit)


def test_video_info_get_segments_at(r: PerfResult) -> None:
    """VideoInfo.get_segments_at (10개 세그먼트 중 조회)"""
    from shared.dto.video_dto import VideoInfo, VideoSegment

    vi = VideoInfo()
    for i in range(10):
        vi.add_segment(VideoSegment(start_time=float(i * 10), end_time=float(i * 10 + 15)))

    def search():
        vi.get_segments_at(25.0)

    elapsed = measure(search, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("get_segments_at (10개)", elapsed, limit)
    else:
        r.fail("get_segments_at (10개)", elapsed, limit)


# ==================== 5. 대량 배치 처리 ====================
def test_batch_segment_creation(r: PerfResult) -> None:
    """VideoSegment 20개 배치 생성"""
    from shared.dto.video_dto import VideoSegment, VideoType

    def batch():
        for i in range(20):
            VideoSegment(
                start_time=float(i * 10),
                end_time=float(i * 10 + 8),
                segment_type=VideoType.GAME,
                confidence=0.8 + i * 0.01,
            )

    elapsed = measure(batch, 5000)
    limit = 150.0
    if elapsed < limit:
        r.ok("VideoSegment×20 배치", elapsed, limit)
    else:
        r.fail("VideoSegment×20 배치", elapsed, limit)


def test_batch_resolution_creation(r: PerfResult) -> None:
    """VideoResolution 30개 배치 생성 + 프로퍼티"""
    from shared.dto.video_dto import VideoResolution

    def batch():
        for i in range(30):
            vr = VideoResolution(width=640 + i * 64, height=360 + i * 36)
            _ = vr.is_hd
            _ = vr.aspect_ratio

    elapsed = measure(batch, 5000)
    limit = 100.0
    if elapsed < limit:
        r.ok("VideoResolution×30+props", elapsed, limit)
    else:
        r.fail("VideoResolution×30+props", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("video_dto.py v2.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- Enum 접근/i18n ---")
    test_video_format_mime_type(r)
    test_video_format_from_extension(r)
    test_video_type_i18n(r)
    test_frame_status_is_usable(r)

    print("\n--- dataclass 생성 ---")
    test_video_resolution_creation(r)
    test_video_metadata_creation(r)
    test_frame_data_creation(r)
    test_video_segment_creation(r)
    test_video_info_creation(r)

    print("\n--- 메서드 성능 ---")
    test_metadata_frame_to_time(r)
    test_segment_contains_time(r)
    test_segment_overlaps(r)
    test_video_info_get_segments_at(r)

    print("\n--- 대량 배치 처리 ---")
    test_batch_segment_creation(r)
    test_batch_resolution_creation(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
