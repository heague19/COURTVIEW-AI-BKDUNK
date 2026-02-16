# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/exceptions/performance
파일: test_validation_exceptions_perf.py
설명: validation_exceptions.py 성능 테스트 (31개 클래스 생성/직렬화/팩토리 벤치마크)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import gc
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# 테스트 대상 임포트
# =============================================================================
from shared.exceptions.validation_exceptions import (
    ValidationException,
    InvalidRequestException,
    InputValidationException,
    MissingFieldException,
    InvalidFieldTypeException,
    InvalidFieldValueException,
    ValueOutOfRangeException,
    StringLengthException,
    InvalidEnumValueException,
    InvalidJsonFormatException,
    InvalidDateFormatException,
    URLValidationException,
    SecurityException,
    FormatDetectionException,
    UnsupportedFormatException,
    FormatValidationException,
    ResolutionException,
    ConfigurationException,
    ConfigurationNotFoundException,
    ConfigurationLoadException,
    ConfigurationParseException,
    ConfigurationValidationException,
    SchemaValidationException,
    AuthenticationException,
    AuthorizationException,
    RateLimitException,
    DataQualityException,
    LowQualityException,
    RuleSetNotFoundException,
    RuleSetValidationException,
    RuleSetVersionMismatchException,
)


# =============================================================================
# 성능 테스트 하네스
# =============================================================================
class PerfResult:
    """성능 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {name}: {elapsed_us:.3f}us ({ratio:.1f}% of {limit_us:.0f}us)")

    def fail(self, name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {elapsed_us:.3f}us > {limit_us:.0f}us")
        print(f"  [FAIL] {name}: {elapsed_us:.3f}us (limit: {limit_us:.0f}us)")

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n  실패:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (마이크로초/반복)."""
    gc.disable()
    try:
        warmup = min(iterations, 1000)
        for _ in range(warmup):
            func()

        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start

        return elapsed_ns / iterations / 1000  # ns → us
    finally:
        gc.enable()


def bench(r: PerfResult, name: str, func, limit_us: float, iters: int = 30000) -> None:
    """벤치마크 헬퍼: 측정 + pass/fail 판정."""
    elapsed = measure(func, iters)
    if elapsed < limit_us:
        r.ok(name, elapsed, limit_us)
    else:
        r.fail(name, elapsed, limit_us)


# =============================================================================
# [1] 기본 클래스 생성 성능
# =============================================================================
def test_base_creation(r: PerfResult) -> None:
    """기본 유효성 검사 예외 생성 성능."""
    limit = 60.0  # us

    bench(r, "ValidationException()", lambda: ValidationException(), limit)
    bench(r, "InvalidRequestException()", lambda: InvalidRequestException(), limit)
    bench(r, "InputValidationException()", lambda: InputValidationException(), limit)


# =============================================================================
# [2] 필드 예외 생성 성능
# =============================================================================
def test_field_creation(r: PerfResult) -> None:
    """필드 유효성 검사 예외 생성 성능."""
    limit = 80.0

    bench(r, "MissingFieldException('name')",
          lambda: MissingFieldException("name"), limit)
    bench(r, "MissingFieldException('city', 'address')",
          lambda: MissingFieldException("city", parent_field="address"), limit)
    bench(r, "InvalidFieldTypeException(str type)",
          lambda: InvalidFieldTypeException("age", int, str), limit)
    bench(r, "InvalidFieldValueException('status')",
          lambda: InvalidFieldValueException("status", "bad", "무효"), limit)


# =============================================================================
# [3] 범위/길이 예외 생성 성능
# =============================================================================
def test_range_length_creation(r: PerfResult) -> None:
    """범위/길이 예외 생성 성능."""
    limit = 80.0

    bench(r, "ValueOutOfRangeException(min+max)",
          lambda: ValueOutOfRangeException("fps", 200, min_value=15, max_value=120), limit)
    bench(r, "StringLengthException(SHORT)",
          lambda: StringLengthException("name", 2, min_length=3), limit)
    bench(r, "StringLengthException(LONG)",
          lambda: StringLengthException("bio", 1000, max_length=500), limit)


# =============================================================================
# [4] 데이터 형식 예외 생성 성능
# =============================================================================
def test_format_creation(r: PerfResult) -> None:
    """데이터 형식 예외 생성 성능."""
    limit = 80.0

    bench(r, "InvalidEnumValueException(3 allowed)",
          lambda: InvalidEnumValueException("status", "x", ["a", "b", "c"]), limit)
    bench(r, "InvalidEnumValueException(15 allowed)",
          lambda: InvalidEnumValueException("type", "x", [f"v{i}" for i in range(15)]), limit)
    bench(r, "InvalidJsonFormatException(line,col)",
          lambda: InvalidJsonFormatException("err", line=10, column=5), limit)
    bench(r, "InvalidDateFormatException()",
          lambda: InvalidDateFormatException("date", "2024-13-45"), limit)


