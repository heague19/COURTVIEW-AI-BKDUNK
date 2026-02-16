# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/config/unit
파일: test_validator.py
설명: SchemaValidator 및 Pydantic 스키마 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-11

테스트 범위:
    - [1] ValidationStatus Enum
    - [2] ValidationErrorDetail 데이터 클래스
    - [3] ValidationResult 데이터 클래스
    - [4] BaseConfigModel 기본 설정
    - [5] LocalDatabaseConfig 스키마
    - [6] GPUConfig 스키마
    - [7] CameraConfig 스키마
    - [8] ModelConfig 스키마
    - [9] AnalysisConfig 스키마
    - [10] LocalStorageConfig 스키마
    - [11] LoggingConfig 스키마
    - [12] AppConfig 통합 스키마
    - [13] SchemaValidator 클래스
    - [14] 헬퍼 함수 (validate_config, get_default_config)
    - [15] 엣지 케이스 및 예외 처리
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.config.validator import (
    # Enum
    ValidationStatus,
    # 데이터 클래스
    ValidationErrorDetail,
    ValidationResult,
    # 기본 모델
    BaseConfigModel,
    # Desktop 전용 스키마
    LocalDatabaseConfig,
    GPUConfig,
    CameraConfig,
    LocalStorageConfig,
    # 공통 스키마
    ModelConfig,
    AnalysisConfig,
    LoggingConfig,
    # 통합 설정
    AppConfig,
    # 검증 클래스
    SchemaValidator,
    # 함수
    validate_config,
    get_default_config,
)
from shared.exceptions.validation_exceptions import SchemaValidationException


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
# [1] ValidationStatus Enum 테스트
# =============================================================================
def test_validation_status_enum(result: TestResult) -> None:
    """ValidationStatus Enum 테스트."""
    print("\n[1] ValidationStatus Enum 테스트")

    # 1-1. 멤버 존재 확인
    try:
        members = {"SUCCESS", "FAILED", "PARTIAL", "SKIPPED"}
        actual = {m.name for m in ValidationStatus}
        assert actual == members, f"멤버: {actual} != {members}"
        result.ok("멤버 존재 확인 (SUCCESS, FAILED, PARTIAL, SKIPPED)")
    except Exception as e:
        result.fail("멤버 존재 확인", str(e))

    # 1-2. 값 확인
    try:
        assert ValidationStatus.SUCCESS.value == "success"
        assert ValidationStatus.FAILED.value == "failed"
        assert ValidationStatus.PARTIAL.value == "partial"
        assert ValidationStatus.SKIPPED.value == "skipped"
        result.ok("값 확인 (success, failed, partial, skipped)")
    except Exception as e:
        result.fail("값 확인", str(e))

    # 1-3. 문자열로부터 생성
    try:
        assert ValidationStatus("success") == ValidationStatus.SUCCESS
        assert ValidationStatus("failed") == ValidationStatus.FAILED
        result.ok("문자열로부터 생성")
    except Exception as e:
        result.fail("문자열로부터 생성", str(e))

    # 1-4. 잘못된 값
    try:
        raised = False
        try:
            ValidationStatus("invalid")
        except ValueError:
            raised = True
        assert raised, "ValueError 발생해야 함"
        result.ok("잘못된 값 → ValueError")
    except Exception as e:
        result.fail("잘못된 값 → ValueError", str(e))


# =============================================================================
# [2] ValidationErrorDetail 데이터 클래스 테스트
# =============================================================================
def test_validation_error_detail(result: TestResult) -> None:
    """ValidationErrorDetail 데이터 클래스 테스트."""
    print("\n[2] ValidationErrorDetail 테스트")

    # 2-1. 기본 생성
    try:
        err = ValidationErrorDetail(
            field="gpu.device_id",
            message="범위 초과",
            error_type="value_error",
        )
        assert err.field == "gpu.device_id"
        assert err.message == "범위 초과"
        assert err.error_type == "value_error"
        assert err.input_value is None  # 기본값
        result.ok("기본 생성 (input_value=None)")
    except Exception as e:
        result.fail("기본 생성", str(e))

    # 2-2. input_value 포함 생성
    try:
        err = ValidationErrorDetail(
            field="camera.fps",
            message="범위 초과",
            error_type="value_error",
            input_value=999,
        )
        assert err.input_value == 999
        result.ok("input_value 포함 생성")
    except Exception as e:
        result.fail("input_value 포함 생성", str(e))

    # 2-3. to_dict()
    try:
        err = ValidationErrorDetail(
            field="model.precision",
            message="유효하지 않음",
            error_type="value_error",
            input_value="fp128",
        )
        d = err.to_dict()
        assert d["field"] == "model.precision"
        assert d["message"] == "유효하지 않음"
        assert d["error_type"] == "value_error"
        assert d["input_value"] == "fp128"
        assert len(d) == 4
        result.ok("to_dict() 정확한 키/값")
    except Exception as e:
        result.fail("to_dict()", str(e))


# =============================================================================
# [3] ValidationResult 데이터 클래스 테스트
# =============================================================================
def test_validation_result(result: TestResult) -> None:
    """ValidationResult 데이터 클래스 테스트."""
    print("\n[3] ValidationResult 테스트")

    # 3-1. 성공 결과
    try:
        vr = ValidationResult(
            status=ValidationStatus.SUCCESS,
            data={"key": "value"},
            schema_name="TestSchema",
        )
        assert vr.is_valid is True
        assert vr.error_count == 0
        assert vr.data == {"key": "value"}
        assert vr.schema_name == "TestSchema"
        result.ok("성공 결과 (is_valid=True, error_count=0)")
    except Exception as e:
        result.fail("성공 결과", str(e))

    # 3-2. 실패 결과
    try:
        errors = [
            ValidationErrorDetail("field1", "오류1", "type1"),
            ValidationErrorDetail("field2", "오류2", "type2"),
        ]
        vr = ValidationResult(
            status=ValidationStatus.FAILED,
            errors=errors,
            schema_name="FailSchema",
        )
        assert vr.is_valid is False
        assert vr.error_count == 2
        assert vr.data is None
        result.ok("실패 결과 (is_valid=False, error_count=2)")
    except Exception as e:
        result.fail("실패 결과", str(e))

    # 3-3. validated_at 자동 생성
    try:
        vr = ValidationResult(status=ValidationStatus.SUCCESS)
        assert isinstance(vr.validated_at, datetime)
        assert vr.validated_at.tzinfo is not None  # UTC 타임존
        result.ok("validated_at 자동 생성 (UTC)")
    except Exception as e:
        result.fail("validated_at 자동 생성", str(e))

    # 3-4. to_dict()
    try:
        errors = [ValidationErrorDetail("f1", "msg1", "t1", "val1")]
        vr = ValidationResult(
            status=ValidationStatus.FAILED,
            errors=errors,
            schema_name="DictSchema",
        )
        d = vr.to_dict()
        assert d["status"] == "failed"
        assert d["is_valid"] is False
        assert d["error_count"] == 1
        assert len(d["errors"]) == 1
        assert d["errors"][0]["field"] == "f1"
        assert d["schema_name"] == "DictSchema"
        assert "validated_at" in d
        result.ok("to_dict() 구조 검증")
    except Exception as e:
        result.fail("to_dict()", str(e))

    # 3-5. PARTIAL 상태
    try:
        vr = ValidationResult(status=ValidationStatus.PARTIAL)
        assert vr.is_valid is False  # SUCCESS만 is_valid=True
        result.ok("PARTIAL 상태 → is_valid=False")
    except Exception as e:
        result.fail("PARTIAL 상태", str(e))

    # 3-6. SKIPPED 상태
    try:
        vr = ValidationResult(status=ValidationStatus.SKIPPED)
        assert vr.is_valid is False
        result.ok("SKIPPED 상태 → is_valid=False")
    except Exception as e:
        result.fail("SKIPPED 상태", str(e))


