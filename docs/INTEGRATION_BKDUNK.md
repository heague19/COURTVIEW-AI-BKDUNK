# COURTVIEW Desktop × bkdunk 백엔드 통합 스펙

> **버전**: v0.1 (초안)
> **작성일**: 2026-04-23
> **대상 독자**: bkdunk 백엔드 개발팀
> **목적**: 현장 노트북에 설치된 COURTVIEW Desktop (Windows AI 농구 분석 앱) 이 경기 종료 시 자동으로 bkdunk 백엔드에 경기 데이터를 업로드하도록 양측 계약을 합의

---

## 0. 요약 (TL;DR)

- **프로토콜**: HTTPS JSON POST
- **주 엔드포인트**: `POST {COURTVIEW_CLOUD_URL}/api/v1/games` ← bkdunk 가 구현할 것
- **인증**: `Authorization: Bearer {SPOIN_ID_TOKEN}`
- **업로드 트리거**: 경기 종료 시 자동 (현장 노트북에서)
- **오프라인 대응**: COURTVIEW 측 로컬 JSONL 큐 + 60초 주기 재시도 워커 (**이미 구현됨**)
- **페이로드**: 경기 전체 스냅샷 JSON (박스스코어, 판정, 통계, 하이라이트, 피드백 등)
- **현재 구현 상태**: COURTVIEW 쪽 80% (핵심 전송·큐·재시도 완성). bkdunk 쪽은 아직 수신기 미준비 → **이 문서의 결정 사항 확정 후 바로 구현 가능**

---

## 1. 시스템 구조

```
┌───────────────────────────────┐      HTTPS POST      ┌──────────────────────────┐
│ COURTVIEW Desktop             │ ── game_result ────▶ │ bkdunk 백엔드             │
│ (현장 Windows 노트북)          │   Authorization:     │ (SPOIN 본사)              │
│                               │   Bearer {token}     │                          │
│  ✓ 로컬 GPU AI 분석            │                      │  ✓ 통합 DB                │
│  ✓ 오프라인 JSONL 큐           │  ◀── 200 OK ──       │  ✓ 관리자 대시보드        │
│  ✓ 60s 주기 재시도 워커        │                      │  ✓ 리포트·통계 집계       │
│                               │                      │                          │
│  localhost:8000 (내부 API)    │                      │                          │
│  localhost:3000 (UI)          │                      │                          │
└───────────────────────────────┘                      └──────────────────────────┘

[노트북 로컬 저장]                                      [본사 스토리지]
  %APPDATA%\COURTVIEW\                                    bkdunk DB (RDBMS)
    ├─ games\                                             + bkdunk 스토리지
    │   └─ {session_id}\snapshot.json                       (영상 클립 추후)
    ├─ cloud_sync_queue\
    │   └─ {ts}_{kind}.json  (오프라인 시)
    └─ logs\
  D:\COURTVIEW_Recordings\
    └─ {session_id}\clips\*.mp4
```

**노트북 1대 = 1 현장 = 1 경기 분석 인스턴스.** 현장 인터넷이 불안정할 수 있으므로 **offline-first** 설계: 로컬에서 모든 분석이 완결되고, 온라인 복귀 시 자동으로 bkdunk 로 업로드.

---

## 2. 연동 플로우

### 2.1 경기 종료 → 자동 업로드

```
사용자                 COURTVIEW Desktop              bkdunk 백엔드
 │                         │                              │
 │ "경기 종료" 클릭        │                              │
 │────────────────────────▶│                              │
 │                         │ ExportService.collect_snapshot()
 │                         │ (박스스코어 + 판정 + 하이라이트 전부)
 │                         │                              │
 │                         │ CloudSyncService.sync_game_result(snapshot)
 │                         │                              │
 │                         │   POST /api/v1/games         │
 │                         │─────────────────────────────▶│
 │                         │                              │ DB 저장
 │                         │                              │ (upsert by game_id)
 │                         │   200 OK                     │
 │                         │◀─────────────────────────────│
 │                         │                              │
 │                         │ 전송 성공                     │
 │                         │                              │
 │ 최종 점수 표시          │                              │
 │◀────────────────────────│                              │
```

### 2.2 네트워크 실패 시 (offline-first)

