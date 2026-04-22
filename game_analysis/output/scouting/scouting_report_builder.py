# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/scouting
파일: scouting_report_builder.py
설명: 종합 스카우팅 리포트 빌더
      - 4개 분석 결과 통합 (프로필 + 성향 + 약점 + 전적)
      - 한글/영문 요약 자동 생성
      - 핵심 포인트 추출 (코칭스태프용)
      - JSON 직렬화 출력

Processing Cadence: POST-GAME (무제한)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/scouting_dto.py (OpponentProfile, TendencyReport, WeaknessReport, HeadToHeadRecord)
의존성: shared/dto/scouting_dto.py
소비자: pre_game/pre_game_briefing_builder, coaching_intelligence, api_server
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.dto.scouting_dto import (
    HeadToHeadRecord,
    OpponentProfile,
    TendencyReport,
    WeaknessReport,
)

logger: Final = logging.getLogger(__name__)

_MAX_KEY_POINTS: Final[int] = 10  # 핵심 포인트 최대 수


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ScoutingReportConfig:
    """스카우팅 리포트 빌더 설정."""

    max_key_points: int = _MAX_KEY_POINTS
    generate_korean: bool = True
    generate_english: bool = True

    @classmethod
    def from_yaml(cls, cfg: dict) -> ScoutingReportConfig:
        """YAML 설정에서 생성."""
        return cls(
            max_key_points=cfg.get("max_key_points", _MAX_KEY_POINTS),
            generate_korean=cfg.get("generate_korean", True),
            generate_english=cfg.get("generate_english", True),
        )


# =============================================================================
# 출력
# =============================================================================
@dataclass(slots=True)
class ScoutingReport:
    """종합 스카우팅 리포트."""

    team_id: str = ""
    team_name: str = ""
    # 구성 요소
    profile: OpponentProfile | None = None
    tendency: TendencyReport | None = None
    weakness: WeaknessReport | None = None
    head_to_head: HeadToHeadRecord | None = None
    # 핵심 포인트
    key_points_ko: list[str] = field(default_factory=list)
    key_points_en: list[str] = field(default_factory=list)
    # 요약
    summary_ko: str = ""
    summary_en: str = ""


