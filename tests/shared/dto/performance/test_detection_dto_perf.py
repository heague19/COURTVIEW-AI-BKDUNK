# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_detection_dto_perf.py

감지 결과 통합 DTO 성능 테스트
- 모듈 임포트 시간
- 데이터클래스 인스턴스 생성 속도
- 프로퍼티 접근 속도
- i18n 조회 속도 (모듈 레벨 캐시)
- IoU / distance 연산 속도
- 대량 감지 결과 처리 속도

성능 기준:
- 모듈 임포트: < 500ms (cold)
- 데이터클래스 생성: < 10μs
- 프로퍼티 접근: < 5μs
- i18n 조회: < 5μs (캐시 적용)

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
    mod_name = "shared.dto.detection_dto"
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


# ==================== 2. 데이터클래스 생성 ====================
def test_detected_object_creation(r: PerfResult) -> None:
    """DetectedObject 인스턴스 생성 속도"""
    from shared.dto.detection_dto import DetectedObject, ObjectType, DetectionSource
    from shared.dto.geometry_dto import BoundingBox
    bbox = BoundingBox(x=100, y=200, width=50, height=60)

    def create():
        DetectedObject(
            object_id=1,
            object_type=ObjectType.PLAYER,
            bbox=bbox,
            confidence=0.9,
            source=DetectionSource.YOLOV8,
        )

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("DetectedObject 생성", elapsed, limit)
    else:
        r.fail("DetectedObject 생성", elapsed, limit)


def test_detection_config_creation(r: PerfResult) -> None:
    """DetectionConfig 인스턴스 생성 속도"""
    from shared.dto.detection_dto import DetectionConfig

    def create():
        DetectionConfig()

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("DetectionConfig 생성", elapsed, limit)
    else:
        r.fail("DetectionConfig 생성", elapsed, limit)


