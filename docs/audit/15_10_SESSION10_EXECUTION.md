# Phase 15 세션 10 — H4 Facade 5 engine 연동 구현

**실행일**: 2026-04-20
**범위**: Tier 2 High H4 (5개 Facade의 engine 데이터 연동, Phase 15 마지막 항목)
**결과**: **5 Facade 중 4개 신규 연동 + GameOrchestrator public property 2개 추가**

---

## 1. 배경

### 이전 상태

`api_server/services/facades/` 5개 Facade 클래스:
- `GameStatsFacade` — placeholder (모두 빈 응답)
- `HighlightFacade` — **이미 연동 완료** (세션 4에서 완성)
- `RefereeFacade` — placeholder
- `ReportFacade` — placeholder
- `TacticalFacade` — placeholder

### 목표

각 Facade가 `GameOrchestrator`의 실제 engine 데이터를 추출하여 Response 스키마로 변환하도록 구현.

---

## 2. 실행 내역

### ✅ GameOrchestrator public property 2개 추가

**파일**: [engine/orchestrator/game_orchestrator.py](engine/orchestrator/game_orchestrator.py)

```python
@property
def event_pipeline(self) -> EventPipeline | None:
    """EVENT cadence 파이프라인 (facade 통계 조회용, Phase 15 H4)."""
    return self._event_pipeline

@property
def possession_pipeline(self) -> PossessionPipeline | None:
    """POSSESSION cadence 파이프라인 (facade 하이라이트/전술 조회용, Phase 15 H4)."""
    return self._possession_pipeline
```

### ✅ GameStatsFacade 연동

**파일**: [api_server/services/facades/game_stats_facade.py](api_server/services/facades/game_stats_facade.py)

**데이터 소스**: `orchestrator.event_pipeline._event_detectors.basic_stats` (`BasicStatsCalculator`)

**구현**:
- `get_box_score()`: 팀별 선수 자동 분류 (첫 2팀을 HOME/AWAY로 매핑) + `get_team_totals()` + `get_all_player_stats()`
- `get_player_stats(player_id=None)`: player_id 필터 지원
- `get_team_stats(team_id=None)`: team_id 필터 지원

**PlayerStats → PlayerStatsResponse 변환 헬퍼** + **get_team_totals → TeamStatsResponse 변환 헬퍼** 내장.

### ✅ RefereeFacade 연동

**파일**: [api_server/services/facades/referee_facade.py](api_server/services/facades/referee_facade.py)

**데이터 소스**: `orchestrator.referee._history` (`list[RefereeResult]`) → 각 `RefereeResult.final_decisions` (`list[FinalDecision]`)

**구현**:
- `get_decisions(limit=20)`: 최근 판정 최신순 반환, 총 위반/파울 카운트 포함
- `get_decision_by_id(decision_id)`: UUID 문자열로 단건 조회

**FinalDecision → RefereeDecisionResponse 변환 헬퍼** 내장 (call_type / violation_type / foul_type enum 처리).

### ✅ TacticalFacade 연동

**파일**: [api_server/services/facades/tactical_facade.py](api_server/services/facades/tactical_facade.py)

**데이터 소스**: `orchestrator.event_pipeline._event_stats` (`EventStatsSet`) — four_factors + possession_stats + advanced_stats

**구현**:
- `get_summary()`: Four Factors 지배 요인 + possession pace + advanced stats offensive/defensive rating 통합
- 홈 팀 ID는 basic_stats 첫 등장 팀으로 자동 추정

### ✅ ReportFacade 연동

**파일**: [api_server/services/facades/report_facade.py](api_server/services/facades/report_facade.py)

**구현**:
- `get_game_report()`: 팀별 요약 (점수/리바운드/어시스트/턴오버/FG%) + 심판 판정 카운트
- `get_scouting_report()`: 팀별 Four Factors (`to_dict()`) + possession 요약

---

## 3. 런타임 검증

### None-safe 검증 (orchestrator=None 시)

```
GameStatsFacade None-safe OK
RefereeFacade None-safe OK
TacticalFacade None-safe OK
ReportFacade None-safe OK
GameOrchestrator public properties OK (event_pipeline, possession_pipeline)
```

### 실 데이터 흐름 검증 (mock orchestrator + 실제 BasicStatsCalculator)

```
# GameStats
Home: id=HOME, pts=3, ast=1
Away: id=AWAY, pts=2, reb=1
Player 20 filter OK: points=2
HOME team stats OK: points=3

# Referee
Decisions: 2, violations=2, fouls=0
  frame=250, call=shot_clock_violation, conf=0.85, review=True
  frame=100, call=traveling, conf=0.92, review=False
Single lookup OK: traveling

# Tactical
OR: 112.5, DR: 104.3
Pace: 95.0
Top factor: efg, composite: 0.7

# Report
Report teams: 2
Report referee: {'total_evaluations': 5, 'total_violations': 2, 'total_fouls': 1}
```

### 기존 테스트 통과

| 테스트 그룹 | 통과 |
|---|---|
| `tests/motion_analysis` (세션 9) | 235 |
| `tests/feedback_system/templates` (세션 8) | 16 |
| `tests/engine` (facades 영향권) | 364/368 (pre-existing 4건 실패는 H4와 무관) |
| **H4 합계** | **615+ 통과** |

