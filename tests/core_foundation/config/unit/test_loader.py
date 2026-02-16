# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/config/unit
파일: test_loader.py
설명: ConfigLoader 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    - Enum (ConfigFormat, ConfigSource)
    - 데이터 클래스 (ConfigEntry, ConfigMetadata)
    - ConfigLoader 싱글톤 패턴
    - YAML/JSON 파일 로드
    - 프로파일 기반 로드
    - dot notation 값 조회
    - 타입 변환 조회 (get_int, get_float, get_bool 등)
    - 값 설정 (set, set_multiple)
    - 딥 머지
    - 환경변수 오버라이드
    - 유틸리티 (keys, items, to_dict, clear, has)
    - 헬퍼 함수 (load_config, get_config_value)
    - 예외 처리
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config.loader import (
    ConfigFormat,
    ConfigSource,
    ConfigEntry,
    ConfigMetadata,
    ConfigLoader,
    load_config,
    get_config_value,
    ENV_PREFIX,
    DEFAULT_CONFIG_PATHS,
    YAML_EXTENSIONS,
    JSON_EXTENSIONS,
    PROFILE_ENV_VAR,
    DEFAULT_PROFILE,
)
from shared.exceptions.validation_exceptions import (
    ConfigurationNotFoundException,
    ConfigurationParseException,
    ConfigurationException,
)

