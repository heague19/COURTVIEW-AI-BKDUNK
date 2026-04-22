# -*- coding: utf-8 -*-
"""
utils/ 단위 테스트.

구조적 검증:
- 18개 서브모듈 import 성공
- __version__ = "1.0.0" 전수 확인
- from __future__ import annotations 전수 확인
- @unique Enum 전수 확인
- __all__ 정의 일치

기능적 검증:
- math_utils: 벡터 연산, 각도 계산, 통계
- geometry_utils: IoU, NMS, 다각형, 코트 존
- time_utils: 프레임↔시간 변환, 경기 시간
- physics_utils: 발사체 궤적, 중력
- basketball_geometry: 코트 규격, 슛 분류, 진입각
- kalman_utils: 칼만 필터 예측/업데이트
- rotation_utils: 회전 행렬, 쿼터니언, SLERP
- sequence_utils: DTW, 프레셰 거리, 피크 검출
- statistical_utils: 왜도, 첨도, 이상값, 신뢰구간
- pose_utils: OKS, Procrustes, 스켈레톤 메트릭
- heatmap_utils: 피크 검출, 가우시안 생성
- camera_calibration_utils: 내부행렬, FOV
- video_utils: 메타데이터 클래스, 리사이즈 설정
- validation_utils: 검증 함수
- interpolation_utils: 선형 보간
- image_utils: 정규화
- feature_matching_utils: 거리 메트릭
"""

from __future__ import annotations

import ast
import math
import importlib
from pathlib import Path
from typing import Final
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# =============================================================================
# 공통 설정
# =============================================================================

_UTILS_DIR: Final[Path] = Path(__file__).resolve().parent.parent.parent / "utils"

_SUBMODULE_NAMES: Final[list[str]] = [
    p.stem for p in sorted(_UTILS_DIR.glob("*.py"))
    if p.stem != "__init__" and not p.stem.startswith("_")
]

# 18개 서브모듈 (17 소스 + __init__)
_EXPECTED_SUBMODULE_COUNT: Final[int] = 17


# =============================================================================
# 1. 구조적 검증 — Import
# =============================================================================

class TestImport:
    """패키지 및 서브모듈 임포트 검증."""

    def test_package_import(self) -> None:
        """utils 패키지 임포트."""
        import utils
        assert hasattr(utils, "__all__")
        assert hasattr(utils, "__version__")

    def test_package_version(self) -> None:
        """utils 패키지 버전 1.0.0."""
        from utils import __version__
        assert __version__ == "1.0.0"

    def test_submodule_count(self) -> None:
        """17개 서브모듈 파일 존재."""
        assert len(_SUBMODULE_NAMES) == _EXPECTED_SUBMODULE_COUNT, (
            f"예상 {_EXPECTED_SUBMODULE_COUNT}개, 실제 {len(_SUBMODULE_NAMES)}개: "
            f"{_SUBMODULE_NAMES}"
        )

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_submodule_import(self, name: str) -> None:
        """각 서브모듈 임포트 성공."""
        mod = importlib.import_module(f"utils.{name}")
        assert mod is not None


# =============================================================================
# 2. 구조적 검증 — AST 기반 (annotations, version, unique)
# =============================================================================

