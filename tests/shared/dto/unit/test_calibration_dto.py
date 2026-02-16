# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_calibration_dto.py

카메라 캘리브레이션 DTO 단위 테스트
- __all__ Export 동기화 (SupportedLanguage 제거 확인)
- typing 모더나이즈 (Dict/List/Tuple 미사용)
- 하드코딩 제거 확인 (REPROJECTION_FAIR 참조)
- i18n 다국어 캐시 (모듈 레벨)
- 행렬 연산 정확도 (내부/외부 파라미터, 호모그래피, 투영)
- __post_init__ 검증 (shape 체크, 정규화)
- numpy 연동

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import inspect
import math
import sys
from pathlib import Path

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


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
    """모듈 임포트 + 버전"""
    try:
        from shared.dto import calibration_dto
        assert calibration_dto.__version__ == "1.1.0"
        r.ok("모듈 임포트 + 버전 1.1.0")
    except Exception as e:
        r.fail("모듈 임포트", str(e))


def test_all_exports(r: TestResult) -> None:
    """__all__ export 완전성 (SupportedLanguage 제거 확인)"""
    from shared.dto import calibration_dto
    expected = {
        "CalibrationStatus", "CalibrationMethod",
        "IntrinsicParams", "DistortionCoeffs", "CameraMatrix",
        "ExtrinsicParams", "RotationMatrix", "TranslationVector",
        "HomographyMatrix", "FundamentalMatrix", "EssentialMatrix", "ProjectionMatrix",
        "CalibrationResult", "StereoCalibration", "MultiCameraCalibration",
    }
    actual = set(calibration_dto.__all__)
    if actual == expected:
        r.ok(f"__all__ = {len(expected)}개 일치")
    else:
        r.fail("__all__ 불일치", f"diff={actual.symmetric_difference(expected)}")


def test_no_supported_language_export(r: TestResult) -> None:
    """SupportedLanguage가 __all__에서 제거됨"""
    from shared.dto import calibration_dto
    if "SupportedLanguage" not in calibration_dto.__all__:
        r.ok("SupportedLanguage __all__에서 제거 확인")
    else:
        r.fail("SupportedLanguage", "__all__에 여전히 존재")


# ==================== 2. typing 모더나이즈 ====================
def test_no_old_typing(r: TestResult) -> None:
    """Dict, List, Tuple 미사용 확인"""
    from shared.dto import calibration_dto
    source = inspect.getsource(calibration_dto)
    old_types = ["Dict[", "List[", "Tuple["]
    found = [t for t in old_types if t in source]
    if not found:
        r.ok("typing 모더나이즈 완료")
    else:
        r.fail("typing 구형 타입 잔존", str(found))


# ==================== 3. 하드코딩 제거 ====================
def test_no_hardcoded_reprojection(r: TestResult) -> None:
    """is_valid 내 1.0 하드코딩 제거"""
    from shared.dto.calibration_dto import CalibrationResult, StereoCalibration
    cr_src = inspect.getsource(CalibrationResult.is_valid.fget)
    sc_src = inspect.getsource(StereoCalibration.is_valid.fget)
    if "< 1.0" not in cr_src and "< 1.0" not in sc_src:
        r.ok("REPROJECTION_FAIR 상수 참조 (하드코딩 제거)")
    else:
        r.fail("reprojection 하드코딩", "< 1.0 발견")


def test_reprojection_constant_value(r: TestResult) -> None:
    """REPROJECTION_FAIR = 1.0 확인"""
    from shared.constants.camera_constants import REPROJECTION_FAIR
    if abs(REPROJECTION_FAIR - 1.0) < 1e-6:
        r.ok("REPROJECTION_FAIR = 1.0")
    else:
        r.fail("REPROJECTION_FAIR", f"actual={REPROJECTION_FAIR}")


# ==================== 4. i18n 캐시 ====================
def test_i18n_module_level_cache(r: TestResult) -> None:
    """i18n 딕셔너리가 모듈 레벨에 존재"""
    from shared.dto import calibration_dto
    has_status = hasattr(calibration_dto, "_CALIBRATION_STATUS_I18N")
    has_method = hasattr(calibration_dto, "_CALIBRATION_METHOD_I18N")
    if has_status and has_method:
        r.ok("i18n 모듈 레벨 캐시 2개 확인")
    else:
        r.fail("i18n 캐시", f"status={has_status}, method={has_method}")


