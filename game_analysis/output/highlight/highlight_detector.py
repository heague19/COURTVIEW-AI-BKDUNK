# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/highlight
파일: highlight_detector.py
설명: 경기 이벤트 기반 하이라이트 후보 감지기
      - GameEvent → HighlightCandidate 변환
      - 이벤트 유형별 기본 점수 부여 (highlight.yaml 설정)
      - 클러치 상황 보너스 적용
      - 연속 이벤트 콤보 감지 (steal→fastbreak→dunk 등)
      - 선수 추적 보너스

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/highlight.yaml (detection 섹션)
의존성: shared/constants/game_rule_constants.py, shared/dto/game_dto.py
소비자: excitement_scorer, clip_extractor, coaching_intelligence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import (
    HighlightType,
    GameEventType,
)

logger: Final = logging.getLogger(__name__)

# === 상수 ===
_MAX_EVENT_HISTORY: Final[int] = 500
_DEFAULT_THRESHOLD: Final[float] = 55.0
_DEFAULT_MIN_CONFIDENCE: Final[float] = 0.40


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class HighlightDetectorConfig:
    """하이라이트 감지기 설정."""

    # 이벤트별 하이라이트 점수 (event_key → score)
    event_scores: dict[str, float] = field(default_factory=dict)
    # 하이라이트 선정 임계값
    threshold: float = _DEFAULT_THRESHOLD
    # 최소 신뢰도
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE
    # 클러치 보너스
    clutch_enabled: bool = True
    clutch_margin_points: int = 5
    clutch_time_remaining_sec: float = 300.0
    clutch_bonus_score: float = 20.0
    # 콤보 이벤트 규칙
    combo_rules: list[ComboRule] = field(default_factory=list)
    # 선수 추적 보너스
    player_tracking_enabled: bool = True
    player_tracking_bonus: float = 15.0
    # 연속 하이라이트 병합
    merge_max_gap_sec: float = 5.0
    merge_max_duration_sec: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> HighlightDetectorConfig:
        """YAML 설정에서 생성."""
        det = cfg.get("detection", {})
        clip = cfg.get("clip", {})
        custom = cfg.get("custom_rules", {})
        merge = det.get("merge", {})
        clutch = det.get("clutch_bonus", {})

        # 콤보 규칙 파싱
        combo_rules: list[ComboRule] = []
        for rule in custom.get("combo_events", []):
            combo_rules.append(ComboRule(
                name=rule.get("name", ""),
                events=rule.get("events", []),
                max_gap_sec=rule.get("max_gap_sec", 10.0),
                bonus_score=rule.get("bonus_score", 0.0),
            ))

        return cls(
            event_scores=det.get("event_scores", {}),
            threshold=det.get("threshold", _DEFAULT_THRESHOLD),
            clutch_enabled=clutch.get("enabled", True),
            clutch_margin_points=clutch.get("margin_points", 5),
            clutch_time_remaining_sec=clutch.get("time_remaining_sec", 300.0),
            clutch_bonus_score=clutch.get("bonus_score", 20.0),
            combo_rules=combo_rules,
            player_tracking_enabled=custom.get("player_tracking", {}).get("enabled", True),
            player_tracking_bonus=custom.get("player_tracking", {}).get("bonus_score_for_tracked", 15.0),
            merge_max_gap_sec=merge.get("max_gap_sec", 5.0),
            merge_max_duration_sec=merge.get("max_merged_duration_sec", 30.0),
        )


