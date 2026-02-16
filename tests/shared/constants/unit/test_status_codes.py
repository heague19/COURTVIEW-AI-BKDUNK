# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_status_codes.py

시스템 상태 코드 상수 모듈 유닛 테스트 (status_codes.py v1.1.0)
- TaskStatus (15): 멤버, is_terminal, is_success, is_failure, is_running, is_pending, to_korean
- AnalysisType (15): 멤버, category (lru_cache), to_korean
- AnalysisPhase (11): 멤버, progress_percent (단조 증가), to_korean
- ServiceStatus (8): 멤버, is_available, is_healthy, to_korean
- QueuePriority (5): 멤버, 정수 값, to_korean
- Environment (4): 멤버, is_production, is_development, is_testing, to_korean
- QualityLevel (5): 멤버, from_score 경계값, min_score/max_score, is_usable, description
- TaskType (15): 멤버, is_analysis, is_report, is_learning, to_korean
- LearningStatus (13): 멤버, is_active, is_terminal, can_trigger_learning, to_korean
- VALID_TASK_TRANSITIONS: 완전성, 터미널 빈 튜플, 특정 전이 검증
- is_valid_transition: 유효/무효 전이 테스트
- __all__: 완전성 (11개 항목)
- 캐시: frozenset 13개, dict 12개
- 메타: 버전, typing modernization
- 에지 케이스, 상호 배타성

