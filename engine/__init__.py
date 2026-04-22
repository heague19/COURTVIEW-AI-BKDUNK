# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine
파일: __init__.py
설명: 분석 파이프라인 오케스트레이션 (Layer 8)
      - config.py: 엔진 정적 설정 (모드/GPU/카메라/Cadence/파이프라인/심판/IO)
      - game_state.py: 엔진 동적 상태 (EngineState FSM + GameContext + Cadence 매핑)
      - gpu/: GPU 리소스 관리 (VRAM/TRT 풀/CUDA Stream/배치)
      - pipeline/: Cadence별 5등급 파이프라인 + 멀티카메라 융합
      - orchestrator/: 경기 수명주기 + Cadence 스케줄링 + 모드 전환
      - referee/: AI 심판 전용 파이프라인
      - io/: 프레임 수집/결과 분배/진행률 보고
      - workers/: 비동기 분석/내보내기/동기화 워커

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - shared/constants/: 경기 규칙, 상태 코드
    - shared/dto/: 데이터 전송 객체
    - core_foundation/: 설정 로더, 모니터링, 레지스트리
    - infrastructure/: 카메라, 전처리, 캐시, 스토리지
    - detection/: 공/코트/선수/골대 감지
    - pose_estimation/: 포즈 추정 백엔드
    - biomechanics/: 생체역학 분석
    - motion_analysis/: 동작 분석 5-Tier
    - game_analysis/: 경기 분석 (이벤트/통계/전술/출력)
    - ai_referee/: AI 심판 (규칙/파울/바이올레이션/판정)
    - feedback_system/: 피드백 생성
"""

from __future__ import annotations

# 1단계: 전역 설정 + 상태 (config.py, game_state.py)
# 2단계 이후 서브모듈은 구축 완료 시 순차 추가

__all__: list[str] = []

__version__ = "1.0.0"
