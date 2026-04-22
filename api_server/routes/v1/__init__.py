# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/routes/v1
설명: API v1 라우터 11종 × 37+ 엔드포인트
      - camera_routes.py: 13 엔드포인트 (연결/스냅샷/MJPEG/캘리브레이션/AI 테스트)
      - game_routes.py: 경기 시작/중지/일시정지/재개/상태
      - referee_routes.py: 판정 목록/챌린지
      - tactical_routes.py: 전술 요약/박스스코어
      - video_routes.py: 영상 업로드/하이라이트
      - feedback_routes.py: 코칭 추천/피드백 목록
      - report_routes.py: 리포트 생성/목록
      - task_routes.py: 진행률/상태
      - export_routes.py: 결과 내보내기/이력
      - metrics_routes.py: GPU/시스템 메트릭
      - stream_routes.py: MJPEG 스트림 (개별/모자이크)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "1.0.0"
