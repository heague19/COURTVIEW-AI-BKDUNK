# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/decisions
파일: consistency_tracker.py
설명: 경기 내 판정 일관성 추적기
      - 판정 이력 기록 (유형별, 팀별)
      - 유사 상황 비교 (접촉 강도 빈 기반)
      - 팀 간 편향 감지
      - 콜 레벨 캘리브레이션 (tight/loose)
      - 일관성 이탈 경고

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0

참조:
    - shared/constants/referee_decision_constants.py (CONSISTENCY_*)
    - ai_referee/rules/base_rule.py (RuleResult, RuleCategory)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.referee_decision_constants import (
    CALL_LEVEL_CALIBRATION_EVENTS,
    CONSISTENCY_COMPARISON_WINDOW,
    CONSISTENCY_DEVIATION_THRESHOLD,
    SEVERITY_BIN_WIDTH,
)
from shared.constants.referee_rule_constants import CallType, RuleSet

from ai_referee.rules.base_rule import RuleCategory, RuleResult

logger: Final = logging.getLogger(__name__)

_MAX_DECISION_HISTORY: Final[int] = 1000


@dataclass(slots=True)
class ConsistencyReport:
    """
    판정 일관성 보고서.

    현재 판정이 과거 유사 판정 대비 일관적인지 분석합니다.
    """

    is_consistent: bool = True
    consistency_score: float = 1.0    # 0.0~1.0 (1.0 = 완전 일관)
    bias_warnings: list[str] = field(default_factory=list)
    similar_count: int = 0            # 유사 이벤트 수
    similar_call_rate: float = 0.0    # 유사 이벤트에서 콜 비율
    call_level: str = "normal"        # tight / normal / loose


@dataclass(slots=True)
class _DecisionRecord:
    """판정 기록 (내부용)."""

    result: RuleResult
    team_id: str | None = None
    severity_bin: int = 0             # 접촉 강도 빈 인덱스


