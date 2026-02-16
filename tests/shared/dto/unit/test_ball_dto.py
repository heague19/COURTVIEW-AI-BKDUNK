# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_ball_dto.py

공 감지 및 궤적 DTO 단위 테스트
- __all__ Export 동기화
- typing 모더나이즈 (Dict/List/Tuple 미사용)
- 하드코딩 제거 확인 (상수 참조)
- 열거형 완전성 (TrajectoryType, ShotResult)
- i18n 다국어 캐시 (모듈 레벨)
- 데이터클래스 생성/프로퍼티/검증
- 상수 연동 (ball_constants, court_constants)

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import inspect
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


# ==================== 테스트 결과 클래스 ====================
class TestResult:
    """테스트 결과 저장"""

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


# ==================== 1. 모듈 임포트 및 Export ====================
def test_module_import(r: TestResult) -> None:
    """모듈 임포트 성공 확인"""
    try:
        from shared.dto import ball_dto
        assert ball_dto.__version__ == "1.1.0"
        r.ok("모듈 임포트 + 버전 1.1.0")
    except Exception as e:
        r.fail("모듈 임포트", str(e))


def test_all_exports(r: TestResult) -> None:
    """__all__ 내 모든 이름이 실제 존재"""
    from shared.dto import ball_dto
    for name in ball_dto.__all__:
        if not hasattr(ball_dto, name):
            r.fail(f"__all__ export '{name}'", "모듈에 존재하지 않음")
            return
    r.ok(f"__all__ {len(ball_dto.__all__)}개 전부 존재")


def test_all_exports_count(r: TestResult) -> None:
    """__all__ export 수 확인"""
    from shared.dto import ball_dto
    expected = {
        "SupportedLanguage", "BallState", "BallSize", "ShotType",
        "TrajectoryType", "ShotResult",
        "BallDetection", "BallTrajectory", "ShotTrajectory", "BallAnalysisResult",
    }
    actual = set(ball_dto.__all__)
    if actual == expected:
        r.ok(f"__all__ = {len(expected)}개 일치")
    else:
        missing = expected - actual
        extra = actual - expected
        r.fail("__all__ 불일치", f"누락={missing}, 초과={extra}")


# ==================== 2. typing 모더나이즈 ====================
def test_no_old_typing(r: TestResult) -> None:
    """Dict, List, Tuple 미사용 확인"""
    from shared.dto import ball_dto
    source = inspect.getsource(ball_dto)
    old_types = ["Dict[", "List[", "Tuple["]
    found = [t for t in old_types if t in source]
    if not found:
        r.ok("typing 모더나이즈 완료 (Dict/List/Tuple 없음)")
    else:
        r.fail("typing 구형 타입 잔존", str(found))


# ==================== 3. 하드코딩 제거 ====================
def test_no_hardcoded_three_point(r: TestResult) -> None:
    """3점 라인 거리 하드코딩(6.75) 제거 확인"""
    from shared.dto import ball_dto
    method_src = inspect.getsource(ball_dto.ShotTrajectory.is_three_pointer.fget)
    if "6.75" in method_src:
        r.fail("3점 라인 하드코딩", "6.75가 is_three_pointer 내부에 존재")
    else:
        r.ok("3점 라인 = THREE_POINT_LINE_DISTANCE_M 참조")


def test_no_hardcoded_release_angle(r: TestResult) -> None:
    """릴리즈 최적각 하드코딩(52.0) 제거 확인"""
    from shared.dto import ball_dto
    method_src = inspect.getsource(ball_dto.ShotTrajectory.release_angle_optimal_diff.fget)
    if "52.0" in method_src:
        r.fail("릴리즈 각도 하드코딩", "52.0이 release_angle_optimal_diff 내부에 존재")
    else:
        r.ok("릴리즈 각도 = SHOT_RELEASE_ANGLE_OPTIMAL 참조")


