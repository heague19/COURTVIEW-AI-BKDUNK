# COURTVIEW 세션 변경 정리 — 2026-05-13

> **세션 범위**: REPLAY 모드 UI 추가, 녹화 버그 fix, 경기 종료 흐름 보강, 게임 시작 성능 최적화, 진단 로그 인프라.
> **백업**: `_session_backup_2026-05-13_021134/` (원본 21 파일, 818 KB) — 전체 되돌리기 가능.

---

## 0. 빠른 요약 (TL;DR)

| 영역 | 무엇이 바뀌었나 | 효과 |
|------|---------------|------|
| **REPLAY 모드** | UI 페이지 신설 (`/replay`, `/replay/view/{id}`), 백엔드 라우트 5개 (list/sessions/upload/browse/register-path/video), 폴더 picker 모달, 비디오 player + 이벤트 사이드바 | UI 에서 REPLAY 분석 가능 (이전: API 직접 호출만) |
| **녹화 버그 fix** | ffmpeg `-reconnect` 옵션 제거 (HTTP 전용인데 RTSP 에 적용 → 즉시 종료시킴) | 모든 RTSP 녹화 0 바이트 → **정상 작동** |
| **경기 종료 (`stopGame`)** | `recording/stop` + `finalize/game` 호출 추가, timeout 가드 (AbortController), Loading UI, 에러 alert | 종료 안 되던 증상 해결, 카메라 LED 꺼짐, 결과 페이지 데이터 채워짐 |
| **시작 성능 (G+I)** | Orchestrator 백그라운드 사전 빌드, `.pt` 파일 TRT 빌드 시도 차단 | game/start **51초 → ~0초** (LIVE/FIBA 매칭 시) |
| **진단 로그** | SCORE-FLOW / BALL-FLOW / PIPE / DECODE / DISPATCH / WS-BROADCAST / WS-PROXY / GAME-SVC / ORCH / PLAYER-FLOW prefix 도입 | "어디서 막히는지" 한 줄로 파악 가능 |
| **GATE 4-3 토글** | score_detector 의 `above→below` 시간 순서 가드 OFF (검증용) | 분석에서 슛 인정률 ↑ but false positive 위험 ↑ |

---

## 1. 디렉토리 변경 요약

### 신규 파일 (untracked)
```
replay.py                                                    # REPLAY CLI 헬퍼 (API 직접 호출)
courtview_ui/templates/pages/replay.html                     # /replay 페이지 (세션 선택)
courtview_ui/templates/pages/replay_view.html                # /replay/view/{id} 페이지 (비디오+이벤트)
configs/game_analysis/event_detection.yaml.backup_2026-05-11_021211   # STEP1 튜닝 전 백업
engine/io/recording.py.backup_2026-05-13_012451              # -reconnect 제거 전 백업
_session_backup_2026-05-13_021134/                           # 세션 전체 백업 (21 파일)
_session_changes_2026-05-13.md                               # 이 문서
```

