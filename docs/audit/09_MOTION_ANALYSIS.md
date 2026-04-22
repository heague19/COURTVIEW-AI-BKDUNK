# Phase 9 — motion_analysis/ 모듈 감사 보고서

> **감사 범위**: `motion_analysis/` 전체 22파일 (~11,666 lines)
> **감사 방식**: Read 도구 전수 직독 (grep/ls 미사용)
> **감사 일자**: 2026-04-20
> **감사 기준**: MODULE_AUDIT_STANDARD v1.0, 8축 평가
> **역할**: 바이오와 게임의 **중간 다리 (event bridge)** — 동작 감지 → 이벤트 도출

---

## 0. 실행 요약 (Executive Summary)

### 0.1 점수 총평 (현재 상태)

| 축 | 점수 | 비고 |
|---|---|---|
| 1. Import 유효성 | 100 | 절대 임포트, `from __future__ import annotations` 전 파일 |
| 2. 기능 유효성 | 95 | 룰 기반 전환 코드 — SV-action 학습 모델 교체 대기 중 |
| 3. 메모리 누수 | 100 | 언바운디드 성장 없음, 모든 상태 RLock 보호 |
| 4. 하드코딩 | 92 | 학술 임계치 Final 상수화 양호, 일부 매직넘버 (400 cm/s 등) |
| 5. 1줄 리뷰 | 100 | 한글 docstring + 학술 출처 표기 일관 |
| 6. 스레드 안전 | 100 | 전 클래스 `threading.RLock` 일관 적용 |
| 7. 예외 처리 | 98 | 빈 시퀀스/데이터 부재 fallback 철저, logger.warning 적절 |
| 8. 확장성 | 100 | 모든 클래스 `from_yaml` 팩토리 제공, 의존성 주입 가능 |
| **총평** | **98.1** | S-grade, 단 **구조적 리팩토링 권고** 별도 제시 |

### 0.2 핵심 발견 (Key Findings)

1. **코드 품질은 S-grade지만, 구조적 재배치가 필요하다.**
   현재 모듈은 5-Tier 파이프라인 (감지 → 분류 → 위상 분해 → 폼 평가 → 비교)으로 구성되어 있으며, 모든 파일이 일관된 코딩 표준·학술 근거·스레드 안전성을 충족한다. 그러나 Tier 3~5는 motion_analysis의 **"동작 감지 → 이벤트"** 역할과 개념적으로 분리되어야 한다.

2. **룰 기반 특성과 SV-action 학습 모델 교체 계획의 정합성.**
   Tier 1 감지기(shot/dribble/pass/movement/rebound)는 torso-length 비례 임계치 + 학술 출처 기반 규칙 엔진이다. 이들은 SV-action 학습 가중치 도입 시 교체 지점으로 명확히 설계되어 있다 (공통 `DetectionCandidate` 인터페이스).

3. **Tier 3-5의 과잉 책임 (Overreach)**.
   - `phase_analysis/shot_phase_analyzer.py`는 키네틱 체인 평가 로직을 포함 — **biomechanics 영역**
   - `form_evaluation/*` 전체는 100점 채점 + 피드백 생성 — **feedback_system 영역**
   - `comparison/form_comparator.py`는 DTW 폼 비교 + 최소 10개 피드백 생성 — **feedback_system 영역**

4. **룰 기반 분류기의 한계 명시.**
   `dribble_classifier.py:273-275`에서 SHAMGOD (샴갓) 드리블은 "포즈 키포인트만으로는 구분 불가 → 향후 학습 기반 분류 대상" 주석으로 자체 한계를 인지. 13종 중 12종 구현, 이는 룰 기반의 실질적 천장 (ceiling)을 보여준다.

### 0.3 리팩토링 권고 (핵심)

```
현재 구조:
motion_analysis/
├── detection/           (Tier 1: 이벤트 감지)
├── classification/      (Tier 2: 세부 유형 분류)
├── phase_analysis/      (Tier 3: 위상 분해)  ⚠️
├── form_evaluation/     (Tier 4: 폼 채점)    ⚠️
└── comparison/          (Tier 5: DTW 비교)    ⚠️

제안 구조:
motion_analysis/          ← 바이오와 게임의 중간 다리, 이벤트 추출만
├── detection/            (유지, SV-action 교체 지점)
└── classification/       (DEPRECATE 예정 — SV-action이 흡수)

biomechanics/
└── phase_analysis/       (← motion_analysis/phase_analysis 이전)

feedback_system/
├── form_evaluation/      (← motion_analysis/form_evaluation 이전)
└── comparison/           (← motion_analysis/comparison 이전)
```

