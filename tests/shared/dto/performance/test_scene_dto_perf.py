# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_scene_dto_perf.py

씬 DTO 성능 테스트
- 모듈 임포트 시간
- dataclass/Enum 인스턴스 생성 속도
- 프로퍼티 접근 속도
- Scene3D 검색 메서드
- 대량 배치 처리

Author: COURTVIEW AI Team
Version: 2.0.0
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
    mod_name = "shared.dto.scene_dto"
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
def test_scene_object_creation(r: PerfResult) -> None:
    """SceneObject 생성 (__post_init__ 포함)"""
    from shared.dto.scene_dto import SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    pos = Point3D(5.0, 3.0, 0.0)

    def create():
        SceneObject(
            object_id=1,
            category=ObjectCategory.PLAYER,
            position=pos,
            confidence=0.95,
            track_id=101,
            team="HOME",
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("SceneObject 생성", elapsed, limit)
    else:
        r.fail("SceneObject 생성", elapsed, limit)


def test_court_model_creation(r: PerfResult) -> None:
    """CourtModel 생성 (__post_init__ 포함)"""
    from shared.dto.scene_dto import CourtModel

    def create():
        CourtModel()

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("CourtModel 생성", elapsed, limit)
    else:
        r.fail("CourtModel 생성", elapsed, limit)


def test_hoop_model_creation(r: PerfResult) -> None:
    """HoopModel 생성"""
    from shared.dto.scene_dto import HoopModel

    def create():
        HoopModel()

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("HoopModel 생성", elapsed, limit)
    else:
        r.fail("HoopModel 생성", elapsed, limit)


def test_scene3d_creation(r: PerfResult) -> None:
    """Scene3D 생성 (빈 씬)"""
    from shared.dto.scene_dto import Scene3D

    def create():
        Scene3D()

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("Scene3D 생성 (빈)", elapsed, limit)
    else:
        r.fail("Scene3D 생성 (빈)", elapsed, limit)


def test_scene_snapshot_creation(r: PerfResult) -> None:
    """SceneSnapshot 생성"""
    from shared.dto.scene_dto import SceneSnapshot

    def create():
        SceneSnapshot(frame_index=100, timestamp=3.33)

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("SceneSnapshot 생성", elapsed, limit)
    else:
        r.fail("SceneSnapshot 생성", elapsed, limit)


def test_scene_metadata_creation(r: PerfResult) -> None:
    """SceneMetadata 생성"""
    from shared.dto.scene_dto import SceneMetadata

    def create():
        SceneMetadata(camera_count=4, fps=60.0)

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("SceneMetadata 생성", elapsed, limit)
    else:
        r.fail("SceneMetadata 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_scene_object_speed_property(r: PerfResult) -> None:
    """SceneObject.speed 프로퍼티 (numpy 연산)"""
    from shared.dto.scene_dto import SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    obj = SceneObject(
        category=ObjectCategory.PLAYER,
        position=Point3D(0, 0, 0),
        velocity=(3.0, 4.0, 0.0),
    )

    def access():
        _ = obj.speed

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("SceneObject.speed", elapsed, limit)
    else:
        r.fail("SceneObject.speed", elapsed, limit)


def test_court_bounds_property(r: PerfResult) -> None:
    """CourtModel.bounds 프로퍼티"""
    from shared.dto.scene_dto import CourtModel

    court = CourtModel()

    def access():
        _ = court.bounds

    elapsed = measure(access, 100000)
    limit = 3.0
    if elapsed < limit:
        r.ok("CourtModel.bounds", elapsed, limit)
    else:
        r.fail("CourtModel.bounds", elapsed, limit)


def test_i18n_get_name(r: PerfResult) -> None:
    """Enum i18n get_name 속도"""
    from shared.dto.scene_dto import SceneStatus
    from shared.constants.localization import SupportedLanguage

    def access():
        SceneStatus.COMPLETE.get_name(SupportedLanguage.KO)

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("SceneStatus.get_name(KO)", elapsed, limit)
    else:
        r.fail("SceneStatus.get_name(KO)", elapsed, limit)


# ==================== 4. Scene3D 검색 메서드 ====================
def test_scene3d_get_object(r: PerfResult) -> None:
    """Scene3D.get_object (20개 객체)"""
    from shared.dto.scene_dto import Scene3D, SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    objects = [
        SceneObject(object_id=i, category=ObjectCategory.PLAYER, position=Point3D(float(i), 0, 0))
        for i in range(20)
    ]
    scene = Scene3D(objects=objects)

    def search():
        scene.get_object(15)

    elapsed = measure(search, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("get_object (20개 중)", elapsed, limit)
    else:
        r.fail("get_object (20개 중)", elapsed, limit)


def test_scene3d_players_property(r: PerfResult) -> None:
    """Scene3D.players 프로퍼티 (20개 중 10명 선수)"""
    from shared.dto.scene_dto import Scene3D, SceneObject, ObjectCategory

    objects = []
    for i in range(20):
        cat = ObjectCategory.PLAYER if i < 10 else ObjectCategory.REFEREE
        objects.append(SceneObject(object_id=i, category=cat))
    scene = Scene3D(objects=objects)

    def access():
        _ = scene.players

    elapsed = measure(access, 20000)
    limit = 20.0
    if elapsed < limit:
        r.ok("Scene3D.players (20객체)", elapsed, limit)
    else:
        r.fail("Scene3D.players (20객체)", elapsed, limit)


def test_scene3d_nearest_player(r: PerfResult) -> None:
    """Scene3D.get_nearest_player_to_ball (10명 선수)"""
    from shared.dto.scene_dto import Scene3D, SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    ball = SceneObject(object_id=100, category=ObjectCategory.BALL, position=Point3D(5, 3, 1))
    objects = [
        SceneObject(
            object_id=i,
            category=ObjectCategory.PLAYER,
            position=Point3D(float(i), float(i % 5), 0),
        )
        for i in range(10)
    ]
    scene = Scene3D(objects=objects, ball=ball)

    def search():
        scene.get_nearest_player_to_ball()

    elapsed = measure(search, 10000)
    limit = 50.0
    if elapsed < limit:
        r.ok("get_nearest_player_to_ball (10명)", elapsed, limit)
    else:
        r.fail("get_nearest_player_to_ball (10명)", elapsed, limit)


# ==================== 5. 대량 배치 처리 ====================
def test_batch_scene_objects(r: PerfResult) -> None:
    """SceneObject 20개 배치 생성"""
    from shared.dto.scene_dto import SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    def batch():
        for i in range(20):
            SceneObject(
                object_id=i,
                category=ObjectCategory.PLAYER,
                position=Point3D(float(i), float(i % 5), 0),
                confidence=0.8 + i * 0.01,
            )

    elapsed = measure(batch, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("SceneObject×20 배치", elapsed, limit)
    else:
        r.fail("SceneObject×20 배치", elapsed, limit)


def test_full_scene_creation(r: PerfResult) -> None:
    """풀 Scene3D (10선수 + 코트 + 골대 2개 + 공)"""
    from shared.dto.scene_dto import (
        Scene3D, SceneObject, ObjectCategory, CourtModel, HoopModel, SceneStatus,
    )
    from shared.dto.geometry_dto import Point3D

    def create():
        objects = [
            SceneObject(
                object_id=i,
                category=ObjectCategory.PLAYER,
                position=Point3D(float(i), float(i % 5), 0),
                confidence=0.9,
                team="HOME" if i < 5 else "AWAY",
            )
            for i in range(10)
        ]
        ball = SceneObject(
            object_id=100,
            category=ObjectCategory.BALL,
            position=Point3D(7, 3, 1),
        )
        court = CourtModel()
        hoops = [HoopModel(), HoopModel(is_left_side=False)]
        Scene3D(
            status=SceneStatus.COMPLETE,
            objects=objects,
            court=court,
            hoops=hoops,
            ball=ball,
            confidence=0.92,
        )

    elapsed = measure(create, 2000)
    limit = 200.0
    if elapsed < limit:
        r.ok("풀 Scene3D (10+1+2)", elapsed, limit)
    else:
        r.fail("풀 Scene3D (10+1+2)", elapsed, limit)


def test_timeline_trajectory(r: PerfResult) -> None:
    """SceneTimeline.get_object_trajectory (30 스냅샷)"""
    from shared.dto.scene_dto import SceneTimeline, SceneSnapshot, Scene3D, SceneObject, ObjectCategory
    from shared.dto.geometry_dto import Point3D

    snapshots = []
    for i in range(30):
        obj = SceneObject(object_id=1, category=ObjectCategory.PLAYER, position=Point3D(float(i), 0, 0))
        scene = Scene3D(objects=[obj])
        snapshots.append(SceneSnapshot(scene=scene, frame_index=i))
    tl = SceneTimeline(snapshots=snapshots)

    def trajectory():
        tl.get_object_trajectory(1)

    elapsed = measure(trajectory, 5000)
    limit = 100.0
    if elapsed < limit:
        r.ok("trajectory (30 스냅샷)", elapsed, limit)
    else:
        r.fail("trajectory (30 스냅샷)", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("scene_dto.py v2.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_scene_object_creation(r)
    test_court_model_creation(r)
    test_hoop_model_creation(r)
    test_scene3d_creation(r)
    test_scene_snapshot_creation(r)
    test_scene_metadata_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_scene_object_speed_property(r)
    test_court_bounds_property(r)
    test_i18n_get_name(r)

    print("\n--- Scene3D 검색 ---")
    test_scene3d_get_object(r)
    test_scene3d_players_property(r)
    test_scene3d_nearest_player(r)

    print("\n--- 대량 배치 처리 ---")
    test_batch_scene_objects(r)
    test_full_scene_creation(r)
    test_timeline_trajectory(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
