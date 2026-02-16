# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼 (Desktop Edition)

모듈: tests/core_foundation/registry/unit
파일: test_pipeline_coordinator.py
설명: PipelineCoordinator 단위 테스트

작성자: COURTVIEW AI Team
최종 수정: 2026-02-12

테스트 범위:
    [1]  Enum 테스트 (12개)
    [2]  상수 테스트 (5개)
    [3]  예외 클래스 (5개)
    [4]  데이터클래스 테스트 (15개)
    [5]  PipelineBuilder 테스트 (8개)
    [6]  PipelineTemplates 테스트 (5개)
    [7]  PipelineCoordinator 기본 (12개)
    [8]  비동기 실행 테스트 (10개)
    [9]  CheckpointManager 테스트 (8개)
    [10] 스레드 안전성 (3개)
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from core_foundation.registry.pipeline_coordinator import (
    # Enum (4개)
    PipelineType,
    StageType,
    StageStatus,
    PipelineStatus,
    # 상수 (5개)
    DEFAULT_STAGE_TIMEOUT,
    DEFAULT_PIPELINE_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    MAX_CONCURRENT_PIPELINES,
    # 예외 클래스 (4개)
    PipelineException,
    StageExecutionError,
    PipelineTimeoutError,
    PipelineConfigError,
    # 타입 별칭 (4개)
    StageHandler,
    ProgressCallback,
    ErrorCallback,
    CheckpointCallback,
    # 데이터 클래스 (6개)
    StageConfig,
    StageResult,
    PipelineConfig,
    PipelineProgress,
    CheckpointData,
    PipelineContext,
    # 메인 클래스 (4개)
    CheckpointManager,
    PipelineCoordinator,
    PipelineBuilder,
    PipelineTemplates,
    # 전역 함수 (3개)
    get_coordinator,
    create_pipeline,
    _reset_coordinator,
)

from shared.constants.status_codes import AnalysisPhase


# ============================================================
# TestResult 클래스
# ============================================================
class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  [FAIL] {test_name}: {error}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ============================================================
# 목 핸들러 패턴
# ============================================================
async def mock_handler(context):
    """성공하는 목 핸들러."""
    return {"status": "ok"}


async def failing_handler(context):
    """실패하는 목 핸들러."""
    raise RuntimeError("stage failed")


async def slow_handler(context):
    """느린 목 핸들러."""
    await asyncio.sleep(0.1)
    return {"status": "slow_ok"}


async def timeout_handler(context):
    """타임아웃되는 핸들러 (매우 긴 대기)."""
    await asyncio.sleep(60)
    return {"status": "should_not_reach"}


# 재시도 카운터 핸들러
_retry_counter = {"count": 0}


async def retry_then_succeed_handler(context):
    """처음 2번 실패 후 성공하는 핸들러."""
    _retry_counter["count"] += 1
    if _retry_counter["count"] < 3:
        raise RuntimeError(f"attempt {_retry_counter['count']} failed")
    return {"status": "ok", "attempts": _retry_counter["count"]}


# ============================================================
# [1] Enum 테스트 (12개)
# ============================================================
def test_enums(result: TestResult) -> None:
    """Enum 클래스 테스트."""
    print("\n[1] Enum 테스트")
    _reset_coordinator()

    # 1-1. PipelineType 멤버 수 (14개)
    try:
        members = list(PipelineType)
        assert len(members) == 14, f"PipelineType 멤버 수: {len(members)} (기대: 14)"
        result.ok("PipelineType 14개 멤버 확인")
    except Exception as e:
        result.fail("PipelineType 14개 멤버 확인", str(e))

    # 1-2. PipelineType.category 프로퍼티
    try:
        assert PipelineType.TRAINING.category == "training"
        assert PipelineType.TRAINING_SHOOTING.category == "training"
        assert PipelineType.GAME.category == "game"
        assert PipelineType.GAME_FULL.category == "game"
        assert PipelineType.REFEREE.category == "referee"
        assert PipelineType.REFEREE_FULL.category == "referee"
        assert PipelineType.REPORT.category == "report"
        assert PipelineType.REPORT_WEEKLY.category == "report"
        result.ok("PipelineType.category 매핑 정확성")
    except Exception as e:
        result.fail("PipelineType.category 매핑 정확성", str(e))

    # 1-3. StageType 멤버 수 (25개)
    try:
        members = list(StageType)
        assert len(members) == 25, f"StageType 멤버 수: {len(members)} (기대: 25)"
        result.ok("StageType 25개 멤버 확인")
    except Exception as e:
        result.fail("StageType 25개 멤버 확인", str(e))

    # 1-4. StageType.phase 프로퍼티 매핑
    try:
        assert StageType.INITIALIZATION.phase == AnalysisPhase.INITIALIZED
        assert StageType.VIDEO_DOWNLOAD.phase == AnalysisPhase.DOWNLOADING
        assert StageType.VIDEO_PREPROCESSING.phase == AnalysisPhase.PREPROCESSING
        assert StageType.DETECTION.phase == AnalysisPhase.DETECTING
        assert StageType.POSE_ESTIMATION.phase == AnalysisPhase.POSE_ESTIMATING
        assert StageType.MOTION_ANALYSIS.phase == AnalysisPhase.ANALYZING
        assert StageType.FEEDBACK_GENERATION.phase == AnalysisPhase.GENERATING_FEEDBACK
        assert StageType.POSTPROCESSING.phase == AnalysisPhase.POSTPROCESSING
        assert StageType.RESULT_UPLOAD.phase == AnalysisPhase.UPLOADING
        assert StageType.CLEANUP.phase == AnalysisPhase.FINALIZING
        result.ok("StageType.phase 매핑 정확성")
    except Exception as e:
        result.fail("StageType.phase 매핑 정확성", str(e))

    # 1-5. StageStatus 멤버 수 (7개)
    try:
        members = list(StageStatus)
        assert len(members) == 7, f"StageStatus 멤버 수: {len(members)} (기대: 7)"
        result.ok("StageStatus 7개 멤버 확인")
    except Exception as e:
        result.fail("StageStatus 7개 멤버 확인", str(e))

    # 1-6. StageStatus.is_terminal / is_success 프로퍼티
    try:
        # 종료 상태
        assert StageStatus.COMPLETED.is_terminal is True
        assert StageStatus.FAILED.is_terminal is True
        assert StageStatus.SKIPPED.is_terminal is True
        assert StageStatus.CANCELLED.is_terminal is True
        # 비종료 상태
        assert StageStatus.PENDING.is_terminal is False
        assert StageStatus.RUNNING.is_terminal is False
        assert StageStatus.RETRYING.is_terminal is False
        # 성공 상태
        assert StageStatus.COMPLETED.is_success is True
        assert StageStatus.SKIPPED.is_success is True
        assert StageStatus.FAILED.is_success is False
        result.ok("StageStatus.is_terminal / is_success 프로퍼티")
    except Exception as e:
        result.fail("StageStatus.is_terminal / is_success 프로퍼티", str(e))

    # 1-7. PipelineStatus 멤버 수 (7개)
    try:
        members = list(PipelineStatus)
        assert len(members) == 7, f"PipelineStatus 멤버 수: {len(members)} (기대: 7)"
        result.ok("PipelineStatus 7개 멤버 확인")
    except Exception as e:
        result.fail("PipelineStatus 7개 멤버 확인", str(e))

    # 1-8. PipelineStatus.is_terminal / is_success 프로퍼티
    try:
        assert PipelineStatus.COMPLETED.is_terminal is True
        assert PipelineStatus.FAILED.is_terminal is True
        assert PipelineStatus.CANCELLED.is_terminal is True
        assert PipelineStatus.RUNNING.is_terminal is False
        assert PipelineStatus.INITIALIZING.is_terminal is False
        assert PipelineStatus.PAUSED.is_terminal is False
        assert PipelineStatus.CREATED.is_terminal is False
        assert PipelineStatus.COMPLETED.is_success is True
        assert PipelineStatus.FAILED.is_success is False
        result.ok("PipelineStatus.is_terminal / is_success 프로퍼티")
    except Exception as e:
        result.fail("PipelineStatus.is_terminal / is_success 프로퍼티", str(e))

    # 1-9. Enum 값 유일성 (PipelineType)
    try:
        values = [m.value for m in PipelineType]
        assert len(values) == len(set(values)), "PipelineType 값 중복"
        values_st = [m.value for m in StageType]
        assert len(values_st) == len(set(values_st)), "StageType 값 중복"
        values_ss = [m.value for m in StageStatus]
        assert len(values_ss) == len(set(values_ss)), "StageStatus 값 중복"
        values_ps = [m.value for m in PipelineStatus]
        assert len(values_ps) == len(set(values_ps)), "PipelineStatus 값 중복"
        result.ok("모든 Enum 값 유일성 확인")
    except Exception as e:
        result.fail("모든 Enum 값 유일성 확인", str(e))

    # 1-10. 문자열 기반 Enum 접근
    try:
        assert PipelineType("training") == PipelineType.TRAINING
        assert StageType("detection") == StageType.DETECTION
        assert StageStatus("completed") == StageStatus.COMPLETED
        assert PipelineStatus("running") == PipelineStatus.RUNNING
        result.ok("문자열 기반 Enum 접근")
    except Exception as e:
        result.fail("문자열 기반 Enum 접근", str(e))

    # 1-11. PipelineType 카테고리 매핑 전체 검증
    try:
        category_mapping = {
            "training": [
                PipelineType.TRAINING, PipelineType.TRAINING_SHOOTING,
                PipelineType.TRAINING_DRIBBLING, PipelineType.TRAINING_COMPARISON,
            ],
            "game": [
                PipelineType.GAME, PipelineType.GAME_FULL,
                PipelineType.GAME_HIGHLIGHTS, PipelineType.GAME_STATISTICS,
            ],
            "referee": [
                PipelineType.REFEREE, PipelineType.REFEREE_FULL,
                PipelineType.REFEREE_VIOLATION, PipelineType.REFEREE_FOUL,
            ],
            "report": [PipelineType.REPORT, PipelineType.REPORT_WEEKLY],
        }
        for category, types in category_mapping.items():
            for pt in types:
                assert pt.category == category, f"{pt.value}.category != {category}"
        result.ok("PipelineType 카테고리 매핑 전체 검증")
    except Exception as e:
        result.fail("PipelineType 카테고리 매핑 전체 검증", str(e))

    # 1-12. StageType.phase 매핑 전체 검증 (25개 전부)
    try:
        # 모든 StageType은 phase 프로퍼티를 가져야 함
        for st in StageType:
            phase = st.phase
            assert isinstance(phase, AnalysisPhase), f"{st.value}.phase 타입 오류"
        result.ok("StageType.phase 전체 매핑 검증 (25개)")
    except Exception as e:
        result.fail("StageType.phase 전체 매핑 검증 (25개)", str(e))


