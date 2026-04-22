# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/templates
파일: variation_engine.py
설명: 피드백 변형 엔진 (Phase 15 H6 분할).

      동일 피드백 문장의 변형을 제공하여 반복 노출 시 신선함 유지.
      seed 기반 결정적 해싱으로 동일 입력 → 동일 결과.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20
버전: 1.0.0
"""

from __future__ import annotations

import hashlib
from threading import RLock

from feedback_system.templates._variation_data import VARIATION_POOL


class TemplateVariationEngine:
    """
    동일 피드백 문장의 변형을 제공하는 엔진.

    같은 카테고리의 피드백을 반복 노출할 때 매번 동일한 문구가
    출력되지 않도록 3~5종의 변형 문장 풀에서 선택합니다.

    선택 방식:
    - seed 기반 결정적 해싱으로 동일 입력 → 동일 결과 (테스트 안정성)
    - seed를 바꾸면 다른 변형 문장 반환 (예: 경기 ID, 이벤트 인덱스)
    """

    __slots__ = ("_lock", "_total_variations")

    def __init__(self) -> None:
        self._lock: RLock = RLock()
        self._total_variations: int = 0

    # -------------------------------------------------------------------------
    # 공개 속성
    # -------------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "TemplateVariationEngine"

    @property
    def total_variations(self) -> int:
        return self._total_variations

    # -------------------------------------------------------------------------
    # 핵심: 변형 문장 반환
    # -------------------------------------------------------------------------
    def get_variation(
        self,
        category: str,
        seed: str = "",
        **format_kwargs: object,
    ) -> str:
        """
        카테고리별 변형 문장 1개를 반환합니다.

        Args:
            category: 변형 카테고리 키 (예: "score_excellent", "tactical_strength")
            seed: 결정적 선택용 시드 (경기ID, 이벤트인덱스 등)
            **format_kwargs: 문장 템플릿 변수 (metric_name, value, unit 등)

        Returns:
            포맷팅된 변형 문장. 카테고리 미존재 시 빈 문자열.
        """
        pool = VARIATION_POOL.get(category)
        if pool is None:
            return ""

        # 결정적 해시 기반 인덱스 선택
        hash_input = f"{category}:{seed}"
        idx = int(hashlib.md5(hash_input.encode()).hexdigest(), 16) % len(pool)
        template = pool[idx]

        with self._lock:
            self._total_variations += 1

        try:
            return template.format(**format_kwargs)
        except (KeyError, ValueError, IndexError):
            return template

    # -------------------------------------------------------------------------
    # 모든 변형 반환 (프리뷰/테스트용)
    # -------------------------------------------------------------------------
    def get_all_variations(
        self,
        category: str,
        **format_kwargs: object,
    ) -> tuple[str, ...]:
        """
        카테고리의 모든 변형 문장을 반환합니다 (포맷팅 적용).

        Args:
            category: 변형 카테고리 키
            **format_kwargs: 문장 템플릿 변수

        Returns:
            포맷팅된 변형 문장 튜플. 카테고리 미존재 시 빈 튜플.
        """
        pool = VARIATION_POOL.get(category)
        if pool is None:
            return ()

        results: list[str] = []
        for template in pool:
            try:
                results.append(template.format(**format_kwargs))
            except (KeyError, ValueError, IndexError):
                results.append(template)
        return tuple(results)

    # -------------------------------------------------------------------------
    # 카테고리 조회
    # -------------------------------------------------------------------------
    @staticmethod
    def get_available_categories() -> tuple[str, ...]:
        """사용 가능한 변형 카테고리 키 목록."""
        return tuple(VARIATION_POOL.keys())

    @staticmethod
    def get_variation_count(category: str) -> int:
        """특정 카테고리의 변형 수."""
        pool = VARIATION_POOL.get(category)
        return len(pool) if pool is not None else 0

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        """변형 카운터 초기화."""
        with self._lock:
            self._total_variations = 0

    def __repr__(self) -> str:
        return f"TemplateVariationEngine(variations={self._total_variations})"


__all__ = ["TemplateVariationEngine"]
