# COURTVIEW Desktop Software

> **버전**: 1.0.1 (Desktop Edition)
> **목적**: 데스크톱 소프트웨어 로컬 AI 서버 (Backend only)
> **배포**: Windows EXE, macOS App, Linux AppImage
> **최적화**: App Server 대비 60% 경량화 (로컬 실행 최적화)

---

## 프로젝트 개요

COURTVIEW Desktop은 로컬에서 실행되는 AI 기반 농구 경기 분석 소프트웨어입니다.
프론트엔드는 별도 개발자가 완성했으며, 이 프로젝트는 Backend AI 서버만 포함합니다.

### 핵심 기능

- 🏀 **경기 분석** - 4대 이상 카메라 기반 멀티뷰 분석
- 👨‍⚖️ **AI 심판** - 기본적인 파울/바이올레이션 감지
- 🎯 **전술 분석** - 포메이션, 공격/수비 패턴
- 📍 **슛 위치** - 슛 차트, 히트맵, 효율 분석
- 🎬 **하이라이트** - 자동 하이라이트 생성
- ✂️ **비디오 편집** - 클립 관리, 주석, 다각도 동기화

### 시스템 요구사항

**최소 사양:**
- OS: Windows 10/11, macOS 12+, Ubuntu 20.04+
- CPU: Intel i5 8세대 이상
- GPU: NVIDIA GTX 1660 (6GB) 이상
- RAM: 16GB
- Storage: 500GB SSD

**권장 사양:**
- GPU: NVIDIA RTX 3060 (12GB) 이상
- RAM: 32GB
- Storage: 1TB NVMe SSD

---

## 프로젝트 구조

```
COURTVIEW_DESK/
├── core_foundation/     # 핵심 기반 (config, monitoring, exceptions)
├── shared/              # 공통 유틸리티 (constants, dto, interfaces, utils)
├── configs/             # 설정 파일 (YAML)
├── detection/           # 객체 감지 (ball, court, player, hoop)
├── multi_view/          # 멀티뷰 3D 융합
├── pose_estimation/     # 포즈 추정
├── biomechanics/        # 생체역학
├── game_analysis/       # 경기 분석
├── ai_referee/          # AI 심판 (FIBA, KBL, NBA, NBL)
├── feedback_system/     # 피드백 시스템
├── api_server/          # REST API (localhost:8000)
├── pipeline/            # 분석 파이프라인
├── workers/             # 백그라운드 워커
├── database/            # SQLite 데이터베이스
├── storage/             # 로컬 파일 저장소
└── tests/               # 테스트
```

---

## 설치 및 실행

### 개발 환경 설정

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일 수정 (GPU, 저장소 경로 등)

# 데이터베이스 초기화
python -m database.migrations.init_db

# API 서버 실행
python -m api_server.main
```

### 프로덕션 빌드

```bash
# Windows
cd deployment/windows
build.bat

# macOS
cd deployment/macos
./build.sh

# Linux
cd deployment/linux
./build.sh
```

---

## API 엔드포인트

**Base URL:** `http://localhost:8000`

```
# 경기 분석
POST   /api/v1/game/analyze
GET    /api/v1/game/{game_id}/status
GET    /api/v1/game/{game_id}/result

# AI 심판
POST   /api/v1/referee/analyze
GET    /api/v1/referee/{game_id}/decisions

# 전술 분석
GET    /api/v1/tactical/{game_id}/formations
GET    /api/v1/tactical/{game_id}/patterns

# 하이라이트
GET    /api/v1/game/{game_id}/highlights
POST   /api/v1/game/{game_id}/highlight/create

# 슛 위치
GET    /api/v1/game/{game_id}/shot_chart
GET    /api/v1/game/{game_id}/shot_heatmap
```

---

## 설정

### GPU 설정 (.env)

```bash
# NVIDIA GPU
CUDA_VISIBLE_DEVICES=0
GPU_MEMORY_FRACTION=0.9

# Apple Silicon
METAL_DEVICE=0
```

### 카메라 설정

```yaml
# configs/multi_camera/calibration.yaml
min_cameras: 4
max_cameras: 8
resolution: [1920, 1080]
fps: 60
```

### AI 심판 설정

```yaml
# configs/ai_referee/fiba_rules.yaml
league: fiba
version: 2022
confidence_threshold: 0.75
multi_angle_threshold: 0.75
```

---

## 문서

- [아키텍처 설계](ARCHITECTURE_DESKTOP.md) - 전체 시스템 구조
- [Layer 0: core_foundation](LAYER0_CORE_FOUNDATION.md) - 핵심 기반 모듈 상세
- [Import 규칙](IMPORT_RULES.md) (작성 예정)
- [API 문서](docs/API.md) (작성 예정)
- [배포 가이드](docs/DEPLOYMENT.md) (작성 예정)

---

## 라이선스

상업용 라이선스 (비공개)

---

## 연락처

- 프로젝트: COURTVIEW
- 이메일: support@courtview.com (가상)
