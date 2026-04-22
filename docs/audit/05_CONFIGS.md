# Phase 5: configs/ 감사 보고서

> **감사자**: SPOIN_COURTVIEW AI 감사팀
> **작성일**: 2026-04-20
> **감사 대상**: `configs/` **42 YAML 파일** (6,502 라인)
> **감사 범위 외**: `configs/calibration/*.json` 27개 (설치 시 생성되는 캘리브레이션 아티팩트, 데이터)
> **감사 기준**: 사용자 8축 (YAML 감사 특성 반영)
> **감사 방식**: **Read 도구 42/42 전수 직독 (100%)**

---

## 0. 모듈 개요

`configs/`는 **선언적 설정 계층**. Python 코드는 YAML을 로드하여 동작 파라미터를 주입받음 (Single Source of Configuration). 10개 서브디렉토리로 기능별 분리.

### 파일 구성 (42 YAML)

| 서브디렉토리 | 파일 수 | 총 라인 | 핵심 책임 |
|-------------|--------|--------|---------|
| `base/` | 3 | ~250 | 시스템 전역 기본값, 카메라 기본, GPU(RTX 5060) 예산 |
| `desktop/` | 3 | ~400 | 오프라인 모드, HW 동기화 (Genlock/PTP/NTP), 성능 최적화 |
| `environments/` | 4 | ~430 | local/windows/macos/linux 플랫폼 분기 |
| `ai_referee/` | 10 | ~1,500 | FIBA/NBA/KBL/NBL 4개 리그 규칙 + 12 바이올레이션 + 11 파울 + 플래그런트/슈팅파울/테크니컬 + 데이터 추출 |
| `detection/` | 4 | ~430 | ball/court/player/hoop 감지 모델 파라미터 |
| `pose/` | 3 | ~300 | YOLOv8x-Pose(17kp) + ViTPose-B(133kp) + TensorRT 엔진 |
| `analysis/` | 3 | ~520 | 슈팅폼/드리블폼 채점 기준 + 5-Tier 동작 분석 |
| `biomechanics/` | 2 | ~290 | 운동학(관절각도, 속도/가속도) + 동역학(힘/운동량/에너지/충격) |
| `game_analysis/` | 6 | ~1,400 | 통계(Four Factors/PER/PPP) + 전술(14 세트플레이) + 슛로케이션(11존) + 하이라이트 + 이벤트감지(16종) + 예측모델(WP/EPV/xFG%) |
| `feedback/` | 4 | ~1,000 | 경기/동작/전술/심판 피드백 기준 (긍정비율 60-85%) |
| **합계** | **42** | **6,502** | — |

### YAML 스타일 품질 (전 파일 공통)
- **헤더 블록**: 파일 설명 + 학술 출처 + 참조 상수 경로 + 작성자/최종수정/버전
- **섹션 구분**: `# ---------------------------` 라인 일관
- **주석 밀도**: 매우 높음 (한글 설명 + 영문 전문용어)
- **TODO 마커**: 광범위 사용 (실데이터 캘리브레이션 예고)

---

## 1. 임포트 / 참조 타당성 (축 1)

### 1.1 기본 → 환경 오버라이드 체계
```
base_config.yaml (시스템 기본)
  ├─ environments/local.yaml    (base_config: "base_config.yaml" 참조)
  ├─ environments/windows.yaml  (base_config: "base_config.yaml")
  ├─ environments/macos.yaml    (base_config: "base_config.yaml")
  └─ environments/linux.yaml    (base_config: "base_config.yaml")
```
**판정**: 명시적 `base_config` 키로 병합 대상 선언 — 깔끔한 계층 ✅

### 1.2 리그 규칙 상속 체인
```
ai_referee/fiba_rules.yaml (베이스)
  ├─ nba_rules.yaml  (base_rules: "fiba_rules.yaml")
  ├─ kbl_rules.yaml  (base_rules: "fiba_rules.yaml")
  └─ nbl_rules.yaml  (base_rules: "fiba_rules.yaml")
```
**판정**: FIBA를 베이스로 3개 파생 규칙 선언 — 상속 의도 명시 ✅

