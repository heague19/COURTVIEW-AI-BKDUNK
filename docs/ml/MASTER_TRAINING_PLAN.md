# COURTVIEW Master Training Plan (v3)

> **Single Source of Truth** for 가중치 학습/배포.
> v3: 사용자 결정 6항목 반영 — CV-Record(기록원 대체) 정의, REID/single-view 보류 확정, Highlight 단계적 LLM→자체학습, CV-Score 귀속, Phase D 우선순위 (XFG→EPV→WP→Lineup) 확정.
> v2: 전 모듈 (`detection`, `motion_analysis`, `feedback_system`, `game_analysis/{event_detection, output, stats}`, `ai_referee`, `biomechanics`, `pose_estimation`) 전수 스캔.
> v1: 1-pass 초안.

---

## 0. 네이밍 컨벤션 (확정)

코드 (`detection/player_detection/jersey_ocr.py:75` glob `CV-Digit_v*.pt`) 가 사용 중인 패턴 = **SSOT**.

```
CV-{CapName}_v{N}[.M].{pt|onnx|engine}

예) CV-BBox_v9.pt        ← PyTorch 원본
    CV-BBox_v9.onnx      ← ONNX
    CV-BBox_v9.engine    ← TensorRT (GPU별 캐시, 첫 실행 자동 빌드)

새 학습 → _v{N+1}. hotfix → _v9.1.
```

배치 위치: `weights/CV-*.pt` (절대 경로 자동 분기 → `engine/orchestrator/game_orchestrator.py::_resolve_weights_dir()`).

---

## 1. 모듈 → 가중치 통합 매트릭스 (전수)

### Phase A — Core Perception (직접 추론)

| # | 모델 | 입력 | 출력 | 통합 모듈 | 상태 | P |
|---|---|---|---|---|---|---|
| **1** | **CV-BBox_v9** | RGB 1080p | ball / player / hoop / backboard bbox | `detection/{ball,player,hoop}_detection/*` 전부 통합 (`engine/pipeline/fusion/detection_fusion.py` 가 1회 추론으로 분배) | ✅ mAP 98.3% | P0 ✅ |
| **2** | **CV-Digit_v6** | jersey ROI 96×96 | 0~99 등번호 | `detection/player_detection/jersey_ocr.py` (glob) | 🔄 학습 중 | P0 |
| **3** | **CV-Team_v2** | player crop 128×256 | team_a / team_b / referee + 128d emb | `detection/player_detection/team_classifier.py` | 🔄 학습 예정 | P0 |
| **4** | **CV-Pose** (yolo11l-pose + vitpose-b) | RGB 1080p | 17 또는 133 키포인트 | `pose_estimation/backends/{yolov8,vitpose}_backend.py` | ✅ 적용 | P0 ✅ |

### Phase B — 단일 통합 모델 (코드 모듈 다수 → 학습 1개로 흡수)

