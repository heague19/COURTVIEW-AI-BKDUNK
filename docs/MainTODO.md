# 📋 COURTVIEW Main TODO

> **다른 컴퓨터에서 이어서 작업할 때 이 파일부터 열 것.**
> 2026-05-22 세션의 발견과 다음 작업을 모두 정리.
> 작성일: 2026-05-22 / 기준 커밋: `daf30d6`

---

## 🎯 한 줄 현황

> **REPLAY 분석 1.15 fps (1쿼터 5시간 13분) → 30 fps 가능. 진짜 병목은 F-matrix 매번 계산 + cv2 호출 누적.**
> 코드 수정은 다른 컴퓨터에서 시작. 이번 세션은 분석·문서화만 완료.

---

## 📚 이번 세션 (2026-05-22) 에서 한 일

### 1. 작성한 문서 10개

분류 정리 완료 (`docs/INDEX.md` 참조):

```
docs/
├── INDEX.md
├── concepts/                          🧠 일반 개념 (3)
│   ├── EPIPOLAR_GEOMETRY_EXPLAINED.md
│   ├── BIG_O_DECISIONS.md
│   └── POSE_FUSION_EXPLAINED.md
└── project/
    ├── architecture/                  📐 시스템 구조 (2)
    │   ├── DATA_FLOW_CONTRACT.md
    │   └── COMPUTATION_CODES_REFERENCE.md
    └── performance/                   ⚡ 성능 / 병목 (5)
        ├── PIPELINE_LATENCY_BUDGET.md
        ├── PIPELINE_LATENCY_BUDGET_REPLAY.md
        ├── FUSION_BOTTLENECK_ANALYSIS.md
        ├── TRIANGULATE_COST_BREAKDOWN.md
        └── PIPELINE_SPEEDUP_GUIDE.md
```

### 2. 한 줄씩 요약

| 문서 | 핵심 발견 |
|---|---|
| [INDEX.md](INDEX.md) | 폴더 분류 + 학습 트랙 |
| [concepts/EPIPOLAR_GEOMETRY](concepts/EPIPOLAR_GEOMETRY_EXPLAINED.md) | F-matrix 는 두 카메라의 기하학적 관계 카드 |
| [concepts/BIG_O_DECISIONS](concepts/BIG_O_DECISIONS.md) | O(log n) 이 항상 좋은 게 아님 — 작은 n 에서는 상수가 중요 |
| [concepts/POSE_FUSION](concepts/POSE_FUSION_EXPLAINED.md) | PoseFusion = "광선의 교점 찾기" |
| [architecture/DATA_FLOW_CONTRACT](project/architecture/DATA_FLOW_CONTRACT.md) | 데이터가 11 레이어를 거치며 BGR uint8 → 3D float → JSON |
| [architecture/COMPUTATION_CODES_REFERENCE](project/architecture/COMPUTATION_CODES_REFERENCE.md) | 40+ 함수, 단위 일관성 매우 중요 |
| [performance/LATENCY_BUDGET (LIVE)](project/performance/PIPELINE_LATENCY_BUDGET.md) | LIVE 33ms 예산 명시 |
| [performance/LATENCY_BUDGET_REPLAY](project/performance/PIPELINE_LATENCY_BUDGET_REPLAY.md) | REPLAY 도 동기화 코드 실행 (단, no-op) |
| [performance/FUSION_BOTTLENECK](project/performance/FUSION_BOTTLENECK_ANALYSIS.md) | 3 fusion 차이 173배 — 작업 종류의 차이 |
| [performance/TRIANGULATE_COST](project/performance/TRIANGULATE_COST_BREAKDOWN.md) | 에피폴라 필터가 호출당 50% — F-matrix 캐싱 최우선 |
| [performance/SPEEDUP_GUIDE](project/performance/PIPELINE_SPEEDUP_GUIDE.md) | 1.15 fps → 30 fps 가능 — 7단계 로드맵 |

### 3. 세션 중 발견된 정정 (이전 추정 → 코드 사실)