```
경기 종료                                                 bkdunk 백엔드
   │                                                         │
   ▼                                                         │
POST /api/v1/games ──── 네트워크 에러 ────X                    │
   │                                                         │
   ▼                                                         │
 로컬 큐에 저장:                                              │
 %APPDATA%\COURTVIEW\cloud_sync_queue\                       │
   1776767195749_game_result.json                            │
   │                                                         │
   │   (60초 간격 워커)                                        │
   ▼                                                         │
 POST 재시도 ──── 네트워크 복구 ─────▶───────────────────▶│
                                                              ▼
                                              DB 저장 (같은 game_id 로 upsert)
                                                              │
                                              200 OK ────────▶ 큐에서 파일 삭제
```

재시도 정책 (COURTVIEW 측, 이미 구현):
- HTTP POST 단일 시도 재시도 **3회** (지수백오프 1s, 2s, 4s)
- 3회 모두 실패 시 → **로컬 JSONL 큐** 저장
- 백그라운드 워커가 **60초마다** 큐 드레인 시도
- 순서 보장: 한 항목 전송 실패 시 이후 큐 항목 전송 중단 (다음 주기까지 대기)

---

## 3. API 계약

### 3.1 필수 엔드포인트 (bkdunk 구현 필요)

```
POST {COURTVIEW_CLOUD_URL}/api/v1/games
```

**헤더**

| 키 | 값 | 비고 |
|---|---|---|
| `Authorization` | `Bearer {SPOIN_ID_TOKEN}` | 노트북별 토큰, 환경변수 주입 |
| `Content-Type` | `application/json; charset=utf-8` | |
| `User-Agent` | `CourtViewDesk/1.0` | COURTVIEW 측 고정값 |

**본문** — 경기 전체 스냅샷 JSON (4절 스키마 참고)

**응답**

| HTTP | 의미 | COURTVIEW 동작 |
|---|---|---|
| `200 OK` / `201 Created` | 수신·저장 완료 | 성공 로그, 큐에서 제거 |
| `401 Unauthorized` | 토큰 문제 | 재시도 (토큰 갱신 후) |
| `4xx` (400/404 등) | payload/요청 문제 | 3회 재시도 후 큐 저장 — bkdunk 팀 로그 확인 필요 |
| `5xx` | 서버 에러 | 3회 재시도 → 큐 → 60초 후 재드레인 |
| Network timeout | 연결 실패 | 동일 (큐) |

**응답 본문** (옵션, 권장):
```json
{
  "ok": true,
  "server_game_id": "bkdunk-assigned-uuid",   // DB 저장 후 생성된 ID (옵션)
  "received_at": "2026-04-22T21:30:02.123Z"
}
```

현재 COURTVIEW 는 **응답 본문을 파싱하지 않음** (2xx 만 확인). 추후 `server_game_id` 를 활용하려면 클라이언트 수정 필요 — 지금은 무시해도 무방.

### 3.2 실시간 스탯 엔드포인트 (옵션, best-effort)

```
POST {COURTVIEW_CLOUD_URL}/api/v1/stats
```

경기 중 주기적으로 박스스코어·통계를 보낼 수 있음. **큐에 저장하지 않고** fire-and-forget. 현재 COURTVIEW 에서는 호출 안 함 (구현만 돼있고 연결 안 됨). bkdunk 에서 **지금 당장은 만들지 않아도 OK**, 향후 대시보드 실시간 기능 요구 시 추가.

---

## 4. Payload 스키마

### 4.1 최상위 구조 (`game_result` 페이로드)

```json
{
  "active": true,
  "timestamp": 1776767195.749,

  "box_score": { ... },          // 4.2
  "players":   [ ... ],          // 4.3 (선수 통계 배열)
  "teams":     [ ... ],          // 4.4 (팀 통계 배열)
  "referee":   { ... },          // 4.5
  "tactical":  { ... },          // 4.6
  "report":    { ... },          // 4.7 (매니저용 종합 리포트)
  "scouting":  { ... },          // 4.8 (스카우팅 리포트)
  "highlights":[ ... ],          // 4.9 (하이라이트 클립 메타)
  "feedback":  { ... }           // 4.10 (코치·선수 피드백)
}
```