# 픽스처 경로
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# =============================================================================
# 테스트 결과 클래스
# =============================================================================
class TestResult:
    """테스트 결과 저장"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        """테스트 통과"""
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        """테스트 실패"""
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        """테스트 요약"""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# =============================================================================
# 헬퍼: 각 테스트 전 싱글톤 리셋
# =============================================================================
def reset_loader() -> ConfigLoader:
    """테스트 전 ConfigLoader 싱글톤 리셋 후 새 인스턴스 반환."""
    ConfigLoader.reset_instance()
    return ConfigLoader.get_instance()


# =============================================================================
# [1] Enum 테스트
# =============================================================================
def test_config_format_enum(result: TestResult) -> None:
    """ConfigFormat Enum 멤버 테스트."""
    try:
        # 멤버 존재 확인
        assert hasattr(ConfigFormat, "YAML"), "YAML 멤버 누락"
        assert hasattr(ConfigFormat, "JSON"), "JSON 멤버 누락"
        assert hasattr(ConfigFormat, "AUTO"), "AUTO 멤버 누락"

        # 멤버 수 확인
        members = list(ConfigFormat)
        assert len(members) == 3, f"멤버 수 불일치: {len(members)} != 3"

        # 고유성 확인
        values = [m.value for m in members]
        assert len(values) == len(set(values)), "값 중복 존재"

        result.ok("ConfigFormat Enum 멤버")
    except AssertionError as e:
        result.fail("ConfigFormat Enum 멤버", str(e))


def test_config_source_enum(result: TestResult) -> None:
    """ConfigSource Enum 멤버 테스트."""
    try:
        assert hasattr(ConfigSource, "FILE"), "FILE 멤버 누락"
        assert hasattr(ConfigSource, "ENV"), "ENV 멤버 누락"
        assert hasattr(ConfigSource, "DEFAULT"), "DEFAULT 멤버 누락"

        members = list(ConfigSource)
        assert len(members) == 3, f"멤버 수 불일치: {len(members)} != 3"

        values = [m.value for m in members]
        assert len(values) == len(set(values)), "값 중복 존재"

        result.ok("ConfigSource Enum 멤버")
    except AssertionError as e:
        result.fail("ConfigSource Enum 멤버", str(e))


# =============================================================================
# [2] 데이터 클래스 테스트
# =============================================================================
def test_config_entry_creation(result: TestResult) -> None:
    """ConfigEntry 기본 생성 테스트."""
    try:
        entry = ConfigEntry(
            key="database.host",
            value="localhost",
            source=ConfigSource.FILE,
        )
        assert entry.key == "database.host", "key 불일치"
        assert entry.value == "localhost", "value 불일치"
        assert entry.source == ConfigSource.FILE, "source 불일치"
        # __post_init__: original_value가 None이면 value로 설정
        assert entry.original_value == "localhost", "original_value 미설정"
        assert isinstance(entry.loaded_at, datetime), "loaded_at 타입 오류"
        assert entry.file_path is None, "file_path 기본값 오류"

        result.ok("ConfigEntry 기본 생성")
    except AssertionError as e:
        result.fail("ConfigEntry 기본 생성", str(e))


def test_config_entry_with_original_value(result: TestResult) -> None:
    """ConfigEntry original_value 직접 설정 테스트."""
    try:
        entry = ConfigEntry(
            key="server.port",
            value=8000,
            source=ConfigSource.ENV,
            original_value="8000",
        )
        assert entry.value == 8000, "value 불일치"
        assert entry.original_value == "8000", "original_value 오버라이드 실패"
        assert entry.source == ConfigSource.ENV, "source 불일치"

        result.ok("ConfigEntry original_value 직접 설정")
    except AssertionError as e:
        result.fail("ConfigEntry original_value 직접 설정", str(e))


def test_config_metadata_creation(result: TestResult) -> None:
    """ConfigMetadata 기본 생성 테스트."""
    try:
        meta = ConfigMetadata()
        assert meta.version == "1.0.0", "version 기본값 오류"
        assert meta.profile == DEFAULT_PROFILE, "profile 기본값 오류"
        assert meta.loaded_files == [], "loaded_files 기본값 오류"
        assert isinstance(meta.loaded_at, datetime), "loaded_at 타입 오류"
        assert meta.env_overrides == [], "env_overrides 기본값 오류"
        assert meta.total_entries == 0, "total_entries 기본값 오류"

        result.ok("ConfigMetadata 기본 생성")
    except AssertionError as e:
        result.fail("ConfigMetadata 기본 생성", str(e))


def test_config_metadata_add_loaded_file(result: TestResult) -> None:
    """ConfigMetadata add_loaded_file 테스트."""
    try:
        meta = ConfigMetadata()
        meta.add_loaded_file("config/app.yaml")
        assert "config/app.yaml" in meta.loaded_files, "파일 추가 실패"

        # 중복 추가 방지
        meta.add_loaded_file("config/app.yaml")
        assert len(meta.loaded_files) == 1, f"중복 추가 방지 실패: {len(meta.loaded_files)}"

        # 다른 파일 추가
        meta.add_loaded_file("config/app.dev.yaml")
        assert len(meta.loaded_files) == 2, "두 번째 파일 추가 실패"

        result.ok("ConfigMetadata add_loaded_file")
    except AssertionError as e:
        result.fail("ConfigMetadata add_loaded_file", str(e))


def test_config_metadata_add_env_override(result: TestResult) -> None:
    """ConfigMetadata add_env_override 테스트."""
    try:
        meta = ConfigMetadata()
        meta.add_env_override("database.host")
        assert "database.host" in meta.env_overrides, "오버라이드 키 추가 실패"

        # 중복 방지
        meta.add_env_override("database.host")
        assert len(meta.env_overrides) == 1, "중복 추가 방지 실패"

        result.ok("ConfigMetadata add_env_override")
    except AssertionError as e:
        result.fail("ConfigMetadata add_env_override", str(e))


def test_config_metadata_to_dict(result: TestResult) -> None:
    """ConfigMetadata to_dict 테스트."""
    try:
        meta = ConfigMetadata()
        meta.add_loaded_file("config/app.yaml")
        d = meta.to_dict()

        assert "version" in d, "version 누락"
        assert "profile" in d, "profile 누락"
        assert "loaded_files" in d, "loaded_files 누락"
        assert "loaded_at" in d, "loaded_at 누락"
        assert "last_updated_at" in d, "last_updated_at 누락"
        assert "env_overrides" in d, "env_overrides 누락"
        assert "total_entries" in d, "total_entries 누락"
        assert isinstance(d["loaded_at"], str), "loaded_at ISO 변환 실패"

        result.ok("ConfigMetadata to_dict")
    except AssertionError as e:
        result.fail("ConfigMetadata to_dict", str(e))


# =============================================================================
# [3] 상수 테스트
# =============================================================================
def test_constants(result: TestResult) -> None:
    """모듈 상수 테스트."""
    try:
        assert ENV_PREFIX == "COURTVIEW_", f"ENV_PREFIX 불일치: {ENV_PREFIX}"
        assert isinstance(DEFAULT_CONFIG_PATHS, list), "DEFAULT_CONFIG_PATHS 타입 오류"
        assert len(DEFAULT_CONFIG_PATHS) > 0, "DEFAULT_CONFIG_PATHS 빈 리스트"
        assert ".yaml" in YAML_EXTENSIONS, "YAML_EXTENSIONS .yaml 누락"
        assert ".yml" in YAML_EXTENSIONS, "YAML_EXTENSIONS .yml 누락"
        assert ".json" in JSON_EXTENSIONS, "JSON_EXTENSIONS .json 누락"
        assert PROFILE_ENV_VAR == "COURTVIEW_PROFILE", f"PROFILE_ENV_VAR 불일치"
        assert DEFAULT_PROFILE == "development", f"DEFAULT_PROFILE 불일치"

        result.ok("모듈 상수")
    except AssertionError as e:
        result.fail("모듈 상수", str(e))


# =============================================================================
# [4] 싱글톤 패턴 테스트
# =============================================================================
def test_singleton_same_instance(result: TestResult) -> None:
    """싱글톤 동일 인스턴스 테스트."""
    try:
        loader1 = reset_loader()
        loader2 = ConfigLoader.get_instance()
        assert loader1 is loader2, "싱글톤 인스턴스 불일치"

        result.ok("싱글톤 동일 인스턴스")
    except AssertionError as e:
        result.fail("싱글톤 동일 인스턴스", str(e))


def test_singleton_reset(result: TestResult) -> None:
    """싱글톤 리셋 테스트."""
    try:
        loader1 = reset_loader()
        ConfigLoader.reset_instance()
        loader2 = ConfigLoader.get_instance()
        assert loader1 is not loader2, "리셋 후 동일 인스턴스"

        result.ok("싱글톤 리셋")
    except AssertionError as e:
        result.fail("싱글톤 리셋", str(e))


def test_singleton_initial_state(result: TestResult) -> None:
    """싱글톤 초기 상태 테스트."""
    try:
        loader = reset_loader()
        assert loader.to_dict() == {}, "초기 설정 비어있지 않음"
        assert loader.keys() == [], "초기 키 비어있지 않음"
        assert loader.metadata.total_entries == 0, "초기 항목 수 0 아님"

        result.ok("싱글톤 초기 상태")
    except AssertionError as e:
        result.fail("싱글톤 초기 상태", str(e))


# =============================================================================
# [5] YAML 파일 로드 테스트
# =============================================================================
def test_load_yaml_file(result: TestResult) -> None:
    """YAML 파일 로드 테스트."""
    try:
        loader = reset_loader()
        data = loader.load(FIXTURES_DIR / "test_base.yaml")

        assert isinstance(data, dict), "반환값 딕셔너리 아님"
        assert data.get("environment") == "development", "environment 불일치"
        assert data["app"]["name"] == "COURTVIEW Desktop", "app.name 불일치"
        assert data["gpu"]["cuda_device"] == "cuda:0", "gpu.cuda_device 불일치"
        assert data["camera"]["count"] == 4, "camera.count 불일치"

        result.ok("YAML 파일 로드")
    except AssertionError as e:
        result.fail("YAML 파일 로드", str(e))


def test_load_json_file(result: TestResult) -> None:
    """JSON 파일 로드 테스트."""
    try:
        loader = reset_loader()
        data = loader.load(FIXTURES_DIR / "test_base.json")

        assert isinstance(data, dict), "반환값 딕셔너리 아님"
        assert data.get("environment") == "testing", "environment 불일치"
        assert data["app"]["name"] == "COURTVIEW Test", "app.name 불일치"
        assert data["gpu"]["cuda_device"] == "cuda:1", "gpu.cuda_device 불일치"

        result.ok("JSON 파일 로드")
    except AssertionError as e:
        result.fail("JSON 파일 로드", str(e))


def test_load_yaml_explicit_format(result: TestResult) -> None:
    """명시적 YAML 포맷 로드 테스트."""
    try:
        loader = reset_loader()
        data = loader.load(FIXTURES_DIR / "test_base.yaml", format=ConfigFormat.YAML)

        assert "app" in data, "YAML 명시적 포맷 로드 실패"

        result.ok("명시적 YAML 포맷 로드")
    except AssertionError as e:
        result.fail("명시적 YAML 포맷 로드", str(e))


def test_load_json_explicit_format(result: TestResult) -> None:
    """명시적 JSON 포맷 로드 테스트."""
    try:
        loader = reset_loader()
        data = loader.load(FIXTURES_DIR / "test_base.json", format=ConfigFormat.JSON)

        assert "app" in data, "JSON 명시적 포맷 로드 실패"

        result.ok("명시적 JSON 포맷 로드")
    except AssertionError as e:
        result.fail("명시적 JSON 포맷 로드", str(e))


def test_load_nonexistent_required(result: TestResult) -> None:
    """존재하지 않는 필수 파일 예외 테스트."""
    try:
        loader = reset_loader()
        try:
            loader.load("nonexistent/file.yaml", required=True)
            result.fail("존재하지 않는 필수 파일 예외", "예외 미발생")
        except ConfigurationNotFoundException:
            result.ok("존재하지 않는 필수 파일 예외")
    except Exception as e:
        result.fail("존재하지 않는 필수 파일 예외", str(e))


def test_load_nonexistent_optional(result: TestResult) -> None:
    """존재하지 않는 선택적 파일 테스트."""
    try:
        loader = reset_loader()
        data = loader.load("nonexistent/file.yaml", required=False)
        assert data == {}, "선택적 파일 미존재 시 빈 딕셔너리 아님"

        result.ok("존재하지 않는 선택적 파일")
    except AssertionError as e:
        result.fail("존재하지 않는 선택적 파일", str(e))


def test_load_invalid_yaml(result: TestResult) -> None:
    """유효하지 않은 YAML 파일 예외 테스트."""
    try:
        loader = reset_loader()
        try:
            loader.load(FIXTURES_DIR / "test_invalid.yaml")
            result.fail("유효하지 않은 YAML 예외", "예외 미발생")
        except ConfigurationParseException:
            result.ok("유효하지 않은 YAML 예외")
    except Exception as e:
        result.fail("유효하지 않은 YAML 예외", str(e))


def test_load_metadata_update(result: TestResult) -> None:
    """파일 로드 후 메타데이터 업데이트 테스트."""
    try:
        loader = reset_loader()
        base_path = str(FIXTURES_DIR / "test_base.yaml")
        loader.load(base_path)

        meta = loader.metadata
        assert base_path in meta.loaded_files, "loaded_files 미업데이트"
        assert meta.total_entries > 0, f"total_entries 0: {meta.total_entries}"

        result.ok("파일 로드 후 메타데이터 업데이트")
    except AssertionError as e:
        result.fail("파일 로드 후 메타데이터 업데이트", str(e))


# =============================================================================
# [6] 다중 파일 로드 / 딥 머지 테스트
# =============================================================================
def test_load_multiple(result: TestResult) -> None:
    """다중 파일 로드 및 병합 테스트."""
    try:
        loader = reset_loader()
        loader.load_multiple(
            [
                FIXTURES_DIR / "test_base.yaml",
                FIXTURES_DIR / "test_override.yaml",
            ],
            required=True,
        )

        # 오버라이드된 값 확인
        assert loader.get("gpu.memory_fraction") == 0.5, "오버라이드 값 불일치 (gpu.memory_fraction)"
        assert loader.get("gpu.precision") == "fp32", "오버라이드 값 불일치 (gpu.precision)"
        assert loader.get("camera.count") == 2, "오버라이드 값 불일치 (camera.count)"
        assert loader.get("analysis.target_fps") == 60, "오버라이드 값 불일치 (analysis.target_fps)"

        # 오버라이드되지 않은 값 유지 확인
        assert loader.get("app.name") == "COURTVIEW Desktop", "기존 값 유실 (app.name)"
        assert loader.get("gpu.cuda_device") == "cuda:0", "기존 값 유실 (gpu.cuda_device)"
        assert loader.get("server.port") == 8000, "기존 값 유실 (server.port)"

        result.ok("다중 파일 로드 및 병합")
    except AssertionError as e:
        result.fail("다중 파일 로드 및 병합", str(e))


def test_deep_merge_nested(result: TestResult) -> None:
    """딥 머지 중첩 딕셔너리 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")
        loader.load(FIXTURES_DIR / "test_override.yaml")

        # 오버라이드된 중첩 값
        assert loader.get("camera.resolution.width") == 1280, "중첩 오버라이드 실패 (width)"
        assert loader.get("camera.resolution.height") == 720, "중첩 오버라이드 실패 (height)"

        # 오버라이드 되지 않은 중첩 값 (camera.fps는 override에 없으므로 유지)
        assert loader.get("camera.fps") == 60, "중첩 병합 시 기존 값 유실 (fps)"

        result.ok("딥 머지 중첩 딕셔너리")
    except AssertionError as e:
        result.fail("딥 머지 중첩 딕셔너리", str(e))


