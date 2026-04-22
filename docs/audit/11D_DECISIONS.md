# 11D. ai_referee/decisions/ 감사 리포트

**감사 범위**: `ai_referee/decisions/` 7파일 (1 `__init__` + 6 엔진)
**감사 방식**: 전수 직독 (Read 전용)
**감사 축**: 8종
**감사일**: 2026-04-20

---

## 1. 감사 대상 구성

| 파일 | 역할 |
|---|---|
| `decision_engine.py` | **오케스트레이터** — 9단계 파이프라인 (수집→필터→중복제거→정렬→보정→검증→일관성→설명→리플레이) |
| `confidence_scorer.py` | 신뢰도 보정 (5요소: 근거/클러치/득점/퇴장/카테고리) |
| `multi_angle_validator.py` | 멀티앵글 교차 검증 (뷰 품질 가중, 근거 병합) |
| `consistency_tracker.py` | 일관성 추적 (팀 편향, 콜 레벨 tight/normal/loose) |
| `decision_explainer.py` | 한글 판정 근거 설명 생성 |
| `replay_manager.py` | 리플레이 큐 + 코치 챌린지 + 환불 시스템 |
| `__init__.py` | export 정상 |

---

## 2. 감사 8축 평가

### 2.1 Import 유효성 ⚠ 93/100

