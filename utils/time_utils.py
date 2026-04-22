# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: time_utils.py
설명: 시간 유틸리티 - 프레임/타임스탬프 변환, 경기 시간, 성능 측정

작성자: COURTVIEW AI Team
최종 수정: 2025-12-24

주요 기능:
    - 프레임 ↔ 시간 변환
    - 타임스탬프 포맷팅
    - 경기 시간 관리 (쿼터, 샷클락)
    - 성능 측정 (타이머, 프로파일러)
    - 시간 범위 연산
"""
from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import re
import time
from datetime import datetime, timezone
from collections.abc import Callable, Iterator
from typing import Any
from dataclasses import dataclass, field
from enum import Enum, auto, unique
from functools import wraps
from contextlib import contextmanager


# ============================================================
# 상수 정의 — shared.constants SSOT re-export (Phase 15 H5)
# ============================================================
# shared.constants import (지연 import 최소화 — 모듈 최상위)
from shared.constants.game_management_constants import (
    OVERTIME_DURATION_SEC as _OVERTIME_DURATION_SEC,
    QUARTER_DURATION_SEC as _QUARTER_DURATION_SEC,
    SHOT_CLOCK_FULL_SEC as _SHOT_CLOCK_FULL_SEC,
)
from shared.constants.referee_rule_constants import RuleSet as _RuleSet

# 기본 FPS
DEFAULT_FPS: float = 30.0

# 경기 시간 상수 (초) — shared.constants SSOT re-export
QUARTER_DURATION_NBA: int = _QUARTER_DURATION_SEC[_RuleSet.NBA]    # 720 (12분)
QUARTER_DURATION_FIBA: int = _QUARTER_DURATION_SEC[_RuleSet.FIBA]  # 600 (10분)
SHOT_CLOCK_NBA: int = _SHOT_CLOCK_FULL_SEC                         # 24
SHOT_CLOCK_FIBA: int = _SHOT_CLOCK_FULL_SEC                        # 24
OVERTIME_DURATION: int = _OVERTIME_DURATION_SEC                    # 300 (5분)

# 시간 형식
TIME_FORMAT_HMS: str = "%H:%M:%S"
TIME_FORMAT_MS: str = "%M:%S"
TIME_FORMAT_MSM: str = "%M:%S.%f"  # 밀리초 포함
TIME_FORMAT_ISO: str = "%Y-%m-%dT%H:%M:%S.%fZ"


# ============================================================
# Enum 정의
# ============================================================
@unique
class GamePeriod(Enum):
    """경기 피리어드."""
    Q1 = 1  # 1쿼터
    Q2 = 2  # 2쿼터
    Q3 = 3  # 3쿼터
    Q4 = 4  # 4쿼터
    OT1 = 5  # 1차 연장
    OT2 = 6  # 2차 연장
    OT3 = 7  # 3차 연장
    HALFTIME = 10  # 하프타임
    BREAK = 11  # 휴식


@unique
class TimeUnit(Enum):
    """시간 단위."""
    NANOSECONDS = auto()
    MICROSECONDS = auto()
    MILLISECONDS = auto()
    SECONDS = auto()
    MINUTES = auto()
    HOURS = auto()


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class TimeRange:
    """시간 범위."""

    start: float  # 시작 시간 (초)
    end: float  # 종료 시간 (초)

    def __post_init__(self) -> None:
        """시작/종료 시간 정규화."""
        if self.start > self.end:
            self.start, self.end = self.end, self.start

    @property
    def duration(self) -> float:
        """범위 길이 (초)."""
        return self.end - self.start

    @property
    def midpoint(self) -> float:
        """중간 시점."""
        return (self.start + self.end) / 2

    def contains(self, time_point: float) -> bool:
        """시점이 범위 내에 있는지 확인."""
        return self.start <= time_point <= self.end

    def overlaps(self, other: "TimeRange") -> bool:
        """다른 범위와 겹치는지 확인."""
        return self.start < other.end and other.start < self.end

    def intersection(self, other: "TimeRange") -> TimeRange | None:
        """교집합 범위 반환."""
        if not self.overlaps(other):
            return None
        return TimeRange(
            start=max(self.start, other.start),
            end=min(self.end, other.end)
        )

    def union(self, other: "TimeRange") -> "TimeRange":
        """합집합 범위 반환 (연속 가정)."""
        return TimeRange(
            start=min(self.start, other.start),
            end=max(self.end, other.end)
        )

    def expand(self, amount: float) -> "TimeRange":
        """범위 확장."""
        return TimeRange(
            start=self.start - amount,
            end=self.end + amount
        )


@dataclass(slots=True)
class FrameRange:
    """프레임 범위."""

    start_frame: int
    end_frame: int
    fps: float = DEFAULT_FPS

    def __post_init__(self) -> None:
        """프레임 정규화."""
        if self.start_frame > self.end_frame:
            self.start_frame, self.end_frame = self.end_frame, self.start_frame

    @property
    def frame_count(self) -> int:
        """프레임 개수."""
        return self.end_frame - self.start_frame + 1

    @property
    def duration(self) -> float:
        """지속 시간 (초)."""
        return self.frame_count / self.fps

    def to_time_range(self) -> TimeRange:
        """시간 범위로 변환."""
        return TimeRange(
            start=frame_to_time(self.start_frame, self.fps),
            end=frame_to_time(self.end_frame, self.fps)
        )

    def contains_frame(self, frame: int) -> bool:
        """프레임이 범위 내에 있는지 확인."""
        return self.start_frame <= frame <= self.end_frame


@dataclass(slots=True)
class GameClock:
    """경기 시계."""

    period: GamePeriod
    time_remaining: float  # 남은 시간 (초)
    shot_clock: float | None = None  # 샷클락 (초)
    is_running: bool = False

    @property
    def time_elapsed_in_period(self) -> float:
        """쿼터 내 경과 시간."""
        if self.period == GamePeriod.HALFTIME:
            return 0.0

        period_duration = self._get_period_duration()
        return period_duration - self.time_remaining

    def _get_period_duration(self) -> float:
        """피리어드 길이 반환."""
        if self.period.value <= 4:
            return float(QUARTER_DURATION_FIBA)
        return float(OVERTIME_DURATION)

    def format_display(self) -> str:
        """디스플레이용 포맷."""
        minutes = int(self.time_remaining // 60)
        seconds = self.time_remaining % 60
        return f"{minutes:02d}:{seconds:05.2f}"


@dataclass(slots=True)
class TimerResult:
    """타이머 결과."""

    elapsed_seconds: float
    elapsed_ms: float = field(init=False)
    start_time: float = field(default=0.0)
    end_time: float = field(default=0.0)
    label: str = ""

    def __post_init__(self) -> None:
        """밀리초 계산."""
        self.elapsed_ms = self.elapsed_seconds * 1000


# ============================================================
# 프레임 ↔ 시간 변환
# ============================================================
def frame_to_time(frame_index: int, fps: float = DEFAULT_FPS) -> float:
    """
    프레임 인덱스를 시간(초)으로 변환.

    Args:
        frame_index: 프레임 인덱스 (0-based)
        fps: 초당 프레임 수

    Returns:
        시간 (초)

    Example:
        >>> frame_to_time(30, 30.0)
        1.0
        >>> frame_to_time(45, 30.0)
        1.5
    """
    if fps <= 0:
        return 0.0
    return frame_index / fps


def time_to_frame(time_seconds: float, fps: float = DEFAULT_FPS) -> int:
    """
    시간(초)을 프레임 인덱스로 변환.

    Args:
        time_seconds: 시간 (초)
        fps: 초당 프레임 수

    Returns:
        프레임 인덱스 (0-based)

    Example:
        >>> time_to_frame(1.0, 30.0)
        30
        >>> time_to_frame(1.5, 30.0)
        45
    """
    if fps <= 0:
        return 0
    return int(time_seconds * fps)


def frame_to_timecode(
    frame_index: int,
    fps: float = DEFAULT_FPS,
    include_frames: bool = False
) -> str:
    """
    프레임 인덱스를 타임코드 문자열로 변환.

    Args:
        frame_index: 프레임 인덱스
        fps: 초당 프레임 수
        include_frames: 프레임 번호 포함 여부

    Returns:
        타임코드 문자열 (HH:MM:SS 또는 HH:MM:SS:FF)

    Example:
        >>> frame_to_timecode(3661 * 30, 30.0)
        '01:01:01'
        >>> frame_to_timecode(3661 * 30 + 15, 30.0, include_frames=True)
        '01:01:01:15'
    """
    if fps <= 0:
        return "00:00:00"

    total_seconds = frame_index / fps
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)

    if include_frames:
        frames = int(frame_index % fps)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def timecode_to_frame(
    timecode: str,
    fps: float = DEFAULT_FPS
) -> int | None:
    """
    타임코드 문자열을 프레임 인덱스로 변환.

    Args:
        timecode: 타임코드 (HH:MM:SS 또는 HH:MM:SS:FF 또는 MM:SS)
        fps: 초당 프레임 수

    Returns:
        프레임 인덱스 또는 파싱 실패 시 None
    """
    if fps <= 0:
        return None

    parts = timecode.split(":")
    try:
        if len(parts) == 2:
            # MM:SS
            minutes, seconds = int(parts[0]), float(parts[1])
            total_seconds = minutes * 60 + seconds
        elif len(parts) == 3:
            # HH:MM:SS
            hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
            total_seconds = hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 4:
            # HH:MM:SS:FF
            hours, minutes, seconds, frames = (
                int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
            )
            total_seconds = hours * 3600 + minutes * 60 + seconds
            return int(total_seconds * fps) + frames
        else:
            return None

        return int(total_seconds * fps)

    except (ValueError, IndexError):
        return None


def frames_to_duration(
    frame_count: int,
    fps: float = DEFAULT_FPS
) -> float:
    """
    프레임 개수를 지속 시간(초)으로 변환.

    Args:
        frame_count: 프레임 개수
        fps: 초당 프레임 수

    Returns:
        지속 시간 (초)
    """
    if fps <= 0:
        return 0.0
    return frame_count / fps


def duration_to_frames(
    duration_seconds: float,
    fps: float = DEFAULT_FPS
) -> int:
    """
    지속 시간(초)을 프레임 개수로 변환.

    Args:
        duration_seconds: 지속 시간 (초)
        fps: 초당 프레임 수

    Returns:
        프레임 개수
    """
    if fps <= 0:
        return 0
    return int(duration_seconds * fps)


# ============================================================
# 시간 포맷팅
# ============================================================
def format_seconds(
    seconds: float,
    include_ms: bool = False,
    include_hours: bool = True
) -> str:
    """
    초를 읽기 쉬운 형식으로 포맷.

    Args:
        seconds: 시간 (초)
        include_ms: 밀리초 포함 여부
        include_hours: 시간 포함 여부

    Returns:
        포맷된 문자열

    Example:
        >>> format_seconds(3661.5)
        '01:01:01'
        >>> format_seconds(3661.5, include_ms=True)
        '01:01:01.500'
        >>> format_seconds(61.5, include_hours=False)
        '01:01'
    """
    if seconds < 0:
        seconds = 0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    if include_ms:
        ms = int((secs % 1) * 1000)
        secs = int(secs)
        if include_hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"
        return f"{minutes:02d}:{secs:02d}.{ms:03d}"

    secs = int(secs)
    if include_hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_milliseconds(milliseconds: float) -> str:
    """
    밀리초를 읽기 쉬운 형식으로 포맷.

    Args:
        milliseconds: 시간 (밀리초)

    Returns:
        포맷된 문자열

    Example:
        >>> format_milliseconds(1500)
        '1.500s'
        >>> format_milliseconds(500)
        '500ms'
    """
    if milliseconds >= 1000:
        return f"{milliseconds / 1000:.3f}s"
    return f"{milliseconds:.0f}ms"


def format_duration(
    start_time: float,
    end_time: float,
    include_ms: bool = True
) -> str:
    """
    시작/종료 시간으로부터 지속 시간 문자열 생성.

    Args:
        start_time: 시작 시간 (초)
        end_time: 종료 시간 (초)
        include_ms: 밀리초 포함 여부

    Returns:
        포맷된 지속 시간 문자열
    """
    duration = abs(end_time - start_time)
    return format_seconds(duration, include_ms=include_ms)


def parse_duration(duration_str: str) -> float | None:
    """
    지속 시간 문자열을 초로 파싱.

    지원 형식: '1h30m', '90m', '5400s', '01:30:00', '90:00'

    Args:
        duration_str: 지속 시간 문자열

    Returns:
        초 단위 시간 또는 파싱 실패 시 None
    """

    duration_str = duration_str.strip().lower()

    # HH:MM:SS 또는 MM:SS 형식
    if ":" in duration_str:
        parts = duration_str.split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except ValueError:
            return None

    # 1h30m, 90m, 5400s 형식
    total_seconds = 0.0
    pattern = r"(\d+(?:\.\d+)?)\s*(h|ms|m|s)?"  # ms를 m보다 먼저 배치 (순서 중요)

    matches = re.findall(pattern, duration_str)
    if not matches:
        return None

    for value_str, unit in matches:
        value = float(value_str)
        if unit == "h":
            total_seconds += value * 3600
        elif unit == "m":
            total_seconds += value * 60
        elif unit == "ms":
            total_seconds += value / 1000
        else:  # s or no unit
            total_seconds += value

    return total_seconds


# ============================================================
# 타임스탬프 함수
# ============================================================
def get_current_timestamp() -> float:
    """
    현재 Unix 타임스탬프 반환 (초, 소수점 포함).

    Returns:
        Unix 타임스탬프
    """
    return time.time()


def get_current_timestamp_ms() -> int:
    """
    현재 Unix 타임스탬프 반환 (밀리초).

    Returns:
        Unix 타임스탬프 (밀리초)
    """
    return int(time.time() * 1000)


def timestamp_to_datetime(timestamp: float) -> datetime:
    """
    Unix 타임스탬프를 datetime으로 변환.

    Args:
        timestamp: Unix 타임스탬프 (초)

    Returns:
        datetime 객체 (UTC)
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime) -> float:
    """
    datetime을 Unix 타임스탬프로 변환.

    Args:
        dt: datetime 객체

    Returns:
        Unix 타임스탬프 (초)
    """
    return dt.timestamp()