### 수정 파일 (M)
| 파일 | 주요 변경 |
|------|----------|
| `launcher.py` | `_SILENCE_VERBOSE` 토글 추가 (진단 로그 일괄 ON/OFF) |
| `api_server/main.py` | lifespan 에 `preload_orchestrator_async()` 호출 |
| `api_server/services/game_service.py` | `[GAME-SVC]` 로그 + Orchestrator 사전 빌드 재사용 |
| `api_server/routes/v1/recording_routes.py` | list/sessions/{id}/video/browse/register-path/upload 라우트 추가 |
| `api_server/websocket/progress_handler.py` | `[WS-BROADCAST]` 메시지 종류 카운트 |
| `configs/game_analysis/event_detection.yaml` | STEP1 임계 튜닝 (min_confidence 0.50→0.30, max_latency 10→30) |
| `detection/ball_detection/ball_detector.py` | `[BALL-FLOW]` 모델 로드/YOLO/필터/색상/형태/결합점수 로그 |
| `detection/player_detection/player_detector.py` | `[PLAYER-FLOW]` 진입/결과 로그 |
| `engine/gpu/tensorrt_pool.py` | `.pt` / 비-ONNX 파일은 `native_*` 핸들로 분기 |
| `engine/io/recording.py` | `-reconnect` 3종 옵션 제거 (RTSP freeze 방지 의도 fix 의 fix) |
| `engine/io/result_dispatcher.py` | `[DISPATCH] 📤` 큐 적재 로그 |
| `engine/orchestrator/game_orchestrator.py` | `[ORCH]` 1️⃣~4️⃣ + 메인 루프 heartbeat + `[SCORE-FLOW]` 1️⃣ 5️⃣ + `[DISPATCH-EVT]` |
| `engine/pipeline/frame_pipeline.py` | `[PIPE F#X]` 1️⃣2️⃣3️⃣ 로그 (50프레임 주기) |
| `game_analysis/game_state/event_detection/score_detector.py` | `[SCORE-FLOW]` 2️⃣~5️⃣ + GATE 1~6 검사 로그 + `_GATE_4_3_STRICT` 토글 |
| `infrastructure/preprocessing/video_decoder.py` | `[DECODE]` 1️⃣~5️⃣ + RTSP reader heartbeat + fetch stale 감지 |
| `courtview_ui/app.py` | `/replay/view/{id}` 라우트, 비디오 스트림 프록시, `[WS-PROXY]` 로그, `game/stop` 타임아웃 30s→5분 |
| `courtview_ui/templates/components/layout.html` | nav 에 REPLAY 항목 추가 |
| `courtview_ui/templates/pages/game_analysis.html` | `stopGame()` 전면 재작성 (A+B+C+D), 종료 버튼에 `id` 추가 |

---

## 2. 기능별 상세

### 2-1. REPLAY 모드 UI 통합

**문제**: 백엔드는 `mode:"replay"` 지원하지만 UI 에 진입점 0건. `curl`/Postman 으로만 가능했음.

**해결**:
- `/replay` 페이지 — 세션 카드 목록 + 폴더 picker + 파일 업로드
- `/replay/view/{session_id}` 페이지 — 비디오 player + 실시간 이벤트 사이드바 (운영자 컨트롤 없는 read-only 뷰)
- 백엔드 라우트:
  - `GET /api/v1/recording/list` — 세션 목록
  - `GET /api/v1/recording/sessions/{id}` — 세션 상세 (카메라/쿼터 매핑)
  - `GET /api/v1/recording/sessions/{id}/video?cam=&q=` — Range 지원 비디오 스트림
  - `GET /api/v1/recording/browse?path=` — 서버 사이드 폴더 탐색 (UI picker 용)
  - `POST /api/v1/recording/register-path` — 외부 폴더 경로 등록 (복사 없이, 매니페스트 기반)
  - `POST /api/v1/recording/upload` — 파일 업로드 (소형 파일용, 멀티파트)

**사용법**: nav → REPLAY → 세션 등록 (폴더 picker / 업로드 / 디스크 경로 입력) → ▶ REPLAY 분석 시작 → 분석 페이지로 자동 이동.

---

### 2-2. 녹화 0 바이트 사고 — `-reconnect` 옵션 제거

**증상**: 모든 RTSP 녹화 세션 폴더가 0 바이트. `.ts`/`.mp4` 파일 0건. `.log` 파일에 `Option reconnect not found` 에러.

**원인**: v0.5.8.6 commit 에서 "5/5 결승 영상 35분 손실 사고 fix" 의도로 `-reconnect`, `-reconnect_streamed`, `-reconnect_delay_max` 추가. 그런데 이 옵션들은 ffmpeg 의 **HTTP demuxer 전용**. RTSP 입력에 적용하면 "Option not found" 로 ffmpeg 즉시 종료. **fix 가 같은 사고를 영구화시킴.**

**해결**: 그 3줄 제거. `-rw_timeout 10000000` 만 남김 (RTSP 도 인식, freeze 방지 효과 유지).

