# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_management
파일: foul_manager.py
설명: 개인/팀 파울 누적 및 보너스 상태 관리
      - 선수별 개인 파울 누적 + 퇴장 판정
      - 쿼터별 팀 파울 누적 + 보너스/더블보너스 전환
      - 파울 트러블 경고
      - 파울아웃 리스크 산출
      - 리그별 규칙 자동 적용 (FIBA=5파울/NBA=6파울)
      - 🟠EVENT 등급 (이벤트 발생 시 <10ms)

      리그별 파울 규정:
        - FIBA: 개인 5파울 퇴장, 쿼터 4팀파울 초과 시 보너스
        - NBA: 개인 6파울 퇴장, 쿼터 4팀파울 초과 시 보너스, 10팀파울 시 더블보너스
        - KBL/NBL/EUROLEAGUE: FIBA 준용

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - shared/constants/game_management_constants.py: BonusStatus, 파울 파라미터
    - shared/constants/referee_rule_constants.py: RuleSet (리그별 파울 퇴장 기준)
    - shared/dto/game_management_dto.py: FoulState, BonusStatus(DTO)

의존성:
    - shared/constants/game_management_constants.py
    - shared/constants/referee_rule_constants.py

소비자:
    - game_analysis/event_detection/foul_detector.py: 파울 이벤트 시 record_foul() 호출
    - game_analysis/game_management/clock_manager.py: 쿼터 번호 참조
    - game_analysis/statistics/basic_stats.py: 파울 통계
    - game_analysis/coaching_intelligence/: 파울 트러블 기반 교체 추천
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from typing import Final

from shared.constants.game_management_constants import (
    BonusStatus,
    TEAM_FOUL_BONUS_THRESHOLD,
    NBA_DOUBLE_BONUS_THRESHOLD,
    FOUL_TROUBLE_WARNING_OFFSET,
    FOUL_OUT_RISK_THRESHOLD,
    REGULAR_PERIODS,
    get_bonus_status,
    is_foul_trouble,
)
from shared.constants.referee_rule_constants import RuleSet
from shared.dto.game_management_dto import FoulState


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 파울 이력 최대 보관 수 (메모리 가드 — 경기당 최대 약 80~100회)
_MAX_FOUL_HISTORY: Final[int] = 200

# 테크니컬 파울 퇴장 기준 (모든 리그 2개)
_TECHNICAL_FOUL_EJECTION: Final[int] = 2


# =============================================================================
# 파울 기록 (개별 파울 이벤트)
# =============================================================================

@dataclass(slots=True)
class FoulRecord:
    """
    개별 파울 기록.

    record_foul() 호출 시 생성되어 이력에 보관.
    """

    player_tracking_id: int
    team_id: str
    quarter: int
    game_clock: str  # 파울 발생 시점 (MM:SS)
    foul_type: str  # personal, offensive, technical, flagrant1, flagrant2
    is_shooting_foul: bool = False
    # 피해 선수 (슈팅 파울, 플래그런트 등)
    fouled_player_tracking_id: int = 0


# =============================================================================
# 파울 관리자 설정
# =============================================================================

@dataclass(slots=True)
class FoulManagerConfig:
    """
    파울 관리자 설정.

    리그 규정에 따라 파울 퇴장 기준, 보너스 전환 기준 등을 결정.
    """

    rule_set: RuleSet = RuleSet.FIBA

    @property
    def max_personal_fouls(self) -> int:
        """개인 파울 퇴장 기준."""
        return self.rule_set.max_personal_fouls

    @property
    def team_foul_bonus_threshold(self) -> int:
        """팀 파울 보너스 전환 기준 (이 값 초과 시 보너스)."""
        return TEAM_FOUL_BONUS_THRESHOLD[self.rule_set]

    @property
    def has_double_bonus(self) -> bool:
        """더블 보너스 적용 여부 (NBA만)."""
        return self.rule_set == RuleSet.NBA

    @classmethod
    def from_yaml(cls, cfg: dict) -> FoulManagerConfig:
        """YAML 설정에서 생성."""
        rule_str = cfg.get("rule_set", "fiba")
        try:
            rule_set = RuleSet(rule_str)
        except ValueError:
            logger.warning("알 수 없는 규칙세트 '%s', FIBA 기본 적용", rule_str)
            rule_set = RuleSet.FIBA

        return cls(rule_set=rule_set)


