# [Plan H] UPnP / SSDP 추가 (산업 표준 hybrid 완성)

**작성일**: 2026-05-13
**선행**: Plan F (ONVIF), Plan G (mDNS) 완료
**목적**: 산업 표준 카메라 탐색 hybrid 의 마지막 표준 프로토콜 UPnP/SSDP 추가. **3순위 자리** 차지 — 가정용 IPCam, 일부 OEM 카메라가 SSDP 로만 광고하는 케이스 보완.

---

## 0. 산업 표준 hybrid 의 완성

| 우선 | 프로토콜 | 포트 | 적용 시점 | 상태 |
|---:|---|---|---|---|
| 🥇 1 | **ONVIF WS-Discovery** | UDP 3702 | 2026-05-13 | ✅ Plan F |
| 🥈 2 | **mDNS / Bonjour** | UDP 5353 | 2026-05-13 | ✅ Plan G |
| 🥉 3 | **UPnP / SSDP** | UDP 1900 | 2026-05-13 | 🆕 **Plan H** |
| 4 | TCP brute-force | TCP 554+ | 기존 | ✅ fallback |

Plan H 완료 후 **2026 산업 표준 multi-protocol hybrid 완성**.

---

## 1. SSDP 프로토콜 핵심

UPnP 의 일부인 Simple Service Discovery Protocol — HTTP 형식의 UDP multicast.

### Request (M-SEARCH)
```
M-SEARCH * HTTP/1.1\r\n
HOST: 239.255.255.250:1900\r\n
MAN: "ssdp:discover"\r\n
MX: 2\r\n
ST: urn:schemas-upnp-org:device:Basic:1\r\n
\r\n
```

`ST` (Search Target):
- `ssdp:all` — 모든 장치 (가장 광범위 + 노이즈 ↑)
- `urn:schemas-upnp-org:device:Basic:1` — 기본 UPnP 장치
- `urn:schemas-upnp-org:device:MediaServer:1` — 미디어 서버 (일부 카메라)
- `urn:axis-com:service:BasicService:1` — Axis 전용
- `urn:dahua-com:service:ws-discovery:1` — Dahua 전용

### Response (HTTP 200 OK over UDP)
```
HTTP/1.1 200 OK\r\n
LOCATION: http://192.168.1.50:5000/rootDesc.xml\r\n
SERVER: Linux/3.x UPnP/1.0 IPCam/1.0\r\n
ST: urn:schemas-upnp-org:device:Basic:1\r\n
USN: uuid:...\r\n
\r\n
```

→ `LOCATION` 의 URL host 가 카메라 IP. `SERVER` 헤더에 모델 정보 가능.

---

## 2. 기술 결정

### **순수 Python 구현** (의존성 0)
- ONVIF (Plan F) 와 동일 패턴 — UDP socket + HTTP-style 응답 파싱
- mDNS 와 달리 binary DNS 가 아니라 텍스트 HTTP → 파싱 간단
- 외부 패키지 없이 ~150줄

### 다중 NIC 처리
- ONVIF 와 동일하게 각 NIC IP 에 bind 후 multicast 발사
- `IP_MULTICAST_IF` 로 NIC 강제

### 안전장치
1. 환경변수 `COURTVIEW_UPNP_DISCOVERY=off` 토글
2. timeout 2초 강제
3. 응답 텍스트 파싱 에러 무시

---

## 3. 변경할 파일 (3개)

| # | 파일 | 변경 |
|---|------|------|
| 1 | **`infrastructure/discovery/upnp_discovery.py`** (신규) | 순수 Python SSDP M-SEARCH |
| 2 | `infrastructure/discovery/__init__.py` | `upnp_discover` export |
| 3 | `api_server/services/camera_service.py` | `discover_many()` Stage 0 에 3종 병렬 통합 |

---

## 4. 단계별

### ☑ STEP 1 — `upnp_discovery.py` 신규