def format_timestamp(
    timestamp: float,
    format_str: str = TIME_FORMAT_ISO
) -> str:
    """
    타임스탬프를 문자열로 포맷.

    Args:
        timestamp: Unix 타임스탬프
        format_str: 포맷 문자열

    Returns:
        포맷된 문자열
    """
    dt = timestamp_to_datetime(timestamp)
    return dt.strftime(format_str)


def get_iso_timestamp() -> str:
    """
    현재 시간의 ISO 8601 형식 문자열 반환.

    Returns:
        ISO 8601 형식 타임스탬프
    """
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# 성능 측정
# ============================================================
class Timer:
    """
    성능 측정용 타이머.

    컨텍스트 매니저 및 데코레이터로 사용 가능.

    Example:
        # 컨텍스트 매니저
        with Timer("my_operation") as t:
            do_something()
        print(f"Elapsed: {t.elapsed_ms}ms")

        # 데코레이터
        @Timer.decorator("function_name")
        def my_function():
            pass
    """

    def __init__(self, label: str = "") -> None:
        """
        타이머 초기화.

        Args:
            label: 타이머 라벨
        """
        self.label = label
        self._start_time: float = 0.0
        self._end_time: float = 0.0
        self._running: bool = False

    @property
    def elapsed(self) -> float:
        """경과 시간 (초)."""
        if self._running:
            return time.perf_counter() - self._start_time
        return self._end_time - self._start_time

    @property
    def elapsed_ms(self) -> float:
        """경과 시간 (밀리초)."""
        return self.elapsed * 1000

    def start(self) -> "Timer":
        """타이머 시작."""
        self._start_time = time.perf_counter()
        self._running = True
        return self

    def stop(self) -> TimerResult:
        """타이머 정지."""
        self._end_time = time.perf_counter()
        self._running = False
        return TimerResult(
            elapsed_seconds=self.elapsed,
            start_time=self._start_time,
            end_time=self._end_time,
            label=self.label
        )

    def reset(self) -> None:
        """타이머 리셋."""
        self._start_time = 0.0
        self._end_time = 0.0
        self._running = False

    def __enter__(self) -> "Timer":
        """컨텍스트 매니저 진입."""
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        """컨텍스트 매니저 종료."""
        self.stop()

    @staticmethod
    def decorator(label: str = "") -> Callable:
        """
        함수 실행 시간 측정 데코레이터.

        Args:
            label: 라벨 (기본값: 함수명)

        Returns:
            데코레이터
        """
        def _decorator(func: Callable) -> Callable:
            @wraps(func)
            def _wrapper(*args: Any, **kwargs: Any) -> Any:
                timer_label = label or func.__name__
                timer = Timer(timer_label)
                timer.start()
                try:
                    result = func(*args, **kwargs)
                finally:
                    timer.stop()
                return result
            return _wrapper
        return _decorator