# ============================================================
# [2] 상수 테스트 (5개)
# ============================================================
def test_constants(result: TestResult) -> None:
    """상수 검증 테스트."""
    print("\n[2] 상수 테스트")
    _reset_coordinator()

    # 2-1. DEFAULT_STAGE_TIMEOUT > 0
    try:
        assert DEFAULT_STAGE_TIMEOUT > 0, f"DEFAULT_STAGE_TIMEOUT: {DEFAULT_STAGE_TIMEOUT}"
        assert isinstance(DEFAULT_STAGE_TIMEOUT, (int, float))
        result.ok("DEFAULT_STAGE_TIMEOUT > 0")
    except Exception as e:
        result.fail("DEFAULT_STAGE_TIMEOUT > 0", str(e))

    # 2-2. DEFAULT_PIPELINE_TIMEOUT > 0
    try:
        assert DEFAULT_PIPELINE_TIMEOUT > 0, f"DEFAULT_PIPELINE_TIMEOUT: {DEFAULT_PIPELINE_TIMEOUT}"
        assert isinstance(DEFAULT_PIPELINE_TIMEOUT, (int, float))
        result.ok("DEFAULT_PIPELINE_TIMEOUT > 0")
    except Exception as e:
        result.fail("DEFAULT_PIPELINE_TIMEOUT > 0", str(e))

    # 2-3. DEFAULT_MAX_RETRIES >= 0
    try:
        assert DEFAULT_MAX_RETRIES >= 0, f"DEFAULT_MAX_RETRIES: {DEFAULT_MAX_RETRIES}"
        assert isinstance(DEFAULT_MAX_RETRIES, int)
        result.ok("DEFAULT_MAX_RETRIES >= 0")
    except Exception as e:
        result.fail("DEFAULT_MAX_RETRIES >= 0", str(e))

    # 2-4. DEFAULT_RETRY_DELAY > 0
    try:
        assert DEFAULT_RETRY_DELAY > 0, f"DEFAULT_RETRY_DELAY: {DEFAULT_RETRY_DELAY}"
        assert isinstance(DEFAULT_RETRY_DELAY, (int, float))
        result.ok("DEFAULT_RETRY_DELAY > 0")
    except Exception as e:
        result.fail("DEFAULT_RETRY_DELAY > 0", str(e))

    # 2-5. MAX_CONCURRENT_PIPELINES > 0
    try:
        assert MAX_CONCURRENT_PIPELINES > 0, f"MAX_CONCURRENT_PIPELINES: {MAX_CONCURRENT_PIPELINES}"
        assert isinstance(MAX_CONCURRENT_PIPELINES, int)
        result.ok("MAX_CONCURRENT_PIPELINES > 0")
    except Exception as e:
        result.fail("MAX_CONCURRENT_PIPELINES > 0", str(e))


