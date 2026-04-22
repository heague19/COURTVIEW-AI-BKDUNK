# Phase 15 세션 6 — M4 Config 가중치 승격 + M5 리그별 Config 분기

**실행일**: 2026-04-20
**범위**: Tier 3 Medium M4 + M5 (Config 확장)
**결과**: **4개 Config 확장, 3파일 수정, 런타임 검증 통과**

---

## 1. 실행 내역

### ✅ M4-1. `foul_severity_analyzer` 5요소 가중치 → RuleParameters Config

**파일**: [ai_referee/fouls/foul_severity_analyzer.py](ai_referee/fouls/foul_severity_analyzer.py)

**변경**:
- 모듈 상수 `_WEIGHT_*` (5종) → `_DEFAULT_WEIGHT_*` 로 이름 변경 (기본값 의미 명시)
- `RuleParameters` 경유 Config 노출:
  - `severity_analysis.weight_impact` (기본 0.30)
  - `severity_analysis.weight_body_part` (기본 0.25)
  - `severity_analysis.weight_intent` (기본 0.20)
  - `severity_analysis.weight_vulnerability` (기본 0.15)
  - `severity_analysis.weight_game_context` (기본 0.10)
- 종합 점수 계산: `impact_score * self._w_impact + ... ` (인스턴스 속성 경유)

### ✅ M4-2. `CoachReportConfig` 종합 점수 가중치 필드 추가

**파일**: [feedback_system/report/coach_report_generator.py](feedback_system/report/coach_report_generator.py)

**변경**:
```python
@dataclass(slots=True)
class CoachReportConfig:
    # ... 기존 필드 ...

    # 종합 점수 가중치 (motion + biomech, 합계 1.0) — Phase 15 M4
    motion_score_weight: float = 0.60
    biomech_score_weight: float = 0.40
```

- `_calculate_overall_score` 에서 `cfg.motion_score_weight` / `cfg.biomech_score_weight` 사용

### ✅ M4-3. `GameReportConfig` 5요소 가중치 필드 추가

**파일**: [feedback_system/report/game_report_generator.py](feedback_system/report/game_report_generator.py)

**변경**:
```python
# === 종합 점수 5요소 가중치 (합계 1.0) — Phase 15 M4 ===
efg_weight: float = 0.35             # 유효 야투율
assist_weight: float = 0.20          # 어시스트율
turnover_weight: float = 0.20        # 턴오버율 (역)
rebound_weight: float = 0.15         # 리바운드
win_weight: float = 0.10             # 승리 보너스
```

- `_calculate_overall_score` 에서 `cfg.efg_weight * efg_score + ...` 5요소 Config 경유

### ✅ M5. `GameFeedbackConfig.for_league()` factory 추가

**파일**: [feedback_system/analysis/game_feedback.py](feedback_system/analysis/game_feedback.py)

**변경**:
- `from shared.constants.referee_rule_constants import RuleSet` import 추가
- Factory classmethod `for_league(rule_set)` 추가 — 리그별 Four Factors 평균 프리셋

**리그별 평균 프리셋**:

| 리그 | eFG% | TOV% | ORB% | FT% |
|---|---|---|---|---|
| **FIBA** (기본) | 50.0 | 14.0 | 25.0 | 22.0 |
| **NBA** | 54.0 | 13.0 | 24.0 | 22.0 |
| **KBL** | 49.0 | 15.0 | 26.0 | 24.0 |
| **NBL** | 48.0 | 13.0 | 25.0 | 22.0 |

**사용**:
```python
# FIBA 기본 (기존 호환)
cfg = GameFeedbackConfig()

# NBA 리그 분기
cfg = GameFeedbackConfig.for_league(RuleSet.NBA)
```

---

## 2. 런타임 검증

```python
# M5 리그별 분기 검증
>>> GameFeedbackConfig.for_league(RuleSet.FIBA)
(eFG=50.0, TOV=14.0, ORB=25.0, FT=22.0)
>>> GameFeedbackConfig.for_league(RuleSet.NBA)
(eFG=54.0, TOV=13.0, ORB=24.0, FT=22.0)
>>> GameFeedbackConfig.for_league(RuleSet.KBL)
(eFG=49.0, TOV=15.0, ORB=26.0, FT=24.0)
>>> GameFeedbackConfig.for_league(RuleSet.NBL)
(eFG=48.0, TOV=13.0, ORB=25.0, FT=22.0)

# M4 가중치 합계 검증
>>> CoachReportConfig().motion_score_weight + CoachReportConfig().biomech_score_weight
1.0

>>> sum of 5 weights in GameReportConfig:
1.0
```

