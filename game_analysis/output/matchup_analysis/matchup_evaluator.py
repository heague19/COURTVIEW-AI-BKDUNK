# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/matchup_analysis
파일: matchup_evaluator.py
설명: 매치업 평가기
      - 수비자 매치업 효율 종합 등급 산출
      - 포지션별 수비 효율 분석
      - 매치업 어드밴티지/디스어드밴티지 판별
      - 최적 매치업 추천

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/tactical_dto.py (MatchupData)
의존성: shared/dto/tactical_dto.py
소비자: coaching_intelligence, defensive_analysis, pre_game
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.dto.tactical_dto import MatchupData

logger: Final = logging.getLogger(__name__)

# 리그 평균 기준
_LEAGUE_AVG_FG_PCT: Final[float] = 0.46
_LEAGUE_AVG_PPP: Final[float] = 1.08  # Points Per Possession


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class MatchupEvaluatorConfig:
    """매치업 평가기 설정."""

    # 리그 평균 기준
    league_avg_fg_pct: float = _LEAGUE_AVG_FG_PCT
    league_avg_ppp: float = _LEAGUE_AVG_PPP
    # 어드밴티지 판단 임계
    advantage_fg_pct_diff: float = 0.05  # FG% 5% 이상 차이 → 어드밴티지
    # 최소 점유 수
    min_possessions: int = 5

    @classmethod
    def from_yaml(cls, cfg: dict) -> MatchupEvaluatorConfig:
        """YAML 설정에서 생성."""
        return cls(
            league_avg_fg_pct=cfg.get("league_avg_fg_pct", _LEAGUE_AVG_FG_PCT),
            league_avg_ppp=cfg.get("league_avg_ppp", _LEAGUE_AVG_PPP),
            advantage_fg_pct_diff=cfg.get("advantage_fg_pct_diff", 0.05),
            min_possessions=cfg.get("min_possessions", 5),
        )


# =============================================================================
# 출력
# =============================================================================
@dataclass(slots=True)
class MatchupEvaluation:
    """매치업 평가 결과."""

    defender_tracking_id: int = 0
    offensive_tracking_id: int = 0
    possessions: int = 0
    # 성과 지표
    points_allowed: int = 0
    ppp: float = 0.0  # Points Per Possession
    fg_pct: float = 0.0
    contest_rate: float = 0.0
    # 평가
    grade: float = 0.0  # 0~100 (100이 최고 수비)
    advantage: str = ""  # "defender" / "offensive" / "neutral"
    # 한글 평가 설명
    evaluation_ko: str = ""


@dataclass(slots=True)
class PositionMatchupSummary:
    """포지션별 매치업 요약."""

    position: str = ""  # PG, SG, SF, PF, C
    avg_fg_pct_allowed: float = 0.0
    avg_ppp: float = 0.0
    total_possessions: int = 0
    avg_grade: float = 0.0


@dataclass(slots=True)
class MatchupRecommendation:
    """최적 매치업 추천."""

    offensive_tracking_id: int = 0
    recommended_defender_id: int = 0
    defender_grade: float = 0.0
    reason_ko: str = ""


