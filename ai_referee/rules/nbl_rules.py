# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/rules
파일: nbl_rules.py
설명: NBL (호주 프로농구) Official Rules 2024-25 정의
      - FIBA 규정을 기반으로 NBL 고유 차이점만 오버라이드
      - 비디오 판독(IRS) 규칙
      - 외국인 선수(Import Player) 규정 (코트 내 최대 3명)
      - 연장전 제한 규칙 (정규시즌 최대 3회)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - NBL (Australia) Official Rules 2024-25
    - configs/ai_referee/nbl_rules.yaml
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
_NBL_RULE_SET: Final[RuleSet] = RuleSet.NBL


# =============================================================================
# NBL 전용 — 비디오 판독
# =============================================================================
@dataclass(slots=True)
class NBLVideoReviewRules:
    """
    NBL 비디오 판독 규칙.

    FIBA IRS에 4Q/OT 마지막 2분 아웃 오브 바운드 판독을 추가합니다.
    코치 챌린지는 미적용입니다.
    """

    enabled: bool = True

    # 비디오 판독 가능 상황
    situations: list[str] = field(default_factory=lambda: [
        "shot_clock_expiry",
        "end_of_period",
        "2pt_or_3pt",
        "goaltending",
        "unsportsmanlike_foul",
        "out_of_bounds_last_2_min",
    ])

    # 코치 챌린지 (NBL 미적용)
    coach_challenge: bool = False

    @classmethod
    def from_yaml(cls, cfg: dict) -> NBLVideoReviewRules:
        """YAML nbl_specific.video_review 섹션에서 생성."""
        return cls(
            enabled=cfg.get("enabled", True),
            situations=cfg.get("situations", [
                "shot_clock_expiry", "end_of_period", "2pt_or_3pt",
                "goaltending", "unsportsmanlike_foul",
                "out_of_bounds_last_2_min",
            ]),
            coach_challenge=cfg.get("coach_challenge", False),
        )

    def is_reviewable(self, situation: str) -> bool:
        """비디오 판독 가능 상황 판정."""
        return self.enabled and situation in self.situations


# =============================================================================
# NBL 전용 — 외국인 선수 규정
# =============================================================================
@dataclass(slots=True)
class ImportPlayerRules:
    """
    NBL 외국인 선수(Import Player) 규정.

    NBL은 팀당 외국인 선수(Import Player) 수를 제한합니다.
    """

    max_on_court: int = 3                     # 코트 위 최대 외국인 3명
    total_roster: int = 3                     # 로스터 내 총 외국인 3명

    @classmethod
    def from_yaml(cls, cfg: dict) -> ImportPlayerRules:
        """YAML nbl_specific.import_player 섹션에서 생성."""
        return cls(
            max_on_court=cfg.get("max_on_court", 3),
            total_roster=cfg.get("total_roster", 3),
        )

    def is_lineup_valid(self, import_count_on_court: int) -> bool:
        """코트 위 외국인 선수 수 적합 여부."""
        return import_count_on_court <= self.max_on_court


# =============================================================================
# NBL 전용 — 연장전 규칙
# =============================================================================
@dataclass(slots=True)
class NBLOvertimeRules:
    """
    NBL 연장전 규칙.

    정규시즌: 최대 3회 연장전 (이후 무승부 처리)
    플레이오프: 무제한 연장전
    """

    max_overtime_periods: int = 3             # 정규시즌 최대 연장전 수
    regular_season_only: bool = True          # 정규시즌만 제한 적용

    @classmethod
    def from_yaml(cls, cfg: dict) -> NBLOvertimeRules:
        """YAML nbl_specific.overtime_rules 섹션에서 생성."""
        return cls(
            max_overtime_periods=cfg.get("max_overtime_periods", 3),
            regular_season_only=cfg.get("regular_season_only", True),
        )

    def can_play_overtime(
        self,
        current_overtime_count: int,
        is_playoff: bool,
    ) -> bool:
        """추가 연장전 가능 여부."""
        if is_playoff or not self.regular_season_only:
            return True  # 플레이오프는 무제한
        return current_overtime_count < self.max_overtime_periods


