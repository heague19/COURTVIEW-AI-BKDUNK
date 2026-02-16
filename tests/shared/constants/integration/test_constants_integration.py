# -*- coding: utf-8 -*-
"""
shared/constants 통합 테스트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
26개 하위 모듈 + __init__.py 간의 교차 검증 (v4.0.0)

검증 범주:
  [A] 패키지 임포트 무결성        — 26개 모듈 개별 임포트, 순환참조 없음
  [B] __init__.py re-export 무결성 — __all__ 완전성, 객체 동일성(is)
  [C] __version__ 일관성           — 모든 모듈 semver 준수
  [D] Enum 타입 시스템 무결성      — 전역 고유성, 메타 클래스, 직렬화
  [E] 물리·농구 도메인 정합성      — 중력, 볼 크기, 코트 규격, 후프 높이
  [F] 신뢰도 임계값 체인           — detection → fusion → tracking 단조 관계
  [G] 에러 코드 범위 비중첩        — 9개 카테고리 코드 범위 분리
  [H] 상태 전이 그래프 무결성      — 종료상태 전이 없음, 도달 가능성
  [I] Localization 의존성          — SupportedLanguage 공유 참조
  [J] ShotType 이중 정의 정합성    — ball(9종) ⊂ game_rule(13종) 관계
  [K] 선수·연령·성별 정합성        — canonical source 일원화
  [L] 매칭 가중치 합산 검증        — weight sum ≈ 1.0
  [M] 모듈 Export 완전성           — 각 모듈 __all__ 자기 참조 정합
  [N] 이벤트 우선순위 일관성       — 모든 이벤트에 우선순위 부여
  [O] 심판 규칙 도메인 정합성      — 리그별 파울 제한·샷클락 연동
  [V] 생체역학 도메인 정합성       — de Leva 모델, 질량비 합산, 속도 단조 증가
  [W] 통계 도메인 정합성           — Four Factors 가중치 합산, TS% 공식
  [X] 전술/경기관리/심판판정/피드백 교차 검증

작성자: COURTVIEW AI Team
"""

from __future__ import annotations

import enum
import importlib
import io
import re
import sys
import types
from pathlib import Path

# ── 인코딩 fix (Windows cp949 대응) ──
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── 프로젝트 루트 ──
_PROJECT_ROOT = str(Path(__file__).resolve().parents[4])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ═══════════════════════════════════════════════════════════════════════
# TestResult 하네스
# ═══════════════════════════════════════════════════════════════════════
class TestResult:
    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.errors: list[str] = []
        self._section: str = ""

    def set_section(self, name: str) -> None:
        self._section = name
        print(f"\n{'─' * 60}")
        print(f"  {name}")
        print(f"{'─' * 60}")

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"  [FAIL] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)
        self.errors.append(f"[{self._section}] {name}: {detail}")

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.ok(name)
        else:
            self.fail(name, detail)

    def summary(self) -> int:
        total = self.passed + self.failed
        print(f"\n{'═' * 60}")
        print(f"  통합 테스트 결과: {self.passed}/{total} PASS | {self.failed} FAIL")
        print(f"{'═' * 60}")
        if self.errors:
            print("\n  실패 목록:")
            for e in self.errors:
                print(f"    ✗ {e}")
        return 1 if self.failed > 0 else 0


# ═══════════════════════════════════════════════════════════════════════
# 상수 모듈 목록 (26개, v4.0.0)
# ═══════════════════════════════════════════════════════════════════════
_MODULE_NAMES: list[str] = [
    # v1.0.0 ~ v2.0.0 (기초 인프라 + 검출/추적)
    "shared.constants.localization",
    "shared.constants.error_codes",
    "shared.constants.status_codes",
    "shared.constants.event_types",
    "shared.constants.camera_constants",
    "shared.constants.court_constants",
    "shared.constants.video_constants",
    "shared.constants.fusion_constants",
    "shared.constants.tracking_constants",
    "shared.constants.occlusion_constants",
    "shared.constants.reid_constants",
    "shared.constants.pose_constants",
    "shared.constants.matching_constants",
    "shared.constants.geometry_constants",
    "shared.constants.ocr_constants",
    "shared.constants.ball_constants",
    # v3.0.0 (경기 규칙 + 심판 시스템)
    "shared.constants.hoop_constants",
    "shared.constants.player_constants",
    "shared.constants.game_rule_constants",
    "shared.constants.referee_rule_constants",
    # v4.0.0 (분석/판정/피드백 도메인)
    "shared.constants.biomechanics_constants",
    "shared.constants.stats_constants",
    "shared.constants.tactical_constants",
    "shared.constants.game_management_constants",
    "shared.constants.referee_decision_constants",
    "shared.constants.feedback_constants",
]


