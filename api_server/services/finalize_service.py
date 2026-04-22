# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: api_server/services
파일: finalize_service.py
설명: 경기 종료 시 전체 산출물을 하나의 폴더로 패키지하는 서비스 (Phase 18-C).

      UI 에서 넘겨준 operator 상태(팀/선수/조작 로그)와
      엔진의 ExportService 스냅샷(분석/하이라이트/리포트)을 합쳐서
      {session_dir}/finalize/ 에 구조화된 JSON + 미디어 레이아웃 생성.

      생성 레이아웃:
        {session_dir}/finalize/
        ├─ match.json            # 경기 메타/스코어/기간
        ├─ players.json          # 팀별 선수 명단 + 박스스코어 스탯
        ├─ highlights.json       # 하이라이트 메타 (clips/ 참조)
        ├─ possessions.json      # 43-analyzer 결과 (점유별)
        ├─ events.json           # 이벤트 타임라인 (operator + 엔진)
        ├─ referee_log.json      # 심판 판정 로그
        ├─ clips/                # HighlightClipService 가 채움
        └─ manifest.json         # 전체 인덱스 + schema_version

      이 폴더는 bkdunk 업로드 단계에서 통째로 전송되도록 설계됨.

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-21
버전: 1.0.0
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api_server.services.export_service import ExportService
    from engine.io.recording import RecordingService

_logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"
FINALIZE_DIRNAME = "finalize"


# =============================================================================
# UI 에서 전달받는 페이로드 — 엔진이 모르는 값들
# =============================================================================
@dataclass(slots=True)
class UIFinalizePayload:
    """UI operator 에서 전달받는 finalize 입력."""

    match_id: str = ""
    league: str = "fiba"           # fiba / nba / kbl / nbl
    venue: str = ""
    referees: list[str] = field(default_factory=list)
    # 팀
    home_team: dict[str, Any] = field(default_factory=dict)  # {name, short_code, players: [...]}
    away_team: dict[str, Any] = field(default_factory=dict)
    # 스코어 (per-quarter)
    score_by_quarter: list[dict[str, int]] = field(default_factory=list)  # [{q,home,away}]
    final_home: int = 0
    final_away: int = 0
    # operator 이벤트 로그 (score+1/2/3, 파울, 작전타임 등)
    operator_events: list[dict[str, Any]] = field(default_factory=list)
    # 시작/종료 wall-clock
    started_at: float = 0.0
    ended_at: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UIFinalizePayload:
        return cls(
            match_id=str(d.get("match_id") or ""),
            league=str(d.get("league") or "fiba"),
            venue=str(d.get("venue") or ""),
            referees=list(d.get("referees") or []),
            home_team=dict(d.get("home_team") or {}),
            away_team=dict(d.get("away_team") or {}),
            score_by_quarter=list(d.get("score_by_quarter") or []),
            final_home=int(d.get("final_home") or 0),
            final_away=int(d.get("final_away") or 0),
            operator_events=list(d.get("operator_events") or []),
            started_at=float(d.get("started_at") or 0.0),
            ended_at=float(d.get("ended_at") or time.time()),
        )


@dataclass(slots=True)
class FinalizeResult:
    """finalize 결과 요약."""

    success: bool
    finalize_dir: str = ""
    files_written: list[str] = field(default_factory=list)
    clip_count: int = 0
    recording_count: int = 0
    match_id: str = ""
    duration_ms: float = 0.0
    error: str = ""


