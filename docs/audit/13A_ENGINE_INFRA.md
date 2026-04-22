# 13A. engine/ {root + gpu + io + orchestrator + workers} 감사 리포트

**감사 범위**: root (4) + `gpu/` (5) + `io/` (4) + `orchestrator/` (4) + `workers/` (3) = **20파일**
**감사 방식**: 전수 직독 (Read 전용)
**감사 축**: 8종
**감사일**: 2026-04-20

---

## 1. 감사 대상 구성

| 디렉토리 | 파일 | 역할 |
|---|---|---|
| root (4) | `__init__`, `config`, `game_state`, `analysis_buffer` | 전역 설정 + FSM + 데이터 버퍼 |
| `gpu/` (5) | `__init__`, `gpu_manager`, `cuda_stream_manager`, `tensorrt_pool`, `batch_accumulator` | GPU 리소스 중앙 관리 |
| `io/` (4) | `__init__`, `frame_ingestion`, `progress_reporter`, `result_dispatcher` | 프레임 수집 + 진행률 + 결과 분배 |
| `orchestrator/` (4) | `__init__`, `cadence_scheduler`, `mode_controller`, `game_orchestrator` | Cadence 스케줄링 + 모드 + 전체 수명주기 |
| `workers/` (3) | `__init__`, `analysis_worker`, `export_worker` | POSSESSION/PERIOD/POSTGAME 비동기 워커 |

---

## 2. 감사 8축 평가

### 2.1 Import 유효성 ✅ 96/100

- 20파일 전체 `from __future__ import annotations` + SSOT 준수 ✓
- 서드파티 조건부 import (`try/except ImportError`) 패턴 일관 (pynvml, tensorrt_engine, motion_analysis.models)
- `TYPE_CHECKING` 활용 (analysis_worker, export_worker) — 순환 의존성 방지 ✓
- **관찰**: [gpu_manager.py](engine/gpu/gpu_manager.py) `import pynvml` 함수 내부 local import 3회 (line 199/244/382) — 선택적 의존성 + 시뮬레이션 fallback 의도. 모듈 레벨 try/except + `_PYNVML_AVAILABLE` flag로 개선 여지

### 2.2 기능 유효성 ✅ 97/100

- **engine/config.py**: 6 서브 Config (`GPU/Camera/Cadence/Pipeline/Referee/IO`) + `EngineConfig` 통합 + 3 GPU 프로파일 (`RTX_4060/5070/4090`)
- **engine/game_state.py**: 6상태 `EngineState` FSM + `_ENGINE_TRANSITIONS` 맵 + `GameContext` 방어적 복사 + 트리거 생산-소비 패턴
- **engine/analysis_buffer.py**: FrameBuffer → POSSESSION/PERIOD/POSTGAME 3단 빌더 + per-player 모션 윈도우 + FRAME 레벨 학습 데이터 자동 추출
- **gpu_manager**: pynvml 연동 + 시뮬레이션 fallback + 5단계 HealthStatus + OOM 방어 (oldest-first `emergency_cleanup`)
- **cadence_scheduler**: GameState → Cadence 매핑 + 트리거 기반 파이프라인 활성화
- **game_orchestrator**: 전체 수명주기 + 모든 서브 모듈 통합 (~70 import)
- **analysis_worker**: possession(4T) + period(2T) 이중 풀 + `_MAX_PENDING_TASKS=50` 제한

### 2.3 메모리 누수 방지 ✅ 97/100

- `_MAX_FRAME_BUFFER=900` (30fps × 30초) + deque maxlen 링 버퍼 ✓
- `_MOTION_WINDOW_SIZE=30` per-player deque ✓
- `_MAX_ALLOCATIONS=100` + `emergency_cleanup` oldest-first ✓
- `_MAX_CALLBACKS=50` / `_MAX_CALLBACKS_PER_CADENCE=10` / `_MAX_TICK_HISTORY=200` / `_MAX_QUEUE_SIZE=500` / `_MAX_DISPATCH_HISTORY=200` / `_MAX_PENDING_TASKS=50` — 전체 상한 체계화
- `get_frame_extractions()` 반환 시 자동 clear (POSTGAME 소비 후 즉시 해제) ✓

### 2.4 하드코딩 점검 ✅ 92/100

- 대부분의 매직 넘버가 `_Final[T]` 모듈 상수 또는 Config 필드로 노출
- 상수 의미 주석 철저 (`# 30fps × 30초 = 900`)
- **관찰**: RTX 4060/5070/4090 프로파일만 존재 — 사용자 언급 렌탈 노트북 타깃(RTX 4070/4080)은 프리셋 미제공 (Deferred)
- **관찰**: `_SIMULATION_TOTAL_VRAM_MB=8192` / `_SIMULATION_TEMPERATURE=45.0` 기본 시뮬레이션 값

### 2.5 한줄 검토 ✅ 97/100

- 20파일 전체 docstring + 의존성 + 소비자 + 데이터 흐름 + 참조 일관
- 상태 전이 다이어그램 ASCII 아트 (`game_state.py`) ✓
- 의미 있는 이모지 (🔴🟠🟡🟢🔵) 활용 — Cadence 등급 시각화
- CLAUDE.md community_49 ASECAM 지시 명시

### 2.6 스레드 안전성 ✅ 98/100

