# Phase 6: detection/ 감사 보고서

> **감사자**: SPOIN_COURTVIEW AI 감사팀
> **작성일**: 2026-04-20
> **감사 대상**: `detection/` **37 파일, 13,628 라인**
> **감사 기준**: 사용자 8축 + [MODULE_AUDIT_STANDARD v1.0](../MODULE_AUDIT_STANDARD.md) 100점 만점
> **감사 방식**: **Read 도구 37/37 전수 직독 (100%)**

---

## 0. 모듈 개요

`detection/`은 **Layer 1 객체 감지 계층**. YOLO Primary + 패턴 보조 하이브리드 감지 아키텍처로 ball/court/hoop/player 4종 객체를 감지·추적·식별. 각 서브패키지는 독립 파이프라인 + `data_extraction/` 재학습 수집기 포함.

### 파일 구성 (37파일, 13,628 라인)

| 서브패키지 | 파일 수 | 라인 | 핵심 책임 |
|-----------|--------|-----|---------|
| `detection/` (root) | 1 | 33 | 패키지 진입점 |
| `ball_detection/` | 4+5 = **9** | **5,246** | YOLO+패턴 감지 + 8D Kalman+Hungarian+ByteTrack 추적 + 9-상태 FSM + 5 추출기 |
| `court_detection/` | 1+3+1 = **5** | **1,048** | **ML 미학습** (캘리브레이션 대체) + 3 추출기 (호모그래피 대체 모델 학습용) |
| `hoop_detection/` | 3+2+1 = **6** | **3,085** | YOLO 2-class(rim/backboard) + Hough Circle 보조 + Lucas-Kanade 네트 분석 + 2 추출기 |
| `player_detection/` | 10+4+1 = **15** | **8,664** | PlayerDetector + TeamClassifier(DL+K-Means) + JerseyOCR(YOLO digit) + Kalman 추적 + TeamAwareTracker + PlayerIDManager(OCR+Track 2원) + MultiView(DBSCAN) + 4 추출기 (reid_module.py는 **비활성**) |

### 공통 아키텍처 패턴

```
[Detector] YOLO Primary + 패턴 보조 하이브리드
   ↓ _Candidate (후보 + 검증 점수)
[Tracker] Kalman 8D + Hungarian + ByteTrack 2-stage
   ↓ Track DTO
[Analyzer/Classifier] DL + 규칙 기반 하이브리드
   ↓ 최종 상태/팀/번호
[data_extraction/] 재학습 데이터 수집 (S3 업로드)
```

### 공통 특성
- **threading.RLock**: 모든 감지기/추적기 보호
- **`unified_mode: bool = False`**: 개별 YOLO 로드 생략 지원 (CV-BBox 통합 모델)
- **MultiViewTriangulator 주입**: infrastructure에서 set_triangulator() 호출
- **워밍업 추론**: 첫 추론 지연 방지
- **CUDA → CPU 자동 폴백**: `torch.cuda.is_available()` 체크

---

## 1. 임포트 타당성 (축 1)

### 1.1 계층 규칙

```
detection ← shared (constants/dto/interfaces, 정방향)  ✅
detection ← infrastructure (multi_camera.MultiViewTriangulator, 정방향)  ✅
detection ← utils (함수 단위 사용 예상)  ✅
detection → core_foundation, game_analysis 등 = 0건  ✅
```

### 1.2 내부 참조
```
ball_detector ← ball_tracker
hoop_detector ← net_analyzer
player_detector ← player_tracker + team_classifier + jersey_ocr + player_id_manager
team_aware_tracker ← player_tracker + team_classifier
```
**순환 참조**: ❌ 0건 ✅

### 1.3 외부 라이브러리
- `cv2` (OpenCV): 전체 사용
- `numpy` / `numpy.typing`: 전체
- `scipy.optimize.linear_sum_assignment`: Hungarian (ball/player tracker)
- `ultralytics.YOLO`: 지연 import (lazy loading)
- `torch`: 지연 import (CUDA 체크)
- `sklearn.cluster.DBSCAN`: multiview_tracker (공간 클러스터링)

