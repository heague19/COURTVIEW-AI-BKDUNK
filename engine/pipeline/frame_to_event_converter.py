# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/pipeline
파일: frame_to_event_converter.py
설명: FramePipelineResult → EventPipeline 입력 변환기
      - motion_analysis 결과를 event_detection 입력 포맷으로 변환
      - frame_pipeline(🔴)과 event_pipeline(🟠) 사이의 다리 역할
      - 상태 관리: 공 궤적 이력, 소유 이력 버퍼, 이전 프레임 데이터

      데이터 흐름:
        FramePipelineResult (detection + pose + biomechanics)
          → FrameToEventConverter.convert()
          → EventFrameData (각 감지기별 *_input 속성 보유)
          → event_pipeline.process_events(frame_data=event_frame_data)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-10
버전: 1.0.0

의존성:
    - engine/pipeline/frame_pipeline.py: FramePipelineResult
    - engine/pipeline/event_pipeline.py: process_events(frame_data=)
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Final

logger: Final = logging.getLogger(__name__)

# ============================================================================
# 좌표계 주의 (Phase 15 Deferred: P15-13B-01)
# ============================================================================
# 현재 구현: 픽셀 좌표계 기반 (영상 직접 측정)
# 장기 로드맵: 코트 좌표계 (미터 단위) 전환 — 호모그래피 경유로 원근 왜곡 제거
# 전환 시 main 카메라 캘리브레이션 데이터 + pixel_to_court() 호출 필요
# 현재 상수들은 호환성 유지용 — 코트 좌표계 전환 시 재정의
# ============================================================================

# 픽셀 → 미터 변환 (림 직경 45cm ≈ 영상 ~15px 기준, 카메라 거리 가정)
_PX_TO_M: Final[float] = 0.03

# 소유 판정 거리 (픽셀, Phase 15에서 코트 좌표계 미터로 전환 예정)
_POSSESSION_DIST_PX: Final[float] = 80.0

# 소유 이력 버퍼 크기
_POSSESSION_HISTORY_SIZE: Final[int] = 30


@dataclass
class _PossessionRecord:
    """소유 이력 레코드."""
    frame_index: int
    player_id: int | None
    team_id: str
    timestamp_sec: float = 0.0


@dataclass
class EventFrameData:
    """
    EventPipeline이 기대하는 프레임 데이터.

    각 이벤트 감지기가 getattr(frame_data, "{name}_input")으로 접근합니다.
    FrameToEventConverter가 FramePipelineResult에서 추출하여 채웁니다.
    """

    # === EVENT cadence 감지기 6종 ===
    shot_release_input: Any = None
    shot_result_input: Any = None
    rebound_input: Any = None
    foul_input: Any = None
    screen_input: Any = None
    fast_break_input: Any = None
    drive_input: Any = None

    # === 역추적 감지기 4종 ===
    assist_input: Any = None
    block_input: Any = None
    steal_input: Any = None
    turnover_input: Any = None

    # === SPECIAL 감지기 3종 ===
    free_throw_input: Any = None
    box_out_input: Any = None
    jump_ball_input: Any = None

    # === 상시 활성 3종 ===
    possession_input: Any = None
    score_input: Any = None
    dead_ball_input: Any = None

    # === 실시간 모듈 ===
    realtime_advisor_input: Any = None
    substitution_optimizer_input: Any = None
    endgame_strategist_input: Any = None
    live_validator_input: Any = None
    correction_sync_input: Any = None
    action_classifier_input: Any = None

    # === 원본 참조 (필요 시 직접 접근) ===
    raw_frame_result: Any = None


