# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_event_types.py

이벤트 타입 상수 모듈 유닛 테스트
- EventCategory: 생성, 값, to_korean, 해시/identity
- EventType: 93개 멤버, 값 형식, category, is_error_event, is_progress_event, to_korean
- _CATEGORY_MAP: 접두어→카테고리 매핑
- _get_event_category: lru_cache 캐시
- WEBHOOK_EVENTS / REALTIME_EVENTS / AUDIT_EVENTS / METRIC_EVENTS: 그룹 구성
- EVENT_PRIORITY: 우선순위 매핑
- get_event_priority: 기본값 3, 우선순위 반환
- 한글 맵 완전성 (8 + 93)
- __all__ export
- 에지 케이스

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
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

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, detail)

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. EventCategory 기본 ====================
def test_event_category_basics(r: TestResult) -> None:
    print("\n[1] EventCategory 기본")
    from shared.constants.event_types import EventCategory

    r.check("Enum 크기 = 8", len(EventCategory) == 8)

    expected = {
        "SYSTEM": "system",
        "ANALYSIS": "analysis",
        "GAME": "game",
        "REFEREE": "referee",
        "FEEDBACK": "feedback",
        "LEARNING": "learning",
        "USER": "user",
        "INFRASTRUCTURE": "infra",
    }
    for name, value in expected.items():
        cat = EventCategory[name]
        r.check(f"{name} = '{value}'", cat.value == value)


# ==================== 2. EventCategory.to_korean ====================
def test_event_category_korean(r: TestResult) -> None:
    print("\n[2] EventCategory.to_korean")
    from shared.constants.event_types import EventCategory

    korean_map = {
        EventCategory.SYSTEM: "시스템",
        EventCategory.ANALYSIS: "분석",
        EventCategory.GAME: "경기",
        EventCategory.REFEREE: "심판",
        EventCategory.FEEDBACK: "피드백",
        EventCategory.LEARNING: "학습",
        EventCategory.USER: "사용자",
        EventCategory.INFRASTRUCTURE: "인프라",
    }
    for cat, expected_kr in korean_map.items():
        r.check(f"{cat.name}.to_korean() = '{expected_kr}'",
                cat.to_korean() == expected_kr)


# ==================== 3. EventType 기본 ====================
def test_event_type_basics(r: TestResult) -> None:
    print("\n[3] EventType 기본")
    from shared.constants.event_types import EventType

    r.check("Enum 크기 = 93", len(EventType) == 93)

    # 주요 멤버 존재 확인
    expected_members = [
        "SYSTEM_STARTED", "SYSTEM_SHUTDOWN", "SYSTEM_ERROR",
        "TASK_CREATED", "TASK_COMPLETED", "TASK_FAILED",
        "ANALYSIS_SHOOTING_STARTED", "ANALYSIS_SHOOTING_COMPLETED",
        "ANALYSIS_DRIBBLING_STARTED", "ANALYSIS_DRIBBLING_COMPLETED",
        "GAME_ANALYSIS_STARTED", "GAME_SHOT_DETECTED",
        "REFEREE_ANALYSIS_STARTED", "VIOLATION_DETECTED", "FOUL_DETECTED",
        "FEEDBACK_GENERATED", "REPORT_WEEKLY_GENERATED",
        "LEARNING_PATTERN_DETECTED",
        "CACHE_HIT", "QUEUE_MESSAGE_PUBLISHED",
        "MODEL_LOADED", "MODEL_INFERENCE_COMPLETED",
    ]
    for name in expected_members:
        r.check(f"멤버 {name} 존재", hasattr(EventType, name))


# ==================== 4. EventType 값 형식 ====================
def test_event_type_value_format(r: TestResult) -> None:
    print("\n[4] EventType 값 형식 (domain.action)")
    from shared.constants.event_types import EventType

    # 모든 값이 '.'로 구분된 형식
    for et in EventType:
        val = et.value
        parts = val.split(".")
        r.check(f"{et.name} 점 구분 ≥ 2", len(parts) >= 2,
                f"값: {val}, 파트: {len(parts)}")


