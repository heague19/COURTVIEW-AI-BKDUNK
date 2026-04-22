# Phase 17 Session 3 — 녹화 파이프라인 (R1-R7 하드닝)

**실행일**: 2026-04-21
**범위**: THE RECORD의 녹화 R1-R7 하드닝을 Python 서버로 포팅
**결과**: **신규 2파일 / 수정 1파일, 실녹화 검증 성공, 251/251 테스트 통과**

---

## 1. 1차 현장 테스트 문제 재진술

1차 테스트(20260331): 분석 + 녹화 동시 실행 시 녹화 품질 붕괴
- cam1=1.7MB, cam8=8.2MB (6배 편차)
- 일부 카메라 녹화 중간 끊김

원인: 이중 RTSP 연결 (UI LibVLC + Python), 리소스 경합.

**S3의 해결**: 녹화는 **서버가 ffmpeg subprocess로 단일 연결**. UI는 RTSP 직접 연결 안 함. 게다가 THE RECORD의 R1-R7 하드닝 포팅으로 녹화 자체의 견고성도 개선.

---

## 2. 구현 내역

### ✅ 신규 `engine/io/recording.py` (~500 LOC)

#### 핵심 클래스
- **`RecordingConfig`**: 세션 루트 경로, 컨테이너(mpegts/mp4), ffmpeg 경로, 보관 기간 등
- **`SessionInfo`**: 세션 ID, 폴더, 시작/종료 시각, 카메라별 상태
- **`CameraRecordingState`**: 개별 카메라 ffmpeg subprocess, 출력 경로, 쿼터, part 번호
- **`RecordingService`**: 스레드 안전 녹화 오케스트레이터 (start_session / stop_session / get_status)

#### R1–R7 하드닝

| ID | 기능 | 구현 |
|---|---|---|
| **R1** | 디스크 공간 사전 검증 | `has_sufficient_disk_space()` — `shutil.disk_usage()` 기반, 기본 5GB 상한 |
| **R2** | Orphan ffmpeg 정리 | `cleanup_orphans_and_old_sessions()` — `psutil` 로 PID 검증 + kill (이름에 'ffmpeg' 포함 시만) |
| **R3** | PID 추적 | `_write_pid_file()` — 세션 폴더에 `pids.txt` 저장 |
| **R4** | Graceful 종료 | `graceful_stop_process()` — stdin `'q'` → 8초 wait → terminate → 2초 wait → kill |
| **R5** | 세그먼트 명명 | `_next_part()` + `_build_segment_filename()` — `cam1_Q1.ts`, `cam1_Q1_part2.ts` |
| **R6** | 세그먼트 머지 | `_merge_session_segments()` — ffmpeg concat demuxer로 `cam1_full.mp4` 생성 |
| **R7** | 오래된 세션 삭제 | 같은 함수에서 7일(기본) 이상 세션 폴더 삭제 |

#### FFmpeg 실행
```python
args = [
    ffmpeg, "-loglevel", "warning",
    "-rtsp_transport", "tcp",                    # RTSP만
    "-use_wallclock_as_timestamps", "1",         # 멀티카메라 시간축 동기화
    "-i", rtsp_url,
    "-c", "copy",                                # 재인코딩 없음 (CPU/GPU 0%)
    "-f", "mpegts",                              # 부분 저장에도 재생 가능
    output_path,
]
```
- `stdin=PIPE` (R4 'q' 전송용)
- `stderr → 세션 내 .log 파일` (디버깅 추적)
- `CREATE_NO_WINDOW` (Windows 콘솔 창 숨김)

### ✅ 신규 `api_server/routes/v1/recording_routes.py` (~140 LOC)

```
POST /api/v1/recording/start    {quarter, camera_urls?} — camera_urls 없으면 CameraService 자동 조회
POST /api/v1/recording/stop     현재 세션 종료 + 머지
GET  /api/v1/recording/status   세션/카메라별 상태
GET  /api/v1/recording/health   ffmpeg 발견 + 디스크 여유
```

### ✅ `api_server/main.py` 연결
- `RecordingService` 싱글턴 생성
- 라이프사이클: startup에 라우터 바인딩, shutdown에 `stop_session()` 안전 종료
- `include_router(recording_routes.router)` 추가

