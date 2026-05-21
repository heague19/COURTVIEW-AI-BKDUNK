# [Plan G] mDNS / Zeroconf 추가 (산업 표준 hybrid 2순위)

**작성일**: 2026-05-13
**선행**: Plan F (ONVIF) 완료
**목적**: 산업 표준 카메라 탐색 hybrid 의 2순위 프로토콜인 mDNS / Zero-configuration networking 추가. Bonjour / Avahi 표준 사용 카메라 발견 + ONVIF 미지원 카메라 보완.

---

## 0. 왜 추가하는가

### 현재 (Plan F 까지)
- Stage 0: ONVIF (UDP 3702) — 전문 IP 카메라 발견
- Stage 1~3: brute-force TCP 554 — fallback

### Gap
- 일부 카메라 (Axis 일부 모델, 가정용 일부) 는 **ONVIF 비활성 + mDNS 광고만 함**
- mDNS 가 발견하는 카메라:
  - `_rtsp._tcp.local` — 표준 RTSP 광고
  - `_axis-video._tcp.local` — Axis 전용
  - `_dahua._tcp.local` — Dahua 전용
  - `_onvif._tcp.local` — ONVIF 보조 광고

### Plan G 가 추가하는 가치
1. ONVIF 가 못 잡는 카메라 일부 보완
2. 카메라 호스트명 발견 (예: `CAM-LIVING-01.local`)
3. 산업 표준 hybrid 의 2/3 단계 완성

---

## 1. 기술 결정

### 선택: **`zeroconf` 패키지 + graceful fallback**

| 옵션 | 코드량 | 안정성 | 의존성 부담 |
|---|---|---|---|
| 순수 Python (raw DNS packet) | 150~200줄 | 중간 (에지 케이스 누락 가능) | 0 |
| **`zeroconf` 패키지** ⭐ | **30~50줄** | **높음 (1억 DL+, battle-tested)** | 1 pip 패키지 |

**선택 이유**:
- mDNS DNS-SD 는 binary DNS packet 파싱이라 순수 Python 구현 복잡 + 버그 가능성 ↑
- `zeroconf` 는 가벼움 (의존성 0개), Python 3.7+ 호환, PyInstaller 호환
- import 실패 시 graceful skip → 사용자가 패키지 설치 안 해도 기존 동작 유지

### 안전장치 (3중)
1. `try/except ImportError` → zeroconf 없으면 조용히 skip
2. 환경변수 `COURTVIEW_MDNS_DISCOVERY=off` 로 강제 비활성
3. timeout 강제 (기본 2초) — mDNS browser 가 무한 대기 안 함

---

## 2. 변경할 파일 (3개)

| # | 파일 | 변경 |
|---|------|------|
| 1 | **`infrastructure/discovery/mdns_discovery.py`** (신규) | zeroconf 기반 mDNS browse |
| 2 | `infrastructure/discovery/__init__.py` | mdns_discover export |
| 3 | `api_server/services/camera_service.py` | `discover_many()` Stage 0.5 추가 |
| 4 | `requirements.txt` | `zeroconf>=0.130` 추가 (선택 — 패키지 미설치 시 자동 skip) |

---

## 3. 단계별 상세

### ☑ STEP 1 — `mdns_discovery.py` 신규

핵심 함수:
```python
def mdns_discover(timeout_sec: float = 2.0) -> list[dict[str, object]]:
    """
    mDNS DNS-SD browse — 카메라 표준 서비스 광고 수집.

    Returns: [{"ip": "192.168.1.50", "hostname": "cam01.local",
               "service": "_rtsp._tcp", "port": 554,
               "discovered_by": "mdns"}, ...]
    """
```

탐색 서비스 타입:
- `_rtsp._tcp.local.` (표준)
- `_axis-video._tcp.local.` (Axis)
- `_dahua._tcp.local.` (Dahua)
- `_onvif._tcp.local.` (ONVIF 보조)

구현:
- `Zeroconf()` 인스턴스 1개
- 각 서비스 타입마다 `ServiceBrowser` 등록 → `ServiceListener` 가 `add_service` 콜백 받음
- `timeout_sec` sleep 후 발견된 결과 수집 → Zeroconf.close()

### ☑ STEP 2 — discover_many() Stage 0.5 통합

ONVIF (Stage 0) 와 brute-force (Stage 1~3) 사이에 mDNS 추가:

