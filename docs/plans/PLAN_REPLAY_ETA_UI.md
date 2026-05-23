# Plan — Replay 분석 ETA UI

작성일: 2026-05-19
대상: REPLAY 모드 분석 시작 후 예상 소요 시간 표시

## 1. 배경

현재 [replay.html:712, 798](courtview_ui/templates/pages/replay.html#L798) 의 "REPLAY 분석 시작" 버튼 클릭 시 단순 "분석 시작 — 결과 뷰어로 이동" 메시지만 출력. 사용자가 **언제 끝나는지** 알 방법 없음. 실측 영상 5초 분석에 87초 소요 → 1시간 영상은 17시간 분석. ETA 필수.

## 2. 기존 인프라 (대부분 준비됨)

| 항목 | 위치 | 상태 |
|---|---|---|
| `ProgressResponse` 스키마 | [response_schemas.py:72-80](api_server/schemas/response_schemas.py#L72) | ✅ frame_current/total/pct/fps/eta_sec 모든 필드 존재 |
| `task_service.get_progress()` | [task_service.py:53](api_server/services/task_service.py#L53) | ✅ snapshot 기반 |
| `frame_pipeline.get_avg_processing_time()` | [frame_pipeline.py:836](engine/pipeline/frame_pipeline.py#L836) | ✅ 최근 100 frame 평균 |
| 영상 duration_sec | [recording_routes.py:146](api_server/routes/v1/recording_routes.py#L146) | ✅ 세션 메타 반환 |
| UI progress 위젯 | [replay.html:537 `rp-upload-progress`](courtview_ui/templates/pages/replay.html#L537) | ✅ 업로드용으로 존재, 재사용 |

→ **거의 모든 piece 가 이미 있음**. UI 연결 + ETA 계산 로직만 추가.

## 3. 작업 흐름

```
[REPLAY 분석 시작]
  ↓ /api/v1/game/start (기존)
[엔진 동작 시작]
  ↓
[UI 5초마다 polling]
  GET /api/v1/task/progress
  → ProgressResponse {frame_current, frame_total, progress_pct, fps, eta_sec}
  ↓
[UI 위젯 갱신]
  - 진행률 bar (progress_pct)
  - 처리 속도 (fps)
  - 남은 시간 (eta_sec)
  - 경과 시간 (계산)
```

## 4. STEP 구현

### STEP 1 — task_service.get_progress() 의 데이터 소스 확인 (코드 확인) ✅
- [x] `task_service.py` 의 snapshot 추적 — `orchestrator._progress_reporter.snapshot()` 직접 호출
- [x] `ProgressReporter` 가 frame_current/total/fps/eta_sec 모두 정확하게 계산
- [x] **결정적 발견**: `progress_reporter.start(total_frames=N)` 호출이 **어디에도 없었음** → frame_total=0 → ETA 항상 0

### STEP 2 — 백엔드: `progress_reporter.start()` 호출 추가 ✅
- [x] `engine/orchestrator/game_orchestrator.py:1003` 근처에 추가
- [x] BATCH/REPLAY 모드일 때 frame_ingestion 의 모든 decoder 의 `total_frames` 중 최솟값 사용 (정렬 한계)
- [x] LIVE 모드는 total=0 으로 호출 (fps 만 계산되며 진행률 0% 표시)

### STEP 3 — `/api/v1/tasks/progress` endpoint 확인 ✅
- [x] `api_server/routes/v1/task_routes.py:46` 에 이미 존재
- [x] `prefix=/api/v1/tasks` (tasks 복수형)

### STEP 4 — UI: ETA polling 추가 (replay_view.html) ✅
- [x] `progressPollHandle` setInterval 5초 polling
- [x] `pollProgress()` 함수 — `/api/v1/tasks/progress` fetch
- [x] `formatEta()` 함수 — 초 → "X시간 Y분 Z초" 변환
- [x] progBox/progBar/progFps 에 정확한 값 표시
- [x] `onAnalysisDone()` 에서 polling 자동 중단

### STEP 5 — 검증
- [ ] 짧은 영상 (10초) 으로 정확도 확인
- [ ] 긴 영상 (1쿼터) 으로 ETA 변동 확인
- [ ] 분석 완료 시 polling 자동 중단 동작

## 5. UI 예상 모습

```
┌──────────────────────────────────────────────────────┐
│ 🔄 REPLAY 분석 진행 중                                │
│                                                      │
│ ████████░░░░░░░░░░░░░░░░░░░░░░  28%   (1,432/5,128) │
│                                                      │
│ 처리 속도:  1.15 fps                                 │
│ 경과 시간:  18분 32초                                │
│ 예상 남은:  약 53분 18초                            │
└──────────────────────────────────────────────────────┘
```

## 6. 한계

- 분석 시작 직후 1분간은 ETA 부정확 (warm-up frame 변동)
- 처리 속도가 frame 마다 변동 시 ETA 흔들림 → **이동평균 5초** 사용

## 7. 변경 파일

| STEP | 파일 | 변경량 |
|---|---|---|
| 2 | `api_server/services/task_service.py` | ~30 lines |
| 2 | `api_server/services/recording_service.py` 또는 sessions API | ~20 lines (total_frames) |
| 4 | `courtview_ui/templates/pages/replay.html` | ~80 lines (HTML+CSS+JS) |

## 8. 진행 체크리스트

- [x] 사용자 승인
- [x] 계획서 작성
- [x] STEP 1 코드 확인 (인프라 완벽, start() 호출만 누락)
- [x] STEP 2 백엔드 보강 (`progress_reporter.start(total_frames)` 호출 추가)
- [x] STEP 3 endpoint 확인 (`/api/v1/tasks/progress` 이미 존재)
- [x] STEP 4 UI 위젯 (replay_view.html ETA polling 추가)
- [ ] STEP 5 검증 (사용자 실행)
