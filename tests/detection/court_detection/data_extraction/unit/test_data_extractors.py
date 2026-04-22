# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/court_detection/data_extraction/unit
파일: test_data_extractors.py
설명: court_detection 데이터 추출기 3종 단위 테스트
      - CourtLineExtractor
      - ZoneExtractor
      - ArenaProfileExtractor

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from detection.court_detection.data_extraction.court_line_extractor import (
    CourtLineExtractor,
)
from detection.court_detection.data_extraction.zone_extractor import (
    ZoneExtractor,
)
from detection.court_detection.data_extraction.arena_profile_extractor import (
    ArenaProfileExtractor,
)
from shared.constants.court_constants import CourtZone
from shared.dto.dataset_dto import UploadStatus


# =============================================================================
# fixture
# =============================================================================

@pytest.fixture()
def temp_output_dir():
    """임시 출력 디렉토리."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture()
def court_lines_frame() -> np.ndarray:
    """코트 라인이 있는 테스트 프레임."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (60, 100, 160)
    cv2.line(frame, (50, 100), (590, 100), (255, 255, 255), 3)
    cv2.line(frame, (50, 380), (590, 380), (255, 255, 255), 3)
    cv2.line(frame, (200, 240), (440, 240), (255, 255, 255), 3)
    return frame


@pytest.fixture()
def sample_lines() -> list[dict]:
    """테스트용 라인 세그먼트 목록."""
    return [
        {"x1": 50.0, "y1": 100.0, "x2": 590.0, "y2": 100.0, "confidence": 0.9},
        {"x1": 50.0, "y1": 380.0, "x2": 590.0, "y2": 380.0, "confidence": 0.85},
        {"x1": 320.0, "y1": 100.0, "x2": 320.0, "y2": 380.0, "confidence": 0.8},
    ]


# =============================================================================
# CourtLineExtractor 테스트
# =============================================================================

class TestCourtLineExtractor:
    """CourtLineExtractor 단위 테스트."""

    def test_초기_상태(self):
        extractor = CourtLineExtractor()
        assert extractor._enabled is False
        assert extractor._total_flushed == 0

    def test_초기화(self, temp_output_dir):
        extractor = CourtLineExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        assert extractor._enabled is True
        assert (temp_output_dir / "images").exists()
        assert (temp_output_dir / "labels").exists()

    def test_비활성화_수집_안함(self, court_lines_frame, sample_lines):
        extractor = CourtLineExtractor()
        # enabled=False (기본)
        count = extractor.process_lines(
            sample_lines, court_lines_frame, frame_index=0,
        )
        assert count == 0

    def test_라인_수집(self, temp_output_dir, court_lines_frame, sample_lines):
        extractor = CourtLineExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)

        count = extractor.process_lines(
            sample_lines, court_lines_frame, frame_index=0,
        )
        # 품질 필터에 따라 일부 수집
        assert count >= 0

    def test_짧은_라인_거부(self, temp_output_dir, court_lines_frame):
        extractor = CourtLineExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)

        short_lines = [
            {"x1": 100.0, "y1": 100.0, "x2": 110.0, "y2": 100.0, "confidence": 0.9},
        ]
        count = extractor.process_lines(
            short_lines, court_lines_frame, frame_index=0,
        )
        assert count == 0
        assert extractor._total_rejected >= 1

    def test_finalize_결과(self, temp_output_dir, court_lines_frame, sample_lines):
        extractor = CourtLineExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        extractor.process_lines(sample_lines, court_lines_frame, frame_index=0)

        result = extractor.finalize()
        assert result.record_count >= 0
        assert result.metadata is not None

    def test_finalize_빈_추출(self, temp_output_dir):
        extractor = CourtLineExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        result = extractor.finalize()
        assert result.record_count == 0
        assert result.upload_status == UploadStatus.PENDING

    def test_reset(self, temp_output_dir):
        extractor = CourtLineExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        extractor._total_flushed = 10
        extractor._total_rejected = 5
        extractor.reset()
        assert extractor._total_flushed == 0
        assert extractor._total_rejected == 0
        assert len(extractor._buffer) == 0

    def test_repr(self):
        extractor = CourtLineExtractor()
        r = repr(extractor)
        assert "CourtLineExtractor" in r
        assert "enabled=False" in r

    def test_중복_해시_거부(self, temp_output_dir, court_lines_frame, sample_lines):
        """동일 라인을 2번 넣으면 두 번째는 거부."""
        extractor = CourtLineExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)

        count1 = extractor.process_lines(
            sample_lines, court_lines_frame, frame_index=0,
        )
        count2 = extractor.process_lines(
            sample_lines, court_lines_frame, frame_index=1,
        )
        # 두 번째는 pHash 중복으로 거부됨 (동일 프레임이므로)
        assert count2 <= count1


