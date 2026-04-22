# COURTVIEW × SPOIN Ecosystem 통합 스펙

> **버전**: v0.2 (양방향 전면 개정)
> **작성일**: 2026-04-23
> **대상 독자**: bkdunk 백엔드 개발팀 (+ 참조: SPOIN-AUTH 팀)
> **목적**: 현장 노트북 COURTVIEW Desktop 이 **SPOIN 통합 계정으로 로그인 → bkdunk 에서 대회·팀·선수 데이터 풀다운 → 로컬 분석 → 경기 결과 bkdunk 에 업로드** 하는 전체 사이클의 양측 계약 합의

---

## 0. 요약 (TL;DR)

COURTVIEW 는 **세 시스템에 걸쳐 동작**합니다:

1. **SPOIN-AUTH (spoinlabs 통합 계정)** — 로그인·토큰·라이선스·프로필. **이미 구현돼있음** (UI 의 `auth-client.js`). bkdunk 팀이 새로 만들 건 없음. SPOIN-AUTH 토큰을 bkdunk 호출 시 Authorization 헤더에 그대로 통과시키는 게 전부.
2. **bkdunk** — 경기·팀·선수 마스터 DB. **풀다운(GET)** + **업로드(POST)** 양방향 필요. 이 문서의 주 초점.
3. **COURTVIEW Desktop** — 현장 노트북. offline-first. bkdunk 로부터 사전 정보 받아 분석, 종료 시 결과 업로드.

**v0.1 MVP 에 반드시 포함돼야 할 bkdunk 엔드포인트 3개**:

| # | 엔드포인트 | 방향 | 상태 |
|---|---|---|---|
| 1 | `GET  /cloud/api/tournaments?my=true` | bkdunk → COURTVIEW | UI 가 이미 호출 중 (best-guess). 스펙 확정 필요 |
| 2 | `GET  /cloud/api/teams/{team_id}/roster` | bkdunk → COURTVIEW | 미구현. 로스터 상세 조회 |
| 3 | `POST /api/v1/games` | COURTVIEW → bkdunk | COURTVIEW 전송·재시도 완성. bkdunk 수신기 미구현 |

**이전 v0.1 스펙은 #3 만 다뤘는데, #1, #2 없이는 UI 가 비어있는 상태로 뜸** — 둘 다 v0.1 필수로 격상.

---

## 1. 3대 시스템 구조

```
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│   SPOIN-AUTH            │   │   bkdunk                │   │   COURTVIEW Desktop     │
│   (spoinlabs 통합 계정)  │   │   (경기·선수 마스터 DB)  │   │   (현장 Windows 노트북)  │
│                         │   │                         │   │                         │
│  POST /spoin/api/v1/    │   │  GET  /cloud/api/       │   │  localhost:8000 (엔진)  │
│       auth/login        │   │       tournaments       │   │  localhost:3000 (UI)    │
│  POST /spoin/api/v1/    │   │  GET  /cloud/api/       │   │                         │
│       auth/refresh      │   │       teams/{id}/       │   │  %APPDATA%\COURTVIEW\   │
│  GET  /spoin/api/v1/    │   │       roster            │   │    ├─ cloud_sync_queue\ │
│       users/me          │   │  POST /api/v1/games     │   │    ├─ games\            │
│                         │   │  POST /api/v1/stats     │   │    └─ logs\             │
│  [발급] Bearer Token    │   │                         │   │  D:\COURTVIEW_Recordings│
│                         │   │                         │   │    └─ {sess}\clips\*.mp4│
└────────────┬────────────┘   └────────────▲────────────┘   └────────────┬────────────┘
             │                             │                             │
             │ 1) 토큰 발급                 │ 2) 같은 토큰으로              │
             └─────────────────────────────┼─── Authorization: Bearer ───┘
                                           │
                                           │ (양방향 호출)
```

### 1.1 역할 경계

| 시스템 | 담당 | 이 문서 범위 |
|---|---|---|
| SPOIN-AUTH | 로그인, 세션, 리프레시, 사용자 프로필(`avatar`, `phone`, `roles`, `license`) | **참조만** (이미 구현·운영 중) |
| **bkdunk** | **대회·팀·선수·경기 일정 마스터 DB + 경기 결과 수집** | **주 초점** |
| COURTVIEW Desktop | 현장 로컬 AI 분석, offline 큐, UI | 이미 구현 (스펙 제공 측) |

