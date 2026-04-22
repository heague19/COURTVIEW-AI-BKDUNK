# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: status_codes.py
설명: 시스템 상태 코드 정의 - 작업 상태, 분석 상태, 서비스 상태 등

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0

참조:
    - pipeline/: 분석 파이프라인에서 TaskStatus, AnalysisPhase 활용
    - api_server/: REST 응답에서 TaskStatus, ServiceStatus 반환
    - workers/: 백그라운드 워커에서 TaskType, LearningStatus 활용
    - infrastructure/validation/: 데이터 품질 검사에서 QualityLevel 사용
    - configs/environments/: Environment 열거형 참조
"""

from __future__ import annotations

# === 표준 라이브러리 ===
from enum import Enum, unique
from functools import lru_cache
from typing import Final


# =============================================================================
# 작업 상태 열거형
# =============================================================================

@unique
class TaskStatus(Enum):
    """
    작업(Task) 상태 열거형.

    비동기 작업의 생명주기를 나타냅니다.

    사용 예시::

        >>> status = TaskStatus.RUNNING
        >>> status.is_running
        True
        >>> status.is_terminal
        False
        >>> status.to_korean()
        '실행 중'
        >>> QualityLevel.from_score(92.5)
        <QualityLevel.EXCELLENT: 'excellent'>
    """

    # 대기 상태
    PENDING = "pending"           # 작업 생성됨, 대기 중
    QUEUED = "queued"             # 큐에 등록됨
    SCHEDULED = "scheduled"       # 스케줄링됨 (예약 실행)

    # 실행 상태
    STARTED = "started"           # 작업 시작됨
    RUNNING = "running"           # 실행 중
    PROCESSING = "processing"     # 처리 중 (세부 단계)

    # 완료 상태
    COMPLETED = "completed"       # 성공적으로 완료
    SUCCESS = "success"           # 성공 (completed와 동일)

    # 실패 상태
    FAILED = "failed"             # 실패
    ERROR = "error"               # 에러 발생 (시스템 예외)
    TIMEOUT = "timeout"           # 시간 초과

    # 취소 상태
    CANCELLED = "cancelled"       # 사용자에 의해 취소
    REVOKED = "revoked"           # 시스템에 의해 취소

    # 재시도 상태
    RETRY = "retry"               # 재시도 예정
    RETRYING = "retrying"         # 재시도 중

    @property
    def is_terminal(self) -> bool:
        """종료 상태인지 확인."""
        return self in _TASK_STATUS_TERMINAL

    @property
    def is_success(self) -> bool:
        """성공 상태인지 확인."""
        return self in _TASK_STATUS_SUCCESS

    @property
    def is_failure(self) -> bool:
        """실패 상태인지 확인."""
        return self in _TASK_STATUS_FAILURE

    @property
    def is_running(self) -> bool:
        """실행 중인지 확인."""
        return self in _TASK_STATUS_RUNNING

    @property
    def is_pending(self) -> bool:
        """대기 중인지 확인."""
        return self in _TASK_STATUS_PENDING

    def to_korean(self) -> str:
        """한글 상태명 반환."""
        return _TASK_STATUS_KOREAN_MAP[self]

    def __str__(self) -> str:
        """문자열 표현."""
        return self.value


# TaskStatus 분류 캐시 (클래스 정의 후 초기화)
_TASK_STATUS_TERMINAL: Final[frozenset[TaskStatus]] = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.SUCCESS,
    TaskStatus.FAILED,
    TaskStatus.ERROR,
    TaskStatus.TIMEOUT,
    TaskStatus.CANCELLED,
    TaskStatus.REVOKED,
})

_TASK_STATUS_SUCCESS: Final[frozenset[TaskStatus]] = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.SUCCESS,
})

_TASK_STATUS_FAILURE: Final[frozenset[TaskStatus]] = frozenset({
    TaskStatus.FAILED,
    TaskStatus.ERROR,
    TaskStatus.TIMEOUT,
})

_TASK_STATUS_RUNNING: Final[frozenset[TaskStatus]] = frozenset({
    TaskStatus.STARTED,
    TaskStatus.RUNNING,
    TaskStatus.PROCESSING,
    TaskStatus.RETRYING,
})

_TASK_STATUS_PENDING: Final[frozenset[TaskStatus]] = frozenset({
    TaskStatus.PENDING,
    TaskStatus.QUEUED,
    TaskStatus.SCHEDULED,
    TaskStatus.RETRY,
})

_TASK_STATUS_KOREAN_MAP: Final[dict[TaskStatus, str]] = {
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


# =============================================================================
# 카테고리 매핑 (성능 최적화용 - 모듈 로드 시 한 번만 생성)
# =============================================================================

_ANALYSIS_CATEGORY_MAP: Final[dict[str, str]] = {
    "training": "training",
    "game": "game",
    "referee": "referee",
    "report": "report",
}


@lru_cache(maxsize=None)
def _get_analysis_category(value: str) -> str:
    """
    분석 값에서 카테고리를 추출 (캐시 적용).

    Args:
        value: 분석 유형의 문자열 값 (예: "training_shooting")

    Returns:
        해당 분석의 카테고리 (training, game, referee, report, unknown)
    """
    prefix = value.split("_")[0]
    return _ANALYSIS_CATEGORY_MAP.get(prefix, "unknown")


# =============================================================================
# 분석 유형 열거형
# =============================================================================

@unique
class AnalysisType(Enum):
    """
    분석 유형 열거형.

    COURTVIEW가 지원하는 모든 분석 유형을 정의합니다.
    """

    # 훈련 분석
    TRAINING_SHOOTING = "training_shooting"       # 슈팅 훈련 분석
    TRAINING_DRIBBLING = "training_dribbling"     # 드리블 훈련 분석
    TRAINING_PASSING = "training_passing"         # 패스 훈련 분석
    TRAINING_DEFENSE = "training_defense"         # 수비 훈련 분석
    TRAINING_MOVEMENT = "training_movement"       # 이동 훈련 분석
    TRAINING_COMPARISON = "training_comparison"   # 정답 영상 비교 분석

    # 경기 분석
    GAME_FULL = "game_full"                       # 전체 경기 분석
    GAME_HIGHLIGHTS = "game_highlights"           # 하이라이트 추출
    GAME_STATISTICS = "game_statistics"           # 통계 분석
    GAME_SHOT_CHART = "game_shot_chart"           # 슛 차트 분석

    # AI 심판
    REFEREE_FULL = "referee_full"                 # 전체 심판 분석
    REFEREE_VIOLATION = "referee_violation"       # 바이올레이션 감지
    REFEREE_FOUL = "referee_foul"                 # 파울 감지

    # 레포트
    REPORT_WEEKLY = "report_weekly"               # 주간 레포트
    REPORT_PROGRESS = "report_progress"           # 진행 추적 레포트

    @property
    def category(self) -> str:
        """
        분석 카테고리 반환.

        성능 최적화: @lru_cache가 적용된 _get_analysis_category() 함수를 호출.
        첫 호출 이후 O(1) 캐시 조회로 동작.
        """
        return _get_analysis_category(self.value)

    def to_korean(self) -> str:
        """한글 분석 유형명 반환."""
        return _ANALYSIS_TYPE_KOREAN_MAP[self]

    def __str__(self) -> str:
        """문자열 표현."""
        return self.value


# AnalysisType 한글 맵 (클래스 정의 후 초기화)
_ANALYSIS_TYPE_KOREAN_MAP: Final[dict[AnalysisType, str]] = {
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


# =============================================================================
# 분석 단계 열거형
# =============================================================================

@unique
class AnalysisPhase(Enum):
    """
    분석 단계 열거형.

    분석 파이프라인의 각 단계를 나타냅니다.
    """

    INITIALIZED = "initialized"           # 초기화됨
    DOWNLOADING = "downloading"           # 영상 다운로드 중
    PREPROCESSING = "preprocessing"       # 전처리 중
    DETECTING = "detecting"               # 객체 감지 중
    POSE_ESTIMATING = "pose_estimating"   # 포즈 추정 중
    ANALYZING = "analyzing"               # 분석 중
    GENERATING_FEEDBACK = "generating_feedback"  # 피드백 생성 중
    POSTPROCESSING = "postprocessing"     # 후처리 중
    UPLOADING = "uploading"               # 결과 업로드 중
    FINALIZING = "finalizing"             # 마무리 중
    DONE = "done"                         # 완료

    def to_korean(self) -> str:
        """한글 단계명 반환."""
        return _ANALYSIS_PHASE_KOREAN_MAP[self]

    @property
    def progress_percent(self) -> int:
        """단계별 대략적인 진행률 반환."""
        return _ANALYSIS_PHASE_PROGRESS_MAP[self]

    def __str__(self) -> str:
        """문자열 표현."""
        return self.value


# AnalysisPhase 캐시 (클래스 정의 후 초기화)
_ANALYSIS_PHASE_KOREAN_MAP: Final[dict[AnalysisPhase, str]] = {
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

_ANALYSIS_PHASE_PROGRESS_MAP: Final[dict[AnalysisPhase, int]] = {
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


# =============================================================================
# 서비스 상태 열거형
# =============================================================================

@unique
class ServiceStatus(Enum):
    """
    서비스 상태 열거형.

    마이크로서비스 및 컴포넌트의 상태를 나타냅니다.
    """

    UNKNOWN = "unknown"           # 알 수 없음
    STARTING = "starting"         # 시작 중
    HEALTHY = "healthy"           # 정상
    DEGRADED = "degraded"         # 성능 저하
    UNHEALTHY = "unhealthy"       # 비정상
    STOPPING = "stopping"         # 종료 중
    STOPPED = "stopped"           # 종료됨
    MAINTENANCE = "maintenance"   # 유지보수 중

    @property
    def is_available(self) -> bool:
        """서비스 사용 가능 여부."""
        return self in _SERVICE_STATUS_AVAILABLE

    @property
    def is_healthy(self) -> bool:
        """정상 상태 여부."""
        return self == ServiceStatus.HEALTHY

    def to_korean(self) -> str:
        """한글 상태명 반환."""
        return _SERVICE_STATUS_KOREAN_MAP[self]

    def __str__(self) -> str:
        """문자열 표현."""
        return self.value


# ServiceStatus 캐시 (클래스 정의 후 초기화)
_SERVICE_STATUS_AVAILABLE: Final[frozenset[ServiceStatus]] = frozenset({
    ServiceStatus.HEALTHY,
    ServiceStatus.DEGRADED,
})

_SERVICE_STATUS_KOREAN_MAP: Final[dict[ServiceStatus, str]] = {
    ServiceStatus.UNKNOWN: "알 수 없음",
    ServiceStatus.STARTING: "시작 중",
    ServiceStatus.HEALTHY: "정상",
    ServiceStatus.DEGRADED: "성능 저하",
    ServiceStatus.UNHEALTHY: "비정상",
    ServiceStatus.STOPPING: "종료 중",
    ServiceStatus.STOPPED: "종료됨",
    ServiceStatus.MAINTENANCE: "유지보수 중",
}


# =============================================================================
# 큐 우선순위 열거형
# =============================================================================

@unique
class QueuePriority(Enum):
    """
    작업 큐 우선순위 열거형.
    """

    CRITICAL = 0    # 긴급 (즉시 처리)
    HIGH = 1        # 높음
    NORMAL = 2      # 보통
    LOW = 3         # 낮음
    BACKGROUND = 4  # 백그라운드

    def to_korean(self) -> str:
        """한글 우선순위명 반환."""
        return _QUEUE_PRIORITY_KOREAN_MAP[self]

    def __str__(self) -> str:
        """문자열 표현."""
        return self.name


# QueuePriority 한글 맵 (클래스 정의 후 초기화)
_QUEUE_PRIORITY_KOREAN_MAP: Final[dict[QueuePriority, str]] = {
    QueuePriority.CRITICAL: "긴급",
    QueuePriority.HIGH: "높음",
    QueuePriority.NORMAL: "보통",
    QueuePriority.LOW: "낮음",
    QueuePriority.BACKGROUND: "백그라운드",
}


# =============================================================================
# 실행 환경 열거형
# =============================================================================

@unique
class Environment(Enum):
    """
    실행 환경 열거형.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"

    @property
    def is_production(self) -> bool:
        """프로덕션 환경인지 확인."""
        return self == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """개발 환경인지 확인."""
        return self == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """테스트 환경인지 확인."""
        return self == Environment.TESTING

    def to_korean(self) -> str:
        """한글 환경명 반환."""
        return _ENVIRONMENT_KOREAN_MAP[self]

    def __str__(self) -> str:
        """문자열 표현."""
        return self.value


