# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_media_dto_perf.py

미디어 DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도
- 프로퍼티 접근 속도 (total_angles, total_clips)
- __post_init__ 자동 계산 속도
- UUID 생성 포함 인스턴스 속도
- 대량 배치 처리 (클립 50개, 주석 20개)

성능 기준:
- 모듈 임포트: < 500ms (cold)
- dataclass 생성: < 5μs (단순) / < 10μs (UUID 포함)
- 프로퍼티 접근: < 2μs

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

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

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


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.media_dto"
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


# ==================== 2. dataclass 생성 속도 ====================
def test_annotation_creation(r: PerfResult) -> None:
    """Annotation 인스턴스 생성 속도 (UUID 포함)"""
    from shared.dto.media_dto import Annotation, AnnotationType

    def create():
        Annotation(
            annotation_type=AnnotationType.ARROW,
            frame_start=100, frame_end=200,
            position_x=0.5, position_y=0.3,
            color="#00FF00",
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("Annotation 생성", elapsed, limit)
    else:
        r.fail("Annotation 생성", elapsed, limit)


def test_video_clip_creation(r: PerfResult) -> None:
    """VideoClip 인스턴스 생성 속도 (UUID + __post_init__)"""
    from shared.dto.media_dto import VideoClip

    def create():
        VideoClip(
            source_video_path="/video/game.mp4",
            camera_id="cam_01",
            start_frame=0, end_frame=900,
            start_time=0.0, end_time=30.0,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("VideoClip 생성", elapsed, limit)
    else:
        r.fail("VideoClip 생성", elapsed, limit)


def test_coaching_point_creation(r: PerfResult) -> None:
    """CoachingPoint 인스턴스 생성 속도"""
    from shared.dto.media_dto import CoachingPoint

    def create():
        CoachingPoint(
            frame_number=450,
            title="스크린 세팅",
            description="좋은 타이밍",
            category="positive",
            priority=2,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("CoachingPoint 생성", elapsed, limit)
    else:
        r.fail("CoachingPoint 생성", elapsed, limit)


def test_export_config_creation(r: PerfResult) -> None:
    """ExportConfig 인스턴스 생성 속도 (UUID 없음, 가벼움)"""
    from shared.dto.media_dto import ExportConfig, ExportFormat

    def create():
        ExportConfig(
            format=ExportFormat.MP4,
            resolution=(1920, 1080),
            fps=30, bitrate_mbps=8.0,
        )

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("ExportConfig 생성", elapsed, limit)
    else:
        r.fail("ExportConfig 생성", elapsed, limit)


def test_film_session_data_creation(r: PerfResult) -> None:
    """FilmSessionData 인스턴스 생성 속도 (UUID + datetime)"""
    from shared.dto.media_dto import FilmSessionData

    def create():
        FilmSessionData(
            session_type="post_game",
            title="경기 후 리뷰",
            estimated_duration_minutes=30,
        )

    elapsed = measure(create, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("FilmSessionData 생성", elapsed, limit)
    else:
        r.fail("FilmSessionData 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 속도 ====================
def test_multi_angle_total_angles(r: PerfResult) -> None:
    """MultiAngleClip.total_angles 프로퍼티 속도"""
    from shared.dto.media_dto import MultiAngleClip, VideoClip

    mac = MultiAngleClip(
        primary_clip=VideoClip(),
        angle_clips=[VideoClip() for _ in range(3)],
    )

    def access():
        _ = mac.total_angles

    elapsed = measure(access, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("total_angles", elapsed, limit)
    else:
        r.fail("total_angles", elapsed, limit)


def test_player_clip_package_total(r: PerfResult) -> None:
    """PlayerClipPackage.total_clips 프로퍼티 속도"""
    from shared.dto.media_dto import PlayerClipPackage, VideoClip

    pkg = PlayerClipPackage(
        offensive_clips=[VideoClip() for _ in range(5)],
        defensive_clips=[VideoClip() for _ in range(3)],
        special_clips=[VideoClip() for _ in range(2)],
    )

    def access():
        _ = pkg.total_clips

    elapsed = measure(access, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("total_clips", elapsed, limit)
    else:
        r.fail("total_clips", elapsed, limit)


# ==================== 4. __post_init__ 속도 ====================
def test_post_init_duration_calc(r: PerfResult) -> None:
    """VideoClip __post_init__ duration 자동계산 속도"""
    from shared.dto.media_dto import VideoClip

    def create():
        VideoClip(start_time=10.0, end_time=25.0)

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("__post_init__ duration", elapsed, limit)
    else:
        r.fail("__post_init__ duration", elapsed, limit)


# ==================== 5. 대량 처리 ====================
def test_batch_video_clips(r: PerfResult) -> None:
    """VideoClip 50개 배치 생성"""
    from shared.dto.media_dto import VideoClip

    def batch():
        for i in range(50):
            VideoClip(
                source_video_path=f"/video/clip_{i}.mp4",
                start_frame=i * 900,
                end_frame=(i + 1) * 900,
                start_time=i * 30.0,
                end_time=(i + 1) * 30.0,
            )

    elapsed = measure(batch, 5000)
    limit = 500.0
    if elapsed < limit:
        r.ok("VideoClip×50", elapsed, limit)
    else:
        r.fail("VideoClip×50", elapsed, limit)


def test_batch_annotations(r: PerfResult) -> None:
    """Annotation 20개 배치 생성"""
    from shared.dto.media_dto import Annotation, AnnotationType

    types = list(AnnotationType)

    def batch():
        for i in range(20):
            Annotation(
                annotation_type=types[i % len(types)],
                frame_start=i * 10,
                frame_end=i * 10 + 30,
                position_x=i * 0.05,
                position_y=0.5,
            )

    elapsed = measure(batch, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("Annotation×20", elapsed, limit)
    else:
        r.fail("Annotation×20", elapsed, limit)


def test_full_film_session(r: PerfResult) -> None:
    """풀 FilmSessionData 스냅샷 생성"""
    from shared.dto.media_dto import (
        FilmSessionData, VideoClip, CoachingPoint,
        PlayerClipPackage, Annotation, AnnotationType,
    )
    from uuid import uuid4

    def create():
        clips = [
            VideoClip(start_time=i * 5.0, end_time=(i + 1) * 5.0)
            for i in range(5)
        ]
        cps = [
            CoachingPoint(title=f"포인트_{i}", category="tactical")
            for i in range(3)
        ]
        pkgs = [
            PlayerClipPackage(
                player_tracking_id=i,
                offensive_clips=[VideoClip()],
            )
            for i in range(2)
        ]
        FilmSessionData(
            session_type="post_game",
            title="전체 스냅샷",
            clips=clips,
            coaching_points=cps,
            player_packages=pkgs,
            comparison_pairs=[(uuid4(), uuid4())],
            estimated_duration_minutes=60,
        )

    elapsed = measure(create, 5000)
    limit = 500.0
    if elapsed < limit:
        r.ok("풀 FilmSession 스냅샷", elapsed, limit)
    else:
        r.fail("풀 FilmSession 스냅샷", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("media_dto.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_annotation_creation(r)
    test_video_clip_creation(r)
    test_coaching_point_creation(r)
    test_export_config_creation(r)
    test_film_session_data_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_multi_angle_total_angles(r)
    test_player_clip_package_total(r)

    print("\n--- __post_init__ ---")
    test_post_init_duration_calc(r)

    print("\n--- 대량 처리 ---")
    test_batch_video_clips(r)
    test_batch_annotations(r)
    test_full_film_session(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