# ==================== 5. EventType.category 속성 ====================
def test_event_type_category(r: TestResult) -> None:
    print("\n[5] EventType.category")
    from shared.constants.event_types import EventType, EventCategory

    # 접두어별 카테고리 매핑 검증
    category_tests = [
        # (이벤트 이름, 기대 카테고리)
        ("SYSTEM_STARTED", EventCategory.SYSTEM),
        ("SYSTEM_ERROR", EventCategory.SYSTEM),
        ("TASK_CREATED", EventCategory.ANALYSIS),        # task → ANALYSIS
        ("TASK_COMPLETED", EventCategory.ANALYSIS),
        ("ANALYSIS_SHOOTING_STARTED", EventCategory.ANALYSIS),  # analysis → ANALYSIS
        ("ANALYSIS_DRIBBLING_COMPLETED", EventCategory.ANALYSIS),
        ("GAME_ANALYSIS_STARTED", EventCategory.GAME),    # game → GAME
        ("GAME_SHOT_DETECTED", EventCategory.GAME),
        ("REFEREE_ANALYSIS_STARTED", EventCategory.REFEREE),  # referee → REFEREE
        ("VIOLATION_DETECTED", EventCategory.REFEREE),
        ("FOUL_DETECTED", EventCategory.REFEREE),
        ("FEEDBACK_GENERATED", EventCategory.FEEDBACK),    # feedback → FEEDBACK
        ("REPORT_WEEKLY_GENERATED", EventCategory.FEEDBACK),  # report → FEEDBACK
        ("LEARNING_PATTERN_DETECTED", EventCategory.LEARNING),  # learning → LEARNING
        ("CACHE_HIT", EventCategory.INFRASTRUCTURE),       # infra → INFRASTRUCTURE
        ("QUEUE_MESSAGE_PUBLISHED", EventCategory.INFRASTRUCTURE),
        ("MODEL_LOADED", EventCategory.SYSTEM),            # model → SYSTEM
        ("MODEL_INFERENCE_COMPLETED", EventCategory.SYSTEM),
    ]
    for name, expected_cat in category_tests:
        et = EventType[name]
        r.check(f"{name}.category = {expected_cat.name}", et.category == expected_cat)


# ==================== 6. EventType.is_error_event ====================
def test_is_error_event(r: TestResult) -> None:
    print("\n[6] is_error_event")
    from shared.constants.event_types import EventType

    # True: 'failed' 또는 'error' 포함
    error_events = [
        "SYSTEM_ERROR", "TASK_FAILED",
        "ANALYSIS_SHOOTING_FAILED", "ANALYSIS_DRIBBLING_FAILED",
        "GAME_ANALYSIS_FAILED",
        "REFEREE_ANALYSIS_FAILED",
        "MODEL_INFERENCE_FAILED",
        "QUEUE_MESSAGE_FAILED",
    ]
    for name in error_events:
        r.check(f"{name}.is_error_event = True", EventType[name].is_error_event)

    # False: 'failed'와 'error' 모두 미포함
    non_error_events = [
        "SYSTEM_STARTED", "TASK_COMPLETED", "TASK_PROGRESS",
        "ANALYSIS_SHOOTING_COMPLETED", "GAME_SHOT_DETECTED",
        "FEEDBACK_GENERATED", "CACHE_HIT", "MODEL_LOADED",
    ]
    for name in non_error_events:
        r.check(f"{name}.is_error_event = False", not EventType[name].is_error_event)


# ==================== 7. EventType.is_progress_event ====================
def test_is_progress_event(r: TestResult) -> None:
    print("\n[7] is_progress_event")
    from shared.constants.event_types import EventType

    # True: 'progress' 또는 'started' 포함
    progress_events = [
        "SYSTEM_STARTED", "TASK_STARTED", "TASK_PROGRESS",
        "ANALYSIS_SHOOTING_STARTED", "ANALYSIS_SHOOTING_PROGRESS",
        "ANALYSIS_DRIBBLING_STARTED", "ANALYSIS_DRIBBLING_PROGRESS",
        "ANALYSIS_PASSING_STARTED", "ANALYSIS_DEFENSE_STARTED",
        "ANALYSIS_COMPARISON_STARTED",
        "GAME_ANALYSIS_STARTED", "GAME_ANALYSIS_PROGRESS",
        "REFEREE_ANALYSIS_STARTED",
        "MODEL_INFERENCE_STARTED",
    ]
    for name in progress_events:
        r.check(f"{name}.is_progress_event = True", EventType[name].is_progress_event)

    # False
    non_progress_events = [
        "SYSTEM_SHUTDOWN", "TASK_COMPLETED", "TASK_FAILED",
        "ANALYSIS_SHOOTING_COMPLETED", "GAME_SHOT_DETECTED",
        "FEEDBACK_GENERATED", "CACHE_HIT", "MODEL_LOADED",
    ]
    for name in non_progress_events:
        r.check(f"{name}.is_progress_event = False", not EventType[name].is_progress_event)