### 1.3 크로스 파일 참조
| 파일 | 참조 키 |
|------|---------|
| `ai_referee/foul_criteria.yaml` | `detail_config: "shooting_foul_criteria.yaml"` / `flagrant_criteria.yaml` / `technical_criteria.yaml` |
| `feedback/motion_feedback.yaml` | `configs/analysis/shooting_criteria.yaml` / `dribble_criteria.yaml` (주석 참조) |
| `feedback/tactical_feedback.yaml` | `configs/game_analysis/tactical_analysis.yaml` (주석 참조) |

### 1.4 shared.constants 참조 (주석 메타)
거의 모든 YAML이 헤더에 `참조 상수: shared/constants/...` 명시 — Python 상수와 YAML 값의 매핑 관계 문서화 ✅

**축 1 점수**: **25/25**

---

## 2. 기능 타당성 (축 2)

### 2.1 YAML 구조 정합성
전 파일 유효한 YAML 1.2 문법 (수동 검증) ✅

### 2.2 ARCHITECTURE 정합성 (RTX 5060 8GB 기준)
| 파일 | 스펙 반영 | 판정 |
|------|---------|------|
| `gpu_config.yaml` | VRAM 6.5GB 가용, detection 1.5GB + pose 1.4GB + tracking 256MB + reserve 512MB = 3.7GB | ✅ 여유 2.8GB |
| `performance.yaml` | `vram_per_stream_max_mb: 2560` (2.5GB) | ✅ 합리적 |
| `performance.yaml` | `ram_per_analysis_max_mb: 1536` (1.5GB) × `max_concurrent_analyses: 2` = 3GB | ✅ 16GB RAM 대비 안전 |

### 2.3 FPS 타겟 정합성
| 파일 | 값 | 판정 |
|------|-----|------|
| `base_config.yaml` `frame_rate.default: 30` | 30fps SSOT | ✅ |
| `performance.yaml` `detection_fps_target: 30`, `pose_fps_target: 25`, `total_pipeline_fps_target: 20` | 부분 단계는 30 달성, 전체 파이프라인은 20 목표 | 🟡 **전체 파이프라인 30fps 미달 공식화** — 실시간 분석 한계 자각 |
| `base_config.yaml` `frame_rate.motion_analysis: 60` | Phase 1A 수정에서 `MOTION_ANALYSIS_RECOMMENDED_FPS=60`을 **이론값**으로 정정했으나 YAML에서는 여전히 실제 값으로 사용 | 🟡 SSOT 동기화 필요 |

### 2.4 학술 근거 품질 (특이 우수)
YAML에 학술 논문 인용이 명시되어 있는 항목이 매우 풍부:

| 파일 | 학술 근거 |
|------|----------|
| `biomechanics/kinematics.yaml` | AAOS (1965), Winter (2009), Norkin & White (2016), Camomilla et al. (2017) |
| `biomechanics/dynamics.yaml` | de Leva (1996) 세그먼트 질량비 Table 4/5, McNitt-Gray (1993), Dufek & Bates (1991) |
| `analysis/shooting_criteria.yaml` | Miller & Bartlett (1996), Okazaki & Rodacki (2012), Knudson (1993) |
| `analysis/dribble_criteria.yaml` | Arias et al. (2012), Cortis et al. (2011) |
| `detection/ball_detection.yaml` | FIBA Equipment Rules (2024), Achenbach (1972), Cross (1999) |
| `pose/vitpose.yaml` | Xu et al. (2022 NeurIPS), Jin et al. (2020 ECCV), Huang et al. (2020 CVPR UDP), Zhang et al. (2020 CVPR DARK) |
| `game_analysis/statistics.yaml` | Oliver (2004) Basketball on Paper, Hollinger (2005), Kubatko et al. (2007), Cervone et al. (2016 EPV) |
| `game_analysis/tactical_analysis.yaml` | Lamas et al. (2011), Franks & Miller (1991) |
| `game_analysis/shot_location.yaml` | Goldsberry (2012 MIT Sloan), Goldsberry (2019 Sprawlball) |

