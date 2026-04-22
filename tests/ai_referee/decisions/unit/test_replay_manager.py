# -*- coding: utf-8 -*-
"""ReplayManager 단위 테스트."""

from __future__ import annotations

import pytest

from shared.constants.referee_rule_constants import RuleSet
from shared.constants.game_rule_constants import FoulType

from ai_referee.rules.base_rule import PenaltyType, RuleResult
from ai_referee.decisions.replay_manager import (
    ReplayEvent,
    ReplayManager,
    ReplayPriority,
    ReplayStatus,
)


@pytest.fixture()
def manager() -> ReplayManager:
    return ReplayManager(rule_set=RuleSet.FIBA)


def _make_result(
    *,
    violated: bool = True,
    confidence: float = 0.80,
    penalty: PenaltyType = PenaltyType.FREE_THROWS,
    foul_type: FoulType | None = None,
    start_frame: int = 100,
    end_frame: int = 110,
) -> RuleResult:
    return RuleResult(
        violated=violated,
        confidence=confidence,
        rule_id="FIBA-33",
        penalty=penalty,
        foul_type=foul_type,
        start_frame=start_frame,
        end_frame=end_frame,
    )


class TestInit:
    def test_rule_set(self, manager: ReplayManager) -> None:
        assert manager.rule_set == RuleSet.FIBA


class TestShouldReplay:
    def test_ejection_always_replay(self, manager: ReplayManager) -> None:
        result = _make_result(penalty=PenaltyType.EJECTION)
        assert manager.should_replay(result) is True

    def test_flagrant_replay(self, manager: ReplayManager) -> None:
        result = _make_result(foul_type=FoulType.FLAGRANT_1)
        assert manager.should_replay(result) is True

    def test_close_call_replay(self, manager: ReplayManager) -> None:
        """경계 신뢰도 → 리플레이."""
        result = _make_result(confidence=0.60)
        assert manager.should_replay(result) is True

    def test_high_confidence_no_replay(self, manager: ReplayManager) -> None:
        """높은 신뢰도 → 리플레이 불필요."""
        result = _make_result(confidence=0.92)
        assert manager.should_replay(result) is False

    def test_no_violation_no_replay(self, manager: ReplayManager) -> None:
        result = _make_result(violated=False)
        assert manager.should_replay(result) is False


class TestPriority:
    def test_ejection_critical(self, manager: ReplayManager) -> None:
        result = _make_result(penalty=PenaltyType.EJECTION)
        assert manager.classify_priority(result) == ReplayPriority.CRITICAL

    def test_flagrant_high(self, manager: ReplayManager) -> None:
        result = _make_result(foul_type=FoulType.FLAGRANT_1)
        assert manager.classify_priority(result) == ReplayPriority.HIGH

    def test_close_call_normal(self, manager: ReplayManager) -> None:
        result = _make_result(confidence=0.60)
        assert manager.classify_priority(result) == ReplayPriority.NORMAL


class TestAddReplay:
    def test_add_replay(self, manager: ReplayManager) -> None:
        result = _make_result()
        event = manager.add_replay(result)
        assert isinstance(event, ReplayEvent)
        assert event.status == ReplayStatus.PENDING

    def test_frame_padding(self, manager: ReplayManager) -> None:
        """리플레이 프레임 패딩 적용."""
        result = _make_result(start_frame=100, end_frame=110)
        event = manager.add_replay(result)
        assert event.start_frame < 100
        assert event.end_frame > 110

    def test_replay_queue(self, manager: ReplayManager) -> None:
        manager.add_replay(_make_result())
        manager.add_replay(_make_result(confidence=0.60))
        queue = manager.get_replay_queue()
        assert len(queue) == 2


class TestChallenge:
    def test_challenge_request(self, manager: ReplayManager) -> None:
        manager.initialize_challenges(["team_a", "team_b"], count=1)
        result = _make_result()
        event = manager.request_challenge(result, "team_a")
        assert event is not None
        assert event.is_challenge is True

    def test_challenge_exhausted(self, manager: ReplayManager) -> None:
        """챌린지 소진 후 요청 불가."""
        manager.initialize_challenges(["team_a"], count=1)
        result = _make_result()
        manager.request_challenge(result, "team_a")
        assert manager.get_challenges_remaining("team_a") == 0
        second = manager.request_challenge(result, "team_a")
        assert second is None

    def test_challenge_success_refund(self, manager: ReplayManager) -> None:
        """챌린지 성공 시 환불."""
        manager.initialize_challenges(["team_a"], count=1)
        result = _make_result()
        event = manager.request_challenge(result, "team_a")
        assert event is not None
        # 챌린지 성공 (번복)
        manager.resolve_replay(event.replay_id, confirmed=False)
        assert manager.get_challenges_remaining("team_a") == 1


class TestResolve:
    def test_confirm_replay(self, manager: ReplayManager) -> None:
        event = manager.add_replay(_make_result())
        manager.resolve_replay(event.replay_id, confirmed=True)
        assert event.status == ReplayStatus.CONFIRMED

    def test_overturn_replay(self, manager: ReplayManager) -> None:
        event = manager.add_replay(_make_result())
        manager.resolve_replay(event.replay_id, confirmed=False)
        assert event.status == ReplayStatus.OVERTURNED


class TestReset:
    def test_reset(self, manager: ReplayManager) -> None:
        manager.add_replay(_make_result())
        manager.reset()
        assert len(manager.get_replay_queue()) == 0