### 1.2 기존 COURTVIEW UI 가 호출하는 경로

UI 코드(`templates/pages/database.html`, `static/js/auth-client.js`)에서 다음 엔드포인트를 **이미 호출 중**이나 bkdunk 측 스펙이 아직 없음 — 이 문서로 확정합니다:

- `GET /cloud/api/tournaments?my=true` ← 대회 목록 동기화 버튼(`syncFromCloud()`)
- 암묵적으로 `/cloud/api/...` prefix 를 모든 bkdunk 데이터 호출에 가정

---

## 2. 전체 데이터 흐름

```
[1] 앱 기동
    │
    ▼
[2] SPOIN 로그인 화면 (auth-guard.js 가 토큰 없으면 /login 리다이렉트)
    │
    ▼  POST /spoin/api/v1/auth/login  {email, password}
    ◀  200 {access_token, refresh_token, access_token_exp}
    │
    ▼  GET  /spoin/api/v1/users/me   (Authorization: Bearer ...)
    ◀  200 {id, name, avatar, phone, roles, license, ...}
    │  localStorage[user_profile] 저장
    │
    ▼
[3] 홈 (home.html) 렌더 — localStorage[cv_db] 비어있으면 "동기화 필요" 안내
    │
    ▼  [DB 관리] 클릭 → database.html
    │
    ▼  [클라우드 동기화] 클릭
    │
    ▼  GET /cloud/api/tournaments?my=true  (Authorization: Bearer ...)  ←── bkdunk
    ◀  200 {data: [{id, name, venue, startDate, endDate, teams: [...]}]}
    │  localStorage[cv_db] 저장
    │
    ▼
[4] 대회 선택 → 경기 선택 (또는 즉시 경기 생성) → 팀·선수 매칭
    │  (game_analysis.html 이 cv_db 기반으로 로컬 UI 구성)
    │
    ▼
[5] 경기 진행 (엔진이 영상 분석, 로컬 DB 에 기록)
    │
    ▼
[6] 경기 종료 → ExportService.collect_snapshot()
    │
    ▼  POST /api/v1/games  {snapshot}  (Authorization: Bearer ...)  ───→ bkdunk
    ◀  200 {ok, server_game_id}
    │  (네트워크 실패 시 %APPDATA%\COURTVIEW\cloud_sync_queue\ 로 큐 저장,
    │   60초 주기 워커가 재전송)
    │
    ▼
[7] 최종 점수·리포트 UI 표시
```

### 2.1 토큰 공유 전제

**SPOIN-AUTH 가 발급한 `access_token` 으로 bkdunk 를 호출** 합니다. 즉 bkdunk 는 자체 로그인 시스템이 없고, SPOIN-AUTH 의 JWT 를 검증하기만 하면 됩니다.

- SPOIN-AUTH 가 JWT 서명에 사용하는 **공개키/시크릿** 를 bkdunk 가 공유
- bkdunk 는 요청마다 JWT 서명 검증 + `exp` 확인 + `sub`(user_id) 추출
- 필요 시 `roles`, `org_id` 클레임을 권한 판단에 사용

(bkdunk 가 자체 토큰 체계를 쓰겠다면 별도 결정 — 현재는 SPOIN-AUTH 통합이 기본 가정)

---

## 3. SPOIN-AUTH 계약 (참조용, 이미 구현됨)

bkdunk 팀은 **이 섹션을 구현할 필요 없습니다** — SPOIN-AUTH 팀이 이미 운영 중. 단지 **토큰 검증 로직** 만 공유하면 됩니다.

### 3.1 로그인

```
POST {SPOIN_AUTH_URL}/spoin/api/v1/auth/login
Body:
{
  "email":    "user@example.com",
  "password": "..."
}

→ 200 OK
{
  "access_token":     "eyJ...",
  "refresh_token":    "eyJ...",
  "access_token_exp": 1776767195
}
```

### 3.2 사용자 프로필

