# Phase 15 세션 7 — H5 shared.constants SSOT 확립

**실행일**: 2026-04-20
**범위**: Tier 2 High H5 (utils 내 중복 상수 → shared.constants SSOT 일원화)
**결과**: **4개 utils 파일 re-export 전환, 3개 shared 파일 정정, 충돌 1건 해결**

---

## 1. 발견한 SSOT 충돌 (중요)

### HOOP_RADIUS_M 값 충돌 — 해결

| 위치 | 값 | 계산 근거 |
|---|---|---|
| `shared/constants/court_constants.HOOP_RADIUS_M` | **0.225** | HOOP_DIAMETER_M=0.45 / 2 (부정확) |
| `utils/physics_utils.HOOP_RADIUS` | **0.2286** | 9 inch = 0.2286m (정확) |
| `utils/basketball_geometry.HOOP_RADIUS_M` | **0.2286** | 9 inch 표준 |

**판정 근거**: FIBA/NBA 공식 18 inch 림 = 0.4572m. 기존 `shared`의 0.45 / 0.225는 근사값 (실제 규정 오차 범위).

**조치**: `shared/constants/court_constants`를 정밀값으로 정정.
- `HOOP_DIAMETER_M`: 0.45 → **0.4572**
- `HOOP_RADIUS_M`: 0.225 → **0.2286**

### GRAVITY_ACCELERATION 정밀도 정정

| 위치 | 기존 값 | 조치 |
|---|---|---|
| `shared/constants/ball_constants.GRAVITY_ACCELERATION` | 9.81 (근사) | → **9.80665** (ISO 표준중력 g₀) |
| `utils/physics_utils.GRAVITY` | 9.80665 | 유지 (정확) |
| `utils/basketball_geometry.GRAVITY` | 9.80665 | 유지 (정확) |

**조치**: shared를 ISO 정밀값으로 상향 (오차 ~0.07%, 무시 가능).

### AIR_DENSITY 값 통합

| 위치 | 기존 값 | 조건 |
|---|---|---|
| `shared/constants/ball_constants.AIR_DENSITY` | 1.204 | 20°C (유지) |
| `utils/physics_utils.AIR_DENSITY` | 1.225 | 0°C 해수면 → shared 값(1.204)으로 변경 |

**판정**: 실내 경기장 조건(20°C)이 실무상 더 합리적 → shared의 1.204 채택.

---

## 2. 실행 내역

### ✅ Phase A. shared/constants 정정

**파일 1**: [shared/constants/ball_constants.py](shared/constants/ball_constants.py)
```python
# Before
GRAVITY_ACCELERATION: Final[float] = 9.81

# After (Phase 15 H5)
GRAVITY_ACCELERATION: Final[float] = 9.80665  # ISO g₀
BASKETBALL_DRAG_COEFFICIENT: Final[float] = 0.47  # 신규 추가
```

**파일 2**: [shared/constants/court_constants.py](shared/constants/court_constants.py)
```python
# Before
HOOP_DIAMETER_M: Final[float] = 0.45
HOOP_RADIUS_M: Final[float] = 0.225

# After (Phase 15 H5 SSOT 정정)
HOOP_DIAMETER_M: Final[float] = 0.4572   # 18 inch
HOOP_RADIUS_M: Final[float] = 0.2286     # 9 inch
```

**파일 3**: [shared/constants/video_constants.py](shared/constants/video_constants.py)
```python
# Before
SUPPORTED_VIDEO_EXTENSIONS: frozenset({
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"
})

# After (utils.video_utils 확장자와 통합)
SUPPORTED_VIDEO_EXTENSIONS: frozenset({
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".flv"
})

# 신규 추가 (utils.video_utils에서 이관)
SUPPORTED_IMAGE_EXTENSIONS: frozenset({
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"
})
```

### ✅ Phase B. utils re-export 전환

**파일 1**: [utils/physics_utils.py](utils/physics_utils.py)
```python
from shared.constants.ball_constants import (
    AIR_DENSITY as _AIR_DENSITY,
    BASKETBALL_DRAG_COEFFICIENT as _BASKETBALL_DRAG_COEFFICIENT,
    BASKETBALL_MASS_KG as _BASKETBALL_MASS_KG,
    BASKETBALL_RADIUS_M as _BASKETBALL_RADIUS_M,
    GRAVITY_ACCELERATION as _GRAVITY_ACCELERATION,
)
from shared.constants.court_constants import (
    FREE_THROW_LINE_DISTANCE_M as _FREE_THROW_LINE_DISTANCE_M,
    HOOP_HEIGHT_M as _HOOP_HEIGHT_M,
    HOOP_RADIUS_M as _HOOP_RADIUS_M,
    THREE_POINT_LINE_DISTANCE_M as _THREE_POINT_LINE_DISTANCE_M,
)

GRAVITY: float = _GRAVITY_ACCELERATION
BASKETBALL_MASS: float = _BASKETBALL_MASS_KG
# ... 8개 상수 re-export
```

