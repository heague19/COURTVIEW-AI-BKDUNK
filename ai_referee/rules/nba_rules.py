# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/rules
파일: nba_rules.py
설명: NBA Official Rulebook 2024-25 규정 정의
      - FIBA 규정을 기반으로 NBA 고유 차이점만 오버라이드
      - 12분 쿼터, 개인파울 6개, 수비 3초, 코치 챌린지
      - 플래그런트 파울 1/2, 클리어 패스 파울, 전환 테이크 파울
      - 리플레이 센터, TV 타임아웃, 어드밴스 볼 규칙

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - NBA Official Rulebook 2024-25
    - configs/ai_referee/nba_rules.yaml
    - ai_referee/rules/fiba_rules.py (기반 클래스)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Final

from shared.constants.referee_rule_constants import RuleSet

from ai_referee.rules.fiba_rules import (
    CourtDimensions,
    FIBARules,
    FoulRules,
    GameTimeRules,
    LeagueSpecificRules,
    ThreeSecondRules,
    TimeoutRules,
    TravelingRules,
)

logger: Final = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================
_NBA_RULE_SET: Final[RuleSet] = RuleSet.NBA


# =============================================================================
# NBA 전용 — 플래그런트 파울
# =============================================================================
@dataclass(slots=True)
class FlagrantFoulRules:
    """
    NBA 플래그런트 파울 규칙.

    FIBA의 비신사적 파울(Unsportsmanlike)에 대응하는 NBA 전용 규칙입니다.
    Flagrant 1: 불필요한 접촉 (Unnecessary Contact)
    Flagrant 2: 불필요하고 과도한 접촉 (Unnecessary and Excessive)
    """

    # Flagrant 1
    flagrant_1_free_throws: int = 2           # FT 2구 + 점유 유지
    flagrant_1_possession_retained: bool = True
    flagrant_1_ejection: bool = False

    # Flagrant 2
    flagrant_2_free_throws: int = 2           # FT 2구 + 점유 유지 + 퇴장
    flagrant_2_possession_retained: bool = True
    flagrant_2_ejection: bool = True

    # 누적 퇴장 (포인트 시스템)
    flagrant_point_limit: int = 2             # 플래그런트 포인트 2점 → 퇴장
    flagrant_1_points: int = 1                # F1 = 1포인트
    flagrant_2_points: int = 2                # F2 = 2포인트 (즉시 퇴장)

    @classmethod
    def from_yaml(cls, cfg: dict) -> FlagrantFoulRules:
        """YAML nba_specific.flagrant_fouls 섹션에서 생성."""
        f1 = cfg.get("flagrant_1", {})
        f2 = cfg.get("flagrant_2", {})
        return cls(
            flagrant_1_free_throws=f1.get("free_throws", 2),
            flagrant_1_possession_retained=f1.get("possession_retained", True),
            flagrant_1_ejection=f1.get("ejection", False),
            flagrant_2_free_throws=f2.get("free_throws", 2),
            flagrant_2_possession_retained=f2.get("possession_retained", True),
            flagrant_2_ejection=f2.get("ejection", True),
        )

    def should_eject_on_flagrant_points(self, flagrant_points: int) -> bool:
        """플래그런트 포인트 기반 퇴장 판정."""
        return flagrant_points >= self.flagrant_point_limit

    def get_free_throws(self, is_flagrant_2: bool) -> int:
        """플래그런트 종류별 자유투 수."""
        return self.flagrant_2_free_throws if is_flagrant_2 else self.flagrant_1_free_throws

    def is_ejection(self, is_flagrant_2: bool) -> bool:
        """플래그런트 종류별 퇴장 여부."""
        return self.flagrant_2_ejection if is_flagrant_2 else self.flagrant_1_ejection


