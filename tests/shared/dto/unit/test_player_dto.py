# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_player_dto.py

선수 DTO 유닛 테스트
- __all__ export / __version__ 검증
- Team Enum: 멤버, 프로퍼티 (is_known, opponent), i18n get_name()
- PlayerRole Enum: 멤버, 프로퍼티 (is_player, is_on_court), i18n get_name()
- PlayerPosition Enum: 멤버, 프로퍼티 (abbreviation, is_guard, is_forward), i18n
- PlayerID: __post_init__ clamp, 프로퍼티, matches()
- PlayerInfo: 프로퍼티 (team, jersey_number, display_name, has_physical_info)
- IdentificationSource: __post_init__ clamp
- PlayerIdentification: add_source(), 프로퍼티 (num_sources, is_ambiguous, best_source_type)
- PlayerHistoryEntry: 기본값
- ManagedPlayer: 프로퍼티, add_history_entry(), update_from_track()
- PlayerManager: add_player(), get_player(), get_team_players(), num_identified

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {test_name}")

    def fail(self, test_name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{test_name}: {detail}" if detail else test_name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def assert_eq(r: TestResult, name: str, actual, expected) -> None:
    if actual == expected:
        r.ok(name)
    else:
        r.fail(name, f"expected={expected!r}, actual={actual!r}")


def assert_true(r: TestResult, name: str, value: bool) -> None:
    if value:
        r.ok(name)
    else:
        r.fail(name, "expected True, got False")


def assert_false(r: TestResult, name: str, value: bool) -> None:
    if not value:
        r.ok(name)
    else:
        r.fail(name, "expected False, got True")


def assert_none(r: TestResult, name: str, value) -> None:
    if value is None:
        r.ok(name)
    else:
        r.fail(name, f"expected None, got {value!r}")


def assert_not_none(r: TestResult, name: str, value) -> None:
    if value is not None:
        r.ok(name)
    else:
        r.fail(name, "expected not None, got None")


def assert_close(r: TestResult, name: str, actual: float, expected: float, tol: float = 1e-6) -> None:
    if abs(actual - expected) < tol:
        r.ok(name)
    else:
        r.fail(name, f"expected≈{expected}, actual={actual}")


def assert_isinstance(r: TestResult, name: str, obj, cls) -> None:
    if isinstance(obj, cls):
        r.ok(name)
    else:
        r.fail(name, f"expected isinstance({cls.__name__}), got {type(obj).__name__}")


# ==================== [A] __all__ / __version__ ====================
def test_exports(r: TestResult) -> None:
    """__all__ export 검증"""
    import shared.dto.player_dto as mod
    assert_true(r, "__all__ 존재", hasattr(mod, "__all__"))
    assert_eq(r, "__all__ 개수 = 11", len(mod.__all__), 11)

    expected = [
        "SupportedLanguage", "Team", "PlayerRole", "PlayerPosition",
        "PlayerID", "PlayerInfo", "IdentificationSource",
        "PlayerIdentification", "PlayerHistoryEntry",
        "ManagedPlayer", "PlayerManager",
    ]
    for name in expected:
        assert_true(r, f"__all__에 {name} 포함", name in mod.__all__)
        assert_true(r, f"{name} 접근 가능", hasattr(mod, name))


def test_version(r: TestResult) -> None:
    """__version__ 검증"""
    import shared.dto.player_dto as mod
    assert_true(r, "__version__ 존재", hasattr(mod, "__version__"))
    assert_eq(r, "__version__ = '1.1.0'", mod.__version__, "1.1.0")


# ==================== [B] Team Enum ====================
def test_team_members(r: TestResult) -> None:
    """Team 멤버 검증"""
    from shared.dto.player_dto import Team

    expected = ["TEAM_A", "TEAM_B", "UNKNOWN"]
    actual = [m.name for m in Team]
    assert_eq(r, "Team 멤버 수 = 3", len(actual), 3)
    for name in expected:
        assert_true(r, f"Team.{name} 존재", name in actual)
    assert_eq(r, "TEAM_A.value", Team.TEAM_A.value, "team_a")
    assert_eq(r, "TEAM_B.value", Team.TEAM_B.value, "team_b")
    assert_eq(r, "UNKNOWN.value", Team.UNKNOWN.value, "unknown")


def test_team_properties(r: TestResult) -> None:
    """Team 프로퍼티 검증"""
    from shared.dto.player_dto import Team

    # is_known
    assert_true(r, "TEAM_A is_known", Team.TEAM_A.is_known)
    assert_true(r, "TEAM_B is_known", Team.TEAM_B.is_known)
    assert_false(r, "UNKNOWN not is_known", Team.UNKNOWN.is_known)

    # opponent
    assert_eq(r, "TEAM_A.opponent = TEAM_B", Team.TEAM_A.opponent, Team.TEAM_B)
    assert_eq(r, "TEAM_B.opponent = TEAM_A", Team.TEAM_B.opponent, Team.TEAM_A)
    assert_eq(r, "UNKNOWN.opponent = UNKNOWN", Team.UNKNOWN.opponent, Team.UNKNOWN)


def test_team_i18n(r: TestResult) -> None:
    """Team i18n get_name() 검증"""
    from shared.dto.player_dto import Team
    from shared.constants.localization import SupportedLanguage

    assert_eq(r, "TEAM_A KO", Team.TEAM_A.get_name(SupportedLanguage.KO), "팀 A (홈)")
    assert_eq(r, "TEAM_B EN", Team.TEAM_B.get_name(SupportedLanguage.EN), "Team B (Away)")
    assert_eq(r, "UNKNOWN JA", Team.UNKNOWN.get_name(SupportedLanguage.JA), "不明")
    assert_eq(r, "TEAM_A ZH", Team.TEAM_A.get_name(SupportedLanguage.ZH), "A队（主场）")
    assert_eq(r, "TEAM_B ES", Team.TEAM_B.get_name(SupportedLanguage.ES), "Equipo B (Visitante)")
    assert_eq(r, "to_korean = get_name(KO)", Team.TEAM_A.to_korean(), "팀 A (홈)")
    assert_eq(r, "get_name() 기본값 KO", Team.UNKNOWN.get_name(), "미분류")


# ==================== [C] PlayerRole Enum ====================
def test_player_role_members(r: TestResult) -> None:
    """PlayerRole 멤버 검증"""
    from shared.dto.player_dto import PlayerRole

    expected = ["PLAYER", "REFEREE", "COACH", "STAFF", "UNKNOWN"]
    actual = [m.name for m in PlayerRole]
    assert_eq(r, "PlayerRole 멤버 수 = 5", len(actual), 5)
    for name in expected:
        assert_true(r, f"PlayerRole.{name} 존재", name in actual)


def test_player_role_properties(r: TestResult) -> None:
    """PlayerRole 프로퍼티 검증"""
    from shared.dto.player_dto import PlayerRole

    # is_player
    assert_true(r, "PLAYER is_player", PlayerRole.PLAYER.is_player)
    assert_false(r, "REFEREE not is_player", PlayerRole.REFEREE.is_player)
    assert_false(r, "COACH not is_player", PlayerRole.COACH.is_player)

    # is_on_court
    assert_true(r, "PLAYER is_on_court", PlayerRole.PLAYER.is_on_court)
    assert_true(r, "REFEREE is_on_court", PlayerRole.REFEREE.is_on_court)
    assert_false(r, "COACH not on_court", PlayerRole.COACH.is_on_court)
    assert_false(r, "STAFF not on_court", PlayerRole.STAFF.is_on_court)
    assert_false(r, "UNKNOWN not on_court", PlayerRole.UNKNOWN.is_on_court)


def test_player_role_i18n(r: TestResult) -> None:
    """PlayerRole i18n get_name() 검증"""
    from shared.dto.player_dto import PlayerRole
    from shared.constants.localization import SupportedLanguage

    assert_eq(r, "PLAYER KO", PlayerRole.PLAYER.get_name(SupportedLanguage.KO), "선수")
    assert_eq(r, "REFEREE EN", PlayerRole.REFEREE.get_name(SupportedLanguage.EN), "Referee")
    assert_eq(r, "COACH JA", PlayerRole.COACH.get_name(SupportedLanguage.JA), "コーチ")
    assert_eq(r, "STAFF ZH", PlayerRole.STAFF.get_name(SupportedLanguage.ZH), "工作人员")
    assert_eq(r, "UNKNOWN ES", PlayerRole.UNKNOWN.get_name(SupportedLanguage.ES), "Desconocido")
    assert_eq(r, "to_korean", PlayerRole.PLAYER.to_korean(), "선수")


# ==================== [D] PlayerPosition Enum ====================
def test_player_position_members(r: TestResult) -> None:
    """PlayerPosition 멤버 검증"""
    from shared.dto.player_dto import PlayerPosition

    expected = ["POINT_GUARD", "SHOOTING_GUARD", "SMALL_FORWARD", "POWER_FORWARD", "CENTER", "UNKNOWN"]
    actual = [m.name for m in PlayerPosition]
    assert_eq(r, "PlayerPosition 멤버 수 = 6", len(actual), 6)
    for name in expected:
        assert_true(r, f"PlayerPosition.{name} 존재", name in actual)


def test_player_position_properties(r: TestResult) -> None:
    """PlayerPosition 프로퍼티 검증"""
    from shared.dto.player_dto import PlayerPosition

    # abbreviation
    assert_eq(r, "PG abbreviation", PlayerPosition.POINT_GUARD.abbreviation, "PG")
    assert_eq(r, "SG abbreviation", PlayerPosition.SHOOTING_GUARD.abbreviation, "SG")
    assert_eq(r, "SF abbreviation", PlayerPosition.SMALL_FORWARD.abbreviation, "SF")
    assert_eq(r, "PF abbreviation", PlayerPosition.POWER_FORWARD.abbreviation, "PF")
    assert_eq(r, "C abbreviation", PlayerPosition.CENTER.abbreviation, "C")
    assert_eq(r, "UNKNOWN abbreviation", PlayerPosition.UNKNOWN.abbreviation, "?")

    # is_guard
    assert_true(r, "PG is_guard", PlayerPosition.POINT_GUARD.is_guard)
    assert_true(r, "SG is_guard", PlayerPosition.SHOOTING_GUARD.is_guard)
    assert_false(r, "SF not guard", PlayerPosition.SMALL_FORWARD.is_guard)
    assert_false(r, "C not guard", PlayerPosition.CENTER.is_guard)

    # is_forward
    assert_true(r, "SF is_forward", PlayerPosition.SMALL_FORWARD.is_forward)
    assert_true(r, "PF is_forward", PlayerPosition.POWER_FORWARD.is_forward)
    assert_false(r, "PG not forward", PlayerPosition.POINT_GUARD.is_forward)
    assert_false(r, "C not forward", PlayerPosition.CENTER.is_forward)


def test_player_position_i18n(r: TestResult) -> None:
    """PlayerPosition i18n get_name() 검증"""
    from shared.dto.player_dto import PlayerPosition
    from shared.constants.localization import SupportedLanguage

    assert_eq(r, "PG KO", PlayerPosition.POINT_GUARD.get_name(SupportedLanguage.KO), "포인트 가드")
    assert_eq(r, "SG EN", PlayerPosition.SHOOTING_GUARD.get_name(SupportedLanguage.EN), "Shooting Guard")
    assert_eq(r, "SF JA", PlayerPosition.SMALL_FORWARD.get_name(SupportedLanguage.JA), "スモールフォワード")
    assert_eq(r, "PF ZH", PlayerPosition.POWER_FORWARD.get_name(SupportedLanguage.ZH), "大前锋")
    assert_eq(r, "C ES", PlayerPosition.CENTER.get_name(SupportedLanguage.ES), "Pívot")
    assert_eq(r, "to_korean", PlayerPosition.CENTER.to_korean(), "센터")


# ==================== [E] PlayerID ====================
def test_player_id_defaults(r: TestResult) -> None:
    """PlayerID 기본값 검증"""
    from shared.dto.player_dto import PlayerID, Team
    from uuid import UUID

    pid = PlayerID()
    assert_eq(r, "기본 track_id = 0", pid.track_id, 0)
    assert_none(r, "기본 jersey_number = None", pid.jersey_number)
    assert_eq(r, "기본 team = UNKNOWN", pid.team, Team.UNKNOWN)
    assert_isinstance(r, "uuid는 UUID", pid.uuid, UUID)
    assert_close(r, "기본 confidence = 0.0", pid.confidence, 0.0)
    assert_false(r, "기본 is_confirmed = False", pid.is_confirmed)


def test_player_id_post_init(r: TestResult) -> None:
    """PlayerID __post_init__ clamp 검증"""
    from shared.dto.player_dto import PlayerID

    pid1 = PlayerID(confidence=1.5)
    assert_close(r, "clamp 상한 1.0", pid1.confidence, 1.0)
    pid2 = PlayerID(confidence=-0.3)
    assert_close(r, "clamp 하한 0.0", pid2.confidence, 0.0)


def test_player_id_properties(r: TestResult) -> None:
    """PlayerID 프로퍼티 검증"""
    from shared.dto.player_dto import PlayerID, Team

    # is_valid: track_id > 0
    assert_false(r, "track_id=0 not valid", PlayerID(track_id=0).is_valid)
    assert_true(r, "track_id=1 is_valid", PlayerID(track_id=1).is_valid)

    # has_jersey_number
    assert_false(r, "jersey=None not has", PlayerID().has_jersey_number)
    assert_true(r, "jersey=23 has", PlayerID(jersey_number=23).has_jersey_number)

    # has_team
    assert_false(r, "UNKNOWN not has_team", PlayerID().has_team)
    assert_true(r, "TEAM_A has_team", PlayerID(team=Team.TEAM_A).has_team)

    # is_fully_identified
    assert_false(r, "기본값 not fully identified", PlayerID().is_fully_identified)
    assert_false(r, "jersey만 not fully", PlayerID(jersey_number=23).is_fully_identified)
    assert_false(r, "team만 not fully", PlayerID(team=Team.TEAM_A).is_fully_identified)
    assert_true(r, "jersey+team fully identified",
                PlayerID(jersey_number=23, team=Team.TEAM_A).is_fully_identified)

    # display_id
    assert_eq(r, "display A23", PlayerID(jersey_number=23, team=Team.TEAM_A).display_id, "T23")
    assert_eq(r, "display ?7", PlayerID(jersey_number=7).display_id, "?7")
    assert_eq(r, "display T??", PlayerID(team=Team.TEAM_B).display_id, "T??")
    assert_eq(r, "display ???", PlayerID().display_id, "???")


def test_player_id_matches(r: TestResult) -> None:
    """PlayerID matches() 검증"""
    from shared.dto.player_dto import PlayerID, Team

    pid1 = PlayerID(track_id=1, jersey_number=23, team=Team.TEAM_A)
    pid2 = PlayerID(track_id=2, jersey_number=23, team=Team.TEAM_A)
    pid3 = PlayerID(track_id=1, jersey_number=45, team=Team.TEAM_B)
    pid4 = PlayerID(track_id=3)

    # 등번호+팀 일치
    assert_true(r, "jersey+team 일치 matches", pid1.matches(pid2))
    # track_id 일치
    assert_true(r, "track_id 일치 matches", pid1.matches(pid3))
    # 아무것도 안 맞음
    assert_false(r, "불일치 not matches", pid1.matches(pid4))


# ==================== [F] PlayerInfo ====================
def test_player_info_defaults(r: TestResult) -> None:
    """PlayerInfo 기본값 검증"""
    from shared.dto.player_dto import PlayerInfo, PlayerRole, PlayerPosition, Team

    info = PlayerInfo()
    assert_eq(r, "기본 name = ''", info.name, "")
    assert_eq(r, "기본 role = PLAYER", info.role, PlayerRole.PLAYER)
    assert_eq(r, "기본 position = UNKNOWN", info.position, PlayerPosition.UNKNOWN)
    assert_none(r, "기본 height_cm = None", info.height_cm)
    assert_none(r, "기본 weight_kg = None", info.weight_kg)
    assert_none(r, "기본 age = None", info.age)
    assert_eq(r, "기본 stats = {}", info.stats, {})


def test_player_info_properties(r: TestResult) -> None:
    """PlayerInfo 프로퍼티 검증"""
    from shared.dto.player_dto import PlayerInfo, PlayerID, Team

    pid = PlayerID(jersey_number=23, team=Team.TEAM_A)
    info = PlayerInfo(
        player_id=pid, name="Kim",
        height_cm=185.0, weight_kg=80.0, age=25,
    )

    assert_eq(r, "team = TEAM_A", info.team, Team.TEAM_A)
    assert_eq(r, "jersey_number = 23", info.jersey_number, 23)
    assert_eq(r, "display_name = 'Kim'", info.display_name, "Kim")
    assert_true(r, "has_physical_info (height)", info.has_physical_info)

    # 이름 없을 때 display_name = display_id
    info2 = PlayerInfo(player_id=pid)
    assert_eq(r, "이름 없으면 display_id", info2.display_name, "T23")

    # 신체 정보 없으면
    info3 = PlayerInfo()
    assert_false(r, "신체 정보 없으면 False", info3.has_physical_info)


# ==================== [G] IdentificationSource ====================
def test_identification_source(r: TestResult) -> None:
    """IdentificationSource 검증"""
    from shared.dto.player_dto import IdentificationSource

    src = IdentificationSource()
    assert_eq(r, "기본 source_type = 'unknown'", src.source_type, "unknown")
    assert_close(r, "기본 confidence = 0.0", src.confidence, 0.0)
    assert_none(r, "기본 camera_id = None", src.camera_id)
    assert_eq(r, "기본 data = {}", src.data, {})

    # clamp
    src2 = IdentificationSource(confidence=1.5)
    assert_close(r, "confidence clamp 상한", src2.confidence, 1.0)
    src3 = IdentificationSource(confidence=-0.2)
    assert_close(r, "confidence clamp 하한", src3.confidence, 0.0)


# ==================== [H] PlayerIdentification ====================
def test_player_identification_defaults(r: TestResult) -> None:
    """PlayerIdentification 기본값 검증"""
    from shared.dto.player_dto import PlayerIdentification

    pi = PlayerIdentification()
    assert_eq(r, "기본 sources = []", pi.sources, [])
    assert_close(r, "기본 confidence = 0.0", pi.confidence, 0.0)
    assert_false(r, "기본 is_confirmed = False", pi.is_confirmed)
    assert_eq(r, "기본 candidates = []", pi.candidates, [])
    assert_none(r, "기본 timestamp = None", pi.timestamp)
    assert_eq(r, "기본 num_sources = 0", pi.num_sources, 0)
    assert_false(r, "기본 is_ambiguous = False", pi.is_ambiguous)
    assert_none(r, "기본 best_source_type = None", pi.best_source_type)


def test_player_identification_add_source(r: TestResult) -> None:
    """PlayerIdentification add_source() 검증"""
    from shared.dto.player_dto import PlayerIdentification, IdentificationSource

    pi = PlayerIdentification()

    src1 = IdentificationSource(source_type="jersey_ocr", confidence=0.9)
    pi.add_source(src1)
    assert_eq(r, "add 후 num_sources=1", pi.num_sources, 1)
    assert_close(r, "add1 후 confidence=0.9", pi.confidence, 0.9)
    assert_eq(r, "best_source_type='jersey_ocr'", pi.best_source_type, "jersey_ocr")

    src2 = IdentificationSource(source_type="appearance", confidence=0.7)
    pi.add_source(src2)
    assert_eq(r, "add2 후 num_sources=2", pi.num_sources, 2)
    assert_close(r, "add2 후 confidence=0.8", pi.confidence, 0.8)
    # best는 0.9인 jersey_ocr
    assert_eq(r, "best still jersey_ocr", pi.best_source_type, "jersey_ocr")


def test_player_identification_ambiguous(r: TestResult) -> None:
    """PlayerIdentification is_ambiguous 검증"""
    from shared.dto.player_dto import PlayerIdentification, PlayerID

    pi = PlayerIdentification()
    assert_false(r, "candidates 없으면 not ambiguous", pi.is_ambiguous)

    pi.candidates = [(PlayerID(jersey_number=23), 0.9)]
    assert_false(r, "1개 후보 not ambiguous", pi.is_ambiguous)

    pi.candidates.append((PlayerID(jersey_number=45), 0.6))
    assert_true(r, "2개 후보 is_ambiguous", pi.is_ambiguous)


# ==================== [I] PlayerHistoryEntry ====================
def test_player_history_entry(r: TestResult) -> None:
    """PlayerHistoryEntry 기본값 검증"""
    from shared.dto.player_dto import PlayerHistoryEntry

    entry = PlayerHistoryEntry()
    assert_eq(r, "기본 frame_index=0", entry.frame_index, 0)
    assert_close(r, "기본 timestamp=0.0", entry.timestamp, 0.0)
    assert_none(r, "기본 position=None", entry.position)
    assert_none(r, "기본 velocity=None", entry.velocity)
    assert_false(r, "기본 possession=False", entry.possession)
    assert_eq(r, "기본 action='idle'", entry.action, "idle")


def test_player_history_entry_with_data(r: TestResult) -> None:
    """PlayerHistoryEntry 값 설정 검증"""
    from shared.dto.player_dto import PlayerHistoryEntry
    from shared.dto.geometry_dto import Point3D

    pos = Point3D(1.0, 2.0, 3.0)
    entry = PlayerHistoryEntry(
        frame_index=500, timestamp=16.67,
        position=pos, velocity=(2.0, 1.5, 0.0),
        possession=True, action="shooting",
    )
    assert_eq(r, "frame_index=500", entry.frame_index, 500)
    assert_not_none(r, "position != None", entry.position)
    assert_eq(r, "velocity 설정", entry.velocity, (2.0, 1.5, 0.0))
    assert_true(r, "possession=True", entry.possession)
    assert_eq(r, "action='shooting'", entry.action, "shooting")


# ==================== [J] ManagedPlayer ====================
def test_managed_player_defaults(r: TestResult) -> None:
    """ManagedPlayer 기본값 검증"""
    from shared.dto.player_dto import ManagedPlayer, Team

    mp = ManagedPlayer()
    assert_eq(r, "기본 team = UNKNOWN", mp.team, Team.UNKNOWN)
    assert_none(r, "기본 jersey_number = None", mp.jersey_number)
    assert_eq(r, "기본 track_id = 0", mp.track_id, 0)
    assert_false(r, "기본 is_identified = False", mp.is_identified)
    assert_none(r, "기본 current_position = None", mp.current_position)
    assert_eq(r, "기본 duration_frames = 0", mp.duration_frames, 0)
    assert_none(r, "기본 info = None", mp.info)
    assert_none(r, "기본 track = None", mp.track)
    assert_true(r, "기본 is_active = True", mp.is_active)


def test_managed_player_add_history(r: TestResult) -> None:
    """ManagedPlayer add_history_entry() 검증"""
    from shared.dto.player_dto import ManagedPlayer, PlayerID, PlayerHistoryEntry, Team
    from shared.dto.geometry_dto import Point3D

    pid = PlayerID(track_id=1, jersey_number=23, team=Team.TEAM_A)
    mp = ManagedPlayer(player_id=pid, first_seen_frame=100)

    entry1 = PlayerHistoryEntry(frame_index=100, position=Point3D(1.0, 2.0, 0.0))
    mp.add_history_entry(entry1)
    assert_eq(r, "history 길이=1", len(mp.history), 1)
    assert_eq(r, "last_seen_frame=100", mp.last_seen_frame, 100)
    assert_eq(r, "total_frames=1", mp.total_frames, 1)

    entry2 = PlayerHistoryEntry(frame_index=150, position=Point3D(3.0, 4.0, 0.0))
    mp.add_history_entry(entry2)
    assert_eq(r, "history 길이=2", len(mp.history), 2)
    assert_eq(r, "last_seen_frame=150", mp.last_seen_frame, 150)
    assert_eq(r, "total_frames=2", mp.total_frames, 2)
    assert_eq(r, "duration_frames=50", mp.duration_frames, 50)


def test_managed_player_current_position(r: TestResult) -> None:
    """ManagedPlayer current_position 검증"""
    from shared.dto.player_dto import ManagedPlayer, PlayerHistoryEntry
    from shared.dto.geometry_dto import Point3D

    mp = ManagedPlayer()

    # history에서 가져오기
    entry = PlayerHistoryEntry(position=Point3D(5.0, 6.0, 0.0))
    mp.add_history_entry(entry)
    pos = mp.current_position
    assert_not_none(r, "history에서 current_position", pos)


def test_managed_player_properties(r: TestResult) -> None:
    """ManagedPlayer 식별 프로퍼티 검증"""
    from shared.dto.player_dto import ManagedPlayer, PlayerID, Team

    # 완전 식별된 경우
    pid = PlayerID(track_id=5, jersey_number=23, team=Team.TEAM_A)
    mp = ManagedPlayer(player_id=pid)
    assert_true(r, "fully identified → is_identified", mp.is_identified)
    assert_eq(r, "team = TEAM_A", mp.team, Team.TEAM_A)
    assert_eq(r, "jersey_number = 23", mp.jersey_number, 23)
    assert_eq(r, "track_id = 5", mp.track_id, 5)


# ==================== [K] PlayerManager ====================
def test_player_manager_defaults(r: TestResult) -> None:
    """PlayerManager 기본값 검증"""
    from shared.dto.player_dto import PlayerManager

    pm = PlayerManager()
    assert_eq(r, "기본 num_players=0", pm.num_players, 0)
    assert_eq(r, "기본 num_identified=0", pm.num_identified, 0)
    assert_eq(r, "기본 players={}", pm.players, {})
    assert_eq(r, "기본 team_a=[]", pm.team_a_players, [])
    assert_eq(r, "기본 team_b=[]", pm.team_b_players, [])


def test_player_manager_add_player(r: TestResult) -> None:
    """PlayerManager add_player() 검증"""
    from shared.dto.player_dto import PlayerManager, ManagedPlayer, PlayerID, Team

    pm = PlayerManager()

    # TEAM_A 선수 추가
    pid1 = PlayerID(track_id=1, jersey_number=23, team=Team.TEAM_A)
    mp1 = ManagedPlayer(player_id=pid1)
    pm.add_player(mp1)
    assert_eq(r, "add 후 num_players=1", pm.num_players, 1)
    assert_eq(r, "team_a_players=[1]", pm.team_a_players, [1])
    assert_eq(r, "num_identified=1", pm.num_identified, 1)

    # TEAM_B 선수 추가
    pid2 = PlayerID(track_id=2, jersey_number=45, team=Team.TEAM_B)
    mp2 = ManagedPlayer(player_id=pid2)
    pm.add_player(mp2)
    assert_eq(r, "add2 후 num_players=2", pm.num_players, 2)
    assert_eq(r, "team_b_players=[2]", pm.team_b_players, [2])

    # UNKNOWN 선수 추가
    pid3 = PlayerID(track_id=3)
    mp3 = ManagedPlayer(player_id=pid3)
    pm.add_player(mp3)
    assert_eq(r, "unidentified=[3]", pm.unidentified_players, [3])
    assert_eq(r, "num_identified=2 (unknown 제외)", pm.num_identified, 2)


def test_player_manager_get_player(r: TestResult) -> None:
    """PlayerManager get_player() 검증"""
    from shared.dto.player_dto import PlayerManager, ManagedPlayer, PlayerID, Team

    pm = PlayerManager()
    pid = PlayerID(track_id=5, jersey_number=7, team=Team.TEAM_A)
    pm.add_player(ManagedPlayer(player_id=pid))

    found = pm.get_player(5)
    assert_not_none(r, "track_id=5 조회 성공", found)
    assert_eq(r, "조회 jersey=7", found.jersey_number, 7)

    not_found = pm.get_player(999)
    assert_none(r, "track_id=999 조회 None", not_found)


def test_player_manager_get_team_players(r: TestResult) -> None:
    """PlayerManager get_team_players() 검증"""
    from shared.dto.player_dto import PlayerManager, ManagedPlayer, PlayerID, Team

    pm = PlayerManager()
    for i, num in enumerate([23, 7, 11], start=1):
        pm.add_player(ManagedPlayer(player_id=PlayerID(track_id=i, jersey_number=num, team=Team.TEAM_A)))
    pm.add_player(ManagedPlayer(player_id=PlayerID(track_id=10, jersey_number=5, team=Team.TEAM_B)))

    team_a = pm.get_team_players(Team.TEAM_A)
    assert_eq(r, "TEAM_A 선수 수=3", len(team_a), 3)

    team_b = pm.get_team_players(Team.TEAM_B)
    assert_eq(r, "TEAM_B 선수 수=1", len(team_b), 1)

    unknown = pm.get_team_players(Team.UNKNOWN)
    assert_eq(r, "UNKNOWN 선수 수=0", len(unknown), 0)


# ==================== [L] SupportedLanguage re-export ====================
def test_supported_language_reexport(r: TestResult) -> None:
    """SupportedLanguage re-export 검증"""
    from shared.dto.player_dto import SupportedLanguage
    from shared.constants.localization import SupportedLanguage as Original

    assert_true(r, "SupportedLanguage 동일 객체", SupportedLanguage is Original)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("player_dto.py v1.1.0 유닛 테스트")
    print("=" * 60)

    print("\n--- [A] __all__ / __version__ ---")
    test_exports(r)
    test_version(r)

    print("\n--- [B] Team Enum ---")
    test_team_members(r)
    test_team_properties(r)
    test_team_i18n(r)

    print("\n--- [C] PlayerRole Enum ---")
    test_player_role_members(r)
    test_player_role_properties(r)
    test_player_role_i18n(r)

    print("\n--- [D] PlayerPosition Enum ---")
    test_player_position_members(r)
    test_player_position_properties(r)
    test_player_position_i18n(r)

    print("\n--- [E] PlayerID ---")
    test_player_id_defaults(r)
    test_player_id_post_init(r)
    test_player_id_properties(r)
    test_player_id_matches(r)

    print("\n--- [F] PlayerInfo ---")
    test_player_info_defaults(r)
    test_player_info_properties(r)

    print("\n--- [G] IdentificationSource ---")
    test_identification_source(r)

    print("\n--- [H] PlayerIdentification ---")
    test_player_identification_defaults(r)
    test_player_identification_add_source(r)
    test_player_identification_ambiguous(r)

    print("\n--- [I] PlayerHistoryEntry ---")
    test_player_history_entry(r)
    test_player_history_entry_with_data(r)

    print("\n--- [J] ManagedPlayer ---")
    test_managed_player_defaults(r)
    test_managed_player_add_history(r)
    test_managed_player_current_position(r)
    test_managed_player_properties(r)

    print("\n--- [K] PlayerManager ---")
    test_player_manager_defaults(r)
    test_player_manager_add_player(r)
    test_player_manager_get_player(r)
    test_player_manager_get_team_players(r)

    print("\n--- [L] SupportedLanguage re-export ---")
    test_supported_language_reexport(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
