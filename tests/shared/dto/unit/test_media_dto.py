# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_media_dto.py

미디어 DTO 유닛 테스트
- 모듈 구조 (__version__, __all__, typing 모던화)
- ExportFormat 열거형 (5 members, str 상속)
- AnnotationType 열거형 (9 members, str 상속)
- Annotation 데이터클래스 (UUID 독립성, Optional 필드, 기본값)
- VideoClip 데이터클래스 (__post_init__ duration 자동계산)
- MultiAngleClip 데이터클래스 (total_angles 프로퍼티)
- CoachingPoint 데이터클래스 (UUID 필드, 기본값)
- PlayerClipPackage 데이터클래스 (total_clips 프로퍼티)
- FilmSessionData 데이터클래스 (created_at, comparison_pairs)
- ExportConfig 데이터클래스 (resolution tuple, 기본값)

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
        self.errors = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def eq(self, name: str, actual, expected) -> None:
        if actual == expected:
            self.ok(name)
        else:
            self.fail(name, f"{actual!r} != {expected!r}")

    def true(self, name: str, condition: bool) -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, "condition is False")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


# ==================== 1. 모듈 구조 ====================
def test_module_structure(r: TestResult) -> None:
    """모듈 메타데이터 및 구조 검증"""
    import shared.dto.media_dto as mod

    r.eq("__version__ == 1.0.0", mod.__version__, "1.0.0")
    r.eq("__all__ 항목 수 == 9", len(mod.__all__), 9)

    # 레거시 typing 없음
    import inspect
    source = inspect.getsource(mod)
    legacy_count = sum(
        source.count(pat) for pat in ["Optional[", "List[", "Dict[", "Tuple[", "Union["]
    )
    r.eq("레거시 typing 없음", legacy_count, 0)
    r.true("typing 임포트 없음", "from typing" not in source)


# ==================== 2. ExportFormat 열거형 ====================
def test_export_format(r: TestResult) -> None:
    """ExportFormat 열거형 검증"""
    from shared.dto.media_dto import ExportFormat

    r.eq("ExportFormat 멤버 수", len(ExportFormat), 5)
    r.eq("MP4.value", ExportFormat.MP4.value, "mp4")
    r.eq("MOV.value", ExportFormat.MOV.value, "mov")
    r.eq("AVI.value", ExportFormat.AVI.value, "avi")
    r.eq("GIF.value", ExportFormat.GIF.value, "gif")
    r.eq("PNG_SEQUENCE.value", ExportFormat.PNG_SEQUENCE.value, "png_sequence")
    r.eq("str(MP4)", str(ExportFormat.MP4), "mp4")
    r.true("str 상속", isinstance(ExportFormat.MP4, str))


# ==================== 3. AnnotationType 열거형 ====================
def test_annotation_type(r: TestResult) -> None:
    """AnnotationType 열거형 검증"""
    from shared.dto.media_dto import AnnotationType

    r.eq("AnnotationType 멤버 수", len(AnnotationType), 9)
    expected = [
        "arrow", "circle", "line", "text", "spotlight",
        "player_trail", "ball_trail", "zone_highlight", "drawing",
    ]
    actual = [m.value for m in AnnotationType]
    r.eq("AnnotationType 값 목록", actual, expected)
    r.eq("str(ARROW)", str(AnnotationType.ARROW), "arrow")
    r.true("str 상속", isinstance(AnnotationType.DRAWING, str))