def test_i18n_no_inline_dict(r: TestResult) -> None:
    """get_name 내부에 inline 딕셔너리 없음"""
    from shared.dto.calibration_dto import CalibrationStatus, CalibrationMethod
    s_src = inspect.getsource(CalibrationStatus.get_name)
    m_src = inspect.getsource(CalibrationMethod.get_name)
    if "translations" not in s_src and "translations" not in m_src:
        r.ok("get_name 내부 inline 딕셔너리 없음")
    else:
        r.fail("inline dict", "translations 변수 발견")


def test_i18n_calibration_status(r: TestResult) -> None:
    """CalibrationStatus i18n 전체 검증"""
    from shared.dto.calibration_dto import CalibrationStatus
    from shared.constants.localization import SupportedLanguage
    ok = True
    for cs in CalibrationStatus:
        for lang in SupportedLanguage:
            name = cs.get_name(lang)
            if not name or not isinstance(name, str):
                r.fail(f"i18n {cs.name}/{lang.name}", "빈 문자열")
                ok = False
    if ok:
        count = len(list(CalibrationStatus)) * len(list(SupportedLanguage))
        r.ok(f"CalibrationStatus i18n {count}건 전부 유효")


def test_i18n_calibration_method(r: TestResult) -> None:
    """CalibrationMethod i18n 전체 검증"""
    from shared.dto.calibration_dto import CalibrationMethod
    from shared.constants.localization import SupportedLanguage
    ok = True
    for cm in CalibrationMethod:
        for lang in SupportedLanguage:
            name = cm.get_name(lang)
            if not name or not isinstance(name, str):
                r.fail(f"i18n {cm.name}/{lang.name}", "빈 문자열")
                ok = False
    if ok:
        count = len(list(CalibrationMethod)) * len(list(SupportedLanguage))
        r.ok(f"CalibrationMethod i18n {count}건 전부 유효")


def test_i18n_to_korean(r: TestResult) -> None:
    """to_korean 하위 호환성"""
    from shared.dto.calibration_dto import CalibrationStatus, CalibrationMethod
    assert CalibrationStatus.CALIBRATED.to_korean == "완료"
    assert CalibrationStatus.FAILED.to_korean == "실패"
    assert CalibrationMethod.COURT_LINES.to_korean == "코트 라인"
    assert CalibrationMethod.MANUAL.to_korean == "수동"
    r.ok("to_korean 4건 정상")


# ==================== 5. IntrinsicParams ====================
def test_intrinsic_to_matrix(r: TestResult) -> None:
    """IntrinsicParams → 3x3 행렬 변환"""
    from shared.dto.calibration_dto import IntrinsicParams
    ip = IntrinsicParams(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0, skew=0.5)
    mat = ip.to_matrix()
    if mat.shape == (3, 3) and mat[0, 0] == 1000.0 and mat[0, 1] == 0.5 and mat[0, 2] == 960.0:
        r.ok("to_matrix: 3x3, fx/skew/cx 정상")
    else:
        r.fail("to_matrix", f"shape={mat.shape}")


def test_intrinsic_from_matrix(r: TestResult) -> None:
    """카메라 행렬 → IntrinsicParams 역변환"""
    from shared.dto.calibration_dto import IntrinsicParams
    ip = IntrinsicParams(fx=1200.0, fy=1100.0, cx=640.0, cy=480.0, skew=0.3)
    mat = ip.to_matrix()
    ip2 = IntrinsicParams.from_matrix(mat)
    if abs(ip2.fx - 1200.0) < 1e-6 and abs(ip2.skew - 0.3) < 1e-6:
        r.ok("from_matrix 역변환 정상")
    else:
        r.fail("from_matrix", f"fx={ip2.fx}, skew={ip2.skew}")


def test_intrinsic_properties(r: TestResult) -> None:
    """focal_length, principal_point, aspect_ratio"""
    from shared.dto.calibration_dto import IntrinsicParams
    ip = IntrinsicParams(fx=1000.0, fy=500.0, cx=960.0, cy=540.0)
    if ip.focal_length == (1000.0, 500.0) and ip.principal_point == (960.0, 540.0) and abs(ip.aspect_ratio - 2.0) < 1e-6:
        r.ok("focal_length, principal_point, aspect_ratio 정상")
    else:
        r.fail("properties", f"fl={ip.focal_length}, pp={ip.principal_point}, ar={ip.aspect_ratio}")