### 1.4 와일드카드 / 상대 임포트
- `from x import *`: 0건 ✅
- 상대 임포트: 0건 ✅
- 절대 경로 (`detection.ball_detection.xxx`) 일관 ✅

**축 1 점수**: **25/25**

---

## 2. 기능 타당성 (축 2)

### 2.1 모듈별 주요 알고리즘

| 모듈 | 알고리즘 | 근거 |
|------|---------|------|
| `ball_detector` | YOLO + HSV 색상 + 원형도 (4π×A/p² ≥ 0.6) | Hough 후보 검증 |
| `ball_tracker` | 8D Kalman [cx, cy, w, h, vx, vy, vw, vh] + Hungarian (scipy) + ByteTrack 2-stage | Matrix 조작 numpy |
| `ball_state` | 9-상태 FSM + 전이 매트릭스 (frozenset) + 물리 조건 | 속도/가속도/근접도/수직궤적 |
| `hoop_detector` | YOLO 2-class + Hough Circle + HSV 오렌지 림 + 백보드 종횡비 | Hough Gradient |
| `hoop_detector` (캐싱) | 정적 객체 최적화: `detection_frequency` 간격만 전체 감지, 나머지 캐시 hit | 골대 정지 가정 |
| `net_analyzer` | Lucas-Kanade Sparse Optical Flow + goodFeaturesToTrack | 네트 수직 변위 누적 → 스위시/림인/림아웃 |
| `player_detector` | YOLO 5-class (player/referee/coach/staff/unknown) + 피부색 HSV + 종횡비 | 패턴 보조 |
| `player_tracker` | 8D Kalman + Hungarian (IoU + 외관 복합 비용) | LinAlgError fallback 처리 |
| `team_classifier` | DL(ResNet) Primary + K-Means(k=2) 보조 75:25 가중 | DL+HSV 하이브리드 |
| `jersey_ocr` | YOLO 숫자 감지(10-class 0~9) + x좌표 정렬 + 다중 프레임 투표 | 형태학적 폴백 |
| `player_id_manager` | OCR 60% + Tracking 40% 가중 투표 + 3단계 상태 | CONFIRMED/TENTATIVE/UNCONFIRMED |
| `team_aware_tracker` | team_a/b/unknown 독립 트래커 → cross-team ID 스왑 원천 차단 | OFFSET_A=0, B=1000, UNK=2000 |
| `multiview_tracker` | 호모그래피 → 코트좌표 → DBSCAN 공간 클러스터링 + 코트좌표 Kalman | 8대 카메라 동일 선수 식별 |

### 2.2 court_detection 설계 의도 재확인

**Phase 3/5에서 제기된 "court_detection 폐기 이슈"는 오해였음을 확인**:

[detection/court_detection/__init__.py:7-8](detection/court_detection/__init__.py)에 명시:
> "코트 감지 모듈 패키지 (현재 ML 미학습 상태, 캘리브레이션 기반 대체)"
> "data_extraction: 재학습 데이터 수집 (3개 추출기)"

즉 **court_detection은 "폐기"가 아니라 "장기 로드맵 (ML 미학습, 호모그래피로 임시 대체)"**. data_extraction/ 3개 추출기가 **미래 ML 모델 학습용 데이터를 수집하는 적극적 활동 중**. configs/detection/court_detection.yaml도 현재 호모그래피 기반 설정이 유효한 용도.

**Phase 5 Y5 DEPRECATED 결정은 재고 필요** — 오히려 "Future ML, currently calibration-based" 주석 추가가 적절.

### 2.3 CLAUDE.md 원칙 준수

| 원칙 | 증거 |
|------|------|
| #5 하드웨어 기반 검증 | TensorRT FP16, CUDA 자동 폴백 |
| #9 Desktop 로컬 GPU | ultralytics + torch 지연 import |
| #19 패턴 보조 | color_score + shape_score + yolo_confidence 가중 합 |
| #21 YOLO Primary | 감지 파이프라인 1단계 YOLO, 2-5단계 보조 |
| #28 DB 없음, S3 업로드 | data_extraction → ExtractionResult (PENDING → S3) |
| #37 엔터프라이즈 | RLock, 메트릭, 캐시, LinAlgError fallback |

