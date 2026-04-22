# -*- coding: utf-8 -*-
"""
COURTVIEW 캘리브레이션 포인트 피커

8대 카메라 프레임에서 코트 교차점을 마우스로 클릭하여
pixel 좌표를 수집하고 JSON으로 저장합니다.

사용법:
    python tools/calibration_point_picker.py

조작법:
    - 좌클릭: 포인트 추가
    - 우클릭: 마지막 포인트 삭제 (Undo)
    - N키: 다음 카메라
    - P키: 이전 카메라
    - S키: 현재까지 저장
    - R키: 현재 카메라 포인트 전체 리셋
    - Q키: 저장 후 종료
    - ESC: 저장 없이 종료

출력:
    configs/calibration/pixel_points.json
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

# =============================================================================
# 설정
# =============================================================================

VIDEO_DIR = "D:/SPOIN/training/videos/2nd_real_test_T/20260410_201400"

CAM_FILES = {
    "cam_0": f"{VIDEO_DIR}/cam1.mp4",
    "cam_1": f"{VIDEO_DIR}/cam2.mp4",
    "cam_2": f"{VIDEO_DIR}/cam3.mp4",
    "cam_3": f"{VIDEO_DIR}/cam4.mp4",
    "cam_4": f"{VIDEO_DIR}/cam5.mp4",
    "cam_5": f"{VIDEO_DIR}/cam6.mp4",
    "cam_6": f"{VIDEO_DIR}/cam7.mp4",
    "cam_7": f"{VIDEO_DIR}/cam8.mp4",
}

# 프레임 추출 위치 (경기 중 코트 라인이 잘 보이는 프레임)
FRAME_INDEX = 100

# 출력 경로
OUTPUT_PATH = Path("configs/calibration/pixel_points.json")

# 표시용 FIBA 코트 교차점 이름 (참고용)
# UI calibrate.html KEYPOINTS 순서와 동일
POINT_NAMES = [
    # 코트 코너 (4)
    "corner_TL", "corner_TR", "corner_BL", "corner_BR",
    # 하프라인 + 센터 (3)
    "half_T", "half_B", "center",
    # 왼쪽 페인트 (4)
    "paint_L_TL", "paint_L_TR", "paint_L_BL", "paint_L_BR",
    # 오른쪽 페인트 (4)
    "paint_R_TL", "paint_R_TR", "paint_R_BL", "paint_R_BR",
    # 왼쪽 3점 (3 — 아크 optional 제외)
    "tpt_L_base_T", "tpt_L_base_B", "tpt_L_peak",
    # 오른쪽 3점 (3 — 아크 optional 제외)
    "tpt_R_base_T", "tpt_R_base_B", "tpt_R_peak",
]

# FIBA 코트 실좌표 (m) — UI calibrate.html KEYPOINTS와 동일
# 원점: corner_TL = (0, 0), x축: 엔드라인→엔드라인 (28m), y축: 사이드→사이드 (15m)
FIBA_COURT_POINTS = {
    "corner_TL": (0.0, 0.0),
    "corner_TR": (28.0, 0.0),
    "corner_BL": (0.0, 15.0),
    "corner_BR": (28.0, 15.0),
    "half_T": (14.0, 0.0),
    "half_B": (14.0, 15.0),
    "center": (14.0, 7.5),
    "paint_L_TL": (5.8, 5.05),
    "paint_L_TR": (0.0, 5.05),
    "paint_L_BL": (5.8, 9.95),
    "paint_L_BR": (0.0, 9.95),
    "paint_R_TL": (22.2, 5.05),
    "paint_R_TR": (28.0, 5.05),
    "paint_R_BL": (22.2, 9.95),
    "paint_R_BR": (28.0, 9.95),
    "tpt_L_base_T": (0.0, 0.9),
    "tpt_L_base_B": (0.0, 14.1),
    "tpt_L_peak": (8.325, 7.5),
    "tpt_R_base_T": (28.0, 0.9),
    "tpt_R_base_B": (28.0, 14.1),
    "tpt_R_peak": (19.675, 7.5),
}


# =============================================================================
# 글로벌 상태
# =============================================================================

class State:
    cam_idx: int = 0
    cam_ids: list = []
    frames: dict = {}
    points: dict = {}  # {cam_id: [(px, py, point_name), ...]}
    dragging: bool = False


state = State()
WINDOW = "COURTVIEW Calibration Point Picker"


# =============================================================================
# 마우스 콜백
# =============================================================================

def mouse_callback(event, x, y, flags, param):
    cam_id = state.cam_ids[state.cam_idx]
    # 확대 좌표 → 원본 좌표로 변환
    scale = 2
    ox, oy = x // scale, y // scale

    if event == cv2.EVENT_LBUTTONDOWN:
        # 좌클릭: 포인트 추가 (원본 좌표로 저장)
        pts = state.points[cam_id]
        idx = len(pts)
        name = POINT_NAMES[idx] if idx < len(POINT_NAMES) else f"pt_{idx}"
        pts.append((ox, oy, name))
        print(f"  [{cam_id}] #{idx}: ({ox}, {oy}) → {name}")
        draw_frame()

    elif event == cv2.EVENT_RBUTTONDOWN:
        # 우클릭: 마지막 포인트 삭제
        pts = state.points[cam_id]
        if pts:
            removed = pts.pop()
            print(f"  [{cam_id}] Undo: {removed[2]} ({removed[0]}, {removed[1]})")
            draw_frame()


# =============================================================================
# 화면 그리기
# =============================================================================

def draw_frame():
    cam_id = state.cam_ids[state.cam_idx]
    frame = state.frames[cam_id].copy()
    h, w = frame.shape[:2]

    # 확대 (640x480 → 1280x960)
    scale = 2
    frame = cv2.resize(frame, (w * scale, h * scale), interpolation=cv2.INTER_LINEAR)

    pts = state.points[cam_id]

    # 포인트 그리기
    for i, (px, py, name) in enumerate(pts):
        sx, sy = px * scale, py * scale
        # 원
        cv2.circle(frame, (sx, sy), 6, (0, 255, 0), -1)
        cv2.circle(frame, (sx, sy), 8, (255, 255, 255), 1)
        # 라벨
        label = f"{i}: {name}"
        cv2.putText(frame, label, (sx + 10, sy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

    # 포인트 간 연결선 (순서대로)
    if len(pts) >= 2:
        for i in range(len(pts) - 1):
            p1 = (pts[i][0] * scale, pts[i][1] * scale)
            p2 = (pts[i + 1][0] * scale, pts[i + 1][1] * scale)
            cv2.line(frame, p1, p2, (0, 200, 200), 1)

    # 상단 정보 바
    info_h = 50
    cv2.rectangle(frame, (0, 0), (frame.shape[1], info_h), (30, 30, 30), -1)
    cam_label = f"{cam_id} ({state.cam_idx + 1}/{len(state.cam_ids)})  |  Points: {len(pts)}"
    cv2.putText(frame, cam_label, (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # 다음 찍을 포인트 힌트
    next_idx = len(pts)
    if next_idx < len(POINT_NAMES):
        hint = f"Next: {POINT_NAMES[next_idx]}"
    else:
        hint = "Next: custom point"
    cv2.putText(frame, hint, (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)

    # 하단 조작법
    controls = "LClick:Add | RClick:Undo | Space:Skip | N:NextCam | P:PrevCam | S:Save | R:Reset | Q:Quit"
    cv2.putText(frame, controls, (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

    cv2.imshow(WINDOW, frame)


# =============================================================================
# 저장
# =============================================================================

def save_points():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    data = {}
    for cam_id, pts in state.points.items():
        if not pts:
            continue
        # SKIP 포인트 제외
        valid = [(p[0], p[1], p[2]) for p in pts if not p[2].startswith("SKIP_")]
        if not valid:
            continue

        pixel_points = [[p[0], p[1]] for p in valid]
        point_names = [p[2] for p in valid]

        # FIBA 실좌표 매핑
        court_points = []
        for name in point_names:
            if name in FIBA_COURT_POINTS:
                court_points.append(list(FIBA_COURT_POINTS[name]))
            else:
                court_points.append([0.0, 0.0])

        data[cam_id] = {
            "pixel_points": pixel_points,
            "court_points": court_points,
            "point_names": point_names,
            "point_count": len(valid),
            "skipped_count": len(pts) - len(valid),
        }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total = sum(d["point_count"] for d in data.values())
    print(f"\n[SAVED] {OUTPUT_PATH} ({len(data)}cam, {total}pts)")
    return data


# =============================================================================
# 메인
# =============================================================================

def main():
    print("=" * 60)
    print("COURTVIEW 캘리브레이션 포인트 피커")
    print("=" * 60)
    print(f"포인트 이름 순서: {', '.join(POINT_NAMES[:8])} ...")
    print()

    # 프레임 추출
    state.cam_ids = list(CAM_FILES.keys())

    for cam_id, path in CAM_FILES.items():
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"[FAIL] {cam_id}: {path}")
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, FRAME_INDEX)
        ret, frame = cap.read()
        cap.release()
        if ret:
            state.frames[cam_id] = frame
            state.points[cam_id] = []
            print(f"[OK] {cam_id}: {frame.shape[1]}x{frame.shape[0]}")
        else:
            print(f"[FAIL] {cam_id}: 프레임 읽기 실패")

    if not state.frames:
        print("[ERROR] 유효한 프레임 없음")
        return

    # 기존 저장 파일 있으면 로드
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            for cam_id, d in existing.items():
                if cam_id in state.points:
                    state.points[cam_id] = [
                        (px[0], px[1], name)
                        for px, name in zip(d["pixel_points"], d["point_names"])
                    ]
                    print(f"[LOAD] {cam_id}: {len(state.points[cam_id])}pts 복원")
        except Exception:
            pass

    # 윈도우 생성
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW, mouse_callback)

    print(f"\n카메라 {len(state.frames)}대 준비 완료. 클릭하세요.")
    print("코트 교차점을 보이는 대로 순서 상관없이 클릭하세요.")
    print("포인트 이름은 순서대로 자동 배정됩니다.\n")

    draw_frame()

    while True:
        key = cv2.waitKey(0) & 0xFF

        if key == ord("q"):
            # 저장 후 종료
            save_points()
            break

        elif key == 27:  # ESC
            print("[EXIT] 저장 없이 종료")
            break

        elif key == ord("n"):
            # 다음 카메라
            state.cam_idx = (state.cam_idx + 1) % len(state.cam_ids)
            cam_id = state.cam_ids[state.cam_idx]
            print(f"\n>>> {cam_id} ({state.cam_idx + 1}/{len(state.cam_ids)})")
            draw_frame()

        elif key == ord("p"):
            # 이전 카메라
            state.cam_idx = (state.cam_idx - 1) % len(state.cam_ids)
            cam_id = state.cam_ids[state.cam_idx]
            print(f"\n>>> {cam_id} ({state.cam_idx + 1}/{len(state.cam_ids)})")
            draw_frame()

        elif key == ord("s"):
            # 중간 저장
            save_points()

        elif key == ord(" "):
            # 스페이스바: 현재 포인트 스킵 (안 보이는 교차점)
            cam_id = state.cam_ids[state.cam_idx]
            pts = state.points[cam_id]
            idx = len(pts)
            name = POINT_NAMES[idx] if idx < len(POINT_NAMES) else f"pt_{idx}"
            pts.append((-1, -1, f"SKIP_{name}"))
            print(f"  [{cam_id}] #{idx}: SKIP → {name} (안 보임)")
            draw_frame()

        elif key == ord("r"):
            # 현재 카메라 리셋
            cam_id = state.cam_ids[state.cam_idx]
            state.points[cam_id] = []
            print(f"[RESET] {cam_id}")
            draw_frame()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