```python
# Before
if is_rtsp:
    args.extend([
        "-rtsp_transport", self._config.rtsp_transport,
        "-reconnect", "1",                # ❌ HTTP 전용
        "-reconnect_streamed", "1",       # ❌
        "-reconnect_delay_max", "5",      # ❌
        "-rw_timeout", "10000000",
    ])

# After
if is_rtsp:
    args.extend([
        "-rtsp_transport", self._config.rtsp_transport,
        "-rw_timeout", "10000000",        # ✓ socket timeout (RTSP 인식)
    ])
```

**되돌리기**: `Copy-Item engine\io\recording.py.backup_2026-05-13_012451 engine\io\recording.py -Force`

---

### 2-3. 경기 종료 (`stopGame`) 흐름 보강

**증상**: 분석 페이지의 "⏹ 종료" 버튼이 작동 안 함. 페이지 멈춤, 카메라 LED 계속 켜짐, 결과 페이지 비어있음.

**원인 (6가지)**:
1. `recording/stop` 호출 없음 → ffmpeg subprocess 좀비 → LED 계속 켜짐
2. fetch 에 timeout 가드 없음 → 페이지 멈춤
3. `finalize/game` 호출 없음 → 결과 페이지 빈상태
4. POST-GAME pipeline 동기 실행 → UI 프록시 30s timeout 초과 위험
5. `try/catch {}` 로 에러 묻음 → 사용자 알림 0
6. Loading UI 부재 → 진행 상황 안 보임

**해결 (A+B+C+D)**:

```javascript
async function stopGame() {
    if (!confirm(...)) return;
    const btn = document.getElementById('ctrl-stop-game');
    if (btn) btn.disabled = true;

    // C) Loading UI
    if (btn) btn.textContent = '⏳ 녹화 종료 중...';

    // A) recording/stop 호출 추가
    const recResult = await callWithTimeout('/api/v1/recording/stop', ...);

    if (btn) btn.textContent = '⏳ 분석 종료 중...';
    const gameResult = await callWithTimeout('/api/v1/game/stop', ...);

    // D) finalize 호출 추가 (최소 payload)
    if (btn) btn.textContent = '⏳ 결과 패키징 중...';
    const finalizeResult = await callWithTimeout('/api/v1/finalize/game', ..., {body: payload});

    // C) 에러 시 confirm
    if (!recResult.ok || !gameResult.ok || !finalizeResult.ok) {
        if (!confirm("일부 실패. 그래도 이동?")) {
            btn.disabled = false; return;
        }
    }
    window.location.href = '/game/result';
}
```

추가로:
- `callWithTimeout()` 헬퍼 — `AbortController` + `signal` 로 timeout 가드
- 응답 코드별 분기 (`ok404: true` 옵션 등)
- 종료 버튼에 `id="ctrl-stop-game"` 부여
- `courtview_ui/app.py` 프록시의 `game/stop` 타임아웃 30s → **300s (5분)** 로 상향 (POST-GAME pipeline 동기 실행 대비)

**되돌리기**: `Copy-Item _session_backup_2026-05-13_021134\courtview_ui\templates\pages\game_analysis.html courtview_ui\templates\pages\game_analysis.html -Force`

---

### 2-4. 시작 성능 최적화 (G + I) — 51초 → ~0초

**증상**: `POST /api/v1/game/start` 응답까지 **51초**. 그동안 페이지 멈춤, 사용자가 답답해서 cancel/새로고침.

**시간 분해**:
- GPU/CUDA stream init: 3초
- CV-BBox TRT engine 로드: 3초
- yolov8_det TRT 로드 + 워밍업: 6초
- **yolov8_pose TRT 빌드 시도 → 실패 → PyTorch 폴백: 5~7초** (← I 대상)
- vitpose_b TRT 로드 (캐시): 3초
- Player/Ball/Hoop detectors + TeamClassifier + JerseyOCR + tracker: 10초
- Motion Analysis 13종 + Event detectors 15종 + AI Referee 23 rules: 5초
- VideoDecoder 8개 (중복 인스턴스) + ffmpeg pipe + reader thread: 5~10초
- 기타: 5초

