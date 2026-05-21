# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/diagnostics
파일: flow_logger.py
설명: 데이터 흐름 추적 로거 (Plan E STEP 1-4 / 2026-05-13).

      카메라에서 감지/분석으로 가는 각 단계에서 "어디에서 무엇을 수신 → 어디로
      무엇을 전달" 형태의 흐름 로그를 throttle 해서 출력. silence_loggers 의
      대상이 아닌 별도 logger ('courtview.flow') 를 사용하므로 launcher 의
      _SILENCE_VERBOSE 설정과 무관하게 항상 활성.

      throttle: 처음 first_n 번은 매번, 그 이후엔 every 번마다 1회.
      이렇게 하면 시작 직후 5번 + 이후 100 프레임마다 = 부담 적고 가시성 충분.

      환경변수:
        COURTVIEW_FLOW_LOG=off  → 전체 비활성

작성자: SPOIN_COURTVIEW
최종 수정: 2026-05-13
버전: 1.0.0
"""
from __future__ import annotations

import logging
import os
from threading import Lock
from typing import Final

_logger = logging.getLogger("courtview.flow")
_counter_lock = Lock()
_counters: dict[str, int] = {}

_FLOW_ENABLED: bool = (
    os.environ.get("COURTVIEW_FLOW_LOG", "on").strip().lower() != "off"
)


def set_flow_enabled(enabled: bool) -> None:
    """런타임에 flow 로깅 on/off."""
    global _FLOW_ENABLED
    _FLOW_ENABLED = enabled


def log_flow(
    stage: str,
    message: str,
    *args: object,
    first_n: int = 5,
    every: int = 100,
    level: int = logging.INFO,
) -> None:
    """
    데이터 흐름 단계 로그 (throttled).

    Args:
        stage:    단계 이름 — 카운터 키로도 사용 (예: "INGEST", "PIPE-IN", "DET",
                  "BUFFER", "POSS_CB"). stage 별로 독립 카운터.
        message:  사람 읽기 좋은 한국어 메시지. %s/%d 등 포맷 지원.
        first_n:  처음 N번은 throttle 무시 (시작 직후 흐름 확인용).
        every:    그 이후엔 every 번마다 1회 로그.
        level:    기본 INFO. WARNING/ERROR 도 가능.
    """
    if not _FLOW_ENABLED:
        return

    with _counter_lock:
        n = _counters.get(stage, 0) + 1
        _counters[stage] = n

    if n <= first_n or n % every == 0:
        # [FLOW][STAGE #N] message
        prefix = f"[FLOW][{stage} #{n}] "
        try:
            _logger.log(level, prefix + message, *args)
        except Exception:
            # 메시지 포맷 실패해도 본 흐름 깨지지 말 것
            _logger.log(level, "%s%s (args=%s)", prefix, message, args)


__all__ = ["log_flow", "set_flow_enabled"]
__version__ = "1.0.0"
