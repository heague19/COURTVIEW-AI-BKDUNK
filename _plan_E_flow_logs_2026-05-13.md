# [Plan E] 카메라 → 경기 분석 데이터 흐름 로그 추가

**작성일**: 2026-05-13
**선행**: A~D + recording rw_timeout fix + analysis_buffer deque
**목표**: 카메라 RTSP 수신부터 분석 결과 산출까지의 데이터 흐름이 어디까지 진행됐는지 launcher 콘솔에서 한눈에 확인 가능하게 만든다. 추가로 엔진 OK/OFFLINE 토글 진단용 timing 정보 노출.

---

## 0. 현재 로그 상태 (이미 있는 것)

세션을 통해 추가한 로그 (이전 작업):
- `[DECODE cam_X]` — RTSP 디코드 ([video_decoder.py](infrastructure/preprocessing/video_decoder.py))
- `[ORCH] 1️⃣~4️⃣` — Orchestrator start_game ([game_orchestrator.py](engine/orchestrator/game_orchestrator.py))
- `[SCORE-FLOW F#X]` — 점수 감지 흐름
- `[GAME-SVC] 1️⃣~5️⃣` — game_service start_game ([game_service.py](api_server/services/game_service.py))
- `[DISPATCH-EVT]` — possession_change / dead_ball 이벤트
- `[STARTUP]` — lifespan 시작 (Plan A/B)

## 0.5 부족한 부분 (추가 필요)

1. **카메라 → frame_pipeline 으로 가는 길** 어디에서도 "이 카메라의 프레임이 N개 처리됐다" 같은 누적 카운터 없음
2. **frame_pipeline → analysis_buffer** 호출 빈도/지연
3. **analysis_buffer → cadence callback (POSSESSION/PERIOD)** 발화 횟수
4. **WebSocket 송신** — UI 로 결과 얼마나 자주 보내는지
5. **이벤트 루프 응답성** — `/health` 가 늦어지는 원인 진단용

---

## 1. 설계 원칙

- **rate-limited**: 매 프레임 로그 절대 금지. 100 프레임마다 or 1초마다 한 줄.
- **flow-stamped**: 각 로그에 `[FLOW]` prefix + 단계 번호 통일 (1️⃣ → 2️⃣ → 3️⃣ ...)
- **toggle 가능**: 환경변수 `COURTVIEW_FLOW_LOG=on/off` (기본 on, 정식 운영 전 off)
- **카운터 기반**: 각 단계마다 통과한 frame_count 누적 → 진행 위치를 즉시 파악

---

## 2. 추가할 로그 (5개 지점)

### ☐ STEP 1 — `[FLOW 1] CAMERA→PIPELINE`
카메라 프레임이 frame_pipeline 으로 들어갈 때.

**위치**: [engine/pipeline/frame_pipeline.py](engine/pipeline/frame_pipeline.py)
`process_frame()` 또는 `__call__()` 진입부 (frame_index 로 throttle).

```python
# 100 프레임마다 한 줄
if frame_index > 0 and frame_index % 100 == 0:
    _logger.info(
        "[FLOW 1] CAMERA→PIPELINE  cam_count=%d frame_index=%d "
        "elapsed_ms_last_100=%.0f",
        len(frames), frame_index, _last_100_elapsed_ms,
    )
```

