# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/output/pre_game
설명: 경기 전 준비 서브모듈
      - 게임 플랜 자동 생성
      - 게임플랜 실행도 추적
      - 수비 매치업 배정
      - 공격 우선순위 설정
      - 경기 전 브리핑 빌드

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from game_analysis.output.pre_game.game_plan_generator import (
    GamePlanGenerator,
    GamePlanGeneratorConfig,
)
from game_analysis.output.pre_game.game_plan_execution_tracker import (
    GamePlanExecutionTracker,
    GamePlanExecutionTrackerConfig,
)
from game_analysis.output.pre_game.defensive_assignment_planner import (
    DefensiveAssignmentPlanner,
    DefensiveAssignmentPlannerConfig,
)
from game_analysis.output.pre_game.offensive_priority_setter import (
    OffensivePrioritySetter,
    OffensivePrioritySetterConfig,
)
from game_analysis.output.pre_game.pre_game_briefing_builder import (
    PreGameBriefingBuilder,
    PreGameBriefingBuilderConfig,
)

__all__ = [
    # game_plan_generator
    "GamePlanGenerator",
    "GamePlanGeneratorConfig",
    # game_plan_execution_tracker
    "GamePlanExecutionTracker",
    "GamePlanExecutionTrackerConfig",
    # defensive_assignment_planner
    "DefensiveAssignmentPlanner",
    "DefensiveAssignmentPlannerConfig",
    # offensive_priority_setter
    "OffensivePrioritySetter",
    "OffensivePrioritySetterConfig",
    # pre_game_briefing_builder
    "PreGameBriefingBuilder",
    "PreGameBriefingBuilderConfig",
]

__version__ = "1.0.0"