def test_load_overwrite_mode(result: TestResult) -> None:
    """merge=False 덮어쓰기 모드 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")
        loader.load(FIXTURES_DIR / "test_override.yaml", merge=False)

        # override 파일의 값만 존재
        assert loader.get("gpu.memory_fraction") == 0.5, "덮어쓰기 값 불일치"
        # base에만 있던 값은 사라짐
        assert loader.get("app.name") is None, "덮어쓰기 후 기존 값 잔존"
        assert loader.get("server.port") is None, "덮어쓰기 후 기존 값 잔존"

        result.ok("merge=False 덮어쓰기 모드")
    except AssertionError as e:
        result.fail("merge=False 덮어쓰기 모드", str(e))


# =============================================================================
# [7] 프로파일 기반 로드 테스트
# =============================================================================
def test_load_with_profile(result: TestResult) -> None:
    """프로파일 기반 설정 로드 테스트."""
    try:
        loader = reset_loader()
        loader.load_with_profile(
            base_name="test_base",
            config_dir=str(FIXTURES_DIR),
        )

        # 기본 설정 + 프로파일(development) + local 병합 확인
        # base: app.name = "COURTVIEW Desktop"
        assert loader.get("app.name") == "COURTVIEW Desktop", "기본 설정 누락"

        # development 프로파일: app.debug = true, gpu.memory_fraction = 0.7
        assert loader.get("app.debug") is True, "프로파일 app.debug 불일치"
        assert loader.get("gpu.memory_fraction") == 0.7, "프로파일 gpu.memory_fraction 불일치"

        # local 오버라이드: server.port = 9000
        assert loader.get("server.port") == 9000, "로컬 오버라이드 server.port 불일치"
        assert loader.get("server.host") == "127.0.0.1", "로컬 오버라이드 server.host 불일치"

        result.ok("프로파일 기반 설정 로드")
    except AssertionError as e:
        result.fail("프로파일 기반 설정 로드", str(e))


def test_load_with_profile_metadata(result: TestResult) -> None:
    """프로파일 로드 후 메타데이터 확인."""
    try:
        loader = reset_loader()
        loader.load_with_profile(
            base_name="test_base",
            config_dir=str(FIXTURES_DIR),
        )

        meta = loader.metadata
        # 최소 기본 파일은 로드되어야 함
        assert len(meta.loaded_files) >= 1, f"로드된 파일 부족: {len(meta.loaded_files)}"

        result.ok("프로파일 로드 후 메타데이터")
    except AssertionError as e:
        result.fail("프로파일 로드 후 메타데이터", str(e))


# =============================================================================
# [8] 값 조회 테스트 (get / dot notation)
# =============================================================================
def test_get_simple(result: TestResult) -> None:
    """단순 키 조회 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        assert loader.get("environment") == "development", "environment 불일치"

        result.ok("단순 키 조회")
    except AssertionError as e:
        result.fail("단순 키 조회", str(e))


