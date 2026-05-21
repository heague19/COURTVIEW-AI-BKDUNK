/**
 * COURTVIEW 페이지 가드
 *
 * localStorage 의 access_token 유무·만료 확인 → 없으면 /login 으로 리다이렉트.
 * 모든 보호 페이지는 이 스크립트를 <head> 맨 앞 쪽에 <script> 로 로드해야 함.
 *
 * 제외:
 *   - /                   (로그인 페이지 자신)
 *   - /test               (개발 헬스체크)
 *
 * 만료 토큰 처리:
 *   이 단계에서는 만료 시 즉시 redirect. (3) 리프레시 로직에서 자동 갱신 도입.
 */
(function () {
    const EXEMPT_PATHS = ['/', '/test'];
    const path = window.location.pathname;

    if (EXEMPT_PATHS.includes(path)) {
        return;  // 로그인/테스트는 가드 미적용
    }

    const token = localStorage.getItem('access_token');
    const expRaw = localStorage.getItem('access_token_exp');
    const exp = expRaw ? parseInt(expRaw, 10) : 0;
    const now = Date.now();

    // 토큰 없음 → 로그인 이동
    if (!token) {
        console.warn('[auth-guard] 토큰 없음 → 로그인');
        // next 파라미터로 원래 페이지 기억 (로그인 후 되돌아오기)
        const next = encodeURIComponent(path + window.location.search);
        window.location.replace('/?next=' + next);
        return;
    }

    // 만료 — 로컬 정보 정리 후 로그인
    // 주의: access_token_exp 가 없는 구버전 토큰은 exp=0 이 되어 '만료' 로 판정됨.
    //      구버전 호환 필요 시 exp>0 인 경우만 비교하도록 수정.
    if (exp > 0 && exp < now) {
        console.warn('[auth-guard] 토큰 만료 → 재로그인');
        localStorage.removeItem('access_token');
        localStorage.removeItem('access_token_exp');
        // refresh_token 은 (3) 단계에서 자동 갱신에 사용하므로 보존
        const next = encodeURIComponent(path + window.location.search);
        window.location.replace('/?next=' + next);
        return;
    }

    // 인증 OK — 아무것도 안 함
})();
