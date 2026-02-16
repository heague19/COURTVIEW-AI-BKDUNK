# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_reid_dto.py

Re-ID DTO 유닛 테스트
- 모듈 구조 / __all__ / __version__
- ReIDFeature: 생성, __post_init__, property, normalize, cosine_similarity, euclidean_distance
- GalleryEntry: 생성, property, add_feature, EMA, similarity_to, prune_old_features
- ReIDGallery: 생성, add/get/remove, update_feature, query, find_best_match, prune_all
- ReIDMatch: 생성, property, get_summary i18n
- ReIDResult: 생성, property, get_match_for_track
- Enum re-export: SupportedLanguage, ReIDModel, MatchStatus

Author: COURTVIEW AI Team
Version: 1.1.0
"""

import sys
from dataclasses import fields
from pathlib import Path

import numpy as np

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
            self.fail(name, f"expected {expected!r}, got {actual!r}")

    def true(self, name: str, value: bool) -> None:
        if value:
            self.ok(name)
        else:
            self.fail(name, "expected True")

    def false(self, name: str, value: bool) -> None:
        if not value:
            self.ok(name)
        else:
            self.fail(name, "expected False")

    def near(self, name: str, actual: float, expected: float, tol: float = 1e-5) -> None:
        if abs(actual - expected) <= tol:
            self.ok(name)
        else:
            self.fail(name, f"expected ~{expected}, got {actual} (tol={tol})")

    def is_none(self, name: str, value) -> None:
        if value is None:
            self.ok(name)
        else:
            self.fail(name, f"expected None, got {value!r}")

    def not_none(self, name: str, value) -> None:
        if value is not None:
            self.ok(name)
        else:
            self.fail(name, "expected not None, got None")

    def isinstance_check(self, name: str, obj, cls) -> None:
        if isinstance(obj, cls):
            self.ok(name)
        else:
            self.fail(name, f"expected {cls.__name__}, got {type(obj).__name__}")

    def ge(self, name: str, actual, minimum) -> None:
        if actual >= minimum:
            self.ok(name)
        else:
            self.fail(name, f"{actual} < {minimum}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. 모듈 구조 ====================
def test_module_structure(r: TestResult) -> None:
    """모듈 기본 구조 검증"""
    import shared.dto.reid_dto as m

    r.true("__all__ 존재", hasattr(m, "__all__"))
    r.true("__version__ 존재", hasattr(m, "__version__"))
    r.eq("__version__", m.__version__, "1.1.0")
    r.eq("__all__ 길이", len(m.__all__), 8)

    expected = [
        "SupportedLanguage", "ReIDModel", "MatchStatus",
        "ReIDFeature", "GalleryEntry", "ReIDGallery",
        "ReIDMatch", "ReIDResult",
    ]
    for name in expected:
        r.true(f"__all__에 {name} 포함", name in m.__all__)
        r.true(f"{name} getattr 가능", hasattr(m, name))


def test_no_legacy_typing(r: TestResult) -> None:
    """legacy typing 미사용 확인"""
    path = _PROJECT_ROOT / "shared" / "dto" / "reid_dto.py"
    content = path.read_text(encoding="utf-8")
    for legacy in ["Optional[", "List[", "Dict[", "Tuple["]:
        r.false(f"legacy typing '{legacy}' 미사용", legacy in content)


# ==================== 2. Enum re-export ====================
def test_enum_reexports(r: TestResult) -> None:
    """Enum re-export 검증"""
    from shared.dto.reid_dto import SupportedLanguage, ReIDModel, MatchStatus
    import enum

    # SupportedLanguage
    r.true("SupportedLanguage is Enum", issubclass(SupportedLanguage, enum.Enum))
    r.true("SupportedLanguage.KO 존재", hasattr(SupportedLanguage, "KO"))
    r.true("SupportedLanguage.EN 존재", hasattr(SupportedLanguage, "EN"))

    # ReIDModel
    r.true("ReIDModel is Enum", issubclass(ReIDModel, enum.Enum))
    r.true("ReIDModel.OSNET 존재", hasattr(ReIDModel, "OSNET"))
    r.true("ReIDModel.RESNET50 존재", hasattr(ReIDModel, "RESNET50"))
    r.true("ReIDModel.TRANSREID 존재", hasattr(ReIDModel, "TRANSREID"))
    r.ge("ReIDModel 멤버 수 >= 9", len(ReIDModel), 9)

    # MatchStatus
    r.true("MatchStatus is Enum", issubclass(MatchStatus, enum.Enum))
    for ms in ["MATCHED", "NEW", "AMBIGUOUS", "LOW_QUALITY", "FAILED"]:
        r.true(f"MatchStatus.{ms} 존재", hasattr(MatchStatus, ms))
    r.true("MatchStatus.MATCHED.is_successful", MatchStatus.MATCHED.is_successful)
    r.true("MatchStatus.NEW.is_successful", MatchStatus.NEW.is_successful)
    r.false("MatchStatus.FAILED.is_successful", MatchStatus.FAILED.is_successful)
    r.false("MatchStatus.AMBIGUOUS.is_successful", MatchStatus.AMBIGUOUS.is_successful)
    r.true("MatchStatus.MATCHED.to_korean()", len(MatchStatus.MATCHED.to_korean()) > 0)


# ==================== 3. ReIDFeature ====================
def test_reid_feature_creation(r: TestResult) -> None:
    """ReIDFeature 기본 생성"""
    from shared.dto.reid_dto import ReIDFeature

    vec = np.random.randn(512).astype(np.float32)
    feat = ReIDFeature(feature=vec, confidence=0.95, frame_index=100)

    r.eq("feature.dtype", feat.feature.dtype, np.float32)
    r.eq("dimension", feat.dimension, 512)
    r.near("confidence", feat.confidence, 0.95)
    r.eq("frame_index", feat.frame_index, 100)
    r.is_none("timestamp 기본값", feat.timestamp)
    r.is_none("camera_id 기본값", feat.camera_id)
    r.is_none("bbox 기본값", feat.bbox)
    r.near("quality_score 기본값", feat.quality_score, 1.0)
    r.eq("model_name 기본값", feat.model_name, "osnet")


def test_reid_feature_post_init(r: TestResult) -> None:
    """ReIDFeature __post_init__ 검증"""
    from shared.dto.reid_dto import ReIDFeature

    # list → numpy 변환
    feat1 = ReIDFeature(feature=[1.0, 2.0, 3.0])
    r.isinstance_check("list → ndarray 변환", feat1.feature, np.ndarray)
    r.eq("dtype float32", feat1.feature.dtype, np.float32)

    # float64 → float32 변환
    vec64 = np.array([1.0, 2.0], dtype=np.float64)
    feat2 = ReIDFeature(feature=vec64)
    r.eq("float64 → float32", feat2.feature.dtype, np.float32)

    # confidence clamp
    feat3 = ReIDFeature(feature=np.zeros(512, dtype=np.float32), confidence=1.5)
    r.near("confidence clamp max", feat3.confidence, 1.0)

    feat4 = ReIDFeature(feature=np.zeros(512, dtype=np.float32), confidence=-0.5)
    r.near("confidence clamp min", feat4.confidence, 0.0)

    # quality_score clamp
    feat5 = ReIDFeature(feature=np.zeros(512, dtype=np.float32), quality_score=2.0)
    r.near("quality_score clamp max", feat5.quality_score, 1.0)


def test_reid_feature_properties(r: TestResult) -> None:
    """ReIDFeature 프로퍼티 검증"""
    from shared.dto.reid_dto import ReIDFeature

    # normalized vector
    vec = np.random.randn(512).astype(np.float32)
    vec /= np.linalg.norm(vec)
    feat = ReIDFeature(feature=vec)

    r.eq("dimension", feat.dimension, 512)
    r.true("is_normalized (정규화된 벡터)", feat.is_normalized)
    r.near("norm ≈ 1.0", feat.norm, 1.0, tol=1e-4)

    # non-normalized
    vec2 = np.ones(256, dtype=np.float32) * 3.0
    feat2 = ReIDFeature(feature=vec2)
    r.eq("dimension 256", feat2.dimension, 256)
    r.false("is_normalized (비정규화)", feat2.is_normalized)


def test_reid_feature_normalize(r: TestResult) -> None:
    """ReIDFeature normalize() 메서드"""
    from shared.dto.reid_dto import ReIDFeature

    vec = np.array([3.0, 4.0, 0.0], dtype=np.float32)
    feat = ReIDFeature(feature=vec, confidence=0.8, frame_index=50)
    normalized = feat.normalize()

    r.true("normalize() 반환 is_normalized", normalized.is_normalized)
    r.near("normalize() norm ≈ 1.0", normalized.norm, 1.0, tol=1e-5)
    r.near("원래 confidence 보존", normalized.confidence, 0.8)
    r.eq("원래 frame_index 보존", normalized.frame_index, 50)

    # 영벡터 normalize
    zero_feat = ReIDFeature(feature=np.zeros(512, dtype=np.float32))
    zero_normalized = zero_feat.normalize()
    r.near("영벡터 normalize norm", zero_normalized.norm, 0.0, tol=1e-10)


def test_reid_feature_similarity(r: TestResult) -> None:
    """ReIDFeature 유사도/거리 메서드"""
    from shared.dto.reid_dto import ReIDFeature

    # 동일 벡터 → 유사도 1.0
    vec = np.random.randn(512).astype(np.float32)
    vec /= np.linalg.norm(vec)
    f1 = ReIDFeature(feature=vec.copy())
    f2 = ReIDFeature(feature=vec.copy())
    r.near("동일 벡터 cosine_similarity", f1.cosine_similarity(f2), 1.0, tol=1e-4)
    r.near("동일 벡터 euclidean_distance", f1.euclidean_distance(f2), 0.0, tol=1e-4)

    # 반대 벡터 → 유사도 -1.0
    f3 = ReIDFeature(feature=-vec.copy())
    r.near("반대 벡터 cosine_similarity", f1.cosine_similarity(f3), -1.0, tol=1e-4)

    # 직교 벡터 → 유사도 0.0
    v1 = np.zeros(512, dtype=np.float32)
    v2 = np.zeros(512, dtype=np.float32)
    v1[0] = 1.0
    v2[1] = 1.0
    f4 = ReIDFeature(feature=v1)
    f5 = ReIDFeature(feature=v2)
    r.near("직교 벡터 cosine_similarity", f4.cosine_similarity(f5), 0.0, tol=1e-5)

    # 비정규화 벡터에서도 cosine_similarity 동작
    va = np.array([3.0, 4.0], dtype=np.float32)
    vb = np.array([6.0, 8.0], dtype=np.float32)  # 같은 방향
    fa = ReIDFeature(feature=va)
    fb = ReIDFeature(feature=vb)
    r.near("비정규화 같은 방향 cosine", fa.cosine_similarity(fb), 1.0, tol=1e-4)

    # 영벡터 → 0.0
    zero = ReIDFeature(feature=np.zeros(512, dtype=np.float32))
    r.near("영벡터 cosine_similarity", f1.cosine_similarity(zero), 0.0, tol=1e-5)


# ==================== 4. GalleryEntry ====================
def test_gallery_entry_creation(r: TestResult) -> None:
    """GalleryEntry 기본 생성"""
    from shared.dto.reid_dto import GalleryEntry
    from uuid import UUID

    entry = GalleryEntry(person_id=23)

    r.isinstance_check("entry_id UUID", entry.entry_id, UUID)
    r.eq("person_id", entry.person_id, 23)
    r.eq("features 빈 리스트", entry.features, [])
    r.is_none("mean_feature 기본 None", entry.mean_feature)
    r.eq("total_observations 0", entry.total_observations, 0)
    r.is_none("team 기본 None", entry.team)
    r.is_none("jersey_number 기본 None", entry.jersey_number)
    r.eq("attributes 빈 dict", entry.attributes, {})


def test_gallery_entry_properties(r: TestResult) -> None:
    """GalleryEntry 프로퍼티"""
    from shared.dto.reid_dto import GalleryEntry, ReIDFeature

    entry = GalleryEntry(person_id=7)
    r.eq("num_features 초기 0", entry.num_features, 0)
    r.false("has_mean_feature 초기", entry.has_mean_feature)
    r.near("average_confidence 초기 0", entry.average_confidence, 0.0)
    r.near("average_quality 초기 0", entry.average_quality, 0.0)

    # 특징 수동 추가
    vec = np.random.randn(512).astype(np.float32)
    entry.features.append(ReIDFeature(feature=vec, confidence=0.8, quality_score=0.9))
    entry.features.append(ReIDFeature(feature=vec, confidence=0.6, quality_score=0.7))

    r.eq("num_features 2", entry.num_features, 2)
    r.near("average_confidence", entry.average_confidence, 0.7, tol=1e-5)
    r.near("average_quality", entry.average_quality, 0.8, tol=1e-5)


def test_gallery_entry_add_feature(r: TestResult) -> None:
    """GalleryEntry add_feature (EMA 포함)"""
    from shared.dto.reid_dto import GalleryEntry, ReIDFeature

    entry = GalleryEntry(person_id=10)

    # 첫 번째 특징 추가
    vec1 = np.random.randn(512).astype(np.float32)
    vec1 /= np.linalg.norm(vec1)
    f1 = ReIDFeature(feature=vec1, frame_index=0, confidence=0.9)
    entry.add_feature(f1)

    r.eq("total_observations 1", entry.total_observations, 1)
    r.eq("num_features 1", entry.num_features, 1)
    r.true("has_mean_feature True", entry.has_mean_feature)
    r.eq("last_update_frame 0", entry.last_update_frame, 0)

    # 두 번째 특징 추가 → EMA 업데이트
    vec2 = np.random.randn(512).astype(np.float32)
    vec2 /= np.linalg.norm(vec2)
    f2 = ReIDFeature(feature=vec2, frame_index=30, confidence=0.85)
    entry.add_feature(f2)

    r.eq("total_observations 2", entry.total_observations, 2)
    r.eq("num_features 2", entry.num_features, 2)
    r.eq("last_update_frame 30", entry.last_update_frame, 30)

    # mean_feature가 정규화되어 있는지
    mean_norm = float(np.linalg.norm(entry.mean_feature))
    r.near("mean_feature 정규화됨", mean_norm, 1.0, tol=1e-4)


def test_gallery_entry_max_size(r: TestResult) -> None:
    """GalleryEntry add_feature max_size 제한"""
    from shared.dto.reid_dto import GalleryEntry, ReIDFeature

    entry = GalleryEntry(person_id=5)

    # max_size=3으로 5개 추가
    for i in range(5):
        vec = np.random.randn(512).astype(np.float32)
        feat = ReIDFeature(
            feature=vec, frame_index=i * 10,
            confidence=0.5 + i * 0.1,
            quality_score=0.5 + i * 0.1,
        )
        entry.add_feature(feat, max_size=3)

    r.eq("max_size=3 제한", entry.num_features, 3)
    r.eq("total_observations 5", entry.total_observations, 5)


def test_gallery_entry_similarity_to(r: TestResult) -> None:
    """GalleryEntry similarity_to"""
    from shared.dto.reid_dto import GalleryEntry, ReIDFeature

    vec = np.random.randn(512).astype(np.float32)
    vec /= np.linalg.norm(vec)

    entry = GalleryEntry(person_id=1)
    feat = ReIDFeature(feature=vec.copy())
    entry.add_feature(feat)

    # 같은 벡터로 쿼리 → 높은 유사도
    query = ReIDFeature(feature=vec.copy())
    sim = entry.similarity_to(query)
    r.ge("동일 벡터 유사도 >= 0.99", sim, 0.99)

    # 빈 엔트리 → 0.0
    empty = GalleryEntry(person_id=99)
    r.near("빈 엔트리 유사도", empty.similarity_to(query), 0.0, tol=1e-5)


def test_gallery_entry_prune(r: TestResult) -> None:
    """GalleryEntry prune_old_features"""
    from shared.dto.reid_dto import GalleryEntry, ReIDFeature

    entry = GalleryEntry(person_id=3)
    for i in range(5):
        vec = np.random.randn(512).astype(np.float32)
        feat = ReIDFeature(feature=vec, frame_index=i * 100)
        entry.features.append(feat)

    # current_frame=350, max_age=200 → frame 0, 100 제거
    removed = entry.prune_old_features(current_frame=350, max_age=200)
    r.eq("제거된 수", removed, 2)
    r.eq("남은 특징", entry.num_features, 3)


# ==================== 5. ReIDGallery ====================
def test_reid_gallery_creation(r: TestResult) -> None:
    """ReIDGallery 기본 생성"""
    from shared.dto.reid_dto import ReIDGallery
    from uuid import UUID

    gallery = ReIDGallery()

    r.isinstance_check("gallery_id UUID", gallery.gallery_id, UUID)
    r.eq("entries 빈 dict", gallery.entries, {})
    r.eq("max_entries 50", gallery.max_entries, 50)
    r.eq("model_name osnet", gallery.model_name, "osnet")
    r.not_none("created_at 자동", gallery.created_at)
    r.is_none("last_update 기본 None", gallery.last_update)


def test_reid_gallery_properties(r: TestResult) -> None:
    """ReIDGallery 프로퍼티"""
    from shared.dto.reid_dto import ReIDGallery

    gallery = ReIDGallery()
    r.eq("num_entries 0", gallery.num_entries, 0)
    r.eq("total_features 0", gallery.total_features, 0)
    r.true("is_empty True", gallery.is_empty)


def test_reid_gallery_add_get_remove(r: TestResult) -> None:
    """ReIDGallery add/get/remove"""
    from shared.dto.reid_dto import ReIDGallery, GalleryEntry

    gallery = ReIDGallery(max_entries=3)

    e1 = GalleryEntry(person_id=1)
    e2 = GalleryEntry(person_id=2)
    e3 = GalleryEntry(person_id=3)
    e4 = GalleryEntry(person_id=4)

    r.true("add e1 성공", gallery.add_entry(e1))
    r.true("add e2 성공", gallery.add_entry(e2))
    r.true("add e3 성공", gallery.add_entry(e3))
    r.false("add e4 실패 (max)", gallery.add_entry(e4))
    r.eq("num_entries 3", gallery.num_entries, 3)
    r.false("is_empty False", gallery.is_empty)

    # get
    got = gallery.get_entry(2)
    r.not_none("get_entry(2)", got)
    r.eq("get_entry(2).person_id", got.person_id, 2)
    r.is_none("get_entry(99) None", gallery.get_entry(99))

    # remove
    r.true("remove(1) 성공", gallery.remove_entry(1))
    r.eq("num_entries 2", gallery.num_entries, 2)
    r.false("remove(99) 실패", gallery.remove_entry(99))
    r.is_none("get_entry(1) after remove", gallery.get_entry(1))


def test_reid_gallery_update_feature(r: TestResult) -> None:
    """ReIDGallery update_feature"""
    from shared.dto.reid_dto import ReIDGallery, GalleryEntry, ReIDFeature

    gallery = ReIDGallery()
    entry = GalleryEntry(person_id=10)
    gallery.add_entry(entry)

    vec = np.random.randn(512).astype(np.float32)
    feat = ReIDFeature(feature=vec, frame_index=100)

    r.true("update_feature 성공", gallery.update_feature(10, feat))
    r.false("update_feature 실패 (없는 ID)", gallery.update_feature(99, feat))

    updated = gallery.get_entry(10)
    r.eq("업데이트 후 특징 수", updated.num_features, 1)
    r.not_none("last_update 갱신됨", gallery.last_update)


def test_reid_gallery_query(r: TestResult) -> None:
    """ReIDGallery query / find_best_match"""
    from shared.dto.reid_dto import ReIDGallery, GalleryEntry, ReIDFeature

    gallery = ReIDGallery()

    # 3명의 엔트리 등록 (각각 고유 방향)
    vecs = []
    for i in range(3):
        vec = np.zeros(512, dtype=np.float32)
        vec[i * 10] = 1.0  # 거의 직교
        vecs.append(vec)
        entry = GalleryEntry(person_id=i)
        entry.add_feature(ReIDFeature(feature=vec.copy()))
        gallery.add_entry(entry)

    # person_id=0과 동일한 벡터로 쿼리
    query = ReIDFeature(feature=vecs[0].copy())
    results = gallery.query(query, top_k=3, threshold=0.0)

    r.ge("query 결과 >= 1", len(results), 1)
    r.eq("최상위 매칭 person_id=0", results[0][0], 0)
    r.near("최상위 유사도 1.0", results[0][1], 1.0, tol=1e-3)

    # find_best_match
    best = gallery.find_best_match(query, threshold=0.0)
    r.not_none("find_best_match 결과", best)
    r.eq("best match person_id", best[0], 0)

    # 임계값 높으면 None
    no_match = gallery.find_best_match(
        ReIDFeature(feature=np.random.randn(512).astype(np.float32)),
        threshold=0.99,
    )
    # 랜덤 벡터는 0.99 이상 거의 불가
    # (약간의 확률은 있지만 512차원에서 사실상 0)


def test_reid_gallery_prune_all(r: TestResult) -> None:
    """ReIDGallery prune_all"""
    from shared.dto.reid_dto import ReIDGallery, GalleryEntry, ReIDFeature

    gallery = ReIDGallery()

    for pid in range(3):
        entry = GalleryEntry(person_id=pid)
        for frame in [0, 100, 200, 300, 400]:
            vec = np.random.randn(512).astype(np.float32)
            entry.features.append(ReIDFeature(feature=vec, frame_index=frame))
        gallery.add_entry(entry)

    # prune current_frame=350, max_age=200 → frame 0, 100 제거 (각 엔트리 2개씩)
    pruned = gallery.prune_all(current_frame=350, max_feature_age=200)
    r.eq("prune_all 제거 수", pruned, 6)  # 3명 × 2개
    r.eq("남은 총 특징", gallery.total_features, 9)  # 3명 × 3개


# ==================== 6. ReIDMatch ====================
def test_reid_match_creation(r: TestResult) -> None:
    """ReIDMatch 기본 생성"""
    from shared.dto.reid_dto import ReIDMatch, MatchStatus

    m = ReIDMatch()
    r.is_none("query_feature 기본 None", m.query_feature)
    r.eq("status 기본 FAILED", m.status, MatchStatus.FAILED)
    r.is_none("matched_person_id 기본 None", m.matched_person_id)
    r.near("similarity 기본 0", m.similarity, 0.0)
    r.near("confidence 기본 0", m.confidence, 0.0)
    r.eq("candidates 빈 리스트", m.candidates, [])
    r.false("is_ambiguous 기본 False", m.is_ambiguous)
    r.near("processing_time_ms 기본 0", m.processing_time_ms, 0.0)


def test_reid_match_properties_matched(r: TestResult) -> None:
    """ReIDMatch 프로퍼티 - MATCHED 상태"""
    from shared.dto.reid_dto import ReIDMatch, MatchStatus

    m = ReIDMatch(
        status=MatchStatus.MATCHED,
        matched_person_id=5,
        similarity=0.92,
        confidence=0.88,
        candidates=[(5, 0.92), (3, 0.75), (7, 0.60)],
    )

    r.true("is_matched True", m.is_matched)
    r.false("is_new False", m.is_new)
    r.true("is_successful True", m.is_successful)
    r.eq("num_candidates 3", m.num_candidates, 3)

    # top_candidate / second_candidate
    r.eq("top_candidate", m.top_candidate, (5, 0.92))
    r.eq("second_candidate", m.second_candidate, (3, 0.75))

    # similarity_gap
    r.near("similarity_gap", m.similarity_gap, 0.17, tol=1e-5)


def test_reid_match_properties_new(r: TestResult) -> None:
    """ReIDMatch 프로퍼티 - NEW 상태"""
    from shared.dto.reid_dto import ReIDMatch, MatchStatus

    m = ReIDMatch(status=MatchStatus.NEW)
    r.false("is_matched False", m.is_matched)
    r.true("is_new True", m.is_new)
    r.true("is_successful True", m.is_successful)


def test_reid_match_properties_edge(r: TestResult) -> None:
    """ReIDMatch 프로퍼티 - 엣지 케이스"""
    from shared.dto.reid_dto import ReIDMatch, MatchStatus

    # 후보 0개
    m0 = ReIDMatch(status=MatchStatus.FAILED)
    r.is_none("top_candidate None (0 후보)", m0.top_candidate)
    r.is_none("second_candidate None (0 후보)", m0.second_candidate)
    r.near("similarity_gap 1.0 (0 후보)", m0.similarity_gap, 1.0)

    # 후보 1개
    m1 = ReIDMatch(
        status=MatchStatus.MATCHED,
        candidates=[(1, 0.85)],
    )
    r.eq("top_candidate (1 후보)", m1.top_candidate, (1, 0.85))
    r.is_none("second_candidate None (1 후보)", m1.second_candidate)
    r.near("similarity_gap 1.0 (1 후보)", m1.similarity_gap, 1.0)


def test_reid_match_summary_i18n(r: TestResult) -> None:
    """ReIDMatch get_summary 다국어"""
    from shared.dto.reid_dto import ReIDMatch, MatchStatus, SupportedLanguage

    # MATCHED → 한국어/영어
    matched = ReIDMatch(
        status=MatchStatus.MATCHED,
        matched_person_id=5,
        similarity=0.92,
    )
    ko = matched.get_summary(SupportedLanguage.KO)
    r.true("KO 매칭 결과에 'ID' 포함", "ID" in ko or "매칭" in ko)

    en = matched.get_summary(SupportedLanguage.EN)
    r.true("EN 매칭 결과에 'Matched' 포함", "Matched" in en)

    ja = matched.get_summary(SupportedLanguage.JA)
    r.true("JA 매칭 결과에 'マッチング' 포함", "マッチング" in ja)

    zh = matched.get_summary(SupportedLanguage.ZH)
    r.true("ZH 매칭 결과에 '匹配' 포함", "匹配" in zh)

    es = matched.get_summary(SupportedLanguage.ES)
    r.true("ES 매칭 결과에 'Coincidencia' 포함", "Coincidencia" in es)

    # NEW
    new_match = ReIDMatch(status=MatchStatus.NEW)
    ko_new = new_match.get_summary(SupportedLanguage.KO)
    r.true("KO NEW에 '새로운' 포함", "새로운" in ko_new)

    en_new = new_match.get_summary(SupportedLanguage.EN)
    r.true("EN NEW에 'New' 포함", "New" in en_new)

    # AMBIGUOUS
    ambig = ReIDMatch(
        status=MatchStatus.AMBIGUOUS,
        is_ambiguous=True,
        candidates=[(1, 0.8), (2, 0.78)],
    )
    ko_ambig = ambig.get_summary(SupportedLanguage.KO)
    r.true("KO AMBIGUOUS에 '모호' 포함", "모호" in ko_ambig)

    # to_korean_summary (하위 호환성)
    ko_compat = matched.to_korean_summary()
    r.eq("to_korean_summary == get_summary(KO)", ko_compat, ko)

    # FAILED → status 출력
    failed = ReIDMatch(status=MatchStatus.FAILED)
    ko_failed = failed.get_summary(SupportedLanguage.KO)
    r.true("KO FAILED에 '상태' 포함", "상태" in ko_failed or "실패" in ko_failed)


# ==================== 7. ReIDResult ====================
def test_reid_result_creation(r: TestResult) -> None:
    """ReIDResult 기본 생성"""
    from shared.dto.reid_dto import ReIDResult

    result = ReIDResult()
    r.eq("frame_index 기본 0", result.frame_index, 0)
    r.near("timestamp 기본 0", result.timestamp, 0.0)
    r.eq("matches 빈 리스트", result.matches, [])
    r.eq("new_persons 빈 리스트", result.new_persons, [])
    r.eq("gallery_updates 기본 0", result.gallery_updates, 0)
    r.near("processing_time_ms 기본 0", result.processing_time_ms, 0.0)


def test_reid_result_properties(r: TestResult) -> None:
    """ReIDResult 프로퍼티"""
    from shared.dto.reid_dto import ReIDResult, ReIDMatch, MatchStatus

    matches = [
        ReIDMatch(status=MatchStatus.MATCHED, matched_person_id=1),
        ReIDMatch(status=MatchStatus.NEW, matched_person_id=2),
        ReIDMatch(status=MatchStatus.AMBIGUOUS, is_ambiguous=True),
        ReIDMatch(status=MatchStatus.FAILED),
    ]
    result = ReIDResult(
        frame_index=100,
        timestamp=3.33,
        matches=matches,
        new_persons=[2],
        gallery_updates=3,
    )

    r.eq("num_matches 4", result.num_matches, 4)
    r.eq("num_successful 2", result.num_successful, 2)  # MATCHED + NEW
    r.eq("num_ambiguous 1", result.num_ambiguous, 1)
    r.near("success_rate 0.5", result.success_rate, 0.5, tol=1e-5)


def test_reid_result_get_match_for_track(r: TestResult) -> None:
    """ReIDResult get_match_for_track"""
    from shared.dto.reid_dto import ReIDResult, ReIDMatch, MatchStatus

    matches = [
        ReIDMatch(status=MatchStatus.MATCHED, matched_person_id=10),
        ReIDMatch(status=MatchStatus.MATCHED, matched_person_id=20),
    ]
    result = ReIDResult(matches=matches)

    found = result.get_match_for_track(10)
    r.not_none("get_match_for_track(10)", found)
    r.eq("found.matched_person_id", found.matched_person_id, 10)

    found2 = result.get_match_for_track(20)
    r.not_none("get_match_for_track(20)", found2)

    r.is_none("get_match_for_track(99) None", result.get_match_for_track(99))

    # 빈 result
    empty = ReIDResult()
    r.is_none("빈 result get_match", empty.get_match_for_track(1))
    r.near("빈 result success_rate", empty.success_rate, 0.0)


# ==================== 8. dataclass 필드 검증 ====================
def test_dataclass_fields(r: TestResult) -> None:
    """각 dataclass의 필드 수 확인"""
    from shared.dto.reid_dto import (
        ReIDFeature, GalleryEntry, ReIDGallery, ReIDMatch, ReIDResult,
    )

    r.eq("ReIDFeature 필드 수", len(fields(ReIDFeature)), 8)
    r.eq("GalleryEntry 필드 수", len(fields(GalleryEntry)), 10)
    r.eq("ReIDGallery 필드 수", len(fields(ReIDGallery)), 7)
    r.eq("ReIDMatch 필드 수", len(fields(ReIDMatch)), 8)
    r.eq("ReIDResult 필드 수", len(fields(ReIDResult)), 6)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("reid_dto.py v1.1.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)
    test_no_legacy_typing(r)

    print("\n--- Enum re-export ---")
    test_enum_reexports(r)

    print("\n--- ReIDFeature ---")
    test_reid_feature_creation(r)
    test_reid_feature_post_init(r)
    test_reid_feature_properties(r)
    test_reid_feature_normalize(r)
    test_reid_feature_similarity(r)

    print("\n--- GalleryEntry ---")
    test_gallery_entry_creation(r)
    test_gallery_entry_properties(r)
    test_gallery_entry_add_feature(r)
    test_gallery_entry_max_size(r)
    test_gallery_entry_similarity_to(r)
    test_gallery_entry_prune(r)

    print("\n--- ReIDGallery ---")
    test_reid_gallery_creation(r)
    test_reid_gallery_properties(r)
    test_reid_gallery_add_get_remove(r)
    test_reid_gallery_update_feature(r)
    test_reid_gallery_query(r)
    test_reid_gallery_prune_all(r)

    print("\n--- ReIDMatch ---")
    test_reid_match_creation(r)
    test_reid_match_properties_matched(r)
    test_reid_match_properties_new(r)
    test_reid_match_properties_edge(r)
    test_reid_match_summary_i18n(r)

    print("\n--- ReIDResult ---")
    test_reid_result_creation(r)
    test_reid_result_properties(r)
    test_reid_result_get_match_for_track(r)

    print("\n--- dataclass 필드 ---")
    test_dataclass_fields(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