def test_get_dot_notation(result: TestResult) -> None:
    """dot notation 중첩 키 조회 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        assert loader.get("gpu.cuda_device") == "cuda:0", "1단계 중첩 불일치"
        assert loader.get("camera.resolution.width") == 1920, "2단계 중첩 불일치"

        result.ok("dot notation 중첩 키 조회")
    except AssertionError as e:
        result.fail("dot notation 중첩 키 조회", str(e))


def test_get_deep_nesting(result: TestResult) -> None:
    """깊은 중첩 키 조회 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_nested.yaml")

        val = loader.get("level1.level2.level3.level4.level5.deep_value")
        assert val == "found_it", f"5단계 중첩 조회 실패: {val}"

        num = loader.get("level1.level2.level3.level4.level5.deep_number")
        assert num == 42, f"5단계 중첩 숫자 조회 실패: {num}"

        result.ok("깊은 중첩 키 조회")
    except AssertionError as e:
        result.fail("깊은 중첩 키 조회", str(e))


def test_get_default_value(result: TestResult) -> None:
    """기본값 반환 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        val = loader.get("nonexistent.key", "fallback")
        assert val == "fallback", f"기본값 반환 실패: {val}"

        val_none = loader.get("nonexistent.key")
        assert val_none is None, f"기본값 None 반환 실패: {val_none}"

        result.ok("기본값 반환")
    except AssertionError as e:
        result.fail("기본값 반환", str(e))


def test_get_with_type_conversion(result: TestResult) -> None:
    """타입 변환 조회 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        # str로 변환
        port = loader.get("server.port", value_type=str)
        assert port == "8000", f"str 변환 실패: {port}"
        assert isinstance(port, str), f"str 타입 아님: {type(port)}"

        # float로 변환
        count = loader.get("camera.count", value_type=float)
        assert count == 4.0, f"float 변환 실패: {count}"

        result.ok("타입 변환 조회")
    except AssertionError as e:
        result.fail("타입 변환 조회", str(e))


# =============================================================================
# [9] 타입별 get 메서드 테스트
# =============================================================================
def test_get_int(result: TestResult) -> None:
    """get_int 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        port = loader.get_int("server.port")
        assert port == 8000, f"get_int 실패: {port}"
        assert isinstance(port, int), f"타입 불일치: {type(port)}"

        # 존재하지 않는 키 → 기본값
        default_val = loader.get_int("nonexistent", 999)
        assert default_val == 999, f"기본값 실패: {default_val}"

        result.ok("get_int")
    except AssertionError as e:
        result.fail("get_int", str(e))


def test_get_float(result: TestResult) -> None:
    """get_float 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        frac = loader.get_float("gpu.memory_fraction")
        assert frac == 0.9, f"get_float 실패: {frac}"
        assert isinstance(frac, float), f"타입 불일치: {type(frac)}"

        result.ok("get_float")
    except AssertionError as e:
        result.fail("get_float", str(e))


def test_get_bool(result: TestResult) -> None:
    """get_bool 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        debug = loader.get_bool("app.debug")
        assert debug is True, f"get_bool 실패: {debug}"
        assert isinstance(debug, bool), f"타입 불일치: {type(debug)}"

        # 존재하지 않는 키 → 기본값
        default_val = loader.get_bool("nonexistent", False)
        assert default_val is False, f"기본값 실패: {default_val}"

        result.ok("get_bool")
    except AssertionError as e:
        result.fail("get_bool", str(e))


def test_get_str(result: TestResult) -> None:
    """get_str 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        name = loader.get_str("app.name")
        assert name == "COURTVIEW Desktop", f"get_str 실패: {name}"
        assert isinstance(name, str), f"타입 불일치: {type(name)}"

        result.ok("get_str")
    except AssertionError as e:
        result.fail("get_str", str(e))


