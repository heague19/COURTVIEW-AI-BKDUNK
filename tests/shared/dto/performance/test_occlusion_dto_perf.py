# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_occlusion_dto_perf.py

오클루전 DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도
- 프로퍼티 접근 속도
- 메서드 호출 속도 (mark_ended, get_summary, get_visible_objects_in_view)
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
    mod_name = "shared.dto.occlusion_dto"
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


# ==================== 2. dataclass 생성 ====================
def test_view_visibility_creation(r: PerfResult) -> None:
    """ViewVisibility 생성 속도 (__post_init__ 포함)"""
    from shared.dto.occlusion_dto import ViewVisibility

    def create():
        ViewVisibility(
            camera_id="cam_01",
            is_visible=True,
            visibility_ratio=0.8,
            visible_keypoints={0, 1, 2, 3},
            occluded_keypoints={4, 5},
            confidence=0.9,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("ViewVisibility 생성", elapsed, limit)
    else:
        r.fail("ViewVisibility 생성", elapsed, limit)


def test_occluded_object_creation(r: PerfResult) -> None:
    """OccludedObject 생성 속도"""
    from shared.dto.occlusion_dto import OccludedObject
    from shared.dto.geometry_dto import BoundingBox, Point2D

    def create():
        OccludedObject(
            object_id=3,
            object_type="player",
            last_known_bbox=BoundingBox(10, 20, 50, 80),
            last_known_position=Point2D(35.0, 60.0),
            occluder_ids=[7, 8],
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("OccludedObject 생성", elapsed, limit)
    else:
        r.fail("OccludedObject 생성", elapsed, limit)


def test_occlusion_event_creation(r: PerfResult) -> None:
    """OcclusionEvent 생성 속도 (UUID 포함)"""
    from shared.dto.occlusion_dto import OcclusionEvent
    from shared.constants.occlusion_constants import OcclusionType, OcclusionSeverity

    def create():
        OcclusionEvent(
            occlusion_type=OcclusionType.INTER_PLAYER,
            severity=OcclusionSeverity.PARTIAL,
            start_frame=100,
            affected_track_ids=[3, 5],
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("OcclusionEvent 생성", elapsed, limit)
    else:
        r.fail("OcclusionEvent 생성", elapsed, limit)


def test_occlusion_resolution_creation(r: PerfResult) -> None:
    """OcclusionResolution 생성 속도"""
    from shared.dto.occlusion_dto import OcclusionResolution
    from shared.constants.occlusion_constants import ResolutionStrategy
    from shared.dto.geometry_dto import Point2D

    def create():
        OcclusionResolution(
            track_id=5,
            strategy_used=ResolutionStrategy.CROSS_VIEW,
            success=True,
            confidence=0.85,
            recovered_position=Point2D(100.0, 200.0),
            source_view_id="cam_02",
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("OcclusionResolution 생성", elapsed, limit)
    else:
        r.fail("OcclusionResolution 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_view_visibility_properties(r: PerfResult) -> None:
    """ViewVisibility 프로퍼티 접근 속도"""
    from shared.dto.occlusion_dto import ViewVisibility

    vv = ViewVisibility(
        camera_id="cam_01",
        visible_keypoints={0, 1, 2, 3, 4},
        occluded_keypoints={5, 6, 7},
        visibility_ratio=0.6,
    )

    def access():
        _ = vv.total_keypoints
        _ = vv.visible_keypoint_ratio
        _ = vv.is_partially_visible
        _ = vv.is_fully_visible
        _ = vv.is_fully_occluded

    elapsed = measure(access, 100000)
    per_call = elapsed / 5
    limit = 2.0
    if per_call < limit:
        r.ok("ViewVisibility 프로퍼티", per_call, limit)
    else:
        r.fail("ViewVisibility 프로퍼티", per_call, limit)


def test_occluded_object_properties(r: PerfResult) -> None:
    """OccludedObject 프로퍼티 접근 속도"""
    from shared.dto.occlusion_dto import OccludedObject, ViewVisibility

    vv1 = ViewVisibility(camera_id="cam_01", is_visible=True, visibility_ratio=0.8)
    vv2 = ViewVisibility(camera_id="cam_02", is_visible=False, visibility_ratio=0.1)
    oo = OccludedObject(
        object_id=3,
        occluder_ids=[7, 8],
        visibility_per_view={"cam_01": vv1, "cam_02": vv2},
    )

    def access():
        _ = oo.num_occluders
        _ = oo.num_visible_views
        _ = oo.best_visible_view
        _ = oo.average_visibility

    elapsed = measure(access, 50000)
    per_call = elapsed / 4
    limit = 3.0
    if per_call < limit:
        r.ok("OccludedObject 프로퍼티", per_call, limit)
    else:
        r.fail("OccludedObject 프로퍼티", per_call, limit)


def test_occlusion_event_properties(r: PerfResult) -> None:
    """OcclusionEvent 프로퍼티 접근 속도"""
    from shared.dto.occlusion_dto import OcclusionEvent
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    oe = OcclusionEvent(
        start_frame=100, end_frame=175,
        start_time=now, end_time=now + timedelta(seconds=2.5),
        affected_track_ids=[3, 5],
    )

    def access():
        _ = oe.is_active
        _ = oe.duration_frames
        _ = oe.duration_seconds
        _ = oe.num_affected_tracks
        _ = oe.is_multi_object

    elapsed = measure(access, 100000)
    per_call = elapsed / 5
    limit = 2.0
    if per_call < limit:
        r.ok("OcclusionEvent 프로퍼티", per_call, limit)
    else:
        r.fail("OcclusionEvent 프로퍼티", per_call, limit)


# ==================== 4. 메서드 호출 ====================
def test_get_summary_i18n(r: PerfResult) -> None:
    """OcclusionResolution.get_summary i18n 속도"""
    from shared.dto.occlusion_dto import OcclusionResolution
    from shared.constants.occlusion_constants import ResolutionStrategy
    from shared.constants.localization import SupportedLanguage

    orr = OcclusionResolution(
        track_id=5,
        strategy_used=ResolutionStrategy.CROSS_VIEW,
        success=True,
        confidence=0.85,
    )

    def call():
        orr.get_summary(SupportedLanguage.KO)
        orr.get_summary(SupportedLanguage.EN)

    elapsed = measure(call, 50000)
    per_call = elapsed / 2
    limit = 10.0
    if per_call < limit:
        r.ok("get_summary i18n", per_call, limit)
    else:
        r.fail("get_summary i18n", per_call, limit)


def test_analysis_result_methods(r: PerfResult) -> None:
    """OcclusionAnalysisResult 메서드 호출 속도"""
    from shared.dto.occlusion_dto import (
        OcclusionAnalysisResult, OcclusionResolution, ViewVisibility,
    )
    from shared.constants.occlusion_constants import ResolutionStrategy

    vv1 = ViewVisibility(camera_id="cam_01", is_visible=True)
    vv2 = ViewVisibility(camera_id="cam_02", is_visible=False, visibility_ratio=0.1)
    vis_map = {
        i: {"cam_01": vv1, "cam_02": vv2}
        for i in range(5)
    }
    resolutions = [
        OcclusionResolution(success=True, strategy_used=ResolutionStrategy.CROSS_VIEW),
        OcclusionResolution(success=False),
    ]
    oar = OcclusionAnalysisResult(
        visibility_map=vis_map,
        resolutions=resolutions,
    )

    def call():
        _ = oar.resolution_success_rate
        oar.get_object_visibility(2, "cam_01")
        oar.get_visible_objects_in_view("cam_01")

    elapsed = measure(call, 50000)
    per_call = elapsed / 3
    limit = 5.0
    if per_call < limit:
        r.ok("AnalysisResult 메서드", per_call, limit)
    else:
        r.fail("AnalysisResult 메서드", per_call, limit)


# ==================== 5. 대량 처리 ====================
def test_batch_occlusion_events(r: PerfResult) -> None:
    """OcclusionEvent 20개 배치 생성"""
    from shared.dto.occlusion_dto import OcclusionEvent
    from shared.constants.occlusion_constants import OcclusionType

    types = list(OcclusionType)

    def batch():
        for i in range(20):
            OcclusionEvent(
                occlusion_type=types[i % len(types)],
                start_frame=i * 30,
                affected_track_ids=[i, i + 1],
            )

    elapsed = measure(batch, 5000)
    limit = 300.0
    if elapsed < limit:
        r.ok("OcclusionEvent×20", elapsed, limit)
    else:
        r.fail("OcclusionEvent×20", elapsed, limit)


def test_full_analysis_snapshot(r: PerfResult) -> None:
    """풀 OcclusionAnalysisResult 스냅샷 생성"""
    from shared.dto.occlusion_dto import (
        OcclusionAnalysisResult, OcclusionEvent, OccludedObject,
        OcclusionResolution, ViewVisibility,
    )
    from shared.constants.occlusion_constants import ResolutionStrategy

    def create():
        vv = ViewVisibility(camera_id="cam_01", is_visible=True, visibility_ratio=0.8)
        objs = [
            OccludedObject(object_id=i, visibility_per_view={"cam_01": vv})
            for i in range(3)
        ]
        events = [OcclusionEvent(start_frame=i * 50) for i in range(3)]
        resolutions = [
            OcclusionResolution(success=True, strategy_used=ResolutionStrategy.CROSS_VIEW),
            OcclusionResolution(success=False),
        ]
        OcclusionAnalysisResult(
            frame_index=500,
            timestamp=16.67,
            active_occlusions=events[:2],
            resolved_occlusions=events[2:],
            occluded_objects=objs,
            resolutions=resolutions,
            processing_time_ms=3.5,
        )

    elapsed = measure(create, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("풀 AnalysisResult 스냅샷", elapsed, limit)
    else:
        r.fail("풀 AnalysisResult 스냅샷", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("occlusion_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_view_visibility_creation(r)
    test_occluded_object_creation(r)
    test_occlusion_event_creation(r)
    test_occlusion_resolution_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_view_visibility_properties(r)
    test_occluded_object_properties(r)
    test_occlusion_event_properties(r)

    print("\n--- 메서드 호출 ---")
    test_get_summary_i18n(r)
    test_analysis_result_methods(r)

    print("\n--- 대량 처리 ---")
    test_batch_occlusion_events(r)
    test_full_analysis_snapshot(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
