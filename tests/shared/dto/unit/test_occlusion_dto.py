# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_occlusion_dto.py

오클루전 DTO 유닛 테스트
- 모듈 구조 (__version__, __all__, typing 모던화)
- ViewVisibility (__post_init__ 클램프, 프로퍼티 5개)
- OccludedObject (프로퍼티 5개, get_visible_views, occlusion_duration_frames)
- OcclusionEvent (is_active, duration, mark_ended/resolved, add_affected_track, is_recoverable)
- OcclusionResolution (전략 프로퍼티, has_ 프로퍼티, get_summary i18n)
- OcclusionAnalysisResult (프로퍼티, get_object_visibility, get_visible_objects_in_view)

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

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
            self.fail(name, f"{actual!r} != {expected!r}")

    def true(self, name: str, condition: bool) -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, "condition is False")

    def near(self, name: str, actual: float, expected: float, tol: float = 1e-6) -> None:
        if abs(actual - expected) < tol:
            self.ok(name)
        else:
            self.fail(name, f"{actual} != {expected} (tol={tol})")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ==================== 1. 모듈 구조 ====================
def test_module_structure(r: TestResult) -> None:
    """모듈 메타데이터 및 구조 검증"""
    import shared.dto.occlusion_dto as mod

    r.eq("__version__ == 1.1.0", mod.__version__, "1.1.0")
    r.eq("__all__ 항목 수 == 9", len(mod.__all__), 9)

    import inspect
    source = inspect.getsource(mod)
    legacy_count = sum(
        source.count(pat) for pat in ["Optional[", "List[", "Dict[", "Tuple[", "Set[", "Union["]
    )
    r.eq("레거시 typing 없음", legacy_count, 0)


# ==================== 2. ViewVisibility ====================
def test_view_visibility_defaults(r: TestResult) -> None:
    """ViewVisibility 기본값 및 __post_init__ 검증"""
    from shared.dto.occlusion_dto import ViewVisibility

    vv = ViewVisibility(camera_id="cam_01")
    r.eq("camera_id", vv.camera_id, "cam_01")
    r.true("is_visible 기본 True", vv.is_visible)
    r.near("visibility_ratio 기본 1.0", vv.visibility_ratio, 1.0)
    r.near("confidence 기본 1.0", vv.confidence, 1.0)
    r.true("depth_estimate is None", vv.depth_estimate is None)
    r.eq("visible_keypoints 빈 set", vv.visible_keypoints, set())
    r.eq("occluded_keypoints 빈 set", vv.occluded_keypoints, set())


def test_view_visibility_clamp(r: TestResult) -> None:
    """__post_init__ 범위 클램프 검증"""
    from shared.dto.occlusion_dto import ViewVisibility

    # 초과값
    vv = ViewVisibility(camera_id="cam", visibility_ratio=1.5, confidence=2.0)
    r.near("visibility_ratio 클램프→1.0", vv.visibility_ratio, 1.0)
    r.near("confidence 클램프→1.0", vv.confidence, 1.0)

    # 음수값
    vv2 = ViewVisibility(camera_id="cam", visibility_ratio=-0.5, confidence=-1.0)
    r.near("visibility_ratio 클램프→0.0", vv2.visibility_ratio, 0.0)
    r.near("confidence 클램프→0.0", vv2.confidence, 0.0)


def test_view_visibility_properties(r: TestResult) -> None:
    """ViewVisibility 프로퍼티 검증"""
    from shared.dto.occlusion_dto import ViewVisibility

    vv = ViewVisibility(
        camera_id="cam_01",
        visible_keypoints={0, 1, 2, 3, 4},
        occluded_keypoints={5, 6, 7},
        visibility_ratio=0.6,
    )
    r.eq("total_keypoints", vv.total_keypoints, 8)
    r.near("visible_keypoint_ratio", vv.visible_keypoint_ratio, 5 / 8)
    r.true("is_partially_visible", vv.is_partially_visible)
    r.true("not is_fully_visible", not vv.is_fully_visible)
    r.true("not is_fully_occluded", not vv.is_fully_occluded)

    # 완전 가시
    vv2 = ViewVisibility(camera_id="cam", visibility_ratio=0.95)
    r.true("is_fully_visible (0.95)", vv2.is_fully_visible)

    # 완전 가림
    vv3 = ViewVisibility(camera_id="cam", visibility_ratio=0.05)
    r.true("is_fully_occluded (0.05)", vv3.is_fully_occluded)

    # 빈 키포인트
    vv4 = ViewVisibility(camera_id="cam")
    r.eq("total_keypoints (빈)", vv4.total_keypoints, 0)
    r.near("visible_keypoint_ratio (빈)", vv4.visible_keypoint_ratio, 0.0)


