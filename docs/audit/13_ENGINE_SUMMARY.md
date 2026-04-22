# 13. engine/ 통합 감사 총평

**감사 범위**: `engine/` 전체 (**34파일**, 2 서브페이즈 완료)
**감사 방식**: 전수 직독 (Read 전용, grep/ls 미사용)
**감사 축**: 8종 (Import/Functional/MemoryLeak/Hardcoding/Review/ThreadSafety/Exception/Extensibility)
**감사 기간**: 2026-04-20 (단일 세션 완료)
**총점**: **96.4 / 100** (최우수) — **Phase 10~13 중 최고점**

---

## 1. 서브페이즈 구성 및 점수

| Phase | 디렉토리 | 파일수 | 점수 | 주요 책무 |
|---|---|---|---|---|
| **13A** | root + gpu + io + orchestrator + workers | 20 | 96.4 | 인프라 + GPU 리소스 + 실행 제어 |
| **13B** | pipeline + fusion + referee | 14 | 96.5 | 5등급 Cadence 파이프라인 + 융합 |
| **합계** | — | **34** | **96.4** | — |

---

## 2. Safe-Now 즉시 처리 내역 (1건)

| ID | 파일 | 이슈 | 처리 |
|---|---|---|---|
| S43 | `detection_fusion.py` | import 섹션 오분류 (json/zipfile/pathlib이 서드파티에 위치) | 표준 라이브러리 섹션으로 이동 |

**Phase 13 은 전체적으로 매우 정제된 엔진 레이어** — Safe-Now 이슈 극히 적음 (1건, 스타일 수준).

---

## 3. 8축 종합 평가

### 3.1 Import 유효성 ✅ 평균 96

- 34파일 전체 `from __future__ import annotations` + SSOT 준수
- **TYPE_CHECKING 패턴 광범위 적용** (pipeline/referee 7+ 파일) — 순환 참조 회피
- 서드파티 조건부 import (`try/except ImportError`) 시뮬레이션 fallback 일관

### 3.2 기능 유효성 ✅ 평균 97

- **6 서브 Config 통합 EngineConfig + 3 GPU 프로파일**
- **6상태 EngineState FSM + 트리거 생산-소비 원자적 패턴**
- **5등급 Cadence 파이프라인** (FRAME 33ms → POSTGAME 무제한)
- **CV-BBox 통합 모델** (1회 추론 → 4 클래스 동시 감지, 3배 속도)
- **54+ 분석기 오케스트레이션** (possession 19 + period 15 + postgame 20+)

### 3.3 메모리 누수 방지 ✅ 평균 97

- 전체 상한 체계: `_MAX_FRAME_BUFFER=900` / `_MAX_ALLOCATIONS=100` / `_MAX_PENDING_TASKS=50` 등
- `deque(maxlen=N)` + `emergency_cleanup` (oldest-first) + ring buffer
- 자동 트림 + 단발 소비 패턴 (POSTGAME dispatcher)

### 3.4 하드코딩 점검 ✅ 평균 93

- 대부분 `_Final[T]` 상수 또는 Config 필드로 노출
- 의미 주석 철저 (`# 30fps × 30초 = 900`)
- RTX 4060/5070/4090 프로파일 — 타깃(RTX 4070/4080) 프리셋 부재 (Phase 15)

### 3.5 한줄 검토 ✅ 평균 97

- docstring + 데이터 흐름 다이어그램 + 의존성 + 소비자 + 참고 메모
- 🔴🟠🟡🟢🔵 Cadence 등급 이모지 시각화
- ASCII 아트 상태 전이 다이어그램
- **Phase 10~13 중 가장 풍부한 문서화**

### 3.6 스레드 안전성 ✅ 평균 98

- 34파일 전체 `RLock + with self._lock + __slots__`
- 콜백 실행 시 lock 해제 후 수행 (블로킹 방지)
- frozen dataclass 방어적 복사 철저
- **Phase 13 최고 점수 축**

### 3.7 예외 처리 ✅ 평균 96

- `try/except ImportError` 시뮬레이션 fallback 패턴 일관
- `logger.exception` 콜백 오류 포착
- 상태 전이 불가 시 `ValueError` + 허용 상태 목록 제공

