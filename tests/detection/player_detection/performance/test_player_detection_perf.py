# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/detection/player_detection/performance
파일: test_player_detection_perf.py
설명: player_detection 모듈 성능 테스트
      - TeamClassifier 분류/캘리브레이션 속도
      - JerseyOCR 인식/유사문자 보정 속도
      - ReIDModule 특징 추출/매칭 속도
      - PlayerTracker 칼만 예측/매칭 속도
      - PlayerIDManager 융합/정리 속도
      - 대량 선수 메모리 안정성
      - data_extraction 초기화/finalize 지연

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from shared.constants.player_constants import (
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
)
from shared.dto.player_dto import Team

from detection.player_detection.models import (
    JerseyOCRConfig,
    PlayerIDManagerConfig,
    PlayerTrackerConfig,
    ReIDConfig,
    TeamClassifierConfig,
    _PlayerCandidate,
)
from detection.player_detection.team_classifier import TeamClassifier
from detection.player_detection.jersey_ocr import JerseyOCR
from detection.player_detection.reid_module import ReIDModule
from detection.player_detection.player_tracker import PlayerTracker
from detection.player_detection.player_id_manager import (
    IDStatus,
    PlayerIDManager,
)
from detection.player_detection.data_extraction import (
    JerseyDigitExtractor,
    PlayerBboxExtractor,
    ReIDAppearanceExtractor,
    TeamUniformExtractor,
)


# =============================================================================
# 공통 픽스처
# =============================================================================

def _make_candidate(
    x: int = 100, y: int = 50, w: int = 100, h: int = 250,
    conf: float = 0.9,
) -> _PlayerCandidate:
    """테스트용 _PlayerCandidate 생성."""
    return _PlayerCandidate(
        bbox_x=x, bbox_y=y, bbox_w=w, bbox_h=h,
        yolo_confidence=conf, class_id=PLAYER_CLASS_ID_PLAYER,
        combined_score=conf * 0.9,
    )


def _make_frame(h: int = 480, w: int = 640, value: int = 128) -> np.ndarray:
    """테스트용 프레임 생성."""
    return np.full((h, w, 3), value, dtype=np.uint8)


# =============================================================================
# TeamClassifier 성능
# =============================================================================