# ==================== 4. Annotation ====================
def test_annotation(r: TestResult) -> None:
    """Annotation 데이터클래스 검증"""
    from shared.dto.media_dto import Annotation, AnnotationType

    # 기본값 생성
    a = Annotation()
    r.true("annotation_id는 UUID", isinstance(a.annotation_id, UUID))
    r.eq("기본 annotation_type", a.annotation_type, AnnotationType.ARROW)
    r.eq("기본 frame_start", a.frame_start, 0)
    r.eq("기본 color", a.color, "#FF0000")
    r.eq("기본 thickness", a.thickness, 2)
    r.eq("기본 opacity", a.opacity, 1.0)
    r.true("end_x is None", a.end_x is None)
    r.true("text is None", a.text is None)

    # 전체 인자 생성
    a2 = Annotation(
        annotation_type=AnnotationType.TEXT,
        frame_start=100, frame_end=200,
        position_x=0.5, position_y=0.3,
        end_x=0.8, end_y=0.9,
        color="#00FF00", text="좋은 플레이!",
        thickness=3, opacity=0.8,
    )
    r.eq("a2 type", a2.annotation_type, AnnotationType.TEXT)
    r.eq("a2 text", a2.text, "좋은 플레이!")
    r.eq("a2 end_x", a2.end_x, 0.8)

    # UUID 독립성
    a3 = Annotation()
    r.true("UUID 독립성", a.annotation_id != a3.annotation_id)


# ==================== 5. VideoClip ====================
def test_video_clip(r: TestResult) -> None:
    """VideoClip 데이터클래스 검증"""
    from shared.dto.media_dto import VideoClip, Annotation

    # 기본값 생성
    vc = VideoClip()
    r.true("clip_id는 UUID", isinstance(vc.clip_id, UUID))
    r.eq("기본 source_video_path", vc.source_video_path, "")
    r.true("camera_id is None", vc.camera_id is None)
    r.eq("기본 annotations", vc.annotations, [])
    r.eq("기본 tags", vc.tags, [])
    r.eq("기본 duration_seconds", vc.duration_seconds, 0.0)

    # __post_init__ duration 자동계산
    vc2 = VideoClip(
        source_video_path="/video/game01.mp4",
        camera_id="cam_01",
        start_frame=0, end_frame=900,
        start_time=0.0, end_time=30.0,
        title="하이라이트 클립",
        tags=["dunk", "fastbreak"],
    )
    r.eq("duration 자동계산", vc2.duration_seconds, 30.0)
    r.eq("title", vc2.title, "하이라이트 클립")

    # duration 직접 지정 시 자동계산 안 함
    vc3 = VideoClip(start_time=0.0, end_time=10.0, duration_seconds=15.0)
    r.eq("duration 직접지정 유지", vc3.duration_seconds, 15.0)

    # 주석 첨부
    ann = Annotation(frame_start=10, frame_end=50)
    vc4 = VideoClip(annotations=[ann])
    r.eq("주석 수", len(vc4.annotations), 1)

    # 리스트 필드 독립성
    vc5 = VideoClip()
    r.true("annotations 독립성", vc.annotations is not vc5.annotations)


# ==================== 6. MultiAngleClip ====================
def test_multi_angle_clip(r: TestResult) -> None:
    """MultiAngleClip 데이터클래스 검증"""
    from shared.dto.media_dto import MultiAngleClip, VideoClip

    # 기본값
    mac = MultiAngleClip()
    r.true("multi_clip_id는 UUID", isinstance(mac.multi_clip_id, UUID))
    r.true("primary_clip is None", mac.primary_clip is None)
    r.eq("기본 layout", mac.layout, "side_by_side")
    r.eq("total_angles (no primary)", mac.total_angles, 0)

    # 프라이머리 + 앵글
    primary = VideoClip(source_video_path="/v/main.mp4")
    angle1 = VideoClip(source_video_path="/v/angle1.mp4")
    angle2 = VideoClip(source_video_path="/v/angle2.mp4")
    mac2 = MultiAngleClip(
        primary_clip=primary,
        angle_clips=[angle1, angle2],
        sync_offset_ms={"cam_01": 0.0, "cam_02": 50.0},
        layout="grid",
    )
    r.eq("total_angles (1+2)", mac2.total_angles, 3)
    r.eq("sync_offset cam_02", mac2.sync_offset_ms["cam_02"], 50.0)
    r.eq("layout", mac2.layout, "grid")

    # 앵글만 (프라이머리 없음)
    mac3 = MultiAngleClip(angle_clips=[angle1])
    r.eq("total_angles (no primary, 1 angle)", mac3.total_angles, 1)


