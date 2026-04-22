# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: pipeline_coordinator.py
설명: 파이프라인 오케스트레이션
      - 파이프라인 단계(Stage) 등록/실행
      - 단계 간 의존성 관리 (DAG 기반)
      - 실행 상태 추적
      - 단계 콜백 (시작/완료/실패)
      - 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable, ClassVar, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 파이프라인 수
MAX_PIPELINES: Final[int] = 30

# 최대 단계 수 (파이프라인당)
MAX_STAGES_PER_PIPELINE: Final[int] = 50


# =============================================================================
# 단계 상태 열거형
# =============================================================================

@unique
class StageStatus(Enum):
    """파이프라인 단계 실행 상태.

    Attributes:
        PENDING: 대기
        RUNNING: 실행 중
        COMPLETED: 완료
        FAILED: 실패
        SKIPPED: 건너뜀
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _STAGE_STATUS_KOREAN_MAP[self]

    @property
    def is_terminal(self) -> bool:
        """종료 상태 여부."""
        return self in _TERMINAL_STATUSES


_STAGE_STATUS_KOREAN_MAP: Final[dict[StageStatus, str]] = {
    StageStatus.PENDING: "대기",
    StageStatus.RUNNING: "실행 중",
    StageStatus.COMPLETED: "완료",
    StageStatus.FAILED: "실패",
    StageStatus.SKIPPED: "건너뜀",
}

_TERMINAL_STATUSES: Final[frozenset[StageStatus]] = frozenset({
    StageStatus.COMPLETED,
    StageStatus.FAILED,
    StageStatus.SKIPPED,
})


# =============================================================================
# 단계 실행 결과
# =============================================================================

@dataclass(slots=True)
class StageResult:
    """파이프라인 단계 실행 결과.

    Attributes:
        stage_name: 단계 이름
        status: 실행 상태
        duration_sec: 소요 시간 (초)
        output: 출력 데이터
        error_message: 오류 메시지
    """

    stage_name: str
    status: StageStatus
    duration_sec: float = 0.0
    output: Any = None
    error_message: str = ""

    def __repr__(self) -> str:
        return (
            f"StageResult('{self.stage_name}', "
            f"{self.status.value}, "
            f"{self.duration_sec:.3f}s)"
        )


# =============================================================================
# 파이프라인 단계 정의
# =============================================================================

@dataclass(slots=True)
class StageDefinition:
    """파이프라인 단계 정의.

    Attributes:
        name: 단계 이름
        handler: 실행 함수 (context: dict) -> Any
        dependencies: 선행 단계 이름 목록
        description: 설명
        optional: 실패 시 파이프라인 중단 여부 (True: 건너뜀)
    """

    name: str
    handler: Callable[[dict[str, Any]], Any]
    dependencies: list[str] = field(default_factory=list)
    description: str = ""
    optional: bool = False

    def __repr__(self) -> str:
        return (
            f"StageDefinition('{self.name}', "
            f"deps={self.dependencies})"
        )


# =============================================================================
# 파이프라인 실행 결과
# =============================================================================

@dataclass(slots=True)
class PipelineResult:
    """파이프라인 전체 실행 결과.

    Attributes:
        pipeline_name: 파이프라인 이름
        success: 전체 성공 여부
        stages: 단계별 결과
        total_duration_sec: 전체 소요 시간
    """

    pipeline_name: str
    success: bool
    stages: dict[str, StageResult]
    total_duration_sec: float

    @property
    def completed_count(self) -> int:
        """완료된 단계 수."""
        return sum(
            1 for r in self.stages.values()
            if r.status == StageStatus.COMPLETED
        )

    @property
    def failed_stages(self) -> list[str]:
        """실패 단계 목록."""
        return [
            name for name, r in self.stages.items()
            if r.status == StageStatus.FAILED
        ]

    def __repr__(self) -> str:
        return (
            f"PipelineResult('{self.pipeline_name}', "
            f"success={self.success}, "
            f"stages={len(self.stages)}, "
            f"{self.total_duration_sec:.3f}s)"
        )


# =============================================================================
# 타입 정의
# =============================================================================

# 단계 콜백: (stage_name, status) -> None
StageCallback = Callable[[str, StageStatus], None]


# =============================================================================
# 핵심 클래스: PipelineCoordinator
# =============================================================================

class PipelineCoordinator:
    """파이프라인 오케스트레이션 관리자.

    파이프라인과 단계를 등록하고, DAG 순서에 따라 실행한다.

    스레드 안전:
        모든 메서드는 RLock 보호.

    사용 예시::

        coordinator = PipelineCoordinator.get_instance()

        # 파이프라인 생성
        coordinator.create_pipeline("game_analysis")

        # 단계 등록
        coordinator.add_stage("game_analysis", StageDefinition(
            name="detection",
            handler=run_detection,
        ))
        coordinator.add_stage("game_analysis", StageDefinition(
            name="tracking",
            handler=run_tracking,
            dependencies=["detection"],
        ))

        # 실행
        result = coordinator.execute("game_analysis")
        print(f"성공: {result.success}")
    """

    _instance: ClassVar[PipelineCoordinator | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pipelines: dict[str, list[StageDefinition]] = {}
        self._callbacks: list[StageCallback] = []

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> PipelineCoordinator:
        """Singleton 인스턴스 획득."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Singleton 초기화 (테스트용)."""
        with cls._class_lock:
            cls._instance = None

    # =========================================================================
    # 파이프라인 관리
    # =========================================================================

    def create_pipeline(self, name: str) -> bool:
        """파이프라인 생성.

        Args:
            name: 파이프라인 이름

        Returns:
            생성 성공 여부
        """
        with self._lock:
            if name in self._pipelines:
                return False
            if len(self._pipelines) >= MAX_PIPELINES:
                return False
            self._pipelines[name] = []
            return True

    def remove_pipeline(self, name: str) -> bool:
        """파이프라인 제거.

        Args:
            name: 파이프라인 이름

        Returns:
            제거 성공 여부
        """
        with self._lock:
            if name in self._pipelines:
                del self._pipelines[name]
                return True
            return False

    def add_stage(
        self,
        pipeline_name: str,
        stage: StageDefinition,
    ) -> bool:
        """파이프라인에 단계 추가.

        Args:
            pipeline_name: 파이프라인 이름
            stage: 단계 정의

        Returns:
            추가 성공 여부

        Raises:
            KeyError: 미등록 파이프라인
        """
        with self._lock:
            stages = self._pipelines.get(pipeline_name)
            if stages is None:
                raise KeyError(f"미등록 파이프라인: '{pipeline_name}'")

            if len(stages) >= MAX_STAGES_PER_PIPELINE:
                return False

            # 중복 이름 검사
            existing_names = {s.name for s in stages}
            if stage.name in existing_names:
                return False

            stages.append(stage)
            return True

    def get_stages(self, pipeline_name: str) -> list[StageDefinition]:
        """파이프라인 단계 목록 조회.

        Args:
            pipeline_name: 파이프라인 이름

        Returns:
            단계 정의 목록 (복사본)

        Raises:
            KeyError: 미등록 파이프라인
        """
        with self._lock:
            stages = self._pipelines.get(pipeline_name)
            if stages is None:
                raise KeyError(f"미등록 파이프라인: '{pipeline_name}'")
            return list(stages)

    # =========================================================================
    # 콜백
    # =========================================================================

    def add_callback(self, callback: StageCallback) -> None:
        """단계 상태 변경 콜백 등록."""
        with self._lock:
            self._callbacks.append(callback)

    def remove_callback(self, callback: StageCallback) -> bool:
        """단계 상태 변경 콜백 해제."""
        with self._lock:
            try:
                self._callbacks.remove(callback)
                return True
            except ValueError:
                return False

    # =========================================================================
    # 파이프라인 실행
    # =========================================================================

    def execute(
        self,
        pipeline_name: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """파이프라인 실행.

        DAG 위상 정렬 순서로 단계 실행.

        Args:
            pipeline_name: 파이프라인 이름
            context: 초기 컨텍스트 데이터

        Returns:
            PipelineResult

        Raises:
            KeyError: 미등록 파이프라인
            RuntimeError: 순환 의존 또는 미등록 의존 단계
        """
        with self._lock:
            stages = self._pipelines.get(pipeline_name)
            if stages is None:
                raise KeyError(f"미등록 파이프라인: '{pipeline_name}'")
            stages_copy = list(stages)
            callbacks = list(self._callbacks)

        # 위상 정렬
        ordered = self._topological_sort(stages_copy)

        # 실행
        start = time.perf_counter()
        ctx = dict(context) if context else {}
        results: dict[str, StageResult] = {}
        success = True

        for stage in ordered:
            # 의존 단계 실패 확인
            deps_ok = all(
                results.get(dep, StageResult(dep, StageStatus.PENDING)).status
                == StageStatus.COMPLETED
                for dep in stage.dependencies
            )

            if not deps_ok:
                if stage.optional:
                    result = StageResult(
                        stage_name=stage.name,
                        status=StageStatus.SKIPPED,
                    )
                else:
                    result = StageResult(
                        stage_name=stage.name,
                        status=StageStatus.FAILED,
                        error_message="선행 단계 실패",
                    )
                    success = False

                results[stage.name] = result
                self._notify(callbacks, stage.name, result.status)
                continue

            # 단계 실행
            result = self._execute_stage(stage, ctx, callbacks)
            results[stage.name] = result

            if result.status == StageStatus.FAILED and not stage.optional:
                success = False

            # 출력을 컨텍스트에 추가
            if result.output is not None:
                ctx[stage.name] = result.output

        total_duration = time.perf_counter() - start

        return PipelineResult(
            pipeline_name=pipeline_name,
            success=success,
            stages=results,
            total_duration_sec=total_duration,
        )

    # =========================================================================
    # 조회
    # =========================================================================

    @property
    def pipeline_count(self) -> int:
        """등록된 파이프라인 수."""
        with self._lock:
            return len(self._pipelines)

    @property
    def pipeline_names(self) -> list[str]:
        """등록된 파이프라인 이름 목록."""
        with self._lock:
            return list(self._pipelines.keys())

    def has_pipeline(self, name: str) -> bool:
        """파이프라인 존재 여부."""
        with self._lock:
            return name in self._pipelines

    def stage_count(self, pipeline_name: str) -> int:
        """파이프라인 단계 수.

        Args:
            pipeline_name: 파이프라인 이름

        Returns:
            단계 수 (미등록 시 0)
        """
        with self._lock:
            stages = self._pipelines.get(pipeline_name)
            return len(stages) if stages is not None else 0

    def clear(self) -> int:
        """전체 파이프라인 제거.

        Returns:
            제거된 파이프라인 수
        """
        with self._lock:
            count = len(self._pipelines)
            self._pipelines.clear()
            return count

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _execute_stage(
        self,
        stage: StageDefinition,
        ctx: dict[str, Any],
        callbacks: list[StageCallback],
    ) -> StageResult:
        """단일 단계 실행 (예외 격리)."""
        self._notify(callbacks, stage.name, StageStatus.RUNNING)

        start = time.perf_counter()
        try:
            output = stage.handler(ctx)
            elapsed = time.perf_counter() - start

            result = StageResult(
                stage_name=stage.name,
                status=StageStatus.COMPLETED,
                duration_sec=elapsed,
                output=output,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start

            if stage.optional:
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.SKIPPED,
                    duration_sec=elapsed,
                    error_message=f"{type(exc).__name__}: {exc}",
                )
            else:
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.FAILED,
                    duration_sec=elapsed,
                    error_message=f"{type(exc).__name__}: {exc}",
                )

        self._notify(callbacks, stage.name, result.status)
        return result

    @staticmethod
    def _topological_sort(
        stages: list[StageDefinition],
    ) -> list[StageDefinition]:
        """DAG 위상 정렬.

        Args:
            stages: 단계 정의 목록

        Returns:
            정렬된 단계 목록

        Raises:
            RuntimeError: 순환 의존 또는 미등록 의존
        """
        stage_map = {s.name: s for s in stages}
        name_set = set(stage_map.keys())

        # 미등록 의존 검증
        for stage in stages:
            for dep in stage.dependencies:
                if dep not in name_set:
                    raise RuntimeError(
                        f"미등록 의존 단계: '{dep}' "
                        f"(단계 '{stage.name}'에서 필요)"
                    )

        # Kahn 알고리즘
        in_degree: dict[str, int] = {name: 0 for name in name_set}
        for stage in stages:
            for dep in stage.dependencies:
                in_degree[stage.name] += 1

        queue: list[str] = [
            name for name, deg in in_degree.items() if deg == 0
        ]
        result: list[StageDefinition] = []

        while queue:
            name = queue.pop(0)
            result.append(stage_map[name])

            for stage in stages:
                if name in stage.dependencies:
                    in_degree[stage.name] -= 1
                    if in_degree[stage.name] == 0:
                        queue.append(stage.name)

        if len(result) != len(stages):
            raise RuntimeError("파이프라인 순환 의존 감지")

        return result

    @staticmethod
    def _notify(
        callbacks: list[StageCallback],
        stage_name: str,
        status: StageStatus,
    ) -> None:
        """콜백 알림 (예외 격리)."""
        for callback in callbacks:
            try:
                callback(stage_name, status)
            except Exception:
                pass

    def __repr__(self) -> str:
        return f"PipelineCoordinator(pipelines={self.pipeline_count})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "StageStatus",
    # 데이터 클래스
    "StageResult",
    "StageDefinition",
    "PipelineResult",
    # 타입
    "StageCallback",
    # 핵심 클래스
    "PipelineCoordinator",
    # 상수
    "MAX_PIPELINES",
    "MAX_STAGES_PER_PIPELINE",
]

__version__ = "1.0.0"
