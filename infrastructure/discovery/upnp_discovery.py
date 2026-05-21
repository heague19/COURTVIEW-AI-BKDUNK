# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/discovery
파일: upnp_discovery.py
설명: UPnP / SSDP M-SEARCH multicast (Plan H, 2026-05-13).

      산업 표준 카메라 탐색 hybrid 의 3순위 자리. UPnP 표준 광고하는 가정용/
      OEM 카메라 발견 보조. ONVIF (Plan F) + mDNS (Plan G) 가 못 잡는 일부
      구형/저가 카메라 커버.

      프로토콜:
        - UDP multicast 239.255.255.250:1900
        - HTTP-style M-SEARCH 요청 (텍스트, binary DNS 아님)
        - 카메라가 HTTP 200 OK 응답 → LOCATION 헤더에 device description URL
        - LOCATION URL 의 host 가 카메라 IP

      외부 패키지: 0 (stdlib socket 만)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-05-13
버전: 1.0.0
"""
from __future__ import annotations

import logging
import os
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Final
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================
MULTICAST_ADDR: Final[str] = "239.255.255.250"
MULTICAST_PORT: Final[int] = 1900
DEFAULT_TIMEOUT_SEC: Final[float] = 2.0
RECV_BUFFER_BYTES: Final[int] = 4096  # HTTP 응답은 보통 ~500B

# Search Target — ssdp:all 은 모든 장치 발견 (노이즈 ↑) / 카메라 특화 ST 도 병행.
# 일반 ssdp:all 로 가장 넓게, 그 후 응답에서 카메라/미디어 키워드 필터.
_SEARCH_TARGETS: Final[tuple[str, ...]] = (
    "ssdp:all",
    "urn:schemas-upnp-org:device:Basic:1",
    "urn:schemas-upnp-org:device:MediaServer:1",
)

# M-SEARCH HTTP-style 요청 템플릿
_MSEARCH_TEMPLATE: Final[str] = (
    "M-SEARCH * HTTP/1.1\r\n"
    "HOST: {host}:{port}\r\n"
    "MAN: \"ssdp:discover\"\r\n"
    "MX: 2\r\n"
    "ST: {st}\r\n"
    "\r\n"
)

# 응답 헤더 파싱용
_LOCATION_RE: Final[re.Pattern[str]] = re.compile(
    r"^LOCATION:\s*(.+?)\r?$", re.MULTILINE | re.IGNORECASE,
)
_SERVER_RE: Final[re.Pattern[str]] = re.compile(
    r"^SERVER:\s*(.+?)\r?$", re.MULTILINE | re.IGNORECASE,
)
_ST_RE: Final[re.Pattern[str]] = re.compile(
    r"^ST:\s*(.+?)\r?$", re.MULTILINE | re.IGNORECASE,
)

# 카메라/미디어 의심 키워드 — server / ST / location 어느 곳에 등장하면 카메라 후보
_CAMERA_KEYWORDS: Final[tuple[str, ...]] = (
    "camera", "ipcam", "video", "media", "axis", "dahua", "hikvision",
    "onvif", "rtsp", "cam",
)

# Plan H: 환경변수 토글
UPNP_ENABLED: Final[bool] = (
    os.environ.get("COURTVIEW_UPNP_DISCOVERY", "on").strip().lower() != "off"
)


# =============================================================================
# 헬퍼
# =============================================================================
def _collect_nic_ips(filter_subnets: list[str] | None = None) -> list[str]:
    """ONVIF 와 동일 패턴 — NIC IPv4 enumerate."""
    ips: list[str] = []
    try:
        import psutil  # type: ignore[import-not-found]
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family != socket.AF_INET:
                    continue
                ip = addr.address
                if ip.startswith("127.") or not ip:
                    continue
                if filter_subnets is not None:
                    prefix = ".".join(ip.split(".")[:3])
                    if prefix not in filter_subnets:
                        continue
                ips.append(ip)
    except ImportError:
        pass
    return ips


def _looks_like_camera(text: str) -> bool:
    """응답 텍스트가 카메라/미디어 장치인지 키워드 매칭."""
    low = text.lower()
    return any(kw in low for kw in _CAMERA_KEYWORDS)


def _parse_response(text: str, source_ip: str) -> dict[str, object] | None:
    """SSDP HTTP 200 OK 응답 파싱."""
    if not text.startswith("HTTP/"):
        return None
    location_match = _LOCATION_RE.search(text)
    server_match = _SERVER_RE.search(text)
    st_match = _ST_RE.search(text)

    location = location_match.group(1).strip() if location_match else ""
    server = server_match.group(1).strip() if server_match else ""
    st = st_match.group(1).strip() if st_match else ""

    # LOCATION URL 의 host 가 더 정확. 없으면 응답 패킷의 src.
    cam_ip = source_ip
    if location:
        try:
            parsed = urlparse(location)
            if parsed.hostname:
                cam_ip = parsed.hostname
        except Exception:
            pass

    # 카메라/미디어 키워드 필터 — 라우터/NAS 등 일반 UPnP 장치 제외
    if not _looks_like_camera(text):
        return None

    return {
        "ip": cam_ip,
        "source_ip": source_ip,
        "location_url": location,
        "server": server,
        "search_target": st,
        "discovered_by": "upnp",
    }


# =============================================================================
# 메인 API
# =============================================================================
def upnp_discover(
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    nic_ips: list[str] | None = None,
    filter_subnets: list[str] | None = None,
) -> list[dict[str, object]]:
    """
    SSDP M-SEARCH multicast 로 UPnP 카메라/미디어 장치 발견.

    Returns: 카메라로 추정되는 응답만 (키워드 필터링).
    """
    if not UPNP_ENABLED:
        _logger.info("UPnP discovery 비활성화 (COURTVIEW_UPNP_DISCOVERY=off)")
        return []

    if nic_ips is None:
        nic_ips = _collect_nic_ips(filter_subnets)
    if not nic_ips:
        _logger.warning("UPnP discovery: NIC IPv4 못 찾음")
        return []

    t0 = time.monotonic()

    def _probe_via_nic(nic_ip: str) -> list[dict[str, object]]:
        """단일 NIC 에서 M-SEARCH 발사 + 응답 수신."""
        sock = None
        results: list[dict[str, object]] = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            try:
                sock.setsockopt(
                    socket.IPPROTO_IP,
                    socket.IP_MULTICAST_IF,
                    socket.inet_aton(nic_ip),
                )
            except OSError as e:
                _logger.debug("UPnP: NIC %s IP_MULTICAST_IF 실패: %s", nic_ip, e)
            try:
                sock.bind((nic_ip, 0))
            except OSError as e:
                _logger.debug("UPnP: NIC %s bind 실패: %s", nic_ip, e)
                return []

            sock.settimeout(timeout_sec)
            # 각 search target 마다 M-SEARCH 발사 (장치마다 응답하는 ST 다름)
            for st in _SEARCH_TARGETS:
                msg = _MSEARCH_TEMPLATE.format(
                    host=MULTICAST_ADDR, port=MULTICAST_PORT, st=st,
                )
                try:
                    sock.sendto(msg.encode("ascii"), (MULTICAST_ADDR, MULTICAST_PORT))
                except OSError as e:
                    _logger.debug("UPnP: NIC %s sendto 실패: %s", nic_ip, e)

            # 모든 search target 발사 후 응답 수집
            seen_ips: set[str] = set()
            deadline = time.monotonic() + timeout_sec
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    data, addr = sock.recvfrom(RECV_BUFFER_BYTES)
                except (socket.timeout, OSError):
                    break
                try:
                    text = data.decode("utf-8", errors="replace")
                except Exception:
                    continue
                parsed = _parse_response(text, source_ip=addr[0])
                if parsed is None:
                    continue
                cam_ip = str(parsed["ip"])
                if cam_ip in seen_ips:
                    continue
                seen_ips.add(cam_ip)
                results.append(parsed)
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
        return results

    # NIC 마다 병렬
    all_results: list[dict[str, object]] = []
    with ThreadPoolExecutor(
        max_workers=max(1, len(nic_ips)), thread_name_prefix="upnp-disc",
    ) as pool:
        for nic_results in pool.map(_probe_via_nic, nic_ips):
            all_results.extend(nic_results)

    # IP 기준 최종 dedup
    dedup: dict[str, dict[str, object]] = {}
    for item in all_results:
        ip = str(item.get("ip", ""))
        if ip and ip not in dedup:
            dedup[ip] = item

    elapsed = time.monotonic() - t0
    _logger.info(
        "UPnP discovery 완료: NIC=%d 발견=%d (%.2fs)",
        len(nic_ips), len(dedup), elapsed,
    )
    return list(dedup.values())


__all__ = ["upnp_discover", "UPNP_ENABLED"]
__version__ = "1.0.0"