- 7파일 전체 SSOT(referee_decision_constants) 준수 ✓
- `@dataclass(slots=True) + field + UUID` 일관
- **Safe-Now**: [replay_manager.py:35](ai_referee/decisions/replay_manager.py#L35) `REPLAY_MAX_REVIEW_TIME_SEC` import 되지만 파일 내 미사용

### 2.2 기능 유효성 ✅ 96/100

- `DecisionEngine` 9단계 파이프라인 구조 명확
- `process_results` 내에서 중복 제거 → 정렬 → 파이프라인 → 기록 흐름 일관
- 멀티뷰 검증 신뢰도 반영: `final_conf = (final_conf + validation.final_confidence) / 2.0` (단순 평균)
- 일관성 위반 시 `final_conf *= 0.95` 감점
- `consistency_tracker` 의 `tight/normal/loose` 콜 레벨 분류 — 심판 일관성 검증 개념 정교
- **관찰**: [replay_manager.py:152](ai_referee/decisions/replay_manager.py#L152) `should_replay` 의 경계 신뢰도 `0.50 <= conf < 0.85` vs [replay_manager.py:165](ai_referee/decisions/replay_manager.py#L165) `classify_priority` 의 NORMAL `0.50 <= conf < 0.70` — 0.70~0.85 구간은 replay=True이나 priority=LOW 배정 (설계 의도일 수도, 불일치로 읽힐 수도)

### 2.3 메모리 누수 방지 ✅ 96/100

- 모든 엔진 `_MAX_*_HISTORY` + trim 패턴 일관 ✓
  - decision_engine 500, confidence_scorer 500, multi_angle 200, consistency 1000, explainer 200, replay 50
- `record_decision` / `add_replay` / `_record` 모두 락 보호 ✓
- replay_manager: `_MAX_REPLAY_QUEUE` 초과 시 우선순위 낮은 것부터 제거 (LRU 아닌 priority 기반) ✓

### 2.4 하드코딩 점검 ⚠ 86/100

- **관찰**: confidence_scorer 5종 보정 계수 (_EVIDENCE_WEIGHT_PER_ITEM=0.02, _MAX_EVIDENCE_BOOST=0.10, _CLUTCH_PENALTY=0.05, _SCORING_PLAY_PENALTY=0.03, _EJECTION_PENALTY=0.05) + `foul_adj = -0.02` 매직. 모듈 상수로 정의되지만 Config 미노출
- **관찰**: [confidence_scorer.py:194](ai_referee/decisions/confidence_scorer.py#L194) 클러치 정의 `quarter>=4, clock<=300.0, score_diff<=5` — 리그별 분기 부재 (11A~11C 연장)
- **관찰**: [consistency_tracker.py:281](ai_referee/decisions/consistency_tracker.py#L281) `max_calls / total > 0.70` (편향 임계), [consistency_tracker.py:300-303](ai_referee/decisions/consistency_tracker.py#L300-L303) `call_rate >= 0.60 tight / <= 0.25 loose` — 매직 넘버
- **관찰**: [replay_manager.py:44](ai_referee/decisions/replay_manager.py#L44) `_REPLAY_FRAME_PADDING: Final[int] = 90` (주석 `30fps × 3초`) — fps 가정 반복 (S21 계통)
- **관찰**: decision_engine 멀티뷰 단순 평균, 일관성 감점 0.95 등 inline 상수

### 2.5 한줄 검토 ✅ 97/100

- docstring 파이프라인 흐름 명시 + 사용 예시 전부 포함 ✓
- 메타데이터 표준 준수

### 2.6 스레드 안전성 ✅ 97/100

- 7파일 전체 `RLock` + `with self._lock:` 일관 ✓
- `_history` / `_queue` / `_team_calls` 등 모든 공유 상태 락 보호 ✓
- `list(...)` 방어적 복사 일관 ✓

### 2.7 예외 처리 ✅ 95/100

- SSOT 상수 (`CHALLENGE_MIN_REMAINING_SEC`, `MULTI_ANGLE_*`, `CONSISTENCY_*`) 활용으로 매직 회피 ✓
- `request_challenge` 의 챌린지 잔여/시간 체크 + 로그 명확 ✓
- **관찰**: [consistency_tracker.py:270-271](ai_referee/decisions/consistency_tracker.py#L270-L271) `max(call_counts, key=call_counts.get)  # type: ignore[arg-type]` — 타입 무시 주석. `key=lambda t: call_counts[t]` 로 개선 여지

### 2.8 확장성 ✅ 96/100

- `DecisionEngine` 의 6개 서브컴포넌트 전부 DI 가능 ✓
- `MultiAngleValidator` `min_cameras`, `agreement_threshold` Config 노출 ✓
- `ReplayManager.initialize_challenges` — 경기 시작 시 팀 챌린지 초기화 메서드 명확 ✓
- **관찰**: [consistency_tracker.py:104-105](ai_referee/decisions/consistency_tracker.py#L104-L105) `_type_calls`, `_type_total` 기록되지만 외부 조회 메서드 없음 — CallType별 통계 활용 확장 여지

---

## 3. Safe-Now 이슈 목록 (2건)

### S30. `replay_manager.py` 미사용 `REPLAY_MAX_REVIEW_TIME_SEC` import

- **파일**: [ai_referee/decisions/replay_manager.py:35](ai_referee/decisions/replay_manager.py#L35)
- **현황**: `from shared.constants.referee_decision_constants import REPLAY_MAX_REVIEW_TIME_SEC` — 파일 내부 미사용 (리뷰 시간 제한 docstring 언급하지만 코드 미구현)
- **조치**: import 제거 (또는 `resolve_replay` 에서 시간 초과 체크로 활용 구현)

### S31. `consistency_tracker.py` 타입 무시 주석

- **파일**: [ai_referee/decisions/consistency_tracker.py:270-271](ai_referee/decisions/consistency_tracker.py#L270-L271)
- **현황**: `max(call_counts, key=call_counts.get)  # type: ignore[arg-type]`
- **조치**: `max(call_counts, key=lambda t: call_counts[t])` 로 변경 → 타입 안전

---

## 4. Phase 15 Deferred 이슈 (6건)

### P15-11D-01. `confidence_scorer` 보정 계수 Config 승격

- 5종 보정 상수 + `foul_adj=-0.02` → YAML 경로 노출 필요

### P15-11D-02. 클러치 정의 리그별 분기 (11A~11C 연장)

- `ConfidenceScorer._is_clutch_situation` 하드코딩 → 통합 `LeagueSpecificRules.clutch_definition` 도입

### P15-11D-03. `consistency_tracker` 편향/콜레벨 임계

- 0.70 편향 임계, 0.60/0.25 tight/loose 경계

### P15-11D-04. `replay_manager` priority/replay 신뢰도 경계

- `should_replay` 0.50~0.85 vs `classify_priority` 0.50~0.70 불일치 검토 + Config 노출

### P15-11D-05. `replay_manager._REPLAY_FRAME_PADDING` fps 가정

- `90 = 30fps × 3초` — 11B/11C의 fps 이슈와 통합 해결

### P15-11D-06. `consistency_tracker._type_calls`/`_type_total` 조회 메서드

- `get_type_call_rates()` 추가하여 CallType별 통계 외부 노출

---

## 5. 11D 종합 점수

| 축 | 점수 |
|---|---|
| Import 유효성 | 93 |
| 기능 유효성 | 96 |
| 메모리 누수 방지 | 96 |
| 하드코딩 점검 | 86 |
| 한줄 검토 | 97 |
| 스레드 안전성 | 97 |
| 예외 처리 | 95 |
| 확장성 | 96 |
| **총점** | **94.5** |

---

## 6. 관찰된 강점

1. **9단계 파이프라인 설계** — `DecisionEngine.process_results`가 수집→필터→중복→정렬→보정→검증→일관성→설명→리플레이를 명확히 오케스트레이션
2. **일관성 추적 개념** — `ConsistencyTracker` 가 팀 편향 + 콜 레벨 (tight/normal/loose) 을 자동 감지하는 심판 보조 기능 우수
3. **한글 설명 생성** — `DecisionExplainer` 의 `_PENALTY_KO / _CATEGORY_KO / _CONFIDENCE_LEVEL_KO` 한글 테이블 + `full_text` 조합 완성도
4. **리플레이 + 챌린지 환불** — `ReplayManager.resolve_replay` 가 챌린지 번복 시 자동 환불 (CHALLENGE_SUCCESS_REFUND)
5. **뷰 품질 가중** — `MultiAngleValidator` 의 `view_quality` 기반 가중 평균 + 근거 병합 (중복 제거)
6. **우선순위 기반 큐 관리** — `ReplayManager._MAX_REPLAY_QUEUE` 초과 시 낮은 priority 제거 (LRU 아님)

---

## 7. 관찰된 약점

1. **보정 계수 외부 노출 부재** — confidence_scorer/consistency_tracker 매직 넘버 다수
2. **클러치 정의 하드코딩** — Phase 11 전체에서 반복되는 미통합 이슈
3. **`REPLAY_MAX_REVIEW_TIME_SEC`** 의도와 구현 괴리 (import만 있음)

---

## 8. 다음 작업

1. Safe-Now 2건 즉시 처리 여부 확정 (S30/S31)
2. `11_AI_REFEREE_SUMMARY.md` 통합 총평 작성 (47파일 종합)
