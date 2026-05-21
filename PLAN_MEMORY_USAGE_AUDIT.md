# Plan — Memory Usage Audit

작성일: 2026-05-14
대상 커밋: main @ f12b788 (v0.2.1+)
조사 범위: COURTVIEW_DESK 전체 (read-only grep/read)

---

## 1. 요약

### 1.1 추정 RSS / VRAM

| 카테고리 | 정상 (5분 가동 후) | 30분 LIVE 종료 직전 | 비고 |
|---|---:|---:|---:|
| **engine_proc RAM** | ~2.8 GB | ~3.5 ~ 4.5 GB | PyTorch ~700 MB + TRT host copy + numpy buffers |
| **ui_proc RAM** | ~250 MB | ~250 MB | FastAPI 정적 자산 + Jinja2 |
| **ffmpeg ×8 (engine 손자)** | ~80 MB × 8 = 640 MB | 640 MB | RTSP demux + sw decode (HW 시 더 작음) |
| **go2rtc (ui 손자)** | ~60 MB | ~60 MB | Go 바이너리 |
| **VRAM (engine)** | ~2.5 GB | ~2.5 GB | 모델 + workspace + activation |
| **총 합계** | **~3.8 GB RAM + 2.5 GB VRAM** | **~4.5 GB RAM + 2.5 GB VRAM** | launcher 임계치 6 GB 대비 75 % |

> 산식·근거는 각 항목별 표 참조. **30분 시점에서도 launcher 6 GB 알람이 아직 한참 남는다**는 게 핵심 결론. 단, §3 잠재 누수 위치가 트리거되면 30분 이후 선형 증가하여 1~2시간 내 임계 도달 가능.

### 1.2 가장 큰 메모리 항목 Top 5

| Rank | 항목 | 추정 | 위치 |
|---|---|---:|---|
| 1 | PyTorch + CUDA runtime 상주 | ~700 MB RAM + ~500 MB VRAM | yolov8/vitpose .pt 로드 시 |
| 2 | ViTPose-B engine + workspace | ~600 MB VRAM | `tensorrt_pool.py:103` (`VITPOSE_B=600.0 MB`) |
| 3 | YOLOv8-Pose engine + workspace | ~800 MB VRAM | `tensorrt_pool.py:102` (`YOLOV8_POSE=800.0 MB`) |
| 4 | `_possession_frames` deque(maxlen=1800) | 최대 ~180 MB RAM | `engine/analysis_buffer.py:191` |
| 5 | `_frame_buffer` deque(maxlen=900) | 최대 ~90 MB RAM | `engine/analysis_buffer.py:177` |

---

## 2. 영역별 상세

### 2.1 ML 모델 (디스크 / VRAM)

#### 2.1.1 디스크 weights/

| 파일 | 크기 | 활성 사용 | 비고 |
|---|---:|---|---|
| `weights/vitpose-l-wholebody.onnx` | 1,177 MB | ❌ (large 미사용, base 사용) | dead weight — 배포 시 제거 검토 |
| `weights/vitpose-b-wholebody.onnx` | 344 MB | ✅ ONNX/TRT 빌드용 | `_MODEL_INPUT_SHAPES[VITPOSE_B]` |
| `weights/CV-BBox_v9.pt` | 194 MB | ✅ PyTorch 모델 | 1.59 MB action 분류 |
| `weights/CV-Digit_v6.pt` | 154 MB | ✅ OCR PyTorch | jersey OCR |
| `weights/yolo11l-pose.onnx` | 101 MB | (선택) | YOLO 변환본 |
| `weights/CV-BBox_v9.onnx` | 97 MB | ✅ ONNX → TRT 변환 | |
| `weights/CV-Team_v3.pt` | 92 MB | ✅ Team classifier | |
| `weights/CV-Digit_v6.onnx` | 77 MB | ✅ ONNX | |
| `weights/yolo11m-pose.onnx` | 80 MB | ✅ | |
| `weights/yolo11l-pose.pt` | 51 MB | (선택) | |
| `weights/CV-BBox_v9.engine` | 52 MB | ✅ prebuilt TRT | `tensorrt_pool.py:287` prebuilt 분기 |
| `weights/yolo11m-pose.pt` | 40 MB | ✅ stage1 후보 | |
| 합계 (실사용) | **~1,200 MB** | | |

> `_appdata/tensorrt_cache/*.engine` 누적: **1,363 MB (15개)** — 모델 버전 변경 시 누적, 정리 로직 없음. (§5에서 다룸)
> 가장 큰 캐시: `44cc9ce5d86264d8.engine = 594.87 MB` (ViTPose 추정).

#### 2.1.2 VRAM 추정치 (tensorrt_pool.py:100-104)

| ModelID | 코드 추정 | 실제 (workspace+weights+activation) | 위치 |
|---|---:|---:|---|
| `YOLOV8_DET` | 400 MB | ~500 MB | `engine/gpu/tensorrt_pool.py:101` |
| `YOLOV8_POSE` | 800 MB | ~900 MB | `engine/gpu/tensorrt_pool.py:102` |
| `VITPOSE_B` | 600 MB | ~750 MB | `engine/gpu/tensorrt_pool.py:103` |
| TRT workspace (per-engine) | — | 2,048 MB (config) | `configs/pose/tensorrt.yaml:18` |
| TRT workspace (gpu_config) | — | 1,024 MB | `configs/base/gpu_config.yaml:51` |
| **총 VRAM 추정** | **1,800 MB** | **~2,500 MB** | GPUConfig.vram_limit_mb=8192 default |