def test_detection_result_creation(r: PerfResult) -> None:
    """DetectionResult 인스턴스 생성 속도"""
    from shared.dto.detection_dto import DetectionResult

    def create():
        DetectionResult(frame_index=100, timestamp=1.5)

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("DetectionResult 생성", elapsed, limit)
    else:
        r.fail("DetectionResult 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_is_valid_speed(r: PerfResult) -> None:
    """DetectedObject.is_valid 프로퍼티 접근 속도"""
    from shared.dto.detection_dto import DetectedObject, ObjectType
    from shared.dto.geometry_dto import BoundingBox
    obj = DetectedObject(
        object_type=ObjectType.PLAYER,
        bbox=BoundingBox(x=0, y=0, width=50, height=50),
        confidence=0.9,
    )

    def access():
        _ = obj.is_valid

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("is_valid", elapsed, limit)
    else:
        r.fail("is_valid", elapsed, limit)


def test_num_objects_speed(r: PerfResult) -> None:
    """DetectionResult.num_objects 프로퍼티 접근 속도"""
    from shared.dto.detection_dto import DetectionResult, DetectedObject
    res = DetectionResult(objects=[DetectedObject() for _ in range(20)])

    def access():
        _ = res.num_objects

    elapsed = measure(access, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("num_objects", elapsed, limit)
    else:
        r.fail("num_objects", elapsed, limit)


def test_average_confidence_speed(r: PerfResult) -> None:
    """DetectionResult.average_confidence 속도"""
    from shared.dto.detection_dto import DetectionResult, DetectedObject
    res = DetectionResult(objects=[DetectedObject(confidence=0.5 + i * 0.02) for i in range(20)])

    def access():
        _ = res.average_confidence

    elapsed = measure(access, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("average_confidence(20)", elapsed, limit)
    else:
        r.fail("average_confidence(20)", elapsed, limit)


# ==================== 4. i18n 조회 ====================
def test_i18n_object_type_speed(r: PerfResult) -> None:
    """ObjectType.get_name i18n 조회 속도 (캐시 적용)"""
    from shared.dto.detection_dto import ObjectType
    from shared.constants.localization import SupportedLanguage
    t = ObjectType.PLAYER

    def lookup():
        _ = t.get_name(SupportedLanguage.KO)
        _ = t.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("ObjectType i18n", per_call, limit)
    else:
        r.fail("ObjectType i18n", per_call, limit)


def test_i18n_detection_source_speed(r: PerfResult) -> None:
    """DetectionSource.get_name i18n 조회 속도 (캐시 적용)"""
    from shared.dto.detection_dto import DetectionSource
    from shared.constants.localization import SupportedLanguage
    s = DetectionSource.YOLOV8

    def lookup():
        _ = s.get_name(SupportedLanguage.KO)
        _ = s.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("DetectionSource i18n", per_call, limit)
    else:
        r.fail("DetectionSource i18n", per_call, limit)


# ==================== 5. IoU / distance 연산 ====================
def test_iou_speed(r: PerfResult) -> None:
    """DetectedObject.iou_with() 연산 속도"""
    from shared.dto.detection_dto import DetectedObject
    from shared.dto.geometry_dto import BoundingBox
    obj1 = DetectedObject(bbox=BoundingBox(x=0, y=0, width=100, height=100), confidence=0.9)
    obj2 = DetectedObject(bbox=BoundingBox(x=50, y=50, width=100, height=100), confidence=0.9)

    def calc():
        _ = obj1.iou_with(obj2)

    elapsed = measure(calc, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("iou_with()", elapsed, limit)
    else:
        r.fail("iou_with()", elapsed, limit)


def test_distance_speed(r: PerfResult) -> None:
    """DetectedObject.distance_to() 연산 속도"""
    from shared.dto.detection_dto import DetectedObject
    from shared.dto.geometry_dto import BoundingBox
    obj1 = DetectedObject(bbox=BoundingBox(x=0, y=0, width=10, height=10), confidence=0.9)
    obj2 = DetectedObject(bbox=BoundingBox(x=100, y=100, width=10, height=10), confidence=0.9)

    def calc():
        _ = obj1.distance_to(obj2)

    elapsed = measure(calc, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("distance_to()", elapsed, limit)
    else:
        r.fail("distance_to()", elapsed, limit)


# ==================== 6. 대량 처리 ====================
def test_batch_detection_result(r: PerfResult) -> None:
    """DetectionResult 50개 객체 생성 + 필터링 속도"""
    from shared.dto.detection_dto import DetectionResult, DetectedObject, ObjectType
    from shared.dto.geometry_dto import BoundingBox

    bbox = BoundingBox(x=10, y=10, width=50, height=50)
    objects = [
        DetectedObject(
            object_id=i,
            object_type=ObjectType.PLAYER if i % 3 == 0 else ObjectType.BALL,
            bbox=bbox,
            confidence=0.5 + (i % 50) * 0.01,
        )
        for i in range(50)
    ]
    res = DetectionResult(objects=objects)

    def process():
        _ = res.num_players
        _ = res.has_ball
        _ = res.average_confidence
        _ = res.filter_by_confidence(0.7)

    elapsed = measure(process, 10000)
    limit = 50.0
    if elapsed < limit:
        r.ok("DetectionResult(50 objs) 처리", elapsed, limit)
    else:
        r.fail("DetectionResult(50 objs) 처리", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("detection_dto.py v2.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 데이터클래스 생성 ---")
    test_detected_object_creation(r)
    test_detection_config_creation(r)
    test_detection_result_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_is_valid_speed(r)
    test_num_objects_speed(r)
    test_average_confidence_speed(r)

    print("\n--- i18n 조회 ---")
    test_i18n_object_type_speed(r)
    test_i18n_detection_source_speed(r)

    print("\n--- IoU / distance ---")
    test_iou_speed(r)
    test_distance_speed(r)

    print("\n--- 대량 처리 ---")
    test_batch_detection_result(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
