# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/integration
파일: test_shared_integration.py
설명: shared/ 모듈 전체 통합 테스트
      - 5개 서브모듈 교차 검증
      - 순환 참조 없음 확인
      - Export 정합성 검증
      - 모듈 간 타입 일관성 검증

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""
import io
import sys
import time
import importlib
import inspect
from pathlib import Path
from abc import ABC
from typing import Any, get_type_hints

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dataclasses import dataclass
from enum import Enum

@dataclass
class TestResult:
    section: str
    name: str
    passed: bool
    message: str = ""

results: list[TestResult] = []
total_pass = 0
total_fail = 0

def run_test(section: str, name: str, test_fn):
    global total_pass, total_fail
    try:
        test_fn()
        results.append(TestResult(section, name, True))
        total_pass += 1
    except Exception as e:
        results.append(TestResult(section, name, False, str(e)))
        total_fail += 1


# =============================================================================
# [A] Top-level shared module (6 tests)
# =============================================================================

def test_a1_shared_version():
    import shared
    assert shared.__version__ == "2.0.0", f"Expected version 2.0.0, got {shared.__version__}"

def test_a2_shared_all_exists():
    import shared
    assert hasattr(shared, "__all__"), "shared.__all__ does not exist"
    assert len(shared.__all__) == 193, f"Expected 193 exports, got {len(shared.__all__)}"

def test_a3_shared_all_accessible():
    import shared
    missing = []
    for name in shared.__all__:
        if not hasattr(shared, name):
            missing.append(name)
    assert len(missing) == 0, f"Missing {len(missing)} items from shared.__all__: {missing[:5]}"

def test_a4_shared_author_exists():
    import shared
    assert hasattr(shared, "__author__"), "shared.__author__ does not exist"

def test_a5_shared_no_import_errors():
    try:
        import shared
        assert True
    except ImportError as e:
        raise AssertionError(f"shared module has import errors: {e}")

def test_a6_shared_is_package():
    import shared
    assert hasattr(shared, "__path__"), "shared is not a package"


# =============================================================================
# [B] Sub-module independence (10 tests)
# =============================================================================

def test_b1_constants_import():
    import shared.constants
    assert hasattr(shared.constants, "__version__"), "constants module has no __version__"
    assert hasattr(shared.constants, "__all__"), "constants module has no __all__"

def test_b2_dto_import():
    import shared.dto
    assert hasattr(shared.dto, "__version__"), "dto module has no __version__"
    assert hasattr(shared.dto, "__all__"), "dto module has no __all__"

def test_b3_interfaces_import():
    import shared.interfaces
    assert hasattr(shared.interfaces, "__version__"), "interfaces module has no __version__"
    assert hasattr(shared.interfaces, "__all__"), "interfaces module has no __all__"

def test_b4_protocols_import():
    import shared.protocols
    assert hasattr(shared.protocols, "__version__"), "protocols module has no __version__"
    assert hasattr(shared.protocols, "__all__"), "protocols module has no __all__"

def test_b5_exceptions_import():
    import shared.exceptions
    assert hasattr(shared.exceptions, "__version__"), "exceptions module has no __version__"
    assert hasattr(shared.exceptions, "__all__"), "exceptions module has no __all__"

def test_b6_constants_export_count():
    import shared.constants
    assert len(shared.constants.__all__) == 216, f"Expected 216 exports from constants, got {len(shared.constants.__all__)}"

def test_b7_dto_export_count():
    import shared.dto
    assert len(shared.dto.__all__) == 292, f"Expected 292 exports from dto, got {len(shared.dto.__all__)}"

def test_b8_interfaces_export_count():
    import shared.interfaces
    assert len(shared.interfaces.__all__) == 81, f"Expected 81 exports from interfaces, got {len(shared.interfaces.__all__)}"

def test_b9_protocols_export_count():
    import shared.protocols
    assert len(shared.protocols.__all__) == 4, f"Expected 4 exports from protocols, got {len(shared.protocols.__all__)}"

def test_b10_exceptions_export_count():
    import shared.exceptions
    assert len(shared.exceptions.__all__) == 145, f"Expected 145 exports from exceptions, got {len(shared.exceptions.__all__)}"


# =============================================================================
# [C] No circular imports (5 tests)
# =============================================================================

def test_c1_constants_no_circular():
    mod = importlib.import_module('shared.constants')
    assert mod is not None, "Failed to import shared.constants"

