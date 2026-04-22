# 11B. ai_referee/fouls/ 감사 리포트

**감사 범위**: `ai_referee/fouls/` 12파일 (1 `__init__` + 11 detector)
**감사 방식**: 전수 직독 (Read 전용)
**감사 축**: 8종
**감사일**: 2026-04-20

---

## 1. 감사 대상

| 분류 | 파일 | 역할 |
|---|---|---|
| 공통 기반 | `contact_detector.py` | 접촉 감지 (biomechanics 기반, 모든 파울 탐지의 전제) |
| 수비 파울 (4) | `blocking_foul_detector`, `hand_check_detector`, `holding_foul_detector`, `reach_in_detector` | LGP/핸드체크/홀딩/리치인 |
| 공격 파울 (2) | `charging_foul_detector`, `illegal_screen_detector` | 차징/불법 스크린 |
| 분석기 (1) | `foul_severity_analyzer` | 5요소 가중 심각도 점수 |
| 슈팅 (1) | `shooting_foul_classifier` | 2PT/3PT/앤드원 분류 |
| 플래그런트 (1) | `flagrant_detector` | F1/F2/Clear Path/UF |
| 테크니컬 (1) | `technical_violation_detector` | 9종 테크니컬 유형 |
| export | `__init__.py` | 11 detector + 타입 export |

---

## 2. 감사 8축 평가

### 2.1 Import 유효성 ⚠ 94/100

