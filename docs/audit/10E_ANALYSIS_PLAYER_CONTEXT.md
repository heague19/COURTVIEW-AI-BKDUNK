# Phase 10E — game_analysis/analysis/player/ + analysis/context/ 감사 보고서

> **감사 범위**: `analysis/player/` 17파일 + `analysis/context/` 25파일 = **42파일**
> **감사 방식**: Read 도구 전수 직독
> **감사 일자**: 2026-04-20
> **총 라인**: ~9,800 lines
> **역할**: POSSESSION/PERIOD/POST-GAME cadence 선수·라인업·공간·흐름·상황별·시즌 분석

---

## 0. 실행 요약

| 축 | 점수 | 핵심 관찰 |
|---|---|---|
| 1. Import 유효성 | 100 | 전 파일 `from __future__ import annotations`, `shared.constants/dto` 일관 참조 |
| 2. 기능 유효성 | 98 | Oliver PPP, Hollinger 방법론 정확 구현. 버그 없음 |
| 3. 메모리 누수 | 92 | **2파일 한도 미 enforcement** (lineup_tracker, movement_heatmap) |
| 4. 하드코딩 | 95 | `tactical/stats/court_constants` SSOT 참조 광범위 |
| 5. 1줄 리뷰 | 100 | 한글 docstring, Cadence 라벨 일관 |
| 6. 스레드 안전 | 100 | 31개 Analyzer 전원 `__slots__` + RLock |
| 7. 예외 처리 | 100 | 분모 0 방어 / 빈 리스트 폴백 |
| 8. 확장성 | 70 | **31개 Analyzer 중 `from_yaml` 제공 0개** — YAML 오버라이드 불가 (10D 대비 더 후퇴) |
| **총평** | **94.4** | S-grade, Safe-Now 2건 + Phase 15 권고 3건 |

---

## 1. 모듈 구조

### 1.1 player/ (17파일)

| 서브 | 파일 수 | 라인 합 | 주요 역할 |
|---|---|---|---|
| `player/__init__.py` | 1 | 11 | 패키지 루트 |
| `individual_analysis/` | 7 | ~1,100 | 드라이브/오프볼/클러치/피로/영향력/리바운드 |
| `lineup_analysis/` | 4 | ~480 | 조합 추적/효율/시너지 |
| `rotation_analysis/` | 5 | ~850 | 교체 패턴/스태거/벤치/휴식 |

### 1.2 context/ (25파일)

| 서브 | 파일 수 | 라인 합 | 주요 역할 |
|---|---|---|---|
| `context/__init__.py` | 1 | 13 | 패키지 루트 |
| `spatial_analysis/` | 5 | ~950 | 플로어 스페이싱/히트맵/구역/페인트 |
| `game_flow/` | 5 | ~760 | 모멘텀/템포/타임아웃/리드 |
| `situation_splits/` | 5 | ~970 | 쿼터/점수차/슛클락/종합 |
| `special_situation/` | 5 | ~830 | ATO/OOB/파울게임/라스트 |
| `season_analysis/` | 4 | ~660 | 누적/추세/벤치마크 |

**전체: 31 Analyzer + 31 Config + 10 Enum + 35+ Record dataclass**

---

## 2. 🔍 핵심 발견: `from_yaml` 부재 — 확장성 후퇴 (P18)

### 2.1 패턴 비교 (Phase 10A~10E)

| Phase | 모듈 | `from_yaml` 제공률 |
|---|---|---|
| 10A | `data_extraction/` | 0/7 (0%) |
| 10B | `game_state/` | 100% (단, S4 Enum 비교 버그) |
| 10C | `stats/` | 100% (단, S3 기본값 불일치) |
| 10D | `analysis/team/` | 44% (4/25 파일은 S8 `cls.attr` 버그) |
| 10E | `analysis/player/+context/` | **0% (31/31 미제공)** |

**의미**:
- 10D에서 절반 이상의 Analyzer가 `from_yaml` 미제공으로 확장성이 후퇴했다고 지적 (P15)
- 10E에서는 **전체가 미제공** — `configs/` YAML을 통한 튜닝이 구조적으로 불가능
- 31개 Analyzer는 Config dataclass 기본값만 사용 (대부분 `shared.constants`의 모듈 상수 참조)

**완화 요소**:
- 모든 Config가 `@dataclass(slots=True)`로 생성자 주입 가능 → 상위 레이어에서 커스텀 Config 객체 전달 가능
- 기본값이 `shared.constants.*` 참조이므로 중앙 상수 변경으로 일괄 조정 가능

