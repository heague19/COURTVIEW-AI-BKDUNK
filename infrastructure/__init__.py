# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure
설명: 인프라 서비스 (Layer 0).
      - cache/: 캐시 관리 (LRU/TTL/LFU 전략, 모델 추론 캐시)
      - events/: 인메모리 이벤트 버스
      - multi_camera/: 4-8대 카메라 관리
      - preprocessing/: 비디오 전처리
      - storage/: 로컬 스토리지
      - validation/: 데이터 검증

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

__version__ = "1.0.0"
