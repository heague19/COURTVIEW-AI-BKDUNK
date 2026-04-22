# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/data_extraction
파일: tactical_sequence_extractor.py
설명: 전술 시퀀스 추출기
      - 한 점유 내 선수/공 궤적 + 전술/수비/결과 라벨을 시퀀스로 추출
      - 전술 인식 모델 학습 시 입력(궤적) → 출력(라벨) 쌍으로 활용
      - 포메이션 스냅샷 + 플레이 유형 라벨링

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import RLock
from uuid import UUID, uuid4

from shared.dto.dataset_dto import (
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
    TacticalSequenceRecord,
)

logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================

_MAX_EXTRACTIONS: int = 200
_MAX_RECORDS_PER_EXTRACTION: int = 10000
_MAX_TRAJECTORY_POINTS: int = 1000  # 프레임당 좌표 수 제한
_MAX_PLAYERS_PER_RECORD: int = 15   # 양 팀 + 심판


# =============================================================================
# 설정
# =============================================================================

@dataclass(slots=True)
class TacticalSequenceExtractorConfig:
    """전술 시퀀스 추출기 설정."""

    max_extractions: int = _MAX_EXTRACTIONS
    max_records_per_extraction: int = _MAX_RECORDS_PER_EXTRACTION
    max_trajectory_points: int = _MAX_TRAJECTORY_POINTS
    max_players_per_record: int = _MAX_PLAYERS_PER_RECORD


# =============================================================================
# 내부 데이터
# =============================================================================

@dataclass(slots=True)
class _ExtractionSession:
    """추출 세션 내부 데이터."""

    extraction_id: UUID
    game_id: str
    records: list[TacticalSequenceRecord]


# =============================================================================
# 추출기
# =============================================================================

