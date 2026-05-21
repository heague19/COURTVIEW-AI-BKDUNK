# [Plan F] ONVIF WS-Discovery 추가

**작성일**: 2026-05-13
**목적**: 카메라 탐색 알고리즘을 2026 산업 표준 (multi-protocol hybrid) 로 모던화. ONVIF 응답하는 카메라를 1~2초 안에 즉시 발견 + 모델 정보 확보. 기존 brute-force 는 fallback 으로 유지.

---

## 0. 현재 vs 목표

### 현재 (brute-force only)
```
ARP prewarm (1s) → TCP probe 254×S IP (0.5s) → path enrich F카메라 (0.6s)
≈ 2.5~3초
```
- ONVIF 응답하는 카메라도 brute-force 로 찾음 — 트래픽/시간 낭비
- 카메라 모델/제조사/serial 정보 없음

### 목표 (ONVIF + brute-force hybrid)
```
ONVIF multicast probe (2s wait) → 응답 IP 즉시 확보
  ║
  └→ 응답 못 받은 IP 만 brute-force fallback (TCP probe)
    └→ path enrich (양쪽 결과 합치기)
```
- ONVIF 표준 준수 카메라: 2초 안에 발견 + URL 즉시 받음
- ONVIF 미지원 카메라: 기존 경로 그대로

---

## 1. 기술 결정

### 라이브러리 선택: **순수 Python 구현**
- 외부 패키지 (`wsdiscovery`, `onvif-zeep`) 추가 안 함
- 이유:
  - WS-Discovery probe 는 SOAP XML 한 덩어리 UDP multicast → 의존성 0 으로 충분
  - 패키지 추가 시 requirements.txt + PyInstaller spec 수정 + 사용자 환경 재배포 필요 — overhead 큼
  - 우리가 필요한 건 IP 발견 + onvif XAddrs URL 정도, 풀 ONVIF SOAP 클라이언트 불필요
- 구현 코드: ~120줄

### 프로토콜 핵심
- UDP multicast 239.255.255.250:3702
- SOAP Envelope with `<d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe>`
- 카메라가 `ProbeMatches` SOAP 응답 → `<d:XAddrs>` 에 ONVIF 서비스 URL
- 응답 wait: 2초 (표준 권장)

### 다중 NIC 처리
- 우리 환경: 169.254.* APIPA 직결 + Wi-Fi 함께
- multicast 는 OS 기본 NIC 으로만 나감 → 카메라 있는 NIC 으로 못 갈 수 있음
- 해결: 각 NIC IP 에 socket bind 해서 NIC 별 1회씩 probe 발사
- `_find_link_local_source()` 와 유사한 패턴

---

## 2. 변경할 파일 (3개)

| # | 파일 | 변경 |
|---|------|------|
| 1 | **`infrastructure/discovery/onvif_discovery.py`** (신규) | 순수 Python WS-Discovery probe 함수 |
| 2 | `api_server/services/camera_service.py` | `discover_many()` 안에서 ONVIF 결과 합치기 |
| 3 | `api_server/routes/v1/camera_routes.py` | (변경 없음 — 기존 route 통해 자동 활성화) |

---

## 3. 단계별 상세

### ☑ STEP 1 — `infrastructure/discovery/__init__.py` + `onvif_discovery.py` 신규

**위치**: `infrastructure/discovery/onvif_discovery.py` (신규 모듈)

핵심 함수:
```python
def onvif_discover(
    timeout_sec: float = 2.0,
    nic_ips: list[str] | None = None,
) -> list[dict[str, str]]:
    """
    UDP multicast WS-Discovery probe.
    Returns: [{"ip": "169.254.24.13", "onvif_xaddrs": [...], "types": "..."}, ...]
    """
```

구현 단계:
1. SOAP Probe XML 생성 (UUID 새로 발행)
2. 각 NIC IP 에 socket bind → 239.255.255.250:3702 로 sendto
3. timeout_sec 동안 recvfrom loop → ProbeMatches 응답 수집
4. XML 에서 XAddrs / Types / EndpointReference 파싱
5. dedup by IP, 결과 반환

XML 파서: stdlib `xml.etree.ElementTree` (의존성 0)

### ☑ STEP 2 — `camera_service.discover_many()` 에 ONVIF 통합