> workspace는 빌드 시 일시적 + 추론 시 일부 유지. RTX 5060 8 GB 기준 25~30 % 점유.
> `GPUManager._VRAM_CRITICAL_RATIO=0.95` → 약 7.8 GB 초과 시 emergency_cleanup (`engine/gpu/gpu_manager.py:137`).

#### 2.1.3 워밍업 / cache buffer

- `tensorrt_pool.warmup_model()` 1회 더미 추론 (`engine/gpu/tensorrt_pool.py:413-422`): 입력 shape 1개당 numpy zeros — 일시적, 누수 없음.
- TRT engine cache 디렉토리는 정리 안 됨 (§5).

---

### 2.2 Frame Buffer / Decoder Cache (RAM)

#### 2.2.1 카메라당 frame 산식

- 1920 × 1080 × 3 bytes (BGR24) = **6,220,800 bytes ≈ 5.93 MB / frame**
- 8 cam 동시 = **47.5 MB**

#### 2.2.2 VideoDecoder 인스턴스별 캐시

| 필드 | 크기 (cam당) | × 8 cam | 위치 (file:line) | 누수 위험 |
|---|---:|---:|---|---|
| `_latest_frame` (BGR numpy) | 5.93 MB | 47.5 MB | `infrastructure/preprocessing/video_decoder.py:544,1348` | 낮음 — 매 frame 덮어쓰기 |
| `_latest_jpeg` (encoded) | ~150 KB | ~1.2 MB | `video_decoder.py:545,695` | 낮음 |
| `_latest_jpeg_quality` (int) | 28 B | 224 B | 무시 | — |
| ffmpeg stdout pipe (kernel) | 64 KB (OS default) | 512 KB | `video_decoder.py:1044` bufsize=0 | 낮음 |
| reader thread `data` bytearray | 5.93 MB (read 중 일시) | 47.5 MB | `video_decoder.py:1251` `data = bytearray()` | **중** — `frame.copy()` 후 `data` 가 GC 안 되면 누적 |
| ffmpeg stderr 파일 핸들 | 미미 | — | `video_decoder.py:1038` `_ffmpeg_stderr_fp` | **중** — §3 누수 후보 |
| `_probe_history` 전역 dict | ~200 B/host | 무한 host로 증가 시 위험 | `video_decoder.py:94` | 낮음 — deque maxlen=10, 정상 운영 시 한도 있음 |

**소계: 카메라 8대 latest_frame 캐시 ≈ 47.5 MB + reader 일시 ~ 47.5 MB peak = 약 95 MB**

#### 2.2.3 듀얼 스트림 (녹화 디코더 별도)

- `_recording_decoders: dict[str, VideoDecoder]` (`engine/io/frame_ingestion.py:189`)
- 녹화 모드 활성 시 카메라 × 2 디코더 → **추가 47.5 MB latest_frame**
- 단, 녹화는 ffmpeg subprocess copy 모드라 별도 디코딩 안 함 (`engine/io/recording.py:21` `-c copy`)
- 실제로는 frame_ingestion 의 recording decoder 만 살아있음 → +95 MB peak 가능

---

### 2.3 Frame Ingestion / Aligner

| 필드 | 크기 | 위치 | 비고 |
|---|---:|---|---|
| `FrameAligner._buffers` per-cam list | 120 frame × 5.93 MB = **712 MB** max | `infrastructure/preprocessing/frame_aligner.py:223,289` `MAX_ALIGNMENT_BUFFER=120` | **8 cam × 120 = 5,696 MB 이론 최대** |
| 정상 운영 시 (tolerance 동작) | cam당 1~5 frame | 8 cam × 5 × 5.93 = **237 MB** peak | aligner.try_align 이 정상 동작하면 즉시 pop_left |
| `_aligner._buffers` 정렬 실패 시 누적 | 위 712 MB cap 까지 | 정렬 실패 모드 (예: 카메라 1대 down)에서 buffer 폭주 가능 | **중** — drift 대량 시 |
| FrameNormalizer | 일시 인자만 — 매 frame 새 ndarray | `infrastructure/preprocessing/video_normalizer.py` | 누수 없음, GC 의존 |
| `_decoders: dict[str, VideoDecoder]` | 카메라 × VideoDecoder 인스턴스 메모리 | `engine/io/frame_ingestion.py:188` | 8개 인스턴스 ~ 100 KB 자체 + frame 캐시는 §2.2 |

> 산식: `MAX_ALIGNMENT_BUFFER=120` (`infrastructure/preprocessing/frame_aligner.py:45`)
> × MAX_CAMERAS=8 (`shared/constants/camera_constants.py:57`)
> × 5.93 MB = **5.69 GB 이론 최대** — 정상 시 도달 안 함이지만 단일 카메라 끊김 시 위험.

