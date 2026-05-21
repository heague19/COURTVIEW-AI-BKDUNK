# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: motion_analysis/data_extraction
파일: record_writer.py
설명: 추출기 finalize 결과(레코드 리스트)를 로컬 파일로 직렬화하고
      ExtractionResult.file_path / file_size_bytes / s3_key 를 채운다.

      포맷: JSON Lines (.jsonl) — 한 줄 = 한 레코드.
      레코드 dataclass(slots=True) → asdict → json.dumps.

      디렉토리 구조:
          {root}/
              {dataset_type}/
                  {game_id}_{extraction_id}.jsonl

      S3 키 규약:
          datasets/{dataset_type}/{game_id}_{extraction_id}.jsonl

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-25
버전: 1.0.0

의존성:
    - shared/dto/dataset_dto.py: ExtractionResult, DatasetType
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from shared.dto.dataset_dto import ExtractionResult

logger = logging.getLogger(__name__)


_DEFAULT_ROOT: Final[Path] = Path("D:/SPOIN/training/datasets/extraction_outputs")
_S3_KEY_PREFIX: Final[str] = "datasets"


# =============================================================================
# 직렬화 헬퍼
# =============================================================================

def _to_jsonable(obj: Any) -> Any:
    """dataclass / tuple / 기타 → JSON 직렬화 가능 형태."""
    if is_dataclass(obj):
        return _to_jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


# =============================================================================
# Writer
# =============================================================================

class RecordWriter:
    """
    레코드 직렬화기.

    기본 사용:
        writer = RecordWriter()
        writer.write(result, records, s3_bucket="courtview-datasets")
        # → result.file_path, file_size_bytes, s3_key 채워짐
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self._root = Path(root) if root is not None else _DEFAULT_ROOT

    def write(
        self,
        result: ExtractionResult,
        records: list,
        s3_bucket: str = "",
    ) -> Path:
        """
        records를 .jsonl 파일로 떨구고 result 메타를 갱신한다.

        반환: 생성된 파일 경로.
        """
        if result.metadata is None:
            raise ValueError("ExtractionResult.metadata가 비어있음 — start_session 누락")

        dataset_type = result.metadata.dataset_type.value
        out_dir = self._root / dataset_type
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{result.game_id}_{result.extraction_id}.jsonl"
        file_path = out_dir / filename

        bytes_written = 0
        start = datetime.now(timezone.utc)
        with file_path.open("w", encoding="utf-8") as fh:
            for rec in records:
                line = json.dumps(_to_jsonable(rec), ensure_ascii=False)
                fh.write(line)
                fh.write("\n")
                bytes_written += len(line.encode("utf-8")) + 1
        elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        result.file_path = str(file_path)
        result.file_size_bytes = bytes_written
        result.processing_time_ms = elapsed_ms
        result.record_count = len(records)
        if s3_bucket:
            result.s3_bucket = s3_bucket
            result.s3_key = f"{_S3_KEY_PREFIX}/{dataset_type}/{filename}"

        logger.info(
            "RecordWriter: dataset_type=%s, records=%d, bytes=%d, path=%s",
            dataset_type, len(records), bytes_written, file_path,
        )
        return file_path

    def write_coach(
        self,
        result: ExtractionResult,
        shot_records: list,
        dribble_records: list,
        pass_records: list,
        s3_bucket: str = "",
    ) -> dict[str, Path]:
        """
        Coach 추출 결과는 카테고리별로 별도 파일.

        하나의 ExtractionResult에 카테고리별 파일 경로를 합친 매니페스트로 적재.
        반환: {"shot": path, "dribble": path, "pass": path}
        """
        if result.metadata is None:
            raise ValueError("ExtractionResult.metadata가 비어있음")

        from shared.dto.dataset_dto import DatasetType  # 지연 임포트로 순환 방지

        category_map = {
            "shot": (DatasetType.COACH_SHOT_SUBTYPE, shot_records),
            "dribble": (DatasetType.COACH_DRIBBLE_SUBTYPE, dribble_records),
            "pass": (DatasetType.COACH_PASS_SUBTYPE, pass_records),
        }

        paths: dict[str, Path] = {}
        total_bytes = 0
        manifest_lines: list[str] = []
        start = datetime.now(timezone.utc)

        for cat, (dtype, records) in category_map.items():
            if not records:
                continue
            out_dir = self._root / dtype.value
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{result.game_id}_{result.extraction_id}_{cat}.jsonl"
            file_path = out_dir / filename
            bytes_written = 0
            with file_path.open("w", encoding="utf-8") as fh:
                for rec in records:
                    line = json.dumps(_to_jsonable(rec), ensure_ascii=False)
                    fh.write(line)
                    fh.write("\n")
                    bytes_written += len(line.encode("utf-8")) + 1
            paths[cat] = file_path
            total_bytes += bytes_written
            manifest_lines.append(f"{cat}={file_path}")

        elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        result.file_path = " | ".join(manifest_lines)
        result.file_size_bytes = total_bytes
        result.processing_time_ms = elapsed_ms
        result.record_count = (
            len(shot_records) + len(dribble_records) + len(pass_records)
        )
        if s3_bucket:
            result.s3_bucket = s3_bucket
            keys = [
                f"{_S3_KEY_PREFIX}/{category_map[cat][0].value}/{p.name}"
                for cat, p in paths.items()
            ]
            result.s3_key = " | ".join(keys)

        logger.info(
            "RecordWriter(coach): shot=%d, dribble=%d, pass=%d, bytes=%d",
            len(shot_records), len(dribble_records), len(pass_records),
            total_bytes,
        )
        return paths


__all__ = [
    "RecordWriter",
]

__version__ = "1.0.0"
