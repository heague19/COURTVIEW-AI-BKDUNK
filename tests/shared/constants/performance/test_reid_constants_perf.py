# -*- coding: utf-8 -*-
"""
tests/shared/constants/performance/test_reid_constants_perf.py

Re-Identification (재식별) 상수 모듈 성능 테스트
- 모듈 임포트 시간
- ReIDModel 프로퍼티 접근 (feature_dim, input_size, is_lightweight, to_korean)
- MatchStatus 프로퍼티 접근 (is_successful, needs_confirmation, should_retry, to_korean)
- Enum 이터레이션 (2개 Enum, 총 14개 멤버)
- frozenset 멤버십 테스트
- dict 캐시 직접 조회
- 복합 시나리오 (재식별 파이프라인)
- 메모리 사용량

성능 기준:
- 모듈 임포트: < 500ms
- 프로퍼티 접근: < 1μs
- frozenset 멤버십: < 1μs
- Enum 순회 (14개): < 20μs
- 메모리 사용량: < 256KB
- 복합 시나리오: < 50μs

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (parents[4]: performance -> constants -> shared -> tests -> PROJECT_ROOT)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# ==================== 테스트 결과 클래스 ====================
class PerfResult:
    """성능 테스트 결과 수집 및 보고"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name, elapsed_us, limit_us):
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.2f}us ({ratio:.0f}% of {limit_us:.0f}us)")

    def fail(self, name, elapsed_us, limit_us):
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.2f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.2f}us (limit: {limit_us:.0f}us)")

    def info(self, msg):
        print(f"  [INFO] {msg}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")
        return self.failed == 0


def measure(func, iterations=10000):
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