---

### 2.4 Analysis Buffer (engine/analysis_buffer.py)

| 필드 | maxlen / 정책 | 메모리 추정 | file:line | 누수 위험 |
|---|---|---:|---|---|
| `_frame_buffer: deque[FramePipelineResult]` | maxlen=900 (30fps×30s) | **~90 MB** (per result ~100 KB) | `analysis_buffer.py:68,177` | ✅ cap 있음 |
| `_possession_frames: deque[FramePipelineResult]` | **maxlen=1800** | **최대 ~180 MB** | `analysis_buffer.py:191` (2026-05-13 수정) | ✅ cap 있음 |
| `_event_buffer: list[Any]` | **무한** | 경기 1시간 × 평균 10 evt/min ≈ 600개 ≈ 60 KB | `analysis_buffer.py:180,253` | **중** — 무한 list, game 종료까지 누적 |
| `_motion_windows: dict[int, deque[MotionSnapshot]]` | per-player maxlen=30 | 30 selectors × ~5KB × 30 deque entries ≈ 4 MB | `analysis_buffer.py:183,327` | ✅ cap 있음 |
| `_period_possessions: list[AnalyzerInput]` | 무한 (쿼터별 reset) | 보통 30 possession/Q × ~5KB = 150 KB | `analysis_buffer.py:196,363,407` | ✅ flush_period() |
| `_all_possession_summaries: list[AnalyzerInput]` | **무한** (게임당 reset 없음) | 1게임 120 possession × ~5KB = 600 KB | `analysis_buffer.py:198,364` | **중** — POSTGAME 까지 보관 의도 OK, 그러나 게임 끝나도 `reset()` 명시 호출 필요 |
| `_frame_extractions: list[dict]` | 30프레임마다 1개 추가, 60분 × 60 = 3,600개 | dict당 keypoint+bio = ~50 KB → **180 MB** | `analysis_buffer.py:201,566` | **🔴 위험** — get_frame_extractions() 호출 시 clear, 미호출 시 무제한 |
| `_motion_windows` dict key | track_id 무제한 키 | dead track 제거 로직 없음 | `analysis_buffer.py:183,326` | **🔴 위험** — 게임 중 track_id 가 재발급되어 dict key 가 monotonic 증가 |

> **합계 (정상 운영)**: 270 MB ~ 350 MB
> **합계 (60분 GamePlay 종료 시)**: 최대 ~ 600 MB 이상 가능 (`_frame_extractions` 미수거 시)

---

### 2.5 Frame Pipeline / 결과 history

| 자료구조 | maxlen | 메모리 추정 | file:line |
|---|---|---:|---|
| `FramePipeline._history: list[FramePipelineResult]` | 100 | ~10 MB | `engine/pipeline/frame_pipeline.py:142,257,593` |
| `EventPipeline._event_history: list[DetectedEvent]` | 500 | ~50 KB | `engine/pipeline/event_pipeline.py:159,363,561` |
| `PossessionPipeline._history` | 200 | ~2 MB | `engine/pipeline/possession_pipeline.py:134,264,504` |
| `PeriodPipeline._history` | 50 | ~500 KB | `engine/pipeline/period_pipeline.py:74,132,235` |
| `PostgamePipeline._history` | 20 | ~200 KB | `engine/pipeline/postgame_pipeline.py:102,184,355` |
| `DetectionFusion._history` | 200 | ~2 MB | `engine/pipeline/fusion/detection_fusion.py:77,168,464` |
| `PoseFusion._history` | 200 | ~2 MB | `engine/pipeline/fusion/pose_fusion.py:65,181,236` |
| `TrackingFusion._history` | 200 | ~2 MB | `engine/pipeline/fusion/tracking_fusion.py:62,175,281` |
| `CadenceScheduler._history: list[TickResult]` | 200 | ~50 KB | `engine/orchestrator/cadence_scheduler.py:55,152,277` |
| `RefereeOrchestrator._history` | 500 | ~200 KB | `engine/referee/referee_orchestrator.py:104,161,354` |
| `MultiAngleValidator._history` | 200 | ~100 KB | `engine/referee/multi_angle_pipeline.py:50,132,206` |
| `FrameToEventConverter._ball_vy_history` | deque(maxlen=10) | <1 KB | `engine/pipeline/frame_to_event_converter.py:136` |
| `FrameToEventConverter._possession_history` | deque(maxlen=30) | <5 KB | `engine/pipeline/frame_to_event_converter.py:140` |

> **소계: ~19 MB** — `FramePipeline._history` 가 단연 큼 (FramePipelineResult 가 무거움).

---

### 2.6 Recording / S3 upload queue

#### 2.6.1 RecordingService

| 항목 | 위치 | 메모리 |
|---|---|---:|
| `subprocess.Popen` per-camera (ffmpeg `-c copy`) | `engine/io/recording.py:649` | OS 손자 프로세스 → engine_proc 메모리 X. **각 60~100 MB** (`-c copy` 라 무인코딩) |
| `_pids` PID 추적 파일 | `recording.py:53` `pids.txt` | disk 만 |
| `cameras: dict[str, CameraRecordingState]` | `recording.py:330` | <10 KB |
| HighlightClipService `_pending: dict[str, Future]` | `api_server/services/highlight_clip_service.py:82` | Future 객체 무한 누적 가능 (`_pending` 정리 코드 검색됨 — done callback 으로 pop) |
| ThreadPoolExecutor max_workers=2 | `highlight_clip_service.py:45,78` | 스레드 2개 ~ 2 MB |