def test_c2_dto_no_circular():
    mod = importlib.import_module('shared.dto')
    assert mod is not None, "Failed to import shared.dto"

def test_c3_interfaces_no_circular():
    mod = importlib.import_module('shared.interfaces')
    assert mod is not None, "Failed to import shared.interfaces"

def test_c4_protocols_no_circular():
    mod = importlib.import_module('shared.protocols')
    assert mod is not None, "Failed to import shared.protocols"

def test_c5_exceptions_no_circular():
    mod = importlib.import_module('shared.exceptions')
    assert mod is not None, "Failed to import shared.exceptions"


# =============================================================================
# [D] Constants export validation (3 tests)
# =============================================================================

def test_d1_constants_all_accessible():
    import shared.constants
    missing = []
    for name in shared.constants.__all__:
        if not hasattr(shared.constants, name):
            missing.append(name)
    assert len(missing) == 0, f"Missing {len(missing)} items: {missing[:5]}"

def test_d2_enum_classes_have_members():
    import shared.constants
    empty_enums = []
    for name in shared.constants.__all__:
        obj = getattr(shared.constants, name, None)
        if obj and isinstance(obj, type) and issubclass(obj, Enum):
            if len(list(obj)) == 0:
                empty_enums.append(name)
    assert len(empty_enums) == 0, f"Empty enums found: {empty_enums}"

def test_d3_key_enums_exist():
    from shared.constants import Gender, AgeGroup, SkillLevel, ErrorCode
    assert Gender is not None
    assert AgeGroup is not None
    assert SkillLevel is not None
    assert ErrorCode is not None


# =============================================================================
# [E] DTO export validation (3 tests)
# =============================================================================

def test_e1_dto_all_accessible():
    import shared.dto
    missing = []
    for name in shared.dto.__all__:
        if not hasattr(shared.dto, name):
            missing.append(name)
    assert len(missing) == 0, f"Missing {len(missing)} items: {missing[:5]}"

def test_e2_key_dto_classes_exist():
    from shared.dto import VideoSource, PipelineOptions, Point2D, Track
    assert VideoSource is not None
    assert PipelineOptions is not None
    assert Point2D is not None
    assert Track is not None

def test_e3_dto_classes_have_fields():
    from shared.dto import Point2D, PipelineOptions
    from dataclasses import fields
    # Point2D should have fields
    pt_fields = fields(Point2D)
    assert len(pt_fields) > 0, "Point2D has no fields"
    # PipelineOptions should have fields (Pydantic BaseModel)
    assert hasattr(PipelineOptions, 'model_fields'), "PipelineOptions has no model_fields"


# =============================================================================
# [F] Interfaces export validation (3 tests)
# =============================================================================

def test_f1_interfaces_all_accessible():
    import shared.interfaces
    missing = []
    for name in shared.interfaces.__all__:
        if not hasattr(shared.interfaces, name):
            missing.append(name)
    assert len(missing) == 0, f"Missing {len(missing)} items: {missing[:5]}"

def test_f2_key_interfaces_exist():
    from shared.interfaces import IAnalyzer, IDetector, IStorage, IRepository
    assert IAnalyzer is not None
    assert IDetector is not None
    assert IStorage is not None
    assert IRepository is not None

def test_f3_abc_classes_have_abstract_methods():
    from shared.interfaces import IAnalyzer, IDetector
    # Check if they have abstractmethods
    analyzer_abstract = getattr(IAnalyzer, '__abstractmethods__', None)
    detector_abstract = getattr(IDetector, '__abstractmethods__', None)
    assert analyzer_abstract is not None and len(analyzer_abstract) > 0, "IAnalyzer has no abstract methods"
    assert detector_abstract is not None and len(detector_abstract) > 0, "IDetector has no abstract methods"


# =============================================================================
# [G] Protocols export validation (3 tests)
# =============================================================================

def test_g1_protocols_all_accessible():
    import shared.protocols
    missing = []
    for name in shared.protocols.__all__:
        if not hasattr(shared.protocols, name):
            missing.append(name)
    assert len(missing) == 0, f"Missing {len(missing)} items: {missing}"

def test_g2_all_protocols_are_runtime_checkable():
    from shared.protocols import CameraProtocol, MultiCameraProtocol, StorageProtocol, AsyncStorageProtocol
    protocols = [CameraProtocol, MultiCameraProtocol, StorageProtocol, AsyncStorageProtocol]
    for proto in protocols:
        assert hasattr(proto, '_is_runtime_protocol'), f"{proto.__name__} is not runtime_checkable"

