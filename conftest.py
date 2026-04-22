# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

루트 conftest.py
프로젝트 루트를 sys.path에 추가하여 모듈 임포트 지원.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
