# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: cloud_sync_service.py
설명: Cloud Backend 동기화 서비스 (Phase 17 S4 구현 완료).

      설계:
      - 경기 종료 시 자동 호출 (GameService.on_game_end)
      - ExportService가 수집한 전체 스냅샷을 bkdunk.com 백엔드로 POST
      - 인터넷 없을 시 로컬 큐에 대기 (JSONL)
      - 백그라운드 재시도 워커가 온라인 복귀 시 큐 flush

      환경 변수 (또는 config):
        COURTVIEW_CLOUD_URL       — bkdunk 백엔드 base URL
        COURTVIEW_CLOUD_TOKEN     — SPOIN ID 토큰
        COURTVIEW_CLOUD_ENABLED   — "1" 일 때만 활성

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-21
버전: 2.0.0
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from threading import RLock
from typing import Any, Final

_logger = logging.getLogger(__name__)

_MAX_RETRIES: Final[int] = 3
_TIMEOUT_SEC: Final[float] = 30.0
_RETRY_WORKER_INTERVAL_SEC: Final[float] = 60.0  # 1분마다 큐 flush 시도
# 기본 큐 디렉토리 — 패키징 시 %APPDATA%\COURTVIEW\cloud_sync_queue\ 로 자동 전환
def _default_queue_dir() -> str:
    try:
        from infrastructure.storage.paths import cloud_sync_queue_dir
        return str(cloud_sync_queue_dir())
    except Exception:
        return "cloud_sync_queue"


_DEFAULT_QUEUE_DIR: Final[str] = _default_queue_dir()