**결과**: ✅ 모든 리그 분기 + 모든 가중치 합계 1.0 검증 통과

---

## 3. 영향 범위

| 디렉토리 | 파일 수 |
|---|---|
| `ai_referee/fouls/` | 1 (foul_severity_analyzer.py) |
| `feedback_system/analysis/` | 1 (game_feedback.py) |
| `feedback_system/report/` | 2 (coach_report_generator + game_report_generator) |
| **합계** | **4파일** |

### 호환성

- **Breaking change**: **없음**
  - 기존 Config 기본값은 원래 하드코딩 값과 동일 (0.60/0.40, 0.35/0.20/0.20/0.15/0.10, 0.30/0.25/0.20/0.15/0.10)
  - `GameFeedbackConfig()` 기본 생성자 FIBA 기본값 유지 — `for_league()` 는 선택적 factory
  - `RuleParameters.severity_analysis.weight_*` 키가 YAML에 없으면 기본값 사용 (기존 동작 그대로)

---

## 4. YAML Config 경로 예시

**M4-1 (foul_severity_analyzer)**:
```yaml
# configs/ai_referee/foul_criteria.yaml
severity_analysis:
  light_threshold: 8.0
  moderate_threshold: 15.0
  hard_threshold: 25.0
  # 5요소 가중치 (신규, Phase 15 M4)
  weight_impact: 0.30
  weight_body_part: 0.25
  weight_intent: 0.20
  weight_vulnerability: 0.15
  weight_game_context: 0.10
```

**M4-2/3 (CoachReport/GameReport)**:
현재는 Python 생성자 파라미터로 조정 가능. 장기적으로 YAML 기반 Config 로드 체계 도입 시 반영.

**M5 (GameFeedback)**:
```python
# api_server/services/game_service.py 등에서
cfg = GameFeedbackConfig.for_league(rule_set=RuleSet.KBL)
```

---

## 5. Phase 15 누적 진행도

| 세션 | Tier | 처리 건수 | 파일 변경 |
|---|---|---|---|
| 1 | Tier 1 + Tier 4 | 9 | 24 |
| 2 | Tier 3 M1 | 10 | 4 |
| 3 | Tier 5 | 7 | 5 |
| 4 | Tier 3 M2 | 31 | 32 |
| 5 | Tier 3 M3 | 26 | 29 |
| **6** | **Tier 3 M4+M5** | **4** | **4** |
| **합계** | — | **87** | **98** |

### 남은 Phase 15 작업 (6건, 모두 Tier 2 High)

| ID | 작업 | 예상 작업량 |
|---|---|---|
| H1 | `motion_analysis/phase_analysis/` → `biomechanics/phase_analysis/` | 중 (파일 이동 + import 교체) |
| H2 | `motion_analysis/form_evaluation/` → `feedback_system/form_evaluation/` | 중 |
| H3 | `motion_analysis/comparison/` → `feedback_system/comparison/` | 소 |
| H4 | Facade 5개 engine 연동 구현 | 중 (engine 통합 테스트 완료 의존) |
| H5 | shared.constants SSOT 확립 (GRAVITY/HOOP_RADIUS/CourtDimensions 등) | 대 (utils/configs 다중 중복 제거) |
| H6 | korean_templates.py 1,630줄 분할 | 대 |

**Tier 3 Medium 완전 완료** ✓ (M1-M5 전량 처리)

---

## 6. 다음 세션 제안

**세션 7 권장**: Tier 2 High **H5 (shared.constants SSOT 확립)**

- **이유**: 다른 H-tier 리팩토링의 기반 (코드 이전 전 SSOT 먼저 확립이 안전)
- **작업**:
  - `utils/physics_utils` + `utils/basketball_geometry` + `utils/geometry_utils` 의 GRAVITY/HOOP_RADIUS/CourtDimensions 중복 → `shared/constants/` 로 일원화
  - `utils/time_utils.QUARTER_DURATION_*` → `shared/constants/game_rule_constants`
  - `utils/video_utils.SUPPORTED_*_EXTENSIONS` → `shared/constants/`
  - 각 소스 파일은 SSOT re-export 방식으로 전환 (하위 호환 유지)
- **예상 파일**: ~15 (utils 4+ shared 2+ re-export 위주)
- **예상 시간**: 60분

**대안 1**: **H6 korean_templates.py 분할** (독립 작업, ~90분)

**대안 2**: **H1/H2/H3 일괄** (motion_analysis → biomechanics/feedback_system, ~60분)

---

**세션 6 완료. Tier 3 Medium 전량 완료 (M1-M5). Breaking change 없음.**