#### 2.6.2 UploadQueue (engine_proc RAM 영향 없음)

- **SQLite WAL** (`infrastructure/storage/upload_queue.py:104`) — 디스크 영속 큐
- engine_proc 의 메모리에 큐 적재 없음. 메모리 영향은 SQLite 캐시 ~10 MB 미만.
- 영구 누수 없음 — `cleanup_completed(older_than_sec=7*86400)` 7일 후 자동 삭제 (`upload_queue.py:205`).

---

### 2.7 Event Detector 시계열 buffer

13개 detector × 각자 `_event_history: list[GameEvent]` (max 300~500개).

| Detector | maxlen | 위치 |
|---|---:|---|
| score_detector | 500 | `game_analysis/game_state/event_detection/score_detector.py:47` |
| shot_event_detector | 500 (×2: `_event_history`, `_shot_attempts`) | `shot_event_detector.py:49,693-696` |
| foul_detector | 500 | `foul_detector.py:44` |
| rebound_detector | 500 | `rebound_detector.py:44` |
| assist_detector | 500 | `assist_detector.py:46` |
| block_detector | 500 | `block_detector.py:46` |
| steal_detector | 500 | `steal_detector.py:46` |
| turnover_detector | 500 | `turnover_detector.py:46` |
| possession_tracker | 500 | `possession_tracker.py:45` |
| free_throw_detector | 300 (×2) | `free_throw_detector.py:47,544-547` |
| jump_ball_detector | 500 | `jump_ball_detector.py:44` |
| dead_ball_detector | 500 | `dead_ball_detector.py:46` |
| box_out_detector | 500 | `box_out_detector.py:45` |
| screen_detector | 500 | `screen_detector.py:52` |
| drive_detector | 500 | `drive_detector.py:53` |
| fast_break_detector | 500 | `fast_break_detector.py:51` |
| **LiveEventValidator** | **5000** | `game_analysis/game_state/live_workspace/live_event_validator.py:45` (가장 큼) |
| play_by_play | 2000 | `game_analysis/output/game_record/play_by_play.py:36` |
| highlight_detector | 500 (×2 candidate+history) | `game_analysis/output/highlight/highlight_detector.py:40` |
| excitement_scorer | 500 (×2) | `excitement_scorer.py:36` |
| clip_extractor | 500 | `clip_extractor.py:36` |
| quarter_summary | 500 | `quarter_summary.py:33` |
| game_sheet_generator | 500 | `game_sheet_generator.py:36` |
| 7 tactical_analysis 모듈 | 500 each | `game_analysis/analysis/team/tactical_analysis/*.py` |

GameEvent 평균 1 KB 가정 → **22+ detector × 500 × 1KB ≈ 11 MB** 정상, LiveEventValidator + play_by_play 추가하면 **~20 MB**.

⚠️ **주의**: 모두 `if len() > max: list = list[-max:]` 슬라이싱 패턴 — deque 가 아니라 매번 새 list 객체 할당. allocator churn 다소 발생. (큰 누수는 아님)

---

### 2.8 Player / Ball / Hoop Tracker

#### 2.8.1 PlayerTracker

| 필드 | 위치 | 메모리 영향 |
|---|---|---:|
| `_tracks: dict[int, _TrackState]` | `detection/player_detection/player_tracker.py:224` | ID 무한 증가 가능. `_remove_dead_tracks` 가 `max_age=360 frame` 초과 track 삭제 (`player_tracker.py:808-817`) ✅ |
| `_appearance_features: dict[int, NDArray]` | `player_tracker.py:228` | dead track 제거 시 함께 pop ✅ (`player_tracker.py:817`) |
| `_DEFAULT_MAX_AGE=360` | `detection/player_detection/models.py:99` | 30fps 기준 12초 → 정상 |
| `JerseyOCR._observation_history` per-track | `detection/player_detection/jersey_ocr.py:1143` deque(maxlen=30) | <100 KB |
| `ReidModule._gallery: OrderedDict[int, _GalleryEntry]` | `detection/player_detection/reid_module.py:229` | `gallery_feature_max_age=300` frame 초과 제거 (`reid_module.py:651`) ✅ |
| `MultiViewTracker.history_xy` per-track | `detection/player_detection/multiview_tracker.py:494-496` | maxlen=30 ✅ |

#### 2.8.2 BallTracker

