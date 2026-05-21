# -*- coding: utf-8 -*-
"""T/B 포맷 자동 감지 + 카메라별 파일 목록 정렬.

T (COURTVIEW DESK 녹화 그대로):
    root/
      2026-04-16_230745/
        cam1_Q1.ts, cam1_Q2.ts, ... cam2_Q1.ts ... cam8_Q4.ts

B (3분 컷 + sync.json):
    root/
      L1(CAM3)/
        20230303122517_000001.MP4
        20230303122517_000002.MP4
        ...
      sync.json   (reference 카메라, offset_from_ref_sec, anchor_sec_from_file01)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


FormatKind = Literal["T", "B", "UNKNOWN"]


@dataclass
class CameraStream:
    """단일 카메라의 정렬된 입력 파일 목록 + sync 정보."""

    folder_name: str            # B: "L1(CAM3)", T: "cam1"
    cam_label: str              # 사용자 친화 라벨 (B: "L1", T: "cam1")
    cam_native_id: str          # 원본 카메라 식별자 (B: "CAM3", T: "1")
    files: list[Path] = field(default_factory=list)  # 순서대로 정렬된 mp4/ts
    offset_sec: float = 0.0     # B: sync 기준 + anchor 보정. T: 항상 0
    total_duration_sec: float = 0.0  # 0 이면 미상 (probe 안 함)


@dataclass
class DetectedSession:
    """검출된 단일 세션 (분석 단위)."""

    kind: FormatKind
    root: Path
    session_label: str          # T: 폴더 timestamp, B: root 폴더명
    cameras: list[CameraStream] = field(default_factory=list)
    sync_reference: str = ""    # B 만 사용
    file_duration_sec: float = 0.0  # B 의 단일 파일 길이 (180.0 등)


_T_TS_RE = re.compile(r"^(cam\d+)_Q(\d+)(?:_part(\d+))?\.(?:ts|mp4)$", re.IGNORECASE)
_B_FOLDER_RE = re.compile(r"^([LR]\d+)\(CAM(\d+)\)$")
_B_FILE_RE = re.compile(r".+_(\d{6})\.MP4$", re.IGNORECASE)


# =============================================================================
# 감지
# =============================================================================
def detect(root: Path) -> DetectedSession:
    """루트 폴더로부터 T/B 포맷 자동 감지.

    T 는 root 가 세션 폴더 자체이거나(cam<n>_Q<n>.ts 직접 포함),
    하위에 세션 폴더 1개 이상을 가진 경우. 세션 폴더 1개만 골라 반환.

    B 는 root 안에 sync.json + 카메라별 폴더(`L*(CAM*)`).

    추가: root 의 하위 1단계에서 sync.json 또는 T 세션을 자동 탐색
    (사용자가 부모 폴더를 잘못 선택해도 동작).
    """
    if not root.exists() or not root.is_dir():
        return DetectedSession(kind="UNKNOWN", root=root, session_label=root.name)

    # B 형식 우선 (sync.json 존재 여부)
    sync_json = root / "sync.json"
    if sync_json.exists():
        return _detect_b(root, sync_json)

    # T 형식 — root 자체가 세션이거나 하위에 세션 폴더가 있는지
    if _has_t_files(root):
        return _detect_t_session(root)

    # 하위 1단계에서 sync.json 가진 폴더 탐색 (B 폴더 부모를 선택한 경우)
    # 카메라 0개로 감지된 경우는 패스하고 다음 후보로 — 잘못된 sync.json 회피
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        child_sync = child / "sync.json"
        if child_sync.exists():
            cand = _detect_b(child, child_sync)
            if cand.cameras:
                return cand

    # 하위에 T 세션 폴더가 1개라도 있으면 첫 번째 사용
    for child in sorted(root.iterdir()):
        if child.is_dir() and _has_t_files(child):
            return _detect_t_session(child)

    return DetectedSession(kind="UNKNOWN", root=root, session_label=root.name)


def list_t_sessions(root: Path) -> list[Path]:
    """T 폴더 안의 세션 폴더 목록 (사용자가 GUI 에서 선택용)."""
    if not root.exists():
        return []
    if _has_t_files(root):
        return [root]
    return [c for c in sorted(root.iterdir()) if c.is_dir() and _has_t_files(c)]


# =============================================================================
# T 파서
# =============================================================================
def _has_t_files(folder: Path) -> bool:
    for f in folder.glob("cam*"):
        if _T_TS_RE.match(f.name):
            return True
    return False


def _detect_t_session(session_dir: Path) -> DetectedSession:
    sess = DetectedSession(
        kind="T",
        root=session_dir,
        session_label=session_dir.name,
    )
    by_cam: dict[str, list[tuple[int, int, Path]]] = {}
    for f in session_dir.iterdir():
        m = _T_TS_RE.match(f.name)
        if not m:
            continue
        cam = m.group(1)
        q = int(m.group(2))
        part = int(m.group(3)) if m.group(3) else 1
        by_cam.setdefault(cam, []).append((q, part, f))

    for cam in sorted(by_cam.keys()):
        items = sorted(by_cam[cam])  # (q, part, path)
        files = [p for (_, _, p) in items]
        # cam1 → cam_native_id="1"
        m = re.match(r"^cam(\d+)$", cam)
        native = m.group(1) if m else cam
        sess.cameras.append(
            CameraStream(
                folder_name=cam,
                cam_label=cam,
                cam_native_id=native,
                files=files,
                offset_sec=0.0,
            )
        )
    return sess


# =============================================================================
# B 파서
# =============================================================================
def _detect_b(root: Path, sync_path: Path) -> DetectedSession:
    sync = json.loads(sync_path.read_text(encoding="utf-8"))
    file_dur = float(sync.get("file_duration_sec", 180.0))
    ref = str(sync.get("reference", ""))
    cam_map: dict = sync.get("cameras", {})

    sess = DetectedSession(
        kind="B",
        root=root,
        session_label=root.name,
        sync_reference=ref,
        file_duration_sec=file_dur,
    )

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        m = _B_FOLDER_RE.match(child.name)
        if not m:
            continue
        cam_label = m.group(1)        # L1 / R3 ...
        cam_native = f"CAM{m.group(2)}"
        meta = cam_map.get(child.name, {})
        offset_ref = float(meta.get("offset_from_ref_sec", 0.0))
        anchor = float(meta.get("anchor_sec_from_file01", 0.0))

        # mp4 정렬 (000001 → 000002 → ...)
        mp4_with_idx: list[tuple[int, Path]] = []
        for f in child.iterdir():
            mm = _B_FILE_RE.match(f.name)
            if mm:
                mp4_with_idx.append((int(mm.group(1)), f))
        mp4_with_idx.sort()
        files = [p for (_, p) in mp4_with_idx]

        sess.cameras.append(
            CameraStream(
                folder_name=child.name,
                cam_label=cam_label,
                cam_native_id=cam_native,
                files=files,
                # 분석 시작 시점을 reference 의 anchor 로 맞추기 위해
                # (anchor - offset_ref) 만큼 이 카메라에서 앞쪽을 잘라냄.
                # offset_sec 양수 = 이 카메라 영상 앞 N초 skip.
                offset_sec=max(0.0, anchor - offset_ref),
            )
        )
    return sess
