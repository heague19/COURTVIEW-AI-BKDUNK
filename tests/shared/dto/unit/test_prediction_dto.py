# -*- coding: utf-8 -*-
"""
tests/shared/dto/unit/test_prediction_dto.py

예측 DTO 유닛 테스트
- 모듈 메타데이터 (__version__, __all__)
- WinProbability 생성/__post_init__/프로퍼티
- ExpectedPossessionValue 생성/프로퍼티
- ShotQualityPrediction 생성
- LineupProjection 생성
- PredictionSnapshot 생성/필드
- 타입 검증 (모던 typing)

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path
from uuid import UUID, uuid4

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))


class TestResult:
    """유닛 테스트 결과"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def eq(self, name: str, actual, expected) -> None:
        if actual == expected:
            self.ok(name)
        else:
            self.fail(name, f"expected {expected!r}, got {actual!r}")

    def true(self, name: str, value: bool) -> None:
        if value:
            self.ok(name)
        else:
            self.fail(name, "expected True")

    def false(self, name: str, value: bool) -> None:
        if not value:
            self.ok(name)
        else:
            self.fail(name, "expected False")

    def none(self, name: str, value) -> None:
        if value is None:
            self.ok(name)
        else:
            self.fail(name, f"expected None, got {value!r}")

    def not_none(self, name: str, value) -> None:
        if value is not None:
            self.ok(name)
        else:
            self.fail(name, "expected not None")

    def approx(self, name: str, actual: float, expected: float, tol: float = 0.01) -> None:
        if abs(actual - expected) < tol:
            self.ok(name)
        else:
            self.fail(name, f"expected ~{expected}, got {actual}")

    def isinstance_check(self, name: str, obj, cls) -> None:
        if isinstance(obj, cls):
            self.ok(name)
        else:
            self.fail(name, f"expected {cls.__name__}, got {type(obj).__name__}")

    def summary(self) -> None:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"유닛 테스트 결과: {self.passed}/{total} 통과")
        if self.failed > 0:
            print(f"\n실패한 테스트:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")


# ==================== 1. 모듈 메타데이터 ====================
def test_module_metadata(r: TestResult) -> None:
    """모듈 메타데이터 검증"""
    import shared.dto.prediction_dto as m

    r.eq("__version__", m.__version__, "1.0.0")
    r.eq("__all__ 길이", len(m.__all__), 5)

    expected_exports = [
        "WinProbability",
        "ExpectedPossessionValue",
        "ShotQualityPrediction",
        "LineupProjection",
        "PredictionSnapshot",
    ]
    for name in expected_exports:
        r.true(f"__all__에 {name} 포함", name in m.__all__)
        r.true(f"{name} 접근 가능", hasattr(m, name))


# ==================== 2. WinProbability ====================
def test_win_probability_defaults(r: TestResult) -> None:
    """WinProbability 기본값"""
    from shared.dto.prediction_dto import WinProbability

    wp = WinProbability()
    r.true("is_dataclass", is_dataclass(wp))
    r.approx("기본 home_wp", wp.home_wp, 50.0)
    r.approx("기본 away_wp (100-50)", wp.away_wp, 50.0)
    r.eq("기본 wp_curve 빈 리스트", wp.wp_curve, [])
    r.approx("기본 last_play_wpa", wp.last_play_wpa, 0.0)
    r.true("기본 is_clutch_time (50% → True)", wp.is_clutch_time)
    r.approx("기본 leverage_index", wp.leverage_index, 1.0)
    r.eq("기본 frame_number", wp.frame_number, 0)
    r.eq("기본 game_clock", wp.game_clock, "")


def test_win_probability_post_init(r: TestResult) -> None:
    """WinProbability __post_init__ 자동 계산"""
    from shared.dto.prediction_dto import WinProbability

    # home_wp=75 → away_wp=25, is_clutch_time=False
    wp75 = WinProbability(home_wp=75.0)
    r.approx("away_wp = 100 - 75", wp75.away_wp, 25.0)
    r.false("is_clutch_time (75%)", wp75.is_clutch_time)

    # home_wp=45 → away_wp=55, is_clutch_time=True
    wp45 = WinProbability(home_wp=45.0)
    r.approx("away_wp = 100 - 45", wp45.away_wp, 55.0)
    r.true("is_clutch_time (45%)", wp45.is_clutch_time)

    # home_wp=40 → 경계값 포함
    wp40 = WinProbability(home_wp=40.0)
    r.true("is_clutch_time (40% 경계)", wp40.is_clutch_time)

    # home_wp=60 → 경계값 포함
    wp60 = WinProbability(home_wp=60.0)
    r.true("is_clutch_time (60% 경계)", wp60.is_clutch_time)

    # home_wp=39 → 경계 밖
    wp39 = WinProbability(home_wp=39.0)
    r.false("is_clutch_time (39%)", wp39.is_clutch_time)

    # home_wp=61 → 경계 밖
    wp61 = WinProbability(home_wp=61.0)
    r.false("is_clutch_time (61%)", wp61.is_clutch_time)


