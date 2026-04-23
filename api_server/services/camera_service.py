# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: camera_service.py
설명: 카메라 연결/캘리브레이션/AI 테스트/설정 관리 서비스
      - 개별/전체 카메라 RTSP 연결 + 상태 관리
      - 캘리브레이션 실행 (코트 인식 + 호모그래피)
      - AI 감지 테스트 (코트/선수/공/골대 1프레임 감지)
      - 스냅샷 반환 (세팅 화면 미리보기)
      - 카메라 설정 저장/불러오기

      호출하는 기존 모듈 (신규 구현 0건):
        - infrastructure/preprocessing/video_decoder.py: VideoDecoder
        - infrastructure/multi_camera/camera_calibrator.py: MultiCameraCalibrator
        - detection/court_detection/court_detector.py: CourtDetector
        - detection/player_detection/player_detector.py: PlayerDetector
        - detection/ball_detection/ball_detector.py: BallDetector
        - detection/hoop_detection/hoop_detector.py: HoopDetector

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-28
버전: 1.0.0

소비자:
    - api_server/routes/v1/camera_routes.py: REST 엔드포인트
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import json
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, Generator

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from infrastructure.preprocessing.video_decoder import VideoDecoder, DecoderState
from infrastructure.multi_camera.camera_calibrator import (
    MultiCameraCalibrator,
    CalibrationSnapshot,
)

if TYPE_CHECKING:
    from detection.player_detection.player_detector import PlayerDetector
    from detection.ball_detection.ball_detector import BallDetector
    from detection.hoop_detection.hoop_detector import HoopDetector

from api_server.schemas.request_schemas import (
    CameraAITestRequest,
    CameraCalibrationRequest,
    CameraConnectAllRequest,
    CameraConnectRequest,
    CameraSaveConfigRequest,
    ManualCalibrationRequest,
)
from api_server.schemas.response_schemas import (
    CameraAITestResponse,
    CameraCalibrationResponse,
    CameraStatusAllResponse,
    CameraStatusResponse,
    ManualCalibrationResponse,
)

_logger = logging.getLogger(__name__)

# 설정 파일 기본 경로
_DEFAULT_CONFIG_DIR = Path("configs/base")
_DEFAULT_CONFIG_FILE = "camera_sources.json"
_CALIBRATION_DIR = Path("configs/calibration")


# =============================================================================
# 개별 카메라 핸들
# =============================================================================
class _CameraHandle:
    """개별 카메라 연결 핸들."""

    __slots__ = (
        "camera_id", "label", "url",
        "decoder", "connected",
        "width", "height", "fps",
        "calibrated", "calibration_quality",
        # Phase 17 S2: 헬스 모니터링
        "last_reconnect_time",
        "reconnect_attempts",
        "health_status",
    )

    def __init__(self, camera_id: str, url: str = "", label: str = "") -> None:
        self.camera_id = camera_id
        self.label = label
        self.url = url
        self.decoder = VideoDecoder(camera_id=camera_id)
        self.connected = False
        self.width = 0
        self.height = 0
        self.fps = 0.0
        self.calibrated = False
        self.calibration_quality = 0.0
        # Phase 17 S2: 헬스 상태 초기값
        self.last_reconnect_time: float = 0.0
        self.reconnect_attempts: int = 0
        self.health_status: str = "unknown"  # unknown / healthy / stalled / reconnecting / failed