# =============================================================================
# [4] BaseConfigModel 기본 설정 테스트
# =============================================================================
def test_base_config_model(result: TestResult) -> None:
    """BaseConfigModel 기본 설정 테스트."""
    print("\n[4] BaseConfigModel 테스트")

    # 4-1. extra="ignore" - 알 수 없는 필드 무시
    try:
        # GPUConfig 을 사용해서 extra 필드 무시 확인
        config = GPUConfig(device_id=0, unknown_field="ignored")
        assert not hasattr(config, "unknown_field")
        result.ok("extra='ignore' - 알 수 없는 필드 무시")
    except Exception as e:
        result.fail("extra='ignore'", str(e))

    # 4-2. str_strip_whitespace=True
    try:
        config = LocalDatabaseConfig(db_path="  data/test.db  ")
        assert config.db_path == "data/test.db"
        result.ok("str_strip_whitespace=True - 공백 제거")
    except Exception as e:
        result.fail("str_strip_whitespace", str(e))

    # 4-3. frozen=False - 변경 가능
    try:
        config = GPUConfig()
        config.device_id = 1
        assert config.device_id == 1
        result.ok("frozen=False - 값 변경 가능")
    except Exception as e:
        result.fail("frozen=False", str(e))

    # 4-4. validate_default=True - 기본값도 검증
    try:
        config = GPUConfig()
        # 기본값 fp16이 검증되어 소문자로 반환
        assert config.precision == "fp16"
        result.ok("validate_default=True - 기본값 검증")
    except Exception as e:
        result.fail("validate_default", str(e))


# =============================================================================
# [5] LocalDatabaseConfig 스키마 테스트
# =============================================================================
def test_local_database_config(result: TestResult) -> None:
    """LocalDatabaseConfig 스키마 테스트."""
    print("\n[5] LocalDatabaseConfig 테스트")

    # 5-1. 기본값 확인
    try:
        config = LocalDatabaseConfig()
        assert config.db_path == "data/courtview.db"
        assert config.journal_mode == "WAL"
        assert config.cache_size == -64000
        assert config.busy_timeout == 5000
        assert config.foreign_keys is True
        assert config.synchronous == "NORMAL"
        assert config.temp_store == "MEMORY"
        assert config.mmap_size == 268435456  # 256MB
        assert config.max_page_count == 0
        assert config.auto_vacuum == "INCREMENTAL"
        result.ok("기본값 10개 필드 확인")
    except Exception as e:
        result.fail("기본값", str(e))

    # 5-2. journal_mode 검증 - 유효 값
    try:
        valid_modes = ["DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"]
        for mode in valid_modes:
            config = LocalDatabaseConfig(journal_mode=mode)
            assert config.journal_mode == mode.upper()
        # 소문자 입력도 대문자로 변환
        config = LocalDatabaseConfig(journal_mode="wal")
        assert config.journal_mode == "WAL"
        result.ok("journal_mode 유효 값 + 대문자 변환")
    except Exception as e:
        result.fail("journal_mode 유효 값", str(e))

    # 5-3. journal_mode 검증 - 무효 값
    try:
        raised = False
        try:
            LocalDatabaseConfig(journal_mode="INVALID")
        except Exception:
            raised = True
        assert raised, "ValidationError 발생해야 함"
        result.ok("journal_mode 무효 값 → 예외")
    except Exception as e:
        result.fail("journal_mode 무효 값", str(e))

    # 5-4. synchronous 검증
    try:
        for mode in ["OFF", "NORMAL", "FULL", "EXTRA"]:
            config = LocalDatabaseConfig(synchronous=mode)
            assert config.synchronous == mode
        # 소문자 → 대문자
        config = LocalDatabaseConfig(synchronous="full")
        assert config.synchronous == "FULL"
        result.ok("synchronous 유효 값 + 대문자 변환")
    except Exception as e:
        result.fail("synchronous 검증", str(e))

    # 5-5. synchronous 무효 값
    try:
        raised = False
        try:
            LocalDatabaseConfig(synchronous="INVALID")
        except Exception:
            raised = True
        assert raised
        result.ok("synchronous 무효 값 → 예외")
    except Exception as e:
        result.fail("synchronous 무효 값", str(e))

    # 5-6. auto_vacuum 검증
    try:
        for mode in ["NONE", "FULL", "INCREMENTAL"]:
            config = LocalDatabaseConfig(auto_vacuum=mode)
            assert config.auto_vacuum == mode
        config = LocalDatabaseConfig(auto_vacuum="incremental")
        assert config.auto_vacuum == "INCREMENTAL"
        result.ok("auto_vacuum 유효 값 + 대문자 변환")
    except Exception as e:
        result.fail("auto_vacuum 검증", str(e))

    # 5-7. auto_vacuum 무효 값
    try:
        raised = False
        try:
            LocalDatabaseConfig(auto_vacuum="INVALID")
        except Exception:
            raised = True
        assert raised
        result.ok("auto_vacuum 무효 값 → 예외")
    except Exception as e:
        result.fail("auto_vacuum 무효 값", str(e))

    # 5-8. busy_timeout 경계값
    try:
        config = LocalDatabaseConfig(busy_timeout=100)  # 최소
        assert config.busy_timeout == 100
        config = LocalDatabaseConfig(busy_timeout=60000)  # 최대
        assert config.busy_timeout == 60000
        result.ok("busy_timeout 경계값 (100, 60000)")
    except Exception as e:
        result.fail("busy_timeout 경계값", str(e))

    # 5-9. busy_timeout 범위 초과
    try:
        raised = False
        try:
            LocalDatabaseConfig(busy_timeout=99)  # 최소 미만
        except Exception:
            raised = True
        assert raised
        raised = False
        try:
            LocalDatabaseConfig(busy_timeout=60001)  # 최대 초과
        except Exception:
            raised = True
        assert raised
        result.ok("busy_timeout 범위 초과 → 예외 (99, 60001)")
    except Exception as e:
        result.fail("busy_timeout 범위 초과", str(e))

    # 5-10. connection_string 프로퍼티
    try:
        config = LocalDatabaseConfig(db_path="my/test.db")
        assert config.connection_string == "sqlite:///my/test.db"
        result.ok("connection_string 프로퍼티")
    except Exception as e:
        result.fail("connection_string", str(e))

    # 5-11. pragma_settings 프로퍼티
    try:
        config = LocalDatabaseConfig()
        pragmas = config.pragma_settings
        assert pragmas["journal_mode"] == "WAL"
        assert pragmas["cache_size"] == -64000
        assert pragmas["busy_timeout"] == 5000
        assert pragmas["foreign_keys"] == 1  # int(True) = 1
        assert pragmas["synchronous"] == "NORMAL"
        assert pragmas["temp_store"] == "MEMORY"
        assert pragmas["mmap_size"] == 268435456
        assert pragmas["auto_vacuum"] == "INCREMENTAL"
        assert len(pragmas) == 8
        result.ok("pragma_settings 프로퍼티 (8개 키)")
    except Exception as e:
        result.fail("pragma_settings", str(e))

    # 5-12. db_path 빈 문자열
    try:
        raised = False
        try:
            LocalDatabaseConfig(db_path="")
        except Exception:
            raised = True
        assert raised, "빈 문자열은 min_length=1 위반"
        result.ok("db_path 빈 문자열 → 예외")
    except Exception as e:
        result.fail("db_path 빈 문자열", str(e))


