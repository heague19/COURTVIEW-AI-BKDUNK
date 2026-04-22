# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: engine/orchestrator
파일: game_orchestrator.py
설명: 경기 전체 수명주기 오케스트레이터
      - 엔진 상태 FSM 제어 (IDLE→LOADING→RUNNING→PAUSED→STOPPED)
      - LOADING 단계: GPU/카메라/모델/감지기/분석기/심판 전체 초기화
      - RUNNING 단계: cadence_scheduler.tick() 메인 루프
      - 파이프라인 콜백 등록 (5등급 Cadence)
      - 모든 서브 모듈 수명주기 통합 관리

      데이터 흐름:
        start_game() → LOADING → initialize_all() → RUNNING
          → main_loop: cadence_scheduler.tick() 반복
            → frame_pipeline (🔴) → event_pipeline (🟠)
            → possession_pipeline (🟡) → period_pipeline (🟢)
            → postgame_pipeline (🔵)
        stop_game() → STOPPED → shutdown_all()

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-27
버전: 1.0.0

의존성:
    - engine/config.py: EngineConfig
    - engine/game_state.py: EngineGameStateManager, EngineState
    - engine/gpu/: GPUManager, CUDAStreamManager, TensorRTPool, BatchAccumulator
    - engine/io/frame_ingestion.py: FrameIngestion
    - engine/pipeline/: FramePipeline, EventPipeline, PossessionPipeline, PeriodPipeline, PostgamePipeline
    - engine/orchestrator/cadence_scheduler.py: CadenceScheduler
    - engine/referee/referee_orchestrator.py: RefereeOrchestrator
    - engine/workers/: AnalysisWorker, ExportWorker

소비자:
    - api_server/ (Layer 9): 경기 시작/중지/일시정지 API
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import time
from pathlib import Path
from threading import RLock, Thread, Event
from typing import Any, Final

# =============================================================================
# 프로젝트 임포트
# =============================================================================
from engine.config import CadenceLevel, EngineConfig
from engine.game_state import EngineGameStateManager, EngineState
from shared.constants.game_management_constants import GameState

# engine 서브모듈 직접 임포트 (빌드 시 인스턴스 생성)
from engine.gpu.gpu_manager import GPUManager
from engine.gpu.cuda_stream_manager import CUDAStreamManager
from engine.gpu.tensorrt_pool import TensorRTPool
from engine.gpu.batch_accumulator import BatchAccumulator
from engine.io.frame_ingestion import FrameIngestion
from infrastructure.preprocessing.frame_aligner import AlignedFrameSet
# MultiViewPlayerTracker game state 매핑 (클록 tick 루프에서 반복 import 방지)
from detection.player_detection.multiview_tracker import (
    GameState as MVGameState,
    MultiViewPlayerTracker,
)
from engine.analysis_buffer import GameAnalysisBuffer
from engine.pipeline.frame_pipeline import FramePipeline, FramePipelineResult
from engine.pipeline.event_pipeline import (
    EventDetectorSet,
    EventPipeline,
    EventRealtimeSet,
    EventStatsSet,
)
from engine.pipeline.possession_pipeline import PossessionAnalyzerSet, PossessionPipeline
from engine.pipeline.period_pipeline import PeriodAnalyzerSet, PeriodPipeline
from engine.pipeline.postgame_pipeline import PostgameModuleSet, PostgamePipeline
from engine.orchestrator.cadence_scheduler import CadenceScheduler
from engine.referee.referee_orchestrator import RefereeOrchestrator
from engine.workers.analysis_worker import AnalysisWorker
from engine.workers.export_worker import ExportWorker
from engine.io.result_dispatcher import ResultDispatcher
from engine.io.progress_reporter import ProgressReporter

# detection 3서브모듈 (객체 감지 — 코트는 캘리브레이션 대체)
from detection.ball_detection.ball_detector import BallDetector
from detection.ball_detection.ball_state import BallStateMachine, PlayerPosition
from detection.player_detection.player_detector import PlayerDetector
from detection.hoop_detection.hoop_detector import HoopDetector

# pose_estimation backends (포즈 추정)
from pose_estimation.backends.base_backend import PoseBackend
from pose_estimation.backends import create_backend

# biomechanics kinematics (생체역학 기본 — 함수 기반 모듈)
from biomechanics.kinematics import velocity_analyzer as biomech_velocity
from biomechanics.kinematics import joint_angle_calculator as biomech_angle
from biomechanics.kinematics import acceleration_analyzer as biomech_accel

# motion_analysis 5Tier (동작 분석)
from motion_analysis.detection.shot_detector import ShotDetector
from motion_analysis.detection.dribble_detector import DribbleDetector
from motion_analysis.detection.pass_detector import PassDetector
from motion_analysis.detection.movement_detector import MovementDetector
from motion_analysis.detection.rebound_detector import ReboundDetector
from motion_analysis.classification.action_classifier import ActionClassifier
from motion_analysis.classification.shot_classifier import ShotClassifier
from motion_analysis.classification.dribble_classifier import DribbleClassifier
from biomechanics.phase_analysis.shot_phase_analyzer import ShotPhaseAnalyzer
from biomechanics.phase_analysis.dribble_phase_analyzer import DribblePhaseAnalyzer
from feedback_system.form_evaluation.shooting_form_evaluator import ShootingFormEvaluator
from feedback_system.form_evaluation.dribble_form_evaluator import DribbleFormEvaluator
from feedback_system.comparison.form_comparator import FormComparator

# event_detection FRAME 3종
from game_analysis.game_state.event_detection import (
    ScoreDetector, ScoreDetectorConfig,
    PossessionTracker, PossessionTrackerConfig,
    DeadBallDetector, DeadBallDetectorConfig,
)

# game_management 6파일 (경기 운영 핵심)
from game_analysis.game_state.game_management import (
    ClockManager, ClockManagerConfig,
    FoulManager, FoulManagerConfig,
    SubstitutionManager, SubstitutionManagerConfig,
    TimeoutManager, TimeoutManagerConfig,
    RecordCorrector, RecordCorrectorConfig,
    OfficialFormatExporter, OfficialFormatExporterConfig,
)

_logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_ERRORS: Final[int] = 10


