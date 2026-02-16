# -*- coding: utf-8 -*-
"""status_codes.py v1.1.0 검증 테스트"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0


def check(name, condition, msg=""):
    global passed, failed
    if condition:
        print(f"[PASS] {name}")
        passed += 1
    else:
        print(f"[FAIL] {name} - {msg}")
        failed += 1


print("=" * 70)
print("status_codes.py v1.1.0 검증 테스트")
print("=" * 70)

# T-01: 모듈 임포트
try:
    from shared.constants.status_codes import (
        TaskStatus, AnalysisType, AnalysisPhase,
        ServiceStatus, QueuePriority, Environment,
        QualityLevel, TaskType, LearningStatus,
        VALID_TASK_TRANSITIONS, is_valid_transition,
    )
    check("T-01: 모듈 임포트", True)
except Exception as e:
    check("T-01: 모듈 임포트", False, str(e))
    sys.exit(1)

# T-02: __init__.py 호환성
try:
    from shared.constants import (
        TaskStatus, AnalysisType, AnalysisPhase,
        ServiceStatus, QueuePriority, Environment,
        QualityLevel, TaskType, LearningStatus,
        VALID_TASK_TRANSITIONS, is_valid_transition,
    )
    check("T-02: __init__.py 호환성", True)
except Exception as e:
    check("T-02: __init__.py 호환성", False, str(e))

# T-03: TaskStatus 15 멤버
check(
    "T-03: TaskStatus 15 멤버",
    len(TaskStatus) == 15,
    f"실제: {len(TaskStatus)}",
)

# T-04: AnalysisType 15 멤버
check(
    "T-04: AnalysisType 15 멤버",
    len(AnalysisType) == 15,
    f"실제: {len(AnalysisType)}",
)

# T-05: AnalysisPhase 11 멤버
check(
    "T-05: AnalysisPhase 11 멤버",
    len(AnalysisPhase) == 11,
    f"실제: {len(AnalysisPhase)}",
)

# T-06: ServiceStatus 8 멤버
check(
    "T-06: ServiceStatus 8 멤버",
    len(ServiceStatus) == 8,
    f"실제: {len(ServiceStatus)}",
)

# T-07: QueuePriority 5 멤버
check(
    "T-07: QueuePriority 5 멤버",
    len(QueuePriority) == 5,
    f"실제: {len(QueuePriority)}",
)

# T-08: Environment 4 멤버
check(
    "T-08: Environment 4 멤버",
    len(Environment) == 4,
    f"실제: {len(Environment)}",
)

# T-09: QualityLevel 5 멤버
check(
    "T-09: QualityLevel 5 멤버",
    len(QualityLevel) == 5,
    f"실제: {len(QualityLevel)}",
)

# T-10: TaskType 15 멤버
check(
    "T-10: TaskType 15 멤버",
    len(TaskType) == 15,
    f"실제: {len(TaskType)}",
)

# T-11: LearningStatus 13 멤버
check(
    "T-11: LearningStatus 13 멤버",
    len(LearningStatus) == 13,
    f"실제: {len(LearningStatus)}",
)

# T-12: TaskStatus.is_terminal
check(
    "T-12: TaskStatus.is_terminal",
    TaskStatus.COMPLETED.is_terminal is True
    and TaskStatus.FAILED.is_terminal is True
    and TaskStatus.CANCELLED.is_terminal is True
    and TaskStatus.RUNNING.is_terminal is False
    and TaskStatus.PENDING.is_terminal is False,
)

# T-13: TaskStatus.is_success
check(
    "T-13: TaskStatus.is_success",
    TaskStatus.COMPLETED.is_success is True
    and TaskStatus.SUCCESS.is_success is True
    and TaskStatus.FAILED.is_success is False,
)

# T-14: TaskStatus.is_failure
check(
    "T-14: TaskStatus.is_failure",
    TaskStatus.FAILED.is_failure is True
    and TaskStatus.ERROR.is_failure is True
    and TaskStatus.TIMEOUT.is_failure is True
    and TaskStatus.COMPLETED.is_failure is False,
)

# T-15: TaskStatus.is_running
check(
    "T-15: TaskStatus.is_running",
    TaskStatus.RUNNING.is_running is True
    and TaskStatus.PROCESSING.is_running is True
    and TaskStatus.STARTED.is_running is True
    and TaskStatus.RETRYING.is_running is True
    and TaskStatus.PENDING.is_running is False,
)

# T-16: TaskStatus.is_pending
check(
    "T-16: TaskStatus.is_pending",
    TaskStatus.PENDING.is_pending is True
    and TaskStatus.QUEUED.is_pending is True
    and TaskStatus.SCHEDULED.is_pending is True
    and TaskStatus.RETRY.is_pending is True
    and TaskStatus.RUNNING.is_pending is False,
)

# T-17: TaskStatus.to_korean
check(
    "T-17: TaskStatus.to_korean",
    TaskStatus.PENDING.to_korean() == "대기 중"
    and TaskStatus.RUNNING.to_korean() == "실행 중"
    and TaskStatus.COMPLETED.to_korean() == "완료"
    and TaskStatus.FAILED.to_korean() == "실패"
    and all(isinstance(s.to_korean(), str) and len(s.to_korean()) > 0 for s in TaskStatus),
)

# T-18: AnalysisType.category
check(
    "T-18: AnalysisType.category",
    AnalysisType.TRAINING_SHOOTING.category == "training"
    and AnalysisType.GAME_FULL.category == "game"
    and AnalysisType.REFEREE_FULL.category == "referee"
    and AnalysisType.REPORT_WEEKLY.category == "report",
)

# T-19: AnalysisType.to_korean
check(
    "T-19: AnalysisType.to_korean",
    AnalysisType.TRAINING_SHOOTING.to_korean() == "슈팅 훈련 분석"
    and AnalysisType.GAME_FULL.to_korean() == "전체 경기 분석"
    and all(isinstance(a.to_korean(), str) and len(a.to_korean()) > 0 for a in AnalysisType),
)

# T-20: AnalysisPhase.progress_percent 단조 증가
phases = list(AnalysisPhase)
progress_values = [p.progress_percent for p in phases]
check(
    "T-20: AnalysisPhase.progress_percent 단조 증가",
    all(progress_values[i] <= progress_values[i + 1] for i in range(len(progress_values) - 1))
    and progress_values[0] == 0
    and progress_values[-1] == 100,
)

# T-21: AnalysisPhase.to_korean
check(
    "T-21: AnalysisPhase.to_korean",
    AnalysisPhase.INITIALIZED.to_korean() == "초기화"
    and AnalysisPhase.DONE.to_korean() == "완료"
    and all(isinstance(p.to_korean(), str) and len(p.to_korean()) > 0 for p in AnalysisPhase),
)

# T-22: ServiceStatus.is_available
check(
    "T-22: ServiceStatus.is_available",
    ServiceStatus.HEALTHY.is_available is True
    and ServiceStatus.DEGRADED.is_available is True
    and ServiceStatus.UNHEALTHY.is_available is False
    and ServiceStatus.STOPPED.is_available is False,
)

# T-23: ServiceStatus.is_healthy
check(
    "T-23: ServiceStatus.is_healthy",
    ServiceStatus.HEALTHY.is_healthy is True
    and ServiceStatus.DEGRADED.is_healthy is False
    and all(isinstance(s.to_korean(), str) for s in ServiceStatus),
)

# T-24: QueuePriority 정수값 순서
check(
    "T-24: QueuePriority 정수값 순서",
    QueuePriority.CRITICAL.value == 0
    and QueuePriority.HIGH.value == 1
    and QueuePriority.NORMAL.value == 2
    and QueuePriority.LOW.value == 3
    and QueuePriority.BACKGROUND.value == 4,
)

# T-25: Environment 프로퍼티
check(
    "T-25: Environment 프로퍼티",
    Environment.PRODUCTION.is_production is True
    and Environment.DEVELOPMENT.is_development is True
    and Environment.TESTING.is_testing is True
    and Environment.STAGING.is_production is False,
)

# T-26: QualityLevel.from_score
check(
    "T-26: QualityLevel.from_score",
    QualityLevel.from_score(95) == QualityLevel.EXCELLENT
    and QualityLevel.from_score(80) == QualityLevel.GOOD
    and QualityLevel.from_score(65) == QualityLevel.ACCEPTABLE
    and QualityLevel.from_score(50) == QualityLevel.POOR
    and QualityLevel.from_score(20) == QualityLevel.UNACCEPTABLE,
)

# T-27: QualityLevel.from_score ValueError
try:
    QualityLevel.from_score(101)
    check("T-27: QualityLevel.from_score ValueError", False, "예외 미발생")
except ValueError:
    check("T-27: QualityLevel.from_score ValueError", True)

# T-28: QualityLevel.is_usable
check(
    "T-28: QualityLevel.is_usable",
    QualityLevel.EXCELLENT.is_usable is True
    and QualityLevel.GOOD.is_usable is True
    and QualityLevel.ACCEPTABLE.is_usable is True
    and QualityLevel.POOR.is_usable is False
    and QualityLevel.UNACCEPTABLE.is_usable is False,
)

# T-29: QualityLevel.min_score/max_score 비중첩
levels = list(QualityLevel)
check(
    "T-29: QualityLevel 점수 범위",
    all(ql.min_score <= ql.max_score for ql in levels),
)

# T-30: TaskType.is_analysis / is_report / is_learning
check(
    "T-30: TaskType 분류 프로퍼티",
    TaskType.ANALYSIS_TRAINING.is_analysis is True
    and TaskType.ANALYSIS_GAME.is_analysis is True
    and TaskType.REPORT_WEEKLY.is_report is True
    and TaskType.LEARNING_TRAINING.is_learning is True
    and TaskType.VIDEO_PROCESSING.is_analysis is False
    and TaskType.VIDEO_PROCESSING.is_report is False
    and TaskType.VIDEO_PROCESSING.is_learning is False,
)

# T-31: LearningStatus.is_active
check(
    "T-31: LearningStatus.is_active",
    LearningStatus.TRAINING.is_active is True
    and LearningStatus.VALIDATING.is_active is True
    and LearningStatus.IDLE.is_active is False
    and LearningStatus.COMPLETED.is_active is False,
)

# T-32: LearningStatus.is_terminal
check(
    "T-32: LearningStatus.is_terminal",
    LearningStatus.COMPLETED.is_terminal is True
    and LearningStatus.FAILED.is_terminal is True
    and LearningStatus.DEPLOYED.is_terminal is True
    and LearningStatus.TRAINING.is_terminal is False,
)

# T-33: LearningStatus.can_trigger_learning
check(
    "T-33: LearningStatus.can_trigger_learning",
    LearningStatus.IDLE.can_trigger_learning is True
    and LearningStatus.READY.can_trigger_learning is True
    and LearningStatus.COMPLETED.can_trigger_learning is True
    and LearningStatus.TRAINING.can_trigger_learning is False
    and LearningStatus.VALIDATING.can_trigger_learning is False,
)

# T-34: VALID_TASK_TRANSITIONS 완전성
check(
    "T-34: VALID_TASK_TRANSITIONS 완전성",
    len(VALID_TASK_TRANSITIONS) == len(TaskStatus),
    f"전이 규칙 수: {len(VALID_TASK_TRANSITIONS)}, TaskStatus 멤버 수: {len(TaskStatus)}",
)

# T-35: is_valid_transition 함수
check(
    "T-35: is_valid_transition",
    is_valid_transition(TaskStatus.PENDING, TaskStatus.QUEUED) is True
    and is_valid_transition(TaskStatus.RUNNING, TaskStatus.COMPLETED) is True
    and is_valid_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING) is False
    and is_valid_transition(TaskStatus.FAILED, TaskStatus.RETRY) is True,
)

# T-36: 종료 상태는 전이 없음
terminal_empty = all(
    len(VALID_TASK_TRANSITIONS.get(s, ())) == 0
    for s in [TaskStatus.COMPLETED, TaskStatus.SUCCESS, TaskStatus.CANCELLED,
              TaskStatus.REVOKED, TaskStatus.ERROR]
)
check("T-36: 종료 상태 전이 없음", terminal_empty)

# T-37: __all__ 개수 및 존재 확인
import shared.constants.status_codes as sc
all_list = sc.__all__
all_exist = all(hasattr(sc, name) for name in all_list)
check(
    f"T-37: __all__ {len(all_list)}개 항목 모두 존재",
    all_exist and len(all_list) == 11,
    f"개수: {len(all_list)}, 존재: {all_exist}",
)

# T-38: 빈 선언 패턴 없음
import inspect
source = inspect.getsource(sc)
check(
    "T-38: 빈 선언 패턴 없음",
    "= {}" not in source
    and "= frozenset()" not in source,
)

# T-39: 버전 검증
check("T-39: 버전 1.1.0", sc.__version__ == "1.1.0", f"실제: {sc.__version__}")

# T-40: typing 모던화 검증
check(
    "T-40: typing 모던화",
    "Dict[" not in source
    and "Tuple[" not in source,
)

print()
print("=" * 70)
print(f"결과: {passed}/{passed + failed} PASS | {failed} FAIL")
print("=" * 70)

if failed > 0:
    sys.exit(1)
