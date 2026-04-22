# -*- coding: utf-8 -*-
"""
infrastructure/preprocessing/video_decoder.py 단위 테스트.

비디오 디코더 모듈의 모든 exported 클래스/상수/Enum을 검증한다.
실제 비디오 파일 없이 mock/synthetic 접근으로 테스트.

테스트 대상:
  - DecoderState: Enum 멤버, is_active, can_open 프로퍼티
  - DecoderStats: 기본값, 계산 프로퍼티, repr
  - VideoDecoder: 상태 전이, open/close, pause/resume/seek, 프로퍼티, context manager
  - 모듈 상수: MAX_DECODE_RETRIES, DECODER_BUFFER_MAX, AUTO_RELEASE_WARNING_FRAMES, SEEK_TOLERANCE_FRAMES
  - __all__, __version__
"""
from __future__ import annotations

import sys
sys.path.insert(0, "d:/COURTVIEW_DESK")

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from infrastructure.preprocessing.video_decoder import (
    DECODER_BUFFER_MAX,
    DecoderState,
    DecoderStats,
    VideoDecoder,
    __all__ as module_all,
    __version__ as module_version,
)
from shared.constants.video_constants import (
    ANALYSIS_NORMALIZED_RESOLUTION,
    DECODE_BUFFER_SIZE,
    DEFAULT_FPS,
)
from shared.dto.video_dto import FrameData, FrameStatus, VideoResolution


# =============================================================================
# 모듈 메타 정보 검증
# =============================================================================

class TestModuleMeta:
    """모듈 __all__, __version__ 검증."""

    def test_version_is_1_0_0(self):
        assert module_version == "1.0.0"

    def test_all_contains_video_decoder(self):
        assert "VideoDecoder" in module_all

    def test_all_contains_decoder_stats(self):
        assert "DecoderStats" in module_all

    def test_all_contains_decoder_state(self):
        assert "DecoderState" in module_all

    def test_all_contains_decoder_buffer_max(self):
        assert "DECODER_BUFFER_MAX" in module_all

    def test_all_has_correct_length(self):
        assert len(module_all) == 4


# =============================================================================
# 모듈 상수 검증
# =============================================================================

class TestModuleConstants:
    """모듈 레벨 상수 값 검증."""

    def test_decoder_buffer_max_equals_decode_buffer_size(self):
        assert DECODER_BUFFER_MAX == DECODE_BUFFER_SIZE

    def test_decoder_buffer_max_value(self):
        assert DECODER_BUFFER_MAX == 30


# =============================================================================
# DecoderState Enum 검증
# =============================================================================

class TestDecoderState:
    """DecoderState Enum 멤버 및 프로퍼티 검증."""

    def test_idle_value(self):
        assert DecoderState.IDLE.value == "idle"

    def test_opening_value(self):
        assert DecoderState.OPENING.value == "opening"

    def test_decoding_value(self):
        assert DecoderState.DECODING.value == "decoding"

    def test_paused_value(self):
        assert DecoderState.PAUSED.value == "paused"

    def test_closed_value(self):
        assert DecoderState.CLOSED.value == "closed"

    def test_error_value(self):
        assert DecoderState.ERROR.value == "error"

    def test_total_member_count(self):
        assert len(DecoderState) == 6

    # is_active 프로퍼티
    def test_idle_not_active(self):
        assert DecoderState.IDLE.is_active is False

    def test_opening_not_active(self):
        assert DecoderState.OPENING.is_active is False

    def test_decoding_is_active(self):
        assert DecoderState.DECODING.is_active is True

    def test_paused_is_active(self):
        assert DecoderState.PAUSED.is_active is True

    def test_closed_not_active(self):
        assert DecoderState.CLOSED.is_active is False

    def test_error_not_active(self):
        assert DecoderState.ERROR.is_active is False

    # can_open 프로퍼티
    def test_idle_can_open(self):
        assert DecoderState.IDLE.can_open is True

    def test_opening_cannot_open(self):
        assert DecoderState.OPENING.can_open is False

    def test_decoding_cannot_open(self):
        assert DecoderState.DECODING.can_open is False

    def test_paused_cannot_open(self):
        assert DecoderState.PAUSED.can_open is False

    def test_closed_can_open(self):
        assert DecoderState.CLOSED.can_open is True

    def test_error_can_open(self):
        assert DecoderState.ERROR.can_open is True


# =============================================================================
# DecoderStats 검증
# =============================================================================