# ==================== 6. DistortionCoeffs ====================
def test_distortion_to_from_array(r: TestResult) -> None:
    """DistortionCoeffs 배열 변환 왕복"""
    from shared.dto.calibration_dto import DistortionCoeffs
    dc = DistortionCoeffs(k1=0.1, k2=-0.2, p1=0.01, p2=-0.01, k3=0.05)
    arr = dc.to_array(5)
    dc2 = DistortionCoeffs.from_array(arr)
    if abs(dc2.k1 - 0.1) < 1e-10 and abs(dc2.k3 - 0.05) < 1e-10:
        r.ok("to_array/from_array 왕복 정상")
    else:
        r.fail("distortion array", f"k1={dc2.k1}, k3={dc2.k3}")


def test_distortion_properties(r: TestResult) -> None:
    """radial, tangential, is_zero"""
    from shared.dto.calibration_dto import DistortionCoeffs
    dc = DistortionCoeffs(k1=0.1, k2=-0.2, p1=0.01, p2=-0.01, k3=0.05)
    assert dc.radial == (0.1, -0.2, 0.05)
    assert dc.tangential == (0.01, -0.01)
    assert not dc.is_zero
    assert DistortionCoeffs().is_zero
    r.ok("radial, tangential, is_zero 정상")


# ==================== 7. RotationMatrix ====================
def test_rotation_identity(r: TestResult) -> None:
    """단위 회전 행렬"""
    from shared.dto.calibration_dto import RotationMatrix
    rm = RotationMatrix.identity()
    if rm.is_valid and np.allclose(rm.matrix, np.eye(3)):
        r.ok("identity 회전 행렬 유효")
    else:
        r.fail("identity", f"is_valid={rm.is_valid}")


def test_rotation_euler_angles(r: TestResult) -> None:
    """단위 행렬의 오일러 각도 = (0, 0, 0)"""
    from shared.dto.calibration_dto import RotationMatrix
    rm = RotationMatrix.identity()
    roll, pitch, yaw = rm.to_euler_angles()
    if abs(roll) < 1e-6 and abs(pitch) < 1e-6 and abs(yaw) < 1e-6:
        r.ok("identity → euler = (0, 0, 0)")
    else:
        r.fail("euler", f"({roll}, {pitch}, {yaw})")


def test_rotation_invalid_shape(r: TestResult) -> None:
    """3x3이 아닌 행렬은 ValueError"""
    from shared.dto.calibration_dto import RotationMatrix
    try:
        RotationMatrix(np.eye(4, dtype=np.float64))
        r.fail("shape 검증", "ValueError 미발생")
    except ValueError:
        r.ok("3x3 아닌 행렬 → ValueError")


# ==================== 8. TranslationVector ====================
def test_translation_from_xyz(r: TestResult) -> None:
    """from_xyz 팩토리"""
    from shared.dto.calibration_dto import TranslationVector
    tv = TranslationVector.from_xyz(3.0, 4.0, 0.0)
    if abs(tv.magnitude - 5.0) < 1e-6 and tv.to_tuple() == (3.0, 4.0, 0.0):
        r.ok("from_xyz(3,4,0) → magnitude=5, tuple=(3,4,0)")
    else:
        r.fail("from_xyz", f"mag={tv.magnitude}, tuple={tv.to_tuple()}")


def test_translation_invalid_dim(r: TestResult) -> None:
    """3차원이 아닌 벡터는 ValueError"""
    from shared.dto.calibration_dto import TranslationVector
    try:
        TranslationVector(np.array([1.0, 2.0], dtype=np.float64))
        r.fail("dim 검증", "ValueError 미발생")
    except ValueError:
        r.ok("2차원 벡터 → ValueError")


# ==================== 9. HomographyMatrix ====================
def test_homography_identity_transform(r: TestResult) -> None:
    """단위 호모그래피 → 점 불변"""
    from shared.dto.calibration_dto import HomographyMatrix
    hm = HomographyMatrix(np.eye(3, dtype=np.float64))
    pt = hm.transform_point((10.0, 20.0))
    if abs(pt[0] - 10.0) < 1e-6 and abs(pt[1] - 20.0) < 1e-6:
        r.ok("identity 호모그래피 → (10,20) 불변")
    else:
        r.fail("homography", f"pt={pt}")


