# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/highlight
파일: excitement_scorer.py
설명: 하이라이트 흥미도/중요도 점수 산출기
      - HighlightCandidate → 최종 excitement + importance 점수
      - 게임 컨텍스트 보정 (접전/대역전/연장전 등)
      - 쿼터별 가중치 (후반 쿼터 > 전반 쿼터)
      - 희소 이벤트 가산 (게임 내 첫 발생 보너스)
      - 경기 흐름 기반 모멘텀 보정 (스코어링 런)

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/highlight.yaml
의존성: shared/constants/game_rule_constants.py
소비자: clip_extractor, game_report_builder
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import HighlightType

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ExcitementScorerConfig:
    """흥미도 점수 산출기 설정."""

    # 쿼터별 가중치 (1Q~4Q, 후반 가중)
    quarter_weights: dict[int, float] = field(default_factory=lambda: {
        1: 0.90, 2: 0.95, 3: 1.00, 4: 1.15,
    })
    # 희소 이벤트 보너스 (게임 내 첫 발생 시)
    rarity_bonus: float = 10.0
    # 접전 가산 (점수차 ≤ 3점)
    tight_game_margin: int = 3
    tight_game_bonus: float = 8.0
    # 대역전 보너스 (10점 이상 뒤집기)
    comeback_threshold_points: int = 10
    comeback_bonus: float = 15.0
    # 모멘텀 보정 (연속 득점/득점 런)
    momentum_run_threshold: int = 3  # 연속 N번 득점
    momentum_bonus: float = 10.0
    # 중요도 가중치 (importance 산출)
    importance_clutch_weight: float = 0.40
    importance_margin_weight: float = 0.30
    importance_quarter_weight: float = 0.30

    @classmethod
    def from_yaml(cls, cfg: dict) -> ExcitementScorerConfig:
        """YAML 설정에서 생성."""
        det = cfg.get("detection", {})
        clutch = det.get("clutch_bonus", {})
        return cls(
            tight_game_margin=clutch.get("margin_points", 3),
            tight_game_bonus=8.0,
        )


# =============================================================================
# 입력/출력
# =============================================================================
@dataclass(slots=True)
class ScoringInput:
    """흥미도 점수 산출 입력."""

    # 하이라이트 후보 정보
    event_id: str = ""
    event_key: str = ""
    team_id: str = ""
    highlight_type: HighlightType | None = None
    # 기본 점수 (HighlightDetector에서 산출)
    base_total_score: float = 0.0
    # 시간/컨텍스트
    timestamp_sec: float = 0.0
    quarter: int = 1
    game_clock_sec: float = 720.0
    # 점수 상황
    home_score: int = 0
    away_score: int = 0
    is_home_team: bool = True
    points_scored: int = 0
    # 클러치 여부
    is_clutch: bool = False
    # 신뢰도
    confidence: float = 0.85


@dataclass(slots=True)
class ScoredHighlight:
    """최종 점수가 부여된 하이라이트."""

    event_id: str = ""
    event_key: str = ""
    team_id: str = ""
    highlight_type: HighlightType | None = None
    # 최종 점수
    excitement_score: float = 0.0  # 0~100
    importance_score: float = 0.0  # 0~100
    # 구성 요소
    base_score: float = 0.0
    quarter_factor: float = 1.0
    rarity_bonus: float = 0.0
    tight_game_bonus: float = 0.0
    comeback_bonus: float = 0.0
    momentum_bonus: float = 0.0
    # 시간/컨텍스트
    timestamp_sec: float = 0.0
    quarter: int = 1
    is_clutch: bool = False
    # 점수 상황
    home_score: int = 0
    away_score: int = 0