# ==================== 7. CoachingPoint ====================
def test_coaching_point(r: TestResult) -> None:
    """CoachingPoint 데이터클래스 검증"""
    from shared.dto.media_dto import CoachingPoint, Annotation, AnnotationType

    # 기본값
    cp = CoachingPoint()
    r.true("point_id는 UUID", isinstance(cp.point_id, UUID))
    r.true("clip_id is None", cp.clip_id is None)
    r.eq("기본 category", cp.category, "tactical")
    r.eq("기본 priority", cp.priority, 3)
    r.true("reference_play is None", cp.reference_play is None)

    # 전체 인자
    from uuid import uuid4
    cid = uuid4()
    ann = Annotation(annotation_type=AnnotationType.CIRCLE, position_x=0.5, position_y=0.5)
    cp2 = CoachingPoint(
        clip_id=cid,
        frame_number=450,
        title="스크린 세팅 오류",
        description="볼핸들러가 스크린 세팅 전에 이동을 시작했습니다",
        category="correction",
        priority=1,
        annotations=[ann],
        reference_play="reference_screen_play_001",
    )
    r.eq("clip_id", cp2.clip_id, cid)
    r.eq("frame_number", cp2.frame_number, 450)
    r.eq("category", cp2.category, "correction")
    r.eq("annotations 수", len(cp2.annotations), 1)
    r.eq("reference_play", cp2.reference_play, "reference_screen_play_001")


# ==================== 8. PlayerClipPackage ====================
def test_player_clip_package(r: TestResult) -> None:
    """PlayerClipPackage 데이터클래스 검증"""
    from shared.dto.media_dto import PlayerClipPackage, VideoClip, CoachingPoint

    # 기본값
    pkg = PlayerClipPackage()
    r.true("package_id는 UUID", isinstance(pkg.package_id, UUID))
    r.eq("기본 player_tracking_id", pkg.player_tracking_id, 0)
    r.eq("total_clips (빈)", pkg.total_clips, 0)

    # 클립 채우기
    off = [VideoClip() for _ in range(3)]
    deff = [VideoClip() for _ in range(2)]
    spec = [VideoClip()]
    cp = CoachingPoint(title="개선 포인트")
    pkg2 = PlayerClipPackage(
        player_tracking_id=7,
        offensive_clips=off,
        defensive_clips=deff,
        special_clips=spec,
        coaching_points=[cp],
        strengths_summary=["빠른 전환", "좋은 슈팅 선택"],
        improvements_summary=["수비 전환 속도"],
    )
    r.eq("total_clips (3+2+1)", pkg2.total_clips, 6)
    r.eq("coaching_points 수", len(pkg2.coaching_points), 1)
    r.eq("strengths 수", len(pkg2.strengths_summary), 2)
    r.eq("improvements 수", len(pkg2.improvements_summary), 1)

    # 리스트 독립성
    pkg3 = PlayerClipPackage()
    r.true("offensive_clips 독립", pkg.offensive_clips is not pkg3.offensive_clips)


