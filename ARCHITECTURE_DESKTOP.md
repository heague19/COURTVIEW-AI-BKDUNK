# COURTVIEW Desktop 아키텍처

> **버전**: 1.0.0
> **최종 수정**: 2026-03-20
> **목적**: 로컬 GPU 기반 경기 분석 + AI 심판 시스템 (B2B 렌탈 노트북)

---

## 1. 프로젝트 개요

### 1.1 목표

| 항목 | 수치 |
|------|------|
| 정확도 | 92%+ (로컬 GPU, 전문 하드웨어) |
| FPS | 60fps (4-8대 카메라) |
| 지연시간 | <50ms |
| 오프라인 | 완전 지원 |
| 배포 | PyInstaller 네이티브 (Windows/macOS/Linux) |

### 1.2 핵심 기능

| 기능 | 상태 |
|------|------|
| 경기 분석 (4-8대 카메라) | ✅ 핵심 |
| AI 심판 (바이올레이션 12종 + 파울 11종 + 판정엔진 + 데이터추출) | ✅ 핵심 |
| 경기 관리/기록원 (교체/파울/타임아웃/공식기록지) | ✅ 포함 |
| 전술 분석 (공격/수비/개인/라인업/공간) | ✅ 포함 |
| 하이라이트 / 슛 위치 분석 | ✅ 포함 |
| 비디오 편집 / 필름 세션 | ✅ 포함 |
| 코칭 인텔리전스 (실시간 추천) | ✅ 포함 |
| 데이터셋 추출 (자체 모델 학습용) | ✅ 포함 |
| 생체역학 분석 (biomechanics) | ✅ 포함 — **규칙 기반 모듈** (ML 미사용, 2026-04-18 결정) |
| 훈련 분석 / 정답 영상 비교 | ❌ 앱 전용 |
| 자가 학습 시스템 | ❌ 별도 프로그램 |

### 1.3 앱 서버와의 차이

| 구분 | 앱 서버 (Cloud) | Desktop (렌탈) |
|------|-----------------|----------------|
| 배포 | AWS 클라우드 | 로컬 노트북 (렌탈) |
| 사용자 | B2C (개인, 앱) | B2B (농구단, 학교, 대회) |
| GPU | 클라우드 공유 | 로컬 전용 (RTX 4080+) |
| FPS | 10-15fps | **60fps** |
| 지연시간 | 200-500ms | **<50ms** |
| 카메라 | 4대 | **4-8대** |
| 동기화 | ±50ms (네트워크) | **±1ms (하드웨어)** |
| 오프라인 | ❌ | ✅ |
| DB | PostgreSQL | **없음** (JSON → 백엔드 반환) |

---

## 2. 설계 전략

### 2.1 "Full Infrastructure, Focused Features"

```
인프라 (Layer 0): 앱 서버와 동일하게 유지 (축소 ❌)
  - 렌탈 서비스는 더 높은 안정성 요구
  - 로컬 GPU 관리 (발열, 메모리)
  - 에러 복구 필수 (네트워크 없이 동작)
  - 멀티카메라 하드웨어 동기화

기능 레이어: 경기 분석 + AI 심판에 집중
  ✅ detection, pose_estimation, biomechanics — 전체 포함
  ✅ motion_analysis — 경기용 5-Tier (감지/분류/위상분석/폼평가/비교)
  ✅ game_analysis — 강화 (26서브모듈, 전력분석원+기록원 완전 대체)
  ✅ ai_referee — Desktop 핵심 (바이올레이션 12종, 파울 11종, 판정엔진, 데이터추출)
  ❌ learning_system — 별도 프로그램
```

### 2.2 Desktop 전용 최적화

| 항목 | 설명 |
|------|------|
| GPU 극대화 | TensorRT FP16, 배치 32, CUDA 멀티 스트림 |
| 2-Stage Pose | YOLOv8x-Pose (상시 17kp) + ViTPose-B (트리거 133kp) |
| 오프라인 | 네트워크 없이 완전 분석, 로컬 SSD 저장 |
| 멀티카메라 | 하드웨어 동기화 ±1ms, 8대 동시 처리 |
| 발열 관리 | 노트북 GPU 온도 모니터링 + 자동 스로틀링 |

---

## 3. 전체 구조

### 3.0 레이어 간 데이터 플로우 (전체 요약)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        📹 8대 카메라 (RTSP/FILE)                         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │  BGR 프레임 (±1ms 동기화)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│   Layer 8: engine/                                                       │
│   ├─ io/frame_ingestion → 동기화 + 배치 수집                             │
│   └─ gpu/batch_accumulator → 8프레임 GPU 텐서                            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼  🔴 CUDA Stream #1 (매 프레임 16ms)
┌─────────────────────────────────────────────────────────────────────────┐
│   Layer 1: detection/      ball + player + hoop (CV-BBox 통합)           │
│   Layer 2: pose_estimation Stage1 YOLOv8-Pose 17kp (전체 프레임)          │
│                           ↓                                              │
│   engine/pipeline/fusion/ detection_fusion + pose_fusion (삼각측량)      │
│                           ↓                                              │
│   detection/player_detection/multiview_tracker (Geometry 영구 ID)        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │  SceneDetection + Skeleton3D + PlayerTrack
                                     ▼  🔴 매 프레임 6ms 예산
┌─────────────────────────────────────────────────────────────────────────┐
│   Layer 3: biomechanics/    관절 각도/속도/가속도 + 힘/에너지/균형        │
│                             (규칙 기반 계산, ML 미사용)                  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │  FrameAngles/Velocities/Forces/...
                                     ▼  🟡 Cadence 판단
┌─────────────────────────────────────────────────────────────────────────┐
│   engine/orchestrator/cadence_scheduler                                   │
│   ├─ 🔴 FRAME      possession / score / dead_ball / clock                │
│   ├─ 🟠 EVENT      shot/foul/rebound 트리거 시 Stage2 ViTPose 133kp      │
│   ├─ 🟡 POSSESSION 점유 종료 → 전술/개인/공간/매치업 분석                │
│   ├─ 🟢 PERIOD     쿼터 종료 → 흐름/로테이션/스플릿                      │
│   └─ 🔵 POSTGAME   경기 종료 → 리포트/영상/스카우팅/데이터추출            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                 ┌───────────────────┼───────────────────┐
                 ▼                   ▼                   ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│  Layer 4:          │  │  Layer 5:          │  │  Layer 6:          │
