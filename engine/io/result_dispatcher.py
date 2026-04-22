# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/io
파일: result_dispatcher.py
설명: 분석 결과 분배기
      - WebSocket: 프론트엔드 실시간 전송 (경기 중)
      - JSON: 로컬 파일 저장 (오프라인 모드)
      - Cloud: 백엔드 REST API 전송 (경기 후)
      - 대상별 독립 큐 + 실패 시 로컬 폴백

      아키텍처 통신 흐름:
        engine → result_dispatcher → WebSocket (프론트엔드)
        engine → result_dispatcher → JSON (로컬 SSD)
        engine → result_dispatcher → REST POST (백엔드 Cloud)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: IOConfig

소비자:
    - engine/orchestrator/game_orchestrator.py: 결과 전송 시 호출
    - api_server/websocket/: WebSocket 연동
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, unique
from pathlib import Path
from threading import RLock
from typing import Any, Final

from engine.config import IOConfig

_logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE: Final[int] = 500
_MAX_DISPATCH_HISTORY: Final[int] = 200


@unique
class DispatchTarget(str, Enum):
    """전송 대상."""
    WEBSOCKET = "websocket"
    JSON_FILE = "json_file"
    CLOUD_API = "cloud_api"

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True)
class DispatchRecord:
    """전송 기록."""
    target: DispatchTarget
    timestamp: float = 0.0
    success: bool = True
    data_keys: tuple[str, ...] = ()


@dataclass(slots=True)
class DispatchStats:
    """전송 통계."""
    websocket_sent: int = 0
    websocket_failed: int = 0
    json_saved: int = 0
    json_failed: int = 0
    cloud_sent: int = 0
    cloud_failed: int = 0