Author: COURTVIEW AI Team
Version: 2.0.0
"""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.current_section = ""

    def set_section(self, name):
        self.current_section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name, msg=""):
        self.failed += 1
        self.errors.append(f"[{self.current_section}] {name}: {msg}")
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
        if self.errors:
            print(f"\n  Errors:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")
        return self.failed == 0


# =============================================================================
# 섹션 1: TaskStatus 멤버 검증
# =============================================================================
def test_task_status_members(r: TestResult) -> None:
    r.set_section("1. TaskStatus 멤버 검증")
    from shared.constants.status_codes import TaskStatus

    expected_members = [
        "PENDING", "QUEUED", "SCHEDULED",
        "STARTED", "RUNNING", "PROCESSING",
        "COMPLETED", "SUCCESS",
        "FAILED", "ERROR", "TIMEOUT",
        "CANCELLED", "REVOKED",
        "RETRY", "RETRYING",
    ]

    r.check("TaskStatus 멤버 수 = 15", len(TaskStatus) == 15,
            f"실제: {len(TaskStatus)}")

    for name in expected_members:
        r.check(f"TaskStatus.{name} 존재", hasattr(TaskStatus, name))

    # 값 검증
    expected_values = {
        "PENDING": "pending", "QUEUED": "queued", "SCHEDULED": "scheduled",
        "STARTED": "started", "RUNNING": "running", "PROCESSING": "processing",
        "COMPLETED": "completed", "SUCCESS": "success",
        "FAILED": "failed", "ERROR": "error", "TIMEOUT": "timeout",
        "CANCELLED": "cancelled", "REVOKED": "revoked",
        "RETRY": "retry", "RETRYING": "retrying",
    }
    for name, val in expected_values.items():
        member = getattr(TaskStatus, name)
        r.check(f"TaskStatus.{name}.value == '{val}'",
                member.value == val, f"실제: {member.value}")

    # Enum 타입 확인
    from enum import Enum
    r.check("TaskStatus는 Enum 서브클래스",
            issubclass(TaskStatus, Enum))

    # 문자열 값으로 생성
    r.check("TaskStatus('pending') == PENDING",
            TaskStatus("pending") == TaskStatus.PENDING)


# =============================================================================
# 섹션 2: TaskStatus is_terminal 검증
# =============================================================================
def test_task_status_is_terminal(r: TestResult) -> None:
    r.set_section("2. TaskStatus is_terminal 검증")
    from shared.constants.status_codes import TaskStatus

    terminal_expected = {
        TaskStatus.COMPLETED, TaskStatus.SUCCESS, TaskStatus.FAILED,
        TaskStatus.ERROR, TaskStatus.TIMEOUT, TaskStatus.CANCELLED,
        TaskStatus.REVOKED,
    }

    for member in TaskStatus:
        expected = member in terminal_expected
        r.check(f"TaskStatus.{member.name}.is_terminal == {expected}",
                member.is_terminal == expected,
                f"실제: {member.is_terminal}")


# =============================================================================
# 섹션 3: TaskStatus is_success 검증
# =============================================================================
def test_task_status_is_success(r: TestResult) -> None:
    r.set_section("3. TaskStatus is_success 검증")
    from shared.constants.status_codes import TaskStatus

    success_expected = {TaskStatus.COMPLETED, TaskStatus.SUCCESS}

    for member in TaskStatus:
        expected = member in success_expected
        r.check(f"TaskStatus.{member.name}.is_success == {expected}",
                member.is_success == expected,
                f"실제: {member.is_success}")


# =============================================================================
# 섹션 4: TaskStatus is_failure 검증
# =============================================================================
def test_task_status_is_failure(r: TestResult) -> None:
    r.set_section("4. TaskStatus is_failure 검증")
    from shared.constants.status_codes import TaskStatus

    failure_expected = {TaskStatus.FAILED, TaskStatus.ERROR, TaskStatus.TIMEOUT}

    for member in TaskStatus:
        expected = member in failure_expected
        r.check(f"TaskStatus.{member.name}.is_failure == {expected}",
                member.is_failure == expected,
                f"실제: {member.is_failure}")


# =============================================================================
# 섹션 5: TaskStatus is_running / is_pending / to_korean 검증
# =============================================================================
def test_task_status_running_pending_korean(r: TestResult) -> None:
    r.set_section("5. TaskStatus is_running / is_pending / to_korean 검증")
    from shared.constants.status_codes import TaskStatus

    running_expected = {
        TaskStatus.STARTED, TaskStatus.RUNNING,
        TaskStatus.PROCESSING, TaskStatus.RETRYING,
    }
    pending_expected = {
        TaskStatus.PENDING, TaskStatus.QUEUED,
        TaskStatus.SCHEDULED, TaskStatus.RETRY,
    }

    for member in TaskStatus:
        exp_run = member in running_expected
        r.check(f"TaskStatus.{member.name}.is_running == {exp_run}",
                member.is_running == exp_run,
                f"실제: {member.is_running}")

    for member in TaskStatus:
        exp_pend = member in pending_expected
        r.check(f"TaskStatus.{member.name}.is_pending == {exp_pend}",
                member.is_pending == exp_pend,
                f"실제: {member.is_pending}")

    # to_korean 전체 검증
    korean_map = {
        TaskStatus.PENDING: "대기 중",
        TaskStatus.QUEUED: "큐 등록됨",
        TaskStatus.SCHEDULED: "예약됨",
        TaskStatus.STARTED: "시작됨",
        TaskStatus.RUNNING: "실행 중",
        TaskStatus.PROCESSING: "처리 중",
        TaskStatus.COMPLETED: "완료",
        TaskStatus.SUCCESS: "성공",
        TaskStatus.FAILED: "실패",
        TaskStatus.ERROR: "오류",
        TaskStatus.TIMEOUT: "시간 초과",
        TaskStatus.CANCELLED: "취소됨",
        TaskStatus.REVOKED: "취소됨",
        TaskStatus.RETRY: "재시도 대기",
        TaskStatus.RETRYING: "재시도 중",
    }
    for member, kr in korean_map.items():
        r.check(f"TaskStatus.{member.name}.to_korean() == '{kr}'",
                member.to_korean() == kr,
                f"실제: '{member.to_korean()}'")

    # to_korean 반환 타입 확인
    r.check("to_korean() 반환 타입 str",
            isinstance(TaskStatus.PENDING.to_korean(), str))


# =============================================================================
# 섹션 6: AnalysisType 멤버 및 카테고리 검증
# =============================================================================
def test_analysis_type_members_category(r: TestResult) -> None:
    r.set_section("6. AnalysisType 멤버 및 카테고리 검증")
    from shared.constants.status_codes import AnalysisType

    r.check("AnalysisType 멤버 수 = 15", len(AnalysisType) == 15,
            f"실제: {len(AnalysisType)}")

    expected_members = [
        "TRAINING_SHOOTING", "TRAINING_DRIBBLING", "TRAINING_PASSING",
        "TRAINING_DEFENSE", "TRAINING_MOVEMENT", "TRAINING_COMPARISON",
        "GAME_FULL", "GAME_HIGHLIGHTS", "GAME_STATISTICS", "GAME_SHOT_CHART",
        "REFEREE_FULL", "REFEREE_VIOLATION", "REFEREE_FOUL",
        "REPORT_WEEKLY", "REPORT_PROGRESS",
    ]
    for name in expected_members:
        r.check(f"AnalysisType.{name} 존재", hasattr(AnalysisType, name))

    # 카테고리 검증 - training (6개)
    training_members = [
        AnalysisType.TRAINING_SHOOTING, AnalysisType.TRAINING_DRIBBLING,
        AnalysisType.TRAINING_PASSING, AnalysisType.TRAINING_DEFENSE,
        AnalysisType.TRAINING_MOVEMENT, AnalysisType.TRAINING_COMPARISON,
    ]
    for m in training_members:
        r.check(f"AnalysisType.{m.name}.category == 'training'",
                m.category == "training",
                f"실제: '{m.category}'")

    # 카테고리 검증 - game (4개)
    game_members = [
        AnalysisType.GAME_FULL, AnalysisType.GAME_HIGHLIGHTS,
        AnalysisType.GAME_STATISTICS, AnalysisType.GAME_SHOT_CHART,
    ]
    for m in game_members:
        r.check(f"AnalysisType.{m.name}.category == 'game'",
                m.category == "game",
                f"실제: '{m.category}'")

    # 카테고리 검증 - referee (3개)
    referee_members = [
        AnalysisType.REFEREE_FULL, AnalysisType.REFEREE_VIOLATION,
        AnalysisType.REFEREE_FOUL,
    ]
    for m in referee_members:
        r.check(f"AnalysisType.{m.name}.category == 'referee'",
                m.category == "referee",
                f"실제: '{m.category}'")

    # 카테고리 검증 - report (2개)
    report_members = [
        AnalysisType.REPORT_WEEKLY, AnalysisType.REPORT_PROGRESS,
    ]
    for m in report_members:
        r.check(f"AnalysisType.{m.name}.category == 'report'",
                m.category == "report",
                f"실제: '{m.category}'")

    # 카테고리 분포: 6 + 4 + 3 + 2 = 15
    category_counts = {}
    for m in AnalysisType:
        cat = m.category
        category_counts[cat] = category_counts.get(cat, 0) + 1
    r.check("training 카테고리 6개", category_counts.get("training", 0) == 6,
            f"실제: {category_counts.get('training', 0)}")
    r.check("game 카테고리 4개", category_counts.get("game", 0) == 4,
            f"실제: {category_counts.get('game', 0)}")
    r.check("referee 카테고리 3개", category_counts.get("referee", 0) == 3,
            f"실제: {category_counts.get('referee', 0)}")
    r.check("report 카테고리 2개", category_counts.get("report", 0) == 2,
            f"실제: {category_counts.get('report', 0)}")


# =============================================================================
# 섹션 7: AnalysisType to_korean 검증
# =============================================================================
def test_analysis_type_korean(r: TestResult) -> None:
    r.set_section("7. AnalysisType to_korean 검증")
    from shared.constants.status_codes import AnalysisType

    korean_map = {
        AnalysisType.TRAINING_SHOOTING: "슈팅 훈련 분석",
        AnalysisType.TRAINING_DRIBBLING: "드리블 훈련 분석",
        AnalysisType.TRAINING_PASSING: "패스 훈련 분석",
        AnalysisType.TRAINING_DEFENSE: "수비 훈련 분석",
        AnalysisType.TRAINING_MOVEMENT: "이동 훈련 분석",
        AnalysisType.TRAINING_COMPARISON: "동작 비교 분석",
        AnalysisType.GAME_FULL: "전체 경기 분석",
        AnalysisType.GAME_HIGHLIGHTS: "하이라이트 추출",
        AnalysisType.GAME_STATISTICS: "경기 통계 분석",
        AnalysisType.GAME_SHOT_CHART: "슛 차트 분석",
        AnalysisType.REFEREE_FULL: "AI 심판 분석",
        AnalysisType.REFEREE_VIOLATION: "바이올레이션 감지",
        AnalysisType.REFEREE_FOUL: "파울 감지",
        AnalysisType.REPORT_WEEKLY: "주간 레포트",
        AnalysisType.REPORT_PROGRESS: "진행 추적 레포트",
    }

    for member, kr in korean_map.items():
        r.check(f"AnalysisType.{member.name}.to_korean() == '{kr}'",
                member.to_korean() == kr,
                f"실제: '{member.to_korean()}'")

    # 모든 멤버가 한글 매핑 보유
    r.check("AnalysisType 한글 매핑 수 == 멤버 수",
            len(korean_map) == len(AnalysisType),
            f"매핑: {len(korean_map)}, 멤버: {len(AnalysisType)}")


# =============================================================================
# 섹션 8: AnalysisPhase 멤버 및 progress_percent 검증
# =============================================================================
def test_analysis_phase_members_progress(r: TestResult) -> None:
    r.set_section("8. AnalysisPhase 멤버 및 progress_percent 검증")
    from shared.constants.status_codes import AnalysisPhase

    r.check("AnalysisPhase 멤버 수 = 11", len(AnalysisPhase) == 11,
            f"실제: {len(AnalysisPhase)}")

    expected_members = [
        "INITIALIZED", "DOWNLOADING", "PREPROCESSING", "DETECTING",
        "POSE_ESTIMATING", "ANALYZING", "GENERATING_FEEDBACK",
        "POSTPROCESSING", "UPLOADING", "FINALIZING", "DONE",
    ]
    for name in expected_members:
        r.check(f"AnalysisPhase.{name} 존재", hasattr(AnalysisPhase, name))

    # 정확한 progress_percent 값 검증
    expected_progress = {
        AnalysisPhase.INITIALIZED: 0,
        AnalysisPhase.DOWNLOADING: 5,
        AnalysisPhase.PREPROCESSING: 15,
        AnalysisPhase.DETECTING: 30,
        AnalysisPhase.POSE_ESTIMATING: 45,
        AnalysisPhase.ANALYZING: 65,
        AnalysisPhase.GENERATING_FEEDBACK: 80,
        AnalysisPhase.POSTPROCESSING: 90,
        AnalysisPhase.UPLOADING: 95,
        AnalysisPhase.FINALIZING: 98,
        AnalysisPhase.DONE: 100,
    }

    for phase, pct in expected_progress.items():
        r.check(f"AnalysisPhase.{phase.name}.progress_percent == {pct}",
                phase.progress_percent == pct,
                f"실제: {phase.progress_percent}")

    # 단조 증가(monotonically increasing) 검증
    phases_ordered = list(AnalysisPhase)
    for i in range(1, len(phases_ordered)):
        prev_pct = phases_ordered[i - 1].progress_percent
        curr_pct = phases_ordered[i].progress_percent
        r.check(
            f"단조증가: {phases_ordered[i-1].name}({prev_pct}) < {phases_ordered[i].name}({curr_pct})",
            prev_pct < curr_pct,
            f"{prev_pct} >= {curr_pct}"
        )

    # 범위 검증: 0 ~ 100
    r.check("INITIALIZED.progress_percent == 0",
            AnalysisPhase.INITIALIZED.progress_percent == 0)
    r.check("DONE.progress_percent == 100",
            AnalysisPhase.DONE.progress_percent == 100)

    for phase in AnalysisPhase:
        pct = phase.progress_percent
        r.check(f"AnalysisPhase.{phase.name}.progress_percent 범위 0-100",
                0 <= pct <= 100, f"실제: {pct}")


# =============================================================================
# 섹션 9: AnalysisPhase to_korean 검증
# =============================================================================
def test_analysis_phase_korean(r: TestResult) -> None:
    r.set_section("9. AnalysisPhase to_korean 검증")
    from shared.constants.status_codes import AnalysisPhase

    korean_map = {
        AnalysisPhase.INITIALIZED: "초기화",
        AnalysisPhase.DOWNLOADING: "영상 다운로드",
        AnalysisPhase.PREPROCESSING: "전처리",
        AnalysisPhase.DETECTING: "객체 감지",
        AnalysisPhase.POSE_ESTIMATING: "포즈 추정",
        AnalysisPhase.ANALYZING: "분석",
        AnalysisPhase.GENERATING_FEEDBACK: "피드백 생성",
        AnalysisPhase.POSTPROCESSING: "후처리",
        AnalysisPhase.UPLOADING: "결과 업로드",
        AnalysisPhase.FINALIZING: "마무리",
        AnalysisPhase.DONE: "완료",
    }

    for phase, kr in korean_map.items():
        r.check(f"AnalysisPhase.{phase.name}.to_korean() == '{kr}'",
                phase.to_korean() == kr,
                f"실제: '{phase.to_korean()}'")

    r.check("AnalysisPhase 한글 매핑 수 == 멤버 수",
            len(korean_map) == len(AnalysisPhase))


# =============================================================================
# 섹션 10: ServiceStatus 멤버, is_available, is_healthy 검증
# =============================================================================
def test_service_status_members(r: TestResult) -> None:
    r.set_section("10. ServiceStatus 멤버, is_available, is_healthy 검증")
    from shared.constants.status_codes import ServiceStatus

    r.check("ServiceStatus 멤버 수 = 8", len(ServiceStatus) == 8,
            f"실제: {len(ServiceStatus)}")

    expected_members = [
        "UNKNOWN", "STARTING", "HEALTHY", "DEGRADED",
        "UNHEALTHY", "STOPPING", "STOPPED", "MAINTENANCE",
    ]
    for name in expected_members:
        r.check(f"ServiceStatus.{name} 존재", hasattr(ServiceStatus, name))

    # is_available 검증
    available_expected = {ServiceStatus.HEALTHY, ServiceStatus.DEGRADED}
    for member in ServiceStatus:
        exp = member in available_expected
        r.check(f"ServiceStatus.{member.name}.is_available == {exp}",
                member.is_available == exp,
                f"실제: {member.is_available}")

    # is_healthy 검증 - 오직 HEALTHY만 True
    for member in ServiceStatus:
        exp = (member == ServiceStatus.HEALTHY)
        r.check(f"ServiceStatus.{member.name}.is_healthy == {exp}",
                member.is_healthy == exp,
                f"실제: {member.is_healthy}")


# =============================================================================
# 섹션 11: ServiceStatus to_korean 검증
# =============================================================================
def test_service_status_korean(r: TestResult) -> None:
    r.set_section("11. ServiceStatus to_korean 검증")
    from shared.constants.status_codes import ServiceStatus

    korean_map = {
        ServiceStatus.UNKNOWN: "알 수 없음",
        ServiceStatus.STARTING: "시작 중",
        ServiceStatus.HEALTHY: "정상",
        ServiceStatus.DEGRADED: "성능 저하",
        ServiceStatus.UNHEALTHY: "비정상",
        ServiceStatus.STOPPING: "종료 중",
        ServiceStatus.STOPPED: "종료됨",
        ServiceStatus.MAINTENANCE: "유지보수 중",
    }

    for member, kr in korean_map.items():
        r.check(f"ServiceStatus.{member.name}.to_korean() == '{kr}'",
                member.to_korean() == kr,
                f"실제: '{member.to_korean()}'")

    r.check("ServiceStatus 한글 매핑 수 == 멤버 수",
            len(korean_map) == len(ServiceStatus))


# =============================================================================
# 섹션 12: QueuePriority 멤버 및 정수 값 검증
# =============================================================================
def test_queue_priority_members(r: TestResult) -> None:
    r.set_section("12. QueuePriority 멤버 및 정수 값 검증")
    from shared.constants.status_codes import QueuePriority

    r.check("QueuePriority 멤버 수 = 5", len(QueuePriority) == 5,
            f"실제: {len(QueuePriority)}")

    expected_values = {
        "CRITICAL": 0,
        "HIGH": 1,
        "NORMAL": 2,
        "LOW": 3,
        "BACKGROUND": 4,
    }

    for name, val in expected_values.items():
        member = getattr(QueuePriority, name)
        r.check(f"QueuePriority.{name}.value == {val}",
                member.value == val, f"실제: {member.value}")

    # 정수 값 타입 확인
    for member in QueuePriority:
        r.check(f"QueuePriority.{member.name}.value는 int",
                isinstance(member.value, int),
                f"타입: {type(member.value)}")

    # 우선순위 순서: CRITICAL(0) < HIGH(1) < NORMAL(2) < LOW(3) < BACKGROUND(4)
    members = list(QueuePriority)
    for i in range(1, len(members)):
        r.check(
            f"우선순위 순서: {members[i-1].name}({members[i-1].value}) < {members[i].name}({members[i].value})",
            members[i - 1].value < members[i].value,
        )


# =============================================================================
# 섹션 13: QueuePriority to_korean 검증
# =============================================================================
def test_queue_priority_korean(r: TestResult) -> None:
    r.set_section("13. QueuePriority to_korean 검증")
    from shared.constants.status_codes import QueuePriority

    korean_map = {
        QueuePriority.CRITICAL: "긴급",
        QueuePriority.HIGH: "높음",
        QueuePriority.NORMAL: "보통",
        QueuePriority.LOW: "낮음",
        QueuePriority.BACKGROUND: "백그라운드",
    }

    for member, kr in korean_map.items():
        r.check(f"QueuePriority.{member.name}.to_korean() == '{kr}'",
                member.to_korean() == kr,
                f"실제: '{member.to_korean()}'")

    r.check("QueuePriority 한글 매핑 수 == 멤버 수",
            len(korean_map) == len(QueuePriority))


# =============================================================================
# 섹션 14: Environment 멤버 및 불리언 속성 검증
# =============================================================================
def test_environment_members(r: TestResult) -> None:
    r.set_section("14. Environment 멤버 및 불리언 속성 검증")
    from shared.constants.status_codes import Environment

    r.check("Environment 멤버 수 = 4", len(Environment) == 4,
            f"실제: {len(Environment)}")

    expected_members = ["DEVELOPMENT", "STAGING", "PRODUCTION", "TESTING"]
    for name in expected_members:
        r.check(f"Environment.{name} 존재", hasattr(Environment, name))

    # is_production 검증 - 모든 멤버
    for member in Environment:
        exp = (member == Environment.PRODUCTION)
        r.check(f"Environment.{member.name}.is_production == {exp}",
                member.is_production == exp,
                f"실제: {member.is_production}")

    # is_development 검증 - 모든 멤버
    for member in Environment:
        exp = (member == Environment.DEVELOPMENT)
        r.check(f"Environment.{member.name}.is_development == {exp}",
                member.is_development == exp,
                f"실제: {member.is_development}")

    # is_testing 검증 - 모든 멤버
    for member in Environment:
        exp = (member == Environment.TESTING)
        r.check(f"Environment.{member.name}.is_testing == {exp}",
                member.is_testing == exp,
                f"실제: {member.is_testing}")


# =============================================================================
# 섹션 15: Environment to_korean 검증
# =============================================================================
def test_environment_korean(r: TestResult) -> None:
    r.set_section("15. Environment to_korean 검증")
    from shared.constants.status_codes import Environment

    korean_map = {
        Environment.DEVELOPMENT: "개발",
        Environment.STAGING: "스테이징",
        Environment.PRODUCTION: "프로덕션",
        Environment.TESTING: "테스트",
    }

    for member, kr in korean_map.items():
        r.check(f"Environment.{member.name}.to_korean() == '{kr}'",
                member.to_korean() == kr,
                f"실제: '{member.to_korean()}'")

    r.check("Environment 한글 매핑 수 == 멤버 수",
            len(korean_map) == len(Environment))


# =============================================================================
# 섹션 16: QualityLevel 멤버 검증
# =============================================================================
def test_quality_level_members(r: TestResult) -> None:
    r.set_section("16. QualityLevel 멤버 검증")
    from shared.constants.status_codes import QualityLevel

    r.check("QualityLevel 멤버 수 = 5", len(QualityLevel) == 5,
            f"실제: {len(QualityLevel)}")

    expected = ["EXCELLENT", "GOOD", "ACCEPTABLE", "POOR", "UNACCEPTABLE"]
    for name in expected:
        r.check(f"QualityLevel.{name} 존재", hasattr(QualityLevel, name))

    expected_values = {
        "EXCELLENT": "excellent",
        "GOOD": "good",
        "ACCEPTABLE": "acceptable",
        "POOR": "poor",
        "UNACCEPTABLE": "unacceptable",
    }
    for name, val in expected_values.items():
        member = getattr(QualityLevel, name)
        r.check(f"QualityLevel.{name}.value == '{val}'",
                member.value == val, f"실제: {member.value}")


# =============================================================================
# 섹션 17: QualityLevel from_score 경계값 테스트
# =============================================================================
def test_quality_level_from_score(r: TestResult) -> None:
    r.set_section("17. QualityLevel from_score 경계값 테스트")
    from shared.constants.status_codes import QualityLevel

    # 정확한 경계값 검증
    boundary_tests = [
        (100.0, QualityLevel.EXCELLENT, "100 -> EXCELLENT"),
        (90.0, QualityLevel.EXCELLENT, "90 -> EXCELLENT"),
        (95.5, QualityLevel.EXCELLENT, "95.5 -> EXCELLENT"),
        (89.9, QualityLevel.GOOD, "89.9 -> GOOD"),
        (89.0, QualityLevel.GOOD, "89 -> GOOD"),
        (75.0, QualityLevel.GOOD, "75 -> GOOD"),
        (74.9, QualityLevel.ACCEPTABLE, "74.9 -> ACCEPTABLE"),
        (74.0, QualityLevel.ACCEPTABLE, "74 -> ACCEPTABLE"),
        (60.0, QualityLevel.ACCEPTABLE, "60 -> ACCEPTABLE"),
        (59.9, QualityLevel.POOR, "59.9 -> POOR"),
        (59.0, QualityLevel.POOR, "59 -> POOR"),
        (40.0, QualityLevel.POOR, "40 -> POOR"),
        (39.9, QualityLevel.UNACCEPTABLE, "39.9 -> UNACCEPTABLE"),
        (39.0, QualityLevel.UNACCEPTABLE, "39 -> UNACCEPTABLE"),
        (0.0, QualityLevel.UNACCEPTABLE, "0 -> UNACCEPTABLE"),
        (0.1, QualityLevel.UNACCEPTABLE, "0.1 -> UNACCEPTABLE"),
        (50.0, QualityLevel.POOR, "50 -> POOR"),
    ]

    for score, expected_level, desc in boundary_tests:
        result = QualityLevel.from_score(score)
        r.check(f"from_score({desc})",
                result == expected_level,
                f"실제: {result.name}")

    # ValueError 검증: 범위 밖 값
    invalid_scores = [-1.0, -0.1, 100.1, 101.0, 200.0, -100.0]
    for score in invalid_scores:
        try:
            QualityLevel.from_score(score)
            r.fail(f"from_score({score}) ValueError 미발생", "예외 없음")
        except ValueError:
            r.ok(f"from_score({score}) ValueError 발생")
        except Exception as e:
            r.fail(f"from_score({score}) 잘못된 예외", f"{type(e).__name__}")

    # 정수 입력도 동작
    r.check("from_score(85) == GOOD (정수 입력)",
            QualityLevel.from_score(85) == QualityLevel.GOOD)


# =============================================================================
# 섹션 18: QualityLevel min_score / max_score 검증
# =============================================================================
def test_quality_level_scores(r: TestResult) -> None:
    r.set_section("18. QualityLevel min_score / max_score 검증")
    from shared.constants.status_codes import QualityLevel

    expected_min = {
        QualityLevel.EXCELLENT: 90,
        QualityLevel.GOOD: 75,
        QualityLevel.ACCEPTABLE: 60,
        QualityLevel.POOR: 40,
        QualityLevel.UNACCEPTABLE: 0,
    }

    expected_max = {
        QualityLevel.EXCELLENT: 100,
        QualityLevel.GOOD: 89,
        QualityLevel.ACCEPTABLE: 74,
        QualityLevel.POOR: 59,
        QualityLevel.UNACCEPTABLE: 39,
    }

    for level, min_val in expected_min.items():
        r.check(f"QualityLevel.{level.name}.min_score == {min_val}",
                level.min_score == min_val,
                f"실제: {level.min_score}")

    for level, max_val in expected_max.items():
        r.check(f"QualityLevel.{level.name}.max_score == {max_val}",
                level.max_score == max_val,
                f"실제: {level.max_score}")

    # min_score <= max_score 확인
    for level in QualityLevel:
        r.check(f"QualityLevel.{level.name}.min_score <= max_score",
                level.min_score <= level.max_score,
                f"min={level.min_score}, max={level.max_score}")

    # 인접 레벨의 점수 범위 연속성 확인 (max + 1 == 다음 min)
    levels_ordered = [
        QualityLevel.UNACCEPTABLE, QualityLevel.POOR,
        QualityLevel.ACCEPTABLE, QualityLevel.GOOD, QualityLevel.EXCELLENT,
    ]
    for i in range(1, len(levels_ordered)):
        prev_max = levels_ordered[i - 1].max_score
        curr_min = levels_ordered[i].min_score
        r.check(
            f"연속성: {levels_ordered[i-1].name}.max({prev_max}) + 1 == {levels_ordered[i].name}.min({curr_min})",
            prev_max + 1 == curr_min,
            f"{prev_max} + 1 != {curr_min}"
        )

    # 전체 범위: 0 ~ 100 커버리지
    r.check("UNACCEPTABLE.min_score == 0",
            QualityLevel.UNACCEPTABLE.min_score == 0)
    r.check("EXCELLENT.max_score == 100",
            QualityLevel.EXCELLENT.max_score == 100)


# =============================================================================
# 섹션 19: QualityLevel is_usable / description 검증
# =============================================================================
def test_quality_level_usable_description(r: TestResult) -> None:
    r.set_section("19. QualityLevel is_usable / description 검증")
    from shared.constants.status_codes import QualityLevel

    usable_expected = {
        QualityLevel.EXCELLENT, QualityLevel.GOOD, QualityLevel.ACCEPTABLE,
    }
    for level in QualityLevel:
        exp = level in usable_expected
        r.check(f"QualityLevel.{level.name}.is_usable == {exp}",
                level.is_usable == exp,
                f"실제: {level.is_usable}")

    # description 검증
    desc_map = {
        QualityLevel.EXCELLENT: "최상 품질 - 분석에 최적화됨",
        QualityLevel.GOOD: "양호 품질 - 정확한 분석 가능",
        QualityLevel.ACCEPTABLE: "허용 품질 - 기본 분석 가능",
        QualityLevel.POOR: "낮은 품질 - 분석 정확도 저하 가능",
        QualityLevel.UNACCEPTABLE: "사용 불가 - 분석 불가능",
    }

    for level, desc in desc_map.items():
        r.check(f"QualityLevel.{level.name}.description",
                level.description == desc,
                f"실제: '{level.description}'")

    # description 반환 타입
    for level in QualityLevel:
        r.check(f"QualityLevel.{level.name}.description은 str",
                isinstance(level.description, str))


# =============================================================================
# 섹션 20: TaskType 멤버 검증
# =============================================================================
def test_task_type_members(r: TestResult) -> None:
    r.set_section("20. TaskType 멤버 검증")
    from shared.constants.status_codes import TaskType

    r.check("TaskType 멤버 수 = 15", len(TaskType) == 15,
            f"실제: {len(TaskType)}")

    expected_members = [
        "ANALYSIS_TRAINING", "ANALYSIS_COMPARISON", "ANALYSIS_GAME",
        "ANALYSIS_REFEREE",
        "REPORT_WEEKLY", "REPORT_PROGRESS", "REPORT_CUSTOM",
        "VIDEO_PROCESSING", "BODY_SCAN", "HIGHLIGHT_EXTRACTION",
        "LEARNING_TRAINING", "LEARNING_VALIDATION",
        "EXPORT_VIDEO", "EXPORT_REPORT",
        "BATCH_ANALYSIS",
    ]

    for name in expected_members:
        r.check(f"TaskType.{name} 존재", hasattr(TaskType, name))

    # 값 검증
    expected_values = {
        "ANALYSIS_TRAINING": "analysis_training",
        "ANALYSIS_COMPARISON": "analysis_comparison",
        "ANALYSIS_GAME": "analysis_game",
        "ANALYSIS_REFEREE": "analysis_referee",
        "REPORT_WEEKLY": "report_weekly",
        "REPORT_PROGRESS": "report_progress",
        "REPORT_CUSTOM": "report_custom",
        "VIDEO_PROCESSING": "video_processing",
        "BODY_SCAN": "body_scan",
        "HIGHLIGHT_EXTRACTION": "highlight_extraction",
        "LEARNING_TRAINING": "learning_training",
        "LEARNING_VALIDATION": "learning_validation",
        "EXPORT_VIDEO": "export_video",
        "EXPORT_REPORT": "export_report",
        "BATCH_ANALYSIS": "batch_analysis",
    }
    for name, val in expected_values.items():
        member = getattr(TaskType, name)
        r.check(f"TaskType.{name}.value == '{val}'",
                member.value == val, f"실제: {member.value}")


# =============================================================================
# 섹션 21: TaskType is_analysis / is_report / is_learning 검증
# =============================================================================
def test_task_type_categories(r: TestResult) -> None:
    r.set_section("21. TaskType is_analysis / is_report / is_learning 검증")
    from shared.constants.status_codes import TaskType

    analysis_expected = {
        TaskType.ANALYSIS_TRAINING, TaskType.ANALYSIS_COMPARISON,
        TaskType.ANALYSIS_GAME, TaskType.ANALYSIS_REFEREE,
    }
    report_expected = {
        TaskType.REPORT_WEEKLY, TaskType.REPORT_PROGRESS,
        TaskType.REPORT_CUSTOM,
    }
    learning_expected = {
        TaskType.LEARNING_TRAINING, TaskType.LEARNING_VALIDATION,
    }

    for member in TaskType:
        exp_a = member in analysis_expected
        r.check(f"TaskType.{member.name}.is_analysis == {exp_a}",
                member.is_analysis == exp_a,
                f"실제: {member.is_analysis}")

    for member in TaskType:
        exp_r = member in report_expected
        r.check(f"TaskType.{member.name}.is_report == {exp_r}",
                member.is_report == exp_r,
                f"실제: {member.is_report}")

    for member in TaskType:
        exp_l = member in learning_expected
        r.check(f"TaskType.{member.name}.is_learning == {exp_l}",
                member.is_learning == exp_l,
                f"실제: {member.is_learning}")

    # 분류 카운트 확인
    r.check("is_analysis True 카운트 == 4",
            sum(1 for m in TaskType if m.is_analysis) == 4)
    r.check("is_report True 카운트 == 3",
            sum(1 for m in TaskType if m.is_report) == 3)
    r.check("is_learning True 카운트 == 2",
            sum(1 for m in TaskType if m.is_learning) == 2)


# =============================================================================
# 섹션 22: TaskType to_korean 검증
# =============================================================================
def test_task_type_korean(r: TestResult) -> None:
    r.set_section("22. TaskType to_korean 검증")
    from shared.constants.status_codes import TaskType

    korean_map = {
        TaskType.ANALYSIS_TRAINING: "훈련 분석",
        TaskType.ANALYSIS_COMPARISON: "비교 분석",
        TaskType.ANALYSIS_GAME: "경기 분석",
        TaskType.ANALYSIS_REFEREE: "심판 분석",
        TaskType.REPORT_WEEKLY: "주간 리포트",
        TaskType.REPORT_PROGRESS: "진행 리포트",
        TaskType.REPORT_CUSTOM: "커스텀 리포트",
        TaskType.VIDEO_PROCESSING: "영상 처리",
        TaskType.BODY_SCAN: "신체 스캔",
        TaskType.HIGHLIGHT_EXTRACTION: "하이라이트 추출",
        TaskType.LEARNING_TRAINING: "모델 학습",
        TaskType.LEARNING_VALIDATION: "모델 검증",
        TaskType.EXPORT_VIDEO: "영상 내보내기",
        TaskType.EXPORT_REPORT: "리포트 내보내기",
        TaskType.BATCH_ANALYSIS: "대량 분석",
    }

    for member, kr in korean_map.items():
        r.check(f"TaskType.{member.name}.to_korean() == '{kr}'",
                member.to_korean() == kr,
                f"실제: '{member.to_korean()}'")

    r.check("TaskType 한글 매핑 수 == 멤버 수",
            len(korean_map) == len(TaskType))


# =============================================================================
# 섹션 23: LearningStatus 멤버 검증
# =============================================================================
def test_learning_status_members(r: TestResult) -> None:
    r.set_section("23. LearningStatus 멤버 검증")
    from shared.constants.status_codes import LearningStatus

    r.check("LearningStatus 멤버 수 = 13", len(LearningStatus) == 13,
            f"실제: {len(LearningStatus)}")

    expected_members = [
        "IDLE", "READY", "PREPARING",
        "TRAINING", "VALIDATING", "OPTIMIZING",
        "COMPLETED", "DEPLOYED",
        "FAILED", "CANCELLED", "PAUSED",
        "ROLLING_BACK", "ROLLED_BACK",
    ]

    for name in expected_members:
        r.check(f"LearningStatus.{name} 존재", hasattr(LearningStatus, name))

    # 값 검증
    expected_values = {
        "IDLE": "idle", "READY": "ready", "PREPARING": "preparing",
        "TRAINING": "training", "VALIDATING": "validating",
        "OPTIMIZING": "optimizing", "COMPLETED": "completed",
        "DEPLOYED": "deployed", "FAILED": "failed",
        "CANCELLED": "cancelled", "PAUSED": "paused",
        "ROLLING_BACK": "rolling_back", "ROLLED_BACK": "rolled_back",
    }
    for name, val in expected_values.items():
        member = getattr(LearningStatus, name)
        r.check(f"LearningStatus.{name}.value == '{val}'",
                member.value == val, f"실제: {member.value}")


# =============================================================================
# 섹션 24: LearningStatus is_active / is_terminal / can_trigger_learning 검증
# =============================================================================
def test_learning_status_properties(r: TestResult) -> None:
    r.set_section("24. LearningStatus is_active / is_terminal / can_trigger_learning 검증")
    from shared.constants.status_codes import LearningStatus

    active_expected = {
        LearningStatus.PREPARING, LearningStatus.TRAINING,
        LearningStatus.VALIDATING, LearningStatus.OPTIMIZING,
        LearningStatus.ROLLING_BACK,
    }
    terminal_expected = {
        LearningStatus.COMPLETED, LearningStatus.DEPLOYED,
        LearningStatus.FAILED, LearningStatus.CANCELLED,
        LearningStatus.ROLLED_BACK,
    }
    can_trigger_expected = {
        LearningStatus.IDLE, LearningStatus.READY,
        LearningStatus.COMPLETED, LearningStatus.DEPLOYED,
        LearningStatus.FAILED, LearningStatus.CANCELLED,
        LearningStatus.ROLLED_BACK,
    }

    for member in LearningStatus:
        exp_a = member in active_expected
        r.check(f"LearningStatus.{member.name}.is_active == {exp_a}",
                member.is_active == exp_a,
                f"실제: {member.is_active}")

    for member in LearningStatus:
        exp_t = member in terminal_expected
        r.check(f"LearningStatus.{member.name}.is_terminal == {exp_t}",
                member.is_terminal == exp_t,
                f"실제: {member.is_terminal}")

    for member in LearningStatus:
        exp_c = member in can_trigger_expected
        r.check(f"LearningStatus.{member.name}.can_trigger_learning == {exp_c}",
                member.can_trigger_learning == exp_c,
                f"실제: {member.can_trigger_learning}")

    # 카운트 확인
    r.check("is_active True 카운트 == 5",
            sum(1 for m in LearningStatus if m.is_active) == 5)
    r.check("is_terminal True 카운트 == 5",
            sum(1 for m in LearningStatus if m.is_terminal) == 5)
    r.check("can_trigger_learning True 카운트 == 7",
            sum(1 for m in LearningStatus if m.can_trigger_learning) == 7)


# =============================================================================
# 섹션 25: LearningStatus to_korean 검증
# =============================================================================
def test_learning_status_korean(r: TestResult) -> None:
    r.set_section("25. LearningStatus to_korean 검증")
    from shared.constants.status_codes import LearningStatus

    korean_map = {
        LearningStatus.IDLE: "유휴",
        LearningStatus.READY: "준비 완료",
        LearningStatus.PREPARING: "준비 중",
        LearningStatus.TRAINING: "학습 중",
        LearningStatus.VALIDATING: "검증 중",
        LearningStatus.OPTIMIZING: "최적화 중",
        LearningStatus.COMPLETED: "완료",
        LearningStatus.DEPLOYED: "배포됨",
        LearningStatus.FAILED: "실패",
        LearningStatus.CANCELLED: "취소됨",
        LearningStatus.PAUSED: "일시 정지",
        LearningStatus.ROLLING_BACK: "롤백 중",
        LearningStatus.ROLLED_BACK: "롤백 완료",
    }

    for member, kr in korean_map.items():
        r.check(f"LearningStatus.{member.name}.to_korean() == '{kr}'",
                member.to_korean() == kr,
                f"실제: '{member.to_korean()}'")

    r.check("LearningStatus 한글 매핑 수 == 멤버 수",
            len(korean_map) == len(LearningStatus))


# =============================================================================
# 섹션 26: VALID_TASK_TRANSITIONS 검증
# =============================================================================
def test_valid_task_transitions(r: TestResult) -> None:
    r.set_section("26. VALID_TASK_TRANSITIONS 검증")
    from shared.constants.status_codes import TaskStatus, VALID_TASK_TRANSITIONS

    # 모든 TaskStatus가 키로 존재
    r.check("VALID_TASK_TRANSITIONS 키 수 == TaskStatus 멤버 수",
            len(VALID_TASK_TRANSITIONS) == len(TaskStatus),
            f"키: {len(VALID_TASK_TRANSITIONS)}, 멤버: {len(TaskStatus)}")

    for member in TaskStatus:
        r.check(f"VALID_TASK_TRANSITIONS에 {member.name} 키 존재",
                member in VALID_TASK_TRANSITIONS)

    # 터미널 상태는 빈 튜플
    terminal_statuses = [
        TaskStatus.COMPLETED, TaskStatus.SUCCESS,
        TaskStatus.CANCELLED, TaskStatus.REVOKED, TaskStatus.ERROR,
    ]
    for ts in terminal_statuses:
        transitions = VALID_TASK_TRANSITIONS[ts]
        r.check(f"터미널 {ts.name}은 빈 전이",
                len(transitions) == 0,
                f"전이: {transitions}")

    # 비터미널 FAILED, TIMEOUT은 RETRY로 전이 가능
    r.check("FAILED -> RETRY 가능",
            TaskStatus.RETRY in VALID_TASK_TRANSITIONS[TaskStatus.FAILED])
    r.check("TIMEOUT -> RETRY 가능",
            TaskStatus.RETRY in VALID_TASK_TRANSITIONS[TaskStatus.TIMEOUT])

    # PENDING -> QUEUED, CANCELLED
    pending_trans = VALID_TASK_TRANSITIONS[TaskStatus.PENDING]
    r.check("PENDING -> QUEUED 가능", TaskStatus.QUEUED in pending_trans)
    r.check("PENDING -> CANCELLED 가능", TaskStatus.CANCELLED in pending_trans)
    r.check("PENDING 전이 수 == 2", len(pending_trans) == 2,
            f"실제: {len(pending_trans)}")

    # QUEUED -> STARTED, CANCELLED, REVOKED
    queued_trans = VALID_TASK_TRANSITIONS[TaskStatus.QUEUED]
    r.check("QUEUED -> STARTED 가능", TaskStatus.STARTED in queued_trans)
    r.check("QUEUED -> CANCELLED 가능", TaskStatus.CANCELLED in queued_trans)
    r.check("QUEUED -> REVOKED 가능", TaskStatus.REVOKED in queued_trans)

    # RUNNING -> PROCESSING, COMPLETED, FAILED, ERROR, TIMEOUT, CANCELLED
    running_trans = VALID_TASK_TRANSITIONS[TaskStatus.RUNNING]
    r.check("RUNNING -> PROCESSING", TaskStatus.PROCESSING in running_trans)
    r.check("RUNNING -> COMPLETED", TaskStatus.COMPLETED in running_trans)
    r.check("RUNNING -> FAILED", TaskStatus.FAILED in running_trans)
    r.check("RUNNING -> ERROR", TaskStatus.ERROR in running_trans)
    r.check("RUNNING -> TIMEOUT", TaskStatus.TIMEOUT in running_trans)
    r.check("RUNNING -> CANCELLED", TaskStatus.CANCELLED in running_trans)
    r.check("RUNNING 전이 수 == 6", len(running_trans) == 6,
            f"실제: {len(running_trans)}")

    # PROCESSING -> RUNNING, COMPLETED, FAILED, ERROR, TIMEOUT
    proc_trans = VALID_TASK_TRANSITIONS[TaskStatus.PROCESSING]
    r.check("PROCESSING -> RUNNING", TaskStatus.RUNNING in proc_trans)
    r.check("PROCESSING -> COMPLETED", TaskStatus.COMPLETED in proc_trans)
    r.check("PROCESSING -> FAILED", TaskStatus.FAILED in proc_trans)
    r.check("PROCESSING -> ERROR", TaskStatus.ERROR in proc_trans)
    r.check("PROCESSING -> TIMEOUT", TaskStatus.TIMEOUT in proc_trans)

    # RETRY -> RETRYING, CANCELLED
    retry_trans = VALID_TASK_TRANSITIONS[TaskStatus.RETRY]
    r.check("RETRY -> RETRYING", TaskStatus.RETRYING in retry_trans)
    r.check("RETRY -> CANCELLED", TaskStatus.CANCELLED in retry_trans)

    # RETRYING -> RUNNING, FAILED, ERROR, CANCELLED
    retrying_trans = VALID_TASK_TRANSITIONS[TaskStatus.RETRYING]
    r.check("RETRYING -> RUNNING", TaskStatus.RUNNING in retrying_trans)
    r.check("RETRYING -> FAILED", TaskStatus.FAILED in retrying_trans)
    r.check("RETRYING -> ERROR", TaskStatus.ERROR in retrying_trans)
    r.check("RETRYING -> CANCELLED", TaskStatus.CANCELLED in retrying_trans)

    # SCHEDULED -> QUEUED, CANCELLED
    sched_trans = VALID_TASK_TRANSITIONS[TaskStatus.SCHEDULED]
    r.check("SCHEDULED -> QUEUED", TaskStatus.QUEUED in sched_trans)
    r.check("SCHEDULED -> CANCELLED", TaskStatus.CANCELLED in sched_trans)

    # STARTED -> RUNNING, FAILED, ERROR, CANCELLED
    started_trans = VALID_TASK_TRANSITIONS[TaskStatus.STARTED]
    r.check("STARTED -> RUNNING", TaskStatus.RUNNING in started_trans)
    r.check("STARTED -> FAILED", TaskStatus.FAILED in started_trans)
    r.check("STARTED -> ERROR", TaskStatus.ERROR in started_trans)
    r.check("STARTED -> CANCELLED", TaskStatus.CANCELLED in started_trans)

    # 모든 전이 값은 tuple 타입
    for status, transitions in VALID_TASK_TRANSITIONS.items():
        r.check(f"VALID_TASK_TRANSITIONS[{status.name}] 타입 == tuple",
                isinstance(transitions, tuple),
                f"타입: {type(transitions)}")

    # 전이 대상은 모두 TaskStatus 멤버
    for status, transitions in VALID_TASK_TRANSITIONS.items():
        for target in transitions:
            r.check(f"{status.name} -> {target.name} 는 TaskStatus 멤버",
                    isinstance(target, TaskStatus))


# =============================================================================
# 섹션 27: is_valid_transition 함수 검증
# =============================================================================
def test_is_valid_transition_function(r: TestResult) -> None:
    r.set_section("27. is_valid_transition 함수 검증")
    from shared.constants.status_codes import (
        TaskStatus, is_valid_transition, VALID_TASK_TRANSITIONS,
    )

    # 유효한 전이 테스트
    valid_transitions = [
        (TaskStatus.PENDING, TaskStatus.QUEUED),
        (TaskStatus.PENDING, TaskStatus.CANCELLED),
        (TaskStatus.QUEUED, TaskStatus.STARTED),
        (TaskStatus.STARTED, TaskStatus.RUNNING),
        (TaskStatus.RUNNING, TaskStatus.COMPLETED),
        (TaskStatus.RUNNING, TaskStatus.FAILED),
        (TaskStatus.RUNNING, TaskStatus.TIMEOUT),
        (TaskStatus.FAILED, TaskStatus.RETRY),
        (TaskStatus.TIMEOUT, TaskStatus.RETRY),
        (TaskStatus.RETRY, TaskStatus.RETRYING),
        (TaskStatus.RETRYING, TaskStatus.RUNNING),
        (TaskStatus.PROCESSING, TaskStatus.COMPLETED),
        (TaskStatus.SCHEDULED, TaskStatus.QUEUED),
    ]

    for from_s, to_s in valid_transitions:
        r.check(f"is_valid_transition({from_s.name}, {to_s.name}) == True",
                is_valid_transition(from_s, to_s) is True)

    # 무효한 전이 테스트
    invalid_transitions = [
        (TaskStatus.COMPLETED, TaskStatus.RUNNING),
        (TaskStatus.COMPLETED, TaskStatus.PENDING),
        (TaskStatus.SUCCESS, TaskStatus.RUNNING),
        (TaskStatus.CANCELLED, TaskStatus.RUNNING),
        (TaskStatus.REVOKED, TaskStatus.RUNNING),
        (TaskStatus.ERROR, TaskStatus.RUNNING),
        (TaskStatus.PENDING, TaskStatus.COMPLETED),
        (TaskStatus.PENDING, TaskStatus.RUNNING),
        (TaskStatus.RUNNING, TaskStatus.PENDING),
        (TaskStatus.RUNNING, TaskStatus.QUEUED),
        (TaskStatus.FAILED, TaskStatus.COMPLETED),
        (TaskStatus.FAILED, TaskStatus.RUNNING),
    ]

    for from_s, to_s in invalid_transitions:
        r.check(f"is_valid_transition({from_s.name}, {to_s.name}) == False",
                is_valid_transition(from_s, to_s) is False)

    # 반환 타입 확인
    result = is_valid_transition(TaskStatus.PENDING, TaskStatus.QUEUED)
    r.check("is_valid_transition 반환 타입 == bool",
            isinstance(result, bool))

    # 자기 자신으로의 전이는 대부분 무효 (명시적으로 허용되지 않은 경우)
    for status in TaskStatus:
        expected = status in VALID_TASK_TRANSITIONS.get(status, ())
        actual = is_valid_transition(status, status)
        r.check(f"is_valid_transition({status.name}, {status.name}) == {expected}",
                actual == expected)


# =============================================================================
# 섹션 28: __all__ 완전성 검증
# =============================================================================
def test_all_completeness(r: TestResult) -> None:
    r.set_section("28. __all__ 완전성 검증")
    import shared.constants.status_codes as module

    r.check("__all__ 정의 존재", hasattr(module, "__all__"))

    expected_all = [
        "TaskStatus",
        "TaskType",
        "AnalysisType",
        "AnalysisPhase",
        "ServiceStatus",
        "QueuePriority",
        "Environment",
        "QualityLevel",
        "LearningStatus",
        "VALID_TASK_TRANSITIONS",
        "is_valid_transition",
    ]

    r.check("__all__ 항목 수 == 11", len(module.__all__) == 11,
            f"실제: {len(module.__all__)}")

    for item in expected_all:
        r.check(f"'{item}' in __all__", item in module.__all__,
                f"'{item}' 누락")

    # __all__에 없는 항목이 없는지 (추가 항목 없음)
    for item in module.__all__:
        r.check(f"__all__ 항목 '{item}' 접근 가능",
                hasattr(module, item),
                f"'{item}'은 모듈에 존재하지 않음")

    # 모든 __all__ 항목은 문자열
    for item in module.__all__:
        r.check(f"__all__ 항목 '{item}'은 str",
                isinstance(item, str))


# =============================================================================
# 섹션 29: 캐시 타입 및 완전성 검증
# =============================================================================
def test_cache_types_completeness(r: TestResult) -> None:
    r.set_section("29. 캐시 타입 및 완전성 검증")
    import shared.constants.status_codes as module

    # frozenset 캐시 13개
    frozenset_caches = [
        "_TASK_STATUS_TERMINAL",
        "_TASK_STATUS_SUCCESS",
        "_TASK_STATUS_FAILURE",
        "_TASK_STATUS_RUNNING",
        "_TASK_STATUS_PENDING",
        "_SERVICE_STATUS_AVAILABLE",
        "_QUALITY_LEVEL_USABLE",
        "_TASK_TYPE_ANALYSIS",
        "_TASK_TYPE_REPORT",
        "_TASK_TYPE_LEARNING",
        "_LEARNING_STATUS_ACTIVE",
        "_LEARNING_STATUS_TERMINAL",
        "_LEARNING_STATUS_CAN_TRIGGER",
    ]

    for name in frozenset_caches:
        r.check(f"{name} 존재", hasattr(module, name),
                f"모듈에 {name} 없음")
        if hasattr(module, name):
            cache = getattr(module, name)
            r.check(f"{name} 타입 == frozenset",
                    isinstance(cache, frozenset),
                    f"타입: {type(cache)}")

    # dict 캐시 12개
    dict_caches = [
        "_TASK_STATUS_KOREAN_MAP",
        "_ANALYSIS_TYPE_KOREAN_MAP",
        "_ANALYSIS_PHASE_KOREAN_MAP",
        "_ANALYSIS_PHASE_PROGRESS_MAP",
        "_SERVICE_STATUS_KOREAN_MAP",
        "_QUEUE_PRIORITY_KOREAN_MAP",
        "_ENVIRONMENT_KOREAN_MAP",
        "_QUALITY_LEVEL_DESC_MAP",
        "_QUALITY_LEVEL_MIN_SCORE_MAP",
        "_QUALITY_LEVEL_MAX_SCORE_MAP",
        "_TASK_TYPE_KOREAN_MAP",
        "_LEARNING_STATUS_KOREAN_MAP",
    ]

    for name in dict_caches:
        r.check(f"{name} 존재", hasattr(module, name),
                f"모듈에 {name} 없음")
        if hasattr(module, name):
            cache = getattr(module, name)
            r.check(f"{name} 타입 == dict",
                    isinstance(cache, dict),
                    f"타입: {type(cache)}")

    # 캐시 총 수 확인
    r.check("frozenset 캐시 13개",
            sum(1 for n in frozenset_caches if hasattr(module, n)) == 13)
    r.check("dict 캐시 12개",
            sum(1 for n in dict_caches if hasattr(module, n)) == 12)

    # 한글 맵은 해당 Enum의 모든 멤버를 키로 가짐
    from shared.constants.status_codes import (
        TaskStatus, AnalysisType, AnalysisPhase, ServiceStatus,
        QueuePriority, Environment, QualityLevel, TaskType, LearningStatus,
    )

    enum_korean_map_pairs = [
        (TaskStatus, "_TASK_STATUS_KOREAN_MAP"),
        (AnalysisType, "_ANALYSIS_TYPE_KOREAN_MAP"),
        (AnalysisPhase, "_ANALYSIS_PHASE_KOREAN_MAP"),
        (ServiceStatus, "_SERVICE_STATUS_KOREAN_MAP"),
        (QueuePriority, "_QUEUE_PRIORITY_KOREAN_MAP"),
        (Environment, "_ENVIRONMENT_KOREAN_MAP"),
        (QualityLevel, "_QUALITY_LEVEL_DESC_MAP"),
        (TaskType, "_TASK_TYPE_KOREAN_MAP"),
        (LearningStatus, "_LEARNING_STATUS_KOREAN_MAP"),
    ]

    for enum_cls, map_name in enum_korean_map_pairs:
        if hasattr(module, map_name):
            cache = getattr(module, map_name)
            r.check(f"{map_name} 키 수 == {enum_cls.__name__} 멤버 수",
                    len(cache) == len(enum_cls),
                    f"캐시: {len(cache)}, 멤버: {len(enum_cls)}")

    # _ANALYSIS_CATEGORY_MAP 존재 확인
    r.check("_ANALYSIS_CATEGORY_MAP 존재",
            hasattr(module, "_ANALYSIS_CATEGORY_MAP"))

    # _get_analysis_category 함수의 lru_cache 확인
    r.check("_get_analysis_category 함수 존재",
            hasattr(module, "_get_analysis_category"))
    if hasattr(module, "_get_analysis_category"):
        func = module._get_analysis_category
        r.check("_get_analysis_category에 cache_info 있음 (lru_cache 적용)",
                hasattr(func, "cache_info"))


# =============================================================================
# 섹션 30: 메타 정보 검증 (버전, typing modernization)
# =============================================================================
def test_meta_info(r: TestResult) -> None:
    r.set_section("30. 메타 정보 검증")
    import shared.constants.status_codes as module

    # 버전 정보
    r.check("__version__ 존재", hasattr(module, "__version__"))
    r.check("__version__ == '1.1.0'", module.__version__ == "1.1.0",
            f"실제: {module.__version__}")

    # Enum @unique 데코레이터 적용 확인 (중복 값 없음)
    from shared.constants.status_codes import (
        TaskStatus, AnalysisType, AnalysisPhase, ServiceStatus,
        QueuePriority, Environment, QualityLevel, TaskType, LearningStatus,
    )

    all_enums = [
        TaskStatus, AnalysisType, AnalysisPhase, ServiceStatus,
        QueuePriority, Environment, QualityLevel, TaskType, LearningStatus,
    ]

    for enum_cls in all_enums:
        values = [m.value for m in enum_cls]
        r.check(f"{enum_cls.__name__} 중복 값 없음 (@unique)",
                len(values) == len(set(values)),
                f"중복: {[v for v in values if values.count(v) > 1]}")

    # 총 멤버 수: 15+15+11+8+5+4+5+15+13 = 91
    total_members = sum(len(e) for e in all_enums)
    r.check("총 Enum 멤버 수 == 91", total_members == 91,
            f"실제: {total_members}")

    # Enum 수 == 9
    r.check("총 Enum 클래스 수 == 9", len(all_enums) == 9)

    # typing.Final 임포트 확인 (소스 코드 레벨)
    import inspect
    source = inspect.getsource(module)
    r.check("typing.Final 사용",
            "Final" in source)
    r.check("functools.lru_cache 사용",
            "lru_cache" in source)

    # VALID_TASK_TRANSITIONS 타입 검증
    from shared.constants.status_codes import VALID_TASK_TRANSITIONS
    r.check("VALID_TASK_TRANSITIONS 타입 == dict",
            isinstance(VALID_TASK_TRANSITIONS, dict))


# =============================================================================
# 섹션 31: 에지 케이스 검증
# =============================================================================
def test_edge_cases(r: TestResult) -> None:
    r.set_section("31. 에지 케이스 검증")
    from shared.constants.status_codes import (
        TaskStatus, AnalysisType, AnalysisPhase, ServiceStatus,
        QueuePriority, Environment, QualityLevel, TaskType, LearningStatus,
        is_valid_transition, VALID_TASK_TRANSITIONS,
    )

    # Enum 멤버 비교: 동일 멤버 == 확인
    r.check("TaskStatus.PENDING == TaskStatus.PENDING",
            TaskStatus.PENDING == TaskStatus.PENDING)
    r.check("TaskStatus.PENDING != TaskStatus.QUEUED",
            TaskStatus.PENDING != TaskStatus.QUEUED)

    # Enum 멤버는 동일 타입의 다른 멤버와 같지 않음
    r.check("TaskStatus.COMPLETED != TaskStatus.SUCCESS",
            TaskStatus.COMPLETED != TaskStatus.SUCCESS)

    # 서로 다른 Enum 타입 간 비교
    r.check("TaskStatus.COMPLETED != AnalysisPhase.DONE",
            TaskStatus.COMPLETED != AnalysisPhase.DONE)

    # QualityLevel.from_score 정확한 경계값
    r.check("from_score(90.0) == EXCELLENT",
            QualityLevel.from_score(90.0) == QualityLevel.EXCELLENT)
    r.check("from_score(89.999) == GOOD",
            QualityLevel.from_score(89.999) == QualityLevel.GOOD)

    # from_score에 정확히 0과 100
    r.check("from_score(0) == UNACCEPTABLE",
            QualityLevel.from_score(0) == QualityLevel.UNACCEPTABLE)
    r.check("from_score(100) == EXCELLENT",
            QualityLevel.from_score(100) == QualityLevel.EXCELLENT)

    # Enum 값으로 생성
    r.check("TaskStatus('pending') == PENDING",
            TaskStatus("pending") == TaskStatus.PENDING)
    r.check("AnalysisType('training_shooting') == TRAINING_SHOOTING",
            AnalysisType("training_shooting") == AnalysisType.TRAINING_SHOOTING)
    r.check("QueuePriority(0) == CRITICAL",
            QueuePriority(0) == QueuePriority.CRITICAL)

    # 잘못된 값으로 생성 시 ValueError
    try:
        TaskStatus("nonexistent_status")
        r.fail("TaskStatus('nonexistent') ValueError 미발생")
    except ValueError:
        r.ok("TaskStatus('nonexistent') ValueError 발생")

    try:
        QueuePriority(99)
        r.fail("QueuePriority(99) ValueError 미발생")
    except ValueError:
        r.ok("QueuePriority(99) ValueError 발생")

    # Enum 멤버 name 속성
    r.check("TaskStatus.PENDING.name == 'PENDING'",
            TaskStatus.PENDING.name == "PENDING")
    r.check("QueuePriority.CRITICAL.name == 'CRITICAL'",
            QueuePriority.CRITICAL.name == "CRITICAL")

    # Enum 반복(iteration) 가능
    task_list = list(TaskStatus)
    r.check("TaskStatus 반복 가능 (list 변환)", len(task_list) == 15)

    # 해싱 가능 (set/dict 키)
    task_set = {TaskStatus.PENDING, TaskStatus.RUNNING}
    r.check("TaskStatus 해싱 가능 (set)", len(task_set) == 2)

    # VALID_TASK_TRANSITIONS에서 자기 자신 전이 허용 여부 확인
    # PROCESSING -> RUNNING -> PROCESSING 양방향 (PROCESSING->RUNNING 가능)
    r.check("PROCESSING -> RUNNING 양방향 전이 (PROCESSING -> RUNNING)",
            TaskStatus.RUNNING in VALID_TASK_TRANSITIONS[TaskStatus.PROCESSING])
    r.check("PROCESSING -> RUNNING 양방향 전이 (RUNNING -> PROCESSING)",
            TaskStatus.PROCESSING in VALID_TASK_TRANSITIONS[TaskStatus.RUNNING])

    # _get_analysis_category lru_cache 동작 확인
    import shared.constants.status_codes as module
    func = module._get_analysis_category
    # 첫 호출 및 캐시 히트 확인
    result1 = func("training_shooting")
    result2 = func("training_shooting")
    r.check("_get_analysis_category 캐시 일관성",
            result1 == result2 == "training")

    # unknown 카테고리 처리
    result_unknown = func("xyz_something")
    r.check("_get_analysis_category unknown 카테고리",
            result_unknown == "unknown")

    # cache_info 확인
    info = func.cache_info()
    r.check("lru_cache cache_info.hits >= 1", info.hits >= 1)

    # QualityLevel from_score에 float 경계값
    r.check("from_score(75.0) == GOOD",
            QualityLevel.from_score(75.0) == QualityLevel.GOOD)
    r.check("from_score(74.999) == ACCEPTABLE",
            QualityLevel.from_score(74.999) == QualityLevel.ACCEPTABLE)
    r.check("from_score(60.0) == ACCEPTABLE",
            QualityLevel.from_score(60.0) == QualityLevel.ACCEPTABLE)
    r.check("from_score(59.999) == POOR",
            QualityLevel.from_score(59.999) == QualityLevel.POOR)
    r.check("from_score(40.0) == POOR",
            QualityLevel.from_score(40.0) == QualityLevel.POOR)
    r.check("from_score(39.999) == UNACCEPTABLE",
            QualityLevel.from_score(39.999) == QualityLevel.UNACCEPTABLE)


# =============================================================================
# 섹션 32: TaskStatus 카테고리 상호 배타성 검증
# =============================================================================
def test_task_status_mutual_exclusivity(r: TestResult) -> None:
    r.set_section("32. TaskStatus 카테고리 상호 배타성 검증")
    from shared.constants.status_codes import TaskStatus

    # 각 TaskStatus 멤버에 대해 카테고리 분류 수집
    for member in TaskStatus:
        categories = []
        if member.is_terminal:
            categories.append("terminal")
        if member.is_success:
            categories.append("success")
        if member.is_failure:
            categories.append("failure")
        if member.is_running:
            categories.append("running")
        if member.is_pending:
            categories.append("pending")

        # is_success와 is_failure는 상호 배타적
        r.check(f"TaskStatus.{member.name}: success/failure 상호 배타",
                not (member.is_success and member.is_failure),
                f"둘 다 True: {categories}")

        # is_running과 is_pending은 상호 배타적
        r.check(f"TaskStatus.{member.name}: running/pending 상호 배타",
                not (member.is_running and member.is_pending),
                f"둘 다 True: {categories}")

        # is_running과 is_terminal은 상호 배타적
        r.check(f"TaskStatus.{member.name}: running/terminal 상호 배타",
                not (member.is_running and member.is_terminal),
                f"둘 다 True: {categories}")

        # is_pending과 is_terminal은 상호 배타적
        r.check(f"TaskStatus.{member.name}: pending/terminal 상호 배타",
                not (member.is_pending and member.is_terminal),
                f"둘 다 True: {categories}")

    # success는 terminal의 부분집합
    for member in TaskStatus:
        if member.is_success:
            r.check(f"TaskStatus.{member.name}: success -> terminal",
                    member.is_terminal,
                    "success인데 terminal이 아님")

    # failure는 terminal의 부분집합
    for member in TaskStatus:
        if member.is_failure:
            r.check(f"TaskStatus.{member.name}: failure -> terminal",
                    member.is_terminal,
                    "failure인데 terminal이 아님")

    # 모든 멤버가 최소 하나의 카테고리에 속하는지 확인
    for member in TaskStatus:
        has_category = (
            member.is_terminal or member.is_running or member.is_pending
        )
        r.check(f"TaskStatus.{member.name}: 최소 하나의 카테고리",
                has_category,
                "어떤 카테고리에도 속하지 않음")


# =============================================================================
# 섹션 33: LearningStatus 카테고리 상호 배타성 검증
# =============================================================================
def test_learning_status_mutual_exclusivity(r: TestResult) -> None:
    r.set_section("33. LearningStatus 카테고리 상호 배타성 검증")
    from shared.constants.status_codes import LearningStatus

    # is_active와 is_terminal은 상호 배타적
    for member in LearningStatus:
        r.check(f"LearningStatus.{member.name}: active/terminal 상호 배타",
                not (member.is_active and member.is_terminal),
                f"active={member.is_active}, terminal={member.is_terminal}")

    # terminal 상태는 can_trigger_learning 가능 (재학습 트리거)
    terminal_can_trigger = {
        LearningStatus.COMPLETED, LearningStatus.DEPLOYED,
        LearningStatus.FAILED, LearningStatus.CANCELLED,
        LearningStatus.ROLLED_BACK,
    }
    for member in terminal_can_trigger:
        r.check(f"LearningStatus.{member.name}: terminal이면서 can_trigger",
                member.is_terminal and member.can_trigger_learning)

    # active 상태는 can_trigger_learning == False
    for member in LearningStatus:
        if member.is_active:
            r.check(f"LearningStatus.{member.name}: active -> not can_trigger",
                    not member.can_trigger_learning,
                    f"active인데 can_trigger={member.can_trigger_learning}")

    # PAUSED는 active도 아니고 terminal도 아님
    r.check("LearningStatus.PAUSED: not active",
            not LearningStatus.PAUSED.is_active)
    r.check("LearningStatus.PAUSED: not terminal",
            not LearningStatus.PAUSED.is_terminal)
    r.check("LearningStatus.PAUSED: not can_trigger",
            not LearningStatus.PAUSED.can_trigger_learning)


# =============================================================================
# 섹션 34: TaskType 카테고리 상호 배타성 검증
# =============================================================================
def test_task_type_mutual_exclusivity(r: TestResult) -> None:
    r.set_section("34. TaskType 카테고리 상호 배타성 검증")
    from shared.constants.status_codes import TaskType

    for member in TaskType:
        # is_analysis와 is_report 상호 배타적
        r.check(f"TaskType.{member.name}: analysis/report 상호 배타",
                not (member.is_analysis and member.is_report),
                f"analysis={member.is_analysis}, report={member.is_report}")

        # is_analysis와 is_learning 상호 배타적
        r.check(f"TaskType.{member.name}: analysis/learning 상호 배타",
                not (member.is_analysis and member.is_learning),
                f"analysis={member.is_analysis}, learning={member.is_learning}")

        # is_report와 is_learning 상호 배타적
        r.check(f"TaskType.{member.name}: report/learning 상호 배타",
                not (member.is_report and member.is_learning),
                f"report={member.is_report}, learning={member.is_learning}")

    # 분류에 속하지 않는 멤버 확인 (VIDEO_PROCESSING, BODY_SCAN, etc.)
    uncategorized = {
        TaskType.VIDEO_PROCESSING, TaskType.BODY_SCAN,
        TaskType.HIGHLIGHT_EXTRACTION, TaskType.EXPORT_VIDEO,
        TaskType.EXPORT_REPORT, TaskType.BATCH_ANALYSIS,
    }
    for member in uncategorized:
        r.check(f"TaskType.{member.name}: 분류 없음 (analysis/report/learning 모두 False)",
                not member.is_analysis and not member.is_report and not member.is_learning)


# =============================================================================
# 섹션 35: AnalysisType lru_cache 동작 상세 검증
# =============================================================================
def test_analysis_type_lru_cache(r: TestResult) -> None:
    r.set_section("35. AnalysisType lru_cache 동작 상세 검증")
    import shared.constants.status_codes as module
    from shared.constants.status_codes import AnalysisType

    func = module._get_analysis_category

    # 캐시 클리어 후 테스트
    func.cache_clear()
    info_before = func.cache_info()
    r.check("cache_clear 후 hits == 0", info_before.hits == 0)
    r.check("cache_clear 후 misses == 0", info_before.misses == 0)
    r.check("cache_clear 후 currsize == 0", info_before.currsize == 0)

    # 모든 AnalysisType.category 한 번 접근 -> misses 증가
    for member in AnalysisType:
        _ = member.category
    info_after_first = func.cache_info()
    r.check("첫 순회 후 misses == 15",
            info_after_first.misses == 15,
            f"실제: {info_after_first.misses}")

    # 두 번째 순회 -> hits 증가
    for member in AnalysisType:
        _ = member.category
    info_after_second = func.cache_info()
    r.check("두 번째 순회 후 hits == 15",
            info_after_second.hits == 15,
            f"실제: {info_after_second.hits}")

    # maxsize == None (무제한 캐시)
    r.check("lru_cache maxsize == None",
            info_after_second.maxsize is None)

    # 캐시 크기 확인 (고유 값 수)
    r.check("캐시 크기 == 15 (고유 값 수)",
            info_after_second.currsize == 15,
            f"실제: {info_after_second.currsize}")


# =============================================================================
# 섹션 36: VALID_TASK_TRANSITIONS 무결성 심층 검증
# =============================================================================
def test_transitions_integrity(r: TestResult) -> None:
    r.set_section("36. VALID_TASK_TRANSITIONS 무결성 심층 검증")
    from shared.constants.status_codes import (
        TaskStatus, VALID_TASK_TRANSITIONS, is_valid_transition,
    )

    # 모든 전이 대상이 VALID_TASK_TRANSITIONS의 키로 존재 (그래프 무결성)
    for from_status, targets in VALID_TASK_TRANSITIONS.items():
        for target in targets:
            r.check(f"전이 대상 {target.name}은 전이 맵 키에 존재",
                    target in VALID_TASK_TRANSITIONS)

    # 터미널 상태 중 전이가 없어야 하는 상태 (완전 종료)
    # FAILED, TIMEOUT은 터미널이지만 RETRY로의 복구 전이를 허용 (설계 의도)
    fully_terminal = {
        TaskStatus.COMPLETED, TaskStatus.SUCCESS,
        TaskStatus.CANCELLED, TaskStatus.REVOKED, TaskStatus.ERROR,
    }
    for ts in fully_terminal:
        transitions = VALID_TASK_TRANSITIONS[ts]
        r.check(f"완전 터미널 {ts.name} 전이 없음",
                len(transitions) == 0,
                f"전이 발견: {[t.name for t in transitions]}")

    # FAILED, TIMEOUT은 터미널이지만 RETRY 복구 경로만 허용
    recoverable_terminal = {TaskStatus.FAILED, TaskStatus.TIMEOUT}
    for ts in recoverable_terminal:
        transitions = VALID_TASK_TRANSITIONS[ts]
        r.check(f"복구 가능 터미널 {ts.name} -> RETRY만 허용",
                len(transitions) == 1 and TaskStatus.RETRY in transitions,
                f"전이: {[t.name for t in transitions]}")

    # is_valid_transition과 VALID_TASK_TRANSITIONS 일관성 전수 검증
    consistency_ok = True
    for from_s in TaskStatus:
        for to_s in TaskStatus:
            expected = to_s in VALID_TASK_TRANSITIONS.get(from_s, ())
            actual = is_valid_transition(from_s, to_s)
            if expected != actual:
                consistency_ok = False
                r.fail(f"일관성 불일치: {from_s.name}->{to_s.name}",
                       f"dict={expected}, func={actual}")
    if consistency_ok:
        r.ok("is_valid_transition과 VALID_TASK_TRANSITIONS 전수 일관성 확인 (225개 조합)")

    # FAILED, TIMEOUT만 RETRY 가능 (복구 경로)
    retry_sources = [s for s in TaskStatus if TaskStatus.RETRY in VALID_TASK_TRANSITIONS.get(s, ())]
    r.check("RETRY 전이 가능 소스 == [FAILED, TIMEOUT]",
            set(retry_sources) == {TaskStatus.FAILED, TaskStatus.TIMEOUT},
            f"실제: {[s.name for s in retry_sources]}")


# =============================================================================
# 섹션 37: Enum 모듈 레벨 속성 및 기타 검증
# =============================================================================
def test_module_level_attributes(r: TestResult) -> None:
    r.set_section("37. 모듈 레벨 속성 및 기타 검증")
    import shared.constants.status_codes as module

    # 모듈 docstring 존재
    r.check("모듈 docstring 존재",
            module.__doc__ is not None and len(module.__doc__) > 0)

    # _ANALYSIS_CATEGORY_MAP 값 확인
    cat_map = module._ANALYSIS_CATEGORY_MAP
    r.check("_ANALYSIS_CATEGORY_MAP 키: training", "training" in cat_map)
    r.check("_ANALYSIS_CATEGORY_MAP 키: game", "game" in cat_map)
    r.check("_ANALYSIS_CATEGORY_MAP 키: referee", "referee" in cat_map)
    r.check("_ANALYSIS_CATEGORY_MAP 키: report", "report" in cat_map)
    r.check("_ANALYSIS_CATEGORY_MAP 키 수 == 4", len(cat_map) == 4,
            f"실제: {len(cat_map)}")

    # 모든 Enum이 to_korean 메서드 보유
    from shared.constants.status_codes import (
        TaskStatus, AnalysisType, AnalysisPhase, ServiceStatus,
        QueuePriority, Environment, TaskType, LearningStatus,
    )
    enums_with_korean = [
        TaskStatus, AnalysisType, AnalysisPhase, ServiceStatus,
        QueuePriority, Environment, TaskType, LearningStatus,
    ]
    for enum_cls in enums_with_korean:
        has_to_korean = all(hasattr(m, "to_korean") for m in enum_cls)
        r.check(f"{enum_cls.__name__} 모든 멤버 to_korean 보유", has_to_korean)

    # to_korean 반환값은 비어있지 않은 문자열
    for enum_cls in enums_with_korean:
        for member in enum_cls:
            kr = member.to_korean()
            r.check(f"{enum_cls.__name__}.{member.name}.to_korean() 비어있지 않음",
                    isinstance(kr, str) and len(kr) > 0,
                    f"실제: '{kr}'")

    # QualityLevel에는 from_score classmethod 존재
    from shared.constants.status_codes import QualityLevel
    r.check("QualityLevel.from_score는 classmethod",
            isinstance(QualityLevel.__dict__["from_score"], classmethod))


# =============================================================================
# 메인 실행
# =============================================================================
def main():
    r = TestResult()

    # 섹션 1-5: TaskStatus
    test_task_status_members(r)
    test_task_status_is_terminal(r)
    test_task_status_is_success(r)
    test_task_status_is_failure(r)
    test_task_status_running_pending_korean(r)

    # 섹션 6-7: AnalysisType
    test_analysis_type_members_category(r)
    test_analysis_type_korean(r)

    # 섹션 8-9: AnalysisPhase
    test_analysis_phase_members_progress(r)
    test_analysis_phase_korean(r)

    # 섹션 10-11: ServiceStatus
    test_service_status_members(r)
    test_service_status_korean(r)

    # 섹션 12-13: QueuePriority
    test_queue_priority_members(r)
    test_queue_priority_korean(r)

    # 섹션 14-15: Environment
    test_environment_members(r)
    test_environment_korean(r)

    # 섹션 16-19: QualityLevel
    test_quality_level_members(r)
    test_quality_level_from_score(r)
    test_quality_level_scores(r)
    test_quality_level_usable_description(r)

    # 섹션 20-22: TaskType
    test_task_type_members(r)
    test_task_type_categories(r)
    test_task_type_korean(r)

    # 섹션 23-25: LearningStatus
    test_learning_status_members(r)
    test_learning_status_properties(r)
    test_learning_status_korean(r)

    # 섹션 26-27: Transitions
    test_valid_task_transitions(r)
    test_is_valid_transition_function(r)

    # 섹션 28: __all__
    test_all_completeness(r)

    # 섹션 29: 캐시
    test_cache_types_completeness(r)

    # 섹션 30: 메타
    test_meta_info(r)

    # 섹션 31: 에지 케이스
    test_edge_cases(r)

    # 섹션 32-34: 상호 배타성
    test_task_status_mutual_exclusivity(r)
    test_learning_status_mutual_exclusivity(r)
    test_task_type_mutual_exclusivity(r)

    # 섹션 35: lru_cache 상세
    test_analysis_type_lru_cache(r)

    # 섹션 36: 전이 무결성
    test_transitions_integrity(r)

    # 섹션 37: 모듈 레벨 속성
    test_module_level_attributes(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(1 if main() > 0 else 0)
