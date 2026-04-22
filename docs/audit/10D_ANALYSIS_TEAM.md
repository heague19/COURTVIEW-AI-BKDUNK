# Phase 10D — game_analysis/analysis/team/ 감사 보고서

> **감사 범위**: `analysis/team/` 25파일 (tactical 6+1 / defensive 5+1 / transition 3+1 / play_type 6+1 / team 1)
> **감사 방식**: Read 도구 전수 직독
> **감사 일자**: 2026-04-20
> **총 라인**: ~6,600 lines
> **역할**: POSSESSION cadence(<100ms) 팀 전술/수비/전환/플레이 유형별 심층 분석

---

## 0. 실행 요약

| 축 | 점수 | 핵심 관찰 |
|---|---|---|
| 1. Import 유효성 | 100 | 전 파일 `from __future__ import annotations`, `shared.constants.tactical_constants` 일관 참조 |
| 2. 기능 유효성 | 88 | **버그 1건**: 4개 파일 `from_yaml`에서 `cls.attr` 접근 (slots+dataclass 조합에서 TypeError) |
| 3. 메모리 누수 | 98 | `_MAX_RECORDS` 한도 도달 시 **경고+거부** 패턴 우수 (basic_stats 이전 버그 없음) |
| 4. 하드코딩 | 90 | `tactical_constants` 광범위 참조. 단 `defense_type_classifier.py:400` FIBA 코트 폭 하드코딩 |
| 5. 1줄 리뷰 | 100 | 한글 docstring + 학술 출처(Lamas, Fewell, Clemente, Oliver, Kubatko) + Cadence 라벨 |
| 6. 스레드 안전 | 100 | 전 분석기 RLock, public 래핑 일관 |
| 7. 예외 처리 | 90 | 분모 0 방어 / 클램핑 우수. 단 `from_yaml` cls.attr 패턴의 TypeError 미처리 |
| 8. 확장성 | 80 | **설계 불일치**: 25개 Analyzer 중 11개만 `from_yaml` 제공, 14개 미제공 (game_state/stats 대비 후퇴) |
| **총평** | **93.2** | S-grade, Safe-Now 1건 (4파일 버그) + Phase 15 권고 4건 |

---

## 1. 모듈 구조

| 서브 | 파일 수 | 라인 합 | 주요 역할 |
|---|---|---|---|
| `team/__init__.py` | 1 | 13 | 패키지 루트 |
| `tactical_analysis/` | 7 | ~1,900 | PnR/속공/세트플레이/패싱/점유/턴오버 |
| `defensive_analysis/` | 6 | ~1,900 | 수비스킴/로테이션/박스아웃/클로즈아웃/헬프 |
| `transition_analysis/` | 4 | ~700 | 전환공격/전환수비/전환효율 |
| `play_type_analysis/` | 7 | ~1,400 | PnR/ISO/포스트업/스팟업/자유투/유형효율 |

**전체 Analyzer 클래스 20개 + Config 20개 + 15개 Enum + 20개 Record dataclass**

---

## 2. 🔴 핵심 발견: `cls.attr` 슬롯 접근 버그 (S8)

### 2.1 영향 범위

| # | 파일 | 라인 | 영향받는 필드 |
|---|---|---|---|
| 1 | `tactical_analysis/screen_analyzer.py` | 128-138 | 9개 필드 (contact_distance_m, angle_min_deg, ...) |
| 2 | `tactical_analysis/fast_break_analyzer.py` | 88-95 | 5개 필드 (primary_break_max_sec, ...) |
| 3 | `tactical_analysis/set_play_recognizer.py` | 65-67 | 3개 필드 (min_confidence, temporal_window_sec, top_plays_count) |
| 4 | `tactical_analysis/possession_analyzer.py` | 112-114 | 3개 필드 (fast_tempo_sec, slow_tempo_sec, halfcourt_set_sec) |

### 2.2 버그 메커니즘

```python
@dataclass(slots=True)
class ScreenAnalyzerConfig:
    contact_distance_m: float = SCREEN_CONTACT_DISTANCE_M  # 0.5m

    @classmethod
    def from_yaml(cls, cfg: dict) -> ScreenAnalyzerConfig:
        screen = cfg.get("screen", {})
        return cls(
            contact_distance_m=float(screen.get(
                "contact_distance_m",
                cls.contact_distance_m,  # ⚠️ 슬롯 디스크립터 반환
            )),
        )
```

