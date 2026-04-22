# Phase 15 세션 1 — Tier 1 Critical + Tier 4 Low 실행 리포트

**실행일**: 2026-04-20
**범위**: Tier 1 Critical (4건) + Tier 4 Low (5건) = **9건**
**결과**: **9/9 완료** (100%)

---

## 1. 실행 내역

### Tier 1 Critical

#### ✅ C4. RTX 4070/4080 프로파일 추가

- **파일**: [engine/config.py](engine/config.py)
- **변경**: `RTX_4070_PROFILE` (12GB VRAM, batch 6/12/3) + `RTX_4080_PROFILE` (16GB, batch 8/16/4) 2개 Final 상수 추가
- **Export**: `__all__` 에 2개 심볼 추가
- **효과**: 렌탈 노트북 타깃 하드웨어 프리셋 완비 (4060/4070/4080/5070/4090 = 5 프로파일)

#### ✅ C3. court_detection.yaml 주석 보완

- **파일**: [configs/detection/court_detection.yaml](configs/detection/court_detection.yaml)
- **변경**: 헤더에 "현재: 호모그래피 대체, 장기 로드맵: ML 학습용 데이터 수집 중" 주석 추가
- **근거**: Phase 06 해석 — detection/court_detection/__init__.py 명시 + data_extraction 3 추출기 활성 데이터 수집
- **효과**: DEPRECATED 혼동 제거, 장기 로드맵 명확화

#### ✅ C2. 리그별 클러치 정의 (인프라)

- **파일**: [ai_referee/rules/fiba_rules.py](ai_referee/rules/fiba_rules.py)
- **변경**: `LeagueSpecificRules` 에 3개 필드 추가
  - `clutch_quarter_min: int = 4`
  - `clutch_clock_sec: float = 300.0`
  - `clutch_score_diff_max: int = 5`
- **from_yaml 로딩**: `cfg.get("clutch", {})` 섹션 파싱 지원
- **후속 작업 (Tier 2 High)**: 4개 사용처 적용 — `calibration_data_extractor`, `confidence_scorer`, `foul_severity_analyzer`, 기타
  - FIBARules 주입 구조 필요하여 구조 리팩토링으로 이관

#### ✅ C1. FrameContext.fps + 10파일 fps 통합 (중요)

- **파일**: [ai_referee/rules/base_rule.py](ai_referee/rules/base_rule.py) — `FrameContext.fps: float = 30.0` 추가
- **10개 사용처 교체** (`fps = 30.0` → `context.fps`):

  | 파일 | 이전 | 이후 |
  |---|---|---|
  | `blocking_foul_detector.py:118` | `fps = 30.0` | `fps = context.fps` |
  | `hand_check_detector.py:117` | `fps = 30.0` | `fps = context.fps` |
  | `holding_foul_detector.py:116` | `fps = 30.0` | `fps = context.fps` |
  | `three_second_detector.py:110` | `fps = 30.0` | `fps = context.fps` + 0 가드 |
  | `defensive_three_sec_detector.py:119` | `fps = 30.0` | `fps = context.fps` + 0 가드 |
  | `five_second_detector.py:118` | `fps = 30.0` | `fps = context.fps` + 0 가드 |
  | `eight_second_detector.py:98` | `fps = 30.0` | `fps = context.fps` + 0 가드 |
  | `carry_detector.py:143` | `fps = 30` | `fps = context.fps if > 0 else 30.0` |
  | `kick_ball_detector.py:114` | `* 30` 직접 곱 | `* context.fps` (0 가드) |
  | `shooting_foul_classifier.py:286` | `> 90` (3초 @ 30fps) | `shooting_timeout_frames = int(fps * 3)` |

- **효과**: **실제 영상 fps 60/24/다른 값 모두 지원** — 이전엔 30fps 전제로 LGP/지속프레임 판정 오차 발생 가능
- **호환성**: `FrameContext.fps = 30.0` 기본값 — 기존 호출 코드 영향 없음

### Tier 4 Low

#### ✅ L1. `__init__.py` 8파일 표준화

- **파일**: 8개
  1. `api_server/__init__.py`
  2. `api_server/middleware/__init__.py`
  3. `api_server/schemas/__init__.py`
  4. `api_server/websocket/__init__.py`
  5. `api_server/routes/__init__.py`
  6. `api_server/routes/v1/__init__.py`
  7. `api_server/services/__init__.py`
  8. `api_server/services/facades/__init__.py`
- **변경**: 각 파일에 표준 docstring (COURTVIEW 헤더 + 모듈 설명 + 파일 역할 목록) + `__all__: list[str] = []` + `__version__ = "1.0.0"` 추가
- **효과**: Phase 10~13 표준과 일관성 확보

#### ✅ L2. schemas `__version__` 추가

- **파일**: [request_schemas.py](api_server/schemas/request_schemas.py), [response_schemas.py](api_server/schemas/response_schemas.py)
- **변경**: `__all__` 뒤에 `__version__ = "1.0.0"` 추가
- **효과**: 35 Pydantic 스키마 버전 관리 표준화

#### ✅ L5. `game_service.py` import 순서 정리

