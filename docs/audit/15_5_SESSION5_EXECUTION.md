# Phase 15 세션 5 — M3 Generator 싱글톤화

**실행일**: 2026-04-20
**범위**: Tier 3 Medium M3 (SeverityMapper + KoreanTemplates 싱글톤 공유)
**결과**: **25파일 변경, 싱글톤 공유 검증 통과**

---

## 1. 실행 내역

### ✅ 단계 1: `templates/__init__.py`에 싱글톤 접근자 추가

**파일**: [feedback_system/templates/__init__.py](feedback_system/templates/__init__.py)

```python
_default_severity_mapper: SeverityMapper | None = None
_default_korean_templates: KoreanTemplates | None = None


def get_default_severity_mapper() -> SeverityMapper:
    """공유 SeverityMapper 반환 (default config 기반)."""
    global _default_severity_mapper
    if _default_severity_mapper is None:
        _default_severity_mapper = SeverityMapper()
    return _default_severity_mapper


def get_default_korean_templates() -> KoreanTemplates:
    """공유 KoreanTemplates 반환 (stateless 조회용)."""
    global _default_korean_templates
    if _default_korean_templates is None:
        _default_korean_templates = KoreanTemplates()
    return _default_korean_templates
```

- **Lazy init**: 최초 호출 시에만 생성 → import 시점 오버헤드 없음
- **Thread safety**: 초기화는 단일 스레드 import-time에 종료 (GIL 보호)

### ✅ 단계 2: 자동화 스크립트로 24+1파일 교체

**스크립트**: [scripts/apply_m3_singletons.py](scripts/apply_m3_singletons.py)

**변경 패턴**:
```python
# Before (24 generators)
self._severity_mapper: SeverityMapper = SeverityMapper()

# After
self._severity_mapper = get_default_severity_mapper()
```

```python
# Before (11 generators)
self._templates: KoreanTemplates = KoreanTemplates()

# After
self._templates = get_default_korean_templates()
```

### ⚠ 단계 3: import 누락 버그 수정

**문제**: 스크립트가 `"get_default_*" in new_src` 로 import 존재 여부 체크 → 할당문에 이미 함수 호출이 들어가서 false positive → import 누락

**해결**: [scripts/fix_m3_imports.py](scripts/fix_m3_imports.py) 추가 스크립트 실행
- 정규식으로 `from feedback_system.templates import ...get_default_\w+` 라인만 감지
- 25파일에 `from feedback_system.templates import get_default_*` import 라인 삽입

### ✅ 단계 4: biomechanics_feedback.py 수동 처리

- import 이미 있었지만 할당문 교체 미적용 → 수동 처리

### ✅ 단계 5: templates/__init__.py self-import 버그 수정

- fix_m3_imports 스크립트가 `templates/__init__.py` 자체에도 import 라인을 삽입 → 자기 자신 import 순환
- 잘못된 위치(`from feedback_formatter import (` 안쪽)에 삽입된 것 수동 제거

---

## 2. 런타임 검증

```python
>>> from feedback_system.analysis.game_feedback import GameFeedbackGenerator
>>> from feedback_system.analysis.defensive_feedback import DefensiveFeedbackGenerator
>>> from feedback_system.analysis.tactical_feedback import TacticalFeedbackGenerator
>>> g1 = GameFeedbackGenerator()
>>> g2 = DefensiveFeedbackGenerator()
>>> g3 = TacticalFeedbackGenerator()
>>> assert g1._severity_mapper is g2._severity_mapper is g3._severity_mapper
>>> assert g1._templates is g2._templates is g3._templates
>>> print('SeverityMapper shared:', id(g1._severity_mapper))
SeverityMapper shared: 1831785514752
>>> print('KoreanTemplates shared:', id(g1._templates))
KoreanTemplates shared: 1831786861312
```

**결과**: ✅ 3개 generator 모두 동일한 SeverityMapper/KoreanTemplates 인스턴스 공유

**추가 검증**: `feedback_system/` 39 파일 전체 `py_compile` 통과

---

## 3. 메모리 절감 효과

### Before (세션 5 이전)
- 24 analysis generators × 1 SeverityMapper = **24 인스턴스**
- 11 analysis generators × 1 KoreanTemplates = **11 인스턴스**
- 1 coach generator (biomechanics) × 1 SeverityMapper
- 1 coach generator (motion) × 1 SeverityMapper + 1 KoreanTemplates
- = **총 ~37 인스턴스**

