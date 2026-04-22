# -*- coding: utf-8 -*-
"""
shared/constants 단위 테스트.

김팀장 지시 §5-4:
- 임포트 성공, __all__ 일치, __version__ 1.0.0, annotations 포함
- Enum 멤버 수, @unique 중복 없음, i18n 5개국어
- 핵심 과학적 수치, 가중치 합 1.0, 상위 레이어 참조 0건
"""

from __future__ import annotations

import ast
import importlib
import inspect
from enum import Enum
from pathlib import Path
from typing import Final

import pytest


# =============================================================================
# 대상 서브모듈 목록
# =============================================================================
_CONSTANTS_DIR = Path(__file__).resolve().parent.parent.parent / "shared" / "constants"

_SUBMODULE_NAMES: Final[list[str]] = [
    p.stem for p in sorted(_CONSTANTS_DIR.glob("*.py"))
    if p.stem != "__init__" and not p.stem.startswith("_")
]


# =============================================================================
# 1. 임포트 성공
# =============================================================================
class TestImport:
    """패키지 및 서브모듈 임포트 테스트."""

    def test_package_import(self) -> None:
        """shared.constants 패키지 임포트 성공."""
        import shared.constants
        assert hasattr(shared.constants, "__all__")
        assert hasattr(shared.constants, "__version__")

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_import(self, name: str) -> None:
        """각 서브모듈 임포트 성공."""
        mod = importlib.import_module(f"shared.constants.{name}")
        assert mod is not None


# =============================================================================
# 2. __all__ 일치
# =============================================================================
class TestAllExport:
    """__all__ vs 실제 정의 일치 테스트."""

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_all_matches_definitions(self, name: str) -> None:
        """__all__ 목록의 모든 이름이 실제 모듈에 정의되어 있는지."""
        mod = importlib.import_module(f"shared.constants.{name}")
        all_names = getattr(mod, "__all__", [])
        for symbol in all_names:
            assert hasattr(mod, symbol), f"{name}.__all__에 '{symbol}' 선언되었으나 정의 없음"


# =============================================================================
# 3. __version__ 전수 1.0.0
# =============================================================================
class TestVersion:
    """__version__ 정책 준수 테스트."""

    def test_package_version(self) -> None:
        """패키지 __version__ == 1.0.0."""
        from shared.constants import __version__
        assert __version__ == "1.0.0"

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_version(self, name: str) -> None:
        """서브모듈 __version__ == 1.0.0."""
        mod = importlib.import_module(f"shared.constants.{name}")
        version = getattr(mod, "__version__", None)
        if version is not None:
            assert version == "1.0.0", f"{name}.__version__ = {version}"


# =============================================================================
# 4. from __future__ import annotations 포함
# =============================================================================
class TestAnnotations:
    """future annotations 포함 테스트."""

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_future_annotations(self, name: str) -> None:
        """from __future__ import annotations 포함."""
        filepath = _CONSTANTS_DIR / f"{name}.py"
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
# 5. Enum @unique 중복 값 없음
# =============================================================================
class TestEnumUnique:
    """Enum 클래스 중복 값 없음 테스트."""

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_enum_no_duplicate_values(self, name: str) -> None:
        """각 Enum의 멤버 값이 고유한지."""
        mod = importlib.import_module(f"shared.constants.{name}")
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if isinstance(obj, type) and issubclass(obj, Enum) and obj is not Enum:
                values = [m.value for m in obj]
                assert len(values) == len(set(values)), (
                    f"{name}.{attr_name}: 중복 Enum 값 발견"
                )


# =============================================================================
# 6. Enum 총 87개 클래스 존재
# =============================================================================
class TestEnumCount:
    """Enum 클래스 수 확인."""

    def test_total_enum_count(self) -> None:
        """전체 Enum 클래스 수 87개."""
        total = 0
        for name in _SUBMODULE_NAMES:
            mod = importlib.import_module(f"shared.constants.{name}")
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name)
                if isinstance(obj, type) and issubclass(obj, Enum) and obj is not Enum:
                    total += 1
        assert total == 103, f"Enum 클래스 총 {total}개 (예상: 103)"


# =============================================================================
# 7. 핵심 과학적 수치
# =============================================================================
class TestScientificValues:
    """FIBA/NBA 규정 기반 과학적 수치 검증."""

    def test_court_dimensions(self) -> None:
        """FIBA 코트 규격: 28m x 15m."""
        from shared.constants.court_constants import COURT_LENGTH_M, COURT_WIDTH_M
        assert COURT_LENGTH_M == 28.0
        assert COURT_WIDTH_M == 15.0

    def test_three_point_line(self) -> None:
        """FIBA 3점 라인: 6.75m."""
        from shared.constants.court_constants import THREE_POINT_LINE_DISTANCE_M
        assert THREE_POINT_LINE_DISTANCE_M == 6.75

    def test_hoop_height(self) -> None:
        """골대 높이: 3.05m."""
        from shared.constants.court_constants import HOOP_HEIGHT_M
        assert HOOP_HEIGHT_M == 3.05

    def test_hoop_diameter(self) -> None:
        """림 지름: 0.45m."""
        from shared.constants.court_constants import HOOP_DIAMETER_M
        assert HOOP_DIAMETER_M == 0.45

    def test_ball_diameter(self) -> None:
        """농구공 지름: 약 0.244m (FIBA 규정 7호 공)."""
        from shared.constants.ball_constants import BASKETBALL_DIAMETER_M
        assert 0.24 <= BASKETBALL_DIAMETER_M <= 0.25

    def test_free_throw_distance(self) -> None:
        """자유투 라인 거리: 4.6m."""
        from shared.constants.court_constants import FREE_THROW_LINE_DISTANCE_M
        assert FREE_THROW_LINE_DISTANCE_M == 4.6

    def test_backboard_dimensions(self) -> None:
        """백보드: 1.8m x 1.05m."""
        from shared.constants.court_constants import BACKBOARD_WIDTH_M, BACKBOARD_HEIGHT_M
        assert BACKBOARD_WIDTH_M == 1.8
        assert BACKBOARD_HEIGHT_M == 1.05


