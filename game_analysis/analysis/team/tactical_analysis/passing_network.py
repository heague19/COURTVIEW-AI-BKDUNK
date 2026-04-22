# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/tactical_analysis
파일: passing_network.py
설명: 패싱 네트워크 분석기
      - 선수 간 패스 연결 그래프 (방향 가중치)
      - 1차/2차 어시스트 (하키 어시스트) 추적
      - 점유당 평균 패스 횟수
      - 볼 무브먼트 레이팅 (0~100)

      학술 근거:
        Fewell et al. (2012) — Basketball Teams as Strategic Networks
        Clemente et al. (2015) — Network Analysis in Team Sports

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/tactical_dto.py (PassingNetworkData, PassConnection)
소비자: coaching_intelligence, film_session, pre_game
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.dto.tactical_dto import (
    PassingNetworkData,
    PassConnection,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class PassingNetworkConfig:
    """패싱 네트워크 분석기 설정."""

    # 볼 무브먼트 레이팅 파라미터
    # 평균 패스 5회/점유 이상이면 가산, 엔트로피 높으면 가산
    optimal_passes_per_possession: float = 5.0
    # 어시스트 비율 가중치 (레이팅 산출 시)
    assist_weight: float = 0.4
    pass_diversity_weight: float = 0.3
    pass_volume_weight: float = 0.3
    # 최소 신뢰도
    min_confidence: float = 0.60

    @classmethod
    def from_yaml(cls, cfg: dict) -> PassingNetworkConfig:
        """YAML 설정으로부터 생성."""
        # 현재 YAML에 패싱 네트워크 전용 섹션 없음 — 기본값 사용
        return cls()


# =============================================================================
# 입력 데이터
# =============================================================================
@dataclass(slots=True)
class PassEventInput:
    """패스 이벤트 입력 데이터."""

    team_id: str
    passer_id: int = 0
    receiver_id: int = 0
    # 패스 결과
    resulted_in_assist: bool = False
    resulted_in_hockey_assist: bool = False
    resulted_in_turnover: bool = False
    # 패스 특성
    pass_distance_m: float = 0.0
    # 메타
    possession_id: str = ""
    confidence: float = 0.85
    timestamp: float = 0.0


# =============================================================================
# 내부 누적기
# =============================================================================
@dataclass(slots=True)
class _ConnectionAccumulator:
    """연결 누적 (from → to)."""

    from_id: int = 0
    to_id: int = 0
    count: int = 0
    assists: int = 0


@dataclass(slots=True)
class _TeamPassAccumulator:
    """팀별 패스 누적."""

    total_passes: int = 0
    total_possessions: int = 0
    total_assists: int = 0
    hockey_assists: int = 0
    turnovers: int = 0
    # (from_id, to_id) → _ConnectionAccumulator
    connections: dict[tuple[int, int], _ConnectionAccumulator] = field(default_factory=dict)
    # 점유별 패스 카운트 추적
    current_possession_id: str = ""
    current_possession_passes: int = 0
    possession_pass_counts: list[int] = field(default_factory=list)


# =============================================================================
# 패싱 네트워크 분석기
# =============================================================================
class PassingNetworkAnalyzer:
    """
    패싱 네트워크 분석기.

    POSSESSION cadence (<100ms).
    """

    def __init__(self, config: PassingNetworkConfig | None = None) -> None:
        self._config = config or PassingNetworkConfig()
        self._lock = RLock()
        self._teams: dict[str, _TeamPassAccumulator] = {}
        self._event_history: list[PassEventInput] = []
        self._name = "PassingNetworkAnalyzer"

    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> PassingNetworkConfig:
        return self._config

    # --- 핵심 메서드 ---
    def process_pass(self, event: PassEventInput) -> bool:
        """패스 이벤트 처리."""
        if event.confidence < self._config.min_confidence:
            return False
        if event.passer_id == 0 or event.receiver_id == 0:
            return False

        with self._lock:
            acc = self._teams.setdefault(event.team_id, _TeamPassAccumulator())
            acc.total_passes += 1

            # 점유 전환 감지
            if event.possession_id and event.possession_id != acc.current_possession_id:
                if acc.current_possession_id:
                    acc.possession_pass_counts.append(acc.current_possession_passes)
                    # 메모리 가드 (최근 500 점유)
                    if len(acc.possession_pass_counts) > _MAX_EVENT_HISTORY:
                        acc.possession_pass_counts = acc.possession_pass_counts[-_MAX_EVENT_HISTORY:]
                acc.current_possession_id = event.possession_id
                acc.current_possession_passes = 0
                acc.total_possessions += 1

            acc.current_possession_passes += 1

            # 연결 누적
            key = (event.passer_id, event.receiver_id)
            conn = acc.connections.setdefault(
                key, _ConnectionAccumulator(from_id=event.passer_id, to_id=event.receiver_id)
            )
            conn.count += 1

            # 어시스트/하키 어시스트
            if event.resulted_in_assist:
                acc.total_assists += 1
                conn.assists += 1
            if event.resulted_in_hockey_assist:
                acc.hockey_assists += 1
            if event.resulted_in_turnover:
                acc.turnovers += 1

            # 히스토리 (메모리 가드)
            self._event_history.append(event)
            if len(self._event_history) > _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

            return True

    def finalize_possession(self, team_id: str) -> None:
        """현재 점유 종료 시 호출 (패스 카운트 기록)."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None:
                return
            if acc.current_possession_id:
                acc.possession_pass_counts.append(acc.current_possession_passes)
                if len(acc.possession_pass_counts) > _MAX_EVENT_HISTORY:
                    acc.possession_pass_counts = acc.possession_pass_counts[-_MAX_EVENT_HISTORY:]
                acc.current_possession_id = ""
                acc.current_possession_passes = 0

    # --- 조회 ---
    def get_team_analysis(self, team_id: str) -> PassingNetworkData:
        """팀별 패싱 네트워크 분석 (DTO)."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None or acc.total_passes == 0:
                return PassingNetworkData()

            # 연결 목록
            connections: list[PassConnection] = []
            for conn in acc.connections.values():
                assist_rate = conn.assists / conn.count if conn.count > 0 else 0.0
                connections.append(PassConnection(
                    from_tracking_id=conn.from_id,
                    to_tracking_id=conn.to_id,
                    count=conn.count,
                    assist_rate=round(assist_rate, 3),
                ))
            # 빈도순 정렬
            connections.sort(key=lambda c: c.count, reverse=True)

            # 점유당 평균 패스
            avg_passes = 0.0
            if acc.possession_pass_counts:
                avg_passes = sum(acc.possession_pass_counts) / len(acc.possession_pass_counts)

            # 볼 무브먼트 레이팅 산출
            rating = self._calc_ball_movement_rating(acc, avg_passes)

            return PassingNetworkData(
                connections=connections,
                hockey_assists=acc.hockey_assists,
                average_passes_per_possession=round(avg_passes, 2),
                ball_movement_rating=round(rating, 1),
            )

    def get_top_connections(self, team_id: str, n: int = 5) -> list[PassConnection]:
        """상위 N개 패스 연결."""
        result = self.get_team_analysis(team_id)
        return result.connections[:n]

    def get_player_pass_count(self, team_id: str, player_id: int) -> int:
        """특정 선수의 총 패스 횟수."""
        with self._lock:
            acc = self._teams.get(team_id)
            if acc is None:
                return 0
            total = 0
            for (from_id, _), conn in acc.connections.items():
                if from_id == player_id:
                    total += conn.count
            return total

    def get_event_history(self) -> list[PassEventInput]:
        """이벤트 히스토리 (방어적 복사)."""
        with self._lock:
            return list(self._event_history)

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._teams.clear()
            self._event_history.clear()

    # --- 내부 ---
    def _calc_ball_movement_rating(
        self, acc: _TeamPassAccumulator, avg_passes: float
    ) -> float:
        """
        볼 무브먼트 레이팅 산출 (0~100).

        구성:
          - pass_volume (30%): 점유당 평균 패스 / 최적 비율
          - pass_diversity (30%): 연결 엔트로피 (분산된 패스일수록 높음)
          - assist_rate (40%): 전체 어시스트 비율
        """
        cfg = self._config

        # 1. 패스 볼륨 점수 (0~100)
        vol_ratio = min(avg_passes / cfg.optimal_passes_per_possession, 1.5)
        vol_score = min(vol_ratio / 1.5 * 100.0, 100.0)

        # 2. 패스 다양성 (연결 엔트로피)
        total_passes = max(acc.total_passes, 1)
        entropy = 0.0
        for conn in acc.connections.values():
            if conn.count > 0:
                p = conn.count / total_passes
                entropy -= p * math.log2(p) if p > 0 else 0.0
        # 최대 엔트로피 = log2(연결수), 정규화
        n_connections = max(len(acc.connections), 1)
        max_entropy = math.log2(n_connections) if n_connections > 1 else 1.0
        div_score = min(entropy / max_entropy * 100.0, 100.0) if max_entropy > 0 else 0.0

        # 3. 어시스트 비율 점수 (0~100)
        # NBA 평균 어시스트/패스 비율 ~5-8%, 높으면 100
        assist_rate = acc.total_assists / total_passes if total_passes > 0 else 0.0
        assist_score = min(assist_rate / 0.10 * 100.0, 100.0)

        # 가중합
        rating = (
            cfg.pass_volume_weight * vol_score
            + cfg.pass_diversity_weight * div_score
            + cfg.assist_weight * assist_score
        )
        return min(max(rating, 0.0), 100.0)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "PassingNetworkConfig",
    "PassingNetworkAnalyzer",
    "PassEventInput",
]

__version__ = "1.0.0"