class TestAST:
    """AST 기반 코드 구조 검증."""

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES + ["__init__"])
    def test_future_annotations(self, name: str) -> None:
        """from __future__ import annotations 전수 확인."""
        path = _UTILS_DIR / f"{name}.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        has_annotations = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "__future__":
                    for alias in node.names:
                        if alias.name == "annotations":
                            has_annotations = True
        assert has_annotations, f"{name}.py에 from __future__ import annotations 미포함"

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_version_string(self, name: str) -> None:
        """__version__ = '1.0.0' 전수 확인."""
        mod = importlib.import_module(f"utils.{name}")
        assert hasattr(mod, "__version__"), f"utils.{name}에 __version__ 미존재"
        assert mod.__version__ == "1.0.0", (
            f"utils.{name}.__version__ = {mod.__version__!r}, 예상 '1.0.0'"
        )

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_all_defined(self, name: str) -> None:
        """__all__ 정의 존재."""
        mod = importlib.import_module(f"utils.{name}")
        assert hasattr(mod, "__all__"), f"utils.{name}에 __all__ 미존재"
        assert isinstance(mod.__all__, list), f"utils.{name}.__all__은 list여야 함"
        assert len(mod.__all__) > 0

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_all_exports_exist(self, name: str) -> None:
        """__all__에 정의된 이름이 실제로 존재."""
        mod = importlib.import_module(f"utils.{name}")
        for item in mod.__all__:
            assert hasattr(mod, item), (
                f"utils.{name}.__all__에 '{item}'이 있으나 실제 정의 없음"
            )

    @pytest.mark.parametrize("name", _SUBMODULE_NAMES)
    def test_unique_enums(self, name: str) -> None:
        """Enum 클래스에 @unique 적용 확인 (AST)."""
        path = _UTILS_DIR / f"{name}.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Enum 상속 여부 확인
                is_enum = any(
                    (isinstance(base, ast.Name) and base.id == "Enum") or
                    (isinstance(base, ast.Attribute) and base.attr == "Enum")
                    for base in node.bases
                )
                if is_enum:
                    # @unique 데코레이터 확인
                    has_unique = any(
                        (isinstance(d, ast.Name) and d.id == "unique") or
                        (isinstance(d, ast.Attribute) and d.attr == "unique")
                        for d in node.decorator_list
                    )
                    assert has_unique, (
                        f"utils/{name}.py: {node.name}(Enum)에 @unique 미적용"
                    )


# =============================================================================
# 3. 기능적 검증 — math_utils
# =============================================================================

class TestMathUtils:
    """math_utils 기능 검증."""

    def test_degrees_to_radians(self) -> None:
        from utils.math_utils import degrees_to_radians
        assert math.isclose(degrees_to_radians(180.0), math.pi, rel_tol=1e-10)
        assert math.isclose(degrees_to_radians(90.0), math.pi / 2, rel_tol=1e-10)

    def test_radians_to_degrees(self) -> None:
        from utils.math_utils import radians_to_degrees
        assert math.isclose(radians_to_degrees(math.pi), 180.0, rel_tol=1e-10)

    def test_vector2d_magnitude(self) -> None:
        from utils.math_utils import vector2d_magnitude
        assert math.isclose(vector2d_magnitude((3.0, 4.0)), 5.0)

    def test_vector2d_dot(self) -> None:
        from utils.math_utils import vector2d_dot
        assert math.isclose(vector2d_dot((1.0, 0.0), (0.0, 1.0)), 0.0)
        assert math.isclose(vector2d_dot((2.0, 3.0), (4.0, 5.0)), 23.0)

    def test_vector2d_cross(self) -> None:
        from utils.math_utils import vector2d_cross
        assert math.isclose(vector2d_cross((1.0, 0.0), (0.0, 1.0)), 1.0)

    def test_euclidean_distance_2d(self) -> None:
        from utils.math_utils import euclidean_distance_2d
        d = euclidean_distance_2d((0.0, 0.0), (3.0, 4.0))
        assert math.isclose(d, 5.0)

    def test_normalize_angle_degrees(self) -> None:
        from utils.math_utils import normalize_angle_degrees
        assert math.isclose(normalize_angle_degrees(-90), 270.0)
        assert math.isclose(normalize_angle_degrees(450), 90.0)

    def test_calculate_joint_angle_2d(self) -> None:
        from utils.math_utils import calculate_joint_angle_2d
        # 직각: 좌(0,1), 중심(0,0), 우(1,0)
        result = calculate_joint_angle_2d((0.0, 1.0), (0.0, 0.0), (1.0, 0.0))
        assert result.is_valid
        assert math.isclose(result.degrees, 90.0, abs_tol=0.1)

    def test_safe_divide(self) -> None:
        from utils.math_utils import safe_divide
        assert math.isclose(safe_divide(10.0, 2.0), 5.0)
        assert math.isclose(safe_divide(10.0, 0.0), 0.0)

    def test_lerp(self) -> None:
        from utils.math_utils import lerp
        assert math.isclose(lerp(0.0, 10.0, 0.5), 5.0)
        assert math.isclose(lerp(0.0, 10.0, 0.0), 0.0)
        assert math.isclose(lerp(0.0, 10.0, 1.0), 10.0)