class FrameToEventConverter:
    """
    FramePipelineResult → EventFrameData 변환기.

    상태 관리:
      - 공 위치 이력 (속도 계산용)
      - 소유 이력 버퍼 (어시스트/스틸/턴오버 역추적용)
      - 이전 프레임 ball-hoop 관계 (궤적 분석용)
    """

    __slots__ = (
        "_prev_ball_pos",
        "_prev_ball_y",
        "_ball_vy_history",
        "_possession_history",
        "_last_shot_frame",
        "_last_shot_team",
        "_last_shot_player",
        "_ball_state_name",
        "_ball_holder_id",
    )

    def __init__(self) -> None:
        # 공 위치/속도 이력
        self._prev_ball_pos: tuple[float, float] | None = None
        self._prev_ball_y: float = 0.0
        self._ball_vy_history: deque[float] = deque(maxlen=10)

        # 소유 이력 버퍼 (최근 30프레임)
        self._possession_history: deque[_PossessionRecord] = deque(
            maxlen=_POSSESSION_HISTORY_SIZE,
        )

        # 마지막 슛 시도 정보 (리바운드 판정용)
        self._last_shot_frame: int = -9999
        self._last_shot_team: str = ""
        self._last_shot_player: int | None = None

        # BallStateMachine 상태 (orchestrator에서 갱신)
        self._ball_state_name: str = "LOST"
        self._ball_holder_id: int | None = None

    # =================================================================
    # 외부 상태 업데이트 (orchestrator에서 호출)
    # =================================================================
    def update_ball_state(
        self,
        state_name: str,
        holder_id: int | None = None,
    ) -> None:
        """BallStateMachine 상태를 동기화."""
        self._ball_state_name = state_name
        self._ball_holder_id = holder_id

    def notify_shot_attempt(
        self,
        frame_index: int,
        shooter_id: int | None,
        team_id: str,
    ) -> None:
        """슛 시도 알림 (리바운드 판정용)."""
        self._last_shot_frame = frame_index
        self._last_shot_player = shooter_id
        self._last_shot_team = team_id

    # =================================================================
    # 메인 변환
    # =================================================================
    def convert(
        self,
        frame_result: Any,
        game_context: Any = None,
    ) -> EventFrameData:
        """
        FramePipelineResult → EventFrameData 변환.

        실제 detection/tracking 데이터에서 스칼라 값을 계산하여
        각 감지기가 직접 사용할 수 있는 형태로 매핑합니다.
        """
        if frame_result is None:
            return EventFrameData()

        data = EventFrameData(raw_frame_result=frame_result)

        # --- 원시 데이터 추출 ---
        detection = getattr(frame_result, "detection", None)
        pose = getattr(frame_result, "pose", None)
        tracking = getattr(frame_result, "tracking", None)
        fi = getattr(frame_result, "frame_index", 0)
        ts = getattr(game_context, "elapsed_sec", 0.0) if game_context else 0.0

        # 공/선수/골대 결과
        ball_result = getattr(detection, "ball_result", None) if detection else None
        player_result = getattr(detection, "player_result", None) if detection else None
        hoop_result = getattr(detection, "hoop_result", None) if detection else None

        # --- 공 위치 추출 ---
        ball_pos = self._extract_ball_position(ball_result)
        hoop_pos = self._extract_hoop_position(hoop_result)

        # --- 공-골대 관계 계산 ---
        ball_rim_dist_m = 999.0
        ball_through = False
        ball_above_rim = False
        ball_below_rim = False
        ball_vy = 0.0

        if ball_pos is not None and hoop_pos is not None:
            bx, by = ball_pos
            hx, hy = hoop_pos
            px_dist = ((bx - hx) ** 2 + (by - hy) ** 2) ** 0.5
            ball_rim_dist_m = px_dist * _PX_TO_M
            ball_above_rim = by < hy
            ball_below_rim = by > hy
            # 공이 골대 바로 근처에 있고 + 하강 중이면 through 판정
            ball_through = ball_rim_dist_m < 1.5

        # 공 수직 속도 (프레임 간 delta)
        if ball_pos is not None:
            by = ball_pos[1]
            ball_vy = (by - self._prev_ball_y) * _PX_TO_M * 30.0  # px/frame → m/s
            self._ball_vy_history.append(ball_vy)
            self._prev_ball_y = by
            self._prev_ball_pos = ball_pos

        # --- 소유자 추정 ---
        tracks = getattr(tracking, "active_tracks", None) or []
        holder_id, holder_team, ball_controlled, holder_dist = (
            self._estimate_ball_holder(ball_pos, tracks)
        )

        # 소유 이력 기록
        if ball_controlled and holder_id is not None:
            self._possession_history.append(_PossessionRecord(
                frame_index=fi,
                player_id=holder_id,
                team_id=holder_team,
                timestamp_sec=ts,
            ))

        # --- 직전 소유자 (어시스트/스틸 역추적용) ---
        prev_possessor_id, prev_possessor_team = self._get_previous_possessor(
            current_holder_id=holder_id,
        )

        # --- 리바운드 판정 보조 ---
        frames_since_shot = fi - self._last_shot_frame
        missed_shot_recent = 10 < frames_since_shot < 150  # 0.3~5초 이내

        # --- 선수 평균 속도 ---
        avg_speed = self._estimate_avg_player_speed(tracks)

        # --- 공통 컨텍스트 ---
        common = {
            "detection": detection,
            "pose": pose,
            "tracking": tracking,
            "game_context": game_context,
            "frame_index": fi,
            # 공 상태 (BallStateMachine)
            "ball_state_name": self._ball_state_name,
            # 소유자
            "ball_holder_tracking_id": holder_id,
            "ball_holder_team_id": holder_team or "",
            "ball_is_controlled": ball_controlled,
            # 공-골대 관계
            "ball_rim_distance_m": ball_rim_dist_m,
            "ball_through_hoop": ball_through,
            "ball_above_rim": ball_above_rim,
            "ball_below_rim": ball_below_rim,
            "ball_vertical_velocity_ms": ball_vy,
            # 직전 소유자
            "previous_possessor_id": prev_possessor_id,
            "previous_possessor_team_id": prev_possessor_team,
            # 리바운드 보조
            "missed_shot_recent": missed_shot_recent,
            "missed_shot_frame": self._last_shot_frame,
            "missed_shot_team_id": self._last_shot_team,
            "missed_shot_player_id": self._last_shot_player,
            # 선수 정보
            "players_on_court_count": len(tracks),
            "avg_player_speed_ms": avg_speed,
        }

        # === 슛 관련 (ShotEvent, Rebound) ===
        shot_input = _build_input(
            ball=ball_result, player=player_result, hoop=hoop_result,
            shooter_tracking_id=holder_id if self._ball_state_name == "SHOOTING" else None,
            shooter_team_id=holder_team if self._ball_state_name == "SHOOTING" else None,
            shot_attempted=self._ball_state_name == "SHOOTING",
            **common,
        )
        data.shot_release_input = shot_input
        data.shot_result_input = shot_input
        data.rebound_input = _build_input(
            ball=ball_result, player=player_result, hoop=hoop_result,
            ball_controlled=ball_controlled,
            ball_controller_id=holder_id,
            ball_controller_team_id=holder_team,
            **common,
        )

        # === 파울 ===
        data.foul_input = _build_input(
            player=player_result, **common,
        )

        # === 스크린/속공/드라이브 ===
        data.screen_input = _build_input(
            player=player_result, **common,
        )
        data.fast_break_input = _build_input(
            ball=ball_result, player=player_result,
            ball_speed_ms=abs(ball_vy) if ball_vy else 0.0,
            **common,
        )
        data.drive_input = _build_input(
            ball=ball_result, player=player_result,
            ball_handler_tracking_id=holder_id,
            ball_handler_speed_ms=avg_speed,
            **common,
        )

        # === 역추적 (어시스트/블록/스틸/턴오버) ===
        data.assist_input = _build_input(
            ball=ball_result, player=player_result,
            passer_tracking_id=prev_possessor_id,
            passer_team_id=prev_possessor_team,
            scorer_tracking_id=holder_id,
            scorer_team_id=holder_team,
            **common,
        )
        data.block_input = _build_input(
            ball=ball_result, player=player_result, hoop=hoop_result,
            **common,
        )
        data.steal_input = _build_input(
            ball=ball_result, player=player_result,
            new_possessor_id=holder_id,
            new_possessor_team_id=holder_team,
            **common,
        )
        data.turnover_input = _build_input(
            ball=ball_result, player=player_result,
            turnover_occurred=bool(
                prev_possessor_team
                and holder_team
                and prev_possessor_team != holder_team
                and prev_possessor_team != "unknown"
                and holder_team != "unknown"
            ),
            **common,
        )

        # === SPECIAL ===
        data.free_throw_input = _build_input(
            ball=ball_result, player=player_result, hoop=hoop_result,
            **common,
        )
        data.box_out_input = _build_input(
            player=player_result, **common,
        )
        data.jump_ball_input = _build_input(
            ball=ball_result, player=player_result, **common,
        )

        # === 상시 활성 3종 (FRAME cadence — orchestrator에서 별도 빌드) ===
        data.possession_input = _build_input(
            ball=ball_result, player=player_result,
            **common,
        )
        data.score_input = _build_input(
            ball=ball_result, hoop=hoop_result,
            **common,
        )
        data.dead_ball_input = _build_input(
            ball=ball_result,
            made_basket_detected=ball_through and ball_below_rim,
            **common,
        )

        # === 실시간 모듈 ===
        realtime_input = _build_input(**common)
        data.realtime_advisor_input = realtime_input
        data.substitution_optimizer_input = realtime_input
        data.endgame_strategist_input = realtime_input
        data.live_validator_input = realtime_input
        data.correction_sync_input = realtime_input
        data.action_classifier_input = _build_input(
            player=player_result, **common,
        )

        return data

    # =================================================================
    # 내부 헬퍼
    # =================================================================
    @staticmethod
    def _extract_ball_position(
        ball_result: Any,
    ) -> tuple[float, float] | None:
        """감지 결과에서 공 중심 좌표 추출."""
        if ball_result is None:
            return None
        fused = getattr(ball_result, "fused_objects", None)
        if not fused:
            return None
        b = fused[0]
        pos = getattr(b, "position", None)
        if pos is not None:
            return (pos.x, pos.y)
        bbox = getattr(b, "bbox", None)
        if bbox is not None:
            return (bbox.x + bbox.width / 2, bbox.y + bbox.height / 2)
        return None

    @staticmethod
    def _extract_hoop_position(
        hoop_result: Any,
    ) -> tuple[float, float] | None:
        """감지 결과에서 골대 중심 좌표 추출."""
        if hoop_result is None:
            return None
        fused = getattr(hoop_result, "fused_objects", None)
        if not fused:
            return None
        h = fused[0]
        pos = getattr(h, "position", None)
        if pos is not None:
            return (pos.x, pos.y)
        bbox = getattr(h, "bbox", None)
        if bbox is not None:
            return (bbox.x + bbox.width / 2, bbox.y + bbox.height / 2)
        return None

    @staticmethod
    def _estimate_ball_holder(
        ball_pos: tuple[float, float] | None,
        tracks: list,
    ) -> tuple[int | None, str, bool, float]:
        """
        공에 가장 가까운 선수 추정.

        Returns:
            (holder_id, team_id, is_controlled, distance_px)
        """
        if ball_pos is None or not tracks:
            return None, "", False, 9999.0

        bx, by = ball_pos
        min_dist = float("inf")
        best_id: int | None = None
        best_team = ""

        for track in tracks:
            bbox = getattr(track, "last_bbox", None)
            if bbox is None or len(bbox) < 4:
                continue
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            dist = ((bx - cx) ** 2 + (by - cy) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                best_id = getattr(track, "global_id", None)
                best_team = getattr(track, "team_id", "") or ""

        controlled = min_dist < _POSSESSION_DIST_PX and best_team != "unknown"
        if not controlled:
            best_id = None
            best_team = ""

        return best_id, best_team, controlled, min_dist

    def _get_previous_possessor(
        self,
        current_holder_id: int | None,
    ) -> tuple[int | None, str]:
        """
        현재 소유자와 다른 직전 소유자 반환 (어시스트/스틸 역추적).
        """
        for rec in reversed(self._possession_history):
            if rec.player_id != current_holder_id and rec.player_id is not None:
                return rec.player_id, rec.team_id
        return None, ""

    @staticmethod
    def _estimate_avg_player_speed(tracks: list) -> float:
        """트래킹 데이터에서 선수 평균 속도 추정 (m/s)."""
        if not tracks:
            return 0.0
        speeds = []
        for t in tracks:
            fs = getattr(t, "frames_since_seen", 0)
            if fs == 0:
                speeds.append(getattr(t, "total_frames", 1) * 0.1)
        return (sum(speeds) / len(speeds)) if speeds else 0.0


class _EventInput:
    """범용 이벤트 입력 객체 — 속성별 적절한 기본값 제공."""

    _DEFAULTS: dict[str, Any] = {
        # 게임 상태
        "ball_is_live": True,
        "ball_in_play": True,
        "game_clock_running": True,
        "is_dead_ball": False,
        "confidence": 0.5,
        "players_on_court_count": 10,
        # 점수 감지기
        "ball_rim_distance_m": 999.0,
        "ball_through_hoop": False,
        "ball_above_rim": False,
        "ball_below_rim": False,
        "rim_contact": False,
        "net_deflection": 0.0,
        "ball_vertical_velocity_ms": 0.0,
        # 이벤트 플래그
        "shot_attempted": False,
        "turnover_occurred": False,
        "free_throw_awarded": False,
        "offensive_rebound": False,
        "foul_detected": False,
        "made_basket_detected": False,
        "out_of_bounds_detected": False,
        "violation_detected": False,
        "players_in_huddle": False,
        "ball_held_by_referee": False,
        # 소유
        "ball_is_controlled": False,
        "ball_controlled": False,
        "ball_holder_team_id": "",
        "ball_holder_tracking_id": None,
        "ball_state_name": "LOST",
        # 역추적
        "previous_possessor_id": None,
        "previous_possessor_team_id": None,
        "passer_tracking_id": None,
        "passer_team_id": None,
        # 슛/리바운드
        "shooter_tracking_id": None,
        "shooter_team_id": None,
        "associated_shot_id": None,
        "missed_shot_recent": False,
        "missed_shot_frame": -9999,
        "missed_shot_team_id": "",
        "missed_shot_player_id": None,
        # 문자열
        "game_clock": "10:00",
    }

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getattr__(self, name: str) -> Any:
        # 1. 속성별 기본값 확인
        if name in _EventInput._DEFAULTS:
            return _EventInput._DEFAULTS[name]

        # 2. game_context에서 추출 시도
        ctx = self.__dict__.get("game_context")
        if ctx is not None:
            if name == "quarter":
                return getattr(ctx, "quarter", 1)
            if name == "home_score":
                return getattr(ctx, "home_score", 0)
            if name == "away_score":
                return getattr(ctx, "away_score", 0)
            if name == "timestamp_sec":
                return getattr(ctx, "elapsed_sec", 0.0)

        # 3. 숫자 비교 안전 기본값
        return 0

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def _build_input(**kwargs: Any) -> _EventInput:
    """키워드 인자로 _EventInput 생성."""
    return _EventInput(**kwargs)


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "FrameToEventConverter",
    "EventFrameData",
]

__version__ = "1.0.0"
