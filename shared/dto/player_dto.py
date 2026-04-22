# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: player_dto.py
설명: 선수 정보 데이터 DTO (Data Transfer Object) 정의
      - 선수 ID, 정보, 식별 결과
      - 선수 관리 데이터
      - 다국어 지원 (i18n)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Any, Final
from uuid import UUID, uuid4

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.localization import SupportedLanguage
from shared.dto.geometry_dto import Point3D
from shared.dto.tracking_dto import Track


# =============================================================================
# i18n 모듈 레벨 캐시
# =============================================================================

_TEAM_I18N: Final[dict[str, dict[str, str]]] = {
    "team_a": {"ko": "팀 A (홈)", "en": "Team A (Home)", "ja": "チームA（ホーム）", "zh": "A队（主场）", "es": "Equipo A (Local)"},
    "team_b": {"ko": "팀 B (원정)", "en": "Team B (Away)", "ja": "チームB（アウェイ）", "zh": "B队（客场）", "es": "Equipo B (Visitante)"},
    "unknown": {"ko": "미분류", "en": "Unknown", "ja": "不明", "zh": "未知", "es": "Desconocido"},
}

_PLAYER_ROLE_I18N: Final[dict[str, dict[str, str]]] = {
    "player": {"ko": "선수", "en": "Player", "ja": "選手", "zh": "球员", "es": "Jugador"},
    "referee": {"ko": "심판", "en": "Referee", "ja": "審判", "zh": "裁判", "es": "Árbitro"},
    "coach": {"ko": "코치", "en": "Coach", "ja": "コーチ", "zh": "教练", "es": "Entrenador"},
    "staff": {"ko": "스태프", "en": "Staff", "ja": "スタッフ", "zh": "工作人员", "es": "Personal"},
    "unknown": {"ko": "미분류", "en": "Unknown", "ja": "不明", "zh": "未知", "es": "Desconocido"},
}

_PLAYER_POSITION_I18N: Final[dict[str, dict[str, str]]] = {
    "point_guard": {"ko": "포인트 가드", "en": "Point Guard", "ja": "ポイントガード", "zh": "控球后卫", "es": "Base"},
    "shooting_guard": {"ko": "슈팅 가드", "en": "Shooting Guard", "ja": "シューティングガード", "zh": "得分后卫", "es": "Escolta"},
    "small_forward": {"ko": "스몰 포워드", "en": "Small Forward", "ja": "スモールフォワード", "zh": "小前锋", "es": "Alero"},
    "power_forward": {"ko": "파워 포워드", "en": "Power Forward", "ja": "パワーフォワード", "zh": "大前锋", "es": "Ala-Pívot"},
    "center": {"ko": "센터", "en": "Center", "ja": "センター", "zh": "中锋", "es": "Pívot"},
    "unknown": {"ko": "미분류", "en": "Unknown", "ja": "不明", "zh": "未知", "es": "Desconocido"},
}


# =============================================================================
# 열거형
# =============================================================================

@unique
class Team(str, Enum):
    """
    팀 열거형.

    경기 참가 팀을 정의합니다.

    >>> team = Team.TEAM_A
    >>> team.opponent
    <Team.TEAM_B: 'team_b'>
    """

    # 팀 A (홈)
    TEAM_A = "team_a"

    # 팀 B (원정)
    TEAM_B = "team_b"

    # 심판 (CV_team.pt 3-class 모델 출력 중 하나)
    REFEREE = "referee"

    # 미분류
    UNKNOWN = "unknown"

    @property
    def is_known(self) -> bool:
        """알려진 팀인지."""
        return self != Team.UNKNOWN

    @property
    def opponent(self) -> "Team":
        """상대 팀."""
        if self == Team.TEAM_A:
            return Team.TEAM_B
        elif self == Team.TEAM_B:
            return Team.TEAM_A
        return Team.UNKNOWN

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 팀명 반환 (모듈 레벨 캐시 참조)."""
        entry = _TEAM_I18N[self.value]
        return entry.get(lang.value, entry["ko"])

    def to_korean(self) -> str:
        """한글 팀명 반환 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


@unique
class PlayerRole(str, Enum):
    """
    선수 역할 열거형.

    코트 위 인물의 역할을 정의합니다.
    """

    # 선수
    PLAYER = "player"

    # 심판
    REFEREE = "referee"

    # 코치
    COACH = "coach"

    # 스태프
    STAFF = "staff"

    # 미분류
    UNKNOWN = "unknown"

    @property
    def is_player(self) -> bool:
        """선수인지."""
        return self == PlayerRole.PLAYER

    @property
    def is_on_court(self) -> bool:
        """코트 위 인물인지."""
        return self in (PlayerRole.PLAYER, PlayerRole.REFEREE)

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 역할명 반환 (모듈 레벨 캐시 참조)."""
        entry = _PLAYER_ROLE_I18N[self.value]
        return entry.get(lang.value, entry["ko"])

    def to_korean(self) -> str:
        """한글 역할명 반환 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