**Phase 15 권고**: 31개 Analyzer에 `from_yaml(cls, cfg: dict)` 일관 추가 (10D P15와 통합 처리)

---

## 3. 축별 평가

### 3.1 축 1 — Import 유효성 (100/100)

- 42파일 전원 `from __future__ import annotations`
- `shared.constants` 30+ 상수 광범위 참조:
  - `court_constants`: `HALF_COURT_LENGTH_M`, `COURT_WIDTH_M`, `KEY_WIDTH_M`, `KEY_LENGTH_M`
  - `tactical_constants`: `SPACING_*`, `DRIVE_LANE_MIN_WIDTH_M`, `TEMPO_*`, `MOMENTUM_*`, `SCORING_RUN_*`, `CUT_SPEED_MIN`, `LONG_REBOUND_DISTANCE_M`, `BOX_OUT_*`, `HELP_DEFENSE_*`, `CLOSEOUT_*`, `HALFCOURT_SET_TIME_SEC`
  - `stats_constants`: `WP_CLUTCH_*`, `TREND_*`, `MIN_GAMES_FOR_*`, `PerformanceRating`, `is_clutch_situation`, `get_performance_rating`
  - `game_management_constants`: `SUBSTITUTION_MIN_STAY_SEC`
- DTO 소비: `tactical_dto.*` (DriveStats, OffBallMovement, ClutchStats, FatigueIndicators, LineupData, SpacingData, MomentumState, TimeoutEffectiveness, SituationSplitData, TransitionData, ReboundPosition, ...)

### 3.2 축 2 — 기능 유효성 (98/100)

**우수**
- Oliver (2004) PPP, Hollinger (2005) GameScore 정확 구현
- 9종 점수차 구간 분류, 3종 슛클락 세그먼트, 14종 세트 플레이
- 볼록 껍질(Graham Scan) + Shoelace 공식 (floor_spacing)
- 선형 회귀 기울기 (trend_tracker)
- 로지스틱 CDF 근사 (benchmark_comparator)

