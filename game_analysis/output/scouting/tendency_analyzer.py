# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/scouting
파일: tendency_analyzer.py
설명: 상대팀 성향 분석기
      - 슛존별 선호도 분석 (CourtZone 20종 기반)
      - 플레이유형별 선호도 분석 (PlayType 13종 기반)
      - 전환 공격 성향, 3점 비율, 페인트 공격 비율
      - 방향 선호도 (좌/우측 공격)

Processing Cadence: POST-GAME (무제한)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/scouting_dto.py (TendencyReport)
      shared/constants/game_rule_constants.py (CourtZone, PlayType)
의존성: shared/dto/scouting_dto.py, shared/constants/game_rule_constants.py
소비자: scouting_report_builder, weakness_finder, coaching_intelligence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import CourtZone, PlayType
from shared.dto.scouting_dto import TendencyReport

logger: Final = logging.getLogger(__name__)

_MAX_SHOT_RECORDS: Final[int] = 5000  # 최대 슛 기록 수
_MAX_POSSESSION_RECORDS: Final[int] = 3000  # 최대 점유 기록 수


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class TendencyAnalyzerConfig:
    """성향 분석기 설정."""

    max_shot_records: int = _MAX_SHOT_RECORDS
    max_possession_records: int = _MAX_POSSESSION_RECORDS
    # 최소 샘플 수 (신뢰도 확보)
    min_shots_for_zone: int = 5  # 존별 최소 슛 횟수
    min_possessions_for_play_type: int = 3  # 유형별 최소 점유 수

    @classmethod
    def from_yaml(cls, cfg: dict) -> TendencyAnalyzerConfig:
        """YAML 설정에서 생성."""
        return cls(
            max_shot_records=cfg.get("max_shot_records", _MAX_SHOT_RECORDS),
            max_possession_records=cfg.get(
                "max_possession_records", _MAX_POSSESSION_RECORDS
            ),
            min_shots_for_zone=cfg.get("min_shots_for_zone", 5),
            min_possessions_for_play_type=cfg.get(
                "min_possessions_for_play_type", 3
            ),
        )


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class ShotRecordInput:
    """슛 기록 입력."""

    zone: str = ""  # CourtZone.value
    made: bool = False
    points: int = 0
    # 방향 (코트 좌우 기준)
    court_side: str = ""  # "left" / "right" / "center"


@dataclass(slots=True)
class PossessionRecordInput:
    """점유 기록 입력."""

    play_type: str = ""  # PlayType.value
    is_transition: bool = False  # 전환 공격 여부
    points_scored: int = 0
    court_side: str = ""  # "left" / "right" / "center"


