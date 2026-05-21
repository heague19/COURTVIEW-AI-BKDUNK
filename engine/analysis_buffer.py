# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine
파일: analysis_buffer.py
설명: 분석 데이터 축적 및 상위 Cadence 파이프라인 입력 빌더

      FRAME 결과를 축적하여:
        - MotionSnapshot 슬라이딩 윈도우 (motion_analysis Tier1/2 입력)
        - PossessionData 빌드 (🟡 POSSESSION 파이프라인 입력)
        - PeriodData 빌드 (🟢 PERIOD 파이프라인 입력)
        - GameData 빌드 (🔵 POSTGAME 파이프라인 입력)

      데이터 흐름:
        FramePipelineResult
          → ingest_frame()
            → per-player MotionSnapshot 축적
          → build_possession_data() → 43종 분석기
          → build_period_data() → 16종 분석기
          → build_game_data() → 35종 모듈

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-28
버전: 1.0.0

의존성:
    - engine/pipeline/frame_pipeline.py: FramePipelineResult
    - engine/pipeline/event_pipeline.py: DetectedEvent
    - motion_analysis/models.py: MotionSnapshot
    - biomechanics/kinematics: FrameAngles, FrameVelocities

소비자:
    - engine/orchestrator/game_orchestrator.py: 모든 cadence 콜백
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.pipeline.frame_pipeline import FramePipelineResult
from shared.constants.pose_constants import JointType

# 선택적 의존성: motion_analysis 미설치 환경 대비
try:
    from motion_analysis.models import MotionSnapshot
    _MOTION_SNAPSHOT_AVAILABLE: Final[bool] = True
except ImportError:
    MotionSnapshot = None  # type: ignore[assignment,misc]
    _MOTION_SNAPSHOT_AVAILABLE = False

_logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
# 프레임 결과 보관 최대 크기 (30fps × 30초 = 900)
_MAX_FRAME_BUFFER: Final[int] = 900
# per-player 모션 윈도우 크기 (30프레임 ≈ 1초)
_MOTION_WINDOW_SIZE: Final[int] = 30
# 점유 이벤트 최대 보관
_MAX_POSSESSION_EVENTS: Final[int] = 200
# 2026-05-14 누수 방어:
# 게임 전체 이벤트 cap (1게임 평균 500개, 비정상 시 누적 방지)
_MAX_EVENT_BUFFER: Final[int] = 2000
# motion window 동시 추적 선수 cap (12명 + ReID 좀비 여유)
_MAX_MOTION_PLAYERS: Final[int] = 50


# =============================================================================
# AnalyzerInput — 모든 상위 분석기의 공통 입력 컨테이너
# =============================================================================
@dataclass(slots=True)
class AnalyzerInput:
    """
    상위 파이프라인 분석기 공통 입력.

    43종 POSSESSION, 16종 PERIOD, 35종 POSTGAME 분석기 모두
    이 구조체에서 필요한 필드를 추출하여 사용.
    """

    # 식별
    segment_id: int = 0                # 점유 ID / 쿼터 / 경기 ID
    quarter: int = 0
    team_id: str = ""
    duration_sec: float = 0.0

    # 프레임 통계
    frame_count: int = 0
    start_frame: int = 0
    end_frame: int = 0

    # 선수 추적 (player_id → 위치 이력 [(x, y), ...])
    player_tracks: dict[int, list[tuple[float, float]]] = field(
        default_factory=dict,
    )

    # 공 위치 이력 [(x, y, z), ...]
    ball_positions: list[tuple[float, float, float]] = field(
        default_factory=list,
    )

    # 이벤트 목록
    events: list[Any] = field(default_factory=list)

    # 선수별 동작 분류 결과 (player_id → action_name 리스트)
    player_actions: dict[int, list[str]] = field(default_factory=dict)

    # 선수별 biomechanics 평균 (player_id → 관절별 평균 각도)
    player_avg_angles: dict[int, dict[str, float]] = field(
        default_factory=dict,
    )

    # 선수별 평균 속도 (player_id → m/s)
    player_avg_speeds: dict[int, float] = field(default_factory=dict)