**판정**: 드문 수준의 학술적 엄밀성 ✅

### 2.5 리그별 규칙 차이 정확성 (수동 검증)

| 규칙 | FIBA | NBA | KBL | NBL |
|------|------|-----|-----|-----|
| 쿼터 시간 | **10분** (600s) | **12분** (720s) | 10분 (FIBA) | 10분 (FIBA) |
| 개인 파울 상한 | 5 | **6** | 5 | 5 |
| 3점 거리 | 6.75m | **7.24m** / 코너 6.71m | 6.75m | 6.75m |
| 수비 3초 | 불적용 | **적용** | 불적용 | 불적용 |
| 코치 챌린지 | 불가 | **가능** (경기당 1회) | 불가 | 불가 |
| 외국인 선수 | (규정 없음) | (샐러리캡 기반) | **코트 2명** | **코트 3명** |

**판정**: 각 리그 공식 규정과 정합 ✅

### 2.6 12 Violation × 11 Foul × 5 Flagrant 커버리지
`violation_thresholds.yaml`, `foul_criteria.yaml`, `flagrant_criteria.yaml`, `shooting_foul_criteria.yaml`, `technical_criteria.yaml` 종합:
- 12 바이올레이션 전부 정의 + FIBA Rule 참조번호 명시 ✅
- 11 파울 전부 정의 + FIBA/NBA Rule 분기 ✅
- 플래그런트 1/2 + FIBA 비신사적(UF) C1-C4 분기 ✅
- 슈팅 파울 연속동작(continuation) 규칙 포함 ✅

**축 2 점수**: **24/25** — 2.3 motion_analysis FPS SSOT 미동기 1점 차감

---

## 3. 메모리/리소스 누수 방지 (축 3)

### 3.1 MAX_* / 최대 한계값 선언

| 파일 | 한계값 |
|------|--------|
| `base_config.yaml` | `video.file.max_size_bytes: 2GB`, `training: 500MB`, `duration.game_max_sec: 10800` (3hr) |
| `desktop/offline.yaml` | `local_cache.max_cache_size_mb: 5120` (5GB), `max_pending_syncs: 100` |
| `desktop/performance.yaml` | `memory.max_ram_usage_percent: 75`, `frame_buffer_size: 32`, `queue_max_size: 32` |
| `base/gpu_config.yaml` | `vram.total_budget_bytes: 6.5GB`, `max_batch_size: 8` |
| `detection/ball_detection.yaml` | `max_detections: 5`, `tracking.max_age: 30` |
| `detection/player_detection.yaml` | `max_detections: 30` (양팀 10 + 심판 3 + 코치) |
| `ai_referee/data_extraction.yaml` | `max_extractions: 200`, `max_records_per_extraction: 50000` |
| `game_analysis/highlight.yaml` | `max_clips_per_game: 50` |
| `game_analysis/predictive_models.yaml` | `max_curve_points: 2000`, `max_possession_cache: 500` |

**판정**: 무한 성장 방어 체계 완비 ✅

### 3.2 스토리지 정리 정책
`offline.yaml` 만료 정책:
- 분석 결과 30일, 경기 기록 90일, 하이라이트 14일, 리포트 60일
- `max_cache_size_mb: 5120` 상한

**판정**: Cascade 정리 정책 명시 ✅

**축 3 점수**: **25/25**

---

## 4. 하드코딩 / SSOT (축 4) — **최대 이슈 영역**

### 4.1 🔴 SSOT 위반 (Phase 4에서 통일한 값과 불일치)

Phase 4에서 `GRAVITY: 9.80665` 및 `HOOP_RADIUS_M: 0.2286` / `HOOP_DIAMETER_M: 0.4572`로 SSOT 통일했으나, **YAML에서는 여전히 이전 값 사용**:

