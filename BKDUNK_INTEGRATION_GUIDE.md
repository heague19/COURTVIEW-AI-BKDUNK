# BKDUNK API 통합 가이드 (외부 개발자용)

> **목적**: 외부 웹사이트에서 SPOIN-AUTH로 로그인한 사용자에게 BKDUNK의 대회 일정을 보여주기.
>
> **핵심 결론 (먼저)**:
> - **BKDUNK 대회 일정 API는 공개 API라 JWT 토큰을 보내지 않아도 호출됩니다.**
> - 필요한 것은 **CORS 화이트리스트에 외부 사이트 도메인 추가** 한 줄뿐.
> - SPOIN 로그인은 외부 사이트의 자체 사용자 인증 용도로만 쓰고, BKDUNK 호출과는 분리해서 운용하면 됩니다.
> - JWT 키 동기화나 토큰 변환 같은 작업은 이 시나리오에서 **불필요**합니다.

---

## 0. 시스템 구성 한눈에

```
┌──────────────────────────────────────────────────┐
│  외부 웹사이트 (당신이 만드는 사이트)              │
│  ├─ 사용자 로그인 → SPOIN-AUTH 호출                │
│  └─ 대회 일정 표시 → BKDUNK API 호출               │
└──────────────────────────────────────────────────┘
            │                              │
            │ ① 로그인                      │ ② 일정 조회
            ▼                              ▼
┌───────────────────────┐    ┌─────────────────────────┐
│  SPOIN-AUTH-SERVICE   │    │  BKDUNK Backend         │
│  auth.spoinlabs.com   │    │  api.bkdunk.com         │
│  (FastAPI / Python)   │    │  (Express / Node.js)    │
│                       │    │                         │
│  - 사용자 인증         │    │  - 대회 일정 API (공개)  │
│  - JWT 토큰 발급       │    │  - 코트, 게시글 등       │
│  - SSO Provider       │    │  - 자체 JWT 검증 (별개)  │
└───────────────────────┘    └─────────────────────────┘
```

두 서비스는 별도의 EC2에서 운영되며 별도의 DB와 별도의 JWT 키를 가집니다.

---

## 1. 시나리오: 일정 조회는 JWT가 필요 없다

### BKDUNK 대회 일정 라우터 코드

`bkdunk-backend/routes/tournaments.js`:

```js
/**
 * 사용자용 Tournament 조회 라우터.
 * - GET /api/tournaments       — 목록 (status 필터 지원)
 * - GET /api/tournaments/:id   — 상세
 *
 * 인증 불필요 (공개 페이지).   ← ★
 */

const express = require('express');
const router = express.Router();
const { Op } = require('sequelize');
const { Event, Club } = require('../models');

// @route   GET /api/tournaments
// @desc    공개 대회 목록
// @access  Public                                     ← ★ Public
router.get(
  '/',
  asyncHandler(async (req, res) => {
    const { clubId, limit = 50 } = req.query;
    // ... DB 조회 후 응답
  })
);
```

`protect`(JWT 검증) 미들웨어가 **붙어 있지 않습니다**. 즉:

```bash
# 토큰 없이 호출
$ curl https://api.bkdunk.com/api/tournaments
HTTP 200 ✓ (정상 응답)

# 임의의 잘못된 토큰을 보내도
$ curl https://api.bkdunk.com/api/tournaments -H "Authorization: Bearer xxx"
HTTP 200 ✓ (헤더 무시됨)
```

**JWT 키 동기화나 SPOIN 토큰 변환 같은 작업은 필요 없습니다.**

---

## 2. 진짜 막힐 수 있는 지점: CORS

`bkdunk-backend/server.js`의 CORS 설정:

```js
const parseAllowedOrigins = () => {
  const defaults = process.env.NODE_ENV === 'production'
    ? [
        'https://courtin.co.kr',
        'https://www.courtin.co.kr',
        'https://courtin-adult.vercel.app'
      ]
    : [
        'http://localhost:3003',
        'http://localhost:3004',
        'http://localhost:3000'
      ];

  // 환경변수에서 추가 허용 도메인
  const fromEnv = (process.env.ALLOWED_ORIGINS || '')
    .split(',').map(o => o.trim()).filter(Boolean);

  const frontendUrl = process.env.FRONTEND_URL;  // = 'https://bkdunk.com'

  return [...new Set([...defaults, ...fromEnv, frontendUrl].filter(Boolean))];
};

const corsOptions = {
  origin: (origin, callback) => {
    if (!origin) return callback(null, true);            // 서버 간 호출은 통과
    if (allowedOrigins.includes(origin)) {
      return callback(null, true);
    }
    logger.warn('CORS rejected origin', { origin });
    return callback(new Error(`CORS: origin ${origin} not allowed`));
  },
  credentials: true,
};
app.use(cors(corsOptions));
```