# ==================== 9. FilmSessionData ====================
def test_film_session_data(r: TestResult) -> None:
    """FilmSessionData 데이터클래스 검증"""
    from shared.dto.media_dto import FilmSessionData, VideoClip, CoachingPoint, PlayerClipPackage
    from datetime import datetime, timezone
    from uuid import uuid4

    # 기본값
    fs = FilmSessionData()
    r.true("session_id는 UUID", isinstance(fs.session_id, UUID))
    r.eq("기본 session_type", fs.session_type, "post_game")
    r.eq("기본 title", fs.title, "")
    r.true("created_at는 datetime", isinstance(fs.created_at, datetime))
    r.true("created_at has tzinfo", fs.created_at.tzinfo is not None)

    # 전체 인자
    clip1 = VideoClip(start_time=0.0, end_time=5.0)
    clip2 = VideoClip(start_time=10.0, end_time=15.0)
    cp = CoachingPoint(title="전술 포인트")
    pkg = PlayerClipPackage(player_tracking_id=5)
    pair = (uuid4(), uuid4())
    fs2 = FilmSessionData(
        session_type="weekly",
        title="주간 리뷰 2026-W07",
        clips=[clip1, clip2],
        coaching_points=[cp],
        player_packages=[pkg],
        comparison_pairs=[pair],
        estimated_duration_minutes=45,
    )
    r.eq("session_type", fs2.session_type, "weekly")
    r.eq("clips 수", len(fs2.clips), 2)
    r.eq("comparison_pairs 수", len(fs2.comparison_pairs), 1)
    r.eq("estimated_duration_minutes", fs2.estimated_duration_minutes, 45)

    # UUID 독립성
    fs3 = FilmSessionData()
    r.true("session_id 독립", fs.session_id != fs3.session_id)


# ==================== 10. ExportConfig ====================
def test_export_config(r: TestResult) -> None:
    """ExportConfig 데이터클래스 검증"""
    from shared.dto.media_dto import ExportConfig, ExportFormat

    # 기본값
    ec = ExportConfig()
    r.eq("기본 format", ec.format, ExportFormat.MP4)
    r.eq("기본 resolution", ec.resolution, (1920, 1080))
    r.eq("기본 fps", ec.fps, 30)
    r.eq("기본 bitrate_mbps", ec.bitrate_mbps, 8.0)
    r.true("include_annotations", ec.include_annotations)
    r.true("include_audio", ec.include_audio)
    r.true("watermark is None", ec.watermark is None)
    r.eq("기본 output_path", ec.output_path, "")

    # 커스텀 설정
    ec2 = ExportConfig(
        format=ExportFormat.MOV,
        resolution=(3840, 2160),
        fps=60,
        bitrate_mbps=20.0,
        include_annotations=False,
        include_audio=False,
        watermark="COURTVIEW",
        output_path="/exports/game_01.mov",
    )
    r.eq("format MOV", ec2.format, ExportFormat.MOV)
    r.eq("resolution 4K", ec2.resolution, (3840, 2160))
    r.eq("fps 60", ec2.fps, 60)
    r.eq("watermark", ec2.watermark, "COURTVIEW")
    r.eq("output_path", ec2.output_path, "/exports/game_01.mov")

    # GIF 설정
    ec3 = ExportConfig(format=ExportFormat.GIF, fps=15, resolution=(640, 360))
    r.eq("GIF format", ec3.format, ExportFormat.GIF)
    r.eq("GIF fps", ec3.fps, 15)


# ==================== 11. __all__ Export 검증 ====================
def test_all_exports(r: TestResult) -> None:
    """__all__에 정의된 모든 클래스 임포트 가능 검증"""
    import shared.dto.media_dto as mod

    for name in mod.__all__:
        obj = getattr(mod, name, None)
        r.true(f"export {name} 존재", obj is not None)


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("media_dto.py v1.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 구조 ---")
    test_module_structure(r)

    print("\n--- ExportFormat ---")
    test_export_format(r)

    print("\n--- AnnotationType ---")
    test_annotation_type(r)

    print("\n--- Annotation ---")
    test_annotation(r)

    print("\n--- VideoClip ---")
    test_video_clip(r)

    print("\n--- MultiAngleClip ---")
    test_multi_angle_clip(r)

    print("\n--- CoachingPoint ---")
    test_coaching_point(r)

    print("\n--- PlayerClipPackage ---")
    test_player_clip_package(r)

    print("\n--- FilmSessionData ---")
    test_film_session_data(r)

    print("\n--- ExportConfig ---")
    test_export_config(r)

    print("\n--- __all__ Export ---")
    test_all_exports(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