def test_get_list(result: TestResult) -> None:
    """get_list 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_nested.yaml")

        lst = loader.get_list("level1.level2.level3.level4.level5.deep_list")
        assert isinstance(lst, list), f"타입 불일치: {type(lst)}"
        assert len(lst) == 3, f"리스트 길이 불일치: {len(lst)}"
        assert lst[0] == "alpha", f"리스트 첫 요소 불일치: {lst[0]}"

        # 존재하지 않는 키 → 빈 리스트
        empty = loader.get_list("nonexistent")
        assert empty == [], f"기본값 빈 리스트 실패: {empty}"

        # 스칼라 값 → 리스트 래핑
        loader.set("scalar_key", "single_value")
        wrapped = loader.get_list("scalar_key")
        assert wrapped == ["single_value"], f"스칼라 래핑 실패: {wrapped}"

        result.ok("get_list")
    except AssertionError as e:
        result.fail("get_list", str(e))


def test_get_dict(result: TestResult) -> None:
    """get_dict 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        gpu = loader.get_dict("gpu")
        assert isinstance(gpu, dict), f"타입 불일치: {type(gpu)}"
        assert "cuda_device" in gpu, "gpu 딕셔너리에 cuda_device 누락"

        # 존재하지 않는 키 → 빈 딕셔너리
        empty = loader.get_dict("nonexistent")
        assert empty == {}, f"기본값 빈 딕셔너리 실패: {empty}"

        result.ok("get_dict")
    except AssertionError as e:
        result.fail("get_dict", str(e))


def test_get_section(result: TestResult) -> None:
    """get_section 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        section = loader.get_section("server")
        assert isinstance(section, dict), "섹션 딕셔너리 아님"
        assert section.get("host") == "0.0.0.0", f"섹션 host 불일치: {section.get('host')}"
        assert section.get("port") == 8000, f"섹션 port 불일치: {section.get('port')}"

        result.ok("get_section")
    except AssertionError as e:
        result.fail("get_section", str(e))


def test_get_required_existing(result: TestResult) -> None:
    """get_required 존재하는 키 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        val = loader.get_required("app.name")
        assert val == "COURTVIEW Desktop", f"get_required 값 불일치: {val}"

        result.ok("get_required 존재하는 키")
    except AssertionError as e:
        result.fail("get_required 존재하는 키", str(e))


def test_get_required_missing(result: TestResult) -> None:
    """get_required 누락 키 예외 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        try:
            loader.get_required("nonexistent.key")
            result.fail("get_required 누락 키 예외", "예외 미발생")
        except ConfigurationException:
            result.ok("get_required 누락 키 예외")
    except Exception as e:
        result.fail("get_required 누락 키 예외", str(e))


# =============================================================================
# [10] 값 설정 테스트
# =============================================================================
def test_set_simple(result: TestResult) -> None:
    """set 단순 값 설정 테스트."""
    try:
        loader = reset_loader()
        loader.set("custom.key", "custom_value")

        assert loader.get("custom.key") == "custom_value", "set 값 불일치"

        result.ok("set 단순 값 설정")
    except AssertionError as e:
        result.fail("set 단순 값 설정", str(e))


def test_set_nested(result: TestResult) -> None:
    """set dot notation 중첩 설정 테스트."""
    try:
        loader = reset_loader()
        loader.set("a.b.c.d", 42)

        assert loader.get("a.b.c.d") == 42, "중첩 set 값 불일치"

        result.ok("set dot notation 중첩 설정")
    except AssertionError as e:
        result.fail("set dot notation 중첩 설정", str(e))


def test_set_updates_entry(result: TestResult) -> None:
    """set 후 ConfigEntry 생성 확인 테스트."""
    try:
        loader = reset_loader()
        loader.set("my.key", "my_value", ConfigSource.DEFAULT)

        entry = loader.get_entry("my.key")
        assert entry is not None, "ConfigEntry 미생성"
        assert entry.value == "my_value", f"entry.value 불일치: {entry.value}"
        assert entry.source == ConfigSource.DEFAULT, f"entry.source 불일치: {entry.source}"

        result.ok("set 후 ConfigEntry 생성")
    except AssertionError as e:
        result.fail("set 후 ConfigEntry 생성", str(e))


def test_set_multiple(result: TestResult) -> None:
    """set_multiple 테스트."""
    try:
        loader = reset_loader()
        loader.set_multiple({
            "key1": "value1",
            "key2": 42,
            "key3": True,
        })

        assert loader.get("key1") == "value1", "key1 불일치"
        assert loader.get("key2") == 42, "key2 불일치"
        assert loader.get("key3") is True, "key3 불일치"

        result.ok("set_multiple")
    except AssertionError as e:
        result.fail("set_multiple", str(e))


# =============================================================================
# [11] 유틸리티 메서드 테스트
# =============================================================================
def test_has(result: TestResult) -> None:
    """has 키 존재 확인 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        assert loader.has("app.name") is True, "has 실패 (존재하는 키)"
        assert loader.has("nonexistent") is False, "has 실패 (존재하지 않는 키)"

        result.ok("has 키 존재 확인")
    except AssertionError as e:
        result.fail("has 키 존재 확인", str(e))