```
GET {SPOIN_AUTH_URL}/spoin/api/v1/users/me
Headers: Authorization: Bearer {access_token}

→ 200 OK
{
  "id":      "user_uuid",
  "email":   "user@example.com",
  "name":    "홍길동",
  "avatar":  "https://.../avatar.png",
  "phone":   "010-...",
  "roles":   ["coach", "admin"],
  "license": { "plan": "pro", "valid_until": "2027-01-01" },
  "org_id":  "team-uuid-001"
}
```

### 3.3 토큰 리프레시

```
POST {SPOIN_AUTH_URL}/spoin/api/v1/auth/refresh
Body: { "refresh_token": "..." }

→ 200 OK { "access_token", "access_token_exp" }
```

### 3.4 bkdunk 쪽 토큰 검증 (의사코드)

```python
# 매 요청마다
token = request.headers["Authorization"].removeprefix("Bearer ")
claims = jwt.decode(token, SPOIN_AUTH_PUBLIC_KEY, algorithms=["RS256"])
user_id = claims["sub"]
org_id  = claims.get("org_id")
# exp 자동 검증
# 403 권한 부족이면 roles 확인
```

---

## 4. bkdunk 풀다운 API — v0.1 **필수**

COURTVIEW UI 가 실제로 호출하는 엔드포인트들. **이 세 가지가 없으면 UI 가 비어있는 상태**.

### 4.1 대회 목록 + 팀/선수/일정 (1-shot)

```
GET {BKDUNK_URL}/cloud/api/tournaments?my=true
Headers: Authorization: Bearer {access_token}
```

`?my=true` — 현재 사용자(로그인한 coach/admin)가 관리 권한을 가진 대회만.

**응답**:
```json
{
  "data": [
    {
      "id":         "tnmt-uuid-001",
      "name":       "2026 SPOIN 리그 Spring",
      "season":     "2026-Spring",
      "venue":      "잠실 실내체육관",
      "start_date": "2026-04-20",
      "end_date":   "2026-06-30",
      "teams": [
        {
          "id":        "team-uuid-101",
          "name":      "SPOIN Lakers",
          "abbr":      "SPL",
          "jersey_color": "#552583",
          "logo_url":  "https://.../lakers.png",
          "players": [
            {
              "id":            "plr-uuid-1001",
              "jersey_number": 23,
              "name":          "김선수",
              "position":      "SF",
              "height_cm":     195,
              "weight_kg":     88,
              "birth_date":    "1998-03-12",
              "photo_url":     "https://.../kim.jpg"
            }
          ]
        }
      ],
      "matches": [
        {
          "id":          "match-uuid-501",
          "scheduled_at":"2026-05-10T19:00:00+09:00",
          "home_team_id":"team-uuid-101",
          "away_team_id":"team-uuid-102",
          "venue":       "잠실 실내체육관",
          "status":      "scheduled"
        }
      ]
    }
  ],
  "meta": { "count": 3, "generated_at": "2026-04-23T10:00:00Z" }
}
```

- 대회 한 건당 팀·선수·일정까지 **nested 로 한 번에** 반환 (페이지 전환 없이 로컬 `cv_db` 로 저장)
- 선수 사진/팀 로고는 **public URL** 권장 — COURTVIEW 가 클라이언트 캐시
- 페이지네이션: 대회 수가 많으면 `?page=&size=` 추가 고려, 초기엔 미필요

### 4.2 단일 팀 로스터 조회 (세부 정보용)

```
GET {BKDUNK_URL}/cloud/api/teams/{team_id}/roster
Headers: Authorization: Bearer {access_token}
```

4.1 의 nested 로 충분하지만, 경기 직전 로스터만 **신선하게 갱신**하고 싶을 때 사용.

**응답**:
```json
{
  "data": {
    "team": { "id": "team-uuid-101", "name": "SPOIN Lakers", ... },
    "players": [ { "id": "...", "jersey_number": 23, ... }, ... ],
    "updated_at": "2026-05-09T23:55:00Z"
  }
}
```

### 4.3 단일 경기 정보 (옵션)

```
GET {BKDUNK_URL}/cloud/api/matches/{match_id}
```

예약된 경기 한 건에 대해 **시작 전 최종 확인** 용도. 4.1 로 이미 가지고 있으면 생략 가능 — **v0.2 로 미룰 수 있음**.

### 4.4 v0.2 이후 후보