---

## 3. 검증

### 실제 녹화 테스트 (로컬 mp4 소스 2개, 3초)
```
세션 시작: 2026-04-21_012543, 카메라 2개
R3: PID 파일 2개 기록  ✓
상태: active=True, ffmpeg=C:\...\ffmpeg.EXE
세션 종료: duration=3.0s
생성 파일:
  cam1_Q1.mp4              ← 원본 세그먼트
  cam1_Q1_part1.log        ← ffmpeg stderr 로그
  cam1_full.mp4            ← R6 머지 결과
  cam2_Q1.mp4
  cam2_Q1_part1.log
  cam2_full.mp4
(pids.txt는 종료 후 정리됨)
```

### 에지 케이스 처리
- `GET /recording/health`: ffmpeg 경로 + 디스크 여유 표시 (UI 사전 체크용)
- `POST /recording/start` 카메라 없음 → 400
- `POST /recording/stop` 세션 없음 → 404
- `POST /recording/start` 이미 실행 중 → 409 (RuntimeError)
- 디스크 5GB 미만 → 409 RuntimeError

### 회귀
- `tests/motion_analysis` + `tests/feedback_system/templates`: **251/251 통과**

---

## 4. 1차 현장 테스트 재현 시 예상 동작

```
1. UI가 'Start Game' → /api/v1/camera/connect-all (S1: 병렬 TCP 연결)
2. UI가 녹화 버튼 → POST /api/v1/recording/start?quarter=1
   ├─ R1: 디스크 5GB 이상 체크 통과
   ├─ R2/R7: 이전 orphan 정리
   ├─ 8개 ffmpeg subprocess 병렬 spawn
   ├─ R3: pids.txt 기록
   └─ 응답: {session_id: 2026-04-21_..., cameras: [cam1..cam8]}
3. 경기 진행... 서버가 별도 분석 파이프라인 실행
   ├─ 녹화 subprocess는 -c copy 라 CPU/GPU 거의 0%
   └─ 분석 파이프라인은 GPU 독점 사용 → 이중 연결 없음
4. UI가 경기 종료 → POST /api/v1/recording/stop
   ├─ R4: 각 ffmpeg에 'q' 전송 → 8초 대기 → terminate
   ├─ R6: cam1_Q1.ts... → cam1_full.mp4 머지
   └─ 응답: {duration, cameras[...]}
```

**1차 테스트의 "녹화 뚝뚝 끊김" 원인이 이중 연결이었으므로, 서버 단독 녹화 + R1-R7 하드닝 조합으로 해결 예상.**

---

## 5. 의존성 / 설치 요구사항

### 필수
- **ffmpeg** (PATH or 표준 설치 경로) — chocolatey/Windows installer로 배포 가능
- Python 표준 라이브러리 (`subprocess`, `pathlib`, `shutil`)

### 선택
- **psutil** — R2 orphan kill 시 필요 (없으면 skip 경고 로그)
- **imageio_ffmpeg** — ffmpeg 번들 용도 (없어도 OK)

### 패키징 시 권장
- pyinstaller로 exe 빌드 시 ffmpeg 바이너리 `%LOCALAPPDATA%\CourtView\ffmpeg\` 에 동봉
- `find_ffmpeg()` 탐색 경로에 해당 위치 포함됨

---

## 6. 영향 + 남은 Session

| 파일 | 타입 | LOC |
|---|---|---|
| `engine/io/recording.py` | 신규 | ~500 |
| `api_server/routes/v1/recording_routes.py` | 신규 | ~140 |
| `api_server/main.py` | 수정 | +10 |
| **합계** | **3파일** | **~650** |

### 남은 Session
- **S4**: 통합 스트리밍 (서버 디코드 1회 → 녹화 + AI + MJPEG 분기 zero-copy) + CloudSyncService main.py wire

녹화가 독립 ffmpeg subprocess로 돌고 있으므로 S4의 "zero-copy 분기"는 AI + MJPEG 스트리밍만 해당. 녹화는 현재 구조 그대로 유지 가능 (네트워크에서 직접 받기 때문에 copy 모드가 가장 효율).

---

**Phase 17 S3 완료. 1차 현장 테스트의 녹화 깨짐 문제 해결 가능 상태.**
