# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/validation
파일: format_validator.py
설명: 비디오 파일 포맷 종합 검증
      - FormatValidationConfig: 검증 규칙 설정 (허용 포맷/코덱/해상도/FPS/길이/크기)
      - FormatValidationResult: 검증 결과 (합격/실패/항목별 상세)
      - FormatValidator: 비디오 파일의 포맷·메타데이터 종합 검증
      - FormatValidationStats: 검증 통계 (합격/실패/에러 집계)
      - 3단계 검증: 파일 존재 → 포맷 감지 → 메타데이터 검증

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.video_constants import (
    MAX_VIDEO_BITRATE_BPS,
    MAX_VIDEO_FILE_SIZE_BYTES,
    MAX_VIDEO_HEIGHT,
    MAX_VIDEO_WIDTH,
    MIN_VIDEO_BITRATE_BPS,
    MIN_VIDEO_HEIGHT,
    MIN_VIDEO_WIDTH,
    SUPPORTED_VIDEO_CODECS,
    SUPPORTED_VIDEO_EXTENSIONS,
)

from infrastructure.storage.format_detector import FormatDetector, FormatInfo
from infrastructure.storage.metadata_extractor import ExtractedMetadata, MetadataExtractor


# =============================================================================
# 상수 정의
# =============================================================================

# 최소 FPS (분석 최저 기준)
MIN_ANALYSIS_FPS: Final[float] = 15.0

# 최대 FPS (슬로모션 상한)
MAX_ANALYSIS_FPS: Final[float] = 240.0

# 최소 비디오 길이 (초) — 분석 가능 최저 기준
MIN_VIDEO_DURATION_SEC: Final[float] = 0.5

# 최대 비디오 길이 (초) — 4시간
MAX_VIDEO_DURATION_SEC: Final[float] = 14400.0

# 최대 검증 이력 (무한 성장 방지)
MAX_VALIDATION_HISTORY: Final[int] = 10_000

# 포맷 감지 최소 신뢰도 (이 미만이면 검증 실패)
MIN_FORMAT_CONFIDENCE: Final[float] = 0.5


# =============================================================================
# FormatValidationConfig: 검증 규칙 설정
# =============================================================================

@dataclass(slots=True)
class FormatValidationConfig:
    """비디오 포맷 검증 규칙 설정.

    Attributes:
        allowed_formats: 허용 비디오 포맷 (None이면 SUPPORTED_VIDEO_EXTENSIONS 전부 허용)
        allowed_codecs: 허용 코덱 (None이면 SUPPORTED_VIDEO_CODECS 전부 허용)
        min_width: 최소 가로 해상도
        max_width: 최대 가로 해상도
        min_height: 최소 세로 해상도
        max_height: 최대 세로 해상도
        min_fps: 최소 FPS
        max_fps: 최대 FPS
        min_duration_sec: 최소 영상 길이 (초)
        max_duration_sec: 최대 영상 길이 (초)
        max_file_size_bytes: 최대 파일 크기 (바이트)
        min_bitrate_bps: 최소 비트레이트 (bps)
        max_bitrate_bps: 최대 비트레이트 (bps)
        check_format: 포맷 감지 검증 수행 여부
        check_metadata: 메타데이터 검증 수행 여부
        strict_codec_check: 엄격한 코덱 검증 (False면 코덱 미감지 시 통과)
    """

    allowed_formats: frozenset[str] | None = None
    allowed_codecs: frozenset[str] | None = None
    min_width: int = MIN_VIDEO_WIDTH
    max_width: int = MAX_VIDEO_WIDTH
    min_height: int = MIN_VIDEO_HEIGHT
    max_height: int = MAX_VIDEO_HEIGHT
    min_fps: float = MIN_ANALYSIS_FPS
    max_fps: float = MAX_ANALYSIS_FPS
    min_duration_sec: float = MIN_VIDEO_DURATION_SEC
    max_duration_sec: float = MAX_VIDEO_DURATION_SEC
    max_file_size_bytes: int = MAX_VIDEO_FILE_SIZE_BYTES
    min_bitrate_bps: int = MIN_VIDEO_BITRATE_BPS
    max_bitrate_bps: int = MAX_VIDEO_BITRATE_BPS
    check_format: bool = True
    check_metadata: bool = True
    strict_codec_check: bool = False

    def __post_init__(self) -> None:
        """범위 검증 및 클램핑."""
        # 해상도 범위 보정
        if self.min_width < 1:
            self.min_width = 1
        if self.min_height < 1:
            self.min_height = 1
        if self.max_width < self.min_width:
            self.max_width = self.min_width
        if self.max_height < self.min_height:
            self.max_height = self.min_height

        # FPS 범위 보정
        if self.min_fps < 1.0:
            self.min_fps = 1.0
        if self.max_fps < self.min_fps:
            self.max_fps = self.min_fps

        # 길이 범위 보정
        if self.min_duration_sec < 0.0:
            self.min_duration_sec = 0.0
        if self.max_duration_sec < self.min_duration_sec:
            self.max_duration_sec = self.min_duration_sec

        # 파일 크기 보정
        if self.max_file_size_bytes < 1:
            self.max_file_size_bytes = 1

        # 비트레이트 보정
        if self.min_bitrate_bps < 0:
            self.min_bitrate_bps = 0
        if self.max_bitrate_bps < self.min_bitrate_bps:
            self.max_bitrate_bps = self.min_bitrate_bps

    def __repr__(self) -> str:
        return (
            f"FormatValidationConfig("
            f"res={self.min_width}x{self.min_height}~{self.max_width}x{self.max_height}, "
            f"fps={self.min_fps:.0f}~{self.max_fps:.0f}, "
            f"dur={self.min_duration_sec:.1f}~{self.max_duration_sec:.1f}s)"
        )