각 sub-object 는 **pydantic BaseModel 의 `.model_dump()`** 결과 (순수 JSON-serializable dict). `None` 필드는 기본값 그대로 포함될 수 있음 — bkdunk DB 스키마 설계 시 **nullable** 로 안전하게.

### 4.2 `box_score`

경기 최종 점수·시간·쿼터 등.

주요 필드 (발견 즉시 세부 스키마 pin 가능):
- `game_id`: UUID 문자열
- `home_team`: `TeamInfo`
- `away_team`: `TeamInfo`
- `home_score`, `away_score`: int
- `current_quarter`: int
- `game_clock`: "MM:SS"
- `events`: `GameEvent[]` — 경기 중 발생한 모든 이벤트 (슛·파울·타임아웃 등)

전체 정의: `shared/dto/game_dto.py` → `GameStats`, `GameEvent`, `TeamInfo`, `ShotAttempt`.

### 4.3 `players` (배열)

각 선수별 통계 (`PlayerStats`):
- `player_tracking_id` (int, 영상 내 tracking id)
- `jersey_number` (0~99)
- `team_id`
- `minutes_played` (float)
- `points`, `rebounds`, `assists`, `steals`, `blocks`, `turnovers`
- `field_goals_made`/`attempted`, `three_pointers_*`, `free_throws_*`
- `efficiency` (계산 필드)

선수 식별: `player_id` (외부 연동 시) 또는 `tracking_id` (영상 내).

### 4.4 `teams` (배열)

팀별 통계 (`TeamStats`). 필드는 `PlayerStats` 와 유사하나 팀 단위 집계.

### 4.5 `referee`

AI 심판 판정 기록 (`GameRefereeReport`):
- `violations`: `ViolationDecision[]` (트래블·더블드리블·바이올레이션)
- `fouls`: `FoulDecision[]` (개인 파울·테크니컬·플레이그런트)
- `corrections`: 심판이 수동 보정한 판정 기록
- `confidence_stats`: AI 평균 신뢰도·합의율

전체 정의: `shared/dto/referee_dto.py`.

### 4.6 `tactical`

전술 분석 (`TacticalReport`):
- `formations`: 자주 관찰된 포메이션
- `plays`: 픽앤롤·ISO·패스 패턴
- `defense_style`: "zone" | "man-to-man" | ...

전체 정의: `shared/dto/tactical_dto.py`.

### 4.7 `report`

매니저용 종합 리포트 (지표 요약 + 주요 순간 주석).

### 4.8 `scouting`

상대 팀 스카우팅 관점 리포트.

### 4.9 `highlights` (배열)

하이라이트 클립 메타 (MP4 자체는 미포함 — 7절 참고):
- `clip_id`: UUID
- `title`: str (자동 생성)
- `start_frame`, `end_frame`: int
- `duration_sec`: float
- `highlight_type`: enum (DUNK / THREE_POINTER / BLOCK / ASSIST / ...)
- `excitement_score`, `importance_score`: 0~100
- `clip_url`: **현재 로컬 경로** (예: `D:\COURTVIEW_Recordings\...\clip_42.mp4`) — bkdunk 스토리지 미확정이라 null 이거나 로컬 경로 (7절 참조)
- `thumbnail_url`: 상동

전체 정의: `shared/dto/game_dto.py` → `HighlightReel`, `media_dto.py` → `VideoClip`.

### 4.10 `feedback`

```json
{
  "items": [
    { "target": "player|team|coach", "type": "shooting|defense|...", "message": "...", "priority": 1 }
  ],
  "total": 12
}
```

전체 정의: `shared/dto/feedback_dto.py`.

### 4.11 예시 페이로드 (최소 버전)

```json
{
  "active": true,
  "timestamp": 1776767195.749,
  "box_score": {
    "game_id": "a1b2c3d4-...",
    "home_team": { "team_id": "HOME", "team_name": "SPOIN", "is_home": true },
    "away_team": { "team_id": "AWAY", "team_name": "Visitors", "is_home": false },
    "home_score": 78,
    "away_score": 82,
    "current_quarter": 4,
    "events": []
  },
  "players": [],
  "teams": [],
  "referee": { "violations": [], "fouls": [] },
  "tactical": {},
  "report": {},
  "scouting": {},
  "highlights": [],
  "feedback": { "items": [], "total": 0 }
}
```

