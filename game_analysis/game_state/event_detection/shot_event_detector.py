# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: shot_event_detector.py
설명: 슛 이벤트 감지기 — 슛 릴리스 감지 + 결과 판정 + 유형 분류
      릴리스 감지: 손목-어깨 높이차, 팔꿈치 신전 각도, 팔 각속도
      결과 판정: 공-림 근접, 네트 흔들림, 백보드 접촉
      유형 분류: 13종 (레이업~팁인), 거리/높이/동작 기반

      학술 근거:
        Miller, S. & Bartlett, R. (1996). "The Relationship Between
        Basketball Shooting Kinematics, Distance and Playing Position."
        J. Sports Sciences, 14(3), 243-253.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (shot_detection 섹션)
의존성: shared.constants.game_rule_constants, shared.dto.game_dto
소비자: game_analysis/statistics/, game_analysis/event_detection/assist_detector
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final
from uuid import UUID, uuid4

from shared.constants.game_rule_constants import (
    GameEventType,
    ShotType,
    ShotResult,
)
from shared.dto.game_dto import GameEvent, ShotAttempt
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500
_MAX_ACTIVE_EVENTS: Final[int] = 10


# =============================================================================
# 슛 릴리스 감지 입력 데이터
# =============================================================================
@dataclass(slots=True)
class ShotReleaseInput:
    """슛 릴리스 감지를 위한 프레임 데이터."""

    frame_index: int
    timestamp_sec: float
    player_tracking_id: int
    team_id: str = ""
    # 포즈 기반 특징
    wrist_above_shoulder_m: float = 0.0    # 손목-어깨 높이차 (미터)
    elbow_extension_deg: float = 0.0        # 팔꿈치 신전 각도 (도)
    arm_angular_velocity_degs: float = 0.0  # 팔 각속도 (도/초)
    release_height_ratio: float = 0.0       # 키 대비 릴리스 높이 비율
    # 공 정보
    ball_position_x: float = 0.0            # 공 위치 X (코트 정규화)
    ball_position_y: float = 0.0            # 공 위치 Y (코트 정규화)
    ball_distance_to_hoop_m: float = 0.0    # 공-골대 거리
    # 선수 정보
    player_court_x: float = 0.0             # 선수 코트 위치 X
    player_court_y: float = 0.0             # 선수 코트 위치 Y
    player_height_ratio: float = 1.0        # 림 대비 높이 비율
    # 동작 정보
    dribbles_before_shot: int = 0           # 슛 전 드리블 수
    time_with_ball_sec: float = 0.0         # 공 소유 시간
    # 게임 상태
    quarter: int = 1
    game_clock: str = ""


# =============================================================================
# 슛 결과 판정 입력 데이터
# =============================================================================
@dataclass(slots=True)
class ShotResultInput:
    """슛 결과 판정을 위한 프레임 데이터."""

    frame_index: int
    timestamp_sec: float
    # 공-림 관계
    ball_rim_distance_m: float = 999.0      # 공-림 거리
    ball_through_hoop: bool = False         # 공 통과 여부
    net_deflection: float = 0.0             # 네트 변형 정도 (0~1)
    backboard_contact: bool = False         # 백보드 접촉
    rim_contact: bool = False               # 림 접촉
    # 신뢰도
    confidence: float = 0.0


