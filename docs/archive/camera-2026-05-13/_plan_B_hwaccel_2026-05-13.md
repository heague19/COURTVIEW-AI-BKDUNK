# [Plan B] ffmpeg HW 디코딩 옵션 추가 (Windows D3D11VA / NVIDIA CUDA)

**작성일**: 2026-05-13
**선행**: Plan A 완료
**목표**: ffmpeg subprocess가 1080p×8 카메라를 CPU 1코어로 디코딩하던 것을 GPU(또는 통합 그래픽) HW 디코더로 옮겨 CPU 부하를 80% 이상 감소시킨다.

---

## 0. 왜 이 작업이 필요한가

### 현재 (검증)
[video_decoder.py:957-972](infrastructure/preprocessing/video_decoder.py#L957-L972)
```python
cmd = [
    ffmpeg_exe,
    "-rtsp_transport", "tcp",
    "-fflags", "nobuffer+discardcorrupt", "-flags", "low_delay",
    "-max_delay", "0", "-reorder_queue_size", "0",
    "-probesize", "32", "-analyzeduration", "0",
    "-i", url,
    "-f", "rawvideo", "-pix_fmt", "bgr24",
    "-an", "-sn", "-loglevel", "error",
    "-",
]
```

- ❌ `-hwaccel` 옵션 없음 → ffmpeg가 H.264 디코딩을 **CPU SW로** 수행
- 1080p@30fps × 8대 = 250M 픽셀/초를 CPU만으로 처리
- VLC/OBS 는 Windows에서 D3D11VA 또는 DXVA2 HW 디코딩을 기본 사용 → CPU 부하 거의 0
- 우리는 동일 카메라/네트워크 환경에서도 CPU 병목 → reader thread stall → 버벅임

### Plan B 가 끝나면 보장되는 것
1. ffmpeg가 H.264 / H.265 영상을 GPU HW 디코더에 위임 → CPU 부하 1코어 100% → 1코어 10~20% 수준
2. 환경변수 `COURTVIEW_HWACCEL` 로 모드 토글 가능 (`d3d11va` / `cuda` / `off`)
3. 시작 로그에 hwaccel 모드 명확히 표시
4. 호환 안 되는 카메라가 있어도 `off` 로 즉시 무력화 가능 (안전장치)

---

## 1. 핵심 기술 결정

### 선택: `-hwaccel d3d11va` (기본값)
- Windows 8 이상 표준 — Intel iGPU, NVIDIA, AMD 전부 지원
- H.264 / H.265 디코딩 → DXVA 인터페이스 → GPU 디코더 블록
- `-hwaccel_output_format` 미지정 시 ffmpeg가 자동으로 system memory 로 download → 우리 기존 `-pix_fmt bgr24` 파이프 그대로 호환

### 선택지: `cuda` (NVIDIA 전용, 더 빠름)
- NVDEC 사용 — D3D11VA 보다 약간 빠르지만 NVIDIA 카드 + 드라이버 필수
- 일반 사용자 환경에서는 d3d11va 가 더 호환성 높음

### 선택지: `off` (현재 동작)
- 옛 동작 그대로 SW 디코딩 — 호환성 100% 보장 (롤백 안전망)

### 위험 요소
1. **저가 IPCam 의 H.265 + 비표준 SPS/PPS** — HW 디코더가 거절할 수 있음 → ffmpeg 시작 시 stderr 에 에러
2. **드라이버 부재/이상** — Windows GPU 드라이버 outdated 시 d3d11va init 실패
3. **rawvideo bgr24 변환 비용** — HW decode 결과를 GPU→CPU 복사 + YUV→BGR 변환. 그래도 SW decode 보다는 훨씬 가벼움.

### 안전장치
- 환경변수로 즉시 off 가능
- 시작 시 ffmpeg stderr 의 첫 N줄을 캡처해 hwaccel init 실패 키워드 검출 → 로그로 경고

---

## 2. 변경할 파일 (총 3개)

| # | 파일 | 변경 내용 | 라인 |
|---|------|-----------|------|
| 1 | `engine/config.py` (또는 신규 상수) | `HWACCEL_MODE` 상수 + 환경변수 읽기 | +20줄 |
| 2 | `infrastructure/preprocessing/video_decoder.py` | `_start_ffmpeg_pipe()`에 hwaccel 옵션 prepend | +25줄 |
| 3 | `api_server/main.py` lifespan | 시작 시 hwaccel 모드 1줄 로그 | +5줄 |

> Plan A 와 같은 구조지만 작업 분량은 더 작음.

---

## 3. 단계별 상세

### ☑ STEP 1 — HWACCEL_MODE 상수 정의

**위치**: [infrastructure/preprocessing/video_decoder.py](infrastructure/preprocessing/video_decoder.py) 모듈 상단

config.py 에 두는 게 정석이지만, video_decoder.py 가 단독으로 import 되는 경우가 많아 같은 파일에 두는 편이 conflict 없음.

```python
# Plan B (2026-05-13): ffmpeg HW 디코딩 모드.
#   - "d3d11va": Windows 디폴트, Intel/NVIDIA/AMD 호환 (기본값)
#   - "cuda":    NVIDIA 전용, NVDEC 사용 (약간 더 빠름)
#   - "off":     SW 디코딩 (롤백 안전망 — 기존 동작과 동일)
# 환경변수 COURTVIEW_HWACCEL 로 override 가능.
_HWACCEL_MODE: Final[str] = os.environ.get("COURTVIEW_HWACCEL", "d3d11va").strip().lower()
_HWACCEL_VALID: Final[frozenset[str]] = frozenset({"d3d11va", "cuda", "off"})
if _HWACCEL_MODE not in _HWACCEL_VALID:
    _logger.warning("COURTVIEW_HWACCEL=%r 인식 불가 — 'off' 로 강제", _HWACCEL_MODE)
    _HWACCEL_MODE = "off"
```

- `os` 가 import 안 돼 있으면 추가 (확인 필요)
- `_logger` 는 기존 모듈 로거 사용

---

### ☑ STEP 2 — _start_ffmpeg_pipe()에 hwaccel 옵션 추가

**위치**: [video_decoder.py:957](infrastructure/preprocessing/video_decoder.py#L957) 의 `cmd = [...]` 부분

```python
cmd = [ffmpeg_exe]
# Plan B: hwaccel 옵션은 -i 보다 앞에 와야 함 (ffmpeg arg ordering 규칙).
if _HWACCEL_MODE == "d3d11va":
    cmd += ["-hwaccel", "d3d11va"]
elif _HWACCEL_MODE == "cuda":
    cmd += ["-hwaccel", "cuda"]
# off → 옵션 추가 안 함 = 기존 동작
cmd += [
    "-rtsp_transport", "tcp",
    "-fflags", "nobuffer+discardcorrupt",
    ...  # 기존 그대로
]
```

**핵심 주의**: `-hwaccel` 은 input 옵션 → `-i URL` **앞에** 와야 함. 뒤에 두면 무시됨.

**호환성 보장**:
- `-hwaccel_output_format` 미지정 시 → ffmpeg가 자동으로 system memory 로 frame download
- 우리 기존 `-pix_fmt bgr24` 그대로 동작
- HW init 실패해도 ffmpeg는 즉시 종료하지 않고 SW fallback 시도 (버전에 따라 다름)

**시작 로그 갱신**: 기존 [987-992](infrastructure/preprocessing/video_decoder.py#L987-L992) 로그에 hwaccel 표시 추가:
```python
_logger.info(
    "[DECODE %s] ffmpeg pipe 시작 → pid=%d %dx%d "
    "(hwaccel=%s, transport=tcp, pix=bgr24)",
    self._camera_id, self._ffmpeg_proc.pid, width, height, _HWACCEL_MODE,
)
```

---

### ☑ STEP 3 — main.py lifespan 시작 시 hwaccel 1줄 로그

**위치**: [api_server/main.py](api_server/main.py) lifespan startup, Plan A 의 STARTUP 로그 바로 옆

```python
# Plan B: ffmpeg HW 디코딩 모드 가시화
try:
    from infrastructure.preprocessing.video_decoder import _HWACCEL_MODE
    _logger.info("[STARTUP] ffmpeg HW decode mode = %r", _HWACCEL_MODE)
    if _HWACCEL_MODE == "off":
        _logger.warning(
            "[STARTUP] ⚠ HW 디코딩 비활성 — CPU 로만 RTSP 디코딩. "
            "8 카메라 × 1080p 환경에서 CPU 병목 위험. "
            "환경변수 COURTVIEW_HWACCEL=d3d11va 로 활성화 권장.",
        )
except Exception:
    _logger.exception("[STARTUP] hwaccel 모드 조회 실패 (무시)")
```

---

### ☑ STEP 4 — 검증

사용자 직접 수행:

1. **기본 동작 (d3d11va)**
   - launcher 재시작 → `[STARTUP] ffmpeg HW decode mode = 'd3d11va'` 로그
   - 카메라 연결 → `[DECODE cam_0] ffmpeg pipe 시작 → ... (hwaccel=d3d11va, ...)`
   - Windows 작업관리자에서 ffmpeg 프로세스 GPU 사용률↑, CPU↓ 확인 (NVIDIA = "Video Decode" 그래프)

2. **fallback (off) — 호환성 문제 시**
   ```powershell
   $env:COURTVIEW_HWACCEL = "off"
   # launcher 재시작
   ```
   → `[STARTUP] ⚠ HW 디코딩 비활성 ...` 경고 + 카메라 정상 연결

3. **NVIDIA 환경에서 cuda 시도**
   ```powershell
   $env:COURTVIEW_HWACCEL = "cuda"
   ```
   → 더 빠른 NVDEC 사용

4. **체감 차이**
   - CPU 사용률: 8대 동시 분석 시 80% → 20% 수준 예상
   - 프리뷰 영상 끊김 감소 (reader thread starvation 완화)

---

## 4. 롤백 방법

가장 빠른 롤백: 환경변수만 설정
```powershell
$env:COURTVIEW_HWACCEL = "off"
```
재시작하면 기존 SW 디코딩으로 즉시 복귀.

코드 롤백이 필요하면 변경된 3개 파일을 git diff 로 revert.

---

## 5. Out of Scope

- D (ffmpeg `-s WxH` 사전 리사이즈) — 다음 작업
- C (재연결 임계값) — Plan C 로 별도
- E (WebRTC 미리보기) — 큰 변경, 마지막에
- HW init 실패 자동 감지 + SW fallback — 일단 환경변수로만 토글. 자동 fallback은 stderr 파싱 필요해서 v2 에서 추가 가능.

---

## 6. 예상 작업 시간

| STEP | 예상 |
|------|------|
| 1 (상수 정의) | 3분 |
| 2 (ffmpeg 옵션) | 5분 |
| 3 (lifespan 로그) | 3분 |
| **합계** | **약 10분** |

---

## 7. 진행 방식

위에서 아래로 STEP 단위 작업, 매 STEP 끝마다 ☐ → ☑.
