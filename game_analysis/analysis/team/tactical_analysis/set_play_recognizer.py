# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/tactical_analysis
파일: set_play_recognizer.py
설명: 14종 세트 플레이 인식기
      - 하프코트 오펜스 패턴 매칭
      - 세트 플레이 PPP 산출
      - 플레이 빈도/성공률 분석

      14종: horn, flex, motion, floppy, princeton, triangle,
            pick_and_roll, pick_and_pop, isolation, post_up,
            dribble_hand_off, stagger_screen, spain_pnr, ato_set

      학술 근거:
        Lamas et al. (2011) — Modeling the Offensive Process in Basketball
        Synergy Sports — Play Type Classification

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/tactical_analysis.yaml (set_play_recognition 섹션)
의존성: shared/constants/tactical_constants.py, shared/dto/tactical_dto.py
소비자: coaching_intelligence, opponent_scouting, pre_game
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import SetPlayType
from shared.dto.tactical_dto import (
    SetPlayAnalysis,
    DetectedPlay,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class SetPlayRecognizerConfig:
    """세트 플레이 인식기 설정."""

    min_confidence: float = 0.65
    temporal_window_sec: float = 8.0
    top_plays_count: int = 5

    @classmethod
    def from_yaml(cls, cfg: dict) -> SetPlayRecognizerConfig:
        """YAML 설정으로부터 생성.

        NOTE: `@dataclass(slots=True)`에서는 `cls.field` 접근이 슬롯 디스크립터를
        반환하므로 dataclass 기본값을 리터럴로 직접 사용한다 (S8 수정).
        """
        spr = cfg.get("set_play_recognition", {})
        return cls(
            min_confidence=float(spr.get("min_confidence", 0.65)),
            temporal_window_sec=float(spr.get("temporal_window_sec", 8.0)),
            top_plays_count=int(spr.get("top_plays_count", 5)),
        )


# =============================================================================
# 입력 데이터
# =============================================================================
@dataclass(slots=True)
class SetPlayEventInput:
    """세트 플레이 인식 이벤트 입력."""

    team_id: str
    possession_id: str = ""
    play_type: SetPlayType = SetPlayType.MOTION
    # 결과
    points_scored: int = 0
    resulted_in_shot: bool = False
    shot_made: bool = False
    resulted_in_turnover: bool = False
    # 메타
    confidence: float = 0.70
    timestamp: float = 0.0
    # 관련 선수
    key_player_ids: list[int] = field(default_factory=list)


# =============================================================================
# 내부 누적기
# =============================================================================
@dataclass(slots=True)
class _PlayAccumulator:
    """플레이 유형별 누적 데이터."""

    count: int = 0
    points: int = 0
    shots: int = 0
    makes: int = 0
    turnovers: int = 0


@dataclass(slots=True)
class _TeamPlayAccumulator:
    """팀별 세트 플레이 누적."""

    total_set_plays: int = 0
    total_points: int = 0
    plays: dict[str, _PlayAccumulator] = field(default_factory=dict)


# =============================================================================
# 세트 플레이 인식기
# =============================================================================
class SetPlayRecognizer:
    """
    14종 세트 플레이 인식 및 효율 분석기.

    POSSESSION cadence (<100ms).
    """

    def __init__(self, config: SetPlayRecognizerConfig | None = None) -> None:
        self._config = config or SetPlayRecognizerConfig()
        self._lock = RLock()
        self._teams: dict[str, _TeamPlayAccumulator] = {}
        self._event_history: list[SetPlayEventInput] = []
        self._name = "SetPlayRecognizer"

    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> SetPlayRecognizerConfig:
        return self._config

    # --- 핵심 메서드 ---
    def process_set_play(self, event: SetPlayEventInput) -> bool:
        """세트 플레이 이벤트 처리."""
        if event.confidence < self._config.min_confidence:
            return False

        with self._lock:
            tacc = self._teams.setdefault(event.team_id, _TeamPlayAccumulator())
            tacc.total_set_plays += 1
            tacc.total_points += event.points_scored

            # 플레이 유형별 누적
            play_key = event.play_type.value
            pacc = tacc.plays.setdefault(play_key, _PlayAccumulator())
            pacc.count += 1
            pacc.points += event.points_scored
            if event.resulted_in_shot:
                pacc.shots += 1
                if event.shot_made:
                    pacc.makes += 1
            if event.resulted_in_turnover:
                pacc.turnovers += 1

            # 히스토리 (메모리 가드)
            self._event_history.append(event)
            if len(self._event_history) > _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

            return True

    # --- 조회 ---
    def get_team_analysis(self, team_id: str) -> SetPlayAnalysis:
        """팀별 세트 플레이 분석 결과 (DTO)."""
        with self._lock:
            tacc = self._teams.get(team_id)
            if tacc is None or tacc.total_set_plays == 0:
                return SetPlayAnalysis()

            ppp = tacc.total_points / tacc.total_set_plays

            # 감지된 플레이 목록
            detected: list[DetectedPlay] = []
            for play_key, pacc in tacc.plays.items():
                success_rate = pacc.makes / pacc.shots if pacc.shots > 0 else 0.0
                detected.append(DetectedPlay(
                    play_name=play_key,
                    count=pacc.count,
                    success_rate=round(success_rate, 3),
                ))

            # 빈도순 정렬
            detected.sort(key=lambda d: d.count, reverse=True)

            # 상위 플레이
            top_plays = [d.play_name for d in detected[:self._config.top_plays_count]]

            return SetPlayAnalysis(
                detected_plays=detected,
                total_set_plays=tacc.total_set_plays,
                set_play_ppp=round(ppp, 3),
                top_plays=top_plays,
            )

    def get_play_ppp(self, team_id: str, play_type: SetPlayType) -> float:
        """특정 플레이 유형의 PPP."""
        with self._lock:
            tacc = self._teams.get(team_id)
            if tacc is None:
                return 0.0
            pacc = tacc.plays.get(play_type.value)
            if pacc is None or pacc.count == 0:
                return 0.0
            return round(pacc.points / pacc.count, 3)

    def get_play_frequency(self, team_id: str) -> dict[str, float]:
        """플레이 유형별 빈도 (비율 %)."""
        with self._lock:
            tacc = self._teams.get(team_id)
            if tacc is None or tacc.total_set_plays == 0:
                return {}
            return {
                k: round(v.count / tacc.total_set_plays * 100.0, 1)
                for k, v in tacc.plays.items()
            }

    def get_play_turnover_rate(self, team_id: str, play_type: SetPlayType) -> float:
        """특정 플레이의 턴오버율 (%)."""
        with self._lock:
            tacc = self._teams.get(team_id)
            if tacc is None:
                return 0.0
            pacc = tacc.plays.get(play_type.value)
            if pacc is None or pacc.count == 0:
                return 0.0
            return round(pacc.turnovers / pacc.count * 100.0, 1)

    def get_event_history(self) -> list[SetPlayEventInput]:
        """이벤트 히스토리 반환 (방어적 복사)."""
        with self._lock:
            return list(self._event_history)

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._teams.clear()
            self._event_history.clear()


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "SetPlayRecognizerConfig",
    "SetPlayRecognizer",
    "SetPlayEventInput",
]

__version__ = "1.0.0"
