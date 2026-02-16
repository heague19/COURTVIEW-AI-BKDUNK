# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_reid_dto_perf.py

Re-ID DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도
- numpy 벡터 연산 (cosine_similarity, normalize)
- GalleryEntry EMA 업데이트
- ReIDGallery query 검색
- 대량 배치 처리

Author: COURTVIEW AI Team
Version: 1.1.0
"""

import gc
import sys
import time
from pathlib import Path

import numpy as np

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
    mod_name = "shared.dto.reid_dto"
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
def test_reid_feature_creation(r: PerfResult) -> None:
    """ReIDFeature 생성 (__post_init__ 포함)"""
    from shared.dto.reid_dto import ReIDFeature

    vec = np.random.randn(512).astype(np.float32)

    def create():
        ReIDFeature(feature=vec, confidence=0.9, frame_index=100)

    elapsed = measure(create, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("ReIDFeature 생성", elapsed, limit)
    else:
        r.fail("ReIDFeature 생성", elapsed, limit)


def test_gallery_entry_creation(r: PerfResult) -> None:
    """GalleryEntry 생성"""
    from shared.dto.reid_dto import GalleryEntry

    def create():
        GalleryEntry(person_id=23, team="HOME", jersey_number=7)

    elapsed = measure(create, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("GalleryEntry 생성", elapsed, limit)
    else:
        r.fail("GalleryEntry 생성", elapsed, limit)


def test_reid_match_creation(r: PerfResult) -> None:
    """ReIDMatch 생성"""
    from shared.dto.reid_dto import ReIDMatch, MatchStatus

    def create():
        ReIDMatch(
            status=MatchStatus.MATCHED,
            matched_person_id=5,
            similarity=0.92,
            confidence=0.88,
            candidates=[(5, 0.92), (3, 0.75)],
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("ReIDMatch 생성", elapsed, limit)
    else:
        r.fail("ReIDMatch 생성", elapsed, limit)


def test_reid_result_creation(r: PerfResult) -> None:
    """ReIDResult 생성"""
    from shared.dto.reid_dto import ReIDResult

    def create():
        ReIDResult(frame_index=100, timestamp=3.33, gallery_updates=5)

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("ReIDResult 생성", elapsed, limit)
    else:
        r.fail("ReIDResult 생성", elapsed, limit)


def test_reid_gallery_creation(r: PerfResult) -> None:
    """ReIDGallery 생성"""
    from shared.dto.reid_dto import ReIDGallery

    def create():
        ReIDGallery(max_entries=50)

    elapsed = measure(create, 50000)
    limit = 15.0
    if elapsed < limit:
        r.ok("ReIDGallery 생성", elapsed, limit)
    else:
        r.fail("ReIDGallery 생성", elapsed, limit)


# ==================== 3. numpy 벡터 연산 ====================
def test_cosine_similarity_speed(r: PerfResult) -> None:
    """cosine_similarity 속도 (정규화된 512차원)"""
    from shared.dto.reid_dto import ReIDFeature

    v1 = np.random.randn(512).astype(np.float32)
    v1 /= np.linalg.norm(v1)
    v2 = np.random.randn(512).astype(np.float32)
    v2 /= np.linalg.norm(v2)
    f1 = ReIDFeature(feature=v1)
    f2 = ReIDFeature(feature=v2)

    def sim():
        f1.cosine_similarity(f2)

    elapsed = measure(sim, 100000)
    limit = 10.0
    if elapsed < limit:
        r.ok("cosine_similarity (정규화)", elapsed, limit)
    else:
        r.fail("cosine_similarity (정규화)", elapsed, limit)


def test_cosine_similarity_unnormalized(r: PerfResult) -> None:
    """cosine_similarity 속도 (비정규화)"""
    from shared.dto.reid_dto import ReIDFeature

    v1 = np.random.randn(512).astype(np.float32) * 3.0
    v2 = np.random.randn(512).astype(np.float32) * 5.0
    f1 = ReIDFeature(feature=v1)
    f2 = ReIDFeature(feature=v2)

    def sim():
        f1.cosine_similarity(f2)

    elapsed = measure(sim, 100000)
    limit = 15.0
    if elapsed < limit:
        r.ok("cosine_similarity (비정규화)", elapsed, limit)
    else:
        r.fail("cosine_similarity (비정규화)", elapsed, limit)


def test_normalize_speed(r: PerfResult) -> None:
    """normalize() 속도"""
    from shared.dto.reid_dto import ReIDFeature

    vec = np.random.randn(512).astype(np.float32)
    feat = ReIDFeature(feature=vec)

    def norm():
        feat.normalize()

    elapsed = measure(norm, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("normalize()", elapsed, limit)
    else:
        r.fail("normalize()", elapsed, limit)


def test_euclidean_distance_speed(r: PerfResult) -> None:
    """euclidean_distance 속도"""
    from shared.dto.reid_dto import ReIDFeature

    v1 = np.random.randn(512).astype(np.float32)
    v2 = np.random.randn(512).astype(np.float32)
    f1 = ReIDFeature(feature=v1)
    f2 = ReIDFeature(feature=v2)

    def dist():
        f1.euclidean_distance(f2)

    elapsed = measure(dist, 100000)
    limit = 10.0
    if elapsed < limit:
        r.ok("euclidean_distance", elapsed, limit)
    else:
        r.fail("euclidean_distance", elapsed, limit)


# ==================== 4. Gallery 연산 ====================
def test_gallery_entry_add_feature(r: PerfResult) -> None:
    """GalleryEntry add_feature (EMA 업데이트)"""
    from shared.dto.reid_dto import GalleryEntry, ReIDFeature

    entry = GalleryEntry(person_id=1)
    vec = np.random.randn(512).astype(np.float32)
    vec /= np.linalg.norm(vec)

    # 초기 특징 하나 추가
    entry.add_feature(ReIDFeature(feature=vec.copy(), frame_index=0))

    def add():
        f = ReIDFeature(feature=vec.copy(), frame_index=entry.total_observations)
        entry.add_feature(f, max_size=100)

    elapsed = measure(add, 10000)
    limit = 30.0
    if elapsed < limit:
        r.ok("add_feature (EMA)", elapsed, limit)
    else:
        r.fail("add_feature (EMA)", elapsed, limit)


def test_gallery_query_speed(r: PerfResult) -> None:
    """ReIDGallery query (20명 갤러리 검색)"""
    from shared.dto.reid_dto import ReIDGallery, GalleryEntry, ReIDFeature

    gallery = ReIDGallery()
    for pid in range(20):
        entry = GalleryEntry(person_id=pid)
        vec = np.random.randn(512).astype(np.float32)
        vec /= np.linalg.norm(vec)
        entry.add_feature(ReIDFeature(feature=vec))
        gallery.add_entry(entry)

    query_vec = np.random.randn(512).astype(np.float32)
    query_vec /= np.linalg.norm(query_vec)
    query_feat = ReIDFeature(feature=query_vec)

    def query():
        gallery.query(query_feat, top_k=5, threshold=0.0)

    elapsed = measure(query, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("gallery.query (20명)", elapsed, limit)
    else:
        r.fail("gallery.query (20명)", elapsed, limit)


def test_gallery_find_best_match(r: PerfResult) -> None:
    """ReIDGallery find_best_match (20명)"""
    from shared.dto.reid_dto import ReIDGallery, GalleryEntry, ReIDFeature

    gallery = ReIDGallery()
    for pid in range(20):
        entry = GalleryEntry(person_id=pid)
        vec = np.random.randn(512).astype(np.float32)
        vec /= np.linalg.norm(vec)
        entry.add_feature(ReIDFeature(feature=vec))
        gallery.add_entry(entry)

    query_vec = np.random.randn(512).astype(np.float32)
    query_vec /= np.linalg.norm(query_vec)
    query_feat = ReIDFeature(feature=query_vec)

    def find():
        gallery.find_best_match(query_feat, threshold=0.0)

    elapsed = measure(find, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("find_best_match (20명)", elapsed, limit)
    else:
        r.fail("find_best_match (20명)", elapsed, limit)


# ==================== 5. 대량 배치 처리 ====================
def test_batch_feature_creation(r: PerfResult) -> None:
    """ReIDFeature 20개 배치 생성"""
    from shared.dto.reid_dto import ReIDFeature

    vecs = [np.random.randn(512).astype(np.float32) for _ in range(20)]

    def batch():
        for i in range(20):
            ReIDFeature(feature=vecs[i], confidence=0.8 + i * 0.01, frame_index=i * 30)

    elapsed = measure(batch, 5000)
    limit = 400.0
    if elapsed < limit:
        r.ok("ReIDFeature×20 배치", elapsed, limit)
    else:
        r.fail("ReIDFeature×20 배치", elapsed, limit)


def test_batch_gallery_updates(r: PerfResult) -> None:
    """GalleryEntry에 10개 특징 연속 추가"""
    from shared.dto.reid_dto import GalleryEntry, ReIDFeature

    vecs = [np.random.randn(512).astype(np.float32) for _ in range(10)]
    for v in vecs:
        v /= np.linalg.norm(v)

    def batch():
        entry = GalleryEntry(person_id=1)
        for i in range(10):
            entry.add_feature(
                ReIDFeature(feature=vecs[i].copy(), frame_index=i * 30)
            )

    elapsed = measure(batch, 2000)
    limit = 500.0
    if elapsed < limit:
        r.ok("gallery 10특징 연속 추가", elapsed, limit)
    else:
        r.fail("gallery 10특징 연속 추가", elapsed, limit)


def test_get_summary_speed(r: PerfResult) -> None:
    """ReIDMatch get_summary 속도"""
    from shared.dto.reid_dto import ReIDMatch, MatchStatus, SupportedLanguage

    m = ReIDMatch(
        status=MatchStatus.MATCHED,
        matched_person_id=5,
        similarity=0.92,
    )

    def summary():
        m.get_summary(SupportedLanguage.KO)

    elapsed = measure(summary, 50000)
    limit = 5.0
    if elapsed < limit:
        r.ok("get_summary(KO)", elapsed, limit)
    else:
        r.fail("get_summary(KO)", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("reid_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_reid_feature_creation(r)
    test_gallery_entry_creation(r)
    test_reid_match_creation(r)
    test_reid_result_creation(r)
    test_reid_gallery_creation(r)

    print("\n--- numpy 벡터 연산 ---")
    test_cosine_similarity_speed(r)
    test_cosine_similarity_unnormalized(r)
    test_normalize_speed(r)
    test_euclidean_distance_speed(r)

    print("\n--- Gallery 연산 ---")
    test_gallery_entry_add_feature(r)
    test_gallery_query_speed(r)
    test_gallery_find_best_match(r)

    print("\n--- 대량 배치 처리 ---")
    test_batch_feature_creation(r)
    test_batch_gallery_updates(r)
    test_get_summary_speed(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