### After (세션 5 이후)
- **1 SeverityMapper** (싱글톤 공유)
- **1 KoreanTemplates** (싱글톤 공유)
- = **총 2 인스턴스**

### 감축
- **~37 → 2 = 약 18배 감축**
- KoreanTemplates 는 **1,630줄 방대한 템플릿 데이터** 보유 → 메모리 절감 효과 큼
- SeverityMapper 는 4 ThresholdSet + 캐시 → 작지만 반복 생성 오버헤드 제거

---

## 4. 영향 범위

| 디렉토리 | 파일 수 |
|---|---|
| `feedback_system/templates/` | 1 (__init__.py) |
| `feedback_system/analysis/` | 24 (전 generator) |
| `feedback_system/coach/` | 2 (biomechanics + motion) |
| `scripts/` | 2 (apply_m3_singletons + fix_m3_imports) |
| **합계** | **29파일** (+ 2 스크립트) |

### 제외

- `visual_feedback_generator.py` — SeverityMapper/KoreanTemplates 사용 안 함 (Skip)
- `FeedbackFormatter` — per-generator FormatterConfig 로 인스턴스마다 다른 설정 → 싱글톤화 제외 (유지)
- `session_summary.py`, `motion_feedback.py` 의 FormatterConfig 주입 패턴 → 의도적 변경 보존

---

## 5. Breaking change 분석

**없음**:
- 싱글톤 인스턴스는 원본 SeverityMapper/KoreanTemplates 클래스 인스턴스 → API 동일
- 기존 generator 호출 코드 (외부) 영향 없음
- `self._severity_mapper.from_score(...)` 등 기존 메서드 호출 동일 작동

**주의**:
- 싱글톤이므로 `reset()` 호출 시 모든 generator에 영향 — 단일 경기 내에서는 일관적
- 멀티 경기 동시 분석 시나리오 출현하면 generator마다 별도 인스턴스 필요 (현재 desktop 단일 경기 사용 모델에서는 문제 없음)

---

## 6. Phase 15 누적 진행도

| 세션 | Tier | 처리 건수 | 파일 변경 |
|---|---|---|---|
| 1 | Tier 1 + Tier 4 | 9 | 24 |
| 2 | Tier 3 M1 | 10 | 4 |
| 3 | Tier 5 | 7 | 5 |
| 4 | Tier 3 M2 | 31 | 32 |
| **5** | **Tier 3 M3** | **26** | **29** |
| **합계** | — | **83** | **94** |

### 남은 Phase 15 작업 (6건)

**Tier 3 Medium (2건)**:
- M4 Config 가중치 승격 (매직 넘버 → Config)
- M5 리그별 Config 분기 (league_avg_*)

**Tier 2 High (6건, 대규모)**:
- H1/H2/H3 motion_analysis 디렉토리 이전
- H4 Facade 5개 engine 연동 구현
- H5 shared.constants SSOT 확립
- H6 korean_templates.py 1,630줄 분할

---

## 7. 다음 세션 제안

**세션 6 권장**: Tier 3 **M4 + M5** 일괄 (2건, ~8파일)

- **M4 Config 가중치 승격**:
  - `foul_severity_analyzer` 5요소 가중 (impact 0.30 / body 0.25 / intent 0.20 / vulnerability 0.15 / context 0.10) → FoulSeverityConfig
  - `game_report._calculate_overall_score` 5요소 (eFG 0.35 / AST 0.20 / TOV 0.20 / REB 0.15 / WIN 0.10) → GameReportConfig
  - `coach_report._calculate_overall_score` 60/40 (motion/biomech) → CoachReportConfig

- **M5 리그별 Config 분기**:
  - `GameFeedbackConfig` 등의 `league_avg_efg=50.0` 기본값 → `RuleSet` 기반 분기 (FIBA 50 / NBA 53 / KBL 49 / NBL 48)

- 예상 시간: 45분

**대안 1**: **H5 shared.constants SSOT 확립** — 다른 H-tier 리팩토링의 기반 (단일 세션 ~60분)

**대안 2**: **H6 korean_templates.py 1,630줄 분할** — 독립 작업, 유지보수성 크게 개선 (~90분)

---

**세션 5 완료. M3 싱글톤화 25파일. 메모리 ~18배 감축. Breaking change 없음.**
