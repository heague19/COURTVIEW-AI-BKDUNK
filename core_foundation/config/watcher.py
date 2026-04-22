# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/config
파일: watcher.py
설명: 설정 파일 변경 감시 엔진
      - 파일 시스템 폴링 기반 변경 감지 (mtime + size)
      - 변경 콜백 등록/해제
      - 백그라운드 감시 스레드 (daemon)
      - 감시 일시정지/재개
      - 변경 이력 추적

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from pathlib import Path
from typing import Any, Callable, ClassVar, Final


# =============================================================================
# 상수 정의
# =============================================================================

# 기본 폴링 간격 (초)
DEFAULT_POLL_INTERVAL: Final[float] = 2.0

# 최소 폴링 간격 (초) — CPU 과부하 방지
MIN_POLL_INTERVAL: Final[float] = 0.5

# 최대 폴링 간격 (초)
MAX_POLL_INTERVAL: Final[float] = 60.0

# 콜백 최대 등록 수 (무한 성장 방지)
MAX_CALLBACKS: Final[int] = 100

# 변경 이력 최대 보관 수
MAX_CHANGE_HISTORY: Final[int] = 200


# =============================================================================
# 변경 이벤트 열거형
# =============================================================================

@unique
class FileChangeType(Enum):
    """파일 변경 유형."""

    MODIFIED = "modified"
    CREATED = "created"
    DELETED = "deleted"

    def to_korean(self) -> str:
        """한글 이름 반환."""
        return _CHANGE_TYPE_KOREAN_MAP[self]


_CHANGE_TYPE_KOREAN_MAP: Final[dict[FileChangeType, str]] = {
    FileChangeType.MODIFIED: "수정",
    FileChangeType.CREATED: "생성",
    FileChangeType.DELETED: "삭제",
}


# =============================================================================
# 변경 이벤트 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class FileChangeEvent:
    """파일 변경 이벤트.

    Attributes:
        file_path: 변경된 파일 경로
        change_type: 변경 유형
        timestamp: 감지 시각 (monotonic)
        old_mtime: 이전 수정 시각 (없으면 None)
        new_mtime: 새 수정 시각 (없으면 None)
        old_size: 이전 파일 크기 (없으면 None)
        new_size: 새 파일 크기 (없으면 None)
    """

    file_path: str
    change_type: FileChangeType
    timestamp: float
    old_mtime: float | None = None
    new_mtime: float | None = None
    old_size: int | None = None
    new_size: int | None = None

    def __repr__(self) -> str:
        return (
            f"FileChangeEvent("
            f"[{self.change_type.value}] {self.file_path})"
        )


# =============================================================================
# 파일 상태 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class _FileState:
    """감시 대상 파일의 마지막 상태."""

    mtime: float
    size: int
    exists: bool


# =============================================================================
# 콜백 타입 정의
# =============================================================================

# 변경 콜백: (event: FileChangeEvent) -> None
ChangeCallback = Callable[[FileChangeEvent], None]


# =============================================================================
# 핵심 클래스: ConfigWatcher
# =============================================================================

