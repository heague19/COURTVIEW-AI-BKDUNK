# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: infrastructure/discovery
파일: mdns_discovery.py
설명: mDNS / DNS-SD 카메라 광고 browse (Plan G, 2026-05-13).

      Zero-configuration networking (Bonjour/Avahi) 표준으로 카메라가 자기
      네트워크에 광고하는 RTSP 서비스를 발견. ONVIF (Plan F) 와 함께 산업
      표준 카메라 탐색 hybrid 의 2순위 자리.

      탐색 서비스 타입:
        - _rtsp._tcp.local.       (표준 RTSP)
        - _axis-video._tcp.local. (Axis 전용)
        - _dahua._tcp.local.      (Dahua 전용)
        - _onvif._tcp.local.      (ONVIF 보조 광고)

      안전장치:
        1. zeroconf 패키지 import 실패 → graceful skip (사용자가 패키지 미설치
           해도 기존 동작 유지)
        2. 환경변수 COURTVIEW_MDNS_DISCOVERY=off 로 강제 비활성
        3. timeout 강제 (기본 2초)

      한계:
        - 저가 IPCam 은 mDNS 미지원 대다수 — 효과 기대 X
        - 다중 NIC 환경 (APIPA + Wi-Fi): zeroconf 가 자동으로 모든 NIC listen

작성자: SPOIN_COURTVIEW
최종 수정: 2026-05-13
버전: 1.0.0
"""
from __future__ import annotations

import logging
import os
import time
from threading import Lock
from typing import Final

_logger = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================
DEFAULT_TIMEOUT_SEC: Final[float] = 2.0

# 카메라 표준 서비스 타입 — mDNS DNS-SD PTR query 대상
_SERVICE_TYPES: Final[tuple[str, ...]] = (
    "_rtsp._tcp.local.",          # 표준 RTSP
    "_axis-video._tcp.local.",    # Axis 전용
    "_dahua._tcp.local.",         # Dahua 전용
    "_onvif._tcp.local.",         # ONVIF 보조 광고
)

# Plan G: 환경변수 토글
MDNS_ENABLED: Final[bool] = (
    os.environ.get("COURTVIEW_MDNS_DISCOVERY", "on").strip().lower() != "off"
)


# =============================================================================
# 메인 API
# =============================================================================
def mdns_discover(timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> list[dict[str, object]]:
    """
    mDNS DNS-SD browse — 카메라 서비스 광고 수집.

    Args:
        timeout_sec: browse 대기 시간 (기본 2.0초)

    Returns:
        [{"ip": "192.168.1.50", "hostname": "cam01.local.",
          "service": "_rtsp._tcp.local.", "port": 554,
          "discovered_by": "mdns"}, ...]
    """
    if not MDNS_ENABLED:
        _logger.info("mDNS discovery 비활성화 (COURTVIEW_MDNS_DISCOVERY=off)")
        return []

    # 외부 패키지 없으면 graceful skip — 사용자 환경 호환성 최우선
    try:
        from zeroconf import (  # type: ignore[import-not-found]
            ServiceBrowser,
            ServiceListener,
            Zeroconf,
        )
    except ImportError:
        _logger.info(
            "mDNS discovery: zeroconf 패키지 미설치 — skip. "
            "사용하려면 'pip install zeroconf'.",
        )
        return []

    t0 = time.monotonic()
    found: list[dict[str, object]] = []
    found_lock = Lock()
    seen_keys: set[tuple[str, str]] = set()  # (ip, service_type) dedup

    class _CamListener(ServiceListener):  # type: ignore[misc]
        """zeroconf ServiceBrowser 콜백."""

        def add_service(self, zc: "Zeroconf", type_: str, name: str) -> None:
            try:
                info = zc.get_service_info(type_, name, timeout=1000)  # ms
                if info is None:
                    return
                addresses = info.parsed_addresses() if hasattr(info, "parsed_addresses") else []
                if not addresses:
                    return
                hostname = info.server or name
                port = info.port or 554
                for ip in addresses:
                    key = (ip, type_)
                    with found_lock:
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        found.append({
                            "ip": ip,
                            "hostname": hostname,
                            "service": type_,
                            "port": port,
                            "discovered_by": "mdns",
                        })
            except Exception as e:
                _logger.debug("mDNS add_service 파싱 실패: %s", e)

        def update_service(self, zc: "Zeroconf", type_: str, name: str) -> None:
            # 변경 이벤트는 무시 (초기 발견만 관심)
            pass

        def remove_service(self, zc: "Zeroconf", type_: str, name: str) -> None:
            pass

    zc = None
    browsers: list[ServiceBrowser] = []
    try:
        zc = Zeroconf()
        listener = _CamListener()
        for svc_type in _SERVICE_TYPES:
            browsers.append(ServiceBrowser(zc, svc_type, listener))

        # 광고 수집을 위한 wait — ServiceBrowser 가 background thread 로 동작
        time.sleep(timeout_sec)
    except Exception:
        _logger.exception("mDNS browse 예외 (계속 진행)")
    finally:
        for b in browsers:
            try:
                b.cancel()
            except Exception:
                pass
        if zc is not None:
            try:
                zc.close()
            except Exception:
                pass

    # IP 기준 최종 dedup (여러 서비스 타입에서 같은 카메라 발견 가능)
    by_ip: dict[str, dict[str, object]] = {}
    for item in found:
        ip = str(item.get("ip", ""))
        if not ip:
            continue
        # 같은 IP 가 여러 service 타입에 등장하면 첫 것 유지, service 누적
        if ip in by_ip:
            existing = by_ip[ip]
            existing_svcs = str(existing.get("service", ""))
            new_svc = str(item.get("service", ""))
            if new_svc and new_svc not in existing_svcs:
                existing["service"] = f"{existing_svcs}, {new_svc}"
        else:
            by_ip[ip] = item

    result = list(by_ip.values())
    _logger.info(
        "mDNS discovery 완료: %d서비스 광고 → %d대 (%.2fs)",
        len(found), len(result), time.monotonic() - t0,
    )
    return result


__all__ = ["mdns_discover", "MDNS_ENABLED"]
__version__ = "1.0.0"
