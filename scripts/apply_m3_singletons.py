#!/usr/bin/env python
"""
Phase 15 세션 5 — M3: Generator 싱글톤화 일괄 전환 스크립트

대상: feedback_system/analysis + coach 의 24+ generator
변경:
    1. `self._severity_mapper: SeverityMapper = SeverityMapper()`
       → `self._severity_mapper = get_default_severity_mapper()`
    2. `self._templates: KoreanTemplates = KoreanTemplates()`
       → `self._templates = get_default_korean_templates()`
    3. import 경로 변경:
       `from feedback_system.templates.severity_mapper import SeverityMapper`
       → `from feedback_system.templates import get_default_severity_mapper`
       (단, `SeverityMapper`/`KoreanTemplates` type hint 사용처는 유지)

안전성:
    - 싱글톤은 lazy init (최초 호출 시 생성)
    - 각 generator가 default config만 사용하므로 공유 안전
    - FeedbackFormatter는 per-generator config 유지 (변경 안 함)
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 24 analysis generators + 1 coach (motion_feedback)
# biomechanics_feedback는 별도 처리 (SeverityMapper만 사용, KoreanTemplates 없음)
TARGET_FILES = [
    # analysis/ (24)
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
    # coach/ (1 — biomechanics_feedback는 수동 처리)
    "feedback_system/coach/motion_feedback.py",
    # coach/biomechanics_feedback은 수동 처리 (KoreanTemplates 없음)
    "feedback_system/coach/biomechanics_feedback.py",
]

# 인스턴스 생성 교체 패턴
SEVERITY_ASSIGN = re.compile(
    r"self\._severity_mapper:\s*SeverityMapper\s*=\s*SeverityMapper\(\)"
)
TEMPLATES_ASSIGN = re.compile(
    r"self\._templates:\s*KoreanTemplates\s*=\s*KoreanTemplates\(\)"
)

# 모듈 레벨 import 교체 (단독 심볼 import)
# 패턴: from feedback_system.templates.severity_mapper import SeverityMapper
SEVERITY_IMPORT_OLD = "from feedback_system.templates.severity_mapper import SeverityMapper"
TEMPLATES_IMPORT_OLD = "from feedback_system.templates.korean_templates import KoreanTemplates"


def process_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"SKIP (not found): {path}"

    src = path.read_text(encoding="utf-8")
    new_src = src

    changes: list[str] = []

    # 1. SeverityMapper 할당 교체
    if SEVERITY_ASSIGN.search(new_src):
        new_src = SEVERITY_ASSIGN.sub(
            "self._severity_mapper = get_default_severity_mapper()",
            new_src,
        )
        changes.append("severity_assign")

    # 2. KoreanTemplates 할당 교체
    if TEMPLATES_ASSIGN.search(new_src):
        new_src = TEMPLATES_ASSIGN.sub(
            "self._templates = get_default_korean_templates()",
            new_src,
        )
        changes.append("templates_assign")

    # 3. 싱글톤 getter import 추가 (아직 없으면)
    need_severity_getter = "severity_assign" in changes
    need_templates_getter = "templates_assign" in changes

    if need_severity_getter or need_templates_getter:
        imports_to_add = []
        if (
            need_severity_getter
            and "get_default_severity_mapper" not in new_src
        ):
            imports_to_add.append("get_default_severity_mapper")
        if (
            need_templates_getter
            and "get_default_korean_templates" not in new_src
        ):
            imports_to_add.append("get_default_korean_templates")

        if imports_to_add:
            # 기존 `from feedback_system.templates.severity_mapper import SeverityMapper` 같은
            # 라인 뒤에 추가하거나, `from feedback_system.templates ...` 블록이 없으면 새로 삽입
            # 단순 접근: 원래 import 라인 뒤에 삽입
            anchor_patterns = [
                "from feedback_system.templates.severity_mapper import SeverityMapper",
                "from feedback_system.templates.korean_templates import KoreanTemplates",
                "from feedback_system.templates.feedback_formatter import",
            ]
            anchor_found = False
            for anchor in anchor_patterns:
                if anchor in new_src:
                    # 해당 라인 뒤에 import 추가
                    new_line = (
                        "from feedback_system.templates import "
                        + ", ".join(imports_to_add)
                    )
                    # anchor 뒤에 삽입 (여러 anchor 중 먼저 발견된 것 1회만)
                    new_src = new_src.replace(
                        anchor,
                        f"{anchor}\n{new_line}",
                        1,
                    )
                    anchor_found = True
                    break
            if not anchor_found:
                return False, f"FAIL (no anchor for import): {path.name}"

    if new_src == src:
        return False, f"NOOP: {path.name}"

    path.write_text(new_src, encoding="utf-8")
    return True, f"OK: {path.name} ({', '.join(changes)})"


def main() -> None:
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
