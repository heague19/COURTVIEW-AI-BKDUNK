# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_management
파일: record_corrector.py
설명: 경기 기록 정정 및 무결성 검증
      - 기록 정정 (득점, 선수, 시간, 이벤트 유형/삭제/추가)
      - 모든 정정에 대한 감사 로그 (audit trail)
      - 정정 체인 (하나의 원본 이벤트에 대한 다수 정정 이력)
      - 기록 무결성 검증 (스코어, 리바운드, 출전시간)
      - 🟠EVENT 등급 (정정 이벤트 시 <10ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - shared/constants/game_management_constants.py: 무결성 검증 파라미터
    - shared/dto/game_management_dto.py: CorrectionRecord, CorrectionType

의존성:
    - shared/constants/game_management_constants.py
    - shared/dto/game_management_dto.py

소비자:
    - game_analysis/live_workspace/correction_sync.py: 보정 동기화
    - game_analysis/game_record/play_by_play.py: PBP 기록 정정 반영
    - game_analysis/statistics/: 통계 재계산 트리거
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.constants.game_management_constants import (
    SCORE_INTEGRITY_MAX_DIFF,
    REBOUND_INTEGRITY_TOLERANCE,
    PLAYING_TIME_TOLERANCE_SEC,
)
from shared.dto.game_management_dto import CorrectionRecord, CorrectionType


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 정정 이력 최대 보관 수 (메모리 가드)
_MAX_CORRECTION_HISTORY: Final[int] = 500


# =============================================================================
# 무결성 검증 결과
# =============================================================================

@dataclass(slots=True)
class IntegrityCheckResult:
    """
    기록 무결성 검증 결과.
    """

    is_valid: bool = True
    # 위반 항목: [(검증 항목, 실제값, 기대값, 차이)]
    violations: list[tuple[str, str, str, str]] = field(default_factory=list)

    def add_violation(
        self,
        check_name: str,
        actual: str,
        expected: str,
        diff: str,
    ) -> None:
        """위반 항목 추가."""
        self.violations.append((check_name, actual, expected, diff))
        self.is_valid = False


# =============================================================================
# 기록 정정 관리자 설정
# =============================================================================

@dataclass(slots=True)
class RecordCorrectorConfig:
    """
    기록 정정 관리자 설정.
    """

    # 스코어 무결성 허용 차이
    score_max_diff: int = SCORE_INTEGRITY_MAX_DIFF
    # 리바운드 무결성 허용 차이
    rebound_tolerance: int = REBOUND_INTEGRITY_TOLERANCE
    # 출전 시간 허용 오차 (초)
    playing_time_tolerance_sec: float = PLAYING_TIME_TOLERANCE_SEC

    @classmethod
    def from_yaml(cls, cfg: dict) -> RecordCorrectorConfig:
        """YAML 설정에서 생성."""
        return cls(
            score_max_diff=int(cfg.get("score_max_diff", SCORE_INTEGRITY_MAX_DIFF)),
            rebound_tolerance=int(cfg.get("rebound_tolerance", REBOUND_INTEGRITY_TOLERANCE)),
            playing_time_tolerance_sec=float(
                cfg.get("playing_time_tolerance_sec", PLAYING_TIME_TOLERANCE_SEC)
            ),
        )


# =============================================================================
# 기록 정정 관리자
# =============================================================================

class RecordCorrector:
    """
    경기 기록 정정 및 무결성 검증.

    🟠EVENT 등급: 정정 이벤트 시 호출 (<10ms).

    기능:
        - 기록 정정 (6종: 득점/선수/시간/이벤트유형/이벤트삭제/이벤트추가)
        - 감사 로그 (audit trail) — 모든 변경에 대한 추적 가능한 이력
        - 이벤트 체인 — 하나의 원본 이벤트에 대한 다수 정정 이력 추적
        - 기록 무결성 검증 (스코어, 리바운드, 출전시간 합산 검증)
        - 정정 통계 (유형별 빈도)

    사용법:
        >>> rc = RecordCorrector()
        >>> correction_id = rc.apply_correction(
        ...     original_event_id=uuid4(),
        ...     correction_type=CorrectionType.SCORE,
        ...     original_value="2점 슛",
        ...     corrected_value="3점 슛",
        ...     corrected_by="기록원A",
        ...     reason="슈터 위치 재확인",
        ... )
        >>> history = rc.get_correction_chain(original_event_id)
    """

    __slots__ = (
        "_config", "_lock",
        # 정정 이력: [CorrectionRecord, ...]
        "_corrections",
        # 이벤트별 정정 체인: {original_event_id: [correction_id, ...]}
        "_event_chains",
    )

    def __init__(self, config: RecordCorrectorConfig | None = None) -> None:
        self._config: RecordCorrectorConfig = config or RecordCorrectorConfig()
        self._lock: RLock = RLock()

        self._corrections: list[CorrectionRecord] = []
        self._event_chains: dict[UUID, list[UUID]] = {}

    # =========================================================================
    # 정정 적용
    # =========================================================================

    def apply_correction(
        self,
        original_event_id: UUID,
        correction_type: CorrectionType,
        original_value: str,
        corrected_value: str,
        corrected_by: str = "",
        reason: str = "",
    ) -> UUID:
        """
        기록 정정 적용.

        🟠EVENT: 정정 이벤트 시 호출.

        Args:
            original_event_id: 정정 대상 원본 이벤트 ID
            correction_type: 정정 유형
            original_value: 변경 전 값 (문자열 표현)
            corrected_value: 변경 후 값 (문자열 표현)
            corrected_by: 정정 주체 (기록원 ID)
            reason: 정정 사유

        Returns:
            정정 ID (correction_id)
        """
        with self._lock:
            correction_id = uuid4()

            record = CorrectionRecord(
                correction_id=correction_id,
                original_event_id=original_event_id,
                correction_type=correction_type,
                original_value=original_value,
                corrected_value=corrected_value,
                corrected_at=datetime.now(timezone.utc),
                corrected_by=corrected_by,
                reason=reason,
            )

            # 이력 추가 (메모리 가드)
            if len(self._corrections) < _MAX_CORRECTION_HISTORY:
                self._corrections.append(record)

            # 이벤트 체인 업데이트
            if original_event_id not in self._event_chains:
                self._event_chains[original_event_id] = []
            self._event_chains[original_event_id].append(correction_id)

            logger.info(
                "기록 정정: 유형=%s, 원본=%s, 변경=%s, 사유='%s', 정정자=%s",
                correction_type, original_value, corrected_value,
                reason, corrected_by,
            )

            return correction_id

    # =========================================================================
    # 정정 이력 조회
    # =========================================================================

    def get_correction_chain(self, original_event_id: UUID) -> list[CorrectionRecord]:
        """
        특정 이벤트에 대한 정정 체인 (시간 순).

        Args:
            original_event_id: 원본 이벤트 ID

        Returns:
            CorrectionRecord 리스트 (시간 순)
        """
        with self._lock:
            chain_ids = self._event_chains.get(original_event_id, [])
            if not chain_ids:
                return []

            chain_id_set = set(chain_ids)
            return [
                rec for rec in self._corrections
                if rec.correction_id in chain_id_set
            ]

    def get_all_corrections(self) -> list[CorrectionRecord]:
        """
        전체 정정 이력 (방어적 복사).

        Returns:
            CorrectionRecord 리스트
        """
        with self._lock:
            return list(self._corrections)

    def get_corrections_by_type(
        self, correction_type: CorrectionType
    ) -> list[CorrectionRecord]:
        """
        특정 유형의 정정 이력.

        Args:
            correction_type: 정정 유형

        Returns:
            CorrectionRecord 리스트
        """
        with self._lock:
            return [
                rec for rec in self._corrections
                if rec.correction_type == correction_type
            ]

    def get_correction_count(self) -> int:
        """전체 정정 횟수."""
        with self._lock:
            return len(self._corrections)

    def get_correction_count_by_type(self) -> dict[CorrectionType, int]:
        """유형별 정정 횟수."""
        with self._lock:
            counts: dict[CorrectionType, int] = {}
            for rec in self._corrections:
                counts[rec.correction_type] = counts.get(rec.correction_type, 0) + 1
            return counts

    def has_corrections(self, original_event_id: UUID) -> bool:
        """
        특정 이벤트에 정정이 있는지 여부.

        Args:
            original_event_id: 원본 이벤트 ID

        Returns:
            정정 존재 여부
        """
        with self._lock:
            return original_event_id in self._event_chains

    def get_latest_value(self, original_event_id: UUID) -> str | None:
        """
        특정 이벤트의 최종 정정 값.

        정정 체인의 마지막 corrected_value 반환.

        Args:
            original_event_id: 원본 이벤트 ID

        Returns:
            최종 정정 값 또는 None (정정 없음)
        """
        with self._lock:
            chain = self.get_correction_chain(original_event_id)
            if not chain:
                return None
            return chain[-1].corrected_value

    # =========================================================================
    # 무결성 검증
    # =========================================================================

    def verify_score_integrity(
        self,
        team_total_score: int,
        individual_scores_sum: int,
    ) -> IntegrityCheckResult:
        """
        스코어 무결성 검증.

        팀 총점 vs 선수별 득점 합산 일치 여부.

        Args:
            team_total_score: 팀 총점
            individual_scores_sum: 선수별 득점 합산

        Returns:
            IntegrityCheckResult
        """
        result = IntegrityCheckResult()
        diff = abs(team_total_score - individual_scores_sum)

        if diff > self._config.score_max_diff:
            result.add_violation(
                check_name="스코어 무결성",
                actual=str(individual_scores_sum),
                expected=str(team_total_score),
                diff=str(diff),
            )
            logger.warning(
                "스코어 무결성 위반: 팀총점=%d, 개인합산=%d, 차이=%d",
                team_total_score, individual_scores_sum, diff,
            )

        return result

    def verify_rebound_integrity(
        self,
        total_rebounds: int,
        total_missed_shots: int,
    ) -> IntegrityCheckResult:
        """
        리바운드 무결성 검증.

        총 리바운드 수 ≈ 총 미스 샷 수 (허용 차이 내).

        Args:
            total_rebounds: 총 리바운드 수
            total_missed_shots: 총 미스 샷 수

        Returns:
            IntegrityCheckResult
        """
        result = IntegrityCheckResult()
        diff = abs(total_rebounds - total_missed_shots)

        if diff > self._config.rebound_tolerance:
            result.add_violation(
                check_name="리바운드 무결성",
                actual=str(total_rebounds),
                expected=f"≈{total_missed_shots}",
                diff=str(diff),
            )
            logger.warning(
                "리바운드 무결성 위반: 리바운드=%d, 미스샷=%d, 차이=%d",
                total_rebounds, total_missed_shots, diff,
            )

        return result

    def verify_playing_time_integrity(
        self,
        player_times_sum_sec: float,
        expected_team_time_sec: float,
    ) -> IntegrityCheckResult:
        """
        출전 시간 무결성 검증.

        선수 출전 시간 합산 ≈ 5 × 경기 시간 (허용 오차 내).

        Args:
            player_times_sum_sec: 선수 출전 시간 합산 (초)
            expected_team_time_sec: 기대 팀 총 시간 (5인 × 경기 시간, 초)

        Returns:
            IntegrityCheckResult
        """
        result = IntegrityCheckResult()
        diff = abs(player_times_sum_sec - expected_team_time_sec)

        if diff > self._config.playing_time_tolerance_sec:
            result.add_violation(
                check_name="출전 시간 무결성",
                actual=f"{player_times_sum_sec:.1f}초",
                expected=f"{expected_team_time_sec:.1f}초",
                diff=f"{diff:.1f}초",
            )
            logger.warning(
                "출전 시간 무결성 위반: 합산=%.1f초, 기대=%.1f초, 차이=%.1f초",
                player_times_sum_sec, expected_team_time_sec, diff,
            )

        return result

    def run_full_integrity_check(
        self,
        team_total_score: int,
        individual_scores_sum: int,
        total_rebounds: int,
        total_missed_shots: int,
        player_times_sum_sec: float,
        expected_team_time_sec: float,
    ) -> IntegrityCheckResult:
        """
        전체 무결성 검증 (3항목 통합).

        Args:
            team_total_score: 팀 총점
            individual_scores_sum: 선수별 득점 합산
            total_rebounds: 총 리바운드 수
            total_missed_shots: 총 미스 샷 수
            player_times_sum_sec: 선수 출전 시간 합산 (초)
            expected_team_time_sec: 기대 팀 총 시간 (초)

        Returns:
            IntegrityCheckResult (통합 결과)
        """
        combined = IntegrityCheckResult()

        score_check = self.verify_score_integrity(
            team_total_score, individual_scores_sum
        )
        rebound_check = self.verify_rebound_integrity(
            total_rebounds, total_missed_shots
        )
        time_check = self.verify_playing_time_integrity(
            player_times_sum_sec, expected_team_time_sec
        )

        for check in (score_check, rebound_check, time_check):
            for violation in check.violations:
                combined.add_violation(*violation)

        return combined

    # =========================================================================
    # 팩토리 / 리셋
    # =========================================================================

    @classmethod
    def from_yaml(cls, cfg: dict) -> RecordCorrector:
        """YAML 설정에서 RecordCorrector 생성."""
        config = RecordCorrectorConfig.from_yaml(cfg)
        return cls(config)

    def reset(self) -> None:
        """전체 리셋 (새 경기 준비)."""
        with self._lock:
            self._corrections.clear()
            self._event_chains.clear()


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "RecordCorrectorConfig",
    "RecordCorrector",
    "IntegrityCheckResult",
]

__version__ = "1.0.0"
