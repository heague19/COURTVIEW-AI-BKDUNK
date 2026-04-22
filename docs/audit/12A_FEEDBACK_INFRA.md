# 12A. feedback_system/ {root + templates + coach + report} 감사 리포트

**감사 범위**: root (1) + `templates/` (4) + `coach/` (3) + `report/` (6) = **14파일**
**감사 방식**: 전수 직독 (Read 전용)
**감사 축**: 8종
**감사일**: 2026-04-20

---

## 1. 감사 대상 구성

| 디렉토리 | 파일 | 역할 |
|---|---|---|
| root | `__init__.py` | Layer 7 전역 export (~60 심볼) |
| `templates/` (4) | `__init__`, `severity_mapper`, `feedback_formatter`, `korean_templates` | 심각도 매핑 / 포맷팅 / 한국어 템플릿 엔진 |
| `coach/` (3) | `__init__`, `motion_feedback`, `biomechanics_feedback` | 코치 역할 피드백 (폼 + 생체역학) |
| `report/` (6) | `__init__`, `coach_report_generator`, `game_report_generator`, `session_summary`, `progress_tracker`, `trend_analyzer` | 리포트 오케스트레이션 + 진행 추적 + 추세 |

---

## 2. 감사 8축 평가

### 2.1 Import 유효성 ❌ 90/100 (**최대 약점**)

