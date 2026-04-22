# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_record
파일: play_by_play.py
설명: 플레이-바이-플레이 기록기
      - 경기 이벤트 시간순 로그
      - 이벤트별 스코어 상태 추적
      - 쿼터별/시간대별 필터링
      - 팀/선수별 이벤트 조회
      - 한글/영문 이벤트 설명 자동 생성

Processing Cadence: EVENT (<10ms, 증분)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/constants/game_rule_constants.py (GameEventType)
의존성: shared/constants/game_rule_constants.py
소비자: game_report_builder, api_server, quarter_summary
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import GameEventType

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 2000  # PBP는 이벤트 수가 많아 한도 확대


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class PlayByPlayConfig:
    """플레이-바이-플레이 설정."""

    # 최대 이벤트 수
    max_events: int = _MAX_EVENT_HISTORY
    # 한글 설명 생성 여부
    generate_korean_description: bool = True

    @classmethod
    def from_yaml(cls, cfg: dict) -> PlayByPlayConfig:
        """YAML 설정에서 생성."""
        return cls(
            max_events=cfg.get("max_events", _MAX_EVENT_HISTORY),
        )


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class PBPEventInput:
    """PBP 이벤트 입력."""

    event_type: GameEventType = GameEventType.SHOT_MADE
    team_id: str = ""
    player_id: int = 0
    secondary_player_id: int = 0  # 어시스터, 블로커 등
    jersey_number: int = 0
    secondary_jersey_number: int = 0
    # 시간
    quarter: int = 1
    game_clock: str = "10:00"  # MM:SS 형식
    timestamp_sec: float = 0.0
    # 점수
    points: int = 0
    home_score: int = 0
    away_score: int = 0
    is_home_team: bool = True
    # 부가 정보
    description: str = ""  # 수동 설명 (없으면 자동 생성)
    shot_type: str = ""  # layup, three_pointer 등
    confidence: float = 0.85


# =============================================================================
# 출력
# =============================================================================
@dataclass(slots=True)
class PBPEntry:
    """PBP 기록 항목."""

    sequence: int = 0  # 전체 순서 번호
    event_type: GameEventType = GameEventType.SHOT_MADE
    team_id: str = ""
    player_id: int = 0
    secondary_player_id: int = 0
    jersey_number: int = 0
    secondary_jersey_number: int = 0
    # 시간
    quarter: int = 1
    game_clock: str = "10:00"
    timestamp_sec: float = 0.0
    # 점수 상태
    home_score: int = 0
    away_score: int = 0
    score_margin: int = 0  # home - away
    # 설명
    description_ko: str = ""
    description_en: str = ""
    # 이벤트 특성
    is_scoring: bool = False
    is_turnover: bool = False
    is_foul: bool = False
    points: int = 0


@dataclass(slots=True)
class PBPSummary:
    """PBP 요약 통계."""

    total_events: int = 0
    scoring_events: int = 0
    turnovers: int = 0
    fouls: int = 0
    events_per_quarter: dict[int, int] = field(default_factory=dict)


# =============================================================================
# 이벤트 설명 자동 생성
# =============================================================================
_EVENT_DESC_KO: Final[dict[GameEventType, str]] = {
    GameEventType.SHOT_ATTEMPT: "#{jersey} 야투 시도",
    GameEventType.SHOT_MADE: "#{jersey} 야투 성공",
    GameEventType.SHOT_MISSED: "#{jersey} 야투 실패",
    GameEventType.FREE_THROW_ATTEMPT: "#{jersey} 자유투 시도",
    GameEventType.FREE_THROW_MADE: "#{jersey} 자유투 성공",
    GameEventType.FREE_THROW_MISSED: "#{jersey} 자유투 실패",
    GameEventType.OFFENSIVE_REBOUND: "#{jersey} 공격 리바운드",
    GameEventType.DEFENSIVE_REBOUND: "#{jersey} 수비 리바운드",
    GameEventType.ASSIST: "#{jersey} 어시스트 (→#{sec_jersey})",
    GameEventType.STEAL: "#{jersey} 스틸",
    GameEventType.BLOCK: "#{jersey} 블록",
    GameEventType.TURNOVER: "#{jersey} 턴오버",
    GameEventType.PERSONAL_FOUL: "#{jersey} 개인 파울",
    GameEventType.OFFENSIVE_FOUL: "#{jersey} 공격 파울",
    GameEventType.TECHNICAL_FOUL: "#{jersey} 테크니컬 파울",
    GameEventType.SUBSTITUTION: "교체: #{jersey} IN ↔ #{sec_jersey} OUT",
    GameEventType.TIMEOUT: "타임아웃",
    GameEventType.JUMP_BALL: "점프볼",
}

