# 📦 Archive — 완료/보관된 문서

> 완료된 PLAN 문서와 과거 작업 이력. 참조용으로만 사용.

## 폴더 구조

```
archive/
├── completed/                       완료된 PLAN_*.md (4개)
└── camera-2026-05-13/               카메라 발견 시리즈 (9개)
```

---

## 📁 completed/ — 완료된 작업

| 파일 | 완료 내용 |
|---|---|
| [PLAN_BACKEND_FINALIZE_SAFETY.md](completed/PLAN_BACKEND_FINALIZE_SAFETY.md) | UI 미호출 시 최소 manifest 안전망 (STEP 1~4 완료) |
| [PLAN_FFMPEG_STDERR_CAPTURE.md](completed/PLAN_FFMPEG_STDERR_CAPTURE.md) | RTSP 재연결 원인 규명 (STEP 1~5 완료) |
| [PLAN_MEMORY_USAGE_AUDIT.md](completed/PLAN_MEMORY_USAGE_AUDIT.md) | RAM/VRAM 감사 — 상위 5대 항목 파악 |
| [PLAN_REPLAY_STOP_FIX.md](completed/PLAN_REPLAY_STOP_FIX.md) | REPLAY STOP finalize + navigation (STEP 1~5 완료) |

---

## 📷 camera-2026-05-13/ — 카메라 발견 시스템 시리즈

2026-05-13 작성된 카메라 수신부 최적화 + 산업표준 발견 알고리즘 시리즈 (A~H).

| 파일 | 주제 |
|---|---|
| [_plan_A_go2rtc_healthcheck_2026-05-13.md](camera-2026-05-13/_plan_A_go2rtc_healthcheck_2026-05-13.md) | go2rtc 헬스체크 + Fallback 가시화 |
| [_plan_B_hwaccel_2026-05-13.md](camera-2026-05-13/_plan_B_hwaccel_2026-05-13.md) | ffmpeg HW 디코딩 (D3D11VA/CUDA) — CPU 80% 감소 |
| [_plan_C_reconnect_cooldown_2026-05-13.md](camera-2026-05-13/_plan_C_reconnect_cooldown_2026-05-13.md) | 재연결 임계값 완화 + 쿨다운 |
| [_plan_D_ffmpeg_prescale_2026-05-13.md](camera-2026-05-13/_plan_D_ffmpeg_prescale_2026-05-13.md) | ffmpeg 사전 리사이즈 — cv2.resize 제거 |
| [_plan_E_flow_logs_2026-05-13.md](camera-2026-05-13/_plan_E_flow_logs_2026-05-13.md) | 카메라 → 분석 데이터 흐름 로그 |
| [_plan_F_onvif_discovery_2026-05-13.md](camera-2026-05-13/_plan_F_onvif_discovery_2026-05-13.md) | ONVIF WS-Discovery |
| [_plan_G_mdns_discovery_2026-05-13.md](camera-2026-05-13/_plan_G_mdns_discovery_2026-05-13.md) | mDNS/Zeroconf |
| [_plan_H_upnp_discovery_2026-05-13.md](camera-2026-05-13/_plan_H_upnp_discovery_2026-05-13.md) | UPnP/SSDP — 가정용 IPCam |
| [_session_changes_2026-05-13.md](camera-2026-05-13/_session_changes_2026-05-13.md) | 2026-05-13 세션 변경 로그 (전반) |

→ A~H 완료 시 **"2026 산업 표준 multi-protocol hybrid"** 카메라 발견 시스템 완성.

---

## 관련 문서

- [../plans/README.md](../plans/README.md) — 진행 중 PLAN
- [../INDEX.md](../INDEX.md) — docs 전체 인덱스
- [../MainTODO.md](../MainTODO.md) — 성능 최적화 트랙