# =============================================================================
# FinalizeService
# =============================================================================
class GameFinalizeService:
    """
    경기 종료 산출물 패키지 서비스.

    스레드 안전. 멱등 (동일 세션 재호출 시 overwrite).
    """

    __slots__ = ("_recording_service", "_export_service", "_lock")

    def __init__(
        self,
        recording_service: RecordingService,
        export_service: ExportService,
    ) -> None:
        self._recording_service = recording_service
        self._export_service = export_service
        self._lock: RLock = RLock()

    # =========================================================================
    # 메인 API
    # =========================================================================
    def finalize(self, ui: UIFinalizePayload) -> FinalizeResult:
        """경기 종료 산출물 생성.

        Args:
            ui: UI 에서 전달받은 operator 상태

        Returns:
            FinalizeResult
        """
        t0 = time.monotonic()

        with self._lock:
            # 1. 세션 디렉토리 확인
            session_dir = self._resolve_session_dir()
            if session_dir is None:
                return FinalizeResult(
                    success=False,
                    error="활성 녹화 세션 없음 — 경기 시작 후에만 finalize 가능",
                )

            # 2. finalize 서브 폴더 준비
            finalize_dir = session_dir / FINALIZE_DIRNAME
            finalize_dir.mkdir(parents=True, exist_ok=True)

            # 3. 엔진 스냅샷 수집 (ExportService 재사용)
            try:
                snapshot = self._export_service.collect_snapshot()
            except Exception:
                _logger.exception("엔진 스냅샷 수집 실패")
                snapshot = {"active": False}

            # 4. match_id 확정 (UI 제공 or 세션 ID 기반 자동 생성)
            match_id = ui.match_id or self._auto_match_id(session_dir)

            # 5. JSON 파일 작성
            files_written: list[str] = []
            files_written.append(self._write_match(finalize_dir, match_id, ui, snapshot, session_dir))
            files_written.append(self._write_players(finalize_dir, ui, snapshot))
            files_written.append(self._write_highlights(finalize_dir, snapshot))
            files_written.append(self._write_possessions(finalize_dir, snapshot))
            files_written.append(self._write_events(finalize_dir, ui, snapshot))
            files_written.append(self._write_referee_log(finalize_dir, snapshot))

            # 6. 녹화 파일 경로 수집 (copy 아닌 reference)
            recording_refs = self._collect_recording_refs(session_dir)

            # 7. 클립 파일 카운트
            clip_count = self._count_clips(session_dir)

            # 8. manifest.json (인덱스)
            manifest_path = self._write_manifest(
                finalize_dir, match_id, ui, files_written,
                clip_count, recording_refs,
            )
            files_written.append(manifest_path)

            elapsed_ms = (time.monotonic() - t0) * 1000.0
            _logger.info(
                "finalize 완료: %s (%d files, %d clips, %d recordings, %.0fms)",
                finalize_dir, len(files_written), clip_count,
                len(recording_refs), elapsed_ms,
            )

            return FinalizeResult(
                success=True,
                finalize_dir=str(finalize_dir),
                files_written=[str(Path(f).name) for f in files_written],
                clip_count=clip_count,
                recording_count=len(recording_refs),
                match_id=match_id,
                duration_ms=elapsed_ms,
            )

    # =========================================================================
    # 내부: 세션 해석
    # =========================================================================
    def _resolve_session_dir(self) -> Path | None:
        """활성 세션 디렉토리 반환. 없으면 가장 최근 세션 폴더."""
        try:
            st = self._recording_service.get_status()
            if st.get("active") and st.get("session_dir"):
                p = Path(st["session_dir"])
                if p.exists():
                    return p
            # 비활성이어도 방금 종료한 세션이면 session_dir 여전히 있음
            if st.get("session_dir"):
                p = Path(st["session_dir"])
                if p.exists():
                    return p
        except Exception:
            _logger.exception("세션 디렉토리 해석 실패")
        return None

    def _auto_match_id(self, session_dir: Path) -> str:
        """세션 폴더명 기반 match_id 생성: YYYY-MM-DD_HHMMSS → match_YYYYMMDD_HHMMSS."""
        sid = session_dir.name
        compact = sid.replace("-", "").replace("_", "_")
        return f"match_{compact}"

    # =========================================================================
    # 내부: JSON 작성
    # =========================================================================
    @staticmethod
    def _dump(path: Path, data: dict[str, Any]) -> str:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str, indent=2)
        return str(path)

    def _write_match(
        self,
        finalize_dir: Path,
        match_id: str,
        ui: UIFinalizePayload,
        snapshot: dict[str, Any],
        session_dir: Path,
    ) -> str:
        box = snapshot.get("box_score") or {}
        data = {
            "schema_version": SCHEMA_VERSION,
            "match_id": match_id,
            "session_id": session_dir.name,
            "league": ui.league,
            "venue": ui.venue,
            "referees": ui.referees,
            "status": "completed",
            "started_at": datetime.fromtimestamp(ui.started_at).isoformat() if ui.started_at else None,
            "ended_at": datetime.fromtimestamp(ui.ended_at).isoformat() if ui.ended_at else None,
            "duration_sec": max(0, int(ui.ended_at - ui.started_at)) if ui.started_at and ui.ended_at else None,
            "teams": {
                "home": {
                    "name": ui.home_team.get("name", ""),
                    "short_code": ui.home_team.get("short_code", ""),
                },
                "away": {
                    "name": ui.away_team.get("name", ""),
                    "short_code": ui.away_team.get("short_code", ""),
                },
            },
            "score": {
                "home_total": ui.final_home,
                "away_total": ui.final_away,
                "by_quarter": ui.score_by_quarter,
            },
            "box_score_summary": box,  # 엔진 자동 계산치 (참고용)
            "engine_version": "1.0.0",
        }
        return self._dump(finalize_dir / "match.json", data)

    def _write_players(
        self,
        finalize_dir: Path,
        ui: UIFinalizePayload,
        snapshot: dict[str, Any],
    ) -> str:
        """UI 선수 명단·스탯이 주축. 엔진 스냅샷은 보조 참조."""
        engine_players = snapshot.get("players") or []

        data = {
            "schema_version": SCHEMA_VERSION,
            "home": ui.home_team.get("players") or [],
            "away": ui.away_team.get("players") or [],
            "engine_computed": engine_players,  # 엔진이 추적한 선수별 스탯 (비교용)
        }
        return self._dump(finalize_dir / "players.json", data)

    def _write_highlights(
        self,
        finalize_dir: Path,
        snapshot: dict[str, Any],
    ) -> str:
        clips = snapshot.get("highlights") or []
        data = {
            "schema_version": SCHEMA_VERSION,
            "clips": clips,
            # 실제 파일 참조는 ../clips/{event_id}.mp4 로 해석
            "clips_dir": "../clips",
        }
        return self._dump(finalize_dir / "highlights.json", data)

    def _write_possessions(
        self,
        finalize_dir: Path,
        snapshot: dict[str, Any],
    ) -> str:
        """전술/개인/공간/수비/전환/플레이유형/라인업/매치업 분석 모음."""
        data = {
            "schema_version": SCHEMA_VERSION,
            "tactical": snapshot.get("tactical") or {},
            "report": snapshot.get("report") or {},
            "scouting": snapshot.get("scouting") or {},
            "team_stats": snapshot.get("teams") or [],
        }
        return self._dump(finalize_dir / "possessions.json", data)

    def _write_events(
        self,
        finalize_dir: Path,
        ui: UIFinalizePayload,
        snapshot: dict[str, Any],
    ) -> str:
        """operator 이벤트 + 엔진 탐지 이벤트 병합 타임라인."""
        data = {
            "schema_version": SCHEMA_VERSION,
            "operator_events": ui.operator_events,
        }
        return self._dump(finalize_dir / "events.json", data)

    def _write_referee_log(
        self,
        finalize_dir: Path,
        snapshot: dict[str, Any],
    ) -> str:
        data = {
            "schema_version": SCHEMA_VERSION,
            "referee": snapshot.get("referee") or {},
        }
        return self._dump(finalize_dir / "referee_log.json", data)

    def _write_manifest(
        self,
        finalize_dir: Path,
        match_id: str,
        ui: UIFinalizePayload,
        files_written: list[str],
        clip_count: int,
        recording_refs: list[dict[str, Any]],
    ) -> str:
        data = {
            "schema_version": SCHEMA_VERSION,
            "match_id": match_id,
            "generated_at": datetime.now().isoformat(),
            "files": sorted({Path(f).name for f in files_written}),
            "clips": {
                "count": clip_count,
                "dir": "clips",
            },
            "recordings": recording_refs,
            "upload_status": "pending",   # bkdunk 업로드 단계에서 업데이트
        }
        return self._dump(finalize_dir / "manifest.json", data)

    # =========================================================================
    # 내부: 미디어 파일 수집
    # =========================================================================
    def _count_clips(self, session_dir: Path) -> int:
        clips_dir = session_dir / "clips"
        if not clips_dir.exists():
            return 0
        return sum(1 for _ in clips_dir.glob("*.mp4"))

    def _collect_recording_refs(self, session_dir: Path) -> list[dict[str, Any]]:
        """세션 폴더 내 풀 녹화 파일 참조 (경로만, copy 안 함)."""
        refs: list[dict[str, Any]] = []
        for f in sorted(session_dir.glob("*_full.mp4")):
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            refs.append({
                "camera_id": f.stem.replace("_full", ""),
                "path": f.name,  # 세션 dir 기준 상대 경로
                "size_bytes": size,
            })
        # 병합 안 된 세그먼트도 참조
        if not refs:
            for f in sorted(session_dir.glob("*.ts")):
                try:
                    size = f.stat().st_size
                except OSError:
                    size = 0
                refs.append({
                    "segment": f.name,
                    "path": f.name,
                    "size_bytes": size,
                })
        return refs


__all__ = [
    "GameFinalizeService",
    "UIFinalizePayload",
    "FinalizeResult",
    "SCHEMA_VERSION",
    "FINALIZE_DIRNAME",
]