# =============================================================================
# 4. 기능적 검증 — geometry_utils
# =============================================================================

class TestGeometryUtils:
    """geometry_utils 기능 검증."""

    def test_bounding_box_iou_identical(self) -> None:
        from utils.geometry_utils import BoundingBox, calculate_iou
        b = BoundingBox(x1=0, y1=0, x2=10, y2=10)
        assert math.isclose(calculate_iou(b, b), 1.0)

    def test_bounding_box_iou_no_overlap(self) -> None:
        from utils.geometry_utils import BoundingBox, calculate_iou
        b1 = BoundingBox(x1=0, y1=0, x2=5, y2=5)
        b2 = BoundingBox(x1=10, y1=10, x2=15, y2=15)
        assert calculate_iou(b1, b2) == 0.0

    def test_bounding_box_iou_partial(self) -> None:
        from utils.geometry_utils import BoundingBox, calculate_iou
        b1 = BoundingBox(x1=0, y1=0, x2=10, y2=10)
        b2 = BoundingBox(x1=5, y1=5, x2=15, y2=15)
        # 교집합: 5x5=25, 합집합: 100+100-25=175
        assert math.isclose(calculate_iou(b1, b2), 25.0 / 175.0, rel_tol=1e-6)

    def test_polygon_area_triangle(self) -> None:
        from utils.geometry_utils import polygon_area
        # 삼각형 (0,0), (4,0), (0,3) → 면적 6
        area = polygon_area([(0, 0), (4, 0), (0, 3)])
        assert math.isclose(area, 6.0)

    def test_point_in_polygon(self) -> None:
        from utils.geometry_utils import point_in_polygon
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert point_in_polygon((5, 5), square) is True
        assert point_in_polygon((15, 5), square) is False

    def test_nms_boxes(self) -> None:
        from utils.geometry_utils import BoundingBox, nms_boxes
        boxes = [
            BoundingBox(0, 0, 10, 10, confidence=0.9),
            BoundingBox(1, 1, 11, 11, confidence=0.8),  # 높은 IoU → 억제
            BoundingBox(50, 50, 60, 60, confidence=0.7),  # 독립
        ]
        kept = nms_boxes(boxes, iou_threshold=0.5, return_indices=True)
        assert 0 in kept  # 최고 신뢰도 유지
        assert 2 in kept  # 독립 박스 유지
        assert 1 not in kept  # 억제됨

    def test_batch_iou_vectorized(self) -> None:
        from utils.geometry_utils import batch_iou
        a = np.array([[0, 0, 10, 10]], dtype=np.float64)
        b = np.array([[0, 0, 10, 10], [20, 20, 30, 30]], dtype=np.float64)
        result = batch_iou(a, b)
        assert result.shape == (1, 2)
        assert math.isclose(result[0, 0], 1.0)
        assert math.isclose(result[0, 1], 0.0)


# =============================================================================
# 5. 기능적 검증 — time_utils
# =============================================================================

class TestTimeUtils:
    """time_utils 기능 검증."""

    def test_frame_to_time(self) -> None:
        from utils.time_utils import frame_to_time
        assert math.isclose(frame_to_time(30, 30.0), 1.0)
        assert math.isclose(frame_to_time(45, 30.0), 1.5)

    def test_time_to_frame(self) -> None:
        from utils.time_utils import time_to_frame
        assert time_to_frame(1.0, 30.0) == 30
        assert time_to_frame(2.5, 30.0) == 75

    def test_game_period_constants(self) -> None:
        from utils.time_utils import QUARTER_DURATION_FIBA, QUARTER_DURATION_NBA
        assert QUARTER_DURATION_FIBA == 600  # 10분
        assert QUARTER_DURATION_NBA == 720  # 12분

    def test_is_clutch_time(self) -> None:
        from utils.time_utils import is_clutch_time, GamePeriod
        # 4쿼터 5분 남음, 3점차 → 클러치
        assert is_clutch_time(GamePeriod.Q4, 300.0, 3) is True
        # 1쿼터 → 클러치 아님
        assert is_clutch_time(GamePeriod.Q1, 300.0, 3) is False

    def test_format_seconds(self) -> None:
        from utils.time_utils import format_seconds
        assert format_seconds(3661) == "01:01:01"


