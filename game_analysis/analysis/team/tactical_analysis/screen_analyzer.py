# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/tactical_analysis
파일: screen_analyzer.py
설명: 픽앤롤(PnR) / 볼스크린 전술 분석기
      - 스크리너/핸들러/롤맨 역할 식별
      - PnR PPP(Points Per Possession) 산출
      - 수비 대응 분류 (drop/hedge/switch/ice/blitz/trap/show_and_recover)
      - 롤맨 다이브 vs 팝아웃 효율 비교

      학술 근거:
        Lamas et al. (2011) — 세트 플레이 분류 프레임워크
        NBA Second Spectrum — PnR 수비 커버리지 분류

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/tactical_analysis.yaml (pick_and_roll 섹션)
의존성: shared/constants/tactical_constants.py, shared/dto/tactical_dto.py
소비자: coaching_intelligence, pre_game, report_generation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    SCREEN_CONTACT_DISTANCE_M,
    SCREEN_ANGLE_MIN_DEG,
    SCREEN_ANGLE_MAX_DEG,
    SCREEN_HOLD_TIME_MIN_SEC,
    SCREEN_HOLD_TIME_MAX_SEC,
    ROLL_MAN_DIVE_SPEED_MIN,
    POP_OUT_DISTANCE_MIN_M,
    PNR_DEFENSE_REACTION_TIME_SEC,
    HAND_OFF_PROXIMITY_M,
)
from shared.dto.tactical_dto import (
    PickAndRollAnalysis,
)

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 열거형
# =============================================================================
@unique
class PnRCoverageType(str, Enum):
    """PnR 수비 대응 유형 (7종)."""

    DROP = "drop"                       # 빅맨 후퇴
    HEDGE = "hedge"                     # 빅맨 전진 (일시)
    SWITCH = "switch"                   # 매치업 교환
    ICE = "ice"                         # 한쪽 방향 강제
    BLITZ = "blitz"                     # 더블팀
    TRAP = "trap"                       # 하프코트 트랩
    SHOW_AND_RECOVER = "show_and_recover"  # 쇼앤리커버

    def __str__(self) -> str:
        return self.value


@unique
class PnRActionType(str, Enum):
    """PnR 후 액션 유형."""

    ROLL = "roll"              # 롤맨 다이브
    POP = "pop"                # 팝아웃 (3점 라인)
    SLIP = "slip"              # 슬립 스크린
    HAND_OFF = "hand_off"      # 드리블 핸드오프
    REJECT = "reject"          # 스크린 거부

    def __str__(self) -> str:
        return self.value


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ScreenAnalyzerConfig:
    """스크린 분석기 설정."""

    # 스크린 감지 파라미터
    contact_distance_m: float = SCREEN_CONTACT_DISTANCE_M
    angle_min_deg: float = SCREEN_ANGLE_MIN_DEG
    angle_max_deg: float = SCREEN_ANGLE_MAX_DEG
    hold_time_min_sec: float = SCREEN_HOLD_TIME_MIN_SEC
    hold_time_max_sec: float = SCREEN_HOLD_TIME_MAX_SEC

    # 롤맨/팝 분류
    roll_dive_speed_min_ms: float = ROLL_MAN_DIVE_SPEED_MIN
    pop_out_distance_min_m: float = POP_OUT_DISTANCE_MIN_M

    # 수비 반응
    defense_reaction_time_sec: float = PNR_DEFENSE_REACTION_TIME_SEC

    # 핸드오프
    hand_off_proximity_m: float = HAND_OFF_PROXIMITY_M

    # 최소 신뢰도
    min_confidence: float = 0.60

    @classmethod
    def from_yaml(cls, cfg: dict) -> ScreenAnalyzerConfig:
        """YAML 설정으로부터 생성.

        NOTE: `@dataclass(slots=True)`에서는 `cls.field` 접근이 슬롯 디스크립터를
        반환하므로 모듈 상수를 직접 기본값으로 사용한다 (S8 수정).
        """
        pnr = cfg.get("pick_and_roll", {})
        screen = pnr.get("screen", {})
        after = pnr.get("after_screen", {})
        defense = pnr.get("defense_reaction", {})
        hand_off = pnr.get("hand_off", {})

        return cls(
            contact_distance_m=float(screen.get("contact_distance_m", SCREEN_CONTACT_DISTANCE_M)),
            angle_min_deg=float(screen.get("angle_min_deg", SCREEN_ANGLE_MIN_DEG)),
            angle_max_deg=float(screen.get("angle_max_deg", SCREEN_ANGLE_MAX_DEG)),
            hold_time_min_sec=float(screen.get("hold_time_min_sec", SCREEN_HOLD_TIME_MIN_SEC)),
            hold_time_max_sec=float(screen.get("hold_time_max_sec", SCREEN_HOLD_TIME_MAX_SEC)),
            roll_dive_speed_min_ms=float(after.get("roll_man_dive_speed_min_ms", ROLL_MAN_DIVE_SPEED_MIN)),
            pop_out_distance_min_m=float(after.get("pop_out_distance_min_m", POP_OUT_DISTANCE_MIN_M)),
            defense_reaction_time_sec=float(defense.get("reaction_time_sec", PNR_DEFENSE_REACTION_TIME_SEC)),
            hand_off_proximity_m=float(hand_off.get("proximity_m", HAND_OFF_PROXIMITY_M)),
        )


