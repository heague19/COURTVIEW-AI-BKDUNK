# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: game_dto.py
설명: 경기 분석, 하이라이트, 슛 차트 관련 DTO 정의
      - Enum은 shared.constants.game_rule_constants에서 import
      - 경기 이벤트, 하이라이트, 경기 통계 DTO
      - AI 심판 관련 DTO (바이올레이션, 파울)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-14
버전: 1.0.0
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from shared.constants.localization import SupportedLanguage

# =============================================================================
# 열거형 (shared.constants.game_rule_constants에서 import)
# =============================================================================
from shared.constants.game_rule_constants import (  # noqa: F401
    ShotType,
    ShotResult,
    CourtZone,
    PlayType,
    GameEventType as EventType,  # 하위 호환성: GameEventType → EventType 별칭
    HighlightType,
    ViolationType,
    FoulType,
)

# =============================================================================
# 선수/팀 정보 DTO
# =============================================================================
class PlayerInfo(BaseModel):
    """
    선수 정보 DTO.

    경기 중 감지된 선수 정보입니다.
    """

    player_id: str | None = Field(default=None, description="선수 ID (연동된 경우)")
    tracking_id: int = Field(..., ge=0, description="트래킹 ID (영상 내)")
    jersey_number: int | None = Field(default=None, ge=0, le=99, description="등번호")
    team_id: str | None = Field(default=None, description="팀 ID")
    position: str | None = Field(default=None, description="추정 포지션")

    # 바운딩 박스 (마지막 감지 위치)
    bbox_x: float = Field(default=0.0, ge=0.0, description="바운딩 박스 X (정규화)")
    bbox_y: float = Field(default=0.0, ge=0.0, description="바운딩 박스 Y (정규화)")
    bbox_width: float = Field(default=0.0, ge=0.0, description="바운딩 박스 너비 (정규화)")
    bbox_height: float = Field(default=0.0, ge=0.0, description="바운딩 박스 높이 (정규화)")

    # 트래킹 정보
    first_frame: int = Field(default=0, ge=0, description="첫 감지 프레임")
    last_frame: int = Field(default=0, ge=0, description="마지막 감지 프레임")
    total_frames_tracked: int = Field(default=0, ge=0, description="총 트래킹 프레임 수")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="트래킹 신뢰도")


class TeamInfo(BaseModel):
    """
    팀 정보 DTO.

    경기에 참여한 팀 정보입니다.
    """

    team_id: str | None = Field(default=None, description="팀 ID")
    team_name: str | None = Field(default=None, description="팀명")
    jersey_color: str | None = Field(default=None, description="유니폼 색상 (HEX)")
    is_home: bool = Field(default=True, description="홈팀 여부")
    players: list[PlayerInfo] = Field(default_factory=list, description="소속 선수 목록")


# =============================================================================
# 슛 관련 DTO
# =============================================================================
class ShotAttempt(BaseModel):
    """
    슛 시도 DTO.

    개별 슛 시도의 상세 정보입니다.
    """

    shot_id: UUID = Field(default_factory=uuid4, description="슛 ID")

    # 선수 정보
    player_tracking_id: int = Field(..., ge=0, description="슛터 트래킹 ID")
    player_id: str | None = Field(default=None, description="선수 ID")
    team_id: str | None = Field(default=None, description="팀 ID")

    # 슛 정보
    shot_type: ShotType = Field(..., description="슛 유형")
    result: ShotResult = Field(..., description="슛 결과")
    points: int = Field(default=0, ge=0, le=3, description="획득 점수")

    # 위치 정보
    court_zone: CourtZone = Field(..., description="코트 구역")
    shot_x: float = Field(..., ge=-1.0, le=1.0, description="슛 위치 X (정규화, -1~1)")
    shot_y: float = Field(..., ge=-1.0, le=1.0, description="슛 위치 Y (정규화, -1~1)")
    distance_meters: float = Field(default=0.0, ge=0.0, description="골대로부터 거리 (m)")

    # 슛 분석
    shot_quality: float = Field(default=0.0, ge=0.0, le=100.0, description="슛 품질 점수")
    contest_level: str = Field(default="open", pattern="^(open|lightly_contested|contested|heavily_contested)$", description="수비 압박 수준")
    release_angle: float | None = Field(default=None, ge=0.0, le=90.0, description="릴리스 각도 (도)")
    arc_height: float | None = Field(default=None, ge=0.0, description="아크 높이 (m)")

    # 시간 정보
    frame_number: int = Field(..., ge=0, description="슛 프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="영상 내 시간 (초)")
    quarter: int | None = Field(default=None, ge=1, le=4, description="쿼터")
    game_clock: str | None = Field(default=None, description="게임 시계 (MM:SS)")

    # 어시스트 정보
    assisted: bool = Field(default=False, description="어시스트 여부")
    assister_tracking_id: int | None = Field(default=None, ge=0, description="어시스터 트래킹 ID")


class ZoneStatistics(BaseModel):
    """
    구역별 슛 통계 DTO.

    특정 코트 구역의 슛 통계입니다.
    """

    zone: CourtZone = Field(..., description="코트 구역")
    attempts: int = Field(default=0, ge=0, description="슛 시도 횟수")
    made: int = Field(default=0, ge=0, description="슛 성공 횟수")
    percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="성공률 (%)")
    points: int = Field(default=0, ge=0, description="획득 점수")
    average_distance: float = Field(default=0.0, ge=0.0, description="평균 슛 거리 (m)")

    @model_validator(mode="after")
    def validate_statistics(self) -> "ZoneStatistics":
        """통계 일관성 검증."""
        if self.made > self.attempts:
            raise ValueError("성공 횟수가 시도 횟수를 초과할 수 없습니다")
        if self.attempts > 0:
            expected_pct = (self.made / self.attempts) * 100
            # 소수점 차이 허용 (0.1% 오차)
            if abs(self.percentage - expected_pct) > 0.1:
                # 자동 보정
                object.__setattr__(self, "percentage", round(expected_pct, 1))
        return self