def test_win_probability_full(r: TestResult) -> None:
    """WinProbability 전체 필드 설정"""
    from shared.dto.prediction_dto import WinProbability

    wp = WinProbability(
        home_wp=65.0,
        wp_curve=[(0.0, 50.0), (120.0, 55.0), (300.0, 65.0)],
        last_play_wpa=3.5,
        leverage_index=1.8,
        frame_number=9000,
        game_clock="Q3 05:30",
    )
    r.approx("home_wp=65", wp.home_wp, 65.0)
    r.approx("away_wp=35", wp.away_wp, 35.0)
    r.eq("wp_curve 길이", len(wp.wp_curve), 3)
    r.approx("last_play_wpa", wp.last_play_wpa, 3.5)
    r.approx("leverage_index", wp.leverage_index, 1.8)
    r.eq("frame_number", wp.frame_number, 9000)
    r.eq("game_clock", wp.game_clock, "Q3 05:30")
    r.false("is_clutch_time (65%)", wp.is_clutch_time)


# ==================== 3. ExpectedPossessionValue ====================
def test_epv_defaults(r: TestResult) -> None:
    """ExpectedPossessionValue 기본값"""
    from shared.dto.prediction_dto import ExpectedPossessionValue

    epv = ExpectedPossessionValue()
    r.true("is_dataclass", is_dataclass(epv))
    r.approx("기본 current_epv", epv.current_epv, 0.0)
    r.eq("기본 pass_options", epv.pass_options, [])
    r.approx("기본 shot_option_epv", epv.shot_option_epv, 0.0)
    r.approx("기본 drive_option_epv", epv.drive_option_epv, 0.0)
    r.eq("기본 optimal_action", epv.optimal_action, "")
    r.approx("기본 decision_quality", epv.decision_quality, 0.0)
    r.none("기본 possession_id", epv.possession_id)
    r.eq("기본 frame_number", epv.frame_number, 0)


def test_epv_full(r: TestResult) -> None:
    """ExpectedPossessionValue 전체 필드"""
    from shared.dto.prediction_dto import ExpectedPossessionValue

    pid = uuid4()
    epv = ExpectedPossessionValue(
        current_epv=1.15,
        pass_options=[
            {"target_tracking_id": 3.0, "epv": 1.2, "improvement": 0.05},
            {"target_tracking_id": 7.0, "epv": 0.9, "improvement": -0.25},
        ],
        shot_option_epv=0.85,
        drive_option_epv=1.05,
        optimal_action="pass_to_3",
        decision_quality=0.3,
        possession_id=pid,
        frame_number=5000,
    )
    r.approx("current_epv", epv.current_epv, 1.15)
    r.eq("pass_options 수", len(epv.pass_options), 2)
    r.approx("shot_option_epv", epv.shot_option_epv, 0.85)
    r.approx("drive_option_epv", epv.drive_option_epv, 1.05)
    r.eq("optimal_action", epv.optimal_action, "pass_to_3")
    r.approx("decision_quality", epv.decision_quality, 0.3)
    r.eq("possession_id", epv.possession_id, pid)


def test_epv_best_option_epv(r: TestResult) -> None:
    """ExpectedPossessionValue.best_option_epv 프로퍼티"""
    from shared.dto.prediction_dto import ExpectedPossessionValue

    # 패스 옵션이 가장 높은 경우
    epv1 = ExpectedPossessionValue(
        shot_option_epv=0.8,
        drive_option_epv=1.0,
        pass_options=[
            {"epv": 1.3},
            {"epv": 0.7},
        ],
    )
    r.approx("best = pass 1.3", epv1.best_option_epv, 1.3)

    # 슛 옵션이 가장 높은 경우
    epv2 = ExpectedPossessionValue(
        shot_option_epv=1.5,
        drive_option_epv=0.9,
        pass_options=[{"epv": 1.0}],
    )
    r.approx("best = shot 1.5", epv2.best_option_epv, 1.5)

    # 드라이브가 가장 높은 경우
    epv3 = ExpectedPossessionValue(
        shot_option_epv=0.5,
        drive_option_epv=1.8,
    )
    r.approx("best = drive 1.8", epv3.best_option_epv, 1.8)

    # 빈 상태
    epv_empty = ExpectedPossessionValue()
    r.approx("best empty = 0.0", epv_empty.best_option_epv, 0.0)

    # pass_options에 epv 키 없는 경우
    epv_no_key = ExpectedPossessionValue(
        shot_option_epv=0.5,
        drive_option_epv=0.3,
        pass_options=[{"target": 1.0}],
    )
    r.approx("best (no epv key) = shot 0.5", epv_no_key.best_option_epv, 0.5)