# =============================================================================
# FormatValidationResult: 검증 결과
# =============================================================================

@dataclass(slots=True)
class FormatValidationResult:
    """비디오 포맷 검증 결과.

    Attributes:
        file_path: 검증한 파일 경로
        is_valid: 종합 합격 여부
        errors: 검증 실패 항목 목록
        warnings: 경고 항목 목록
        format_info: 포맷 감지 결과 (있는 경우)
        metadata: 메타데이터 추출 결과 (있는 경우)
        validation_time_ms: 검증 소요 시간 (밀리초)
    """

    file_path: str = ""
    is_valid: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    format_info: FormatInfo | None = None
    metadata: ExtractedMetadata | None = None
    validation_time_ms: float = 0.0

    @property
    def error_count(self) -> int:
        """검증 오류 수."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """경고 수."""
        return len(self.warnings)

    @property
    def has_metadata(self) -> bool:
        """메타데이터 포함 여부."""
        return self.metadata is not None and self.metadata.is_valid

    def __repr__(self) -> str:
        status = "PASS" if self.is_valid else "FAIL"
        return (
            f"FormatValidationResult("
            f"file='{self.file_path}', "
            f"status={status}, "
            f"errors={self.error_count}, "
            f"warnings={self.warning_count}, "
            f"time={self.validation_time_ms:.1f}ms)"
        )


# =============================================================================
# FormatValidationStats: 검증 통계
# =============================================================================

@dataclass(slots=True)
class FormatValidationStats:
    """포맷 검증 통계.

    Attributes:
        total_validated: 총 검증 파일 수
        passed: 합격 수
        failed: 실패 수
        errors_occurred: 검증 중 에러 발생 수 (파일 접근 실패 등)
        total_time_sec: 총 소요 시간 (초)
    """

    total_validated: int = 0
    passed: int = 0
    failed: int = 0
    errors_occurred: int = 0
    total_time_sec: float = 0.0

    @property
    def pass_rate(self) -> float:
        """합격률 (0.0 ~ 1.0)."""
        if self.total_validated == 0:
            return 0.0
        return self.passed / self.total_validated

    @property
    def avg_time_ms(self) -> float:
        """파일당 평균 검증 시간 (밀리초)."""
        if self.total_validated == 0:
            return 0.0
        return (self.total_time_sec / self.total_validated) * 1000.0

    def __repr__(self) -> str:
        return (
            f"FormatValidationStats("
            f"total={self.total_validated}, "
            f"passed={self.passed}, "
            f"failed={self.failed}, "
            f"rate={self.pass_rate:.1%}, "
            f"avg={self.avg_time_ms:.1f}ms)"
        )


# =============================================================================
# FormatValidator: 비디오 포맷 종합 검증기
# =============================================================================

class FormatValidator:
    """비디오 파일 포맷 종합 검증기.

    3단계 검증 파이프라인:
    1. 파일 존재/크기/확장자 확인
    2. 매직 바이트 기반 포맷 감지 (FormatDetector 활용)
    3. 메타데이터 기반 검증 — 해상도/FPS/코덱/길이/비트레이트 (MetadataExtractor 활용)

    사용 예시::

        config = FormatValidationConfig(min_fps=24.0, min_width=1280, min_height=720)
        validator = FormatValidator(config)
        result = validator.validate("game_video.mp4")
        if result.is_valid:
            print("검증 통과")
        else:
            for err in result.errors:
                print(f"실패: {err}")
    """

    __slots__ = (
        "_config",
        "_format_detector",
        "_metadata_extractor",
        "_stats",
        "_lock",
    )

    def __init__(
        self,
        config: FormatValidationConfig | None = None,
    ) -> None:
        """포맷 검증기 초기화.

        Args:
            config: 검증 규칙 설정 (None이면 기본값)
        """
        self._config: FormatValidationConfig = config or FormatValidationConfig()
        self._format_detector: FormatDetector = FormatDetector()
        self._metadata_extractor: MetadataExtractor = MetadataExtractor()
        self._stats: FormatValidationStats = FormatValidationStats()
        self._lock: threading.RLock = threading.RLock()

    # -------------------------------------------------------------------------
    # 공개 API
    # -------------------------------------------------------------------------

    def validate(self, file_path: str | Path) -> FormatValidationResult:
        """비디오 파일 종합 검증.

        3단계 파이프라인을 순차 실행하고, 첫 실패에서 중단하지 않고
        모든 항목을 검사하여 전체 오류 목록을 반환한다.

        Args:
            file_path: 검증할 파일 경로

        Returns:
            FormatValidationResult — 합격 여부, 오류/경고 목록, 메타데이터
        """
        t0 = time.monotonic()
        path = Path(file_path)
        result = FormatValidationResult(file_path=str(path))

        try:
            # 1단계: 파일 존재/크기/확장자
            self._validate_file(path, result)

            # 2단계: 포맷 감지 (1단계 통과 시에만)
            if result.error_count == 0 and self._config.check_format:
                self._validate_format(path, result)

            # 3단계: 메타데이터 검증 (1~2단계 통과 시에만)
            if result.error_count == 0 and self._config.check_metadata:
                self._validate_metadata(path, result)

            # 최종 판정
            result.is_valid = result.error_count == 0

        except Exception as exc:
            result.errors.append(f"검증 중 예외 발생: {exc!s}")
            result.is_valid = False
            with self._lock:
                self._stats.errors_occurred += 1

        elapsed_ms = (time.monotonic() - t0) * 1000.0
        result.validation_time_ms = elapsed_ms

        # 통계 갱신
        with self._lock:
            self._stats.total_validated += 1
            self._stats.total_time_sec += elapsed_ms / 1000.0
            if result.is_valid:
                self._stats.passed += 1
            else:
                self._stats.failed += 1

        return result

    def validate_batch(
        self,
        file_paths: list[str | Path],
    ) -> list[FormatValidationResult]:
        """복수 파일 일괄 검증.

        Args:
            file_paths: 검증할 파일 경로 목록

        Returns:
            검증 결과 목록 (입력 순서 유지)
        """
        if len(file_paths) > MAX_VALIDATION_HISTORY:
            file_paths = file_paths[:MAX_VALIDATION_HISTORY]

        return [self.validate(fp) for fp in file_paths]

    def get_stats(self) -> FormatValidationStats:
        """검증 통계 조회 (방어적 복사).

        Returns:
            현재 통계 스냅샷
        """
        with self._lock:
            return FormatValidationStats(
                total_validated=self._stats.total_validated,
                passed=self._stats.passed,
                failed=self._stats.failed,
                errors_occurred=self._stats.errors_occurred,
                total_time_sec=self._stats.total_time_sec,
            )

    def reset_stats(self) -> None:
        """통계 초기화."""
        with self._lock:
            self._stats = FormatValidationStats()

    @property
    def config(self) -> FormatValidationConfig:
        """현재 검증 설정."""
        return self._config

    # -------------------------------------------------------------------------
    # 1단계: 파일 존재/크기/확장자 검증
    # -------------------------------------------------------------------------

    def _validate_file(
        self,
        path: Path,
        result: FormatValidationResult,
    ) -> None:
        """파일 기본 검증."""
        # 파일 존재 확인
        if not path.exists():
            result.errors.append(f"파일이 존재하지 않습니다: {path}")
            return

        if not path.is_file():
            result.errors.append(f"파일이 아닙니다 (디렉토리 또는 특수 파일): {path}")
            return

        # 파일 크기 확인
        try:
            file_size = path.stat().st_size
        except OSError as exc:
            result.errors.append(f"파일 크기 확인 실패: {exc}")
            return

        if file_size == 0:
            result.errors.append("파일 크기가 0바이트입니다")
            return

        if file_size > self._config.max_file_size_bytes:
            size_mb = file_size / (1024 * 1024)
            max_mb = self._config.max_file_size_bytes / (1024 * 1024)
            result.errors.append(
                f"파일 크기 초과: {size_mb:.1f}MB (최대: {max_mb:.1f}MB)"
            )

        # 확장자 확인
        ext = path.suffix.lower()
        allowed_exts = self._config.allowed_formats or SUPPORTED_VIDEO_EXTENSIONS
        if ext not in allowed_exts:
            allowed_str = ", ".join(sorted(allowed_exts)[:6])
            result.errors.append(
                f"지원하지 않는 확장자: '{ext}' (허용: {allowed_str})"
            )

    # -------------------------------------------------------------------------
    # 2단계: 포맷 감지 검증
    # -------------------------------------------------------------------------

    def _validate_format(
        self,
        path: Path,
        result: FormatValidationResult,
    ) -> None:
        """매직 바이트 기반 포맷 감지 검증."""
        try:
            format_info: FormatInfo = self._format_detector.detect(str(path))
        except Exception as exc:
            result.errors.append(f"포맷 감지 실패: {exc!s}")
            return

        result.format_info = format_info

        # 감지 실패
        if not format_info.is_detected:
            result.errors.append("파일 포맷을 감지할 수 없습니다")
            return

        # 비디오 포맷 여부
        if not format_info.is_video:
            result.errors.append(
                f"비디오 파일이 아닙니다: 감지된 포맷 '{format_info.detected_format}' "
                f"(MIME: {format_info.mime_type})"
            )
            return

        # 신뢰도 확인
        if format_info.confidence < MIN_FORMAT_CONFIDENCE:
            result.warnings.append(
                f"포맷 감지 신뢰도 낮음: {format_info.confidence:.2f} "
                f"(최소 권장: {MIN_FORMAT_CONFIDENCE:.2f})"
            )

        # 확장자와 감지 포맷 불일치 경고
        ext = path.suffix.lower().lstrip(".")
        detected = format_info.detected_format.lower()
        # mp4/mov는 동일 컨테이너(ftyp)이므로 호환
        compatible_groups: list[frozenset[str]] = [
            frozenset({"mp4", "mov", "m4v"}),
            frozenset({"mkv", "webm"}),
        ]
        is_compatible = ext == detected or any(
            ext in group and detected in group for group in compatible_groups
        )
        if not is_compatible and ext != "" and detected != "":
            result.warnings.append(
                f"확장자({ext})와 감지 포맷({detected}) 불일치"
            )

    # -------------------------------------------------------------------------
    # 3단계: 메타데이터 검증
    # -------------------------------------------------------------------------

    def _validate_metadata(
        self,
        path: Path,
        result: FormatValidationResult,
    ) -> None:
        """메타데이터 기반 해상도/FPS/코덱/길이/비트레이트 검증."""
        try:
            metadata: ExtractedMetadata = self._metadata_extractor.extract(str(path))
        except Exception as exc:
            result.errors.append(f"메타데이터 추출 실패: {exc!s}")
            return

        result.metadata = metadata

        if not metadata.is_valid:
            result.errors.append("유효한 메타데이터를 추출할 수 없습니다")
            return

        # --- 해상도 검증 ---
        w, h = metadata.width, metadata.height
        cfg = self._config

        if w < cfg.min_width or h < cfg.min_height:
            result.errors.append(
                f"해상도 부족: {w}x{h} (최소: {cfg.min_width}x{cfg.min_height})"
            )

        if w > cfg.max_width or h > cfg.max_height:
            result.errors.append(
                f"해상도 초과: {w}x{h} (최대: {cfg.max_width}x{cfg.max_height})"
            )

        # --- FPS 검증 ---
        fps = metadata.fps
        if fps > 0:
            if fps < cfg.min_fps:
                result.errors.append(
                    f"FPS 부족: {fps:.2f} (최소: {cfg.min_fps:.2f})"
                )
            if fps > cfg.max_fps:
                result.errors.append(
                    f"FPS 초과: {fps:.2f} (최대: {cfg.max_fps:.2f})"
                )
        else:
            result.warnings.append("FPS 정보를 확인할 수 없습니다")

        # --- 코덱 검증 ---
        if metadata.codec is not None:
            codec_value = metadata.codec.value.lower()
            allowed_codecs = cfg.allowed_codecs or SUPPORTED_VIDEO_CODECS
            if codec_value not in allowed_codecs:
                result.errors.append(
                    f"지원하지 않는 코덱: '{codec_value}' "
                    f"(허용: {', '.join(sorted(allowed_codecs)[:5])})"
                )
        elif cfg.strict_codec_check:
            result.errors.append("코덱 정보를 감지할 수 없습니다 (엄격 모드)")
        else:
            result.warnings.append("코덱 정보를 감지할 수 없습니다")

        # --- 길이 검증 ---
        dur = metadata.duration_sec
        if dur > 0:
            if dur < cfg.min_duration_sec:
                result.errors.append(
                    f"영상 길이 부족: {dur:.2f}초 (최소: {cfg.min_duration_sec:.2f}초)"
                )
            if dur > cfg.max_duration_sec:
                result.errors.append(
                    f"영상 길이 초과: {dur:.2f}초 (최대: {cfg.max_duration_sec:.2f}초)"
                )
        else:
            result.warnings.append("영상 길이 정보를 확인할 수 없습니다")

        # --- 비트레이트 검증 ---
        bitrate_bps = metadata.bitrate_kbps * 1000 if metadata.bitrate_kbps > 0 else 0
        if bitrate_bps > 0:
            if bitrate_bps < cfg.min_bitrate_bps:
                result.warnings.append(
                    f"비트레이트 낮음: {metadata.bitrate_kbps}kbps "
                    f"(최소 권장: {cfg.min_bitrate_bps // 1000}kbps)"
                )
            if bitrate_bps > cfg.max_bitrate_bps:
                result.warnings.append(
                    f"비트레이트 높음: {metadata.bitrate_kbps}kbps "
                    f"(최대 권장: {cfg.max_bitrate_bps // 1000}kbps)"
                )

    # -------------------------------------------------------------------------
    # repr
    # -------------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"FormatValidator(config={self._config!r})"


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    # --- 클래스 ---
    "FormatValidator",
    "FormatValidationConfig",
    "FormatValidationResult",
    "FormatValidationStats",
    # --- 상수 ---
    "MIN_ANALYSIS_FPS",
    "MAX_ANALYSIS_FPS",
    "MIN_VIDEO_DURATION_SEC",
    "MAX_VIDEO_DURATION_SEC",
    "MAX_VALIDATION_HISTORY",
    "MIN_FORMAT_CONFIDENCE",
]

__version__ = "1.0.0"
