# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/output/coaching_intelligence
설명: 코칭 인텔리전스 패키지
      - realtime_advisor: 실시간 코칭 추천
      - substitution_optimizer: 교체 타이밍 최적화
      - endgame_strategist: 엔드게임 전략

Processing Cadence: EVENT (캐시 기반)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from game_analysis.output.coaching_intelligence.endgame_strategist import (
    EndgameAction,
    EndgameStrategist,
    EndgameStrategistConfig,
    GameSituation,
)
from game_analysis.output.coaching_intelligence.realtime_advisor import (
    RealtimeAdvisor,
    RealtimeAdvisorConfig,
    RecommendationType,
    Urgency,
)
from game_analysis.output.coaching_intelligence.substitution_optimizer import (
    SubstitutionOptimizer,
    SubstitutionOptimizerConfig,
)

__all__ = [
    # realtime_advisor
    "RealtimeAdvisor",
    "RealtimeAdvisorConfig",
    "RecommendationType",
    "Urgency",
    # substitution_optimizer
    "SubstitutionOptimizer",
    "SubstitutionOptimizerConfig",
    # endgame_strategist
    "EndgameStrategist",
    "EndgameStrategistConfig",
    "EndgameAction",
    "GameSituation",
]

__version__ = "1.0.0"