# =============================================================================
# NBA 전용 — 코치 챌린지
# =============================================================================
@dataclass(slots=True)
class CoachChallengeRules:
    """
    NBA 코치 챌린지 규칙.

    2019-20 시즌부터 도입된 코치의 판정 이의 시스템입니다.
    """

    enabled: bool = True
    challenges_per_game: int = 1
    successful_challenge_retain: bool = True   # 성공 시 챌린지 유지 (2024-25 시즌)

    # 챌린지 가능 판정 유형
    reviewable_plays: list[str] = field(default_factory=lambda: [
        "personal_foul",
        "offensive_foul",
        "out_of_bounds",
        "goaltending",
    ])

    @classmethod
    def from_yaml(cls, cfg: dict) -> CoachChallengeRules:
        """YAML nba_specific.coach_challenge 섹션에서 생성."""
        return cls(
            enabled=cfg.get("enabled", True),
            challenges_per_game=cfg.get("challenges_per_game", 1),
            successful_challenge_retain=cfg.get("successful_challenge_retain", True),
            reviewable_plays=cfg.get("reviewable_plays", [
                "personal_foul", "offensive_foul",
                "out_of_bounds", "goaltending",
            ]),
        )

    def can_challenge(self, remaining_challenges: int, play_type: str) -> bool:
        """챌린지 가능 여부 판정."""
        return (
            self.enabled
            and remaining_challenges > 0
            and play_type in self.reviewable_plays
        )


# =============================================================================
# NBA 전용 — 클리어 패스 파울
# =============================================================================
@dataclass(slots=True)
class ClearPathFoulRules:
    """
    NBA 클리어 패스 파울 규칙.

    속공 기회에서 수비수가 공격수와 바스켓 사이에 없을 때
    발생하는 파울에 대한 규칙입니다.
    """

    enabled: bool = True
    free_throws: int = 2                      # 2구 + 점유 유지
    possession_retained: bool = True

    # 클리어 패스 판정 기준
    criteria: list[str] = field(default_factory=lambda: [
        "no_defender_between_ball_and_basket",
        "fast_break_opportunity",
    ])

    @classmethod
    def from_yaml(cls, cfg: dict) -> ClearPathFoulRules:
        """YAML nba_specific.clear_path_foul 섹션에서 생성."""
        return cls(
            enabled=cfg.get("enabled", True),
            free_throws=cfg.get("free_throws", 2),
            possession_retained=cfg.get("possession_retained", True),
            criteria=cfg.get("criteria", [
                "no_defender_between_ball_and_basket",
                "fast_break_opportunity",
            ]),
        )


# =============================================================================
# NBA 전용 — 전환 테이크 파울
# =============================================================================
@dataclass(slots=True)
class TransitionTakeFoulRules:
    """
    NBA 전환 테이크 파울 규칙 (2022-23~).

    전환 공격 중 의도적으로 파울을 범하여 속공을 저지하는
    행위에 대한 페널티 규칙입니다.
    """

    enabled: bool = True
    free_throw_awarded: int = 1               # FT 1구 + 점유 유지
    possession_retained: bool = True

    # 전환 판정 기준
    transition_window_sec: float = 7.0        # 전환 공격 판정 시간
    half_court_threshold: float = 0.5         # 하프코트 기준 비율

    @classmethod
    def from_yaml(cls, cfg: dict) -> TransitionTakeFoulRules:
        """YAML nba_specific.transition_take_foul 섹션에서 생성."""
        return cls(
            enabled=cfg.get("enabled", True),
            free_throw_awarded=cfg.get("free_throw_awarded", 1),
            possession_retained=cfg.get("possession_retained", True),
            transition_window_sec=cfg.get("transition_window_sec", 7.0),
            half_court_threshold=cfg.get("half_court_threshold", 0.5),
        )


# =============================================================================
# NBA 전용 — 리플레이 센터
# =============================================================================
@dataclass(slots=True)
class ReplayCenterRules:
    """
    NBA 리플레이 센터 규칙.

    Secaucus, NJ의 NBA 리플레이 센터에서 원격 비디오 판독을
    수행하는 규칙입니다.
    """

    enabled: bool = True

    # 자동 트리거 상황
    automatic_triggers: list[str] = field(default_factory=lambda: [
        "last_2_minutes_4q",
        "overtime",
        "flagrant_foul_review",
        "out_of_bounds_last_2_min",
    ])

    @classmethod
    def from_yaml(cls, cfg: dict) -> ReplayCenterRules:
        """YAML nba_specific.replay_center 섹션에서 생성."""
        return cls(
            enabled=cfg.get("enabled", True),
            automatic_triggers=cfg.get("automatic_triggers", [
                "last_2_minutes_4q", "overtime",
                "flagrant_foul_review", "out_of_bounds_last_2_min",
            ]),
        )

    def is_automatic_review(self, situation: str) -> bool:
        """자동 리플레이 트리거 상황 판정."""
        return situation in self.automatic_triggers


