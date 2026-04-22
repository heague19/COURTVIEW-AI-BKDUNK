# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/game_management
파일: official_format_exporter.py
설명: FIBA/NBA/KBL/NBL 공식 기록지 포맷 변환 및 출력
      - 리그별 공식 박스스코어 형식 생성
      - JSON/XML 실시간 피드 생성
      - OfficialBoxScore DTO 기반 구조화 출력
      - 🔵POST-GAME 등급 (경기 종료 후 생성, 시간 제한 없음)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - shared/constants/game_management_constants.py: RecordFormat
    - shared/dto/game_management_dto.py: OfficialBoxScore, PlayerBoxStat, TeamBoxStat

의존성:
    - shared/constants/game_management_constants.py
    - shared/dto/game_management_dto.py

소비자:
    - game_analysis/game_record/game_report_builder.py: 경기 리포트에 기록지 포함
    - api_server: 클라이언트에 기록지 전송
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from threading import RLock
from typing import Any, Final

from shared.constants.game_management_constants import RecordFormat
from shared.constants.referee_rule_constants import RuleSet
from shared.dto.game_management_dto import (
    OfficialBoxScore,
    PlayerBoxStat,
    TeamBoxStat,
)


# =============================================================================
# 상수
# =============================================================================

logger: Final = logging.getLogger(__name__)

# 리그별 기본 출력 형식
_RULE_SET_TO_FORMAT: Final[dict[RuleSet, RecordFormat]] = {
    RuleSet.FIBA: RecordFormat.FIBA_BOXSCORE,
    RuleSet.NBA: RecordFormat.NBA_BOXSCORE,
    RuleSet.KBL: RecordFormat.KBL_BOXSCORE,
    RuleSet.NBL: RecordFormat.NBL_BOXSCORE,
    RuleSet.EUROLEAGUE: RecordFormat.FIBA_BOXSCORE,
}


# =============================================================================
# 공식 기록지 출력기 설정
# =============================================================================

@dataclass(slots=True)
class OfficialFormatExporterConfig:
    """
    공식 기록지 출력기 설정.
    """

    rule_set: RuleSet = RuleSet.FIBA
    # 기본 출력 형식 (리그별 자동 결정)
    default_format: RecordFormat | None = None
    # JSON 출력 시 들여쓰기
    json_indent: int = 2

    @property
    def resolved_format(self) -> RecordFormat:
        """적용할 출력 형식."""
        if self.default_format is not None:
            return self.default_format
        return _RULE_SET_TO_FORMAT.get(self.rule_set, RecordFormat.FIBA_BOXSCORE)

    @classmethod
    def from_yaml(cls, cfg: dict) -> OfficialFormatExporterConfig:
        """YAML 설정에서 생성."""
        rule_str = cfg.get("rule_set", "fiba")
        try:
            rule_set = RuleSet(rule_str)
        except ValueError:
            logger.warning("알 수 없는 규칙세트 '%s', FIBA 기본 적용", rule_str)
            rule_set = RuleSet.FIBA

        fmt_str = cfg.get("default_format")
        default_format = None
        if fmt_str:
            try:
                default_format = RecordFormat(fmt_str)
            except ValueError:
                logger.warning("알 수 없는 출력 형식 '%s', 리그 기본 적용", fmt_str)

        return cls(
            rule_set=rule_set,
            default_format=default_format,
            json_indent=int(cfg.get("json_indent", 2)),
        )


# =============================================================================
# 공식 기록지 출력기
# =============================================================================

