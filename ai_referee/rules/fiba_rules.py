# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/rules
파일: fiba_rules.py
설명: FIBA Official Basketball Rules 2024 규정 정의
      - 국제 대회 기준 규정 (모든 리그의 기반)
      - 바이올레이션 12종 + 파울 11종의 FIBA 파라미터
      - 경기 시간, 코트 규격, 파울 규칙, 타임아웃 규칙
      - 리그별 규칙(NBA/KBL/NBL)이 이 클래스를 기반으로 오버라이드

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - FIBA Official Basketball Rules 2024
    - configs/ai_referee/fiba_rules.yaml
    - configs/ai_referee/violation_thresholds.yaml
    - configs/ai_referee/foul_criteria.yaml
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Final

from shared.constants.referee_rule_constants import RuleSet

logger: Final = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================
_FIBA_RULE_SET: Final[RuleSet] = RuleSet.FIBA


# =============================================================================
# 시간 규칙
# =============================================================================
@dataclass(slots=True)
class GameTimeRules:
    """경기 시간 규칙."""

    quarter_duration_sec: int = 600           # 10분
    overtime_duration_sec: int = 300           # 연장전 5분
    halftime_break_sec: int = 900             # 하프타임 15분
    period_break_sec: int = 120               # 쿼터 간 휴식 2분
    shot_clock_sec: int = 24                  # 슛클락 24초
    shot_clock_reset_oreb_sec: int = 14       # 공격 리바운드 후 14초 리셋
    backcourt_sec: int = 8                    # 백코트 8초
    free_throw_sec: int = 5                   # 자유투 시도 5초
    throw_in_sec: int = 5                     # 스로인 5초

    @classmethod
    def from_yaml(cls, cfg: dict) -> GameTimeRules:
        """YAML game_time 섹션에서 생성."""
        return cls(
            quarter_duration_sec=cfg.get("quarter_duration_sec", 600),
            overtime_duration_sec=cfg.get("overtime_duration_sec", 300),
            halftime_break_sec=cfg.get("halftime_break_sec", 900),
            period_break_sec=cfg.get("period_break_sec", 120),
            shot_clock_sec=cfg.get("shot_clock_sec", 24),
            shot_clock_reset_oreb_sec=cfg.get("shot_clock_reset_oreb_sec", 14),
            backcourt_sec=cfg.get("backcourt_sec", 8),
            free_throw_sec=cfg.get("free_throw_sec", 5),
            throw_in_sec=cfg.get("throw_in_sec", 5),
        )


# =============================================================================
# 코트 규격
# =============================================================================
@dataclass(slots=True)
class CourtDimensions:
    """코트 규격."""

    three_point_distance_m: float = 6.75      # 3점 라인 거리
    three_point_corner_m: float = 6.75        # 코너 3점 (FIBA는 동일)
    free_throw_distance_m: float = 4.225      # 프리스로 라인 거리
    restricted_area_arc_m: float = 1.25       # 제한 구역 아크
    paint_width_m: float = 4.9                # 페인트존 너비
    paint_depth_m: float = 5.8                # 페인트존 깊이

    @classmethod
    def from_yaml(cls, cfg: dict) -> CourtDimensions:
        """YAML court 섹션에서 생성."""
        return cls(
            three_point_distance_m=cfg.get("three_point_distance_m", 6.75),
            three_point_corner_m=cfg.get("three_point_corner_m", 6.75),
            free_throw_distance_m=cfg.get("free_throw_distance_m", 4.225),
            restricted_area_arc_m=cfg.get("restricted_area_arc_m", 1.25),
            paint_width_m=cfg.get("paint_width_m", 4.9),
            paint_depth_m=cfg.get("paint_depth_m", 5.8),
        )