def test_homography_inverse(r: TestResult) -> None:
    """호모그래피 역변환"""
    from shared.dto.calibration_dto import HomographyMatrix
    H = np.array([[2, 0, 10], [0, 2, 20], [0, 0, 1]], dtype=np.float64)
    hm = HomographyMatrix(H)
    inv = hm.inverse
    pt = hm.transform_point((5.0, 5.0))
    pt_back = inv.transform_point(pt)
    if abs(pt_back[0] - 5.0) < 1e-4 and abs(pt_back[1] - 5.0) < 1e-4:
        r.ok("호모그래피 역변환 왕복 정상")
    else:
        r.fail("inverse", f"back={pt_back}")


def test_homography_batch_transform(r: TestResult) -> None:
    """여러 점 배치 변환"""
    from shared.dto.calibration_dto import HomographyMatrix
    hm = HomographyMatrix(np.eye(3, dtype=np.float64))
    pts = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    result = hm.transform_points(pts)
    if np.allclose(result, pts):
        r.ok("batch transform 3점 정상")
    else:
        r.fail("batch", f"result={result}")


# ==================== 10. CalibrationResult ====================
def test_calibration_result_is_valid(r: TestResult) -> None:
    """CalibrationResult.is_valid — REPROJECTION_FAIR 참조"""
    from shared.dto.calibration_dto import (
        CalibrationResult, CalibrationStatus, IntrinsicParams, DistortionCoeffs,
    )
    good = CalibrationResult(
        intrinsic=IntrinsicParams(fx=1000, fy=1000, cx=960, cy=540),
        distortion=DistortionCoeffs(),
        reprojection_error=0.5,
        status=CalibrationStatus.CALIBRATED,
    )
    bad_error = CalibrationResult(
        intrinsic=IntrinsicParams(fx=1000, fy=1000, cx=960, cy=540),
        distortion=DistortionCoeffs(),
        reprojection_error=1.5,
        status=CalibrationStatus.CALIBRATED,
    )
    bad_status = CalibrationResult(
        intrinsic=IntrinsicParams(fx=1000, fy=1000, cx=960, cy=540),
        distortion=DistortionCoeffs(),
        reprojection_error=0.5,
        status=CalibrationStatus.FAILED,
    )
    if good.is_valid and not bad_error.is_valid and not bad_status.is_valid:
        r.ok("is_valid: good=True, bad_error=False, bad_status=False")
    else:
        r.fail("is_valid", f"good={good.is_valid}, err={bad_error.is_valid}, stat={bad_status.is_valid}")


# ==================== 11. StereoCalibration ====================
def test_stereo_is_valid(r: TestResult) -> None:
    """StereoCalibration.is_valid"""
    from shared.dto.calibration_dto import (
        StereoCalibration, CalibrationStatus, RotationMatrix, TranslationVector,
    )
    good = StereoCalibration(
        rotation=RotationMatrix.identity(),
        translation=TranslationVector.from_xyz(0.1, 0.0, 0.0),
        reprojection_error=0.3,
        status=CalibrationStatus.CALIBRATED,
    )
    bad = StereoCalibration(reprojection_error=2.0, status=CalibrationStatus.CALIBRATED)
    if good.is_valid and not bad.is_valid:
        r.ok("StereoCalibration.is_valid 정상")
    else:
        r.fail("stereo is_valid", f"good={good.is_valid}, bad={bad.is_valid}")


def test_stereo_baseline(r: TestResult) -> None:
    """baseline 거리 계산"""
    from shared.dto.calibration_dto import StereoCalibration, TranslationVector, RotationMatrix
    sc = StereoCalibration(
        rotation=RotationMatrix.identity(),
        translation=TranslationVector.from_xyz(0.12, 0.0, 0.0),
    )
    if abs(sc.baseline - 0.12) < 1e-6:
        r.ok("baseline = 0.12m")
    else:
        r.fail("baseline", f"actual={sc.baseline}")


# ==================== 12. MultiCameraCalibration ====================
def test_multi_camera_num_cameras(r: TestResult) -> None:
    """num_cameras 프로퍼티"""
    from shared.dto.calibration_dto import MultiCameraCalibration, CalibrationResult
    from uuid import uuid4
    cams = {uuid4(): CalibrationResult() for _ in range(3)}
    mc = MultiCameraCalibration(camera_calibrations=cams)
    if mc.num_cameras == 3:
        r.ok("num_cameras = 3")
    else:
        r.fail("num_cameras", f"actual={mc.num_cameras}")