**실제 경기 데이터는 각 배열에 수십~수백 개** 들어감. 한 경기 스냅샷 JSON 크기는 대략 **0.5–3 MB** 로 추정.

---

## 5. 인증

### 5.1 현재 설계

COURTVIEW 런타임이 다음 환경변수를 읽어 요청 헤더 구성:

| 환경변수 | 용도 |
|---|---|
| `COURTVIEW_CLOUD_URL` | bkdunk 백엔드 base URL (예: `https://api.bkdunk.spoin.co.kr`) |
| `COURTVIEW_CLOUD_TOKEN` | `Authorization: Bearer` 로 보낼 토큰 |
| `COURTVIEW_CLOUD_ENABLED` | `"1"` 일 때만 활성화 (개발 중 꺼둘 수 있게) |

**런타임 갱신 지원**: `CloudSyncService.set_token(token)` — UI 로그인 후 토큰 새로 받을 때 호출.

### 5.2 bkdunk 결정 사항 (5절의 핵심 질문)

토큰 발급·관리 전략은 **bkdunk 에서 결정**:

- [ ] **노트북 단위 토큰**: 노트북 1대 = 토큰 1개 (설치 시 SPOIN IT 가 발급·주입)
  - 장점: 구현 단순, 노트북별 audit log 쉬움
  - 단점: 유출 시 갱신 번거로움, 사용자 개념 없음
- [ ] **조직/팀 단위 토큰**: B2B 납품 시 고객사별 1 토큰, 여러 노트북 공유
  - 장점: 관리 단순
  - 단점: 노트북 식별 불가 (payload 에 `device_id` 추가 필요)
- [ ] **사용자 로그인 + JWT**: 코치·심판이 UI 로그인 → JWT 발급
  - 장점: 사용자별 권한, 갱신 용이
  - 단점: UI 로그인 화면 필요 (현재 `templates/pages/login.html` 존재 확인 요)

**추천**: **노트북 단위 + JWT 갱신 가능** 조합. 설치 시 bkdunk 에 노트북 등록 API (`POST /api/v1/devices/register`) 를 호출해 JWT 수령 → `COURTVIEW_CLOUD_TOKEN` 저장. 만료 전 갱신.

### 5.3 토큰 유출 시

- bkdunk 측에서 해당 토큰 revoke
- 해당 노트북은 다음 업로드 시 401 → 큐에 누적 → 수동 재발급 후 큐 자동 플러시

---

## 6. Idempotency (중복 방지)

현장 → bkdunk 네트워크 타임아웃 시 COURTVIEW 는 **같은 payload 를 재전송**합니다. bkdunk 측에서 반드시 중복 방지 로직 구현 필요.

**권장 방식**: `game_id` (또는 `(session_id, game_id)` 조합) 기준 **upsert**
- 첫 수신: INSERT
- 재수신: UPDATE (같은 경기의 최종 상태는 항상 동일)

payload 의 `box_score.game_id` 는 **노트북에서 생성한 UUID** 이므로 전역적으로 unique. bkdunk DB PK 로 사용 가능.

대안 (RFC 7240 준수): COURTVIEW 측에서 `Idempotency-Key` 헤더 전송 — **현재 미구현**. bkdunk 가 요구하면 추가 가능 (15분 작업).

---

## 7. 미디어 (영상 클립) 업로드

### 7.1 현재 상태

- **JSON 스냅샷만 전송**. MP4 파일은 로컬(`D:\COURTVIEW_Recordings\{session_id}\clips\*.mp4`)에만 존재
- `HighlightReel` DTO 의 `clip_url` 필드는 로컬 경로 (bkdunk 에서는 접근 불가능)

### 7.2 안 제시 (bkdunk 결정 필요)