**근거**: 사용자 요구사항 — "motion_analysis는 동작을 감지하고 분석해서 상황별 이벤트를 감지할 수 있도록 하는 바이오와 게임의 중간 다리 역할이라고 생각하거든? 그랬을때, 단계와 슛폼 분석, 비교가 현재 필요할까 라는 생각? 앞으로 학습하는 모델 중에 분명 recorder, referee, coach, scout 이게 있다만 이건 해당 가중치한테 값을 넣어서 따로 작업하는게 맞지 않나 싶은거야"

---

## 1. 모듈 개요 (Module Overview)

### 1.1 역할 (Role)
- **입력**: `MotionSnapshot` 시퀀스 (pose_estimation 모듈 출력)
- **출력** (현재):
  - Tier 1: `DetectionCandidate` 리스트 (감지된 동작 후보)
  - Tier 2: `ActionType` + 세부 유형 (ShotType, DribbleType)
  - Tier 3: `PhaseResult` (위상 분해 + 키네틱 체인 점수)
  - Tier 4: `FormEvaluation` (8카테고리 100점 채점 + 최소 10개 피드백)
  - Tier 5: `ComparisonResult` (DTW 유사도 + 주요 차이점)
- **출력** (리팩토링 후): Tier 1-2만 유지, 즉 **이벤트 감지 및 분류**에 집중

### 1.2 파일 구성 (22 files, 11,666 lines)

| 카테고리 | 파일 | Lines | 역할 |
|---|---|---|---|
| Core | `__init__.py` | 160 | Lazy import, 통합 export |
| Core | `models.py` | 803 | DTO 정의 (14개 dataclass) |
| **Tier 1** | `detection/__init__.py` | 69 | 감지기 통합 |
| Tier 1 | `detection/shot_detector.py` | 609 | 슈팅 감지 (손목↑어깨, 팔꿈치 150°+) |
| Tier 1 | `detection/dribble_detector.py` | 478 | 드리블 감지 (torso 비례 진동) |
| Tier 1 | `detection/pass_detector.py` | 489 | 패스 감지 (릴리스 피크, 주기성) |
| Tier 1 | `detection/movement_detector.py` | 580 | 이동 감지 (COM 속도, sprint/jog/lateral) |
| Tier 1 | `detection/rebound_detector.py` | 566 | 리바운드 감지 (점프+골대근접+팔상승) |
| **Tier 2** | `classification/__init__.py` | 45 | 분류기 통합 |
| Tier 2 | `classification/action_classifier.py` | 425 | 11 ActionType 우선순위 + 겹침 해소 |
| Tier 2 | `classification/shot_classifier.py` | 536 | 13 ShotType 세분화 |
| Tier 2 | `classification/dribble_classifier.py` | 570 | 13 DribbleType (12 구현, SHAMGOD 제외) |
| **Tier 3** | `phase_analysis/__init__.py` | 44 | 위상 분석기 통합 |
| Tier 3 | `phase_analysis/shot_phase_analyzer.py` | 866 | 슈팅 4위상 + 키네틱 체인 평가 |
| Tier 3 | `phase_analysis/dribble_phase_analyzer.py` | 797 | 드리블 4위상 + 바운스 사이클 일관성 |
| **Tier 4** | `form_evaluation/__init__.py` | 54 | 폼 평가기 통합 |
| Tier 4 | `form_evaluation/shooting_criteria.py` | 677 | 슈팅 8카테고리 기준 DataClass |
| Tier 4 | `form_evaluation/dribble_criteria.py` | 658 | 드리블 8카테고리 기준 DataClass |
| Tier 4 | `form_evaluation/shooting_form_evaluator.py` | 1,070 | 슈팅 100점 채점 + 피드백 |
| Tier 4 | `form_evaluation/dribble_form_evaluator.py` | 897 | 드리블 100점 채점 + 피드백 |
| **Tier 5** | `comparison/__init__.py` | 35 | 비교기 통합 |
| Tier 5 | `comparison/form_comparator.py` | 1,236 | DTW 비교 + 최소 10개 차이점 |

---

## 2. 감사 축별 상세 평가

### 2.1 축 1 — Import 유효성 (100/100)

**전수 검증 결과: 통과**