- 12파일 전체 `from __future__ import annotations` ✓
- 모든 detector가 `base_rule`(FoulRule) + `shared.constants.*` SSOT 준수 ✓
- **Safe-Now**: [technical_violation_detector.py:299](ai_referee/fouls/technical_violation_detector.py#L299) `import math` 함수 내부 local import (상단에 없음, PEP 8 위반)

### 2.2 기능 유효성 ⚠ 91/100

- **기반 구조 우수**: `FoulRule` 베이스 + `_check_*` 하위 헬퍼 + `evaluate()` 표준 템플릿
- FIBA 규정 정확 반영 (LGP, 실린더, Verticality, Restricted Arc)
- NBA 차이점 분기 적절 (3pt 7.24m vs 6.75m, restricted arc 1.22 vs 1.25)
- **Safe-Now**:
  - [reach_in_detector.py:99](ai_referee/fouls/reach_in_detector.py#L99) `_states: dict[tuple[int, int], _ReachState]` 초기화되지만 코드 흐름 상 **저장/조회 경로 없음** (죽은 상태). `_ReachState` dataclass도 인스턴스 생성 없음
  - [illegal_screen_detector.py:138-139](ai_referee/fouls/illegal_screen_detector.py#L138-L139) `if state.positions is None:` 방어 — `_ScreenerState(positions=[pos])` 로 항상 초기화되어 있어 죽은 가드
  - [contact_detector.py:289-301](ai_referee/fouls/contact_detector.py#L289-L301) 주석 "3가지 중 2가지 이상 충족" ↔ 실제 4가지 조건 체크 → 주석-코드 불일치
- **관찰**: [contact_detector.py:335](ai_referee/fouls/contact_detector.py#L335) `max_accel == abs(accel1.get("torso", 0.0))` — 부동소수점 동등 비교, offender 판별 불안정

### 2.3 메모리 누수 방지 ⚠ 91/100

- 대부분 detector `_states` 딕셔너리 크기 제한 (30/50/100) + stale 제거 ✓
- `contact_detector._states` 100 쌍 초과 시 80개 유지 ✓
- **관찰**: [reach_in_detector.py:222-223](ai_referee/fouls/reach_in_detector.py#L222-L223) `if len(self._states) > 50: self._states.clear()` — 전체 초기화 (LRU 아님). 다른 detector는 시간 기반 stale 제거. 일관성 없음 (게다가 상기 S22처럼 실제 사용조차 안 됨)

### 2.4 하드코딩 점검 ❌ 82/100

- **중요 이슈**: **`fps = 30.0` 하드코딩 반복** (8파일 이상)
  - [blocking_foul_detector.py:118](ai_referee/fouls/blocking_foul_detector.py#L118)
  - [hand_check_detector.py:117](ai_referee/fouls/hand_check_detector.py#L117)
  - [holding_foul_detector.py:116](ai_referee/fouls/holding_foul_detector.py#L116)
  - [shooting_foul_classifier.py:286](ai_referee/fouls/shooting_foul_classifier.py#L286) `> 90` 프레임 (3초 @ 30fps 암묵 가정)
  - → 실제 영상 fps 다를 시 LGP/지속프레임 판정 오차
- **매직 넘버 다수**:
  - [contact_detector.py:234](ai_referee/fouls/contact_detector.py#L234) `dist > 2.0` (2m 접촉 불가 거리)
  - [contact_detector.py:266](ai_referee/fouls/contact_detector.py#L266) `shoulder_width = 0.45` (평균 어깨 너비)
  - [reach_in_detector.py:253](ai_referee/fouls/reach_in_detector.py#L253) / [illegal_screen_detector.py:299](ai_referee/fouls/illegal_screen_detector.py#L299) `cylinder_radius = shoulder_width * 0.6`
  - `movement < 0.02` (정지 판정 임계) 반복
- **관찰**: [foul_severity_analyzer.py:296](ai_referee/fouls/foul_severity_analyzer.py#L296) `context.game_clock_sec < 120.0 and context.quarter >= 4` — 클러치 정의 리그별 분기 부재 (11A 관찰 재발)

### 2.5 한줄 검토 ✅ 97/100

- docstring + 규정 참조 (`FIBA Rule 33.7` 등) + 판정 기준 나열 일관
- Korean 한글 evidence 표기 일관 (`"블로킹: ..."`, `"차징: ..."`)
- 파일 버전/작성자 표준 준수

### 2.6 스레드 안전성 ✅ 96/100

- 12개 detector 모두 `_state_lock = RLock()` + `with self._state_lock:` ✓
- BaseRule 통계 락 + 각 detector state 락 분리 설계 ✓
- `last_contacts` / `last_severity` 방어적 복사 ✓
- **관찰**: [flagrant_detector](ai_referee/fouls/flagrant_detector.py) `_state_lock` 정의하지만 보호할 내부 상태 없음 (evaluate 로컬 변수만) — 데드 락이나 _make_foul_result 호출 보호로 유용

### 2.7 예외 처리 ✅ 94/100

- `RuleParameters.get_float/get_int` 방어적 캐스팅 일관 ✓
- `None` 체크 방어 전면 (keypoints, positions, ball_position) ✓
- `applies_to` 에서 데드볼/미보유 조기 리턴으로 안정적 ✓

### 2.8 확장성 ✅ 96/100

- 11 detector 전부 `FoulRule` 상속 + `RuleParameters` 주입 가능 ✓
- 리그별 분기 `if rule_set == RuleSet.NBA:` 패턴 일관 ✓
- `TechnicalType.requires_human_review` property — 사람 검토 필수 유형 플래그 ✓ (실제 활용은 `decisions/` 에서 확인 필요)

---

## 3. Safe-Now 이슈 목록 (5건)

### S21. `technical_violation_detector.py` math import 함수 내부 local (중요)

- **파일**: [ai_referee/fouls/technical_violation_detector.py:299](ai_referee/fouls/technical_violation_detector.py#L299)
- **현황**: `_check_protest_gesture` 내부에서 `import math` — 파일 상단에 math import 없음
- **조치**: 모듈 상단 import 목록에 `import math` 추가 + 함수 내부 local import 제거

### S22. `reach_in_detector.py` `_states` 죽은 딕셔너리

- **파일**: [ai_referee/fouls/reach_in_detector.py:99](ai_referee/fouls/reach_in_detector.py#L99)
- **현황**:
  - `self._states: dict[tuple[int, int], _ReachState] = {}` 초기화
  - `_ReachState` dataclass 정의
  - 하지만 `evaluate()` / `_check_*` 내부에서 `_states` 에 쓰기/읽기 없음
  - line 222-223 `if len(self._states) > 50: self._states.clear()` — 영원히 발동 안 됨
  - `reset()` 의 `self._states.clear()` 만 유효
- **조치**: `_ReachState` dataclass + `self._states` + 관련 clear/stale 로직 제거 (현재 파일에서 미사용)

### S23. `illegal_screen_detector.py` 죽은 None 가드

- **파일**: [ai_referee/fouls/illegal_screen_detector.py:138-139](ai_referee/fouls/illegal_screen_detector.py#L138-L139)
- **현황**: `_ScreenerState(player_id=pid, positions=[pos])` 로 생성되어 `positions` 는 절대 None이 아님. `if state.positions is None: state.positions = []` 블록은 영원히 False
- **조치**:
  - 간편 제거: 해당 `if/=[]` 블록 삭제
  - 또는 `_ScreenerState.positions` 기본값을 `None` 으로 두고 헬퍼 생성자 도입 (현재가 더 간결)

### S24. `contact_detector.py` 주석-코드 불일치

- **파일**: [ai_referee/fouls/contact_detector.py:289-301](ai_referee/fouls/contact_detector.py#L289-L301)
- **현황**: 주석 `"접촉 판정 기준: 3가지 중 2가지 이상 충족"` ↔ 실제 코드 4가지 조건 (overlap_ratio, max_accel, min_kp_dist, max_vel_change)
- **조치**: 주석 수정 "4가지 중 2가지 이상 충족"

### S25. `flagrant_detector.py` 미사용 `_state_lock`

- **파일**: [ai_referee/fouls/flagrant_detector.py:104](ai_referee/fouls/flagrant_detector.py#L104)
- **현황**: `self._state_lock = RLock()` 초기화, `with self._state_lock:` 로 `evaluate` 본문 감싸지만 보호할 공유 상태 없음 (evaluate 내부 로컬 변수만 사용)
- **조치**: lock 제거 — BaseRule 의 `_lock` 이 통계 보호 담당

---

## 4. Phase 15 Deferred 이슈 (5건)

### P15-11B-01. fps Config 노출 (광범위)

- **대상**: blocking/hand_check/holding/shooting_foul_classifier
- **방안**: `RuleParameters` 에 `fps` 키 추가 (`context.extra["fps"]` 주입 또는 Config 필드)
- **우선순위**: **높음** — 실제 영상 fps가 30 아닐 시 LGP/지속프레임 판정 오차

### P15-11B-02. `foul_severity_analyzer` 가중치 5종 Config 미노출

- [foul_severity_analyzer.py:64-69](ai_referee/fouls/foul_severity_analyzer.py#L64-L69) `_WEIGHT_IMPACT/BODY_PART/INTENT/VULNERABILITY/GAME_CONTEXT` 모듈 상수
- 리그/대회별 가중치 조정 가능성 — Config 승격

### P15-11B-03. `contact_detector` offender 판별 float compare

- [contact_detector.py:335](ai_referee/fouls/contact_detector.py#L335) `max_accel == abs(accel1.get("torso", 0.0))`
- 부동소수점 == 비교는 두 선수의 가속도가 정확히 같지 않으면 p1 or p2 판별이 불안정
- 방안: `abs(accel1.get("torso",0.0)) >= abs(accel2.get("torso",0.0))` 비교

### P15-11B-04. 매직 넘버 Config 승격

- `shoulder_width=0.45`, `cylinder_radius = shoulder_width * 0.6`, `dist > 2.0` (접촉 불가), `movement < 0.02` (정지), `90프레임` (shooting timeout)

### P15-11B-05. 리그별 클러치 분기

- `foul_severity_analyzer` 의 "경기 종반" 정의 `< 120s + quarter >= 4` — 11A와 동일 이슈. 통합 정책 필요

---

## 5. 11B 종합 점수

| 축 | 점수 |
|---|---|
| Import 유효성 | 94 |
| 기능 유효성 | 91 |
| 메모리 누수 방지 | 91 |
| 하드코딩 점검 | 82 |
| 한줄 검토 | 97 |
| 스레드 안전성 | 96 |
| 예외 처리 | 94 |
| 확장성 | 96 |
| **총점** | **92.6** |

---

## 6. 관찰된 강점

1. **규정 기반 설계** — 각 detector가 FIBA Rule 번호 명시 + NBA 차이 분기
2. **심각도 분석기 설계** — 5요소 가중 (impact/body_part/intent/vulnerability/context) 합계 1.0 정규화
3. **근거 기반 판정** — `evidence` 리스트에 한글 근거 축적 → 설명 가능성 확보
4. **계층적 구조** — `contact_detector` 가 공통 기반, 나머지 10 detector가 `contact_events` extra 활용
5. **리걸 가딩 포지션(LGP)** 판정 — 정지 프레임 기반 0.10초 임계, `lgp_established` 플래그 일관

---

## 7. 관찰된 약점

1. **fps 가정 만연** — 8+ 파일에서 30fps 암묵 가정
2. **죽은 코드 일부 존재** — `reach_in._states`, `illegal_screen.None` 가드, 주석-코드 불일치
3. **매직 넘버 Config 미노출** — 파라미터 튜닝 범위가 코드 직접 수정 필요

---

## 8. 다음 작업

1. Safe-Now 5건 즉시 처리 여부 확정 (S21/S22/S23/S24/S25)
2. Phase 11C `violations/` 13파일 착수
