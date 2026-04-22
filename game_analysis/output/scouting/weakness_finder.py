# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/scouting
파일: weakness_finder.py
설명: 상대팀 약점 발견기
      - 수비 갭 분석 (존별 실점률 기반)
      - 전환 수비 취약점 평가
      - 리바운드 약점 감지
      - 매치업 약점 식별
      - 3점 수비 등급 산출

Processing Cadence: POST-GAME (무제한)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/scouting_dto.py (WeaknessReport, DefensiveGap, MatchupExploit)
의존성: shared/dto/scouting_dto.py
소비자: scouting_report_builder, coaching_intelligence, pre_game
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.dto.scouting_dto import DefensiveGap, MatchupExploit, WeaknessReport

logger: Final = logging.getLogger(__name__)

_MAX_RECORDS: Final[int] = 2000


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class WeaknessFinderConfig:
    """약점 발견기 설정."""

    max_records: int = _MAX_RECORDS
    # 수비 갭 판단 기준
    zone_gap_fg_pct_threshold: float = 0.50  # FG% 50% 이상이면 수비 갭
    zone_min_attempts: int = 5  # 존별 최소 시도 수
    # 전환 수비 임계
    transition_weakness_ppp_threshold: float = 1.15  # 전환 PPP 1.15 이상 → 취약
    # 리바운드 약점 임계
    oreb_rate_weakness: float = 0.25  # 공리 허용률 25% 이상 → 취약
    dreb_rate_weakness: float = 0.70  # 수리 확보율 70% 이하 → 취약
    # 3점 수비 임계
    three_pt_defense_bad: float = 0.37  # 상대 3P% 37% 이상 → 취약
    # 매치업 약점 임계
    matchup_fg_pct_weakness: float = 0.50  # 매치업 FG% 50% 이상 → 약점
    matchup_min_possessions: int = 5  # 최소 점유 수

    @classmethod
    def from_yaml(cls, cfg: dict) -> WeaknessFinderConfig:
        """YAML 설정에서 생성."""
        return cls(
            max_records=cfg.get("max_records", _MAX_RECORDS),
            zone_gap_fg_pct_threshold=cfg.get("zone_gap_fg_pct_threshold", 0.50),
            zone_min_attempts=cfg.get("zone_min_attempts", 5),
            transition_weakness_ppp_threshold=cfg.get(
                "transition_weakness_ppp_threshold", 1.15
            ),
            oreb_rate_weakness=cfg.get("oreb_rate_weakness", 0.25),
            dreb_rate_weakness=cfg.get("dreb_rate_weakness", 0.70),
            three_pt_defense_bad=cfg.get("three_pt_defense_bad", 0.37),
            matchup_fg_pct_weakness=cfg.get("matchup_fg_pct_weakness", 0.50),
            matchup_min_possessions=cfg.get("matchup_min_possessions", 5),
        )


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class ZoneDefenseInput:
    """존별 수비 데이터 입력."""

    zone: str = ""  # 수비 구역명
    fg_attempts_allowed: int = 0  # 허용 슛 시도
    fg_made_allowed: int = 0  # 허용 슛 성공
    points_allowed: int = 0


@dataclass(slots=True)
class TransitionDefenseInput:
    """전환 수비 데이터 입력."""

    transition_possessions: int = 0
    transition_points_allowed: int = 0


@dataclass(slots=True)
class ReboundInput:
    """리바운드 데이터 입력."""

    offensive_rebounds: int = 0  # 상대 공리 허용
    defensive_rebounds: int = 0  # 우리 수리 확보
    total_rebound_chances: int = 0  # 전체 리바운드 기회


@dataclass(slots=True)
class MatchupDefenseInput:
    """매치업별 수비 데이터 입력."""

    player_tracking_id: int = 0
    weakness_type: str = ""  # post_defense, perimeter_defense, iso_defense 등
    possessions: int = 0
    fg_attempts: int = 0
    fg_made: int = 0


@dataclass(slots=True)
class ThreePointDefenseInput:
    """3점 수비 데이터 입력."""

    three_pt_attempts_allowed: int = 0
    three_pt_made_allowed: int = 0