# =============================================================================
# 점수 산출기
# =============================================================================
class ExcitementScorer:
    """
    하이라이트 흥미도/중요도 점수 산출기.

    base_total_score에 게임 컨텍스트 보정을 적용하여
    excitement_score (0~100)과 importance_score (0~100)을 산출합니다.
    """

    def __init__(self, config: ExcitementScorerConfig | None = None) -> None:
        self._config = config or ExcitementScorerConfig()
        self._lock = RLock()
        self._scored: list[ScoredHighlight] = []
        self._event_history: list[ScoringInput] = []
        # 희소성 추적 (유형별 발생 수)
        self._type_counts: dict[str, int] = {}
        # 모멘텀 추적 (팀별 최근 연속 득점 수)
        self._team_scoring_streak: dict[str, int] = {}
        # 역대 최대 리드 추적 (역전 감지)
        self._max_lead: dict[str, int] = {"home": 0, "away": 0}

    @property
    def name(self) -> str:
        return "ExcitementScorer"

    # === 점수 산출 ===

    def score_highlight(self, inp: ScoringInput) -> ScoredHighlight | None:
        """
        하이라이트 흥미도/중요도 점수를 산출합니다.

        Args:
            inp: 점수 산출 입력

        Returns:
            점수가 부여된 하이라이트 (None = 유효하지 않은 입력)
        """
        if inp.confidence < 0.40:
            return None

        with self._lock:
            # 히스토리 메모리 가드
            if len(self._event_history) >= _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY // 2:]
            self._event_history.append(inp)

            # 1. 쿼터 가중치
            q_factor = self._config.quarter_weights.get(inp.quarter, 1.0)

            # 2. 희소 이벤트 보너스
            rarity = self._calc_rarity_bonus(inp)

            # 3. 접전 보너스
            tight = self._calc_tight_game_bonus(inp)

            # 4. 역전 보너스
            comeback = self._calc_comeback_bonus(inp)

            # 5. 모멘텀 보너스
            momentum = self._calc_momentum_bonus(inp)

            # 상태 업데이트
            self._update_tracking(inp)

            # excitement = base * quarter_factor + 보너스들 (0~100 클램프)
            excitement = inp.base_total_score * q_factor + rarity + tight + comeback + momentum
            excitement = max(0.0, min(100.0, excitement))

            # importance 별도 산출
            importance = self._calc_importance(inp, excitement)

            result = ScoredHighlight(
                event_id=inp.event_id,
                event_key=inp.event_key,
                team_id=inp.team_id,
                highlight_type=inp.highlight_type,
                excitement_score=round(excitement, 1),
                importance_score=round(importance, 1),
                base_score=inp.base_total_score,
                quarter_factor=q_factor,
                rarity_bonus=rarity,
                tight_game_bonus=tight,
                comeback_bonus=comeback,
                momentum_bonus=momentum,
                timestamp_sec=inp.timestamp_sec,
                quarter=inp.quarter,
                is_clutch=inp.is_clutch,
                home_score=inp.home_score,
                away_score=inp.away_score,
            )

            # 결과 저장 (메모리 가드)
            if len(self._scored) >= _MAX_EVENT_HISTORY:
                self._scored = self._scored[-_MAX_EVENT_HISTORY // 2:]
            self._scored.append(result)

            return result

    # === 조회 ===

    def get_scored_highlights(self, min_excitement: float = 0.0) -> list[ScoredHighlight]:
        """점수가 부여된 하이라이트 목록 (excitement 내림차순)."""
        with self._lock:
            filtered = [s for s in self._scored if s.excitement_score >= min_excitement]
            return sorted(filtered, key=lambda s: s.excitement_score, reverse=True)

    def get_most_important(self, n: int = 10) -> list[ScoredHighlight]:
        """중요도 상위 N개 하이라이트."""
        with self._lock:
            return sorted(self._scored, key=lambda s: s.importance_score, reverse=True)[:n]

    def get_average_excitement(self) -> float:
        """평균 흥미도."""
        with self._lock:
            if not self._scored:
                return 0.0
            return round(sum(s.excitement_score for s in self._scored) / len(self._scored), 1)

    def get_event_history(self) -> list[ScoringInput]:
        """이벤트 히스토리."""
        with self._lock:
            return list(self._event_history)

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._scored.clear()
            self._event_history.clear()
            self._type_counts.clear()
            self._team_scoring_streak.clear()
            self._max_lead = {"home": 0, "away": 0}

    # === 내부 메서드 ===

    def _calc_rarity_bonus(self, inp: ScoringInput) -> float:
        """희소 이벤트 보너스 (게임 내 첫 발생)."""
        key = inp.event_key
        count = self._type_counts.get(key, 0)
        if count == 0:
            return self._config.rarity_bonus
        return 0.0

    def _calc_tight_game_bonus(self, inp: ScoringInput) -> float:
        """접전 보너스."""
        margin = abs(inp.home_score - inp.away_score)
        if margin <= self._config.tight_game_margin:
            return self._config.tight_game_bonus
        return 0.0

    def _calc_comeback_bonus(self, inp: ScoringInput) -> float:
        """역전 보너스 (이전 최대 리드 대비)."""
        current_lead = inp.home_score - inp.away_score
        # 홈팀이 behind → 득점 → 역전 시
        if inp.is_home_team and inp.points_scored > 0:
            prev_max_deficit = self._max_lead.get("away", 0)
            if prev_max_deficit >= self._config.comeback_threshold_points and current_lead >= 0:
                return self._config.comeback_bonus
        # 어웨이팀 역전
        if not inp.is_home_team and inp.points_scored > 0:
            prev_max_deficit = self._max_lead.get("home", 0)
            if prev_max_deficit >= self._config.comeback_threshold_points and current_lead <= 0:
                return self._config.comeback_bonus
        return 0.0

    def _calc_momentum_bonus(self, inp: ScoringInput) -> float:
        """모멘텀 보너스 (연속 득점 런)."""
        if inp.points_scored <= 0:
            return 0.0
        streak = self._team_scoring_streak.get(inp.team_id, 0)
        if streak >= self._config.momentum_run_threshold:
            return self._config.momentum_bonus
        return 0.0

    def _update_tracking(self, inp: ScoringInput) -> None:
        """내부 추적 상태 업데이트."""
        # 유형별 카운트
        key = inp.event_key
        self._type_counts[key] = self._type_counts.get(key, 0) + 1

        # 모멘텀: 득점 시 해당 팀 스트릭 증가, 상대팀 리셋
        if inp.points_scored > 0:
            self._team_scoring_streak[inp.team_id] = (
                self._team_scoring_streak.get(inp.team_id, 0) + 1
            )
            # 상대팀 스트릭 리셋
            for t in list(self._team_scoring_streak.keys()):
                if t != inp.team_id:
                    self._team_scoring_streak[t] = 0

        # 최대 리드 업데이트
        lead = inp.home_score - inp.away_score
        if lead > 0:
            self._max_lead["home"] = max(self._max_lead.get("home", 0), lead)
        elif lead < 0:
            self._max_lead["away"] = max(self._max_lead.get("away", 0), abs(lead))

    def _calc_importance(self, inp: ScoringInput, excitement: float) -> float:
        """
        중요도 점수 산출 (0~100).

        importance = clutch_factor * w1 + margin_factor * w2 + quarter_factor * w3
        """
        cfg = self._config
        # 클러치: 1.0 or 0.0
        clutch_factor = 100.0 if inp.is_clutch else 0.0

        # 점수차 기반 (0점차=100, 20점차 이상=0)
        margin = abs(inp.home_score - inp.away_score)
        margin_factor = max(0.0, 100.0 - margin * 5.0)

        # 쿼터 기반 (4Q=100, 1Q=50)
        quarter_factor = min(100.0, 50.0 + (inp.quarter - 1) * 16.7)

        importance = (
            clutch_factor * cfg.importance_clutch_weight
            + margin_factor * cfg.importance_margin_weight
            + quarter_factor * cfg.importance_quarter_weight
        )
        return max(0.0, min(100.0, importance))


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "ExcitementScorerConfig",
    "ExcitementScorer",
    "ScoringInput",
    "ScoredHighlight",
]

__version__ = "1.0.0"
