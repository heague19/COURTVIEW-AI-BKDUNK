# -*- coding: utf-8 -*-
"""
tests/shared/dto/performance/test_game_dto_perf.py

경기 분석 DTO 성능 테스트
- 모듈 임포트 시간
- Pydantic BaseModel 인스턴스 생성 속도
- Enum i18n 조회 속도
- 통계 계산 메서드 속도 (EFF, TS%, eFG%, GameScore, Pace, FourFactors)
- to_visualization_data / to_box_score_dict 변환 속도
- get_hot_zones / get_cold_zones 조회 속도
- 대량 ShotAttempt 배치 생성

성능 기준:
- 모듈 임포트: < 500ms (cold)
- Pydantic 생성: < 50μs
- i18n 조회: < 5μs (캐시)
- 통계 계산: < 10μs
- dict 변환: < 50μs

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

    def info(self, msg: str) -> None:
        print(f"  [INFO] {msg}")

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


# ==================== 1. 모듈 임포트 시간 ====================
def test_module_import_time(r: PerfResult) -> None:
    """모듈 cold 임포트 시간"""
    import importlib
    mod_name = "shared.dto.game_dto"
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


# ==================== 2. Pydantic 생성 속도 ====================
def test_player_info_creation(r: PerfResult) -> None:
    """PlayerInfo 인스턴스 생성 속도"""
    from shared.dto.game_dto import PlayerInfo

    def create():
        PlayerInfo(tracking_id=1, jersey_number=23)

    elapsed = measure(create, 50000)
    limit = 30.0
    if elapsed < limit:
        r.ok("PlayerInfo 생성", elapsed, limit)
    else:
        r.fail("PlayerInfo 생성", elapsed, limit)


def test_shot_attempt_creation(r: PerfResult) -> None:
    """ShotAttempt 인스턴스 생성 속도"""
    from shared.dto.game_dto import ShotAttempt, ShotType, ShotResult, CourtZone

    def create():
        ShotAttempt(
            player_tracking_id=1,
            shot_type=ShotType.THREE_POINTER,
            result=ShotResult.MADE,
            court_zone=CourtZone.THREE_CENTER,
            shot_x=0.5, shot_y=0.8,
            frame_number=500,
            timestamp=16.5,
            points=3,
        )

    elapsed = measure(create, 50000)
    limit = 50.0
    if elapsed < limit:
        r.ok("ShotAttempt 생성", elapsed, limit)
    else:
        r.fail("ShotAttempt 생성", elapsed, limit)


def test_player_stats_creation(r: PerfResult) -> None:
    """PlayerStats 인스턴스 생성 속도"""
    from shared.dto.game_dto import PlayerStats

    def create():
        PlayerStats(
            player_tracking_id=1,
            points=25,
            field_goals_made=9, field_goals_attempted=20,
            three_pointers_made=3, three_pointers_attempted=8,
            free_throws_made=4, free_throws_attempted=5,
            offensive_rebounds=2, defensive_rebounds=8, total_rebounds=10,
            assists=5, steals=2, blocks=1, turnovers=3, personal_fouls=2,
        )

    elapsed = measure(create, 50000)
    limit = 50.0
    if elapsed < limit:
        r.ok("PlayerStats 생성", elapsed, limit)
    else:
        r.fail("PlayerStats 생성", elapsed, limit)


def test_game_event_creation(r: PerfResult) -> None:
    """GameEvent 인스턴스 생성 속도"""
    from shared.dto.game_dto import GameEvent, EventType

    def create():
        GameEvent(
            event_type=EventType.SHOT_MADE,
            primary_player_id=1,
            frame_number=300,
            timestamp=10.0,
            quarter=1,
        )

    elapsed = measure(create, 50000)
    limit = 30.0
    if elapsed < limit:
        r.ok("GameEvent 생성", elapsed, limit)
    else:
        r.fail("GameEvent 생성", elapsed, limit)


def test_referee_report_creation(r: PerfResult) -> None:
    """RefereeReport 인스턴스 생성 속도"""
    from shared.dto.game_dto import RefereeReport
    from uuid import uuid4

    tid = uuid4()

    def create():
        RefereeReport(task_id=tid, rule_set="FIBA")

    elapsed = measure(create, 50000)
    limit = 30.0
    if elapsed < limit:
        r.ok("RefereeReport 생성", elapsed, limit)
    else:
        r.fail("RefereeReport 생성", elapsed, limit)


# ==================== 3. Enum i18n 조회 속도 ====================
def test_i18n_shot_type(r: PerfResult) -> None:
    """ShotType.get_name i18n 조회 속도"""
    from shared.dto.game_dto import ShotType
    from shared.constants.localization import SupportedLanguage
    st = ShotType.THREE_POINTER

    def lookup():
        _ = st.get_name(SupportedLanguage.KO)
        _ = st.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("ShotType i18n", per_call, limit)
    else:
        r.fail("ShotType i18n", per_call, limit)


def test_i18n_court_zone(r: PerfResult) -> None:
    """CourtZone.get_name i18n 조회 속도 (20멤버)"""
    from shared.dto.game_dto import CourtZone
    from shared.constants.localization import SupportedLanguage
    cz = CourtZone.PAINT_CENTER

    def lookup():
        _ = cz.get_name(SupportedLanguage.KO)
        _ = cz.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("CourtZone i18n", per_call, limit)
    else:
        r.fail("CourtZone i18n", per_call, limit)


def test_i18n_highlight_type(r: PerfResult) -> None:
    """HighlightType.get_name i18n 조회 속도"""
    from shared.dto.game_dto import HighlightType
    from shared.constants.localization import SupportedLanguage
    ht = HighlightType.SPECTACULAR_DUNK

    def lookup():
        _ = ht.get_name(SupportedLanguage.KO)
        _ = ht.get_name(SupportedLanguage.EN)

    elapsed = measure(lookup, 50000)
    per_call = elapsed / 2
    limit = 5.0
    if per_call < limit:
        r.ok("HighlightType i18n", per_call, limit)
    else:
        r.fail("HighlightType i18n", per_call, limit)


# ==================== 4. 통계 계산 메서드 속도 ====================
def test_calculate_efficiency(r: PerfResult) -> None:
    """PlayerStats.calculate_efficiency 속도"""
    from shared.dto.game_dto import PlayerStats

    ps = PlayerStats(
        player_tracking_id=1,
        points=25,
        field_goals_made=9, field_goals_attempted=20,
        three_pointers_made=3, three_pointers_attempted=8,
        free_throws_made=4, free_throws_attempted=5,
        offensive_rebounds=2, defensive_rebounds=8, total_rebounds=10,
        assists=5, steals=2, blocks=1, turnovers=3,
    )

    def calc():
        _ = ps.calculate_efficiency()

    elapsed = measure(calc, 100000)
    limit = 10.0
    if elapsed < limit:
        r.ok("calculate_efficiency", elapsed, limit)
    else:
        r.fail("calculate_efficiency", elapsed, limit)


def test_calculate_ts_percentage(r: PerfResult) -> None:
    """PlayerStats.calculate_true_shooting_percentage 속도"""
    from shared.dto.game_dto import PlayerStats

    ps = PlayerStats(
        player_tracking_id=1,
        points=25,
        field_goals_made=9, field_goals_attempted=20,
        free_throws_made=4, free_throws_attempted=5,
    )

    def calc():
        _ = ps.calculate_true_shooting_percentage()

    elapsed = measure(calc, 100000)
    limit = 10.0
    if elapsed < limit:
        r.ok("calculate_ts%", elapsed, limit)
    else:
        r.fail("calculate_ts%", elapsed, limit)


def test_calculate_game_score(r: PerfResult) -> None:
    """PlayerStats.calculate_game_score 속도 (Hollinger)"""
    from shared.dto.game_dto import PlayerStats

    ps = PlayerStats(
        player_tracking_id=1,
        points=25,
        field_goals_made=9, field_goals_attempted=20,
        three_pointers_made=3, three_pointers_attempted=8,
        free_throws_made=4, free_throws_attempted=5,
        offensive_rebounds=2, defensive_rebounds=8, total_rebounds=10,
        assists=5, steals=2, blocks=1, turnovers=3, personal_fouls=2,
    )

    def calc():
        _ = ps.calculate_game_score()

    elapsed = measure(calc, 100000)
    limit = 10.0
    if elapsed < limit:
        r.ok("calculate_game_score", elapsed, limit)
    else:
        r.fail("calculate_game_score", elapsed, limit)


def test_calculate_pace(r: PerfResult) -> None:
    """TeamStats.calculate_pace 속도"""
    from shared.dto.game_dto import TeamStats

    ts = TeamStats(
        team_name="Home",
        field_goals_made=35, field_goals_attempted=80,
        three_pointers_made=10, three_pointers_attempted=25,
        free_throws_made=15, free_throws_attempted=20,
        offensive_rebounds=10, defensive_rebounds=30,
        assists=20, turnovers=12,
    )

    def calc():
        _ = ts.calculate_pace(game_minutes=48.0)

    elapsed = measure(calc, 100000)
    limit = 10.0
    if elapsed < limit:
        r.ok("calculate_pace", elapsed, limit)
    else:
        r.fail("calculate_pace", elapsed, limit)


def test_get_four_factors(r: PerfResult) -> None:
    """TeamStats.get_four_factors 속도"""
    from shared.dto.game_dto import TeamStats

    ts = TeamStats(
        team_name="Home",
        field_goals_made=35, field_goals_attempted=80,
        three_pointers_made=10, three_pointers_attempted=25,
        free_throws_made=15, free_throws_attempted=20,
        offensive_rebounds=10, defensive_rebounds=30,
        assists=20, turnovers=12,
    )

    def calc():
        _ = ts.get_four_factors()

    elapsed = measure(calc, 50000)
    limit = 20.0
    if elapsed < limit:
        r.ok("get_four_factors", elapsed, limit)
    else:
        r.fail("get_four_factors", elapsed, limit)


# ==================== 5. dict 변환 속도 ====================
def test_to_box_score_dict_speed(r: PerfResult) -> None:
    """PlayerStats.to_box_score_dict 변환 속도"""
    from shared.dto.game_dto import PlayerStats
    from shared.constants.localization import SupportedLanguage

    ps = PlayerStats(
        player_tracking_id=1,
        points=25,
        field_goals_made=9, field_goals_attempted=20,
        three_pointers_made=3, three_pointers_attempted=8,
        free_throws_made=4, free_throws_attempted=5,
        offensive_rebounds=2, defensive_rebounds=8, total_rebounds=10,
        assists=5, steals=2, blocks=1, turnovers=3, personal_fouls=2,
    )

    def convert():
        _ = ps.to_box_score_dict(SupportedLanguage.KO)

    elapsed = measure(convert, 50000)
    limit = 50.0
    if elapsed < limit:
        r.ok("to_box_score_dict", elapsed, limit)
    else:
        r.fail("to_box_score_dict", elapsed, limit)


def test_to_summary_dict_speed(r: PerfResult) -> None:
    """TeamStats.to_summary_dict 변환 속도"""
    from shared.dto.game_dto import TeamStats
    from shared.constants.localization import SupportedLanguage

    ts = TeamStats(
        team_name="Home",
        field_goals_made=35, field_goals_attempted=80,
        three_pointers_made=10, three_pointers_attempted=25,
        free_throws_made=15, free_throws_attempted=20,
        offensive_rebounds=10, defensive_rebounds=30,
        assists=20, turnovers=12,
    )

    def convert():
        _ = ts.to_summary_dict(SupportedLanguage.EN)

    elapsed = measure(convert, 50000)
    limit = 50.0
    if elapsed < limit:
        r.ok("to_summary_dict", elapsed, limit)
    else:
        r.fail("to_summary_dict", elapsed, limit)


def test_to_visualization_data_speed(r: PerfResult) -> None:
    """ShotChart.to_visualization_data 변환 속도"""
    from shared.dto.game_dto import (
        ShotChart, ShotAttempt, ShotType, ShotResult,
        CourtZone, ZoneStatistics,
    )
    from shared.constants.localization import SupportedLanguage
    from uuid import uuid4

    shots = [
        ShotAttempt(
            player_tracking_id=1,
            shot_type=ShotType.LAYUP, result=ShotResult.MADE,
            court_zone=CourtZone.PAINT_CENTER,
            shot_x=0.0, shot_y=0.1, frame_number=100, timestamp=3.3, points=2,
        ),
        ShotAttempt(
            player_tracking_id=1,
            shot_type=ShotType.THREE_POINTER, result=ShotResult.MISSED,
            court_zone=CourtZone.THREE_CENTER,
            shot_x=0.0, shot_y=0.8, frame_number=200, timestamp=6.6, points=0,
        ),
    ]
    chart = ShotChart(
        task_id=uuid4(),
        total_attempts=2, total_made=1,
        field_goal_percentage=50.0,
        shots=shots,
        zone_stats={
            CourtZone.PAINT_CENTER.value: ZoneStatistics(
                zone=CourtZone.PAINT_CENTER, attempts=1, made=1, percentage=100.0, points=2,
            ),
        },
    )

    def convert():
        _ = chart.to_visualization_data(SupportedLanguage.KO)

    elapsed = measure(convert, 10000)
    limit = 100.0
    if elapsed < limit:
        r.ok("to_visualization_data", elapsed, limit)
    else:
        r.fail("to_visualization_data", elapsed, limit)


# ==================== 6. hot/cold zone 조회 ====================
def test_get_hot_cold_zones_speed(r: PerfResult) -> None:
    """ShotChart.get_hot_zones / get_cold_zones 조회 속도"""
    from shared.dto.game_dto import ShotChart, CourtZone, ZoneStatistics
    from uuid import uuid4

    zones = {}
    zone_list = list(CourtZone)
    for i, z in enumerate(zone_list):
        pct = 20.0 + i * 4.0
        made = int(10 * pct / 100)
        zones[z.value] = ZoneStatistics(
            zone=z, attempts=10, made=made, percentage=round(made / 10 * 100, 1), points=made * 2,
        )

    chart = ShotChart(
        task_id=uuid4(),
        total_attempts=200, total_made=100,
        field_goal_percentage=50.0,
        zone_stats=zones,
    )

    def hot():
        _ = chart.get_hot_zones(min_attempts=3, min_percentage=50.0)

    def cold():
        _ = chart.get_cold_zones(min_attempts=3, max_percentage=30.0)

    elapsed_hot = measure(hot, 50000)
    limit = 20.0
    if elapsed_hot < limit:
        r.ok("get_hot_zones(20z)", elapsed_hot, limit)
    else:
        r.fail("get_hot_zones(20z)", elapsed_hot, limit)

    elapsed_cold = measure(cold, 50000)
    if elapsed_cold < limit:
        r.ok("get_cold_zones(20z)", elapsed_cold, limit)
    else:
        r.fail("get_cold_zones(20z)", elapsed_cold, limit)


# ==================== 7. 대량 처리 ====================
def test_batch_shot_attempts(r: PerfResult) -> None:
    """ShotAttempt 20개 배치 생성"""
    from shared.dto.game_dto import ShotAttempt, ShotType, ShotResult, CourtZone

    types = list(ShotType)
    results = list(ShotResult)
    zones = list(CourtZone)

    def batch():
        for i in range(20):
            ShotAttempt(
                player_tracking_id=i % 5,
                shot_type=types[i % len(types)],
                result=results[i % len(results)],
                court_zone=zones[i % len(zones)],
                shot_x=(i % 10) * 0.1,
                shot_y=(i % 10) * 0.1,
                frame_number=i * 100,
                timestamp=i * 3.3,
                points=2 if i % 3 == 0 else 3,
            )

    elapsed = measure(batch, 5000)
    limit = 500.0
    if elapsed < limit:
        r.ok("ShotAttempt×20", elapsed, limit)
    else:
        r.fail("ShotAttempt×20", elapsed, limit)


# ==================== main ====================
def main() -> int:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = PerfResult()
    print("\n" + "=" * 60)
    print("game_dto.py v3.0.0 성능 테스트")
    print("=" * 60)

    print("\n--- 모듈 임포트 ---")
    test_module_import_time(r)

    print("\n--- Pydantic 생성 ---")
    test_player_info_creation(r)
    test_shot_attempt_creation(r)
    test_player_stats_creation(r)
    test_game_event_creation(r)
    test_referee_report_creation(r)

    print("\n--- i18n 조회 ---")
    test_i18n_shot_type(r)
    test_i18n_court_zone(r)
    test_i18n_highlight_type(r)

    print("\n--- 통계 계산 ---")
    test_calculate_efficiency(r)
    test_calculate_ts_percentage(r)
    test_calculate_game_score(r)
    test_calculate_pace(r)
    test_get_four_factors(r)

    print("\n--- dict 변환 ---")
    test_to_box_score_dict_speed(r)
    test_to_summary_dict_speed(r)
    test_to_visualization_data_speed(r)

    print("\n--- hot/cold zone ---")
    test_get_hot_cold_zones_speed(r)

    print("\n--- 대량 처리 ---")
    test_batch_shot_attempts(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