- 모든 22파일에 `from __future__ import annotations` 1행 존재
- 절대 임포트만 사용 — `from motion_analysis.xxx import ...`, `from shared.xxx import ...`
- 순환 참조 없음:
  - `shooting_criteria.py` → `motion_analysis.models` (상위 단일 방향)
  - `dribble_criteria.py` → `motion_analysis.models` + `motion_analysis.form_evaluation.shooting_criteria` (RangeJudgment 재사용) — 동일 계층 DAG 유지
  - `form_comparator.py` → `motion_analysis.models` 만 (비교기는 evaluator에 의존 안 함)
- `__init__.py` 3개 (motion_analysis/, detection/, classification/ 등)에서 하위 모듈 통합 export — `__all__` 명시

**우려사항: 없음**

### 2.2 축 2 — 기능 유효성 (95/100)

**통과 영역**

- 학술 근거 전 파일 기재:
  - Miller & Bartlett (1996), Knudson (1993), Okazaki & Rodacki (2012) — 슈팅
  - Arias (2012), Cortis (2011) — 드리블
  - Ben Abdelkrim (2007), Ziv & Lidor (2009) — 이동
  - Sakoe & Chiba (1978), Müller (2007) — DTW
  - de Leva (1996) — 신체 비율 정규화
- torso-length 비례 임계치 — 카메라/해상도 독립적 (검증 우수)
- 폴백 로직 철저 — `_DEFAULT_FALLBACK_TORSO_PX = 200.0` 등

**감점 영역 (-5)**

- `dribble_classifier.py:273-275`: SHAMGOD 드리블 미구현 (12/13종) — 명시된 한계
- `shooting_form_evaluator.py:477`: `speed_ratio = min(1.0, wrist_speed / 400.0)` — 400 cm/s 매직넘버 (criteria.wrist_snap_range 상한 1200 대비 불일치)
- `shooting_form_evaluator.py:517`: `height_score = min(1.0, release_height / 30.0)` — 30cm 매직넘버
- `dribble_form_evaluator.py:200`: `speed_score = min(1.0, pd_speed / 150.0) * 5.0` — 150 cm/s 매직넘버

이들은 YAML 기준치와 따로 하드코딩됨. **Safe-Now 아님** (튜닝 값이며, Phase 15 리팩토링 시 criteria로 이동 권고).

### 2.3 축 3 — 메모리 누수 (100/100)

- 모든 분석기는 **stateless** 또는 설정 파라미터만 보관 (`__slots__` 활용)
- 중간 결과 축적 없음 — `list[PhaseSegment]`, `list[FeedbackItem]` 모두 호출 지역 변수
- `FormComparator._compute_dtw`는 O(n×m) DP 테이블을 로컬 생성 후 해제 — 함수 종료 시 GC
- RLock도 `__slots__`에 포함되어 객체당 1개만 유지
- **PhaseResult 6분 분석 시**: 400 프레임 × 4 위상 × ~5 metrics = 8KB 수준, 누적 없음

**우려사항: 없음**

### 2.4 축 4 — 하드코딩 (92/100)

**양호**

- 학술 임계치는 `_CONSTANT_NAME: Final[type] = value` 패턴 일관
- 출처 주석 동반: `# Miller & Bartlett (1996): 슈팅 전체 ~0.5-1.0초`
- torso-length 환산 주석: `# 실제 성인 torso ≈ 0.5m 기준, 물리 거리 → torso-length 변환`

**감점 (-8)**

1. **Evaluator의 임시 매직넘버** (Phase 15 이관 대상):
   - `shooting_form_evaluator.py:477, 517, 585, 615` — 400, 30, 170, 0.8 등
   - `dribble_form_evaluator.py:200, 230, 292, 324` — 150, 70, hip_y 기반, 50.0

2. **FormComparator σ 파라미터**:
   - `form_comparator.py:522`: `sigma = 0.5` (경험적) — YAML 노출 안 됨

3. **DribblePhaseAnalyzer 상수**:
   - `_CONSISTENCY_WEIGHT: Final[float] = 0.30` 정의되나 실제 사용처에서는 다른 가중치 사용 — 데드 상수

**Safe-Now 판정**: 위 항목들은 기능 정확성에 즉시 영향 없음. Tier 4-5가 `feedback_system/`으로 이전될 때 YAML 기준으로 흡수하면 자연 해소됨 → **Phase 15 리팩토링 권고**.

### 2.5 축 5 — 1줄 리뷰 (100/100)

**우수**