| 필드 | maxlen | 위치 |
|---|---:|---|
| `BallState._state_history` | 90 | `detection/ball_detection/ball_state.py:232` (`_STATE_HISTORY_MAX=90`) |
| `BallState._position_history` | 5 | `ball_state.py:235` (`_VELOCITY_SMOOTHING_WINDOW=5`) |
| `BallState._speed_history` | 5 | `ball_state.py:238` |
| BallTrack `trajectory` | 90 (`BALL_TRACKING_TRAJECTORY_LENGTH`) | `detection/ball_detection/ball_tracker.py:337,821` |
| `BALL_TRACKING_MAX_TRACK_AGE=30` frame | | `shared/constants/ball_constants.py:334` (1초@30fps) |
| `_detection_cache` deque | maxlen=300 (`_MAX_CACHE_SIZE`) | `ball_detector.py:264-265` |

#### 2.8.3 HoopDetector

- `_detection_cache: deque[HoopDetectionResult]` maxlen=300 (`detection/hoop_detection/hoop_detector.py:349-350`)
- `NetMotionExtractor` ring buffers (`detection/hoop_detection/data_extraction/net_motion_extractor.py:193-195`) maxlen=ring_size (pre+post frames+5) → 일반적으로 ~30~60 frames × **160×120 ROI** 이미지 = ~2~5 MB

> **모든 tracker 합계 ≈ 20~30 MB** — 잘 통제됨.

---

### 2.9 WebSocket / WebRTC

| 항목 | 위치 | 메모리 |
|---|---|---:|
| `ConnectionManager._connections: list[WebSocket]` | `api_server/websocket/connection_manager.py:39` | 클라이언트 수 × ~수 KB. 무제한이지만 동시 클라이언트 ≤ 5 가정 시 무시 가능 |
| `ResultDispatcher._ws_queue: deque(maxlen=500)` | `engine/io/result_dispatcher.py:103` | dict per item ~1 KB × 500 = 500 KB ✅ |
| `ResultDispatcher._cloud_queue: deque(maxlen=500)` | `result_dispatcher.py:104` | 동일 ✅ |
| `ResultDispatcher._history: list[DispatchRecord]` | `result_dispatcher.py:102,252-257` | `_MAX_DISPATCH_HISTORY=200` × ~200 B = 40 KB ✅ |
| Go2rtcService consumer buffer | `vendor/go2rtc/` Go 바이너리 | engine_proc 영향 없음 |

> **소계: <2 MB.** 가장 큰 위험은 _connections 무제한 list 인데, UI 한 명만 쓰는 데스크톱 앱이라 실제로는 1~2 connection.

---

### 2.10 TensorRT inference buffer / engine cache

| 항목 | 위치 | 크기 |
|---|---|---:|
| `_appdata/tensorrt_cache/` 디스크 누적 | 15 files | **1,363 MB** (가장 큰 단일 file = 594.87 MB) |
| TRT workspace_size_mb (pose) | `configs/pose/tensorrt.yaml:18` | 2,048 MB VRAM (빌드 시) |
| TRT workspace_size_mb (gpu) | `configs/base/gpu_config.yaml:51` | 1,024 MB VRAM (런타임) |
| YOLOv8 backend workspace | `pose_estimation/backends/yolov8_backend.py:516` | 기본 1,024 MB |
| TRT activation memory (per-inference) | engine 빌드 시 결정 | 추정 200~500 MB VRAM |

> TRT engine cache 는 디스크만 점유. RAM 영향 없음. 하지만 **모델 버전 바뀔 때마다 새 engine 추가되고 청소 코드 없음** — 운영 1년차 5~10 GB 도달 가능. (§5 참조)

---

### 2.11 잠재 누수 위치 (이번 audit 의 핵심)