# =============================================================================
# NBA 전용 — 타임아웃 확장 규칙
# =============================================================================
@dataclass(slots=True)
class NBATimeoutRules(TimeoutRules):
    """
    NBA 타임아웃 규칙 (FIBA 확장).

    NBA 고유: TV 강제 타임아웃, 어드밴스 볼 규칙.
    """

    # NBA 기본값 오버라이드 (FIBA 5 → NBA 7)
    total_per_game: int = 7
    first_half_max: int = 4
    second_half_max: int = 3
    overtime_additional: int = 2
    duration_sec: int = 75

    mandatory_tv_timeouts: bool = True        # TV 강제 타임아웃
    advance_ball_timeout: bool = True         # 타임아웃 후 프론트코트 진출

    @classmethod
    def from_yaml(cls, cfg: dict) -> NBATimeoutRules:
        """YAML timeouts 섹션에서 생성."""
        return cls(
            total_per_game=cfg.get("total_per_game", 7),
            first_half_max=cfg.get("first_half_max", 4),
            second_half_max=cfg.get("second_half_max", 3),
            overtime_additional=cfg.get("overtime_additional", 2),
            duration_sec=cfg.get("duration_sec", 75),
            carryover=cfg.get("carryover", False),
            mandatory_tv_timeouts=cfg.get("mandatory_tv_timeouts", True),
            advance_ball_timeout=cfg.get("advance_ball_timeout", True),
        )