# =============================================================================
# NBLRules — NBL 규정 통합
# =============================================================================
class NBLRules(FIBARules):
    """
    NBL (Australia) Official Rules 2024-25.

    FIBARules를 기반으로 NBL 고유 차이점을 오버라이드합니다.

    주요 차이점 (vs FIBA):
      - 비디오 판독: 4Q/OT 마지막 2분 아웃 판독 추가
      - 외국인 선수: 코트 내 최대 3명 (Import Player)
      - 연장전: 정규시즌 최대 3회 (플레이오프 무제한)
      - 나머지: FIBA 완전 준용

    YAML 설정(configs/ai_referee/nbl_rules.yaml)에서 로딩합니다.
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
        video_review: NBLVideoReviewRules | None = None,
        import_player: ImportPlayerRules | None = None,
        overtime: NBLOvertimeRules | None = None,
    ) -> None:
        # NBL은 FIBA 기본값 그대로 사용
        super().__init__(
            game_time=game_time or GameTimeRules(),
            court=court or CourtDimensions(),
            fouls=fouls or FoulRules(),
            timeouts=timeouts or TimeoutRules(),
            three_second=three_second or ThreeSecondRules(),
            traveling=traveling or TravelingRules(),
            league_specific=league_specific or LeagueSpecificRules(),
        )
        self._rule_set = _NBL_RULE_SET

        # NBL 전용 서브 규칙
        self._video_review = video_review or NBLVideoReviewRules()
        self._import_player = import_player or ImportPlayerRules()
        self._overtime = overtime or NBLOvertimeRules()

    # === NBL 전용 속성 ===

    @property
    def video_review(self) -> NBLVideoReviewRules:
        """비디오 판독 규칙."""
        return self._video_review

    @property
    def import_player(self) -> ImportPlayerRules:
        """외국인 선수(Import Player) 규정."""
        return self._import_player

    @property
    def overtime_rules(self) -> NBLOvertimeRules:
        """연장전 규칙."""
        return self._overtime

    # === 팩토리 ===

    @classmethod
    def from_yaml(cls, cfg: dict) -> NBLRules:
        """
        YAML 설정에서 NBLRules 생성.

        Args:
            cfg: nbl_rules.yaml 전체 딕셔너리

        Returns:
            NBLRules 인스턴스
        """
        nbl_specific = cfg.get("nbl_specific", {})

        return cls(
            game_time=GameTimeRules.from_yaml(cfg.get("game_time", {})),
            court=CourtDimensions.from_yaml(cfg.get("court", {})),
            fouls=FoulRules.from_yaml(cfg.get("fouls", {})),
            timeouts=TimeoutRules.from_yaml(cfg.get("timeouts", {})),
            three_second=ThreeSecondRules.from_yaml(
                nbl_specific.get("three_second_rule", {}),
            ),
            traveling=TravelingRules.from_yaml(cfg.get("traveling", {})),
            league_specific=LeagueSpecificRules.from_yaml(nbl_specific),
            video_review=NBLVideoReviewRules.from_yaml(
                nbl_specific.get("video_review", {}),
            ),
            import_player=ImportPlayerRules.from_yaml(
                nbl_specific.get("import_player", {}),
            ),
            overtime=NBLOvertimeRules.from_yaml(
                nbl_specific.get("overtime_rules", {}),
            ),
        )

    # === NBL 전용 규칙 조회 ===

    def is_video_reviewable(self, situation: str) -> bool:
        """비디오 판독 가능 상황 여부."""
        return self._video_review.is_reviewable(situation)

    def is_lineup_valid(self, import_count_on_court: int) -> bool:
        """외국인 선수 수 라인업 검증."""
        return self._import_player.is_lineup_valid(import_count_on_court)

    def can_play_overtime(
        self,
        current_overtime_count: int,
        is_playoff: bool = False,
    ) -> bool:
        """추가 연장전 가능 여부."""
        return self._overtime.can_play_overtime(current_overtime_count, is_playoff)

    # === 통계 / 표현 ===

    def get_stats(self) -> dict[str, Any]:
        """규칙 요약 통계."""
        base_stats = super().get_stats()
        base_stats.update({
            "rule_set": self._rule_set.value,
            "video_review": self._video_review.enabled,
            "import_player_max": self._import_player.max_on_court,
            "max_overtime": self._overtime.max_overtime_periods,
            "coach_challenge": False,
        })
        return base_stats

    def __repr__(self) -> str:
        return (
            f"NBLRules(rule_set={self._rule_set.value}, "
            f"quarter={self._game_time.quarter_duration_sec}s, "
            f"max_fouls={self._fouls.max_personal_fouls}, "
            f"import_max={self._import_player.max_on_court})"
        )


# =============================================================================
# Export
# =============================================================================
__all__ = [
    # NBL 전용 서브 규칙
    "NBLVideoReviewRules",
    "ImportPlayerRules",
    "NBLOvertimeRules",
    # 통합 규칙
    "NBLRules",
]

__version__ = "1.0.0"