# =============================================================================
# 약점 발견기
# =============================================================================
class WeaknessFinder:
    """
    상대팀 약점 발견기.

    수비 갭, 전환 취약점, 리바운드 약점, 매치업 약점, 3점 수비 등급을 분석합니다.
    """

    def __init__(self, config: WeaknessFinderConfig | None = None) -> None:
        self._config = config or WeaknessFinderConfig()
        self._lock = RLock()
        self._team_id: str = ""
        self._zone_data: list[ZoneDefenseInput] = []
        self._transition_data: list[TransitionDefenseInput] = []
        self._rebound_data: list[ReboundInput] = []
        self._matchup_data: list[MatchupDefenseInput] = []
        self._three_pt_data: list[ThreePointDefenseInput] = []

    @property
    def name(self) -> str:
        return "WeaknessFinder"

    # === 데이터 입력 ===

    def set_team_id(self, team_id: str) -> None:
        """팀 ID 설정."""
        with self._lock:
            self._team_id = team_id

    def add_zone_defense(self, data: ZoneDefenseInput) -> None:
        """존별 수비 데이터 추가."""
        with self._lock:
            self._zone_data.append(data)

    def add_transition_defense(self, data: TransitionDefenseInput) -> None:
        """전환 수비 데이터 추가."""
        with self._lock:
            self._transition_data.append(data)

    def add_rebound_data(self, data: ReboundInput) -> None:
        """리바운드 데이터 추가."""
        with self._lock:
            self._rebound_data.append(data)

    def add_matchup_defense(self, data: MatchupDefenseInput) -> None:
        """매치업 수비 데이터 추가."""
        with self._lock:
            self._matchup_data.append(data)

    def add_three_pt_defense(self, data: ThreePointDefenseInput) -> None:
        """3점 수비 데이터 추가."""
        with self._lock:
            self._three_pt_data.append(data)

    # === 분석 ===

    def find_weaknesses(self) -> WeaknessReport:
        """
        약점 분석 실행.

        Returns:
            WeaknessReport DTO
        """
        with self._lock:
            defensive_gaps = self._analyze_zone_gaps()
            transition_score = self._analyze_transition_weakness()
            rebound_weakness = self._analyze_rebound_weakness()
            matchup_exploits = self._analyze_matchup_weaknesses()
            three_pt_rating = self._analyze_three_pt_defense()

            return WeaknessReport(
                team_id=self._team_id,
                defensive_gaps=defensive_gaps,
                transition_weakness_score=round(transition_score, 1),
                rebounding_weakness=rebound_weakness,
                matchup_exploits=matchup_exploits,
                three_point_defense_rating=round(three_pt_rating, 1),
            )

    # === 내부 메서드 ===

    def _analyze_zone_gaps(self) -> list[DefensiveGap]:
        """존별 수비 갭 분석."""
        cfg = self._config
        gaps: list[DefensiveGap] = []

        # 존별 합산
        zone_agg: dict[str, tuple[int, int]] = {}  # zone → (attempts, made)
        for zd in self._zone_data:
            if zd.zone:
                prev = zone_agg.get(zd.zone, (0, 0))
                zone_agg[zd.zone] = (
                    prev[0] + zd.fg_attempts_allowed,
                    prev[1] + zd.fg_made_allowed,
                )

        for zone, (attempts, made) in zone_agg.items():
            if attempts < cfg.zone_min_attempts:
                continue
            fg_pct = made / attempts if attempts > 0 else 0.0
            if fg_pct >= cfg.zone_gap_fg_pct_threshold:
                # 갭 심각도: FG% 초과분을 0~1 스케일로 변환
                severity = min(
                    (fg_pct - cfg.zone_gap_fg_pct_threshold) / 0.20, 1.0
                )
                gaps.append(
                    DefensiveGap(
                        zone=zone,
                        gap_severity=round(severity, 2),
                        exploitable_play=self._suggest_exploit_play(zone),
                    )
                )

        # 심각도 기준 내림차순
        gaps.sort(key=lambda g: g.gap_severity, reverse=True)
        return gaps

    def _analyze_transition_weakness(self) -> float:
        """전환 수비 취약점 점수 (0~100)."""
        total_poss = sum(t.transition_possessions for t in self._transition_data)
        total_pts = sum(t.transition_points_allowed for t in self._transition_data)
        if total_poss == 0:
            return 0.0

        ppp = total_pts / total_poss
        threshold = self._config.transition_weakness_ppp_threshold
        if ppp < threshold:
            return 0.0

        # PPP 초과분을 0~100 스케일로 변환 (최대 0.50 초과 시 100)
        score = min((ppp - threshold) / 0.50, 1.0) * 100.0
        return score

    def _analyze_rebound_weakness(self) -> str:
        """리바운드 약점 유형 판단."""
        cfg = self._config
        total_oreb = sum(r.offensive_rebounds for r in self._rebound_data)
        total_dreb = sum(r.defensive_rebounds for r in self._rebound_data)
        total_chances = sum(r.total_rebound_chances for r in self._rebound_data)

        if total_chances == 0:
            return "none"

        oreb_rate = total_oreb / total_chances  # 상대 공리 허용 비율
        dreb_rate = total_dreb / total_chances  # 우리 수리 확보 비율

        oreb_weak = oreb_rate >= cfg.oreb_rate_weakness
        dreb_weak = dreb_rate <= cfg.dreb_rate_weakness

        if oreb_weak and dreb_weak:
            return "both"
        if oreb_weak:
            return "offensive"
        if dreb_weak:
            return "defensive"
        return "none"

    def _analyze_matchup_weaknesses(self) -> list[MatchupExploit]:
        """매치업 약점 식별."""
        cfg = self._config
        exploits: list[MatchupExploit] = []

        for md in self._matchup_data:
            if md.possessions < cfg.matchup_min_possessions:
                continue
            if md.fg_attempts == 0:
                continue
            fg_pct = md.fg_made / md.fg_attempts
            if fg_pct >= cfg.matchup_fg_pct_weakness:
                severity = min(
                    (fg_pct - cfg.matchup_fg_pct_weakness) / 0.20, 1.0
                )
                exploits.append(
                    MatchupExploit(
                        player_tracking_id=md.player_tracking_id,
                        weakness_type=md.weakness_type,
                        severity=round(severity, 2),
                    )
                )

        exploits.sort(key=lambda e: e.severity, reverse=True)
        return exploits

    def _analyze_three_pt_defense(self) -> float:
        """3점 수비 등급 (0~100, 100이 최고)."""
        total_att = sum(t.three_pt_attempts_allowed for t in self._three_pt_data)
        total_made = sum(t.three_pt_made_allowed for t in self._three_pt_data)

        if total_att == 0:
            return 50.0  # 데이터 없으면 중립

        three_pct = total_made / total_att
        # 등급: 30% 이하 → 100점 (최고), 40% 이상 → 0점 (최악)
        rating = max(0.0, min(100.0, (0.40 - three_pct) / 0.10 * 100.0))
        return rating

    @staticmethod
    def _suggest_exploit_play(zone: str) -> str:
        """존에 따른 공략 플레이 제안."""
        paint_zones = {"paint_left", "paint_center", "paint_right"}
        mid_zones = {
            "mid_left_corner", "mid_left_wing", "mid_left_elbow",
            "mid_center", "mid_right_elbow", "mid_right_wing", "mid_right_corner",
        }
        if zone in paint_zones:
            return "pick_and_roll"  # 페인트 갭 → PnR 공략
        if zone in mid_zones:
            return "isolation"  # 미드레인지 갭 → ISO 공략
        return "spot_up"  # 3점 존 갭 → 캐치앤슛

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._team_id = ""
            self._zone_data.clear()
            self._transition_data.clear()
            self._rebound_data.clear()
            self._matchup_data.clear()
            self._three_pt_data.clear()

    def get_event_history(self) -> list[ZoneDefenseInput]:
        """존별 수비 데이터 이력."""
        with self._lock:
            return list(self._zone_data)


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "WeaknessFinderConfig",
    "WeaknessFinder",
    "ZoneDefenseInput",
    "TransitionDefenseInput",
    "ReboundInput",
    "MatchupDefenseInput",
    "ThreePointDefenseInput",
]

__version__ = "1.0.0"
