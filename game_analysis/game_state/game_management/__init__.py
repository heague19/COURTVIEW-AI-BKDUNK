# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_state/game_management
설명: Phase 1A — 경기 관리 (기록원 대체)
      - clock_manager: 경기 시계 + 게임 상태 머신 (🔴FRAME)
      - foul_manager: 개인/팀 파울 누적 + 보너스 (🟠EVENT)
      - timeout_manager: 타임아웃 잔여/사용 (🟠EVENT)
      - substitution_manager: 교체 + 출전 시간 (🟠EVENT)
      - record_corrector: 기록 정정 + 무결성 검증 (🟠EVENT)
      - official_format_exporter: 공식 기록지 출력 (🔵POST-GAME)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from game_analysis.game_state.game_management.clock_manager import (
    ClockManagerConfig,
    ClockManager,
)
from game_analysis.game_state.game_management.foul_manager import (
    FoulRecord,
    FoulManagerConfig,
    FoulManager,
    FoulRecordResult,
)
from game_analysis.game_state.game_management.timeout_manager import (
    TimeoutManagerConfig,
    TimeoutManager,
    TimeoutUseResult,
)
from game_analysis.game_state.game_management.substitution_manager import (
    SubstitutionManagerConfig,
    SubstitutionManager,
    PlayerStint,
    SubstitutionResult,
)
from game_analysis.game_state.game_management.record_corrector import (
    RecordCorrectorConfig,
    RecordCorrector,
    IntegrityCheckResult,
)
from game_analysis.game_state.game_management.official_format_exporter import (
    OfficialFormatExporterConfig,
    OfficialFormatExporter,
)

__all__ = [
    # clock_manager
    "ClockManagerConfig",
    "ClockManager",
    # foul_manager
    "FoulRecord",
    "FoulManagerConfig",
    "FoulManager",
    "FoulRecordResult",
    # timeout_manager
    "TimeoutManagerConfig",
    "TimeoutManager",
    "TimeoutUseResult",
    # substitution_manager
    "SubstitutionManagerConfig",
    "SubstitutionManager",
    "PlayerStint",
    "SubstitutionResult",
    # record_corrector
    "RecordCorrectorConfig",
    "RecordCorrector",
    "IntegrityCheckResult",
    # official_format_exporter
    "OfficialFormatExporterConfig",
    "OfficialFormatExporter",
]

__version__ = "1.0.0"