def _check(r, name, elapsed, limit):
    """결과 판정 헬퍼"""
    if elapsed <= limit:
        r.ok(name, elapsed, limit)
    else:
        r.fail(name, elapsed, limit)


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 최초 임포트 시간 측정 (< 500ms)"""
    import importlib

    mod_name = "shared.constants.reid_constants"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000  # 500ms = 500,000us

    r.info(f"임포트 시간: {elapsed_us / 1000:.2f}ms")
    _check(r, "모듈 임포트 (cold)", elapsed_us, limit_us)


# ==================== 2. ReIDModel.feature_dim 접근 ====================
def test_reidmodel_feature_dim(r: PerfResult) -> None:
    """ReIDModel.feature_dim 프로퍼티 접근 (< 1us each)"""
    from shared.constants.reid_constants import ReIDModel

    limit = 1.0

    def access_feature_dim():
        _ = ReIDModel.OSNET.feature_dim
        _ = ReIDModel.OSNET_AIN.feature_dim
        _ = ReIDModel.RESNET50.feature_dim
        _ = ReIDModel.RESNET50_IBN.feature_dim
        _ = ReIDModel.MGN.feature_dim
        _ = ReIDModel.PCB.feature_dim
        _ = ReIDModel.AGW.feature_dim
        _ = ReIDModel.TRANSREID.feature_dim
        _ = ReIDModel.CUSTOM.feature_dim

    elapsed = measure(access_feature_dim, iterations=100_000)
    per_access = elapsed / 9
    _check(r, "ReIDModel.feature_dim (9모델)", per_access, limit)


# ==================== 3. ReIDModel.input_size 접근 ====================
def test_reidmodel_input_size(r: PerfResult) -> None:
    """ReIDModel.input_size 프로퍼티 접근 (< 1us each)"""
    from shared.constants.reid_constants import ReIDModel

    limit = 1.0

    def access_input_size():
        _ = ReIDModel.OSNET.input_size
        _ = ReIDModel.OSNET_AIN.input_size
        _ = ReIDModel.RESNET50.input_size
        _ = ReIDModel.RESNET50_IBN.input_size
        _ = ReIDModel.MGN.input_size
        _ = ReIDModel.PCB.input_size
        _ = ReIDModel.AGW.input_size
        _ = ReIDModel.TRANSREID.input_size
        _ = ReIDModel.CUSTOM.input_size

    elapsed = measure(access_input_size, iterations=100_000)
    per_access = elapsed / 9
    _check(r, "ReIDModel.input_size (9모델)", per_access, limit)


# ==================== 4. ReIDModel.is_lightweight 접근 ====================
def test_reidmodel_is_lightweight(r: PerfResult) -> None:
    """ReIDModel.is_lightweight 프로퍼티 접근 (< 1us each)"""
    from shared.constants.reid_constants import ReIDModel

    limit = 1.0

    def access_is_lightweight():
        _ = ReIDModel.OSNET.is_lightweight         # True
        _ = ReIDModel.OSNET_AIN.is_lightweight      # True
        _ = ReIDModel.RESNET50.is_lightweight       # False
        _ = ReIDModel.RESNET50_IBN.is_lightweight   # False
        _ = ReIDModel.MGN.is_lightweight            # False
        _ = ReIDModel.PCB.is_lightweight            # False
        _ = ReIDModel.AGW.is_lightweight            # False
        _ = ReIDModel.TRANSREID.is_lightweight      # False
        _ = ReIDModel.CUSTOM.is_lightweight         # False

    elapsed = measure(access_is_lightweight, iterations=100_000)
    per_access = elapsed / 9
    _check(r, "ReIDModel.is_lightweight (9모델)", per_access, limit)


# ==================== 5. ReIDModel.to_korean() 메서드 ====================
def test_reidmodel_to_korean(r: PerfResult) -> None:
    """ReIDModel.to_korean() 메서드 호출 (< 1us each)"""
    from shared.constants.reid_constants import ReIDModel

    limit = 1.0

    def access_to_korean():
        _ = ReIDModel.OSNET.to_korean()
        _ = ReIDModel.OSNET_AIN.to_korean()
        _ = ReIDModel.RESNET50.to_korean()
        _ = ReIDModel.RESNET50_IBN.to_korean()
        _ = ReIDModel.MGN.to_korean()
        _ = ReIDModel.PCB.to_korean()
        _ = ReIDModel.AGW.to_korean()
        _ = ReIDModel.TRANSREID.to_korean()
        _ = ReIDModel.CUSTOM.to_korean()

    elapsed = measure(access_to_korean, iterations=100_000)
    per_access = elapsed / 9
    _check(r, "ReIDModel.to_korean() (9모델)", per_access, limit)


# ==================== 6. MatchStatus.is_successful 접근 ====================
def test_matchstatus_is_successful(r: PerfResult) -> None:
    """MatchStatus.is_successful 프로퍼티 접근 (< 1us each)"""
    from shared.constants.reid_constants import MatchStatus

    limit = 1.0

    def access_is_successful():
        _ = MatchStatus.MATCHED.is_successful       # True
        _ = MatchStatus.NEW.is_successful            # True
        _ = MatchStatus.AMBIGUOUS.is_successful      # False
        _ = MatchStatus.LOW_QUALITY.is_successful    # False
        _ = MatchStatus.FAILED.is_successful         # False

    elapsed = measure(access_is_successful, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "MatchStatus.is_successful (5상태)", per_access, limit)


# ==================== 7. MatchStatus.needs_confirmation 접근 ====================
def test_matchstatus_needs_confirmation(r: PerfResult) -> None:
    """MatchStatus.needs_confirmation 프로퍼티 접근 (< 1us each)"""
    from shared.constants.reid_constants import MatchStatus

    limit = 1.0

    def access_needs_confirmation():
        _ = MatchStatus.MATCHED.needs_confirmation       # False
        _ = MatchStatus.NEW.needs_confirmation            # False
        _ = MatchStatus.AMBIGUOUS.needs_confirmation      # True
        _ = MatchStatus.LOW_QUALITY.needs_confirmation    # True
        _ = MatchStatus.FAILED.needs_confirmation         # False

    elapsed = measure(access_needs_confirmation, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "MatchStatus.needs_confirmation (5상태)", per_access, limit)


# ==================== 8. MatchStatus.should_retry 접근 ====================
def test_matchstatus_should_retry(r: PerfResult) -> None:
    """MatchStatus.should_retry 프로퍼티 접근 (< 1us each)"""
    from shared.constants.reid_constants import MatchStatus

    limit = 1.0

    def access_should_retry():
        _ = MatchStatus.MATCHED.should_retry       # False
        _ = MatchStatus.NEW.should_retry            # False
        _ = MatchStatus.AMBIGUOUS.should_retry      # False
        _ = MatchStatus.LOW_QUALITY.should_retry    # True
        _ = MatchStatus.FAILED.should_retry         # True

    elapsed = measure(access_should_retry, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "MatchStatus.should_retry (5상태)", per_access, limit)


# ==================== 9. MatchStatus.to_korean() 메서드 ====================
def test_matchstatus_to_korean(r: PerfResult) -> None:
    """MatchStatus.to_korean() 메서드 호출 (< 1us each)"""
    from shared.constants.reid_constants import MatchStatus

    limit = 1.0

    def access_to_korean():
        _ = MatchStatus.MATCHED.to_korean()
        _ = MatchStatus.NEW.to_korean()
        _ = MatchStatus.AMBIGUOUS.to_korean()
        _ = MatchStatus.LOW_QUALITY.to_korean()
        _ = MatchStatus.FAILED.to_korean()

    elapsed = measure(access_to_korean, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "MatchStatus.to_korean() (5상태)", per_access, limit)


# ==================== 10. Enum 이터레이션 ====================
def test_enum_iteration(r: PerfResult) -> None:
    """2개 Enum 전체 순회 -- 총 14개 멤버 (< 20us)"""
    from shared.constants.reid_constants import ReIDModel, MatchStatus

    total_members = len(list(ReIDModel)) + len(list(MatchStatus))
    r.info(f"총 Enum 멤버 수: {total_members}개 (2개 Enum)")

    limit = 20.0

    def iterate_all():
        for m in ReIDModel:
            _ = m.value
        for s in MatchStatus:
            _ = s.value

    elapsed = measure(iterate_all, iterations=50_000)
    _check(r, f"전체 Enum 순회 ({total_members}개 멤버)", elapsed, limit)

    # 개별 Enum 순회 측정
    def iterate_reidmodel():
        for m in ReIDModel:
            _ = m.value

    def iterate_matchstatus():
        for s in MatchStatus:
            _ = s.value

    elapsed_rm = measure(iterate_reidmodel, iterations=50_000)
    r.info(f"ReIDModel 순회 ({len(list(ReIDModel))}개): {elapsed_rm:.2f}us")

    elapsed_ms = measure(iterate_matchstatus, iterations=50_000)
    r.info(f"MatchStatus 순회 ({len(list(MatchStatus))}개): {elapsed_ms:.2f}us")


# ==================== 11. frozenset 멤버십 테스트 ====================
def test_frozenset_membership(r: PerfResult) -> None:
    """frozenset 멤버십 조회 -- 4개 frozenset (< 1us per lookup)"""
    from shared.constants.reid_constants import (
        ReIDModel, MatchStatus,
        _REID_MODEL_IS_LIGHTWEIGHT,
        _MATCH_STATUS_IS_SUCCESSFUL,
        _MATCH_STATUS_NEEDS_CONFIRMATION,
        _MATCH_STATUS_SHOULD_RETRY,
    )

    limit = 1.0

    # is_lightweight (양성 + 음성)
    def membership_is_lightweight():
        _ = ReIDModel.OSNET in _REID_MODEL_IS_LIGHTWEIGHT        # True
        _ = ReIDModel.OSNET_AIN in _REID_MODEL_IS_LIGHTWEIGHT    # True
        _ = ReIDModel.RESNET50 in _REID_MODEL_IS_LIGHTWEIGHT     # False
        _ = ReIDModel.MGN in _REID_MODEL_IS_LIGHTWEIGHT          # False
        _ = ReIDModel.TRANSREID in _REID_MODEL_IS_LIGHTWEIGHT    # False

    elapsed = measure(membership_is_lightweight, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "frozenset _REID_MODEL_IS_LIGHTWEIGHT 멤버십", per_lookup, limit)

    # is_successful (양성 + 음성)
    def membership_is_successful():
        _ = MatchStatus.MATCHED in _MATCH_STATUS_IS_SUCCESSFUL      # True
        _ = MatchStatus.NEW in _MATCH_STATUS_IS_SUCCESSFUL           # True
        _ = MatchStatus.AMBIGUOUS in _MATCH_STATUS_IS_SUCCESSFUL     # False
        _ = MatchStatus.LOW_QUALITY in _MATCH_STATUS_IS_SUCCESSFUL   # False
        _ = MatchStatus.FAILED in _MATCH_STATUS_IS_SUCCESSFUL        # False

    elapsed = measure(membership_is_successful, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "frozenset _MATCH_STATUS_IS_SUCCESSFUL 멤버십", per_lookup, limit)

    # needs_confirmation (양성 + 음성)
    def membership_needs_confirmation():
        _ = MatchStatus.AMBIGUOUS in _MATCH_STATUS_NEEDS_CONFIRMATION     # True
        _ = MatchStatus.LOW_QUALITY in _MATCH_STATUS_NEEDS_CONFIRMATION   # True
        _ = MatchStatus.MATCHED in _MATCH_STATUS_NEEDS_CONFIRMATION       # False
        _ = MatchStatus.NEW in _MATCH_STATUS_NEEDS_CONFIRMATION           # False
        _ = MatchStatus.FAILED in _MATCH_STATUS_NEEDS_CONFIRMATION        # False

    elapsed = measure(membership_needs_confirmation, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "frozenset _MATCH_STATUS_NEEDS_CONFIRMATION 멤버십", per_lookup, limit)

    # should_retry (양성 + 음성)
    def membership_should_retry():
        _ = MatchStatus.LOW_QUALITY in _MATCH_STATUS_SHOULD_RETRY    # True
        _ = MatchStatus.FAILED in _MATCH_STATUS_SHOULD_RETRY         # True
        _ = MatchStatus.MATCHED in _MATCH_STATUS_SHOULD_RETRY        # False
        _ = MatchStatus.NEW in _MATCH_STATUS_SHOULD_RETRY            # False
        _ = MatchStatus.AMBIGUOUS in _MATCH_STATUS_SHOULD_RETRY      # False

    elapsed = measure(membership_should_retry, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "frozenset _MATCH_STATUS_SHOULD_RETRY 멤버십", per_lookup, limit)


# ==================== 12. dict 캐시 직접 조회 ====================
def test_dict_cache_direct_lookup(r: PerfResult) -> None:
    """dict 캐시 직접 키 조회 성능 (< 1us per lookup)"""
    from shared.constants.reid_constants import (
        ReIDModel, MatchStatus,
        _REID_MODEL_FEATURE_DIM_MAP,
        _REID_MODEL_INPUT_SIZE_MAP,
        _REID_MODEL_KOREAN_MAP,
        _MATCH_STATUS_KOREAN_MAP,
    )

    limit = 1.0

    # ReIDModel feature_dim_map 직접 조회
    def lookup_feature_dim_map():
        _ = _REID_MODEL_FEATURE_DIM_MAP[ReIDModel.OSNET]
        _ = _REID_MODEL_FEATURE_DIM_MAP[ReIDModel.RESNET50]
        _ = _REID_MODEL_FEATURE_DIM_MAP[ReIDModel.MGN]
        _ = _REID_MODEL_FEATURE_DIM_MAP[ReIDModel.PCB]
        _ = _REID_MODEL_FEATURE_DIM_MAP[ReIDModel.TRANSREID]
        _ = _REID_MODEL_FEATURE_DIM_MAP[ReIDModel.CUSTOM]

    elapsed = measure(lookup_feature_dim_map, iterations=100_000)
    per_lookup = elapsed / 6
    _check(r, "dict _REID_MODEL_FEATURE_DIM_MAP 직접 조회", per_lookup, limit)

    # ReIDModel input_size_map 직접 조회
    def lookup_input_size_map():
        _ = _REID_MODEL_INPUT_SIZE_MAP[ReIDModel.OSNET]
        _ = _REID_MODEL_INPUT_SIZE_MAP[ReIDModel.RESNET50]
        _ = _REID_MODEL_INPUT_SIZE_MAP[ReIDModel.MGN]
        _ = _REID_MODEL_INPUT_SIZE_MAP[ReIDModel.TRANSREID]
        _ = _REID_MODEL_INPUT_SIZE_MAP[ReIDModel.CUSTOM]

    elapsed = measure(lookup_input_size_map, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "dict _REID_MODEL_INPUT_SIZE_MAP 직접 조회", per_lookup, limit)

    # ReIDModel korean_map 직접 조회
    def lookup_korean_map():
        _ = _REID_MODEL_KOREAN_MAP[ReIDModel.OSNET]
        _ = _REID_MODEL_KOREAN_MAP[ReIDModel.RESNET50]
        _ = _REID_MODEL_KOREAN_MAP[ReIDModel.TRANSREID]
        _ = _REID_MODEL_KOREAN_MAP[ReIDModel.CUSTOM]

    elapsed = measure(lookup_korean_map, iterations=100_000)
    per_lookup = elapsed / 4
    _check(r, "dict _REID_MODEL_KOREAN_MAP 직접 조회", per_lookup, limit)

    # MatchStatus korean_map 직접 조회
    def lookup_match_status_korean():
        _ = _MATCH_STATUS_KOREAN_MAP[MatchStatus.MATCHED]
        _ = _MATCH_STATUS_KOREAN_MAP[MatchStatus.NEW]
        _ = _MATCH_STATUS_KOREAN_MAP[MatchStatus.AMBIGUOUS]
        _ = _MATCH_STATUS_KOREAN_MAP[MatchStatus.LOW_QUALITY]
        _ = _MATCH_STATUS_KOREAN_MAP[MatchStatus.FAILED]

    elapsed = measure(lookup_match_status_korean, iterations=100_000)
    per_lookup = elapsed / 5
    _check(r, "dict _MATCH_STATUS_KOREAN_MAP 직접 조회", per_lookup, limit)


# ==================== 13. Final 상수 직접 접근 ====================
def test_final_constants_access(r: PerfResult) -> None:
    """Final[int/float/bool] 상수 직접 접근 (< 1us each)"""
    from shared.constants.reid_constants import (
        FEATURE_DIM, FEATURE_DIM_HIGH, FEATURE_DIM_LOW,
        NORMALIZE_FEATURES, FEATURE_NORMALIZE_EPS,
        SIMILARITY_THRESHOLD, HIGH_SIMILARITY_THRESHOLD,
        LOW_SIMILARITY_THRESHOLD, IDENTITY_CONFIRMED_SIMILARITY,
        GALLERY_MAX_SIZE, GALLERY_MIN_SIZE,
        EMA_MOMENTUM, EMA_MOMENTUM_FAST, EMA_MOMENTUM_STABLE,
    )

    limit = 1.0

    # 특징 벡터 상수
    def access_feature_constants():
        _ = FEATURE_DIM
        _ = FEATURE_DIM_HIGH
        _ = FEATURE_DIM_LOW
        _ = NORMALIZE_FEATURES
        _ = FEATURE_NORMALIZE_EPS

    elapsed = measure(access_feature_constants, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "Final 상수: 특징 벡터 (5개)", per_access, limit)

    # 유사도 임계값 상수
    def access_similarity_constants():
        _ = SIMILARITY_THRESHOLD
        _ = HIGH_SIMILARITY_THRESHOLD
        _ = LOW_SIMILARITY_THRESHOLD
        _ = IDENTITY_CONFIRMED_SIMILARITY

    elapsed = measure(access_similarity_constants, iterations=100_000)
    per_access = elapsed / 4
    _check(r, "Final 상수: 유사도 임계값 (4개)", per_access, limit)

    # 갤러리/EMA 상수
    def access_gallery_ema():
        _ = GALLERY_MAX_SIZE
        _ = GALLERY_MIN_SIZE
        _ = EMA_MOMENTUM
        _ = EMA_MOMENTUM_FAST
        _ = EMA_MOMENTUM_STABLE

    elapsed = measure(access_gallery_ema, iterations=100_000)
    per_access = elapsed / 5
    _check(r, "Final 상수: 갤러리/EMA (5개)", per_access, limit)


# ==================== 14. Enum(value) 역방향 조회 ====================
def test_enum_value_lookup(r: PerfResult) -> None:
    """Enum(value) 역방향 조회 성능 (< 5us per lookup)"""
    from shared.constants.reid_constants import ReIDModel, MatchStatus

    limit = 5.0

    def value_lookup_all():
        _ = ReIDModel("osnet")
        _ = ReIDModel("resnet50")
        _ = ReIDModel("mgn")
        _ = ReIDModel("transreid")
        _ = ReIDModel("custom")
        _ = MatchStatus("matched")
        _ = MatchStatus("new")
        _ = MatchStatus("ambiguous")
        _ = MatchStatus("failed")

    elapsed = measure(value_lookup_all, iterations=50_000)
    per_lookup = elapsed / 9
    _check(r, "Enum(value) 역방향 조회", per_lookup, limit)


# ==================== 15. 복합 시나리오: 재식별 파이프라인 ====================
def test_composite_reid_pipeline(r: PerfResult) -> None:
    """복합 시나리오: 재식별 파이프라인 전체 (< 50us)"""
    from shared.constants.reid_constants import (
        ReIDModel, MatchStatus,
        FEATURE_DIM, SIMILARITY_THRESHOLD, HIGH_SIMILARITY_THRESHOLD,
        LOW_SIMILARITY_THRESHOLD, IDENTITY_CONFIRMED_SIMILARITY,
        GALLERY_MAX_SIZE, GALLERY_MIN_SIZE,
        EMA_MOMENTUM, EMA_MOMENTUM_FAST, EMA_MOMENTUM_STABLE,
        MAX_MATCH_CANDIDATES, TOPK_MATCHES, MIN_MATCH_CONFIDENCE,
        CROSS_VIEW_FUSION_WEIGHT_QUALITY, CROSS_VIEW_FUSION_WEIGHT_DISTANCE,
        UNIFORM_COLOR_WEIGHT, BODY_SHAPE_WEIGHT, DEEP_FEATURE_WEIGHT,
        REID_INPUT_SIZE, REID_INPUT_SIZE_HIGH, MIN_BBOX_SIZE,
        TEMPORAL_WINDOW_SIZE, TEMPORAL_CONSISTENCY_MIN_RATIO,
    )

    limit = 50.0

    def reid_pipeline():
        # 1단계: 모델 선택
        model = ReIDModel.OSNET
        dim = model.feature_dim
        size = model.input_size
        lightweight = model.is_lightweight
        name = model.to_korean()

        # 2단계: 입력 검증
        min_h, min_w = MIN_BBOX_SIZE
        input_h, input_w = REID_INPUT_SIZE

        # 3단계: 특징 추출 파라미터
        _ = FEATURE_DIM
        _ = dim  # 모델 특정 차원

        # 4단계: 유사도 계산 (임계값 순서 확인)
        sim_score = 0.82
        is_low = sim_score < LOW_SIMILARITY_THRESHOLD
        is_match = sim_score >= SIMILARITY_THRESHOLD
        is_high = sim_score >= HIGH_SIMILARITY_THRESHOLD
        is_confirmed = sim_score >= IDENTITY_CONFIRMED_SIMILARITY

        # 5단계: 매칭 상태 결정
        if is_confirmed:
            status = MatchStatus.MATCHED
        elif is_high:
            status = MatchStatus.MATCHED
        elif is_match:
            status = MatchStatus.AMBIGUOUS
        elif is_low:
            status = MatchStatus.LOW_QUALITY
        else:
            status = MatchStatus.FAILED

        # 6단계: 상태 플래그 검사
        success = status.is_successful
        confirm = status.needs_confirmation
        retry = status.should_retry
        status_name = status.to_korean()

        # 7단계: 갤러리 관리 파라미터
        _ = GALLERY_MAX_SIZE
        _ = GALLERY_MIN_SIZE

        # 8단계: EMA 업데이트 파라미터
        _ = EMA_MOMENTUM
        _ = EMA_MOMENTUM_FAST
        _ = EMA_MOMENTUM_STABLE

        # 9단계: 크로스뷰 파라미터
        w_quality = CROSS_VIEW_FUSION_WEIGHT_QUALITY
        w_distance = CROSS_VIEW_FUSION_WEIGHT_DISTANCE

        # 10단계: 재식별 특징 가중치
        w_color = UNIFORM_COLOR_WEIGHT
        w_body = BODY_SHAPE_WEIGHT
        w_deep = DEEP_FEATURE_WEIGHT

        # 11단계: 시간적 일관성
        _ = TEMPORAL_WINDOW_SIZE
        _ = TEMPORAL_CONSISTENCY_MIN_RATIO

        # 12단계: 매칭 후보
        _ = MAX_MATCH_CANDIDATES
        _ = TOPK_MATCHES
        _ = MIN_MATCH_CONFIDENCE

    elapsed = measure(reid_pipeline, iterations=50_000)
    _check(r, "재식별 파이프라인 (12단계)", elapsed, limit)


# ==================== 16. 복합 시나리오: 모델 비교 ====================
def test_composite_model_comparison(r: PerfResult) -> None:
    """복합 시나리오: 9개 모델 전체 프로퍼티 비교 (< 30us)"""
    from shared.constants.reid_constants import ReIDModel

    limit = 30.0

    def compare_all_models():
        for model in ReIDModel:
            _ = model.feature_dim
            _ = model.input_size
            _ = model.is_lightweight
            _ = model.to_korean()

    elapsed = measure(compare_all_models, iterations=50_000)
    _check(r, "9개 모델 전체 프로퍼티 비교 (36 접근)", elapsed, limit)


# ==================== 17. 복합 시나리오: 매칭 상태 분류 ====================
def test_composite_status_classification(r: PerfResult) -> None:
    """복합 시나리오: 5개 MatchStatus 전체 분류 (< 20us)"""
    from shared.constants.reid_constants import MatchStatus

    limit = 20.0

    def classify_all_statuses():
        successful = []
        needs_confirm = []
        retry_needed = []
        for status in MatchStatus:
            name = status.to_korean()
            if status.is_successful:
                successful.append(status)
            if status.needs_confirmation:
                needs_confirm.append(status)
            if status.should_retry:
                retry_needed.append(status)

    elapsed = measure(classify_all_statuses, iterations=50_000)
    _check(r, "5개 MatchStatus 전체 분류", elapsed, limit)


# ==================== 18. 복합 시나리오: 경량 모델 필터링 ====================
def test_composite_lightweight_filtering(r: PerfResult) -> None:
    """복합 시나리오: 경량 모델만 필터링 (< 20us)"""
    from shared.constants.reid_constants import ReIDModel

    limit = 20.0

    def filter_lightweight():
        lightweight = []
        heavy = []
        for model in ReIDModel:
            if model.is_lightweight:
                lightweight.append((model, model.feature_dim, model.input_size))
            else:
                heavy.append((model, model.feature_dim, model.input_size))

    elapsed = measure(filter_lightweight, iterations=50_000)
    _check(r, "경량 모델 필터링 (9개 모델)", elapsed, limit)


# ==================== 19. 메모리 사용량 ====================
def test_memory_usage(r: PerfResult) -> None:
    """모듈 메모리 사용량 (< 256KB)"""
    import shared.constants.reid_constants as mod

    total_size = sys.getsizeof(mod)
    for name in mod.__all__:
        obj = getattr(mod, name)
        total_size += sys.getsizeof(obj)

        if isinstance(obj, dict):
            for k, v in obj.items():
                total_size += sys.getsizeof(k)
                total_size += sys.getsizeof(v)
        elif isinstance(obj, frozenset):
            for item in obj:
                total_size += sys.getsizeof(item)

    # 내부 캐시 크기도 측정
    internal_caches = [
        "_REID_MODEL_IS_LIGHTWEIGHT",
        "_MATCH_STATUS_IS_SUCCESSFUL",
        "_MATCH_STATUS_NEEDS_CONFIRMATION",
        "_MATCH_STATUS_SHOULD_RETRY",
        "_REID_MODEL_FEATURE_DIM_MAP",
        "_REID_MODEL_INPUT_SIZE_MAP",
        "_REID_MODEL_KOREAN_MAP",
        "_MATCH_STATUS_KOREAN_MAP",
    ]
    for cache_name in internal_caches:
        if hasattr(mod, cache_name):
            cache_obj = getattr(mod, cache_name)
            total_size += sys.getsizeof(cache_obj)
            if isinstance(cache_obj, dict):
                for k, v in cache_obj.items():
                    total_size += sys.getsizeof(k)
                    total_size += sys.getsizeof(v)
            elif isinstance(cache_obj, frozenset):
                for item in cache_obj:
                    total_size += sys.getsizeof(item)

    limit_kb = 256.0
    total_kb = total_size / 1024

    r.info(f"모듈 메모리 사용량: {total_kb:.1f} KB")
    _check(r, f"메모리 사용량 ({total_kb:.1f} KB)", total_kb, limit_kb)


# ==================== 20. 대량 처리량 (1K 반복) ====================
def test_bulk_operations(r: PerfResult) -> None:
    """대량 처리량: 1,000회 반복 -- 2개 Enum 전체 프로퍼티 접근 (< 500ms)"""
    from shared.constants.reid_constants import (
        ReIDModel, MatchStatus,
        FEATURE_DIM, SIMILARITY_THRESHOLD, GALLERY_MAX_SIZE,
        EMA_MOMENTUM, CROSS_VIEW_FUSION_WEIGHT_QUALITY,
        UNIFORM_COLOR_WEIGHT, BODY_SHAPE_WEIGHT, DEEP_FEATURE_WEIGHT,
    )

    iterations = 1_000

    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        # Final 상수 접근 (8개)
        _ = FEATURE_DIM
        _ = SIMILARITY_THRESHOLD
        _ = GALLERY_MAX_SIZE
        _ = EMA_MOMENTUM
        _ = CROSS_VIEW_FUSION_WEIGHT_QUALITY
        _ = UNIFORM_COLOR_WEIGHT
        _ = BODY_SHAPE_WEIGHT
        _ = DEEP_FEATURE_WEIGHT

        # ReIDModel 프로퍼티 (9개 멤버 x 4 프로퍼티 = 36 접근)
        for model in ReIDModel:
            _ = model.feature_dim
            _ = model.input_size
            _ = model.is_lightweight
            _ = model.to_korean()

        # MatchStatus 프로퍼티 (5개 멤버 x 4 프로퍼티 = 20 접근)
        for status in MatchStatus:
            _ = status.is_successful
            _ = status.needs_confirmation
            _ = status.should_retry
            _ = status.to_korean()

    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()

    elapsed_ms = elapsed_ns / 1_000_000
    limit_ms = 500.0

    r.info(f"1,000회 반복 (2개 Enum, 64 접근/회) 처리 시간: {elapsed_ms:.2f}ms")
    _check(r, f"대량 처리량 ({iterations:,}회 x 2 Enum)", elapsed_ms * 1000, limit_ms * 1000)


# ==================== 실행 ====================
def main():
    r = PerfResult()
    print("\n" + "=" * 60)
    print("reid_constants.py 성능 테스트")
    print("=" * 60)

    print("\n--- 1. 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- 2. ReIDModel.feature_dim 접근 ---")
    test_reidmodel_feature_dim(r)

    print("\n--- 3. ReIDModel.input_size 접근 ---")
    test_reidmodel_input_size(r)

    print("\n--- 4. ReIDModel.is_lightweight 접근 ---")
    test_reidmodel_is_lightweight(r)

    print("\n--- 5. ReIDModel.to_korean() 메서드 ---")
    test_reidmodel_to_korean(r)

    print("\n--- 6. MatchStatus.is_successful 접근 ---")
    test_matchstatus_is_successful(r)

    print("\n--- 7. MatchStatus.needs_confirmation 접근 ---")
    test_matchstatus_needs_confirmation(r)

    print("\n--- 8. MatchStatus.should_retry 접근 ---")
    test_matchstatus_should_retry(r)

    print("\n--- 9. MatchStatus.to_korean() 메서드 ---")
    test_matchstatus_to_korean(r)

    print("\n--- 10. Enum 이터레이션 ---")
    test_enum_iteration(r)

    print("\n--- 11. frozenset 멤버십 테스트 ---")
    test_frozenset_membership(r)

    print("\n--- 12. dict 캐시 직접 조회 ---")
    test_dict_cache_direct_lookup(r)

    print("\n--- 13. Final 상수 직접 접근 ---")
    test_final_constants_access(r)

    print("\n--- 14. Enum(value) 역방향 조회 ---")
    test_enum_value_lookup(r)

    print("\n--- 15. 복합 시나리오: 재식별 파이프라인 ---")
    test_composite_reid_pipeline(r)

    print("\n--- 16. 복합 시나리오: 모델 비교 ---")
    test_composite_model_comparison(r)

    print("\n--- 17. 복합 시나리오: 매칭 상태 분류 ---")
    test_composite_status_classification(r)

    print("\n--- 18. 복합 시나리오: 경량 모델 필터링 ---")
    test_composite_lightweight_filtering(r)

    print("\n--- 19. 메모리 사용량 ---")
    test_memory_usage(r)

    print("\n--- 20. 대량 처리량 ---")
    test_bulk_operations(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
