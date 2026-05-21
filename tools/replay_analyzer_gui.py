# -*- coding: utf-8 -*-
"""COURTVIEW Replay Analyzer GUI

녹화된 mp4/ts 영상으로부터 기록지·전력분석·하이라이트 추출.
"""
from __future__ import annotations

import logging
import sys
import tempfile
import uuid
from pathlib import Path
from threading import Event

# 프로젝트 루트 sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtCore import Qt, QObject, Signal as pyqtSignal, QThread, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tools.replay.calibration_dialog import (
    CalibrationDialog,
    calibration_quality,
    is_calibrated,
)
from tools.replay.format_detector import (
    DetectedSession,
    detect,
    list_t_sessions,
)
from tools.replay.multi_file_ingestion import (
    PreparedSession,
    cleanup,
    prepare_session,
)
from tools.replay.replay_runner import ReplayResult, run_replay

_logger = logging.getLogger(__name__)


# =============================================================================
class ReplayWorker(QObject):
    progress = pyqtSignal(str, float)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        session: DetectedSession,
        cam_assignment: dict[str, str],
        home: str,
        away: str,
        work_dir: Path,
        n_files_per_cam: int,
        smoke_seconds: int = 0,
        start_offset_sec: float = 0.0,
    ) -> None:
        super().__init__()
        self._session = session
        self._cam_assignment = cam_assignment
        self._home = home
        self._away = away
        self._work_dir = work_dir
        self._n_files_per_cam = n_files_per_cam
        self._smoke_seconds = smoke_seconds
        self._start_offset_sec = start_offset_sec
        self._stop = Event()
        self._prepared: PreparedSession | None = None
        self._smoke_timer = None  # 스모크 모드: 자동 종료 Timer

    def stop(self) -> None:
        self._stop.set()
        if self._smoke_timer is not None:
            try:
                self._smoke_timer.cancel()
            except Exception:
                pass

    def run(self) -> None:
        try:
            self.progress.emit("전처리: 카메라 mp4 합치는 중…", 1.0)

            def _prep_progress(msg: str, pct: float) -> None:
                self.progress.emit(msg, max(1.0, min(20.0, pct * 0.2)))

            # N 파일 제한 적용 — DetectedSession 의 cameras[*].files 잘라냄 (in-place 안전)
            if self._n_files_per_cam > 0:
                for cam in self._session.cameras:
                    cam.files = cam.files[:self._n_files_per_cam]

            self._prepared = prepare_session(
                self._session,
                self._work_dir,
                self._cam_assignment,
                progress=_prep_progress,
                extra_offset_sec=self._start_offset_sec,
            )

            if not self._prepared.cameras:
                self.failed.emit("매핑된 카메라가 없습니다 — 최소 1개를 cam_X 에 매핑하세요")
                return

            def _analyze_progress(msg: str, pct: float) -> None:
                self.progress.emit(msg, 20.0 + min(80.0, pct * 0.8))

            # 스모크 모드: 영상 N초 분량 분석 후 자동 stop.
            # 분석 처리 속도가 영상 fps 보다 4-5배 느리므로 wall-clock 으로는 5배 시간 부여.
            # (예: 영상 60초 분량 → wall-clock 300초 timer)
            if self._smoke_seconds > 0:
                from threading import Timer
                _wall_seconds = self._smoke_seconds * 6  # 안전 마진 포함 6배
                def _smoke_stop():
                    _logger.warning(
                        "스모크 모드: 영상 %d초 분량 (wall-clock %d초) 경과 → 자동 종료",
                        self._smoke_seconds, _wall_seconds,
                    )
                    self._stop.set()
                self._smoke_timer = Timer(_wall_seconds, _smoke_stop)
                self._smoke_timer.daemon = True
                self._smoke_timer.start()
                _logger.warning(
                    "스모크 모드 활성: 영상 %d초 분량 분석 (wall-clock 최대 %d초 = %.1f분)",
                    self._smoke_seconds, _wall_seconds, _wall_seconds / 60.0,
                )

            result = run_replay(
                prepared=self._prepared,
                home_team=self._home,
                away_team=self._away,
                progress=_analyze_progress,
                stop_event=self._stop,
            )

            # 분석 끝났으면 work_dir 의 합쳐진 mp4 들 즉시 정리
            try:
                cleanup(self._prepared)
            except Exception:
                _logger.warning("work_dir 정리 실패 (수동 삭제 필요)", exc_info=True)

            self.finished.emit(result)
        except Exception as exc:
            _logger.exception("Replay worker 실패")
            # 실패해도 work_dir 정리
            if self._prepared is not None:
                try:
                    cleanup(self._prepared)
                except Exception:
                    pass
            self.failed.emit(str(exc))


