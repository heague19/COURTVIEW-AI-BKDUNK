# CV Weights Manifest v2.0 — 학습 가중치 전체 설계

**버전**: 2.0.0
**작성일**: 2026-04-20
**작성자**: SPOIN_COURTVIEW
**변경 사유**: v1.0(14개) 대비 기록원·심판 커버리지 부족 → 24개로 확장, 3층 아키텍처 명시, 보조 우선 전략 반영
**포지셔닝**: **보조 도구 우선 (95% 커버) → 점진적 대체** (완전 대체는 장기 목표)

---

## 1. 설계 원칙

| 원칙 | 내용 |
|---|---|
| **보조 우선** | 인간 인력(기록원·분석원·코치·심판) **대체 아닌 증강**. 법적 책임·도입 저항·피드백 루프 관점에서 최적 |
| **3층 아키텍처** | Perception(ML) → Computation(코드) → Analysis(ML) → Output(코드) |
| **bioml_rt 제외** | 연산 기반 biomechanics 모듈이 학습 모델보다 정확도·해석성 우수 → **가중치화 금지**, 54d feature는 CV-action 입력으로 공급 |
| **백본 공유** | 공통 맥락이 필요한 태스크(심판 F/V)는 공유 백본 + 헤드 분리로 파라미터 ~40% 절감 |
| **단일 태스크 = 단일 가중치** | 역할(recorder/coach/scout) 통합 금지 — 손실함수·입력·학습 데이터 이질적 |
| **데이터 재활용 극대화** | 60만장 team 데이터 → pretrained encoder로 CV-reid·CV-action 전이학습 |
| **self-supervised 우선** | xFG·value·tendency는 아웃컴 기반 자동 레이블 |
| **티어 게이팅** | 단일 코드베이스, 라이선스 매니페스트로 번들 활성화 |

---

## 2. 3층 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  [D] OUTPUT 레이어 — 코드 유지                          │
│  game_record / video_editing / report_templates         │
│  feedback_system / api_server / film_session 포맷팅     │
└─────────────────────────────────────────────────────────┘
                          ↑ DTO·텍스트
┌─────────────────────────────────────────────────────────┐
│  [C] ★ ANALYSIS 레이어 — 학습 가중치 (13개)             │
│  event·relation·pattern·tendency·weakness·xfg·matchup   │
│  highlight·commentary·advisor·playcall·timeout·referee  │
└─────────────────────────────────────────────────────────┘
                          ↑ 이벤트·지표
┌─────────────────────────────────────────────────────────┐
│  [B] COMPUTATION 레이어 — 코드 유지                     │
│  biomechanics(54d) / stats 수식(FG%·PPP·PER·4Factors)   │
│  possession 상태기계 / data_extraction ETL              │
│  core_foundation / shared                               │
└─────────────────────────────────────────────────────────┘
                          ↑ 검출 결과
┌─────────────────────────────────────────────────────────┐
│  [A] ★ PERCEPTION 레이어 — 학습 가중치 (11개)           │
│  bbox·digit·team·action·reid·score·clock                │
│  substitution·gesture·oob·possession                    │
└─────────────────────────────────────────────────────────┘
                          ↑
                      [영상 입력]