# =============================================================================
# 빌더
# =============================================================================
class ScoutingReportBuilder:
    """
    종합 스카우팅 리포트 빌더.

    4개 분석 결과(프로필, 성향, 약점, 전적)를 통합하여
    코칭스태프용 종합 리포트를 생성합니다.
    """

    def __init__(self, config: ScoutingReportConfig | None = None) -> None:
        self._config = config or ScoutingReportConfig()
        self._lock = RLock()
        self._profile: OpponentProfile | None = None
        self._tendency: TendencyReport | None = None
        self._weakness: WeaknessReport | None = None
        self._head_to_head: HeadToHeadRecord | None = None
        self._event_history: list[str] = []

    @property
    def name(self) -> str:
        return "ScoutingReportBuilder"

    # === 데이터 설정 ===

    def set_profile(self, profile: OpponentProfile) -> None:
        """상대팀 프로필 설정."""
        with self._lock:
            self._profile = profile
            self._event_history.append("profile_set")

    def set_tendency(self, tendency: TendencyReport) -> None:
        """성향 보고서 설정."""
        with self._lock:
            self._tendency = tendency
            self._event_history.append("tendency_set")

    def set_weakness(self, weakness: WeaknessReport) -> None:
        """약점 보고서 설정."""
        with self._lock:
            self._weakness = weakness
            self._event_history.append("weakness_set")

    def set_head_to_head(self, h2h: HeadToHeadRecord) -> None:
        """상대 전적 설정."""
        with self._lock:
            self._head_to_head = h2h
            self._event_history.append("h2h_set")

    # === 리포트 생성 ===

    def build(self) -> ScoutingReport:
        """
        종합 스카우팅 리포트 생성.

        Returns:
            ScoutingReport
        """
        with self._lock:
            team_id = ""
            team_name = ""
            if self._profile is not None:
                team_id = self._profile.team_id
                team_name = self._profile.team_name

            key_points_ko = self._generate_key_points_ko()
            key_points_en = self._generate_key_points_en()
            summary_ko = self._generate_summary_ko()
            summary_en = self._generate_summary_en()

            return ScoutingReport(
                team_id=team_id,
                team_name=team_name,
                profile=self._profile,
                tendency=self._tendency,
                weakness=self._weakness,
                head_to_head=self._head_to_head,
                key_points_ko=key_points_ko,
                key_points_en=key_points_en,
                summary_ko=summary_ko,
                summary_en=summary_en,
            )

    def build_json(self) -> dict:
        """JSON 직렬화 가능한 dict 출력."""
        with self._lock:
            result: dict = {"team_id": "", "team_name": ""}

            if self._profile is not None:
                result["team_id"] = self._profile.team_id
                result["team_name"] = self._profile.team_name
                result["profile"] = {
                    "games_analyzed": self._profile.games_analyzed,
                    "offensive_rating": self._profile.offensive_rating,
                    "defensive_rating": self._profile.defensive_rating,
                    "pace": self._profile.pace,
                    "primary_offense": self._profile.primary_offense,
                    "primary_defense": self._profile.primary_defense,
                    "strengths": list(self._profile.strengths),
                    "weaknesses": list(self._profile.weaknesses),
                    "key_players": [
                        {
                            "tracking_id": kp.tracking_id,
                            "name": kp.name,
                            "role": kp.role,
                            "ppg": kp.ppg,
                            "usage_pct": kp.usage_pct,
                        }
                        for kp in self._profile.key_players
                    ],
                }

            if self._tendency is not None:
                result["tendency"] = {
                    "shot_zone_preferences": dict(
                        self._tendency.shot_zone_preferences
                    ),
                    "play_type_preferences": dict(
                        self._tendency.play_type_preferences
                    ),
                    "transition_tendency": self._tendency.transition_tendency,
                    "three_point_rate": self._tendency.three_point_rate,
                    "paint_attack_rate": self._tendency.paint_attack_rate,
                }

            if self._weakness is not None:
                result["weakness"] = {
                    "defensive_gaps": [
                        {
                            "zone": g.zone,
                            "gap_severity": g.gap_severity,
                            "exploitable_play": g.exploitable_play,
                        }
                        for g in self._weakness.defensive_gaps
                    ],
                    "transition_weakness_score": (
                        self._weakness.transition_weakness_score
                    ),
                    "rebounding_weakness": self._weakness.rebounding_weakness,
                    "three_point_defense_rating": (
                        self._weakness.three_point_defense_rating
                    ),
                }

            if self._head_to_head is not None:
                h2h = self._head_to_head
                result["head_to_head"] = {
                    "total_games": h2h.total_games,
                    "wins": h2h.wins,
                    "losses": h2h.losses,
                    "avg_point_differential": h2h.avg_point_differential,
                    "successful_strategies": list(h2h.successful_strategies),
                    "failed_strategies": list(h2h.failed_strategies),
                }

            result["key_points_ko"] = self._generate_key_points_ko()
            result["summary_ko"] = self._generate_summary_ko()
            return result

    # === 핵심 포인트 생성 ===

    def _generate_key_points_ko(self) -> list[str]:
        """한글 핵심 포인트 생성."""
        if not self._config.generate_korean:
            return []

        points: list[str] = []

        # 프로필 기반
        if self._profile is not None:
            p = self._profile
            if p.offensive_rating > 0:
                points.append(
                    f"공격 효율 {p.offensive_rating:.1f} / "
                    f"수비 효율 {p.defensive_rating:.1f}"
                )
            if p.primary_offense:
                points.append(f"주력 공격: {p.primary_offense}")
            if p.primary_defense:
                points.append(f"주력 수비: {p.primary_defense}")
            for s in p.strengths[:2]:
                points.append(f"강점: {s}")

        # 성향 기반
        if self._tendency is not None:
            t = self._tendency
            if t.three_point_rate > 0.35:
                points.append(
                    f"3점 의존도 높음 ({t.three_point_rate:.1%})"
                )
            if t.transition_tendency > 20.0:
                points.append(
                    f"전환 공격 빈도 높음 ({t.transition_tendency:.1f}%)"
                )

        # 약점 기반
        if self._weakness is not None:
            w = self._weakness
            for gap in w.defensive_gaps[:2]:
                points.append(
                    f"수비 갭: {gap.zone} (심각도 {gap.gap_severity:.0%})"
                )
            if w.transition_weakness_score >= 50.0:
                points.append("전환 수비 취약")
            if w.rebounding_weakness != "none":
                weakness_map = {
                    "offensive": "공격 리바운드",
                    "defensive": "수비 리바운드",
                    "both": "전체 리바운드",
                }
                label = weakness_map.get(w.rebounding_weakness, w.rebounding_weakness)
                points.append(f"리바운드 약점: {label}")

        # 전적 기반
        if self._head_to_head is not None:
            h = self._head_to_head
            if h.total_games > 0:
                points.append(
                    f"상대 전적: {h.wins}승 {h.losses}패 "
                    f"(평균 점수차 {h.avg_point_differential:+.1f})"
                )

        return points[: self._config.max_key_points]

    def _generate_key_points_en(self) -> list[str]:
        """영문 핵심 포인트 생성."""
        if not self._config.generate_english:
            return []

        points: list[str] = []

        if self._profile is not None:
            p = self._profile
            if p.offensive_rating > 0:
                points.append(
                    f"ORTG {p.offensive_rating:.1f} / "
                    f"DRTG {p.defensive_rating:.1f}"
                )
            if p.primary_offense:
                points.append(f"Primary offense: {p.primary_offense}")

        if self._weakness is not None:
            w = self._weakness
            for gap in w.defensive_gaps[:2]:
                points.append(
                    f"Defensive gap: {gap.zone} "
                    f"(severity {gap.gap_severity:.0%})"
                )

        if self._head_to_head is not None:
            h = self._head_to_head
            if h.total_games > 0:
                points.append(
                    f"H2H record: {h.wins}W-{h.losses}L "
                    f"(avg diff {h.avg_point_differential:+.1f})"
                )

        return points[: self._config.max_key_points]

    def _generate_summary_ko(self) -> str:
        """한글 요약 생성."""
        if self._profile is None:
            return ""

        p = self._profile
        parts: list[str] = [f"{p.team_name}"]

        if p.games_analyzed > 0:
            parts.append(f"({p.games_analyzed}경기 분석)")

        if p.offensive_rating > 0:
            parts.append(
                f" 공격효율 {p.offensive_rating:.1f},"
                f" 수비효율 {p.defensive_rating:.1f}."
            )

        if p.strengths:
            parts.append(f" 강점: {', '.join(p.strengths[:3])}.")

        if p.weaknesses:
            parts.append(f" 약점: {', '.join(p.weaknesses[:3])}.")

        if self._head_to_head is not None and self._head_to_head.total_games > 0:
            h = self._head_to_head
            parts.append(
                f" 상대전적 {h.wins}승 {h.losses}패."
            )

        return "".join(parts)

    def _generate_summary_en(self) -> str:
        """영문 요약 생성."""
        if not self._config.generate_english or self._profile is None:
            return ""

        p = self._profile
        parts: list[str] = [p.team_name]

        if p.games_analyzed > 0:
            parts.append(f" ({p.games_analyzed} games analyzed)")

        if p.offensive_rating > 0:
            parts.append(
                f" ORTG {p.offensive_rating:.1f},"
                f" DRTG {p.defensive_rating:.1f}."
            )

        return "".join(parts)

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._profile = None
            self._tendency = None
            self._weakness = None
            self._head_to_head = None
            self._event_history.clear()

    def get_event_history(self) -> list[str]:
        """이벤트 이력."""
        with self._lock:
            return list(self._event_history)


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "ScoutingReportConfig",
    "ScoutingReportBuilder",
    "ScoutingReport",
]

__version__ = "1.0.0"
