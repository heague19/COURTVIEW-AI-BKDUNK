# -*- coding: utf-8 -*-
"""tracking_constants.py v1.1.0 단위 테스트"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.current_section = ""

    def set_section(self, name):
        self.current_section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name, msg=""):
        self.failed += 1
        self.errors.append(f"[{self.current_section}] {name}: {msg}")
        print(f"  [FAIL] {name} - {msg}")

    def check(self, name, condition, msg=""):
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        if self.errors:
            print(f"\n  Errors:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*60}")
        return self.failed == 0


result = TestResult()

# =============================================================================
# 임포트
# =============================================================================
from shared.constants.tracking_constants import (
    # 열거형
    TrackState, TrackingTarget, TrackingAlgorithm,
    # 트랙 생명주기
    MAX_TRACK_AGE, MAX_TRACK_AGE_PLAYER, MAX_TRACK_AGE_BALL,
    MIN_TRACK_HITS, MIN_TRACK_HITS_PLAYER, MIN_TRACK_HITS_BALL,
    TENTATIVE_TRACK_MAX_AGE, TRACK_DELETION_GRACE_PERIOD,
    # IoU 임계값
    IOU_THRESHOLD, IOU_THRESHOLD_HIGH_CONFIDENCE, IOU_THRESHOLD_LOW_CONFIDENCE,
    NMS_IOU_THRESHOLD, NMS_IOU_THRESHOLD_PLAYER, NMS_IOU_THRESHOLD_BALL,
    # 거리 임계값
    DISTANCE_THRESHOLD, DISTANCE_THRESHOLD_PLAYER, DISTANCE_THRESHOLD_BALL,
    MAHALANOBIS_THRESHOLD, MAX_EUCLIDEAN_DISTANCE,
    # 속도 및 움직임
    VELOCITY_SMOOTHING, VELOCITY_SMOOTHING_PLAYER, VELOCITY_SMOOTHING_BALL,
    MAX_VELOCITY_PX_PER_FRAME, MAX_VELOCITY_PLAYER_PX_PER_FRAME,
    MAX_VELOCITY_BALL_PX_PER_FRAME, STATIONARY_VELOCITY_THRESHOLD,
    SUDDEN_DIRECTION_CHANGE_ANGLE_DEG,
    # 칼만 필터
    KALMAN_STATE_DIM, KALMAN_MEASUREMENT_DIM,
    KALMAN_STD_WEIGHT_POSITION, KALMAN_STD_WEIGHT_VELOCITY,
    KALMAN_STD_WEIGHT_MEASUREMENT, KALMAN_INITIAL_COVARIANCE_SCALE,
    KALMAN_GAIN_MIN, KALMAN_GAIN_MAX,
    # 트랙 히스토리
    TRACK_HISTORY_MAX_LENGTH, VELOCITY_HISTORY_MAX_LENGTH,
    FEATURE_HISTORY_MAX_LENGTH, TRAJECTORY_DISPLAY_LENGTH,
    # 비용 행렬 및 연관
    ASSOCIATION_COST_THRESHOLD, APPEARANCE_COST_WEIGHT, MOTION_COST_WEIGHT,
    GATING_COST, MAX_COSINE_DISTANCE, MAX_REID_DISTANCE,
    # ByteTrack
    BYTETRACK_HIGH_THRESHOLD, BYTETRACK_LOW_THRESHOLD,
    BYTETRACK_NEW_TRACK_THRESHOLD, BYTETRACK_SECOND_ASSOCIATION_ENABLED,
    # ID 관리
    MAX_TRACK_ID, ID_REUSE_WAIT_FRAMES,
    MAX_ACTIVE_TRACKS, MAX_ACTIVE_PLAYER_TRACKS,
)
import shared.constants.tracking_constants as tc

# =============================================================================
# 1. TrackState 멤버 수, 값, 유일성, isinstance
# =============================================================================
result.set_section("1. TrackState 멤버 수, 값, 유일성, isinstance")
result.check("TrackState 멤버 수 = 6", len(TrackState) == 6, f"실제: {len(TrackState)}")

_expected_track_states = [
    ("TENTATIVE", "tentative"),
    ("CONFIRMED", "confirmed"),
    ("TRACKED", "tracked"),
    ("LOST", "lost"),
    ("OCCLUDED", "occluded"),
    ("DELETED", "deleted"),
]
for name, value in _expected_track_states:
    s = TrackState[name]
    result.check(f"TrackState.{name} = '{value}'", s.value == value, f"실제: {s.value}")

# 값 유일성
_ts_vals = [s.value for s in TrackState]
result.check("TrackState 값 유일성", len(_ts_vals) == len(set(_ts_vals)))

# isinstance 검증
from enum import Enum
for s in TrackState:
    result.check(f"TrackState.{s.name} isinstance Enum", isinstance(s, Enum))
    result.check(f"TrackState.{s.name} isinstance TrackState", isinstance(s, TrackState))

# =============================================================================
# 2. TrackState.is_active (6 멤버 정확)
# =============================================================================
result.set_section("2. TrackState.is_active")

_expected_is_active = {
    "TENTATIVE": False,
    "CONFIRMED": True,
    "TRACKED": True,
    "LOST": False,
    "OCCLUDED": False,
    "DELETED": False,
}
for name, expected in _expected_is_active.items():
    s = TrackState[name]
    result.check(
        f"TrackState.{name}.is_active = {expected}",
        s.is_active is expected,
        f"실제: {s.is_active}",
    )

# is_active는 bool 타입
for s in TrackState:
    result.check(f"TrackState.{s.name}.is_active bool 타입", isinstance(s.is_active, bool))

# 활성 상태 2개만
_active_count = sum(1 for s in TrackState if s.is_active)
result.check("is_active True 개수 = 2", _active_count == 2, f"실제: {_active_count}")

# =============================================================================
# 3. TrackState.is_visible (6 멤버 정확)
# =============================================================================
result.set_section("3. TrackState.is_visible")

_expected_is_visible = {
    "TENTATIVE": True,
    "CONFIRMED": True,
    "TRACKED": True,
    "LOST": False,
    "OCCLUDED": False,
    "DELETED": False,
}
for name, expected in _expected_is_visible.items():
    s = TrackState[name]
    result.check(
        f"TrackState.{name}.is_visible = {expected}",
        s.is_visible is expected,
        f"실제: {s.is_visible}",
    )

# is_visible는 bool 타입
for s in TrackState:
    result.check(f"TrackState.{s.name}.is_visible bool 타입", isinstance(s.is_visible, bool))

# 가시 상태 3개
_visible_count = sum(1 for s in TrackState if s.is_visible)
result.check("is_visible True 개수 = 3", _visible_count == 3, f"실제: {_visible_count}")

# =============================================================================
# 4. TrackState.can_associate (6 멤버 정확)
# =============================================================================
result.set_section("4. TrackState.can_associate")

_expected_can_associate = {
    "TENTATIVE": True,
    "CONFIRMED": True,
    "TRACKED": True,
    "LOST": True,
    "OCCLUDED": True,
    "DELETED": False,
}
for name, expected in _expected_can_associate.items():
    s = TrackState[name]
    result.check(
        f"TrackState.{name}.can_associate = {expected}",
        s.can_associate is expected,
        f"실제: {s.can_associate}",
    )

# can_associate는 bool 타입
for s in TrackState:
    result.check(f"TrackState.{s.name}.can_associate bool 타입", isinstance(s.can_associate, bool))

# 연관 가능 5개 (DELETED 제외)
_assoc_count = sum(1 for s in TrackState if s.can_associate)
result.check("can_associate True 개수 = 5", _assoc_count == 5, f"실제: {_assoc_count}")

# =============================================================================
# 5. TrackState.needs_prediction (6 멤버 정확)
# =============================================================================
result.set_section("5. TrackState.needs_prediction")

_expected_needs_prediction = {
    "TENTATIVE": False,
    "CONFIRMED": False,
    "TRACKED": False,
    "LOST": True,
    "OCCLUDED": True,
    "DELETED": False,
}
for name, expected in _expected_needs_prediction.items():
    s = TrackState[name]
    result.check(
        f"TrackState.{name}.needs_prediction = {expected}",
        s.needs_prediction is expected,
        f"실제: {s.needs_prediction}",
    )

# needs_prediction은 bool 타입
for s in TrackState:
    result.check(f"TrackState.{s.name}.needs_prediction bool 타입", isinstance(s.needs_prediction, bool))

# 예측 필요 2개
_pred_count = sum(1 for s in TrackState if s.needs_prediction)
result.check("needs_prediction True 개수 = 2", _pred_count == 2, f"실제: {_pred_count}")

# =============================================================================
# 6. TrackState.to_korean (6 정확한 한글 이름)
# =============================================================================
result.set_section("6. TrackState.to_korean")

_expected_ts_korean = {
    "TENTATIVE": "잠정",
    "CONFIRMED": "확정",
    "TRACKED": "추적 중",
    "LOST": "손실",
    "OCCLUDED": "가려짐",
    "DELETED": "삭제",
}
for name, korean in _expected_ts_korean.items():
    s = TrackState[name]
    result.check(
        f"TrackState.{name}.to_korean() = '{korean}'",
        s.to_korean() == korean,
        f"실제: '{s.to_korean()}'",
    )

# 모두 str, 비어있지 않음
for s in TrackState:
    result.check(f"TrackState.{s.name}.to_korean() str 타입", isinstance(s.to_korean(), str))
    result.check(f"TrackState.{s.name}.to_korean() 비어있지 않음", len(s.to_korean()) > 0)

# to_korean은 메서드 (호출 가능)
result.check("TrackState.to_korean 호출 가능", callable(TrackState.TENTATIVE.to_korean))

# =============================================================================
# 7. TrackingTarget 멤버 수, 값, 유일성
# =============================================================================
result.set_section("7. TrackingTarget 멤버 수, 값, 유일성")
result.check("TrackingTarget 멤버 수 = 6", len(TrackingTarget) == 6, f"실제: {len(TrackingTarget)}")

_expected_targets = [
    ("PLAYER", "player"),
    ("BALL", "ball"),
    ("REFEREE", "referee"),
    ("COACH", "coach"),
    ("HOOP", "hoop"),
    ("UNKNOWN", "unknown"),
]
for name, value in _expected_targets:
    t = TrackingTarget[name]
    result.check(f"TrackingTarget.{name} = '{value}'", t.value == value, f"실제: {t.value}")

# 값 유일성
_tt_vals = [t.value for t in TrackingTarget]
result.check("TrackingTarget 값 유일성", len(_tt_vals) == len(set(_tt_vals)))

# isinstance 검증
for t in TrackingTarget:
    result.check(f"TrackingTarget.{t.name} isinstance Enum", isinstance(t, Enum))
    result.check(f"TrackingTarget.{t.name} isinstance TrackingTarget", isinstance(t, TrackingTarget))

# =============================================================================
# 8. TrackingTarget.is_person (6 정확)
# =============================================================================
result.set_section("8. TrackingTarget.is_person")

_expected_is_person = {
    "PLAYER": True,
    "BALL": False,
    "REFEREE": True,
    "COACH": True,
    "HOOP": False,
    "UNKNOWN": False,
}
for name, expected in _expected_is_person.items():
    t = TrackingTarget[name]
    result.check(
        f"TrackingTarget.{name}.is_person = {expected}",
        t.is_person is expected,
        f"실제: {t.is_person}",
    )

# is_person은 bool 타입
for t in TrackingTarget:
    result.check(f"TrackingTarget.{t.name}.is_person bool 타입", isinstance(t.is_person, bool))

# 사람 3명 (PLAYER, REFEREE, COACH)
_person_count = sum(1 for t in TrackingTarget if t.is_person)
result.check("is_person True 개수 = 3", _person_count == 3, f"실제: {_person_count}")

# =============================================================================
# 9. TrackingTarget.is_dynamic (6 정확)
# =============================================================================
result.set_section("9. TrackingTarget.is_dynamic")

_expected_is_dynamic = {
    "PLAYER": True,
    "BALL": True,
    "REFEREE": True,
    "COACH": True,
    "HOOP": False,
    "UNKNOWN": True,
}
for name, expected in _expected_is_dynamic.items():
    t = TrackingTarget[name]
    result.check(
        f"TrackingTarget.{name}.is_dynamic = {expected}",
        t.is_dynamic is expected,
        f"실제: {t.is_dynamic}",
    )

# is_dynamic은 bool 타입
for t in TrackingTarget:
    result.check(f"TrackingTarget.{t.name}.is_dynamic bool 타입", isinstance(t.is_dynamic, bool))

# 동적 5개 (HOOP 제외)
_dynamic_count = sum(1 for t in TrackingTarget if t.is_dynamic)
result.check("is_dynamic True 개수 = 5", _dynamic_count == 5, f"실제: {_dynamic_count}")

# 정적 객체는 사람이 아님
for t in TrackingTarget:
    if not t.is_dynamic:
        result.check(f"정적 객체 {t.name}는 사람이 아님", not t.is_person)

# =============================================================================
# 10. TrackingTarget.default_max_age (6 정확한 값)
# =============================================================================
result.set_section("10. TrackingTarget.default_max_age")

_expected_max_age = {
    "PLAYER": 45,
    "BALL": 15,
    "REFEREE": 45,
    "COACH": 45,
    "HOOP": 1000,
    "UNKNOWN": 30,
}
for name, expected in _expected_max_age.items():
    t = TrackingTarget[name]
    result.check(
        f"TrackingTarget.{name}.default_max_age = {expected}",
        t.default_max_age == expected,
        f"실제: {t.default_max_age}",
    )

# int 타입 검증
for t in TrackingTarget:
    result.check(f"TrackingTarget.{t.name}.default_max_age int 타입", isinstance(t.default_max_age, int))
    result.check(f"TrackingTarget.{t.name}.default_max_age > 0", t.default_max_age > 0)

# PLAYER와 상수 일관성
result.check(
    "PLAYER.default_max_age == MAX_TRACK_AGE_PLAYER",
    TrackingTarget.PLAYER.default_max_age == MAX_TRACK_AGE_PLAYER,
)
result.check(
    "BALL.default_max_age == MAX_TRACK_AGE_BALL",
    TrackingTarget.BALL.default_max_age == MAX_TRACK_AGE_BALL,
)
result.check(
    "UNKNOWN.default_max_age == MAX_TRACK_AGE",
    TrackingTarget.UNKNOWN.default_max_age == MAX_TRACK_AGE,
)

# =============================================================================
# 11. TrackingTarget.default_min_hits (6 정확한 값)
# =============================================================================
result.set_section("11. TrackingTarget.default_min_hits")

_expected_min_hits = {
    "PLAYER": 3,
    "BALL": 2,
    "REFEREE": 3,
    "COACH": 3,
    "HOOP": 5,
    "UNKNOWN": 3,
}
for name, expected in _expected_min_hits.items():
    t = TrackingTarget[name]
    result.check(
        f"TrackingTarget.{name}.default_min_hits = {expected}",
        t.default_min_hits == expected,
        f"실제: {t.default_min_hits}",
    )

# int 타입 검증
for t in TrackingTarget:
    result.check(f"TrackingTarget.{t.name}.default_min_hits int 타입", isinstance(t.default_min_hits, int))
    result.check(f"TrackingTarget.{t.name}.default_min_hits > 0", t.default_min_hits > 0)

# 상수 일관성
result.check(
    "PLAYER.default_min_hits == MIN_TRACK_HITS_PLAYER",
    TrackingTarget.PLAYER.default_min_hits == MIN_TRACK_HITS_PLAYER,
)
result.check(
    "BALL.default_min_hits == MIN_TRACK_HITS_BALL",
    TrackingTarget.BALL.default_min_hits == MIN_TRACK_HITS_BALL,
)
result.check(
    "UNKNOWN.default_min_hits == MIN_TRACK_HITS",
    TrackingTarget.UNKNOWN.default_min_hits == MIN_TRACK_HITS,
)

# =============================================================================
# 12. TrackingTarget.to_korean (6 정확한 한글 이름)
# =============================================================================
result.set_section("12. TrackingTarget.to_korean")

_expected_tt_korean = {
    "PLAYER": "선수",
    "BALL": "공",
    "REFEREE": "심판",
    "COACH": "코치",
    "HOOP": "골대",
    "UNKNOWN": "미분류",
}
for name, korean in _expected_tt_korean.items():
    t = TrackingTarget[name]
    result.check(
        f"TrackingTarget.{name}.to_korean() = '{korean}'",
        t.to_korean() == korean,
        f"실제: '{t.to_korean()}'",
    )

# 모두 str, 비어있지 않음
for t in TrackingTarget:
    result.check(f"TrackingTarget.{t.name}.to_korean() str 타입", isinstance(t.to_korean(), str))
    result.check(f"TrackingTarget.{t.name}.to_korean() 비어있지 않음", len(t.to_korean()) > 0)

# to_korean은 메서드 (호출 가능)
result.check("TrackingTarget.to_korean 호출 가능", callable(TrackingTarget.PLAYER.to_korean))

# =============================================================================
# 13. TrackingAlgorithm 멤버 수, 값, 유일성
# =============================================================================
result.set_section("13. TrackingAlgorithm 멤버 수, 값, 유일성")
result.check("TrackingAlgorithm 멤버 수 = 6", len(TrackingAlgorithm) == 6, f"실제: {len(TrackingAlgorithm)}")

_expected_algorithms = [
    ("SORT", "sort"),
    ("DEEPSORT", "deepsort"),
    ("BYTETRACK", "bytetrack"),
    ("OCSORT", "ocsort"),
    ("BOTSORT", "botsort"),
    ("STRONGSORT", "strongsort"),
]
for name, value in _expected_algorithms:
    a = TrackingAlgorithm[name]
    result.check(f"TrackingAlgorithm.{name} = '{value}'", a.value == value, f"실제: {a.value}")

# 값 유일성
_ta_vals = [a.value for a in TrackingAlgorithm]
result.check("TrackingAlgorithm 값 유일성", len(_ta_vals) == len(set(_ta_vals)))

# isinstance 검증
for a in TrackingAlgorithm:
    result.check(f"TrackingAlgorithm.{a.name} isinstance Enum", isinstance(a, Enum))
    result.check(f"TrackingAlgorithm.{a.name} isinstance TrackingAlgorithm", isinstance(a, TrackingAlgorithm))

# =============================================================================
# 14. TrackingAlgorithm.uses_appearance (6 정확)
# =============================================================================
result.set_section("14. TrackingAlgorithm.uses_appearance")

_expected_uses_appearance = {
    "SORT": False,
    "DEEPSORT": True,
    "BYTETRACK": False,
    "OCSORT": False,
    "BOTSORT": True,
    "STRONGSORT": True,
}
for name, expected in _expected_uses_appearance.items():
    a = TrackingAlgorithm[name]
    result.check(
        f"TrackingAlgorithm.{name}.uses_appearance = {expected}",
        a.uses_appearance is expected,
        f"실제: {a.uses_appearance}",
    )

# bool 타입
for a in TrackingAlgorithm:
    result.check(f"TrackingAlgorithm.{a.name}.uses_appearance bool 타입", isinstance(a.uses_appearance, bool))

# 외관 사용 3개 (DEEPSORT, BOTSORT, STRONGSORT)
_appearance_count = sum(1 for a in TrackingAlgorithm if a.uses_appearance)
result.check("uses_appearance True 개수 = 3", _appearance_count == 3, f"실제: {_appearance_count}")

# =============================================================================
# 15. TrackingAlgorithm.uses_motion_compensation (6 정확)
# =============================================================================
result.set_section("15. TrackingAlgorithm.uses_motion_compensation")

_expected_uses_mc = {
    "SORT": False,
    "DEEPSORT": False,
    "BYTETRACK": False,
    "OCSORT": True,
    "BOTSORT": True,
    "STRONGSORT": False,
}
for name, expected in _expected_uses_mc.items():
    a = TrackingAlgorithm[name]
    result.check(
        f"TrackingAlgorithm.{name}.uses_motion_compensation = {expected}",
        a.uses_motion_compensation is expected,
        f"실제: {a.uses_motion_compensation}",
    )

# bool 타입
for a in TrackingAlgorithm:
    result.check(
        f"TrackingAlgorithm.{a.name}.uses_motion_compensation bool 타입",
        isinstance(a.uses_motion_compensation, bool),
    )

# 모션 보상 사용 2개 (BOTSORT, OCSORT)
_mc_count = sum(1 for a in TrackingAlgorithm if a.uses_motion_compensation)
result.check("uses_motion_compensation True 개수 = 2", _mc_count == 2, f"실제: {_mc_count}")

# =============================================================================
# 16. TrackingAlgorithm.default_iou_threshold (6 정확한 값)
# =============================================================================
result.set_section("16. TrackingAlgorithm.default_iou_threshold")

_expected_iou = {
    "SORT": 0.3,
    "DEEPSORT": 0.3,
    "BYTETRACK": 0.3,
    "OCSORT": 0.3,
    "BOTSORT": 0.2,
    "STRONGSORT": 0.3,
}
for name, expected in _expected_iou.items():
    a = TrackingAlgorithm[name]
    result.check(
        f"TrackingAlgorithm.{name}.default_iou_threshold = {expected}",
        abs(a.default_iou_threshold - expected) < 1e-9,
        f"실제: {a.default_iou_threshold}",
    )

# float 타입
for a in TrackingAlgorithm:
    result.check(
        f"TrackingAlgorithm.{a.name}.default_iou_threshold float 타입",
        isinstance(a.default_iou_threshold, float),
    )

# IoU 범위 0~1 검증
for a in TrackingAlgorithm:
    result.check(
        f"TrackingAlgorithm.{a.name}.default_iou_threshold 0~1 범위",
        0.0 < a.default_iou_threshold < 1.0,
    )

# BOTSORT만 0.2, 나머지 0.3
result.check(
    "BOTSORT만 IoU 0.2 (가장 낮음)",
    TrackingAlgorithm.BOTSORT.default_iou_threshold < TrackingAlgorithm.SORT.default_iou_threshold,
)

# =============================================================================
# 17. TrackingAlgorithm.to_korean (6 정확한 이름)
# =============================================================================
result.set_section("17. TrackingAlgorithm.to_korean")

_expected_ta_korean = {
    "SORT": "SORT",
    "DEEPSORT": "DeepSORT",
    "BYTETRACK": "ByteTrack",
    "OCSORT": "OC-SORT",
    "BOTSORT": "BoT-SORT",
    "STRONGSORT": "StrongSORT",
}
for name, korean in _expected_ta_korean.items():
    a = TrackingAlgorithm[name]
    result.check(
        f"TrackingAlgorithm.{name}.to_korean() = '{korean}'",
        a.to_korean() == korean,
        f"실제: '{a.to_korean()}'",
    )

# 모두 str, 비어있지 않음
for a in TrackingAlgorithm:
    result.check(f"TrackingAlgorithm.{a.name}.to_korean() str 타입", isinstance(a.to_korean(), str))
    result.check(f"TrackingAlgorithm.{a.name}.to_korean() 비어있지 않음", len(a.to_korean()) > 0)

# to_korean은 메서드 (호출 가능)
result.check("TrackingAlgorithm.to_korean 호출 가능", callable(TrackingAlgorithm.SORT.to_korean))

# =============================================================================
# 18. 트랙 생명주기 상수 (정확한 값 + 순서: BALL < DEFAULT < PLAYER)
# =============================================================================
result.set_section("18. 트랙 생명주기 상수")

# 정확한 값 검증
result.check("MAX_TRACK_AGE = 30", MAX_TRACK_AGE == 30, f"실제: {MAX_TRACK_AGE}")
result.check("MAX_TRACK_AGE_PLAYER = 45", MAX_TRACK_AGE_PLAYER == 45, f"실제: {MAX_TRACK_AGE_PLAYER}")
result.check("MAX_TRACK_AGE_BALL = 15", MAX_TRACK_AGE_BALL == 15, f"실제: {MAX_TRACK_AGE_BALL}")
result.check("MIN_TRACK_HITS = 3", MIN_TRACK_HITS == 3, f"실제: {MIN_TRACK_HITS}")
result.check("MIN_TRACK_HITS_PLAYER = 3", MIN_TRACK_HITS_PLAYER == 3, f"실제: {MIN_TRACK_HITS_PLAYER}")
result.check("MIN_TRACK_HITS_BALL = 2", MIN_TRACK_HITS_BALL == 2, f"실제: {MIN_TRACK_HITS_BALL}")
result.check("TENTATIVE_TRACK_MAX_AGE = 5", TENTATIVE_TRACK_MAX_AGE == 5, f"실제: {TENTATIVE_TRACK_MAX_AGE}")
result.check("TRACK_DELETION_GRACE_PERIOD = 3", TRACK_DELETION_GRACE_PERIOD == 3, f"실제: {TRACK_DELETION_GRACE_PERIOD}")

# 타입 검증
result.check("MAX_TRACK_AGE int 타입", isinstance(MAX_TRACK_AGE, int))
result.check("MAX_TRACK_AGE_PLAYER int 타입", isinstance(MAX_TRACK_AGE_PLAYER, int))
result.check("MAX_TRACK_AGE_BALL int 타입", isinstance(MAX_TRACK_AGE_BALL, int))
result.check("MIN_TRACK_HITS int 타입", isinstance(MIN_TRACK_HITS, int))
result.check("TENTATIVE_TRACK_MAX_AGE int 타입", isinstance(TENTATIVE_TRACK_MAX_AGE, int))
result.check("TRACK_DELETION_GRACE_PERIOD int 타입", isinstance(TRACK_DELETION_GRACE_PERIOD, int))

# 순서 검증: BALL < DEFAULT < PLAYER (최대 나이)
result.check(
    "MAX_TRACK_AGE_BALL < MAX_TRACK_AGE",
    MAX_TRACK_AGE_BALL < MAX_TRACK_AGE,
    f"{MAX_TRACK_AGE_BALL} < {MAX_TRACK_AGE}",
)
result.check(
    "MAX_TRACK_AGE < MAX_TRACK_AGE_PLAYER",
    MAX_TRACK_AGE < MAX_TRACK_AGE_PLAYER,
    f"{MAX_TRACK_AGE} < {MAX_TRACK_AGE_PLAYER}",
)

# 순서 검증: BALL < PLAYER (최소 히트)
result.check(
    "MIN_TRACK_HITS_BALL < MIN_TRACK_HITS_PLAYER",
    MIN_TRACK_HITS_BALL < MIN_TRACK_HITS_PLAYER,
    f"{MIN_TRACK_HITS_BALL} < {MIN_TRACK_HITS_PLAYER}",
)

# 양수 검증
for name, val in [
    ("MAX_TRACK_AGE", MAX_TRACK_AGE),
    ("MAX_TRACK_AGE_PLAYER", MAX_TRACK_AGE_PLAYER),
    ("MAX_TRACK_AGE_BALL", MAX_TRACK_AGE_BALL),
    ("MIN_TRACK_HITS", MIN_TRACK_HITS),
    ("TENTATIVE_TRACK_MAX_AGE", TENTATIVE_TRACK_MAX_AGE),
    ("TRACK_DELETION_GRACE_PERIOD", TRACK_DELETION_GRACE_PERIOD),
]:
    result.check(f"{name} > 0", val > 0)

# TENTATIVE < DEFAULT (잠정은 빨리 삭제)
result.check(
    "TENTATIVE_TRACK_MAX_AGE < MAX_TRACK_AGE",
    TENTATIVE_TRACK_MAX_AGE < MAX_TRACK_AGE,
)

# =============================================================================
# 19. IoU 임계값 상수 (정확한 값 + 순서: LOW < DEFAULT < HIGH)
# =============================================================================
result.set_section("19. IoU 임계값 상수")

result.check("IOU_THRESHOLD = 0.3", abs(IOU_THRESHOLD - 0.3) < 1e-9, f"실제: {IOU_THRESHOLD}")
result.check("IOU_THRESHOLD_HIGH_CONFIDENCE = 0.5", abs(IOU_THRESHOLD_HIGH_CONFIDENCE - 0.5) < 1e-9, f"실제: {IOU_THRESHOLD_HIGH_CONFIDENCE}")
result.check("IOU_THRESHOLD_LOW_CONFIDENCE = 0.2", abs(IOU_THRESHOLD_LOW_CONFIDENCE - 0.2) < 1e-9, f"실제: {IOU_THRESHOLD_LOW_CONFIDENCE}")
result.check("NMS_IOU_THRESHOLD = 0.4", abs(NMS_IOU_THRESHOLD - 0.4) < 1e-9, f"실제: {NMS_IOU_THRESHOLD}")
result.check("NMS_IOU_THRESHOLD_PLAYER = 0.5", abs(NMS_IOU_THRESHOLD_PLAYER - 0.5) < 1e-9, f"실제: {NMS_IOU_THRESHOLD_PLAYER}")
result.check("NMS_IOU_THRESHOLD_BALL = 0.3", abs(NMS_IOU_THRESHOLD_BALL - 0.3) < 1e-9, f"실제: {NMS_IOU_THRESHOLD_BALL}")

# 타입 검증
for name, val in [
    ("IOU_THRESHOLD", IOU_THRESHOLD),
    ("IOU_THRESHOLD_HIGH_CONFIDENCE", IOU_THRESHOLD_HIGH_CONFIDENCE),
    ("IOU_THRESHOLD_LOW_CONFIDENCE", IOU_THRESHOLD_LOW_CONFIDENCE),
    ("NMS_IOU_THRESHOLD", NMS_IOU_THRESHOLD),
    ("NMS_IOU_THRESHOLD_PLAYER", NMS_IOU_THRESHOLD_PLAYER),
    ("NMS_IOU_THRESHOLD_BALL", NMS_IOU_THRESHOLD_BALL),
]:
    result.check(f"{name} float 타입", isinstance(val, float))
    result.check(f"{name} 0~1 범위", 0.0 < val < 1.0)

# 순서 검증: LOW < DEFAULT < HIGH
result.check(
    "IOU_THRESHOLD_LOW_CONFIDENCE < IOU_THRESHOLD",
    IOU_THRESHOLD_LOW_CONFIDENCE < IOU_THRESHOLD,
    f"{IOU_THRESHOLD_LOW_CONFIDENCE} < {IOU_THRESHOLD}",
)
result.check(
    "IOU_THRESHOLD < IOU_THRESHOLD_HIGH_CONFIDENCE",
    IOU_THRESHOLD < IOU_THRESHOLD_HIGH_CONFIDENCE,
    f"{IOU_THRESHOLD} < {IOU_THRESHOLD_HIGH_CONFIDENCE}",
)

# NMS 순서: BALL < DEFAULT < PLAYER
result.check(
    "NMS_IOU_THRESHOLD_BALL < NMS_IOU_THRESHOLD",
    NMS_IOU_THRESHOLD_BALL < NMS_IOU_THRESHOLD,
)
result.check(
    "NMS_IOU_THRESHOLD < NMS_IOU_THRESHOLD_PLAYER",
    NMS_IOU_THRESHOLD < NMS_IOU_THRESHOLD_PLAYER,
)

# =============================================================================
# 20. 거리 임계값 상수 (정확한 값)
# =============================================================================
result.set_section("20. 거리 임계값 상수")

result.check("DISTANCE_THRESHOLD = 100.0", abs(DISTANCE_THRESHOLD - 100.0) < 1e-9, f"실제: {DISTANCE_THRESHOLD}")
result.check("DISTANCE_THRESHOLD_PLAYER = 150.0", abs(DISTANCE_THRESHOLD_PLAYER - 150.0) < 1e-9, f"실제: {DISTANCE_THRESHOLD_PLAYER}")
result.check("DISTANCE_THRESHOLD_BALL = 200.0", abs(DISTANCE_THRESHOLD_BALL - 200.0) < 1e-9, f"실제: {DISTANCE_THRESHOLD_BALL}")
result.check("MAHALANOBIS_THRESHOLD = 9.4877", abs(MAHALANOBIS_THRESHOLD - 9.4877) < 1e-4, f"실제: {MAHALANOBIS_THRESHOLD}")
result.check("MAX_EUCLIDEAN_DISTANCE = 1.0", abs(MAX_EUCLIDEAN_DISTANCE - 1.0) < 1e-9, f"실제: {MAX_EUCLIDEAN_DISTANCE}")

# 타입 검증
for name, val in [
    ("DISTANCE_THRESHOLD", DISTANCE_THRESHOLD),
    ("DISTANCE_THRESHOLD_PLAYER", DISTANCE_THRESHOLD_PLAYER),
    ("DISTANCE_THRESHOLD_BALL", DISTANCE_THRESHOLD_BALL),
    ("MAHALANOBIS_THRESHOLD", MAHALANOBIS_THRESHOLD),
    ("MAX_EUCLIDEAN_DISTANCE", MAX_EUCLIDEAN_DISTANCE),
]:
    result.check(f"{name} float 타입", isinstance(val, float))
    result.check(f"{name} > 0", val > 0)

# 순서: DEFAULT < PLAYER < BALL (공은 빠르므로 넓은 임계값)
result.check(
    "DISTANCE_THRESHOLD < DISTANCE_THRESHOLD_PLAYER",
    DISTANCE_THRESHOLD < DISTANCE_THRESHOLD_PLAYER,
)
result.check(
    "DISTANCE_THRESHOLD_PLAYER < DISTANCE_THRESHOLD_BALL",
    DISTANCE_THRESHOLD_PLAYER < DISTANCE_THRESHOLD_BALL,
)

# 마할라노비스 임계값은 chi2inv95(4)에 근사
result.check("MAHALANOBIS_THRESHOLD ≈ chi2inv95(4)", abs(MAHALANOBIS_THRESHOLD - 9.4877) < 0.01)

# =============================================================================
# 21. 속도 상수 (정확한 값 + 순서: BALL_SMOOTHING < DEFAULT < PLAYER)
# =============================================================================
result.set_section("21. 속도 상수")

result.check("VELOCITY_SMOOTHING = 0.3", abs(VELOCITY_SMOOTHING - 0.3) < 1e-9, f"실제: {VELOCITY_SMOOTHING}")
result.check("VELOCITY_SMOOTHING_PLAYER = 0.4", abs(VELOCITY_SMOOTHING_PLAYER - 0.4) < 1e-9, f"실제: {VELOCITY_SMOOTHING_PLAYER}")
result.check("VELOCITY_SMOOTHING_BALL = 0.2", abs(VELOCITY_SMOOTHING_BALL - 0.2) < 1e-9, f"실제: {VELOCITY_SMOOTHING_BALL}")
result.check("MAX_VELOCITY_PX_PER_FRAME = 100.0", abs(MAX_VELOCITY_PX_PER_FRAME - 100.0) < 1e-9, f"실제: {MAX_VELOCITY_PX_PER_FRAME}")
result.check("MAX_VELOCITY_PLAYER_PX_PER_FRAME = 50.0", abs(MAX_VELOCITY_PLAYER_PX_PER_FRAME - 50.0) < 1e-9, f"실제: {MAX_VELOCITY_PLAYER_PX_PER_FRAME}")
result.check("MAX_VELOCITY_BALL_PX_PER_FRAME = 150.0", abs(MAX_VELOCITY_BALL_PX_PER_FRAME - 150.0) < 1e-9, f"실제: {MAX_VELOCITY_BALL_PX_PER_FRAME}")
result.check("STATIONARY_VELOCITY_THRESHOLD = 2.0", abs(STATIONARY_VELOCITY_THRESHOLD - 2.0) < 1e-9, f"실제: {STATIONARY_VELOCITY_THRESHOLD}")
result.check("SUDDEN_DIRECTION_CHANGE_ANGLE_DEG = 90.0", abs(SUDDEN_DIRECTION_CHANGE_ANGLE_DEG - 90.0) < 1e-9, f"실제: {SUDDEN_DIRECTION_CHANGE_ANGLE_DEG}")

# 타입 검증
for name, val in [
    ("VELOCITY_SMOOTHING", VELOCITY_SMOOTHING),
    ("VELOCITY_SMOOTHING_PLAYER", VELOCITY_SMOOTHING_PLAYER),
    ("VELOCITY_SMOOTHING_BALL", VELOCITY_SMOOTHING_BALL),
    ("MAX_VELOCITY_PX_PER_FRAME", MAX_VELOCITY_PX_PER_FRAME),
    ("MAX_VELOCITY_PLAYER_PX_PER_FRAME", MAX_VELOCITY_PLAYER_PX_PER_FRAME),
    ("MAX_VELOCITY_BALL_PX_PER_FRAME", MAX_VELOCITY_BALL_PX_PER_FRAME),
    ("STATIONARY_VELOCITY_THRESHOLD", STATIONARY_VELOCITY_THRESHOLD),
    ("SUDDEN_DIRECTION_CHANGE_ANGLE_DEG", SUDDEN_DIRECTION_CHANGE_ANGLE_DEG),
]:
    result.check(f"{name} float 타입", isinstance(val, float))
    result.check(f"{name} > 0", val > 0)

# 순서 검증: BALL_SMOOTHING < DEFAULT < PLAYER
result.check(
    "VELOCITY_SMOOTHING_BALL < VELOCITY_SMOOTHING",
    VELOCITY_SMOOTHING_BALL < VELOCITY_SMOOTHING,
    f"{VELOCITY_SMOOTHING_BALL} < {VELOCITY_SMOOTHING}",
)
result.check(
    "VELOCITY_SMOOTHING < VELOCITY_SMOOTHING_PLAYER",
    VELOCITY_SMOOTHING < VELOCITY_SMOOTHING_PLAYER,
    f"{VELOCITY_SMOOTHING} < {VELOCITY_SMOOTHING_PLAYER}",
)

# 스무딩 계수 범위 0~1
for name, val in [
    ("VELOCITY_SMOOTHING", VELOCITY_SMOOTHING),
    ("VELOCITY_SMOOTHING_PLAYER", VELOCITY_SMOOTHING_PLAYER),
    ("VELOCITY_SMOOTHING_BALL", VELOCITY_SMOOTHING_BALL),
]:
    result.check(f"{name} 0~1 범위", 0.0 < val < 1.0)

# 속도 순서: PLAYER < DEFAULT < BALL (공이 가장 빠름)
result.check(
    "MAX_VELOCITY_PLAYER < MAX_VELOCITY (일반)",
    MAX_VELOCITY_PLAYER_PX_PER_FRAME < MAX_VELOCITY_PX_PER_FRAME,
)
result.check(
    "MAX_VELOCITY (일반) < MAX_VELOCITY_BALL",
    MAX_VELOCITY_PX_PER_FRAME < MAX_VELOCITY_BALL_PX_PER_FRAME,
)

# 정지 임계값은 모든 최대 속도보다 작음
result.check(
    "STATIONARY_VELOCITY < MAX_VELOCITY_PLAYER",
    STATIONARY_VELOCITY_THRESHOLD < MAX_VELOCITY_PLAYER_PX_PER_FRAME,
)

# 방향 전환 각도 범위
result.check("방향 전환 각도 0~360 범위", 0.0 < SUDDEN_DIRECTION_CHANGE_ANGLE_DEG <= 360.0)

# =============================================================================
# 22. 칼만 필터 상수 (정확한 값 + STATE_DIM > MEASUREMENT_DIM, GAIN_MIN < GAIN_MAX)
# =============================================================================
result.set_section("22. 칼만 필터 상수")

result.check("KALMAN_STATE_DIM = 8", KALMAN_STATE_DIM == 8, f"실제: {KALMAN_STATE_DIM}")
result.check("KALMAN_MEASUREMENT_DIM = 4", KALMAN_MEASUREMENT_DIM == 4, f"실제: {KALMAN_MEASUREMENT_DIM}")
result.check("KALMAN_STD_WEIGHT_POSITION = 1/20", abs(KALMAN_STD_WEIGHT_POSITION - 1.0/20.0) < 1e-9, f"실제: {KALMAN_STD_WEIGHT_POSITION}")
result.check("KALMAN_STD_WEIGHT_VELOCITY = 1/160", abs(KALMAN_STD_WEIGHT_VELOCITY - 1.0/160.0) < 1e-9, f"실제: {KALMAN_STD_WEIGHT_VELOCITY}")
result.check("KALMAN_STD_WEIGHT_MEASUREMENT = 1/20", abs(KALMAN_STD_WEIGHT_MEASUREMENT - 1.0/20.0) < 1e-9, f"실제: {KALMAN_STD_WEIGHT_MEASUREMENT}")
result.check("KALMAN_INITIAL_COVARIANCE_SCALE = 10.0", abs(KALMAN_INITIAL_COVARIANCE_SCALE - 10.0) < 1e-9, f"실제: {KALMAN_INITIAL_COVARIANCE_SCALE}")
result.check("KALMAN_GAIN_MIN = 0.01", abs(KALMAN_GAIN_MIN - 0.01) < 1e-9, f"실제: {KALMAN_GAIN_MIN}")
result.check("KALMAN_GAIN_MAX = 0.99", abs(KALMAN_GAIN_MAX - 0.99) < 1e-9, f"실제: {KALMAN_GAIN_MAX}")

# 타입 검증
result.check("KALMAN_STATE_DIM int 타입", isinstance(KALMAN_STATE_DIM, int))
result.check("KALMAN_MEASUREMENT_DIM int 타입", isinstance(KALMAN_MEASUREMENT_DIM, int))
for name, val in [
    ("KALMAN_STD_WEIGHT_POSITION", KALMAN_STD_WEIGHT_POSITION),
    ("KALMAN_STD_WEIGHT_VELOCITY", KALMAN_STD_WEIGHT_VELOCITY),
    ("KALMAN_STD_WEIGHT_MEASUREMENT", KALMAN_STD_WEIGHT_MEASUREMENT),
    ("KALMAN_INITIAL_COVARIANCE_SCALE", KALMAN_INITIAL_COVARIANCE_SCALE),
    ("KALMAN_GAIN_MIN", KALMAN_GAIN_MIN),
    ("KALMAN_GAIN_MAX", KALMAN_GAIN_MAX),
]:
    result.check(f"{name} float 타입", isinstance(val, float))
    result.check(f"{name} > 0", val > 0)

# 관계 검증
result.check(
    "STATE_DIM > MEASUREMENT_DIM",
    KALMAN_STATE_DIM > KALMAN_MEASUREMENT_DIM,
    f"{KALMAN_STATE_DIM} > {KALMAN_MEASUREMENT_DIM}",
)
result.check(
    "STATE_DIM = 2 * MEASUREMENT_DIM (위치+속도)",
    KALMAN_STATE_DIM == 2 * KALMAN_MEASUREMENT_DIM,
)
result.check(
    "GAIN_MIN < GAIN_MAX",
    KALMAN_GAIN_MIN < KALMAN_GAIN_MAX,
    f"{KALMAN_GAIN_MIN} < {KALMAN_GAIN_MAX}",
)
result.check(
    "GAIN_MIN > 0 (수치 안정성)",
    KALMAN_GAIN_MIN > 0,
)
result.check(
    "GAIN_MAX < 1.0",
    KALMAN_GAIN_MAX < 1.0,
)

# 노이즈 관계: 속도 < 위치 (속도는 더 적은 노이즈)
result.check(
    "STD_WEIGHT_VELOCITY < STD_WEIGHT_POSITION",
    KALMAN_STD_WEIGHT_VELOCITY < KALMAN_STD_WEIGHT_POSITION,
)

# 위치/측정 일관성 (동일 스케일)
result.check(
    "STD_WEIGHT_POSITION == STD_WEIGHT_MEASUREMENT",
    abs(KALMAN_STD_WEIGHT_POSITION - KALMAN_STD_WEIGHT_MEASUREMENT) < 1e-9,
)

# =============================================================================
# 23. 트랙 히스토리 상수 (정확한 값)
# =============================================================================
result.set_section("23. 트랙 히스토리 상수")

result.check("TRACK_HISTORY_MAX_LENGTH = 100", TRACK_HISTORY_MAX_LENGTH == 100, f"실제: {TRACK_HISTORY_MAX_LENGTH}")
result.check("VELOCITY_HISTORY_MAX_LENGTH = 30", VELOCITY_HISTORY_MAX_LENGTH == 30, f"실제: {VELOCITY_HISTORY_MAX_LENGTH}")
result.check("FEATURE_HISTORY_MAX_LENGTH = 50", FEATURE_HISTORY_MAX_LENGTH == 50, f"실제: {FEATURE_HISTORY_MAX_LENGTH}")
result.check("TRAJECTORY_DISPLAY_LENGTH = 30", TRAJECTORY_DISPLAY_LENGTH == 30, f"실제: {TRAJECTORY_DISPLAY_LENGTH}")

# 타입 검증
for name, val in [
    ("TRACK_HISTORY_MAX_LENGTH", TRACK_HISTORY_MAX_LENGTH),
    ("VELOCITY_HISTORY_MAX_LENGTH", VELOCITY_HISTORY_MAX_LENGTH),
    ("FEATURE_HISTORY_MAX_LENGTH", FEATURE_HISTORY_MAX_LENGTH),
    ("TRAJECTORY_DISPLAY_LENGTH", TRAJECTORY_DISPLAY_LENGTH),
]:
    result.check(f"{name} int 타입", isinstance(val, int))
    result.check(f"{name} > 0", val > 0)

# 순서: VELOCITY < FEATURE < TRACK (위치 히스토리가 가장 김)
result.check(
    "VELOCITY_HISTORY < FEATURE_HISTORY",
    VELOCITY_HISTORY_MAX_LENGTH < FEATURE_HISTORY_MAX_LENGTH,
)
result.check(
    "FEATURE_HISTORY < TRACK_HISTORY",
    FEATURE_HISTORY_MAX_LENGTH < TRACK_HISTORY_MAX_LENGTH,
)

# TRAJECTORY_DISPLAY <= TRACK_HISTORY (시각화는 히스토리보다 짧거나 같음)
result.check(
    "TRAJECTORY_DISPLAY <= TRACK_HISTORY",
    TRAJECTORY_DISPLAY_LENGTH <= TRACK_HISTORY_MAX_LENGTH,
)

# TRAJECTORY_DISPLAY == VELOCITY_HISTORY (같은 용도)
result.check(
    "TRAJECTORY_DISPLAY == VELOCITY_HISTORY",
    TRAJECTORY_DISPLAY_LENGTH == VELOCITY_HISTORY_MAX_LENGTH,
)

# =============================================================================
# 24. 연관 비용 상수 (정확한 값 + 가중치 합 = 1.0)
# =============================================================================
result.set_section("24. 연관 비용 상수")

result.check("ASSOCIATION_COST_THRESHOLD = 0.8", abs(ASSOCIATION_COST_THRESHOLD - 0.8) < 1e-9, f"실제: {ASSOCIATION_COST_THRESHOLD}")
result.check("APPEARANCE_COST_WEIGHT = 0.5", abs(APPEARANCE_COST_WEIGHT - 0.5) < 1e-9, f"실제: {APPEARANCE_COST_WEIGHT}")
result.check("MOTION_COST_WEIGHT = 0.5", abs(MOTION_COST_WEIGHT - 0.5) < 1e-9, f"실제: {MOTION_COST_WEIGHT}")
result.check("GATING_COST = 1e5", abs(GATING_COST - 1e5) < 1e-3, f"실제: {GATING_COST}")
result.check("MAX_COSINE_DISTANCE = 0.4", abs(MAX_COSINE_DISTANCE - 0.4) < 1e-9, f"실제: {MAX_COSINE_DISTANCE}")
result.check("MAX_REID_DISTANCE = 0.3", abs(MAX_REID_DISTANCE - 0.3) < 1e-9, f"실제: {MAX_REID_DISTANCE}")

# 타입 검증
for name, val in [
    ("ASSOCIATION_COST_THRESHOLD", ASSOCIATION_COST_THRESHOLD),
    ("APPEARANCE_COST_WEIGHT", APPEARANCE_COST_WEIGHT),
    ("MOTION_COST_WEIGHT", MOTION_COST_WEIGHT),
    ("GATING_COST", GATING_COST),
    ("MAX_COSINE_DISTANCE", MAX_COSINE_DISTANCE),
    ("MAX_REID_DISTANCE", MAX_REID_DISTANCE),
]:
    result.check(f"{name} float 타입", isinstance(val, float))
    result.check(f"{name} > 0", val > 0)

# 핵심: 비용 가중치 합 = 1.0
result.check(
    "APPEARANCE_COST_WEIGHT + MOTION_COST_WEIGHT = 1.0",
    abs(APPEARANCE_COST_WEIGHT + MOTION_COST_WEIGHT - 1.0) < 1e-9,
    f"실제: {APPEARANCE_COST_WEIGHT + MOTION_COST_WEIGHT}",
)

# 가중치 개별 범위 0~1
result.check("APPEARANCE_COST_WEIGHT 0~1 범위", 0.0 < APPEARANCE_COST_WEIGHT <= 1.0)
result.check("MOTION_COST_WEIGHT 0~1 범위", 0.0 < MOTION_COST_WEIGHT <= 1.0)

# GATING_COST >> ASSOCIATION_COST_THRESHOLD (게이트 비용은 매우 큼)
result.check(
    "GATING_COST >> ASSOCIATION_COST_THRESHOLD",
    GATING_COST > ASSOCIATION_COST_THRESHOLD * 100,
)

# 코사인 거리 < 비용 임계값
result.check(
    "MAX_COSINE_DISTANCE < ASSOCIATION_COST_THRESHOLD",
    MAX_COSINE_DISTANCE < ASSOCIATION_COST_THRESHOLD,
)

# Re-ID 거리 < 코사인 거리
result.check(
    "MAX_REID_DISTANCE < MAX_COSINE_DISTANCE",
    MAX_REID_DISTANCE < MAX_COSINE_DISTANCE,
)

# =============================================================================
# 25. ByteTrack 상수 (정확한 값 + LOW < HIGH < NEW_TRACK 순서)
# =============================================================================
result.set_section("25. ByteTrack 상수")

result.check("BYTETRACK_HIGH_THRESHOLD = 0.6", abs(BYTETRACK_HIGH_THRESHOLD - 0.6) < 1e-9, f"실제: {BYTETRACK_HIGH_THRESHOLD}")
result.check("BYTETRACK_LOW_THRESHOLD = 0.1", abs(BYTETRACK_LOW_THRESHOLD - 0.1) < 1e-9, f"실제: {BYTETRACK_LOW_THRESHOLD}")
result.check("BYTETRACK_NEW_TRACK_THRESHOLD = 0.7", abs(BYTETRACK_NEW_TRACK_THRESHOLD - 0.7) < 1e-9, f"실제: {BYTETRACK_NEW_TRACK_THRESHOLD}")
result.check("BYTETRACK_SECOND_ASSOCIATION_ENABLED = True", BYTETRACK_SECOND_ASSOCIATION_ENABLED is True, f"실제: {BYTETRACK_SECOND_ASSOCIATION_ENABLED}")

# 타입 검증
result.check("BYTETRACK_HIGH_THRESHOLD float 타입", isinstance(BYTETRACK_HIGH_THRESHOLD, float))
result.check("BYTETRACK_LOW_THRESHOLD float 타입", isinstance(BYTETRACK_LOW_THRESHOLD, float))
result.check("BYTETRACK_NEW_TRACK_THRESHOLD float 타입", isinstance(BYTETRACK_NEW_TRACK_THRESHOLD, float))
result.check("BYTETRACK_SECOND_ASSOCIATION_ENABLED bool 타입", isinstance(BYTETRACK_SECOND_ASSOCIATION_ENABLED, bool))

# 순서 검증: LOW < HIGH < NEW_TRACK
result.check(
    "BYTETRACK_LOW < BYTETRACK_HIGH",
    BYTETRACK_LOW_THRESHOLD < BYTETRACK_HIGH_THRESHOLD,
    f"{BYTETRACK_LOW_THRESHOLD} < {BYTETRACK_HIGH_THRESHOLD}",
)
result.check(
    "BYTETRACK_HIGH < BYTETRACK_NEW_TRACK",
    BYTETRACK_HIGH_THRESHOLD < BYTETRACK_NEW_TRACK_THRESHOLD,
    f"{BYTETRACK_HIGH_THRESHOLD} < {BYTETRACK_NEW_TRACK_THRESHOLD}",
)

# 모두 0~1 범위 (확률값)
for name, val in [
    ("BYTETRACK_HIGH_THRESHOLD", BYTETRACK_HIGH_THRESHOLD),
    ("BYTETRACK_LOW_THRESHOLD", BYTETRACK_LOW_THRESHOLD),
    ("BYTETRACK_NEW_TRACK_THRESHOLD", BYTETRACK_NEW_TRACK_THRESHOLD),
]:
    result.check(f"{name} 0~1 범위", 0.0 < val < 1.0)

# =============================================================================
# 26. ID 관리 상수 (정확한 값)
# =============================================================================
result.set_section("26. ID 관리 상수")

result.check("MAX_TRACK_ID = 1_000_000", MAX_TRACK_ID == 1_000_000, f"실제: {MAX_TRACK_ID}")
result.check("ID_REUSE_WAIT_FRAMES = 100", ID_REUSE_WAIT_FRAMES == 100, f"실제: {ID_REUSE_WAIT_FRAMES}")
result.check("MAX_ACTIVE_TRACKS = 50", MAX_ACTIVE_TRACKS == 50, f"실제: {MAX_ACTIVE_TRACKS}")
result.check("MAX_ACTIVE_PLAYER_TRACKS = 20", MAX_ACTIVE_PLAYER_TRACKS == 20, f"실제: {MAX_ACTIVE_PLAYER_TRACKS}")

# 타입 검증
for name, val in [
    ("MAX_TRACK_ID", MAX_TRACK_ID),
    ("ID_REUSE_WAIT_FRAMES", ID_REUSE_WAIT_FRAMES),
    ("MAX_ACTIVE_TRACKS", MAX_ACTIVE_TRACKS),
    ("MAX_ACTIVE_PLAYER_TRACKS", MAX_ACTIVE_PLAYER_TRACKS),
]:
    result.check(f"{name} int 타입", isinstance(val, int))
    result.check(f"{name} > 0", val > 0)

# 관계 검증
result.check(
    "MAX_ACTIVE_PLAYER_TRACKS < MAX_ACTIVE_TRACKS",
    MAX_ACTIVE_PLAYER_TRACKS < MAX_ACTIVE_TRACKS,
    f"{MAX_ACTIVE_PLAYER_TRACKS} < {MAX_ACTIVE_TRACKS}",
)

# 실제 농구 경기: 한 팀 5명, 총 10명 + 심판 + 코치 등
result.check(
    "MAX_ACTIVE_PLAYER_TRACKS >= 10 (양팀 최소 10명)",
    MAX_ACTIVE_PLAYER_TRACKS >= 10,
)

# ID 재사용 대기는 최대 나이보다 커야 함 (안전성)
result.check(
    "ID_REUSE_WAIT_FRAMES > MAX_TRACK_AGE_PLAYER",
    ID_REUSE_WAIT_FRAMES > MAX_TRACK_AGE_PLAYER,
)

# MAX_TRACK_ID는 충분히 커야 함 (순환 방지)
result.check(
    "MAX_TRACK_ID >= 1_000_000",
    MAX_TRACK_ID >= 1_000_000,
)

# =============================================================================
# 27. __all__ 완전성 (56 항목, 중복 없음, 모두 존재)
# =============================================================================
result.set_section("27. __all__ 완전성")

_all_list = tc.__all__
result.check("__all__ 56 항목", len(_all_list) == 56, f"실제: {len(_all_list)}")
result.check("__all__ 중복 없음", len(_all_list) == len(set(_all_list)))

# 모든 항목이 모듈에 존재
_missing = [name for name in _all_list if not hasattr(tc, name)]
result.check("__all__ 모든 항목 모듈에 존재", len(_missing) == 0, f"누락: {_missing}")

# 열거형 포함 확인
result.check("'TrackState' in __all__", "TrackState" in _all_list)
result.check("'TrackingTarget' in __all__", "TrackingTarget" in _all_list)
result.check("'TrackingAlgorithm' in __all__", "TrackingAlgorithm" in _all_list)

# 트랙 생명주기 상수 포함
_lifecycle_names = [
    "MAX_TRACK_AGE", "MAX_TRACK_AGE_PLAYER", "MAX_TRACK_AGE_BALL",
    "MIN_TRACK_HITS", "MIN_TRACK_HITS_PLAYER", "MIN_TRACK_HITS_BALL",
    "TENTATIVE_TRACK_MAX_AGE", "TRACK_DELETION_GRACE_PERIOD",
]
for name in _lifecycle_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# IoU 상수 포함
_iou_names = [
    "IOU_THRESHOLD", "IOU_THRESHOLD_HIGH_CONFIDENCE", "IOU_THRESHOLD_LOW_CONFIDENCE",
    "NMS_IOU_THRESHOLD", "NMS_IOU_THRESHOLD_PLAYER", "NMS_IOU_THRESHOLD_BALL",
]
for name in _iou_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 거리 상수 포함
_distance_names = [
    "DISTANCE_THRESHOLD", "DISTANCE_THRESHOLD_PLAYER", "DISTANCE_THRESHOLD_BALL",
    "MAHALANOBIS_THRESHOLD", "MAX_EUCLIDEAN_DISTANCE",
]
for name in _distance_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 속도 상수 포함
_velocity_names = [
    "VELOCITY_SMOOTHING", "VELOCITY_SMOOTHING_PLAYER", "VELOCITY_SMOOTHING_BALL",
    "MAX_VELOCITY_PX_PER_FRAME", "MAX_VELOCITY_PLAYER_PX_PER_FRAME",
    "MAX_VELOCITY_BALL_PX_PER_FRAME", "STATIONARY_VELOCITY_THRESHOLD",
    "SUDDEN_DIRECTION_CHANGE_ANGLE_DEG",
]
for name in _velocity_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 칼만 상수 포함
_kalman_names = [
    "KALMAN_STATE_DIM", "KALMAN_MEASUREMENT_DIM",
    "KALMAN_STD_WEIGHT_POSITION", "KALMAN_STD_WEIGHT_VELOCITY",
    "KALMAN_STD_WEIGHT_MEASUREMENT", "KALMAN_INITIAL_COVARIANCE_SCALE",
    "KALMAN_GAIN_MIN", "KALMAN_GAIN_MAX",
]
for name in _kalman_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 히스토리 상수 포함
_history_names = [
    "TRACK_HISTORY_MAX_LENGTH", "VELOCITY_HISTORY_MAX_LENGTH",
    "FEATURE_HISTORY_MAX_LENGTH", "TRAJECTORY_DISPLAY_LENGTH",
]
for name in _history_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# 연관 비용 상수 포함
_assoc_names = [
    "ASSOCIATION_COST_THRESHOLD", "APPEARANCE_COST_WEIGHT", "MOTION_COST_WEIGHT",
    "GATING_COST", "MAX_COSINE_DISTANCE", "MAX_REID_DISTANCE",
]
for name in _assoc_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# ByteTrack 상수 포함
_bt_names = [
    "BYTETRACK_HIGH_THRESHOLD", "BYTETRACK_LOW_THRESHOLD",
    "BYTETRACK_NEW_TRACK_THRESHOLD", "BYTETRACK_SECOND_ASSOCIATION_ENABLED",
]
for name in _bt_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# ID 관리 상수 포함
_id_names = [
    "MAX_TRACK_ID", "ID_REUSE_WAIT_FRAMES",
    "MAX_ACTIVE_TRACKS", "MAX_ACTIVE_PLAYER_TRACKS",
]
for name in _id_names:
    result.check(f"'{name}' in __all__", name in _all_list)

# =============================================================================
# 28. 캐시 타입 및 완전성 (8 frozenset + 6 dict)
# =============================================================================
result.set_section("28. 캐시 타입 및 완전성")

# 8 frozenset 캐시
_frozenset_caches = [
    ("_TRACK_STATE_IS_ACTIVE", tc._TRACK_STATE_IS_ACTIVE),
    ("_TRACK_STATE_IS_VISIBLE", tc._TRACK_STATE_IS_VISIBLE),
    ("_TRACK_STATE_CAN_ASSOCIATE", tc._TRACK_STATE_CAN_ASSOCIATE),
    ("_TRACK_STATE_NEEDS_PREDICTION", tc._TRACK_STATE_NEEDS_PREDICTION),
    ("_TRACKING_TARGET_IS_PERSON", tc._TRACKING_TARGET_IS_PERSON),
    ("_TRACKING_TARGET_IS_DYNAMIC", tc._TRACKING_TARGET_IS_DYNAMIC),
    ("_TRACKING_ALGORITHM_USES_APPEARANCE", tc._TRACKING_ALGORITHM_USES_APPEARANCE),
    ("_TRACKING_ALGORITHM_USES_MOTION_COMPENSATION", tc._TRACKING_ALGORITHM_USES_MOTION_COMPENSATION),
]
for name, cache in _frozenset_caches:
    result.check(f"{name} frozenset 타입", isinstance(cache, frozenset), f"실제: {type(cache).__name__}")
    result.check(f"{name} 비어있지 않음", len(cache) > 0)

result.check("frozenset 캐시 8개", len(_frozenset_caches) == 8)

# 6 dict 캐시
_dict_caches = [
    ("_TRACK_STATE_KOREAN_MAP", tc._TRACK_STATE_KOREAN_MAP),
    ("_TRACKING_TARGET_MAX_AGE_MAP", tc._TRACKING_TARGET_MAX_AGE_MAP),
    ("_TRACKING_TARGET_MIN_HITS_MAP", tc._TRACKING_TARGET_MIN_HITS_MAP),
    ("_TRACKING_TARGET_KOREAN_MAP", tc._TRACKING_TARGET_KOREAN_MAP),
    ("_TRACKING_ALGORITHM_IOU_MAP", tc._TRACKING_ALGORITHM_IOU_MAP),
    ("_TRACKING_ALGORITHM_KOREAN_MAP", tc._TRACKING_ALGORITHM_KOREAN_MAP),
]
for name, cache in _dict_caches:
    result.check(f"{name} dict 타입", isinstance(cache, dict), f"실제: {type(cache).__name__}")
    result.check(f"{name} 비어있지 않음", len(cache) > 0)

result.check("dict 캐시 6개", len(_dict_caches) == 6)

# frozenset 캐시 크기 검증
result.check("_TRACK_STATE_IS_ACTIVE 크기 = 2", len(tc._TRACK_STATE_IS_ACTIVE) == 2)
result.check("_TRACK_STATE_IS_VISIBLE 크기 = 3", len(tc._TRACK_STATE_IS_VISIBLE) == 3)
result.check("_TRACK_STATE_CAN_ASSOCIATE 크기 = 5", len(tc._TRACK_STATE_CAN_ASSOCIATE) == 5)
result.check("_TRACK_STATE_NEEDS_PREDICTION 크기 = 2", len(tc._TRACK_STATE_NEEDS_PREDICTION) == 2)
result.check("_TRACKING_TARGET_IS_PERSON 크기 = 3", len(tc._TRACKING_TARGET_IS_PERSON) == 3)
result.check("_TRACKING_TARGET_IS_DYNAMIC 크기 = 5", len(tc._TRACKING_TARGET_IS_DYNAMIC) == 5)
result.check("_TRACKING_ALGORITHM_USES_APPEARANCE 크기 = 3", len(tc._TRACKING_ALGORITHM_USES_APPEARANCE) == 3)
result.check("_TRACKING_ALGORITHM_USES_MOTION_COMPENSATION 크기 = 2", len(tc._TRACKING_ALGORITHM_USES_MOTION_COMPENSATION) == 2)

# dict 캐시 크기 검증 (모든 멤버 포함)
result.check("_TRACK_STATE_KOREAN_MAP 크기 = 6", len(tc._TRACK_STATE_KOREAN_MAP) == 6)
result.check("_TRACKING_TARGET_MAX_AGE_MAP 크기 = 6", len(tc._TRACKING_TARGET_MAX_AGE_MAP) == 6)
result.check("_TRACKING_TARGET_MIN_HITS_MAP 크기 = 6", len(tc._TRACKING_TARGET_MIN_HITS_MAP) == 6)
result.check("_TRACKING_TARGET_KOREAN_MAP 크기 = 6", len(tc._TRACKING_TARGET_KOREAN_MAP) == 6)
result.check("_TRACKING_ALGORITHM_IOU_MAP 크기 = 6", len(tc._TRACKING_ALGORITHM_IOU_MAP) == 6)
result.check("_TRACKING_ALGORITHM_KOREAN_MAP 크기 = 6", len(tc._TRACKING_ALGORITHM_KOREAN_MAP) == 6)

# dict 키가 Enum 멤버인지 확인
for ts in TrackState:
    result.check(f"TrackState.{ts.name} in KOREAN_MAP", ts in tc._TRACK_STATE_KOREAN_MAP)

for tt in TrackingTarget:
    result.check(f"TrackingTarget.{tt.name} in MAX_AGE_MAP", tt in tc._TRACKING_TARGET_MAX_AGE_MAP)
    result.check(f"TrackingTarget.{tt.name} in MIN_HITS_MAP", tt in tc._TRACKING_TARGET_MIN_HITS_MAP)
    result.check(f"TrackingTarget.{tt.name} in KOREAN_MAP", tt in tc._TRACKING_TARGET_KOREAN_MAP)

for ta in TrackingAlgorithm:
    result.check(f"TrackingAlgorithm.{ta.name} in IOU_MAP", ta in tc._TRACKING_ALGORITHM_IOU_MAP)
    result.check(f"TrackingAlgorithm.{ta.name} in KOREAN_MAP", ta in tc._TRACKING_ALGORITHM_KOREAN_MAP)

# =============================================================================
# 29. 메타 검증 (버전, typing 모더나이제이션)
# =============================================================================
result.set_section("29. 메타 검증")

result.check("버전 1.1.0", tc.__version__ == "1.1.0", f"실제: {tc.__version__}")
result.check("__version__ str 타입", isinstance(tc.__version__, str))

# typing 모더나이제이션 검증 (Dict[, Tuple[ 미사용 -> dict[, tuple[ 사용)
import inspect
source = inspect.getsource(tc)
result.check("Dict[ 미사용 (모더나이제이션)", "Dict[" not in source)
result.check("Tuple[ 미사용 (모더나이제이션)", "Tuple[" not in source)
result.check("List[ 미사용 (모더나이제이션)", "List[" not in source)
result.check("FrozenSet[ 미사용 (모더나이제이션)", "FrozenSet[" not in source)
result.check("빈 선언 패턴 없음", "= {}" not in source and "= frozenset()" not in source)

# assert 존재 (비용 가중치 합 검증)
result.check("assert 문 존재 (가중치 합)", "assert abs(" in source)

# Final 타입 사용 확인
result.check("Final 타입 사용", "Final[" in source)

# @unique 데코레이터 사용
result.check("@unique 데코레이터 사용", "@unique" in source)

# Enum import 확인
result.check("from enum import Enum, unique", "from enum import Enum, unique" in source)

# typing.Final import 확인
result.check("from typing import Final", "from typing import Final" in source)

# =============================================================================
# 30. 엣지 케이스 (해시 가능, 이터레이션, ValueError)
# =============================================================================
result.set_section("30. 엣지 케이스")

# Enum 해시 가능
result.check("TrackState hashable", hash(TrackState.TENTATIVE) is not None)
result.check("TrackingTarget hashable", hash(TrackingTarget.PLAYER) is not None)
result.check("TrackingAlgorithm hashable", hash(TrackingAlgorithm.SORT) is not None)

# dict 키 사용 가능
d = {TrackState.TENTATIVE: 1, TrackingTarget.PLAYER: 2, TrackingAlgorithm.SORT: 3}
result.check("Enum dict key 사용 가능", len(d) == 3)

# set 중복 제거
s = {TrackState.TENTATIVE, TrackState.TENTATIVE, TrackState.CONFIRMED}
result.check("TrackState set 중복 제거", len(s) == 2)

s2 = {TrackingTarget.PLAYER, TrackingTarget.PLAYER}
result.check("TrackingTarget set 중복 제거", len(s2) == 1)

s3 = {TrackingAlgorithm.SORT, TrackingAlgorithm.SORT}
result.check("TrackingAlgorithm set 중복 제거", len(s3) == 1)

# Enum 이터레이션
result.check("TrackState 이터레이션 = 6", len(list(TrackState)) == 6)
result.check("TrackingTarget 이터레이션 = 6", len(list(TrackingTarget)) == 6)
result.check("TrackingAlgorithm 이터레이션 = 6", len(list(TrackingAlgorithm)) == 6)

# ValueError on invalid
try:
    TrackState("invalid_state")
    result.fail("TrackState('invalid_state') ValueError", "예외 미발생")
except ValueError:
    result.ok("TrackState('invalid_state') ValueError")

try:
    TrackingTarget("invalid_target")
    result.fail("TrackingTarget('invalid_target') ValueError", "예외 미발생")
except ValueError:
    result.ok("TrackingTarget('invalid_target') ValueError")

try:
    TrackingAlgorithm("invalid_algorithm")
    result.fail("TrackingAlgorithm('invalid_algorithm') ValueError", "예외 미발생")
except ValueError:
    result.ok("TrackingAlgorithm('invalid_algorithm') ValueError")

# KeyError on invalid key access
try:
    TrackState["INVALID"]
    result.fail("TrackState['INVALID'] KeyError", "예외 미발생")
except KeyError:
    result.ok("TrackState['INVALID'] KeyError")

try:
    TrackingTarget["INVALID"]
    result.fail("TrackingTarget['INVALID'] KeyError", "예외 미발생")
except KeyError:
    result.ok("TrackingTarget['INVALID'] KeyError")

try:
    TrackingAlgorithm["INVALID"]
    result.fail("TrackingAlgorithm['INVALID'] KeyError", "예외 미발생")
except KeyError:
    result.ok("TrackingAlgorithm['INVALID'] KeyError")

# Enum 비교 (동일성, 동등성)
result.check("TrackState.TENTATIVE == TrackState.TENTATIVE", TrackState.TENTATIVE == TrackState.TENTATIVE)
result.check("TrackState.TENTATIVE is TrackState.TENTATIVE", TrackState.TENTATIVE is TrackState.TENTATIVE)
result.check("TrackState.TENTATIVE != TrackState.CONFIRMED", TrackState.TENTATIVE != TrackState.CONFIRMED)

result.check("TrackingTarget.PLAYER == TrackingTarget.PLAYER", TrackingTarget.PLAYER == TrackingTarget.PLAYER)
result.check("TrackingTarget.PLAYER != TrackingTarget.BALL", TrackingTarget.PLAYER != TrackingTarget.BALL)

result.check("TrackingAlgorithm.SORT == TrackingAlgorithm.SORT", TrackingAlgorithm.SORT == TrackingAlgorithm.SORT)
result.check("TrackingAlgorithm.SORT != TrackingAlgorithm.DEEPSORT", TrackingAlgorithm.SORT != TrackingAlgorithm.DEEPSORT)

# Enum 문자열 표현
result.check("TrackState.TENTATIVE.value == 'tentative'", TrackState.TENTATIVE.value == "tentative")
result.check("TrackState.TENTATIVE.name == 'TENTATIVE'", TrackState.TENTATIVE.name == "TENTATIVE")

# frozenset 불변성 (추가 시도 시 AttributeError)
try:
    tc._TRACK_STATE_IS_ACTIVE.add(TrackState.DELETED)
    result.fail("frozenset 불변성", "add 성공 (불변이어야 함)")
except AttributeError:
    result.ok("frozenset 불변성 (add 시도 시 AttributeError)")

# 논리적 일관성: active이면 visible
for s in TrackState:
    if s.is_active:
        result.check(f"is_active이면 is_visible: {s.name}", s.is_visible)

# 논리적 일관성: needs_prediction이면 can_associate
for s in TrackState:
    if s.needs_prediction:
        result.check(f"needs_prediction이면 can_associate: {s.name}", s.can_associate)

# 논리적 일관성: DELETED는 모든 속성 False (can_associate 제외)
result.check("DELETED.is_active = False", not TrackState.DELETED.is_active)
result.check("DELETED.is_visible = False", not TrackState.DELETED.is_visible)
result.check("DELETED.can_associate = False", not TrackState.DELETED.can_associate)
result.check("DELETED.needs_prediction = False", not TrackState.DELETED.needs_prediction)

# 논리적 일관성: 사람인 타겟은 동적
for t in TrackingTarget:
    if t.is_person:
        result.check(f"is_person이면 is_dynamic: {t.name}", t.is_dynamic)

# =============================================================================
sys.exit(0 if result.summary() else 1)