### 현재 운영 EC2의 허용 도메인
```
https://courtin.co.kr
https://www.courtin.co.kr
https://courtin-adult.vercel.app
https://bkdunk.com
```

### 외부 사이트가 브라우저에서 직접 호출하면
- 등록 안 된 origin → **CORS 에러로 차단** (응답은 성공해도 브라우저가 막음)
- 콘솔에 `Access to fetch at ... from origin '...' has been blocked by CORS policy` 떠요

### 해결 방법
운영자(BKDUNK 측)가 EC2 환경변수에 외부 사이트 도메인 추가:
```bash
# /home/ubuntu/courtin-backend/.env
ALLOWED_ORIGINS=https://your-site.com,https://staging.your-site.com
```
PM2 reload 후 적용.

→ **외부 개발자가 할 일은 BKDUNK 측에 자기 사이트 도메인을 알려주는 것뿐.**

---

## 3. 호출 방법 (외부 사이트가 실제로 작성할 코드)

### 3-1. 클라이언트 사이드 (가장 단순)

```ts
// 대회 목록
async function getTournaments() {
  const res = await fetch('https://api.bkdunk.com/api/tournaments');
  if (!res.ok) throw new Error('failed');
  const json = await res.json();
  return json.data;  // 대회 배열
}

// 특정 대회 상세
async function getTournament(id: string) {
  const res = await fetch(`https://api.bkdunk.com/api/tournaments/${id}`);
  return (await res.json()).data;
}

// 사용 예 (React)
function TournamentList() {
  const [tournaments, setTournaments] = useState([]);
  useEffect(() => {
    getTournaments().then(setTournaments);
  }, []);
  return (
    <ul>
      {tournaments.map(t => (
        <li key={t.id}>
          {t.name} — {new Date(t.startDate).toLocaleDateString()} @ {t.venue}
        </li>
      ))}
    </ul>
  );
}
```

CORS 화이트리스트 등록만 되면 끝.

### 3-2. 서버 사이드 프록시 (권장 — 캐싱과 안정성 면에서 유리)

외부 사이트의 백엔드가 BKDUNK를 호출하고, 외부 사이트의 프론트는 자기 백엔드만 호출:

```ts
// 외부 사이트의 Express/Next API
import axios from 'axios';

let cache: { data: any; ts: number } | null = null;
const CACHE_TTL_MS = 5 * 60 * 1000;  // 5분

export async function GET() {
  if (cache && Date.now() - cache.ts < CACHE_TTL_MS) {
    return Response.json({ data: cache.data, cached: true });
  }
  const r = await axios.get('https://api.bkdunk.com/api/tournaments', {
    timeout: 10_000,
  });
  cache = { data: r.data.data, ts: Date.now() };
  return Response.json({ data: cache.data, cached: false });
}
```

장점:
- CORS 무관 (서버 간 호출은 origin 헤더 없음 → BKDUNK가 통과시킴)
- BKDUNK API 일시 장애 시 외부 사이트가 직접 영향 안 받음 (캐시로 버팀)
- BKDUNK API URL을 클라이언트에 노출 안 함

---

## 4. 응답 구조 (그대로 사용 가능)

### `GET /api/tournaments`

쿼리 파라미터:
| 이름 | 타입 | 기본 | 설명 |
|------|------|------|------|
| `clubId` | UUID | (전체) | 특정 코트가 호스트한 대회만 |
| `limit` | number | 50 | 최대 100 |

응답:
```json
{
  "success": true,
  "data": [
    {
      "id": "11111111-...",
      "name": "강남구청장배 대회",
      "description": "...",
      "startDate": "2025-09-15T00:00:00.000Z",
      "endDate": null,
      "venue": "강남구 체육관",
      "maxTeams": 24,
      "currentTeams": 0,
      "entryFee": 0,
      "notes": "상금: 우승 100만원\n규정: 3vs3",
      "hostClubId": "uuid-...",
      "hostClubName": "SPOIN",
      "coverImage": null,
      "category": "official",
      "format": "league",
      "status": "completed",
      "createdAt": "2025-...",
      "updatedAt": "2025-..."
    }
  ]
}
```

`status` enum:
- `open` — 시작일 전 (모집 중)
- `ongoing` — 시작일 ≤ 현재 ≤ 종료일
- `completed` — 종료일 지남

### `GET /api/tournaments/:id`

응답: 위 객체 1개를 `data`에 직접 (`{ success, data: {...} }`).

404일 경우:
```json
{
  "success": false,
  "message": "대회를 찾을 수 없습니다."
}
```

---

## 5. SPOIN-AUTH는 외부 사이트의 자체 인증 용도로만

외부 사이트가 사용자 식별이 필요하다면 SPOIN-AUTH로 로그인시키되, **BKDUNK 호출과는 분리**:

```
[ 외부 사이트의 흐름 ]