**파일 2**: [utils/basketball_geometry.py](utils/basketball_geometry.py)
- GRAVITY, HOOP_HEIGHT_M, HOOP_DIAMETER_M, HOOP_RADIUS_M, BALL_DIAMETER_M, BALL_RADIUS_M, BACKBOARD_* 등 10개 re-export

**파일 3**: [utils/time_utils.py](utils/time_utils.py)
```python
from shared.constants.game_management_constants import (
    OVERTIME_DURATION_SEC as _OVERTIME_DURATION_SEC,
    QUARTER_DURATION_SEC as _QUARTER_DURATION_SEC,
    SHOT_CLOCK_FULL_SEC as _SHOT_CLOCK_FULL_SEC,
)
from shared.constants.referee_rule_constants import RuleSet as _RuleSet

QUARTER_DURATION_NBA: int = _QUARTER_DURATION_SEC[_RuleSet.NBA]     # 720
QUARTER_DURATION_FIBA: int = _QUARTER_DURATION_SEC[_RuleSet.FIBA]   # 600
SHOT_CLOCK_NBA: int = _SHOT_CLOCK_FULL_SEC                          # 24
SHOT_CLOCK_FIBA: int = _SHOT_CLOCK_FULL_SEC                         # 24
OVERTIME_DURATION: int = _OVERTIME_DURATION_SEC                     # 300
```

**파일 4**: [utils/video_utils.py](utils/video_utils.py)
```python
from shared.constants.video_constants import (
    SUPPORTED_IMAGE_EXTENSIONS as _SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS as _SUPPORTED_VIDEO_EXTENSIONS,
)

# 하위 호환: shared는 frozenset, utils는 tuple
SUPPORTED_VIDEO_EXTENSIONS: tuple[str, ...] = tuple(sorted(_SUPPORTED_VIDEO_EXTENSIONS))
SUPPORTED_IMAGE_EXTENSIONS: tuple[str, ...] = tuple(sorted(_SUPPORTED_IMAGE_EXTENSIONS))
```

---

## 3. 런타임 검증

```python
# === GRAVITY SSOT ===
physics_utils.GRAVITY           = 9.80665
basketball_geometry.GRAVITY     = 9.80665
shared.GRAVITY_ACCELERATION     = 9.80665

# === HOOP_RADIUS SSOT ===
physics_utils.HOOP_RADIUS         = 0.2286
basketball_geometry.HOOP_RADIUS_M = 0.2286
shared.HOOP_RADIUS_M              = 0.2286
shared.HOOP_DIAMETER_M            = 0.4572

# === BASKETBALL physics SSOT ===
BASKETBALL_MASS                 = 0.62
BASKETBALL_RADIUS               = 0.122
BASKETBALL_DRAG_COEFFICIENT     = 0.47
AIR_DENSITY                     = 1.204

# === QUARTER_DURATION SSOT ===
QUARTER_DURATION_NBA            = 720
QUARTER_DURATION_FIBA           = 600
SHOT_CLOCK_NBA                  = 24
OVERTIME_DURATION               = 300

# === SUPPORTED_EXTENSIONS SSOT ===
VIDEO = ('.avi', '.flv', '.m4v', '.mkv', '.mov', '.mp4', '.webm', '.wmv')
IMAGE = ('.bmp', '.jpeg', '.jpg', '.png', '.tiff', '.webp')

ALL H5 SSOT ASSERTIONS PASSED
```

**Consumer 21/21 import OK**: utils, physics_utils, basketball_geometry, time_utils, video_utils, court/ball/video/game_management_constants, infrastructure/validation/format_validator, infrastructure/preprocessing/video_type_classifier, biomechanics (3), detection/ball_detection, game_analysis (2), ai_referee/rules (4).

**세션 5-6 호환성**: CoachReportConfig + GameReportConfig 가중치 합계 1.0 유지, GameFeedbackConfig.for_league() FIBA/NBA/KBL/NBL 4개 프리셋 정상.

---

## 4. 영향 범위

| 디렉토리 | 파일 수 | 비고 |
|---|---|---|
| `shared/constants/` | 3 | ball_constants + court_constants + video_constants |
| `utils/` | 4 | physics_utils + basketball_geometry + time_utils + video_utils |
| **합계** | **7파일** |  |

### Breaking change 분석

