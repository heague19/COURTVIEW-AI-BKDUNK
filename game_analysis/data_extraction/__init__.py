# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/data_extraction
설명: Phase 5 — 자체 모델 학습용 데이터셋 추출 서브모듈

      COURTVIEW 자체 모델 학습용 (원시 데이터):
        frame_record_extractor — 프레임 단위 종합 (10인 위치+키포인트+공+이벤트)
        possession_record_extractor — 점유 단위 전술 라벨 (전술/수비/결과)
        game_record_extractor — 경기 단위 집계 (팀스타일+라인업+모멘텀)

      game_analysis 고유 학습 데이터 (분석 레벨):
        event_correction_extractor — 이벤트 보정 쌍 (AI예측 vs 인간보정)
        tactical_sequence_extractor — 전술 시퀀스 (포메이션→이동→결과)
        player_performance_extractor — 선수 프로파일 (상황별 경향성/효율)
        prediction_outcome_extractor — 예측 캘리브레이션 (예측 vs 실제)

      ※ 하위 레이어 재학습용 (bbox/궤적/라인) → detection/ 자체 data_extraction 참조
      ※ AI 심판 학습용 (파울 장면) → ai_referee/ 자체 data_extraction 참조

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

from game_analysis.data_extraction.frame_record_extractor import (
    FrameRecordExtractor,
    FrameRecordExtractorConfig,
)
from game_analysis.data_extraction.possession_record_extractor import (
    PossessionRecordExtractor,
    PossessionRecordExtractorConfig,
)
from game_analysis.data_extraction.game_record_extractor import (
    GameRecordExtractor,
    GameRecordExtractorConfig,
)
from game_analysis.data_extraction.event_correction_extractor import (
    EventCorrectionExtractor,
    EventCorrectionExtractorConfig,
)
from game_analysis.data_extraction.tactical_sequence_extractor import (
    TacticalSequenceExtractor,
    TacticalSequenceExtractorConfig,
)
from game_analysis.data_extraction.player_performance_extractor import (
    PlayerPerformanceExtractor,
    PlayerPerformanceExtractorConfig,
)
from game_analysis.data_extraction.prediction_outcome_extractor import (
    PredictionOutcomeExtractor,
    PredictionOutcomeExtractorConfig,
)

__all__ = [
    # 원시 데이터 추출
    "FrameRecordExtractor",
    "FrameRecordExtractorConfig",
    "PossessionRecordExtractor",
    "PossessionRecordExtractorConfig",
    "GameRecordExtractor",
    "GameRecordExtractorConfig",
    # 분석 레벨 학습 데이터 추출
    "EventCorrectionExtractor",
    "EventCorrectionExtractorConfig",
    "TacticalSequenceExtractor",
    "TacticalSequenceExtractorConfig",
    "PlayerPerformanceExtractor",
    "PlayerPerformanceExtractorConfig",
    "PredictionOutcomeExtractor",
    "PredictionOutcomeExtractorConfig",
]

__version__ = "1.0.0"