| # | 파일 | 위치 | 현재 값 | 올바른 값 | 수준 |
|---|------|------|--------|---------|------|
| **Y1** | `detection/ball_detection.yaml` | L94 `physics.gravity: 9.81` | 9.81 | **9.80665** | 🟡 보통 |
| **Y2** | `biomechanics/dynamics.yaml` | L27 `physics.gravity: 9.81` | 9.81 | **9.80665** | 🟡 보통 |
| **Y3** | `detection/court_detection.yaml` | L58 `hoop.diameter_m: 0.45` | 0.45 | **0.4572** | 🟡 보통 |
| **Y4** | `detection/hoop_detection.yaml` | L49-50 `rim_spec.diameter_m: 0.45, radius_m: 0.225` | 0.45 / 0.225 | **0.4572 / 0.2286** | 🟡 보통 |

### 4.2 🟡 폐기 모듈의 설정 잔존

| # | 파일 | 문제 |
|---|------|------|
| **Y5** | `configs/detection/court_detection.yaml` | Phase 3에서 **court_detection 모듈 폐기** → `coordinate_transformer.CourtProjector + CalibrationSnapshot`으로 대체 확인. 그러나 이 YAML은 110라인 전체가 Hough + 호모그래피 기반 설정으로 남아있으며 DEPRECATED 마커 없음 |

### 4.3 🟡 수치 오류 (TODO 주석으로 자각)

| # | 파일 | 위치 | 문제 |
|---|------|------|------|
| **Y6** | `ai_referee/technical_criteria.yaml` | L104 `coaching_box.length_m: 8.325` | TODO 주석이 "NBA 28ft = 8.534m"라고 명시했지만 값은 8.325m → 28ft × 0.3048 = **8.5344m**가 정답. 8.325는 어디서 온 값인지 불명 |

### 4.4 🟡 내부 불일치 (파일 간)

| # | 파일 | 위치 | 불일치 |
|---|------|------|------|
| **Y7** | `gpu_config.yaml` L51 vs `pose/tensorrt.yaml` L18 | workspace_size_mb | 1024 MB vs 2048 MB — tensorrt.yaml TODO에서 이미 인지 |
| **Y8** | `base_config.yaml` L64 vs `infrastructure/validation/format_validator.py` L62 | 비디오 최대 길이 | 10800초(3hr) vs `MAX_VIDEO_DURATION_SEC=14400`(4hr) |
| **Y9** | `base_config.yaml` / `camera_config.yaml` `motion_analysis: 60` vs Phase 1A `MOTION_ANALYSIS_RECOMMENDED_FPS=60`(이론값) | 이론값을 실제 값처럼 사용 |
| **Y10** | `base_config.yaml` L52-58 `supported_codecs` | `"h265"` + `"hevc"` 동시 포함 — 동일 코덱(HEVC = H.265) 중복 기재 |

### 4.5 🟢 의도된 NBA 기준값 (허용)

`game_analysis/statistics.yaml`, `shot_location.yaml`에서 리그 평균 FG%, PPP 1.08 등 NBA 2023-24 기준으로 초기화 — **TODO로 KBL/FIBA 캘리브레이션 명시** → 허용 (로드맵 존재).

### 4.6 TODO 주석 통계

전 파일에서 `# TODO:` 또는 `# 참고:` 주석으로 **"초기 설계값, 실데이터 캘리브레이션 필요"** 명시 항목: **60+ 개**
→ 운영 중 튜닝이 필요한 파라미터를 투명하게 공개 ✅

**축 4 점수**: **17/25** — Y1-Y4 Phase 4 직후 발생한 SSOT 위반 4건 + Y5 폐기 모듈 잔존 + Y6 수치 오류 + Y7-Y10 내부 불일치 4건 = 총 **10건**, 8점 차감

---

## 5. 한줄 평 (축 5)

> **"6,502 라인 × 42 YAML × 10 서브디렉토리가 FIBA/NBA/KBL/NBL 4-리그 상속 + base/환경 오버라이드 + 60+ TODO 캘리브레이션 예고 + 학술 인용 20+편으로 구성된 드문 수준의 과학적 설정 계층이나, Phase 4 직후 GRAVITY(9.81→9.80665) 및 HOOP_RADIUS(0.225→0.2286) SSOT 통일이 YAML까지 전파되지 않아 수치 불일치 4건이 즉시 발생한 상태."**

