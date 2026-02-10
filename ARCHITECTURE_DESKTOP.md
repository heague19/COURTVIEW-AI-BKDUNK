# COURTVIEW 데스크톱 소프트웨어 아키텍처

> **버전**: 1.0.1 (Desktop Edition)
> **기반**: architecture.md v4.3.0
> **최종 수정**: 2026-02-10 (core_foundation 구조 명확화)
> **목적**: 데스크톱 소프트웨어 로컬 AI 서버 (Backend only)
> **배포**: Windows EXE (PyInstaller), macOS App, Linux AppImage

---

## 📋 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [Desktop 전용 범위](#2-desktop-전용-범위)
3. [전체 구조](#3-전체-구조)
4. [카메라 구성 규칙](#4-카메라-구성-규칙)
5. [AI 심판 시스템](#5-ai-심판-시스템)
6. [데이터셋 추출](#6-데이터셋-추출)
7. [API 엔드포인트](#7-api-엔드포인트)
8. [성능 목표](#8-성능-목표)
9. [로컬 실행 환경](#9-로컬-실행-환경)

---

## 1. 프로젝트 개요

### 1.1 목표

```yaml
정확도:
  초기: 88-90% (기학습 모델 + 로컬 GPU)
  학습 후: 92-95% (자가학습 시스템 연동)

성능:
  경기 분석: 25-30 FPS (4대 카메라, GPU 활용)
  AI 심판: 30-35 FPS (실시간 판정)
  처리 시간: 무제한 (로컬 실행)

배포:
  방식: Windows EXE, macOS App, Linux AppImage
  실행: 로컬 GPU 활용 (NVIDIA CUDA, Apple Metal)
  데이터베이스: SQLite (로컬)

비용:
  라이선스: 영구 또는 연간 구독
  운영 비용: $0 (로컬 실행)
```

### 1.2 핵심 기능

| 기능 | 카메라 | 신체 스캔 | 상태 |
|------|--------|----------|------|
| **경기 분석** | 4대+ | ❌ | ✅ 포함 |
| **경기 기록지** | 4대+ | ❌ | ✅ 포함 (2차 스탯) |
| **하이라이트** | 4대+ | ❌ | ✅ 포함 |
| **슛 위치 분석** | 4대+ | ❌ | ✅ 포함 |
| **전술 분석** | 4대+ | ❌ | ✅ 포함 |
| **AI 심판** | 4대+ | ❌ | ✅ 포함 (기본) |
| **비디오 편집** | - | ❌ | ✅ 포함 |
| **데이터셋 추출** | - | ❌ | ✅ 포함 |
| **훈련 분석** | - | - | ❌ 제외 (앱 전용) |
| **정답 영상 비교** | - | - | ❌ 제외 (앱 전용) |
| **자가 학습** | - | - | ❌ 제외 (별도 프로그램) |

---

## 2. Desktop 전용 범위

### 2.1 포함 항목 (✅)

```
[Layer 0] core_foundation (핵심 기반, 60% 경량화)
  ✅ config/ (YAML/ENV 로더, Pydantic 검증)
  ✅ monitoring/ (Loguru 로깅, GPU/CPU 메트릭)
  ✅ exceptions/ (구조화된 예외 계층)
  ❌ registry/ (서비스 레지스트리 - 로컬 불필요)
  ❌ resilience/ (Circuit Breaker - 네트워크 없음)
  ❌ security/ (Secrets Manager - .env 충분)

[Layer 0] shared (공통 유틸리티, core_foundation 외)
  ✅ constants/ (에러 코드, 상태 코드)
  ✅ dto/ (데이터 전송 객체)
  ✅ interfaces/ (인터페이스)
  ✅ utils/ (공통 유틸리티)

[Layer 0.5] configs (설정)
  ✅ base/
  ✅ detection/
  ✅ pose/
  ✅ biomechanics/
  ✅ game_analysis/
  ✅ ai_referee/
  ✅ feedback/
  ✅ multi_camera/
  ✅ environments/ (local.yaml)

[Layer 1] detection (모두 포함, 기학습 완료)
  ✅ ball_detection/ (+ data_extraction/)
  ✅ court_detection/ (+ data_extraction/)
  ✅ player_detection/ (ReID, OCR, Team Classifier + data_extraction/)
  ✅ hoop_detection/ (+ data_extraction/)
  📝 기존 라벨링 도구 및 학습 스크립트 존재

[Layer 1.5] multi_view (모두 포함)
  ✅ core/ (triangulation, epipolar_geometry, view_matcher)
  ✅ fusion/ (object_fusion, pose_fusion, ball_trajectory_fusion, scene_builder)
  ✅ player_identification/ (multi_view_ocr, multi_view_reid, multi_view_tracker)
  ✅ occlusion/ (occlusion_detector, occlusion_resolver)

[Layer 2] pose_estimation (모두 포함)
  ✅ backends/ (MediaPipe, YOLOv8-Pose)
  ✅ keypoint_types.py
  ✅ processing.py
  ✅ validation.py
  ✅ data_extraction/ (농구 특화 학습용)
  📝 YOLO/MediaPipe/ViTPose(고려중) 농구 특화 학습 예정

[Layer 3] biomechanics (모두 포함)
  ✅ kinematics/ (관절 각도, 속도, 가속도, 궤적, 방향, 패턴)
  ✅ dynamics/ (힘, 모멘텀, 에너지, 균형, 충격)
  ✅ anthropometry/ (신체 세그먼트, 연령/성별 어댑터, 비율)
  ✅ standards/ (youth, teen, adult, senior 기준)

[Layer 5] game_analysis (모두 포함, 확장)
  ✅ event_detection/ (shot, pass, rebound, steal, block, turnover)
  ✅ statistics/ (basic_stats, advanced_stats, shot_chart, player_tracker_stats)
  ✅ shot_location/ (shot_zone_mapper, shot_heatmap, efficiency_by_zone)
  ✅ highlight/ (highlight_detector, excitement_scorer, clip_extractor)
  ✅ game_record/ (game_sheet_generator, play_by_play, quarter_summary)
  ✅ tactical_analysis/ (🆕 전술 분석)
    ├── formation_detector.py
    ├── offensive_pattern_analyzer.py
    ├── defensive_pattern_analyzer.py
    ├── spacing_analyzer.py
    ├── ball_movement_analyzer.py
    └── pick_and_roll_detector.py
  ✅ video_editing/ (🆕 비디오 편집)
    ├── clip_manager.py
    ├── annotation_overlay.py
    ├── multi_angle_sync.py
    └── export_manager.py
  ✅ data_extraction/ (경기 데이터 추출)

[Layer 6] ai_referee (✅ 포함!)
  ✅ rules/
    ├── __init__.py
    ├── base_rule.py
    ├── fiba_rules.py        # FIBA 국제농구연맹
    ├── kbl_rules.py         # KBL 한국프로농구
    ✅ nba_rules.py         # NBA 미국프로농구
    ├── nbl_rules.py         # NBL 호주프로농구
    └── rule_loader.py

  ✅ violations/ (바이올레이션 감지)
    ├── __init__.py
    ├── traveling_detector.py
    ├── double_dribble_detector.py
    ├── three_second_detector.py
    ├── five_second_detector.py
    ├── eight_second_detector.py
    ├── twenty_four_second_detector.py
    ├── backcourt_detector.py
    ├── out_of_bounds_detector.py
    └── goaltending_detector.py

  ✅ fouls/ (파울 감지 및 판정)
    ├── __init__.py
    ├── contact_detector.py        # 접촉 감지 (biomechanics 기반)
    ├── blocking_foul_detector.py
    ├── charging_foul_detector.py
    ├── hand_check_detector.py
    ├── holding_foul_detector.py
    ├── illegal_screen_detector.py
    ├── reach_in_detector.py
    └── foul_severity_analyzer.py

  ✅ decisions/ (판정 의사결정)
    ├── __init__.py
    ├── decision_engine.py
    ├── confidence_scorer.py
    ├── multi_angle_validator.py  # 4대 카메라 다각도 검증
    ├── replay_manager.py
    └── decision_explainer.py     # 판정 근거 설명

[Layer 7] feedback_system (부분 포함)
  ✅ generators/
    ├── game_feedback.py         # 경기 피드백
    ├── tactical_feedback.py     # 전술 피드백
    ├── referee_feedback.py      # 심판 피드백
    └── visual_feedback_generator.py

  ✅ templates/
    ├── korean_templates.py
    ├── feedback_formatter.py
    └── severity_mapper.py

  ✅ report/
    ├── game_report_generator.py
    ├── session_summary.py
    ├── progress_tracker.py
    └── trend_analyzer.py

[Layer 9] api_server (로컬 전용)
  ✅ routes/v1/
    ├── game_routes.py
    ├── referee_routes.py       # 🆕 심판 기능
    ├── tactical_routes.py      # 🆕 전술 분석
    ├── video_routes.py         # 🆕 비디오 편집
    ├── feedback_routes.py
    ├── report_routes.py
    ├── task_routes.py
    └── metrics_routes.py

  ✅ middleware/ (rate_limiter 제외)
  ✅ websocket/ (진행 상황 알림)
  ✅ services/
  ✅ services/facades/
  ✅ schemas/

[Layer 10] pipeline (부분 포함)
  ✅ game_pipeline.py
  ✅ referee_pipeline.py        # 🆕 심판 파이프라인
  ✅ tactical_pipeline.py       # 🆕 전술 분석 파이프라인
  ✅ multi_camera_pipeline.py
  ✅ video_editing_pipeline.py  # 🆕 비디오 편집 파이프라인
  ✅ export_pipeline.py

[workers] (부분 포함)
  ✅ video_worker.py
  ✅ analysis_worker.py
  ✅ referee_worker.py          # 🆕 심판 워커
  ✅ notification_worker.py
  ✅ cleanup_worker.py
```

### 2.2 제외 항목 (❌)

```
[Layer 4] motion_analysis (완전 제외)
  ❌ shooting/
  ❌ dribbling/
  ❌ passing/
  ❌ defense/
  ❌ movement/
  ❌ comparison/ (정답 영상 비교)
  ❌ classification/
  ❌ data_extraction/
  → 훈련 분석은 앱 전용 기능

[Layer 8] learning_system (완전 제외)
  ❌ self_learning/ (8개 모듈)
  ❌ adaptive_learning/ (5개 모듈)
  ❌ calibration/ (5개 모듈)
  ❌ data_management/ (3개 모듈)
  ❌ experimentation/ (4개 모듈)
  → 별도 "자가 학습 프로그램"으로 분리

[Layer 10] pipeline
  ❌ training_pipeline.py
  ❌ body_scan_pipeline.py
  ❌ user_scan_pipeline.py
  ❌ learning_pipeline.py

[workers]
  ❌ learning_worker.py
  ❌ user_worker.py

[infrastructure] (클라우드 전용)
  ❌ cache/ (Redis - 로컬은 메모리 캐시)
  ❌ queue/ (Celery - 로컬은 ThreadPool)
  ❌ events/ (EventBus - 로컬은 Observer 패턴)
  ❌ tracing/ (OpenTelemetry - 로컬은 로깅)

[core_foundation] (App Server 대비 60% 경량화)
  ✅ config/ (설정 관리 - 유지)
  ✅ monitoring/ (로깅/메트릭 - 유지)
  ✅ exceptions/ (예외 계층 - 유지)

  ❌ registry/ (서비스 레지스트리 - 제외)
     이유: 단일 프로세스, 직접 import로 충분
     대체: from detection.ball_detector import BallDetector

  ❌ resilience/ (회복탄력성 - 제외)
     이유: 네트워크 호출 없음, 로컬 GPU/파일시스템 직접 접근
     대체: 즉시 에러 표시 (GPU 메모리 부족, SQLite 잠금 등)

  ❌ security/ (보안 모듈 - 제외)
     이유: 단일 사용자, 외부 노출 없음, localhost만 Listen
     대체: .env 파일 + OS 파일 권한
```

---

## 3. 전체 구조

### 3.1 계층 구조 (9-Layer)

```
Layer 0   (core_foundation)    ← 의존성 없음 (config, monitoring, exceptions만)
Layer 0   (shared)             ← core_foundation
Layer 0.5 (configs)            ← Layer 0
Layer 1   (detection)          ← Layer 0, 0.5
Layer 1.5 (multi_view)         ← Layer 0, 0.5, 1
Layer 2   (pose_estimation)    ← Layer 0, 0.5, 1, 1.5
Layer 3   (biomechanics)       ← Layer 0, 0.5, 1, 1.5, 2
❌ Layer 4 (motion_analysis)   ← 제외
Layer 5   (game_analysis)      ← Layer 0, 0.5, 1, 1.5, 2, 3
Layer 6   (ai_referee)         ← Layer 0, 0.5, 1, 1.5, 2, 3, 5 ✅ 포함!
Layer 7   (feedback_system)    ← Layer 0, 0.5, 1, 1.5, 2, 3, 5, 6
❌ Layer 8 (learning_system)   ← 제외
Layer 9   (api_server)         ← 모든 계층 (4, 8 제외)
Layer 10  (pipeline)           ← 모든 계층 (4, 8 제외)

shared    → 모든 계층에서 사용 가능
configs   → 모든 계층에서 사용 가능
workers   ← Layer 0, 0.5, 10
```

**주요 변경점:**
1. ✅ **Layer 6 포함** - AI 심판 기능 (파울, 바이올레이션 판정)
2. ❌ **Layer 4 제외** - motion_analysis (훈련 분석 제외)
3. ✅ **game_analysis 독립성** - detection + pose + biomechanics만으로 작동
4. ✅ **ai_referee → game_analysis** - 심판이 경기 분석 결과 사용

### 3.2 폴더 구조

```
📁 courtview_desktop/
│
├── 📁 core_foundation/         # [Layer 0] 핵심 기반 (60% 경량화)
│   ├── 📁 config/
│   │   ├── __init__.py
│   │   ├── loader.py              # YAML/ENV 로더
│   │   ├── validator.py           # Pydantic 검증
│   │   └── settings.py            # 전역 설정 객체 (Singleton)
│   │
│   ├── 📁 monitoring/
│   │   ├── __init__.py
│   │   ├── logger.py              # Loguru 기반 로거
│   │   ├── metrics.py             # 성능 메트릭 (FPS, GPU 사용률)
│   │   └── profiler.py            # 함수 실행 시간 프로파일링
│   │
│   └── 📁 exceptions/
│       ├── __init__.py
│       ├── base.py                # BaseError
│       ├── hardware.py            # GPUError, CameraError
│       └── validation.py          # ConfigError, DataValidationError
│
├── 📁 shared/                  # [Layer 0] 공통 유틸리티
│   ├── 📁 constants/
│   │   ├── __init__.py
│   │   ├── error_codes.py
│   │   ├── status_codes.py
│   │   └── event_types.py
│   │
│   ├── 📁 dto/
│   │   ├── __init__.py
│   │   ├── game_dto.py
│   │   ├── referee_dto.py             # 🆕 심판 DTO
│   │   ├── tactical_dto.py            # 🆕 전술 DTO
│   │   └── feedback_dto.py
│   │
│   ├── 📁 interfaces/
│   │   ├── __init__.py
│   │   ├── analyzer_interface.py
│   │   ├── detector_interface.py
│   │   └── referee_interface.py       # 🆕 심판 인터페이스
│   │
│   └── 📁 utils/
│       ├── __init__.py
│       ├── local_storage.py           # 로컬 파일 저장
│       ├── gpu_manager.py             # GPU 자원 관리 (CUDA/Metal)
│       └── sqlite_helper.py           # SQLite 헬퍼
│
│   📝 Note: core_foundation/exceptions/ 사용 (shared/exceptions/ 제거)
│
├── 📁 configs/                 # [Layer 0.5] 설정
│   ├── 📁 base/
│   │   ├── base_config.yaml
│   │   └── gpu_config.yaml
│   │
│   ├── 📁 detection/
│   │   ├── ball_detection.yaml
│   │   ├── court_detection.yaml
│   │   ├── player_detection.yaml
│   │   └── hoop_detection.yaml
│   │
│   ├── 📁 pose/
│   │   ├── mediapipe.yaml
│   │   └── yolov8.yaml
│   │
│   ├── 📁 biomechanics/
│   │   ├── kinematics.yaml
│   │   └── dynamics.yaml
│   │
│   ├── 📁 game_analysis/
│   │   ├── event_detection.yaml
│   │   ├── statistics.yaml
│   │   ├── shot_location.yaml
│   │   ├── highlight.yaml
│   │   └── tactical_analysis.yaml
│   │
│   ├── 📁 ai_referee/
│   │   ├── fiba_rules.yaml
│   │   ├── kbl_rules.yaml
│   │   ├── nba_rules.yaml
│   │   ├── nbl_rules.yaml
│   │   ├── violation_thresholds.yaml
│   │   └── foul_criteria.yaml
│   │
│   ├── 📁 feedback/
│   │   ├── game_feedback.yaml
│   │   ├── tactical_feedback.yaml
│   │   └── referee_feedback.yaml
│   │
│   ├── 📁 multi_camera/
│   │   ├── calibration.yaml
│   │   └── fusion.yaml
│   │
│   └── 📁 environments/
│       ├── local.yaml
│       ├── windows.yaml
│       ├── macos.yaml
│       └── linux.yaml
│
├── 📁 detection/               # [Layer 1] 객체 감지 (기학습 완료)
│   ├── 📁 ball_detection/
│   │   ├── __init__.py
│   │   ├── ball_detector.py
│   │   ├── ball_tracker.py
│   │   ├── ball_state.py
│   │   └── 📁 data_extraction/
│   │       ├── __init__.py
│   │       ├── ball_bbox_extractor.py
│   │       └── trajectory_extractor.py
│   │
│   ├── 📁 court_detection/
│   │   ├── __init__.py
│   │   ├── court_detector.py
│   │   ├── court_mapper.py
│   │   ├── zone_classifier.py
│   │   └── 📁 data_extraction/
│   │       ├── __init__.py
│   │       ├── court_line_extractor.py
│   │       └── zone_extractor.py
│   │
│   ├── 📁 player_detection/
│   │   ├── __init__.py
│   │   ├── player_detector.py
│   │   ├── team_classifier.py
│   │   ├── jersey_ocr.py
│   │   ├── reid_module.py
│   │   └── 📁 data_extraction/
│   │       ├── __init__.py
│   │       ├── player_bbox_extractor.py
│   │       ├── reid_extractor.py
│   │       └── ocr_extractor.py
│   │
│   └── 📁 hoop_detection/
│       ├── __init__.py
│       ├── hoop_detector.py
│       ├── net_analyzer.py
│       └── 📁 data_extraction/
│           ├── __init__.py
│           └── hoop_bbox_extractor.py
│
├── 📁 multi_view/              # [Layer 1.5] 멀티뷰 3D 융합
│   ├── __init__.py
│   │
│   ├── 📁 core/
│   │   ├── __init__.py
│   │   ├── triangulation.py
│   │   ├── epipolar_geometry.py
│   │   └── view_matcher.py
│   │
│   ├── 📁 fusion/
│   │   ├── __init__.py
│   │   ├── object_fusion.py
│   │   ├── pose_fusion.py
│   │   ├── ball_trajectory_fusion.py
│   │   └── scene_builder.py
│   │
│   ├── 📁 player_identification/
│   │   ├── __init__.py
│   │   ├── multi_view_ocr.py
│   │   ├── multi_view_reid.py
│   │   ├── multi_view_tracker.py
│   │   └── player_id_manager.py
│   │
│   └── 📁 occlusion/
│       ├── __init__.py
│       ├── occlusion_detector.py
│       └── occlusion_resolver.py
│
├── 📁 pose_estimation/         # [Layer 2] 포즈 추정
│   ├── __init__.py
│   ├── 📁 backends/
│   │   ├── __init__.py
│   │   ├── base_backend.py
│   │   ├── mediapipe_backend.py
│   │   └── yolov8_backend.py
│   ├── keypoint_types.py
│   ├── processing.py
│   ├── validation.py
│   └── 📁 data_extraction/
│       ├── __init__.py
│       ├── keypoint_extractor.py
│       ├── pose_sequence_extractor.py
│       └── basketball_pose_extractor.py
│
├── 📁 biomechanics/            # [Layer 3] 생체역학
│   ├── 📁 kinematics/
│   │   ├── __init__.py
│   │   ├── joint_angle_calculator.py
│   │   ├── velocity_analyzer.py
│   │   ├── acceleration_analyzer.py
│   │   ├── trajectory_analyzer.py
│   │   ├── body_orientation.py
│   │   └── motion_pattern.py
│   │
│   ├── 📁 dynamics/
│   │   ├── __init__.py
│   │   ├── force_estimator.py
│   │   ├── momentum_calculator.py
│   │   ├── energy_analyzer.py
│   │   ├── balance_analyzer.py
│   │   └── impact_analyzer.py
│   │
│   ├── 📁 anthropometry/
│   │   ├── __init__.py
│   │   ├── body_segment.py
│   │   ├── age_gender_adapter.py
│   │   └── proportion_calculator.py
│   │
│   └── 📁 standards/
│       ├── __init__.py
│       ├── youth_standards.py
│       ├── teen_standards.py
│       ├── adult_standards.py
│       └── senior_standards.py
│
├── 📁 game_analysis/           # [Layer 5] 경기 분석
│   ├── 📁 event_detection/
│   │   ├── __init__.py
│   │   ├── shot_event_detector.py
│   │   ├── score_detector.py
│   │   ├── rebound_detector.py
│   │   ├── steal_detector.py
│   │   ├── block_detector.py
│   │   └── turnover_detector.py
│   │
│   ├── 📁 statistics/
│   │   ├── __init__.py
│   │   ├── basic_stats.py
│   │   ├── advanced_stats.py
│   │   ├── shot_chart.py
│   │   └── player_tracker_stats.py
│   │
│   ├── 📁 shot_location/
│   │   ├── __init__.py
│   │   ├── shot_zone_mapper.py
│   │   ├── shot_heatmap.py
│   │   └── efficiency_by_zone.py
│   │
│   ├── 📁 highlight/
│   │   ├── __init__.py
│   │   ├── highlight_detector.py
│   │   ├── excitement_scorer.py
│   │   └── clip_extractor.py
│   │
│   ├── 📁 game_record/
│   │   ├── __init__.py
│   │   ├── game_sheet_generator.py
│   │   ├── play_by_play.py
│   │   └── quarter_summary.py
│   │
│   ├── 📁 tactical_analysis/   # 🆕 전술 분석
│   │   ├── __init__.py
│   │   ├── formation_detector.py        # 포메이션 감지 (3-2, 2-3, 1-3-1 등)
│   │   ├── offensive_pattern_analyzer.py # 공격 패턴 (픽앤롤, 아이솔레이션, 포스트업)
│   │   ├── defensive_pattern_analyzer.py # 수비 패턴 (맨투맨, 존, 프레스)
│   │   ├── spacing_analyzer.py          # 스페이싱 분석
│   │   ├── ball_movement_analyzer.py    # 볼 무브먼트
│   │   └── pick_and_roll_detector.py    # 픽앤롤 감지
│   │
│   ├── 📁 video_editing/       # 🆕 비디오 편집
│   │   ├── __init__.py
│   │   ├── clip_manager.py              # 클립 관리
│   │   ├── annotation_overlay.py        # 주석 오버레이 (선, 화살표, 텍스트)
│   │   ├── multi_angle_sync.py          # 다각도 동기화
│   │   └── export_manager.py            # 내보내기 관리 (MP4, MOV, AVI)
│   │
│   └── 📁 data_extraction/
│       ├── __init__.py
│       ├── shot_trajectory_extractor.py
│       ├── player_bbox_extractor.py
│       ├── court_line_extractor.py
│       └── foul_scene_extractor.py
│
├── 📁 ai_referee/              # [Layer 6] AI 심판 ✅ 포함!
│   ├── 📁 rules/
│   │   ├── __init__.py
│   │   ├── base_rule.py
│   │   ├── fiba_rules.py               # FIBA 국제농구연맹
│   │   ├── kbl_rules.py                # KBL 한국프로농구
│   │   ├── nba_rules.py                # NBA 미국프로농구
│   │   ├── nbl_rules.py                # NBL 호주프로농구
│   │   └── rule_loader.py
│   │
│   ├── 📁 violations/          # 바이올레이션 감지
│   │   ├── __init__.py
│   │   ├── traveling_detector.py       # 트래블링
│   │   ├── double_dribble_detector.py  # 더블 드리블
│   │   ├── three_second_detector.py    # 3초 룰
│   │   ├── five_second_detector.py     # 5초 룰
│   │   ├── eight_second_detector.py    # 8초 룰
│   │   ├── twenty_four_second_detector.py # 24초 룰
│   │   ├── backcourt_detector.py       # 백코트 바이올레이션
│   │   ├── out_of_bounds_detector.py   # 아웃 오브 바운즈
│   │   └── goaltending_detector.py     # 골텐딩
│   │
│   ├── 📁 fouls/               # 파울 감지 및 판정
│   │   ├── __init__.py
│   │   ├── contact_detector.py         # 접촉 감지 (biomechanics 기반)
│   │   ├── blocking_foul_detector.py   # 블로킹 파울
│   │   ├── charging_foul_detector.py   # 차징 파울
│   │   ├── hand_check_detector.py      # 핸드 체크
│   │   ├── holding_foul_detector.py    # 홀딩 파울
│   │   ├── illegal_screen_detector.py  # 일리걸 스크린
│   │   ├── reach_in_detector.py        # 리치 인
│   │   └── foul_severity_analyzer.py   # 파울 심각도 분석
│   │
│   └── 📁 decisions/           # 판정 의사결정
│       ├── __init__.py
│       ├── decision_engine.py           # 판정 엔진
│       ├── confidence_scorer.py         # 신뢰도 점수
│       ├── multi_angle_validator.py     # 다각도 검증 (4대 카메라)
│       ├── replay_manager.py            # 리플레이 관리
│       └── decision_explainer.py        # 판정 근거 설명
│
├── 📁 feedback_system/         # [Layer 7] 피드백 시스템
│   ├── 📁 generators/
│   │   ├── __init__.py
│   │   ├── game_feedback.py
│   │   ├── tactical_feedback.py        # 🆕 전술 피드백
│   │   ├── referee_feedback.py         # 🆕 심판 피드백
│   │   └── visual_feedback_generator.py
│   │
│   ├── 📁 templates/
│   │   ├── __init__.py
│   │   ├── korean_templates.py
│   │   ├── feedback_formatter.py
│   │   └── severity_mapper.py
│   │
│   └── 📁 report/
│       ├── __init__.py
│       ├── game_report_generator.py
│       ├── session_summary.py
│       ├── progress_tracker.py
│       └── trend_analyzer.py
│
├── 📁 api_server/              # [Layer 9] API 서버 (로컬)
│   ├── 📁 routes/
│   │   ├── __init__.py
│   │   ├── 📁 v1/
│   │   │   ├── __init__.py
│   │   │   ├── game_routes.py
│   │   │   ├── referee_routes.py       # 🆕 심판 기능
│   │   │   ├── tactical_routes.py      # 🆕 전술 분석
│   │   │   ├── video_routes.py         # 🆕 비디오 편집
│   │   │   ├── feedback_routes.py
│   │   │   ├── report_routes.py
│   │   │   ├── task_routes.py
│   │   │   └── metrics_routes.py
│   │   └── health_routes.py
│   │
│   ├── 📁 middleware/
│   │   ├── __init__.py
│   │   ├── request_validator.py
│   │   ├── cors_middleware.py
│   │   └── error_handler.py
│   │
│   ├── 📁 websocket/
│   │   ├── __init__.py
│   │   ├── connection_manager.py
│   │   └── progress_handler.py
│   │
│   ├── 📁 services/
│   │   ├── __init__.py
│   │   ├── video_service.py
│   │   ├── game_service.py
│   │   ├── referee_service.py          # 🆕 심판 서비스
│   │   ├── tactical_service.py         # 🆕 전술 서비스
│   │   ├── feedback_service.py
│   │   ├── report_service.py
│   │   ├── task_service.py
│   │   └── export_service.py
│   │
│   ├── 📁 services/facades/
│   │   ├── __init__.py
│   │   ├── game_stats_facade.py
│   │   ├── referee_facade.py           # 🆕 심판 파사드
│   │   ├── tactical_facade.py          # 🆕 전술 파사드
│   │   ├── highlight_facade.py
│   │   └── report_facade.py
│   │
│   ├── 📁 schemas/
│   │   ├── __init__.py
│   │   ├── request_schemas.py
│   │   └── response_schemas.py
│   │
│   └── main.py
│
├── 📁 pipeline/                # [Layer 10] 파이프라인
│   ├── __init__.py
│   ├── base_pipeline.py
│   ├── video_pipeline.py
│   ├── game_pipeline.py
│   ├── referee_pipeline.py             # 🆕 심판 파이프라인
│   ├── tactical_pipeline.py            # 🆕 전술 분석 파이프라인
│   ├── multi_camera_pipeline.py
│   ├── video_editing_pipeline.py       # 🆕 비디오 편집 파이프라인
│   └── export_pipeline.py
│
├── 📁 workers/
│   ├── __init__.py
│   ├── base_worker.py
│   ├── video_worker.py
│   ├── analysis_worker.py
│   ├── referee_worker.py               # 🆕 심판 워커
│   ├── notification_worker.py
│   ├── cleanup_worker.py
│   └── scheduler.py
│
├── 📁 database/                # SQLite 데이터베이스
│   ├── __init__.py
│   ├── models.py                       # SQLAlchemy 모델
│   ├── migrations/                     # Alembic 마이그레이션
│   └── courtview.db                    # SQLite DB 파일
│
├── 📁 storage/                 # 로컬 파일 저장소
│   ├── videos/                         # 입력 비디오
│   ├── outputs/                        # 출력 결과
│   ├── exports/                        # 내보내기 파일
│   ├── datasets/                       # 추출 데이터셋
│   └── logs/                           # 로그 파일
│
├── 📁 tests/
│   ├── 📁 unit/
│   ├── 📁 integration/
│   └── 📁 performance/
│
├── 📁 deployment/
│   ├── 📁 windows/
│   │   ├── build.bat
│   │   ├── installer.nsi
│   │   └── icon.ico
│   ├── 📁 macos/
│   │   ├── build.sh
│   │   ├── Info.plist
│   │   └── icon.icns
│   └── 📁 linux/
│       ├── build.sh
│       ├── AppImage.yaml
│       └── icon.png
│
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 4. 카메라 구성 규칙

### 4.1 경기 분석 (필수 4대+)

```yaml
멀티 카메라 (4대+, 필수):
  용도: 경기 분석, AI 심판, 전술 분석
  정확도: 90-92%
  FPS: 25-30 (로컬 GPU)
  처리 흐름:
    - Detection (2D × 4+)
    - Pose Estimation (2D × 4+)
    - Multi-view Fusion (3D)
    - Player Identification (ReID, OCR)
    - Game Events (shot, pass, rebound, steal)
    - AI Referee (foul, violation)
    - Tactical Analysis (formation, pattern)
    - Statistics
    - Game Record

필수 배치 (4대):
  - 카메라 1: 코트 코너 1 (대각선 시야)
  - 카메라 2: 코트 코너 2 (대각선 시야)
  - 카메라 3: 사이드 라인 중앙 (측면)
  - 카메라 4: 엔드 라인 중앙 (정면)

권장 배치 (6대):
  - 기본 4대 +
  - 카메라 5: 림 후방 (백보드 뷰, 골텐딩 판정)
  - 카메라 6: 반대 림 후방

최적 배치 (8대):
  - 기본 6대 +
  - 카메라 7: 타임라인 상단 (전체 뷰)
  - 카메라 8: 반대 타임라인 상단
```

### 4.2 카메라 요구사항

```yaml
최소 사양:
  해상도: 1920×1080 (Full HD)
  FPS: 30 FPS
  렌즈: 광각 (FOV 90° 이상)
  동기화: 하드웨어 동기화 또는 타임스탬프

권장 사양:
  해상도: 2560×1440 (2K) 또는 3840×2160 (4K)
  FPS: 60 FPS
  렌즈: 광각 (FOV 100-120°)
  동기화: Genlock 하드웨어 동기화
  센서: 글로벌 셔터

지원 포맷:
  - MP4 (H.264, H.265)
  - MOV (ProRes, H.264)
  - AVI (MJPEG, DivX)
  - MKV (H.264, VP9)
```

---

## 5. AI 심판 시스템

### 5.1 목적

```
경기 중 파울, 바이올레이션 실시간 판정 (4대 이상 카메라 기반)

지원 리그:
1. FIBA (국제농구연맹)
2. KBL (한국프로농구)
3. NBA (미국프로농구)
4. NBL (호주프로농구)

주요 기능:
1. 바이올레이션 감지 (트래블링, 더블 드리블, 3초, 5초, 8초, 24초, 백코트, 아웃, 골텐딩)
2. 파울 판정 (블로킹, 차징, 핸드 체크, 홀딩, 일리걸 스크린, 리치 인)
3. 다각도 검증 (4대 카메라 크로스 체크)
4. 판정 근거 설명 (AI 해석 가능성)
```

### 5.2 판정 프로세스

```python
# ai_referee/decisions/decision_engine.py

class DecisionEngine:
    """판정 의사결정 엔진"""

    async def make_decision(
        self,
        event_type: str,
        multi_view_data: List[ViewData],
        biomechanics_data: BiomechanicsData,
        rule_set: str = "FIBA"
    ) -> RefereeDecision:
        """
        다각도 AI 심판 판정

        입력:
        - event_type: "blocking_foul", "charging_foul", "traveling" 등
        - multi_view_data: 4대 카메라 데이터
        - biomechanics_data: 생체역학 데이터 (접촉 감지, 힘 분석)
        - rule_set: "FIBA", "KBL", "NBA", "NBL"

        출력:
        {
            "decision_id": "DEC_20260210_001",
            "event_type": "blocking_foul",
            "timestamp": 125.3,              # 초
            "quarter": 2,
            "game_time": "05:23",

            "call": "DEFENSIVE_FOUL",        # OFFENSIVE_FOUL, NO_CALL, PLAY_ON
            "player_id": "P07",
            "opponent_id": "P23",

            "confidence": 0.87,              # 0-1
            "severity": "COMMON",            # COMMON, TECHNICAL, FLAGRANT

            "multi_angle_agreement": 0.92,   # 4대 카메라 일치도
            "view_scores": {
                "cam1": 0.89,
                "cam2": 0.94,
                "cam3": 0.91,
                "cam4": 0.95
            },

            "biomechanics_evidence": {
                "contact_detected": True,
                "contact_force": 120.5,      # N (뉴턴)
                "contact_location": "chest",
                "defender_moving": True,
                "offensive_established": True
            },

            "rule_violation": {
                "rule_id": "FIBA_37.1.1",
                "description": "수비수가 법적 수비 위치를 확립하지 못함"
            },

            "explanation": "수비수 P07이 공격수 P23과 접촉 시 여전히 움직이고 있었으며, 법적 수비 위치를 확립하지 못했습니다. 4대 카메라 모두 동일한 판정을 지지합니다.",

            "replay_clips": [
                {
                    "camera_id": "cam1",
                    "start_time": 124.8,
                    "end_time": 126.0,
                    "file_path": "replays/DEC_20260210_001_cam1.mp4"
                },
                {
                    "camera_id": "cam2",
                    "start_time": 124.8,
                    "end_time": 126.0,
                    "file_path": "replays/DEC_20260210_001_cam2.mp4"
                }
            ],

            "created_at": "2026-02-10T15:30:25Z"
        }
        """
        # Step 1: 각 카메라별 판정
        cam_decisions = []
        for view in multi_view_data:
            decision = await self._analyze_single_view(view, event_type, rule_set)
            cam_decisions.append(decision)

        # Step 2: 생체역학 분석 (접촉 감지, 힘 분석)
        biomech_result = self._analyze_biomechanics(biomechanics_data, event_type)

        # Step 3: 다각도 합의 계산
        agreement = self._calculate_agreement(cam_decisions)

        # Step 4: 최종 판정 (4대 카메라 + 생체역학)
        final_call = self._make_final_call(cam_decisions, biomech_result, agreement)

        # Step 5: 판정 근거 생성
        explanation = self._generate_explanation(final_call, cam_decisions, biomech_result)

        # Step 6: 리플레이 클립 추출
        clips = await self._extract_replay_clips(multi_view_data, final_call)

        return RefereeDecision(
            call=final_call,
            confidence=agreement,
            explanation=explanation,
            replay_clips=clips,
            biomechanics_evidence=biomech_result
        )
```

### 5.3 주요 판정 유형

#### 5.3.1 블로킹 vs 차징 판정

```python
# ai_referee/fouls/blocking_foul_detector.py

class BlockingFoulDetector:
    """블로킹 파울 감지 (수비 파울)"""

    def detect(self, contact_event, multi_view_data, biomechanics_data):
        """
        블로킹 파울 조건 (FIBA 37.1.1):
        1. 수비수가 법적 수비 위치를 확립하지 못함
        2. 접촉 시 수비수가 여전히 움직이고 있음
        3. 공격수가 이미 슛 동작 시작

        생체역학 근거:
        - 수비수 속도 > 0.5 m/s (여전히 움직임)
        - 접촉 지점: 수비수 측면/뒷면 (정면 아님)
        - 접촉 힘: 공격수 → 수비수 방향
        """
        # Step 1: 수비수 움직임 분석
        defender_velocity = biomechanics_data.defender_velocity
        defender_moving = defender_velocity > 0.5  # m/s

        # Step 2: 법적 수비 위치 확립 시점
        legal_position_time = self._find_legal_position_time(multi_view_data)
        contact_time = contact_event.timestamp

        # Step 3: 공격수 슛 동작 시작 시점
        offensive_committed = biomechanics_data.offensive_committed_time

        # Step 4: 판정
        if defender_moving and (contact_time < legal_position_time):
            return "BLOCKING_FOUL"
        elif not defender_moving and (legal_position_time < offensive_committed):
            return "NO_CALL"  # 합법적 수비
        else:
            return "UNCERTAIN"  # 추가 분석 필요


# ai_referee/fouls/charging_foul_detector.py

class ChargingFoulDetector:
    """차징 파울 감지 (공격 파울)"""

    def detect(self, contact_event, multi_view_data, biomechanics_data):
        """
        차징 파울 조건 (FIBA 37.1.1):
        1. 수비수가 법적 수비 위치를 확립함
        2. 접촉 시 수비수가 정지 상태 (또는 뒤로 이동)
        3. 공격수가 수비수에게 돌진

        생체역학 근거:
        - 수비수 속도 <= 0.5 m/s (정지) 또는 음수 (뒤로)
        - 접촉 지점: 수비수 정면 (가슴/복부)
        - 접촉 힘: 공격수 → 수비수 방향 (큰 힘)
        """
        pass
```

#### 5.3.2 트래블링 감지

```python
# ai_referee/violations/traveling_detector.py

class TravelingDetector:
    """트래블링 감지"""

    def detect(self, player_motion, ball_state, rule_set="FIBA"):
        """
        트래블링 조건:
        1. 드리블 없이 3스텝 이상 (FIBA: 2스텝)
        2. 피벗 풋 이동
        3. 점프 후 착지 전 드리블 안함

        포즈 추정 기반 스텝 카운팅:
        - 발목(ankle) 키포인트 y좌표 변화
        - 발이 지면에서 떨어진 순간 카운트
        - 드리블 상태와 동기화
        """
        # Step 1: 스텝 카운팅
        steps = self._count_steps(player_motion.pose_sequence)

        # Step 2: 드리블 상태
        dribbling = ball_state.is_dribbling

        # Step 3: 판정
        max_steps = 2 if rule_set == "FIBA" else 2.5  # NBA는 2.5 스텝

        if not dribbling and steps > max_steps:
            return "TRAVELING"
        else:
            return "NO_VIOLATION"
```

#### 5.3.3 골텐딩 감지

```python
# ai_referee/violations/goaltending_detector.py

class GoaltendingDetector:
    """골텐딩 감지"""

    def detect(self, ball_trajectory, rim_position, player_hand_position):
        """
        골텐딩 조건 (FIBA 31.2.4):
        1. 볼이 림 위 실린더 내부에 있을 때 터치
        2. 볼이 하강 궤적일 때 터치 (림 위)
        3. 볼이 백보드에 닿은 후 림으로 향할 때 터치

        물리 기반 판정:
        - 림 실린더: 반지름 22.5cm, 높이 45cm
        - 볼 궤적: 포물선 방정식 (physics-based)
        - 하강 여부: dy/dt < 0
        """
        # Step 1: 볼이 림 실린더 내부인지 확인
        in_cylinder = self._check_rim_cylinder(ball_trajectory, rim_position)

        # Step 2: 볼이 하강 중인지 확인
        descending = ball_trajectory.velocity_y < 0

        # Step 3: 선수 손이 볼에 닿았는지 확인
        contact = self._check_ball_hand_contact(ball_trajectory, player_hand_position)

        # Step 4: 판정
        if in_cylinder and descending and contact:
            return "GOALTENDING"
        else:
            return "NO_VIOLATION"
```

### 5.4 다각도 검증

```python
# ai_referee/decisions/multi_angle_validator.py

class MultiAngleValidator:
    """다각도 검증 (4대 카메라)"""

    def validate(self, event, cam_decisions):
        """
        4대 카메라 판정 일치도 계산

        예시:
        - cam1: BLOCKING_FOUL (0.89)
        - cam2: BLOCKING_FOUL (0.94)
        - cam3: BLOCKING_FOUL (0.91)
        - cam4: NO_CALL (0.65)

        → 일치도: 3/4 = 0.75
        → 평균 신뢰도: (0.89 + 0.94 + 0.91) / 3 = 0.91
        → 최종 판정: BLOCKING_FOUL (신뢰도 0.91)
        """
        # Step 1: 각 카메라 판정 집계
        decision_counts = {}
        for cam_id, decision in cam_decisions.items():
            call = decision['call']
            confidence = decision['confidence']

            if call not in decision_counts:
                decision_counts[call] = {'count': 0, 'total_confidence': 0}

            decision_counts[call]['count'] += 1
            decision_counts[call]['total_confidence'] += confidence

        # Step 2: 다수결 판정
        majority_call = max(decision_counts, key=lambda x: decision_counts[x]['count'])
        majority_count = decision_counts[majority_call]['count']

        # Step 3: 일치도 계산
        agreement = majority_count / len(cam_decisions)

        # Step 4: 평균 신뢰도
        avg_confidence = decision_counts[majority_call]['total_confidence'] / majority_count

        # Step 5: 최종 판정 (일치도 >= 0.75이면 채택)
        if agreement >= 0.75:
            return {
                'call': majority_call,
                'confidence': avg_confidence,
                'agreement': agreement,
                'status': 'CONFIRMED'
            }
        else:
            return {
                'call': None,
                'confidence': 0.0,
                'agreement': agreement,
                'status': 'UNCERTAIN'
            }
```

---

## 6. 데이터셋 추출

### 6.1 목적

```
Desktop에서 수집한 데이터를 자가학습 프로그램에 전달

추출 위치:
1. detection/*/data_extraction/ (Layer 1)
   - 객체 감지 모델 재학습용 데이터

2. pose_estimation/data_extraction/ (Layer 2)
   - 농구 특화 포즈 학습용 데이터

3. game_analysis/data_extraction/ (Layer 5)
   - 경기 중 이벤트 데이터
   - 파울 장면 데이터 (AI 심판 학습용)

저장 위치:
- 로컬: storage/datasets/
- 외부: USB, 네트워크 드라이브, 클라우드 (선택)

추출 대상:
1. Detection 데이터:
   - 공, 코트, 선수, 림 (고신뢰도 샘플)

2. Pose 데이터:
   - 농구 특화 키포인트 시퀀스

3. Game 데이터:
   - 경기 이벤트 (슛, 패스, 리바운드)
   - 파울 장면 (사용자 확인 완료)
   - 바이올레이션 장면
```

### 6.2 로컬 저장 구조

```
storage/datasets/
├── detection/
│   ├── ball/
│   │   ├── 2026-02-10/
│   │   │   ├── images/
│   │   │   ├── labels/
│   │   │   └── metadata.json
│   │   └── ...
│   ├── court/
│   ├── player/
│   │   ├── reid/
│   │   └── ocr/
│   └── hoop/
│
├── pose/
│   ├── basketball_poses/
│   │   ├── 2026-02-10/
│   │   │   ├── sequences/
│   │   │   ├── annotations/
│   │   │   └── metadata.json
│   │   └── ...
│   └── ...
│
└── game/
    ├── events/
    │   ├── shots/
    │   ├── passes/
    │   └── rebounds/
    ├── fouls/
    │   ├── blocking/
    │   ├── charging/
    │   └── hand_check/
    └── violations/
        ├── traveling/
        ├── double_dribble/
        └── goaltending/
```

---

## 7. API 엔드포인트

### 7.1 로컬 서버 구성

```yaml
서버:
  호스트: localhost (127.0.0.1)
  포트: 8000 (기본), 사용자 설정 가능
  프로토콜: HTTP (로컬 전용)
  CORS: 허용 (Frontend 통신)

인증:
  없음 (로컬 실행)

WebSocket:
  진행 상황 알림: ws://localhost:8000/ws/progress/{task_id}
```

### 7.2 주요 엔드포인트

```
# 경기 분석
POST   /api/v1/game/analyze                 # 경기 분석 시작
GET    /api/v1/game/{game_id}/status        # 분석 상태 조회
GET    /api/v1/game/{game_id}/result        # 분석 결과 조회
GET    /api/v1/game/{game_id}/stats         # 경기 통계
GET    /api/v1/game/{game_id}/record        # 경기 기록지

# AI 심판
POST   /api/v1/referee/analyze               # 심판 판정 시작
GET    /api/v1/referee/{game_id}/decisions   # 전체 판정 목록
GET    /api/v1/referee/decision/{decision_id} # 개별 판정 상세
POST   /api/v1/referee/replay                # 리플레이 요청
PUT    /api/v1/referee/decision/{decision_id}/review # 판정 검토

# 전술 분석
GET    /api/v1/tactical/{game_id}/formations  # 포메이션 분석
GET    /api/v1/tactical/{game_id}/patterns    # 패턴 분석
GET    /api/v1/tactical/{game_id}/spacing     # 스페이싱 분석
GET    /api/v1/tactical/{game_id}/ball_movement # 볼 무브먼트

# 하이라이트
GET    /api/v1/game/{game_id}/highlights     # 하이라이트 목록
POST   /api/v1/game/{game_id}/highlight/create # 하이라이트 생성
GET    /api/v1/game/{game_id}/highlight/{clip_id}/download # 다운로드

# 슛 위치
GET    /api/v1/game/{game_id}/shot_chart     # 슛 차트
GET    /api/v1/game/{game_id}/shot_heatmap   # 슛 히트맵
GET    /api/v1/game/{game_id}/shot_efficiency # 위치별 효율

# 비디오 편집
POST   /api/v1/video/clip                    # 클립 생성
POST   /api/v1/video/annotate                # 주석 추가
POST   /api/v1/video/sync                    # 다각도 동기화
POST   /api/v1/video/export                  # 내보내기

# 피드백
GET    /api/v1/feedback/{game_id}/game       # 경기 피드백
GET    /api/v1/feedback/{game_id}/tactical   # 전술 피드백
GET    /api/v1/feedback/{game_id}/referee    # 심판 피드백

# 리포트
GET    /api/v1/report/{game_id}/summary      # 경기 요약
GET    /api/v1/report/{game_id}/pdf          # PDF 리포트

# 작업 관리
GET    /api/v1/task/{task_id}/status         # 작업 상태
POST   /api/v1/task/{task_id}/cancel         # 작업 취소

# 건강 체크
GET    /health                                # 서버 상태
GET    /api/v1/metrics/gpu                   # GPU 사용률
GET    /api/v1/metrics/storage               # 저장소 용량
```

---

## 8. 성능 목표

### 8.1 처리 성능

```yaml
경기 분석:
  FPS: 25-30 (4대 카메라, GPU 활용)
  정확도: 90-92%
  지연 시간: 무제한 (로컬 실행)

AI 심판:
  FPS: 30-35 (실시간 판정)
  정확도: 88-90% (파울), 92-95% (바이올레이션)
  판정 시간: < 3초 (다각도 검증 포함)

전술 분석:
  FPS: 20-25
  정확도: 85-88%
  분석 시간: 무제한

하이라이트:
  생성 시간: < 5분 (1시간 경기 기준)
  정확도: 90-92%

비디오 편집:
  렌더링: 실시간 또는 고품질 (사용자 선택)
  내보내기: H.264 (빠름), ProRes (고품질)
```

### 8.2 GPU 요구사항

```yaml
최소 사양:
  GPU: NVIDIA GTX 1660 (6GB) 또는 동급
  VRAM: 6GB
  CUDA: 11.0+
  성능: 15-20 FPS (4대 카메라)

권장 사양:
  GPU: NVIDIA RTX 3060 (12GB) 또는 동급
  VRAM: 12GB
  CUDA: 11.8+
  성능: 25-30 FPS (4대 카메라)

최적 사양:
  GPU: NVIDIA RTX 4070 Ti (12GB) 또는 동급
  VRAM: 12GB+
  CUDA: 12.0+
  성능: 30-35 FPS (4대 카메라)

macOS:
  GPU: Apple M1 Pro/Max/Ultra, M2 Pro/Max/Ultra
  Metal: 지원
  성능: 20-30 FPS (통합 메모리 활용)
```

### 8.3 저장소 요구사항

```yaml
최소:
  HDD/SSD: 500GB
  비디오: 1시간 경기 ≈ 50GB (4대 카메라, 1080p)
  결과: 1시간 경기 ≈ 5GB (분석 결과, 하이라이트)

권장:
  SSD: 1TB (NVMe)
  비디오: 여유 공간 확보
  데이터셋: 별도 외장 HDD (2TB+)
```

---

## 9. 로컬 실행 환경

### 9.1 실행 방식

```yaml
Windows:
  패키징: PyInstaller
  포맷: .exe (단일 실행 파일 또는 폴더)
  설치: 인스톨러 (NSIS)
  의존성: 포함 (Python 런타임, CUDA 라이브러리)

macOS:
  패키징: PyInstaller + py2app
  포맷: .app (애플리케이션 번들)
  설치: .dmg 디스크 이미지
  의존성: 포함 (Python 런타임, Metal)

Linux:
  패키징: PyInstaller
  포맷: AppImage (단일 실행 파일)
  설치: 복사 및 실행 권한 부여
  의존성: 포함 (Python 런타임, CUDA)
```

### 9.2 데이터베이스

```yaml
SQLite:
  파일: database/courtview.db
  마이그레이션: Alembic
  백업: 자동 (일일, 주간)

테이블:
  - games (경기 정보)
  - players (선수 정보)
  - events (경기 이벤트)
  - decisions (심판 판정)
  - statistics (통계)
  - highlights (하이라이트)
  - tasks (작업 관리)
```

### 9.3 설정 파일

```yaml
.env:
  # 서버 설정
  SERVER_HOST=127.0.0.1
  SERVER_PORT=8000

  # GPU 설정
  CUDA_VISIBLE_DEVICES=0
  GPU_MEMORY_FRACTION=0.9

  # 저장소 설정
  STORAGE_PATH=./storage
  VIDEO_PATH=./storage/videos
  OUTPUT_PATH=./storage/outputs
  DATASET_PATH=./storage/datasets

  # 카메라 설정
  MIN_CAMERAS=4
  MAX_CAMERAS=8

  # AI 심판 설정
  DEFAULT_RULE_SET=FIBA
  CONFIDENCE_THRESHOLD=0.75
  MULTI_ANGLE_THRESHOLD=0.75

  # 성능 설정
  TARGET_FPS=30
  BATCH_SIZE=4
  NUM_WORKERS=4
```

### 9.4 로그

```yaml
위치:
  - storage/logs/app.log (애플리케이션 로그)
  - storage/logs/error.log (에러 로그)
  - storage/logs/access.log (API 액세스 로그)

레벨:
  개발: DEBUG
  프로덕션: INFO

로테이션:
  크기: 100MB
  보관: 30일
```

---

## 10. 프론트엔드 통신

### 10.1 통신 방식

```yaml
REST API:
  - 경기 분석 시작/조회
  - 심판 판정 조회
  - 전술 분석 조회
  - 비디오 편집
  - 리포트 생성

WebSocket:
  - 분석 진행 상황 (실시간)
  - 심판 판정 알림 (실시간)
  - GPU 사용률 모니터링
```

### 10.2 프론트엔드 요구사항

```
1. localhost:8000 API 호출
2. WebSocket 연결 (진행 상황)
3. 파일 업로드 (멀티파트)
4. 비디오 플레이어 (MP4, MOV 재생)
5. 리플레이 뷰어 (다각도 동기화)
```

---

## 11. 배포 프로세스

### 11.1 빌드

```bash
# Windows
cd deployment/windows
build.bat

# macOS
cd deployment/macos
./build.sh

# Linux
cd deployment/linux
./build.sh
```

### 11.2 패키징

```yaml
포함 파일:
  - courtview_desktop/ (소스 코드)
  - configs/ (설정 파일)
  - database/ (빈 DB)
  - storage/ (빈 폴더)
  - requirements.txt
  - .env.example

제외 파일:
  - tests/
  - .git/
  - __pycache__/
  - *.pyc
```

### 11.3 라이선스 검증

```python
# 애플리케이션 시작 시 라이선스 확인
class LicenseValidator:
    def validate(self):
        """
        라이선스 유형:
        1. 영구 라이선스 (하드웨어 ID 기반)
        2. 연간 구독 (만료일 확인)
        3. 체험판 (30일 제한)
        """
        pass
```

---

## 12. 다음 단계

```
1. Desktop 전용 Import Spec 작성
   - PHASE_XX_DESKTOP_IMPORT_SPEC.md
   - Layer 4 제외, Layer 6 포함 반영

2. AI 심판 모듈 상세 설계
   - FIBA/KBL/NBA/NBL 규칙 정의
   - 파울/바이올레이션 판정 로직

3. 전술 분석 모듈 설계
   - 포메이션 감지 알고리즘
   - 공격/수비 패턴 분류

4. 비디오 편집 모듈 설계
   - 주석 오버레이 (선, 화살표, 텍스트)
   - 다각도 동기화 재생

5. 프론트엔드 통합 가이드
   - API 사용 예제
   - WebSocket 연결 예제
```

---

## 부록: App Server와의 core_foundation 차이

| 모듈 | App Server | Desktop | 이유 |
|------|-----------|---------|------|
| **config/** | ✅ Consul 연동, 동적 reload | ✅ .env + YAML (정적) | 로컬 실행, 재시작으로 충분 |
| **monitoring/** | ✅ Prometheus, OpenTelemetry | ✅ Loguru, 로컬 메트릭 | 분산 추적 불필요 |
| **exceptions/** | ✅ 전체 예외 계층 | ✅ 동일 구조 | 에러 처리는 동일 |
| **registry/** | ✅ Service Registry, Model Registry, DI | ❌ 제외 | 단일 프로세스, 직접 import |
| **resilience/** | ✅ Circuit Breaker, Retry, Rate Limiter | ❌ 제외 | 네트워크 호출 없음 |
| **security/** | ✅ Secrets Manager, Audit Logger, API Key | ❌ 제외 | 단일 사용자, 외부 노출 없음 |

**크기 비교:**
- App Server: 15개 모듈, ~3,000줄, ~200MB 메모리
- Desktop: 6개 모듈 (3 포함 + 3 제외), ~1,200줄, ~50MB 메모리
- **60% 경량화** 달성

---

**문서 버전 이력**:
- v1.0.0 (2026-02-10): Desktop Edition 초판
- v1.0.1 (2026-02-10): core_foundation 구조 명확화
  - Layer 0: shared → core_foundation + shared로 분리
  - registry, resilience, security 제외 이유 명시
  - App Server 대비 60% 경량화 설명 추가
  - LAYER0_CORE_FOUNDATION.md 참조 문서 연결

**다음 업데이트**: Desktop Import Spec 작성 후