# =============================================================================
# [6] GPUConfig 스키마 테스트
# =============================================================================
def test_gpu_config(result: TestResult) -> None:
    """GPUConfig 스키마 테스트."""
    print("\n[6] GPUConfig 테스트")

    # 6-1. 기본값 확인
    try:
        config = GPUConfig()
        assert config.device_id == 0
        assert config.memory_limit_gb == 0.0
        assert config.memory_fraction == 0.9
        assert config.tensorrt_enabled is True
        assert config.tensorrt_cache_dir == "cache/tensorrt"
        assert config.tensorrt_workspace_gb == 4.0
        assert config.precision == "fp16"
        assert config.allow_growth is True
        assert config.benchmark_mode is True
        assert config.deterministic is False
        assert config.fallback_to_cpu is True
        result.ok("기본값 11개 필드 확인")
    except Exception as e:
        result.fail("기본값", str(e))

    # 6-2. precision 검증 - 유효 값
    try:
        for p in ["fp32", "fp16", "int8", "bf16"]:
            config = GPUConfig(precision=p)
            assert config.precision == p
        # 대문자 입력 → 소문자
        config = GPUConfig(precision="FP16")
        assert config.precision == "fp16"
        result.ok("precision 유효 값 + 소문자 변환")
    except Exception as e:
        result.fail("precision 유효 값", str(e))

    # 6-3. precision 무효 값
    try:
        raised = False
        try:
            GPUConfig(precision="fp128")
        except Exception:
            raised = True
        assert raised
        result.ok("precision 무효 값 → 예외")
    except Exception as e:
        result.fail("precision 무효 값", str(e))

    # 6-4. device_id 경계값
    try:
        config = GPUConfig(device_id=0)
        assert config.device_id == 0
        config = GPUConfig(device_id=7)
        assert config.device_id == 7
        result.ok("device_id 경계값 (0, 7)")
    except Exception as e:
        result.fail("device_id 경계값", str(e))

    # 6-5. device_id 범위 초과
    try:
        raised = False
        try:
            GPUConfig(device_id=-1)
        except Exception:
            raised = True
        assert raised
        raised = False
        try:
            GPUConfig(device_id=8)
        except Exception:
            raised = True
        assert raised
        result.ok("device_id 범위 초과 → 예외 (-1, 8)")
    except Exception as e:
        result.fail("device_id 범위 초과", str(e))

    # 6-6. memory_fraction 경계값
    try:
        config = GPUConfig(memory_fraction=0.1)
        assert config.memory_fraction == 0.1
        config = GPUConfig(memory_fraction=1.0)
        assert config.memory_fraction == 1.0
        result.ok("memory_fraction 경계값 (0.1, 1.0)")
    except Exception as e:
        result.fail("memory_fraction 경계값", str(e))

    # 6-7. memory_fraction 범위 초과
    try:
        raised = False
        try:
            GPUConfig(memory_fraction=0.09)
        except Exception:
            raised = True
        assert raised
        raised = False
        try:
            GPUConfig(memory_fraction=1.01)
        except Exception:
            raised = True
        assert raised
        result.ok("memory_fraction 범위 초과 → 예외")
    except Exception as e:
        result.fail("memory_fraction 범위 초과", str(e))

    # 6-8. tensorrt_workspace_gb 경계값
    try:
        config = GPUConfig(tensorrt_workspace_gb=0.5)
        assert config.tensorrt_workspace_gb == 0.5
        config = GPUConfig(tensorrt_workspace_gb=16.0)
        assert config.tensorrt_workspace_gb == 16.0
        result.ok("tensorrt_workspace_gb 경계값 (0.5, 16.0)")
    except Exception as e:
        result.fail("tensorrt_workspace_gb 경계값", str(e))

    # 6-9. cuda_device 프로퍼티
    try:
        config = GPUConfig(device_id=0)
        assert config.cuda_device == "cuda:0"
        config = GPUConfig(device_id=3)
        assert config.cuda_device == "cuda:3"
        result.ok("cuda_device 프로퍼티")
    except Exception as e:
        result.fail("cuda_device", str(e))

    # 6-10. memory_limit_gb 경계값
    try:
        config = GPUConfig(memory_limit_gb=0.0)
        assert config.memory_limit_gb == 0.0
        config = GPUConfig(memory_limit_gb=48.0)
        assert config.memory_limit_gb == 48.0
        result.ok("memory_limit_gb 경계값 (0.0, 48.0)")
    except Exception as e:
        result.fail("memory_limit_gb 경계값", str(e))

    # 6-11. memory_limit_gb 범위 초과
    try:
        raised = False
        try:
            GPUConfig(memory_limit_gb=48.1)
        except Exception:
            raised = True
        assert raised
        result.ok("memory_limit_gb 범위 초과 → 예외 (48.1)")
    except Exception as e:
        result.fail("memory_limit_gb 범위 초과", str(e))


# =============================================================================
# [7] CameraConfig 스키마 테스트
# =============================================================================
def test_camera_config(result: TestResult) -> None:
    """CameraConfig 스키마 테스트."""
    print("\n[7] CameraConfig 테스트")

    # 7-1. 기본값 확인
    try:
        config = CameraConfig()
        assert config.count == 4
        assert config.resolution_width == 1920
        assert config.resolution_height == 1080
        assert config.fps == 30
        assert config.sync_mode == "genlock"
        assert config.buffer_size == 30
        assert config.auto_exposure is True
        assert config.codec == "h264"
        assert config.pixel_format == "bgr24"
        assert config.calibration_dir == "data/calibration"
        result.ok("기본값 10개 필드 확인")
    except Exception as e:
        result.fail("기본값", str(e))

    # 7-2. sync_mode 검증 - 유효 값
    try:
        for mode in ["genlock", "software", "none"]:
            config = CameraConfig(sync_mode=mode)
            assert config.sync_mode == mode
        # 대문자 → 소문자
        config = CameraConfig(sync_mode="GENLOCK")
        assert config.sync_mode == "genlock"
        result.ok("sync_mode 유효 값 + 소문자 변환")
    except Exception as e:
        result.fail("sync_mode", str(e))

    # 7-3. sync_mode 무효 값
    try:
        raised = False
        try:
            CameraConfig(sync_mode="invalid")
        except Exception:
            raised = True
        assert raised
        result.ok("sync_mode 무효 값 → 예외")
    except Exception as e:
        result.fail("sync_mode 무효 값", str(e))

    # 7-4. codec 검증 - 유효 값
    try:
        for c in ["h264", "h265", "hevc", "mjpeg", "raw"]:
            config = CameraConfig(codec=c)
            assert config.codec == c
        config = CameraConfig(codec="H264")
        assert config.codec == "h264"
        result.ok("codec 유효 값 + 소문자 변환")
    except Exception as e:
        result.fail("codec", str(e))

    # 7-5. codec 무효 값
    try:
        raised = False
        try:
            CameraConfig(codec="vp9")
        except Exception:
            raised = True
        assert raised
        result.ok("codec 무효 값 → 예외 (vp9)")
    except Exception as e:
        result.fail("codec 무효 값", str(e))

    # 7-6. pixel_format 검증 - 유효 값
    try:
        for fmt in ["bgr24", "rgb24", "yuv420p", "nv12", "gray"]:
            config = CameraConfig(pixel_format=fmt)
            assert config.pixel_format == fmt
        config = CameraConfig(pixel_format="BGR24")
        assert config.pixel_format == "bgr24"
        result.ok("pixel_format 유효 값 + 소문자 변환")
    except Exception as e:
        result.fail("pixel_format", str(e))

    # 7-7. pixel_format 무효 값
    try:
        raised = False
        try:
            CameraConfig(pixel_format="rgba32")
        except Exception:
            raised = True
        assert raised
        result.ok("pixel_format 무효 값 → 예외 (rgba32)")
    except Exception as e:
        result.fail("pixel_format 무효 값", str(e))

    # 7-8. count 경계값
    try:
        config = CameraConfig(count=1)
        assert config.count == 1
        config = CameraConfig(count=8)
        assert config.count == 8
        result.ok("count 경계값 (1, 8)")
    except Exception as e:
        result.fail("count 경계값", str(e))

    # 7-9. count 범위 초과
    try:
        raised = False
        try:
            CameraConfig(count=0)
        except Exception:
            raised = True
        assert raised
        raised = False
        try:
            CameraConfig(count=9)
        except Exception:
            raised = True
        assert raised
        result.ok("count 범위 초과 → 예외 (0, 9)")
    except Exception as e:
        result.fail("count 범위 초과", str(e))

    # 7-10. resolution 경계값 (width)
    try:
        config = CameraConfig(resolution_width=640)
        assert config.resolution_width == 640
        config = CameraConfig(resolution_width=7680)
        assert config.resolution_width == 7680
        result.ok("resolution_width 경계값 (640, 7680)")
    except Exception as e:
        result.fail("resolution_width 경계값", str(e))

    # 7-11. resolution_height 경계값
    try:
        config = CameraConfig(resolution_height=480)
        assert config.resolution_height == 480
        config = CameraConfig(resolution_height=4320)
        assert config.resolution_height == 4320
        result.ok("resolution_height 경계값 (480, 4320)")
    except Exception as e:
        result.fail("resolution_height 경계값", str(e))

    # 7-12. fps 경계값
    try:
        config = CameraConfig(fps=15)
        assert config.fps == 15
        config = CameraConfig(fps=120)
        assert config.fps == 120
        result.ok("fps 경계값 (15, 120)")
    except Exception as e:
        result.fail("fps 경계값", str(e))

    # 7-13. fps 범위 초과
    try:
        raised = False
        try:
            CameraConfig(fps=14)
        except Exception:
            raised = True
        assert raised
        raised = False
        try:
            CameraConfig(fps=121)
        except Exception:
            raised = True
        assert raised
        result.ok("fps 범위 초과 → 예외 (14, 121)")
    except Exception as e:
        result.fail("fps 범위 초과", str(e))

    # 7-14. buffer_size 경계값
    try:
        config = CameraConfig(buffer_size=5)
        assert config.buffer_size == 5
        config = CameraConfig(buffer_size=300)
        assert config.buffer_size == 300
        result.ok("buffer_size 경계값 (5, 300)")
    except Exception as e:
        result.fail("buffer_size 경계값", str(e))

    # 7-15. resolution 프로퍼티
    try:
        config = CameraConfig(resolution_width=3840, resolution_height=2160)
        assert config.resolution == (3840, 2160)
        result.ok("resolution 프로퍼티 → (3840, 2160)")
    except Exception as e:
        result.fail("resolution 프로퍼티", str(e))

    # 7-16. total_pixels_per_second 프로퍼티
    try:
        config = CameraConfig(
            count=4, resolution_width=1920,
            resolution_height=1080, fps=30,
        )
        # 1920 * 1080 * 30 * 4 = 248,832,000
        expected = 1920 * 1080 * 30 * 4
        assert config.total_pixels_per_second == expected
        result.ok(f"total_pixels_per_second = {expected}")
    except Exception as e:
        result.fail("total_pixels_per_second", str(e))


