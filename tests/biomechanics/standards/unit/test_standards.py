# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/biomechanics/standards/unit
파일: test_standards.py
설명: biomechanics/standards/ 전체 단위 테스트

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-22
버전: 1.0.0
"""
from __future__ import annotations

import pytest

from shared.constants.player_constants import AgeGroup, Gender


# ============================================================
# Section 1: region_types 테스트
# ============================================================
class TestLeagueType:
    """LeagueType 열거형 테스트."""

    def test_member_count(self) -> None:
        from biomechanics.standards.region_types import LeagueType
        assert len(LeagueType) == 4

    def test_fiba_court_spec(self) -> None:
        from biomechanics.standards.region_types import LeagueType
        assert LeagueType.FIBA.court_length_m == 28.0
        assert LeagueType.FIBA.court_width_m == 15.0
        assert LeagueType.FIBA.three_point_distance_m == 6.75
        assert LeagueType.FIBA.shot_clock_s == 24
        assert LeagueType.FIBA.quarter_minutes == 10

    def test_nba_court_spec(self) -> None:
        from biomechanics.standards.region_types import LeagueType
        assert LeagueType.NBA.court_length_m == pytest.approx(28.65, abs=0.01)
        assert LeagueType.NBA.three_point_distance_m == 7.24
        assert LeagueType.NBA.quarter_minutes == 12

    def test_korean_name(self) -> None:
        from biomechanics.standards.region_types import LeagueType
        assert LeagueType.KBL.korean_name == "한국프로농구"
        assert LeagueType.FIBA.korean_name == "FIBA 국제농구"

    def test_str(self) -> None:
        from biomechanics.standards.region_types import LeagueType
        assert str(LeagueType.NBA) == "nba"


class TestRegionType:
    """RegionType 열거형 테스트."""

    def test_member_count(self) -> None:
        from biomechanics.standards.region_types import RegionType
        assert len(RegionType) == 8

    def test_east_asian_profile(self) -> None:
        from biomechanics.standards.region_types import RegionType
        assert RegionType.EAST_ASIAN.avg_height_male_cm == 174.0
        assert RegionType.EAST_ASIAN.avg_height_female_cm == 161.0
        assert RegionType.EAST_ASIAN.limb_trunk_ratio < 1.0  # 짧은 사지

    def test_african_profile(self) -> None:
        from biomechanics.standards.region_types import RegionType
        assert RegionType.AFRICAN.limb_trunk_ratio > 1.0  # 긴 사지

    def test_european_baseline(self) -> None:
        from biomechanics.standards.region_types import RegionType
        assert RegionType.EUROPEAN.limb_trunk_ratio == 1.00  # 기준

    def test_korean_name(self) -> None:
        from biomechanics.standards.region_types import RegionType
        assert RegionType.EAST_ASIAN.korean_name == "동아시아"


class TestRegionUtilities:
    """region_types 유틸리티 함수 테스트."""

    def test_get_default_region(self) -> None:
        from biomechanics.standards.region_types import (
            LeagueType, RegionType, get_default_region,
        )
        assert get_default_region(LeagueType.KBL) == RegionType.EAST_ASIAN
        assert get_default_region(LeagueType.NBA) == RegionType.NORTH_AMERICAN

    def test_get_age_boundary(self) -> None:
        from biomechanics.standards.region_types import LeagueType, get_age_boundary
        nba_boundary = get_age_boundary(LeagueType.NBA)
        assert nba_boundary.pro_min_age == 19
        kbl_boundary = get_age_boundary(LeagueType.KBL)
        assert kbl_boundary.pro_min_age == 18

    def test_get_region_profile(self) -> None:
        from biomechanics.standards.region_types import RegionType, get_region_profile
        profile = get_region_profile(RegionType.EAST_ASIAN)
        assert profile.avg_height_male_cm == 174.0

    def test_get_court_spec(self) -> None:
        from biomechanics.standards.region_types import LeagueType, get_court_spec
        spec = get_court_spec(LeagueType.NBA)
        assert spec.hoop_height_m == 3.05

    def test_age_to_league_category(self) -> None:
        from biomechanics.standards.region_types import (
            LeagueType, age_to_league_category,
        )
        assert age_to_league_category(10, LeagueType.FIBA) == AgeGroup.YOUTH
        assert age_to_league_category(15, LeagueType.FIBA) == AgeGroup.TEEN
        assert age_to_league_category(25, LeagueType.FIBA) == AgeGroup.ADULT
        assert age_to_league_category(55, LeagueType.FIBA) == AgeGroup.SENIOR


class TestLeagueCourtSpec:
    """LeagueCourtSpec 데이터클래스 테스트."""

    def test_frozen(self) -> None:
        from biomechanics.standards.region_types import LeagueCourtSpec
        spec = LeagueCourtSpec(
            court_length_m=28.0, court_width_m=15.0,
            three_point_distance_m=6.75, shot_clock_s=24, quarter_minutes=10,
        )
        with pytest.raises(AttributeError):
            spec.court_length_m = 30.0  # type: ignore[misc]

    def test_slots(self) -> None:
        from biomechanics.standards.region_types import LeagueCourtSpec
        spec = LeagueCourtSpec(
            court_length_m=28.0, court_width_m=15.0,
            three_point_distance_m=6.75, shot_clock_s=24, quarter_minutes=10,
        )
        assert not hasattr(spec, "__dict__")


# ============================================================
# Section 2: youth_standards 테스트
# ============================================================
class TestYouthStandards:
    """유소년 기준값 테스트."""

    def test_target_age_group(self) -> None:
        from biomechanics.standards.youth_standards import TARGET_AGE_GROUP
        assert TARGET_AGE_GROUP == AgeGroup.YOUTH

    def test_age_range(self) -> None:
        from biomechanics.standards.youth_standards import AGE_RANGE
        assert AGE_RANGE == (6, 12)

    def test_body_defaults_all_ages(self) -> None:
        from biomechanics.standards.youth_standards import YOUTH_BODY_DEFAULTS
        for age in range(6, 13):
            assert age in YOUTH_BODY_DEFAULTS
            d = YOUTH_BODY_DEFAULTS[age]
            assert d.height_cm_male > 0
            assert d.weight_kg_male > 0

    def test_body_defaults_growth_progression(self) -> None:
        """나이가 증가하면 신장/체중도 증가."""
        from biomechanics.standards.youth_standards import YOUTH_BODY_DEFAULTS
        for age in range(7, 13):
            prev = YOUTH_BODY_DEFAULTS[age - 1]
            curr = YOUTH_BODY_DEFAULTS[age]
            assert curr.height_cm_male >= prev.height_cm_male
            assert curr.weight_kg_male >= prev.weight_kg_male

    def test_velocity_factor(self) -> None:
        from biomechanics.standards.youth_standards import VELOCITY_FACTOR
        assert VELOCITY_FACTOR == 0.65

    def test_angle_tolerance(self) -> None:
        from biomechanics.standards.youth_standards import ANGLE_TOLERANCE
        assert ANGLE_TOLERANCE == 15.0

    def test_rom_expansion(self) -> None:
        from biomechanics.standards.youth_standards import ROM_EXPANSION_FACTOR
        assert ROM_EXPANSION_FACTOR > 1.0  # 유소년은 유연성 높음

    def test_shooting_angles_keys(self) -> None:
        from biomechanics.standards.youth_standards import SHOOTING_OPTIMAL_ANGLES_YOUTH
        assert "release_shoulder_flexion" in SHOOTING_OPTIMAL_ANGLES_YOUTH
        assert "set_knee_flexion" in SHOOTING_OPTIMAL_ANGLES_YOUTH

    def test_severity_thresholds(self) -> None:
        from biomechanics.standards.youth_standards import SEVERITY_THRESHOLDS
        assert SEVERITY_THRESHOLDS.warning > 10.0  # 성인보다 넓음
        assert SEVERITY_THRESHOLDS.critical > SEVERITY_THRESHOLDS.warning

    def test_max_reps_limits(self) -> None:
        from biomechanics.standards.youth_standards import (
            MAX_JUMP_LANDINGS_PER_SESSION,
            MAX_SHOOTING_REPS_PER_SESSION,
        )
        assert MAX_JUMP_LANDINGS_PER_SESSION == 80
        assert MAX_SHOOTING_REPS_PER_SESSION == 150

    def test_get_body_defaults(self) -> None:
        from biomechanics.standards.youth_standards import get_body_defaults
        d = get_body_defaults(10)
        assert d.age == 10
        assert d.height_cm_male > 0

    def test_get_body_defaults_invalid_age(self) -> None:
        from biomechanics.standards.youth_standards import get_body_defaults
        with pytest.raises(ValueError):
            get_body_defaults(5)
        with pytest.raises(ValueError):
            get_body_defaults(13)

    def test_get_height_cm(self) -> None:
        from biomechanics.standards.youth_standards import get_height_cm
        h_male = get_height_cm(10, Gender.MALE)
        h_female = get_height_cm(10, Gender.FEMALE)
        assert h_male > 0
        assert h_female > 0

    def test_get_weight_kg(self) -> None:
        from biomechanics.standards.youth_standards import get_weight_kg
        w = get_weight_kg(10, Gender.MALE)
        assert w > 0


# ============================================================
# Section 3: teen_standards 테스트
# ============================================================
class TestTeenStandards:
    """청소년 기준값 테스트."""

    def test_target_age_group(self) -> None:
        from biomechanics.standards.teen_standards import TARGET_AGE_GROUP
        assert TARGET_AGE_GROUP == AgeGroup.TEEN

    def test_age_range(self) -> None:
        from biomechanics.standards.teen_standards import AGE_RANGE
        assert AGE_RANGE == (13, 18)

    def test_body_defaults_all_ages(self) -> None:
        from biomechanics.standards.teen_standards import TEEN_BODY_DEFAULTS
        for age in range(13, 19):
            assert age in TEEN_BODY_DEFAULTS

    def test_phv_growth_spurt(self) -> None:
        """13-14세 남성 PHV 확인."""
        from biomechanics.standards.teen_standards import TEEN_BODY_DEFAULTS
        d13 = TEEN_BODY_DEFAULTS[13]
        d14 = TEEN_BODY_DEFAULTS[14]
        growth = d14.height_cm_male - d13.height_cm_male
        assert growth >= 5.0  # PHV 시기 급성장

    def test_velocity_factor(self) -> None:
        from biomechanics.standards.teen_standards import VELOCITY_FACTOR
        assert VELOCITY_FACTOR == 0.85

    def test_angle_tolerance(self) -> None:
        from biomechanics.standards.teen_standards import ANGLE_TOLERANCE
        assert ANGLE_TOLERANCE == 8.0

    def test_knee_valgus_female_stricter(self) -> None:
        from biomechanics.standards.teen_standards import (
            KNEE_VALGUS_WARNING_DEGREES,
            KNEE_VALGUS_CRITICAL_DEGREES_FEMALE,
        )
        assert KNEE_VALGUS_CRITICAL_DEGREES_FEMALE < KNEE_VALGUS_WARNING_DEGREES

    def test_severity_between_youth_and_adult(self) -> None:
        from biomechanics.standards.teen_standards import SEVERITY_THRESHOLDS as teen_sev
        from biomechanics.standards.youth_standards import SEVERITY_THRESHOLDS as youth_sev
        from biomechanics.standards.adult_standards import SEVERITY_THRESHOLDS as adult_sev
        assert youth_sev.warning > teen_sev.warning > adult_sev.warning


# ============================================================
# Section 4: adult_standards 테스트
# ============================================================
class TestAdultStandards:
    """성인 기준값 테스트."""

    def test_target_age_group(self) -> None:
        from biomechanics.standards.adult_standards import TARGET_AGE_GROUP
        assert TARGET_AGE_GROUP == AgeGroup.ADULT

    def test_velocity_factor_baseline(self) -> None:
        from biomechanics.standards.adult_standards import VELOCITY_FACTOR
        assert VELOCITY_FACTOR == 1.00

    def test_angle_tolerance_zero(self) -> None:
        from biomechanics.standards.adult_standards import ANGLE_TOLERANCE
        assert ANGLE_TOLERANCE == 0.0

    def test_rom_expansion_baseline(self) -> None:
        from biomechanics.standards.adult_standards import ROM_EXPANSION_FACTOR
        assert ROM_EXPANSION_FACTOR == 1.00

    def test_body_defaults_both_genders(self) -> None:
        from biomechanics.standards.adult_standards import ADULT_BODY_DEFAULTS
        assert Gender.MALE in ADULT_BODY_DEFAULTS
        assert Gender.FEMALE in ADULT_BODY_DEFAULTS

    def test_get_body_defaults(self) -> None:
        from biomechanics.standards.adult_standards import get_body_defaults
        male = get_body_defaults(Gender.MALE)
        female = get_body_defaults(Gender.FEMALE)
        assert male.height_cm > female.height_cm
        assert male.weight_kg > female.weight_kg

    def test_shooting_angles_match_constants(self) -> None:
        """성인 슈팅 각도가 biomechanics_constants 관절 각도와 일치."""
        from biomechanics.standards.adult_standards import SHOOTING_OPTIMAL_ANGLES_ADULT
        from shared.constants.biomechanics_constants import SHOOTING_OPTIMAL_ANGLES
        # ball_release_angle은 공 궤적(관절이 아님)이므로 제외
        joint_keys = {k for k in SHOOTING_OPTIMAL_ANGLES if not k.startswith("ball_")}
        for key in joint_keys:
            assert key in SHOOTING_OPTIMAL_ANGLES_ADULT
            assert SHOOTING_OPTIMAL_ANGLES_ADULT[key] == SHOOTING_OPTIMAL_ANGLES[key]


# ============================================================
# Section 5: senior_standards 테스트
# ============================================================
class TestSeniorStandards:
    """시니어 기준값 테스트."""

    def test_target_age_group(self) -> None:
        from biomechanics.standards.senior_standards import TARGET_AGE_GROUP
        assert TARGET_AGE_GROUP == AgeGroup.SENIOR

    def test_velocity_factor(self) -> None:
        from biomechanics.standards.senior_standards import VELOCITY_FACTOR
        assert VELOCITY_FACTOR == 0.78

    def test_rom_contraction(self) -> None:
        from biomechanics.standards.senior_standards import ROM_EXPANSION_FACTOR
        assert ROM_EXPANSION_FACTOR < 1.0  # 시니어는 ROM 감소

    def test_muscle_mass_decline(self) -> None:
        from biomechanics.standards.senior_standards import SENIOR_BODY_DEFAULTS
        for key in ("50s", "60s", "70s", "80+"):
            assert SENIOR_BODY_DEFAULTS[key].muscle_mass_ratio < 1.0

    def test_muscle_mass_progressive_decline(self) -> None:
        """연대가 올라갈수록 근감소 심화."""
        from biomechanics.standards.senior_standards import SENIOR_BODY_DEFAULTS
        keys = ["50s", "60s", "70s", "80+"]
        for i in range(1, len(keys)):
            prev = SENIOR_BODY_DEFAULTS[keys[i - 1]].muscle_mass_ratio
            curr = SENIOR_BODY_DEFAULTS[keys[i]].muscle_mass_ratio
            assert curr < prev

    def test_get_body_defaults(self) -> None:
        from biomechanics.standards.senior_standards import get_body_defaults
        d = get_body_defaults(55)
        assert d.age_range == (50, 59)
        d = get_body_defaults(85)
        assert d.age_range == (80, 99)

    def test_get_body_defaults_invalid_age(self) -> None:
        from biomechanics.standards.senior_standards import get_body_defaults
        with pytest.raises(ValueError):
            get_body_defaults(45)

    def test_get_muscle_mass_ratio(self) -> None:
        from biomechanics.standards.senior_standards import get_muscle_mass_ratio
        assert get_muscle_mass_ratio(55) == 0.92
        assert get_muscle_mass_ratio(85) == 0.60

    def test_safety_limits_stricter(self) -> None:
        """시니어 안전 상한이 성인보다 낮음."""
        from biomechanics.standards.senior_standards import (
            VERTICAL_GRF_MAX_SAFE_BW as senior_max,
            MAX_JUMP_LANDINGS_PER_SESSION as senior_jumps,
        )
        from biomechanics.standards.adult_standards import (
            VERTICAL_GRF_MAX_SAFE_BW as adult_max,
            MAX_JUMP_LANDINGS_PER_SESSION as adult_jumps,
        )
        assert senior_max < adult_max
        assert senior_jumps < adult_jumps


# ============================================================
# Section 6: league_standards 통합 테스트
# ============================================================
class TestLeagueStandards:
    """league_standards 통합 조회 테스트."""

    def test_get_standard_adult_male_fiba(self) -> None:
        from biomechanics.standards.league_standards import get_standard
        std = get_standard(AgeGroup.ADULT, Gender.MALE, )
        assert std.age_group == AgeGroup.ADULT
        assert std.gender == Gender.MALE
        assert std.velocity_factor == 1.00
        assert std.angle_tolerance == 0.0

    def test_get_standard_youth(self) -> None:
        from biomechanics.standards.league_standards import get_standard
        from biomechanics.standards.region_types import LeagueType
        std = get_standard(AgeGroup.YOUTH, Gender.FEMALE, LeagueType.KBL)
        assert std.velocity_factor == 0.65
        assert std.angle_tolerance == 15.0

    def test_get_standard_has_all_fields(self) -> None:
        from biomechanics.standards.league_standards import get_standard
        std = get_standard(AgeGroup.ADULT)
        # 모든 필수 필드 존재 확인
        assert std.shooting_angles is not None
        assert std.defensive_angles is not None
        assert std.dribbling_angles is not None
        assert std.acceleration_normal is not None
        assert std.stability_min > 0
        assert std.grf_max_safe > 0
        assert std.severity_warning > 0
        assert std.max_jumps_per_session > 0

    def test_get_standard_by_age(self) -> None:
        from biomechanics.standards.league_standards import get_standard_by_age
        std = get_standard_by_age(10)  # 유소년
        assert std.age_group == AgeGroup.YOUTH
        std = get_standard_by_age(15)  # 청소년
        assert std.age_group == AgeGroup.TEEN
        std = get_standard_by_age(30)  # 성인
        assert std.age_group == AgeGroup.ADULT
        std = get_standard_by_age(60)  # 시니어
        assert std.age_group == AgeGroup.SENIOR

    def test_get_velocity_threshold(self) -> None:
        from biomechanics.standards.league_standards import get_velocity_threshold
        # 성인 남성 = 1.0
        assert get_velocity_threshold(AgeGroup.ADULT, Gender.MALE) == 1.00
        # 유소년 남성 = 0.65
        assert get_velocity_threshold(AgeGroup.YOUTH, Gender.MALE) == 0.65

    def test_get_angle_tolerance(self) -> None:
        from biomechanics.standards.league_standards import get_angle_tolerance
        assert get_angle_tolerance(AgeGroup.ADULT) == 0.0
        assert get_angle_tolerance(AgeGroup.YOUTH) == 15.0
        assert get_angle_tolerance(AgeGroup.TEEN) == 8.0
        assert get_angle_tolerance(AgeGroup.SENIOR) == 10.0

    def test_get_severity_thresholds(self) -> None:
        from biomechanics.standards.league_standards import get_severity_thresholds
        w, c, s = get_severity_thresholds(AgeGroup.ADULT)
        assert w == 10.0
        assert c == 20.0
        assert s == 30.0

    def test_three_point_factor(self) -> None:
        from biomechanics.standards.league_standards import get_three_point_factor
        from biomechanics.standards.region_types import LeagueType
        assert get_three_point_factor(LeagueType.FIBA) == pytest.approx(1.0)
        assert get_three_point_factor(LeagueType.NBA) > 1.0  # NBA 3점이 더 멀다

    def test_court_area_factor(self) -> None:
        from biomechanics.standards.league_standards import get_court_area_factor
        from biomechanics.standards.region_types import LeagueType
        assert get_court_area_factor(LeagueType.FIBA) == pytest.approx(1.0)
        assert get_court_area_factor(LeagueType.NBA) > 1.0  # NBA 코트가 더 크다

    def test_frozen_standard(self) -> None:
        from biomechanics.standards.league_standards import get_standard
        std = get_standard(AgeGroup.ADULT)
        with pytest.raises(AttributeError):
            std.velocity_factor = 2.0  # type: ignore[misc]

    def test_slots_standard(self) -> None:
        from biomechanics.standards.league_standards import get_standard
        std = get_standard(AgeGroup.ADULT)
        assert not hasattr(std, "__dict__")


# ============================================================
# Section 7: standards/__init__.py lazy import 테스트
# ============================================================
class TestStandardsInit:
    """standards 패키지 lazy import 테스트."""

    def test_lazy_import_league_type(self) -> None:
        from biomechanics.standards import LeagueType
        assert len(LeagueType) == 4

    def test_lazy_import_get_standard(self) -> None:
        from biomechanics.standards import get_standard
        std = get_standard(AgeGroup.ADULT)
        assert std.velocity_factor == 1.00

    def test_lazy_import_nonexistent(self) -> None:
        with pytest.raises(ImportError):
            from biomechanics.standards import NonExistentSymbol  # type: ignore[attr-defined]  # noqa: F401


# ============================================================
# Section 8: 전체 일관성 검증
# ============================================================
class TestCrossAgeConsistency:
    """연령대 간 기준값 일관성 검증."""

    def test_velocity_factor_ordering(self) -> None:
        """유소년 < 시니어 < 청소년 < 성인 순서."""
        from biomechanics.standards import youth_standards, teen_standards
        from biomechanics.standards import adult_standards, senior_standards
        assert youth_standards.VELOCITY_FACTOR < teen_standards.VELOCITY_FACTOR
        assert teen_standards.VELOCITY_FACTOR < adult_standards.VELOCITY_FACTOR
        assert senior_standards.VELOCITY_FACTOR < adult_standards.VELOCITY_FACTOR

    def test_angle_tolerance_ordering(self) -> None:
        """유소년(15) > 시니어(10) > 청소년(8) > 성인(0)."""
        from biomechanics.standards import youth_standards, teen_standards
        from biomechanics.standards import adult_standards, senior_standards
        assert youth_standards.ANGLE_TOLERANCE > senior_standards.ANGLE_TOLERANCE
        assert senior_standards.ANGLE_TOLERANCE > teen_standards.ANGLE_TOLERANCE
        assert teen_standards.ANGLE_TOLERANCE > adult_standards.ANGLE_TOLERANCE

    def test_grf_max_safe_ordering(self) -> None:
        """시니어 < 유소년 < 청소년 < 성인."""
        from biomechanics.standards import youth_standards, teen_standards
        from biomechanics.standards import adult_standards, senior_standards
        assert senior_standards.VERTICAL_GRF_MAX_SAFE_BW < youth_standards.VERTICAL_GRF_MAX_SAFE_BW
        assert youth_standards.VERTICAL_GRF_MAX_SAFE_BW < teen_standards.VERTICAL_GRF_MAX_SAFE_BW
        assert teen_standards.VERTICAL_GRF_MAX_SAFE_BW < adult_standards.VERTICAL_GRF_MAX_SAFE_BW

    def test_stability_min_ordering(self) -> None:
        """시니어 < 유소년 < 청소년 < 성인."""
        from biomechanics.standards import youth_standards, teen_standards
        from biomechanics.standards import adult_standards, senior_standards
        assert senior_standards.STABILITY_INDEX_MIN_STABLE < youth_standards.STABILITY_INDEX_MIN_STABLE
        assert youth_standards.STABILITY_INDEX_MIN_STABLE < teen_standards.STABILITY_INDEX_MIN_STABLE
        assert teen_standards.STABILITY_INDEX_MIN_STABLE < adult_standards.STABILITY_INDEX_MIN_STABLE

    def test_all_shooting_angles_have_same_keys(self) -> None:
        """4개 연령대 슈팅 각도 키가 동일."""
        from biomechanics.standards.youth_standards import SHOOTING_OPTIMAL_ANGLES_YOUTH
        from biomechanics.standards.teen_standards import SHOOTING_OPTIMAL_ANGLES_TEEN
        from biomechanics.standards.adult_standards import SHOOTING_OPTIMAL_ANGLES_ADULT
        from biomechanics.standards.senior_standards import SHOOTING_OPTIMAL_ANGLES_SENIOR

        keys = set(SHOOTING_OPTIMAL_ANGLES_ADULT.keys())
        assert set(SHOOTING_OPTIMAL_ANGLES_YOUTH.keys()) == keys
        assert set(SHOOTING_OPTIMAL_ANGLES_TEEN.keys()) == keys
        assert set(SHOOTING_OPTIMAL_ANGLES_SENIOR.keys()) == keys
