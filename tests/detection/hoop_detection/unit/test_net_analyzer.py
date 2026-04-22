# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/hoop_detection/unit
파일: test_net_analyzer.py
설명: NetAnalyzer 단위 테스트
      - NetAnalyzerConfig 설정 클래스
      - _NetMotionState 내부 상태 클래스
      - _ScoringEvent 득점 이벤트 클래스
      - NetAnalyzer 초기화/종료/리셋 라이프사이클
      - analyze() 광학 흐름 분석
      - _classify_pattern() 패턴 분류
      - 쿨다운 로직

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-21
버전: 1.0.0
"""

from __future__ import annotations

from collections import deque

import cv2
import numpy as np
import pytest

from shared.constants.hoop_constants import (
    NET_ANALYSIS_HISTORY_SIZE,
    NET_COOLDOWN_FRAMES,
    NET_MIN_FRAMES_FOR_ANALYSIS,
    NET_MOTION_THRESHOLD_PX,
    NET_SCORE_CONFIDENCE_THRESHOLD,
    NET_SWISH_MAX_DURATION_FRAMES,
    NET_SWISH_MIN_DISPLACEMENT_PX,
    NET_SWISH_VERTICAL_RATIO,
    NET_RIM_IN_MAX_DURATION_FRAMES,
    NET_RIM_IN_MIN_DISPLACEMENT_PX,
    NET_RIM_IN_OSCILLATION_THRESHOLD,
    NET_RIM_OUT_MAX_DISPLACEMENT_PX,
    NET_RIM_OUT_UPPER_RATIO,
)

from detection.hoop_detection.hoop_detector import ScoringType
from detection.hoop_detection.net_analyzer import (
    NetAnalyzer,
    NetAnalyzerConfig,
    _NetMotionState,
    _ScoringEvent,
)


# =============================================================================
# NetAnalyzerConfig 테스트
# =============================================================================

class TestNetAnalyzerConfig:
    """NetAnalyzerConfig 단위 테스트."""

    def test_기본값_상수_참조(self):
        """기본값이 shared constants를 참조."""
        config = NetAnalyzerConfig()
        assert config.history_size == NET_ANALYSIS_HISTORY_SIZE
        assert config.motion_threshold_px == NET_MOTION_THRESHOLD_PX
        assert config.score_confidence_threshold == NET_SCORE_CONFIDENCE_THRESHOLD
        assert config.cooldown_frames == NET_COOLDOWN_FRAMES

    def test_스위시_기준_상수_참조(self):
        """스위시 판정 기준이 shared constants 참조."""
        config = NetAnalyzerConfig()
        assert config.swish_vertical_ratio == NET_SWISH_VERTICAL_RATIO
        assert config.swish_min_displacement_px == NET_SWISH_MIN_DISPLACEMENT_PX
        assert config.swish_max_duration_frames == NET_SWISH_MAX_DURATION_FRAMES

    def test_림인_기준_상수_참조(self):
        """림인 판정 기준이 shared constants 참조."""
        config = NetAnalyzerConfig()
        assert config.rim_in_oscillation_threshold == NET_RIM_IN_OSCILLATION_THRESHOLD
        assert config.rim_in_min_displacement_px == NET_RIM_IN_MIN_DISPLACEMENT_PX
        assert config.rim_in_max_duration_frames == NET_RIM_IN_MAX_DURATION_FRAMES

    def test_림아웃_기준_상수_참조(self):
        """림아웃 판정 기준이 shared constants 참조."""
        config = NetAnalyzerConfig()
        assert config.rim_out_max_displacement_px == NET_RIM_OUT_MAX_DISPLACEMENT_PX
        assert config.rim_out_upper_ratio == NET_RIM_OUT_UPPER_RATIO

    def test_커스텀_값(self):
        """커스텀 값 설정."""
        config = NetAnalyzerConfig(
            history_size=50,
            motion_threshold_px=3.0,
            cooldown_frames=20,
        )
        assert config.history_size == 50
        assert config.motion_threshold_px == 3.0
        assert config.cooldown_frames == 20

    def test_repr_포맷(self):
        """__repr__ 형식."""
        config = NetAnalyzerConfig()
        repr_str = repr(config)
        assert "NetAnalyzerConfig" in repr_str
        assert "history=" in repr_str

    def test_slots_적용(self):
        """slots=True 적용."""
        config = NetAnalyzerConfig()
        assert not hasattr(config, "__dict__")


# =============================================================================
# _NetMotionState 테스트
# =============================================================================

class TestNetMotionState:
    """내부 _NetMotionState 테스트."""

    def test_초기_상태(self):
        """기본 초기값."""
        state = _NetMotionState()
        assert state.is_active is False
        assert state.accumulated_vertical == 0.0
        assert state.accumulated_horizontal == 0.0
        assert state.direction_changes == 0
        assert state.frame_count == 0
        assert state.cooldown_remaining == 0

    def test_total_displacement_영점(self):
        """초기 total_displacement = 0."""
        state = _NetMotionState()
        assert state.total_displacement == 0.0

    def test_total_displacement_계산(self):
        """누적 변위 크기 계산 (피타고라스)."""
        state = _NetMotionState(
            accumulated_vertical=3.0,
            accumulated_horizontal=4.0,
        )
        assert state.total_displacement == pytest.approx(5.0)

    def test_vertical_ratio_영점(self):
        """total=0이면 vertical_ratio=0."""
        state = _NetMotionState()
        assert state.vertical_ratio == 0.0

    def test_vertical_ratio_수직지배(self):
        """수직 지배적 움직임."""
        state = _NetMotionState(
            accumulated_vertical=10.0,
            accumulated_horizontal=1.0,
        )
        assert state.vertical_ratio > 0.9

    def test_reset_motion(self):
        """reset_motion 후 상태 초기화."""
        state = _NetMotionState(
            is_active=True,
            accumulated_vertical=15.0,
            accumulated_horizontal=5.0,
            direction_changes=3,
            frame_count=10,
        )
        state.reset_motion()
        assert state.is_active is False
        assert state.accumulated_vertical == 0.0
        assert state.accumulated_horizontal == 0.0
        assert state.direction_changes == 0
        assert state.frame_count == 0

    def test_apply_decay(self):
        """감쇠 적용."""
        state = _NetMotionState(
            accumulated_vertical=10.0,
            accumulated_horizontal=5.0,
        )
        state.apply_decay(0.5)
        assert state.accumulated_vertical == pytest.approx(5.0)
        assert state.accumulated_horizontal == pytest.approx(2.5)

    def test_displacement_history_maxlen(self):
        """변위 이력 크기 제한."""
        state = _NetMotionState()
        assert state.displacement_history.maxlen == NET_ANALYSIS_HISTORY_SIZE

    def test_repr_포맷(self):
        """__repr__ 형식."""
        state = _NetMotionState(hoop_side="left")
        repr_str = repr(state)
        assert "left" in repr_str
        assert "idle" in repr_str

    def test_repr_active(self):
        """활성 상태 repr."""
        state = _NetMotionState(is_active=True, hoop_side="right")
        assert "active" in repr(state)

    def test_slots_적용(self):
        """slots=True 적용."""
        state = _NetMotionState()
        assert not hasattr(state, "__dict__")


# =============================================================================
# _ScoringEvent 테스트
# =============================================================================

class TestScoringEvent:
    """내부 _ScoringEvent 테스트."""

    def test_기본값(self):
        """기본값은 UNKNOWN, 신뢰도 0."""
        event = _ScoringEvent()
        assert event.scoring_type == ScoringType.UNKNOWN
        assert event.confidence == 0.0

    def test_is_score_스위시(self):
        """스위시 이벤트는 득점."""
        event = _ScoringEvent(scoring_type=ScoringType.SWISH, confidence=0.95)
        assert event.is_score is True

    def test_is_score_림인(self):
        """림인 이벤트는 득점."""
        event = _ScoringEvent(scoring_type=ScoringType.RIM_IN, confidence=0.85)
        assert event.is_score is True

    def test_is_score_림아웃(self):
        """림아웃 이벤트는 미득점."""
        event = _ScoringEvent(scoring_type=ScoringType.RIM_OUT, confidence=0.7)
        assert event.is_score is False

    def test_전체_필드(self):
        """모든 필드 설정."""
        event = _ScoringEvent(
            scoring_type=ScoringType.SWISH,
            confidence=0.95,
            hoop_side="right",
            frame_index=42,
            vertical_displacement=25.0,
            horizontal_displacement=3.0,
            oscillation_count=0,
            duration_frames=8,
            camera_id="cam_1",
        )
        assert event.hoop_side == "right"
        assert event.frame_index == 42
        assert event.vertical_displacement == 25.0
        assert event.camera_id == "cam_1"

    def test_repr_포맷(self):
        """__repr__ 형식."""
        event = _ScoringEvent(
            scoring_type=ScoringType.SWISH, confidence=0.95,
        )
        repr_str = repr(event)
        assert "swish" in repr_str
        assert "0.950" in repr_str

    def test_slots_적용(self):
        """slots=True 적용."""
        event = _ScoringEvent()
        assert not hasattr(event, "__dict__")


# =============================================================================
# NetAnalyzer 라이프사이클 테스트
# =============================================================================

class TestNetAnalyzerLifecycle:
    """NetAnalyzer 초기화/종료/리셋 테스트."""

    def test_인스턴스_생성(self):
        """생성 후 미초기화 상태."""
        analyzer = NetAnalyzer()
        assert analyzer.is_initialized is False
        assert analyzer.total_events == 0
        assert analyzer.total_scores == 0

    def test_initialize(self, net_analyzer_config):
        """초기화 후 is_initialized=True."""
        analyzer = NetAnalyzer()
        analyzer.initialize(net_analyzer_config)
        assert analyzer.is_initialized is True

    def test_shutdown(self, net_analyzer):
        """shutdown 후 미초기화 상태."""
        net_analyzer.shutdown()
        assert net_analyzer.is_initialized is False

    def test_reset_통계_초기화(self, net_analyzer):
        """reset 후 통계 초기화, 설정 유지."""
        net_analyzer._total_events = 5
        net_analyzer._total_scores = 3
        net_analyzer.reset()
        assert net_analyzer.total_events == 0
        assert net_analyzer.total_scores == 0
        assert net_analyzer.is_initialized is True

    def test_미초기화_시_analyze_None(self, left_hoop, dummy_frame_480p):
        """미초기화 상태에서 analyze → None."""
        analyzer = NetAnalyzer()
        result = analyzer.analyze(dummy_frame_480p, left_hoop, frame_index=0)
        assert result is None

    def test_repr(self, net_analyzer):
        """__repr__ 형식."""
        repr_str = repr(net_analyzer)
        assert "NetAnalyzer" in repr_str
        assert "initialized=True" in repr_str


# =============================================================================
# NetAnalyzer 상태 관리 테스트
# =============================================================================

class TestNetAnalyzerStateManagement:
    """NetAnalyzer 골대별 상태 관리 테스트."""

    def test_좌우_독립_상태(self, net_analyzer):
        """좌/우 골대 상태는 독립적."""
        state_left = net_analyzer._get_or_create_state("left")
        state_right = net_analyzer._get_or_create_state("right")
        assert state_left is not state_right
        assert state_left.hoop_side == "left"
        assert state_right.hoop_side == "right"

    def test_동일_side_동일_객체(self, net_analyzer):
        """같은 side는 같은 상태 객체 반환."""
        s1 = net_analyzer._get_or_create_state("left")
        s2 = net_analyzer._get_or_create_state("left")
        assert s1 is s2

    def test_get_state_없는_side(self, net_analyzer):
        """존재하지 않는 side → None."""
        assert net_analyzer.get_state("center") is None

    def test_get_state_존재하는_side(self, net_analyzer):
        """생성된 side → 상태 반환."""
        net_analyzer._get_or_create_state("left")
        state = net_analyzer.get_state("left")
        assert state is not None
        assert state.hoop_side == "left"

    def test_get_all_states(self, net_analyzer):
        """모든 상태 조회."""
        net_analyzer._get_or_create_state("left")
        net_analyzer._get_or_create_state("right")
        all_states = net_analyzer.get_all_states()
        assert "left" in all_states
        assert "right" in all_states
        assert len(all_states) == 2

    def test_get_all_states_방어적_복사(self, net_analyzer):
        """get_all_states는 방어적 복사본 반환."""
        net_analyzer._get_or_create_state("left")
        states = net_analyzer.get_all_states()
        states["fake"] = _NetMotionState()
        assert "fake" not in net_analyzer.get_all_states()


# =============================================================================
# NetAnalyzer analyze 테스트
# =============================================================================

class TestNetAnalyzerAnalyze:
    """NetAnalyzer.analyze() 단위 테스트."""

    def test_첫_프레임_None(self, net_analyzer, left_hoop, rim_frame):
        """첫 프레임은 추적 포인트 초기화만 → None."""
        result = net_analyzer.analyze(rim_frame, left_hoop, frame_index=0)
        assert result is None

    def test_정적_프레임_연속_None(self, net_analyzer, left_hoop):
        """움직임 없는 프레임 연속 → 이벤트 없음."""
        frame = np.full((480, 640, 3), 128, dtype=np.uint8)
        # 추적 가능한 특징 추가
        cv2.rectangle(frame, (300, 140), (340, 200), (255, 255, 255), 2)
        for x in range(305, 340, 5):
            cv2.line(frame, (x, 145), (x, 195), (200, 200, 200), 1)

        for i in range(10):
            result = net_analyzer.analyze(frame, left_hoop, frame_index=i)
            # 정적 프레임 → 이벤트 없음
            if result is not None:
                assert isinstance(result, _ScoringEvent)

    def test_쿨다운_중_분석_스킵(self, net_analyzer, left_hoop, rim_frame):
        """쿨다운 중에는 분석을 건너뜀."""
        # 강제 쿨다운 설정
        state = net_analyzer._get_or_create_state("left")
        state.cooldown_remaining = 5

        result = net_analyzer.analyze(rim_frame, left_hoop, frame_index=0)
        assert result is None
        assert state.cooldown_remaining == 4  # 1 감소

    def test_analyze_batch_빈_목록(self, net_analyzer, dummy_frame_480p):
        """빈 골대 목록 → 빈 이벤트 목록."""
        events = net_analyzer.analyze_batch(dummy_frame_480p, [], frame_index=0)
        assert events == []


# =============================================================================
# _classify_pattern 패턴 분류 테스트
# =============================================================================

class TestClassifyPattern:
    """NetAnalyzer._classify_pattern() 패턴 분류 테스트."""

    def _make_swish_state(self) -> _NetMotionState:
        """스위시 패턴 상태 생성."""
        state = _NetMotionState(
            hoop_side="left",
            is_active=True,
            accumulated_vertical=25.0,  # 강한 수직 변위
            accumulated_horizontal=2.0,  # 약한 수평 변위
            direction_changes=0,
            frame_count=8,
        )
        return state

    def _make_rim_in_state(self) -> _NetMotionState:
        """림인 패턴 상태 생성."""
        state = _NetMotionState(
            hoop_side="left",
            is_active=True,
            accumulated_vertical=15.0,
            accumulated_horizontal=8.0,
            direction_changes=4,  # 진동 다수
            frame_count=15,
        )
        return state

    def _make_rim_out_state(self) -> _NetMotionState:
        """림아웃 패턴 상태 생성."""
        state = _NetMotionState(
            hoop_side="left",
            is_active=True,
            accumulated_vertical=3.0,
            accumulated_horizontal=2.0,
            direction_changes=1,
            frame_count=NET_MIN_FRAMES_FOR_ANALYSIS,
            upper_motion_ratio=0.5,
        )
        return state

    def test_스위시_판별(self, net_analyzer):
        """스위시 패턴 → SWISH 이벤트."""
        state = self._make_swish_state()
        config = NetAnalyzerConfig()
        event = net_analyzer._classify_pattern(state, 100, None, config)

        assert event is not None
        assert event.scoring_type == ScoringType.SWISH
        assert event.confidence > 0.0
        assert event.is_score is True

    def test_림인_판별(self, net_analyzer):
        """림인 패턴 → RIM_IN 이벤트."""
        state = self._make_rim_in_state()
        config = NetAnalyzerConfig()
        event = net_analyzer._classify_pattern(state, 200, None, config)

        assert event is not None
        assert event.scoring_type == ScoringType.RIM_IN
        assert event.confidence > 0.0
        assert event.is_score is True

    def test_림아웃_판별(self, net_analyzer):
        """림아웃 패턴 → RIM_OUT 이벤트."""
        state = self._make_rim_out_state()
        config = NetAnalyzerConfig()
        event = net_analyzer._classify_pattern(state, 300, None, config)

        assert event is not None
        assert event.scoring_type == ScoringType.RIM_OUT
        assert event.is_score is False

    def test_판별_불가(self, net_analyzer):
        """어떤 패턴에도 해당하지 않으면 None."""
        state = _NetMotionState(
            is_active=True,
            accumulated_vertical=0.5,  # 너무 작은 변위
            accumulated_horizontal=0.5,
            frame_count=1,
        )
        config = NetAnalyzerConfig()
        event = net_analyzer._classify_pattern(state, 400, None, config)
        assert event is None

    def test_스위시_이벤트_필드(self, net_analyzer):
        """스위시 이벤트의 모든 필드 확인."""
        state = self._make_swish_state()
        config = NetAnalyzerConfig()
        event = net_analyzer._classify_pattern(state, 100, "cam_1", config)

        assert event is not None
        assert event.hoop_side == "left"
        assert event.frame_index == 100
        assert event.camera_id == "cam_1"
        assert event.vertical_displacement == 25.0
        assert event.horizontal_displacement == 2.0
        assert event.duration_frames == 8

    def test_스위시_우선순위(self, net_analyzer):
        """스위시 조건 충족 시 림인보다 우선."""
        state = _NetMotionState(
            hoop_side="left",
            is_active=True,
            accumulated_vertical=30.0,
            accumulated_horizontal=1.0,
            direction_changes=5,  # 림인 조건도 충족
            frame_count=8,
        )
        config = NetAnalyzerConfig()
        event = net_analyzer._classify_pattern(state, 100, None, config)

        assert event is not None
        assert event.scoring_type == ScoringType.SWISH


# =============================================================================
# __all__ / __version__ Export 테스트
# =============================================================================

class TestNetAnalyzerExport:
    """모듈 export 정합성 테스트."""

    def test_net_analyzer_all(self):
        """net_analyzer.py __all__ 정의."""
        from detection.hoop_detection import net_analyzer as mod
        assert "NetAnalyzer" in mod.__all__

    def test_net_analyzer_version(self):
        """net_analyzer.py __version__."""
        from detection.hoop_detection import net_analyzer as mod
        assert mod.__version__ == "1.0.0"

    def test_init_all_포함_NetAnalyzer(self):
        """__init__.py __all__에 NetAnalyzer 포함."""
        from detection import hoop_detection
        assert "NetAnalyzer" in hoop_detection.__all__

    def test_init_all_포함_NetAnalyzerConfig(self):
        """__init__.py __all__에 NetAnalyzerConfig 포함."""
        from detection import hoop_detection
        assert "NetAnalyzerConfig" in hoop_detection.__all__
