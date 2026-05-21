/**
 * COURTVIEW WebSocket 매니저
 * 엔진 실시간 데이터 수신 + 자동 재연결
 */

class CourtViewWS {
    constructor() {
        this.ws = null;
        this.handlers = {};
        this.reconnectDelay = 2000;
        this.connected = false;
    }

    connect(url) {
        // 엔진 직접 연결 (프록시 경유 시 websockets 라이브러리 의존 + 지연 발생)
        const wsUrl = url || 'ws://localhost:8000/ws/live';
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            this.connected = true;
            console.log('[WS] 연결됨');
            this._emit('connected');
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this._emit(msg.type, msg);
                this._emit('message', msg);
            } catch (e) {
                console.warn('[WS] 파싱 오류:', e);
            }
        };

        this.ws.onclose = () => {
            this.connected = false;
            console.log('[WS] 연결 끊김, 재연결 대기...');
            this._emit('disconnected');
            setTimeout(() => this.connect(), this.reconnectDelay);
        };

        this.ws.onerror = (e) => {
            console.error('[WS] 에러:', e);
        };
    }

    on(type, handler) {
        if (!this.handlers[type]) this.handlers[type] = [];
        this.handlers[type].push(handler);
        return this;
    }

    off(type, handler) {
        if (this.handlers[type]) {
            this.handlers[type] = this.handlers[type].filter(h => h !== handler);
        }
        return this;
    }

    _emit(type, data = null) {
        (this.handlers[type] || []).forEach(h => {
            try { h(data); } catch (e) { console.error(`[WS] handler error (${type}):`, e); }
        });
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// 글로벌 인스턴스
window.cvWS = new CourtViewWS();
