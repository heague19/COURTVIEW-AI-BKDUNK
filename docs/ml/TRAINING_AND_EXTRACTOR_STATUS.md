# COURTVIEW 학습/추출기 종합 현황

> 최종 갱신: 2026-04-25
> 작성: SPOIN_COURTVIEW
> 범위: 본 세션에서 추가된 추출기 + 11개 가중치 학습 로드맵 + 전 추출기 인벤토리

---

## 1. 본 세션 업데이트 (DTO + Extractor + Writer)

### 1.1 `shared/dto/dataset_dto.py` 확장

**DatasetType enum 5종 추가**

| 값 | 용도 |
|---|---|
| `RECORDER_EVENT` | CV-Recorder (Score+Rebound+Assist+Steal+Turnover+Block) |
| `COACH_SHOT_SUBTYPE` | CV-Coach 슛 13종 |
| `COACH_DRIBBLE_SUBTYPE` | CV-Coach 드리블 13종 |
| `COACH_PASS_SUBTYPE` | CV-Coach 패스 11종 |
| `POSSESSION_FRAME` | CV-Possession 프레임 단위 라벨 |

**Record dataclass 5종 추가** (모두 `slots=True`)

| 클래스 | 핵심 필드 |
|---|---|
| `RecorderEventRecord` | trigger_frame, primary_event/subtype, frame_indices, ball_positions, primary/secondary_player_id, hoop_position, quarter, game_clock_sec, score_diff |
| `CoachShotSubtypeRecord` | shot_subtype(13종), shooter_id+keypoints, ball_positions, is_made, shot_distance_m, contested |
| `CoachDribbleSubtypeRecord` | dribble_subtype(13종), dribbler_id+keypoints, duration_sec, is_change_direction |
| `CoachPassSubtypeRecord` | pass_subtype(11종), passer_id, receiver_id, ball_trajectory, pass_distance_m, is_assist |
| `PossessionFrameRecord` | frame_index, possessor_id, candidate_player_ids, candidate_distances_m, candidate_hand_distances_m, recent_possessor_ids |

### 1.2 `motion_analysis/data_extraction/` 신설 모듈

| 파일 | 역할 | 주요 인터페이스 |
|---|---|---|
| `recorder_event_extractor.py` | 6이벤트 통합 시퀀스 추출, 인과체인 보존 (전60+후60 프레임 ≈ 4초@30fps) | `start_session` / `push_frame` / `push_event` / `finalize` |
| `coach_subtype_extractor.py` | 슛/드리블/패스 서브타입 통합. 카테고리별 윈도우(슛±30, 드리블±15, 패스±20-25) | `push_shot` / `push_dribble` / `push_pass` |
| `possession_frame_extractor.py` | 프레임 단위 possessor 라벨, 룰 기반 자동 + 수동 덮어쓰기 (sample_interval=3프레임) | `push_frame` / `push_possession_label` |
| `record_writer.py` | .jsonl 직렬화 + ExtractionResult 메타 채움 (file_path, file_size, s3_key) | `write` / `write_coach` |
| `__init__.py` | 4개 클래스+3개 Config 노출 | — |

**공통 패턴**
- 스레드 안전(`threading.RLock`)
- `min_confidence`(0.5) 필터, `min_sequence_ratio`(0.7) 검증
- `finalize()` → `(ExtractionResult, records)` 튜플 (Coach는 4튜플)

### 1.3 미완 — 다음 세션
- ❌ S3 업로드 서비스 (boto3): RecordWriter는 **메타만 채움**, 실업로드 없음
- ❌ `UploadStatus.PENDING → COMPLETED` 전이 로직
- ❌ Cloud Backend pull/push 결정

---

## 2. 가중치 학습 로드맵 (15개 모델 — 2026-04-26 갱신)

> 2026-04-26 갱신 #2: CV-Action 단일 8cls → CV-Action(7cls) + CV-Phase(6cls) 분리.
> 동작 분류와 위상(phase) 분류는 추출기 1개에서 multi-label 출력하지만 모델은
> 별도 학습 (multi-task 또는 분리). 총 15 모델로 확장.