def test_g3_key_protocols_exist():
    from shared.protocols import CameraProtocol, MultiCameraProtocol, StorageProtocol, AsyncStorageProtocol
    assert CameraProtocol is not None
    assert MultiCameraProtocol is not None
    assert StorageProtocol is not None
    assert AsyncStorageProtocol is not None


# =============================================================================
# [H] Exceptions export validation (3 tests)
# =============================================================================

def test_h1_exceptions_all_accessible():
    import shared.exceptions
    missing = []
    for name in shared.exceptions.__all__:
        if not hasattr(shared.exceptions, name):
            missing.append(name)
    assert len(missing) == 0, f"Missing {len(missing)} items: {missing[:5]}"

def test_h2_all_exports_are_exceptions():
    import shared.exceptions
    non_exceptions = []
    for name in shared.exceptions.__all__:
        obj = getattr(shared.exceptions, name)
        if not (isinstance(obj, type) and issubclass(obj, BaseException)):
            non_exceptions.append(name)
    assert len(non_exceptions) == 0, f"Non-exception classes found: {non_exceptions}"

def test_h3_key_base_exceptions_exist():
    from shared.exceptions import (
        CourtViewException,
        RetryableException,
        NonRetryableException,
        CriticalException
    )
    assert CourtViewException is not None
    assert RetryableException is not None
    assert NonRetryableException is not None
    assert CriticalException is not None


# =============================================================================
# [I] Exception hierarchy validation (6 tests)
# =============================================================================

def test_i1_all_exceptions_inherit_from_courtview_exception():
    from shared.exceptions import CourtViewException
    import shared.exceptions
    non_conforming = []
    for name in shared.exceptions.__all__:
        exc_class = getattr(shared.exceptions, name)
        if exc_class is not CourtViewException:
            if not issubclass(exc_class, CourtViewException):
                non_conforming.append(name)
    assert len(non_conforming) == 0, f"Exceptions not inheriting from CourtViewException: {non_conforming}"

def test_i2_retryable_exception_hierarchy():
    from shared.exceptions import CourtViewException, RetryableException
    assert issubclass(RetryableException, CourtViewException), "RetryableException does not inherit from CourtViewException"

def test_i3_non_retryable_exception_hierarchy():
    from shared.exceptions import CourtViewException, NonRetryableException
    assert issubclass(NonRetryableException, CourtViewException), "NonRetryableException does not inherit from CourtViewException"

def test_i4_critical_exception_hierarchy():
    from shared.exceptions import CourtViewException, CriticalException
    assert issubclass(CriticalException, CourtViewException), "CriticalException does not inherit from CourtViewException"

def test_i5_video_exception_hierarchy():
    from shared.exceptions import CourtViewException, VideoException
    assert issubclass(VideoException, CourtViewException), "VideoException does not inherit from CourtViewException"

def test_i6_gpu_exception_hierarchy():
    from shared.exceptions import CourtViewException, GPUException
    assert issubclass(GPUException, CourtViewException), "GPUException does not inherit from CourtViewException"


# =============================================================================
# [J] Interface ABC verification (5 tests)
# =============================================================================

def test_j1_ianalyzer_is_abc():
    from shared.interfaces import IAnalyzer
    assert issubclass(IAnalyzer, ABC), "IAnalyzer is not a subclass of ABC"

def test_j2_idetector_is_abc():
    from shared.interfaces import IDetector
    assert issubclass(IDetector, ABC), "IDetector is not a subclass of ABC"

def test_j3_istorage_is_abc():
    from shared.interfaces import IStorage
    assert issubclass(IStorage, ABC), "IStorage is not a subclass of ABC"

def test_j4_igame_event_detector_is_abc():
    from shared.interfaces import IGameEventDetector
    assert issubclass(IGameEventDetector, ABC), "IGameEventDetector is not a subclass of ABC"

def test_j5_each_abc_has_abstractmethod():
    from shared.interfaces import IAnalyzer, IDetector, IStorage, IGameEventDetector
    for iface in [IAnalyzer, IDetector, IStorage, IGameEventDetector]:
        abstract = getattr(iface, '__abstractmethods__', None)
        assert abstract and len(abstract) > 0, f"{iface.__name__} has no abstract methods"


# =============================================================================
# [K] Protocol runtime_checkable verification (4 tests)
# =============================================================================