- **파일**: [api_server/services/game_service.py](api_server/services/game_service.py)
- **변경**: 표준 라이브러리 → 프로젝트 → api_server 순서로 재배치
  - `Callable` + `TYPE_CHECKING` 통합 import
  - TYPE_CHECKING 블록을 import 끝으로 이동
  - 모듈 상수(`_AGE_GROUP_MAP` 등) 4종을 모듈 상단에 모아두기
- **효과**: PEP 8 표준 준수

#### ✅ L3. `demo_page` 경로 IOConfig 승격

- **파일**: [engine/config.py](engine/config.py), [api_server/main.py](api_server/main.py)
- **변경**:
  - `IOConfig.demo_page_path: str = "tests/demo_page.html"` 필드 추가
  - `main.py` `/demo` 엔드포인트가 `IOConfig().demo_page_path` 사용
- **효과**: 배포 환경에서 경로 설정 가능

#### ✅ L4. `stream_routes` MJPEG fps Config 승격

- **파일**: [api_server/routes/v1/stream_routes.py](api_server/routes/v1/stream_routes.py)
- **변경**:
  - `_DEFAULT_MJPEG_FPS_CAP: float = 20.0` 모듈 상수 도입
  - `_CameraBuffer.__init__(fps_cap=_DEFAULT_MJPEG_FPS_CAP)` 파라미터화
  - `min(cap.get(CAP_PROP_FPS) or self._fps, self._fps)` — 카메라 실제 FPS vs Config 상한 중 작은 값
- **효과**: FPS 상한 Config 경로 명확화 (향후 IOConfig 승격 용이)

---

## 2. 영향 범위

### 코드 변경 파일 수

| 디렉토리 | 파일 수 |
|---|---|
| `engine/` | 1 (config.py) |
| `configs/detection/` | 1 (court_detection.yaml) |
| `ai_referee/rules/` | 2 (base_rule.py + fiba_rules.py) |
| `ai_referee/fouls/` | 4 (blocking/hand_check/holding/shooting) |
| `ai_referee/violations/` | 6 (three/def_three/five/eight + carry/kick) |
| `api_server/` | 10 (main.py + 8 __init__ + 2 schemas + game_service + stream_routes) |
| **합계** | **24파일** |

### 호환성

- **Breaking change**: **없음** — 모든 변경은 기본값 유지 (FrameContext.fps=30.0, IOConfig 기본값 등)
- **API 변경**: `FrameContext.fps` 필드 추가 (옵션)
- **YAML 변경**: `configs/detection/court_detection.yaml` 주석만 변경

---

## 3. 남은 Phase 15 작업

### Tier 2 High (대규모 리팩토링, 별도 세션)

| ID | 작업 | 파일 수 |
|---|---|---|
| H1 | motion_analysis/phase_analysis → biomechanics/phase_analysis 이전 | ~5 |
| H2 | motion_analysis/form_evaluation → feedback_system 이전 | ~5 |
| H3 | motion_analysis/comparison → feedback_system 이전 | ~3 |
| H4 | Facade 5개 engine 데이터 연동 구현 | 5 |
| H5 | shared.constants SSOT 확립 (GRAVITY/HOOP_RADIUS/CourtDimensions) | ~10 |
| H6 | korean_templates.py 1,630줄 분할 | 5-6 |

### Tier 3 Medium (설계 변경)

| ID | 작업 |
|---|---|
| M1 | GameOrchestrator public getter 추가 (6 private 접근) |
| M2 | age_group 문자열 → AgeGroup enum |
| M3 | Generator 인스턴스 공유 (싱글톤) |
| M4 | Config 가중치 승격 (매직 넘버 → Config) |
| M5 | 리그별 Config 분기 (league_avg_* 동적) |

### Tier 5 Optional

- O3 GameContext `dataclasses.replace` 간소화
- O1/O2 local import 모듈화 (pynvml, MotionSnapshot)
- O6 DEFAULT_VRAM_BUDGET_MB 14000 → 6000
- O5 reid_module.py 921줄 처리 (사용자 결정)
- O4 frame_to_event_converter 픽셀 단위
- O7 motion_analysis classification DEPRECATE (SV-action 배포 후)

### C2 후속 (Tier 2 이관)

- `LeagueSpecificRules.clutch_*` 3 필드는 추가 완료, 4개 사용처 적용은 FIBARules 주입 구조 리팩토링 필요 → Tier 2로 이관

---

## 4. 검증

- **Python syntax**: 24 파일 모두 import 및 syntax 정상 (기본값 유지로 런타임 영향 없음)
- **Breaking change**: 없음
- **테스트 필요 영역**: fps=30 이외 값(60/24)에서 이벤트 감지 정확도 회귀 테스트 (향후 통합 테스트 단계)

---

## 5. 다음 세션 제안

**세션 2 권장**: Tier 3 Medium **M1 (GameOrchestrator public getter)** 집중 처리

- GameOrchestrator에 4개 property 추가 (`gpu_manager`, `trt_pool`, `batch_accumulator`, `result_dispatcher`)
- 6개 private 접근 지점 교체 (metrics_routes 4 + game_routes + progress_handler)
- 파일 변경: ~4파일

**예상 시간**: 30분 내외

**대안**: Tier 5 Optional 빠른 정리 7건 일괄

---

**세션 1 완료. 9건 모두 적용. Breaking change 없음.**