# =============================================================================
# ShotEventDetectorConfig
# =============================================================================
@dataclass(slots=True)
class ShotEventDetectorConfig:
    """
    슛 이벤트 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → shot_detection
    """

    # 릴리스 감지
    wrist_above_shoulder_min_m: float = 0.1
    elbow_extension_min_deg: float = 120.0
    arm_velocity_min_degs: float = 300.0
    release_height_min_ratio: float = 0.9
    min_shooting_motion_frames: int = 4

    # 결과 판정
    ball_rim_proximity_m: float = 0.3
    made_shot_confidence: float = 0.85
    rim_contact_detection: bool = True
    net_motion_threshold: float = 0.5
    backboard_contact_detection: bool = True

    # 유형 분류
    layup_max_distance_m: float = 2.0
    dunk_min_height_ratio: float = 1.05
    floater_height_range_m: tuple[float, float] = (2.5, 4.0)
    hook_shot_arm_angle_deg: float = 90.0
    three_point_distance_fiba_m: float = 6.75
    three_point_distance_nba_m: float = 7.24
    catch_and_shoot_max_touch_sec: float = 2.0
    pull_up_min_dribbles: int = 1

    # 멀티뷰
    min_cameras_for_confirmation: int = 2
    angle_disagreement_max_deg: float = 15.0

    # 결과 판정 최대 대기 프레임
    max_result_wait_frames: int = 45  # 1.5초 (30fps)

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> ShotEventDetectorConfig:
        """YAML 설정 로드."""
        shot = cfg.get("shot_detection", cfg)
        release = shot.get("release_detection", {})
        result = shot.get("result_detection", {})
        type_cls = shot.get("type_classification", {})
        mv = shot.get("multi_view", {})
        common = cfg.get("common", {})

        floater_range = type_cls.get("floater_height_range_m", [2.5, 4.0])
        if isinstance(floater_range, list) and len(floater_range) == 2:
            floater_tuple = (float(floater_range[0]), float(floater_range[1]))
        else:
            floater_tuple = (2.5, 4.0)

        return cls(
            wrist_above_shoulder_min_m=float(release.get("wrist_above_shoulder_min_m", 0.1)),
            elbow_extension_min_deg=float(release.get("elbow_extension_min_deg", 120.0)),
            arm_velocity_min_degs=float(release.get("arm_velocity_min_degs", 300.0)),
            release_height_min_ratio=float(release.get("release_height_min_ratio", 0.9)),
            min_shooting_motion_frames=int(release.get("min_shooting_motion_frames", 4)),
            ball_rim_proximity_m=float(result.get("ball_rim_proximity_m", 0.3)),
            made_shot_confidence=float(result.get("made_shot_confidence", 0.85)),
            rim_contact_detection=bool(result.get("rim_contact_detection", True)),
            net_motion_threshold=float(result.get("net_motion_threshold", 0.5)),
            backboard_contact_detection=bool(result.get("backboard_contact_detection", True)),
            layup_max_distance_m=float(type_cls.get("layup_max_distance_m", 2.0)),
            dunk_min_height_ratio=float(type_cls.get("dunk_min_height_ratio", 1.05)),
            floater_height_range_m=floater_tuple,
            hook_shot_arm_angle_deg=float(type_cls.get("hook_shot_arm_angle_deg", 90.0)),
            three_point_distance_fiba_m=float(type_cls.get("three_point_distance_fiba_m", 6.75)),
            three_point_distance_nba_m=float(type_cls.get("three_point_distance_nba_m", 7.24)),
            catch_and_shoot_max_touch_sec=float(type_cls.get("catch_and_shoot_max_touch_sec", 2.0)),
            pull_up_min_dribbles=int(type_cls.get("pull_up_min_dribbles", 1)),
            min_cameras_for_confirmation=int(mv.get("min_cameras_for_confirmation", 2)),
            angle_disagreement_max_deg=float(mv.get("angle_disagreement_max_deg", 15.0)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# 진행 중인 슛 시도 추적
# =============================================================================
@dataclass(slots=True)
class _PendingShotAttempt:
    """아직 결과가 확정되지 않은 슛 시도."""

    shot_id: UUID
    player_tracking_id: int
    team_id: str
    release_frame: int
    release_timestamp_sec: float
    shot_type: ShotType
    distance_to_hoop_m: float
    court_x: float
    court_y: float
    quarter: int
    game_clock: str
    release_confidence: float
    motion_frame_count: int  # 슈팅 모션 프레임 수
    result: ShotResult | None = None
    result_frame: int | None = None
    result_confidence: float = 0.0
    points: int = 0


# =============================================================================
# ShotEventDetector
# =============================================================================
class ShotEventDetector:
    """
    슛 이벤트 감지기.

    Cadence: EVENT (<10ms)

    3단계 파이프라인:
      1. 릴리스 감지 — 포즈 데이터 기반 슈팅 모션 인식
      2. 결과 판정 — 공-림 관계, 네트 변형 기반 성공/실패 판정
      3. 유형 분류 — 거리/높이/동작 패턴 기반 13종 분류
    """

    def __init__(self, config: ShotEventDetectorConfig | None = None) -> None:
        self._config: Final = config or ShotEventDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []
        self._shot_attempts: list[ShotAttempt] = []

        # 진행 중인 슛 시도
        self._pending_shots: list[_PendingShotAttempt] = []

        # 슈팅 모션 버퍼 (선수별)
        self._motion_buffers: dict[int, list[ShotReleaseInput]] = {}

        logger.info("ShotEventDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "ShotEventDetector"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> GameModuleState:
        return self._state

    @property
    def metrics(self) -> GameModuleMetrics:
        return self._metrics

    @property
    def supported_events(self) -> list[str]:
        return [
            GameEventType.SHOT_ATTEMPT.value,
            GameEventType.SHOT_MADE.value,
            GameEventType.SHOT_MISSED.value,
        ]

    @property
    def pending_shot_count(self) -> int:
        """결과 대기 중인 슛 수."""
        with self._lock:
            return len(self._pending_shots)

    @property
    def total_shots_detected(self) -> int:
        """총 감지된 슛 시도 수."""
        with self._lock:
            return len(self._shot_attempts)

    # -- 릴리스 감지 --

    def process_release(self, data: ShotReleaseInput) -> GameEvent | None:
        """
        슛 릴리스 감지.

        포즈 데이터를 분석하여 슈팅 모션을 감지하고,
        기준 프레임 수 이상 연속되면 슛 시도로 확정합니다.

        Args:
            data: 포즈 기반 릴리스 입력 데이터

        Returns:
            SHOT_ATTEMPT GameEvent (감지 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._detect_release(data)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if event:
                    self._metrics.update_from_event_result(
                        GameEventResult.success_result(
                            data=[event], confidence=event.confidence,
                            processing_time_ms=elapsed_ms, events_detected=1,
                        ),
                        elapsed_ms,
                    )
                return event
            except Exception as e:
                logger.error("슛 릴리스 감지 오류: %s", e)
                return None

    def _detect_release(self, data: ShotReleaseInput) -> GameEvent | None:
        """릴리스 감지 내부 로직."""
        cfg = self._config
        pid = data.player_tracking_id

        # 슈팅 모션 조건 확인
        is_shooting = (
            data.wrist_above_shoulder_m >= cfg.wrist_above_shoulder_min_m
            and data.elbow_extension_deg >= cfg.elbow_extension_min_deg
            and data.arm_angular_velocity_degs >= cfg.arm_velocity_min_degs
            and data.release_height_ratio >= cfg.release_height_min_ratio
        )

        # 모션 버퍼 관리
        if is_shooting:
            buf = self._motion_buffers.setdefault(pid, [])
            buf.append(data)

            # 최소 프레임 수 충족 시 슛 시도 확정
            if len(buf) >= cfg.min_shooting_motion_frames:
                event = self._confirm_shot_attempt(buf)
                self._motion_buffers.pop(pid, None)
                return event
        else:
            # 모션 끊김 → 버퍼 리셋
            self._motion_buffers.pop(pid, None)

        return None

    def _confirm_shot_attempt(self, motion_frames: list[ShotReleaseInput]) -> GameEvent:
        """슈팅 모션 확정 → SHOT_ATTEMPT 이벤트 생성."""
        last = motion_frames[-1]

        # 유형 분류
        shot_type = self._classify_shot_type(last)

        # 릴리스 신뢰도 (모션 프레임 수 + 각도/속도 품질)
        confidence = self._calculate_release_confidence(motion_frames)

        # 펜딩 슛 등록
        shot_id = uuid4()
        pending = _PendingShotAttempt(
            shot_id=shot_id,
            player_tracking_id=last.player_tracking_id,
            team_id=last.team_id,
            release_frame=last.frame_index,
            release_timestamp_sec=last.timestamp_sec,
            shot_type=shot_type,
            distance_to_hoop_m=last.ball_distance_to_hoop_m,
            court_x=last.player_court_x,
            court_y=last.player_court_y,
            quarter=last.quarter,
            game_clock=last.game_clock,
            release_confidence=confidence,
            motion_frame_count=len(motion_frames),
        )
        self._pending_shots.append(pending)

        # 펜딩 제한
        if len(self._pending_shots) > _MAX_ACTIVE_EVENTS:
            self._pending_shots.pop(0)

        # SHOT_ATTEMPT 이벤트
        event = GameEvent(
            event_id=shot_id,
            event_type=GameEventType.SHOT_ATTEMPT,
            primary_player_id=last.player_tracking_id,
            team_id=last.team_id,
            court_x=last.player_court_x,
            court_y=last.player_court_y,
            frame_number=last.frame_index,
            timestamp=last.timestamp_sec,
            quarter=last.quarter,
            game_clock=last.game_clock,
            confidence=confidence,
            description=f"슛 시도: {shot_type.value} (거리 {last.ball_distance_to_hoop_m:.1f}m)",
        )
        self._event_history.append(event)
        self._trim_history()

        logger.debug(
            "슛 시도 감지: player=%d, type=%s, dist=%.1fm, conf=%.2f",
            last.player_tracking_id, shot_type.value,
            last.ball_distance_to_hoop_m, confidence,
        )
        return event

    # -- 결과 판정 --

    def process_result(self, data: ShotResultInput) -> GameEvent | None:
        """
        슛 결과 판정.

        공-림 관계 데이터를 분석하여 가장 최근 펜딩 슛의 결과를 확정합니다.

        Args:
            data: 공-림 관계 입력 데이터

        Returns:
            SHOT_MADE 또는 SHOT_MISSED GameEvent (확정 시) 또는 None
        """
        t0 = time.perf_counter()
        with self._lock:
            try:
                event = self._judge_result(data)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if event:
                    self._metrics.update_from_event_result(
                        GameEventResult.success_result(
                            data=[event], confidence=event.confidence,
                            processing_time_ms=elapsed_ms, events_detected=1,
                        ),
                        elapsed_ms,
                    )
                return event
            except Exception as e:
                logger.error("슛 결과 판정 오류: %s", e)
                return None

    def _judge_result(self, data: ShotResultInput) -> GameEvent | None:
        """결과 판정 내부 로직."""
        if not self._pending_shots:
            return None

        cfg = self._config
        pending = self._pending_shots[0]  # 가장 오래된 펜딩

        # 타임아웃 체크 (최대 대기 프레임 초과)
        frame_gap = data.frame_index - pending.release_frame
        if frame_gap > cfg.max_result_wait_frames:
            # 타임아웃 → 미스 처리
            return self._finalize_shot(pending, ShotResult.MISSED, data.frame_index, 0.5)

        # 공-림 근접 확인
        if data.ball_rim_distance_m > cfg.ball_rim_proximity_m:
            return None  # 아직 림 근처에 도달하지 않음

        # 성공 판정
        if data.ball_through_hoop and data.confidence >= cfg.made_shot_confidence:
            # 네트 변형 보조 확인
            net_ok = data.net_deflection >= cfg.net_motion_threshold
            if net_ok or not cfg.rim_contact_detection:
                return self._finalize_shot(pending, ShotResult.MADE, data.frame_index, data.confidence)

        # 림 접촉 + 공 미통과 → 미스
        if data.rim_contact and not data.ball_through_hoop:
            return self._finalize_shot(pending, ShotResult.MISSED, data.frame_index, data.confidence)

        return None

    def _finalize_shot(
        self,
        pending: _PendingShotAttempt,
        result: ShotResult,
        result_frame: int,
        confidence: float,
    ) -> GameEvent:
        """슛 결과 확정 → 이벤트 생성 + ShotAttempt 기록."""
        self._pending_shots.remove(pending)

        pending.result = result
        pending.result_frame = result_frame
        pending.result_confidence = confidence

        # 점수 계산
        points = 0
        if result == ShotResult.MADE or result == ShotResult.AND_ONE:
            points = self._calculate_points(pending.distance_to_hoop_m, pending.shot_type)
        pending.points = points

        # 이벤트 유형 결정
        if result == ShotResult.MADE or result == ShotResult.AND_ONE:
            event_type = GameEventType.SHOT_MADE
        else:
            event_type = GameEventType.SHOT_MISSED

        event = GameEvent(
            event_id=pending.shot_id,
            event_type=event_type,
            primary_player_id=pending.player_tracking_id,
            team_id=pending.team_id,
            court_x=pending.court_x,
            court_y=pending.court_y,
            frame_number=result_frame,
            timestamp=pending.release_timestamp_sec,
            quarter=pending.quarter,
            game_clock=pending.game_clock,
            points=points,
            confidence=confidence,
            description=(
                f"{'득점' if points > 0 else '미스'}: "
                f"{pending.shot_type.value} {points}점 "
                f"(거리 {pending.distance_to_hoop_m:.1f}m)"
            ),
        )
        self._event_history.append(event)

        # ShotAttempt DTO 기록
        from shared.constants.game_rule_constants import CourtZone
        shot_attempt = ShotAttempt(
            shot_id=pending.shot_id,
            player_tracking_id=pending.player_tracking_id,
            team_id=pending.team_id,
            shot_type=pending.shot_type,
            result=result,
            points=points,
            court_zone=CourtZone.PAINT_CENTER if pending.distance_to_hoop_m <= 2.0 else CourtZone.MID_CENTER,
            shot_x=pending.court_x,
            shot_y=pending.court_y,
            distance_meters=pending.distance_to_hoop_m,
            frame_number=pending.release_frame,
            timestamp=pending.release_timestamp_sec,
            quarter=pending.quarter,
            game_clock=pending.game_clock,
            confidence=confidence,
        )
        self._shot_attempts.append(shot_attempt)
        self._trim_history()

        logger.info(
            "슛 결과 확정: player=%d, %s, %s, %d점",
            pending.player_tracking_id, pending.shot_type.value,
            result.value, points,
        )
        return event

    # -- 유형 분류 --

    def _classify_shot_type(self, data: ShotReleaseInput) -> ShotType:
        """슛 유형 분류 (13종)."""
        cfg = self._config
        dist = data.ball_distance_to_hoop_m
        height = data.player_height_ratio

        # 덩크: 림 위 높이
        if height >= cfg.dunk_min_height_ratio and dist <= cfg.layup_max_distance_m:
            return ShotType.DUNK

        # 레이업: 근거리
        if dist <= cfg.layup_max_distance_m:
            return ShotType.LAYUP

        # 플로터: 중거리 + 높은 릴리스
        if (cfg.floater_height_range_m[0] <= data.release_height_ratio * 2.0
                <= cfg.floater_height_range_m[1]):
            if dist <= 4.0:
                return ShotType.FLOATER

        # 훅샷: 옆팔 각도
        if data.elbow_extension_deg < cfg.hook_shot_arm_angle_deg and dist <= 4.0:
            return ShotType.HOOK_SHOT

        # 3점슛: FIBA 기준 거리
        if dist >= cfg.three_point_distance_fiba_m:
            # 캐치앤슛 vs 풀업
            if data.time_with_ball_sec <= cfg.catch_and_shoot_max_touch_sec:
                return ShotType.CATCH_AND_SHOOT
            if data.dribbles_before_shot >= cfg.pull_up_min_dribbles:
                return ShotType.PULL_UP
            return ShotType.THREE_POINTER

        # 중거리 세부 분류
        if data.dribbles_before_shot >= cfg.pull_up_min_dribbles:
            return ShotType.PULL_UP

        if data.time_with_ball_sec <= cfg.catch_and_shoot_max_touch_sec:
            return ShotType.CATCH_AND_SHOOT

        return ShotType.JUMP_SHOT

    def _calculate_release_confidence(self, frames: list[ShotReleaseInput]) -> float:
        """릴리스 신뢰도 계산."""
        cfg = self._config
        if not frames:
            return 0.0

        # 프레임 수 기여 (최소 충족 시 0.6, 추가 프레임마다 +0.05, 최대 0.3 추가)
        frame_score = min(0.3, (len(frames) - cfg.min_shooting_motion_frames) * 0.05)
        base = 0.6 + frame_score

        # 각도/속도 품질 (최대 0.1)
        last = frames[-1]
        quality = 0.0
        if last.elbow_extension_deg >= 150.0:  # 높은 신전
            quality += 0.05
        if last.arm_angular_velocity_degs >= 400.0:  # 빠른 각속도
            quality += 0.05

        return min(1.0, base + quality)

    def _calculate_points(self, distance_m: float, shot_type: ShotType) -> int:
        """득점 계산 (2점/3점)."""
        if shot_type == ShotType.FREE_THROW:
            return 1
        if distance_m >= self._config.three_point_distance_fiba_m:
            return 3
        return 2

    # -- 만료된 펜딩 정리 --

    def expire_pending_shots(self, current_frame: int) -> list[GameEvent]:
        """
        타임아웃된 펜딩 슛을 미스로 확정.

        Args:
            current_frame: 현재 프레임 인덱스

        Returns:
            미스로 확정된 이벤트 목록
        """
        with self._lock:
            expired: list[GameEvent] = []
            max_wait = self._config.max_result_wait_frames
            for pending in list(self._pending_shots):
                if current_frame - pending.release_frame > max_wait:
                    event = self._finalize_shot(pending, ShotResult.MISSED, current_frame, 0.4)
                    expired.append(event)
            return expired

    # -- 조회 --

    def get_active_events(self) -> list[GameEvent]:
        """진행 중인 이벤트 (펜딩 슛 시도)."""
        with self._lock:
            return [
                GameEvent(
                    event_id=p.shot_id,
                    event_type=GameEventType.SHOT_ATTEMPT,
                    primary_player_id=p.player_tracking_id,
                    team_id=p.team_id,
                    frame_number=p.release_frame,
                    timestamp=p.release_timestamp_sec,
                    confidence=p.release_confidence,
                )
                for p in self._pending_shots
            ]

    def get_event_history(
        self,
        event_type: str | None = None,
        max_count: int = 100,
    ) -> list[GameEvent]:
        """이벤트 이력 조회."""
        with self._lock:
            events = list(self._event_history)
            if event_type:
                events = [e for e in events if e.event_type.value == event_type]
            return events[-max_count:]

    def get_shot_attempts(self, max_count: int = 100) -> list[ShotAttempt]:
        """ShotAttempt DTO 이력 조회."""
        with self._lock:
            return list(self._shot_attempts[-max_count:])

    def get_last_shot(self) -> ShotAttempt | None:
        """마지막 슛 시도."""
        with self._lock:
            return self._shot_attempts[-1] if self._shot_attempts else None

    # -- 리셋/팩토리 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._shot_attempts.clear()
            self._pending_shots.clear()
            self._motion_buffers.clear()
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]
        if len(self._shot_attempts) > _MAX_EVENT_HISTORY:
            self._shot_attempts = self._shot_attempts[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> ShotEventDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(ShotEventDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "ShotEventDetectorConfig",
    "ShotEventDetector",
    "ShotReleaseInput",
    "ShotResultInput",
]

__version__ = "1.0.0"
