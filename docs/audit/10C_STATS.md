# Phase 10C — game_analysis/stats/ 감사 보고서

> **감사 범위**: `stats/` 14파일 (statistics 7 + predictive_models 4 + __init__ 3)
> **감사 방식**: Read 도구 전수 직독
> **감사 일자**: 2026-04-20
> **총 라인**: ~5,300 lines
> **역할**: Phase 1B 이벤트 소비 → 박스스코어/고급스탯/슛차트/트래킹/팀통계/점유효율/Four Factors 증분 산출 + WP/EPV/xFG/라인업 예측

---

## 0. 실행 요약

| 축 | 점수 | 핵심 관찰 |
|---|---|---|
| 1. Import 유효성 | 100 | 전 파일 `from __future__ import annotations`, 절대 임포트, `shared.constants.stats_constants` SSOT 활용 |
| 2. 기능 유효성 | 92 | Hollinger/Oliver/Goldsberry 학술 기반 정확. 단 **3pt 감지가 description 문자열 파싱** (fragile) |
| 3. 메모리 누수 | 94 | `_MAX_*_CACHE` 전 파일 trim, 단 `basic_stats._MAX_PLAYER_CACHE=100` 경고만 하고 무제한 증가 허용 |
| 4. 하드코딩 | 85 | `shared.constants.stats_constants` 광범위 참조. 단 6개 매직넘버/하드코딩 발견 |
| 5. 1줄 리뷰 | 100 | 한글 docstring, 학술 출처, 사용 예시 포함 |
| 6. 스레드 안전 | 100 | 전 클래스 RLock, public 진입 래핑 일관 |
| 7. 예외 처리 | 95 | 분모 0 방어, 클램핑, 공 입력 검증 — except 블록은 detector보다 적음 (stats는 예외 적음) |
| 8. 확장성 | 98 | 전 Config `from_yaml`, 14개 Calculator/Model 본체 `__slots__` 사용 (game_state 대비 우수) |
| **총평** | **94.0** | S-grade, Safe-Now 2건 + Phase 15 권고 4건 |

---

## 1. 모듈 구조

| 서브 | 파일 수 | 라인 합 | 역할 |
|---|---|---|---|
| `__init__.py` ×3 | 3 | 170 | 패키지/서브패키지 통합 export |
| `statistics/` | 7 | ~2,800 | 박스스코어·고급스탯·슛차트·트래킹·팀·점유·Four Factors |
| `predictive_models/` | 4 | ~1,770 | WP·EPV·xFG·라인업 예측 |

---

## 2. 축별 평가

### 2.1 축 1 — Import 유효성 (100/100)

- 14파일 전원 `from __future__ import annotations`
- `shared.constants.stats_constants`의 40+ 상수 SSOT 참조:
  - `POINTS_FREE_THROW/TWO_POINTER/THREE_POINTER`, `FREE_THROW_TRIP_FACTOR`, `THREE_POINT_EFG_BONUS`
  - `PER_ASSIST_FACTOR`, `PER_FREE_THROW_FACTOR`, `PER_LEAGUE_AVERAGE`, `NORMALIZATION_MINUTES_36`
  - `PPP_ELITE/GOOD/AVERAGE/POOR_THRESHOLD`, `POSSESSION_EARLY/MID_CLOCK_SEC`
  - `WP_CLUTCH/GARBAGE/POSSESSION/HOME_COURT` 파라미터
  - `CONTEST_DISTANCE_TIGHT/MODERATE/OPEN_M`, `CATCH_AND_SHOOT_MAX_TOUCH_SEC`
  - `FOUR_FACTORS_*_WEIGHT`, `SHOT_ZONE_*`, `ShotZone`, `StatCategory`, `PerformanceRating`
- 공통 함수 사용: `calculate_ts_pct`, `calculate_efg_pct`, `calculate_usg_pct`
- DTO 소비: `shared.dto.game_dto.PlayerStats/GameEvent`, `shared.dto.prediction_dto.*`

### 2.2 축 2 — 기능 유효성 (92/100)