- 파일 헤더 일관 포맷:
  ```
  COURTVIEW - AI 농구 분석 플랫폼
  모듈: motion_analysis/xxx
  파일: xxx.py
  설명: ... (Tier N)
  학술 근거: ...
  참조: ...
  의존성: ...
  소비자: ...
  작성자/수정일/버전
  ```
- 모든 public 메서드 Korean docstring (Args/Returns 명시)
- 비자명 로직에 근거 주석 — 예: `# 손목이 엉덩이 뒤(z 작음)`

### 2.6 축 6 — 스레드 안전 (100/100)

- 전 클래스 `self._lock = RLock()` 초기화, public 진입점에서 `with self._lock:` 래핑
- 내부 `_xxx_impl` 메서드 패턴 일관 — 락은 진입점에서만 획득
- `__slots__`에 `_lock` 포함 — 누락 없음

**우려사항: 없음**

### 2.7 축 7 — 예외 처리 (98/100)

**우수**

- 빈 시퀀스 방어:
  - `FormComparator._compare_impl`: 2프레임 미만 시 `logger.warning` + 기본 ComparisonResult 반환
  - `ShotPhaseAnalyzer._analyze_impl`: 4프레임 미만 시 `_empty_result` 반환
- `try/except ValueError`로 YAML enum 파싱 방어 — `ShotPhaseAnalyzer.from_yaml:162-164`
- 폴백 체인:
  - COM 없음 → 엉덩이 대체 → 둘 다 없음 → `return 0.0`

**감점 (-2)**

- `dribble_phase_analyzer.py:215-220`: `cycle_results[best_idx]`에서 `best_idx = 0` 초기값이지만 `cycle_results`가 `empty_result` 경유 후 복귀하므로 방어됨. 단, 방어적 코드 (`if not cycle_results: return ...`)는 별도 존재하여 중복 방어 → 가독성 미미한 감점.

### 2.8 축 8 — 확장성 (100/100)

- 모든 주요 클래스에 `@classmethod from_yaml(cls, config: dict)` 팩토리 존재:
  - `ShotPhaseAnalyzer.from_yaml`, `DribblePhaseAnalyzer.from_yaml`
  - `ShootingCriteria.from_yaml`, `DribbleCriteria.from_yaml`
  - `ShootingFormEvaluator.from_yaml`, `DribbleFormEvaluator.from_yaml`
  - `FormComparator.from_yaml`
- DI 가능 — `ShootingFormEvaluator(criteria)` 생성자로 criteria 주입
- `__init__.py` lazy import 패턴 — 순환 의존 회피 + 시작 시간 단축

---

## 3. 계층별 심층 분석 (Layer Deep Dive)

### 3.1 Tier 1 — Detection (KEEP, SV-action 교체 지점)

**현재 역할**
- 5개 감지기 (shot/dribble/pass/movement/rebound)
- 입력: `list[MotionSnapshot]` → 출력: `list[DetectionCandidate]`
- 모든 임계치 torso-length 비례 — 체형/카메라 독립

**SV-action 교체 적합성: 매우 높음**

공통 인터페이스가 확립되어 있어 ML 모델 교체가 용이:
```python
class ShotDetector:
    def detect(self, snapshots: list[MotionSnapshot]) -> list[DetectionCandidate]: ...
```
SV-action ML 가중치는 동일 인터페이스로 교체하면 됨. 룰 기반은 **fallback 또는 A/B 비교용**으로 보존 권고.

**감사 결과**: 유지, 룰 기반 코드는 SV-action 학습 데이터 레이블링 기준으로 활용 가능.

### 3.2 Tier 2 — Classification (DEPRECATE 예정)

**현재 역할**
- `ActionClassifier`: 11 ActionType 우선순위 해소
- `ShotClassifier`: 13 ShotType 세분화 (덩크/레이업/3점/풀업 등)
- `DribbleClassifier`: 13 DribbleType 세분화 (크로스오버/비하인드/스핀 등)

**SV-action 통합 시 중복 발생**

SV-action 모델은 학습 단계에서 이미 세부 클래스를 출력하므로 classification/ 모듈의 룰 기반 분류기는 중복이 된다. SHAMGOD 미구현 (12/13) 주석은 룰 기반의 본질적 한계를 보여줌.

**감사 결과**: SV-action 배포 후 즉시 DEPRECATE 권고. 중간 기간에는 룰 기반 결과와 ML 결과를 앙상블하는 용도로 활용 가능.

### 3.3 Tier 3 — Phase Analysis (MOVE to biomechanics/)