핵심 함수:
```python
def upnp_discover(
    timeout_sec: float = 2.0,
    nic_ips: list[str] | None = None,
    filter_subnets: list[str] | None = None,
    search_targets: tuple[str, ...] | None = None,
) -> list[dict[str, object]]:
    """Returns: [{"ip": "...", "location_url": "...", "server": "...",
                  "search_target": "...", "discovered_by": "upnp"}, ...]"""
```

ONVIF 와 거의 동일한 패턴:
1. 각 NIC IP 에 UDP socket bind
2. M-SEARCH 패킷 발사 (multicast 239.255.255.250:1900)
3. timeout_sec 동안 recvfrom loop → HTTP-style 응답 수집
4. LOCATION 헤더에서 host IP 추출

### ☑ STEP 2 — 3종 병렬 통합

[camera_service.py:1313~](api_server/services/camera_service.py#L1313) Stage 0 의 `ThreadPoolExecutor(max_workers=2)` → `max_workers=3` 로 늘리고 UPnP 추가:

```python
with ThreadPoolExecutor(max_workers=3, thread_name_prefix="disc-std") as disc_pool:
    fut_onvif = disc_pool.submit(onvif_discover, ...) if ONVIF_ENABLED else None
    fut_mdns  = disc_pool.submit(mdns_discover, ...) if MDNS_ENABLED else None
    fut_upnp  = disc_pool.submit(upnp_discover, ...) if UPNP_ENABLED else None
    ...
```

3 프로토콜이 동시에 2초 wait → 총 시간 max(2,2,2) = 2초 (변화 없음).

---

## 5. 시간 복잡도 — 4단계 비교

| 시나리오 | brute-only | Plan F | Plan G | **Plan H** |
|---|---|---|---|---|
| 전부 ONVIF | 2.5-3 s | 2.0 s | 2.0 s | **2.0 s** |
| 혼합 | 2.5-3 s | 2.6 s | 2.0 s | **2.0 s** |
| mDNS만 | 2.5-3 s | 4.5 s | 2.0 s | **2.0 s** |
| UPnP만 | 2.5-3 s | 4.5 s | 4.5 s | **2.0 s** |
| 전부 미지원 (저가) | 2.5-3 s | 4.5 s | 4.5 s | **4.5 s** (변화 없음) |

**3 프로토콜 병렬이라 시간은 동일 2초** — 효과는 발견 가능 카메라 수가 늘어남.

---

## 6. ROI 정직한 평가

### 발견 가능 카메라 분포 (산업 통계)
- ONVIF 지원: 전문 카메라 ~80% (2026 기준)
- mDNS 지원: ~30% (Axis, 일부 가정용)
- UPnP/SSDP 지원: ~20% (구형, 가정용 일부)

### 우리 환경 (저가 IPCam APIPA)
- 3 프로토콜 모두 미지원 가능성 큼
- Plan H 추가의 즉시 효과 거의 0
- 산업 표준 완성 가치는 미래 카메라 교체 시 (다른 모델로 바꿔도 코드 그대로 호환)

### 코드 가치
- 산업 표준 hybrid 완성 — 어떤 카메라가 와도 발견
- 호환성 측면에서 production-ready

---

## 7. 검증

```
[INFO] ONVIF discovery 완료: NIC=2 발견=N1 (2.0s)
[INFO] mDNS discovery 완료: ... → N2대 (2.0s)
[INFO] UPnP discovery 완료: NIC=2 발견=N3 (2.0s)
[INFO] 표준 protocol 탐색 완료: ONVIF=N1, mDNS=N2, UPnP=N3, dedup=합 (~2.0s)
```

---

## 8. 롤백
```powershell
$env:COURTVIEW_UPNP_DISCOVERY = "off"
```

---

## 9. 진행 순서
1. STEP 1: `upnp_discovery.py` 신규
2. STEP 2: 3종 병렬 통합
3. 보고 (시간 복잡도 + Plan F/G/H 비교 표)