```python
# Stage 0: ONVIF (기존)
onvif_results = onvif_discover(...)
onvif_ips = {r["ip"] for r in onvif_results}

# Stage 0.5: mDNS — ONVIF 못 찾은 카메라 추가 발견 (병렬 가능하지만 단순화 위해 직렬)
mdns_results = mdns_discover(timeout_sec=2.0)
mdns_ips = {r["ip"] for r in mdns_results}

# brute-force 풀에서 ONVIF + mDNS 발견 IP 제외
all_discovered_ips = onvif_ips | mdns_ips
ips = [ip for ip in ips if ip not in all_discovered_ips]
```

**최적화 포인트**: ONVIF + mDNS 를 **병렬로** 실행하면 2s + 2s 가 아니라 max(2s, 2s) = 2s.
ThreadPoolExecutor 로 두 작업 동시 실행.

### ☑ STEP 3 — requirements.txt 에 zeroconf 추가 (선택적)

```
zeroconf>=0.130
```

미설치 환경에서도 코드는 동작 (try/except). 단 mDNS 효과 0.

---

## 4. 시간 복잡도 (Plan F 와 비교)

### 변수 추가
- **T_mdns** = mDNS browse timeout = 2.0s
- **F_mdns** = mDNS 응답 카메라 수
- **F_brute** = 두 방법 모두 못 찾는 카메라 수 = F - F_onvif - F_mdns

### 직렬 실행 (단순)
- Stage 0: ONVIF (2.0s)
- Stage 0.5: mDNS (2.0s)
- 나머지: brute-force
- **총합: 4.0s + brute-force time**

### 병렬 실행 (Plan G 권장)
ONVIF + mDNS 를 동시에:
```python
with ThreadPoolExecutor(max_workers=2) as pool:
    f_onvif = pool.submit(onvif_discover, ...)
    f_mdns = pool.submit(mdns_discover, ...)
    onvif_results = f_onvif.result()
    mdns_results = f_mdns.result()
```
- **max(T_onvif, T_mdns) = 2.0s**
- 총합: 2.0s + brute-force time (= Plan F 와 동일)

### 시나리오별 실측 예상

| 시나리오 | F_onvif | F_mdns | F_brute | Plan F | **Plan G (병렬)** |
|---|:-:|:-:|:-:|---|---|
| 전부 ONVIF | 8 | 0 | 0 | 2.0 s | **2.0 s** (변화 없음) |
| ONVIF + mDNS 혼합 | 4 | 4 | 0 | 2.0 + 0.6 = 2.6 s | **2.0 s** (개선) |
| 전부 mDNS | 0 | 8 | 0 | 2.0 + 2.5 = 4.5 s | **2.0 s** (대폭 개선) |
| 전부 미지원 (저가) | 0 | 0 | 8 | 4.5 s | **4.5 s** (변화 없음) |

→ **저가 카메라 환경 (우리) 에서는 시간 변화 0**. mDNS 효과는 다른 카메라 환경에서 발휘.

---

## 5. 우리 환경 (저가 IPCam APIPA) 에 대한 정직한 평가

- ONVIF: 응답 안 할 가능성 큼 (이미 Plan F 에서 인지)
- mDNS: **응답 더 가능성 낮음** (저가 카메라 일반적 미지원)
- 따라서 **시간 효과는 거의 없음** — 하지만:
  - 보조 안전망 (혹시 카메라 모델 일부가 mDNS 만 광고)
  - 호스트명 발견 (있다면)
  - 향후 카메라 교체 / 추가 시 표준 호환성 확보

→ 코드 추가의 ROI 는 미래 가치. 즉시 효과 기대 X.

---

## 6. 검증

1. `pip install zeroconf` 실행 (또는 미설치 상태로 graceful skip 확인)
2. launcher 재시작 → 카메라 탐색
3. 로그 확인:
   ```
   [INFO] mDNS discovery 완료: N개 서비스 발견 (X.XXs)
   ```
4. N = 0 이어도 정상 (저가 환경)

---

## 7. 롤백
```powershell
$env:COURTVIEW_MDNS_DISCOVERY = "off"
```

또는 `pip uninstall zeroconf` — 코드는 자동 skip.

---

## 8. Out of Scope
- mDNS 응답 카메라의 SOAP GetStreamUri 호출 — 기존 probe_rtsp_paths 로 보완
- 카메라 모델별 service type DB — 일단 4종만 (RTSP/Axis/Dahua/ONVIF)
- UPnP / SSDP — 별도 Plan H 로

---

## 9. 진행 순서
1. STEP 1: `mdns_discovery.py` 신규
2. STEP 2: `discover_many()` Stage 0.5 + ONVIF/mDNS 병렬 실행
3. STEP 3: requirements.txt 갱신
4. 사용자 검증 (선택)