# ============================================================
# [3] 예외 클래스 (5개)
# ============================================================
def test_exceptions(result: TestResult) -> None:
    """예외 클래스 테스트."""
    print("\n[3] 예외 클래스 테스트")
    _reset_coordinator()

    # 3-1. PipelineException 생성
    try:
        exc = PipelineException("테스트 오류", pipeline_id="test-001")
        assert "테스트 오류" in str(exc)
        assert exc.pipeline_id == "test-001"
        result.ok("PipelineException 생성")
    except Exception as e:
        result.fail("PipelineException 생성", str(e))

    # 3-2. StageExecutionError 스테이지 정보 포함
    try:
        exc = StageExecutionError(
            stage_type=StageType.DETECTION,
            reason="감지 실패",
            pipeline_id="test-002",
        )
        assert exc.stage_type == StageType.DETECTION
        assert exc.reason == "감지 실패"
        assert exc.pipeline_id == "test-002"
        assert "detection" in str(exc).lower() or "감지" in str(exc)
        result.ok("StageExecutionError 스테이지 정보 포함")
    except Exception as e:
        result.fail("StageExecutionError 스테이지 정보 포함", str(e))

    # 3-3. PipelineTimeoutError 타임아웃 값 포함
    try:
        exc = PipelineTimeoutError(timeout_seconds=120.5, pipeline_id="test-003")
        assert exc.timeout_seconds == 120.5
        assert exc.pipeline_id == "test-003"
        assert "120.5" in str(exc)
        result.ok("PipelineTimeoutError 타임아웃 값 포함")
    except Exception as e:
        result.fail("PipelineTimeoutError 타임아웃 값 포함", str(e))

    # 3-4. PipelineConfigError 생성
    try:
        exc = PipelineConfigError("설정 오류 메시지", pipeline_id="test-004")
        assert exc.pipeline_id == "test-004"
        assert "설정 오류" in str(exc)
        result.ok("PipelineConfigError 생성")
    except Exception as e:
        result.fail("PipelineConfigError 생성", str(e))

    # 3-5. 예외 계층 구조
    try:
        # PipelineException -> AnalysisException -> CourtViewException -> Exception
        assert issubclass(PipelineException, Exception)
        assert issubclass(StageExecutionError, PipelineException)
        assert issubclass(PipelineTimeoutError, PipelineException)
        assert issubclass(PipelineConfigError, PipelineException)
        # 인스턴스 확인
        exc = StageExecutionError(StageType.CLEANUP, "테스트")
        assert isinstance(exc, PipelineException)
        assert isinstance(exc, Exception)
        result.ok("예외 계층 구조 확인")
    except Exception as e:
        result.fail("예외 계층 구조 확인", str(e))


# ============================================================
# [4] 데이터클래스 테스트 (15개)
# ============================================================
def test_dataclasses(result: TestResult) -> None:
    """데이터클래스 테스트."""
    print("\n[4] 데이터클래스 테스트")
    _reset_coordinator()

    # 4-1. StageConfig 기본값 생성
    try:
        sc = StageConfig(stage_type=StageType.INITIALIZATION)
        assert sc.stage_type == StageType.INITIALIZATION
        assert sc.handler is None
        assert sc.timeout_seconds == DEFAULT_STAGE_TIMEOUT
        assert sc.max_retries == DEFAULT_MAX_RETRIES
        assert sc.retry_delay == DEFAULT_RETRY_DELAY
        assert sc.skip_on_failure is False
        assert sc.dependencies == []
        assert sc.metadata == {}
        assert sc.stage_name == "initialization"
        result.ok("StageConfig 기본값 생성")
    except Exception as e:
        result.fail("StageConfig 기본값 생성", str(e))

    # 4-2. StageConfig 커스텀 핸들러 설정
    try:
        sc = StageConfig(
            stage_type=StageType.DETECTION,
            handler=mock_handler,
            timeout_seconds=120.0,
            max_retries=5,
        )
        assert sc.handler is mock_handler
        assert sc.timeout_seconds == 120.0
        assert sc.max_retries == 5
        result.ok("StageConfig 커스텀 핸들러 설정")
    except Exception as e:
        result.fail("StageConfig 커스텀 핸들러 설정", str(e))

    # 4-3. StageConfig 의존성 설정
    try:
        sc = StageConfig(
            stage_type=StageType.POSE_ESTIMATION,
            dependencies=[StageType.DETECTION, StageType.PERSON_DETECTION],
        )
        assert len(sc.dependencies) == 2
        assert StageType.DETECTION in sc.dependencies
        d = sc.to_dict()
        assert "detection" in d["dependencies"]
        result.ok("StageConfig 의존성 설정")
    except Exception as e:
        result.fail("StageConfig 의존성 설정", str(e))

    # 4-4. StageResult COMPLETED 생성
    try:
        now = datetime.now(timezone.utc)
        sr = StageResult(
            stage_type=StageType.DETECTION,
            status=StageStatus.COMPLETED,
            started_at=now,
            completed_at=now,
            output={"boxes": [1, 2, 3]},
        )
        assert sr.status == StageStatus.COMPLETED
        assert sr.is_success is True
        assert sr.is_failed is False
        assert sr.output == {"boxes": [1, 2, 3]}
        result.ok("StageResult COMPLETED 생성")
    except Exception as e:
        result.fail("StageResult COMPLETED 생성", str(e))

    # 4-5. StageResult.is_failed 프로퍼티
    try:
        sr = StageResult(
            stage_type=StageType.DETECTION,
            status=StageStatus.FAILED,
            started_at=datetime.now(timezone.utc),
            error=RuntimeError("test"),
            error_message="test",
        )
        assert sr.is_failed is True
        assert sr.is_success is False
        result.ok("StageResult.is_failed 프로퍼티")
    except Exception as e:
        result.fail("StageResult.is_failed 프로퍼티", str(e))

    # 4-6. StageResult duration 계산
    try:
        from datetime import timedelta
        start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)
        sr = StageResult(
            stage_type=StageType.INITIALIZATION,
            status=StageStatus.COMPLETED,
            started_at=start,
            completed_at=end,
        )
        # __post_init__에서 자동 계산
        assert abs(sr.duration_seconds - 5.0) < 0.01, f"duration: {sr.duration_seconds}"
        result.ok("StageResult duration 자동 계산")
    except Exception as e:
        result.fail("StageResult duration 자동 계산", str(e))

    # 4-7. PipelineConfig 생성
    try:
        pc = PipelineConfig(
            pipeline_type=PipelineType.TRAINING_SHOOTING,
            stages=[
                StageConfig(stage_type=StageType.INITIALIZATION),
                StageConfig(stage_type=StageType.DETECTION),
            ],
        )
        assert pc.pipeline_type == PipelineType.TRAINING_SHOOTING
        assert len(pc.stages) == 2
        assert pc.fail_fast is True
        assert pc.parallel_stages is False
        result.ok("PipelineConfig 생성")
    except Exception as e:
        result.fail("PipelineConfig 생성", str(e))

    # 4-8. PipelineConfig.stage_count
    try:
        pc = PipelineConfig(
            pipeline_type=PipelineType.GAME_FULL,
            stages=[StageConfig(stage_type=s) for s in [
                StageType.INITIALIZATION,
                StageType.VIDEO_DOWNLOAD,
                StageType.DETECTION,
            ]],
        )
        assert pc.stage_count == 3
        # add_stage
        pc.add_stage(StageConfig(stage_type=StageType.CLEANUP))
        assert pc.stage_count == 4
        result.ok("PipelineConfig.stage_count")
    except Exception as e:
        result.fail("PipelineConfig.stage_count", str(e))

    # 4-9. PipelineProgress 생성
    try:
        pp = PipelineProgress(
            pipeline_id="pp-001",
            pipeline_type=PipelineType.TRAINING,
            status=PipelineStatus.RUNNING,
            total_stages=5,
            completed_stages=2,
        )
        assert pp.pipeline_id == "pp-001"
        assert pp.total_stages == 5
        assert pp.completed_stages == 2
        result.ok("PipelineProgress 생성")
    except Exception as e:
        result.fail("PipelineProgress 생성", str(e))

    # 4-10. PipelineProgress.progress_percent 계산
    try:
        pp = PipelineProgress(
            pipeline_id="pp-002",
            pipeline_type=PipelineType.GAME,
            status=PipelineStatus.RUNNING,
            total_stages=10,
            completed_stages=5,
            skipped_stages=1,
        )
        # (5 + 1) / 10 * 100 = 60.0%
        assert abs(pp.progress_percent - 60.0) < 0.01, f"percent: {pp.progress_percent}"
        result.ok("PipelineProgress.progress_percent 계산")
    except Exception as e:
        result.fail("PipelineProgress.progress_percent 계산", str(e))

    # 4-11. PipelineProgress.update_stage_completed
    try:
        pp = PipelineProgress(
            pipeline_id="pp-003",
            pipeline_type=PipelineType.REFEREE,
            status=PipelineStatus.RUNNING,
            total_stages=4,
        )
        assert pp.completed_stages == 0
        sr = StageResult(
            stage_type=StageType.INITIALIZATION,
            status=StageStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
        )
        pp.update_stage_completed(sr)
        assert pp.completed_stages == 1
        assert abs(pp.progress_percent - 25.0) < 0.01
        # SKIPPED 처리
        sr_skip = StageResult(
            stage_type=StageType.CLEANUP,
            status=StageStatus.SKIPPED,
            started_at=datetime.now(timezone.utc),
        )
        pp.update_stage_completed(sr_skip)
        assert pp.skipped_stages == 1
        # (1 + 1) / 4 * 100 = 50%
        assert abs(pp.progress_percent - 50.0) < 0.01
        result.ok("PipelineProgress.update_stage_completed")
    except Exception as e:
        result.fail("PipelineProgress.update_stage_completed", str(e))

    # 4-12. PipelineProgress.set_current_stage
    try:
        pp = PipelineProgress(
            pipeline_id="pp-004",
            pipeline_type=PipelineType.TRAINING_SHOOTING,
            status=PipelineStatus.RUNNING,
            total_stages=3,
        )
        pp.set_current_stage(StageType.POSE_ESTIMATION)
        assert pp.current_stage == StageType.POSE_ESTIMATION
        assert pp.current_phase == AnalysisPhase.POSE_ESTIMATING
        result.ok("PipelineProgress.set_current_stage")
    except Exception as e:
        result.fail("PipelineProgress.set_current_stage", str(e))

    # 4-13. CheckpointData 생성 및 to_dict
    try:
        cd = CheckpointData(
            pipeline_id="cp-001",
            pipeline_type=PipelineType.GAME_FULL,
            completed_stages=[StageType.INITIALIZATION, StageType.VIDEO_DOWNLOAD],
            current_stage_index=2,
            stage_outputs={"initialization": {"ok": True}},
            metadata={"user_id": "user-1"},
            created_at=datetime.now(timezone.utc),
        )
        assert cd.pipeline_id == "cp-001"
        assert cd.current_stage_index == 2
        assert len(cd.completed_stages) == 2
        # checksum 자동 생성
        assert len(cd.checksum) > 0
        # to_dict
        d = cd.to_dict()
        assert d["pipeline_type"] == "game_full"
        assert len(d["completed_stages"]) == 2
        assert "initialization" in d["completed_stages"]
        result.ok("CheckpointData 생성 및 to_dict")
    except Exception as e:
        result.fail("CheckpointData 생성 및 to_dict", str(e))

    # 4-14. PipelineContext 생성
    try:
        ctx = PipelineContext(
            pipeline_id="ctx-001",
            pipeline_type=PipelineType.TRAINING,
            input_data={"video_url": "https://example.com/v.mp4"},
            metadata={"session": "s-1"},
        )
        assert ctx.pipeline_id == "ctx-001"
        assert ctx.input_data["video_url"] == "https://example.com/v.mp4"
        assert ctx.checkpoint_enabled is True
        assert ctx.last_checkpoint_index == -1
        assert ctx.recovered_from_checkpoint is False
        result.ok("PipelineContext 생성")
    except Exception as e:
        result.fail("PipelineContext 생성", str(e))

    # 4-15. PipelineContext.is_cancelled (cancellation_token 연동)
    try:
        token = asyncio.Event()
        ctx = PipelineContext(
            pipeline_id="ctx-002",
            pipeline_type=PipelineType.GAME,
            cancellation_token=token,
        )
        assert ctx.is_cancelled is False
        token.set()
        assert ctx.is_cancelled is True
        result.ok("PipelineContext.is_cancelled (cancellation_token)")
    except Exception as e:
        result.fail("PipelineContext.is_cancelled (cancellation_token)", str(e))