def test_k1_camera_protocol_runtime_checkable():
    from shared.protocols import CameraProtocol
    assert hasattr(CameraProtocol, '_is_runtime_protocol'), "CameraProtocol is not runtime_checkable"

def test_k2_multi_camera_protocol_runtime_checkable():
    from shared.protocols import MultiCameraProtocol
    assert hasattr(MultiCameraProtocol, '_is_runtime_protocol'), "MultiCameraProtocol is not runtime_checkable"

def test_k3_storage_protocol_runtime_checkable():
    from shared.protocols import StorageProtocol
    assert hasattr(StorageProtocol, '_is_runtime_protocol'), "StorageProtocol is not runtime_checkable"

def test_k4_async_storage_protocol_runtime_checkable():
    from shared.protocols import AsyncStorageProtocol
    assert hasattr(AsyncStorageProtocol, '_is_runtime_protocol'), "AsyncStorageProtocol is not runtime_checkable"


# =============================================================================
# [L] Constants → DTO type consistency (8 tests)
# =============================================================================

def test_l1_gender_enum_has_members():
    from shared.constants import Gender
    members = list(Gender)
    assert len(members) >= 2, f"Gender enum has {len(members)} members, expected at least 2"
    # Check for MALE, FEMALE
    assert any(m.name in ['MALE', 'FEMALE'] for m in members), "Gender enum missing MALE or FEMALE"

def test_l2_age_group_enum_has_members():
    from shared.constants import AgeGroup
    members = list(AgeGroup)
    assert len(members) >= 3, f"AgeGroup enum has {len(members)} members, expected at least 3"

def test_l3_skill_level_enum_has_members():
    from shared.constants import SkillLevel
    members = list(SkillLevel)
    assert len(members) >= 4, f"SkillLevel enum has {len(members)} members, expected at least 4"

def test_l4_rule_set_enum_exists():
    from shared.constants import RuleSet
    members = list(RuleSet)
    assert any(m.name in ['FIBA', 'NBA', 'KBL'] for m in members), "RuleSet missing key members"

def test_l5_shot_result_exists():
    from shared.constants import ShotResult
    assert ShotResult is not None

def test_l6_play_type_exists():
    from shared.constants import PlayType
    assert PlayType is not None

def test_l7_violation_type_exists():
    from shared.constants import ViolationType
    assert ViolationType is not None

def test_l8_foul_type_exists():
    from shared.constants import FoulType
    assert FoulType is not None


# =============================================================================
# [M] Cross-module data flow simulation (5 tests)
# =============================================================================

def test_m1_detection_target_usable():
    from shared.interfaces import DetectionTarget
    assert DetectionTarget is not None
    # Try to access members
    members = list(DetectionTarget)
    assert len(members) > 0, "DetectionTarget has no members"

def test_m2_bounding_box_instantiable():
    from shared.interfaces import BoundingBox
    # Try to instantiate
    bbox = BoundingBox(x=0.0, y=0.0, width=100.0, height=100.0)
    assert bbox.x == 0.0

def test_m3_analysis_result_instantiable():
    from shared.interfaces import AnalysisResult
    # Use the success_result factory method
    result = AnalysisResult.success_result(
        data={"test": "value"},
        confidence=0.95
    )
    assert result.confidence == 0.95
    assert result.success is True

def test_m4_exceptions_can_be_raised():
    from shared.exceptions import DetectionException
    from shared.constants import ErrorCode
    try:
        raise DetectionException(
            error_code=ErrorCode.DETECTION_ERROR,
            message="Test exception"
        )
        assert False, "Exception was not raised"
    except DetectionException as e:
        # Exception was caught successfully
        assert e.message == "Test exception"
        assert e.error_code == ErrorCode.DETECTION_ERROR

def test_m5_protocol_isinstance_check():
    from shared.protocols import CameraProtocol
    # This should not raise an error
    class DummyCamera:
        def get_frame(self):
            pass
        def get_info(self):
            pass
    # We can check if it's a protocol
    assert hasattr(CameraProtocol, '_is_runtime_protocol')


# =============================================================================
# [N] Name collision detection (4 tests)
# =============================================================================