# ==================== 4. ShotQualityPrediction ====================
def test_shot_quality_defaults(r: TestResult) -> None:
    """ShotQualityPrediction 기본값"""
    from shared.dto.prediction_dto import ShotQualityPrediction
    from shared.constants.game_rule_constants import CourtZone

    sq = ShotQualityPrediction()
    r.true("is_dataclass", is_dataclass(sq))
    r.approx("기본 xfg_pct", sq.xfg_pct, 0.0)
    r.eq("기본 shot_location", sq.shot_location, (0.0, 0.0))
    r.eq("기본 court_zone", sq.court_zone, CourtZone.PAINT_LEFT)
    r.approx("기본 defender_distance_m", sq.defender_distance_m, 0.0)
    r.false("기본 hand_contest", sq.hand_contest)
    r.eq("기본 shot_type", sq.shot_type, "")
    r.approx("기본 shooting_skill_index", sq.shooting_skill_index, 0.0)
    r.eq("기본 player_tracking_id", sq.player_tracking_id, 0)
    r.none("기본 shot_id", sq.shot_id)


def test_shot_quality_full(r: TestResult) -> None:
    """ShotQualityPrediction 전체 필드"""
    from shared.dto.prediction_dto import ShotQualityPrediction
    from shared.constants.game_rule_constants import CourtZone

    sid = uuid4()
    sq = ShotQualityPrediction(
        xfg_pct=45.0,
        shot_location=(12.5, 8.3),
        court_zone=CourtZone.MID_LEFT_WING,
        defender_distance_m=1.8,
        hand_contest=True,
        shot_type="mid_range_jumper",
        shooting_skill_index=5.2,
        player_tracking_id=23,
        shot_id=sid,
    )
    r.approx("xfg_pct", sq.xfg_pct, 45.0)
    r.eq("shot_location", sq.shot_location, (12.5, 8.3))
    r.eq("court_zone", sq.court_zone, CourtZone.MID_LEFT_WING)
    r.approx("defender_distance_m", sq.defender_distance_m, 1.8)
    r.true("hand_contest", sq.hand_contest)
    r.eq("shot_type", sq.shot_type, "mid_range_jumper")
    r.approx("shooting_skill_index", sq.shooting_skill_index, 5.2)
    r.eq("player_tracking_id", sq.player_tracking_id, 23)
    r.eq("shot_id", sq.shot_id, sid)


# ==================== 5. LineupProjection ====================
def test_lineup_projection_defaults(r: TestResult) -> None:
    """LineupProjection 기본값"""
    from shared.dto.prediction_dto import LineupProjection

    lp = LineupProjection()
    r.true("is_dataclass", is_dataclass(lp))
    r.eq("기본 lineup_players", lp.lineup_players, [])
    r.approx("기본 predicted_net_rating", lp.predicted_net_rating, 0.0)
    r.approx("기본 predicted_offensive_rating", lp.predicted_offensive_rating, 0.0)
    r.approx("기본 predicted_defensive_rating", lp.predicted_defensive_rating, 0.0)
    r.approx("기본 sample_minutes", lp.sample_minutes, 0.0)
    r.approx("기본 matchup_quality", lp.matchup_quality, 0.0)
    r.false("기본 fatigue_adjusted", lp.fatigue_adjusted)


def test_lineup_projection_full(r: TestResult) -> None:
    """LineupProjection 전체 필드"""
    from shared.dto.prediction_dto import LineupProjection

    lp = LineupProjection(
        lineup_players=[1, 3, 5, 7, 11],
        predicted_net_rating=8.5,
        predicted_offensive_rating=112.0,
        predicted_defensive_rating=103.5,
        sample_minutes=48.5,
        matchup_quality=0.7,
        fatigue_adjusted=True,
    )
    r.eq("lineup_players 수", len(lp.lineup_players), 5)
    r.eq("lineup_players[0]", lp.lineup_players[0], 1)
    r.approx("predicted_net_rating", lp.predicted_net_rating, 8.5)
    r.approx("predicted_offensive_rating", lp.predicted_offensive_rating, 112.0)
    r.approx("predicted_defensive_rating", lp.predicted_defensive_rating, 103.5)
    r.approx("sample_minutes", lp.sample_minutes, 48.5)
    r.approx("matchup_quality", lp.matchup_quality, 0.7)
    r.true("fatigue_adjusted", lp.fatigue_adjusted)


