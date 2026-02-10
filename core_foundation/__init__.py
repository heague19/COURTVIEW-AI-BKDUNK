"""
core_foundation - COURTVIEW Desktop 핵심 기반 모듈

Desktop Edition에 최적화된 경량 Foundation Layer (App Server 대비 60% 경량화)

포함 모듈:
- config: YAML/ENV 로더, Pydantic 검증, 전역 설정
- monitoring: Loguru 로깅, GPU/CPU 메트릭, 프로파일링
- exceptions: 구조화된 예외 계층 (하드웨어, 검증 등)

제외 모듈 (이유: 로컬 단일 프로세스 실행):
- registry: 서비스 레지스트리 → 직접 import로 대체
- resilience: Circuit Breaker → 네트워크 호출 없음
- security: Secrets Manager → .env 파일 충분
"""

__version__ = "1.0.0"
__author__ = "COURTVIEW Development Team"

# TODO: settings.py와 logger.py 구현 후 주석 해제
# from core_foundation.config.settings import settings
# from core_foundation.monitoring.logger import setup_logger
from core_foundation.exceptions.base import CourtViewError

__all__ = [
    # "settings",  # TODO: 구현 후 추가
    # "setup_logger",  # TODO: 구현 후 추가
    "CourtViewError",
]