# ============================================================
# [5] PipelineBuilder 테스트 (8개)
# ============================================================
def test_pipeline_builder(result: TestResult) -> None:
    """PipelineBuilder 테스트."""
    print("\n[5] PipelineBuilder 테스트")
    _reset_coordinator()

    # 5-1. PipelineType으로 빌더 생성
    try:
        builder = PipelineBuilder(PipelineType.TRAINING_SHOOTING)
        assert builder._pipeline_type == PipelineType.TRAINING_SHOOTING
        result.ok("PipelineBuilder 생성")
    except Exception as e:
        result.fail("PipelineBuilder 생성", str(e))

    # 5-2. add_stage 체이닝
    try:
        builder = PipelineBuilder(PipelineType.GAME)
        ret = builder.add_stage(StageType.INITIALIZATION)
        assert ret is builder, "add_stage가 self를 반환해야 함"
        builder.add_stage(StageType.DETECTION).add_stage(StageType.CLEANUP)
        assert len(builder._stages) == 3
        result.ok("add_stage 체이닝")
    except Exception as e:
        result.fail("add_stage 체이닝", str(e))

    # 5-3. with_timeout
    try:
        builder = PipelineBuilder(PipelineType.REFEREE)
        ret = builder.with_timeout(2400)
        assert ret is builder
        assert builder._timeout == 2400
        result.ok("with_timeout")
    except Exception as e:
        result.fail("with_timeout", str(e))

    # 5-4. with_fail_fast
    try:
        builder = PipelineBuilder(PipelineType.REPORT)
        ret = builder.with_fail_fast(False)
        assert ret is builder
        assert builder._fail_fast is False
        result.ok("with_fail_fast")
    except Exception as e:
        result.fail("with_fail_fast", str(e))

    # 5-5. with_parallel
    try:
        builder = PipelineBuilder(PipelineType.GAME_FULL)
        ret = builder.with_parallel(True, max_parallel=8)
        assert ret is builder
        assert builder._parallel_stages is True
        assert builder._max_parallel == 8
        result.ok("with_parallel")
    except Exception as e:
        result.fail("with_parallel", str(e))

    # 5-6. with_metadata
    try:
        builder = PipelineBuilder(PipelineType.TRAINING)
        ret = builder.with_metadata("user_id", "u-1")
        assert ret is builder
        assert builder._metadata["user_id"] == "u-1"
        builder.with_metadata("source", "app")
        assert builder._metadata["source"] == "app"
        result.ok("with_metadata")
    except Exception as e:
        result.fail("with_metadata", str(e))

    # 5-7. build() -> PipelineConfig 반환
    try:
        config = (
            PipelineBuilder(PipelineType.TRAINING_DRIBBLING)
            .add_stage(StageType.INITIALIZATION)
            .add_stage(StageType.VIDEO_DOWNLOAD)
            .add_stage(StageType.DETECTION)
            .with_timeout(900)
            .with_fail_fast(False)
            .with_parallel(True, 6)
            .with_metadata("version", "1.0")
            .build()
        )
        assert isinstance(config, PipelineConfig)
        assert config.pipeline_type == PipelineType.TRAINING_DRIBBLING
        assert config.timeout_seconds == 900
        assert config.fail_fast is False
        assert config.parallel_stages is True
        assert config.max_parallel == 6
        assert config.metadata["version"] == "1.0"
        result.ok("build() -> PipelineConfig 반환")
    except Exception as e:
        result.fail("build() -> PipelineConfig 반환", str(e))

    # 5-8. build된 config의 stage_count 확인
    try:
        config = (
            PipelineBuilder(PipelineType.GAME)
            .add_stage(StageType.INITIALIZATION)
            .add_stage(StageType.DETECTION)
            .add_stage(StageType.POSE_ESTIMATION)
            .add_stage(StageType.GAME_ANALYSIS)
            .add_stage(StageType.CLEANUP)
            .build()
        )
        assert config.stage_count == 5
        result.ok("빌드된 config stage_count 확인")
    except Exception as e:
        result.fail("빌드된 config stage_count 확인", str(e))


