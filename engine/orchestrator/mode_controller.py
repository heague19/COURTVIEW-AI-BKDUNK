# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/orchestrator
파일: mode_controller.py
설명: 엔진 실행 모드 제어
      - LIVE: 실시간 분석 (30fps 제약, frame_budget 33ms)
      - BATCH: 배치 분석 (FPS 제약 없음, 최대 속도)
      - REPLAY: 리플레이 분석 (속도 배율 조절 가능)
      - 모드별 실행 파라미터 자동 조정

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: EngineConfig, EngineMode, CadenceConfig

소비자:
    - engine/orchestrator/game_orchestrator.py: 메인 루프 파라미터 조회
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from engine.config import CadenceConfig, EngineMode

_logger = logging.getLogger(__name__)


# =============================================================================
# 모드별 실행 파라미터
# =============================================================================
@dataclass(slots=True)
class ModeParameters:
    """
    모드별 실행 파라미터.

    Attributes:
        mode: 현재 모드
        fps_limited: FPS 제약 적용 여부
        frame_budget_ms: 프레임 시간 예산 (ms, 0=무제한)
        max_batch_size: GPU 배치 크기 상한
        enable_stage2: Stage2 (ViTPose) 활성화
        enable_referee: AI 심판 활성화
        enable_recording: 4K 녹화 활성화
        playback_speed: 재생 속도 배율 (REPLAY 전용, 1.0=실시간)
    """

    mode: EngineMode = EngineMode.LIVE
    fps_limited: bool = True
    frame_budget_ms: float = 33.0
    max_batch_size: int = 8
    enable_stage2: bool = True
    enable_referee: bool = True
    enable_recording: bool = True
    playback_speed: float = 1.0


# =============================================================================
# 모드별 프리셋
# =============================================================================
_LIVE_PARAMS: Final[ModeParameters] = ModeParameters(
    mode=EngineMode.LIVE,
    fps_limited=True,
    frame_budget_ms=33.0,
    max_batch_size=8,
    enable_stage2=True,
    enable_referee=True,
    enable_recording=True,
    playback_speed=1.0,
)

_BATCH_PARAMS: Final[ModeParameters] = ModeParameters(
    mode=EngineMode.BATCH,
    fps_limited=False,
    frame_budget_ms=0.0,
    max_batch_size=16,
    enable_stage2=True,
    enable_referee=True,
    enable_recording=False,
    playback_speed=0.0,
)

_REPLAY_PARAMS: Final[ModeParameters] = ModeParameters(
    mode=EngineMode.REPLAY,
    fps_limited=True,
    frame_budget_ms=33.0,
    max_batch_size=8,
    enable_stage2=True,
    enable_referee=True,
    enable_recording=False,
    playback_speed=1.0,
)

_MODE_PRESET_MAP: Final[dict[EngineMode, ModeParameters]] = {
    EngineMode.LIVE: _LIVE_PARAMS,
    EngineMode.BATCH: _BATCH_PARAMS,
    EngineMode.REPLAY: _REPLAY_PARAMS,
}


# =============================================================================
# 모드 컨트롤러
# =============================================================================
class ModeController:
    """
    엔진 실행 모드 제어.

    모드 전환 시 실행 파라미터를 자동 조정합니다.
    game_orchestrator의 메인 루프가 참조합니다.
    """

    __slots__ = ("_current", "_cadence_config", "_lock")

    def __init__(
        self,
        initial_mode: EngineMode = EngineMode.LIVE,
        cadence_config: CadenceConfig | None = None,
    ) -> None:
        preset = _MODE_PRESET_MAP[initial_mode]
        cfg = cadence_config or CadenceConfig()

        # LIVE 모드는 CadenceConfig 값 반영
        self._current = ModeParameters(
            mode=preset.mode,
            fps_limited=preset.fps_limited,
            frame_budget_ms=cfg.frame_budget_ms if preset.fps_limited else 0.0,
            max_batch_size=preset.max_batch_size,
            enable_stage2=preset.enable_stage2,
            enable_referee=preset.enable_referee,
            enable_recording=preset.enable_recording,
            playback_speed=preset.playback_speed,
        )
        self._cadence_config = cfg
        self._lock: RLock = RLock()

    def switch_mode(self, mode: EngineMode) -> ModeParameters:
        """
        모드 전환.

        Args:
            mode: 전환 대상 모드

        Returns:
            새 모드 파라미터
        """
        with self._lock:
            preset = _MODE_PRESET_MAP[mode]
            self._current = ModeParameters(
                mode=mode,
                fps_limited=preset.fps_limited,
                frame_budget_ms=(
                    self._cadence_config.frame_budget_ms
                    if preset.fps_limited else 0.0
                ),
                max_batch_size=preset.max_batch_size,
                enable_stage2=preset.enable_stage2,
                enable_referee=preset.enable_referee,
                enable_recording=preset.enable_recording,
                playback_speed=preset.playback_speed,
            )
            _logger.info("모드 전환: %s", mode.value)
            return self.parameters

    def set_playback_speed(self, speed: float) -> None:
        """REPLAY 모드 재생 속도 변경 (0.25~4.0)."""
        with self._lock:
            if self._current.mode != EngineMode.REPLAY:
                _logger.warning("REPLAY 모드가 아닌 상태에서 속도 변경 무시")
                return
            self._current.playback_speed = max(0.25, min(4.0, speed))
            self._current.frame_budget_ms = (
                self._cadence_config.frame_budget_ms / self._current.playback_speed
            )

    @property
    def parameters(self) -> ModeParameters:
        """현재 모드 파라미터 (방어적 복사)."""
        with self._lock:
            c = self._current
            return ModeParameters(
                mode=c.mode,
                fps_limited=c.fps_limited,
                frame_budget_ms=c.frame_budget_ms,
                max_batch_size=c.max_batch_size,
                enable_stage2=c.enable_stage2,
                enable_referee=c.enable_referee,
                enable_recording=c.enable_recording,
                playback_speed=c.playback_speed,
            )

    @property
    def mode(self) -> EngineMode:
        return self._current.mode

    @property
    def is_live(self) -> bool:
        return self._current.mode == EngineMode.LIVE

    @property
    def is_batch(self) -> bool:
        return self._current.mode == EngineMode.BATCH

    def __repr__(self) -> str:
        c = self._current
        return (
            f"ModeController(mode={c.mode.value}, "
            f"budget={c.frame_budget_ms:.0f}ms, "
            f"fps_limited={c.fps_limited})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "ModeParameters",
    "ModeController",
]

__version__ = "1.0.0"