**현재 코드의 기능**

`shot_phase_analyzer.py`의 핵심 로직:
- **위상 경계 감지**: 무릎 각도, 팔꿈치 신전, 손목 속도 피크 기반
- **키네틱 체인 평가**: 무릎 → 엉덩이 → 어깨 → 팔꿈치 → 손목의 피크 도달 순서 검증
- **전환 부드러움**: jerk (2차 차분) 기반 정규화

이는 **바이오메카닉스 영역의 고유 책임**이다. 특히 `_evaluate_kinetic_chain`은 de Leva / Newton-Euler 기반 역학 분석과 직접 연결되어야 한다.

**이전 위치**: `biomechanics/phase_analysis/`
**이유**:
- 키네틱 체인 = 신체 역학 (biomechanics의 8축 중 "운동학" 축)
- 위상 경계 감지 = 관절 각도/속도 분석 (이미 biomechanics/kinematics/에 유사 로직 존재)
- 위상 출력 `PhaseResult`은 Tier 4 폼 평가의 입력 — 그러나 Tier 4도 이전 대상이므로 의존성 체인은 유지됨

**이전 시 API 호환**: motion_analysis에서 re-export shim 유지 (Phase 15 deprecation window).

### 3.4 Tier 4 — Form Evaluation (MOVE to feedback_system/)

**현재 코드의 기능**

`shooting_form_evaluator.py`의 핵심 출력:
- `FormEvaluation.raw_score` (100점)
- `FormEvaluation.category_scores` (8카테고리)
- `FormEvaluation.feedback_items` (최소 10개 한글 피드백)
- `FormEvaluation.adjustment_factor` (skill_level 기반)
- `FormEvaluation.adjusted_score`

**이는 본질적으로 피드백 생성이다**:
- 점수는 **사용자에게 보여주기 위한** 것이지 분석 결과가 아니다
- 피드백 메시지 생성 로직 (`_knee_feedback`, `_trunk_feedback` 등)은 자연어 처리에 가깝다
- `_generate_supplementary_feedback`: 최소 10개 보장 — UX 요구사항

**이전 위치**: `feedback_system/form_evaluation/`
**이유**:
- feedback_system의 역할은 "분석 결과를 사용자 이해 가능한 피드백으로 변환"
- 100점 채점 + 한글 피드백 = 정확히 이 역할
- 입력(`PhaseResult` from biomechanics) + 입력(`Criteria` from configs/) → 출력(FeedbackItem) 의존성 체인이 더 자연스러움

### 3.5 Tier 5 — Comparison (MOVE to feedback_system/)

**현재 코드의 기능**
- DTW 기반 시계열 정합 (Sakoe & Chiba 1978)
- 신체 비율 정규화 (de Leva 1996)
- `ComparisonResult.key_differences`: 최소 10개 차이점 피드백

**이전 위치**: `feedback_system/comparison/`
**이유**:
- DTW는 수학적 알고리즘이지만, 출력은 **"레퍼런스 대비 무엇을 개선해야 하는가"**라는 피드백
- `_generate_supplementary_differences`: 피드백 수 보장 로직 — 이 역시 UX 요구사항

---

## 4. Safe-Now / Phase 15 분류

### 4.1 Safe-Now (즉시 처리 가능)

**없음.** 모든 발견 사항은 구조적 리팩토링 또는 ML 모델 교체와 연관됨.

### 4.2 Phase 15 (구조 리팩토링 시 일괄 처리)

| 항목 | 파일 | 조치 |
|---|---|---|
| H1 | `motion_analysis/phase_analysis/*` | → `biomechanics/phase_analysis/` 이전 |
| H2 | `motion_analysis/form_evaluation/*` | → `feedback_system/form_evaluation/` 이전 |
| H3 | `motion_analysis/comparison/*` | → `feedback_system/comparison/` 이전 |
| M1 | `shooting_form_evaluator.py:477, 517, 585, 615` | 매직넘버 400/30/170/0.8 → `ShootingCriteria` 흡수 |
| M2 | `dribble_form_evaluator.py:200, 324` | 매직넘버 150/50 → `DribbleCriteria` 흡수 |
| M3 | `form_comparator.py:522` | σ=0.5 → `motion_analysis.yaml` comparison 섹션 |
| L1 | `dribble_phase_analyzer.py:85` | `_CONSISTENCY_WEIGHT` 데드 상수 제거 |
| L2 | `classification/*` | SV-action 배포 후 DEPRECATE |
| L3 | `dribble_classifier.py:273-275` | SHAMGOD 주석 — DEPRECATE와 함께 자연 해소 |