# =============================================================================
# [8] ModelConfig 스키마 테스트
# =============================================================================
def test_model_config(result: TestResult) -> None:
    """ModelConfig 스키마 테스트."""
    print("\n[8] ModelConfig 테스트")

    # 8-1. 기본값 확인
    try:
        config = ModelConfig()
        assert config.model_path == "models"
        assert config.model_type == "yolo"
        assert config.device == "cuda"
        assert config.precision == "fp16"
        assert config.batch_size == 1
        assert config.confidence_threshold == 0.5
        assert config.nms_threshold == 0.45
        assert config.max_detections == 100
        assert config.warmup_iterations == 3
        assert config.cache_enabled is True
        result.ok("기본값 10개 필드 확인")
    except Exception as e:
        result.fail("기본값", str(e))

    # 8-2. model_type 검증 - 유효 값
    try:
        valid_types = ["yolo", "mediapipe", "onnx", "tensorrt", "pytorch", "tflite"]
        for mt in valid_types:
            config = ModelConfig(model_type=mt)
            assert config.model_type == mt
        # 대소문자
        config = ModelConfig(model_type="YOLO")
        assert config.model_type == "yolo"
        result.ok("model_type 유효 값 6종 + 소문자 변환")
    except Exception as e:
        result.fail("model_type", str(e))

    # 8-3. model_type 무효 값
    try:
        raised = False
        try:
            ModelConfig(model_type="caffe")
        except Exception:
            raised = True
        assert raised
        result.ok("model_type 무효 값 → 예외 (caffe)")
    except Exception as e:
        result.fail("model_type 무효 값", str(e))

    # 8-4. device 검증 - 유효 패턴
    try:
        for dev in ["cpu", "cuda", "cuda:0", "cuda:7", "mps"]:
            config = ModelConfig(device=dev)
            assert config.device == dev
        result.ok("device 유효 패턴 (cpu, cuda, cuda:N, mps)")
    except Exception as e:
        result.fail("device 유효 패턴", str(e))

    # 8-5. device 무효 패턴
    try:
        invalid_devices = ["gpu", "tpu", "cuda:", "cuda:abc", "vulkan"]
        for dev in invalid_devices:
            raised = False
            try:
                ModelConfig(device=dev)
            except Exception:
                raised = True
            assert raised, f"'{dev}' 무효지만 예외 없음"
        result.ok("device 무효 패턴 → 예외 (5종)")
    except Exception as e:
        result.fail("device 무효 패턴", str(e))

    # 8-6. precision 검증
    try:
        for p in ["fp32", "fp16", "int8", "bf16"]:
            config = ModelConfig(precision=p)
            assert config.precision == p
        result.ok("precision 유효 값 4종")
    except Exception as e:
        result.fail("precision", str(e))

    # 8-7. batch_size 경계값
    try:
        config = ModelConfig(batch_size=1)
        assert config.batch_size == 1
        config = ModelConfig(batch_size=64)
        assert config.batch_size == 64
        result.ok("batch_size 경계값 (1, 64)")
    except Exception as e:
        result.fail("batch_size 경계값", str(e))

    # 8-8. batch_size 범위 초과
    try:
        raised = False
        try:
            ModelConfig(batch_size=0)
        except Exception:
            raised = True
        assert raised
        raised = False
        try:
            ModelConfig(batch_size=65)
        except Exception:
            raised = True
        assert raised
        result.ok("batch_size 범위 초과 → 예외 (0, 65)")
    except Exception as e:
        result.fail("batch_size 범위 초과", str(e))

    # 8-9. confidence_threshold 경계값
    try:
        config = ModelConfig(confidence_threshold=0.0)
        assert config.confidence_threshold == 0.0
        config = ModelConfig(confidence_threshold=1.0)
        assert config.confidence_threshold == 1.0
        result.ok("confidence_threshold 경계값 (0.0, 1.0)")
    except Exception as e:
        result.fail("confidence_threshold 경계값", str(e))

    # 8-10. max_detections 경계값
    try:
        config = ModelConfig(max_detections=1)
        assert config.max_detections == 1
        config = ModelConfig(max_detections=1000)
        assert config.max_detections == 1000
        result.ok("max_detections 경계값 (1, 1000)")
    except Exception as e:
        result.fail("max_detections 경계값", str(e))

    # 8-11. model_path 빈 문자열
    try:
        raised = False
        try:
            ModelConfig(model_path="")
        except Exception:
            raised = True
        assert raised, "빈 문자열은 min_length=1 위반"
        result.ok("model_path 빈 문자열 → 예외")
    except Exception as e:
        result.fail("model_path 빈 문자열", str(e))