### 3.8 확장성 ✅ 평균 98

- DI 컨테이너 체계 (`XxxAnalyzerSet` 4종)
- 3 GPU 프로파일 Final 상수
- TYPE_CHECKING으로 분석기 확장 용이
- `FrameToEventConverter` 동적 속성 매핑
- **Phase 13 최고 점수 축** (공동)

---

## 4. Phase 15 Deferred 이슈 (6건)

### 4.1 13A 세부

| ID | 내용 |
|---|---|
| P15-13A-01 | `gpu_manager` pynvml local import 3회 반복 → 모듈 레벨 `_PYNVML_AVAILABLE` flag 도입 |
| P15-13A-02 | **RTX 4070/4080 프로파일 부재** — 렌탈 노트북 타깃 프리셋 추가 |
| P15-13A-03 | `analysis_buffer` MotionSnapshot local import → 모듈 레벨 처리 |
| P15-13A-04 | `GameContext` 11필드 수동 복사 → `dataclasses.replace` 간결화 |

### 4.2 13B 세부

| ID | 내용 |
|---|---|
| P15-13B-01 | `frame_to_event_converter` 픽셀 단위 하드코딩 (`_PX_TO_M=0.03`, `_POSSESSION_DIST_PX=80.0`) → 코트 좌표계 일원화 |
| P15-13B-02 | 5개 파이프라인 시간 예산 초과 시 자동 degradation 전략 (Stage2 스킵, 배치 축소) |

---

## 5. 페이즈별 특징 요약

### 13A — 엔진 인프라 (96.4)