# =============================================================================
# [5] URL 예외 + 팩토리 성능
# =============================================================================
def test_url_creation(r: PerfResult) -> None:
    """URL 검증 예외 + 팩토리 메서드 성능."""
    limit_base = 100.0  # URL sanitize 포함
    limit_factory = 120.0

    bench(r, "URLValidationException(url=...)",
          lambda: URLValidationException(url="https://example.com/path?key=val"), limit_base)
    bench(r, "URL.invalid_format()",
          lambda: URLValidationException.invalid_format("http://bad"), limit_factory)
    bench(r, "URL.invalid_scheme()",
          lambda: URLValidationException.invalid_scheme("ftp://x", "ftp", ["http"]), limit_factory)
    bench(r, "URL.blocked_host()",
          lambda: URLValidationException.blocked_host("http://evil", "evil"), limit_factory)
    bench(r, "URL.private_ip()",
          lambda: URLValidationException.private_ip("http://10.0.0.1", "10.0.0.1"), limit_factory)
    bench(r, "URL.too_long()",
          lambda: URLValidationException.too_long("http://x/" + "a" * 100, 110, 2048), limit_factory)


# =============================================================================
# [6] 보안 예외 + 팩토리 성능
# =============================================================================
def test_security_creation(r: PerfResult) -> None:
    """보안 예외 + 팩토리 성능."""
    limit = 80.0

    bench(r, "SecurityException()",
          lambda: SecurityException(), limit)
    bench(r, "Security.ssrf_detected()",
          lambda: SecurityException.ssrf_detected("http://evil", "10.0.0.1"), limit)
    bench(r, "Security.dns_rebinding_detected()",
          lambda: SecurityException.dns_rebinding_detected("evil.com", ["1.2.3.4"]), limit)


# =============================================================================
# [7] 파일 포맷 예외 + 팩토리 성능
# =============================================================================
def test_file_format_creation(r: PerfResult) -> None:
    """파일 포맷 예외 + 팩토리 성능."""
    limit = 80.0

    bench(r, "FormatDetection.read_failed()",
          lambda: FormatDetectionException.read_failed("/tmp/v.mp4"), limit)
    bench(r, "FormatDetection.invalid_magic_bytes()",
          lambda: FormatDetectionException.invalid_magic_bytes("/tmp/v.mp4", b"\x00\x01"), limit)
    bench(r, "FormatDetection.corrupted_file()",
          lambda: FormatDetectionException.corrupted_file("/tmp/v.mp4"), limit)
    bench(r, "FormatDetection.format_mismatch()",
          lambda: FormatDetectionException.format_mismatch("/tmp/v.mp4", "avi", "mp4"), limit)

    bench(r, "Unsupported.video_format()",
          lambda: UnsupportedFormatException.video_format("/tmp/v.wmv", "WMV"), limit)
    bench(r, "Unsupported.image_format()",
          lambda: UnsupportedFormatException.image_format("/tmp/i.tiff", "TIFF"), limit)
    bench(r, "Unsupported.audio_format()",
          lambda: UnsupportedFormatException.audio_format("/tmp/a.wma", "WMA"), limit)


# =============================================================================
# [8] 포맷 검증 팩토리 성능
# =============================================================================
def test_format_validation_creation(r: PerfResult) -> None:
    """포맷 검증 팩토리 (7개) 성능."""
    limit = 80.0

    bench(r, "FmtVal.codec_not_supported()",
          lambda: FormatValidationException.codec_not_supported("/tmp/v.mp4", "vp9"), limit)
    bench(r, "FmtVal.format_not_allowed()",
          lambda: FormatValidationException.format_not_allowed("/tmp/v.flv", "FLV"), limit)
    bench(r, "FmtVal.bitrate_out_of_range()",
          lambda: FormatValidationException.bitrate_out_of_range("/tmp/v.mp4", 50_000_000, 1_000_000, 20_000_000), limit)
    bench(r, "FmtVal.fps_too_low()",
          lambda: FormatValidationException.fps_too_low("/tmp/v.mp4", 10.0, 24.0), limit)
    bench(r, "FmtVal.fps_too_high()",
          lambda: FormatValidationException.fps_too_high("/tmp/v.mp4", 240.0, 120.0), limit)
    bench(r, "FmtVal.duration_too_short()",
          lambda: FormatValidationException.duration_too_short("/tmp/v.mp4", 0.5, 3.0), limit)
    bench(r, "FmtVal.duration_too_long()",
          lambda: FormatValidationException.duration_too_long("/tmp/v.mp4", 7200.0, 3600.0), limit)