# =============================================================================
# [9] AnalysisConfig 스키마 테스트
# =============================================================================
def test_analysis_config(result: TestResult) -> None:
    """AnalysisConfig 스키마 테스트."""
    print("\n[9] AnalysisConfig 테스트")

    # 9-1. 기본값 확인
    try:
        config = AnalysisConfig()
        assert config.target_fps == 30
        assert config.max_video_duration == 7200
        assert config.min_video_duration == 1
        assert config.max_video_size_mb == 4096
        assert config.supported_formats == ["mp4", "avi", "mov", "mkv", "webm"]
        assert config.keypoint_confidence_threshold == 0.5
        assert config.motion_smoothing_window == 5
        assert config.enable_tracking is True
        assert config.enable_pose_estimation is True
        assert config.enable_ball_detection is True
        assert config.enable_court_detection is True
        assert config.parallel_workers == 4
        result.ok("기본값 12개 필드 확인")
    except Exception as e:
        result.fail("기본값", str(e))

    # 9-2. duration 범위 검증 (model_validator) - 정상
    try:
        config = AnalysisConfig(min_video_duration=5, max_video_duration=3600)
        assert config.min_video_duration == 5
        assert config.max_video_duration == 3600
        result.ok("duration 범위 정상 (min < max)")
    except Exception as e:
        result.fail("duration 범위 정상", str(e))

    # 9-3. duration 범위 검증 - min > max → 예외
    try:
        raised = False
        try:
            AnalysisConfig(min_video_duration=60, max_video_duration=30)
        except Exception:
            raised = True
        assert raised, "min > max 시 예외 발생해야 함"
        result.ok("duration 범위 위반 (min=60 > max=30) → 예외")
    except Exception as e:
        result.fail("duration 범위 위반", str(e))

    # 9-4. duration 같은 값 - 허용
    try:
        config = AnalysisConfig(min_video_duration=10, max_video_duration=10)
        assert config.min_video_duration == 10
        assert config.max_video_duration == 10
        result.ok("duration 같은 값 (min=max=10) 허용")
    except Exception as e:
        result.fail("duration 같은 값", str(e))

    # 9-5. supported_formats 검증 - 유효
    try:
        config = AnalysisConfig(supported_formats=["mp4", "avi", "flv", "m4v"])
        assert "mp4" in config.supported_formats
        assert "flv" in config.supported_formats
        assert "m4v" in config.supported_formats
        result.ok("supported_formats 유효 값 (mp4, avi, flv, m4v)")
    except Exception as e:
        result.fail("supported_formats 유효", str(e))

    # 9-6. supported_formats 소문자 변환 + 점(.) 제거
    try:
        config = AnalysisConfig(supported_formats=[".MP4", ".AVI"])
        assert config.supported_formats == ["mp4", "avi"]
        result.ok("supported_formats 소문자 변환 + 점 제거")
    except Exception as e:
        result.fail("supported_formats 변환", str(e))

    # 9-7. supported_formats 무효 값
    try:
        raised = False
        try:
            AnalysisConfig(supported_formats=["mp4", "gif"])
        except Exception:
            raised = True
        assert raised, "gif 는 유효하지 않은 형식"
        result.ok("supported_formats 무효 값 → 예외 (gif)")
    except Exception as e:
        result.fail("supported_formats 무효 값", str(e))

    # 9-8. target_fps 경계값
    try:
        config = AnalysisConfig(target_fps=1)
        assert config.target_fps == 1
        config = AnalysisConfig(target_fps=120)
        assert config.target_fps == 120
        result.ok("target_fps 경계값 (1, 120)")
    except Exception as e:
        result.fail("target_fps 경계값", str(e))

    # 9-9. parallel_workers 경계값
    try:
        config = AnalysisConfig(parallel_workers=1)
        assert config.parallel_workers == 1
        config = AnalysisConfig(parallel_workers=32)
        assert config.parallel_workers == 32
        result.ok("parallel_workers 경계값 (1, 32)")
    except Exception as e:
        result.fail("parallel_workers 경계값", str(e))

    # 9-10. keypoint_confidence_threshold 경계값
    try:
        config = AnalysisConfig(keypoint_confidence_threshold=0.0)
        assert config.keypoint_confidence_threshold == 0.0
        config = AnalysisConfig(keypoint_confidence_threshold=1.0)
        assert config.keypoint_confidence_threshold == 1.0
        result.ok("keypoint_confidence_threshold 경계값 (0.0, 1.0)")
    except Exception as e:
        result.fail("keypoint_confidence_threshold 경계값", str(e))

    # 9-11. motion_smoothing_window 경계값
    try:
        config = AnalysisConfig(motion_smoothing_window=1)
        assert config.motion_smoothing_window == 1
        config = AnalysisConfig(motion_smoothing_window=30)
        assert config.motion_smoothing_window == 30
        result.ok("motion_smoothing_window 경계값 (1, 30)")
    except Exception as e:
        result.fail("motion_smoothing_window 경계값", str(e))

    # 9-12. max_video_size_mb 경계값
    try:
        config = AnalysisConfig(max_video_size_mb=1)
        assert config.max_video_size_mb == 1
        config = AnalysisConfig(max_video_size_mb=20480)
        assert config.max_video_size_mb == 20480
        result.ok("max_video_size_mb 경계값 (1, 20480)")
    except Exception as e:
        result.fail("max_video_size_mb 경계값", str(e))


# =============================================================================
# [10] LocalStorageConfig 스키마 테스트
# =============================================================================
def test_local_storage_config(result: TestResult) -> None:
    """LocalStorageConfig 스키마 테스트."""
    print("\n[10] LocalStorageConfig 테스트")

    # 10-1. 기본값 확인
    try:
        config = LocalStorageConfig()
        assert config.data_dir == "data"
        assert config.video_dir == "data/videos"
        assert config.cache_dir == "cache"
        assert config.export_dir == "exports"
        assert config.temp_dir == "temp"
        assert config.max_cache_gb == 50.0
        assert config.max_storage_gb == 0.0
        assert config.auto_cleanup is True
        assert config.cleanup_threshold_percent == 90.0
        assert config.video_output_format == "mp4"
        result.ok("기본값 10개 필드 확인")
    except Exception as e:
        result.fail("기본값", str(e))

    # 10-2. video_output_format 유효 값
    try:
        for fmt in ["mp4", "avi", "mov", "mkv"]:
            config = LocalStorageConfig(video_output_format=fmt)
            assert config.video_output_format == fmt
        config = LocalStorageConfig(video_output_format="MP4")
        assert config.video_output_format == "mp4"
        result.ok("video_output_format 유효 값 + 소문자 변환")
    except Exception as e:
        result.fail("video_output_format", str(e))

    # 10-3. video_output_format 무효 값
    try:
        raised = False
        try:
            LocalStorageConfig(video_output_format="webm")
        except Exception:
            raised = True
        assert raised
        result.ok("video_output_format 무효 값 → 예외 (webm)")
    except Exception as e:
        result.fail("video_output_format 무효 값", str(e))

    # 10-4. max_cache_gb 경계값
    try:
        config = LocalStorageConfig(max_cache_gb=1.0)
        assert config.max_cache_gb == 1.0
        config = LocalStorageConfig(max_cache_gb=1000.0)
        assert config.max_cache_gb == 1000.0
        result.ok("max_cache_gb 경계값 (1.0, 1000.0)")
    except Exception as e:
        result.fail("max_cache_gb 경계값", str(e))

    # 10-5. cleanup_threshold_percent 경계값
    try:
        config = LocalStorageConfig(cleanup_threshold_percent=50.0)
        assert config.cleanup_threshold_percent == 50.0
        config = LocalStorageConfig(cleanup_threshold_percent=99.0)
        assert config.cleanup_threshold_percent == 99.0
        result.ok("cleanup_threshold_percent 경계값 (50.0, 99.0)")
    except Exception as e:
        result.fail("cleanup_threshold_percent 경계값", str(e))

    # 10-6. cleanup_threshold_percent 범위 초과
    try:
        raised = False
        try:
            LocalStorageConfig(cleanup_threshold_percent=49.9)
        except Exception:
            raised = True
        assert raised
        raised = False
        try:
            LocalStorageConfig(cleanup_threshold_percent=99.1)
        except Exception:
            raised = True
        assert raised
        result.ok("cleanup_threshold_percent 범위 초과 → 예외")
    except Exception as e:
        result.fail("cleanup_threshold_percent 범위 초과", str(e))

    # 10-7. 디렉토리 경로 빈 문자열
    try:
        raised = False
        try:
            LocalStorageConfig(data_dir="")
        except Exception:
            raised = True
        assert raised, "빈 문자열은 min_length=1 위반"
        result.ok("data_dir 빈 문자열 → 예외")
    except Exception as e:
        result.fail("data_dir 빈 문자열", str(e))