# =============================================================================
# 입력 데이터
# =============================================================================
@dataclass(slots=True)
class PnREventInput:
    """PnR 이벤트 입력 데이터."""

    team_id: str
    possession_id: str = ""
    # 역할 선수
    screener_id: int = 0
    handler_id: int = 0
    # 스크린 파라미터
    screen_distance_m: float = 0.0
    screen_angle_deg: float = 0.0
    screen_hold_sec: float = 0.0
    # 스크린 후 액션
    action_type: PnRActionType = PnRActionType.ROLL
    roll_speed_ms: float = 0.0
    pop_distance_m: float = 0.0
    # 수비 대응
    defense_coverage: PnRCoverageType = PnRCoverageType.DROP
    defense_reaction_sec: float = 0.0
    # 결과
    points_scored: int = 0
    resulted_in_shot: bool = False
    shot_made: bool = False
    resulted_in_turnover: bool = False
    # 신뢰도
    confidence: float = 0.85
    timestamp: float = 0.0


# =============================================================================
# 내부 누적기
# =============================================================================
@dataclass(slots=True)
class _PnRAccumulator:
    """팀별 PnR 누적 데이터."""

    total_pnr: int = 0
    total_points: int = 0
    total_possessions_with_shot: int = 0
    # 핸들러
    handler_points: int = 0
    handler_shots: int = 0
    handler_makes: int = 0
    # 롤맨
    roller_points: int = 0
    roller_shots: int = 0
    roller_makes: int = 0
    # 팝
    pop_points: int = 0
    pop_shots: int = 0
    pop_makes: int = 0
    # 수비 대응 횟수
    defense_counts: dict[str, int] = field(default_factory=dict)
    # 액션별 PPP
    action_points: dict[str, int] = field(default_factory=dict)
    action_possessions: dict[str, int] = field(default_factory=dict)


