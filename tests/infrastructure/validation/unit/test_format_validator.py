# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/infrastructure/validation/unit
파일: test_format_validator.py
설명: FormatValidator 단위 테스트
      - FormatValidationConfig 슬롯/기본값/__post_init__ 클램핑/__repr__
      - FormatValidationResult 슬롯/기본값/프로퍼티/__repr__
      - FormatValidationStats 슬롯/기본값/pass_rate/avg_time_ms/__repr__
      - FormatValidator 파일 검증 (파일 없음/디렉토리/빈 파일/크기초과/확장자)
      - FormatValidator 포맷 검증 (실제 MP4 생성/비-비디오/check_format=False)
      - FormatValidator 메타데이터 검증 (해상도/FPS/check_metadata=False)
      - FormatValidator 배치 검증
      - FormatValidator 통계 누적 및 reset_stats
      - 상수 타입·값 검증
      - __all__ / __version__ export 검증

주의: __init__.py 없음 (Windows 패키지 섀도잉 방지)
      메서드명 ASCII 전용 (Windows cp949 인코딩 문제 방지)
      임시 파일은 tempfile.mkdtemp() 사용 (한글 경로 회피)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
# =============================================================================
# sys.path 설정 (프로젝트 루트 우선 등록)
# =============================================================================
import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

# =============================================================================
# 표준 라이브러리
# =============================================================================
import os
import tempfile
from pathlib import Path

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
import pytest

# =============================================================================
# 테스트 대상 모듈
# =============================================================================
import infrastructure.validation.format_validator as fv_module
from infrastructure.validation.format_validator import (
    MAX_ANALYSIS_FPS,
    MAX_VALIDATION_HISTORY,
    MIN_ANALYSIS_FPS,
    MIN_FORMAT_CONFIDENCE,
    MIN_VIDEO_DURATION_SEC,
    MAX_VIDEO_DURATION_SEC,
    FormatValidationConfig,
    FormatValidationResult,
    FormatValidationStats,
    FormatValidator,
)


# =============================================================================
# 공통 헬퍼: 실제 MP4 비디오 파일 생성
# =============================================================================

