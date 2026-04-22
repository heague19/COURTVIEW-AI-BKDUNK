# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection
파일: player_id_manager.py
설명: 선수 ID 통합 관리자
      - OCR(등번호) + Tracking(추적) 2원 융합 (ReID 제거 — digit+team으로 대체)
      - 가중 투표: OCR 60% + Tracking 40%
      - 확정/임시/미확정 3단계 ID 상태 관리
      - 멀티뷰 ID 일관성 유지

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/dto/player_dto.py: Team, PlayerRole
    - detection/player_detection/models.py: PlayerIDManagerConfig, _PlayerCandidate
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import threading
from dataclasses import dataclass
from enum import Enum, unique
from typing import Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
# =============================================================================
# 프로젝트 모듈
# =============================================================================
from shared.constants.player_constants import (
    PLAYER_CLASS_ID_COACH,
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
    PLAYER_CLASS_ID_STAFF,
)
from shared.dto.player_dto import PlayerRole, Team
from detection.player_detection.models import (
    PlayerIDManagerConfig,
    _PlayerCandidate,
)

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 모듈 상수
# =============================================================================

# 클래스 ID → PlayerRole 매핑
_CLASS_TO_ROLE: Final[dict[int, PlayerRole]] = {
    PLAYER_CLASS_ID_PLAYER: PlayerRole.PLAYER,
    PLAYER_CLASS_ID_REFEREE: PlayerRole.REFEREE,
    PLAYER_CLASS_ID_COACH: PlayerRole.COACH,
    PLAYER_CLASS_ID_STAFF: PlayerRole.STAFF,
}


# =============================================================================
# ID 상태 열거형
# =============================================================================

@unique
class IDStatus(str, Enum):
    """선수 ID 확정 상태."""

    # 확정됨 (OCR + Tracking 일치)
    CONFIRMED = "confirmed"

    # 임시 (일부 소스만 일치)
    TENTATIVE = "tentative"

    # 미확정 (추적만 진행 중)
    UNCONFIRMED = "unconfirmed"

    @property
    def is_confirmed(self) -> bool:
        """확정 여부."""
        return self == IDStatus.CONFIRMED


# =============================================================================
# 관리 대상 선수 엔트리
# =============================================================================

@dataclass(slots=True)
class ManagedPlayer:
    """
    관리 중인 선수 정보.

    OCR, Tracking 결과를 종합한 최종 선수 식별 상태.
    ReID는 digit(등번호) + team(색상)으로 대체됨.

    Attributes:
        player_id: 최종 선수 ID (통합)
        track_id: 추적기 트랙 ID
        jersey_number: 등번호 (확정 시)
        team: 팀 분류 결과
        role: 역할 (선수/심판/코치/스태프)
        status: ID 확정 상태
        fusion_confidence: 융합 신뢰도 (0.0~1.0)
        ocr_confidence: OCR 신뢰도
        tracking_confidence: 추적 연속성 신뢰도
        last_frame: 마지막 업데이트 프레임
        creation_frame: 생성 프레임
    """

    player_id: int = 0
    track_id: int = -1
    jersey_number: int | None = None
    team: Team = Team.UNKNOWN
    role: PlayerRole = PlayerRole.UNKNOWN
    status: IDStatus = IDStatus.UNCONFIRMED
    fusion_confidence: float = 0.0
    ocr_confidence: float = 0.0
    tracking_confidence: float = 0.0
    last_frame: int = 0
    creation_frame: int = 0

    def __repr__(self) -> str:
        jersey_str = f"#{self.jersey_number}" if self.jersey_number is not None else "#?"
        return (
            f"ManagedPlayer(id={self.player_id}, {jersey_str}, "
            f"team={self.team.value}, {self.status.value}, "
            f"fusion={self.fusion_confidence:.2f})"
        )


# =============================================================================
# 선수 ID 통합 관리자
# =============================================================================