# ==================== 3. OccludedObject ====================
def test_occluded_object(r: TestResult) -> None:
    """OccludedObject 데이터클래스 검증"""
    from shared.dto.occlusion_dto import OccludedObject, ViewVisibility
    from shared.dto.geometry_dto import BoundingBox, Point2D, Point3D

    oo = OccludedObject(object_id=5)
    r.eq("object_id", oo.object_id, 5)
    r.eq("기본 object_type", oo.object_type, "unknown")
    r.eq("num_occluders (빈)", oo.num_occluders, 0)
    r.eq("num_visible_views (빈)", oo.num_visible_views, 0)
    r.eq("total_views (빈)", oo.total_views, 0)
    r.true("best_visible_view is None (빈)", oo.best_visible_view is None)
    r.near("average_visibility (빈)", oo.average_visibility, 0.0)

    # 전체 인자
    vv1 = ViewVisibility(camera_id="cam_01", is_visible=True, visibility_ratio=0.8)
    vv2 = ViewVisibility(camera_id="cam_02", is_visible=False, visibility_ratio=0.1)
    oo2 = OccludedObject(
        object_id=3,
        object_type="player",
        last_known_bbox=BoundingBox(10, 20, 50, 80),
        last_known_position=Point2D(35.0, 60.0),
        last_known_position_3d=Point3D(5.0, 3.0, 1.8),
        occluded_since_frame=100,
        occluder_ids=[7, 8],
        visibility_per_view={"cam_01": vv1, "cam_02": vv2},
        estimated_position=Point2D(36.0, 61.0),
        estimation_confidence=0.75,
    )
    r.eq("num_occluders", oo2.num_occluders, 2)
    r.eq("num_visible_views", oo2.num_visible_views, 1)
    r.eq("total_views", oo2.total_views, 2)
    r.eq("best_visible_view", oo2.best_visible_view, "cam_01")
    r.near("average_visibility", oo2.average_visibility, 0.45)
    r.eq("get_visible_views", oo2.get_visible_views(), ["cam_01"])
    r.eq("occlusion_duration_frames(150)", oo2.occlusion_duration_frames(150), 50)


def test_occluded_object_best_view_logic(r: TestResult) -> None:
    """best_visible_view: 모든 뷰 invisible → None"""
    from shared.dto.occlusion_dto import OccludedObject, ViewVisibility

    vv = ViewVisibility(camera_id="cam_01", is_visible=False, visibility_ratio=0.05)
    oo = OccludedObject(
        object_id=1,
        visibility_per_view={"cam_01": vv},
    )
    r.true("best_visible_view None (all invisible)", oo.best_visible_view is None)


# ==================== 4. OcclusionEvent ====================
def test_occlusion_event_defaults(r: TestResult) -> None:
    """OcclusionEvent 기본값 검증"""
    from shared.dto.occlusion_dto import OcclusionEvent
    from shared.constants.occlusion_constants import OcclusionType, OcclusionSeverity

    oe = OcclusionEvent()
    r.true("event_id는 UUID", isinstance(oe.event_id, UUID))
    r.eq("기본 occlusion_type", oe.occlusion_type, OcclusionType.UNKNOWN)
    r.eq("기본 severity", oe.severity, OcclusionSeverity.NONE)
    r.true("end_frame is None", oe.end_frame is None)
    r.true("is_active (기본)", oe.is_active)
    r.true("duration_frames is None", oe.duration_frames is None)
    r.true("duration_seconds is None", oe.duration_seconds is None)
    r.eq("num_affected_tracks (빈)", oe.num_affected_tracks, 0)
    r.true("not is_multi_object", not oe.is_multi_object)


