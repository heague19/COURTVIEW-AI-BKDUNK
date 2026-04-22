# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/constants
파일: localization.py
설명: 다국어 지원을 위한 언어 코드 정의
      - 지원 언어 열거형
      - ISO 639-1 표준 준수

사용 예시::

    >>> from shared.constants.localization import SupportedLanguage
    >>> SupportedLanguage.KO.native_name
    '한국어'
    >>> SupportedLanguage.from_code("en").english_name
    'English'

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0
"""

from __future__ import annotations

# === 표준 라이브러리 ===
from enum import Enum, unique


@unique
class SupportedLanguage(str, Enum):
    """
    지원 언어 열거형.

    분석 결과 및 피드백의 다국어 출력을 위한 언어 코드입니다.
    ISO 639-1 표준을 따릅니다.

    Attributes:
        KO: 한국어 (기본 언어)
        EN: 영어
        JA: 일본어
        ZH: 중국어 (간체)
        ES: 스페인어
    """

    KO = "ko"  # 한국어 (기본)
    EN = "en"  # 영어
    JA = "ja"  # 일본어
    ZH = "zh"  # 중국어 (간체)
    ES = "es"  # 스페인어

    @property
    def native_name(self) -> str:
        """해당 언어의 원어 명칭."""
        return _SUPPORTED_LANGUAGE_NATIVE_NAME_MAP[self]

    @property
    def english_name(self) -> str:
        """영어 언어명."""
        return _SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP[self]

    @classmethod
    def from_code(cls, code: str) -> SupportedLanguage:
        """
        언어 코드로부터 SupportedLanguage 인스턴스 반환.

        Args:
            code: 언어 코드 (예: "ko", "en", "ja")

        Returns:
            해당 SupportedLanguage, 없으면 KO (기본값)
        """
        if not isinstance(code, str) or not code:
            return cls.KO
        return _CODE_TO_LANG.get(code.lower().strip(), cls.KO)


# -- SupportedLanguage 캐시 --

# 언어 코드 → SupportedLanguage 역방향 조회 (O(1))
_CODE_TO_LANG: dict[str, SupportedLanguage] = {
    lang.value: lang for lang in SupportedLanguage
}

_SUPPORTED_LANGUAGE_NATIVE_NAME_MAP: dict[SupportedLanguage, str] = {
    SupportedLanguage.KO: "한국어",
    SupportedLanguage.EN: "English",
    SupportedLanguage.JA: "日本語",
    SupportedLanguage.ZH: "中文",
    SupportedLanguage.ES: "Español",
}

_SUPPORTED_LANGUAGE_ENGLISH_NAME_MAP: dict[SupportedLanguage, str] = {
    SupportedLanguage.KO: "Korean",
    SupportedLanguage.EN: "English",
    SupportedLanguage.JA: "Japanese",
    SupportedLanguage.ZH: "Chinese",
    SupportedLanguage.ES: "Spanish",
}


# =============================================================================
# 모듈 Export 정의
# =============================================================================

__all__ = [
    "SupportedLanguage",
]

__version__ = "1.0.0"
