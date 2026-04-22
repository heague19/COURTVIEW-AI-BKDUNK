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

    def set_camera_service(self, camera_service) -> None:
        """CameraService 주입.

        start_game() 시 request.source_urls가 비어 있으면
        camera_service.get_status_all()에서 연결된 카메라의 RTSP URL을
        자동으로 사용한다. UI가 기자재 페이지에서 카메라를 연결해두면
        경기 시작 API에 URL을 명시하지 않아도 동작한다.
        """
        self._camera_service = camera_service

    def _get_connected_urls(self) -> dict[str, str]:
        """camera_service에서 현재 연결된 카메라의 {camera_id: url} 맵 반환."""
        if self._camera_service is None:
            return {}
        try:
            status = self._camera_service.get_status_all()
            return {
                c.camera_id: c.url
                for c in status.cameras
                if c.connected and c.url
            }
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
        with self._lock:
            if self._orchestrator is not None and self._orchestrator.is_running:
                return GameStartResponse(
                    success=False,
                    message="이미 진행 중인 경기가 있습니다.",
                )
            if self._demo_broadcaster is not None and self._demo_broadcaster.is_running:
                return GameStartResponse(
                    success=False,
                    message="데모가 진행 중입니다.",
                )

            # ===== 데모 모드 =====
            if request.mode == "demo":
                return self._start_demo(request)

            # ===== 일반 모드 =====
            mode = _MODE_MAP.get(request.mode, EngineMode.LIVE)
            rule_set = _RULE_SET_MAP.get(request.rule_set, RuleSet.FIBA)

            config = EngineConfig(mode=mode)
            config.referee.rule_set = rule_set
            config.camera.recording_enabled = request.recording_enabled
            config.age_group = _AGE_GROUP_MAP.get(request.age_group, AgeGroup.ADULT)
            config.gender = _GENDER_MAP.get(request.gender, Gender.MALE)

            # source_urls 비어 있으면 camera_service에서 연결된 카메라 자동 사용
            # (UI가 기자재 페이지에서 미리 연결해 둔 카메라 URL을 재사용)
            source_urls = request.source_urls
            if not source_urls and mode == EngineMode.LIVE:
                source_urls = self._get_connected_urls() or None

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
            from engine.orchestrator.game_orchestrator import GameOrchestrator
            self._orchestrator = GameOrchestrator.build_from_config(config)
            self._game_id = str(uuid.uuid4())
            self._home_team = request.home_team_name
            self._away_team = request.away_team_name

            # 시작
            success = self._orchestrator.start_game(
                source_urls=source_urls or None,
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