class ShotChart(BaseModel):
    """
    슛 차트 DTO.

    경기 전체의 슛 분석 결과입니다.
    """

    chart_id: UUID = Field(default_factory=uuid4, description="차트 ID")
    task_id: UUID = Field(..., description="분석 태스크 ID")

    # 전체 통계
    total_attempts: int = Field(default=0, ge=0, description="총 슛 시도")
    total_made: int = Field(default=0, ge=0, description="총 성공")
    field_goal_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="야투율 (%)")

    # 2점슛 통계
    two_point_attempts: int = Field(default=0, ge=0, description="2점슛 시도")
    two_point_made: int = Field(default=0, ge=0, description="2점슛 성공")
    two_point_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="2점슛 성공률 (%)")

    # 3점슛 통계
    three_point_attempts: int = Field(default=0, ge=0, description="3점슛 시도")
    three_point_made: int = Field(default=0, ge=0, description="3점슛 성공")
    three_point_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="3점슛 성공률 (%)")

    # 페인트 존 통계
    paint_attempts: int = Field(default=0, ge=0, description="페인트존 시도")
    paint_made: int = Field(default=0, ge=0, description="페인트존 성공")
    paint_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="페인트존 성공률 (%)")

    # 구역별 통계 (키: CourtZone 값, 값: ZoneStatistics)
    zone_stats: dict[str, ZoneStatistics] = Field(default_factory=dict, description="구역별 슛 통계")

    # 슛 상세 목록
    shots: list[ShotAttempt] = Field(default_factory=list, description="슛 시도 목록")

    @field_validator("zone_stats")
    @classmethod
    def validate_zone_keys(cls, v: dict[str, ZoneStatistics]) -> dict[str, ZoneStatistics]:
        """구역별 통계의 키가 유효한 CourtZone 값인지 검증."""
        valid_zones = {zone.value for zone in CourtZone}
        invalid_keys = [key for key in v.keys() if key not in valid_zones]
        if invalid_keys:
            raise ValueError(f"유효하지 않은 구역 키: {invalid_keys}. 유효한 값: {valid_zones}")
        return v

    # 시각화 URL
    chart_image_url: HttpUrl | None = Field(default=None, description="슛 차트 이미지 URL")
    heatmap_url: HttpUrl | None = Field(default=None, description="슛 히트맵 URL")

    # ==================== 시각화 유틸리티 메서드 ====================

    def to_visualization_data(self, lang: SupportedLanguage = SupportedLanguage.KO) -> dict[str, Any]:
        """
        슛 차트 시각화용 데이터 변환.

        프론트엔드 시각화 라이브러리 (D3.js, Chart.js 등)에서 사용할 수 있는
        형식으로 데이터를 변환합니다.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            시각화용 데이터 딕셔너리
        """
        # 슛 좌표 데이터 (scatter plot용)
        shot_points = [
            {
                "x": shot.shot_x,
                "y": shot.shot_y,
                "made": shot.result.is_successful,
                "type": shot.shot_type.get_name(lang),
                "zone": shot.court_zone.get_name(lang),
                "points": shot.points,
                "distance": shot.distance_meters,
                "quality": shot.shot_quality,
            }
            for shot in self.shots
        ]

        # 구역별 효율성 데이터 (히트맵용)
        zone_efficiency = {
            zone.get_name(lang): {
                "value": zone.value,
                "attempts": stats.attempts,
                "made": stats.made,
                "percentage": stats.percentage,
                "points": stats.points,
                "color_intensity": min(100, stats.percentage * 1.2) if stats.attempts > 0 else 0,
            }
            for zone_value, stats in self.zone_stats.items()
            for zone in [CourtZone(zone_value)]
        }

        # 슛 유형별 분포 데이터 (pie chart용)
        shot_type_counts: dict[str, int] = {}
        for shot in self.shots:
            type_name = shot.shot_type.get_name(lang)
            shot_type_counts[type_name] = shot_type_counts.get(type_name, 0) + 1

        return {
            "summary": {
                "total_attempts": self.total_attempts,
                "total_made": self.total_made,
                "field_goal_percentage": self.field_goal_percentage,
                "two_point": {
                    "attempts": self.two_point_attempts,
                    "made": self.two_point_made,
                    "percentage": self.two_point_percentage,
                },
                "three_point": {
                    "attempts": self.three_point_attempts,
                    "made": self.three_point_made,
                    "percentage": self.three_point_percentage,
                },
                "paint": {
                    "attempts": self.paint_attempts,
                    "made": self.paint_made,
                    "percentage": self.paint_percentage,
                },
            },
            "shot_points": shot_points,
            "zone_efficiency": zone_efficiency,
            "shot_type_distribution": shot_type_counts,
        }

    def get_hot_zones(self, min_attempts: int = 3, min_percentage: float = 50.0) -> list[str]:
        """
        핫 존 (높은 슛 성공률 구역) 반환.

        Args:
            min_attempts: 최소 시도 횟수 (기본값: 3)
            min_percentage: 최소 성공률 (기본값: 50%)

        Returns:
            핫 존 구역 값 리스트
        """
        return [
            zone_value
            for zone_value, stats in self.zone_stats.items()
            if stats.attempts >= min_attempts and stats.percentage >= min_percentage
        ]

    def get_cold_zones(self, min_attempts: int = 3, max_percentage: float = 30.0) -> list[str]:
        """
        콜드 존 (낮은 슛 성공률 구역) 반환.

        Args:
            min_attempts: 최소 시도 횟수 (기본값: 3)
            max_percentage: 최대 성공률 (기본값: 30%)

        Returns:
            콜드 존 구역 값 리스트
        """
        return [
            zone_value
            for zone_value, stats in self.zone_stats.items()
            if stats.attempts >= min_attempts and stats.percentage <= max_percentage
        ]

    def calculate_effective_field_goal_percentage(self) -> float:
        """
        유효 야투율 (eFG%) 계산.

        eFG% = (FGM + 0.5 * 3PM) / FGA * 100

        Returns:
            유효 야투율 (%)
        """
        if self.total_attempts == 0:
            return 0.0
        efg = (self.total_made + 0.5 * self.three_point_made) / self.total_attempts * 100
        return round(efg, 1)

    def calculate_true_shooting_percentage(self, free_throws_made: int = 0, free_throws_attempted: int = 0) -> float:
        """
        트루 슈팅 퍼센티지 (TS%) 계산.

        TS% = Points / (2 * (FGA + 0.44 * FTA)) * 100

        Args:
            free_throws_made: 자유투 성공 수 (기본값: 0)
            free_throws_attempted: 자유투 시도 수 (기본값: 0)

        Returns:
            트루 슈팅 퍼센티지 (%)
        """
        total_points = (self.two_point_made * 2) + (self.three_point_made * 3) + free_throws_made
        denominator = 2 * (self.total_attempts + 0.44 * free_throws_attempted)
        if denominator == 0:
            return 0.0
        ts = total_points / denominator * 100
        return round(ts, 1)