@unique
class PlayerPosition(str, Enum):
    """
    선수 포지션 열거형.

    농구 포지션을 정의합니다.
    """

    # 포인트 가드
    POINT_GUARD = "point_guard"

    # 슈팅 가드
    SHOOTING_GUARD = "shooting_guard"

    # 스몰 포워드
    SMALL_FORWARD = "small_forward"

    # 파워 포워드
    POWER_FORWARD = "power_forward"

    # 센터
    CENTER = "center"

    # 미분류
    UNKNOWN = "unknown"

    @property
    def abbreviation(self) -> str:
        """약어."""
        abbr_map: dict[PlayerPosition, str] = {
            PlayerPosition.POINT_GUARD: "PG",
            PlayerPosition.SHOOTING_GUARD: "SG",
            PlayerPosition.SMALL_FORWARD: "SF",
            PlayerPosition.POWER_FORWARD: "PF",
            PlayerPosition.CENTER: "C",
            PlayerPosition.UNKNOWN: "?",
        }
        return abbr_map[self]

    @property
    def is_guard(self) -> bool:
        """가드 포지션인지."""
        return self in (
            PlayerPosition.POINT_GUARD,
            PlayerPosition.SHOOTING_GUARD,
        )

    @property
    def is_forward(self) -> bool:
        """포워드 포지션인지."""
        return self in (
            PlayerPosition.SMALL_FORWARD,
            PlayerPosition.POWER_FORWARD,
        )

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """다국어 포지션명 반환 (모듈 레벨 캐시 참조)."""
        entry = _PLAYER_POSITION_I18N[self.value]
        return entry.get(lang.value, entry["ko"])

    def to_korean(self) -> str:
        """한글 포지션명 반환 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class PlayerID:
    """
    선수 ID.

    선수를 고유하게 식별하는 정보입니다.

    Attributes:
        track_id: 트랙 ID
        jersey_number: 등번호
        team: 팀
        uuid: 고유 UUID
        confidence: 식별 신뢰도
        is_confirmed: 확정된 ID인지
    """

    track_id: int = 0
    jersey_number: int | None = None
    team: Team = Team.UNKNOWN
    uuid: UUID = field(default_factory=uuid4)
    confidence: float = 0.0
    is_confirmed: bool = False

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def is_valid(self) -> bool:
        """유효한 ID인지."""
        return self.track_id > 0

    @property
    def has_jersey_number(self) -> bool:
        """등번호 존재 여부."""
        return self.jersey_number is not None

    @property
    def has_team(self) -> bool:
        """팀 정보 존재 여부."""
        return self.team != Team.UNKNOWN

    @property
    def is_fully_identified(self) -> bool:
        """완전히 식별되었는지."""
        return self.has_jersey_number and self.has_team

    @property
    def display_id(self) -> str:
        """표시용 ID."""
        team_str = self.team.value[:1].upper() if self.team.is_known else "?"
        number_str = str(self.jersey_number) if self.jersey_number is not None else "??"
        return f"{team_str}{number_str}"

    def matches(self, other: "PlayerID") -> bool:
        """다른 ID와 일치하는지."""
        # 등번호와 팀이 모두 일치하면 동일 선수
        if self.has_jersey_number and other.has_jersey_number:
            if self.jersey_number == other.jersey_number and self.team == other.team:
                return True
        # track_id가 일치하면 동일
        return self.track_id == other.track_id


@dataclass(slots=True)
class DetailedPlayerInfo:
    """
    선수 정보.

    선수의 상세 정보입니다.

    Attributes:
        player_id: 선수 ID
        name: 이름
        role: 역할
        position: 포지션
        height_cm: 키 (cm)
        weight_kg: 체중 (kg)
        age: 나이
        stats: 통계 데이터
        created_at: 생성 시간
    """

    player_id: PlayerID = field(default_factory=PlayerID)
    name: str = ""
    role: PlayerRole = PlayerRole.PLAYER
    position: PlayerPosition = PlayerPosition.UNKNOWN
    height_cm: float | None = None
    weight_kg: float | None = None
    age: int | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def team(self) -> Team:
        """팀."""
        return self.player_id.team

    @property
    def jersey_number(self) -> int | None:
        """등번호."""
        return self.player_id.jersey_number

    @property
    def display_name(self) -> str:
        """표시용 이름."""
        if self.name:
            return self.name
        return self.player_id.display_id

    @property
    def has_physical_info(self) -> bool:
        """신체 정보 존재 여부."""
        return self.height_cm is not None or self.weight_kg is not None


@dataclass(slots=True)
class IdentificationSource:
    """
    식별 소스.

    선수 식별에 사용된 정보 소스입니다.

    Attributes:
        source_type: 소스 유형 (jersey_ocr, appearance, tracking, manual)
        confidence: 신뢰도
        camera_id: 카메라 ID (선택적)
        frame_index: 프레임 인덱스 (선택적)
        data: 추가 데이터
    """

    source_type: str = "unknown"
    confidence: float = 0.0
    camera_id: str | None = None
    frame_index: int | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        self.confidence = max(0.0, min(1.0, self.confidence))


@dataclass(slots=True)
class PlayerIdentification:
    """
    선수 식별 결과.

    선수 식별 프로세스의 결과입니다.

    Attributes:
        player_id: 식별된 선수 ID
        sources: 식별 소스 목록
        confidence: 전체 신뢰도
        is_confirmed: 확정 여부
        candidates: 후보 목록 (모호한 경우)
        timestamp: 식별 시간
    """

    player_id: PlayerID = field(default_factory=PlayerID)
    sources: list[IdentificationSource] = field(default_factory=list)
    confidence: float = 0.0
    is_confirmed: bool = False
    candidates: list[tuple[PlayerID, float]] = field(default_factory=list)
    timestamp: datetime | None = None

    @property
    def num_sources(self) -> int:
        """소스 수."""
        return len(self.sources)

    @property
    def is_ambiguous(self) -> bool:
        """모호한 식별인지."""
        return len(self.candidates) > 1

    @property
    def best_source_type(self) -> str | None:
        """가장 신뢰도 높은 소스 유형."""
        if not self.sources:
            return None
        best = max(self.sources, key=lambda s: s.confidence)
        return best.source_type

    # 상태 변이 로직 이관: add_source → detection/player/ 서비스 레이어


@dataclass(slots=True)
class PlayerHistoryEntry:
    """
    선수 히스토리 항목.

    선수의 특정 시점 상태입니다.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        position: 3D 위치
        velocity: 속도
        possession: 볼 소유 여부
        action: 현재 동작
    """

    frame_index: int = 0
    timestamp: float = 0.0
    position: Point3D | None = None
    velocity: tuple[float, float, float] | None = None
    possession: bool = False
    action: str = "idle"


@dataclass(slots=True)
class ManagedPlayer:
    """
    관리되는 선수.

    추적 및 관리 중인 선수의 전체 정보입니다.

    Attributes:
        player_id: 선수 ID
        info: 선수 정보
        track: 연관된 트랙
        identification: 식별 결과
        history: 히스토리
        first_seen_frame: 첫 발견 프레임
        last_seen_frame: 마지막 발견 프레임
        total_frames: 총 관측 프레임 수
        is_active: 활성 상태 여부
    """

    player_id: PlayerID = field(default_factory=PlayerID)
    info: DetailedPlayerInfo | None = None
    track: Track | None = None
    identification: PlayerIdentification | None = None
    history: list[PlayerHistoryEntry] = field(default_factory=list)
    first_seen_frame: int = 0
    last_seen_frame: int = 0
    total_frames: int = 0
    is_active: bool = True

    @property
    def team(self) -> Team:
        """팀."""
        return self.player_id.team

    @property
    def jersey_number(self) -> int | None:
        """등번호."""
        return self.player_id.jersey_number

    @property
    def track_id(self) -> int:
        """트랙 ID."""
        return self.player_id.track_id

    @property
    def is_identified(self) -> bool:
        """식별되었는지."""
        return self.player_id.is_fully_identified

    @property
    def current_position(self) -> Point3D | None:
        """현재 위치."""
        if self.track and self.track.position_3d:
            return self.track.position_3d
        if self.history:
            return self.history[-1].position
        return None

    @property
    def duration_frames(self) -> int:
        """추적 지속 프레임 수."""
        return self.last_seen_frame - self.first_seen_frame

    # 비즈니스 로직 이관 완료: add_history_entry, update_from_track
    # → detection/player/ 서비스 레이어


@dataclass(slots=True)
class PlayerManager:
    """
    선수 관리자.

    모든 관리 중인 선수를 관리합니다.

    Attributes:
        players: 관리 중인 선수 목록
        team_a_players: 팀 A 선수 목록
        team_b_players: 팀 B 선수 목록
        unidentified_players: 미식별 선수 목록
    """

    players: dict[int, ManagedPlayer] = field(default_factory=dict)
    team_a_players: list[int] = field(default_factory=list)
    team_b_players: list[int] = field(default_factory=list)
    unidentified_players: list[int] = field(default_factory=list)

    @property
    def num_players(self) -> int:
        """전체 선수 수."""
        return len(self.players)

    @property
    def num_identified(self) -> int:
        """식별된 선수 수."""
        return sum(1 for p in self.players.values() if p.is_identified)

    # 비즈니스 로직 이관 완료: add_player, get_team_players
    # → detection/player/ 서비스 레이어
    # get_player는 단순 조회로 유지


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # Enum (DTO 고유)
    "Team",
    "PlayerRole",
    "PlayerPosition",

    # 데이터 클래스
    "PlayerID",
    "DetailedPlayerInfo",
    "IdentificationSource",
    "PlayerIdentification",
    "PlayerHistoryEntry",
    "ManagedPlayer",
    "PlayerManager",
]

# 모듈 버전 정보
__version__ = "1.0.0"