# =============================================================================
# CameraService
# =============================================================================
class CameraService:
    """
    카메라 관리 서비스.

    세팅 화면에서 필요한 모든 카메라 기능을 제공합니다:
    연결 → 미리보기 → 캘리브레이션 → AI 테스트 → 설정 저장.
    """

    __slots__ = (
        "_cameras",
        "_calibrator",
        "_court_detector",
        "_player_detector",
        "_ball_detector",
        "_hoop_detector",
        "_config_dir",
        "_lock",
        "_stream_caps",
        "_stream_urls",
        "_stream_lock",
        # Phase 17 S2: 헬스 모니터링
        "_watchdog_thread",
        "_watchdog_stop_event",
        "_watchdog_interval_sec",
        "_stall_threshold_sec",
        "_max_reconnect_attempts",
    )

    def __init__(
        self,
        player_detector: PlayerDetector | None = None,
        ball_detector: BallDetector | None = None,
        hoop_detector: HoopDetector | None = None,
        config_dir: Path | None = None,
    ) -> None:
        self._cameras: dict[str, _CameraHandle] = {}
        self._calibrator: MultiCameraCalibrator | None = None
        self._player_detector = player_detector
        self._ball_detector = ball_detector
        self._hoop_detector = hoop_detector
        self._config_dir = config_dir or _DEFAULT_CONFIG_DIR
        self._lock = RLock()
        # MJPEG 스트리밍용 — URL당 1개 리더 스레드가 최신 JPEG 프레임을 유지
        self._stream_caps: dict[str, bytes | None] = {}
        self._stream_urls: dict[str, bool] = {}
        self._stream_lock = threading.Lock()
        # Phase 17 S2: 헬스 모니터링
        self._watchdog_thread: threading.Thread | None = None
        self._watchdog_stop_event = threading.Event()
        self._watchdog_interval_sec: float = 2.0      # 2초마다 헬스 체크
        self._stall_threshold_sec: float = 3.0        # 3초 이상 프레임 없으면 stalled
        self._max_reconnect_attempts: int = 5         # 연속 재연결 실패 5회 → failed

    # =========================================================================
    # 연결
    # =========================================================================
    def connect_camera(self, request: CameraConnectRequest) -> CameraStatusResponse:
        """
        개별 카메라 RTSP 연결.

        Args:
            request: 카메라 연결 요청 (id, url, label)

        Returns:
            CameraStatusResponse
        """
        cam_id = request.camera_id
        url = request.url
        label = request.label or cam_id

        handle = _CameraHandle(camera_id=cam_id, url=url, label=label)

        # RTSP 연결 시도
        opened = handle.decoder.open(url)
        if opened:
            handle.connected = True
            # 메타데이터 추출
            cap = getattr(handle.decoder, "_cap", None)
            if cap is not None and hasattr(cap, "get"):
                handle.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                handle.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                handle.fps = cap.get(cv2.CAP_PROP_FPS)
            _logger.info("카메라 연결 성공: %s → %s", cam_id, url)
        else:
            handle.connected = False
            _logger.warning("카메라 연결 실패: %s → %s", cam_id, url)

        with self._lock:
            # 기존 연결 있으면 닫기
            old = self._cameras.get(cam_id)
            if old is not None:
                old.decoder.close()
            self._cameras[cam_id] = handle

        return self._handle_to_status(handle)

    def connect_all(self, request: CameraConnectAllRequest) -> CameraStatusAllResponse:
        """
        전체 카메라 일괄 연결 (Phase 17 S1: 병렬 처리).

        8대 순차 연결 시 최대 60초(카메라당 재시도 포함) 걸리던 것을
        ThreadPoolExecutor로 병렬화하여 단일 카메라 연결 시간 수준으로 단축.
        카메라 1대 실패는 다른 카메라에 영향 없음 (독립 실행).
        """
        camera_reqs = list(request.cameras)
        if not camera_reqs:
            return CameraStatusAllResponse(
                cameras=[], total_cameras=0, connected_count=0,
                calibrated_count=0, all_ready=False,
            )

        # 병렬 연결 (카메라 수만큼 워커, 최대 16)
        max_workers = min(len(camera_reqs), 16)
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cam-connect") as pool:
            # submit 순서 = 결과 순서 보장 위해 map 대신 future 리스트 사용
            futures = [pool.submit(self.connect_camera, req) for req in camera_reqs]
            statuses: list[CameraStatusResponse] = [f.result() for f in futures]

        connected = sum(1 for s in statuses if s.connected)
        calibrated = sum(1 for s in statuses if s.calibrated)

        _logger.info(
            "병렬 카메라 연결 완료: %d/%d 성공",
            connected, len(statuses),
        )

        return CameraStatusAllResponse(
            cameras=statuses,
            total_cameras=len(statuses),
            connected_count=connected,
            calibrated_count=calibrated,
            all_ready=connected == len(statuses) and connected > 0,
        )

    def reconnect_all(self) -> CameraStatusAllResponse:
        """저장된 URL로 전체 재연결 (Phase 17 S1: 병렬 처리)."""
        with self._lock:
            handles = list(self._cameras.values())

        if not handles:
            return CameraStatusAllResponse(
                cameras=[], total_cameras=0, connected_count=0,
                calibrated_count=0, all_ready=False,
            )

        reqs = [
            CameraConnectRequest(camera_id=h.camera_id, url=h.url, label=h.label)
            for h in handles
        ]
        max_workers = min(len(reqs), 16)
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cam-reconnect") as pool:
            futures = [pool.submit(self.connect_camera, req) for req in reqs]
            statuses: list[CameraStatusResponse] = [f.result() for f in futures]

        connected = sum(1 for s in statuses if s.connected)
        calibrated = sum(1 for s in statuses if s.calibrated)

        return CameraStatusAllResponse(
            cameras=statuses,
            total_cameras=len(statuses),
            connected_count=connected,
            calibrated_count=calibrated,
            all_ready=connected == len(statuses) and connected > 0,
        )

    def disconnect_all(self) -> None:
        """전체 카메라 연결 해제."""
        with self._lock:
            for handle in self._cameras.values():
                handle.decoder.close()
                handle.connected = False
            _logger.info("전체 카메라 연결 해제: %d대", len(self._cameras))

    def reconnect_camera(self, camera_id: str) -> CameraStatusResponse | None:
        """
        단일 카메라 재연결 (Phase 17 S2).

        기존 디코더 닫고 재시도 후 health_status 갱신.
        """
        with self._lock:
            handle = self._cameras.get(camera_id)
            if handle is None:
                return None

        # 기존 디코더 정리
        try:
            handle.decoder.close()
        except Exception:
            _logger.exception("카메라 %s 디코더 close 중 오류", camera_id)

        # 새 디코더로 교체
        handle.decoder = VideoDecoder(camera_id=camera_id)
        handle.health_status = "reconnecting"
        handle.last_reconnect_time = time.time()
        handle.reconnect_attempts += 1

        opened = handle.decoder.open(handle.url)
        if opened:
            handle.connected = True
            handle.health_status = "healthy"
            _logger.info(
                "카메라 %s 재연결 성공 (attempts=%d)",
                camera_id, handle.reconnect_attempts,
            )
        else:
            handle.connected = False
            if handle.reconnect_attempts >= self._max_reconnect_attempts:
                handle.health_status = "failed"
                _logger.error(
                    "카메라 %s 재연결 %d회 실패 — failed 상태",
                    camera_id, handle.reconnect_attempts,
                )
            else:
                handle.health_status = "stalled"
                _logger.warning("카메라 %s 재연결 실패", camera_id)

        return self._handle_to_status(handle)

    # =========================================================================
    # 헬스 모니터링 워치도그 (Phase 17 S2)
    # =========================================================================
    def start_watchdog(self) -> None:
        """백그라운드 헬스 모니터 스레드 시작."""
        if self._watchdog_thread is not None and self._watchdog_thread.is_alive():
            return

        self._watchdog_stop_event.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="camera-watchdog",
            daemon=True,
        )
        self._watchdog_thread.start()
        _logger.info(
            "카메라 워치도그 시작 (interval=%.1fs, stall_threshold=%.1fs)",
            self._watchdog_interval_sec, self._stall_threshold_sec,
        )

    def stop_watchdog(self) -> None:
        """워치도그 스레드 종료."""
        self._watchdog_stop_event.set()
        if self._watchdog_thread is not None:
            self._watchdog_thread.join(timeout=3.0)
            self._watchdog_thread = None
        _logger.info("카메라 워치도그 종료")

    def _watchdog_loop(self) -> None:
        """
        헬스 체크 루프 — 카메라별로 stalled 감지 시 자동 재연결.

        체크 로직:
          1. connected=True 상태만 감시
          2. decoder.is_stalled(threshold) 감지
          3. stalled → reconnect_camera() 호출
          4. reconnect_attempts >= max 이면 failed 로 고정, 재시도 중단
        """
        while not self._watchdog_stop_event.is_set():
            try:
                # 스냅샷
                with self._lock:
                    handles = list(self._cameras.values())

                for handle in handles:
                    if not handle.connected:
                        continue
                    if handle.health_status == "failed":
                        continue  # 포기 상태는 건너뜀

                    if handle.decoder.is_stalled(self._stall_threshold_sec):
                        seconds_silent = handle.decoder.seconds_since_last_frame()
                        _logger.warning(
                            "카메라 %s stalled 감지 (%.1fs 무프레임) — 재연결 시도",
                            handle.camera_id, seconds_silent,
                        )
                        handle.health_status = "stalled"
                        self.reconnect_camera(handle.camera_id)
                    else:
                        # 정상 — healthy 로 마크 (초기 unknown 포함)
                        if handle.health_status in ("unknown", "reconnecting"):
                            handle.health_status = "healthy"

            except Exception:
                _logger.exception("워치도그 루프 오류 (계속)")

            # 다음 체크까지 대기 (stop_event 기다리면 조기 종료 가능)
            self._watchdog_stop_event.wait(self._watchdog_interval_sec)

    def get_health_all(self) -> dict[str, dict[str, object]]:
        """전체 카메라 헬스 상태 조회."""
        with self._lock:
            handles = list(self._cameras.values())

        result: dict[str, dict[str, object]] = {}
        for h in handles:
            stats = h.decoder.stats
            result[h.camera_id] = {
                "camera_id": h.camera_id,
                "connected": h.connected,
                "health_status": h.health_status,
                "frames_decoded": stats.frames_decoded,
                "frames_failed": stats.frames_failed,
                "consecutive_failures": stats.consecutive_failures,
                "seconds_since_last_frame": round(h.decoder.seconds_since_last_frame(), 2),
                "reconnect_attempts": h.reconnect_attempts,
                "last_reconnect_time": h.last_reconnect_time,
            }
        return result

    # =========================================================================
    # 상태 조회
    # =========================================================================
    def get_status(self, camera_id: str) -> CameraStatusResponse:
        """개별 카메라 상태."""
        with self._lock:
            handle = self._cameras.get(camera_id)
        if handle is None:
            return CameraStatusResponse(camera_id=camera_id)
        return self._handle_to_status(handle)

    def get_status_all(self) -> CameraStatusAllResponse:
        """전체 카메라 상태."""
        with self._lock:
            handles = list(self._cameras.values())

        statuses = [self._handle_to_status(h) for h in handles]
        connected = sum(1 for s in statuses if s.connected)
        calibrated = sum(1 for s in statuses if s.calibrated)

        return CameraStatusAllResponse(
            cameras=statuses,
            total_cameras=len(statuses),
            connected_count=connected,
            calibrated_count=calibrated,
            all_ready=connected == len(statuses) and connected > 0,
        )

    # =========================================================================
    # 스냅샷 (미리보기)
    # =========================================================================
    def get_snapshot(self, camera_id: str) -> bytes | None:
        """
        1프레임 스냅샷 (JPEG 바이트).

        세팅 화면 미리보기용.

        Returns:
            JPEG 인코딩된 바이트 또는 None
        """
        with self._lock:
            handle = self._cameras.get(camera_id)
        if handle is None or not handle.connected:
            return None

        frame_data = handle.decoder.decode_next()
        if frame_data is None or not frame_data.is_valid:
            return None

        # JPEG 인코딩
        success, buffer = cv2.imencode(".jpg", frame_data.image, [
            cv2.IMWRITE_JPEG_QUALITY, 80,
        ])
        return buffer.tobytes() if success else None

    # =========================================================================
    # MJPEG 스트리밍 (Phase 17 S4 — 분석 디코더 공유, 별도 RTSP 연결 제거)
    # =========================================================================
    def stream_mjpeg(
        self,
        camera_id: str,
        quality: int = 60,
        max_fps: float = 10.0,
    ) -> Generator[bytes, None, None]:
        """MJPEG 스트림 제너레이터.

        Phase 17 S4 리팩토링:
          - 이전: URL당 별도 RTSP 연결 + 리더 스레드
          - 현재: handle.decoder와 공유 — RTSP 연결 1회만, 분석 파이프라인 프레임 재사용

        분석 파이프라인이 활성 상태면 decoder 에 최신 프레임이 이미 캐시돼 있어 재디코드 안 함.
        스탠드얼론 모드(경기 전)면 decode_next()가 내부에서 호출됨.

        Args:
            camera_id: 카메라 식별자
            quality: JPEG 품질 (1-100)
            max_fps: 최대 전송 FPS

        Yields:
            multipart/x-mixed-replace 바이너리 프레임
        """
        with self._lock:
            handle = self._cameras.get(camera_id)
        if handle is None or not handle.connected:
            return

        min_interval = 1.0 / max_fps if max_fps > 0 else 0.1
        boundary = b"--frame\r\n"
        last_frame: bytes | None = None

        try:
            while True:
                t0 = time.monotonic()

                # decoder의 캐시된 최신 프레임 → JPEG (공유)
                jpg_bytes = handle.decoder.get_or_decode_latest_jpeg(
                    quality=quality,
                    max_width=1280,
                    max_height=720,
                    max_age_sec=0.5,
                )

                if jpg_bytes is not None and jpg_bytes is not last_frame:
                    last_frame = jpg_bytes
                    yield (
                        boundary
                        + b"Content-Type: image/jpeg\r\n"
                        + f"Content-Length: {len(jpg_bytes)}\r\n\r\n".encode()
                        + jpg_bytes
                        + b"\r\n"
                    )

                elapsed = time.monotonic() - t0
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
        except GeneratorExit:
            pass

    # =========================================================================
    # 캘리브레이션
    # =========================================================================
    def calibrate(self, request: CameraCalibrationRequest) -> CameraCalibrationResponse:
        """
        개별 카메라 캘리브레이션.

        코트 라인 인식 → 호모그래피 산출 → 품질 점수 반환.

        Args:
            request: 캘리브레이션 요청

        Returns:
            CameraCalibrationResponse
        """
        cam_id = request.camera_id

        with self._lock:
            handle = self._cameras.get(cam_id)
        if handle is None or not handle.connected:
            return CameraCalibrationResponse(
                camera_id=cam_id,
                message="카메라가 연결되지 않았습니다.",
            )

        # 프레임 캡처
        frame_data = handle.decoder.decode_next()
        if frame_data is None or not frame_data.is_valid:
            return CameraCalibrationResponse(
                camera_id=cam_id,
                message="프레임을 캡처할 수 없습니다.",
            )

        # 코트 감지로 캘리브레이션 품질 판단
        court_detected = False
        quality = 0.0

        if self._court_detector is not None:
            try:
                court_result = self._court_detector.detect_court(frame_data.image)
                court_detected = len(court_result.court_lines) > 0
                quality = getattr(court_result, "calibration_quality", 0.0)
                if court_detected and quality == 0.0:
                    quality = court_result.confidence
            except Exception:
                _logger.exception("캘리브레이션 코트 감지 실패: %s", cam_id)

        # 캘리브레이터로 정밀 캘리브레이션
        if self._calibrator is not None:
            try:
                snapshot = self._calibrator.calibrate_single(cam_id)
                if snapshot is not None:
                    quality = max(quality, snapshot.reprojection_error)
            except Exception:
                _logger.exception("캘리브레이터 실행 실패: %s", cam_id)

        # 결과 반영
        handle.calibrated = court_detected and quality >= 0.3
        handle.calibration_quality = quality

        status = "인식 OK" if handle.calibrated else "조정 필요"
        _logger.info("캘리브레이션 완료: %s → %s (quality=%.2f)", cam_id, status, quality)

        return CameraCalibrationResponse(
            camera_id=cam_id,
            success=handle.calibrated,
            court_detected=court_detected,
            calibration_quality=quality,
            message=status,
        )

    # =========================================================================
    # 수동 캘리브레이션 (고정 카메라 1회 설정)
    # =========================================================================
    def calibrate_manual(
        self, request: ManualCalibrationRequest,
    ) -> ManualCalibrationResponse:
        """
        수동 캘리브레이션 — UI에서 사용자가 클릭한 좌표로 호모그래피 계산.

        고정 카메라 설치 시 1회 실행합니다. 사용자가 카메라 화면에서
        코트 교차점을 클릭하면 해당 pixel 좌표와 실제 코트 좌표(미터)를
        대응시켜 호모그래피 매트릭스를 계산하고 JSON으로 저장합니다.

        Args:
            request: 수동 캘리브레이션 요청 (pixel_points, court_points, court_standard)

        Returns:
            ManualCalibrationResponse (품질 점수, 재투영 오차 등)
        """
        cam_id = request.camera_id
        pixel_pts = np.array(request.pixel_points, dtype=np.float64)
        court_pts = np.array(request.court_points, dtype=np.float64)

        # 포인트 수 검증
        if len(pixel_pts) != len(court_pts):
            return ManualCalibrationResponse(
                camera_id=cam_id,
                message="pixel_points와 court_points 개수가 일치하지 않습니다.",
            )
        if len(pixel_pts) < 4:
            return ManualCalibrationResponse(
                camera_id=cam_id,
                message="최소 4개 포인트가 필요합니다.",
            )

        # RANSAC 호모그래피 계산
        homography, mask = cv2.findHomography(
            pixel_pts, court_pts, cv2.RANSAC, ransacReprojThreshold=3.0,
        )
        if homography is None:
            return ManualCalibrationResponse(
                camera_id=cam_id,
                message="호모그래피 계산 실패 — 포인트 배치를 확인하세요.",
            )

        # 품질 평가: 재투영 오차 계산
        inlier_mask = mask.ravel().astype(bool)
        inlier_count = int(inlier_mask.sum())
        total_points = len(pixel_pts)

        # 재투영 오차 (pixel → court → pixel 왕복)
        projected = cv2.perspectiveTransform(
            pixel_pts.reshape(-1, 1, 2), homography,
        ).reshape(-1, 2)
        errors = np.linalg.norm(projected - court_pts, axis=1)
        mean_reproj = float(errors[inlier_mask].mean()) if inlier_count > 0 else 999.0

        # 품질 점수 (0~1)
        inlier_ratio = inlier_count / total_points
        reproj_score = max(0.0, 1.0 - mean_reproj / 5.0)
        kp_score = min(inlier_count / 8.0, 1.0)
        quality_score = 0.30 * inlier_ratio + 0.50 * reproj_score + 0.20 * kp_score

        # 역행렬 (court → pixel)
        inverse_homography = np.linalg.inv(homography)

        # JSON 저장
        success = self._save_calibration(
            cam_id=cam_id,
            homography=homography,
            inverse_homography=inverse_homography,
            quality_score=quality_score,
            mean_reproj_error=mean_reproj,
            inlier_count=inlier_count,
            total_points=total_points,
            court_standard=request.court_standard,
            pixel_points=request.pixel_points,
            court_points=request.court_points,
        )

        # 카메라 핸들 상태 업데이트
        with self._lock:
            handle = self._cameras.get(cam_id)
            if handle is not None:
                handle.calibrated = success and quality_score >= 0.5
                handle.calibration_quality = quality_score

        status_msg = (
            f"캘리브레이션 완료 (품질: {quality_score:.2f}, 오차: {mean_reproj:.2f}px)"
            if success
            else "캘리브레이션 저장 실패"
        )
        _logger.info("수동 캘리브레이션: %s → %s", cam_id, status_msg)

        return ManualCalibrationResponse(
            camera_id=cam_id,
            success=success and quality_score >= 0.3,
            quality_score=round(quality_score, 4),
            mean_reproj_error_px=round(mean_reproj, 4),
            inlier_count=inlier_count,
            total_points=total_points,
            message=status_msg,
        )

    def _save_calibration(
        self,
        cam_id: str,
        homography: np.ndarray,
        inverse_homography: np.ndarray,
        quality_score: float,
        mean_reproj_error: float,
        inlier_count: int,
        total_points: int,
        court_standard: str,
        pixel_points: list[list[float]],
        court_points: list[list[float]],
    ) -> bool:
        """캘리브레이션 결과를 JSON 파일로 저장."""
        _CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
        cal_path = _CALIBRATION_DIR / f"cam_{cam_id}.json"

        data = {
            "camera_id": cam_id,
            "court_standard": court_standard,
            "homography": homography.tolist(),
            "inverse_homography": inverse_homography.tolist(),
            "quality_score": quality_score,
            "mean_reproj_error_px": mean_reproj_error,
            "inlier_count": inlier_count,
            "total_points": total_points,
            "pixel_points": pixel_points,
            "court_points": court_points,
        }

        try:
            with open(cal_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            _logger.info("캘리브레이션 저장: %s", cal_path)
            return True
        except Exception:
            _logger.exception("캘리브레이션 저장 실패: %s", cal_path)
            return False

    @staticmethod
    def load_calibration(camera_id: str) -> dict | None:
        """저장된 캘리브레이션 JSON 로드."""
        cal_path = _CALIBRATION_DIR / f"cam_{camera_id}.json"
        if not cal_path.exists():
            return None
        try:
            with open(cal_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["homography"] = np.array(data["homography"], dtype=np.float64)
            data["inverse_homography"] = np.array(
                data["inverse_homography"], dtype=np.float64,
            )
            return data
        except Exception:
            _logger.exception("캘리브레이션 로드 실패: %s", cal_path)
            return None

    # =========================================================================
    # AI 감지 테스트
    # =========================================================================
    def ai_test(self, request: CameraAITestRequest) -> CameraAITestResponse:
        """
        1프레임 AI 감지 테스트.

        코트/선수/공/골대를 감지하여 인식 상태를 반환합니다.
        세팅 화면의 "AI 테스트" 버튼에 대응합니다.

        Args:
            request: AI 테스트 요청

        Returns:
            CameraAITestResponse
        """
        cam_id = request.camera_id
        targets = set(request.test_targets)

        with self._lock:
            handle = self._cameras.get(cam_id)
        if handle is None or not handle.connected:
            return CameraAITestResponse(
                camera_id=cam_id,
                overall_status="error",
                message="카메라가 연결되지 않았습니다.",
            )

        # 프레임 캡처
        frame_data = handle.decoder.decode_next()
        if frame_data is None or not frame_data.is_valid:
            return CameraAITestResponse(
                camera_id=cam_id,
                overall_status="error",
                message="프레임을 캡처할 수 없습니다.",
            )

        frame = frame_data.image
        court_ok = False
        court_conf = 0.0
        players = 0
        ball_ok = False
        ball_conf = 0.0
        hoops = 0

        # 코트 감지
        if "court" in targets and self._court_detector is not None:
            try:
                result = self._court_detector.detect_court(frame)
                court_ok = len(result.court_lines) > 0
                court_conf = result.confidence
            except Exception:
                _logger.exception("AI 테스트 코트 감지 실패: %s", cam_id)

        # 선수 감지
        if "player" in targets and self._player_detector is not None:
            try:
                result = self._player_detector.detect(frame, camera_id=cam_id)
                players = len(result.objects)
            except Exception:
                _logger.exception("AI 테스트 선수 감지 실패: %s", cam_id)

        # 공 감지
        if "ball" in targets and self._ball_detector is not None:
            try:
                result = self._ball_detector.detect(frame)
                ball_ok = len(result.detections) > 0
                if result.detections:
                    ball_conf = result.detections[0].confidence
            except Exception:
                _logger.exception("AI 테스트 공 감지 실패: %s", cam_id)

        # 골대 감지
        if "hoop" in targets and self._hoop_detector is not None:
            try:
                result = self._hoop_detector.detect_hoops(frame)
                hoops = len(result.hoops)
            except Exception:
                _logger.exception("AI 테스트 골대 감지 실패: %s", cam_id)

        # 종합 판정
        issues: list[str] = []
        if "court" in targets and not court_ok:
            issues.append("코트 미인식")
        if "player" in targets and players == 0:
            issues.append("선수 미감지")
        if "hoop" in targets and hoops == 0:
            issues.append("골대 미감지")

        if not issues:
            overall = "ok"
            message = "인식 OK"
        elif len(issues) <= 1:
            overall = "warning"
            message = f"⚠️ 조정 필요: {', '.join(issues)}"
        else:
            overall = "error"
            message = f"❌ 문제 감지: {', '.join(issues)}"

        _logger.info("AI 테스트 완료: %s → %s", cam_id, overall)

        return CameraAITestResponse(
            camera_id=cam_id,
            court_detected=court_ok,
            court_confidence=court_conf,
            players_detected=players,
            ball_detected=ball_ok,
            ball_confidence=ball_conf,
            hoops_detected=hoops,
            overall_status=overall,
            message=message,
        )

    # =========================================================================
    # 설정 저장/불러오기
    # =========================================================================
    def save_config(self, request: CameraSaveConfigRequest) -> bool:
        """카메라 설정을 JSON 파일에 저장."""
        config_path = self._config_dir / _DEFAULT_CONFIG_FILE
        self._config_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "config_name": request.config_name,
            "cameras": [
                {
                    "camera_id": cam.camera_id,
                    "url": cam.url,
                    "label": cam.label,
                }
                for cam in request.cameras
            ],
        }

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            _logger.info("카메라 설정 저장: %s (%d대)", config_path, len(data["cameras"]))
            return True
        except Exception:
            _logger.exception("카메라 설정 저장 실패")
            return False

    def load_config(self) -> list[dict[str, str]]:
        """저장된 카메라 설정 불러오기."""
        config_path = self._config_dir / _DEFAULT_CONFIG_FILE
        if not config_path.exists():
            return []

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("cameras", [])
        except Exception:
            _logger.exception("카메라 설정 불러오기 실패")
            return []

    # =========================================================================
    # 서브넷 자동 감지
    # =========================================================================
    @staticmethod
    def detect_local_subnet() -> str:
        """
        모든 네트워크 인터페이스에서 서브넷을 추출한다.

        노트북처럼 WiFi + 유선 + VPN 등 다중 인터페이스 환경에서
        단일 socket.connect(("8.8.8.8", 80)) 방식은 기본 게이트웨이 하나만
        반환하기 때문에 카메라가 연결된 인터페이스를 놓치게 된다.

        Returns:
            쉼표로 구분된 서브넷 문자열 (예: "192.168.1,192.168.24").
            감지 실패 시 기본값 "192.168.24" 반환.
        """
        import socket
        subnets: list[str] = []

        # 1차: psutil로 모든 네트워크 인터페이스 열거
        try:
            import psutil
            for name, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family != socket.AF_INET:
                        continue
                    ip = addr.address
                    if ip.startswith("127."):
                        continue
                    parts = ip.split(".")
                    if len(parts) == 4:
                        subnet = ".".join(parts[:3])
                        if subnet not in subnets:
                            subnets.append(subnet)
                            _logger.info(
                                "서브넷 감지: %s (%s, %s)", subnet, name, ip,
                            )
        except ImportError:
            pass

        # 2차: psutil 미설치 또는 실패 시 hostname 폴백
        if not subnets:
            try:
                hostname = socket.gethostname()
                for ip_info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                    addr_str = ip_info[4][0]
                    if addr_str.startswith("127."):
                        continue
                    subnet = ".".join(addr_str.split(".")[:3])
                    if subnet not in subnets:
                        subnets.append(subnet)
            except Exception:
                pass

        if not subnets:
            _logger.warning("서브넷 자동 감지 실패, 기본값 사용")
            return "192.168.24"
        return ",".join(subnets)

    # =========================================================================
    # 자동 탐색 (네트워크 스캔)
    # =========================================================================
    def discover(
        self,
        subnet: str = "192.168.1",
        port: int = 554,
        timeout_sec: float = 0.3,
        start: int = 1,
        end: int = 254,
    ) -> list[dict[str, str]]:
        """
        단일 서브넷 스캔 (하위 호환).

        여러 서브넷을 한 번에 스캔하려면 discover_many() 를 쓰세요 — IP 전부를
        하나의 풀에 던져 병렬성을 최대화하므로 훨씬 빠릅니다.
        """
        return self.discover_many([subnet], port=port, timeout_sec=timeout_sec, start=start, end=end)

    @staticmethod
    def _find_link_local_source(target_ip: str) -> str | None:
        """
        target_ip(169.254.x.y) 와 **같은 /24 서브넷** 을 가진 로컬 NIC 의 APIPA
        주소를 찾아 반환. socket.bind((source, 0)) 에 써서 해당 NIC 로 out-routing
        을 강제한다.

        배경: 다중 NIC (이더넷 + Wi-Fi + Wi-Fi Direct 등) 환경에서 각 NIC 가 서로
              다른 169.254.*.* APIPA 를 받는다. Windows 기본 라우팅은 route metric
              이 낮은 Wi-Fi 를 먼저 선택하므로 이더넷에 연결된 카메라도 Wi-Fi 로
              out 시도 → 실패. 사용자가 route/metric 만지지 않아도 되도록 소켓을
              이더넷 APIPA 에 직접 bind 해 버린다.

        /24 매치 기준: target=169.254.24.13 이면 source 는 169.254.24.x 여야 같은
        서브넷. 다른 /24 의 APIPA (예: Wi-Fi Direct 169.254.216.x) 는 제외.

        Returns:
            적합한 source IP (예: "169.254.24.236"), 없으면 None
        """
        if not target_ip.startswith("169.254."):
            return None
        prefix = ".".join(target_ip.split(".")[:3]) + "."
        try:
            import psutil  # type: ignore[import-not-found]
            import socket as _s
            for name, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == _s.AF_INET and addr.address.startswith(prefix):
                        return addr.address
        except Exception:
            return None
        return None

    @staticmethod
    def _prewarm_arp(ips: list[str], timeout_ms: int = 200) -> None:
        """
        각 IP 로 ping 을 병렬 발사해 ARP 테이블 + Windows 라우팅 결정 (route metric)
        을 사전 예열한다.

        배경: 다중 NIC (Wi-Fi + 이더넷 APIPA) 환경에서 Windows 가 처음엔 기본
              게이트웨이 있는 Wi-Fi 인터페이스로 패킷을 보내려다 실패하고, 재시도
              해야 링크-로컬 이더넷을 찾는다. socket.connect 의 짧은 timeout
              (300~500 ms) 로는 첫 시도 실패 뒤 재시도까지 끝내기 어려움.
              ping 한 번 선행시키면 Windows 가 올바른 interface 선택을 "학습" 한다.

        실측 증거: 노트북 APIPA 환경에서 첫 discover → 0 대, ping 후 discover → 1 대.
        """
        import subprocess

        creationflags = 0
        if sys.platform == "win32":
            # CREATE_NO_WINDOW — 콘솔 창 뜨지 않게
            creationflags = 0x08000000

        def _ping(ip: str) -> None:
            try:
                subprocess.run(
                    ["ping", "-n", "1", "-w", str(timeout_ms), ip],
                    capture_output=True,
                    timeout=(timeout_ms / 1000.0) + 1.0,
                    creationflags=creationflags,
                )
            except Exception:
                pass

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(len(ips), 512), thread_name_prefix="arp-prewarm") as pool:
            list(pool.map(_ping, ips))

    def discover_many(
        self,
        subnets: list[str],
        port: int = 554,
        timeout_sec: float = 0.5,
        start: int = 1,
        end: int = 254,
        prewarm: bool = True,
    ) -> list[dict[str, str]]:
        """
        여러 서브넷을 단일 스레드 풀로 한 번에 스캔한다.

        THE RECORD (C# AICourtView) 의 CameraScan 방식을 반영 + Windows 다중 NIC
        환경의 라우팅 지연을 ping prewarm 으로 보정:
          - 먼저 ARP prewarm (ping sweep, ~200 ms/IP, 모두 병렬): Windows 가 올바른
            interface 를 학습하게 함 (Wi-Fi 에서 APIPA 로 오라우팅 방지).
          - 이후 TCP 554 probe: 서브넷별로 for-loop 순차가 아니라 전체 IP 를 한 풀에.
          - per-IP timeout 500 ms (300 ms 는 Python socket 에서 아슬아슬, 500 ms 안전).

        Args:
            subnets: ["169.254.24", "192.168.1", ...] 형태
            port: RTSP 포트 (기본 554)
            timeout_sec: per-IP TCP connect timeout (기본 500 ms)
            start/end: 스캔 옥텟 범위 (기본 1~254)
            prewarm: True 면 ping sweep 선행 (기본 True, 현장 APIPA 환경에 필수)
        """
        import socket
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 공백·중복 제거
        subnets = [s.strip() for s in subnets if s and s.strip()]
        subnets = list(dict.fromkeys(subnets))
        if not subnets:
            return []

        ips: list[str] = []
        for subnet in subnets:
            ips.extend(f"{subnet}.{i}" for i in range(start, end + 1))

        if prewarm:
            t0 = time.monotonic()
            self._prewarm_arp(ips)
            _logger.info("ARP prewarm 완료: %d IP × ping (%.1f s)", len(ips), time.monotonic() - t0)

        # 같은 /24 의 link-local source 를 미리 찾아둔다 (서브넷당 1회 계산).
        # 예: target 169.254.24.* 의 source = 169.254.24.236 (이더넷 APIPA)
        sources: dict[str, str | None] = {}
        for sn in subnets:
            sample_target = f"{sn}.1"
            sources[sn] = self._find_link_local_source(sample_target)

        def _probe(ip: str) -> dict[str, str] | None:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(timeout_sec)
                    # 169.254.x.x 타겟이면 같은 /24 의 source IP 로 bind →
                    # Windows route metric 무관하게 해당 NIC 로 강제 out-routing.
                    # 이게 Wi-Fi 가 먼저 선택되는 문제 (route_metric 경쟁) 를 근본 차단.
                    target_prefix = ".".join(ip.split(".")[:3])
                    src = sources.get(target_prefix)
                    if src:
                        try:
                            sock.bind((src, 0))
                        except OSError:
                            pass  # bind 실패해도 일반 connect 는 시도
                    if sock.connect_ex((ip, port)) == 0:
                        return {
                            "ip": ip,
                            "port": str(port),
                            "rtsp_url": f"rtsp://{ip}:{port}/stream1",
                        }
            except Exception:
                pass
            return None

        max_workers = min(len(ips), 512)
        found: list[dict[str, str]] = []

        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cam-disc") as pool:
            futures = [pool.submit(_probe, ip) for ip in ips]
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    found.append(result)

        found.sort(key=lambda x: tuple(int(p) for p in x["ip"].split(".")))
        _logger.info(
            "카메라 탐색 완료: %d 서브넷 × %d IP → %d대 발견 (probe %.1f s, timeout=%.0f ms)",
            len(subnets), end - start + 1, len(found),
            time.monotonic() - t0, timeout_sec * 1000,
        )
        return found

    # =========================================================================
    # 내부 유틸리티
    # =========================================================================
    @staticmethod
    def _handle_to_status(handle: _CameraHandle) -> CameraStatusResponse:
        """_CameraHandle → CameraStatusResponse 변환."""
        return CameraStatusResponse(
            camera_id=handle.camera_id,
            label=handle.label,
            url=handle.url,
            connected=handle.connected,
            width=handle.width,
            height=handle.height,
            fps=handle.fps,
            calibrated=handle.calibrated,
            calibration_quality=handle.calibration_quality,
        )

    def __repr__(self) -> str:
        with self._lock:
            total = len(self._cameras)
            connected = sum(1 for h in self._cameras.values() if h.connected)
        return f"CameraService(cameras={connected}/{total})"


__all__ = ["CameraService"]
__version__ = "1.0.0"
