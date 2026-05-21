# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/data_extraction
파일: coach_subtype_extractor.py
설명: CV-Coach 서브타입 학습 데이터 추출기.
      슛(13종) / 드리블(13종) / 패스(11종) 세 카테고리를
      하나의 세션에서 통합 추출.

      슛 13종: jump_shot/layup/dunk/floater/hook/fadeaway/stepback/pullup/
              turnaround/finger_roll/euro_step/reverse_layup/tip_in
      드리블 13종: crossover/between_legs/behind_back/spin/hesitation/
                  in_and_out/stepback/half_spin/double_crossover/
                  wrap_around/nash_dribble/push_dribble/pocket_dribble
      패스 11종: chest_pass/bounce_pass/overhead_pass/outlet_pass/lob_pass/
                alley_oop/no_look/behind_back/wrap_around/baseball_pass/
                skip_pass

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-25
버전: 1.0.0

의존성:
    - shared/dto/dataset_dto.py: Coach*SubtypeRecord, DatasetType
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Final, Literal
from uuid import uuid4

from shared.dto.dataset_dto import (
    CoachDribbleSubtypeRecord,
    CoachPassSubtypeRecord,
    CoachShotSubtypeRecord,
    DatasetMetadata,
    DatasetType,
    ExtractionResult,
    UploadStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================

# 슛 윈도우: 슛 시작 직전 30 + 릴리즈 후 30 (≈ 2초)
_SHOT_PRE_FRAMES: Final[int] = 30
_SHOT_POST_FRAMES: Final[int] = 30

# 드리블 윈도우: 동작 한 사이클 (≈ 1초)
_DRIBBLE_PRE_FRAMES: Final[int] = 15
_DRIBBLE_POST_FRAMES: Final[int] = 15

# 패스 윈도우: 패스 모션 + 도착 (≈ 1.5초)
_PASS_PRE_FRAMES: Final[int] = 20
_PASS_POST_FRAMES: Final[int] = 25

# 버퍼 (롤링 윈도우, 가장 큰 윈도우 + 여유)
_HISTORY_LEN: Final[int] = 120

# 카테고리
SubtypeCategory = Literal["shot", "dribble", "pass"]

# 검증용 클래스 셋
_SHOT_CLASSES: Final[frozenset[str]] = frozenset({
    "jump_shot", "layup", "dunk", "floater", "hook", "fadeaway",
    "stepback", "pullup", "turnaround", "finger_roll", "euro_step",
    "reverse_layup", "tip_in",
})
_DRIBBLE_CLASSES: Final[frozenset[str]] = frozenset({
    "crossover", "between_legs", "behind_back", "spin", "hesitation",
    "in_and_out", "stepback", "half_spin", "double_crossover",
    "wrap_around", "nash_dribble", "push_dribble", "pocket_dribble",
})
_PASS_CLASSES: Final[frozenset[str]] = frozenset({
    "chest_pass", "bounce_pass", "overhead_pass", "outlet_pass",
    "lob_pass", "alley_oop", "no_look", "behind_back", "wrap_around",
    "baseball_pass", "skip_pass",
})


# =============================================================================
# 설정
# =============================================================================

@dataclass(slots=True)
class CoachSubtypeExtractorConfig:
    """CoachSubtypeExtractor 설정."""

    shot_pre_frames: int = _SHOT_PRE_FRAMES
    shot_post_frames: int = _SHOT_POST_FRAMES
    dribble_pre_frames: int = _DRIBBLE_PRE_FRAMES
    dribble_post_frames: int = _DRIBBLE_POST_FRAMES
    pass_pre_frames: int = _PASS_PRE_FRAMES
    pass_post_frames: int = _PASS_POST_FRAMES
    min_confidence: float = 0.5
    # 시퀀스 충분도 (이 비율 미만은 학습 가치 낮음)
    min_sequence_ratio: float = 0.7
    max_buffer: int = 1000


# =============================================================================
# 추출 세션
# =============================================================================

@dataclass(slots=True)
class _CoachSession:
    """경기 단위 Coach 추출 상태."""

    game_id: str = ""
    metadata: DatasetMetadata = field(default_factory=DatasetMetadata)
    shot_records: list[CoachShotSubtypeRecord] = field(default_factory=list)
    dribble_records: list[CoachDribbleSubtypeRecord] = field(default_factory=list)
    pass_records: list[CoachPassSubtypeRecord] = field(default_factory=list)
    ball_history: deque = field(default_factory=lambda: deque(maxlen=_HISTORY_LEN))
    player_history: deque = field(default_factory=lambda: deque(maxlen=_HISTORY_LEN))
    # (frame, category, info)
    pending_events: list[tuple[int, str, dict]] = field(default_factory=list)


# =============================================================================
# 메인 추출기
# =============================================================================

class CoachSubtypeExtractor:
    """
    CV-Coach 서브타입(슛/드리블/패스) 학습 데이터 추출기.

    워크플로우:
        1. start_session(game_id)
        2. 매 프레임 push_frame(frame_idx, ball, players)
        3. 슛/드리블/패스 발생 시 push_shot/push_dribble/push_pass
        4. finalize() → ExtractionResult (3카테고리 레코드 통합)

    스레드 안전: yes (RLock).
    """

    def __init__(self, config: CoachSubtypeExtractorConfig | None = None) -> None:
        self._config = config or CoachSubtypeExtractorConfig()
        self._lock = threading.RLock()
        self._session: _CoachSession | None = None

    def start_session(self, game_id: str) -> None:
        """경기 시작."""
        with self._lock:
            self._session = _CoachSession(
                game_id=game_id,
                metadata=DatasetMetadata(
                    dataset_id=uuid4(),
                    dataset_type=DatasetType.COACH_SHOT_SUBTYPE,
                    source_game_ids=[game_id],
                    description="CV-Coach shot/dribble/pass subtype sequences",
                ),
            )
            logger.info("CoachSubtypeExtractor session 시작: game_id=%s", game_id)

    def push_frame(
        self,
        frame_index: int,
        ball_position: tuple[float, float, float] | None,
        player_keypoints: dict[int, dict[str, tuple[float, float, float]]],
    ) -> None:
        """매 프레임 호출."""
        with self._lock:
            if self._session is None:
                return
            self._session.ball_history.append((frame_index, ball_position))
            self._session.player_history.append((frame_index, player_keypoints))

            # 윈도우 채워진 pending 이벤트 flush
            ready: list[tuple[int, str, dict]] = []
            for fi, cat, info in self._session.pending_events:
                post = self._post_frames(cat)
                if frame_index - fi >= post:
                    ready.append((fi, cat, info))
            for ev in ready:
                self._flush(*ev)
                self._session.pending_events.remove(ev)

    def push_shot(
        self,
        frame_index: int,
        shot_subtype: str,
        shooter_id: int,
        is_made: bool = False,
        shot_distance_m: float = 0.0,
        contested: bool = False,
        confidence: float = 1.0,
        label_source: str = "auto",
    ) -> None:
        """슛 이벤트."""
        if shot_subtype not in _SHOT_CLASSES:
            logger.warning("Unknown shot_subtype: %s", shot_subtype)
            return
        self._push_event(frame_index, "shot", {
            "subtype": shot_subtype,
            "shooter_id": shooter_id,
            "is_made": is_made,
            "shot_distance_m": shot_distance_m,
            "contested": contested,
            "confidence": confidence,
            "label_source": label_source,
        })

    def push_dribble(
        self,
        frame_index: int,
        dribble_subtype: str,
        dribbler_id: int,
        duration_sec: float = 0.0,
        is_change_direction: bool = False,
        confidence: float = 1.0,
        label_source: str = "auto",
    ) -> None:
        """드리블 이벤트."""
        if dribble_subtype not in _DRIBBLE_CLASSES:
            logger.warning("Unknown dribble_subtype: %s", dribble_subtype)
            return
        self._push_event(frame_index, "dribble", {
            "subtype": dribble_subtype,
            "dribbler_id": dribbler_id,
            "duration_sec": duration_sec,
            "is_change_direction": is_change_direction,
            "confidence": confidence,
            "label_source": label_source,
        })

    def push_pass(
        self,
        frame_index: int,
        pass_subtype: str,
        passer_id: int,
        receiver_id: int | None = None,
        pass_distance_m: float = 0.0,
        is_assist: bool = False,
        confidence: float = 1.0,
        label_source: str = "auto",
    ) -> None:
        """패스 이벤트."""
        if pass_subtype not in _PASS_CLASSES:
            logger.warning("Unknown pass_subtype: %s", pass_subtype)
            return
        self._push_event(frame_index, "pass", {
            "subtype": pass_subtype,
            "passer_id": passer_id,
            "receiver_id": receiver_id,
            "pass_distance_m": pass_distance_m,
            "is_assist": is_assist,
            "confidence": confidence,
            "label_source": label_source,
        })

    def _push_event(self, frame_index: int, category: str, info: dict) -> None:
        with self._lock:
            if self._session is None:
                return
            if info["confidence"] < self._config.min_confidence:
                return
            self._session.pending_events.append((frame_index, category, info))

    def _pre_frames(self, category: str) -> int:
        if category == "shot":
            return self._config.shot_pre_frames
        if category == "dribble":
            return self._config.dribble_pre_frames
        return self._config.pass_pre_frames

    def _post_frames(self, category: str) -> int:
        if category == "shot":
            return self._config.shot_post_frames
        if category == "dribble":
            return self._config.dribble_post_frames
        return self._config.pass_post_frames

    def _slice_sequence(
        self,
        trigger_frame: int,
        pre: int,
        post: int,
        primary_id: int,
        secondary_id: int | None = None,
    ) -> tuple[
        list[int],
        list[tuple[float, float, float] | None],
        list[dict[str, tuple[float, float, float]]],
        list[dict[str, tuple[float, float, float]]] | None,
    ]:
        """버퍼에서 시퀀스 슬라이스."""
        if self._session is None:
            return [], [], [], None
        start_fi = trigger_frame - pre
        end_fi = trigger_frame + post
        frame_indices: list[int] = []
        ball_positions: list[tuple[float, float, float] | None] = []
        primary_kps: list[dict[str, tuple[float, float, float]]] = []
        secondary_kps: list[dict[str, tuple[float, float, float]]] = []
        for (fi, ball_pos), (_, kps) in zip(
            self._session.ball_history,
            self._session.player_history,
        ):
            if not (start_fi <= fi <= end_fi):
                continue
            frame_indices.append(fi)
            ball_positions.append(ball_pos)
            primary_kps.append(kps.get(primary_id, {}))
            if secondary_id is not None:
                secondary_kps.append(kps.get(secondary_id, {}))
        return (
            frame_indices,
            ball_positions,
            primary_kps,
            secondary_kps if secondary_id is not None else None,
        )

    def _flush(self, trigger_frame: int, category: str, info: dict) -> None:
        if self._session is None:
            return
        pre = self._pre_frames(category)
        post = self._post_frames(category)
        min_len = int((pre + post) * self._config.min_sequence_ratio)

        if category == "shot":
            frame_indices, ball_positions, kps, _ = self._slice_sequence(
                trigger_frame, pre, post, info["shooter_id"],
            )
            if len(frame_indices) < min_len:
                return
            self._session.shot_records.append(CoachShotSubtypeRecord(
                trigger_frame=trigger_frame,
                shot_subtype=info["subtype"],
                frame_indices=frame_indices,
                shooter_id=info["shooter_id"],
                shooter_keypoints=kps,
                ball_positions=ball_positions,
                is_made=info["is_made"],
                shot_distance_m=info["shot_distance_m"],
                contested=info["contested"],
                label_source=info["label_source"],
            ))
        elif category == "dribble":
            frame_indices, ball_positions, kps, _ = self._slice_sequence(
                trigger_frame, pre, post, info["dribbler_id"],
            )
            if len(frame_indices) < min_len:
                return
            self._session.dribble_records.append(CoachDribbleSubtypeRecord(
                trigger_frame=trigger_frame,
                dribble_subtype=info["subtype"],
                frame_indices=frame_indices,
                dribbler_id=info["dribbler_id"],
                dribbler_keypoints=kps,
                ball_positions=ball_positions,
                duration_sec=info["duration_sec"],
                is_change_direction=info["is_change_direction"],
                label_source=info["label_source"],
            ))
        else:  # pass
            frame_indices, ball_positions, passer_kps, _ = self._slice_sequence(
                trigger_frame, pre, post, info["passer_id"],
            )
            if len(frame_indices) < min_len:
                return
            self._session.pass_records.append(CoachPassSubtypeRecord(
                trigger_frame=trigger_frame,
                pass_subtype=info["subtype"],
                frame_indices=frame_indices,
                passer_id=info["passer_id"],
                receiver_id=info["receiver_id"],
                passer_keypoints=passer_kps,
                ball_trajectory=ball_positions,
                pass_distance_m=info["pass_distance_m"],
                is_assist=info["is_assist"],
                label_source=info["label_source"],
            ))

        total = (
            len(self._session.shot_records)
            + len(self._session.dribble_records)
            + len(self._session.pass_records)
        )
        if total > self._config.max_buffer:
            logger.warning("Coach buffer overflow — finalize 권장")

    def finalize(self) -> tuple[
        ExtractionResult,
        list[CoachShotSubtypeRecord],
        list[CoachDribbleSubtypeRecord],
        list[CoachPassSubtypeRecord],
    ] | None:
        """
        경기 종료.

        반환: (메타 ExtractionResult, shot_records, dribble_records, pass_records).
        ExtractionResult는 메타/업로드 추적 전용이며 records 필드를 갖지 않으므로
        세 카테고리 레코드는 별도 리스트로 노출.
        """
        with self._lock:
            if self._session is None:
                return None
            for fi, cat, info in self._session.pending_events:
                self._flush(fi, cat, info)
            self._session.pending_events.clear()

            shot_records = list(self._session.shot_records)
            dribble_records = list(self._session.dribble_records)
            pass_records = list(self._session.pass_records)
            total = len(shot_records) + len(dribble_records) + len(pass_records)

            self._session.metadata.total_records = total
            result = ExtractionResult(
                game_id=self._session.game_id,
                metadata=self._session.metadata,
                record_count=total,
                upload_status=UploadStatus.PENDING,
            )
            logger.info(
                "CoachSubtypeExtractor finalized: game_id=%s, "
                "shot=%d, dribble=%d, pass=%d",
                self._session.game_id,
                len(shot_records),
                len(dribble_records),
                len(pass_records),
            )
            self._session = None
            return result, shot_records, dribble_records, pass_records


__all__ = [
    "CoachSubtypeExtractor",
    "CoachSubtypeExtractorConfig",
    "SubtypeCategory",
]

__version__ = "1.0.0"
