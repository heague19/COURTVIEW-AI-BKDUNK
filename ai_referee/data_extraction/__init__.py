# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/data_extraction
설명: AI 심판 데이터 추출 (Phase E — 자가학습용)
      - decision_record_extractor: 전체 판정 기록 수집
      - correction_pair_extractor: AI판정 vs 인간교정 쌍
      - edge_case_extractor: 저신뢰도 경계 케이스
      - calibration_data_extractor: 신뢰도 보정 데이터
      - foul_contact_extractor: 접촉+파울 라벨 쌍
      - violation_sequence_extractor: 바이올레이션 시계열

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from ai_referee.data_extraction.decision_record_extractor import (
    DecisionRecordExtractor,
    DecisionRecordExtractorConfig,
)
from ai_referee.data_extraction.correction_pair_extractor import (
    CorrectionPairExtractor,
    CorrectionPairExtractorConfig,
    CorrectionSource,
    ErrorCategory,
)
from ai_referee.data_extraction.edge_case_extractor import (
    EdgeCaseExtractor,
    EdgeCaseExtractorConfig,
    UncertaintyReason,
)
from ai_referee.data_extraction.calibration_data_extractor import (
    CalibrationDataExtractor,
    CalibrationDataExtractorConfig,
    ActualOutcome,
)
from ai_referee.data_extraction.foul_contact_extractor import (
    FoulContactExtractor,
    FoulContactExtractorConfig,
)
from ai_referee.data_extraction.violation_sequence_extractor import (
    ViolationSequenceExtractor,
    ViolationSequenceExtractorConfig,
)

__all__ = [
    # 1. 판정 기록
    "DecisionRecordExtractor",
    "DecisionRecordExtractorConfig",
    # 2. 교정 쌍
    "CorrectionPairExtractor",
    "CorrectionPairExtractorConfig",
    "CorrectionSource",
    "ErrorCategory",
    # 3. 경계 케이스
    "EdgeCaseExtractor",
    "EdgeCaseExtractorConfig",
    "UncertaintyReason",
    # 4. 캘리브레이션
    "CalibrationDataExtractor",
    "CalibrationDataExtractorConfig",
    "ActualOutcome",
    # 5. 접촉+파울
    "FoulContactExtractor",
    "FoulContactExtractorConfig",
    # 6. 바이올레이션 시퀀스
    "ViolationSequenceExtractor",
    "ViolationSequenceExtractorConfig",
]

__version__ = "1.0.0"
