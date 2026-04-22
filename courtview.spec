# -*- mode: python ; coding: utf-8 -*-
"""
COURTVIEW Desktop — PyInstaller Spec (v2)

빌드:
    cd C:\\COURTVIEW_DESK
    pyinstaller courtview.spec

또는:
    python build.py

결과:
    dist/courtview/courtview.exe
    dist/courtview/_internal/      (Python 런타임 + 패키지)
    dist/courtview/weights/        (.pt, .onnx — TensorRT 빌드 소스)
    dist/courtview/courtview_ui/   (UI templates/static/app.py)

단일 폴더(onedir) 배포 — onefile 은 3GB+ 번들에서 압축 해제 비용 큼.
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_submodules, collect_data_files, collect_all, collect_dynamic_libs
)

# =============================================================================
# 경로
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(SPEC))
UI_DIR = os.path.join(os.path.dirname(BASE_DIR), "COURTVIEW-UI")

if not os.path.exists(UI_DIR):
    raise SystemExit(
        f"❌ UI 디렉토리 없음: {UI_DIR}\n"
        f"   C:\\COURTVIEW-UI 가 형제 디렉토리로 존재해야 합니다."
    )

block_cipher = None


# =============================================================================
# Hidden imports — 동적(importlib) 로드되는 COURTVIEW 모듈 자동 수집
# =============================================================================
hidden_imports = []

# 엔진 내부 패키지 — importlib 또는 sc() 로 동적 로드되는 것들 많음
for pkg in (
    "api_server",
    "engine",
    "detection",
    "pose_estimation",
    "biomechanics",
    "motion_analysis",
    "game_analysis",
    "ai_referee",
    "feedback_system",
    "shared",
    "infrastructure",
    "core_foundation",
    "utils",
):
    try:
        hidden_imports += collect_submodules(pkg)
    except Exception:
        # 하위 모듈이 import 오류 있으면 수동 리스트 — 런타임에 실패해도 catch 됨
        hidden_imports.append(pkg)

# FastAPI / Uvicorn / Starlette — 하위 모듈까지 전부 수집 (동적 import 많음)
hidden_imports += [
    # Uvicorn 하위
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops", "uvicorn.loops.auto", "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http", "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    # 기타
    "httpx",
    "websockets",
    "jinja2",
    "python_multipart",
    "email_validator",
    "pydantic",
    "pydantic_core",
    "aiofiles",   # starlette.staticfiles 가 사용
    "anyio",
]

# FastAPI / Starlette 전체 하위 모듈 — staticfiles, templating, routing 등 동적 import 대비
for pkg in ("fastapi", "starlette"):
    try:
        hidden_imports += collect_submodules(pkg)
    except Exception:
        hidden_imports.append(pkg)

# 외부 런처 모듈 (우리가 만든 것)
hidden_imports += [
    "launcher_warmup",
    "launcher_splash",
    "launcher_version",
    "launcher_updater",
    "launcher_workers",   # 자식 프로세스 target 함수 (frozen 호환)
    "tkinter",     # 스플래시용
    "tkinter.ttk",
    "onnx",         # warmup 이 shape 추출에 사용
]

# ONNX Runtime — provider 동적 로드
hidden_imports += [
    "onnxruntime",
    "onnxruntime.capi",
    "onnxruntime.capi._pybind_state",
]

# OpenCV
hidden_imports += ["cv2"]


# =============================================================================
# collect_all — torch / ultralytics / tensorrt : datas + binaries + hiddenimports
# =============================================================================
extra_datas = []
extra_binaries = []

# TensorRT 는 3개 pip 패키지로 쪼개져있음 (CUDA 버전별):
#   tensorrt            — 메인 Python 바인딩
#   tensorrt_cu13       — CUDA 13 wheel 메타 (실제로 CUDA 12.8+ 에서도 호환)
#   tensorrt_cu13_libs  — 실제 DLL (~375MB, nvinfer_*.dll) ← 빠지면 TRT import 실패
#   tensorrt_cu13_bindings
# 구 CUDA 12 환경이면 tensorrt_cu12_* 로 교체 필요.
TRT_PKGS = ("tensorrt", "tensorrt_cu13", "tensorrt_cu13_libs", "tensorrt_cu13_bindings",
            "tensorrt_cu12", "tensorrt_cu12_libs", "tensorrt_cu12_bindings")

for pkg in ("torch", "torchvision", "ultralytics") + TRT_PKGS:
    try:
        datas, binaries, hi = collect_all(pkg)
        extra_datas += datas
        extra_binaries += binaries
        hidden_imports += hi
        print(f"  [collect_all] {pkg}: datas={len(datas)} binaries={len(binaries)} hiddenimports={len(hi)}")
    except Exception as e:
        # 존재하지 않는 선택적 패키지는 조용히 skip (예: tensorrt_cu12_* 가 설치 안 됐으면)
        print(f"  [skip] collect_all({pkg}): {type(e).__name__}")

# TensorRT DLL 은 collect_all 이 못 잡는 경우가 있어 명시적으로 한번 더
for libs_pkg in ("tensorrt_libs", "tensorrt_cu13_libs", "tensorrt_cu12_libs"):
    try:
        libs = collect_dynamic_libs(libs_pkg)
        if libs:
            extra_binaries += libs
            print(f"  [collect_dynamic_libs] {libs_pkg}: {len(libs)} DLL")
    except Exception:
        pass


# =============================================================================
# 데이터 파일 — 소스 디렉토리 그대로 번들
# =============================================================================
project_datas = [
    # 설정
    ("configs", "configs"),
    # 가중치 (.pt + .onnx — TensorRT 빌드 소스)
    # .engine 은 tensorrt_cache 가 런타임 생성하므로 번들 제외
    ("weights", "weights"),
    # UI
    (os.path.join(UI_DIR, "templates"), "courtview_ui/templates"),
    (os.path.join(UI_DIR, "static"), "courtview_ui/static"),
    (os.path.join(UI_DIR, "app.py"), "courtview_ui"),
]

# build.py 가 생성한 버전 파일 (있으면 번들에 포함)
if os.path.exists(os.path.join(BASE_DIR, "_build_version.json")):
    project_datas.append(("_build_version.json", "."))


# =============================================================================
# Analysis
# =============================================================================
a = Analysis(
    ["launcher.py"],
    pathex=[BASE_DIR, UI_DIR],
    binaries=extra_binaries,
    datas=project_datas + extra_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 개발/테스트 전용 — 번들 크기 축소
        "matplotlib",
        "matplotlib.pyplot",
        "jupyter",
        "jupyter_core",
        "notebook",
        "IPython",
        "ipywidgets",
        "pytest",
        "pytest_asyncio",
        "mypy",
        "black",
        "pylint",
        # GUI 프레임워크 중복
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "wx",
        # torch 불필요 서브 — 학습/프로파일링 관련
        "torch.distributed",
        "torch.onnx.utils",   # export 는 우리가 개발PC에서만 하고 런타임엔 불필요
        "torch.utils.tensorboard",
        "torchaudio",
        # 기타
        "sphinx",
        "sphinx_rtd_theme",
        "pip",
        "setuptools",
        "wheel",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


# =============================================================================
# 제외 파일 필터 (바이너리·데이터에서 특정 패턴 제외)
# - recordings/, _appdata/, tensorrt_cache/, logs/ 등 런타임 생성물
# - __pycache__, .pyc
# - 미사용·구버전 모델 가중치 (번들 크기 감축)
# =============================================================================

# 미사용 모델 파일 (weights/ 내 특정 파일명 — 정확 매칭)
UNUSED_WEIGHTS = {
    # Depth 추정 — 미사용
    "depth_anything_vitl14.pth",
    # HRNet — 미사용 (VitPose 가 대체)
    "hrnet_w48_coco_256x192.pth",
    # ByteTrack x — 미사용
    "bytetrack_x_mot17.pth.tar",
    # VitPose H/S — 미사용 (L/B 만 사용)
    "vitpose_h_wholebody_data.bin",
    "vitpose-s-wholebody.onnx",
    # Digit 구버전
    "CV-Digit_v2.0.0.cv",
    # YOLOv8 pose — YOLO11 로 교체됨, 구버전 번들 제외
    "yolov8l-pose.pt", "yolov8l-pose.onnx",
    "yolov8m-pose.pt", "yolov8m-pose.onnx",
    "yolov8x-pose.pt", "yolov8x-pose.onnx",
    "yolov8s.onnx",
}


def _exclude_runtime_artifacts(toc_list):
    """(src, dest, type) tuples 에서 런타임 생성물 + 미사용 모델 제거."""
    skip_patterns = (
        # 런타임 생성물
        "recordings/", "recordings\\",
        "_appdata/", "_appdata\\",
        "tensorrt_cache/", "tensorrt_cache\\",
        "logs/", "logs\\",
        "cloud_sync_queue/", "cloud_sync_queue\\",
        # 개발 잔재
        "__pycache__", ".pyc", ".pyo",
        ".git", ".pytest_cache", ".vscode",
        "tests/", "tests\\", "test_",
        # 엔진 캐시 (런타임 생성) + 백업
        ".engine", ".engine.bak",
    )
    filtered = []
    removed = 0
    removed_size = 0
    for entry in toc_list:
        src = str(entry[0]).replace("\\", "/").lower()
        src_basename = src.rsplit("/", 1)[-1]

        # 1. 런타임 artifacts · .engine 등
        if any(p.lower() in src for p in skip_patterns):
            removed += 1
            try:
                removed_size += os.path.getsize(entry[0])
            except Exception:
                pass
            continue

        # 2. 미사용 모델 파일명 (basename 정확 매칭, 대소문자 무시)
        bn = os.path.basename(str(entry[0]))
        if bn in UNUSED_WEIGHTS:
            removed += 1
            try:
                removed_size += os.path.getsize(entry[0])
            except Exception:
                pass
            continue

        filtered.append(entry)

    if removed:
        print(f"  [exclude] 제거: {removed} 파일 (~{removed_size / 1024**2:.0f} MB)")
    return filtered


a.datas = _exclude_runtime_artifacts(a.datas)
a.binaries = _exclude_runtime_artifacts(a.binaries)


# =============================================================================
# PYZ: 바이트코드 아카이브
# =============================================================================
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


# =============================================================================
# EXE: 실행 파일 (bootstrap)
# =============================================================================
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="courtview",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX 금지 — torch/CUDA DLL 손상 위험
    console=True,              # 로그 확인용 (배포 시 False 로 변경 가능)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                 # 아이콘 준비되면: "assets/icon.ico"
)


# =============================================================================
# COLLECT: onedir 출력 (폴더 배포)
# =============================================================================
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="courtview",
)