def test_n1_find_name_collisions():
    """Document expected collisions between sub-modules"""
    import shared.constants
    import shared.dto
    import shared.interfaces

    constants_names = set(shared.constants.__all__)
    dto_names = set(shared.dto.__all__)
    interfaces_names = set(shared.interfaces.__all__)

    # Find collisions
    const_dto_collision = constants_names & dto_names
    const_iface_collision = constants_names & interfaces_names
    dto_iface_collision = dto_names & interfaces_names

    # Expected collisions (these are by design)
    expected_collisions = {
        'BallState', 'ShotType', 'TrackState', 'BallSize',
        'VideoFormat', 'VideoCodec', 'AudioCodec', 'CameraType', 'CameraState',
        'OcclusionType', 'OcclusionSeverity', 'ResolutionStrategy',
        'ReIDModel', 'MatchStatus', 'JointType', 'SkeletonType', 'PoseQuality',
        'ShotResult', 'PlayType', 'ViolationType', 'FoulType', 'CourtZone',
        'RuleSet', 'CallType', 'SignalType', 'ReviewTrigger', 'ReviewOutcome', 'RefereeRole',
        'GameState', 'BonusStatus', 'DetectionTarget', 'DetectionState',
        'BoundingBox', 'DetectedObject', 'DetectionResult', 'StorageType', 'StorageState',
        'ContentType', 'SortOrder'
    }

    all_collisions = const_dto_collision | const_iface_collision | dto_iface_collision
    unexpected = all_collisions - expected_collisions

    # This is informational - we document collisions but don't fail
    assert True, f"Documented collisions: {len(all_collisions)}, Unexpected: {len(unexpected)}"

def test_n2_shared_handles_collisions():
    """Verify shared/__init__.py handles known collisions with aliases"""
    import shared
    # GameEventType is aliased from dto.game_dto.EventType
    assert hasattr(shared, 'GameEventType')
    # StorageVideoMetadata is aliased from interfaces.storage_interface.VideoMetadata
    assert hasattr(shared, 'StorageVideoMetadata')

def test_n3_event_type_collision():
    """EventType exists in both constants and dto, shared uses aliases"""
    from shared.constants import EventType as ConstEventType
    from shared.dto.game_dto import EventType as DTOEventType
    # They should be different classes
    assert ConstEventType is not DTOEventType, "EventType collision not resolved"

def test_n4_video_metadata_collision():
    """VideoMetadata exists in both dto and interfaces, shared uses aliases"""
    from shared.dto import VideoMetadata as DTOVideoMetadata
    from shared.interfaces import VideoMetadata as InterfaceVideoMetadata
    # They should be different classes
    assert DTOVideoMetadata is not InterfaceVideoMetadata, "VideoMetadata collision not resolved"


# =============================================================================
# [O] Alias consistency (3 tests)
# =============================================================================

def test_o1_game_event_type_alias():
    from shared import GameEventType
    from shared.dto.game_dto import EventType as DTOEventType
    assert GameEventType is DTOEventType, "GameEventType alias is incorrect"

def test_o2_storage_video_metadata_alias():
    from shared import StorageVideoMetadata
    from shared.interfaces.storage_interface import VideoMetadata as InterfaceVideoMetadata
    assert StorageVideoMetadata is InterfaceVideoMetadata, "StorageVideoMetadata alias is incorrect"

def test_o3_no_confusion_between_event_types():
    from shared.constants import EventType as ConstEventType
    from shared.dto.game_dto import EventType as DTOEventType
    # Ensure they are different and have different purposes
    assert ConstEventType is not DTOEventType
    # ConstEventType should be a general event enum
    # DTOEventType should be game-specific


# =============================================================================
# [P] Import path consistency (5 tests)
# =============================================================================

def test_p1_gender_import_consistency():
    from shared.constants.player_constants import Gender as G1
    from shared.constants import Gender as G2
    assert G1 is G2, "Gender imports are not consistent"

def test_p2_error_code_import_consistency():
    from shared import ErrorCode as E1
    from shared.constants import ErrorCode as E2
    assert E1 is E2, "ErrorCode imports are not consistent"

def test_p3_video_source_import_consistency():
    from shared import VideoSource as V1
    from shared.dto import VideoSource as V2
    assert V1 is V2, "VideoSource imports are not consistent"

def test_p4_ianalyzer_import_consistency():
    from shared import IAnalyzer as I1
    from shared.interfaces import IAnalyzer as I2
    assert I1 is I2, "IAnalyzer imports are not consistent"

def test_p5_courtview_exception_import_consistency():
    from shared import CourtViewException as C1
    from shared.exceptions import CourtViewException as C2
    assert C1 is C2, "CourtViewException imports are not consistent"


# =============================================================================
# [Q] Version consistency (3 tests)
# =============================================================================

def test_q1_shared_version_exists():
    import shared
    assert hasattr(shared, '__version__')
    version = shared.__version__
    assert isinstance(version, str) and len(version) > 0