class TacticalSequenceExtractor:
    """
    전술 시퀀스 추출기.

    점유 단위 선수 이동 궤적 + 전술 라벨을 수집.
    전술 인식 모델(play type recognizer)의 학습 데이터 생산.

    흐름:
        1. create_extraction(game_id) → 세션 생성
        2. add_record(...) → 궤적 + 라벨 쌍 추가
        3. build_result() → ExtractionResult 반환
    """

    __slots__ = (
        "_config", "_sessions", "_lock", "_total_records",
    )

    def __init__(self, config: TacticalSequenceExtractorConfig | None = None) -> None:
        self._config = config or TacticalSequenceExtractorConfig()
        self._sessions: dict[UUID, _ExtractionSession] = {}
        self._lock = RLock()
        self._total_records: int = 0

    # -- 속성 --

    @property
    def name(self) -> str:
        return "TacticalSequenceExtractor"

    @property
    def total_extractions(self) -> int:
        with self._lock:
            return len(self._sessions)

    @property
    def total_records(self) -> int:
        with self._lock:
            return self._total_records

    def __repr__(self) -> str:
        return (
            f"TacticalSequenceExtractor("
            f"extractions={self.total_extractions}, "
            f"records={self.total_records})"
        )

    # -- 세션 관리 --

    def create_extraction(self, game_id: str) -> UUID | None:
        """추출 세션 생성."""
        with self._lock:
            if len(self._sessions) >= self._config.max_extractions:
                logger.warning(
                    "추출 세션 한도 도달: %d", self._config.max_extractions,
                )
                return None
            eid = uuid4()
            self._sessions[eid] = _ExtractionSession(
                extraction_id=eid,
                game_id=game_id,
                records=[],
            )
            return eid

    def add_record(
        self,
        extraction_id: UUID,
        team_id: str,
        start_frame: int,
        end_frame: int,
        play_type_label: str = "",
        defense_type_label: str = "",
        result_label: str = "",
        formation_label: str = "",
        player_trajectories: dict[int, list[tuple[float, float]]] | None = None,
        ball_trajectory: list[tuple[float, float]] | None = None,
    ) -> bool:
        """전술 시퀀스 레코드 추가."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return False
            if len(session.records) >= self._config.max_records_per_extraction:
                logger.warning(
                    "레코드 한도 도달: %d", self._config.max_records_per_extraction,
                )
                return False

            # 프레임 범위 검증
            start_frame = max(0, start_frame)
            end_frame = max(start_frame, end_frame)

            # 궤적 truncation
            safe_trajectories: dict[int, list[tuple[float, float]]] = {}
            if player_trajectories:
                count = 0
                for tid, pts in player_trajectories.items():
                    if count >= self._config.max_players_per_record:
                        logger.warning(
                            "선수 궤적 한도 초과, %d명으로 제한",
                            self._config.max_players_per_record,
                        )
                        break
                    safe_trajectories[tid] = list(
                        pts[: self._config.max_trajectory_points],
                    )
                    count += 1

            safe_ball: list[tuple[float, float]] = []
            if ball_trajectory:
                safe_ball = list(
                    ball_trajectory[: self._config.max_trajectory_points],
                )

            record = TacticalSequenceRecord(
                team_id=team_id,
                start_frame=start_frame,
                end_frame=end_frame,
                play_type_label=play_type_label,
                defense_type_label=defense_type_label,
                result_label=result_label,
                formation_label=formation_label,
                player_trajectories=safe_trajectories,
                ball_trajectory=safe_ball,
            )
            session.records.append(record)
            self._total_records += 1
            return True

    # -- 추출 결과 --

    def build_result(self, extraction_id: UUID) -> ExtractionResult | None:
        """추출 결과 빌드."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            metadata = DatasetMetadata(
                dataset_type=DatasetType.TACTICAL_SEQUENCE,
                total_records=len(session.records),
                source_game_ids=[session.game_id],
                description="전술 시퀀스 추출 — 전술 인식 모델 학습용",
            )
            return ExtractionResult(
                extraction_id=session.extraction_id,
                game_id=session.game_id,
                metadata=metadata,
                record_count=len(session.records),
            )

    def get_records(self, extraction_id: UUID) -> list[TacticalSequenceRecord]:
        """레코드 목록 반환."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return []
            return list(session.records)

    # -- 조회 --

    def get_extraction_summary(self, extraction_id: UUID) -> dict[str, object] | None:
        """추출 세션 요약."""
        with self._lock:
            session = self._sessions.get(extraction_id)
            if session is None:
                return None
            play_type_dist: dict[str, int] = {}
            defense_type_dist: dict[str, int] = {}
            result_dist: dict[str, int] = {}
            total_frames = 0

            for r in session.records:
                if r.play_type_label:
                    play_type_dist[r.play_type_label] = (
                        play_type_dist.get(r.play_type_label, 0) + 1
                    )
                if r.defense_type_label:
                    defense_type_dist[r.defense_type_label] = (
                        defense_type_dist.get(r.defense_type_label, 0) + 1
                    )
                if r.result_label:
                    result_dist[r.result_label] = (
                        result_dist.get(r.result_label, 0) + 1
                    )
                total_frames += max(0, r.end_frame - r.start_frame)

            return {
                "game_id": session.game_id,
                "total_records": len(session.records),
                "play_type_distribution": dict(play_type_dist),
                "defense_type_distribution": dict(defense_type_dist),
                "result_distribution": dict(result_dist),
                "total_frames": total_frames,
            }

    # -- 삭제 / 유틸리티 --

    def delete_extraction(self, extraction_id: UUID) -> bool:
        """추출 세션 삭제."""
        with self._lock:
            session = self._sessions.pop(extraction_id, None)
            if session is None:
                return False
            self._total_records -= len(session.records)
            return True

    def get_stats(self) -> dict[str, object]:
        """전체 통계."""
        with self._lock:
            return {
                "total_extractions": len(self._sessions),
                "total_records": self._total_records,
            }

    def reset(self) -> None:
        """전체 초기화."""
        with self._lock:
            self._sessions.clear()
            self._total_records = 0


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "TacticalSequenceExtractor",
    "TacticalSequenceExtractorConfig",
]

__version__ = "1.0.0"