def test_constant_values_match(r: TestResult) -> None:
    """상수 임포트 값 일치 확인"""
    from shared.constants.ball_constants import SHOT_RELEASE_ANGLE_OPTIMAL
    from shared.constants.court_constants import THREE_POINT_LINE_DISTANCE_M
    if abs(THREE_POINT_LINE_DISTANCE_M - 6.75) < 1e-6 and abs(SHOT_RELEASE_ANGLE_OPTIMAL - 52.0) < 1e-6:
        r.ok("상수값 일치: THREE_POINT=6.75, RELEASE_ANGLE=52.0")
    else:
        r.fail("상수값 불일치", f"3pt={THREE_POINT_LINE_DISTANCE_M}, angle={SHOT_RELEASE_ANGLE_OPTIMAL}")


# ==================== 4. 열거형 완전성 ====================
def test_trajectory_type_members(r: TestResult) -> None:
    """TrajectoryType 멤버 완전성"""
    from shared.dto.ball_dto import TrajectoryType
    expected = {"SHOT", "PASS", "DRIBBLE", "REBOUND", "FREE_THROW", "FREE_BALL", "UNKNOWN"}
    actual = {m.name for m in TrajectoryType}
    if actual == expected:
        r.ok(f"TrajectoryType {len(expected)}개 멤버")
    else:
        r.fail("TrajectoryType 멤버 불일치", f"expected={expected}, actual={actual}")


def test_trajectory_type_is_str_enum(r: TestResult) -> None:
    """TrajectoryType은 str, Enum 상속"""
    from shared.dto.ball_dto import TrajectoryType
    t = TrajectoryType.SHOT
    if isinstance(t, str) and t.value == "shot":
        r.ok("TrajectoryType(str, Enum) 정상")
    else:
        r.fail("TrajectoryType 타입 오류", f"type={type(t)}, value={t.value}")


def test_shot_result_members(r: TestResult) -> None:
    """ShotResult 멤버 완전성"""
    from shared.dto.ball_dto import ShotResult
    expected = {"MADE", "MISSED_RIM", "AIR_BALL", "BLOCKED", "HIT_BACKBOARD", "IN_PROGRESS", "UNKNOWN"}
    actual = {m.name for m in ShotResult}
    if actual == expected:
        r.ok(f"ShotResult {len(expected)}개 멤버")
    else:
        r.fail("ShotResult 멤버 불일치", f"expected={expected}, actual={actual}")


def test_shot_result_properties(r: TestResult) -> None:
    """ShotResult.is_successful, is_complete 프로퍼티"""
    from shared.dto.ball_dto import ShotResult
    # is_successful
    if not ShotResult.MADE.is_successful:
        r.fail("ShotResult.is_successful", "MADE가 False")
        return
    for sr in [ShotResult.MISSED_RIM, ShotResult.AIR_BALL, ShotResult.BLOCKED]:
        if sr.is_successful:
            r.fail("ShotResult.is_successful", f"{sr.name}가 True")
            return
    # is_complete
    if not ShotResult.MADE.is_complete:
        r.fail("ShotResult.is_complete", "MADE가 False")
        return
    if ShotResult.IN_PROGRESS.is_complete or ShotResult.UNKNOWN.is_complete:
        r.fail("ShotResult.is_complete", "IN_PROGRESS/UNKNOWN이 True")
        return
    r.ok("ShotResult.is_successful + is_complete 정상")


# ==================== 5. i18n 캐시 ====================
def test_i18n_module_level_cache(r: TestResult) -> None:
    """i18n 딕셔너리가 모듈 레벨에 존재"""
    from shared.dto import ball_dto
    has_traj = hasattr(ball_dto, "_TRAJECTORY_TYPE_I18N")
    has_shot = hasattr(ball_dto, "_SHOT_RESULT_I18N")
    if has_traj and has_shot:
        r.ok("i18n 모듈 레벨 캐시: _TRAJECTORY_TYPE_I18N, _SHOT_RESULT_I18N")
    else:
        r.fail("i18n 캐시 누락", f"traj={has_traj}, shot={has_shot}")


