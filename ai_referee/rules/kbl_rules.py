# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/rules
파일: kbl_rules.py
설명: KBL (한국프로농구) 경기 운영 규칙 2024-25 정의
      - FIBA 규정을 기반으로 KBL 고유 차이점만 오버라이드
      - 비디오 판독(IRS) 규칙
      - 외국인 선수 규정 (코트 내 최대 2명)
      - TV 타임아웃 규칙

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - KBL 경기 운영 규칙 2024-25
    - configs/ai_referee/kbl_rules.yaml
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
_KBL_RULE_SET: Final[RuleSet] = RuleSet.KBL


# =============================================================================
# KBL 전용 — 비디오 판독
# =============================================================================
@dataclass(slots=True)
class KBLVideoReviewRules:
    """
    KBL 비디오 판독 (IRS) 규칙.

    KBL은 FIBA IRS에 아웃 오브 바운드 판독을 추가 적용합니다.
    코치 챌린지는 FIBA 준용(미적용)입니다.
    """

    enabled: bool = True

    # 비디오 판독 가능 상황
    situations: list[str] = field(default_factory=lambda: [
        "shot_clock_expiry",
        "end_of_period",
        "2pt_or_3pt",
        "goaltending",
        "unsportsmanlike_foul",
        "out_of_bounds",
    ])

    # 코치 챌린지 (KBL 미적용)
    coach_challenge: bool = False

    @classmethod
    def from_yaml(cls, cfg: dict) -> KBLVideoReviewRules:
        """YAML kbl_specific.video_review 섹션에서 생성."""
        return cls(
            enabled=cfg.get("enabled", True),
            situations=cfg.get("situations", [
                "shot_clock_expiry", "end_of_period", "2pt_or_3pt",
                "goaltending", "unsportsmanlike_foul", "out_of_bounds",
            ]),
            coach_challenge=cfg.get("coach_challenge", False),
        )

    def is_reviewable(self, situation: str) -> bool:
        """비디오 판독 가능 상황 판정."""
        return self.enabled and situation in self.situations


# =============================================================================
# KBL 전용 — 외국인 선수 규정
# =============================================================================
@dataclass(slots=True)
class ForeignPlayerRules:
    """
    KBL 외국인 선수 규정.

    KBL은 팀당 외국인 선수 수를 제한합니다.
    AI 심판이 라인업 검증 시 사용합니다.
    """

    max_on_court: int = 2                     # 코트 위 최대 외국인 수
    total_roster: int = 2                     # 로스터 내 총 외국인 수

    @classmethod
    def from_yaml(cls, cfg: dict) -> ForeignPlayerRules:
        """YAML kbl_specific.foreign_player 섹션에서 생성."""
        return cls(
            max_on_court=cfg.get("max_on_court", 2),
            total_roster=cfg.get("total_roster", 2),
        )

    def is_lineup_valid(self, foreign_count_on_court: int) -> bool:
        """코트 위 외국인 선수 수 적합 여부."""
        return foreign_count_on_court <= self.max_on_court


# =============================================================================
# KBL 전용 — 교체 규칙
# =============================================================================
@dataclass(slots=True)
class KBLSubstitutionRules:
    """
    KBL 교체 규칙.

    데드볼 시에만 교체 가능, 자유 교체 불가.
    """

    dead_ball_only: bool = True               # 데드볼 시에만 교체
    free_substitution: bool = False           # 자유 교체 불가

    @classmethod
    def from_yaml(cls, cfg: dict) -> KBLSubstitutionRules:
        """YAML kbl_specific.substitution 섹션에서 생성."""
        return cls(
            dead_ball_only=cfg.get("dead_ball_only", True),
            free_substitution=cfg.get("free_substitution", False),
        )


# =============================================================================
# KBL 전용 — 타임아웃 확장
# =============================================================================
@dataclass(slots=True)
class KBLTimeoutRules(TimeoutRules):
    """
    KBL 타임아웃 규칙 (FIBA 확장).

    KBL 고유: TV 타임아웃 존재.
    """

    tv_timeout: bool = True                   # TV 타임아웃 적용

    @classmethod
    def from_yaml(cls, cfg: dict) -> KBLTimeoutRules:
        """YAML timeouts 섹션에서 생성."""
        return cls(
            total_per_game=cfg.get("total_per_game", 5),
            first_half_max=cfg.get("first_half_max", 2),
            second_half_max=cfg.get("second_half_max", 3),
            overtime_additional=cfg.get("overtime_additional", 1),
            duration_sec=cfg.get("duration_sec", 60),
            carryover=cfg.get("carryover", False),
            tv_timeout=cfg.get("tv_timeout", True),
        )