# =============================================================================
# 분석기
# =============================================================================
class TendencyAnalyzer:
    """
    상대팀 성향 분석기.

    슛존/플레이유형 선호도, 전환 성향, 방향 선호도를 분석합니다.
    """

    def __init__(self, config: TendencyAnalyzerConfig | None = None) -> None:
        self._config = config or TendencyAnalyzerConfig()
        self._lock = RLock()
        self._team_id: str = ""
        self._shots: list[ShotRecordInput] = []
        self._possessions: list[PossessionRecordInput] = []

    @property
    def name(self) -> str:
        return "TendencyAnalyzer"

    # === 데이터 입력 ===

    def set_team_id(self, team_id: str) -> None:
        """팀 ID 설정."""
        with self._lock:
            self._team_id = team_id

    def add_shot(self, shot: ShotRecordInput) -> None:
        """슛 기록 추가."""
        with self._lock:
            if len(self._shots) >= self._config.max_shot_records:
                self._shots = self._shots[-self._config.max_shot_records // 2 :]
            self._shots.append(shot)

    def add_possession(self, poss: PossessionRecordInput) -> None:
        """점유 기록 추가."""
        with self._lock:
            if len(self._possessions) >= self._config.max_possession_records:
                self._possessions = self._possessions[
                    -self._config.max_possession_records // 2 :
                ]
            self._possessions.append(poss)

    # === 분석 ===

    def analyze(self) -> TendencyReport:
        """
        성향 분석 실행.

        Returns:
            TendencyReport DTO
        """
        with self._lock:
            shot_zone_prefs = self._calc_shot_zone_preferences()
            play_type_prefs = self._calc_play_type_preferences()
            transition = self._calc_transition_tendency()
            three_rate, paint_rate = self._calc_shot_tendency()
            right_pref, left_pref = self._calc_direction_preference()

            return TendencyReport(
                team_id=self._team_id,
                shot_zone_preferences=shot_zone_prefs,
                play_type_preferences=play_type_prefs,
                transition_tendency=round(transition, 1),
                three_point_rate=round(three_rate, 3),
                paint_attack_rate=round(paint_rate, 3),
                right_side_preference=round(right_pref, 3),
                left_side_preference=round(left_pref, 3),
            )

    # === 내부 메서드 ===

    def _calc_shot_zone_preferences(self) -> dict[str, float]:
        """슛존별 선호도 (빈도 %) 계산."""
        total = len(self._shots)
        if total == 0:
            return {}

        zone_counts: dict[str, int] = {}
        for s in self._shots:
            if s.zone:
                zone_counts[s.zone] = zone_counts.get(s.zone, 0) + 1

        result: dict[str, float] = {}
        for zone, count in zone_counts.items():
            if count >= self._config.min_shots_for_zone:
                result[zone] = round(count / total * 100.0, 1)
        return result

    def _calc_play_type_preferences(self) -> dict[str, float]:
        """플레이유형별 선호도 (빈도 %) 계산."""
        total = len(self._possessions)
        if total == 0:
            return {}

        type_counts: dict[str, int] = {}
        for p in self._possessions:
            if p.play_type:
                type_counts[p.play_type] = type_counts.get(p.play_type, 0) + 1

        result: dict[str, float] = {}
        for play_type, count in type_counts.items():
            if count >= self._config.min_possessions_for_play_type:
                result[play_type] = round(count / total * 100.0, 1)
        return result

    def _calc_transition_tendency(self) -> float:
        """전환 점유 비율 (%)."""
        total = len(self._possessions)
        if total == 0:
            return 0.0
        trans_count = sum(1 for p in self._possessions if p.is_transition)
        return trans_count / total * 100.0

    def _calc_shot_tendency(self) -> tuple[float, float]:
        """3점 시도 비율 및 페인트 공격 비율."""
        total = len(self._shots)
        if total == 0:
            return 0.0, 0.0

        # 3점 존 집합 (CourtZone enum의 3점 관련 값들)
        three_zones = {
            CourtZone.THREE_LEFT_CORNER.value,
            CourtZone.THREE_LEFT_WING.value,
            CourtZone.THREE_LEFT_TOP.value,
            CourtZone.THREE_CENTER.value,
            CourtZone.THREE_RIGHT_TOP.value,
            CourtZone.THREE_RIGHT_WING.value,
            CourtZone.THREE_RIGHT_CORNER.value,
            CourtZone.DEEP_THREE_LEFT.value,
            CourtZone.DEEP_THREE_CENTER.value,
            CourtZone.DEEP_THREE_RIGHT.value,
        }
        paint_zones = {
            CourtZone.PAINT_LEFT.value,
            CourtZone.PAINT_CENTER.value,
            CourtZone.PAINT_RIGHT.value,
        }

        three_count = sum(1 for s in self._shots if s.zone in three_zones)
        paint_count = sum(1 for s in self._shots if s.zone in paint_zones)

        return three_count / total, paint_count / total

    def _calc_direction_preference(self) -> tuple[float, float]:
        """방향 선호도 (우/좌측 비율)."""
        total = len(self._possessions)
        if total == 0:
            return 0.0, 0.0
        right = sum(1 for p in self._possessions if p.court_side == "right")
        left = sum(1 for p in self._possessions if p.court_side == "left")
        return right / total, left / total

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._team_id = ""
            self._shots.clear()
            self._possessions.clear()

    def get_event_history(self) -> list[ShotRecordInput]:
        """슛 기록 이력."""
        with self._lock:
            return list(self._shots)


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "TendencyAnalyzerConfig",
    "TendencyAnalyzer",
    "ShotRecordInput",
    "PossessionRecordInput",
]

__version__ = "1.0.0"