def test_multi_camera_get_stereo(r: TestResult) -> None:
    """get_stereo_calibration 양방향 조회"""
    from shared.dto.calibration_dto import MultiCameraCalibration, StereoCalibration
    from uuid import uuid4
    id1, id2 = uuid4(), uuid4()
    sc = StereoCalibration(camera1_id=id1, camera2_id=id2)
    mc = MultiCameraCalibration(stereo_calibrations=[sc])
    # 정방향
    found_fwd = mc.get_stereo_calibration(id1, id2)
    # 역방향
    found_rev = mc.get_stereo_calibration(id2, id1)
    if found_fwd is sc and found_rev is sc:
        r.ok("get_stereo_calibration 양방향 조회 정상")
    else:
        r.fail("stereo lookup", f"fwd={found_fwd is not None}, rev={found_rev is not None}")


# ==================== 13. ProjectionMatrix ====================
def test_projection_identity(r: TestResult) -> None:
    """단위 투영 행렬 → 3D(1,2,1) → 2D(1,2)"""
    from shared.dto.calibration_dto import ProjectionMatrix
    pm = ProjectionMatrix()  # [I | 0]
    pt = pm.project(np.array([1.0, 2.0, 1.0]))
    if abs(pt[0] - 1.0) < 1e-6 and abs(pt[1] - 2.0) < 1e-6:
        r.ok("identity 투영: (1,2,1) → (1,2)")
    else:
        r.fail("projection", f"pt={pt}")


def test_projection_from_intrinsic_extrinsic(r: TestResult) -> None:
    """IntrinsicParams + ExtrinsicParams → ProjectionMatrix"""
    from shared.dto.calibration_dto import ProjectionMatrix, IntrinsicParams, ExtrinsicParams
    ip = IntrinsicParams(fx=1000, fy=1000, cx=960, cy=540)
    ep = ExtrinsicParams()
    pm = ProjectionMatrix.from_intrinsic_extrinsic(ip, ep)
    if pm.matrix.shape == (3, 4):
        r.ok("from_intrinsic_extrinsic → 3x4")
    else:
        r.fail("projection shape", f"shape={pm.matrix.shape}")


# ==================== 14. CameraMatrix shape 검증 ====================
def test_camera_matrix_shape_error(r: TestResult) -> None:
    """3x3이 아닌 행렬은 ValueError"""
    from shared.dto.calibration_dto import CameraMatrix
    try:
        CameraMatrix(np.eye(4, dtype=np.float64))
        r.fail("CameraMatrix shape", "ValueError 미발생")
    except ValueError:
        r.ok("CameraMatrix: 4x4 → ValueError")


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("calibration_dto.py v1.1.0 단위 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 및 Export ---")
    test_module_import(r)
    test_all_exports(r)
    test_no_supported_language_export(r)

    print("\n--- typing 모더나이즈 ---")
    test_no_old_typing(r)

    print("\n--- 하드코딩 제거 ---")
    test_no_hardcoded_reprojection(r)
    test_reprojection_constant_value(r)

    print("\n--- i18n 캐시 ---")
    test_i18n_module_level_cache(r)
    test_i18n_no_inline_dict(r)
    test_i18n_calibration_status(r)
    test_i18n_calibration_method(r)
    test_i18n_to_korean(r)

    print("\n--- IntrinsicParams ---")
    test_intrinsic_to_matrix(r)
    test_intrinsic_from_matrix(r)
    test_intrinsic_properties(r)

    print("\n--- DistortionCoeffs ---")
    test_distortion_to_from_array(r)
    test_distortion_properties(r)

    print("\n--- RotationMatrix ---")
    test_rotation_identity(r)
    test_rotation_euler_angles(r)
    test_rotation_invalid_shape(r)

    print("\n--- TranslationVector ---")
    test_translation_from_xyz(r)
    test_translation_invalid_dim(r)

    print("\n--- HomographyMatrix ---")
    test_homography_identity_transform(r)
    test_homography_inverse(r)
    test_homography_batch_transform(r)

    print("\n--- CalibrationResult ---")
    test_calibration_result_is_valid(r)

    print("\n--- StereoCalibration ---")
    test_stereo_is_valid(r)
    test_stereo_baseline(r)

    print("\n--- MultiCameraCalibration ---")
    test_multi_camera_num_cameras(r)
    test_multi_camera_get_stereo(r)

    print("\n--- ProjectionMatrix ---")
    test_projection_identity(r)
    test_projection_from_intrinsic_extrinsic(r)

    print("\n--- CameraMatrix ---")
    test_camera_matrix_shape_error(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
