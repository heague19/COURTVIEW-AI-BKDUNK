# Plan — RTSP 좀비 세션 방지 (Graceful Shutdown)

작성일: 2026-05-14

## 1. 배경

저가 IPCam (TP-Link VIGI 등) 은 클라이언트 측 RTSP `TEARDOWN` 명령 없이 끊기면 카메라 측 세션 슬롯이 30~120초간 좀비로 남는다. 카메라당 동시 viewer 슬롯이 4~6개 제한이라 좀비 누적 시 새 연결 거부 → 다음 게임 시 카메라 0대 연결.

### 현 코드 검증 결과 (확정)

- `launcher.py:401-410` `_shutdown`: 자식 process 에 `terminate()` → Windows `TerminateProcess` → **atexit/signal handler 실행 X**
- `api_server/main.py`: `app.on_event("shutdown")` 으로 카메라 정리하는 코드 **없음**
- `decoder.close()` → `_stop_ffmpeg_pipe` → `_send_rtsp_teardown` 호출 경로는 **정상 API path 만**
- → **launcher Ctrl+C / 창 닫기 / fatal crash → TEARDOWN 0회 송신 → 100% 좀비 발생**

증거:
- `Tcl_AsyncDelete: async handler deleted by the wrong thread` (이미 매 실행 발생 — fatal C-level exit)
- 어제 8/8 → 오늘 21:04 1/8 → 21:25 0/8 (좀비 누적 패턴)

## 2. 목표

**비정상 종료 (Ctrl+C, 창 닫기, fatal crash) 시에도 모든 카메라에 RTSP TEARDOWN 이 송신되도록 보장.**

## 3. STEP 별 수정 방안

### STEP 1 — engine FastAPI shutdown event 핸들러 추가 (필수)

- [ ] **파일**: `api_server/main.py`
- **변경 내용**: `@app.on_event("shutdown")` 데코레이터로 종료 핸들러 등록. 등록된 모든 카메라 decoder.close() 호출.
- **코드 (예시)**:
  ```python
  @app.on_event("shutdown")
  async def cleanup_rtsp_sessions():
      """engine 종료 시 모든 카메라에 RTSP TEARDOWN 강제 송신."""
      try:
          from api_server.services.camera_service import get_camera_service
          cs = get_camera_service()
          for cam_id, handle in list(cs._cameras.items()):
              try:
                  handle.decoder.close()  # → _stop_ffmpeg_pipe → TEARDOWN
                  logger.info("[SHUTDOWN] %s TEARDOWN 송신", cam_id)
              except Exception as e:
                  logger.warning("[SHUTDOWN] %s 정리 실패: %s", cam_id, e)
      except Exception as e:
          logger.warning("[SHUTDOWN] cleanup 전체 실패: %s", e)
  ```
- **효과**: uvicorn `Ctrl+C` (SIGINT graceful) 시 자동 정리.
- **한계**: `TerminateProcess` 강제 종료 시엔 여전히 실행 안 됨 → STEP 2 필요.

---

### STEP 2 — launcher 가 engine 에 HTTP `/shutdown` 호출 후 graceful 대기 (핵심)

- [ ] **파일**: `launcher.py` (line 401 `_shutdown` 함수)
- **변경 내용**:
  1. 자식 process `terminate()` 직전에 engine HTTP API 호출
  2. graceful 종료 대기 시간 5초 → 15초로 증가
- **코드 (예시)**:
  ```python
  def _shutdown(signum, frame):
      logger.info("종료 신호 수신, RTSP 정리 후 서버 종료 중...")
      # 1. engine 에 graceful shutdown 요청 (모든 카메라 TEARDOWN 시간 확보)
      try:
          import urllib.request
          req = urllib.request.Request(
              "http://127.0.0.1:8000/api/v1/shutdown",
              method="POST",
          )
          urllib.request.urlopen(req, timeout=2)
      except Exception:
          pass
      # 2. 충분히 대기 (8대 × ~1초 TEARDOWN)
      import time
      time.sleep(2)
      # 3. 그 후 terminate
      for proc in (ui_proc, engine_proc):
          if proc.is_alive():
              proc.terminate()
      for proc in (ui_proc, engine_proc):
          proc.join(timeout=15)  # 5 → 15
          if proc.is_alive():
              proc.kill()
      sys.exit(0)
  ```
- **효과**: Ctrl+C 시 engine 에 정리 시간 부여 → 모든 카메라 TEARDOWN 송신.

---