# ==================== 8. EventType.to_korean ====================
def test_event_type_korean(r: TestResult) -> None:
    print("\n[8] EventType.to_korean")
    from shared.constants.event_types import EventType

    # 대표 이벤트 한글 매핑 확인
    korean_tests = {
        EventType.SYSTEM_STARTED: "시스템 시작",
        EventType.TASK_COMPLETED: "작업 완료됨",
        EventType.ANALYSIS_SHOOTING_COMPLETED: "슈팅 분석 완료",
        EventType.GAME_SHOT_DETECTED: "슛 감지",
        EventType.VIOLATION_TRAVELING: "트래블링 감지",
        EventType.FOUL_PERSONAL: "개인 파울 감지",
        EventType.FEEDBACK_GENERATED: "피드백 생성됨",
        EventType.REPORT_WEEKLY_GENERATED: "주간 레포트 생성됨",
        EventType.LEARNING_PATTERN_DETECTED: "학습 패턴 감지",
        EventType.CACHE_HIT: "캐시 적중",
        EventType.MODEL_LOADED: "모델 로드",
        EventType.DATABASE_QUERY_SLOW: "느린 쿼리 감지",
    }
    for et, expected_kr in korean_tests.items():
        r.check(f"{et.name} → '{expected_kr}'", et.to_korean() == expected_kr)


# ==================== 9. 한글 맵 완전성 ====================
def test_korean_map_completeness(r: TestResult) -> None:
    print("\n[9] 한글 맵 완전성")
    from shared.constants.event_types import EventType, EventCategory

    # EventCategory 한글 전수
    for cat in EventCategory:
        try:
            kr = cat.to_korean()
            r.check(f"EventCategory.{cat.name} 한글 존재", isinstance(kr, str) and len(kr) > 0)
        except KeyError:
            r.fail(f"EventCategory.{cat.name} 한글 누락")

    # EventType 한글 전수 (93개)
    missing = []
    for et in EventType:
        try:
            kr = et.to_korean()
            if not isinstance(kr, str) or len(kr) == 0:
                missing.append(et.name)
        except KeyError:
            missing.append(et.name)
    r.check("EventType 한글 93개 전수 매핑", len(missing) == 0,
            f"누락: {missing[:5]}" if missing else "")


# ==================== 10. WEBHOOK_EVENTS ====================
def test_webhook_events(r: TestResult) -> None:
    print("\n[10] WEBHOOK_EVENTS")
    from shared.constants.event_types import EventType, WEBHOOK_EVENTS

    r.check("frozenset 타입", isinstance(WEBHOOK_EVENTS, frozenset))
    r.check("12개 멤버", len(WEBHOOK_EVENTS) == 12)

    # 주요 멤버 포함 확인
    expected_in = [
        EventType.TASK_COMPLETED,
        EventType.TASK_FAILED,
        EventType.ANALYSIS_SHOOTING_COMPLETED,
        EventType.GAME_ANALYSIS_COMPLETED,
        EventType.REFEREE_ANALYSIS_COMPLETED,
        EventType.REPORT_WEEKLY_GENERATED,
    ]
    for et in expected_in:
        r.check(f"{et.name} ∈ WEBHOOK_EVENTS", et in WEBHOOK_EVENTS)

    # 포함되지 않아야 할 멤버
    not_in = [
        EventType.TASK_STARTED,
        EventType.TASK_PROGRESS,
        EventType.CACHE_HIT,
        EventType.SYSTEM_STARTED,
    ]
    for et in not_in:
        r.check(f"{et.name} ∉ WEBHOOK_EVENTS", et not in WEBHOOK_EVENTS)


# ==================== 11. REALTIME_EVENTS ====================
def test_realtime_events(r: TestResult) -> None:
    print("\n[11] REALTIME_EVENTS")
    from shared.constants.event_types import EventType, REALTIME_EVENTS

    r.check("frozenset 타입", isinstance(REALTIME_EVENTS, frozenset))
    r.check("12개 멤버", len(REALTIME_EVENTS) == 12)

    # 실시간 전송 대상
    expected_in = [
        EventType.TASK_STARTED,
        EventType.TASK_PROGRESS,
        EventType.TASK_COMPLETED,
        EventType.TASK_FAILED,
        EventType.GAME_SHOT_DETECTED,
        EventType.GAME_SCORE_DETECTED,
        EventType.HIGHLIGHT_DETECTED,
        EventType.VIOLATION_DETECTED,
        EventType.FOUL_DETECTED,
    ]
    for et in expected_in:
        r.check(f"{et.name} ∈ REALTIME_EVENTS", et in REALTIME_EVENTS)