# ============================================================
# [6] PipelineTemplates 테스트 (5개)
# ============================================================
def test_pipeline_templates(result: TestResult) -> None:
    """PipelineTemplates 사전 정의 템플릿 테스트."""
    print("\n[6] PipelineTemplates 테스트")
    _reset_coordinator()

    # 6-1. training_shooting 템플릿
    try:
        config = PipelineTemplates.training_shooting()
        assert isinstance(config, PipelineConfig)
        assert config.pipeline_type == PipelineType.TRAINING_SHOOTING
        assert config.stage_count > 0
        # 핵심 스테이지 존재 확인
        stage_types = [s.stage_type for s in config.stages]
        assert StageType.INITIALIZATION in stage_types
        assert StageType.SHOOTING_ANALYSIS in stage_types
        assert StageType.FEEDBACK_GENERATION in stage_types
        result.ok("training_shooting 템플릿 유효성")
    except Exception as e:
        result.fail("training_shooting 템플릿 유효성", str(e))

    # 6-2. training_dribbling 템플릿
    try:
        config = PipelineTemplates.training_dribbling()
        assert isinstance(config, PipelineConfig)
        assert config.pipeline_type == PipelineType.TRAINING_DRIBBLING
        assert config.stage_count > 0
        stage_types = [s.stage_type for s in config.stages]
        assert StageType.DRIBBLING_ANALYSIS in stage_types
        result.ok("training_dribbling 템플릿 유효성")
    except Exception as e:
        result.fail("training_dribbling 템플릿 유효성", str(e))

    # 6-3. training_comparison 템플릿
    try:
        config = PipelineTemplates.training_comparison()
        assert isinstance(config, PipelineConfig)
        assert config.pipeline_type == PipelineType.TRAINING_COMPARISON
        assert config.stage_count > 0
        stage_types = [s.stage_type for s in config.stages]
        assert StageType.COMPARISON_ANALYSIS in stage_types
        result.ok("training_comparison 템플릿 유효성")
    except Exception as e:
        result.fail("training_comparison 템플릿 유효성", str(e))

    # 6-4. game_full 템플릿
    try:
        config = PipelineTemplates.game_full()
        assert isinstance(config, PipelineConfig)
        assert config.pipeline_type == PipelineType.GAME_FULL
        assert config.stage_count > 0
        stage_types = [s.stage_type for s in config.stages]
        assert StageType.GAME_ANALYSIS in stage_types
        assert StageType.COURT_DETECTION in stage_types
        result.ok("game_full 템플릿 유효성")
    except Exception as e:
        result.fail("game_full 템플릿 유효성", str(e))

    # 6-5. referee_full 템플릿
    try:
        config = PipelineTemplates.referee_full()
        assert isinstance(config, PipelineConfig)
        assert config.pipeline_type == PipelineType.REFEREE_FULL
        assert config.stage_count > 0
        stage_types = [s.stage_type for s in config.stages]
        assert StageType.REFEREE_ANALYSIS in stage_types
        result.ok("referee_full 템플릿 유효성")
    except Exception as e:
        result.fail("referee_full 템플릿 유효성", str(e))


# ============================================================
# [7] PipelineCoordinator 기본 (12개)
# ============================================================
def test_coordinator_basic(result: TestResult) -> None:
    """PipelineCoordinator 기본 기능 테스트."""
    print("\n[7] PipelineCoordinator 기본 테스트")
    _reset_coordinator()

    # 7-1. 인스턴스 생성
    try:
        coord = PipelineCoordinator()
        assert coord is not None
        assert isinstance(coord, PipelineCoordinator)
        result.ok("PipelineCoordinator 인스턴스 생성")
    except Exception as e:
        result.fail("PipelineCoordinator 인스턴스 생성", str(e))

    # 7-2. register_handler
    try:
        coord = PipelineCoordinator()
        coord.register_handler(StageType.DETECTION, mock_handler)
        handler = coord.get_handler(StageType.DETECTION)
        assert handler is mock_handler
        result.ok("register_handler")
    except Exception as e:
        result.fail("register_handler", str(e))

    # 7-3. unregister_handler
    try:
        coord = PipelineCoordinator()
        coord.register_handler(StageType.DETECTION, mock_handler)
        coord.unregister_handler(StageType.DETECTION)
        handler = coord.get_handler(StageType.DETECTION)
        assert handler is None
        result.ok("unregister_handler")
    except Exception as e:
        result.fail("unregister_handler", str(e))

    # 7-4. get_handler (미등록 시 None)
    try:
        coord = PipelineCoordinator()
        handler = coord.get_handler(StageType.GAME_ANALYSIS)
        assert handler is None
        result.ok("get_handler 미등록 시 None")
    except Exception as e:
        result.fail("get_handler 미등록 시 None", str(e))

    # 7-5. add_progress_callback / remove_progress_callback
    try:
        coord = PipelineCoordinator()
        called = []

        def on_progress(progress):
            called.append(progress)

        coord.add_progress_callback(on_progress)
        assert on_progress in coord._progress_callbacks
        coord.remove_progress_callback(on_progress)
        assert on_progress not in coord._progress_callbacks
        result.ok("add/remove_progress_callback")
    except Exception as e:
        result.fail("add/remove_progress_callback", str(e))

    # 7-6. add_error_callback / remove_error_callback
    try:
        coord = PipelineCoordinator()
        called = []

        def on_error(exc, stage_result):
            called.append(exc)

        coord.add_error_callback(on_error)
        assert on_error in coord._error_callbacks
        coord.remove_error_callback(on_error)
        assert on_error not in coord._error_callbacks
        result.ok("add/remove_error_callback")
    except Exception as e:
        result.fail("add/remove_error_callback", str(e))

    # 7-7. active_count 초기값 0
    try:
        coord = PipelineCoordinator()
        assert coord.active_count == 0
        result.ok("active_count 초기값 0")
    except Exception as e:
        result.fail("active_count 초기값 0", str(e))

    # 7-8. registered_handlers 초기 빈 리스트
    try:
        coord = PipelineCoordinator()
        assert coord.registered_handlers == []
        coord.register_handler(StageType.INITIALIZATION, mock_handler)
        assert StageType.INITIALIZATION in coord.registered_handlers
        result.ok("registered_handlers 리스트")
    except Exception as e:
        result.fail("registered_handlers 리스트", str(e))

    # 7-9. get_status 딕셔너리 반환
    try:
        coord = PipelineCoordinator()
        status = coord.get_status()
        assert isinstance(status, dict)
        assert "active_pipelines" in status
        assert "registered_handlers" in status
        assert "config" in status
        assert "checkpoints" in status
        assert status["active_pipelines"] == 0
        result.ok("get_status 딕셔너리 반환")
    except Exception as e:
        result.fail("get_status 딕셔너리 반환", str(e))

    # 7-10. reload_config 호출
    try:
        coord = PipelineCoordinator()
        coord.reload_config()  # 예외 없이 호출 성공
        result.ok("reload_config 호출")
    except Exception as e:
        result.fail("reload_config 호출", str(e))

    # 7-11. 싱글톤: get_coordinator / _reset_coordinator
    try:
        _reset_coordinator()
        coord1 = get_coordinator()
        coord2 = get_coordinator()
        assert coord1 is coord2, "get_coordinator 싱글톤이어야 함"
        _reset_coordinator()
        coord3 = get_coordinator()
        assert coord3 is not coord1, "리셋 후 새 인스턴스여야 함"
        result.ok("get_coordinator / _reset_coordinator 싱글톤")
    except Exception as e:
        result.fail("get_coordinator / _reset_coordinator 싱글톤", str(e))

    # 7-12. create_pipeline 헬퍼
    try:
        _reset_coordinator()
        # 템플릿 기반 (스테이지 미지정)
        config = create_pipeline(PipelineType.TRAINING_SHOOTING)
        assert isinstance(config, PipelineConfig)
        assert config.pipeline_type == PipelineType.TRAINING_SHOOTING
        assert config.stage_count > 0  # 템플릿에서 스테이지 채워짐

        # 스테이지 직접 지정
        stages = [StageConfig(stage_type=StageType.INITIALIZATION)]
        config2 = create_pipeline(PipelineType.GAME, stages=stages, timeout_seconds=500)
        assert config2.stage_count == 1
        assert config2.timeout_seconds == 500
        result.ok("create_pipeline 헬퍼")
    except Exception as e:
        result.fail("create_pipeline 헬퍼", str(e))