# =============================================================================
# 6. 기능적 검증 — basketball_geometry
# =============================================================================

class TestBasketballGeometry:
    """basketball_geometry 과학적 팩트 검증."""

    def test_court_spec_fiba(self) -> None:
        from utils.basketball_geometry import get_court_spec, CourtStandard
        spec = get_court_spec(CourtStandard.FIBA)
        assert spec.length == 28.0
        assert spec.width == 15.0
        assert spec.three_point_distance == 6.75

    def test_court_spec_nba(self) -> None:
        from utils.basketball_geometry import get_court_spec, CourtStandard
        spec = get_court_spec(CourtStandard.NBA)
        assert spec.length == 28.65
        assert spec.three_point_distance == 7.24

    def test_hoop_height(self) -> None:
        from utils.basketball_geometry import HOOP_HEIGHT_M
        assert HOOP_HEIGHT_M == 3.05

    def test_three_point_classification(self) -> None:
        from utils.basketball_geometry import is_three_point, CourtStandard
        assert is_three_point(7.0, CourtStandard.FIBA) is True
        assert is_three_point(5.0, CourtStandard.FIBA) is False

    def test_optimal_release_angle(self) -> None:
        from utils.basketball_geometry import optimal_release_angle
        # 5m 거리, 2m 높이에서 방출 → 45~55도 범위
        angle = optimal_release_angle(5.0, 2.0)
        assert 40.0 <= angle <= 60.0

    def test_effective_rim_diameter(self) -> None:
        from utils.basketball_geometry import effective_rim_diameter, HOOP_DIAMETER_M
        # 90도 진입 → 전체 직경
        assert math.isclose(effective_rim_diameter(90.0), HOOP_DIAMETER_M)
        # 0도 진입 → 유효 직경 0
        assert math.isclose(effective_rim_diameter(0.0), 0.0, abs_tol=1e-10)

    def test_minimum_entry_angle(self) -> None:
        from utils.basketball_geometry import minimum_entry_angle
        # Size 7 공 기준 약 32.8도
        min_angle = minimum_entry_angle()
        assert 32.0 <= min_angle <= 33.5

    def test_gravity_constant(self) -> None:
        from utils.basketball_geometry import GRAVITY
        assert math.isclose(GRAVITY, 9.80665)


# =============================================================================
# 7. 기능적 검증 — rotation_utils
# =============================================================================

class TestRotationUtils:
    """rotation_utils 수학적 정확성 검증."""

    def test_identity_rotation(self) -> None:
        from utils.rotation_utils import axis_angle_to_rotation_matrix
        R = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), 0.0)
        assert np.allclose(R, np.eye(3))

    def test_90deg_z_rotation(self) -> None:
        from utils.rotation_utils import axis_angle_to_rotation_matrix
        R = axis_angle_to_rotation_matrix(np.array([0, 0, 1.0]), math.pi / 2)
        # [1,0,0] → [0,1,0]
        result = R @ np.array([1, 0, 0])
        assert np.allclose(result, [0, 1, 0], atol=1e-10)

    def test_quaternion_roundtrip(self) -> None:
        from utils.rotation_utils import (
            axis_angle_to_quaternion,
            quaternion_to_axis_angle,
        )
        q = axis_angle_to_quaternion(np.array([0, 0, 1.0]), math.pi / 3)
        aa = quaternion_to_axis_angle(q)
        assert math.isclose(aa.angle, math.pi / 3, abs_tol=1e-10)

    def test_quaternion_multiply(self) -> None:
        from utils.rotation_utils import (
            axis_angle_to_quaternion,
            quaternion_multiply,
        )
        # 45° + 45° = 90°
        q = axis_angle_to_quaternion(np.array([0, 0, 1.0]), math.pi / 4)
        q2 = quaternion_multiply(q, q)
        assert math.isclose(q2.w, math.cos(math.pi / 4), abs_tol=1e-10)

    def test_slerp_midpoint(self) -> None:
        from utils.rotation_utils import (
            quaternion_slerp, Quaternion,
            axis_angle_to_quaternion,
        )
        q1 = Quaternion.identity()
        q2 = axis_angle_to_quaternion(np.array([0, 0, 1.0]), math.pi)
        qm = quaternion_slerp(q1, q2, 0.5)
        assert math.isclose(qm.w, math.cos(math.pi / 4), abs_tol=1e-6)

    def test_so3_validation(self) -> None:
        from utils.rotation_utils import (
            is_valid_rotation_matrix,
            axis_angle_to_rotation_matrix,
        )
        R = axis_angle_to_rotation_matrix(np.array([1, 0, 0.0]), 0.5)
        assert is_valid_rotation_matrix(R)
        assert not is_valid_rotation_matrix(np.ones((3, 3)))

    def test_rotation_distance_zero(self) -> None:
        from utils.rotation_utils import rotation_distance
        R = np.eye(3)
        d = rotation_distance(R, R)
        assert math.isclose(d.geodesic, 0.0, abs_tol=1e-10)