class ResultDispatcher:
    """
    분석 결과 분배기.

    3가지 대상(WebSocket/JSON/Cloud)으로 결과를 전송합니다.
    Cloud 전송 실패 시 로컬 JSON으로 폴백합니다.
    """

    __slots__ = (
        "_config",
        "_stats",
        "_history",
        "_ws_queue",
        "_cloud_queue",
        "_initialized",
        "_lock",
    )

    def __init__(self, config: IOConfig | None = None) -> None:
        self._config = config or IOConfig()
        self._stats = DispatchStats()
        self._history: list[DispatchRecord] = []
        self._ws_queue: deque[dict[str, Any]] = deque(maxlen=_MAX_QUEUE_SIZE)
        self._cloud_queue: deque[dict[str, Any]] = deque(maxlen=_MAX_QUEUE_SIZE)
        self._initialized: bool = False
        self._lock: RLock = RLock()

    def initialize(self) -> None:
        """출력 디렉토리 생성."""
        with self._lock:
            if self._initialized:
                return
            Path(self._config.output_dir).mkdir(parents=True, exist_ok=True)
            self._initialized = True
            _logger.info("ResultDispatcher 초기화: output=%s", self._config.output_dir)

    def shutdown(self) -> None:
        """잔여 큐 플러시."""
        with self._lock:
            ws_remaining = len(self._ws_queue)
            cloud_remaining = len(self._cloud_queue)
            self._ws_queue.clear()
            self._cloud_queue.clear()
            self._initialized = False
            _logger.info(
                "ResultDispatcher 종료 (잔여: ws=%d, cloud=%d)",
                ws_remaining, cloud_remaining,
            )

    # =========================================================================
    # 전송
    # =========================================================================
    def dispatch(
        self,
        data: dict[str, Any],
        targets: frozenset[DispatchTarget] | None = None,
    ) -> None:
        """
        결과 전송.

        Args:
            data: 전송할 데이터 (JSON 직렬화 가능)
            targets: 전송 대상 (None=전체)
        """
        if targets is None:
            targets = frozenset({
                DispatchTarget.WEBSOCKET,
                DispatchTarget.JSON_FILE,
            })

        data_keys = tuple(data.keys())

        for target in targets:
            try:
                if target == DispatchTarget.WEBSOCKET:
                    self._send_websocket(data)
                elif target == DispatchTarget.JSON_FILE:
                    self._save_json(data)
                elif target == DispatchTarget.CLOUD_API:
                    self._send_cloud(data)

                self._record(target, True, data_keys)

            except Exception:
                self._record(target, False, data_keys)
                _logger.exception("결과 전송 실패: %s", target.value)

                # Cloud 실패 시 로컬 폴백
                if target == DispatchTarget.CLOUD_API:
                    try:
                        self._save_json(data, prefix="cloud_fallback")
                    except Exception:
                        _logger.exception("Cloud 폴백 JSON 저장 실패")

    def dispatch_realtime(self, data: dict[str, Any]) -> None:
        """실시간 전송 (WebSocket만)."""
        self.dispatch(data, frozenset({DispatchTarget.WEBSOCKET}))

    def dispatch_postgame(self, data: dict[str, Any]) -> None:
        """경기 후 전송 (JSON + Cloud)."""
        targets = {DispatchTarget.JSON_FILE}
        if self._config.cloud_sync_enabled:
            targets.add(DispatchTarget.CLOUD_API)
        self.dispatch(data, frozenset(targets))

    # =========================================================================
    # 내부 전송
    # =========================================================================
    def _send_websocket(self, data: dict[str, Any]) -> None:
        """WebSocket 전송 (실제 연동은 api_server에서)."""
        with self._lock:
            self._ws_queue.append(data)
            self._stats.websocket_sent += 1
        # api_server의 WebSocket manager가 ws_queue를 소비

    def _save_json(self, data: dict[str, Any], prefix: str = "result") -> None:
        """로컬 JSON 저장."""
        ts = int(time.time() * 1000)
        filename = f"{prefix}_{ts}.json"
        filepath = Path(self._config.output_dir) / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str, indent=2)

        with self._lock:
            self._stats.json_saved += 1

    def _send_cloud(self, data: dict[str, Any]) -> None:
        """Cloud REST API 전송 (시뮬레이션)."""
        url = self._config.cloud_sync_url
        if not url:
            raise ValueError("cloud_sync_url 미설정")

        # 실제 전송은 api_server/services/cloud_sync_service.py에서 구현
        # 여기서는 큐에 적재
        with self._lock:
            self._cloud_queue.append(data)
            self._stats.cloud_sent += 1

    def _record(
        self, target: DispatchTarget, success: bool, keys: tuple[str, ...],
    ) -> None:
        """전송 기록."""
        with self._lock:
            if not success:
                if target == DispatchTarget.WEBSOCKET:
                    self._stats.websocket_failed += 1
                elif target == DispatchTarget.JSON_FILE:
                    self._stats.json_failed += 1
                elif target == DispatchTarget.CLOUD_API:
                    self._stats.cloud_failed += 1

            self._history.append(DispatchRecord(
                target=target, timestamp=time.monotonic(),
                success=success, data_keys=keys,
            ))
            if len(self._history) > _MAX_DISPATCH_HISTORY:
                self._history = self._history[-_MAX_DISPATCH_HISTORY:]

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def stats(self) -> DispatchStats:
        with self._lock:
            s = self._stats
            return DispatchStats(
                websocket_sent=s.websocket_sent,
                websocket_failed=s.websocket_failed,
                json_saved=s.json_saved,
                json_failed=s.json_failed,
                cloud_sent=s.cloud_sent,
                cloud_failed=s.cloud_failed,
            )

    @property
    def ws_queue_size(self) -> int:
        return len(self._ws_queue)

    def pop_ws_messages(self, count: int = 10) -> list[dict[str, Any]]:
        """WebSocket 큐에서 메시지 꺼내기 (api_server 소비용)."""
        with self._lock:
            result = []
            for _ in range(min(count, len(self._ws_queue))):
                result.append(self._ws_queue.popleft())
            return result

    def reset(self) -> None:
        with self._lock:
            self._stats = DispatchStats()
            self._history.clear()
            self._ws_queue.clear()
            self._cloud_queue.clear()

    def __repr__(self) -> str:
        s = self._stats
        return (
            f"ResultDispatcher(ws={s.websocket_sent}, "
            f"json={s.json_saved}, cloud={s.cloud_sent})"
        )


__all__ = [
    "DispatchTarget",
    "DispatchRecord",
    "DispatchStats",
    "ResultDispatcher",
]

__version__ = "1.0.0"