# =============================================================================
# [9] 해상도 팩토리 성능
# =============================================================================
def test_resolution_creation(r: PerfResult) -> None:
    """해상도 팩토리 (4개) 성능."""
    limit = 80.0
    limit_gcd = 100.0  # gcd 계산 포함

    bench(r, "Resolution.too_low()",
          lambda: ResolutionException.too_low("/tmp/v.mp4", 320, 240, 640, 480), limit)
    bench(r, "Resolution.too_high()",
          lambda: ResolutionException.too_high("/tmp/v.mp4", 7680, 4320, 3840, 2160), limit)
    bench(r, "Resolution.not_supported()",
          lambda: ResolutionException.not_supported("/tmp/v.mp4", 800, 600), limit)
    bench(r, "Resolution.aspect_ratio(gcd 포함)",
          lambda: ResolutionException.aspect_ratio_not_supported("/tmp/v.mp4", 1920, 1080, ["16:9"]), limit_gcd)


# =============================================================================
# [10] 설정 예외 생성 성능
# =============================================================================
def test_config_creation(r: PerfResult) -> None:
    """설정 예외 (5개) 생성 성능."""
    limit = 80.0

    bench(r, "ConfigurationException()",
          lambda: ConfigurationException(), limit)
    bench(r, "ConfigNotFound('config.yaml')",
          lambda: ConfigurationNotFoundException("config.yaml"), limit)
    bench(r, "ConfigLoad('config.yaml', reason)",
          lambda: ConfigurationLoadException("config.yaml", "손상"), limit)
    bench(r, "ConfigParse('config.yaml', reason, line)",
          lambda: ConfigurationParseException("config.yaml", "YAML 오류", 42), limit)
    bench(r, "ConfigValidation('key', 'val', 'reason')",
          lambda: ConfigurationValidationException("db.port", "abc", "숫자"), limit)


# =============================================================================
# [11] 스키마/인증/권한/속도제한 생성 성능
# =============================================================================
def test_schema_auth_rate_creation(r: PerfResult) -> None:
    """스키마/인증/권한/속도제한 생성 성능."""
    limit = 80.0

    bench(r, "SchemaValidationException(2 errors)",
          lambda: SchemaValidationException([{"f": "a"}, {"f": "b"}], "Model"), limit)
    bench(r, "Schema.from_pydantic_errors()",
          lambda: SchemaValidationException.from_pydantic_errors(
              [{"loc": ("name",), "type": "missing", "msg": "필수"}], "User"), limit)

    bench(r, "Auth.token_expired()",
          lambda: AuthenticationException.token_expired(), limit)
    bench(r, "Auth.invalid_credentials()",
          lambda: AuthenticationException.invalid_credentials(), limit)
    bench(r, "Auth.api_key_invalid(prefix)",
          lambda: AuthenticationException.api_key_invalid("sk-12345678"), limit)

    bench(r, "Authz.resource_access_denied()",
          lambda: AuthorizationException.resource_access_denied("video", "v001", "read"), limit)

    bench(r, "RateLimitException(full)",
          lambda: RateLimitException(limit=100, window_seconds=60, current_count=105, retry_after=30.0), limit)


# =============================================================================
# [12] 데이터 품질 팩토리 성능
# =============================================================================
def test_quality_creation(r: PerfResult) -> None:
    """데이터 품질 팩토리 성능."""
    limit = 80.0
    limit_quality = 100.0  # from_quality_result는 recommendations 생성

    bench(r, "DQ.brightness_error()",
          lambda: DataQualityException.brightness_error(10.0, 30.0, 200.0), limit)
    bench(r, "DQ.contrast_error()",
          lambda: DataQualityException.contrast_error(15.0, 30.0), limit)
    bench(r, "DQ.noise_error()",
          lambda: DataQualityException.noise_error(80.0, 50.0), limit)
    bench(r, "DQ.blur_error()",
          lambda: DataQualityException.blur_error(10.0, 30.0), limit)

    bench(r, "LowQuality.from_quality_result(3 dims)",
          lambda: LowQualityException.from_quality_result(
              45.0, 60.0, {"brightness": 20.0, "blur": 15.0, "noise": 80.0},
              ["brightness", "blur", "noise"], "poor"), limit_quality)