def test_i18n_no_inline_dict(r: TestResult) -> None:
    """get_name 메서드 내부에 translations 딕셔너리 미생성"""
    from shared.dto.ball_dto import TrajectoryType, ShotResult
    t_src = inspect.getsource(TrajectoryType.get_name)
    s_src = inspect.getsource(ShotResult.get_name)
    if "translations" not in t_src and "translations" not in s_src:
        r.ok("get_name 내부에 inline 딕셔너리 없음")
    else:
        r.fail("get_name 내부 inline 딕셔너리 존재", "translations 변수 발견")


def test_i18n_all_languages_trajectory(r: TestResult) -> None:
    """TrajectoryType 전체 멤버 x 전체 언어 i18n"""
    from shared.dto.ball_dto import TrajectoryType
    from shared.constants.localization import SupportedLanguage
    ok = True
    for tt in TrajectoryType:
        for lang in SupportedLanguage:
            name = tt.get_name(lang)
            if not name or not isinstance(name, str):
                r.fail(f"i18n TrajectoryType.{tt.name}/{lang.name}", "빈 문자열")
                ok = False
    if ok:
        count = len(list(TrajectoryType)) * len(list(SupportedLanguage))
        r.ok(f"TrajectoryType i18n {count}건 전부 유효")


def test_i18n_all_languages_shot_result(r: TestResult) -> None:
    """ShotResult 전체 멤버 x 전체 언어 i18n"""
    from shared.dto.ball_dto import ShotResult
    from shared.constants.localization import SupportedLanguage
    ok = True
    for sr in ShotResult:
        for lang in SupportedLanguage:
            name = sr.get_name(lang)
            if not name or not isinstance(name, str):
                r.fail(f"i18n ShotResult.{sr.name}/{lang.name}", "빈 문자열")
                ok = False
    if ok:
        count = len(list(ShotResult)) * len(list(SupportedLanguage))
        r.ok(f"ShotResult i18n {count}건 전부 유효")


def test_i18n_to_korean(r: TestResult) -> None:
    """to_korean 프로퍼티 하위 호환성"""
    from shared.dto.ball_dto import TrajectoryType, ShotResult
    ok = True
    for tt in TrajectoryType:
        kor = tt.to_korean
        if not kor or not isinstance(kor, str):
            r.fail(f"TrajectoryType.{tt.name}.to_korean", "빈 문자열")
            ok = False
    for sr in ShotResult:
        kor = sr.to_korean
        if not kor or not isinstance(kor, str):
            r.fail(f"ShotResult.{sr.name}.to_korean", "빈 문자열")
            ok = False
    if ok:
        r.ok("to_korean 프로퍼티 전부 정상")


# ==================== 6. BallDetection 데이터클래스 ====================
def test_ball_detection_creation(r: TestResult) -> None:
    """BallDetection 기본 생성"""
    from shared.dto.ball_dto import BallDetection
    from shared.dto.geometry_dto import BoundingBox, Point2D
    from shared.constants.ball_constants import BallState
    try:
        det = BallDetection(
            position=Point2D(x=500.0, y=300.0),
            confidence=0.92,
            state=BallState.SHOOTING,
            bbox=BoundingBox(x=480, y=280, width=40, height=40),
            frame_index=10,
        )
        if det.frame_index == 10 and det.confidence == 0.92 and det.state == BallState.SHOOTING:
            r.ok("BallDetection 생성 정상")
        else:
            r.fail("BallDetection 생성", f"frame={det.frame_index}, conf={det.confidence}")
    except Exception as e:
        r.fail("BallDetection 생성", str(e))