- `GET /cloud/api/players/{player_id}` — 선수 히스토리·통계 조회 (스카우팅 기능 추가 시)
- `GET /cloud/api/games/{game_id}` — 내가 업로드했던 과거 경기 조회 (복기용)
- `GET /cloud/api/licenses/me` — 세부 구독 정보 (현재는 `/spoin/api/v1/users/me` 응답에 포함됨)

---

## 5. bkdunk 업로드 API — v0.1 **필수**

### 5.1 경기 결과 업로드

```
POST {BKDUNK_URL}/api/v1/games
Headers:
  Authorization: Bearer {access_token}
  Content-Type:  application/json; charset=utf-8
  User-Agent:    CourtViewDesk/1.0
```

**요청 본문** — 6.2 의 `game_result` 페이로드 (최상위 키 11 개).

**응답**:
```json
{
  "ok": true,
  "server_game_id": "srv-uuid-999",
  "received_at": "2026-05-10T21:30:02.123Z"
}
```

**HTTP 코드 정책**:

| HTTP | 의미 | COURTVIEW 동작 |
|---|---|---|
| 2xx | 수신 완료 | 큐에서 제거 |
| 401 | 토큰 만료/무효 | `auth-client.js` 가 리프레시 → 재시도 |
| 4xx | payload 오류 | 3회 재시도 후 큐 저장 → bkdunk 로그 확인 필요 |
| 5xx | 서버 에러 | 3회 재시도 → 큐 → 60초 주기 재드레인 |
| 타임아웃 | 네트워크 | 동일 (큐) |

### 5.2 Idempotency

네트워크 타임아웃 시 COURTVIEW 가 같은 payload 재전송. bkdunk 는 **`payload.box_score.game_id` 를 고유 키로 upsert**:

```sql
INSERT INTO games (game_id, ...) VALUES (...)
ON CONFLICT (game_id) DO UPDATE SET ...
```

`game_id` 는 노트북에서 생성된 UUID 로 전역 unique.

### 5.3 실시간 스탯 (옵션, v0.2)

```
POST {BKDUNK_URL}/api/v1/stats
```

경기 중 주기적 박스스코어 푸시. **v0.1 에서는 구현 불필요**. 현재 COURTVIEW 도 호출하지 않음.

---

## 6. 데이터 스키마

### 6.1 풀다운 핵심 엔티티 (Tournament / Team / Player / Match)

4.1 응답이 사실상 스키마. 간결 요약:

| 엔티티 | 필수 필드 | 옵션 필드 |
|---|---|---|
| Tournament | `id`, `name`, `season`, `start_date`, `end_date` | `venue`, `description` |
| Team | `id`, `name`, `abbr` | `jersey_color`, `logo_url`, `head_coach` |
| Player | `id`, `jersey_number`, `name` | `position`, `height_cm`, `weight_kg`, `birth_date`, `photo_url` |
| Match | `id`, `scheduled_at`, `home_team_id`, `away_team_id` | `venue`, `status` |

COURTVIEW 측 대응 DTO: `shared/dto/game_dto.py` 의 `TeamInfo`, `PlayerInfo` (match/tournament 은 UI-only, 엔진 DTO 없음).

### 6.2 업로드 페이로드 (`game_result`)

경기 종료 시 `ExportService.collect_snapshot()` 이 만드는 최상위 11 키:

```json
{
  "active": true,
  "timestamp": 1776767195.749,

  "box_score":  {...},   // GameStats: game_id, home_team, away_team, scores, events
  "players":    [...],   // PlayerStats[]: 선수별 통계
  "teams":      [...],   // TeamStats[]:   팀별 통계
  "referee":    {...},   // GameRefereeReport: violations, fouls, corrections
  "tactical":   {...},   // TacticalReport: formations, plays, defense_style
  "report":     {...},   // 매니저용 종합 리포트
  "scouting":   {...},   // 상대팀 스카우팅 관점
  "highlights": [...],   // HighlightReel[]: 클립 메타 (clip_url은 로컬 경로 — 7절 참조)
  "feedback":   { "items": [...], "total": N }
}
```

각 sub-object 는 pydantic `.model_dump()` — **null 필드도 기본값 그대로 포함** 될 수 있어 bkdunk DB 는 nullable 로 설계.

**핵심 식별자**: `box_score.game_id` = 노트북에서 생성한 UUID. Idempotency key.