def test_keys(result: TestResult) -> None:
    """keys 전체 키 목록 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        keys = loader.keys()
        assert isinstance(keys, list), "keys 반환 타입 오류"
        assert len(keys) > 0, "keys 빈 리스트"
        # environment는 최상위 키이므로 entries에 포함
        assert "environment" in keys, f"environment 키 누락: {keys[:5]}..."

        result.ok("keys 전체 키 목록")
    except AssertionError as e:
        result.fail("keys 전체 키 목록", str(e))


def test_items(result: TestResult) -> None:
    """items 반복 테스트."""
    try:
        loader = reset_loader()
        loader.set("a", 1)
        loader.set("b", 2)

        collected = dict(loader.items())
        assert collected.get("a") == 1, "items a 불일치"
        assert collected.get("b") == 2, "items b 불일치"

        result.ok("items 반복")
    except AssertionError as e:
        result.fail("items 반복", str(e))


def test_to_dict(result: TestResult) -> None:
    """to_dict 딕셔너리 반환 및 불변성 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        d = loader.to_dict()
        assert isinstance(d, dict), "to_dict 반환 타입 오류"
        assert "app" in d, "to_dict app 키 누락"

        # 딥카피 확인: 외부 수정이 내부에 영향 없어야 함
        d["app"]["name"] = "MODIFIED"
        assert loader.get("app.name") == "COURTVIEW Desktop", "to_dict 불변성 위반"

        result.ok("to_dict 딕셔너리 반환 및 불변성")
    except AssertionError as e:
        result.fail("to_dict 딕셔너리 반환 및 불변성", str(e))


def test_clear(result: TestResult) -> None:
    """clear 초기화 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")
        assert len(loader.keys()) > 0, "로드 후 키 없음"

        loader.clear()
        assert loader.to_dict() == {}, "clear 후 설정 비어있지 않음"
        assert loader.keys() == [], "clear 후 키 비어있지 않음"
        assert loader.metadata.total_entries == 0, "clear 후 total_entries 0 아님"

        result.ok("clear 초기화")
    except AssertionError as e:
        result.fail("clear 초기화", str(e))


def test_profile_property(result: TestResult) -> None:
    """profile 프로퍼티 테스트."""
    try:
        loader = reset_loader()
        profile = loader.profile
        assert isinstance(profile, str), f"profile 타입 오류: {type(profile)}"
        # 기본값은 development (환경변수 미설정 시)
        assert len(profile) > 0, "profile 빈 문자열"

        result.ok("profile 프로퍼티")
    except AssertionError as e:
        result.fail("profile 프로퍼티", str(e))


# =============================================================================
# [12] 환경변수 오버라이드 테스트
# =============================================================================
def test_env_override(result: TestResult) -> None:
    """환경변수 오버라이드 테스트."""
    env_key = f"{ENV_PREFIX}SERVER_PORT"
    try:
        # 환경변수 설정
        os.environ[env_key] = "3000"

        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        # 환경변수로 오버라이드된 값 확인
        val = loader.get("server.port")
        assert val == 3000, f"환경변수 오버라이드 실패: {val}"

        # 소스 확인
        entry = loader.get_entry("server.port")
        assert entry is not None, "오버라이드 엔트리 없음"
        assert entry.source == ConfigSource.ENV, f"소스 불일치: {entry.source}"
        assert entry.original_value == "3000", f"원본 값 불일치: {entry.original_value}"

        # 메타데이터 확인
        assert "server.port" in loader.metadata.env_overrides, "메타데이터 오버라이드 누락"

        result.ok("환경변수 오버라이드")
    except AssertionError as e:
        result.fail("환경변수 오버라이드", str(e))
    finally:
        os.environ.pop(env_key, None)


def test_env_bool_parsing(result: TestResult) -> None:
    """환경변수 불리언 파싱 테스트."""
    env_key = f"{ENV_PREFIX}APP_DEBUG"
    try:
        for true_val in ("true", "True", "yes", "1", "on"):
            os.environ[env_key] = true_val
            loader = reset_loader()
            loader.load(FIXTURES_DIR / "test_base.yaml")
            val = loader.get("app.debug")
            assert val is True, f"'{true_val}' → True 변환 실패: {val}"

        for false_val in ("false", "False", "no", "0", "off"):
            os.environ[env_key] = false_val
            loader = reset_loader()
            loader.load(FIXTURES_DIR / "test_base.yaml")
            val = loader.get("app.debug")
            assert val is False, f"'{false_val}' → False 변환 실패: {val}"

        result.ok("환경변수 불리언 파싱")
    except AssertionError as e:
        result.fail("환경변수 불리언 파싱", str(e))
    finally:
        os.environ.pop(env_key, None)


def test_env_numeric_parsing(result: TestResult) -> None:
    """환경변수 숫자 파싱 테스트."""
    try:
        # 정수
        int_key = f"{ENV_PREFIX}CAMERA_COUNT"
        os.environ[int_key] = "8"
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")
        val = loader.get("camera.count")
        assert val == 8, f"정수 변환 실패: {val}"
        assert isinstance(val, int), f"정수 타입 실패: {type(val)}"
        os.environ.pop(int_key, None)

        # 실수
        float_key = f"{ENV_PREFIX}GPU_MEMORY.FRACTION"
        os.environ[float_key] = "0.75"
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")
        val = loader.get("gpu.memory.fraction")
        assert val == 0.75, f"실수 변환 실패: {val}"
        os.environ.pop(float_key, None)

        result.ok("환경변수 숫자 파싱")
    except AssertionError as e:
        result.fail("환경변수 숫자 파싱", str(e))
    finally:
        os.environ.pop(f"{ENV_PREFIX}CAMERA_COUNT", None)
        os.environ.pop(f"{ENV_PREFIX}GPU_MEMORY.FRACTION", None)


def test_env_json_parsing(result: TestResult) -> None:
    """환경변수 JSON 파싱 테스트."""
    env_key = f"{ENV_PREFIX}CUSTOM_LIST"
    try:
        os.environ[env_key] = '["a","b","c"]'
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")
        val = loader.get("custom.list")
        assert isinstance(val, list), f"JSON 배열 변환 실패: {type(val)}"
        assert val == ["a", "b", "c"], f"JSON 배열 값 불일치: {val}"

        result.ok("환경변수 JSON 파싱")
    except AssertionError as e:
        result.fail("환경변수 JSON 파싱", str(e))
    finally:
        os.environ.pop(env_key, None)


# =============================================================================
# [13] 헬퍼 함수 테스트
# =============================================================================
def test_load_config_helper(result: TestResult) -> None:
    """load_config 헬퍼 함수 테스트."""
    try:
        ConfigLoader.reset_instance()
        data = load_config(FIXTURES_DIR / "test_base.yaml")

        assert isinstance(data, dict), "load_config 반환 타입 오류"
        assert "app" in data, "load_config app 키 누락"

        result.ok("load_config 헬퍼 함수")
    except AssertionError as e:
        result.fail("load_config 헬퍼 함수", str(e))


def test_get_config_value_helper(result: TestResult) -> None:
    """get_config_value 헬퍼 함수 테스트."""
    try:
        ConfigLoader.reset_instance()
        load_config(FIXTURES_DIR / "test_base.yaml")

        val = get_config_value("app.name")
        assert val == "COURTVIEW Desktop", f"get_config_value 불일치: {val}"

        default_val = get_config_value("nonexistent", "fallback")
        assert default_val == "fallback", f"get_config_value 기본값 실패: {default_val}"

        typed_val = get_config_value("server.port", 0, int)
        assert typed_val == 8000, f"get_config_value 타입 변환 실패: {typed_val}"

        result.ok("get_config_value 헬퍼 함수")
    except AssertionError as e:
        result.fail("get_config_value 헬퍼 함수", str(e))


# =============================================================================
# [14] get_entry 메타정보 테스트
# =============================================================================
def test_get_entry(result: TestResult) -> None:
    """get_entry 설정 항목 메타정보 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        entry = loader.get_entry("app.name")
        assert entry is not None, "entry 없음"
        assert isinstance(entry, ConfigEntry), "entry 타입 오류"
        assert entry.key == "app.name", f"entry.key 불일치: {entry.key}"
        assert entry.value == "COURTVIEW Desktop", f"entry.value 불일치: {entry.value}"
        assert entry.source == ConfigSource.FILE, f"entry.source 불일치: {entry.source}"
        assert entry.file_path is not None, "entry.file_path 없음"

        # 존재하지 않는 키
        none_entry = loader.get_entry("nonexistent")
        assert none_entry is None, "존재하지 않는 키에 entry 반환"

        result.ok("get_entry 설정 항목 메타정보")
    except AssertionError as e:
        result.fail("get_entry 설정 항목 메타정보", str(e))