| # | 위치 | 코드 패턴 | 위험도 | 권장 fix |
|---|---|---|---|---|
| 1 | `engine/analysis_buffer.py:201,566` `_frame_extractions: list[dict]` | 30프레임마다 1개 append. `get_frame_extractions()` 호출 없으면 무한 누적. 1게임 60분 × 60개 = 3,600 ≈ **180 MB**. | ★★★ | maxlen 있는 deque 로 교체 또는 `_MAX_FRAME_EXTRACTIONS=3600` cap |
| 2 | `engine/analysis_buffer.py:180,253` `_event_buffer: list[Any]` extend | reset() 만 clear. 게임 종료 안 하면 무한. | ★★ | `_MAX_EVENT_BUFFER=2000` cap |
| 3 | `engine/analysis_buffer.py:183,326` `_motion_windows: dict[int, deque]` | player_id key 무제한. dead track 후에도 dict 에 남음. | ★★★ | PlayerTracker dead track 시 callback 으로 motion_windows pop |
| 4 | `engine/analysis_buffer.py:198,364` `_all_possession_summaries: list[AnalyzerInput]` | game reset 없으면 무한 (1게임 = 120 possession ~ OK) | ★ | 명시적 game 종료 시 reset() 호출 확인 |
| 5 | `infrastructure/preprocessing/frame_aligner.py:223,289` `_buffers: dict[str, list[FrameData]]` MAX_ALIGNMENT_BUFFER=120 | 카메라 1대 down → drift 계속 커지면 buffer 가 120 까지 채워짐. **8 cam × 120 frame × 5.93 MB = 5.7 GB 이론 cap**. 정상 시 cam당 1~5 frame. | ★★★ | 일정 시간 이상 drift 발생 시 카메라 force-reset, 또는 MAX_ALIGNMENT_BUFFER 를 30 으로 하향 |
| 6 | `infrastructure/preprocessing/video_decoder.py:94` `_probe_history: dict[str, deque]` 전역 | host key 무제한. 실제론 host 후보 제한적이지만 mDNS/discover 가 임의 host 추가 시 누적 | ★ | maxlen=100 host TTL eviction |
| 7 | `infrastructure/preprocessing/video_decoder.py:1038` `_ffmpeg_stderr_fp = open(...)` | close 는 `_stop_ffmpeg_pipe` 에서 처리 (line 1098-1103) ✅. 단, ffmpeg crash 후 try-except 에서 close 누락 경로 검토 필요. open(..., buffering=1) line-buffered 파일 핸들. | ★ | 현재 코드 try/except 로 보호되어 있음 — OK |
| 8 | `api_server/websocket/connection_manager.py:39` `_connections: list[WebSocket]` 무제한 | 클라이언트가 연결 → 비정상 종료 시 disconnect 호출 안 될 수 있음 | ★★ | heartbeat ping 으로 좀비 연결 정리, `_MAX_CONNECTIONS=10` cap |
| 9 | `api_server/services/highlight_clip_service.py:82` `_pending: dict[str, Future]` | extract 완료 후 dict 정리 코드를 callback 으로 등록해야 함 (검색 시 확인 필요) | ★★ | future.add_done_callback 으로 self._pending.pop 보장 |
| 10 | `engine/orchestrator/game_orchestrator.py:887` `_pending_substitutions = []` getattr 패턴 | 명시적 cap 없음, getattr fallback. 정상 게임당 ~10건 미만이라 실제 누수는 작음 | ★ | maxlen 명시화 |
| 11 | `engine/orchestrator/game_orchestrator.py:2758-2760` `_holder_team_history` | `> 10` 후 슬라이스 — OK ✅ | — | — |
| 12 | `subprocess.Popen` ffmpeg pipe TEARDOWN 누락 시 | `video_decoder.py:1085 terminate() → wait(timeout=2) → kill()`. 정상 종료 보장 안 됨, 좀비 ffmpeg 가능 (24.13 dangling session 이슈). 메모리는 OS 수거하지만 카메라 슬롯 문제 ★ 이 별도 발생 | ★★ | TEARDOWN 패킷 발송 코드 `video_decoder.py:1107-1156` 이미 있음. 추가 모니터링 필요. |
| 13 | `engine/io/recording.py:649` `subprocess.Popen` ffmpeg recording | `_c copy` 로 가벼움. close 보장됨 | ★ | OK |
| 14 | `_appdata/tensorrt_cache/` 디스크 누적 | 코드에 청소 로직 없음. 운영 1년차 5~10 GB 도달 가능 (디스크) | ★★ | TTL cleanup 또는 모델 버전 changed 시 stale engine 삭제 |
| 15 | TensorRT workspace_size 중복 설정 (1024 vs 2048) | `configs/base/gpu_config.yaml:51`=1024, `configs/pose/tensorrt.yaml:18`=2048. 어떤 config 가 우선되는지 확인 필요 — 둘 다 적용되면 VRAM 낭비 | ★ | config 일원화 (8GB VRAM 환경에서 2048 은 너무 큼) |

---

## 3. 잠재적 메모리 누수 의심 위치 (요약)

§2.11 의 ★★★ 위험 3건:

### 누수 #1 — `_frame_extractions` 무한 list
- **파일**: `engine/analysis_buffer.py:201`
- **패턴**: `self._frame_extractions: list[dict[str, Any]] = []` + 매 30프레임 append (`analysis_buffer.py:566`)
- **방어**: `get_frame_extractions()` 가 호출 시 clear (`analysis_buffer.py:572`), 그러나 호출 누락 시 누적
- **메모리**: dict 당 ~50 KB (keypoints+bio+det) × 3,600 (60분) = **180 MB**
- **권장**: `_MAX_FRAME_EXTRACTIONS=7200` (2시간 cap) 또는 deque(maxlen=7200)

### 누수 #2 — `_motion_windows` dict key 누수
- **파일**: `engine/analysis_buffer.py:183, 326-330`
- **패턴**: `if pid not in self._motion_windows: self._motion_windows[pid] = deque(maxlen=30)`
- **방어**: 없음 — dict key (player_id) 가 player_tracker 가 만든 모든 ID 를 보관. PlayerTracker 가 `_remove_dead_tracks` 로 track 을 지워도 analysis_buffer 는 그 ID 의 deque 를 영원히 보관.
- **메모리**: 1게임 60분 동안 track 재발급으로 ID 수백~수천 개 가능. deque 빈 상태라도 key + RLock + deque 객체로 ~200 B/key × 1000 keys = **200 KB**. 작지만 누적
- **권장**: PlayerTracker remove_dead_tracks 시 `_motion_windows.pop(pid, None)` 호출