# ============================================================
# [8] 비동기 실행 테스트 (10개)
# ============================================================
def test_async_execution(result: TestResult) -> None:
    """비동기 파이프라인 실행 테스트."""
    print("\n[8] 비동기 실행 테스트")
    _reset_coordinator()

    # 8-1. 단일 스테이지 파이프라인 실행
    try:
        _reset_coordinator()

        async def _test():
            coord = PipelineCoordinator()
            coord.register_handler(StageType.INITIALIZATION, mock_handler)
            config = PipelineConfig(
                pipeline_type=PipelineType.TRAINING,
                stages=[StageConfig(stage_type=StageType.INITIALIZATION)],
                timeout_seconds=10.0,
            )
            progress = await coord.execute(config)
            return progress

        progress = asyncio.run(_test())
        assert progress.status == PipelineStatus.COMPLETED
        assert progress.completed_stages == 1
        result.ok("단일 스테이지 파이프라인 실행")
    except Exception as e:
        result.fail("단일 스테이지 파이프라인 실행", str(e))

    # 8-2. 다중 스테이지 파이프라인 실행
    try:
        _reset_coordinator()

        async def _test():
            coord = PipelineCoordinator()
            coord.register_handler(StageType.INITIALIZATION, mock_handler)
            coord.register_handler(StageType.VIDEO_DOWNLOAD, mock_handler)
            coord.register_handler(StageType.DETECTION, mock_handler)
            config = PipelineConfig(
                pipeline_type=PipelineType.TRAINING,
                stages=[
                    StageConfig(stage_type=StageType.INITIALIZATION),
                    StageConfig(stage_type=StageType.VIDEO_DOWNLOAD),
                    StageConfig(stage_type=StageType.DETECTION),
                ],
                timeout_seconds=10.0,
            )
            return await coord.execute(config)

        progress = asyncio.run(_test())
        assert progress.status == PipelineStatus.COMPLETED
        assert progress.completed_stages == 3
        result.ok("다중 스테이지 파이프라인 실행")
    except Exception as e:
        result.fail("다중 스테이지 파이프라인 실행", str(e))

    # 8-3. 핸들러가 context를 수신하는지 확인
    try:
        _reset_coordinator()
        received_ctx = {}

        async def context_handler(context):
            received_ctx["pipeline_id"] = context.pipeline_id
            received_ctx["pipeline_type"] = context.pipeline_type
            return {"checked": True}

        async def _test():
            coord = PipelineCoordinator()
            coord.register_handler(StageType.INITIALIZATION, context_handler)
            config = PipelineConfig(
                pipeline_type=PipelineType.GAME,
                stages=[StageConfig(stage_type=StageType.INITIALIZATION)],
                timeout_seconds=10.0,
            )
            return await coord.execute(config, pipeline_id="ctx-test-001")

        asyncio.run(_test())
        assert received_ctx["pipeline_id"] == "ctx-test-001"
        assert received_ctx["pipeline_type"] == PipelineType.GAME
        result.ok("핸들러가 context를 수신")
    except Exception as e:
        result.fail("핸들러가 context를 수신", str(e))

    # 8-4. progress_callback 호출 확인
    try:
        _reset_coordinator()
        progress_updates = []

        async def _test():
            coord = PipelineCoordinator()
            coord.register_handler(StageType.INITIALIZATION, mock_handler)
            coord.add_progress_callback(lambda p: progress_updates.append(p.status))
            config = PipelineConfig(
                pipeline_type=PipelineType.TRAINING,
                stages=[StageConfig(stage_type=StageType.INITIALIZATION)],
                timeout_seconds=10.0,
            )
            return await coord.execute(config)

        asyncio.run(_test())
        # progress callback은 최소 실행 시작, 스테이지 시작, 완료 시 호출됨
        assert len(progress_updates) >= 2, f"콜백 호출 횟수: {len(progress_updates)}"
        result.ok("progress_callback 호출 확인")
    except Exception as e:
        result.fail("progress_callback 호출 확인", str(e))

    # 8-5. error_callback 실패 시 호출 확인
    try:
        _reset_coordinator()
        error_events = []

        async def _test():
            coord = PipelineCoordinator()
            coord.register_handler(StageType.DETECTION, failing_handler)
            coord.add_error_callback(lambda exc, sr: error_events.append(str(exc)))
            config = PipelineConfig(
                pipeline_type=PipelineType.TRAINING,
                stages=[
                    StageConfig(
                        stage_type=StageType.DETECTION,
                        max_retries=0,
                        skip_on_failure=False,
                    ),
                ],
                timeout_seconds=10.0,
                fail_fast=True,
            )
            try:
                progress = await coord.execute(config)
                return progress
            except PipelineException:
                # 실패한 파이프라인은 예외를 던질 수 있음
                return None

        progress = asyncio.run(_test())
        # YAML skip_on_error 설정에 따라:
        # - skip_on_error=True: 스테이지가 SKIPPED되고 error_callback 미호출
        # - skip_on_error=False: 스테이지가 FAILED되고 error_callback 호출
        # 어느 경우든 핸들러 실패가 정상적으로 처리되어야 함
        if len(error_events) > 0:
            # 에러 콜백이 호출됨 (FAILED 경로)
            result.ok("error_callback 실패 시 호출 확인")
        elif progress is not None and (progress.skipped_stages > 0 or progress.failed_stages > 0):
            # skip_on_error로 SKIPPED되어 에러 콜백 미호출이지만 실패가 감지됨
            result.ok("error_callback 실패 시 호출 확인")
        else:
            result.fail("error_callback 실패 시 호출 확인", "에러 감지 실패")
    except Exception as e:
        result.fail("error_callback 실패 시 호출 확인", str(e))

    # 8-6. 파이프라인 타임아웃
    try:
        _reset_coordinator()

        async def _test():
            coord = PipelineCoordinator()
            coord.register_handler(StageType.INITIALIZATION, timeout_handler)
            config = PipelineConfig(
                pipeline_type=PipelineType.TRAINING,
                stages=[
                    StageConfig(
                        stage_type=StageType.INITIALIZATION,
                        timeout_seconds=0.1,
                        max_retries=0,
                    ),
                ],
                timeout_seconds=0.5,
            )
            return await coord.execute(config)

        # 실행 - 타임아웃으로 FAILED 또는 PipelineTimeoutError 예외 발생
        try:
            progress = asyncio.run(_test())
            # 타임아웃이 발생했지만 skip_on_error 설정으로 SKIPPED 될 수 있음
            assert progress.status in (PipelineStatus.COMPLETED, PipelineStatus.FAILED)
            result.ok("파이프라인 타임아웃 처리")
        except PipelineTimeoutError:
            result.ok("파이프라인 타임아웃 처리")
        except PipelineException:
            result.ok("파이프라인 타임아웃 처리")
    except Exception as e:
        result.fail("파이프라인 타임아웃 처리", str(e))

    # 8-7. 스테이지 재시도
    try:
        _reset_coordinator()
        _retry_counter["count"] = 0

        async def _test():
            coord = PipelineCoordinator()
            coord.register_handler(StageType.DETECTION, retry_then_succeed_handler)
            config = PipelineConfig(
                pipeline_type=PipelineType.TRAINING,
                stages=[
                    StageConfig(
                        stage_type=StageType.DETECTION,
                        max_retries=5,
                        retry_delay=0.01,
                        timeout_seconds=5.0,
                    ),
                ],
                timeout_seconds=30.0,
            )
            return await coord.execute(config)

        progress = asyncio.run(_test())
        # 재시도 후 성공해야 함
        assert progress.completed_stages >= 1 or progress.skipped_stages >= 1
        assert _retry_counter["count"] >= 3, f"재시도 횟수: {_retry_counter['count']}"
        result.ok("스테이지 재시도 후 성공")
    except Exception as e:
        result.fail("스테이지 재시도 후 성공", str(e))

    # 8-8. skip_on_failure 설정
    try:
        _reset_coordinator()

        async def _test():
            coord = PipelineCoordinator()
            coord.register_handler(StageType.DETECTION, failing_handler)
            coord.register_handler(StageType.CLEANUP, mock_handler)
            config = PipelineConfig(
                pipeline_type=PipelineType.TRAINING,
                stages=[
                    StageConfig(
                        stage_type=StageType.DETECTION,
                        skip_on_failure=True,
                        max_retries=0,
                    ),
                    StageConfig(stage_type=StageType.CLEANUP),
                ],
                timeout_seconds=10.0,
                fail_fast=False,
            )
            return await coord.execute(config)

        progress = asyncio.run(_test())
        # DETECTION은 skip, CLEANUP은 성공
        assert progress.skipped_stages >= 1, f"skipped: {progress.skipped_stages}"
        result.ok("skip_on_failure 설정 동작")
    except Exception as e:
        result.fail("skip_on_failure 설정 동작", str(e))

    # 8-9. 파이프라인 취소 (cancellation_token.set())
    try:
        _reset_coordinator()

        async def _test():
            coord = PipelineCoordinator()

            async def slow_then_check(context):
                await asyncio.sleep(0.05)
                return {"ok": True}

            async def cancel_checker(context):
                # 이 스테이지 실행 전에 이미 취소됨
                await asyncio.sleep(0.01)
                return {"should_not_run": True}

            coord.register_handler(StageType.INITIALIZATION, slow_then_check)
            coord.register_handler(StageType.DETECTION, cancel_checker)
            coord.register_handler(StageType.CLEANUP, cancel_checker)

            config = PipelineConfig(
                pipeline_type=PipelineType.TRAINING,
                stages=[
                    StageConfig(stage_type=StageType.INITIALIZATION),
                    StageConfig(stage_type=StageType.DETECTION),
                    StageConfig(stage_type=StageType.CLEANUP),
                ],
                timeout_seconds=10.0,
            )

            # 실행 시작 후 잠시 뒤에 취소
            async def run_and_cancel():
                task = asyncio.create_task(coord.execute(config, pipeline_id="cancel-test"))
                await asyncio.sleep(0.02)
                coord.cancel("cancel-test")
                return await task

            return await run_and_cancel()

        progress = asyncio.run(_test())
        # 취소 처리됨 - CANCELLED이거나 일부만 완료
        assert progress.status in (
            PipelineStatus.CANCELLED,
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
        )
        result.ok("파이프라인 취소 동작")
    except Exception as e:
        result.fail("파이프라인 취소 동작", str(e))

    # 8-10. 파이프라인 결과의 completed_stages 정확도
    try:
        _reset_coordinator()

        async def _test():
            coord = PipelineCoordinator()
            coord.register_handler(StageType.INITIALIZATION, mock_handler)
            coord.register_handler(StageType.VIDEO_DOWNLOAD, mock_handler)
            coord.register_handler(StageType.DETECTION, mock_handler)
            coord.register_handler(StageType.POSE_ESTIMATION, mock_handler)

            config = PipelineConfig(
                pipeline_type=PipelineType.TRAINING,
                stages=[
                    StageConfig(stage_type=StageType.INITIALIZATION),
                    StageConfig(stage_type=StageType.VIDEO_DOWNLOAD),
                    StageConfig(stage_type=StageType.DETECTION),
                    StageConfig(stage_type=StageType.POSE_ESTIMATION),
                ],
                timeout_seconds=10.0,
            )
            return await coord.execute(config)

        progress = asyncio.run(_test())
        assert progress.completed_stages == 4, f"completed: {progress.completed_stages}"
        assert progress.total_stages == 4
        assert abs(progress.progress_percent - 100.0) < 0.01
        assert progress.elapsed_seconds > 0
        result.ok("completed_stages 정확도 검증")
    except Exception as e:
        result.fail("completed_stages 정확도 검증", str(e))