def test_ball_detection_is_valid(r: TestResult) -> None:
    """BallDetection.is_valid — BALL_DETECTION_MIN_CONFIDENCE 참조"""
    from shared.dto.ball_dto import BallDetection
    from shared.dto.geometry_dto import Point2D
    from shared.constants.ball_constants import BALL_DETECTION_MIN_CONFIDENCE
    det_high = BallDetection(
        position=Point2D(x=0, y=0),
        confidence=BALL_DETECTION_MIN_CONFIDENCE + 0.1,
    )
    det_low = BallDetection(
        position=Point2D(x=0, y=0),
        confidence=BALL_DETECTION_MIN_CONFIDENCE - 0.1,
    )
    det_no_pos = BallDetection(confidence=0.9)
    if det_high.is_valid and not det_low.is_valid and not det_no_pos.is_valid:
        r.ok(f"is_valid: threshold={BALL_DETECTION_MIN_CONFIDENCE}, position 필수")
    else:
        r.fail("is_valid", f"high={det_high.is_valid}, low={det_low.is_valid}, no_pos={det_no_pos.is_valid}")


def test_ball_detection_confidence_clamp(r: TestResult) -> None:
    """BallDetection.__post_init__ 신뢰도 클램핑 (0.0~1.0)"""
    from shared.dto.ball_dto import BallDetection
    det_over = BallDetection(confidence=1.5)
    det_under = BallDetection(confidence=-0.5)
    if det_over.confidence == 1.0 and det_under.confidence == 0.0:
        r.ok("confidence 클램핑: 1.5→1.0, -0.5→0.0")
    else:
        r.fail("confidence 클램핑", f"over={det_over.confidence}, under={det_under.confidence}")


def test_ball_detection_is_visible(r: TestResult) -> None:
    """BallDetection.is_visible — LOST가 아니면 True"""
    from shared.dto.ball_dto import BallDetection
    from shared.constants.ball_constants import BallState
    det_lost = BallDetection(state=BallState.LOST)
    det_held = BallDetection(state=BallState.HELD)
    if not det_lost.is_visible and det_held.is_visible:
        r.ok("is_visible: LOST=False, HELD=True")
    else:
        r.fail("is_visible", f"lost={det_lost.is_visible}, held={det_held.is_visible}")


# ==================== 7. BallTrajectory 데이터클래스 ====================
def test_ball_trajectory_creation(r: TestResult) -> None:
    """BallTrajectory 기본 생성 + length"""
    from shared.dto.ball_dto import BallTrajectory
    from shared.dto.geometry_dto import Point2D
    pts = [Point2D(x=float(i * 10), y=float(i * 5)) for i in range(5)]
    traj = BallTrajectory(points_2d=pts)
    if traj.length == 5:
        r.ok("BallTrajectory.length = 5")
    else:
        r.fail("BallTrajectory.length", f"expected=5, actual={traj.length}")


def test_ball_trajectory_is_valid(r: TestResult) -> None:
    """BallTrajectory.is_valid — TRAJECTORY_MIN_POINTS 참조"""
    from shared.dto.ball_dto import BallTrajectory
    from shared.dto.geometry_dto import Point2D
    from shared.constants.ball_constants import TRAJECTORY_MIN_POINTS
    few = BallTrajectory(
        points_2d=[Point2D(x=0, y=0) for _ in range(TRAJECTORY_MIN_POINTS - 1)]
    )
    enough = BallTrajectory(
        points_2d=[Point2D(x=0, y=0) for _ in range(TRAJECTORY_MIN_POINTS + 1)]
    )
    if not few.is_valid and enough.is_valid:
        r.ok(f"is_valid: min_points={TRAJECTORY_MIN_POINTS}")
    else:
        r.fail("is_valid", f"few={few.is_valid}, enough={enough.is_valid}")


def test_ball_trajectory_uuid(r: TestResult) -> None:
    """BallTrajectory UUID 고유성"""
    from shared.dto.ball_dto import BallTrajectory
    ids = {BallTrajectory().trajectory_id for _ in range(50)}
    if len(ids) == 50:
        r.ok("BallTrajectory UUID 50개 고유")
    else:
        r.fail("UUID 고유성", f"50개 중 {len(ids)}개 고유")


