# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_player_dto_perf.py

선수 DTO 성능 테스트
- 모듈 임포트 시간
- dataclass 인스턴스 생성 속도
- 프로퍼티 접근 속도
- 메서드 호출 속도 (matches, add_source, add_player)
- i18n get_name() 속도
- 대량 배치 처리

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import gc
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class PerfResult:
    """성능 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.passed += 1
        ratio = elapsed_us / limit_us * 100
        print(f"  [PASS] {test_name}: {elapsed_us:.2f}μs ({ratio:.0f}% of {limit_us:.0f}μs limit)")

    def fail(self, test_name: str, elapsed_us: float, limit_us: float) -> None:
        self.failed += 1
        self.errors.append(f"{test_name}: {elapsed_us:.2f}μs > {limit_us:.0f}μs")
        print(f"  [FAIL] {test_name}: {elapsed_us:.2f}μs (limit: {limit_us:.0f}μs)")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"성능 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*60}")


def measure(func, iterations: int = 10000) -> float:
    """함수 실행 시간 측정 (μs/회)"""
    gc.disable()
    try:
        for _ in range(min(iterations, 1000)):
            func()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            func()
        elapsed_ns = time.perf_counter_ns() - start
        return elapsed_ns / iterations / 1000
    finally:
        gc.enable()


# ==================== 1. 모듈 임포트 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.player_dto"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.disable()
    start = time.perf_counter_ns()
    importlib.import_module(mod_name)
    elapsed_ns = time.perf_counter_ns() - start
    gc.enable()
    elapsed_us = elapsed_ns / 1000
    limit_us = 500_000
    if elapsed_us < limit_us:
        r.ok("모듈 임포트", elapsed_us, limit_us)
    else:
        r.fail("모듈 임포트", elapsed_us, limit_us)


# ==================== 2. dataclass 생성 ====================
def test_player_id_creation(r: PerfResult) -> None:
    """PlayerID 생성 속도 (UUID + __post_init__)"""
    from shared.dto.player_dto import PlayerID, Team

    def create():
        PlayerID(track_id=1, jersey_number=23, team=Team.TEAM_A, confidence=0.9)

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("PlayerID 생성", elapsed, limit)
    else:
        r.fail("PlayerID 생성", elapsed, limit)


def test_player_info_creation(r: PerfResult) -> None:
    """PlayerInfo 생성 속도"""
    from shared.dto.player_dto import PlayerInfo, PlayerRole, PlayerPosition

    def create():
        PlayerInfo(
            name="Kim", role=PlayerRole.PLAYER,
            position=PlayerPosition.SHOOTING_GUARD,
            height_cm=185.0, weight_kg=80.0, age=25,
        )

    elapsed = measure(create, 50000)
    limit = 10.0
    if elapsed < limit:
        r.ok("PlayerInfo 생성", elapsed, limit)
    else:
        r.fail("PlayerInfo 생성", elapsed, limit)


def test_identification_source_creation(r: PerfResult) -> None:
    """IdentificationSource 생성 속도"""
    from shared.dto.player_dto import IdentificationSource

    def create():
        IdentificationSource(source_type="jersey_ocr", confidence=0.9, camera_id="cam_01")

    elapsed = measure(create, 100000)
    limit = 5.0
    if elapsed < limit:
        r.ok("IdentificationSource 생성", elapsed, limit)
    else:
        r.fail("IdentificationSource 생성", elapsed, limit)


def test_managed_player_creation(r: PerfResult) -> None:
    """ManagedPlayer 생성 속도"""
    from shared.dto.player_dto import ManagedPlayer, PlayerID, Team

    pid = PlayerID(track_id=1, jersey_number=23, team=Team.TEAM_A)

    def create():
        ManagedPlayer(player_id=pid, first_seen_frame=100)

    elapsed = measure(create, 50000)
    limit = 5.0
    if elapsed < limit:
        r.ok("ManagedPlayer 생성", elapsed, limit)
    else:
        r.fail("ManagedPlayer 생성", elapsed, limit)


# ==================== 3. 프로퍼티 접근 ====================
def test_player_id_properties(r: PerfResult) -> None:
    """PlayerID 프로퍼티 접근 속도"""
    from shared.dto.player_dto import PlayerID, Team

    pid = PlayerID(track_id=1, jersey_number=23, team=Team.TEAM_A, confidence=0.9)

    def access():
        _ = pid.is_valid
        _ = pid.has_jersey_number
        _ = pid.has_team
        _ = pid.is_fully_identified
        _ = pid.display_id

    elapsed = measure(access, 100000)
    per_call = elapsed / 5
    limit = 2.0
    if per_call < limit:
        r.ok("PlayerID 프로퍼티", per_call, limit)
    else:
        r.fail("PlayerID 프로퍼티", per_call, limit)


def test_managed_player_properties(r: PerfResult) -> None:
    """ManagedPlayer 프로퍼티 접근 속도"""
    from shared.dto.player_dto import ManagedPlayer, PlayerID, Team

    pid = PlayerID(track_id=5, jersey_number=23, team=Team.TEAM_A)
    mp = ManagedPlayer(player_id=pid)

    def access():
        _ = mp.team
        _ = mp.jersey_number
        _ = mp.track_id
        _ = mp.is_identified
        _ = mp.duration_frames

    elapsed = measure(access, 100000)
    per_call = elapsed / 5
    limit = 2.0
    if per_call < limit:
        r.ok("ManagedPlayer 프로퍼티", per_call, limit)
    else:
        r.fail("ManagedPlayer 프로퍼티", per_call, limit)


# ==================== 4. 메서드 호출 ====================
def test_matches_method(r: PerfResult) -> None:
    """PlayerID.matches() 속도"""
    from shared.dto.player_dto import PlayerID, Team

    pid1 = PlayerID(track_id=1, jersey_number=23, team=Team.TEAM_A)
    pid2 = PlayerID(track_id=2, jersey_number=23, team=Team.TEAM_A)

    def call():
        pid1.matches(pid2)

    elapsed = measure(call, 100000)
    limit = 2.0
    if elapsed < limit:
        r.ok("matches()", elapsed, limit)
    else:
        r.fail("matches()", elapsed, limit)


def test_i18n_get_name(r: PerfResult) -> None:
    """Enum i18n get_name() 속도"""
    from shared.dto.player_dto import Team, PlayerRole, PlayerPosition
    from shared.constants.localization import SupportedLanguage

    def call():
        Team.TEAM_A.get_name(SupportedLanguage.KO)
        PlayerRole.PLAYER.get_name(SupportedLanguage.EN)
        PlayerPosition.CENTER.get_name(SupportedLanguage.JA)

    elapsed = measure(call, 50000)
    per_call = elapsed / 3
    limit = 10.0
    if per_call < limit:
        r.ok("i18n get_name()", per_call, limit)
    else:
        r.fail("i18n get_name()", per_call, limit)


def test_player_manager_workflow(r: PerfResult) -> None:
    """PlayerManager add+get 워크플로우 속도"""
    from shared.dto.player_dto import PlayerManager, ManagedPlayer, PlayerID, Team

    def workflow():
        pm = PlayerManager()
        for i in range(5):
            pid = PlayerID(track_id=i + 1, jersey_number=i * 10, team=Team.TEAM_A)
            pm.add_player(ManagedPlayer(player_id=pid))
        _ = pm.num_identified
        pm.get_player(3)
        pm.get_team_players(Team.TEAM_A)

    elapsed = measure(workflow, 10000)
    limit = 50.0
    if elapsed < limit:
        r.ok("Manager 워크플로우", elapsed, limit)
    else:
        r.fail("Manager 워크플로우", elapsed, limit)


# ==================== 5. 대량 처리 ====================
def test_batch_player_ids(r: PerfResult) -> None:
    """PlayerID 20개 배치 생성"""
    from shared.dto.player_dto import PlayerID, Team

    teams = [Team.TEAM_A, Team.TEAM_B, Team.UNKNOWN]

    def batch():
        for i in range(20):
            PlayerID(
                track_id=i + 1,
                jersey_number=i % 100,
                team=teams[i % 3],
                confidence=0.5 + (i % 5) * 0.1,
            )

    elapsed = measure(batch, 5000)
    limit = 300.0
    if elapsed < limit:
        r.ok("PlayerID×20", elapsed, limit)
    else:
        r.fail("PlayerID×20", elapsed, limit)


def test_full_managed_player_snapshot(r: PerfResult) -> None:
    """풀 ManagedPlayer + history 스냅샷 생성"""
    from shared.dto.player_dto import (
        ManagedPlayer, PlayerID, PlayerInfo, PlayerIdentification,
        IdentificationSource, PlayerHistoryEntry, Team, PlayerRole,
        PlayerPosition,
    )
    from shared.dto.geometry_dto import Point3D

    def create():
        pid = PlayerID(track_id=1, jersey_number=23, team=Team.TEAM_A, confidence=0.95)
        info = PlayerInfo(
            player_id=pid, name="Kim",
            role=PlayerRole.PLAYER,
            position=PlayerPosition.SHOOTING_GUARD,
        )
        ident = PlayerIdentification(player_id=pid, confidence=0.9)
        ident.add_source(IdentificationSource(source_type="jersey_ocr", confidence=0.9))
        history = [
            PlayerHistoryEntry(frame_index=i * 30, position=Point3D(float(i), 0.0, 0.0))
            for i in range(5)
        ]
        ManagedPlayer(
            player_id=pid, info=info,
            identification=ident, history=history,
            first_seen_frame=0, last_seen_frame=120,
            total_frames=5,
        )

    elapsed = measure(create, 5000)
    limit = 200.0
    if elapsed < limit:
        r.ok("풀 ManagedPlayer 스냅샷", elapsed, limit)
    else:
        r.fail("풀 ManagedPlayer 스냅샷", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("player_dto.py v1.1.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- dataclass 생성 ---")
    test_player_id_creation(r)
    test_player_info_creation(r)
    test_identification_source_creation(r)
    test_managed_player_creation(r)

    print("\n--- 프로퍼티 접근 ---")
    test_player_id_properties(r)
    test_managed_player_properties(r)

    print("\n--- 메서드 호출 ---")
    test_matches_method(r)
    test_i18n_get_name(r)
    test_player_manager_workflow(r)

    print("\n--- 대량 처리 ---")
    test_batch_player_ids(r)
    test_full_managed_player_snapshot(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
