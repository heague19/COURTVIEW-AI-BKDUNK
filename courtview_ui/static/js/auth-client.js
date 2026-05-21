/**
 * COURTVIEW 인증 클라이언트
 *
 * - authFetch(input, init): fetch 래퍼 — Authorization 자동 부착 + 401 시 자동 리프레시 + 재시도
 * - refreshAccessToken(): 수동 호출 가능
 * - logout(): 로컬 토큰 정리 + SPOIN logout 호출 + 로그인 복귀
 *
 * 의존: localStorage 에 access_token / refresh_token / access_token_exp 이 있어야 함 (login.html 저장).
 * 적용 범위: 모든 fetch 를 authFetch 로 감싸면 refresh 자동화 됨. api.js 호출도 authFetch 로 교체 가능.
 *
 * 단일 플라이트 보장: 동시에 여러 요청이 401 을 받아도 refresh 는 1회만 수행 (Promise 공유).
 */
(function () {
    const TOKEN_KEY = 'access_token';
    const REFRESH_KEY = 'refresh_token';
    const EXP_KEY = 'access_token_exp';
    // 만료 N 초 전에 미리 리프레시 (클럭 스큐 방어)
    const REFRESH_EARLY_SEC = 30;

    let _refreshPromise = null;  // 진행 중인 refresh 공유

    function getToken()        { return localStorage.getItem(TOKEN_KEY); }
    function getRefreshToken() { return localStorage.getItem(REFRESH_KEY); }
    function getExpAt()        { return parseInt(localStorage.getItem(EXP_KEY) || '0', 10); }

    function clearTokens() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_KEY);
        localStorage.removeItem(EXP_KEY);
    }

    function redirectToLogin() {
        // 현재 경로 기억 → 로그인 후 복귀
        const path = window.location.pathname + window.location.search;
        if (window.location.pathname !== '/') {
            window.location.replace('/?next=' + encodeURIComponent(path));
        }
    }

    function saveTokens(access, refresh, expiresInSec) {
        if (access) localStorage.setItem(TOKEN_KEY, access);
        if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
        if (expiresInSec) {
            const expAt = Date.now() + (Number(expiresInSec) * 1000);
            localStorage.setItem(EXP_KEY, String(expAt));
        }
    }

    /**
     * Access Token 리프레시.
     * SPOIN-AUTH: POST /api/v1/auth/refresh { refresh_token } → ApiResponse<TokenResponse>
     *
     * @returns {Promise<string|null>} 새 access_token (실패 시 null)
     */
    function refreshAccessToken() {
        if (_refreshPromise) return _refreshPromise;

        const rt = getRefreshToken();
        if (!rt) return Promise.resolve(null);

        _refreshPromise = (async () => {
            try {
                const resp = await fetch('/spoin/api/v1/auth/refresh', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: rt }),
                });
                if (!resp.ok) {
                    console.warn('[auth] refresh 실패 (status=' + resp.status + ') → 로그아웃');
                    clearTokens();
                    return null;
                }
                const body = await resp.json();
                const d = body?.data || body;
                if (!d?.access_token) {
                    console.warn('[auth] refresh 응답에 access_token 없음');
                    clearTokens();
                    return null;
                }
                // SPOIN 이 refresh 도 함께 갱신할 수 있으므로 둘 다 저장
                saveTokens(d.access_token, d.refresh_token, d.expires_in);
                console.log('[auth] 토큰 리프레시 성공');
                return d.access_token;
            } catch (e) {
                console.error('[auth] refresh 네트워크 오류:', e);
                return null;
            } finally {
                _refreshPromise = null;
            }
        })();

        return _refreshPromise;
    }

    /**
     * Authorization 헤더를 자동 부착하고 401 시 refresh 후 재시도하는 fetch.
     *
     * @param {string|Request} input
     * @param {RequestInit} [init]
     * @returns {Promise<Response>}
     */
    async function authFetch(input, init = {}) {
        // 요청 직전 만료 임박이면 선제 refresh (401 대기 없이)
        const expAt = getExpAt();
        if (expAt > 0 && (expAt - Date.now()) < (REFRESH_EARLY_SEC * 1000)) {
            await refreshAccessToken();
        }

        const doRequest = async () => {
            const headers = new Headers(init.headers || {});
            const token = getToken();
            if (token && !headers.has('Authorization')) {
                headers.set('Authorization', 'Bearer ' + token);
            }
            return fetch(input, { ...init, headers });
        };

        let resp = await doRequest();

        // 401 → refresh 1회 → 재시도
        if (resp.status === 401) {
            const newToken = await refreshAccessToken();
            if (!newToken) {
                // refresh 실패 → 로그인으로
                redirectToLogin();
                return resp;
            }
            resp = await doRequest();
            // 재시도도 401 이면 포기
            if (resp.status === 401) {
                clearTokens();
                redirectToLogin();
            }
        }
        return resp;
    }

    async function logout() {
        const token = getToken();
        try {
            if (token) {
                await fetch('/spoin/api/v1/auth/logout', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token },
                });
            }
        } catch { /* 서버 연결 실패해도 로컬은 정리 */ }
        clearTokens();
        localStorage.removeItem('user_email');
        localStorage.removeItem('auth_user_id');
        localStorage.removeItem('display_name');
        localStorage.removeItem('nickname');
        localStorage.removeItem('user_name');
        localStorage.removeItem('roles');
        window.location.replace('/');
    }

    window.Auth = {
        fetch: authFetch,
        refresh: refreshAccessToken,
        logout,
        getToken,
        getUser() {
            return {
                auth_user_id: localStorage.getItem('auth_user_id') || '',
                email: localStorage.getItem('user_email') || '',
                display_name: localStorage.getItem('display_name') || '',
                nickname: localStorage.getItem('nickname') || '',
                name: localStorage.getItem('user_name') || '',
                roles: JSON.parse(localStorage.getItem('roles') || '[]'),
            };
        },
    };
})();