class PlayerIDManager:
    """
    선수 ID 통합 관리자.

    OCR(등번호), ReID(외관), Tracking(추적)의 결과를
    가중 융합하여 최종 선수 ID를 결정합니다.

    융합 공식:
        fusion_score = ocr_weight × ocr_conf
                     + reid_weight × reid_sim
                     + tracking_weight × tracking_conf

    확정 규칙:
        - fusion_score ≥ confirmation_threshold → CONFIRMED
        - 일부 소스 일치 → TENTATIVE
        - 추적만 → UNCONFIRMED

    사용 예시::

        >>> config = PlayerIDManagerConfig()
        >>> manager = PlayerIDManager()
        >>> manager.initialize(config)
        >>> player = manager.update_player(
        ...     track_id=1, jersey_number=23, jersey_conf=0.9,
        ...     reid_id=5, reid_sim=0.85, team=Team.TEAM_A,
        ...     class_id=0, frame_index=100,
        ... )
    """

    def __init__(self) -> None:
        """관리자 초기화."""
        self._lock = threading.RLock()
        self._config: PlayerIDManagerConfig | None = None
        self._initialized: bool = False

        # 관리 중인 선수: player_id → ManagedPlayer
        self._players: dict[int, ManagedPlayer] = {}

        # 역매핑: track_id → player_id
        self._track_to_player: dict[int, int] = {}

        self._next_player_id: int = 1

        # 통계
        self._total_confirmed: int = 0
        self._total_managed: int = 0

        logger.info("PlayerIDManager 인스턴스 생성")

    # =========================================================================
    # 공개 속성
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def managed_count(self) -> int:
        """관리 중인 선수 수."""
        return len(self._players)

    @property
    def confirmed_count(self) -> int:
        """확정된 선수 수."""
        return sum(1 for p in self._players.values() if p.status.is_confirmed)

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    def initialize(self, config: PlayerIDManagerConfig) -> None:
        """
        관리자 초기화.

        Args:
            config: ID 관리 설정
        """
        with self._lock:
            self._config = config
            self._players.clear()
            self._track_to_player.clear()
            self._next_player_id = 1
            self._total_confirmed = 0
            self._total_managed = 0
            self._initialized = True
            logger.info("PlayerIDManager 초기화 완료: %r", config)

    def shutdown(self) -> None:
        """관리자 종료."""
        with self._lock:
            self._initialized = False
            logger.info(
                "PlayerIDManager 종료: 관리=%d, 확정=%d",
                self._total_managed,
                self._total_confirmed,
            )
            self._players.clear()
            self._track_to_player.clear()

    def reset(self) -> None:
        """상태 초기화 (설정 유지)."""
        with self._lock:
            self._players.clear()
            self._track_to_player.clear()
            self._next_player_id = 1
            self._total_confirmed = 0
            self._total_managed = 0

    # =========================================================================
    # 선수 업데이트
    # =========================================================================

    def update_player(
        self,
        track_id: int,
        jersey_number: int | None = None,
        jersey_conf: float = 0.0,
        team: Team = Team.UNKNOWN,
        class_id: int = PLAYER_CLASS_ID_PLAYER,
        frame_index: int = 0,
    ) -> ManagedPlayer:
        """
        선수 ID 업데이트 (OCR + Tracking 융합).

        ReID는 digit(등번호) + team(색상)으로 대체됨.
        8대 카메라에서 등번호가 보이면 자동 식별.

        Args:
            track_id: 추적기 트랙 ID
            jersey_number: OCR 인식 등번호 (None이면 미인식)
            jersey_conf: OCR 신뢰도
            team: 팀 분류 결과
            class_id: YOLO 클래스 ID
            frame_index: 현재 프레임 인덱스

        Returns:
            업데이트된 ManagedPlayer
        """
        if not self._initialized or self._config is None:
            return ManagedPlayer()

        with self._lock:
            config = self._config

            # 기존 선수 조회 (track_id 기준)
            player_id = self._track_to_player.get(track_id)

            # 등번호+팀으로 기존 선수 조회 (ReID 대체)
            if player_id is None and jersey_number is not None and team != Team.UNKNOWN:
                for pid, p in self._players.items():
                    if p.jersey_number == jersey_number and p.team == team:
                        player_id = pid
                        break

            if player_id is not None and player_id in self._players:
                player = self._players[player_id]
            else:
                player = self._register_new_player(
                    track_id, class_id, frame_index,
                )

            # OCR 신뢰도 갱신
            if jersey_number is not None and jersey_conf > 0.0:
                player.jersey_number = jersey_number
                player.ocr_confidence = jersey_conf

            # Tracking 연속성
            tracking_conf = self._compute_tracking_confidence(player, frame_index)
            player.tracking_confidence = tracking_conf

            # 팀 갱신
            if team != Team.UNKNOWN:
                player.team = team

            # 역할 갱신
            role = _CLASS_TO_ROLE.get(class_id, PlayerRole.UNKNOWN)
            if role != PlayerRole.UNKNOWN:
                player.role = role

            # 융합 점수 산출
            fusion_score = self._compute_fusion_score(player, config)
            player.fusion_confidence = fusion_score

            # 상태 판정
            player.status = self._determine_status(player, config)

            player.last_frame = frame_index
            player.track_id = track_id
            self._track_to_player[track_id] = player.player_id

            return player

    def update_batch(
        self,
        track_ids: list[int],
        jersey_numbers: list[int | None],
        jersey_confs: list[float],
        teams: list[Team],
        class_ids: list[int],
        frame_index: int = 0,
    ) -> list[ManagedPlayer]:
        """
        배치 선수 ID 업데이트.

        Args:
            track_ids: 추적 ID 목록
            jersey_numbers: OCR 등번호 목록
            jersey_confs: OCR 신뢰도 목록
            teams: 팀 목록
            class_ids: 클래스 ID 목록
            frame_index: 프레임 인덱스

        Returns:
            ManagedPlayer 목록
        """
        results: list[ManagedPlayer] = []
        n = len(track_ids)

        for i in range(n):
            player = self.update_player(
                track_id=track_ids[i],
                jersey_number=jersey_numbers[i] if i < len(jersey_numbers) else None,
                jersey_conf=jersey_confs[i] if i < len(jersey_confs) else 0.0,
                team=teams[i] if i < len(teams) else Team.UNKNOWN,
                class_id=class_ids[i] if i < len(class_ids) else PLAYER_CLASS_ID_PLAYER,
                frame_index=frame_index,
            )
            results.append(player)

        return results

    # =========================================================================
    # 조회
    # =========================================================================

    def get_player(self, player_id: int) -> ManagedPlayer | None:
        """선수 조회 (player_id)."""
        return self._players.get(player_id)

    def get_player_by_track(self, track_id: int) -> ManagedPlayer | None:
        """선수 조회 (track_id)."""
        pid = self._track_to_player.get(track_id)
        if pid is None:
            return None
        return self._players.get(pid)

    def get_player_by_jersey(self, jersey_number: int) -> ManagedPlayer | None:
        """선수 조회 (등번호)."""
        for p in self._players.values():
            if p.jersey_number == jersey_number and p.status.is_confirmed:
                return p
        return None

    def get_all_players(self) -> list[ManagedPlayer]:
        """모든 관리 중인 선수 목록."""
        return list(self._players.values())

    def get_confirmed_players(self) -> list[ManagedPlayer]:
        """확정된 선수만."""
        return [p for p in self._players.values() if p.status.is_confirmed]

    def get_team_players(self, team: Team) -> list[ManagedPlayer]:
        """특정 팀 선수만."""
        return [p for p in self._players.values() if p.team == team]

    # =========================================================================
    # 정리
    # =========================================================================

    def cleanup(self, current_frame: int) -> int:
        """
        오래된 미확정 선수 제거.

        Args:
            current_frame: 현재 프레임 인덱스

        Returns:
            제거된 선수 수
        """
        if self._config is None:
            return 0

        with self._lock:
            max_frames = self._config.max_unconfirmed_frames
            max_players = self._config.max_managed_players

            expired: list[int] = []
            for pid, player in self._players.items():
                if not player.status.is_confirmed:
                    if current_frame - player.last_frame > max_frames:
                        expired.append(pid)

            for pid in expired:
                self._remove_player(pid)

            # 최대 관리 수 초과 → 가장 낮은 신뢰도부터 제거
            while len(self._players) > max_players:
                worst_pid = min(
                    self._players,
                    key=lambda pid: self._players[pid].fusion_confidence,
                )
                self._remove_player(worst_pid)

            return len(expired)

    def remove_track(self, track_id: int) -> None:
        """
        추적 종료 시 선수 제거.

        Args:
            track_id: 삭제할 추적 ID
        """
        with self._lock:
            pid = self._track_to_player.pop(track_id, None)
            if pid is not None:
                player = self._players.get(pid)
                if player is not None and not player.status.is_confirmed:
                    self._remove_player(pid)

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    def _register_new_player(
        self,
        track_id: int,
        class_id: int,
        frame_index: int,
    ) -> ManagedPlayer:
        """신규 선수 등록."""
        pid = self._next_player_id
        self._next_player_id += 1

        role = _CLASS_TO_ROLE.get(class_id, PlayerRole.UNKNOWN)

        player = ManagedPlayer(
            player_id=pid,
            track_id=track_id,
            role=role,
            status=IDStatus.UNCONFIRMED,
            creation_frame=frame_index,
            last_frame=frame_index,
        )

        self._players[pid] = player
        self._track_to_player[track_id] = pid
        self._total_managed += 1

        return player

    def _remove_player(self, player_id: int) -> None:
        """선수 제거 (역매핑 포함)."""
        player = self._players.pop(player_id, None)
        if player is None:
            return

        # 역매핑 정리
        if player.track_id >= 0:
            self._track_to_player.pop(player.track_id, None)

    def _compute_tracking_confidence(
        self,
        player: ManagedPlayer,
        current_frame: int,
    ) -> float:
        """
        추적 연속성 신뢰도 산출.

        생성 이후 지속 시간이 길수록 높은 신뢰도.

        Args:
            player: 선수 정보
            current_frame: 현재 프레임

        Returns:
            추적 신뢰도 (0.0~1.0)
        """
        age = current_frame - player.creation_frame + 1
        # 30프레임(~1초) 이상 추적되면 신뢰도 1.0
        return min(1.0, age / 30.0)

    @staticmethod
    def _compute_fusion_score(
        player: ManagedPlayer,
        config: PlayerIDManagerConfig,
    ) -> float:
        """
        2원 융합 점수 산출 (OCR + Tracking).

        ReID 제거 — digit(등번호) + team(색상)으로 선수 식별 대체.

        Args:
            player: 선수 정보
            config: 설정

        Returns:
            융합 점수 (0.0~1.0)
        """
        # OCR 60% + Tracking 40% (ReID 가중치를 OCR에 재배분)
        score = (
            0.60 * player.ocr_confidence
            + 0.40 * player.tracking_confidence
        )
        return min(1.0, score)

    @staticmethod
    def _determine_status(
        player: ManagedPlayer,
        config: PlayerIDManagerConfig,
    ) -> IDStatus:
        """
        ID 상태 판정.

        Args:
            player: 선수 정보
            config: 설정

        Returns:
            IDStatus
        """
        if player.fusion_confidence >= config.confirmation_threshold:
            return IDStatus.CONFIRMED

        # OCR(등번호) 확보 시 임시 확정
        has_ocr = player.jersey_number is not None and player.ocr_confidence > 0.3

        if has_ocr:
            return IDStatus.TENTATIVE

        return IDStatus.UNCONFIRMED

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def __repr__(self) -> str:
        return (
            f"PlayerIDManager(managed={len(self._players)}, "
            f"confirmed={self.confirmed_count}, "
            f"total={self._total_managed})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "PlayerIDManager",
    "PlayerIDManagerConfig",
    "ManagedPlayer",
    "IDStatus",
]

__version__: str = "1.0.0"