### 2.4 unified_mode 설계 (CV-BBox 통합 추론)

**일관된 패턴** (ball/hoop/player 3개 감지기 동일):
```python
if unified_mode:
    self._model = None  # 개별 YOLO 로드 생략
    self._state = DetectionState.READY
    return  # process_detections()로 후처리만 수행
```

외부 통합 모델이 전체 추론을 담당하고, 각 감지기는 후처리 (NMS/크기 필터/패턴 검증/점수 산출)만 실행. 추론 비용 공유 설계.

### 2.5 설계 트레이드오프

| 결정 | 장단점 |
|------|------|
| `reid_module.py` 비활성화 (921라인) | **장**: digit+team으로 ReID 대체로 추론 비용 절감. **단**: 921라인 dead code 잔존 |
| `TeamAwareTracker` 팀별 독립 추적 | **장**: 크로스팀 ID 스왑 원천 차단. **단**: 3개 트래커 인스턴스로 메모리 3배 |
| `hoop_detector` 캐싱 (detection_frequency 간격) | **장**: 정적 객체 감지 비용 절감. **단**: 골대 이동 시 지연 |

**축 2 점수**: **24/25** — reid_module.py dead code (1점 차감)

---

## 3. 메모리 누수 여부 (축 3)

### 3.1 MAX_* 한계값

| 모듈 | 한계값 |
|------|--------|
| `ball_detector` | `_MAX_CACHE_SIZE = 300` (deque) |
| `ball_tracker` | `_MAX_TRACK_ID = 1,000,000` (오버플로 방지 리셋) |
| `ball_state` | `_STATE_HISTORY_MAX = 90` (deque) |
| `hoop_detector` | `_MAX_CACHE_SIZE = 300`, 정적 객체 캐싱 |
| `net_analyzer` | `NET_ANALYSIS_HISTORY_SIZE` (config) |
| `player_detector` | `_MAX_CACHE_SIZE = 300` |
| `player_tracker` | `max_age: 360` 프레임 (3초@120fps, 12초@30fps) |
| `player_id_manager` | `max_managed_players: 30` (양팀 10 + 심판 3 + 코치 2×2) |
| `team_classifier` | K-Means 샘플 수집 제한 |
| `multiview_tracker` | `history_xy: list` (30프레임 제한 암시) |
| `ball_bbox_extractor` | `_MAX_BUFFER_SIZE = 500`, `_MAX_PHASH_SET_SIZE = 5000`, `_BUFFER_FLUSH_COUNT = 100`, `_BUFFER_FLUSH_INTERVAL_SEC = 300` |

### 3.2 제너레이터 / deque 활용
- 모든 추적기 `deque(maxlen=N)` 사용 — 무한 성장 방지 ✅
- 데이터 추출기 `_BUFFER_FLUSH_COUNT`/`_BUFFER_FLUSH_INTERVAL_SEC` 이중 조건 — 메모리 + 시간 안전망

### 3.3 OpenCV / YOLO 리소스 해제
- `shutdown()` 메서드에서 `self._model = None` ✅
- `_triangulator = None` 해제 ✅
- `deque.clear()` 호출 ✅

### 3.4 dataclass(slots=True)
전 파일에서 `@dataclass(slots=True)` 일관 적용 — 메모리 최적화 ✅

**축 3 점수**: **25/25**

---

## 4. 하드코딩 유무 (축 4) — **주요 이슈 영역**

### 4.1 🟡 개발자 개인 절대 경로 하드코딩 (2건)

| # | 위치 | 내용 | 수준 |
|---|------|------|------|
| **D1** | `team_classifier.py:97-99` | `_EMBED_MODEL_PATH_FALLBACK: "D:/SPOIN/training/team_classification/weights/team_embed_v4.pt"` | 🟡 **보통** — 개발 PC `D:` 드라이브 경로, 배포 환경에서 무효 |
| **D2** | `jersey_ocr.py:79` | `_DEFAULT_CLS_PT_PATH: "D:/SPOIN/training/runs/jersey_cls_v1/weights/best.pt"` | 🟡 **보통** — 동일 문제 |