@dataclass(slots=True)
class ComboRule:
    """콤보 이벤트 규칙."""

    name: str = ""
    events: list[str] = field(default_factory=list)
    max_gap_sec: float = 10.0
    bonus_score: float = 0.0


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class HighlightEventInput:
    """하이라이트 감지용 이벤트 입력."""

    # 이벤트 식별
    event_id: str = ""
    event_key: str = ""  # highlight.yaml event_scores 키
    team_id: str = ""
    # 선수
    primary_player_id: int = 0
    related_player_ids: list[int] = field(default_factory=list)
    # 시간
    timestamp_sec: float = 0.0
    quarter: int = 1
    game_clock_sec: float = 720.0  # 쿼터 내 남은 시간
    # 점수 상황
    home_score: int = 0
    away_score: int = 0
    is_home_team: bool = True
    # 득점
    points_scored: int = 0
    # 하이라이트 유형 (매핑 가능 시)
    highlight_type: HighlightType | None = None
    # 신뢰도
    confidence: float = 0.85


@dataclass(slots=True)
class HighlightCandidate:
    """하이라이트 후보."""

    event_id: str = ""
    event_key: str = ""
    team_id: str = ""
    highlight_type: HighlightType | None = None
    # 선수
    primary_player_id: int = 0
    related_player_ids: list[int] = field(default_factory=list)
    # 시간
    timestamp_sec: float = 0.0
    quarter: int = 1
    game_clock_sec: float = 720.0
    # 점수
    base_score: float = 0.0
    clutch_bonus: float = 0.0
    combo_bonus: float = 0.0
    player_bonus: float = 0.0
    total_score: float = 0.0
    # 점수 상황
    home_score: int = 0
    away_score: int = 0
    # 콤보 이름
    combo_name: str = ""
    # 클러치 여부
    is_clutch: bool = False


# =============================================================================
# 이벤트 키 ↔ HighlightType 매핑
# =============================================================================
_EVENT_KEY_TO_HIGHLIGHT_TYPE: Final[dict[str, HighlightType]] = {
    "dunk": HighlightType.SPECTACULAR_DUNK,
    "put_back_dunk": HighlightType.SPECTACULAR_DUNK,
    "three_pointer_made": HighlightType.THREE_POINTER,
    "deep_three": HighlightType.THREE_POINTER,
    "buzzer_beater": HighlightType.BUZZER_BEATER,
    "crossover_ankle_breaker": HighlightType.ANKLE_BREAKER,
    "chase_down_block": HighlightType.MONSTER_BLOCK,
    "weakside_block": HighlightType.MONSTER_BLOCK,
    "multiple_blocks": HighlightType.MONSTER_BLOCK,
    "fast_break_finish": HighlightType.FAST_BREAK,
    "steal_fast_break": HighlightType.FAST_BREAK,
    "alley_oop": HighlightType.ALLEY_OOP,
    "and_one": HighlightType.AND_ONE,
    "four_point_play": HighlightType.AND_ONE,
    "scoring_run": HighlightType.SCORING_RUN,
}