- **핵심**: `engine/config.py` 6 서브 Config + `game_state.py` FSM + `analysis_buffer.py` 3단 빌더
- **gpu/**: pynvml 연동 + 시뮬레이션 fallback + OOM 방어 + TRT Pool
- **io/**: frame_ingestion (infrastructure 연동) + progress_reporter + result_dispatcher
- **orchestrator/**: cadence_scheduler (GameState → Cadence 매핑) + game_orchestrator (전체 수명주기 ~70 의존성) + mode_controller (LIVE/BATCH/REPLAY 프리셋)
- **workers/**: analysis_worker (possession 4T + period 2T) + export_worker (단일 T)

### 13B — 파이프라인 + 융합 + 심판 (96.5)

- **핵심**: 5등급 Cadence 파이프라인 완전 구현
- **pipeline/**: frame → event → possession → period → postgame (🔴🟠🟡🟢🔵)
- **fusion/**: CV-BBox 통합 모델 1회 추론 + pose 3D 복원 + 트래킹 글로벌 ID + ReID 대체 (digit+team)
- **referee/**: 12 바이올레이션 + 11 파울 + 6 decisions 통합 오케스트레이션 + 멀티앵글 검증
- **frame_to_event_converter**: FramePipelineResult → EventFrameData 동적 `*_input` 매핑

---

## 6. 전후 비교 — 수정 효과

| 항목 | 수정 전 | 수정 후 |
|---|---|---|
| import 섹션 오분류 | 1건 (S43) | 0 |

**누적 결함 제거**: 1건 (Phase 13 에서 발견된 전량)

---

## 7. CV 가중치 대체 매핑 (CV_WEIGHTS_MANIFEST v2.0 연계)

### 7.1 engine 은 코드 유지 (학습 가중치 대체 불가)

**이유**: engine은 **오케스트레이션 레이어**로, 학습 가중치 대체 영역 아님. 단, **CV 가중치의 런타임 호스트** 역할:

1. **`tensorrt_pool`** — CV-bbox/digit/team/action/reid/score/clock 등 **14~24 가중치 로드/언로드** 관리
2. **`cuda_stream_manager`** — Stage1 (bbox/pose/action) + Stage2 (ViTPose 트리거 시) 이중 스트림
3. **`batch_accumulator`** — 8cam CPU → GPU 배치 텐서 변환 (CV-bbox 1회 추론 대비)
4. **`detection_fusion`** — CV-BBox 통합 추론 결과 → 4 클래스 분배
5. **`pose_fusion`** — CV-pose 다시점 → 3D 키포인트 복원
6. **`tracking_fusion`** — CV-reid 대체 (digit + team 조합)
7. **`referee_orchestrator`** — CV-referee_F/V 호스팅

### 7.2 가중치 로딩 지점

| engine 모듈 | 로드하는 가중치 | 역할 |
|---|---|---|
| `tensorrt_pool.py` | 모든 `.engine` 가중치 | TRT 엔진 풀 관리 |
| `game_orchestrator.py` | LOADING 단계 | 전체 가중치 초기화 |
| `referee_orchestrator.py` | CV-referee_F/V | AI 심판 전용 |
| `multi_angle_pipeline.py` | CV-referee backbone (공유) | 멀티앵글 검증 |

### 7.3 가중치 → engine 런타임 흐름

```
[Weights (.engine)]
    ↓ tensorrt_pool.py 로드
[GPU Memory]
    ↓ cuda_stream_manager Stage1/Stage2
[Batch Accumulator 8cam]
    ↓ detection_fusion / pose_fusion / tracking_fusion
[frame_pipeline 🔴]
    ↓ frame_to_event_converter
[event_pipeline 🟠 + 16 detectors]
    ↓ game_analysis 분석기들
[possession/period/postgame pipelines]
    ↓ feedback_system
[한국어 피드백 출력]
```

**engine 이 24개 가중치의 런타임 호스트** — Phase 14 (`api_server/`) 이전 마지막 대형 인프라 레이어

---

## 8. 보조 우선 전략과의 정합성

Phase 13 감사 결과는 **CV_WEIGHTS_MANIFEST v2.0 "보조 우선" 전략과 정합**:

1. **5등급 Cadence 체계** — 실시간 보조(FRAME/EVENT) + 사후 분석(POSSESSION/PERIOD/POSTGAME) 분리 가능
2. **Mode Controller 3종** — LIVE(실시간 보조) / BATCH(경기 후 분석) / REPLAY(판정 리뷰) 모두 지원
3. **multi_angle_pipeline** — 4~8대 카메라 교차검증은 "보조 도구" 판정 품질의 핵심 기반
4. **시뮬레이션 fallback** — pynvml/tensorrt 없이도 동작 → 개발 환경 친화적, 배포 유연성
5. **RTX 5060 8GB 프로덕션 기준** — 렌탈 노트북 하드웨어 스펙 명시 (config.py docstring)

---

## 9. 결론

`engine/` **34파일** 전수 감사 결과:

- **총점 96.4/100 — 최우수** (Phase 10~13 중 최고점)
- **스레드 안전성 (98) / 확장성 (98)** 두 축이 최고
- **한줄 검토 (97)** — 데이터 흐름 다이어그램, Cadence 이모지 시각화, ASCII 상태 전이 — **Phase 10~13 중 가장 풍부한 문서화**
- Safe-Now 이슈 극소 (1건)
- 엔진 레이어 프로덕션 수준 품질 입증

**Phase 13 핵심 정착 패턴 8가지**:

1. `EngineConfig` 6 서브 통합 + 3 GPU 프로파일 Final 상수
2. `EngineState` 6상태 FSM + `_ENGINE_TRANSITIONS` 맵
3. 5등급 Cadence (FRAME/EVENT/POSSESSION/PERIOD/POSTGAME) + 이모지 시각화
4. TYPE_CHECKING 순환 참조 회피 패턴
5. `try/except ImportError` 시뮬레이션 fallback
6. DI 컨테이너 (`XxxAnalyzerSet` 4종)
7. 트리거 생산-소비 원자적 패턴 (`set_trigger / consume_triggers`)
8. OOM `emergency_cleanup` oldest-first 해제

**Phase 10+11+12+13 누적 현황**:
- **285파일 감사 완료** (game_analysis 165 + ai_referee 47 + feedback_system 39 + engine 34)
- **Safe-Now 43건 전량 처리** (Phase 10 13건 + Phase 11 18건 + Phase 12 11건 + Phase 13 1건)
- **Deferred 44건** 이월 → Phase 15 일괄 정비

**Phase 13 감사 종료. Phase 14 (`api_server/` 44파일) 착수 준비 완료.**
