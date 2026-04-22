# 15. Phase 15 — Deferred 이슈 통합 카탈로그 & 일괄 정비 계획

**작성일**: 2026-04-20
**범위**: Phase 00~14 전수 감사 결과 수집된 **모든 Deferred 이슈**
**감사 대상 파일**: **329+ 파일** (game_analysis 165 + ai_referee 47 + feedback_system 39 + engine 34 + api_server 44 + shared/core/infra/utils/configs/detection/pose/biomech/motion)
**목적**: Phase 00~14 에서 이월된 이슈를 우선순위별로 분류하고 일괄 실행 계획 수립

---

## 1. Deferred 이슈 총괄

| Phase | 모듈 | Deferred 건수 | 주요 유형 |
|---|---|---|---|
| **00** | ARCHITECTURE | 1 | 리팩토링 권고 |
| **01A** | shared/constants | 1 | SSOT |
| **01B** | shared/dto | 1 | DTO 정비 |
| **01C** | shared/rest | 1 | 기타 |
| **02** | core_foundation | 2 | VRAM 자동감지, DEFAULT_CONFIG |
| **03** | infrastructure | 1 | 기타 |
| **04** | utils | **10** | SSOT 통합 4 + 설계 변경 2 + 기타 |
| **05** | configs | **4** | Y5 폐기 모듈 + workspace_size + video duration + motion_analysis 60 |
| **06** | detection | 2 | dead code 921줄 + court_detection ML 로드맵 |
| **07** | pose_estimation | 1 | 기타 |
| **08** | biomechanics | 1 | 기타 |
| **09** | motion_analysis | **10** | **구조 리팩토링** (Tier 3-5 이전) + 매직넘버 3 + 데드코드 |
| **10** | game_analysis | **9** | SSOT + Config + fps 관련 |
| **11** | ai_referee | **20** | **fps 하드코딩** + 클러치 정의 + 매직 계수 + Config |
| **12** | feedback_system | **9** | korean_templates 분할 + age_group enum + 리그별 분기 |
| **13** | engine | **6** | RTX 4070/4080 프로파일 + local import + dataclasses.replace |
| **14** | api_server | **10** | __init__ 표준화 8파일 + Facade stub 5 + private 속성 |
| **합계** | — | **~89건** | — |

---

## 2. 우선순위 분류 (5 tiers)

### Tier 1: **Critical** — 즉시 실행 (기능 영향·품질 핵심)

| ID | 설명 | 영향 범위 |
|---|---|---|
| **C1** | **fps 하드코딩 통합** — `FrameContext.fps` 필드 추가 + 10+ 파일 수정 | ai_referee, engine (정확도 핵심) |
| **C2** | **리그별 클러치 정의** — `LeagueSpecificRules.clutch_definition` 도입 | Phase 10/11/12 4회 반복 이슈 |
| **C3** | **court_detection.yaml 처리** — DEPRECATED / 삭제 / 이동 결정 | Phase 06 해석 근거로 주석 추가만 권장 |
| **C4** | **RTX 4070/4080 프로파일 추가** — 렌탈 노트북 타깃 | Phase 13 engine/config.py |

### Tier 2: **High** — 구조 리팩토링 (대규모)