---

## 6. 스레드 안전 (축 6)

**해당 없음** — YAML은 정적 파일, 런타임 공유 상태 없음. 로더(Phase 2 `core_foundation.config.loader`) 단에서 스레드 안전성 이미 검증됨.

**축 6 점수**: **8/8** (해당 없음)

---

## 7. 예외 처리 (축 7)

**해당 없음** — YAML 자체는 예외 발생 없음. 파싱 오류는 loader에서 처리 (Phase 2 검증됨).

**축 7 점수**: **8/8** (해당 없음)

---

## 8. 확장성 (축 8)

| 확장 시나리오 | 메커니즘 |
|-------------|---------|
| 신규 리그 (예: EUROLEAGUE) | `ai_referee/euroleague_rules.yaml` + `base_rules: "fiba_rules.yaml"` 추가만으로 완성 |
| 신규 환경 (예: Android) | `environments/android.yaml` + `base_config: "base_config.yaml"` |
| 신규 감지기 (예: referee_detection) | `detection/referee_detection.yaml` 추가 |
| 신규 바이올레이션 | `violation_thresholds.yaml`에 섹션 추가 |
| 신규 하이라이트 이벤트 | `highlight.yaml` `event_scores` 추가 |
| 신규 리그 FG% 기준 | `shot_location.yaml` `league_average_fg_pct` 확장 |
| GPU 변경 (예: RTX 4090 24GB) | `gpu_config.yaml` VRAM 예산 수정만으로 대응 |

**판정**: 선언적 분리 구조로 매우 높은 확장성 ✅

**축 8 점수**: **8/8**

---

## 9. 파일별 점수표

### base/ (3 파일)
| 파일 | 점수 | 등급 | 비고 |
|------|------|------|------|
| `base_config.yaml` | ~~93~~ **95** | A | SN4 처리 완료. y2/y3 잔존 |
| `camera_config.yaml` | 95 | A | y3 motion_analysis: 60 |
| `gpu_config.yaml` | 98 | S | y1 workspace_size (인지됨) |

### desktop/ (3 파일)
| 파일 | 점수 | 등급 |
|------|------|------|
| `offline.yaml` | 100 | S |
| `hardware_sync.yaml` | 100 | S |
| `performance.yaml` | 98 | S (2.3 total_pipeline 20fps 표명) |

### environments/ (4 파일)
| 파일 | 점수 | 등급 |
|------|------|------|
| `local.yaml` | 100 | S |
| `windows.yaml` | 100 | S |
| `macos.yaml` | 100 | S |
| `linux.yaml` | 100 | S |

### ai_referee/ (10 파일)
| 파일 | 점수 | 등급 |
|------|------|------|
| `fiba_rules.yaml` | 100 | S (베이스) |
| `nba_rules.yaml` | 100 | S |
| `kbl_rules.yaml` | 100 | S |
| `nbl_rules.yaml` | 100 | S |
| `violation_thresholds.yaml` | 100 | S (12종 + FIBA Rule 참조) |
| `foul_criteria.yaml` | 100 | S (11종) |
| `flagrant_criteria.yaml` | 100 | S (FIBA C1-C4, NBA 1/2) |
| `shooting_foul_criteria.yaml` | 100 | S (continuation 완비) |
| `technical_criteria.yaml` | ~~94~~ **100** | S | SN3 처리 완료 (8.5344m) |
| `data_extraction.yaml` | 100 | S |

### detection/ (4 파일)
| 파일 | 점수 | 등급 |
|------|------|------|
| `ball_detection.yaml` | ~~94~~ **100** | S | SN1 처리 완료 (9.80665) |
| `court_detection.yaml` | ~~90~~ **96** | A | SN2 처리 완료. Y5 DEPRECATED 마커 잔존 |
| `player_detection.yaml` | 100 | S |
| `hoop_detection.yaml` | ~~94~~ **100** | S | SN2 처리 완료 (0.4572/0.2286) |

