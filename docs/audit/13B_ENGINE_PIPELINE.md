# 13B. engine/{pipeline + fusion + referee} 감사 리포트

**감사 범위**: `pipeline/` (7) + `pipeline/fusion/` (4) + `referee/` (3) = **14파일**
**감사 방식**: 전수 직독 (Read 전용)
**감사 축**: 8종
**감사일**: 2026-04-20

---

## 1. 감사 대상 구성

| 디렉토리 | 파일 | 역할 |
|---|---|---|
| `pipeline/` (7) | `__init__`, `frame_pipeline`, `event_pipeline`, `possession_pipeline`, `period_pipeline`, `postgame_pipeline`, `frame_to_event_converter` | 5등급 Cadence 파이프라인 + 변환기 |
| `pipeline/fusion/` (4) | `__init__`, `detection_fusion`, `pose_fusion`, `tracking_fusion` | 8cam 멀티뷰 융합 (CV-BBox 통합) |
| `referee/` (3) | `__init__`, `referee_orchestrator`, `multi_angle_pipeline` | AI 심판 오케스트레이션 |

---

## 2. 감사 8축 평가

### 2.1 Import 유효성 ⚠ 95/100

- 14파일 전체 `from __future__ import annotations` + SSOT 준수 ✓
- **TYPE_CHECKING 패턴 광범위 적용** — 순환 참조 회피 (pipeline 5개 + referee 2개)
- DI 주입 패턴 철저 (`XxxAnalyzerSet` / `XxxDetectorSet` / `XxxModuleSet` 컨테이너)
- **관찰 (S43 후보)**: [detection_fusion.py:50-53](engine/pipeline/fusion/detection_fusion.py#L50-L53) import 섹션 오분류
  - `import cv2` (서드파티 ✓) + `import json` + `import zipfile` (둘 다 표준 라이브러리) 가 "서드파티 라이브러리" 블록 주석 아래 혼재
  - 표준 라이브러리 블록으로 이동 권장

### 2.2 기능 유효성 ✅ 97/100

- **5등급 Cadence 파이프라인 완전 구현**:
  - 🔴 FRAME (33ms): detection + pose + tracking fusion + biomechanics 직접 호출
  - 🟠 EVENT (<10ms): 16종 이벤트 감지기 + BasicStatsCalculator 증분 갱신
  - 🟡 POSSESSION (<100ms): 전술 6 + 개인 6 + 하이라이트 3 + 공간 4 = 19종 분석기
  - 🟢 PERIOD (<1s): 경기흐름 4 + 로테이션 4 + 시즌 3 + 상황 4 = 15종 분석기
  - 🔵 POSTGAME (무제한): 리포트 + 추출 7+6 + 비디오 편집 4 + 필름 세션 3 = 20+ 모듈
- **frame_to_event_converter**: FramePipelineResult → EventFrameData 변환기 (`_input` 속성 동적 매핑)
- **detection_fusion**: CV-BBox 통합 모델 1회 추론 → ball/player/hoop/backboard 동시 분배 (기존 3회 대비 3배 속도)
- **pose_fusion**: 멀티뷰 2D → MultiViewTriangulator → 3D 키포인트 복원
- **tracking_fusion**: 로컬 track_id → 글로벌 ID + digit/team 기반 ReID 대체 (별도 모델 불필요)
- **referee_orchestrator**: 12 바이올레이션 + 11 파울 + 6 decisions 통합 오케스트레이션

### 2.3 메모리 누수 방지 ✅ 97/100

- `_MAX_RESULT_HISTORY=50` / `_MAX_VALIDATION_HISTORY=200` / `_POSSESSION_HISTORY_SIZE=30` 일관
- `deque(maxlen=N)` 자동 트림 ✓
- 모든 pipeline `_total_*` 카운터 + RLock 보호
- 상위 Cadence 결과는 단발 생성 후 dispatcher로 즉시 전달

### 2.4 하드코딩 점검 ✅ 93/100

- 모든 매직 넘버 `_Final[T]` 상수화 또는 Config 노출
- **관찰**: [frame_to_event_converter.py:37](engine/pipeline/frame_to_event_converter.py#L37) `_PX_TO_M: Final[float] = 0.03` 주석 "림 직경 45cm ≈ 영상 ~15px 기준" — 고정 값 (카메라 캘리브레이션 기반)
- **관찰**: [frame_to_event_converter.py:40](engine/pipeline/frame_to_event_converter.py#L40) `_POSSESSION_DIST_PX: Final[float] = 80.0` 픽셀 단위 — 코트 좌표계가 아닌 픽셀 기반

### 2.5 한줄 검토 ✅ 98/100

- **docstring 최고 수준**: 데이터 흐름 다이어그램 + 의존성 + 소비자 + 참고 메모
- 🔴🟠🟡🟢🔵 Cadence 등급 이모지 시각화 일관
- `계층 분리` 명시 (tensorrt_engine = Low-level, tensorrt_pool = High-level) ✓
- `engine은 오케스트레이션만 담당` 원칙 명시 — 기존 모듈 변경 0건 보장

### 2.6 스레드 안전성 ✅ 98/100

- 14파일 전체 `RLock` + `with self._lock:` + `__slots__` 수동 선언
- TYPE_CHECKING으로 순환 참조 회피 — 런타임 import 안전
- `deque` / `dict` 방어적 복사 일관

### 2.7 예외 처리 ✅ 96/100

- TYPE_CHECKING 블록 내부에 조건부 import — 순환 참조 해결
- `if TYPE_CHECKING:` 런타임 회피로 상위 의존성 누락 시에도 import 안전
- 시간 예산 초과 모니터링 + 경고 로그

### 2.8 확장성 ✅ 98/100

- `PossessionAnalyzerSet` / `PeriodAnalyzerSet` / `PostgameModuleSet` / `EventDetectorSet` / `EventStatsSet` / `EventRealtimeSet` DI 컨테이너 — **주입만 하면 분석기 확장 가능**
- `FrameToEventConverter` 동적 `*_input` 속성 매핑 — 새 감지기 추가 시 `EventFrameData` 필드만 추가
- CV-BBox 통합 모델 설계 — 단일 추론으로 4 클래스 동시 감지 (확장 용이)
- **Phase 13 최고 점수 축** (98)

---

## 3. Safe-Now 이슈 목록 (0~1건)

### S43 (후보, 매우 사소) — `detection_fusion.py` import 섹션 오분류

- **파일**: [engine/pipeline/fusion/detection_fusion.py:50-53](engine/pipeline/fusion/detection_fusion.py#L50-L53)
- **현황**: 서드파티 섹션 주석 하단에 `import cv2` (서드파티) + `import json` + `import zipfile` (둘 다 표준)이 혼재
- **조치**: 표준 라이브러리 섹션으로 `json`, `zipfile` 이동
- **영향**: 스타일 정리 수준 (기능 영향 없음)

---

## 4. Phase 15 Deferred 이슈 (2건)

### P15-13B-01. `frame_to_event_converter` 픽셀 단위 하드코딩

- [frame_to_event_converter.py:37-40](engine/pipeline/frame_to_event_converter.py#L37-L40) `_PX_TO_M=0.03`, `_POSSESSION_DIST_PX=80.0`
- 코트 좌표계 변환으로 일원화 권장 (캘리브레이션 호모그래피 경유)

### P15-13B-02. 5개 파이프라인 시간 예산 초과 핸들링

- 각 파이프라인 docstring에 시간 예산 명시 (33ms / <10ms / <100ms / <1s / 무제한)
- 초과 시 경고 로그 존재하나 자동 degradation 전략 미구현 (Stage2 스킵, 배치 축소 등)

---

## 5. 13B 종합 점수

| 축 | 점수 |
|---|---|
| Import 유효성 | 95 |
| 기능 유효성 | 97 |
| 메모리 누수 방지 | 97 |
| 하드코딩 점검 | 93 |
| 한줄 검토 | 98 |
| 스레드 안전성 | 98 |
| 예외 처리 | 96 |
| 확장성 | 98 |
| **총점** | **96.5** |

---

## 6. 관찰된 강점

1. **5등급 Cadence 파이프라인** — 33ms FRAME → <10ms EVENT → <100ms POSSESSION → <1s PERIOD → 무제한 POSTGAME
2. **TYPE_CHECKING 패턴** — 순환 참조 없이 54+ 분석기 DI 주입
3. **DI 컨테이너 체계** — `XxxAnalyzerSet` / `XxxDetectorSet` / `XxxModuleSet` 4종
4. **CV-BBox 통합 모델 설계** — 1회 추론으로 4 클래스 동시 감지 (3배 속도)
5. **ReID 대체 전략** — digit(등번호) + team(색상)로 별도 ReID 모델 불필요
6. **`FrameToEventConverter`** — `*_input` 동적 속성 매핑으로 이벤트 감지기 확장 용이
7. **계층 분리 명시** — Low-level(기존 모듈) vs High-level(engine 오케스트레이션) 역할 명확
8. **engine은 오케스트레이션만** — 기존 모듈 변경 0건 원칙
9. **데이터 흐름 다이어그램** — 각 docstring ASCII 아트로 시각화
10. **시간 예산 모니터링** — Cadence별 명시적 budget_ms + 초과 경고

---

## 7. 관찰된 약점

1. **픽셀 단위 하드코딩** — `frame_to_event_converter` 가 코트 좌표계 미사용
2. **시간 예산 초과 핸들링** — 자동 degradation 전략 미구현
3. **import 섹션 오분류** — `detection_fusion` 의 json/zipfile 오분류 (사소)

---

## 8. 다음 작업

1. Safe-Now 이슈 없음 (S43은 극히 사소, 선택 처리)
2. `13_ENGINE_SUMMARY.md` 통합 총평 작성
