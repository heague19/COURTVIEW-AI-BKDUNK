# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/highlight
파일: clip_extractor.py
설명: 하이라이트 클립 시간 범위 산출 및 릴 구성
      - ScoredHighlight → HighlightClip DTO 변환
      - 이벤트 유형별 전후 패딩 적용
      - 연속 클립 병합 (max_gap_sec 이내)
      - 자동 릴 구성 (top_plays, scoring, defensive, player_spotlight)
      - 경기당 최대 클립 수 / 총 길이 제한

Processing Cadence: POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/highlight.yaml (clip, reel 섹션)
의존성: shared/constants/game_rule_constants.py, shared/dto/game_dto.py
소비자: video_editing, film_session, api_server
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.game_rule_constants import HighlightType

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500
_DEFAULT_FPS: Final[int] = 30


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class ClipExtractorConfig:
    """클립 추출기 설정."""

    # 기본 전후 패딩 (초)
    padding_before_sec: float = 3.0
    padding_after_sec: float = 3.0
    # 이벤트별 패딩 오버라이드 (event_key → (before, after))
    duration_overrides: dict[str, tuple[float, float]] = field(default_factory=dict)
    # 출력 FPS
    output_fps: int = _DEFAULT_FPS
    # 클립 제한
    max_clips_per_game: int = 50
    max_total_duration_sec: float = 600.0
    # 병합 설정
    merge_max_gap_sec: float = 5.0
    merge_max_duration_sec: float = 30.0
    # 릴 설정
    reel_configs: list[ReelConfig] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, cfg: dict) -> ClipExtractorConfig:
        """YAML 설정에서 생성."""
        clip = cfg.get("clip", {})
        pad = clip.get("padding", {})
        output = clip.get("output", {})
        merge = cfg.get("detection", {}).get("merge", {})
        reel_cfg = cfg.get("reel", {})

        # 패딩 오버라이드
        overrides: dict[str, tuple[float, float]] = {}
        for key, val in clip.get("duration_override", {}).items():
            overrides[key] = (
                val.get("before_sec", pad.get("before_event_sec", 3.0)),
                val.get("after_sec", pad.get("after_event_sec", 3.0)),
            )

        # 릴 설정
        reels: list[ReelConfig] = []
        for r in reel_cfg.get("auto_reels", []):
            reels.append(ReelConfig(
                reel_type=r.get("type", ""),
                description=r.get("description", ""),
                max_clips=r.get("max_clips", 10),
                max_clips_per_player=r.get("max_clips_per_player", 5),
                target_duration_sec=r.get("target_duration_sec", 120),
                sort_by=r.get("sort_by", "score_desc"),
                filter_events=r.get("filter_events", []),
                per_player=r.get("per_player", False),
            ))

        return cls(
            padding_before_sec=pad.get("before_event_sec", 3.0),
            padding_after_sec=pad.get("after_event_sec", 3.0),
            duration_overrides=overrides,
            output_fps=output.get("fps", _DEFAULT_FPS),
            max_clips_per_game=clip.get("max_clips_per_game", 50),
            max_total_duration_sec=clip.get("max_total_duration_sec", 600.0),
            merge_max_gap_sec=merge.get("max_gap_sec", 5.0),
            merge_max_duration_sec=merge.get("max_merged_duration_sec", 30.0),
            reel_configs=reels,
        )


@dataclass(slots=True)
class ReelConfig:
    """릴 생성 설정."""

    reel_type: str = ""
    description: str = ""
    max_clips: int = 10
    max_clips_per_player: int = 5
    target_duration_sec: float = 120.0
    sort_by: str = "score_desc"  # score_desc, time_asc
    filter_events: list[str] = field(default_factory=list)
    per_player: bool = False


# =============================================================================
# 입력
# =============================================================================
@dataclass(slots=True)
class ClipInput:
    """클립 추출 입력 (ScoredHighlight → ClipInput 변환용)."""

    event_id: str = ""
    event_key: str = ""
    team_id: str = ""
    highlight_type: HighlightType | None = None
    primary_player_id: int = 0
    related_player_ids: list[int] = field(default_factory=list)
    # 시간
    timestamp_sec: float = 0.0
    quarter: int = 1
    # 점수
    excitement_score: float = 0.0
    importance_score: float = 0.0
    # 컨텍스트
    home_score: int = 0
    away_score: int = 0
    is_clutch: bool = False
    confidence: float = 0.85


