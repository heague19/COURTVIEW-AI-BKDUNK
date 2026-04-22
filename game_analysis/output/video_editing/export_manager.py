# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/video_editing
파일: export_manager.py
설명: 비디오 내보내기 관리기
      - ExportConfig 기반 내보내기 작업 큐잉
      - 내보내기 상태 추적
      - 출력 경로/포맷/해상도 관리

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

의존성:
  shared.dto.media_dto (ExportFormat, ExportConfig)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.dto.media_dto import ExportConfig, ExportFormat

logger: Final = logging.getLogger(__name__)

_MAX_EXPORT_JOBS: Final[int] = 500


# =============================================================================
# Enum
# =============================================================================

@unique
class ExportStatus(str, Enum):
    """내보내기 작업 상태."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Config
# =============================================================================

@dataclass(slots=True)
class ExportManagerConfig:
    """내보내기 관리기 설정."""

    max_export_jobs: int = _MAX_EXPORT_JOBS


# =============================================================================
# 내부 데이터 구조
# =============================================================================

@dataclass(slots=True)
class _ExportJob:
    """내보내기 작업 1건."""

    job_id: UUID
    clip_id: UUID
    config: ExportConfig
    status: ExportStatus
    output_path: str
    error_message: str


# =============================================================================
# Manager
# =============================================================================

class ExportManager:
    """비디오 내보내기 관리기."""

    __slots__ = ("_config", "_lock", "_jobs")

    def __init__(self, config: ExportManagerConfig | None = None) -> None:
        self._config = config or ExportManagerConfig()
        self._lock = RLock()
        self._jobs: dict[UUID, _ExportJob] = {}

    # ── 속성 ──

    @property
    def name(self) -> str:
        return "ExportManager"

    @property
    def total_jobs(self) -> int:
        with self._lock:
            return len(self._jobs)

    # ── 작업 생성 ──

    def queue_export(
        self,
        clip_id: UUID,
        export_config: ExportConfig,
        *,
        output_path: str = "",
    ) -> UUID | None:
        """
        내보내기 작업 큐잉. 반환: job_id 또는 None (한도 초과).
        output_path가 비어있으면 ExportConfig.output_path 사용.
        """
        with self._lock:
            if len(self._jobs) >= self._config.max_export_jobs:
                logger.warning("내보내기 작업 한도 도달 (%d)", self._config.max_export_jobs)
                return None

            resolved_path = output_path or export_config.output_path
            jid = uuid4()
            self._jobs[jid] = _ExportJob(
                job_id=jid,
                clip_id=clip_id,
                config=export_config,
                status=ExportStatus.QUEUED,
                output_path=resolved_path,
                error_message="",
            )
            return jid

    # ── 상태 변경 ──

    def start_export(self, job_id: UUID) -> bool:
        """작업 시작 (QUEUED → IN_PROGRESS)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != ExportStatus.QUEUED:
                return False
            job.status = ExportStatus.IN_PROGRESS
            return True

    def complete_export(self, job_id: UUID, output_path: str = "") -> bool:
        """작업 완료 (IN_PROGRESS → COMPLETED)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != ExportStatus.IN_PROGRESS:
                return False
            job.status = ExportStatus.COMPLETED
            if output_path:
                job.output_path = output_path
            return True

    def fail_export(self, job_id: UUID, error_message: str = "") -> bool:
        """작업 실패 (IN_PROGRESS → FAILED)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != ExportStatus.IN_PROGRESS:
                return False
            job.status = ExportStatus.FAILED
            job.error_message = error_message
            return True

    # ── 조회 ──

    def get_job(self, job_id: UUID) -> dict[str, object] | None:
        """작업 상세 조회."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "job_id": str(job.job_id),
                "clip_id": str(job.clip_id),
                "format": job.config.format.value,
                "resolution": job.config.resolution,
                "fps": job.config.fps,
                "bitrate_mbps": job.config.bitrate_mbps,
                "status": job.status.value,
                "output_path": job.output_path,
                "error_message": job.error_message,
            }

    def get_jobs_by_status(self, status: ExportStatus) -> list[UUID]:
        """상태별 작업 ID 목록."""
        with self._lock:
            return [
                jid for jid, job in self._jobs.items()
                if job.status == status
            ]

    def get_queued_count(self) -> int:
        """대기 중 작업 수."""
        with self._lock:
            return sum(
                1 for job in self._jobs.values()
                if job.status == ExportStatus.QUEUED
            )

    def get_status_distribution(self) -> dict[str, int]:
        """상태별 작업 수 분포."""
        with self._lock:
            dist: dict[str, int] = {}
            for job in self._jobs.values():
                dist[job.status.value] = dist.get(job.status.value, 0) + 1
            return dist

    # ── 삭제 ──

    def remove_job(self, job_id: UUID) -> bool:
        """작업 제거 (COMPLETED/FAILED만)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status not in (ExportStatus.COMPLETED, ExportStatus.FAILED):
                return False
            del self._jobs[job_id]
            return True

    def clear_completed(self) -> int:
        """완료된 작업 일괄 제거. 반환: 제거 수."""
        with self._lock:
            completed = [
                jid for jid, job in self._jobs.items()
                if job.status == ExportStatus.COMPLETED
            ]
            for jid in completed:
                del self._jobs[jid]
            return len(completed)

    # ── 유틸리티 ──

    def get_stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "total_jobs": len(self._jobs),
                "status_distribution": self.get_status_distribution(),
            }

    def reset(self) -> None:
        with self._lock:
            self._jobs.clear()

    def __repr__(self) -> str:
        return f"ExportManager(jobs={self.total_jobs})"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "ExportManager",
    "ExportManagerConfig",
    "ExportStatus",
]

__version__ = "1.0.0"