**예상 크기**: 0.5 – 3 MB / 경기.

각 DTO 의 전체 필드는 참조 파일 (11 장) 을 보면 됨.

### 6.3 최소 예시

```json
{
  "active": true,
  "timestamp": 1776767195.749,
  "box_score": {
    "game_id":    "a1b2c3d4-e5f6-...",
    "home_team":  { "team_id": "team-uuid-101", "team_name": "Lakers", "is_home": true },
    "away_team":  { "team_id": "team-uuid-102", "team_name": "Bulls",  "is_home": false },
    "home_score": 78,
    "away_score": 82,
    "current_quarter": 4,
    "events": []
  },
  "players": [], "teams": [],
  "referee": {"violations":[], "fouls":[]},
  "tactical": {}, "report": {}, "scouting": {},
  "highlights": [],
  "feedback": { "items": [], "total": 0 }
}
```

---

## 7. 미디어 (영상 클립) 업로드

**v0.1 에서는 JSON 스냅샷만 전송**. MP4 는 노트북 로컬(`D:\COURTVIEW_Recordings\{session}\clips\*.mp4`).

`HighlightReel.clip_url` 는 로컬 파일 경로로 채워 보냄 → bkdunk 는 "파일은 아직 없음" 으로 인지.

### 7.1 v0.2 안 (권장: Presigned URL)

```
[업로드 단계]
POST /api/v1/games  {snapshot + pending_clips: [{clip_id, size_bytes}...]}
  → 200 { ok, server_game_id,
          upload_urls: [{clip_id, put_url, expires_at}, ...] }

[클립 단계 — COURTVIEW → S3 직접]
PUT {put_url}   <mp4 binary>

[완료 통지 — 옵션]
POST /api/v1/games/{game_id}/clips/{clip_id}/complete
```

bkdunk 자체 S3 버킷(예: `s3://spoin-courtview-clips/`) 에 발급. COURTVIEW 는 이미 `courtview-releases` S3 쓰는 경험 있어 구현 빠름.

---

## 8. 오프라인·캐시 정책

### 8.1 풀다운 캐시 (로컬 `cv_db`)

UI 측 `database.html` 의 `syncFromCloud()` 가 `/cloud/api/tournaments?my=true` 호출 후 결과를 **localStorage `cv_db`** 에 저장. 이후 현장에서 인터넷 없어도 이 캐시로 경기 진행 가능.

**갱신 정책 (양측 합의 필요)**:
- [ ] **수동 (현재 설계)** — 사용자가 [클라우드 동기화] 클릭 시에만 풀다운. 단순·안전.
- [ ] **자동 + TTL** — 마지막 동기화 후 N 시간 지나면 자동 갱신. 신선도 ↑, 오프라인 중엔 실패 무시.
- [ ] **변경 알림** — bkdunk 가 WebSocket/SSE 로 변경 이벤트 푸시. 복잡.

**추천: 수동 + 앱 시작 시 자동 1회** (백그라운드, 실패해도 캐시로 fallback).

### 8.2 업로드 큐 (오프라인 → 온라인)

COURTVIEW 측 이미 구현:
- HTTP POST 3회 재시도 (지수백오프 1s, 2s, 4s)
- 실패 → `%APPDATA%\COURTVIEW\cloud_sync_queue\{ts}_{kind}.json`
- 60초 주기 워커가 큐 드레인
- 순서 보장 (한 항목 실패 시 이후 중단)

bkdunk 입장에서는 같은 `game_id` 로 여러 번 수신 가능성 → **Idempotency (5.2)** 필수.

---

## 9. bkdunk 결정 체크리스트 (v0.1 MVP)

### 9.1 즉시 결정

- [ ] **프로덕션 base URL** 확정 (예: `https://api.bkdunk.spoin.co.kr`)
- [ ] **스테이징 base URL** + **테스트 토큰** 발급 절차
- [ ] **SPOIN-AUTH JWT 검증 방식** 확정 (공개키 공유 vs bkdunk 자체 토큰 — 기본 가정: 공개키 공유)
- [ ] **권한 모델** — `roles`/`org_id` 기반 대회 접근 제어 (coach/admin/viewer 등)
- [ ] **nullable 필드 정책** — payload 내 `null` 허용 vs 필수 필드 엄격 검증
- [ ] **응답 포맷** — `{data: [...], meta: {...}}` 래핑 방식 합의 (4.1 예시 따를지)
- [ ] **풀다운 캐시 갱신** 정책 (8.1 3안 중 선택)

