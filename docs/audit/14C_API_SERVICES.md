# 14C. api_server/services/ 감사 리포트

**감사 범위**: `services/` (13) + `services/facades/` (6) = **19파일**
**감사 방식**: 전수 직독 (Read 전용)
**감사 축**: 8종
**감사일**: 2026-04-20

---

## 1. 감사 대상 구성

| 레이어 | 파일 | 역할 |
|---|---|---|
| **Services (13)** | `__init__`, `game_service`, `camera_service`, `referee_service`, `tactical_service`, `feedback_service`, `report_service`, `task_service`, `export_service`, `video_service`, `batch_sync_service`, `cloud_sync_service`, `realtime_stream_service` | 비즈니스 로직 (routes → services → facades → engine) |
| **Facades (6)** | `__init__`, `game_stats_facade`, `highlight_facade`, `referee_facade`, `report_facade`, `tactical_facade` | engine 데이터 → 프론트엔드 응답 변환 |

---

## 2. 감사 8축 평가

### 2.1 Import 유효성 ✅ 96/100

- 19파일 전체 `from __future__ import annotations` + SSOT 준수 ✓
- TYPE_CHECKING 패턴 광범위 활용 — engine.orchestrator.game_orchestrator 순환 참조 회피
- **관찰**: `game_service.py` 의 import 순서 특이 — `_AGE_GROUP_MAP` / `_GENDER_MAP` 정의 후 schemas import (표준 순서 미준수, 기능 영향 없음)

### 2.2 기능 유효성 ⚠ 90/100

- **Services (13) 일관 패턴**: `__slots__ + RLock + bind_orchestrator(orchestrator) + Facade 위임`
- **game_service**: 경기 수명주기 완전 구현 — camera_service 연동 + `on_game_start` 콜백 + demo/일반 모드 분기
- **camera_service**: 카메라 연결/캘리브레이션/AI 테스트 완전 구현 (13 엔드포인트 백엔드)
- **export_service**: 파일 I/O 완전 구현 (JSON/CSV)
- **video_service**: 배치 업로드 완전 구현
- **batch_sync_service**: 오프라인 미전송분 일괄 동기화
- **cloud_sync_service**: 백엔드 REST 호출 + 재시도
- **realtime_stream_service**: ResultDispatcher → WebSocket 연결
- **Facades (5)**: **모두 stub 상태** — orchestrator 인자 받지만 빈 응답 반환 (`return RefereeListResponse()`). 통합 테스트 단계에서 실제 engine 데이터 연동 예정 (주석 명시)

### 2.3 메모리 누수 방지 ✅ 96/100

- 모든 service `__slots__` 수동 선언 ✓
- `_orchestrator_ref` 약한 참조 (engine 수명주기와 별개 관리)
- 싱글턴 서비스 — 앱 수명주기와 일치

### 2.4 하드코딩 점검 ✅ 95/100

- `_AGE_GROUP_MAP`, `_GENDER_MAP`, `_MODE_MAP`, `_RULE_SET_MAP` 모듈 상수로 문자열 → Enum 매핑
- `cloud_sync_service`: `_MAX_RETRIES=3`, `_TIMEOUT_SEC=30.0` Final 상수
- `_VALID_REPORT_TYPES: frozenset` 화이트리스트

### 2.5 한줄 검토 ⚠ 92/100

- 19파일 전체 docstring + 의존성/소비자/호출 모듈 철저
- **관찰**: `services/__init__.py`, `facades/__init__.py` 거의 비어있음 (14A/14B와 동일)
- `camera_service.py` 특히 의존 모듈 명시 풍부 (`infrastructure/`, `detection/` 6 모듈)

### 2.6 스레드 안전성 ✅ 97/100

- 13 service 전체 `RLock` + `with self._lock:` 보호
- `bind_orchestrator` 메서드는 lock 보호 — 교체 시 race condition 방지
- Facade 5개는 `@staticmethod` — stateless, thread-safe

### 2.7 예외 처리 ✅ 94/100

- `try/except` + `_logger.exception` 패턴 일관
- `is_game_active` 체크 + 중복 시작 방지
- `if orchestrator is None: return DefaultResponse()` 방어적 처리
- Facade 5개 모두 `if orchestrator is None: return ...()` 방어

### 2.8 확장성 ✅ 96/100

- `bind_orchestrator` 패턴 — 경기 시작 시 자동 주입, 테스트 mock 주입 용이
- Facade 레이어 — engine 변경 시 services 영향 최소화
- `set_camera_service` + `on_game_start` 콜백 — DI 확장 용이

---

## 3. Safe-Now 이슈 목록 (0건)

**Phase 14C 는 Facade 5개가 stub 상태**지만 **의도적 미구현** (주석 명시). Safe-Now 수준 이슈 없음.

---

## 4. Phase 15 Deferred 이슈 (3건)

### P15-14C-01. Facade 5개 실제 engine 데이터 연동 (중요)

- `game_stats_facade`, `highlight_facade`, `referee_facade`, `report_facade`, `tactical_facade` 모두 빈 응답 반환
- **engine 통합 테스트 단계**에서 구현 예정 — API 스키마 계약은 확정, 실제 데이터 조립만 남음
- **우선순위**: Phase 15 에서 engine 완성도 확인 후 일괄 구현

### P15-14C-02. `__init__.py` 2파일 표준화 (14A/14B 통합)

- `services/__init__.py`, `facades/__init__.py` 표준 docstring + `__version__` 적용

### P15-14C-03. `game_service.py` import 순서 정리

- 모듈 상수(`_AGE_GROUP_MAP`, `_GENDER_MAP`) 정의 후 schemas import — 표준 순서로 재배치

---

## 5. 14C 종합 점수

| 축 | 점수 |
|---|---|
| Import 유효성 | 96 |
| 기능 유효성 | 90 |
| 메모리 누수 방지 | 96 |
| 하드코딩 점검 | 95 |
| 한줄 검토 | 92 |
| 스레드 안전성 | 97 |
| 예외 처리 | 94 |
| 확장성 | 96 |
| **총점** | **94.5** |

---

## 6. 관찰된 강점

1. **3층 아키텍처 명확** — Routes → Services → Facades → Engine
2. **`bind_orchestrator` 패턴** — 13 service 전체 일관 (경기 시작 시 자동 주입)
3. **camera_service 완성도** — 13 엔드포인트 + 6 infrastructure 모듈 연동
4. **game_service 콜백 시스템** — `on_game_start` 등록 → 6 서비스 자동 바인딩
5. **batch_sync + cloud_sync 2단 구조** — 오프라인 대비 + 온라인 복구
6. **realtime_stream_service** — ResultDispatcher + WebSocket 통합
7. **Enum 매핑 상수화** — `_AGE_GROUP_MAP`, `_MODE_MAP`, `_RULE_SET_MAP` 명확
8. **Facade 계약 분리** — engine 변경 시 services 영향 격리
9. **`if orchestrator is None: return ...()` 방어 패턴** — 초기화 전 호출 대응
10. **TYPE_CHECKING** 순환 참조 회피 19파일 일관

---

## 7. 관찰된 약점

1. **Facade 5개 stub** — 빈 응답 반환 (통합 테스트 단계 이월)
2. **`__init__.py` 2파일 비어있음** — 14A/14B와 동일 표준 미준수
3. **game_service import 순서** — 모듈 상수 정의 후 import 비표준

---

## 8. 다음 작업

1. Safe-Now 이슈 없음
2. `14_API_SERVER_SUMMARY.md` 통합 총평 작성