① 사용자 로그인:
   POST https://auth.spoinlabs.com/api/v1/auth/login
   Body: { username, password }
   →  { access_token, refresh_token, auth_user_id, email, ... }
   외부 사이트가 access_token 을 자기 localStorage 또는 세션에 저장

② "로그인된 사용자에게만 일정 보여주기" 같은 정책:
   if (!localStorage.getItem('access_token')) {
     showLoginPrompt();  // 외부 사이트의 로그인 게이트
     return;
   }

③ 일정 조회 (BKDUNK 공개 API):
   fetch('https://api.bkdunk.com/api/tournaments')   // 토큰 안 보냄
   .then(r => r.json())
   .then(({ data }) => render(data));
```

**핵심**: SPOIN 토큰을 BKDUNK로 그대로 보내도 무시되고 통과합니다 (BKDUNK는 검증 안 함). 그러나 보낼 필요도 없어요. 외부 사이트의 인증과 BKDUNK 호출은 직교합니다.

### SPOIN-AUTH 로그인 엔드포인트 요약

```
POST https://auth.spoinlabs.com/api/v1/auth/login
Body (form-urlencoded 또는 JSON):
  username: 이메일
  password: 비밀번호

응답:
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 3600,
  "auth_user_id": "uuid",
  "email": "...",
  "name": "...",
  "nickname": "...",
  "display_name": "...",
  "roles": [...]
}
```

토큰 만료 시:
```
POST https://auth.spoinlabs.com/api/v1/auth/refresh
Body: { "refresh_token": "..." }
```

---

## 6. (참고) BKDUNK가 인증을 요구한다면 어떻게 됐을까

만약 미래에 BKDUNK에 "로그인한 사용자만 볼 수 있는 일정"이 생겨서 인증이 필요해지면 — 이때는 추가 작업이 필요합니다. **현재는 해당 없음**이지만 참고용으로:

### 6-1. 현재 BKDUNK의 JWT 검증 로직 (`bkdunk-backend/middleware/auth.js`)

```js
const decoded = jwt.verify(token, process.env.JWT_SECRET);

// SPOIN-AUTH 토큰 (sub 필드) vs 자체 토큰 (id 필드) 분기
if (decoded.sub && !decoded.id) {
  // SPOIN-AUTH 토큰: 로컬 User 자동 생성/매핑
  let localUser = await User.findByPk(decoded.sub);
  if (!localUser) {
    localUser = await User.create({
      id: decoded.sub,            // SPOIN UnifiedUser.id 를 PK 로
      email: decoded.email,
      name: decoded.name,
      ...
    });
  }
  req.user = localUser;
} else {
  // 자체 발급 토큰
  req.user = await User.findByPk(decoded.id);
}
```

**문제**: `process.env.JWT_SECRET` 한 개로 두 종류 토큰을 검증 → SPOIN과 BKDUNK의 키가 같아야 동작.

### 6-2. 현재 두 서버의 JWT 키 상태 (2026-05-04 기준)

| 서버 | 환경변수 | 알고리즘 | 길이 | 앞 16자 |
|------|----------|----------|------|---------|
| bkdunk-backend | `JWT_SECRET` | HS256 | 128 | `bdbb961625a22d6b` |
| SPOIN-AUTH | `JWT_SECRET_KEY` | HS256 | 43 | `spoin-jwt-secret` |

→ **두 키가 다름 → SPOIN 토큰은 BKDUNK 보호 라우트에서 검증 실패**.

### 6-3. 인증 필요한 BKDUNK 라우트를 외부 앱이 호출하려면

옵션 1) **두 서버 JWT 키 통일**: 양쪽 동시 회전 + 모든 사용자 재로그인. 가장 단순하지만 영향 큼.

옵션 2) **bkdunk-backend가 SPOIN 키를 별도 환경변수로 보관**:
```js
// 코드 수정 필요
let decoded;
try {
  decoded = jwt.verify(token, process.env.JWT_SECRET);  // 자체 토큰
} catch {
  decoded = jwt.verify(token, process.env.SPOIN_AUTH_JWT_SECRET);  // SPOIN 토큰
}
```

옵션 3) **SPOIN-AUTH의 `/token/verify` 엔드포인트 위임**: bkdunk-backend가 받은 토큰을 SPOIN에 검증 요청. 키 노출 없이 안전. 단 매 요청마다 네트워크 호출 1회 추가.

**현재 시나리오(공개 일정 조회)에서는 위 셋 중 무엇도 필요 없음.**

---

## 7. 외부 개발자에게 요청드리는 정보 (BKDUNK 측 운영자에게 전달)

CORS 화이트리스트 등록을 위해 다음을 알려주세요:

1. **외부 사이트의 운영 도메인** (예: `https://my-site.com`)
2. **스테이징/개발 도메인** (있다면, 예: `https://staging.my-site.com`, `http://localhost:3000`)
3. **호출 빈도 예상** (분당/시간당) — 필요시 캐싱/레이트 리밋 조정
4. **호출 방식** (브라우저 직접 / 서버 프록시) — CORS 필요 여부 판단