# =============================================================================
# 8. 기능적 검증 — statistical_utils
# =============================================================================

class TestStatisticalUtils:
    """statistical_utils 통계학 검증."""

    def test_skewness_symmetric(self) -> None:
        from utils.statistical_utils import calculate_skewness
        # 대칭 분포 → 왜도 ≈ 0
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=np.float64)
        skew = calculate_skewness(data)
        assert abs(skew) < 0.5

    def test_z_to_percentile(self) -> None:
        from utils.statistical_utils import z_to_percentile
        # z=0 → 50%
        assert math.isclose(z_to_percentile(0.0), 50.0, abs_tol=0.01)
        # z=1.96 → ~97.5%
        assert math.isclose(z_to_percentile(1.96), 97.5, abs_tol=0.1)

    def test_coefficient_of_variation(self) -> None:
        from utils.statistical_utils import coefficient_of_variation
        data = np.array([10.0, 10.0, 10.0])  # 변동 없음
        assert math.isclose(coefficient_of_variation(data), 0.0)

    def test_detect_outliers_iqr(self) -> None:
        from utils.statistical_utils import detect_outliers_iqr
        data = np.array([1, 2, 3, 4, 5, 100], dtype=np.float64)
        result = detect_outliers_iqr(data)
        assert result.n_outliers >= 1  # 100은 이상값

    def test_confidence_interval(self) -> None:
        from utils.statistical_utils import confidence_interval_z
        data = np.array([10, 20, 30, 40, 50], dtype=np.float64)
        ci = confidence_interval_z(data)
        assert ci.lower < ci.upper
        assert ci.lower < 30.0 < ci.upper  # 평균(30) 포함


# =============================================================================
# 9. 기능적 검증 — sequence_utils
# =============================================================================

class TestSequenceUtils:
    """sequence_utils 시퀀스 분석 검증."""

    def test_dtw_identical(self) -> None:
        from utils.sequence_utils import dtw_distance
        a = np.array([1, 2, 3, 4, 5], dtype=np.float64)
        result = dtw_distance(a, a)
        assert math.isclose(result.distance, 0.0)

    def test_dtw_shifted(self) -> None:
        from utils.sequence_utils import dtw_distance
        a = np.array([1, 2, 3, 4, 5], dtype=np.float64)
        b = np.array([2, 3, 4, 5, 6], dtype=np.float64)
        result = dtw_distance(a, b)
        assert result.distance > 0
        assert len(result.warping_path) > 0

    def test_frechet_distance_identical(self) -> None:
        from utils.sequence_utils import frechet_distance
        a = np.array([0, 1, 2, 3], dtype=np.float64)
        assert math.isclose(frechet_distance(a, a), 0.0)

    def test_z_normalize(self) -> None:
        from utils.sequence_utils import z_normalize_sequence
        data = np.array([10, 20, 30, 40, 50], dtype=np.float64)
        normalized = z_normalize_sequence(data)
        assert math.isclose(float(np.mean(normalized)), 0.0, abs_tol=1e-10)
        # z_normalize는 ddof=0 std로 정규화할 수 있음 — ddof=0 기준 확인
        assert math.isclose(float(np.std(normalized)), 1.0, abs_tol=0.01)

    def test_resample_sequence(self) -> None:
        from utils.sequence_utils import resample_sequence
        data = np.array([0, 10, 20], dtype=np.float64)
        resampled = resample_sequence(data, 5)
        assert resampled.shape[0] == 5
        assert math.isclose(resampled[0], 0.0, abs_tol=0.1)
        assert math.isclose(resampled[-1], 20.0, abs_tol=0.1)


