# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine
파일: config.py
설명: 엔진 정적 설정 데이터 클래스
      - EngineMode: 라이브/배치/리플레이 모드
      - TRTPrecision: TensorRT 정밀도 (FP32/FP16/INT8)
      - CadenceLevel: 5등급 파이프라인 실행 주기
      - GPUConfig: GPU/VRAM/발열/배치 설정
      - CameraConfig: 카메라 수/해상도/FPS/동기화/듀얼 스트림
      - CadenceConfig: 각 Cadence별 실행 주기 및 스레드 풀 크기
      - PipelineConfig: 모델 경로/Stage2 트리거/융합 임계치
      - RefereeConfig: AI 심판 규정/신뢰도/리플레이 윈도우
      - IOConfig: WebSocket/경로/클라우드 설정
      - EngineConfig: 위 6개 통합 + 모드/디버그/프로파일링

      하드웨어 기준:
        - GPU: RTX 5060 8GB (프로덕션), RTX 5070 Ti 16GB (개발)
        - 카메라: ASECAM C*MPHS-2MM × 8대 (8MP/4MP 듀얼 스트림)
        - 분석용: 서브 스트림 1080p 30fps (RTSP)
        - 녹화용: 메인 스트림 4K (SSD 직접 저장)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - shared/constants/referee_rule_constants.py: RuleSet (리그별 규칙)
    - core_foundation/config/loader.py: YAML 설정 로딩 (런타임)

