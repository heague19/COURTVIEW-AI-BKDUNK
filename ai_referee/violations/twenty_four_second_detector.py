# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/violations
파일: twenty_four_second_detector.py
설명: 24초 슛클락 바이올레이션 감지 (FIBA Rule 29)
      - 점유 시작 후 24초 이내 슛 시도 추적
      - 공격 리바운드 시 14초 리셋
      - 파울 후 14초 또는 남은 시간 중 큰 값 리셋
      - 슛이 림에 닿아야 리셋

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024, Rule 29
    - configs/ai_referee/violation_thresholds.yaml: shot_clock 섹션
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import ViolationType
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import (
    FrameContext,
    RuleParameters,
    RuleResult,
    ViolationRule,
)

logger: Final = logging.getLogger(__name__)

_DEFAULT_MAX_SEC: Final[float] = 24.0
_DEFAULT_RESET_14_SEC: Final[float] = 14.0


@dataclass(slots=True)
class _ShotClockState:
    """슛클락 상태."""
    active: bool = False
    start_frame: int = 0
    remaining_sec: float = 24.0
    possession_team_id: str = ""
    rim_hit: bool = False


class TwentyFourSecondDetector(ViolationRule):
    """
    24초 슛클락 바이올레이션 감지기 (FIBA Rule 29).

    공격팀은 점유 시작 후 24초 이내에 슛을 시도해야 하며,
    슛이 림에 닿아야 합니다.

    리셋 조건:
      - 수비팀 점유 변경 시 24초 리셋
      - 공격 리바운드 시 14초 리셋
      - 파울 후 14초 또는 남은 시간 중 큰 값으로 리셋
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
        *,
        parameters: RuleParameters | None = None,
    ) -> None:
        super().__init__(
            rule_id=f"{rule_set.value.upper()}-29",
            rule_set=rule_set,
            call_type=CallType.SHOT_CLOCK_VIOLATION,
            violation_type=ViolationType.SHOT_CLOCK,
            rule_reference="FIBA Rule 29",
            description="24초 슛클락 바이올레이션",
            parameters=parameters,
        )
        self._state_lock = RLock()

        p = self._parameters
        self._max_sec = p.get_float("detection.max_duration_sec", _DEFAULT_MAX_SEC)
        self._reset_14_on_oreb = p.get_bool("detection.reset_14_on_oreb", True)
        self._reset_14_on_foul = p.get_bool("detection.reset_14_on_foul", True)
        self._must_hit_rim = p.get_bool("detection.must_hit_rim", True)

        self._state: _ShotClockState | None = None

    def applies_to(self, context: FrameContext) -> bool:
        return (
            context.is_live_ball
            and not context.is_dead_ball
            and context.possession_team_id is not None
        )

    def evaluate(self, context: FrameContext) -> RuleResult:
        evidence: list[str] = []
        confidence = 0.0

        with self._state_lock:
            # 점유 변경 시 24초 풀 리셋
            if (
                self._state is not None
                and self._state.possession_team_id != context.possession_team_id
            ):
                self._state = None

            # 새 점유 시작
            if self._state is None:
                self._state = _ShotClockState(
                    active=True,
                    start_frame=context.frame_number,
                    remaining_sec=self._max_sec,
                    possession_team_id=context.possession_team_id or "",
                )

            # 이벤트 기반 리셋 처리
            event = context.extra.get("shot_clock_event", "")

            if event == "offensive_rebound" and self._reset_14_on_oreb:
                # 공격 리바운드 — 14초 리셋
                self._state.remaining_sec = _DEFAULT_RESET_14_SEC
                self._state.start_frame = context.frame_number
                self._state.rim_hit = False
                return self._make_violation_result(
                    context, violated=False, confidence=0.0,
                )

            if event == "foul" and self._reset_14_on_foul:
                # 파울 — 14초 또는 남은 시간 중 큰 값
                self._state.remaining_sec = max(
                    self._state.remaining_sec, _DEFAULT_RESET_14_SEC,
                )
                self._state.rim_hit = False
                return self._make_violation_result(
                    context, violated=False, confidence=0.0,
                )

            if event == "rim_hit":
                self._state.rim_hit = True

            if event == "shot_attempt" and self._state.rim_hit:
                # 림에 맞은 슛 시도 — 클락 리셋
                self._state = None
                return self._make_violation_result(
                    context, violated=False, confidence=0.0,
                )

            # 시간 동기화 — FrameContext.shot_clock_sec 활용 (더 정확)
            shot_clock = context.shot_clock_sec
            if shot_clock >= 0:
                self._state.remaining_sec = shot_clock
            else:
                # shot_clock_sec가 음수 (이미 만료)
                self._state.remaining_sec = shot_clock

            # 24초 만료 체크
            if self._state.remaining_sec <= 0.0:
                elapsed = self._max_sec - self._state.remaining_sec
                confidence = min(
                    0.92 + abs(self._state.remaining_sec) * 0.02,
                    0.98,
                )
                evidence.append(
                    f"24초 슛클락 위반: 경과={elapsed:.2f}s "
                    f"(한계: {self._max_sec:.1f}s)",
                )
                violated = confidence >= self.min_confidence
                result = self._make_violation_result(
                    context,
                    violated=violated,
                    confidence=confidence,
                    description="슛클락: " + "; ".join(evidence) if evidence else "",
                    evidence=evidence,
                    offending_player_id=(
                        context.ball_possession_player_id if violated else None
                    ),
                    start_frame=self._state.start_frame,
                )
                self._state = None
                return result

        return self._make_violation_result(
            context, violated=False, confidence=0.0,
        )

    def reset(self) -> None:
        super().reset()
        with self._state_lock:
            self._state = None


__all__ = ["TwentyFourSecondDetector"]
__version__ = "1.0.0"