# =============================================================================
# [13] 규칙 세트 팩토리 성능
# =============================================================================
def test_rule_set_creation(r: PerfResult) -> None:
    """규칙 세트 팩토리 성능."""
    limit = 80.0

    bench(r, "RuleSetNotFound('NBA')",
          lambda: RuleSetNotFoundException("NBA"), limit)
    bench(r, "RuleSetNotFound.for_league()",
          lambda: RuleSetNotFoundException.for_league("WNBA", ["NBA", "FIBA"]), limit)

    bench(r, "RuleSetValidation.schema_error()",
          lambda: RuleSetValidationException.schema_error("NBA", [{"f": "err"}]), limit)
    bench(r, "RuleSetValidation.invalid_rule()",
          lambda: RuleSetValidationException.invalid_rule("FIBA", "R042", "invalid"), limit)
    bench(r, "RuleSetValidation.missing_required_field()",
          lambda: RuleSetValidationException.missing_required_field("KBL", "shot_clock"), limit)

    bench(r, "VersionMismatch('NBA', v2, v1)",
          lambda: RuleSetVersionMismatchException("NBA", "v2.0.0", "v1.5.0"), limit)
    bench(r, "VersionMismatch.incompatible()",
          lambda: RuleSetVersionMismatchException.incompatible("FIBA", "v3.0", "v2.0"), limit)


# =============================================================================
# [14] 직렬화 성능
# =============================================================================
def test_serialization_perf(r: PerfResult) -> None:
    """직렬화 메서드 성능."""
    limit_dict = 30.0
    limit_resp = 20.0

    # ValidationException to_dict
    ve = ValidationException(field_name="email", field_value="bad@")
    bench(r, "ValidationException.to_dict()", lambda: ve.to_dict(), limit_dict)
    bench(r, "ValidationException.to_response_dict()", lambda: ve.to_response_dict(), limit_resp)

    # SecurityException to_dict (복잡한 details)
    se = SecurityException.ssrf_detected("http://evil.com", "10.0.0.1", "내부망")
    bench(r, "SecurityException.to_dict()", lambda: se.to_dict(), limit_dict)

    # RateLimitException to_dict (retry 필드 포함)
    rl = RateLimitException(limit=100, current_count=105, retry_after=30.0)
    bench(r, "RateLimitException.to_dict()", lambda: rl.to_dict(), limit_dict)

    # LowQualityException to_dict (복잡)
    lq = LowQualityException.from_quality_result(
        45.0, 60.0, {"brightness": 20.0, "blur": 15.0}, ["brightness", "blur"], "poor")
    bench(r, "LowQualityException.to_dict()", lambda: lq.to_dict(), limit_dict)


# =============================================================================
# [15] 특수 메서드 성능
# =============================================================================
def test_special_methods_perf(r: PerfResult) -> None:
    """특수 메서드 성능."""
    # to_response_headers
    rl = RateLimitException(limit=100, current_count=80, reset_at="2026-02-16T12:00:00Z")
    bench(r, "to_response_headers()", lambda: rl.to_response_headers(), 15.0)

    # is_upgrade_available
    vm = RuleSetVersionMismatchException("NBA", "v1.0.0", "v2.0.0")
    bench(r, "is_upgrade_available()", lambda: vm.is_upgrade_available(), 10.0)

    # add_field_error
    ive = InputValidationException()
    bench(r, "add_field_error()", lambda: ive.add_field_error("f", "err"), 10.0)

    # _sanitize_url
    bench(r, "_sanitize_url(복잡 URL)",
          lambda: URLValidationException._sanitize_url("https://user:pass@example.com/path?key=val&token=abc"),
          50.0)

    # has_errors
    ive2 = InputValidationException(field_errors={"a": ["x"]})
    bench(r, "has_errors()", lambda: ive2.has_errors(), 5.0)


# =============================================================================
# [16] __str__ 성능
# =============================================================================
def test_str_perf(r: PerfResult) -> None:
    """__str__ 성능."""
    limit = 15.0

    ve = ValidationException(field_name="email")
    bench(r, "str(ValidationException)", lambda: str(ve), limit)

    me = MissingFieldException("name", "user")
    bench(r, "str(MissingFieldException)", lambda: str(me), limit)

    rl = RateLimitException(limit=100)
    bench(r, "str(RateLimitException)", lambda: str(rl), limit)

    vm = RuleSetVersionMismatchException("NBA", "v2.0.0", "v1.5.0")
    bench(r, "str(VersionMismatchException)", lambda: str(vm), limit)