# ==================== 12. AUDIT_EVENTS ====================
def test_audit_events(r: TestResult) -> None:
    print("\n[12] AUDIT_EVENTS")
    from shared.constants.event_types import EventType, AUDIT_EVENTS

    r.check("frozenset 타입", isinstance(AUDIT_EVENTS, frozenset))
    r.check("10개 멤버", len(AUDIT_EVENTS) == 10)

    # 감사 로깅 대상
    expected_in = [
        EventType.SYSTEM_STARTED,
        EventType.SYSTEM_SHUTDOWN,
        EventType.SYSTEM_ERROR,
        EventType.TASK_CREATED,
        EventType.MODEL_LOADED,
        EventType.LEARNING_MODEL_UPDATED,
    ]
    for et in expected_in:
        r.check(f"{et.name} ∈ AUDIT_EVENTS", et in AUDIT_EVENTS)


# ==================== 13. METRIC_EVENTS ====================
def test_metric_events(r: TestResult) -> None:
    print("\n[13] METRIC_EVENTS")
    from shared.constants.event_types import EventType, METRIC_EVENTS

    r.check("frozenset 타입", isinstance(METRIC_EVENTS, frozenset))
    r.check("10개 멤버", len(METRIC_EVENTS) == 10)

    # 메트릭 수집 대상
    expected_in = [
        EventType.TASK_STARTED,
        EventType.TASK_COMPLETED,
        EventType.TASK_FAILED,
        EventType.MODEL_INFERENCE_STARTED,
        EventType.MODEL_INFERENCE_COMPLETED,
        EventType.CACHE_HIT,
        EventType.CACHE_MISS,
        EventType.DATABASE_QUERY_SLOW,
    ]
    for et in expected_in:
        r.check(f"{et.name} ∈ METRIC_EVENTS", et in METRIC_EVENTS)


# ==================== 14. EVENT_PRIORITY ====================
def test_event_priority(r: TestResult) -> None:
    print("\n[14] EVENT_PRIORITY")
    from shared.constants.event_types import EventType, EVENT_PRIORITY

    r.check("dict 타입", isinstance(EVENT_PRIORITY, dict))
    r.check("14개 엔트리", len(EVENT_PRIORITY) == 14)

    # 우선순위 0 (최우선) - 시스템 장애
    priority_0 = [
        EventType.SYSTEM_ERROR,
        EventType.SYSTEM_SHUTDOWN,
        EventType.DATABASE_CONNECTION_LOST,
    ]
    for et in priority_0:
        r.check(f"{et.name} priority=0", EVENT_PRIORITY[et] == 0)

    # 우선순위 1 (높음) - 에러
    priority_1 = [
        EventType.TASK_FAILED,
        EventType.GAME_ANALYSIS_FAILED,
        EventType.REFEREE_ANALYSIS_FAILED,
        EventType.MODEL_INFERENCE_FAILED,
    ]
    for et in priority_1:
        r.check(f"{et.name} priority=1", EVENT_PRIORITY[et] == 1)

    # 우선순위 2 (중간) - 완료
    priority_2 = [
        EventType.TASK_COMPLETED,
        EventType.ANALYSIS_SHOOTING_COMPLETED,
        EventType.GAME_ANALYSIS_COMPLETED,
    ]
    for et in priority_2:
        r.check(f"{et.name} priority=2", EVENT_PRIORITY[et] == 2)

    # 우선순위 4 (최저) - 인프라
    priority_4 = [
        EventType.CACHE_HIT,
        EventType.CACHE_MISS,
    ]
    for et in priority_4:
        r.check(f"{et.name} priority=4", EVENT_PRIORITY[et] == 4)