_EVENT_DESC_EN: Final[dict[GameEventType, str]] = {
    GameEventType.SHOT_ATTEMPT: "#{jersey} Shot Attempt",
    GameEventType.SHOT_MADE: "#{jersey} FG Made",
    GameEventType.SHOT_MISSED: "#{jersey} FG Missed",
    GameEventType.FREE_THROW_ATTEMPT: "#{jersey} FT Attempt",
    GameEventType.FREE_THROW_MADE: "#{jersey} FT Made",
    GameEventType.FREE_THROW_MISSED: "#{jersey} FT Missed",
    GameEventType.OFFENSIVE_REBOUND: "#{jersey} OREB",
    GameEventType.DEFENSIVE_REBOUND: "#{jersey} DREB",
    GameEventType.ASSIST: "#{jersey} AST (→#{sec_jersey})",
    GameEventType.STEAL: "#{jersey} STL",
    GameEventType.BLOCK: "#{jersey} BLK",
    GameEventType.TURNOVER: "#{jersey} TO",
    GameEventType.PERSONAL_FOUL: "#{jersey} PF",
    GameEventType.OFFENSIVE_FOUL: "#{jersey} OFF",
    GameEventType.TECHNICAL_FOUL: "#{jersey} TECH",
    GameEventType.SUBSTITUTION: "SUB: #{jersey} IN ↔ #{sec_jersey} OUT",
    GameEventType.TIMEOUT: "Timeout",
    GameEventType.JUMP_BALL: "Jump Ball",
}

# 득점 이벤트 집합
_SCORING_EVENTS: Final[frozenset[GameEventType]] = frozenset({
    GameEventType.SHOT_MADE,
    GameEventType.FREE_THROW_MADE,
})

# 턴오버 이벤트 집합
_TURNOVER_EVENTS: Final[frozenset[GameEventType]] = frozenset({
    GameEventType.TURNOVER,
})

# 파울 이벤트 집합
_FOUL_EVENTS: Final[frozenset[GameEventType]] = frozenset({
    GameEventType.PERSONAL_FOUL,
    GameEventType.OFFENSIVE_FOUL,
    GameEventType.TECHNICAL_FOUL,
})


