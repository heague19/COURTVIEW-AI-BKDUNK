# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: event_types.py
설명: 이벤트 타입 상수 정의 - 이벤트 버스, 웹훅, 실시간 알림에서 사용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0
"""

from enum import Enum, unique
from functools import lru_cache
from typing import Final


# =============================================================================
# 이벤트 카테고리 열거형
# =============================================================================

@unique
class EventCategory(Enum):
    """
    이벤트 카테고리 열거형.

    이벤트의 대분류를 나타냅니다.
    """

    SYSTEM = "system"           # 시스템 이벤트
    ANALYSIS = "analysis"       # 분석 이벤트
    GAME = "game"               # 경기 이벤트
    REFEREE = "referee"         # 심판 이벤트
    FEEDBACK = "feedback"       # 피드백 이벤트
    LEARNING = "learning"       # 학습 이벤트
    USER = "user"               # 사용자 이벤트
    INFRASTRUCTURE = "infra"    # 인프라 이벤트

    def to_korean(self) -> str:
        """한글 카테고리명 반환."""
        return _EVENT_CATEGORY_KOREAN_MAP[self]


# EventCategory 한글 맵 (클래스 정의 후 초기화)
_EVENT_CATEGORY_KOREAN_MAP: dict[EventCategory, str] = {
    EventCategory.SYSTEM: "시스템",
    EventCategory.ANALYSIS: "분석",
    EventCategory.GAME: "경기",
    EventCategory.REFEREE: "심판",
    EventCategory.FEEDBACK: "피드백",
    EventCategory.LEARNING: "학습",
    EventCategory.USER: "사용자",
    EventCategory.INFRASTRUCTURE: "인프라",
}


# =============================================================================
# 카테고리 매핑 (성능 최적화용 - 모듈 로드 시 한 번만 생성)
# =============================================================================

_CATEGORY_MAP: Final[dict[str, EventCategory]] = {
    "system": EventCategory.SYSTEM,
    "task": EventCategory.ANALYSIS,
    "analysis": EventCategory.ANALYSIS,
    "game": EventCategory.GAME,
    "referee": EventCategory.REFEREE,
    "feedback": EventCategory.FEEDBACK,
    "report": EventCategory.FEEDBACK,
    "learning": EventCategory.LEARNING,
    "infra": EventCategory.INFRASTRUCTURE,
    "model": EventCategory.SYSTEM,
}


@lru_cache(maxsize=None)
def _get_event_category(event_value: str) -> EventCategory:
    """
    이벤트 값에서 카테고리를 추출 (캐시 적용).

    Args:
        event_value: 이벤트의 문자열 값 (예: "task.completed")

    Returns:
        해당 이벤트의 카테고리
    """
    prefix = event_value.split(".")[0]
    return _CATEGORY_MAP.get(prefix, EventCategory.SYSTEM)


# =============================================================================
# 이벤트 타입 열거형
# =============================================================================

@unique
class EventType(Enum):
    """
    이벤트 타입 열거형.

    시스템 전체에서 발생하는 모든 이벤트 유형을 정의합니다.

    네이밍 규칙: {도메인}.{동작}.{상태}
    예: analysis.shooting.completed
    """

    # ==================== 시스템 이벤트 ====================

    SYSTEM_STARTED = "system.started"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_HEALTH_CHECK = "system.health.check"
    SYSTEM_HEALTH_CHANGED = "system.health.changed"
    SYSTEM_CONFIG_RELOADED = "system.config.reloaded"
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"

    # ==================== 분석 작업 이벤트 ====================

    # 작업 생명주기
    TASK_CREATED = "task.created"
    TASK_QUEUED = "task.queued"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_TIMEOUT = "task.timeout"
    TASK_RETRYING = "task.retrying"

    # ==================== 훈련 분석 이벤트 ====================

    # 슈팅 분석
    ANALYSIS_SHOOTING_STARTED = "analysis.shooting.started"
    ANALYSIS_SHOOTING_PROGRESS = "analysis.shooting.progress"
    ANALYSIS_SHOOTING_COMPLETED = "analysis.shooting.completed"
    ANALYSIS_SHOOTING_FAILED = "analysis.shooting.failed"

    # 드리블 분석
    ANALYSIS_DRIBBLING_STARTED = "analysis.dribbling.started"
    ANALYSIS_DRIBBLING_PROGRESS = "analysis.dribbling.progress"
    ANALYSIS_DRIBBLING_COMPLETED = "analysis.dribbling.completed"
    ANALYSIS_DRIBBLING_FAILED = "analysis.dribbling.failed"

    # 패스 분석
    ANALYSIS_PASSING_STARTED = "analysis.passing.started"
    ANALYSIS_PASSING_COMPLETED = "analysis.passing.completed"

    # 수비 분석
    ANALYSIS_DEFENSE_STARTED = "analysis.defense.started"
    ANALYSIS_DEFENSE_COMPLETED = "analysis.defense.completed"

    # 동작 비교 분석
    ANALYSIS_COMPARISON_STARTED = "analysis.comparison.started"
    ANALYSIS_COMPARISON_COMPLETED = "analysis.comparison.completed"

    # ==================== 경기 분석 이벤트 ====================

    GAME_ANALYSIS_STARTED = "game.analysis.started"
    GAME_ANALYSIS_PROGRESS = "game.analysis.progress"
    GAME_ANALYSIS_COMPLETED = "game.analysis.completed"
    GAME_ANALYSIS_FAILED = "game.analysis.failed"

    # 경기 중 감지 이벤트
    GAME_SHOT_DETECTED = "game.shot.detected"
    GAME_SCORE_DETECTED = "game.score.detected"
    GAME_REBOUND_DETECTED = "game.rebound.detected"
    GAME_ASSIST_DETECTED = "game.assist.detected"
    GAME_STEAL_DETECTED = "game.steal.detected"
    GAME_BLOCK_DETECTED = "game.block.detected"
    GAME_TURNOVER_DETECTED = "game.turnover.detected"

    # 하이라이트 이벤트
    HIGHLIGHT_DETECTED = "game.highlight.detected"
    HIGHLIGHT_EXTRACTED = "game.highlight.extracted"

    # 통계 이벤트
    STATISTICS_GENERATED = "game.statistics.generated"
    SHOT_CHART_GENERATED = "game.shotchart.generated"

    # ==================== AI 심판 이벤트 ====================

    REFEREE_ANALYSIS_STARTED = "referee.analysis.started"
    REFEREE_ANALYSIS_COMPLETED = "referee.analysis.completed"
    REFEREE_ANALYSIS_FAILED = "referee.analysis.failed"

    # 바이올레이션 감지
    VIOLATION_DETECTED = "referee.violation.detected"
    VIOLATION_TRAVELING = "referee.violation.traveling"
    VIOLATION_DOUBLE_DRIBBLE = "referee.violation.double_dribble"
    VIOLATION_BACKCOURT = "referee.violation.backcourt"
    VIOLATION_SHOT_CLOCK = "referee.violation.shot_clock"
    VIOLATION_3_SECOND = "referee.violation.3_second"
    VIOLATION_5_SECOND = "referee.violation.5_second"
    VIOLATION_8_SECOND = "referee.violation.8_second"
    VIOLATION_OUT_OF_BOUNDS = "referee.violation.out_of_bounds"

    # 파울 감지
    FOUL_DETECTED = "referee.foul.detected"
    FOUL_PERSONAL = "referee.foul.personal"
    FOUL_OFFENSIVE = "referee.foul.offensive"
    FOUL_DEFENSIVE = "referee.foul.defensive"
    FOUL_TECHNICAL = "referee.foul.technical"
    FOUL_FLAGRANT = "referee.foul.flagrant"

    # ==================== 피드백 이벤트 ====================

    FEEDBACK_GENERATED = "feedback.generated"
    FEEDBACK_SHOOTING_GENERATED = "feedback.shooting.generated"
    FEEDBACK_DRIBBLING_GENERATED = "feedback.dribbling.generated"
    FEEDBACK_DEFENSE_GENERATED = "feedback.defense.generated"

    RECOMMENDATION_GENERATED = "feedback.recommendation.generated"
    DRILL_RECOMMENDED = "feedback.drill.recommended"

    REPORT_WEEKLY_GENERATED = "report.weekly.generated"
    REPORT_PROGRESS_GENERATED = "report.progress.generated"

    # ==================== 학습 시스템 이벤트 ====================

    LEARNING_PATTERN_DETECTED = "learning.pattern.detected"
    LEARNING_MODEL_UPDATED = "learning.model.updated"
    LEARNING_THRESHOLD_ADJUSTED = "learning.threshold.adjusted"
    LEARNING_ACCURACY_IMPROVED = "learning.accuracy.improved"

    # ==================== 인프라 이벤트 ====================

    # 캐시 이벤트
    CACHE_HIT = "infra.cache.hit"
    CACHE_MISS = "infra.cache.miss"
    CACHE_EVICTED = "infra.cache.evicted"

    # 큐 이벤트
    QUEUE_MESSAGE_PUBLISHED = "infra.queue.published"
    QUEUE_MESSAGE_CONSUMED = "infra.queue.consumed"
    QUEUE_MESSAGE_FAILED = "infra.queue.failed"
    QUEUE_MESSAGE_DEAD_LETTER = "infra.queue.dead_letter"

    # 스토리지 이벤트
    STORAGE_FILE_UPLOADED = "infra.storage.uploaded"
    STORAGE_FILE_DOWNLOADED = "infra.storage.downloaded"
    STORAGE_FILE_DELETED = "infra.storage.deleted"

    # 데이터베이스 이벤트
    DATABASE_QUERY_SLOW = "infra.database.slow_query"
    DATABASE_CONNECTION_LOST = "infra.database.connection_lost"
    DATABASE_CONNECTION_RESTORED = "infra.database.connection_restored"

    # ==================== 모델 이벤트 ====================

    MODEL_LOADED = "model.loaded"
    MODEL_UNLOADED = "model.unloaded"
    MODEL_INFERENCE_STARTED = "model.inference.started"
    MODEL_INFERENCE_COMPLETED = "model.inference.completed"
    MODEL_INFERENCE_FAILED = "model.inference.failed"

    @property
    def category(self) -> EventCategory:
        """
        이벤트 카테고리 반환.

        성능 최적화: @lru_cache가 적용된 _get_event_category() 함수를 호출.
        첫 호출 이후 O(1) 캐시 조회로 동작.
        """
        return _get_event_category(self.value)

    @property
    def is_error_event(self) -> bool:
        """에러 관련 이벤트인지 확인."""
        return "failed" in self.value or "error" in self.value

    @property
    def is_progress_event(self) -> bool:
        """진행 상황 이벤트인지 확인."""
        return "progress" in self.value or "started" in self.value

    def to_korean(self) -> str:
        """한글 이벤트명 반환."""
        return _EVENT_TYPE_KOREAN_MAP[self]


# =============================================================================
# EventType 한글 맵 (93개 전수 매핑)
# =============================================================================

_EVENT_TYPE_KOREAN_MAP: dict[EventType, str] = {
    # 시스템 이벤트
    EventType.SYSTEM_STARTED: "시스템 시작",
    EventType.SYSTEM_SHUTDOWN: "시스템 종료",
    EventType.SYSTEM_HEALTH_CHECK: "시스템 상태 점검",
    EventType.SYSTEM_HEALTH_CHANGED: "시스템 상태 변경",
    EventType.SYSTEM_CONFIG_RELOADED: "설정 리로드",
    EventType.SYSTEM_ERROR: "시스템 오류",
    EventType.SYSTEM_WARNING: "시스템 경고",

    # 작업 생명주기
    EventType.TASK_CREATED: "작업 생성됨",
    EventType.TASK_QUEUED: "작업 큐 등록됨",
    EventType.TASK_STARTED: "작업 시작됨",
    EventType.TASK_PROGRESS: "작업 진행 중",
    EventType.TASK_COMPLETED: "작업 완료됨",
    EventType.TASK_FAILED: "작업 실패",
    EventType.TASK_CANCELLED: "작업 취소됨",
    EventType.TASK_TIMEOUT: "작업 시간 초과",
    EventType.TASK_RETRYING: "작업 재시도 중",

    # 슈팅 분석
    EventType.ANALYSIS_SHOOTING_STARTED: "슈팅 분석 시작",
    EventType.ANALYSIS_SHOOTING_PROGRESS: "슈팅 분석 진행 중",
    EventType.ANALYSIS_SHOOTING_COMPLETED: "슈팅 분석 완료",
    EventType.ANALYSIS_SHOOTING_FAILED: "슈팅 분석 실패",

    # 드리블 분석
    EventType.ANALYSIS_DRIBBLING_STARTED: "드리블 분석 시작",
    EventType.ANALYSIS_DRIBBLING_PROGRESS: "드리블 분석 진행 중",
    EventType.ANALYSIS_DRIBBLING_COMPLETED: "드리블 분석 완료",
    EventType.ANALYSIS_DRIBBLING_FAILED: "드리블 분석 실패",

    # 패스 분석
    EventType.ANALYSIS_PASSING_STARTED: "패스 분석 시작",
    EventType.ANALYSIS_PASSING_COMPLETED: "패스 분석 완료",

    # 수비 분석
    EventType.ANALYSIS_DEFENSE_STARTED: "수비 분석 시작",
    EventType.ANALYSIS_DEFENSE_COMPLETED: "수비 분석 완료",

    # 동작 비교 분석
    EventType.ANALYSIS_COMPARISON_STARTED: "동작 비교 분석 시작",
    EventType.ANALYSIS_COMPARISON_COMPLETED: "동작 비교 분석 완료",

    # 경기 분석
    EventType.GAME_ANALYSIS_STARTED: "경기 분석 시작",
    EventType.GAME_ANALYSIS_PROGRESS: "경기 분석 진행 중",
    EventType.GAME_ANALYSIS_COMPLETED: "경기 분석 완료",
    EventType.GAME_ANALYSIS_FAILED: "경기 분석 실패",

    # 경기 감지
    EventType.GAME_SHOT_DETECTED: "슛 감지",
    EventType.GAME_SCORE_DETECTED: "득점 감지",
    EventType.GAME_REBOUND_DETECTED: "리바운드 감지",
    EventType.GAME_ASSIST_DETECTED: "어시스트 감지",
    EventType.GAME_STEAL_DETECTED: "스틸 감지",
    EventType.GAME_BLOCK_DETECTED: "블록 감지",
    EventType.GAME_TURNOVER_DETECTED: "턴오버 감지",

    # 하이라이트
    EventType.HIGHLIGHT_DETECTED: "하이라이트 감지",
    EventType.HIGHLIGHT_EXTRACTED: "하이라이트 추출",

    # 통계
    EventType.STATISTICS_GENERATED: "통계 생성",
    EventType.SHOT_CHART_GENERATED: "슛 차트 생성",

    # AI 심판
    EventType.REFEREE_ANALYSIS_STARTED: "AI 심판 분석 시작",
    EventType.REFEREE_ANALYSIS_COMPLETED: "AI 심판 분석 완료",
    EventType.REFEREE_ANALYSIS_FAILED: "AI 심판 분석 실패",

    # 바이올레이션
    EventType.VIOLATION_DETECTED: "바이올레이션 감지",
    EventType.VIOLATION_TRAVELING: "트래블링 감지",
    EventType.VIOLATION_DOUBLE_DRIBBLE: "더블 드리블 감지",
    EventType.VIOLATION_BACKCOURT: "백코트 바이올레이션 감지",
    EventType.VIOLATION_SHOT_CLOCK: "샷 클락 바이올레이션 감지",
    EventType.VIOLATION_3_SECOND: "3초 바이올레이션 감지",
    EventType.VIOLATION_5_SECOND: "5초 바이올레이션 감지",
    EventType.VIOLATION_8_SECOND: "8초 바이올레이션 감지",
    EventType.VIOLATION_OUT_OF_BOUNDS: "아웃 오브 바운즈 감지",

    # 파울
    EventType.FOUL_DETECTED: "파울 감지",
    EventType.FOUL_PERSONAL: "개인 파울 감지",
    EventType.FOUL_OFFENSIVE: "공격 파울 감지",
    EventType.FOUL_DEFENSIVE: "수비 파울 감지",
    EventType.FOUL_TECHNICAL: "테크니컬 파울 감지",
    EventType.FOUL_FLAGRANT: "플래그런트 파울 감지",

    # 피드백
    EventType.FEEDBACK_GENERATED: "피드백 생성됨",
    EventType.FEEDBACK_SHOOTING_GENERATED: "슈팅 피드백 생성됨",
    EventType.FEEDBACK_DRIBBLING_GENERATED: "드리블 피드백 생성됨",
    EventType.FEEDBACK_DEFENSE_GENERATED: "수비 피드백 생성됨",

    # 추천
    EventType.RECOMMENDATION_GENERATED: "추천 훈련 생성됨",
    EventType.DRILL_RECOMMENDED: "드릴 추천됨",

    # 레포트
    EventType.REPORT_WEEKLY_GENERATED: "주간 레포트 생성됨",
    EventType.REPORT_PROGRESS_GENERATED: "진행 레포트 생성됨",

    # 학습
    EventType.LEARNING_PATTERN_DETECTED: "학습 패턴 감지",
    EventType.LEARNING_MODEL_UPDATED: "학습 모델 업데이트",
    EventType.LEARNING_THRESHOLD_ADJUSTED: "학습 임계값 조정",
    EventType.LEARNING_ACCURACY_IMPROVED: "학습 정확도 향상",

    # 캐시
    EventType.CACHE_HIT: "캐시 적중",
    EventType.CACHE_MISS: "캐시 미스",
    EventType.CACHE_EVICTED: "캐시 제거",

    # 큐
    EventType.QUEUE_MESSAGE_PUBLISHED: "큐 메시지 발행",
    EventType.QUEUE_MESSAGE_CONSUMED: "큐 메시지 소비",
    EventType.QUEUE_MESSAGE_FAILED: "큐 메시지 실패",
    EventType.QUEUE_MESSAGE_DEAD_LETTER: "데드 레터 큐 전송",

    # 스토리지
    EventType.STORAGE_FILE_UPLOADED: "파일 업로드",
    EventType.STORAGE_FILE_DOWNLOADED: "파일 다운로드",
    EventType.STORAGE_FILE_DELETED: "파일 삭제",

    # 데이터베이스
    EventType.DATABASE_QUERY_SLOW: "느린 쿼리 감지",
    EventType.DATABASE_CONNECTION_LOST: "데이터베이스 연결 끊김",
    EventType.DATABASE_CONNECTION_RESTORED: "데이터베이스 연결 복구",

    # 모델
    EventType.MODEL_LOADED: "모델 로드",
    EventType.MODEL_UNLOADED: "모델 언로드",
    EventType.MODEL_INFERENCE_STARTED: "모델 추론 시작",
    EventType.MODEL_INFERENCE_COMPLETED: "모델 추론 완료",
    EventType.MODEL_INFERENCE_FAILED: "모델 추론 실패",
}


# =============================================================================
# 이벤트 그룹 정의 (immutable frozenset)
# =============================================================================

# 외부 웹훅으로 전송할 이벤트
WEBHOOK_EVENTS: Final[frozenset[EventType]] = frozenset({
    EventType.TASK_COMPLETED,
    EventType.TASK_FAILED,
    EventType.ANALYSIS_SHOOTING_COMPLETED,
    EventType.ANALYSIS_DRIBBLING_COMPLETED,
    EventType.ANALYSIS_PASSING_COMPLETED,
    EventType.ANALYSIS_DEFENSE_COMPLETED,
    EventType.ANALYSIS_COMPARISON_COMPLETED,
    EventType.GAME_ANALYSIS_COMPLETED,
    EventType.GAME_ANALYSIS_FAILED,
    EventType.REFEREE_ANALYSIS_COMPLETED,
    EventType.REFEREE_ANALYSIS_FAILED,
    EventType.REPORT_WEEKLY_GENERATED,
})

# WebSocket으로 실시간 전송할 이벤트
REALTIME_EVENTS: Final[frozenset[EventType]] = frozenset({
    EventType.TASK_STARTED,
    EventType.TASK_PROGRESS,
    EventType.TASK_COMPLETED,
    EventType.TASK_FAILED,
    EventType.ANALYSIS_SHOOTING_PROGRESS,
    EventType.ANALYSIS_DRIBBLING_PROGRESS,
    EventType.GAME_ANALYSIS_PROGRESS,
    EventType.GAME_SHOT_DETECTED,
    EventType.GAME_SCORE_DETECTED,
    EventType.HIGHLIGHT_DETECTED,
    EventType.VIOLATION_DETECTED,
    EventType.FOUL_DETECTED,
})

# 로깅이 필요한 중요 이벤트
AUDIT_EVENTS: Final[frozenset[EventType]] = frozenset({
    EventType.SYSTEM_STARTED,
    EventType.SYSTEM_SHUTDOWN,
    EventType.SYSTEM_CONFIG_RELOADED,
    EventType.SYSTEM_ERROR,
    EventType.TASK_CREATED,
    EventType.TASK_COMPLETED,
    EventType.TASK_FAILED,
    EventType.MODEL_LOADED,
    EventType.MODEL_UNLOADED,
    EventType.LEARNING_MODEL_UPDATED,
})

# 메트릭 수집 대상 이벤트
METRIC_EVENTS: Final[frozenset[EventType]] = frozenset({
    EventType.TASK_STARTED,
    EventType.TASK_COMPLETED,
    EventType.TASK_FAILED,
    EventType.TASK_TIMEOUT,
    EventType.MODEL_INFERENCE_STARTED,
    EventType.MODEL_INFERENCE_COMPLETED,
    EventType.MODEL_INFERENCE_FAILED,
    EventType.CACHE_HIT,
    EventType.CACHE_MISS,
    EventType.DATABASE_QUERY_SLOW,
})


# =============================================================================
# 이벤트 우선순위
# =============================================================================

EVENT_PRIORITY: Final[dict[EventType, int]] = {
    # 시스템 이벤트 (최우선)
    EventType.SYSTEM_ERROR: 0,
    EventType.SYSTEM_SHUTDOWN: 0,
    EventType.DATABASE_CONNECTION_LOST: 0,

    # 에러 이벤트 (높음)
    EventType.TASK_FAILED: 1,
    EventType.GAME_ANALYSIS_FAILED: 1,
    EventType.REFEREE_ANALYSIS_FAILED: 1,
    EventType.MODEL_INFERENCE_FAILED: 1,

    # 완료 이벤트 (중간)
    EventType.TASK_COMPLETED: 2,
    EventType.ANALYSIS_SHOOTING_COMPLETED: 2,
    EventType.GAME_ANALYSIS_COMPLETED: 2,

    # 진행 이벤트 (낮음)
    EventType.TASK_PROGRESS: 3,
    EventType.ANALYSIS_SHOOTING_PROGRESS: 3,

    # 인프라 이벤트 (최저)
    EventType.CACHE_HIT: 4,
    EventType.CACHE_MISS: 4,
}


def get_event_priority(event_type: EventType) -> int:
    """
    이벤트 우선순위 반환.

    Args:
        event_type: 이벤트 타입

    Returns:
        우선순위 (0이 가장 높음, 기본값 3)
    """
    return EVENT_PRIORITY.get(event_type, 3)


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 이벤트 카테고리
    "EventCategory",
    # 이벤트 타입
    "EventType",
    # 이벤트 그룹
    "WEBHOOK_EVENTS",
    "REALTIME_EVENTS",
    "AUDIT_EVENTS",
    "METRIC_EVENTS",
    # 우선순위
    "EVENT_PRIORITY",
    "get_event_priority",
]

# 모듈 버전 정보
__version__ = "1.0.0"