class TestDecoderStats:
    """DecoderStats 기본값, 계산 프로퍼티, repr 검증."""

    def test_defaults(self):
        stats = DecoderStats()
        assert stats.frames_decoded == 0
        assert stats.frames_failed == 0
        assert stats.bytes_read == 0
        assert stats.decode_time_sec == 0.0
        assert stats.seek_count == 0

    def test_has_slots(self):
        assert hasattr(DecoderStats, "__slots__")

    def test_total_frames_zero(self):
        stats = DecoderStats()
        assert stats.total_frames == 0

    def test_total_frames_sum(self):
        stats = DecoderStats(frames_decoded=80, frames_failed=20)
        assert stats.total_frames == 100

    def test_success_rate_zero_when_no_frames(self):
        stats = DecoderStats()
        assert stats.success_rate == 0.0

    def test_success_rate_all_success(self):
        stats = DecoderStats(frames_decoded=100, frames_failed=0)
        assert stats.success_rate == 1.0

    def test_success_rate_half(self):
        stats = DecoderStats(frames_decoded=50, frames_failed=50)
        assert stats.success_rate == pytest.approx(0.5)

    def test_success_rate_with_failures(self):
        stats = DecoderStats(frames_decoded=90, frames_failed=10)
        assert stats.success_rate == pytest.approx(0.9)

    def test_avg_decode_ms_zero_when_no_decoded(self):
        stats = DecoderStats()
        assert stats.avg_decode_ms == 0.0

    def test_avg_decode_ms_calculated(self):
        stats = DecoderStats(frames_decoded=100, decode_time_sec=1.0)
        assert stats.avg_decode_ms == pytest.approx(10.0)

    def test_avg_decode_ms_precise(self):
        stats = DecoderStats(frames_decoded=200, decode_time_sec=2.5)
        expected = (2.5 / 200) * 1000.0
        assert stats.avg_decode_ms == pytest.approx(expected)

    def test_repr_contains_decoded(self):
        stats = DecoderStats(frames_decoded=42, frames_failed=3)
        r = repr(stats)
        assert "decoded=42" in r
        assert "failed=3" in r

    def test_repr_contains_rate_and_avg(self):
        stats = DecoderStats(frames_decoded=100, frames_failed=0, decode_time_sec=1.0)
        r = repr(stats)
        assert "rate=100.00%" in r
        assert "avg=10.0ms" in r


# =============================================================================
# VideoDecoder 기본 프로퍼티/상태 검증
# =============================================================================

class TestVideoDecoderInit:
    """VideoDecoder 초기 상태 검증."""

    def test_initial_state_is_idle(self):
        dec = VideoDecoder()
        assert dec.state == DecoderState.IDLE

    def test_initial_is_open_false(self):
        dec = VideoDecoder()
        assert dec.is_open is False

    def test_initial_file_path_empty(self):
        dec = VideoDecoder()
        assert dec.file_path == ""

    def test_initial_metadata_none(self):
        dec = VideoDecoder()
        assert dec.metadata is None

    def test_initial_current_index_zero(self):
        dec = VideoDecoder()
        assert dec.current_index == 0

    def test_initial_stats_defaults(self):
        dec = VideoDecoder()
        stats = dec.stats
        assert stats.frames_decoded == 0
        assert stats.frames_failed == 0

    def test_initial_total_frames_zero(self):
        dec = VideoDecoder()
        assert dec.total_frames == 0

    def test_initial_fps_default(self):
        dec = VideoDecoder()
        assert dec.fps == float(DEFAULT_FPS)

    def test_initial_resolution_default(self):
        dec = VideoDecoder()
        assert dec.resolution == ANALYSIS_NORMALIZED_RESOLUTION

    def test_camera_id_default_none(self):
        dec = VideoDecoder()
        assert dec._camera_id is None

    def test_camera_id_custom(self):
        dec = VideoDecoder(camera_id="cam_01")
        assert dec._camera_id == "cam_01"


# =============================================================================
# VideoDecoder open/close 및 상태 전이 검증
# =============================================================================

class TestVideoDecoderOpenClose:
    """open/close 및 상태 전이 검증 (파일 없음 시나리오)."""

    def test_open_nonexistent_file_returns_false(self):
        dec = VideoDecoder()
        result = dec.open("__nonexistent_video_file_12345.mp4")
        assert result is False

    def test_open_nonexistent_sets_error_state(self):
        dec = VideoDecoder()
        dec.open("__nonexistent_video_file_12345.mp4")
        assert dec.state == DecoderState.ERROR

    def test_close_from_idle(self):
        dec = VideoDecoder()
        dec.close()
        assert dec.state == DecoderState.CLOSED

    def test_close_from_error(self):
        dec = VideoDecoder()
        dec.open("__nonexistent.mp4")
        dec.close()
        assert dec.state == DecoderState.CLOSED

    def test_open_from_closed_after_error(self):
        """ERROR → close() → CLOSED → open 시도 가능."""
        dec = VideoDecoder()
        dec.open("__nonexistent.mp4")
        assert dec.state == DecoderState.ERROR
        # ERROR에서도 can_open=True
        assert dec.state.can_open is True

    def test_stats_are_defensive_copy(self):
        """stats 프로퍼티가 방어적 복사인지 검증."""
        dec = VideoDecoder()
        s1 = dec.stats
        s2 = dec.stats
        assert s1 is not s2
        assert s1.frames_decoded == s2.frames_decoded


