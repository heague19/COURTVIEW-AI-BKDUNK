#!/usr/bin/env python
"""
Phase 15 세션 5 버그 수정 — M3 싱글톤 getter import 누락 보완

스크립트 `apply_m3_singletons.py` 실행 시 import 존재 여부 체크가
할당문까지 포함하여 false positive 발생. 실제 import 가 없는데
있다고 판정되어 누락됨.

이 스크립트: `get_default_*()` 사용처는 있지만 import 가 없는 파일을 찾아
`from feedback_system.templates import ...` 라인을 추가.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def process_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"SKIP (not found): {path}"

    src = path.read_text(encoding="utf-8")
    needs_severity = (
        "get_default_severity_mapper()" in src
        and "from feedback_system.templates import" not in src
        and "import get_default_severity_mapper" not in src
    )
    needs_templates = (
        "get_default_korean_templates()" in src
        and "import get_default_korean_templates" not in src
        and "get_default_korean_templates," not in src
    )

    # 더 정확한 import 감지: 정규식
    has_import_line = re.search(
        r"from feedback_system\.templates import [^\n]*get_default_\w+",
        src,
    )

    if has_import_line:
        return False, f"SKIP (already imported): {path.name}"

    symbols_needed: list[str] = []
    if "get_default_severity_mapper()" in src:
        symbols_needed.append("get_default_severity_mapper")
    if "get_default_korean_templates()" in src:
        symbols_needed.append("get_default_korean_templates")

    if not symbols_needed:
        return False, f"SKIP (no usage): {path.name}"

    new_import_line = (
        "from feedback_system.templates import "
        + ", ".join(symbols_needed)
    )

    # anchor: severity_mapper/korean_templates import 라인 뒤에 삽입
    anchor_patterns = [
        "from feedback_system.templates.severity_mapper import SeverityMapper",
        "from feedback_system.templates.korean_templates import KoreanTemplates",
        "from feedback_system.templates.feedback_formatter import",
    ]

    new_src = src
    inserted = False
    for anchor in anchor_patterns:
        if anchor in new_src:
            # 해당 anchor 라인을 찾고 그 뒤에 import 삽입
            # 다중 라인 import 대응 — anchor가 매 라인에 정확 매칭되어야 함
            idx = new_src.find(anchor)
            # anchor 라인 끝 찾기
            line_end = new_src.find("\n", idx)
            if anchor.endswith("("):
                # 다중 라인 import — 닫는 ) 까지 찾기
                close_idx = new_src.find(")", idx)
                line_end = new_src.find("\n", close_idx) if close_idx > 0 else line_end
            if line_end > 0:
                new_src = (
                    new_src[: line_end + 1]
                    + new_import_line + "\n"
                    + new_src[line_end + 1:]
                )
                inserted = True
                break

    if not inserted:
        return False, f"FAIL (no anchor): {path.name}"

    path.write_text(new_src, encoding="utf-8")
    return True, f"OK: {path.name} ({', '.join(symbols_needed)})"


def main() -> None:
    # feedback_system 내 모든 Python 파일 스캔
    changed = 0
    skipped = 0
    failed = 0

    fb_dir = ROOT / "feedback_system"
    for path in fb_dir.rglob("*.py"):
        ok, msg = process_file(path)
        if "SKIP (no usage)" in msg or "SKIP (already" in msg:
            skipped += 1
            continue
        print(msg)
        if ok:
            changed += 1
        elif "FAIL" in msg:
            failed += 1

    print(f"\n총 {changed}개 변경 / {skipped} skip / {failed} fail")


if __name__ == "__main__":
    main()
