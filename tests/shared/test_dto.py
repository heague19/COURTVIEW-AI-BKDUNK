# -*- coding: utf-8 -*-
"""
shared/dto 단위 테스트.

김팀장 지시 §5-4:
- 임포트 성공, __all__ 일치, __version__ 1.0.0, annotations 포함
- 각 DTO 인스턴스 생성 + 필수 필드 검증
- dataclass slots=True 확인 (21개)
- Pydantic frozen 적용 확인 (4개 파일)
- 별칭(as) 0건, 상수 re-export 0건
- 통계 공식 정확성 (TS%, eFG%, Game Score)
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Final

import pytest


# =============================================================================
# 대상 서브모듈 목록
# =============================================================================
_DTO_DIR = Path(__file__).resolve().parent.parent.parent / "shared" / "dto"

_SUBMODULE_NAMES: Final[list[str]] = [
    p.stem for p in sorted(_DTO_DIR.glob("*.py"))
    if p.stem != "__init__" and not p.stem.startswith("_")
]

# Pydantic 파일 (from __future__ import annotations 제외 대상)
_PYDANTIC_FILES: Final[set[str]] = {"pipeline_dto", "referee_dto", "feedback_dto", "game_dto"}

# dataclass 파일 (Pydantic 제외)
_DATACLASS_FILES: Final[list[str]] = [n for n in _SUBMODULE_NAMES if n not in _PYDANTIC_FILES]


# =============================================================================
# 1. 임포트 성공
# =============================================================================
class TestImport:
    """패키지 및 서브모듈 임포트 테스트."""

    def test_package_import(self) -> None:
        """shared.dto 패키지 임포트 성공."""
        from shared.dto import __all__, __version__
        assert len(__all__) > 0
        assert __version__ == "1.0.0"

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_import(self, name: str) -> None:
        """각 서브모듈 임포트 성공."""
        mod = importlib.import_module(f"shared.dto.{name}")
        assert mod is not None


# =============================================================================
# 2. __all__ 일치
# =============================================================================
class TestAllExport:
    """__all__ vs 실제 정의 일치 테스트."""

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_all_matches_definitions(self, name: str) -> None:
        """__all__ 목록의 모든 이름이 실제 모듈에 정의되어 있는지."""
        mod = importlib.import_module(f"shared.dto.{name}")
        all_names = getattr(mod, "__all__", [])
        for symbol in all_names:
            assert hasattr(mod, symbol), f"{name}.__all__에 '{symbol}' 선언되었으나 정의 없음"


# =============================================================================
# 3. __version__ 전수 1.0.0
# =============================================================================
class TestVersion:
    """__version__ 정책 준수 테스트."""

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_version(self, name: str) -> None:
        """서브모듈 __version__ == 1.0.0."""
        mod = importlib.import_module(f"shared.dto.{name}")
        version = getattr(mod, "__version__", None)
        if version is not None:
            assert version == "1.0.0", f"{name}.__version__ = {version}"


# =============================================================================
# 4. from __future__ import annotations (dataclass 파일만)
# =============================================================================
class TestAnnotations:
    """future annotations 포함 테스트 (dataclass 파일만)."""

    @pytest.mark.parametrize("name", _DATACLASS_FILES)
    def test_future_annotations(self, name: str) -> None:
        """dataclass 파일에 from __future__ import annotations 포함."""
        filepath = _DTO_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
        has_future = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in ast.walk(tree)
        )
        assert has_future, f"{name}.py에 from __future__ import annotations 없음"


# =============================================================================
# 5. dataclass slots=True 확인
# =============================================================================
class TestDataclassSlots:
    """dataclass slots=True 적용 테스트."""

    @pytest.mark.parametrize("name", _DATACLASS_FILES)
    def test_slots_true(self, name: str) -> None:
        """dataclass 파일에 slots=True 사용."""
        filepath = _DTO_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        # dataclass 데코레이터가 있으면 slots=True도 있어야 함
        if "@dataclass" in source:
            assert "slots=True" in source, f"{name}.py에 slots=True 없음"


# =============================================================================
# 6. Pydantic frozen 적용 확인
# =============================================================================
class TestPydanticFrozen:
    """Pydantic model_config frozen 테스트."""

    @pytest.mark.parametrize("name", list(_PYDANTIC_FILES))
    def test_frozen_config(self, name: str) -> None:
        """Pydantic 파일에 ConfigDict(frozen=True) 적용."""
        filepath = _DTO_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        if "BaseModel" in source:
            assert "ConfigDict(frozen=True)" in source, (
                f"{name}.py에 ConfigDict(frozen=True) 없음"
            )


# =============================================================================
# 7. __init__.py 별칭(as) 0건
# =============================================================================
class TestNoAlias:
    """__init__.py 별칭 없음 테스트."""

    def test_no_alias_in_init(self) -> None:
        """__init__.py에 'as' 별칭 0건."""
        init_path = _DTO_DIR / "__init__.py"
        source = init_path.read_text(encoding="utf-8")
        lines = source.split("\n")
        alias_lines = [
            line.strip() for line in lines
            if " as " in line and not line.strip().startswith("#")
        ]
        assert len(alias_lines) == 0, f"별칭 발견: {alias_lines}"


# =============================================================================
# 8. 상수 re-export 0건
# =============================================================================
class TestNoConstantReexport:
    """상수 Enum re-export 없음 테스트."""

    _CONSTANT_ENUMS = [
        "SupportedLanguage", "BallState", "BallSize", "ShotType",
        "OcclusionType", "OcclusionSeverity", "ResolutionStrategy",
        "ReIDModel", "MatchStatus", "JointType", "SkeletonType", "PoseQuality",
    ]

    def test_no_constant_reexport_in_init(self) -> None:
        """__init__.py __all__에 상수 Enum 없음."""
        from shared.dto import __all__
        for const_name in self._CONSTANT_ENUMS:
            assert const_name not in __all__, (
                f"__all__에 상수 '{const_name}' re-export 발견"
            )


# =============================================================================
# 9. 통계 공식 정확성
# =============================================================================
class TestStatisticsFormulas:
    """game_dto 통계 공식 테스트."""

    def test_effective_field_goal_percentage(self) -> None:
        """eFG% = (FGM + 0.5 * 3PM) / FGA * 100."""
        from shared.dto.game_dto import PlayerStats
        stats = PlayerStats(
            player_tracking_id=1,
            field_goals_made=10,
            field_goals_attempted=20,
            three_pointers_made=4,
        )
        efg = stats.calculate_effective_field_goal_percentage()
        expected = (10 + 0.5 * 4) / 20 * 100  # 60.0
        assert abs(efg - expected) < 0.1

    def test_true_shooting_percentage(self) -> None:
        """TS% = PTS / (2 * (FGA + 0.44 * FTA)) * 100."""
        from shared.dto.game_dto import PlayerStats
        stats = PlayerStats(
            player_tracking_id=1,
            points=25,
            field_goals_attempted=20,
            free_throws_attempted=5,
        )
        ts = stats.calculate_true_shooting_percentage()
        expected = 25 / (2 * (20 + 0.44 * 5)) * 100
        assert abs(ts - expected) < 0.2

    def test_game_score(self) -> None:
        """Game Score (Hollinger) 공식 검증."""
        from shared.dto.game_dto import PlayerStats
        stats = PlayerStats(
            player_tracking_id=1,
            points=30, field_goals_made=12, field_goals_attempted=22,
            free_throws_made=4, free_throws_attempted=5,
            offensive_rebounds=2, defensive_rebounds=8,
            assists=5, steals=2, blocks=1,
            personal_fouls=3, turnovers=3,
        )
        gs = stats.calculate_game_score()
        expected = (
            30 + 0.4 * 12 - 0.7 * 22
            - 0.4 * (5 - 4)
            + 0.7 * 2 + 0.3 * 8
            + 2 + 0.7 * 5 + 0.7 * 1
            - 0.4 * 3 - 3
        )
        assert abs(gs - round(expected, 1)) < 0.2


# =============================================================================
# 10. 상위 레이어 참조 0건
# =============================================================================
class TestNoUpperLayerImport:
    """상위 레이어 임포트 금지 테스트."""

    _UPPER_LAYERS = (
        "from utils", "from core_foundation", "from infrastructure",
        "from detection", "from pose_estimation", "from biomechanics",
        "from motion_analysis", "from game_analysis", "from ai_referee",
        "from feedback_system",
    )

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_no_upper_layer_import(self, name: str) -> None:
        """상위 레이어 임포트 없음."""
        filepath = _DTO_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        for pattern in self._UPPER_LAYERS:
            assert pattern not in source, (
                f"{name}.py에 상위 레이어 임포트 발견: {pattern}"
            )


# =============================================================================
# 11. DTO 인스턴스 생성 테스트
# =============================================================================
class TestDtoInstantiation:
    """DTO 인스턴스 생성 및 필드 검증."""

    def test_bounding_box(self) -> None:
        """BoundingBox 생성 및 area 계산."""
        from shared.dto.geometry_dto import BoundingBox
        bbox = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
        assert bbox.area == 5000.0
        assert bbox.center.x == 60.0
        assert bbox.center.y == 45.0

    def test_bounding_box_iou(self) -> None:
        """BoundingBox IoU 계산."""
        from shared.dto.geometry_dto import BoundingBox
        a = BoundingBox(x=0, y=0, width=10, height=10)
        b = BoundingBox(x=5, y=5, width=10, height=10)
        iou = a.iou(b)
        # 교집합: 5x5=25, 합집합: 100+100-25=175
        assert abs(iou - 25 / 175) < 0.01

    def test_bounding_box_no_overlap(self) -> None:
        """겹치지 않는 BoundingBox IoU == 0."""
        from shared.dto.geometry_dto import BoundingBox
        a = BoundingBox(x=0, y=0, width=10, height=10)
        b = BoundingBox(x=20, y=20, width=10, height=10)
        assert a.iou(b) == 0.0

    def test_point2d_distance(self) -> None:
        """Point2D 유클리드 거리."""
        from shared.dto.geometry_dto import Point2D
        p1 = Point2D(x=0.0, y=0.0)
        p2 = Point2D(x=3.0, y=4.0)
        assert abs(p1.distance_to(p2) - 5.0) < 1e-6

    def test_point3d_distance(self) -> None:
        """Point3D 유클리드 거리."""
        from shared.dto.geometry_dto import Point3D
        p1 = Point3D(x=0.0, y=0.0, z=0.0)
        p2 = Point3D(x=1.0, y=2.0, z=2.0)
        assert abs(p1.distance_to(p2) - 3.0) < 1e-6

    def test_vector3d_magnitude(self) -> None:
        """Vector3D 크기."""
        from shared.dto.geometry_dto import Vector3D
        v = Vector3D(x=3.0, y=4.0, z=0.0)
        assert abs(v.magnitude - 5.0) < 1e-6

    def test_vector3d_normalized(self) -> None:
        """Vector3D 정규화 크기 1.0."""
        from shared.dto.geometry_dto import Vector3D
        v = Vector3D(x=3.0, y=4.0, z=0.0)
        n = v.normalized
        assert abs(n.magnitude - 1.0) < 1e-6

    def test_win_probability_post_init(self) -> None:
        """WinProbability away_wp 자동 계산."""
        from shared.dto.prediction_dto import WinProbability
        wp = WinProbability(home_wp=60.0)
        assert wp.away_wp == 40.0
        # 60%는 clutch 범위(40~60%) 내 → True
        assert wp.is_clutch_time is True

    def test_win_probability_clutch(self) -> None:
        """WinProbability 클러치 타임 (40~60%)."""
        from shared.dto.prediction_dto import WinProbability
        wp = WinProbability(home_wp=50.0)
        assert wp.is_clutch_time is True

    def test_clock_state_display(self) -> None:
        """ClockState 시계 표시."""
        from shared.dto.game_management_dto import ClockState
        clock = ClockState(game_clock_seconds=125.0)
        assert clock.game_clock_display == "02:05"

    def test_trajectory_type_is_flight(self) -> None:
        """TrajectoryType 비행 여부."""
        from shared.dto.ball_dto import TrajectoryType
        assert TrajectoryType.SHOT.is_flight is True
        assert TrajectoryType.DRIBBLE.is_flight is False


# =============================================================================
# 12. Pydantic 필드 검증 테스트
# =============================================================================
class TestPydanticValidation:
    """Pydantic 모델 필드 검증."""

    def test_pipeline_options_quality_pattern(self) -> None:
        """PipelineOptions quality 패턴 검증."""
        from pydantic import ValidationError
        from shared.dto.pipeline_dto import PipelineOptions
        # 정상
        opt = PipelineOptions(quality="high")
        assert opt.quality == "high"
        # 잘못된 값
        with pytest.raises(ValidationError):
            PipelineOptions(quality="invalid_quality")

    def test_pipeline_options_time_range(self) -> None:
        """PipelineOptions end_time > start_time 검증."""
        from pydantic import ValidationError
        from shared.dto.pipeline_dto import PipelineOptions
        with pytest.raises(ValidationError):
            PipelineOptions(start_time=10.0, end_time=5.0)

    def test_video_metadata_source_path_required(self) -> None:
        """VideoMetadata source_path 필수."""
        from pydantic import ValidationError
        from shared.dto.pipeline_dto import VideoMetadata
        with pytest.raises(ValidationError):
            VideoMetadata(source_path="")

    def test_zone_statistics_consistency(self) -> None:
        """ZoneStatistics made <= attempts 검증."""
        from pydantic import ValidationError
        from shared.dto.game_dto import ZoneStatistics, CourtZone
        with pytest.raises(ValidationError):
            ZoneStatistics(zone=CourtZone.PAINT_LEFT, attempts=5, made=10, percentage=200.0)


# =============================================================================
# 13. 더블더블/트리플더블 테스트
# =============================================================================
class TestPlayerStatsAchievements:
    """선수 통계 성취 테스트."""

    def test_double_double(self) -> None:
        """더블더블 판별."""
        from shared.dto.game_dto import PlayerStats
        stats = PlayerStats(
            player_tracking_id=1,
            points=20, total_rebounds=10,
        )
        assert stats.is_double_double() is True

    def test_not_double_double(self) -> None:
        """더블더블 미달."""
        from shared.dto.game_dto import PlayerStats
        stats = PlayerStats(
            player_tracking_id=1,
            points=9, total_rebounds=9,
        )
        assert stats.is_double_double() is False

    def test_triple_double(self) -> None:
        """트리플더블 판별."""
        from shared.dto.game_dto import PlayerStats
        stats = PlayerStats(
            player_tracking_id=1,
            points=15, total_rebounds=12, assists=11,
        )
        assert stats.is_triple_double() is True