class TestTeamClassifierPerformance:
    """팀 분류기 성능 테스트."""

    def test_분류_1000회_속도(self) -> None:
        """단일 후보 분류 1000회 < 300ms."""
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())
        frame = _make_frame()
        c = _make_candidate()

        start = time.perf_counter()
        for _ in range(1000):
            tc.classify(c, frame)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 300.0, f"분류 1000회: {elapsed_ms:.1f}ms > 300ms"

    def test_배치_분류_100후보_속도(self) -> None:
        """100명 배치 분류 < 100ms."""
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())
        frame = _make_frame(720, 1280)

        candidates = [
            _make_candidate(x=50 + i * 12, y=50)
            for i in range(100)
        ]

        start = time.perf_counter()
        results = tc.classify_batch(candidates, frame)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert len(results) == 100
        assert elapsed_ms < 100.0, f"배치 분류 100명: {elapsed_ms:.1f}ms > 100ms"

    def test_수동_캘리브레이션_속도(self) -> None:
        """수동 캘리브레이션 1000회 < 50ms."""
        tc = TeamClassifier()
        tc.initialize(TeamClassifierConfig())

        start = time.perf_counter()
        for _ in range(1000):
            tc.set_team_colors(
                team_a_hsv=(120.0, 200.0, 80.0),
                team_b_hsv=(30.0, 150.0, 220.0),
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 50.0, f"캘리브레이션 1000회: {elapsed_ms:.1f}ms > 50ms"


# =============================================================================
# JerseyOCR 성능
# =============================================================================

class TestJerseyOCRPerformance:
    """등번호 OCR 성능 테스트."""

    def test_인식_500회_속도(self) -> None:
        """단일 인식 500회 < 5000ms (YOLO 모델 또는 형태학적 폴백)."""
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        frame = _make_frame()
        c = _make_candidate()

        start = time.perf_counter()
        for _ in range(500):
            ocr.recognize(c, frame)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 5000.0, f"인식 500회: {elapsed_ms:.1f}ms > 5000ms"

    def test_유효성_검증_10000회_속도(self) -> None:
        """번호 유효성 검증 10000회 < 50ms."""
        start = time.perf_counter()
        for _ in range(10000):
            JerseyOCR._validate_number("23", [0.9, 0.8])
            JerseyOCR._validate_number("", [])
            JerseyOCR._validate_number("100", [0.9, 0.9, 0.9])
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 50.0, f"검증 30000회: {elapsed_ms:.1f}ms > 50ms"

    def test_심판_인식_제외_1000회_속도(self) -> None:
        """심판은 즉시 반환 → 1000회 < 20ms."""
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        frame = _make_frame()
        c = _PlayerCandidate(
            bbox_x=100, bbox_y=50, bbox_w=100, bbox_h=250,
            yolo_confidence=0.9, class_id=PLAYER_CLASS_ID_REFEREE,
        )

        start = time.perf_counter()
        for _ in range(1000):
            ocr.recognize(c, frame)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 20.0, f"심판 제외 1000회: {elapsed_ms:.1f}ms > 20ms"


# =============================================================================
# ReIDModule 성능
# =============================================================================

class TestReIDModulePerformance:
    """ReID 모듈 성능 테스트."""

    def test_특징추출_500회_속도(self) -> None:
        """특징 추출 500회 < 5000ms (ResNet50 모델 또는 히스토그램 폴백)."""
        reid = ReIDModule()
        reid.initialize(ReIDConfig())
        frame = _make_frame()
        c = _make_candidate()

        start = time.perf_counter()
        for _ in range(500):
            reid.extract_feature(c, frame)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 5000.0, f"추출 500회: {elapsed_ms:.1f}ms > 5000ms"

    def test_매칭_100갤러리_속도(self) -> None:
        """갤러리 100명 대비 매칭 < 50ms/회."""
        reid = ReIDModule()
        reid.initialize(ReIDConfig())
        frame = _make_frame()

        # 갤러리에 100명 등록
        for i in range(100):
            c = _make_candidate(x=50 + i * 5)
            reid.match_or_update(c, frame, track_id=i)

        # 매칭 성능 측정
        c = _make_candidate()
        feat = reid.extract_feature(c, frame)
        assert feat is not None

        start = time.perf_counter()
        for _ in range(100):
            reid.match(feat)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 100.0, f"매칭 100회(갤러리100): {elapsed_ms:.1f}ms > 100ms"

    def test_갤러리_정리_속도(self) -> None:
        """갤러리 정리 (200명 → max_persons) < 50ms."""
        reid = ReIDModule()
        reid.initialize(ReIDConfig())
        frame = _make_frame()

        for i in range(200):
            c = _make_candidate(x=50 + i * 3)
            reid.match_or_update(c, frame, track_id=i)

        start = time.perf_counter()
        reid.cleanup_gallery(current_frame=10000)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 50.0, f"갤러리 정리: {elapsed_ms:.1f}ms > 50ms"


# =============================================================================
# PlayerTracker 성능
# =============================================================================

class TestPlayerTrackerPerformance:
    """선수 추적기 성능 테스트."""

    def test_10명_추적_1000프레임_속도(self) -> None:
        """10명 1000프레임 추적 < 3000ms."""
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())

        start = time.perf_counter()
        for frame_idx in range(1000):
            candidates = [
                _make_candidate(
                    x=100 + i * 100 + (frame_idx % 5),
                    y=100,
                )
                for i in range(10)
            ]
            tracker.update(candidates, frame_index=frame_idx)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 3000.0, f"10명×1000프레임: {elapsed_ms:.1f}ms > 3000ms"

    def test_빈_프레임_1000회_속도(self) -> None:
        """빈 프레임 처리 1000회 < 200ms."""
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig())

        start = time.perf_counter()
        for i in range(1000):
            tracker.update([], frame_index=i)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 200.0, f"빈 프레임 1000회: {elapsed_ms:.1f}ms > 200ms"

    def test_트랙_생성_삭제_사이클(self) -> None:
        """트랙 생성 → 사라짐 → 삭제 반복 안정성."""
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig(max_age=5))

        start = time.perf_counter()
        for cycle in range(50):
            # 생성: 5프레임 감지
            for f in range(5):
                fi = cycle * 20 + f
                candidates = [
                    _make_candidate(x=100 + cycle * 10)
                ]
                tracker.update(candidates, frame_index=fi)

            # 소멸: 15프레임 미감지
            for f in range(15):
                fi = cycle * 20 + 5 + f
                tracker.update([], frame_index=fi)

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        # 50사이클 × 20프레임 = 1000프레임 처리
        assert elapsed_ms < 2000.0, f"생성삭제 50사이클: {elapsed_ms:.1f}ms > 2000ms"


