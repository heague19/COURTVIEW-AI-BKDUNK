# Phase 17 Session 2 — 헬스 모니터 + 자동 재연결

**실행일**: 2026-04-21
**범위**: Stalled stream 자동 감지 + 재연결 + 사전 probe
**결과**: **5파일 수정, 기존 테스트 251/251 통과, 3개 신규 엔드포인트**

---

## 1. S1 후에도 남는 문제

S1(UDP→TCP + 재시도)으로 **초기 연결** 안정화는 해결. 하지만:

- **경기 중 네트워크 블립** → 카메라 중간에 멈춤 (stalled)
- 현재: 재연결 안 됨 → 사용자가 수동으로 다시 연결 버튼 눌러야 함
- THE RECORD도 **헬스 모니터 없음** (`EncounteredError` 핸들러 부재)
- 우리가 **THE RECORD보다 더 잘할 수 있는 영역**

## 2. 구현 내역

### ✅ `infrastructure/preprocessing/video_decoder.py`

**`DecoderStats` 확장**:
```python
@dataclass
class DecoderStats:
    # 기존 필드 ...
    last_frame_time: float = 0.0         # 성공 프레임 타임스탬프
    consecutive_failures: int = 0        # 연속 실패 카운터
```

**`decode_next()` 계측**:
- 성공 시 `last_frame_time = time.monotonic()` 갱신 + `consecutive_failures = 0`
- 실패 시 `consecutive_failures += 1`

**헬스 체크 메서드 2종**:
```python
def seconds_since_last_frame(self) -> float
def is_stalled(self, threshold_sec: float = 3.0) -> bool
```

판정 기준 (`is_stalled`):
1. `state == DECODING` 이어야 함
2. 최소 1프레임 이상 디코드됨 (연결 직후 유예)
3. 마지막 프레임 이후 `threshold_sec` 경과
4. OR `consecutive_failures >= 30` (~1초 @ 30fps)

**신규 함수 `probe_rtsp(url, timeout_sec)`**:
```python
def probe_rtsp(url, timeout_sec=3.0) -> dict:
    """TCP 연결 + RTSP DESCRIBE 요청으로 사전 검증"""
```
- THE RECORD `EngineRtsp.cs:176-230` 패턴 포팅
- OpenCV 호출 없이 빠른 검증 (~ms 단위)
- 반환: `reachable`, `rtsp_ok`, `status_code`, `server`, `elapsed_ms`, `error`

### ✅ `api_server/services/camera_service.py`

**`_CameraHandle` 확장**:
```python
class _CameraHandle:
    # 기존 필드 ...
    last_reconnect_time: float
    reconnect_attempts: int
    health_status: str  # unknown / healthy / stalled / reconnecting / failed
```

**신규 `reconnect_camera(camera_id)` 메서드**:
- 단일 카메라 디코더 close → 새 인스턴스 → `open()` 호출
- `reconnect_attempts` 카운트 증가
- `max_reconnect_attempts=5` 초과 시 `failed` 고정 (무한 재시도 방지)

**백그라운드 워치도그 스레드** (`start_watchdog` / `stop_watchdog`):
```
2초 간격으로:
  for handle in cameras:
    if handle.connected and not handle.health_status == 'failed':
      if decoder.is_stalled(3.0):
        reconnect_camera(handle.camera_id)
      else:
        health_status = 'healthy'
```

**헬스 조회 `get_health_all()`**:
- 전체 카메라의 `frames_decoded/failed/consecutive_failures/seconds_since_last_frame/health_status` 딕셔너리 반환

### ✅ `api_server/routes/v1/camera_routes.py` — 3 신규 엔드포인트

```
POST /api/v1/camera/{camera_id}/reconnect   단일 카메라 재연결
GET  /api/v1/camera/health                   전체 카메라 헬스 조회
POST /api/v1/camera/probe                    RTSP URL 사전 검증
```

### ✅ `api_server/main.py` — 워치도그 라이프사이클

```python
# startup
_camera_service.start_watchdog()

# shutdown
_camera_service.stop_watchdog()
```

---

## 3. 검증

### 단위 검증
```
1. DecoderStats 확장: last_frame_time=0.0, consecutive_failures=0    ✓
2. VideoDecoder.is_stalled()=False (DECODING 아니면)                 ✓
3. _CameraHandle.health_status='unknown', reconnect_attempts=0       ✓
4. probe_rtsp('rtsp://invalid.test/'):
   reachable=False, error='DNS 오류', elapsed=0.02s                   ✓
5. CameraService 워치도그 시작/종료 라이프사이클                         ✓
```

### HTTP 엔드포인트 (TestClient)
```
GET  /api/v1/camera/health               → 200
POST /api/v1/camera/probe                → 200, success=False
POST /api/v1/camera/nonexistent/reconnect → 404
```

### 회귀 테스트
`tests/motion_analysis` + `tests/feedback_system/templates`: **251/251 통과**

---

## 4. 동작 시나리오

### 시나리오 A: 경기 중 카메라 한 대 일시 단절
```
t=0s   카메라 1~8 정상 연결, health='healthy'
t=60s  cam3 네트워크 단절 → cap.read() 실패 반복
t=60~63s  consecutive_failures 증가, last_frame_time 정지
t=63s  워치도그 감지 (is_stalled=True) → cam3 'stalled'
t=63s  reconnect_camera('cam3') 호출
t=63.3s 재연결 성공 → health='healthy' 복귀
→ cam1/2/4~8 영향 없음, AI 추론 지속
```

### 시나리오 B: 카메라 영구 장애
```
t=0s   cam5 연결
t=30s  네트워크 완전 단절
t=33s  stalled 감지 → reconnect 시도 1/5
t=34s  실패 (decoder.open 재시도 3회 × backoff = ~6s)
...
t=80s  연속 5회 실패 → health='failed', 워치도그 건너뜀
→ 다른 카메라 계속 동작
→ 수동 재연결: POST /api/v1/camera/cam5/reconnect
```

### 시나리오 C: UI 입력 직후 URL 검증
```
사용자가 카메라 URL 입력 → UI가 POST /probe 호출
→ 1.5초 내 결과
  reachable=True, rtsp_ok=True, server='GStreamer'
  → 즉시 'Connect' 버튼 활성화
OR
  reachable=False, error='연결 타임아웃'
  → "카메라에 연결할 수 없습니다" 메시지
```

---

## 5. 영향 + 남은 Session

| 파일 | 변경 | LOC |
|---|---|---|
| `video_decoder.py` | `probe_rtsp` + `is_stalled` + `seconds_since_last_frame` + stats 확장 | +120 |
| `camera_service.py` | `_CameraHandle` 확장 + `reconnect_camera` + 워치도그 + `get_health_all` | +130 |
| `camera_routes.py` | 3 엔드포인트 추가 | +55 |
| `main.py` | 워치도그 자동 시작/종료 | +4 |
| **합계** | **4파일** | **~300 LOC** |

### 남은 Session
- **S3**: 녹화 파이프라인 (THE RECORD R1-R7 하드닝 포팅) — 현장 녹화 깨짐 해결
- **S4**: 통합 스트리밍 (zero-copy decode → 녹화+AI+MJPEG 분기) + CloudSync wire

---

**Phase 17 S2 완료. 현장에서 경기 중 일시 단절이 발생해도 자동 복구 가능.**