# =============================================================================
# [17] 대량 생성 성능 (31개 클래스 연속 생성)
# =============================================================================
def test_bulk_creation(r: PerfResult) -> None:
    """31개 예외 클래스 연속 생성 성능."""
    def create_all():
        ValidationException()
        InvalidRequestException()
        InputValidationException()
        MissingFieldException("name")
        InvalidFieldTypeException("age", int, str)
        InvalidFieldValueException("status", "bad", "무효")
        ValueOutOfRangeException("fps", 200, min_value=15, max_value=120)
        StringLengthException("name", 2, min_length=3)
        InvalidEnumValueException("type", "x", ["a", "b"])
        InvalidJsonFormatException()
        InvalidDateFormatException("date", "bad")
        URLValidationException()
        SecurityException()
        FormatDetectionException()
        UnsupportedFormatException()
        FormatValidationException()
        ResolutionException()
        ConfigurationException()
        ConfigurationNotFoundException("cfg.yaml")
        ConfigurationLoadException("cfg.yaml")
        ConfigurationParseException("cfg.yaml")
        ConfigurationValidationException("key", "val", "reason")
        SchemaValidationException([{"f": "err"}])
        AuthenticationException()
        AuthorizationException()
        RateLimitException()
        DataQualityException()
        LowQualityException()
        RuleSetNotFoundException("NBA")
        RuleSetValidationException("NBA")
        RuleSetVersionMismatchException("NBA", "v2.0", "v1.0")

    elapsed = measure(create_all, 10000)
    limit = 2500.0  # 31개 × ~60us = ~1860us, 여유 포함
    if elapsed < limit:
        r.ok("31개 클래스 연속 생성", elapsed, limit)
    else:
        r.fail("31개 클래스 연속 생성", elapsed, limit)


# =============================================================================
# [18] raise/catch 성능
# =============================================================================
def test_raise_catch_perf(r: PerfResult) -> None:
    """raise/catch 성능."""
    limit = 100.0

    def raise_validation():
        try:
            raise ValidationException()
        except Exception:
            pass

    bench(r, "raise + catch ValidationException", raise_validation, limit)

    def raise_missing_field():
        try:
            raise MissingFieldException("name")
        except Exception:
            pass

    bench(r, "raise + catch MissingFieldException", raise_missing_field, limit)

    def raise_rate_limit():
        try:
            raise RateLimitException()
        except Exception:
            pass

    bench(r, "raise + catch RateLimitException", raise_rate_limit, limit)


# =============================================================================
# 메인
# =============================================================================
def main() -> int:
    r = PerfResult()
    print("\n" + "=" * 60)
    print("  validation_exceptions.py v1.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- [1] 기본 클래스 생성 ---")
    test_base_creation(r)

    print("\n--- [2] 필드 예외 생성 ---")
    test_field_creation(r)

    print("\n--- [3] 범위/길이 예외 생성 ---")
    test_range_length_creation(r)

    print("\n--- [4] 데이터 형식 예외 생성 ---")
    test_format_creation(r)

    print("\n--- [5] URL 예외 + 팩토리 ---")
    test_url_creation(r)

    print("\n--- [6] 보안 예외 + 팩토리 ---")
    test_security_creation(r)

    print("\n--- [7] 파일 포맷 팩토리 ---")
    test_file_format_creation(r)

    print("\n--- [8] 포맷 검증 팩토리 ---")
    test_format_validation_creation(r)

    print("\n--- [9] 해상도 팩토리 ---")
    test_resolution_creation(r)

    print("\n--- [10] 설정 예외 생성 ---")
    test_config_creation(r)

    print("\n--- [11] 스키마/인증/권한/속도제한 ---")
    test_schema_auth_rate_creation(r)

    print("\n--- [12] 데이터 품질 팩토리 ---")
    test_quality_creation(r)

    print("\n--- [13] 규칙 세트 팩토리 ---")
    test_rule_set_creation(r)

    print("\n--- [14] 직렬화 성능 ---")
    test_serialization_perf(r)

    print("\n--- [15] 특수 메서드 성능 ---")
    test_special_methods_perf(r)

    print("\n--- [16] __str__ 성능 ---")
    test_str_perf(r)

    print("\n--- [17] 대량 생성 (31개 연속) ---")
    test_bulk_creation(r)

    print("\n--- [18] raise/catch 성능 ---")
    test_raise_catch_perf(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    sys.exit(main())
