# Phase 15 세션 8 — H6 korean_templates.py 1,630줄 분할

**실행일**: 2026-04-20
**범위**: Tier 2 High H6 (단일 1,630줄 파일 → 도메인별 8파일 분할)
**결과**: **1→8파일 분할, 기존 공개 API 100% 보존, 테스트 16/16 통과**

---

## 1. 배경

### 이전 상태

`feedback_system/templates/korean_templates.py` — **단일 파일 1,630줄**:
- 슈팅 폼 40 + 드리블 폼 40 템플릿 (TemplateEntry dict)
- 비교 4 + 훈련 2 템플릿
- 5개 패턴 템플릿 (score/comparison/trend/tactical/referee)
- 6개 관절 × 2방향 편차 표현 + 속도/균형/착지/에너지 편차 표현
- 유소년 용어 치환 맵 (23개)
- 14개 카테고리 × 3~5개 변형 문장 풀
- `KoreanTemplates` 클래스 (420+ 줄)
- `TemplateVariationEngine` 클래스 (120+ 줄)
- `DeviationExpression` dataclass + 5개 편차 조회 함수

### 문제점

- 단일 파일 1,630줄 → IDE 탐색/편집 부담
- 데이터/로직/클래스가 한 파일에 혼재
- 유지보수 시 전체 파일을 읽어야 하는 오버헤드

---

## 2. 분할 결과

### 신규 파일 구조

```
feedback_system/templates/
├── _types.py                    (신규,  46줄) — 공유 dataclass
├── _form_data.py                (신규, 558줄) — 슈팅+드리블 템플릿 (80개)
├── _pattern_data.py             (신규, 160줄) — 비교+패턴+훈련+유소년
├── _deviation_data.py           (신규, 237줄) — 편차 표현 사전
├── _variation_data.py           (신규, 114줄) — 변형 문장 풀
├── deviation_expressions.py     (신규, 183줄) — 편차 조회 함수 5개
├── variation_engine.py          (신규, 147줄) — TemplateVariationEngine
└── korean_templates.py          (재작성, 318줄) — 오케스트레이터
                                  ──────────
                              총  1,763줄 (+133줄, 대부분 헤더/import)
```

**원본 1,630줄 → 오케스트레이터 318줄 (80% 감소)**

### 파일별 역할

| 파일 | 역할 | 내용 |
|---|---|---|
| `_types.py` | 공유 dataclass | TemplateEntry, DeviationExpression (circular import 방지) |
| `_form_data.py` | 폼 템플릿 데이터 | SHOOTING_TEMPLATES (40), DRIBBLE_TEMPLATES (40) |
| `_pattern_data.py` | 패턴/비교/훈련 데이터 | 7개 dict (COMPARISON/5-PATTERN/TRAINING), 유소년 맵 |
| `_deviation_data.py` | 편차 표현 사전 | 6개 관절 × 2방향 + 속도/균형/착지/에너지 + 코치 문미 |
| `_variation_data.py` | 변형 문장 풀 | VARIATION_POOL (14 카테고리) |
| `deviation_expressions.py` | 편차 조회 로직 | get_angle/speed/balance/landing/coach_ending |
| `variation_engine.py` | 변형 엔진 | TemplateVariationEngine 클래스 |
| `korean_templates.py` | 오케스트레이터 | KoreanTemplates 클래스 + 기존 공개 API 재노출 |

---

## 3. 공개 API 보존 (Breaking change 없음)

### 기존 import 경로 그대로 유지

```python
# 기존 (이전 버전 코드)
from feedback_system.templates.korean_templates import (
    KoreanTemplates,
    TemplateEntry,
    DeviationExpression,
    TemplateVariationEngine,
    get_angle_deviation_text,
    get_speed_deviation_text,
    get_balance_deviation_text,
    get_landing_text,
    get_coach_ending,
)

# → 모두 그대로 작동 (korean_templates.py가 내부에서 분할 모듈로부터 re-export)
```

### `feedback_system/templates/__init__.py` 변경 없음

기존 `__init__.py`는 `from feedback_system.templates.korean_templates import (...)` 만 있으므로, `korean_templates.py`가 re-export 체계를 유지하는 한 수정 불필요.

---

## 4. 런타임 검증

### 기능 검증

```
Form points: 40+40=80              ✓ (슈팅 40 + 드리블 40 포인트 전량 보존)
Comparison keys: 4                  ✓
Training keys: 2                    ✓
5 deviation helpers callable        ✓
Variation categories: 14            ✓
Deterministic variation OK          ✓ (같은 seed → 같은 문장)
Singleton OK                        ✓ (get_default_korean_templates())
Youth simplified: 공 놓기 각도       ✓ ("릴리스 각도" → "공 놓기 각도" 치환 작동)
=== H6 ALL TESTS PASSED ===
```

### 기존 테스트 통과

```
tests/feedback_system/templates/unit/test_template_variation_engine.py
................
16 passed in 1.01s
```

### Consumer 모듈 24/24 import OK