**I — `.pt` 파일 TRT 빌드 시도 차단**

`engine/gpu/tensorrt_pool.py:_load_model()` 의 분기에 `.pt` 등 비-ONNX 파일 조기 차단 추가.

```python
if model_path and model_path.endswith(".engine"):
    # 이미 빌드된 TRT 엔진 → skip
    entry.engine_handle = f"prebuilt_{model_id.value}"
elif model_path and not model_path.endswith(".onnx"):
    # ★ NEW: .pt / .pth 등 — TRT 빌드 불가 → native 분기 (백엔드가 PyTorch 로 직접 로드)
    entry.engine_handle = f"native_{model_id.value}"
elif _TRT_ENGINE_AVAILABLE and ...:
    # TRT 빌드 (.onnx 만)
    ...
```

→ "MODEL_DESERIALIZE_FAILED" 에러 사라짐, 2~3초 절감.

**G — Orchestrator 백그라운드 사전 빌드**

엔진 부팅 직후, 사용자가 카메라 연결/캘리브 하는 동안 백그라운드 스레드에서 Orchestrator 를 미리 빌드. 사용자가 점프볼 누를 때 이미 준비된 인스턴스 재사용 → **51초 → ~0초**.

```python
# api_server/main.py:lifespan
_game_service.preload_orchestrator_async()  # 백그라운드 스레드 시작

# api_server/services/game_service.py
def preload_orchestrator_async(self):
    threading.Thread(target=self._preload_worker, name="orch-preload", daemon=True).start()

def _preload_worker(self):
    config = EngineConfig(mode=EngineMode.LIVE)
    self._preloaded_orchestrator = GameOrchestrator.build_from_config(config)

def start_game(self, request):
    ...
    if self._preloaded_orchestrator and mode == LIVE and rule_set == FIBA:
        # ★ 재사용 — build skip!
        self._orchestrator = self._preloaded_orchestrator
        # config 의 동적 부분 (recording_enabled, num_cameras, age/gender) 만 업데이트
    else:
        # 일반 빌드 (REPLAY 등 매칭 안 됨)
        self._orchestrator = GameOrchestrator.build_from_config(config)
```

**조건**:
- mode = LIVE (REPLAY/BATCH 매칭 안 됨)
- rule_set = FIBA (NBA/KBL 등 매칭 안 됨)
- 매칭 안 되면 자동으로 일반 빌드 경로로 폴백

**한계**:
- 두 번째 게임은 다시 51초 (preload 가 일회용). 필요하면 `stop_game()` 후 `preload_orchestrator_async()` 재호출 가능.

---

### 2-5. 진단 로그 인프라

**Prefix 규약**:

| Prefix | 위치 | 발화 주기 |
|--------|------|----------|
| `[GAME-SVC]` 1️⃣~5️⃣ | game_service.start_game | 요청당 1회 |
| `[ORCH]` 1️⃣~4️⃣ + 🔁 | game_orchestrator.start_game + main_loop | 시작 1회 + 5초마다 heartbeat |
| `[DECODE cam_X]` 1️⃣~5️⃣ + 🎥 🔄 | video_decoder | open 1회 + 100f 주기 |
| `[PIPE F#X]` 1️⃣2️⃣3️⃣ | frame_pipeline.process_frame | 50f 주기 |
| `[BALL-FLOW]` 📦 + F#X 1️⃣~6️⃣ + 수식 | ball_detector | 모델 로드 1회 + 매 프레임 (스팸 가드) |
| `[PLAYER-FLOW F#X]` 1️⃣2️⃣ | player_detector.process_detections | 50f 주기 |
| `[SCORE F#X] ★ 림접근` | game_orchestrator._build_score_input | 림 5m 내 진입 시 |
| `[SCORE-FLOW F#X]` 1️⃣~5️⃣ + GATE 1~6 | score_detector | 림 5m 내 또는 evidence active 시 |
| `[DISPATCH-EVT]` | game_orchestrator (possession/dead_ball dispatch) | 이벤트 발화 시 |
| `[DISPATCH] 📤` | result_dispatcher._send_websocket | event 메시지마다 + 100건당 |
| `[WS-BROADCAST] 📡` | progress_handler.broadcast_loop | 메시지 전송 시 (종류 카운트) |
| `[WS-PROXY]` 🌐 🔗 📨 🔚 | courtview_ui/app.py:websocket_proxy | 연결/이벤트마다 + 100건당 |

