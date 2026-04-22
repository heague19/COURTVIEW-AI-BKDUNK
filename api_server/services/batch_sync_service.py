# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: batch_sync_service.py
설명: 오프라인 미전송분 일괄 동기화 서비스
      - 로컬 JSON 파일에서 미전송 결과 탐색
      - 온라인 복구 시 CloudSyncService로 일괄 전송
      - 전송 완료 후 로컬 파일 정리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from api_server.services.cloud_sync_service import CloudSyncService

_logger = logging.getLogger(__name__)


class BatchSyncService:
    """오프라인 미전송분 일괄 동기화."""

    __slots__ = ("_cloud_service", "_output_dir")

    def __init__(
        self,
        cloud_service: CloudSyncService,
        output_dir: str = "output",
    ) -> None:
        self._cloud_service = cloud_service
        self._output_dir = output_dir

    def sync_pending(self) -> int:
        """
        미전송 JSON 파일 일괄 전송.

        Returns:
            전송 성공 건수
        """
        if not self._cloud_service.is_enabled:
            return 0

        output_path = Path(self._output_dir)
        if not output_path.exists():
            return 0

        # cloud_fallback_*.json 파일 탐색
        pending_files = sorted(output_path.glob("cloud_fallback_*.json"))
        sent = 0

        for filepath in pending_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if self._cloud_service.sync_game_result(data):
                    filepath.unlink()  # 전송 성공 → 삭제
                    sent += 1
                    _logger.info("미전송 동기화: %s", filepath.name)
                else:
                    break  # 실패 시 중단

            except Exception:
                _logger.exception("미전송 파일 처리 오류: %s", filepath.name)
                break

        if sent > 0:
            _logger.info("미전송 일괄 동기화: %d건 완료", sent)
        return sent

    @property
    def pending_count(self) -> int:
        """미전송 파일 수."""
        output_path = Path(self._output_dir)
        if not output_path.exists():
            return 0
        return len(list(output_path.glob("cloud_fallback_*.json")))


__all__ = ["BatchSyncService"]
