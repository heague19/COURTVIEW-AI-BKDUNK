# -*- coding: utf-8 -*-
"""캘리브레이션 다이얼로그 — COURTVIEW-UI 의 calibrate.html 방식 그대로 이식.

핵심 동작:
  - 25 키포인트 (코너 4 + 하프 3 + 좌/우 페인트 4×2 + 좌/우 3PT 5×2) 중 4점 이상이면 저장 가능
  - 코너가 화면에 안 보이는 카메라 각도에서도 페인트/3PT/하프라인 등으로 대체
  - 우측 목록에서 점 선택 → 좌측 캔버스 클릭 → 자동으로 다음 미찍힌 점으로 이동
  - 우클릭: 가장 가까운 찍힌 점 삭제 / Ctrl+Z: 마지막 점 되돌리기 / S: 현재 점 스킵
  - 카메라 위치별 추천 키포인트 가이드 (cam_0~cam_7)

저장 위치: %APPDATA%\\COURTVIEW\\calibration\\cam_<id>.json
저장 포맷: GameOrchestrator._load_all_calibrations() 와 호환 (homography 3x3)
"""
from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import (
    QBrush, QColor, QImage, QKeyEvent, QKeySequence, QMouseEvent, QPainter,
    QPen, QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

_logger = logging.getLogger(__name__)


# =============================================================================
# 키포인트 정의 (calibrate.html KEYPOINTS 와 동일)
# =============================================================================
@dataclass
class Keypoint:
    id: int
    name: str
    label: str
    cx: float | None  # 코트 좌표 (m). None = optional 가변 (3PT 아크 곡선 위)
    cy: float | None
    group: str
    optional: bool = False


KEYPOINTS: list[Keypoint] = [
    # 코너 4
    Keypoint(0, "corner_TL", "좌상단 코너", 0.0, 0.0, "코너"),
    Keypoint(1, "corner_TR", "우상단 코너", 28.0, 0.0, "코너"),
    Keypoint(2, "corner_BL", "좌하단 코너", 0.0, 15.0, "코너"),
    Keypoint(3, "corner_BR", "우하단 코너", 28.0, 15.0, "코너"),
    # 하프 + 센터 3
    Keypoint(4, "half_T", "하프라인 상단", 14.0, 0.0, "하프"),
    Keypoint(5, "half_B", "하프라인 하단", 14.0, 15.0, "하프"),
    Keypoint(6, "center", "센터서클 중심", 14.0, 7.5, "하프"),
    # 좌 페인트 4
    Keypoint(7, "paint_L_TL", "좌 페인트 좌상", 5.8, 5.05, "좌 페인트"),
    Keypoint(8, "paint_L_TR", "좌 페인트 우상", 0.0, 5.05, "좌 페인트"),
    Keypoint(9, "paint_L_BL", "좌 페인트 좌하", 5.8, 9.95, "좌 페인트"),
    Keypoint(10, "paint_L_BR", "좌 페인트 우하", 0.0, 9.95, "좌 페인트"),
    # 우 페인트 4
    Keypoint(11, "paint_R_TL", "우 페인트 좌상", 22.2, 5.05, "우 페인트"),
    Keypoint(12, "paint_R_TR", "우 페인트 우상", 28.0, 5.05, "우 페인트"),
    Keypoint(13, "paint_R_BL", "우 페인트 좌하", 22.2, 9.95, "우 페인트"),
    Keypoint(14, "paint_R_BR", "우 페인트 우하", 28.0, 9.95, "우 페인트"),
    # 좌 3PT 5
    Keypoint(15, "tpt_L_base_T", "좌 3PT 베이스 상", 0.0, 0.9, "좌 3PT"),
    Keypoint(16, "tpt_L_base_B", "좌 3PT 베이스 하", 0.0, 14.1, "좌 3PT"),
    Keypoint(17, "tpt_L_peak", "좌 3PT 정점", 8.325, 7.5, "좌 3PT"),
    Keypoint(18, "tpt_L_arc_T", "좌 3PT 아크 상", None, None, "좌 3PT", optional=True),
    Keypoint(19, "tpt_L_arc_B", "좌 3PT 아크 하", None, None, "좌 3PT", optional=True),
    # 우 3PT 5
    Keypoint(20, "tpt_R_base_T", "우 3PT 베이스 상", 28.0, 0.9, "우 3PT"),
    Keypoint(21, "tpt_R_base_B", "우 3PT 베이스 하", 28.0, 14.1, "우 3PT"),
    Keypoint(22, "tpt_R_peak", "우 3PT 정점", 19.675, 7.5, "우 3PT"),
    Keypoint(23, "tpt_R_arc_T", "우 3PT 아크 상", None, None, "우 3PT", optional=True),
    Keypoint(24, "tpt_R_arc_B", "우 3PT 아크 하", None, None, "우 3PT", optional=True),
]


# 카메라 위치별 추천 키포인트 (calibrate.html CAM_POSITIONS)
CAM_POSITIONS: dict[str, dict] = {
    "cam_0": {"label": "CAM 1 — 좌하", "position": "BL",
              "recommended": [2, 8, 10, 9, 7, 16, 5, 6, 17, 19]},
    "cam_1": {"label": "CAM 2 — 하중좌", "position": "BC_L",
              "recommended": [2, 5, 8, 10, 9, 7, 6, 16, 17, 19, 15]},
    "cam_2": {"label": "CAM 3 — 하중우", "position": "BC_R",
              "recommended": [3, 5, 13, 11, 14, 12, 6, 21, 22, 24, 20]},
    "cam_3": {"label": "CAM 4 — 우하", "position": "BR",
              "recommended": [3, 12, 14, 13, 11, 21, 5, 6, 22, 24]},
    "cam_4": {"label": "CAM 5 — 우상", "position": "TR",
              "recommended": [1, 12, 11, 13, 14, 20, 4, 6, 22, 23]},
    "cam_5": {"label": "CAM 6 — 상중우", "position": "TC_R",
              "recommended": [1, 4, 12, 11, 13, 14, 6, 20, 22, 23, 21]},
    "cam_6": {"label": "CAM 7 — 상중좌", "position": "TC_L",
              "recommended": [0, 4, 8, 7, 9, 10, 6, 15, 17, 18, 16]},
    "cam_7": {"label": "CAM 8 — 좌상", "position": "TL",
              "recommended": [0, 8, 7, 9, 10, 15, 4, 6, 17, 18]},
}


# =============================================================================
def _appdata_calibration_dir() -> Path:
    ad = os.environ.get("APPDATA")
    if ad:
        return Path(ad) / "COURTVIEW" / "calibration"
    return Path.home() / ".courtview" / "calibration"


# =============================================================================
class _ClickCanvas(QLabel):
    """프레임 표시 + 키포인트 클릭/우클릭 삭제."""

    point_placed = Signal(int, float, float)  # kp_id, image_x, image_y
    point_remove_request = Signal(float, float)  # image_x, image_y

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(960, 540)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background:#0c0c0c;")
        self._frame: np.ndarray | None = None
        self._pixmap: QPixmap | None = None
        # placed: kp_id → (px, py) (이미지 좌표)
        self._placed: dict[int, tuple[float, float]] = {}
        self._active_kp: int | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_frame(self, bgr: np.ndarray) -> None:
        self._frame = bgr
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        # QImage 가 데이터 ownership 이슈 회피 — bytes 로 복사
        qimg = QImage(rgb.tobytes(), w, h, w * 3, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._draw()

    def set_placed(self, placed: dict[int, tuple[float, float]]) -> None:
        self._placed = dict(placed)
        self._draw()

    def set_active(self, kp_id: int | None) -> None:
        self._active_kp = kp_id
        self._draw()

    # 화면 좌표 → 이미지 좌표
    def _screen_to_image(self, sx: float, sy: float) -> tuple[float, float] | None:
        if self._pixmap is None:
            return None
        lw, lh = self.width(), self.height()
        pw, ph = self._pixmap.width(), self._pixmap.height()
        scale = min(lw / pw, lh / ph)
        dw, dh = pw * scale, ph * scale
        ox = (lw - dw) / 2
        oy = (lh - dh) / 2
        x = sx - ox
        y = sy - oy
        if not (0 <= x < dw and 0 <= y < dh):
            return None
        return x / scale, y / scale

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # noqa: N802
        if self._pixmap is None:
            return
        pt = self._screen_to_image(ev.position().x(), ev.position().y())
        if pt is None:
            return
        if ev.button() == Qt.MouseButton.RightButton:
            self.point_remove_request.emit(*pt)
            return
        if ev.button() == Qt.MouseButton.LeftButton:
            if self._active_kp is None:
                return
            self.point_placed.emit(self._active_kp, pt[0], pt[1])

    def resizeEvent(self, ev) -> None:  # noqa: N802
        super().resizeEvent(ev)
        self._draw()

    def _draw(self) -> None:
        if self._pixmap is None:
            self.clear()
            return
        canvas = self._pixmap.copy()
        painter = QPainter(canvas)
        try:
            # 점 + 라벨
            r_outer = max(6, canvas.width() // 400)
            font = painter.font()
            font.setPointSize(max(8, canvas.width() // 200))
            font.setBold(True)
            painter.setFont(font)

            for kp_id, (x, y) in self._placed.items():
                if 0 <= kp_id < len(KEYPOINTS):
                    kp = KEYPOINTS[kp_id]
                else:
                    kp = None

                # 외곽
                painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
                painter.setBrush(QBrush(QColor(255, 153, 51)))
                painter.drawEllipse(QPointF(x, y), r_outer, r_outer)

                # 라벨
                if kp is not None:
                    text = kp.name
                    fm = painter.fontMetrics()
                    tw = fm.horizontalAdvance(text)
                    th = fm.height()
                    bg_rect = (x + r_outer + 2, y - th / 2, tw + 8, th + 2)
                    painter.fillRect(
                        int(bg_rect[0]), int(bg_rect[1]),
                        int(bg_rect[2]), int(bg_rect[3]),
                        QColor(0, 0, 0, 180),
                    )
                    painter.setPen(QPen(QColor(255, 153, 51)))
                    painter.drawText(
                        int(bg_rect[0]) + 4,
                        int(bg_rect[1]) + th - 2,
                        text,
                    )

            # 활성 점 안내 — 좌상단
            if self._active_kp is not None and 0 <= self._active_kp < len(KEYPOINTS):
                kp = KEYPOINTS[self._active_kp]
                painter.fillRect(8, 8, 320, 30, QColor(0, 0, 0, 200))
                painter.setPen(QPen(QColor(255, 153, 51)))
                painter.drawText(16, 28, f"클릭할 점: {kp.name} ({kp.label})")
        finally:
            painter.end()

        scaled = canvas.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


# =============================================================================
class _MiniMap(QLabel):
    """코트 미니맵 — 키포인트 위치 시각화 (calibrate.html drawMinimap 포팅)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(280, 180)
        self.setStyleSheet("background:#111;")
        self._placed: dict[int, tuple[float, float]] = {}
        self._active: int | None = None
        self._cam_position: str = ""
        self._render()

    def set_state(
        self,
        placed: dict[int, tuple[float, float]],
        active: int | None,
        cam_position: str = "",
    ) -> None:
        self._placed = placed
        self._active = active
        self._cam_position = cam_position
        self._render()

    @staticmethod
    def _court_to_mini(cx: float, cy: float, w: int, h: int) -> tuple[float, float]:
        """3D 원근 (top 좁고, bottom 넓음)."""
        nx = cx / 28.0
        ny = cy / 15.0
        top_w, bot_w = 0.5, 1.0
        wy = top_w + (bot_w - top_w) * ny
        top_y = h * 0.12
        bot_y = h * 0.92
        my = top_y + (bot_y - top_y) * ny
        cx_pix = w / 2 + (nx - 0.5) * (w * wy) * 0.9
        return cx_pix, my

    def _render(self) -> None:
        w, h = self.width(), self.height()
        pix = QPixmap(w, h)
        pix.fill(QColor("#111"))
        p = QPainter(pix)
        try:
            # 코트 바닥
            corners = [
                self._court_to_mini(0, 0, w, h),
                self._court_to_mini(28, 0, w, h),
                self._court_to_mini(28, 15, w, h),
                self._court_to_mini(0, 15, w, h),
            ]
            p.setPen(QPen(QColor(255, 153, 51, 130), 1))
            p.setBrush(QBrush(QColor(26, 42, 26)))
            from PySide6.QtGui import QPolygonF
            poly = QPolygonF([QPointF(*c) for c in corners])
            p.drawPolygon(poly)

            # 라인들
            def line(x1, y1, x2, y2):
                a = self._court_to_mini(x1, y1, w, h)
                b = self._court_to_mini(x2, y2, w, h)
                p.drawLine(QPointF(*a), QPointF(*b))

            line(14, 0, 14, 15)         # 하프
            line(0, 5.05, 5.8, 5.05)    # 좌 페인트 위
            line(0, 9.95, 5.8, 9.95)    # 좌 페인트 아래
            line(5.8, 5.05, 5.8, 9.95)  # 좌 페인트 우
            line(22.2, 5.05, 28, 5.05)
            line(22.2, 9.95, 28, 9.95)
            line(22.2, 5.05, 22.2, 9.95)

            # 센터 서클
            n = 24
            for i in range(n):
                a1 = (i / n) * math.pi * 2
                a2 = ((i + 1) / n) * math.pi * 2
                x1 = 14 + 1.8 * math.cos(a1)
                y1 = 7.5 + 1.8 * math.sin(a1)
                x2 = 14 + 1.8 * math.cos(a2)
                y2 = 7.5 + 1.8 * math.sin(a2)
                line(x1, y1, x2, y2)

            # 미찍힌 점 (어두운 점)
            for kp in KEYPOINTS:
                if kp.cx is None or kp.id in self._placed:
                    continue
                mx, my = self._court_to_mini(kp.cx, kp.cy, w, h)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(255, 153, 51, 60)))
                p.drawEllipse(QPointF(mx, my), 2.5, 2.5)

            # 찍힌 점
            for kp_id in self._placed:
                if not (0 <= kp_id < len(KEYPOINTS)):
                    continue
                kp = KEYPOINTS[kp_id]
                if kp.cx is None:
                    continue
                mx, my = self._court_to_mini(kp.cx, kp.cy, w, h)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(255, 153, 51, 90)))
                p.drawEllipse(QPointF(mx, my), 6.0, 6.0)
                p.setBrush(QBrush(QColor(255, 153, 51)))
                p.drawEllipse(QPointF(mx, my), 3.5, 3.5)

            # 활성 점 외곽
            if self._active is not None and 0 <= self._active < len(KEYPOINTS):
                ka = KEYPOINTS[self._active]
                if ka.cx is not None:
                    mx, my = self._court_to_mini(ka.cx, ka.cy, w, h)
                    p.setPen(QPen(QColor(255, 255, 255), 2))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(QPointF(mx, my), 6.0, 6.0)

            # 카메라 위치 표시
            cam_pos_map = {
                "BL": (1, 14), "BC_L": (7, 15), "BC_R": (21, 15), "BR": (27, 14),
                "TR": (27, 1), "TC_R": (21, 0), "TC_L": (7, 0), "TL": (1, 1),
            }
            if self._cam_position in cam_pos_map:
                cx, cy = cam_pos_map[self._cam_position]
                mx, my = self._court_to_mini(cx, cy, w, h)
                p.setPen(QPen(QColor(255, 255, 255), 1.5))
                p.setBrush(QBrush(QColor(68, 136, 255, 220)))
                p.drawEllipse(QPointF(mx, my), 6.0, 6.0)
                p.setPen(QPen(QColor(255, 255, 255)))
                fnt = p.font()
                fnt.setBold(True)
                p.setFont(fnt)
                p.drawText(QPointF(mx - 5, my + 3), "C")
        finally:
            p.end()
        self.setPixmap(pix)


# =============================================================================
class CalibrationDialog(QDialog):
    """단일 카메라 캘리 — 25 키포인트 중 4점 이상 자유롭게."""

    def __init__(
        self,
        parent: QWidget | None,
        cam_id: str,
        mp4_path: Path,
        label: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"캘리브레이션 — {label} ({cam_id})")
        self.resize(1380, 820)
        self._cam_id = cam_id
        self._mp4_path = mp4_path
        self._label = label
        self._placed: dict[int, tuple[float, float]] = {}
        self._active_kp: int | None = None

        # cam_id → 추천 정보 (cam_0 = "cam_0")
        self._cam_info = CAM_POSITIONS.get(f"cam_{cam_id}") or CAM_POSITIONS.get(cam_id) or {}

        self._build_ui()
        self._load_first_frame()
        # 초기 활성 — 추천 첫번째 또는 0
        recs = self._cam_info.get("recommended") or []
        self._set_active(recs[0] if recs else 0)
        self._refresh()

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 헤더
        info = QLabel(
            "코트 위에서 식별 가능한 점들을 우측 목록에서 선택 → 좌측 영상 위에 클릭. "
            "최소 4점이면 저장 가능. 코너가 안 보이면 페인트/3PT 베이스/하프라인 등 다른 점들로 대체.\n"
            "<b>우클릭</b>: 가까운 점 삭제 &nbsp; <b>Ctrl+Z</b>: 마지막 되돌리기 &nbsp; <b>S</b>: 현재 점 스킵"
        )
        info.setWordWrap(True)
        root.addWidget(info)

        # 코트 표준 + 카메라 위치 안내
        std_row = QHBoxLayout()
        std_row.addWidget(QLabel("코트 표준:"))
        self._std_combo = QComboBox()
        self._std_combo.addItems(["FIBA (28.0×15.0)", "NBA (28.65×15.24)"])
        std_row.addWidget(self._std_combo)
        if self._cam_info:
            std_row.addWidget(QLabel(
                f"&nbsp;&nbsp;<b>카메라:</b> {self._cam_info.get('label', '')}"
            ))
        std_row.addStretch(1)
        self._counter_label = QLabel("0 / 4 점")
        std_row.addWidget(self._counter_label)
        root.addLayout(std_row)

        # 본문 — 좌(캔버스) + 우(미니맵+목록)
        body = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(body, stretch=1)

        # 좌
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self._canvas = _ClickCanvas()
        self._canvas.point_placed.connect(self._on_point_placed)
        self._canvas.point_remove_request.connect(self._on_remove_near)
        ll.addWidget(self._canvas, stretch=1)
        body.addWidget(left)

        # 우
        right = QWidget()
        right.setMinimumWidth(320)
        right.setMaximumWidth(360)
        rl = QVBoxLayout(right)
        self._minimap = _MiniMap()
        rl.addWidget(self._minimap, alignment=Qt.AlignmentFlag.AlignTop)

        rl.addWidget(QLabel("<b>키포인트</b> — 클릭하여 활성 점 변경 (✓ 찍힘 / ⭕ 미찍 / ⬜ 선택)"))
        self._kp_list = QListWidget()
        self._kp_list.itemClicked.connect(self._on_kp_item_click)
        rl.addWidget(self._kp_list, stretch=1)
        body.addWidget(right)

        body.setStretchFactor(0, 1)
        body.setStretchFactor(1, 0)

        # 버튼
        btns = QHBoxLayout()
        reset = QPushButton("초기화")
        reset.clicked.connect(self._reset)
        btns.addWidget(reset)
        btns.addStretch(1)
        self._save_btn = QPushButton("저장")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        btns.addWidget(self._save_btn)
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        root.addLayout(btns)

        # 단축키
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo_last)
        QShortcut(QKeySequence("S"), self, activated=self._skip_active)

    # ---------------------------------------------------------------- frame
    def _load_first_frame(self) -> None:
        cap = cv2.VideoCapture(str(self._mp4_path))
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            QMessageBox.critical(self, "오류", f"프레임 디코딩 실패: {self._mp4_path}")
            self.reject()
            return
        self._canvas.set_frame(frame)

    # ---------------------------------------------------------------- list
    def _populate_list(self) -> None:
        self._kp_list.clear()
        recs = set(self._cam_info.get("recommended", []) or [])
        last_group = ""
        for kp in KEYPOINTS:
            if kp.group != last_group:
                header = QListWidgetItem(f"━━ {kp.group} ━━")
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                f = header.font()
                f.setBold(True)
                header.setFont(f)
                header.setForeground(QColor(255, 153, 51))
                self._kp_list.addItem(header)
                last_group = kp.group

            placed = kp.id in self._placed
            active = self._active_kp == kp.id
            recommended = kp.id in recs
            icon = "✓" if placed else ("⬜" if active else "⭕")
            opt = "  (선택)" if kp.optional else ""
            star = " ★" if recommended and not placed else ""
            coord = f"({kp.cx:.1f}, {kp.cy:.1f})" if kp.cx is not None else "(가변)"

            item = QListWidgetItem(f"{icon}  {kp.name}{star}  — {kp.label} {coord}{opt}")
            item.setData(Qt.ItemDataRole.UserRole, kp.id)
            if placed:
                item.setForeground(QColor("#3acf6c"))
            elif active:
                item.setBackground(QColor(255, 153, 51, 60))
            elif kp.optional:
                item.setForeground(QColor("#777"))
            self._kp_list.addItem(item)

    def _on_kp_item_click(self, item: QListWidgetItem) -> None:
        kp_id = item.data(Qt.ItemDataRole.UserRole)
        if kp_id is None:
            return
        self._set_active(int(kp_id))
        self._refresh()

    # ---------------------------------------------------------------- placement
    def _on_point_placed(self, kp_id: int, x: float, y: float) -> None:
        self._placed[kp_id] = (x, y)
        # 다음 미찍 점 (필수 우선, 추천 우선, 그 다음 순서)
        self._set_active(self._next_unplaced(kp_id))
        self._refresh()

    def _on_remove_near(self, x: float, y: float) -> None:
        if not self._placed:
            return
        # 50px (이미지 좌표) 이내 가장 가까운 점 삭제
        best = None
        best_d = 1e9
        for kp_id, (px, py) in self._placed.items():
            d = (px - x) ** 2 + (py - y) ** 2
            if d < best_d:
                best_d = d
                best = kp_id
        if best is not None and best_d <= 50 ** 2:
            del self._placed[best]
            self._refresh()

    def _undo_last(self) -> None:
        if not self._placed:
            return
        last_id = max(self._placed.keys())
        del self._placed[last_id]
        self._refresh()

    def _skip_active(self) -> None:
        if self._active_kp is None:
            return
        self._set_active(self._next_unplaced(self._active_kp))
        self._refresh()

    def _next_unplaced(self, current_id: int) -> int | None:
        recs = self._cam_info.get("recommended", []) or []
        # 1) 추천 중 미찍 + 좌표 있음 + current 다음
        for kp_id in recs:
            if kp_id == current_id:
                continue
            if kp_id in self._placed:
                continue
            if 0 <= kp_id < len(KEYPOINTS):
                kp = KEYPOINTS[kp_id]
                if kp.cx is not None:
                    return kp_id
        # 2) current 이후 순차 (필수)
        for i in range(current_id + 1, len(KEYPOINTS)):
            kp = KEYPOINTS[i]
            if i not in self._placed and kp.cx is not None and not kp.optional:
                return i
        # 3) 처음부터 순차 (필수)
        for i in range(len(KEYPOINTS)):
            kp = KEYPOINTS[i]
            if i not in self._placed and kp.cx is not None and not kp.optional:
                return i
        # 4) optional 포함
        for i in range(len(KEYPOINTS)):
            if i not in self._placed and KEYPOINTS[i].cx is not None:
                return i
        return None

    def _set_active(self, kp_id: int | None) -> None:
        self._active_kp = kp_id

    def _reset(self) -> None:
        if self._placed:
            r = QMessageBox.question(
                self, "확인", "찍은 점을 모두 초기화하시겠습니까?",
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self._placed.clear()
        recs = self._cam_info.get("recommended") or []
        self._set_active(recs[0] if recs else 0)
        self._refresh()

    def _refresh(self) -> None:
        self._canvas.set_placed(self._placed)
        self._canvas.set_active(self._active_kp)
        self._minimap.set_state(
            placed=self._placed,
            active=self._active_kp,
            cam_position=self._cam_info.get("position", ""),
        )
        self._populate_list()
        n = len(self._placed)
        if n >= 4:
            self._counter_label.setText(f"<b>{n} 점 (저장 가능)</b>")
        else:
            self._counter_label.setText(f"{n} / 4 점 (저장까지 {4 - n} 점 필요)")
        self._save_btn.setEnabled(n >= 4)

    # ---------------------------------------------------------------- save
    def _on_save(self) -> None:
        pixel_pts = []
        court_pts = []
        for kp_id, (px, py) in self._placed.items():
            kp = KEYPOINTS[kp_id]
            if kp.cx is None or kp.cy is None:
                continue
            pixel_pts.append([px, py])
            court_pts.append([kp.cx, kp.cy])
        if len(pixel_pts) < 4:
            QMessageBox.warning(self, "실패", "유효한 점이 4개 미만입니다")
            return

        std_text = self._std_combo.currentText()
        std_key = "FIBA" if "FIBA" in std_text else "NBA"

        np_pixel = np.array(pixel_pts, dtype=np.float64)
        np_court = np.array(court_pts, dtype=np.float64)
        H, mask = cv2.findHomography(np_pixel, np_court, cv2.RANSAC, 3.0)
        if H is None:
            QMessageBox.warning(
                self, "실패",
                "호모그래피 계산 실패 — 점이 일직선이거나 너무 가깝습니다",
            )
            return
        try:
            inverse = np.linalg.inv(H)
        except np.linalg.LinAlgError:
            QMessageBox.warning(self, "실패", "호모그래피 역행렬 계산 실패")
            return

        projected = cv2.perspectiveTransform(
            np_pixel.reshape(-1, 1, 2), H,
        ).reshape(-1, 2)
        errors = np.linalg.norm(projected - np_court, axis=1)
        mean_reproj = float(errors.mean())

        cal_dir = _appdata_calibration_dir()
        cal_path = cal_dir / f"cam_{self._cam_id}.json"
        data = {
            "camera_id": self._cam_id,
            "court_standard": std_key,
            "homography": H.tolist(),
            "inverse_homography": inverse.tolist(),
            "quality_score": max(0.0, 1.0 - mean_reproj / 5.0),
            "mean_reproj_error_px": mean_reproj,
            "inlier_count": int(mask.sum()) if mask is not None else len(pixel_pts),
            "total_points": len(pixel_pts),
            "pixel_points": pixel_pts,
            "court_points": court_pts,
            "_source": "replay_analyzer_gui",
            "_video_path": str(self._mp4_path),
            "_keypoint_ids": list(self._placed.keys()),
        }
        # 안전 저장 — mkdir 실패 / write 실패 (디스크 가득 등) 명확히 알림
        try:
            cal_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(
                self, "캘리 저장 실패",
                f"폴더 생성 실패:\n{cal_dir}\n\n원인: {e}\n\n"
                "디스크 공간을 확보하거나 권한을 확인 후 다시 시도하세요. "
                "(찍은 점은 그대로 유지됩니다)",
            )
            _logger.exception("cal_dir mkdir 실패")
            return

        try:
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            cal_path.write_text(payload, encoding="utf-8")
            # 검증: 파일 존재 + 사이즈 > 0
            if not cal_path.exists() or cal_path.stat().st_size <= 0:
                raise OSError("쓰기 후 파일 사이즈가 0입니다 (디스크 가득 찼을 가능성)")
        except OSError as e:
            QMessageBox.critical(
                self, "캘리 저장 실패",
                f"파일 쓰기 실패:\n{cal_path}\n\n원인: {e}\n\n"
                "디스크 공간 확보 후 다시 시도하세요. "
                "(찍은 점은 그대로 유지됩니다)",
            )
            _logger.exception("캘리 파일 쓰기 실패: %s", cal_path)
            # 부분 저장된 파일 정리 (있을 경우)
            try:
                if cal_path.exists() and cal_path.stat().st_size <= 0:
                    cal_path.unlink(missing_ok=True)
            except Exception:
                pass
            return

        _logger.info(
            "캘리 저장: %s (점 %d개, 평균 오차 %.2f px)",
            cal_path, len(pixel_pts), mean_reproj,
        )
        QMessageBox.information(
            self, "저장 완료",
            f"{self._label} ({self._cam_id})\n"
            f"점 개수: {len(pixel_pts)}\n"
            f"평균 재투영 오차: {mean_reproj:.2f} px\n"
            f"품질 점수: {data['quality_score']:.2f}\n"
            f"저장: {cal_path}",
        )
        self.accept()


# =============================================================================
def is_calibrated(cam_id: str) -> bool:
    return (_appdata_calibration_dir() / f"cam_{cam_id}.json").exists()


def calibration_quality(cam_id: str) -> float | None:
    p = _appdata_calibration_dir() / f"cam_{cam_id}.json"
    if not p.exists():
        return None
    try:
        return float(json.loads(p.read_text(encoding="utf-8")).get("quality_score", 0.0))
    except Exception:
        return None
