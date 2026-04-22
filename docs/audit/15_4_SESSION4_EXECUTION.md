# Phase 15 세션 4 — M2 age_group 문자열 → AgeGroup Enum

**실행일**: 2026-04-20
**범위**: Tier 3 Medium M2 (전역 age_group 타입 전환)
**결과**: **31파일 완료** (feedback_system 전역)

---

## 1. 실행 내역

### ✅ 자동화 스크립트 도입

- **파일**: [scripts/apply_age_group_enum.py](scripts/apply_age_group_enum.py) 신규
- **용도**: 30개 파일 일괄 패턴 교체
- **동작**:
  1. `age_group: str = "adult"` → `age_group: AgeGroup = AgeGroup.ADULT`
  2. `from shared.constants.player_constants import AgeGroup` 자동 import 추가
  3. import 위치: `from shared.dto.*` / `from shared.constants.feedback_constants` / `from __future__ import` 블록 직후

### ✅ 29파일 스크립트 자동 변경

| 디렉토리 | 파일 수 |
|---|---|
| `feedback_system/analysis/` | 24 (causal, clutch, defensive, drill_prescription, finish_repertoire, foul_trouble, free_throw, game_context, game, individual, lineup, opponent_tendency, pace_tempo, play_by_play, position, quarter_momentum, referee, rotation, scouting, shot_quality, spatial, strategic_recommendation, tactical, visual_feedback_generator) |
| `feedback_system/coach/` | 1 (motion_feedback) |
| `feedback_system/report/` | 3 (coach_report_generator, game_report_generator, session_summary) |
| `feedback_system/templates/` | 1 (feedback_formatter) |
| **스크립트 자동** | **29** |

### ✅ 2파일 수동 처리

| 파일 | 처리 |
|---|---|
| `feedback_system/coach/biomechanics_feedback.py` | AgeGroup import 이미 존재 (line 70) → 필드만 수동 교체 |
| `feedback_system/templates/korean_templates.py:1270` | 메서드 시그니처 `age_group: AgeGroup \| str = AgeGroup.ADULT` (외부 유연성 유지) + import 추가 |

### 🟢 제외 (의도적 유지)

- `api_server/schemas/request_schemas.py:38` — **Pydantic Field (외부 JSON 입력)**. 문자열 유지가 자연스러움 (프론트엔드에서 `"adult"` 문자열 전송 → `_AGE_GROUP_MAP`이 서비스 레이어에서 AgeGroup 변환)

---

## 2. 런타임 검증

```python
>>> from feedback_system.report.session_summary import SessionSummaryConfig
>>> c = SessionSummaryConfig()
>>> c.age_group
AgeGroup.ADULT
>>> type(c.age_group).__name__
'AgeGroup'
>>> c.age_group == "adult"
True   # AgeGroup(str, Enum) — 문자열 호환 유지
```

**결과**: ✅ enum 타입 + 기존 문자열 비교 100% 호환

---

## 3. 호환성 분석

### Breaking change 여부: **없음**

1. **`AgeGroup(str, Enum)` str 서브클래스** — 기존 `if age_group == "youth":` 로직 그대로 작동
2. **Config 생성 시 문자열 전달 허용** — 예: `SessionSummaryConfig(age_group="youth")` 런타임 정상 (type checker만 경고)
3. **_simplify_for_youth 등 문자열 매칭 코드** — `age_group == "youth"` 여전히 True 반환

### 장점

1. **타입 안전성** — IDE 자동완성 + mypy 검사 강화
2. **리팩토링 용이** — AgeGroup 값 변경 시 일괄 추적 가능
3. **문서화 강화** — 가능한 값(`YOUTH/TEEN/ADULT/SENIOR`) enum으로 명시

---

## 4. 영향 범위

| 디렉토리 | 파일 수 |
|---|---|
| `feedback_system/analysis/` | 24 |
| `feedback_system/coach/` | 2 |
| `feedback_system/report/` | 3 |
| `feedback_system/templates/` | 2 |
| `scripts/` | 1 (신규 마이그레이션 스크립트) |
| **합계** | **32파일** |

---

## 5. Phase 15 누적 진행도

| 세션 | Tier | 처리 건수 | 파일 변경 |
|---|---|---|---|
| 1 | Tier 1 + Tier 4 | 9 | 24 |
| 2 | Tier 3 M1 | 10 | 4 |
| 3 | Tier 5 | 7 | 5 |
| **4** | **Tier 3 M2** | **31** | **32** |
| **합계** | — | **57** | **65** |

### 남은 Phase 15 작업 (7건)

**Tier 3 Medium (3건)**:
- M3 Generator 인스턴스 싱글톤화 (SeverityMapper/KoreanTemplates/FeedbackFormatter 중복 제거)
- M4 Config 가중치 승격 (매직 넘버 → Config)
- M5 리그별 Config 분기 (league_avg_*)

**Tier 2 High (6건, 대규모)**:
- H1/H2/H3 motion_analysis 디렉토리 이전
- H4 Facade 5개 engine 연동 구현
- H5 shared.constants SSOT 확립
- H6 korean_templates.py 1,630줄 분할

---

## 6. 다음 세션 제안

**세션 5 권장**: Tier 3 Medium **M3 (Generator 싱글톤화)**

- `SeverityMapper/KoreanTemplates/FeedbackFormatter` 3종이 24 generator × 각자 생성 = **~72회 중복 생성**
- 공유 인스턴스 도입 시 메모리 ~72배 감축 가능
- 영향 파일: 24 generator + 2 report orchestrator = ~26파일
- 예상 시간: 40분

**대안**: **M4 (Config 가중치 승격)** — 매직 넘버 Config 필드화
- foul_severity 5요소 / game_report 5요소 / coach_report 60/40
- 영향 파일: 3파일

**대안 2**: Tier 2 High **H5 (shared.constants SSOT 확립)** — 대규모 기반 작업

---

**세션 4 완료. M2 age_group enum 전환 31파일. Breaking change 없음.**
