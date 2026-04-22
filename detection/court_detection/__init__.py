# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/court_detection
파일: __init__.py
설명: 코트 감지 모듈 패키지 (현재 ML 미학습 상태, 캘리브레이션 기반 대체)
      - data_extraction: 재학습 데이터 수집 (3개 추출기)
        - CourtFrameExtractor: 프레임 + 독립 Hough 라인
        - ArenaProfileExtractor: 경기장 환경 프로필 스냅샷
        - ZoneExtractor: 구역 히트맵/분포

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0

아키텍처:
    ML 기반 코트 감지는 장기 로드맵. 현재는
    configs/calibration/cam_*.json 호모그래피로 대체 (UI 수동 클릭).
    data_extraction 파이프라인으로 호모그래피 대체 자체 학습 모델 학습 대상.
"""

from __future__ import annotations


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__: list[str] = []

__version__ = "1.0.0"
