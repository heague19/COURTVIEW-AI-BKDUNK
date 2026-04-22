# -*- coding: utf-8 -*-
"""
COURTVIEW - 런처 스플래시 화면

tkinter 기반 경량 스플래시.
- 브랜드 로고 + 진행률 바 + 상태 텍스트
- 자체 스레드에서 돌고, 진행률은 Queue 로 받음
- 번들 크기 영향 0 (Python 표준 라이브러리)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-21
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from typing import Optional


BG_COLOR = "#0E0E10"
ACCENT_ORANGE = "#FF9933"
TEXT_WHITE = "#FFFFFF"
TEXT_GRAY = "#999999"
TEXT_DARK = "#555555"
PROGRESS_BG = "#222224"
PROGRESS_FG = ACCENT_ORANGE


@dataclass
class SplashMessage:
    """스플래시에 전달되는 메시지."""
    kind: str      # 'progress' | 'status' | 'close'
    current: int = 0
    total: int = 0
    text: str = ""


class SplashController:
    """외부(런처 메인 스레드)에서 스플래시를 조작하는 핸들."""

    def __init__(self):
        self._queue: "queue.Queue[SplashMessage]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """스플래시 UI 스레드 기동."""
        self._thread = threading.Thread(target=_run_splash, args=(self._queue,), daemon=True)
        self._thread.start()

    def set_status(self, text: str) -> None:
        self._queue.put(SplashMessage(kind="status", text=text))

    def set_progress(self, current: int, total: int, text: str = "") -> None:
        self._queue.put(SplashMessage(kind="progress", current=current, total=total, text=text))

    def close(self) -> None:
        self._queue.put(SplashMessage(kind="close"))
        if self._thread is not None:
            self._thread.join(timeout=2.0)


# =============================================================================
# UI 스레드
# =============================================================================
def _run_splash(msg_queue: "queue.Queue[SplashMessage]") -> None:
    """스플래시 UI 를 독립 스레드에서 실행 (main 프로세스 블록 안 함)."""
    try:
        root = tk.Tk()
    except Exception:
        # tkinter 사용 불가 환경 (headless) — 조용히 리턴
        return

    root.title("COURTVIEW")
    root.overrideredirect(True)  # 타이틀바 제거 = 진짜 스플래시
    root.configure(bg=BG_COLOR)

    # 크기·위치 (화면 중앙)
    W, H = 520, 280
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - W) // 2
    y = (sh - H) // 2
    root.geometry(f"{W}x{H}+{x}+{y}")
    root.attributes("-topmost", True)

    # ── 레이아웃 ──
    # 상단 로고
    logo_frame = tk.Frame(root, bg=BG_COLOR)
    logo_frame.pack(pady=(40, 10))

    tk.Label(logo_frame, text="COURT", font=("Segoe UI", 32, "bold"),
             bg=BG_COLOR, fg=TEXT_WHITE).pack(side="left")
    tk.Label(logo_frame, text="VIEW", font=("Segoe UI", 32, "bold"),
             bg=BG_COLOR, fg=ACCENT_ORANGE).pack(side="left")

    tk.Label(root, text="AI 농구 분석 플랫폼", font=("Segoe UI", 10),
             bg=BG_COLOR, fg=TEXT_GRAY).pack(pady=(0, 20))

    # 상태 텍스트
    status_var = tk.StringVar(value="초기화 중...")
    tk.Label(root, textvariable=status_var, font=("Segoe UI", 10),
             bg=BG_COLOR, fg=TEXT_WHITE).pack(pady=(4, 8))

    # 진행률 바 (캔버스로 직접 그림 — ttk.Progressbar 는 스타일 제한)
    bar_w = 440
    bar_h = 6
    bar_canvas = tk.Canvas(root, width=bar_w, height=bar_h,
                           bg=PROGRESS_BG, highlightthickness=0)
    bar_canvas.pack(pady=(4, 4))
    bar_fill = bar_canvas.create_rectangle(0, 0, 0, bar_h, fill=PROGRESS_FG, width=0)

    # 서브 텍스트 (세부 정보)
    sub_var = tk.StringVar(value="")
    tk.Label(root, textvariable=sub_var, font=("Segoe UI", 9),
             bg=BG_COLOR, fg=TEXT_GRAY).pack(pady=(4, 4))

    # 하단 힌트
    tk.Label(root, text="첫 실행 시 AI 모델 최적화에 5~15분 소요됩니다",
             font=("Segoe UI", 8), bg=BG_COLOR, fg=TEXT_DARK).pack(
        side="bottom", pady=(0, 14))

    # ── 메시지 펌프 ──
    closed = {"flag": False}

    def _pump():
        try:
            while True:
                msg = msg_queue.get_nowait()
                if msg.kind == "close":
                    closed["flag"] = True
                    root.after(100, root.destroy)
                    return
                elif msg.kind == "status":
                    status_var.set(msg.text)
                elif msg.kind == "progress":
                    ratio = (msg.current / msg.total) if msg.total else 0
                    ratio = max(0.0, min(1.0, ratio))
                    bar_canvas.coords(bar_fill, 0, 0, int(bar_w * ratio), bar_h)
                    if msg.text:
                        sub_var.set(f"{msg.text}  ({msg.current}/{msg.total})")
        except queue.Empty:
            pass

        if not closed["flag"]:
            root.after(80, _pump)

    root.after(50, _pump)
    try:
        root.mainloop()
    except Exception:
        pass


__all__ = ["SplashController", "SplashMessage"]


# =============================================================================
# 단독 실행 데모
# =============================================================================
if __name__ == "__main__":
    ctl = SplashController()
    ctl.start()
    time.sleep(0.5)
    ctl.set_status("AI 모델 최적화 중...")
    for i in range(1, 8):
        time.sleep(0.6)
        ctl.set_progress(i, 7, f"yolo11l-pose" if i == 3 else f"model_{i}")
    ctl.set_status("서버 기동 중...")
    time.sleep(1.0)
    ctl.close()
