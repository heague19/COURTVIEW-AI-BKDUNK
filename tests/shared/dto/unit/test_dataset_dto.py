# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_dataset_dto.py

데이터셋 DTO 유닛 테스트
- 모듈 구조 검증 (__all__, typing, 버전)
- Enum 클래스 (DatasetType, DatasetSplit, UploadStatus)
- 데이터클래스 (ShotTrajectoryRecord, PlayerBboxRecord, CourtLineRecord,
  FoulSceneRecord, FrameRecord, PossessionRecord, GameDataRecord,
  DatasetMetadata, ExtractionResult)
- 프로퍼티 검증

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from pathlib import Path
from uuid import UUID

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. 모듈 구조 검증 ====================
def test_module_import(r: TestResult) -> None:
    """모듈 임포트 성공 여부"""
    try:
        import shared.dto.dataset_dto as mod
        assert hasattr(mod, "__all__")
        assert hasattr(mod, "__version__")
        r.ok("모듈 임포트")
    except Exception as e:
        r.fail("모듈 임포트", str(e))


def test_all_exports(r: TestResult) -> None:
    """__all__ 13개 export 검증"""
    from shared.dto.dataset_dto import __all__
    expected = {
        "DatasetType", "DatasetSplit", "UploadStatus",
        "ShotTrajectoryRecord", "PlayerBboxRecord", "CourtLineRecord", "FoulSceneRecord",
        "FrameRecord", "PossessionRecord", "GameDataRecord",
        "DatasetMetadata", "ExtractionResult",
    }
    actual = set(__all__)
    if actual == expected:
        r.ok(f"__all__ = {len(actual)}개")
    else:
        missing = expected - actual
        extra = actual - expected
        r.fail("__all__", f"missing={missing}, extra={extra}")


def test_version(r: TestResult) -> None:
    """버전 1.1.0 확인"""
    from shared.dto.dataset_dto import __version__
    if __version__ == "1.1.0":
        r.ok("__version__ = 1.1.0")
    else:
        r.fail("__version__", f"expected 1.1.0, got {__version__}")


def test_no_legacy_typing(r: TestResult) -> None:
    """Dict/List/Tuple 레거시 typing 미사용 확인"""
    import re
    src = Path(_PROJECT_ROOT / "shared" / "dto" / "dataset_dto.py").read_text(encoding="utf-8")
    hits = re.findall(r'\b(Dict\[|List\[|Tuple\[)', src)
    if not hits:
        r.ok("레거시 typing 미사용")
    else:
        r.fail("레거시 typing", f"{len(hits)}건 발견")


# ==================== 2. DatasetType Enum ====================
def test_dataset_type_members(r: TestResult) -> None:
    """DatasetType 7개 멤버"""
    from shared.dto.dataset_dto import DatasetType
    expected = {
        "SHOT_TRAJECTORY", "PLAYER_BBOX", "COURT_LINE", "FOUL_SCENE",
        "FRAME_RECORD", "POSSESSION_RECORD", "GAME_RECORD",
    }
    actual = {m.name for m in DatasetType}
    if actual == expected:
        r.ok(f"DatasetType 멤버 {len(actual)}개")
    else:
        r.fail("DatasetType 멤버", f"expected={expected}, actual={actual}")


def test_dataset_type_str(r: TestResult) -> None:
    """DatasetType.__str__ → value"""
    from shared.dto.dataset_dto import DatasetType
    assert str(DatasetType.SHOT_TRAJECTORY) == "shot_trajectory"
    assert str(DatasetType.GAME_RECORD) == "game_record"
    r.ok("DatasetType __str__")


# ==================== 3. DatasetSplit Enum ====================
def test_dataset_split_members(r: TestResult) -> None:
    """DatasetSplit 3개 멤버"""
    from shared.dto.dataset_dto import DatasetSplit
    expected = {"TRAIN", "VALIDATION", "TEST"}
    actual = {m.name for m in DatasetSplit}
    if actual == expected:
        r.ok(f"DatasetSplit 멤버 {len(actual)}개")
    else:
        r.fail("DatasetSplit 멤버", f"expected={expected}, actual={actual}")