# ==================== 8. ShotTrajectory 데이터클래스 ====================
def test_shot_trajectory_creation(r: TestResult) -> None:
    """ShotTrajectory 기본 생성"""
    from shared.dto.ball_dto import ShotTrajectory, ShotResult
    shot = ShotTrajectory(
        distance_to_hoop=6.8,
        release_angle=52.0,
        result=ShotResult.MADE,
        release_height=2.5,
        entry_angle=45.0,
    )
    if shot.distance_to_hoop == 6.8 and shot.result == ShotResult.MADE:
        r.ok("ShotTrajectory 생성 정상")
    else:
        r.fail("ShotTrajectory 생성", f"dist={shot.distance_to_hoop}, result={shot.result}")


def test_shot_trajectory_three_pointer(r: TestResult) -> None:
    """ShotTrajectory.is_three_pointer — 상수 참조"""
    from shared.dto.ball_dto import ShotTrajectory, ShotResult
    from shared.constants.court_constants import THREE_POINT_LINE_DISTANCE_M
    shot_3 = ShotTrajectory(
        distance_to_hoop=THREE_POINT_LINE_DISTANCE_M + 0.5,
        result=ShotResult.MADE,
    )
    shot_2 = ShotTrajectory(
        distance_to_hoop=THREE_POINT_LINE_DISTANCE_M - 0.5,
        result=ShotResult.MADE,
    )
    if shot_3.is_three_pointer and not shot_2.is_three_pointer:
        r.ok(f"is_three_pointer: threshold={THREE_POINT_LINE_DISTANCE_M}m")
    else:
        r.fail("is_three_pointer", f"3pt={shot_3.is_three_pointer}, 2pt={shot_2.is_three_pointer}")


def test_shot_trajectory_three_pointer_for(r: TestResult) -> None:
    """ShotTrajectory.is_three_pointer_for — 리그별 3점 라인"""
    from shared.dto.ball_dto import ShotTrajectory, ShotResult
    shot = ShotTrajectory(distance_to_hoop=7.0, result=ShotResult.MADE)
    # NBA 3점 라인 = 7.24m → 7.0m에서는 2점
    if shot.is_three_pointer_for(7.24):
        r.fail("is_three_pointer_for", "7.0m < 7.24m인데 True")
        return
    # FIBA 3점 라인 = 6.75m → 7.0m에서는 3점
    if not shot.is_three_pointer_for(6.75):
        r.fail("is_three_pointer_for", "7.0m >= 6.75m인데 False")
        return
    r.ok("is_three_pointer_for: NBA=False, FIBA=True (7.0m)")


def test_shot_trajectory_release_angle_diff(r: TestResult) -> None:
    """ShotTrajectory.release_angle_optimal_diff — 상수 참조"""
    from shared.dto.ball_dto import ShotTrajectory, ShotResult
    from shared.constants.ball_constants import SHOT_RELEASE_ANGLE_OPTIMAL
    shot = ShotTrajectory(
        distance_to_hoop=5.0,
        release_angle=55.0,
        result=ShotResult.MADE,
    )
    expected_diff = abs(55.0 - SHOT_RELEASE_ANGLE_OPTIMAL)
    actual_diff = shot.release_angle_optimal_diff
    if abs(actual_diff - expected_diff) < 1e-6:
        r.ok(f"release_angle_optimal_diff = {actual_diff:.1f}°")
    else:
        r.fail("release_angle_optimal_diff", f"expected={expected_diff}, actual={actual_diff}")


def test_shot_trajectory_is_made(r: TestResult) -> None:
    """ShotTrajectory.is_made — 결과 연동"""
    from shared.dto.ball_dto import ShotTrajectory, ShotResult
    made = ShotTrajectory(distance_to_hoop=5.0, result=ShotResult.MADE)
    missed = ShotTrajectory(distance_to_hoop=5.0, result=ShotResult.MISSED_RIM)
    if made.is_made and not missed.is_made:
        r.ok("ShotTrajectory.is_made: MADE=True, MISSED_RIM=False")
    else:
        r.fail("is_made", f"made={made.is_made}, missed={missed.is_made}")