```
feedback_system.templates.korean_templates
feedback_system.templates.variation_engine
feedback_system.templates.deviation_expressions
feedback_system.templates._{types,form,pattern,deviation,variation}_data
feedback_system.coach.{motion,biomechanics}_feedback
feedback_system.analysis.{game,defensive,tactical,referee,individual,lineup,
                          rotation,spatial,opponent_tendency,strategic_recommendation}_feedback
feedback_system.report.{coach,game}_report_generator
```

---

## 5. 영향 범위

| 변경 유형 | 파일 수 | 비고 |
|---|---|---|
| 신규 파일 | 7 | `_types`, `_form_data`, `_pattern_data`, `_deviation_data`, `_variation_data`, `deviation_expressions`, `variation_engine` |
| 재작성 | 1 | `korean_templates.py` (1,630 → 318줄) |
| 미수정 (영향 X) | 24+ | 모든 consumer — 기존 import 경로 그대로 작동 |
| **합계** | **8파일** | **+7 / -0 / 재작성 1** |

### Breaking change 분석

**없음**:
- 모든 공개 심볼 (`KoreanTemplates`, `TemplateEntry`, `DeviationExpression`, `TemplateVariationEngine`, 5개 함수) 기존 import 경로 그대로 유지
- `feedback_system.templates.korean_templates.X` 로 접근 시 동일 객체 반환
- `TemplateEntry` / `DeviationExpression` 는 `_types.py`로 이동했지만 `korean_templates.py`에서 re-export — 기존 코드 영향 없음
- 메서드 시그니처/동작 완전 동일

---

## 6. 부가 이득

### 파일당 라인 수 극적 감소

- 기존: 단일 파일 1,630줄
- 신규: 최대 558줄 (`_form_data.py`, 슈팅+드리블 80개 템플릿 데이터)
- 그 외: 모두 318줄 이하

### 관심사 분리 (Separation of Concerns)

| 계층 | 파일 | 역할 |
|---|---|---|
| **데이터** | `_form_data`, `_pattern_data`, `_deviation_data`, `_variation_data` | 순수 상수 데이터 |
| **로직** | `deviation_expressions`, `variation_engine` | 비즈니스 로직 |
| **오케스트레이션** | `korean_templates` | 공개 API + 조합 |
| **공유 타입** | `_types` | circular import 방지용 dataclass |

### 향후 유지보수 용이

- 새 템플릿 추가 시 해당 데이터 파일만 편집
- 편차 로직 변경 시 `deviation_expressions.py` 만 터치
- 변형 문장 추가 시 `_variation_data.py`만 터치

---

## 7. Phase 15 누적 진행도

| 세션 | Tier | 처리 건수 | 파일 변경 |
|---|---|---|---|
| 1 | Tier 1 + Tier 4 | 9 | 24 |
| 2 | Tier 3 M1 | 10 | 4 |
| 3 | Tier 5 | 7 | 5 |
| 4 | Tier 3 M2 | 31 | 32 |
| 5 | Tier 3 M3 | 26 | 29 |
| 6 | Tier 3 M4+M5 | 4 | 4 |
| 7 | Tier 2 H5 | 7 | 7 |
| **8** | **Tier 2 H6** | **1** | **8** |
| **합계** | — | **95** | **113** |

### 남은 Phase 15 작업 (4건, Tier 2 High)

| ID | 작업 | 예상 작업량 |
|---|---|---|
| H1 | `motion_analysis/phase_analysis/` → `biomechanics/phase_analysis/` | 중 |
| H2 | `motion_analysis/form_evaluation/` → `feedback_system/form_evaluation/` | 중 |
| H3 | `motion_analysis/comparison/` → `feedback_system/comparison/` | 소 |
| H4 | Facade 5개 engine 연동 구현 | 중 (engine 통합 의존) |

---

## 8. 다음 세션 제안

**세션 9 권장**: **H1 + H2 + H3 일괄 이동** (~60분, motion_analysis 3개 서브디렉토리 재배치)

- **이유**: 세 작업 모두 `motion_analysis/` 내부 서브디렉토리 이동 + import 경로 교체. 일괄 처리가 import 수정 중복 제거에 유리.
- **작업**:
  - H1: `motion_analysis/phase_analysis/` → `biomechanics/phase_analysis/` (중)
  - H2: `motion_analysis/form_evaluation/` → `feedback_system/form_evaluation/` (중)
  - H3: `motion_analysis/comparison/` → `feedback_system/comparison/` (소)
  - 기존 `motion_analysis/__init__.py` 에서 re-export로 하위 호환 유지 (또는 DeprecationWarning)
  - 모든 consumer의 import 경로 일괄 교체 (자동화 스크립트)

**대안**: **H4 Facade engine 연동** — engine 통합 테스트 완료 여부에 의존. 우선도 낮음.

---

**세션 8 완료. korean_templates.py 1,630줄 단일 파일 → 8파일 분할. 공개 API 100% 보존. 테스트 16/16 + consumer 24/24 통과.**