# =============================================================================
# 경기 이벤트 DTO
# =============================================================================
class GameEvent(BaseModel):
    """
    경기 이벤트 DTO.

    경기 중 발생한 개별 이벤트입니다.
    """

    event_id: UUID = Field(default_factory=uuid4, description="이벤트 ID")
    event_type: EventType = Field(..., description="이벤트 유형")

    # 관련 선수
    primary_player_id: int | None = Field(default=None, ge=0, description="주 선수 트래킹 ID")
    secondary_player_id: int | None = Field(default=None, ge=0, description="보조 선수 트래킹 ID (어시스터 등)")
    team_id: str | None = Field(default=None, description="팀 ID")

    # 위치 정보
    court_x: float | None = Field(default=None, ge=-1.0, le=1.0, description="위치 X (정규화)")
    court_y: float | None = Field(default=None, ge=-1.0, le=1.0, description="위치 Y (정규화)")

    # 시간 정보
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="영상 내 시간 (초)")
    quarter: int | None = Field(default=None, ge=1, le=4, description="쿼터")
    game_clock: str | None = Field(default=None, description="게임 시계")

    # 점수 정보
    points: int = Field(default=0, ge=0, description="획득 점수")
    home_score: int | None = Field(default=None, ge=0, description="홈팀 점수")
    away_score: int | None = Field(default=None, ge=0, description="어웨이팀 점수")

    # 추가 정보
    description: str | None = Field(default=None, description="이벤트 설명")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="감지 신뢰도")