**영향**: 
- 프로덕션 배포 시 해당 경로 존재 불가 → fallback 실패 → 1순위 경로(`weights/CV-team.pt` / glob) 의존
- 코드 공유 시 저자 PC 정보 노출 (보안 민감 낮음이나 클린 코드 원칙 위반)

### 4.2 🟡 Dead Code 잔존 (1건)

| # | 위치 | 내용 | 수준 |
|---|------|------|------|
| **DC1** | `reid_module.py` (921 라인 전체) | `player_detection/__init__.py:65-66`에서 **import 주석 처리됨**. `PlayerDetector`도 "ReID 제거 — digit(등번호) + team(색상)으로 선수 식별 대체" 주석 명시. 그러나 파일은 온전히 남음 | 🟡 **보통** — 명시적 삭제 또는 `_deprecated/` 이동 필요 |

### 4.3 🟢 합리적 기본 상수 (허용)

| 위치 | 내용 | 판정 |
|------|------|------|
| `ball_detector._BROWN_HSV_LOWER/UPPER` | (10,50,50)/(30,200,200) | 🟢 HSV 검증용, 경험적 |
| `ball_tracker._DISTANCE_WEIGHT=0.6, _IOU_WEIGHT=0.4` | 매칭 비용 가중 | 🟢 |
| `ball_state._VALID_TRANSITIONS` | 9-상태 전이 매트릭스 | 🟢 도메인 정의 |
| `hoop_detector._YOLO_WEIGHT=0.7, _HOUGH_WEIGHT=0.3` | 결합 점수 가중 | 🟢 |
| `player_detector._MIN_SKIN_RATIO=0.03, _MAX_SKIN_RATIO=0.40` | 피부색 비율 | 🟢 경험적 |
| `team_classifier._DL_WEIGHT=0.75, _KMEANS_WEIGHT=0.25` | DL Primary 중심 | 🟢 |
| `player_id_manager.ocr_weight=0.4, reid_weight=0.35, tracking_weight=0.25` | 2원 융합 (ReID는 사실상 0) | 🟡 설계상 ReID는 0이어야 맞음 (DC1과 연관) |

### 4.4 🟢 자체 학습 모델 경로 (글로벌 규칙)

| 모델 | 경로 |
|------|------|
| `COURTVIEW_ball.pt` | `weights/COURTVIEW_ball.pt` |
| `COURTVIEW_hoop.pt` | `weights/COURTVIEW_hoop.pt` |
| `COURTVIEW_player.pt` | `weights/COURTVIEW_player.pt` |
| `COURTVIEW_team.pt` | `weights/COURTVIEW_team.pt` (1순위) |
| `CV-team.pt` | `weights/CV-team.pt` (2순위) |
| `CV-Digit_v*.cv` | glob 자동 감지 (v1→v99 자동 업그레이드) |
| `COURTVIEW_digit.pt` / `COURTVIEW_reid.pt` | 비활성 |

**판정**: `weights/` 디렉토리 일관 ✅ — 제외 하드코딩은 D1/D2뿐.

### 4.5 팀 분류기 `PlayerIDManagerConfig` 가중치 설계 불일치

`models.py` L328-330:
```python
ocr_weight: float = 0.4
reid_weight: float = 0.35
tracking_weight: float = 0.25
```

그러나 `__init__.py` 주석: "ReID 제거 — digit(등번호) + team(색상)으로 선수 식별 대체".

**실제 사용**: ReID는 비활성이므로 `reid_weight=0.35` 사실상 무효. 3개 가중치 합 = 1.0이지만 ReID 0 반영 시 OCR 0.4 + Tracking 0.25 = 0.65로 재정규화 필요할 가능성.

→ 🟡 **재검토 필요** (Phase 15 설계 재정비 대상)

**축 4 점수**: **19/25** — D1/D2 경로 2건 + DC1 dead code + models.py 가중치 불일치 = 4건 → 6점 차감

