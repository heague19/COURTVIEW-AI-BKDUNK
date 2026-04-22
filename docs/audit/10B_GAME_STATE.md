# Phase 10B — game_analysis/game_state/ 감사 보고서

> **감사 범위**: `game_state/` 29파일 (__init__ 4 + game_management 6 + event_detection 16 + live_workspace 3)
> **감사 방식**: Read 도구 전수 직독 (grep/ls 미사용)
> **감사 일자**: 2026-04-20
> **총 라인**: ~14,200 lines
> **역할**: 경기 상태 관리 (기록원 대체) + 16종 이벤트 감지 + Human-in-the-Loop 검증/보정

---

## 0. 실행 요약

| 축 | 점수 | 핵심 관찰 |
|---|---|---|
| 1. Import 유효성 | 100 | 전 파일 `from __future__ import annotations`, 절대 임포트 |
| 2. 기능 유효성 | 94 | 학술 근거 일관 기재, 16종 이벤트 + 6종 관리 + 3종 검증 모두 동작 |
| 3. 메모리 누수 | 98 | `_MAX_*_HISTORY` 전 파일 trim, 단 silent drop 1건 (foul history 200) |
| 4. 하드코딩 | 88 | 리그 상수 참조 양호 / score_detector dataclass vs from_yaml 기본값 불일치 (버그) |
| 5. 1줄 리뷰 | 100 | 한글 docstring + 학술 출처 + Cadence 라벨 (🔴FRAME/🟠EVENT/🔵POST/🟡SPECIAL) |
| 6. 스레드 안전 | 100 | 전 클래스 RLock, 진입점 래핑 일관 |
| 7. 예외 처리 | 95 | try/except 감지기 최상위 래핑, logger.error로 격리 |
| 8. 확장성 | 95 | `from_yaml` 일관 제공, `__slots__` 미사용 (Manager/Detector 클래스) |
| **총평** | **96.3** | S-grade, Safe-Now 3건 + Phase 15 권고 5건 |

---

## 1. 모듈 구조

### 1.1 파일 분포 (29파일, ~14,200 lines)

| 서브 | 파일 수 | 라인 합 | 역할 |
|---|---|---|---|
| `__init__.py` ×4 | 4 | 620 | 패키지/서브패키지 통합 export |
| `game_management/` | 6+1 | ~3,100 | 🟠/🔴/🔵 경기 관리 (시계·파울·타임아웃·교체·기록정정·출력) |
| `event_detection/` | 16+1 | ~7,700 | 🔴/🟠/🟡 16종 이벤트 감지 |
| `live_workspace/` | 3+1 | ~1,700 | 🟠 HITL 검증/수동태깅/보정동기화 |

### 1.2 Cadence 분포

| Cadence | 파일 | 예산 |
|---|---|---|
| 🔴 FRAME | clock_manager, score_detector, possession_tracker, dead_ball_detector | <2ms |
| 🟠 EVENT | foul_manager, timeout_manager, substitution_manager, record_corrector, shot_event_detector, rebound_detector, assist_detector, block_detector, steal_detector, turnover_detector, foul_detector, screen_detector, fast_break_detector, drive_detector, live_event_validator, manual_event_tagger, correction_sync | <10ms |
| 🟡 SPECIAL | free_throw_detector, box_out_detector, jump_ball_detector | 상황별 |
| 🔵 POST-GAME | official_format_exporter | 시간 무제한 |

---

## 2. 감사 축별 평가

### 2.1 축 1 — Import 유효성 (100/100)

- 29파일 전원 `from __future__ import annotations` 적용
- `shared.constants`, `shared.dto`, `shared.interfaces` 세 계층으로 명확히 분리
- `GameModuleState`, `GameModuleMetrics`, `GameEventResult` 공통 인터페이스 16개 detector 일관 사용
- 순환 참조 없음

### 2.2 축 2 — 기능 유효성 (94/100)

**우수**
- 학술 출처 전 파일 기재:
  - Knudson (1993), Miller & Bartlett (1996) — 슈팅
  - Oliver (2004), Kubatko (2007) — 점유/턴오버
  - Gomez (2008) — 리바운드
  - McNitt-Gray (1993) — 파울 접촉
  - Sampaio (2010) — 블록/데드볼
  - Lamas (2011) — 스크린
  - Conte (2015) — 속공
  - Courel-Ibáñez (2017) — 드라이브
  - Trninić (2002) — 박스아웃
  - FIBA Rule 12, 43 — 점프볼/자유투
  - Okazaki & Rodacki (2012), Silverberg (2018) — 슛 궤적
- 리그별 규정 분기 (FIBA/NBA/KBL/NBL/EUROLEAGUE):
  - `clock_manager`: quarter_duration, OT_duration
  - `foul_manager`: max_personal_fouls, bonus_threshold
  - `timeout_manager`: 전반/후반 분리 (FIBA) vs 통합 (NBA)