# ==================== 15. get_event_priority ====================
def test_get_event_priority(r: TestResult) -> None:
    print("\n[15] get_event_priority")
    from shared.constants.event_types import EventType, get_event_priority

    # 명시적 우선순위
    r.check("SYSTEM_ERROR = 0", get_event_priority(EventType.SYSTEM_ERROR) == 0)
    r.check("TASK_FAILED = 1", get_event_priority(EventType.TASK_FAILED) == 1)
    r.check("TASK_COMPLETED = 2", get_event_priority(EventType.TASK_COMPLETED) == 2)
    r.check("CACHE_HIT = 4", get_event_priority(EventType.CACHE_HIT) == 4)

    # 기본값 3 (매핑에 없는 이벤트)
    r.check("SYSTEM_STARTED 기본값=3", get_event_priority(EventType.SYSTEM_STARTED) == 3)
    r.check("FEEDBACK_GENERATED 기본값=3", get_event_priority(EventType.FEEDBACK_GENERATED) == 3)
    r.check("VIOLATION_DETECTED 기본값=3", get_event_priority(EventType.VIOLATION_DETECTED) == 3)
    r.check("MODEL_LOADED 기본값=3", get_event_priority(EventType.MODEL_LOADED) == 3)


# ==================== 16. _CATEGORY_MAP 접두어 매핑 ====================
def test_category_map_prefixes(r: TestResult) -> None:
    print("\n[16] _CATEGORY_MAP 접두어 매핑")
    from shared.constants.event_types import EventType, EventCategory

    # 모든 EventType에 대해 category 속성이 유효한 EventCategory를 반환하는지 확인
    for et in EventType:
        cat = et.category
        r.check(f"{et.name}.category = {cat.name}",
                isinstance(cat, EventCategory))


# ==================== 17. __all__ export ====================
def test_all_exports(r: TestResult) -> None:
    print("\n[17] __all__ export")
    import shared.constants.event_types as module

    expected_exports = [
        "EventCategory", "EventType",
        "WEBHOOK_EVENTS", "REALTIME_EVENTS", "AUDIT_EVENTS", "METRIC_EVENTS",
        "EVENT_PRIORITY", "get_event_priority",
    ]
    r.check("__all__ 존재", hasattr(module, "__all__"))
    r.check("__all__ 크기 = 8", len(module.__all__) == 8)

    for name in expected_exports:
        r.check(f"'{name}' ∈ __all__", name in module.__all__)


# ==================== 18. 이벤트 그룹 상호 관계 ====================
def test_event_group_relations(r: TestResult) -> None:
    print("\n[18] 이벤트 그룹 상호 관계")
    from shared.constants.event_types import (
        EventType, WEBHOOK_EVENTS, REALTIME_EVENTS,
        AUDIT_EVENTS, METRIC_EVENTS,
    )

    # WEBHOOK과 REALTIME 교집합 (공통: TASK_COMPLETED, TASK_FAILED)
    overlap_wr = WEBHOOK_EVENTS & REALTIME_EVENTS
    r.check("WEBHOOK ∩ REALTIME 존재", len(overlap_wr) >= 2)
    r.check("TASK_COMPLETED 공통", EventType.TASK_COMPLETED in overlap_wr)
    r.check("TASK_FAILED 공통", EventType.TASK_FAILED in overlap_wr)

    # AUDIT과 METRIC 교집합
    overlap_am = AUDIT_EVENTS & METRIC_EVENTS
    r.check("AUDIT ∩ METRIC 존재", len(overlap_am) >= 2)
    r.check("TASK_COMPLETED 공통 (감사+메트릭)",
            EventType.TASK_COMPLETED in overlap_am)
    r.check("TASK_FAILED 공통 (감사+메트릭)",
            EventType.TASK_FAILED in overlap_am)

    # 모든 그룹의 멤버는 유효한 EventType
    all_group_events = WEBHOOK_EVENTS | REALTIME_EVENTS | AUDIT_EVENTS | METRIC_EVENTS
    for et in all_group_events:
        r.check(f"그룹 멤버 {et.name} 유효",
                isinstance(et, EventType))


# ==================== 19. 값 유일성 ====================
def test_value_uniqueness(r: TestResult) -> None:
    print("\n[19] EventType 값 유일성")
    from shared.constants.event_types import EventType

    values = [et.value for et in EventType]
    r.check("93개 값 모두 고유", len(values) == len(set(values)))

    # 이름도 모두 고유 (@unique 보장)
    names = [et.name for et in EventType]
    r.check("93개 이름 모두 고유", len(names) == len(set(names)))


