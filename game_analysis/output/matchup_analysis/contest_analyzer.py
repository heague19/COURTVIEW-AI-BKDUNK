# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/matchup_analysis
파일: contest_analyzer.py
설명: 슛 컨테스트 분석기
      - 컨테스트 거리별 효과 분석
      - 수비자별 컨테스트 성과 (FG% 억제)
      - 컨테스트 유형 분류 (tight/moderate/open)
      - 컨테스트 등급 산출 (0~100)

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/constants/tactical_constants.py
의존성: shared/constants/tactical_constants.py
소비자: matchup_evaluator, defensive_analysis, coaching_intelligence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

logger: Final = logging.getLogger(__name__)

_MAX_CONTEST_RECORDS: Final[int] = 2000

# 컨테스트 거리 임계 (미터)
_TIGHT_CONTEST_DIST: Final[float] = 0.9  # 0.9m 이하 → 밀착 컨테스트
_MODERATE_CONTEST_DIST: Final[float] = 1.8  # 1.8m 이하 → 보통 컨테스트
# 1.8m 초과 → 오픈 슛


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ContestAnalyzerConfig:
    """컨테스트 분석기 설정."""

    max_records: int = _MAX_CONTEST_RECORDS
    tight_distance_m: float = _TIGHT_CONTEST_DIST
    moderate_distance_m: float = _MODERATE_CONTEST_DIST
    # 최소 샘플 수 (유의미한 분석)
    min_contests_for_report: int = 3

    @classmethod
    def from_yaml(cls, cfg: dict) -> ContestAnalyzerConfig:
        """YAML 설정에서 생성."""
        return cls(
            max_records=cfg.get("max_records", _MAX_CONTEST_RECORDS),
            tight_distance_m=cfg.get("tight_distance_m", _TIGHT_CONTEST_DIST),
            moderate_distance_m=cfg.get(
                "moderate_distance_m", _MODERATE_CONTEST_DIST
            ),
            min_contests_for_report=cfg.get("min_contests_for_report", 3),
        )


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class ContestEventInput:
    """컨테스트 이벤트 입력."""

    defender_tracking_id: int = 0
    shooter_tracking_id: int = 0
    contest_distance_m: float = 0.0  # 수비자-슈터 거리 (미터)
    shot_made: bool = False  # 슛 성공 여부
    shot_points: int = 2  # 슛 배점 (2 or 3)


# =============================================================================
# 출력
# =============================================================================
@dataclass(slots=True)
class ContestResult:
    """수비자별 컨테스트 분석 결과."""

    defender_tracking_id: int = 0
    total_contests: int = 0
    # 거리별 분류
    tight_contests: int = 0
    moderate_contests: int = 0
    open_allowed: int = 0  # 오픈 허용 횟수
    # 효과
    fg_pct_when_tight: float = 0.0
    fg_pct_when_moderate: float = 0.0
    fg_pct_when_open: float = 0.0
    # 전체 FG% 억제
    overall_opponent_fg_pct: float = 0.0
    # 등급 (0~100, 100이 최고)
    contest_grade: float = 0.0


@dataclass(slots=True)
class ContestSummary:
    """팀 전체 컨테스트 요약."""

    total_shots_faced: int = 0
    contested_rate: float = 0.0  # 컨테스트 비율
    tight_rate: float = 0.0  # 밀착 컨테스트 비율
    avg_contest_distance_m: float = 0.0
    opponent_fg_pct_contested: float = 0.0  # 컨테스트 시 상대 FG%
    opponent_fg_pct_open: float = 0.0  # 오픈 시 상대 FG%


# =============================================================================
# 내부 축적 구조
# =============================================================================
@dataclass(slots=True)
class _ContestAccum:
    """수비자별 컨테스트 축적 데이터."""

    tight_attempts: int = 0
    tight_made: int = 0
    moderate_attempts: int = 0
    moderate_made: int = 0
    open_attempts: int = 0
    open_made: int = 0


