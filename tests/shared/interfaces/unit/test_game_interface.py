# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/interfaces/unit
파일: test_game_interface.py
설명: game_interface.py 단위 테스트 (8개 export, 전체 메서드/프로퍼티 검증)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
from abc import ABC
from dataclasses import fields
from datetime import datetime, timezone
from enum import Enum
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# 테스트 대상 임포트
# =============================================================================
import numpy as np

from shared.constants.localization import SupportedLanguage
from shared.interfaces.game_interface import (
    GameModuleState,
    GameEventResult,
    ValidationResult,
    FusionResult,
    GameModuleMetrics,
    IGameEventDetector,
    IRefereeValidator,
    IMultiViewFusion,
    __version__,
)


# =============================================================================
# 테스트 하네스
# =============================================================================
class TestResult:
    """단위 테스트 결과 수집기."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.section = ""

    def set_section(self, name: str) -> None:
        self.section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, msg: str = "") -> None:
        self.failed += 1
        detail = f" - {msg}" if msg else ""
        print(f"  [FAIL] {name}{detail}")

    def check(self, name: str, condition: bool, msg: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        print(f"{'='*60}")
        return self.failed == 0


# =============================================================================
# 구체 스텁 클래스 (ABC 검증용)
# =============================================================================
class StubEventDetector(IGameEventDetector[dict, dict]):
    """IGameEventDetector 구체 구현 스텁."""

    def __init__(self) -> None:
        self._state = GameModuleState.UNINITIALIZED
        self._metrics = GameModuleMetrics()
        self._active_events: list[dict] = []
        self._event_history: list[dict] = []

    @property
    def name(self) -> str:
        return "StubEventDetector"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> GameModuleState:
        return self._state

    @property
    def metrics(self) -> GameModuleMetrics:
        return self._metrics

    @property
    def supported_events(self) -> list[str]:
        return ["shot", "foul", "violation"]

    def initialize(self, config: dict) -> None:
        self._state = GameModuleState.READY

    def detect_events(
        self,
        frame: np.ndarray,
        detections: list[Any],
        tracks: list[Any],
        poses: list[Any],
        frame_index: int = 0,
        timestamp_ms: float = 0.0,
    ) -> GameEventResult[list[dict]]:
        self._state = GameModuleState.PROCESSING
        event = {"type": "shot", "frame": frame_index, "ts": timestamp_ms}
        self._active_events.append(event)
        self._event_history.append(event)
        result = GameEventResult.success_result(
            data=[event],
            confidence=0.9,
            events_detected=1,
            frame_index=frame_index,
        )
        self._state = GameModuleState.READY
        return result

    def get_active_events(self) -> list[dict]:
        return list(self._active_events)

    def get_event_history(
        self,
        event_type: str | None = None,
        start_time_ms: float | None = None,
        end_time_ms: float | None = None,
        max_count: int = 100,
    ) -> list[dict]:
        result = self._event_history
        if event_type is not None:
            result = [e for e in result if e.get("type") == event_type]
        return result[:max_count]

    def reset(self) -> None:
        self._state = GameModuleState.UNINITIALIZED
        self._active_events.clear()
        self._event_history.clear()
        self._metrics = GameModuleMetrics()

    def shutdown(self) -> None:
        self._state = GameModuleState.SHUTDOWN


class StubRefereeValidator(IRefereeValidator[dict]):
    """IRefereeValidator 구체 구현 스텁."""

    def __init__(self) -> None:
        self._state = GameModuleState.UNINITIALIZED
        self._metrics = GameModuleMetrics()
        self._rule_set = "fiba"
        self._decisions: list[Any] = []

    @property
    def name(self) -> str:
        return "StubRefereeValidator"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> GameModuleState:
        return self._state

    @property
    def metrics(self) -> GameModuleMetrics:
        return self._metrics

    @property
    def active_rule_set(self) -> str:
        return self._rule_set

    @property
    def confidence_threshold(self) -> float:
        return 0.85

    @property
    def consistency_score(self) -> float:
        return 0.9 if self._decisions else 0.0

    def initialize(self, config: dict, rule_set: str = "fiba") -> None:
        self._state = GameModuleState.READY
        self._rule_set = rule_set

    def validate_violation(
        self,
        violation_data: Any,
        evidence: dict[str, Any],
    ) -> ValidationResult:
        result = ValidationResult.confirmed(
            confidence=0.92,
            rule_reference="FIBA Art.25",
            explanation="트래블링 확인",
            processing_time_ms=5.0,
            evidence_quality=0.88,
        )
        self._decisions.append(result)
        return result

    def validate_foul(
        self,
        foul_data: Any,
        evidence: dict[str, Any],
    ) -> ValidationResult:
        result = ValidationResult.confirmed(
            confidence=0.88,
            rule_reference="FIBA Art.33",
            explanation="개인 파울 확인",
            processing_time_ms=6.0,
            evidence_quality=0.85,
        )
        self._decisions.append(result)
        return result

    def check_consistency(
        self,
        decision: Any,
        history: list[Any],
    ) -> float:
        return 0.95

    def get_decision_explanation(
        self,
        decision: Any,
        lang: str = "ko",
    ) -> str:
        if lang == "en":
            return "Test decision explanation"
        return "테스트 판정 설명"

    def reset(self) -> None:
        self._state = GameModuleState.UNINITIALIZED
        self._decisions.clear()

    def shutdown(self) -> None:
        self._state = GameModuleState.SHUTDOWN


class StubMultiViewFusion(IMultiViewFusion[dict]):
    """IMultiViewFusion 구체 구현 스텁."""

    def __init__(self) -> None:
        self._state = GameModuleState.UNINITIALIZED
        self._metrics = GameModuleMetrics()
        self._num_views = 0
        self._calibration_quality = 0.0

    @property
    def name(self) -> str:
        return "StubMultiViewFusion"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def state(self) -> GameModuleState:
        return self._state

    @property
    def metrics(self) -> GameModuleMetrics:
        return self._metrics

    @property
    def num_views(self) -> int:
        return self._num_views

    @property
    def calibration_quality(self) -> float:
        return self._calibration_quality

    def initialize(
        self, config: dict, calibrations: list[Any] | None = None
    ) -> None:
        self._state = GameModuleState.READY
        self._num_views = len(calibrations) if calibrations else 0
        self._calibration_quality = 0.95 if calibrations else 0.0

    def fuse_detections(
        self, per_view_detections: dict[str, list[Any]]
    ) -> FusionResult[list[Any]]:
        merged = []
        for dets in per_view_detections.values():
            merged.extend(dets)
        return FusionResult.success_result(
            data=merged,
            confidence=0.85,
            num_views_used=len(per_view_detections),
        )

    def fuse_poses(
        self, per_view_poses: dict[str, list[Any]]
    ) -> FusionResult[list[Any]]:
        merged = []
        for poses in per_view_poses.values():
            merged.extend(poses)
        return FusionResult.success_result(
            data=merged,
            confidence=0.88,
            num_views_used=len(per_view_poses),
        )

    def fuse_trajectories(
        self, per_view_trajectories: dict[str, list[Any]]
    ) -> FusionResult[list[Any]]:
        merged = []
        for trajs in per_view_trajectories.values():
            merged.extend(trajs)
        return FusionResult.success_result(
            data=merged,
            confidence=0.82,
            num_views_used=len(per_view_trajectories),
        )

    def triangulate_point(
        self, per_view_points: dict[str, tuple[float, float]]
    ) -> tuple[float, float, float]:
        if len(per_view_points) < 2:
            raise ValueError("2개 이상의 뷰 필요")
        return (1.0, 2.0, 3.0)

    def reset(self) -> None:
        self._state = GameModuleState.UNINITIALIZED
        self._num_views = 0
        self._calibration_quality = 0.0

    def shutdown(self) -> None:
        self._state = GameModuleState.SHUTDOWN


# =============================================================================
# 유틸: 테스트용 프레임 생성
# =============================================================================
def make_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """BGR 테스트 프레임 생성."""
    return np.zeros((h, w, 3), dtype=np.uint8)


# =============================================================================
# 1. GameModuleState 테스트
# =============================================================================
def test_game_module_state_members(t: TestResult) -> None:
    """GameModuleState 멤버 값 및 수량 검증."""
    members = list(GameModuleState)
    t.check("멤버 수 = 7", len(members) == 7, f"실제: {len(members)}")

    expected = {
        "UNINITIALIZED": "uninitialized",
        "INITIALIZING": "initializing",
        "READY": "ready",
        "PROCESSING": "processing",
        "PAUSED": "paused",
        "ERROR": "error",
        "SHUTDOWN": "shutdown",
    }
    for name, value in expected.items():
        state = GameModuleState[name]
        t.check(f"{name} = '{value}'", state.value == value)


def test_game_module_state_str(t: TestResult) -> None:
    """GameModuleState __str__ 테스트."""
    for state in GameModuleState:
        t.check(f"str({state.name}) = value", str(state) == state.value)


def test_game_module_state_str_enum(t: TestResult) -> None:
    """GameModuleState가 str, Enum 동시 상속 검증."""
    t.check("str 상속", issubclass(GameModuleState, str))
    t.check("Enum 상속", issubclass(GameModuleState, Enum))
    # str이므로 문자열 연산 가능
    t.check("문자열 upper() 가능",
            GameModuleState.READY.upper() == "READY")
    t.check("문자열 startswith() 가능",
            GameModuleState.INITIALIZING.startswith("init"))


def test_game_module_state_get_name(t: TestResult) -> None:
    """GameModuleState.get_name() 다국어 테스트."""
    # 한국어 기본값
    t.check("READY 한국어 = '준비 완료'",
            GameModuleState.READY.get_name() == "준비 완료")
    t.check("ERROR 한국어 = '오류'",
            GameModuleState.ERROR.get_name(SupportedLanguage.KO) == "오류")

    # 영어
    t.check("READY 영어 = 'Ready'",
            GameModuleState.READY.get_name(SupportedLanguage.EN) == "Ready")
    t.check("INITIALIZING 영어 = 'Initializing'",
            GameModuleState.INITIALIZING.get_name(SupportedLanguage.EN) == "Initializing")

    # 일본어
    t.check("PAUSED 일본어 = '一時停止'",
            GameModuleState.PAUSED.get_name(SupportedLanguage.JA) == "一時停止")

    # 중국어
    t.check("SHUTDOWN 중국어 = '已关闭'",
            GameModuleState.SHUTDOWN.get_name(SupportedLanguage.ZH) == "已关闭")

    # 스페인어
    t.check("UNINITIALIZED 스페인어 = 'Sin inicializar'",
            GameModuleState.UNINITIALIZED.get_name(SupportedLanguage.ES) == "Sin inicializar")

    # 모든 상태 × 모든 언어 조합 누락 없음
    for state in GameModuleState:
        for lang in [SupportedLanguage.KO, SupportedLanguage.EN,
                     SupportedLanguage.JA, SupportedLanguage.ZH,
                     SupportedLanguage.ES]:
            name = state.get_name(lang)
            t.check(f"get_name({state.name}, {lang.value}) 비어있지 않음",
                    isinstance(name, str) and len(name) > 0)


def test_game_module_state_to_korean(t: TestResult) -> None:
    """GameModuleState.to_korean 프로퍼티 테스트."""
    expected_ko = {
        GameModuleState.UNINITIALIZED: "초기화 전",
        GameModuleState.INITIALIZING: "초기화 중",
        GameModuleState.READY: "준비 완료",
        GameModuleState.PROCESSING: "처리 중",
        GameModuleState.PAUSED: "일시 정지",
        GameModuleState.ERROR: "오류",
        GameModuleState.SHUTDOWN: "종료됨",
    }
    for state, ko_name in expected_ko.items():
        t.check(f"{state.name}.to_korean = '{ko_name}'",
                state.to_korean == ko_name)


def test_game_module_state_is_active(t: TestResult) -> None:
    """GameModuleState.is_active 프로퍼티 테스트."""
    t.check("READY.is_active = True", GameModuleState.READY.is_active is True)
    t.check("PROCESSING.is_active = True", GameModuleState.PROCESSING.is_active is True)
    t.check("PAUSED.is_active = True", GameModuleState.PAUSED.is_active is True)
    t.check("UNINITIALIZED.is_active = False", GameModuleState.UNINITIALIZED.is_active is False)
    t.check("INITIALIZING.is_active = False", GameModuleState.INITIALIZING.is_active is False)
    t.check("ERROR.is_active = False", GameModuleState.ERROR.is_active is False)
    t.check("SHUTDOWN.is_active = False", GameModuleState.SHUTDOWN.is_active is False)


def test_game_module_state_is_initializing(t: TestResult) -> None:
    """GameModuleState.is_initializing 프로퍼티 테스트."""
    t.check("INITIALIZING.is_initializing = True",
            GameModuleState.INITIALIZING.is_initializing is True)
    for state in GameModuleState:
        if state != GameModuleState.INITIALIZING:
            t.check(f"{state.name}.is_initializing = False",
                    state.is_initializing is False)


def test_game_module_state_is_error(t: TestResult) -> None:
    """GameModuleState.is_error 프로퍼티 테스트."""
    t.check("ERROR.is_error = True", GameModuleState.ERROR.is_error is True)
    for state in GameModuleState:
        if state != GameModuleState.ERROR:
            t.check(f"{state.name}.is_error = False", state.is_error is False)


def test_game_module_state_is_terminated(t: TestResult) -> None:
    """GameModuleState.is_terminated 프로퍼티 테스트."""
    t.check("SHUTDOWN.is_terminated = True",
            GameModuleState.SHUTDOWN.is_terminated is True)
    t.check("ERROR.is_terminated = True",
            GameModuleState.ERROR.is_terminated is True)
    for state in GameModuleState:
        if state not in (GameModuleState.SHUTDOWN, GameModuleState.ERROR):
            t.check(f"{state.name}.is_terminated = False",
                    state.is_terminated is False)


def test_game_module_state_can_process(t: TestResult) -> None:
    """GameModuleState.can_process 프로퍼티 테스트."""
    t.check("READY.can_process = True", GameModuleState.READY.can_process is True)
    t.check("PAUSED.can_process = True", GameModuleState.PAUSED.can_process is True)
    for state in GameModuleState:
        if state not in (GameModuleState.READY, GameModuleState.PAUSED):
            t.check(f"{state.name}.can_process = False",
                    state.can_process is False)


# =============================================================================
# 2. GameEventResult 테스트
# =============================================================================
def test_game_event_result_success_factory(t: TestResult) -> None:
    """GameEventResult.success_result() 팩토리 테스트."""
    r = GameEventResult.success_result(
        data=[{"type": "shot"}],
        confidence=0.92,
        processing_time_ms=15.5,
        frame_index=42,
        events_detected=1,
        metadata={"source": "test"},
    )
    t.check("success = True", r.success is True)
    t.check("data 설정됨", r.data == [{"type": "shot"}])
    t.check("confidence = 0.92", r.confidence == 0.92)
    t.check("processing_time_ms = 15.5", r.processing_time_ms == 15.5)
    t.check("frame_index = 42", r.frame_index == 42)
    t.check("events_detected = 1", r.events_detected == 1)
    t.check("metadata 설정됨", r.metadata == {"source": "test"})
    t.check("error_message = None", r.error_message is None)


def test_game_event_result_failure_factory(t: TestResult) -> None:
    """GameEventResult.failure_result() 팩토리 테스트."""
    r = GameEventResult.failure_result(
        error_message="감지 실패",
        error_code="EVENT_ERROR",
        metadata={"retry": True},
    )
    t.check("success = False", r.success is False)
    t.check("data = None", r.data is None)
    t.check("error_message 설정됨", r.error_message == "감지 실패")
    t.check("error_code 설정됨", r.error_code == "EVENT_ERROR")
    t.check("confidence = 0.0 (기본값)", r.confidence == 0.0)
    t.check("metadata 설정됨", r.metadata == {"retry": True})


def test_game_event_result_defaults(t: TestResult) -> None:
    """GameEventResult 기본값 테스트."""
    r = GameEventResult(success=True)
    t.check("data 기본값 = None", r.data is None)
    t.check("error_message 기본값 = None", r.error_message is None)
    t.check("error_code 기본값 = None", r.error_code is None)
    t.check("confidence 기본값 = 0.0", r.confidence == 0.0)
    t.check("processing_time_ms 기본값 = 0.0", r.processing_time_ms == 0.0)
    t.check("frame_index 기본값 = None", r.frame_index is None)
    t.check("timestamp 타입 = datetime", isinstance(r.timestamp, datetime))
    t.check("timestamp UTC timezone", r.timestamp.tzinfo == timezone.utc)
    t.check("events_detected 기본값 = 0", r.events_detected == 0)
    t.check("metadata 기본값 = 빈 dict", r.metadata == {})


def test_game_event_result_metadata_isolation(t: TestResult) -> None:
    """GameEventResult metadata 인스턴스 간 격리 테스트."""
    r1 = GameEventResult(success=True)
    r2 = GameEventResult(success=True)
    r1.metadata["key"] = "value"
    t.check("metadata 인스턴스 격리",
            "key" not in r2.metadata,
            "r2.metadata에 r1의 값이 침투함")

    # success_result metadata=None → 빈 dict
    r3 = GameEventResult.success_result(data="test")
    t.check("metadata=None → 빈 dict",
            r3.metadata == {} and r3.metadata is not None)


def test_game_event_result_fields(t: TestResult) -> None:
    """GameEventResult 필드 수 검증."""
    field_names = [f.name for f in fields(GameEventResult)]
    expected = [
        "success", "data", "error_message", "error_code",
        "confidence", "processing_time_ms", "frame_index",
        "timestamp", "events_detected", "metadata",
    ]
    t.check(f"필드 수 = {len(expected)}", len(field_names) == len(expected),
            f"실제: {len(field_names)}")
    for name in expected:
        t.check(f"필드 '{name}' 존재", name in field_names)


# =============================================================================
# 3. ValidationResult 테스트
# =============================================================================
def test_validation_result_confirmed_factory(t: TestResult) -> None:
    """ValidationResult.confirmed() 팩토리 테스트."""
    r = ValidationResult.confirmed(
        confidence=0.92,
        rule_reference="FIBA Art.25",
        explanation="트래블링 확인",
        processing_time_ms=5.0,
        evidence_quality=0.88,
        metadata={"view": "cam1"},
    )
    t.check("is_valid = True", r.is_valid is True)
    t.check("confidence = 0.92", r.confidence == 0.92)
    t.check("rule_reference 설정됨", r.rule_reference == "FIBA Art.25")
    t.check("explanation 설정됨", r.explanation == "트래블링 확인")
    t.check("processing_time_ms = 5.0", r.processing_time_ms == 5.0)
    t.check("evidence_quality = 0.88", r.evidence_quality == 0.88)
    t.check("metadata 설정됨", r.metadata == {"view": "cam1"})


def test_validation_result_rejected_factory(t: TestResult) -> None:
    """ValidationResult.rejected() 팩토리 테스트."""
    r = ValidationResult.rejected(
        confidence=0.75,
        explanation="증거 불충분",
        processing_time_ms=3.0,
        evidence_quality=0.45,
        metadata={"reason": "occlusion"},
    )
    t.check("is_valid = False", r.is_valid is False)
    t.check("confidence = 0.75", r.confidence == 0.75)
    t.check("explanation 설정됨", r.explanation == "증거 불충분")
    t.check("processing_time_ms = 3.0", r.processing_time_ms == 3.0)
    t.check("evidence_quality = 0.45", r.evidence_quality == 0.45)
    t.check("requires_review 기본값 = False", r.requires_review is False)
    t.check("metadata 설정됨", r.metadata == {"reason": "occlusion"})


def test_validation_result_defaults(t: TestResult) -> None:
    """ValidationResult 기본값 테스트."""
    r = ValidationResult(is_valid=True)
    t.check("confidence 기본값 = 0.0", r.confidence == 0.0)
    t.check("rule_reference 기본값 = ''", r.rule_reference == "")
    t.check("explanation 기본값 = ''", r.explanation == "")
    t.check("processing_time_ms 기본값 = 0.0", r.processing_time_ms == 0.0)
    t.check("evidence_quality 기본값 = 0.0", r.evidence_quality == 0.0)
    t.check("requires_review 기본값 = False", r.requires_review is False)
    t.check("alternative_calls 기본값 = []", r.alternative_calls == [])
    t.check("timestamp 타입 = datetime", isinstance(r.timestamp, datetime))
    t.check("timestamp UTC timezone", r.timestamp.tzinfo == timezone.utc)
    t.check("metadata 기본값 = 빈 dict", r.metadata == {})


def test_validation_result_isolation(t: TestResult) -> None:
    """ValidationResult metadata/alternative_calls 격리 테스트."""
    r1 = ValidationResult(is_valid=True)
    r2 = ValidationResult(is_valid=False)
    r1.metadata["x"] = 1
    r1.alternative_calls.append("travel")
    t.check("metadata 인스턴스 격리", "x" not in r2.metadata)
    t.check("alternative_calls 인스턴스 격리",
            len(r2.alternative_calls) == 0)


def test_validation_result_fields(t: TestResult) -> None:
    """ValidationResult 필드 수 검증."""
    field_names = [f.name for f in fields(ValidationResult)]
    expected = [
        "is_valid", "confidence", "rule_reference", "explanation",
        "processing_time_ms", "evidence_quality", "requires_review",
        "alternative_calls", "timestamp", "metadata",
    ]
    t.check(f"필드 수 = {len(expected)}", len(field_names) == len(expected),
            f"실제: {len(field_names)}")
    for name in expected:
        t.check(f"필드 '{name}' 존재", name in field_names)


# =============================================================================
# 4. FusionResult 테스트
# =============================================================================
def test_fusion_result_success_factory(t: TestResult) -> None:
    """FusionResult.success_result() 팩토리 테스트."""
    r = FusionResult.success_result(
        data=[{"fused": True}],
        confidence=0.88,
        processing_time_ms=25.0,
        num_views_used=3,
        num_views_rejected=1,
        fusion_quality=0.92,
        metadata={"method": "triangulation"},
    )
    t.check("success = True", r.success is True)
    t.check("data 설정됨", r.data == [{"fused": True}])
    t.check("confidence = 0.88", r.confidence == 0.88)
    t.check("processing_time_ms = 25.0", r.processing_time_ms == 25.0)
    t.check("num_views_used = 3", r.num_views_used == 3)
    t.check("num_views_rejected = 1", r.num_views_rejected == 1)
    t.check("fusion_quality = 0.92", r.fusion_quality == 0.92)
    t.check("metadata 설정됨", r.metadata == {"method": "triangulation"})


def test_fusion_result_failure_factory(t: TestResult) -> None:
    """FusionResult.failure_result() 팩토리 테스트."""
    r = FusionResult.failure_result(
        error_message="뷰 부족",
        metadata={"views": 1},
    )
    t.check("success = False", r.success is False)
    t.check("data = None", r.data is None)
    t.check("error_message 설정됨", r.error_message == "뷰 부족")
    t.check("confidence = 0.0 (기본값)", r.confidence == 0.0)
    t.check("metadata 설정됨", r.metadata == {"views": 1})


def test_fusion_result_defaults(t: TestResult) -> None:
    """FusionResult 기본값 테스트."""
    r = FusionResult(success=True)
    t.check("data 기본값 = None", r.data is None)
    t.check("error_message 기본값 = None", r.error_message is None)
    t.check("confidence 기본값 = 0.0", r.confidence == 0.0)
    t.check("processing_time_ms 기본값 = 0.0", r.processing_time_ms == 0.0)
    t.check("num_views_used 기본값 = 0", r.num_views_used == 0)
    t.check("num_views_rejected 기본값 = 0", r.num_views_rejected == 0)
    t.check("fusion_quality 기본값 = 0.0", r.fusion_quality == 0.0)
    t.check("timestamp 타입 = datetime", isinstance(r.timestamp, datetime))
    t.check("timestamp UTC timezone", r.timestamp.tzinfo == timezone.utc)
    t.check("metadata 기본값 = 빈 dict", r.metadata == {})


def test_fusion_result_metadata_isolation(t: TestResult) -> None:
    """FusionResult metadata 인스턴스 간 격리 테스트."""
    r1 = FusionResult(success=True)
    r2 = FusionResult(success=True)
    r1.metadata["key"] = "value"
    t.check("metadata 인스턴스 격리",
            "key" not in r2.metadata)

    # success_result metadata=None → 빈 dict
    r3 = FusionResult.success_result(data="test")
    t.check("metadata=None → 빈 dict",
            r3.metadata == {} and r3.metadata is not None)


def test_fusion_result_fields(t: TestResult) -> None:
    """FusionResult 필드 수 검증."""
    field_names = [f.name for f in fields(FusionResult)]
    expected = [
        "success", "data", "error_message", "confidence",
        "processing_time_ms", "num_views_used", "num_views_rejected",
        "fusion_quality", "timestamp", "metadata",
    ]
    t.check(f"필드 수 = {len(expected)}", len(field_names) == len(expected),
            f"실제: {len(field_names)}")
    for name in expected:
        t.check(f"필드 '{name}' 존재", name in field_names)


# =============================================================================
# 5. GameModuleMetrics 테스트
# =============================================================================
def test_game_module_metrics_defaults(t: TestResult) -> None:
    """GameModuleMetrics 기본값 테스트."""
    m = GameModuleMetrics()
    t.check("total_processed = 0", m.total_processed == 0)
    t.check("successful_count = 0", m.successful_count == 0)
    t.check("failed_count = 0", m.failed_count == 0)
    t.check("total_processing_time_ms = 0.0", m.total_processing_time_ms == 0.0)
    t.check("average_processing_time_ms = 0.0", m.average_processing_time_ms == 0.0)
    t.check("average_confidence = 0.0", m.average_confidence == 0.0)
    t.check("peak_memory_mb = 0.0", m.peak_memory_mb == 0.0)
    t.check("current_fps = 0.0", m.current_fps == 0.0)
    t.check("last_error = None", m.last_error is None)
    t.check("last_error_time = None", m.last_error_time is None)


def test_game_module_metrics_update_event_success(t: TestResult) -> None:
    """GameModuleMetrics.update_from_event_result() 성공 업데이트 테스트."""
    m = GameModuleMetrics()

    # 첫 번째 성공
    r1 = GameEventResult.success_result(data=["evt"], confidence=0.9)
    m.update_from_event_result(r1, processing_time_ms=10.0)

    t.check("1회 후 total_processed = 1", m.total_processed == 1)
    t.check("1회 후 successful_count = 1", m.successful_count == 1)
    t.check("1회 후 failed_count = 0", m.failed_count == 0)
    t.check("1회 후 average_confidence = 0.9",
            abs(m.average_confidence - 0.9) < 1e-9)
    t.check("1회 후 average_processing_time_ms = 10.0",
            abs(m.average_processing_time_ms - 10.0) < 1e-9)
    t.check("1회 후 current_fps = 100.0",
            abs(m.current_fps - 100.0) < 1e-6)

    # 두 번째 성공
    r2 = GameEventResult.success_result(data=["evt2"], confidence=0.8)
    m.update_from_event_result(r2, processing_time_ms=20.0)

    t.check("2회 후 total_processed = 2", m.total_processed == 2)
    # 이동 평균: (0.9 * 1 + 0.8) / 2 = 0.85
    t.check("2회 후 average_confidence = 0.85",
            abs(m.average_confidence - 0.85) < 1e-9)
    # 평균 처리 시간: (10 + 20) / 2 = 15.0
    t.check("2회 후 average_processing_time_ms = 15.0",
            abs(m.average_processing_time_ms - 15.0) < 1e-9)
    # FPS: 1000 / 15 = 66.666...
    t.check("2회 후 current_fps ≈ 66.67",
            abs(m.current_fps - 1000.0 / 15.0) < 1e-3)


def test_game_module_metrics_update_event_failure(t: TestResult) -> None:
    """GameModuleMetrics.update_from_event_result() 실패 업데이트 테스트."""
    m = GameModuleMetrics()

    r_fail = GameEventResult.failure_result(error_message="감지 실패")
    m.update_from_event_result(r_fail, processing_time_ms=5.0)

    t.check("실패 후 total_processed = 1", m.total_processed == 1)
    t.check("실패 후 successful_count = 0", m.successful_count == 0)
    t.check("실패 후 failed_count = 1", m.failed_count == 1)
    t.check("실패 후 last_error = '감지 실패'",
            m.last_error == "감지 실패")
    t.check("실패 후 last_error_time 설정됨",
            isinstance(m.last_error_time, datetime))
    t.check("실패 후 last_error_time UTC",
            m.last_error_time.tzinfo == timezone.utc)
    # 실패 시 average_confidence 변하지 않음
    t.check("실패만 → average_confidence = 0.0",
            m.average_confidence == 0.0)


def test_game_module_metrics_update_validation(t: TestResult) -> None:
    """GameModuleMetrics.update_from_validation_result() 테스트."""
    m = GameModuleMetrics()

    # 검증 처리 자체는 항상 성공으로 기록
    vr = ValidationResult.confirmed(
        confidence=0.92, rule_reference="FIBA Art.25",
        explanation="트래블링", processing_time_ms=4.0,
    )
    m.update_from_validation_result(vr, processing_time_ms=4.0)

    t.check("validation 후 total_processed = 1", m.total_processed == 1)
    t.check("validation 후 successful_count = 1", m.successful_count == 1)
    t.check("validation 후 average_confidence = 0.92",
            abs(m.average_confidence - 0.92) < 1e-9)
    t.check("validation 후 last_error = None", m.last_error is None)


def test_game_module_metrics_update_fusion(t: TestResult) -> None:
    """GameModuleMetrics.update_from_fusion_result() 테스트."""
    m = GameModuleMetrics()

    # 성공 융합
    fr_ok = FusionResult.success_result(data=[], confidence=0.85, num_views_used=3)
    m.update_from_fusion_result(fr_ok, processing_time_ms=20.0)

    t.check("fusion 성공 후 total_processed = 1", m.total_processed == 1)
    t.check("fusion 성공 후 successful_count = 1", m.successful_count == 1)

    # 실패 융합
    fr_fail = FusionResult.failure_result(error_message="뷰 부족")
    m.update_from_fusion_result(fr_fail, processing_time_ms=2.0)

    t.check("fusion 실패 후 total_processed = 2", m.total_processed == 2)
    t.check("fusion 실패 후 failed_count = 1", m.failed_count == 1)
    t.check("fusion 실패 후 last_error = '뷰 부족'",
            m.last_error == "뷰 부족")


def test_game_module_metrics_success_rate(t: TestResult) -> None:
    """GameModuleMetrics.success_rate 프로퍼티 테스트."""
    m = GameModuleMetrics()

    # 0/0 = 0.0
    t.check("처리 없음 → success_rate = 0.0",
            m.success_rate == 0.0)

    # 3 성공, 1 실패
    for _ in range(3):
        m.update_from_event_result(
            GameEventResult.success_result(data=[], confidence=0.9), 10.0)
    m.update_from_event_result(
        GameEventResult.failure_result(error_message="err"), 10.0)

    t.check("3/4 → success_rate = 0.75",
            abs(m.success_rate - 0.75) < 1e-9)


def test_game_module_metrics_fps_zero_time(t: TestResult) -> None:
    """GameModuleMetrics FPS 계산 - 0ms 처리 시간 안전성."""
    m = GameModuleMetrics()
    r = GameEventResult.success_result(data=[], confidence=1.0)
    m.update_from_event_result(r, processing_time_ms=0.0)
    t.check("0ms 처리 시 current_fps = 0.0 (나눗셈 안전)",
            m.current_fps == 0.0)


# =============================================================================
# 6. IGameEventDetector 테스트
# =============================================================================
def test_igame_event_detector_abc(t: TestResult) -> None:
    """IGameEventDetector ABC 검증."""
    t.check("IGameEventDetector는 ABC", issubclass(IGameEventDetector, ABC))

    detector = StubEventDetector()
    t.check("StubEventDetector 생성 가능",
            isinstance(detector, IGameEventDetector))
    t.check("name = 'StubEventDetector'",
            detector.name == "StubEventDetector")
    t.check("version = '1.0.0'", detector.version == "1.0.0")
    t.check("초기 state = UNINITIALIZED",
            detector.state == GameModuleState.UNINITIALIZED)
    t.check("supported_events = 3개",
            len(detector.supported_events) == 3)


def test_igame_event_detector_lifecycle(t: TestResult) -> None:
    """IGameEventDetector 생명주기 테스트."""
    detector = StubEventDetector()

    # 초기화
    detector.initialize({})
    t.check("initialize 후 state = READY",
            detector.state == GameModuleState.READY)

    # 감지
    frame = make_frame(100, 100)
    result = detector.detect_events(frame, [], [], [], frame_index=5)
    t.check("detect_events 결과 success = True", result.success is True)
    t.check("detect_events 후 state = READY",
            detector.state == GameModuleState.READY)

    # 리셋
    detector.reset()
    t.check("reset 후 state = UNINITIALIZED",
            detector.state == GameModuleState.UNINITIALIZED)

    # 종료
    detector.initialize({})
    detector.shutdown()
    t.check("shutdown 후 state = SHUTDOWN",
            detector.state == GameModuleState.SHUTDOWN)


def test_igame_event_detector_detect_events(t: TestResult) -> None:
    """IGameEventDetector.detect_events() 테스트."""
    detector = StubEventDetector()
    detector.initialize({})
    frame = make_frame(100, 100)

    result = detector.detect_events(
        frame, detections=[], tracks=[], poses=[],
        frame_index=10, timestamp_ms=333.3,
    )
    t.check("결과 data는 리스트", isinstance(result.data, list))
    t.check("events_detected = 1", result.events_detected == 1)
    t.check("confidence = 0.9", result.confidence == 0.9)
    t.check("frame_index = 10", result.frame_index == 10)


def test_igame_event_detector_active_history(t: TestResult) -> None:
    """IGameEventDetector active_events/event_history 테스트."""
    detector = StubEventDetector()
    detector.initialize({})
    frame = make_frame(10, 10)

    # 3개 이벤트 생성
    for i in range(3):
        detector.detect_events(frame, [], [], [], frame_index=i)

    active = detector.get_active_events()
    t.check("active_events 3개", len(active) == 3)

    history = detector.get_event_history()
    t.check("event_history 3개", len(history) == 3)

    # 타입 필터
    shot_history = detector.get_event_history(event_type="shot")
    t.check("shot 필터 결과 3개", len(shot_history) == 3)

    foul_history = detector.get_event_history(event_type="foul")
    t.check("foul 필터 결과 0개", len(foul_history) == 0)


def test_igame_event_detector_validate_input(t: TestResult) -> None:
    """IGameEventDetector.validate_input() 테스트."""
    detector = StubEventDetector()

    # 유효한 BGR 프레임
    valid_frame = make_frame()
    t.check("유효한 BGR 프레임 → True",
            detector.validate_input(valid_frame) is True)

    # None
    t.check("None → False",
            detector.validate_input(None) is False)

    # ndarray 아닌 타입
    t.check("list → False",
            detector.validate_input([[1, 2, 3]]) is False)

    # 2D 배열 (grayscale)
    gray = np.zeros((480, 640), dtype=np.uint8)
    t.check("2D (grayscale) → False",
            detector.validate_input(gray) is False)

    # 4채널 (RGBA)
    rgba = np.zeros((480, 640, 4), dtype=np.uint8)
    t.check("4채널 (RGBA) → False",
            detector.validate_input(rgba) is False)

    # 1채널
    single = np.zeros((480, 640, 1), dtype=np.uint8)
    t.check("1채널 → False",
            detector.validate_input(single) is False)

    # 올바른 3채널 소형
    bgr = np.zeros((100, 100, 3), dtype=np.uint8)
    t.check("소형 3채널 → True",
            detector.validate_input(bgr) is True)


# =============================================================================
# 7. IRefereeValidator 테스트
# =============================================================================
def test_ireferee_validator_abc(t: TestResult) -> None:
    """IRefereeValidator ABC 검증."""
    t.check("IRefereeValidator는 ABC", issubclass(IRefereeValidator, ABC))

    validator = StubRefereeValidator()
    t.check("StubRefereeValidator 생성 가능",
            isinstance(validator, IRefereeValidator))
    t.check("name = 'StubRefereeValidator'",
            validator.name == "StubRefereeValidator")
    t.check("version = '1.0.0'", validator.version == "1.0.0")
    t.check("초기 state = UNINITIALIZED",
            validator.state == GameModuleState.UNINITIALIZED)
    t.check("confidence_threshold = 0.85",
            validator.confidence_threshold == 0.85)


def test_ireferee_validator_lifecycle(t: TestResult) -> None:
    """IRefereeValidator 생명주기 테스트."""
    validator = StubRefereeValidator()

    # 초기화 (기본 fiba)
    validator.initialize({})
    t.check("initialize 후 state = READY",
            validator.state == GameModuleState.READY)
    t.check("기본 rule_set = 'fiba'",
            validator.active_rule_set == "fiba")

    # NBA 규칙으로 초기화
    validator2 = StubRefereeValidator()
    validator2.initialize({}, rule_set="nba")
    t.check("rule_set = 'nba'",
            validator2.active_rule_set == "nba")

    # 종료
    validator.shutdown()
    t.check("shutdown 후 state = SHUTDOWN",
            validator.state == GameModuleState.SHUTDOWN)


def test_ireferee_validator_validate(t: TestResult) -> None:
    """IRefereeValidator.validate_violation/foul 테스트."""
    validator = StubRefereeValidator()
    validator.initialize({})

    # 바이올레이션 검증
    vr = validator.validate_violation(
        violation_data={"type": "traveling"},
        evidence={"frames": [1, 2, 3]},
    )
    t.check("validate_violation is_valid = True", vr.is_valid is True)
    t.check("validate_violation confidence = 0.92", vr.confidence == 0.92)
    t.check("validate_violation rule_reference",
            vr.rule_reference == "FIBA Art.25")

    # 파울 검증
    fr = validator.validate_foul(
        foul_data={"type": "personal"},
        evidence={"contact": True},
    )
    t.check("validate_foul is_valid = True", fr.is_valid is True)
    t.check("validate_foul confidence = 0.88", fr.confidence == 0.88)
    t.check("validate_foul rule_reference",
            fr.rule_reference == "FIBA Art.33")


def test_ireferee_validator_consistency_explanation(t: TestResult) -> None:
    """IRefereeValidator.check_consistency/get_decision_explanation 테스트."""
    validator = StubRefereeValidator()
    validator.initialize({})

    score = validator.check_consistency(decision={}, history=[])
    t.check("check_consistency 반환 = float",
            isinstance(score, float))
    t.check("check_consistency 값 = 0.95",
            abs(score - 0.95) < 1e-9)

    explanation_ko = validator.get_decision_explanation(decision={}, lang="ko")
    t.check("get_decision_explanation (ko) 반환",
            isinstance(explanation_ko, str) and len(explanation_ko) > 0)

    explanation_en = validator.get_decision_explanation(decision={}, lang="en")
    t.check("get_decision_explanation (en) 반환",
            isinstance(explanation_en, str) and len(explanation_en) > 0)


# =============================================================================
# 8. IMultiViewFusion 테스트
# =============================================================================
def test_imulti_view_fusion_abc(t: TestResult) -> None:
    """IMultiViewFusion ABC 검증."""
    t.check("IMultiViewFusion는 ABC", issubclass(IMultiViewFusion, ABC))

    fusion = StubMultiViewFusion()
    t.check("StubMultiViewFusion 생성 가능",
            isinstance(fusion, IMultiViewFusion))
    t.check("name = 'StubMultiViewFusion'",
            fusion.name == "StubMultiViewFusion")
    t.check("version = '1.0.0'", fusion.version == "1.0.0")
    t.check("초기 state = UNINITIALIZED",
            fusion.state == GameModuleState.UNINITIALIZED)
    t.check("초기 num_views = 0", fusion.num_views == 0)


def test_imulti_view_fusion_lifecycle(t: TestResult) -> None:
    """IMultiViewFusion 생명주기 테스트."""
    fusion = StubMultiViewFusion()

    # 캘리브레이션 없이 초기화
    fusion.initialize({})
    t.check("initialize (no calib) 후 state = READY",
            fusion.state == GameModuleState.READY)
    t.check("캘리브레이션 없음 → num_views = 0",
            fusion.num_views == 0)

    # 캘리브레이션 포함 초기화
    fusion2 = StubMultiViewFusion()
    fusion2.initialize({}, calibrations=["cam1", "cam2", "cam3"])
    t.check("3 카메라 → num_views = 3", fusion2.num_views == 3)
    t.check("캘리브레이션 품질 = 0.95",
            abs(fusion2.calibration_quality - 0.95) < 1e-9)

    # 리셋
    fusion2.reset()
    t.check("reset 후 num_views = 0", fusion2.num_views == 0)

    # 종료
    fusion.shutdown()
    t.check("shutdown 후 state = SHUTDOWN",
            fusion.state == GameModuleState.SHUTDOWN)


def test_imulti_view_fusion_fuse_methods(t: TestResult) -> None:
    """IMultiViewFusion fuse_detections/poses/trajectories 테스트."""
    fusion = StubMultiViewFusion()
    fusion.initialize({}, calibrations=["cam1", "cam2"])

    # 감지 융합
    det_result = fusion.fuse_detections({
        "cam1": [{"id": 1}],
        "cam2": [{"id": 2}],
    })
    t.check("fuse_detections success = True", det_result.success is True)
    t.check("fuse_detections num_views_used = 2",
            det_result.num_views_used == 2)

    # 포즈 융합
    pose_result = fusion.fuse_poses({
        "cam1": [{"skeleton": [1, 2, 3]}],
        "cam2": [{"skeleton": [4, 5, 6]}],
    })
    t.check("fuse_poses success = True", pose_result.success is True)
    t.check("fuse_poses data 길이 = 2",
            len(pose_result.data) == 2)

    # 궤적 융합
    traj_result = fusion.fuse_trajectories({
        "cam1": [{"trajectory": [0, 1]}],
        "cam2": [{"trajectory": [2, 3]}],
        "cam3": [{"trajectory": [4, 5]}],
    })
    t.check("fuse_trajectories success = True", traj_result.success is True)
    t.check("fuse_trajectories num_views_used = 3",
            traj_result.num_views_used == 3)


def test_imulti_view_fusion_triangulate(t: TestResult) -> None:
    """IMultiViewFusion.triangulate_point() 테스트."""
    fusion = StubMultiViewFusion()
    fusion.initialize({}, calibrations=["cam1", "cam2"])

    # 정상 삼각측량
    point_3d = fusion.triangulate_point({
        "cam1": (100.0, 200.0),
        "cam2": (150.0, 180.0),
    })
    t.check("triangulate_point 반환 = tuple[3]",
            isinstance(point_3d, tuple) and len(point_3d) == 3)

    # 뷰 1개 → ValueError
    raised = False
    try:
        fusion.triangulate_point({"cam1": (100.0, 200.0)})
    except ValueError:
        raised = True
    t.check("1개 뷰 → ValueError 발생", raised is True)

    # 2개 이상 뷰에서 3D 좌표
    t.check("3D 좌표 (1.0, 2.0, 3.0)",
            point_3d == (1.0, 2.0, 3.0))


# =============================================================================
# 9. 모듈 메타데이터 검증
# =============================================================================
def test_module_metadata(t: TestResult) -> None:
    """모듈 메타데이터 검증."""
    import shared.interfaces.game_interface as mod

    t.check("__version__ = '1.0.0'",
            mod.__version__ == "1.0.0")
    t.check("__all__ 길이 = 8",
            len(mod.__all__) == 8, f"실제: {len(mod.__all__)}")

    expected = {
        "GameModuleState", "GameEventResult", "ValidationResult",
        "FusionResult", "GameModuleMetrics",
        "IGameEventDetector", "IRefereeValidator", "IMultiViewFusion",
    }
    t.check("__all__ 내용 일치",
            set(mod.__all__) == expected,
            f"차이: {set(mod.__all__) ^ expected}")


def test_all_exports_importable(t: TestResult) -> None:
    """__all__ 모든 항목 import 가능 검증."""
    import shared.interfaces.game_interface as mod

    for name in mod.__all__:
        obj = getattr(mod, name, None)
        t.check(f"export '{name}' 존재",
                obj is not None)
        t.check(f"export '{name}' 은 type 또는 class",
                isinstance(obj, type))


# =============================================================================
# 10. __init__.py 통합 import 검증
# =============================================================================
def test_init_exports(t: TestResult) -> None:
    """shared/interfaces/__init__.py에서 game_interface 항목 import 검증."""
    from shared.interfaces import (
        GameModuleState as _GMS,
        GameEventResult as _GER,
        ValidationResult as _VR,
        FusionResult as _FR,
        GameModuleMetrics as _GMM,
        IGameEventDetector as _IGED,
        IRefereeValidator as _IRV,
        IMultiViewFusion as _IMVF,
    )
    t.check("__init__ → GameModuleState import",
            _GMS is GameModuleState)
    t.check("__init__ → GameEventResult import",
            _GER is GameEventResult)
    t.check("__init__ → ValidationResult import",
            _VR is ValidationResult)
    t.check("__init__ → FusionResult import",
            _FR is FusionResult)
    t.check("__init__ → GameModuleMetrics import",
            _GMM is GameModuleMetrics)
    t.check("__init__ → IGameEventDetector import",
            _IGED is IGameEventDetector)
    t.check("__init__ → IRefereeValidator import",
            _IRV is IRefereeValidator)
    t.check("__init__ → IMultiViewFusion import",
            _IMVF is IMultiViewFusion)


# =============================================================================
# 11. 엣지 케이스
# =============================================================================
def test_edge_cases(t: TestResult) -> None:
    """엣지 케이스 테스트."""
    # GameModuleState 문자열 비교
    t.check("GameModuleState == 문자열 값",
            GameModuleState.READY == "ready")
    t.check("GameModuleState != 다른 문자열",
            GameModuleState.READY != "processing")

    # GameEventResult 타입 Generic (런타임에는 영향 없음)
    r_int = GameEventResult.success_result(data=42)
    t.check("Generic[int] → data = 42", r_int.data == 42)

    r_list = GameEventResult.success_result(data=[1, 2, 3])
    t.check("Generic[list] → data = [1,2,3]", r_list.data == [1, 2, 3])

    # FusionResult 타입 Generic
    fr_str = FusionResult.success_result(data="fused")
    t.check("FusionResult[str] → data = 'fused'", fr_str.data == "fused")

    # ValidationResult requires_review 직접 설정
    vr = ValidationResult(is_valid=True, requires_review=True)
    t.check("requires_review = True 직접 설정", vr.requires_review is True)

    # ValidationResult alternative_calls 직접 설정
    vr2 = ValidationResult(
        is_valid=False,
        alternative_calls=["block", "charge"],
    )
    t.check("alternative_calls 설정",
            vr2.alternative_calls == ["block", "charge"])

    # GameModuleMetrics 100회 업데이트 후 정확도
    m = GameModuleMetrics()
    for _ in range(100):
        m.update_from_event_result(
            GameEventResult.success_result(data=[], confidence=0.9), 10.0)
    t.check("100회 업데이트 후 average_confidence ≈ 0.9",
            abs(m.average_confidence - 0.9) < 1e-6)
    t.check("100회 업데이트 후 success_rate = 1.0",
            abs(m.success_rate - 1.0) < 1e-9)

    # IGameEventDetector validate_input: 4D 배열
    detector = StubEventDetector()
    arr_4d = np.zeros((1, 480, 640, 3), dtype=np.uint8)
    t.check("4D 배열 → False (ndim != 3)",
            detector.validate_input(arr_4d) is False)

    # INITIALIZING 상태 고유 프로퍼티 조합
    state = GameModuleState.INITIALIZING
    t.check("INITIALIZING: is_active=F, is_initializing=T, can_process=F",
            state.is_active is False
            and state.is_initializing is True
            and state.can_process is False)


# =============================================================================
# 메인
# =============================================================================
def main() -> None:
    t = TestResult()
    print("\n" + "=" * 60)
    print("  game_interface.py v1.0.0 단위 테스트")
    print("=" * 60)

    # 1. GameModuleState
    t.set_section("[1] GameModuleState - 멤버 값 및 수량")
    test_game_module_state_members(t)

    t.set_section("[2] GameModuleState - __str__")
    test_game_module_state_str(t)

    t.set_section("[3] GameModuleState - str,Enum 상속")
    test_game_module_state_str_enum(t)

    t.set_section("[4] GameModuleState - get_name() 다국어")
    test_game_module_state_get_name(t)

    t.set_section("[5] GameModuleState - to_korean")
    test_game_module_state_to_korean(t)

    t.set_section("[6] GameModuleState - is_active")
    test_game_module_state_is_active(t)

    t.set_section("[7] GameModuleState - is_initializing")
    test_game_module_state_is_initializing(t)

    t.set_section("[8] GameModuleState - is_error")
    test_game_module_state_is_error(t)

    t.set_section("[9] GameModuleState - is_terminated")
    test_game_module_state_is_terminated(t)

    t.set_section("[10] GameModuleState - can_process")
    test_game_module_state_can_process(t)

    # 2. GameEventResult
    t.set_section("[11] GameEventResult - success_result()")
    test_game_event_result_success_factory(t)

    t.set_section("[12] GameEventResult - failure_result()")
    test_game_event_result_failure_factory(t)

    t.set_section("[13] GameEventResult - 기본값")
    test_game_event_result_defaults(t)

    t.set_section("[14] GameEventResult - metadata 격리")
    test_game_event_result_metadata_isolation(t)

    t.set_section("[15] GameEventResult - 필드 수")
    test_game_event_result_fields(t)

    # 3. ValidationResult
    t.set_section("[16] ValidationResult - confirmed()")
    test_validation_result_confirmed_factory(t)

    t.set_section("[17] ValidationResult - rejected()")
    test_validation_result_rejected_factory(t)

    t.set_section("[18] ValidationResult - 기본값")
    test_validation_result_defaults(t)

    t.set_section("[19] ValidationResult - metadata/alt 격리")
    test_validation_result_isolation(t)

    t.set_section("[20] ValidationResult - 필드 수")
    test_validation_result_fields(t)

    # 4. FusionResult
    t.set_section("[21] FusionResult - success_result()")
    test_fusion_result_success_factory(t)

    t.set_section("[22] FusionResult - failure_result()")
    test_fusion_result_failure_factory(t)

    t.set_section("[23] FusionResult - 기본값")
    test_fusion_result_defaults(t)

    t.set_section("[24] FusionResult - metadata 격리")
    test_fusion_result_metadata_isolation(t)

    t.set_section("[25] FusionResult - 필드 수")
    test_fusion_result_fields(t)

    # 5. GameModuleMetrics
    t.set_section("[26] GameModuleMetrics - 기본값")
    test_game_module_metrics_defaults(t)

    t.set_section("[27] GameModuleMetrics - update_from_event_result (성공)")
    test_game_module_metrics_update_event_success(t)

    t.set_section("[28] GameModuleMetrics - update_from_event_result (실패)")
    test_game_module_metrics_update_event_failure(t)

    t.set_section("[29] GameModuleMetrics - update_from_validation_result")
    test_game_module_metrics_update_validation(t)

    t.set_section("[30] GameModuleMetrics - update_from_fusion_result")
    test_game_module_metrics_update_fusion(t)

    t.set_section("[31] GameModuleMetrics - success_rate")
    test_game_module_metrics_success_rate(t)

    t.set_section("[32] GameModuleMetrics - FPS 0ms 안전성")
    test_game_module_metrics_fps_zero_time(t)

    # 6. IGameEventDetector
    t.set_section("[33] IGameEventDetector - ABC 검증")
    test_igame_event_detector_abc(t)

    t.set_section("[34] IGameEventDetector - 생명주기")
    test_igame_event_detector_lifecycle(t)

    t.set_section("[35] IGameEventDetector - detect_events()")
    test_igame_event_detector_detect_events(t)

    t.set_section("[36] IGameEventDetector - active/history")
    test_igame_event_detector_active_history(t)

    t.set_section("[37] IGameEventDetector - validate_input()")
    test_igame_event_detector_validate_input(t)

    # 7. IRefereeValidator
    t.set_section("[38] IRefereeValidator - ABC 검증")
    test_ireferee_validator_abc(t)

    t.set_section("[39] IRefereeValidator - 생명주기")
    test_ireferee_validator_lifecycle(t)

    t.set_section("[40] IRefereeValidator - validate_violation/foul")
    test_ireferee_validator_validate(t)

    t.set_section("[41] IRefereeValidator - consistency/explanation")
    test_ireferee_validator_consistency_explanation(t)

    # 8. IMultiViewFusion
    t.set_section("[42] IMultiViewFusion - ABC 검증")
    test_imulti_view_fusion_abc(t)

    t.set_section("[43] IMultiViewFusion - 생명주기")
    test_imulti_view_fusion_lifecycle(t)

    t.set_section("[44] IMultiViewFusion - fuse_*() 메서드")
    test_imulti_view_fusion_fuse_methods(t)

    t.set_section("[45] IMultiViewFusion - triangulate_point()")
    test_imulti_view_fusion_triangulate(t)

    # 9. 모듈 메타데이터
    t.set_section("[46] 모듈 메타데이터 검증")
    test_module_metadata(t)

    t.set_section("[47] __all__ export import 검증")
    test_all_exports_importable(t)

    # 10. __init__.py 통합
    t.set_section("[48] __init__.py 통합 import 검증")
    test_init_exports(t)

    # 11. 엣지 케이스
    t.set_section("[49] 엣지 케이스")
    test_edge_cases(t)

    sys.exit(0 if t.summary() else 1)


if __name__ == "__main__":
    main()
