# Phase 15 세션 2 — M1 GameOrchestrator Public Getter

**실행일**: 2026-04-20
**범위**: Tier 3 Medium M1 (GameOrchestrator 캡슐화)
**결과**: **완료** — 6 property 추가 + 10개 private 접근 교체

---

## 1. 실행 내역

### ✅ GameOrchestrator에 6개 public property 추가

**파일**: [engine/orchestrator/game_orchestrator.py](engine/orchestrator/game_orchestrator.py)

| Property | 반환 타입 | 용도 |
|---|---|---|
| `gpu_manager` | `GPUManager \| None` | GPU 리소스 메트릭 조회 |
| `trt_pool` | `TensorRTPool \| None` | 로드된 모델 상태 조회 |
| `batch_accumulator` | `BatchAccumulator \| None` | 추론 카운터 조회 |
| `result_dispatcher` | `ResultDispatcher \| None` | 큐 상태 + WS 메시지 소비 |
| `progress_reporter` | `ProgressReporter \| None` | 실시간 FPS + 진행률 조회 |
| `referee` | `RefereeOrchestrator \| None` | 판정 이벤트 카운터 조회 |

### ✅ 10개 private 접근 지점 → public property 교체

| 파일 | 변경 |
|---|---|
| **metrics_routes.py** (7회) | `_gpu_manager×3 + _trt_pool×2 + _batch_accumulator×2 + _progress_reporter×2 + _referee×2` → public |
| **game_routes.py** (2회) | `_result_dispatcher` + `_stats` → `result_dispatcher` + `stats` |
| **progress_handler.py** (1회) | `_result_dispatcher` → `result_dispatcher` |
| **합계** | **10 접근 지점** |

참고: `metrics_routes.py` 의 일부 접근은 `replace_all`로 한 번에 교체 (패턴 반복).

---

## 2. 캡슐화 효과

### Before (Phase 14B 지적)
```python
# metrics_routes.py
if orchestrator._gpu_manager is not None:      # private 접근
    snap = orchestrator._gpu_manager.snapshot()
```

### After
```python
if orchestrator.gpu_manager is not None:        # public API
    snap = orchestrator.gpu_manager.snapshot()
```

### 이점

1. **GameOrchestrator 내부 구현 변경 자유** — `_gpu_manager` → `_gpu_mgr` 리네임 시 외부 영향 없음
2. **타입 검사 강화** — property 반환 타입 명시로 IDE 자동완성 지원
3. **모킹 용이** — 테스트 시 property override 가능
4. **docstring 포함** — 외부 호출자에게 의도 명확

---

## 3. 영향 범위

| 디렉토리 | 파일 수 |
|---|---|
| `engine/orchestrator/` | 1 (game_orchestrator.py) |
| `api_server/routes/v1/` | 2 (metrics_routes.py, game_routes.py) |
| `api_server/websocket/` | 1 (progress_handler.py) |
| **합계** | **4파일** |

### 호환성

- **Breaking change**: **없음** — 기존 코드의 `_*` 접근은 여전히 동작 (Python 관습상 private)
- **신규 property**: 모두 `@property` 데코레이터로 동일 객체 반환 (wrapper 오버헤드 없음)

---

## 4. 남은 Phase 15 작업

### Tier 5 Optional (7건, 다음 세션)

| ID | 작업 | 파일 수 |
|---|---|---|
| O1 | `gpu_manager` pynvml local import → 모듈 레벨 flag | 1 |
| O2 | `analysis_buffer` MotionSnapshot local import | 1 |
| O3 | `GameContext` `dataclasses.replace` 간소화 | 1 |
| O4 | `frame_to_event_converter` 픽셀 단위 → 코트 좌표계 | 1 |
| O5 | `reid_module.py` 921줄 dead code 처리 | 사용자 결정 |
| O6 | `DEFAULT_VRAM_BUDGET_MB` 14000 → 6000 | 1 (core_foundation) |
| O7 | motion_analysis `classification/` DEPRECATE | SV-action 배포 후 |

### Tier 3 Medium 나머지

- M2 age_group 문자열 → AgeGroup enum
- M3 Generator 인스턴스 싱글톤화
- M4 Config 가중치 승격 (매직 넘버)
- M5 리그별 Config 분기

### Tier 2 High (대규모 리팩토링, 별도 세션)

- H1/H2/H3 motion_analysis 디렉토리 이전 (biomechanics/feedback_system)
- H4 Facade 5개 engine 연동 구현
- H5 shared.constants SSOT 확립
- H6 korean_templates.py 1,630줄 분할

---

## 5. 다음 세션 제안

**세션 3 권장**: Tier 5 Optional **빠른 정리 7건 일괄**

- 각각 1~3줄 수정 수준 (O4/O5 제외)
- O5 reid_module.py 921줄 처리는 사용자 결정 필요
- 예상 파일 변경: ~6-7파일

**대안**: Tier 3 Medium **M2 (age_group enum)** 집중 — feedback_system 전반 영향

---

**세션 2 완료. GameOrchestrator 캡슐화 강화. 10 private 접근 지점 제거.**