**학술 근거**
- Hollinger (2005), Kubatko (2007) — PER, 고급 스탯
- Oliver (2004) — Four Factors, 점유 효율
- Goldsberry (2019) — 슛 차트 존 분류

**수식 정확성 검증**
- TS% = PTS / (2 × (FGA + 0.44 × FTA)) ✓
- eFG% = (FGM + 0.5 × 3PM) / FGA ✓
- USG% = Hollinger 공식 ✓
- TOV% = TOV / (FGA + 0.44×FTA + TOV) ✓
- OREB% = OREB / (OREB + OPP_DREB) ✓
- FT Rate = FTA / FGA ✓
- Possessions ≈ FGA - OREB + TOV + 0.44×FTA ✓
- Hollinger Game Score ✓
- Logistic WP = σ(k × margin / time_factor) ✓

**감점 (-8)**

- **Q1 (fragile)**: [basic_stats.py:277-287](game_analysis/stats/statistics/basic_stats.py#L277-L287), [team_stats_aggregator.py:307-309](game_analysis/stats/statistics/team_stats_aggregator.py#L307-L309) — 3pt 미스 감지를 `description` 문자열의 `"3pt"`/`"three"` 포함 여부로 판정:
  ```python
  if "3pt" in desc or "three" in desc.lower():
      acc.three_pointers_attempted += 1
  ```
  - Shot_event_detector의 description 포맷이 바뀌면 조용히 실패
  - `event.points == 3` 또는 전용 flag (`is_three_pointer`) 사용 필요 → **Safe-Now 후보**
- **Q2 (OT 미지원)**: 세 파일이 `quarter_scores = [0]*4` (정규 4쿼터만):
  - [basic_stats.py](game_analysis/stats/statistics/basic_stats.py) 간접 (PlayerStats DTO 통해)
  - [team_stats_aggregator.py:71](game_analysis/stats/statistics/team_stats_aggregator.py#L71), 300-301, 317-318
  - [possession_stats.py:178-179](game_analysis/stats/statistics/possession_stats.py#L178-L179), 277-280
  - `1 <= quarter <= 4`로 OT 방어되어 있으나 OT 점수는 카운트되지 않음 → 리포트에서 OT 누락
- **Q3 (overlap)**: [possession_stats.py:294-313](game_analysis/stats/statistics/possession_stats.py#L294-L313) — `fast_break`(≤7s)는 `early_offense`(≤10s)의 하위집합이지만 두 누적기에 **동시 누적**됨. 통계 합산 시 이중 계산 가능 (의도된 설계일 수 있으나 주석 부재)

### 2.3 축 3 — 메모리 누수 (94/100)

**우수**
- 전 파일 `_MAX_*_CACHE`, `_MAX_*_LOG`, `_MAX_*_HISTORY` 상수 + trim 로직
- 대부분 `del list[:trim]` (20% 배치 제거) 패턴
- `lineup_projection._trim_lineup_cache`는 **최소 출전시간 라인업 먼저 제거** (스마트 정리)

**감점 (-6)**

- **M3**: [basic_stats.py:437-441](game_analysis/stats/statistics/basic_stats.py#L437-L441) — `_MAX_PLAYER_CACHE=100` 초과 시 경고 로그만 출력하고 **여전히 추가**. 상한이 실제로 enforced 되지 않음:
  ```python
  if len(self._players) >= _MAX_PLAYER_CACHE:
      logger.warning("선수 캐시 최대치(%d) 도달, 새 선수 %d 추가", ...)
  # 그 후에도 계속 self._players[player_id] = acc
  ```
  - 무제한 선수 추가 가능 (예: 해커/버그 입력) → **Safe-Now 후보**

### 2.4 축 4 — 하드코딩 (85/100)

**우수**
- `stats_constants`의 40+ 상수 광범위 참조
- 존별 FG%는 `_ZONE_BASE_FG_PCT` 상수 + YAML 오버라이드 가능

**감점 (-15)**

- **H7**: [shot_chart.py:268](game_analysis/stats/statistics/shot_chart.py#L268) — 코트 좌표→거리 변환에 `* 15.0` (FIBA 코트 폭 15m) 하드코딩. `court_constants.FIBA_COURT_WIDTH_M` 참조 필요
- **H8**: [win_probability.py:62-63](game_analysis/stats/predictive_models/win_probability.py#L62-L63) — `_QUARTER_DURATION_SEC = 600`, `_OVERTIME_DURATION_SEC = 300` FIBA만 지원. NBA 12분 쿼터 적용 시 WP 산출 왜곡
- **H9**: [lineup_projection.py:43-44](game_analysis/stats/predictive_models/lineup_projection.py#L43-L44) — `_LEAGUE_AVG_ORTG = 108.0`, `_LEAGUE_AVG_DRTG = 108.0`, `_LEAGUE_AVG_NET_RATING = 0.0` — stats_constants로 승격 권고
- **H10**: [expected_possession_value.py:55-57](game_analysis/stats/predictive_models/expected_possession_value.py#L55-L57) — `_EARLY_CLOCK_BONUS=0.10`, `_MID_CLOCK_BONUS=0.0`, `_LATE_CLOCK_PENALTY=-0.08` — 모듈 상수, YAML 노출 안 됨
- **H11**: [win_probability.py:58-59](game_analysis/stats/predictive_models/win_probability.py#L58-L59) — `_LOGISTIC_K_BASE=0.15`, `_LOGISTIC_TIME_SCALE=2400.0` — 모델 핵심 파라미터이나 YAML 미노출
- **H12**: [shot_quality_model.py:51-72](game_analysis/stats/predictive_models/shot_quality_model.py#L51-L72) — `_ZONE_BASE_FG_PCT` 20개 값이 FIBA 평균. NBA/KBL 평균 다름 (딥3는 NBA 0.32 vs FIBA 0.25)

### 2.5 축 5 — 1줄 리뷰 (100/100)

- 파일 헤더 + 학술 근거 + Cadence 라벨 + 소비자 명시 일관
- 사용 예시 포함 (`>>> calc = ...`)

### 2.6 축 6 — 스레드 안전 (100/100)

- 14개 Calculator/Model 클래스 전원 RLock
- public 메서드 `with self._lock:` 래핑 일관

### 2.7 축 7 — 예외 처리 (95/100)

**우수**
- 분모 0 방어 (`if attempts <= 0: return 0.0`)
- 클램핑 (`max(min(exponent, 10.0), -10.0)` — sigmoid 오버플로 방지)
- Float 곱셈 오버플로 보호

**감점 (-5)**
- stats 모듈은 event_detection과 달리 `try/except` 최상위 래핑이 없음. 이벤트 처리 중 예외 발생 시 호출자 전파 — 의도적이라면 OK. 단 `basic_stats.process_event`는 broad try 없음 → 비정상 event가 전체 파이프라인 중단 가능

### 2.8 축 8 — 확장성 (98/100)

**우수**
- 전 Calculator/Model 본체 클래스 `__slots__` 적용 — game_state detector 대비 우수
- 전 Config `from_yaml` 팩토리 제공
- `ShotQualityConfig.zone_base_fg_pct`, `contest_adjustment` 등 dict를 YAML에서 오버라이드 가능
- 캐시 기반 증분 갱신 + 재계산 가능 (`get_cached`, `calculate`, `reset`)

---

## 3. 파일별 하이라이트

### 3.1 statistics/ (7)

| 파일 | 점수 | 비고 |
|---|---|---|
| `basic_stats.py` | 90 | 17항목 박스스코어 증분. **Q1 3pt 문자열 파싱**, **M3 캐시 약한 enforcement** |
| `advanced_stats.py` | 100 | PER/TS%/eFG%/USG%/ORtg/DRtg/GameScore/per-36 — 수식 정확 |
| `shot_chart.py` | 92 | 11존 분류 (RA, PAINT, 미드 3부위, 3점 7부위), **H7 15m 하드코딩** |
| `player_tracker_stats.py` | 100 | 이동거리/속도/스프린트/터치/컨테스트 FRAME 단위 누적 |
| `team_stats_aggregator.py` | 90 | 팀 박스 + 특수득점 (PIP/속공/세컨드찬스/벤치). **Q1, Q2 OT 미지원** |
| `possession_stats.py` | 90 | PPP 5등급, 타이밍 5구간 분류. **Q2 OT, Q3 중복 누적** |
| `four_factors.py` | 100 | eFG/TOV/OREB/FT Rate 가중 합산 + 팀 비교 어드밴티지 |

### 3.2 predictive_models/ (4)

| 파일 | 점수 | 비고 |
|---|---|---|
| `win_probability.py` | 88 | 로지스틱 WP + 클러치/가비지/모멘텀/레버리지. **H8 FIBA 하드코딩, H11 k/σ 미노출** |
| `expected_possession_value.py` | 92 | shot/drive/pass 옵션별 EPV + 의사결정 품질. **H10 clock bonus 미노출** |
| `shot_quality_model.py` | 92 | 20존 × 4컨테스트 × 10슛유형 xFG%. **H12 FIBA 평균 하드코딩** |
| `lineup_projection.py` | 94 | 피로/시너지/매치업/평균회귀 반영. **H9 리그 평균 상수** |

---

## 4. Safe-Now / Phase 15 분류

### 4.1 Safe-Now (즉시 처리 검토)

| 항목 | 파일:라인 | 조치 |
|---|---|---|
| **S6** | `basic_stats.py:277-287`, `team_stats_aggregator.py:307-309` | 3pt 감지 — description 문자열 파싱 제거. `event.points == 3` 또는 전용 flag 사용 |
| **S7** | `basic_stats.py:437-441` | `_MAX_PLAYER_CACHE` 실제 enforcement (로깅 후 `return None`으로 거부) |

### 4.2 Phase 15 (구조 리팩토링 시)

| 항목 | 파일 | 조치 |
|---|---|---|
| P10 | `team_stats_aggregator.py`, `possession_stats.py`, `basic_stats.py` | `quarter_scores` OT 확장 (가변 길이 + OT 슬롯) |
| P11 | `possession_stats.py:294-313` | fast_break vs early_offense 중복 누적 주석 추가 또는 배타적 분류 |
| P12 | `shot_chart.py:268`, `win_probability.py:62-63` | 코트 규격/쿼터 시간 SSOT 참조 (`court_constants`, `game_management_constants`) |
| P13 | `win_probability.py`, `expected_possession_value.py`, `lineup_projection.py` | 리그 평균 상수(ORtg 108, DRtg 108, 로지스틱 k/σ 등) `stats_constants` 승격 + YAML 노출 |

---

## 5. 통계

| 항목 | 값 |
|---|---|
| 총 파일 | 14 |
| 총 라인 | ~5,300 |
| `from __future__ import annotations` 적용률 | 100% |
| `@dataclass(slots=True)` DTO 수 | 25 |
| `__slots__` 적용 Calculator/Model | 11/11 |
| RLock 적용률 | 100% |
| `from_yaml` 팩토리 제공률 | 100% |
| `shared.constants.stats_constants` 참조 상수 수 | 40+ |
| 학술 근거 인용 파일 | 7 (Hollinger, Oliver, Kubatko, Goldsberry) |

---

## 6. 결론

Phase 10C — **S-grade (94.0/100)**.

**핵심 강점**:
- `shared.constants.stats_constants`의 광범위 SSOT 참조 — Phase 5 원칙 일관 준수
- 14개 클래스 모두 `__slots__` + RLock + `from_yaml` 일관 (game_state detector 대비 우수)
- Hollinger/Oliver/Goldsberry 수식을 교과서적으로 구현

**주요 약점**:
- 3pt 감지 문자열 파싱 (S6) — 가장 취약한 기능 이슈
- FIBA 하드코딩된 리그 평균 (NBA 대응 미비)
- 4쿼터 고정 구조 (OT 미지원)

**사용자 결정 대기**:
- **S6, S7** 즉시 처리 여부

**다음**: Phase 10D — `analysis/team/` ~24파일 (tactical/defensive/transition/play_type).

---

**감사자**: Claude (Opus 4.7)
**검토 완료**: 2026-04-20
