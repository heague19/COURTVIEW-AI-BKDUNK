# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: game_service.py
설명: 경기 수명주기 서비스
      - GameOrchestrator 래핑
      - 경기 시작/중지/일시정지/재개
      - 경기 상태 조회

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0
"""

from __future__ import annotations

import logging
import time
import uuid
from threading import RLock
from typing import TYPE_CHECKING, Callable

from engine.config import EngineConfig, EngineMode
from shared.constants.player_constants import AgeGroup, Gender
from shared.constants.referee_rule_constants import RuleSet

from api_server.schemas.request_schemas import StartGameRequest, StopGameRequest
from api_server.schemas.response_schemas import GameStartResponse, GameStatusResponse

if TYPE_CHECKING:
    from engine.orchestrator.game_orchestrator import GameOrchestrator

_logger = logging.getLogger(__name__)

# 연령대 문자열 → AgeGroup 매핑
_AGE_GROUP_MAP: dict[str, AgeGroup] = {
    "youth": AgeGroup.YOUTH,
    "teen": AgeGroup.TEEN,
    "adult": AgeGroup.ADULT,
    "senior": AgeGroup.SENIOR,
}

# 성별 문자열 → Gender 매핑
_GENDER_MAP: dict[str, Gender] = {
    "male": Gender.MALE,
    "female": Gender.FEMALE,
}

# 모드 문자열 → EngineMode 매핑
_MODE_MAP: dict[str, EngineMode] = {
    "live": EngineMode.LIVE,
    "batch": EngineMode.BATCH,
    "replay": EngineMode.REPLAY,
}

# 리그 문자열 → RuleSet 매핑
_RULE_SET_MAP: dict[str, RuleSet] = {
    "fiba": RuleSet.FIBA,
    "nba": RuleSet.NBA,
    "kbl": RuleSet.KBL,
    "nbl": RuleSet.NBL,
}


class GameService:
    """
    경기 수명주기 서비스.

    api_server의 라우트에서 호출합니다.
    내부적으로 GameOrchestrator를 관리합니다.
    """

    __slots__ = (
        "_orchestrator",
        "_game_id",
        "_home_team",
        "_away_team",
        "_lock",
        "_on_game_start_callbacks",
        "_on_game_end_callbacks",
        "_demo_broadcaster",
        "_camera_service",
        "_extraction_finalizer",  # v0.4.0
        "_preloaded_orchestrator",  # 2026-05-13: G — 사전 빌드 결과
        "_preload_thread",          # 2026-05-13: G — preload worker 스레드
    )

    def __init__(self) -> None:
        self._orchestrator: GameOrchestrator | None = None
        self._game_id: str = ""
        self._home_team: str = ""
        self._away_team: str = ""
        self._lock: RLock = RLock()
        self._on_game_start_callbacks: list[Callable] = []
        self._on_game_end_callbacks: list[Callable] = []  # Phase 17 S4
        self._demo_broadcaster = None  # DemoBroadcaster (데모 모드)
        self._camera_service = None    # CameraService 참조 (연결된 RTSP URL 조회용)
        # v0.4.0: 추출기 finalize hook — orchestrator/추출기가 register() 로 등록
        self._extraction_finalizer = None
        # 2026-05-13: G — Orchestrator 사전 빌드 (51초 → ~0초)
        #   launcher 시작 직후 백그라운드에서 LIVE/FIBA 기본으로 미리 빌드.
        #   start_game(request) 호출 시 mode/rule_set 매칭되면 재사용.
        self._preloaded_orchestrator = None
        self._preload_thread = None

    def set_extraction_finalizer(self, finalizer) -> None:
        """v0.4.0: ExtractionFinalizerService 주입.

        orchestrator 또는 추출기 인스턴스화 시점에 `finalizer.register(name, ext)` 로
        등록 → 경기 종료 시 자동 finalize + S3 업로드.
        """
        self._extraction_finalizer = finalizer

    @property
    def extraction_finalizer(self):
        """v0.4.0: 등록된 finalizer 반환 (orchestrator / 추출기 wiring 용)."""
        return self._extraction_finalizer

    def set_camera_service(self, camera_service) -> None:
        """CameraService 주입.

        start_game() 시 request.source_urls가 비어 있으면
        camera_service.get_status_all()에서 연결된 카메라의 RTSP URL을
        자동으로 사용한다. UI가 기자재 페이지에서 카메라를 연결해두면
        경기 시작 API에 URL을 명시하지 않아도 동작한다.
        """
        self._camera_service = camera_service

    # =========================================================================
    # 2026-05-13: G — 사전 빌드 (Orchestrator preload)
    # =========================================================================
    def preload_orchestrator_async(self) -> None:
        """백그라운드 스레드에서 Orchestrator 사전 빌드.

        launcher 시작 직후 (engine 부팅 후) 1회 호출하면 LIVE/FIBA 기본 설정으로
        Orchestrator 를 미리 빌드한다. 사용자가 카메라 연결/캘리브/AI 테스트 하는
        동안 모델/TRT 엔진 로드가 백그라운드에서 완료 → game/start 클릭 시
        ~51초 → ~0초로 단축.

        실제 start_game(request) 호출 시 mode/rule_set 매칭되면 이 인스턴스 재사용.
        매칭 안 되면 (REPLAY/BATCH 또는 다른 rule_set) 일반 빌드 경로로 폴백.
        """
        import threading
        with self._lock:
            if self._preload_thread is not None and self._preload_thread.is_alive():
                _logger.info("[GAME-SVC] 사전 빌드 스레드 이미 동작 중 — skip")
                return
            if self._preloaded_orchestrator is not None:
                _logger.info("[GAME-SVC] 사전 빌드 결과 이미 있음 — skip")
                return

            self._preload_thread = threading.Thread(
                target=self._preload_worker,
                name="orch-preload",
                daemon=True,
            )
            self._preload_thread.start()
            _logger.info("[GAME-SVC] 🔥 Orchestrator 사전 빌드 백그라운드 시작 (LIVE/FIBA)")

    def _preload_worker(self) -> None:
        """preload_orchestrator_async 의 worker 스레드."""
        from engine.orchestrator.game_orchestrator import GameOrchestrator
        t0 = time.perf_counter()
        try:
            config = EngineConfig(mode=EngineMode.LIVE)
            # 기본값: rule_set=FIBA, recording_enabled=True (start_game 시 override 가능)
            built = GameOrchestrator.build_from_config(config)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            with self._lock:
                # 그동안 실제 start_game 이 다른 mode 로 진행되어 이미 _orchestrator 가
                # 있으면 사전 빌드 결과는 버림 (메모리 충돌 방지).
                if self._orchestrator is not None:
                    _logger.warning(
                        "[GAME-SVC] 사전 빌드 완료했으나 다른 game 이 이미 시작됨 — 폐기 (%.0f ms)",
                        elapsed_ms,
                    )
                    return
                self._preloaded_orchestrator = built
                _logger.info(
                    "[GAME-SVC] ✅ Orchestrator 사전 빌드 완료 (%.0f ms) — 다음 LIVE/FIBA "
                    "start_game 즉시 사용 가능",
                    elapsed_ms,
                )
        except Exception:
            _logger.exception("[GAME-SVC] ❌ 사전 빌드 실패 (정상 빌드 경로로 폴백)")

    def _get_connected_urls(self) -> dict[str, str]:
        """camera_service에서 현재 연결된 카메라의 {camera_id: url} 맵 반환.

        2026-05-13 Fix A 재적용: effective_url (go2rtc relay) 우선 사용.
          이전엔 c.url (native) 만 반환 → FrameIngestion 이 카메라당 추가 RTSP 세션 →
          저가 IPCam 의 2-session 한계 초과 → buffer 영원히 empty (frame 미수신).
          get_recording_url() 은 go2rtc 활성 시 relay URL 반환 → 모든 decoder 가 단일
          RTSP 세션 공유. go2rtc 비활성/실패 시 native URL fallback.
        """
        if self._camera_service is None:
            return {}
        try:
            status = self._camera_service.get_status_all()
            result: dict[str, str] = {}
            for c in status.cameras:
                if not (c.connected and c.url):
                    continue
                rec_url = self._camera_service.get_recording_url(c.camera_id)
                result[c.camera_id] = rec_url or c.url
            return result
        except Exception:
            _logger.exception("연결 카메라 URL 조회 실패")
            return {}

    def on_game_start(self, callback: Callable) -> None:
        """경기 시작 시 호출할 콜백 등록 (orchestrator 바인딩용)."""
        self._on_game_start_callbacks.append(callback)

    def on_game_end(self, callback: Callable) -> None:
        """경기 종료 시 호출할 콜백 등록 (Phase 17 S4 — CloudSync 트리거용)."""
        self._on_game_end_callbacks.append(callback)

    @property
    def orchestrator(self) -> GameOrchestrator | None:
        return self._orchestrator

    @property
    def is_game_active(self) -> bool:
        return self._orchestrator is not None and self._orchestrator.is_running

    @property
    def current_game_id(self) -> str:
        """v0.4.0: 진행 중인 game_id (없으면 빈 문자열). 하이라이트 업로드 라우팅용."""
        return self._game_id or ""

    # =========================================================================
    # 경기 시작
    # =========================================================================
    def start_game(self, request: StartGameRequest) -> GameStartResponse:
        """
        경기 시작.

        Args:
            request: 경기 시작 요청

        Returns:
            GameStartResponse
        """
        # ===== GAME-SVC 1️⃣ 요청 수신 =====
        _logger.info(
            "[GAME-SVC] 1️⃣ 요청 수신 → mode=%s rule=%s recording=%s home='%s' away='%s' "
            "source_urls=%d개 keys=%s",
            request.mode, request.rule_set, request.recording_enabled,
            request.home_team_name, request.away_team_name,
            len(request.source_urls or {}),
            list((request.source_urls or {}).keys()),
        )

        with self._lock:
            if self._orchestrator is not None and self._orchestrator.is_running:
                _logger.warning("[GAME-SVC] ❌ 이미 진행 중인 경기 — 거부")
                return GameStartResponse(
                    success=False,
                    message="이미 진행 중인 경기가 있습니다.",
                )
            if self._demo_broadcaster is not None and self._demo_broadcaster.is_running:
                _logger.warning("[GAME-SVC] ❌ 데모 진행 중 — 거부")
                return GameStartResponse(
                    success=False,
                    message="데모가 진행 중입니다.",
                )

            # ===== 데모 모드 =====
            if request.mode == "demo":
                _logger.info("[GAME-SVC] → 데모 모드 분기")
                return self._start_demo(request)

            # ===== 일반 모드 =====
            mode = _MODE_MAP.get(request.mode, EngineMode.LIVE)
            rule_set = _RULE_SET_MAP.get(request.rule_set, RuleSet.FIBA)
            _logger.info(
                "[GAME-SVC] 2️⃣ 모드/룰셋 매핑 → EngineMode.%s, RuleSet.%s",
                mode.name, rule_set.name,
            )

            config = EngineConfig(mode=mode)
            config.referee.rule_set = rule_set
            config.camera.recording_enabled = request.recording_enabled
            config.age_group = _AGE_GROUP_MAP.get(request.age_group, AgeGroup.ADULT)
            config.gender = _GENDER_MAP.get(request.gender, Gender.MALE)

            # source_urls 비어 있으면 camera_service에서 연결된 카메라 자동 사용
            # (UI가 기자재 페이지에서 미리 연결해 둔 카메라 URL을 재사용)
            # v0.5.8.4: mode 조건 제거 + 진단 로그. 이전엔 mode 매핑 실패 시 자동 채움 skip
            # → orchestrator 가 source 0개로 init → frame_pipeline 미실행 → 매 프레임 0건.
            # 또한 _get_connected_urls 결과가 비었을 때 명확한 warning 로그.
            source_urls = request.source_urls
            if not source_urls:
                source_urls = self._get_connected_urls() or None
                if source_urls:
                    _logger.warning(
                        "source_urls 자동 채움 (camera_service): %d대 → %s",
                        len(source_urls), list(source_urls.keys()),
                    )
                else:
                    _logger.warning(
                        "source_urls 자동 채움 실패 — camera_service=%s, 연결된 카메라 없음. "
                        "orchestrator 는 frame source 0개로 init 됩니다 (분석 0건).",
                        "ok" if self._camera_service else "None",
                    )

            # 카메라 수를 소스에 맞게 조정
            if source_urls:
                config.camera.num_cameras = len(source_urls)

            # REPLAY/BATCH: 파일 재생 시 동기화 허용 오차 확대 (카메라 FPS 차이 허용)
            if mode in (EngineMode.REPLAY, EngineMode.BATCH):
                config.camera.sync_tolerance_ms = 5000.0  # 파일 재생: FPS 차이로 drift 누적 → 사실상 비활성

            # 소스 해상도 자동 감지 → 불필요한 업스케일 방지
            if source_urls and mode in (EngineMode.REPLAY, EngineMode.BATCH):
                first_url = next(iter(source_urls.values()), "")
                if first_url:
                    try:
                        import cv2 as _cv2
                        _cap = _cv2.VideoCapture(first_url)
                        if _cap.isOpened():
                            src_w = int(_cap.get(_cv2.CAP_PROP_FRAME_WIDTH))
                            src_h = int(_cap.get(_cv2.CAP_PROP_FRAME_HEIGHT))
                            _cap.release()
                            # 소스 해상도가 분석 해상도보다 작으면 업스케일 방지
                            if src_w < config.camera.analysis_width:
                                config.camera.analysis_width = src_w
                                config.camera.analysis_height = src_h
                                config.camera.recording_enabled = False
                                _logger.warning(
                                    "분석 해상도 자동 조정: %dx%d → %dx%d (업스케일 방지)",
                                    1920, 1080, src_w, src_h,
                                )
                        else:
                            _logger.warning("소스 해상도 감지 실패: VideoCapture 열기 실패 — %s", first_url)
                    except Exception as exc:
                        _logger.warning("소스 해상도 감지 오류: %s", exc)

            # GameOrchestrator 빌드 (lazy import — torch 로딩 지연)
            _logger.info(
                "[GAME-SVC] 3️⃣ EngineConfig 완성 → mode=%s sync_tol=%.0fms recording=%s "
                "num_cameras=%d analysis=%dx%d age=%s gender=%s",
                config.mode.name, config.camera.sync_tolerance_ms,
                config.camera.recording_enabled, config.camera.num_cameras,
                config.camera.analysis_width, config.camera.analysis_height,
                config.age_group.name, config.gender.name,
            )

            # 2026-05-13: G — 사전 빌드 재사용 분기
            # 조건: mode=LIVE + rule_set=FIBA (사전 빌드 기본값과 매칭)
            # 매칭 안 되면 정상 빌드. 매칭되면 51초 → ~0초.
            preloaded = self._preloaded_orchestrator
            can_reuse = (
                preloaded is not None
                and mode == EngineMode.LIVE
                and rule_set == RuleSet.FIBA
            )
            from engine.orchestrator.game_orchestrator import GameOrchestrator

            if can_reuse:
                _logger.info(
                    "[GAME-SVC] 4️⃣ 🚀 사전 빌드된 Orchestrator 재사용 (LIVE/FIBA) — "
                    "build 단계 skip",
                )
                self._orchestrator = preloaded
                self._preloaded_orchestrator = None  # 일회용 — 다음 게임은 다시 preload 필요
                # config 의 동적 부분 (request 별) 업데이트
                try:
                    self._orchestrator._config.camera.recording_enabled = request.recording_enabled
                    self._orchestrator._config.camera.num_cameras = config.camera.num_cameras
                    self._orchestrator._config.age_group = config.age_group
                    self._orchestrator._config.gender = config.gender
                    _logger.info(
                        "[GAME-SVC] 4️⃣ config 동적 업데이트: recording=%s num_cameras=%d age=%s gender=%s",
                        request.recording_enabled, config.camera.num_cameras,
                        config.age_group.name, config.gender.name,
                    )
                except Exception:
                    _logger.exception("[GAME-SVC] config 동적 업데이트 실패 (무시)")
            else:
                if preloaded is not None:
                    _logger.info(
                        "[GAME-SVC] 4️⃣ 사전 빌드 있으나 mode=%s rule=%s 불일치 → 정상 빌드",
                        mode.name, rule_set.name,
                    )
                _logger.info(
                    "[GAME-SVC] 4️⃣ GameOrchestrator.build_from_config 호출 (모델 로드 — 분 단위)",
                )
                t_build = time.perf_counter()
                self._orchestrator = GameOrchestrator.build_from_config(config)
                build_ms = (time.perf_counter() - t_build) * 1000.0
                _logger.info(
                    "[GAME-SVC] 4️⃣ Orchestrator 빌드 완료 (%.0f ms)",
                    build_ms,
                )
            self._game_id = str(uuid.uuid4())
            self._home_team = request.home_team_name
            self._away_team = request.away_team_name

            # v0.4.0: orchestrator 에 ExtractionFinalizer + game_id 주입 (start_game 전)
            try:
                self._orchestrator._game_id = self._game_id
                if self._extraction_finalizer is not None:
                    self._orchestrator._extraction_finalizer = self._extraction_finalizer
            except Exception:
                _logger.exception("orchestrator finalizer 주입 실패 (무시)")

            # 시작
            _logger.info(
                "[GAME-SVC] 5️⃣ Orchestrator.start_game 호출 → source_urls=%s",
                list((source_urls or {}).keys()) if source_urls else "(빈)",
            )
            t_start = time.perf_counter()
            success = self._orchestrator.start_game(
                source_urls=source_urls or None,
            )
            start_ms = (time.perf_counter() - t_start) * 1000.0
            _logger.info(
                "[GAME-SVC] 5️⃣ start_game 반환 → success=%s (%.0f ms)",
                success, start_ms,
            )

            if success:
                # 팀 유니폼 색상 설정 (UI에서 입력)
                if request.home_team_color and request.away_team_color:
                    try:
                        self._orchestrator.set_team_colors(
                            request.home_team_color,
                            request.away_team_color,
                        )
                        _logger.info(
                            "팀 색상 설정: home=%s, away=%s",
                            request.home_team_color, request.away_team_color,
                        )
                    except Exception:
                        _logger.warning("팀 색상 설정 실패")

                # 서비스들에 orchestrator 바인딩
                for cb in self._on_game_start_callbacks:
                    try:
                        cb(self._orchestrator)
                    except Exception:
                        _logger.exception("게임 시작 콜백 오류")

                _logger.info(
                    "경기 시작: game_id=%s, mode=%s, rule_set=%s",
                    self._game_id, mode.value, rule_set.value,
                )
                return GameStartResponse(
                    success=True,
                    game_id=self._game_id,
                    message=f"경기 시작 완료 ({mode.value}, {rule_set.value})",
                )
            else:
                self._orchestrator = None
                return GameStartResponse(
                    success=False,
                    message="경기 시작 실패",
                )

    # =========================================================================
    # 데모 모드 시작
    # =========================================================================
    def _start_demo(self, request: StartGameRequest) -> GameStartResponse:
        """데모 모드 — 엔진 없이 시나리오 기반 WebSocket 브로드캐스트."""
        from demo.demo_broadcaster import DemoBroadcaster

        scenario_path = request.source_urls.get(
            "scenario", "demo/scenario.json",
        ) if request.source_urls else "demo/scenario.json"

        try:
            self._demo_broadcaster = DemoBroadcaster(
                scenario_path=scenario_path, speed=1.0,
            )
            # 데모 브로드캐스터의 ws_queue를 progress_handler에 공유
            self._demo_broadcaster.start()

            teams = self._demo_broadcaster.get_teams()
            self._game_id = str(uuid.uuid4())
            self._home_team = teams.get("home", {}).get("name", "HOME")
            self._away_team = teams.get("away", {}).get("name", "AWAY")

            _logger.info(
                "데모 시작: %s vs %s (game_id=%s)",
                self._home_team, self._away_team, self._game_id,
            )
            return GameStartResponse(
                success=True,
                game_id=self._game_id,
                message=f"데모 모드 시작 ({self._home_team} vs {self._away_team})",
            )
        except Exception as e:
            _logger.exception("데모 시작 실패")
            self._demo_broadcaster = None
            return GameStartResponse(
                success=False,
                message=f"데모 시작 실패: {e}",
            )

    @property
    def demo_broadcaster(self):
        """데모 브로드캐스터 참조 (WebSocket 핸들러에서 사용)."""
        return self._demo_broadcaster

    # =========================================================================
    # 경기 중지
    # =========================================================================
    def stop_game(self, request: StopGameRequest | None = None) -> GameStatusResponse:
        """경기 중지."""
        with self._lock:
            # 데모 모드 중지
            if self._demo_broadcaster is not None:
                self._demo_broadcaster.stop()
                self._demo_broadcaster = None
                self._game_id = ""
                _logger.info("데모 중지 완료")
                return self.get_status()

            if self._orchestrator is None:
                return self.get_status()

            orch = self._orchestrator
            self._orchestrator.stop_game()
            status = self.get_status()
            self._orchestrator = None
            self._game_id = ""
            _logger.info("경기 중지 완료")

        # Phase 17 S4: 경기 종료 콜백 (CloudSync 트리거) — lock 바깥에서 실행
        for cb in self._on_game_end_callbacks:
            try:
                cb(orch)
            except Exception:
                _logger.exception("경기 종료 콜백 오류")

        return status

    # =========================================================================
    # 일시정지 / 재개
    # =========================================================================
    def pause_game(self) -> GameStatusResponse:
        """경기 일시정지."""
        if self._orchestrator is not None:
            self._orchestrator.pause_game()
        return self.get_status()

    def resume_game(self) -> GameStatusResponse:
        """경기 재개."""
        if self._orchestrator is not None:
            self._orchestrator.resume_game()
        return self.get_status()

    # =========================================================================
    # 상태 조회
    # =========================================================================
    def get_status(self) -> GameStatusResponse:
        """현재 경기 상태 조회."""
        if self._orchestrator is None:
            return GameStatusResponse()

        sm = self._orchestrator.state_manager
        ctx = sm.game_context

        return GameStatusResponse(
            engine_state=sm.engine_state.value,
            game_state=ctx.game_state.value,
            mode=self._orchestrator._config.mode.value,
            quarter=ctx.quarter,
            game_clock_sec=ctx.game_clock_sec,
            shot_clock_sec=ctx.shot_clock_sec,
            home_score=ctx.home_score,
            away_score=ctx.away_score,
            home_team_name=self._home_team,
            away_team_name=self._away_team,
            frame_number=ctx.frame_number,
            uptime_sec=sm.uptime_sec,
        )


__all__ = ["GameService"]