운영자가 EC2에서:
```bash
ssh -i basketball-academy-key.pem ubuntu@107.22.120.161
echo "ALLOWED_ORIGINS=https://my-site.com,http://localhost:3000" >> ~/courtin-backend/.env
pm2 reload courtin-backend --update-env
# 또는 기존 ALLOWED_ORIGINS 가 있으면 콤마로 추가
```

---

## 8. 빠른 시작 체크리스트 (외부 개발자용)

- [ ] 외부 사이트 도메인을 BKDUNK 운영자에게 전달
- [ ] BKDUNK 운영자가 CORS 등록 + PM2 reload 완료 확인
- [ ] 브라우저에서 `fetch('https://api.bkdunk.com/api/tournaments')` 테스트
  - DevTools Network 탭에서 200 + CORS preflight 통과 확인
- [ ] (권장) 외부 사이트의 백엔드에서 호출 + 5분 캐싱 구현
- [ ] SPOIN-AUTH 로그인은 외부 사이트의 자체 게이트로 별도 운용
- [ ] BKDUNK 호출 시 토큰 첨부 안 하기 — 첨부해도 무시되지만 불필요한 헤더

---

## 9. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 콘솔에 CORS 에러 | 외부 사이트 origin 미등록 | BKDUNK 운영자에게 `ALLOWED_ORIGINS` 추가 요청 |
| `HTTP 502 Bad Gateway` | bkdunk-backend 다운/재시작 중 | 잠시 후 재시도. 외부 사이트는 캐시 사용 권장 |
| `HTTP 429 Too Many Requests` | rate limit 초과 | 호출 빈도 줄이거나 서버 사이드 캐싱 도입 |
| 응답이 `{ success: false }` | 잘못된 쿼리 파라미터 | `clubId` UUID 형식 확인, `limit ≤ 100` |
| `data` 배열이 비어 있음 | 해당 조건의 대회 없음 | 정상. status 필터 등 점검 |

---

## 10. 빠른 참조 (Quick Reference)

| 항목 | 값 |
|------|---|
| **BKDUNK API base URL** | `https://api.bkdunk.com` |
| **SPOIN-AUTH base URL** | `https://auth.spoinlabs.com/api/v1` |
| **대회 목록** | `GET /api/tournaments` (Public) |
| **대회 상세** | `GET /api/tournaments/:id` (Public) |
| **SPOIN 로그인** | `POST /auth/login` (form: username, password) |
| **SPOIN 갱신** | `POST /auth/refresh` (json: { refresh_token }) |
| **JWT 필요 여부 (일정 조회)** | ❌ |
| **CORS 화이트리스트 등록 필요** | ✅ (외부 사이트 도메인) |

---

## 11. 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-05-04 | 초판. 일정 조회 시나리오 기준. JWT 키 현황 + CORS 정책 + 호출 예제 정리. |

---

**문의**: BKDUNK 운영 측 접근 권한이 필요한 작업(CORS 등록, 라우트 추가, 인증 정책 변경)은 BKDUNK 운영자(spoinlabs@gmail.com)에게 직접 요청해주세요.