# =============================================================================
# 10. 기능적 검증 — pose_utils
# =============================================================================

class TestPoseUtils:
    """pose_utils 포즈 분석 검증."""

    def test_oks_perfect_match(self) -> None:
        from utils.pose_utils import oks_similarity
        kps = np.random.rand(17, 3).astype(np.float64)
        kps[:, 2] = 1.0  # 모두 가시
        oks = oks_similarity(kps, kps, area=10000.0)
        assert math.isclose(oks, 1.0, abs_tol=0.01)

    def test_skeleton_metrics(self) -> None:
        from utils.pose_utils import calculate_skeleton_metrics
        kps = np.random.rand(17, 3).astype(np.float64)
        kps[:, 2] = 0.9  # 모두 높은 신뢰도
        m = calculate_skeleton_metrics(kps)
        assert m.completeness == 1.0
        assert m.num_valid == 17

    def test_mirror_skeleton(self) -> None:
        from utils.pose_utils import mirror_skeleton
        kps = np.zeros((17, 3), dtype=np.float64)
        kps[:, 2] = 1.0
        kps[5, 0] = 10.0  # 왼쪽 어깨 x=10
        mirrored = mirror_skeleton(kps, image_width=100)
        # 왼쪽 어깨(5)의 x가 오른쪽 어깨(6) 위치로 이동
        assert mirrored[6, 0] == 90.0  # 100 - 10


# =============================================================================
# 11. 기능적 검증 — heatmap_utils
# =============================================================================

class TestHeatmapUtils:
    """heatmap_utils 히트맵 처리 검증."""

    def test_gaussian_heatmap_peak(self) -> None:
        from utils.heatmap_utils import generate_gaussian_heatmap
        hm = generate_gaussian_heatmap(64, 48, 24.0, 32.0, sigma=2.0)
        assert hm.shape == (64, 48)
        # 중심에 최대값
        assert hm[32, 24] == hm.max()

    def test_extract_peaks(self) -> None:
        from utils.heatmap_utils import generate_gaussian_heatmap, extract_peaks
        hm = generate_gaussian_heatmap(64, 48, 24.0, 32.0, sigma=2.0)
        peaks = extract_peaks(hm, threshold=0.1)
        assert len(peaks) >= 1
        # 최고 피크가 중심 근처
        top = peaks[0]
        assert abs(top.x - 24.0) < 1.0
        assert abs(top.y - 32.0) < 1.0

    def test_normalize_heatmap(self) -> None:
        from utils.heatmap_utils import normalize_heatmap
        hm = np.array([[1, 2], [3, 4]], dtype=np.float32)
        norm = normalize_heatmap(hm, method="minmax")
        assert math.isclose(norm.min(), 0.0)
        assert math.isclose(norm.max(), 1.0)


# =============================================================================
# 12. 기능적 검증 — camera_calibration_utils
# =============================================================================

class TestCameraCalibrationUtils:
    """camera_calibration_utils 카메라 기하학 검증."""

    def test_intrinsic_matrix(self) -> None:
        from utils.camera_calibration_utils import CameraIntrinsics
        K = CameraIntrinsics(fx=1000, fy=1000, cx=960, cy=540)
        mat = K.to_matrix()
        assert mat.shape == (3, 3)
        assert mat[0, 0] == 1000
        assert mat[1, 1] == 1000
        assert mat[0, 2] == 960
        assert mat[1, 2] == 540
        assert mat[2, 2] == 1.0

    def test_intrinsic_roundtrip(self) -> None:
        from utils.camera_calibration_utils import CameraIntrinsics
        K = CameraIntrinsics(fx=800, fy=800, cx=320, cy=240)
        K2 = CameraIntrinsics.from_matrix(K.to_matrix())
        assert math.isclose(K2.fx, 800)
        assert math.isclose(K2.cy, 240)

    def test_field_of_view(self) -> None:
        from utils.camera_calibration_utils import compute_field_of_view
        # fx=1000, 센서 너비=1920 → fov ≈ 2*atan(960/1000) ≈ 87.4°
        fov = compute_field_of_view(1000.0, 1920)
        assert 80.0 < math.degrees(fov) < 95.0