def test_dataset_split_str(r: TestResult) -> None:
    """DatasetSplit.__str__ → value"""
    from shared.dto.dataset_dto import DatasetSplit
    assert str(DatasetSplit.TRAIN) == "train"
    assert str(DatasetSplit.VALIDATION) == "validation"
    assert str(DatasetSplit.TEST) == "test"
    r.ok("DatasetSplit __str__")


# ==================== 4. UploadStatus Enum ====================
def test_upload_status_members(r: TestResult) -> None:
    """UploadStatus 4개 멤버"""
    from shared.dto.dataset_dto import UploadStatus
    expected = {"PENDING", "UPLOADING", "COMPLETED", "FAILED"}
    actual = {m.name for m in UploadStatus}
    if actual == expected:
        r.ok(f"UploadStatus 멤버 {len(actual)}개")
    else:
        r.fail("UploadStatus 멤버", f"expected={expected}, actual={actual}")


def test_upload_status_is_terminal(r: TestResult) -> None:
    """UploadStatus.is_terminal 프로퍼티"""
    from shared.dto.dataset_dto import UploadStatus
    assert UploadStatus.COMPLETED.is_terminal is True
    assert UploadStatus.FAILED.is_terminal is True
    assert UploadStatus.PENDING.is_terminal is False
    assert UploadStatus.UPLOADING.is_terminal is False
    r.ok("UploadStatus is_terminal")


def test_upload_status_is_uploaded(r: TestResult) -> None:
    """UploadStatus.is_uploaded 프로퍼티"""
    from shared.dto.dataset_dto import UploadStatus
    assert UploadStatus.COMPLETED.is_uploaded is True
    assert UploadStatus.FAILED.is_uploaded is False
    assert UploadStatus.PENDING.is_uploaded is False
    r.ok("UploadStatus is_uploaded")


# ==================== 5. ShotTrajectoryRecord ====================
def test_shot_trajectory_record(r: TestResult) -> None:
    """ShotTrajectoryRecord 기본값 및 데이터 설정"""
    from shared.dto.dataset_dto import ShotTrajectoryRecord
    # 기본값
    rec = ShotTrajectoryRecord()
    assert rec.trajectory_points == []
    assert rec.ball_detected is True
    assert rec.shot_result is None
    assert rec.frame_indices == []
    assert rec.camera_id == ""
    # 데이터 설정
    rec2 = ShotTrajectoryRecord(
        trajectory_points=[(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)],
        ball_detected=True,
        shot_result="made",
        frame_indices=[10, 11, 12],
        camera_id="cam_01",
    )
    assert len(rec2.trajectory_points) == 2
    assert rec2.trajectory_points[0] == (1.0, 2.0, 3.0)
    assert rec2.frame_indices == [10, 11, 12]
    r.ok("ShotTrajectoryRecord")


# ==================== 6. PlayerBboxRecord ====================
def test_player_bbox_record(r: TestResult) -> None:
    """PlayerBboxRecord 기본값 및 데이터 설정"""
    from shared.dto.dataset_dto import PlayerBboxRecord
    rec = PlayerBboxRecord()
    assert rec.bbox == (0.0, 0.0, 0.0, 0.0)
    assert rec.class_label == "player"
    assert rec.team_id is None
    assert rec.confidence == 0.0
    # 데이터 설정
    rec2 = PlayerBboxRecord(
        bbox=(0.1, 0.2, 0.3, 0.4),
        class_label="referee",
        confidence=0.95,
        frame_index=100,
    )
    assert rec2.bbox == (0.1, 0.2, 0.3, 0.4)
    assert rec2.class_label == "referee"
    assert rec2.confidence == 0.95
    r.ok("PlayerBboxRecord")