def test_occlusion_event_with_data(r: TestResult) -> None:
    """OcclusionEvent 데이터 및 프로퍼티 검증"""
    from shared.dto.occlusion_dto import OcclusionEvent
    from shared.constants.occlusion_constants import OcclusionType, OcclusionSeverity

    now = datetime.now(timezone.utc)
    later = now + timedelta(seconds=2.5)

    oe = OcclusionEvent(
        occlusion_type=OcclusionType.INTER_PLAYER,
        severity=OcclusionSeverity.PARTIAL,
        start_frame=100,
        end_frame=175,
        start_time=now,
        end_time=later,
        affected_track_ids=[3, 5],
        occluder_track_ids=[7],
        overlap_iou=0.35,
    )
    r.true("not is_active (end_frame set)", not oe.is_active)
    r.eq("duration_frames", oe.duration_frames, 75)
    r.near("duration_seconds", oe.duration_seconds, 2.5)
    r.eq("num_affected_tracks", oe.num_affected_tracks, 2)
    r.true("is_multi_object", oe.is_multi_object)


def test_occlusion_event_methods(r: TestResult) -> None:
    """OcclusionEvent mark_ended, mark_resolved, add_affected_track"""
    from shared.dto.occlusion_dto import OcclusionEvent, OccludedObject
    from shared.constants.occlusion_constants import OcclusionType, ResolutionStrategy

    oe = OcclusionEvent(occlusion_type=OcclusionType.INTER_PLAYER, start_frame=50)
    r.true("is_active 초기", oe.is_active)

    # mark_ended
    oe.mark_ended(end_frame=100)
    r.eq("end_frame 설정", oe.end_frame, 100)
    r.true("end_time 자동 설정", oe.end_time is not None)
    r.true("not is_active (ended)", not oe.is_active)

    # mark_resolved
    oe.mark_resolved(ResolutionStrategy.CROSS_VIEW)
    r.true("is_resolved", oe.is_resolved)
    r.eq("resolution_strategy", oe.resolution_strategy, ResolutionStrategy.CROSS_VIEW)

    # add_affected_track
    oe2 = OcclusionEvent(start_frame=10)
    oo = OccludedObject(object_id=5, object_type="player")
    oe2.add_affected_track(5, oo)
    r.eq("affected_track_ids", oe2.affected_track_ids, [5])
    r.eq("affected_objects 수", len(oe2.affected_objects), 1)

    # 중복 트랙 추가 방지
    oe2.add_affected_track(5)
    r.eq("중복 방지", len(oe2.affected_track_ids), 1)

    # 새 트랙 추가
    oe2.add_affected_track(7)
    r.eq("새 트랙 추가", len(oe2.affected_track_ids), 2)


def test_occlusion_event_recoverable(r: TestResult) -> None:
    """OcclusionEvent is_recoverable, recommended_strategy"""
    from shared.dto.occlusion_dto import OcclusionEvent
    from shared.constants.occlusion_constants import OcclusionType

    oe = OcclusionEvent(occlusion_type=OcclusionType.INTER_PLAYER)
    # is_recoverable와 recommended_strategy는 OcclusionType의 프로퍼티에 위임
    r.true("is_recoverable 호출 가능", isinstance(oe.is_recoverable, bool))
    r.true("recommended_strategy 호출 가능", oe.recommended_strategy is not None)


# ==================== 5. OcclusionResolution ====================
def test_occlusion_resolution_defaults(r: TestResult) -> None:
    """OcclusionResolution 기본값 검증"""
    from shared.dto.occlusion_dto import OcclusionResolution
    from shared.constants.occlusion_constants import ResolutionStrategy

    orr = OcclusionResolution()
    r.true("event_id is None", orr.event_id is None)
    r.eq("strategy_used NONE", orr.strategy_used, ResolutionStrategy.NONE)
    r.true("not success", not orr.success)
    r.true("not has_position", not orr.has_position)
    r.true("not has_3d_position", not orr.has_3d_position)
    r.true("not has_bbox", not orr.has_bbox)
    r.eq("num_fallback_attempts", orr.num_fallback_attempts, 0)
    r.true("error_message is None", orr.error_message is None)