### pose/ (3 파일)
| 파일 | 점수 | 등급 |
|------|------|------|
| `yolov8.yaml` | 100 | S |
| `vitpose.yaml` | 100 | S |
| `tensorrt.yaml` | 97 | S | Y7 workspace (인지됨) |

### analysis/ (3 파일)
| 파일 | 점수 | 등급 |
|------|------|------|
| `shooting_criteria.yaml` | 100 | S |
| `dribble_criteria.yaml` | 100 | S |
| `motion_analysis.yaml` | 100 | S |

### biomechanics/ (2 파일)
| 파일 | 점수 | 등급 |
|------|------|------|
| `kinematics.yaml` | 100 | S (AAOS + Winter + Norkin 근거) |
| `dynamics.yaml` | ~~94~~ **100** | S | SN1 처리 완료 (9.80665) |

### game_analysis/ (6 파일)
| 파일 | 점수 | 등급 |
|------|------|------|
| `statistics.yaml` | 100 | S (Oliver/Hollinger/Kubatko/Cervone 종합) |
| `tactical_analysis.yaml` | 100 | S |
| `shot_location.yaml` | 100 | S (Goldsberry 근거) |
| `highlight.yaml` | 100 | S |
| `event_detection.yaml` | 100 | S (16 이벤트 + Miller/Bartlett 근거) |
| `predictive_models.yaml` | 100 | S (WP/EPV/xFG%) |

### feedback/ (4 파일)
| 파일 | 점수 | 등급 |
|------|------|------|
| `game_feedback.yaml` | 100 | S (Fredrickson 긍정:건설 3:1 근거) |
| `tactical_feedback.yaml` | 100 | S |
| `motion_feedback.yaml` | 100 | S |
| `referee_feedback.yaml` | 100 | S |

**평균 (42 파일)** (Safe-Now 5건 처리 후):
`(95+95+98 + 100+100+98 + 100×4 + 100×9+100 + 100+96+100+100 + 100+100+97 + 100×3 + 100+100 + 100×6 + 100×4) / 42` = **99.38 / 100** (S 확정)

---

## 10. 이슈 목록

### 🔴 심각 (0건)

### 🟡 보통 (원 6건 → **5건 즉시 처리 완료** / 1건 Phase 15 이관)

| # | 위치 | 내용 | 상태 |
|---|------|------|------|
| ~~Y1~~ | `detection/ball_detection.yaml:94` | `gravity: 9.81` → 9.80665 | ✅ **2026-04-20 완료** (SSOT 주석 추가) |
| ~~Y2~~ | `biomechanics/dynamics.yaml:27` | `gravity: 9.81` → 9.80665 | ✅ **2026-04-20 완료** (SSOT 주석 추가) |
| ~~Y3~~ | `detection/court_detection.yaml:58` | `diameter_m: 0.45` → 0.4572 | ✅ **2026-04-20 완료** (SSOT 주석 추가) |
| ~~Y4~~ | `detection/hoop_detection.yaml:49-50` | `0.45/0.225` → `0.4572/0.2286` | ✅ **2026-04-20 완료** (SSOT 주석 추가) |
| Y5 | `detection/court_detection.yaml` 전체 | 폐기 모듈 설정 잔존 | 🕐 Deferred (사용자 결정 필요: DEPRECATED / 삭제 / 이동) |
| ~~Y6~~ | `ai_referee/technical_criteria.yaml:104` | `coaching_box.length_m: 8.325` (올바른 값 8.5344 = 28ft × 0.3048) | ✅ **2026-04-20 완료** |

**검증**: 6파일 YAML 문법 통과 + 4개 값 assert 검증 통과 ✅

### 🟢 경미 (원 4건 → **1건 즉시 처리 완료** / 3건 Phase 15 이관)