@contextmanager
def measure_time(label: str = ""):
    """
    시간 측정 컨텍스트 매니저.

    Args:
        label: 라벨

    Yields:
        Timer 객체

    Example:
        with measure_time("processing") as timer:
            process_data()
        print(f"{timer.label}: {timer.elapsed_ms:.2f}ms")
    """
    timer = Timer(label)
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()


def measure_function(func: Callable, *args: Any, **kwargs: Any) -> tuple[Any, TimerResult]:
    """
    함수 실행 시간 측정.

    Args:
        func: 측정할 함수
        *args: 함수 인자
        **kwargs: 함수 키워드 인자

    Returns:
        (함수 반환값, 타이머 결과)
    """
    timer = Timer(func.__name__)
    timer.start()
    result = func(*args, **kwargs)
    timer_result = timer.stop()
    return result, timer_result


# ============================================================
# 경기 시간 함수
# ============================================================
def get_total_game_time(
    period: GamePeriod,
    time_remaining: float,
    period_duration: int = QUARTER_DURATION_FIBA
) -> float:
    """
    경기 총 경과 시간 계산.

    Args:
        period: 현재 쿼터/피리어드
        time_remaining: 쿼터 내 남은 시간 (초)
        period_duration: 쿼터 길이 (초)

    Returns:
        총 경과 시간 (초)
    """
    if period == GamePeriod.HALFTIME:
        return 2 * period_duration

    period_num = period.value
    if period_num > 4:
        # 연장전
        overtime_num = period_num - 4
        base_time = 4 * period_duration
        overtime_elapsed = (overtime_num - 1) * OVERTIME_DURATION
        current_elapsed = OVERTIME_DURATION - time_remaining
        return base_time + overtime_elapsed + current_elapsed

    # 정규 쿼터
    previous_periods_time = (period_num - 1) * period_duration
    current_period_elapsed = period_duration - time_remaining
    return previous_periods_time + current_period_elapsed