**감점 (-2)**
- [benchmark_comparator.py:126](game_analysis/analysis/context/season_analysis/benchmark_comparator.py#L126) — `2.718281828` 하드코딩 (`math.e` 또는 `math.exp()` 사용 권고)

### 3.3 축 3 — 메모리 누수 (92/100)

**우수 패턴** (대부분 파일):
```python
if len(self._records) >= self._config.max_records:
    logger.warning("XXX 기록 한도 도달 (%d)", self._config.max_records)
    return
self._records.append(rec)
```
→ 정확한 enforcement (basic_stats S7 교정 후 패턴과 동일)

**감점 (-8)** — 2파일 한도 미 enforcement:

- **M4 (Safe-Now 후보)**: [lineup_tracker.py:32-39](game_analysis/analysis/player/lineup_analysis/lineup_tracker.py#L32-L39)
  - Config에 `max_lineups: int = _MAX_LINEUPS` 정의
  - `set_lineup` 메서드(line 79-88)에서 한도 체크 없이 무제한 dict 추가
  - 실제로는 라인업 조합이 한정적이나 악의적 호출 시 메모리 누수 가능

- **M5**: [movement_heatmap.py:37](game_analysis/analysis/context/spatial_analysis/movement_heatmap.py#L37)
  - `_MAX_POSITION_RECORDS: Final[int] = 5000` 상수 정의되나 실제 미사용 데드 상수
  - 대신 `_record_count` 카운터만 증가 — 그리드는 고정 크기(10×10)이므로 메모리 자체는 bounded, 상수 의미 없음

### 3.4 축 4 — 하드코딩 (95/100)

**우수** — `shared.constants` 광범위 참조:
- 쿼터 시간, 코트 규격, 전술 임계치 대부분 모듈 상수
- 값 세팅에 `SCORING_RUN_MIN_POINTS`, `TREND_RISING_SLOPE_MIN` 등 SSOT 활용

**감점 (-5)**
- **H15**: [benchmark_comparator.py:126](game_analysis/analysis/context/season_analysis/benchmark_comparator.py#L126) 지수 리터럴 `2.718281828` (과학 상수)
- **H16**: [last_possession.py:35](game_analysis/analysis/context/special_situation/last_possession.py#L35) `_LAST_POSSESSION_THRESHOLD_SEC = 24` — 슛클락 상수 `SHOT_CLOCK_FULL_SEC` 참조 권고
- **H17**: [game_context_analyzer.py:40](game_analysis/analysis/context/situation_splits/game_context_analyzer.py#L40) `_GARBAGE_MARGIN: Final[int] = 25` — `WP_GARBAGE_TIME_MARGIN_POINTS` (stats_constants 기 정의) 있으면 참조 권고
- **H18**: [shot_clock_splits.py:38-39](game_analysis/analysis/context/situation_splits/shot_clock_splits.py#L38-L39) 18초/7초 슛클락 구간 경계 — 모듈 상수만 사용, SSOT 승격 여지

### 3.5 축 5 — 1줄 리뷰 (100/100)

- 42파일 헤더 일관 (목적 + Cadence 라벨 + 의존성 + 소비자)
- Cadence 라벨: 🔵 POSSESSION (<100ms), 🟡 PERIOD, 🟢 POSSESSION(조건부), POST-GAME

### 3.6 축 6 — 스레드 안전 (100/100)

- 31개 Analyzer 본체 전원 `__slots__` ✓
- RLock 일관 적용 ✓
- `with self._lock:` 래핑 완비 ✓

### 3.7 축 7 — 예외 처리 (100/100)

**우수**
- 분모 0 방어: `if attempts == 0: return 0.0`, `if pairs == 0: return 0.0`
- 빈 리스트 early return: `if not recs: return SituationSplitData()`
- Z-score std=0 방어: `if std == 0.0: return False`
- Log 분모 방어: `max_entropy = log2(n) if n > 1 else 1.0`

### 3.8 축 8 — 확장성 (70/100)

**감점 (-30)**
- **P18 (중대 구조 이슈)**: 31/31 Analyzer `from_yaml` 미제공
- 기본값 오버라이드는 Config 인스턴스 생성자 전달로만 가능
- 10D 대비 추가 후퇴 — Phase 10A/B/C 수준(100% 제공)으로 복원 필요

---

## 4. 파일별 하이라이트

### 4.1 player/individual_analysis/ (6)

| 파일 | 점수 | 비고 |
|---|---|---|
| `drive_analyzer.py` | 98 | DriveStats DTO + 방향/결과 분류 |
| `off_ball_movement.py` | 98 | 컷/스크린/이동거리 추적 |
| `clutch_performance.py` | 100 | `is_clutch_situation` 활용, WP_CLUTCH_* 참조 |
| `fatigue_analyzer.py` | 98 | 기준선(1Q 초) 대비 속도/점프 하락률 |
| `player_impact.py` | 100 | 온/오프코트 넷레이팅 간결 구현 |
| `rebound_analysis.py` | 98 | 공/수 + 경합/비경합 + 2차기회 |

### 4.2 player/lineup_analysis/ (3)

| 파일 | 점수 | 비고 |
|---|---|---|
| `lineup_tracker.py` | 88 | **M4 max_lineups 미 enforcement** |
| `lineup_efficiency.py` | 100 | 넷레이팅 + best/worst 식별 |
| `player_synergy.py` | 100 | 2인/3인 조합 combinations 활용 |

### 4.3 player/rotation_analysis/ (4)

| 파일 | 점수 | 비고 |
|---|---|---|
| `rotation_tracker.py` | 100 | 스틴트 관리 + finalize_game |
| `stagger_analyzer.py` | 100 | 핵심 선수 등록 + 함께/스태거 비교 |
| `bench_unit_analyzer.py` | 100 | 스타터 vs 벤치 유닛 분류 |
| `rest_period_analyzer.py` | 100 | 충분/불충분 휴식 비교 |

### 4.4 context/spatial_analysis/ (4)

| 파일 | 점수 | 비고 |
|---|---|---|
| `floor_spacing.py` | 98 | Graham Scan + Shoelace, DRIVE_LANE 계산 |
| `movement_heatmap.py` | 88 | **M5 max_records 데드 상수** |
| `zone_control.py` | 100 | 3구역 × 팀별 × 이벤트 누적 |
| `paint_analysis.py` | 100 | 진입 경로 × 결과 × 선수/팀 |

### 4.5 context/game_flow/ (4)

| 파일 | 점수 | 비고 |
|---|---|---|
| `momentum_tracker.py` | 100 | MOMENTUM_* 상수, 5단계 상태 + tanh 감쇠 |
| `tempo_analyzer.py` | 100 | 팀별 페이스 (per 48min) |
| `timeout_effectiveness.py` | 100 | 전/후 N점유 넷득점 비교 |
| `lead_management.py` | 100 | 역전/타이/최대 리드 추적 |

### 4.6 context/situation_splits/ (4)

| 파일 | 점수 | 비고 |
|---|---|---|
| `period_splits.py` | 100 | Q1~4 + 전/후반 + OT 별도 |
| `score_margin_splits.py` | 100 | 9종 MarginBucket + close/leading/trailing |
| `shot_clock_splits.py` | 98 | early/mid/late 3구간 — **H18 모듈 상수** |
| `game_context_analyzer.py` | 95 | `is_clutch_situation` 재사용 — **H17 garbage_margin** |

### 4.7 context/special_situation/ (4)

| 파일 | 점수 | 비고 |
|---|---|---|
| `ato_play_analyzer.py` | 100 | 타임아웃 후 30초 내 점유 추적 |
| `oob_play_analyzer.py` | 100 | SIDELINE/BASELINE + 5초 바이올레이션 |
| `foul_game_analyzer.py` | 100 | 의도적 파울 전략 감지 |
| `last_possession.py` | 98 | END_OF_* 4종 + 클러치 판정. **H16 24초 상수** |

### 4.8 context/season_analysis/ (3)

| 파일 | 점수 | 비고 |
|---|---|---|
| `season_aggregator.py` | 100 | 시즌 누적 + 경기당 평균 |
| `trend_tracker.py` | 100 | 이동평균 + 선형 회귀 기울기 + Z-score 이상치 |
| `benchmark_comparator.py` | 95 | **H15 지수 리터럴 하드코딩** |

---

## 5. Safe-Now / Phase 15 분류

### 5.1 Safe-Now (즉시 처리 검토)

| 항목 | 파일:라인 | 조치 |
|---|---|---|
| **S9** | `lineup_tracker.py:79-88` (set_lineup) | `max_lineups` 한도 체크 추가 — 경고 후 기존 라인업 반환 또는 None |
| **S10** | `movement_heatmap.py:37` | `_MAX_POSITION_RECORDS` 데드 상수 제거 또는 실제 enforcement (히트맵은 bounded이므로 제거 권고) |

### 5.2 Phase 15 (구조 리팩토링 시)

| 항목 | 파일 | 조치 |
|---|---|---|
| **P18** | 31개 Analyzer | `from_yaml` 팩토리 일괄 추가 (10D P15와 통합 처리) |
| P19 | `benchmark_comparator.py:126` | `2.718281828` → `math.exp(...)` 또는 `math.e` |
| P20 | `last_possession.py:35`, `game_context_analyzer.py:40`, `shot_clock_splits.py:38-39` | 슛클락/가비지 타임 상수 `stats_constants` SSOT 참조 |

---

## 6. 통계

| 항목 | 값 |
|---|---|
| 총 파일 | 42 |
| 총 라인 | ~9,800 |
| `from __future__ import annotations` 적용률 | 100% |
| `@dataclass(slots=True)` DTO/Record/Config 수 | 76 |
| `__slots__` 적용 Analyzer 수 | 31/31 (100%) |
| RLock 적용률 | 100% |
| `from_yaml` 팩토리 제공률 | **0% (31/31 미제공)** |
| `shared.constants.*` 참조 상수 수 | 30+ |
| `shared.dto.tactical_dto.*` 소비 DTO 수 | 15+ |

---

## 7. 결론

Phase 10E — **S-grade (94.4/100)**.

**핵심 강점**:
- 31개 Analyzer 전원 `__slots__` + RLock (Phase 10D 대비 더 일관)
- 학술 방법론(Oliver, Hollinger) + 기하 알고리즘(Convex Hull, Shoelace, 선형회귀, Z-score) 정확 구현
- `shared.constants.*` 광범위 SSOT 참조

**주요 약점**:
- **확장성 완전 후퇴**: 31/31 Analyzer `from_yaml` 미제공 — YAML 오버라이드 구조적 불가
- **메모리 가드 불일치**: 2파일 (lineup_tracker, movement_heatmap)에서 한도 enforcement 누락

**사용자 결정 대기**:
- **S9, S10** 즉시 처리 여부

**다음**: Phase 10F — `output/` 45파일 (shot_location/highlight/game_record/video_editing/film_session/coaching_intelligence/pre_game/scouting/matchup_analysis).

---

**감사자**: Claude (Opus 4.7)
**검토 완료**: 2026-04-20