# =============================================================================
# 출력
# =============================================================================
@dataclass(slots=True)
class ExtractedClip:
    """추출된 클립 정보."""

    event_id: str = ""
    event_key: str = ""
    team_id: str = ""
    highlight_type: HighlightType | None = None
    primary_player_id: int = 0
    # 시간 범위
    start_time_sec: float = 0.0
    end_time_sec: float = 0.0
    duration_sec: float = 0.0
    # 프레임 범위
    start_frame: int = 0
    end_frame: int = 0
    # 점수
    excitement_score: float = 0.0
    importance_score: float = 0.0
    # 컨텍스트
    quarter: int = 1
    home_score: int = 0
    away_score: int = 0
    is_clutch: bool = False
    # 병합 여부
    is_merged: bool = False
    merged_event_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HighlightReel:
    """하이라이트 릴."""

    reel_type: str = ""
    description: str = ""
    clips: list[ExtractedClip] = field(default_factory=list)
    total_duration_sec: float = 0.0
    clip_count: int = 0


# =============================================================================
# 추출기
# =============================================================================
class ClipExtractor:
    """
    하이라이트 클립 추출기.

    이벤트 유형별 전후 패딩을 적용하여 클립 시간 범위를 산출하고,
    연속 클립을 병합하며, 릴을 자동 구성합니다.
    """

    def __init__(self, config: ClipExtractorConfig | None = None) -> None:
        self._config = config or ClipExtractorConfig()
        self._lock = RLock()
        self._clips: list[ExtractedClip] = []
        self._event_history: list[ClipInput] = []

    @property
    def name(self) -> str:
        return "ClipExtractor"

    # === 클립 추출 ===

    def extract_clip(self, inp: ClipInput) -> ExtractedClip | None:
        """
        하이라이트 이벤트에 대한 클립 시간 범위를 산출합니다.

        Args:
            inp: 클립 추출 입력

        Returns:
            추출된 클립 (제한 초과 시 None)
        """
        if inp.confidence < 0.40:
            return None

        with self._lock:
            # 히스토리 메모리 가드
            if len(self._event_history) >= _MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-_MAX_EVENT_HISTORY // 2:]
            self._event_history.append(inp)

            # 클립 수 제한 확인
            if len(self._clips) >= self._config.max_clips_per_game:
                # 가장 낮은 점수의 클립보다 높은 점수인지 확인
                min_clip = min(self._clips, key=lambda c: c.excitement_score)
                if inp.excitement_score <= min_clip.excitement_score:
                    return None
                # 교체
                self._clips.remove(min_clip)

            # 패딩 산출
            before, after = self._get_padding(inp.event_key)

            start = max(0.0, inp.timestamp_sec - before)
            end = inp.timestamp_sec + after
            duration = end - start

            clip = ExtractedClip(
                event_id=inp.event_id,
                event_key=inp.event_key,
                team_id=inp.team_id,
                highlight_type=inp.highlight_type,
                primary_player_id=inp.primary_player_id,
                start_time_sec=round(start, 2),
                end_time_sec=round(end, 2),
                duration_sec=round(duration, 2),
                start_frame=int(start * self._config.output_fps),
                end_frame=int(end * self._config.output_fps),
                excitement_score=inp.excitement_score,
                importance_score=inp.importance_score,
                quarter=inp.quarter,
                home_score=inp.home_score,
                away_score=inp.away_score,
                is_clutch=inp.is_clutch,
            )

            self._clips.append(clip)
            return clip

    # === 병합 ===

    def merge_overlapping_clips(self) -> list[ExtractedClip]:
        """
        시간이 겹치거나 가까운 클립을 병합합니다.

        Returns:
            병합된 클립 목록
        """
        with self._lock:
            if len(self._clips) < 2:
                return list(self._clips)

            sorted_clips = sorted(self._clips, key=lambda c: c.start_time_sec)
            merged: list[ExtractedClip] = [sorted_clips[0]]

            for clip in sorted_clips[1:]:
                last = merged[-1]
                gap = clip.start_time_sec - last.end_time_sec
                potential_duration = clip.end_time_sec - last.start_time_sec

                if (
                    gap <= self._config.merge_max_gap_sec
                    and potential_duration <= self._config.merge_max_duration_sec
                ):
                    # 병합
                    merged_clip = ExtractedClip(
                        event_id=last.event_id,
                        event_key=last.event_key,
                        team_id=last.team_id,
                        highlight_type=last.highlight_type,
                        primary_player_id=last.primary_player_id,
                        start_time_sec=last.start_time_sec,
                        end_time_sec=max(last.end_time_sec, clip.end_time_sec),
                        duration_sec=round(
                            max(last.end_time_sec, clip.end_time_sec) - last.start_time_sec, 2
                        ),
                        start_frame=last.start_frame,
                        end_frame=max(last.end_frame, clip.end_frame),
                        excitement_score=max(last.excitement_score, clip.excitement_score),
                        importance_score=max(last.importance_score, clip.importance_score),
                        quarter=last.quarter,
                        home_score=clip.home_score,
                        away_score=clip.away_score,
                        is_clutch=last.is_clutch or clip.is_clutch,
                        is_merged=True,
                        merged_event_ids=(
                            last.merged_event_ids + [last.event_id, clip.event_id]
                            if last.is_merged
                            else [last.event_id, clip.event_id]
                        ),
                    )
                    merged[-1] = merged_clip
                else:
                    merged.append(clip)

            return merged

    # === 릴 생성 ===

    def build_reel(self, reel_type: str) -> HighlightReel:
        """
        지정된 유형의 하이라이트 릴을 생성합니다.

        Args:
            reel_type: 릴 유형 (top_plays, scoring_highlights, defensive_highlights, player_spotlight)

        Returns:
            하이라이트 릴
        """
        with self._lock:
            # 릴 설정 찾기
            reel_cfg = None
            for rc in self._config.reel_configs:
                if rc.reel_type == reel_type:
                    reel_cfg = rc
                    break

            if reel_cfg is None:
                reel_cfg = ReelConfig(reel_type=reel_type, description=reel_type)

            # 필터 적용
            candidates = list(self._clips)
            if reel_cfg.filter_events:
                candidates = [c for c in candidates if c.event_key in reel_cfg.filter_events]

            # 정렬
            if reel_cfg.sort_by == "score_desc":
                candidates.sort(key=lambda c: c.excitement_score, reverse=True)
            elif reel_cfg.sort_by == "time_asc":
                candidates.sort(key=lambda c: c.start_time_sec)

            # 목표 시간/수 제한
            selected: list[ExtractedClip] = []
            total_dur = 0.0
            for c in candidates:
                if len(selected) >= reel_cfg.max_clips:
                    break
                if total_dur + c.duration_sec > reel_cfg.target_duration_sec:
                    continue
                selected.append(c)
                total_dur += c.duration_sec

            return HighlightReel(
                reel_type=reel_cfg.reel_type,
                description=reel_cfg.description,
                clips=selected,
                total_duration_sec=round(total_dur, 2),
                clip_count=len(selected),
            )

    def build_player_reel(self, player_id: int, max_clips: int = 5) -> HighlightReel:
        """
        선수별 하이라이트 릴 생성.

        Args:
            player_id: 선수 트래킹 ID
            max_clips: 최대 클립 수

        Returns:
            선수별 하이라이트 릴
        """
        with self._lock:
            player_clips = sorted(
                [c for c in self._clips if c.primary_player_id == player_id],
                key=lambda c: c.excitement_score,
                reverse=True,
            )[:max_clips]

            total_dur = sum(c.duration_sec for c in player_clips)
            return HighlightReel(
                reel_type="player_spotlight",
                description=f"Player {player_id} Highlights",
                clips=player_clips,
                total_duration_sec=round(total_dur, 2),
                clip_count=len(player_clips),
            )

    # === 조회 ===

    def get_all_clips(self) -> list[ExtractedClip]:
        """전체 클립 목록 (excitement 내림차순)."""
        with self._lock:
            return sorted(self._clips, key=lambda c: c.excitement_score, reverse=True)

    def get_total_duration(self) -> float:
        """전체 하이라이트 총 길이 (초)."""
        with self._lock:
            return round(sum(c.duration_sec for c in self._clips), 2)

    def get_clips_by_quarter(self, quarter: int) -> list[ExtractedClip]:
        """쿼터별 클립 목록."""
        with self._lock:
            return sorted(
                [c for c in self._clips if c.quarter == quarter],
                key=lambda c: c.start_time_sec,
            )

    def get_event_history(self) -> list[ClipInput]:
        """이벤트 히스토리."""
        with self._lock:
            return list(self._event_history)

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._clips.clear()
            self._event_history.clear()

    # === 내부 메서드 ===

    def _get_padding(self, event_key: str) -> tuple[float, float]:
        """이벤트 키에 대한 전후 패딩 반환."""
        override = self._config.duration_overrides.get(event_key)
        if override:
            return override
        return self._config.padding_before_sec, self._config.padding_after_sec


# =============================================================================
# 모듈 export
# =============================================================================
__all__ = [
    "ClipExtractorConfig",
    "ClipExtractor",
    "ClipInput",
    "ExtractedClip",
    "HighlightReel",
    "ReelConfig",
]

__version__ = "1.0.0"