# =============================================================================
# 감지기
# =============================================================================
class HighlightDetector:
    """
    경기 이벤트 기반 하이라이트 후보 감지기.

    이벤트별 기본 점수 + 클러치 보너스 + 콤보 보너스 + 선수 추적 보너스를 합산하여
    threshold 이상이면 하이라이트 후보로 등록합니다.
    """

    def __init__(self, config: HighlightDetectorConfig | None = None) -> None:
        self._config = config or HighlightDetectorConfig()
        self._lock = RLock()
        self._candidates: list[HighlightCandidate] = []
        self._event_history: list[HighlightEventInput] = []
        # 추적 대상 선수 ID
        self._tracked_players: set[int] = set()
        # 최근 이벤트 시간순 (콤보 감지용)
        self._recent_events: list[HighlightEventInput] = []

    @property
    def name(self) -> str:
        return "HighlightDetector"

    # === 선수 추적 ===

    def add_tracked_player(self, player_id: int) -> None:
        """추적 대상 선수 추가."""
        with self._lock:
            self._tracked_players.add(player_id)

    def remove_tracked_player(self, player_id: int) -> None:
        """추적 대상 선수 제거."""
        with self._lock:
            self._tracked_players.discard(player_id)

    # === 이벤트 처리 ===

    def process_event(self, event: HighlightEventInput) -> HighlightCandidate | None:
        """
        이벤트를 처리하여 하이라이트 후보 여부를 판정합니다.

        Args:
            event: 하이라이트 감지용 이벤트 입력

        Returns:
            하이라이트 후보 (threshold 미달 시 None)
        """
        if event.confidence < self._config.min_confidence:
            return None

        with self._lock:
            # 히스토리 메모리 가드
            if len(self._event_history) >= _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY // 2:]
            self._event_history.append(event)

            # 최근 이벤트 관리 (콤보 감지용, 최대 20개)
            self._recent_events.append(event)
            if len(self._recent_events) > 20:
                self._recent_events = self._recent_events[-20:]

            # 1. 기본 점수
            base_score = self._get_base_score(event.event_key)
            if base_score <= 0.0:
                return None

            # 2. 클러치 보너스
            clutch_bonus = 0.0
            is_clutch = False
            if self._config.clutch_enabled:
                clutch_bonus, is_clutch = self._calc_clutch_bonus(event)

            # 3. 콤보 보너스
            combo_bonus = 0.0
            combo_name = ""
            combo_bonus, combo_name = self._calc_combo_bonus(event)

            # 4. 선수 추적 보너스
            player_bonus = 0.0
            if self._config.player_tracking_enabled:
                player_bonus = self._calc_player_bonus(event)

            # 합산
            total = base_score + clutch_bonus + combo_bonus + player_bonus

            # threshold 확인
            if total < self._config.threshold:
                return None

            # HighlightType 매핑
            hl_type = event.highlight_type
            if hl_type is None:
                hl_type = _EVENT_KEY_TO_HIGHLIGHT_TYPE.get(event.event_key)

            candidate = HighlightCandidate(
                event_id=event.event_id,
                event_key=event.event_key,
                team_id=event.team_id,
                highlight_type=hl_type,
                primary_player_id=event.primary_player_id,
                related_player_ids=list(event.related_player_ids),
                timestamp_sec=event.timestamp_sec,
                quarter=event.quarter,
                game_clock_sec=event.game_clock_sec,
                base_score=base_score,
                clutch_bonus=clutch_bonus,
                combo_bonus=combo_bonus,
                player_bonus=player_bonus,
                total_score=total,
                home_score=event.home_score,
                away_score=event.away_score,
                combo_name=combo_name,
                is_clutch=is_clutch,
            )

            # 후보 등록 (메모리 가드)
            if len(self._candidates) >= _MAX_EVENT_HISTORY:
                self._candidates = self._candidates[-_MAX_EVENT_HISTORY // 2:]
            self._candidates.append(candidate)

            return candidate

    # === 조회 ===

    def get_candidates(self, team_id: str | None = None) -> list[HighlightCandidate]:
        """하이라이트 후보 목록 반환 (점수 내림차순)."""
        with self._lock:
            if team_id is not None:
                filtered = [c for c in self._candidates if c.team_id == team_id]
            else:
                filtered = list(self._candidates)
            return sorted(filtered, key=lambda c: c.total_score, reverse=True)

    def get_top_highlights(self, n: int = 10) -> list[HighlightCandidate]:
        """상위 N개 하이라이트 반환."""
        return self.get_candidates()[:n]

    def get_clutch_highlights(self) -> list[HighlightCandidate]:
        """클러치 하이라이트만 반환."""
        with self._lock:
            return sorted(
                [c for c in self._candidates if c.is_clutch],
                key=lambda c: c.total_score,
                reverse=True,
            )

    def get_highlights_by_type(self, hl_type: HighlightType) -> list[HighlightCandidate]:
        """특정 유형의 하이라이트만 반환."""
        with self._lock:
            return sorted(
                [c for c in self._candidates if c.highlight_type == hl_type],
                key=lambda c: c.total_score,
                reverse=True,
            )

    def get_player_highlights(self, player_id: int) -> list[HighlightCandidate]:
        """특정 선수의 하이라이트만 반환."""
        with self._lock:
            return sorted(
                [c for c in self._candidates if c.primary_player_id == player_id],
                key=lambda c: c.total_score,
                reverse=True,
            )

    def get_type_distribution(self) -> dict[str, int]:
        """하이라이트 유형별 수 반환."""
        with self._lock:
            dist: dict[str, int] = {}
            for c in self._candidates:
                key = c.highlight_type.value if c.highlight_type else "unknown"
                dist[key] = dist.get(key, 0) + 1
            return dist

    def get_event_history(self) -> list[HighlightEventInput]:
        """이벤트 히스토리 반환."""
        with self._lock:
            return list(self._event_history)

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._candidates.clear()
            self._event_history.clear()
            self._recent_events.clear()

    # === 내부 메서드 ===

    def _get_base_score(self, event_key: str) -> float:
        """이벤트 키에 대한 기본 점수 반환."""
        return self._config.event_scores.get(event_key, 0.0)

    def _calc_clutch_bonus(
        self, event: HighlightEventInput,
    ) -> tuple[float, bool]:
        """
        클러치 보너스 계산.

        점수차 ≤ margin_points 이고 남은 시간 ≤ time_remaining_sec 이면 보너스.
        """
        margin = abs(event.home_score - event.away_score)
        # 쿼터 4 남은 시간 기준으로 계산
        remaining = self._estimate_remaining_sec(event.quarter, event.game_clock_sec)
        if (
            margin <= self._config.clutch_margin_points
            and remaining <= self._config.clutch_time_remaining_sec
        ):
            return self._config.clutch_bonus_score, True
        return 0.0, False

    def _calc_combo_bonus(
        self, event: HighlightEventInput,
    ) -> tuple[float, str]:
        """콤보 이벤트 보너스 계산."""
        best_bonus = 0.0
        best_name = ""
        for rule in self._config.combo_rules:
            if not rule.events:
                continue
            # 현재 이벤트가 콤보의 마지막 이벤트인지 확인
            if event.event_key not in rule.events:
                continue
            # 최근 이벤트에서 콤보 매칭
            if self._match_combo(rule, event):
                if rule.bonus_score > best_bonus:
                    best_bonus = rule.bonus_score
                    best_name = rule.name
        return best_bonus, best_name

    def _match_combo(self, rule: ComboRule, current: HighlightEventInput) -> bool:
        """콤보 규칙에 맞는 이벤트 시퀀스가 있는지 확인."""
        needed = list(rule.events)
        # 현재 이벤트 제외하고 최근 이벤트를 역순으로 확인
        matched: list[HighlightEventInput] = [current]
        remaining = [e for e in needed if e != current.event_key]

        # 시퀀스에 current 이벤트가 없으면 실패
        if current.event_key not in needed:
            return False

        for ev in reversed(self._recent_events[:-1]):
            if not remaining:
                break
            time_gap = current.timestamp_sec - ev.timestamp_sec
            if time_gap > rule.max_gap_sec:
                break
            if ev.event_key in remaining:
                remaining.remove(ev.event_key)
                matched.append(ev)

        return len(remaining) == 0

    def _calc_player_bonus(self, event: HighlightEventInput) -> float:
        """선수 추적 보너스."""
        if event.primary_player_id in self._tracked_players:
            return self._config.player_tracking_bonus
        return 0.0

    @staticmethod
    def _estimate_remaining_sec(quarter: int, game_clock_sec: float) -> float:
        """
        경기 남은 시간 추정 (초).

        Args:
            quarter: 현재 쿼터 (1~4)
            game_clock_sec: 현재 쿼터 남은 시간 (초)

        Returns:
            경기 전체 남은 시간 (초)
        """
        # FIBA 기준 10분 쿼터
        remaining_quarters = max(0, 4 - quarter)
        return remaining_quarters * 600.0 + game_clock_sec


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "HighlightDetectorConfig",
    "HighlightDetector",
    "HighlightEventInput",
    "HighlightCandidate",
    "ComboRule",
]

__version__ = "1.0.0"
