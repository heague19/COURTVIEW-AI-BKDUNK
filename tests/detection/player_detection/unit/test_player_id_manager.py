# -*- coding: utf-8 -*-
"""
player_detection/player_id_manager.py 단위 테스트.
"""

from __future__ import annotations

import pytest

from shared.constants.player_constants import (
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
)
from shared.dto.player_dto import PlayerRole, Team
from detection.player_detection.models import PlayerIDManagerConfig
from detection.player_detection.player_id_manager import (
    IDStatus,
    ManagedPlayer,
    PlayerIDManager,
)


# =============================================================================
# 초기화 / 종료
# =============================================================================

class Test_PlayerIDManager_초기화:

    def test_초기화_전_상태(self) -> None:
        mgr = PlayerIDManager()
        assert mgr.is_initialized is False
        assert mgr.managed_count == 0

    def test_초기화_후_상태(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        assert mgr.is_initialized is True

    def test_종료(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        mgr.shutdown()
        assert mgr.is_initialized is False


# =============================================================================
# 선수 등록 및 업데이트
# =============================================================================

class Test_PlayerIDManager_등록:

    def test_신규_등록(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        player = mgr.update_player(
            track_id=1,
            class_id=PLAYER_CLASS_ID_PLAYER,
            frame_index=0,
        )
        assert player.player_id == 1
        assert player.track_id == 1
        assert player.status == IDStatus.UNCONFIRMED
        assert mgr.managed_count == 1

    def test_동일_track_id_재사용(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        p1 = mgr.update_player(track_id=1, frame_index=0)
        p2 = mgr.update_player(track_id=1, frame_index=1)
        assert p1.player_id == p2.player_id
        assert mgr.managed_count == 1

    def test_다른_track_id_별도_등록(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        mgr.update_player(track_id=1, frame_index=0)
        mgr.update_player(track_id=2, frame_index=0)
        assert mgr.managed_count == 2


# =============================================================================
# 융합 점수
# =============================================================================

class Test_PlayerIDManager_융합:

    def test_OCR만_입력_시_TENTATIVE(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        player = mgr.update_player(
            track_id=1,
            jersey_number=23,
            jersey_conf=0.9,
            frame_index=30,  # 30프레임 경과 → tracking_conf=1.0
        )
        # OCR 0.4 * 0.9 = 0.36, Tracking 0.25 * 1.0 = 0.25 → fusion=0.61
        # < confirmation_threshold(0.7) → TENTATIVE
        assert player.status == IDStatus.TENTATIVE
        assert player.jersey_number == 23

    def test_전체_소스_입력_시_CONFIRMED(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())

        # 먼저 등록 (creation_frame=0)
        mgr.update_player(track_id=1, frame_index=0)

        # 30프레임 후 모든 소스 업데이트 → tracking_conf = min(1.0, 31/30) = 1.0
        player = mgr.update_player(
            track_id=1,
            jersey_number=7,
            jersey_conf=0.95,
            reid_id=5,
            reid_sim=0.88,
            team=Team.TEAM_A,
            frame_index=30,
        )
        # OCR: 0.4 * 0.95 = 0.38
        # ReID: 0.35 * 0.88 = 0.308
        # Tracking: 0.25 * 1.0 = 0.25 (age=31)
        # fusion = 0.938 ≥ 0.7 → CONFIRMED
        assert player.status == IDStatus.CONFIRMED
        assert player.jersey_number == 7
        assert player.team == Team.TEAM_A

    def test_가중치합_1_0(self) -> None:
        config = PlayerIDManagerConfig()
        total = config.ocr_weight + config.reid_weight + config.tracking_weight
        assert total == pytest.approx(1.0)


# =============================================================================
# 역할 매핑
# =============================================================================

class Test_PlayerIDManager_역할:

    def test_선수_역할(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        player = mgr.update_player(
            track_id=1, class_id=PLAYER_CLASS_ID_PLAYER, frame_index=0,
        )
        assert player.role == PlayerRole.PLAYER

    def test_심판_역할(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        player = mgr.update_player(
            track_id=1, class_id=PLAYER_CLASS_ID_REFEREE, frame_index=0,
        )
        assert player.role == PlayerRole.REFEREE

    def test_팀_갱신(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        player = mgr.update_player(
            track_id=1, team=Team.TEAM_B, frame_index=0,
        )
        assert player.team == Team.TEAM_B


# =============================================================================
# 조회
# =============================================================================

class Test_PlayerIDManager_조회:

    def test_트랙_조회(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        mgr.update_player(track_id=5, frame_index=0)
        player = mgr.get_player_by_track(5)
        assert player is not None
        assert player.track_id == 5

    def test_없는_트랙_조회(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        assert mgr.get_player_by_track(999) is None

    def test_전체_선수_조회(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        for i in range(3):
            mgr.update_player(track_id=i, frame_index=0)
        assert len(mgr.get_all_players()) == 3

    def test_팀별_조회(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        mgr.update_player(track_id=1, team=Team.TEAM_A, frame_index=0)
        mgr.update_player(track_id=2, team=Team.TEAM_B, frame_index=0)
        mgr.update_player(track_id=3, team=Team.TEAM_A, frame_index=0)
        team_a = mgr.get_team_players(Team.TEAM_A)
        assert len(team_a) == 2


# =============================================================================
# 정리
# =============================================================================

class Test_PlayerIDManager_정리:

    def test_오래된_미확정_제거(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig(max_unconfirmed_frames=10))
        mgr.update_player(track_id=1, frame_index=0)
        removed = mgr.cleanup(current_frame=20)
        assert removed == 1
        assert mgr.managed_count == 0

    def test_확정_선수는_제거_안됨(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig(max_unconfirmed_frames=10))
        player = mgr.update_player(
            track_id=1,
            jersey_number=23, jersey_conf=0.95,
            reid_id=1, reid_sim=0.9,
            frame_index=60,
        )
        assert player.status == IDStatus.CONFIRMED
        removed = mgr.cleanup(current_frame=200)
        assert removed == 0
        assert mgr.managed_count == 1

    def test_reset(self) -> None:
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())
        mgr.update_player(track_id=1, frame_index=0)
        mgr.reset()
        assert mgr.managed_count == 0


# =============================================================================
# IDStatus / ManagedPlayer
# =============================================================================

class Test_IDStatus:

    def test_confirmed(self) -> None:
        assert IDStatus.CONFIRMED.is_confirmed is True
        assert IDStatus.TENTATIVE.is_confirmed is False
        assert IDStatus.UNCONFIRMED.is_confirmed is False


class Test_ManagedPlayer:

    def test_repr(self) -> None:
        p = ManagedPlayer(
            player_id=1, jersey_number=23,
            team=Team.TEAM_A, status=IDStatus.CONFIRMED,
            fusion_confidence=0.92,
        )
        r = repr(p)
        assert "#23" in r
        assert "confirmed" in r