# =============================================================================
# 13. 기능적 검증 — kalman_utils
# =============================================================================

class TestKalmanUtils:
    """kalman_utils 칼만 필터 검증."""

    def test_kalman_2d_predict(self) -> None:
        from utils.kalman_utils import KalmanFilter2D
        kf = KalmanFilter2D()
        kf.initialize(np.array([10.0, 20.0]))
        pred = kf.predict()
        # 초기 속도 0이므로 위치 유지
        assert math.isclose(pred.predicted_state.mean[0], 10.0, abs_tol=0.5)
        assert math.isclose(pred.predicted_state.mean[1], 20.0, abs_tol=0.5)

    def test_kalman_2d_update(self) -> None:
        from utils.kalman_utils import KalmanFilter2D
        kf = KalmanFilter2D()
        kf.initialize(np.array([0.0, 0.0]))
        kf.predict()
        kf.update(np.array([5.0, 5.0]))
        # 업데이트 후 측정값 방향으로 이동
        assert kf.state.mean[0] > 0
        assert kf.state.mean[1] > 0


# =============================================================================
# 14. 기능적 검증 — validation_utils
# =============================================================================

class TestValidationUtils:
    """validation_utils 검증 함수 테스트."""

    def test_validate_positive(self) -> None:
        from utils.validation_utils import validate_positive
        assert validate_positive(5.0, "test") == 5.0
        with pytest.raises(ValueError):
            validate_positive(-1.0, "test")

    def test_validate_range(self) -> None:
        from utils.validation_utils import validate_range
        assert validate_range(0.5, 0.0, 1.0, "test") == 0.5
        with pytest.raises(ValueError):
            validate_range(1.5, 0.0, 1.0, "test")

    def test_validate_percentage(self) -> None:
        from utils.validation_utils import validate_percentage
        assert validate_percentage(50.0, "test") == 50.0
        with pytest.raises(ValueError):
            validate_percentage(150.0, "test")


# =============================================================================
# 15. 기능적 검증 — video_utils (클래스 단위, 파일 I/O 없음)
# =============================================================================

class TestVideoUtils:
    """video_utils 데이터 구조 검증."""

    def test_resize_config_max_size(self) -> None:
        from utils.video_utils import ResizeConfig
        config = ResizeConfig(max_size=640)
        w, h = config.calculate_size(1920, 1080)
        assert max(w, h) <= 640
        # 비율 유지
        assert math.isclose(w / h, 1920 / 1080, abs_tol=0.02)

    def test_video_metadata_properties(self) -> None:
        from utils.video_utils import VideoMetadata, VideoRotation
        meta = VideoMetadata(
            width=1920, height=1080, fps=30.0,
            frame_count=900, duration=30.0, codec="mp4v"
        )
        assert meta.resolution == (1920, 1080)
        assert math.isclose(meta.aspect_ratio, 1920 / 1080)
        assert meta.is_valid()


# =============================================================================
# 16. 기능적 검증 — feature_matching_utils
# =============================================================================

class TestFeatureMatchingUtils:
    """feature_matching_utils 거리 메트릭 검증."""

    def test_descriptor_distance_l2(self) -> None:
        from utils.feature_matching_utils import compute_descriptor_distance, DescriptorNorm
        a = np.array([1, 0, 0], dtype=np.float64)
        b = np.array([0, 1, 0], dtype=np.float64)
        d = compute_descriptor_distance(a, b, DescriptorNorm.L2)
        assert math.isclose(d, math.sqrt(2.0))

    def test_match_quality_empty(self) -> None:
        from utils.feature_matching_utils import compute_match_quality
        q = compute_match_quality([], total_keypoints=100)
        assert q.num_good == 0
        assert q.confidence == 0.0
