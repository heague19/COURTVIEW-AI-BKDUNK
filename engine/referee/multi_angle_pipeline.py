# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/referee
파일: multi_angle_pipeline.py
설명: 멀티앵글 판정 교차검증 파이프라인
      - 4~8대 카메라 뷰에서 독립 규칙 평가
      - 뷰 품질 가중 다수결 투표
      - ai_referee/decisions/multi_angle_validator.py에 위임
      - engine은 뷰 수집 + 호출 순서 제어만 담당

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/referee/referee_orchestrator.py: RefereeOrchestrator
    - engine/config.py: RefereeConfig
    - ai_referee/decisions/multi_angle_validator.py: MultiAngleValidator (TYPE_CHECKING)

소비자:
    - engine/referee/referee_orchestrator.py: 멀티앵글 검증 단계
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING, Any, Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import RefereeConfig

if TYPE_CHECKING:
    from ai_referee.decisions.multi_angle_validator import MultiAngleValidator

_logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_VALIDATION_HISTORY: Final[int] = 200


# =============================================================================
# 뷰 평가 결과
# =============================================================================
@dataclass(slots=True)
class ViewEvaluation:
    """
    단일 뷰의 규칙 평가 결과.

    Attributes:
        camera_id: 카메라 식별자
        violated: 위반 감지 여부
        confidence: 신뢰도
        view_quality: 뷰 품질 점수 (0~1)
        rule_id: 규칙 ID
    """

    camera_id: str = ""
    violated: bool = False
    confidence: float = 0.0
    view_quality: float = 1.0
    rule_id: str = ""


# =============================================================================
# 멀티앵글 결과
# =============================================================================
@dataclass(slots=True)
class MultiAngleResult:
    """
    멀티앵글 교차검증 결과.

    Attributes:
        rule_id: 평가 대상 규칙 ID
        num_views: 참여 뷰 수
        agreement_ratio: 합의 비율 (0~1)
        consensus_reached: 합의 도달 여부
        weighted_confidence: 가중 신뢰도
        view_evaluations: 뷰별 평가 결과
        processing_time_ms: 처리 시간 (ms)
    """

    rule_id: str = ""
    num_views: int = 0
    agreement_ratio: float = 0.0
    consensus_reached: bool = False
    weighted_confidence: float = 0.0
    view_evaluations: list[ViewEvaluation] = field(default_factory=list)
    processing_time_ms: float = 0.0


# =============================================================================
# 멀티앵글 파이프라인
# =============================================================================
class MultiAnglePipeline:
    """
    멀티앵글 판정 교차검증 파이프라인.

    여러 카메라 뷰에서 동일 규칙을 독립 평가하고,
    품질 가중 다수결로 최종 판정을 결정합니다.

    Attributes:
        _config: 심판 설정
        _validator: MultiAngleValidator (DI 주입)
        _history: 검증 이력
        _total_validations: 총 검증 횟수
        _lock: 스레드 안전 잠금
    """

    __slots__ = (
        "_config",
        "_validator",
        "_history",
        "_total_validations",
        "_lock",
    )

    def __init__(self, config: RefereeConfig | None = None) -> None:
        self._config = config or RefereeConfig()
        self._validator: MultiAngleValidator | None = None
        self._history: list[MultiAngleResult] = []
        self._total_validations: int = 0
        self._lock: RLock = RLock()

    def set_validator(self, validator: MultiAngleValidator) -> None:
        """MultiAngleValidator 주입."""
        self._validator = validator
        _logger.info("MultiAngleValidator 주입 완료")

    # =========================================================================
    # 교차검증 실행
    # =========================================================================
    def validate(
        self,
        view_evaluations: list[ViewEvaluation],
        rule_id: str = "",
    ) -> MultiAngleResult:
        """
        멀티앵글 교차검증 실행.

        Args:
            view_evaluations: 뷰별 평가 결과
            rule_id: 규칙 ID

        Returns:
            MultiAngleResult
        """
        t0 = time.perf_counter()

        num_views = len(view_evaluations)
        if num_views == 0:
            return MultiAngleResult(rule_id=rule_id)

        # 가중 투표
        total_weight = 0.0
        violated_weight = 0.0
        confidence_sum = 0.0
        confidence_weight_sum = 0.0

        for ve in view_evaluations:
            w = max(0.0, ve.view_quality)
            total_weight += w
            if ve.violated:
                violated_weight += w
            confidence_sum += ve.confidence * w
            confidence_weight_sum += w

        # 합의 비율
        agreement = violated_weight / max(total_weight, 1e-6)

        # 가중 신뢰도
        weighted_conf = (
            confidence_sum / max(confidence_weight_sum, 1e-6)
            if confidence_weight_sum > 0 else 0.0
        )

        # 합의 도달 여부
        consensus = agreement >= self._config.multi_angle_agreement

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        result = MultiAngleResult(
            rule_id=rule_id,
            num_views=num_views,
            agreement_ratio=agreement,
            consensus_reached=consensus,
            weighted_confidence=weighted_conf,
            view_evaluations=list(view_evaluations),
            processing_time_ms=elapsed_ms,
        )

        with self._lock:
            self._total_validations += 1
            self._history.append(result)
            if len(self._history) > _MAX_VALIDATION_HISTORY:
                self._history = self._history[-_MAX_VALIDATION_HISTORY:]

        return result

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def total_validations(self) -> int:
        """총 검증 횟수."""
        return self._total_validations

    def reset(self) -> None:
        """이력 초기화."""
        with self._lock:
            self._history.clear()
            self._total_validations = 0

    def __repr__(self) -> str:
        return (
            f"MultiAnglePipeline(validations={self._total_validations})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "ViewEvaluation",
    "MultiAngleResult",
    "MultiAnglePipeline",
]

__version__ = "1.0.0"
