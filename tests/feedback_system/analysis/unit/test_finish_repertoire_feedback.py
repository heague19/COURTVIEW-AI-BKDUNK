# -*- coding: utf-8 -*-
"""feedback_system/analysis/finish_repertoire_feedback.py 단위 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from shared.dto.feedback_dto import FeedbackItem
from shared.dto.game_dto import ShotAttempt, ShotChart, ShotType, ShotResult, CourtZone

from feedback_system.analysis.finish_repertoire_feedback import (
    FinishRepertoireFeedbackConfig,
    FinishRepertoireFeedbackGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================
_TASK_ID = uuid4()


@pytest.fixture
def gen() -> FinishRepertoireFeedbackGenerator:
    return FinishRepertoireFeedbackGenerator()


@pytest.fixture
def shot_chart() -> ShotChart:
    """다양한 피니시 유형이 포함된 슛 차트."""
    shots = [
        # 페인트 존 레이업 성공
        ShotAttempt(
            player_tracking_id=1, shot_type=ShotType.LAYUP,
            result=ShotResult.MADE, court_zone=CourtZone.PAINT_CENTER,
            shot_x=0.05, shot_y=0.1, frame_number=100, timestamp=4.0,
            distance_meters=1.2, contest_level="contested", shot_quality=80.0,
        ),
        # 페인트 존 레이업 실패
        ShotAttempt(
            player_tracking_id=1, shot_type=ShotType.LAYUP,
            result=ShotResult.MISSED, court_zone=CourtZone.PAINT_CENTER,
            shot_x=0.1, shot_y=0.15, frame_number=300, timestamp=12.0,
            distance_meters=1.5, contest_level="heavily_contested", shot_quality=45.0,
        ),
        # 훅샷 성공
        ShotAttempt(
            player_tracking_id=2, shot_type=ShotType.HOOK_SHOT,
            result=ShotResult.MADE, court_zone=CourtZone.PAINT_CENTER,
            shot_x=-0.1, shot_y=0.08, frame_number=500, timestamp=20.0,
            distance_meters=2.0, contest_level="open", shot_quality=88.0,
        ),
        # 덩크 성공
        ShotAttempt(
            player_tracking_id=3, shot_type=ShotType.DUNK,
            result=ShotResult.MADE, court_zone=CourtZone.PAINT_CENTER,
            shot_x=0.0, shot_y=0.02, frame_number=700, timestamp=28.0,
            distance_meters=0.5, contest_level="open", shot_quality=95.0,
        ),
        # 미드레인지 (페인트 아님)
        ShotAttempt(
            player_tracking_id=1, shot_type=ShotType.JUMP_SHOT,
            result=ShotResult.MADE, court_zone=CourtZone.MID_LEFT_WING,
            shot_x=0.3, shot_y=0.4, frame_number=900, timestamp=36.0,
            distance_meters=4.5, contest_level="open", shot_quality=72.0,
        ),
        # 3점 (페인트 아님)
        ShotAttempt(
            player_tracking_id=2, shot_type=ShotType.THREE_POINTER,
            result=ShotResult.MISSED, court_zone=CourtZone.THREE_LEFT_WING,
            shot_x=-0.5, shot_y=0.7, frame_number=1100, timestamp=44.0,
            distance_meters=7.2, contest_level="contested", shot_quality=50.0,
        ),
        # 페인트 존 추가 레이업
        ShotAttempt(
            player_tracking_id=3, shot_type=ShotType.LAYUP,
            result=ShotResult.MADE, court_zone=CourtZone.PAINT_CENTER,
            shot_x=0.08, shot_y=0.12, frame_number=1300, timestamp=52.0,
            distance_meters=1.0, contest_level="open", shot_quality=90.0,
        ),
        # 플로터 성공
        ShotAttempt(
            player_tracking_id=1, shot_type=ShotType.FLOATER,
            result=ShotResult.MADE, court_zone=CourtZone.PAINT_CENTER,
            shot_x=0.15, shot_y=0.2, frame_number=1500, timestamp=60.0,
            distance_meters=2.5, contest_level="contested", shot_quality=70.0,
        ),
    ]
    return ShotChart(
        task_id=_TASK_ID,
        shots=shots,
        total_attempts=8,
        total_made=6,
        field_goal_percentage=75.0,
    )


@pytest.fixture
def empty_shot_chart() -> ShotChart:
    return ShotChart(
        task_id=uuid4(),
        shots=[],
        total_attempts=0,
        total_made=0,
        field_goal_percentage=0.0,
    )


# =============================================================================
# 테스트
# =============================================================================
class TestFinishRepertoireFeedbackConfig:
    def test_defaults(self) -> None:
        cfg = FinishRepertoireFeedbackConfig()
        assert cfg.paint_fg_pct_good == 55.0
        assert cfg.repertoire_good == 3

    def test_custom(self) -> None:
        cfg = FinishRepertoireFeedbackConfig(paint_fg_pct_good=60.0)
        assert cfg.paint_fg_pct_good == 60.0


class TestFinishRepertoireFeedbackGenerator:
    def test_name(self, gen: FinishRepertoireFeedbackGenerator) -> None:
        assert gen.name == "FinishRepertoireFeedbackGenerator"

    def test_generate_returns_items(
        self,
        gen: FinishRepertoireFeedbackGenerator,
        shot_chart: ShotChart,
    ) -> None:
        items = gen.generate(shot_chart)
        assert len(items) >= 5
        for item in items:
            assert isinstance(item, FeedbackItem)

    def test_paint_efficiency(
        self,
        gen: FinishRepertoireFeedbackGenerator,
        shot_chart: ShotChart,
    ) -> None:
        items = gen.generate(shot_chart)
        titles = [i.title for i in items]
        assert any("페인트" in t or "근거리" in t or "골밑" in t for t in titles)

    def test_repertoire_diversity(
        self,
        gen: FinishRepertoireFeedbackGenerator,
        shot_chart: ShotChart,
    ) -> None:
        items = gen.generate(shot_chart)
        titles = [i.title for i in items]
        assert any("레퍼토리" in t or "다양성" in t or "유형" in t for t in titles)

    def test_empty_chart(
        self,
        gen: FinishRepertoireFeedbackGenerator,
        empty_shot_chart: ShotChart,
    ) -> None:
        """슛 데이터 없음 → 기본 피드백 생성."""
        items = gen.generate(empty_shot_chart)
        assert len(items) >= 1

    def test_player_finish_profiles(
        self,
        gen: FinishRepertoireFeedbackGenerator,
        shot_chart: ShotChart,
    ) -> None:
        items = gen.generate(shot_chart)
        descs = [i.description for i in items]
        # 선수별 피니시 프로필 언급
        assert any("선수" in d or "P" in d for d in descs)

    def test_total_generated(
        self,
        gen: FinishRepertoireFeedbackGenerator,
        shot_chart: ShotChart,
    ) -> None:
        gen.generate(shot_chart)
        gen.generate(shot_chart)
        assert gen.total_generated == 2

    def test_reset(
        self,
        gen: FinishRepertoireFeedbackGenerator,
        shot_chart: ShotChart,
    ) -> None:
        gen.generate(shot_chart)
        gen.reset()
        assert gen.total_generated == 0

    def test_repr(self, gen: FinishRepertoireFeedbackGenerator) -> None:
        assert "FinishRepertoireFeedbackGenerator" in repr(gen)
