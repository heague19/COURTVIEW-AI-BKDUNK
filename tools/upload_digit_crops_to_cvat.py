"""
tools/upload_digit_crops_to_cvat.py
digit_v4 크롭을 CVAT 태스크에 업로드

태스크 ID는 하드코딩 (프로젝트 18, 태스크 133-139)
"""

import os
import sys
import time
import requests
import glob

CVAT_URL = "http://localhost:8080"
USERNAME = "spoin"
PASSWORD = "ghltk@2026"

# 리그별 태스크 ID
TASKS = {
    "kbl": 133,
    "bleague": 134,
    "euroleague": 135,
    "PBA": 136,
    "fiba": 137,
    "ncaa": 138,
    "KOREA_amature": 139,
}

CROPS_ROOT = "D:/SPOIN/training/datasets/digit_v4_crops"

# CVAT 업로드 배치 크기 (한번에 보낼 파일 수)
BATCH_SIZE = 500


def get_token():
    r = requests.post(f"{CVAT_URL}/api/auth/login", json={
        "username": USERNAME, "password": PASSWORD
    })
    return r.json()["key"]


def upload_images(task_id: int, image_paths: list, token: str, league: str):
    """이미지를 CVAT 태스크에 배치 업로드."""
    headers = {"Authorization": f"Token {token}"}

    total = len(image_paths)
    uploaded = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = image_paths[batch_start:batch_start + BATCH_SIZE]
        files = []
        for p in batch:
            fname = os.path.basename(p)
            files.append(("client_files[]", (fname, open(p, "rb"), "image/jpeg")))

        data = {"image_quality": 70}

        # 첫 배치만 create, 나머지는 append
        if batch_start == 0:
            r = requests.post(
                f"{CVAT_URL}/api/tasks/{task_id}/data",
                headers=headers,
                files=files,
                data=data,
            )
        else:
            # CVAT는 data 엔드포인트 재호출로 추가 불가
            # 첫 호출에서 전부 보내야 함 → 배치 방식 변경 필요
            # 실제로는 한번에 보내되 파일 수가 많으면 여러 요청으로 나눠야 함
            pass

        # 파일 핸들 정리
        for _, (_, fh, _) in files:
            fh.close()

        uploaded += len(batch)
        status = r.status_code if batch_start == 0 else "skip"
        print(f"  [{league}] {uploaded}/{total} uploaded (status: {status})", flush=True)

    return uploaded


def upload_all_at_once(task_id: int, image_dir: str, token: str, league: str):
    """CVAT는 data를 한번만 POST 가능 → 모든 파일을 한번에."""
    headers = {"Authorization": f"Token {token}"}

    images = sorted(glob.glob(os.path.join(image_dir, "*.jpg")))
    total = len(images)

    if total == 0:
        print(f"  [{league}] no images, skip", flush=True)
        return 0

    print(f"  [{league}] uploading {total} images to task {task_id}...", flush=True)

    # 서버 공유 방식 사용 (로컬 경로 전달)
    # CVAT server_files 방식은 CVAT의 share 폴더에 있어야 함
    # client_files 방식으로 직접 업로드
    files = []
    for p in images:
        fname = os.path.basename(p)
        files.append(("client_files[]", (fname, open(p, "rb"), "image/jpeg")))

    data = {"image_quality": 70}

    t0 = time.time()
    r = requests.post(
        f"{CVAT_URL}/api/tasks/{task_id}/data",
        headers=headers,
        files=files,
        data=data,
        timeout=3600,
    )

    # 파일 핸들 정리
    for _, (_, fh, _) in files:
        fh.close()

    elapsed = time.time() - t0
    print(f"  [{league}] done: {r.status_code} ({elapsed:.0f}s)", flush=True)

    if r.status_code not in (200, 201, 202):
        print(f"  [{league}] ERROR: {r.text[:200]}", flush=True)

    return total


def main():
    token = get_token()
    print(f"CVAT token: {token[:10]}...", flush=True)

    total_uploaded = 0

    for league, task_id in TASKS.items():
        image_dir = os.path.join(CROPS_ROOT, league)
        count = len(glob.glob(os.path.join(image_dir, "*.jpg")))
        print(f"\n[{league}] {count} images -> task {task_id}", flush=True)

        if count == 0:
            continue

        uploaded = upload_all_at_once(task_id, image_dir, token, league)
        total_uploaded += uploaded

        # 업로드 간 대기 (서버 부하 방지)
        time.sleep(5)

    print(f"\nDONE: {total_uploaded} images uploaded", flush=True)


if __name__ == "__main__":
    main()