# ==================== 9. BallAnalysisResult ====================
def test_ball_analysis_result_creation(r: TestResult) -> None:
    """BallAnalysisResult 생성 + num_completed_trajectories"""
    from shared.dto.ball_dto import BallAnalysisResult, BallTrajectory
    result = BallAnalysisResult(
        completed_trajectories=[BallTrajectory(), BallTrajectory(), BallTrajectory()],
        processing_time_ms=15.3,
    )
    if result.num_completed_trajectories == 3 and result.processing_time_ms == 15.3:
        r.ok("BallAnalysisResult 생성 + num_completed_trajectories=3")
    else:
        r.fail("BallAnalysisResult", f"count={result.num_completed_trajectories}")


def test_ball_analysis_result_ball_state(r: TestResult) -> None:
    """BallAnalysisResult.ball_state — 감지 없으면 LOST"""
    from shared.dto.ball_dto import BallAnalysisResult, BallDetection
    from shared.dto.geometry_dto import Point2D
    from shared.constants.ball_constants import BallState
    # detection 없으면 LOST
    result_no_det = BallAnalysisResult()
    if result_no_det.ball_state != BallState.LOST:
        r.fail("ball_state(no det)", f"expected=LOST, actual={result_no_det.ball_state}")
        return
    # detection 있으면 해당 상태
    result_with_det = BallAnalysisResult(
        detection=BallDetection(
            position=Point2D(x=100, y=200),
            confidence=0.9,
            state=BallState.SHOOTING,
        )
    )
    if result_with_det.ball_state == BallState.SHOOTING:
        r.ok("ball_state: no_det=LOST, with_det=SHOOTING")
    else:
        r.fail("ball_state(with det)", f"expected=SHOOTING, actual={result_with_det.ball_state}")


# ==================== 10. UUID 고유성 ====================
def test_shot_uuid_uniqueness(r: TestResult) -> None:
    """ShotTrajectory UUID 고유성"""
    from shared.dto.ball_dto import ShotTrajectory
    ids = {ShotTrajectory().shot_id for _ in range(100)}
    if len(ids) == 100:
        r.ok("ShotTrajectory UUID 100개 전부 고유")
    else:
        r.fail("UUID 고유성", f"100개 중 {len(ids)}개 고유")


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("ball_dto.py v1.1.0 단위 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 및 Export ---")
    test_module_import(r)
    test_all_exports(r)
    test_all_exports_count(r)

    print("\n--- typing 모더나이즈 ---")
    test_no_old_typing(r)

    print("\n--- 하드코딩 제거 ---")
    test_no_hardcoded_three_point(r)
    test_no_hardcoded_release_angle(r)
    test_constant_values_match(r)

    print("\n--- 열거형 완전성 ---")
    test_trajectory_type_members(r)
    test_trajectory_type_is_str_enum(r)
    test_shot_result_members(r)
    test_shot_result_properties(r)

    print("\n--- i18n 캐시 ---")
    test_i18n_module_level_cache(r)
    test_i18n_no_inline_dict(r)
    test_i18n_all_languages_trajectory(r)
    test_i18n_all_languages_shot_result(r)
    test_i18n_to_korean(r)

    print("\n--- BallDetection ---")
    test_ball_detection_creation(r)
    test_ball_detection_is_valid(r)
    test_ball_detection_confidence_clamp(r)
    test_ball_detection_is_visible(r)

    print("\n--- BallTrajectory ---")
    test_ball_trajectory_creation(r)
    test_ball_trajectory_is_valid(r)
    test_ball_trajectory_uuid(r)

    print("\n--- ShotTrajectory ---")
    test_shot_trajectory_creation(r)
    test_shot_trajectory_three_pointer(r)
    test_shot_trajectory_three_pointer_for(r)
    test_shot_trajectory_release_angle_diff(r)
    test_shot_trajectory_is_made(r)

    print("\n--- BallAnalysisResult ---")
    test_ball_analysis_result_creation(r)
    test_ball_analysis_result_ball_state(r)

    print("\n--- UUID ---")
    test_shot_uuid_uniqueness(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