- 16종 이벤트 감지 세분화 (shot 13종 + dribble 13종 + turnover 18종 + block 4종 + screen 7종 + drive 5종 + box_out 4종 + fastbreak 7종 + jumpball 4종)

**감점 (-6)**

- **B1 (버그 후보)**: [score_detector.py:101-104](game_analysis/game_state/event_detection/score_detector.py#L101-L104) dataclass 기본값과 [score_detector.py:127-129](game_analysis/game_state/event_detection/score_detector.py#L127-L129) `from_yaml` 기본값 불일치:
  - dataclass: `min_confidence=0.40`, `require_ball_through_hoop=False`, `net_deflection_required=False`
  - from_yaml: `min_confidence=0.90`, `require_ball_through_hoop=True`, `net_deflection_required=True`
  - `ScoreDetector()` vs `ScoreDetector.from_yaml({})`가 서로 다른 동작 → **Safe-Now 후보**
- **B2 (버그 후보)**: [correction_sync.py:133](game_analysis/game_state/live_workspace/correction_sync.py#L133): `scope_str in RecalcScope.__members__.values()` — `__members__.values()`는 `Enum` 객체 반환이므로 문자열 비교 항상 False. 결과적으로 **항상 `INCREMENTAL` 기본값 사용됨**. `any(s.value == scope_str for s in RecalcScope)` 또는 `try/except ValueError` 필요 → **Safe-Now 후보**
- **B3 (의미 혼용)**: `screen_detector.py:309`, `possession_tracker.py:394`, `fast_break_detector.py:333`, `drive_detector.py:401`, `dead_ball_detector.py:325,350`, `box_out_detector.py:287`가 `GameEventType.SUBSTITUTION/JUMP_BALL/SHOT_ATTEMPT/TIMEOUT/DEFENSIVE_REBOUND`를 다른 의미로 재사용. 추적 체인 오염 가능 — Phase 15 권고

### 2.3 축 3 — 메모리 누수 (98/100)

**우수**
- 전 파일 `_MAX_*_HISTORY` 상수 + `_trim_history()` 메서드
- `reset()` 완전 정리
- `__slots__` 모든 dataclass (Config/Input/Result/Record) 적용
- `correction_sync`는 `_cleanup_triggers` + 상태 기반 정리 (COMPLETED/EXPIRED)

**감점 (-2)**
- **M1 (silent drop)**: [foul_manager.py:250-251](game_analysis/game_state/game_management/foul_manager.py#L250-L251) — `_MAX_FOUL_HISTORY=200` 초과 시 파울 이력 사일런트 드롭. 개인파울/팀파울 카운트는 유지되나 `revoke_foul`이 실패할 수 있음 (이력에서 찾지 못함). 경기당 80~100회 예상이므로 정상 상황 문제 없으나 장기 OT에서 위험
- **M2 (silent drop)**: [timeout_manager.py:235-236](game_analysis/game_state/game_management/timeout_manager.py#L235-L236), [substitution_manager.py:342-343](game_analysis/game_state/game_management/substitution_manager.py#L342-L343) — 동일 패턴 (history 드롭)

### 2.4 축 4 — 하드코딩 (88/100)

**우수**
- `shared/constants/game_management_constants`의 모든 리그 상수 참조:
  - `QUARTER_DURATION_SEC`, `OVERTIME_DURATION_SEC`, `SHOT_CLOCK_FULL_SEC`
  - `TEAM_FOUL_BONUS_THRESHOLD`, `TIMEOUTS_PER_TEAM`, `TIMEOUT_DURATION_SEC`
  - `SCORE_INTEGRITY_MAX_DIFF`, `REBOUND_INTEGRITY_TOLERANCE`, `PLAYING_TIME_TOLERANCE_SEC`
- `shared/constants/tactical_constants`의 모든 전술 상수:
  - `SCREEN_*`, `FAST_BREAK_*`, `DRIVE_*` (7개)

**감점 (-12)**
- **H1**: [free_throw_detector.py:416](game_analysis/game_state/event_detection/free_throw_detector.py#L416) `distance_meters=4.57` 하드코딩 — `court_constants.FREE_THROW_LINE_M` 참조 필요 (Phase 5 SSOT 원칙 위반)
- **H2**: [shot_event_detector.py:527](game_analysis/game_state/event_detection/shot_event_detector.py#L527) `CourtZone.PAINT_CENTER if pending.distance_to_hoop_m <= 2.0` — 2.0m 하드코딩, zone_constants 참조 권고
- **H3**: [shot_event_detector.py:332](game_analysis/game_state/event_detection/shot_event_detector.py#L332) `_DEDUP_WINDOW_SEC: Final[float] = 1.0` — 정의만 있고 사용 없음 (데드 코드)
- **H4**: [possession_tracker.py:332-333](game_analysis/game_state/event_detection/possession_tracker.py#L332-L333) 쿨다운 프레임 50 하드코딩 ("30프레임(~3초)" 주석과 불일치)
- **H5**: [dead_ball_detector.py:137](game_analysis/game_state/event_detection/dead_ball_detector.py#L137) `player_inactivity_speed_ms=0.3` — YAML 미노출 (from_yaml이 이 값을 읽지 않음)
- **H6**: [foul_manager.py:71](game_analysis/game_state/game_management/foul_manager.py#L71) `_TECHNICAL_FOUL_EJECTION = 2` — FIBA/NBA 공통이지만 리그별 상수로 승격 권고

### 2.5 축 5 — 1줄 리뷰 (100/100)

일관된 헤더 포맷:
```
COURTVIEW - AI 농구 분석 플랫폼
모듈: ...
파일: ...
설명: ... + Cadence 라벨
학술 근거: ...
참조/의존성/소비자
작성자/수정일/버전
```

### 2.6 축 6 — 스레드 안전 (100/100)

- 전 클래스 `self._lock = RLock()` 생성자에서 초기화
- 모든 public 메서드 `with self._lock:` 래핑
- 내부 `_detect_*`, `_evaluate_*` 메서드는 lock 내부 호출 전제

### 2.7 축 7 — 예외 처리 (95/100)

**우수**
- 감지기 최상위 `try: ... except Exception as e: logger.error(...); return None` 패턴 — 예외 격리
- `transition_to` 실패 시 `logger.warning` + `return False`

**감점 (-5)**
- **E1**: [foul_manager.py:586-664](game_analysis/game_state/game_management/foul_manager.py#L586-L664) `revoke_foul`이 이력에서 못 찾으면 warning + return False — 정상. 그러나 **퇴장 해제 로직(645-658)**이 현재 파울 수만 확인하고 revoke된 파울이 "이미 이력에 없음" 상황을 처리. 엣지 케이스 (이력 trim + revoke) 취약
- **E2**: [correction_sync.py:133](game_analysis/game_state/live_workspace/correction_sync.py#L133) Enum 변환 버그(B2)에서 `try/except`를 쓰지 않아 잘못된 YAML이 조용히 기본값 fallback

### 2.8 축 8 — 확장성 (95/100)

- 전 Config 클래스 `from_yaml` 팩토리 ✓
- 전 Manager/Detector 클래스 `from_yaml` 팩토리 ✓
- `@dataclass(slots=True)` — Config/Input/Record 전부
- **감점 (-5)**: **Manager/Detector 클래스 본체**는 `__slots__` 미사용 (동적 속성 추가 가능). [possession_tracker.py:389](game_analysis/game_state/event_detection/possession_tracker.py#L389) `self._last_transition_frame = data.frame_index`가 `__init__`에 선언되지 않고 런타임 동적 생성 — **Safe-Now 후보**

---

## 3. 파일별 하이라이트

### 3.1 game_management/ (6+1)

| 파일 | 점수 | 비고 |
|---|---|---|
| `clock_manager.py` | 100 | 9상태 머신, FPS 기반 tick, GameState 전이 검증 (`is_valid_game_transition`) |
| `foul_manager.py` | 95 | 개인/팀/테크니컬 분리 카운팅, bonus/foul_trouble, revoke 지원. M1 silent drop |
| `timeout_manager.py` | 98 | FIBA 전후반 분리 vs NBA 통합 분기 명확, OT 추가 부여 |
| `substitution_manager.py` | 98 | stint 기반 출전시간 자동 계산, 쿼터 전환 시 `close_quarter_stints` |
| `record_corrector.py` | 100 | 정정 체인(event_chains), 3종 무결성 검증 (스코어/리바운드/출전시간) |
| `official_format_exporter.py` | 100 | FIBA/NBA/KBL/NBL/JSON/XML 5종 포맷, 재귀 XML 변환 |

### 3.2 event_detection/ (16+1)

| 파일 | 점수 | 비고 |
|---|---|---|
| `shot_event_detector.py` | 95 | 릴리스→결과 2단계, 13종 유형, H2/H3 하드코딩 |
| `free_throw_detector.py` | 92 | 라운드 관리 (1~3구), H1 (4.57m 하드코딩) |
| `score_detector.py` | 88 | 🔴FRAME 증거 누적 패턴. **B1 dataclass/yaml 기본값 불일치** |
| `rebound_detector.py` | 98 | 미스 등록→확보 추적→공수/팀 분류, 팁체인 감지 |
| `assist_detector.py` | 100 | 역추적 방식, 정규/잠재/하키/FT 4종 |
| `block_detector.py` | 100 | 4종 분류 (chase_down/weakside/post/perimeter) |
| `steal_detector.py` | 100 | 3종 분류 (on_ball/passing_lane/post) |
| `turnover_detector.py` | 100 | 18종 세분화, forced/unforced 분류 |
| `foul_detector.py` | 100 | 접촉 감지만 담당 (유형 판정은 ai_referee), 6종 접촉 유형 |
| `possession_tracker.py` | 94 | 팀/개인/슛클락 통합, H4/E3 (런타임 동적 속성) |
| `dead_ball_detector.py` | 92 | 10종 원인, H5 (YAML 미노출), B3 (TIMEOUT/JUMP_BALL 재사용) |
| `screen_detector.py` | 92 | 7종 유형 + 5종 결과, B3 (SUBSTITUTION 재사용) |
| `fast_break_detector.py` | 98 | 7종 유형 (1v0~secondary), B3 (SHOT_ATTEMPT 재사용) |
| `drive_detector.py` | 98 | 5종 방향 + 7종 결과, B3 (SHOT_ATTEMPT 재사용) |
| `box_out_detector.py` | 98 | 4종 유형 + 5종 결과, B3 (DEFENSIVE_REBOUND 재사용) |
| `jump_ball_detector.py` | 100 | 4종 유형 (tip_off/held/alternating/OT) + 승자 판정 |

### 3.3 live_workspace/ (3+1)

| 파일 | 점수 | 비고 |
|---|---|---|
| `live_event_validator.py` | 98 | 3단계 검증 (중복→컨텍스트→신뢰도), 이벤트별 신뢰도 오버라이드 |
| `manual_event_tagger.py` | 100 | 수동 생성 + 태그 + 오버라이드, Pydantic `model_copy` 활용 |
| `correction_sync.py` | 88 | 재계산 트리거 발행 시스템, **B2 Enum 비교 버그**, H6 (영향 모듈 매핑 하드코딩) |

---

## 4. Safe-Now / Phase 15 분류

### 4.1 Safe-Now (즉시 처리 검토)

| 항목 | 파일:라인 | 조치 |
|---|---|---|
| **S3** | `score_detector.py:101-104` vs `:127-129` | dataclass 기본값과 from_yaml 기본값 일치 (0.90/True/True로 통일) |
| **S4** | `correction_sync.py:133` | `scope_str in RecalcScope.__members__.values()` → `try: RecalcScope(scope_str) except ValueError: ...` |
| **S5** | `shot_event_detector.py:51` | `_DEDUP_WINDOW_SEC` 데드 상수 제거 또는 실제 사용 |

### 4.2 Phase 15 (구조 리팩토링 시)

| 항목 | 파일 | 조치 |
|---|---|---|
| P4 | 6개 detector (screen/possession/fast_break/drive/dead_ball/box_out) | `GameEventType` 재사용 대신 전용 event_type 추가 (screen_set, dead_ball, live_ball, drive_start, drive_end, box_out) |
| P5 | `possession_tracker.py:389` | `_last_transition_frame` `__init__`에 명시적 선언 |
| P6 | `foul_manager.py` 외 2개 | Manager/Detector 본체 클래스에 `__slots__` 적용 |
| P7 | `free_throw_detector.py:416` | `FREE_THROW_LINE_M` SSOT 참조 |
| P8 | `dead_ball_detector.py:137` | `player_inactivity_speed_ms` YAML 노출 |
| P9 | `_MAX_*_HISTORY` 전 파일 | silent drop 대신 circular buffer 또는 경고 로그 격상 |

---

## 5. 통계

| 항목 | 값 |
|---|---|
| 총 파일 | 29 |
| 총 라인 | 14,200 |
| `from __future__ import annotations` 적용률 | 100% |
| `@dataclass(slots=True)` 적용 DTO 수 | 72 |
| RLock 적용 Manager/Detector 수 | 20 |
| `from_yaml` 팩토리 제공률 | 100% |
| 학술 출처 인용 파일 수 | 16 (감지기 전원) |
| GameModuleState/Metrics 인터페이스 준수 감지기 | 16 |

---

## 6. 결론

Phase 10B — **S-grade (96.3/100)** 확인.

**핵심 구조 강점**:
- 🔴FRAME/🟠EVENT/🔵POST-GAME/🟡SPECIAL 4-Cadence 명확한 구분
- 16종 이벤트 감지기가 공통 인터페이스(`GameModuleState`, `GameModuleMetrics`, `GameEventResult`)로 통일
- HITL(Human-in-the-Loop) 3단계 (validate → tag/override → sync) 완성

**사용자 결정 대기**:
- **S3, S4, S5** 즉시 처리 여부

**다음**: Phase 10C — `stats/` 14파일 (statistics 7 + predictive_models 4 + __init__ 3).

---

**감사자**: Claude (Opus 4.7)
**검토 완료**: 2026-04-20