| # | 모델 | 입력 | 출력 | **흡수할 모듈** | 상태 | P |
|---|---|---|---|---|---|---|
| **5** | **CV-Action** | 30f × (54d biomechanics + ball relation + pose) | 7-class: `shoot / dribble / pass / rebound / move / idle / layup` | **🗑️ motion_analysis 전체 폐기**:<br>• `motion_analysis/detection/{shot,dribble,pass,rebound,movement}_detector.py` (5)<br>• `motion_analysis/classification/{action,shot,dribble}_classifier.py` (3)<br>+ `biomechanics/phase_analysis/{shot,dribble}_phase_analyzer.py` 분류 부분 | 🔄 학습 예정 | P1 |
| **6** | **CV-Record** ⭐ <br>(기록원 대체) | 이벤트 시퀀스 + player_id + 멀티뷰 frame + scoreboard ROI | **기록원이 하는 모든 일**:<br>• 이벤트 감지 (score / rebound / assist / steal / turnover / block / jump_ball)<br>• 점유권 추적 (`possession`)<br>• 시간 기록 (event_time, quarter)<br>• 선수 귀속 (누가 한 행위)<br>• 스코어 누적 + 점수판 cross-check<br>• 기록지 row 생성 + 자동 보정 | **🔁 흡수 대상 (대규모 통합)**:<br>• `game_analysis/game_state/event_detection/{score, possession_tracker, shot_event, rebound, assist, steal, turnover, block, free_throw, jump_ball, dead_ball, fast_break, drive, screen, box_out}_detector.py` (16)<br>• `game_analysis/game_state/game_management/{clock_manager, foul_manager, record_corrector, official_format_exporter}.py` 의 기록 부분<br>• `game_analysis/output/game_record/{game_report_builder, game_sheet_generator, play_by_play, quarter_summary}.py`<br>• `~~CV-Score~~` (스코어보드 OCR) 흡수 | 🟡 대기 | P1 |
| **7** | **CV-Foul** | 이벤트 ±2s 멀티뷰 + pose | 5-class: `personal / shooting / blocking / charging / hand_check` | **🔁 ai_referee/fouls/*.py (10) 전부 흡수**:<br>blocking, charging, contact, flagrant, foul_severity, hand_check, holding, illegal_screen, reach_in, shooting_foul, technical_violation | 🟡 대기 | P1 |
| **8** | **CV-Violation** | 이벤트 ±2s 멀티뷰 + ball trajectory + pose | 7-class: `traveling / double_dribble / 3sec / 5sec / 8sec / 24sec / oob` | **🔁 ai_referee/violations/*.py (12) 전부 흡수**:<br>backcourt, carry, def_3sec, double_dribble, 8sec, 5sec, goaltending, kick_ball, oob, 3sec, traveling, 24sec | 🟡 대기 | P1 |

### Phase C — 분석/생성 (코치/스카우트 통합)

| # | 모델 | 입력 | 출력 | **흡수할 모듈** | 상태 | P |
|---|---|---|---|---|---|---|
| **10** | **CV-Coach** | 경기 상태 임베딩 + 사이드라인 영상 | 추천 액션 (교체/타임아웃/수비전환/플레이콜) | **🔁 통합 대상**:<br>• `game_analysis/output/coaching_intelligence/{endgame_strategist, realtime_advisor, substitution_optimizer}.py` (3)<br>• `feedback_system/coach/*` 일부<br>• `game_analysis/output/pre_game/{defensive_assignment_planner, game_plan_generator, game_plan_execution_tracker, offensive_priority_setter, pre_game_briefing_builder}.py` (5)<br>+ `feedback_system/{form_evaluation, comparison, report}/*` (슛폼/드리블폼 평가) | 🟡 대기 | P2 |
| **11** | **CV-Scout** | 경기 시퀀스 (선수/팀 통계) | 상대 분석 / 매치업 / 약점 / 성향 / 패턴 | **🔁 통합 대상**:<br>• `game_analysis/output/scouting/{tendency_analyzer, opponent_profiler, weakness_finder, head_to_head_analyzer, play_pattern_matcher, referee_tendency_analyzer, scouting_report_builder}.py` (7)<br>• `game_analysis/output/matchup_analysis/{contest_analyzer, matchup_evaluator, matchup_tracker}.py` (3)<br>• `feedback_system/analysis/*` 일부 | 🟡 대기 | P2 |
| **12** | **CV-Highlight** | 클립 frame + 이벤트 맥락 + 관중 환호 (오디오) | excitement_score [0,1] + 클립 priority | `game_analysis/output/highlight/{excitement_scorer, highlight_detector, clip_extractor, clip_file_extractor}.py` (4)<br>`api_server/services/highlight_clip_service.py` | 🟡 **단계적**: <br>(1) Phase 2 = LLM API (Claude/GPT) 로 시작 → 데이터 수집<br>(2) 충분히 라벨 누적 시 자체 학습 모델 교체 | P2 |

### Phase D — 통계/예측 (선택)

| # | 모델 | 입력 | 출력 | 통합 모듈 | 상태 | P |
|---|---|---|---|---|---|---|
| **13** | **CV-XFG** (Expected Field Goal) | (loc_xy, def_dist, velocity, shot_clock, shot_type) | P(made) ∈ [0,1] | `game_analysis/stats/predictive_models/shot_quality_model.py` | 🟡 대기 | P3 |
| **14** | **CV-EPV** (Expected Possession Value) | 점유 시작 상태 (5+5 위치, ball, clock) | 예상 득점 기댓값 | `game_analysis/stats/predictive_models/expected_possession_value.py` | 🟡 대기 | P3 |
| **15** | **CV-WP** (Win Probability) | 현재 점수, clock, 점유, 반칙수 | P(home_win) ∈ [0,1] | `game_analysis/stats/predictive_models/win_probability.py` | 🟡 대기 | P3 |
| **16** | **CV-Lineup** | 5인 조합 + 상대 5인 + matchup features | net_rating 예측 | `game_analysis/stats/predictive_models/lineup_projection.py` | 🟡 대기 | P3 |

### ❌ 보류 (학습 안 함, 조건 충족 시 재검토)

| # | 모델 | 결정 사유 |
|---|---|---|
| ~~CV-REID~~ | **보류 확정** — 8 카메라 voting (§6) + single-view 미지원 (§8.4) 으로 영구 불필요 |
| ~~CV-Score~~ | **CV-Record 안에 귀속** (§8.5). 별도 학습 없음 |
| ~~CV-Clock~~ | clock_manager 휴리스틱 + 외부 스코어보드 연동 시 불필요 (또는 CV-Record 흡수) |
| ~~CV-Gesture~~ | 운영자 입력 우회 |
| ~~CV-Pattern~~ | CV-Scout 안 흡수 |
| ~~CV-Commentary~~ | LLM API (Claude/GPT) 우회 |

### ❌ 폐기

| 모델 | 사유 |
|---|---|
| ~~motion_analysis 전체~~ | **CV-Action 으로 통합 흡수** (사용자 결정) |
| ~~feedback_system 독립 모델~~ | **CV-Coach + CV-Scout 에 통합** (사용자 결정) |
| ~~CV-BioML~~ | biomechanics 연산이 학습 모델보다 정확/해석성 우수 |
| ~~CV-Substitution~~ | game_management/substitution_manager 휴리스틱 + 운영자 입력 충분 |
| ~~CV-OOB~~ | bbox + 캘리브레이션 좌표 비교 충분 (CV-Violation 안 oob class 로 흡수) |
| ~~CV-Court~~ | court_detection 모듈 폐기 (4점 수동 캘리) |

---

## 2. 우선순위 / Phase 일정

### Phase 0 — 즉시 (이번 주)

```
✅ 1. CV-BBox_v9                  적용 완료
🔄 2. CV-Digit_v6                 학습 끝나면 weights/ 에 두기 → glob 자동 감지
🔄 3. CV-Team_v2                  학습 끝나면 weights/CV-Team_v2.pt
✅ 4. CV-Pose                     적용 완료 (yolo11l-pose + vitpose-b)
```

**효과:** 등번호 인식 → player_id 매핑 정확 → 기록지 선수란 채워짐.

### Phase 1 — 2-3주 (Action / Record / Foul / Violation)

```
🆕 5. CV-Action            유튜브 highlight + 자체 영상 → motion_analysis 전체 흡수 후 폐기
🆕 6. CV-Record ⭐         기록원 대체 (이벤트 16종 + 점유 + 시간 + 귀속 + 스코어 + 기록지)
                          → game_state/event_detection/* 16개 + game_management/record_corrector
                          + game_record/* + CV-Score(스코어보드 OCR) 모두 흡수
🆕 7. CV-Foul              ai_referee/fouls/* 10 종 흡수
🆕 8. CV-Violation         ai_referee/violations/* 12 종 흡수
```

**효과:** ScoreDetector FP 2건 → 0. 기록지 정확도 80% → 95%. 심판 22 detector → 모델 후처리. **휴리스틱 50+ 모듈이 4 개 모델로 통합**.

**가장 큰 도전 = CV-Record** — 16개 이벤트 감지기를 단일 모델로 통합. 데이터셋 라벨링 비용 가장 큼.

### Phase 2 — 3-4주 (Coach / Scout) + LLM 우회 (Highlight)

```
🆕 9.  CV-Coach           feedback_system + coaching_intelligence + pre_game (총 13 모듈) 흡수
🆕 10. CV-Scout           scouting + matchup_analysis (총 10 모듈) 흡수
🚀 11. CV-Highlight (LLM) Claude/GPT API 우회 (Phase 2)
                          → 사용자 클립 선택 데이터 누적 → Phase 3 자체 학습 가능
```

**효과:** "코치 보조" + "전략 보고서" 자동 생성. 사용자 manual 작업 70% 감소. Highlight 는 학습 없이 즉시 활용.

### Phase 3 — 1-3개월 (예측 통계 + Highlight 자체학습)

```
권장 순서 (의존성 + 데이터 양 기준):

1순위 🆕 12. CV-XFG          shot_quality - 단일 슛 → P(made)
                              · 자동 라벨: shot detection + outcome 매칭
                              · 다른 모델 (EPV/WP) 의 입력으로 재사용 → 가장 ROI 큼
                              · 데이터 10K 슛이면 충분
2순위 🆕 13. CV-EPV          expected possession value - 점유 시작 → 기대 득점
                              · 입력에 CV-XFG 출력 사용
3순위 🆕 14. CV-WP           win probability - 현 상황 → 승리 확률
                              · 입력에 EPV 사용
4순위 🆕 15. CV-Lineup       lineup projection - 5인 조합 → net rating
                              · 시즌 통계 충분 누적 후

🆕 16. CV-Highlight (자체)   LLM 우회 데이터 충분 누적 시 자체 학습 모델 교체
```

**효과:** xG 같은 고급 메트릭. 데이터 양 누적 (10K+ 슛, 5K+ 점유) 후 진행.

### Phase 4 — 보류 (효과 검증 후)

```
🤔 17. CV-REID                   §6 토론 결과
⏳ 18~22                          외부 데이터 / 장기
```

---

## 3. 데이터셋 / 라벨링

### 3.1 위치 (현재)

```
D:/SPOIN/training/
├── action/                  CV-Action 학습 데이터
├── datasets/                jersey_cls 등 분류 데이터
├── runs/                    PyTorch 학습 실행 결과
├── team_classification/     CV-Team 데이터 (60만 장)
├── tools/                   라벨링 스크립트
└── videos/
    ├── 1st_real_test ~ 5th_real_test_*    내부 녹화
    └── 4th_real_test_T/2026-04-16_*       8 cam 30fps 1080p
```

### 3.2 데이터 추출기 매트릭스

| Extractor | 출력 형식 | 학습 대상 |
|---|---|---|
| `detection/ball_detection/data_extraction/` | 디렉토리 (YOLO format) | CV-BBox 추가 |
| `detection/hoop_detection/data_extraction/` | 디렉토리 | CV-BBox hoop class |
| `detection/player_detection/data_extraction/` | 디렉토리 | CV-Digit / CV-Team |
| `detection/court_detection/data_extraction/` | (폐기 — 캘리 4점) | — |
| `motion_analysis/data_extraction/` | jsonl | CV-Action 입력 시퀀스 (+ pose+bbox) |
| `biomechanics/data_extraction/{event,frame,sequence}_extractor.py` | jsonl | CV-Action 보조 features |
| `game_analysis/data_extraction/` | jsonl | CV-Possession / CV-Record |
| `ai_referee/data_extraction/` | jsonl | CV-Foul / CV-Violation |
| `feedback_system/templates/_form_data/` | 폼별 라벨 데이터 | CV-Coach (form 평가 부분) |

### 3.3 자동 라벨 파이프라인 (CV-Action 우선)

```
[1] yt-dlp 로 NBA/KBL/대회 highlight 영상 다운로드
[2] CV-BBox_v9 + CV-Digit_v6 + CV-Team_v2 분석 → player track
[3] 영상 제목/thumbnail OCR + scene transition 검출 → 액션 자동 라벨
[4] motion_analysis/data_extraction + biomechanics 30f sequence 추출
[5] CV-Action 학습
```

100시간/주 데이터 구축 가능 → 7-class macro F1 ≥85% 목표.

---

## 4. 배포 / 통합 규칙

### 4.1 가중치 → 코드 자동 인식 (glob 패턴)

| 모듈 | glob | 동작 |
|---|---|---|
| `engine/orchestrator/game_orchestrator.py:413` | `CV-BBox_v*.engine\|cv\|onnx\|pt` | reverse=True (최신 우선) |
| `detection/player_detection/jersey_ocr.py:75` | `CV-Digit_v*.pt` | 동일 |
| `detection/player_detection/team_classifier.py` | `CV-Team_v*.pt` (필요 시 추가) | 동일 |
| 기타 | `CV-{Name}_v*.pt` 통일 | reverse=True |

**규칙**: 새 학습 가중치 → `weights/CV-{Name}_v{N+1}.pt` 파일 하나만 두면 코드 변경 없이 자동 사용.

### 4.2 TensorRT 자동 빌드

`game_orchestrator::_ensure_engine_built()` 가 첫 실행 시 `.pt` → `.engine` 자동 export (batch=8). GPU 별 1회, ~3-5분.

### 4.3 EXE 번들

```
모든 weights/CV-*.pt → PyInstaller datas → _internal/weights/
새 모델 → weights/ 에 두고 build.py 0.X.Y 빌드 → installer 자동 포함
EXE 사이즈 ~9.6GB 중 가중치 ~3GB
```

---

## 5. 평가 메트릭

| 모델 | 메트릭 | 목표 |
|---|---|---|
| CV-BBox_v9 | mAP@0.5 | ≥ 95% (현 98.3%) |
| CV-Digit_v6 | top-1 acc + reject rate | ≥ 90% acc, ≤ 10% reject |
| CV-Team_v2 | 3-class accuracy | ≥ 98% |
| CV-Pose | OKS@0.5 | ≥ 75% |
| CV-Action | 7-class macro F1 | ≥ 85% |
| CV-Possession | 4-class acc + transition F1 | ≥ 90% |
| CV-Record | row-level accuracy (vs 수기) | ≥ 95% |
| CV-Foul | 5-class macro F1 | ≥ 80% |
| CV-Violation | 7-class macro F1 | ≥ 80% |
| CV-Coach | 추천 채택률 (vs 운영자) | ≥ 70% |
| CV-Scout | 보고서 품질 평가 (1-5점) | ≥ 4.0 |
| CV-Highlight | NDCG@10 | ≥ 0.85 |
| CV-XFG | log-loss | ≤ 0.45 |
| CV-EPV | RMSE (점) | ≤ 0.6 |
| CV-WP | calibration ECE | ≤ 0.05 |

---

## 6. CV-REID 결정 토론

**보류 이유 — 8 카메라 멀티뷰 voting 으로 대체:**

```
한 카메라 등 가릴 확률 ≈ 0.3
8 카메라 동시에 다 가릴 확률 = 0.3^8 = 0.0066%
→ 99.99% 의 경우 최소 1 카메라 등번호 보임
→ ReID 외모 fallback 불필요
```

**조건부 학습 시점:**
- CV-Digit_v6 + CV-Team_v2 적용 후 실측 식별률 < 90%
- 또는 폰 1대 single-view 모드 추가 시 (multiview 불가)

**현재 코드:**
- `detection/player_detection/multiview_tracker.py` ← court_position voting 수행
- `detection/player_detection/reid_module.py` ← 가중치 없으면 0.35 weight 자리 0
- `detection/player_detection/player_id_manager.py` ← OCR(0.4) + ReID(0.35) + Track(0.25) 결합

---

## 7. 빌드 / 릴리즈 통합

```bash
cp /path/to/CV-Action_v1.pt c:/COURTVIEW_DESK/weights/

# 빌드 + 배포
venv/Scripts/python.exe build.py 0.X.Y
venv/Scripts/python.exe build.py 0.X.Y --zip
venv/Scripts/python.exe release.py 0.X.Y --with-installer
```

자동:
- PyInstaller 가 `weights/CV-*.pt` 모두 번들 포함
- 첫 실행 시 batch=8 .engine 자동 export
- 모든 detector glob 으로 최신 버전 자동 감지

---

## 8. 사용자 결정 사항 (2026-05-01 확정)

| # | 항목 | 결정 |
|---|---|---|
| 1 | **CV-Record 정의** | ✅ **기록원 대체** — 이벤트 감지(16종) + 점유 + 시간 기록 + 선수 귀속 + 스코어 누적 + 기록지 row 자동 생성/보정. 사실상 game_state/event_detection 16개 모듈 + game_management 기록 부분 + game_record 출력 4개 모듈을 통합 흡수. CV-Score 도 여기 귀속. |
| 2 | **CV-REID** | ✅ **보류 확정** — single-view 미지원 + 8 카메라 voting 으로 영구 불필요 |
| 3 | **CV-Highlight 우회** | ✅ **단계적**: Phase 2 LLM API → 데이터 누적 → Phase 3 자체 학습 교체 |
| 4 | **single-view (폰 1대) 모드** | ✅ **미지원** (의존성: ReID 보류 굳힘) |
| 5 | **CV-Score 별도 학습?** | ✅ **CV-Record 안에 귀속** (별도 학습 없음) |
| 6 | **Phase D 우선순위** | ✅ **CV-XFG → CV-EPV → CV-WP → CV-Lineup**:<br>• XFG 가 EPV/WP 의 입력으로 재사용 (ROI 가장 큼)<br>• EPV 는 XFG 출력 사용<br>• WP 는 EPV 사용<br>• Lineup 은 시즌 통계 누적 후 |

---

## 9. 최종 가중치 인벤토리 요약

```
✅ Phase A (P0, 적용 완료/학습 중): 4 개
   1. CV-BBox_v9        ✅ mAP 98.3%
   2. CV-Digit_v6       🔄 학습 중
   3. CV-Team_v2        🔄 예정
   4. CV-Pose           ✅ (yolo11l-pose + vitpose-b)

🔄 Phase B (P1, 2-3주): 4 개 — 휴리스틱 50+ 모듈 통합
   5. CV-Action         (motion_analysis 8 모듈 흡수 → 폐기)
   6. CV-Record ⭐      (event_detection 16 + game_management 3 + game_record 4 = 23 모듈 흡수)
   7. CV-Foul           (ai_referee/fouls 10 모듈 흡수)
   8. CV-Violation      (ai_referee/violations 12 모듈 흡수)

🔄 Phase C (P2, 3-4주): 3 개 — feedback_system + output 흡수
   9.  CV-Coach         (feedback_system + coaching_intelligence + pre_game = 13 모듈)
   10. CV-Scout         (scouting + matchup_analysis = 10 모듈)
   11. CV-Highlight     (LLM 우회 → 자체 학습 단계적 마이그레이션)

🔄 Phase D (P3, 1-3개월): 4 개 — 예측 통계 (XFG → EPV → WP → Lineup 순)
   12. CV-XFG           (shot_quality_model.py)
   13. CV-EPV           (expected_possession_value.py — XFG 입력 사용)
   14. CV-WP            (win_probability.py — EPV 입력 사용)
   15. CV-Lineup        (lineup_projection.py — 시즌 통계 누적 후)

❌ 보류/폐기:
   - CV-REID (single-view 미지원 + 8cam voting)
   - CV-Score (CV-Record 안 귀속)
   - CV-Clock (clock_manager 휴리스틱)
   - CV-Gesture, CV-Pattern, CV-Commentary, CV-BioML, CV-Substitution, CV-OOB, CV-Court

총 학습 대상 = 15 개 (단, 4번 CV-Pose 는 외부 사전학습 모델 활용)
순수 자체학습 = 14 개 (Phase A 3 + B 4 + C 3 + D 4)
```

## 10. 변경 이력

| 날짜 | 변경 |
|---|---|
| 2026-05-01 | v1 작성 (1-pass scan, 누락 4 영역) |
| 2026-05-01 | v2 작성 — 전수 스캔 + motion_analysis 폐기 + feedback_system 통합 + predictive 4종 + Coach/Scout 신설 |
| 2026-05-01 | **v3 확정** — 사용자 결정 6항목 반영: CV-Record(기록원 통합) / REID 보류 / Highlight LLM→자체 / single-view 미지원 / CV-Score 귀속 / Phase D 우선순위 |

---

## 부록 A — 모듈 → 가중치 전수 역참조

### detection/
```
ball_detection/ball_detector.py            → CV-BBox_v9 (unified)
ball_detection/ball_state.py               → 휴리스틱 (학습 모델 없음)
ball_detection/ball_tracker.py             → 휴리스틱 (Kalman + IoU)
hoop_detection/hoop_detector.py            → CV-BBox_v9 (unified)
hoop_detection/net_analyzer.py             → 휴리스틱
player_detection/player_detector.py        → CV-BBox_v9 (unified)
player_detection/jersey_ocr.py             → CV-Digit_v6 (glob)
player_detection/team_classifier.py        → CV-Team_v2 + CV-team.pt centroid
player_detection/reid_module.py            → CV-REID (보류)
player_detection/multiview_tracker.py      → 학습 없음 (geometry voting)
player_detection/player_id_manager.py      → 결합 (OCR + ReID + Track)
player_detection/team_aware_tracker.py     → ByteTrack 확장
court_detection/                           → ❌ 폐기 (4점 수동 캘리)
```

### pose_estimation/
```
backends/yolov8_backend.py                 → yolo11l-pose.pt (CV-Pose 일부)
backends/vitpose_backend.py                → vitpose-b-wholebody.onnx (CV-Pose 일부)
backends/tensorrt_engine.py                → 공통 런타임
```

### motion_analysis/  (🗑️ CV-Action 흡수 후 폐기)
```
detection/{shot,dribble,pass,rebound,movement}_detector.py     → CV-Action 흡수
classification/{action,shot,dribble}_classifier.py             → CV-Action 흡수
data_extraction/                                               → CV-Action 학습 데이터 추출 (폐기 전 유지)
```

### biomechanics/
```
kinematics/{joint_angle,velocity,acceleration,trajectory,motion_pattern,body_orientation}.py
                                           → 연산 (학습 모델 없음, CV-Pose 결과 사용)
phase_analysis/{shot,dribble}_phase_analyzer.py
                                           → 휴리스틱 (분류 부분만 CV-Action 통합 후 단순화)
data_extraction/{event,frame,sequence}_extractor.py
                                           → CV-Action 입력 features 추출
dynamics/, anthropometry/, standards/      → 연산 / 상수 (학습 없음)
```

### game_analysis/game_state/event_detection/  (16개) — 🔁 CV-Record 흡수
```
score_detector.py                  → CV-Record (이벤트 감지)
possession_tracker.py              → CV-Record (점유 추적)
shot_event_detector.py             → CV-Record + CV-Action 보조
rebound_detector.py                → CV-Record (이벤트) + CV-Action (rebound class)
foul_detector.py                   → CV-Record (이벤트 트리거) + CV-Foul (분류)
free_throw_detector.py             → CV-Record (이벤트) + CV-Foul (트리거)
screen_detector.py                 → CV-Record (이벤트) + CV-Action (screen class)
fast_break_detector.py             → CV-Record (transition 이벤트)
drive_detector.py                  → CV-Record + CV-Action (drive class)
assist_detector.py                 → CV-Record (귀속 매칭)
block_detector.py                  → CV-Record + CV-Foul/Action
steal_detector.py                  → CV-Record (점유 전이)
turnover_detector.py               → CV-Record (점유 전이)
box_out_detector.py                → CV-Record + CV-Foul
jump_ball_detector.py              → CV-Record (점유 시작)
dead_ball_detector.py              → CV-Record (게임 상태)
```

### game_analysis/game_state/game_management/
```
clock_manager.py                   → CV-Record 흡수 (시간 기록)
foul_manager.py                    → CV-Record (반칙 누적) + CV-Foul (분류)
substitution_manager.py            → 휴리스틱 + 운영자 입력 (학습 없음)
timeout_manager.py                 → 휴리스틱 (학습 없음)
record_corrector.py                → CV-Record 흡수 (row 보정)
official_format_exporter.py        → CV-Record 출력 단계 (포맷 변환만)
```

### game_analysis/output/  (Phase C 통합)
```
coaching_intelligence/{endgame_strategist, realtime_advisor, substitution_optimizer}.py
                                   → 🔁 CV-Coach 흡수
pre_game/{game_plan_generator, defensive_assignment_planner, offensive_priority_setter,
          game_plan_execution_tracker, pre_game_briefing_builder}.py
                                   → 🔁 CV-Coach 흡수
scouting/{tendency_analyzer, opponent_profiler, weakness_finder, head_to_head_analyzer,
          play_pattern_matcher, referee_tendency_analyzer, scouting_report_builder}.py
                                   → 🔁 CV-Scout 흡수
matchup_analysis/{contest_analyzer, matchup_evaluator, matchup_tracker}.py
                                   → 🔁 CV-Scout 흡수
highlight/{excitement_scorer, highlight_detector, clip_extractor, clip_file_extractor}.py
                                   → CV-Highlight 통합
game_record/{game_report_builder, game_sheet_generator, play_by_play, quarter_summary}.py
                                   → CV-Record 후처리 (또는 LLM API)
film_session/{film_session_builder, player_clip_package, teaching_point_generator}.py
                                   → CV-Coach 일부 (티칭 포인트)
video_editing/{annotation_overlay, clip_manager, export_manager, multi_angle_sync}.py
                                   → 비디오 편집 (학습 없음)
shot_location/{shot_zone_mapper, shot_heatmap, efficiency_by_zone}.py
                                   → 통계 집계 (학습 없음, CV-XFG 입력 가능)
```

### game_analysis/stats/
```
predictive_models/shot_quality_model.py        → CV-XFG
predictive_models/expected_possession_value.py → CV-EPV
predictive_models/win_probability.py           → CV-WP
predictive_models/lineup_projection.py         → CV-Lineup
statistics/                                    → 단순 집계 (학습 없음)
```

### feedback_system/  (🗑️ 독립 모델 없음, CV-Coach + CV-Scout 흡수)
```
analysis/                          → CV-Scout 흡수
coach/                             → CV-Coach 흡수
comparison/                        → CV-Coach 흡수 (선수 비교)
form_evaluation/                   → CV-Coach 흡수 (슛폼/드리블폼 평가)
report/                            → CV-Coach + CV-Scout 출력 단계
templates/                         → 보고서 템플릿 (학습 없음)
```

### ai_referee/
```
fouls/*.py (10)                    → 🔁 CV-Foul 5-class head 흡수
violations/*.py (12)               → 🔁 CV-Violation 7-class head 흡수
decisions/*                        → 결정 종합 (학습 없음, CV-Foul/Violation 결과 합산)
rules/{kbl, fiba, nba}_rules.yaml  → 규칙 정의 (학습 없음)
data_extraction/                   → CV-Foul/Violation 학습 데이터
```

### engine/  (오케스트레이션, 학습 모델 없음)
```
orchestrator/game_orchestrator.py  → 모든 모듈 통합
pipeline/fusion/detection_fusion.py → CV-BBox 1회 추론 → ball/player/hoop 분배
pipeline/fusion/pose_fusion.py     → CV-Pose 결과 통합
pipeline/fusion/tracking_fusion.py → multiview tracking 결합
pipeline/{frame, event, possession, period, postgame}_pipeline.py
                                   → 단계별 cadence (학습 없음)
referee/referee_orchestrator.py    → CV-Foul + CV-Violation 호출 통합
referee/multi_angle_pipeline.py    → 멀티뷰 referee 결정
workers/analysis_worker.py         → 백그라운드 분석 큐
workers/export_worker.py           → 출력물 export 큐
gpu/{gpu_manager, cuda_stream_manager, tensorrt_pool}.py
                                   → GPU 자원 관리 (학습 없음)
analysis_buffer.py, game_state.py, config.py
                                   → 코어 (학습 없음)
io/{frame_ingestion, recording, video_decoder}.py
                                   → 입출력 (학습 없음)
```

### infrastructure/, shared/, core_foundation/, utils/, scripts/
```
모두 인프라/공통 코드 — 학습 모델 없음
```
