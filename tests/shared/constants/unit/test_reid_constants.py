# -*- coding: utf-8 -*-
"""reid_constants.py v1.1.0 단위 테스트"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.section = ""

    def set_section(self, name):
        self.section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name, msg=""):
        self.failed += 1
        print(f"  [FAIL] {name} - {msg}")

    def check(self, name, condition, msg=""):
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        print(f"{'='*60}")
        return self.failed == 0


result = TestResult()

# =============================================================================
# 임포트
# =============================================================================
from shared.constants.reid_constants import (
    ReIDModel, MatchStatus,
    FEATURE_DIM, FEATURE_DIM_HIGH, FEATURE_DIM_LOW,
    NORMALIZE_FEATURES, FEATURE_NORMALIZE_EPS,
    SIMILARITY_THRESHOLD, HIGH_SIMILARITY_THRESHOLD,
    LOW_SIMILARITY_THRESHOLD, IDENTITY_CONFIRMED_SIMILARITY,
    EUCLIDEAN_DISTANCE_THRESHOLD, MAHALANOBIS_DISTANCE_THRESHOLD,
    GALLERY_MAX_SIZE, GALLERY_MIN_SIZE, GALLERY_UPDATE_INTERVAL,
    GALLERY_FEATURE_MAX_AGE, GALLERY_PRUNING_RATIO,
    GLOBAL_GALLERY_MAX_PERSONS,
    EMA_MOMENTUM, EMA_MOMENTUM_FAST, EMA_MOMENTUM_STABLE, EMA_MOMENTUM_INITIAL,
    EMA_MIN_SAMPLES,
    MAX_MATCH_CANDIDATES, TOPK_MATCHES, MIN_MATCH_CONFIDENCE,
    AMBIGUOUS_MATCH_DIFF, RERANKING_THRESHOLD,
    RERANKING_K1, RERANKING_K2, RERANKING_LAMBDA,
    CROSS_VIEW_MIN_CONFIDENCE, CROSS_VIEW_CONSISTENCY_THRESHOLD,
    CROSS_VIEW_FUSION_WEIGHT_QUALITY, CROSS_VIEW_FUSION_WEIGHT_DISTANCE,
    TEMPORAL_WINDOW_SIZE, TEMPORAL_CONSISTENCY_MIN_RATIO,
    TEMPORAL_SMOOTHING_WEIGHT, LONG_TERM_FEATURE_INTERVAL,
    REID_INPUT_SIZE, REID_INPUT_SIZE_HIGH, MIN_BBOX_SIZE,
    BBOX_EXPANSION_RATIO, FEATURE_EXTRACTION_BATCH_SIZE,
    UNIFORM_COLOR_WEIGHT, BODY_SHAPE_WEIGHT, DEEP_FEATURE_WEIGHT,
    COLOR_HISTOGRAM_BINS, COLOR_SIMILARITY_THRESHOLD,
    _REID_MODEL_FEATURE_DIM_MAP, _REID_MODEL_INPUT_SIZE_MAP,
    _REID_MODEL_IS_LIGHTWEIGHT, _REID_MODEL_KOREAN_MAP,
    _MATCH_STATUS_IS_SUCCESSFUL, _MATCH_STATUS_NEEDS_CONFIRMATION,
    _MATCH_STATUS_SHOULD_RETRY, _MATCH_STATUS_KOREAN_MAP,
)
import shared.constants.reid_constants as rc

# =============================================================================
# 1. ReIDModel 멤버 수 및 값
# =============================================================================
result.set_section("1. ReIDModel 멤버 수 및 값")
result.check("ReIDModel 멤버 수 = 9", len(ReIDModel) == 9, f"실제: {len(ReIDModel)}")

_expected_models = [
    ("OSNET", "osnet"), ("OSNET_AIN", "osnet_ain"),
    ("RESNET50", "resnet50"), ("RESNET50_IBN", "resnet50_ibn"),
    ("MGN", "mgn"), ("PCB", "pcb"), ("AGW", "agw"),
    ("TRANSREID", "transreid"), ("CUSTOM", "custom"),
]
for name, value in _expected_models:
    m = ReIDModel[name]
    result.check(f"ReIDModel.{name} = '{value}'", m.value == value, f"실제: {m.value}")

# 유일성
vals = [m.value for m in ReIDModel]
result.check("ReIDModel 값 유일성", len(vals) == len(set(vals)))

# Enum 타입
for m in ReIDModel:
    result.check(f"ReIDModel.{m.name} isinstance Enum", isinstance(m, ReIDModel))

# =============================================================================
# 2. ReIDModel.feature_dim
# =============================================================================
result.set_section("2. ReIDModel.feature_dim")

_expected_dims = {
    "OSNET": 512, "OSNET_AIN": 512, "RESNET50": 2048, "RESNET50_IBN": 2048,
    "MGN": 2048, "PCB": 1536, "AGW": 2048, "TRANSREID": 768, "CUSTOM": FEATURE_DIM,
}
for name, dim in _expected_dims.items():
    m = ReIDModel[name]
    result.check(f"ReIDModel.{name}.feature_dim = {dim}", m.feature_dim == dim, f"실제: {m.feature_dim}")
    result.check(f"ReIDModel.{name}.feature_dim int 타입", isinstance(m.feature_dim, int))
    result.check(f"ReIDModel.{name}.feature_dim > 0", m.feature_dim > 0)

# CUSTOM은 FEATURE_DIM 상수와 동일
result.check("CUSTOM.feature_dim == FEATURE_DIM 일관성", ReIDModel.CUSTOM.feature_dim == FEATURE_DIM)

# =============================================================================
# 3. ReIDModel.input_size
# =============================================================================
result.set_section("3. ReIDModel.input_size")

_expected_sizes = {
    "OSNET": (256, 128), "OSNET_AIN": (256, 128),
    "RESNET50": (256, 128), "RESNET50_IBN": (256, 128),
    "MGN": (384, 128), "PCB": (384, 128),
    "AGW": (256, 128), "TRANSREID": (256, 128),
    "CUSTOM": REID_INPUT_SIZE,
}
for name, size in _expected_sizes.items():
    m = ReIDModel[name]
    result.check(f"ReIDModel.{name}.input_size = {size}", m.input_size == size, f"실제: {m.input_size}")
    result.check(f"ReIDModel.{name}.input_size tuple", isinstance(m.input_size, tuple))
    result.check(f"ReIDModel.{name}.input_size len=2", len(m.input_size) == 2)
    # Re-ID: 사람 크롭은 height > width (서 있는 형태)
    result.check(f"ReIDModel.{name} height >= width", m.input_size[0] >= m.input_size[1])

# CUSTOM은 REID_INPUT_SIZE와 동일
result.check("CUSTOM.input_size == REID_INPUT_SIZE", ReIDModel.CUSTOM.input_size == REID_INPUT_SIZE)

# =============================================================================
# 4. ReIDModel.is_lightweight
# =============================================================================
result.set_section("4. ReIDModel.is_lightweight")

_expected_lightweight = {"OSNET": True, "OSNET_AIN": True}
for m in ReIDModel:
    expected = _expected_lightweight.get(m.name, False)
    result.check(f"ReIDModel.{m.name}.is_lightweight = {expected}", m.is_lightweight is expected)

# 경량 모델은 feature_dim이 더 작아야 함
for m in ReIDModel:
    if m.is_lightweight:
        result.check(f"{m.name} 경량: feature_dim <= 512", m.feature_dim <= 512)

# =============================================================================
# 5. ReIDModel.to_korean() (METHOD)
# =============================================================================
result.set_section("5. ReIDModel.to_korean() (METHOD)")

_expected_korean = {
    "OSNET": "OSNet", "OSNET_AIN": "OSNet-AIN",
    "RESNET50": "ResNet50", "RESNET50_IBN": "ResNet50-IBN",
    "MGN": "MGN", "PCB": "PCB", "AGW": "AGW",
    "TRANSREID": "TransReID", "CUSTOM": "커스텀",
}
for name, korean in _expected_korean.items():
    m = ReIDModel[name]
    result.check(f"ReIDModel.{name}.to_korean() = '{korean}'", m.to_korean() == korean, f"실제: {m.to_korean()}")

# 모두 str, 비어있지 않음
for m in ReIDModel:
    result.check(f"ReIDModel.{m.name}.to_korean() str", isinstance(m.to_korean(), str))
    result.check(f"ReIDModel.{m.name}.to_korean() 비어있지 않음", len(m.to_korean()) > 0)

# to_korean은 메서드 (호출 가능)
result.check("to_korean 호출 가능", callable(ReIDModel.OSNET.to_korean))

# =============================================================================
# 6. MatchStatus 멤버 수 및 값
# =============================================================================
result.set_section("6. MatchStatus 멤버 수 및 값")
result.check("MatchStatus 멤버 수 = 5", len(MatchStatus) == 5, f"실제: {len(MatchStatus)}")

_expected_statuses = [
    ("MATCHED", "matched"), ("NEW", "new"), ("AMBIGUOUS", "ambiguous"),
    ("LOW_QUALITY", "low_quality"), ("FAILED", "failed"),
]
for name, value in _expected_statuses:
    s = MatchStatus[name]
    result.check(f"MatchStatus.{name} = '{value}'", s.value == value)

# =============================================================================
# 7. MatchStatus.is_successful
# =============================================================================
result.set_section("7. MatchStatus.is_successful")
_successful = {"MATCHED": True, "NEW": True, "AMBIGUOUS": False, "LOW_QUALITY": False, "FAILED": False}
for name, expected in _successful.items():
    s = MatchStatus[name]
    result.check(f"MatchStatus.{name}.is_successful = {expected}", s.is_successful is expected)

# =============================================================================
# 8. MatchStatus.needs_confirmation
# =============================================================================
result.set_section("8. MatchStatus.needs_confirmation")
_confirmation = {"MATCHED": False, "NEW": False, "AMBIGUOUS": True, "LOW_QUALITY": True, "FAILED": False}
for name, expected in _confirmation.items():
    s = MatchStatus[name]
    result.check(f"MatchStatus.{name}.needs_confirmation = {expected}", s.needs_confirmation is expected)

# =============================================================================
# 9. MatchStatus.should_retry
# =============================================================================
result.set_section("9. MatchStatus.should_retry")
_retry = {"MATCHED": False, "NEW": False, "AMBIGUOUS": False, "LOW_QUALITY": True, "FAILED": True}
for name, expected in _retry.items():
    s = MatchStatus[name]
    result.check(f"MatchStatus.{name}.should_retry = {expected}", s.should_retry is expected)

# =============================================================================
# 10. MatchStatus 플래그 상호 배제 및 교차
# =============================================================================
result.set_section("10. MatchStatus 플래그 상호 배제 및 교차")

# is_successful과 should_retry는 동시에 True가 아님
for s in MatchStatus:
    result.check(
        f"{s.name}: is_successful과 should_retry 동시 True 없음",
        not (s.is_successful and s.should_retry),
    )

# is_successful과 needs_confirmation도 동시에 True가 아님
for s in MatchStatus:
    result.check(
        f"{s.name}: is_successful과 needs_confirmation 동시 True 없음",
        not (s.is_successful and s.needs_confirmation),
    )

# LOW_QUALITY는 needs_confirmation과 should_retry 모두 True (교차)
result.check(
    "LOW_QUALITY: needs_confirmation AND should_retry",
    MatchStatus.LOW_QUALITY.needs_confirmation and MatchStatus.LOW_QUALITY.should_retry,
)

# 각 MatchStatus는 3가지 플래그 중 하나 이상 True
for s in MatchStatus:
    has_flag = s.is_successful or s.needs_confirmation or s.should_retry
    result.check(f"{s.name}: 최소 1개 플래그 True", has_flag)

# =============================================================================
# 11. MatchStatus.to_korean() (METHOD)
# =============================================================================
result.set_section("11. MatchStatus.to_korean() (METHOD)")
_status_korean = {
    "MATCHED": "매칭됨", "NEW": "새로운 인물", "AMBIGUOUS": "모호함",
    "LOW_QUALITY": "낮은 품질", "FAILED": "실패",
}
for name, korean in _status_korean.items():
    s = MatchStatus[name]
    result.check(f"MatchStatus.{name}.to_korean() = '{korean}'", s.to_korean() == korean)

for s in MatchStatus:
    result.check(f"MatchStatus.{s.name}.to_korean() str", isinstance(s.to_korean(), str))
    result.check(f"MatchStatus.{s.name}.to_korean() 비어있지 않음", len(s.to_korean()) > 0)

# =============================================================================
# 12. 특징 벡터 상수
# =============================================================================
result.set_section("12. 특징 벡터 상수")
result.check("FEATURE_DIM = 512", FEATURE_DIM == 512)
result.check("FEATURE_DIM_HIGH = 1024", FEATURE_DIM_HIGH == 1024)
result.check("FEATURE_DIM_LOW = 256", FEATURE_DIM_LOW == 256)
result.check("DIM 순서: LOW < DIM < HIGH", FEATURE_DIM_LOW < FEATURE_DIM < FEATURE_DIM_HIGH)
result.check("NORMALIZE_FEATURES = True", NORMALIZE_FEATURES is True)
result.check("FEATURE_NORMALIZE_EPS = 1e-12", abs(FEATURE_NORMALIZE_EPS - 1e-12) < 1e-20)
result.check("FEATURE_NORMALIZE_EPS > 0", FEATURE_NORMALIZE_EPS > 0)

# 2의 거듭제곱
for name, val in [("LOW", FEATURE_DIM_LOW), ("DIM", FEATURE_DIM), ("HIGH", FEATURE_DIM_HIGH)]:
    result.check(f"FEATURE_DIM_{name} 2의 거듭제곱", val > 0 and (val & (val - 1)) == 0)

# =============================================================================
# 13. 유사도 임계값 순서
# =============================================================================
result.set_section("13. 유사도 임계값 순서")
result.check("LOW_SIMILARITY = 0.5", abs(LOW_SIMILARITY_THRESHOLD - 0.5) < 1e-9)
result.check("SIMILARITY = 0.7", abs(SIMILARITY_THRESHOLD - 0.7) < 1e-9)
result.check("HIGH_SIMILARITY = 0.85", abs(HIGH_SIMILARITY_THRESHOLD - 0.85) < 1e-9)
result.check("IDENTITY_CONFIRMED = 0.9", abs(IDENTITY_CONFIRMED_SIMILARITY - 0.9) < 1e-9)
result.check(
    "순서: LOW < SIMILARITY < HIGH < IDENTITY",
    LOW_SIMILARITY_THRESHOLD < SIMILARITY_THRESHOLD < HIGH_SIMILARITY_THRESHOLD < IDENTITY_CONFIRMED_SIMILARITY,
)
# 모두 0~1 범위
for name, val in [
    ("LOW", LOW_SIMILARITY_THRESHOLD), ("SIMILARITY", SIMILARITY_THRESHOLD),
    ("HIGH", HIGH_SIMILARITY_THRESHOLD), ("IDENTITY", IDENTITY_CONFIRMED_SIMILARITY),
]:
    result.check(f"{name}_THRESHOLD 0~1 범위", 0.0 <= val <= 1.0)

# 거리 임계값
result.check("EUCLIDEAN_DISTANCE = 1.0", abs(EUCLIDEAN_DISTANCE_THRESHOLD - 1.0) < 1e-9)
result.check("MAHALANOBIS_DISTANCE = 50.0", abs(MAHALANOBIS_DISTANCE_THRESHOLD - 50.0) < 1e-9)
result.check("거리 임계값 양수", EUCLIDEAN_DISTANCE_THRESHOLD > 0 and MAHALANOBIS_DISTANCE_THRESHOLD > 0)

# =============================================================================
# 14. 갤러리 관리 상수
# =============================================================================
result.set_section("14. 갤러리 관리 상수")
result.check("GALLERY_MAX_SIZE = 100", GALLERY_MAX_SIZE == 100)
result.check("GALLERY_MIN_SIZE = 5", GALLERY_MIN_SIZE == 5)
result.check("GALLERY_MIN < GALLERY_MAX", GALLERY_MIN_SIZE < GALLERY_MAX_SIZE)
result.check("GALLERY_UPDATE_INTERVAL = 5", GALLERY_UPDATE_INTERVAL == 5)
result.check("GALLERY_FEATURE_MAX_AGE = 300", GALLERY_FEATURE_MAX_AGE == 300)
result.check("GALLERY_PRUNING_RATIO = 0.2", abs(GALLERY_PRUNING_RATIO - 0.2) < 1e-9)
result.check("GALLERY_PRUNING_RATIO 0~1", 0.0 < GALLERY_PRUNING_RATIO < 1.0)
result.check("GLOBAL_GALLERY_MAX_PERSONS = 50", GLOBAL_GALLERY_MAX_PERSONS == 50)
result.check("모든 갤러리 상수 양수", all(v > 0 for v in [
    GALLERY_MAX_SIZE, GALLERY_MIN_SIZE, GALLERY_UPDATE_INTERVAL,
    GALLERY_FEATURE_MAX_AGE, GLOBAL_GALLERY_MAX_PERSONS,
]))

# =============================================================================
# 15. EMA 상수
# =============================================================================
result.set_section("15. EMA 상수")
result.check("EMA_MOMENTUM = 0.9", abs(EMA_MOMENTUM - 0.9) < 1e-9)
result.check("EMA_MOMENTUM_FAST = 0.7", abs(EMA_MOMENTUM_FAST - 0.7) < 1e-9)
result.check("EMA_MOMENTUM_STABLE = 0.95", abs(EMA_MOMENTUM_STABLE - 0.95) < 1e-9)
result.check("EMA_MOMENTUM_INITIAL = 0.5", abs(EMA_MOMENTUM_INITIAL - 0.5) < 1e-9)
result.check("EMA_MIN_SAMPLES = 3", EMA_MIN_SAMPLES == 3)
result.check(
    "EMA 순서: INITIAL < FAST < default < STABLE",
    EMA_MOMENTUM_INITIAL < EMA_MOMENTUM_FAST < EMA_MOMENTUM < EMA_MOMENTUM_STABLE,
)
# 모두 0~1 범위
for name, val in [
    ("MOMENTUM", EMA_MOMENTUM), ("FAST", EMA_MOMENTUM_FAST),
    ("STABLE", EMA_MOMENTUM_STABLE), ("INITIAL", EMA_MOMENTUM_INITIAL),
]:
    result.check(f"EMA_{name} 0~1 범위", 0.0 < val < 1.0)

# =============================================================================
# 16. 매칭 파라미터
# =============================================================================
result.set_section("16. 매칭 파라미터")
result.check("MAX_MATCH_CANDIDATES = 10", MAX_MATCH_CANDIDATES == 10)
result.check("TOPK_MATCHES = 5", TOPK_MATCHES == 5)
result.check("TOPK < MAX_CANDIDATES", TOPK_MATCHES < MAX_MATCH_CANDIDATES)
result.check("MIN_MATCH_CONFIDENCE = 0.5", abs(MIN_MATCH_CONFIDENCE - 0.5) < 1e-9)
result.check("AMBIGUOUS_MATCH_DIFF = 0.1", abs(AMBIGUOUS_MATCH_DIFF - 0.1) < 1e-9)
result.check("RERANKING_THRESHOLD = 0.6", abs(RERANKING_THRESHOLD - 0.6) < 1e-9)
result.check("RERANKING_K1 = 20", RERANKING_K1 == 20)
result.check("RERANKING_K2 = 6", RERANKING_K2 == 6)
result.check("RERANKING_K2 < RERANKING_K1", RERANKING_K2 < RERANKING_K1)
result.check("RERANKING_LAMBDA = 0.3", abs(RERANKING_LAMBDA - 0.3) < 1e-9)
result.check("RERANKING_LAMBDA 0~1", 0.0 < RERANKING_LAMBDA < 1.0)

# =============================================================================
# 17. 크로스뷰 가중치 합 = 1.0
# =============================================================================
result.set_section("17. 크로스뷰 파라미터")
result.check("CROSS_VIEW_MIN_CONFIDENCE = 0.6", abs(CROSS_VIEW_MIN_CONFIDENCE - 0.6) < 1e-9)
result.check("CROSS_VIEW_CONSISTENCY_THRESHOLD = 0.7", abs(CROSS_VIEW_CONSISTENCY_THRESHOLD - 0.7) < 1e-9)
result.check("FUSION_WEIGHT_QUALITY = 0.6", abs(CROSS_VIEW_FUSION_WEIGHT_QUALITY - 0.6) < 1e-9)
result.check("FUSION_WEIGHT_DISTANCE = 0.4", abs(CROSS_VIEW_FUSION_WEIGHT_DISTANCE - 0.4) < 1e-9)
cv_sum = CROSS_VIEW_FUSION_WEIGHT_QUALITY + CROSS_VIEW_FUSION_WEIGHT_DISTANCE
result.check("크로스뷰 융합 가중치 합 = 1.0", abs(cv_sum - 1.0) < 1e-9, f"합: {cv_sum}")
result.check("QUALITY > DISTANCE (품질 우선)", CROSS_VIEW_FUSION_WEIGHT_QUALITY > CROSS_VIEW_FUSION_WEIGHT_DISTANCE)

# =============================================================================
# 18. Re-ID 특징 가중치 합 = 1.0
# =============================================================================
result.set_section("18. Re-ID 특징 가중치")
result.check("UNIFORM_COLOR_WEIGHT = 0.3", abs(UNIFORM_COLOR_WEIGHT - 0.3) < 1e-9)
result.check("BODY_SHAPE_WEIGHT = 0.2", abs(BODY_SHAPE_WEIGHT - 0.2) < 1e-9)
result.check("DEEP_FEATURE_WEIGHT = 0.5", abs(DEEP_FEATURE_WEIGHT - 0.5) < 1e-9)
reid_sum = UNIFORM_COLOR_WEIGHT + BODY_SHAPE_WEIGHT + DEEP_FEATURE_WEIGHT
result.check("특징 가중치 합 = 1.0", abs(reid_sum - 1.0) < 1e-9, f"합: {reid_sum}")
result.check("DEEP > UNIFORM > BODY 순서", DEEP_FEATURE_WEIGHT > UNIFORM_COLOR_WEIGHT > BODY_SHAPE_WEIGHT)
result.check("COLOR_HISTOGRAM_BINS = 32", COLOR_HISTOGRAM_BINS == 32)
result.check("COLOR_SIMILARITY_THRESHOLD = 0.7", abs(COLOR_SIMILARITY_THRESHOLD - 0.7) < 1e-9)
# 모든 가중치 양수
for name, val in [("UNIFORM", UNIFORM_COLOR_WEIGHT), ("BODY", BODY_SHAPE_WEIGHT), ("DEEP", DEEP_FEATURE_WEIGHT)]:
    result.check(f"{name}_WEIGHT > 0", val > 0)

# =============================================================================
# 19. 시간적 일관성 파라미터
# =============================================================================
result.set_section("19. 시간적 일관성 파라미터")
result.check("TEMPORAL_WINDOW_SIZE = 15", TEMPORAL_WINDOW_SIZE == 15)
result.check("TEMPORAL_CONSISTENCY_MIN_RATIO = 0.6", abs(TEMPORAL_CONSISTENCY_MIN_RATIO - 0.6) < 1e-9)
result.check("TEMPORAL_SMOOTHING_WEIGHT = 0.3", abs(TEMPORAL_SMOOTHING_WEIGHT - 0.3) < 1e-9)
result.check("LONG_TERM_FEATURE_INTERVAL = 30", LONG_TERM_FEATURE_INTERVAL == 30)
result.check("SMOOTHING_WEIGHT 0~1", 0.0 < TEMPORAL_SMOOTHING_WEIGHT < 1.0)
result.check("CONSISTENCY_MIN_RATIO 0~1", 0.0 < TEMPORAL_CONSISTENCY_MIN_RATIO < 1.0)

# =============================================================================
# 20. 입력 크기 상수
# =============================================================================
result.set_section("20. 입력 크기 상수")
result.check("REID_INPUT_SIZE = (256, 128)", REID_INPUT_SIZE == (256, 128))
result.check("REID_INPUT_SIZE_HIGH = (384, 192)", REID_INPUT_SIZE_HIGH == (384, 192))
result.check("MIN_BBOX_SIZE = (32, 64)", MIN_BBOX_SIZE == (32, 64))
result.check("BBOX_EXPANSION_RATIO = 1.1", abs(BBOX_EXPANSION_RATIO - 1.1) < 1e-9)
result.check("FEATURE_EXTRACTION_BATCH_SIZE = 32", FEATURE_EXTRACTION_BATCH_SIZE == 32)

# height > width (서있는 사람 크롭)
for name, val in [("REID_INPUT_SIZE", REID_INPUT_SIZE), ("REID_INPUT_SIZE_HIGH", REID_INPUT_SIZE_HIGH)]:
    result.check(f"{name} height > width", val[0] > val[1])

# MIN < standard < HIGH
result.check("MIN < standard size", MIN_BBOX_SIZE[0] < REID_INPUT_SIZE[0])
result.check("standard < HIGH size", REID_INPUT_SIZE[0] < REID_INPUT_SIZE_HIGH[0])

# BBOX_EXPANSION > 1.0 (확장)
result.check("BBOX_EXPANSION > 1.0", BBOX_EXPANSION_RATIO > 1.0)

# =============================================================================
# 21. __all__ 완전성
# =============================================================================
result.set_section("21. __all__ 완전성")
all_list = rc.__all__
result.check(f"__all__ 개수 = 50", len(all_list) == 50, f"실제: {len(all_list)}")
result.check("__all__ 중복 없음", len(all_list) == len(set(all_list)))

for name in all_list:
    result.check(f"__all__: '{name}' 모듈에 존재", hasattr(rc, name))

# =============================================================================
# 22. 캐시 타입 및 완전성
# =============================================================================
result.set_section("22. 캐시 타입 및 완전성")

# frozenset 캐시
result.check("_REID_MODEL_IS_LIGHTWEIGHT frozenset", isinstance(_REID_MODEL_IS_LIGHTWEIGHT, frozenset))
result.check("_MATCH_STATUS_IS_SUCCESSFUL frozenset", isinstance(_MATCH_STATUS_IS_SUCCESSFUL, frozenset))
result.check("_MATCH_STATUS_NEEDS_CONFIRMATION frozenset", isinstance(_MATCH_STATUS_NEEDS_CONFIRMATION, frozenset))
result.check("_MATCH_STATUS_SHOULD_RETRY frozenset", isinstance(_MATCH_STATUS_SHOULD_RETRY, frozenset))

# dict 캐시 완전성
result.check("_REID_MODEL_FEATURE_DIM_MAP 완전", len(_REID_MODEL_FEATURE_DIM_MAP) == len(ReIDModel))
result.check("_REID_MODEL_INPUT_SIZE_MAP 완전", len(_REID_MODEL_INPUT_SIZE_MAP) == len(ReIDModel))
result.check("_REID_MODEL_KOREAN_MAP 완전", len(_REID_MODEL_KOREAN_MAP) == len(ReIDModel))
result.check("_MATCH_STATUS_KOREAN_MAP 완전", len(_MATCH_STATUS_KOREAN_MAP) == len(MatchStatus))

# 모든 Enum 멤버가 dict 캐시에 존재
for m in ReIDModel:
    result.check(f"ReIDModel.{m.name} in feature_dim_map", m in _REID_MODEL_FEATURE_DIM_MAP)
    result.check(f"ReIDModel.{m.name} in input_size_map", m in _REID_MODEL_INPUT_SIZE_MAP)
    result.check(f"ReIDModel.{m.name} in korean_map", m in _REID_MODEL_KOREAN_MAP)

for s in MatchStatus:
    result.check(f"MatchStatus.{s.name} in korean_map", s in _MATCH_STATUS_KOREAN_MAP)

# =============================================================================
# 23. 메타 검증
# =============================================================================
result.set_section("23. 메타 검증")
result.check("버전 1.1.0", rc.__version__ == "1.1.0", f"실제: {rc.__version__}")

# typing 모더나이제이션 검증
import inspect
source = inspect.getsource(rc)
result.check("Dict[ 미사용", "Dict[" not in source)
result.check("Tuple[ 미사용", "Tuple[" not in source)
result.check("FrozenSet[ 미사용", "FrozenSet[" not in source)
result.check("빈 선언 패턴 없음", "= {}" not in source and "= frozenset()" not in source)

# assert 존재 (가중치 합 검증)
result.check("assert 문 존재 (가중치 합)", source.count("assert abs(") >= 2)

# =============================================================================
# 24. 엣지 케이스
# =============================================================================
result.set_section("24. 엣지 케이스")

# Enum 해시 가능
result.check("ReIDModel hashable", hash(ReIDModel.OSNET) is not None)
result.check("MatchStatus hashable", hash(MatchStatus.MATCHED) is not None)

# dict 키/set 사용 가능
d = {ReIDModel.OSNET: 1, MatchStatus.MATCHED: 2}
result.check("Enum dict key 사용 가능", len(d) == 2)

s = {ReIDModel.OSNET, ReIDModel.OSNET}
result.check("Enum set 중복 제거", len(s) == 1)

# Enum 이터레이션
result.check("ReIDModel 이터레이션", len(list(ReIDModel)) == 9)
result.check("MatchStatus 이터레이션", len(list(MatchStatus)) == 5)

# ValueError on invalid
try:
    ReIDModel("invalid_model")
    result.fail("ReIDModel('invalid_model') ValueError", "예외 미발생")
except ValueError:
    result.ok("ReIDModel('invalid_model') ValueError")

try:
    MatchStatus("invalid_status")
    result.fail("MatchStatus('invalid_status') ValueError", "예외 미발생")
except ValueError:
    result.ok("MatchStatus('invalid_status') ValueError")

# =============================================================================
sys.exit(0 if result.summary() else 1)