# =============================================================================
# _DynamicInputProvider — {name}_input 동적 속성 제공
# =============================================================================
class _DynamicInputProvider:
    """
    ``getattr(provider, "{name}_input")`` 호출 시 AnalyzerInput 반환.

    상위 파이프라인의 ``getattr(data, f"{name}_input", None)`` 패턴에 대응.
    모든 ``*_input`` 속성은 동일한 AnalyzerInput을 반환.
    """

    __slots__ = ("_data",)

    def __init__(self, data: AnalyzerInput) -> None:
        self._data = data

    def __getattr__(self, name: str) -> AnalyzerInput | None:
        if name.endswith("_input"):
            return self._data
        raise AttributeError(
            f"'{type(self).__name__}' 객체에 '{name}' 속성 없음",
        )


# =============================================================================
# GameAnalysisBuffer — 메인 축적/빌더 클래스
# =============================================================================
class GameAnalysisBuffer:
    """
    경기 중 프레임/이벤트 결과를 축적하고
    상위 Cadence 파이프라인(POSSESSION/PERIOD/POSTGAME)에 전달할 데이터를 빌드.

    스레드 안전: RLock 기반.
    """

    __slots__ = (
        "_frame_buffer",
        "_event_buffer",
        "_motion_windows",
        "_motion_player_order",     # 2026-05-14: motion_windows 키 LRU evict 용 deque
        "_possession_frames",
        "_possession_events",
        "_possession_start_frame",
        "_period_possessions",
        "_all_possession_summaries",
        "_frame_extractions",       # FRAME 레벨 추출 데이터 (학습용)
        "_extraction_interval",     # 추출 주기 (프레임 단위)
        "_total_events",
        "_total_frames",
        "_lock",
    )

    def __init__(self) -> None:
        # 프레임 결과 링 버퍼
        self._frame_buffer: deque[FramePipelineResult] = deque(
            maxlen=_MAX_FRAME_BUFFER,
        )
        # 전체 이벤트 축적
        # 2026-05-14 메모리 누수 안전장치: list → deque(maxlen=_MAX_EVENT_BUFFER).
        # 1게임 평균 ~500 events. 비정상 흐름 시 무한 누적 방지.
        # build_game_data() 에서 list() 로 복사하므로 deque 도 무방.
        self._event_buffer: deque[Any] = deque(maxlen=_MAX_EVENT_BUFFER)

        # per-player 모션 스냅샷 윈도우
        # 2026-05-14 메모리 누수 안전장치:
        # dict 자체는 key→deque 매핑 유지, 추가로 _motion_player_order deque(maxlen)
        # 가 player_id 의 insertion 순서 추적. maxlen 도달 시 가장 오래된 pid 가
        # dict 에서도 제거되어 ReID 실패로 인한 무한 키 증가 방지.
        self._motion_windows: dict[int, deque[Any]] = {}
        self._motion_player_order: deque[int] = deque(maxlen=_MAX_MOTION_PLAYERS)

        # 현재 점유 축적
        # 2026-05-13 메모리 누수 안전장치: 무제한 list → deque(maxlen=1800).
        # 30fps × 60초 = 1800. 점유 종료 cadence(_possession_cb) 가 어떤 이유로
        # 발화 못 하면 (예: score detection GATE 4-3 실패) 무한 누적되어 RAM 폭주.
        # 1점유 평균 길이는 ~10초 (300프레임) → 1분 cap 은 정상 흐름엔 영향 없음.
        # FramePipelineResult 개당 ~100KB 기준 deque 최대 ~180MB 로 상한.
        self._possession_frames: deque[FramePipelineResult] = deque(maxlen=1800)
        # 2026-05-14 메모리 누수 안전장치 (일관성):
        # list → deque(maxlen=_MAX_POSSESSION_EVENTS=200).
        # _possession_frames 와 같은 lifecycle 인데 cap 누락이었음.
        # 1점유 평균 event ~10개 → 200 cap 은 정상 흐름엔 영향 없음.
        # flush_possession() 발화 실패 시 무한 누적 방지.
        self._possession_events: deque[Any] = deque(maxlen=_MAX_POSSESSION_EVENTS)
        self._possession_start_frame: int = 0

        # 쿼터별 점유 요약 축적
        self._period_possessions: list[AnalyzerInput] = []
        # 전체 경기 점유 요약
        self._all_possession_summaries: list[AnalyzerInput] = []

        # FRAME 레벨 추출 데이터 축적
        self._frame_extractions: list[dict[str, Any]] = []
        self._extraction_interval: int = 30  # 30프레임(~1초)마다 추출

        self._total_events: int = 0
        self._total_frames: int = 0
        self._lock: RLock = RLock()

    # =========================================================================
    # 프레임 결과 수집
    # =========================================================================
    def ingest_frame(self, result: FramePipelineResult) -> None:
        """
        FRAME 결과 축적.

        매 프레임 호출. 프레임 버퍼 + 현재 점유 축적 + per-player 모션 윈도우 갱신.
        주기적으로 FRAME 레벨 학습 데이터 추출.
        """
        with self._lock:
            self._frame_buffer.append(result)
            self._possession_frames.append(result)
            self._total_frames += 1
            _total = self._total_frames
            _poss = len(self._possession_frames)
            _evt = len(self._event_buffer)

        # per-player 모션 스냅샷 구축
        self._update_motion_windows(result)

        # FRAME 레벨 학습 데이터 추출 (매 N프레임)
        if self._total_frames % self._extraction_interval == 0:
            self._extract_frame_level_data(result)

        # Plan E STEP 3 (2026-05-13): analysis_buffer 수신 흐름
        try:
            from infrastructure.diagnostics.flow_logger import log_flow
            log_flow(
                "BUFFER",
                "analysis_buffer.ingest_frame 수신 → frame_buffer/possession_frames 추가 "
                "(total=%d, possession_frames=%d, events=%d)",
                _total, _poss, _evt,
            )
        except Exception:
            pass

    # =========================================================================
    # 이벤트 결과 수집
    # =========================================================================
    def ingest_events(self, events: list[Any]) -> None:
        """EVENT 파이프라인 결과 축적."""
        if not events:
            return
        with self._lock:
            self._event_buffer.extend(events)
            self._possession_events.extend(events)
            self._total_events += len(events)

    # =========================================================================
    # 모션 스냅샷 윈도우 갱신
    # =========================================================================
    def _update_motion_windows(self, result: FramePipelineResult) -> None:
        """FramePipelineResult에서 per-player MotionSnapshot 추출 → 윈도우 추가."""
        if result.pose is None or not result.pose.poses_3d:
            return
        if not _MOTION_SNAPSHOT_AVAILABLE:
            return

        det = result.detection

        # 공/골대 위치 추출
        ball_pos: tuple[float, float, float] | None = None
        hoop_pos: tuple[float, float, float] | None = None
        if det is not None:
            if det.ball_result and det.ball_result.fused_objects:
                # v0.5.3: ball detector 객체는 position_3d 없을 수 있음 — getattr 가드
                bp = getattr(det.ball_result.fused_objects[0], "position_3d", None)
                if bp is not None:
                    ball_pos = (bp.x * 100.0, bp.y * 100.0, bp.z * 100.0)
            if det.hoop_result and det.hoop_result.fused_objects:
                hp = getattr(det.hoop_result.fused_objects[0], "position_3d", None)
                if hp is not None:
                    hoop_pos = (hp.x * 100.0, hp.y * 100.0, hp.z * 100.0)

        for pose_3d in result.pose.poses_3d:
            pid = pose_3d.person_id

            # 관절 각도 (biomechanics → MotionSnapshot)
            joint_angles: dict[JointType, float] = {}
            if pid in result.biomechanics_angles:
                fa = result.biomechanics_angles[pid]
                for jt, ja in fa.angles.items():
                    joint_angles[jt] = ja.angle_deg

            # 관절 속도 (biomechanics → MotionSnapshot)
            joint_speeds: dict[JointType, float] = {}
            joint_ang_vel: dict[JointType, float] = {}
            if pid in result.biomechanics_velocities:
                fv = result.biomechanics_velocities[pid]
                for jt, jv in fv.joint_velocities.items():
                    joint_speeds[jt] = jv.speed
                    joint_ang_vel[jt] = jv.angular_velocity

            # 관절 3D 위치 (m → cm)
            joint_positions: dict[JointType, tuple[float, float, float]] = {}
            kp = pose_3d.keypoints_3d
            for i, jt in enumerate(JointType):
                if i < kp.shape[0]:
                    joint_positions[jt] = (
                        float(kp[i, 0]) * 100.0,
                        float(kp[i, 1]) * 100.0,
                        float(kp[i, 2]) * 100.0,
                    )

            snapshot = MotionSnapshot(
                frame_index=result.frame_index,
                timestamp=result.timestamp,
                player_tracking_id=pid,
                joint_angles=joint_angles,
                joint_speeds=joint_speeds,
                joint_angular_velocities=joint_ang_vel,
                joint_positions=joint_positions,
                ball_position=ball_pos,
                hoop_position=hoop_pos,
            )

            with self._lock:
                if pid not in self._motion_windows:
                    # 2026-05-14: deque maxlen 메커니즘으로 dict 키 cap.
                    # _motion_player_order 가 가득 차서 새 pid append 시 가장 오래된
                    # pid 가 자동 popleft → dict 에서도 동기 제거.
                    if (
                        len(self._motion_player_order)
                        == self._motion_player_order.maxlen
                    ):
                        evicted_pid = self._motion_player_order[0]
                        self._motion_windows.pop(evicted_pid, None)
                    self._motion_player_order.append(pid)
                    self._motion_windows[pid] = deque(
                        maxlen=_MOTION_WINDOW_SIZE,
                    )
                self._motion_windows[pid].append(snapshot)

    # =========================================================================
    # 모션 윈도우 조회 (motion_analysis 입력)
    # =========================================================================
    def get_motion_window(self, player_id: int) -> list[Any]:
        """선수별 최근 MotionSnapshot 윈도우 반환."""
        with self._lock:
            window = self._motion_windows.get(player_id)
            if window is None:
                return []
            return list(window)

    def get_all_player_ids(self) -> list[int]:
        """모션 윈도우가 있는 선수 ID 목록."""
        with self._lock:
            return list(self._motion_windows.keys())

    # =========================================================================
    # 2026-05-21: 엔진 이벤트 직렬화 (finalize → events.json)
    # =========================================================================
    def get_engine_events(self) -> list[dict[str, Any]]:
        """`_event_buffer` 의 엔진 탐지 이벤트들을 JSON-safe dict 로 반환.

        finalize_service._write_events 가 events.json 에 dump 하는 입력.
        score/shot/foul/turnover 등 모든 detector 의 GameEvent (또는 dataclass)
        를 일관된 형식으로 변환.
        """
        with self._lock:
            events_snapshot = list(self._event_buffer)

        out: list[dict[str, Any]] = []
        for e in events_snapshot:
            try:
                # Pydantic BaseModel (GameEvent 등)
                if hasattr(e, "model_dump"):
                    d = e.model_dump(mode="json")
                # dataclass
                elif hasattr(e, "__dataclass_fields__"):
                    from dataclasses import asdict as _asdict
                    d = _asdict(e)
                # 일반 dict
                elif isinstance(e, dict):
                    d = dict(e)
                else:
                    # 최후 fallback — 핵심 필드만 추출
                    d = {
                        "event_type": str(getattr(e, "event_type", "?")),
                        "frame_number": getattr(e, "frame_number", None),
                        "timestamp": getattr(e, "timestamp", None),
                        "quarter": getattr(e, "quarter", None),
                        "player_id": getattr(e, "primary_player_id",
                                             getattr(e, "player_id", None)),
                        "confidence": getattr(e, "confidence", 0.0),
                    }
                # Enum / UUID → str 정리 (json.dumps 호환)
                for k, v in list(d.items()):
                    if hasattr(v, "value") and hasattr(v, "name"):  # Enum
                        d[k] = v.value
                    elif hasattr(v, "hex") and not isinstance(v, (bytes, bytearray)):  # UUID
                        d[k] = str(v)
                out.append(d)
            except Exception:
                out.append({"raw": str(e), "serialize_error": True})
        return out

    # =========================================================================
    # POSSESSION 데이터 빌드
    # =========================================================================
    def build_possession_data(self, possession_id: int) -> _DynamicInputProvider:
        """현재 점유 축적 데이터 → POSSESSION 파이프라인 입력 빌드."""
        with self._lock:
            frames = list(self._possession_frames)
            events = list(self._possession_events)

        inp = self._build_analyzer_input(
            frames, events, segment_id=possession_id,
        )

        # 점유 요약 보관 (PERIOD/POSTGAME에서 재사용)
        with self._lock:
            self._period_possessions.append(inp)
            self._all_possession_summaries.append(inp)

        return _DynamicInputProvider(inp)

    def flush_possession(self) -> None:
        """점유 종료 시 현재 점유 버퍼 초기화."""
        with self._lock:
            self._possession_frames.clear()
            self._possession_events.clear()

    # =========================================================================
    # PERIOD 데이터 빌드
    # =========================================================================
    def build_period_data(self, quarter: int) -> _DynamicInputProvider:
        """현재 쿼터 축적 데이터 → PERIOD 파이프라인 입력 빌드."""
        with self._lock:
            possessions = list(self._period_possessions)

        # 쿼터 전체 프레임/이벤트 합산
        all_events: list[Any] = []
        total_frames = 0
        total_dur = 0.0
        player_tracks: dict[int, list[tuple[float, float]]] = {}
        for p in possessions:
            all_events.extend(p.events)
            total_frames += p.frame_count
            total_dur += p.duration_sec
            for pid, track in p.player_tracks.items():
                player_tracks.setdefault(pid, []).extend(track)

        inp = AnalyzerInput(
            segment_id=quarter,
            quarter=quarter,
            duration_sec=total_dur,
            frame_count=total_frames,
            events=all_events,
            player_tracks=player_tracks,
        )
        return _DynamicInputProvider(inp)

    def flush_period(self) -> None:
        """쿼터 종료 시 쿼터 축적 초기화."""
        with self._lock:
            self._period_possessions.clear()

    # =========================================================================
    # POSTGAME 데이터 빌드
    # =========================================================================
    def build_game_data(self) -> _DynamicInputProvider:
        """전체 경기 축적 데이터 → POSTGAME 파이프라인 입력 빌드."""
        with self._lock:
            summaries = list(self._all_possession_summaries)
            events = list(self._event_buffer)

        total_dur = sum(s.duration_sec for s in summaries)
        total_frames = sum(s.frame_count for s in summaries)
        player_tracks: dict[int, list[tuple[float, float]]] = {}
        for s in summaries:
            for pid, track in s.player_tracks.items():
                player_tracks.setdefault(pid, []).extend(track)

        inp = AnalyzerInput(
            segment_id=0,
            duration_sec=total_dur,
            frame_count=total_frames,
            events=events,
            player_tracks=player_tracks,
        )
        return _DynamicInputProvider(inp)

    # =========================================================================
    # 공통: AnalyzerInput 빌드
    # =========================================================================
    def _build_analyzer_input(
        self,
        frames: list[FramePipelineResult],
        events: list[Any],
        segment_id: int = 0,
    ) -> AnalyzerInput:
        """프레임 리스트 → AnalyzerInput 변환."""
        if not frames:
            return AnalyzerInput(segment_id=segment_id, events=events)

        start_fi = frames[0].frame_index
        end_fi = frames[-1].frame_index
        start_ts = frames[0].timestamp
        end_ts = frames[-1].timestamp
        duration = max(end_ts - start_ts, 0.001)

        # 선수 위치 이력 추출
        player_tracks: dict[int, list[tuple[float, float]]] = {}
        ball_positions: list[tuple[float, float, float]] = []
        player_avg_speeds: dict[int, list[float]] = {}

        for fr in frames:
            # 트래킹 → 선수 위치
            if fr.tracking is not None:
                for track in fr.tracking.active_tracks:
                    if track.last_bbox:
                        cx = (track.last_bbox[0] + track.last_bbox[2]) / 2.0
                        cy = (track.last_bbox[1] + track.last_bbox[3]) / 2.0
                        player_tracks.setdefault(
                            track.global_id, [],
                        ).append((cx, cy))

            # 공 위치
            if (
                fr.detection is not None
                and fr.detection.ball_result
                and fr.detection.ball_result.fused_objects
            ):
                bp3 = fr.detection.ball_result.fused_objects[0].position_3d
                if bp3 is not None:
                    ball_positions.append((bp3.x, bp3.y, bp3.z))

            # biomechanics 속도
            for pid, fv in fr.biomechanics_velocities.items():
                player_avg_speeds.setdefault(pid, []).append(
                    fv.body_speed_m_s,
                )

        # 평균 속도 계산
        avg_speeds = {
            pid: sum(speeds) / len(speeds)
            for pid, speeds in player_avg_speeds.items()
            if speeds
        }

        return AnalyzerInput(
            segment_id=segment_id,
            duration_sec=duration,
            frame_count=len(frames),
            start_frame=start_fi,
            end_frame=end_fi,
            events=events,
            player_tracks=player_tracks,
            ball_positions=ball_positions,
            player_avg_speeds=avg_speeds,
        )

    # =========================================================================
    # FRAME 레벨 학습 데이터 추출 (detection/pose/biomechanics)
    # =========================================================================
    def _extract_frame_level_data(self, result: FramePipelineResult) -> None:
        """
        FRAME 결과에서 학습용 데이터 추출.

        detection bbox 좌표, pose 키포인트, biomechanics 특성값을
        경량 dict로 변환하여 축적. POSTGAME에서 일괄 전송.
        """
        record: dict[str, Any] = {
            "frame_index": result.frame_index,
            "timestamp": result.timestamp,
        }

        # detection: 감지 객체 bbox + 신뢰도
        if result.detection is not None:
            det_samples: list[dict] = []
            for det_type in ("ball_result", "player_result", "hoop_result"):
                mv = getattr(result.detection, det_type, None)
                if mv is not None:
                    for obj in mv.fused_objects:
                        # v0.4.5: fused_objects 의 객체가 bbox 없는 타입일 수 있음 — 안전 처리
                        bbox = getattr(obj, "bbox", None)
                        if bbox is not None:
                            det_samples.append({
                                "type": det_type.replace("_result", ""),
                                "bbox": [bbox.x, bbox.y,
                                         bbox.width, bbox.height],
                                "confidence": getattr(obj, "confidence", 0.0),
                            })
            if det_samples:
                record["detections"] = det_samples

        # pose: 3D 키포인트
        if result.pose is not None and result.pose.poses_3d:
            pose_samples: list[dict] = []
            for pose_3d in result.pose.poses_3d:
                pose_samples.append({
                    "person_id": pose_3d.person_id,
                    "keypoints_3d": pose_3d.keypoints_3d.tolist(),
                    "confidences": pose_3d.keypoint_confidences.tolist(),
                })
            if pose_samples:
                record["poses"] = pose_samples

        # biomechanics: 관절 각도/속도
        bio: dict[str, Any] = {}
        for pid, angles in result.biomechanics_angles.items():
            bio.setdefault(pid, {})["angles"] = {
                jt.value: ja.angle_deg
                for jt, ja in angles.angles.items()
            }
        for pid, vels in result.biomechanics_velocities.items():
            bio.setdefault(pid, {})["speeds"] = {
                jt.value: jv.speed
                for jt, jv in vels.joint_velocities.items()
            }
        if bio:
            record["biomechanics"] = bio

        with self._lock:
            self._frame_extractions.append(record)

    def get_frame_extractions(self) -> list[dict[str, Any]]:
        """축적된 FRAME 레벨 추출 데이터 반환 (POSTGAME에서 호출)."""
        with self._lock:
            data = list(self._frame_extractions)
            self._frame_extractions.clear()
            return data

    # =========================================================================
    # 리셋
    # =========================================================================
    def reset(self) -> None:
        """전체 초기화."""
        with self._lock:
            self._frame_buffer.clear()
            self._event_buffer.clear()
            self._motion_windows.clear()
            self._motion_player_order.clear()  # 2026-05-14: order 추적도 reset
            self._possession_frames.clear()
            self._possession_events.clear()
            self._possession_start_frame = 0
            self._period_possessions.clear()
            self._all_possession_summaries.clear()
            self._frame_extractions.clear()
            self._total_events = 0
            self._total_frames = 0

    def __repr__(self) -> str:
        return (
            f"GameAnalysisBuffer(frames={self._total_frames}, "
            f"events={self._total_events}, "
            f"players={len(self._motion_windows)})"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "AnalyzerInput",
    "GameAnalysisBuffer",
]

__version__ = "1.0.0"