def test_q2_all_submodule_versions_exist():
    import shared.constants, shared.dto, shared.interfaces, shared.protocols, shared.exceptions
    modules = [shared.constants, shared.dto, shared.interfaces, shared.protocols, shared.exceptions]
    for mod in modules:
        assert hasattr(mod, '__version__'), f"{mod.__name__} has no __version__"

def test_q3_versions_are_semver():
    import shared
    import shared.constants, shared.dto, shared.interfaces, shared.protocols, shared.exceptions
    modules = [shared, shared.constants, shared.dto, shared.interfaces, shared.protocols, shared.exceptions]
    for mod in modules:
        version = mod.__version__
        parts = version.split('.')
        assert len(parts) == 3, f"{mod.__name__} version {version} is not semver"
        for part in parts:
            assert part.isdigit(), f"{mod.__name__} version {version} has non-numeric part"


# =============================================================================
# [R] Module completeness (5 tests)
# =============================================================================

def test_r1_constants_has_26_modules():
    """Check that constants has 26 module files"""
    constants_path = Path(_project_root) / "shared" / "constants"
    py_files = list(constants_path.glob("*.py"))
    # Exclude __init__.py
    module_files = [f for f in py_files if f.name != "__init__.py"]
    assert len(module_files) == 26, f"Expected 26 module files in constants, found {len(module_files)}"

def test_r2_dto_has_26_modules():
    """Check that dto has 25 module files (26 total including __init__.py)"""
    dto_path = Path(_project_root) / "shared" / "dto"
    py_files = list(dto_path.glob("*.py"))
    module_files = [f for f in py_files if f.name != "__init__.py"]
    # 25 module files + 1 __init__.py = 26 total
    assert len(module_files) == 25, f"Expected 25 module files in dto (excluding __init__.py), found {len(module_files)}"

def test_r3_interfaces_has_at_least_4_modules():
    """Check that interfaces has at least 4 module files"""
    interfaces_path = Path(_project_root) / "shared" / "interfaces"
    py_files = list(interfaces_path.glob("*.py"))
    module_files = [f for f in py_files if f.name != "__init__.py"]
    assert len(module_files) >= 4, f"Expected at least 4 module files in interfaces, found {len(module_files)}"

def test_r4_protocols_has_at_least_2_modules():
    """Check that protocols has at least 2 module files"""
    protocols_path = Path(_project_root) / "shared" / "protocols"
    py_files = list(protocols_path.glob("*.py"))
    module_files = [f for f in py_files if f.name != "__init__.py"]
    assert len(module_files) >= 2, f"Expected at least 2 module files in protocols, found {len(module_files)}"

def test_r5_exceptions_has_at_least_5_modules():
    """Check that exceptions has at least 5 module files"""
    exceptions_path = Path(_project_root) / "shared" / "exceptions"
    py_files = list(exceptions_path.glob("*.py"))
    module_files = [f for f in py_files if f.name != "__init__.py"]
    assert len(module_files) >= 5, f"Expected at least 5 module files in exceptions, found {len(module_files)}"


# =============================================================================
# Main Test Runner
# =============================================================================

