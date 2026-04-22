# 11A. ai_referee/ {root + rules + data_extraction} 감사 리포트

**감사 범위**: `ai_referee/__init__.py` + `rules/` (7) + `data_extraction/` (7) = **15파일**
**감사 방식**: 전수 직독 (Read 전용)
**감사 축**: 8종 (Import/Functional/MemoryLeak/Hardcoding/Review/ThreadSafety/Exception/Extensibility)
**감사일**: 2026-04-20

---

## 1. 감사 대상 구성

| 서브디렉토리 | 파일 | 역할 |
|---|---|---|
| root | `__init__.py` | 5 Phase (A~E) 전체 심볼 공개 |
| `rules/` (7) | `__init__`, `base_rule`, `fiba_rules`, `nba_rules`, `kbl_rules`, `nbl_rules`, `rule_loader` | 규칙 ABC + 4개 리그 + YAML 로더 |
| `data_extraction/` (7) | `__init__`, `decision_record`, `correction_pair`, `edge_case`, `calibration_data`, `foul_contact`, `violation_sequence` _extractor | 자가학습용 6종 데이터셋 추출 |

---

## 2. 감사 8축 평가

### 2.1 Import 유효성 ⚠ 93/100

- 15파일 전체 `from __future__ import annotations` 일관 ✓
- `shared.constants.*`, `shared.dto.*` SSOT 경유 ✓
- **Safe-Now**: 3파일에서 `dataclass, field` 중 `field` 미사용
  - [calibration_data_extractor.py:27](ai_referee/data_extraction/calibration_data_extractor.py#L27)
  - [foul_contact_extractor.py:26](ai_referee/data_extraction/foul_contact_extractor.py#L26)
  - [violation_sequence_extractor.py:26](ai_referee/data_extraction/violation_sequence_extractor.py#L26)

### 2.2 기능 유효성 ✅ 96/100

- `BaseRule(ABC)` → `ViolationRule` / `FoulRule` → 리그별 규칙 계층 완벽
- FIBA → NBA/KBL/NBL 상속 구조 일관 (모두 `FIBARules` 상속)
- 자가학습 6종 추출기 모두 `create_extraction → add_* → build_result` 표준 패턴
- **관찰**: [edge_case_extractor.py:218-222](ai_referee/data_extraction/edge_case_extractor.py#L218-L222) `if conf < ... or conf > ...: pass` 죽은 코드 블록 (주석만 있음, 로직 오해 유발)
- **관찰**: [foul_contact_extractor.py:237](ai_referee/data_extraction/foul_contact_extractor.py#L237) `result.evidence[-1]` 를 severity_grade로 강제 해석 — evidence 형식 의존

### 2.3 메모리 누수 방지 ✅ 94/100

- `_MAX_EXTRACTIONS=200` / `_MAX_RECORDS=50000` 모든 추출기에 일관 적용 ✓
- `create_extraction` 한도 초과 시 `None` 반환 (거부) ✓
- `foul_contact` / `violation_sequence` 의 `frame_history` 슬라이싱 정상 ✓
- **Safe-Now**: `base_rule.py` 미사용 상수 2개
  - [base_rule.py:52](ai_referee/rules/base_rule.py#L52) `_MAX_EVALUATION_HISTORY: Final[int] = 2000` — 실제 history list 자체 없음
  - [base_rule.py:54](ai_referee/rules/base_rule.py#L54) `_MAX_RULE_PARAMETERS: Final[int] = 200` — 미사용

### 2.4 하드코딩 점검 ⚠ 89/100

- FIBA/NBA/KBL/NBL 규칙은 dataclass 필드로 명시 + `from_yaml` 노출 — SSOT 준수 ✓
- **관찰**: [nba_rules.py:531](ai_referee/rules/nba_rules.py#L531) `get_defensive_three_second_penalty` 리턴값 `(1, True)` 매직 넘버 — `FoulRules`나 `LeagueSpecificRules` 에 노출 권장
- **관찰**: [calibration_data_extractor.py:53-54](ai_referee/data_extraction/calibration_data_extractor.py#L53-L54) `_CLUTCH_QUARTER=4`, `_CLUTCH_CLOCK_SEC=120.0` — 리그별 분기 없음 (FIBA 4Q vs NBA 12min 기준 상이)

### 2.5 한줄 검토 (1-line review) ✅ 97/100

- docstring 3단 메타 (`참조:`/`의존성:`/`소비자:`) 일관
- `Processing Cadence` 대신 `작성자`/`최종 수정`/`버전` 표준 준수
- 자가학습 추출기 모두 `사용 예시::` docstring 포함 ✓

### 2.6 스레드 안전성 ⚠ 92/100

- 모든 추출기 `threading.RLock` + `with self._lock:` + `__slots__` 수동 선언 ✓
- `base_rule.BaseRule` 의 통계 락 보호 ✓
- **Safe-Now (중요)**: `FIBARules` / `NBARules` / `KBLRules` / `NBLRules` 4파일에서 **`self._lock = RLock()` 초기화만 있고 실제 사용처 없음**
  - [fiba_rules.py:339](ai_referee/rules/fiba_rules.py#L339)
  - [nba_rules.py:367](ai_referee/rules/nba_rules.py#L367)
  - [kbl_rules.py:217](ai_referee/rules/kbl_rules.py#L217)
  - [nbl_rules.py:201](ai_referee/rules/nbl_rules.py#L201)
  - 모든 속성이 `__init__` 에서만 세팅되고 읽기 전용 — 리로드는 `rule_loader._rules_cache` 레벨에서 처리
- **관찰**: [rule_loader.py:262-275](ai_referee/rules/rule_loader.py#L262-L275) lock 외부 I/O 후 lock 내부 저장 → 두 스레드 동시 미스 시 중복 로딩 (무해하나 비효율)

### 2.7 예외 처리 ✅ 95/100

- `rule_loader` 의 `ConfigurationLoadException` 체이닝 (`from exc`) 일관 ✓
- `RuleParameters.get_*` 방어적 예외 처리 (TypeError/ValueError catch) ✓
- `create_extraction` 한도 초과 시 `logger.warning + return None` — silent 없음 ✓
- **관찰**: [correction_pair_extractor.py:366](ai_referee/data_extraction/correction_pair_extractor.py#L366) `if original_call == "no_call": return FALSE_NEGATIVE` — 상위 `register_decision` 이 `violated=True` 만 허용하므로 주석처럼 "드묾" (데드 로직이나 방어적 설계)

### 2.8 확장성 ✅ 97/100

- `BaseRule.update_parameters` — YAML 리로드 시 런타임 파라미터 갱신 가능 ✓
- `rule_loader.reload_rules` — 리그 단위 리로드 지원 ✓
- `RuleLoader.load_all_rules` — 다중 리그 일괄 로딩 ✓
- 추출기 모두 `Config` 주입 가능 (DI) — 테스트 용이 ✓
- **관찰**: `from_yaml` 미제공 — `DecisionRecordExtractorConfig` 등 6개 (P18 대상)

---

## 3. Safe-Now 이슈 목록 (6건)

### S14. `base_rule.py` 미사용 상수 `_MAX_EVALUATION_HISTORY`

- **파일**: [ai_referee/rules/base_rule.py:52](ai_referee/rules/base_rule.py#L52)
- **현황**: `_MAX_EVALUATION_HISTORY: Final[int] = 2000` 정의되어 있으나 history list 자체가 없음 (평가 결과는 `_last_result` 단일 슬롯)
- **조치**: 상수 제거

### S15. `base_rule.py` 미사용 상수 `_MAX_RULE_PARAMETERS`

- **파일**: [ai_referee/rules/base_rule.py:54](ai_referee/rules/base_rule.py#L54)
- **현황**: `_MAX_RULE_PARAMETERS: Final[int] = 200` 정의되어 있으나 `RuleParameters.parameters` 크기 제한에 사용되지 않음
- **조치**: 상수 제거

### S16. 리그 규칙 클래스 4종 미사용 `self._lock` (중요)

- **파일**:
  - [fiba_rules.py:339](ai_referee/rules/fiba_rules.py#L339)
  - [nba_rules.py:367](ai_referee/rules/nba_rules.py#L367)
  - [kbl_rules.py:217](ai_referee/rules/kbl_rules.py#L217)
  - [nbl_rules.py:201](ai_referee/rules/nbl_rules.py#L201)
- **현황**: 4개 클래스 모두 `self._lock = RLock()` 로 초기화하지만 실제 `with self._lock:` 사용처 없음. 모든 속성이 `__init__` 에서만 세팅되고 이후 읽기 전용
- **조치**: 4개 파일 모두 lock 제거 (리로드는 `rule_loader._rules_cache` 교체 방식으로 처리됨)

### S18. `calibration_data_extractor.py` 미사용 `field` import

- **파일**: [ai_referee/data_extraction/calibration_data_extractor.py:27](ai_referee/data_extraction/calibration_data_extractor.py#L27)
- **조치**: `from dataclasses import dataclass, field` → `from dataclasses import dataclass`

### S19. `foul_contact_extractor.py` 미사용 `field` import

- **파일**: [ai_referee/data_extraction/foul_contact_extractor.py:26](ai_referee/data_extraction/foul_contact_extractor.py#L26)
- **조치**: 동일

### S20. `violation_sequence_extractor.py` 미사용 `field` import

- **파일**: [ai_referee/data_extraction/violation_sequence_extractor.py:26](ai_referee/data_extraction/violation_sequence_extractor.py#L26)
- **조치**: 동일

---

## 4. Phase 15 Deferred 이슈 (4건)

### P15-11A-01. NBA 수비 3초 페널티 매직 값

- [nba_rules.py:531](ai_referee/rules/nba_rules.py#L531) `(1, True)` → `LeagueSpecificRules.defensive_three_second_ft`, `defensive_three_second_possession` 필드 승격

### P15-11A-02. 클러치 기준 리그별 분기 부재

- `_CLUTCH_CLOCK_SEC: Final[float] = 120.0` 하드코딩 → 리그별 `clutch_definition` 도입 (NBA 2분, FIBA 4분?, KBL 1분?)

### P15-11A-03. `from_yaml` 미제공 추출기 Config

- 6개 `*ExtractorConfig` 모두 `from_yaml` 미제공 — P18 (game_analysis Phase 15 연장)

### P15-11A-04. `edge_case_extractor` 죽은 코드 블록

- [edge_case_extractor.py:218-222](ai_referee/data_extraction/edge_case_extractor.py#L218-L222) `if conf ... : pass` — 주석을 코드 상단으로 이동 + `pass` 블록 제거 (의도 명확화)

---

## 5. 11A 종합 점수

| 축 | 점수 |
|---|---|
| Import 유효성 | 93 |
| 기능 유효성 | 96 |
| 메모리 누수 방지 | 94 |
| 하드코딩 점검 | 89 |
| 한줄 검토 | 97 |
| 스레드 안전성 | 92 |
| 예외 처리 | 95 |
| 확장성 | 97 |
| **총점** | **94.1** |

---

## 6. 관찰된 강점

1. **ABC 계층 구조** — `BaseRule → ViolationRule/FoulRule` 명확, 리그별 상속 (FIBA→NBA/KBL/NBL) 일관
2. **YAML 로더 설계** — `base_rules` 재귀 상속 + `_deep_merge` + 캐시 관리 전문가급
3. **자가학습 추출기 철학** — 콜 전수/노콜 샘플링, 교정 쌍 자동 분류, 능동 학습 우선순위, 캘리브레이션 빈 분류 — Active Learning 모범 구현
4. **Extension points** — `update_parameters` / `reload_rules` / DI Config — 운영 중 교체 가능

---

## 7. 다음 작업

1. Safe-Now 6건 즉시 처리 여부 확정 (S14/S15/S16/S18/S19/S20)
2. Phase 11B `fouls/` 12파일 착수