def test_occlusion_resolution_strategies(r: TestResult) -> None:
    """OcclusionResolution 전략 프로퍼티 검증"""
    from shared.dto.occlusion_dto import OcclusionResolution
    from shared.constants.occlusion_constants import ResolutionStrategy
    from shared.dto.geometry_dto import Point2D, Point3D, BoundingBox

    # CROSS_VIEW
    orr = OcclusionResolution(
        strategy_used=ResolutionStrategy.CROSS_VIEW,
        success=True,
        confidence=0.85,
        recovered_position=Point2D(100.0, 200.0),
        recovered_position_3d=Point3D(5.0, 3.0, 1.8),
        recovered_bbox=BoundingBox(90, 180, 30, 60),
        source_view_id="cam_02",
    )
    r.true("is_cross_view_recovery", orr.is_cross_view_recovery)
    r.true("not is_interpolated", not orr.is_interpolated)
    r.true("not is_predicted", not orr.is_predicted)
    r.true("has_position", orr.has_position)
    r.true("has_3d_position", orr.has_3d_position)
    r.true("has_bbox", orr.has_bbox)

    # INTERPOLATION
    orr2 = OcclusionResolution(strategy_used=ResolutionStrategy.INTERPOLATION)
    r.true("is_interpolated", orr2.is_interpolated)

    # PREDICTION
    orr3 = OcclusionResolution(strategy_used=ResolutionStrategy.PREDICTION)
    r.true("is_predicted", orr3.is_predicted)


def test_occlusion_resolution_i18n(r: TestResult) -> None:
    """OcclusionResolution get_summary 다국어 검증"""
    from shared.dto.occlusion_dto import OcclusionResolution
    from shared.constants.occlusion_constants import ResolutionStrategy
    from shared.constants.localization import SupportedLanguage

    # 성공
    orr = OcclusionResolution(
        track_id=5,
        strategy_used=ResolutionStrategy.CROSS_VIEW,
        success=True,
        confidence=0.85,
    )
    ko = orr.get_summary(SupportedLanguage.KO)
    r.true("한국어 성공 요약에 '5' 포함", "5" in ko)
    r.true("한국어 성공 요약에 '85' 포함", "85" in ko)

    en = orr.get_summary(SupportedLanguage.EN)
    r.true("영어 성공 요약에 'Track 5' 포함", "Track 5" in en)

    ja = orr.get_summary(SupportedLanguage.JA)
    r.true("일본어 성공 요약에 'トラック' 포함", "トラック" in ja)

    # 실패
    orr2 = OcclusionResolution(
        track_id=3,
        success=False,
        error_message="시야 확보 불가",
    )
    ko2 = orr2.get_summary(SupportedLanguage.KO)
    r.true("한국어 실패 요약에 '실패' 포함", "실패" in ko2)

    # to_korean_summary (하위 호환성)
    ko3 = orr.to_korean_summary()
    r.eq("to_korean_summary == get_summary(KO)", ko3, ko)

    # 실패 시 error_message 없으면 기본 메시지
    orr3 = OcclusionResolution(track_id=1, success=False)
    ko4 = orr3.get_summary(SupportedLanguage.KO)
    r.true("기본 오류 메시지 포함", "알 수 없는 오류" in ko4)