# Environment 한글 맵 (클래스 정의 후 초기화)
_ENVIRONMENT_KOREAN_MAP: Final[dict[Environment, str]] = {
    Environment.DEVELOPMENT: "개발",
    Environment.STAGING: "스테이징",
    Environment.PRODUCTION: "프로덕션",
    Environment.TESTING: "테스트",
}


# =============================================================================
# 상태 전이 규칙 (State Transition Rules)
# =============================================================================

# TaskStatus 허용된 전이 (immutable Tuple 사용)
VALID_TASK_TRANSITIONS: Final[dict[TaskStatus, tuple[TaskStatus, ...]]] = {
    TaskStatus.PENDING: (TaskStatus.QUEUED, TaskStatus.CANCELLED),
    TaskStatus.QUEUED: (TaskStatus.STARTED, TaskStatus.CANCELLED, TaskStatus.REVOKED),
    TaskStatus.SCHEDULED: (TaskStatus.QUEUED, TaskStatus.CANCELLED),
    TaskStatus.STARTED: (
        TaskStatus.RUNNING,
        TaskStatus.FAILED,
        TaskStatus.ERROR,
        TaskStatus.CANCELLED,
    ),
    TaskStatus.RUNNING: (
        TaskStatus.PROCESSING,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.ERROR,
        TaskStatus.TIMEOUT,
        TaskStatus.CANCELLED,
    ),
    TaskStatus.PROCESSING: (
        TaskStatus.RUNNING,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.ERROR,
        TaskStatus.TIMEOUT,
    ),
    TaskStatus.FAILED: (TaskStatus.RETRY,),
    TaskStatus.TIMEOUT: (TaskStatus.RETRY,),
    TaskStatus.RETRY: (TaskStatus.RETRYING, TaskStatus.CANCELLED),
    TaskStatus.RETRYING: (
        TaskStatus.RUNNING,
        TaskStatus.FAILED,
        TaskStatus.ERROR,
        TaskStatus.CANCELLED,
    ),
    # 종료 상태는 전이 없음
    TaskStatus.COMPLETED: (),
    TaskStatus.SUCCESS: (),
    TaskStatus.CANCELLED: (),
    TaskStatus.REVOKED: (),
    TaskStatus.ERROR: (),
}