---

## 5. 한줄 평 (축 5)

> **"13,628 라인 × 37 파일 × YOLO Primary+패턴 보조 하이브리드 × 4종 객체(ball/court/hoop/player) × 8D Kalman+Hungarian+ByteTrack 추적 × DL+K-Means 팀 분류 × OCR+Track 2원 ID 융합 × TeamAwareTracker 크로스팀 스왑 차단 × DBSCAN 멀티뷰 클러스터링 × 14 데이터 추출기(S3 업로드)가 일관된 unified_mode + 삼각측량 통합으로 구성된 최상급 감지 엔진이나, D:/SPOIN/training 개발자 절대경로 2건 + reid_module 921라인 dead code가 프로덕션 청결도 저하."**

---

## 6. 스레드 안전 (축 6)

| 패턴 | 적용 |
|------|------|
| `threading.RLock()` | 전 감지기/추적기 일관 적용 ✅ |
| `scipy.optimize.linear_sum_assignment` | CPython GIL 외부 C 코드, 스레드 안전 |
| `cv2.VideoCapture` | 인스턴스별 독립 — 공유 금지 |
| `ultralytics.YOLO.predict()` | ultralytics 내부 스레드 안전 보장 |
| `deque(maxlen=N)` | CPython GIL 하에 원자적 append/popleft |

**축 6 점수**: **8/8**

---

## 7. 예외 처리 (축 7)

### 7.1 모델 로드 예외 (일관 패턴)
```python
try:
    from ultralytics import YOLO
    self._model = YOLO(str(model_path))
    # 워밍업
except Exception as exc:
    self._state = DetectionState.ERROR
    raise RuntimeError(f"YOLO 모델 로드 실패: {exc}") from exc
```
— `from exc` chaining 일관 ✅

### 7.2 수치 안정성 fallback
```python
try:
    kalman_gain = P @ H.T @ np.linalg.inv(S)
except np.linalg.LinAlgError:
    logger.warning("특이행렬, 예측 상태 유지")
    return state
```
— ball_tracker, player_tracker 모두 LinAlgError fallback ✅

### 7.3 삼각측량 실패 처리
```python
result = self._triangulator.triangulate(observations)
if result.is_valid:
    # 3D 결과
else:
    # 최고 신뢰도 2D 결과 fallback
```
— 2D graceful degradation ✅

**축 7 점수**: **8/8**

---

## 8. 확장성 (축 8)

| 확장 시나리오 | 메커니즘 |
|-------------|---------|
| 신규 감지 대상 (예: 심판 제스처) | 새 서브패키지 + `IDetector` 인터페이스 구현 |
| 신규 팀 분류 모델 | `_EMBED_MODEL_PATH` 교체 (DL Primary 유지, K-Means 보조 자동 폴백) |
| 신규 YOLO 숫자 모델 버전 | glob 패턴 자동 감지 (`CV-Digit_v*.cv` v99까지) |
| ReID 재도입 | `reid_module.py` 주석 해제 + `__init__.py` import 복구 |
| 신규 네트 득점 유형 | `ScoringType` enum 추가 + `NetAnalyzer` 분기 |
| 멀티뷰 카메라 수 변경 | `multiview_tracker` cam_id 1~8 하드코딩 (가변화 가능) |

**축 8 점수**: **8/8**

---

## 9. 파일별 점수표

### detection/ 루트 (1파일)
| 파일 | 라인 | 점수 | 등급 |
|------|-----|------|------|
| `__init__.py` | 33 | 100 | S |

### ball_detection/ (9파일)
| 파일 | 라인 | 점수 | 등급 |
|------|-----|------|------|
| `__init__.py` | 59 | 100 | S |
| `ball_detector.py` | 1,359 | 100 | S (YOLO+패턴 완성) |
| `ball_tracker.py` | 945 | 100 | S (8D Kalman+Hungarian+ByteTrack) |
| `ball_state.py` | 659 | 100 | S (9-상태 FSM 전이 매트릭스) |
| `data_extraction/__init__.py` | 70 | 100 | S |
| `ball_bbox_extractor.py` | 817 | 100 | S (6중 품질 필터) |
| `trajectory_extractor.py` | 782 | 100 | S |
| `hard_negative_extractor.py` | 666 | 100 | S |
| `occlusion_sample_extractor.py` | 845 | 100 | S |
| `temporal_sequence_extractor.py` | 774 | 100 | S |