# =============================================================================
# 기록기
# =============================================================================
class PlayByPlayRecorder:
    """
    플레이-바이-플레이 기록기.

    경기 이벤트를 시간순으로 기록하고, 스코어 상태를 추적합니다.
    """

    def __init__(self, config: PlayByPlayConfig | None = None) -> None:
        self._config = config or PlayByPlayConfig()
        self._lock = RLock()
        self._entries: list[PBPEntry] = []
        self._sequence: int = 0

    @property
    def name(self) -> str:
        return "PlayByPlayRecorder"

    # === 이벤트 기록 ===

    def record_event(self, event: PBPEventInput) -> PBPEntry:
        """
        이벤트를 PBP에 기록합니다.

        Args:
            event: PBP 이벤트 입력

        Returns:
            생성된 PBP 항목
        """
        with self._lock:
            self._sequence += 1

            # 메모리 가드
            if len(self._entries) >= self._config.max_events:
                self._entries = self._entries[-self._config.max_events // 2:]

            # 설명 생성
            desc_ko = event.description or self._generate_description(
                event, _EVENT_DESC_KO
            )
            desc_en = self._generate_description(event, _EVENT_DESC_EN)

            is_scoring = event.event_type in _SCORING_EVENTS
            is_turnover = event.event_type in _TURNOVER_EVENTS
            is_foul = event.event_type in _FOUL_EVENTS

            entry = PBPEntry(
                sequence=self._sequence,
                event_type=event.event_type,
                team_id=event.team_id,
                player_id=event.player_id,
                secondary_player_id=event.secondary_player_id,
                jersey_number=event.jersey_number,
                secondary_jersey_number=event.secondary_jersey_number,
                quarter=event.quarter,
                game_clock=event.game_clock,
                timestamp_sec=event.timestamp_sec,
                home_score=event.home_score,
                away_score=event.away_score,
                score_margin=event.home_score - event.away_score,
                description_ko=desc_ko,
                description_en=desc_en,
                is_scoring=is_scoring,
                is_turnover=is_turnover,
                is_foul=is_foul,
                points=event.points,
            )

            self._entries.append(entry)
            return entry

    # === 조회 ===

    def get_all_entries(self) -> list[PBPEntry]:
        """전체 PBP 항목 (시간순)."""
        with self._lock:
            return list(self._entries)

    def get_quarter_entries(self, quarter: int) -> list[PBPEntry]:
        """쿼터별 PBP 항목."""
        with self._lock:
            return [e for e in self._entries if e.quarter == quarter]

    def get_team_entries(self, team_id: str) -> list[PBPEntry]:
        """팀별 PBP 항목."""
        with self._lock:
            return [e for e in self._entries if e.team_id == team_id]

    def get_player_entries(self, player_id: int) -> list[PBPEntry]:
        """선수별 PBP 항목."""
        with self._lock:
            return [
                e for e in self._entries
                if e.player_id == player_id or e.secondary_player_id == player_id
            ]

    def get_scoring_entries(self) -> list[PBPEntry]:
        """득점 이벤트만 반환."""
        with self._lock:
            return [e for e in self._entries if e.is_scoring]

    def get_scoring_runs(self, min_run: int = 6) -> list[dict]:
        """
        스코어링 런 감지 (연속 N점 이상).

        Args:
            min_run: 최소 런 점수

        Returns:
            스코어링 런 목록 [{team_id, points, start_seq, end_seq}]
        """
        with self._lock:
            scoring = [e for e in self._entries if e.is_scoring]
            if not scoring:
                return []

            runs: list[dict] = []
            current_team = scoring[0].team_id
            current_points = scoring[0].points
            start_seq = scoring[0].sequence

            for e in scoring[1:]:
                if e.team_id == current_team:
                    current_points += e.points
                else:
                    if current_points >= min_run:
                        runs.append({
                            "team_id": current_team,
                            "points": current_points,
                            "start_seq": start_seq,
                            "end_seq": e.sequence - 1,
                        })
                    current_team = e.team_id
                    current_points = e.points
                    start_seq = e.sequence

            # 마지막 런
            if current_points >= min_run:
                runs.append({
                    "team_id": current_team,
                    "points": current_points,
                    "start_seq": start_seq,
                    "end_seq": scoring[-1].sequence,
                })

            return runs

    def get_summary(self) -> PBPSummary:
        """PBP 요약 통계."""
        with self._lock:
            epq: dict[int, int] = {}
            scoring = 0
            turnovers = 0
            fouls = 0

            for e in self._entries:
                epq[e.quarter] = epq.get(e.quarter, 0) + 1
                if e.is_scoring:
                    scoring += 1
                if e.is_turnover:
                    turnovers += 1
                if e.is_foul:
                    fouls += 1

            return PBPSummary(
                total_events=len(self._entries),
                scoring_events=scoring,
                turnovers=turnovers,
                fouls=fouls,
                events_per_quarter=epq,
            )

    def get_event_history(self) -> list[PBPEntry]:
        """이벤트 히스토리 (= get_all_entries 동일)."""
        return self.get_all_entries()

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._entries.clear()
            self._sequence = 0

    # === 내부 메서드 ===

    @staticmethod
    def _generate_description(
        event: PBPEventInput,
        templates: dict[GameEventType, str],
    ) -> str:
        """이벤트 설명 생성."""
        template = templates.get(event.event_type, str(event.event_type.value))
        return (
            template
            .replace("#{jersey}", str(event.jersey_number))
            .replace("#{sec_jersey}", str(event.secondary_jersey_number))
            .replace("{quarter}", str(event.quarter))
        )


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "PlayByPlayConfig",
    "PlayByPlayRecorder",
    "PBPEventInput",
    "PBPEntry",
    "PBPSummary",
]

__version__ = "1.0.0"