소비자:
    - engine/game_state.py: CadenceLevel, EngineMode
    - engine/gpu/*: GPUConfig
    - engine/pipeline/*: PipelineConfig, CadenceConfig
    - engine/orchestrator/*: EngineConfig
    - engine/io/*: IOConfig, CameraConfig
    - engine/referee/*: RefereeConfig
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from shared.constants.player_constants import AgeGroup, Gender
from shared.constants.referee_rule_constants import RuleSet


# =============================================================================
# 엔진 모드 열거형
# =============================================================================
@unique
class EngineMode(str, Enum):
    """
    엔진 실행 모드 열거형 (3종).

    Attributes:
        LIVE: 실시간 분석 (카메라 입력, FPS 제약)
        BATCH: 배치 분석 (파일 입력, 최대 속도)
        REPLAY: 리플레이 분석 (녹화 영상, 속도 조절 가능)
    """

    LIVE = "live"
    BATCH = "batch"
    REPLAY = "replay"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# TensorRT 정밀도 열거형
# =============================================================================
@unique
class TRTPrecision(str, Enum):
    """
    TensorRT 추론 정밀도 열거형 (3종).

    Attributes:
        FP32: 32비트 부동소수점 (최고 정확도, 느림)
        FP16: 16비트 부동소수점 (균형 — 프로덕션 기본)
        INT8: 8비트 정수 (최고 속도, 캘리브레이션 필요)
    """

    FP32 = "fp32"
    FP16 = "fp16"
    INT8 = "int8"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# Cadence 등급 열거형
# =============================================================================
@unique
class CadenceLevel(str, Enum):
    """
    파이프라인 실행 주기 등급 열거형 (5종).

    각 등급은 독립 파이프라인 파일에 대응합니다:
        FRAME → frame_pipeline.py (🔴 매 프레임)
        EVENT → event_pipeline.py (🟠 이벤트 감지 시)
        POSSESSION → possession_pipeline.py (🟡 점유 종료 시)
        PERIOD → period_pipeline.py (🟢 쿼터 종료 시)
        POSTGAME → postgame_pipeline.py (🔵 경기 종료 후)

    Attributes:
        FRAME: 매 프레임 실행 (감지/포즈/트래킹, 33ms 이내)
        EVENT: 이벤트 발생 시 실행 (통계 증분, <10ms)
        POSSESSION: 점유 종료 시 실행 (전술/개인, <100ms)
        PERIOD: 쿼터 종료 시 실행 (요약/추세, <1s)
        POSTGAME: 경기 종료 후 실행 (보고서/추출, 무제한)
    """

    FRAME = "frame"
    EVENT = "event"
    POSSESSION = "possession"
    PERIOD = "period"
    POSTGAME = "postgame"

    def __str__(self) -> str:
        return self.value


# =============================================================================
# GPU 설정
# =============================================================================
@dataclass(slots=True)
class GPUConfig:
    """
    GPU 리소스 설정.

    Attributes:
        vram_limit_mb: VRAM 상한 (MB, 0=자동 감지)
        trt_precision: TensorRT 정밀도
        num_cuda_streams: CUDA 스트림 수 (Stage1 + Stage2)
        thermal_warning_celsius: 발열 경고 온도 (°C)
        thermal_critical_celsius: 발열 위험 온도 (°C, 스로틀링)
        detection_batch_size: Stage1 감지 배치 크기
        pose_stage1_batch_size: Stage1 포즈(YOLOv8-Pose) 배치 크기
        pose_stage2_batch_size: Stage2 포즈(ViTPose) 배치 크기
    """

    vram_limit_mb: int = 0
    trt_precision: TRTPrecision = TRTPrecision.FP16
    num_cuda_streams: int = 2
    thermal_warning_celsius: float = 85.0
    thermal_critical_celsius: float = 95.0
    detection_batch_size: int = 8
    pose_stage1_batch_size: int = 16
    pose_stage2_batch_size: int = 4


# =============================================================================
# 카메라 설정
# =============================================================================
@dataclass(slots=True)
class CameraConfig:
    """
    멀티카메라 설정 (ASECAM 듀얼 스트림).

    Attributes:
        num_cameras: 카메라 수 (4~8)
        analysis_width: 분석용 가로 해상도 (px)
        analysis_height: 분석용 세로 해상도 (px)
        target_fps: 목표 FPS (ASECAM 서브스트림 기준 30fps)
        sync_tolerance_ms: 동기화 허용 오차 (ms)
        sync_method: 동기화 방식 (timestamp/hardware)
        input_source: 입력 소스 (rtsp/file/usb)
        recording_enabled: 4K 녹화 활성화 여부
        recording_width: 녹화용 가로 해상도 (px)
        recording_height: 녹화용 세로 해상도 (px)
        recording_codec: 녹화 코덱 (h264/h265)
    """

    num_cameras: int = 8
    analysis_width: int = 1920
    analysis_height: int = 1080
    target_fps: int = 30
    # 2026-05-13: 1.0 → 33.33 → 50.0.
    #   1.0  : GENLOCK HW 동기화 가정 — software RTSP 환경에선 영원히 align 실패
    #   33.33: 1 frame @ 30fps — 표준값이지만 RTSP jitter (네트워크+카메라) 가 30ms 보다 커서 fail
    #   50.0 : RTSP IPCam 환경 실용값. min_cameras=8 (모든 카메라 필요) 유지하고
    #          tolerance 만 약간 풀어줘 jitter 흡수. 3D triangulation 정확도 유지.
    #          공 10m/s 가정 시 50ms 격차 = 50cm 위치 오차 (코트 28m 의 1.8%).
    sync_tolerance_ms: float = 50.0
    sync_method: str = "timestamp"
    input_source: str = "rtsp"
    recording_enabled: bool = True
    recording_width: int = 3840
    recording_height: int = 2160
    recording_codec: str = "h265"


# =============================================================================
# Cadence 설정
# =============================================================================
@dataclass(slots=True)
class CadenceConfig:
    """
    Cadence별 실행 주기 및 스레드 풀 설정.

    Attributes:
        frame_budget_ms: FRAME 등급 시간 예산 (ms)
        frame_module_budget_ms: FRAME 등급 개별 모듈 예산 (ms)
        event_budget_ms: EVENT 등급 시간 예산 (ms)
        possession_budget_ms: POSSESSION 등급 시간 예산 (ms)
        possession_threads: POSSESSION 워커 스레드 수
        period_budget_ms: PERIOD 등급 시간 예산 (ms)
        period_threads: PERIOD 워커 스레드 수
    """

    frame_budget_ms: float = 33.0
    frame_module_budget_ms: float = 4.0
    event_budget_ms: float = 10.0
    possession_budget_ms: float = 100.0
    possession_threads: int = 4
    period_budget_ms: float = 1000.0
    period_threads: int = 2


# =============================================================================
# 파이프라인 설정
# =============================================================================
@dataclass(slots=True)
class PipelineConfig:
    """
    파이프라인 모델 및 융합 설정.

    Attributes:
        model_yolov8_det: YOLOv8 감지 모델 경로
        model_yolov8_pose: YOLOv8 포즈 모델 경로
        model_vitpose: ViTPose 모델 경로
        stage2_triggers: Stage2 트리거 이벤트 목록
        fusion_nms_threshold: 멀티카메라 NMS IoU 임계치
        fusion_triangulation_error_m: 삼각측량 최대 재투영 오차 (m)
        fusion_tracking_iou_threshold: 트래킹 융합 IoU 임계치
        result_cache_ttl_sec: 결과 캐시 TTL (초)
    """

    model_yolov8_det: str = "weights/yolov8s.onnx"
    model_yolov8_pose: str = "weights/yolo11l-pose.pt"  # v0.5.1: ultralytics 가 PyTorch 만 .to(device) 가능
    model_vitpose: str = "weights/vitpose-b-wholebody.onnx"
    stage2_triggers: tuple[str, ...] = (
        "shooting_detected",
        "foul_contact",
        "violation_suspected",
        "close_play",
    )
    fusion_nms_threshold: float = 0.5
    fusion_triangulation_error_m: float = 0.3
    fusion_tracking_iou_threshold: float = 0.4
    result_cache_ttl_sec: int = 5


# =============================================================================
# AI 심판 설정
# =============================================================================
@dataclass(slots=True)
class RefereeConfig:
    """
    AI 심판 설정.

    Attributes:
        rule_set: 적용 규정 (FIBA/NBA/KBL/NBL/EUROLEAGUE)
        min_confidence: 최소 판정 신뢰도
        multi_angle_agreement: 멀티앵글 합의 비율
        replay_window_sec: 리플레이 검토 윈도우 (초)
        auto_confirm_threshold: 자동 확정 신뢰도 임계치
    """

    rule_set: RuleSet = RuleSet.FIBA
    min_confidence: float = 0.75
    multi_angle_agreement: float = 0.75
    replay_window_sec: float = 10.0
    auto_confirm_threshold: float = 0.95


# =============================================================================
# 입출력 설정
# =============================================================================
@dataclass(slots=True)
class IOConfig:
    """
    입출력 설정.

    Attributes:
        websocket_host: WebSocket 서버 호스트
        websocket_port: WebSocket 서버 포트
        output_dir: 분석 결과 출력 디렉토리
        export_dir: 내보내기 디렉토리
        log_dir: 로그 디렉토리
        demo_page_path: 데모 HTML 경로 (프로젝트 루트 기준 상대경로)
        cloud_sync_enabled: 클라우드 동기화 활성화
        cloud_sync_url: 클라우드 동기화 엔드포인트
        progress_interval_ms: 진행률 보고 주기 (ms)
    """

    websocket_host: str = "localhost"
    websocket_port: int = 8000
    output_dir: str = "output"
    export_dir: str = "export"
    log_dir: str = "logs"
    demo_page_path: str = "tests/demo_page.html"
    cloud_sync_enabled: bool = False
    cloud_sync_url: str = ""
    progress_interval_ms: float = 500.0


# =============================================================================
# 엔진 통합 설정
# =============================================================================
@dataclass(slots=True)
class EngineConfig:
    """
    엔진 최상위 통합 설정.

    6개 서브 설정 + 모드/디버그/프로파일링을 묶은 루트 설정.

    Attributes:
        mode: 엔진 실행 모드
        gpu: GPU 리소스 설정
        camera: 멀티카메라 설정
        cadence: Cadence별 실행 주기 설정
        pipeline: 파이프라인 모델/융합 설정
        referee: AI 심판 설정
        io: 입출력 설정
        debug: 디버그 모드 활성화
        profiling: 프로파일링 활성화
    """

    mode: EngineMode = EngineMode.LIVE
    gpu: GPUConfig = field(default_factory=GPUConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    cadence: CadenceConfig = field(default_factory=CadenceConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    referee: RefereeConfig = field(default_factory=RefereeConfig)
    io: IOConfig = field(default_factory=IOConfig)
    # 선수 연령/성별 기본값 (경기 설정에서 오버라이드 가능)
    age_group: AgeGroup = AgeGroup.ADULT
    gender: Gender = Gender.MALE
    debug: bool = False
    profiling: bool = False


# =============================================================================
# GPU 프로파일 (하드웨어별 프리셋)
# =============================================================================

# RTX 4060 8GB (엔트리급)
RTX_4060_PROFILE: Final[GPUConfig] = GPUConfig(
    vram_limit_mb=8192,
    trt_precision=TRTPrecision.FP16,
    num_cuda_streams=2,
    detection_batch_size=4,
    pose_stage1_batch_size=8,
    pose_stage2_batch_size=2,
)

# RTX 4070 12GB (렌탈 노트북 중급)
RTX_4070_PROFILE: Final[GPUConfig] = GPUConfig(
    vram_limit_mb=12288,
    trt_precision=TRTPrecision.FP16,
    num_cuda_streams=2,
    detection_batch_size=6,
    pose_stage1_batch_size=12,
    pose_stage2_batch_size=3,
)

# RTX 4080 16GB (렌탈 노트북 상급)
RTX_4080_PROFILE: Final[GPUConfig] = GPUConfig(
    vram_limit_mb=16384,
    trt_precision=TRTPrecision.FP16,
    num_cuda_streams=2,
    detection_batch_size=8,
    pose_stage1_batch_size=16,
    pose_stage2_batch_size=4,
)

# RTX 5070 Ti 16GB (개발 기준)
RTX_5070_PROFILE: Final[GPUConfig] = GPUConfig(
    vram_limit_mb=16384,
    trt_precision=TRTPrecision.FP16,
    num_cuda_streams=2,
    detection_batch_size=8,
    pose_stage1_batch_size=16,
    pose_stage2_batch_size=4,
)

# RTX 4090 24GB (고성능)
RTX_4090_PROFILE: Final[GPUConfig] = GPUConfig(
    vram_limit_mb=24576,
    trt_precision=TRTPrecision.FP16,
    num_cuda_streams=2,
    detection_batch_size=8,
    pose_stage1_batch_size=32,
    pose_stage2_batch_size=8,
)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 열거형
    "EngineMode",
    "TRTPrecision",
    "CadenceLevel",
    # 설정 데이터 클래스
    "GPUConfig",
    "CameraConfig",
    "CadenceConfig",
    "PipelineConfig",
    "RefereeConfig",
    "IOConfig",
    "EngineConfig",
    # GPU 프로파일
    "RTX_4060_PROFILE",
    "RTX_4070_PROFILE",
    "RTX_4080_PROFILE",
    "RTX_5070_PROFILE",
    "RTX_4090_PROFILE",
]

__version__ = "1.0.0"
