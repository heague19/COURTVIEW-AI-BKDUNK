# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/discovery
파일: onvif_discovery.py
설명: ONVIF WS-Discovery (UDP multicast 3702) 순수 Python 구현 — 외부 패키지 0.

      배경:
        기존 카메라 탐색은 brute-force TCP 554 scan 단독. 2026 산업 표준은
        ONVIF + mDNS + UPnP + brute-force 의 multi-protocol hybrid.
        이 모듈은 가장 비중 큰 ONVIF 만 추가해 hybrid 의 첫 발판을 마련.

      프로토콜:
        - UDP multicast 239.255.255.250:3702
        - SOAP Envelope with Probe action
        - Types = dn:NetworkVideoTransmitter (NVR/IP 카메라)
        - 카메라가 ProbeMatches SOAP 응답 → XAddrs (ONVIF 서비스 URL) 추출

      한계:
        - 응답하지 않는 카메라 (ONVIF 미지원 or 펌웨어 비활성) → fallback 필요
        - multicast 가 차단된 네트워크 (방화벽/관리 라우터) → fallback 필요
        - 본 모듈은 IP + ONVIF URL 만 반환. 실제 RTSP URL 은 별도 `probe_rtsp_paths`
          또는 ONVIF SOAP GetStreamUri 로 보완.

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
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from typing import Final

_logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================
MULTICAST_ADDR: Final[str] = "239.255.255.250"
MULTICAST_PORT: Final[int] = 3702
DEFAULT_TIMEOUT_SEC: Final[float] = 2.0  # WS-Discovery 표준 권장 wait
RECV_BUFFER_BYTES: Final[int] = 8192     # 응답 패킷 크기 (보통 1~4KB)


# SOAP Probe XML. {msgid} 만 매번 새 UUID 로 채움.
# Types = dn:NetworkVideoTransmitter — ONVIF Profile S/T (스트리밍 NVR)
_PROBE_XML: Final[str] = """\
<?xml version="1.0" encoding="UTF-8"?>\
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"\
 xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"\
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"\
 xmlns:dn="http://www.onvif.org/ver10/network/wsdl">\
<e:Header>\
<w:MessageID>uuid:{msgid}</w:MessageID>\
<w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>\
<w:Action e:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>\
</e:Header>\
<e:Body>\
<d:Probe>\
<d:Types>dn:NetworkVideoTransmitter</d:Types>\
</d:Probe>\
</e:Body>\
</e:Envelope>"""

# XAddrs 파싱 — namespace 우회 위해 regex (네임스페이스 prefix 가 카메라마다 달라
# ET 의 findall 로는 잡기 까다로움). XAddrs 내용은 URL 공백 구분 list.
_XADDRS_RE: Final[re.Pattern[str]] = re.compile(
    r"<[\w:]*XAddrs[^>]*>(.*?)</[\w:]*XAddrs>",
    re.DOTALL | re.IGNORECASE,
)
_TYPES_RE: Final[re.Pattern[str]] = re.compile(
    r"<[\w:]*Types[^>]*>(.*?)</[\w:]*Types>",
    re.DOTALL | re.IGNORECASE,
)

# Plan F (2026-05-13): 환경변수로 즉시 비활성화 가능 (저가 카메라 환경 fallback).
ONVIF_ENABLED: Final[bool] = (
    os.environ.get("COURTVIEW_ONVIF_DISCOVERY", "on").strip().lower() != "off"
)


# =============================================================================
# 헬퍼 — NIC IP 수집
# =============================================================================
def _collect_nic_ips(filter_subnets: list[str] | None = None) -> list[str]:
    """
    Multicast probe 송신용 NIC IPv4 주소 enumerate.

    다중 NIC 환경 (이더넷 APIPA + Wi-Fi) 에서 OS 가 기본 NIC 으로만
    multicast 를 내보내면 카메라가 있는 NIC 으로 안 갈 수 있다. 각 NIC 마다
    socket bind 후 1회씩 probe 발사 → 모든 LAN segment 커버.

    Args:
        filter_subnets: ["169.254.24", "192.168.1"] 형태. 지정 시 해당 /24
                        와 매치되는 NIC 만 반환. None 이면 전부.
    """
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