class CloudSyncService:
    """
    Cloud Backend 동기화 서비스 (bkdunk.com).

    - 경기 종료 시 ExportService 스냅샷을 전송
    - 오프라인 시 로컬 JSONL 큐에 대기
    - 백그라운드 워커가 온라인 복귀 시 자동 재전송
    """

    __slots__ = (
        "_base_url",
        "_auth_token",
        "_enabled",
        "_queue_dir",
        "_lock",
        "_worker_thread",
        "_stop_event",
    )

    def __init__(
        self,
        base_url: str = "",
        auth_token: str = "",
        enabled: bool | None = None,
        queue_dir: str | Path | None = None,
    ) -> None:
        # 환경 변수 fallback
        self._base_url = base_url or os.environ.get("COURTVIEW_CLOUD_URL", "")
        self._auth_token = auth_token or os.environ.get("COURTVIEW_CLOUD_TOKEN", "")
        if enabled is None:
            enabled = os.environ.get("COURTVIEW_CLOUD_ENABLED", "0") == "1"
        self._enabled = bool(enabled)

        self._queue_dir = Path(queue_dir or _DEFAULT_QUEUE_DIR)
        self._queue_dir.mkdir(parents=True, exist_ok=True)

        self._lock = RLock()
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # =========================================================================
    # 설정
    # =========================================================================
    @property
    def is_enabled(self) -> bool:
        return self._enabled and bool(self._base_url)

    def set_token(self, token: str) -> None:
        """SPOIN ID 토큰 갱신 (로그인 후 호출)."""
        with self._lock:
            self._auth_token = token

    def configure(self, base_url: str = "", token: str = "", enabled: bool | None = None) -> None:
        """런타임 설정 변경."""
        with self._lock:
            if base_url:
                self._base_url = base_url
            if token:
                self._auth_token = token
            if enabled is not None:
                self._enabled = enabled

    # =========================================================================
    # 공개 API
    # =========================================================================
    def sync_game_result(self, game_data: dict[str, Any]) -> bool:
        """
        경기 결과 전송 (POST /api/v1/games).

        - 성공: True 반환
        - 실패 또는 비활성: 큐에 저장 후 False 반환 (큐에서 재시도됨)
        """
        if not self.is_enabled:
            _logger.info("Cloud Sync 비활성 — 큐에 저장")
            self._enqueue("game_result", game_data)
            return False

        ok = self._http_post("/api/v1/games", game_data)
        if not ok:
            self._enqueue("game_result", game_data)
        return ok

    def sync_stats(self, stats_data: dict[str, Any]) -> bool:
        """실시간 스탯 전송 (best-effort, 큐 안 함)."""
        if not self.is_enabled:
            return False
        return self._http_post("/api/v1/stats", stats_data)

    # =========================================================================
    # HTTP 전송
    # =========================================================================
    def _http_post(self, path: str, payload: dict[str, Any]) -> bool:
        """
        백엔드 POST 호출 (재시도 포함).

        httpx 가 없으면 urllib fallback.
        """
        url = self._base_url.rstrip("/") + path
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "CourtViewDesk/1.0",
        }
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                if self._try_post(url, body, headers):
                    _logger.info(
                        "Cloud 전송 성공: %s (attempt %d/%d, %d bytes)",
                        path, attempt, _MAX_RETRIES, len(body),
                    )
                    return True
            except Exception as e:
                _logger.warning(
                    "Cloud 전송 실패: %s (attempt %d/%d): %s",
                    path, attempt, _MAX_RETRIES, e,
                )
            if attempt < _MAX_RETRIES:
                time.sleep(2.0 ** (attempt - 1))  # 1s, 2s

        return False

    @staticmethod
    def _try_post(url: str, body: bytes, headers: dict[str, str]) -> bool:
        """HTTP POST 단일 시도. True iff 2xx."""
        try:
            import httpx  # type: ignore[import-not-found]
            with httpx.Client(timeout=_TIMEOUT_SEC) as client:
                resp = client.post(url, content=body, headers=headers)
                return 200 <= resp.status_code < 300
        except ImportError:
            pass

        # Fallback: urllib
        import urllib.error
        import urllib.request
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as e:
            _logger.debug("urllib HTTPError %d: %s", e.code, e.reason)
            return False

    # =========================================================================
    # 오프라인 큐
    # =========================================================================
    def _enqueue(self, kind: str, payload: dict[str, Any]) -> None:
        """큐에 저장 (JSONL, 한 줄 = 한 엔트리)."""
        ts = int(time.time() * 1000)
        filename = self._queue_dir / f"{ts}_{kind}.json"
        try:
            filename.write_text(
                json.dumps({"kind": kind, "payload": payload, "ts": ts}, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            _logger.info("큐 저장: %s", filename.name)
        except Exception:
            _logger.exception("큐 저장 실패")

    def flush_queue(self) -> tuple[int, int]:
        """
        큐 내 모든 항목 전송 시도.

        Returns:
            (sent, failed)
        """
        if not self.is_enabled:
            return 0, 0

        sent = 0
        failed = 0
        for f in sorted(self._queue_dir.glob("*_*.json")):
            try:
                entry = json.loads(f.read_text(encoding="utf-8"))
                kind = entry.get("kind", "")
                payload = entry.get("payload", {})

                path = "/api/v1/games" if kind == "game_result" else "/api/v1/stats"
                ok = self._http_post(path, payload)
                if ok:
                    f.unlink(missing_ok=True)
                    sent += 1
                else:
                    failed += 1
            except Exception:
                _logger.exception("큐 항목 처리 실패: %s", f.name)
                failed += 1

        if sent or failed:
            _logger.info("큐 flush: %d 전송 성공, %d 실패", sent, failed)
        return sent, failed

    # =========================================================================
    # 백그라운드 워커
    # =========================================================================
    def start_worker(self) -> None:
        """백그라운드 재시도 워커 시작."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="cloud-sync-worker",
            daemon=True,
        )
        self._worker_thread.start()
        _logger.info(
            "Cloud Sync 워커 시작 (enabled=%s, interval=%.0fs)",
            self.is_enabled, _RETRY_WORKER_INTERVAL_SEC,
        )

    def stop_worker(self) -> None:
        """워커 종료."""
        self._stop_event.set()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=3.0)
            self._worker_thread = None

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.is_enabled:
                    self.flush_queue()
            except Exception:
                _logger.exception("Cloud Sync 워커 오류")
            self._stop_event.wait(_RETRY_WORKER_INTERVAL_SEC)

    def get_queue_size(self) -> int:
        """대기 중 큐 항목 수."""
        try:
            return sum(1 for _ in self._queue_dir.glob("*_*.json"))
        except Exception:
            return 0


__all__ = ["CloudSyncService"]
