# 11C. ai_referee/violations/ 감사 리포트

**감사 범위**: `ai_referee/violations/` 13파일 (1 `__init__` + 12 detector)
**감사 방식**: 전수 직독 (Read 전용)
**감사 축**: 8종
**감사일**: 2026-04-20

---

## 1. 감사 대상 구성

| 범주 | 파일 | 역할 |
|---|---|---|
| 드리블/볼 (3) | `traveling`, `double_dribble`, `carry` _detector | 피봇/양손/팔밍 |
| 접촉/볼 (1) | `kick_ball_detector` | 의도적 킥볼 |
| 시간 기반 (5) | `three_second`, `defensive_three_sec` (NBA), `five_second`, `eight_second`, `twenty_four_second` _detector | 페인트/FT/스로인/백코트/샷클락 |
| 코트 경계 (2) | `backcourt_detector`, `out_of_bounds_detector` | 백코트/아웃 |
| 바스켓 (1) | `goaltending_detector` | 골텐딩 + 인터피어런스 통합 |

---

## 2. 감사 8축 평가

### 2.1 Import 유효성 ⚠ 93/100

- 13파일 전체 `from __future__ import annotations` + SSOT 준수 ✓
- **Safe-Now**:
  - [traveling_detector.py:26](ai_referee/violations/traveling_detector.py#L26) `from collections import deque` 미사용 (파일 내 deque 참조 없음)
  - [traveling_detector.py:27](ai_referee/violations/traveling_detector.py#L27) `dataclass, field` 중 `field` 미사용

### 2.2 기능 유효성 ✅ 94/100

- 모든 detector가 `ViolationRule` 상속 + `_make_violation_result` 일관 사용 ✓
- 리그별 분기 적절 (NBA 제로스텝/수비3초/공격 방향)
- 골텐딩 + 바스켓 인터피어런스 통합 모듈 설계 우수 (단일 detector로 두 유형 처리)
- **관찰**: [five_second_detector.py:222](ai_referee/violations/five_second_detector.py#L222) `is_stationary = "hold" in action.lower() or "stationary" in action.lower()` — 문자열 `in` 매칭, action enum 엄격 비교 권장
- **관찰**: [eight_second_detector.py:59](ai_referee/violations/eight_second_detector.py#L59) 주석 `"NBA는 10초가 아닌 8초를 사용합니다 (동일한 FIBA 기준)"` — 다소 혼란스러운 표현 (2000년 이후 NBA·FIBA 모두 8초)

### 2.3 메모리 누수 방지 ✅ 94/100

- 모든 detector가 `_states` 딕셔너리 + `reset()` 구현 ✓
- 단일 상태 detector (eight_second/twenty_four_second/backcourt/five_second)는 `_state: T | None` 패턴 일관 ✓
- **Safe-Now**:
  - [traveling_detector.py:47](ai_referee/violations/traveling_detector.py#L47) `_MAX_STEP_HISTORY: Final[int] = 60` 미사용 상수 (history list 자체 없음, step_count 스칼라만 유지)
  - [twenty_four_second_detector.py:104-105](ai_referee/violations/twenty_four_second_detector.py#L104-L105) `fps = 30.0` + `frame_sec = 1.0 / fps` 정의되지만 실제 `context.shot_clock_sec` 만 사용 → **frame_sec 미사용 변수**

### 2.4 하드코딩 점검 ❌ 83/100

- **중요 이슈 (Phase 11B와 동일 패턴 확대)**: `fps = 30.0` 반복 하드코딩
  - [carry_detector.py:143](ai_referee/violations/carry_detector.py#L143)
  - [kick_ball_detector.py:114](ai_referee/violations/kick_ball_detector.py#L114) `* 30` 직접 상수
  - [three_second_detector.py:110](ai_referee/violations/three_second_detector.py#L110)
  - [defensive_three_sec_detector.py:119](ai_referee/violations/defensive_three_sec_detector.py#L119)
  - [five_second_detector.py:118](ai_referee/violations/five_second_detector.py#L118)
  - [eight_second_detector.py:98](ai_referee/violations/eight_second_detector.py#L98)
  - 총 6+ 파일에서 반복 — **Phase 11B의 S21과 동일 이슈 계속**
- **매직 넘버**:
  - [carry_detector.py:122](ai_referee/violations/carry_detector.py#L122) `wrist[2] < ball_pos[2] - 0.05` (손목 아래 판정 오프셋)
  - [carry_detector.py:140](ai_referee/violations/carry_detector.py#L140) `abs(ball_z - state.last_ball_z) < 0.02` (체류 판정)
  - [double_dribble_detector.py:146](ai_referee/violations/double_dribble_detector.py#L146) `left_dist < 0.3 and right_dist < 0.3` (양손 근접)
  - [kick_ball_detector.py:104](ai_referee/violations/kick_ball_detector.py#L104) `_BALL_LEG_CONTACT_DIST_M: Final[float] = 0.25` — Config 미노출
  - [goaltending_detector.py:129](ai_referee/violations/goaltending_detector.py#L129) `cylinder_radius = 0.225` 기본값 (extra override 가능하나 FIBA 표준 0.2286 근사)

### 2.5 한줄 검토 ✅ 96/100

- docstring + 규정 참조 + 감지 시나리오 나열 일관 ✓
- Korean 한글 evidence 일관 ✓
- 파일 메타 표준 준수 ✓

### 2.6 스레드 안전성 ✅ 97/100

- 12 detector + `__init__` 전체 `_state_lock = RLock()` + `with self._state_lock:` 일관 ✓
- 단일 상태 및 딕셔너리 모두 락 보호 ✓

### 2.7 예외 처리 ✅ 95/100

- `if not ball_pos:` / `if not keypoints:` 등 방어 체크 전면 ✓
- `_make_violation_result(violated=False, confidence=0.0)` 조기 리턴 패턴 일관 ✓
- `context.extra.get()` 기본값 fallback ✓

### 2.8 확장성 ✅ 96/100

- 12 detector 모두 `RuleParameters` DI ✓
- 리그별 분기 명확 (NBA 전용: `defensive_three_sec`, `traveling.zero_step`; FIBA 전용: `five_second.closely_guarded`)
- `out_of_bounds_detector` 멀티뷰 카메라 투표 지원 (`oob_camera_votes` via extra) — **decisions 레이어와 정합 우수**
- **관찰**: `context.extra.get("attack_direction", "right")` — 방향 추론 외부 제공 의존. 확장 지점 명확

---

## 3. Safe-Now 이슈 목록 (4건)

### S26. `traveling_detector.py` 미사용 `deque` import

- **파일**: [ai_referee/violations/traveling_detector.py:26](ai_referee/violations/traveling_detector.py#L26)
- **현황**: `from collections import deque` — 파일 내 `deque` 사용처 없음
- **조치**: import 제거

### S27. `traveling_detector.py` 미사용 `field` import

- **파일**: [ai_referee/violations/traveling_detector.py:27](ai_referee/violations/traveling_detector.py#L27)
- **현황**: `from dataclasses import dataclass, field` — `field` 미사용
- **조치**: `from dataclasses import dataclass` 로 축소

### S28. `traveling_detector.py` 미사용 상수 `_MAX_STEP_HISTORY`

- **파일**: [ai_referee/violations/traveling_detector.py:47](ai_referee/violations/traveling_detector.py#L47)
- **현황**: `_MAX_STEP_HISTORY: Final[int] = 60` 정의, 주석 "최대 스텝 이력 프레임" 이지만 history list 자체 없음 (state.step_count 스칼라만 유지)
- **조치**: 상수 제거

### S29. `twenty_four_second_detector.py` 미사용 변수 `fps`/`frame_sec`

- **파일**: [ai_referee/violations/twenty_four_second_detector.py:104-105](ai_referee/violations/twenty_four_second_detector.py#L104-L105)
- **현황**:
  ```python
  fps = 30.0
  frame_sec = 1.0 / fps
  ```
  이후 `context.shot_clock_sec` 를 직접 사용 (line 157-162)하므로 `frame_sec` / `fps` 활용 없음
- **조치**: 두 변수 제거

---

## 4. Phase 15 Deferred 이슈 (5건)

### P15-11C-01. **fps Config 노출 (광범위·중요)**

- 11B에 이어 11C에서도 6+ 파일 하드코딩
- 통합 방안: `context.extra["fps"]` 주입 또는 `FrameContext.fps` 필드 추가 (core 변경)
- **권장**: `FrameContext` 확장이 가장 깔끔 (FrameContext는 이미 모든 파이프라인 입력 컨테이너)

### P15-11C-02. `five_second_detector` 문자열 `in` 매칭

- [five_second_detector.py:222](ai_referee/violations/five_second_detector.py#L222) `"hold" in action.lower()` — enum 엄격 매칭 대체

### P15-11C-03. `eight_second_detector` 주석 정정

- [eight_second_detector.py:59](ai_referee/violations/eight_second_detector.py#L59) 주석 혼란스러운 표현 → "FIBA·NBA 모두 8초 (NBA는 2000년 10→8초 전환)"

### P15-11C-04. 매직 넘버 Config 승격

- carry 손목 오프셋 0.05, ball_z 체류 0.02, double_dribble 양손 거리 0.3 등

### P15-11C-05. goaltending `cylinder_radius` 기본값

- [goaltending_detector.py:129](ai_referee/violations/goaltending_detector.py#L129) `0.225` — FIBA 표준 림 내경은 0.2286m (9인치), 오차 ±0.003m. Config 노출 + FIBA 값으로 동기화

---

## 5. 11C 종합 점수

| 축 | 점수 |
|---|---|
| Import 유효성 | 93 |
| 기능 유효성 | 94 |
| 메모리 누수 방지 | 94 |
| 하드코딩 점검 | 83 |
| 한줄 검토 | 96 |
| 스레드 안전성 | 97 |
| 예외 처리 | 95 |
| 확장성 | 96 |
| **총점** | **93.5** |

---

## 6. 관찰된 강점

1. **규칙 분기 설계** — `if self._rule_set == RuleSet.NBA:` / `== RuleSet.FIBA` 명확 (zero_step, defensive_three_sec, closely_guarded)
2. **상태 유형 일관** — 단일 상태 (`_state: T | None`) vs 딕셔너리 (`_states: dict[pid, T]`) 적절 선택
3. **골텐딩 통합 모듈** — 골텐딩 + 바스켓 인터피어런스 + 림 접촉 규칙 분기까지 포함한 단일 detector
4. **멀티뷰 통합** — `oob_camera_votes` 등 다중 카메라 합의 로직 내장
5. **이벤트 드리븐 리셋** — `shot_clock_event: "offensive_rebound"/"foul"/"rim_hit"/"shot_attempt"` 외부 이벤트 수신으로 유연한 상태 관리

---

## 7. 관찰된 약점

1. **fps 가정 만연 (11B 연장)** — violations/ 6+ 파일 + fouls/ 4+ 파일 동일 이슈, 전역 해결 필요
2. **action 문자열 매칭** — `"dribble" in action.lower()`, `"hold" in action.lower()` 등 enum 대체 여지
3. **traveling_detector 죽은 구조** — `_MAX_STEP_HISTORY`, `deque` import, `field` import 모두 미사용

---

## 8. 다음 작업

1. Safe-Now 4건 즉시 처리 여부 확정 (S26/S27/S28/S29)
2. Phase 11D `decisions/` 7파일 착수