class OfficialFormatExporter:
    """
    FIBA/NBA/KBL/NBL 공식 기록지 포맷 변환 및 출력.

    🔵POST-GAME 등급: 경기 종료 후 호출 (시간 제한 없음).

    기능:
        - OfficialBoxScore DTO 생성
        - 리그별 공식 박스스코어 dict 생성
        - JSON 직렬화
        - XML 직렬화
        - 다중 포맷 동시 출력

    사용법:
        >>> exporter = OfficialFormatExporter()
        >>> box_score = exporter.build_box_score(
        ...     game_id="G001", date="2026-03-24", venue="서울 체육관",
        ...     home_team="서울 팀", away_team="부산 팀",
        ...     final_score=(85, 78), quarter_scores=[(22,20),(18,22),(25,18),(20,18)],
        ...     player_stats=[...], team_stats=TeamBoxStat(...),
        ... )
        >>> json_str = exporter.to_json(box_score)
    """

    __slots__ = ("_config", "_lock")

    def __init__(self, config: OfficialFormatExporterConfig | None = None) -> None:
        self._config: OfficialFormatExporterConfig = (
            config or OfficialFormatExporterConfig()
        )
        self._lock: RLock = RLock()

    # =========================================================================
    # OfficialBoxScore 생성
    # =========================================================================

    def build_box_score(
        self,
        game_id: str,
        date: str,
        venue: str,
        home_team: str,
        away_team: str,
        final_score: tuple[int, int],
        quarter_scores: list[tuple[int, int]],
        player_stats: list[PlayerBoxStat],
        team_stats: TeamBoxStat | None = None,
        overtime_scores: list[tuple[int, int]] | None = None,
        officials: list[str] | None = None,
    ) -> OfficialBoxScore:
        """
        공식 기록지 DTO 생성.

        Args:
            game_id: 경기 ID
            date: 경기 일자
            venue: 경기 장소
            home_team: 홈팀 이름
            away_team: 어웨이팀 이름
            final_score: 최종 스코어 (홈, 어웨이)
            quarter_scores: 쿼터별 스코어 [(홈, 어웨이), ...]
            player_stats: 선수별 박스스코어
            team_stats: 팀 종합 통계
            overtime_scores: 연장전 스코어 (있는 경우)
            officials: 심판 목록

        Returns:
            OfficialBoxScore DTO
        """
        return OfficialBoxScore(
            format_type=str(self._config.resolved_format),
            game_id=game_id,
            date=date,
            venue=venue,
            home_team=home_team,
            away_team=away_team,
            final_score=final_score,
            quarter_scores=list(quarter_scores),
            overtime_scores=list(overtime_scores) if overtime_scores else [],
            player_stats=list(player_stats),
            team_stats=team_stats,
            officials=list(officials) if officials else [],
        )

    # =========================================================================
    # 리그별 포맷 변환
    # =========================================================================

    def format_box_score(
        self,
        box_score: OfficialBoxScore,
        fmt: RecordFormat | None = None,
    ) -> dict[str, Any]:
        """
        OfficialBoxScore를 리그별 포맷 dict로 변환.

        Args:
            box_score: OfficialBoxScore DTO
            fmt: 출력 형식 (None이면 설정 기본값)

        Returns:
            리그별 포맷화된 dict
        """
        target_fmt = fmt or self._config.resolved_format

        if target_fmt in (
            RecordFormat.FIBA_BOXSCORE,
            RecordFormat.KBL_BOXSCORE,
            RecordFormat.NBL_BOXSCORE,
        ):
            return self._format_fiba_style(box_score, target_fmt)
        elif target_fmt == RecordFormat.NBA_BOXSCORE:
            return self._format_nba_style(box_score)
        elif target_fmt == RecordFormat.JSON_FEED:
            return self._format_json_feed(box_score)
        elif target_fmt == RecordFormat.XML_FEED:
            return self._format_xml_dict(box_score)
        else:
            return self._format_fiba_style(box_score, target_fmt)

    # =========================================================================
    # JSON/XML 직렬화
    # =========================================================================

    def to_json(
        self,
        box_score: OfficialBoxScore,
        fmt: RecordFormat | None = None,
    ) -> str:
        """
        JSON 문자열로 직렬화.

        Args:
            box_score: OfficialBoxScore DTO
            fmt: 출력 형식

        Returns:
            JSON 문자열
        """
        data = self.format_box_score(box_score, fmt)
        return json.dumps(data, ensure_ascii=False, indent=self._config.json_indent)

    def to_xml(self, box_score: OfficialBoxScore) -> str:
        """
        XML 문자열로 직렬화.

        Args:
            box_score: OfficialBoxScore DTO

        Returns:
            XML 문자열
        """
        data = self._format_xml_dict(box_score)
        lines: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>']
        self._dict_to_xml(data, lines, root_tag="game_record")
        return "\n".join(lines)

    # =========================================================================
    # 선수 통계 유틸리티
    # =========================================================================

    def calculate_team_stats(
        self, player_stats: list[PlayerBoxStat]
    ) -> TeamBoxStat:
        """
        선수 통계로부터 팀 종합 통계 산출.

        Args:
            player_stats: 선수별 박스스코어

        Returns:
            TeamBoxStat
        """
        total_fg_made = sum(p.fg_made for p in player_stats)
        total_fg_att = sum(p.fg_attempts for p in player_stats)
        total_3_made = sum(p.three_made for p in player_stats)
        total_3_att = sum(p.three_attempts for p in player_stats)
        total_ft_made = sum(p.ft_made for p in player_stats)
        total_ft_att = sum(p.ft_attempts for p in player_stats)

        return TeamBoxStat(
            fg_pct=total_fg_made / total_fg_att if total_fg_att > 0 else 0.0,
            three_pct=total_3_made / total_3_att if total_3_att > 0 else 0.0,
            ft_pct=total_ft_made / total_ft_att if total_ft_att > 0 else 0.0,
            rebounds=sum(p.rebounds for p in player_stats),
            assists=sum(p.assists for p in player_stats),
            steals=sum(p.steals for p in player_stats),
            blocks=sum(p.blocks for p in player_stats),
            turnovers=sum(p.turnovers for p in player_stats),
        )

    # =========================================================================
    # 내부 포맷 메서드
    # =========================================================================

    def _format_fiba_style(
        self,
        box_score: OfficialBoxScore,
        fmt: RecordFormat,
    ) -> dict[str, Any]:
        """FIBA/KBL/NBL 스타일 박스스코어."""
        players: list[dict[str, Any]] = []
        for p in box_score.player_stats:
            fg_str = f"{p.fg_made}/{p.fg_attempts}"
            three_str = f"{p.three_made}/{p.three_attempts}"
            ft_str = f"{p.ft_made}/{p.ft_attempts}"
            players.append({
                "tracking_id": p.player_tracking_id,
                "name": p.name,
                "min": round(p.minutes, 1),
                "pts": p.points,
                "reb": p.rebounds,
                "ast": p.assists,
                "stl": p.steals,
                "blk": p.blocks,
                "to": p.turnovers,
                "pf": p.fouls,
                "fg": fg_str,
                "3pt": three_str,
                "ft": ft_str,
                "+/-": p.plus_minus,
            })

        result: dict[str, Any] = {
            "format": str(fmt),
            "game_id": box_score.game_id,
            "date": box_score.date,
            "venue": box_score.venue,
            "home_team": box_score.home_team,
            "away_team": box_score.away_team,
            "final_score": {
                "home": box_score.final_score[0],
                "away": box_score.final_score[1],
            },
            "quarter_scores": [
                {"q": i + 1, "home": qs[0], "away": qs[1]}
                for i, qs in enumerate(box_score.quarter_scores)
            ],
            "players": players,
            "officials": box_score.officials,
            "winner": box_score.winner,
        }

        if box_score.overtime_scores:
            result["overtime_scores"] = [
                {"ot": i + 1, "home": ots[0], "away": ots[1]}
                for i, ots in enumerate(box_score.overtime_scores)
            ]

        if box_score.team_stats:
            ts = box_score.team_stats
            result["team_stats"] = {
                "fg_pct": round(ts.fg_pct * 100, 1),
                "three_pct": round(ts.three_pct * 100, 1),
                "ft_pct": round(ts.ft_pct * 100, 1),
                "rebounds": ts.rebounds,
                "assists": ts.assists,
                "steals": ts.steals,
                "blocks": ts.blocks,
                "turnovers": ts.turnovers,
                "points_in_paint": ts.points_in_paint,
                "fast_break_points": ts.fast_break_points,
                "second_chance_points": ts.second_chance_points,
                "bench_points": ts.bench_points,
            }

        return result

    def _format_nba_style(self, box_score: OfficialBoxScore) -> dict[str, Any]:
        """NBA 스타일 박스스코어."""
        # NBA 포맷은 FIBA와 기본 구조 동일하나 추가 필드 포함
        result = self._format_fiba_style(box_score, RecordFormat.NBA_BOXSCORE)

        # NBA 고유 필드 추가
        for player_data in result.get("players", []):
            # NBA는 분:초 형식 표시
            minutes = player_data.get("min", 0)
            mins = int(minutes)
            secs = int((minutes - mins) * 60)
            player_data["min_display"] = f"{mins}:{secs:02d}"

        return result

    def _format_json_feed(self, box_score: OfficialBoxScore) -> dict[str, Any]:
        """JSON 실시간 피드 형식."""
        return {
            "type": "game_feed",
            "format": str(RecordFormat.JSON_FEED),
            "game_id": box_score.game_id,
            "date": box_score.date,
            "home": {
                "team": box_score.home_team,
                "score": box_score.final_score[0],
            },
            "away": {
                "team": box_score.away_team,
                "score": box_score.final_score[1],
            },
            "quarters": box_score.quarter_scores,
            "overtime": box_score.overtime_scores,
            "player_count": len(box_score.player_stats),
            "winner": box_score.winner,
        }

    def _format_xml_dict(self, box_score: OfficialBoxScore) -> dict[str, Any]:
        """XML 변환용 dict."""
        return {
            "format": str(RecordFormat.XML_FEED),
            "game_id": box_score.game_id,
            "date": box_score.date,
            "venue": box_score.venue,
            "home_team": box_score.home_team,
            "away_team": box_score.away_team,
            "home_score": box_score.final_score[0],
            "away_score": box_score.final_score[1],
            "officials": ", ".join(box_score.officials),
            "winner": box_score.winner,
        }

    def _dict_to_xml(
        self,
        data: dict[str, Any],
        lines: list[str],
        root_tag: str,
        indent: int = 0,
    ) -> None:
        """dict를 XML 요소로 변환 (재귀)."""
        prefix = "  " * indent
        lines.append(f"{prefix}<{root_tag}>")
        for key, value in data.items():
            if isinstance(value, dict):
                self._dict_to_xml(value, lines, root_tag=key, indent=indent + 1)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._dict_to_xml(item, lines, root_tag=key, indent=indent + 1)
                    else:
                        lines.append(f"{prefix}  <{key}>{item}</{key}>")
            else:
                lines.append(f"{prefix}  <{key}>{value}</{key}>")
        lines.append(f"{prefix}</{root_tag}>")

    # =========================================================================
    # 팩토리
    # =========================================================================

    @classmethod
    def from_yaml(cls, cfg: dict) -> OfficialFormatExporter:
        """YAML 설정에서 OfficialFormatExporter 생성."""
        config = OfficialFormatExporterConfig.from_yaml(cfg)
        return cls(config)


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    "OfficialFormatExporterConfig",
    "OfficialFormatExporter",
]

__version__ = "1.0.0"
