# Phase 15 세션 9 — H1+H2+H3 motion_analysis 서브디렉토리 이전

**실행일**: 2026-04-20
**범위**: Tier 2 High H1/H2/H3 일괄 (motion_analysis 3개 서브패키지 재배치)
**결과**: **3디렉토리 이동, 14파일 수정, 테스트 122+16 전량 통과**

---

## 1. 실행 내역

### ✅ H1. `motion_analysis/phase_analysis/` → `biomechanics/phase_analysis/`

**이유**: 위상 분석(ShotPhase/DribblePhase 분해)은 생체역학 분석의 선행 단계로 `biomechanics/` 계층에 속함.

**이동 파일**:
- `__init__.py` (44줄)
- `shot_phase_analyzer.py` (866줄)
- `dribble_phase_analyzer.py` (797줄)

### ✅ H2. `motion_analysis/form_evaluation/` → `feedback_system/form_evaluation/`

**이유**: 폼 평가(슈팅/드리블 8카테고리 채점)는 피드백 생성의 입력 단계로 `feedback_system/` 계층에 속함.

**이동 파일**:
- `__init__.py` (54줄)
- `shooting_criteria.py` (677줄)
- `shooting_form_evaluator.py` (1,070줄)
- `dribble_criteria.py` (658줄)
- `dribble_form_evaluator.py` (897줄)

### ✅ H3. `motion_analysis/comparison/` → `feedback_system/comparison/`

**이유**: 폼 비교(DTW 기반 정답 영상 대비)는 피드백 생성의 입력으로 `feedback_system/` 계층.

**이동 파일**:
- `__init__.py` (35줄)
- `form_comparator.py` (1,236줄)

### 총 이동: **10파일 / 6,334줄**

---

## 2. 수정 내역

### Self-reference import 수정 (이동된 파일 내부)

| 파일 | 변경 |
|---|---|
| `biomechanics/phase_analysis/__init__.py` | `from motion_analysis.phase_analysis.X` → `from biomechanics.phase_analysis.X` |
| `feedback_system/form_evaluation/__init__.py` | 4곳 `motion_analysis.form_evaluation` → `feedback_system.form_evaluation` |
| `feedback_system/form_evaluation/shooting_form_evaluator.py` | `.shooting_criteria` self-ref |
| `feedback_system/form_evaluation/dribble_form_evaluator.py` | `.dribble_criteria` self-ref |
| `feedback_system/form_evaluation/dribble_criteria.py` | `.shooting_criteria` cross-ref |
| `feedback_system/comparison/__init__.py` | `.form_comparator` self-ref |

### motion_analysis/__init__.py 정리

**Before** (Tier 1-5 전체 re-export):
```python
from motion_analysis.phase_analysis import ShotPhaseAnalyzer, DribblePhaseAnalyzer
from motion_analysis.form_evaluation import (ShootingCriteria, ...)
from motion_analysis.comparison import FormComparator
__all__ = [..., "ShotPhaseAnalyzer", ..., "FormComparator"]
```

**After** (Tier 1-2만 유지, Tier 3-5 주석 가이드):
```python
# Tier 3-5는 Phase 15 H1-H3에서 이전됨:
#   phase_analysis   → biomechanics.phase_analysis
#   form_evaluation  → feedback_system.form_evaluation
#   comparison       → feedback_system.comparison
__all__ = [..., Tier 1-2만]
```

- Breaking: `from motion_analysis import ShotPhaseAnalyzer` 등은 **더 이상 작동하지 않음**
- 신규 경로: `from biomechanics.phase_analysis import ShotPhaseAnalyzer`

### Consumer import 교체

**실행 파일**:
- [engine/orchestrator/game_orchestrator.py](engine/orchestrator/game_orchestrator.py) — 5개 import 라인 교체

**테스트 파일** (7파일):
- `tests/motion_analysis/phase_analysis/unit/test_phase_analyzers.py` — 2건
- `tests/motion_analysis/performance/test_performance.py` — 4건
- `tests/motion_analysis/integration/test_tier4_to_tier5.py` — 3건
- `tests/motion_analysis/integration/test_tier3_to_tier4.py` — 6건
- `tests/motion_analysis/integration/test_tier1_to_tier5_e2e.py` — 4건
- `tests/motion_analysis/form_evaluation/unit/test_form_evaluators.py` — 4건
- `tests/motion_analysis/comparison/unit/test_form_comparator.py` — 1건

**참고**: `tests/motion_analysis/` 디렉토리명은 이번 세션 범위에서 유지 (import만 교체). 장기적으로 `tests/biomechanics/phase_analysis/` + `tests/feedback_system/form_evaluation/` 로 재배치 가능.

---

## 3. 런타임 검증

### 신규 경로 import OK

```python
>>> from biomechanics.phase_analysis import ShotPhaseAnalyzer, DribblePhaseAnalyzer
>>> from feedback_system.form_evaluation import ShootingCriteria, DribbleCriteria, ShootingFormEvaluator, DribbleFormEvaluator, RangeJudgment
>>> from feedback_system.comparison import FormComparator
>>> from engine.orchestrator.game_orchestrator import GameOrchestrator
New paths OK
GameOrchestrator import OK
```

### motion_analysis 축소 확인

```python
>>> import motion_analysis
>>> assert 'ShotPhaseAnalyzer' not in motion_analysis.__all__
>>> assert 'ShotDetector' in motion_analysis.__all__
motion_analysis.__all__ correctly updated
```

### 테스트 통과

