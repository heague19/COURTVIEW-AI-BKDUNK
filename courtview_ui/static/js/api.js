/**
 * COURTVIEW API 클라이언트
 * 엔진(localhost:8000) + 클라우드 통신 래퍼
 */

const API = {
    // 엔진 API 호출
    async engine(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);

        try {
            const resp = await fetch(`/api/v1/${path}`, opts);
            return await resp.json();
        } catch (e) {
            return { success: false, message: e.message };
        }
    },

    // 클라우드 API 호출 (bkdunk) — Auth.fetch 로 Authorization 자동 부착 + 401 자동 리프레시
    async cloud(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);

        try {
            const fetcher = window.Auth?.fetch || fetch;
            const resp = await fetcher(`/cloud/${path}`, opts);
            return await resp.json();
        } catch (e) {
            return { success: false, message: e.message };
        }
    },

    // SPOIN-AUTH API 호출 (인증 계열 — /auth/me 등)
    async spoin(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);
        try {
            const fetcher = window.Auth?.fetch || fetch;
            const resp = await fetcher(`/spoin/${path}`, opts);
            return await resp.json();
        } catch (e) {
            return { success: false, message: e.message };
        }
    },

    // 경기 관리
    game: {
        start: (data) => API.engine('POST', 'game/start', data),
        stop: () => API.engine('POST', 'game/stop'),
        pause: () => API.engine('POST', 'game/pause'),
        resume: () => API.engine('POST', 'game/resume'),
        status: () => API.engine('GET', 'game/status'),
    },

    // 카메라
    camera: {
        discover: () => API.engine('GET', 'camera/discover'),
        connect: (data) => API.engine('POST', 'camera/connect', data),
        connectAll: (cameras) => API.engine('POST', 'camera/connect-all', { cameras }),
        disconnectAll: () => API.engine('POST', 'camera/disconnect-all'),
        reconnectAll: () => API.engine('POST', 'camera/reconnect-all'),
        reconnectOne: (camId) => API.engine('POST', `camera/${camId}/reconnect`),
        statusAll: () => API.engine('GET', 'camera/status-all'),
        // Phase 17 S2 — 헬스/사전 검증
        health: () => API.engine('GET', 'camera/health'),
        probe: (data) => API.engine('POST', 'camera/probe', data),
        // 기존
        calibrate: (camId, data) => API.engine('POST', `camera/${camId}/calibrate/manual`, data),
        aiTest: (camId) => API.engine('POST', `camera/${camId}/ai-test`),
    },

    // 녹화 (Phase 17 S3)
    recording: {
        start: (data) => API.engine('POST', 'recording/start', data),
        stop: () => API.engine('POST', 'recording/stop'),
        status: () => API.engine('GET', 'recording/status'),
        health: () => API.engine('GET', 'recording/health'),
    },

    // 메트릭
    metrics: {
        gpu: () => API.engine('GET', 'metrics/gpu'),
        system: () => API.engine('GET', 'metrics/system'),
    },

    // 심판
    referee: {
        decisions: (limit = 20) => API.engine('GET', `referee/decisions?limit=${limit}`),
    },

    // 전술
    tactical: {
        summary: () => API.engine('GET', 'tactical/summary'),
        boxscore: () => API.engine('GET', 'tactical/boxscore'),
    },
};