# =============================================================================
# 경기 오케스트레이터
# =============================================================================
class GameOrchestrator:
    """
    경기 전체 수명주기 오케스트레이터.

    engine/ 내 모든 서브 모듈의 초기화/실행/종료를 통합 관리합니다.
    api_server가 start_game()/stop_game()/pause_game()을 호출합니다.
    """

    __slots__ = (
        "_config",
        "_state_manager",
        # GPU
        "_gpu_manager",
        "_stream_manager",
        "_trt_pool",
        "_batch_accumulator",
        # IO
        "_frame_ingestion",
        # Pipeline
        "_frame_pipeline",
        "_event_pipeline",
        "_possession_pipeline",
        "_period_pipeline",
        "_postgame_pipeline",
        # Orchestration
        "_cadence_scheduler",
        "_referee",
        # Workers
        "_analysis_worker",
        "_export_worker",
        # Detection (코트는 캘리브레이션 대체 — _calibrations에 저장)
        "_ball_detector",
        "_ball_state_machine",
        "_player_detector",
        "_hoop_detector",
        "_calibrations",
        "_det_fusion",
        # Pose
        "_pose_backend_stage1",
        "_pose_backend_stage2",
        # Biomechanics (함수 기반 모듈 참조)
        "_biomech_velocity_mod",
        "_biomech_angle_mod",
        "_biomech_accel_mod",
        # Motion Analysis
        "_shot_detector",
        "_dribble_detector",
        "_pass_detector",
        "_movement_detector",
        "_rebound_detector",
        "_action_classifier",
        "_shot_classifier",
        "_dribble_classifier",
        # Motion Analysis Tier3~5
        "_shot_phase_analyzer",
        "_dribble_phase_analyzer",
        "_shooting_form_evaluator",
        "_dribble_form_evaluator",
        "_form_comparator",
        # Event Detection FRAME 3종
        "_score_detector",
        "_possession_tracker",
        "_dead_ball_detector",
        # Game Management
        "_clock_manager",
        "_foul_manager",
        "_substitution_manager",
        "_timeout_manager",
        "_record_corrector",
        "_format_exporter",
        # IO 출력
        "_result_dispatcher",
        "_progress_reporter",
        # 메인 루프
        "_main_thread",
        "_stop_event",
        "_lock",
        # 최신 프레임 (FRAME cadence 콜백 공유용)
        "_current_aligned",
        "_holder_team_history",
        "_prev_ball_y",
        "_current_frame_result",
        # 분석 데이터 축적 버퍼
        "_analysis_buffer",
        "_court_zones",
        "_attack_direction",
        "_event_converter",
    )

    def __init__(
        self,
        config: EngineConfig | None = None,
        state_manager: EngineGameStateManager | None = None,
    ) -> None:
        self._config = config or EngineConfig()
        self._state_manager = state_manager or EngineGameStateManager()

        # GPU (DI 주입)
        self._gpu_manager: GPUManager | None = None
        self._stream_manager: CUDAStreamManager | None = None
        self._trt_pool: TensorRTPool | None = None
        self._batch_accumulator: BatchAccumulator | None = None

        # IO
        self._frame_ingestion: FrameIngestion | None = None

        # Pipeline
        self._frame_pipeline: FramePipeline | None = None
        self._event_pipeline: EventPipeline | None = None
        self._possession_pipeline: PossessionPipeline | None = None
        self._period_pipeline: PeriodPipeline | None = None
        self._postgame_pipeline: PostgamePipeline | None = None

        # Orchestration
        self._cadence_scheduler: CadenceScheduler | None = None
        self._referee: RefereeOrchestrator | None = None

        # Workers
        self._analysis_worker: AnalysisWorker | None = None
        self._export_worker: ExportWorker | None = None

        # Detection (코트는 캘리브레이션 방식으로 대체)
        self._ball_detector: BallDetector | None = None
        self._ball_state_machine: BallStateMachine = BallStateMachine()
        self._player_detector: PlayerDetector | None = None
        self._hoop_detector: HoopDetector | None = None
        # 카메라별 호모그래피 {cam_id: 3x3 ndarray}
        self._calibrations: dict[str, Any] = {}

        # Pose
        self._pose_backend_stage1: PoseBackend | None = None
        self._pose_backend_stage2: PoseBackend | None = None

        # Biomechanics (모듈 참조)
        self._biomech_velocity_mod = biomech_velocity
        self._biomech_angle_mod = biomech_angle
        self._biomech_accel_mod = biomech_accel

        # Motion Analysis
        self._shot_detector: ShotDetector | None = None
        self._dribble_detector: DribbleDetector | None = None
        self._pass_detector: PassDetector | None = None
        self._movement_detector: MovementDetector | None = None
        self._rebound_detector: ReboundDetector | None = None
        self._action_classifier: ActionClassifier | None = None
        self._shot_classifier: ShotClassifier | None = None
        self._dribble_classifier: DribbleClassifier | None = None
        # Motion Analysis Tier3~5
        self._shot_phase_analyzer: ShotPhaseAnalyzer | None = None
        self._dribble_phase_analyzer: DribblePhaseAnalyzer | None = None
        self._shooting_form_evaluator: ShootingFormEvaluator | None = None
        self._dribble_form_evaluator: DribbleFormEvaluator | None = None
        self._form_comparator: FormComparator | None = None

        # Event Detection FRAME 3종
        self._score_detector: ScoreDetector | None = None
        self._possession_tracker: PossessionTracker | None = None
        self._dead_ball_detector: DeadBallDetector | None = None

        # Game Management
        self._clock_manager: ClockManager | None = None
        self._foul_manager: FoulManager | None = None
        self._substitution_manager: SubstitutionManager | None = None
        self._timeout_manager: TimeoutManager | None = None
        self._record_corrector: RecordCorrector | None = None
        self._format_exporter: OfficialFormatExporter | None = None

        # IO 출력
        self._result_dispatcher: ResultDispatcher | None = None
        self._progress_reporter: ProgressReporter | None = None

        # 메인 루프
        self._main_thread: Thread | None = None
        self._stop_event: Event = Event()
        self._lock: RLock = RLock()
        # 최신 프레임 (FRAME cadence 콜백과 공유)
        self._current_aligned: AlignedFrameSet | None = None
        self._holder_team_history: list[str] = []
        self._prev_ball_y: float = 0.0
        self._current_frame_result: FramePipelineResult | None = None

        # AI 심판용 코트 존 (픽셀 좌표, set_court_zones()로 설정)
        self._court_zones: dict[str, Any] = {
            "half_court_x": 960.0,
            "paint_left": {"x_min": 0.0, "x_max": 350.0, "y_min": 250.0, "y_max": 830.0},
            "paint_right": {"x_min": 1570.0, "x_max": 1920.0, "y_min": 250.0, "y_max": 830.0},
        }
        self._attack_direction: str = "right"
        self._event_converter: Any = None  # EVENT 콜백 등록 시 생성
        self._analysis_buffer: GameAnalysisBuffer = GameAnalysisBuffer()

    # =========================================================================
    # 팩토리: 설정 기반 전체 빌드
    # =========================================================================
    @classmethod
    def build_from_config(
        cls,
        config: EngineConfig | None = None,
    ) -> GameOrchestrator:
        """
        EngineConfig 기반으로 전체 서브 모듈을 생성하고 주입한 오케스트레이터 반환.

        api_server에서 이 메서드를 호출하면 됩니다::

            orchestrator = GameOrchestrator.build_from_config(config)
            orchestrator.start_game(source_urls)

        Args:
            config: 엔진 설정 (None이면 기본값)

        Returns:
            완전히 조립된 GameOrchestrator
        """
        cfg = config or EngineConfig()
        sm = EngineGameStateManager()
        go = cls(config=cfg, state_manager=sm)

        # --- GPU ---
        gpu_mgr = GPUManager(cfg.gpu)
        stream_mgr = CUDAStreamManager(cfg.gpu)
        trt_pool = TensorRTPool(
            config=cfg.gpu,
            pipeline_config=cfg.pipeline,
            gpu_manager=gpu_mgr,
        )
        batch_acc = BatchAccumulator(
            camera_config=cfg.camera,
            gpu_config=cfg.gpu,
        )
        go.inject_gpu(gpu_mgr, stream_mgr, trt_pool, batch_acc)

        # --- IO ---
        ingestion = FrameIngestion(config=cfg.camera)
        go.inject_io(ingestion)

        # --- Pipeline: Fusion ---
        from engine.pipeline.fusion.detection_fusion import DetectionFusion
        from engine.pipeline.fusion.pose_fusion import PoseFusion
        from engine.pipeline.fusion.tracking_fusion import TrackingFusion

        # --- Detection 3종 + 캘리브레이션 ---
        go._ball_detector = BallDetector()
        go._player_detector = PlayerDetector()
        go._hoop_detector = HoopDetector()
        go._ball_state_machine = BallStateMachine()

        # 코트 감지 → 캘리브레이션 방식 (고정 카메라 1회 설정)
        go._calibrations = cls._load_all_calibrations()

        # CV-BBox 통합 모델 존재 여부에 따라 초기화 모드 결정
        # .engine(TRT) 우선 → 없으면 .cv 패키지 폴백
        _bbox_engines = sorted(Path("weights").glob("CV-BBox_v*.engine"), reverse=True)
        _bbox_cv = sorted(Path("weights").glob("CV-BBox_v*.cv"), reverse=True)
        _bbox_files = _bbox_engines or _bbox_cv
        _unified = len(_bbox_files) > 0
        if _unified:
            _logger.info(
                "CV-BBox 통합 모델 감지: %s → 개별 YOLO 로드 생략 (GPU 절약)",
                _bbox_files[0].name,
            )
        # 감지기 초기화 (unified_mode=True면 YOLO 로드 안 함)
        from detection.ball_detection.ball_detector import BallDetectorConfig
        from detection.player_detection.models import PlayerDetectorConfig
        from detection.hoop_detection.hoop_detector import HoopDetectorConfig
        go._ball_detector.initialize(BallDetectorConfig(), unified_mode=_unified)
        go._player_detector.initialize(PlayerDetectorConfig(), unified_mode=_unified)
        go._hoop_detector.initialize(HoopDetectorConfig(), unified_mode=_unified)

        _logger.info(
            "Detection 3종 + BallStateMachine + 캘리브레이션 %d대 로드 완료 (unified=%s)",
            len(go._calibrations), _unified,
        )

        # --- Pose Estimation (각 백엔드 독립 초기화) ---
        from pose_estimation.backends.base_backend import PoseModelType
        try:
            go._pose_backend_stage1 = create_backend(
                PoseModelType.YOLOV8_POSE,
                weights_path=cfg.pipeline.model_yolov8_pose,
            )
        except Exception as exc:
            _logger.warning("Stage1(YOLOv8-Pose) 초기화 실패: %s", exc)

        try:
            go._pose_backend_stage2 = create_backend(
                PoseModelType.VITPOSE,
                weights_path=cfg.pipeline.model_vitpose,
            )
        except Exception as exc:
            _logger.warning("Stage2(ViTPose) 초기화 실패: %s", exc)

        # --- Biomechanics (함수 기반 — 모듈 참조만, 인스턴스 불필요) ---
        _logger.info("Biomechanics kinematics 모듈 참조 완료")

        # --- Motion Analysis ---
        go._shot_detector = ShotDetector()
        go._dribble_detector = DribbleDetector()
        go._pass_detector = PassDetector()
        go._movement_detector = MovementDetector()
        go._rebound_detector = ReboundDetector()
        go._action_classifier = ActionClassifier()
        go._shot_classifier = ShotClassifier()
        go._dribble_classifier = DribbleClassifier()
        # Tier3~5 (동작 분절 → 자세 평가 → 비교)
        go._shot_phase_analyzer = ShotPhaseAnalyzer()
        go._dribble_phase_analyzer = DribblePhaseAnalyzer()
        go._shooting_form_evaluator = ShootingFormEvaluator.from_yaml({})
        go._dribble_form_evaluator = DribbleFormEvaluator.from_yaml({})
        go._form_comparator = FormComparator()
        _logger.info("Motion Analysis 13종 초기화 완료 (Tier1~5)")

        # --- Fusion (CV-BBox 통합 모델 + 감지기 후처리 + 캘리브레이션) ---
        det_fusion = DetectionFusion()
        go._det_fusion = det_fusion  # CLI에서 set_team_colors() 접근용
        # CV-BBox 통합 모델 로드 (최신 버전 자동 탐색)
        if _bbox_files:
            if det_fusion.load_unified_model(str(_bbox_files[0])):
                _logger.info("CV-BBox 통합 모델 사용: %s", _bbox_files[0].name)
            else:
                _logger.warning("CV-BBox 로드 실패, 개별 감지기 폴백 모드")
        else:
            _logger.warning("CV-BBox 미발견, 개별 감지기 폴백 모드")
        # 후처리용 감지기 주입 (트래킹/검증/분류)
        det_fusion.set_detectors(
            ball=go._ball_detector,
            player=go._player_detector,
            hoop=go._hoop_detector,
        )
        det_fusion.set_calibrations(go._calibrations)
        det_fusion.init_team_tracker()
        pose_fusion = PoseFusion()
        tracking_fusion = TrackingFusion()

        # --- MultiViewPlayerTracker (Geometry 기반 선수 영구 ID) ---
        # 튜닝 파라미터는 현재 캘리브 정밀도 기준. 캘리브 향상 시 eps/match 낮추면 됨.
        multiview_tracker = None
        try:
            calib_dir = "C:/COURTVIEW_DESK/configs/calibration"
            multiview_tracker = MultiViewPlayerTracker(
                calib_dir=calib_dir,
                cluster_eps_m=2.5,
                match_max_dist_m=4.0,
                max_miss_frames=30,
                dt=1.0 / 30,
            )
            _logger.info(
                "MultiViewPlayerTracker 로드: cams=%s",
                sorted(multiview_tracker.loader.homographies.keys()),
            )
        except Exception as _mv_exc:
            _logger.warning("MultiViewPlayerTracker 초기화 실패: %s (폴백: 비활성)", _mv_exc)

        # --- Pipeline: 하위 모듈 인스턴스 생성 ---
        detectors, stats_set, realtime_set = cls._build_event_modules()
        possession_analyzers = cls._build_possession_modules()
        period_analyzers = cls._build_period_modules()
        postgame_modules = cls._build_postgame_modules()

        # --- Pipeline: pose_backends 로드된 것만 주입 ---
        pose_backends = [
            b for b in [go._pose_backend_stage1, go._pose_backend_stage2]
            if b is not None
        ]

        frame_pl = FramePipeline(
            detection_fusion=det_fusion,
            pose_fusion=pose_fusion,
            tracking_fusion=tracking_fusion,
            cadence_config=cfg.cadence,
            pose_backends=pose_backends,
            age_group=cfg.age_group,
            gender=cfg.gender,
            multiview_tracker=multiview_tracker,
        )
        event_pl = EventPipeline(
            detectors=detectors,
            stats_set=stats_set,
            realtime_set=realtime_set,
            cadence_config=cfg.cadence,
        )
        possession_pl = PossessionPipeline(
            analyzers=possession_analyzers,
            cadence_config=cfg.cadence,
        )
        period_pl = PeriodPipeline(
            analyzers=period_analyzers,
            cadence_config=cfg.cadence,
        )
        postgame_pl = PostgamePipeline(
            modules=postgame_modules,
            cadence_config=cfg.cadence,
        )
        go.inject_pipelines(frame_pl, event_pl, possession_pl, period_pl, postgame_pl)

        # --- Event Detection FRAME 3종 ---
        go._score_detector = ScoreDetector(ScoreDetectorConfig.from_yaml({}))
        go._possession_tracker = PossessionTracker(PossessionTrackerConfig.from_yaml({}))
        go._dead_ball_detector = DeadBallDetector(DeadBallDetectorConfig.from_yaml({}))
        _logger.info("FRAME 3종 감지기 초기화 완료")

        # --- Game Management ---
        go._clock_manager = ClockManager(ClockManagerConfig.from_yaml({}))
        go._foul_manager = FoulManager(FoulManagerConfig.from_yaml({}))
        go._substitution_manager = SubstitutionManager(SubstitutionManagerConfig.from_yaml({}))
        go._timeout_manager = TimeoutManager(TimeoutManagerConfig.from_yaml({}))
        go._record_corrector = RecordCorrector(RecordCorrectorConfig.from_yaml({}))
        go._format_exporter = OfficialFormatExporter(OfficialFormatExporterConfig.from_yaml({}))
        _logger.info("Game Management 6모듈 초기화 완료")

        # --- Orchestration ---
        scheduler = CadenceScheduler(sm, cfg.cadence)
        referee = RefereeOrchestrator(cfg.referee)
        go.inject_orchestration(scheduler, referee)

        # AI 심판 → event_pipeline 콜백 실제 연동
        def _referee_callback(fi: int, events: list) -> list:
            """referee_orchestrator.evaluate() 실제 위임 + WebSocket 전송."""
            if referee is None:
                return events
            try:
                ctx = go._build_referee_context(fi)
                if fi % 300 == 0:
                    _logger.warning(
                        "⚖️ [심판 진단] frame=%d | live=%s | poss=%s | shot_clk=%.1f | half_x=%.0f | paint=%s",
                        fi, ctx.is_live_ball, ctx.possession_team_id,
                        ctx.shot_clock_sec, ctx.half_court_x,
                        bool(ctx.paint_zone_bounds),
                    )
                referee_result = referee.evaluate(ctx)
                if referee_result.violations_found or referee_result.fouls_found:
                    _logger.info(
                        "⚖️ 심판: violations=%d fouls=%d frame=%d",
                        referee_result.violations_found,
                        referee_result.fouls_found,
                        fi,
                    )
                if referee_result.final_decisions:
                    # WebSocket으로 심판 판정 별도 전송 (UI: referee_decision 타입)
                    if go._result_dispatcher is not None:
                        for decision in referee_result.final_decisions:
                            try:
                                rule_result = getattr(decision, "result", None)
                                call_type_str = ""
                                rule_ref = ""
                                violation_str = ""
                                description = ""
                                if rule_result is not None:
                                    call_type_str = str(getattr(rule_result, "call_type", ""))
                                    rule_ref = getattr(rule_result, "rule_reference", "")
                                    vt = getattr(rule_result, "violation_type", None)
                                    violation_str = str(vt) if vt else ""
                                    description = getattr(rule_result, "description", "")
                                expl = getattr(decision, "explanation", None)
                                expl_text = getattr(expl, "summary", str(expl)) if expl else ""
                                go._result_dispatcher.dispatch_realtime({
                                    "type": "referee_decision",
                                    "frame_index": fi,
                                    "call_type": call_type_str,
                                    "violation_type": violation_str,
                                    "rule_reference": rule_ref,
                                    "description": description,
                                    "confidence": getattr(decision, "final_confidence", 0.0),
                                    "explanation": expl_text,
                                    "requires_review": getattr(decision, "requires_review", False),
                                    "is_final": getattr(decision, "is_final", False),
                                })
                            except Exception:
                                pass
                    return list(referee_result.final_decisions)
            except Exception:
                _logger.debug("심판 평가 오류 frame=%d", fi)
            return events

        event_pl.set_referee_callback(_referee_callback)

        # --- Workers ---
        analysis_wk = AnalysisWorker(
            possession_pipeline=possession_pl,
            period_pipeline=period_pl,
            cadence_config=cfg.cadence,
        )
        export_wk = ExportWorker(pipeline=postgame_pl)
        go.inject_workers(analysis_wk, export_wk)

        # --- Result Dispatcher + Progress Reporter ---
        go._result_dispatcher = ResultDispatcher(cfg.io)
        go._progress_reporter = ProgressReporter(cfg.io)

        _logger.info(
            "GameOrchestrator 빌드 완료: mode=%s, cameras=%d",
            cfg.mode.value, cfg.camera.num_cameras,
        )
        return go

    # =========================================================================
    # DI 주입
    # =========================================================================
    def inject_gpu(
        self,
        gpu_manager: GPUManager,
        stream_manager: CUDAStreamManager,
        trt_pool: TensorRTPool,
        batch_accumulator: BatchAccumulator,
    ) -> None:
        """GPU 서브시스템 주입."""
        self._gpu_manager = gpu_manager
        self._stream_manager = stream_manager
        self._trt_pool = trt_pool
        self._batch_accumulator = batch_accumulator

    def inject_io(self, frame_ingestion: FrameIngestion) -> None:
        """IO 서브시스템 주입."""
        self._frame_ingestion = frame_ingestion

    def inject_pipelines(
        self,
        frame: FramePipeline,
        event: EventPipeline,
        possession: PossessionPipeline,
        period: PeriodPipeline,
        postgame: PostgamePipeline,
    ) -> None:
        """파이프라인 주입."""
        self._frame_pipeline = frame
        self._event_pipeline = event
        self._possession_pipeline = possession
        self._period_pipeline = period
        self._postgame_pipeline = postgame

    def inject_orchestration(
        self,
        scheduler: CadenceScheduler,
        referee: RefereeOrchestrator,
    ) -> None:
        """오케스트레이션 주입."""
        self._cadence_scheduler = scheduler
        self._referee = referee

    def inject_workers(
        self,
        analysis: AnalysisWorker,
        export: ExportWorker,
    ) -> None:
        """워커 주입."""
        self._analysis_worker = analysis
        self._export_worker = export

    # =========================================================================
    # 팀 색상 설정 (CLI → orchestrator → team_classifier)
    # =========================================================================
    @staticmethod
    def _hex_to_hsv(hex_color: str) -> tuple[float, float, float]:
        """
        Hex 색상 → OpenCV HSV 변환.

        Args:
            hex_color: "#FF0000" 또는 "FF0000" 형태

        Returns:
            (H, S, V) — OpenCV 범위: H=0~180, S=0~255, V=0~255
        """
        import cv2 as _cv2
        import numpy as _np
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        pixel = _np.array([[[b, g, r]]], dtype=_np.uint8)
        hsv = _cv2.cvtColor(pixel, _cv2.COLOR_BGR2HSV)
        return float(hsv[0, 0, 0]), float(hsv[0, 0, 1]), float(hsv[0, 0, 2])

    def set_team_colors(
        self,
        team_a: str | tuple[float, float, float],
        team_b: str | tuple[float, float, float],
    ) -> None:
        """
        팀 저지 색상 수동 설정.

        CLI에서 경기 시작 전 호출. Hex 또는 HSV로 양팀 색상을 지정하면
        K-Means 클러스터가 강제 설정되어 팀 분류 정확도 100%.

        Args:
            team_a: 홈팀 색상 — Hex("#1A1A1A") 또는 HSV (85, 80, 65)
            team_b: 원정팀 색상 — Hex("#FFFFFF") 또는 HSV (100, 25, 120)

        사용 예시 (CLI):
            # Hex 방식
            orchestrator.set_team_colors("#1A1A1A", "#FFFFFF")
            # HSV 방식
            orchestrator.set_team_colors((85, 80, 65), (100, 25, 120))
        """
        # Hex → HSV 자동 변환
        if isinstance(team_a, str):
            team_a_hsv = self._hex_to_hsv(team_a)
        else:
            team_a_hsv = team_a

        if isinstance(team_b, str):
            team_b_hsv = self._hex_to_hsv(team_b)
        else:
            team_b_hsv = team_b
        # detection_fusion → team_tracker → team_classifier
        try:
            fusion = getattr(self, "_det_fusion", None)
            if fusion is not None:
                tracker = getattr(fusion, "_team_tracker", None)
                if tracker is not None:
                    tracker.team_classifier.set_team_colors(team_a_hsv, team_b_hsv)
                    _logger.info(
                        "팀 색상 설정: A=HSV%s, B=HSV%s",
                        team_a_hsv, team_b_hsv,
                    )
                    return
            _logger.warning("TeamAwareTracker 미초기화 — 팀 색상 설정 실패")
        except Exception:
            _logger.exception("팀 색상 설정 실패")

    # =========================================================================
    # 교체 처리 (CLI → orchestrator → substitution_manager + player_id_manager)
    # =========================================================================
    def set_court_zones(
        self,
        half_court_x: float,
        paint_left: dict[str, float] | None = None,
        paint_right: dict[str, float] | None = None,
        attack_direction: str = "right",
    ) -> None:
        """AI 심판용 코트 존 좌표 설정 (픽셀 기준)."""
        self._court_zones["half_court_x"] = half_court_x
        if paint_left:
            self._court_zones["paint_left"] = paint_left
        if paint_right:
            self._court_zones["paint_right"] = paint_right
        self._attack_direction = attack_direction
        _logger.info(
            "코트 존 설정: half_x=%.0f, attack=%s",
            half_court_x, attack_direction,
        )


    def process_substitution(
        self,
        team: str,
        out_number: int,
        in_number: int,
    ) -> bool:
        """
        선수 교체 처리.

        기록원이 교체 입력 시 호출. 나간 선수의 트랙을 삭제하고,
        다음 프레임에서 새로 감지되는 미매칭 선수에 들어온 번호를 배정합니다.

        Args:
            team: 팀 ("team_a" 또는 "team_b")
            out_number: 나가는 선수 등번호
            in_number: 들어오는 선수 등번호

        Returns:
            성공 여부

        사용 예시 (CLI):
            orchestrator.process_substitution("team_a", 5, 12)
        """
        try:
            fusion = getattr(self, "_det_fusion", None)
            if fusion is None:
                _logger.warning("detection_fusion 미초기화")
                return False

            tracker = getattr(fusion, "_team_tracker", None)
            if tracker is None:
                _logger.warning("TeamAwareTracker 미초기화")
                return False

            # 나간 선수 트랙 찾기 + 삭제
            # 해당 팀 트래커에서 검색
            from shared.dto.player_dto import Team
            if team == "team_a":
                target_tracker = tracker._tracker_a
            elif team == "team_b":
                target_tracker = tracker._tracker_b
            else:
                _logger.warning("알 수 없는 팀: %s", team)
                return False

            # 교체 정보 저장 (다음 프레임에서 새 감지 시 배정)
            if not hasattr(self, "_pending_substitutions"):
                self._pending_substitutions = []
            self._pending_substitutions.append({
                "team": team,
                "out_number": out_number,
                "in_number": in_number,
            })

            _logger.info(
                "교체 등록: %s #%d OUT → #%d IN",
                team, out_number, in_number,
            )
            return True

        except Exception:
            _logger.exception("교체 처리 실패")
            return False

    def get_pending_substitutions(self) -> list[dict]:
        """대기 중인 교체 목록."""
        return getattr(self, "_pending_substitutions", [])

    def clear_substitution(self, index: int = 0) -> None:
        """처리 완료된 교체 제거."""
        subs = getattr(self, "_pending_substitutions", [])
        if 0 <= index < len(subs):
            removed = subs.pop(index)
            _logger.info("교체 완료: %s", removed)

    # =========================================================================
    # 로스터 설정 (CLI → orchestrator)
    # =========================================================================
    def set_roster(
        self,
        team: str,
        players: list[dict],
    ) -> None:
        """
        팀 로스터 설정.

        경기 시작 전 호출. 선수 목록을 등록하면
        교체 시 자동 번호 배정에 활용됩니다.

        Args:
            team: "team_a" 또는 "team_b"
            players: [{"number": 7, "name": "홍길동"}, ...]

        사용 예시 (CLI):
            orchestrator.set_roster("team_a", [
                {"number": 7, "name": "김선수"},
                {"number": 14, "name": "이선수"},
                ...
            ])
        """
        if not hasattr(self, "_rosters"):
            self._rosters = {}
        self._rosters[team] = players
        _logger.info("로스터 설정: %s %d명", team, len(players))

    def get_roster(self, team: str) -> list[dict]:
        """팀 로스터 조회."""
        return getattr(self, "_rosters", {}).get(team, [])

    # =========================================================================
    # 경기 수명주기
    # =========================================================================
    def start_game(self, source_urls: dict[str, str] | None = None) -> bool:
        """
        경기 시작.

        IDLE → LOADING → (초기화) → RUNNING → 메인 루프 시작.

        Args:
            source_urls: 카메라별 RTSP URL {camera_id: url}

        Returns:
            시작 성공 여부
        """
        sm = self._state_manager

        try:
            # IDLE → LOADING
            sm.transition_engine(EngineState.LOADING)
            _logger.info("경기 시작: LOADING 진입")

            # 초기화
            self._initialize_all(source_urls)

            # 콜백 등록
            self._register_cadence_callbacks()

            # LOADING → RUNNING
            sm.transition_engine(EngineState.RUNNING)

            # game_state → LIVE (BATCH/REPLAY 모드는 즉시 분석 시작)
            with sm._lock:
                sm._context.game_state = GameState.LIVE

            # ClockManager 시작 + LIVE 전환 (시계 동작 시작)
            if self._clock_manager is not None:
                from shared.constants.game_management_constants import (
                    GameState as ClockGameState,
                )
                self._clock_manager.start_game()
                self._clock_manager.transition_to(ClockGameState.LIVE)

            _logger.info("경기 시작: RUNNING + LIVE 진입 (시계 동작)")

            # 메인 루프 시작 (별도 스레드)
            self._stop_event.clear()
            self._main_thread = Thread(
                target=self._main_loop,
                name="cv-main-loop",
                daemon=True,
            )
            self._main_thread.start()

            return True

        except Exception as exc:
            _logger.exception("경기 시작 실패")
            sm.set_error(str(exc))
            return False

    def stop_game(self) -> None:
        """경기 중지. RUNNING/PAUSED → STOPPED."""
        self._stop_event.set()

        if self._main_thread is not None:
            self._main_thread.join(timeout=10.0)
            self._main_thread = None

        # 경기 종료 후 POSTGAME 실행
        if self._postgame_pipeline is not None:
            try:
                _logger.info("POST-GAME 파이프라인 실행")
                self._postgame_pipeline.process()
            except Exception:
                _logger.exception("POST-GAME 실행 오류")

        self._shutdown_all()

        try:
            self._state_manager.transition_engine(EngineState.STOPPED)
        except ValueError:
            pass  # 이미 STOPPED/ERROR

        _logger.info("경기 중지 완료")

    def pause_game(self) -> None:
        """경기 일시정지. RUNNING → PAUSED."""
        self._stop_event.set()
        if self._main_thread is not None:
            self._main_thread.join(timeout=5.0)
            self._main_thread = None

        try:
            self._state_manager.transition_engine(EngineState.PAUSED)
            _logger.info("경기 일시정지")
        except ValueError:
            _logger.warning("일시정지 전이 불가")

    def resume_game(self) -> None:
        """경기 재개. PAUSED → RUNNING."""
        try:
            self._state_manager.transition_engine(EngineState.RUNNING)
        except ValueError:
            _logger.warning("재개 전이 불가")
            return

        self._stop_event.clear()
        self._main_thread = Thread(
            target=self._main_loop,
            name="cv-main-loop",
            daemon=True,
        )
        self._main_thread.start()
        _logger.info("경기 재개")

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================
    def _initialize_all(self, source_urls: dict[str, str] | None = None) -> None:
        """전체 서브 모듈 초기화."""
        # GPU
        if self._gpu_manager is not None:
            self._gpu_manager.initialize()
        if self._stream_manager is not None:
            self._stream_manager.initialize()
        if self._trt_pool is not None:
            self._trt_pool.initialize()
            self._trt_pool.load_all()
            self._trt_pool.warmup_all()

        # IO
        if self._frame_ingestion is not None:
            self._frame_ingestion.initialize(source_urls)
            # 단일 카메라 테스트 지원: 연결 카메라 수에 맞춰 aligner 최소 카메라 조정
            if self._frame_ingestion._aligner is not None and source_urls:
                n_cams = len(source_urls)
                self._frame_ingestion._aligner._config.min_cameras_required = max(1, n_cams)
                _logger.info("Aligner min_cameras=%d (연결 카메라 %d대)", n_cams, n_cams)

        # Pose Backends 모델 로드
        for backend in (self._pose_backend_stage1, self._pose_backend_stage2):
            if backend is not None:
                try:
                    backend.load_model()
                    _logger.info(
                        "포즈 백엔드 로드 완료: %s (format=%s)",
                        backend.model_type.value,
                        backend.get_keypoint_format(),
                    )
                except Exception:
                    _logger.warning(
                        "포즈 백엔드 로드 실패: %s — 해당 스테이지 비활성",
                        type(backend).__name__,
                    )

        # AI 심판
        if self._referee is not None:
            self._referee.initialize()

        # Workers
        if self._analysis_worker is not None:
            self._analysis_worker.initialize()
        if self._export_worker is not None:
            self._export_worker.initialize()

        _logger.info("전체 서브 모듈 초기화 완료")

    def _shutdown_all(self) -> None:
        """전체 서브 모듈 종료."""
        # Workers 먼저
        if self._analysis_worker is not None:
            self._analysis_worker.shutdown()
        if self._export_worker is not None:
            self._export_worker.shutdown()

        # AI 심판
        if self._referee is not None:
            self._referee.shutdown()

        # Pose Backends 언로드
        for backend in (self._pose_backend_stage1, self._pose_backend_stage2):
            if backend is not None and backend.is_loaded:
                try:
                    backend.unload_model()
                except Exception:
                    pass

        # IO
        if self._frame_ingestion is not None:
            self._frame_ingestion.shutdown()

        # GPU (마지막)
        if self._trt_pool is not None:
            self._trt_pool.shutdown()
        if self._stream_manager is not None:
            self._stream_manager.shutdown()
        if self._gpu_manager is not None:
            self._gpu_manager.shutdown()

        _logger.info("전체 서브 모듈 종료 완료")

    # =========================================================================
    # Cadence 콜백 등록
    # =========================================================================
    def _register_cadence_callbacks(self) -> None:
        """5등급 Cadence 콜백 등록."""
        if self._cadence_scheduler is None:
            return

        cs = self._cadence_scheduler

        # 🔴 FRAME
        if self._frame_pipeline is not None:
            fp = self._frame_pipeline

            def _frame_cb(_cadence: object, _keys: object) -> None:
                """프레임 파이프라인 → buffer 축적 → motion 감지 → FRAME 3종 → 트리거."""
                aligned = self._current_aligned
                if aligned is None or not aligned.frames:
                    return
                frames_dict = {
                    cam_id: fd.image
                    for cam_id, fd in aligned.frames.items()
                }
                fi = aligned.frame_index
                ts = aligned.reference_timestamp
                sm = self._state_manager
                buf = self._analysis_buffer

                # 1. 프레임 파이프라인 실행 → 결과 저장
                result = fp.process_frame(
                    frames=frames_dict, frame_index=fi, timestamp=ts,
                )
                self._current_frame_result = result

                # 2. 분석 버퍼 축적 (MotionSnapshot 포함)
                buf.ingest_frame(result)

                # 3. motion_analysis Tier1 감지 + Tier2 분류 (5프레임 주기 — 성능 최적화)
                if fi % 5 == 0:
                    self._run_motion_analysis()

                # 4. BallStateMachine 상태 분류 (cross-detector)
                if self._ball_state_machine is not None and result.detection:
                    try:
                        self._update_ball_state(result, fi)
                        # converter에 공 상태 동기화
                        if hasattr(self, "_event_converter") and self._event_converter is not None:
                            bsm = self._ball_state_machine
                            self._event_converter.update_ball_state(
                                state_name=bsm.current_state.name,
                                holder_id=bsm.holder_id,
                            )
                    except Exception:
                        _logger.debug("BallStateMachine 갱신 오류")

                # 5. game_management: ClockManager tick → state_manager 동기화
                if self._clock_manager is not None:
                    try:
                        clock_state = self._clock_manager.tick()
                        sm.update_clock(
                            quarter=clock_state.quarter,
                            game_clock_sec=clock_state.game_clock_seconds,
                            shot_clock_sec=clock_state.shot_clock_seconds,
                        )
                        # MultiViewPlayerTracker 게임 상태 동기화 (교체/쿼터 대응)
                        mv = getattr(self._frame_pipeline, "_multiview_tracker", None)
                        if mv is not None:
                            cs_name = getattr(clock_state.state, "name", str(clock_state.state))
                            if cs_name == "LIVE":
                                mv.set_game_state(MVGameState.ACTIVE)
                            elif cs_name in ("DEAD_BALL", "TIMEOUT", "PERIOD_BREAK", "HALFTIME"):
                                mv.set_game_state(MVGameState.PAUSED)
                            elif cs_name == "FINAL":
                                # 경기 종료 → 모든 트랙/영구ID 초기화
                                mv.reset()
                    except Exception as _cm_err:
                        _logger.debug("ClockManager tick 또는 tracker 동기화 오류: %s", _cm_err)

                # 6. FRAME 3종 감지기 → 트리거 세팅
                if self._score_detector is not None:
                    try:
                        score_input = self._build_score_input(result, fi, ts)
                        evt = self._score_detector.process_frame(score_input)
                        if evt is not None:
                            sm.set_trigger(pending_shooting=True)
                            _logger.warning(
                                "🏀 득점 감지: frame=%d conf=%.2f",
                                fi, getattr(evt, "confidence", 0.0),
                            )
                            # converter에 슛 시도 알림 (리바운드/어시스트 역추적용)
                            if self._event_converter is not None:
                                poss_input = self._build_possession_input(result, fi, ts)
                                self._event_converter.notify_shot_attempt(
                                    frame_index=fi,
                                    shooter_id=poss_input.ball_holder_tracking_id,
                                    team_id=poss_input.ball_holder_team_id or "",
                                )
                            if self._result_dispatcher is not None:
                                self._result_dispatcher.dispatch_realtime({
                                    "type": "event",
                                    "event_type": "score",
                                    "frame_index": fi,
                                    "confidence": getattr(evt, "confidence", 0.0),
                                    "points": getattr(evt, "points", 2),
                                })
                    except Exception:
                        _logger.debug("ScoreDetector 오류")

                if self._possession_tracker is not None and fi > 100:
                    try:
                        poss_input = self._build_possession_input(result, fi, ts)
                        if fi % 50 == 0:
                            _logger.warning(
                                "[POSS F#%d] controlled=%s team='%s' holder=%s",
                                fi, poss_input.ball_is_controlled,
                                poss_input.ball_holder_team_id,
                                poss_input.ball_holder_tracking_id,
                            )
                        evt = self._possession_tracker.process_frame(poss_input)
                        if evt is not None:
                            sm.set_trigger(pending_possession_end=True)
                            _logger.warning(
                                "🔄 점유 전환: frame=%d conf=%.2f", fi,
                                getattr(evt, "confidence", 0.0),
                            )
                            # 샷클락 24초 리셋 (점유 전환 시)
                            if self._clock_manager is not None:
                                self._clock_manager.reset_shot_clock_full()
                            # 공격 방향 전환
                            if self._attack_direction == "right":
                                self._attack_direction = "left"
                            else:
                                self._attack_direction = "right"  
                            # ResultDispatcher로 전송
                            if self._result_dispatcher is not None:
                                self._result_dispatcher.dispatch_realtime({
                                    "type": "event",
                                    "event_type": "possession_change",
                                    "frame_index": fi,
                                    "confidence": getattr(evt, "confidence", 0.0),
                                    "team_id": poss_input.ball_holder_team_id,
                                })
                    except Exception:
                        _logger.exception("PossessionTracker 오류")

                if self._dead_ball_detector is not None:
                    try:
                        evt = self._dead_ball_detector.process_frame(
                            self._build_dead_ball_input(result, fi, ts),
                        )
                        if evt is not None:
                            sm.set_trigger(pending_foul_contact=True)
                            _logger.warning("⏸ 데드볼 감지: frame=%d", fi)
                            if self._result_dispatcher is not None:
                                self._result_dispatcher.dispatch_realtime({
                                    "type": "event",
                                    "event_type": "dead_ball",
                                    "frame_index": fi,
                                })
                    except Exception:
                        _logger.debug("DeadBallDetector 오류")

                # 6. ProgressReporter 갱신
                if self._progress_reporter is not None:
                    try:
                        self._progress_reporter.update_frame(fi)
                    except Exception:
                        pass

                # 7. ResultDispatcher 실시간 전송 (WebSocket → UI)
                if self._result_dispatcher is not None:
                    try:
                        self._result_dispatcher.dispatch_realtime({
                            "type": "frame",
                            "frame_index": fi,
                            "timestamp": ts,
                            "total_objects": result.total_objects,
                            "total_persons_3d": result.total_persons_3d,
                            "active_tracks": result.active_tracks,
                            "processing_time_ms": round(
                                result.processing_time_ms, 1,
                            ),
                            "stage_times_ms": result.stage_times_ms,
                        })
                    except Exception:
                        pass

            cs.register(CadenceLevel.FRAME, _frame_cb)

        # 🟠 EVENT
        if self._event_pipeline is not None:
            ep = self._event_pipeline

            # FramePipelineResult → EventFrameData 변환기 (상태 관리 — 인스턴스 유지)
            from engine.pipeline.frame_to_event_converter import FrameToEventConverter
            self._event_converter = FrameToEventConverter()

            def _event_cb(_cadence: object, trigger_keys: frozenset) -> None:
                """이벤트 감지 → Stage2 ViTPose → buffer → game_management → 전송."""
                # 변환기로 frame_result → event_data 변환
                event_data = self._event_converter.convert(
                    self._current_frame_result,
                    game_context=self._state_manager.game_context,
                )
                event_result = ep.process_events(
                    frame_index=self._state_manager.game_context.frame_number,
                    trigger_keys=trigger_keys,
                    frame_data=event_data,
                )
                if event_result is None or not event_result.detected_events:
                    # 이벤트 미감지 상태 10프레임마다 로그
                    fn = self._state_manager.game_context.frame_number
                    if fn % 50 == 0:
                        _logger.warning(
                            "EVENT 콜백 실행 (F#%d) — 감지 0건 | triggers=%s | data=%s",
                            fn, trigger_keys,
                            f"objects={getattr(event_data, 'total_objects', '?')}" if event_data else "None",
                        )
                    return

                _logger.info(
                    "🟠 EVENT 감지: %d건 (triggers=%s)",
                    len(event_result.detected_events),
                    trigger_keys,
                )

                # Stage2 ViTPose 정밀 분석 (트리거 조건 매칭 시)
                self._try_stage2_vitpose(event_result.detected_events)

                # buffer 축적
                self._analysis_buffer.ingest_events(
                    event_result.detected_events,
                )
                # game_management 이벤트 기반 갱신
                self._update_game_management(event_result.detected_events)

                # ResultDispatcher 이벤트 실시간 전송
                if self._result_dispatcher is not None:
                    for det_evt in event_result.detected_events:
                        try:
                            self._result_dispatcher.dispatch_realtime({
                                "type": "event",
                                "event_type": getattr(det_evt, "event_type", ""),
                                "frame_index": getattr(det_evt, "frame_index", 0),
                                "confidence": getattr(det_evt, "confidence", 0.0),
                                "player_id": getattr(det_evt, "player_id", None),
                                "team_id": getattr(det_evt, "team_id", None),
                            })
                        except Exception:
                            pass

            cs.register(CadenceLevel.EVENT, _event_cb)

        # 🟡 POSSESSION — buffer에서 축적 데이터 빌드하여 전달
        if self._analysis_worker is not None and self._possession_pipeline is not None:
            aw = self._analysis_worker

            def _possession_cb(_cadence: object, _keys: object) -> None:
                poss_id = self._state_manager.game_context.possession_count
                poss_data = self._analysis_buffer.build_possession_data(poss_id)
                aw.submit_possession(poss_id, data=poss_data)
                self._analysis_buffer.flush_possession()

            cs.register(CadenceLevel.POSSESSION, _possession_cb)

        # 🟢 PERIOD — buffer에서 쿼터 축적 데이터 빌드
        if self._analysis_worker is not None and self._period_pipeline is not None:
            aw = self._analysis_worker

            def _period_cb(_cadence: object, _keys: object) -> None:
                quarter = self._state_manager.game_context.quarter
                period_data = self._analysis_buffer.build_period_data(quarter)
                aw.submit_period(quarter, data=period_data)
                self._analysis_buffer.flush_period()

            cs.register(CadenceLevel.PERIOD, _period_cb)

        # 🔵 POSTGAME — 전체 경기 축적 데이터 빌드
        if self._export_worker is not None and self._postgame_pipeline is not None:
            ew = self._export_worker

            def _postgame_cb(_cadence: object, _keys: object) -> None:
                game_data = self._analysis_buffer.build_game_data()

                # POSTGAME pipeline 실행 (동기 — 추출 결과 즉시 필요)
                postgame_result = None
                if self._postgame_pipeline is not None:
                    try:
                        postgame_result = self._postgame_pipeline.process(game_data)
                    except Exception:
                        _logger.exception("POSTGAME 파이프라인 오류")

                # ExportWorker에도 전달 (비동기 후처리)
                ew.submit(game_data=game_data)

                # OfficialFormatExporter: 공식 기록지 생성
                if self._format_exporter is not None:
                    try:
                        ctx = self._state_manager.game_context
                        self._format_exporter.build_box_score(
                            game_id=str(ctx.frame_number),
                            date="",
                            venue="",
                            home_team="HOME",
                            away_team="AWAY",
                            quarter=ctx.quarter,
                            home_score=ctx.home_score,
                            away_score=ctx.away_score,
                        )
                    except Exception:
                        _logger.debug("OfficialFormatExporter 생성 오류")

                # FRAME 레벨 추출 데이터 수집
                frame_extraction = self._analysis_buffer.get_frame_extractions()

                # ResultDispatcher: 학습 데이터 + 경기 결과 Cloud 전송
                if self._result_dispatcher is not None:
                    # 13종 extractor 결과 (POSTGAME)
                    training_payload: dict = {}
                    if postgame_result is not None:
                        training_payload.update(
                            postgame_result.extracted_training_data,
                        )
                    # FRAME 레벨 추출 데이터 병합
                    if frame_extraction:
                        training_payload["frame_level"] = frame_extraction

                    try:
                        self._result_dispatcher.dispatch_postgame({
                            "type": "training_data",
                            "status": "completed",
                            "data": training_payload,
                        })
                    except Exception:
                        _logger.debug("학습 데이터 전송 오류")

            cs.register(CadenceLevel.POSTGAME, _postgame_cb)

        _logger.info("Cadence 콜백 등록 완료")

    # =========================================================================
    # 메인 루프
    # =========================================================================
    def _main_loop(self) -> None:
        """
        메인 분석 루프 (daemon 스레드).

        매 프레임:
          1. frame_ingestion.capture_and_align()
          2. batch_accumulator.add_synchronized_frames()
          3. cadence_scheduler.tick()
          4. game_state 갱신
        """
        _logger.info("메인 루프 시작")
        consecutive_errors = 0
        frame_index = 0

        while not self._stop_event.is_set():
            t0 = time.perf_counter()

            try:
                # 1. 프레임 수집 + 동기화
                if self._frame_ingestion is not None:
                    aligned = self._frame_ingestion.capture_and_align()
                    if aligned is not None:
                        # 최신 정렬 프레임 저장 → FRAME cadence 콜백에서 사용
                        self._current_aligned = aligned
                        # BatchAccumulator에 등록
                        if self._batch_accumulator is not None:
                            from engine.gpu.batch_accumulator import FrameMeta
                            frames_list = [
                                fd.image for fd in aligned.frames.values()
                            ]
                            metas_list = [
                                FrameMeta(
                                    camera_id=cam_id,
                                    frame_number=aligned.frame_index,
                                    timestamp=aligned.reference_timestamp,
                                    width=fd.image.shape[1] if fd.image.ndim >= 2 else 0,
                                    height=fd.image.shape[0] if fd.image.ndim >= 2 else 0,
                                )
                                for cam_id, fd in aligned.frames.items()
                            ]
                            self._batch_accumulator.add_synchronized_frames(
                                frames_list, metas_list,
                            )

                # 2. 프레임 카운터 갱신
                frame_index += 1
                self._state_manager.update_frame(frame_index, time.monotonic())

                # 3. Cadence 스케줄링
                if self._cadence_scheduler is not None:
                    self._cadence_scheduler.tick(frame_index=frame_index)

                # 4. 발열 점검 (100프레임마다)
                if frame_index % 100 == 0 and self._gpu_manager is not None:
                    self._gpu_manager.check_thermal()

                consecutive_errors = 0

            except Exception:
                consecutive_errors += 1
                _logger.exception("메인 루프 오류 (연속 %d회)", consecutive_errors)

                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    _logger.critical(
                        "연속 오류 %d회 초과 → ERROR 전이", _MAX_CONSECUTIVE_ERRORS,
                    )
                    self._state_manager.set_error(
                        f"메인 루프 연속 오류 {consecutive_errors}회",
                    )
                    break

            # FPS 제어 (LIVE 모드)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            budget_ms = self._config.cadence.frame_budget_ms
            if elapsed_ms < budget_ms:
                sleep_sec = (budget_ms - elapsed_ms) / 1000.0
                self._stop_event.wait(timeout=sleep_sec)

        _logger.info("메인 루프 종료 (frame=%d)", frame_index)

    # =========================================================================
    # 조회
    # =========================================================================
    @property
    def state_manager(self) -> EngineGameStateManager:
        return self._state_manager

    @property
    def is_running(self) -> bool:
        return self._state_manager.is_running

    @property
    def gpu_manager(self) -> GPUManager | None:
        """GPU 리소스 관리자 (외부 메트릭 조회용)."""
        return self._gpu_manager

    @property
    def trt_pool(self) -> TensorRTPool | None:
        """TensorRT 엔진 풀 (외부 모델 상태 조회용)."""
        return self._trt_pool

    @property
    def batch_accumulator(self) -> BatchAccumulator | None:
        """배치 누적기 (외부 추론 카운터 조회용)."""
        return self._batch_accumulator

    @property
    def result_dispatcher(self) -> ResultDispatcher | None:
        """결과 분배기 (외부 큐 상태 조회용)."""
        return self._result_dispatcher

    @property
    def progress_reporter(self) -> ProgressReporter | None:
        """진행률 보고기 (외부 진행률 조회용)."""
        return self._progress_reporter

    @property
    def referee(self) -> RefereeOrchestrator | None:
        """AI 심판 오케스트레이터 (외부 판정 이벤트 조회용)."""
        return self._referee

    @property
    def event_pipeline(self) -> EventPipeline | None:
        """EVENT cadence 파이프라인 (facade 통계 조회용, Phase 15 H4)."""
        return self._event_pipeline

    @property
    def possession_pipeline(self) -> PossessionPipeline | None:
        """POSSESSION cadence 파이프라인 (facade 하이라이트/전술 조회용, Phase 15 H4)."""
        return self._possession_pipeline

    def __repr__(self) -> str:
        return (
            f"GameOrchestrator("
            f"state={self._state_manager.engine_state.value}, "
            f"mode={self._config.mode.value})"
        )

    # =========================================================================
    # 하위 모듈 인스턴스 빌더 (안전 임포트 — 실패 시 None)
    # =========================================================================
    @staticmethod
    def _safe_create(module_path: str, class_name: str, **kwargs: object) -> object | None:
        """모듈에서 클래스를 임포트하고 인스턴스 생성. 실패 시 None."""
        try:
            import importlib
            mod = importlib.import_module(module_path)
            cls_obj = getattr(mod, class_name)
            return cls_obj(**kwargs) if kwargs else cls_obj()
        except Exception:
            _logger.debug("모듈 생성 스킵: %s.%s", module_path, class_name)
            return None

    @staticmethod
    def _load_all_calibrations() -> dict[str, Any]:
        """
        configs/calibration/ 에서 모든 카메라 캘리브레이션 JSON 로드.

        Returns:
            {camera_id: 3x3 호모그래피 ndarray}
        """
        import json as _json
        from pathlib import Path as _Path
        import numpy as _np

        cal_dir = _Path("configs/calibration")
        calibrations: dict[str, Any] = {}
        if not cal_dir.exists():
            _logger.warning("캘리브레이션 디렉토리 없음: %s", cal_dir)
            return calibrations

        for cal_file in cal_dir.glob("cam_*.json"):
            try:
                with open(cal_file, "r", encoding="utf-8") as f:
                    data = _json.load(f)
                cam_id = data.get("camera_id", cal_file.stem.replace("cam_", ""))
                H = _np.array(data["homography"], dtype=_np.float64)
                if H.shape == (3, 3):
                    calibrations[cam_id] = H
                    _logger.info("캘리브레이션 로드: %s (quality=%.2f)", cam_id, data.get("quality_score", 0))
            except Exception:
                _logger.exception("캘리브레이션 로드 실패: %s", cal_file)

        return calibrations

    @classmethod
    def _build_event_modules(cls) -> tuple[EventDetectorSet, EventStatsSet, EventRealtimeSet]:
        """EVENT 파이프라인 하위 모듈 전체 인스턴스 생성."""
        sc = cls._safe_create

        detectors = EventDetectorSet(
            # EVENT cadence 6종
            shot_event=sc("game_analysis.game_state.event_detection.shot_event_detector", "ShotEventDetector"),
            rebound=sc("game_analysis.game_state.event_detection.rebound_detector", "ReboundDetector"),
            foul=sc("game_analysis.game_state.event_detection.foul_detector", "FoulDetector"),
            screen=sc("game_analysis.game_state.event_detection.screen_detector", "ScreenDetector"),
            fast_break=sc("game_analysis.game_state.event_detection.fast_break_detector", "FastBreakDetector"),
            drive=sc("game_analysis.game_state.event_detection.drive_detector", "DriveDetector"),
            # 역추적 4종
            assist=sc("game_analysis.game_state.event_detection.assist_detector", "AssistDetector"),
            block=sc("game_analysis.game_state.event_detection.block_detector", "BlockDetector"),
            steal=sc("game_analysis.game_state.event_detection.steal_detector", "StealDetector"),
            turnover=sc("game_analysis.game_state.event_detection.turnover_detector", "TurnoverDetector"),
            # SPECIAL 3종
            free_throw=sc("game_analysis.game_state.event_detection.free_throw_detector", "FreeThrowDetector"),
            box_out=sc("game_analysis.game_state.event_detection.box_out_detector", "BoxOutDetector"),
            jump_ball=sc("game_analysis.game_state.event_detection.jump_ball_detector", "JumpBallDetector"),
            # 통계 기본
            basic_stats=sc("game_analysis.stats.statistics.basic_stats", "BasicStatsCalculator"),
        )

        stats_set = EventStatsSet(
            advanced_stats=sc("game_analysis.stats.statistics.advanced_stats", "AdvancedStatsCalculator"),
            shot_chart=sc("game_analysis.stats.statistics.shot_chart", "ShotChartCalculator"),
            player_tracker=sc("game_analysis.stats.statistics.player_tracker_stats", "PlayerTrackerStatsCalculator"),
            team_stats=sc("game_analysis.stats.statistics.team_stats_aggregator", "TeamStatsAggregator"),
            possession_stats=sc("game_analysis.stats.statistics.possession_stats", "PossessionStatsCalculator"),
            four_factors=sc("game_analysis.stats.statistics.four_factors", "FourFactorsCalculator"),
            win_probability=sc("game_analysis.stats.predictive_models.win_probability", "WinProbabilityModel"),
            epv=sc("game_analysis.stats.predictive_models.expected_possession_value", "EPVModel"),
            shot_quality=sc("game_analysis.stats.predictive_models.shot_quality_model", "ShotQualityModel"),
            lineup_projection=sc("game_analysis.stats.predictive_models.lineup_projection", "LineupProjectionModel"),
            game_sheet=sc("game_analysis.output.game_record.game_sheet_generator", "GameSheetGenerator"),
            play_by_play=sc("game_analysis.output.game_record.play_by_play", "PlayByPlayTracker"),
            quarter_summary=sc("game_analysis.output.game_record.quarter_summary", "QuarterSummaryGenerator"),
            shot_zone_mapper=sc("game_analysis.output.shot_location.shot_zone_mapper", "ShotZoneMapper"),
            shot_heatmap=sc("game_analysis.output.shot_location.shot_heatmap", "ShotHeatmapCalculator"),
            efficiency_by_zone=sc("game_analysis.output.shot_location.efficiency_by_zone", "EfficiencyByZoneCalculator"),
        )

        realtime_set = EventRealtimeSet(
            realtime_advisor=sc("game_analysis.output.coaching_intelligence.realtime_advisor", "RealtimeAdvisor"),
            substitution_optimizer=sc("game_analysis.output.coaching_intelligence.substitution_optimizer", "SubstitutionOptimizer"),
            endgame_strategist=sc("game_analysis.output.coaching_intelligence.endgame_strategist", "EndgameStrategist"),
            live_validator=sc("game_analysis.game_state.live_workspace.live_event_validator", "LiveEventValidator"),
            correction_sync=sc("game_analysis.game_state.live_workspace.correction_sync", "CorrectionSync"),
            action_classifier=sc("motion_analysis.classification.action_classifier", "ActionClassifier"),
        )

        return detectors, stats_set, realtime_set

    @classmethod
    def _build_possession_modules(cls) -> PossessionAnalyzerSet:
        """POSSESSION 파이프라인 43종 분석기 인스턴스 생성."""
        sc = cls._safe_create
        return PossessionAnalyzerSet(
            # 전술 6종
            screen_analyzer=sc("game_analysis.analysis.team.tactical_analysis.screen_analyzer", "ScreenAnalyzer"),
            fast_break_analyzer=sc("game_analysis.analysis.team.tactical_analysis.fast_break_analyzer", "FastBreakAnalyzer"),
            set_play_recognizer=sc("game_analysis.analysis.team.tactical_analysis.set_play_recognizer", "SetPlayRecognizer"),
            passing_network=sc("game_analysis.analysis.team.tactical_analysis.passing_network", "PassingNetworkAnalyzer"),
            possession_analyzer=sc("game_analysis.analysis.team.tactical_analysis.possession_analyzer", "PossessionAnalyzer"),
            turnover_analyzer=sc("game_analysis.analysis.team.tactical_analysis.turnover_analyzer", "TurnoverAnalyzer"),
            # 개인 6종
            drive_analyzer=sc("game_analysis.analysis.player.individual_analysis.drive_analyzer", "DriveAnalyzer"),
            off_ball=sc("game_analysis.analysis.player.individual_analysis.off_ball_movement", "OffBallMovementAnalyzer"),
            clutch=sc("game_analysis.analysis.player.individual_analysis.clutch_performance", "ClutchPerformanceAnalyzer"),
            fatigue=sc("game_analysis.analysis.player.individual_analysis.fatigue_analyzer", "FatigueAnalyzer"),
            player_impact=sc("game_analysis.analysis.player.individual_analysis.player_impact", "PlayerImpactAnalyzer"),
            rebound_analyzer=sc("game_analysis.analysis.player.individual_analysis.rebound_analysis", "ReboundAnalyzer"),
            # 하이라이트 3종
            highlight_detector=sc("game_analysis.output.highlight.highlight_detector", "HighlightDetector"),
            excitement_scorer=sc("game_analysis.output.highlight.excitement_scorer", "ExcitementScorer"),
            clip_extractor=sc("game_analysis.output.highlight.clip_extractor", "ClipExtractor"),
            # 공간 4종
            floor_spacing=sc("game_analysis.analysis.context.spatial_analysis.floor_spacing", "FloorSpacingAnalyzer"),
            movement_heatmap=sc("game_analysis.analysis.context.spatial_analysis.movement_heatmap", "MovementHeatmapAnalyzer"),
            zone_control=sc("game_analysis.analysis.context.spatial_analysis.zone_control", "ZoneControlAnalyzer"),
            paint_analyzer=sc("game_analysis.analysis.context.spatial_analysis.paint_analysis", "PaintAnalyzer"),
            # 수비 5종
            defense_type=sc("game_analysis.analysis.team.defensive_analysis.defense_type_classifier", "DefenseTypeClassifier"),
            defensive_rotation=sc("game_analysis.analysis.team.defensive_analysis.defensive_rotation", "DefensiveRotationAnalyzer"),
            box_out_analyzer=sc("game_analysis.analysis.team.defensive_analysis.box_out_analyzer", "BoxOutAnalyzer"),
            closeout=sc("game_analysis.analysis.team.defensive_analysis.closeout_analyzer", "CloseoutAnalyzer"),
            help_recovery=sc("game_analysis.analysis.team.defensive_analysis.help_recovery", "HelpRecoveryAnalyzer"),
            # 전환 3종
            transition_offense=sc("game_analysis.analysis.team.transition_analysis.transition_offense", "TransitionOffenseAnalyzer"),
            transition_defense=sc("game_analysis.analysis.team.transition_analysis.transition_defense", "TransitionDefenseAnalyzer"),
            transition_efficiency=sc("game_analysis.analysis.team.transition_analysis.transition_efficiency", "TransitionEfficiencyAnalyzer"),
            # 플레이유형 6종
            pick_and_roll=sc("game_analysis.analysis.team.play_type_analysis.pick_and_roll", "PickAndRollAnalyzer"),
            isolation=sc("game_analysis.analysis.team.play_type_analysis.isolation_analyzer", "IsolationAnalyzer"),
            post_up=sc("game_analysis.analysis.team.play_type_analysis.post_up_analyzer", "PostUpAnalyzer"),
            spot_up=sc("game_analysis.analysis.team.play_type_analysis.spot_up_analyzer", "SpotUpAnalyzer"),
            play_type_ft=sc("game_analysis.analysis.team.play_type_analysis.free_throw_analyzer", "FreeThrowAnalyzer"),
            play_type_efficiency=sc("game_analysis.analysis.team.play_type_analysis.play_type_efficiency", "PlayTypeEfficiencyAnalyzer"),
            # 라인업 3종
            lineup_tracker=sc("game_analysis.analysis.player.lineup_analysis.lineup_tracker", "LineupTracker"),
            lineup_efficiency=sc("game_analysis.analysis.player.lineup_analysis.lineup_efficiency", "LineupEfficiencyAnalyzer"),
            player_synergy=sc("game_analysis.analysis.player.lineup_analysis.player_synergy", "PlayerSynergyAnalyzer"),
            # 매치업 3종
            matchup_tracker=sc("game_analysis.output.matchup_analysis.matchup_tracker", "MatchupTracker"),
            contest_analyzer=sc("game_analysis.output.matchup_analysis.contest_analyzer", "ContestAnalyzer"),
            matchup_evaluator=sc("game_analysis.output.matchup_analysis.matchup_evaluator", "MatchupEvaluator"),
            # 특수상황 4종
            ato_play=sc("game_analysis.analysis.context.special_situation.ato_play_analyzer", "ATOPlayAnalyzer"),
            oob_play=sc("game_analysis.analysis.context.special_situation.oob_play_analyzer", "OOBPlayAnalyzer"),
            foul_game=sc("game_analysis.analysis.context.special_situation.foul_game_analyzer", "FoulGameAnalyzer"),
            last_possession=sc("game_analysis.analysis.context.special_situation.last_possession", "LastPossessionAnalyzer"),
        )

    @classmethod
    def _build_period_modules(cls) -> PeriodAnalyzerSet:
        """PERIOD 파이프라인 16종 분석기 인스턴스 생성."""
        sc = cls._safe_create
        return PeriodAnalyzerSet(
            # 경기 흐름 4종
            momentum=sc("game_analysis.analysis.context.game_flow.momentum_tracker", "MomentumTracker"),
            tempo=sc("game_analysis.analysis.context.game_flow.tempo_analyzer", "TempoAnalyzer"),
            timeout_effectiveness=sc("game_analysis.analysis.context.game_flow.timeout_effectiveness", "TimeoutEffectivenessAnalyzer"),
            lead_management=sc("game_analysis.analysis.context.game_flow.lead_management", "LeadManagementAnalyzer"),
            # 로테이션 4종
            rotation_tracker=sc("game_analysis.analysis.player.rotation_analysis.rotation_tracker", "RotationTracker"),
            stagger=sc("game_analysis.analysis.player.rotation_analysis.stagger_analyzer", "StaggerAnalyzer"),
            bench_unit=sc("game_analysis.analysis.player.rotation_analysis.bench_unit_analyzer", "BenchUnitAnalyzer"),
            rest_period=sc("game_analysis.analysis.player.rotation_analysis.rest_period_analyzer", "RestPeriodAnalyzer"),
            # 쿼터 요약
            quarter_summary=sc("game_analysis.output.game_record.quarter_summary", "QuarterSummaryGenerator"),
            # 시즌 3종
            season_aggregator=sc("game_analysis.analysis.context.season_analysis.season_aggregator", "SeasonAggregator"),
            trend_tracker=sc("game_analysis.analysis.context.season_analysis.trend_tracker", "TrendTracker"),
            benchmark=sc("game_analysis.analysis.context.season_analysis.benchmark_comparator", "BenchmarkComparator"),
            # 상황 스플릿 4종
            period_splits=sc("game_analysis.analysis.context.situation_splits.period_splits", "PeriodSplitsAnalyzer"),
            score_margin_splits=sc("game_analysis.analysis.context.situation_splits.score_margin_splits", "ScoreMarginSplitsAnalyzer"),
            shot_clock_splits=sc("game_analysis.analysis.context.situation_splits.shot_clock_splits", "ShotClockSplitsAnalyzer"),
            game_context_analyzer=sc("game_analysis.analysis.context.situation_splits.game_context_analyzer", "GameContextAnalyzer"),
        )

    @classmethod
    def _build_postgame_modules(cls) -> PostgameModuleSet:
        """POSTGAME 파이프라인 35종 모듈 인스턴스 생성."""
        sc = cls._safe_create
        return PostgameModuleSet(
            # 리포트 3종
            game_report_builder=sc("game_analysis.output.game_record.game_report_builder", "GameReportBuilder"),
            game_report_generator=sc("feedback_system.report.game_report_generator", "GameReportGenerator"),
            coach_report_generator=sc("feedback_system.report.coach_report_generator", "CoachReportGenerator"),
            # GA 데이터 추출 7종
            frame_extractor=sc("game_analysis.data_extraction.frame_record_extractor", "FrameRecordExtractor"),
            possession_extractor=sc("game_analysis.data_extraction.possession_record_extractor", "PossessionRecordExtractor"),
            game_extractor=sc("game_analysis.data_extraction.game_record_extractor", "GameRecordExtractor"),
            correction_extractor=sc("game_analysis.data_extraction.event_correction_extractor", "EventCorrectionExtractor"),
            tactical_extractor=sc("game_analysis.data_extraction.tactical_sequence_extractor", "TacticalSequenceExtractor"),
            performance_extractor=sc("game_analysis.data_extraction.player_performance_extractor", "PlayerPerformanceExtractor"),
            prediction_extractor=sc("game_analysis.data_extraction.prediction_outcome_extractor", "PredictionOutcomeExtractor"),
            # 심판 데이터 추출 6종
            decision_record_extractor=sc("ai_referee.data_extraction.decision_record_extractor", "DecisionRecordExtractor"),
            correction_pair_extractor=sc("ai_referee.data_extraction.correction_pair_extractor", "CorrectionPairExtractor"),
            edge_case_extractor=sc("ai_referee.data_extraction.edge_case_extractor", "EdgeCaseExtractor"),
            calibration_extractor=sc("ai_referee.data_extraction.calibration_data_extractor", "CalibrationDataExtractor"),
            foul_contact_extractor=sc("ai_referee.data_extraction.foul_contact_extractor", "FoulContactExtractor"),
            violation_sequence_extractor=sc("ai_referee.data_extraction.violation_sequence_extractor", "ViolationSequenceExtractor"),
            # 비디오 편집 4종
            clip_manager=sc("game_analysis.output.video_editing.clip_manager", "ClipManager"),
            annotation_overlay=sc("game_analysis.output.video_editing.annotation_overlay", "AnnotationOverlayManager"),
            multi_angle_sync=sc("game_analysis.output.video_editing.multi_angle_sync", "MultiAngleSyncManager"),
            export_manager=sc("game_analysis.output.video_editing.export_manager", "ExportManager"),
            # 필름 세션 3종
            film_session_builder=sc("game_analysis.output.film_session.film_session_builder", "FilmSessionBuilder"),
            player_clip_package=sc("game_analysis.output.film_session.player_clip_package", "PlayerClipPackageManager"),
            teaching_point_gen=sc("game_analysis.output.film_session.teaching_point_generator", "TeachingPointGenerator"),
            # 경기 전 5종
            game_plan_gen=sc("game_analysis.output.pre_game.game_plan_generator", "GamePlanGenerator"),
            game_plan_tracker=sc("game_analysis.output.pre_game.game_plan_execution_tracker", "GamePlanExecutionTracker"),
            defensive_planner=sc("game_analysis.output.pre_game.defensive_assignment_planner", "DefensiveAssignmentPlanner"),
            offensive_priority=sc("game_analysis.output.pre_game.offensive_priority_setter", "OffensivePrioritySetter"),
            pre_game_briefing=sc("game_analysis.output.pre_game.pre_game_briefing_builder", "PreGameBriefingBuilder"),
            # 스카우팅 7종
            opponent_profiler=sc("game_analysis.output.scouting.opponent_profiler", "OpponentProfiler"),
            tendency_analyzer=sc("game_analysis.output.scouting.tendency_analyzer", "TendencyAnalyzer"),
            weakness_finder=sc("game_analysis.output.scouting.weakness_finder", "WeaknessFinder"),
            head_to_head=sc("game_analysis.output.scouting.head_to_head_analyzer", "HeadToHeadAnalyzer"),
            scouting_report=sc("game_analysis.output.scouting.scouting_report_builder", "ScoutingReportBuilder"),
            play_pattern_matcher=sc("game_analysis.output.scouting.play_pattern_matcher", "PlayPatternMatcher"),
            referee_tendency=sc("game_analysis.output.scouting.referee_tendency_analyzer", "RefereeTendencyAnalyzer"),
        )

    # =========================================================================
    # motion_analysis Tier1 감지 + Tier2 분류
    # =========================================================================
    def _run_motion_analysis(self) -> None:
        """
        per-player 슬라이딩 윈도우 → Tier1~5 전체 체인.

        Tier1: 5종 감지기 (shot/dribble/pass/movement/rebound)
        Tier2: 2종 분류기 (shot_classifier/dribble_classifier)
        Tier3: 2종 동작 분절 (shot_phase/dribble_phase)
        Tier4: 2종 자세 평가 (shooting_form/dribble_form)
        Tier5: 1종 기준 비교 (form_comparator)
        """
        buf = self._analysis_buffer
        detectors = [
            ("shot", self._shot_detector),
            ("dribble", self._dribble_detector),
            ("pass", self._pass_detector),
            ("movement", self._movement_detector),
            ("rebound", self._rebound_detector),
        ]
        classifiers = {
            "shot": self._shot_classifier,
            "dribble": self._dribble_classifier,
        }
        phase_analyzers = {
            "shot": self._shot_phase_analyzer,
            "dribble": self._dribble_phase_analyzer,
        }
        form_evaluators = {
            "shot": self._shooting_form_evaluator,
            "dribble": self._dribble_form_evaluator,
        }

        for pid in buf.get_all_player_ids():
            window = buf.get_motion_window(pid)
            if len(window) < 5:
                continue

            for action_name, detector in detectors:
                if detector is None:
                    continue
                try:
                    candidates = detector.detect(window)
                    if not candidates:
                        continue

                    for candidate in candidates:
                        # Tier2: 분류
                        classifier = classifiers.get(action_name)
                        if classifier is not None:
                            try:
                                classifier.classify(candidate, window)
                            except Exception:
                                pass

                        # Tier3: 동작 분절 (shot/dribble만)
                        phase_analyzer = phase_analyzers.get(action_name)
                        phase_result = None
                        if phase_analyzer is not None:
                            try:
                                phase_result = phase_analyzer.analyze(
                                    candidate, window,
                                )
                            except Exception:
                                pass

                        # Tier4: 자세 평가
                        form_evaluator = form_evaluators.get(action_name)
                        if form_evaluator is not None and phase_result is not None:
                            try:
                                form_evaluator.evaluate(
                                    phase_result, window,
                                )
                            except Exception:
                                pass

                except Exception:
                    _logger.debug(
                        "%s 감지 오류 player=%d", action_name, pid,
                    )

    # =========================================================================
    # game_management 이벤트 기반 갱신
    # =========================================================================
    def _update_game_management(self, events: list) -> None:
        """
        감지된 이벤트 → game_management 6종 모듈 갱신.

        - FoulManager: foul 이벤트 시 record_foul()
        - SubstitutionManager: substitution 이벤트 시 처리
        - TimeoutManager: timeout 이벤트 시 처리
        """
        ctx = self._state_manager.game_context

        for evt in events:
            evt_type = getattr(evt, "event_type", "")
            details = getattr(evt, "details", {})

            # 파울 기록
            if "foul" in evt_type and self._foul_manager is not None:
                try:
                    self._foul_manager.record_foul(
                        team_id=getattr(evt, "team_id", ""),
                        player_tracking_id=getattr(evt, "player_id", 0),
                        quarter=ctx.quarter,
                        game_clock=f"{ctx.game_clock_sec:.1f}",
                        foul_type=details.get("foul_type", "personal")
                        if isinstance(details, dict) else "personal",
                    )
                except Exception:
                    _logger.debug("FoulManager 기록 오류")

            # 교체 처리
            if "substitution" in evt_type and self._substitution_manager is not None:
                try:
                    method = getattr(
                        self._substitution_manager, "process_substitution", None,
                    )
                    if method is not None:
                        method(details if isinstance(details, dict) else {})
                except Exception:
                    _logger.debug("SubstitutionManager 처리 오류")

            # 타임아웃 처리
            if "timeout" in evt_type and self._timeout_manager is not None:
                try:
                    method = getattr(
                        self._timeout_manager, "process_timeout", None,
                    )
                    if method is not None:
                        method(details if isinstance(details, dict) else {})
                except Exception:
                    _logger.debug("TimeoutManager 처리 오류")

            # 기록 정정 (correction 이벤트)
            if "correction" in evt_type and self._record_corrector is not None:
                try:
                    from uuid import UUID
                    orig_id = details.get("original_event_id", "") if isinstance(details, dict) else ""
                    corr_type = details.get("correction_type", "score") if isinstance(details, dict) else "score"
                    if orig_id:
                        self._record_corrector.apply_correction(
                            original_event_id=UUID(str(orig_id)),
                            correction_type=corr_type,
                            corrected_data=details if isinstance(details, dict) else {},
                        )
                except Exception:
                    _logger.debug("RecordCorrector 처리 오류")

    # =========================================================================
    # Stage2 ViTPose 정밀 분석 (이벤트 트리거)
    # =========================================================================
    def _try_stage2_vitpose(self, events: list) -> None:
        """
        이벤트 유형이 stage2_triggers에 매칭되면 Stage2(ViTPose) 정밀 포즈 추론.

        현재 프레임의 선수 bbox crop → ViTPose 133kp 추론 → 결과 저장.
        CUDA Stream #2에서 실행 (Stage1과 독립).
        """
        stage2 = self._pose_backend_stage2
        if stage2 is None or not stage2.is_loaded:
            return

        # 트리거 조건 확인
        triggers = self._config.pipeline.stage2_triggers
        should_run = False
        for evt in events:
            evt_type = getattr(evt, "event_type", "")
            for trigger_keyword in triggers:
                if trigger_keyword in evt_type:
                    should_run = True
                    break
            if should_run:
                break

        if not should_run:
            return

        # 현재 프레임에서 선수 bbox 추출 → Stage2 추론
        result = self._current_frame_result
        aligned = self._current_aligned
        if result is None or aligned is None or not aligned.frames:
            return

        # 대표 카메라 1대 선택 (첫 번째)
        first_cam = next(iter(aligned.frames), None)
        if first_cam is None:
            return
        frame = aligned.frames[first_cam].image

        # detection에서 선수 bbox 추출
        person_boxes = []
        if result.detection and result.detection.player_result:
            view = result.detection.player_result.view_results.get(first_cam)
            if view is not None:
                from shared.interfaces.detector_interface import BoundingBox
                person_boxes = [
                    obj.bbox for obj in view.objects
                    if obj.bbox is not None and obj.is_person_type
                ]

        try:
            # Stage2 ViTPose 133kp 추론
            keypoints_133 = stage2.infer(frame, person_boxes or None)
            if keypoints_133:
                _logger.info(
                    "Stage2 ViTPose 정밀 분석 완료: %d명 (133kp)",
                    len(keypoints_133),
                )
                # 결과를 WebSocket으로 실시간 전송
                if self._result_dispatcher is not None:
                    self._result_dispatcher.dispatch_realtime({
                        "type": "stage2_pose",
                        "frame_index": result.frame_index,
                        "persons_analyzed": len(keypoints_133),
                        "keypoint_format": "wholebody_133",
                    })
        except Exception:
            _logger.debug("Stage2 ViTPose 추론 오류")

    # =========================================================================
    # BallStateMachine 갱신 (cross-detector)
    # =========================================================================
    def _update_ball_state(
        self,
        result: FramePipelineResult,
        frame_index: int,
    ) -> None:
        """detection 결과 + tracking 결과에서 BallStateMachine 입력 구성."""
        from shared.dto.ball_dto import BallDetection
        from shared.dto.geometry_dto import Point2D

        det = result.detection

        # 공 감지 결과
        ball_detection: BallDetection | None = None
        if det is not None and det.ball_result and det.ball_result.fused_objects:
            obj = det.ball_result.fused_objects[0]
            if obj.position is not None:
                ball_detection = BallDetection(
                    position=obj.position,
                    confidence=obj.confidence,
                    bbox=obj.bbox,
                    frame_index=frame_index,
                )

        # 선수 위치 목록 (tracking에서)
        players: list[PlayerPosition] = []
        if result.tracking is not None:
            for track in result.tracking.active_tracks:
                if track.last_bbox:
                    cx = (track.last_bbox[0] + track.last_bbox[2]) / 2.0
                    cy = (track.last_bbox[1] + track.last_bbox[3]) / 2.0
                    players.append(PlayerPosition(
                        player_id=track.global_id,
                        position=Point2D(x=cx, y=cy),
                        bbox_height=track.last_bbox[3] - track.last_bbox[1],
                    ))

        # 림 위치 (hoop detection)
        rim_pos: Point2D | None = None
        if det is not None and det.hoop_result and det.hoop_result.fused_objects:
            hp = det.hoop_result.fused_objects[0].position
            if hp is not None:
                rim_pos = hp

        self._ball_state_machine.update(
            detection=ball_detection,
            players=players,
            rim_position=rim_pos,
        )

    # =========================================================================
    # FRAME 3종 감지기 입력 빌더
    # =========================================================================
    def _build_score_input(
        self,
        result: FramePipelineResult,
        frame_index: int,
        timestamp: float,
    ) -> object:
        """FramePipelineResult → ScoreFrameInput 변환."""
        from game_analysis.game_state.event_detection.score_detector import (
            ScoreFrameInput,
        )
        det = result.detection
        ball_rim_dist = 999.0
        ball_through = False
        ball_above_rim = False
        ball_below_rim = False
        ball_vy = 0.0

        if det is not None and det.ball_result and det.hoop_result:
            ball_fused = det.ball_result.fused_objects
            hoop_fused = det.hoop_result.fused_objects
            if ball_fused and hoop_fused:
                # 볼 위치: position 우선 → bbox 폴백
                bx, by = None, None
                b = ball_fused[0]
                if getattr(b, "position", None) is not None:
                    bx, by = b.position.x, b.position.y
                elif getattr(b, "bbox", None) is not None:
                    bx = b.bbox.x + b.bbox.width / 2
                    by = b.bbox.y + b.bbox.height / 2

                # 후프 위치: position 우선 → bbox 폴백
                hx, hy = None, None
                h = hoop_fused[0]
                if getattr(h, "position", None) is not None:
                    hx, hy = h.position.x, h.position.y
                elif getattr(h, "bbox", None) is not None:
                    hx = h.bbox.x + h.bbox.width / 2
                    hy = h.bbox.y + h.bbox.height / 2

                if bx is not None and hx is not None:
                    dx = bx - hx
                    dy = by - hy
                    px_dist = (dx * dx + dy * dy) ** 0.5

                    # 픽셀 거리 → 미터 (림 크기 기준: 림 직경 45cm ≈ 영상에서 ~15px)
                    px_to_m = 0.45 / 15.0  # 0.03m/px
                    ball_rim_dist = px_dist * px_to_m
                    ball_through = ball_rim_dist < 2.0  # 픽셀 변환 부정확 → 넓은 threshold
                    ball_above_rim = by < hy
                    ball_below_rim = by > hy

                    # 볼 수직 속도 추정
                    prev_by = getattr(self, "_prev_ball_y", by)
                    ball_vy = (by - prev_by) * px_to_m * 10
                    self._prev_ball_y = by

        if frame_index % 50 == 0:
            _logger.warning(
                "[SCORE F#%d] ball_rim=%.2f through=%s above=%s below=%s vy=%.2f",
                frame_index, ball_rim_dist, ball_through, ball_above_rim, ball_below_rim, ball_vy,
            )

        return ScoreFrameInput(
            frame_index=frame_index,
            timestamp_sec=timestamp,
            ball_rim_distance_m=ball_rim_dist,
            ball_through_hoop=ball_through,
            ball_above_rim=ball_above_rim,
            ball_below_rim=ball_below_rim,
            ball_vertical_velocity_ms=ball_vy,
        )

    def _build_possession_input(
        self,
        result: FramePipelineResult,
        frame_index: int,
        timestamp: float,
    ) -> object:
        """FramePipelineResult → PossessionFrameInput 변환."""
        from game_analysis.game_state.event_detection.possession_tracker import (
            PossessionFrameInput,
        )
        holder_id: int | None = None
        holder_team = ""
        ball_controlled = False
        tracking = result.tracking
        det = result.detection

        if tracking and det and det.ball_result:
            ball_fused = det.ball_result.fused_objects
            # 볼 위치: position 우선, 없으면 bbox 중심
            ball_x, ball_y = None, None
            if ball_fused:
                b = ball_fused[0]
                if getattr(b, "position", None) is not None:
                    ball_x, ball_y = b.position.x, b.position.y
                elif getattr(b, "bbox", None) is not None:
                    ball_x = b.bbox.x + b.bbox.width / 2
                    ball_y = b.bbox.y + b.bbox.height / 2

            if ball_x is not None and tracking.active_tracks:
                min_dist = float("inf")
                for track in tracking.active_tracks:
                    if track.last_bbox:
                        cx = (track.last_bbox[0] + track.last_bbox[2]) / 2.0
                        cy = (track.last_bbox[1] + track.last_bbox[3]) / 2.0
                        d = ((ball_x - cx) ** 2 + (ball_y - cy) ** 2) ** 0.5
                        if d < min_dist:
                            min_dist = d
                            holder_id = track.global_id
                            holder_team = track.team_id or ""

                if min_dist < 60.0 and holder_team and holder_team != "unknown":
                    ball_controlled = True
                else:
                    holder_id = None
                    holder_team = ""
                    ball_controlled = False

        # 볼 소유 팀 스무딩 (최근 10프레임 다수결)
        if ball_controlled and holder_team:
            self._holder_team_history.append(holder_team)
            if len(self._holder_team_history) > 10:
                self._holder_team_history = self._holder_team_history[-10:]
            # 다수결
            from collections import Counter
            known = [t for t in self._holder_team_history if t and t != "unknown"]
            if known:
                holder_team = Counter(known).most_common(1)[0][0]

        return PossessionFrameInput(
            frame_index=frame_index,
            timestamp_sec=timestamp,
            ball_holder_tracking_id=holder_id,
            ball_holder_team_id=holder_team,
            ball_is_controlled=ball_controlled,
        )

    def _build_dead_ball_input(
        self,
        result: FramePipelineResult,
        frame_index: int,
        timestamp: float,
    ) -> object:
        """FramePipelineResult → DeadBallFrameInput 변환."""
        from game_analysis.game_state.event_detection.dead_ball_detector import (
            DeadBallFrameInput,
        )
        ctx = self._state_manager.game_context

        # 코트 위 선수 수 + 평균 속도
        on_court = 10
        avg_speed = 2.0  # 기본값 (움직이는 중)
        if result.tracking is not None:
            tracks = result.tracking.active_tracks
            on_court = len(tracks)
            # bbox 이동량으로 속도 추정
            speeds = []
            for t in tracks:
                fs = getattr(t, "frames_since_seen", 0)
                if fs == 0 and hasattr(t, "last_bbox") and t.last_bbox:
                    # 간단한 속도 추정: 트래킹 프레임 수 대비 이동량
                    speeds.append(getattr(t, "total_frames", 1) * 0.1)
            if speeds:
                avg_speed = sum(speeds) / len(speeds)

        # 득점 후 감지 (score dispatch된 경우)
        made_basket = False
        # 나중에 score_detector 결과와 연동

        return DeadBallFrameInput(
            frame_index=frame_index,
            timestamp_sec=timestamp,
            game_clock_running=ctx.game_clock_sec > 0.0,
            game_clock_value=f"{ctx.game_clock_sec:.1f}",
            players_on_court_count=on_court,
            avg_player_speed_ms=avg_speed,
            made_basket_detected=made_basket,
        )

    # =========================================================================
    # AI 심판 FrameContext 빌더
    # =========================================================================
    def _build_referee_context(self, frame_index: int) -> object:
        """FramePipelineResult + GameContext → FrameContext 변환."""
        from ai_referee.rules.base_rule import FrameContext

        result = self._current_frame_result
        ctx = self._state_manager.game_context

        # 선수 위치 (tracking)
        player_positions: dict[int, tuple[float, float]] = {}
        if result is not None and result.tracking:
            for track in result.tracking.active_tracks:
                if track.last_bbox:
                    cx = (track.last_bbox[0] + track.last_bbox[2]) / 2.0
                    cy = (track.last_bbox[1] + track.last_bbox[3]) / 2.0
                    player_positions[track.global_id] = (cx, cy)

        # 공 위치
        ball_pos: tuple[float, float, float] | None = None
        ball_holder: int | None = None
        if result is not None and result.detection and result.detection.ball_result:
            ball_fused = result.detection.ball_result.fused_objects
            if ball_fused:
                bp3d = ball_fused[0].position_3d
                bp2d = ball_fused[0].position
                if bp3d is not None:
                    ball_pos = (bp3d.x, bp3d.y, bp3d.z)
                elif bp2d is not None:
                    ball_pos = (bp2d.x, bp2d.y, 0.0)

        # 3D 키포인트 (pose)
        player_kp: dict[int, dict[str, tuple[float, float, float]]] = {}
        if result is not None and result.pose and result.pose.poses_3d:
            for pose_3d in result.pose.poses_3d:
                kp_dict: dict[str, tuple[float, float, float]] = {}
                for i, row in enumerate(pose_3d.keypoints_3d):
                    kp_dict[str(i)] = (
                        float(row[0]), float(row[1]), float(row[2]),
                    )
                player_kp[pose_3d.person_id] = kp_dict

        # 페인트존 결정 (공격 방향에 따라 상대편 페인트존 = 공격 페인트존)
        zones = self._court_zones
        attack_dir = self._attack_direction
        if attack_dir == "right":
            paint = zones.get("paint_right", {})
        else:
            paint = zones.get("paint_left", {})

        # 데드볼 여부
        from shared.constants.game_management_constants import GameState as _GS
        is_dead = ctx.game_state in (_GS.DEAD_BALL, _GS.TIMEOUT, _GS.PERIOD_BREAK, _GS.HALFTIME, _GS.FINAL)

        return FrameContext(
            frame_number=frame_index,
            timestamp=ctx.frame_timestamp,
            quarter=ctx.quarter,
            game_clock_sec=ctx.game_clock_sec,
            shot_clock_sec=ctx.shot_clock_sec,
            is_dead_ball=is_dead,
            is_live_ball=not is_dead,
            possession_team_id=ctx.possession_team_id,
            player_positions=player_positions,
            ball_position=ball_pos,
            ball_possession_player_id=ball_holder,
            player_keypoints=player_kp,
            court_boundaries={
                "x_min": 0.0, "x_max": 1920.0,
                "y_min": 0.0, "y_max": 1080.0,
            },
            paint_zone_bounds=paint,
            half_court_x=float(zones.get("half_court_x", 960.0)),
            extra={
                "attack_direction": attack_dir,
            },
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "GameOrchestrator",
]

__version__ = "1.0.0"