# ==================== 7. CourtLineRecord ====================
def test_court_line_record(r: TestResult) -> None:
    """CourtLineRecord 기본값 및 데이터 설정"""
    from shared.dto.dataset_dto import CourtLineRecord
    rec = CourtLineRecord()
    assert rec.line_points == []
    assert rec.line_type == ""
    # 데이터 설정
    rec2 = CourtLineRecord(
        line_points=[(0.0, 0.5), (1.0, 0.5)],
        line_type="baseline",
        frame_index=50,
        camera_id="cam_02",
    )
    assert len(rec2.line_points) == 2
    assert rec2.line_type == "baseline"
    r.ok("CourtLineRecord")


# ==================== 8. FoulSceneRecord ====================
def test_foul_scene_record(r: TestResult) -> None:
    """FoulSceneRecord 기본값 및 데이터 설정"""
    from shared.dto.dataset_dto import FoulSceneRecord
    rec = FoulSceneRecord()
    assert rec.contact_frames == []
    assert rec.player_positions == {}
    assert rec.foul_type == ""
    assert rec.severity == ""
    assert rec.is_correct_call is True
    # 데이터 설정
    rec2 = FoulSceneRecord(
        contact_frames=[100, 101, 102],
        player_positions={1: (0.5, 0.3), 2: (0.6, 0.4)},
        foul_type="blocking",
        severity="moderate",
        referee_call="personal_foul",
        is_correct_call=False,
    )
    assert len(rec2.contact_frames) == 3
    assert rec2.player_positions[1] == (0.5, 0.3)
    assert rec2.is_correct_call is False
    r.ok("FoulSceneRecord")


# ==================== 9. FrameRecord ====================
def test_frame_record(r: TestResult) -> None:
    """FrameRecord 기본값 및 데이터 설정"""
    from shared.dto.dataset_dto import FrameRecord
    rec = FrameRecord()
    assert rec.frame_index == 0
    assert rec.player_positions == []
    assert rec.keypoints == []
    assert rec.ball_position is None
    assert rec.actions == []
    assert rec.events == []
    # 데이터 설정
    rec2 = FrameRecord(
        frame_index=200,
        camera_id="cam_01",
        player_positions=[(1, 0.5, 0.3), (2, 0.6, 0.4)],
        ball_position=(0.55, 0.35),
    )
    assert len(rec2.player_positions) == 2
    assert rec2.ball_position == (0.55, 0.35)
    r.ok("FrameRecord")


# ==================== 10. PossessionRecord ====================
def test_possession_record(r: TestResult) -> None:
    """PossessionRecord 기본값 및 UUID"""
    from shared.dto.dataset_dto import PossessionRecord
    rec = PossessionRecord()
    assert isinstance(rec.possession_id, UUID)
    assert rec.team_id == ""
    assert rec.start_frame == 0
    assert rec.end_frame == 0
    assert rec.tactical_label == ""
    assert rec.defensive_label == ""
    assert rec.result_label == ""
    assert rec.points_scored == 0
    # 데이터 설정
    rec2 = PossessionRecord(
        team_id="team_a",
        start_frame=100,
        end_frame=300,
        frame_count=200,
        tactical_label="PnR",
        defensive_label="MAN",
        result_label="made",
        points_scored=2,
    )
    assert rec2.frame_count == 200
    assert rec2.tactical_label == "PnR"
    r.ok("PossessionRecord")


# ==================== 11. GameDataRecord ====================
def test_game_data_record(r: TestResult) -> None:
    """GameDataRecord 기본값 및 데이터 설정"""
    from shared.dto.dataset_dto import GameDataRecord
    rec = GameDataRecord()
    assert rec.game_id == ""
    assert rec.team_style_metrics == {}
    assert rec.lineup_data == []
    assert rec.momentum_curve == []
    assert rec.final_score == (0, 0)
    assert rec.total_possessions == 0
    # 데이터 설정
    rec2 = GameDataRecord(
        game_id="game_001",
        date="2026-02-16",
        team_style_metrics={"pace": 95.2, "three_rate": 0.35},
        final_score=(85, 78),
        total_possessions=90,
    )
    assert rec2.team_style_metrics["pace"] == 95.2
    assert rec2.final_score == (85, 78)
    r.ok("GameDataRecord")