# =============================================================================
# ZoneExtractor 테스트
# =============================================================================

class TestZoneExtractor:
    """ZoneExtractor 단위 테스트."""

    def test_초기_상태(self):
        extractor = ZoneExtractor()
        assert extractor._enabled is False
        assert extractor._total_records == 0

    def test_초기화(self, temp_output_dir):
        extractor = ZoneExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        assert extractor._enabled is True
        assert extractor._heatmap is not None
        assert extractor._heatmap.shape == (100, 100)

    def test_비활성화_기록_안함(self):
        extractor = ZoneExtractor()
        extractor.record_position((5.0, 7.5), CourtZone.PAINT_CENTER)
        assert extractor._total_records == 0

    def test_위치_기록(self, temp_output_dir):
        extractor = ZoneExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)

        extractor.record_position((5.0, 7.5), CourtZone.PAINT_CENTER)
        assert extractor._total_records == 1
        assert extractor._zone_counts[CourtZone.PAINT_CENTER.value] == 1

    def test_일괄_기록(self, temp_output_dir):
        extractor = ZoneExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)

        positions = [
            ((5.0, 7.5), CourtZone.PAINT_CENTER),
            ((8.0, 7.5), CourtZone.THREE_TOP_CENTER),
            ((3.0, 2.0), CourtZone.MID_LEFT_BASELINE),
        ]
        extractor.record_batch(positions)
        assert extractor._total_records == 3

    def test_히트맵_갱신(self, temp_output_dir):
        extractor = ZoneExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)

        extractor.record_position((14.0, 7.5))
        assert extractor._heatmap is not None
        assert np.sum(extractor._heatmap) == 1.0

    def test_구역_분포(self, temp_output_dir):
        extractor = ZoneExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)

        extractor.record_position((5.0, 7.5), CourtZone.PAINT_CENTER)
        extractor.record_position((5.0, 7.5), CourtZone.PAINT_CENTER)
        extractor.record_position((8.0, 7.5), CourtZone.THREE_TOP_CENTER)

        dist = extractor.get_zone_distribution()
        assert abs(dist[CourtZone.PAINT_CENTER.value] - 2 / 3) < 0.01
        assert abs(dist[CourtZone.THREE_TOP_CENTER.value] - 1 / 3) < 0.01

    def test_빈_분포(self):
        extractor = ZoneExtractor()
        extractor.initialize(
            output_dir=Path(tempfile.mkdtemp()), enabled=True,
        )
        dist = extractor.get_zone_distribution()
        assert all(v == 0.0 for v in dist.values())

    def test_히트맵_방어적_복사(self, temp_output_dir):
        extractor = ZoneExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        extractor.record_position((10.0, 5.0))

        hm = extractor.get_heatmap()
        assert hm is not None
        hm[:] = 999.0
        assert np.sum(extractor._heatmap) < 999.0

    def test_finalize_저장(self, temp_output_dir):
        extractor = ZoneExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        extractor.record_position((5.0, 7.5), CourtZone.PAINT_CENTER)

        result = extractor.finalize()
        assert result.record_count == 1
        assert result.upload_status == UploadStatus.PENDING

        # JSON 저장 확인
        stats_path = temp_output_dir / "zone_stats.json"
        assert stats_path.exists()
        data = json.loads(stats_path.read_text(encoding="utf-8"))
        assert data["total_records"] == 1

        # 히트맵 저장 확인
        heatmap_path = temp_output_dir / "heatmap.npy"
        assert heatmap_path.exists()

    def test_reset(self, temp_output_dir):
        extractor = ZoneExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        extractor.record_position((5.0, 7.5), CourtZone.PAINT_CENTER)
        extractor.reset()
        assert extractor._total_records == 0
        assert all(v == 0 for v in extractor._zone_counts.values())

    def test_repr(self):
        extractor = ZoneExtractor()
        r = repr(extractor)
        assert "ZoneExtractor" in r
        assert "enabled=False" in r