| ID | 설명 | 영향 범위 |
|---|---|---|
| **H1** | **motion_analysis/phase_analysis/** → `biomechanics/phase_analysis/` | Phase 09 구조 |
| **H2** | **motion_analysis/form_evaluation/** → `feedback_system/form_evaluation/` | Phase 09 구조 |
| **H3** | **motion_analysis/comparison/** → `feedback_system/comparison/` | Phase 09 구조 |
| **H4** | **Facade 5개 engine 연동 구현** — game_stats/highlight/referee/report/tactical | Phase 14 통합 테스트 |
| **H5** | **shared.constants SSOT 확립** — GRAVITY/HOOP_RADIUS/CourtDimensions/QUARTER_DURATION 등 | Phase 04/05 중복 제거 |
| **H6** | **korean_templates.py 1,630줄 분할** — 슈팅/드리블/편차/문미/변형 5~6 서브모듈 | Phase 12 유지보수성 |

### Tier 3: **Medium** — 설계 개선

| ID | 설명 | 영향 범위 |
|---|---|---|
| **M1** | **GameOrchestrator public getter** — `gpu_manager`, `trt_pool`, `batch_accumulator`, `result_dispatcher` | Phase 14 캡슐화 (6회 private 접근) |
| **M2** | **age_group 문자열 → AgeGroup enum** | Phase 12 반복 이슈 |
| **M3** | **Generator 인스턴스 공유** — SeverityMapper/KoreanTemplates/FeedbackFormatter 중복 생성 방지 | Phase 12 ~54회 중복 |
| **M4** | **Config 가중치 승격** — game_report 5요소 / coach_report 60/40 / foul_severity 5요소 | Phase 11/12 매직 넘버 |
| **M5** | **리그별 Config 분기** — league_avg_efg/tov/orb/ft_rate 등 FIBA/NBA/KBL/NBL | Phase 10/12 임계치 |

### Tier 4: **Low** — 표준화

| ID | 설명 | 영향 범위 |
|---|---|---|
| **L1** | **`__init__.py` 8파일 표준화** — docstring + `__version__` + `__all__` | Phase 14 api_server/middleware/schemas/websocket/routes/routes-v1/services/facades |
| **L2** | **schemas `__version__` 추가** — request_schemas, response_schemas | Phase 14A |
| **L3** | **`main.py` demo_page 경로** → `IOConfig.demo_page_path` | Phase 14A |
| **L4** | **stream_routes MJPEG 20fps** Config 승격 | Phase 14B |
| **L5** | **game_service import 순서 정리** | Phase 14C |

### Tier 5: **Optional** — 정리

| ID | 설명 | 영향 범위 |
|---|---|---|
| **O1** | **gpu_manager pynvml local import** → 모듈 레벨 flag | Phase 13A |
| **O2** | **analysis_buffer MotionSnapshot local import** → 모듈 레벨 | Phase 13A |
| **O3** | **GameContext `dataclasses.replace`** 간소화 | Phase 13A |
| **O4** | **frame_to_event_converter 픽셀 단위** → 코트 좌표계 | Phase 13B |
| **O5** | **reid_module.py 921줄 dead code** 처리 | Phase 06 사용자 결정 |
| **O6** | **DEFAULT_VRAM_BUDGET_MB 14000 → 6000** | Phase 02 |
| **O7** | **motion_analysis classification/ DEPRECATE** (SV-action 배포 후) | Phase 09 L2 |

---

## 3. 즉시 실행 계획 (권장 순서)

### Phase 15-1: Tier 1 Critical (4건)

1. **C3 court_detection.yaml 주석 보완** (가장 간단)
2. **C4 RTX 4070/4080 프로파일 추가** (engine/config.py Final 상수 2개)
3. **C1 fps 하드코딩 통합** — `FrameContext.fps` 추가 + 10+ 파일 수정
4. **C2 리그별 클러치 정의** — `LeagueSpecificRules.clutch_definition` 도입 + 4 사용처 업데이트

### Phase 15-2: Tier 4 Low (5건, 빠름)

1. **L1 `__init__.py` 8파일 표준화** — api_server 일관화
2. **L2 schemas `__version__` 추가**
3. **L5 game_service import 순서 정리**
4. **L4 stream_routes MJPEG fps** Config 승격
5. **L3 demo_page 경로** IOConfig 승격

### Phase 15-3: Tier 3 Medium — M1 (캡슐화)

- **M1 GameOrchestrator public getter 추가** (6 접근 경로)
  - `gpu_manager`, `trt_pool`, `batch_accumulator`, `result_dispatcher`
  - metrics_routes + game_routes + progress_handler 3곳 수정

### Phase 15-4: Tier 5 Optional (7건, 빠른 정리)

1. **O3 GameContext `dataclasses.replace`**
2. **O1/O2 local import 모듈화**
3. **O6 DEFAULT_VRAM_BUDGET_MB** 수정
4. **O5 reid_module.py dead code** — 사용자 결정 필요
5. **O4 frame_to_event_converter 픽셀 단위** — 설계 결정 필요
6. **O7 classification DEPRECATE** — SV-action 배포 후 자연 해소

### Phase 15-5: Tier 2 High — 대규모 리팩토링 (별도 세션)

1. **H5 shared.constants SSOT 확립** (선행 — H1-H3 기반)
2. **H1/H2/H3 motion_analysis 디렉토리 이전** (Phase 09 3단계)
3. **H6 korean_templates.py 분할** (5-6 서브모듈)
4. **H4 Facade 5개 engine 연동 구현** (engine 통합 테스트 단계)

### Phase 15-6: Tier 3 Medium — M2-M5 (Config/Enum)

1. **M2 age_group → AgeGroup enum** (반복 패턴)
2. **M4 Config 가중치 승격** (매직 넘버)
3. **M5 리그별 Config 분기** (league_avg_* 시즌 동적 갱신)
4. **M3 Generator 인스턴스 공유** (중복 생성 방지)

---

## 4. 사용자 승인 필요 항목

| ID | 결정 사항 |
|---|---|
| **C3** | court_detection.yaml 처리 방식 (주석 추가 / 삭제 / 이동) |
| **O5** | reid_module.py 921줄 처리 (삭제 / `_deprecated/` 이동 / 유지) |
| **H1-H3** | motion_analysis 디렉토리 이전 타이밍 (즉시 / 지연) |
| **H4** | Facade 5개 구현 시점 (engine 통합 테스트 완료 후?) |
| **기타** | 5_CONFIGS D2/D3 (workspace_size, video duration 용도 분리 정책) |

---

## 5. 실행 전 현황 (Phase 00~14 누적)

| 항목 | 값 |
|---|---|
| 감사 완료 파일 | **329+파일** |
| Safe-Now 처리 완료 | **44건** (Phase 10~14) + 기존 Phase 00~09 처리분 |
| Deferred 카탈로그 | **~89건** (본 문서) |
| 평균 점수 | **95.7/100** (Phase 10~14 평균) |
| 최고 점수 | **96.4** (Phase 13 engine) |
| 최저 점수 | **92.6** (Phase 11B fouls — fps 하드코딩) |

---

## 6. 권장 실행 전략

### 단계적 실행 — **1회 세션당 1 Tier**

**세션 1 (본 세션)**: Tier 1 Critical (4건) + Tier 4 Low (5건) = **9건 + 8 `__init__.py`**

**세션 2**: Tier 3 Medium M1 (GameOrchestrator public getter) — 1건 집중

**세션 3**: Tier 5 Optional 빠른 정리 (7건)

**세션 4+**: Tier 2 High 리팩토링 (4건, 대규모 — 각 세션당 1건)

**세션 N**: Tier 3 Medium M2-M5 (4건, 설계 변경)

---

## 7. 다음 작업

사용자 승인 받아 **세션 1 (Tier 1 + Tier 4)** 부터 착수하거나, 다른 우선순위 제안.