# =============================================================================
# [15] 스레드 안전성 테스트
# =============================================================================
def test_thread_safety(result: TestResult) -> None:
    """스레드 안전성 기본 테스트."""
    import threading

    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        errors = []
        barrier = threading.Barrier(10)

        def concurrent_read(thread_id: int):
            try:
                barrier.wait(timeout=5)
                for _ in range(100):
                    val = loader.get("app.name")
                    if val != "COURTVIEW Desktop":
                        errors.append(f"Thread-{thread_id}: 값 불일치 {val}")
            except Exception as e:
                errors.append(f"Thread-{thread_id}: {e}")

        threads = [
            threading.Thread(target=concurrent_read, args=(i,))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        if errors:
            result.fail("스레드 안전성", f"{len(errors)}건 오류: {errors[0]}")
        else:
            result.ok("스레드 안전성")
    except Exception as e:
        result.fail("스레드 안전성", str(e))


def test_thread_safety_write(result: TestResult) -> None:
    """동시 쓰기 스레드 안전성 테스트."""
    import threading

    try:
        loader = reset_loader()
        errors = []
        barrier = threading.Barrier(5)

        def concurrent_write(thread_id: int):
            try:
                barrier.wait(timeout=5)
                for i in range(50):
                    loader.set(f"thread.{thread_id}.key{i}", i)
            except Exception as e:
                errors.append(f"Thread-{thread_id}: {e}")

        threads = [
            threading.Thread(target=concurrent_write, args=(i,))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        if errors:
            result.fail("동시 쓰기 스레드 안전성", f"{len(errors)}건: {errors[0]}")
        else:
            # 모든 값이 정상적으로 설정되었는지 확인
            for tid in range(5):
                for i in range(50):
                    val = loader.get(f"thread.{tid}.key{i}")
                    if val != i:
                        result.fail("동시 쓰기 스레드 안전성", f"thread.{tid}.key{i} = {val}")
                        return

            result.ok("동시 쓰기 스레드 안전성")
    except Exception as e:
        result.fail("동시 쓰기 스레드 안전성", str(e))


# =============================================================================
# [16] 엣지 케이스 테스트
# =============================================================================
def test_empty_yaml(result: TestResult) -> None:
    """빈 YAML 파일 로드 테스트."""
    try:
        # 임시 빈 YAML 파일 생성
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            tmp_path = f.name

        loader = reset_loader()
        data = loader.load(tmp_path)
        assert data == {}, f"빈 YAML 반환값 오류: {data}"

        result.ok("빈 YAML 파일 로드")
    except AssertionError as e:
        result.fail("빈 YAML 파일 로드", str(e))
    finally:
        os.unlink(tmp_path)


def test_load_returns_deepcopy(result: TestResult) -> None:
    """load 반환값이 딥카피인지 테스트."""
    try:
        loader = reset_loader()
        data = loader.load(FIXTURES_DIR / "test_base.yaml")

        # 반환된 데이터 수정
        data["app"]["name"] = "MODIFIED"

        # 내부 데이터는 영향 없어야 함
        assert loader.get("app.name") == "COURTVIEW Desktop", "load 반환값이 딥카피 아님"

        result.ok("load 반환값 딥카피 확인")
    except AssertionError as e:
        result.fail("load 반환값 딥카피 확인", str(e))


def test_set_overwrites_loaded_value(result: TestResult) -> None:
    """set이 로드된 값을 덮어쓰는지 테스트."""
    try:
        loader = reset_loader()
        loader.load(FIXTURES_DIR / "test_base.yaml")

        loader.set("app.name", "OVERWRITTEN")
        assert loader.get("app.name") == "OVERWRITTEN", "set 덮어쓰기 실패"

        result.ok("set 로드된 값 덮어쓰기")
    except AssertionError as e:
        result.fail("set 로드된 값 덮어쓰기", str(e))


def test_format_detection(result: TestResult) -> None:
    """포맷 자동 감지 테스트 (.yaml, .yml, .json)."""
    try:
        loader = reset_loader()

        # .yaml 감지
        fmt = loader._detect_format(Path("test.yaml"), ConfigFormat.AUTO)
        assert fmt == ConfigFormat.YAML, f".yaml 감지 실패: {fmt}"

        # .yml 감지
        fmt = loader._detect_format(Path("test.yml"), ConfigFormat.AUTO)
        assert fmt == ConfigFormat.YAML, f".yml 감지 실패: {fmt}"

        # .json 감지
        fmt = loader._detect_format(Path("test.json"), ConfigFormat.AUTO)
        assert fmt == ConfigFormat.JSON, f".json 감지 실패: {fmt}"

        # 알 수 없는 확장자 → YAML 기본값
        fmt = loader._detect_format(Path("test.toml"), ConfigFormat.AUTO)
        assert fmt == ConfigFormat.YAML, f"알 수 없는 확장자 기본값 실패: {fmt}"

        # 명시적 포맷은 그대로 반환
        fmt = loader._detect_format(Path("test.yaml"), ConfigFormat.JSON)
        assert fmt == ConfigFormat.JSON, f"명시적 포맷 무시됨: {fmt}"

        result.ok("포맷 자동 감지")
    except AssertionError as e:
        result.fail("포맷 자동 감지", str(e))


def test_parse_bool_various(result: TestResult) -> None:
    """_parse_bool 다양한 입력 테스트."""
    try:
        loader = reset_loader()

        # bool 타입
        assert loader._parse_bool(True) is True, "True 실패"
        assert loader._parse_bool(False) is False, "False 실패"

        # 문자열
        assert loader._parse_bool("true") is True, "'true' 실패"
        assert loader._parse_bool("yes") is True, "'yes' 실패"
        assert loader._parse_bool("1") is True, "'1' 실패"
        assert loader._parse_bool("on") is True, "'on' 실패"
        assert loader._parse_bool("false") is False, "'false' 실패"
        assert loader._parse_bool("no") is False, "'no' 실패"
        assert loader._parse_bool("random") is False, "'random' 실패"

        # 숫자
        assert loader._parse_bool(1) is True, "1 실패"
        assert loader._parse_bool(0) is False, "0 실패"
        assert loader._parse_bool(0.0) is False, "0.0 실패"

        result.ok("_parse_bool 다양한 입력")
    except AssertionError as e:
        result.fail("_parse_bool 다양한 입력", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main():
    """모든 ConfigLoader 단위 테스트 실행."""
    print("=" * 60)
    print("ConfigLoader 단위 테스트")
    print(f"픽스처 경로: {FIXTURES_DIR}")
    print("=" * 60)

    result = TestResult()

    print("\n[1] Enum 테스트")
    test_config_format_enum(result)
    test_config_source_enum(result)

    print("\n[2] 데이터 클래스 테스트")
    test_config_entry_creation(result)
    test_config_entry_with_original_value(result)
    test_config_metadata_creation(result)
    test_config_metadata_add_loaded_file(result)
    test_config_metadata_add_env_override(result)
    test_config_metadata_to_dict(result)

    print("\n[3] 상수 테스트")
    test_constants(result)

    print("\n[4] 싱글톤 패턴 테스트")
    test_singleton_same_instance(result)
    test_singleton_reset(result)
    test_singleton_initial_state(result)

    print("\n[5] YAML/JSON 파일 로드 테스트")
    test_load_yaml_file(result)
    test_load_json_file(result)
    test_load_yaml_explicit_format(result)
    test_load_json_explicit_format(result)
    test_load_nonexistent_required(result)
    test_load_nonexistent_optional(result)
    test_load_invalid_yaml(result)
    test_load_metadata_update(result)

    print("\n[6] 다중 파일 로드 / 딥 머지 테스트")
    test_load_multiple(result)
    test_deep_merge_nested(result)
    test_load_overwrite_mode(result)

    print("\n[7] 프로파일 기반 로드 테스트")
    test_load_with_profile(result)
    test_load_with_profile_metadata(result)

    print("\n[8] 값 조회 테스트 (get / dot notation)")
    test_get_simple(result)
    test_get_dot_notation(result)
    test_get_deep_nesting(result)
    test_get_default_value(result)
    test_get_with_type_conversion(result)

    print("\n[9] 타입별 get 메서드 테스트")
    test_get_int(result)
    test_get_float(result)
    test_get_bool(result)
    test_get_str(result)
    test_get_list(result)
    test_get_dict(result)
    test_get_section(result)
    test_get_required_existing(result)
    test_get_required_missing(result)

    print("\n[10] 값 설정 테스트")
    test_set_simple(result)
    test_set_nested(result)
    test_set_updates_entry(result)
    test_set_multiple(result)

    print("\n[11] 유틸리티 메서드 테스트")
    test_has(result)
    test_keys(result)
    test_items(result)
    test_to_dict(result)
    test_clear(result)
    test_profile_property(result)

    print("\n[12] 환경변수 오버라이드 테스트")
    test_env_override(result)
    test_env_bool_parsing(result)
    test_env_numeric_parsing(result)
    test_env_json_parsing(result)

    print("\n[13] 헬퍼 함수 테스트")
    test_load_config_helper(result)
    test_get_config_value_helper(result)

    print("\n[14] get_entry 메타정보 테스트")
    test_get_entry(result)

    print("\n[15] 스레드 안전성 테스트")
    test_thread_safety(result)
    test_thread_safety_write(result)

    print("\n[16] 엣지 케이스 테스트")
    test_empty_yaml(result)
    test_load_returns_deepcopy(result)
    test_set_overwrites_loaded_value(result)
    test_format_detection(result)
    test_parse_bool_various(result)

    result.summary()
    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
