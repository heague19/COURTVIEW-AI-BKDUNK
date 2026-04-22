# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: _types.py
설명: 템플릿 공유 dataclass (circular import 방지용 분리).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TemplateEntry:
    """
    피드백 템플릿 항목.

    title: 피드백 제목 (짧은 레이블)
    positive: 긍정 피드백 설명 (GOOD/EXCELLENT 시 사용)
    correction: 교정 피드백 설명 (NEEDS_WORK/CRITICAL 시 사용)
    suggestion: 개선 제안 문구
    """

    title: str
    positive: str
    correction: str
    suggestion: str


@dataclass(slots=True, frozen=True)
class DeviationExpression:
    """편차 구간별 표현 항목."""

    threshold: float | None   # 편차 절대값 상한 (None = 무한대)
    word: str                 # 상태 서술어 (예: "살짝 접혀")
    tone: str                 # 어조 (casual/neutral/serious/urgent)
    emoji_hint: str           # UI 힌트 (서버에서는 미사용, 프론트 참조용)


__all__ = ["TemplateEntry", "DeviationExpression"]