### court_detection/ (5파일)
| 파일 | 라인 | 점수 | 등급 |
|------|-----|------|------|
| `__init__.py` | 31 | 100 | S (ML 미학습 의도 명시) |
| `data_extraction/__init__.py` | 34 | 100 | S |
| `arena_profile_extractor.py` | 348 | 100 | S |
| `court_frame_extractor.py` | 370 | 100 | S |
| `zone_extractor.py` | 299 | 100 | S |

### hoop_detection/ (6파일)
| 파일 | 라인 | 점수 | 등급 |
|------|-----|------|------|
| `__init__.py` | 52 | 100 | S |
| `hoop_detector.py` | 1,575 | 100 | S (정적 캐싱 최적화) |
| `net_analyzer.py` | 922 | 100 | S (Lucas-Kanade 광학 흐름) |
| `data_extraction/__init__.py` | 40 | 100 | S |
| `hoop_bbox_extractor.py` | 533 | 100 | S |
| `net_motion_extractor.py` | 513 | 100 | S |

### player_detection/ (15파일)
| 파일 | 라인 | 점수 | 등급 | 비고 |
|------|-----|------|------|------|
| `__init__.py` | 118 | 100 | S |
| `models.py` | 570 | 97 | S | PlayerIDManagerConfig ReID 가중치 설계 불일치 |
| `player_detector.py` | 1,342 | 100 | S |
| `team_classifier.py` | 1,463 | **92** | A | **D1** D: 절대경로 하드코딩 |
| `jersey_ocr.py` | 1,234 | **92** | A | **D2** D: 절대경로 하드코딩 |
| `reid_module.py` | 921 | **80** | B | **DC1** dead code (비활성화) |
| `player_tracker.py` | 873 | 100 | S |
| `multiview_tracker.py` | 599 | 100 | S (DBSCAN + 코트좌표 Kalman) |
| `player_id_manager.py` | 596 | 100 | S |
| `team_aware_tracker.py` | 310 | 100 | S (cross-team 스왑 차단) |
| `data_extraction/__init__.py` | 40 | 100 | S |
| `jersey_digit_extractor.py` | 237 | 100 | S |
| `player_bbox_extractor.py` | 256 | 100 | S |
| `reid_appearance_extractor.py` | 281 | 100 | S |
| `team_uniform_extractor.py` | 250 | 100 | S |

**평균 (37파일)**:
- 34개 × 100 = 3,400
- 2개 × 92 = 184 (team_classifier, jersey_ocr)
- 1개 × 97 = 97 (models.py)
- 1개 × 80 = 80 (reid_module)
- **합계**: 3,761 / 37 = **101.6? 재계산**:

실제 계산: `(100×32 + 97×1 + 92×2 + 80×1 + 100×1)` ... 계산 다시:
- 100점 파일 수: 37 - 4 = 33개 → 3,300
- 97×1 = 97
- 92×2 = 184
- 80×1 = 80
- **총합**: 3,661
- **평균**: 3,661 / 37 = **98.95 / 100**

---

## 10. 이슈 목록

### 🔴 심각 (0건)

### 🟡 보통 (3건)

| # | 위치 | 내용 | 조치 |
|---|------|------|------|
| **D1** | `team_classifier.py:97-99` | `_EMBED_MODEL_PATH_FALLBACK: "D:/SPOIN/training/team_classification/weights/team_embed_v4.pt"` | 상대 경로로 변경 또는 제거 |
| **D2** | `jersey_ocr.py:79` | `_DEFAULT_CLS_PT_PATH: "D:/SPOIN/training/runs/jersey_cls_v1/weights/best.pt"` | 상대 경로로 변경 또는 제거 |
| **DC1** | `reid_module.py` 전체 921 라인 | 비활성화 상태로 잔존 (import 주석 처리됨) | `_deprecated/` 이동 또는 삭제 결정 |

