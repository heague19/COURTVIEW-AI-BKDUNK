# -*- coding: utf-8 -*-
"""
Phase 1A 단위 테스트: record_corrector.py

대상: RecordCorrectorConfig, RecordCorrector, IntegrityCheckResult
등급: 🟠EVENT (<10ms)
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from shared.dto.game_management_dto import CorrectionRecord, CorrectionType

from game_analysis.game_state.game_management.record_corrector import (
    RecordCorrector,
    RecordCorrectorConfig,
    IntegrityCheckResult,
)


# =============================================================================
# RecordCorrectorConfig
# =============================================================================

class TestRecordCorrectorConfig:
    def test_default_config(self) -> None:
        cfg = RecordCorrectorConfig()
        assert cfg.score_max_diff == 0
        assert cfg.rebound_tolerance == 3
        assert cfg.playing_time_tolerance_sec == 5.0

    def test_from_yaml(self) -> None:
        cfg = RecordCorrectorConfig.from_yaml({
            "score_max_diff": 1,
            "rebound_tolerance": 5,
            "playing_time_tolerance_sec": 10.0,
        })
        assert cfg.score_max_diff == 1
        assert cfg.rebound_tolerance == 5
        assert cfg.playing_time_tolerance_sec == 10.0

    def test_from_yaml_empty(self) -> None:
        cfg = RecordCorrectorConfig.from_yaml({})
        assert cfg.score_max_diff == 0


# =============================================================================
# RecordCorrector — 정정 적용
# =============================================================================

class TestRecordCorrectorApply:
    def test_apply_correction(self) -> None:
        rc = RecordCorrector()
        event_id = uuid4()
        cid = rc.apply_correction(
            event_id, CorrectionType.SCORE,
            "2점", "3점", "기록원A", "위치 재확인",
        )
        assert cid is not None
        assert rc.get_correction_count() == 1

    def test_apply_multiple_types(self) -> None:
        rc = RecordCorrector()
        event_id = uuid4()
        rc.apply_correction(event_id, CorrectionType.SCORE, "2점", "3점")
        rc.apply_correction(event_id, CorrectionType.PLAYER, "#7", "#23")
        rc.apply_correction(uuid4(), CorrectionType.TIME, "08:30", "08:25")
        assert rc.get_correction_count() == 3

    def test_correction_preserves_metadata(self) -> None:
        rc = RecordCorrector()
        event_id = uuid4()
        rc.apply_correction(
            event_id, CorrectionType.SCORE,
            "2점", "3점", "기록원A", "위치 재확인",
        )
        corrections = rc.get_all_corrections()
        rec = corrections[0]
        assert isinstance(rec, CorrectionRecord)
        assert rec.corrected_by == "기록원A"
        assert rec.reason == "위치 재확인"
        assert rec.original_value == "2점"
        assert rec.corrected_value == "3점"


# =============================================================================
# RecordCorrector — 정정 체인
# =============================================================================

class TestRecordCorrectorChain:
    def test_correction_chain(self) -> None:
        rc = RecordCorrector()
        event_id = uuid4()
        cid1 = rc.apply_correction(event_id, CorrectionType.SCORE, "2점", "3점")
        cid2 = rc.apply_correction(event_id, CorrectionType.PLAYER, "#7", "#23")
        chain = rc.get_correction_chain(event_id)
        assert len(chain) == 2
        assert chain[0].correction_id == cid1
        assert chain[1].correction_id == cid2

    def test_chain_empty_for_unknown(self) -> None:
        rc = RecordCorrector()
        assert rc.get_correction_chain(uuid4()) == []

    def test_has_corrections(self) -> None:
        rc = RecordCorrector()
        event_id = uuid4()
        assert not rc.has_corrections(event_id)
        rc.apply_correction(event_id, CorrectionType.SCORE, "2점", "3점")
        assert rc.has_corrections(event_id)

    def test_get_latest_value(self) -> None:
        rc = RecordCorrector()
        event_id = uuid4()
        rc.apply_correction(event_id, CorrectionType.SCORE, "2점", "3점")
        rc.apply_correction(event_id, CorrectionType.SCORE, "3점", "2점")
        assert rc.get_latest_value(event_id) == "2점"

    def test_get_latest_value_none(self) -> None:
        rc = RecordCorrector()
        assert rc.get_latest_value(uuid4()) is None


# =============================================================================
# RecordCorrector — 조회
# =============================================================================

class TestRecordCorrectorQueries:
    def test_get_corrections_by_type(self) -> None:
        rc = RecordCorrector()
        rc.apply_correction(uuid4(), CorrectionType.SCORE, "a", "b")
        rc.apply_correction(uuid4(), CorrectionType.PLAYER, "c", "d")
        rc.apply_correction(uuid4(), CorrectionType.SCORE, "e", "f")
        score_recs = rc.get_corrections_by_type(CorrectionType.SCORE)
        assert len(score_recs) == 2

    def test_get_correction_count_by_type(self) -> None:
        rc = RecordCorrector()
        rc.apply_correction(uuid4(), CorrectionType.SCORE, "a", "b")
        rc.apply_correction(uuid4(), CorrectionType.TIME, "c", "d")
        counts = rc.get_correction_count_by_type()
        assert counts[CorrectionType.SCORE] == 1
        assert counts[CorrectionType.TIME] == 1

    def test_get_all_corrections_defensive_copy(self) -> None:
        rc = RecordCorrector()
        rc.apply_correction(uuid4(), CorrectionType.SCORE, "a", "b")
        all_recs = rc.get_all_corrections()
        all_recs.clear()
        assert rc.get_correction_count() == 1  # 원본 유지


# =============================================================================
# RecordCorrector — 무결성 검증
# =============================================================================

class TestRecordCorrectorIntegrity:
    def test_score_integrity_pass(self) -> None:
        rc = RecordCorrector()
        result = rc.verify_score_integrity(80, 80)
        assert result.is_valid
        assert len(result.violations) == 0

    def test_score_integrity_fail(self) -> None:
        rc = RecordCorrector()
        result = rc.verify_score_integrity(80, 78)
        assert not result.is_valid
        assert len(result.violations) == 1

    def test_rebound_integrity_pass(self) -> None:
        rc = RecordCorrector()
        result = rc.verify_rebound_integrity(40, 42)
        assert result.is_valid

    def test_rebound_integrity_fail(self) -> None:
        rc = RecordCorrector()
        result = rc.verify_rebound_integrity(40, 50)
        assert not result.is_valid

    def test_playing_time_integrity_pass(self) -> None:
        rc = RecordCorrector()
        result = rc.verify_playing_time_integrity(12000.0, 12003.0)
        assert result.is_valid

    def test_playing_time_integrity_fail(self) -> None:
        rc = RecordCorrector()
        result = rc.verify_playing_time_integrity(12000.0, 12010.0)
        assert not result.is_valid

    def test_full_integrity_all_pass(self) -> None:
        rc = RecordCorrector()
        result = rc.run_full_integrity_check(80, 80, 40, 42, 12000.0, 12003.0)
        assert result.is_valid

    def test_full_integrity_all_fail(self) -> None:
        rc = RecordCorrector()
        result = rc.run_full_integrity_check(80, 78, 40, 50, 12000.0, 12020.0)
        assert not result.is_valid
        assert len(result.violations) == 3

    def test_full_integrity_partial_fail(self) -> None:
        rc = RecordCorrector()
        result = rc.run_full_integrity_check(80, 78, 40, 42, 12000.0, 12003.0)
        assert not result.is_valid
        assert len(result.violations) == 1

    def test_custom_tolerance(self) -> None:
        rc = RecordCorrector(RecordCorrectorConfig(score_max_diff=5))
        result = rc.verify_score_integrity(80, 76)
        assert result.is_valid  # 차이 4 < 5


# =============================================================================
# RecordCorrector — 리셋
# =============================================================================

class TestRecordCorrectorReset:
    def test_reset(self) -> None:
        rc = RecordCorrector()
        event_id = uuid4()
        rc.apply_correction(event_id, CorrectionType.SCORE, "a", "b")
        rc.reset()
        assert rc.get_correction_count() == 0
        assert not rc.has_corrections(event_id)

    def test_from_yaml(self) -> None:
        rc = RecordCorrector.from_yaml({"score_max_diff": 2})
        assert rc is not None