**문제**:
- `@dataclass(slots=True)`는 클래스 레벨 기본값을 슬롯 디스크립터로 대체
- `cls.contact_distance_m`는 `<member 'contact_distance_m' of 'ScreenAnalyzerConfig' objects>` 반환
- `float(<member>)` → `TypeError: float() argument must be a string or a real number, not 'member_descriptor'`

**재현 시나리오**: YAML에 `pick_and_roll.screen.contact_distance_m` 키가 없을 때 (빈 dict 전달 포함) 전체 `from_yaml` 호출 실패 → `ScreenAnalyzer.from_yaml({})` 예외 → 상위 모듈 초기화 실패 가능.

### 2.3 수정 방법 (2가지 옵션)

**옵션 A** (권장): 모듈 상수 참조
```python
contact_distance_m=float(screen.get("contact_distance_m", SCREEN_CONTACT_DISTANCE_M)),
```

**옵션 B**: 기본 인스턴스 생성 후 오버라이드
```python
@classmethod
def from_yaml(cls, cfg: dict) -> ScreenAnalyzerConfig:
    defaults = cls()
    return cls(
        contact_distance_m=float(screen.get("contact_distance_m", defaults.contact_distance_m)),
        ...
    )
```

→ **Safe-Now 후보 S8** (4파일, 20필드 수정)

---

## 3. 축별 평가

### 3.1 축 1 — Import 유효성 (100/100)

- 25파일 전원 `from __future__ import annotations`
- `shared.constants.tactical_constants` 30+ 상수 참조:
  - `SCREEN_*`, `PNR_*`, `FAST_BREAK_*`, `PRIMARY/SECONDARY_BREAK_*`
  - `DRIVE_*`, `HAND_OFF_*`, `TEMPO_*`, `HALFCOURT_SET_*`
  - `MATCHUP_ASSIGNMENT_DISTANCE_M`, `DEFENSIVE_BREAKDOWN_DISTANCE_M`
  - `HELP_DEFENSE_*`, `HELP_RECOVERY_*`, `CLOSEOUT_*`, `BOX_OUT_*`
  - `DEFENSIVE_TRANSITION_TARGET_SEC`
- DTO 소비: `tactical_dto.*`, `game_rule_constants.PlayType`
- 순환 없음

### 3.2 축 2 — 기능 유효성 (88/100)

**우수**
- 학술 근거:
  - Lamas et al. (2011) — 세트 플레이 분류 (screen/set_play)
  - Fewell et al. (2012), Clemente et al. (2015) — 패싱 네트워크
  - Oliver (2004), Kubatko (2007) — 점유 효율
- 14종 세트 플레이, 18종 턴오버 원인, 10종 스킴, 5종 수비 대응 등 체계적 열거
- DTO 생성 로직 (`get_team_analysis` → `PickAndRollAnalysis`/`FastBreakAnalysis`/...) 일관

**감점 (-12)**
- **B1 (S8)**: 4파일 `cls.attr` 버그 (위 2절 참조)

### 3.3 축 3 — 메모리 누수 (98/100)

**우수 패턴** (Phase 10C basic_stats 이전 문제 해결됨):
```python
with self._lock:
    if len(self._records) >= self._config.max_records:
        logger.warning("XXX 기록 한도 도달 (%d), 이후 기록 무시", ...)
        return
    self._records.append(rec)
```

- 이벤트/기록 한도 도달 시 **경고 후 거부** — `return None`/`return False` 명시
- 18개 Analyzer에서 동일 패턴 일관 적용
- `_trim_records` 대안 있는 파일 (screen/fast_break 등): `list[-max:]` 슬라이스 기반

**감점 (-2)**
- `screen_analyzer._event_history` 및 유사 파일들은 `trim` 방식 사용 — 오래된 기록 드롭. 한도 도달 시 데이터 정확성보다 최신성 우선 (의도된 트레이드오프이나 명시 주석 없음)

### 3.4 축 4 — 하드코딩 (90/100)

**우수**
- `tactical_constants` 광범위 참조 (30+ 상수)
- Config dataclass 기본값 전원 `shared.constants.*` 상수 사용