```

---

## 3. 보유 데이터셋 현황

| 데이터셋 | 규모 | 업계 평균 대비 | 학습 상태 |
|---|---|---|---|
| `bbox_v8_all` (ball/player/hoop/backboard) | **250,000장** | ×5~25 | ✅ 학습 완료 |
| `digit_v5_all` (0~9 등번호) | **600,000장** | ×6~30 | ✅ 학습 완료 |
| `team_classification/data` (team_a/b/referee) | **600,000장** | ×20~60 | ✅ 학습 완료 |
| `action_labeled` + `action_scenes` | 대량 (실측 필요) | — | ✅ 학습 완료 (7-class) |
| `datasets/referee/fouls+violations` | 보유 | — | 🟡 학습 스크립트 미확인 |
| `datasets/score/clips+trajectories` | 보유 | — | 🟡 신규 |
| `videos/KBL+PBA+1st~5th_real_test` | 다량 | — | 원천 소스 |

→ **Perception 레이어 가중치 품질 상위권 보장**. Pretrained encoder 전이학습 대상.

---

## 4. [A] Perception 레이어 — 11개 가중치

| # | 파일명 | 아키텍처 | 입력 | 출력 | 데이터 원천 | 상태 |
|---|---|---|---|---|---|---|
| A1 | `CV-bbox.engine` | YOLOv8 | RGB 프레임 | ball / player / hoop / backboard bbox | `bbox_v8_all` (250K) | ✅ |
| A2 | `CV-digit.engine` | YOLOv8 + CRNN | 선수 등번호 크롭 | 0~9 등번호 | `digit_v5_all` (600K) | ✅ |
| A3 | `CV-team.engine` | ResNet18 → 128d | 선수 크롭 | team_a / team_b / referee 임베딩 | `team_classification` (600K) | ✅ |
| A4 | `CV-action.engine` | BiLSTM/Transformer (59d×30f) | BioML 시퀀스 + 공 관계 | 7-class: shooting / dribbling / passing / rebounding / movement / idle / layup | `action_labeled + action_scenes` | ✅ |
| A5 | **`CV-reid.engine`** | OSNet / FastReID | 선수 크롭 시퀀스 | 128~256d ID 임베딩 | `1st~5th_real_test` 멀티뷰 + CV-team 백본 전이 | 🟡 신규 |
| A6 | **`CV-score.engine`** | CRNN + 궤적 보정 | 스코어보드 ROI + 시계열 | (home_score, away_score) | `datasets/score/clips+trajectories` | 🟡 신규 |
| A7 | **`CV-clock.engine`** | CRNN | 클럭 ROI | (game_clock_sec, shot_clock_sec, quarter) | `datasets/score` 재활용 (클럭 영역) | 🟡 신규 |
| A8 | **`CV-substitution.engine`** | CV-reid + zone classifier | 선수 위치 시퀀스 | 교체 이벤트 (in_player_id, out_player_id) | 기존 영상 벤치/코트 전환 레이블 | 🟡 신규 |
| A9 | **`CV-gesture.engine`** | Pose(vitpose) + Temporal CNN | 심판 크롭 시퀀스 | 심판 수신호 (traveling/pushing/blocking/...) | `datasets/referee` + 심판 크롭 + 제스처 레이블 | 🟡 신규 |
| A10 | **`CV-oob.engine`** | Ball trajectory + line detection | 공 궤적 + 코트 캘리브레이션 | OOB 위치 (sideline/baseline, coord) | bbox + 캘리브레이션 | 🟡 신규 |
| A11 | **`CV-possession.engine`** | Temporal CNN | ball + 10인 player bbox 시퀀스 | 4-class: team_a / team_b / loose / dead | bbox + action 조합 자동 레이블 | 🟡 신규 |

---

## 5. [C] Analysis 레이어 — 13개 가중치

| # | 파일명 | 아키텍처 | 대체 역할 | 입력 | 출력 | 상태 |
|---|---|---|---|---|---|---|
| C1 | **`CV-event.engine`** | Graph + Temporal | 기록원 | 이벤트 시점 ±3s | assist / rebound / steal 귀속 ID | 🟡 |
| C2 | **`CV-relation.engine`** | Graph Transformer | 분석원·심판 | 2~3인 페어 시퀀스(30f) | blocking / stealing / screening / boxing_out / pick_and_roll | 🟡 |
| C3 | **`CV-pattern.engine`** | Seq2One Transformer | 분석원 | 점유 단위 10인 궤적 | 14-class set-play (horn/flex/motion/…/ato_set) | 🟡 |
| C4 | **`CV-tendency.engine`** | Contrastive encoder | 분석원 | 선수/팀 이벤트 시퀀스 | 128d 성향 임베딩 | 🟡 self-supervised |
| C5 | **`CV-weakness.engine`** | Tendency + MLP | 분석원 | 상대팀 성향 임베딩 | 약점 카테고리 + 신뢰도 | 🟡 |
| C6 | **`CV-xfg.engine`** | MLP/GBDT | 코치·분석원 | (loc_xy, def_dist, velocity, shot_clock, shot_type) | P(made) ∈ [0,1] | 🟡 self-supervised |
| C7 | **`CV-matchup.engine`** | MLP | 코치·분석원 | 수비자·공격자 페어 스탯 | 매치업 등급 [0,100] | 🟡 |
| C8 | **`CV-highlight.engine`** | Temporal CNN | 기록원·코치 | 클립 프레임 + 이벤트 맥락 | excitement_score ∈ [0,1] | 🟡 |
| C9 | **`CV-commentary.engine`** | LLM fine-tune (Ko) | 기록원 | 이벤트 시퀀스 | 한국어 play-by-play 텍스트 | 🟡 장기 |
| C10 | **`CV-advisor.engine`** | Transformer policy | 코치 | 현재 경기 상황 임베딩 | 추천 액션 (교체/타임아웃/수비전환) | 🟡 P5 장기 |
| C11 | **`CV-playcall.engine`** | Pose + Temporal CNN | 코치 | 감독 사이드라인 크롭 시퀀스 | 플레이 콜 분류 | 🟡 |
| C12 | **`CV-timeout.engine`** | Gesture CNN | 기록원·코치 | 사이드라인 크롭 | T-sign 감지 (True/False) | 🟡 |
| C13 | **`CV-referee_*`** (backbone+F/V heads) | Video Transformer + 2 MLP heads | 심판 | 이벤트 시점 ±2s 멀티뷰 | 파울 유형(5) / 바이올레이션 유형(7) | 🟡 |

---

## 6. [B] + [D] 코드로 유지되는 모듈

| 레이어 | 디렉토리 | 유지 사유 |
|---|---|---|
| [B] Base | `core_foundation/` | 인프라 (config·registry·monitoring·security·resilience) |
| [B] Base | `shared/` | 상수·DTO·Enum — SSOT |
| [B] Computation | `biomechanics/` | **연산 기반이 학습보다 우수** (54d feature 산출) |
| [B] Computation | `game_analysis/stats/` (수식부) | FG%·PPP·eFG%·TS%·PER·Four Factors — 결정론적 공식 |
| [B] Computation | `game_analysis/game_state/possession/` (상태기계부) | 전이 규칙 명확 |
| [B] ETL | `game_analysis/data_extraction/` | 프레임·이벤트 → DTO 변환 |
| [D] Output | `game_analysis/output/game_record/` | play-by-play 포맷팅 (생성은 CV-commentary) |
| [D] Output | `game_analysis/output/video_editing/` | 편집·export 기계 동작 |
| [D] Output | `game_analysis/output/film_session/` (포맷팅부) | 클립 컴파일 |
| [D] Output | `feedback_system/` | 피드백 전달·채널 |
| [D] Output | `api_server/` | HTTP/WebSocket 서버 |
| [D] Output | `engine/` | 런타임 엔진 |

---

## 7. 번들 구성 (5개 번들)

### 7.1 cv-core/ — 전 티어 공통 (11개)
```
CV-bbox ✅ / CV-digit ✅ / CV-team ✅ / CV-action ✅
CV-reid / CV-score / CV-clock / CV-substitution
CV-gesture / CV-oob / CV-possession
```

### 7.2 cv-recorder/ — 기록원 번들 (4개)
```
CV-event / CV-commentary / CV-highlight / CV-timeout
```

### 7.3 cv-scout/ — 전력분석원 번들 (6개)
```
CV-relation / CV-pattern / CV-tendency / CV-weakness
CV-xfg / CV-matchup
```

### 7.4 cv-coach/ — 코치 번들 (4개)
```
CV-advisor / CV-playcall / CV-xfg(공유) / CV-highlight(공유)
```

### 7.5 cv-referee/ — 심판 번들 (3개 파일 = 1 backbone + 2 heads)
```
CV-referee_backbone.engine
  ├── head_foul (파울 5종)
  └── head_violation (바이올레이션 7종)