### 누수 #3 — FrameAligner `_buffers` 폭주 (특정 시나리오)
- **파일**: `infrastructure/preprocessing/frame_aligner.py:223,289`
- **패턴**: cam당 list 에 frame 누적, `MAX_ALIGNMENT_BUFFER=120` 도달 시 oldest pop
- **시나리오**: 카메라 1대 끊기면 정렬 실패 → 다른 7대 cam 의 buffer 가 빠른 속도로 채워짐. 정상 cam 은 120 frame × 5.93 MB = 712 MB/cam, 7 cam = **4.98 GB peak**.
- **권장**: drift > threshold 인 카메라는 aligner 에서 제외하거나, `MAX_ALIGNMENT_BUFFER` 를 30 으로 하향 (정상 sync 시 충분)

---

## 4. 최적화 가능 영역

| 우선순위 | 영역 | 예상 절감 | 작업 난이도 |
|---|---|---:|---|
| 🔴 P0 | `MAX_ALIGNMENT_BUFFER=120 → 30` (frame_aligner.py:45) | peak 4.98 GB → 1.24 GB | 1 줄 변경 |
| 🔴 P0 | `_frame_extractions` cap | 30분 운영 후 ~90 MB → ~10 MB | maxlen 추가 |
| 🟡 P1 | `_motion_windows` dead-track cleanup | 1게임당 ~200 KB | callback 등록 |
| 🟡 P1 | TRT workspace_size_mb 통일 (8GB VRAM → 512MB) | VRAM 1.5 GB → 0.5 GB | config 1개 |
| 🟡 P1 | `vitpose-l-wholebody.onnx` (1.18 GB) 미사용 weight 제거 | 디스크 1.18 GB | weights/ 삭제 |
| 🟢 P2 | `_appdata/tensorrt_cache` TTL cleanup | 디스크 1.36 GB → ~500 MB | 시작 시 정리 스크립트 |
| 🟢 P2 | Event detector 13개 `list[-max:]` 슬라이싱 → deque(maxlen) | GC churn 감소, 메모리 동일 | 13 파일 변경 |
| 🟢 P2 | `WebSocket._connections` heartbeat 좀비 정리 | 작음 | ping 로직 추가 |

---

## 5. 모니터링 권장

### 5.1 launcher 6 GB 임계치 평가

- 위치: `launcher.py:297` `alert_threshold_mb=6000.0`
- **현재 추정 정상 사용량 ~3.8 GB → 임계치까지 여유 2.2 GB**. 적정.
- 그러나 §3 누수 #1/#3 트리거되면 1~2 시간 내 도달 가능.

### 5.2 추가 모니터링 포인트

| 메트릭 | 위치 | 알람 임계 |
|---|---|---:|
| `len(_aligner._buffers[cam])` 모니터 | frame_aligner.py 에 stats property 추가 | > 30 |
| `len(_possession_frames)` | analysis_buffer.py:191 | > 1500 (cap 의 83 %) |
| `len(_frame_extractions)` | analysis_buffer.py:201 | > 3000 |
| `len(_motion_windows)` (player count) | analysis_buffer.py:183 | > 50 (코트당 10명 + 교체 20명 가정) |
| ffmpeg subprocess RSS (per camera) | launcher.py:323 children loop 에서 cam별 분리 | > 200 MB/cam |
| GPUManager snapshot | engine/gpu/gpu_manager.py:464 | utilization > 85 % |
| TRT engine cache size | `_appdata/tensorrt_cache` 디렉토리 | > 3 GB |
| `_ws_queue` size | engine/io/result_dispatcher.py:281 | > 400 (cap=500) |

### 5.3 모니터링 코드 위치 권장

`launcher.py:_monitor_process_memory` 가 30초마다 RSS 만 측정 → 누수 진단 부족.

**추가 권장**:
1. `engine_proc` 내부에서 5분마다 `analysis_buffer.__repr__()` + `result_dispatcher.ws_queue_size` 를 INFO 로그.
2. 메트릭 endpoint (`/api/v1/debug/memory`) 추가 — 위 표의 카운터 dump.
3. `tracemalloc.start()` 로 top10 allocation 5분 주기 dump (debug 모드 한정).

---

## 6. 비명시적 메모리 위험 (자유 추가)

### 6.1 PyTorch `torch.cuda.empty_cache()` 미호출
- yolov8_backend, vitpose_backend 등이 PyTorch 로 모델 로드. 모델 unload 후 `empty_cache()` 호출 안 하면 VRAM fragmentation 으로 같은 모델 재로드 시 OOM 가능.
- **확인 위치**: `tensorrt_pool._unload_entry` (line 353-377) — `entry.engine_handle.release()` 만 호출, `torch.cuda.empty_cache()` 없음.

### 6.2 OpenCV `cv2.VideoCapture` 누수 (file 모드)
- `video_decoder.py:886` `cv2.VideoCapture(file_path)` — `close()` 가 `_cap.release()` 호출 (line 947) ✅
- 그러나 `open()` 중간 실패 분기 (line 909) 에서 `cap.release()` 가 호출되는지 확인 필요 → 코드상 OK.