**위치**: [camera_service.py:1272-1398](api_server/services/camera_service.py#L1272-L1398)

흐름:
```python
def discover_many(self, subnets, port=554, ...):
    # 신규: Stage 0 — ONVIF probe (2s, 1회)
    onvif_found = onvif_discover(timeout_sec=2.0, nic_ips=_collect_nic_ips(subnets))

    # ARP prewarm (기존) — ONVIF 못 찾은 IP 만 대상으로 줄임
    onvif_ips = {item["ip"] for item in onvif_found}
    ips = [ip for ip in all_ips if ip not in onvif_ips]
    self._prewarm_arp(ips)

    # TCP probe (기존) — onvif_ips 제외 IP 만 brute-force
    ...

    # 결과 합치기: onvif_found ∪ brute_found
    # 우선순위: ONVIF 발견 (camera 확실) > brute-force 발견 (모르는 서버일 수 있음)
```

핵심: **ONVIF 발견 IP 는 brute-force 풀에서 제외** → 워커 수 / 트래픽 둘 다 절약.

### ☑ STEP 3 — 추가 메타데이터 노출 (옵션)

ONVIF 응답에 모델 정보가 있으면 결과 dict 에 포함:
```python
{
    "ip": "169.254.24.13",
    "port": "554",
    "rtsp_url": "rtsp://169.254.24.13:554/11",
    "discovered_by": "onvif",  # or "brute-force"
    "onvif_xaddrs": "http://169.254.24.13:80/onvif/device_service",
}
```

UI 가 "ONVIF 발견" / "TCP 발견" 구분 표시 가능.

### ☑ STEP 4 — 환경변수 토글

```python
_ONVIF_ENABLED: bool = os.environ.get("COURTVIEW_ONVIF_DISCOVERY", "on").lower() != "off"
```
사용자가 문제 발생 시 즉시 비활성화 가능.

---

## 4. 변경 후 예상 시간 복잡도

### 새 변수
- **F_onvif** = ONVIF 응답 카메라 수
- **F_brute** = brute-force 로만 찾는 카메라 수
- **F** = F_onvif + F_brute
- **T_onvif** = ONVIF probe wait = 2 s (고정)

### 단계별 복잡도 (병렬)

| 단계 | 복잡도 | 실측 |
|---|---|---|
| Stage 0: ONVIF probe | O(T_onvif) = **2.0 s** (고정 wait) | 2 s |
| Stage 1: ARP prewarm (N' = N - F_onvif) | O(⌈N'/K⌉ · T_ping) | ~1 s (변화 없음) |
| Stage 3: TCP probe (N' = N - F_onvif) | O(⌈N'/K⌉ · T_tcp) | ~0.5 s |
| Stage 4: path enrich (F_brute 만 — ONVIF 는 onvif xaddrs 에서 RTSP URL 추론 가능) | O(⌈F_brute/16⌉ · T_rtsp) | ~0.3 s if F_brute=4, ~0 s if F_brute=0 |

### 전체 시간

| 시나리오 | 현재 (brute-only) | Plan F (hybrid) |
|---|---|---|
| **8 카메라 전부 ONVIF 지원** | 2.5~3 s | **2.0 s + path enrich skip = ~2.0 s** |
| **8 카메라 전부 ONVIF 미지원 (저가 IPCam)** | 2.5~3 s | **2.0 s + 기존 경로 = ~4.5 s** |
| **혼합 (5 ONVIF, 3 brute)** | 2.5~3 s | **2.0 s + brute path enrich(3개) = ~3 s** |

**Trade-off 정리**:
- ONVIF 표준 준수 환경: 더 빠르고 정확
- ONVIF 미지원 환경 (우리 저가 IPCam 가능): **2초 느려짐** (ONVIF 응답 wait 시간이 추가됨)
- ONVIF 비활성 토글로 즉시 원복 가능

### 정성적 가치 (시간 외)
- 카메라 모델/제조사/serial 노출 — UI 에 표시 가능
- 비밀 카메라 (TCP 554 비표준 포트 사용) 발견 가능
- 네트워크 트래픽 감소 (ONVIF 발견 카메라는 TCP probe 안 함)
- 보안 카메라 정보 수집 — 추후 펌웨어 업데이트 알림 등에 활용

---

## 5. 검증 시나리오

1. **ONVIF 응답 카메라 환경** (가정용 IPCam 일부): ONVIF 결과 + brute-force 0건
2. **ONVIF 미지원 환경** (저가 IPCam): ONVIF 0건 + brute-force 결과 (현재와 동일)
3. **혼합 환경**: 양쪽 결과 dedup 후 합집합
4. **환경변수 off**: 기존 경로만 (현재와 동일)

---

## 6. 롤백
```powershell
$env:COURTVIEW_ONVIF_DISCOVERY = "off"
```
즉시 brute-force only 모드로 복귀.

---

## 7. Out of Scope
- 카메라 인증 정보 자동 발견 (별도 mDNS / SSDP 추가 시)
- ONVIF SOAP `GetStreamUri` 호출로 RTSP URL 직접 받기 — 일단 기존 `probe_rtsp_paths` 로 보완
- ONVIF 결과의 모델별 자동 매칭 (Hikvision / Dahua / Axis) — 우선 IP/URL 만

---

## 8. 진행 순서
1. STEP 1 — `onvif_discovery.py` 신규
2. STEP 2 — `camera_service.discover_many()` hybrid 통합
3. STEP 3/4 — 메타데이터 + env toggle
4. 사용자 검증