- 14파일 전체 `from __future__ import annotations` + SSOT 준수 ✓
- `__slots__` 수동 선언 + `@dataclass(slots=True)` 혼용 일관
- **Safe-Now (다수)**: 미사용 import 7건
  - S32 [severity_mapper.py:36](feedback_system/templates/severity_mapper.py#L36) `validate_probability` 미사용
  - S33 [feedback_formatter.py:21](feedback_system/templates/feedback_formatter.py#L21) `field` 미사용
  - S34 [feedback_formatter.py:41](feedback_system/templates/feedback_formatter.py#L41) `cosine_similarity` 미사용 (파일 내 `_deduplicate` 가 문자열 키 비교만 사용)
  - S38 [session_summary.py:23](feedback_system/report/session_summary.py#L23) `FEEDBACK_MIN_DETAIL_POINTS` 미사용
  - S39 [trend_analyzer.py:19](feedback_system/report/trend_analyzer.py#L19) `field` 미사용
  - S40 [trend_analyzer.py:20](feedback_system/report/trend_analyzer.py#L20) `timezone` 미사용
  - S41 [trend_analyzer.py:22](feedback_system/report/trend_analyzer.py#L22) `UUID` 미사용

### 2.2 기능 유효성 ✅ 95/100

- **SeverityMapper**: score/percentile/ratio/ratio_inverse 4가지 입력 지원, 연령대 조정(`apply_age_adjustment`), 5단계 FeedbackSeverity 매핑
- **KoreanTemplates**: 슈팅 4×10=40 + 드리블 4×10=40 + 비교 4 + 패턴 5종 + 편차 6종 + 훈련 2종 — **1,630줄 방대한 템플릿 체계** 완성
- **DeviationExpression**: 코치 말투 tone(casual/neutral/serious/urgent) + 이모지 힌트 — UI/UX 정교
- **TemplateVariationEngine**: 해시 기반 결정적 변형 (테스트 안정성 확보)
- **MotionFeedbackGenerator**: 폼 평가 + 따라하기 비교 + 훈련 추천 3기능
- **BiomechanicsFeedbackGenerator**: 8카테고리 (관절운동학/각도/균형/에너지/착지/인체측정/궤적/동작체인)
- **CoachReportGenerator**: motion + biomechanics 통합, 60/40 가중 평균 점수
- **GameReportGenerator**: **18개 analysis 생성기 오케스트레이션** — Phase 12B 내용 호출

### 2.3 메모리 누수 방지 ✅ 96/100

- 모든 generator `RLock` + `_total_*` 카운터 락 보호 ✓
- history/queue 트림 없이 누적만 — 하지만 `FeedbackSummary`/`ProgressReport` 는 세션 단위 단발 생성 후 소비이므로 누수 없음

### 2.4 하드코딩 점검 ⚠ 87/100

- **관찰**: [severity_mapper.py:480](feedback_system/templates/severity_mapper.py#L480) `cfg = self._config` 정의되지만 사용 안 됨 (S35 — 죽은 로컬 변수)
- **관찰**: [game_report_generator.py:518-524](feedback_system/report/game_report_generator.py#L518-L524) 5요소 가중 (eFG 0.35 / AST 0.20 / TOV 0.20 / REB 0.15 / WIN 0.10) — 농구 분석 계수, 주관적 조정 여지
- **관찰**: [coach_report_generator.py:229-233](feedback_system/report/coach_report_generator.py#L229-L233) 60/40 가중 (motion 0.60, biomech 0.40) 매직 넘버
- **관찰**: [biomechanics_feedback.py:391](feedback_system/coach/biomechanics_feedback.py#L391) `accel_safe = self._config.joint_speed_warning_cm_s * 5` 간이 기준 주석에 명시
- **관찰**: `apply_age_adjustment` 의 `tolerance_multiplier >= 1.3` 매직 경계

### 2.5 한줄 검토 ✅ 97/100

- 14파일 전체 docstring + 참조 + CLAUDE.md 주석 일관
- Korean 한글 코칭 톤 완성도 최상급 (`get_coach_ending`, `DeviationExpression`, `_YOUTH_TERM_SIMPLIFICATIONS`)

### 2.6 스레드 안전성 ✅ 96/100

- 14파일 전체 `RLock` + `with self._lock:` 보호 ✓
- `_total_*` 카운터 증가만 보호 (이력 누적 없음)

### 2.7 예외 처리 ✅ 93/100

- `_safe_format` 의 `try/except (KeyError, ValueError, IndexError)` 패턴 일관
- `validate_range` / `validate_probability` (미사용) 사용 가능하나 실제로는 `validate_range` 만
- **관찰**: [korean_templates.py:1023](feedback_system/templates/korean_templates.py#L1023) `import hashlib` 함수 내부 local import (S36)
- **관찰**: [korean_templates.py:1543](feedback_system/templates/korean_templates.py#L1543) 동일 패턴 (S37)

### 2.8 확장성 ✅ 97/100

- 모든 generator `Config` DI (기본값 + 주입 가능)
- `CoachReportGenerator` / `GameReportGenerator` 가 서브 generator Config 전파 (`motion_feedback_config`, `game_feedback_config` 등)
- **관찰**: `motion_feedback.py:210-214` 문자열 매칭 `"shoot" in motion_type.lower()` / `"dribbl" in motion_type.lower()` — enum 대체 여지
- **관찰**: `biomechanics_feedback.py:520-526` 동일 패턴 `if context == "shooting"`

---

## 3. Safe-Now 이슈 목록 (10건)

### S32. `severity_mapper.py` 미사용 `validate_probability` import

- **파일**: [feedback_system/templates/severity_mapper.py:36](feedback_system/templates/severity_mapper.py#L36)
- **현황**: `from utils.validation_utils import validate_probability, validate_range` — `validate_probability` 파일 내 미사용 (ratio는 1.0 초과 가능하므로 의도된 미사용)
- **조치**: `from utils.validation_utils import validate_range` 로 축소

### S33. `feedback_formatter.py` 미사용 `field` import

- **파일**: [feedback_system/templates/feedback_formatter.py:21](feedback_system/templates/feedback_formatter.py#L21)
- **조치**: `from dataclasses import dataclass` 로 축소

### S34. `feedback_formatter.py` 미사용 `cosine_similarity` import

- **파일**: [feedback_system/templates/feedback_formatter.py:41](feedback_system/templates/feedback_formatter.py#L41)
- **현황**: `from utils.math_utils import cosine_similarity` — `_deduplicate` 가 문자열 키 비교만 사용 (`f"{category}:{title}"`)
- **조치**: import 제거 (또는 주석: "dedup_similarity_threshold Config는 노출만, cosine_similarity 사용 예정")

### S35. `severity_mapper.py` 미사용 로컬 변수 `cfg`

- **파일**: [feedback_system/templates/severity_mapper.py:480](feedback_system/templates/severity_mapper.py#L480)
- **현황**: `_build_default_thresholds` 에서 `cfg = self._config` 정의 후 사용 안 됨 (다음 줄부터 `self._cache[...]`)
- **조치**: `cfg = self._config` 제거

### S36. `korean_templates.py` hashlib 함수 내부 local import

- **파일**: [feedback_system/templates/korean_templates.py:1023](feedback_system/templates/korean_templates.py#L1023)
- **현황**: `get_coach_ending` 내부 `import hashlib` (PEP 8 위반)
- **조치**: 모듈 상단 import 목록에 `import hashlib` 추가

### S37. `korean_templates.py` hashlib 함수 내부 local import (두번째)

- **파일**: [feedback_system/templates/korean_templates.py:1543](feedback_system/templates/korean_templates.py#L1543)
- **현황**: `TemplateVariationEngine.get_variation` 내부 동일 패턴
- **조치**: S36과 함께 상단 import 로 통합

### S38. `session_summary.py` 미사용 `FEEDBACK_MIN_DETAIL_POINTS` import

- **파일**: [feedback_system/report/session_summary.py:23](feedback_system/report/session_summary.py#L23)
- **조치**: import 제거

### S39. `trend_analyzer.py` 미사용 `field` import

- **파일**: [feedback_system/report/trend_analyzer.py:19](feedback_system/report/trend_analyzer.py#L19)
- **조치**: `from dataclasses import dataclass` 로 축소

### S40. `trend_analyzer.py` 미사용 `timezone` import

- **파일**: [feedback_system/report/trend_analyzer.py:20](feedback_system/report/trend_analyzer.py#L20)
- **현황**: `from datetime import datetime, timezone` — `timezone` 미사용
- **조치**: `from datetime import datetime` 으로 축소

### S41. `trend_analyzer.py` 미사용 `UUID` import

- **파일**: [feedback_system/report/trend_analyzer.py:22](feedback_system/report/trend_analyzer.py#L22)
- **현황**: `from uuid import UUID` — 파일 내 `UUID(...)` 호출 없음, 타입 힌트로도 등장 안 함
- **조치**: import 제거

---

## 4. Phase 15 Deferred 이슈 (5건)

### P15-12A-01. `motion_feedback` 문자열 매칭 → Enum

- [motion_feedback.py:210-214](feedback_system/coach/motion_feedback.py#L210-L214) `"shoot" in motion_type.lower()` / `"dribbl" in motion_type.lower()`
- [biomechanics_feedback.py:520-526](feedback_system/coach/biomechanics_feedback.py#L520-L526) `if context == "shooting":` 반복
- **방안**: `MotionContext` enum 도입

### P15-12A-02. 종합 점수 가중치 Config 승격

- `game_report._calculate_overall_score` 5요소 가중 (eFG/AST/TOV/REB/WIN)
- `coach_report._calculate_overall_score` 60/40 (motion/biomech)
- → `OverallScoreConfig` 추가

### P15-12A-03. 심각도 완화 임계 매직 넘버

- `severity_mapper.apply_age_adjustment` 의 `tolerance_multiplier >= 1.3`
- → `SeverityMapperConfig.age_softening_threshold` 필드 추가

### P15-12A-04. `biomechanics_feedback` 매직 넘버

- `accel_safe = joint_speed_warning_cm_s * 5` 간이 기준 — 과학적 근거 있는 상수화 필요

### P15-12A-05. `korean_templates.py` 1,630줄 거대 파일 분할

- 슈팅 템플릿 / 드리블 템플릿 / 편차 표현 / 코치 문미 / 변형 엔진 → 5~6개 서브모듈 분할 권장 (유지보수성)

---

## 5. 12A 종합 점수

| 축 | 점수 |
|---|---|
| Import 유효성 | 90 |
| 기능 유효성 | 95 |
| 메모리 누수 방지 | 96 |
| 하드코딩 점검 | 87 |
| 한줄 검토 | 97 |
| 스레드 안전성 | 96 |
| 예외 처리 | 93 |
| 확장성 | 97 |
| **총점** | **93.9** |

---

## 6. 관찰된 강점

1. **한국어 코칭 톤 완성도** — 1,630줄 `korean_templates.py` + DeviationExpression + 유소년용 용어 간소화
2. **SeverityMapper 4입력 지원** — score/percentile/ratio/ratio_inverse 모두 커버, 연령대 조정
3. **TemplateVariationEngine 해시 기반 결정적 변형** — 같은 seed → 같은 결과 (테스트 안정성)
4. **Formatter 코칭 과학 비율** — 긍정:교정 3:1~5:1 자동 조정 (`_balance_ratio`)
5. **BiomechanicsFeedbackGenerator 8카테고리 커버** — 관절/각도/균형/에너지/착지/인체/궤적/동작체인 완비
6. **GameReportGenerator 18개 오케스트레이션** — analysis/ 전체 생성기 통합
7. **ProgressTracker + TrendAnalyzer** — 세션 간 비교 + 장기 추세 + 성취 판별
8. **DI 철저** — 모든 generator가 Config 주입 가능, 서브 generator Config 전파
9. **__slots__ + RLock + Final 삼위일체** — Phase 10/11 패턴 일관 유지
10. **CLAUDE.md 직접 참조** — docstring에 CLAUDE.md 섹션(5-1, 5-2, #15, #22, #23) 명시

---

## 7. 관찰된 약점

1. **미사용 import 7건** — 10 Safe-Now 중 7건이 import 관련 (가장 큰 품질 이슈)
2. **문자열 매칭 반복** — motion_type/context 판별에 `in` 매칭 사용 (enum 대체 필요)
3. **종합 점수 가중치 매직 넘버** — game/coach 리포트 모두 Config 미노출
4. **`korean_templates.py` 1,630줄** — 단일 파일 너무 큼, 분할 권장

---

## 8. 다음 작업

1. Safe-Now 10건 즉시 처리 여부 확정 (S32~S41)
2. Phase 12B `analysis/` 25파일 착수
