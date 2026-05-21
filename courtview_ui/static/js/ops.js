/**
 * COURTVIEW — UI 페이지 간 상태 broker 클라이언트 (Phase 18-A4)
 *
 * 3 페이지(/analysis, /operator, /scoreboard) 가 /ws/ops 를 공유하여
 * 실시간으로 상태를 전파. 서버는 단순 브로드캐스트 허브.
 *
 * 사용:
 *   Ops.subscribe('game_state', (data) => { ... });
 *   Ops.publish('game_state', { homeScore: 42, ... });
 */
(function () {
    const HANDLERS = {};  // topic → [callback, ...]
    let ws = null;
    let reconnectTimer = null;
    let connected = false;
    const OUTBOX = [];

    function connect() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${proto}//${location.host}/ws/ops`);

        ws.onopen = () => {
            connected = true;
            console.log('[Ops] WebSocket connected');
            // outbox flush
            while (OUTBOX.length > 0) {
                try { ws.send(OUTBOX.shift()); } catch {}
            }
            _onStatus(true);
        };

        ws.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                const topic = msg.topic;
                const cbs = HANDLERS[topic];
                if (cbs) cbs.forEach(cb => {
                    try { cb(msg.data, msg); } catch (err) {
                        console.error('[Ops] handler error', topic, err);
                    }
                });
            } catch (err) {
                console.warn('[Ops] invalid message', e.data);
            }
        };

        ws.onclose = () => {
            connected = false;
            _onStatus(false);
            console.log('[Ops] WebSocket disconnected, reconnecting in 2s');
            if (reconnectTimer) clearTimeout(reconnectTimer);
            reconnectTimer = setTimeout(connect, 2000);
        };

        ws.onerror = () => {
            // onclose 에서 재연결 처리
        };
    }

    function _onStatus(ok) {
        // 선택: body에 data-attribute 로 상태 노출 (CSS에서 스타일링 가능)
        document.documentElement.setAttribute('data-ops', ok ? 'online' : 'offline');
    }

    window.Ops = {
        publish(topic, data) {
            const payload = JSON.stringify({ topic, data, ts: Date.now() });
            if (connected && ws && ws.readyState === WebSocket.OPEN) {
                try { ws.send(payload); } catch { OUTBOX.push(payload); }
            } else {
                // 재연결 전이면 outbox에 쌓고 flush 대기
                OUTBOX.push(payload);
                if (OUTBOX.length > 50) OUTBOX.shift();  // overflow 방지
            }
        },

        subscribe(topic, callback) {
            if (!HANDLERS[topic]) HANDLERS[topic] = [];
            HANDLERS[topic].push(callback);
        },

        unsubscribe(topic, callback) {
            const arr = HANDLERS[topic];
            if (!arr) return;
            const i = arr.indexOf(callback);
            if (i >= 0) arr.splice(i, 1);
        },

        get connected() { return connected; },

        // 멀티 모니터 창 자동 오픈 — 반드시 user gesture 안에서 동기 호출
        // (window.open을 Promise.then 안에서 호출하면 팝업 차단됨)
        openMonitors() {
            const primaryW = screen.availWidth;
            const primaryH = screen.availHeight;

            // 1단계: 동기 open (user gesture 유지)
            const w2 = window.open('/scoreboard', 'cv_scoreboard',
                `width=${primaryW},height=${primaryH},left=${primaryW},top=0`);
            const w3 = window.open('/operator', 'cv_operator',
                `width=1600,height=900,left=100,top=100`);

            if (!w2 && !w3) {
                alert('⚠ 팝업이 차단되었습니다. 주소창 우측 아이콘에서 이 사이트의 팝업을 허용 후 다시 시도하세요.');
                return;
            }

            // 2단계: 비동기 Window Management API 로 정확한 모니터에 재배치
            if (typeof window.getScreenDetails === 'function') {
                window.getScreenDetails().then(sd => {
                    const monitors = sd.screens;
                    if (monitors.length >= 2 && w2) {
                        const m2 = monitors[1];
                        try {
                            w2.moveTo(m2.left, m2.top);
                            w2.resizeTo(m2.width, m2.height);
                        } catch {}
                    }
                    if (monitors.length >= 3 && w3) {
                        const m3 = monitors[2];
                        try {
                            w3.moveTo(m3.left, m3.top);
                            w3.resizeTo(m3.width, m3.height);
                        } catch {}
                    }
                }).catch(() => { /* 권한 없으면 기본 위치 유지 */ });
            }
        },
    };

    // 자동 연결
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', connect);
    } else {
        connect();
    }
})();
