# -*- coding: utf-8 -*-
"""
COURTVIEW Desktop UI — Python Web Application

FastAPI + Jinja2 + WebSocket 기반 로컬 데스크톱 UI.
COURTVIEW_DESK 엔진(localhost:8000)과 통신합니다.

실행:
    cd D:\COURTVIEW-UI
    python app.py

브라우저:
    http://localhost:3000
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("courtview-ui")

# =============================================================================
# 설정
# =============================================================================
UI_PORT = 3000
ENGINE_URL = os.getenv("COURTVIEW_ENGINE_URL", "http://localhost:8000")  # COURTVIEW_DESK 엔진
# SPOIN-AUTH-SERVICE — SSO 토큰 발급/갱신/검증 주체 (로그인은 여기로)
# 프로덕션 AWS 배포 URL (COURTVIEW_SPOIN_AUTH_URL env 로 로컬 개발 override 가능)
SPOIN_AUTH_URL = os.getenv("COURTVIEW_SPOIN_AUTH_URL", "http://98.81.23.206:8002")
# bkdunk-backend (Node.js) — 커뮤니티 + 경기 데이터 클라우드 (SPOIN 토큰으로 접근)
# 프로덕션: https://api.bkdunk.com (HTTPS, reverse proxy 뒤). 로컬 개발은 env 로 override.
# (옛 임시 endpoint http://98.81.23.206:5000 은 폐기 — cloud/* 라우트 미배포 + HTTP only)
BKDUNK_URL = os.getenv("COURTVIEW_BKDUNK_URL", "https://api.bkdunk.com")
# 레거시 별칭 (일부 템플릿/JS가 /cloud/* 경로 사용 — bkdunk 으로 포워딩)
CLOUD_URL = BKDUNK_URL

# =============================================================================
# FastAPI 앱
# =============================================================================
app = FastAPI(title="COURTVIEW Desktop UI", version="1.0.0")

# 정적 파일 + 템플릿
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# =============================================================================
# 페이지 라우트
# =============================================================================

@app.get("/test")
async def test_page():
    """순수 HTML 테스트."""
    return HTMLResponse("<h1>TEST OK</h1>")


@app.get("/", response_class=HTMLResponse)
async def page_login(request: Request):
    """로그인 페이지."""
    try:
        return templates.TemplateResponse(request, "pages/login.html")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return HTMLResponse(f"<pre>ERROR:\n{tb}</pre>", status_code=500)


@app.get("/home", response_class=HTMLResponse)
async def page_home(request: Request):
    """홈 대시보드."""
    return templates.TemplateResponse(request, "pages/home.html")


@app.get("/equipment/calibrate/{camera_id}", response_class=HTMLResponse)
async def page_calibrate(request: Request, camera_id: str):
    """카메라 캘리브레이션."""
    return templates.TemplateResponse(request, "pages/calibrate.html", {"camera_id": camera_id})


@app.get("/game/analysis", response_class=HTMLResponse)
async def page_game_analysis(request: Request):
    """경기 분석 (카메라 + AI 분석)."""
    return templates.TemplateResponse(request, "pages/game_analysis.html")


@app.get("/game/result", response_class=HTMLResponse)
async def page_game_result(request: Request):
    """경기 결과."""
    return templates.TemplateResponse(request, "pages/game_result.html")


@app.get("/operator", response_class=HTMLResponse)
async def page_operator(request: Request):
    """M3 — 오퍼레이터 (전광판 컨트롤러 + 기록지 + 교체 큐)."""
    return templates.TemplateResponse(request, "pages/operator.html")


@app.get("/replay", response_class=HTMLResponse)
async def page_replay(request: Request):
    """REPLAY — 녹화된 세션을 다시 분석에 투입."""
    return templates.TemplateResponse(request, "pages/replay.html")


@app.get("/replay/view/{session_id}", response_class=HTMLResponse)
async def page_replay_view(request: Request, session_id: str):
    """REPLAY 결과 뷰어 — 비디오 + 이벤트 오버레이 (운영자 컨트롤 없음)."""
    return templates.TemplateResponse(
        request,
        "pages/replay_view.html",
        {"session_id": session_id},
    )


@app.get("/scoreboard", response_class=HTMLResponse)
async def page_scoreboard(request: Request):
    """M2 — 메인 전광판 (관객용 풀스크린)."""
    return templates.TemplateResponse(request, "pages/scoreboard.html")



@app.get("/database", response_class=HTMLResponse)
async def page_database(request: Request):
    """DB 관리 (팀/선수)."""
    return templates.TemplateResponse(request, "pages/database.html")


@app.get("/equipment", response_class=HTMLResponse)
async def page_equipment(request: Request):
    """장비 관리."""
    return templates.TemplateResponse(request, "pages/equipment.html")


@app.get("/court", response_class=HTMLResponse)
async def page_court(request: Request):
    """경기장 관리."""
    return templates.TemplateResponse(request, "pages/court.html")


@app.get("/referee", response_class=HTMLResponse)
async def page_referee(request: Request):
    """심판 관리."""
    return templates.TemplateResponse(request, "pages/referee.html")


@app.get("/license", response_class=HTMLResponse)
async def page_license(request: Request):
    """라이선스 관리."""
    return templates.TemplateResponse(request, "pages/license.html")


@app.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    """설정."""
    return templates.TemplateResponse(request, "pages/settings.html")


# =============================================================================
# 엔진 API 프록시 (UI → Engine)
# =============================================================================

@app.get("/api/v1/camera/{camera_id}/snapshot")
async def proxy_snapshot(camera_id: str):
    """카메라 스냅샷 프록시 — JPEG 바이너리를 그대로 중계."""
    from starlette.responses import Response as StarletteResponse
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{ENGINE_URL}/api/v1/camera/{camera_id}/snapshot")
            if resp.status_code == 200:
                return StarletteResponse(content=resp.content, media_type="image/jpeg")
        except Exception:
            pass
    return StarletteResponse(content=b"", status_code=404)


@app.get("/api/v1/stream/{camera_id}")
async def proxy_stream(camera_id: str):
    """MJPEG 스트림 프록시 — 바이너리 스트림을 그대로 중계."""
    from starlette.responses import StreamingResponse as StarletteStream

    async def stream_gen():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "GET", f"{ENGINE_URL}/api/v1/stream/{camera_id}"
            ) as resp:
                async for chunk in resp.aiter_bytes(4096):
                    yield chunk

    return StarletteStream(
        stream_gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/v1/recording/sessions/{session_id}/video")
async def proxy_recording_video(session_id: str, request: Request):
    """REPLAY 영상 프록시 — Range 헤더 전달 + 바이너리 스트림 중계 (HTML5 video 재생용).

    /api/* 일반 프록시는 JSON 응답만 다루므로 binary mp4 는 별도 라우트가 필요.
    `proxy_clips` 와 동일한 패턴.
    """
    from starlette.responses import StreamingResponse as StarletteStream

    qs = str(request.url.query)
    upstream = f"{ENGINE_URL}/api/v1/recording/sessions/{session_id}/video"
    if qs:
        upstream += f"?{qs}"

    fwd_headers = {}
    if "range" in request.headers:
        fwd_headers["Range"] = request.headers["range"]
    auth = request.headers.get("authorization")
    if auth:
        fwd_headers["Authorization"] = auth

    client = httpx.AsyncClient(timeout=None)
    try:
        req = client.build_request("GET", upstream, headers=fwd_headers)
        resp = await client.send(req, stream=True)
    except httpx.ConnectError:
        await client.aclose()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"success": False, "message": "엔진 서버 연결 실패"})

    out_headers = {}
    for k in ("content-length", "content-range", "accept-ranges", "cache-control"):
        if k in resp.headers:
            out_headers[k.title()] = resp.headers[k]

    async def body_gen():
        try:
            async for chunk in resp.aiter_bytes(64 * 1024):
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StarletteStream(
        body_gen(),
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "video/mp4"),
        headers=out_headers,
    )


@app.get("/clips/{path:path}")
async def proxy_clips(path: str, request: Request):
    """하이라이트 클립 MP4 프록시 — Range 헤더 전달 + 바이너리 스트림 중계."""
    from starlette.responses import StreamingResponse as StarletteStream

    upstream = f"{ENGINE_URL}/clips/{path}"
    fwd_headers = {}
    # 비디오 시크용 Range 전달
    if "range" in request.headers:
        fwd_headers["Range"] = request.headers["range"]

    client = httpx.AsyncClient(timeout=None)
    try:
        req = client.build_request("GET", upstream, headers=fwd_headers)
        resp = await client.send(req, stream=True)
    except httpx.ConnectError:
        await client.aclose()
        return {"success": False, "message": "엔진 서버 연결 실패"}

    # 스트리밍 응답 — content-length / content-range 보존
    out_headers = {}
    for k in ("content-length", "content-range", "accept-ranges", "cache-control"):
        if k in resp.headers:
            out_headers[k.title()] = resp.headers[k]

    async def body_gen():
        try:
            async for chunk in resp.aiter_bytes(64 * 1024):
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StarletteStream(
        body_gen(),
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "video/mp4"),
        headers=out_headers,
    )


# 경로별 타임아웃 — game/start·finalize·video 분석은 무거운 작업
def _timeout_for(path: str) -> float:
    p = path.lower()
    # GameOrchestrator 빌드 (torch/CUDA 모델 로딩) — 첫 실행 시 2~3분 걸릴 수 있음
    # game/stop 도 POST-GAME pipeline (통계 산출/머지/cloud sync) 동기 실행으로 길어질 수 있음
    if 'game/start' in p or 'game/stop' in p or 'finalize' in p or 'video/upload' in p or 'analyze' in p:
        return 300.0  # 5분
    # REPLAY 업로드 — 카메라당 수백 MB ~ 1GB 영상 전송
    if 'recording/upload' in p:
        return 300.0  # 5분
    # 녹화 시작/종료 (ffmpeg spawn / 머지) — 몇 초
    if 'recording/' in p:
        return 60.0
    # 카메라 자동탐색 — 여러 서브넷 × 254 IP 병렬이지만 안전 마진
    if 'camera/discover' in p or 'camera/ai-test' in p or 'camera/calibrate' in p:
        return 60.0
    # 기본
    return 30.0


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_engine_api(request: Request, path: str):
    """엔진 API 프록시 — UI에서 /api/* 호출 시 엔진으로 전달 (Authorization 헤더 포함)."""
    from fastapi.responses import JSONResponse
    timeout = _timeout_for(path)
    async with httpx.AsyncClient(timeout=timeout) as client:
        url = f"{ENGINE_URL}/api/{path}"
        body = await request.body()
        # host/content-length 만 제거, Authorization/Content-Type 등은 전달
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length")
        }

        try:
            resp = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
                params=dict(request.query_params),
            )
            # 상태 코드 보존 — finalize 의 409 등을 UI 가 정확히 받아야 함
            try:
                return JSONResponse(status_code=resp.status_code, content=resp.json())
            except Exception:
                return JSONResponse(status_code=resp.status_code, content={"raw": resp.text})
        except httpx.ConnectError:
            return JSONResponse(
                status_code=503,
                content={"success": False, "message": "엔진 서버 연결 실패 (localhost:8000)"},
            )
        except httpx.ReadTimeout:
            logger.warning("proxy timeout (%.0fs) on /api/%s — 엔진이 응답 안 함", timeout, path)
            return JSONResponse(
                status_code=504,
                content={
                    "success": False,
                    "message": f"엔진 응답 타임아웃 ({timeout:.0f}초). 첫 실행 시 모델 로딩으로 오래 걸릴 수 있습니다.",
                    "path": path,
                },
            )
        except Exception as e:
            logger.exception("proxy error on /api/%s", path)
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"{type(e).__name__}: {e}"},
            )


# =============================================================================
# SPOIN-AUTH-SERVICE 프록시 (UI → SSO 토큰 발급/갱신/검증)
# =============================================================================

@app.api_route("/spoin/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_spoin_auth(request: Request, path: str):
    """SPOIN-AUTH-SERVICE 프록시 — 로그인/토큰 발급·갱신·검증."""
    from fastapi.responses import JSONResponse
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"{SPOIN_AUTH_URL}/{path}"
        body = await request.body()
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length")
        }
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
                params=dict(request.query_params),
            )
            # 상태 코드 보존 (401 / 429 등을 UI 가 정확히 받아야 리프레시/재로그인 가능)
            try:
                return JSONResponse(
                    status_code=resp.status_code,
                    content=resp.json(),
                )
            except Exception:
                return JSONResponse(
                    status_code=resp.status_code,
                    content={"raw": resp.text},
                )
        except httpx.ConnectError:
            return JSONResponse(
                status_code=503,
                content={"success": False, "message": "SPOIN-AUTH 서버 연결 실패"},
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": str(e)},
            )


# =============================================================================
# bkdunk API 프록시 (UI → 커뮤니티/경기 데이터)
# =============================================================================

@app.api_route("/bkdunk-public/{path:path}", methods=["GET"])
async def proxy_bkdunk_public(request: Request, path: str):
    """bkdunk 공개 API 프록시 — `/api/tournaments` 등 인증 불필요 라우트용.

    BKDUNK_INTEGRATION_GUIDE §1 기준: 대회 일정은 공개 라우트라 토큰 X.
    SPOIN-AUTH 토큰을 그대로 보내면 bkdunk JWT_SECRET 으로 검증 실패 (secret 불일치)
    하므로 Authorization 헤더 자체를 떨어뜨리고 forward — 가이드 §3-2 권장.
    """
    from fastapi.responses import JSONResponse
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{CLOUD_URL}/{path}"
        # Authorization / Cookie 등 인증 헤더는 일부러 제외 — 공개 호출
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length", "authorization", "cookie")
        }
        try:
            resp = await client.get(url, headers=headers, params=dict(request.query_params))
            try:
                return JSONResponse(status_code=resp.status_code, content=resp.json())
            except Exception:
                return JSONResponse(status_code=resp.status_code, content={"raw": resp.text})
        except httpx.ConnectError:
            return JSONResponse(status_code=503, content={"success": False, "message": "bkdunk 공개 API 연결 실패"})
        except Exception as e:
            return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


@app.api_route("/cloud/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_cloud_api(request: Request, path: str):
    """bkdunk-backend 프록시 — 커뮤니티, 경기, 하이라이트 등.

    bkdunk 라우터는 `/cloud/api/*` prefix 로 마운트돼 있어 `/cloud/` 를 살려 forward.
    이전엔 `${CLOUD_URL}/${path}` 로 보내서 prefix 가 떨어져 404 발생 (모든 cloud 호출 실패).
    """
    from fastapi.responses import JSONResponse
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{CLOUD_URL}/cloud/{path}"
        body = await request.body()
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length")
        }

        try:
            resp = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
                params=dict(request.query_params),
            )
            try:
                return JSONResponse(
                    status_code=resp.status_code,
                    content=resp.json(),
                )
            except Exception:
                return JSONResponse(
                    status_code=resp.status_code,
                    content={"raw": resp.text},
                )
        except httpx.ConnectError:
            return JSONResponse(
                status_code=503,
                content={"success": False, "message": "클라우드 서버 연결 실패"},
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": str(e)},
            )


# =============================================================================
# WebSocket 프록시 (UI ↔ Engine 실시간)
# =============================================================================

# =============================================================================
# Phase 18-A4: UI 로컬 broker (/ws/ops) — 3 페이지 간 상태 동기화
# =============================================================================
_ops_clients: set[WebSocket] = set()
_ops_lock = asyncio.Lock()


@app.websocket("/ws/ops")
async def ws_ops(ws: WebSocket):
    """UI 로컬 상태 동기화 broker.

    operator/scoreboard/analysis 페이지가 각자 연결,
    메시지를 받으면 본인 제외한 나머지 클라이언트에게 그대로 브로드캐스트.
    payload 규약 (client가 정하는 topic):
      { "topic": "game_state" | "sub_pending" | "recording" | "scoreboard_mode", "data": {...} }
    """
    await ws.accept()
    async with _ops_lock:
        _ops_clients.add(ws)
    logger.info("ops client connected (%d)", len(_ops_clients))

    try:
        while True:
            msg = await ws.receive_text()
            dead: set[WebSocket] = set()
            async with _ops_lock:
                others = list(_ops_clients)
            for client in others:
                if client is ws:
                    continue
                try:
                    await client.send_text(msg)
                except Exception:
                    dead.add(client)
            if dead:
                async with _ops_lock:
                    _ops_clients.difference_update(dead)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("ops ws error: %s", e)
    finally:
        async with _ops_lock:
            _ops_clients.discard(ws)
        logger.info("ops client disconnected (%d)", len(_ops_clients))


@app.websocket("/ws/live")
async def websocket_proxy(websocket: WebSocket):
    """엔진 WebSocket 프록시 — UI ↔ Engine 실시간 데이터 중계."""
    await websocket.accept()
    client = websocket.client
    client_str = f"{client.host}:{client.port}" if client else "?"
    logger.info("[WS-PROXY] 🌐 UI 클라이언트 연결 → %s", client_str)

    import websockets

    try:
        async with websockets.connect(f"ws://localhost:8000/ws/live") as engine_ws:
            logger.info(
                "[WS-PROXY] 🔗 엔진 연결 성공 → %s ↔ ws://localhost:8000/ws/live",
                client_str,
            )
            stats = {"to_ui": 0, "to_engine": 0, "events_to_ui": 0}

            async def forward_to_ui():
                """엔진 → UI."""
                try:
                    async for msg in engine_ws:
                        await websocket.send_text(msg)
                        stats["to_ui"] += 1
                        # 이벤트 메시지는 매번 로그, 그 외는 100건마다 1번
                        try:
                            payload = json.loads(msg)
                            mtype = payload.get("type") if isinstance(payload, dict) else None
                            if mtype == "event":
                                stats["events_to_ui"] += 1
                                logger.info(
                                    "[WS-PROXY] 📨 엔진→UI event_type=%s "
                                    "frame=%s (events_total=%d)",
                                    payload.get("event_type"),
                                    payload.get("frame_index"),
                                    stats["events_to_ui"],
                                )
                            elif stats["to_ui"] % 100 == 0:
                                logger.info(
                                    "[WS-PROXY] 📨 엔진→UI 누적 %d건 "
                                    "(최근 type=%s)",
                                    stats["to_ui"], mtype,
                                )
                        except Exception:
                            pass
                except Exception as fwd_exc:
                    logger.debug("[WS-PROXY] forward_to_ui 종료: %s", fwd_exc)

            async def forward_to_engine():
                """UI → 엔진."""
                try:
                    while True:
                        data = await websocket.receive_text()
                        await engine_ws.send(data)
                        stats["to_engine"] += 1
                        if stats["to_engine"] <= 5 or stats["to_engine"] % 50 == 0:
                            logger.info(
                                "[WS-PROXY] 📨 UI→엔진 #%d (%d bytes)",
                                stats["to_engine"], len(data),
                            )
                except WebSocketDisconnect:
                    logger.info(
                        "[WS-PROXY] UI 클라이언트 disconnect → %s "
                        "(전송 통계: ui=%d events=%d engine=%d)",
                        client_str, stats["to_ui"], stats["events_to_ui"],
                        stats["to_engine"],
                    )

            await asyncio.gather(forward_to_ui(), forward_to_engine())

    except Exception as e:
        logger.warning("[WS-PROXY] 엔진 WebSocket 연결 실패 → %s: %s", client_str, e)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "엔진 WebSocket 연결 실패",
            }))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("[WS-PROXY] 🔚 세션 종료 → %s", client_str)


# =============================================================================
# 헬스 체크
# =============================================================================

@app.get("/health")
async def health():
    """UI 서버 헬스 체크."""
    engine_ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{ENGINE_URL}/health")
            engine_ok = resp.status_code == 200
    except Exception:
        pass

    return {
        "ui": "ok",
        "engine": "ok" if engine_ok else "disconnected",
        "engine_url": ENGINE_URL,
    }


# =============================================================================
# 메인
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("COURTVIEW Desktop UI")
    print(f"  UI:     http://localhost:{UI_PORT}")
    print(f"  Engine: {ENGINE_URL}")
    print(f"  Cloud:  {CLOUD_URL}")
    print("=" * 50)

    import os
    os.chdir(str(BASE_DIR))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=UI_PORT,
        log_level="info",
    )
