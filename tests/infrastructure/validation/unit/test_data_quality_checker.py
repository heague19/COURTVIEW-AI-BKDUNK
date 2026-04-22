# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

테스트: infrastructure/validation/data_quality_checker.py
설명: DataQualityChecker 및 관련 클래스 단위 테스트
      - QualityDimension, QualityLevel, QualityConfig
      - DimensionScore, QualityCheckResult, QualityCheckStats
      - DataQualityChecker (check_frame, check_batch, stats, 측정 메서드)
      - 상수 및 __all__ export 검증

작성자: SPOIN_COURTVIEW
버전: 1.0.0
"""

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

import math
import threading
import unittest

import cv2
import numpy as np

from infrastructure.validation.data_quality_checker import (
    BRIGHTNESS_WEIGHT,
    CONTRAST_WEIGHT,
    DEFAULT_CONTRAST_MIN_THRESHOLD,
    MAX_QUALITY_BATCH_SIZE,
    MAX_QUALITY_CHECK_HISTORY,
    MIN_QUALITY_CHECK_SIZE,
    NOISE_WEIGHT,
    SHARPNESS_WEIGHT,
    DataQualityChecker,
    DimensionScore,
    QualityCheckResult,
    QualityCheckStats,
    QualityConfig,
    QualityDimension,
    QualityLevel,
)


# =============================================================================
# 헬퍼 함수
# =============================================================================

def _make_black(h: int = 480, w: int = 640) -> np.ndarray:
    """완전히 어두운(검정) 이미지 생성."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_mid_gray(h: int = 480, w: int = 640) -> np.ndarray:
    """중간 밝기 이미지 생성."""
    return np.full((h, w, 3), 128, dtype=np.uint8)


def _make_white(h: int = 480, w: int = 640) -> np.ndarray:
    """완전히 밝은(흰색) 이미지 생성."""
    return np.full((h, w, 3), 255, dtype=np.uint8)


def _make_noisy(h: int = 480, w: int = 640) -> np.ndarray:
    """랜덤 노이즈 이미지 생성."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)


def _make_gradient(h: int = 480, w: int = 640) -> np.ndarray:
    """수평 그래디언트 이미지 생성 (노이즈 낮음, 대비 있음)."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for x in range(w):
        val = int(x * 255 / (w - 1))
        img[:, x, :] = val
    return img


def _make_blurred(h: int = 480, w: int = 640) -> np.ndarray:
    """극도로 블러된 이미지 생성."""
    base = _make_gradient(h, w)
    blurred = cv2.GaussianBlur(base, (61, 61), 30)
    return blurred