# ==================== 6. PredictionSnapshot ====================
def test_prediction_snapshot_defaults(r: TestResult) -> None:
    """PredictionSnapshot 기본값"""
    from shared.dto.prediction_dto import PredictionSnapshot

    ps = PredictionSnapshot()
    r.true("is_dataclass", is_dataclass(ps))
    r.isinstance_check("snapshot_id is UUID", ps.snapshot_id, UUID)
    r.eq("기본 frame_number", ps.frame_number, 0)
    r.approx("기본 timestamp", ps.timestamp, 0.0)
    r.eq("기본 game_clock", ps.game_clock, "")
    r.eq("기본 quarter", ps.quarter, 1)
    r.none("기본 win_probability", ps.win_probability)
    r.none("기본 epv", ps.epv)
    r.none("기본 current_lineup_projection", ps.current_lineup_projection)


def test_prediction_snapshot_full(r: TestResult) -> None:
    """PredictionSnapshot 전체 구성"""
    from shared.dto.prediction_dto import (
        PredictionSnapshot, WinProbability,
        ExpectedPossessionValue, LineupProjection,
    )

    wp = WinProbability(home_wp=55.0)
    epv = ExpectedPossessionValue(current_epv=1.2)
    lp = LineupProjection(lineup_players=[1, 2, 3, 4, 5])

    ps = PredictionSnapshot(
        frame_number=9000,
        timestamp=300.0,
        game_clock="Q3 05:00",
        quarter=3,
        win_probability=wp,
        epv=epv,
        current_lineup_projection=lp,
    )
    r.eq("frame_number", ps.frame_number, 9000)
    r.approx("timestamp", ps.timestamp, 300.0)
    r.eq("game_clock", ps.game_clock, "Q3 05:00")
    r.eq("quarter", ps.quarter, 3)
    r.not_none("win_probability", ps.win_probability)
    r.approx("wp home_wp", ps.win_probability.home_wp, 55.0)
    r.not_none("epv", ps.epv)
    r.approx("epv current_epv", ps.epv.current_epv, 1.2)
    r.not_none("lineup_projection", ps.current_lineup_projection)
    r.eq("lineup 수", len(ps.current_lineup_projection.lineup_players), 5)


def test_prediction_snapshot_unique_ids(r: TestResult) -> None:
    """PredictionSnapshot UUID 유일성"""
    from shared.dto.prediction_dto import PredictionSnapshot

    ps1 = PredictionSnapshot()
    ps2 = PredictionSnapshot()
    r.true("snapshot_id 유일", ps1.snapshot_id != ps2.snapshot_id)


# ==================== 7. 타입 검증 ====================
def test_modern_typing(r: TestResult) -> None:
    """모던 typing 검증"""
    with open(Path(_PROJECT_ROOT) / "shared" / "dto" / "prediction_dto.py", "r", encoding="utf-8") as f:
        content = f.read()

    r.false("Optional[ 미사용", "Optional[" in content)
    r.false("Dict[ 미사용", "Dict[" in content)
    r.false("List[ 미사용", "List[" in content)
    r.false("Tuple[ 미사용", "Tuple[" in content)
    r.false("from typing import 미사용", "from typing import" in content)

    # 모던 패턴 사용
    r.true("list[ 사용", "list[" in content)
    r.true("tuple[ 사용", "tuple[" in content)
    r.true("| None 사용", "| None" in content)

    # __version__ 존재
    r.true("__version__ 존재", "__version__" in content)


# ==================== 8. 엣지 케이스 ====================
def test_wp_extreme_values(r: TestResult) -> None:
    """WinProbability 극단값"""
    from shared.dto.prediction_dto import WinProbability

    # home_wp=0 → away_wp=100
    wp0 = WinProbability(home_wp=0.0)
    r.approx("away_wp (home=0)", wp0.away_wp, 100.0)
    r.false("is_clutch (0%)", wp0.is_clutch_time)

    # home_wp=100 → away_wp=0
    wp100 = WinProbability(home_wp=100.0)
    r.approx("away_wp (home=100)", wp100.away_wp, 0.0)
    r.false("is_clutch (100%)", wp100.is_clutch_time)