# =============================================================================
# 품질 레벨 정의
# =============================================================================

@unique
class QualityLevel(Enum):
    """
    데이터 품질 레벨 정의.

    품질 검사 결과를 표준화된 레벨로 분류합니다.

    Attributes:
        EXCELLENT: 최상 품질 (90-100점)
        GOOD: 양호 품질 (75-89점)
        ACCEPTABLE: 허용 가능 품질 (60-74점)
        POOR: 낮은 품질 (40-59점)
        UNACCEPTABLE: 사용 불가 품질 (0-39점)
    """

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNACCEPTABLE = "unacceptable"

    @property
    def description(self) -> str:
        """품질 레벨 설명."""
        return _QUALITY_LEVEL_DESC_MAP[self]

    @property
    def min_score(self) -> int:
        """최소 점수."""
        return _QUALITY_LEVEL_MIN_SCORE_MAP[self]

    @property
    def max_score(self) -> int:
        """최대 점수."""
        return _QUALITY_LEVEL_MAX_SCORE_MAP[self]

    @classmethod
    def from_score(cls, score: float) -> "QualityLevel":
        """
        점수로부터 품질 레벨 결정.

        Args:
            score: 품질 점수 (0-100)

        Returns:
            QualityLevel: 해당하는 품질 레벨

        Raises:
            ValueError: 점수가 0-100 범위를 벗어난 경우
        """
        if not 0.0 <= score <= 100.0:
            raise ValueError(f"품질 점수는 0-100 범위여야 합니다: {score}")

        if score >= 90:
            return cls.EXCELLENT
        elif score >= 75:
            return cls.GOOD
        elif score >= 60:
            return cls.ACCEPTABLE
        elif score >= 40:
            return cls.POOR
        else:
            return cls.UNACCEPTABLE

    @property
    def is_usable(self) -> bool:
        """분석에 사용 가능한지 여부."""
        return self in _QUALITY_LEVEL_USABLE

    def __str__(self) -> str:
        """문자열 표현."""
        return self.value