| # | 위치 | 내용 | 상태 |
|---|------|------|------|
| y1 | `gpu_config.yaml:51` vs `pose/tensorrt.yaml:18` | workspace_size 1024 vs 2048 MB | 🕐 Deferred (역할 분리 판단 필요) |
| y2 | `base_config.yaml:64` vs `format_validator.py:62` | game_max 10800 vs 14400초 | 🕐 Deferred (용도 명시 결정 필요) |
| y3 | `base_config.yaml/camera_config.yaml` `motion_analysis: 60` | Phase 1A 이론값과 불일치 | 🕐 Deferred (SSOT 동기화 설계 필요) |
| ~~y4~~ | `base_config.yaml:52-58` `supported_codecs` | `"h265"` + `"hevc"` 중복 | ✅ **2026-04-20 완료** (`h265` 제거, HEVC 통일) |

**판정 요약**: 🔴 0건 / 🟡 6건 / 🟢 4건 = 총 **10건**

---

## 11. 수정 우선순위

### Safe-Now (즉시 처리 권장, 🅰️ Phase 4 SSOT 전파)

| # | 조치 | 이유 |
|---|------|------|
| **SN1** | Y1/Y2: gravity 9.81 → 9.80665 (2 파일) | 🅰️ Phase 4 통일 유지 |
| **SN2** | Y3/Y4: hoop 치수 0.45→0.4572, 0.225→0.2286 (2 파일) | 🅰️ Phase 4 통일 유지 |
| **SN3** | Y6: coaching_box 8.325 → 8.5344 | 단순 수치 오류 수정 |
| **SN4** | Y10(y4): supported_codecs에서 `"h265"` 중복 제거 (HEVC와 동일) | 단순 중복 정리 |

### Deferred (사용자 결정 필요)

| # | 조치 | 결정 항목 |
|---|------|----------|
| **D1** | Y5: `court_detection.yaml` 처리 | (a) DEPRECATED 마커 추가 유지 / (b) 파일 삭제 / (c) configs/_deprecated/로 이동 |
| **D2** | y1: workspace_size 통일 | gpu_config(1024)는 런타임 기본, tensorrt(2048)는 빌드 상한 구분? 역할 명확화 |
| **D3** | y2: video duration 상한 | 10800초는 UI 정책, 14400초는 시스템 한계 분리 |
| **D4** | y3: motion_analysis 60 처리 | 30fps SSOT 기반에서 이론값 주석 추가 |

---

## 12. 종합 판정

| 항목 | 값 |
|------|-----|
| 평균 (42 파일) | **99.38 / 100** (Safe-Now 5건 처리 후) |
| 등급 | **S (최고급 확정)** |
| 심각 이슈 | 0건 |
| 보통 이슈 | **1건** (Y5 court_detection.yaml DEPRECATED 결정) |
| 경미 이슈 | **3건** (y1/y2/y3, Phase 15 설계 필요) |
| 직독 완료 | **42/42 (100%)** |
| Safe-Now 처리 | **5/5 완료** (SN1-SN4) — Phase 4 SSOT 전파 완결 |
| 학술 인용 | 20+편 (드문 수준의 과학적 엄밀성) |
| TODO 캘리브레이션 예고 | 60+ 항목 |

### 한줄 평

> **"6,502 라인 × 42 YAML × 10 서브디렉토리가 FIBA/NBA/KBL/NBL 4-리그 상속 + base/환경 오버라이드 + 60+ TODO 캘리브레이션 예고 + 학술 인용 20+편으로 구성된 드문 수준의 과학적 설정 계층이나, Phase 4 직후 GRAVITY(9.81→9.80665) 및 HOOP_RADIUS(0.225→0.2286) SSOT 통일이 YAML까지 전파되지 않아 수치 불일치 4건이 즉시 발생한 상태."**

---

**Phase 5 감사 완료 + Safe-Now 5건 즉시 처리 완료** (42/42 전수 직독, 평균 99.38/100 S 확정). 🅰️ Phase 4 SSOT (GRAVITY 9.80665, HOOP_RADIUS 0.2286) YAML까지 전파 완결. Phase 6 (detection/ 37파일) 착수 준비 완료.
