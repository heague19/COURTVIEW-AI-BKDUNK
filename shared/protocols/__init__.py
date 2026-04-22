# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/protocols
파일: __init__.py
설명: 프로토콜 모듈 패키지 초기화
      - typing.Protocol 기반 인터페이스 정의
      - 구조적 서브타이핑(Structural Subtyping) 지원
      - 런타임 체크 가능

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0

변경 이력:
    - v1.1.0: typing 모던화 (Optional → X | None), 헤더 통일
    - v1.0.0: 초기 생성 (storage_protocol, camera_protocol)
"""

from __future__ import annotations

# =============================================================================
# 스토리지 프로토콜
# =============================================================================
from shared.protocols.storage_protocol import (
    StorageProtocol,
    AsyncStorageProtocol,
)

# =============================================================================
# 카메라 프로토콜
# =============================================================================
from shared.protocols.camera_protocol import (
    CameraProtocol,
    MultiCameraProtocol,
)


__all__ = [
    # 스토리지 프로토콜
    "StorageProtocol",
    "AsyncStorageProtocol",
    # 카메라 프로토콜
    "CameraProtocol",
    "MultiCameraProtocol",
]

__version__ = "1.0.0"
