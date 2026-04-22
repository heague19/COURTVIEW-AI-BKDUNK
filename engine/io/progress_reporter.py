# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/io
파일: progress_reporter.py
설명: 분석 진행률 보고
      - 프레임 진행률 (현재/전체)
      - 분석 단계별 진행률
      - FPS 실측
      - ETA 예측
      - WebSocket으로 프론트엔드에 주기적 보고

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: IOConfig

소비자:
    - engine/orchestrator/game_orchestrator.py: 메인 루프에서 주기적 호출
    - engine/io/result_dispatcher.py: WebSocket 전송 위임
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import RLock
from typing import Final

from engine.config import IOConfig

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProgressSnapshot:
    """
    진행률 스냅샷.

    Attributes:
        frame_current: 현재 프레임
        frame_total: 전체 프레임 (BATCH 모드, LIVE=0)
        progress_pct: 진행률 (0~100, LIVE=0)
        phase: 현재 분석 단계
        phase_pct: 단계 내 진행률 (0~100)
        fps: 실측 FPS
        eta_sec: 잔여 예상 시간 (초, LIVE=0)
    """

    frame_current: int = 0
    frame_total: int = 0
    progress_pct: float = 0.0
    phase: str = "idle"
    phase_pct: float = 0.0
    fps: float = 0.0
    eta_sec: float = 0.0


class ProgressReporter:
    """
    분석 진행률 보고기.

    주기적으로 진행 상태를 계산하고, should_report()가 True이면
    result_dispatcher를 통해 WebSocket 전송합니다.
    """

    __slots__ = (
        "_config",
        "_frame_current",
        "_frame_total",
        "_phase",
        "_phase_pct",
        "_start_time",
        "_last_report_time",
        "_frame_times",
        "_lock",
    )

    _MAX_FRAME_TIMES: Final = 100

    def __init__(self, config: IOConfig | None = None) -> None:
        self._config = config or IOConfig()
        self._frame_current: int = 0
        self._frame_total: int = 0
        self._phase: str = "idle"
        self._phase_pct: float = 0.0
        self._start_time: float = 0.0
        self._last_report_time: float = 0.0
        self._frame_times: list[float] = []
        self._lock: RLock = RLock()

    def start(self, total_frames: int = 0) -> None:
        """분석 시작."""
        with self._lock:
            self._frame_current = 0
            self._frame_total = max(0, total_frames)
            self._phase = "running"
            self._phase_pct = 0.0
            self._start_time = time.monotonic()
            self._last_report_time = 0.0
            self._frame_times.clear()

    def update_frame(self, frame_number: int) -> None:
        """프레임 카운터 갱신 + FPS 기록."""
        now = time.monotonic()
        with self._lock:
            self._frame_current = frame_number
            self._frame_times.append(now)
            if len(self._frame_times) > self._MAX_FRAME_TIMES:
                self._frame_times = self._frame_times[-self._MAX_FRAME_TIMES:]

    def update_phase(self, phase: str, pct: float = 0.0) -> None:
        """분석 단계 갱신."""
        with self._lock:
            self._phase = phase
            self._phase_pct = max(0.0, min(100.0, pct))

    def should_report(self) -> bool:
        """보고 주기 도달 여부."""
        now = time.monotonic()
        interval_sec = self._config.progress_interval_ms / 1000.0
        if now - self._last_report_time >= interval_sec:
            self._last_report_time = now
            return True
        return False

    def snapshot(self) -> ProgressSnapshot:
        """현재 진행률 스냅샷."""
        with self._lock:
            # FPS 계산
            fps = 0.0
            if len(self._frame_times) >= 2:
                dt = self._frame_times[-1] - self._frame_times[0]
                if dt > 0:
                    fps = (len(self._frame_times) - 1) / dt

            # 진행률 (BATCH 모드)
            progress = 0.0
            if self._frame_total > 0:
                progress = min(100.0, self._frame_current / self._frame_total * 100.0)

            # ETA
            eta = 0.0
            if self._frame_total > 0 and fps > 0:
                remaining = self._frame_total - self._frame_current
                if remaining > 0:
                    eta = remaining / fps

            return ProgressSnapshot(
                frame_current=self._frame_current,
                frame_total=self._frame_total,
                progress_pct=progress,
                phase=self._phase,
                phase_pct=self._phase_pct,
                fps=round(fps, 1),
                eta_sec=round(eta, 1),
            )

    def to_dict(self) -> dict:
        """WebSocket 전송용 딕셔너리."""
        s = self.snapshot()
        return {
            "type": "progress",
            "frame_current": s.frame_current,
            "frame_total": s.frame_total,
            "progress_pct": s.progress_pct,
            "phase": s.phase,
            "phase_pct": s.phase_pct,
            "fps": s.fps,
            "eta_sec": s.eta_sec,
        }

    def reset(self) -> None:
        with self._lock:
            self._frame_current = 0
            self._frame_total = 0
            self._phase = "idle"
            self._phase_pct = 0.0
            self._start_time = 0.0
            self._frame_times.clear()

    def __repr__(self) -> str:
        s = self.snapshot()
        return (
            f"ProgressReporter(frame={s.frame_current}/{s.frame_total}, "
            f"fps={s.fps}, phase={s.phase})"
        )


__all__ = [
    "ProgressSnapshot",
    "ProgressReporter",
]

__version__ = "1.0.0"