# =============================================================================
# 스크린 분석기
# =============================================================================
class ScreenAnalyzer:
    """
    픽앤롤/볼스크린 전술 분석기.

    POSSESSION cadence (<100ms).
    점유 종료 시 PnR 이벤트를 처리하여 누적 통계 산출.
    """

    def __init__(self, config: ScreenAnalyzerConfig | None = None) -> None:
        self._config = config or ScreenAnalyzerConfig()
        self._lock = RLock()
        self._teams: dict[str, _PnRAccumulator] = {}
        self._event_history: list[PnREventInput] = []
        self._name = "ScreenAnalyzer"

    # --- 속성 ---
    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> ScreenAnalyzerConfig:
        return self._config

    # --- 핵심 메서드 ---
    def process_pnr_event(self, event: PnREventInput) -> bool:
        """
        PnR 이벤트 처리.

        Returns:
            유효 이벤트면 True
        """
        if event.confidence < self._config.min_confidence:
            return False

        with self._lock:
            acc = self._teams.setdefault(event.team_id, _PnRAccumulator())
            acc.total_pnr += 1

            # 점수 누적
            if event.points_scored > 0:
                acc.total_points += event.points_scored

            if event.resulted_in_shot:
                acc.total_possessions_with_shot += 1

            # 액션별 분류
            action_key = event.action_type.value
            acc.action_points[action_key] = acc.action_points.get(action_key, 0) + event.points_scored
            acc.action_possessions[action_key] = acc.action_possessions.get(action_key, 0) + 1

            # 롤/팝 상세
            if event.action_type == PnRActionType.ROLL:
                acc.roller_points += event.points_scored
                if event.resulted_in_shot:
                    acc.roller_shots += 1
                    if event.shot_made:
                        acc.roller_makes += 1
            elif event.action_type == PnRActionType.POP:
                acc.pop_points += event.points_scored
                if event.resulted_in_shot:
                    acc.pop_shots += 1
                    if event.shot_made:
                        acc.pop_makes += 1
            else:
                # 핸들러 액션 (slip/hand_off/reject)
                acc.handler_points += event.points_scored
                if event.resulted_in_shot:
                    acc.handler_shots += 1
                    if event.shot_made:
                        acc.handler_makes += 1

            # 수비 대응 집계
            cov_key = event.defense_coverage.value
            acc.defense_counts[cov_key] = acc.defense_counts.get(cov_key, 0) + 1

            # 이벤트 히스토리 (메모리 가드)
            self._event_history.append(event)
            if len(self._event_history) > _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

            return True

    def validate_screen(self, distance_m: float, angle_deg: float, hold_sec: float) -> bool:
        """스크린 유효성 검증."""
        if distance_m > self._config.contact_distance_m:
            return False
        if not (self._config.angle_min_deg <= angle_deg <= self._config.angle_max_deg):
            return False
        if hold_sec < self._config.hold_time_min_sec:
            return False
        return True

    def classify_action(self, roll_speed_ms: float, pop_distance_m: float) -> PnRActionType:
        """스크린 후 액션 분류 (롤 vs 팝)."""
        if roll_speed_ms >= self._config.roll_dive_speed_min_ms:
            return PnRActionType.ROLL
        if pop_distance_m >= self._config.pop_out_distance_min_m:
            return PnRActionType.POP
        # 기본값: 속도/거리 모두 낮으면 핸드오프
        return PnRActionType.HAND_OFF

    def is_illegal_screen(self, hold_sec: float) -> bool:
        """불법 스크린 경고 판정."""
        return hold_sec > self._config.hold_time_max_sec

    # --- 조회 ---
    def get_team_pnr_analysis(self, team_id: str) -> PickAndRollAnalysis:
        """팀별 PnR 분석 결과 (DTO)."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None or acc.total_pnr == 0:
                return PickAndRollAnalysis()

            ppp = acc.total_points / acc.total_pnr

            handler_eff = (
                acc.handler_makes / acc.handler_shots
                if acc.handler_shots > 0 else 0.0
            )
            roller_eff = (
                acc.roller_makes / acc.roller_shots
                if acc.roller_shots > 0 else 0.0
            )
            pop_eff = (
                acc.pop_makes / acc.pop_shots
                if acc.pop_shots > 0 else 0.0
            )

            # 가장 효율적인 액션 판별
            best_action = ""
            best_ppp = 0.0
            for action_key, poss in acc.action_possessions.items():
                if poss >= 3:  # 최소 3회 이상
                    a_ppp = acc.action_points.get(action_key, 0) / poss
                    if a_ppp > best_ppp:
                        best_ppp = a_ppp
                        best_action = action_key

            return PickAndRollAnalysis(
                total_pnr=acc.total_pnr,
                pnr_ppp=round(ppp, 3),
                ballhandler_efficiency=round(handler_eff, 3),
                roller_efficiency=round(roller_eff, 3),
                pop_efficiency=round(pop_eff, 3),
                defense_responses=dict(acc.defense_counts),
                most_effective_action=best_action,
            )

    def get_defense_distribution(self, team_id: str) -> dict[str, float]:
        """수비 대응 분포 (비율)."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None or acc.total_pnr == 0:
                return {}
            total = sum(acc.defense_counts.values())
            if total == 0:
                return {}
            return {
                k: round(v / total * 100.0, 1)
                for k, v in acc.defense_counts.items()
            }

    def get_event_history(self) -> list[PnREventInput]:
        """이벤트 히스토리 반환 (방어적 복사)."""
        with self._lock:
            return list(self._event_history)

    # --- 리셋 ---
    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._teams.clear()
            self._event_history.clear()


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "ScreenAnalyzerConfig",
    "ScreenAnalyzer",
    "PnREventInput",
    "PnRCoverageType",
    "PnRActionType",
]

__version__ = "1.0.0"