# =============================================================================
# NBARules — NBA 규정 통합
# =============================================================================
class NBARules(FIBARules):
    """
    NBA Official Rulebook 2024-25.

    FIBARules를 기반으로 NBA 고유 차이점을 오버라이드합니다.

    주요 차이점 (vs FIBA):
      - 경기 시간: 12분 × 4쿼터 (FIBA: 10분)
      - 개인 파울: 6개 퇴장 (FIBA: 5개)
      - 수비 3초: 적용 (FIBA: 미적용)
      - 트래블링: 제로 스텝 적용, 더 관대한 해석
      - 타임아웃: 7개, 75초, TV 강제, 어드밴스 볼
      - 코치 챌린지: 경기당 1회
      - 플래그런트 파울: F1(불필요) / F2(과도) — FIBA 비신사적 대응
      - 클리어 패스 파울: 속공 파울 → FT 2구 + 점유
      - 전환 테이크 파울: 전환 파울 → FT 1구 + 점유
      - 리플레이 센터: Secaucus 원격 판독
      - 점프볼: 교대 점유 화살표 미사용

    YAML 설정(configs/ai_referee/nba_rules.yaml)에서 로딩합니다.
    """

    def __init__(
        self,
        *,
        game_time: GameTimeRules | None = None,
        court: CourtDimensions | None = None,
        fouls: FoulRules | None = None,
        timeouts: NBATimeoutRules | None = None,
        three_second: ThreeSecondRules | None = None,
        traveling: TravelingRules | None = None,
        league_specific: LeagueSpecificRules | None = None,
        flagrant: FlagrantFoulRules | None = None,
        coach_challenge: CoachChallengeRules | None = None,
        clear_path: ClearPathFoulRules | None = None,
        transition_take_foul: TransitionTakeFoulRules | None = None,
        replay_center: ReplayCenterRules | None = None,
    ) -> None:
        # NBA 기본값으로 FIBA 오버라이드
        super().__init__(
            game_time=game_time or GameTimeRules(
                quarter_duration_sec=720,
                free_throw_sec=10,
                period_break_sec=130,
            ),
            court=court or CourtDimensions(
                three_point_distance_m=7.24,
                three_point_corner_m=6.71,
                restricted_area_arc_m=1.22,
            ),
            fouls=fouls or FoulRules(max_personal_fouls=6),
            timeouts=timeouts or NBATimeoutRules(),
            three_second=three_second or ThreeSecondRules(
                offensive_three_sec=True,
                defensive_three_sec=True,
            ),
            traveling=traveling or TravelingRules(
                zero_step_enabled=True,
                pivot_slide_threshold_m=0.20,
            ),
            league_specific=league_specific or LeagueSpecificRules(
                alternating_possession=False,
                coach_challenge_enabled=True,
                challenges_per_game=1,
                clear_path_foul_enabled=True,
                clear_path_free_throws=2,
                transition_take_foul_enabled=True,
            ),
        )
        self._rule_set = _NBA_RULE_SET

        # NBA 전용 서브 규칙
        self._flagrant = flagrant or FlagrantFoulRules()
        self._coach_challenge = coach_challenge or CoachChallengeRules()
        self._clear_path = clear_path or ClearPathFoulRules()
        self._transition_take_foul = transition_take_foul or TransitionTakeFoulRules()
        self._replay_center = replay_center or ReplayCenterRules()

    # === NBA 전용 속성 ===

    @property
    def flagrant(self) -> FlagrantFoulRules:
        """플래그런트 파울 규칙."""
        return self._flagrant

    @property
    def coach_challenge(self) -> CoachChallengeRules:
        """코치 챌린지 규칙."""
        return self._coach_challenge

    @property
    def clear_path(self) -> ClearPathFoulRules:
        """클리어 패스 파울 규칙."""
        return self._clear_path

    @property
    def transition_take_foul(self) -> TransitionTakeFoulRules:
        """전환 테이크 파울 규칙."""
        return self._transition_take_foul

    @property
    def replay_center(self) -> ReplayCenterRules:
        """리플레이 센터 규칙."""
        return self._replay_center

    # === 팩토리 ===

    @classmethod
    def from_yaml(cls, cfg: dict) -> NBARules:
        """
        YAML 설정에서 NBARules 생성.

        Args:
            cfg: nba_rules.yaml 전체 딕셔너리

        Returns:
            NBARules 인스턴스
        """
        nba_specific = cfg.get("nba_specific", {})

        return cls(
            game_time=GameTimeRules.from_yaml(cfg.get("game_time", {})),
            court=CourtDimensions.from_yaml(cfg.get("court", {})),
            fouls=FoulRules.from_yaml(cfg.get("fouls", {})),
            timeouts=NBATimeoutRules.from_yaml(cfg.get("timeouts", {})),
            three_second=ThreeSecondRules.from_yaml(
                cfg.get("three_second_rule", {}),
            ),
            traveling=TravelingRules.from_yaml(cfg.get("traveling", {})),
            league_specific=LeagueSpecificRules.from_yaml(nba_specific),
            flagrant=FlagrantFoulRules.from_yaml(
                nba_specific.get("flagrant_fouls", {}),
            ),
            coach_challenge=CoachChallengeRules.from_yaml(
                nba_specific.get("coach_challenge", {}),
            ),
            clear_path=ClearPathFoulRules.from_yaml(
                nba_specific.get("clear_path_foul", {}),
            ),
            transition_take_foul=TransitionTakeFoulRules.from_yaml(
                nba_specific.get("transition_take_foul", {}),
            ),
            replay_center=ReplayCenterRules.from_yaml(
                nba_specific.get("replay_center", {}),
            ),
        )

    # === NBA 전용 규칙 조회 ===

    def get_flagrant_free_throws(self, is_flagrant_2: bool) -> int:
        """플래그런트 파울 자유투 수."""
        return self._flagrant.get_free_throws(is_flagrant_2)

    def should_eject_on_flagrant(
        self,
        is_flagrant_2: bool,
        total_flagrant_points: int,
    ) -> bool:
        """
        플래그런트 파울 퇴장 판정.

        Args:
            is_flagrant_2: F2 여부 (F2는 즉시 퇴장)
            total_flagrant_points: 누적 플래그런트 포인트

        Returns:
            퇴장 여부
        """
        if is_flagrant_2:
            return True
        return self._flagrant.should_eject_on_flagrant_points(total_flagrant_points)

    def can_coach_challenge(
        self,
        remaining_challenges: int,
        play_type: str,
    ) -> bool:
        """
        코치 챌린지 가능 여부 판정.

        Args:
            remaining_challenges: 남은 챌린지 횟수
            play_type: 판정 유형 (personal_foul, out_of_bounds 등)

        Returns:
            챌린지 가능 여부
        """
        return self._coach_challenge.can_challenge(remaining_challenges, play_type)

    def is_clear_path_applicable(self) -> bool:
        """클리어 패스 파울 적용 가능 여부."""
        return self._clear_path.enabled

    def get_clear_path_penalty(self) -> tuple[int, bool]:
        """클리어 패스 파울 페널티 (자유투 수, 점유 유지 여부)."""
        return (self._clear_path.free_throws, self._clear_path.possession_retained)

    def is_transition_take_foul_applicable(self) -> bool:
        """전환 테이크 파울 적용 가능 여부."""
        return self._transition_take_foul.enabled

    def get_transition_take_foul_penalty(self) -> tuple[int, bool]:
        """전환 테이크 파울 페널티 (자유투 수, 점유 유지 여부)."""
        return (
            self._transition_take_foul.free_throw_awarded,
            self._transition_take_foul.possession_retained,
        )

    def is_automatic_replay_situation(self, situation: str) -> bool:
        """자동 리플레이 트리거 상황 여부."""
        return self._replay_center.is_automatic_review(situation)

    def has_advance_ball_timeout(self) -> bool:
        """타임아웃 후 프론트코트 진출 가능 여부."""
        timeouts = self._timeouts
        if isinstance(timeouts, NBATimeoutRules):
            return timeouts.advance_ball_timeout
        return False

    def has_mandatory_tv_timeouts(self) -> bool:
        """TV 강제 타임아웃 적용 여부."""
        timeouts = self._timeouts
        if isinstance(timeouts, NBATimeoutRules):
            return timeouts.mandatory_tv_timeouts
        return False

    def get_defensive_three_second_penalty(self) -> tuple[int, bool]:
        """
        수비 3초 위반 페널티.

        Returns:
            (자유투 수, 점유 유지 여부) — 테크니컬 FT 1구 + 공격팀 점유
        """
        return (1, True)

    # === 타임아웃 조회 오버라이드 ===

    def get_timeouts_remaining(
        self,
        used: int,
        quarter: int,
        is_overtime: bool = False,
    ) -> int:
        """
        남은 타임아웃 수 계산 (NBA 규칙).

        NBA: 경기당 7개 + 연장전 추가 2개.
        4쿼터 마지막 3분에 최소 2개 남아야 하는 강제 규칙 미적용 (소프트웨어 레벨).

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

    # === 통계 / 표현 ===

    def get_stats(self) -> dict[str, Any]:
        """규칙 요약 통계."""
        base_stats = super().get_stats()
        base_stats.update({
            "rule_set": self._rule_set.value,
            "flagrant_enabled": True,
            "coach_challenge": self._coach_challenge.enabled,
            "clear_path_foul": self._clear_path.enabled,
            "transition_take_foul": self._transition_take_foul.enabled,
            "replay_center": self._replay_center.enabled,
            "advance_ball_timeout": self.has_advance_ball_timeout(),
            "mandatory_tv_timeouts": self.has_mandatory_tv_timeouts(),
        })
        return base_stats

    def __repr__(self) -> str:
        return (
            f"NBARules(rule_set={self._rule_set.value}, "
            f"quarter={self._game_time.quarter_duration_sec}s, "
            f"max_fouls={self._fouls.max_personal_fouls}, "
            f"defensive_3sec={self._three_second.defensive_three_sec})"
        )


# =============================================================================
# Export
# =============================================================================
__all__ = [
    # NBA 전용 서브 규칙
    "FlagrantFoulRules",
    "CoachChallengeRules",
    "ClearPathFoulRules",
    "TransitionTakeFoulRules",
    "ReplayCenterRules",
    "NBATimeoutRules",
    # 통합 규칙
    "NBARules",
]

__version__ = "1.0.0"
