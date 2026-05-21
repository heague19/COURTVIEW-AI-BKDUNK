# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/event_detection
파일: score_detector.py
설명: 득점 감지기 — 매 프레임 공-골대 통과 확인 + 득점 확정
      🔴 FRAME cadence (<2ms) — 60fps 매 프레임 실행
      네트 변형, 공 궤적 하강, 림 통과 증거 통합 판정

      학술 근거:
        Silverberg, L.M. et al. (2018). "Optimal Backspin and
        Shooting Angle in Basketball Free Throws." J. of Applied
        Biomechanics, 34(4).

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/event_detection.yaml (score_detection 섹션)
의존성: shared.constants.game_rule_constants, shared.dto.game_dto
소비자: game_analysis/statistics/, game_analysis/game_management/
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Final
from uuid import uuid4

from shared.constants.game_rule_constants import (
    GameEventType,
    ShotResult,
)
from shared.dto.game_dto import GameEvent
from shared.interfaces.game_interface import (
    GameModuleState,
    GameModuleMetrics,
    GameEventResult,
)

logger: Final = logging.getLogger(__name__)

_MAX_EVENT_HISTORY: Final[int] = 500
_DEDUP_COOLDOWN_FRAMES: Final[int] = 150  # 중복 제거 쿨다운 (150f = 5초@30fps)

# 2026-05-11 STEP2 토글 (검증용) — GATE 4-3 above→below 시간 순서 가드
#   True  : 진짜 슛 (above 먼저 → below 나중) 만 인정 — 기본/안전.
#   False : 순서 무시 → 카메라 각도가 거꾸로 잡는 영상도 통과시킴.
#           단, 리바운드/팁/드리블/패스 등 false positive 폭증 가능.
#           플립으로 되돌리려면 다시 True 로.
_GATE_4_3_STRICT: Final[bool] = False


# =============================================================================
# 프레임 단위 득점 입력
# =============================================================================
@dataclass(slots=True)
class ScoreFrameInput:
    """매 프레임 득점 감지 입력 데이터. 최소 필드만 사용 (2ms 예산)."""

    frame_index: int
    timestamp_sec: float

    # 공-골대 관계 (detection 레이어에서 사전 계산)
    ball_rim_distance_m: float = 999.0       # 공-림 거리
    ball_through_hoop: bool = False          # 공이 림을 통과했는가
    ball_above_rim: bool = False             # 공이 림 위에 있는가
    ball_below_rim: bool = False             # 공이 림 아래로 내려갔는가
    ball_vertical_velocity_ms: float = 0.0   # 공 수직 속도 (m/s, 음수=하강)

    # 네트 상태
    net_deflection: float = 0.0              # 네트 변형 정도 (0~1)

    # 림 접촉
    rim_contact: bool = False                # 림 접촉 여부

    # 연관 슛 시도 (shot_event_detector에서 연결)
    associated_shot_id: str | None = None    # 연관된 슛 시도 ID
    shooter_tracking_id: int | None = None   # 슈터 트래킹 ID
    shooter_team_id: str | None = None       # 슈터 팀 ID

    # 게임 상태
    quarter: int = 1
    game_clock: str = ""
    home_score: int = 0
    away_score: int = 0

    # 신뢰도 (detection 레이어 기준)
    confidence: float = 0.0