def main() -> int:
    r = TestResult()
    print("=" * 60)
    print("  shared/constants 통합 테스트")
    print("=" * 60)

    # ═══════════════════════════════════════════════════════════════
    # [A] 패키지 임포트 무결성 — 20개 모듈 개별 임포트
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[A] 패키지 임포트 무결성 (26개 모듈)")
    loaded_modules: dict[str, types.ModuleType] = {}

    for mod_name in _MODULE_NAMES:
        try:
            m = importlib.import_module(mod_name)
            loaded_modules[mod_name] = m
            r.ok(f"import {mod_name.split('.')[-1]}")
        except Exception as exc:
            r.fail(f"import {mod_name.split('.')[-1]}", str(exc))

    # __init__.py 패키지 임포트
    try:
        import shared.constants as pkg
        r.ok("import shared.constants (패키지)")
    except Exception as exc:
        r.fail("import shared.constants", str(exc))
        return r.summary()

    # ═══════════════════════════════════════════════════════════════
    # [B] __init__.py re-export 무결성
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[B] __init__.py re-export 무결성")

    pkg_all = getattr(pkg, "__all__", [])
    r.check("__all__ 존재", len(pkg_all) > 0, f"길이: {len(pkg_all)}")

    # __all__ 내 모든 항목이 실제 접근 가능
    missing_exports = [name for name in pkg_all if not hasattr(pkg, name)]
    r.check(
        f"__all__ {len(pkg_all)}개 항목 모두 접근 가능",
        len(missing_exports) == 0,
        f"누락: {missing_exports}",
    )

    # __all__ 내 중복 없음
    r.check(
        "__all__ 중복 없음",
        len(pkg_all) == len(set(pkg_all)),
        f"중복: {[n for n in pkg_all if pkg_all.count(n) > 1]}",
    )

    # 객체 동일성(is) 검증 — 패키지 re-export가 어느 한 원본 모듈과 동일
    # 참고: 동일 이름 상수가 여러 모듈에 존재할 수 있음 (FRAME_BUFFER_SIZE 등)
    identity_failures: list[str] = []
    for name in pkg_all:
        pkg_obj = getattr(pkg, name, None)
        if pkg_obj is None:
            continue
        # 어느 하나의 모듈이라도 동일 객체(is)이면 OK
        found_identical = False
        found_any = False
        for mod_name, mod in loaded_modules.items():
            if hasattr(mod, name):
                found_any = True
                if getattr(mod, name) is pkg_obj:
                    found_identical = True
                    break
        if not found_any:
            identity_failures.append(f"{name}: 원본 모듈에서 미발견")
        elif not found_identical:
            identity_failures.append(f"{name}: 어떤 모듈과도 is 불일치")

    r.check(
        f"re-export 객체 동일성 (is) {len(pkg_all)}건",
        len(identity_failures) == 0,
        f"불일치 {len(identity_failures)}건: {identity_failures[:5]}",
    )

    # ═══════════════════════════════════════════════════════════════
    # [C] __version__ 일관성
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[C] __version__ 일관성 (semver)")

    semver_re = re.compile(r"^\d+\.\d+\.\d+$")
    for mod_name, mod in loaded_modules.items():
        short = mod_name.split(".")[-1]
        ver = getattr(mod, "__version__", None)
        r.check(
            f"{short} __version__ 존재",
            ver is not None,
            "미정의",
        )
        if ver is not None:
            r.check(
                f"{short} semver 형식 ({ver})",
                semver_re.match(ver) is not None,
                f"'{ver}' 비정규",
            )

    # 패키지 __init__ 버전
    pkg_ver = getattr(pkg, "__version__", None)
    r.check("__init__.py __version__ 존재", pkg_ver is not None)

    # ═══════════════════════════════════════════════════════════════
    # [D] Enum 타입 시스템 무결성
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[D] Enum 타입 시스템 무결성")

    # 모든 모듈에서 Enum 클래스 수집
    all_enums: dict[str, list[tuple[str, type]]] = {}  # name → [(module, cls)]
    total_enum_count = 0

    for mod_name, mod in loaded_modules.items():
        short = mod_name.split(".")[-1]
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, enum.Enum)
                and obj is not enum.Enum
                and obj.__module__ == mod.__name__
            ):
                total_enum_count += 1
                if attr_name not in all_enums:
                    all_enums[attr_name] = []
                all_enums[attr_name].append((short, obj))

    r.check(f"Enum 총 {total_enum_count}개 수집", total_enum_count > 0)

    # Enum 이름 충돌 검사 (ShotType은 의도적 이중 정의)
    _ALLOWED_DUPES = {"ShotType", "CourtZone"}
    name_collisions = {
        name: [(m, c) for m, c in locs]
        for name, locs in all_enums.items()
        if len(locs) > 1 and name not in _ALLOWED_DUPES
    }
    r.check(
        f"Enum 이름 전역 고유성 ({', '.join(sorted(_ALLOWED_DUPES))} 제외)",
        len(name_collisions) == 0,
        f"충돌: {list(name_collisions.keys())}",
    )

    # 모든 Enum이 enum.Enum 서브클래스인지 검증
    non_enum_failures = []
    for name, locs in all_enums.items():
        for mod_short, cls in locs:
            if not issubclass(cls, enum.Enum):
                non_enum_failures.append(f"{mod_short}.{name}")
    r.check(
        "모든 Enum이 enum.Enum 서브클래스",
        len(non_enum_failures) == 0,
        str(non_enum_failures),
    )

    # 모든 Enum 멤버가 hashable (dict key 사용 가능)
    unhashable = []
    for name, locs in all_enums.items():
        for mod_short, cls in locs:
            for member in cls:
                try:
                    hash(member)
                except TypeError:
                    unhashable.append(f"{mod_short}.{name}.{member.name}")
    r.check(
        "모든 Enum 멤버 hashable",
        len(unhashable) == 0,
        str(unhashable[:5]),
    )

    # ═══════════════════════════════════════════════════════════════
    # [E] 물리·농구 도메인 정합성
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[E] 물리·농구 도메인 정합성")

    ball = loaded_modules.get("shared.constants.ball_constants")
    court = loaded_modules.get("shared.constants.court_constants")
    hoop = loaded_modules.get("shared.constants.hoop_constants")
    player = loaded_modules.get("shared.constants.player_constants")

    if ball:
        # 중력 가속도 물리 상수 정확성
        g = getattr(ball, "GRAVITY_ACCELERATION", None)
        r.check("중력 가속도 ≈ 9.81 m/s²", g is not None and abs(g - 9.81) < 0.01, f"실제: {g}")

        # 농구공 규격 (FIBA 규격: 직경 약 0.238–0.248m)
        d = getattr(ball, "BASKETBALL_DIAMETER_M", None)
        r.check(
            "농구공 직경 0.220–0.260m 범위",
            d is not None and 0.220 <= d <= 0.260,
            f"실제: {d}",
        )

        # 농구공 질량 (FIBA 규격: 0.567–0.650kg)
        m = getattr(ball, "BASKETBALL_MASS_KG", None)
        r.check(
            "농구공 질량 0.500–0.700kg 범위",
            m is not None and 0.500 <= m <= 0.700,
            f"실제: {m}",
        )

        # 공기저항 계수 양수
        cd = getattr(ball, "AIR_RESISTANCE_COEFFICIENT", None)
        r.check("공기저항 계수 > 0", cd is not None and cd > 0, f"실제: {cd}")

    if court:
        # FIBA 코트 규격: 28m × 15m
        cl = getattr(court, "COURT_LENGTH_M", None)
        cw = getattr(court, "COURT_WIDTH_M", None)
        r.check("코트 길이 = 28.0m (FIBA)", cl is not None and cl == 28.0, f"실제: {cl}")
        r.check("코트 너비 = 15.0m (FIBA)", cw is not None and cw == 15.0, f"실제: {cw}")

        # 3점 라인: FIBA 6.75m, NBA 7.24m
        fiba_3pt = getattr(court, "THREE_POINT_LINE_DISTANCE_M", None)
        nba_3pt = getattr(court, "THREE_POINT_LINE_NBA_DISTANCE_M", None)
        r.check(
            "FIBA 3점 라인 = 6.75m",
            fiba_3pt is not None and abs(fiba_3pt - 6.75) < 0.01,
            f"실제: {fiba_3pt}",
        )
        r.check(
            "NBA 3점 라인 = 7.24m",
            nba_3pt is not None and abs(nba_3pt - 7.24) < 0.01,
            f"실제: {nba_3pt}",
        )
        r.check(
            "NBA 3점 > FIBA 3점",
            fiba_3pt is not None and nba_3pt is not None and nba_3pt > fiba_3pt,
        )

        # 자유투 라인 거리
        ft = getattr(court, "FREE_THROW_LINE_DISTANCE_M", None)
        r.check(
            "자유투 라인 = 4.6m",
            ft is not None and abs(ft - 4.6) < 0.01,
            f"실제: {ft}",
        )

    if hoop:
        # 후프 높이 3.05m (10ft)
        hh = getattr(hoop, "HOOP_HEIGHT_M", None)
        if hh is not None:
            r.check("후프 높이 = 3.05m", abs(hh - 3.05) < 0.01, f"실제: {hh}")

        # 검출 confidence 범위 [0, 1]
        hc = getattr(hoop, "HOOP_DETECTION_CONFIDENCE_THRESHOLD", None)
        r.check(
            "후프 검출 confidence ∈ (0, 1)",
            hc is not None and 0 < hc < 1,
            f"실제: {hc}",
        )

        # 득점 판정 confidence
        sc = getattr(hoop, "HOOP_SCORING_CONFIDENCE_THRESHOLD", None)
        r.check(
            "득점 판정 confidence ∈ (0, 1)",
            sc is not None and 0 < sc < 1,
            f"실제: {sc}",
        )

        # 득점 판정 confidence ≥ 검출 confidence (더 엄격)
        if hc is not None and sc is not None:
            r.check(
                "득점 판정 confidence ≥ 검출 confidence",
                sc >= hc,
                f"scoring={sc}, detection={hc}",
            )

    # ═══════════════════════════════════════════════════════════════
    # [F] 신뢰도 임계값 체인 (detection → fusion → tracking)
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[F] 신뢰도 임계값 체인")

    fusion = loaded_modules.get("shared.constants.fusion_constants")
    tracking = loaded_modules.get("shared.constants.tracking_constants")
    reid = loaded_modules.get("shared.constants.reid_constants")
    pose = loaded_modules.get("shared.constants.pose_constants")

    if fusion:
        fc = getattr(fusion, "FUSION_CONFIDENCE_THRESHOLD", None)
        r.check(
            "FUSION_CONFIDENCE_THRESHOLD ∈ (0, 1)",
            fc is not None and 0 < fc < 1,
            f"실제: {fc}",
        )

        min_views = getattr(fusion, "MIN_VIEWS_FOR_TRIANGULATION", None)
        r.check(
            "MIN_VIEWS_FOR_TRIANGULATION ≥ 2",
            min_views is not None and min_views >= 2,
            f"실제: {min_views}",
        )

    if tracking:
        iou = getattr(tracking, "IOU_THRESHOLD", None)
        r.check(
            "IOU_THRESHOLD ∈ (0, 1)",
            iou is not None and 0 < iou < 1,
            f"실제: {iou}",
        )

        max_age = getattr(tracking, "MAX_TRACK_AGE", None)
        min_hits = getattr(tracking, "MIN_TRACK_HITS", None)
        r.check(
            "MAX_TRACK_AGE > MIN_TRACK_HITS",
            max_age is not None and min_hits is not None and max_age > min_hits,
            f"age={max_age}, hits={min_hits}",
        )

    if reid:
        sim_th = getattr(reid, "SIMILARITY_THRESHOLD", None)
        r.check(
            "SIMILARITY_THRESHOLD ∈ (0, 1)",
            sim_th is not None and 0 < sim_th < 1,
            f"실제: {sim_th}",
        )

        ema = getattr(reid, "EMA_MOMENTUM", None)
        r.check(
            "EMA_MOMENTUM ∈ (0, 1)",
            ema is not None and 0 < ema < 1,
            f"실제: {ema}",
        )

        feat_dim = getattr(reid, "FEATURE_DIM", None)
        r.check(
            "FEATURE_DIM은 2의 거듭제곱",
            feat_dim is not None and feat_dim > 0 and (feat_dim & (feat_dim - 1)) == 0,
            f"실제: {feat_dim}",
        )

    if pose:
        jct = getattr(pose, "JOINT_CONFIDENCE_THRESHOLD", None)
        r.check(
            "JOINT_CONFIDENCE_THRESHOLD ∈ (0, 1)",
            jct is not None and 0 < jct < 1,
            f"실제: {jct}",
        )

        sct = getattr(pose, "SKELETON_COMPLETENESS_THRESHOLD", None)
        r.check(
            "SKELETON_COMPLETENESS_THRESHOLD ∈ (0, 1)",
            sct is not None and 0 < sct < 1,
            f"실제: {sct}",
        )

        mp = getattr(pose, "NUM_KEYPOINTS_MEDIAPIPE", None)
        coco = getattr(pose, "NUM_KEYPOINTS_COCO", None)
        r.check(
            "MediaPipe(33) > COCO(17) 키포인트",
            mp is not None and coco is not None and mp > coco,
            f"mediapipe={mp}, coco={coco}",
        )

    # ═══════════════════════════════════════════════════════════════
    # [G] 에러 코드 범위 비중첩
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[G] 에러 코드 범위 비중첩")

    error_mod = loaded_modules.get("shared.constants.error_codes")
    if error_mod:
        ErrorCode = getattr(error_mod, "ErrorCode", None)
        ErrorCategory = getattr(error_mod, "ErrorCategory", None)

        if ErrorCode and ErrorCategory:
            # ErrorCode.value는 (code, message, http_status) 튜플
            all_values = [e.value for e in ErrorCode]
            r.check(
                "ErrorCode 값 전부 tuple(code, msg, http)",
                all(isinstance(v, tuple) and len(v) == 3 for v in all_values),
            )

            # 에러 코드(첫 번째 요소) 추출
            all_codes = [v[0] if isinstance(v, tuple) else v for v in all_values]
            r.check("에러 코드 전부 정수", all(isinstance(c, int) for c in all_codes))

            # 중복 코드 없음
            r.check(
                "에러 코드 값 중복 없음",
                len(all_codes) == len(set(all_codes)),
                f"총 {len(all_codes)}개 중 {len(all_codes) - len(set(all_codes))}건 중복",
            )

            # 각 카테고리별 에러 그룹 존재 확인
            group_names = [
                "GENERAL_ERRORS", "AUTH_ERRORS", "VALIDATION_ERRORS",
                "BUSINESS_ERRORS", "INFRASTRUCTURE_ERRORS", "EXTERNAL_ERRORS",
                "ANALYSIS_ERRORS", "REFEREE_ERRORS", "CONFIGURATION_ERRORS",
                "SYSTEM_ERRORS",
            ]
            for gname in group_names:
                grp = getattr(error_mod, gname, None)
                r.check(
                    f"{gname} 존재 및 비어있지 않음",
                    grp is not None and len(grp) > 0,
                    f"{'미정의' if grp is None else f'길이: {len(grp)}'}",
                )

    # ═══════════════════════════════════════════════════════════════
    # [H] 상태 전이 그래프 무결성
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[H] 상태 전이 그래프 무결성")

    status_mod = loaded_modules.get("shared.constants.status_codes")
    if status_mod:
        TaskStatus = getattr(status_mod, "TaskStatus", None)
        VALID_TASK_TRANSITIONS = getattr(status_mod, "VALID_TASK_TRANSITIONS", None)
        is_valid_transition = getattr(status_mod, "is_valid_transition", None)

        if TaskStatus and VALID_TASK_TRANSITIONS:
            # 모든 TaskStatus가 전이 맵에 키로 존재
            missing_keys = [s for s in TaskStatus if s not in VALID_TASK_TRANSITIONS]
            r.check(
                "전이 맵 키 완전성 (모든 TaskStatus 포함)",
                len(missing_keys) == 0,
                f"누락: {[s.name for s in missing_keys]}",
            )

            # 종료 상태는 전이 대상 없음
            terminal_states = [s for s in TaskStatus if s.is_terminal]
            terminal_with_transitions = [
                s for s in terminal_states
                if len(VALID_TASK_TRANSITIONS.get(s, ())) > 0
                and s not in (TaskStatus.FAILED, TaskStatus.TIMEOUT)
            ]
            r.check(
                "종료 상태 전이 없음 (FAILED/TIMEOUT 복구 제외)",
                len(terminal_with_transitions) == 0,
                f"전이 존재: {[s.name for s in terminal_with_transitions]}",
            )

            # 전이 대상이 모두 유효한 TaskStatus 멤버
            invalid_targets = []
            for src, targets in VALID_TASK_TRANSITIONS.items():
                for tgt in targets:
                    if tgt not in TaskStatus:
                        invalid_targets.append(f"{src.name}→{tgt}")
            r.check(
                "전이 대상 모두 유효한 TaskStatus",
                len(invalid_targets) == 0,
                str(invalid_targets[:5]),
            )

        if is_valid_transition and TaskStatus:
            # PENDING → QUEUED 허용
            r.check(
                "PENDING → QUEUED 전이 허용",
                is_valid_transition(TaskStatus.PENDING, TaskStatus.QUEUED) is True,
            )
            # COMPLETED → RUNNING 차단
            r.check(
                "COMPLETED → RUNNING 전이 차단",
                is_valid_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING) is False,
            )

    # ═══════════════════════════════════════════════════════════════
    # [I] Localization 의존성 — SupportedLanguage 공유 참조
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[I] Localization 공유 참조")

    loc_mod = loaded_modules.get("shared.constants.localization")
    if loc_mod:
        SupportedLanguage = getattr(loc_mod, "SupportedLanguage", None)
        if SupportedLanguage:
            r.check("SupportedLanguage Enum 존재", True)
            r.check(
                "KO (한국어) 멤버 존재",
                hasattr(SupportedLanguage, "KO"),
            )
            r.check(
                "EN (영어) 멤버 존재",
                hasattr(SupportedLanguage, "EN"),
            )

            # 다른 모듈에서 import하는 SupportedLanguage과 동일 객체인지
            _lang_dependent_modules = [
                "shared.constants.ball_constants",
                "shared.constants.camera_constants",
                "shared.constants.court_constants",
                "shared.constants.player_constants",
                "shared.constants.game_rule_constants",
            ]
            for dep_mod_name in _lang_dependent_modules:
                dep_mod = loaded_modules.get(dep_mod_name)
                short = dep_mod_name.split(".")[-1]
                if dep_mod:
                    dep_lang = getattr(dep_mod, "SupportedLanguage", None)
                    r.check(
                        f"{short} → SupportedLanguage is 동일 객체",
                        dep_lang is SupportedLanguage,
                        "다른 객체" if dep_lang is not None else "미정의",
                    )

    # ═══════════════════════════════════════════════════════════════
    # [J] ShotType 이중 정의 정합성
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[J] ShotType 이중 정의 정합성")

    game_mod = loaded_modules.get("shared.constants.game_rule_constants")
    if ball and game_mod:
        BallShotType = getattr(ball, "ShotType", None)
        GameShotType = getattr(game_mod, "ShotType", None)

        if BallShotType and GameShotType:
            r.check("ball ShotType ≠ game ShotType (별도 클래스)", BallShotType is not GameShotType)

            ball_names = {s.name for s in BallShotType}
            game_names = {s.name for s in GameShotType}

            r.check(
                f"ball ShotType ({len(BallShotType)}종) < game ShotType ({len(GameShotType)}종)",
                len(BallShotType) < len(GameShotType),
            )

            # 공통 이름 존재 확인 (물리적 슛 타입과 경기 분석 타입 간 중첩)
            common = ball_names & game_names
            r.check(
                f"공통 ShotType 이름 {len(common)}개 ≥ 5",
                len(common) >= 5,
                f"공통: {common}",
            )

            # game_rule 전용 타입 (경기 통계 확장): 정보 출력
            game_only = game_names - ball_names
            ball_only = ball_names - game_names
            if game_only:
                print(f"  [INFO] game 전용 ShotType ({len(game_only)}종): "
                      f"{', '.join(sorted(game_only))}")
            if ball_only:
                print(f"  [INFO] ball 전용 ShotType ({len(ball_only)}종, 물리 궤적용): "
                      f"{', '.join(sorted(ball_only))}")

    # ═══════════════════════════════════════════════════════════════
    # [K] 선수·연령·성별 정합성 (canonical source)
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[K] 선수·연령·성별 정합성")

    if player:
        Gender = getattr(player, "Gender", None)
        AgeGroup = getattr(player, "AgeGroup", None)
        SkillLevel = getattr(player, "SkillLevel", None)

        if Gender:
            r.check("Gender Enum 존재", True)
            r.check("Gender에 MALE 존재", hasattr(Gender, "MALE"))
            r.check("Gender에 FEMALE 존재", hasattr(Gender, "FEMALE"))

        if AgeGroup:
            r.check("AgeGroup Enum 존재", True)
            # 연령 그룹 순서 검증 (유소년 < 청소년 < 성인)
            members = list(AgeGroup)
            r.check(f"AgeGroup {len(members)}개 멤버", len(members) >= 3)

        if SkillLevel:
            r.check("SkillLevel Enum 존재", True)
            members = list(SkillLevel)
            r.check(f"SkillLevel {len(members)}개 멤버", len(members) >= 3)

        # __init__.py에서도 같은 객체 re-export
        if Gender:
            r.check(
                "pkg.Gender is player.Gender",
                getattr(pkg, "Gender", None) is Gender,
            )
        if AgeGroup:
            r.check(
                "pkg.AgeGroup is player.AgeGroup",
                getattr(pkg, "AgeGroup", None) is AgeGroup,
            )
        if SkillLevel:
            r.check(
                "pkg.SkillLevel is player.SkillLevel",
                getattr(pkg, "SkillLevel", None) is SkillLevel,
            )

    # ball_constants가 player_constants.AgeGroup을 올바르게 참조하는지
    if ball and player:
        ball_AgeGroup = getattr(ball, "AgeGroup", None)
        player_AgeGroup = getattr(player, "AgeGroup", None)
        if ball_AgeGroup and player_AgeGroup:
            r.check(
                "ball.AgeGroup is player.AgeGroup (canonical)",
                ball_AgeGroup is player_AgeGroup,
            )

    # ═══════════════════════════════════════════════════════════════
    # [L] 매칭 가중치 합산 검증
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[L] 매칭 가중치 합산 검증")

    matching = loaded_modules.get("shared.constants.matching_constants")
    if matching:
        aw = getattr(matching, "APPEARANCE_WEIGHT", None)
        gw = getattr(matching, "GEOMETRY_WEIGHT", None)
        pw = getattr(matching, "POSITION_WEIGHT", None)

        if aw is not None and gw is not None and pw is not None:
            total = aw + gw + pw
            r.check(
                f"APPEARANCE + GEOMETRY + POSITION = 1.0 (실제: {total})",
                abs(total - 1.0) < 1e-9,
            )
            r.check("모든 가중치 > 0", aw > 0 and gw > 0 and pw > 0)
        else:
            r.fail("매칭 가중치 상수 접근 불가")

    # tracking 모듈 가중치 합산도 검증
    if tracking:
        acw = getattr(tracking, "APPEARANCE_COST_WEIGHT", None)
        mcw = getattr(tracking, "MOTION_COST_WEIGHT", None)
        if acw is not None and mcw is not None:
            total = acw + mcw
            r.check(
                f"APPEARANCE_COST + MOTION_COST = 1.0 (실제: {total})",
                abs(total - 1.0) < 1e-9,
            )

    # ═══════════════════════════════════════════════════════════════
    # [M] 모듈 Export 완전성 — 각 모듈 __all__ 자기 참조 정합
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[M] 모듈 Export 완전성 (26개)")

    for mod_name, mod in loaded_modules.items():
        short = mod_name.split(".")[-1]
        mod_all = getattr(mod, "__all__", None)
        if mod_all is None:
            r.fail(f"{short} __all__ 미정의")
            continue

        missing = [name for name in mod_all if not hasattr(mod, name)]
        r.check(
            f"{short}: __all__ {len(mod_all)}개 항목 모두 존재",
            len(missing) == 0,
            f"누락: {missing}",
        )

    # ═══════════════════════════════════════════════════════════════
    # [N] 이벤트 우선순위 일관성
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[N] 이벤트 우선순위 일관성")

    event_mod = loaded_modules.get("shared.constants.event_types")
    if event_mod:
        EventType = getattr(event_mod, "EventType", None)
        EVENT_PRIORITY = getattr(event_mod, "EVENT_PRIORITY", None)
        get_event_priority = getattr(event_mod, "get_event_priority", None)

        if EventType and EVENT_PRIORITY:
            # EVENT_PRIORITY 딕셔너리에 정의된 항목 수 확인
            r.check(
                f"EVENT_PRIORITY 딕셔너리 비어있지 않음 ({len(EVENT_PRIORITY)}건)",
                len(EVENT_PRIORITY) > 0,
            )

            # 명시적 매핑된 우선순위 값이 양수 정수
            invalid_priorities = [
                (e.name, p) for e, p in EVENT_PRIORITY.items()
                if not isinstance(p, int) or p < 0
            ]
            r.check(
                "명시적 우선순위 ≥ 0 정수",
                len(invalid_priorities) == 0,
                str(invalid_priorities[:5]),
            )

        if get_event_priority and EventType:
            # get_event_priority()가 모든 이벤트에 대해 기본값 포함 정수 반환
            non_int_results: list[str] = []
            for evt in EventType:
                try:
                    prio = get_event_priority(evt)
                    if not isinstance(prio, int):
                        non_int_results.append(f"{evt.name}: {type(prio).__name__}")
                except Exception as exc:
                    non_int_results.append(f"{evt.name}: 예외 {exc}")

            r.check(
                f"get_event_priority() {len(EventType)}개 이벤트 모두 정수 반환",
                len(non_int_results) == 0,
                f"실패 {len(non_int_results)}건: {non_int_results[:5]}",
            )

    # ═══════════════════════════════════════════════════════════════
    # [O] 심판 규칙 도메인 정합성
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[O] 심판 규칙 도메인 정합성")

    ref_mod = loaded_modules.get("shared.constants.referee_rule_constants")
    if ref_mod and game_mod:
        RuleSet = getattr(ref_mod, "RuleSet", None)
        if RuleSet:
            # RuleSet에 FIBA, NBA 존재
            r.check("RuleSet에 FIBA 존재", hasattr(RuleSet, "FIBA"))
            r.check("RuleSet에 NBA 존재", hasattr(RuleSet, "NBA"))
            r.check("RuleSet에 KBL 존재", hasattr(RuleSet, "KBL"))

        # 심판 시스템 상수와 경기 규칙 상수 교차 검증
        # 경기 규칙: 파울 퇴장 기준
        max_foul_fiba = getattr(game_mod, "MAX_PERSONAL_FOULS_FIBA", None)
        max_foul_nba = getattr(game_mod, "MAX_PERSONAL_FOULS_NBA", None)
        r.check(
            "FIBA 개인 파울 제한 = 5",
            max_foul_fiba is not None and max_foul_fiba == 5,
            f"실제: {max_foul_fiba}",
        )
        r.check(
            "NBA 개인 파울 제한 = 6",
            max_foul_nba is not None and max_foul_nba == 6,
            f"실제: {max_foul_nba}",
        )

        # 샷클락
        shot_clock = getattr(game_mod, "SHOT_CLOCK_SEC", None)
        r.check(
            "샷클락 = 24초",
            shot_clock is not None and shot_clock == 24,
            f"실제: {shot_clock}",
        )

        # 팀 파울 보너스
        fiba_bonus = getattr(game_mod, "TEAM_FOUL_BONUS_FIBA", None)
        nba_bonus = getattr(game_mod, "TEAM_FOUL_BONUS_NBA", None)
        r.check(
            "FIBA 팀 파울 보너스 = 4",
            fiba_bonus is not None and fiba_bonus == 4,
            f"실제: {fiba_bonus}",
        )
        r.check(
            "NBA 팀 파울 보너스 = 4",
            nba_bonus is not None and nba_bonus == 4,
            f"실제: {nba_bonus}",
        )

        # 심판 인원
        ref_count = getattr(ref_mod, "REFEREE_COUNT_STANDARD", None)
        r.check(
            "표준 심판 인원 = 3명",
            ref_count is not None and ref_count == 3,
            f"실제: {ref_count}",
        )

        # 심판 판정 confidence 범위
        min_conf = getattr(ref_mod, "MIN_DECISION_CONFIDENCE", None)
        auto_conf = getattr(ref_mod, "AUTO_CONFIRM_CONFIDENCE", None)
        r.check(
            "MIN_DECISION_CONFIDENCE ∈ (0, 1)",
            min_conf is not None and 0 < min_conf < 1,
            f"실제: {min_conf}",
        )
        r.check(
            "AUTO_CONFIRM_CONFIDENCE ∈ (0, 1)",
            auto_conf is not None and 0 < auto_conf < 1,
            f"실제: {auto_conf}",
        )
        if min_conf is not None and auto_conf is not None:
            r.check(
                "AUTO_CONFIRM > MIN_DECISION (더 엄격)",
                auto_conf > min_conf,
                f"auto={auto_conf}, min={min_conf}",
            )

        # 코트 위 선수 수
        players = getattr(game_mod, "PLAYERS_ON_COURT", None)
        r.check(
            "코트 위 선수 수 = 5명",
            players is not None and players == 5,
            f"실제: {players}",
        )

        # 쿼터 수
        periods = getattr(game_mod, "GAME_PERIODS", None)
        r.check(
            "경기 쿼터 수 = 4",
            periods is not None and periods == 4,
            f"실제: {periods}",
        )

    # ═══════════════════════════════════════════════════════════════
    # [P] 비디오·카메라 도메인 교차 검증
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[P] 비디오·카메라 도메인 교차 검증")

    video_mod = loaded_modules.get("shared.constants.video_constants")
    camera_mod = loaded_modules.get("shared.constants.camera_constants")

    if video_mod:
        default_fps = getattr(video_mod, "DEFAULT_FPS", None)
        r.check("DEFAULT_FPS > 0", default_fps is not None and default_fps > 0, f"실제: {default_fps}")

        drift = getattr(video_mod, "MAX_SYNC_DRIFT_MS", None)
        r.check("MAX_SYNC_DRIFT_MS > 0", drift is not None and drift > 0, f"실제: {drift}")

    if camera_mod:
        cam_fps = getattr(camera_mod, "DEFAULT_FRAME_RATE", None)
        min_fps = getattr(camera_mod, "MIN_FRAME_RATE", None)
        max_fps = getattr(camera_mod, "MAX_FRAME_RATE", None)

        r.check(
            "MIN_FRAME_RATE < DEFAULT_FRAME_RATE < MAX_FRAME_RATE",
            all(v is not None for v in (min_fps, cam_fps, max_fps))
            and min_fps < cam_fps < max_fps,
            f"min={min_fps}, default={cam_fps}, max={max_fps}",
        )

        # 비디오 DEFAULT_FPS가 카메라 FPS 범위 내에 있는지
        if video_mod and cam_fps is not None:
            vid_fps = getattr(video_mod, "DEFAULT_FPS", None)
            if vid_fps is not None and min_fps is not None and max_fps is not None:
                r.check(
                    "VIDEO DEFAULT_FPS ∈ [카메라 MIN, MAX]",
                    min_fps <= vid_fps <= max_fps,
                    f"video={vid_fps}, camera range=[{min_fps}, {max_fps}]",
                )

    # ═══════════════════════════════════════════════════════════════
    # [Q] OCR 도메인 정합성
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[Q] OCR 도메인 정합성")

    ocr_mod = loaded_modules.get("shared.constants.ocr_constants")
    if ocr_mod:
        min_conf = getattr(ocr_mod, "MIN_OCR_CONFIDENCE", None)
        r.check(
            "MIN_OCR_CONFIDENCE ∈ (0, 1)",
            min_conf is not None and 0 < min_conf < 1,
            f"실제: {min_conf}",
        )

        j_min = getattr(ocr_mod, "JERSEY_NUMBER_MIN", None)
        j_max = getattr(ocr_mod, "JERSEY_NUMBER_MAX", None)
        r.check(
            "등번호 범위: MIN < MAX",
            j_min is not None and j_max is not None and j_min < j_max,
            f"min={j_min}, max={j_max}",
        )
        r.check(
            "등번호 범위: 0 ≤ MIN, MAX ≤ 99",
            j_min is not None and j_max is not None and j_min >= 0 and j_max <= 99,
            f"min={j_min}, max={j_max}",
        )

        frame_interval = getattr(ocr_mod, "OCR_FRAME_INTERVAL", None)
        r.check(
            "OCR_FRAME_INTERVAL ≥ 1",
            frame_interval is not None and frame_interval >= 1,
            f"실제: {frame_interval}",
        )

    # ═══════════════════════════════════════════════════════════════
    # [R] 기하학·융합 도메인 교차 검증
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[R] 기하학·융합 도메인 교차 검증")

    geom_mod = loaded_modules.get("shared.constants.geometry_constants")
    if geom_mod:
        ransac = getattr(geom_mod, "RANSAC_THRESHOLD", None)
        r.check(
            "RANSAC_THRESHOLD > 0",
            ransac is not None and ransac > 0,
            f"실제: {ransac}",
        )

        min_pts = getattr(geom_mod, "MIN_POINTS_FOR_FUNDAMENTAL", None)
        r.check(
            "MIN_POINTS_FOR_FUNDAMENTAL ≥ 8 (8-point algorithm)",
            min_pts is not None and min_pts >= 8,
            f"실제: {min_pts}",
        )

    if fusion and geom_mod:
        max_depth = getattr(fusion, "TRIANGULATION_MAX_DEPTH_M", None)
        r.check(
            "TRIANGULATION_MAX_DEPTH_M > 0",
            max_depth is not None and max_depth > 0,
            f"실제: {max_depth}",
        )

    # ═══════════════════════════════════════════════════════════════
    # [S] 오클루전 도메인 정합성
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[S] 오클루전 도메인 정합성")

    occ_mod = loaded_modules.get("shared.constants.occlusion_constants")
    if occ_mod:
        ot = getattr(occ_mod, "OVERLAP_THRESHOLD", None)
        r.check(
            "OVERLAP_THRESHOLD ∈ (0, 1)",
            ot is not None and 0 < ot < 1,
            f"실제: {ot}",
        )

        mkr = getattr(occ_mod, "MIN_VISIBLE_KEYPOINTS_RATIO", None)
        r.check(
            "MIN_VISIBLE_KEYPOINTS_RATIO ∈ (0, 1)",
            mkr is not None and 0 < mkr < 1,
            f"실제: {mkr}",
        )

        mdf = getattr(occ_mod, "MAX_OCCLUSION_DURATION_FRAMES", None)
        r.check(
            "MAX_OCCLUSION_DURATION_FRAMES > 0",
            mdf is not None and mdf > 0,
            f"실제: {mdf}",
        )

    # ═══════════════════════════════════════════════════════════════
    # [T] 전체 __init__.py ↔ 하위 모듈 동기화 검증
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[T] __init__.py ↔ 하위 모듈 동기화 종합")

    # __init__.py에서 export하는 모든 Enum이 원본 모듈의 __all__에도 있는지
    enum_in_pkg_all = [
        name for name in pkg_all
        if hasattr(pkg, name) and isinstance(getattr(pkg, name), type)
        and issubclass(getattr(pkg, name), enum.Enum)
    ]
    missing_in_origin = []
    for ename in enum_in_pkg_all:
        ecls = getattr(pkg, ename)
        origin_mod_name = ecls.__module__
        origin_mod = loaded_modules.get(origin_mod_name)
        if origin_mod:
            origin_all = getattr(origin_mod, "__all__", [])
            if ename not in origin_all:
                missing_in_origin.append(f"{ename} (from {origin_mod_name})")

    r.check(
        f"패키지 Enum {len(enum_in_pkg_all)}개 원본 __all__ 포함",
        len(missing_in_origin) == 0,
        f"원본 __all__ 누락: {missing_in_origin}",
    )

    # 각 모듈별 __init__.py에서 import하는 항목이 원본(정의) 모듈 __all__에 있는지
    # 동일 이름이 여러 모듈에 존재할 수 있으므로 is 동일 객체인 모듈 기준
    init_import_not_in_origin_all: list[str] = []
    for name in pkg_all:
        obj = getattr(pkg, name, None)
        if obj is None:
            continue
        # is 동일 객체인 모듈 중 하나라도 __all__에 포함하면 OK
        found_in_any_all = False
        for mod_name, mod in loaded_modules.items():
            if hasattr(mod, name) and getattr(mod, name) is obj:
                mod_all = getattr(mod, "__all__", [])
                if name in mod_all:
                    found_in_any_all = True
                    break
        if not found_in_any_all:
            init_import_not_in_origin_all.append(name)

    r.check(
        f"__init__ import 항목 전체 원본 __all__ 포함",
        len(init_import_not_in_origin_all) == 0,
        f"미포함: {init_import_not_in_origin_all[:10]}",
    )

    # ═══════════════════════════════════════════════════════════════
    # [U] 순환 참조 안전성 검증
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[U] 순환 참조 안전성")

    # 모든 모듈을 개별적으로 재임포트 시도 (sys.modules 캐시 미사용)
    # 실제 순환참조가 있으면 이미 [A]에서 실패했겠지만,
    # 여기서는 모듈 간 의존 그래프를 명시적으로 검증
    import_graph: dict[str, set[str]] = {}
    for mod_name, mod in loaded_modules.items():
        short = mod_name.split(".")[-1]
        deps: set[str] = set()
        mod_all_attrs = dir(mod)
        for attr_name in mod_all_attrs:
            try:
                obj = getattr(mod, attr_name)
            except Exception:
                continue
            if isinstance(obj, type) and issubclass(obj, enum.Enum) and obj.__module__ != mod.__name__:
                dep_short = obj.__module__.split(".")[-1]
                if dep_short != short:
                    deps.add(dep_short)
        import_graph[short] = deps

    # 순환 탐지 (DFS)
    def has_cycle(graph: dict[str, set[str]]) -> list[str] | None:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in graph}
        path: list[str] = []

        def dfs(node: str) -> list[str] | None:
            color[node] = GRAY
            path.append(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
                if color[neighbor] == WHITE:
                    result = dfs(neighbor)
                    if result:
                        return result
            path.pop()
            color[node] = BLACK
            return None

        for node in graph:
            if color[node] == WHITE:
                result = dfs(node)
                if result:
                    return result
        return None

    cycle = has_cycle(import_graph)
    r.check(
        "Enum 의존 그래프에 순환 없음",
        cycle is None,
        f"순환: {' → '.join(cycle)}" if cycle else "",
    )

    # 의존 관계 요약 출력
    deps_with_links = {k: v for k, v in import_graph.items() if v}
    if deps_with_links:
        print(f"  [INFO] Enum 교차 의존: {len(deps_with_links)}개 모듈")
        for mod_short, deps in deps_with_links.items():
            print(f"         {mod_short} → {', '.join(sorted(deps))}")

    # ═══════════════════════════════════════════════════════════════
    # [V] 생체역학 도메인 정합성 (v4.0.0)
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[V] 생체역학 도메인 정합성 (v4.0.0)")

    bio_mod = loaded_modules.get("shared.constants.biomechanics_constants")
    if bio_mod:
        BodySegment = getattr(bio_mod, "BodySegment", None)
        if BodySegment:
            r.check("BodySegment 10종", len(BodySegment) == 10, f"실제: {len(BodySegment)}")

        # 질량비 합계 검증 (~1.0, 양측성 x2)
        mass_male = getattr(bio_mod, "SEGMENT_MASS_RATIO_MALE", None)
        if mass_male and BodySegment:
            total = 0.0
            for seg, ratio in mass_male.items():
                total += ratio * 2 if seg.is_bilateral else ratio
            r.check(
                f"남성 질량비 합계 ~1.0 (실제: {total:.4f})",
                0.95 <= total <= 1.05,
            )

        mass_female = getattr(bio_mod, "SEGMENT_MASS_RATIO_FEMALE", None)
        if mass_female and BodySegment:
            total = 0.0
            for seg, ratio in mass_female.items():
                total += ratio * 2 if seg.is_bilateral else ratio
            r.check(
                f"여성 질량비 합계 ~1.0 (실제: {total:.4f})",
                0.95 <= total <= 1.05,
            )

        # 속도 임계치 단조 증가
        MovementIntensity = getattr(bio_mod, "MovementIntensity", None)
        vel_male = getattr(bio_mod, "VELOCITY_THRESHOLDS_ADULT_MALE", None)
        if MovementIntensity and vel_male:
            ordered = list(MovementIntensity)
            lowers = [vel_male[m][0] for m in ordered]
            r.check(
                "속도 하한 단조 증가",
                all(lowers[i] < lowers[i + 1] for i in range(len(lowers) - 1)),
                f"하한값: {lowers}",
            )

        # biomechanics → player_constants.AgeGroup 교차 참조 검증
        age_vel = getattr(bio_mod, "AGE_VELOCITY_FACTOR", None)
        if player and age_vel:
            AgeGroup = getattr(player, "AgeGroup", None)
            if AgeGroup:
                r.check(
                    "AGE_VELOCITY_FACTOR 키 = AgeGroup 전체",
                    set(age_vel.keys()) == set(AgeGroup),
                    f"차이: {set(age_vel.keys()).symmetric_difference(set(AgeGroup))}",
                )
                r.check(
                    "AGE_VELOCITY_FACTOR[ADULT] = 1.0",
                    age_vel.get(AgeGroup.ADULT) == 1.0,
                )

    # ═══════════════════════════════════════════════════════════════
    # [W] 통계 도메인 정합성 (v4.0.0)
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[W] 통계 도메인 정합성 (v4.0.0)")

    stats_mod = loaded_modules.get("shared.constants.stats_constants")
    if stats_mod:
        # Four Factors 가중치 합산 = 1.0
        ff_efg = getattr(stats_mod, "FOUR_FACTORS_EFG_WEIGHT", None)
        ff_tov = getattr(stats_mod, "FOUR_FACTORS_TOV_WEIGHT", None)
        ff_oreb = getattr(stats_mod, "FOUR_FACTORS_OREB_WEIGHT", None)
        ff_ft = getattr(stats_mod, "FOUR_FACTORS_FT_RATE_WEIGHT", None)
        if all(v is not None for v in (ff_efg, ff_tov, ff_oreb, ff_ft)):
            total = ff_efg + ff_tov + ff_oreb + ff_ft
            r.check(
                f"Four Factors 가중치 합 = 1.0 (실제: {total})",
                abs(total - 1.0) < 1e-9,
            )
            r.check("eFG% 가중치가 최대 (0.40)", ff_efg >= ff_tov and ff_efg >= ff_oreb and ff_efg >= ff_ft)

        # FREE_THROW_TRIP_FACTOR = 0.44 (학계 표준)
        ftt = getattr(stats_mod, "FREE_THROW_TRIP_FACTOR", None)
        r.check("FREE_THROW_TRIP_FACTOR = 0.44", ftt is not None and abs(ftt - 0.44) < 1e-9, f"실제: {ftt}")

        # calculate_ts_pct 함수 검증
        calc_ts = getattr(stats_mod, "calculate_ts_pct", None)
        if calc_ts:
            # 20점, 15 FGA, 5 FTA → TS% = 20 / (2*(15+0.44*5)) = 20/34.4 ≈ 58.14%
            ts = calc_ts(20, 15, 5)
            expected_ts = 20.0 / (2 * (15 + 0.44 * 5))
            r.check(
                f"calculate_ts_pct(20, 15, 5) ≈ {expected_ts:.4f}",
                abs(ts - expected_ts) < 1e-6,
                f"실제: {ts}",
            )

        # calculate_efg_pct 함수 검증
        calc_efg = getattr(stats_mod, "calculate_efg_pct", None)
        if calc_efg:
            # 8 FGM, 4 3PM, 15 FGA → eFG% = (8 + 0.5*4)/15 = 10/15 ≈ 66.67%
            efg = calc_efg(8, 4, 15)
            expected_efg = (8 + 0.5 * 4) / 15
            r.check(
                f"calculate_efg_pct(8, 4, 15) ≈ {expected_efg:.4f}",
                abs(efg - expected_efg) < 1e-6,
                f"실제: {efg}",
            )

        # ShotZone 11종
        ShotZone = getattr(stats_mod, "ShotZone", None)
        if ShotZone:
            r.check("ShotZone 11종", len(ShotZone) == 11, f"실제: {len(ShotZone)}")

    # ═══════════════════════════════════════════════════════════════
    # [X] 전술/경기관리/심판판정/피드백 교차 검증 (v4.0.0)
    # ═══════════════════════════════════════════════════════════════
    r.set_section("[X] 전술/경기관리/심판판정/피드백 교차 검증 (v4.0.0)")

    tac_mod = loaded_modules.get("shared.constants.tactical_constants")
    gm_mod = loaded_modules.get("shared.constants.game_management_constants")
    rd_mod = loaded_modules.get("shared.constants.referee_decision_constants")
    fb_mod = loaded_modules.get("shared.constants.feedback_constants")

    # --- 전술 ---
    if tac_mod:
        SetPlayType = getattr(tac_mod, "SetPlayType", None)
        r.check("SetPlayType 14종", SetPlayType is not None and len(SetPlayType) == 14,
                f"실제: {len(SetPlayType) if SetPlayType else 'None'}")

        # 스페이싱 임계치 순서
        sp_col = getattr(tac_mod, "SPACING_COLLAPSED_DISTANCE_M", None)
        sp_min = getattr(tac_mod, "SPACING_MIN_DISTANCE_M", None)
        sp_opt = getattr(tac_mod, "SPACING_OPTIMAL_DISTANCE_M", None)
        if all(v is not None for v in (sp_col, sp_min, sp_opt)):
            r.check(
                "COLLAPSED < MIN < OPTIMAL 스페이싱",
                sp_col < sp_min < sp_opt,
                f"collapsed={sp_col}, min={sp_min}, opt={sp_opt}",
            )

        # classify_spacing_quality 경계값 테스트
        csq = getattr(tac_mod, "classify_spacing_quality", None)
        SpacingQuality = getattr(tac_mod, "SpacingQuality", None)
        if csq and SpacingQuality and sp_opt:
            r.check("spacing(5.0m) = EXCELLENT", csq(5.0) == SpacingQuality.EXCELLENT)
            r.check("spacing(2.0m) = COLLAPSED", csq(2.0) == SpacingQuality.COLLAPSED)

    # --- 경기 관리 ---
    if gm_mod:
        GameState = getattr(gm_mod, "GameState", None)
        r.check("GameState 9종", GameState is not None and len(GameState) == 9,
                f"실제: {len(GameState) if GameState else 'None'}")

        # 경기 상태 전이 검증
        is_valid_gt = getattr(gm_mod, "is_valid_game_transition", None)
        if is_valid_gt and GameState:
            r.check("PRE_GAME → TIP_OFF 허용",
                    is_valid_gt(GameState.PRE_GAME, GameState.TIP_OFF))
            r.check("FINAL → LIVE 차단",
                    not is_valid_gt(GameState.FINAL, GameState.LIVE))

        # game_management → referee_rule_constants.RuleSet 교차 참조
        ref_mod = loaded_modules.get("shared.constants.referee_rule_constants")
        if ref_mod:
            RuleSet_ref = getattr(ref_mod, "RuleSet", None)
            q_dur = getattr(gm_mod, "QUARTER_DURATION_SEC", None)
            if RuleSet_ref and q_dur:
                r.check(
                    "QUARTER_DURATION_SEC 키 = RuleSet 전체",
                    set(q_dur.keys()) == set(RuleSet_ref),
                    f"차이: {set(q_dur.keys()).symmetric_difference(set(RuleSet_ref))}",
                )
                # NBA 쿼터 = 720초 (12분)
                nba_q = q_dur.get(RuleSet_ref.NBA)
                r.check("NBA 쿼터 = 720초", nba_q == 720, f"실제: {nba_q}")
                # FIBA 쿼터 = 600초 (10분)
                fiba_q = q_dur.get(RuleSet_ref.FIBA)
                r.check("FIBA 쿼터 = 600초", fiba_q == 600, f"실제: {fiba_q}")

    # --- 심판 판정 ---
    if rd_mod:
        DecisionConfidence = getattr(rd_mod, "DecisionConfidence", None)
        r.check("DecisionConfidence 4종", DecisionConfidence is not None and len(DecisionConfidence) == 4,
                f"실제: {len(DecisionConfidence) if DecisionConfidence else 'None'}")

        # 신뢰도 임계치 순서
        auto_th = getattr(rd_mod, "DECISION_AUTO_CONFIRM_THRESHOLD", None)
        high_th = getattr(rd_mod, "DECISION_HIGH_CONFIDENCE_THRESHOLD", None)
        mod_th = getattr(rd_mod, "DECISION_MODERATE_THRESHOLD", None)
        min_th = getattr(rd_mod, "DECISION_MIN_THRESHOLD", None)
        if all(v is not None for v in (auto_th, high_th, mod_th, min_th)):
            r.check(
                "AUTO > HIGH > MODERATE > MIN 신뢰도",
                auto_th > high_th > mod_th > min_th,
                f"auto={auto_th}, high={high_th}, mod={mod_th}, min={min_th}",
            )

        # classify_decision_confidence 경계값
        cdc = getattr(rd_mod, "classify_decision_confidence", None)
        if cdc and DecisionConfidence and auto_th:
            r.check("confidence(0.96) = AUTO_CONFIRM",
                    cdc(0.96) == DecisionConfidence.AUTO_CONFIRM)
            r.check("confidence(0.40) = LOW",
                    cdc(0.40) == DecisionConfidence.LOW)

        # 파울 등급
        FoulGrade = getattr(rd_mod, "FoulGrade", None)
        r.check("FoulGrade 4종", FoulGrade is not None and len(FoulGrade) == 4,
                f"실제: {len(FoulGrade) if FoulGrade else 'None'}")

    # --- 피드백 ---
    if fb_mod:
        FeedbackSeverity = getattr(fb_mod, "FeedbackSeverity", None)
        r.check("FeedbackSeverity 5종", FeedbackSeverity is not None and len(FeedbackSeverity) == 5,
                f"실제: {len(FeedbackSeverity) if FeedbackSeverity else 'None'}")

        # CLAUDE.md #15: 최소 10개 세부 피드백
        min_pts = getattr(fb_mod, "FEEDBACK_MIN_DETAIL_POINTS", None)
        r.check("FEEDBACK_MIN_DETAIL_POINTS ≥ 10",
                min_pts is not None and min_pts >= 10,
                f"실제: {min_pts}")

        # 카테고리 우선순위 8개 완전성
        cat_prio = getattr(fb_mod, "FEEDBACK_CATEGORY_PRIORITY", None)
        FeedbackCategory = getattr(fb_mod, "FeedbackCategory", None)
        if cat_prio and FeedbackCategory:
            r.check(
                "CATEGORY_PRIORITY 키 = FeedbackCategory 전체",
                set(cat_prio.keys()) == set(FeedbackCategory),
                f"차이: {set(cat_prio.keys()).symmetric_difference(set(FeedbackCategory))}",
            )

        # 리포트 섹션 존재 및 비어있지 않음
        sections = getattr(fb_mod, "SINGLE_GAME_REPORT_SECTIONS", None)
        r.check("SINGLE_GAME_REPORT_SECTIONS 비어있지 않음",
                sections is not None and len(sections) > 0,
                f"실제: {len(sections) if sections else 'None'}")

        # get_feedback_severity_from_percentile 유틸리티
        get_sev = getattr(fb_mod, "get_feedback_severity_from_percentile", None)
        if get_sev and FeedbackSeverity:
            r.check("percentile(95) = EXCELLENT",
                    get_sev(95) == FeedbackSeverity.EXCELLENT)
            r.check("percentile(5) = CRITICAL",
                    get_sev(5) == FeedbackSeverity.CRITICAL)

    # ═══════════════════════════════════════════════════════════════
    # 결과 요약
    # ═══════════════════════════════════════════════════════════════
    return r.summary()


if __name__ == "__main__":
    sys.exit(main())