**감점 (-10)**
- **H13**: [defense_type_classifier.py:400-401](game_analysis/analysis/team/defensive_analysis/defense_type_classifier.py#L400-L401) — `court_length = 28.0`, `court_width = 15.0` FIBA 하드코딩:
  ```python
  court_width = 15.0  # FIBA 코트 폭
  half_width = court_width / 2.0
  ```
  `court_constants.FIBA_COURT_WIDTH_M` 참조 필요 (기 정의됨, Phase 10C H7과 동일 패턴)
- **H14**: 12개 zone 패턴 (`_ZONE_PATTERNS`)의 좌표값 하드코딩 — FIBA 하프코트 기반 가정. 다양한 리그 지원 시 YAML 노출 권고

### 3.5 축 5 — 1줄 리뷰 (100/100)

- 헤더 일관 포맷 + Cadence 라벨 (🟢 POSSESSION / 🔵 POSSESSION 혼재)
- 학술 출처 기재 일관

### 3.6 축 6 — 스레드 안전 (100/100)

- 20개 Analyzer 전원 `self._lock = RLock()` ✓
- 20개 클래스 전원 `__slots__` 선언 — **game_state detector 대비 우수**
- 조회 메서드도 일관되게 `with self._lock:` 래핑

### 3.7 축 7 — 예외 처리 (90/100)

**우수**
- 분모 0 방어 일관 (`if attempts == 0: return 0.0`)
- 선수/팀 미존재 시 빈 dict/list 반환
- Confidence 미달 시 `return False`

**감점 (-10)**
- B1 (S8) 연관: `from_yaml`의 `cls.attr` 접근이 TypeError를 유발하지만 `try/except` 없음 → 외부 초기화 실패 전파

### 3.8 축 8 — 확장성 (80/100)

**설계 불일치 발견**:

| 서브 | `from_yaml` 있음 | 없음 |
|---|---|---|
| tactical_analysis/ | 6/6 (단, 4개는 버그 포함) | 0 |
| defensive_analysis/ | 1/5 (defense_type_classifier) | 4 (rotation, box_out, closeout, help_recovery) |
| transition_analysis/ | 0/3 | 3 (offense, defense, efficiency) |
| play_type_analysis/ | 0/6 | 6 (pick_and_roll, iso, post_up, spot_up, free_throw, efficiency) |

**14/25 파일이 YAML 오버라이드 불가**:
- Config는 모듈 상수 기반 기본값만 허용
- 외부 구성 주입 불가 → 테스트/튜닝 용이성 저하
- 이전 모듈들 (game_state/stats)에서는 `from_yaml` 일관 제공 → **Phase 15 리팩토링 권고**

---

## 4. 파일별 하이라이트

### 4.1 tactical_analysis/ (6+1)

| 파일 | 점수 | 비고 |
|---|---|---|
| `screen_analyzer.py` | 85 | 7종 PnR 대응 + 5종 액션. **B1 버그 (9필드)** |
| `fast_break_analyzer.py` | 85 | 7종 속공 유형 (1v0~secondary). **B1 버그 (5필드)** |
| `set_play_recognizer.py` | 85 | 14종 세트 플레이 + PPP. **B1 버그 (3필드)** |
| `passing_network.py` | 95 | 볼 무브먼트 레이팅 (볼륨/다양성/어시스트). `from_yaml` no-op |
| `possession_analyzer.py` | 85 | 6종 점유 유형 + 슛클락 구간. **B1 버그 (3필드)** |
| `turnover_analyzer.py` | 95 | 18종 원인 + POT + 선수별. `from_yaml` no-op |

### 4.2 defensive_analysis/ (5+1)

| 파일 | 점수 | 비고 |
|---|---|---|
| `defense_type_classifier.py` | 93 | 10종 스킴 + 존 패턴 매칭. **H13 (FIBA 하드코딩)** |
| `defensive_rotation.py` | 100 | 로테이션 품질 3축 (성공률/시간/브레이크다운) |
| `box_out_analyzer.py` | 100 | 박스아웃 vs 無 리바운드 비교 |
| `closeout_analyzer.py` | 100 | 오버클로즈아웃 감지 (속도+거리) |
| `help_recovery.py` | 100 | 헬프→리커버리 품질 3축 |

### 4.3 transition_analysis/ (3+1)

| 파일 | 점수 | 비고 |
|---|---|---|
| `transition_offense.py` | 100 | 1차/2차/얼리오펜스 3 페이즈 분류 |
| `transition_defense.py` | 100 | 복귀 시간 + 미복귀 페널티 |
| `transition_efficiency.py` | 100 | 전환 vs 하프코트 PPP 비교 + DTO |

### 4.4 play_type_analysis/ (6+1)

| 파일 | 점수 | 비고 |
|---|---|---|
| `pick_and_roll.py` | 100 | 역할(3종) × 수비(6종) 교차 |
| `isolation_analyzer.py` | 100 | 5종 결과 유형 + 선수별 분해 |
| `post_up_analyzer.py` | 100 | 7종 기술 유형 (hook/fade/drop_step/...) |
| `spot_up_analyzer.py` | 100 | 3종 컨테스트 레벨 비교 |
| `free_throw_analyzer.py` | 100 | 5종 상황 (normal/and_one/tech/flagrant/clutch) + 루틴 시간 |
| `play_type_efficiency.py` | 100 | 유형별 순위 + PlayTypeData DTO |

---

## 5. Safe-Now / Phase 15 분류

### 5.1 Safe-Now (즉시 처리 검토)

| 항목 | 파일:라인 | 조치 |
|---|---|---|
| **S8** | `screen_analyzer.py:128-138`, `fast_break_analyzer.py:88-95`, `set_play_recognizer.py:65-67`, `possession_analyzer.py:112-114` | `cls.attr` → 모듈 상수 직접 참조 (옵션 A) 또는 `defaults = cls()` 패턴 (옵션 B) |

### 5.2 Phase 15 (구조 리팩토링 시)

| 항목 | 파일 | 조치 |
|---|---|---|
| P14 | `defense_type_classifier.py:400-401` | FIBA 코트 규격 SSOT(`court_constants`) 참조 |
| P15 | 14개 Analyzer (defensive/transition/play_type) | `from_yaml` 팩토리 추가로 일관성 복원 |
| P16 | `defense_type_classifier._ZONE_PATTERNS` | 존 패턴 YAML 노출 (다양한 리그 대응) |
| P17 | `screen_analyzer`, `fast_break_analyzer` 등 | history 관리 `trim` 방식 주석 추가 (데이터 손실 의도 명시) |

---

## 6. 통계

| 항목 | 값 |
|---|---|
| 총 파일 | 25 |
| 총 라인 | ~6,600 |
| `from __future__ import annotations` 적용률 | 100% |
| `@dataclass(slots=True)` DTO/Record/Config 수 | 52 |
| `__slots__` 적용 Analyzer 수 | 20/20 (100%) |
| RLock 적용률 | 100% (20/20) |
| `from_yaml` 팩토리 제공률 | **44%** (11/25, game_state·stats 대비 후퇴) |
| `from_yaml` 중 버그 있는 파일 | **4** (S8) |
| `shared.constants.tactical_constants` 참조 상수 | 30+ |
| 학술 근거 인용 파일 | 10+ |

---

## 7. 결론

Phase 10D — **S-grade (93.2/100)**.

**핵심 강점**:
- 20개 Analyzer 전원 `__slots__` + RLock + 메모리 가드 (basic_stats 이전 버그 패턴 없음)
- 14종 세트 플레이, 18종 턴오버, 10종 수비 스킴 등 체계적 열거
- `shared.constants.tactical_constants` 광범위 SSOT 참조

**핵심 약점**:
- **S8 (슬롯 + cls.attr 버그)**: 4파일, 20필드 — YAML 키 누락 시 TypeError
- **확장성 불일치**: 14/25 파일 `from_yaml` 미제공 (이전 모듈 대비 후퇴)

**사용자 결정 대기**:
- **S8** 즉시 처리 여부 (4파일 일괄 수정)

**다음**: Phase 10E — `analysis/player/` + `analysis/context/` ~44파일 (individual/lineup/rotation/spatial/game_flow/splits/special/season).

---

**감사자**: Claude (Opus 4.7)
**검토 완료**: 2026-04-20