def format_game_clock(time_remaining: float, show_tenths: bool = True) -> str:
    """
    경기 시계 포맷팅.

    Args:
        time_remaining: 남은 시간 (초)
        show_tenths: 1분 미만일 때 0.1초 단위 표시

    Returns:
        포맷된 문자열 (예: "5:30" 또는 "0:23.5")
    """
    if time_remaining < 0:
        time_remaining = 0

    minutes = int(time_remaining // 60)
    seconds = time_remaining % 60

    if show_tenths and time_remaining < 60:
        return f"{minutes}:{seconds:04.1f}"

    return f"{minutes}:{int(seconds):02d}"


def format_shot_clock(shot_clock: float) -> str:
    """
    샷클락 포맷팅.

    Args:
        shot_clock: 샷클락 시간 (초)

    Returns:
        포맷된 문자열
    """
    if shot_clock < 0:
        return "0.0"

    if shot_clock < 5:
        return f"{shot_clock:.1f}"

    return f"{int(shot_clock)}"


def is_clutch_time(
    period: GamePeriod,
    time_remaining: float,
    point_difference: int,
    clutch_threshold_time: float = 300.0,  # 5분
    clutch_threshold_points: int = 5
) -> bool:
    """
    클러치 타임 여부 판정.

    Args:
        period: 현재 쿼터
        time_remaining: 남은 시간 (초)
        point_difference: 점수 차이 (절대값)
        clutch_threshold_time: 클러치 기준 시간 (초)
        clutch_threshold_points: 클러치 기준 점수차

    Returns:
        클러치 타임이면 True
    """
    # 4쿼터 또는 연장전
    if period.value < 4:
        return False

    return (
        time_remaining <= clutch_threshold_time and
        abs(point_difference) <= clutch_threshold_points
    )


# ============================================================
# FPS 관련 함수
# ============================================================
def calculate_fps(frame_count: int, elapsed_seconds: float) -> float:
    """
    FPS 계산.

    Args:
        frame_count: 처리된 프레임 수
        elapsed_seconds: 경과 시간 (초)

    Returns:
        FPS
    """
    if elapsed_seconds <= 0:
        return 0.0
    return frame_count / elapsed_seconds


def calculate_frame_interval(fps: float) -> float:
    """
    프레임 간격 계산 (초).

    Args:
        fps: 초당 프레임 수

    Returns:
        프레임 간격 (초)
    """
    if fps <= 0:
        return 0.0
    return 1.0 / fps


def calculate_frame_interval_ms(fps: float) -> float:
    """
    프레임 간격 계산 (밀리초).

    Args:
        fps: 초당 프레임 수

    Returns:
        프레임 간격 (밀리초)
    """
    return calculate_frame_interval(fps) * 1000


def should_process_frame(
    current_frame: int,
    target_fps: float,
    source_fps: float
) -> bool:
    """
    프레임 스킵 여부 결정.

    소스 FPS가 타겟 FPS보다 높을 때 균등하게 프레임 스킵.

    Args:
        current_frame: 현재 프레임 인덱스
        target_fps: 목표 FPS
        source_fps: 원본 FPS

    Returns:
        처리해야 하면 True
    """
    if source_fps <= 0 or target_fps <= 0:
        return True

    if target_fps >= source_fps:
        return True

    # 스킵 간격 계산
    skip_interval = source_fps / target_fps
    return (current_frame % int(skip_interval)) == 0


def get_frame_indices_for_duration(
    start_time: float,
    end_time: float,
    fps: float = DEFAULT_FPS
) -> list[int]:
    """
    시간 범위에 해당하는 프레임 인덱스 리스트 반환.

    Args:
        start_time: 시작 시간 (초)
        end_time: 종료 시간 (초)
        fps: FPS

    Returns:
        프레임 인덱스 리스트

    Note:
        대규모 범위 (1시간+ 영상)의 경우 메모리 효율을 위해
        iter_frame_indices_for_duration 사용을 권장합니다.
    """
    start_frame = time_to_frame(start_time, fps)
    end_frame = time_to_frame(end_time, fps)
    return list(range(start_frame, end_frame + 1))


def iter_frame_indices_for_duration(
    start_time: float,
    end_time: float,
    fps: float = DEFAULT_FPS
) -> Iterator[int]:
    """
    시간 범위에 해당하는 프레임 인덱스 제너레이터.

    대규모 범위 처리 시 메모리 효율적인 버전.

    Args:
        start_time: 시작 시간 (초)
        end_time: 종료 시간 (초)
        fps: FPS

    Yields:
        프레임 인덱스

    Example:
        >>> for frame_idx in iter_frame_indices_for_duration(0, 3600, 30):
        ...     process_frame(frame_idx)
    """
    start_frame = time_to_frame(start_time, fps)
    end_frame = time_to_frame(end_time, fps)
    for frame_idx in range(start_frame, end_frame + 1):
        yield frame_idx


# ============================================================
# 시간 단위 변환
# ============================================================
def convert_time_unit(
    value: float,
    from_unit: TimeUnit,
    to_unit: TimeUnit
) -> float:
    """
    시간 단위 변환.

    Args:
        value: 변환할 값
        from_unit: 원본 단위
        to_unit: 대상 단위

    Returns:
        변환된 값
    """
    # 나노초 기준으로 변환
    to_nanoseconds = {
        TimeUnit.NANOSECONDS: 1,
        TimeUnit.MICROSECONDS: 1_000,
        TimeUnit.MILLISECONDS: 1_000_000,
        TimeUnit.SECONDS: 1_000_000_000,
        TimeUnit.MINUTES: 60_000_000_000,
        TimeUnit.HOURS: 3_600_000_000_000,
    }

    nanoseconds = value * to_nanoseconds[from_unit]
    return nanoseconds / to_nanoseconds[to_unit]


def seconds_to_hms(seconds: float) -> tuple[int, int, float]:
    """
    초를 시:분:초로 분리.

    Args:
        seconds: 초

    Returns:
        (시간, 분, 초) 튜플
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return hours, minutes, secs


def hms_to_seconds(hours: int, minutes: int, seconds: float) -> float:
    """
    시:분:초를 초로 변환.

    Args:
        hours: 시간
        minutes: 분
        seconds: 초

    Returns:
        총 초
    """
    return hours * 3600 + minutes * 60 + seconds


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # 상수
    "DEFAULT_FPS",
    "QUARTER_DURATION_NBA",
    "QUARTER_DURATION_FIBA",
    "SHOT_CLOCK_NBA",
    "SHOT_CLOCK_FIBA",
    "OVERTIME_DURATION",
    "TIME_FORMAT_HMS",
    "TIME_FORMAT_MS",
    "TIME_FORMAT_MSM",
    "TIME_FORMAT_ISO",
    # Enum
    "GamePeriod",
    "TimeUnit",
    # 데이터 클래스
    "TimeRange",
    "FrameRange",
    "GameClock",
    "TimerResult",
    # 프레임/시간 변환
    "frame_to_time",
    "time_to_frame",
    "frame_to_timecode",
    "timecode_to_frame",
    "frames_to_duration",
    "duration_to_frames",
    # 포맷팅
    "format_seconds",
    "format_milliseconds",
    "format_duration",
    "parse_duration",
    # 타임스탬프
    "get_current_timestamp",
    "get_current_timestamp_ms",
    "timestamp_to_datetime",
    "datetime_to_timestamp",
    "format_timestamp",
    "get_iso_timestamp",
    # 성능 측정
    "Timer",
    "measure_time",
    "measure_function",
    # 경기 시간
    "get_total_game_time",
    "format_game_clock",
    "format_shot_clock",
    "is_clutch_time",
    # FPS
    "calculate_fps",
    "calculate_frame_interval",
    "calculate_frame_interval_ms",
    "should_process_frame",
    "get_frame_indices_for_duration",
    "iter_frame_indices_for_duration",
    # 단위 변환
    "convert_time_unit",
    "seconds_to_hms",
    "hms_to_seconds",
]

__version__: str = "1.0.0"