**일괄 ON/OFF**: `launcher.py:106` 의 `_SILENCE_VERBOSE` 토글

```python
_SILENCE_VERBOSE: bool = False    # True = 침묵 (운영용), False = 출력 (디버깅용)
```

**유용한 tail 명령어**:
```powershell
# 종료 관련만
Get-Content -Wait "$env:APPDATA\COURTVIEW\logs\courtview.log" -Tail 0 | Select-String "GAME-SVC|stop|종료|POST-GAME|recording|finalize|Traceback|ERROR"

# 시작 관련만
Get-Content -Wait "$env:APPDATA\COURTVIEW\logs\courtview.log" -Tail 0 | Select-String "GAME-SVC|ORCH|preload|build|TRT"

# 분석 흐름
Get-Content -Wait "$env:APPDATA\COURTVIEW\logs\courtview.log" -Tail 0 | Select-String "SCORE-FLOW|BALL-FLOW|GATE"
```

---

### 2-6. GATE 4-3 토글 (실험)

`score_detector.py:50`:
```python
_GATE_4_3_STRICT: Final[bool] = False    # True = 정상 (above→below 강제), False = 토글 OFF
```

**OFF 시 효과**:
- 슛 아닌 패턴 (rebound, tip, dunk setup) 도 점수로 잡힐 위험 ↑
- 카메라 각도상 below→above 로 보이는 진짜 슛은 인정됨
- **실험용** — 운영 시엔 `True` 권장

---

## 3. 테스트 가이드

### 3-1. 사전 준비
```powershell
# 모든 좀비 정리 (이전 launcher 가 남긴 ffmpeg/go2rtc 등)
Get-Process | Where-Object { $_.ProcessName -in @('python','ffmpeg','go2rtc') } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 포트 확인
Get-NetTCPConnection -LocalPort 8000,3000,8554 -State Listen -ErrorAction SilentlyContinue
# (출력 0줄이면 OK)
```

### 3-2. launcher 시작
```powershell
$env:COURTVIEW_CLOUD_ENABLED = "0"; .\venv\Scripts\python.exe launcher.py
```

### 3-3. 별도 창에서 로그 tail (권장)
```powershell
Get-Content -Wait "$env:APPDATA\COURTVIEW\logs\courtview.log" -Tail 0 | Select-String "GAME-SVC|ORCH|stop|preload|✅|🚀|🔥|❌"
```

### 3-4. 시나리오별 확인 포인트

#### 시나리오 A — LIVE 게임 정상 흐름
1. ✅ launcher 부팅 직후 `[GAME-SVC] 🔥 Orchestrator 사전 빌드 백그라운드 시작 (LIVE/FIBA)` 떠야 함
2. ~50초 후 `[GAME-SVC] ✅ Orchestrator 사전 빌드 완료 (XXXXX ms)` 떠야 함
3. 그 사이에 카메라 연결, 캘리브 가능 (UI 멈춤 없음)
4. 분석 시작 (점프볼) 시 `[GAME-SVC] 4️⃣ 🚀 사전 빌드된 Orchestrator 재사용` 떠야 함
5. → 응답 거의 즉시 (~3초 이내)

#### 시나리오 B — 녹화 정상 작동
1. 카메라 1대 이상 연결
2. UI 에서 녹화 시작
3. 약 15~30초 진행 후 종료
4. 확인:
```powershell
$latest = Get-ChildItem "C:\Users\spoin\Desktop\COURTVIEW_DESK\recordings" -Directory | Sort-Object LastWriteTime -Desc | Select-Object -First 1
Get-ChildItem $latest.FullName -File | Select-Object Name, @{N='Size_MB';E={[math]::Round($_.Length/1MB,2)}}
```
   - `cam_*_Q1.ts` 가 **수 MB 이상** 떠야 함 (이전: 0 바이트)
   - `cam_*_Q1_part1.log` 는 비어있거나 warning 몇 줄만