+ cv-core 에서 CV-gesture·CV-oob·CV-possession 활용
```

---

## 8. 티어 매핑

| 티어 | 포함 번들 | 가중치 수 | 대상 고객 |
|---|---|---|---|
| **Basic** | cv-core | 11 | 중·고등학교 (녹화·기본 통계) |
| **Scorer** | cv-core + cv-recorder | 15 | 기록원 보조 전용 |
| **Pro** | cv-core + cv-scout | 17 | 대학·실업팀 (전력분석원 보조) |
| **Elite** | cv-core + cv-scout + cv-coach | 19 | 프로팀 (코치 보조) |
| **Referee** | cv-core + cv-referee | 14 | 심판 교육·판정 지원 |
| **All-in-One** | 전체 | 24 | 프로팀·연맹·방송사 |

---

## 9. 역할 커버리지 (95% 이상 목표)

| 역할 | 번들 | 커버율 | 근거 |
|---|---|---|---|
| **기록원** | Scorer | **98%** | 기록 자동화 + play-by-play 생성. 최종 검토만 인간 |
| **전력분석원** | Pro | **98%** | 성향·패턴·매치업 자동. 리포트 스토리텔링만 인간 |
| **심판** | Referee | **95%** | 판정 보조. 최종 권위는 인간 심판 |
| **코치** | Elite | **85%** | 전술 분석 완전. 실시간 RL 의사결정은 장기 |

> **95% 커버**는 "보조로 충분" 기준. 100%는 법적·도메인 제약으로 비현실적이며, 그 선을 지키는 것이 오히려 도입 전략상 우수.

---

## 10. game_analysis/ 파일 대체 매핑

### 10.1 cv-core (Perception) 대체

| 가중치 | 대체 파일 |
|---|---|
| CV-action | `event_detection/{shot,pass,dribble,rebound,movement,layup}_detector.py` (6) |
| CV-score | `game_state/correction/score_detector.py` (1) |
| CV-clock | `game_state/correction/clock_sync.py` 등 (1~2) |
| CV-reid + CV-team + CV-digit | `context/lineup_tracker.py` 선수 식별부 |
| CV-possession | `game_state/possession/{possession_tracker, possession_change_detector}.py` (2) |
| CV-substitution | `context/lineup_tracker.py` 교체 감지부 |

### 10.2 cv-recorder (Analysis) 대체

| 가중치 | 대체 파일 |
|---|---|
| CV-event | `event_detection/{assist, steal}_detector.py` + `stats/*` 의 귀속 로직 (2~4) |
| CV-commentary | `output/game_record/play_by_play.py` 생성부 (1) |
| CV-highlight | `output/highlight/{excitement_scorer, highlight_detector}.py` (2) |
| CV-timeout | `game_state/event_detection/timeout_detector.py` (1) |

### 10.3 cv-scout (Analysis) 대체

| 가중치 | 대체 파일 |
|---|---|
| CV-relation | `analysis/team/tactical_analysis/{screen_analyzer, fast_break_analyzer}.py` + `event_detection/{block, steal, screen}_detector.py` (5) |
| CV-pattern | `analysis/team/tactical_analysis/{set_play_recognizer, possession_analyzer}.py` (2) |
| CV-tendency | `analysis/player/tendency/*.py` + `output/scouting/tendency_analyzer.py` (4) |
| CV-weakness | `output/scouting/{weakness_finder, play_pattern_matcher}.py` (2) |
| CV-xfg | `output/shot_location/efficiency_by_zone.py` + `output/matchup_analysis/contest_analyzer.py` (2) |
| CV-matchup | `output/matchup_analysis/matchup_evaluator.py` (1) |

### 10.4 cv-coach (Analysis) 대체

| 가중치 | 대체 파일 |
|---|---|
| CV-advisor | `output/coaching_intelligence/{realtime_advisor, substitution_optimizer, endgame_strategist}.py` (3) |
| CV-playcall | `output/pre_game/execution_tracker.py` 콜 감지부 (1) |

### 10.5 cv-referee (Analysis) 대체

| 가중치 | 대체 파일 |
|---|---|
| CV-referee_F/V | `ai_referee/` 47파일 중 판정 로직 (Phase 11 감사 후 확정) |

**총 제거 가능 파일 (game_analysis 기준)**: 직접 ~30 + 간접 ~20 = **50+ 파일**

---

## 11. 개발 로드맵

| Phase | 내용 | 기간 | 누적 가중치 수 |
|---|---|---|---|
| **P0** ✅ | 4개 보유 (bbox/digit/team/action) | — | 4 |
| **P1** | cv-core 완성 — score / clock / reid / possession / substitution 학습 | **2-4주** | 9 |
| **P2** | cv-core 완성 — gesture / oob + cv-recorder 착수 (event / timeout / highlight) | 4-6주 | 14 |
| **P3** | cv-scout — tendency / pattern / relation / weakness / xfg / matchup | 8-12주 | 20 |
| **P4** | cv-referee — backbone + F/V + commentary 착수 | 6-10주 | 23 |
| **P5** | cv-coach — advisor(RL) + playcall. commentary 고도화 | **3-6개월+** | 24 |

---

## 12. 학습 전략

### 12.1 Pretrained Encoder 전이학습
- `CV-team` ResNet18 백본 (600K 학습) → `CV-reid` 초기화
- `CV-action` BiLSTM 백본 → `CV-relation` / `CV-pattern` 시퀀스 인코더 초기화
- 효과: 신규 가중치 학습 데이터 요구량 **30~50% 절감**

### 12.2 Self-Supervised (레이블 불필요)
- `CV-xfg`: 슛 시도 bbox + 결과만으로 회귀
- `CV-value`: 박스스코어 + 승패로 회귀
- `CV-tendency`: 이벤트 시퀀스 contrastive (같은 선수 positive)

### 12.3 Active Learning (라벨링 효율화)
- 모델 불확실성 기반 샘플 선정 → 사용자 라벨링 노동 최소화
- 특히 `CV-pattern` (14 set-play) — 수동 어노테이션 부담 큰 영역

### 12.4 Outcome-Based 자동 레이블
- assist 귀속: "패스 후 4초 이내 득점" 규칙으로 초기 레이블 → 모델 → 인간 검수
- possession: 볼 터치 + 소유 지속 시간 규칙으로 초기 레이블

---

## 13. 가중치 파일 포맷 및 배포

### 13.1 파일 포맷
- **개발**: `.pt` (PyTorch 체크포인트)
- **배포**: `.engine` (TensorRT FP16, 렌탈 노트북 RTX 4070/4080 타깃)
- **검증용**: `.onnx` (A/B 테스트, 디바이스 호환성)

### 13.2 번들 디렉토리 구조
```
cv-core.bundle/
├── manifest.json
├── CV-bbox.engine
├── CV-digit.engine
├── CV-team.engine
├── CV-action.engine
├── CV-reid.engine
├── CV-score.engine
├── CV-clock.engine
├── CV-substitution.engine
├── CV-gesture.engine
├── CV-oob.engine
└── CV-possession.engine

cv-recorder.bundle/   { 4개 }
cv-scout.bundle/      { 6개 }
cv-coach.bundle/      { 4개, xfg·highlight 공유 링크 }
cv-referee.bundle/    { 1 backbone + 2 heads + gesture/oob/possession 공유 링크 }
```

### 13.3 manifest.json 스키마
```json
{
  "bundle": "cv-core",
  "version": "1.0.0",
  "weights": [
    {
      "name": "CV-action",
      "file": "CV-action.engine",
      "sha256": "...",
      "arch": "bilstm_59d_30f",
      "input": {
        "features": 59,
        "sequence": 30,
        "dtype": "fp16"
      },
      "classes": ["shooting", "dribbling", "passing", "rebounding", "movement", "idle", "layup"],
      "depends_on": ["biomechanics_module", "CV-bbox"]
    }
  ],
  "license_tier": "basic"
}
```

### 13.4 로딩 게이팅
`core_foundation/security/license_manager` 에서 티어 검증 후 번들 로드:
```python
tier = license.tier
load_bundle("cv-core")  # 항상
if tier >= Tier.SCORER:   load_bundle("cv-recorder")
if tier >= Tier.PRO:      load_bundle("cv-scout")
if tier >= Tier.ELITE:    load_bundle("cv-coach")
if tier == Tier.REFEREE:  load_bundle("cv-referee")
```

---

## 14. 역할 분담

| 담당 | 내용 |
|---|---|
| **사용자** | 라벨링, 전략 결정, 도메인 검증, 현장 피드백, 우선순위 결정 |
| **AI 어시스턴트** | 아키텍처 설계, 학습 스크립트 템플릿, 데이터 스키마, 통합 코드, 감사, 문서화, 튜닝 지원 |

### 14.1 라벨링 스키마 원칙
1. **Active Learning 먼저** — 모델 불확실성 기반 우선 샘플만 라벨
2. **단일 라벨러 검증 가능** — 복수 라벨러 일치도 측정 불필요한 명료한 정의
3. **Outcome-Based 자동 레이블 활용** — xFG·possession은 사용자 라벨 최소
4. **증분 추가** — 초기 모델 → 오답 수집 → 타깃 라벨링

---

## 15. 유지 관리 정책

### 15.1 버전 관리
- `major.minor.patch` — 입출력 시그니처 변경=major, 정확도 개선=minor, 재학습=patch

### 15.2 검증 지표
| 태스크 | 지표 |
|---|---|
| Detection | mAP50 / mAP50-95 |
| Classification | Top-1 / Macro-F1 / Confusion Matrix |
| OCR | CER (Character Error Rate) |
| Attribution | Precision@K / 인간 평가자 일치율 |
| Regression | MAE / R² |
| Generation | BLEU / 인간 평가 (LGTM %) |

### 15.3 A/B 배포
- `manifest.json` 내 `stable` / `canary` 채널 병행
- canary 10% 롤아웃 → 지표 악화 시 즉시 롤백

### 15.4 롤백
- 번들 단위 이전 버전 즉시 교체 (`previous_stable` 필드 유지)

---

## 16. 부록 A. v1.0 → v2.0 변경 요약

| 항목 | v1.0 | v2.0 |
|---|---|---|
| 가중치 수 | 14 | **24** |
| 번들 수 | 4 | **5** (cv-recorder 신설) |
| 3층 아키텍처 | 미명시 | **명시** |
| 데이터셋 규모 반영 | — | **bbox 25만 / digit·team 60만 명시** |
| 포지셔닝 | 대체 | **보조 우선 → 점진적 대체** |
| 역할 커버율 | 70~80% | **95%+** (advisor 제외) |
| 티어 | 4개 | **6개** (Scorer 신설) |
| 신규 가중치 | 10 | **20** (clock/substitution/gesture/oob/possession/weakness/matchup/commentary/timeout/playcall 추가) |
| 학습 전략 | 단편 | **Pretrained / Self-Supervised / Active Learning / Outcome-Based 4종 명시** |

---

## 17. 다음 작업

1. ~~v2.0 작성 완료~~ ✅ (2026-04-20)
2. **P1 착수** — 우선순위:
   - `CV-score` (데이터 준비됨)
   - `CV-clock` (score ROI 재활용)
   - `CV-possession` (bbox + action 자동 레이블)
3. **Phase 11 `ai_referee/` 감사** — CV-referee_F/V 데이터 스키마 확정
4. **학습 스크립트 템플릿 표준화** — `train_action.py` 스타일 통일

---

**END OF MANIFEST v2.0**