- 20파일 전체 `RLock` + `with self._lock:` + `__slots__` 수동 선언
- 콜백 실행은 lock 해제 후 수행 (블로킹 방지) ✓ [game_state.py:271-275](engine/game_state.py#L271-L275)
- GPU 스냅샷 frozen dataclass 방어적 복사 ✓
- GameContext 11필드 수동 복사 방어적 복사 ✓

### 2.7 예외 처리 ✅ 96/100

- `try/except ImportError` → 시뮬레이션 fallback 패턴 일관 (pynvml, tensorrt, motion_analysis)
- `ValueError` 상태 전이 불가 시 발생 + 허용 상태 목록 포함 ✓
- `logger.exception()` 콜백 오류 포착 ✓
- `_read_temperature` pynvml 실패 시 `_SIMULATION_TEMPERATURE` fallback ✓

### 2.8 확장성 ✅ 98/100

- `EngineStateCallback` 콜백 등록 패턴
- `register_state_callback` / `set_trigger` / `consume_triggers` 이벤트 드리븐
- `GPUConfig` / `CameraConfig` / `CadenceConfig` 독립 주입 가능
- 3 GPU 프로파일 (4060/5070/4090) Final 상수 — 하드웨어별 프리셋 확장 용이
- **Phase 13 최고 점수 축**

---

## 3. Safe-Now 이슈 목록 (0건)

**Phase 13A 는 엔진 인프라 레이어로 매우 정제된 코드 품질**. Safe-Now 처리가 필요한 이슈 없음.

---

## 4. Phase 15 Deferred 이슈 (4건)

### P15-13A-01. `gpu_manager` pynvml local import 패턴

- [gpu_manager.py:199/244/382](engine/gpu/gpu_manager.py#L199) `import pynvml` 함수 내부 3회 반복
- **방안**: 모듈 레벨에 `try: import pynvml; _PYNVML_AVAILABLE = True except ImportError: pynvml = None; _PYNVML_AVAILABLE = False` 도입

### P15-13A-02. RTX 4070/4080 프로파일 부재

- [config.py](engine/config.py) 3 GPU 프로파일(`RTX_4060/5070/4090`) — 사용자 언급 렌탈 노트북 타깃(RTX 4070/4080) 미포함
- **방안**: `RTX_4070_PROFILE`, `RTX_4080_PROFILE` 추가 (16GB/12GB VRAM 기준)

### P15-13A-03. `analysis_buffer` MotionSnapshot local import

- [analysis_buffer.py:238](engine/analysis_buffer.py#L238) `from motion_analysis.models import MotionSnapshot` 함수 내부
- 매 프레임 `_update_motion_windows` 호출 시 import 체크 오버헤드
- **방안**: 모듈 레벨 `try/except ImportError` + `_MOTION_SNAPSHOT_AVAILABLE` flag

### P15-13A-04. `GameContext` 방어적 복사 간소화

- [game_state.py:336-349](engine/game_state.py#L336-L349) 11필드 수동 복사 → `dataclasses.replace(self._context)` 사용으로 간결화

---

## 5. 13A 종합 점수

| 축 | 점수 |
|---|---|
| Import 유효성 | 96 |
| 기능 유효성 | 97 |
| 메모리 누수 방지 | 97 |
| 하드코딩 점검 | 92 |
| 한줄 검토 | 97 |
| 스레드 안전성 | 98 |
| 예외 처리 | 96 |
| 확장성 | 98 |
| **총점** | **96.4** |

**Phase 10~13 서브페이즈 중 최고 점수** (이전 최고는 11D 94.5)

---

## 6. 관찰된 강점

1. **6 서브 Config + 3 GPU 프로파일** — 하드웨어별 프리셋 체계화 (`RTX_4060/5070/4090_PROFILE`)
2. **6상태 `EngineState` FSM** + `_ENGINE_TRANSITIONS` 맵 — 엄격한 상태 전이 제어
3. **`GameState → Cadence` 매핑** — `_GAME_STATE_CADENCE_MAP` 9상태 × 5 Cadence 테이블
4. **트리거 생산-소비 패턴** — `set_trigger / consume_triggers` 원자적 읽기+리셋
5. **pynvml 조건부 연동 + 시뮬레이션 fallback** — 환경 무관 동작 보장
6. **OOM 방어** — `emergency_cleanup` oldest-first 해제 + WARNING 80% 목표 복귀
7. **이중 Cadence 스레드풀** — possession(4T) + period(2T) 독립 관리
8. **per-player 모션 윈도우** — `deque(maxlen=30)` 자동 트림 + 학습 데이터 자동 추출
9. **방어적 복사 철저** — `GPUSnapshot`/`GameContext` frozen dataclass
10. **CLAUDE.md 하드웨어 지시 직접 준수** — ASECAM 듀얼 스트림 (분석 1080p + 녹화 4K), community_49

---

## 7. 관찰된 약점

1. **local import 2곳** — pynvml(`gpu_manager`) / MotionSnapshot(`analysis_buffer`) — 기능적 문제는 없으나 PEP 8 관점 개선 여지
2. **RTX 4070/4080 프로파일 누락** — 타깃 하드웨어 대응 여지
3. **`GameContext` 11필드 수동 복사** — `dataclasses.replace` 간결화 여지

---

## 8. 다음 작업

1. Safe-Now 이슈 **없음** — 바로 Phase 13B 진행 가능
2. Phase 13B `pipeline + fusion + referee` 14파일 착수