### 9.2 v0.1 구현 범위 (bkdunk 쪽)

- [ ] `GET /cloud/api/tournaments?my=true` — 4.1 스키마
- [ ] `GET /cloud/api/teams/{team_id}/roster` — 4.2 스키마
- [ ] `POST /api/v1/games` — 5.1 스키마 (Idempotency upsert)
- [ ] JWT 검증 미들웨어 (SPOIN-AUTH 토큰)
- [ ] 관리자 대시보드 최소 (수신 경기 목록)
- [ ] 수신량·에러율 모니터링

### 9.3 v0.2 이후

- [ ] `GET /cloud/api/matches/{match_id}`
- [ ] `GET /cloud/api/players/{player_id}` (스카우팅)
- [ ] `GET /cloud/api/games/{game_id}` (COURTVIEW 에서 과거 경기 조회)
- [ ] `POST /api/v1/stats` (실시간 박스스코어)
- [ ] 클립 MP4 업로드 (Presigned URL — 7.1)

### 9.4 인프라

- [ ] AWS 리전 (COURTVIEW 는 `us-east-1`)
- [ ] 유효한 TLS 인증서 (self-signed 금지)
- [ ] CORS: **불필요** (COURTVIEW 는 서버 투 서버; UI 호출은 localhost: 3000 → localhost:8000 proxy 경유)

### 9.5 bkdunk → COURTVIEW 가 받아야 할 산출물

#### 9.5.1 값 (환경변수 · 검증 자료)

- [ ] **프로덕션 base URL** (`BKDUNK_URL`)
- [ ] **스테이징 base URL** + 테스트용 **스테이징 SPOIN-AUTH** 사용자 계정
- [ ] **JWT 검증 공개키** (SPOIN-AUTH 에서 받아서 bkdunk 가 공유)

COURTVIEW 환경변수 (둘 중 하나 방식):
```
# 방식 A: 런타임에 SPOIN-AUTH 토큰을 bkdunk 에도 그대로 사용
COURTVIEW_CLOUD_URL=https://api.bkdunk.spoin.co.kr
COURTVIEW_CLOUD_ENABLED=1
# COURTVIEW_CLOUD_TOKEN 은 auth-client 가 SPOIN 로그인 후 set_token() 으로 주입

# 방식 B: bkdunk 전용 토큰을 프로비저닝
COURTVIEW_CLOUD_URL=...
COURTVIEW_CLOUD_TOKEN=...
```

#### 9.5.2 API 명세

- [ ] 4.1, 4.2, 5.1 **성공 응답 샘플** (실제 body)
- [ ] 401/4xx/5xx **실패 응답 샘플 + 에러 코드 리스트** (`E_UNAUTHORIZED`, `E_INVALID_GAME_ID`, `E_TOKEN_EXPIRED`, `E_PAYLOAD_TOO_LARGE` 등)
- [ ] 최대 payload 크기 한도 (예상 ~3 MB)
- [ ] 응답 SLO (p95 응답시간 기대치)
- [ ] (선택) OpenAPI/Swagger 스펙 URL

#### 9.5.3 저장 확인·디버깅 수단

- [ ] 관리자 대시보드 URL + 계정 또는 `GET /cloud/api/games/{id}` 조회 엔드포인트
- [ ] 로그 접근 방법 (CloudWatch/Datadog URL + 공유 권한, 또는 담당자 경유)
- [ ] 토큰 revoke 절차 (유출·퇴사 시) — SPOIN-AUTH 에서 revoke 하면 bkdunk 도 즉시 검증 실패해야

#### 9.5.4 장애·운영

- [ ] 운영 담당자 연락처 / on-call
- [ ] 배포 공지 채널 (bkdunk 배포로 인한 일시 장애 사전 공지)
- [ ] (선택) SLA 문서

#### 9.5.5 E2E 테스트 전환 종료 조건

