# [Plan C] 재연결 임계값 완화 + 쿨다운

**작성일**: 2026-05-13
**선행**: Plan A, B 완료
**목표**: 일시적 네트워크 글리치(300ms ~ 수초)로 watchdog 가 ffmpeg 를 죽이고 재시작하는 패턴을 차단. 재연결 후 일정 시간 동안 stall 감지를 유예해 재연결 루프 폭주를 방지.

---

## 0. 현재 동작 (검증)

[camera_service.py:199-201](api_server/services/camera_service.py#L199-L201)
- `_watchdog_interval_sec = 2.0` — 2초마다 체크
- `_stall_threshold_sec = 3.0` — 3초 무프레임 시 stalled 판정
- 쿨다운 없음

[camera_service.py:467-496](api_server/services/camera_service.py#L467-L496)
```python
while not self._watchdog_stop_event.is_set():
    for handle in handles:
        if handle.decoder.is_stalled(self._stall_threshold_sec):
            self.reconnect_camera(handle.camera_id)   # 즉시 재연결
    self._watchdog_stop_event.wait(2.0)
```

### 시나리오: 4초 네트워크 글리치
1. T=0: 정상
2. T=4: 글리치 → 프레임 4초 없음 → stalled 판정
3. T=4: ffmpeg kill + 새 ffmpeg 시작 (3~5초 소요)
4. T=9: 새 ffmpeg 가 RTSP DESCRIBE 받는 중
5. T=11: 첫 프레임 도착 → 그 사이 5초간 frame=0
6. T=11: 다시 정상화

**vs VLC**: VLC는 동일 글리치에 ffmpeg 재시작 안 함. 그냥 버퍼링하다가 데이터 도착하면 이어서 재생.

### Plan C 가 끝나면 보장되는 것
1. 5초 미만 글리치는 무시 (재연결 안 함)
2. 재연결 후 30초 동안은 stall 감지 일시 정지 (방금 시작한 ffmpeg 가 첫 프레임 받을 시간 보장)
3. 모든 임계값은 환경변수로 override 가능

---

## 1. 변경할 파일 (1개)

| # | 파일 | 변경 내용 |
|---|------|-----------|
| 1 | `api_server/services/camera_service.py` | stall_threshold 기본값 5초로 상향, `_reconnect_cooldown_sec` 신규, _watchdog_loop 에 쿨다운 체크 |

---

## 2. 단계별 상세

### ☑ STEP 1 — 임계값 + 쿨다운 상수

**위치**: [camera_service.py:172-206](api_server/services/camera_service.py#L172-L206)

변경:
- `__slots__` 에 `_reconnect_cooldown_sec` 추가
- `__init__` 에서:
  - `_stall_threshold_sec`: `3.0` → `5.0`
  - `_reconnect_cooldown_sec`: `30.0` 신규
- 환경변수 override 추가:
  ```python
  self._stall_threshold_sec = float(os.environ.get("COURTVIEW_STALL_THRESHOLD_SEC", "5.0"))
  self._reconnect_cooldown_sec = float(os.environ.get("COURTVIEW_RECONNECT_COOLDOWN_SEC", "30.0"))
  ```
- `os` import 확인 (이미 있음 — 같은 파일에서 다른 환경변수 사용 중일 수 있음)

---

### ☑ STEP 2 — _watchdog_loop 에 쿨다운 체크

**위치**: [camera_service.py:479-486](api_server/services/camera_service.py#L479-L486)

기존:
```python
if handle.decoder.is_stalled(self._stall_threshold_sec):
    ...
    self.reconnect_camera(handle.camera_id)
```

변경:
```python
if handle.decoder.is_stalled(self._stall_threshold_sec):
    # Plan C: 재연결 후 쿨다운 동안은 stall 감지 무시 — 방금 시작한 ffmpeg 가
    # 첫 프레임 받을 시간을 보장 (재연결 루프 폭주 방지).
    cooldown_remaining = (
        handle.last_reconnect_time
        + self._reconnect_cooldown_sec
        - time.time()
    )
    if cooldown_remaining > 0:
        _logger.debug(
            "카메라 %s stalled 이지만 쿨다운 %.1fs 남음 — 재연결 보류",
            handle.camera_id, cooldown_remaining,
        )
        continue
    seconds_silent = handle.decoder.seconds_since_last_frame()
    _logger.warning(
        "카메라 %s stalled 감지 (%.1fs 무프레임) — 재연결 시도",
        handle.camera_id, seconds_silent,
    )
    handle.health_status = "stalled"
    self.reconnect_camera(handle.camera_id)
```

---

### ☑ STEP 3 — start_watchdog() 로그에 새 값 노출

**위치**: [camera_service.py:446](api_server/services/camera_service.py#L446) 인근 — watchdog 시작 로그

기존 로그가 `interval, threshold` 만 찍는데, `cooldown` 도 추가.

---

### ☑ STEP 4 — 검증

1. 정상 카메라: stall 감지 없음
2. 카메라 케이블 살짝 흔들어 4초 글리치 → 재연결 발생 안 함 (5초 미만이라 무시)
3. 카메라 전원 끄기 → 5초 후 첫 재연결 → 30초 동안은 추가 재연결 안 함
4. 30초 지나도 stall 계속이면 다시 재연결 시도 (실패 5회 후 failed 고정 — 기존 로직 그대로)

---

## 3. 롤백

환경변수로:
```powershell
$env:COURTVIEW_STALL_THRESHOLD_SEC = "3"
$env:COURTVIEW_RECONNECT_COOLDOWN_SEC = "0"
```

---

## 4. Out of Scope
- 동적 재연결 백오프 (1회 실패 시 5초, 2회 시 10초 등) — 추후
- 재연결 알림 UI 표시 — Plan A 의 health endpoint 에 이미 reconnect_attempts 노출

---

## 5. 예상 시간
약 5분
