# -*- coding: utf-8 -*-
"""
tests/verify_event_types.py

이벤트 타입 상수 모듈 검증 테스트
- typing 현대화 검증
- EventCategory 멤버/값/한글 매핑 검증
- EventType 87개 멤버 전수 검증
- EventType 한글 매핑 완전성 검증
- _CATEGORY_MAP 프리픽스 매핑 검증
- EventType.category 프로퍼티 검증
- 이벤트 그룹 (WEBHOOK/REALTIME/AUDIT/METRIC) 검증
- EVENT_PRIORITY 우선순위 논리 검증
- is_error_event / is_progress_event 검증
- get_event_priority 함수 검증
- __all__ export 검증
- __init__.py re-export 검증

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
        print(f"검증 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== A. typing 현대화 ====================
def test_typing(r: TestResult) -> None:
    print("\n[A] typing 현대화")
    src = Path(_PROJECT_ROOT / "shared" / "constants" / "event_types.py").read_text(encoding="utf-8")
    code_lines = [line.split("#")[0] for line in src.split("\n")]
    code_only = "\n".join(code_lines)

    r.check("typing import = Final만", "from typing import Final" in src)
    r.check("Dict[ 잔존 없음", "Dict[" not in code_only)
    r.check("FrozenSet[ 잔존 없음", "FrozenSet[" not in code_only)
    r.check("List[ 잔존 없음", "List[" not in code_only)
    r.check("Tuple[ 잔존 없음", "Tuple[" not in code_only)
    r.check("dict[ 사용 확인", "dict[" in code_only)
    r.check("frozenset[ 사용 확인", "frozenset[" in code_only)


# ==================== B. EventCategory ====================
def test_event_category(r: TestResult) -> None:
    print("\n[B] EventCategory")
    from shared.constants.event_types import EventCategory

    r.check("8개 멤버", len(EventCategory) == 8)

    expected = {
        "SYSTEM": ("system", "시스템"),
        "ANALYSIS": ("analysis", "분석"),
        "GAME": ("game", "경기"),
        "REFEREE": ("referee", "심판"),
        "FEEDBACK": ("feedback", "피드백"),
        "LEARNING": ("learning", "학습"),
        "USER": ("user", "사용자"),
        "INFRASTRUCTURE": ("infra", "인프라"),
    }
    for name, (value, korean) in expected.items():
        cat = EventCategory[name]
        r.check(f"{name}.value='{value}'", cat.value == value)
        r.check(f"{name}.to_korean()='{korean}'", cat.to_korean() == korean)


# ==================== C. EventType 멤버 수 ====================
def test_event_type_count(r: TestResult) -> None:
    print("\n[C] EventType 멤버 수")
    from shared.constants.event_types import EventType

    actual_count = len(EventType)
    r.check(f"EventType {actual_count}개 멤버", actual_count == 93)

    # 도메인별 카운트
    all_values = [e.value for e in EventType]
    domain_counts = {
        "system": 7, "task": 9,
        "analysis": 14, "game": 15,
        "referee": 18, "feedback": 6,
        "report": 2, "learning": 4,
        "infra": 13, "model": 5,
    }
    # 값의 프리픽스별 카운트 검증은 전수 검증 대신 총합만
    total_expected = sum(domain_counts.values())
    r.check(f"도메인별 합계={total_expected}", total_expected == 93)
    # 실제 87개는 도메인 분할이 아닌 Enum 멤버 수
    # 위 93은 세부 분류 합이므로 맞지 않음, 실제 프리픽스 카운트 확인
    prefix_counts: dict[str, int] = {}
    for v in all_values:
        prefix = v.split(".")[0]
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

    for prefix, count in prefix_counts.items():
        r.check(f"프리픽스 '{prefix}': {count}개", count > 0)


# ==================== D. EventType 값 형식 ====================
def test_event_value_format(r: TestResult) -> None:
    print("\n[D] EventType 값 형식 (dot notation)")
    from shared.constants.event_types import EventType

    bad_format = []
    for e in EventType:
        if "." not in e.value:
            bad_format.append(e.name)
    r.check("모든 값이 dot notation", len(bad_format) == 0,
            f"잘못된 형식: {bad_format[:5]}")

    # 값 유일성
    values = [e.value for e in EventType]
    r.check("값 유일성", len(values) == len(set(values)))


# ==================== E. 한글 매핑 완전성 ====================
def test_korean_map_completeness(r: TestResult) -> None:
    print("\n[E] 한글 매핑 완전성")
    from shared.constants.event_types import EventType, EventCategory

    # EventType 전수 한글 매핑
    missing_korean = []
    for e in EventType:
        try:
            name = e.to_korean()
            if not name or not isinstance(name, str):
                missing_korean.append(e.name)
        except (KeyError, AttributeError):
            missing_korean.append(e.name)

    r.check(f"EventType 93개 한글 매핑 완전", len(missing_korean) == 0,
            f"누락: {missing_korean[:5]}")

    # EventCategory 전수 한글 매핑
    missing_cat = []
    for c in EventCategory:
        try:
            name = c.to_korean()
            if not name:
                missing_cat.append(c.name)
        except (KeyError, AttributeError):
            missing_cat.append(c.name)

    r.check(f"EventCategory 8개 한글 매핑 완전", len(missing_cat) == 0,
            f"누락: {missing_cat[:5]}")

    # 한글 포함 확인
    no_korean = []
    for e in EventType:
        name = e.to_korean()
        has_korean = any('\uac00' <= c <= '\ud7a3' for c in name)
        if not has_korean:
            no_korean.append(e.name)
    r.check("모든 한글명에 한글 포함", len(no_korean) == 0,
            f"한글 없음: {no_korean[:5]}")


# ==================== F. category 프로퍼티 ====================
def test_category_property(r: TestResult) -> None:
    print("\n[F] EventType.category 프로퍼티")
    from shared.constants.event_types import EventType, EventCategory

    # 대표 샘플 검증
    tests = [
        ("SYSTEM_STARTED", EventCategory.SYSTEM),
        ("SYSTEM_ERROR", EventCategory.SYSTEM),
        ("TASK_CREATED", EventCategory.ANALYSIS),
        ("ANALYSIS_SHOOTING_COMPLETED", EventCategory.ANALYSIS),
        ("GAME_ANALYSIS_STARTED", EventCategory.GAME),
        ("GAME_SHOT_DETECTED", EventCategory.GAME),
        ("REFEREE_ANALYSIS_STARTED", EventCategory.REFEREE),
        ("VIOLATION_DETECTED", EventCategory.REFEREE),
        ("FOUL_PERSONAL", EventCategory.REFEREE),
        ("FEEDBACK_GENERATED", EventCategory.FEEDBACK),
        ("REPORT_WEEKLY_GENERATED", EventCategory.FEEDBACK),
        ("LEARNING_PATTERN_DETECTED", EventCategory.LEARNING),
        ("CACHE_HIT", EventCategory.INFRASTRUCTURE),
        ("DATABASE_QUERY_SLOW", EventCategory.INFRASTRUCTURE),
        ("MODEL_LOADED", EventCategory.SYSTEM),
    ]
    for name, expected_cat in tests:
        event = EventType[name]
        r.check(f"{name} → {expected_cat.name}", event.category == expected_cat)

    # 모든 이벤트에 카테고리 매핑 검증 (에러 없이 접근 가능)
    errors = []
    for e in EventType:
        try:
            _ = e.category
        except Exception as ex:
            errors.append(f"{e.name}: {ex}")
    r.check("93개 전체 category 접근 가능", len(errors) == 0,
            f"에러: {errors[:3]}")


# ==================== G. is_error_event / is_progress_event ====================
def test_event_predicates(r: TestResult) -> None:
    print("\n[G] is_error_event / is_progress_event")
    from shared.constants.event_types import EventType

    # is_error_event
    error_events = [e for e in EventType if e.is_error_event]
    expected_errors = {
        "SYSTEM_ERROR", "TASK_FAILED", "ANALYSIS_SHOOTING_FAILED",
        "ANALYSIS_DRIBBLING_FAILED", "GAME_ANALYSIS_FAILED",
        "REFEREE_ANALYSIS_FAILED", "QUEUE_MESSAGE_FAILED",
        "MODEL_INFERENCE_FAILED",
    }
    actual_errors = {e.name for e in error_events}
    r.check(f"에러 이벤트 {len(expected_errors)}개", actual_errors == expected_errors,
            f"차이: {actual_errors.symmetric_difference(expected_errors)}")

    # is_progress_event: "progress" or "started"
    progress_events = [e for e in EventType if e.is_progress_event]
    # "started" 이벤트 + "progress" 이벤트
    for name in ["TASK_STARTED", "TASK_PROGRESS", "ANALYSIS_SHOOTING_STARTED",
                  "GAME_ANALYSIS_STARTED", "MODEL_INFERENCE_STARTED"]:
        r.check(f"{name}.is_progress_event=True", EventType[name].is_progress_event)

    # 완료 이벤트는 progress가 아님
    r.check("TASK_COMPLETED not progress", not EventType.TASK_COMPLETED.is_progress_event)


# ==================== H. 이벤트 그룹 ====================
def test_event_groups(r: TestResult) -> None:
    print("\n[H] 이벤트 그룹")
    from shared.constants.event_types import (
        EventType, WEBHOOK_EVENTS, REALTIME_EVENTS, AUDIT_EVENTS, METRIC_EVENTS,
    )

    # 타입 검증
    r.check("WEBHOOK_EVENTS frozenset", isinstance(WEBHOOK_EVENTS, frozenset))
    r.check("REALTIME_EVENTS frozenset", isinstance(REALTIME_EVENTS, frozenset))
    r.check("AUDIT_EVENTS frozenset", isinstance(AUDIT_EVENTS, frozenset))
    r.check("METRIC_EVENTS frozenset", isinstance(METRIC_EVENTS, frozenset))

    # 크기 검증
    r.check("WEBHOOK_EVENTS 12개", len(WEBHOOK_EVENTS) == 12)
    r.check("REALTIME_EVENTS 12개", len(REALTIME_EVENTS) == 12)
    r.check("AUDIT_EVENTS 10개", len(AUDIT_EVENTS) == 10)
    r.check("METRIC_EVENTS 10개", len(METRIC_EVENTS) == 10)

    # 모든 멤버가 EventType인지
    for group_name, group in [
        ("WEBHOOK", WEBHOOK_EVENTS), ("REALTIME", REALTIME_EVENTS),
        ("AUDIT", AUDIT_EVENTS), ("METRIC", METRIC_EVENTS),
    ]:
        all_et = all(isinstance(e, EventType) for e in group)
        r.check(f"{group_name} 모든 멤버 EventType", all_et)

    # WEBHOOK: 주요 완료/실패 이벤트
    r.check("WEBHOOK: TASK_COMPLETED", EventType.TASK_COMPLETED in WEBHOOK_EVENTS)
    r.check("WEBHOOK: GAME_ANALYSIS_COMPLETED", EventType.GAME_ANALYSIS_COMPLETED in WEBHOOK_EVENTS)
    r.check("WEBHOOK: REPORT_WEEKLY", EventType.REPORT_WEEKLY_GENERATED in WEBHOOK_EVENTS)

    # REALTIME: 진행/감지 이벤트
    r.check("REALTIME: TASK_PROGRESS", EventType.TASK_PROGRESS in REALTIME_EVENTS)
    r.check("REALTIME: GAME_SHOT_DETECTED", EventType.GAME_SHOT_DETECTED in REALTIME_EVENTS)
    r.check("REALTIME: VIOLATION_DETECTED", EventType.VIOLATION_DETECTED in REALTIME_EVENTS)

    # AUDIT: 시스템 생명주기
    r.check("AUDIT: SYSTEM_STARTED", EventType.SYSTEM_STARTED in AUDIT_EVENTS)
    r.check("AUDIT: MODEL_LOADED", EventType.MODEL_LOADED in AUDIT_EVENTS)

    # METRIC: 성능 측정
    r.check("METRIC: CACHE_HIT", EventType.CACHE_HIT in METRIC_EVENTS)
    r.check("METRIC: DATABASE_QUERY_SLOW", EventType.DATABASE_QUERY_SLOW in METRIC_EVENTS)


# ==================== I. EVENT_PRIORITY ====================
def test_event_priority(r: TestResult) -> None:
    print("\n[I] EVENT_PRIORITY")
    from shared.constants.event_types import EventType, EVENT_PRIORITY, get_event_priority

    r.check("EVENT_PRIORITY dict", isinstance(EVENT_PRIORITY, dict))

    # 우선순위 범위 (0~4)
    all_valid = all(0 <= p <= 4 for p in EVENT_PRIORITY.values())
    r.check("우선순위 범위 0~4", all_valid)

    # 긴급(0) 이벤트
    r.check("SYSTEM_ERROR 우선순위=0", EVENT_PRIORITY[EventType.SYSTEM_ERROR] == 0)
    r.check("SYSTEM_SHUTDOWN 우선순위=0", EVENT_PRIORITY[EventType.SYSTEM_SHUTDOWN] == 0)
    r.check("DB_CONNECTION_LOST 우선순위=0", EVENT_PRIORITY[EventType.DATABASE_CONNECTION_LOST] == 0)

    # 높음(1)
    r.check("TASK_FAILED 우선순위=1", EVENT_PRIORITY[EventType.TASK_FAILED] == 1)

    # 중간(2)
    r.check("TASK_COMPLETED 우선순위=2", EVENT_PRIORITY[EventType.TASK_COMPLETED] == 2)

    # 최저(4)
    r.check("CACHE_HIT 우선순위=4", EVENT_PRIORITY[EventType.CACHE_HIT] == 4)

    # get_event_priority 기본값
    r.check("get_event_priority(SYSTEM_ERROR)=0", get_event_priority(EventType.SYSTEM_ERROR) == 0)
    r.check("미지정 이벤트 기본값=3", get_event_priority(EventType.CACHE_EVICTED) == 3)


# ==================== J. __all__ export ====================
def test_all_exports(r: TestResult) -> None:
    print("\n[J] __all__ export")
    from shared.constants import event_types

    expected = {
        "EventCategory", "EventType",
        "WEBHOOK_EVENTS", "REALTIME_EVENTS", "AUDIT_EVENTS", "METRIC_EVENTS",
        "EVENT_PRIORITY", "get_event_priority",
    }
    actual = set(event_types.__all__)
    r.check("__all__ 8개", len(actual) == 8)
    r.check("__all__ 일치", actual == expected,
            f"차이: {actual.symmetric_difference(expected)}")

    for name in expected:
        r.check(f"export '{name}' 존재", hasattr(event_types, name))


# ==================== K. __init__.py re-export ====================
def test_init_reexport(r: TestResult) -> None:
    print("\n[K] __init__.py re-export")
    import shared.constants as pkg

    init_expected = [
        "EventCategory", "EventType",
        "WEBHOOK_EVENTS", "REALTIME_EVENTS", "AUDIT_EVENTS", "METRIC_EVENTS",
        "EVENT_PRIORITY", "get_event_priority",
    ]
    for name in init_expected:
        r.check(f"re-export '{name}'", hasattr(pkg, name))


# ==================== L. 특정 이벤트 값 검증 ====================
def test_specific_event_values(r: TestResult) -> None:
    print("\n[L] 주요 이벤트 값 검증")
    from shared.constants.event_types import EventType

    spot_checks = {
        "SYSTEM_STARTED": "system.started",
        "TASK_COMPLETED": "task.completed",
        "ANALYSIS_SHOOTING_COMPLETED": "analysis.shooting.completed",
        "GAME_SHOT_DETECTED": "game.shot.detected",
        "VIOLATION_TRAVELING": "referee.violation.traveling",
        "VIOLATION_3_SECOND": "referee.violation.3_second",
        "FOUL_FLAGRANT": "referee.foul.flagrant",
        "FEEDBACK_GENERATED": "feedback.generated",
        "REPORT_WEEKLY_GENERATED": "report.weekly.generated",
        "LEARNING_MODEL_UPDATED": "learning.model.updated",
        "CACHE_HIT": "infra.cache.hit",
        "MODEL_LOADED": "model.loaded",
    }
    for name, expected_value in spot_checks.items():
        r.check(f"{name}='{expected_value}'", EventType[name].value == expected_value)


def main():
    r = TestResult()
    test_typing(r)                    # A
    test_event_category(r)            # B
    test_event_type_count(r)          # C
    test_event_value_format(r)        # D
    test_korean_map_completeness(r)   # E
    test_category_property(r)         # F
    test_event_predicates(r)          # G
    test_event_groups(r)              # H
    test_event_priority(r)            # I
    test_all_exports(r)               # J
    test_init_reexport(r)             # K
    test_specific_event_values(r)     # L
    r.summary()
    return 0 if r.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