# ==================== 12. DatasetMetadata ====================
def test_dataset_metadata_defaults(r: TestResult) -> None:
    """DatasetMetadata 기본값 및 UUID"""
    from shared.dto.dataset_dto import DatasetMetadata, DatasetType, DatasetSplit
    from datetime import datetime
    meta = DatasetMetadata()
    assert isinstance(meta.dataset_id, UUID)
    assert meta.dataset_type == DatasetType.FRAME_RECORD
    assert meta.version == "1.0.0"
    assert meta.total_records == 0
    assert meta.split == DatasetSplit.TRAIN
    assert isinstance(meta.created_at, datetime)
    assert meta.source_game_ids == []
    assert meta.description == ""
    r.ok("DatasetMetadata 기본값")


def test_dataset_metadata_custom(r: TestResult) -> None:
    """DatasetMetadata 커스텀 값"""
    from shared.dto.dataset_dto import DatasetMetadata, DatasetType, DatasetSplit
    meta = DatasetMetadata(
        dataset_type=DatasetType.SHOT_TRAJECTORY,
        version="2.0.0",
        total_records=5000,
        split=DatasetSplit.VALIDATION,
        source_game_ids=["game_001", "game_002"],
        description="슛 궤적 학습 데이터",
    )
    assert meta.dataset_type == DatasetType.SHOT_TRAJECTORY
    assert meta.total_records == 5000
    assert meta.split == DatasetSplit.VALIDATION
    assert len(meta.source_game_ids) == 2
    r.ok("DatasetMetadata 커스텀 값")


# ==================== 13. ExtractionResult ====================
def test_extraction_result_defaults(r: TestResult) -> None:
    """ExtractionResult 기본값"""
    from shared.dto.dataset_dto import ExtractionResult, UploadStatus
    from datetime import datetime
    res = ExtractionResult()
    assert isinstance(res.extraction_id, UUID)
    assert res.game_id == ""
    assert res.metadata is None
    assert res.record_count == 0
    assert res.file_path == ""
    assert res.file_size_bytes == 0
    assert res.s3_bucket == ""
    assert res.s3_key == ""
    assert res.upload_status == UploadStatus.PENDING
    assert res.upload_error is None
    assert res.uploaded_at is None
    assert isinstance(res.created_at, datetime)
    r.ok("ExtractionResult 기본값")


def test_extraction_result_s3_uri_completed(r: TestResult) -> None:
    """ExtractionResult.s3_uri - 업로드 완료 시"""
    from shared.dto.dataset_dto import ExtractionResult, UploadStatus
    res = ExtractionResult(
        s3_bucket="courtview-datasets",
        s3_key="training/shot_trajectory/2026-02-16.parquet",
        upload_status=UploadStatus.COMPLETED,
    )
    expected = "s3://courtview-datasets/training/shot_trajectory/2026-02-16.parquet"
    assert res.s3_uri == expected
    r.ok("ExtractionResult s3_uri (COMPLETED)")


def test_extraction_result_s3_uri_pending(r: TestResult) -> None:
    """ExtractionResult.s3_uri - 업로드 미완료 시 None"""
    from shared.dto.dataset_dto import ExtractionResult, UploadStatus
    # PENDING → None
    res1 = ExtractionResult(upload_status=UploadStatus.PENDING)
    assert res1.s3_uri is None
    # FAILED → None
    res2 = ExtractionResult(
        s3_bucket="bucket",
        s3_key="key",
        upload_status=UploadStatus.FAILED,
    )
    assert res2.s3_uri is None
    r.ok("ExtractionResult s3_uri (PENDING/FAILED → None)")


def test_extraction_result_s3_uri_empty_bucket(r: TestResult) -> None:
    """ExtractionResult.s3_uri - bucket/key 비어있으면 None"""
    from shared.dto.dataset_dto import ExtractionResult, UploadStatus
    res = ExtractionResult(
        s3_bucket="",
        s3_key="",
        upload_status=UploadStatus.COMPLETED,
    )
    assert res.s3_uri is None
    r.ok("ExtractionResult s3_uri (빈 bucket → None)")