# ==================== 6. OcclusionAnalysisResult ====================
def test_occlusion_analysis_result(r: TestResult) -> None:
    """OcclusionAnalysisResult 프로퍼티 및 메서드 검증"""
    from shared.dto.occlusion_dto import (
        OcclusionAnalysisResult, OcclusionEvent, OccludedObject,
        OcclusionResolution, ViewVisibility,
    )
    from shared.constants.occlusion_constants import ResolutionStrategy

    # 기본값
    oar = OcclusionAnalysisResult()
    r.eq("num_active_occlusions (빈)", oar.num_active_occlusions, 0)
    r.eq("num_occluded_objects (빈)", oar.num_occluded_objects, 0)
    r.eq("num_successful_resolutions (빈)", oar.num_successful_resolutions, 0)
    r.near("resolution_success_rate (빈)", oar.resolution_success_rate, 0.0)

    # 전체 인자
    active = [OcclusionEvent(), OcclusionEvent()]
    resolved = [OcclusionEvent(end_frame=100)]
    objects = [OccludedObject(object_id=1), OccludedObject(object_id=2)]
    resolutions = [
        OcclusionResolution(success=True, strategy_used=ResolutionStrategy.CROSS_VIEW),
        OcclusionResolution(success=False),
        OcclusionResolution(success=True, strategy_used=ResolutionStrategy.INTERPOLATION),
    ]
    vv1 = ViewVisibility(camera_id="cam_01", is_visible=True, visibility_ratio=0.9)
    vv2 = ViewVisibility(camera_id="cam_02", is_visible=False, visibility_ratio=0.1)
    vis_map = {
        1: {"cam_01": vv1, "cam_02": vv2},
        2: {"cam_01": ViewVisibility(camera_id="cam_01", is_visible=True)},
    }
    oar2 = OcclusionAnalysisResult(
        frame_index=500,
        timestamp=16.67,
        active_occlusions=active,
        resolved_occlusions=resolved,
        occluded_objects=objects,
        visibility_map=vis_map,
        resolutions=resolutions,
        processing_time_ms=3.5,
    )
    r.eq("num_active_occlusions", oar2.num_active_occlusions, 2)
    r.eq("num_occluded_objects", oar2.num_occluded_objects, 2)
    r.eq("num_successful_resolutions", oar2.num_successful_resolutions, 2)
    r.near("resolution_success_rate", oar2.resolution_success_rate, 2 / 3)

    # get_object_visibility
    gv = oar2.get_object_visibility(1, "cam_01")
    r.true("get_object_visibility 반환됨", gv is not None)
    r.near("가시 비율 0.9", gv.visibility_ratio, 0.9)

    gv_none = oar2.get_object_visibility(99, "cam_01")
    r.true("존재하지 않는 객체 → None", gv_none is None)

    gv_none2 = oar2.get_object_visibility(1, "cam_99")
    r.true("존재하지 않는 뷰 → None", gv_none2 is None)

    # get_visible_objects_in_view
    visible_cam01 = oar2.get_visible_objects_in_view("cam_01")
    r.eq("cam_01 가시 객체 수", len(visible_cam01), 2)
    r.true("객체 1 가시", 1 in visible_cam01)
    r.true("객체 2 가시", 2 in visible_cam01)

    visible_cam02 = oar2.get_visible_objects_in_view("cam_02")
    r.eq("cam_02 가시 객체 수", len(visible_cam02), 0)


# ==================== 7. __all__ Export 검증 ====================
def test_all_exports(r: TestResult) -> None:
    """__all__에 정의된 모든 클래스 임포트 가능 검증"""
    import shared.dto.occlusion_dto as mod

    for name in mod.__all__:
        obj = getattr(mod, name, None)
        r.true(f"export {name} 존재", obj is not None)


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("occlusion_dto.py v1.1.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)

    print("\n--- ViewVisibility 기본값 ---")
    test_view_visibility_defaults(r)

    print("\n--- ViewVisibility 클램프 ---")
    test_view_visibility_clamp(r)

    print("\n--- ViewVisibility 프로퍼티 ---")
    test_view_visibility_properties(r)

    print("\n--- OccludedObject ---")
    test_occluded_object(r)

    print("\n--- OccludedObject best_view 로직 ---")
    test_occluded_object_best_view_logic(r)

    print("\n--- OcclusionEvent 기본값 ---")
    test_occlusion_event_defaults(r)

    print("\n--- OcclusionEvent 데이터 ---")
    test_occlusion_event_with_data(r)

    print("\n--- OcclusionEvent 메서드 ---")
    test_occlusion_event_methods(r)

    print("\n--- OcclusionEvent recoverable ---")
    test_occlusion_event_recoverable(r)

    print("\n--- OcclusionResolution 기본값 ---")
    test_occlusion_resolution_defaults(r)

    print("\n--- OcclusionResolution 전략 ---")
    test_occlusion_resolution_strategies(r)

    print("\n--- OcclusionResolution i18n ---")
    test_occlusion_resolution_i18n(r)

    print("\n--- OcclusionAnalysisResult ---")
    test_occlusion_analysis_result(r)

    print("\n--- __all__ Export ---")
    test_all_exports(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