| 안 | 플로우 | 장점 | 단점 |
|---|---|---|---|
| **A. Presigned URL** ✓ 권장 | COURTVIEW 가 `POST /api/v1/games` 로 스냅샷 → bkdunk 응답에 클립별 upload URL 포함 → COURTVIEW 가 S3 등에 직접 PUT | bkdunk 서버 대역폭·처리 부담 0 | 양측 3개월 정도 구현 시간 필요 |
| B. 직접 multipart POST | `POST /api/v1/games/{game_id}/clips` 로 multipart/form-data | 단순 | bkdunk 가 대용량(GB) 업로드 수신 — 대역폭·디스크 부담 |
| C. 링크만 저장 (SMB/NFS) | `clip_url` 에 사내망 UNC 경로 | 구현 없음 | 사내망 밖 접근 불가 |

**권장: A (Presigned URL + S3)**. 참고:
- COURTVIEW 측은 이미 `courtview-releases` S3 버킷 사용 중 (auto-update)
- bkdunk 가 별도 버킷(`courtview-clips` 등) 만들고 presigned PUT URL 발급

### 7.3 A 안의 확장 계약 (향후)

```
// 1. 스냅샷 업로드 (기존)
POST /api/v1/games
Body: { ...snapshot..., "pending_clips": [{clip_id, local_path, size_bytes}...] }

Response:
{
  "ok": true,
  "server_game_id": "...",
  "upload_urls": [
    { "clip_id": "...", "put_url": "https://s3...", "expires_at": "..." }
  ]
}

// 2. 각 클립 업로드 (COURTVIEW → S3 직접)
PUT {put_url}
Body: <mp4 binary>

// 3. 업로드 완료 통보 (옵션)
POST /api/v1/games/{game_id}/clips/{clip_id}/complete
```

이 단계는 **v0.2 이후** 로 미룸. v0.1 (MVP) 는 JSON 스냅샷만.

---

## 8. 운영 고려

### 8.1 크기·빈도

- 한 경기 스냅샷: **~0.5–3 MB**
- 한 경기 지속 시간: 2–3 시간
- 업로드 빈도: 경기 종료 시 1회 + 큐 재시도 (offline 복구 시 몰려서 N회)
- 초기 배포 규모: **노트북 1–10 대** (SPOIN 자사 + B2B 파일럿)

### 8.2 관측·디버깅