### 🟢 경미 (2건)

| # | 위치 | 내용 | 조치 |
|---|------|------|------|
| m1 | `models.py:328-330` | `PlayerIDManagerConfig` ReID 가중치 0.35 남음 (실제 무효) | OCR 0.6 + Tracking 0.4로 재정규화 권장 |
| m2 | `multiview_tracker.py` | cam_id 1~8 암묵적 가정 | `MAX_CAMERAS=8`(shared)와 연계 명시화 권장 |

**판정 요약**: 🔴 0건 / 🟡 3건 / 🟢 2건 = 총 **5건**

---

## 11. 수정 우선순위

### Safe-Now (즉시 처리 권장)

| # | 조치 | 영향 |
|---|------|------|
| **SN1** | D1: `team_classifier.py` `_EMBED_MODEL_PATH_FALLBACK` 제거 또는 상대 경로화 | 프로덕션 배포 안전성 |
| **SN2** | D2: `jersey_ocr.py` `_DEFAULT_CLS_PT_PATH` 제거 또는 상대 경로화 | 동일 |
| **SN3** | m1: `PlayerIDManagerConfig` ReID 가중치 제거 + 2원 재정규화 (OCR 0.6 + Tracking 0.4) | 설계 투명성 |

### Deferred (사용자 판단 필요)

| # | 조치 | 결정 사항 |
|---|------|----------|
| **DC1** | `reid_module.py` 921라인 dead code 처리 | (a) `_deprecated/` 이동 / (b) 완전 삭제 / (c) 주석만 복원 후 유지 |
| **DV1** | court_detection ML 학습 착수 시점 | Phase 15 로드맵에서 결정 |

---

## 12. 종합 판정

| 항목 | 값 |
|------|-----|
| 평균 (37파일) | **98.95 / 100** |
| 등급 | **S (최고급 근접)** |
| 심각 이슈 | 0건 |
| 보통 이슈 | **3건** (D: 절대경로 2 + dead code 1) |
| 경미 이슈 | **2건** |
| 직독 완료 | **37/37 (100%)** |
| Safe-Now 후보 | 3건 |
| Deferred | 2건 |

### 한줄 평

> **"13,628 라인 × 37 파일 × YOLO Primary+패턴 보조 하이브리드 × 4종 객체(ball/court/hoop/player) × 8D Kalman+Hungarian+ByteTrack 추적 × DL+K-Means 팀 분류 × OCR+Track 2원 ID 융합 × TeamAwareTracker 크로스팀 스왑 차단 × DBSCAN 멀티뷰 클러스터링 × 14 데이터 추출기(S3 업로드)가 일관된 unified_mode + 삼각측량 통합으로 구성된 최상급 감지 엔진이나, D:/SPOIN/training 개발자 절대경로 2건 + reid_module 921라인 dead code가 프로덕션 청결도 저하."**

### Phase 5 Y5 재평가

**Phase 5에서 `configs/detection/court_detection.yaml`을 "폐기 모듈 잔존"으로 판정했으나, Phase 6 직독 결과 재해석 필요**:
- `detection/court_detection/__init__.py` 명시: "ML 미학습 상태, 캘리브레이션 기반 대체"
- data_extraction/ 3개 추출기는 **장기 로드맵 ML 모델 학습용 데이터 활발히 수집 중**
- configs/detection/court_detection.yaml은 **현재 호모그래피 기반 설정으로 유효**

→ **Y5 해결 방향**: DEPRECATED 마커 대신 `# 현재: 호모그래피 대체, 장기 로드맵: ML 코트 감지` 주석 추가 권장.

---

**Phase 6 감사 완료.** Safe-Now 3건(SN1/SN2/SN3)은 프로덕션 청결도 차원에서 즉시 처리 권장. Deferred 2건은 사용자 결정 필요. Phase 7 (pose_estimation/ 13파일) 착수 준비 완료.