# =============================================================================
# ScoreDetectorConfig
# =============================================================================
@dataclass(slots=True)
class ScoreDetectorConfig:
    """
    득점 감지기 설정.

    YAML 설정: configs/game_analysis/event_detection.yaml → score_detection.confirmation
    """

    # 득점 확인 조건
    min_confidence: float = 0.40                # 최소 신뢰도 (완화)
    require_ball_through_hoop: bool = False      # 공 통과 확인 완화 (픽셀 정밀도 부족)
    net_deflection_required: bool = False        # 네트 변형 미감지 환경
    max_latency_frames: int = 5                  # 최대 판정 지연 프레임

    # 점수 배점
    free_throw_points: int = 1
    two_pointer_points: int = 2
    three_pointer_points: int = 3

    # 득점 확정 보조 증거
    net_deflection_min: float = 0.3              # 네트 변형 최소값
    ball_descent_velocity_min_ms: float = -0.5   # 공 하강 속도 최소 (m/s, 음수)

    # 공통
    fps: float = 30.0

    @classmethod
    def from_yaml(cls, cfg: dict) -> ScoreDetectorConfig:
        """YAML 설정 로드.

        Fallback 기본값은 dataclass 기본값과 동일 (완화된 값).
        YAML에서 보수적 값을 원하면 명시적으로 오버라이드 필요.
        """
        score = cfg.get("score_detection", cfg)
        confirm = score.get("confirmation", {})
        pts = score.get("points", {})
        common = cfg.get("common", {})

        return cls(
            min_confidence=float(confirm.get("min_confidence", 0.40)),
            require_ball_through_hoop=bool(confirm.get("require_ball_through_hoop", False)),
            net_deflection_required=bool(confirm.get("net_deflection_required", False)),
            max_latency_frames=int(confirm.get("max_latency_frames", 5)),
            free_throw_points=int(pts.get("free_throw", 1)),
            two_pointer_points=int(pts.get("two_pointer", 2)),
            three_pointer_points=int(pts.get("three_pointer", 3)),
            fps=float(common.get("default_fps", 30)),
        )


# =============================================================================
# 내부 증거 누적기
# =============================================================================
@dataclass(slots=True)
class _ScoringEvidence:
    """
    득점 증거 누적 — 여러 프레임에 걸친 증거를 통합.

    FRAME cadence에서 최소 연산으로 증거를 축적하고,
    충분한 증거 누적 시 득점을 확정합니다.
    """

    start_frame: int
    ball_through_count: int = 0         # 공 통과 감지 프레임 수
    net_deflection_max: float = 0.0     # 최대 네트 변형
    rim_contact_count: int = 0          # 림 접촉 프레임 수
    descent_detected: bool = False       # 공 하강 감지
    peak_confidence: float = 0.0         # 최대 신뢰도
    above_seen: bool = False             # ball_above_rim=True 한 번이라도 봤음
    below_seen: bool = False             # ball_below_rim=True 한 번이라도 봤음
    above_first_frame: int = -1          # above 가 처음 잡힌 frame (시간 순서 검증용)
    below_first_frame: int = -1          # below 가 처음 잡힌 frame
    last_frame: int = 0
    shooter_tracking_id: int | None = None
    shooter_team_id: str | None = None
    associated_shot_id: str | None = None
    confirmed: bool = False