# =============================================================================
# [11] LoggingConfig 스키마 테스트
# =============================================================================
def test_logging_config(result: TestResult) -> None:
    """LoggingConfig 스키마 테스트."""
    print("\n[11] LoggingConfig 테스트")

    # 11-1. 기본값 확인
    try:
        config = LoggingConfig()
        assert config.level == "INFO"
        assert "%(asctime)s" in config.format
        assert config.output == "both"
        assert config.file_path == "logs/courtview.log"
        assert config.max_file_size_mb == 100
        assert config.backup_count == 5
        assert config.json_format is False
        result.ok("기본값 7개 필드 확인")
    except Exception as e:
        result.fail("기본값", str(e))

    # 11-2. level 유효 값
    try:
        for lvl in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = LoggingConfig(level=lvl)
            assert config.level == lvl
        # 소문자 → 대문자
        config = LoggingConfig(level="debug")
        assert config.level == "DEBUG"
        result.ok("level 유효 값 5종 + 대문자 변환")
    except Exception as e:
        result.fail("level", str(e))

    # 11-3. level 무효 값
    try:
        raised = False
        try:
            LoggingConfig(level="TRACE")
        except Exception:
            raised = True
        assert raised
        result.ok("level 무효 값 → 예외 (TRACE)")
    except Exception as e:
        result.fail("level 무효 값", str(e))

    # 11-4. output 유효 값
    try:
        for out in ["console", "file", "both"]:
            config = LoggingConfig(output=out)
            assert config.output == out
        config = LoggingConfig(output="CONSOLE")
        assert config.output == "console"
        result.ok("output 유효 값 + 소문자 변환")
    except Exception as e:
        result.fail("output", str(e))

    # 11-5. output 무효 값
    try:
        raised = False
        try:
            LoggingConfig(output="syslog")
        except Exception:
            raised = True
        assert raised
        result.ok("output 무효 값 → 예외 (syslog)")
    except Exception as e:
        result.fail("output 무효 값", str(e))

    # 11-6. max_file_size_mb 경계값
    try:
        config = LoggingConfig(max_file_size_mb=1)
        assert config.max_file_size_mb == 1
        config = LoggingConfig(max_file_size_mb=1024)
        assert config.max_file_size_mb == 1024
        result.ok("max_file_size_mb 경계값 (1, 1024)")
    except Exception as e:
        result.fail("max_file_size_mb 경계값", str(e))

    # 11-7. backup_count 경계값
    try:
        config = LoggingConfig(backup_count=0)
        assert config.backup_count == 0
        config = LoggingConfig(backup_count=100)
        assert config.backup_count == 100
        result.ok("backup_count 경계값 (0, 100)")
    except Exception as e:
        result.fail("backup_count 경계값", str(e))


# =============================================================================
# [12] AppConfig 통합 스키마 테스트
# =============================================================================
def test_app_config(result: TestResult) -> None:
    """AppConfig 통합 스키마 테스트."""
    print("\n[12] AppConfig 테스트")

    # 12-1. 기본값 확인
    try:
        config = AppConfig()
        assert config.app_name == "COURTVIEW Desktop"
        assert config.version == "1.0.0"
        assert config.environment == "production"
        assert isinstance(config.gpu, GPUConfig)
        assert isinstance(config.camera, CameraConfig)
        assert isinstance(config.storage, LocalStorageConfig)
        assert isinstance(config.database, LocalDatabaseConfig)
        assert isinstance(config.model, ModelConfig)
        assert isinstance(config.analysis, AnalysisConfig)
        assert isinstance(config.logging, LoggingConfig)
        result.ok("기본값 (3개 스칼라 + 7개 서브 설정)")
    except Exception as e:
        result.fail("기본값", str(e))

    # 12-2. environment 유효 값
    try:
        for env in ["development", "production", "testing"]:
            config = AppConfig(environment=env)
            assert config.environment == env
        config = AppConfig(environment="PRODUCTION")
        assert config.environment == "production"
        result.ok("environment 유효 값 + 소문자 변환")
    except Exception as e:
        result.fail("environment", str(e))

    # 12-3. environment 무효 값
    try:
        raised = False
        try:
            AppConfig(environment="staging")
        except Exception:
            raised = True
        assert raised
        result.ok("environment 무효 값 → 예외 (staging)")
    except Exception as e:
        result.fail("environment 무효 값", str(e))

    # 12-4. 중첩 딕셔너리로 생성
    try:
        data = {
            "app_name": "TestApp",
            "version": "2.0.0",
            "environment": "testing",
            "gpu": {"device_id": 1, "precision": "fp32"},
            "camera": {"count": 2, "fps": 60},
            "model": {"model_type": "onnx", "device": "cpu"},
            "analysis": {"target_fps": 60, "parallel_workers": 8},
        }
        config = AppConfig(**data)
        assert config.app_name == "TestApp"
        assert config.gpu.device_id == 1
        assert config.gpu.precision == "fp32"
        assert config.camera.count == 2
        assert config.camera.fps == 60
        assert config.model.model_type == "onnx"
        assert config.model.device == "cpu"
        assert config.analysis.target_fps == 60
        result.ok("중첩 딕셔너리로 생성")
    except Exception as e:
        result.fail("중첩 딕셔너리", str(e))

    # 12-5. model_validate로 생성 (Pydantic v2)
    try:
        data = {
            "app_name": "ValidateApp",
            "gpu": {"memory_fraction": 0.5},
            "database": {"journal_mode": "delete"},  # 소문자 → 대문자
        }
        config = AppConfig.model_validate(data)
        assert config.app_name == "ValidateApp"
        assert config.gpu.memory_fraction == 0.5
        assert config.database.journal_mode == "DELETE"
        result.ok("model_validate 딕셔너리 검증")
    except Exception as e:
        result.fail("model_validate", str(e))

    # 12-6. 서브 설정 기본 인스턴스 독립성
    try:
        c1 = AppConfig()
        c2 = AppConfig()
        c1.gpu.device_id = 5
        assert c2.gpu.device_id == 0  # 독립적이어야 함
        result.ok("서브 설정 기본 인스턴스 독립성")
    except Exception as e:
        result.fail("인스턴스 독립성", str(e))

    # 12-7. 알 수 없는 최상위 필드 무시
    try:
        config = AppConfig(unknown_top_level="ignored")
        assert not hasattr(config, "unknown_top_level")
        result.ok("알 수 없는 최상위 필드 무시 (extra='ignore')")
    except Exception as e:
        result.fail("알 수 없는 필드 무시", str(e))