# =============================================================================
# 응답 파싱
# =============================================================================
def _parse_probe_match(xml_data: str, source_ip: str) -> dict[str, object] | None:
    """
    ProbeMatches SOAP 응답에서 XAddrs / Types 추출.

    네임스페이스가 카메라 펌웨어마다 다르게 prefix 되므로 ET 의 정확한 path
    검색 대신 regex 로 본문만 추출 — 강건성 우선.
    """
    xaddrs_match = _XADDRS_RE.search(xml_data)
    types_match = _TYPES_RE.search(xml_data)
    if not xaddrs_match:
        return None
    xaddrs_raw = xaddrs_match.group(1).strip()
    # XAddrs 는 공백 구분 URL list
    xaddrs = [u for u in xaddrs_raw.split() if u.startswith("http")]
    if not xaddrs:
        return None
    types_raw = types_match.group(1).strip() if types_match else ""

    # source_ip 가 응답 패킷의 src — multicast 응답은 카메라 본인 IP 에서 옴.
    # 단, XAddrs URL 에 들어있는 호스트가 더 정확한 경우가 있어 (NAT 환경 등)
    # 우선 XAddrs URL 의 host 를 채택, 실패 시 source_ip fallback.
    onvif_ip = source_ip
    try:
        from urllib.parse import urlparse
        parsed = urlparse(xaddrs[0])
        if parsed.hostname:
            onvif_ip = parsed.hostname
    except Exception:
        pass

    return {
        "ip": onvif_ip,
        "source_ip": source_ip,
        "onvif_xaddrs": xaddrs[0],
        "types": types_raw,
    }


# =============================================================================
# 메인 API
# =============================================================================
def onvif_discover(
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    nic_ips: list[str] | None = None,
    filter_subnets: list[str] | None = None,
) -> list[dict[str, object]]:
    """
    UDP multicast WS-Discovery probe.

    각 NIC IP 에서 한 번씩 probe 발사 후, timeout_sec 동안 모든 NIC 의
    응답을 모음.

    Args:
        timeout_sec: 응답 대기 시간 (기본 2.0s, ONVIF 표준 권장)
        nic_ips:     송신용 NIC IPv4 list. None 이면 _collect_nic_ips() 자동 호출.
        filter_subnets: nic_ips=None 일 때 NIC 필터링용 ["169.254.24", ...].

    Returns:
        [{"ip": "169.254.24.13", "source_ip": ..., "onvif_xaddrs": "http://...",
          "types": "...", "discovered_by": "onvif"}, ...]
    """
    if not ONVIF_ENABLED:
        _logger.info("ONVIF discovery 비활성화 (COURTVIEW_ONVIF_DISCOVERY=off)")
        return []

    if nic_ips is None:
        nic_ips = _collect_nic_ips(filter_subnets)
    if not nic_ips:
        _logger.warning("ONVIF discovery: NIC IPv4 못 찾음")
        return []

    t0 = time.monotonic()

    def _probe_via_nic(nic_ip: str) -> list[dict[str, object]]:
        """단일 NIC 에서 probe 발사 + 응답 수신."""
        sock = None
        results: list[dict[str, object]] = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            # NIC 강제 — multicast 가 이 NIC 으로 나가게
            try:
                sock.setsockopt(
                    socket.IPPROTO_IP,
                    socket.IP_MULTICAST_IF,
                    socket.inet_aton(nic_ip),
                )
            except OSError as e:
                _logger.debug("ONVIF: NIC %s IP_MULTICAST_IF 실패 (계속): %s", nic_ip, e)
            # ephemeral port bind on this NIC
            try:
                sock.bind((nic_ip, 0))
            except OSError as e:
                _logger.debug("ONVIF: NIC %s bind 실패: %s", nic_ip, e)
                return []

            sock.settimeout(timeout_sec)
            msg_id = str(uuid.uuid4())
            payload = _PROBE_XML.format(msgid=msg_id).encode("utf-8")
            try:
                sock.sendto(payload, (MULTICAST_ADDR, MULTICAST_PORT))
            except OSError as e:
                _logger.debug("ONVIF: NIC %s sendto 실패: %s", nic_ip, e)
                return []

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
                # ProbeMatches 응답이 아니어도 XAddrs 있으면 카메라
                match = _parse_probe_match(text, source_ip=addr[0])
                if match is None:
                    continue
                cam_ip = str(match["ip"])
                if cam_ip in seen_ips:
                    continue
                seen_ips.add(cam_ip)
                match["discovered_by"] = "onvif"
                results.append(match)
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
        return results

    # NIC 마다 병렬 — 합쳐서 timeout_sec 안에 끝남
    all_results: list[dict[str, object]] = []
    with ThreadPoolExecutor(
        max_workers=max(1, len(nic_ips)), thread_name_prefix="onvif-disc",
    ) as pool:
        for nic_results in pool.map(_probe_via_nic, nic_ips):
            all_results.extend(nic_results)

    # IP 기준 dedup (여러 NIC 에서 같은 카메라가 응답하는 경우 — 일반적)
    dedup: dict[str, dict[str, object]] = {}
    for item in all_results:
        ip = str(item.get("ip", ""))
        if ip and ip not in dedup:
            dedup[ip] = item

    elapsed = time.monotonic() - t0
    _logger.info(
        "ONVIF discovery 완료: NIC=%d 발견=%d (%.2fs)",
        len(nic_ips), len(dedup), elapsed,
    )
    return list(dedup.values())


__all__ = ["onvif_discover", "ONVIF_ENABLED"]
__version__ = "1.0.0"
