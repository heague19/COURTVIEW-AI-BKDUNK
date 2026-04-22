# -*- coding: utf-8 -*-
"""
Phase 1A 성능 테스트: record_corrector.py

Cadence: EVENT (<10ms)
목표: apply_correction() <10ms, 무결성 검증 <5ms
"""

from __future__ import annotations

import time
import statistics
import pytest
from uuid import uuid4

from shared.dto.game_management_dto import CorrectionType
from game_analysis.game_state.game_management.record_corrector import (
    RecordCorrector,
    RecordCorrectorConfig,
)


class TestRecordCorrectorPerf:
    """record_corrector 이벤트 처리 성능 검증."""

    EVENT_BUDGET_SEC: float = 0.010
    ITERATIONS: int = 500

    def test_apply_correction_under_10ms(self) -> None:
        """apply_correction() 평균 < 10ms."""
        rc = RecordCorrector()
        durations: list[float] = []
        for i in range(self.ITERATIONS):
            event_id = uuid4()
            t0 = time.perf_counter()
            rc.apply_correction(
                event_id, CorrectionType.SCORE,
                f"원래값{i}", f"수정값{i}",
                "기록원A", "테스트",
            )
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < self.EVENT_BUDGET_SEC, (
            f"apply_correction() 평균 {avg*1000:.3f}ms > 10ms"
        )

    def test_get_correction_chain_under_5ms(self) -> None:
        """get_correction_chain() < 5ms (이벤트당 10건 체인)."""
        rc = RecordCorrector()
        event_id = uuid4()
        for i in range(10):
            rc.apply_correction(
                event_id, CorrectionType.SCORE,
                f"v{i}", f"v{i+1}",
            )

        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            rc.get_correction_chain(event_id)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.005, f"get_correction_chain() 평균 {avg*1000:.3f}ms > 5ms"

    def test_integrity_check_under_5ms(self) -> None:
        """run_full_integrity_check() < 5ms."""
        rc = RecordCorrector()
        durations: list[float] = []
        for _ in range(self.ITERATIONS):
            t0 = time.perf_counter()
            rc.run_full_integrity_check(80, 80, 40, 42, 12000.0, 12003.0)
            durations.append(time.perf_counter() - t0)

        avg = statistics.mean(durations)
        assert avg < 0.005, f"run_full_integrity_check() 평균 {avg*1000:.3f}ms > 5ms"

    def test_large_correction_volume(self) -> None:
        """1000건 정정 후 조회 안정성."""
        rc = RecordCorrector()
        events = [uuid4() for _ in range(100)]
        for i in range(1000):
            rc.apply_correction(
                events[i % 100],
                CorrectionType.SCORE if i % 3 == 0 else CorrectionType.PLAYER,
                f"v{i}", f"v{i+1}",
            )

        # 전체 조회
        t0 = time.perf_counter()
        all_recs = rc.get_all_corrections()
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.050, f"1000건 전체 조회 {elapsed*1000:.3f}ms > 50ms"

        # 타입별 조회
        t0 = time.perf_counter()
        rc.get_corrections_by_type(CorrectionType.SCORE)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.020, f"타입별 조회 {elapsed*1000:.3f}ms > 20ms"