### 6.3 numpy `frombuffer().copy()` 매 frame 할당
- `video_decoder.py:1311` `np.frombuffer(bytes(data), ...).reshape(h,w,3)`
- `data: bytearray()` 가 매 frame 새로 alloc (line 1251). reader 루프가 GIL 없이 도는 bytearray → numpy copy → bytearray 폐기. 정상 GC.
- **위험**: `bytes(data)` 가 한 번 더 복사 (불필요) → 5.93 MB × 30 fps × 8 cam = **1.4 GB/s allocator pressure**. CPython allocator 가 잘 재사용하지만 fragmentation 위험.
- **권장**: `np.frombuffer(memoryview(data).tobytes(), ...)` 대신 `np.frombuffer(bytes(memoryview(data)), ...)` 또는 stdout 에서 직접 numpy `readinto()` 사용.

### 6.4 logging handler 핸들 누수
- `video_decoder.py:1038` `open(_stderr_path, "w", encoding="utf-8", buffering=1)` — 카메라당 1 핸들. 카메라 reconnect 시 기존 fp close 후 새 open 확인 필요 — `_start_ffmpeg_pipe` 호출 시 매번 새 open. `_stop_ffmpeg_pipe` 에서 close 보장 (line 1098-1103). **단**, ffmpeg crash 후 reader_loop 가 EOF 처리 (line 1268-1283) 하면서 `_stop_ffmpeg_pipe` 가 호출되는지 확인 필요. 검토 결과 reader 는 return 만 하고 close 호출은 외부 (`close()` 또는 reconnect) 에 의존. **카메라 자동 재연결 시 fp 누수 가능**.

### 6.5 ThreadPoolExecutor 종료 누락
- `infrastructure/preprocessing/video_decoder.py:337-340` `with ThreadPoolExecutor(...) as pool` ✅
- `engine/io/frame_ingestion.py:232,251` `with ThreadPoolExecutor(...) as pool` ✅
- `api_server/services/highlight_clip_service.py:78` `self._executor = ThreadPoolExecutor(...)` — `with` 아닌 멤버 변수. **shutdown 누락 가능** — service 소멸 시 `_executor.shutdown(wait=True)` 명시 호출 필요. 코드 검색 후 shutdown 코드 없으면 누수.

### 6.6 ffmpeg subprocess.PIPE stdout 미소비 시 dead-lock
- `video_decoder.py:1044` `stdout=subprocess.PIPE` — 64 KB OS pipe buffer 차면 ffmpeg 가 block. reader_thread 가 죽으면 ffmpeg 도 hang.
- 현재 reader_thread daemon=True (line 1179) — main thread 죽으면 함께 종료 ✅
- 그러나 reader_loop 가 exception 으로 죽고 ffmpeg 는 살아있는 시나리오: ffmpeg pipe buffer 가 가득 차면 ffmpeg 가 stuck → 카메라 슬롯 점유 + 메모리 소량 누적.
- **권장**: reader_loop 의 try/except 외부에 reset 로직 추가.

### 6.7 `GPUManager._allocations` dict 한도 100
- `engine/gpu/gpu_manager.py:141` `_MAX_ALLOCATIONS=100` — emergency_cleanup 이 LRU 해제 하지만 정상 운영에서 100 도달은 비현실적 (모델 3종이 전부).

### 6.8 ARP / mDNS / ONVIF discovery 의 임시 dict
- `_session_backup` 디렉토리에 ONVIF / mDNS 백업 — 정작 활성 코드는 _plan_*.md 만 있고 코드 미통합. 메모리 영향 0.

### 6.9 ApiServer FastAPI request 라이프사이클
- Pydantic schema 검증 — 인스턴스 짧게 살고 GC. 누수 없음.
- middleware `_MAX_CONTENT_LENGTH=100MB` (`api_server/middleware/request_validator.py:33`) — 단일 request body 한도.

---

## 7. 결론

1. **현재 코드는 launcher 6 GB 임계치를 정상 운영 시 절대 못 친다** (추정 3.8~4.5 GB). 어제 `_possession_frames=deque(maxlen=1800)` 패치로 가장 큰 위험 1건 해소.
2. **그러나 30분 이상 LIVE 가동 + 카메라 1대 끊김 시나리오 에서는 `FrameAligner._buffers` 가 GB 단위로 폭주 가능** (5.7 GB 이론 최대). 이 패치가 다음 우선순위.
3. **`_frame_extractions` + `_motion_windows` 두 자료구조에 명시적 cap 부재** — 60분 게임 1회 운영 후 ~200 MB 추가 누적.
4. **VRAM 은 모델 + workspace 합산 2.5 GB 안팎으로 안정적**. workspace_size_mb config 일원화로 0.5~1 GB 절감 여지.
5. **디스크 누적**: `_appdata/tensorrt_cache` 1.36 GB / `weights/vitpose-l-wholebody.onnx` 1.18 GB 미사용 — 합 ~2.5 GB 회수 가능.

다음 작업 후보 (우선순위 순):
1. `MAX_ALIGNMENT_BUFFER=120 → 30` 하향 + 카메라 drift watchdog
2. `_frame_extractions` deque(maxlen=7200) 변경
3. `_motion_windows` dead-track cleanup hook
4. TRT workspace_size_mb config 단일화 (gpu_config.yaml 우선)
5. `weights/vitpose-l-wholebody.onnx` 제거
6. `_appdata/tensorrt_cache` TTL cleanup
