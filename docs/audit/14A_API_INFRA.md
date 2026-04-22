# 14A. api_server/{root + middleware + schemas + websocket} 감사 리포트

**감사 범위**: root (2) + `middleware/` (4) + `schemas/` (3) + `websocket/` (3) = **12파일**
**감사 방식**: 전수 직독 (Read 전용)
**감사 축**: 8종
**감사일**: 2026-04-20

---

## 1. 감사 대상 구성

| 디렉토리 | 파일 | 역할 |
|---|---|---|
| root (2) | `__init__`, `main` | FastAPI 앱 조립 + lifespan + 서비스 DI |
| `middleware/` (4) | `__init__`, `cors_middleware`, `error_handler`, `request_validator` | CORS + 3단 예외 핸들러 + 요청 검증(크기/rate limit) |
| `schemas/` (3) | `__init__`, `request_schemas`, `response_schemas` | Pydantic v2 요청/응답 스키마 35종 |
| `websocket/` (3) | `__init__`, `connection_manager`, `progress_handler` | WebSocket 다중 클라이언트 + 브로드캐스트 |

---

## 2. 감사 8축 평가

### 2.1 Import 유효성 ✅ 95/100

- 12파일 전체 `from __future__ import annotations` 준수 ✓
- FastAPI + Pydantic v2 + starlette 의존성 깔끔 분리
- TYPE_CHECKING 활용 (progress_handler → GameService 순환 참조 회피)
- **관찰**: 4개 `__init__.py` (`api_server/` `middleware/` `schemas/` `websocket/`) 거의 비어있음 (`# -*- coding: utf-8 -*-` 1줄만) — Phase 10~13 표준(docstring + `__version__`)과 일관성 떨어짐

### 2.2 기능 유효성 ✅ 96/100

- **main.py**: FastAPI 앱 완전 조립 — `lifespan` 컨텍스트 + 9 서비스 DI + 라우트 등록 + WebSocket + `on_game_start` 콜백으로 경기 시작 시 orchestrator 바인딩
- **cors_middleware**: 로컬 desktop 용도 `allow_origins=["*"]` — 합리적
- **error_handler**: 3단 예외 처리 (CourtViewException → 특정 HTTP 매핑 / ValueError → 400 / Exception → 500 + traceback 로그)
- **request_validator**: 100MB 크기 제한 + 100req/s rate limit + IP 기반 sliding window
- **request_schemas**: 16종 Pydantic 요청 스키마 (경기/영상/심판/리포트/내보내기/설정/카메라)
- **response_schemas**: 19종 응답 스키마 (공통 래퍼 + 9 도메인별)
- **connection_manager**: WebSocket 다중 클라이언트 + broadcast + 끊어진 연결 자동 제거
- **progress_handler**: demo/일반 모드 분기 + 20msg/tick batch + 10s 간격 진단 로그

### 2.3 메모리 누수 방지 ⚠ 92/100