# =============================================================================
# [13] SchemaValidator 클래스 테스트
# =============================================================================
def test_schema_validator(result: TestResult) -> None:
    """SchemaValidator 클래스 테스트."""
    print("\n[13] SchemaValidator 테스트")

    # 13-1. 기본 초기화
    try:
        sv = SchemaValidator()
        assert sv._strict_mode is False
        assert sv._coerce_types is True
        assert sv._apply_defaults is True
        result.ok("기본 초기화 (strict=False, coerce=True, defaults=True)")
    except Exception as e:
        result.fail("기본 초기화", str(e))

    # 13-2. 커스텀 초기화
    try:
        sv = SchemaValidator(strict_mode=True, coerce_types=False, apply_defaults=False)
        assert sv._strict_mode is True
        assert sv._coerce_types is False
        assert sv._apply_defaults is False
        result.ok("커스텀 초기화")
    except Exception as e:
        result.fail("커스텀 초기화", str(e))

    # 13-3. validate() 성공
    try:
        sv = SchemaValidator()
        vr = sv.validate({"device_id": 2, "precision": "fp32"}, GPUConfig)
        assert vr.is_valid is True
        assert vr.status == ValidationStatus.SUCCESS
        assert isinstance(vr.data, GPUConfig)
        assert vr.data.device_id == 2
        assert vr.data.precision == "fp32"
        assert vr.schema_name == "GPUConfig"
        assert vr.error_count == 0
        result.ok("validate() 성공 → GPUConfig")
    except Exception as e:
        result.fail("validate() 성공", str(e))

    # 13-4. validate() 실패
    try:
        sv = SchemaValidator()
        vr = sv.validate({"device_id": 99}, GPUConfig)  # 범위 초과
        assert vr.is_valid is False
        assert vr.status == ValidationStatus.FAILED
        assert vr.data is None
        assert vr.error_count >= 1
        assert vr.schema_name == "GPUConfig"
        # 오류 상세
        err = vr.errors[0]
        assert isinstance(err, ValidationErrorDetail)
        assert err.field  # 필드명 존재
        assert err.message  # 메시지 존재
        result.ok("validate() 실패 → 오류 상세 포함")
    except Exception as e:
        result.fail("validate() 실패", str(e))

    # 13-5. validate() 빈 딕셔너리 → 기본값 적용
    try:
        sv = SchemaValidator()
        vr = sv.validate({}, GPUConfig)
        assert vr.is_valid is True
        assert vr.data.device_id == 0  # 기본값
        assert vr.data.precision == "fp16"  # 기본값
        result.ok("validate() 빈 딕셔너리 → 기본값 적용")
    except Exception as e:
        result.fail("validate() 빈 딕셔너리", str(e))

    # 13-6. validate_or_raise() 성공
    try:
        sv = SchemaValidator()
        data = sv.validate_or_raise({"fps": 60, "count": 2}, CameraConfig)
        assert isinstance(data, CameraConfig)
        assert data.fps == 60
        assert data.count == 2
        result.ok("validate_or_raise() 성공 → CameraConfig")
    except Exception as e:
        result.fail("validate_or_raise() 성공", str(e))

    # 13-7. validate_or_raise() 실패 → SchemaValidationException
    try:
        sv = SchemaValidator()
        raised = False
        try:
            sv.validate_or_raise({"device_id": 99}, GPUConfig)
        except SchemaValidationException as e:
            raised = True
            assert e.errors  # 오류 목록 존재
        assert raised, "SchemaValidationException 발생해야 함"
        result.ok("validate_or_raise() 실패 → SchemaValidationException")
    except Exception as e:
        result.fail("validate_or_raise() 실패", str(e))

    # 13-8. validate_field() 단일 필드 검증
    try:
        sv = SchemaValidator()
        vr = sv.validate_field("fp32", GPUConfig, "precision")
        assert vr.is_valid is True
        result.ok("validate_field() 성공 (precision=fp32)")
    except Exception as e:
        result.fail("validate_field() 성공", str(e))

    # 13-9. validate_field() 실패
    try:
        sv = SchemaValidator()
        vr = sv.validate_field("invalid_precision", GPUConfig, "precision")
        assert vr.is_valid is False
        assert vr.error_count >= 1
        result.ok("validate_field() 실패 (invalid_precision)")
    except Exception as e:
        result.fail("validate_field() 실패", str(e))

    # 13-10. get_schema_info()
    try:
        sv = SchemaValidator()
        info = sv.get_schema_info(GPUConfig)
        assert info["name"] == "GPUConfig"
        assert "fields" in info
        assert "device_id" in info["fields"]
        assert "precision" in info["fields"]
        field_info = info["fields"]["device_id"]
        assert "type" in field_info
        assert "required" in field_info
        assert "description" in field_info
        result.ok("get_schema_info() 구조 검증")
    except Exception as e:
        result.fail("get_schema_info()", str(e))

    # 13-11. get_schema_info() 필드 수
    try:
        sv = SchemaValidator()
        info = sv.get_schema_info(GPUConfig)
        assert len(info["fields"]) == 11  # GPUConfig 11개 필드
        info = sv.get_schema_info(CameraConfig)
        assert len(info["fields"]) == 10  # CameraConfig 10개 필드
        result.ok("get_schema_info() 필드 수 (GPU=11, Camera=10)")
    except Exception as e:
        result.fail("get_schema_info() 필드 수", str(e))

    # 13-12. _convert_pydantic_errors()
    try:
        sv = SchemaValidator()
        # 일부러 에러 유발
        vr = sv.validate({"device_id": 99, "precision": "xxx"}, GPUConfig)
        assert vr.is_valid is False
        # 오류에 field, message, error_type이 모두 있는지 확인
        for err in vr.errors:
            assert err.field is not None
            assert err.message is not None
            assert err.error_type is not None
        result.ok("_convert_pydantic_errors() 오류 변환")
    except Exception as e:
        result.fail("_convert_pydantic_errors()", str(e))

    # 13-13. validate() 중첩 스키마 (AppConfig)
    try:
        sv = SchemaValidator()
        data = {
            "app_name": "Test",
            "gpu": {"device_id": 1},
            "camera": {"count": 2},
        }
        vr = sv.validate(data, AppConfig)
        assert vr.is_valid is True
        assert vr.data.gpu.device_id == 1
        assert vr.data.camera.count == 2
        result.ok("validate() 중첩 스키마 (AppConfig)")
    except Exception as e:
        result.fail("validate() 중첩 스키마", str(e))

    # 13-14. validate() 중첩 스키마 오류
    try:
        sv = SchemaValidator()
        data = {
            "gpu": {"device_id": 99},  # 범위 초과
        }
        vr = sv.validate(data, AppConfig)
        assert vr.is_valid is False
        assert vr.error_count >= 1
        # 중첩 필드 경로 확인
        has_gpu_error = any("gpu" in err.field for err in vr.errors)
        assert has_gpu_error, "gpu 관련 오류 경로 포함해야 함"
        result.ok("validate() 중첩 스키마 오류 경로 포함")
    except Exception as e:
        result.fail("validate() 중첩 스키마 오류", str(e))