| 정정 | 이전 추정 | 코드 기반 사실 |
|---|---|---|
| REPLAY 동기화 | "5초 tolerance 로 느슨함" | **사실상 no-op** ([game_service.py:316](../api_server/services/game_service.py#L316) 주석에 명시) |
| 에피폴라 비교 | "n choose 2 쌍별" | **n-1 회** (기준 cameras[0] vs 나머지) |
| SVD 비용 | "380ms 매우 무거움" | **~6ms** (행렬이 (2n × 4) 로 작음) |
| 메모리 할당 | "50ms" | **~10ms** (5배 과대 추정이었음) |
| 함수 호출 오버헤드 | "큼" | **~10ms (2%)** — 실제로 작음 |
| 진짜 병목 | "SVD 자체" | **cv2 호출 누적 + F-matrix 매번 계산** |

---

## ⚡ 다음 작업 — 우선순위 TODO

### 🔴 우선순위 0 (먼저 실측부터)

#### TODO-1: Baseline 측정
**왜 먼저**: 모든 최적화는 baseline 없이 무의미. STEP 0 부터.

```powershell
# 실행할 명령
.\venv\Scripts\python.exe tools\bench_pipeline_realistic.py `
  --session "D:\COURTVIEW_Recordings\<session_id>" `
  --warmup 10 `
  --frames 100 `
  --start-frame 300
```

**측정할 항목**:
- [ ] `stage_times_ms` 분포 (detection_fusion, pose_fusion, tracking_fusion, ...)
- [ ] GPU 사용률 (`nvidia-smi dmon -s u -c 60`)
- [ ] ViTPose Stage2 호출 빈도 (별도 카운터 임시 삽입 — `game_orchestrator.py:2366`)

**기대 결과**:
- pose_fusion 이 압도적이면 → [SPEEDUP_GUIDE](project/performance/PIPELINE_SPEEDUP_GUIDE.md) P0-2 우선
- GPU util <30% 면 → CPU bound, ThreadPool 우선
- ViTPose 가 매 프레임 돌면 → Stage2 트리거 점검

📄 자세히: [PIPELINE_SPEEDUP_GUIDE §STEP 0](project/performance/PIPELINE_SPEEDUP_GUIDE.md)

---

#### TODO-2: weights/ 폴더 미사용 파일 확인
**왜**: 이번 세션 마지막에 발견 — `launcher_warmup.py:48` 가 weights/*.onnx 를 **전부 스캔해서 TRT 빌드**. 미사용 weights 도 로드됨.

```powershell
# 1. 실제 weights/ 폴더 내용 확인
ls weights\*.onnx, weights\*.pt, weights\*.engine | Format-Table Name, Length, LastWriteTime

# 2. TensorRT 캐시 (워밍업이 빌드한 목록)
ls "$env:APPDATA\COURTVIEW\tensorrt_cache\*.engine" | Select Name, Length

# 3. 의심 파일 존재 확인
Test-Path weights\vitpose-l-wholebody.onnx     # ⚠️ 1.18GB 미사용 의심
Test-Path weights\yolo11m-pose.onnx            # ⚠️ 참조 없음
Test-Path weights\yolo11m-pose.pt              # ⚠️ 참조 없음
```

**미사용 의심 3개** (코드 grep 결과):
- `vitpose-l-wholebody.onnx` — engine/config.py 는 `vitpose-b` 만 참조
- `yolo11m-pose.onnx` — 코드 어디서도 import 안 함
- `yolo11m-pose.pt` — 동상

**약간 의심 4개** (tools/ 학습 전용):
- `CV-Team_v3.pt`, `CV-BBox_v7.engine`, `CV_team.pt`, `cv-action_v1.pt`

**조치**:
- 미사용 확인되면 → 별도 폴더로 이동 (`weights_archive/`) 또는 삭제
- 또는 [launcher_warmup.py:48 `_discover_onnx_models`](../launcher_warmup.py#L48) 에 화이트리스트 추가

---

### 🔴 우선순위 1 (성능 최적화 — 효과 큰 순)

> ⚠️ **2026-05-22 추가 발견**: 중첩 포문(~520ms) 보다 무거운 영역이 4개 더 있음.
> 그래서 **TODO-3 (F-matrix 캐싱) 보다 TODO-3a (decode 병렬화) 와 TODO-7 (TRT batch=8) 이 더 큰 효과**.
> 우선순위 재조정: **3a → 3 → 3b → 4 → 5** 순서 권장.

---

#### TODO-3a: ⭐⭐ Decode 병렬화 (NEW — 가장 큰 효과)

**왜 최우선**: 매 프레임 시작에서 8 카메라 H.264 디코드를 **순차** 실행 → 240~640ms 소요.
중첩 포문(520ms) 보다 무겁고, ThreadPool 만으로 8배 가속 가능.

##### 1) Decode 가 뭐고 어디 쓰나
- **Decode**: 카메라가 보낸 H.264 압축 비트스트림 → numpy uint8 BGR 픽셀 배열로 변환
- **시점**: 모든 AI 파이프라인의 **첫 단계** (매 frame 사이클의 시작점)
- **흐름**:
  ```
  📡 RTSP/파일 (H.264) → 🔓 decode_next() → 📐 정규화 → ⏰ 동기화 → 🤖 AI
  ```
- **왜 필수**: 카메라는 대역폭 절약 위해 압축 송신 (1.5 Gbps → 10 Mbps). AI 모델은 픽셀 numpy 입력 필요. 둘 사이의 다리.

##### 2) 현재 문제 — 코드 위치

[frame_ingestion.py:303-420](../engine/io/frame_ingestion.py#L303) `capture_and_align` (LIVE):

```python
with self._lock:                                  # ⚠️ 락 안에 전체 루프
    for cam_id, decoder in self._decoders.items():
        frame_data = decoder.decode_next()        # ← 순차 실행!
        normalized = self._normalizer.normalize(frame_data)
        self._aligner.add_frame(cam_id, normalized)
    aligned = self._aligner.try_align()
```

[frame_ingestion.py:504-539](../engine/io/frame_ingestion.py#L504) `decode_all` (BATCH/REPLAY) — 동일 패턴.

##### 3) 비용 분석

| 항목 | 시간 |
|---|---|
| H.264 디코드 1 카메라 | 30~80ms (CPU, HW 가속 없을 때) |
| 8 카메라 순차 | **240~640ms** |
| ThreadPool 8 병렬 | **max(30~80ms) = 30~80ms** |
| **잠재 가속** | **8배** |

##### 4) 왜 ThreadPool 이 효과 있나
- ffmpeg / cv2 는 C++ 외부 호출 → **GIL 해제됨**
- Python ThreadPool 로도 진짜 병렬 실행
- 각 decoder 는 독립된 ffmpeg subprocess → 충돌 없음
- 이미 [frame_ingestion.py:231-235](../engine/io/frame_ingestion.py#L231) 의 "카메라 열기" 에 동일 패턴 적용됨 (참조용)

##### 5) 수정안 (의사코드)

```python
from concurrent.futures import ThreadPoolExecutor

def capture_and_align(self) -> AlignedFrameSet | None:
    if not self._initialized or self._normalizer is None or self._aligner is None:
        return None

    cam_ids_list = list(self._decoders.keys())

    # 디코드 + 정규화는 락 밖에서 병렬
    def _decode_and_normalize(cam_id):
        decoder = self._decoders[cam_id]
        try:
            frame_data = decoder.decode_next()
            if frame_data is None or not frame_data.is_valid:
                return cam_id, None, "invalid"
            normalized = self._normalizer.normalize(frame_data)
            if not normalized.is_valid:
                return cam_id, None, "norm_invalid"
            return cam_id, normalized, "ok"
        except Exception as e:
            logger.exception("디코드/정규화 에러: %s", cam_id)
            return cam_id, None, f"exc:{e}"

    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="fi-decode") as pool:
        results = list(pool.map(_decode_and_normalize, cam_ids_list))

    # 통계 갱신 + 정렬기 투입은 락 안에서 짧게
    with self._lock:
        for cam_id, normalized, status in results:
            if status == "ok":
                self._stats.total_captured += 1
                self._stats.total_normalized += 1
                self._aligner.add_frame(cam_id, normalized)
            elif status.startswith("exc:"):
                self._stats.total_decode_errors += 1
            else:
                self._stats.total_dropped += 1

        aligned = self._aligner.try_align()
        if aligned is not None:
            self._stats.total_aligned_sets += 1
            self._frame_counter += 1
        return aligned
```

##### 6) ⚠️ 주의사항 / 함정

| 항목 | 점검 내용 |
|---|---|
| 락 범위 축소 | `self._lock` 을 디코드 밖으로 빼면 다른 메서드와 경쟁 가능 → `__init__`, `shutdown` 등도 확인 |
| `_stats` 카운터 | 락 안에서 갱신하면 OK. 락 밖에서 갱신 시 atomic 보장 필요 |
| `flow_logger` 호출 | 각 카메라마다 log_flow 호출 — 병렬화해도 동작 OK (logger 는 thread-safe) |
| `decode_next()` 내부 상태 | decoder 객체별 상태 (예: `_latest_frame`) 가 thread-safe 한지 → [video_decoder.py:1374](../infrastructure/preprocessing/video_decoder.py#L1374) 확인 필요 |
| ThreadPool 생성 비용 | 매 호출마다 생성하면 오버헤드 (~1ms) — 멤버 변수로 재사용 권장 (`self._decode_pool`) |
| BATCH 모드도 동일 적용 | `decode_all()` 도 같은 패턴으로 수정 |

##### 7) 수정 대상 파일

| 파일 | 함수 | 라인 |
|---|---|---|
| [frame_ingestion.py](../engine/io/frame_ingestion.py) | `__init__` | ThreadPool 멤버 추가 |
| 〃 | `capture_and_align` | 303-483 (LIVE) |
| 〃 | `decode_all` | 488-557 (BATCH/REPLAY) |
| 〃 | `shutdown` 또는 `close` | ThreadPool shutdown 추가 |

##### 8) 테스트 시나리오

- [ ] **단위 테스트**: 직렬 결과 vs 병렬 결과 동일성 확인 (8 카메라 mock decoder)
- [ ] **순서 보장**: `_decoders.items()` 순서가 ThreadPool 후에도 유지되는지 (정렬은 별개 단계라 OK)
- [ ] **에러 격리**: 1 카메라 디코드 실패 시 나머지 7 카메라가 정상 진행되는지
- [ ] **통계 정확성**: total_captured, total_dropped, total_decode_errors 가 직렬 모드와 동일하게 카운트되는지
- [ ] **데드락 검증**: `self._lock` 과 ThreadPool 의 동시 사용에서 데드락 없는지

##### 9) 검증 방법

```powershell
# Before/After 측정
.\venv\Scripts\python.exe tools\bench_pipeline_realistic.py `
  --session "D:\COURTVIEW_Recordings\<session>" `
  --warmup 10 --frames 100

# stage_times_ms 안에 별도 측정 키 추가
# 또는 frame_ingestion.py 내부에 t0 = perf_counter; ... ; t1 = perf_counter 로 직접
```

**기대 결과**:
- decode 단계 평균: ~400ms → ~50ms
- 전체 fps: 1.15 → ~2 (decode 만 개선해도)

##### 10) 후속 시너지 (별도 작업)

decode 병렬화 후 추가로 적용 가능:
- **Plan B** ([_plan_B_hwaccel_2026-05-13.md](../../_plan_B_hwaccel_2026-05-13.md)): ffmpeg `-hwaccel d3d11va` 또는 `cuda` → CPU 부하 80% 감소
- **Plan D** ([_plan_D_ffmpeg_prescale_2026-05-13.md](../../_plan_D_ffmpeg_prescale_2026-05-13.md)): ffmpeg `-s 1920x1080` 사전 리사이즈 → cv2.resize 제거
- 둘 다 합치면: decode 240~640ms → **~10ms 가능** (32~64배)

##### 11) 예상 효과 최종

| 단계 | decode 시간 / 프레임 | 누적 fps (추정) |
|---|---|---|
| 현재 (직렬, SW 디코드) | 240~640ms | 1.15 |
| + ThreadPool 병렬 | 30~80ms | ~2 |
| + HW 가속 (Plan B) | 5~15ms | ~3 |
| + ffmpeg pre-resize (Plan D) | ~10ms | ~3.5 |

##### 12) 작업 순서

1. [ ] **STEP 1**: 단위 테스트 작성 (mock decoder × 8)
2. [ ] **STEP 2**: `frame_ingestion.py:__init__` 에 `self._decode_pool = ThreadPoolExecutor(...)` 추가
3. [ ] **STEP 3**: `capture_and_align` 수정 (LIVE)
4. [ ] **STEP 4**: 측정 — 8 카메라 영상으로 bench 비교
5. [ ] **STEP 5**: `decode_all` 수정 (BATCH/REPLAY)
6. [ ] **STEP 6**: `shutdown`/`close` 에 pool 정리 추가
7. [ ] **STEP 7**: stage_times 에 `decode_ms` 키 추가 (측정 가시화)
8. [ ] **STEP 8**: PR 작성 + 통합 테스트

📄 더 자세한 개념 설명: 이 문서 §개념 자체는 사용자 응답으로 받음 (decode 가 무엇이고 왜 필요한가)

---

#### TODO-3: F-matrix 캐싱 ⭐ 가장 효과 큼

**위치**: [coordinate_transformer.py:582-627](../infrastructure/multi_camera/coordinate_transformer.py#L582) `_fundamental_from_projections`

**현재 문제**:
- 매 키포인트마다 F-matrix 새로 계산 (~120ms 누적)
- 그런데 카메라는 **고정** → F 는 frame 마다 안 바뀜
- **23만 frame × 같은 계산 반복 = 낭비**

**수정안** (의사코드):
```python
class MultiViewTriangulator:
    def __init__(self, ...):
        self._F_cache: dict[tuple[str, str], np.ndarray] = {}

    def _get_F(self, cam_id_1, cam_id_2, P1, P2):
        key = (cam_id_1, cam_id_2)
        if key not in self._F_cache:
            self._F_cache[key] = self._fundamental_from_projections(P1, P2)
        return self._F_cache[key]

    # _filter_epipolar_outliers 안에서
    F = self._get_F(ref_cam_id, other_cam_id, ref_P, other_P)  # ← 캐시 사용
```

**주의사항**:
- 카메라 calibration 갱신 시 캐시 무효화 (cache_invalidate API)
- 8 카메라 = 28 쌍만 한 번 계산
- 단위 테스트로 결과 동일성 확인

**예상 효과**: **120ms → 5ms (24배 가속)**

📄 자세히: [TRIANGULATE_COST_BREAKDOWN §10.2](project/performance/TRIANGULATE_COST_BREAKDOWN.md)

---

#### TODO-4: cv2 배치 호출

**위치**:
- [coordinate_transformer.py:251 `undistort_pixel`](../infrastructure/multi_camera/coordinate_transformer.py#L251)
- [coordinate_transformer.py:312 `compute_reprojection_error`](../infrastructure/multi_camera/coordinate_transformer.py#L312)

**현재 문제**:
- 점 1개씩 340회 호출 → 호출 오버헤드만 ~40ms
- cv2 는 배치로 부르면 압도적으로 빠름

**수정안**: 한 카메라의 모든 점을 (N, 2) 배열로 한 번에 처리.

**예상 효과**: **100ms → 15ms (7배 가속)**

---

#### TODO-5: PoseFusion 선수 단위 ThreadPool

**위치**: [pose_fusion.py:219-222](../engine/pipeline/fusion/pose_fusion.py#L219)

**현재 코드**:
```python
for person_id, group in person_groups.items():     # 직렬
    fused = self._fuse_person(person_id, group)
```

**수정안**:
```python
from concurrent.futures import ThreadPoolExecutor

self._pose_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pose-fuse")

# fuse() 내부
futures = {
    person_id: self._pose_pool.submit(self._fuse_person, person_id, group)
    for person_id, group in person_groups.items()
}
poses_3d = [f.result() for f in futures.values() if f.result() is not None]
```

**주의사항**:
- `_triangulator` thread safety 확인 ([:423](../infrastructure/multi_camera/coordinate_transformer.py#L423) 에 RLock 있음 — OK)
- 선수 2명 이하면 직렬 (스레드 오버헤드 회피)
- 단위 테스트로 결과 일치 확인 (numpy `allclose`)

**예상 효과**: **3배 가속** (선수 4~5명 가정)

📄 자세히: [PIPELINE_SPEEDUP_GUIDE P0-2](project/performance/PIPELINE_SPEEDUP_GUIDE.md)

---

### 🟠 우선순위 2 (중간 효과)

#### TODO-6: Stage2 (ViTPose) 트리거 호출 빈도 확인

**위치**: [game_orchestrator.py:2366-2432](../engine/orchestrator/game_orchestrator.py#L2366) `_try_stage2_vitpose`

**작업**:
1. 임시 카운터 삽입 (1줄):
   ```python
   self._stage2_call_count = getattr(self, '_stage2_call_count', 0) + 1
   if self._stage2_call_count % 10 == 0:
       logger.info(f"[STAGE2] called {self._stage2_call_count} times")
   ```
2. 100 frame 분석 후 호출 빈도 확인
3. 빈도가 30%+ 면 → 트리거 조건 강화 ([game_orchestrator.py:2378](../engine/orchestrator/game_orchestrator.py#L2378))

**효과**: 호출 빈도에 따라 다름. 만약 매번 돌고 있었다면 **5~10배 가속**.

---

#### TODO-7: TensorRT batch=8 재빌드

**위치**: [tensorrt_engine.py:162-164](../pose_estimation/backends/tensorrt_engine.py#L162)

**수정**:
```python
min_batch_size: int = 1
optimal_batch_size: int = 8     # ← 1 → 8 변경
max_batch_size: int = 8
```

**중요**:
- `%APPDATA%\COURTVIEW\tensorrt_cache\*.engine` 캐시 삭제 → 첫 실행 재빌드
- VRAM 한계 주의 (RTX 4070 12GB 에서 다른 모델과 합쳐 OOM 위험)
- 빌드 실패 시 자동 폴백 ([launcher_warmup.py](../launcher_warmup.py) 가 처리)

**예상 효과**: **2배 가속** (현재 batch=1 → GPU 60~70% 유휴)

---

#### TODO-8: 프레임 스킵 (Motion Gate)

**위치**: [frame_pipeline.py](../engine/pipeline/frame_pipeline.py) 초입

**아이디어**:
- 대표 카메라 1대의 그레이 차분으로 motion 측정
- 정적 프레임은 detect 스킵, ByteTrack 보간만

**주의사항**:
- 슈팅 릴리스(~50ms = 1.5 프레임) 누락 위험
- 이벤트 감지 정확도 검증 필수
- 같은 영상으로 ON/OFF 비교 → `events.json` 차이 확인

**예상 효과**: **2배 가속** (정적 시간 비중에 따라)

---

#### TODO-9: yaml workspace 설정 충돌 해결

**파일**:
- [configs/pose/tensorrt.yaml:18](../configs/pose/tensorrt.yaml#L18) — `workspace_size_mb: 2048`
- [configs/base/gpu_config.yaml:51](../configs/base/gpu_config.yaml#L51) — `workspace_size_mb: 1024`

**조치**:
1. 실제 어느 쪽이 적용되는지 확인 ([yolov8_backend.py:516](../pose_estimation/backends/yolov8_backend.py#L516) 의 model.yaml 우선순위)
2. 사용 안 하는 쪽 삭제 또는 통일
3. VRAM 0.5GB 회수

---

### 🟡 우선순위 3 (큰 변경, 위험 동반)

#### TODO-10: INT8 Quantization (위험)

**조건**:
- 캘리브레이션 데이터셋 100~500 프레임 필요
- YOLO 감지 → YOLOv8-Pose Stage1 → ViTPose 순으로 단계적 적용
- **ViTPose 는 FP16 유지** (정밀 분석용)

**예상 효과**: 2~3배 가속 + 30% VRAM 절감
**위험**: 슈팅 폼 분석의 5cm 정밀도 손실 가능

📄 자세히: [PIPELINE_SPEEDUP_GUIDE P2-6](project/performance/PIPELINE_SPEEDUP_GUIDE.md)

---

## 📊 예상 누적 효과 (2026-05-22 재조정)

| 단계 | 누적 fps | 1쿼터 12분 분석 | 비고 |
|---|---|---|---|
| **현재 baseline** | 1.15 | **5시간 13분** | |
| + **TODO-3a (decode 병렬화)** ⭐⭐ | ~2 | 3시간 | **NEW — 8배 가속 (decode 영역)** |
| + TODO-7 (TRT batch=8) | ~4 | 1시간 30분 | 포즈 추정 4~7배 |
| + TODO-3 (F-matrix 캐싱) | ~5 | 1시간 12분 | 에피폴라 24배 |
| + TODO-4 (cv2 배치) | ~10 | 36분 | undistort/project 7배 |
| + TODO-5 (Pose ThreadPool) | ~15 | 24분 | 선수 단위 3배 |
| + TODO-8 (프레임 스킵) | ~25 | 14분 | 정적 시간 흡수 |
| + Plan B (HW 디코드) | ~30 | 12분 | **NVDEC 추가** |
| + TODO-10 (INT8, 선택) | ~40 | **9분** | 위험 동반 |

> ⚠️ 모두 추정. TODO-1 (실측) 결과에 따라 우선순위 재조정.
>
> **2026-05-22 변경점**: TODO-3a (decode 병렬화) 가 단일 효과로는 TODO-3 (F-matrix 캐싱) 보다 큼 — 매 프레임 240~640ms 디코드를 30~80ms 로 줄이는 것이 직접적이고 범용적.

---

## 🗺️ 다음 컴퓨터에서 시작하는 순서

### Day 0 — 환경 확인 (10분)

```powershell
# 1. 리포 클론 및 최신 상태
cd <work-dir>
git clone <repo>
cd COURTVIEW-AI-BKDUNK
git pull
git log --oneline -5

# 2. venv 활성화
.\venv\Scripts\activate

# 3. 이 파일부터 읽기
code docs\MainTODO.md
code docs\INDEX.md
```

### Day 1 — 실측 (1시간)

- [ ] **TODO-1** 실행 (bench_pipeline_realistic.py)
- [ ] **TODO-2** 실행 (weights/ 폴더 확인)
- [ ] 결과를 `docs/project/performance/BENCHMARK_BASELINE.md` 에 기록

### Day 2 — 안전한 변경 (1일)

- [ ] **TODO-2** 후속: 미사용 weights 격리
- [ ] **TODO-9**: yaml 설정 통일
- [ ] **TODO-6**: Stage2 카운터 임시 삽입 → 호출 빈도 확인

### Day 3 — Decode 병렬화 (1일) ⭐⭐

- [ ] **TODO-3a (decode 병렬화)** ⭐ **최우선 — 8배 가속**
  - [ ] STEP 1-2: 단위 테스트 + ThreadPool 멤버 추가
  - [ ] STEP 3-4: capture_and_align 수정 (LIVE) + bench 측정
  - [ ] STEP 5: decode_all 수정 (BATCH/REPLAY)
  - [ ] STEP 6-7: shutdown 정리 + stage_times 측정 키 추가
  - [ ] STEP 8: PR + 통합 테스트
  - [ ] **검증**: decode 단계 400ms → 50ms 확인

### Day 4-6 — 핵심 최적화 (3일)

- [ ] **TODO-7 (TRT batch=8)** — 포즈 추정 4~7배
  - [ ] tensorrt_cache 삭제 → 재빌드 (수 분)
  - [ ] VRAM 모니터링
- [ ] **TODO-3 (F-matrix 캐싱)** — 에피폴라 24배
  - [ ] 단위 테스트 작성 (캐시 vs 비캐시 결과 동일)
  - [ ] PR 작성
- [ ] **TODO-4 (cv2 배치 호출)** — undistort/project 7배

### Day 7 — Pose 병렬화 + 프레임 스킵 (1일)

- [ ] **TODO-5 (Pose ThreadPool)** — 선수 단위 3배
- [ ] **TODO-8 (프레임 스킵 motion gate)**

### Day 8 — 정리 + 측정

- [ ] 다시 **TODO-1** 실행해서 개선 측정
- [ ] PIPELINE_SPEEDUP_GUIDE 의 예상치와 비교

---

## 🗂️ 자주 참조할 코드 위치

### 좌표 변환 / 3D 복원
| 항목 | 위치 |
|---|---|
| `triangulate()` 본체 | [coordinate_transformer.py:406-481](../infrastructure/multi_camera/coordinate_transformer.py#L406) |
| `_dlt_triangulate` | [:506-535](../infrastructure/multi_camera/coordinate_transformer.py#L506) |
| `_filter_epipolar_outliers` ⭐ | [:537-580](../infrastructure/multi_camera/coordinate_transformer.py#L537) |
| `_fundamental_from_projections` ⭐ **TODO-3** | [:582-627](../infrastructure/multi_camera/coordinate_transformer.py#L582) |
| `_epipolar_distance` | [:629-660](../infrastructure/multi_camera/coordinate_transformer.py#L629) |
| `undistort_pixel` ⭐ **TODO-4** | [:251-276](../infrastructure/multi_camera/coordinate_transformer.py#L251) |
| `compute_reprojection_error` ⭐ **TODO-4** | [:312-329](../infrastructure/multi_camera/coordinate_transformer.py#L312) |

### Pose Fusion
| 항목 | 위치 |
|---|---|
| `PoseFusion.fuse()` | [pose_fusion.py:193-239](../engine/pipeline/fusion/pose_fusion.py#L193) |
| `_fuse_person` | [:244-321](../engine/pipeline/fusion/pose_fusion.py#L244) |
| 3중 루프 (성능 핫스팟) ⭐ **TODO-5** | [:259-313](../engine/pipeline/fusion/pose_fusion.py#L259) |
| 선수 외부 루프 ⭐ **TODO-5** | [:219-222](../engine/pipeline/fusion/pose_fusion.py#L219) |

### Engine / Orchestrator
| 항목 | 위치 |
|---|---|
| `_try_stage2_vitpose` ⭐ **TODO-6** | [game_orchestrator.py:2366-2432](../engine/orchestrator/game_orchestrator.py#L2366) |
| `stage2_triggers` 정의 | [engine/config.py:254-259](../engine/config.py#L254) |
| `CadenceConfig` (예산) | [engine/config.py:223-229](../engine/config.py#L223) |
| `cadence_scheduler.tick()` | [cadence_scheduler.py:107-150](../engine/orchestrator/cadence_scheduler.py#L107) |
| frame_pipeline (stage_times) | [frame_pipeline.py:314,353,396](../engine/pipeline/frame_pipeline.py#L314) |

### TensorRT / Warmup
| 항목 | 위치 |
|---|---|
| `optimal_batch_size = 1` ⭐ **TODO-7** | [tensorrt_engine.py:162-164](../pose_estimation/backends/tensorrt_engine.py#L162) |
| `_discover_onnx_models` ⭐ **TODO-2** | [launcher_warmup.py:48-72](../launcher_warmup.py#L48) |
| workspace yaml 충돌 ⭐ **TODO-9** | [configs/pose/tensorrt.yaml:18](../configs/pose/tensorrt.yaml#L18), [gpu_config.yaml:51](../configs/base/gpu_config.yaml#L51) |
| TRT optimization profile | [tensorrt_engine.py:783-792](../pose_estimation/backends/tensorrt_engine.py#L783) |

### Frame Ingestion / Sync
| 항목 | 위치 |
|---|---|
| sync_tolerance_ms=5000 (REPLAY) | [game_service.py:316](../api_server/services/game_service.py#L316) |
| `try_align()` | [frame_aligner.py:301-383](../engine/io/frame_aligner.py#L301) |
| `min_cameras_required=2` | [frame_aligner.py:313](../engine/io/frame_aligner.py#L313) |
| `capture_and_align` (LIVE) ⭐⭐ **TODO-3a** | [frame_ingestion.py:303-483](../engine/io/frame_ingestion.py#L303) |
| decode_next 순차 루프 (LIVE) ⭐⭐ **TODO-3a** | [frame_ingestion.py:315-420](../engine/io/frame_ingestion.py#L315) |
| `decode_all` (BATCH/REPLAY) ⭐⭐ **TODO-3a** | [frame_ingestion.py:488-557](../engine/io/frame_ingestion.py#L488) |
| decode_next 순차 루프 (BATCH) ⭐⭐ **TODO-3a** | [frame_ingestion.py:504-539](../engine/io/frame_ingestion.py#L504) |
| ThreadPool 적용 예시 (열기, 참조용) | [frame_ingestion.py:231-235](../engine/io/frame_ingestion.py#L231) |
| `decode_next()` 본체 | [video_decoder.py:1374](../infrastructure/preprocessing/video_decoder.py#L1374) |
| HW 가속 옵션 (Plan B) | [video_decoder.py:71-72](../infrastructure/preprocessing/video_decoder.py#L71) |
| ThreadPool 예시 (열기) | [frame_ingestion.py:231-235](../engine/io/frame_ingestion.py#L231) |

---

## ⚠️ 주의 사항 / 함정

### 1. weights/ 폴더 복사 필수
README 에 명시: "**내부 보안 대상** — NAS 에서 수동 복사".
`C:\COURTVIEW_DESK\weights\` 에 다음 파일들 있어야:
- `CV-BBox_v9.onnx`, `CV-BBox_v9.pt`
- `vitpose-b-wholebody.onnx`
- `yolo11l-pose.onnx`, `.pt`
- `yolov8s.onnx`
- `COURTVIEW_player.pt`, `.onnx`
- `COURTVIEW_ball.pt`, `.onnx`
- `COURTVIEW_hoop.pt`, `.onnx`
- `CV-team.pt`, `COURTVIEW_team.pt`
- `CV-Digit_v6.pt`, `.onnx`
- `COURTVIEW_reid.pt`
- `best.pt` (jersey OCR)

### 2. UI 레포 별도
빌드 시:
```
C:\COURTVIEW_DESK\     ← 이 레포
C:\COURTVIEW-UI\       ← courtview_ui 레포 (spec 이 ../COURTVIEW-UI 참조)
```

### 3. 단위 일관성 (계산 코드 수정 시 필수 확인)
| 도메인 | 단위 |
|---|---|
| 픽셀 | px (정수) |
| 키포인트 3D | **cm** |
| 속도 | cm/s, m/s (변환 시 `/100`) |
| 각도 | degree |
| 각속도 | rad/s (변환 시 `math.radians`) |
| 힘 | N |
| 코트 좌표 (GameEvent) | 0~1 정규화 |

📄 자세히: [COMPUTATION_CODES_REFERENCE §8.3](project/architecture/COMPUTATION_CODES_REFERENCE.md)

### 4. 기존 PLAN 문서 충돌
루트에 PLAN_*.md 가 17개 + `_plan_*.md` 8개 등 어수선. 이번 세션 작업은 `docs/` 안에만 있음. 충돌 없음.

### 5. CLAUDE.md 가 비어있음
협업 지침이 아직 없음. 필요 시 작성 권장.

---

## 🚨 실측 전에 단정하지 말 것

이번 세션에서 정정된 사례:

| 영역 | 실수했던 추정 | 실제 |
|---|---|---|
| SVD 비용 | 380ms | **~6ms** |
| 메모리 할당 | 50ms | **~10ms** |
| 에피폴라 쌍 | n choose 2 | **n-1** |

→ **항상 코드를 우선** 보고, **실측 → 추정** 순서를 지킬 것.

---

## 📖 참고 문서 빠른 링크

| 목적 | 문서 |
|---|---|
| 전체 인덱스 | [INDEX.md](INDEX.md) |
| 신규 합류자 → | [DATA_FLOW_CONTRACT](project/architecture/DATA_FLOW_CONTRACT.md) |
| 성능 작업 → | [PIPELINE_SPEEDUP_GUIDE](project/performance/PIPELINE_SPEEDUP_GUIDE.md) |
| 병목 진단 → | [FUSION_BOTTLENECK_ANALYSIS](project/performance/FUSION_BOTTLENECK_ANALYSIS.md) |
| 비용 분해 → | [TRIANGULATE_COST_BREAKDOWN](project/performance/TRIANGULATE_COST_BREAKDOWN.md) |
| 알고리즘 학습 → | [POSE_FUSION_EXPLAINED](concepts/POSE_FUSION_EXPLAINED.md), [EPIPOLAR_GEOMETRY](concepts/EPIPOLAR_GEOMETRY_EXPLAINED.md) |
| 코드 위치 검색 → | [COMPUTATION_CODES_REFERENCE](project/architecture/COMPUTATION_CODES_REFERENCE.md) §부록 |

### 기존 PLAN 문서 (루트)
| 목적 | 문서 |
|---|---|
| 메모리 감사 | [../PLAN_MEMORY_USAGE_AUDIT.md](../PLAN_MEMORY_USAGE_AUDIT.md) |
| RTSP 좀비 | [../PLAN_RTSP_ZOMBIE_SHUTDOWN_FIX.md](../PLAN_RTSP_ZOMBIE_SHUTDOWN_FIX.md) |
| Frame cadence 버그 | [../PLAN_FRAME_CADENCE_BUFFER_GAP.md](../PLAN_FRAME_CADENCE_BUFFER_GAP.md) |
| Replay ETA UI | [../PLAN_REPLAY_ETA_UI.md](../PLAN_REPLAY_ETA_UI.md) |
| Replay STOP fix | [../PLAN_REPLAY_STOP_FIX.md](../PLAN_REPLAY_STOP_FIX.md) |

---

## ✅ TODO 체크리스트 (작업하며 갱신)

### 실측 단계
- [ ] TODO-1: bench_pipeline_realistic.py 실행
- [ ] TODO-2: weights/ 폴더 확인 (PowerShell)
- [ ] 결과를 `BENCHMARK_BASELINE.md` 에 기록

### 안전한 변경
- [ ] TODO-9: yaml 충돌 통일
- [ ] TODO-2 후속: 미사용 weights 격리
- [ ] TODO-6: Stage2 카운터 → 호출 빈도 확인

### 성능 최적화 (효과 큰 순)
- [ ] **TODO-3a: Decode 병렬화** ⭐⭐ (8배 가속, 매 프레임 240~640ms 절약)
  - [ ] STEP 1: 단위 테스트 (mock decoder × 8)
  - [ ] STEP 2: ThreadPool 멤버 추가
  - [ ] STEP 3: capture_and_align 수정 (LIVE)
  - [ ] STEP 4: bench 측정 (decode 단계 ms)
  - [ ] STEP 5: decode_all 수정 (BATCH/REPLAY)
  - [ ] STEP 6: shutdown 정리
  - [ ] STEP 7: stage_times 키 추가
  - [ ] STEP 8: PR + 통합 테스트
- [ ] TODO-7: TRT batch=8 재빌드 (4~7배, 포즈 추정)
- [ ] TODO-3: F-matrix 캐싱 (24배, 에피폴라 영역)
- [ ] TODO-4: cv2 배치 호출 (7배, undistort/project)
- [ ] TODO-5: Pose ThreadPool (3배, 선수 단위)

### 큰 변경
- [ ] TODO-8: 프레임 스킵 motion gate (2배)
- [ ] Plan B: HW 디코드 가속 (NVDEC/D3D11VA) — TODO-3a 후속

### 위험 동반 (선택)
- [ ] TODO-10: INT8 quantization (2~3배, 정확도 검증 필요)

### 최종
- [ ] 다시 TODO-1 실행 → 개선 확인
- [ ] PIPELINE_SPEEDUP_GUIDE 의 예상 vs 실제 비교
- [ ] 다음 TODO 사이클 계획

---

## 📝 메모

이 파일에 작업 중 발견하는 내용 추가:

### 새 발견
(여기에 메모)

### 추가 TODO
(여기에 메모)

### 막힌 부분
(여기에 메모)

---

**마지막 업데이트**: 2026-05-22 (분석/문서화 세션 종료)
**다음 세션**: 다른 컴퓨터에서 TODO-1, TODO-2 부터 시작