# =============================================================================
# 파울 관리자
# =============================================================================

class FoulManager:
    """
    개인/팀 파울 누적 및 보너스 상태 관리자.

    🟠EVENT 등급: 파울 이벤트 발생 시 호출 (<10ms).

    기능:
        - 선수별 개인 파울 누적 + 퇴장 판정
        - 쿼터별 팀 파울 누적 + 보너스/더블보너스 전환
        - 테크니컬/플래그런트 파울 별도 누적
        - 파울 트러블 경고 (퇴장 기준 - 1)
        - 파울아웃 리스크 (시간 대비 파울 비율)
        - 파울 기록 이력 관리

    사용법:
        >>> config = FoulManagerConfig(rule_set=RuleSet.FIBA)
        >>> fm = FoulManager(config, teams=["home", "away"])
        >>> fm.record_foul("home", player_id=7, quarter=1, game_clock="08:30", foul_type="personal")
        >>> state = fm.get_foul_state("home", quarter=1)
        >>> state.bonus_status
        <BonusStatus.NONE: 'none'>
    """

    __slots__ = (
        "_config", "_lock",
        "_team_ids",
        # 쿼터별 팀 파울: {team_id: {quarter: count}}
        "_team_fouls_per_quarter",
        # 선수별 개인 파울: {player_tracking_id: count}
        "_personal_fouls",
        # 선수별 테크니컬 파울: {player_tracking_id: count}
        "_technical_fouls",
        # 퇴장 선수: {team_id: [player_tracking_id, ...]}
        "_disqualified",
        # 파울 이력
        "_foul_history",
    )

    def __init__(
        self,
        config: FoulManagerConfig | None = None,
        teams: list[str] | None = None,
    ) -> None:
        self._config: FoulManagerConfig = config or FoulManagerConfig()
        self._lock: RLock = RLock()

        self._team_ids: list[str] = list(teams) if teams else []

        # 쿼터별 팀 파울: {team_id: {quarter: count}}
        self._team_fouls_per_quarter: dict[str, dict[int, int]] = {
            tid: {} for tid in self._team_ids
        }
        # 선수별 개인 파울 누적 (경기 전체)
        self._personal_fouls: dict[int, int] = {}
        # 선수별 테크니컬 파울 누적
        self._technical_fouls: dict[int, int] = {}
        # 팀별 퇴장 선수 목록
        self._disqualified: dict[str, list[int]] = {
            tid: [] for tid in self._team_ids
        }
        # 파울 이력 (시간 순)
        self._foul_history: list[FoulRecord] = []

    # =========================================================================
    # 파울 기록
    # =========================================================================

    def record_foul(
        self,
        team_id: str,
        player_tracking_id: int,
        quarter: int,
        game_clock: str,
        foul_type: str = "personal",
        is_shooting_foul: bool = False,
        fouled_player_tracking_id: int = 0,
    ) -> FoulRecordResult:
        """
        파울 기록.

        🟠EVENT: 파울 이벤트 발생 시 호출.

        Args:
            team_id: 파울을 범한 팀 ID
            player_tracking_id: 파울을 범한 선수 tracking ID
            quarter: 현재 쿼터 (1~4, OT: 5+)
            game_clock: 현재 경기 시계 (MM:SS)
            foul_type: 파울 유형 (personal/offensive/technical/flagrant1/flagrant2)
            is_shooting_foul: 슈팅 파울 여부
            fouled_player_tracking_id: 피해 선수 tracking ID

        Returns:
            FoulRecordResult (퇴장/보너스/트러블 정보 포함)
        """
        with self._lock:
            # 팀 등록 확인 (미등록 팀이면 자동 등록)
            self._ensure_team(team_id)

            # 이력 기록
            record = FoulRecord(
                player_tracking_id=player_tracking_id,
                team_id=team_id,
                quarter=quarter,
                game_clock=game_clock,
                foul_type=foul_type,
                is_shooting_foul=is_shooting_foul,
                fouled_player_tracking_id=fouled_player_tracking_id,
            )
            if len(self._foul_history) < _MAX_FOUL_HISTORY:
                self._foul_history.append(record)

            # 개인 파울 누적
            is_ejected = False
            if foul_type == "flagrant2":
                # 플래그런트 2: 즉시 퇴장
                is_ejected = True
                self._personal_fouls[player_tracking_id] = (
                    self._personal_fouls.get(player_tracking_id, 0) + 1
                )
            elif foul_type == "technical":
                # 테크니컬 파울: 별도 누적
                tech_count = self._technical_fouls.get(player_tracking_id, 0) + 1
                self._technical_fouls[player_tracking_id] = tech_count
                if tech_count >= _TECHNICAL_FOUL_EJECTION:
                    is_ejected = True
            else:
                # 일반/슈팅/공격/플래그런트1: 개인 파울 누적
                personal_count = (
                    self._personal_fouls.get(player_tracking_id, 0) + 1
                )
                self._personal_fouls[player_tracking_id] = personal_count
                if personal_count >= self._config.max_personal_fouls:
                    is_ejected = True

            # 퇴장 처리
            if is_ejected:
                disq_list = self._disqualified[team_id]
                if player_tracking_id not in disq_list:
                    disq_list.append(player_tracking_id)
                    logger.info(
                        "선수 퇴장: 팀=%s, 선수=%d, 사유=%s",
                        team_id, player_tracking_id, foul_type,
                    )

            # 팀 파울 누적 (공격 파울은 팀 파울에 미포함 — FIBA/NBA 공통)
            is_team_foul = foul_type not in ("offensive", "technical")
            if is_team_foul:
                quarter_fouls = self._team_fouls_per_quarter[team_id]
                quarter_fouls[quarter] = quarter_fouls.get(quarter, 0) + 1

            # 보너스 상태 산출
            team_foul_count = self._team_fouls_per_quarter[team_id].get(quarter, 0)
            bonus = get_bonus_status(team_foul_count, self._config.rule_set)

            # 파울 트러블 여부
            current_personal = self._personal_fouls.get(player_tracking_id, 0)
            in_foul_trouble = is_foul_trouble(
                current_personal, self._config.rule_set
            )

            logger.debug(
                "파울 기록: 팀=%s, 선수=%d, Q%d %s, 유형=%s, "
                "개인파울=%d/%d, 팀파울=%d, 보너스=%s",
                team_id, player_tracking_id, quarter, game_clock, foul_type,
                current_personal, self._config.max_personal_fouls,
                team_foul_count, bonus,
            )

            return FoulRecordResult(
                player_tracking_id=player_tracking_id,
                team_id=team_id,
                personal_foul_count=current_personal,
                team_foul_count=team_foul_count,
                bonus_status=bonus,
                is_ejected=is_ejected,
                is_foul_trouble=in_foul_trouble,
                is_shooting_foul=is_shooting_foul,
                foul_type=foul_type,
            )

    # =========================================================================
    # 쿼터 리셋 (팀 파울)
    # =========================================================================

    def reset_quarter_fouls(self, quarter: int) -> None:
        """
        새 쿼터 시작 시 팀 파울 리셋.

        NBA: 쿼터별 리셋, FIBA: 쿼터별 리셋.
        개인 파울은 경기 전체 누적이므로 리셋하지 않음.

        Args:
            quarter: 새 쿼터 번호
        """
        with self._lock:
            for tid in self._team_ids:
                # 새 쿼터의 팀 파울 초기화 (이미 존재하면 유지)
                if quarter not in self._team_fouls_per_quarter[tid]:
                    self._team_fouls_per_quarter[tid][quarter] = 0

    # =========================================================================
    # 상태 조회
    # =========================================================================

    def get_foul_state(self, team_id: str, quarter: int) -> FoulState:
        """
        특정 팀의 파울 상태 스냅샷 반환.

        Args:
            team_id: 팀 ID
            quarter: 현재 쿼터

        Returns:
            FoulState DTO (game_management_dto)
        """
        with self._lock:
            self._ensure_team(team_id)

            team_foul_count = self._team_fouls_per_quarter[team_id].get(quarter, 0)
            bonus = get_bonus_status(team_foul_count, self._config.rule_set)

            # 해당 팀 선수들의 개인 파울만 추출
            team_player_fouls: dict[int, int] = {}
            for rec in self._foul_history:
                if rec.team_id == team_id:
                    pid = rec.player_tracking_id
                    if pid not in team_player_fouls:
                        team_player_fouls[pid] = self._personal_fouls.get(pid, 0)

            return FoulState(
                team_id=team_id,
                quarter=quarter,
                team_fouls=team_foul_count,
                bonus_status=bonus,
                player_fouls=team_player_fouls,
                disqualified_players=list(self._disqualified.get(team_id, [])),
                foul_limit=self._config.max_personal_fouls,
            )

    def get_personal_foul_count(self, player_tracking_id: int) -> int:
        """
        선수 개인 파울 수 조회.

        Args:
            player_tracking_id: 선수 tracking ID

        Returns:
            누적 개인 파울 수
        """
        with self._lock:
            return self._personal_fouls.get(player_tracking_id, 0)

    def get_technical_foul_count(self, player_tracking_id: int) -> int:
        """
        선수 테크니컬 파울 수 조회.

        Args:
            player_tracking_id: 선수 tracking ID

        Returns:
            누적 테크니컬 파울 수
        """
        with self._lock:
            return self._technical_fouls.get(player_tracking_id, 0)

    def get_team_foul_count(self, team_id: str, quarter: int) -> int:
        """
        팀 파울 수 조회 (특정 쿼터).

        Args:
            team_id: 팀 ID
            quarter: 쿼터 번호

        Returns:
            해당 쿼터 팀 파울 수
        """
        with self._lock:
            self._ensure_team(team_id)
            return self._team_fouls_per_quarter[team_id].get(quarter, 0)

    def get_bonus_status(self, team_id: str, quarter: int) -> BonusStatus:
        """
        팀 보너스 상태 조회.

        Args:
            team_id: 팀 ID
            quarter: 현재 쿼터

        Returns:
            BonusStatus
        """
        with self._lock:
            self._ensure_team(team_id)
            team_foul_count = self._team_fouls_per_quarter[team_id].get(quarter, 0)
            return get_bonus_status(team_foul_count, self._config.rule_set)

    def is_player_ejected(self, player_tracking_id: int) -> bool:
        """
        선수 퇴장 여부.

        Args:
            player_tracking_id: 선수 tracking ID

        Returns:
            퇴장 여부
        """
        with self._lock:
            for disq_list in self._disqualified.values():
                if player_tracking_id in disq_list:
                    return True
            return False

    def is_player_in_foul_trouble(self, player_tracking_id: int) -> bool:
        """
        선수 파울 트러블 여부.

        파울 트러블: 퇴장 기준 - 1개 이상.

        Args:
            player_tracking_id: 선수 tracking ID

        Returns:
            파울 트러블 여부
        """
        with self._lock:
            count = self._personal_fouls.get(player_tracking_id, 0)
            return is_foul_trouble(count, self._config.rule_set)

    def get_foul_out_risk(
        self,
        player_tracking_id: int,
        remaining_game_time_sec: float,
        total_game_time_sec: float,
    ) -> float:
        """
        파울아웃 리스크 산출.

        리스크 = (현재 파울 / 퇴장 기준) / (남은 시간 / 전체 시간).
        1.0 이상이면 파울아웃 위험, FOUL_OUT_RISK_THRESHOLD(1.2) 이상이면 높은 리스크.

        Args:
            player_tracking_id: 선수 tracking ID
            remaining_game_time_sec: 남은 경기 시간 (초)
            total_game_time_sec: 전체 경기 시간 (초)

        Returns:
            파울아웃 리스크 (0.0 ~ ∞)
        """
        with self._lock:
            count = self._personal_fouls.get(player_tracking_id, 0)
            max_fouls = self._config.max_personal_fouls

            if max_fouls <= 0 or total_game_time_sec <= 0.0:
                return 0.0

            foul_ratio = count / max_fouls

            # 남은 시간 비율 (0에 가까울수록 위험)
            if remaining_game_time_sec <= 0.0:
                # 경기 종료 임박 — 파울이 있으면 무한 리스크
                return float("inf") if count > 0 else 0.0

            time_ratio = remaining_game_time_sec / total_game_time_sec
            if time_ratio <= 0.0:
                return float("inf") if count > 0 else 0.0

            return foul_ratio / time_ratio

    def is_high_foul_risk(
        self,
        player_tracking_id: int,
        remaining_game_time_sec: float,
        total_game_time_sec: float,
    ) -> bool:
        """
        높은 파울아웃 리스크 여부.

        Args:
            player_tracking_id: 선수 tracking ID
            remaining_game_time_sec: 남은 경기 시간 (초)
            total_game_time_sec: 전체 경기 시간 (초)

        Returns:
            FOUL_OUT_RISK_THRESHOLD 초과 여부
        """
        risk = self.get_foul_out_risk(
            player_tracking_id, remaining_game_time_sec, total_game_time_sec
        )
        return risk >= FOUL_OUT_RISK_THRESHOLD

    def get_foul_trouble_players(self, team_id: str) -> list[int]:
        """
        특정 팀의 파울 트러블 선수 목록.

        Args:
            team_id: 팀 ID

        Returns:
            파울 트러블 중인 선수 tracking ID 목록
        """
        with self._lock:
            trouble: list[int] = []
            # 해당 팀 소속 선수만 검사 (이력에서 팀 소속 파악)
            team_players: set[int] = set()
            for rec in self._foul_history:
                if rec.team_id == team_id:
                    team_players.add(rec.player_tracking_id)

            for pid in team_players:
                if pid in self._disqualified.get(team_id, []):
                    continue  # 이미 퇴장
                count = self._personal_fouls.get(pid, 0)
                if is_foul_trouble(count, self._config.rule_set):
                    trouble.append(pid)

            return trouble

    def get_disqualified_players(self, team_id: str) -> list[int]:
        """
        특정 팀 퇴장 선수 목록.

        Args:
            team_id: 팀 ID

        Returns:
            퇴장 선수 tracking ID 목록
        """
        with self._lock:
            return list(self._disqualified.get(team_id, []))

    def get_foul_history(self) -> list[FoulRecord]:
        """
        전체 파울 이력 반환 (방어적 복사).

        Returns:
            FoulRecord 리스트
        """
        with self._lock:
            return list(self._foul_history)

    # =========================================================================
    # 파울 취소 (기록 정정용)
    # =========================================================================

    def revoke_foul(
        self, team_id: str, player_tracking_id: int, quarter: int, foul_type: str
    ) -> bool:
        """
        파울 취소 (기록 정정 시).

        가장 최근의 해당 유형 파울을 취소합니다.

        Args:
            team_id: 팀 ID
            player_tracking_id: 선수 tracking ID
            quarter: 쿼터 번호
            foul_type: 파울 유형

        Returns:
            취소 성공 여부
        """
        with self._lock:
            self._ensure_team(team_id)

            # 이력에서 가장 최근 해당 파울 찾기 (역순 검색)
            target_idx: int | None = None
            for i in range(len(self._foul_history) - 1, -1, -1):
                rec = self._foul_history[i]
                if (
                    rec.team_id == team_id
                    and rec.player_tracking_id == player_tracking_id
                    and rec.quarter == quarter
                    and rec.foul_type == foul_type
                ):
                    target_idx = i
                    break

            if target_idx is None:
                logger.warning(
                    "파울 취소 실패: 해당 파울 기록 없음 (팀=%s, 선수=%d, Q%d, 유형=%s)",
                    team_id, player_tracking_id, quarter, foul_type,
                )
                return False

            # 이력에서 제거
            self._foul_history.pop(target_idx)

            # 개인 파울 감소
            if foul_type == "technical":
                count = self._technical_fouls.get(player_tracking_id, 0)
                self._technical_fouls[player_tracking_id] = max(0, count - 1)
            else:
                count = self._personal_fouls.get(player_tracking_id, 0)
                self._personal_fouls[player_tracking_id] = max(0, count - 1)

            # 팀 파울 감소 (공격 파울, 테크니컬은 팀 파울에 미포함)
            if foul_type not in ("offensive", "technical"):
                quarter_fouls = self._team_fouls_per_quarter[team_id]
                quarter_fouls[quarter] = max(
                    0, quarter_fouls.get(quarter, 0) - 1
                )

            # 퇴장 해제 (파울 수가 기준 미만이면)
            disq_list = self._disqualified[team_id]
            if player_tracking_id in disq_list:
                personal = self._personal_fouls.get(player_tracking_id, 0)
                technical = self._technical_fouls.get(player_tracking_id, 0)
                still_ejected = (
                    personal >= self._config.max_personal_fouls
                    or technical >= _TECHNICAL_FOUL_EJECTION
                )
                if not still_ejected:
                    disq_list.remove(player_tracking_id)
                    logger.info(
                        "퇴장 해제: 팀=%s, 선수=%d (파울 취소)",
                        team_id, player_tracking_id,
                    )

            logger.info(
                "파울 취소: 팀=%s, 선수=%d, Q%d, 유형=%s",
                team_id, player_tracking_id, quarter, foul_type,
            )
            return True

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _ensure_team(self, team_id: str) -> None:
        """팀 미등록 시 자동 등록 (lock 내부 호출)."""
        if team_id not in self._team_fouls_per_quarter:
            self._team_ids.append(team_id)
            self._team_fouls_per_quarter[team_id] = {}
            self._disqualified[team_id] = []

    # =========================================================================
    # 팩토리 / 리셋
    # =========================================================================

    @classmethod
    def from_yaml(cls, cfg: dict, teams: list[str] | None = None) -> FoulManager:
        """YAML 설정에서 FoulManager 생성."""
        config = FoulManagerConfig.from_yaml(cfg)
        return cls(config, teams=teams)

    def reset(self) -> None:
        """전체 리셋 (새 경기 준비)."""
        with self._lock:
            for tid in self._team_ids:
                self._team_fouls_per_quarter[tid] = {}
                self._disqualified[tid] = []
            self._personal_fouls.clear()
            self._technical_fouls.clear()
            self._foul_history.clear()


# =============================================================================
# 파울 기록 결과
# =============================================================================

@dataclass(slots=True)
class FoulRecordResult:
    """
    record_foul() 반환 결과.

    파울 기록 후 즉시 파악해야 할 정보를 포함.
    """

    player_tracking_id: int = 0
    team_id: str = ""
    personal_foul_count: int = 0
    team_foul_count: int = 0
    bonus_status: BonusStatus = BonusStatus.NONE
    is_ejected: bool = False
    is_foul_trouble: bool = False
    is_shooting_foul: bool = False
    foul_type: str = "personal"


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "FoulRecord",
    "FoulManagerConfig",
    "FoulManager",
    "FoulRecordResult",
]

__version__ = "1.0.0"
