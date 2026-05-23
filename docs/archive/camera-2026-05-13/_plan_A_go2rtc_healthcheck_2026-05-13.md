# [Plan A] go2rtc 헬스체크 + Fallback 가시화

**작성일**: 2026-05-13
**목표**: go2rtc relay 가 실제로 동작 중인지 즉시 판별 가능하게 만들고, fallback(직결 RTSP) 발생 시 UI/로그에서 크게 경고

---

## 0. 왜 이 작업이 필요한가

### 현재 동작 (검증된 사실)
- [api_server/services/camera_service.py:240-254](api_server/services/camera_service.py#L240-L254)
  - `self._go2rtc.add_stream(cam_id, url)` 성공 → `decoder_url = rtsp://127.0.0.1:8554/{cam_id}` (relay 1세션 공유 ✅)
  - 실패 → `decoder_url = url` (카메라 직결, 녹화 ffmpeg 도 같이 직결 → 2-3세션 ❌)
- 현재 fallback 발생 시 단지 `_logger.warning(...)` 한 줄만 찍힘. UI에는 표시 없음.

### 문제
- 사용자가 launcher 콘솔을 일일이 grep 해야 fallback 여부 알 수 있음
- 카메라 8대 중 일부만 fallback 인 경우 식별 불가
- "버벅임" 현상이 fallback 때문인지 다른 원인인지 즉시 판별 불가

### Plan A 가 끝나면 보장되는 것
1. `GET /api/v1/camera/go2rtc/health` 라는 단일 엔드포인트로 전체 상태 1번에 조회 가능
2. 카메라 등록 결과(`relay` / `direct` / `failed`)가 `CameraStatusResponse` 에 노출
3. game_analysis.html 헤더에 fallback 발생 시 빨간색 배너 표시
4. launcher 시작 직후 go2rtc 상태 1줄 요약 로그 (start ok? api ready? streams=N)
5. fallback 카메라가 1대라도 있으면 launcher 콘솔에 ⚠ 로 강조

---

## 1. 변경할 파일 (총 5개)

| # | 파일 | 변경 내용 | 라인 영향 |
|---|------|-----------|-----------|
| 1 | `api_server/services/go2rtc_service.py` | 상태 추적용 카운터 + `get_health()` 메서드 | +60줄 |
| 2 | `api_server/services/camera_service.py` | `_CameraHandle.transport_mode` 필드 + connect_camera 기록 + `get_go2rtc_health()` 통합 | +40줄 |
| 3 | `api_server/schemas/response_schemas.py` | `CameraStatusResponse` 에 `transport_mode` 필드 + `Go2rtcHealthResponse` 신규 | +25줄 |
| 4 | `api_server/routes/v1/camera_routes.py` | `GET /api/v1/camera/go2rtc/health` 라우트 | +20줄 |
| 5 | `courtview_ui/templates/pages/game_analysis.html` | 페이지 로딩 시 헬스 폴링 + 배너 표시 | +60줄 |

---

## 2. 단계별 상세 (체크박스로 진행 추적)

### ☑ STEP 1 — go2rtc_service.py 에 상태 추적 추가

**위치**: [api_server/services/go2rtc_service.py](api_server/services/go2rtc_service.py)

**변경 사항**:
- `__slots__` 에 `_health_lock`, `_add_attempts`, `_add_successes`, `_add_failures`, `_last_failure_msg`, `_last_failure_time` 추가
- `__init__` 에서 초기화
- `add_stream()` 안에서 성공/실패 카운트 증가, 실패 시 마지막 사유 + 시각 저장
- `get_health() -> dict` 신규 메서드:
  ```python
  {
      "running": bool,         # subprocess 살아있나
      "api_ready": bool,       # /api 응답하나
      "add_attempts": int,
      "add_successes": int,
      "add_failures": int,
      "last_failure_msg": str | None,
      "last_failure_time": float | None,
      "api_base": str,         # http://127.0.0.1:1984
  }
  ```
- `api_ready` 는 매번 호출 시 짧은(0.3s) HEAD 요청으로 확인

**테스트 포인트**: 직접 호출하면 dict 반환되는지

---

### ☑ STEP 2 — CameraService 에 transport_mode 기록

**위치**: [api_server/services/camera_service.py](api_server/services/camera_service.py)

**변경 사항**:
1. `_CameraHandle.__slots__` 에 `transport_mode` 추가 (값: `"relay"` / `"direct"` / `"unknown"`)
2. `__init__` 에서 `self.transport_mode: str = "unknown"`
3. `connect_camera()` 함수에서:
   - `registered=True` 시 `handle.transport_mode = "relay"`
   - `registered=False` 시 `handle.transport_mode = "direct"`
   - 기존 `_logger.warning(...)` 메시지에 ⚠ 이모지 추가하고 한 줄 더 진하게
4. `_handle_to_status()` 에서 `transport_mode` 를 응답에 포함
5. 신규 메서드 `get_go2rtc_health() -> dict`:
   - `self._go2rtc.get_health()` 호출 + 각 카메라의 `transport_mode` 집계
   - 반환 구조:
   ```python
   {
       "go2rtc": { ...STEP1 의 get_health 결과... },
       "cameras": [
           {"camera_id": "cam_0", "transport_mode": "relay", "connected": True},
           ...
       ],
       "summary": {
           "total": 8,
           "relay": 7,
           "direct": 1,        # ← 이게 0보다 크면 빨간 배너
           "failed": 0,
       }
   }
   ```

**중요**: `_CameraHandle.__slots__` 수정 시 다른 곳에서 `transport_mode` 참조하는지 grep 으로 확인

---

### ☑ STEP 3 — Response 스키마 확장

**위치**: [api_server/schemas/response_schemas.py](api_server/schemas/response_schemas.py)

**변경 사항**:
1. `CameraStatusResponse` 모델에 `transport_mode: str = "unknown"` 추가 (기본값 두어 기존 호출자 호환)
2. 신규 모델 추가:
   ```python
   class Go2rtcHealthResponse(BaseModel):
       go2rtc: dict
       cameras: list[dict]
       summary: dict
   ```
3. `__all__` 갱신

---

### ☑ STEP 4 — `/api/v1/camera/go2rtc/health` 엔드포인트

**위치**: [api_server/routes/v1/camera_routes.py](api_server/routes/v1/camera_routes.py)

**변경 사항**:
- `# 헬스 모니터링` 섹션(현재 [라인 163-194](api_server/routes/v1/camera_routes.py#L163-L194)) 바로 아래에 추가:
  ```python
  @router.get("/go2rtc/health", response_model=Go2rtcHealthResponse)
  async def get_go2rtc_health(service: CameraService = Depends(get_camera_service)):
      """go2rtc 서비스 + 카메라 transport_mode 통합 조회."""
      return service.get_go2rtc_health()
  ```
- import 에 `Go2rtcHealthResponse` 추가

**라우트 충돌 주의**: `/{camera_id}/status` 보다 위에 두어야 `go2rtc` 가 `camera_id` 로 잡히지 않음. 현재 파일 구조상 `# 헬스 모니터링` 섹션이 `# 상태` 섹션보다 위에 있으니 OK.

**테스트 명령** (작업 후 사용자가 확인 가능):
```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/camera/go2rtc/health | ConvertTo-Json -Depth 4
```

---

### ☑ STEP 5 — UI 배너 (game_analysis.html)

**위치**: [courtview_ui/templates/pages/game_analysis.html](courtview_ui/templates/pages/game_analysis.html)

**변경 사항**:
1. 페이지 최상단(`<body>` 직후, 또는 헤더 영역)에 숨겨진 배너 추가:
   ```html
   <div id="go2rtc-warning-banner" style="display:none; background:#7a1f1f; color:#fff; padding:8px 16px; border-bottom:2px solid #ff4444; font-size:13px;">
     <span id="go2rtc-warning-text">⚠ go2rtc 비정상</span>
     <button id="go2rtc-warning-detail-btn" style="margin-left:12px; padding:2px 8px;">자세히</button>
   </div>
   ```
2. 페이지 로딩 시 `fetchGo2rtcHealth()` 1회 호출 + 이후 30초마다 폴링
3. 응답 결과 분기:
   - `go2rtc.running == false` → 빨간 배너 "go2rtc 프로세스 죽음 — RTSP 미리보기 비활성"
   - `summary.direct > 0` → 주황 배너 "{n}대 카메라가 go2rtc 우회 — 버벅임 위험"
   - `summary.relay == summary.total && total > 0` → 배너 숨김 (정상)
4. "자세히" 버튼 클릭 시 모달 또는 alert 로 카메라별 transport_mode 표시

**스타일**: 기존 페이지 톤(다크) 따름. 빨강 = `#7a1f1f`, 주황 = `#7a5a1f`.

---

### ☑ STEP 6 — launcher 시작 시 1줄 요약 로그

**위치**: [launcher.py](launcher.py) — go2rtc 시작 후 lifespan 이내

**변경 사항**:
- main.py lifespan 또는 launcher.py 에서 `_go2rtc.start()` 직후:
  ```python
  health = _go2rtc.get_health()
  logger.info(
      "[STARTUP] go2rtc running=%s api_ready=%s api_base=%s",
      health["running"], health["api_ready"], health["api_base"],
  )
  if not health["running"] or not health["api_ready"]:
      logger.warning("[STARTUP] ⚠ go2rtc 비정상 — 카메라는 직결 fallback. RTSP 버벅임 위험.")
  ```
- 위치는 main.py lifespan 가 더 자연스러움 — STEP 6 진행 시 결정

---

### ☑ STEP 7 — 검증

사용자가 직접 수행:

1. **launcher 재시작** → 콘솔에 `[STARTUP] go2rtc running=True api_ready=True ...` 보이는지
2. **카메라 1대 연결** → `transport_mode` 가 `"relay"` 인지 (Invoke-RestMethod 로 확인)
3. **일부러 fallback 유도**: go2rtc 를 외부에서 kill → 다시 connect → `transport_mode = "direct"` 가 되고 UI 배너가 주황색으로 뜨는지
4. **배너 자세히 버튼**: 카메라별 모드가 표시되는지

---

## 3. 안전 장치

- 기존 동작에 영향 없음 — 새 필드는 모두 옵셔널, 기존 라우트 그대로
- `Go2rtcService.get_health()` 가 예외 던지면 health 응답에 `"error": "..."` 로 반환 (라우트 자체는 500 안 던짐)
- UI 폴링 실패 시 배너 표시 안 함 (false alarm 방지)

---

## 4. Out of Scope (이 작업에서는 안 함)

- B (HW 디코딩), C (재연결 임계값), D (사전 리사이즈), E (WebRTC 미리보기) — 별도 계획서로
- go2rtc fallback 자동 복구 — 일단 가시화만, 자동 재시도는 추후
- Settings 페이지에도 배너 — game_analysis.html 만 우선

---

## 5. 예상 작업 시간

| STEP | 예상 |
|------|------|
| 1 (go2rtc_service) | 5분 |
| 2 (camera_service) | 10분 |
| 3 (스키마) | 3분 |
| 4 (라우트) | 3분 |
| 5 (UI) | 10분 |
| 6 (launcher 로그) | 3분 |
| **합계** | **약 35분** |

---

## 6. 진행 방식

이 .md 를 위에서 아래로 한 STEP 씩 작업하고, 매 STEP 끝마다 체크박스 ☐ → ☑ 갱신. 모든 STEP 완료 후 사용자에게 STEP 7 검증 시나리오 안내.