### 4.3 이전 순서 권고 (Refactoring Sequence)

1. **1단계 (Preparation)**: 신규 경로에 파일 복사 + 기존 경로에서 re-export shim 생성
   - `biomechanics/phase_analysis/__init__.py`에 `from motion_analysis.phase_analysis import *`
   - 기존 `motion_analysis/phase_analysis/__init__.py`에서 `DeprecationWarning` 부착
2. **2단계 (Migration)**: 호출자(`game_analysis/`, `feedback_system/`, `api_server/`) 임포트 경로 일괄 변경
3. **3단계 (Cleanup)**: `motion_analysis/phase_analysis/`, `form_evaluation/`, `comparison/` 디렉토리 삭제

Phase 15에서 일괄 수행.

---

## 5. 통계 및 총평

### 5.1 코드 통계

| 항목 | 수치 |
|---|---|
| 총 파일 | 22 |
| 총 라인 | 11,666 |
| 평균 파일당 라인 | 530 |
| 최대 파일 | `form_comparator.py` (1,236) |
| 최소 파일 | `comparison/__init__.py` (35) |
| `from __future__ import annotations` 적용률 | 100% |
| `@dataclass(slots=True)` 사용 클래스 | 14 (models.py + criteria.py) |
| RLock 적용 클래스 | 11 (모든 분석기·평가기) |
| `from_yaml` 팩토리 제공 클래스 | 7 |

### 5.2 학술 근거 문헌

1. Miller & Bartlett (1996) — 슈팅 운동학
2. Okazaki & Rodacki (2012) — 점프슛 거리별 역학
3. Knudson (1993) — 슈팅 6대 교수 포인트
4. Arias et al. (2012) — 드리블 바이오메카닉스
5. Cortis et al. (2011) — 청년 농구 협응력
6. Ben Abdelkrim et al. (2007) — 농구 경기 중 이동 속도
7. Ziv & Lidor (2009) — 농구 신체 요구
8. Sakoe & Chiba (1978) — DTW
9. Müller (2007) — Information Retrieval for Motion
10. de Leva (1996) — 신체 분절 관성 모델

### 5.3 종합 평점

**현재 코드 품질 기준**: **98.1/100 (S-grade)**

**구조 적합성 기준** (리팩토링 전 기준): **72/100**
- Tier 1-2는 적절한 책임 (event bridge)
- Tier 3는 biomechanics 영역 침범
- Tier 4-5는 feedback_system 영역 침범

**리팩토링 후 예상 평점**: **99/100**
- motion_analysis가 본연의 "이벤트 감지 브리지" 역할에 집중
- biomechanics / feedback_system 경계 명확화
- SV-action ML 교체 시 영향 범위 축소 (detection/ 만)

---

## 6. 결론 및 다음 단계

### 6.1 Phase 9 결론

1. **코드 품질 S-grade 확인**. 전 22파일이 기술 표준을 충족함.
2. **구조적 리팩토링 권고를 공식화**. Tier 3-5 재배치는 아키텍처 정합성 향상을 위해 필수.
3. **SV-action 교체 준비 완료**. Tier 1의 인터페이스(`DetectionCandidate`)는 ML 모델 swap-in에 적합.

### 6.2 다음 Phase 준비

- **Phase 10**: `game_analysis/` (165 파일, 최대 모듈) — 본 Phase 9의 Tier 3-5 이전 이후 소비자 변경 검토 필요
- **Phase 12**: `feedback_system/` (39 파일) — motion_analysis Tier 4-5 이전 대상 디렉토리. Phase 12에서 현재 구조를 먼저 본 후 Phase 15에서 통합 리팩토링
- **Phase 15**: 리팩토링 권고 일괄 실행 — motion_analysis ↔ biomechanics ↔ feedback_system 경계 재정립

### 6.3 사용자 결정 필요 사항

1. **리팩토링 타이밍**: Phase 15 일괄? 아니면 즉시 착수?
2. **API 호환 유지 기간**: DeprecationWarning 몇 릴리즈 유지?
3. **SV-action 배포 시점**: classification/ DEPRECATE 언제 트리거?

---

**감사자**: Claude (Opus 4.7)
**검토 완료**: 2026-04-20
**다음 단계**: Phase 10 — `game_analysis/` 감사 착수 대기
