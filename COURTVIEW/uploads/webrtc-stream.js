// =============================================================================
// webrtc-stream.js  —  COURTVIEW v0.3.0
//
// go2rtc WHEP (WebRTC-HTTP Egress Protocol) 클라이언트.
// <video> 태그에 백엔드의 go2rtc 서브프로세스가 제공하는 WebRTC 스트림을 연결.
//
// 사용:
//   const ctrl = startWebRtcStream(videoElement, 'cam_0');
//   ...
//   ctrl.stop();   // 스트림 정리
//
// 왜 WebRTC 인가:
//   v0.2.x 까지 쓰던 백엔드 MJPEG 재인코딩 파이프라인은 ffmpeg 서브프로세스가
//   조용히 죽으면 프레임이 얼어붙는 고질적 문제가 있었다. go2rtc 는 RTSP→
//   WebRTC 변환 전용 서버로 재연결·코덱 협상·네트워크 glitch 복구가 검증돼있
//   고, 브라우저는 native <video> 로 H.264 를 직접 디코딩 → 지연 0.3s 이하.
// =============================================================================

(function () {
    'use strict';

    // go2rtc API endpoint (백엔드와 동일 호스트, 별도 포트)
    const GO2RTC_BASE = 'http://127.0.0.1:1984';

    /**
     * <video> 엘리먼트에 WebRTC 스트림을 연결한다.
     *
     * @param {HTMLVideoElement} videoEl   대상 <video> 태그 (muted, autoplay 권장)
     * @param {string}           streamId  go2rtc 에 등록된 스트림 이름 (ex. "cam_0")
     * @param {Object}           [opts]
     * @param {number}           [opts.reconnectDelayMs=1500]  재연결 대기 시간
     * @returns {{stop: () => void}}       정리 핸들
     */
    function startWebRtcStream(videoEl, streamId, opts) {
        const options = Object.assign({reconnectDelayMs: 1500}, opts || {});
        let pc = null;
        let reconnectTimer = null;
        let stopped = false;

        async function connect() {
            if (stopped) return;

            try {
                pc = new RTCPeerConnection({iceServers: []});

                // recvonly transceiver — 클라이언트는 수신만
                pc.addTransceiver('video', {direction: 'recvonly'});
                pc.addTransceiver('audio', {direction: 'recvonly'});

                pc.ontrack = (e) => {
                    if (videoEl.srcObject !== e.streams[0]) {
                        videoEl.srcObject = e.streams[0];
                    }
                };

                pc.onconnectionstatechange = () => {
                    if (!pc) return;
                    if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
                        scheduleReconnect();
                    }
                };

                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);

                const resp = await fetch(
                    `${GO2RTC_BASE}/api/webrtc?src=${encodeURIComponent(streamId)}`,
                    {
                        method: 'POST',
                        headers: {'Content-Type': 'application/sdp'},
                        body: offer.sdp,
                    }
                );
                if (!resp.ok) {
                    throw new Error(`WHEP HTTP ${resp.status}`);
                }
                const answerSdp = await resp.text();
                await pc.setRemoteDescription({type: 'answer', sdp: answerSdp});
            } catch (e) {
                console.warn(`[webrtc] ${streamId} 연결 실패:`, e?.message || e);
                scheduleReconnect();
            }
        }

        function scheduleReconnect() {
            cleanupPc();
            if (stopped) return;
            if (reconnectTimer) return;
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                connect();
            }, options.reconnectDelayMs);
        }

        function cleanupPc() {
            if (pc) {
                try { pc.close(); } catch (_) {}
                pc = null;
            }
            if (videoEl) {
                try { videoEl.srcObject = null; } catch (_) {}
            }
        }

        function stop() {
            stopped = true;
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
            cleanupPc();
        }

        // 최초 연결
        connect();

        return {stop};
    }

    // 전역 등록
    window.startWebRtcStream = startWebRtcStream;
})();