### STEP 3 — `/api/v1/shutdown` endpoint 추가 (STEP 2 와 짝)

- [ ] **파일**: `api_server/routes/v1/` 아래 적당한 위치 (또는 `api_server/main.py` 직접)
- **변경 내용**: POST `/api/v1/shutdown` 받으면 STEP 1 의 cleanup 즉시 실행.
- **코드 (예시)**:
  ```python
  @app.post("/api/v1/shutdown")
  async def shutdown_cameras():
      await cleanup_rtsp_sessions()
      return {"success": True}
  ```
- **보안**: 로컬 only (`127.0.0.1` bind) 이므로 인증 불필요.

---

### STEP 4 — atexit handler 보강 (보너스, 비용 0)

- [ ] **파일**: `api_server/main.py` 또는 `launcher_workers.py:run_engine_server`
- **변경 내용**: `atexit.register(cleanup_rtsp_sessions_sync)` 로 보험 추가.
- **효과**: STEP 1/2 실패해도 Python interpreter 정상 종료 시엔 동작.
- **한계**: `TerminateProcess` 시엔 여전히 실행 안 됨 (Windows 특성).

---

### STEP 5 — Windows console close handler 등록 (선택)

- [ ] **파일**: `launcher.py`
- **변경 내용**: `SetConsoleCtrlHandler` 등록해서 콘솔 창 X 버튼 클릭 시 graceful 종료.
- **방법**: `win32api.SetConsoleCtrlHandler(_shutdown, True)` (pywin32 사용)
- **효과**: PowerShell 창 강제 닫기 시에도 정리.
- **우선순위**: 낮음 (사용자가 보통 Ctrl+C 사용).

---

### STEP 6 — 검증

- [ ] **시나리오 1**: launcher 정상 실행 → 카메라 8대 connect → Ctrl+C
  - 콘솔에 `[SHUTDOWN] cam_0 TEARDOWN 송신` × 8개 출력
- [ ] **시나리오 2**: STEP 6.1 직후 즉시 launcher 재실행 → 8대 즉시 connect 성공 (0대 → 8대)
- [ ] **시나리오 3**: launcher 정상 실행 → 카메라 8대 connect → PowerShell 창 X 버튼
  - STEP 5 적용 시 마찬가지 8개 TEARDOWN 송신

검증 통과 기준:
- 종료 후 즉시 재시작해도 8/8 연결 성공
- 카메라 좀비 슬롯 0개

## 4. 변경 파일 요약

| STEP | 파일 | 변경 양 |
|---|---|---|
| 1 | `api_server/main.py` | 함수 1개 추가 (~15 lines) |
| 2 | `launcher.py:_shutdown` | 함수 수정 (~15 lines) |
| 3 | `api_server/main.py` 또는 routes | endpoint 1개 추가 (~5 lines) |
| 4 | `api_server/main.py` | `atexit.register` 1줄 |
| 5 | `launcher.py` | (선택) Windows console handler |

## 5. 리스크

| 리스크 | 영향 | 완화 |
|---|---|---|
| TEARDOWN 송신 1~2초 × 8대 = 종료 8~16초 지연 | 낮음 | `timeout=2` 로 짧게 |
| `/api/v1/shutdown` endpoint 의도치 않은 호출 | 낮음 | 로컬 bind, optional API key |
| STEP 2 의 urllib timeout 실패 시 fallback | 낮음 | try/except 로 graceful |

## 6. 롤백

각 STEP 가 독립적이라 부분 롤백 가능. git diff 로 되돌리기.

## 7. 우선순위 / 적용 권장

| 우선 | STEP | 내일 경기 전 적용 가치 |
|---|---|---|
| **★★★** | STEP 1 + 2 + 3 | 같이 적용해야 효과. 좀비 100% → 0% |
| ★★ | STEP 4 | 보험. 0 비용. |
| ★ | STEP 5 | 선택. pywin32 의존성 추가. |

**최소 적용**: STEP 1, 2, 3 (3개 파일 ~35 lines 추가). 30분 작업.

## 8. 진행 체크리스트

- [ ] 사용자 승인
- [ ] STEP 1 적용
- [ ] STEP 2 적용
- [ ] STEP 3 적용
- [ ] STEP 4 적용 (선택)
- [ ] STEP 5 적용 (선택)
- [ ] STEP 6 검증 시나리오 1
- [ ] STEP 6 검증 시나리오 2
- [ ] (선택) STEP 6 검증 시나리오 3
- [ ] 내일 경기 전 운영 가이드 업데이트