class ConfigWatcher:
    """설정 파일 변경 감시기.

    파일 시스템 폴링 방식으로 감시 대상 파일의 변경을 감지한다.
    서드파티 watchdog 등의 의존성 없이 순수 표준 라이브러리만 사용.

    감지 기준:
        - mtime (수정 시각) 변경
        - size (파일 크기) 변경
        - 파일 생성/삭제

    스레드 안전:
        - 감시 스레드: daemon 스레드로 실행
        - 콜백 등록/해제: RLock 보호
        - 콜백 실행: 메인 감시 스레드에서 동기 호출

    사용 예시::

        watcher = ConfigWatcher(poll_interval=2.0)

        # 감시 대상 추가
        watcher.watch("configs/core_foundation/config.yaml")

        # 변경 콜백 등록
        def on_change(event: FileChangeEvent):
            print(f"변경 감지: {event.file_path}")
        watcher.add_callback(on_change)

        # 감시 시작
        watcher.start()

        # ... 앱 실행 ...

        # 감시 중지
        watcher.stop()
    """

    def __init__(
        self,
        *,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """ConfigWatcher 초기화.

        Args:
            poll_interval: 폴링 간격 (초). MIN~MAX 범위로 클램핑.
        """
        self._lock = threading.RLock()

        # 폴링 간격 클램핑
        self._poll_interval = max(
            MIN_POLL_INTERVAL,
            min(poll_interval, MAX_POLL_INTERVAL),
        )

        # 감시 대상: 절대 경로 → 마지막 상태
        self._watched_files: dict[str, _FileState | None] = {}

        # 콜백 목록
        self._callbacks: list[ChangeCallback] = []

        # 변경 이력
        self._change_history: list[FileChangeEvent] = []

        # 감시 스레드 상태
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._paused = False

    # =========================================================================
    # 감시 대상 관리
    # =========================================================================

    def watch(self, file_path: str | Path) -> bool:
        """감시 대상 파일 추가.

        Args:
            file_path: 감시할 파일 경로 (절대 또는 상대)

        Returns:
            새로 추가되면 True, 이미 감시 중이면 False
        """
        resolved = str(Path(file_path).resolve())

        with self._lock:
            if resolved in self._watched_files:
                return False

            # 현재 파일 상태 캡처
            state = self._capture_file_state(resolved)
            self._watched_files[resolved] = state
            return True

    def unwatch(self, file_path: str | Path) -> bool:
        """감시 대상 파일 제거.

        Args:
            file_path: 제거할 파일 경로

        Returns:
            제거 성공 여부
        """
        resolved = str(Path(file_path).resolve())

        with self._lock:
            if resolved in self._watched_files:
                del self._watched_files[resolved]
                return True
            return False

    def watch_directory(self, dir_path: str | Path, pattern: str = "*.yaml") -> int:
        """디렉토리 내 파일 일괄 감시.

        Args:
            dir_path: 감시할 디렉토리 경로
            pattern: glob 패턴 (기본: *.yaml)

        Returns:
            새로 추가된 파일 수
        """
        directory = Path(dir_path).resolve()
        if not directory.is_dir():
            return 0

        count = 0
        for file_path in directory.rglob(pattern):
            if file_path.is_file():
                if self.watch(file_path):
                    count += 1
        return count

    @property
    def watched_files(self) -> list[str]:
        """감시 중인 파일 목록."""
        with self._lock:
            return list(self._watched_files.keys())

    @property
    def watched_count(self) -> int:
        """감시 중인 파일 수."""
        with self._lock:
            return len(self._watched_files)

    # =========================================================================
    # 콜백 관리
    # =========================================================================

    def add_callback(self, callback: ChangeCallback) -> bool:
        """변경 콜백 등록.

        Args:
            callback: 변경 이벤트 콜백 함수

        Returns:
            등록 성공 여부 (최대 수 초과 시 False)
        """
        with self._lock:
            if len(self._callbacks) >= MAX_CALLBACKS:
                return False
            self._callbacks.append(callback)
            return True

    def remove_callback(self, callback: ChangeCallback) -> bool:
        """변경 콜백 해제.

        Args:
            callback: 해제할 콜백 함수

        Returns:
            해제 성공 여부
        """
        with self._lock:
            try:
                self._callbacks.remove(callback)
                return True
            except ValueError:
                return False

    def clear_callbacks(self) -> None:
        """모든 콜백 해제."""
        with self._lock:
            self._callbacks.clear()

    @property
    def callback_count(self) -> int:
        """등록된 콜백 수."""
        with self._lock:
            return len(self._callbacks)

    # =========================================================================
    # 감시 제어
    # =========================================================================

    def start(self) -> bool:
        """감시 시작.

        백그라운드 daemon 스레드를 시작한다.

        Returns:
            시작 성공 여부 (이미 실행 중이면 False)
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False

            self._stop_event.clear()
            self._paused = False
            self._thread = threading.Thread(
                target=self._poll_loop,
                name="ConfigWatcher-Poll",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float = 5.0) -> bool:
        """감시 중지.

        Args:
            timeout: 스레드 종료 대기 시간 (초)

        Returns:
            정상 종료 여부
        """
        self._stop_event.set()

        with self._lock:
            thread = self._thread
            self._thread = None

        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            return not thread.is_alive()
        return True

    def pause(self) -> None:
        """감시 일시정지. 스레드는 유지하되 폴링 건너뜀."""
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        """감시 재개."""
        with self._lock:
            self._paused = False

    @property
    def is_running(self) -> bool:
        """감시 스레드 실행 중 여부."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def is_paused(self) -> bool:
        """감시 일시정지 여부."""
        with self._lock:
            return self._paused

    # =========================================================================
    # 변경 이력
    # =========================================================================

    @property
    def change_history(self) -> list[FileChangeEvent]:
        """변경 이력 (방어적 복사)."""
        with self._lock:
            return list(self._change_history)

    @property
    def change_count(self) -> int:
        """누적 변경 감지 수."""
        with self._lock:
            return len(self._change_history)

    def clear_history(self) -> None:
        """변경 이력 초기화."""
        with self._lock:
            self._change_history.clear()

    # =========================================================================
    # 수동 폴링
    # =========================================================================

    def poll_once(self) -> list[FileChangeEvent]:
        """1회 수동 폴링.

        감시 스레드 없이도 변경 감지 가능.

        Returns:
            감지된 변경 이벤트 목록
        """
        with self._lock:
            return self._check_all_files()

    # =========================================================================
    # 내부 메서드 — 폴링 루프
    # =========================================================================

    def _poll_loop(self) -> None:
        """백그라운드 폴링 루프."""
        while not self._stop_event.is_set():
            if not self._paused:
                with self._lock:
                    events = self._check_all_files()

                # 콜백 실행 (lock 밖에서)
                for event in events:
                    self._fire_callbacks(event)

            # 폴링 간격 대기 (stop_event로 조기 중단 가능)
            self._stop_event.wait(timeout=self._poll_interval)

    def _check_all_files(self) -> list[FileChangeEvent]:
        """모든 감시 대상 파일 변경 확인.

        Returns:
            감지된 변경 이벤트 목록
        """
        events: list[FileChangeEvent] = []
        now = time.monotonic()

        for file_path, old_state in list(self._watched_files.items()):
            new_state = self._capture_file_state(file_path)
            event = self._detect_change(file_path, old_state, new_state, now)

            if event is not None:
                events.append(event)
                self._change_history.append(event)
                self._watched_files[file_path] = new_state

        # 이력 최대 수 제한
        while len(self._change_history) > MAX_CHANGE_HISTORY:
            self._change_history.pop(0)

        return events

    def _fire_callbacks(self, event: FileChangeEvent) -> None:
        """콜백 실행 (예외 격리).

        콜백에서 예외가 발생해도 다른 콜백에는 영향 없음.
        """
        with self._lock:
            callbacks = list(self._callbacks)

        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                # 콜백 예외 격리 — 로깅은 monitoring 모듈 구축 후 연동
                pass

    # =========================================================================
    # 내부 메서드 — 파일 상태
    # =========================================================================

    @staticmethod
    def _capture_file_state(file_path: str) -> _FileState | None:
        """파일 현재 상태 캡처.

        Args:
            file_path: 파일 절대 경로

        Returns:
            파일 상태. 존재하지 않으면 exists=False 상태.
        """
        path = Path(file_path)
        try:
            if path.is_file():
                stat = path.stat()
                return _FileState(
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                    exists=True,
                )
        except OSError:
            pass

        return _FileState(mtime=0.0, size=0, exists=False)

    @staticmethod
    def _detect_change(
        file_path: str,
        old_state: _FileState | None,
        new_state: _FileState | None,
        timestamp: float,
    ) -> FileChangeEvent | None:
        """두 상태를 비교하여 변경 이벤트 생성.

        Args:
            file_path: 파일 경로
            old_state: 이전 상태
            new_state: 현재 상태
            timestamp: 감지 시각

        Returns:
            변경 이벤트. 변경 없으면 None.
        """
        # 초기 상태 (첫 폴링)
        if old_state is None:
            if new_state is not None and new_state.exists:
                return FileChangeEvent(
                    file_path=file_path,
                    change_type=FileChangeType.CREATED,
                    timestamp=timestamp,
                    new_mtime=new_state.mtime,
                    new_size=new_state.size,
                )
            return None

        old_exists = old_state.exists
        new_exists = new_state is not None and new_state.exists

        # 삭제
        if old_exists and not new_exists:
            return FileChangeEvent(
                file_path=file_path,
                change_type=FileChangeType.DELETED,
                timestamp=timestamp,
                old_mtime=old_state.mtime,
                old_size=old_state.size,
            )

        # 생성
        if not old_exists and new_exists:
            return FileChangeEvent(
                file_path=file_path,
                change_type=FileChangeType.CREATED,
                timestamp=timestamp,
                new_mtime=new_state.mtime if new_state else None,
                new_size=new_state.size if new_state else None,
            )

        # 수정 (mtime 또는 size 변경)
        if old_exists and new_exists and new_state is not None:
            if (
                old_state.mtime != new_state.mtime
                or old_state.size != new_state.size
            ):
                return FileChangeEvent(
                    file_path=file_path,
                    change_type=FileChangeType.MODIFIED,
                    timestamp=timestamp,
                    old_mtime=old_state.mtime,
                    new_mtime=new_state.mtime,
                    old_size=old_state.size,
                    new_size=new_state.size,
                )

        return None

    @property
    def poll_interval(self) -> float:
        """현재 폴링 간격 (초)."""
        return self._poll_interval

    def __repr__(self) -> str:
        return (
            f"ConfigWatcher("
            f"files={self.watched_count}, "
            f"running={self.is_running}, "
            f"interval={self._poll_interval}s)"
        )


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # Enum
    "FileChangeType",
    # 데이터 클래스
    "FileChangeEvent",
    # 상수
    "DEFAULT_POLL_INTERVAL",
    "MIN_POLL_INTERVAL",
    "MAX_POLL_INTERVAL",
    "MAX_CALLBACKS",
    "MAX_CHANGE_HISTORY",
    # 타입
    "ChangeCallback",
    # 핵심 클래스
    "ConfigWatcher",
]

__version__ = "1.0.0"