#### 시나리오 C — 경기 종료 정상
1. 분석 페이지에서 `⏹ 종료` 클릭
2. 버튼 텍스트 변화 관찰:
   - `⏹ 종료` → `⏳ 녹화 종료 중...` → `⏳ 분석 종료 중...` → `⏳ 결과 패키징 중...`
3. `/game/result` 페이지로 자동 이동
4. 카메라 LED 꺼졌는지 확인 (이전: 계속 켜져있음)

#### 시나리오 D — REPLAY 모드
1. nav 의 **REPLAY** 클릭
2. 세션 등록 옵션 3개 중 선택:
   - **📁 폴더 경로 등록**: 영상이 있는 폴더 경로 입력 또는 "📂 찾기…" 모달
   - **📤 파일 업로드**: 작은 mp4 파일 업로드
   - 기존 녹화 세션 카드 클릭
3. 쿼터 선택 → **▶ REPLAY 분석 시작**
4. `/replay/view/{id}` 페이지로 이동, 비디오 + 이벤트 사이드바 표시

### 3-5. 실패 신호

| 증상 | 의심 |
|------|------|
| `[GAME-SVC] 🔥 사전 빌드 시작` 안 보임 | api_server/main.py 의 lifespan hook 변경 적용 안 됨 |
| 사전 빌드는 됐는데 `[GAME-SVC] 🚀 재사용` 안 보임 | mode 불일치 (REPLAY 요청 등) 또는 rule_set 불일치 |
| 녹화 파일 여전히 0 바이트 | `.log` 파일 내용 확인 — `-reconnect` 외 다른 옵션 에러일 가능성 |
| 종료 후 카메라 LED 안 꺼짐 | `recording/stop` 응답 확인 (404 면 세션 없음, 200 이면 정상) |
| 종료 시 페이지 멈춤 | 브라우저 콘솔 (F12) 의 에러 확인. `AbortError` 면 timeout 도달 |
| `MODEL_DESERIALIZE_FAILED` 에러 다시 나옴 | tensorrt_pool.py 의 I 패치 적용 안 됨 |

---

## 4. 되돌리기 (Rollback)

### 4-1. 전체 되돌리기 (이번 세션 전부)
```powershell
Copy-Item "_session_backup_2026-05-13_021134\*" "." -Recurse -Force
```

### 4-2. 개별 파일 되돌리기 (예시)
```powershell
# 녹화 관련만
Copy-Item "engine\io\recording.py.backup_2026-05-13_012451" "engine\io\recording.py" -Force

# stopGame 만
Copy-Item "_session_backup_2026-05-13_021134\courtview_ui\templates\pages\game_analysis.html" "courtview_ui\templates\pages\game_analysis.html" -Force

# event_detection.yaml 만 (STEP1 튜닝 전으로)
Copy-Item "configs\game_analysis\event_detection.yaml.backup_2026-05-11_021211" "configs\game_analysis\event_detection.yaml" -Force
```

### 4-3. 특정 기능만 비활성 (수정 안 하고 토글)

```python
# 진단 로그 OFF
launcher.py:106    _SILENCE_VERBOSE: bool = True

# GATE 4-3 다시 ON (안전 모드)
game_analysis/game_state/event_detection/score_detector.py:50    _GATE_4_3_STRICT: Final[bool] = True

# Orchestrator preload 비활성 (lifespan 에서 호출만 막기)
api_server/main.py:300   # _game_service.preload_orchestrator_async()
```

---

## 5. 알려진 제한 (TODO)