def test_extraction_result_with_metadata(r: TestResult) -> None:
    """ExtractionResult + DatasetMetadata 연결"""
    from shared.dto.dataset_dto import ExtractionResult, DatasetMetadata, DatasetType
    meta = DatasetMetadata(
        dataset_type=DatasetType.FOUL_SCENE,
        total_records=150,
    )
    res = ExtractionResult(
        game_id="game_001",
        metadata=meta,
        record_count=150,
        file_path="/data/foul_scenes.parquet",
        file_size_bytes=1024000,
    )
    assert res.metadata is not None
    assert res.metadata.dataset_type == DatasetType.FOUL_SCENE
    assert res.record_count == 150
    r.ok("ExtractionResult + DatasetMetadata 연결")


# ==================== 14. UUID 고유성 ====================
def test_uuid_uniqueness(r: TestResult) -> None:
    """UUID 고유성 (ExtractionResult, DatasetMetadata, PossessionRecord)"""
    from shared.dto.dataset_dto import ExtractionResult, DatasetMetadata, PossessionRecord
    ext_ids = {ExtractionResult().extraction_id for _ in range(100)}
    meta_ids = {DatasetMetadata().dataset_id for _ in range(100)}
    poss_ids = {PossessionRecord().possession_id for _ in range(100)}
    assert len(ext_ids) == 100
    assert len(meta_ids) == 100
    assert len(poss_ids) == 100
    r.ok("UUID 고유성 (3종 × 100개)")


# ==================== 15. 리스트/딕트 독립성 ====================
def test_mutable_default_independence(r: TestResult) -> None:
    """field(default_factory=...) 인스턴스 독립성"""
    from shared.dto.dataset_dto import ShotTrajectoryRecord, FoulSceneRecord
    a = ShotTrajectoryRecord()
    b = ShotTrajectoryRecord()
    a.trajectory_points.append((1.0, 2.0, 3.0))
    assert len(b.trajectory_points) == 0  # b에 영향 없음

    c = FoulSceneRecord()
    d = FoulSceneRecord()
    c.contact_frames.append(100)
    assert len(d.contact_frames) == 0
    r.ok("mutable default 독립성")


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("dataset_dto.py v1.1.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_import(r)
    test_all_exports(r)
    test_version(r)
    test_no_legacy_typing(r)

    print("\n--- DatasetType ---")
    test_dataset_type_members(r)
    test_dataset_type_str(r)

    print("\n--- DatasetSplit ---")
    test_dataset_split_members(r)
    test_dataset_split_str(r)

    print("\n--- UploadStatus ---")
    test_upload_status_members(r)
    test_upload_status_is_terminal(r)
    test_upload_status_is_uploaded(r)

    print("\n--- ShotTrajectoryRecord ---")
    test_shot_trajectory_record(r)

    print("\n--- PlayerBboxRecord ---")
    test_player_bbox_record(r)

    print("\n--- CourtLineRecord ---")
    test_court_line_record(r)

    print("\n--- FoulSceneRecord ---")
    test_foul_scene_record(r)

    print("\n--- FrameRecord ---")
    test_frame_record(r)

    print("\n--- PossessionRecord ---")
    test_possession_record(r)

    print("\n--- GameDataRecord ---")
    test_game_data_record(r)

    print("\n--- DatasetMetadata ---")
    test_dataset_metadata_defaults(r)
    test_dataset_metadata_custom(r)

    print("\n--- ExtractionResult ---")
    test_extraction_result_defaults(r)
    test_extraction_result_s3_uri_completed(r)
    test_extraction_result_s3_uri_pending(r)
    test_extraction_result_s3_uri_empty_bucket(r)
    test_extraction_result_with_metadata(r)

    print("\n--- UUID / 독립성 ---")
    test_uuid_uniqueness(r)
    test_mutable_default_independence(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