# =============================================================================
# 분석기
# =============================================================================
class ContestAnalyzer:
    """
    슛 컨테스트 분석기.

    수비자별 컨테스트 거리, FG% 억제, 등급을 분석합니다.
    """

    def __init__(self, config: ContestAnalyzerConfig | None = None) -> None:
        self._config = config or ContestAnalyzerConfig()
        self._lock = RLock()
        # defender_id → 축적 데이터
        self._defenders: dict[int, _ContestAccum] = {}
        # 전체 거리 기록 (평균 계산용)
        self._all_distances: list[float] = []
        self._record_count: int = 0

    @property
    def name(self) -> str:
        return "ContestAnalyzer"

    # === 이벤트 입력 ===

    def record_contest(self, event: ContestEventInput) -> None:
        """
        컨테스트 이벤트 기록.

        Args:
            event: 컨테스트 이벤트 입력
        """
        with self._lock:
            # 메모리 가드: 리스트 트림 후 카운터 동기화 (미동기화 시 매 레코드 트림 반복)
            if self._record_count >= self._config.max_records:
                half = self._config.max_records // 2
                self._all_distances = self._all_distances[-half:]
                self._record_count = half

            d_id = event.defender_tracking_id
            if d_id not in self._defenders:
                self._defenders[d_id] = _ContestAccum()

            accum = self._defenders[d_id]
            dist = event.contest_distance_m
            made = event.shot_made

            if dist <= self._config.tight_distance_m:
                accum.tight_attempts += 1
                if made:
                    accum.tight_made += 1
            elif dist <= self._config.moderate_distance_m:
                accum.moderate_attempts += 1
                if made:
                    accum.moderate_made += 1
            else:
                accum.open_attempts += 1
                if made:
                    accum.open_made += 1

            self._all_distances.append(dist)
            self._record_count += 1

    # === 분석 ===

    def get_defender_result(self, defender_id: int) -> ContestResult | None:
        """수비자별 컨테스트 분석 결과."""
        with self._lock:
            accum = self._defenders.get(defender_id)
            if accum is None:
                return None
            total = (
                accum.tight_attempts + accum.moderate_attempts + accum.open_attempts
            )
            if total < self._config.min_contests_for_report:
                return None
            return self._to_result(defender_id, accum)

    def get_all_defender_results(self) -> list[ContestResult]:
        """전체 수비자 컨테스트 결과."""
        with self._lock:
            results: list[ContestResult] = []
            min_ct = self._config.min_contests_for_report
            for d_id, accum in self._defenders.items():
                total = (
                    accum.tight_attempts
                    + accum.moderate_attempts
                    + accum.open_attempts
                )
                if total >= min_ct:
                    results.append(self._to_result(d_id, accum))
            results.sort(key=lambda r: r.contest_grade, reverse=True)
            return results

    def get_summary(self) -> ContestSummary:
        """팀 전체 컨테스트 요약."""
        with self._lock:
            total_shots = 0
            contested_shots = 0
            tight_shots = 0
            contested_made = 0
            open_made = 0
            open_shots = 0

            for accum in self._defenders.values():
                tight = accum.tight_attempts
                moderate = accum.moderate_attempts
                opn = accum.open_attempts

                total_shots += tight + moderate + opn
                contested_shots += tight + moderate
                tight_shots += tight
                contested_made += accum.tight_made + accum.moderate_made
                open_made += accum.open_made
                open_shots += opn

            if total_shots == 0:
                return ContestSummary()

            avg_dist = (
                sum(self._all_distances) / len(self._all_distances)
                if self._all_distances
                else 0.0
            )

            return ContestSummary(
                total_shots_faced=total_shots,
                contested_rate=round(contested_shots / total_shots, 3),
                tight_rate=round(
                    tight_shots / total_shots if total_shots > 0 else 0.0, 3
                ),
                avg_contest_distance_m=round(avg_dist, 2),
                opponent_fg_pct_contested=round(
                    contested_made / contested_shots
                    if contested_shots > 0
                    else 0.0,
                    3,
                ),
                opponent_fg_pct_open=round(
                    open_made / open_shots if open_shots > 0 else 0.0, 3
                ),
            )

    # === 내부 메서드 ===

    def _to_result(self, defender_id: int, accum: _ContestAccum) -> ContestResult:
        """축적 데이터 → ContestResult 변환."""
        tight_pct = (
            accum.tight_made / accum.tight_attempts
            if accum.tight_attempts > 0
            else 0.0
        )
        mod_pct = (
            accum.moderate_made / accum.moderate_attempts
            if accum.moderate_attempts > 0
            else 0.0
        )
        open_pct = (
            accum.open_made / accum.open_attempts
            if accum.open_attempts > 0
            else 0.0
        )

        total = (
            accum.tight_attempts + accum.moderate_attempts + accum.open_attempts
        )
        total_made = accum.tight_made + accum.moderate_made + accum.open_made
        overall_pct = total_made / total if total > 0 else 0.0

        # 등급 계산:
        #   - 컨테스트 비율 (밀착+보통) / 전체 → 40%
        #   - 상대 FG% 억제 (리그 평균 46% 대비) → 40%
        #   - 밀착 비율 → 20%
        contested = accum.tight_attempts + accum.moderate_attempts
        contest_rate = contested / total if total > 0 else 0.0
        tight_rate = accum.tight_attempts / total if total > 0 else 0.0

        # 컨테스트 비율 점수 (0~100)
        contest_score = min(contest_rate / 0.80, 1.0) * 100.0
        # FG% 억제 점수 (낮을수록 좋음, 46%=평균)
        suppression_score = max(0.0, min(100.0, (0.46 - overall_pct) / 0.20 * 100.0))
        # 밀착 비율 점수
        tight_score = min(tight_rate / 0.40, 1.0) * 100.0

        grade = contest_score * 0.40 + suppression_score * 0.40 + tight_score * 0.20

        return ContestResult(
            defender_tracking_id=defender_id,
            total_contests=total,
            tight_contests=accum.tight_attempts,
            moderate_contests=accum.moderate_attempts,
            open_allowed=accum.open_attempts,
            fg_pct_when_tight=round(tight_pct, 3),
            fg_pct_when_moderate=round(mod_pct, 3),
            fg_pct_when_open=round(open_pct, 3),
            overall_opponent_fg_pct=round(overall_pct, 3),
            contest_grade=round(grade, 1),
        )

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._defenders.clear()
            self._all_distances.clear()
            self._record_count = 0

    def get_event_history(self) -> list[ContestResult]:
        """전체 수비자 결과 이력."""
        return self.get_all_defender_results()


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "ContestAnalyzerConfig",
    "ContestAnalyzer",
    "ContestEventInput",
    "ContestResult",
    "ContestSummary",
]

__version__ = "1.0.0"