**pre-existing 실패 4건** (git stash 확인):
- `test_cadence_scheduler::test_live_event_no_trigger`
- `test_config::test_model_paths`, `test_all_count`
- `test_gpu::test_member_count`

모두 세션 10 이전부터 실패 상태. 모델 ID 카운트 stale 등 H4와 관련 없음.

---

## 4. 영향 범위

| 파일 | 변경 |
|---|---|
| `engine/orchestrator/game_orchestrator.py` | public property 2개 추가 |
| `api_server/services/facades/game_stats_facade.py` | 재작성 (62줄 → 176줄) |
| `api_server/services/facades/referee_facade.py` | 재작성 (48줄 → 124줄) |
| `api_server/services/facades/tactical_facade.py` | 재작성 (35줄 → 100줄) |
| `api_server/services/facades/report_facade.py` | 재작성 (40줄 → 131줄) |
| **합계** | **5파일** |

### Breaking change 분석

**없음**:
- Facade public API 시그니처 동일 (`get_box_score(orchestrator)` 등)
- Response 스키마 동일 (`BoxScoreResponse`, `RefereeListResponse` 등)
- orchestrator=None 시 빈 응답 유지 (startup 전 안전성)
- 모든 필드 접근이 `getattr(..., None)` 방어 로직 — 파이프라인 부분 초기화 상태에도 안전

---

## 5. 연동 데이터 흐름도

```
┌─ GameOrchestrator (public properties) ─┐
│  • event_pipeline                       │
│  • possession_pipeline                  │
│  • referee                              │
└─────────────┬───────────────────────────┘
              │
       ┌──────┴──────────┬───────────────┬──────────────┐
       ▼                 ▼               ▼              ▼
 GameStatsFacade   RefereeFacade   TacticalFacade   ReportFacade
       │                 │               │              │
       ▼                 ▼               ▼              ▼
 BasicStats         Referee         four_factors       basic_stats
 Calculator         _history        possession_stats   + referee
 .get_all_player_   .final_         advanced_stats     + four_factors
 stats()            decisions       (EventStatsSet)    (종합)
 .get_team_totals()                                    
```

---

## 6. Phase 15 누적 진행도

| 세션 | Tier | 처리 건수 | 파일 변경 |
|---|---|---|---|
| 1 | Tier 1 + Tier 4 | 9 | 24 |
| 2 | Tier 3 M1 | 10 | 4 |
| 3 | Tier 5 | 7 | 5 |
| 4 | Tier 3 M2 | 31 | 32 |
| 5 | Tier 3 M3 | 26 | 29 |
| 6 | Tier 3 M4+M5 | 4 | 4 |
| 7 | Tier 2 H5 | 7 | 7 |
| 8 | Tier 2 H6 | 1 | 8 |
| 9 | Tier 2 H1+H2+H3 | 3 | 14 |
| **10** | **Tier 2 H4** | **5** | **5** |
| **합계** | — | **103** | **132** |

### 남은 Phase 15 작업

**0건 — Phase 15 전량 완료** ✓

---

## 7. Phase 15 전체 마감 요약

### 처리 건수 (총 103건)

| Tier | 이름 | 건수 |
|---|---|---|
| Tier 1 | Critical | 9 |
| Tier 2 | High | 16 (H1/H2/H3/H4/H5/H6) |
| Tier 3 | Medium | 71 (M1/M2/M3/M4/M5) |
| Tier 4 | Low | — (Tier 1에 통합) |
| Tier 5 | Deprecation | 7 |

### 주요 성과

1. **M1 (Session 2)**: GameOrchestrator에 6개 public property 추가 — 외부 접근 표준화
2. **M2 (Session 4)**: AgeGroup Enum 전환 30+ 파일 (`str` subclass로 하위 호환)
3. **M3 (Session 5)**: SeverityMapper + KoreanTemplates 싱글톤화 (메모리 ~18배 감축)
4. **M4+M5 (Session 6)**: 5요소 가중치 Config + 리그별 분기
5. **H5 (Session 7)**: shared.constants SSOT 확립 (HOOP_RADIUS 0.225→0.2286 정정)
6. **H6 (Session 8)**: korean_templates.py 1,630줄 → 8파일 분할
7. **H1/H2/H3 (Session 9)**: motion_analysis 3개 서브패키지 이전 (Layer 재정렬)
8. **H4 (Session 10)**: 5 Facade engine 데이터 연동 (API 계층 완성)

### 누적 영향

- **파일 변경**: 132파일
- **Breaking change**: H1/H2/H3 (motion_analysis → biomechanics/feedback_system 경로 변경)만. 그 외 하위 호환성 유지.
- **테스트**: 615+ 테스트 통과, pre-existing 4개는 이번 Phase 15와 무관한 stale 테스트

### 계층 구조 최종 정렬

```
Layer 0: shared/, core_foundation/ (SSOT)
Layer 1: detection/
Layer 2: pose_estimation/
Layer 3: biomechanics/ (+ phase_analysis 이전)
Layer 4: motion_analysis/ (detection/classification만)
Layer 5: game_analysis/
Layer 6: ai_referee/
Layer 7: feedback_system/ (+ form_evaluation/comparison 이전)
Layer 8: engine/
Layer 9: api_server/ (facades: engine 데이터 → 프론트엔드)
```

---

**세션 10 완료. H4 Facade 5 engine 연동 구현. Phase 15 전량 마감 (103건 / 132파일 / 10 세션).**