| 테스트 그룹 | 통과 |
|---|---|
| `tests/motion_analysis/phase_analysis/unit/` | 24 |
| `tests/motion_analysis/form_evaluation/unit/` | 41 |
| `tests/motion_analysis/comparison/unit/` | 9 |
| `tests/motion_analysis/integration/` | 41 |
| `tests/motion_analysis/performance/` | 7 |
| **H1-H3 합계** | **122** |
| `tests/feedback_system/templates/unit/` (세션 8 호환성) | 16 |
| **총합** | **138** |

### Phase 15 누적 호환성

- H5 SSOT (GRAVITY=9.80665, HOOP_RADIUS=0.2286, QUARTER_DURATION_NBA=720, .wmv in SUPPORTED_VIDEO_EXTENSIONS) ✓
- H6 korean_templates 분할 (40+40 폼 템플릿 조회 정상) ✓
- M4 가중치 Config (CoachReportConfig 0.60+0.40=1.0) ✓
- M5 리그별 분기 (KBL eFG=49.0) ✓

---

## 4. 영향 범위

| 변경 유형 | 디렉토리/파일 수 | 비고 |
|---|---|---|
| 디렉토리 이동 | 3 | phase_analysis, form_evaluation, comparison |
| 파일 이동 | 10 | (이동 + 내부 self-ref 수정) |
| `motion_analysis/__init__.py` | 1 | 축소 (Tier 3-5 re-export 제거) |
| Consumer import 교체 | 8 | orchestrator 1 + tests 7 |
| **합계 수정 파일** | **~14** | 이동 자체 제외 (파일 내용은 import만 변경) |

### Breaking change 분석

**있음** (의도적):

- `from motion_analysis import ShotPhaseAnalyzer` → **더 이상 작동하지 않음**
  - 신규: `from biomechanics.phase_analysis import ShotPhaseAnalyzer`
- `from motion_analysis import ShootingFormEvaluator, FormComparator` 등 동일
- `from motion_analysis.phase_analysis import X` → `from biomechanics.phase_analysis import X`
- `from motion_analysis.form_evaluation import X` → `from feedback_system.form_evaluation import X`
- `from motion_analysis.comparison import X` → `from feedback_system.comparison import X`

**검색 결과 외부 consumer 0건**: 코드베이스 내 `motion_analysis.(phase_analysis|form_evaluation|comparison)` 참조는 docs/audit 문서에만 남아 있음 (런타임 영향 없음).

---

## 5. 계층 구조 정리 효과

### Before (혼재)

```
motion_analysis/       # Layer 4 (동작 분석, 5-Tier)
├── detection/         # Tier 1: 감지
├── classification/    # Tier 2: 분류
├── phase_analysis/    # Tier 3: 위상
├── form_evaluation/   # Tier 4: 폼 평가  ← 본래 feedback 성격
├── comparison/        # Tier 5: 비교      ← 본래 feedback 성격
└── models.py
```

### After (계층 분리)

```
motion_analysis/       # Layer 4 (동작 감지/분류만)
├── detection/         # Tier 1
├── classification/    # Tier 2
└── models.py

biomechanics/          # Layer 3 (생체역학)
└── phase_analysis/    # 위상 분해 — biomech 계층으로 이전

feedback_system/       # Layer 7 (피드백)
├── form_evaluation/   # 폼 평가 — 피드백 입력단
├── comparison/        # 폼 비교 — 피드백 입력단
├── templates/
├── coach/
├── analysis/
└── report/
```

**관심사 분리**:
- 순수 **검출/분류**는 `motion_analysis/` (Layer 4)
- 분석을 위한 **위상 분해**는 `biomechanics/` (Layer 3)
- 피드백 생성에 쓰이는 **평가/비교**는 `feedback_system/` (Layer 7)

---

## 6. Phase 15 누적 진행도

| 세션 | Tier | 처리 건수 | 파일 변경 |
|---|---|---|---|
| 1 | Tier 1 + Tier 4 | 9 | 24 |
| 2 | Tier 3 M1 | 10 | 4 |
| 3 | Tier 5 | 7 | 5 |
| 4 | Tier 3 M2 | 31 | 32 |
| 5 | Tier 3 M3 | 26 | 29 |
| 6 | Tier 3 M4+M5 | 4 | 4 |
| 7 | Tier 2 H5 | 7 | 7 |
| 8 | Tier 2 H6 | 1 | 8 |
| **9** | **Tier 2 H1+H2+H3** | **3** | **14** |
| **합계** | — | **98** | **127** |

### 남은 Phase 15 작업 (1건)

| ID | 작업 | 예상 작업량 |
|---|---|---|
| **H4** | Facade 5개 engine 데이터 연동 구현 | 중 (engine 통합 테스트 완료 의존) |

---

## 7. 다음 세션 제안

**세션 10 권장**: **H4 Facade 5개 engine 연동 구현** (마지막 Tier 2 항목)

- **대상 Facade** (5개):
  - GameStatsEngine
  - HighlightEngine
  - RefereeEngine
  - ReportEngine
  - TacticalEngine
- **작업**: 각 Facade 클래스에 실제 engine 데이터 연동 (현재 placeholder/stub 상태)
- **의존성**: engine 통합 테스트 완료 여부 확인 필요

**Phase 15 완료 시점**: 세션 10 완료 후 전체 98+N건 처리, Tier 1-5 전량 마감.

---

**세션 9 완료. motion_analysis 3개 서브패키지 이전 (6,334줄 이동). 계층 구조 정리 완료. 테스트 138/138 통과. 의도적 breaking change 있음 (import 경로 변경).**