# =============================================================================
# KBLRules — KBL 규정 통합
# =============================================================================
class KBLRules(FIBARules):
    """
    KBL 경기 운영 규칙 2024-25.

    FIBARules를 기반으로 KBL 고유 차이점을 오버라이드합니다.

    주요 차이점 (vs FIBA):
      - 비디오 판독: 아웃 오브 바운드 추가 항목
      - 외국인 선수: 코트 내 최대 2명 제한
      - TV 타임아웃: 적용
      - 나머지: FIBA 완전 준용

    YAML 설정(configs/ai_referee/kbl_rules.yaml)에서 로딩합니다.
    """

    def __init__(
        self,
        *,
        game_time: GameTimeRules | None = None,
        court: CourtDimensions | None = None,
        fouls: FoulRules | None = None,
        timeouts: KBLTimeoutRules | None = None,
        three_second: ThreeSecondRules | None = None,
        traveling: TravelingRules | None = None,
        league_specific: LeagueSpecificRules | None = None,
        video_review: KBLVideoReviewRules | None = None,
        foreign_player: ForeignPlayerRules | None = None,
        substitution: KBLSubstitutionRules | None = None,
    ) -> None:
        # KBL은 FIBA 기본값 그대로 사용
        super().__init__(
            game_time=game_time or GameTimeRules(),
            court=court or CourtDimensions(),
            fouls=fouls or FoulRules(),
            timeouts=timeouts or KBLTimeoutRules(),
            three_second=three_second or ThreeSecondRules(),
            traveling=traveling or TravelingRules(),
            league_specific=league_specific or LeagueSpecificRules(),
        )
        self._rule_set = _KBL_RULE_SET

        # KBL 전용 서브 규칙
        self._video_review = video_review or KBLVideoReviewRules()
        self._foreign_player = foreign_player or ForeignPlayerRules()
        self._substitution = substitution or KBLSubstitutionRules()

    # === KBL 전용 속성 ===

    @property
    def video_review(self) -> KBLVideoReviewRules:
        """비디오 판독 규칙."""
        return self._video_review

    @property
    def foreign_player(self) -> ForeignPlayerRules:
        """외국인 선수 규정."""
        return self._foreign_player

    @property
    def substitution(self) -> KBLSubstitutionRules:
        """교체 규칙."""
        return self._substitution

    # === 팩토리 ===

    @classmethod
    def from_yaml(cls, cfg: dict) -> KBLRules:
        """
        YAML 설정에서 KBLRules 생성.

        Args:
            cfg: kbl_rules.yaml 전체 딕셔너리

        Returns:
            KBLRules 인스턴스
        """
        kbl_specific = cfg.get("kbl_specific", {})

        return cls(
            game_time=GameTimeRules.from_yaml(cfg.get("game_time", {})),
            court=CourtDimensions.from_yaml(cfg.get("court", {})),
            fouls=FoulRules.from_yaml(cfg.get("fouls", {})),
            timeouts=KBLTimeoutRules.from_yaml(cfg.get("timeouts", {})),
            three_second=ThreeSecondRules.from_yaml(
                kbl_specific.get("three_second_rule", {}),
            ),
            traveling=TravelingRules.from_yaml(cfg.get("traveling", {})),
            league_specific=LeagueSpecificRules.from_yaml(kbl_specific),
            video_review=KBLVideoReviewRules.from_yaml(
                kbl_specific.get("video_review", {}),
            ),
            foreign_player=ForeignPlayerRules.from_yaml(
                kbl_specific.get("foreign_player", {}),
            ),
            substitution=KBLSubstitutionRules.from_yaml(
                kbl_specific.get("substitution", {}),
            ),
        )

    # === KBL 전용 규칙 조회 ===

    def is_video_reviewable(self, situation: str) -> bool:
        """비디오 판독 가능 상황 여부."""
        return self._video_review.is_reviewable(situation)

    def is_lineup_valid(self, foreign_count_on_court: int) -> bool:
        """외국인 선수 수 라인업 검증."""
        return self._foreign_player.is_lineup_valid(foreign_count_on_court)

    def can_substitute(self, is_dead_ball: bool) -> bool:
        """교체 가능 여부."""
        if self._substitution.free_substitution:
            return True
        return is_dead_ball if self._substitution.dead_ball_only else True

    def has_tv_timeout(self) -> bool:
        """TV 타임아웃 적용 여부."""
        timeouts = self._timeouts
        if isinstance(timeouts, KBLTimeoutRules):
            return timeouts.tv_timeout
        return False

    # === 통계 / 표현 ===

    def get_stats(self) -> dict[str, Any]:
        """규칙 요약 통계."""
        base_stats = super().get_stats()
        base_stats.update({
            "rule_set": self._rule_set.value,
            "video_review": self._video_review.enabled,
            "foreign_player_max": self._foreign_player.max_on_court,
            "tv_timeout": self.has_tv_timeout(),
            "coach_challenge": False,
        })
        return base_stats

    def __repr__(self) -> str:
        return (
            f"KBLRules(rule_set={self._rule_set.value}, "
            f"quarter={self._game_time.quarter_duration_sec}s, "
            f"max_fouls={self._fouls.max_personal_fouls}, "
            f"foreign_max={self._foreign_player.max_on_court})"
        )


# =============================================================================
# Export
# =============================================================================
__all__ = [
    # KBL 전용 서브 규칙
    "KBLVideoReviewRules",
    "ForeignPlayerRules",
    "KBLSubstitutionRules",
    "KBLTimeoutRules",
    # 통합 규칙
    "KBLRules",
]

__version__ = "1.0.0"