# =============================================================================
# 평가기
# =============================================================================
class MatchupEvaluator:
    """
    매치업 평가기.

    수비자별 매치업 효율을 평가하고, 어드밴티지/디스어드밴티지를 판별하며,
    포지션별 분석 및 최적 매치업을 추천합니다.
    """

    def __init__(self, config: MatchupEvaluatorConfig | None = None) -> None:
        self._config = config or MatchupEvaluatorConfig()
        self._lock = RLock()
        # 매치업 데이터 (외부 주입)
        self._matchup_data: list[MatchupData] = []
        # 선수 포지션 매핑
        self._positions: dict[int, str] = {}  # tracking_id → position
        self._event_history: list[str] = []

    @property
    def name(self) -> str:
        return "MatchupEvaluator"

    # === 데이터 입력 ===

    def set_matchup_data(self, data: list[MatchupData]) -> None:
        """매치업 데이터 설정 (MatchupTracker 출력)."""
        with self._lock:
            self._matchup_data = list(data)
            self._event_history.append("matchup_data_set")

    def set_player_positions(self, positions: dict[int, str]) -> None:
        """선수 포지션 매핑 설정."""
        with self._lock:
            self._positions = dict(positions)

    # === 평가 ===

    def evaluate_matchup(self, matchup: MatchupData) -> MatchupEvaluation:
        """
        단일 매치업 평가.

        Args:
            matchup: MatchupData DTO

        Returns:
            MatchupEvaluation 결과
        """
        cfg = self._config
        poss = matchup.possessions
        if poss == 0:
            return MatchupEvaluation(
                defender_tracking_id=matchup.defender_tracking_id,
                offensive_tracking_id=matchup.offensive_tracking_id,
            )

        ppp = matchup.points_allowed / poss

        # 등급 계산 (3요소 가중)
        # 1) PPP 억제 (40%): 리그 평균 대비
        ppp_score = max(
            0.0,
            min(100.0, (cfg.league_avg_ppp - ppp) / 0.50 * 50.0 + 50.0),
        )
        # 2) FG% 억제 (40%): 리그 평균 대비
        fg_score = max(
            0.0,
            min(
                100.0,
                (cfg.league_avg_fg_pct - matchup.fg_pct) / 0.20 * 50.0 + 50.0,
            ),
        )
        # 3) 컨테스트율 (20%): 높을수록 좋음
        contest_score = min(matchup.contest_rate / 0.80, 1.0) * 100.0

        grade = ppp_score * 0.40 + fg_score * 0.40 + contest_score * 0.20

        # 어드밴티지 판단
        fg_diff = matchup.fg_pct - cfg.league_avg_fg_pct
        if fg_diff <= -cfg.advantage_fg_pct_diff:
            advantage = "defender"
        elif fg_diff >= cfg.advantage_fg_pct_diff:
            advantage = "offensive"
        else:
            advantage = "neutral"

        # 한글 평가
        evaluation_ko = self._generate_evaluation_ko(
            grade, advantage, ppp, matchup.fg_pct, matchup.contest_rate
        )

        return MatchupEvaluation(
            defender_tracking_id=matchup.defender_tracking_id,
            offensive_tracking_id=matchup.offensive_tracking_id,
            possessions=poss,
            points_allowed=matchup.points_allowed,
            ppp=round(ppp, 3),
            fg_pct=matchup.fg_pct,
            contest_rate=matchup.contest_rate,
            grade=round(grade, 1),
            advantage=advantage,
            evaluation_ko=evaluation_ko,
        )

    def evaluate_all(self) -> list[MatchupEvaluation]:
        """전체 매치업 평가."""
        with self._lock:
            results: list[MatchupEvaluation] = []
            for m in self._matchup_data:
                if m.possessions >= self._config.min_possessions:
                    results.append(self.evaluate_matchup(m))
            results.sort(key=lambda e: e.grade, reverse=True)
            return results

    def get_position_summary(self) -> list[PositionMatchupSummary]:
        """포지션별 매치업 요약."""
        with self._lock:
            # 공격자 포지션별 그룹핑
            pos_data: dict[str, list[MatchupData]] = {}
            for m in self._matchup_data:
                if m.possessions < self._config.min_possessions:
                    continue
                pos = self._positions.get(m.offensive_tracking_id, "")
                if not pos:
                    continue
                if pos not in pos_data:
                    pos_data[pos] = []
                pos_data[pos].append(m)

            results: list[PositionMatchupSummary] = []
            for pos, matchups in pos_data.items():
                total_poss = sum(m.possessions for m in matchups)
                total_pts = sum(m.points_allowed for m in matchups)
                avg_ppp = total_pts / total_poss if total_poss > 0 else 0.0

                total_fg_att = sum(m.fg_attempts for m in matchups)
                total_fg_made = sum(m.fg_made for m in matchups)
                avg_fg = (
                    total_fg_made / total_fg_att if total_fg_att > 0 else 0.0
                )

                # 평균 등급
                evals = [self.evaluate_matchup(m) for m in matchups]
                avg_grade = (
                    sum(e.grade for e in evals) / len(evals)
                    if evals
                    else 0.0
                )

                results.append(
                    PositionMatchupSummary(
                        position=pos,
                        avg_fg_pct_allowed=round(avg_fg, 3),
                        avg_ppp=round(avg_ppp, 3),
                        total_possessions=total_poss,
                        avg_grade=round(avg_grade, 1),
                    )
                )

            results.sort(key=lambda r: r.avg_grade, reverse=True)
            return results

    def recommend_matchups(
        self, offensive_ids: list[int]
    ) -> list[MatchupRecommendation]:
        """
        공격자별 최적 수비 매치업 추천.

        Args:
            offensive_ids: 추천 대상 공격자 ID 목록

        Returns:
            공격자별 최적 수비자 추천
        """
        with self._lock:
            recommendations: list[MatchupRecommendation] = []

            for off_id in offensive_ids:
                # 해당 공격자를 상대한 모든 수비자의 매치업
                candidate_matchups = [
                    m
                    for m in self._matchup_data
                    if m.offensive_tracking_id == off_id
                    and m.possessions >= self._config.min_possessions
                ]

                if not candidate_matchups:
                    continue

                # 가장 높은 등급의 수비자 추천
                best_eval: MatchupEvaluation | None = None
                for m in candidate_matchups:
                    ev = self.evaluate_matchup(m)
                    if best_eval is None or ev.grade > best_eval.grade:
                        best_eval = ev

                if best_eval is not None:
                    reason = (
                        f"허용 FG% {best_eval.fg_pct:.1%}, "
                        f"PPP {best_eval.ppp:.2f}, "
                        f"등급 {best_eval.grade:.0f}"
                    )
                    recommendations.append(
                        MatchupRecommendation(
                            offensive_tracking_id=off_id,
                            recommended_defender_id=best_eval.defender_tracking_id,
                            defender_grade=best_eval.grade,
                            reason_ko=reason,
                        )
                    )

            recommendations.sort(key=lambda r: r.defender_grade, reverse=True)
            return recommendations

    # === 내부 메서드 ===

    @staticmethod
    def _generate_evaluation_ko(
        grade: float,
        advantage: str,
        ppp: float,
        fg_pct: float,
        contest_rate: float,
    ) -> str:
        """한글 평가 설명 생성."""
        parts: list[str] = []

        if grade >= 80:
            parts.append("우수한 수비 매치업")
        elif grade >= 60:
            parts.append("양호한 수비 매치업")
        elif grade >= 40:
            parts.append("보통 수비 매치업")
        else:
            parts.append("약한 수비 매치업")

        adv_map = {
            "defender": " (수비자 유리)",
            "offensive": " (공격자 유리)",
            "neutral": " (중립)",
        }
        parts.append(adv_map.get(advantage, ""))
        parts.append(f" — PPP {ppp:.2f}, FG% {fg_pct:.1%}, 컨테스트율 {contest_rate:.1%}")
        return "".join(parts)

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._matchup_data.clear()
            self._positions.clear()
            self._event_history.clear()

    def get_event_history(self) -> list[str]:
        """이벤트 이력."""
        with self._lock:
            return list(self._event_history)


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "MatchupEvaluatorConfig",
    "MatchupEvaluator",
    "MatchupEvaluation",
    "PositionMatchupSummary",
    "MatchupRecommendation",
]

__version__ = "1.0.0"