# =============================================================================
# 8. i18n get_name() 5개국어 반환
# =============================================================================
class TestI18n:
    """다국어 지원 테스트."""

    def test_supported_languages(self) -> None:
        """SupportedLanguage 5개국어."""
        from shared.constants.localization import SupportedLanguage
        assert len(SupportedLanguage) == 5
        values = {m.value for m in SupportedLanguage}
        assert values == {"ko", "en", "ja", "zh", "es"}

    def test_court_zone_i18n(self) -> None:
        """CourtZone Enum get_name 5개국어 문자열 반환."""
        from shared.constants.court_constants import CourtZone
        from shared.constants.localization import SupportedLanguage
        zone = list(CourtZone)[0]
        for lang in SupportedLanguage:
            name = zone.get_name(lang)
            assert isinstance(name, str) and len(name) > 0


# =============================================================================
# 9. 상위 레이어 참조 0건
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
        filepath = _CONSTANTS_DIR / f"{name}.py"
        source = filepath.read_text(encoding="utf-8")
        for pattern in self._UPPER_LAYERS:
            assert pattern not in source, (
                f"{name}.py에 상위 레이어 임포트 발견: {pattern}"
            )


# =============================================================================
# 10. 기능 테스트: Enum 멤버 접근 및 속성
# =============================================================================
class TestEnumFunctional:
    """Enum 멤버 실제 접근 및 속성 테스트."""

    def test_court_zone_is_three_point(self) -> None:
        """CourtZone 3점 구역 판별."""
        from shared.constants.court_constants import CourtZone
        assert CourtZone.THREE_LEFT_CORNER.is_three_point is True
        assert CourtZone.PAINT_LEFT.is_three_point is False

    def test_shot_type_values(self) -> None:
        """ShotType Enum 멤버 접근."""
        from shared.constants.game_rule_constants import ShotType
        assert ShotType.JUMP_SHOT.value == "jump_shot"
        assert ShotType.LAYUP.value == "layup"
        assert ShotType.DUNK.value == "dunk"

    def test_rule_set_members(self) -> None:
        """RuleSet Enum FIBA/NBA/KBL 존재."""
        from shared.constants.referee_rule_constants import RuleSet
        assert RuleSet.FIBA.value == "fiba"
        assert RuleSet.NBA.value == "nba"
        assert RuleSet.KBL.value == "kbl"

    def test_error_code_has_code_and_message(self) -> None:
        """ErrorCode 멤버에 code, message 속성 존재."""
        from shared.constants.error_codes import ErrorCode
        ec = ErrorCode.VALIDATION_ERROR
        assert hasattr(ec, "code")
        assert hasattr(ec, "message")
        assert isinstance(ec.code, int)
        assert isinstance(ec.message, str)

    def test_joint_type_coco_17(self) -> None:
        """JointType COCO 17 키포인트 존재."""
        from shared.constants.pose_constants import JointType
        assert JointType.NOSE.value == 0
        assert JointType.LEFT_ANKLE.value == 15
        assert JointType.RIGHT_ANKLE.value == 16

    def test_ball_state_properties(self) -> None:
        """BallState 속성 메서드."""
        from shared.constants.ball_constants import BallState
        assert BallState.SHOOTING.is_in_flight is True
        assert BallState.HELD.is_controlled is True
        assert BallState.LOST.is_in_flight is False


# =============================================================================
# 11. 기능 테스트: 가중치 합 1.0 검증
# =============================================================================
class TestWeightSums:
    """가중치 합계 1.0 검증."""

    def test_tracking_cost_weights(self) -> None:
        """트래킹 비용 가중치 합 1.0."""
        from shared.constants.tracking_constants import (
            APPEARANCE_COST_WEIGHT, MOTION_COST_WEIGHT,
        )
        assert abs(APPEARANCE_COST_WEIGHT + MOTION_COST_WEIGHT - 1.0) < 1e-9


# =============================================================================
# 12. 기능 테스트: CourtStandard별 3점 라인 거리
# =============================================================================
class TestCourtStandard:
    """코트 규격별 수치 검증."""

    def test_nba_three_point_distance(self) -> None:
        """NBA 3점 라인: 7.24m."""
        from shared.constants.court_constants import THREE_POINT_LINE_NBA_DISTANCE_M
        assert THREE_POINT_LINE_NBA_DISTANCE_M == 7.24

    def test_shot_clock(self) -> None:
        """샷클락: 24초."""
        from shared.constants.game_rule_constants import SHOT_CLOCK_SEC
        assert SHOT_CLOCK_SEC == 24