│  motion_analysis/  │  │  game_analysis/    │  │  ai_referee/       │
│  5-Tier            │  │  5-Phase 130파일   │  │  23규칙 + 판정엔진 │
│  감지→분류→분절   │  │  이벤트→통계→분석 │  │  FIBA/NBA/KBL/NBL │
│  →평가→비교       │  │  →출력→추출       │  │  다각도 교차 검증 │
└─────────┬──────────┘  └─────────┬──────────┘  └─────────┬──────────┘
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│   Layer 7: feedback_system/                                              │
│   ├─ coach/     동작 폼 + 생체역학 피드백 (motion/bio DTO 입력)          │
│   └─ analysis/  전술/수비/개인/공간 피드백 (game/tactical DTO 입력)      │
│                        ↓                                                  │
│         report/ CoachReportGenerator + GameReportGenerator               │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │  FeedbackResult + GameReport
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│   Layer 9: api_server/                                                   │
│   ├─ REST      POST /game/analyze, GET /referee/decisions, ...          │
│   ├─ WebSocket 실시간 진행률 + 판정 알림 (ws://localhost:8000/ws)        │
│   └─ services/ cloud_sync_service → Backend Cloud (JSON 전송)           │
└─────────────────────────────────────────────────────────────────────────┘

주요 DTO 흐름:
  geometry_dto → detection_dto → pose_dto → biomechanics_dto →
  motion_dto → game_dto/tactical_dto → referee_dto → feedback_dto
```

### 3.1 계층 구조

```
Layer 0   shared/              공통 어휘 (constants, dto, exceptions, interfaces, protocols)
Layer 0   core_foundation/     핵심 기반 (config, monitoring, registry, resilience, security)
Layer 0   infrastructure/      인프라 서비스 (cache, events, multi_camera, preprocessing, storage, validation)
Layer 0   utils/               공통 유틸리티 (18파일)
Layer 0.5 configs/             Desktop 전용 YAML 설정
Layer 1   detection/           객체 감지 (ball, court, player, hoop)
Layer 2   pose_estimation/     포즈 추정 (2-Stage: YOLOv8x-Pose + ViTPose-B)
Layer 3   biomechanics/        생체역학 (kinematics, dynamics, anthropometry, standards)
Layer 4   motion_analysis/     동작 분석 (감지→분류→위상→폼평가→비교)
Layer 5   game_analysis/       경기 분석 (26서브모듈)
Layer 6   ai_referee/          AI 심판 (rules, violations, fouls, decisions, data_extraction)
Layer 7   feedback_system/     경기 피드백 (analysis, coach, templates, report)
Layer 8   engine/              분석 파이프라인 오케스트레이션 (26파일, 6서브모듈)
Layer 9   api_server/          로컬 API 서버
```

### 3.2 폴더 구조

```
📁 COURTVIEW_DESK/
│
├── 📁 shared/                         # [Layer 0] 공통 어휘
│   ├── 📁 constants/                  # 26개 파일 — Enum, 상수값
│   │   ├── ball_constants.py
│   │   ├── biomechanics_constants.py
│   │   ├── camera_constants.py
│   │   ├── court_constants.py
│   │   ├── error_codes.py
│   │   ├── event_types.py
│   │   ├── feedback_constants.py
│   │   ├── fusion_constants.py
│   │   ├── game_management_constants.py
│   │   ├── game_rule_constants.py
│   │   ├── geometry_constants.py
│   │   ├── hoop_constants.py
│   │   ├── localization.py
│   │   ├── matching_constants.py
│   │   ├── occlusion_constants.py
│   │   ├── ocr_constants.py
│   │   ├── player_constants.py
│   │   ├── pose_constants.py
│   │   ├── referee_decision_constants.py
│   │   ├── referee_rule_constants.py
│   │   ├── reid_constants.py
│   │   ├── stats_constants.py
│   │   ├── status_codes.py
│   │   ├── tactical_constants.py
│   │   ├── tracking_constants.py
│   │   └── video_constants.py
│   │
│   ├── 📁 dto/                        # 26개 파일 — 모듈 간 통신 계약서 (Pydantic)
│   │   ├── geometry_dto.py            # 2D/3D 기본형 (Point, Vector, BBox, Polygon)
│   │   ├── video_dto.py               # 비디오 메타데이터
│   │   ├── camera_dto.py              # 카메라 정보/설정
│   │   ├── calibration_dto.py         # 캘리브레이션 파라미터
│   │   ├── detection_dto.py           # 객체 감지 결과
│   │   ├── tracking_dto.py            # 객체 추적
│   │   ├── occlusion_dto.py           # 오클루전 감지/해결
│   │   ├── reid_dto.py                # Re-ID 특징/매칭
│   │   ├── pose_dto.py                # 포즈/스켈레톤
│   │   ├── ball_dto.py                # 공 감지/궤적
│   │   ├── ocr_dto.py                 # 등번호 OCR
│   │   ├── scene_dto.py               # 3D 씬
│   │   ├── player_dto.py              # 선수 식별/관리
│   │   ├── biomechanics_dto.py        # 운동학/동역학/인체측정
│   │   ├── motion_dto.py              # 동작 분류 결과
│   │   ├── game_management_dto.py     # 교체/파울/타임아웃/시계/공식기록지
│   │   ├── prediction_dto.py          # 예측 모델 (WP, EPV, xFG%)
│   │   ├── tactical_dto.py            # 전술 분석 결과
│   │   ├── scouting_dto.py            # 스카우팅/게임플랜
│   │   ├── media_dto.py               # 비디오 편집/필름 세션
│   │   ├── dataset_dto.py             # 데이터셋 추출
│   │   ├── pipeline_dto.py            # 파이프라인 요청/응답/진행률
│   │   ├── feedback_dto.py            # 피드백/리포트 + VideoClipReference, CausalFactor
│   │   ├── game_dto.py                # 경기 통계/이벤트/하이라이트
│   │   └── referee_dto.py             # AI 심판 판정/리뷰
│   │
│   ├── 📁 exceptions/                 # 5개 파일
│   │   ├── base_exception.py          # CourtViewException 기반 클래스
│   │   ├── analysis_exceptions.py     # 영상/감지/포즈/동작/심판 예외
│   │   ├── validation_exceptions.py   # 입력/포맷/스키마 예외
│   │   ├── infrastructure_exceptions.py # 캐시/스토리지/스트림 예외
│   │   └── desktop_exceptions.py      # GPU/하드웨어/멀티카메라 예외
│   │
│   ├── 📁 interfaces/                 # 4개 파일
│   │   ├── analyzer_interface.py
│   │   ├── detector_interface.py
│   │   ├── storage_interface.py
│   │   └── game_interface.py
│   │
│   └── 📁 protocols/                  # 2개 파일
│       ├── camera_protocol.py
│       └── storage_protocol.py
│
├── 📁 core_foundation/               # [Layer 0] 핵심 기반
│   ├── 📁 config/
│   │   ├── loader.py                  # YAML/ENV 로더
│   │   ├── validator.py               # Pydantic 검증
│   │   ├── settings.py                # 전역 설정 (Singleton)
│   │   └── watcher.py                 # 설정 변경 감시
│   │
│   ├── 📁 monitoring/
│   │   ├── logger.py                  # Loguru 기반 중앙 로깅
│   │   ├── error_tracker.py           # 에러 추적/집계
│   │   ├── metrics.py                 # 메트릭 (GPU/Camera/System 포함)
│   │   ├── profiler.py                # CPU/메모리/GPU 프로파일링
│   │   └── health_checker.py          # 헬스 체크 (GPU/Camera 포함)
│   │
│   ├── 📁 registry/
│   │   ├── service_registry.py        # 서비스 레지스트리
│   │   ├── model_registry.py          # 모델 레지스트리
│   │   ├── dependency_injector.py     # DI 컨테이너
│   │   ├── pipeline_coordinator.py    # 파이프라인 오케스트레이션
│   │   └── rule_set_manager.py        # 리그별 규칙 관리 (FIBA/NBA/KBL/NBL)
│   │
│   ├── 📁 resilience/
│   │   ├── circuit_breaker.py         # 서킷 브레이커 (타임아웃 내장)
│   │   └── retry_mechanism.py         # 재시도 (Exponential 백오프)
│   │
│   └── 📁 security/
│       ├── license_validator.py       # 라이선스 검증 (하드웨어 ID, 렌탈 핵심)
│       ├── secret_manager.py          # 시크릿 관리 (Env/File 기반)
│       └── audit_logger.py            # 감사 로깅 (체인 해싱 무결성)
│
├── 📁 infrastructure/                 # [Layer 0] 인프라 (로컬 최적화)
│   ├── 📁 cache/
│   │   ├── cache_manager.py           # 캐시 수명주기
│   │   ├── cache_strategies.py        # LRU/TTL 퇴거 전략
│   │   └── model_cache.py             # 모델 추론 결과 캐시
│   │
│   ├── 📁 events/
│   │   ├── event_bus.py               # 인메모리 pub/sub
│   │   ├── event_handlers.py          # 이벤트 핸들러
│   │   └── event_types.py             # 이벤트 타입 정의
│   │
│   ├── 📁 multi_camera/
│   │   ├── camera_manager.py          # 4-8대 카메라 수명주기
│   │   ├── camera_calibrator.py       # 내부/외부 파라미터 캘리브레이션
│   │   ├── camera_config.py           # 카메라별 설정
│   │   └── coordinate_transformer.py  # 2D→3D 좌표 변환
│   │
│   ├── 📁 preprocessing/
│   │   ├── video_decoder.py           # 비디오 디코딩 (FFmpeg/OpenCV)
│   │   ├── frame_extractor.py         # 프레임 추출
│   │   ├── frame_aligner.py           # 멀티카메라 프레임 정렬
│   │   ├── multi_video_sync.py        # 다중 영상 동기화 (±1ms)
│   │   ├── video_normalizer.py        # 해상도/색공간 정규화
│   │   ├── adaptive_sampling.py       # 적응형 프레임 샘플링
│   │   └── video_type_classifier.py   # 입력 영상 타입 분류
│   │
│   ├── 📁 storage/
│   │   ├── local_storage.py           # SSD 파일 관리
│   │   ├── video_storage.py           # 비디오 전용 저장소
│   │   ├── format_detector.py         # 비디오 포맷 감지
│   │   └── metadata_extractor.py      # 비디오 메타데이터 추출
│   │
│   └── 📁 validation/
│       ├── format_validator.py        # 비디오 포맷 검증
│       ├── schema_validator.py        # API 요청 스키마 검증
│       └── data_quality_checker.py    # 프레임 품질 체크
│
├── 📁 utils/                          # [Layer 0] 공통 유틸리티 (18파일)
│   ├── math_utils.py                  # 벡터, 각도, 통계, 보간, 거리
│   ├── geometry_utils.py              # 좌표변환, bbox, 다각형, 코트존
│   ├── time_utils.py                  # 프레임↔시간, 경기시간, FPS
│   ├── video_utils.py                 # 프레임추출, 색상변환, 비디오쓰기
│   ├── kalman_utils.py                # 2D/3D 칼만 필터, EKF
│   ├── physics_utils.py               # 중력, 항력, 마그누스, 궤적예측
│   ├── interpolation_utils.py         # 스플라인, 베지어, 궤적보간
│   ├── image_utils.py                 # 크롭, 리사이즈, 히스토그램, 텐서변환
│   ├── validation_utils.py            # 타입/범위/도메인 검증
│   ├── rotation_utils.py              # 3D 회전 (쿼터니언, 로드리게스, 오일러)
│   ├── pose_utils.py                  # 포즈/스켈레톤 (COCO-17, OKS, Procrustes)
│   ├── sequence_utils.py              # 시계열 (DTW, 위상분할, 피크검출)
│   ├── statistical_utils.py           # 고급 통계 (분포, 이상값, 신뢰구간)
│   ├── basketball_geometry.py         # 농구 기하학 (7리그 코트규격, 슛궤적, 림통과)
│   ├── camera_calibration_utils.py    # 카메라 캘리브레이션 (삼각측량, 에피폴라)
│   ├── feature_matching_utils.py      # 특징점 매칭 (ORB/SIFT, FLANN)
│   └── heatmap_utils.py               # 히트맵 처리 (피크검출, 스켈레톤디코딩)
│
├── 📁 configs/                        # [Layer 0.5] Desktop 전용 YAML 설정
│   ├── 📁 base/
│   │   ├── base_config.yaml
│   │   ├── gpu_config.yaml
│   │   └── camera_config.yaml
│   ├── 📁 detection/
│   │   ├── ball_detection.yaml
│   │   ├── court_detection.yaml
│   │   ├── player_detection.yaml
│   │   └── hoop_detection.yaml
│   ├── 📁 pose/
│   │   ├── yolov8.yaml                # Stage 1
│   │   ├── vitpose.yaml               # Stage 2
│   │   └── tensorrt.yaml              # TensorRT 엔진 설정
│   ├── 📁 biomechanics/
│   │   ├── kinematics.yaml
│   │   └── dynamics.yaml
│   ├── 📁 analysis/
│   │   ├── motion_analysis.yaml
│   │   ├── shooting_criteria.yaml     # 슈팅 폼 평가 기준
│   │   └── dribble_criteria.yaml      # 드리블 폼 평가 기준
│   ├── 📁 game_analysis/
│   │   ├── event_detection.yaml
│   │   ├── statistics.yaml
│   │   ├── shot_location.yaml
│   │   ├── highlight.yaml
│   │   └── tactical_analysis.yaml
│   ├── 📁 ai_referee/
│   │   ├── fiba_rules.yaml
│   │   ├── kbl_rules.yaml
│   │   ├── nba_rules.yaml
│   │   ├── nbl_rules.yaml
│   │   ├── violation_thresholds.yaml
│   │   ├── foul_criteria.yaml
│   │   ├── shooting_foul_criteria.yaml
│   │   ├── flagrant_criteria.yaml
│   │   ├── technical_criteria.yaml
│   │   └── data_extraction.yaml          # 추출기별 버퍼/임계치/샘플링 설정
│   ├── 📁 feedback/
│   │   ├── game_feedback.yaml
│   │   ├── tactical_feedback.yaml
│   │   └── referee_feedback.yaml
│   ├── 📁 desktop/
│   │   ├── performance.yaml           # 60fps, TensorRT, 배치 크기
│   │   ├── offline.yaml               # 오프라인 모드
│   │   └── hardware_sync.yaml         # Genlock 하드웨어 동기화
│   ├── 📁 environments/
│   │   ├── local.yaml
│   │   ├── windows.yaml
│   │   ├── macos.yaml
│   │   └── linux.yaml
│   └── 📁 calibration/                   # 카메라별 호모그래피 (설치 시 자동 생성)
│       ├── cam_0.json                    # cam1 영상 매핑 (picker 규약)
│       ├── cam_1.json                    # cam2 영상 매핑
│       ├── ...                           # cam_2 ~ cam_6
│       ├── cam_7.json                    # cam8 영상 매핑
│       └── pixel_points.json             # 클릭한 픽셀+코트 좌표 원본
│
├── 📁 detection/                      # [Layer 1] 객체 감지 (4서브모듈)
│   │
│   ├── 📁 ball_detection/
│   │   ├── ball_detector.py           # 패턴 Primary + YOLO Accelerator 하이브리드
│   │   ├── ball_tracker.py            # Kalman + ByteTrack 추적 (멀티카메라 융합)
│   │   ├── ball_state.py              # 소유/슛/패스/루즈볼/데드/리바운드 상태 판별
│   │   └── 📁 data_extraction/
│   │       ├── ball_bbox_extractor.py
│   │       ├── trajectory_extractor.py
│   │       ├── hard_negative_extractor.py
│   │       ├── occlusion_sample_extractor.py
│   │       └── temporal_sequence_extractor.py
│   │
│   ├── 📁 player_detection/
│   │   ├── models.py                  # 감지 전용 데이터 클래스
│   │   ├── player_detector.py         # 패턴+YOLO 선수/심판/코치 감지
│   │   ├── team_classifier.py         # 유니폼 색상 기반 팀 분류
│   │   ├── jersey_ocr.py              # 등번호 OCR (다중 뷰 투표 + 배치)
│   │   ├── reid_module.py             # Re-Identification (보조, MV트래커 주력)
│   │   ├── player_tracker.py          # 단일카메라 IoU/Kalman 트래커
│   │   ├── player_id_manager.py       # (legacy) OCR+ReID+추적 융합
│   │   ├── multiview_tracker.py       # ★ 8대 카메라 Geometry 영구 ID 트래커 (주력, 2026-04-20)
│   │   └── 📁 data_extraction/
│   │       ├── player_bbox_extractor.py
│   │       ├── team_uniform_extractor.py
│   │       ├── jersey_digit_extractor.py
│   │       └── reid_appearance_extractor.py
│   │
│   └── 📁 hoop_detection/
│       ├── hoop_detector.py           # YOLOv8 + Hough Circle 골대/림/백보드
│       ├── net_analyzer.py            # 네트 움직임 분석 (득점 판정)
│       └── 📁 data_extraction/
│           ├── hoop_bbox_extractor.py
│           └── net_motion_extractor.py
│
├── 📁 pose_estimation/               # [Layer 2] 2-Stage Pose Pipeline
│   ├── 📁 backends/
│   │   ├── base_backend.py            # 추상 기반 클래스
│   │   ├── yolov8_backend.py          # Stage 1: 상시 17kp (TensorRT FP16)
│   │   ├── vitpose_backend.py         # Stage 2: 이벤트 트리거 133kp (TensorRT FP16)
│   │   └── tensorrt_engine.py         # ONNX→TRT 엔진 빌더/캐싱
│   ├── keypoint_types.py              # COCO 17kp + WholeBody 133kp
│   ├── processing.py                  # 정규화 + 스무딩 + 필터링
│   ├── validation.py                  # 해부학적 검증
│   └── 📁 data_extraction/
│       ├── keypoint_extractor.py      # COCO 17kp → YOLOv8-Pose 재학습
│       ├── pose_sequence_extractor.py # 시퀀스 → LSTM/Transformer 학습
│       └── wholebody_keypoint_extractor.py  # 133kp → ViTPose 재학습
│
├── 📁 biomechanics/                   # [Layer 3] 생체역학
│   ├── 📁 kinematics/
│   │   ├── joint_angle_calculator.py
│   │   ├── velocity_analyzer.py
│   │   ├── acceleration_analyzer.py
│   │   ├── trajectory_analyzer.py
│   │   ├── body_orientation.py
│   │   └── motion_pattern.py
│   ├── 📁 dynamics/
│   │   ├── force_estimator.py
│   │   ├── momentum_calculator.py
│   │   ├── energy_analyzer.py
│   │   ├── balance_analyzer.py
│   │   └── impact_analyzer.py
│   ├── 📁 anthropometry/
│   │   ├── body_segment.py
│   │   ├── age_gender_adapter.py
│   │   └── proportion_calculator.py
│   └── 📁 standards/
│       ├── youth_standards.py
│       ├── teen_standards.py
│       ├── adult_standards.py
│       └── senior_standards.py
│
├── 📁 motion_analysis/               # [Layer 4] 동작 분석 (5-Tier, 5서브모듈, ~20파일)
│   ├── models.py                      # 공통 DTO/dataclass
│   │
│   ├── 📁 detection/                  # Tier 1: 동작 감지 (WHEN — 언제 발생하는가)
│   │   ├── shot_detector.py           # 슈팅 동작 감지 (공 궤적 + 자세 + 골대)
│   │   ├── dribble_detector.py        # 드리블 감지 + 13유형 분류
│   │   ├── pass_detector.py           # 패스 감지 + 11유형 분류
│   │   ├── movement_detector.py       # 이동/커팅 감지 + 12유형 분류
│   │   └── rebound_detector.py        # 리바운드 동작 감지
│   │
│   ├── 📁 classification/            # Tier 2: 동작 분류 (WHAT — 무슨 동작인가)
│   │   ├── action_classifier.py       # 전체 동작 분류 (shot/dribble/pass/defense/movement)
│   │   ├── shot_classifier.py         # 슛 세부 분류 (layup/jumpshot/hook/dunk)
│   │   └── dribble_classifier.py      # 드리블 세부 분류 (crossover/behind/hesitation)
│   │
│   ├── 📁 phase_analysis/            # Tier 3: 단계 분석 (PHASE — AI 심판 핵심 의존)
│   │   ├── shot_phase_analyzer.py     # wind-up → release → follow-through
│   │   └── dribble_phase_analyzer.py  # gather → control → execute
│   │
│   ├── 📁 form_evaluation/           # Tier 4: 폼 평가 (HOW WELL — 경기 중 폼 분석)
│   │   ├── shooting_form_evaluator.py # 슈팅 폼 정확도 + 피드백
│   │   ├── dribble_form_evaluator.py  # 드리블 폼 정확도 + 피드백
│   │   ├── shooting_criteria.py       # 슈팅 기준 (각도/타이밍/릴리스)
│   │   └── dribble_criteria.py        # 드리블 기준 (높이/리듬/핸들)
│   │
│   └── 📁 comparison/                # Tier 5: 비교 분석 (VS — 정답 대비 비교)
│       └── form_comparator.py         # 정답 영상 vs 사용자 동작 비교
│
├── 📁 game_analysis/                  # [Layer 5] 경기 분석 (5그룹, 27서브모듈)
│   │
│   │  ══ Phase 1: game_state/ — 경기 상태 (3모듈) ══
│   │
│   ├── 📁 game_state/
│   │   ├── 📁 game_management/            # 1A: 기록원 대체 (6파일)
│   │   │   ├── substitution_manager.py    # 교체 관리 + 출전시간 자동 계산
│   │   │   ├── foul_manager.py            # 개인/팀 파울 누적 + 보너스 상태 전환
│   │   │   ├── timeout_manager.py         # 타임아웃 잔여 추적 (리그별 규칙)
│   │   │   ├── clock_manager.py           # 경기/슛 클락 + 게임 상태 머신
│   │   │   ├── record_corrector.py        # 스탯 수정 이력 + 무결성 검증
│   │   │   └── official_format_exporter.py # 공식 기록지 형식 출력 (FIBA/KBL/NBA/NBL)
│   │   │
│   │   ├── 📁 event_detection/            # 1B: 원시 이벤트 감지 (16파일)
│   │   │   ├── shot_event_detector.py     # 슛 이벤트 (필드골)
│   │   │   ├── free_throw_detector.py     # 자유투 이벤트
│   │   │   ├── score_detector.py          # 득점
│   │   │   ├── rebound_detector.py        # 리바운드
│   │   │   ├── assist_detector.py         # 어시스트
│   │   │   ├── block_detector.py          # 블록
│   │   │   ├── steal_detector.py          # 스틸
│   │   │   ├── turnover_detector.py       # 턴오버 (18종 분류)
│   │   │   ├── foul_detector.py           # 파울 접촉 감지 (판정은 ai_referee)
│   │   │   ├── possession_tracker.py      # 점유 추적
│   │   │   ├── dead_ball_detector.py      # 데드볼 감지
│   │   │   ├── screen_detector.py         # 스크린/픽 이벤트
│   │   │   ├── fast_break_detector.py     # 속공 이벤트
│   │   │   ├── drive_detector.py          # 드라이브(돌파) 이벤트
│   │   │   ├── box_out_detector.py        # 박스아웃 감지
│   │   │   └── jump_ball_detector.py      # 점프볼 감지
│   │   │
│   │   └── 📁 live_workspace/             # 1C: 실시간 이벤트 검증/보정 (3파일)
│   │       ├── live_event_validator.py    # AI 감지 이벤트 실시간 검증 (신뢰도 기반)
│   │       ├── manual_event_tagger.py     # 수동 이벤트 추가/태깅
│   │       └── correction_sync.py         # 보정 동기화 + 증분 재계산 트리거
│   │
│   │  ══ Phase 2: stats/ — 통계·예측 (2모듈) ══
│   │
│   ├── 📁 stats/
│   │   ├── 📁 statistics/                 # 통계 집계 (7파일)
│   │   │   ├── basic_stats.py             # 기본 스탯 (PTS, REB, AST...)
│   │   │   ├── advanced_stats.py          # 고급 스탯 (PER, TS%, USG%...)
│   │   │   ├── shot_chart.py              # 슛 차트
│   │   │   ├── player_tracker_stats.py    # 선수 트래킹 스탯
│   │   │   ├── team_stats_aggregator.py   # 팀 단위 통계 집계
│   │   │   ├── possession_stats.py        # PPP, 점유 효율
│   │   │   └── four_factors.py            # Dean Oliver Four Factors
│   │   │
│   │   └── 📁 predictive_models/          # 예측/확률 모델 (4파일)
│   │       ├── win_probability.py         # 실시간 승리 확률 (WP/WPA)
│   │       ├── expected_possession_value.py # 점유별 기대 득점 (EPV)
│   │       ├── shot_quality_model.py      # 슛 품질 모델 (xFG%)
│   │       └── lineup_projection.py       # 라인업 넷레이팅 예측
│   │
│   │  ══ Phase 3: analysis/ — 분석 (3서브그룹, 12모듈) ══
│   │
│   ├── 📁 analysis/
│   │   │
│   │   ├── 📁 team/                       # 팀 전술 공수 (4모듈)
│   │   │   ├── 📁 tactical_analysis/      # 공격 전술 (6파일)
│   │   │   │   ├── screen_analyzer.py     # 스크린/PnR 분석
│   │   │   │   ├── fast_break_analyzer.py # 속공 분석
│   │   │   │   ├── set_play_recognizer.py # 세트 플레이 인식
│   │   │   │   ├── passing_network.py     # 패싱 네트워크
│   │   │   │   ├── possession_analyzer.py # 점유 분석
│   │   │   │   └── turnover_analyzer.py   # 턴오버 심층 분석
│   │   │   │
│   │   │   ├── 📁 defensive_analysis/     # 수비 분석 (5파일)
│   │   │   │   ├── defense_type_classifier.py # 수비 유형 (맨투맨/존)
│   │   │   │   ├── defensive_rotation.py  # 수비 로테이션
│   │   │   │   ├── box_out_analyzer.py    # 박스아웃 효과
│   │   │   │   ├── closeout_analyzer.py   # 클로즈아웃 분석
│   │   │   │   └── help_recovery.py       # 헬프 리커버리
│   │   │   │
│   │   │   ├── 📁 transition_analysis/    # 전환 공수 (3파일)
│   │   │   │   ├── transition_offense.py  # 1차/2차 속공 + 얼리 오펜스
│   │   │   │   ├── transition_defense.py  # 전환 수비 복귀
│   │   │   │   └── transition_efficiency.py # 전환 효율 집계
│   │   │   │
│   │   │   └── 📁 play_type_analysis/     # 플레이 유형별 (6파일)
│   │   │       ├── pick_and_roll.py       # PnR 볼핸들러+롤맨
│   │   │       ├── isolation_analyzer.py  # ISO 분석
│   │   │       ├── post_up_analyzer.py    # 포스트업
│   │   │       ├── spot_up_analyzer.py    # 캐치앤슛
│   │   │       ├── free_throw_analyzer.py # 자유투 심층
│   │   │       └── play_type_efficiency.py # 유형별 PPP
│   │   │
│   │   ├── 📁 player/                     # 선수·라인업 (3모듈)
│   │   │   ├── 📁 individual_analysis/    # 개인 심층 (6파일)
│   │   │   │   ├── drive_analyzer.py      # 드라이브 분석
│   │   │   │   ├── off_ball_movement.py   # 오프볼 무브먼트
│   │   │   │   ├── clutch_performance.py  # 클러치 분석
│   │   │   │   ├── fatigue_analyzer.py    # 피로도 분석
│   │   │   │   ├── player_impact.py       # 선수 영향력 (온/오프코트)
│   │   │   │   └── rebound_analysis.py    # 리바운딩 심층
│   │   │   │
│   │   │   ├── 📁 lineup_analysis/        # 라인업 (3파일)
│   │   │   │   ├── lineup_tracker.py      # 라인업 조합 추적
│   │   │   │   ├── lineup_efficiency.py   # 라인업 효율 (넷레이팅, +/-)
│   │   │   │   └── player_synergy.py      # 선수 시너지
│   │   │   │
│   │   │   └── 📁 rotation_analysis/      # 로테이션 (4파일)
│   │   │       ├── rotation_tracker.py    # 교체 패턴 추적
│   │   │       ├── stagger_analyzer.py    # 스태거링 분석
│   │   │       ├── bench_unit_analyzer.py # 스타터 vs 벤치 비교
│   │   │       └── rest_period_analyzer.py # 휴식 시간 분석
│   │   │
│   │   └── 📁 context/                    # 상황·흐름 (5모듈)
│   │       ├── 📁 spatial_analysis/       # 공간/위치 (4파일)
│   │       │   ├── floor_spacing.py       # 플로어 스페이싱
│   │       │   ├── movement_heatmap.py    # 이동 히트맵
│   │       │   ├── zone_control.py        # 구역 지배력
│   │       │   └── paint_analysis.py      # 페인트 존 분석
│   │       │
│   │       ├── 📁 game_flow/              # 경기 흐름 (4파일)
│   │       │   ├── momentum_tracker.py    # 모멘텀/런 추적
│   │       │   ├── tempo_analyzer.py      # 템포 분석
│   │       │   ├── timeout_effectiveness.py # 타임아웃 효과
│   │       │   └── lead_management.py     # 리드 관리 분석
│   │       │
│   │       ├── 📁 situation_splits/       # 상황별 스플릿 (4파일)
│   │       │   ├── period_splits.py       # 쿼터/하프/OT별
│   │       │   ├── score_margin_splits.py # 점수차별
│   │       │   ├── shot_clock_splits.py   # 슛클락 구간별
│   │       │   └── game_context_analyzer.py # 종합 상황 (클러치 포함)
│   │       │
│   │       ├── 📁 special_situation/      # 특수 상황 (4파일)
│   │       │   ├── ato_play_analyzer.py   # ATO 분석
│   │       │   ├── oob_play_analyzer.py   # 아웃오브바운드 플레이
│   │       │   ├── foul_game_analyzer.py  # 파울 게임 분석
│   │       │   └── last_possession.py     # 라스트 포제션
│   │       │
│   │       └── 📁 season_analysis/        # 시즌/다경기 (3파일)
│   │           ├── season_aggregator.py   # 시즌 누적 통계
│   │           ├── trend_tracker.py       # N경기 이동평균 추세
│   │           └── benchmark_comparator.py # 리그 벤치마크 비교
│   │
│   │  ══ Phase 4: output/ — 출력·코칭 (9모듈) ══
│   │
│   ├── 📁 output/
│   │   ├── 📁 shot_location/              # 슛 위치 (3파일)
│   │   │   ├── shot_zone_mapper.py
│   │   │   ├── shot_heatmap.py
│   │   │   └── efficiency_by_zone.py
│   │   │
│   │   ├── 📁 highlight/                  # 하이라이트 (3파일)
│   │   │   ├── highlight_detector.py
│   │   │   ├── excitement_scorer.py
│   │   │   └── clip_extractor.py
│   │   │
│   │   ├── 📁 game_record/                # 경기 기록 (4파일)
│   │   │   ├── game_sheet_generator.py
│   │   │   ├── play_by_play.py
│   │   │   ├── quarter_summary.py
│   │   │   └── game_report_builder.py
│   │   │
│   │   ├── 📁 video_editing/              # 비디오 편집 (4파일)
│   │   │   ├── clip_manager.py
│   │   │   ├── annotation_overlay.py
│   │   │   ├── multi_angle_sync.py
│   │   │   └── export_manager.py
│   │   │
│   │   ├── 📁 film_session/               # 코칭 필름 세션 (3파일)
│   │   │   ├── film_session_builder.py    # 주제별 클립 컬렉션 자동 생성
│   │   │   ├── player_clip_package.py     # 선수별 개인 리뷰 패키지
│   │   │   └── teaching_point_generator.py # 티칭 포인트 생성
│   │   │
│   │   ├── 📁 coaching_intelligence/      # 실시간 코칭 (3파일)
│   │   │   ├── realtime_advisor.py        # 실시간 코칭 추천
│   │   │   ├── substitution_optimizer.py  # 교체 타이밍 최적화
│   │   │   └── endgame_strategist.py      # 엔드게임 전략
│   │   │
│   │   ├── 📁 pre_game/                   # 경기 전 준비 (5파일)
│   │   │   ├── game_plan_generator.py
│   │   │   ├── game_plan_execution_tracker.py
│   │   │   ├── defensive_assignment_planner.py
│   │   │   ├── offensive_priority_setter.py
│   │   │   └── pre_game_briefing_builder.py
│   │   │
│   │   ├── 📁 scouting/                   # 상대팀 스카우팅 (7파일)
│   │   │   ├── opponent_profiler.py       # 상대팀 프로파일링
│   │   │   ├── tendency_analyzer.py       # 선수별 성향
│   │   │   ├── play_pattern_matcher.py    # 세트플레이 패턴 인식
│   │   │   ├── weakness_finder.py         # 약점 도출
│   │   │   ├── head_to_head_analyzer.py   # 상대전적 분석
│   │   │   ├── referee_tendency_analyzer.py # 심판 성향 분석
│   │   │   └── scouting_report_builder.py # 스카우팅 리포트
│   │   │
│   │   └── 📁 matchup_analysis/           # 매치업 분석 (3파일)
│   │       ├── matchup_tracker.py         # 매치업 트래킹
│   │       ├── contest_analyzer.py        # 슛 컨테스트
│   │       └── matchup_evaluator.py       # 매치업 종합 평가
│   │
│   │  ══ Phase 5: data_extraction/ — 데이터셋 추출 (7파일) ══
│   │
│   └── 📁 data_extraction/
│       ├── frame_record_extractor.py       # 프레임 단위 종합 (10인 위치+키포인트+공+이벤트)
│       ├── possession_record_extractor.py  # 점유 단위 전술 라벨 (전술/수비/결과)
│       ├── game_record_extractor.py        # 경기 단위 집계 (팀스타일+라인업+모멘텀)
│       ├── event_correction_extractor.py   # 이벤트 보정 쌍 (AI예측 vs 인간보정 → 이벤트 모델 재학습)
│       ├── tactical_sequence_extractor.py  # 전술 시퀀스 (포메이션→이동→결과 → 전술 인식 모델)
│       ├── player_performance_extractor.py # 선수 프로파일 (상황별 경향성/효율 → 개인화 모델)
│       └── prediction_outcome_extractor.py # 예측 캘리브레이션 (WP/EPV/xFG% 예측 vs 실제)
│
├── 📁 ai_referee/                     # [Layer 6] AI 심판
│   ├── 📁 rules/
│   │   ├── base_rule.py
│   │   ├── fiba_rules.py
│   │   ├── kbl_rules.py
│   │   ├── nba_rules.py
│   │   ├── nbl_rules.py
│   │   └── rule_loader.py
│   │
│   ├── 📁 violations/                 # 바이올레이션 12종
│   │   ├── traveling_detector.py
│   │   ├── double_dribble_detector.py
│   │   ├── carry_detector.py
│   │   ├── kick_ball_detector.py
│   │   ├── three_second_detector.py       # 공격 3초
│   │   ├── defensive_three_sec_detector.py # 수비 3초 (NBA 전용)
│   │   ├── five_second_detector.py
│   │   ├── eight_second_detector.py
│   │   ├── twenty_four_second_detector.py
│   │   ├── backcourt_detector.py
│   │   ├── out_of_bounds_detector.py
│   │   └── goaltending_detector.py        # 골텐딩 + 인터페어런스 통합
│   │
│   ├── 📁 fouls/                      # 파울 감지 11종
│   │   ├── contact_detector.py            # 접촉 감지 (biomechanics 기반)
│   │   ├── blocking_foul_detector.py
│   │   ├── charging_foul_detector.py
│   │   ├── hand_check_detector.py
│   │   ├── holding_foul_detector.py
│   │   ├── illegal_screen_detector.py
│   │   ├── reach_in_detector.py
│   │   ├── foul_severity_analyzer.py      # 접촉 강도 수치화
│   │   ├── shooting_foul_classifier.py    # 슈팅파울 분류 (2PT/3PT/앤드원)
│   │   ├── flagrant_detector.py           # 플래그런트(NBA)/언스포츠맨라이크(FIBA)
│   │   └── technical_violation_detector.py # 규정 기반 테크니컬
│   │
│   ├── 📁 decisions/                  # 판정 의사결정 (6파일)
│   │   ├── decision_engine.py             # 판정 엔진 (다각도 통합)
│   │   ├── confidence_scorer.py           # 신뢰도 점수
│   │   ├── multi_angle_validator.py       # 4-8대 카메라 크로스 체크
│   │   ├── replay_manager.py              # 리플레이 관리
│   │   ├── decision_explainer.py          # 판정 근거 설명
│   │   └── consistency_tracker.py         # 경기 내 판정 일관성 추적
│   │
│   └── 📁 data_extraction/            # 심판 데이터 추출 (자가학습용, 6파일)
│       ├── decision_record_extractor.py   # 전체 판정 기록 수집 (콜/노콜 + 풀 컨텍스트)
│       ├── correction_pair_extractor.py   # AI 판정 vs 인간 교정 쌍 (지도학습 핵심 신호)
│       ├── edge_case_extractor.py         # 저신뢰도 경계 케이스 캡처 (능동 학습)
│       ├── calibration_data_extractor.py  # 신뢰도→정확도 보정 데이터 (Platt/Isotonic)
│       ├── foul_contact_extractor.py      # 접촉 이벤트+파울 라벨 쌍 (파울 모델 재훈련)
│       └── violation_sequence_extractor.py # 바이올레이션 시계열 패턴 (40프레임 시퀀스)
│
├── 📁 feedback_system/                # [Layer 7] 피드백 시스템 (코치 + 전력분석원)
│   │
│   │  ┌──────────────────────────────────────────────────────────────────┐
│   │  │  역할 분리 원칙                                                  │
│   │  │  ● 코치 (coach/)       : 개인 동작 폼 교정 + 생체역학 피드백       │
│   │  │    → 입력: motion_dto, biomechanics_dto, pose_dto               │
│   │  │  ● 전력분석원 (analysis/): 경기/전술 전략 분석 피드백               │
│   │  │    → 입력: game_dto, tactical_dto, prediction_dto               │
│   │  │  ● 기록원: feedback_system 미사용                                │
│   │  │    → game_analysis/output/game_record/ 직접 출력                 │
│   │  └──────────────────────────────────────────────────────────────────┘
│   │
│   ├── 📁 coach/                      # ═══ 코치 역할 (동작 폼 교정 + 생체역학 피드백) ═══
│   │   │
│   │   │  입력 DTO:
│   │   │    motion_dto    → ShootingMotion (13유형), DribblingMotion (13유형),
│   │   │                    PassingMotion (11유형), DefensiveMotion (11유형),
│   │   │                    MovementMotion (12유형), MotionDetectionResult
│   │   │    biomechanics_dto → BiomechanicalResult, JointKinematics,
│   │   │                       BalanceMetrics, EnergyMetrics, ForceEstimate,
│   │   │                       LandingImpactData, AnthropometryData,
│   │   │                       TrajectoryProfileData, MotionPatternData
│   │   │    pose_dto      → Skeleton2D, Skeleton3D, JointAngle
│   │   │
│   │   ├── motion_feedback.py         # 동작 폼 코칭 피드백 (generators/에서 이동)
│   │   │   │
│   │   │   │  ◆ 슈팅 폼 코칭 (13유형 × 4단계)
│   │   │   │    - 준비(Preparation): 스탠스 너비, 무릎 굴곡각, 볼 세팅 위치
│   │   │   │    - 실행(Execution): 팔꿈치 각도(90±5°), 어깨 회전, 손목 스냅 타이밍
│   │   │   │    - 릴리스(Release): 릴리스 각도(50~55°), 릴리스 높이, 백스핀 RPM
│   │   │   │    - 팔로우스루(Follow-through): 손목 완전 신전, 팔 유지 시간
│   │   │   │    - 슛 유형별 기준 차등: 레이업(저아크) vs 3점슛(고아크) vs 훅슛(측면)
│   │   │   │    - 거리별 릴리스 각도/속도 최적 기준 자동 조정
│   │   │   │    - 컨테스트 레벨별 난이도 보정 (오픈/라이트/헤비 컨테스트)
│   │   │   │
│   │   │   │  ◆ 드리블 폼 코칭 (13유형)
│   │   │   │    - 바운스 빈도 적정성, 볼 높이 변동 폭 평가
│   │   │   │    - 제어 품질(control_quality) 기반 핸들링 피드백
│   │   │   │    - 방향 전환 빈도 및 크로스오버 효율성
│   │   │   │    - 드리블 유형별 핸드 포지션/바디 앵글 기준
│   │   │   │
│   │   │   │  ◆ 패스/수비/이동 폼 코칭
│   │   │   │    - 패스(11유형): 체스트패스 양손 대칭, 바운스패스 각도, 오버헤드 릴리스 포인트
│   │   │   │    - 수비(11유형): 스탠스 너비, 힙 높이, 손 위치, 슬라이드 스텝 보폭
│   │   │   │    - 이동(12유형): 가속 자세, 감속 메커니즘, 방향전환 중심이동
│   │   │   │
│   │   │   └── 출력: FeedbackItem[] (동작별 최소 10개 이상 세부 피드백)
│   │   │
│   │   └── biomechanics_feedback.py   # 생체역학 코칭 피드백 (신규)
│   │       │
│   │       │  ◆ 관절 운동학 피드백 (JointKinematics 기반)
│   │       │    - 관절별 속도/가속도 적정 범위 평가 (17개 관절 × 동작 단계별)
│   │       │    - 각속도 기반 동작 유창성(fluency) 판정
│   │       │    - 동작 체인 분석: 하체→코어→상체 순차적 에너지 전달 평가
│   │       │    - 관절간 타이밍 동기화(coordination) 피드백
│   │       │      (예: 슈팅 시 무릎 신전→팔꿈치 신전→손목 스냅 시간차 최적화)
│   │       │
│   │       │  ◆ 균형/안정성 피드백 (BalanceMetrics 기반)
│   │       │    - 무게중심(CoM) 위치: 슛/드리블/수비 동작별 최적 CoM 범위
│   │       │    - 체중 분배 좌우 대칭성: (0.45~0.55) 정상, 비대칭 시 교정 피드백
│   │       │    - 동요 속도(sway_velocity): 안정 임계치 대비 평가
│   │       │    - 지지기저면(BoS) 넓이: 스탠스 너비 적정성 (어깨너비 ±10%)
│   │       │    - 슛 시 점프 정점 안정성, 착지 후 균형 회복 시간
│   │       │
│   │       │  ◆ 에너지 효율성 피드백 (EnergyMetrics 기반)
│   │       │    - 운동/위치 에너지 비율: 동작 단계별 최적 에너지 분배
│   │       │    - 에너지 전달률(W): 하체→상체 에너지 전달 효율 (손실률 평가)
│   │       │    - 탄성 에너지 활용도: 반동 동작(SSC) 효율성 판정
│   │       │    - 불필요한 에너지 소비 감지 (비효율적 동작 패턴 경고)
│   │       │
│   │       │  ◆ 착지 충격/부상 예방 피드백 (LandingImpactData 기반)
│   │       │    - 피크 지면반력 평가: <3.0 BW(안전), 3.0~5.0(주의), >5.0(위험)
│   │       │    - 충격 흡수 시간: ≥50ms(양호), 30~50ms(보통), <30ms(불량)
│   │       │    - 착지 메커니즘: 양발/편발 착지 패턴, 무릎 발구스 각도
│   │       │    - 부상 위험 등급별 구체적 교정 가이드
│   │       │
│   │       │  ◆ 인체측정 보정 피드백 (AnthropometryData 기반)
│   │       │    - 사용자 신체 비율에 맞는 관절 각도 기준 동적 조정
│   │       │    - 성별 보정: 남성/여성 관절 가동범위(ROM) 차등 기준
│   │       │    - 연령대 보정: 유소년(<13)/청소년(13~18)/성인(18+) 차등 기준
│   │       │    - 에이프 인덱스 기반 슛 릴리스 포인트 최적화 조언
│   │       │    - BMI/체형별 동작 효율 기준 보정
│   │       │
│   │       │  ◆ 궤적/힘 분석 피드백
│   │       │    - 슈팅 아크 궤적 평가: 최적 포물선 대비 편차
│   │       │    - 드리블 리듬 패턴: 바운스 간격 일정성, 리듬 변화 의도성
│   │       │    - 관절별 토크 적정 범위: 과부하 관절 경고
│   │       │    - 폭발적 가속/감속: 방향전환 효율, First Step 퀵니스
│   │       │
│   │       └── 출력: FeedbackItem[] (생체역학 지표별 최소 10개 이상 세부 피드백)
│   │
│   ├── 📁 analysis/                   # ═══ 전력분석원 역할 (경기/전술 전략 분석 피드백) ═══
│   │   │
│   │   │  입력 DTO:
│   │   │    game_dto       → GameStats, TeamStats, PlayerStats, ShotChart, ShotAttempt
│   │   │    tactical_dto   → TacticalAnalysisResult (20+ 하위 DTO 통합)
│   │   │                     - GameFlowData (ScoringRun, MomentumShift, MomentumState)
│   │   │                     - ClutchStats, TransitionData, SituationSplitData
│   │   │                     - SpacingMetrics, LineupAnalysis, PlayTypeAnalysis
│   │   │                     - DefenseAnalysis, PassingNetworkData, FastBreakAnalysis
│   │   │    prediction_dto → WinProbability, EPV, ShotQualityPrediction
│   │   │    scouting_dto   → OpponentProfile, TendencyReport, WeaknessReport
│   │   │    feedback_dto   → FeedbackItem + VideoClipReference, CausalFactor (근거 연동)
│   │   │
│   │   ├── game_feedback.py               # 경기 종합 피드백 (Four Factors, 승리 요인)
│   │   ├── tactical_feedback.py           # 전술 피드백 (PnR, 패스트브레이크, 세트플레이)
│   │   ├── defensive_feedback.py          # 수비 전략 피드백 (DRtg, 컨테스트율, 로테이션)
│   │   ├── individual_feedback.py         # 개인 스탯 피드백 (TS%, eFG%, GameScore)
│   │   ├── spatial_feedback.py            # 공간 활용 피드백 (스페이싱, 코트 점유율)
│   │   ├── lineup_feedback.py             # 라인업 효율 피드백 (넷레이팅, 조합 분석)
│   │   ├── referee_feedback.py            # 심판 판정 영향 피드백
│   │   ├── visual_feedback_generator.py   # 시각화 피드백 (슛 차트, 히트맵)
│   │   ├── quarter_momentum_feedback.py   # 쿼터별 모멘텀 분석 (스코링런, 모멘텀시프트)
│   │   ├── clutch_feedback.py             # 클러치 상황 분석 (4Q 5분 이내, 5점차 이내)
│   │   ├── pace_tempo_feedback.py         # 페이스/템포 분석 (포제션당 시간, 트랜지션 빈도)
│   │   ├── shot_quality_feedback.py       # 슛 퀄리티 분석 (오픈룩 비율, 슛 셀렉션)
│   │   ├── opponent_tendency_feedback.py  # 상대팀 경향 분석 (공수 패턴, 약점 도출)
│   │   ├── rotation_feedback.py           # 로테이션/벤치 분석 (교체 타이밍, 벤치 기여도)
│   │   ├── strategic_recommendation_feedback.py  # 전략 권고 (종합 전략 제안)
│   │   │
│   │   │  ═══ 고급 분석 생성기 (전력분석원 수준 심화) ═══
│   │   │
│   │   ├── causal_feedback.py             # 원인 추론 분석 ("왜?" 근거 제시, CausalFactor 첨부)
│   │   │   └── 슈팅/턴오버/수비/전환/리바운드/득점패턴 6개 섹션 × 원인 추론
│   │   ├── game_context_feedback.py       # 경기 맥락 분석 (접전/대승, 가비지타임, 모멘텀)
│   │   │   └── 경기유형/쿼터추세/스코링런/모멘텀/전반후반 체력추세 등 game_context 태그
│   │   └── scouting_feedback.py           # 스카우팅 실행도 분석 (사전 보고서 vs 실제 결과)
│   │       └── 상대 프로필 대비/경향 비교/약점 공략/스카우팅 등급 (A/B/C/D)
│   │
│   ├── 📁 templates/
│   │   ├── korean_templates.py            # 한글 템플릿 (코치/분석 공용)
│   │   ├── feedback_formatter.py          # 피드백 포맷터
│   │   └── severity_mapper.py             # 심각도 매핑
│   │
│   └── 📁 report/
│       ├── coach_report_generator.py      # 코치 리포트 오케스트레이터 (신규)
│       │   └── motion_feedback + biomechanics_feedback → CoachFeedbackResult
│       ├── game_report_generator.py       # 전력분석 리포트 오케스트레이터 (기존 확장)
│       │   └── analysis/ 18개 생성기 → GameFeedbackResult
│       ├── session_summary.py             # 세션 요약
│       ├── progress_tracker.py            # 진행도 추적
│       └── trend_analyzer.py              # 트렌드 분석
│
├── 📁 api_server/                     # [Layer 9] 로컬 API
│   ├── main.py
│   ├── 📁 routes/v1/
│   │   ├── game_routes.py
│   │   ├── referee_routes.py
│   │   ├── tactical_routes.py
│   │   ├── video_routes.py
│   │   ├── feedback_routes.py
│   │   ├── report_routes.py
│   │   ├── task_routes.py
│   │   └── metrics_routes.py
│   ├── 📁 middleware/
│   │   ├── request_validator.py
│   │   ├── cors_middleware.py
│   │   └── error_handler.py
│   ├── 📁 websocket/
│   │   ├── connection_manager.py
│   │   └── progress_handler.py
│   ├── 📁 services/
│   │   ├── video_service.py
│   │   ├── game_service.py
│   │   ├── referee_service.py
│   │   ├── tactical_service.py
│   │   ├── feedback_service.py
│   │   ├── report_service.py
│   │   ├── task_service.py
│   │   ├── export_service.py
│   │   ├── cloud_sync_service.py      # Cloud Backend 동기화 총괄
│   │   ├── realtime_stream_service.py  # 실시간 스트리밍 (경기 중)
│   │   └── batch_sync_service.py      # 경기 후 결과 일괄 전송
│   ├── 📁 services/facades/
│   │   ├── game_stats_facade.py
│   │   ├── referee_facade.py
│   │   ├── tactical_facade.py
│   │   ├── highlight_facade.py
│   │   └── report_facade.py
│   └── 📁 schemas/
│       ├── request_schemas.py
│       └── response_schemas.py
│
├── 📁 engine/                        # [Layer 8] 분석 파이프라인 오케스트레이션 (27파일)
│   ├── __init__.py
│   ├── config.py                     # EngineConfig (모드/GPU/카메라/Cadence 설정)
│   ├── game_state.py                 # GameState (경기 상태 — 전역 동적 컨텍스트)
│   │                                 # LIVE/DEAD_BALL/FREE_THROW/TIMEOUT/HALFTIME/POSTGAME
│   │                                 # 점유 상태, 시계, 파울 누적, 라인업 — cadence_scheduler 참조
│   ├── analysis_buffer.py            # motion_analysis Tier1용 MotionSnapshot 30프레임 슬라이딩 윈도우
│   │
│   ├── 📁 gpu/                       # GPU 리소스 관리
│   │   ├── __init__.py
│   │   ├── gpu_manager.py            # VRAM 할당/모니터링/발열 스로틀링/OOM 방어
│   │   ├── tensorrt_pool.py          # 다중 TRT 엔진 풀 (YOLOv8/ViTPose/ReID...)
│   │   │                             # pose_estimation/backends/tensorrt_engine.py의 public API 호출
│   │   ├── cuda_stream_manager.py    # CUDA Stream #1(Stage1) / #2(Stage2) 관리
│   │   └── batch_accumulator.py      # 8카메라 CPU큐 → GPU 배치 텐서 변환
│   │
│   ├── 📁 pipeline/                  # 핵심 파이프라인 (Cadence = 파일)
│   │   ├── __init__.py
│   │   ├── frame_pipeline.py         # 🔴 FRAME: 감지→포즈→트래킹 (16ms 이내)
│   │   ├── event_pipeline.py         # 🟠 EVENT: 이벤트감지→통계증분→기록 (<10ms)
│   │   ├── possession_pipeline.py    # 🟡 POSSESSION: 전술→개인→하이라이트 (<100ms)
│   │   ├── period_pipeline.py        # 🟢 PERIOD: 쿼터요약→추세→로테이션 (<1s)
│   │   ├── postgame_pipeline.py      # 🔵 POST-GAME: 보고서→추출→동기화 (무제한)
│   │   └── 📁 fusion/               # 멀티카메라 융합 (기존 인프라 조합)
│   │       ├── __init__.py
│   │       ├── detection_fusion.py   # 🔴 8cam DetectionResult → 단일 SceneDetection
│   │       ├── pose_fusion.py        # 🔴 8cam PoseResult → 단일 Skeleton3D (삼각측량)
│   │       └── tracking_fusion.py    # 🟠 8cam TrackingID → 통합 ID (충돌 시 트리거)
│   │
│   ├── 📁 orchestrator/             # 오케스트레이션
│   │   ├── __init__.py
│   │   ├── game_orchestrator.py      # 경기 전체 수명주기 (시작→진행→종료)
│   │   ├── cadence_scheduler.py      # GameState 참조 → 5등급 파이프라인 트리거
│   │   └── mode_controller.py        # 라이브(60fps 제약) vs 배치(최대속도) 모드 전환
│   │
│   ├── 📁 referee/                   # AI 심판 전용 파이프라인
│   │   ├── __init__.py
│   │   ├── referee_orchestrator.py   # violation+foul+decision 통합 판정 루프
│   │   └── multi_angle_pipeline.py   # 4~8대 카메라 판정 교차검증+다수결
│   │
│   ├── 📁 io/                        # 입출력
│   │   ├── __init__.py
│   │   ├── frame_ingestion.py        # 멀티카메라 프레임 수집+동기화(±1ms)+CPU큐
│   │   ├── result_dispatcher.py      # 결과 분배 (WebSocket/JSON/클라우드)
│   │   └── progress_reporter.py      # 분석 진행률 보고
│   │
│   └── 📁 workers/                   # 비동기 워커
│       ├── __init__.py
│       ├── analysis_worker.py        # 🟡🟢 분석 워커 (내부 2풀: possession 4T + period 2T)
│       └──  export_worker.py          # 🔵 내보내기/데이터추출 워커
│
├── 📁 storage/                        # 로컬 파일 저장소
│   ├── 📁 videos/
│   ├── 📁 outputs/
│   ├── 📁 exports/
│   ├── 📁 datasets/
│   └── 📁 logs/
│
├── 📁 deployment/
│   ├── 📁 windows/
│   ├── 📁 macos/
│   └── 📁 linux/
│
├── 📁 tests/
│   ├── conftest.py
│   ├── 📁 unit/
│   ├── 📁 integration/
│   └── 📁 performance/
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 4. 2-Stage Pose Pipeline

**"항시 가벼운 감시 + 필요할 때만 정밀 분석"**

```
프레임 입력 (1080p, 60fps)
    │
    ▼
┌───────────────────────────────────────┐
│  Stage 1: YOLOv8x-Pose (TRT FP16)    │
│  - CUDA Stream #1 (상시 실행)          │
│  - 전체 프레임 → 10명 BBox + 17kp     │
│  - ~12ms / VRAM ~800MB                │
└───────────────┬───────────────────────┘
                │ 트리거 조건 판단
                │ (슈팅/파울/바이올레이션/드리블기술)
                ▼
┌───────────────────────────────────────┐
│  Stage 2: ViTPose-B (TRT FP16)        │
│  - CUDA Stream #2 (이벤트 트리거)      │
│  - Top-Down 1~3명 → 133kp            │
│  - ~12ms / VRAM ~600MB                │
└───────────────┬───────────────────────┘
                ▼
          biomechanics → game_analysis → ai_referee
```

| 분석 항목 | Stage 1 (17kp) | Stage 2 (133kp) |
|-----------|:-:|:-:|
| 선수 위치/이동/팀 배치 | ✅ | - |
| 슛/리바운드/블록 감지 | ✅ | - |
| 경기 통계 (기록지) | ✅ | - |
| 트래블링 판정 | ❌ | **필수** (발 6kp) |
| 더블드리블/핸드체킹 | ❌ | **필수** (손 42kp) |
| 슈팅파울/파울 강도 | △ | **필수** (정밀 관절) |

**VRAM 예산 (12GB 최소 기준):**

```
상시 모델:  YOLOv8x-Pose ~800MB + YOLOv8l-Det ~400MB + ViTPose-B ~600MB + ReID ~300MB = ~2.1GB
버퍼/텐서: 입력 프레임 ~200MB + 중간 텐서 ~300MB + 후처리 ~200MB = ~700MB
총계:      ~2.8GB / 12GB (23%) — 여유 ~9.2GB
```

---

## 5. 실시간 처리 아키텍처 (Processing Cadence)

> game_analysis 26서브모듈이 동시에 매 프레임 실행되는 것이 아님.
> 각 모듈은 **실행 등급(Cadence)**에 따라 트리거된다.

### 5.1 실행 등급

| 등급 | 트리거 | 시간 제한 | 실행 위치 |
|------|--------|----------|----------|
| 🔴 FRAME | 매 프레임 (60fps) | <2ms/모듈 | 메인 GPU 파이프라인 |
| 🟠 EVENT | 이벤트 감지 즉시 | <10ms | 이벤트 버스 (비동기) |
| 🟡 POSSESSION | 점유 종료 시 | <100ms | 워커 스레드 |
| 🟢 PERIOD | 쿼터/하프 종료 시 | <1s | 백그라운드 풀 |
| 🔵 POST-GAME | 경기 종료 후 | 무제한 | 배치 프로세서 |

### 5.2 event_detection 조건부 실행

```
game_state: LIVE (인플레이)
├── 🔴 상시 활성 (매 프레임, 합산 <6ms)
│   ├── possession_tracker
│   ├── score_detector
│   └── dead_ball_detector
│
├── 🟠 상태 조건부 (게임 상태에 따라 ON/OFF)
│   ├── shot_event_detector      # 공격 점유 시
│   ├── rebound_detector         # 슛 시도 후 3초 윈도우
│   ├── fast_break_detector      # 점유 전환 후 5초 윈도우
│   ├── drive_detector           # 볼핸들러 속도 임계치 초과
│   ├── screen_detector          # 하프코트 오펜스 시
│   └── foul_detector            # 접촉 감지 트리거
│
├── 🟠 이벤트 역추적 (이벤트 발생 후 과거 N프레임 분석)
│   ├── assist_detector          # 득점 → 직전 패스 역추적
│   ├── steal_detector           # 점유 전환 → 원인 역추적
│   ├── turnover_detector        # 점유 전환 → 원인 역추적
│   └── block_detector           # 슛 미스 → 블록 여부 확인
│
└── 🟡 특수 상황 전용
    ├── free_throw_detector      # FREE_THROW 상태
    ├── box_out_detector         # 슛 시도 후
    └── jump_ball_detector       # JUMP_BALL 상태

game_state: DEAD_BALL / TIMEOUT / HALFTIME
└── 전체 디텍터 비활성 (GPU 유휴)
```

### 5.3 game_analysis Cadence 매핑

| Phase | 서브모듈 | 등급 |
|-------|---------|------|
| 1A | game_management | 🟠 EVENT (clock_manager만 🔴 FRAME) |
| 1B | event_detection | 🔴/🟠 혼합 (5.2절 참조) |
| 1C | live_workspace | 🟠 EVENT |
| 2 | statistics | 🟠 EVENT (증분 계산만) |
| 2 | predictive_models | 🟠 EVENT (캐시 + 변경분만) |
| 3 | tactical_analysis, defensive_analysis, individual_analysis, spatial_analysis, play_type_analysis | 🟡 POSSESSION |
| 3 | lineup_analysis, transition_analysis, special_situation | 🟡 POSSESSION (조건부) |
| 3 | game_flow, situation_splits, rotation_analysis | 🟢 PERIOD |
| 3 | opponent_scouting, season_analysis | 🔵 POST-GAME |
| 4 | shot_location, game_record | 🟠 EVENT (증분) |
| 4 | highlight | 🟡 POSSESSION |
| 4 | coaching_intelligence | 🟠 EVENT (캐시 기반) |
| 4 | video_editing, film_session, pre_game | 🔵 POST-GAME |
| 5 | data_extraction | 🔵 POST-GAME |

### 5.4 핵심 규칙

- 🔴 FRAME 등급: **전체 합산 16ms 이내** (60fps 보장)
- Phase 2: **증분(O(1)) 계산만**, 전체 재계산은 쿼터/경기 종료 시
- Phase 4: Phase 3 결과를 **캐시에서 읽음** (완료 대기 금지, 200ms 타임아웃 후 Phase 2 폴백)

### 5.5 engine/ 데이터 흐름

```
카메라 8대 (USB/IP/RTSP/FILE)
    │
    ▼ io/frame_ingestion ─── 수집+동기화(±1ms)+CPU큐
    │
    ▼ gpu/batch_accumulator ── CPU큐 → GPU 배치 텐서 (8프레임)
    │
    ▼ ─── CUDA Stream #1 (gpu/cuda_stream_manager) ─────────────────────
    │  pipeline/frame_pipeline (🔴 FRAME, 16ms)
    │  ├── detection (ball+player+court+hoop)
    │  ├── pipeline/fusion/detection_fusion → 단일 SceneDetection
    │  ├── pose Stage1 (YOLOv8x-Pose 17kp)
    │  ├── pipeline/fusion/pose_fusion → 단일 Skeleton3D
    │  ├── tracking (ByteTrack + ReID)
    │  ├── 기본 biomechanics (속도/가속도/관절각도)
    │  └── game_state 갱신 (possession/clock/score)
    │
    ▼ orchestrator/cadence_scheduler ── GameState 참조 → 트리거 판단
    │
    ├─ 슈팅/파울/바이올레이션? ──→ pipeline/event_pipeline (🟠 EVENT)
    │   ├─ CUDA Stream #2: ViTPose 133kp → 정밀 biomech
    │   ├─ motion_analysis → ai_referee
    │   └─ referee/referee_orchestrator + multi_angle_pipeline
    │
    ├─ 점유 종료? ──→ workers/analysis_worker (🟡 POSSESSION, 4T 풀)
    │   └─ pipeline/possession_pipeline → 전술/개인/공간/하이라이트
    │
    ├─ 쿼터 종료? ──→ workers/analysis_worker (🟢 PERIOD, 2T 풀)
    │   └─ pipeline/period_pipeline → game_flow/rotation/situation_splits
    │
    └─ 경기 종료? ──→ workers/export_worker (🔵 POST-GAME)
        └─ pipeline/postgame_pipeline → 피드백 → 데이터 추출 → 리포트
            └─ workers/sync_worker → 클라우드 동기화
                └─ io/result_dispatcher → WebSocket/JSON/Cloud
```

### 5.6 engine 설계 원칙

| # | 원칙 | 설명 |
|:-:|------|------|
| 1 | **Cadence = 파이프라인 파일** | 5등급 각각이 독립 파이프라인, cadence_scheduler가 트리거 |
| 2 | **GPU 중앙 제어** | gpu/ 4파일이 CUDA Stream 2개 할당, VRAM 모니터링, 발열 스로틀링 |
| 3 | **모드 전환** | mode_controller가 라이브(16ms 제약) vs 배치(무제한) 실행 파라미터 조정 |
| 4 | **기존 모듈 변경 0건** | engine은 Layer 0~7의 public API만 호출, 기존 코드 수정 없음 |
| 5 | **GameState 전역 참조** | engine/ 루트의 game_state.py를 pipeline/과 orchestrator/ 모두 참조 |
| 6 | **fusion = 인프라 조합** | infrastructure/multi_camera의 API를 조합, 새 알고리즘 아님 |

---

## 6. AI 심판 시스템

### 6.1 지원 리그

FIBA (국제) / KBL (한국) / NBA (미국) / NBL (호주)

### 6.2 바이올레이션 12종

| # | 바이올레이션 | 핵심 입력 |
|---|------------|----------|
| 1 | 트래블링 | 발 6kp (ViTPose) |
| 2 | 더블 드리블 | 손 42kp + 볼 상태 |
| 3 | 캐리/팜잉 | 손-볼 회전 + 체류시간 |
| 4 | 킥볼 | 발-볼 근접도 + 의도성 |
| 5 | 공격 3초 | 페인트존 체류 추적 |
| 6 | 수비 3초 (NBA 전용) | 마크맨 거리 + 페인트존 |
| 7 | 5초 | 인바운드/밀접수비 타이머 |
| 8 | 8초 | 백코트 진입 타이머 |
| 9 | 24초 | 슛클락 |
| 10 | 백코트 | 하프라인 + 볼 위치 |
| 11 | 아웃오브바운드 | 라인 + 볼/발 위치 |
| 12 | 골텐딩/인터페어런스 | 볼 궤적 + 림 실린더 |

### 6.3 파울 11종

**접촉 유형 (7종):** 블로킹, 차징, 핸드체크, 홀딩, 일리걸스크린, 리치인, 일반접촉

**상황 맥락 (shooting_foul_classifier):**
- 슈팅파울 2PT/3PT, 앤드원 2PT/3PT, 비슈팅파울
- 접촉 시점의 모션 페이즈 분석 (wind-up/release/follow-through)

**특수 등급 (flagrant_detector):**
- NBA: Flagrant 1 (불필요 접촉) / Flagrant 2 (불필요+과도)
- FIBA: Unsportsmanlike C1~C4

**규정 테크니컬 (technical_violation_detector):**
- 림 매달리기, 지연행위, 코트 인원 초과
- ⚠️ 행위 기반 테크니컬(항의/도발)은 AI 범위 밖 → live_workspace 수동 입력

### 6.4 판정 프로세스

```
접촉/이벤트 감지
  → 4-8대 카메라 개별 판정
  → 다수결 + 신뢰도 가중평균
  → 생체역학 증거 교차 검증
  → 일관성 검증 (경기 내 동일 강도 = 동일 판정)
  → 최종 판정 (일치도 ≥75% + 생체역학 일치 → CONFIRMED)
```

### 6.5 ML 모델 로드맵 (2026-04-20 확정)

AI 심판 **판정 엔진은 규칙 기반(92%+)**. 이벤트 감지는 아래 ML 가중치와 연동:

```
BBox v8 / Digit v5 / team v2 → Action → Recorder → Coach → Scout → Foul → Violation → Possession
```

**핵심 정책:**
- **CV-Score 단독 모델 폐기** → CV-Recorder가 `made/missed/rebound/assist/steal/turnover/block` 이벤트 통합 판정 (인과관계 보존)
- **CV-Foul/CV-Violation은 판정 ML** (ai_referee rules 기반 감지 후 상황 분류)
- **CV-BioML 전면 폐기** → biomechanics는 규칙 기반 계산 모듈로 유지 (2026-04-18)
- **CV-Possession** = 판단 ML (거리 계산만으론 지나가는 수비수 오탐지)

상세: `memory/project_weight_roadmap.md`

### 6.6 데이터 추출 (Phase E: data_extraction/)

판정 파이프라인이 생성한 모든 결과를 자가학습용 데이터셋으로 수집.

| # | 추출기 | 목적 | 수집 대상 | DatasetType |
|---|--------|------|----------|-------------|
| 1 | DecisionRecordExtractor | 전체 판정 기록 | FinalDecision + FrameContext (콜+노콜 3:1 샘플링) | REFEREE_DECISION |
| 2 | CorrectionPairExtractor | AI판정 vs 인간교정 쌍 | 리플레이 번복 / 코치 챌린지 성공 / 수동 검토 | REFEREE_CORRECTION |
| 3 | EdgeCaseExtractor | 저신뢰도 경계 케이스 | 신뢰도 0.50~0.85 / 동의율 <0.75 / 일관성 <0.70 | REFEREE_EDGE_CASE |
| 4 | CalibrationDataExtractor | 신뢰도 보정 데이터 | (예측 신뢰도, 실제 확정 결과) 쌍, 0.05 구간 빈 | REFEREE_CALIBRATION |
| 5 | FoulContactExtractor | 접촉+파울 라벨 쌍 | ContactEvent + 키포인트 ±3프레임 + 최종 라벨 | FOUL_CONTACT |
| 6 | ViolationSequenceExtractor | 위반 시계열 패턴 | 위반 전후 40프레임 시퀀스 + 정상 네거티브 10:1 | VIOLATION_SEQUENCE |

**데이터 흐름:**

```
Phase A~D (판정 생성)
    │
    ▼
Phase E data_extraction (판정 기록 수집)
    │
    ├── decision_record     ─→ 전체 판정 재현 데이터셋
    ├── correction_pair     ─→ 오류 교정 지도학습 신호 (최고 가치)
    ├── edge_case           ─→ 능동 학습 라벨링 큐
    ├── calibration_data    ─→ 신뢰도 보정 곡선
    ├── foul_contact        ─→ 파울 감지 모델 재훈련
    └── violation_sequence  ─→ 바이올레이션 패턴 학습
         │
         ▼
    ExtractionResult (PENDING) → S3 업로드 → 자가학습 시스템
```

### 6.7 자가학습을 통한 정확도 향상 경로

규칙 기반 모델(92%+)에서 출발하여, 실전 데이터 누적으로 프로 심판 수준(96~98%)까지 도달.

```
Phase 1: 규칙 기반 베이스라인 (현재)
  └── 92%+ 정확도 (모델 자체, 학습 없이)

Phase 2: 초기 데이터 수집 (50~100경기)
  ├── correction_pair → 명시적 오류 패턴 학습
  ├── calibration → 신뢰도 보정 곡선 구축 (빈당 30개+)
  └── 예상: 93~94%

Phase 3: 능동 학습 루프 (100~300경기)
  ├── edge_case → 전문가 라벨링 → 약점 집중 개선
  ├── foul_contact → 접촉 판정 모델 미세조정
  ├── violation_sequence → 시계열 패턴 인식 강화
  └── 예상: 95~96%

Phase 4: 대규모 누적 (300경기+)
  ├── 리그별/상황별 보정 모델 분화
  ├── 클러치/퇴장 등 고위험 판정 특화
  ├── 팀 편향/경기 일관성 메타 학습
  └── 예상: 96~98% (프로 심판 수준 도달)
```

| 단계 | 경기 수 | 예상 정확도 | 핵심 학습 소스 |
|------|:------:|:----------:|--------------|
| 베이스라인 | 0 | 92%+ | 규칙 기반 (하드코딩 없음) |
| 초기 수집 | 50~100 | 93~94% | correction_pair + calibration |
| 능동 학습 | 100~300 | 95~96% | edge_case + foul_contact |
| 대규모 누적 | 300+ | 96~98% | 전체 6종 추출기 + 메타 학습 |

> **참고**: 프로 심판 정확도 95~97% (NBA 공식 Last 2 Minute Report 기준).
> 자가학습 시스템은 별도 프로그램으로 운영 (COURTVIEW_DESK 외부).

---

## 7. engine/ 구축 순서

> community_49.md (이대리 + 최과장 합의, 2026-03-27 송사장 승인)

| 순서 | 대상 | 파일 수 | 이유 |
|:----:|------|:------:|------|
| 1 | `config.py` + `game_state.py` | 2 | 전역 설정+상태 — 모든 것의 토대 |
| 2 | `gpu/` (4파일) | 4 | GPU 추상화 없이 파이프라인 불가 |
| 3 | `io/frame_ingestion.py` | 1 | 프레임 입력 없이 파이프라인 불가 |
| 4 | `pipeline/fusion/` (3파일) | 3 | 멀티카메라 → 단일 씬 변환 |
| 5 | `pipeline/frame_pipeline.py` | 1 | 🔴 60fps 핵심 루프 |
| 6 | `orchestrator/cadence_scheduler.py` | 1 | EVENT 이상 파이프라인 제어 |
| 7 | `pipeline/event_pipeline.py` + `referee/` (2파일) | 3 | 🟠 + AI 심판 |
| 8 | `workers/` (3파일) + 나머지 pipeline (2파일) | 5 | 🟡🟢🔵 비동기 |
| 9 | `orchestrator/game_orchestrator.py` + `mode_controller.py` | 2 | 최상위 수명주기 |
| 10 | `io/result_dispatcher.py` + `progress_reporter.py` | 2 | 출력+진행률 |

---

## 8. 성능 목표

### 7.1 처리 성능

| 항목 | 목표 |
|------|------|
| 경기 분석 FPS | 60fps (4-8카메라) |
| AI 심판 FPS | 60fps (실시간 판정) |
| 경기 분석 정확도 | 90-92% |
| AI 심판 정확도 (베이스라인) | 92-95% (8카메라), 88-90% (4카메라) |
| AI 심판 정확도 (자가학습 후) | 96-98% (300경기+ 누적, 프로 심판 수준) |
| 처리 지연 | <50ms |
| 판정 시간 | <1초 (다각도 검증 포함) |
| 하이라이트 생성 | <2분 (1시간 경기) |

### 7.2 지원 하드웨어

| 항목 | RTX 5060 (권장/표준) | RTX 5070 Ti (고성능) | RTX 4090 Laptop (프리미엄) |
|------|:-:|:-:|:-:|
| VRAM | 8GB GDDR7 | 8GB GDDR7 | 8GB GDDR6 |
| FP16 추론 | ~190 TFLOPS | ~220 TFLOPS | ~280 TFLOPS |
| TensorRT | ✅ | ✅ | ✅ |

**표준 사양 (B2B 렌탈)**: RTX 5060 8GB + RAM 16GB
**최소 사양**: RTX 5060 동등 이상 (VRAM 8GB 필수)
**피크 VRAM**: ~2.35GB / 가용 6.5GB (36% 사용률)

---

## 9. API 엔드포인트

### 8.1 서버 설정

```yaml
호스트: localhost:8000
프로토콜: HTTP (로컬 전용)
WebSocket: ws://localhost:8000/ws/{channel}/{id}
인증: 하드웨어 ID 기반 라이선스 검증
```

### 8.2 주요 엔드포인트

```
# 경기 분석
POST   /api/v1/game/analyze
GET    /api/v1/game/{game_id}/status
GET    /api/v1/game/{game_id}/result
GET    /api/v1/game/{game_id}/stats
GET    /api/v1/game/{game_id}/record

# AI 심판
POST   /api/v1/referee/analyze
GET    /api/v1/referee/{game_id}/decisions
POST   /api/v1/referee/replay
PUT    /api/v1/referee/decision/{decision_id}/review
POST   /api/v1/referee/{game_id}/correction    # 인간 교정 이벤트 수신
GET    /api/v1/referee/{game_id}/extractions    # 추출 데이터 현황

# 전술 분석
GET    /api/v1/tactical/{game_id}/formations
GET    /api/v1/tactical/{game_id}/patterns

# 하이라이트 / 비디오
GET    /api/v1/game/{game_id}/highlights
POST   /api/v1/video/clip
POST   /api/v1/video/export

# 메트릭 (Desktop)
GET    /api/v1/metrics/gpu
GET    /api/v1/metrics/thermal
GET    /api/v1/metrics/camera_sync

# Cloud Backend 동기화
POST   /api/v1/sync/realtime/start/{game_id}
POST   /api/v1/sync/realtime/stop/{game_id}
POST   /api/v1/sync/batch/{game_id}
POST   /api/v1/sync/pull/roster
POST   /api/v1/sync/pull/schedule
POST   /api/v1/sync/pull/scouting/{team_id}
```

---

## 10. 배포 환경

| 플랫폼 | 패키징 | 포맷 |
|--------|--------|------|
| Windows | PyInstaller | .exe + NSIS 인스톨러 |
| macOS | PyInstaller + py2app | .app (.dmg) |
| Linux | PyInstaller | AppImage |

**라이선스 유형:**
- 영구 라이선스 (하드웨어 ID 고정)
- 연간/월간 구독 (렌탈 기본)

---

## 11. Phase 의존 규칙

```
game_analysis 내부 Phase 간 임포트 규칙:

Phase 1A (game_management) → Layer 0만 임포트
Phase 1B (event_detection) → Phase 1A + Layer 0~4 임포트
Phase 1C (live_workspace)  → Phase 1A+1B 읽기 전용
Phase 2  (statistics, predictive_models) → Phase 1A+1B+1C
Phase 3  (tactical~ 등 분석 모듈) → Phase 1~2 (Phase 3 모듈 간 직접 임포트 금지)
Phase 4  (출력 모듈) → Phase 1~3
Phase 5  (data_extraction) → Phase 1~4

역방향 금지: Phase 1/2 → Phase 3/4/5 임포트 불가
game_management → event_detection 직접 임포트 금지 (이벤트버스 통해 업데이트)

ai_referee 내부 Phase 간 임포트 규칙:

Phase A (rules/)          → Layer 0만 임포트
Phase B (violations/)     → Phase A + Layer 0 임포트
Phase C (fouls/)          → Phase A + Layer 0 임포트
Phase D (decisions/)      → Phase A~C + Layer 0 임포트
Phase E (data_extraction/) → Phase A~D + Layer 0 (shared.dto) 임포트

역방향 금지: Phase A/B/C → Phase D/E 임포트 불가
상위 레이어 (detection/pose/biomechanics 등) 임포트 절대 금지
```