# QualityLevel 캐시 (클래스 정의 후 초기화)
_QUALITY_LEVEL_USABLE: Final[frozenset[QualityLevel]] = frozenset({
    QualityLevel.EXCELLENT,
    QualityLevel.GOOD,
    QualityLevel.ACCEPTABLE,
})

_QUALITY_LEVEL_DESC_MAP: Final[dict[QualityLevel, str]] = {
    QualityLevel.EXCELLENT: "최상 품질 - 분석에 최적화됨",
    QualityLevel.GOOD: "양호 품질 - 정확한 분석 가능",
    QualityLevel.ACCEPTABLE: "허용 품질 - 기본 분석 가능",
    QualityLevel.POOR: "낮은 품질 - 분석 정확도 저하 가능",
    QualityLevel.UNACCEPTABLE: "사용 불가 - 분석 불가능",
}

_QUALITY_LEVEL_MIN_SCORE_MAP: Final[dict[QualityLevel, int]] = {
    QualityLevel.EXCELLENT: 90,
    QualityLevel.GOOD: 75,
    QualityLevel.ACCEPTABLE: 60,
    QualityLevel.POOR: 40,
    QualityLevel.UNACCEPTABLE: 0,
}

_QUALITY_LEVEL_MAX_SCORE_MAP: Final[dict[QualityLevel, int]] = {
    QualityLevel.EXCELLENT: 100,
    QualityLevel.GOOD: 89,
    QualityLevel.ACCEPTABLE: 74,
    QualityLevel.POOR: 59,
    QualityLevel.UNACCEPTABLE: 39,
}


