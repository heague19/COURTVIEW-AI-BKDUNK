# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection
파일: __init__.py
설명: 객체 감지 모듈 루트 패키지
      - ball_detection: 공 감지/추적/상태 + 데이터 추출
      - court_detection: 데이터 추출만 구축 (ML 미학습, 호모그래피 대체)
      - hoop_detection: 골대 감지/네트 분석 + 데이터 추출
      - player_detection: 선수 감지/팀 분류/번호 OCR + 멀티뷰 트래커

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0

아키텍처 (ARCHITECTURE_DESKTOP.md Layer 1):
    detection/
    ├── ball_detection/     (구축 완료, unified_mode 지원)
    ├── court_detection/    (data_extraction만, ML은 캘리브레이션 대체)
    ├── hoop_detection/     (구축 완료, unified_mode 지원)
    └── player_detection/   (구축 완료, unified_mode + 멀티뷰 트래커)
"""

from __future__ import annotations


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__: list[str] = []

__version__ = "1.0.0"
