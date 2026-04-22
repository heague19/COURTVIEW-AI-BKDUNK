# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/output/film_session
설명: 필름 세션 서브모듈
      - 주제별 필름 세션 자동 생성
      - 선수별 개인 리뷰 패키지
      - 티칭 포인트 생성

      Processing Cadence: POST-GAME

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from game_analysis.output.film_session.film_session_builder import (
    FilmSessionBuilder,
    FilmSessionBuilderConfig,
)
from game_analysis.output.film_session.player_clip_package import (
    ClipCategory,
    PlayerClipPackageConfig,
    PlayerClipPackageManager,
)
from game_analysis.output.film_session.teaching_point_generator import (
    TeachingPointGenerator,
    TeachingPointGeneratorConfig,
)

__all__ = [
    # film_session_builder
    "FilmSessionBuilder",
    "FilmSessionBuilderConfig",
    # player_clip_package
    "PlayerClipPackageManager",
    "PlayerClipPackageConfig",
    "ClipCategory",
    # teaching_point_generator
    "TeachingPointGenerator",
    "TeachingPointGeneratorConfig",
]

__version__ = "1.0.0"