# =============================================================================
# 하이라이트 DTO
# =============================================================================
class HighlightClip(BaseModel):
    """
    하이라이트 클립 DTO.

    개별 하이라이트 클립 정보입니다.
    """

    clip_id: UUID = Field(default_factory=uuid4, description="클립 ID")
    highlight_type: HighlightType = Field(..., description="하이라이트 유형")

    # 시간 정보
    start_frame: int = Field(..., ge=0, description="시작 프레임")
    end_frame: int = Field(..., ge=0, description="종료 프레임")
    start_time: float = Field(..., ge=0.0, description="시작 시간 (초)")
    end_time: float = Field(..., ge=0.0, description="종료 시간 (초)")
    duration_seconds: float = Field(..., ge=0.0, description="클립 길이 (초)")

    # 관련 선수
    primary_player_id: int | None = Field(default=None, ge=0, description="주 선수 트래킹 ID")
    related_player_ids: list[int] = Field(default_factory=list, description="관련 선수 트래킹 ID 목록")

    # 이벤트 정보
    related_events: list[UUID] = Field(default_factory=list, description="관련 이벤트 ID 목록")

    # 점수/평가
    excitement_score: float = Field(default=0.0, ge=0.0, le=100.0, description="흥미도 점수")
    importance_score: float = Field(default=0.0, ge=0.0, le=100.0, description="중요도 점수")

    # 영상 정보
    clip_url: HttpUrl | None = Field(default=None, description="클립 URL")
    thumbnail_url: HttpUrl | None = Field(default=None, description="썸네일 URL")

    # 설명
    title: str | None = Field(default=None, description="하이라이트 제목")
    description: str | None = Field(default=None, description="하이라이트 설명")

    @model_validator(mode="after")
    def validate_time_range(self) -> "HighlightClip":
        """시간 범위 검증."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time은 start_time보다 커야 합니다")
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame은 start_frame보다 커야 합니다")
        return self


class HighlightReel(BaseModel):
    """
    하이라이트 릴 DTO.

    경기 전체의 하이라이트 모음입니다.
    """

    reel_id: UUID = Field(default_factory=uuid4, description="릴 ID")
    task_id: UUID = Field(..., description="분석 태스크 ID")

    # 클립 목록
    clips: list[HighlightClip] = Field(default_factory=list, description="하이라이트 클립 목록")
    total_clips: int = Field(default=0, ge=0, description="총 클립 수")

    # 전체 릴 정보
    total_duration_seconds: float = Field(default=0.0, ge=0.0, description="전체 하이라이트 길이")
    reel_video_url: HttpUrl | None = Field(default=None, description="전체 하이라이트 영상 URL")

    # 하이라이트 유형별 수
    type_counts: dict[str, int] = Field(default_factory=dict, description="유형별 하이라이트 수")

    # 생성 정보
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시간 (UTC)",
    )


# =============================================================================
# 경기 통계 DTO
# =============================================================================
class PlayerStats(BaseModel):
    """
    선수 통계 DTO.

    경기 중 개별 선수의 통계입니다.
    """

    player_tracking_id: int = Field(..., ge=0, description="트래킹 ID")
    player_id: str | None = Field(default=None, description="선수 ID")
    team_id: str | None = Field(default=None, description="팀 ID")

    # 득점
    points: int = Field(default=0, ge=0, description="득점")
    field_goals_made: int = Field(default=0, ge=0, description="야투 성공")
    field_goals_attempted: int = Field(default=0, ge=0, description="야투 시도")
    field_goal_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="야투율")

    # 3점슛
    three_pointers_made: int = Field(default=0, ge=0, description="3점슛 성공")
    three_pointers_attempted: int = Field(default=0, ge=0, description="3점슛 시도")
    three_point_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="3점슛 성공률")

    # 자유투
    free_throws_made: int = Field(default=0, ge=0, description="자유투 성공")
    free_throws_attempted: int = Field(default=0, ge=0, description="자유투 시도")
    free_throw_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="자유투 성공률")

    # 리바운드
    offensive_rebounds: int = Field(default=0, ge=0, description="공격 리바운드")
    defensive_rebounds: int = Field(default=0, ge=0, description="수비 리바운드")
    total_rebounds: int = Field(default=0, ge=0, description="총 리바운드")

    # 어시스트/턴오버
    assists: int = Field(default=0, ge=0, description="어시스트")
    turnovers: int = Field(default=0, ge=0, description="턴오버")

    # 수비
    steals: int = Field(default=0, ge=0, description="스틸")
    blocks: int = Field(default=0, ge=0, description="블락")

    # 파울
    personal_fouls: int = Field(default=0, ge=0, description="개인 파울")

    # 효율성
    efficiency_rating: float = Field(default=0.0, description="효율성 지수")
    plus_minus: int = Field(default=0, description="플러스/마이너스")

    # ==================== 통계 계산 헬퍼 메서드 ====================

    def calculate_efficiency(self) -> float:
        """
        선수 효율성 지수 (EFF/PIR) 계산.

        EFF = (PTS + REB + AST + STL + BLK) - (FGA - FGM) - (FTA - FTM) - TO

        Returns:
            효율성 지수
        """
        positive = self.points + self.total_rebounds + self.assists + self.steals + self.blocks
        negative = (
            (self.field_goals_attempted - self.field_goals_made) +
            (self.free_throws_attempted - self.free_throws_made) +
            self.turnovers
        )
        return float(positive - negative)

    def calculate_true_shooting_percentage(self) -> float:
        """
        트루 슈팅 퍼센티지 (TS%) 계산.

        TS% = Points / (2 * (FGA + 0.44 * FTA)) * 100

        Returns:
            트루 슈팅 퍼센티지 (%)
        """
        denominator = 2 * (self.field_goals_attempted + 0.44 * self.free_throws_attempted)
        if denominator == 0:
            return 0.0
        return round(self.points / denominator * 100, 1)

    def calculate_effective_field_goal_percentage(self) -> float:
        """
        유효 야투율 (eFG%) 계산.

        eFG% = (FGM + 0.5 * 3PM) / FGA * 100

        Returns:
            유효 야투율 (%)
        """
        if self.field_goals_attempted == 0:
            return 0.0
        efg = (self.field_goals_made + 0.5 * self.three_pointers_made) / self.field_goals_attempted * 100
        return round(efg, 1)

    def calculate_assist_to_turnover_ratio(self) -> float:
        """
        어시스트 대 턴오버 비율 (AST/TO) 계산.

        Returns:
            어시스트/턴오버 비율 (턴오버가 0이면 어시스트 값 반환)
        """
        if self.turnovers == 0:
            return float(self.assists)
        return round(self.assists / self.turnovers, 2)

    def calculate_game_score(self) -> float:
        """
        게임 스코어 (Game Score) 계산 - John Hollinger 공식.

        GmSc = PTS + 0.4*FGM - 0.7*FGA - 0.4*(FTA-FTM) + 0.7*ORB + 0.3*DRB
               + STL + 0.7*AST + 0.7*BLK - 0.4*PF - TO

        Returns:
            게임 스코어
        """
        game_score = (
            self.points +
            0.4 * self.field_goals_made -
            0.7 * self.field_goals_attempted -
            0.4 * (self.free_throws_attempted - self.free_throws_made) +
            0.7 * self.offensive_rebounds +
            0.3 * self.defensive_rebounds +
            self.steals +
            0.7 * self.assists +
            0.7 * self.blocks -
            0.4 * self.personal_fouls -
            self.turnovers
        )
        return round(game_score, 1)

    def is_double_double(self) -> bool:
        """
        더블-더블 달성 여부 확인.

        5개 카테고리 중 2개에서 두 자릿수 기록.

        Returns:
            더블-더블 여부
        """
        categories = [
            self.points,
            self.total_rebounds,
            self.assists,
            self.steals,
            self.blocks
        ]
        return sum(1 for c in categories if c >= 10) >= 2

    def is_triple_double(self) -> bool:
        """
        트리플-더블 달성 여부 확인.

        5개 카테고리 중 3개에서 두 자릿수 기록.

        Returns:
            트리플-더블 여부
        """
        categories = [
            self.points,
            self.total_rebounds,
            self.assists,
            self.steals,
            self.blocks
        ]
        return sum(1 for c in categories if c >= 10) >= 3

    def to_box_score_dict(self, lang: SupportedLanguage = SupportedLanguage.KO) -> dict[str, Any]:
        """
        박스 스코어 형식 딕셔너리 변환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            박스 스코어 딕셔너리
        """
        labels = {
            SupportedLanguage.KO: {
                "points": "득점", "rebounds": "리바운드", "assists": "어시스트",
                "steals": "스틸", "blocks": "블락", "turnovers": "턴오버",
                "fg": "야투", "3pt": "3점슛", "ft": "자유투", "fouls": "파울",
                "efficiency": "효율성", "plus_minus": "+/-"
            },
            SupportedLanguage.EN: {
                "points": "PTS", "rebounds": "REB", "assists": "AST",
                "steals": "STL", "blocks": "BLK", "turnovers": "TO",
                "fg": "FG", "3pt": "3PT", "ft": "FT", "fouls": "PF",
                "efficiency": "EFF", "plus_minus": "+/-"
            },
        }
        lbl = labels.get(lang, labels[SupportedLanguage.EN])

        return {
            lbl["points"]: self.points,
            lbl["rebounds"]: self.total_rebounds,
            lbl["assists"]: self.assists,
            lbl["steals"]: self.steals,
            lbl["blocks"]: self.blocks,
            lbl["turnovers"]: self.turnovers,
            lbl["fg"]: f"{self.field_goals_made}/{self.field_goals_attempted}",
            lbl["3pt"]: f"{self.three_pointers_made}/{self.three_pointers_attempted}",
            lbl["ft"]: f"{self.free_throws_made}/{self.free_throws_attempted}",
            lbl["fouls"]: self.personal_fouls,
            lbl["efficiency"]: self.calculate_efficiency(),
            lbl["plus_minus"]: self.plus_minus,
        }


class TeamStats(BaseModel):
    """
    팀 통계 DTO.

    경기 중 팀 전체 통계입니다.
    """

    team_id: str | None = Field(default=None, description="팀 ID")
    team_name: str | None = Field(default=None, description="팀명")
    is_home: bool = Field(default=True, description="홈팀 여부")

    # 점수
    final_score: int = Field(default=0, ge=0, description="최종 점수")
    quarter_scores: list[int] = Field(default_factory=list, description="쿼터별 점수")

    # 슈팅
    field_goals_made: int = Field(default=0, ge=0, description="야투 성공")
    field_goals_attempted: int = Field(default=0, ge=0, description="야투 시도")
    field_goal_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="야투율")

    three_pointers_made: int = Field(default=0, ge=0, description="3점슛 성공")
    three_pointers_attempted: int = Field(default=0, ge=0, description="3점슛 시도")
    three_point_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="3점슛 성공률")

    free_throws_made: int = Field(default=0, ge=0, description="자유투 성공")
    free_throws_attempted: int = Field(default=0, ge=0, description="자유투 시도")
    free_throw_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="자유투 성공률")

    # 리바운드
    offensive_rebounds: int = Field(default=0, ge=0, description="공격 리바운드")
    defensive_rebounds: int = Field(default=0, ge=0, description="수비 리바운드")
    total_rebounds: int = Field(default=0, ge=0, description="총 리바운드")

    # 어시스트/턴오버
    assists: int = Field(default=0, ge=0, description="어시스트")
    turnovers: int = Field(default=0, ge=0, description="턴오버")

    # 수비
    steals: int = Field(default=0, ge=0, description="스틸")
    blocks: int = Field(default=0, ge=0, description="블락")

    # 파울
    personal_fouls: int = Field(default=0, ge=0, description="팀 파울")

    # 페인트존
    points_in_paint: int = Field(default=0, ge=0, description="페인트존 득점")

    # 세컨드 찬스
    second_chance_points: int = Field(default=0, ge=0, description="세컨드 찬스 득점")

    # 속공
    fast_break_points: int = Field(default=0, ge=0, description="속공 득점")

    # 벤치 득점
    bench_points: int = Field(default=0, ge=0, description="벤치 득점")

    # 선수별 통계
    player_stats: list[PlayerStats] = Field(default_factory=list, description="선수별 통계")

    # ==================== 통계 계산 헬퍼 메서드 ====================

    def calculate_offensive_rating(self, possessions: int) -> float:
        """
        공격 효율 (ORtg) 계산.

        ORtg = (Points / Possessions) * 100

        Args:
            possessions: 공격 횟수 (포제션)

        Returns:
            공격 효율 (100 포제션당 득점)
        """
        if possessions == 0:
            return 0.0
        return round(self.final_score / possessions * 100, 1)

    def calculate_effective_field_goal_percentage(self) -> float:
        """
        유효 야투율 (eFG%) 계산.

        eFG% = (FGM + 0.5 * 3PM) / FGA * 100

        Returns:
            유효 야투율 (%)
        """
        if self.field_goals_attempted == 0:
            return 0.0
        efg = (self.field_goals_made + 0.5 * self.three_pointers_made) / self.field_goals_attempted * 100
        return round(efg, 1)

    def calculate_true_shooting_percentage(self) -> float:
        """
        트루 슈팅 퍼센티지 (TS%) 계산.

        TS% = Points / (2 * (FGA + 0.44 * FTA)) * 100

        Returns:
            트루 슈팅 퍼센티지 (%)
        """
        denominator = 2 * (self.field_goals_attempted + 0.44 * self.free_throws_attempted)
        if denominator == 0:
            return 0.0
        return round(self.final_score / denominator * 100, 1)

    def calculate_offensive_rebound_percentage(self, opponent_defensive_rebounds: int) -> float:
        """
        공격 리바운드율 (ORB%) 계산.

        ORB% = ORB / (ORB + Opp DRB) * 100

        Args:
            opponent_defensive_rebounds: 상대팀 수비 리바운드

        Returns:
            공격 리바운드율 (%)
        """
        total = self.offensive_rebounds + opponent_defensive_rebounds
        if total == 0:
            return 0.0
        return round(self.offensive_rebounds / total * 100, 1)

    def calculate_assist_percentage(self) -> float:
        """
        어시스트율 (AST%) 계산.

        AST% = AST / FGM * 100

        Returns:
            어시스트율 (%) - 성공한 야투 중 어시스트 비율
        """
        if self.field_goals_made == 0:
            return 0.0
        return round(self.assists / self.field_goals_made * 100, 1)

    def calculate_turnover_percentage(self) -> float:
        """
        턴오버율 (TOV%) 계산.

        TOV% = TO / (FGA + 0.44 * FTA + TO) * 100

        Returns:
            턴오버율 (%)
        """
        denominator = self.field_goals_attempted + 0.44 * self.free_throws_attempted + self.turnovers
        if denominator == 0:
            return 0.0
        return round(self.turnovers / denominator * 100, 1)

    def calculate_pace(self, game_minutes: float = 48.0, opponent_stats: "TeamStats | None" = None) -> float:
        """
        경기 페이스 (Pace) 추정.

        Pace ≈ (FGA + 0.44 * FTA - ORB + TO) * (game_minutes / actual_minutes)

        Args:
            game_minutes: 경기 시간 (분, 기본값: 48분)
            opponent_stats: 상대팀 통계 (None이면 자체 통계만 사용)

        Returns:
            추정 페이스 (포제션/경기)
        """
        own_possessions = (
            self.field_goals_attempted +
            0.44 * self.free_throws_attempted -
            self.offensive_rebounds +
            self.turnovers
        )

        if opponent_stats:
            opp_possessions = (
                opponent_stats.field_goals_attempted +
                0.44 * opponent_stats.free_throws_attempted -
                opponent_stats.offensive_rebounds +
                opponent_stats.turnovers
            )
            return round((own_possessions + opp_possessions) / 2, 1)

        return round(own_possessions, 1)

    def get_four_factors(self, opponent_stats: "TeamStats | None" = None) -> dict[str, float]:
        """
        포 팩터 (Four Factors) 계산 - Dean Oliver의 농구 분석 기법.

        1. eFG% (유효 야투율) - 40% 중요도
        2. TOV% (턴오버율) - 25% 중요도
        3. ORB% (공격 리바운드율) - 20% 중요도
        4. FT Rate (자유투 비율) - 15% 중요도

        Args:
            opponent_stats: 상대팀 통계 (공격 리바운드율 계산용)

        Returns:
            포 팩터 딕셔너리
        """
        opp_drb = opponent_stats.defensive_rebounds if opponent_stats else 0

        return {
            "efg_percentage": self.calculate_effective_field_goal_percentage(),
            "turnover_percentage": self.calculate_turnover_percentage(),
            "offensive_rebound_percentage": self.calculate_offensive_rebound_percentage(opp_drb),
            "free_throw_rate": round(self.free_throws_attempted / max(1, self.field_goals_attempted) * 100, 1),
        }

    def get_scoring_breakdown(self) -> dict[str, dict[str, int | float]]:
        """
        득점 분포 분석.

        Returns:
            득점 분포 딕셔너리 (2점슛, 3점슛, 자유투, 특수 득점)
        """
        two_point_made = self.field_goals_made - self.three_pointers_made
        two_point_points = two_point_made * 2
        three_point_points = self.three_pointers_made * 3
        free_throw_points = self.free_throws_made

        total = self.final_score if self.final_score > 0 else 1  # 0으로 나누기 방지

        return {
            "two_point": {
                "points": two_point_points,
                "percentage": round(two_point_points / total * 100, 1),
            },
            "three_point": {
                "points": three_point_points,
                "percentage": round(three_point_points / total * 100, 1),
            },
            "free_throw": {
                "points": free_throw_points,
                "percentage": round(free_throw_points / total * 100, 1),
            },
            "special": {
                "paint": self.points_in_paint,
                "fast_break": self.fast_break_points,
                "second_chance": self.second_chance_points,
                "bench": self.bench_points,
            },
        }

    def to_summary_dict(self, lang: SupportedLanguage = SupportedLanguage.KO) -> dict[str, Any]:
        """
        팀 통계 요약 딕셔너리 변환.

        Args:
            lang: 출력 언어 (기본값: 한국어)

        Returns:
            통계 요약 딕셔너리
        """
        labels = {
            SupportedLanguage.KO: {
                "fg": "야투", "3pt": "3점슛", "ft": "자유투",
                "rebounds": "리바운드", "assists": "어시스트",
                "turnovers": "턴오버", "steals": "스틸", "blocks": "블락"
            },
            SupportedLanguage.EN: {
                "fg": "FG", "3pt": "3PT", "ft": "FT",
                "rebounds": "REB", "assists": "AST",
                "turnovers": "TO", "steals": "STL", "blocks": "BLK"
            },
        }
        lbl = labels.get(lang, labels[SupportedLanguage.EN])

        return {
            "score": self.final_score,
            lbl["fg"]: f"{self.field_goals_made}/{self.field_goals_attempted} ({self.field_goal_percentage:.1f}%)",
            lbl["3pt"]: f"{self.three_pointers_made}/{self.three_pointers_attempted} ({self.three_point_percentage:.1f}%)",
            lbl["ft"]: f"{self.free_throws_made}/{self.free_throws_attempted} ({self.free_throw_percentage:.1f}%)",
            lbl["rebounds"]: self.total_rebounds,
            lbl["assists"]: self.assists,
            lbl["turnovers"]: self.turnovers,
            lbl["steals"]: self.steals,
            lbl["blocks"]: self.blocks,
        }


class GameStats(BaseModel):
    """
    경기 통계 DTO.

    경기 전체 통계 및 기록지입니다.
    """

    stats_id: UUID = Field(default_factory=uuid4, description="통계 ID")
    task_id: UUID = Field(..., description="분석 태스크 ID")

    # 경기 정보
    game_date: datetime | None = Field(default=None, description="경기 일시")
    venue: str | None = Field(default=None, description="경기장")
    league: str | None = Field(default=None, description="리그명")

    # 최종 스코어
    home_score: int = Field(default=0, ge=0, description="홈팀 최종 점수")
    away_score: int = Field(default=0, ge=0, description="어웨이팀 최종 점수")

    # 팀 통계
    home_team_stats: TeamStats | None = Field(default=None, description="홈팀 통계")
    away_team_stats: TeamStats | None = Field(default=None, description="어웨이팀 통계")

    # 이벤트 목록
    events: list[GameEvent] = Field(default_factory=list, description="경기 이벤트 목록")
    total_events: int = Field(default=0, ge=0, description="총 이벤트 수")

    # 경기 흐름 분석
    lead_changes: int = Field(default=0, ge=0, description="리드 변경 횟수")
    ties: int = Field(default=0, ge=0, description="동점 횟수")
    largest_lead_home: int = Field(default=0, ge=0, description="홈팀 최대 리드")
    largest_lead_away: int = Field(default=0, ge=0, description="어웨이팀 최대 리드")

    # 생성 정보
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시간 (UTC)",
    )



# =============================================================================
# AI 심판 DTO
# =============================================================================
class ViolationEvent(BaseModel):
    """
    바이올레이션 이벤트 DTO.

    감지기에서 생성되는 바이올레이션 이벤트입니다.
    """

    event_id: str = Field(..., description="이벤트 ID")
    event_type: EventType = Field(..., description="이벤트 타입")
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="타임스탬프 (초)")
    violation_type: ViolationType = Field(..., description="바이올레이션 유형")
    player_id: int | None = Field(default=None, description="선수 ID")
    team_id: str | None = Field(default=None, description="팀 ID")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="신뢰도")
    description: str | None = Field(default=None, description="설명")
    court_x: float | None = Field(default=None, description="코트 X 좌표")
    court_y: float | None = Field(default=None, description="코트 Y 좌표")


class FoulEvent(BaseModel):
    """
    파울 이벤트 DTO.

    감지기에서 생성되는 파울 이벤트입니다.
    """

    event_id: str = Field(..., description="이벤트 ID")
    event_type: EventType = Field(..., description="이벤트 타입")
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="타임스탬프 (초)")
    foul_type: FoulType = Field(..., description="파울 유형")
    fouler_id: int | None = Field(default=None, description="파울 선수 ID")
    fouled_id: int | None = Field(default=None, description="피파울 선수 ID")
    team_id: str | None = Field(default=None, description="파울 팀 ID")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="신뢰도")
    description: str | None = Field(default=None, description="설명")
    court_x: float | None = Field(default=None, description="코트 X 좌표")
    court_y: float | None = Field(default=None, description="코트 Y 좌표")
    free_throws: int = Field(default=0, ge=0, le=3, description="부여 자유투 수")


class RefereeDecision(BaseModel):
    """
    심판 판정 DTO.

    AI 심판의 판정 결과입니다.
    """

    decision_id: str = Field(..., description="판정 ID")
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="타임스탬프 (초)")
    decision_type: str = Field(..., description="판정 유형 (violation/foul/no_call)")
    violation_event: ViolationEvent | None = Field(default=None, description="바이올레이션 이벤트")
    foul_event: FoulEvent | None = Field(default=None, description="파울 이벤트")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="판정 신뢰도")
    rule_reference: str | None = Field(default=None, description="규칙 참조")
    explanation: str | None = Field(default=None, description="판정 설명")


class ReviewSuggestion(BaseModel):
    """
    리뷰 제안 DTO.

    리뷰가 필요한 상황에 대한 제안입니다.
    """

    suggestion_id: str = Field(..., description="제안 ID")
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="타임스탬프 (초)")
    reason: str = Field(..., description="리뷰 필요 사유")
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$", description="우선순위")
    related_events: list[str] = Field(default_factory=list, description="관련 이벤트 ID 목록")
    clip_start_time: float | None = Field(default=None, ge=0.0, description="클립 시작 시간")
    clip_end_time: float | None = Field(default=None, ge=0.0, description="클립 종료 시간")


class ViolationDetection(BaseModel):
    """
    바이올레이션 감지 DTO.

    감지된 개별 바이올레이션 정보입니다.
    """

    detection_id: UUID = Field(default_factory=uuid4, description="감지 ID")
    violation_type: ViolationType = Field(..., description="바이올레이션 유형")

    # 관련 선수
    player_tracking_id: int = Field(..., ge=0, description="선수 트래킹 ID")
    team_id: str | None = Field(default=None, description="팀 ID")

    # 시간/위치 정보
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="영상 내 시간 (초)")
    court_x: float | None = Field(default=None, ge=-1.0, le=1.0, description="위치 X")
    court_y: float | None = Field(default=None, ge=-1.0, le=1.0, description="위치 Y")

    # 감지 정보
    confidence: float = Field(..., ge=0.0, le=1.0, description="감지 신뢰도")
    severity: str = Field(default="medium", pattern="^(low|medium|high)$", description="심각도")

    # 설명
    description: str | None = Field(default=None, description="바이올레이션 설명")
    rule_reference: str | None = Field(default=None, description="규칙 참조")

    # 영상 클립
    clip_start_time: float | None = Field(default=None, ge=0.0, description="클립 시작 시간")
    clip_end_time: float | None = Field(default=None, ge=0.0, description="클립 종료 시간")
    clip_url: HttpUrl | None = Field(default=None, description="클립 URL")


class FoulDetection(BaseModel):
    """
    파울 감지 DTO.

    감지된 개별 파울 정보입니다.
    """

    detection_id: UUID = Field(default_factory=uuid4, description="감지 ID")
    foul_type: FoulType = Field(..., description="파울 유형")

    # 관련 선수
    fouler_tracking_id: int = Field(..., ge=0, description="파울 선수 트래킹 ID")
    fouled_tracking_id: int | None = Field(default=None, ge=0, description="피파울 선수 트래킹 ID")
    team_id: str | None = Field(default=None, description="파울 팀 ID")

    # 시간/위치 정보
    frame_number: int = Field(..., ge=0, description="프레임 번호")
    timestamp: float = Field(..., ge=0.0, description="영상 내 시간 (초)")
    court_x: float | None = Field(default=None, ge=-1.0, le=1.0, description="위치 X")
    court_y: float | None = Field(default=None, ge=-1.0, le=1.0, description="위치 Y")

    # 감지 정보
    confidence: float = Field(..., ge=0.0, le=1.0, description="감지 신뢰도")
    severity: str = Field(default="medium", pattern="^(low|medium|high)$", description="심각도")

    # 자유투 정보
    free_throws_awarded: int = Field(default=0, ge=0, le=3, description="부여 자유투 수")

    # 설명
    description: str | None = Field(default=None, description="파울 설명")
    rule_reference: str | None = Field(default=None, description="규칙 참조")

    # 영상 클립
    clip_start_time: float | None = Field(default=None, ge=0.0, description="클립 시작 시간")
    clip_end_time: float | None = Field(default=None, ge=0.0, description="클립 종료 시간")
    clip_url: HttpUrl | None = Field(default=None, description="클립 URL")


class RefereeReport(BaseModel):
    """
    AI 심판 보고서 DTO.

    경기 전체의 심판 분석 결과입니다.
    """

    report_id: UUID = Field(default_factory=uuid4, description="보고서 ID")
    task_id: UUID = Field(..., description="분석 태스크 ID")
    rule_set: str = Field(..., description="적용된 규칙 세트")

    # 바이올레이션 목록
    violations: list[ViolationDetection] = Field(default_factory=list, description="바이올레이션 목록")
    total_violations: int = Field(default=0, ge=0, description="총 바이올레이션 수")

    # 파울 목록
    fouls: list[FoulDetection] = Field(default_factory=list, description="파울 목록")
    total_fouls: int = Field(default=0, ge=0, description="총 파울 수")

    # 유형별 집계
    violation_counts: dict[str, int] = Field(default_factory=dict, description="바이올레이션 유형별 수")
    foul_counts: dict[str, int] = Field(default_factory=dict, description="파울 유형별 수")

    # 팀별 집계
    team_violation_counts: dict[str, int] = Field(default_factory=dict, description="팀별 바이올레이션 수")
    team_foul_counts: dict[str, int] = Field(default_factory=dict, description="팀별 파울 수")

    # 통계
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="평균 감지 신뢰도")
    high_confidence_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="높은 신뢰도 비율")

    # 생성 정보
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시간 (UTC)",
    )



# =============================================================================
# 경기 DTO 모듈 익스포트
# =============================================================================
__all__ = [
    "ShotType",
    "ShotResult",
    "CourtZone",
    "PlayType",
    "EventType",
    "HighlightType",
    "ViolationType",
    "FoulType",
    "PlayerInfo",
    "TeamInfo",
    "ShotAttempt",
    "ZoneStatistics",
    "ShotChart",
    "GameEvent",
    "HighlightClip",
    "HighlightReel",
    "PlayerStats",
    "TeamStats",
    "GameStats",
    "ViolationEvent",
    "FoulEvent",
    "RefereeDecision",
    "ReviewSuggestion",
    "ViolationDetection",
    "FoulDetection",
    "RefereeReport",
]

__version__ = "1.0.0"