# =============================================================================
# 작업 유형 열거형
# =============================================================================

@unique
class TaskType(Enum):
    """
    작업(Task) 유형 열거형.

    COURTVIEW 시스템의 비동기 작업 유형을 정의합니다.
    """

    # 분석 작업
    ANALYSIS_TRAINING = "analysis_training"          # 훈련 분석
    ANALYSIS_COMPARISON = "analysis_comparison"      # 비교 분석
    ANALYSIS_GAME = "analysis_game"                  # 경기 분석
    ANALYSIS_REFEREE = "analysis_referee"            # 심판 분석

    # 리포트 작업
    REPORT_WEEKLY = "report_weekly"                  # 주간 리포트
    REPORT_PROGRESS = "report_progress"              # 진행 리포트
    REPORT_CUSTOM = "report_custom"                  # 커스텀 리포트

    # 처리 작업
    VIDEO_PROCESSING = "video_processing"            # 영상 처리
    BODY_SCAN = "body_scan"                          # 신체 스캔
    HIGHLIGHT_EXTRACTION = "highlight_extraction"    # 하이라이트 추출

    # 학습 작업
    LEARNING_TRAINING = "learning_training"          # 모델 학습
    LEARNING_VALIDATION = "learning_validation"      # 모델 검증

    # 내보내기 작업
    EXPORT_VIDEO = "export_video"                    # 영상 내보내기
    EXPORT_REPORT = "export_report"                  # 리포트 내보내기

    # 배치 작업
    BATCH_ANALYSIS = "batch_analysis"                # 대량 분석

    def to_korean(self) -> str:
        """한글 유형명 반환."""
        return _TASK_TYPE_KOREAN_MAP[self]

    @property
    def is_analysis(self) -> bool:
        """분석 작업인지 확인."""
        return self in _TASK_TYPE_ANALYSIS

    @property
    def is_report(self) -> bool:
        """리포트 작업인지 확인."""
        return self in _TASK_TYPE_REPORT

    @property
    def is_learning(self) -> bool:
        """학습 작업인지 확인."""
        return self in _TASK_TYPE_LEARNING

    def __str__(self) -> str:
        """문자열 표현."""
        return self.value


# TaskType 캐시 (클래스 정의 후 초기화)
_TASK_TYPE_ANALYSIS: Final[frozenset[TaskType]] = frozenset({
    TaskType.ANALYSIS_TRAINING,
    TaskType.ANALYSIS_COMPARISON,
    TaskType.ANALYSIS_GAME,
    TaskType.ANALYSIS_REFEREE,
})