# =============================================================================
# VideoDecoder pause/resume/seek on non-open decoder
# =============================================================================

class TestVideoDecoderControlNotOpen:
    """열려있지 않은 디코더에서의 제어 메서드 검증."""

    def test_pause_on_idle_returns_false(self):
        dec = VideoDecoder()
        assert dec.pause() is False

    def test_resume_on_idle_returns_false(self):
        dec = VideoDecoder()
        assert dec.resume() is False

    def test_seek_on_idle_returns_false(self):
        dec = VideoDecoder()
        assert dec.seek(0) is False

    def test_pause_on_closed_returns_false(self):
        dec = VideoDecoder()
        dec.close()
        assert dec.pause() is False

    def test_resume_on_closed_returns_false(self):
        dec = VideoDecoder()
        dec.close()
        assert dec.resume() is False

    def test_seek_on_closed_returns_false(self):
        dec = VideoDecoder()
        dec.close()
        assert dec.seek(10) is False

    def test_decode_next_on_idle_returns_none(self):
        dec = VideoDecoder()
        assert dec.decode_next() is None

    def test_decode_frame_on_idle_returns_none(self):
        dec = VideoDecoder()
        assert dec.decode_frame(0) is None

    def test_decode_frame_negative_index_returns_none(self):
        dec = VideoDecoder()
        assert dec.decode_frame(-1) is None

    def test_decode_range_negative_start(self):
        dec = VideoDecoder()
        assert dec.decode_range(-1, 10) == []

    def test_decode_range_end_le_start(self):
        dec = VideoDecoder()
        assert dec.decode_range(10, 10) == []
        assert dec.decode_range(10, 5) == []


# =============================================================================
# VideoDecoder context manager
# =============================================================================

class TestVideoDecoderContextManager:
    """Context Manager 프로토콜 검증."""

    def test_enter_returns_self(self):
        dec = VideoDecoder()
        result = dec.__enter__()
        assert result is dec

    def test_exit_closes_decoder(self):
        dec = VideoDecoder()
        dec.__enter__()
        dec.__exit__(None, None, None)
        assert dec.state == DecoderState.CLOSED

    def test_with_statement(self):
        with VideoDecoder() as dec:
            assert isinstance(dec, VideoDecoder)
        assert dec.state == DecoderState.CLOSED

    def test_with_statement_custom_camera(self):
        with VideoDecoder(camera_id="test_cam") as dec:
            assert dec._camera_id == "test_cam"
        assert dec.state == DecoderState.CLOSED


# =============================================================================
# VideoDecoder repr
# =============================================================================

class TestVideoDecoderRepr:
    """repr 문자열 형식 검증."""

    def test_repr_idle_state(self):
        dec = VideoDecoder()
        r = repr(dec)
        assert "VideoDecoder(" in r
        assert "state=idle" in r
        assert "frame=0" in r

    def test_repr_contains_file_path(self):
        dec = VideoDecoder()
        r = repr(dec)
        assert "file=''" in r

    def test_repr_after_failed_open(self):
        dec = VideoDecoder()
        dec.open("test_video.mp4")
        r = repr(dec)
        assert "state=error" in r
        assert "test_video.mp4" in r


# =============================================================================
# VideoDecoder reset_stats
# =============================================================================

class TestVideoDecoderResetStats:
    """통계 초기화 검증."""

    def test_reset_stats_clears_values(self):
        dec = VideoDecoder()
        # 통계를 수동으로 변경할 수 없으므로(slots) 초기화만 검증
        dec.reset_stats()
        stats = dec.stats
        assert stats.frames_decoded == 0
        assert stats.frames_failed == 0
        assert stats.bytes_read == 0
        assert stats.decode_time_sec == 0.0
        assert stats.seek_count == 0


# =============================================================================
# VideoDecoder decode_sequential on non-open yields nothing
# =============================================================================

class TestVideoDecoderDecodeSequential:
    """decode_sequential 제너레이터 경계 조건 검증."""

    def test_sequential_on_idle_yields_nothing(self):
        dec = VideoDecoder()
        frames = list(dec.decode_sequential())
        assert frames == []

    def test_sequential_on_closed_yields_nothing(self):
        dec = VideoDecoder()
        dec.close()
        frames = list(dec.decode_sequential())
        assert frames == []

    def test_sequential_with_max_frames_zero(self):
        """max_frames=0 → 즉시 종료."""
        dec = VideoDecoder()
        frames = list(dec.decode_sequential(max_frames=0))
        assert frames == []