class ConsistencyTracker:
    """
    경기 내 판정 일관성 추적기.

    모든 판정을 기록하고, 새로운 판정이 기존 판정과 일관적인지 검증합니다.

    일관성 판단 기준:
      1. 유사 이벤트 비교: 동일 CallType + 유사 신뢰도 범위에서 콜/노콜 비율
      2. 팀 간 편향: 한쪽 팀에 편중된 콜 감지
      3. 콜 레벨: tight(소소한 접촉도 콜) / normal / loose(강한 접촉만 콜)

    사용 예시::

        tracker = ConsistencyTracker(rule_set=RuleSet.FIBA)
        report = tracker.check_consistency(rule_result, team_id="team_a")
        if not report.is_consistent:
            # 일관성 이탈 경고
        tracker.record_decision(rule_result, team_id="team_a")
    """

    def __init__(
        self,
        rule_set: RuleSet = RuleSet.FIBA,
    ) -> None:
        self._rule_set = rule_set
        self._lock = RLock()
        self._history: list[_DecisionRecord] = []

        # 팀별 콜 카운트
        self._team_calls: dict[str, int] = defaultdict(int)
        self._team_nocalls: dict[str, int] = defaultdict(int)

        # CallType별 콜 카운트
        self._type_calls: dict[str, int] = defaultdict(int)
        self._type_total: dict[str, int] = defaultdict(int)

    @property
    def rule_set(self) -> RuleSet:
        return self._rule_set

    def record_decision(
        self,
        result: RuleResult,
        *,
        team_id: str | None = None,
    ) -> None:
        """
        판정 기록.

        Args:
            result: 규칙 평가 결과
            team_id: 해당 팀 ID (offending player의 소속팀)
        """
        with self._lock:
            sbin = int(result.confidence / SEVERITY_BIN_WIDTH)
            record = _DecisionRecord(
                result=result,
                team_id=team_id,
                severity_bin=sbin,
            )
            self._history.append(record)
            if len(self._history) > _MAX_DECISION_HISTORY:
                self._history = self._history[-_MAX_DECISION_HISTORY:]

            # 팀별 통계
            if team_id:
                if result.violated:
                    self._team_calls[team_id] += 1
                else:
                    self._team_nocalls[team_id] += 1

            # CallType별 통계
            ct = result.call_type.value
            self._type_total[ct] += 1
            if result.violated:
                self._type_calls[ct] += 1

    def check_consistency(
        self,
        result: RuleResult,
        *,
        team_id: str | None = None,
    ) -> ConsistencyReport:
        """
        판정 일관성 검증.

        현재 판정을 과거 이력과 비교하여 일관성 보고서를 생성합니다.

        Args:
            result: 평가할 판정
            team_id: 해당 팀 ID

        Returns:
            ConsistencyReport — 일관성 보고서
        """
        with self._lock:
            warnings: list[str] = []
            score = 1.0

            # 1. 유사 이벤트 비교 (동일 CallType + 유사 신뢰도)
            sbin = int(result.confidence / SEVERITY_BIN_WIDTH)
            similar = self._find_similar(result.call_type, sbin)
            similar_count = len(similar)
            similar_call_rate = 0.0

            if similar_count >= 2:
                calls = sum(1 for r in similar if r.result.violated)
                similar_call_rate = calls / similar_count

                # 현재 판정이 과거 패턴과 다른지 확인
                if result.violated and similar_call_rate < (1.0 - CONSISTENCY_DEVIATION_THRESHOLD):
                    deviation = 1.0 - similar_call_rate
                    score -= deviation * 0.5
                    warnings.append(
                        f"유사 상황({similar_count}건) 콜 비율 "
                        f"{similar_call_rate:.0%} — 현재 콜 판정은 비일관적",
                    )
                elif not result.violated and similar_call_rate > CONSISTENCY_DEVIATION_THRESHOLD:
                    score -= similar_call_rate * 0.5
                    warnings.append(
                        f"유사 상황({similar_count}건) 콜 비율 "
                        f"{similar_call_rate:.0%} — 현재 노콜 판정은 비일관적",
                    )

            # 2. 팀 간 편향 감지
            bias_warning = self._check_team_bias(team_id)
            if bias_warning:
                warnings.append(bias_warning)
                score -= 0.15

            # 3. 콜 레벨 판정
            call_level = self._determine_call_level()

            score = max(min(score, 1.0), 0.0)
            is_consistent = score >= (1.0 - CONSISTENCY_DEVIATION_THRESHOLD)

            return ConsistencyReport(
                is_consistent=is_consistent,
                consistency_score=round(score, 3),
                bias_warnings=warnings,
                similar_count=similar_count,
                similar_call_rate=round(similar_call_rate, 3),
                call_level=call_level,
            )

    def get_call_level(self) -> str:
        """현재 콜 레벨 반환."""
        with self._lock:
            return self._determine_call_level()

    def get_team_call_counts(self) -> dict[str, dict[str, int]]:
        """팀별 콜/노콜 카운트."""
        with self._lock:
            teams: dict[str, dict[str, int]] = {}
            all_teams = set(self._team_calls.keys()) | set(self._team_nocalls.keys())
            for tid in all_teams:
                teams[tid] = {
                    "calls": self._team_calls.get(tid, 0),
                    "nocalls": self._team_nocalls.get(tid, 0),
                }
            return teams

    def _find_similar(
        self,
        call_type: CallType,
        severity_bin: int,
    ) -> list[_DecisionRecord]:
        """유사 이벤트 검색 (동일 CallType + 유사 빈)."""
        window = CONSISTENCY_COMPARISON_WINDOW
        ct = call_type.value
        similar: list[_DecisionRecord] = []

        for record in reversed(self._history):
            if len(similar) >= window:
                break
            if (
                record.result.call_type.value == ct
                and abs(record.severity_bin - severity_bin) <= 1
            ):
                similar.append(record)

        return similar

    def _check_team_bias(self, team_id: str | None) -> str | None:
        """팀 간 편향 감지."""
        if team_id is None:
            return None

        teams = set(self._team_calls.keys()) | set(self._team_nocalls.keys())
        if len(teams) < 2:
            return None

        # 팀별 총 콜 수 비교
        call_counts = {
            t: self._team_calls.get(t, 0) for t in teams
        }
        if not call_counts:
            return None

        max_team = max(call_counts, key=lambda t: call_counts[t])
        min_team = min(call_counts, key=lambda t: call_counts[t])

        max_calls = call_counts[max_team]
        min_calls = call_counts[min_team]

        total = sum(call_counts.values())
        if total < CALL_LEVEL_CALIBRATION_EVENTS:
            return None  # 아직 캘리브레이션 미완료

        # 편향 비율 (한쪽 팀 콜 > 전체의 70% → 편향 경고)
        if max_calls > 0 and max_calls / total > 0.70:
            return (
                f"팀 편향 감지: {max_team} {max_calls}콜 vs "
                f"{min_team} {min_calls}콜 (비율 {max_calls/total:.0%})"
            )

        return None

    def _determine_call_level(self) -> str:
        """콜 레벨 판정 (tight/normal/loose)."""
        total_events = len(self._history)
        if total_events < CALL_LEVEL_CALIBRATION_EVENTS:
            return "normal"  # 캘리브레이션 미완료

        # 최근 이벤트에서 콜 비율
        recent = self._history[-CALL_LEVEL_CALIBRATION_EVENTS:]
        calls = sum(1 for r in recent if r.result.violated)
        call_rate = calls / len(recent)

        if call_rate >= 0.60:
            return "tight"
        elif call_rate <= 0.25:
            return "loose"
        return "normal"

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._history.clear()
            self._team_calls.clear()
            self._team_nocalls.clear()
            self._type_calls.clear()
            self._type_total.clear()


__all__ = ["ConsistencyTracker", "ConsistencyReport"]
__version__ = "1.0.0"