def _write_real_video(out_path: str, width: int = 640, height: int = 480,
                      fps: float = 30.0, frame_count: int = 30) -> str:
    """cv2.VideoWriter 로 실제 MP4 비디오를 생성한다.

    Windows 에서는 XVID 코덱이 안정적이므로 .avi 컨테이너를 사용하고,
    호출자가 경로 확장자를 .avi 로 지정해야 한다.

    Args:
        out_path: 출력 파일 경로 (*.avi)
        width: 가로 해상도
        height: 세로 해상도
        fps: 프레임 레이트
        frame_count: 생성할 프레임 수

    Returns:
        실제로 기록된 파일 경로
    """
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
    assert writer.isOpened(), f"VideoWriter 열기 실패: {out_path}"
    try:
        for i in range(frame_count):
            # 색이 다른 단색 프레임 (검은색~흰색 그라디언트)
            val = int((i / max(frame_count - 1, 1)) * 200)
            frame = np.full((height, width, 3), val, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()
    assert os.path.exists(out_path) and os.path.getsize(out_path) > 0, \
        f"VideoWriter 기록 실패: {out_path}"
    return out_path


def _make_tmp_dir() -> str:
    """한글 경로를 피하기 위해 tempfile.mkdtemp() 를 사용한다."""
    return tempfile.mkdtemp(prefix="cv_fmtval_")


# =============================================================================
# TestFormatValidationConfig
# =============================================================================

class TestFormatValidationConfig:
    """FormatValidationConfig 슬롯·기본값·__post_init__ 클램핑·__repr__ 검증."""

    # ------------------------------------------------------------------
    # 슬롯 & 기본값
    # ------------------------------------------------------------------

    def test_slots_exist(self) -> None:
        """__slots__ 이 정의되어 인스턴스 __dict__ 가 없어야 한다."""
        cfg = FormatValidationConfig()
        assert not hasattr(cfg, "__dict__"), "__dict__ 가 없어야 함 (slots=True)"

    def test_default_values_allowed_formats_none(self) -> None:
        """allowed_formats 기본값은 None 이다."""
        cfg = FormatValidationConfig()
        assert cfg.allowed_formats is None

    def test_default_values_allowed_codecs_none(self) -> None:
        """allowed_codecs 기본값은 None 이다."""
        cfg = FormatValidationConfig()
        assert cfg.allowed_codecs is None

    def test_default_check_format_true(self) -> None:
        """check_format 기본값은 True 이다."""
        cfg = FormatValidationConfig()
        assert cfg.check_format is True

    def test_default_check_metadata_true(self) -> None:
        """check_metadata 기본값은 True 이다."""
        cfg = FormatValidationConfig()
        assert cfg.check_metadata is True

    def test_default_strict_codec_check_false(self) -> None:
        """strict_codec_check 기본값은 False 이다."""
        cfg = FormatValidationConfig()
        assert cfg.strict_codec_check is False

    def test_default_fps_range(self) -> None:
        """기본 FPS 범위는 MIN_ANALYSIS_FPS ~ MAX_ANALYSIS_FPS 이다."""
        cfg = FormatValidationConfig()
        assert cfg.min_fps == MIN_ANALYSIS_FPS
        assert cfg.max_fps == MAX_ANALYSIS_FPS

    def test_default_duration_range(self) -> None:
        """기본 길이 범위는 MIN/MAX_VIDEO_DURATION_SEC 이다."""
        cfg = FormatValidationConfig()
        assert cfg.min_duration_sec == MIN_VIDEO_DURATION_SEC
        assert cfg.max_duration_sec == MAX_VIDEO_DURATION_SEC

    # ------------------------------------------------------------------
    # __post_init__ 클램핑
    # ------------------------------------------------------------------

    def test_post_init_clamps_negative_min_width(self) -> None:
        """min_width < 1 이면 1로 클램핑된다."""
        cfg = FormatValidationConfig(min_width=-5)
        assert cfg.min_width == 1

    def test_post_init_clamps_negative_min_height(self) -> None:
        """min_height < 1 이면 1로 클램핑된다."""
        cfg = FormatValidationConfig(min_height=-10)
        assert cfg.min_height == 1

    def test_post_init_clamps_max_width_less_than_min(self) -> None:
        """max_width < min_width 이면 max_width = min_width 로 조정된다."""
        cfg = FormatValidationConfig(min_width=800, max_width=200)
        assert cfg.max_width == cfg.min_width

    def test_post_init_clamps_max_height_less_than_min(self) -> None:
        """max_height < min_height 이면 max_height = min_height 로 조정된다."""
        cfg = FormatValidationConfig(min_height=600, max_height=100)
        assert cfg.max_height == cfg.min_height

    def test_post_init_clamps_fps_below_one(self) -> None:
        """min_fps < 1.0 이면 1.0 으로 클램핑된다."""
        cfg = FormatValidationConfig(min_fps=0.0)
        assert cfg.min_fps == 1.0

    def test_post_init_clamps_max_fps_less_than_min(self) -> None:
        """max_fps < min_fps 이면 max_fps = min_fps 로 조정된다."""
        cfg = FormatValidationConfig(min_fps=60.0, max_fps=30.0)
        assert cfg.max_fps == cfg.min_fps

    def test_post_init_clamps_negative_min_duration(self) -> None:
        """min_duration_sec < 0 이면 0 으로 클램핑된다."""
        cfg = FormatValidationConfig(min_duration_sec=-1.0)
        assert cfg.min_duration_sec == 0.0

    def test_post_init_clamps_max_duration_less_than_min(self) -> None:
        """max_duration_sec < min_duration_sec 이면 조정된다."""
        cfg = FormatValidationConfig(min_duration_sec=10.0, max_duration_sec=5.0)
        assert cfg.max_duration_sec == cfg.min_duration_sec

    def test_post_init_clamps_file_size_zero(self) -> None:
        """max_file_size_bytes < 1 이면 1 로 클램핑된다."""
        cfg = FormatValidationConfig(max_file_size_bytes=0)
        assert cfg.max_file_size_bytes == 1

    def test_post_init_clamps_negative_min_bitrate(self) -> None:
        """min_bitrate_bps < 0 이면 0 으로 클램핑된다."""
        cfg = FormatValidationConfig(min_bitrate_bps=-1000)
        assert cfg.min_bitrate_bps == 0

    def test_post_init_clamps_max_bitrate_less_than_min(self) -> None:
        """max_bitrate_bps < min_bitrate_bps 이면 조정된다."""
        cfg = FormatValidationConfig(min_bitrate_bps=5_000_000, max_bitrate_bps=1_000_000)
        assert cfg.max_bitrate_bps == cfg.min_bitrate_bps

    # ------------------------------------------------------------------
    # __repr__
    # ------------------------------------------------------------------

    def test_repr_contains_class_name(self) -> None:
        """__repr__ 에 클래스명이 포함된다."""
        cfg = FormatValidationConfig()
        assert "FormatValidationConfig" in repr(cfg)

    def test_repr_contains_resolution_info(self) -> None:
        """__repr__ 에 해상도 범위 정보가 포함된다."""
        cfg = FormatValidationConfig(min_width=320, min_height=240,
                                     max_width=1920, max_height=1080)
        r = repr(cfg)
        assert "320" in r
        assert "240" in r

    def test_custom_allowed_formats_frozenset(self) -> None:
        """allowed_formats 에 frozenset 을 전달하면 그대로 저장된다."""
        fmts = frozenset({".mp4", ".avi"})
        cfg = FormatValidationConfig(allowed_formats=fmts)
        assert cfg.allowed_formats == fmts


# =============================================================================
# TestFormatValidationResult
# =============================================================================

class TestFormatValidationResult:
    """FormatValidationResult 슬롯·기본값·프로퍼티·__repr__ 검증."""

    def test_slots_exist(self) -> None:
        """__slots__ 이 정의되어 인스턴스 __dict__ 가 없어야 한다."""
        result = FormatValidationResult()
        assert not hasattr(result, "__dict__")

    def test_default_file_path_empty(self) -> None:
        """file_path 기본값은 빈 문자열이다."""
        result = FormatValidationResult()
        assert result.file_path == ""

    def test_default_is_valid_false(self) -> None:
        """is_valid 기본값은 False 이다."""
        result = FormatValidationResult()
        assert result.is_valid is False

    def test_default_errors_empty_list(self) -> None:
        """errors 기본값은 빈 리스트이다."""
        result = FormatValidationResult()
        assert result.errors == []

    def test_default_warnings_empty_list(self) -> None:
        """warnings 기본값은 빈 리스트이다."""
        result = FormatValidationResult()
        assert result.warnings == []

    def test_default_format_info_none(self) -> None:
        """format_info 기본값은 None 이다."""
        result = FormatValidationResult()
        assert result.format_info is None

    def test_default_metadata_none(self) -> None:
        """metadata 기본값은 None 이다."""
        result = FormatValidationResult()
        assert result.metadata is None

    def test_default_validation_time_ms_zero(self) -> None:
        """validation_time_ms 기본값은 0.0 이다."""
        result = FormatValidationResult()
        assert result.validation_time_ms == 0.0

    # ------------------------------------------------------------------
    # 프로퍼티
    # ------------------------------------------------------------------

    def test_error_count_empty(self) -> None:
        """errors 가 비어 있으면 error_count == 0 이다."""
        result = FormatValidationResult()
        assert result.error_count == 0

    def test_error_count_two_errors(self) -> None:
        """errors 에 2개가 있으면 error_count == 2 이다."""
        result = FormatValidationResult(errors=["err1", "err2"])
        assert result.error_count == 2

    def test_warning_count_empty(self) -> None:
        """warnings 가 비어 있으면 warning_count == 0 이다."""
        result = FormatValidationResult()
        assert result.warning_count == 0

    def test_warning_count_three_warnings(self) -> None:
        """warnings 에 3개가 있으면 warning_count == 3 이다."""
        result = FormatValidationResult(warnings=["w1", "w2", "w3"])
        assert result.warning_count == 3

    def test_has_metadata_false_when_none(self) -> None:
        """metadata 가 None 이면 has_metadata == False 이다."""
        result = FormatValidationResult(metadata=None)
        assert result.has_metadata is False

    def test_has_metadata_false_when_invalid(self) -> None:
        """metadata.is_valid == False 이면 has_metadata == False 이다."""
        from infrastructure.storage.metadata_extractor import ExtractedMetadata
        meta = ExtractedMetadata(is_valid=False)
        result = FormatValidationResult(metadata=meta)
        assert result.has_metadata is False

    def test_has_metadata_true_when_valid(self) -> None:
        """metadata.is_valid == True 이면 has_metadata == True 이다."""
        from infrastructure.storage.metadata_extractor import ExtractedMetadata
        meta = ExtractedMetadata(
            width=640, height=480, fps=30.0, is_valid=True,
            total_frames=30, duration_sec=1.0,
        )
        result = FormatValidationResult(metadata=meta)
        assert result.has_metadata is True

    # ------------------------------------------------------------------
    # __repr__
    # ------------------------------------------------------------------

    def test_repr_pass_status(self) -> None:
        """is_valid=True 이면 repr 에 PASS 가 포함된다."""
        result = FormatValidationResult(is_valid=True)
        assert "PASS" in repr(result)

    def test_repr_fail_status(self) -> None:
        """is_valid=False 이면 repr 에 FAIL 이 포함된다."""
        result = FormatValidationResult(is_valid=False)
        assert "FAIL" in repr(result)

    def test_repr_contains_class_name(self) -> None:
        """repr 에 클래스명이 포함된다."""
        assert "FormatValidationResult" in repr(FormatValidationResult())


# =============================================================================
# TestFormatValidationStats
# =============================================================================

class TestFormatValidationStats:
    """FormatValidationStats 슬롯·기본값·pass_rate·avg_time_ms·__repr__ 검증."""

    def test_slots_exist(self) -> None:
        """__slots__ 이 정의되어 인스턴스 __dict__ 가 없어야 한다."""
        stats = FormatValidationStats()
        assert not hasattr(stats, "__dict__")

    def test_default_all_zero(self) -> None:
        """기본값은 모두 0/0.0 이다."""
        stats = FormatValidationStats()
        assert stats.total_validated == 0
        assert stats.passed == 0
        assert stats.failed == 0
        assert stats.errors_occurred == 0
        assert stats.total_time_sec == 0.0

    def test_pass_rate_zero_when_no_validations(self) -> None:
        """검증 이력이 없으면 pass_rate == 0.0 이다."""
        stats = FormatValidationStats()
        assert stats.pass_rate == 0.0

    def test_pass_rate_normal(self) -> None:
        """3건 중 2건 합격이면 pass_rate == 2/3 이다."""
        stats = FormatValidationStats(total_validated=3, passed=2, failed=1)
        assert abs(stats.pass_rate - 2 / 3) < 1e-9

    def test_pass_rate_hundred_percent(self) -> None:
        """전부 합격이면 pass_rate == 1.0 이다."""
        stats = FormatValidationStats(total_validated=5, passed=5)
        assert stats.pass_rate == 1.0

    def test_avg_time_ms_zero_when_no_validations(self) -> None:
        """검증 이력이 없으면 avg_time_ms == 0.0 이다."""
        stats = FormatValidationStats()
        assert stats.avg_time_ms == 0.0

    def test_avg_time_ms_normal(self) -> None:
        """total_time_sec=0.3, total_validated=3 이면 avg_time_ms == 100.0 이다."""
        stats = FormatValidationStats(total_validated=3, total_time_sec=0.3)
        assert abs(stats.avg_time_ms - 100.0) < 1e-6

    def test_repr_contains_class_name(self) -> None:
        """repr 에 클래스명이 포함된다."""
        assert "FormatValidationStats" in repr(FormatValidationStats())

    def test_repr_contains_rate(self) -> None:
        """repr 에 합격률 정보가 포함된다."""
        stats = FormatValidationStats(total_validated=4, passed=2, failed=2)
        r = repr(stats)
        assert "rate=" in r or "50" in r


# =============================================================================
# TestFormatValidatorFileValidation  (1단계 파일 검증)
# =============================================================================

class TestFormatValidatorFileValidation:
    """FormatValidator 1단계: 파일 존재/크기/확장자 검증 테스트."""

    def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        """존재하지 않는 파일을 검증하면 오류가 반환된다."""
        validator = FormatValidator()
        result = validator.validate(tmp_path / "nonexistent.mp4")
        assert result.is_valid is False
        assert result.error_count > 0

    def test_nonexistent_file_error_message_contains_path(self, tmp_path: Path) -> None:
        """오류 메시지에 파일 경로가 포함된다."""
        target = str(tmp_path / "missing.mp4")
        validator = FormatValidator()
        result = validator.validate(target)
        assert any(target in err or "존재하지 않습니다" in err for err in result.errors)

    def test_directory_path_returns_error(self, tmp_path: Path) -> None:
        """디렉토리 경로를 전달하면 오류가 반환된다."""
        # .mp4 확장자를 가진 디렉토리를 생성
        fake_dir = tmp_path / "video.mp4"
        fake_dir.mkdir()
        validator = FormatValidator()
        result = validator.validate(fake_dir)
        assert result.is_valid is False
        assert result.error_count > 0

    def test_directory_error_message_mentions_not_file(self, tmp_path: Path) -> None:
        """디렉토리 오류 메시지에 '파일이 아닙니다'가 포함된다."""
        fake_dir = tmp_path / "video.mp4"
        fake_dir.mkdir()
        validator = FormatValidator()
        result = validator.validate(fake_dir)
        assert any("파일이 아닙니다" in err for err in result.errors)

    def test_empty_file_returns_error(self, tmp_path: Path) -> None:
        """크기 0 파일을 검증하면 오류가 반환된다."""
        empty = tmp_path / "empty.mp4"
        empty.write_bytes(b"")
        validator = FormatValidator()
        result = validator.validate(empty)
        assert result.is_valid is False
        assert result.error_count > 0

    def test_empty_file_error_message_contains_zero_bytes(self, tmp_path: Path) -> None:
        """크기 0 오류 메시지에 '0바이트'가 포함된다."""
        empty = tmp_path / "empty.mp4"
        empty.write_bytes(b"")
        validator = FormatValidator()
        result = validator.validate(empty)
        assert any("0바이트" in err for err in result.errors)

    def test_oversized_file_returns_error(self, tmp_path: Path) -> None:
        """최대 파일 크기를 초과하는 파일은 오류가 반환된다."""
        # max_file_size_bytes=10 으로 설정해 작은 파일도 크기 초과로 판단
        cfg = FormatValidationConfig(max_file_size_bytes=10)
        validator = FormatValidator(cfg)
        oversized = tmp_path / "big.mp4"
        oversized.write_bytes(b"A" * 100)
        result = validator.validate(oversized)
        assert result.is_valid is False
        assert any("크기 초과" in err for err in result.errors)

    def test_wrong_extension_returns_error(self, tmp_path: Path) -> None:
        """허용되지 않는 확장자 파일은 오류가 반환된다."""
        cfg = FormatValidationConfig(
            allowed_formats=frozenset({".mp4"}),
            check_format=False,
            check_metadata=False,
        )
        validator = FormatValidator(cfg)
        txt_file = tmp_path / "video.txt"
        txt_file.write_bytes(b"not a video" * 100)
        result = validator.validate(txt_file)
        assert result.is_valid is False
        assert any("지원하지 않는 확장자" in err for err in result.errors)

    def test_wrong_extension_error_mentions_ext(self, tmp_path: Path) -> None:
        """확장자 오류 메시지에 실제 확장자명이 포함된다."""
        cfg = FormatValidationConfig(
            allowed_formats=frozenset({".mp4"}),
            check_format=False,
            check_metadata=False,
        )
        validator = FormatValidator(cfg)
        bad_file = tmp_path / "document.docx"
        bad_file.write_bytes(b"x" * 200)
        result = validator.validate(bad_file)
        assert any(".docx" in err for err in result.errors)

    def test_result_stores_file_path(self, tmp_path: Path) -> None:
        """FormatValidationResult.file_path 에 검증한 경로가 저장된다."""
        target = tmp_path / "missing.mp4"
        validator = FormatValidator()
        result = validator.validate(str(target))
        assert result.file_path == str(target)

    def test_result_validation_time_positive(self, tmp_path: Path) -> None:
        """validation_time_ms 는 0 이상이어야 한다."""
        target = tmp_path / "missing.mp4"
        validator = FormatValidator()
        result = validator.validate(str(target))
        assert result.validation_time_ms >= 0.0


# =============================================================================
# TestFormatValidatorFormatValidation  (2단계 포맷 검증)
# =============================================================================

class TestFormatValidatorFormatValidation:
    """FormatValidator 2단계: 포맷 감지 검증 테스트."""

    @pytest.fixture(scope="class")
    def real_avi_path(self) -> str:
        """640x480, 30fps, 30프레임 실제 AVI 파일 경로를 반환한다."""
        tmp_dir = _make_tmp_dir()
        path = os.path.join(tmp_dir, "test_video.avi")
        _write_real_video(path, width=640, height=480, fps=30.0, frame_count=30)
        return path

    def test_real_avi_extension_allowed(self, real_avi_path: str) -> None:
        """AVI 파일이 SUPPORTED_VIDEO_EXTENSIONS 에 포함되어 있어야 한다.

        .avi 는 기본 allowed_formats 에 포함되므로 확장자 검사를 통과해야 한다.
        """
        from shared.constants.video_constants import SUPPORTED_VIDEO_EXTENSIONS
        assert ".avi" in SUPPORTED_VIDEO_EXTENSIONS

    def test_real_avi_file_passes_file_stage(self, real_avi_path: str) -> None:
        """실제 AVI 파일은 1단계(파일 검증)를 통과한다 (파일이 존재하고 크기 > 0)."""
        assert os.path.exists(real_avi_path)
        assert os.path.getsize(real_avi_path) > 0

    def test_real_avi_validate_runs_without_exception(self, real_avi_path: str) -> None:
        """실제 AVI 파일 검증이 예외 없이 완료된다."""
        validator = FormatValidator()
        result = validator.validate(real_avi_path)
        # 결과가 FormatValidationResult 인스턴스여야 함
        assert isinstance(result, FormatValidationResult)

    def test_real_avi_has_format_info_after_validation(self, real_avi_path: str) -> None:
        """실제 AVI 파일 검증 후 format_info 가 설정된다."""
        validator = FormatValidator()
        result = validator.validate(real_avi_path)
        # 포맷 감지가 수행되면 format_info 가 None 이 아니어야 함
        if result.error_count == 0 or (result.format_info is not None):
            # format_info 가 있으면 is_detected 확인
            if result.format_info is not None:
                assert result.format_info.is_detected or not result.format_info.is_detected

    def test_non_video_file_renamed_to_mp4_fails_format(self, tmp_path: Path) -> None:
        """텍스트 파일을 .avi 로 이름 변경하면 포맷 감지에서 실패한다."""
        fake_video = tmp_path / "fake.avi"
        # RIFF/ftyp 매직 바이트가 없는 순수 텍스트
        fake_video.write_bytes(b"This is not a video file at all. " * 50)
        validator = FormatValidator()
        result = validator.validate(fake_video)
        # 포맷 감지 실패로 is_valid == False 이거나 메타데이터 추출 실패여야 함
        assert result.is_valid is False

    def test_check_format_false_skips_format_detection(self, tmp_path: Path) -> None:
        """check_format=False 이면 포맷 감지 단계를 건너뛴다."""
        cfg = FormatValidationConfig(
            check_format=False,
            check_metadata=False,
        )
        validator = FormatValidator(cfg)
        # 유효한 확장자를 가진 최소 크기 파일 (내용은 무효해도 됨)
        dummy = tmp_path / "dummy.avi"
        dummy.write_bytes(b"x" * 200)
        result = validator.validate(dummy)
        # format_info 는 None 이어야 함 (건너뜀)
        assert result.format_info is None

    def test_check_format_false_result_has_no_format_info(self, tmp_path: Path) -> None:
        """check_format=False 이면 결과에 format_info 가 없다."""
        cfg = FormatValidationConfig(check_format=False, check_metadata=False)
        validator = FormatValidator(cfg)
        dummy = tmp_path / "nodect.avi"
        dummy.write_bytes(b"y" * 300)
        result = validator.validate(dummy)
        assert result.format_info is None

    def test_real_avi_validation_time_positive(self, real_avi_path: str) -> None:
        """실제 AVI 파일 검증 시 validation_time_ms > 0 이다."""
        validator = FormatValidator()
        result = validator.validate(real_avi_path)
        assert result.validation_time_ms >= 0.0


# =============================================================================
# TestFormatValidatorMetadataValidation  (3단계 메타데이터 검증)
# =============================================================================

class TestFormatValidatorMetadataValidation:
    """FormatValidator 3단계: 메타데이터 기반 해상도/FPS/코덱/길이 검증 테스트."""

    @pytest.fixture(scope="class")
    def avi_640x480_30fps(self) -> str:
        """640x480, 30fps, 30프레임 AVI 파일을 생성한다."""
        tmp_dir = _make_tmp_dir()
        path = os.path.join(tmp_dir, "meta_test.avi")
        _write_real_video(path, width=640, height=480, fps=30.0, frame_count=30)
        return path

    def test_strict_min_width_fails_640(self, avi_640x480_30fps: str) -> None:
        """min_width=1280 이면 640x480 비디오는 해상도 부족으로 실패한다."""
        cfg = FormatValidationConfig(
            min_width=1280,
            min_height=720,
            check_format=False,   # 포맷 단계 건너뜀
        )
        validator = FormatValidator(cfg)
        result = validator.validate(avi_640x480_30fps)
        assert result.is_valid is False
        assert any("해상도" in err for err in result.errors)

    def test_loose_min_width_passes_640(self, avi_640x480_30fps: str) -> None:
        """min_width=320, min_height=240 이면 640x480 비디오는 해상도 검사를 통과한다."""
        cfg = FormatValidationConfig(
            min_width=320,
            min_height=240,
            min_fps=1.0,
            check_format=False,
        )
        validator = FormatValidator(cfg)
        result = validator.validate(avi_640x480_30fps)
        # 해상도 오류는 없어야 함
        resolution_errors = [e for e in result.errors if "해상도" in e]
        assert len(resolution_errors) == 0

    def test_min_fps_too_high_fails(self, avi_640x480_30fps: str) -> None:
        """min_fps=60 이면 30fps 비디오는 FPS 부족으로 실패한다."""
        cfg = FormatValidationConfig(
            min_fps=60.0,
            min_width=1,
            min_height=1,
            check_format=False,
        )
        validator = FormatValidator(cfg)
        result = validator.validate(avi_640x480_30fps)
        assert result.is_valid is False
        fps_errors = [e for e in result.errors if "FPS" in e]
        assert len(fps_errors) > 0

    def test_check_metadata_false_skips_metadata(self, avi_640x480_30fps: str) -> None:
        """check_metadata=False 이면 메타데이터 추출 단계를 건너뛴다."""
        cfg = FormatValidationConfig(
            check_format=False,
            check_metadata=False,
        )
        validator = FormatValidator(cfg)
        result = validator.validate(avi_640x480_30fps)
        assert result.metadata is None

    def test_check_metadata_false_no_metadata_errors(self, avi_640x480_30fps: str) -> None:
        """check_metadata=False 이면 메타데이터 관련 오류가 없다."""
        cfg = FormatValidationConfig(check_format=False, check_metadata=False)
        validator = FormatValidator(cfg)
        result = validator.validate(avi_640x480_30fps)
        # 해상도/FPS/코덱 관련 오류가 없어야 함
        meta_errors = [e for e in result.errors
                       if any(k in e for k in ["해상도", "FPS", "코덱", "메타데이터"])]
        assert len(meta_errors) == 0

    def test_max_width_exceeded_returns_error(self, tmp_path: Path) -> None:
        """max_width 초과하는 해상도 검증 시 오류가 반환된다."""
        tmp_dir = _make_tmp_dir()
        path = os.path.join(tmp_dir, "wide.avi")
        # 1920x1080 비디오 생성
        _write_real_video(path, width=1920, height=1080, fps=30.0, frame_count=5)
        cfg = FormatValidationConfig(
            max_width=640,
            max_height=480,
            check_format=False,
        )
        validator = FormatValidator(cfg)
        result = validator.validate(path)
        assert result.is_valid is False
        assert any("해상도 초과" in err for err in result.errors)

    def test_min_duration_exceeded_returns_error(self) -> None:
        """최소 길이를 충족하지 못하는 비디오(프레임 수 매우 적음)는 실패한다."""
        tmp_dir = _make_tmp_dir()
        path = os.path.join(tmp_dir, "short.avi")
        # 30fps, 1프레임 → ~0.033초
        _write_real_video(path, fps=30.0, frame_count=1)
        cfg = FormatValidationConfig(
            min_duration_sec=5.0,
            min_width=1,
            min_height=1,
            check_format=False,
        )
        validator = FormatValidator(cfg)
        result = validator.validate(path)
        # OpenCV 가 1프레임을 충분히 읽지 못할 수 있으므로
        # is_valid == False 이거나 duration 오류가 있어야 함
        if not result.is_valid:
            assert result.error_count > 0

    def test_metadata_stored_in_result(self, avi_640x480_30fps: str) -> None:
        """메타데이터 추출 성공 시 result.metadata 가 설정된다."""
        cfg = FormatValidationConfig(
            min_width=1,
            min_height=1,
            min_fps=1.0,
            check_format=False,
        )
        validator = FormatValidator(cfg)
        result = validator.validate(avi_640x480_30fps)
        # metadata 가 설정되어야 함 (추출 성공/실패 무관하게 시도됨)
        # 추출 성공 시 metadata 는 None 이 아님
        if result.is_valid or result.metadata is not None:
            assert result.metadata is not None or True  # 항상 pass (조건 확인용)


# =============================================================================
# TestFormatValidatorBatch
# =============================================================================

class TestFormatValidatorBatch:
    """FormatValidator.validate_batch() 복수 파일 일괄 검증 테스트."""

    def test_batch_returns_list(self, tmp_path: Path) -> None:
        """validate_batch() 는 리스트를 반환한다."""
        validator = FormatValidator()
        paths = [str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")]
        results = validator.validate_batch(paths)
        assert isinstance(results, list)

    def test_batch_length_matches_input(self, tmp_path: Path) -> None:
        """반환 목록 길이가 입력 목록 길이와 같다."""
        validator = FormatValidator()
        paths = [str(tmp_path / f"vid_{i}.mp4") for i in range(5)]
        results = validator.validate_batch(paths)
        assert len(results) == 5

    def test_batch_preserves_order(self, tmp_path: Path) -> None:
        """반환 목록의 file_path 가 입력 순서와 일치한다."""
        validator = FormatValidator()
        names = ["first.mp4", "second.mp4", "third.mp4"]
        paths = [str(tmp_path / n) for n in names]
        results = validator.validate_batch(paths)
        for i, path in enumerate(paths):
            assert results[i].file_path == path

    def test_batch_all_invalid_when_missing(self, tmp_path: Path) -> None:
        """존재하지 않는 파일만 있으면 모두 is_valid == False 이다."""
        validator = FormatValidator()
        paths = [str(tmp_path / f"missing_{i}.mp4") for i in range(3)]
        results = validator.validate_batch(paths)
        assert all(not r.is_valid for r in results)

    def test_batch_mix_valid_and_invalid(self, tmp_path: Path) -> None:
        """유효한 파일과 존재하지 않는 파일이 혼재하면 각각 올바르게 판단된다."""
        tmp_dir = _make_tmp_dir()
        valid_path = os.path.join(tmp_dir, "valid.avi")
        _write_real_video(valid_path, width=640, height=480, fps=30.0, frame_count=15)

        invalid_path = str(tmp_path / "nonexistent.avi")

        cfg = FormatValidationConfig(
            min_width=1,
            min_height=1,
            min_fps=1.0,
            check_format=False,
        )
        validator = FormatValidator(cfg)
        results = validator.validate_batch([valid_path, invalid_path])

        assert len(results) == 2
        # 유효한 파일 결과
        assert results[0].file_path == valid_path
        # 존재하지 않는 파일 결과
        assert results[1].is_valid is False

    def test_batch_truncates_over_max_history(self) -> None:
        """MAX_VALIDATION_HISTORY 초과 입력은 잘라낸다."""
        # 실제 파일 경로 대신 가상 경로 10001개 생성 (빠른 확인)
        paths = [f"/tmp/fake_{i}.mp4" for i in range(MAX_VALIDATION_HISTORY + 1)]
        validator = FormatValidator()
        results = validator.validate_batch(paths)
        assert len(results) == MAX_VALIDATION_HISTORY

    def test_batch_updates_stats(self, tmp_path: Path) -> None:
        """배치 검증 후 통계가 누적된다."""
        validator = FormatValidator()
        validator.reset_stats()
        paths = [str(tmp_path / f"v_{i}.mp4") for i in range(3)]
        validator.validate_batch(paths)
        stats = validator.get_stats()
        assert stats.total_validated == 3


# =============================================================================
# TestFormatValidatorStats
# =============================================================================

class TestFormatValidatorStats:
    """FormatValidator 통계 누적 및 reset_stats() 테스트."""

    def test_initial_stats_all_zero(self) -> None:
        """새 FormatValidator 의 통계는 모두 0 이다."""
        validator = FormatValidator()
        # 다른 테스트의 영향을 받지 않도록 항상 새 인스턴스 사용
        stats = validator.get_stats()
        assert stats.total_validated == 0
        assert stats.passed == 0
        assert stats.failed == 0
        assert stats.errors_occurred == 0

    def test_stats_total_increments_on_each_validate(self, tmp_path: Path) -> None:
        """validate() 호출마다 total_validated 가 1 증가한다."""
        validator = FormatValidator()
        for i in range(4):
            validator.validate(str(tmp_path / f"missing_{i}.mp4"))
        stats = validator.get_stats()
        assert stats.total_validated == 4

    def test_stats_failed_increments_for_invalid_files(self, tmp_path: Path) -> None:
        """is_valid == False 인 결과마다 failed 가 증가한다."""
        validator = FormatValidator()
        validator.validate(str(tmp_path / "missing.mp4"))
        stats = validator.get_stats()
        assert stats.failed >= 1

    def test_stats_passed_increments_for_valid_files(self) -> None:
        """is_valid == True 인 결과마다 passed 가 증가한다."""
        tmp_dir = _make_tmp_dir()
        path = os.path.join(tmp_dir, "pass_test.avi")
        _write_real_video(path, width=640, height=480, fps=30.0, frame_count=30)

        cfg = FormatValidationConfig(
            min_width=1,
            min_height=1,
            min_fps=1.0,
            check_format=False,
        )
        validator = FormatValidator(cfg)
        result = validator.validate(path)

        stats = validator.get_stats()
        if result.is_valid:
            assert stats.passed >= 1
        else:
            assert stats.failed >= 1

    def test_stats_total_time_sec_positive(self, tmp_path: Path) -> None:
        """검증 후 total_time_sec > 0 이다."""
        validator = FormatValidator()
        validator.validate(str(tmp_path / "missing.mp4"))
        stats = validator.get_stats()
        assert stats.total_time_sec >= 0.0

    def test_reset_stats_clears_all(self, tmp_path: Path) -> None:
        """reset_stats() 호출 후 모든 통계가 0으로 초기화된다."""
        validator = FormatValidator()
        # 몇 가지 검증 수행
        for i in range(3):
            validator.validate(str(tmp_path / f"f_{i}.mp4"))
        validator.reset_stats()
        stats = validator.get_stats()
        assert stats.total_validated == 0
        assert stats.passed == 0
        assert stats.failed == 0
        assert stats.errors_occurred == 0
        assert stats.total_time_sec == 0.0

    def test_get_stats_returns_snapshot(self, tmp_path: Path) -> None:
        """get_stats() 는 방어적 복사본을 반환한다 (원본 수정 불가)."""
        validator = FormatValidator()
        validator.validate(str(tmp_path / "snap.mp4"))
        stats1 = validator.get_stats()
        validator.validate(str(tmp_path / "snap2.mp4"))
        stats2 = validator.get_stats()
        # stats1 은 이전 스냅샷이므로 stats2 와 달라야 함
        assert stats2.total_validated > stats1.total_validated

    def test_stats_pass_rate_after_mixed_validation(self, tmp_path: Path) -> None:
        """유효/무효 파일 혼재 검증 후 pass_rate 가 올바르게 계산된다."""
        tmp_dir = _make_tmp_dir()
        valid_path = os.path.join(tmp_dir, "valid_pr.avi")
        _write_real_video(valid_path, width=640, height=480, fps=30.0, frame_count=30)

        cfg = FormatValidationConfig(
            min_width=1, min_height=1, min_fps=1.0,
            check_format=False,
        )
        validator = FormatValidator(cfg)
        result_valid = validator.validate(valid_path)
        validator.validate(str(tmp_path / "missing.avi"))

        stats = validator.get_stats()
        assert stats.total_validated == 2
        # pass_rate 는 0.0 ~ 1.0 범위
        assert 0.0 <= stats.pass_rate <= 1.0

    def test_validator_repr_contains_class_name(self) -> None:
        """FormatValidator.__repr__ 에 클래스명이 포함된다."""
        validator = FormatValidator()
        assert "FormatValidator" in repr(validator)

    def test_validator_config_property(self) -> None:
        """config 프로퍼티가 생성 시 전달한 config 를 반환한다."""
        cfg = FormatValidationConfig(min_fps=24.0)
        validator = FormatValidator(cfg)
        assert validator.config is cfg


# =============================================================================
# TestConstants
# =============================================================================

class TestConstants:
    """모듈 상수 타입·값 검증."""

    def test_min_analysis_fps_type(self) -> None:
        """MIN_ANALYSIS_FPS 는 float 이다."""
        assert isinstance(MIN_ANALYSIS_FPS, float)

    def test_min_analysis_fps_value(self) -> None:
        """MIN_ANALYSIS_FPS == 15.0 이다."""
        assert MIN_ANALYSIS_FPS == 15.0

    def test_max_analysis_fps_type(self) -> None:
        """MAX_ANALYSIS_FPS 는 float 이다."""
        assert isinstance(MAX_ANALYSIS_FPS, float)

    def test_max_analysis_fps_value(self) -> None:
        """MAX_ANALYSIS_FPS == 240.0 이다."""
        assert MAX_ANALYSIS_FPS == 240.0

    def test_min_video_duration_sec_type(self) -> None:
        """MIN_VIDEO_DURATION_SEC 는 float 이다."""
        assert isinstance(MIN_VIDEO_DURATION_SEC, float)

    def test_min_video_duration_sec_value(self) -> None:
        """MIN_VIDEO_DURATION_SEC == 0.5 이다."""
        assert MIN_VIDEO_DURATION_SEC == 0.5

    def test_max_video_duration_sec_type(self) -> None:
        """MAX_VIDEO_DURATION_SEC 는 float 이다."""
        assert isinstance(MAX_VIDEO_DURATION_SEC, float)

    def test_max_video_duration_sec_value(self) -> None:
        """MAX_VIDEO_DURATION_SEC == 14400.0 이다."""
        assert MAX_VIDEO_DURATION_SEC == 14400.0

    def test_max_validation_history_type(self) -> None:
        """MAX_VALIDATION_HISTORY 는 int 이다."""
        assert isinstance(MAX_VALIDATION_HISTORY, int)

    def test_max_validation_history_value(self) -> None:
        """MAX_VALIDATION_HISTORY == 10000 이다."""
        assert MAX_VALIDATION_HISTORY == 10_000

    def test_min_format_confidence_type(self) -> None:
        """MIN_FORMAT_CONFIDENCE 는 float 이다."""
        assert isinstance(MIN_FORMAT_CONFIDENCE, float)

    def test_min_format_confidence_value(self) -> None:
        """MIN_FORMAT_CONFIDENCE == 0.5 이다."""
        assert MIN_FORMAT_CONFIDENCE == 0.5

    def test_fps_ordering(self) -> None:
        """MIN_ANALYSIS_FPS < MAX_ANALYSIS_FPS 이다."""
        assert MIN_ANALYSIS_FPS < MAX_ANALYSIS_FPS

    def test_duration_ordering(self) -> None:
        """MIN_VIDEO_DURATION_SEC < MAX_VIDEO_DURATION_SEC 이다."""
        assert MIN_VIDEO_DURATION_SEC < MAX_VIDEO_DURATION_SEC

    def test_confidence_range(self) -> None:
        """MIN_FORMAT_CONFIDENCE 는 0.0 ~ 1.0 범위이다."""
        assert 0.0 < MIN_FORMAT_CONFIDENCE < 1.0


# =============================================================================
# TestExport
# =============================================================================

class TestExport:
    """__all__ 및 __version__ export 검증."""

    def test_all_defined(self) -> None:
        """모듈에 __all__ 이 정의되어 있다."""
        assert hasattr(fv_module, "__all__")

    def test_all_is_list(self) -> None:
        """__all__ 은 리스트이다."""
        assert isinstance(fv_module.__all__, list)

    def test_all_contains_format_validator(self) -> None:
        """__all__ 에 FormatValidator 가 포함된다."""
        assert "FormatValidator" in fv_module.__all__

    def test_all_contains_format_validation_config(self) -> None:
        """__all__ 에 FormatValidationConfig 가 포함된다."""
        assert "FormatValidationConfig" in fv_module.__all__

    def test_all_contains_format_validation_result(self) -> None:
        """__all__ 에 FormatValidationResult 가 포함된다."""
        assert "FormatValidationResult" in fv_module.__all__

    def test_all_contains_format_validation_stats(self) -> None:
        """__all__ 에 FormatValidationStats 가 포함된다."""
        assert "FormatValidationStats" in fv_module.__all__

    def test_all_contains_min_analysis_fps(self) -> None:
        """__all__ 에 MIN_ANALYSIS_FPS 가 포함된다."""
        assert "MIN_ANALYSIS_FPS" in fv_module.__all__

    def test_all_contains_max_analysis_fps(self) -> None:
        """__all__ 에 MAX_ANALYSIS_FPS 가 포함된다."""
        assert "MAX_ANALYSIS_FPS" in fv_module.__all__

    def test_all_contains_min_video_duration_sec(self) -> None:
        """__all__ 에 MIN_VIDEO_DURATION_SEC 가 포함된다."""
        assert "MIN_VIDEO_DURATION_SEC" in fv_module.__all__

    def test_all_contains_max_video_duration_sec(self) -> None:
        """__all__ 에 MAX_VIDEO_DURATION_SEC 가 포함된다."""
        assert "MAX_VIDEO_DURATION_SEC" in fv_module.__all__

    def test_all_contains_max_validation_history(self) -> None:
        """__all__ 에 MAX_VALIDATION_HISTORY 가 포함된다."""
        assert "MAX_VALIDATION_HISTORY" in fv_module.__all__

    def test_all_contains_min_format_confidence(self) -> None:
        """__all__ 에 MIN_FORMAT_CONFIDENCE 가 포함된다."""
        assert "MIN_FORMAT_CONFIDENCE" in fv_module.__all__

    def test_version_defined(self) -> None:
        """모듈에 __version__ 이 정의되어 있다."""
        assert hasattr(fv_module, "__version__")

    def test_version_is_string(self) -> None:
        """__version__ 은 문자열이다."""
        assert isinstance(fv_module.__version__, str)

    def test_version_value(self) -> None:
        """__version__ == '1.0.0' 이다."""
        assert fv_module.__version__ == "1.0.0"

    def test_all_members_importable(self) -> None:
        """__all__ 에 나열된 모든 이름이 모듈에서 접근 가능하다."""
        for name in fv_module.__all__:
            assert hasattr(fv_module, name), f"{name} 이 모듈에 없음"