- WebSocket `ConnectionManager` 끊어진 연결 자동 제거 ✓
- **Safe-Now**: [request_validator.py:44](api_server/middleware/request_validator.py#L44) `_request_counts: dict[str, list[float]]` — 새 IP 등록 시 dict 무한 증가 가능 (각 IP의 timestamp list는 자동 정리되지만 빈 list 된 entry가 dict에 잔존)
- **관찰**: `main.py` 글로벌 9 서비스 인스턴스 — 앱 수명주기와 일치하므로 누수 없음

### 2.4 하드코딩 점검 ✅ 93/100

- `_MAX_CONTENT_LENGTH=100MB`, `_RATE_LIMIT_PER_SEC=100`, `_RATE_WINDOW_SEC=1.0` Final 상수
- WebSocket `timeout=30.0`, `interval_ms=500.0`, batch 20msg — 합리적 기본값
- **관찰**: [main.py:184](api_server/main.py#L184) `/tests/demo_page.html` 경로 하드코딩 — 배포 환경에서 문제 가능성
- **관찰**: `progress_handler._tick % 20 == 0` (10s), `_tick % 40 == 0` (20s) — 진단 로그 주기 매직 넘버

### 2.5 한줄 검토 ⚠ 93/100

- 12파일 전체 docstring + 설명 일관 (main/cors/error/request/schemas/ws)
- **관찰**: 4 `__init__.py` 거의 비어있음 — Phase 10~13 표준 (docstring + `__version__` + `__all__`) 미준수
- Field description 한글 설명 철저 (request/response schemas)

### 2.6 스레드 안전성 ✅ 96/100

- `request_validator` / `connection_manager` RLock 보호 ✓
- WebSocket broadcast 시 방어적 복사 (`targets = list(self._connections)`) ✓
- **관찰**: `progress_handler` 모듈 레벨 `_manager`, `_game_service` 싱글턴 — `set_ws_dependencies` 로 교체 시 thread-safe 보장 없음 (FastAPI 시작 시 1회 주입이므로 실질 문제 없음)

### 2.7 예외 처리 ✅ 97/100

- **3단 예외 핸들러**: `CourtViewException` → HTTP 매핑 / `ValueError` → 400 / `Exception` → 500 + `traceback.format_exc()`
- WebSocket 연결 실패 → `close(code=1011)` + 서버 미초기화 메시지
- `broadcast_loop` 최상위 `except Exception` + 1초 sleep 복구
- Pydantic 자동 검증 → 422 자동 반환

### 2.8 확장성 ✅ 96/100

- `lifespan` 컨텍스트 매니저 — FastAPI 시작/종료 생명주기 명확
- `_bind_orchestrator` 콜백 등록 — 경기 시작 시 6 서비스 자동 바인딩
- Pydantic v2 모델 — 스키마 확장 용이 (새 필드/모델 추가)
- **관찰**: [progress_handler.py:117](api_server/websocket/progress_handler.py#L117) `getattr(go, "_result_dispatcher", None)` — private 속성 외부 접근 (의존성 캡슐화 위반)

---

## 3. Safe-Now 이슈 목록 (1건)

### S44. `request_validator` IP 타임스탬프 dict 누수 가능성

- **파일**: [api_server/middleware/request_validator.py:44](api_server/middleware/request_validator.py#L44)
- **현황**: `_request_counts: dict[str, list[float]] = defaultdict(list)` — 각 IP 별 timestamp list는 자동 정리되지만, 빈 list가 된 entry가 dict에 계속 잔존
- **영향**: 로컬 desktop 환경에서는 IP 변동 적어 실질 영향 미미. 하지만 네트워크 설정/VPN 등으로 IP 변동 시 누적 가능
- **조치**: `dispatch` 끝에 빈 list entry 제거 로직 추가 또는 주기적 정리

```python
# dispatch() 내부 timestamps 정리 후 추가:
if not timestamps:
    self._request_counts.pop(client_ip, None)
```

---

## 4. Phase 15 Deferred 이슈 (4건)

### P15-14A-01. `__init__.py` 4파일 표준화

- `api_server/__init__.py`, `middleware/__init__.py`, `schemas/__init__.py`, `websocket/__init__.py` 모두 `# -*- coding: utf-8 -*-` 1줄만 존재
- Phase 10~13 표준 (docstring + `__version__` + `__all__`) 적용

### P15-14A-02. `main.py` demo_page 경로 하드코딩

- [main.py:184](api_server/main.py#L184) `Path(__file__).parent.parent / "tests" / "demo_page.html"` — 배포 시 `tests/` 디렉토리 위치 보장 안 됨
- **방안**: `IOConfig.demo_page_path` Config 필드로 노출

### P15-14A-03. `progress_handler` private 속성 접근

- [progress_handler.py:117](api_server/websocket/progress_handler.py#L117) `getattr(go, "_result_dispatcher", None)`
- GameOrchestrator 에 `get_result_dispatcher()` public 메서드 도입 권장

### P15-14A-04. `schemas` 파일 `__version__` 누락

- [request_schemas.py](api_server/schemas/request_schemas.py) + [response_schemas.py](api_server/schemas/response_schemas.py) 마지막에 `__version__ = "1.0.0"` 없음
- 다른 모든 Phase 파일과 표준 일관성 확보 필요

---

## 5. 14A 종합 점수

| 축 | 점수 |
|---|---|
| Import 유효성 | 95 |
| 기능 유효성 | 96 |
| 메모리 누수 방지 | 92 |
| 하드코딩 점검 | 93 |
| 한줄 검토 | 93 |
| 스레드 안전성 | 96 |
| 예외 처리 | 97 |
| 확장성 | 96 |
| **총점** | **94.8** |

---

## 6. 관찰된 강점

1. **FastAPI lifespan 완전 조립** — 9 서비스 DI + 카메라 연동 + WebSocket 브로드캐스트 루프 자동 시작/종료
2. **3단 예외 핸들러** — CourtViewException / ValueError / Exception 계층적 매핑
3. **rate limiting + 크기 제한** — IP 기반 sliding window (100req/s, 100MB)
4. **Pydantic v2 스키마 체계** — 16 요청 + 19 응답 + 공통 래퍼 `APIResponse`
5. **WebSocket 자동 연결 관리** — broadcast 시 끊어진 연결 자동 제거
6. **demo + 일반 모드 분기** — `DemoBroadcaster` + `ResultDispatcher` 이중 경로
7. **20msg/tick batch broadcasting** — 과도한 WebSocket 플러딩 방지
8. **10s 간격 진단 로그** — 연결 상태/큐 잔여량 실시간 추적
9. **CORS 로컬 설정** — Electron/웹 프론트엔드 친화적
10. **`_bind_orchestrator` 콜백** — 경기 시작 시 6 서비스 자동 바인딩

---

## 7. 관찰된 약점

1. **`__init__.py` 4파일 표준 미준수** — 거의 빈 파일
2. **`_request_counts` IP dict 누적** — 빈 entry 잔존 (S44)
3. **private 속성 외부 접근** — `_result_dispatcher` 캡슐화 위반
4. **demo_page 경로 하드코딩** — 배포 환경 취약

---

## 8. 다음 작업

1. Safe-Now 1건 즉시 처리 여부 확정 (S44)
2. Phase 14B `routes/v1` 13파일 착수