# ==================== 20. 에지 케이스 ====================
def test_edge_cases(r: TestResult) -> None:
    print("\n[20] 에지 케이스")
    from shared.constants.event_types import EventType, EventCategory

    # 동일 비교
    r.check("동일 이벤트 비교",
            EventType.SYSTEM_STARTED == EventType.SYSTEM_STARTED)
    r.check("다른 이벤트 비교",
            EventType.SYSTEM_STARTED != EventType.SYSTEM_SHUTDOWN)

    # identity 보장 (싱글턴)
    r.check("identity 보장",
            EventType.SYSTEM_STARTED is EventType.SYSTEM_STARTED)

    # 해시 가능 → dict 키 사용
    d = {EventType.SYSTEM_STARTED: "test"}
    r.check("dict 키 사용 가능", d[EventType.SYSTEM_STARTED] == "test")

    # set 멤버 사용
    s = {EventType.SYSTEM_STARTED, EventType.SYSTEM_SHUTDOWN}
    r.check("set 멤버 사용 가능", len(s) == 2)

    # EventCategory도 동일
    cat_set = set(EventCategory)
    r.check("EventCategory set 가능", len(cat_set) == 8)

    # 문자열 변환
    r.check("EventType str", "SYSTEM_STARTED" in str(EventType.SYSTEM_STARTED))
    r.check("EventCategory str", "SYSTEM" in str(EventCategory.SYSTEM))

    # is_error_event / is_progress_event 동시 True
    # ANALYSIS_SHOOTING_FAILED: 'failed' → is_error=True, 'started' 없음 → is_progress=False
    r.check("SHOOTING_FAILED: error=T, progress=F",
            EventType.ANALYSIS_SHOOTING_FAILED.is_error_event and
            not EventType.ANALYSIS_SHOOTING_FAILED.is_progress_event)

    # TASK_STARTED: 'started' → is_progress=True, 'failed'/'error' 없음 → is_error=False
    r.check("TASK_STARTED: error=F, progress=T",
            not EventType.TASK_STARTED.is_error_event and
            EventType.TASK_STARTED.is_progress_event)

    # SYSTEM_STARTED: 'started' → is_progress=True, 'error' 없음 → is_error=False
    r.check("SYSTEM_STARTED: error=F, progress=T",
            not EventType.SYSTEM_STARTED.is_error_event and
            EventType.SYSTEM_STARTED.is_progress_event)


# ==================== 21. 특정 값 검증 ====================
def test_specific_values(r: TestResult) -> None:
    print("\n[21] 특정 이벤트 값 검증")
    from shared.constants.event_types import EventType

    specific_values = {
        "SYSTEM_STARTED": "system.started",
        "TASK_COMPLETED": "task.completed",
        "ANALYSIS_SHOOTING_COMPLETED": "analysis.shooting.completed",
        "GAME_SHOT_DETECTED": "game.shot.detected",
        "VIOLATION_TRAVELING": "referee.violation.traveling",
        "FOUL_TECHNICAL": "referee.foul.technical",
        "FEEDBACK_GENERATED": "feedback.generated",
        "REPORT_WEEKLY_GENERATED": "report.weekly.generated",
        "LEARNING_PATTERN_DETECTED": "learning.pattern.detected",
        "CACHE_HIT": "infra.cache.hit",
        "QUEUE_MESSAGE_DEAD_LETTER": "infra.queue.dead_letter",
        "DATABASE_QUERY_SLOW": "infra.database.slow_query",
        "MODEL_LOADED": "model.loaded",
    }
    for name, expected_val in specific_values.items():
        r.check(f"{name} = '{expected_val}'", EventType[name].value == expected_val)


def main():
    r = TestResult()
    test_event_category_basics(r)       # 1: 9
    test_event_category_korean(r)       # 2: 8
    test_event_type_basics(r)           # 3: 23
    test_event_type_value_format(r)     # 4: 93
    test_event_type_category(r)         # 5: 18
    test_is_error_event(r)              # 6: 16
    test_is_progress_event(r)           # 7: 22
    test_event_type_korean(r)           # 8: 12
    test_korean_map_completeness(r)     # 9: 9
    test_webhook_events(r)              # 10: 10
    test_realtime_events(r)             # 11: 11
    test_audit_events(r)                # 12: 8
    test_metric_events(r)               # 13: 10
    test_event_priority(r)              # 14: 14
    test_get_event_priority(r)          # 15: 8
    test_category_map_prefixes(r)       # 16: 93
    test_all_exports(r)                 # 17: 10
    test_event_group_relations(r)       # 18: 8
    test_value_uniqueness(r)            # 19: 2
    test_edge_cases(r)                  # 20: 12
    test_specific_values(r)             # 21: 13
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
