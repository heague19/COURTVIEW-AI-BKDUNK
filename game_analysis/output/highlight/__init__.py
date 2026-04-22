# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/output/highlight
파일: __init__.py
설명: 하이라이트 서브모듈 — 경기 하이라이트 감지/점수/클립 추출 3개 모듈 통합 export
      이벤트 기반으로 하이라이트 후보를 감지하고, 흥미도/중요도 점수를 산출하며,
      클립 시간 범위를 산출하여 릴을 자동 구성합니다.

      Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

# === 하이라이트 감지기 ===
from game_analysis.output.highlight.highlight_detector import (
    HighlightDetectorConfig,
    HighlightDetector,
    HighlightEventInput,
    HighlightCandidate,
    ComboRule,
)

# === 흥미도 점수 산출기 ===
from game_analysis.output.highlight.excitement_scorer import (
    ExcitementScorerConfig,
    ExcitementScorer,
    ScoringInput,
    ScoredHighlight,
)

# === 클립 추출기 ===
from game_analysis.output.highlight.clip_extractor import (
    ClipExtractorConfig,
    ClipExtractor,
    ClipInput,
    ExtractedClip,
    HighlightReel,
    ReelConfig,
)


__all__ = [
    # 하이라이트 감지기
    "HighlightDetectorConfig",
    "HighlightDetector",
    "HighlightEventInput",
    "HighlightCandidate",
    "ComboRule",
    # 흥미도 점수 산출기
    "ExcitementScorerConfig",
    "ExcitementScorer",
    "ScoringInput",
    "ScoredHighlight",
    # 클립 추출기
    "ClipExtractorConfig",
    "ClipExtractor",
    "ClipInput",
    "ExtractedClip",
    "HighlightReel",
    "ReelConfig",
]

__version__ = "1.0.0"
