# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/output/video_editing
설명: 비디오 편집 서브모듈
      - 클립 생성/관리
      - 오버레이 주석 렌더링
      - 멀티앵글 동기화
      - 내보내기 관리

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from game_analysis.output.video_editing.annotation_overlay import (
    AnnotationOverlayConfig,
    AnnotationOverlayManager,
)
from game_analysis.output.video_editing.clip_manager import (
    ClipManager,
    ClipManagerConfig,
)
from game_analysis.output.video_editing.export_manager import (
    ExportManager,
    ExportManagerConfig,
    ExportStatus,
)
from game_analysis.output.video_editing.multi_angle_sync import (
    MultiAngleSyncConfig,
    MultiAngleSyncManager,
    SyncLayout,
)

__all__ = [
    # clip_manager
    "ClipManager",
    "ClipManagerConfig",
    # annotation_overlay
    "AnnotationOverlayManager",
    "AnnotationOverlayConfig",
    # multi_angle_sync
    "MultiAngleSyncManager",
    "MultiAngleSyncConfig",
    "SyncLayout",
    # export_manager
    "ExportManager",
    "ExportManagerConfig",
    "ExportStatus",
]

__version__ = "1.0.0"
