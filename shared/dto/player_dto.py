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

# =============================================================================
# 표준 라이브러리
# =============================================================================
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Any
from uuid import UUID, uuid4

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.localization import SupportedLanguage
from shared.dto.geometry_dto import Point3D
from shared.dto.tracking_dto import Track


# =============================================================================
# 열거형
# =============================================================================

@unique
class Team(str, Enum):
    """
    팀 열거형.

    경기 참가 팀을 정의합니다.
    """

    # 팀 A (홈)
    TEAM_A = "team_a"

    # 팀 B (원정)
    TEAM_B = "team_b"

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
        """
        다국어 팀명 반환.

        Args:
            lang: 언어 코드 (기본: 한국어)

        Returns:
            해당 언어의 팀명
        """
        translations: dict[Team, dict[SupportedLanguage, str]] = {
            Team.TEAM_A: {
                SupportedLanguage.KO: "팀 A (홈)",
                SupportedLanguage.EN: "Team A (Home)",
                SupportedLanguage.JA: "チームA（ホーム）",
                SupportedLanguage.ZH: "A队（主场）",
                SupportedLanguage.ES: "Equipo A (Local)",
            },
            Team.TEAM_B: {
                SupportedLanguage.KO: "팀 B (원정)",
                SupportedLanguage.EN: "Team B (Away)",
                SupportedLanguage.JA: "チームB（アウェイ）",
                SupportedLanguage.ZH: "B队（客场）",
                SupportedLanguage.ES: "Equipo B (Visitante)",
            },
            Team.UNKNOWN: {
                SupportedLanguage.KO: "미분류",
                SupportedLanguage.EN: "Unknown",
                SupportedLanguage.JA: "不明",
                SupportedLanguage.ZH: "未知",
                SupportedLanguage.ES: "Desconocido",
            },
        }
        return translations[self].get(lang, translations[self][SupportedLanguage.KO])

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
        """
        다국어 역할명 반환.

        Args:
            lang: 언어 코드 (기본: 한국어)

        Returns:
            해당 언어의 역할명
        """
        translations: dict[PlayerRole, dict[SupportedLanguage, str]] = {
            PlayerRole.PLAYER: {
                SupportedLanguage.KO: "선수",
                SupportedLanguage.EN: "Player",
                SupportedLanguage.JA: "選手",
                SupportedLanguage.ZH: "球员",
                SupportedLanguage.ES: "Jugador",
            },
            PlayerRole.REFEREE: {
                SupportedLanguage.KO: "심판",
                SupportedLanguage.EN: "Referee",
                SupportedLanguage.JA: "審判",
                SupportedLanguage.ZH: "裁判",
                SupportedLanguage.ES: "Árbitro",
            },
            PlayerRole.COACH: {
                SupportedLanguage.KO: "코치",
                SupportedLanguage.EN: "Coach",
                SupportedLanguage.JA: "コーチ",
                SupportedLanguage.ZH: "教练",
                SupportedLanguage.ES: "Entrenador",
            },
            PlayerRole.STAFF: {
                SupportedLanguage.KO: "스태프",
                SupportedLanguage.EN: "Staff",
                SupportedLanguage.JA: "スタッフ",
                SupportedLanguage.ZH: "工作人员",
                SupportedLanguage.ES: "Personal",
            },
            PlayerRole.UNKNOWN: {
                SupportedLanguage.KO: "미분류",
                SupportedLanguage.EN: "Unknown",
                SupportedLanguage.JA: "不明",
                SupportedLanguage.ZH: "未知",
                SupportedLanguage.ES: "Desconocido",
            },
        }
        return translations[self].get(lang, translations[self][SupportedLanguage.KO])

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
        """
        다국어 포지션명 반환.

        Args:
            lang: 언어 코드 (기본: 한국어)

        Returns:
            해당 언어의 포지션명
        """
        translations: dict[PlayerPosition, dict[SupportedLanguage, str]] = {
            PlayerPosition.POINT_GUARD: {
                SupportedLanguage.KO: "포인트 가드",
                SupportedLanguage.EN: "Point Guard",
                SupportedLanguage.JA: "ポイントガード",
                SupportedLanguage.ZH: "控球后卫",
                SupportedLanguage.ES: "Base",
            },
            PlayerPosition.SHOOTING_GUARD: {
                SupportedLanguage.KO: "슈팅 가드",
                SupportedLanguage.EN: "Shooting Guard",
                SupportedLanguage.JA: "シューティングガード",
                SupportedLanguage.ZH: "得分后卫",
                SupportedLanguage.ES: "Escolta",
            },
            PlayerPosition.SMALL_FORWARD: {
                SupportedLanguage.KO: "스몰 포워드",
                SupportedLanguage.EN: "Small Forward",
                SupportedLanguage.JA: "スモールフォワード",
                SupportedLanguage.ZH: "小前锋",
                SupportedLanguage.ES: "Alero",
            },
            PlayerPosition.POWER_FORWARD: {
                SupportedLanguage.KO: "파워 포워드",
                SupportedLanguage.EN: "Power Forward",
                SupportedLanguage.JA: "パワーフォワード",
                SupportedLanguage.ZH: "大前锋",
                SupportedLanguage.ES: "Ala-Pívot",
            },
            PlayerPosition.CENTER: {
                SupportedLanguage.KO: "센터",
                SupportedLanguage.EN: "Center",
                SupportedLanguage.JA: "センター",
                SupportedLanguage.ZH: "中锋",
                SupportedLanguage.ES: "Pívot",
            },
            PlayerPosition.UNKNOWN: {
                SupportedLanguage.KO: "미분류",
                SupportedLanguage.EN: "Unknown",
                SupportedLanguage.JA: "不明",
                SupportedLanguage.ZH: "未知",
                SupportedLanguage.ES: "Desconocido",
            },
        }
        return translations[self].get(lang, translations[self][SupportedLanguage.KO])

    def to_korean(self) -> str:
        """한글 포지션명 반환 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
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

    def __post_init__(self):
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


@dataclass
class PlayerInfo:
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


@dataclass
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

    def __post_init__(self):
        """초기화 후 처리."""
        self.confidence = max(0.0, min(1.0, self.confidence))


@dataclass
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

    def add_source(self, source: IdentificationSource) -> None:
        """소스 추가."""
        self.sources.append(source)
        # 전체 신뢰도 업데이트 (가중 평균)
        total_conf = sum(s.confidence for s in self.sources)
        self.confidence = total_conf / len(self.sources) if self.sources else 0.0


@dataclass
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


@dataclass
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
    info: PlayerInfo | None = None
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

    def add_history_entry(self, entry: PlayerHistoryEntry) -> None:
        """히스토리 항목 추가."""
        self.history.append(entry)
        self.last_seen_frame = entry.frame_index
        self.total_frames += 1

    def update_from_track(self, track: Track, frame_index: int) -> None:
        """트랙에서 상태 업데이트."""
        self.track = track
        self.last_seen_frame = frame_index

        entry = PlayerHistoryEntry(
            frame_index=frame_index,
            position=track.position_3d,
            velocity=track.velocity,
        )
        self.add_history_entry(entry)


@dataclass
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

    def get_player(self, track_id: int) -> ManagedPlayer | None:
        """트랙 ID로 선수 조회."""
        return self.players.get(track_id)

    def add_player(self, player: ManagedPlayer) -> None:
        """선수 추가."""
        track_id = player.track_id
        self.players[track_id] = player

        # 팀별 분류
        if player.team == Team.TEAM_A:
            if track_id not in self.team_a_players:
                self.team_a_players.append(track_id)
        elif player.team == Team.TEAM_B:
            if track_id not in self.team_b_players:
                self.team_b_players.append(track_id)
        else:
            if track_id not in self.unidentified_players:
                self.unidentified_players.append(track_id)

    def get_team_players(self, team: Team) -> list[ManagedPlayer]:
        """팀별 선수 목록."""
        return [
            p for p in self.players.values()
            if p.team == team
        ]


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # Re-export (다국어 지원)
    "SupportedLanguage",

    # Enum
    "Team",
    "PlayerRole",
    "PlayerPosition",

    # 데이터 클래스
    "PlayerID",
    "PlayerInfo",
    "IdentificationSource",
    "PlayerIdentification",
    "PlayerHistoryEntry",
    "ManagedPlayer",
    "PlayerManager",
]

# 모듈 버전 정보
__version__ = "1.0.0"