# =============================================================================
class ReplayAnalyzerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("COURTVIEW Replay Analyzer")
        self.resize(1200, 880)

        self._session: DetectedSession | None = None
        self._cam_assignment: dict[str, str] = {}
        self._worker: ReplayWorker | None = None
        self._worker_thread: QThread | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.addWidget(self._build_section_input())
        root.addWidget(self._build_section_cameras(), stretch=1)
        root.addWidget(self._build_section_analysis())
        root.addWidget(self._build_section_run())
        root.addWidget(self._build_section_result())

        self.setStatusBar(QStatusBar())

    # ---------------------------------------------------------------- sections
    def _build_section_input(self) -> QGroupBox:
        box = QGroupBox("[1] 영상 폴더")
        h = QHBoxLayout(box)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(
            "T(cam<n>_Q<n>.ts) / B(sync.json + L*(CAM*) 폴더)"
        )
        h.addWidget(self._path_edit, stretch=1)
        pick = QPushButton("폴더 선택…")
        pick.clicked.connect(self._on_pick_folder)
        h.addWidget(pick)
        scan = QPushButton("스캔")
        scan.clicked.connect(self._on_scan)
        h.addWidget(scan)
        self._t_session_combo = QComboBox()
        self._t_session_combo.setVisible(False)
        self._t_session_combo.currentIndexChanged.connect(self._on_t_session_changed)
        h.addWidget(self._t_session_combo)
        return box

    def _build_section_cameras(self) -> QGroupBox:
        box = QGroupBox("[2] 카메라 매핑 + 캘리브레이션")
        v = QVBoxLayout(box)
        info = QLabel(
            "각 카메라를 cam_0~cam_7 슬롯에 직접 매핑하고 코트 4점 캘리 진행. "
            "(매핑 안 한 카메라는 분석에서 제외)"
        )
        info.setWordWrap(True)
        v.addWidget(info)

        self._cam_table = QTableWidget(0, 5)
        self._cam_table.setHorizontalHeaderLabels(
            ["원본 폴더/파일", "라벨", "Native ID", "할당 cam_X", "캘리"]
        )
        self._cam_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch,
        )
        self._cam_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents,
        )
        self._cam_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v.addWidget(self._cam_table, stretch=1)

        return box

    def _build_section_analysis(self) -> QGroupBox:
        box = QGroupBox("[3] 분석 옵션")
        v = QVBoxLayout(box)

        # 작업 폴더
        wrow = QHBoxLayout()
        wrow.addWidget(QLabel("작업 폴더(큰 디스크 권장):"))
        self._work_dir_edit = QLineEdit(str(Path(tempfile.gettempdir())))
        wrow.addWidget(self._work_dir_edit, stretch=1)
        pick_w = QPushButton("폴더 선택…")
        pick_w.clicked.connect(self._on_pick_work_dir)
        wrow.addWidget(pick_w)
        self._disk_label = QLabel("")
        wrow.addWidget(self._disk_label)
        v.addLayout(wrow)

        # B 형식 — 시작 인덱스 + N 파일 제한
        # (첫 파일은 카메라 anchor 직후 = 코트 비어있을 수 있음 → 시작 인덱스로 skip)
        nrow = QHBoxLayout()
        nrow.addWidget(QLabel("시작 파일 인덱스:"))
        self._start_idx_spin = QSpinBox()
        self._start_idx_spin.setRange(0, 99)
        self._start_idx_spin.setValue(0)
        self._start_idx_spin.setSuffix(" (0=첫 파일)")
        self._start_idx_spin.valueChanged.connect(self._update_required_label)
        nrow.addWidget(self._start_idx_spin)
        nrow.addSpacing(20)
        nrow.addWidget(QLabel("사용 파일 수:"))
        self._n_files_spin = QSpinBox()
        self._n_files_spin.setRange(0, 100)
        self._n_files_spin.setValue(1)
        self._n_files_spin.setSpecialValueText("끝까지")
        self._n_files_spin.setSuffix(" 개 (각 ~3분)")
        self._n_files_spin.valueChanged.connect(self._update_required_label)
        nrow.addWidget(self._n_files_spin)
        nrow.addStretch(1)
        self._required_label = QLabel("")
        nrow.addWidget(self._required_label)
        v.addLayout(nrow)

        # 시작 오프셋 — 영상 X분 Y초부터 분석 시작 (예: 쿼터 시작 지점)
        orow = QHBoxLayout()
        orow.addWidget(QLabel("시작 시점:"))
        self._offset_min_spin = QSpinBox()
        self._offset_min_spin.setRange(0, 240)
        self._offset_min_spin.setValue(0)
        self._offset_min_spin.setSuffix(" 분")
        orow.addWidget(self._offset_min_spin)
        self._offset_sec_spin = QSpinBox()
        self._offset_sec_spin.setRange(0, 59)
        self._offset_sec_spin.setValue(0)
        self._offset_sec_spin.setSuffix(" 초")
        orow.addWidget(self._offset_sec_spin)
        orow.addWidget(QLabel("(0:00 = 처음부터)"))
        orow.addStretch(1)
        v.addLayout(orow)

        # 스모크 모드 — 영상 N초 분량 분석 후 자동 종료 + 로그 자동 저장 (디버그용)
        srow = QHBoxLayout()
        self._smoke_check = QCheckBox("스모크 모드 (디버그):")
        self._smoke_check.setChecked(False)
        srow.addWidget(self._smoke_check)
        self._smoke_seconds_spin = QSpinBox()
        self._smoke_seconds_spin.setRange(5, 600)
        self._smoke_seconds_spin.setValue(60)
        self._smoke_seconds_spin.setSuffix(" 초 영상 분량 분석")
        srow.addWidget(self._smoke_seconds_spin)
        srow.addWidget(QLabel("(wall-clock ~6배 소요, 로그 작업폴더에 저장)"))
        srow.addStretch(1)
        v.addLayout(srow)

        # 팀명 + 산출물 옵션
        h = QHBoxLayout()
        h.addWidget(QLabel("HOME:"))
        self._home_edit = QLineEdit("HOME")
        self._home_edit.setMaxLength(20)
        h.addWidget(self._home_edit)
        h.addWidget(QLabel("AWAY:"))
        self._away_edit = QLineEdit("AWAY")
        self._away_edit.setMaxLength(20)
        h.addWidget(self._away_edit)
        h.addStretch(1)
        self._opt_gamesheet = QCheckBox("기록지(PDF)")
        self._opt_gamesheet.setChecked(True)
        h.addWidget(self._opt_gamesheet)
        self._opt_report = QCheckBox("전력분석(HTML)")
        self._opt_report.setChecked(True)
        h.addWidget(self._opt_report)
        self._opt_clips = QCheckBox("하이라이트")
        self._opt_clips.setChecked(True)
        h.addWidget(self._opt_clips)
        v.addLayout(h)

        self._update_disk_label()
        self._work_dir_edit.editingFinished.connect(self._update_disk_label)
        return box

    def _build_section_run(self) -> QGroupBox:
        box = QGroupBox("[4] 실행")
        v = QVBoxLayout(box)
        h = QHBoxLayout()
        self._run_btn = QPushButton("▶ 분석 시작")
        self._run_btn.clicked.connect(self._on_run)
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        self._run_btn.setFont(f)
        self._run_btn.setMinimumHeight(36)
        h.addWidget(self._run_btn, stretch=1)
        self._stop_btn = QPushButton("중지")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        h.addWidget(self._stop_btn)
        v.addLayout(h)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        v.addWidget(self._progress)
        self._progress_label = QLabel("대기 중")
        v.addWidget(self._progress_label)
        return box

    def _build_section_result(self) -> QGroupBox:
        box = QGroupBox("[5] 결과")
        h = QHBoxLayout(box)
        self._result_label = QLabel("(분석 후 표시)")
        h.addWidget(self._result_label, stretch=1)
        self._open_dir_btn = QPushButton("출력 폴더 열기")
        self._open_dir_btn.setEnabled(False)
        self._open_dir_btn.clicked.connect(self._on_open_dir)
        h.addWidget(self._open_dir_btn)
        self._open_clips_btn = QPushButton("하이라이트 폴더")
        self._open_clips_btn.setEnabled(False)
        self._open_clips_btn.clicked.connect(self._on_open_clips)
        h.addWidget(self._open_clips_btn)
        self._result_dir: Path | None = None
        self._highlights_dir: Path | None = None
        return box

    # ---------------------------------------------------------------- folder/work_dir
    def _on_pick_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "영상 폴더 선택", self._path_edit.text() or str(Path.home()),
        )
        if d:
            self._path_edit.setText(d)
            self._on_scan()

    def _on_pick_work_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "작업 폴더 선택 (큰 디스크 권장)",
            self._work_dir_edit.text() or str(Path.home()),
        )
        if d:
            self._work_dir_edit.setText(d)
            self._update_disk_label()

    def _update_disk_label(self) -> None:
        path = self._work_dir_edit.text().strip()
        if not path:
            self._disk_label.setText("")
            return
        try:
            import shutil as _sh
            target = Path(path) if Path(path).exists() else Path(Path(path).anchor)
            usage = _sh.disk_usage(str(target))
            free_gb = usage.free / (1024 ** 3)
            color = "#3acf6c" if free_gb >= 250 else ("#e0a020" if free_gb >= 100 else "#e04040")
            self._disk_label.setText(
                f"<span style='color:{color}'>여유 {free_gb:.1f} GB</span>"
            )
        except Exception:
            self._disk_label.setText("(디스크 조회 실패)")

    def _estimate_required_gb(self) -> float:
        if self._session is None:
            return 0.0
        n_limit = self._n_files_spin.value() if hasattr(self, "_n_files_spin") else 0
        start = self._start_idx_spin.value() if hasattr(self, "_start_idx_spin") else 0
        total = 0
        for cam in self._session.cameras:
            if cam.folder_name not in self._cam_assignment:
                continue
            sliced = cam.files[start:]
            files = sliced if n_limit <= 0 else sliced[:n_limit]
            for f in files:
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
        return total / (1024 ** 3)

    def _update_required_label(self) -> None:
        gb = self._estimate_required_gb()
        if gb <= 0:
            self._required_label.setText("")
        else:
            color = "#e04040" if gb >= 100 else ("#e0a020" if gb >= 30 else "#3acf6c")
            self._required_label.setText(
                f"<span style='color:{color}'>예상 임시 사용: {gb:.1f} GB</span>"
            )

    # ---------------------------------------------------------------- scan
    def _on_scan(self) -> None:
        path = self._path_edit.text().strip()
        if not path:
            return
        root = Path(path)
        if not root.exists():
            QMessageBox.warning(self, "오류", f"폴더 없음: {root}")
            return

        t_sessions = list_t_sessions(root)
        if len(t_sessions) > 1:
            self._t_session_combo.setVisible(True)
            self._t_session_combo.blockSignals(True)
            self._t_session_combo.clear()
            for s in t_sessions:
                self._t_session_combo.addItem(s.name, str(s))
            self._t_session_combo.blockSignals(False)
            self._on_t_session_changed()
            return
        self._t_session_combo.setVisible(False)

        sess = detect(root)
        self._apply_detected_session(sess)

    def _on_t_session_changed(self) -> None:
        path = self._t_session_combo.currentData()
        if not path:
            return
        sess = detect(Path(path))
        self._apply_detected_session(sess)

    def _apply_detected_session(self, sess: DetectedSession) -> None:
        if sess.kind == "UNKNOWN":
            root = sess.root
            diag = [f"선택 폴더: {root}"]
            try:
                if root.exists():
                    diag.append(f"sync.json: {'있음' if (root / 'sync.json').exists() else '없음'}")
                    children = [c.name for c in root.iterdir() if c.is_dir()][:10]
                    diag.append(f"하위 폴더 ({len(children)}+): {', '.join(children) if children else '(없음)'}")
                    sub_with_sync = [c.name for c in root.iterdir()
                                     if c.is_dir() and (c / 'sync.json').exists()]
                    if sub_with_sync:
                        diag.append(f"하위 sync.json 폴더: {sub_with_sync}")
                else:
                    diag.append("폴더가 존재하지 않습니다")
            except Exception as e:
                diag.append(f"진단 오류: {e}")
            QMessageBox.warning(
                self, "감지 실패",
                "T(cam<n>_Q<n>.ts) 또는 B(sync.json + L*(CAM*)) 형식을 인식하지 못했습니다.\n\n"
                + "\n".join(diag)
            )
            self._session = None
            self._cam_table.setRowCount(0)
            return
        self._session = sess
        self.statusBar().showMessage(
            f"감지: {sess.kind} 형식 — {sess.session_label} ({len(sess.cameras)} 카메라)"
        )
        self._populate_camera_table()
        self._update_required_label()

    def _populate_camera_table(self) -> None:
        if self._session is None:
            return
        self._cam_assignment.clear()
        cams = self._session.cameras
        self._cam_table.setRowCount(len(cams))
        for row, cam in enumerate(cams):
            self._cam_table.setItem(row, 0, QTableWidgetItem(cam.folder_name))
            self._cam_table.setItem(row, 1, QTableWidgetItem(cam.cam_label))
            self._cam_table.setItem(row, 2, QTableWidgetItem(cam.cam_native_id))

            combo = QComboBox()
            combo.addItem("(미사용)", "")
            for i in range(8):
                combo.addItem(f"cam_{i}", f"cam_{i}")
            default_idx = self._default_assignment_idx(cam.cam_native_id, row)
            combo.setCurrentIndex(default_idx)
            combo.currentIndexChanged.connect(
                lambda _idx, r=row: self._on_cam_assignment_changed(r),
            )
            self._cam_table.setCellWidget(row, 3, combo)

            btn = QPushButton(self._calib_btn_text(self._assigned_cam_id(row)))
            btn.clicked.connect(lambda _checked=False, r=row: self._on_calibrate_row(r))
            self._cam_table.setCellWidget(row, 4, btn)

            self._on_cam_assignment_changed(row, refresh_btn=False)

        # 매핑 다 적용된 후 캘리 버튼 텍스트 일괄 갱신 (저장된 캘리 파일 인식)
        for row in range(self._cam_table.rowCount()):
            self._refresh_calib_button(row)

    def _default_assignment_idx(self, native_id: str, row: int) -> int:
        digits = "".join(c for c in native_id if c.isdigit())
        if digits.isdigit():
            n = int(digits)
            if 1 <= n <= 8:
                return n
        return min(row + 1, 8)

    def _assigned_cam_id(self, row: int) -> str:
        if self._session is None:
            return ""
        folder = self._session.cameras[row].folder_name
        return self._cam_assignment.get(folder, "")

    def _calib_btn_text(self, cam_id: str) -> str:
        if not cam_id:
            return "(매핑 후)"
        short = cam_id.replace("cam_", "")
        if is_calibrated(short):
            q = calibration_quality(short) or 0.0
            return f"✓ Q {q:.2f} — 재캘리"
        return "캘리 (4점)"

    def _on_cam_assignment_changed(self, row: int, refresh_btn: bool = True) -> None:
        if self._session is None:
            return
        cam = self._session.cameras[row]
        combo = self._cam_table.cellWidget(row, 3)
        if combo is None:
            return
        target = combo.currentData() or ""

        if target:
            for r2 in range(self._cam_table.rowCount()):
                if r2 == row:
                    continue
                c2 = self._cam_table.cellWidget(r2, 3)
                if c2 is not None and c2.currentData() == target:
                    c2.blockSignals(True)
                    c2.setCurrentIndex(0)
                    c2.blockSignals(False)
                    folder2 = self._session.cameras[r2].folder_name
                    self._cam_assignment.pop(folder2, None)
                    self._refresh_calib_button(r2)

        if target:
            self._cam_assignment[cam.folder_name] = target
        else:
            self._cam_assignment.pop(cam.folder_name, None)

        if refresh_btn:
            self._refresh_calib_button(row)
        self._update_required_label()

    def _refresh_calib_button(self, row: int) -> None:
        btn = self._cam_table.cellWidget(row, 4)
        if isinstance(btn, QPushButton):
            btn.setText(self._calib_btn_text(self._assigned_cam_id(row)))

    def _on_calibrate_row(self, row: int) -> None:
        if self._session is None:
            return
        cam = self._session.cameras[row]
        cam_id_full = self._assigned_cam_id(row)
        if not cam_id_full:
            QMessageBox.information(
                self, "안내",
                "먼저 'cam_0~cam_7' 슬롯에 매핑하세요. 매핑된 슬롯 ID 로 캘리 파일이 저장됩니다.",
            )
            return
        cam_id_short = cam_id_full.replace("cam_", "")
        if not cam.files:
            QMessageBox.warning(self, "오류", "이 카메라의 영상 파일이 없습니다")
            return
        dlg = CalibrationDialog(
            self,
            cam_id=cam_id_short,
            mp4_path=cam.files[0],
            label=cam.cam_label,
        )
        dlg.exec()
        self._refresh_calib_button(row)

    # ---------------------------------------------------------------- run
    def _on_run(self) -> None:
        if self._session is None:
            QMessageBox.warning(self, "오류", "먼저 영상 폴더를 스캔하세요")
            return
        if not self._cam_assignment:
            QMessageBox.warning(self, "오류", "최소 1개 카메라를 cam_X 에 매핑하세요")
            return

        # 디스크 검증
        work_dir_str = self._work_dir_edit.text().strip()
        if not work_dir_str:
            QMessageBox.warning(self, "오류", "작업 폴더를 지정하세요")
            return
        work_root = Path(work_dir_str)
        if not work_root.exists():
            try:
                work_root.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "오류", f"작업 폴더 생성 실패: {e}")
                return
        try:
            import shutil as _sh
            usage = _sh.disk_usage(str(work_root))
            free_gb = usage.free / (1024 ** 3)
        except Exception:
            free_gb = 0.0
        required_gb = self._estimate_required_gb()
        if required_gb > 0 and free_gb < required_gb * 1.2:
            r = QMessageBox.question(
                self, "디스크 공간 부족 가능",
                f"예상 임시 사용량: {required_gb:.1f} GB\n"
                f"작업 폴더 여유: {free_gb:.1f} GB\n\n"
                f"여유공간 부족할 수 있습니다. 계속 진행할까요?\n"
                f"(B 형식 파일 수를 줄이거나 다른 디스크로 작업폴더 변경 권장)",
            )
            if r != QMessageBox.StandardButton.Yes:
                return

        # 캘리 미완료 경고
        missing = [
            cid for cid in self._cam_assignment.values()
            if not is_calibrated(cid.replace("cam_", ""))
        ]
        if missing:
            r = QMessageBox.question(
                self, "캘리 미완료",
                f"다음 카메라가 캘리 미완료: {', '.join(missing)}\n진행할까요?",
            )
            if r != QMessageBox.StandardButton.Yes:
                return

        # 작업 폴더 (세션별)
        session_work = work_root / f"courtview_replay_{uuid.uuid4().hex[:8]}"
        session_work.mkdir(parents=True, exist_ok=True)

        # 스모크 모드: 로그를 작업폴더에 자동 저장 (전체 logger 에 FileHandler 부착)
        smoke_seconds = (
            self._smoke_seconds_spin.value() if self._smoke_check.isChecked() else 0
        )
        self._log_file_handler = None
        if smoke_seconds > 0:
            log_path = session_work / f"replay_smoke_{smoke_seconds}s.log"
            try:
                fh = logging.FileHandler(str(log_path), mode="w", encoding="utf-8")
                fh.setLevel(logging.INFO)
                fh.setFormatter(logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%H:%M:%S",
                ))
                logging.getLogger().addHandler(fh)
                self._log_file_handler = fh
                _logger.warning("스모크 모드 로그 저장: %s", log_path)
                self._smoke_log_path = log_path
            except Exception:
                _logger.exception("스모크 로그 파일 생성 실패")

        # UI 잠금
        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress.setValue(0)
        self._progress_label.setText("시작 중…")
        self._open_dir_btn.setEnabled(False)
        self._open_clips_btn.setEnabled(False)
        self._result_label.setText("(분석 중…)")

        offset_sec = (
            self._offset_min_spin.value() * 60 + self._offset_sec_spin.value()
        )
        worker = ReplayWorker(
            session=self._session,
            cam_assignment=dict(self._cam_assignment),
            home=self._home_edit.text().strip() or "HOME",
            away=self._away_edit.text().strip() or "AWAY",
            work_dir=session_work,
            n_files_per_cam=self._n_files_spin.value(),
            smoke_seconds=smoke_seconds,
            start_offset_sec=float(offset_sec),
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._worker_thread = thread
        thread.start()

    def _on_stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()
        self._stop_btn.setEnabled(False)
        self._progress_label.setText("중지 요청 — 정리 중…")

    def _on_progress(self, msg: str, pct: float) -> None:
        self._progress.setValue(int(pct))
        self._progress_label.setText(msg)

    def _on_finished(self, result: ReplayResult) -> None:
        self._detach_log_handler()
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setValue(100)
        if not result.success:
            self._progress_label.setText(f"실패: {result.error}")
            err_extra = f"\n로그: {self._smoke_log_path}" if getattr(
                self, "_smoke_log_path", None) else ""
            self._result_label.setText(f"❌ 분석 실패\n{result.error}{err_extra}")
            return
        self._progress_label.setText(
            f"완료 — game_id={result.game_id}, {result.elapsed_sec:.1f}s"
        )
        self._result_dir = result.output_dir
        self._highlights_dir = result.highlights_dir
        self._open_dir_btn.setEnabled(self._result_dir is not None)
        self._open_clips_btn.setEnabled(self._highlights_dir is not None)
        log_extra = (
            f"\n로그 파일: {self._smoke_log_path}"
            if getattr(self, "_smoke_log_path", None) else ""
        )
        self._result_label.setText(
            f"✓ 완료 — game_id={result.game_id}\n"
            f"분석 시간: {result.elapsed_sec:.1f}초\n"
            f"카메라: {', '.join(result.cameras)}\n"
            f"출력: {result.output_dir}\n"
            f"하이라이트: {result.highlights_dir or '(없음)'}"
            f"{log_extra}"
        )
        self._smoke_log_path = None

    def _on_failed(self, error: str) -> None:
        self._detach_log_handler()
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress_label.setText(f"실패: {error}")
        log_extra = f"\n로그: {self._smoke_log_path}" if getattr(
            self, "_smoke_log_path", None) else ""
        self._result_label.setText(f"❌ {error}{log_extra}")

    def _detach_log_handler(self) -> None:
        h = getattr(self, "_log_file_handler", None)
        if h is not None:
            try:
                logging.getLogger().removeHandler(h)
                h.close()
            except Exception:
                pass
            self._log_file_handler = None

    def _on_open_dir(self) -> None:
        if self._result_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._result_dir)))

    def _on_open_clips(self) -> None:
        if self._highlights_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._highlights_dir)))


# =============================================================================
def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    app = QApplication(sys.argv)
    win = ReplayAnalyzerWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
