# Plan — 백엔드 finalize 안전망

작성일: 2026-05-21
대상: UI 누락 버그 보완 — `_on_game_end` 콜백에 minimal finalize 추가

## 1. 배경

[PLAN_REPLAY_STOP_FIX.md](PLAN_REPLAY_STOP_FIX.md) 에서 REPLAY 모드 finalize 누락 확정.
UI 쪽 STOP 흐름은 패치했지만, 향후 또 다른 페이지/모드에서 누락 발생 시 결과 영구 손실 위험.
백엔드에서 안전망 1겹 추가 → UI 가 finalize 안 불러도 최소한 빈 manifest 라도 남게.

## 2. 동작

```
UI POST /api/v1/game/stop
  → game_service.stop_game()
     → orchestrator.stop_game()         # postgame (long)
     → _on_game_end(orch) 콜백 fire:
        - CloudSync                       (기존)
        - ExtractionFinalizer (async)     (기존)
        - safety_finalize()  ← NEW
            ├─ session_dir 확인
            ├─ <session>/finalize/manifest.json 이미 있으면 skip
            └─ 없으면 minimal UIFinalizePayload 로 finalize() 호출
UI receives response
UI POST /api/v1/finalize/game  (UI 가 정상 호출하면)
  → 전체 payload 로 overwrite (멱등)
```

## 3. 보장사항

- **idempotent**: finalize_service.finalize() 내부 lock + overwrite 패턴 → 안전
- **UI 우선**: UI 가 정상 호출하면 safety 의 minimal 을 full 로 덮어씀 (호출 순서: safety → UI)
- **누락 방어**: UI 가 호출 안 해도 빈 manifest 라도 남음 → BATCH 탭에 표시 + 향후 재finalize 가능
- **에러 격리**: safety 실패해도 stop_game 응답에 영향 없음 (try/except 감쌈)

## 4. 변경

- [ ] `api_server/main.py:_on_game_end` 끝에 safety_finalize 블록 추가 (~25 lines)
- [ ] 로그 prefix `[SAFETY-FINALIZE]` 로 식별

## 5. 리스크 + REPLAY 추가 발견

| 리스크 | 영향 | 완화 |
|---|---|---|
| stop_game 응답 지연 (safety finalize ~100-500ms) | 무시할 수준 | finalize 자체가 빠름 (JSON 7개) |
| UI finalize 가 더 빨리 끝나서 safety 가 overwrite? | 불가능 — 동기 실행 순서상 safety 가 먼저 끝남 (callback 내) | N/A |
| **REPLAY 에선 recording_service stale LIVE 세션을 잡음** | safety 가 wrong dir 에 manifest 씀 → 진짜 LIVE 결과 손상 위험 | **(a) active=True 이거나 (b) ended_at ≤ 60s 일 때만 safety 발동**. REPLAY 는 둘 다 안 맞아 자동 skip |
| operator 가 finalize 늦게 호출 (작전타임 등) | safety 가 먼저 minimal 작성 → UI 가 덮어씀 | 의도된 동작 |

## 5.5. REPLAY 전용 추가 fix (발견 후 진행)

조사 중 발견 — REPLAY 모드는 **recording_service 를 통해 session 등록을 하지 않음**. 따라서:
- UI 의 `/api/v1/finalize/game` 호출도 그동안 실패하고 있었음 (활성 녹화 세션 없음)
- `recording_service.get_status()` 가 stale 한 이전 LIVE 세션 가리킴

→ FinalizeRequest 에 `session_id` 필드 추가 (REPLAY UI 가 명시 전달) + finalize_service._resolve_session_dir 가 explicit_session_id 우선 사용하도록 보강.

- [x] `FinalizeRequest.session_id: str = ""` 추가 (routes/v1/finalize_routes.py)
- [x] `UIFinalizePayload.session_id: str = ""` 추가 (services/finalize_service.py)
- [x] `_resolve_session_dir(explicit_session_id="")` 시그니처 + 우선순위 로직
- [x] `replay_view.html` finalize payload 에 `session_id: sessionId` 포함

## 6. 체크리스트

- [x] 사용자 승인
- [x] main.py _on_game_end 에 safety_finalize 블록 추가 (`[SAFETY-FINALIZE]` prefix)
- [x] active=True / ended_at≤60s 조건으로 REPLAY 오작동 방지
- [x] REPLAY: finalize_service / FinalizeRequest 가 explicit session_id 받게 보강
- [x] replay_view.html finalize 호출에 session_id 포함
- [ ] 다음 game/stop 시 로그 `[SAFETY-FINALIZE]` 확인
- [ ] LIVE: manifest 가 safety 로 자동 생성됨 확인
- [ ] REPLAY: import_* 폴더에 finalize/manifest.json 생성됨 확인