# =============================================================================
# 파울 규칙
# =============================================================================
@dataclass(slots=True)
class FoulRules:
    """파울 규칙."""

    max_personal_fouls: int = 5               # 개인 파울 퇴장 기준
    team_foul_bonus_threshold: int = 4        # 쿼터당 팀파울 보너스 진입
    technical_foul_ejection: int = 2           # 테크니컬 퇴장 기준
    unsportsmanlike_foul_ejection: int = 2     # 비신사적 파울 퇴장 기준
    disqualifying_foul: bool = True            # 실격 파울 (즉시 퇴장)

    # 자유투 부여 규칙
    bonus_free_throws: int = 2                # 보너스 상태 시 FT 수
    shooting_foul_2pt: int = 2                # 2점 슈팅 파울 FT 수
    shooting_foul_3pt: int = 3                # 3점 슈팅 파울 FT 수
    technical_free_throws: int = 1            # 테크니컬 FT 수
    unsportsmanlike_free_throws: int = 2       # 비신사적 FT 수

    @classmethod
    def from_yaml(cls, cfg: dict) -> FoulRules:
        """YAML fouls 섹션에서 생성."""
        ft = cfg.get("free_throws", {})
        return cls(
            max_personal_fouls=cfg.get("max_personal_fouls", 5),
            team_foul_bonus_threshold=cfg.get("team_foul_bonus_threshold", 4),
            technical_foul_ejection=cfg.get("technical_foul_ejection", 2),
            unsportsmanlike_foul_ejection=cfg.get("unsportsmanlike_foul_ejection", 2),
            disqualifying_foul=cfg.get("disqualifying_foul", True),
            bonus_free_throws=ft.get("bonus_free_throws", 2),
            shooting_foul_2pt=ft.get("shooting_foul_2pt", 2),
            shooting_foul_3pt=ft.get("shooting_foul_3pt", 3),
            technical_free_throws=ft.get("technical_free_throws", 1),
            unsportsmanlike_free_throws=ft.get("unsportsmanlike_free_throws", 2),
        )

    def get_shooting_foul_ft(self, is_three_point: bool) -> int:
        """슈팅 파울 자유투 수 반환."""
        return self.shooting_foul_3pt if is_three_point else self.shooting_foul_2pt


# =============================================================================
# 타임아웃 규칙
# =============================================================================
@dataclass(slots=True)
class TimeoutRules:
    """타임아웃 규칙."""

    total_per_game: int = 5                   # 경기당 총 타임아웃
    first_half_max: int = 2                   # 전반 최대
    second_half_max: int = 3                  # 후반 최대
    overtime_additional: int = 1              # 연장전 추가
    duration_sec: int = 60                    # 타임아웃 시간
    carryover: bool = False                   # 미사용 이월 여부

    @classmethod
    def from_yaml(cls, cfg: dict) -> TimeoutRules:
        """YAML timeouts 섹션에서 생성."""
        return cls(
            total_per_game=cfg.get("total_per_game", 5),
            first_half_max=cfg.get("first_half_max", 2),
            second_half_max=cfg.get("second_half_max", 3),
            overtime_additional=cfg.get("overtime_additional", 1),
            duration_sec=cfg.get("duration_sec", 60),
            carryover=cfg.get("carryover", False),
        )


# =============================================================================
# 3초 규칙
# =============================================================================
@dataclass(slots=True)
class ThreeSecondRules:
    """3초 규칙."""

    offensive_three_sec: bool = True           # 공격 3초 적용
    defensive_three_sec: bool = False          # 수비 3초 (NBA 전용)
    grace_period_sec: float = 0.5             # 유예 시간
    paint_entry_tolerance_m: float = 0.1      # 페인트 진입 여유

    @classmethod
    def from_yaml(cls, cfg: dict) -> ThreeSecondRules:
        """YAML three_second_rule 섹션에서 생성."""
        return cls(
            offensive_three_sec=cfg.get("offensive_three_sec", True),
            defensive_three_sec=cfg.get("defensive_three_sec", False),
            grace_period_sec=cfg.get("grace_period_sec", 0.5),
            paint_entry_tolerance_m=cfg.get("paint_entry_tolerance_m", 0.1),
        )