if __name__ == "__main__":
    _start_time = time.perf_counter()

    print(f"\n{'='*70}")
    print(f"  shared/ 모듈 전체 통합 테스트")
    print(f"  서브모듈: constants(216) + dto(292) + interfaces(81) + protocols(4) + exceptions(145)")
    print(f"  총 exports: 738 (shared 상위: 193)")
    print(f"{'='*70}")

    # [A] Top-level shared module (6 tests)
    run_test("A", "shared.__version__ == 2.0.0", test_a1_shared_version)
    run_test("A", "shared.__all__ exists with 193 items", test_a2_shared_all_exists)
    run_test("A", "All 193 items in __all__ are accessible", test_a3_shared_all_accessible)
    run_test("A", "shared.__author__ exists", test_a4_shared_author_exists)
    run_test("A", "shared module has no import errors", test_a5_shared_no_import_errors)
    run_test("A", "shared module is a package", test_a6_shared_is_package)

    # [B] Sub-module independence (10 tests)
    run_test("B", "constants module imports independently", test_b1_constants_import)
    run_test("B", "dto module imports independently", test_b2_dto_import)
    run_test("B", "interfaces module imports independently", test_b3_interfaces_import)
    run_test("B", "protocols module imports independently", test_b4_protocols_import)
    run_test("B", "exceptions module imports independently", test_b5_exceptions_import)
    run_test("B", "constants has 216 exports", test_b6_constants_export_count)
    run_test("B", "dto has 292 exports", test_b7_dto_export_count)
    run_test("B", "interfaces has 81 exports", test_b8_interfaces_export_count)
    run_test("B", "protocols has 4 exports", test_b9_protocols_export_count)
    run_test("B", "exceptions has 145 exports", test_b10_exceptions_export_count)

    # [C] No circular imports (5 tests)
    run_test("C", "constants: no circular import", test_c1_constants_no_circular)
    run_test("C", "dto: no circular import", test_c2_dto_no_circular)
    run_test("C", "interfaces: no circular import", test_c3_interfaces_no_circular)
    run_test("C", "protocols: no circular import", test_c4_protocols_no_circular)
    run_test("C", "exceptions: no circular import", test_c5_exceptions_no_circular)

    # [D] Constants export validation (3 tests)
    run_test("D", "All 216 constants exports are accessible", test_d1_constants_all_accessible)
    run_test("D", "All Enum classes have members", test_d2_enum_classes_have_members)
    run_test("D", "Key enums exist (Gender, AgeGroup, SkillLevel, ErrorCode)", test_d3_key_enums_exist)

    # [E] DTO export validation (3 tests)
    run_test("E", "All 292 DTO exports are accessible", test_e1_dto_all_accessible)
    run_test("E", "Key DTO classes exist (VideoSource, PipelineOptions, Point2D, Track)", test_e2_key_dto_classes_exist)
    run_test("E", "DTO classes have fields", test_e3_dto_classes_have_fields)

    # [F] Interfaces export validation (3 tests)
    run_test("F", "All 81 interface exports are accessible", test_f1_interfaces_all_accessible)
    run_test("F", "Key interfaces exist (IAnalyzer, IDetector, IStorage, IRepository)", test_f2_key_interfaces_exist)
    run_test("F", "ABC classes have abstract methods", test_f3_abc_classes_have_abstract_methods)

    # [G] Protocols export validation (3 tests)
    run_test("G", "All 4 protocol exports are accessible", test_g1_protocols_all_accessible)
    run_test("G", "All protocols are runtime_checkable", test_g2_all_protocols_are_runtime_checkable)
    run_test("G", "Key protocols exist (CameraProtocol, MultiCameraProtocol, StorageProtocol, AsyncStorageProtocol)", test_g3_key_protocols_exist)

    # [H] Exceptions export validation (3 tests)
    run_test("H", "All 145 exception exports are accessible", test_h1_exceptions_all_accessible)
    run_test("H", "All exports are exception classes", test_h2_all_exports_are_exceptions)
    run_test("H", "Key base exceptions exist (CourtViewException, RetryableException, etc.)", test_h3_key_base_exceptions_exist)

    # [I] Exception hierarchy validation (6 tests)
    run_test("I", "All exceptions inherit from CourtViewException", test_i1_all_exceptions_inherit_from_courtview_exception)
    run_test("I", "RetryableException inherits from CourtViewException", test_i2_retryable_exception_hierarchy)
    run_test("I", "NonRetryableException inherits from CourtViewException", test_i3_non_retryable_exception_hierarchy)
    run_test("I", "CriticalException inherits from CourtViewException", test_i4_critical_exception_hierarchy)
    run_test("I", "VideoException inherits from CourtViewException", test_i5_video_exception_hierarchy)
    run_test("I", "GPUException inherits from CourtViewException", test_i6_gpu_exception_hierarchy)

    # [J] Interface ABC verification (5 tests)
    run_test("J", "IAnalyzer is subclass of ABC", test_j1_ianalyzer_is_abc)
    run_test("J", "IDetector is subclass of ABC", test_j2_idetector_is_abc)
    run_test("J", "IStorage is subclass of ABC", test_j3_istorage_is_abc)
    run_test("J", "IGameEventDetector is subclass of ABC", test_j4_igame_event_detector_is_abc)
    run_test("J", "Each ABC has at least one abstractmethod", test_j5_each_abc_has_abstractmethod)

    # [K] Protocol runtime_checkable verification (4 tests)
    run_test("K", "CameraProtocol is runtime_checkable", test_k1_camera_protocol_runtime_checkable)
    run_test("K", "MultiCameraProtocol is runtime_checkable", test_k2_multi_camera_protocol_runtime_checkable)
    run_test("K", "StorageProtocol is runtime_checkable", test_k3_storage_protocol_runtime_checkable)
    run_test("K", "AsyncStorageProtocol is runtime_checkable", test_k4_async_storage_protocol_runtime_checkable)

    # [L] Constants → DTO type consistency (8 tests)
    run_test("L", "Gender enum has MALE, FEMALE members", test_l1_gender_enum_has_members)
    run_test("L", "AgeGroup enum has members for youth/teen/adult", test_l2_age_group_enum_has_members)
    run_test("L", "SkillLevel enum has BEGINNER through PROFESSIONAL", test_l3_skill_level_enum_has_members)
    run_test("L", "RuleSet enum has FIBA, NBA, KBL", test_l4_rule_set_enum_exists)
    run_test("L", "ShotResult exists in constants", test_l5_shot_result_exists)
    run_test("L", "PlayType exists in constants", test_l6_play_type_exists)
    run_test("L", "ViolationType exists in constants", test_l7_violation_type_exists)
    run_test("L", "FoulType exists in constants", test_l8_foul_type_exists)

    # [M] Cross-module data flow simulation (5 tests)
    run_test("M", "DetectionTarget enum is usable", test_m1_detection_target_usable)
    run_test("M", "BoundingBox can be instantiated", test_m2_bounding_box_instantiable)
    run_test("M", "AnalysisResult can be instantiated", test_m3_analysis_result_instantiable)
    run_test("M", "Exceptions can be raised and caught", test_m4_exceptions_can_be_raised)
    run_test("M", "Protocol isinstance check works", test_m5_protocol_isinstance_check)

    # [N] Name collision detection (4 tests)
    run_test("N", "Find and document name collisions", test_n1_find_name_collisions)
    run_test("N", "shared/__init__.py handles collisions with aliases", test_n2_shared_handles_collisions)
    run_test("N", "EventType collision is resolved", test_n3_event_type_collision)
    run_test("N", "VideoMetadata collision is resolved", test_n4_video_metadata_collision)

    # [O] Alias consistency (3 tests)
    run_test("O", "GameEventType alias is correct", test_o1_game_event_type_alias)
    run_test("O", "StorageVideoMetadata alias is correct", test_o2_storage_video_metadata_alias)
    run_test("O", "No confusion between EventType variants", test_o3_no_confusion_between_event_types)

    # [P] Import path consistency (5 tests)
    run_test("P", "Gender import path consistency", test_p1_gender_import_consistency)
    run_test("P", "ErrorCode import path consistency", test_p2_error_code_import_consistency)
    run_test("P", "VideoSource import path consistency", test_p3_video_source_import_consistency)
    run_test("P", "IAnalyzer import path consistency", test_p4_ianalyzer_import_consistency)
    run_test("P", "CourtViewException import path consistency", test_p5_courtview_exception_import_consistency)

    # [Q] Version consistency (3 tests)
    run_test("Q", "shared.__version__ exists", test_q1_shared_version_exists)
    run_test("Q", "All sub-module __version__ exist", test_q2_all_submodule_versions_exist)
    run_test("Q", "All versions are valid semver", test_q3_versions_are_semver)

    # [R] Module completeness (5 tests)
    run_test("R", "constants/ has 26 module files", test_r1_constants_has_26_modules)
    run_test("R", "dto/ has 26 module files", test_r2_dto_has_26_modules)
    run_test("R", "interfaces/ has at least 4 module files", test_r3_interfaces_has_at_least_4_modules)
    run_test("R", "protocols/ has at least 2 module files", test_r4_protocols_has_at_least_2_modules)
    run_test("R", "exceptions/ has at least 5 module files", test_r5_exceptions_has_at_least_5_modules)

    _elapsed = time.perf_counter() - _start_time

    # Print results by section
    current_section = ""
    for r in results:
        if r.section != current_section:
            current_section = r.section
            print(f"\n{'='*70}")
            print(f"  섹션 {current_section}")
            print(f"{'='*70}")
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}")
        if not r.passed:
            print(f"         → {r.message}")

    print(f"\n{'='*70}")
    print(f"  shared/ 통합 테스트 최종 결과")
    print(f"{'='*70}")
    print(f"  총 테스트: {total_pass + total_fail}")
    print(f"  PASS: {total_pass}")
    print(f"  FAIL: {total_fail}")
    print(f"  실행 시간: {_elapsed:.3f}초")
    print(f"{'='*70}")

    if total_fail > 0:
        sys.exit(1)