> 2026-04-26: ARCHITECTURE_DESKTOP.md 와의 정합성 검증 결과 누락분 추가:
>   - **#4b ViTPose-B Stage2 (133kp)** — 이벤트 트리거 시 사용. weights/ 에 vitpose-b-wholebody.onnx 존재
>   - **#10b CV-ReID** — Layer 1 외관 임베딩, ARCHITECTURE 4 의 ~300MB 명시. 추출기 `reid_appearance_extractor` 보유
>   - 이전 #11 "CV-Foul / CV-Violation" 통합 항목을 분리하여 2 모델로 표기
>   - ARCHITECTURE 6.5 의 "Scout" 표기는 학습 모델 X — game_analysis/output/scouting/ 분석 출력. 흐름도 표기 오해

### 2.1 학습 상태 매트릭스

| # | 모델 | 상태 | 성능 | 추출기 | 비고 |
|---|---|---|---|---|---|
| 1 | CV-BBox v7 | ✅ 완료 | — | (외부) | TensorRT 변환 완료, 4cls(ball/player/hoop/backboard) |
| 2 | **CV-BBox v8 Phase1** | ✅ 완료 | mAP50 **95.3%**, mAP50-95 84.9% | `ball_bbox_extractor` 등 detection/* | 17 epoch best |
| 3 | **CV-BBox v8 Phase2** | 🟡 학습 중 | epoch1 95.4% | 동일 | 260K fine-tune (60 epoch), player 개선 목표 |
| 4 | CV-Pose Stage1 (YOLOv8l-Pose 25kp) | ✅ TensorRT 완료 (추출기 25kp 확장 2026-04-26) | — | `keypoint_extractor` (UNIFIED_25) | 매 프레임 25kp |
| 4b | **CV-Pose Stage2 (ViTPose-B 133kp)** | ✅ ONNX 보유 | — | `wholebody_keypoint_extractor` | 이벤트 트리거 시 호출 (shot/foul/rebound) |
| 5a | **CV-Action (7cls)** | ⏳ 추출기 ✅ (2026-04-26 신설), 학습 대기 | — | **`motion_analysis/data_extraction/action_extractor`** | shooting/dribbling/passing/layup/rebounding/movement/idle |
| 5b | **CV-Phase (6cls)** | ⏳ 추출기 ✅ (action_extractor 동시 출력) | — | **`action_extractor` (push_phase_label)** | idle/preparation/loading/execution/follow_through/recovery — Action 과 multi-task 가능 |
| 6 | **CV-Recorder** | ⏳ 추출기 ✅, 학습 대기 | — | **`recorder_event_extractor`** | Score 흡수형 통합 (made/missed/rebound/assist/steal/turnover/block) |
| 7a | **CV-Coach-Shot** | ⏳ 추출기 ✅, 학습 대기 | — | `coach_subtype_extractor` (슛 윈도우 ±30) | 슛 13종 분류 |
| 7b | **CV-Coach-Dribble** | ⏳ 추출기 ✅, 학습 대기 | — | `coach_subtype_extractor` (드리블 ±15) | 드리블 13종 |
| 7c | **CV-Coach-Pass** | ⏳ 추출기 ✅, 학습 대기 | — | `coach_subtype_extractor` (패스 ±20-25) | 패스 11종 |
| 8 | **CV-Possession** | ⏳ 추출기 ✅, 학습 대기 | — | `possession_frame_extractor` | 프레임 단위 ML (룰 + 수동 덮어쓰기) |
| 9 | CV-Digit v5 (YOLO11m) | ⏳ 데이터 준비 | — | `jersey_digit_extractor` | BBox v8 player crop 후 자동라벨+GUI 검수 |
| 10 | CV-Team v2 (256dim Triplet) | ⏳ 데이터 준비 | — | `team_uniform_extractor` | ResNet18 임베딩, 128→256 dim |
| 10b | **CV-ReID (OSNet 외관 임베딩)** | ❌ 추출기 ✅, 학습 미시작 | — | `reid_appearance_extractor` | 후순위 — 카메라 간 영구 ID 매칭. ARCHITECTURE 4 명시 |
| 11 | CV-Foul | ❌ 추출기 ✅, 학습 대기 | — | `foul_contact_extractor` | 룰 92% 보조용 ML 분류 |
| 12 | CV-Violation | ❌ 추출기 ✅, 학습 대기 | — | `violation_sequence_extractor` | 위반 시계열 패턴 분류 |

### 2.2 폐기

| 모델 | 사유 | 대체 |
|---|---|---|
| CV-BioML (RT 25kp / PRO 133kp) | 2026-04-18 결정 | biomechanics 룰 기반 모듈 강화 |
| court_detection (CourtLine/Zone) | 2026-04-20 결정 | configs/calibration/*.json 호모그래피 |
| YOLO `.engine` 직접 배포 | GPU 종속성 | ONNX 번들 → 고객 GPU에서 자동 engine 생성 |
| CV-Score 단독 모델 | 2026-04-20 (ARCHITECTURE 6.5) | CV-Recorder 가 이벤트 통합 판정 (인과관계 보존) |

### 2.2.1 학습 모델 아닌 항목 (오해 주의)

| 항목 | 실체 | 위치 |
|---|---|---|
| Scout | 학습 모델 X — **분석 출력 모듈** (스카우팅 리포트 룰 기반 생성) | `game_analysis/output/scouting/` |
| Predictive Models (xFG%/EPV/WP) | 학습 모델 X — **확률 계산 모듈** | `game_analysis/.../predictive_models/` |
| AI 심판 판정 엔진 | 학습 모델 X — **규칙 기반 92%+** | `ai_referee/` 룰셋 |

### 2.3 즉시 다음 학습 단계

1. Phase 2 BBox v8 완료 대기 (현재 진행)
2. BBox v8 → ONNX export (`opset=17 dynamic=True simplify=True`)
3. BBox v8 player crop 추출 → Digit v5 / Team v2 데이터셋
4. Digit v5 + Team v2 병렬 학습
5. CV-Recorder/Coach/Possession 데이터 추출 시작 (본 세션 추출기 사용)
6. CV-Action 학습 (별도 세션)

---

## 3. 데이터 추출기 전수 인벤토리

### 3.1 `motion_analysis/data_extraction/` (5개)

| 파일 | 대상 가중치 | 출력 DTO |
|---|---|---|
| `recorder_event_extractor.py` | CV-Recorder | RecorderEventRecord |
| `coach_subtype_extractor.py` | CV-Coach (Shot/Dribble/Pass) | CoachShot/Dribble/PassSubtypeRecord |
| `possession_frame_extractor.py` | CV-Possession | PossessionFrameRecord |
| **`action_extractor.py`** (2026-04-26) | **CV-Action (7cls) + CV-Phase (6cls)** | **ActionClassRecord / PhaseClassRecord** |
| `record_writer.py` | (공통 직렬화) | .jsonl |

### 3.2 `detection/*/data_extraction/` (검출 모델 학습용)

| 모듈 | 파일 | 대상 |
|---|---|---|
| ball_detection | `ball_bbox_extractor.py` | CV-BBox v7/v8 (ball) |
| ball_detection | `trajectory_extractor.py` | 볼 궤적 |
| ball_detection | `occlusion_sample_extractor.py` | 가림 샘플 |
| ball_detection | `temporal_sequence_extractor.py` | 시간 시퀀스 |
| ball_detection | `hard_negative_extractor.py` | Hard negative |
| court_detection | `arena_profile_extractor.py` | 코트 프로파일 |
| court_detection | `court_frame_extractor.py` | 코트 프레임 |
| court_detection | `zone_extractor.py` | 존(3점/페인트 등) |
| hoop_detection | `hoop_bbox_extractor.py` | CV-BBox v7/v8 (hoop) |
| hoop_detection | `net_motion_extractor.py` | 네트 모션 (득점 단서) |
| player_detection | `player_bbox_extractor.py` | CV-BBox v7/v8 (player) |
| player_detection | `team_uniform_extractor.py` | CV-Team v2 |
| player_detection | `jersey_digit_extractor.py` | CV-Digit v5 |
| player_detection | `reid_appearance_extractor.py` | (Re-ID, OSNet 후순위) |

### 3.3 `pose_estimation/data_extraction/`

| 파일 | 대상 |
|---|---|
| `keypoint_extractor.py` | YOLO-Pose 25kp |
| `wholebody_keypoint_extractor.py` | 133kp (PRO 폐기 후 보존) |
| `pose_sequence_extractor.py` | 포즈 시퀀스 |

### 3.4 `biomechanics/data_extraction/`

| 파일 | 용도 |
|---|---|
| `frame_extractor.py` | 프레임 단위 바이오메카닉스 입력 |
| `event_extractor.py` | 이벤트 트리거 |
| `sequence_extractor.py` | 시퀀스 (BioML 폐기 후 룰 입력용으로 유지) |

### 3.5 `game_analysis/data_extraction/`

| 파일 | 용도 |
|---|---|
| `frame_record_extractor.py` | 프레임 기록 |
| `possession_record_extractor.py` | 소유권 기록 (룰 기반) |
| `game_record_extractor.py` | 경기 기록지 |
| `tactical_sequence_extractor.py` | 전술 시퀀스 (리그 영상 학습 후보) |
| `prediction_outcome_extractor.py` | 예측 vs 실측 |
| `player_performance_extractor.py` | 선수별 퍼포먼스 |
| `event_correction_extractor.py` | 사용자 보정 라벨 |

### 3.6 `ai_referee/data_extraction/`

| 파일 | 대상 |
|---|---|
| `decision_record_extractor.py` | 심판 결정 기록 |
| `correction_pair_extractor.py` | 보정 페어 |
| `edge_case_extractor.py` | 엣지케이스 |
| `calibration_data_extractor.py` | 캘리브레이션 |
| `foul_contact_extractor.py` | CV-Foul (미구현 학습) |
| `violation_sequence_extractor.py` | CV-Violation (미구현 학습) |

### 3.7 인프라/유틸

| 파일 | 용도 |
|---|---|
| `infrastructure/preprocessing/frame_extractor.py` | 비디오→프레임 |
| `infrastructure/storage/metadata_extractor.py` | 메타데이터 |
| `tools/frame_extractor.py` | CLI 프레임 추출 |
| `game_analysis/output/highlight/clip_extractor.py` | 하이라이트 클립 |
| `game_analysis/output/highlight/clip_file_extractor.py` | 클립 파일 |

### 3.8 추출기 → 가중치 매핑 (4 카테고리)

#### A. 학습 활성 (TRAINING_TARGETS — 14 모델, 추출기 12개)

| 추출기 | 학습 가중치 |
|---|---|
| `ball_bbox_extractor` + `player_bbox_extractor` + `hoop_bbox_extractor` | **CV-BBox v8** (단일 4cls 모델) |
| `keypoint_extractor` (25kp) | **CV-Pose Stage1** (YOLOv8l-Pose) |
| `wholebody_keypoint_extractor` (133kp) | **CV-Pose Stage2** (ViTPose-B) |
| `jersey_digit_extractor` | **CV-Digit v5** (YOLO11m) |
| `team_uniform_extractor` | **CV-Team v2** (256dim Triplet) |
| `reid_appearance_extractor` | **CV-ReID** (OSNet, 후순위) |
| `recorder_event_extractor` | **CV-Recorder** |
| `coach_subtype_extractor` (3분기) | **CV-Coach-Shot/Dribble/Pass** (3 모델) |
| `possession_frame_extractor` | **CV-Possession** |
| `foul_contact_extractor` | **CV-Foul** (룰 92% 보조 ML) |
| `violation_sequence_extractor` | **CV-Violation** |
| (별도 세션) | **CV-Action** |

#### B. 보조 입력 (AUXILIARY — 학습 활성 모델 augmentation, 8개)

| 추출기 | 흡수 대상 | 역할 |
|---|---|---|
| `hard_negative_extractor` | CV-BBox | 부정 샘플 (오탐 억제) |
| `occlusion_sample_extractor` | CV-BBox | 가려짐 강화 |
| `temporal_sequence_extractor` | CV-BBox | 시간 일관성 |
| `trajectory_extractor` | CV-BBox / CV-Recorder | 궤적 정답 |
| `net_motion_extractor` | CV-Recorder | 득점 단서 |
| `pose_sequence_extractor` | (포즈 시계열 후보) | 미정 |
| `arena_profile_extractor` | (색상/조명 정규화) | 전처리 보조 |
| `(foul_scene)` 미존재 — DTO 만 정의 | CV-Foul/Violation 보조 | — |

#### C. 자가학습 (SELF_REFINEMENT — Phase 2~4, ai_referee 4개)

ARCHITECTURE 6.7: 룰 92% → 자가학습 96~98% 도달 경로.

| 추출기 | 단계 | 목적 |
|---|---|---|
| `decision_record_extractor` | Phase 2 | 베이스라인 재현 |
| `correction_pair_extractor` | Phase 2 | 명시적 오류 신호 (최고 가치) |
| `edge_case_extractor` | Phase 3 | 능동 학습 (라벨링 우선순위) |
| `calibration_data_extractor` | Phase 2 | 신뢰도 보정 곡선 |

#### D. 데이터 보존만 (PRESERVED_NO_TRAINING — 학습 미정의, 10개)

후일 자체 모델 추가 시 활용. 현재는 추출 → S3 보존만.

| 추출기 | 비고 |
|---|---|
| `frame_record_extractor` | game_analysis 자체 모델 (검토 후) |
| `possession_record_extractor` | 동상 |
| `game_record_extractor` | 동상 |
| `event_correction_extractor` | 동상 |
| `tactical_sequence_extractor` | "전술 분석 모델 (데모 후 검토)" |
| `player_performance_extractor` | 동상 |
| `prediction_outcome_extractor` | 동상 (xFG%/EPV/WP 캘리브레이션) |
| `event_extractor` (biomechanics) | CV-BioML 폐기, 룰 입력만 |
| `frame_extractor` (biomechanics) | 동상 |
| `sequence_extractor` (biomechanics) | 동상 |

#### E. 폐기 (DEPRECATED — court_detection 3개)

`arena_profile_extractor` 는 보조로 살아남음. 나머지 2개:

| 추출기 | 폐기 사유 |
|---|---|
| `court_frame_extractor` | court_detection 폐기 (캘리브레이션 대체) |
| `zone_extractor` | 동상 |

---

## 4. 다음 세션 위임 항목

| 항목 | 이유 |
|---|---|
| S3 업로드 서비스 (boto3) | 인프라 트랙, DESK→Cloud 또는 Cloud-pull 결정 필요 |
| CV-Action 학습 | 별도 세션 진행 중 |
| 가중치 재학습 (트랙B) | 유대리 담당 별도 세션 |

---

## 5. 변경 이력

| 날짜 | 항목 |
|---|---|
| 2026-04-18 | CV-BioML 폐기, biomechanics 룰 기반 강화 결정 |
| 2026-04-19 | BBox v8 (API 유지) / Digit v5 (YOLO11m) / Team v2 (256dim) 모델 업그레이드 확정 |
| 2026-04-20 | 11개 가중치 최종 로드맵 확정 (CV-Recorder가 Score 흡수) |
| 2026-04-21 | ONNX 배포 방식 확정 (.engine 폐기) |
| 2026-04-25 | DTO+Extractor 5종 추가 + RecordWriter 신설 (본 세션) |
