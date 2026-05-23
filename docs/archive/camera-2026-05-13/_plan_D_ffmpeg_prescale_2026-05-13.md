# [Plan D] ffmpeg 사전 리사이즈로 cv2.resize 제거

**작성일**: 2026-05-13
**선행**: Plan A, B, C 완료
**목표**: reader thread 가 매 프레임 호출하던 `cv2.resize(frame, target)` 를 ffmpeg subprocess 에 위임. Python GIL 점유 시간 단축 + 메모리 복사 1회 절약.

---

## 0. 현재 동작 (검증)

[video_decoder.py:1170-1232](infrastructure/preprocessing/video_decoder.py#L1170-L1232)
```python
target_w, target_h = ANALYSIS_NORMALIZED_RESOLUTION  # (1920, 1080)
need_resize = (w > target_w) or (h > target_h)
...
while reader loop:
    frame = np.frombuffer(...).reshape(h, w, 3)   # native 해상도
    if need_resize:
        frame = cv2.resize(frame, (target_w, target_h), cv2.INTER_AREA)  # ← GIL 점유
```

- 카메라가 1080p 출력하면 `need_resize=False` → 영향 없음
- 카메라가 4K 출력하면 `need_resize=True` → 매 프레임 4K→1080p resize (수 ms × 카메라 수)
- ffmpeg 가 더 빠르게 할 수 있는 작업을 Python 단에서 GIL 잡고 함

### Plan D 가 끝나면 보장되는 것
1. ffmpeg가 디코딩 직후 GPU/CPU 단에서 바로 target 해상도로 스케일 → Python 에는 이미 리사이즈된 프레임만 도착
2. `reader_loop` 내 `cv2.resize` 호출 제거 → GIL 점유 시간 감소
3. `np.frombuffer` 의 `frame_size` 가 작아짐(4K→1080p 시 6.2MB→6.2MB 동일하지 않고 → 6MB → 6MB... 잠깐 1080p 는 1920*1080*3 = 6.2MB, 4K 는 3840*2160*3 = 25MB). 정확히 25MB → 6.2MB 로 4배 감소.
4. `_latest_frame` 의 `frame.copy()` 도 6.2MB 만 복사

---

## 1. 기술 결정

### 선택 옵션
**선택**: ffmpeg output 옵션으로 `-s {target_w}x{target_h}` 추가 (need_resize 일 때만)

이유:
- ffmpeg 가 자동으로 적절한 scale filter 삽입
- HW 디코딩 (Plan B 의 d3d11va/cuda) 과 호환 — ffmpeg가 자동 hwdownload + sws_scale
- `-vf scale` 보다 호환성 높음 (filter graph 충돌 없음)

### 위험
- 카메라 native 가 정확히 1920x1080 인 경우 ffmpeg 가 `-s` 무시 (no-op) → 성능 영향 0
- 카메라 native > target 인 경우만 효과
- aspect ratio 비대칭 카메라 (1280x720 vs target 1920x1080) — `-s` 강제 스케일 → 약간 늘어남. 현재 cv2.resize 도 동일 동작이므로 호환.

### 안전장치
- ffmpeg 가 사전 리사이즈하므로 `reader_loop` 의 `frame_size` 계산도 target 기준으로 변경 필요
- need_resize=False (native ≤ target) 인 경우는 그대로 native 통과 → 변경 없음

---

## 2. 변경할 파일 (1개)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `infrastructure/preprocessing/video_decoder.py` | `_start_ffmpeg_pipe()` 에 `-s` 옵션 + `reader_loop` 의 cv2.resize 제거 |

---

## 3. 단계별 상세

### ☑ STEP 1 — _start_ffmpeg_pipe 시그니처 확장 + -s 옵션 추가

[video_decoder.py:949](infrastructure/preprocessing/video_decoder.py#L949)

기존:
```python
def _start_ffmpeg_pipe(self, url: str, width: int, height: int) -> None:
```

변경: target 해상도도 받음 (호출부에서 native + target 둘 다 전달)
```python
def _start_ffmpeg_pipe(
    self, url: str, width: int, height: int,
    target_width: int, target_height: int,
) -> None:
```

cmd 구성 시:
- output 직전 위치 (`"-f", "rawvideo"` 앞)에:
  ```python
  if width > target_width or height > target_height:
      cmd += ["-s", f"{target_width}x{target_height}"]
      out_w, out_h = target_width, target_height
  else:
      out_w, out_h = width, height
  ```
- `self._ffmpeg_width = out_w`, `self._ffmpeg_height = out_h` 저장 (reader 가 읽을 frame_size 계산용)

---

### ☑ STEP 2 — open() 에서 target 전달

[video_decoder.py:830](infrastructure/preprocessing/video_decoder.py#L830)

기존:
```python
self._start_ffmpeg_pipe(file_path, width, height)
```

변경:
```python
from shared.constants.video_constants import ANALYSIS_NORMALIZED_RESOLUTION
target_w, target_h = ANALYSIS_NORMALIZED_RESOLUTION
self._start_ffmpeg_pipe(file_path, width, height, target_w, target_h)
```

(import 는 이미 상단에서 했을 수도 — 확인 후 처리)

---

### ☑ STEP 3 — reader_loop 의 cv2.resize 제거

[video_decoder.py:1170-1232](infrastructure/preprocessing/video_decoder.py#L1170-L1232)

기존:
```python
w = self._ffmpeg_width   # native
h = self._ffmpeg_height
target_w, target_h = ANALYSIS_NORMALIZED_RESOLUTION
need_resize = (w > target_w) or (h > target_h)
...
frame = np.frombuffer(...).reshape(h, w, 3)
if need_resize:
    frame = cv2.resize(frame, (target_w, target_h), cv2.INTER_AREA)
```

변경: `_ffmpeg_width/height` 가 이미 ffmpeg 출력 해상도 (사전 리사이즈된 값) 이므로 그냥 그대로 사용:
```python
w = self._ffmpeg_width   # = ffmpeg 가 출력하는 해상도 (이미 target 으로 스케일됨)
h = self._ffmpeg_height
frame_size = w * h * 3
# Plan D: cv2.resize 제거 — ffmpeg 가 사전 스케일.
...
frame = np.frombuffer(...).reshape(h, w, 3)
# (cv2.resize 호출 삭제)
```

기존 로그 `need_resize=...` 도 정리.

---

### ☑ STEP 4 — get_or_decode_latest_jpeg / 미리보기에서도 동일하게

[video_decoder.py:1306-1309](infrastructure/preprocessing/video_decoder.py#L1306-L1309)

이 부분은 `_latest_frame` 을 받아서 JPEG 인코딩 전에 한번 더 리사이즈하는 코드. ffmpeg 가 이미 리사이즈했으면 native > target 케이스가 사라지므로 dead branch. 그러나 file 모드(파일 디코드) 에서는 여전히 cv2.resize 필요할 수 있음 → 지금은 건드리지 않고 그대로 둠 (Out of Scope).

---

### ☑ STEP 5 — 검증

1. 1080p 카메라 연결 → ffmpeg cmd 에 `-s` 없음, 동작 동일
2. 4K 카메라 연결 → ffmpeg cmd 에 `-s 1920x1080` 추가, reader frame_size = 6.2MB
3. `[DECODE cam_X] ffmpeg pipe 시작` 로그에 출력 해상도 표시
4. CPU 사용률: 4K 카메라 8대 환경에서 reader thread CPU 사용률 감소 측정

---

## 4. 롤백
환경변수 토글 안 만들었음 (단순 코드 경로 — 문제 없으면 그대로 유지).
필요 시 git revert 로 3개 hunk 되돌리기.

---

## 5. Out of Scope
- file mode 의 cv2.resize 제거 — RTSP 만 우선
- `-vf scale=...:flags=area` 처럼 ffmpeg scale 알고리즘 명시 — 기본값(bicubic)으로 충분

---

## 6. 예상 시간
약 10분.