# =============================================================================
# 트래블링 규칙
# =============================================================================
@dataclass(slots=True)
class TravelingRules:
    """트래블링 규칙."""

    # 피봇풋
    pivot_lift_threshold_m: float = 0.05       # 피봇풋 들림 높이
    pivot_slide_threshold_m: float = 0.15      # 피봇풋 미끄러짐 허용

    # 게더 스텝
    gather_step_enabled: bool = True           # 게더 스텝 적용
    max_steps_after_gather: int = 2            # 게더 후 최대 스텝
    zero_step_enabled: bool = False            # 제로 스텝 (NBA 전용)

    # 점프 스탑
    simultaneous_landing_tolerance_ms: int = 50  # 양발 동시 착지 허용 (ms)

    @classmethod
    def from_yaml(cls, cfg: dict) -> TravelingRules:
        """YAML traveling 섹션에서 생성."""
        pivot = cfg.get("pivot_foot", {})
        gather = cfg.get("gather_step", {})
        jump = cfg.get("jump_stop", {})
        return cls(
            pivot_lift_threshold_m=pivot.get("lift_threshold_m", 0.05),
            pivot_slide_threshold_m=pivot.get("slide_threshold_m", 0.15),
            gather_step_enabled=gather.get("enabled", True),
            max_steps_after_gather=gather.get("max_steps_after_gather", 2),
            zero_step_enabled=gather.get("zero_step_enabled", False),
            simultaneous_landing_tolerance_ms=jump.get(
                "both_feet_simultaneous_tolerance_ms", 50,
            ),
        )


# =============================================================================
# 리그 고유 규칙
# =============================================================================
@dataclass(slots=True)
class LeagueSpecificRules:
    """리그 고유 규칙."""

    # 비신사적 파울 기준
    unsportsmanlike_criteria: list[str] = field(default_factory=lambda: [
        "unnecessary_contact",
        "excessive_contact",
        "no_play_on_ball",
        "fast_break_prevention",
    ])

    # 점유권 교대 화살표 (FIBA: true, NBA: false)
    alternating_possession: bool = True
    alternating_possession_reset_on_ot: bool = True

    # 코치 챌린지
    coach_challenge_enabled: bool = False
    challenges_per_game: int = 0

    # 리플레이 (IRS)
    instant_replay_situations: list[str] = field(default_factory=lambda: [
        "shot_clock_expiry",
        "end_of_period",
        "2pt_or_3pt",
        "goaltending",
        "flagrant_foul",
    ])

    # NBA 전용 — Clear Path Foul
    clear_path_foul_enabled: bool = False
    clear_path_free_throws: int = 0

    # NBA 전용 — Transition Take Foul
    transition_take_foul_enabled: bool = False

    # 클러치 상황 정의 (리그별 분기)
    # FIBA: 4Q + 5분 이내 + 5점차 이내
    # NBA: 4Q or OT + 5분 이내 + 5점차 이내 (NBA 공식 정의)
    # KBL: 4Q + 5분 이내 + 6점차 이내 (KBL 관습)
    # NBL: 4Q + 3분 이내 + 10점차 이내 (NBL 관습)
    clutch_quarter_min: int = 4                  # 클러치 진입 쿼터
    clutch_clock_sec: float = 300.0              # 클러치 잔여시간 (초)
    clutch_score_diff_max: int = 5               # 클러치 점수차 (점)

    @classmethod
    def from_yaml(cls, cfg: dict) -> LeagueSpecificRules:
        """YAML league_specific 섹션에서 생성 (fiba_specific, nba_specific 등)."""
        # FIBA 기본값
        unsportsmanlike = cfg.get("unsportsmanlike_criteria", [
            "unnecessary_contact", "excessive_contact",
            "no_play_on_ball", "fast_break_prevention",
        ])
        alt_poss = cfg.get("alternating_possession", {})
        irs = cfg.get("instant_replay", {})
        challenge = cfg.get("coach_challenge", {}) if isinstance(
            cfg.get("coach_challenge"), dict,
        ) else {}
        clear_path = cfg.get("clear_path_foul", {})
        clutch = cfg.get("clutch", {}) if isinstance(cfg.get("clutch"), dict) else {}

        return cls(
            unsportsmanlike_criteria=(
                unsportsmanlike if isinstance(unsportsmanlike, list) else []
            ),
            alternating_possession=alt_poss.get("enabled", True) if isinstance(
                alt_poss, dict,
            ) else True,
            alternating_possession_reset_on_ot=alt_poss.get(
                "reset_on_overtime", True,
            ) if isinstance(alt_poss, dict) else True,
            coach_challenge_enabled=(
                challenge.get("enabled", False) if challenge else
                cfg.get("coach_challenge", False)
                if isinstance(cfg.get("coach_challenge"), bool) else False
            ),
            challenges_per_game=challenge.get("challenges_per_game", 0),
            instant_replay_situations=irs.get(
                "available_situations", [],
            ) if isinstance(irs, dict) else [],
            clear_path_foul_enabled=clear_path.get("enabled", False) if isinstance(
                clear_path, dict,
            ) else False,
            clear_path_free_throws=clear_path.get("free_throws", 0) if isinstance(
                clear_path, dict,
            ) else 0,
            clutch_quarter_min=int(clutch.get("quarter_min", 4)),
            clutch_clock_sec=float(clutch.get("clock_sec", 300.0)),
            clutch_score_diff_max=int(clutch.get("score_diff_max", 5)),
        )


