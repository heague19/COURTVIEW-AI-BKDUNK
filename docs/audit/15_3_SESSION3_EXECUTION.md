# Phase 15 세션 3 — Tier 5 Optional 일괄 정리

**실행일**: 2026-04-20
**범위**: Tier 5 Optional (7건)
**결과**: **7/7 완료** (100%)

---

## 1. 실행 내역

### ✅ O6. `DEFAULT_VRAM_BUDGET_MB` 14000 → 6000

- **파일**: [core_foundation/registry/model_registry.py:40](core_foundation/registry/model_registry.py#L40)
- **상태**: **이미 6000.0 으로 적용됨** (Phase 02 이후 반영된 것으로 확인) — Skip

### ✅ O3. `GameContext` `dataclasses.replace` 간소화

- **파일**: [engine/game_state.py](engine/game_state.py)
- **변경**:
  ```python
  # Before: 11필드 수동 복사
  return GameContext(
      game_state=self._context.game_state,
      quarter=self._context.quarter,
      ... (11 fields)
  )

  # After
  return replace(self._context)
  ```
- **import 추가**: `from dataclasses import dataclass, field, replace`
- **효과**: 11줄 → 1줄, 유지보수 용이 (새 필드 추가 시 자동 반영)

### ✅ O1. `gpu_manager` pynvml 모듈 레벨 flag

- **파일**: [engine/gpu/gpu_manager.py](engine/gpu/gpu_manager.py)
- **변경**:
  - 모듈 상단에 `try: import pynvml; _PYNVML_AVAILABLE = True except ImportError: pynvml = None; _PYNVML_AVAILABLE = False`
  - 함수 내부 3개 local import 제거 (initialize / shutdown / _read_temperature)
  - `_PYNVML_AVAILABLE` flag 로 early-return 패턴
- **효과**: 매 호출 시 import 체크 오버헤드 제거, PEP 8 준수

### ✅ O2. `analysis_buffer` MotionSnapshot 모듈 레벨

- **파일**: [engine/analysis_buffer.py](engine/analysis_buffer.py)
- **변경**:
  - 모듈 상단 `try: from motion_analysis.models import MotionSnapshot; _MOTION_SNAPSHOT_AVAILABLE = True except ImportError`
  - `_update_motion_windows` 함수 내부 local import 제거
  - `if not _MOTION_SNAPSHOT_AVAILABLE: return` early-return
- **효과**: 매 프레임 호출 시 import 오버헤드 제거

### ✅ O4. `frame_to_event_converter` 코트 좌표계 주석

- **파일**: [engine/pipeline/frame_to_event_converter.py](engine/pipeline/frame_to_event_converter.py)
- **변경**: 파일 상단에 좌표계 주의 블록 주석 추가
  - 현재: 픽셀 좌표계 기반
  - 장기 로드맵: 코트 좌표계 (미터) 전환 — 호모그래피 경유
  - `_PX_TO_M`, `_POSSESSION_DIST_PX` 상수에 "Phase 15에서 코트 좌표계 전환 예정" 주석 추가
- **효과**: 미래 마이그레이션 의도 명확화 (실제 전환은 H-tier 리팩토링)

### ✅ O5. `reid_module.py` DEPRECATED 마크

- **파일**: [detection/player_detection/reid_module.py](detection/player_detection/reid_module.py)
- **결정**: `_deprecated/` 이동 대신 **DEPRECATED 마크 + `DeprecationWarning`** 부착 선택
- **이유**:
  - `__init__.py` 에서 이미 export 제외됨 (주석 처리 확인)
  - 테스트 파일 1개(`tests/detection/player_detection/performance/test_player_detection_perf.py`)가 직접 import
  - 즉시 이동 시 테스트 깨짐 → 테스트 업데이트 전까지 DEPRECATED 마크로 점진 제거
- **변경**:
  - docstring에 DEPRECATED (Phase 15 P15-06-DC1 확정) 경고
  - 모듈 로딩 시 `warnings.warn(..., DeprecationWarning)` 발동
  - 대체 모듈 명시 (`PlayerDetector` + digit/team 조합)
- **효과**: 921줄 dead code 점진적 제거 경로 확립

### ✅ O7. motion_analysis `classification/` DEPRECATED 예고

- **파일**: [motion_analysis/classification/__init__.py](motion_analysis/classification/__init__.py)
- **결정**: CV-action.pt 학습 가중치 배포 **전** 이므로 **PendingDeprecationWarning**으로 예고만
- **변경**:
  - docstring에 DEPRECATED 예고 (P15-09-L2)
  - `warnings.warn(..., PendingDeprecationWarning)` 모듈 로딩 시 발동
  - 대체 경로 명시 (CV-action.pt BiLSTM/Transformer, 7-class)
- **효과**: SV-action ML 모델 배포 시 자연 교체 경로 확립

---

## 2. 영향 범위

| 디렉토리 | 파일 수 |
|---|---|
| `engine/` | 3 (game_state + gpu_manager + analysis_buffer + frame_to_event_converter) |
| `detection/player_detection/` | 1 (reid_module.py) |
| `motion_analysis/classification/` | 1 (__init__.py) |
| **합계** | **5파일** |

### 호환성

- **Breaking change**: **없음**
  - `dataclasses.replace` 는 기존 동작과 완전 동일 (새 인스턴스 반환)
  - pynvml/MotionSnapshot 모듈 레벨 import 는 기존 local import 와 동일 동작 (fallback 패턴 보존)
  - `DeprecationWarning` 은 경고만 발동, 기존 코드 동작 불변
  - frame_to_event_converter 주석만 추가 (로직 불변)

---

## 3. Phase 15 누적 진행도

| 세션 | Tier | 처리 건수 | 파일 변경 |
|---|---|---|---|
| **1** | Tier 1 + Tier 4 | 9 | 24 |
| **2** | Tier 3 M1 | 10 (6 property + 10 접근 교체) | 4 |
| **3** | Tier 5 Optional | 7 (O6 Skip) | 5 |
| **합계** | — | **26** | **33** |

### 남은 Phase 15 작업

**Tier 3 Medium (4건)**:
- M2 age_group 문자열 → AgeGroup enum
- M3 Generator 인스턴스 싱글톤화
- M4 Config 가중치 승격 (매직 넘버)
- M5 리그별 Config 분기

**Tier 2 High (6건, 대규모)**:
- H1/H2/H3 motion_analysis 디렉토리 이전
- H4 Facade 5개 engine 연동 구현
- H5 shared.constants SSOT 확립
- H6 korean_templates.py 1,630줄 분할

---

## 4. 다음 세션 제안

**세션 4 권장**: Tier 3 Medium **M2 (age_group enum)** 집중

- `AgeGroup` enum은 이미 `shared/constants/player_constants` 에 존재
- `feedback_system/` 전반에 `age_group: str = "adult"` 문자열 → enum 타입 교체
- 영향 파일: ~27 (feedback_system 24 + game_service 등)
- 예상 시간: 40분

**대안**: Tier 2 High **H5 shared.constants SSOT 확립** — 전 모듈 영향

**대안 2**: Tier 3 **M1/M3/M4/M5 일괄** — 설계 변경 완료 후 H-tier 착수

어느 방향으로?

---

**세션 3 완료. Tier 5 Optional 7건 전량 처리. Breaking change 없음.**