def test_epv_with_uuid(r: TestResult) -> None:
    """EPV possession_id UUID 검증"""
    from shared.dto.prediction_dto import ExpectedPossessionValue

    pid = uuid4()
    epv = ExpectedPossessionValue(possession_id=pid)
    r.isinstance_check("possession_id is UUID", epv.possession_id, UUID)
    r.eq("possession_id 값", epv.possession_id, pid)


def test_shot_quality_with_court_zones(r: TestResult) -> None:
    """ShotQualityPrediction 다양한 CourtZone"""
    from shared.dto.prediction_dto import ShotQualityPrediction
    from shared.constants.game_rule_constants import CourtZone

    zones = [CourtZone.PAINT_LEFT, CourtZone.PAINT_CENTER, CourtZone.MID_LEFT_WING]
    for zone in zones:
        sq = ShotQualityPrediction(court_zone=zone, xfg_pct=50.0)
        r.eq(f"court_zone={zone.name}", sq.court_zone, zone)


def test_lineup_list_independence(r: TestResult) -> None:
    """LineupProjection 리스트 독립성 (default_factory)"""
    from shared.dto.prediction_dto import LineupProjection

    lp1 = LineupProjection()
    lp2 = LineupProjection()
    lp1.lineup_players.append(99)
    r.eq("lp2 독립 (빈 리스트)", len(lp2.lineup_players), 0)


def test_wp_curve_data(r: TestResult) -> None:
    """WinProbability wp_curve 데이터"""
    from shared.dto.prediction_dto import WinProbability

    curve = [(0.0, 50.0), (60.0, 52.0), (120.0, 48.0), (180.0, 55.0)]
    wp = WinProbability(home_wp=55.0, wp_curve=curve)
    r.eq("wp_curve 길이", len(wp.wp_curve), 4)
    r.eq("wp_curve[0]", wp.wp_curve[0], (0.0, 50.0))
    r.eq("wp_curve[-1]", wp.wp_curve[-1], (180.0, 55.0))

    # wp_curve 독립성
    wp1 = WinProbability()
    wp2 = WinProbability()
    wp1.wp_curve.append((0.0, 50.0))
    r.eq("wp_curve 독립", len(wp2.wp_curve), 0)


def test_dataclass_field_count(r: TestResult) -> None:
    """각 dataclass 필드 수 검증"""
    from shared.dto.prediction_dto import (
        WinProbability, ExpectedPossessionValue,
        ShotQualityPrediction, LineupProjection,
        PredictionSnapshot,
    )

    r.eq("WinProbability 필드 수", len(fields(WinProbability)), 8)
    r.eq("ExpectedPossessionValue 필드 수", len(fields(ExpectedPossessionValue)), 8)
    r.eq("ShotQualityPrediction 필드 수", len(fields(ShotQualityPrediction)), 9)
    r.eq("LineupProjection 필드 수", len(fields(LineupProjection)), 7)
    r.eq("PredictionSnapshot 필드 수", len(fields(PredictionSnapshot)), 8)


# ==================== main ====================
def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    r = TestResult()
    print("\n" + "=" * 60)
    print("prediction_dto.py v1.0.0 유닛 테스트")
    print("=" * 60)

    print("\n--- 모듈 메타데이터 ---")
    test_module_metadata(r)

    print("\n--- WinProbability ---")
    test_win_probability_defaults(r)
    test_win_probability_post_init(r)
    test_win_probability_full(r)

    print("\n--- ExpectedPossessionValue ---")
    test_epv_defaults(r)
    test_epv_full(r)
    test_epv_best_option_epv(r)

    print("\n--- ShotQualityPrediction ---")
    test_shot_quality_defaults(r)
    test_shot_quality_full(r)

    print("\n--- LineupProjection ---")
    test_lineup_projection_defaults(r)
    test_lineup_projection_full(r)

    print("\n--- PredictionSnapshot ---")
    test_prediction_snapshot_defaults(r)
    test_prediction_snapshot_full(r)
    test_prediction_snapshot_unique_ids(r)

    print("\n--- 타입 검증 ---")
    test_modern_typing(r)

    print("\n--- 엣지 케이스 ---")
    test_wp_extreme_values(r)
    test_epv_with_uuid(r)
    test_shot_quality_with_court_zones(r)
    test_lineup_list_independence(r)
    test_wp_curve_data(r)
    test_dataclass_field_count(r)

    r.summary()
    return r.failed


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed > 0 else 0)