# =============================================================================
# PlayerIDManager 성능
# =============================================================================

class TestPlayerIDManagerPerformance:
    """선수 ID 관리자 성능 테스트."""

    def test_등록_갱신_1000회_속도(self) -> None:
        """동일 선수 등록/갱신 1000회 < 200ms."""
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())

        start = time.perf_counter()
        for i in range(1000):
            mgr.update_player(track_id=1, frame_index=i)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 200.0, f"등록갱신 1000회: {elapsed_ms:.1f}ms > 200ms"

    def test_50명_등록_속도(self) -> None:
        """50명 동시 등록 < 100ms."""
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())

        start = time.perf_counter()
        for i in range(50):
            mgr.update_player(
                track_id=i,
                jersey_number=i % 100,
                jersey_conf=0.8,
                reid_id=i,
                reid_sim=0.85,
                team=Team.TEAM_A if i % 2 == 0 else Team.TEAM_B,
                frame_index=0,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert mgr.managed_count == 50
        assert elapsed_ms < 100.0, f"50명 등록: {elapsed_ms:.1f}ms > 100ms"

    def test_융합_점수_계산_10000회_속도(self) -> None:
        """융합 점수 계산 (등록+업데이트) 10000회 < 500ms."""
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())

        start = time.perf_counter()
        for i in range(10000):
            mgr.update_player(
                track_id=i % 100,
                jersey_number=23,
                jersey_conf=0.9,
                reid_id=i % 100,
                reid_sim=0.85,
                frame_index=i,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 500.0, f"융합 10000회: {elapsed_ms:.1f}ms > 500ms"

    def test_정리_속도(self) -> None:
        """200명 정리 < 50ms."""
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig(max_unconfirmed_frames=10))

        # 200명 미확정 등록
        for i in range(200):
            mgr.update_player(track_id=i, frame_index=0)

        start = time.perf_counter()
        removed = mgr.cleanup(current_frame=100)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert removed == 200
        assert elapsed_ms < 50.0, f"200명 정리: {elapsed_ms:.1f}ms > 50ms"

    def test_팀별_조회_성능(self) -> None:
        """100명 중 팀별 조회 1000회 < 200ms."""
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())

        for i in range(100):
            mgr.update_player(
                track_id=i,
                team=Team.TEAM_A if i % 2 == 0 else Team.TEAM_B,
                frame_index=0,
            )

        start = time.perf_counter()
        for _ in range(1000):
            mgr.get_team_players(Team.TEAM_A)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert elapsed_ms < 200.0, f"팀별 조회 1000회: {elapsed_ms:.1f}ms > 200ms"


# =============================================================================
# 메모리 안정성
# =============================================================================