# =============================================================================
# FIBARules — FIBA 규정 통합
# =============================================================================
class FIBARules:
    """
    FIBA Official Basketball Rules 2024.

    국제 대회 기준 규정으로, 모든 리그 규칙의 기반입니다.
    KBL/NBL/EUROLEAGUE는 이 규정을 기반으로 소수의 차이만 오버라이드합니다.

    YAML 설정(configs/ai_referee/fiba_rules.yaml)에서 로딩하거나,
    기본값으로 생성할 수 있습니다.
    """

    def __init__(
        self,
        *,
        game_time: GameTimeRules | None = None,
        court: CourtDimensions | None = None,
        fouls: FoulRules | None = None,
        timeouts: TimeoutRules | None = None,
        three_second: ThreeSecondRules | None = None,
        traveling: TravelingRules | None = None,
        league_specific: LeagueSpecificRules | None = None,
    ) -> None:
        self._rule_set = _FIBA_RULE_SET

        self._game_time = game_time or GameTimeRules()
        self._court = court or CourtDimensions()
        self._fouls = fouls or FoulRules()
        self._timeouts = timeouts or TimeoutRules()
        self._three_second = three_second or ThreeSecondRules()
        self._traveling = traveling or TravelingRules()
        self._league_specific = league_specific or LeagueSpecificRules()

    # === 속성 ===

    @property
    def rule_set(self) -> RuleSet:
        return self._rule_set

    @property
    def game_time(self) -> GameTimeRules:
        return self._game_time

    @property
    def court(self) -> CourtDimensions:
        return self._court

    @property
    def fouls(self) -> FoulRules:
        return self._fouls

    @property
    def timeouts(self) -> TimeoutRules:
        return self._timeouts

    @property
    def three_second(self) -> ThreeSecondRules:
        return self._three_second

    @property
    def traveling(self) -> TravelingRules:
        return self._traveling

    @property
    def league_specific(self) -> LeagueSpecificRules:
        return self._league_specific

    # === 팩토리 ===

    @classmethod
    def from_yaml(cls, cfg: dict) -> FIBARules:
        """
        YAML 설정에서 FIBARules 생성.

        Args:
            cfg: fiba_rules.yaml 전체 딕셔너리

        Returns:
            FIBARules 인스턴스
        """
        return cls(
            game_time=GameTimeRules.from_yaml(cfg.get("game_time", {})),
            court=CourtDimensions.from_yaml(cfg.get("court", {})),
            fouls=FoulRules.from_yaml(cfg.get("fouls", {})),
            timeouts=TimeoutRules.from_yaml(cfg.get("timeouts", {})),
            three_second=ThreeSecondRules.from_yaml(cfg.get("three_second_rule", {})),
            traveling=TravelingRules.from_yaml(cfg.get("traveling", {})),
            league_specific=LeagueSpecificRules.from_yaml(
                cfg.get("fiba_specific", {}),
            ),
        )

    # === 규칙 조회 ===

    def is_bonus_situation(self, team_fouls_in_quarter: int) -> bool:
        """팀 보너스 상황 판정."""
        return team_fouls_in_quarter >= self._fouls.team_foul_bonus_threshold

    def should_eject_on_personal(self, personal_fouls: int) -> bool:
        """개인 파울 퇴장 판정."""
        return personal_fouls >= self._fouls.max_personal_fouls

    def should_eject_on_technical(self, technical_fouls: int) -> bool:
        """테크니컬 파울 퇴장 판정."""
        return technical_fouls >= self._fouls.technical_foul_ejection

    def should_eject_on_unsportsmanlike(self, unsportsmanlike_fouls: int) -> bool:
        """비신사적 파울 퇴장 판정."""
        return unsportsmanlike_fouls >= self._fouls.unsportsmanlike_foul_ejection

    def get_free_throws_for_shooting_foul(
        self,
        is_three_point: bool,
        basket_made: bool,
    ) -> int:
        """
        슈팅 파울 시 자유투 수 결정.

        Args:
            is_three_point: 3점 슛 여부
            basket_made: 바스켓 성공 여부 (앤드원)

        Returns:
            자유투 수
        """
        if basket_made:
            return 1  # 앤드원
        return self._fouls.get_shooting_foul_ft(is_three_point)

    def get_timeouts_remaining(
        self,
        used: int,
        quarter: int,
        is_overtime: bool = False,
    ) -> int:
        """
        남은 타임아웃 수 계산.

        Args:
            used: 사용한 타임아웃 수
            quarter: 현재 쿼터
            is_overtime: 연장전 여부

        Returns:
            남은 타임아웃 수
        """
        total = self._timeouts.total_per_game
        if is_overtime:
            total += self._timeouts.overtime_additional
        return max(0, total - used)

    def is_half_court_violation_time(self) -> int:
        """백코트 제한시간 반환 (초)."""
        return self._game_time.backcourt_sec

    def has_defensive_three_seconds(self) -> bool:
        """수비 3초 룰 적용 여부."""
        return self._three_second.defensive_three_sec

    def has_coach_challenge(self) -> bool:
        """코치 챌린지 가능 여부."""
        return self._league_specific.coach_challenge_enabled

    def has_alternating_possession(self) -> bool:
        """교대 점유 화살표 사용 여부."""
        return self._league_specific.alternating_possession

    # === 통계 / 리셋 ===

    def get_stats(self) -> dict[str, Any]:
        """규칙 요약 통계."""
        return {
            "rule_set": self._rule_set.value,
            "quarter_duration_sec": self._game_time.quarter_duration_sec,
            "shot_clock_sec": self._game_time.shot_clock_sec,
            "max_personal_fouls": self._fouls.max_personal_fouls,
            "team_foul_bonus": self._fouls.team_foul_bonus_threshold,
            "three_point_distance_m": self._court.three_point_distance_m,
            "defensive_three_sec": self._three_second.defensive_three_sec,
            "coach_challenge": self._league_specific.coach_challenge_enabled,
            "alternating_possession": self._league_specific.alternating_possession,
        }

    def __repr__(self) -> str:
        return (
            f"FIBARules(rule_set={self._rule_set.value}, "
            f"quarter={self._game_time.quarter_duration_sec}s, "
            f"max_fouls={self._fouls.max_personal_fouls})"
        )


# =============================================================================
# Export
# =============================================================================
__all__ = [
    # 서브 규칙
    "GameTimeRules",
    "CourtDimensions",
    "FoulRules",
    "TimeoutRules",
    "ThreeSecondRules",
    "TravelingRules",
    "LeagueSpecificRules",
    # 통합 규칙
    "FIBARules",
]

__version__ = "1.0.0"
