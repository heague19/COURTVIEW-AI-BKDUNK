# Plan — 이벤트 타임라인 UI

작성일: 2026-05-14
상태: 계획만 (구현 X)

## 1. 배경

게임 종료 후 사용자가 **시간 순서대로 발생한 이벤트** (슛/리바운드/턴오버/스틸 등) 를 한눈에 볼 수 있는 타임라인 UI 가 필요. 클릭 시 해당 시점 영상으로 점프 가능해야 함.

## 2. 현재 코드 상태 (3가지 갭)

### 2.1 데이터 모델 ✅ 준비됨

[game_analysis/game_state/event_detection/shot_event_detector.py:385-392](game_analysis/game_state/event_detection/shot_event_detector.py#L385):
```python
GameEvent(
    event_type=GameEventType.SHOT_ATTEMPT,
    frame_number=last.frame_index,
    timestamp=last.timestamp_sec,
    quarter=last.quarter,
    ...
)
```

13종 event detector 가 모두 동일 구조의 `GameEvent` 객체 생성.
→ frame_index, timestamp, quarter, event_type, player_id 모두 있음. **타임라인 그리기 충분**.

### 2.2 실시간 흐름 ✅ 작동

```
event_pipeline → analysis_buffer._event_buffer.extend(events)
                 analysis_buffer._possession_events.extend(events)
```

게임 진행 중 모든 event 가 메모리에 누적.

### 2.3 영구 저장 ⚠️ 갭 발견

[api_server/services/finalize_service.py:327-338](api_server/services/finalize_service.py#L327):
```python
def _write_events(self, finalize_dir, ui, snapshot) -> str:
    """operator 이벤트 + 엔진 탐지 이벤트 병합 타임라인."""
    data = {
        "schema_version": SCHEMA_VERSION,
        "operator_events": ui.operator_events,    # ← operator 만 dump
    }
    return self._dump(finalize_dir / "events.json", data)
```

**주석은 "병합"** 이라 적혀있지만 실제 코드는 `operator_events` 만 dump.
→ **엔진 탐지 이벤트 (`_event_buffer`) 가 events.json 에 안 들어감**. S3 업로드도 안 됨. 사라짐.

### 2.4 UI 표시 ⚠️ 컴포넌트 없음

[courtview_ui/templates/pages/game_result.html](courtview_ui/templates/pages/game_result.html):

| 항목 | 위치 | 상태 |
|---|---|---|
| `d-highlights` div | line 260 | ✅ highlights.json 의 clips 만 표시 |
| events fetch | line 712 | ✅ 받아오긴 함 |
| events 사용처 | line 764 `events.operator_events.length` | ⚠️ 개수만, 타임라인 없음 |
| **timeline 컴포넌트** | — | ❌ **없음** |
| 쿼터 탭 필터 (1Q~4Q) | line 1530 `switchQuarter` | ✅ 이미 존재 (highlights 필터링용) |
| 영상 sync 점프 | line 1571 | ✅ clip 단위, ❌ event timestamp 점프는 X |

## 3. 목표 데이터 흐름

```
event 발생 (메모리)
   ↓ _event_buffer 누적 (deque(maxlen=2000) 으로 fix 됨)
finalize_service._write_events
   ↓ ✅ operator + 엔진 이벤트 병합, timestamp 정렬
events.json {
    operator_events: [...],
    engine_events: [
        {type, timestamp, quarter, player_id, frame_index, ...},
        ...
    ]
}
   ↓ UI fetch (/api/v1/finalize/detail/<id>)
game_result.html
   ↓ ✅ 타임라인 컴포넌트:
       - timestamp 기준 시간순 정렬
       - 쿼터별 필터 (기존 q-tab 재사용)
       - event_type 아이콘 (🏀슛, 🛡블록, 💎리바운드 등)
       - 클릭 → 영상 currentTime 점프
사용자
```

## 4. STEP 별 구현 계획

### STEP A — Backend: 엔진 이벤트도 events.json 에 저장 ✅ (2026-05-21 완료)
- [x] **파일 1**: `engine/analysis_buffer.py` — `get_engine_events()` public 메서드 추가
  - Pydantic BaseModel / dataclass / dict / fallback 모두 처리
  - Enum / UUID → str 정리 (JSON 호환)
- [x] **파일 2**: `api_server/services/export_service.py:collect_snapshot()` — `snapshot["events"] = buf.get_engine_events()` 추가
  - `_analysis_buffer` 가 없거나 메서드 없으면 빈 배열로 안전 fallback
- [x] **파일 3**: `api_server/services/finalize_service.py:_write_events` — `snapshot.get("events")` → `engine_events` 로 dump
  - `engine_events_count` 도 함께 (확인 편의용)
- [ ] **검증**: 다음 game/stop 후 `recordings/<game>/finalize/events.json` 에 `engine_events` 배열 확인

### STEP B — UI: 타임라인 컴포넌트 (필수, 2~3h)
- [ ] **파일**: `courtview_ui/templates/pages/game_result.html`
- [ ] **컴포넌트 위치**: `d-highlights` 아래 또는 별도 섹션 `d-events-timeline`
- [ ] **렌더 로직**:
  - timestamp 기준 정렬
  - 쿼터 필터 적용 (`currentQuarter`)
  - event_type → 아이콘 매핑
  - 클릭 핸들러: `seekToEvent(timestamp, quarter)`
- [ ] **CSS**: 기존 `event-item` 클래스 재사용 (이미 존재 line 1547)
- [ ] **검증**: 시뮬레이션 데이터 또는 실제 게임 후 표시 확인

### STEP C — 영상 sync 점프 (선택, 1~2h)
- [ ] **방법 1 (raw 영상)**: `<video>.currentTime = event.timestamp` 직접 설정
- [ ] **방법 2 (clip 점프)**: event_type 매칭되는 highlight clip 있으면 그걸 재생
- [ ] **멀티뷰 sync (선택)**: 8대 카메라 동시 점프 — 복잡, V2 로 미루기 권장

### STEP D — Live timeline WebSocket (선택, V2)
- [ ] **방법**: 기존 `/ws/live` 에 `event` 메시지 추가
- [ ] **UI 실시간 push**: 분석 결과 실시간 표시

## 5. 변경 파일 요약

| STEP | 파일 | 변경 양 |
|---|---|---|
| A | `engine/orchestrator/game_orchestrator.py` | snapshot 1줄 추가 |
| A | `engine/analysis_buffer.py` | `get_all_events()` 메서드 신설 (~10 lines) |
| A | `api_server/services/finalize_service.py` | `_write_events` 1줄 추가 |
| B | `courtview_ui/templates/pages/game_result.html` | HTML + JS ~100 lines |
| C | `courtview_ui/templates/pages/game_result.html` | seekToEvent 함수 ~20 lines |
| D | `engine/orchestrator/game_orchestrator.py` + UI WS handler | (선택) |

## 6. 리스크 / 의존성

| 리스크 | 영향 | 완화 |
|---|---|---|
| 현재 detection failure (player=0) 로 엔진 이벤트 거의 0건 | 데이터 없음 | 선결: 카메라 정상 연결 + 영상에 사람 |
| events.json 크기 증가 | S3 비용 / 로딩 속도 | 1게임 1000 events × ~1KB = 1MB 미만 OK |
| GameEvent 직렬화 (dataclass → dict) | 일부 필드 누락 가능 | `asdict()` + 특수 필드 수동 처리 |

## 7. 선결 조건

1. ✅ 카메라 8대 정상 RTSP 연결 (오늘 0대 → 좀비 세션 fix 필요)
2. ✅ 영상에 사람/공이 들어와서 detector 작동
3. ✅ `_event_buffer` deque 변환 (지금 진행)

## 8. 진행 체크리스트

- [ ] 사용자 승인
- [ ] STEP A 적용
- [ ] STEP A 검증 (events.json 안에 engine_events)
- [ ] STEP B 적용
- [ ] STEP B 검증 (UI 에서 timeline 표시)
- [ ] STEP C 적용 (선택)
- [ ] STEP D 적용 (선택)
- [ ] 다음 경기 테스트로 end-to-end 검증
