# Plan — FrameIngestion ffmpeg stderr 캡처 (옵션 A)

## 목표
`infrastructure/preprocessing/video_decoder.py:1026` 의 `stderr=subprocess.DEVNULL` 때문에
우리쪽 ffmpeg consumer 가 왜 RTSP relay 에 붙은 뒤 ~1.4 초 만에 죽는지가 안 보임.
stderr 를 카메라별 파일로 redirect 해서 첫 frame 못 받는 진짜 원인을 확인.

## 배경 (go2rtc.log debug 분석)
- 카메라 `/11` sub-stream codec = **HEVC** (H.265). go2rtc 가 `-c:v libx264 -preset superfast` 로 CPU 트랜스코딩.
- producer (go2rtc → 카메라) 는 1.2초 만에 ready, "start producer" 정상 발화.
- **consumer (우리 ffmpeg → relay) 가 ~1.4~2.7초 만에 EOF**. 무한 reconnect 루프.
- → buffer 영원히 empty → 분석 0건.

## 가설
1. `-probesize 32 -analyzeduration 0` 이 너무 작아 relay h264 stream 의 SPS/PPS 못 읽고 die
2. `-hwaccel d3d11va` 가 stream metadata 부족으로 init 실패
3. relay 의 첫 keyframe 도착 전 timeout

stderr 보면 위 셋 중 어느 것 (혹은 다른 것) 인지 즉시 판단 가능.

## STEP

- [x] STEP 1 — 계획서 작성
- [x] STEP 2 — `video_decoder.py:_start_ffmpeg_pipe` 수정: stderr → `_appdata/logs/ffmpeg_<camera_id>.log` 파일로 redirect (+ `-loglevel info`)
- [x] STEP 3 — 잔류 프로세스/포트 정리
- [x] STEP 4 — 사용자: launcher 재실행 + 카메라 connect + game/start (1-2분)
- [x] STEP 5 — `_appdata/logs/ffmpeg_cam_0.log` 등 분석 → 진짜 fail 원인 식별
  - **발견**: ffmpeg subprocess 정상, frame=7000+ 디코딩, 0.95x realtime
  - **진짜 원인**: ffmpeg output 실제 해상도 = **640x480** (sub-stream native)
  - 그러나 FrameIngestion 은 1920x1080 으로 reader frame_size 계산
  - → reader 가 1920×1080×3 = 6.2MB 기다리는데 실제 921KB/frame 흐름
  - → 첫 frame 도착 무한 대기 → buffer 영원히 empty
- [x] STEP 6 (옵션 B2) — `_start_ffmpeg_pipe` 에서 ffmpeg 실제 output 해상도를 stderr 파싱으로 detect → `_ffmpeg_width/height` 재설정
  - 방법: stderr 파일을 polling (max 2초) 하며 `Stream #0:0 ... WxH` 정규식 매치
  - **결과**: 가설 빗나감. native 가 이미 640x480 으로 알려져 있었음 (frame_size mismatch 아님).
  - **부작용**: polling sleep 이 event loop 블로킹 → HEALTH 41초, proxy 30s timeout.

## 추가: 모든 단계 진단 로그 부착 (STEP 7~9)

frame 경로 모든 분기에 flow_logger 진단 박아서 진짜 막힌 곳 식별.

```
ffmpeg → stdout.read → np.reshape → _latest_frame → decode_next() → normalize → aligner.add_frame → try_align
            (A)            (B)           (C)            (D)             (E)            (F)
```

- [x] STEP 7 — stderr polling 코드 제거 (event loop 블로킹 해소)
- [x] STEP 8 — `video_decoder._rtsp_reader_loop` 의 각 분기에 flow_logger 추가
  - READ-ENTER (reader 진입)
  - READ-FIRST-CHUNK (첫 chunk 도착)
  - READ-FIRST-FRAME (첫 frame reshape 성공)
  - READ-EOF / READ-EXC / READ-RESHAPE-FAIL
  - FETCH-WAIT-TIMEOUT (decode_next 가 frame 못 받음)
- [x] STEP 9 — `FrameIngestion.capture_and_align` 의 카메라별 for-loop 에 flow_logger 추가
  - CAA-DECODE-OK / CAA-NONE / CAA-INVALID / CAA-DECODE-EXC
  - CAA-NORM-EXC / CAA-NORM-INVALID
  - CAA-ADD-FRAME (aligner.add_frame 직전)
- [x] STEP 10 — 재실행 → 어느 단계에서 멈추는지 확인
  - **발견**: `decode_next` 첫 줄 가드 `if self._cap is None or ...` 가 RTSP 모드에서 즉시 None 반환
  - RTSP 는 `_cap` 안 쓰고 ffmpeg subprocess pipe 사용 → `_cap=None` 정상
  - 기존 가드 위치 때문에 `_fetch_latest_rtsp_frame` 진입 못 함

- [x] STEP 11 (진짜 fix) — `_cap is None` 가드를 RTSP 분기 이후로 이동
  - `video_decoder.py:1386` 수정. RTSP: 가드 통과 → `_fetch_latest_rtsp_frame` 호출. 파일: 기존 동작 유지.

## 변경 파일
- `infrastructure/preprocessing/video_decoder.py` (line 1023~1029 영역)

## 롤백 방법
stderr=subprocess.DEVNULL 로 한 줄 되돌리면 끝. 파일 핸들 leak 없도록 cleanup 도 포함.
