# 12B. feedback_system/analysis/ 감사 리포트

**감사 범위**: `feedback_system/analysis/` **25파일** (1 `__init__` + 24 generators)
**감사 방식**: 전수 직독 (Read 전용)
**감사 축**: 8종
**감사일**: 2026-04-20

---

## 1. 감사 대상 구성

| 그룹 | 파일 수 | 생성기 |
|---|---|---|
| **기존 8종** | 8 | game / tactical / defensive / individual / spatial / lineup / referee / visual |
| **신규 7종** | 7 | quarter_momentum / clutch / pace_tempo / shot_quality / opponent_tendency / rotation / strategic_recommendation |
| **고급 3종** | 3 | causal / game_context / scouting |
| **잔여 6종** | 6 | free_throw / foul_trouble / drill_prescription / play_by_play / position / finish_repertoire |
| **합계** | **24** + `__init__` | — |

---

## 2. 감사 8축 평가

### 2.1 Import 유효성 ✅ 96/100

- 25파일 전체 `from __future__ import annotations` + SSOT 준수 ✓
- 일관된 의존 패턴: `SeverityMapper + KoreanTemplates + FeedbackFormatter`
- **Safe-Now**: 1건
  - S42 [game_feedback.py:27](feedback_system/analysis/game_feedback.py#L27) `FeedbackCategory as ConstFeedbackCategory` alias — 파일 내 `ConstFeedbackCategory` 참조 없음, `FeedbackCategory` (from `shared.dto.feedback_dto`) 만 사용

### 2.2 기능 유효성 ✅ 95/100

- **24 generators 전체 일관 패턴**: Config 주입 → generate() 메서드 → `list[FeedbackItem]` 반환
- `GameFeedbackGenerator`: 12개 세부 피드백 생성 메서드 (result/shooting/four_factors/rebound/key_players/game_flow/bench/second_chance/pace/defensive/quarter_momentum/assist_distribution)
- `DefensiveFeedbackGenerator`: 15+ 항목 (DRtg/컨테스트/헬프/클로즈아웃/박스아웃/매치업/스틸블락/상대 FG%/페인트/외곽/전환수비/매치업승패/파울규율/종합)
- `TacticalFeedbackGenerator`: 픽앤롤/속공/세트/패스/전환/아이솔레이션/포스트업/스팟업 (10+ 설정 임계)
- `SpatialFeedbackGenerator`: 11개 세부 (코트활용/스페이싱/드라이브/3점/페인트/품질/밀도/벤치마크/일관성/약사이드/코너)
- `CausalFeedbackGenerator`: "왜?" 원인 추론 (슈팅/턴오버/전환/득점 원인 교차 분석)
- `GameContextFeedbackGenerator`: 가비지타임/클러치/리드추격/모멘텀 전환 맥락 인식
- `ScoutingFeedbackGenerator`: 스카우팅 대비 실행도 ("스카우팅 보고서대로 했는가?")

### 2.3 메모리 누수 방지 ✅ 96/100

- 모든 generator `__slots__` 수동 선언 + `RLock` + `_total_generated` ✓
- `_total_generated` 카운터만 증가, 이력 누적 없음 (단발 생성 패턴)
- **관찰**: 모든 generator가 `SeverityMapper` / `KoreanTemplates` / `FeedbackFormatter` 를 각자 `__init__` 에서 새로 생성 — 메모리 낭비 가능성 (Phase 15 검토)

### 2.4 하드코딩 점검 ⚠ 86/100

- **Config 노출 ✓**: 각 generator의 매직 넘버 임계치가 모두 Config 필드로 노출 (`drtg_good=105.0`, `open_look_ratio_elite=0.60` 등)
- **스포츠 분석 계수**: 도메인 지식 기반 (NBA/FIBA 평균값, PPP 기준, 효율 임계)
- **관찰**: [defensive_feedback.py:55-73](feedback_system/analysis/defensive_feedback.py#L55-L73) 15+ 임계치 — Config 승격은 되어있지만 리그별 차이(KBL/NBL) 반영 여지
- **관찰**: 각 generator의 `age_group: str = "adult"` 문자열 — enum 대체 여지 (12A와 동일 이슈)

### 2.5 한줄 검토 ✅ 97/100

- 24 generator 전체 docstring + CLAUDE.md 주석 + 참조 일관
- Korean 한글 피드백 텍스트 품질 최상
- 파일 메타 표준 준수

### 2.6 스레드 안전성 ✅ 97/100

- 25파일 전체 `RLock` + `with self._lock:` + `_total_generated` 보호 ✓
- 각 generator가 독립 상태 유지 — concurrent 호출 안전

### 2.7 예외 처리 ✅ 94/100

- `_safe_format` 패턴 상속 (korean_templates 위임)
- 빈 데이터 체크 방어 (`if not target.player_stats: return items`) 일관
- `if opponent is not None:` 조건부 처리 철저

### 2.8 확장성 ✅ 97/100

- 24 generator 전체 Config DI ✓
- `_severity_to_priority` / `_resolve_teams` 등 내부 헬퍼 재사용 패턴
- **관찰**: 새 generator 추가 시 `analysis/__init__.py` + `report/game_report_generator.py` 2곳 수정 필요 — Service Registry 방식 대체 여지 (Phase 15 확장성 개선 후보)

---

## 3. Safe-Now 이슈 목록 (1건)

### S42. `game_feedback.py` 미사용 alias import

- **파일**: [feedback_system/analysis/game_feedback.py:27](feedback_system/analysis/game_feedback.py#L27)
- **현황**: `FeedbackCategory as ConstFeedbackCategory` alias — 파일 내 전혀 참조 없음
- **조치**: alias 제거 또는 import 자체 제거 (파일 내 `FeedbackCategory` 는 `shared.dto.feedback_dto` 에서 가져옴)

---

## 4. Phase 15 Deferred 이슈 (4건)

### P15-12B-01. generator 내부 인스턴스 중복 생성

- 24 generator 모두 `SeverityMapper()` / `KoreanTemplates()` / `FeedbackFormatter()` 각자 새로 생성
- `GameReportGenerator` 에서 18 generator 인스턴스 생성 시 총 ~54 인스턴스 생성
- **방안**: 싱글톤 또는 공유 인스턴스 DI

### P15-12B-02. `age_group` 문자열 → Enum

- 모든 generator `age_group: str = "adult"` — 12A `apply_age_adjustment` 와 일관된 이슈
- `AgeGroup` enum 도입 (player_constants 에 이미 존재)

### P15-12B-03. Config 임계치 리그별 분기

- NBA/FIBA/KBL/NBL 리그별 평균 차이 반영 필요
- 현재는 FIBA 기준 하드코딩 (`league_avg_efg=50.0`, `league_avg_tov_rate=14.0` 등)

### P15-12B-04. Service Registry 패턴 도입

- 새 generator 추가 시 2곳(`__init__.py` + `game_report_generator.py`) 수정 필요
- `core_foundation/registry/service_registry` 활용한 동적 등록 방식 고려

---

## 5. 12B 종합 점수

| 축 | 점수 |
|---|---|
| Import 유효성 | 96 |
| 기능 유효성 | 95 |
| 메모리 누수 방지 | 96 |
| 하드코딩 점검 | 86 |
| 한줄 검토 | 97 |
| 스레드 안전성 | 97 |
| 예외 처리 | 94 |
| 확장성 | 97 |
| **총점** | **94.8** |

---

## 6. 관찰된 강점

1. **24 generator 일관 패턴** — `__slots__ + RLock + Config DI + SeverityMapper/KoreanTemplates/FeedbackFormatter` 철저 준수
2. **도메인 세분화** — 기존 8 + 신규 7 + 고급 3 + 잔여 6 = **24종 피드백 커버리지**
3. **causal_feedback** — 통계 결과 "왜?" 원인 추론 (슈팅/턴오버/전환/득점)
4. **scouting_feedback** — 스카우팅 대비 실행도 (게임플랜 실행 평가)
5. **game_context_feedback** — 가비지타임/리드추격/모멘텀 맥락 인식
6. **drill_prescription_feedback** — 약점별 훈련 드릴 자동 처방
7. **finish_repertoire_feedback** — 레이업/덩크/플로터/훅샷/풋백 다양성 평가
8. **position_feedback** — 스탯 기반 포지션 추정 + 역할 대비 평가
9. **free_throw_feedback** — 자유투 루틴/연속성/And-One 변환 분석
10. **foul_trouble_feedback** — 파울아웃 위험 + 보너스 상황 추적
11. **Config 임계치 명확** — 매직 넘버 대부분 Config 필드로 노출
12. **한국어 피드백 톤** — 12A `korean_templates.py` 활용으로 일관된 품질

---

## 7. 관찰된 약점

1. **Generator 인스턴스 중복 생성** — SeverityMapper/KoreanTemplates/FeedbackFormatter 각 generator 별 개별 생성
2. **age_group 문자열** — enum 미사용 (공통 이슈)
3. **리그별 임계치 분기 부재** — FIBA 기준 하드코딩

---

## 8. 다음 작업

1. Safe-Now 1건 즉시 처리 여부 확정 (S42)
2. `12_FEEDBACK_SYSTEM_SUMMARY.md` 통합 총평 작성