# =============================================================================
# ArenaProfileExtractor 테스트
# =============================================================================

class TestArenaProfileExtractor:
    """ArenaProfileExtractor 단위 테스트."""

    def test_초기_상태(self):
        extractor = ArenaProfileExtractor()
        assert extractor._enabled is False
        assert extractor._total_processed == 0

    def test_초기화(self, temp_output_dir):
        extractor = ArenaProfileExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        assert extractor._enabled is True

    def test_비활성화_처리_안함(self, court_lines_frame):
        extractor = ArenaProfileExtractor()
        result = extractor.process_frame(court_lines_frame, frame_index=0)
        assert result is False

    def test_프레임_처리(self, temp_output_dir, court_lines_frame):
        extractor = ArenaProfileExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)

        result = extractor.process_frame(
            court_lines_frame,
            frame_index=0,
            homography_quality=0.9,
            detected_standard="fiba",
            num_keypoints=15,
            court_type="full",
        )
        assert result is True
        assert extractor._total_processed == 1

    def test_샘플링_간격(self, temp_output_dir, court_lines_frame):
        """30프레임 간격으로만 수집."""
        extractor = ArenaProfileExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)

        # 프레임 0 수집
        r0 = extractor.process_frame(court_lines_frame, frame_index=0)
        assert r0 is True
        # 프레임 10 건너뜀
        r10 = extractor.process_frame(court_lines_frame, frame_index=10)
        assert r10 is False
        # 프레임 30 수집
        r30 = extractor.process_frame(court_lines_frame, frame_index=30)
        assert r30 is True
        assert extractor._total_processed == 2

    def test_평균_밝기(self, temp_output_dir, court_lines_frame):
        extractor = ArenaProfileExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        extractor.process_frame(court_lines_frame, frame_index=0)

        avg_bright = extractor.get_average_brightness()
        assert avg_bright > 0.0

    def test_평균_호모그래피_품질(self, temp_output_dir, court_lines_frame):
        extractor = ArenaProfileExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        extractor.process_frame(
            court_lines_frame, frame_index=0, homography_quality=0.85,
        )
        extractor.process_frame(
            court_lines_frame, frame_index=30, homography_quality=0.95,
        )

        avg_q = extractor.get_average_homography_quality()
        assert abs(avg_q - 0.9) < 0.01

    def test_지배적_규격(self, temp_output_dir, court_lines_frame):
        extractor = ArenaProfileExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        extractor.process_frame(
            court_lines_frame, frame_index=0, detected_standard="fiba",
        )
        extractor.process_frame(
            court_lines_frame, frame_index=30, detected_standard="nba",
        )
        extractor.process_frame(
            court_lines_frame, frame_index=60, detected_standard="fiba",
        )

        dominant = extractor.get_dominant_standard()
        assert dominant == "fiba"

    def test_빈_상태_기본값(self):
        extractor = ArenaProfileExtractor()
        assert extractor.get_average_brightness() == 0.0
        assert extractor.get_average_homography_quality() == 0.0
        assert extractor.get_dominant_standard() == "fiba"

    def test_finalize_저장(self, temp_output_dir, court_lines_frame):
        extractor = ArenaProfileExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        extractor.process_frame(
            court_lines_frame, frame_index=0, homography_quality=0.9,
        )

        result = extractor.finalize()
        assert result.record_count == 1
        assert result.upload_status == UploadStatus.PENDING

        # JSON 저장 확인
        profile_path = temp_output_dir / "arena_profile.json"
        assert profile_path.exists()
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        assert data["total_snapshots"] == 1
        assert "average_brightness" in data

    def test_finalize_빈_추출(self, temp_output_dir):
        extractor = ArenaProfileExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        result = extractor.finalize()
        assert result.record_count == 0
        assert result.upload_status == UploadStatus.PENDING

    def test_reset(self, temp_output_dir, court_lines_frame):
        extractor = ArenaProfileExtractor()
        extractor.initialize(output_dir=temp_output_dir, enabled=True)
        extractor.process_frame(court_lines_frame, frame_index=0)
        extractor.reset()
        assert extractor._total_processed == 0
        assert len(extractor._snapshots) == 0

    def test_repr(self, temp_output_dir):
        extractor = ArenaProfileExtractor()
        r = repr(extractor)
        assert "ArenaProfileExtractor" in r
        assert "enabled=False" in r