| 항목 | 영향 | 해결 방향 |
|------|------|----------|
| **두 번째 게임 51초 회귀** | preload 가 일회용 — stop 후 다음 game/start 는 다시 51초 | `stop_game()` 끝에 `preload_orchestrator_async()` 재호출 추가 (5줄) |
| **VideoDecoder 중복 인스턴스 (F번 이슈)** | 카메라 1대당 ffmpeg subprocess 2개, reader thread 2개 (CameraService + Orchestrator 별도 생성) — 자원 ×2 | CameraService 의 decoder 를 Orchestrator 가 borrow 하도록 변경 (큰 작업, 30분~2시간) |
| **POST-GAME pipeline 동기 실행** | game/stop 응답이 늦어질 수 있음 (UI 프록시 5분으로 늘려 임시 대응 중) | `stop_game()` 의 `_postgame_pipeline.process()` 를 background task 로 분리 |
| **GATE 4-3 OFF 상태** | rebound/dunk setup 등이 점수로 잘못 잡힐 위험 | 영상 검증 후 다시 `True` 로 (실험 끝나면) |
| **finalize 최소 payload** | analysis 페이지에서 종료 시 player roster / operator_events 없음 | operator 페이지에서 별도 finalize 호출 시 풀 payload 로 덮어쓰기 (이미 idempotent 동작 확인됨) |
| **REPLAY 재생속도/seek 미지원** | `/replay/view` 페이지는 1.0배속 처음부터만 분석 | `/api/v1/game/playback-speed` + `/api/v1/game/seek` 엔드포인트 신규 + UI 슬라이더 |

---

## 6. 파일 위치 참조

### 백업
- 세션 전체: `_session_backup_2026-05-13_021134/` (21 파일, 818 KB)
- recording.py: `engine/io/recording.py.backup_2026-05-13_012451`
- event_detection.yaml: `configs/game_analysis/event_detection.yaml.backup_2026-05-11_021211`

### 신규
- `replay.py` — CLI 헬퍼 (UI 없이 REPLAY 트리거)
- `courtview_ui/templates/pages/replay.html`
- `courtview_ui/templates/pages/replay_view.html`

### 토글 위치
- `launcher.py:106` — `_SILENCE_VERBOSE` (진단 로그)
- `game_analysis/game_state/event_detection/score_detector.py:50` — `_GATE_4_3_STRICT`

### 새 백엔드 라우트
- `GET /api/v1/recording/list`
- `GET /api/v1/recording/sessions/{id}`
- `GET /api/v1/recording/sessions/{id}/video?cam=&q=`
- `GET /api/v1/recording/browse?path=`
- `POST /api/v1/recording/register-path`
- `POST /api/v1/recording/upload`

### 새 UI 라우트
- `GET /replay` — 세션 목록 + 등록
- `GET /replay/view/{session_id}` — REPLAY 결과 뷰어

---

## 7. 변경 이력 (참고)

| 시간 | 작업 |
|------|------|
| 02:11:34 | 세션 전체 백업 생성 (`_session_backup_2026-05-13_021134/`) |
| 02:12 ~ | A+B+C+D — stopGame() 재작성 + UI 프록시 timeout |
| 02:24 ~ | I — `.pt` TRT 빌드 시도 차단 |
| 02:24 ~ | G — Orchestrator preload 인프라 |
| 02:25 ~ | smoke test 통과 |
| 02:30 ~ | 이 문서 작성 |

---

## 8. 본인 테스트 결과 기록란

```
[ ] 시나리오 A: LIVE 게임 시작 ~ 3초 이내 응답
[ ] 시나리오 B: 녹화 파일 수 MB 이상 생성됨
[ ] 시나리오 C: 경기 종료 후 카메라 LED 꺼짐
[ ] 시나리오 D: REPLAY 페이지에서 세션 등록 + 분석 시작 가능

문제 발생 시 메모:
-

추가로 필요한 조정:
-
```

---

**문의 / 다음 단계**:
- 테스트 중 막히면 `Get-Content -Wait` 명령어로 로그 캡처 → 그 시점 로그를 공유
- 두 번째 게임도 빠르게 하려면 → "stop 후 preload 재트리거" 5줄 추가 가능
- VideoDecoder 중복 (F) 정리도 원하시면 → 별도 작업으로 진행

작성: 2026-05-13