_TASK_TYPE_REPORT: Final[frozenset[TaskType]] = frozenset({
    TaskType.REPORT_WEEKLY,
    TaskType.REPORT_PROGRESS,
    TaskType.REPORT_CUSTOM,
})

_TASK_TYPE_LEARNING: Final[frozenset[TaskType]] = frozenset({
    TaskType.LEARNING_TRAINING,
    TaskType.LEARNING_VALIDATION,
})

_TASK_TYPE_KOREAN_MAP: Final[dict[TaskType, str]] = {
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


# =============================================================================
# 학습 시스템 상태 열거형
# =============================================================================

@unique
class LearningStatus(Enum):
    """
    학습 시스템 상태 열거형.

    COURTVIEW 학습 시스템의 상태를 나타냅니다.
    """

    # 대기/준비 상태
    IDLE = "idle"                       # 유휴 상태 (학습 대기)
    READY = "ready"                     # 학습 준비 완료
    PREPARING = "preparing"             # 학습 준비 중

    # 학습 진행 상태
    TRAINING = "training"               # 모델 학습 중
    VALIDATING = "validating"           # 검증 중
    OPTIMIZING = "optimizing"           # 최적화 중

    # 완료 상태
    COMPLETED = "completed"             # 학습 완료
    DEPLOYED = "deployed"               # 배포 완료

    # 실패/중단 상태
    FAILED = "failed"                   # 학습 실패
    CANCELLED = "cancelled"             # 학습 취소
    PAUSED = "paused"                   # 학습 일시 정지

    # 롤백 상태
    ROLLING_BACK = "rolling_back"       # 롤백 진행 중
    ROLLED_BACK = "rolled_back"         # 롤백 완료

    @property
    def is_active(self) -> bool:
        """학습 진행 중인지 확인."""
        return self in _LEARNING_STATUS_ACTIVE

    @property
    def is_terminal(self) -> bool:
        """종료 상태인지 확인."""
        return self in _LEARNING_STATUS_TERMINAL

    @property
    def can_trigger_learning(self) -> bool:
        """학습을 트리거할 수 있는 상태인지 확인."""
        return self in _LEARNING_STATUS_CAN_TRIGGER

    def to_korean(self) -> str:
        """한글 상태명 반환."""
        return _LEARNING_STATUS_KOREAN_MAP[self]

    def __str__(self) -> str:
        """문자열 표현."""
        return self.value


# LearningStatus 캐시 (클래스 정의 후 초기화)
_LEARNING_STATUS_ACTIVE: Final[frozenset[LearningStatus]] = frozenset({
    LearningStatus.PREPARING,
    LearningStatus.TRAINING,
    LearningStatus.VALIDATING,
    LearningStatus.OPTIMIZING,
    LearningStatus.ROLLING_BACK,
})

_LEARNING_STATUS_TERMINAL: Final[frozenset[LearningStatus]] = frozenset({
    LearningStatus.COMPLETED,
    LearningStatus.DEPLOYED,
    LearningStatus.FAILED,
    LearningStatus.CANCELLED,
    LearningStatus.ROLLED_BACK,
})

_LEARNING_STATUS_CAN_TRIGGER: Final[frozenset[LearningStatus]] = frozenset({
    LearningStatus.IDLE,
    LearningStatus.READY,
    LearningStatus.COMPLETED,
    LearningStatus.DEPLOYED,
    LearningStatus.FAILED,
    LearningStatus.CANCELLED,
    LearningStatus.ROLLED_BACK,
})

_LEARNING_STATUS_KOREAN_MAP: Final[dict[LearningStatus, str]] = {
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


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 작업 상태
    "TaskStatus",
    # 작업 유형
    "TaskType",
    # 분석 유형
    "AnalysisType",
    # 분석 단계
    "AnalysisPhase",
    # 서비스 상태
    "ServiceStatus",
    # 큐 우선순위
    "QueuePriority",
    # 실행 환경
    "Environment",
    # 품질 레벨
    "QualityLevel",
    # 학습 상태
    "LearningStatus",
    # 상태 전이 규칙
    "VALID_TASK_TRANSITIONS",
]

# 모듈 버전 정보
__version__ = "1.0.0"