# =============================================================================
# ScoreDetector
# =============================================================================
class ScoreDetector:
    """
    득점 감지기.

    Cadence: 🔴 FRAME (<2ms)

    매 프레임 공-골대 관계를 확인하고, 다중 프레임 증거를
    누적하여 득점을 확정합니다.

    설계 원칙:
      - 2ms 예산 준수 → 무조건 O(1) 연산
      - 단일 활성 증거만 유지 (동시에 2개 득점 불가)
      - 증거 누적 → 확정 → 쿨다운 → 리셋 패턴
    """

    def __init__(self, config: ScoreDetectorConfig | None = None) -> None:
        self._config: Final = config or ScoreDetectorConfig()
        self._lock: Final = RLock()
        self._state = GameModuleState.READY
        self._metrics = GameModuleMetrics()

        # 이벤트 이력
        self._event_history: list[GameEvent] = []

        # 현재 증거 (단일 슬롯)
        self._evidence: _ScoringEvidence | None = None

        # 중복 제거 쿨다운
        self._last_score_frame: int = -_DEDUP_COOLDOWN_FRAMES

        # 누적 점수
        self._total_home_scores: int = 0
        self._total_away_scores: int = 0

        logger.info("ScoreDetector 초기화 완료 (fps=%.1f)", self._config.fps)

    # -- 속성 --

    @property
    def name(self) -> str:
        return "ScoreDetector"

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
            GameEventType.SHOT_MADE.value,
        ]

    @property
    def total_scores_detected(self) -> int:
        """총 감지된 득점 수."""
        with self._lock:
            return len(self._event_history)

    # -- 프레임 처리 (핵심 메서드, <2ms) --

    def process_frame(self, data: ScoreFrameInput) -> GameEvent | None:
        """
        프레임 단위 득점 감지.

        🔴 FRAME cadence: 반드시 2ms 이내 완료.

        Args:
            data: 매 프레임 입력 데이터

        Returns:
            SHOT_MADE 이벤트 (득점 확정 시) 또는 None
        """
        t0 = time.perf_counter()
        # SCORE-FLOW 추적 — 가까운 림(<5m) 또는 증거 active 일 때만 verbose
        # (원거리 일반 프레임 스팸 방지)
        verbose = (data.ball_rim_distance_m < 5.0) or (self._evidence is not None)
        if verbose:
            logger.info(
                "[SCORE-FLOW F#%d] 2️⃣ 데이터 수신 완료 → process_frame 진입 "
                "(rim=%.2fm through=%s above=%s below=%s vy=%.2f conf=%.2f evidence=%s)",
                data.frame_index, data.ball_rim_distance_m, data.ball_through_hoop,
                data.ball_above_rim, data.ball_below_rim,
                data.ball_vertical_velocity_ms, data.confidence,
                "active" if self._evidence is not None else "none",
            )

        with self._lock:
            try:
                event = self._detect_score(data, verbose=verbose)
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
                logger.error("득점 감지 오류: %s", e)
                return None

    def _detect_score(
        self, data: ScoreFrameInput, verbose: bool = False,
    ) -> GameEvent | None:
        """
        득점 감지 내부 로직 (O(1) 연산).

        증거 누적 → 확정 판단 패턴.
        """
        cfg = self._config
        fi = data.frame_index

        # 쿨다운 체크 (중복 제거)
        cooldown_gap = fi - self._last_score_frame
        if cooldown_gap < _DEDUP_COOLDOWN_FRAMES:
            if verbose:
                logger.info(
                    "[SCORE-FLOW F#%d] 3️⃣-A 쿨다운 GATE: ❌ %d/%df 미경과 "
                    "(last_score=%d) → 증거 폐기 + None 반환",
                    fi, cooldown_gap, _DEDUP_COOLDOWN_FRAMES, self._last_score_frame,
                )
            self._evidence = None
            return None
        if verbose and self._last_score_frame >= 0:
            logger.info(
                "[SCORE-FLOW F#%d] 3️⃣-A 쿨다운 GATE: ✓ %df 경과 (last_score=%d)",
                fi, cooldown_gap, self._last_score_frame,
            )

        # 새 증거 시작 조건: 공이 림 근처에 도달
        if self._evidence is None:
            if data.ball_rim_distance_m < 3.0:  # 림 근처 (픽셀 변환 오차 허용)
                self._evidence = _ScoringEvidence(
                    start_frame=fi,
                    shooter_tracking_id=data.shooter_tracking_id,
                    shooter_team_id=data.shooter_team_id,
                    associated_shot_id=data.associated_shot_id,
                )
                if verbose:
                    logger.info(
                        "[SCORE-FLOW F#%d] 3️⃣-B 증거 수집 시작 ✨ "
                        "(rim=%.2fm < 3.0m, shooter=%s, team=%s)",
                        fi, data.ball_rim_distance_m,
                        data.shooter_tracking_id, data.shooter_team_id,
                    )
            else:
                if verbose:
                    logger.info(
                        "[SCORE-FLOW F#%d] 3️⃣-B 증거 미시작 (rim=%.2fm >= 3.0m) "
                        "→ 4️⃣ 결과: None (림 너무 멀음)",
                        fi, data.ball_rim_distance_m,
                    )
                return None

        ev = self._evidence
        elapsed = fi - ev.start_frame

        # 증거 누적 (O(1))
        ev.last_frame = fi

        if data.ball_through_hoop:
            ev.ball_through_count += 1

        if data.net_deflection > ev.net_deflection_max:
            ev.net_deflection_max = data.net_deflection

        if data.rim_contact:
            ev.rim_contact_count += 1

        if data.ball_vertical_velocity_ms < cfg.ball_descent_velocity_min_ms:
            ev.descent_detected = True

        if data.confidence > ev.peak_confidence:
            ev.peak_confidence = data.confidence

        # v0.4.5: 포물선 (위에서 아래로) 전이 추적 — noise FP 차단.
        # 시간 순서 (above_first < below_first) 검증으로 noise 한층 더 차단.
        if data.ball_above_rim:
            ev.above_seen = True
            if ev.above_first_frame < 0:
                ev.above_first_frame = fi
        if data.ball_below_rim:
            ev.below_seen = True
            if ev.below_first_frame < 0:
                ev.below_first_frame = fi

        # 슈터 정보 업데이트 (첫 유효 값)
        if ev.shooter_tracking_id is None and data.shooter_tracking_id is not None:
            ev.shooter_tracking_id = data.shooter_tracking_id
        if ev.shooter_team_id is None and data.shooter_team_id is not None:
            ev.shooter_team_id = data.shooter_team_id
        if ev.associated_shot_id is None and data.associated_shot_id is not None:
            ev.associated_shot_id = data.associated_shot_id

        if verbose:
            logger.info(
                "[SCORE-FLOW F#%d] 3️⃣-C 증거 누적 (start=%d, %df 경과) → "
                "through_cnt=%d net_max=%.2f rim_cnt=%d descent=%s "
                "above=%s(@%d) below=%s(@%d) peak_conf=%.2f",
                fi, ev.start_frame, elapsed,
                ev.ball_through_count, ev.net_deflection_max, ev.rim_contact_count,
                ev.descent_detected,
                ev.above_seen, ev.above_first_frame,
                ev.below_seen, ev.below_first_frame,
                ev.peak_confidence,
            )

        # 타임아웃 (최대 지연 프레임 초과 → 증거 폐기)
        if elapsed > cfg.max_latency_frames:
            if verbose:
                logger.warning(
                    "[SCORE-FLOW F#%d] 3️⃣-D 타임아웃 GATE: ❌ %df > max_latency=%df "
                    "→ 증거 폐기 + 4️⃣ 결과: None (조건 미달성)",
                    fi, elapsed, cfg.max_latency_frames,
                )
            if not ev.confirmed:
                self._evidence = None
            return None

        # 득점 확정 판단
        if not ev.confirmed:
            confirmed = self._evaluate_evidence(
                ev, cfg, verbose=verbose, frame_index=fi,
            )
            if confirmed:
                ev.confirmed = True
                event = self._create_score_event(ev, data)
                self._last_score_frame = fi
                self._evidence = None
                if verbose:
                    logger.info(
                        "[SCORE-FLOW F#%d] 4️⃣ 결과: ✅ 성공 → SHOT_MADE 이벤트 발화 "
                        "(conf=%.2f, points=%d)",
                        fi,
                        getattr(event, "confidence", 0.0),
                        getattr(event, "points", 2),
                    )
                return event
            else:
                if verbose:
                    logger.info(
                        "[SCORE-FLOW F#%d] 4️⃣ 결과: ✗ 조건 미달 (증거 계속 누적, "
                        "%d/%df 남음)",
                        fi, cfg.max_latency_frames - elapsed,
                        cfg.max_latency_frames,
                    )

        return None

    def _evaluate_evidence(
        self,
        ev: _ScoringEvidence,
        cfg: ScoreDetectorConfig,
        verbose: bool = False,
        frame_index: int = 0,
    ) -> bool:
        """
        증거 평가 — 득점 여부 판단.

        조건:
          1. 공 통과 감지 (필수 또는 선택)
          2. 네트 변형 (필수 또는 선택)
          3. 신뢰도 충족
        """
        if verbose:
            logger.info(
                "[SCORE-FLOW F#%d] 3️⃣-E 조건부 확인 진행 → _evaluate_evidence 진입",
                frame_index,
            )

        # GATE 1: 신뢰도 확인
        if ev.peak_confidence < cfg.min_confidence:
            if verbose:
                logger.info(
                    "[SCORE-FLOW F#%d]    ├─ GATE 1 confidence: ❌ peak=%.2f < min=%.2f",
                    frame_index, ev.peak_confidence, cfg.min_confidence,
                )
            return False
        if verbose:
            logger.info(
                "[SCORE-FLOW F#%d]    ├─ GATE 1 confidence: ✓ peak=%.2f >= min=%.2f",
                frame_index, ev.peak_confidence, cfg.min_confidence,
            )

        # GATE 2: 공 통과 확인
        if cfg.require_ball_through_hoop and ev.ball_through_count == 0:
            if verbose:
                logger.info(
                    "[SCORE-FLOW F#%d]    ├─ GATE 2 through: ❌ require_through=True && count=0",
                    frame_index,
                )
            return False
        if verbose:
            logger.info(
                "[SCORE-FLOW F#%d]    ├─ GATE 2 through: ✓ require=%s, count=%d",
                frame_index, cfg.require_ball_through_hoop, ev.ball_through_count,
            )

        # GATE 3: 네트 변형 확인
        if cfg.net_deflection_required and ev.net_deflection_max < cfg.net_deflection_min:
            if verbose:
                logger.info(
                    "[SCORE-FLOW F#%d]    ├─ GATE 3 net_deflection: ❌ %.2f < min=%.2f",
                    frame_index, ev.net_deflection_max, cfg.net_deflection_min,
                )
            return False
        if verbose:
            logger.info(
                "[SCORE-FLOW F#%d]    ├─ GATE 3 net_deflection: ✓ required=%s (max=%.2f)",
                frame_index, cfg.net_deflection_required, ev.net_deflection_max,
            )

        # GATE 4-1: above + below 둘 다 봤나 (v0.4.5 가드)
        if not (ev.above_seen and ev.below_seen):
            if verbose:
                logger.info(
                    "[SCORE-FLOW F#%d]    ├─ GATE 4-1 above/below seen: ❌ "
                    "above=%s, below=%s",
                    frame_index, ev.above_seen, ev.below_seen,
                )
            return False
        if verbose:
            logger.info(
                "[SCORE-FLOW F#%d]    ├─ GATE 4-1 above/below seen: ✓ 둘 다 OK",
                frame_index,
            )

        # GATE 4-2: above/below frame 인덱스 유효 (음수 ↔ 미관측)
        if ev.above_first_frame < 0 or ev.below_first_frame < 0:
            if verbose:
                logger.info(
                    "[SCORE-FLOW F#%d]    ├─ GATE 4-2 frame indices: ❌ "
                    "above_first=%d, below_first=%d (음수)",
                    frame_index, ev.above_first_frame, ev.below_first_frame,
                )
            return False

        # GATE 4-3: above 가 below 보다 시간상 먼저 (위→아래 궤적)
        # 토글 비활성 시엔 시간 순서 무시 (리바운드/패스 false positive 위험 감수)
        if _GATE_4_3_STRICT:
            if ev.above_first_frame >= ev.below_first_frame:
                if verbose:
                    logger.info(
                        "[SCORE-FLOW F#%d]    ├─ GATE 4-3 above→below 순서: ❌ "
                        "above_first=%d >= below_first=%d (역순서, slut 아님 - rebound 등)",
                        frame_index, ev.above_first_frame, ev.below_first_frame,
                    )
                return False
            if verbose:
                logger.info(
                    "[SCORE-FLOW F#%d]    ├─ GATE 4-3 above→below 순서: ✓ "
                    "above_first=%d < below_first=%d",
                    frame_index, ev.above_first_frame, ev.below_first_frame,
                )
        else:
            if verbose:
                order_str = (
                    "정상순서 (위→아래)"
                    if ev.above_first_frame < ev.below_first_frame
                    else "역순서 (아래→위)"
                )
                logger.info(
                    "[SCORE-FLOW F#%d]    ├─ GATE 4-3 above→below 순서: "
                    "⚠ BYPASS (toggle OFF) → above_first=%d below_first=%d %s",
                    frame_index, ev.above_first_frame, ev.below_first_frame,
                    order_str,
                )

        # GATE 5: 하강 속도 (vy < descent_velocity_min_ms 한 번이라도)
        if not ev.descent_detected:
            if verbose:
                logger.info(
                    "[SCORE-FLOW F#%d]    ├─ GATE 5 descent: ❌ vy < %.2f 한 번도 없음",
                    frame_index, cfg.ball_descent_velocity_min_ms,
                )
            return False
        if verbose:
            logger.info(
                "[SCORE-FLOW F#%d]    ├─ GATE 5 descent: ✓",
                frame_index,
            )

        # GATE 6: through_count >= 2 (단일 frame FP 차단)
        if ev.ball_through_count < 2:
            if verbose:
                logger.info(
                    "[SCORE-FLOW F#%d]    ├─ GATE 6 through_count>=2: ❌ count=%d",
                    frame_index, ev.ball_through_count,
                )
            return False
        if verbose:
            logger.info(
                "[SCORE-FLOW F#%d]    ├─ GATE 6 through_count>=2: ✓ count=%d",
                frame_index, ev.ball_through_count,
            )

        if verbose:
            logger.info(
                "[SCORE-FLOW F#%d]    └─ ✅ 모든 GATE 통과 → 득점 확정",
                frame_index,
            )
        return True

    def _create_score_event(
        self, ev: _ScoringEvidence, data: ScoreFrameInput,
    ) -> GameEvent:
        """득점 확정 이벤트 생성."""
        event = GameEvent(
            event_id=uuid4(),
            event_type=GameEventType.SHOT_MADE,
            primary_player_id=ev.shooter_tracking_id or 0,
            team_id=ev.shooter_team_id or "",
            frame_number=ev.start_frame,
            timestamp=data.timestamp_sec,
            quarter=data.quarter,
            game_clock=data.game_clock,
            home_score=data.home_score,
            away_score=data.away_score,
            confidence=ev.peak_confidence,
            description=(
                f"득점 확인 (프레임 {ev.start_frame}-{ev.last_frame}, "
                f"네트변형={ev.net_deflection_max:.2f}, "
                f"통과={ev.ball_through_count}f)"
            ),
        )
        self._event_history.append(event)
        self._trim_history()

        logger.info(
            "득점 감지: player=%s, team=%s, conf=%.2f",
            ev.shooter_tracking_id, ev.shooter_team_id, ev.peak_confidence,
        )
        return event

    # -- 조회 --

    def get_active_events(self) -> list[GameEvent]:
        """현재 진행 중인 증거 (있으면)."""
        with self._lock:
            if self._evidence and not self._evidence.confirmed:
                return [GameEvent(
                    event_id=uuid4(),
                    event_type=GameEventType.SHOT_MADE,
                    primary_player_id=self._evidence.shooter_tracking_id or 0,
                    frame_number=self._evidence.start_frame,
                    timestamp=0.0,
                    confidence=self._evidence.peak_confidence,
                    description="득점 판정 진행 중",
                )]
            return []

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

    # -- 리셋 --

    def reset(self) -> None:
        """상태 초기화."""
        with self._lock:
            self._event_history.clear()
            self._evidence = None
            self._last_score_frame = -_DEDUP_COOLDOWN_FRAMES
            self._total_home_scores = 0
            self._total_away_scores = 0
            self._metrics = GameModuleMetrics()
            self._state = GameModuleState.READY

    def _trim_history(self) -> None:
        """이력 크기 제한."""
        if len(self._event_history) > _MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-_MAX_EVENT_HISTORY:]

    @classmethod
    def from_yaml(cls, cfg: dict) -> ScoreDetector:
        """YAML 설정으로 인스턴스 생성."""
        return cls(ScoreDetectorConfig.from_yaml(cfg))


# =============================================================================
# 모듈 익스포트
# =============================================================================
__all__ = [
    "ScoreDetectorConfig",
    "ScoreDetector",
    "ScoreFrameInput",
]

__version__ = "1.0.0"