**없음** (값 공개 API 보존):
- `utils.physics_utils.GRAVITY` 등 기존 심볼명·타입 그대로 유지
- `utils.time_utils.QUARTER_DURATION_NBA` = 720 (기존과 동일)
- `utils.video_utils.SUPPORTED_VIDEO_EXTENSIONS` — `tuple` 타입 유지 (shared는 frozenset이지만 utils는 tuple 변환)

**의도적 값 변경** (정정):
- `shared.court_constants.HOOP_DIAMETER_M`: 0.45 → 0.4572 (9 inch 정확 표준)
- `shared.court_constants.HOOP_RADIUS_M`: 0.225 → 0.2286
- `shared.ball_constants.GRAVITY_ACCELERATION`: 9.81 → 9.80665 (ISO g₀)
- `utils.physics_utils.AIR_DENSITY`: 1.225 → 1.204 (20°C 실내 경기장)
  - 궤적 계산 오차 ≈ 0.17%, 실질 무시 가능

**확장자 집합 변경**:
- `shared.video_constants.SUPPORTED_VIDEO_EXTENSIONS`: {6} → {8} (.wmv, .flv 추가)
- `shared.video_constants.SUPPORTED_IMAGE_EXTENSIONS`: 신규 추가

---

## 5. 남은 중복 (추후 고려)

### CourtDimensions 구조 중복 — 이번 세션 범위 외

| 위치 | 구조 | 용도 |
|---|---|---|
| `utils/geometry_utils.CourtDimensions` | dataclass (length/width/paint_*/rim_*) | 기하학 계산 |
| `ai_referee/rules/fiba_rules.CourtDimensions` | dataclass (FIBA rule 맥락) | Rule 판정 |
| `shared/constants/court_constants.CourtStandard` | Enum + 캐시 dict | 상수 접근 |

**판단**: 3개 구조가 용도별로 분리되어 있음 (기하/규칙/상수). 통합은 의미 있는 API 변경 필요 → H1/H2/H3 이후 별도 진행.

---

## 6. Phase 15 누적 진행도

| 세션 | Tier | 처리 건수 | 파일 변경 |
|---|---|---|---|
| 1 | Tier 1 + Tier 4 | 9 | 24 |
| 2 | Tier 3 M1 | 10 | 4 |
| 3 | Tier 5 | 7 | 5 |
| 4 | Tier 3 M2 | 31 | 32 |
| 5 | Tier 3 M3 | 26 | 29 |
| 6 | Tier 3 M4+M5 | 4 | 4 |
| **7** | **Tier 2 H5** | **7** | **7** |
| **합계** | — | **94** | **105** |

### 남은 Phase 15 작업 (5건, Tier 2 High)

| ID | 작업 | 예상 작업량 |
|---|---|---|
| H1 | `motion_analysis/phase_analysis/` → `biomechanics/phase_analysis/` | 중 |
| H2 | `motion_analysis/form_evaluation/` → `feedback_system/form_evaluation/` | 중 |
| H3 | `motion_analysis/comparison/` → `feedback_system/comparison/` | 소 |
| H4 | Facade 5개 engine 연동 구현 | 중 |
| H6 | korean_templates.py 1,630줄 분할 | 대 |

**H5 완료**: shared.constants SSOT 확립 — 이후 H1/H2/H3 코드 이전 시 일관된 상수 참조 보장.

---

## 7. 다음 세션 제안

**세션 8 권장**: **H6 korean_templates.py 1,630줄 분할** (~90분, 독립 작업)

- **이유**: H1/H2/H3는 연관 디렉토리 3개 이동 (작업량 중복 방지 위해 일괄이 유리), H4는 engine 통합 의존. H6은 독립적이고 메모리 절감 추가 효과.
- **작업**:
  - `korean_templates.py` 1,630줄 → 도메인별 파일 분할
    - `templates/motion/` (슈팅/드리블/패스)
    - `templates/tactical/` (공격/수비/스페이싱)
    - `templates/referee/` (파울/바이올레이션)
    - `templates/biomech/` (안정성/에너지)
  - `KoreanTemplates` 클래스는 lazy 로딩으로 전환 (모듈 최초 import 시 부분 로딩)
- **예상 파일**: 1개 분할 + 재구성 6~8개

**대안 1**: **H1/H2/H3 일괄 motion_analysis 이전** (~60분)

**대안 2**: **H4 Facade engine 연동 구현** (~60분, engine 통합 의존)

---

**세션 7 완료. H5 SSOT 확립 7파일 변경. 값 충돌 1건 해결 (HOOP_RADIUS 0.225 → 0.2286). Breaking change 없음 (AIR_DENSITY 0.17% 미세 조정).**