1. 스테이징 URL + SPOIN 테스트 계정 + JWT 검증 공개키 공유 완료
2. `curl` (부록 A) 로 스테이징 `/cloud/api/tournaments` 200 응답 + 4.1 스키마 일치
3. `curl` 로 스테이징 `/api/v1/games` 테스트 payload 200 + 저장 확인
4. 응답 샘플 (9.5.2) 실제 바디가 문서와 일치

충족되면 COURTVIEW 실제 노트북 → 스테이징 전체 사이클 테스트 → 프로덕션 배포.

---

## 10. 타임라인 제안

| 단계 | 내용 | 예상 |
|---|---|---|
| **W1** | 이 문서 리뷰 + 9.1 결정 사항 확정 (특히 JWT 검증 방식) | 3–5일 |
| **W2** | bkdunk: 풀다운 2개 + 업로드 1개 엔드포인트 + 토큰 검증 + 스테이징 배포 | 1–2주 |
| **W3** | COURTVIEW: 스테이징 URL/토큰으로 end-to-end (로그인 → 풀다운 → 경기 → 업로드) | 3–5일 |
| **W4** | 프로덕션 배포 + 자사 노트북 1–2대 파일럿 | 1주 |
| **M2+** | v0.2 (클립 업로드, 실시간 stats, 과거 조회 등) | 점진적 |

---

## 11. COURTVIEW 측 참조 파일

저장소: `https://github.com/SPOIN-Inc/COURTVIEW_DESK`, `https://github.com/SPOIN-Inc/courtview_ui`

| 관심사 | 파일 |
|---|---|
| 업로드·큐·재시도 | `api_server/services/cloud_sync_service.py` |
| 스냅샷 빌드 (payload 생성) | `api_server/services/export_service.py` — `collect_snapshot()` |
| UI 인증 클라이언트 | `courtview_ui / static/js/auth-client.js`, `auth-guard.js` |
| UI 풀다운 호출 | `courtview_ui / templates/pages/database.html` — `syncFromCloud()` |
| UI 홈·경기 분석 | `courtview_ui / templates/pages/{home,database,game_analysis,scoreboard,referee}.html` |
| 경기·팀·선수 DTO | `shared/dto/game_dto.py`, `media_dto.py`, `referee_dto.py`, `tactical_dto.py`, `feedback_dto.py` |
| 로컬 스토리지 경로 | `infrastructure/storage/paths.py` |
| 라이선스(하드웨어 기반) | `core_foundation/security/license_validator.py` — SPOIN-AUTH 와는 분리 |

---

## 12. 연락

- COURTVIEW Desktop 팀: (SPOIN Desk 팀 / 담당 @)
- SPOIN-AUTH 팀: (참조 연락처 필요 시)
- 이 문서: GitHub `COURTVIEW_DESK/docs/INTEGRATION_BKDUNK.md` PR/이슈

---

## 부록 A. 빠른 검증 (curl)

### A.1 풀다운 (스테이징)

```bash
# 1. SPOIN 로그인 (테스트 계정)
TOKEN=$(curl -s -X POST 'https://staging-auth.spoinlabs.com/spoin/api/v1/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@spoin.co","password":"..."}' \
  | jq -r '.access_token')

# 2. 내 대회 목록
curl -s -H "Authorization: Bearer $TOKEN" \
  'https://staging-api.bkdunk.spoin.co.kr/cloud/api/tournaments?my=true' | jq .

# 3. 팀 로스터
curl -s -H "Authorization: Bearer $TOKEN" \
  'https://staging-api.bkdunk.spoin.co.kr/cloud/api/teams/team-uuid-101/roster' | jq .
```

### A.2 업로드 (스테이징)

```bash
curl -X POST 'https://staging-api.bkdunk.spoin.co.kr/api/v1/games' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json; charset=utf-8' \
  -H 'User-Agent: CourtViewDesk/1.0' \
  -d '{
    "active": true,
    "timestamp": 1776767195.749,
    "box_score": {
      "game_id": "test-game-001",
      "home_score": 78, "away_score": 82
    },
    "players": [], "teams": [],
    "referee": {}, "tactical": {}, "report": {}, "scouting": {},
    "highlights": [],
    "feedback": {"items": [], "total": 0}
  }'
```

기대 응답: `200 OK` + `{"ok": true, "server_game_id": "..."}`.

두 curl 모두 통과하면 bkdunk end-to-end 준비 완료 → COURTVIEW 노트북 테스트 단계로.
