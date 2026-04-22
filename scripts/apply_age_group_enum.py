#!/usr/bin/env python
"""
Phase 15 세션 4 — M2: age_group 문자열 → AgeGroup enum 일괄 전환 스크립트

대상: feedback_system/ 전역 31파일 + api_server 일부
변경:
    1. `from shared.constants.player_constants import AgeGroup` import 추가
    2. `age_group: str = "adult"` → `age_group: AgeGroup = AgeGroup.ADULT`

안전성:
    - `AgeGroup(str, Enum)` 이므로 기존 문자열 비교 100% 호환
    - 외부 호출자가 str "adult" 전달 시 런타임 정상 (str 서브클래스)
    - Breaking change 없음

사용: python scripts/apply_age_group_enum.py
"""
from __future__ import annotations

import re
from pathlib import Path

# 프로젝트 루트 (이 스크립트는 scripts/ 에 위치)
ROOT = Path(__file__).resolve().parent.parent

# 대상 파일 (feedback_system/ 전역 + korean_templates method)
TARGET_FILES = [
    # feedback_system/analysis (24)
    "feedback_system/analysis/causal_feedback.py",
    "feedback_system/analysis/clutch_feedback.py",
    "feedback_system/analysis/defensive_feedback.py",
    "feedback_system/analysis/drill_prescription_feedback.py",
    "feedback_system/analysis/finish_repertoire_feedback.py",
    "feedback_system/analysis/foul_trouble_feedback.py",
    "feedback_system/analysis/free_throw_feedback.py",
    "feedback_system/analysis/game_context_feedback.py",
    "feedback_system/analysis/game_feedback.py",
    "feedback_system/analysis/individual_feedback.py",
    "feedback_system/analysis/lineup_feedback.py",
    "feedback_system/analysis/opponent_tendency_feedback.py",
    "feedback_system/analysis/pace_tempo_feedback.py",
    "feedback_system/analysis/play_by_play_feedback.py",
    "feedback_system/analysis/position_feedback.py",
    "feedback_system/analysis/quarter_momentum_feedback.py",
    "feedback_system/analysis/referee_feedback.py",
    "feedback_system/analysis/rotation_feedback.py",
    "feedback_system/analysis/scouting_feedback.py",
    "feedback_system/analysis/shot_quality_feedback.py",
    "feedback_system/analysis/spatial_feedback.py",
    "feedback_system/analysis/strategic_recommendation_feedback.py",
    "feedback_system/analysis/tactical_feedback.py",
    "feedback_system/analysis/visual_feedback_generator.py",
    # feedback_system/coach (2 — biomechanics_feedback 이미 import 있음)
    "feedback_system/coach/motion_feedback.py",
    # feedback_system/report (3)
    "feedback_system/report/coach_report_generator.py",
    "feedback_system/report/game_report_generator.py",
    "feedback_system/report/session_summary.py",
    # feedback_system/templates (1)
    "feedback_system/templates/feedback_formatter.py",
]

FIELD_PATTERN = re.compile(r'age_group: str = "adult"')
IMPORT_LINE = "from shared.constants.player_constants import AgeGroup"


def process_file(path: Path) -> tuple[bool, str]:
    """단일 파일 처리.

    Returns:
        (변경됨 여부, 메시지)
    """
    if not path.exists():
        return False, f"SKIP (not found): {path}"

    src = path.read_text(encoding="utf-8")

    # 1. 필드 패턴 검색
    if not FIELD_PATTERN.search(src):
        return False, f"SKIP (no pattern): {path}"

    # 2. 필드 교체
    new_src = FIELD_PATTERN.sub(
        "age_group: AgeGroup = AgeGroup.ADULT", src,
    )

    # 3. AgeGroup import 추가 (없으면)
    if IMPORT_LINE not in new_src:
        # `from shared.dto` import 뒤에 삽입 (없으면 from __future__ 뒤)
        marker_candidates = [
            "from shared.dto.",
            "from shared.constants.feedback_constants import",
            "from __future__ import annotations",
        ]
        inserted = False
        for marker in marker_candidates:
            if marker in new_src:
                # 해당 import 블록 끝에 삽입
                lines = new_src.split("\n")
                out: list[str] = []
                i = 0
                while i < len(lines):
                    out.append(lines[i])
                    if marker in lines[i]:
                        # 블록 끝까지 진행 (닫는 괄호 ) 또는 다음 빈 줄)
                        while i + 1 < len(lines) and (
                            lines[i + 1].startswith("    ")
                            or lines[i + 1].startswith(")")
                        ):
                            i += 1
                            out.append(lines[i])
                        # import 라인 삽입
                        out.append(IMPORT_LINE)
                        inserted = True
                        i += 1
                        # 나머지 복사
                        while i < len(lines):
                            out.append(lines[i])
                            i += 1
                        break
                    i += 1
                if inserted:
                    new_src = "\n".join(out)
                    break

        if not inserted:
            return False, f"FAIL (no marker): {path}"

    # 4. 저장
    if new_src == src:
        return False, f"NOOP: {path}"

    path.write_text(new_src, encoding="utf-8")
    return True, f"OK: {path}"


def main() -> None:
    """모든 대상 파일 처리."""
    changed = 0
    skipped = 0
    failed = 0

    for rel in TARGET_FILES:
        path = ROOT / rel
        ok, msg = process_file(path)
        print(msg)
        if ok:
            changed += 1
        elif "FAIL" in msg:
            failed += 1
        else:
            skipped += 1

    print(f"\n총 {changed}개 변경 / {skipped} skip / {failed} fail")


if __name__ == "__main__":
    main()
