# Plan — FRAME cadence 이벤트 buffer 적재 누락

작성일: 2026-05-21
대상: events.json `engine_events_count=0` 원인 fix

## 1. 현상

REPLAY/LIVE 분석 후 finalize 시 [events.json](recordings/import_2026-05-19_003120/finalize/events.json):
```
engine_events: []
engine_events_count: 0
```

사용자 게임에서 `🏀 득점 감지 F#21 79%` 가 UI EVENT FEED 에 표시됐는데도 0건.

## 2. 근본 원인

[game_orchestrator.py](engine/orchestrator/game_orchestrator.py) 의 FRAME cadence 콜백에서 직접 감지하는 3종 detector 가 **`_analysis_buffer.ingest_events()` 호출 안 함**:

| 위치 | 감지기 | 누락 |
|---|---|---|
| [game_orchestrator.py:1387](engine/orchestrator/game_orchestrator.py#L1387) | `_score_detector.process_frame` | ❌ buffer 적재 |
| [game_orchestrator.py:1436](engine/orchestrator/game_orchestrator.py#L1436) | `_possession_tracker.process_frame` | ❌ buffer 적재 |
| [game_orchestrator.py:1477](engine/orchestrator/game_orchestrator.py#L1477) | `_dead_ball_detector.process_frame` | ❌ buffer 적재 |

이 3종은 WS dispatch 만 해서 UI 에는 표시되지만 `_event_buffer` 에는 안 들어감.

EVENT cadence ([game_orchestrator.py:1577](engine/orchestrator/game_orchestrator.py#L1577)) 의 `_analysis_buffer.ingest_events(event_result.detected_events)` 만 buffer 에 적재. 그런데 EVENT cadence 의 [event_pipeline.py:405-445](engine/pipeline/event_pipeline.py#L405-L445) 는 shot_event/rebound/foul/screen/... 만 호출하고 **score/possession/dead_ball 은 호출 안 함**.

→ FRAME cadence 에서만 감지되는 이 3종은 영구 손실. finalize 시 events.json 비어있음.

## 3. 중복 적재 우려

EVENT cadence 가 score/possession/dead_ball 을 다시 호출하지 않으므로 **중복 적재 X** — 각 detection 은 단 1번만 buffer 에 들어감.

## 4. 패치

각 FRAME-cadence detection 성공 직후 (set_trigger 다음, dispatch 이전):

```python
if evt is not None:
    sm.set_trigger(pending_shooting=True)
    # 2026-05-21: events.json 누락 fix — FRAME cadence 직접 감지 이벤트도 buffer 적재
    if self._analysis_buffer is not None:
        try:
            self._analysis_buffer.ingest_events([evt])
        except Exception:
            _logger.exception("score 이벤트 buffer 적재 실패")
    _logger.warning("🏀 득점 감지: ...")
```

## 5. 변경 파일

- [ ] [engine/orchestrator/game_orchestrator.py](engine/orchestrator/game_orchestrator.py)
  - score (line 1389 직후)
  - possession (line 1438 직후)
  - dead_ball (line 1481 직후)

## 6. 체크리스트

- [x] 사용자 승인 (fix 진행)
- [x] 3 detector 블록에 ingest_events 추가 (score / possession / dead_ball)
- [x] 문법 검증 (`ast.parse` OK)
- [ ] 다음 분석 → finalize → events.json 에 engine_events 채워짐 확인
- [ ] UI BATCH 탭 detail 진입 시 events 표시 확인
