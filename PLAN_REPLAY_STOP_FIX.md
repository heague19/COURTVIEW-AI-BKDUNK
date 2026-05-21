# Plan — REPLAY STOP 막힘 풀기

작성일: 2026-05-21
대상: replay_view.html STOP 버튼 → finalize + navigation 없어서 화면 freeze

## 1. 현상

[replay_view.html:621-631](courtview_ui/templates/pages/replay_view.html#L621) STOP 핸들러가:
- `/api/v1/game/stop` 만 호출 (postgame 동기 처리 60s+ 블로킹)
- 응답 받아도 `onAnalysisDone('stopped')` 만 — 같은 페이지에 멈춤
- finalize 호출 X → events.json 등 결과 파일 안 만들어짐
- /game/result 로 navigation X → 사용자 freeze 경험

## 2. 정식 흐름 (게임분석 페이지 참고)

[game_analysis.html:1614-1673](courtview_ui/templates/pages/game_analysis.html#L1614-L1673):
```
1. /api/v1/recording/stop  (60s, 404=OK)
2. /api/v1/game/stop       (60s)
3. /api/v1/finalize/game   (120s, payload)
4. window.location.href = '/game/result'
```

## 3. 패치 (replay_view.html STOP 핸들러)

- [x] **STEP 1**: 버튼 클릭 즉시 progText 갱신 → "🛑 분석 종료 중..." (응답 대기 freeze 보이지 않게)
- [x] **STEP 2**: ETA polling 중단 + WS 닫기 (즉시)
- [x] **STEP 3**: `/api/v1/recording/stop` 호출 (REPLAY 모드는 녹화 안 함이지만 안전 차원, 404 무시)
- [x] **STEP 4**: `/api/v1/game/stop` 호출 (기존)
- [x] **STEP 5**: 진행 텍스트 "⏳ 결과 패키징 중..." 갱신 후 `/api/v1/finalize/game` 호출
- [x] **STEP 6**: 응답 OK 면 `window.location.href = '/game/result?session_id=<id>'`
- [x] **STEP 7**: 실패 시 confirm 으로 이동 여부 물음

## 4. finalize payload (REPLAY 최소화)

REPLAY 는 operator events / 선수 명단 없음 → 최소 payload:
```js
{
    match_id: sessionId,                   // 세션ID 를 match_id 로 (백엔드 fallback)
    league: 'fiba',
    home_team: { name: 'HOME', short_code: 'HOM', players: [] },
    away_team: { name: 'AWAY', short_code: 'AWA', players: [] },
    final_home: 0,
    final_away: 0,
    ended_at: Date.now() / 1000,
}
```

## 5. (선택) game_result.html 자동 detail 열기

- [ ] URL `?session_id=<id>` 있으면 init() 끝나고 해당 row 자동 showDetail 호출

## 6. 변경 파일

| 파일 | 변경량 |
|---|---|
| `courtview_ui/templates/pages/replay_view.html` | STOP 핸들러 ~40줄 (기존 10줄 대체) |
| `courtview_ui/templates/pages/game_result.html` | init() 끝에 URL param 처리 ~10줄 (선택) |

## 6.5. 누락 버그 검증 (2026-05-21)

3가지 증거로 finalize 누락 확정:

1. **UI 코드**: replay_view.html 구 STOP 핸들러 (line 621-631) 에 `/api/v1/finalize/game` 호출 **없음**. game_analysis.html:1645 / operator.html:1388 에는 있음.

2. **백엔드 콜백** ([api_server/main.py:277-297](api_server/main.py#L277-L297)): `_on_game_end(orch)` 는 CloudSync + ExtractionFinalizer 만 트리거. `finalize_service.finalize()` 호출 X → UI 가 명시 호출 안 하면 `<session>/finalize/` 영구 미생성.

3. **파일시스템**:
   - LIVE 세션 70+ 개 → 전부 `finalize/manifest.json` 존재
   - REPLAY (`import_*`) 5개 → 단 하나도 `finalize/` 폴더 없음 (단일 manifest.json 은 소스 영상 등록 메타임, 별개)

→ 5/11, 5/19 모든 REPLAY 결과가 영구 손실된 원인.

## 7. 체크리스트

- [x] 사용자 승인
- [x] replay_view.html STOP 핸들러 교체
- [x] game_result.html `_loadLocalResults` mode 구분 (`import_*` → batch)
- [x] game_result.html `init()` URL `?session_id=` → 자동 detail 오픈
- [ ] 다음 STOP 시 확인:
  - [ ] 진행 텍스트 단계별 갱신
  - [ ] /game/result 자동 이동
  - [ ] recordings/<session>/finalize/events.json 의 engine_events 채워짐