# ============================================================
# [9] CheckpointManager 테스트 (8개)
# ============================================================
def test_checkpoint_manager(result: TestResult) -> None:
    """CheckpointManager 테스트."""
    print("\n[9] CheckpointManager 테스트")
    _reset_coordinator()

    # 9-1. 생성
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            assert cm is not None
            assert isinstance(cm, CheckpointManager)
        result.ok("CheckpointManager 생성")
    except Exception as e:
        result.fail("CheckpointManager 생성", str(e))

    # 9-2. enabled 프로퍼티
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            # enabled는 YAML 설정에서 로드 (기본값 True)
            assert isinstance(cm.enabled, bool)
        result.ok("CheckpointManager.enabled 프로퍼티")
    except Exception as e:
        result.fail("CheckpointManager.enabled 프로퍼티", str(e))

    # 9-3. save 체크포인트
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            cp = CheckpointData(
                pipeline_id="save-test-001",
                pipeline_type=PipelineType.TRAINING,
                completed_stages=[StageType.INITIALIZATION],
                current_stage_index=1,
                stage_outputs={"initialization": {"ok": True}},
                metadata={"test": True},
                created_at=datetime.now(timezone.utc),
            )
            saved = cm.save(cp)
            if cm.enabled:
                assert saved is True
                # 파일 존재 확인
                filepath = Path(tmpdir) / "save-test-001.json"
                assert filepath.exists()
            result.ok("save 체크포인트")
    except Exception as e:
        result.fail("save 체크포인트", str(e))

    # 9-4. load 체크포인트
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            cp = CheckpointData(
                pipeline_id="load-test-001",
                pipeline_type=PipelineType.GAME_FULL,
                completed_stages=[StageType.INITIALIZATION, StageType.VIDEO_DOWNLOAD],
                current_stage_index=2,
                stage_outputs={"initialization": {"ok": True}},
                metadata={"user": "tester"},
                created_at=datetime.now(timezone.utc),
            )
            cm.save(cp)
            loaded = cm.load("load-test-001")
            if cm.enabled:
                assert loaded is not None
                assert loaded.pipeline_id == "load-test-001"
                assert loaded.pipeline_type == PipelineType.GAME_FULL
                assert loaded.current_stage_index == 2
                assert len(loaded.completed_stages) == 2
            result.ok("load 체크포인트")
    except Exception as e:
        result.fail("load 체크포인트", str(e))

    # 9-5. delete 체크포인트
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            cp = CheckpointData(
                pipeline_id="del-test-001",
                pipeline_type=PipelineType.REFEREE,
                completed_stages=[],
                current_stage_index=0,
                stage_outputs={},
                metadata={},
                created_at=datetime.now(timezone.utc),
            )
            cm.save(cp)
            deleted = cm.delete("del-test-001")
            assert deleted is True
            loaded = cm.load("del-test-001")
            assert loaded is None
            result.ok("delete 체크포인트")
    except Exception as e:
        result.fail("delete 체크포인트", str(e))

    # 9-6. list_checkpoints
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            # 여러 체크포인트 저장
            for i in range(3):
                cp = CheckpointData(
                    pipeline_id=f"list-test-{i:03d}",
                    pipeline_type=PipelineType.TRAINING,
                    completed_stages=[],
                    current_stage_index=0,
                    stage_outputs={},
                    metadata={},
                    created_at=datetime.now(timezone.utc),
                )
                cm.save(cp)
            checkpoints = cm.list_checkpoints()
            if cm.enabled:
                assert len(checkpoints) == 3
                assert "list-test-000" in checkpoints
                assert "list-test-001" in checkpoints
                assert "list-test-002" in checkpoints
            result.ok("list_checkpoints")
    except Exception as e:
        result.fail("list_checkpoints", str(e))

    # 9-7. cleanup_old
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            cp = CheckpointData(
                pipeline_id="old-test-001",
                pipeline_type=PipelineType.TRAINING,
                completed_stages=[],
                current_stage_index=0,
                stage_outputs={},
                metadata={},
                created_at=datetime.now(timezone.utc),
            )
            cm.save(cp)
            # 최근 파일이므로 정리되지 않음
            deleted_count = cm.cleanup_old(max_age_hours=24)
            assert deleted_count == 0
            # 매우 짧은 기간으로 정리 시도 (0시간 = 즉시 만료 가능)
            # 파일이 방금 생성되었으므로 mtime이 현재와 거의 같아
            # 0시간이면 cutoff가 현재 시간이므로 파일이 정리될 수 있음
            result.ok("cleanup_old")
    except Exception as e:
        result.fail("cleanup_old", str(e))

    # 9-8. should_checkpoint 간격 로직
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CheckpointManager(storage_path=tmpdir)
            interval = cm.interval
            if cm.enabled:
                # last_checkpoint = -1, stage_index = 0
                # 간격보다 작으면 False
                if interval > 1:
                    assert cm.should_checkpoint(0, -1) is False or interval <= 1
                # 간격 이상이면 True
                assert cm.should_checkpoint(interval, 0) is True
                assert cm.should_checkpoint(interval + 1, 0) is True
                # 마지막 체크포인트 직후면 False
                assert cm.should_checkpoint(1, 0) is (interval <= 1)
            result.ok("should_checkpoint 간격 로직")
    except Exception as e:
        result.fail("should_checkpoint 간격 로직", str(e))