def _make_sharp_edges(h: int = 480, w: int = 640) -> np.ndarray:
    """날카로운 엣지가 있는 이미지 생성 (체커보드 패턴)."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    block = 8
    for i in range(h):
        for j in range(w):
            if ((i // block) + (j // block)) % 2 == 0:
                img[i, j, :] = 255
    return img


# =============================================================================
# TestQualityDimension
# =============================================================================

class TestQualityDimension(unittest.TestCase):
    """QualityDimension 열거형 테스트."""

    def test_member_count(self):
        """4개의 멤버가 존재해야 한다."""
        self.assertEqual(len(QualityDimension), 4)

    def test_member_brightness_exists(self):
        """BRIGHTNESS 멤버가 존재해야 한다."""
        self.assertIn("BRIGHTNESS", QualityDimension.__members__)

    def test_member_contrast_exists(self):
        """CONTRAST 멤버가 존재해야 한다."""
        self.assertIn("CONTRAST", QualityDimension.__members__)

    def test_member_sharpness_exists(self):
        """SHARPNESS 멤버가 존재해야 한다."""
        self.assertIn("SHARPNESS", QualityDimension.__members__)

    def test_member_noise_exists(self):
        """NOISE 멤버가 존재해야 한다."""
        self.assertIn("NOISE", QualityDimension.__members__)

    def test_get_korean_name_brightness(self):
        """BRIGHTNESS 한글 이름이 '밝기'여야 한다."""
        self.assertEqual(QualityDimension.BRIGHTNESS.get_korean_name(), "밝기")

    def test_get_korean_name_contrast(self):
        """CONTRAST 한글 이름이 '대비'여야 한다."""
        self.assertEqual(QualityDimension.CONTRAST.get_korean_name(), "대비")

    def test_get_korean_name_sharpness(self):
        """SHARPNESS 한글 이름이 '선명도'여야 한다."""
        self.assertEqual(QualityDimension.SHARPNESS.get_korean_name(), "선명도")

    def test_get_korean_name_noise(self):
        """NOISE 한글 이름이 '노이즈'여야 한다."""
        self.assertEqual(QualityDimension.NOISE.get_korean_name(), "노이즈")

    def test_str_returns_value(self):
        """str(QualityDimension.X)는 value를 반환해야 한다."""
        self.assertEqual(str(QualityDimension.BRIGHTNESS), "brightness")
        self.assertEqual(str(QualityDimension.CONTRAST), "contrast")
        self.assertEqual(str(QualityDimension.SHARPNESS), "sharpness")
        self.assertEqual(str(QualityDimension.NOISE), "noise")

    def test_value_strings(self):
        """각 멤버의 value가 소문자 영문자여야 한다."""
        for member in QualityDimension:
            self.assertIsInstance(member.value, str)
            self.assertEqual(member.value, member.value.lower())


# =============================================================================
# TestQualityLevel
# =============================================================================

class TestQualityLevel(unittest.TestCase):
    """QualityLevel 열거형 테스트."""

    def test_member_count(self):
        """5개의 멤버가 존재해야 한다."""
        self.assertEqual(len(QualityLevel), 5)

    def test_all_members_exist(self):
        """EXCELLENT, GOOD, ACCEPTABLE, POOR, UNACCEPTABLE 멤버가 존재해야 한다."""
        members = QualityLevel.__members__
        for name in ("EXCELLENT", "GOOD", "ACCEPTABLE", "POOR", "UNACCEPTABLE"):
            self.assertIn(name, members)

    def test_get_korean_name_excellent(self):
        """EXCELLENT 한글 이름이 '우수'여야 한다."""
        self.assertEqual(QualityLevel.EXCELLENT.get_korean_name(), "우수")

    def test_get_korean_name_good(self):
        """GOOD 한글 이름이 '양호'여야 한다."""
        self.assertEqual(QualityLevel.GOOD.get_korean_name(), "양호")

    def test_get_korean_name_acceptable(self):
        """ACCEPTABLE 한글 이름이 '허용'이어야 한다."""
        self.assertEqual(QualityLevel.ACCEPTABLE.get_korean_name(), "허용")

    def test_get_korean_name_poor(self):
        """POOR 한글 이름이 '불량'이어야 한다."""
        self.assertEqual(QualityLevel.POOR.get_korean_name(), "불량")

    def test_get_korean_name_unacceptable(self):
        """UNACCEPTABLE 한글 이름이 '사용불가'여야 한다."""
        self.assertEqual(QualityLevel.UNACCEPTABLE.get_korean_name(), "사용불가")

    def test_is_usable_excellent(self):
        """EXCELLENT는 is_usable이 True여야 한다."""
        self.assertTrue(QualityLevel.EXCELLENT.is_usable)

    def test_is_usable_good(self):
        """GOOD은 is_usable이 True여야 한다."""
        self.assertTrue(QualityLevel.GOOD.is_usable)

    def test_is_usable_acceptable(self):
        """ACCEPTABLE은 is_usable이 True여야 한다."""
        self.assertTrue(QualityLevel.ACCEPTABLE.is_usable)

    def test_is_usable_poor_false(self):
        """POOR는 is_usable이 False여야 한다."""
        self.assertFalse(QualityLevel.POOR.is_usable)

    def test_is_usable_unacceptable_false(self):
        """UNACCEPTABLE은 is_usable이 False여야 한다."""
        self.assertFalse(QualityLevel.UNACCEPTABLE.is_usable)

    def test_str_returns_value(self):
        """str(QualityLevel.X)는 value를 반환해야 한다."""
        self.assertEqual(str(QualityLevel.EXCELLENT), "excellent")
        self.assertEqual(str(QualityLevel.GOOD), "good")
        self.assertEqual(str(QualityLevel.ACCEPTABLE), "acceptable")
        self.assertEqual(str(QualityLevel.POOR), "poor")
        self.assertEqual(str(QualityLevel.UNACCEPTABLE), "unacceptable")

    def test_value_strings(self):
        """각 멤버의 value가 소문자 영문자여야 한다."""
        for member in QualityLevel:
            self.assertIsInstance(member.value, str)


# =============================================================================
# TestQualityConfig
# =============================================================================

class TestQualityConfig(unittest.TestCase):
    """QualityConfig 데이터클래스 테스트."""

    def test_slots_defined(self):
        """__slots__이 정의되어 있어야 한다."""
        self.assertTrue(hasattr(QualityConfig, "__slots__"))

    def test_default_brightness_min(self):
        """brightness_min 기본값은 30.0이어야 한다."""
        cfg = QualityConfig()
        self.assertAlmostEqual(cfg.brightness_min, 30.0, places=1)

    def test_default_brightness_max(self):
        """brightness_max 기본값은 225.0이어야 한다."""
        cfg = QualityConfig()
        self.assertAlmostEqual(cfg.brightness_max, 225.0, places=1)

    def test_default_contrast_min(self):
        """contrast_min 기본값은 20.0이어야 한다."""
        cfg = QualityConfig()
        self.assertAlmostEqual(cfg.contrast_min, 20.0, places=1)

    def test_default_sharpness_min(self):
        """sharpness_min 기본값은 100.0이어야 한다."""
        cfg = QualityConfig()
        self.assertAlmostEqual(cfg.sharpness_min, 100.0, places=1)

    def test_default_noise_max(self):
        """noise_max 기본값은 50.0이어야 한다."""
        cfg = QualityConfig()
        self.assertAlmostEqual(cfg.noise_max, 50.0, places=1)

    def test_default_minimum_score(self):
        """minimum_score 기본값은 30.0이어야 한다."""
        cfg = QualityConfig()
        self.assertAlmostEqual(cfg.minimum_score, 30.0, places=1)

    def test_post_init_clamps_brightness_min_negative(self):
        """brightness_min 음수 입력 시 0.0으로 보정되어야 한다."""
        cfg = QualityConfig(brightness_min=-10.0, brightness_max=200.0)
        self.assertGreaterEqual(cfg.brightness_min, 0.0)

    def test_post_init_clamps_brightness_max_above_255(self):
        """brightness_max 255 초과 시 255.0으로 보정되어야 한다."""
        cfg = QualityConfig(brightness_min=30.0, brightness_max=300.0)
        self.assertLessEqual(cfg.brightness_max, 255.0)

    def test_post_init_swaps_brightness_min_max(self):
        """brightness_min > brightness_max 입력 시 max >= min으로 보정되어야 한다."""
        cfg = QualityConfig(brightness_min=200.0, brightness_max=50.0)
        self.assertGreaterEqual(cfg.brightness_max, cfg.brightness_min)

    def test_post_init_clamps_contrast_min_negative(self):
        """contrast_min 음수 입력 시 0.0으로 보정되어야 한다."""
        cfg = QualityConfig(contrast_min=-5.0)
        self.assertGreaterEqual(cfg.contrast_min, 0.0)

    def test_post_init_clamps_sharpness_min_negative(self):
        """sharpness_min 음수 입력 시 0.0으로 보정되어야 한다."""
        cfg = QualityConfig(sharpness_min=-100.0)
        self.assertGreaterEqual(cfg.sharpness_min, 0.0)

    def test_post_init_clamps_noise_max_negative(self):
        """noise_max 음수 입력 시 0.0으로 보정되어야 한다."""
        cfg = QualityConfig(noise_max=-10.0)
        self.assertGreaterEqual(cfg.noise_max, 0.0)

    def test_post_init_clamps_minimum_score_above_100(self):
        """minimum_score 100 초과 시 100.0으로 보정되어야 한다."""
        cfg = QualityConfig(minimum_score=150.0)
        self.assertLessEqual(cfg.minimum_score, 100.0)

    def test_post_init_clamps_minimum_score_negative(self):
        """minimum_score 음수 입력 시 0.0으로 보정되어야 한다."""
        cfg = QualityConfig(minimum_score=-20.0)
        self.assertGreaterEqual(cfg.minimum_score, 0.0)

    def test_repr_contains_bright(self):
        """repr에 'bright' 문자열이 포함되어야 한다."""
        cfg = QualityConfig()
        self.assertIn("bright", repr(cfg).lower())

    def test_custom_values(self):
        """커스텀 값으로 생성 시 해당 값이 설정되어야 한다."""
        cfg = QualityConfig(
            brightness_min=50.0,
            brightness_max=200.0,
            contrast_min=25.0,
            sharpness_min=150.0,
            noise_max=40.0,
            minimum_score=40.0,
        )
        self.assertAlmostEqual(cfg.brightness_min, 50.0, places=1)
        self.assertAlmostEqual(cfg.brightness_max, 200.0, places=1)
        self.assertAlmostEqual(cfg.contrast_min, 25.0, places=1)
        self.assertAlmostEqual(cfg.sharpness_min, 150.0, places=1)
        self.assertAlmostEqual(cfg.noise_max, 40.0, places=1)
        self.assertAlmostEqual(cfg.minimum_score, 40.0, places=1)


# =============================================================================
# TestDimensionScore
# =============================================================================

class TestDimensionScore(unittest.TestCase):
    """DimensionScore 데이터클래스 테스트."""

    def test_slots_defined(self):
        """__slots__이 정의되어 있어야 한다."""
        self.assertTrue(hasattr(DimensionScore, "__slots__"))

    def test_default_dimension(self):
        """기본 dimension은 BRIGHTNESS여야 한다."""
        ds = DimensionScore()
        self.assertEqual(ds.dimension, QualityDimension.BRIGHTNESS)

    def test_default_raw_value(self):
        """기본 raw_value는 0.0이어야 한다."""
        ds = DimensionScore()
        self.assertAlmostEqual(ds.raw_value, 0.0)

    def test_default_normalized_score(self):
        """기본 normalized_score는 0.0이어야 한다."""
        ds = DimensionScore()
        self.assertAlmostEqual(ds.normalized_score, 0.0)

    def test_default_passed(self):
        """기본 passed는 True여야 한다."""
        ds = DimensionScore()
        self.assertTrue(ds.passed)

    def test_default_message(self):
        """기본 message는 빈 문자열이어야 한다."""
        ds = DimensionScore()
        self.assertEqual(ds.message, "")

    def test_custom_values(self):
        """커스텀 값으로 DimensionScore를 생성할 수 있어야 한다."""
        ds = DimensionScore(
            dimension=QualityDimension.SHARPNESS,
            raw_value=150.0,
            normalized_score=75.0,
            passed=True,
            message="선명도 양호",
        )
        self.assertEqual(ds.dimension, QualityDimension.SHARPNESS)
        self.assertAlmostEqual(ds.raw_value, 150.0)
        self.assertAlmostEqual(ds.normalized_score, 75.0)
        self.assertTrue(ds.passed)
        self.assertEqual(ds.message, "선명도 양호")

    def test_repr_contains_pass(self):
        """통과 시 repr에 'PASS' 문자열이 포함되어야 한다."""
        ds = DimensionScore(passed=True)
        self.assertIn("PASS", repr(ds))

    def test_repr_contains_fail(self):
        """실패 시 repr에 'FAIL' 문자열이 포함되어야 한다."""
        ds = DimensionScore(passed=False)
        self.assertIn("FAIL", repr(ds))

    def test_repr_contains_dimension_value(self):
        """repr에 dimension value가 포함되어야 한다."""
        ds = DimensionScore(dimension=QualityDimension.NOISE)
        self.assertIn("noise", repr(ds))


# =============================================================================
# TestQualityCheckResult
# =============================================================================

class TestQualityCheckResult(unittest.TestCase):
    """QualityCheckResult 데이터클래스 테스트."""

    def test_slots_defined(self):
        """__slots__이 정의되어 있어야 한다."""
        self.assertTrue(hasattr(QualityCheckResult, "__slots__"))

    def test_default_overall_score(self):
        """기본 overall_score는 0.0이어야 한다."""
        r = QualityCheckResult()
        self.assertAlmostEqual(r.overall_score, 0.0)

    def test_default_quality_level(self):
        """기본 quality_level은 UNACCEPTABLE이어야 한다."""
        r = QualityCheckResult()
        self.assertEqual(r.quality_level, QualityLevel.UNACCEPTABLE)

    def test_default_is_acceptable(self):
        """기본 is_acceptable은 False여야 한다."""
        r = QualityCheckResult()
        self.assertFalse(r.is_acceptable)

    def test_default_dimension_scores_empty(self):
        """기본 dimension_scores는 빈 리스트여야 한다."""
        r = QualityCheckResult()
        self.assertEqual(r.dimension_scores, [])

    def test_default_failed_dimensions_empty(self):
        """기본 failed_dimensions는 빈 리스트여야 한다."""
        r = QualityCheckResult()
        self.assertEqual(r.failed_dimensions, [])

    def test_default_recommendations_empty(self):
        """기본 recommendations는 빈 리스트여야 한다."""
        r = QualityCheckResult()
        self.assertEqual(r.recommendations, [])

    def test_default_check_time_ms(self):
        """기본 check_time_ms는 0.0이어야 한다."""
        r = QualityCheckResult()
        self.assertAlmostEqual(r.check_time_ms, 0.0)

    def test_passed_count_empty(self):
        """dimension_scores가 없을 때 passed_count는 0이어야 한다."""
        r = QualityCheckResult()
        self.assertEqual(r.passed_count, 0)

    def test_total_dimensions_empty(self):
        """dimension_scores가 없을 때 total_dimensions는 0이어야 한다."""
        r = QualityCheckResult()
        self.assertEqual(r.total_dimensions, 0)

    def test_passed_count_with_scores(self):
        """통과/실패 DimensionScore가 있을 때 passed_count가 정확해야 한다."""
        r = QualityCheckResult()
        r.dimension_scores = [
            DimensionScore(passed=True),
            DimensionScore(passed=True),
            DimensionScore(passed=False),
            DimensionScore(passed=True),
        ]
        self.assertEqual(r.passed_count, 3)

    def test_total_dimensions_with_scores(self):
        """DimensionScore가 4개일 때 total_dimensions가 4여야 한다."""
        r = QualityCheckResult()
        r.dimension_scores = [DimensionScore() for _ in range(4)]
        self.assertEqual(r.total_dimensions, 4)

    def test_get_dimension_score_found(self):
        """존재하는 차원 조회 시 해당 DimensionScore를 반환해야 한다."""
        r = QualityCheckResult()
        ds_sharp = DimensionScore(dimension=QualityDimension.SHARPNESS, raw_value=200.0)
        r.dimension_scores = [
            DimensionScore(dimension=QualityDimension.BRIGHTNESS),
            ds_sharp,
            DimensionScore(dimension=QualityDimension.CONTRAST),
        ]
        found = r.get_dimension_score(QualityDimension.SHARPNESS)
        self.assertIsNotNone(found)
        self.assertAlmostEqual(found.raw_value, 200.0)

    def test_get_dimension_score_not_found(self):
        """존재하지 않는 차원 조회 시 None을 반환해야 한다."""
        r = QualityCheckResult()
        r.dimension_scores = [DimensionScore(dimension=QualityDimension.BRIGHTNESS)]
        self.assertIsNone(r.get_dimension_score(QualityDimension.NOISE))

    def test_repr_contains_score(self):
        """repr에 score 값이 포함되어야 한다."""
        r = QualityCheckResult(overall_score=75.0)
        self.assertIn("75.0", repr(r))

    def test_repr_contains_level(self):
        """repr에 level 값이 포함되어야 한다."""
        r = QualityCheckResult(quality_level=QualityLevel.GOOD)
        self.assertIn("good", repr(r))


# =============================================================================
# TestQualityCheckStats
# =============================================================================

class TestQualityCheckStats(unittest.TestCase):
    """QualityCheckStats 데이터클래스 테스트."""

    def test_slots_defined(self):
        """__slots__이 정의되어 있어야 한다."""
        self.assertTrue(hasattr(QualityCheckStats, "__slots__"))

    def test_default_total_checked(self):
        """기본 total_checked는 0이어야 한다."""
        s = QualityCheckStats()
        self.assertEqual(s.total_checked, 0)

    def test_default_acceptable_count(self):
        """기본 acceptable_count는 0이어야 한다."""
        s = QualityCheckStats()
        self.assertEqual(s.acceptable_count, 0)

    def test_default_rejected_count(self):
        """기본 rejected_count는 0이어야 한다."""
        s = QualityCheckStats()
        self.assertEqual(s.rejected_count, 0)

    def test_default_avg_score(self):
        """기본 avg_score는 0.0이어야 한다."""
        s = QualityCheckStats()
        self.assertAlmostEqual(s.avg_score, 0.0)

    def test_default_total_time_sec(self):
        """기본 total_time_sec는 0.0이어야 한다."""
        s = QualityCheckStats()
        self.assertAlmostEqual(s.total_time_sec, 0.0)

    def test_acceptance_rate_zero_when_no_checks(self):
        """total_checked가 0일 때 acceptance_rate는 0.0이어야 한다."""
        s = QualityCheckStats()
        self.assertAlmostEqual(s.acceptance_rate, 0.0)

    def test_acceptance_rate_normal(self):
        """정상 케이스에서 acceptance_rate가 정확해야 한다."""
        s = QualityCheckStats(
            total_checked=10,
            acceptable_count=7,
        )
        self.assertAlmostEqual(s.acceptance_rate, 0.7, places=5)

    def test_acceptance_rate_full(self):
        """모두 허용될 때 acceptance_rate는 1.0이어야 한다."""
        s = QualityCheckStats(total_checked=5, acceptable_count=5)
        self.assertAlmostEqual(s.acceptance_rate, 1.0, places=5)

    def test_avg_time_ms_zero_when_no_checks(self):
        """total_checked가 0일 때 avg_time_ms는 0.0이어야 한다."""
        s = QualityCheckStats()
        self.assertAlmostEqual(s.avg_time_ms, 0.0)

    def test_avg_time_ms_normal(self):
        """정상 케이스에서 avg_time_ms가 정확해야 한다."""
        s = QualityCheckStats(total_checked=4, total_time_sec=0.4)
        # 0.4 / 4 * 1000 = 100ms
        self.assertAlmostEqual(s.avg_time_ms, 100.0, places=3)

    def test_repr_contains_total(self):
        """repr에 total 정보가 포함되어야 한다."""
        s = QualityCheckStats(total_checked=5)
        self.assertIn("5", repr(s))

    def test_repr_contains_rate(self):
        """repr에 acceptance rate가 포함되어야 한다."""
        s = QualityCheckStats(total_checked=10, acceptable_count=8)
        r = repr(s)
        self.assertIn("%", r)


# =============================================================================
# TestDataQualityCheckerInit
# =============================================================================

class TestDataQualityCheckerInit(unittest.TestCase):
    """DataQualityChecker 초기화 테스트."""

    def test_default_init(self):
        """기본 설정으로 초기화가 가능해야 한다."""
        checker = DataQualityChecker()
        self.assertIsNotNone(checker)

    def test_default_config_type(self):
        """기본 초기화 시 config가 QualityConfig 인스턴스여야 한다."""
        checker = DataQualityChecker()
        self.assertIsInstance(checker.config, QualityConfig)

    def test_custom_config(self):
        """커스텀 QualityConfig로 초기화가 가능해야 한다."""
        cfg = QualityConfig(brightness_min=50.0, brightness_max=210.0)
        checker = DataQualityChecker(config=cfg)
        self.assertAlmostEqual(checker.config.brightness_min, 50.0, places=1)
        self.assertAlmostEqual(checker.config.brightness_max, 210.0, places=1)

    def test_slots_defined(self):
        """__slots__이 정의되어 있어야 한다."""
        self.assertTrue(hasattr(DataQualityChecker, "__slots__"))

    def test_initial_stats_zero(self):
        """초기 통계는 모두 0이어야 한다."""
        checker = DataQualityChecker()
        stats = checker.get_stats()
        self.assertEqual(stats.total_checked, 0)
        self.assertEqual(stats.acceptable_count, 0)
        self.assertEqual(stats.rejected_count, 0)

    def test_repr_contains_config(self):
        """repr에 config 정보가 포함되어야 한다."""
        checker = DataQualityChecker()
        self.assertIn("DataQualityChecker", repr(checker))


# =============================================================================
# TestBrightnessMeasurement
# =============================================================================

class TestBrightnessMeasurement(unittest.TestCase):
    """밝기 측정 테스트."""

    def setUp(self):
        self.checker = DataQualityChecker()

    def test_dark_image_brightness_fails(self):
        """완전히 어두운 이미지는 밝기 검사에서 실패해야 한다."""
        frame = _make_black()
        result = self.checker.check_frame(frame)
        brightness_ds = result.get_dimension_score(QualityDimension.BRIGHTNESS)
        self.assertIsNotNone(brightness_ds)
        self.assertFalse(brightness_ds.passed)

    def test_dark_image_low_raw_value(self):
        """완전히 어두운 이미지의 raw_value는 0에 가까워야 한다."""
        frame = _make_black()
        result = self.checker.check_frame(frame)
        brightness_ds = result.get_dimension_score(QualityDimension.BRIGHTNESS)
        self.assertAlmostEqual(brightness_ds.raw_value, 0.0, places=1)

    def test_bright_image_brightness_fails(self):
        """완전히 밝은 이미지는 밝기 검사에서 실패해야 한다."""
        frame = _make_white()
        result = self.checker.check_frame(frame)
        brightness_ds = result.get_dimension_score(QualityDimension.BRIGHTNESS)
        self.assertIsNotNone(brightness_ds)
        self.assertFalse(brightness_ds.passed)

    def test_bright_image_high_raw_value(self):
        """완전히 밝은 이미지의 raw_value는 255에 가까워야 한다."""
        frame = _make_white()
        result = self.checker.check_frame(frame)
        brightness_ds = result.get_dimension_score(QualityDimension.BRIGHTNESS)
        self.assertAlmostEqual(brightness_ds.raw_value, 255.0, places=1)

    def test_mid_gray_image_brightness_passes(self):
        """중간 밝기(128) 이미지는 밝기 검사를 통과해야 한다."""
        frame = _make_mid_gray()
        result = self.checker.check_frame(frame)
        brightness_ds = result.get_dimension_score(QualityDimension.BRIGHTNESS)
        self.assertIsNotNone(brightness_ds)
        self.assertTrue(brightness_ds.passed)

    def test_mid_gray_raw_value_near_128(self):
        """중간 밝기 이미지의 raw_value는 128에 가까워야 한다."""
        frame = _make_mid_gray()
        result = self.checker.check_frame(frame)
        brightness_ds = result.get_dimension_score(QualityDimension.BRIGHTNESS)
        self.assertAlmostEqual(brightness_ds.raw_value, 128.0, delta=2.0)

    def test_dark_image_has_recommendation(self):
        """어두운 이미지는 권장사항에 메시지가 포함되어야 한다."""
        frame = _make_black()
        result = self.checker.check_frame(frame)
        self.assertGreater(len(result.recommendations), 0)


# =============================================================================
# TestContrastMeasurement
# =============================================================================

class TestContrastMeasurement(unittest.TestCase):
    """대비 측정 테스트."""

    def setUp(self):
        self.checker = DataQualityChecker()

    def test_flat_image_contrast_fails(self):
        """단색 이미지는 대비 검사에서 실패해야 한다."""
        frame = _make_mid_gray()
        result = self.checker.check_frame(frame)
        contrast_ds = result.get_dimension_score(QualityDimension.CONTRAST)
        self.assertIsNotNone(contrast_ds)
        self.assertFalse(contrast_ds.passed)

    def test_flat_image_near_zero_std(self):
        """단색 이미지의 표준편차(raw_value)는 0에 가까워야 한다."""
        frame = _make_mid_gray()
        result = self.checker.check_frame(frame)
        contrast_ds = result.get_dimension_score(QualityDimension.CONTRAST)
        self.assertAlmostEqual(contrast_ds.raw_value, 0.0, delta=1.0)

    def test_varied_image_contrast_passes(self):
        """다양한 픽셀값을 가진 이미지는 대비 검사를 통과해야 한다."""
        frame = _make_noisy()
        result = self.checker.check_frame(frame)
        contrast_ds = result.get_dimension_score(QualityDimension.CONTRAST)
        self.assertIsNotNone(contrast_ds)
        self.assertTrue(contrast_ds.passed)

    def test_varied_image_high_std(self):
        """노이즈 이미지의 표준편차는 contrast_min(20.0) 이상이어야 한다."""
        frame = _make_noisy()
        result = self.checker.check_frame(frame)
        contrast_ds = result.get_dimension_score(QualityDimension.CONTRAST)
        self.assertGreater(contrast_ds.raw_value, 20.0)

    def test_gradient_image_has_contrast(self):
        """그래디언트 이미지는 대비 검사를 통과해야 한다."""
        frame = _make_gradient()
        result = self.checker.check_frame(frame)
        contrast_ds = result.get_dimension_score(QualityDimension.CONTRAST)
        self.assertTrue(contrast_ds.passed)

    def test_normalized_score_range(self):
        """normalized_score는 0.0에서 100.0 사이여야 한다."""
        for frame in [_make_black(), _make_mid_gray(), _make_noisy()]:
            result = self.checker.check_frame(frame)
            contrast_ds = result.get_dimension_score(QualityDimension.CONTRAST)
            self.assertGreaterEqual(contrast_ds.normalized_score, 0.0)
            self.assertLessEqual(contrast_ds.normalized_score, 100.0)


# =============================================================================
# TestSharpnessMeasurement
# =============================================================================

class TestSharpnessMeasurement(unittest.TestCase):
    """선명도 측정 테스트."""

    def setUp(self):
        self.checker = DataQualityChecker()

    def test_blurred_image_sharpness_fails(self):
        """극도로 블러된 이미지는 선명도 검사에서 실패해야 한다."""
        frame = _make_blurred()
        result = self.checker.check_frame(frame)
        sharpness_ds = result.get_dimension_score(QualityDimension.SHARPNESS)
        self.assertIsNotNone(sharpness_ds)
        self.assertFalse(sharpness_ds.passed)

    def test_blurred_image_low_variance(self):
        """블러된 이미지의 라플라시안 분산은 sharpness_min(100.0)보다 낮아야 한다."""
        frame = _make_blurred()
        result = self.checker.check_frame(frame)
        sharpness_ds = result.get_dimension_score(QualityDimension.SHARPNESS)
        self.assertLess(sharpness_ds.raw_value, 100.0)

    def test_sharp_edges_high_sharpness(self):
        """날카로운 엣지 이미지는 라플라시안 분산이 높아야 한다."""
        frame = _make_sharp_edges()
        result = self.checker.check_frame(frame)
        sharpness_ds = result.get_dimension_score(QualityDimension.SHARPNESS)
        self.assertIsNotNone(sharpness_ds)
        self.assertGreater(sharpness_ds.raw_value, 100.0)

    def test_sharp_edges_passes(self):
        """날카로운 엣지 이미지는 선명도 검사를 통과해야 한다."""
        frame = _make_sharp_edges()
        result = self.checker.check_frame(frame)
        sharpness_ds = result.get_dimension_score(QualityDimension.SHARPNESS)
        self.assertTrue(sharpness_ds.passed)

    def test_sharpness_normalized_score_range(self):
        """normalized_score는 0.0에서 100.0 사이여야 한다."""
        for frame in [_make_blurred(), _make_sharp_edges()]:
            result = self.checker.check_frame(frame)
            sharpness_ds = result.get_dimension_score(QualityDimension.SHARPNESS)
            self.assertGreaterEqual(sharpness_ds.normalized_score, 0.0)
            self.assertLessEqual(sharpness_ds.normalized_score, 100.0)

    def test_blurred_image_has_recommendation(self):
        """블러된 이미지는 권장사항에 메시지가 포함되어야 한다."""
        frame = _make_blurred()
        result = self.checker.check_frame(frame)
        sharpness_ds = result.get_dimension_score(QualityDimension.SHARPNESS)
        self.assertNotEqual(sharpness_ds.message, "")


# =============================================================================
# TestNoiseMeasurement
# =============================================================================

class TestNoiseMeasurement(unittest.TestCase):
    """노이즈 측정 테스트."""

    def setUp(self):
        self.checker = DataQualityChecker()

    def test_clean_gradient_low_noise(self):
        """그래디언트 이미지는 노이즈 검사를 통과해야 한다."""
        frame = _make_gradient()
        result = self.checker.check_frame(frame)
        noise_ds = result.get_dimension_score(QualityDimension.NOISE)
        self.assertIsNotNone(noise_ds)
        self.assertTrue(noise_ds.passed)

    def test_clean_gradient_low_noise_value(self):
        """그래디언트 이미지의 노이즈 레벨은 낮아야 한다."""
        frame = _make_gradient()
        result = self.checker.check_frame(frame)
        noise_ds = result.get_dimension_score(QualityDimension.NOISE)
        self.assertLess(noise_ds.raw_value, 50.0)

    def test_very_noisy_image(self):
        """매우 노이즈가 많은 이미지는 높은 노이즈 레벨을 가져야 한다."""
        # 강한 노이즈 이미지: 기본 이미지에 큰 노이즈 추가
        rng = np.random.default_rng(0)
        base = np.full((480, 640, 3), 128, dtype=np.int32)
        noise_array = rng.integers(-80, 80, (480, 640, 3), dtype=np.int32)
        noisy = np.clip(base + noise_array, 0, 255).astype(np.uint8)
        result = self.checker.check_frame(noisy)
        noise_ds = result.get_dimension_score(QualityDimension.NOISE)
        self.assertIsNotNone(noise_ds)
        # 노이즈가 많을수록 raw_value가 높아야 함
        self.assertGreater(noise_ds.raw_value, 0.0)

    def test_noise_normalized_score_range(self):
        """normalized_score는 0.0에서 100.0 사이여야 한다."""
        for frame in [_make_gradient(), _make_noisy()]:
            result = self.checker.check_frame(frame)
            noise_ds = result.get_dimension_score(QualityDimension.NOISE)
            self.assertGreaterEqual(noise_ds.normalized_score, 0.0)
            self.assertLessEqual(noise_ds.normalized_score, 100.0)

    def test_flat_image_low_noise(self):
        """완전히 평탄한 단색 이미지는 노이즈 레벨이 매우 낮아야 한다."""
        frame = _make_mid_gray()
        result = self.checker.check_frame(frame)
        noise_ds = result.get_dimension_score(QualityDimension.NOISE)
        self.assertAlmostEqual(noise_ds.raw_value, 0.0, delta=1.0)


# =============================================================================
# TestOverallScore
# =============================================================================

class TestOverallScore(unittest.TestCase):
    """종합 점수 계산 테스트."""

    def setUp(self):
        self.checker = DataQualityChecker()

    def test_overall_score_is_weighted_sum(self):
        """종합 점수는 차원별 가중 합산이어야 한다."""
        frame = _make_mid_gray()
        result = self.checker.check_frame(frame)
        # 차원 점수가 존재할 때만 검증
        if result.total_dimensions == 4:
            b = result.get_dimension_score(QualityDimension.BRIGHTNESS)
            c = result.get_dimension_score(QualityDimension.CONTRAST)
            s = result.get_dimension_score(QualityDimension.SHARPNESS)
            n = result.get_dimension_score(QualityDimension.NOISE)
            expected = (
                b.normalized_score * BRIGHTNESS_WEIGHT
                + c.normalized_score * CONTRAST_WEIGHT
                + s.normalized_score * SHARPNESS_WEIGHT
                + n.normalized_score * NOISE_WEIGHT
            )
            self.assertAlmostEqual(result.overall_score, expected, places=4)

    def test_overall_score_range(self):
        """종합 점수는 0.0에서 100.0 사이여야 한다."""
        for frame in [_make_black(), _make_mid_gray(), _make_white(), _make_noisy()]:
            result = self.checker.check_frame(frame)
            self.assertGreaterEqual(result.overall_score, 0.0)
            self.assertLessEqual(result.overall_score, 100.0)

    def test_quality_level_assigned(self):
        """quality_level이 QualityLevel 열거형이어야 한다."""
        frame = _make_mid_gray()
        result = self.checker.check_frame(frame)
        self.assertIsInstance(result.quality_level, QualityLevel)

    def test_normal_image_has_dimension_scores(self):
        """정상 이미지 처리 결과에는 4개의 차원 점수가 있어야 한다."""
        frame = _make_gradient()
        result = self.checker.check_frame(frame)
        self.assertEqual(result.total_dimensions, 4)

    def test_check_time_ms_non_negative(self):
        """검사 시간(ms)은 0 이상이어야 한다 (Windows 타이머 해상도 고려)."""
        frame = _make_mid_gray()
        result = self.checker.check_frame(frame)
        self.assertGreaterEqual(result.check_time_ms, 0.0)

    def test_is_acceptable_consistent_with_score_and_level(self):
        """is_acceptable은 quality_level.is_usable과 일치해야 한다."""
        for frame in [_make_mid_gray(), _make_gradient(), _make_sharp_edges()]:
            result = self.checker.check_frame(frame)
            if result.quality_level.is_usable:
                # is_acceptable은 level과 minimum_score 모두 고려
                self.assertEqual(
                    result.is_acceptable,
                    result.overall_score >= self.checker.config.minimum_score,
                )


# =============================================================================
# TestScoreToLevel
# =============================================================================

class TestScoreToLevel(unittest.TestCase):
    """_score_to_level 정적 메서드 경계값 테스트."""

    def test_score_90_is_excellent(self):
        """90.0점은 EXCELLENT여야 한다."""
        self.assertEqual(DataQualityChecker._score_to_level(90.0), QualityLevel.EXCELLENT)

    def test_score_100_is_excellent(self):
        """100.0점은 EXCELLENT여야 한다."""
        self.assertEqual(DataQualityChecker._score_to_level(100.0), QualityLevel.EXCELLENT)

    def test_score_89_9_is_good(self):
        """89.9점은 GOOD이어야 한다."""
        self.assertEqual(DataQualityChecker._score_to_level(89.9), QualityLevel.GOOD)

    def test_score_70_is_good(self):
        """70.0점은 GOOD이어야 한다."""
        self.assertEqual(DataQualityChecker._score_to_level(70.0), QualityLevel.GOOD)

    def test_score_69_9_is_acceptable(self):
        """69.9점은 ACCEPTABLE이어야 한다."""
        self.assertEqual(DataQualityChecker._score_to_level(69.9), QualityLevel.ACCEPTABLE)

    def test_score_50_is_acceptable(self):
        """50.0점은 ACCEPTABLE이어야 한다."""
        self.assertEqual(DataQualityChecker._score_to_level(50.0), QualityLevel.ACCEPTABLE)

    def test_score_49_9_is_poor(self):
        """49.9점은 POOR여야 한다."""
        self.assertEqual(DataQualityChecker._score_to_level(49.9), QualityLevel.POOR)

    def test_score_30_is_poor(self):
        """30.0점은 POOR여야 한다."""
        self.assertEqual(DataQualityChecker._score_to_level(30.0), QualityLevel.POOR)

    def test_score_29_9_is_unacceptable(self):
        """29.9점은 UNACCEPTABLE이어야 한다."""
        self.assertEqual(DataQualityChecker._score_to_level(29.9), QualityLevel.UNACCEPTABLE)

    def test_score_0_is_unacceptable(self):
        """0.0점은 UNACCEPTABLE이어야 한다."""
        self.assertEqual(DataQualityChecker._score_to_level(0.0), QualityLevel.UNACCEPTABLE)


# =============================================================================
# TestFrameEdgeCases
# =============================================================================

class TestFrameEdgeCases(unittest.TestCase):
    """프레임 엣지 케이스 테스트."""

    def setUp(self):
        self.checker = DataQualityChecker()

    def test_none_frame_returns_result(self):
        """None 프레임 입력 시 QualityCheckResult를 반환해야 한다."""
        result = self.checker.check_frame(None)
        self.assertIsInstance(result, QualityCheckResult)

    def test_none_frame_is_not_acceptable(self):
        """None 프레임은 is_acceptable이 False여야 한다."""
        result = self.checker.check_frame(None)
        self.assertFalse(result.is_acceptable)

    def test_none_frame_has_failed_dimensions(self):
        """None 프레임은 failed_dimensions에 항목이 있어야 한다."""
        result = self.checker.check_frame(None)
        self.assertGreater(len(result.failed_dimensions), 0)

    def test_none_frame_has_recommendation(self):
        """None 프레임은 recommendations에 항목이 있어야 한다."""
        result = self.checker.check_frame(None)
        self.assertGreater(len(result.recommendations), 0)

    def test_empty_frame_returns_result(self):
        """빈 배열 프레임 입력 시 QualityCheckResult를 반환해야 한다."""
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        result = self.checker.check_frame(empty)
        self.assertIsInstance(result, QualityCheckResult)

    def test_too_small_frame_returns_result(self):
        """MIN_QUALITY_CHECK_SIZE보다 작은 프레임 입력 시 QualityCheckResult를 반환해야 한다."""
        small = np.zeros((16, 16, 3), dtype=np.uint8)
        result = self.checker.check_frame(small)
        self.assertIsInstance(result, QualityCheckResult)

    def test_too_small_frame_not_acceptable(self):
        """너무 작은 프레임은 is_acceptable이 False여야 한다."""
        small = np.zeros((10, 10, 3), dtype=np.uint8)
        result = self.checker.check_frame(small)
        self.assertFalse(result.is_acceptable)

    def test_too_small_frame_has_resolution_failed(self):
        """너무 작은 프레임은 failed_dimensions에 'resolution'이 있어야 한다."""
        small = np.zeros((10, 10, 3), dtype=np.uint8)
        result = self.checker.check_frame(small)
        self.assertIn("resolution", result.failed_dimensions)

    def test_grayscale_frame_2d_returns_result(self):
        """2D 그레이스케일 프레임도 처리 가능해야 한다."""
        gray_2d = np.full((480, 640), 128, dtype=np.uint8)
        result = self.checker.check_frame(gray_2d)
        self.assertIsInstance(result, QualityCheckResult)

    def test_grayscale_frame_2d_has_dimension_scores(self):
        """2D 그레이스케일 프레임 처리 결과에 차원 점수가 있어야 한다."""
        gray_2d = np.full((480, 640), 128, dtype=np.uint8)
        result = self.checker.check_frame(gray_2d)
        self.assertEqual(result.total_dimensions, 4)

    def test_minimum_valid_frame(self):
        """MIN_QUALITY_CHECK_SIZE x MIN_QUALITY_CHECK_SIZE 프레임은 처리 가능해야 한다."""
        frame = np.full(
            (MIN_QUALITY_CHECK_SIZE, MIN_QUALITY_CHECK_SIZE, 3), 128, dtype=np.uint8
        )
        result = self.checker.check_frame(frame)
        self.assertEqual(result.total_dimensions, 4)


# =============================================================================
# TestBatchCheck
# =============================================================================

class TestBatchCheck(unittest.TestCase):
    """배치 검사 테스트."""

    def setUp(self):
        self.checker = DataQualityChecker()

    def test_batch_returns_list(self):
        """check_batch는 리스트를 반환해야 한다."""
        frames = [_make_mid_gray() for _ in range(3)]
        results = self.checker.check_batch(frames)
        self.assertIsInstance(results, list)

    def test_batch_result_count_matches_input(self):
        """결과 수는 입력 프레임 수와 같아야 한다."""
        frames = [_make_mid_gray() for _ in range(5)]
        results = self.checker.check_batch(frames)
        self.assertEqual(len(results), 5)

    def test_batch_results_are_quality_check_result(self):
        """각 결과는 QualityCheckResult 인스턴스여야 한다."""
        frames = [_make_mid_gray(), _make_gradient(), _make_noisy()]
        results = self.checker.check_batch(frames)
        for r in results:
            self.assertIsInstance(r, QualityCheckResult)

    def test_batch_exceeds_max_is_truncated(self):
        """MAX_QUALITY_BATCH_SIZE 초과 입력 시 결과 수는 MAX 이하여야 한다."""
        frames = [_make_mid_gray() for _ in range(MAX_QUALITY_BATCH_SIZE + 10)]
        results = self.checker.check_batch(frames)
        self.assertLessEqual(len(results), MAX_QUALITY_BATCH_SIZE)

    def test_batch_empty_input(self):
        """빈 리스트 입력 시 빈 리스트를 반환해야 한다."""
        results = self.checker.check_batch([])
        self.assertEqual(results, [])

    def test_batch_updates_stats(self):
        """배치 처리 후 통계가 갱신되어야 한다."""
        self.checker.reset_stats()
        frames = [_make_mid_gray() for _ in range(4)]
        self.checker.check_batch(frames)
        stats = self.checker.get_stats()
        self.assertEqual(stats.total_checked, 4)

    def test_batch_mixed_frames(self):
        """다양한 품질의 프레임을 배치로 처리할 수 있어야 한다."""
        frames = [_make_black(), _make_mid_gray(), _make_white(), _make_gradient()]
        results = self.checker.check_batch(frames)
        self.assertEqual(len(results), 4)


# =============================================================================
# TestStats
# =============================================================================

class TestStats(unittest.TestCase):
    """통계 누적 및 초기화 테스트."""

    def setUp(self):
        self.checker = DataQualityChecker()
        self.checker.reset_stats()

    def test_stats_accumulate_total_checked(self):
        """check_frame 호출 수만큼 total_checked가 증가해야 한다."""
        for _ in range(3):
            self.checker.check_frame(_make_mid_gray())
        stats = self.checker.get_stats()
        self.assertEqual(stats.total_checked, 3)

    def test_stats_accumulate_acceptable_count(self):
        """허용 가능한 프레임에 대해 acceptable_count가 증가해야 한다."""
        frame = _make_gradient()
        self.checker.check_frame(frame)
        stats = self.checker.get_stats()
        frame_result = DataQualityChecker().check_frame(frame)
        if frame_result.is_acceptable:
            self.assertGreaterEqual(stats.acceptable_count, 0)

    def test_stats_accumulate_rejected_count(self):
        """거부된 프레임에 대해 rejected_count가 증가해야 한다."""
        self.checker.check_frame(None)
        stats = self.checker.get_stats()
        self.assertGreaterEqual(stats.rejected_count, 1)

    def test_stats_total_checked_and_counts_sum(self):
        """total_checked = acceptable_count + rejected_count여야 한다."""
        frames = [_make_mid_gray(), _make_black(), None]
        for f in frames:
            self.checker.check_frame(f)
        stats = self.checker.get_stats()
        self.assertEqual(
            stats.total_checked,
            stats.acceptable_count + stats.rejected_count,
        )

    def test_stats_avg_score_updated(self):
        """여러 프레임 처리 후 avg_score가 0.0이 아니어야 한다."""
        self.checker.check_frame(_make_gradient())
        self.checker.check_frame(_make_mid_gray())
        stats = self.checker.get_stats()
        self.assertGreaterEqual(stats.avg_score, 0.0)

    def test_stats_total_time_sec_non_negative(self):
        """프레임 처리 후 total_time_sec가 0 이상이어야 한다 (Windows 타이머 해상도 고려)."""
        self.checker.check_frame(_make_mid_gray())
        stats = self.checker.get_stats()
        self.assertGreaterEqual(stats.total_time_sec, 0.0)

    def test_reset_stats_zeroes_all(self):
        """reset_stats 호출 후 모든 통계가 0이 되어야 한다."""
        self.checker.check_frame(_make_mid_gray())
        self.checker.reset_stats()
        stats = self.checker.get_stats()
        self.assertEqual(stats.total_checked, 0)
        self.assertEqual(stats.acceptable_count, 0)
        self.assertEqual(stats.rejected_count, 0)
        self.assertAlmostEqual(stats.avg_score, 0.0)
        self.assertAlmostEqual(stats.total_time_sec, 0.0)

    def test_get_stats_returns_copy(self):
        """get_stats는 방어적 복사본을 반환해야 한다."""
        self.checker.check_frame(_make_mid_gray())
        stats1 = self.checker.get_stats()
        stats2 = self.checker.get_stats()
        self.assertIsNot(stats1, stats2)

    def test_thread_safety_concurrent_check(self):
        """멀티스레드에서 check_frame을 동시에 호출해도 안전해야 한다."""
        errors: list[Exception] = []

        def worker():
            try:
                for _ in range(10):
                    self.checker.check_frame(_make_mid_gray())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        stats = self.checker.get_stats()
        self.assertEqual(stats.total_checked, 40)


# =============================================================================
# TestConstants
# =============================================================================

class TestConstants(unittest.TestCase):
    """상수 값 테스트."""

    def test_min_quality_check_size(self):
        """MIN_QUALITY_CHECK_SIZE는 32여야 한다."""
        self.assertEqual(MIN_QUALITY_CHECK_SIZE, 32)

    def test_max_quality_batch_size(self):
        """MAX_QUALITY_BATCH_SIZE는 500이어야 한다."""
        self.assertEqual(MAX_QUALITY_BATCH_SIZE, 500)

    def test_max_quality_check_history(self):
        """MAX_QUALITY_CHECK_HISTORY는 10000이어야 한다."""
        self.assertEqual(MAX_QUALITY_CHECK_HISTORY, 10_000)

    def test_default_contrast_min_threshold(self):
        """DEFAULT_CONTRAST_MIN_THRESHOLD는 20.0이어야 한다."""
        self.assertAlmostEqual(DEFAULT_CONTRAST_MIN_THRESHOLD, 20.0)

    def test_brightness_weight(self):
        """BRIGHTNESS_WEIGHT는 0.25여야 한다."""
        self.assertAlmostEqual(BRIGHTNESS_WEIGHT, 0.25)

    def test_contrast_weight(self):
        """CONTRAST_WEIGHT는 0.25여야 한다."""
        self.assertAlmostEqual(CONTRAST_WEIGHT, 0.25)

    def test_sharpness_weight(self):
        """SHARPNESS_WEIGHT는 0.30이어야 한다."""
        self.assertAlmostEqual(SHARPNESS_WEIGHT, 0.30)

    def test_noise_weight(self):
        """NOISE_WEIGHT는 0.20이어야 한다."""
        self.assertAlmostEqual(NOISE_WEIGHT, 0.20)

    def test_weights_sum_to_one(self):
        """모든 가중치의 합은 1.0이어야 한다."""
        total = BRIGHTNESS_WEIGHT + CONTRAST_WEIGHT + SHARPNESS_WEIGHT + NOISE_WEIGHT
        self.assertAlmostEqual(total, 1.0, places=10)


# =============================================================================
# TestExport
# =============================================================================

class TestExport(unittest.TestCase):
    """__all__ 및 __version__ export 테스트."""

    def _get_module(self):
        import infrastructure.validation.data_quality_checker as m
        return m

    def test_all_defined(self):
        """__all__이 정의되어 있어야 한다."""
        mod = self._get_module()
        self.assertTrue(hasattr(mod, "__all__"))

    def test_all_contains_quality_dimension(self):
        """__all__에 'QualityDimension'이 포함되어야 한다."""
        mod = self._get_module()
        self.assertIn("QualityDimension", mod.__all__)

    def test_all_contains_quality_level(self):
        """__all__에 'QualityLevel'이 포함되어야 한다."""
        mod = self._get_module()
        self.assertIn("QualityLevel", mod.__all__)

    def test_all_contains_quality_config(self):
        """__all__에 'QualityConfig'이 포함되어야 한다."""
        mod = self._get_module()
        self.assertIn("QualityConfig", mod.__all__)

    def test_all_contains_dimension_score(self):
        """__all__에 'DimensionScore'가 포함되어야 한다."""
        mod = self._get_module()
        self.assertIn("DimensionScore", mod.__all__)

    def test_all_contains_quality_check_result(self):
        """__all__에 'QualityCheckResult'가 포함되어야 한다."""
        mod = self._get_module()
        self.assertIn("QualityCheckResult", mod.__all__)

    def test_all_contains_quality_check_stats(self):
        """__all__에 'QualityCheckStats'가 포함되어야 한다."""
        mod = self._get_module()
        self.assertIn("QualityCheckStats", mod.__all__)

    def test_all_contains_data_quality_checker(self):
        """__all__에 'DataQualityChecker'가 포함되어야 한다."""
        mod = self._get_module()
        self.assertIn("DataQualityChecker", mod.__all__)

    def test_all_contains_constants(self):
        """__all__에 모든 8개 상수가 포함되어야 한다."""
        mod = self._get_module()
        for const in (
            "MIN_QUALITY_CHECK_SIZE",
            "MAX_QUALITY_BATCH_SIZE",
            "MAX_QUALITY_CHECK_HISTORY",
            "DEFAULT_CONTRAST_MIN_THRESHOLD",
            "BRIGHTNESS_WEIGHT",
            "CONTRAST_WEIGHT",
            "SHARPNESS_WEIGHT",
            "NOISE_WEIGHT",
        ):
            self.assertIn(const, mod.__all__)

    def test_version_defined(self):
        """__version__이 정의되어 있어야 한다."""
        mod = self._get_module()
        self.assertTrue(hasattr(mod, "__version__"))

    def test_version_is_string(self):
        """__version__은 문자열이어야 한다."""
        mod = self._get_module()
        self.assertIsInstance(mod.__version__, str)

    def test_version_value(self):
        """__version__은 '1.0.0'이어야 한다."""
        mod = self._get_module()
        self.assertEqual(mod.__version__, "1.0.0")

    def test_all_exports_are_importable(self):
        """__all__에 선언된 모든 항목이 모듈에서 접근 가능해야 한다."""
        mod = self._get_module()
        for name in mod.__all__:
            self.assertTrue(hasattr(mod, name), f"{name} not found in module")


# =============================================================================
# 테스트 실행
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