# =============================================================================
# [14] 헬퍼 함수 테스트
# =============================================================================
def test_helper_functions(result: TestResult) -> None:
    """헬퍼 함수 테스트."""
    print("\n[14] 헬퍼 함수 테스트")

    # 14-1. validate_config() 성공
    try:
        config = validate_config({"device_id": 3, "precision": "int8"}, GPUConfig)
        assert isinstance(config, GPUConfig)
        assert config.device_id == 3
        assert config.precision == "int8"
        result.ok("validate_config() 성공")
    except Exception as e:
        result.fail("validate_config() 성공", str(e))

    # 14-2. validate_config() 실패 → SchemaValidationException
    try:
        raised = False
        try:
            validate_config({"device_id": 99}, GPUConfig)
        except SchemaValidationException:
            raised = True
        assert raised
        result.ok("validate_config() 실패 → SchemaValidationException")
    except Exception as e:
        result.fail("validate_config() 실패", str(e))

    # 14-3. validate_config() strict 모드
    try:
        config = validate_config({"device_id": 0}, GPUConfig, strict=True)
        assert isinstance(config, GPUConfig)
        result.ok("validate_config(strict=True) 동작")
    except Exception as e:
        result.fail("validate_config(strict=True)", str(e))

    # 14-4. get_default_config() - GPUConfig
    try:
        config = get_default_config(GPUConfig)
        assert isinstance(config, GPUConfig)
        assert config.device_id == 0
        assert config.precision == "fp16"
        result.ok("get_default_config(GPUConfig)")
    except Exception as e:
        result.fail("get_default_config(GPUConfig)", str(e))

    # 14-5. get_default_config() - AppConfig
    try:
        config = get_default_config(AppConfig)
        assert isinstance(config, AppConfig)
        assert isinstance(config.gpu, GPUConfig)
        assert isinstance(config.camera, CameraConfig)
        result.ok("get_default_config(AppConfig)")
    except Exception as e:
        result.fail("get_default_config(AppConfig)", str(e))

    # 14-6. get_default_config() - 각 스키마
    try:
        schemas = [
            LocalDatabaseConfig, GPUConfig, CameraConfig,
            ModelConfig, AnalysisConfig, LocalStorageConfig,
            LoggingConfig, AppConfig,
        ]
        for schema in schemas:
            config = get_default_config(schema)
            assert isinstance(config, schema)
        result.ok(f"get_default_config() 전체 스키마 ({len(schemas)}종)")
    except Exception as e:
        result.fail("get_default_config() 전체 스키마", str(e))

    # 14-7. validate_config() 빈 딕셔너리 → 기본값
    try:
        config = validate_config({}, GPUConfig)
        assert config.device_id == 0
        assert config.precision == "fp16"
        result.ok("validate_config({}) 빈 딕셔너리 → 기본값")
    except Exception as e:
        result.fail("validate_config({}) 빈 딕셔너리", str(e))


# =============================================================================
# [15] 엣지 케이스 및 예외 처리 테스트
# =============================================================================
def test_edge_cases(result: TestResult) -> None:
    """엣지 케이스 및 예외 처리 테스트."""
    print("\n[15] 엣지 케이스 테스트")

    # 15-1. 타입 강제 변환 (int → float)
    try:
        config = GPUConfig(memory_fraction=1)  # int → float 변환
        assert config.memory_fraction == 1.0
        assert isinstance(config.memory_fraction, float)
        result.ok("타입 강제 변환 (int → float)")
    except Exception as e:
        result.fail("타입 강제 변환", str(e))

    # 15-2. 타입 강제 변환 (str → int)
    try:
        config = CameraConfig(count="4")  # str → int 변환
        assert config.count == 4
        result.ok("타입 강제 변환 (str → int)")
    except Exception as e:
        result.fail("타입 강제 변환 str→int", str(e))

    # 15-3. None 값 처리 (Optional 필드)
    try:
        config = LoggingConfig(file_path=None)
        assert config.file_path is None
        result.ok("None 값 (Optional 필드)")
    except Exception as e:
        result.fail("None 값", str(e))

    # 15-4. 다중 오류 동시 검출
    try:
        sv = SchemaValidator()
        data = {
            "device_id": 99,        # 범위 초과
            "memory_fraction": 5.0,  # 범위 초과
            "precision": "invalid",  # 무효 값
        }
        vr = sv.validate(data, GPUConfig)
        assert vr.is_valid is False
        assert vr.error_count >= 3  # 최소 3개 오류
        result.ok(f"다중 오류 동시 검출 ({vr.error_count}개)")
    except Exception as e:
        result.fail("다중 오류 동시 검출", str(e))

    # 15-5. model_validate 사용 (Pydantic v2 API)
    try:
        config = GPUConfig.model_validate({"device_id": 2, "precision": "int8"})
        assert config.device_id == 2
        assert config.precision == "int8"
        result.ok("model_validate (Pydantic v2 API)")
    except Exception as e:
        result.fail("model_validate", str(e))

    # 15-6. model_dump 사용 (Pydantic v2 API)
    try:
        config = GPUConfig()
        dumped = config.model_dump()
        assert isinstance(dumped, dict)
        assert "device_id" in dumped
        assert "precision" in dumped
        assert dumped["device_id"] == 0
        assert dumped["precision"] == "fp16"
        result.ok("model_dump (Pydantic v2 API)")
    except Exception as e:
        result.fail("model_dump", str(e))

    # 15-7. model_json_schema (Pydantic v2 API)
    try:
        schema = GPUConfig.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "device_id" in schema["properties"]
        result.ok("model_json_schema (Pydantic v2 API)")
    except Exception as e:
        result.fail("model_json_schema", str(e))

    # 15-8. ValidationResult.to_dict() → JSON 직렬화 가능
    try:
        import json
        vr = ValidationResult(
            status=ValidationStatus.SUCCESS,
            data=None,
            schema_name="TestSchema",
        )
        d = vr.to_dict()
        json_str = json.dumps(d, default=str)  # datetime 처리
        assert isinstance(json_str, str)
        result.ok("ValidationResult.to_dict() JSON 직렬화")
    except Exception as e:
        result.fail("JSON 직렬화", str(e))

    # 15-9. SchemaValidator validate() 예외 발생 (비정상 입력)
    try:
        sv = SchemaValidator()
        # None 입력 시 내부에서 Exception 포착
        vr = sv.validate(None, GPUConfig)
        assert vr.is_valid is False
        assert vr.error_count >= 1
        result.ok("validate(None) → FAILED + 오류")
    except Exception as e:
        result.fail("validate(None)", str(e))

    # 15-10. __all__ 모듈 Export 확인
    try:
        from core_foundation.config import validator
        expected = {
            "ValidationStatus",
            "ValidationErrorDetail", "ValidationResult",
            "BaseConfigModel",
            "LocalDatabaseConfig", "GPUConfig", "CameraConfig", "LocalStorageConfig",
            "ModelConfig", "AnalysisConfig", "LoggingConfig",
            "AppConfig",
            "SchemaValidator",
            "validate_config", "get_default_config",
        }
        actual = set(validator.__all__)
        assert actual == expected, f"차이: {actual.symmetric_difference(expected)}"
        result.ok(f"__all__ Export 확인 ({len(expected)}개)")
    except Exception as e:
        result.fail("__all__ Export", str(e))

    # 15-11. __version__ 확인
    try:
        from core_foundation.config import validator
        assert validator.__version__ == "1.0.0"
        result.ok("__version__ = 1.0.0")
    except Exception as e:
        result.fail("__version__", str(e))

    # 15-12. AnalysisConfig supported_formats 빈 리스트
    try:
        config = AnalysisConfig(supported_formats=[])
        assert config.supported_formats == []
        result.ok("supported_formats 빈 리스트 허용")
    except Exception as e:
        result.fail("supported_formats 빈 리스트", str(e))


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> bool:
    """메인 실행."""
    print("=" * 60)
    print("COURTVIEW - SchemaValidator 단위 테스트")
    print("대상: core_foundation/config/validator.py")
    print("=" * 60)

    r = TestResult()

    # [1] ValidationStatus Enum
    test_validation_status_enum(r)

    # [2] ValidationErrorDetail
    test_validation_error_detail(r)

    # [3] ValidationResult
    test_validation_result(r)

    # [4] BaseConfigModel
    test_base_config_model(r)

    # [5] LocalDatabaseConfig
    test_local_database_config(r)

    # [6] GPUConfig
    test_gpu_config(r)

    # [7] CameraConfig
    test_camera_config(r)

    # [8] ModelConfig
    test_model_config(r)

    # [9] AnalysisConfig
    test_analysis_config(r)

    # [10] LocalStorageConfig
    test_local_storage_config(r)

    # [11] LoggingConfig
    test_logging_config(r)

    # [12] AppConfig
    test_app_config(r)

    # [13] SchemaValidator
    test_schema_validator(r)

    # [14] 헬퍼 함수
    test_helper_functions(r)

    # [15] 엣지 케이스
    test_edge_cases(r)

    r.summary()
    return r.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