COURTVIEW 측 로그 (`%APPDATA%\COURTVIEW\logs\`):
- `Cloud 전송 성공: /api/v1/games (attempt 1/3, NNN bytes)` — 정상
- `Cloud 전송 실패: ... (attempt X/3): <error>` — 재시도 중
- `큐 저장: 1776767195749_game_result.json` — 큐 진입
- `큐 flush: N 전송 성공, M 실패` — 60초 워커 결과

bkdunk 측에서 제공하면 좋은 것:
- 요청별 응답 body 에 **server_game_id** 포함
- 실패 시 구체적 에러 코드 (예: `E_INVALID_GAME_ID`, `E_TOKEN_EXPIRED`)

### 8.3 스테이징 환경

개발·테스트 용도로 **별도 URL/토큰**을 환경변수로 주입 가능.

```
# 스테이징 테스트 시
set COURTVIEW_CLOUD_URL=https://staging-api.bkdunk.spoin.co.kr
set COURTVIEW_CLOUD_TOKEN=test-token-xyz
set COURTVIEW_CLOUD_ENABLED=1
```

bkdunk 에서 **스테이징 URL + 테스트 토큰**을 제공해주면 COURTVIEW 팀이 end-to-end 검증 가능.

---

## 9. bkdunk 가 결정·준비해야 할 것 (체크리스트)

### 9.1 즉시 결정 (v0.1 MVP 위해 필수)

- [ ] **프로덕션 base URL** 확정 (예: `https://api.bkdunk.spoin.co.kr`)
- [ ] **스테이징 base URL** 및 **테스트 토큰** 발급
- [ ] **토큰 발급 정책** (노트북 단위 / 조직 단위 / 사용자 JWT 중 1)
- [ ] **토큰 프로비저닝 절차** (설치 스크립트에 주입? 관리자 대시보드에서 복사?)
- [ ] DB 스키마 설계 (upsert key = `game_id`, 스냅샷 JSON 저장 방식: JSONB / 정규화 분해)
- [ ] 응답 포맷 (`{ok, server_game_id}` 수준으로 합의)
- [ ] 4xx / 5xx 에러 정책 + 재전송 정책 명세

### 9.2 v0.1 구현 범위

- [ ] `POST /api/v1/games` 엔드포인트 (인증 + upsert + 응답)
- [ ] 토큰 검증 미들웨어
- [ ] 최소 관리자 대시보드 (수신된 경기 목록 조회)
- [ ] 모니터링: 수신량·에러율 로깅

### 9.3 v0.2 이후 (후속)

- [ ] `POST /api/v1/stats` (실시간 경기 중 스탯)
- [ ] `POST /api/v1/games/{id}/clips` (presigned URL 발급)
- [ ] `GET /api/v1/teams/{id}/roster` (bkdunk → COURTVIEW 풀다운, 선수 명단 사전 설정)
- [ ] `GET /api/v1/games/{id}` (대시보드용 조회)

### 9.4 인프라

- [ ] AWS 계정·리전 (COURTVIEW 는 `us-east-1` 기존 사용. bkdunk 가 다른 리전이면 latency 감안)
- [ ] TLS 인증서 (유효한 CA 서명 필요 — self-signed 면 COURTVIEW 클라이언트가 거부)
- [ ] CORS: **불필요** (COURTVIEW 는 서버 투 서버, 브라우저 아님)

---

## 10. 타임라인 제안

| 단계 | 내용 | 예상 소요 |
|---|---|---|
| **W1** | 이 문서 리뷰 + 9.1 결정 사항 확정 | 3–5일 |
| **W2** | bkdunk: v0.1 엔드포인트 + 토큰 + 스테이징 구축 | 1–2주 |
| **W3** | COURTVIEW: 스테이징 URL/토큰으로 end-to-end 테스트 | 2–3일 |
| **W4** | 프로덕션 토큰 배포 + 자사 노트북 1–2 대 파일럿 | 1주 |
| **M2+** | v0.2 (클립 업로드, stats 실시간, 조회 API) | 점진적 |

---

## 11. COURTVIEW 측 참조 파일

bkdunk 팀이 직접 확인 가능한 소스 (저장소: `https://github.com/SPOIN-Inc/COURTVIEW_DESK`):

| 관심사 | 파일 |
|---|---|
| 전송 로직 (HTTP POST, 재시도, 타임아웃) | `api_server/services/cloud_sync_service.py` |
| 페이로드 구성 (snapshot 빌드) | `api_server/services/export_service.py` — `collect_snapshot()` |
| 경기 DTO (box_score, stats, events) | `shared/dto/game_dto.py` |
| 심판 DTO | `shared/dto/referee_dto.py` |
| 전술 DTO | `shared/dto/tactical_dto.py` |
| 피드백 DTO | `shared/dto/feedback_dto.py` |
| 미디어 DTO (클립·하이라이트) | `shared/dto/media_dto.py` |
| 저장 경로 (AppData, 큐) | `infrastructure/storage/paths.py` |

---

## 12. 연락

- COURTVIEW Desktop 측: (SPOIN Desk 팀 / Claude + 담당자)
- 이 문서 업데이트·질문: GitHub `COURTVIEW_DESK` 레포 이슈 또는 slack `#courtview-integration`

---

## 부록 A. 빠른 테스트 (bkdunk 엔드포인트 검증용)

bkdunk 팀이 엔드포인트 프로토타입 작성 후, 다음 `curl` 으로 COURTVIEW 없이 수신 테스트 가능:

```bash
curl -X POST 'https://staging-api.bkdunk.spoin.co.kr/api/v1/games' \
  -H 'Authorization: Bearer test-token-xyz' \
  -H 'Content-Type: application/json; charset=utf-8' \
  -H 'User-Agent: CourtViewDesk/1.0' \
  -d '{
    "active": true,
    "timestamp": 1776767195.749,
    "box_score": {
      "game_id": "test-game-001",
      "home_score": 78,
      "away_score": 82
    },
    "players": [],
    "teams": [],
    "referee": {},
    "tactical": {},
    "report": {},
    "scouting": {},
    "highlights": [],
    "feedback": {"items": [], "total": 0}
  }'
```

기대 응답: `200 OK` + `{"ok": true, "server_game_id": "..."}`.

이 응답이 정상적으로 돌아오면 COURTVIEW 실제 노트북과 end-to-end 테스트로 넘어갈 수 있습니다.