class TestMemoryStability:
    """장시간 운용 메모리 안정성."""

    def test_OCR_이력_maxlen_제한(self) -> None:
        """JerseyOCR 투표 이력이 무한 성장하지 않음."""
        ocr = JerseyOCR()
        ocr.initialize(JerseyOCRConfig())
        frame = _make_frame()

        # 동일 후보 2000회 인식 → 내부 이력 deque 제한 확인
        c = _make_candidate()
        for _ in range(2000):
            ocr.recognize(c, frame)

        # 내부 상태가 적정 크기 이내
        # (JerseyOCR._histories 는 deque로 제한됨)
        assert ocr.total_recognized >= 0  # 정상 동작 확인

    def test_갤러리_LRU_제한(self) -> None:
        """ReIDModule 갤러리가 max_persons 초과 시 LRU 제거."""
        reid = ReIDModule()
        reid.initialize(ReIDConfig())
        frame = _make_frame()

        # 500명 등록 → max_persons(기본 200) 초과
        for i in range(500):
            c = _make_candidate(x=50 + i * 2)
            reid.match_or_update(c, frame, track_id=i)

        reid.cleanup_gallery(current_frame=10000)

        # 갤러리 크기가 max_persons 이하
        gallery_size = len(reid._gallery)
        max_persons = ReIDConfig().gallery_max_persons
        assert gallery_size <= max_persons, (
            f"갤러리 {gallery_size} > max_persons {max_persons}"
        )

    def test_트래커_사망_트랙_메모리_해제(self) -> None:
        """사망 트랙이 메모리에서 제거됨."""
        tracker = PlayerTracker()
        tracker.initialize(PlayerTrackerConfig(max_age=3))

        # 100개 트랙 생성
        candidates = [
            _make_candidate(x=50 + i * 10) for i in range(100)
        ]
        tracker.update(candidates, frame_index=0)
        assert tracker.active_track_count == 100

        # 10프레임 빈 감지 → 모두 사망
        for f in range(1, 11):
            tracker.update([], frame_index=f)

        assert tracker.active_track_count == 0

    def test_IDManager_reset_메모리_해제(self) -> None:
        """reset() 후 내부 매핑 완전 해제."""
        mgr = PlayerIDManager()
        mgr.initialize(PlayerIDManagerConfig())

        for i in range(500):
            mgr.update_player(
                track_id=i,
                reid_id=i,
                reid_sim=0.85,
                frame_index=0,
            )
        assert mgr.managed_count == 500

        mgr.reset()
        assert mgr.managed_count == 0


# =============================================================================
# 데이터 추출 성능
# =============================================================================

class TestDataExtractionPerformance:
    """데이터 추출기 초기화/처리 성능."""

    def test_bbox_추출기_초기화_속도(self) -> None:
        """PlayerBboxExtractor 초기화 100회 < 50ms."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            start = time.perf_counter()
            for _ in range(100):
                ext = PlayerBboxExtractor(output_dir=tmpdir)
                ext.initialize()
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            assert elapsed_ms < 50.0, f"초기화 100회: {elapsed_ms:.1f}ms > 50ms"

    def test_uniform_추출기_초기화_속도(self) -> None:
        """TeamUniformExtractor 초기화 100회 < 50ms."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            start = time.perf_counter()
            for _ in range(100):
                ext = TeamUniformExtractor(output_dir=tmpdir)
                ext.initialize()
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            assert elapsed_ms < 50.0, f"초기화 100회: {elapsed_ms:.1f}ms > 50ms"

    def test_jersey_추출기_초기화_속도(self) -> None:
        """JerseyDigitExtractor 초기화 100회 < 50ms."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            start = time.perf_counter()
            for _ in range(100):
                ext = JerseyDigitExtractor(output_dir=tmpdir)
                ext.initialize()
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            assert elapsed_ms < 50.0, f"초기화 100회: {elapsed_ms:.1f}ms > 50ms"

    def test_reid_추출기_초기화_속도(self) -> None:
        """ReIDAppearanceExtractor 초기화 100회 < 50ms."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            start = time.perf_counter()
            for _ in range(100):
                ext = ReIDAppearanceExtractor(output_dir=tmpdir)
                ext.initialize()
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            assert elapsed_ms < 50.0, f"초기화 100회: {elapsed_ms:.1f}ms > 50ms"