### ☐ STEP 2 — `[FLOW 2] PIPELINE→BUFFER`
[analysis_buffer.py:206 `ingest_frame()`](engine/analysis_buffer.py#L206) 안.

```python
# 100 프레임마다
if self._total_frames % 100 == 0:
    _logger.info(
        "[FLOW 2] PIPELINE→BUFFER  total_frames=%d "
        "possession_frames=%d period_possessions=%d events=%d",
        self._total_frames, len(self._possession_frames),
        len(self._period_possessions), len(self._event_buffer),
    )
```

이미 deque(maxlen=1800) 적용했으므로 `possession_frames` 길이가 1800 에서 cap 되는지 visibility 확보.

### ☐ STEP 3 — `[FLOW 3] BUFFER→CADENCE`
[game_orchestrator.py:1567 `_possession_cb`](engine/orchestrator/game_orchestrator.py#L1567) 와 `_period_cb`, `_event_cb` 안.

```python
def _possession_cb(_cadence, _keys):
    poss_id = self._state_manager.game_context.possession_count
    _logger.info("[FLOW 3] BUFFER→CADENCE  POSSESSION fire poss_id=%d", poss_id)
    poss_data = self._analysis_buffer.build_possession_data(poss_id)
    aw.submit_possession(poss_id, data=poss_data)
    self._analysis_buffer.flush_possession()
```

매 점유 종료 시 1번만 발화 — rate-limit 불필요.

### ☐ STEP 4 — `[FLOW 4] WS-OUT`
[api_server/websocket/progress_handler.py](api_server/websocket/progress_handler.py) 또는 result_dispatcher 의 broadcast 호출부.

```python
# 100 메시지마다
self._ws_sent += 1
if self._ws_sent % 100 == 0:
    _logger.info(
        "[FLOW 4] WS-OUT  ws_sent=%d connections=%d last_topic=%s",
        self._ws_sent, _ws_manager.connection_count, topic,
    )
```

### ☑ STEP 5 — `[FLOW 0] HEALTH` (엔진 OK/OFFLINE 진단) — 적용됨 2026-05-13
[api_server/main.py:436 `/health`](api_server/main.py#L436)

```python
import time as _time
_h_start = _time.monotonic()
@app.get("/health")
async def health_check():
    _delay = (_time.monotonic() - _h_start_prev) if _h_start_prev else 0
    ...
    if _delay > 4.0:   # 5초 폴링 주기에서 4초 이상 갭이면 블로킹 의심
        _logger.warning(
            "[FLOW 0] HEALTH  ⚠ 응답 갭 %.2fs (event loop 블로킹 의심)", _delay,
        )
```

이게 활성화되면 어느 순간에 이벤트 루프가 블로킹되는지 timestamp 로 추적 가능.

---

## 3. 추가 변경 (엔진 OK/OFFLINE 즉시 완화)

### ☐ STEP 6 — UI /health timeout 3 → 8초

**위치**: [courtview_ui/app.py:638](courtview_ui/app.py#L638)

```python
# Before
async with httpx.AsyncClient(timeout=3.0) as client:
# After
async with httpx.AsyncClient(timeout=8.0) as client:
```

이유:
- engine 이 GIL 잠시 잡혀도 OFFLINE 으로 안 떨어짐
- 진짜 죽은 경우는 8초도 안 응답 → 동작 동일
- 깜빡이는 빈도 감소

---

## 4. 환경변수 토글

```python
_FLOW_LOG_ENABLED: Final[bool] = os.environ.get("COURTVIEW_FLOW_LOG", "on").lower() != "off"
```

각 FLOW 로그 앞에 `if _FLOW_LOG_ENABLED:` 가드. 사용자가 정식 운영 시 `COURTVIEW_FLOW_LOG=off` 로 끌 수 있음.

---

## 5. 단계별 결과 흐름 예시 (정상 동작 시 콘솔에 보이는 패턴)

```
[FLOW 1] CAMERA→PIPELINE  cam_count=8 frame_index=100 elapsed_ms_last_100=3340
[FLOW 2] PIPELINE→BUFFER  total_frames=100 possession_frames=100 period_possessions=0 events=0
[FLOW 1] CAMERA→PIPELINE  cam_count=8 frame_index=200 elapsed_ms_last_100=3320
[FLOW 2] PIPELINE→BUFFER  total_frames=200 possession_frames=200 period_possessions=0 events=2
[FLOW 4] WS-OUT  ws_sent=100 connections=1 last_topic=score
[FLOW 3] BUFFER→CADENCE  POSSESSION fire poss_id=1
[FLOW 2] PIPELINE→BUFFER  total_frames=300 possession_frames=12 period_possessions=1 events=4  ← flush 후 12로 떨어짐
...
```

이상이 보이면:
- FLOW 1 만 흐르고 FLOW 2 가 멈춤 → frame_pipeline → ingest 호출 누락
- FLOW 2 의 `possession_frames` 가 1800 에서 멈춤 → cadence callback 발화 안 됨 (deque cap 도달 = 점유 종료 못 잡음)
- FLOW 3 발화 빈도 0 → score 감지 GATE 4-3 같은 이슈 의심
- FLOW 4 안 보임 → WS 끊김

---

## 6. 변경할 파일 (6개)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `engine/pipeline/frame_pipeline.py` | FLOW 1 |
| 2 | `engine/analysis_buffer.py` | FLOW 2 |
| 3 | `engine/orchestrator/game_orchestrator.py` | FLOW 3 (3곳 — possession/period/event cb) |
| 4 | `api_server/websocket/progress_handler.py` 또는 dispatcher | FLOW 4 |
| 5 | `api_server/main.py` | FLOW 0 (HEALTH 갭 측정) |
| 6 | `courtview_ui/app.py` | timeout 3→8 |

---

## 7. 진행 순서

1. STEP 6 (timeout 즉시 완화) — 1줄, 즉시 OK/OFFLINE 깜빡임 감소
2. STEP 5 (HEALTH 갭 측정) — 블로킹 발생 시점 visibility
3. STEP 1~4 (FLOW 1~4) — 데이터 흐름 추적

---

## 8. 롤백
환경변수 `COURTVIEW_FLOW_LOG=off` 로 모든 FLOW 로그 무력화.
timeout 변경은 단일 라인이라 즉시 git revert 가능.

---

## 9. Out of Scope
- 매 프레임 로그 (이미 너무 많음)
- 로그 파일 분리 (현재 launcher 콘솔로 충분)
- Prometheus / metric export