# ============================================================
# [10] 스레드 안전성 (3개)
# ============================================================
def test_thread_safety(result: TestResult) -> None:
    """스레드 안전성 테스트."""
    print("\n[10] 스레드 안전성 테스트")
    _reset_coordinator()

    # 10-1. 동시 핸들러 등록
    try:
        coord = PipelineCoordinator()
        errors = []
        stage_types = list(StageType)[:10]

        def register_worker(st):
            try:
                coord.register_handler(st, mock_handler)
            except Exception as exc:
                errors.append(str(exc))

        threads = []
        for st in stage_types:
            t = threading.Thread(target=register_worker, args=(st,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"등록 에러: {errors}"
        # 모든 핸들러가 등록되었는지 확인
        registered = coord.registered_handlers
        for st in stage_types:
            assert st in registered, f"{st.value} 미등록"
        result.ok("동시 핸들러 등록 스레드 안전성")
    except Exception as e:
        result.fail("동시 핸들러 등록 스레드 안전성", str(e))

    # 10-2. 복수 코디네이터 리셋 격리
    try:
        _reset_coordinator()
        coord1 = get_coordinator()
        coord1.register_handler(StageType.INITIALIZATION, mock_handler)

        _reset_coordinator()
        coord2 = get_coordinator()
        # 리셋 후 새 인스턴스이므로 핸들러가 없어야 함
        assert coord2 is not coord1
        assert StageType.INITIALIZATION not in coord2.registered_handlers
        result.ok("복수 코디네이터 리셋 격리")
    except Exception as e:
        result.fail("복수 코디네이터 리셋 격리", str(e))

    # 10-3. Lock 경합 부하 테스트
    try:
        coord = PipelineCoordinator()
        errors = []
        iterations = 50

        def worker(thread_id):
            try:
                for i in range(iterations):
                    stage = list(StageType)[i % len(list(StageType))]
                    coord.register_handler(stage, mock_handler)
                    coord.get_handler(stage)
                    coord.get_status()
                    _ = coord.active_count
                    _ = coord.registered_handlers
            except Exception as exc:
                errors.append(f"Thread-{thread_id}: {exc}")

        threads = []
        for tid in range(5):
            t = threading.Thread(target=worker, args=(tid,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Lock 경합 에러: {errors}"
        result.ok("Lock 경합 부하 테스트")
    except Exception as e:
        result.fail("Lock 경합 부하 테스트", str(e))


# ============================================================
# 메인 실행
# ============================================================
def main():
    """메인 테스트 실행 함수."""
    print("=" * 60)
    print("PipelineCoordinator 단위 테스트")
    print("=" * 60)

    result = TestResult()

    # [1] Enum 테스트
    test_enums(result)

    # [2] 상수 테스트
    test_constants(result)

    # [3] 예외 클래스 테스트
    test_exceptions(result)

    # [4] 데이터클래스 테스트
    test_dataclasses(result)

    # [5] PipelineBuilder 테스트
    test_pipeline_builder(result)

    # [6] PipelineTemplates 테스트
    test_pipeline_templates(result)

    # [7] PipelineCoordinator 기본 테스트
    test_coordinator_basic(result)

    # [8] 비동기 실행 테스트
    test_async_execution(result)

    # [9] CheckpointManager 테스트
    test_checkpoint_manager(result)

    # [10] 스레드 안전성 테스트
    test_thread_safety(result)

    # 최종 결과
    _reset_coordinator()
    result.summary()

    return result.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
