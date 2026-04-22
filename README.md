# COURTVIEW Desktop

SPOIN 농구 분석 데스크톱 애플리케이션. 실시간 파울·바이올레이션 판정, 전술·통계 분석, 코치·선수 피드백 자동 생성. Windows 데스크톱 환경에서 로컬 GPU 를 활용해 오프라인 분석을 수행하고, S3 기반 auto-update 로 배포됩니다.

**UI 는 별도 레포**: [SPOIN-Inc/courtview_ui](https://github.com/SPOIN-Inc/courtview_ui)

---

## 아키텍처

```
[Splash] → [launcher.py]
              ├── launcher_updater.py   (S3 latest.json, SHA-256 검증, helper swap)
              ├── launcher_warmup.py    (TensorRT 엔진 사전 빌드)
              └── launcher_workers.py
                    ├── engine (api_server)    localhost:8000   ← 본체
                    └── UI     (../COURTVIEW-UI) localhost:3000
```

### 모듈 구조

| 디렉토리 | 역할 |
|---|---|
| `core_foundation/` | Layer 0 공통 기반 (config/registry/resilience/monitoring/security) |
| `shared/` | constants, DTO, types, utils, interfaces |
| `infrastructure/` | 스토리지 경로(AppData/Roaming), 카메라, 전처리, 이벤트 버스 |
| `detection/` | YOLO11/YOLOv8 + ByteTrack + CV-BBox/Digit ONNX |
| `pose_estimation/` | ViTPose(b/l) + HRNet, TensorRT 백엔드 |
| `biomechanics/`, `motion_analysis/` | 관절·동작 분석 |
| `game_analysis/` | 팀/플레이/통계/경기 관리 |
| `ai_referee/` | 파울·바이올레이션 판정 + 증거 추출 + 다각도 검증 |
| `feedback_system/` | 코치·선수용 피드백 생성 |
| `engine/` | 분석 파이프라인 오케스트레이터 (frame→event→period→possession→postgame) |
| `api_server/` | FastAPI + WebSocket 라우트 |
| `launcher*.py` | 런처 + auto-update + 워밍업 + multiprocess 워커 |
| `build.py`, `release.py`, `courtview.spec` | PyInstaller 빌드 + S3 릴리즈 |

---

## 시스템 요구사항

| 항목 | 최소 | 권장 |
|---|---|---|
| OS | Windows 10/11 | Windows 11 |
| GPU | NVIDIA GTX 1660 (6GB) | RTX 4070 (12GB) 이상 |
| CPU | Intel i5 8세대 | Intel i7 12세대 이상 |
| RAM | 16 GB | 32 GB |
| Storage | 500 GB SSD | 1 TB NVMe |
| CUDA | 12.8+ (tensorrt_cu13 번들) | 동일 |

---

## 개발 환경 셋업

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**주의: `weights/` 는 내부 보안 대상** — GitHub/S3 어디에도 없습니다. 사내 공유/NAS 에서 수동 복사하세요. 빌드 시 `C:\COURTVIEW_DESK\weights\` 에 필요한 `.onnx`/`.pt` 전부 있어야 합니다.

**빌드 시 UI 레포도 병렬 체크아웃**:
```
C:\COURTVIEW_DESK\     ← 이 레포
C:\COURTVIEW-UI\       ← courtview_ui 레포 (spec 이 ../COURTVIEW-UI 참조)
```

### 로컬 개발 실행

```bash
python launcher.py            # 런처 (splash → workers)
# 또는 frozen 없이 각 서버 직접
python -m api_server.main     # 엔진 :8000
cd ..\COURTVIEW-UI && python app.py   # UI :3000
```

---

## 빌드 · 릴리즈 파이프라인

```bash
# 1. 번들 빌드 + zip + SHA-256
python build.py X.Y.Z --clean --zip

# 2. S3 업로드 (zip + manifest + latest.json 포인터)
python release.py X.Y.Z --channel beta|stable [--mandatory] [--notes "..."]
```

`--mandatory` 플래그를 쓰면 고객이 업데이트 스킵 불가. `--notes` 는 `latest.json` 에 포함되어 런타임에 UI 로 표시 가능.

### S3 구조

```
s3://courtview-releases/
  ├── beta/
  │   ├── latest.json                         (Cache-Control: max-age=60)
  │   ├── vX.Y.Z/courtview-X.Y.Z.zip
  │   ├── vX.Y.Z/courtview-X.Y.Z.sha256
  │   └── vX.Y.Z/manifest.json
  └── stable/  (동일 구조)
```

### Auto-update 동작

1. 런처 시작 → `DEFAULT_LATEST_URL` 의 `latest.json` 조회
2. 새 버전 발견 시 zip 다운로드 → **SHA-256 검증**
3. `install.parent` 에 staging 폴더로 압축 해제
4. Helper `.bat` 을 `CREATE_NO_WINDOW + cwd=install.parent` 로 spawn
5. `move install → backup_<ts>`, `move staging → install` (errorlevel 실패 시 롤백, `_courtview_swap.log` 기록)
6. `start` 로 새 exe 자동 기동

검증된 주요 수정점:
- `build.py`: 버전에 dot 포함 시 `Path.with_suffix` 버그 → 파일명 직접 조립
- `launcher_warmup.py`: `_default_dims_for` 모델 stem 기반 입력 shape (YOLO=640×640, ViTPose=256×192)
- `launcher_updater.py`: helper cmd 의 cwd 를 install 외부로 지정 (install 폴더 잠김 회피)

---

## 런타임 경로

| 목적 | 경로 |
|---|---|
| 설치 | `C:\Program Files\COURTVIEW\` (installer 시) / `dist\courtview\` (개발) |
| AppData | `%APPDATA%\COURTVIEW\` (`tensorrt_cache/`, `logs/`, `games/`, `cloud_sync_queue/`) |
| Recordings | `D:\COURTVIEW_Recordings\` (설정으로 재정의 가능) |
| Engine API | `http://localhost:8000` |
| UI | `http://localhost:3000` |

---

## 문서

- `ARCHITECTURE_DESKTOP.md` — 데스크톱 아키텍처 상세
- `ARCHITECTURE_REFERENCE.md` — 모듈 간 계약/참조 레퍼런스
- `CLAUDE.md` — 개발 지침 (Claude Code 협업용)
- `docs/audit/NN_<module>.md` — 모듈별 감사 로그 (MODULE_AUDIT_STANDARD)
- `docs/` — 기타 설계/운영 문서

---

## 라이선스

상업용 라이선스 (SPOIN-Inc 비공개 소유)
