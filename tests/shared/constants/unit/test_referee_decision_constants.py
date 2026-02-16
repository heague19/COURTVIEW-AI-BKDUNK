# -*- coding: utf-8 -*-
"""
tests/shared/constants/unit/test_referee_decision_constants.py

AI 심판 판정 엔진 도메인 상수 모듈 단위 테스트
- DecisionConfidence (4종): 멤버, 값, str 상속, requires_human_review, get_name(i18n)
- FoulGrade (4종): 멤버, 값, str 상속, results_in_ejection, grants_free_throws, get_name(i18n)
- ContactArea (12종): 멤버, 값, str 상속, is_high_risk, get_name(i18n)
- 판정 신뢰도 임계치 (4종): 타입, 값, 순서
- 바이올레이션 감지 임계치 (15종): 타입, 값, 양수
- 파울 판정 임계치 (10종): 타입, 값, 양수
- 슈팅파울 분류 파라미터 (4종): 타입, 값, 양수
- 테크니컬 파울 파라미터 (4종): 타입, 값, 양수
- 멀티앵글 검증 파라미터 (4종): 타입, 값, 양수
- 판정 일관성 추적 파라미터 (4종): 타입, 값, 양수
- 리플레이/챌린지 파라미터 (3종): 타입, 값
- 유틸리티 함수 (3종): classify_decision_confidence, classify_foul_grade, is_action_reviewable
- __all__ Export (67항목)
- 메타 (version 1.0.0)

Author: COURTVIEW AI Team
Version: 1.0.0
"""

import io
import sys
from enum import Enum
from pathlib import Path

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트 경로 추가 (parents[4]: unit -> constants -> shared -> tests -> PROJECT_ROOT)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

from shared.constants.localization import SupportedLanguage
from shared.constants import referee_decision_constants
from shared.constants.referee_decision_constants import (
    # 열거형 (3종)
    DecisionConfidence,
    FoulGrade,
    ContactArea,
    # 판정 신뢰도 임계치 (4종)
    DECISION_AUTO_CONFIRM_THRESHOLD,
    DECISION_HIGH_CONFIDENCE_THRESHOLD,
    DECISION_MODERATE_CONFIDENCE_THRESHOLD,
    DECISION_MIN_ACTIONABLE_THRESHOLD,
    # 바이올레이션 감지 임계치 (15종)
    TRAVELING_PIVOT_DISPLACEMENT_M,
    TRAVELING_MAX_STEPS_AFTER_GATHER,
    DOUBLE_DRIBBLE_HOLD_TIME_SEC,
    CARRY_PALM_ANGLE_THRESHOLD_DEG,
    CARRY_BALL_REST_TIME_SEC,
    KICK_BALL_FOOT_VELOCITY_MIN,
    THREE_SECOND_OFFENSE_THRESHOLD_SEC,
    THREE_SECOND_EXIT_DISTANCE_M,
    DEFENSIVE_THREE_SEC_MARKING_DISTANCE_M,
    FIVE_SECOND_INBOUND_SEC,
    FIVE_SECOND_HELD_BALL_SEC,
    EIGHT_SECOND_BACKCOURT_SEC,
    GOALTENDING_MIN_DESCENT_SPEED,
    RIM_CYLINDER_RADIUS_M,
    OUT_OF_BOUNDS_MARGIN_M,
    # 파울 판정 임계치 (10종)
    CHARGE_BLOCK_SET_TIME_SEC,
    DEFENDER_FEET_SET_DISPLACEMENT_M,
    REACH_IN_ARM_SPEED_THRESHOLD,
    HAND_CHECK_DURATION_THRESHOLD_SEC,
    HOLDING_SPEED_REDUCTION_PCT,
    ILLEGAL_SCREEN_MOVEMENT_THRESHOLD,
    FLAGRANT_1_SEVERITY_SCORE,
    FLAGRANT_2_SEVERITY_SCORE,
    BALL_RELATEDNESS_THRESHOLD,
    WINDUP_ANGULAR_VELOCITY_THRESHOLD,
    # 슈팅파울 분류 (4종)
    SHOOTING_MOTION_START_SPEED,
    SHOT_RELEASE_SEPARATION_M,
    GATHER_TO_SHOT_MAX_SEC,
    AND_ONE_MAX_FLIGHT_TIME_SEC,
    # 테크니컬 파울 (4종)
    RIM_HANGING_MAX_SEC,
    RIM_HANGING_SAFETY_RADIUS_M,
    DELAY_OF_GAME_MAX_SEC,
    MAX_PLAYERS_ON_COURT_PER_TEAM,
    # 멀티앵글 검증 (4종)
    MULTI_ANGLE_MIN_CAMERAS,
    MULTI_ANGLE_AGREEMENT_THRESHOLD,
    MULTI_ANGLE_TIME_TOLERANCE_SEC,
    OPTIMAL_ANGLE_MIN_SEPARATION_DEG,
    # 판정 일관성 (4종)
    CONSISTENCY_COMPARISON_WINDOW,
    CONSISTENCY_DEVIATION_THRESHOLD,
    CALL_LEVEL_CALIBRATION_EVENTS,
    SEVERITY_BIN_WIDTH,
    # 리플레이/챌린지 (3종)
    REPLAY_MAX_REVIEW_TIME_SEC,
    CHALLENGE_SUCCESS_REFUND,
    CHALLENGE_MIN_REMAINING_SEC,
    # 유틸리티 함수 (3종)
    classify_decision_confidence,
    classify_foul_grade,
    is_action_reviewable,
)


# =============================================================================
# 테스트 하네스
# =============================================================================
class TestResult:
    """경량 테스트 결과 수집기."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.section = ""

    def set_section(self, name: str):
        self.section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, name: str):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, msg: str = ""):
        self.failed += 1
        print(f"  [FAIL] {name} - {msg}")

    def check(self, name: str, condition: bool, msg: str = ""):
        if condition:
            self.ok(name)
        else:
            self.fail(name, msg)

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL")
        print(f"{'='*60}")
        return self.failed == 0


# =============================================================================
# 메인 테스트
# =============================================================================
def main():
    T = TestResult()

    # =================================================================
    # [A] DecisionConfidence - 멤버, 값, str 상속
    # =================================================================
    T.set_section("[A] DecisionConfidence - 멤버, 값, str 상속")

    # 멤버 존재
    expected_dc_members = ["AUTO_CONFIRM", "HIGH", "MODERATE", "LOW"]
    for name in expected_dc_members:
        T.check(f"DecisionConfidence.{name} 멤버 존재", hasattr(DecisionConfidence, name))

    # 멤버 수
    T.check("DecisionConfidence 멤버 수 4", len(DecisionConfidence) == 4,
            f"expected 4, got {len(DecisionConfidence)}")

    # 값 검증
    dc_values = {
        "AUTO_CONFIRM": "auto_confirm", "HIGH": "high",
        "MODERATE": "moderate", "LOW": "low",
    }
    for name, val in dc_values.items():
        member = DecisionConfidence[name]
        T.check(f"DecisionConfidence.{name}.value == '{val}'",
                member.value == val, f"got {member.value!r}")

    # str 상속
    for member in DecisionConfidence:
        T.check(f"DecisionConfidence.{member.name} isinstance(str)",
                isinstance(member, str))

    # str mixin: member == value
    for member in DecisionConfidence:
        T.check(f"DecisionConfidence.{member.name} == value (str mixin)",
                member == member.value,
                f"member={member!r}, value={member.value!r}")

    # str(member) 형식 검증
    for member in DecisionConfidence:
        s = str(member)
        T.check(f"str(DecisionConfidence.{member.name}) == value",
                s == member.value, f"got {s!r}")

    # Enum 상속
    for member in DecisionConfidence:
        T.check(f"DecisionConfidence.{member.name} isinstance(Enum)",
                isinstance(member, Enum))

    # 값 유일성
    dc_vals = [m.value for m in DecisionConfidence]
    T.check("DecisionConfidence 값 유일성", len(dc_vals) == len(set(dc_vals)))

    # identity (is)
    T.check("DecisionConfidence.AUTO_CONFIRM is DecisionConfidence('auto_confirm')",
            DecisionConfidence.AUTO_CONFIRM is DecisionConfidence("auto_confirm"))
    T.check("DecisionConfidence.LOW is DecisionConfidence('low')",
            DecisionConfidence.LOW is DecisionConfidence("low"))

    # hash
    T.check("DecisionConfidence 해시 가능",
            all(isinstance(hash(m), int) for m in DecisionConfidence))

    # set 사용
    s = {DecisionConfidence.AUTO_CONFIRM, DecisionConfidence.HIGH, DecisionConfidence.LOW}
    T.check("DecisionConfidence set 사용 가능", len(s) == 3)

    # dict 키 사용
    d = {DecisionConfidence.AUTO_CONFIRM: 1, DecisionConfidence.LOW: 2}
    T.check("DecisionConfidence dict 키 사용",
            d[DecisionConfidence.AUTO_CONFIRM] == 1 and d[DecisionConfidence.LOW] == 2)

    # =================================================================
    # [B] DecisionConfidence.requires_human_review (AUTO_CONFIRM, HIGH: False / MODERATE, LOW: True)
    # =================================================================
    T.set_section("[B] DecisionConfidence.requires_human_review")

    review_map = {
        DecisionConfidence.AUTO_CONFIRM: False,
        DecisionConfidence.HIGH: False,
        DecisionConfidence.MODERATE: True,
        DecisionConfidence.LOW: True,
    }
    for member, expected in review_map.items():
        T.check(f"DecisionConfidence.{member.name}.requires_human_review == {expected}",
                member.requires_human_review == expected,
                f"got {member.requires_human_review}")

    # 타입 검증
    for member in DecisionConfidence:
        T.check(f"DecisionConfidence.{member.name}.requires_human_review is bool",
                isinstance(member.requires_human_review, bool))

    # 리뷰 필요 수: 2개
    review_count = sum(1 for m in DecisionConfidence if m.requires_human_review)
    T.check("requires_human_review True 수 == 2", review_count == 2, f"got {review_count}")

    # 리뷰 불필요 수: 2개
    no_review_count = sum(1 for m in DecisionConfidence if not m.requires_human_review)
    T.check("requires_human_review False 수 == 2", no_review_count == 2, f"got {no_review_count}")

    # =================================================================
    # [C] DecisionConfidence.get_name (i18n 5개국어)
    # =================================================================
    T.set_section("[C] DecisionConfidence.get_name (i18n)")

    # 한국어 (기본)
    dc_ko = {
        DecisionConfidence.AUTO_CONFIRM: "자동 확정",
        DecisionConfidence.HIGH: "높은 확신",
        DecisionConfidence.MODERATE: "보통 확신",
        DecisionConfidence.LOW: "낮은 확신",
    }
    for member, expected in dc_ko.items():
        T.check(f"DecisionConfidence.{member.name}.get_name(KO) == '{expected}'",
                member.get_name(SupportedLanguage.KO) == expected,
                f"got {member.get_name(SupportedLanguage.KO)!r}")

    # 영어
    dc_en = {
        DecisionConfidence.AUTO_CONFIRM: "Auto Confirm",
        DecisionConfidence.HIGH: "High Confidence",
        DecisionConfidence.MODERATE: "Moderate Confidence",
        DecisionConfidence.LOW: "Low Confidence",
    }
    for member, expected in dc_en.items():
        T.check(f"DecisionConfidence.{member.name}.get_name(EN) == '{expected}'",
                member.get_name(SupportedLanguage.EN) == expected,
                f"got {member.get_name(SupportedLanguage.EN)!r}")

    # 일본어
    dc_ja = {
        DecisionConfidence.AUTO_CONFIRM: "自動確定",
        DecisionConfidence.HIGH: "高確信",
        DecisionConfidence.MODERATE: "中確信",
        DecisionConfidence.LOW: "低確信",
    }
    for member, expected in dc_ja.items():
        T.check(f"DecisionConfidence.{member.name}.get_name(JA) == '{expected}'",
                member.get_name(SupportedLanguage.JA) == expected,
                f"got {member.get_name(SupportedLanguage.JA)!r}")

    # 중국어
    dc_zh = {
        DecisionConfidence.AUTO_CONFIRM: "自动确认",
        DecisionConfidence.HIGH: "高置信度",
        DecisionConfidence.MODERATE: "中置信度",
        DecisionConfidence.LOW: "低置信度",
    }
    for member, expected in dc_zh.items():
        T.check(f"DecisionConfidence.{member.name}.get_name(ZH) == '{expected}'",
                member.get_name(SupportedLanguage.ZH) == expected,
                f"got {member.get_name(SupportedLanguage.ZH)!r}")

    # 스페인어
    dc_es = {
        DecisionConfidence.AUTO_CONFIRM: "Confirmación Automática",
        DecisionConfidence.HIGH: "Alta Confianza",
        DecisionConfidence.MODERATE: "Confianza Moderada",
        DecisionConfidence.LOW: "Baja Confianza",
    }
    for member, expected in dc_es.items():
        T.check(f"DecisionConfidence.{member.name}.get_name(ES) == '{expected}'",
                member.get_name(SupportedLanguage.ES) == expected,
                f"got {member.get_name(SupportedLanguage.ES)!r}")

    # 기본값 (인자 없이 호출 시 한국어)
    for member in DecisionConfidence:
        T.check(f"DecisionConfidence.{member.name}.get_name() == get_name(KO)",
                member.get_name() == member.get_name(SupportedLanguage.KO))

    # get_name 반환 타입
    for member in DecisionConfidence:
        T.check(f"DecisionConfidence.{member.name}.get_name() is str",
                isinstance(member.get_name(), str))

    # get_name 비어있지 않음
    for member in DecisionConfidence:
        for lang in SupportedLanguage:
            T.check(f"DecisionConfidence.{member.name}.get_name({lang.name}) 비어있지 않음",
                    len(member.get_name(lang)) > 0)

    # =================================================================
    # [D] FoulGrade - 멤버, 값, str 상속
    # =================================================================
    T.set_section("[D] FoulGrade - 멤버, 값, str 상속")

    expected_fg_members = ["NORMAL", "FLAGRANT_1", "FLAGRANT_2", "DISQUALIFYING"]
    for name in expected_fg_members:
        T.check(f"FoulGrade.{name} 멤버 존재", hasattr(FoulGrade, name))

    T.check("FoulGrade 멤버 수 4", len(FoulGrade) == 4,
            f"expected 4, got {len(FoulGrade)}")

    fg_values = {
        "NORMAL": "normal", "FLAGRANT_1": "flagrant_1",
        "FLAGRANT_2": "flagrant_2", "DISQUALIFYING": "disqualifying",
    }
    for name, val in fg_values.items():
        member = FoulGrade[name]
        T.check(f"FoulGrade.{name}.value == '{val}'",
                member.value == val, f"got {member.value!r}")

    for member in FoulGrade:
        T.check(f"FoulGrade.{member.name} isinstance(str)", isinstance(member, str))

    for member in FoulGrade:
        T.check(f"FoulGrade.{member.name} == value (str mixin)",
                member == member.value)

    for member in FoulGrade:
        s = str(member)
        T.check(f"str(FoulGrade.{member.name}) == value", s == member.value, f"got {s!r}")

    for member in FoulGrade:
        T.check(f"FoulGrade.{member.name} isinstance(Enum)", isinstance(member, Enum))

    fg_vals = [m.value for m in FoulGrade]
    T.check("FoulGrade 값 유일성", len(fg_vals) == len(set(fg_vals)))

    T.check("FoulGrade.NORMAL is FoulGrade('normal')",
            FoulGrade.NORMAL is FoulGrade("normal"))
    T.check("FoulGrade.DISQUALIFYING is FoulGrade('disqualifying')",
            FoulGrade.DISQUALIFYING is FoulGrade("disqualifying"))

    T.check("FoulGrade 해시 가능", all(isinstance(hash(m), int) for m in FoulGrade))

    # =================================================================
    # [E] FoulGrade.results_in_ejection
    # =================================================================
    T.set_section("[E] FoulGrade.results_in_ejection")

    ejection_map = {
        FoulGrade.NORMAL: False,
        FoulGrade.FLAGRANT_1: False,
        FoulGrade.FLAGRANT_2: True,
        FoulGrade.DISQUALIFYING: True,
    }
    for member, expected in ejection_map.items():
        T.check(f"FoulGrade.{member.name}.results_in_ejection == {expected}",
                member.results_in_ejection == expected,
                f"got {member.results_in_ejection}")

    for member in FoulGrade:
        T.check(f"FoulGrade.{member.name}.results_in_ejection is bool",
                isinstance(member.results_in_ejection, bool))

    ejection_count = sum(1 for m in FoulGrade if m.results_in_ejection)
    T.check("results_in_ejection True 수 == 2", ejection_count == 2, f"got {ejection_count}")

    # =================================================================
    # [F] FoulGrade.grants_free_throws
    # =================================================================
    T.set_section("[F] FoulGrade.grants_free_throws")

    ft_map = {
        FoulGrade.NORMAL: False,
        FoulGrade.FLAGRANT_1: True,
        FoulGrade.FLAGRANT_2: True,
        FoulGrade.DISQUALIFYING: True,
    }
    for member, expected in ft_map.items():
        T.check(f"FoulGrade.{member.name}.grants_free_throws == {expected}",
                member.grants_free_throws == expected,
                f"got {member.grants_free_throws}")

    for member in FoulGrade:
        T.check(f"FoulGrade.{member.name}.grants_free_throws is bool",
                isinstance(member.grants_free_throws, bool))

    ft_count = sum(1 for m in FoulGrade if m.grants_free_throws)
    T.check("grants_free_throws True 수 == 3", ft_count == 3, f"got {ft_count}")

    # NORMAL만 False
    no_ft = [m for m in FoulGrade if not m.grants_free_throws]
    T.check("grants_free_throws False == NORMAL만",
            len(no_ft) == 1 and no_ft[0] == FoulGrade.NORMAL)

    # =================================================================
    # [G] FoulGrade.get_name (i18n 5개국어)
    # =================================================================
    T.set_section("[G] FoulGrade.get_name (i18n)")

    fg_ko = {
        FoulGrade.NORMAL: "일반 파울",
        FoulGrade.FLAGRANT_1: "플래그런트 1",
        FoulGrade.FLAGRANT_2: "플래그런트 2",
        FoulGrade.DISQUALIFYING: "실격 파울",
    }
    for member, expected in fg_ko.items():
        T.check(f"FoulGrade.{member.name}.get_name(KO) == '{expected}'",
                member.get_name(SupportedLanguage.KO) == expected,
                f"got {member.get_name(SupportedLanguage.KO)!r}")

    fg_en = {
        FoulGrade.NORMAL: "Normal Foul",
        FoulGrade.FLAGRANT_1: "Flagrant 1",
        FoulGrade.FLAGRANT_2: "Flagrant 2",
        FoulGrade.DISQUALIFYING: "Disqualifying Foul",
    }
    for member, expected in fg_en.items():
        T.check(f"FoulGrade.{member.name}.get_name(EN) == '{expected}'",
                member.get_name(SupportedLanguage.EN) == expected,
                f"got {member.get_name(SupportedLanguage.EN)!r}")

    fg_ja = {
        FoulGrade.NORMAL: "通常ファウル",
        FoulGrade.FLAGRANT_1: "フレグラント1",
        FoulGrade.FLAGRANT_2: "フレグラント2",
        FoulGrade.DISQUALIFYING: "失格ファウル",
    }
    for member, expected in fg_ja.items():
        T.check(f"FoulGrade.{member.name}.get_name(JA) == '{expected}'",
                member.get_name(SupportedLanguage.JA) == expected,
                f"got {member.get_name(SupportedLanguage.JA)!r}")

    fg_zh = {
        FoulGrade.NORMAL: "普通犯规",
        FoulGrade.FLAGRANT_1: "恶意犯规1级",
        FoulGrade.FLAGRANT_2: "恶意犯规2级",
        FoulGrade.DISQUALIFYING: "取消资格犯规",
    }
    for member, expected in fg_zh.items():
        T.check(f"FoulGrade.{member.name}.get_name(ZH) == '{expected}'",
                member.get_name(SupportedLanguage.ZH) == expected,
                f"got {member.get_name(SupportedLanguage.ZH)!r}")

    fg_es = {
        FoulGrade.NORMAL: "Falta Normal",
        FoulGrade.FLAGRANT_1: "Flagrante 1",
        FoulGrade.FLAGRANT_2: "Flagrante 2",
        FoulGrade.DISQUALIFYING: "Falta Descalificante",
    }
    for member, expected in fg_es.items():
        T.check(f"FoulGrade.{member.name}.get_name(ES) == '{expected}'",
                member.get_name(SupportedLanguage.ES) == expected,
                f"got {member.get_name(SupportedLanguage.ES)!r}")

    for member in FoulGrade:
        T.check(f"FoulGrade.{member.name}.get_name() == get_name(KO)",
                member.get_name() == member.get_name(SupportedLanguage.KO))

    for member in FoulGrade:
        for lang in SupportedLanguage:
            T.check(f"FoulGrade.{member.name}.get_name({lang.name}) 비어있지 않음",
                    len(member.get_name(lang)) > 0)

    # =================================================================
    # [H] ContactArea - 멤버, 값, str 상속 (12종)
    # =================================================================
    T.set_section("[H] ContactArea - 멤버, 값, str 상속 (12종)")

    expected_ca_members = [
        "HEAD_NECK", "SHOULDER", "CHEST_TORSO", "BACK",
        "UPPER_ARM", "FOREARM_HAND", "HIP_WAIST", "THIGH",
        "KNEE", "LOWER_LEG", "FOOT", "BALL_HAND",
    ]
    for name in expected_ca_members:
        T.check(f"ContactArea.{name} 멤버 존재", hasattr(ContactArea, name))

    T.check("ContactArea 멤버 수 12", len(ContactArea) == 12,
            f"expected 12, got {len(ContactArea)}")

    ca_values = {
        "HEAD_NECK": "head_neck", "SHOULDER": "shoulder",
        "CHEST_TORSO": "chest_torso", "BACK": "back",
        "UPPER_ARM": "upper_arm", "FOREARM_HAND": "forearm_hand",
        "HIP_WAIST": "hip_waist", "THIGH": "thigh",
        "KNEE": "knee", "LOWER_LEG": "lower_leg",
        "FOOT": "foot", "BALL_HAND": "ball_hand",
    }
    for name, val in ca_values.items():
        member = ContactArea[name]
        T.check(f"ContactArea.{name}.value == '{val}'",
                member.value == val, f"got {member.value!r}")

    for member in ContactArea:
        T.check(f"ContactArea.{member.name} isinstance(str)", isinstance(member, str))

    for member in ContactArea:
        T.check(f"ContactArea.{member.name} == value (str mixin)",
                member == member.value)

    for member in ContactArea:
        s = str(member)
        T.check(f"str(ContactArea.{member.name}) == value", s == member.value, f"got {s!r}")

    for member in ContactArea:
        T.check(f"ContactArea.{member.name} isinstance(Enum)", isinstance(member, Enum))

    ca_vals = [m.value for m in ContactArea]
    T.check("ContactArea 값 유일성", len(ca_vals) == len(set(ca_vals)))

    T.check("ContactArea 해시 가능", all(isinstance(hash(m), int) for m in ContactArea))

    # =================================================================
    # [I] ContactArea.is_high_risk (HEAD_NECK, KNEE: True / 나머지: False)
    # =================================================================
    T.set_section("[I] ContactArea.is_high_risk")

    high_risk_map = {
        ContactArea.HEAD_NECK: True,
        ContactArea.KNEE: True,
        ContactArea.SHOULDER: False,
        ContactArea.CHEST_TORSO: False,
        ContactArea.BACK: False,
        ContactArea.UPPER_ARM: False,
        ContactArea.FOREARM_HAND: False,
        ContactArea.HIP_WAIST: False,
        ContactArea.THIGH: False,
        ContactArea.LOWER_LEG: False,
        ContactArea.FOOT: False,
        ContactArea.BALL_HAND: False,
    }
    for member, expected in high_risk_map.items():
        T.check(f"ContactArea.{member.name}.is_high_risk == {expected}",
                member.is_high_risk == expected,
                f"got {member.is_high_risk}")

    for member in ContactArea:
        T.check(f"ContactArea.{member.name}.is_high_risk is bool",
                isinstance(member.is_high_risk, bool))

    high_risk_count = sum(1 for m in ContactArea if m.is_high_risk)
    T.check("is_high_risk True 수 == 2", high_risk_count == 2, f"got {high_risk_count}")

    not_high_risk_count = sum(1 for m in ContactArea if not m.is_high_risk)
    T.check("is_high_risk False 수 == 10", not_high_risk_count == 10, f"got {not_high_risk_count}")

    # =================================================================
    # [J] ContactArea.get_name (i18n 한국어, 영어)
    # =================================================================
    T.set_section("[J] ContactArea.get_name (i18n)")

    ca_ko = {
        ContactArea.HEAD_NECK: "머리/목",
        ContactArea.SHOULDER: "어깨",
        ContactArea.CHEST_TORSO: "가슴/체간",
        ContactArea.BACK: "등",
        ContactArea.UPPER_ARM: "상완",
        ContactArea.FOREARM_HAND: "전완/손",
        ContactArea.HIP_WAIST: "골반/허리",
        ContactArea.THIGH: "대퇴",
        ContactArea.KNEE: "무릎",
        ContactArea.LOWER_LEG: "하퇴",
        ContactArea.FOOT: "발",
        ContactArea.BALL_HAND: "볼/손",
    }
    for member, expected in ca_ko.items():
        T.check(f"ContactArea.{member.name}.get_name(KO) == '{expected}'",
                member.get_name(SupportedLanguage.KO) == expected,
                f"got {member.get_name(SupportedLanguage.KO)!r}")

    ca_en = {
        ContactArea.HEAD_NECK: "Head/Neck",
        ContactArea.SHOULDER: "Shoulder",
        ContactArea.CHEST_TORSO: "Chest/Torso",
        ContactArea.BACK: "Back",
        ContactArea.UPPER_ARM: "Upper Arm",
        ContactArea.FOREARM_HAND: "Forearm/Hand",
        ContactArea.HIP_WAIST: "Hip/Waist",
        ContactArea.THIGH: "Thigh",
        ContactArea.KNEE: "Knee",
        ContactArea.LOWER_LEG: "Lower Leg",
        ContactArea.FOOT: "Foot",
        ContactArea.BALL_HAND: "Ball/Hand",
    }
    for member, expected in ca_en.items():
        T.check(f"ContactArea.{member.name}.get_name(EN) == '{expected}'",
                member.get_name(SupportedLanguage.EN) == expected,
                f"got {member.get_name(SupportedLanguage.EN)!r}")

    # 기본값 (인자 없이 호출 시 한국어)
    for member in ContactArea:
        T.check(f"ContactArea.{member.name}.get_name() == get_name(KO)",
                member.get_name() == member.get_name(SupportedLanguage.KO))

    # 모든 언어 비어있지 않음
    for member in ContactArea:
        for lang in SupportedLanguage:
            T.check(f"ContactArea.{member.name}.get_name({lang.name}) 비어있지 않음",
                    len(member.get_name(lang)) > 0)

    # =================================================================
    # [K] 판정 신뢰도 임계치 (4종) - 타입, 값, 순서
    # =================================================================
    T.set_section("[K] 판정 신뢰도 임계치 (4종)")

    # 타입 검증
    T.check("DECISION_AUTO_CONFIRM_THRESHOLD is float",
            isinstance(DECISION_AUTO_CONFIRM_THRESHOLD, float))
    T.check("DECISION_HIGH_CONFIDENCE_THRESHOLD is float",
            isinstance(DECISION_HIGH_CONFIDENCE_THRESHOLD, float))
    T.check("DECISION_MODERATE_CONFIDENCE_THRESHOLD is float",
            isinstance(DECISION_MODERATE_CONFIDENCE_THRESHOLD, float))
    T.check("DECISION_MIN_ACTIONABLE_THRESHOLD is float",
            isinstance(DECISION_MIN_ACTIONABLE_THRESHOLD, float))

    # 구체적 값
    T.check("AUTO_CONFIRM == 0.95",
            abs(DECISION_AUTO_CONFIRM_THRESHOLD - 0.95) < 1e-9)
    T.check("HIGH == 0.85",
            abs(DECISION_HIGH_CONFIDENCE_THRESHOLD - 0.85) < 1e-9)
    T.check("MODERATE == 0.70",
            abs(DECISION_MODERATE_CONFIDENCE_THRESHOLD - 0.70) < 1e-9)
    T.check("MIN_ACTIONABLE == 0.50",
            abs(DECISION_MIN_ACTIONABLE_THRESHOLD - 0.50) < 1e-9)

    # 순서 (AUTO > HIGH > MODERATE > MIN)
    T.check("AUTO > HIGH",
            DECISION_AUTO_CONFIRM_THRESHOLD > DECISION_HIGH_CONFIDENCE_THRESHOLD)
    T.check("HIGH > MODERATE",
            DECISION_HIGH_CONFIDENCE_THRESHOLD > DECISION_MODERATE_CONFIDENCE_THRESHOLD)
    T.check("MODERATE > MIN",
            DECISION_MODERATE_CONFIDENCE_THRESHOLD > DECISION_MIN_ACTIONABLE_THRESHOLD)

    # 범위 (0~1)
    for name, val in [
        ("AUTO", DECISION_AUTO_CONFIRM_THRESHOLD),
        ("HIGH", DECISION_HIGH_CONFIDENCE_THRESHOLD),
        ("MODERATE", DECISION_MODERATE_CONFIDENCE_THRESHOLD),
        ("MIN", DECISION_MIN_ACTIONABLE_THRESHOLD),
    ]:
        T.check(f"{name} 범위 0~1", 0.0 <= val <= 1.0, f"got {val}")

    # =================================================================
    # [L] 바이올레이션 감지 임계치 (15종) - 타입, 양수/음수, 합리적 범위
    # =================================================================
    T.set_section("[L] 바이올레이션 감지 임계치 (15종)")

    # float 임계치 (양수)
    violation_positive_floats = {
        "TRAVELING_PIVOT_DISPLACEMENT_M": (TRAVELING_PIVOT_DISPLACEMENT_M, 0.15),
        "DOUBLE_DRIBBLE_HOLD_TIME_SEC": (DOUBLE_DRIBBLE_HOLD_TIME_SEC, 0.3),
        "CARRY_PALM_ANGLE_THRESHOLD_DEG": (CARRY_PALM_ANGLE_THRESHOLD_DEG, 135.0),
        "CARRY_BALL_REST_TIME_SEC": (CARRY_BALL_REST_TIME_SEC, 0.15),
        "KICK_BALL_FOOT_VELOCITY_MIN": (KICK_BALL_FOOT_VELOCITY_MIN, 1.5),
        "THREE_SECOND_OFFENSE_THRESHOLD_SEC": (THREE_SECOND_OFFENSE_THRESHOLD_SEC, 3.0),
        "THREE_SECOND_EXIT_DISTANCE_M": (THREE_SECOND_EXIT_DISTANCE_M, 0.5),
        "DEFENSIVE_THREE_SEC_MARKING_DISTANCE_M": (DEFENSIVE_THREE_SEC_MARKING_DISTANCE_M, 0.91),
        "FIVE_SECOND_INBOUND_SEC": (FIVE_SECOND_INBOUND_SEC, 5.0),
        "FIVE_SECOND_HELD_BALL_SEC": (FIVE_SECOND_HELD_BALL_SEC, 5.0),
        "EIGHT_SECOND_BACKCOURT_SEC": (EIGHT_SECOND_BACKCOURT_SEC, 8.0),
        "RIM_CYLINDER_RADIUS_M": (RIM_CYLINDER_RADIUS_M, 0.225),
        "OUT_OF_BOUNDS_MARGIN_M": (OUT_OF_BOUNDS_MARGIN_M, 0.05),
    }
    for name, (val, expected) in violation_positive_floats.items():
        T.check(f"{name} is float", isinstance(val, float))
        T.check(f"{name} > 0", val > 0, f"got {val}")
        T.check(f"{name} == {expected}", abs(val - expected) < 1e-9, f"got {val}")

    # int 임계치
    T.check("TRAVELING_MAX_STEPS_AFTER_GATHER is int",
            isinstance(TRAVELING_MAX_STEPS_AFTER_GATHER, int))
    T.check("TRAVELING_MAX_STEPS_AFTER_GATHER == 2",
            TRAVELING_MAX_STEPS_AFTER_GATHER == 2)
    T.check("TRAVELING_MAX_STEPS_AFTER_GATHER > 0",
            TRAVELING_MAX_STEPS_AFTER_GATHER > 0)

    # 골텐딩 하강 속도 (음수)
    T.check("GOALTENDING_MIN_DESCENT_SPEED is float",
            isinstance(GOALTENDING_MIN_DESCENT_SPEED, float))
    T.check("GOALTENDING_MIN_DESCENT_SPEED < 0 (하강)",
            GOALTENDING_MIN_DESCENT_SPEED < 0,
            f"got {GOALTENDING_MIN_DESCENT_SPEED}")
    T.check("GOALTENDING_MIN_DESCENT_SPEED == -0.5",
            abs(GOALTENDING_MIN_DESCENT_SPEED - (-0.5)) < 1e-9)

    # 시간 위반 순서 (3초 < 5초 < 8초)
    T.check("3초 < 5초 < 8초 위반 순서",
            THREE_SECOND_OFFENSE_THRESHOLD_SEC
            < FIVE_SECOND_INBOUND_SEC
            < EIGHT_SECOND_BACKCOURT_SEC)

    # =================================================================
    # [M] 파울 판정 임계치 (10종) - 타입, 양수, 구체적 값
    # =================================================================
    T.set_section("[M] 파울 판정 임계치 (10종)")

    foul_thresholds = {
        "CHARGE_BLOCK_SET_TIME_SEC": (CHARGE_BLOCK_SET_TIME_SEC, 0.3),
        "DEFENDER_FEET_SET_DISPLACEMENT_M": (DEFENDER_FEET_SET_DISPLACEMENT_M, 0.10),
        "REACH_IN_ARM_SPEED_THRESHOLD": (REACH_IN_ARM_SPEED_THRESHOLD, 2.0),
        "HAND_CHECK_DURATION_THRESHOLD_SEC": (HAND_CHECK_DURATION_THRESHOLD_SEC, 0.5),
        "HOLDING_SPEED_REDUCTION_PCT": (HOLDING_SPEED_REDUCTION_PCT, 0.30),
        "ILLEGAL_SCREEN_MOVEMENT_THRESHOLD": (ILLEGAL_SCREEN_MOVEMENT_THRESHOLD, 0.5),
        "FLAGRANT_1_SEVERITY_SCORE": (FLAGRANT_1_SEVERITY_SCORE, 0.65),
        "FLAGRANT_2_SEVERITY_SCORE": (FLAGRANT_2_SEVERITY_SCORE, 0.85),
        "BALL_RELATEDNESS_THRESHOLD": (BALL_RELATEDNESS_THRESHOLD, 0.30),
        "WINDUP_ANGULAR_VELOCITY_THRESHOLD": (WINDUP_ANGULAR_VELOCITY_THRESHOLD, 500.0),
    }
    for name, (val, expected) in foul_thresholds.items():
        T.check(f"{name} is float", isinstance(val, float))
        T.check(f"{name} > 0", val > 0, f"got {val}")
        T.check(f"{name} == {expected}", abs(val - expected) < 1e-9, f"got {val}")

    # 플래그런트 순서 (F1 < F2)
    T.check("FLAGRANT_1 < FLAGRANT_2",
            FLAGRANT_1_SEVERITY_SCORE < FLAGRANT_2_SEVERITY_SCORE)

    # HOLDING_SPEED_REDUCTION_PCT (0~1 범위)
    T.check("HOLDING_SPEED_REDUCTION_PCT 범위 0~1",
            0.0 <= HOLDING_SPEED_REDUCTION_PCT <= 1.0)

    # BALL_RELATEDNESS_THRESHOLD (0~1 범위)
    T.check("BALL_RELATEDNESS_THRESHOLD 범위 0~1",
            0.0 <= BALL_RELATEDNESS_THRESHOLD <= 1.0)

    # =================================================================
    # [N] 슈팅파울 분류 파라미터 (4종) - 타입, 양수, 구체적 값
    # =================================================================
    T.set_section("[N] 슈팅파울 분류 파라미터 (4종)")

    shooting_params = {
        "SHOOTING_MOTION_START_SPEED": (SHOOTING_MOTION_START_SPEED, 1.0),
        "SHOT_RELEASE_SEPARATION_M": (SHOT_RELEASE_SEPARATION_M, 0.10),
        "GATHER_TO_SHOT_MAX_SEC": (GATHER_TO_SHOT_MAX_SEC, 0.5),
        "AND_ONE_MAX_FLIGHT_TIME_SEC": (AND_ONE_MAX_FLIGHT_TIME_SEC, 3.0),
    }
    for name, (val, expected) in shooting_params.items():
        T.check(f"{name} is float", isinstance(val, float))
        T.check(f"{name} > 0", val > 0, f"got {val}")
        T.check(f"{name} == {expected}", abs(val - expected) < 1e-9, f"got {val}")

    # =================================================================
    # [O] 테크니컬 파울 파라미터 (4종)
    # =================================================================
    T.set_section("[O] 테크니컬 파울 파라미터 (4종)")

    T.check("RIM_HANGING_MAX_SEC is float", isinstance(RIM_HANGING_MAX_SEC, float))
    T.check("RIM_HANGING_MAX_SEC == 2.0", abs(RIM_HANGING_MAX_SEC - 2.0) < 1e-9)
    T.check("RIM_HANGING_MAX_SEC > 0", RIM_HANGING_MAX_SEC > 0)

    T.check("RIM_HANGING_SAFETY_RADIUS_M is float", isinstance(RIM_HANGING_SAFETY_RADIUS_M, float))
    T.check("RIM_HANGING_SAFETY_RADIUS_M == 1.5", abs(RIM_HANGING_SAFETY_RADIUS_M - 1.5) < 1e-9)
    T.check("RIM_HANGING_SAFETY_RADIUS_M > 0", RIM_HANGING_SAFETY_RADIUS_M > 0)

    T.check("DELAY_OF_GAME_MAX_SEC is float", isinstance(DELAY_OF_GAME_MAX_SEC, float))
    T.check("DELAY_OF_GAME_MAX_SEC == 5.0", abs(DELAY_OF_GAME_MAX_SEC - 5.0) < 1e-9)
    T.check("DELAY_OF_GAME_MAX_SEC > 0", DELAY_OF_GAME_MAX_SEC > 0)

    T.check("MAX_PLAYERS_ON_COURT_PER_TEAM is int", isinstance(MAX_PLAYERS_ON_COURT_PER_TEAM, int))
    T.check("MAX_PLAYERS_ON_COURT_PER_TEAM == 5", MAX_PLAYERS_ON_COURT_PER_TEAM == 5)
    T.check("MAX_PLAYERS_ON_COURT_PER_TEAM > 0", MAX_PLAYERS_ON_COURT_PER_TEAM > 0)

    # =================================================================
    # [P] 멀티앵글 검증 파라미터 (4종)
    # =================================================================
    T.set_section("[P] 멀티앵글 검증 파라미터 (4종)")

    T.check("MULTI_ANGLE_MIN_CAMERAS is int", isinstance(MULTI_ANGLE_MIN_CAMERAS, int))
    T.check("MULTI_ANGLE_MIN_CAMERAS == 2", MULTI_ANGLE_MIN_CAMERAS == 2)
    T.check("MULTI_ANGLE_MIN_CAMERAS > 0", MULTI_ANGLE_MIN_CAMERAS > 0)

    T.check("MULTI_ANGLE_AGREEMENT_THRESHOLD is float",
            isinstance(MULTI_ANGLE_AGREEMENT_THRESHOLD, float))
    T.check("MULTI_ANGLE_AGREEMENT_THRESHOLD == 0.75",
            abs(MULTI_ANGLE_AGREEMENT_THRESHOLD - 0.75) < 1e-9)
    T.check("MULTI_ANGLE_AGREEMENT_THRESHOLD 범위 0~1",
            0.0 <= MULTI_ANGLE_AGREEMENT_THRESHOLD <= 1.0)

    T.check("MULTI_ANGLE_TIME_TOLERANCE_SEC is float",
            isinstance(MULTI_ANGLE_TIME_TOLERANCE_SEC, float))
    T.check("MULTI_ANGLE_TIME_TOLERANCE_SEC == 0.05",
            abs(MULTI_ANGLE_TIME_TOLERANCE_SEC - 0.05) < 1e-9)
    T.check("MULTI_ANGLE_TIME_TOLERANCE_SEC > 0", MULTI_ANGLE_TIME_TOLERANCE_SEC > 0)

    T.check("OPTIMAL_ANGLE_MIN_SEPARATION_DEG is float",
            isinstance(OPTIMAL_ANGLE_MIN_SEPARATION_DEG, float))
    T.check("OPTIMAL_ANGLE_MIN_SEPARATION_DEG == 30.0",
            abs(OPTIMAL_ANGLE_MIN_SEPARATION_DEG - 30.0) < 1e-9)
    T.check("OPTIMAL_ANGLE_MIN_SEPARATION_DEG > 0", OPTIMAL_ANGLE_MIN_SEPARATION_DEG > 0)

    # =================================================================
    # [Q] 판정 일관성 추적 파라미터 (4종)
    # =================================================================
    T.set_section("[Q] 판정 일관성 추적 파라미터 (4종)")

    T.check("CONSISTENCY_COMPARISON_WINDOW is int",
            isinstance(CONSISTENCY_COMPARISON_WINDOW, int))
    T.check("CONSISTENCY_COMPARISON_WINDOW == 10", CONSISTENCY_COMPARISON_WINDOW == 10)
    T.check("CONSISTENCY_COMPARISON_WINDOW > 0", CONSISTENCY_COMPARISON_WINDOW > 0)

    T.check("CONSISTENCY_DEVIATION_THRESHOLD is float",
            isinstance(CONSISTENCY_DEVIATION_THRESHOLD, float))
    T.check("CONSISTENCY_DEVIATION_THRESHOLD == 0.20",
            abs(CONSISTENCY_DEVIATION_THRESHOLD - 0.20) < 1e-9)
    T.check("CONSISTENCY_DEVIATION_THRESHOLD 범위 0~1",
            0.0 <= CONSISTENCY_DEVIATION_THRESHOLD <= 1.0)

    T.check("CALL_LEVEL_CALIBRATION_EVENTS is int",
            isinstance(CALL_LEVEL_CALIBRATION_EVENTS, int))
    T.check("CALL_LEVEL_CALIBRATION_EVENTS == 15", CALL_LEVEL_CALIBRATION_EVENTS == 15)
    T.check("CALL_LEVEL_CALIBRATION_EVENTS > 0", CALL_LEVEL_CALIBRATION_EVENTS > 0)

    T.check("SEVERITY_BIN_WIDTH is float", isinstance(SEVERITY_BIN_WIDTH, float))
    T.check("SEVERITY_BIN_WIDTH == 0.10", abs(SEVERITY_BIN_WIDTH - 0.10) < 1e-9)
    T.check("SEVERITY_BIN_WIDTH > 0", SEVERITY_BIN_WIDTH > 0)

    # =================================================================
    # [R] 리플레이/챌린지 파라미터 (3종)
    # =================================================================
    T.set_section("[R] 리플레이/챌린지 파라미터 (3종)")

    T.check("REPLAY_MAX_REVIEW_TIME_SEC is int",
            isinstance(REPLAY_MAX_REVIEW_TIME_SEC, int))
    T.check("REPLAY_MAX_REVIEW_TIME_SEC == 120", REPLAY_MAX_REVIEW_TIME_SEC == 120)
    T.check("REPLAY_MAX_REVIEW_TIME_SEC > 0", REPLAY_MAX_REVIEW_TIME_SEC > 0)

    T.check("CHALLENGE_SUCCESS_REFUND is bool",
            isinstance(CHALLENGE_SUCCESS_REFUND, bool))
    T.check("CHALLENGE_SUCCESS_REFUND == True", CHALLENGE_SUCCESS_REFUND is True)

    T.check("CHALLENGE_MIN_REMAINING_SEC is int",
            isinstance(CHALLENGE_MIN_REMAINING_SEC, int))
    T.check("CHALLENGE_MIN_REMAINING_SEC == 0", CHALLENGE_MIN_REMAINING_SEC == 0)
    T.check("CHALLENGE_MIN_REMAINING_SEC >= 0", CHALLENGE_MIN_REMAINING_SEC >= 0)

    # =================================================================
    # [S] classify_decision_confidence 유틸리티 함수
    # =================================================================
    T.set_section("[S] classify_decision_confidence 유틸리티")

    # 경계값 테스트
    T.check("confidence=1.0 -> AUTO_CONFIRM",
            classify_decision_confidence(1.0) == DecisionConfidence.AUTO_CONFIRM)
    T.check("confidence=0.95 -> AUTO_CONFIRM (경계)",
            classify_decision_confidence(0.95) == DecisionConfidence.AUTO_CONFIRM)
    T.check("confidence=0.949 -> HIGH",
            classify_decision_confidence(0.949) == DecisionConfidence.HIGH)
    T.check("confidence=0.90 -> HIGH",
            classify_decision_confidence(0.90) == DecisionConfidence.HIGH)
    T.check("confidence=0.85 -> HIGH (경계)",
            classify_decision_confidence(0.85) == DecisionConfidence.HIGH)
    T.check("confidence=0.849 -> MODERATE",
            classify_decision_confidence(0.849) == DecisionConfidence.MODERATE)
    T.check("confidence=0.75 -> MODERATE",
            classify_decision_confidence(0.75) == DecisionConfidence.MODERATE)
    T.check("confidence=0.70 -> MODERATE (경계)",
            classify_decision_confidence(0.70) == DecisionConfidence.MODERATE)
    T.check("confidence=0.699 -> LOW",
            classify_decision_confidence(0.699) == DecisionConfidence.LOW)
    T.check("confidence=0.50 -> LOW",
            classify_decision_confidence(0.50) == DecisionConfidence.LOW)
    T.check("confidence=0.0 -> LOW",
            classify_decision_confidence(0.0) == DecisionConfidence.LOW)

    # 반환 타입
    T.check("classify_decision_confidence 반환 타입",
            isinstance(classify_decision_confidence(0.80), DecisionConfidence))

    # =================================================================
    # [T] classify_foul_grade 유틸리티 함수
    # =================================================================
    T.set_section("[T] classify_foul_grade 유틸리티")

    # FLAGRANT_2: severity >= 0.85
    T.check("severity=0.90, ball=0.50 -> FLAGRANT_2",
            classify_foul_grade(0.90, 0.50) == FoulGrade.FLAGRANT_2)
    T.check("severity=0.85, ball=0.50 -> FLAGRANT_2 (경계)",
            classify_foul_grade(0.85, 0.50) == FoulGrade.FLAGRANT_2)

    # FLAGRANT_1: severity >= 0.65 (but < 0.85)
    T.check("severity=0.84, ball=0.50 -> FLAGRANT_1",
            classify_foul_grade(0.84, 0.50) == FoulGrade.FLAGRANT_1)
    T.check("severity=0.70, ball=0.50 -> FLAGRANT_1",
            classify_foul_grade(0.70, 0.50) == FoulGrade.FLAGRANT_1)
    T.check("severity=0.65, ball=0.50 -> FLAGRANT_1 (경계)",
            classify_foul_grade(0.65, 0.50) == FoulGrade.FLAGRANT_1)

    # FLAGRANT_1: 볼 관련성 낮음 (ball_relatedness < 0.30)
    T.check("severity=0.30, ball=0.10 -> FLAGRANT_1 (볼 관련성 낮음)",
            classify_foul_grade(0.30, 0.10) == FoulGrade.FLAGRANT_1)
    T.check("severity=0.20, ball=0.29 -> FLAGRANT_1 (볼 관련성 경계 미만)",
            classify_foul_grade(0.20, 0.29) == FoulGrade.FLAGRANT_1)

    # NORMAL: severity < 0.65 AND ball_relatedness >= 0.30
    T.check("severity=0.64, ball=0.50 -> NORMAL",
            classify_foul_grade(0.64, 0.50) == FoulGrade.NORMAL)
    T.check("severity=0.40, ball=0.50 -> NORMAL",
            classify_foul_grade(0.40, 0.50) == FoulGrade.NORMAL)
    T.check("severity=0.20, ball=0.30 -> NORMAL (볼 관련성 경계)",
            classify_foul_grade(0.20, 0.30) == FoulGrade.NORMAL)

    # 반환 타입
    T.check("classify_foul_grade 반환 타입",
            isinstance(classify_foul_grade(0.50, 0.50), FoulGrade))

    # =================================================================
    # [U] is_action_reviewable 유틸리티 함수
    # =================================================================
    T.set_section("[U] is_action_reviewable 유틸리티")

    # 비득점 플레이 (기본): threshold = 0.70
    T.check("confidence=0.60 -> True (일반, < 0.70)",
            is_action_reviewable(0.60) is True)
    T.check("confidence=0.69 -> True (일반, < 0.70)",
            is_action_reviewable(0.69) is True)
    T.check("confidence=0.70 -> False (일반, >= 0.70)",
            is_action_reviewable(0.70) is False)
    T.check("confidence=0.80 -> False (일반, >= 0.70)",
            is_action_reviewable(0.80) is False)

    # 득점 플레이: threshold = 0.85
    T.check("confidence=0.70, scoring=True -> True (득점, < 0.85)",
            is_action_reviewable(0.70, is_scoring_play=True) is True)
    T.check("confidence=0.84, scoring=True -> True (득점, < 0.85)",
            is_action_reviewable(0.84, is_scoring_play=True) is True)
    T.check("confidence=0.85, scoring=True -> False (득점, >= 0.85)",
            is_action_reviewable(0.85, is_scoring_play=True) is False)
    T.check("confidence=0.95, scoring=True -> False (득점, >= 0.85)",
            is_action_reviewable(0.95, is_scoring_play=True) is False)

    # 반환 타입
    T.check("is_action_reviewable 반환 타입",
            isinstance(is_action_reviewable(0.50), bool))

    # 기본 매개변수
    T.check("is_action_reviewable 기본 is_scoring_play=False",
            is_action_reviewable(0.80) == is_action_reviewable(0.80, is_scoring_play=False))

    # =================================================================
    # [V] __all__ Export (55항목)
    # =================================================================
    T.set_section("[V] __all__ Export")

    all_list = referee_decision_constants.__all__
    T.check(f"__all__ 개수 == 55", len(all_list) == 55,
            f"got {len(all_list)}")

    # 모든 항목 존재
    for name in all_list:
        T.check(f"__all__: {name} 존재",
                hasattr(referee_decision_constants, name),
                f"{name} not found")

    # 유일성
    T.check("__all__ 항목 유일성",
            len(all_list) == len(set(all_list)),
            f"중복: {[n for n in all_list if all_list.count(n) > 1]}")

    # 필수 항목 포함 확인
    required_in_all = [
        "__version__",
        "DecisionConfidence", "FoulGrade", "ContactArea",
        "DECISION_AUTO_CONFIRM_THRESHOLD", "DECISION_HIGH_CONFIDENCE_THRESHOLD",
        "DECISION_MODERATE_CONFIDENCE_THRESHOLD", "DECISION_MIN_ACTIONABLE_THRESHOLD",
        "FLAGRANT_1_SEVERITY_SCORE", "FLAGRANT_2_SEVERITY_SCORE",
        "classify_decision_confidence", "classify_foul_grade", "is_action_reviewable",
        "MULTI_ANGLE_MIN_CAMERAS", "MULTI_ANGLE_AGREEMENT_THRESHOLD",
        "CONSISTENCY_COMPARISON_WINDOW", "REPLAY_MAX_REVIEW_TIME_SEC",
    ]
    for name in required_in_all:
        T.check(f"__all__ 필수 항목: {name}", name in all_list, f"{name} not in __all__")

    # =================================================================
    # [W] 메타 정보 (version)
    # =================================================================
    T.set_section("[W] 메타 정보")

    T.check("__version__ == '1.0.0'",
            referee_decision_constants.__version__ == "1.0.0",
            f"got {referee_decision_constants.__version__!r}")

    T.check("__version__ is str",
            isinstance(referee_decision_constants.__version__, str))

    # =================================================================
    # [X] 도메인 일관성 크로스 체크
    # =================================================================
    T.set_section("[X] 도메인 일관성 크로스 체크")

    # FLAGRANT_1 < FLAGRANT_2 (값 기반 심각도 검증)
    T.check("FLAGRANT_1_SEVERITY < FLAGRANT_2_SEVERITY",
            FLAGRANT_1_SEVERITY_SCORE < FLAGRANT_2_SEVERITY_SCORE)

    # classify_foul_grade + FoulGrade.results_in_ejection 일관성
    # FLAGRANT_2 이상이면 퇴장
    f2_grade = classify_foul_grade(0.90, 0.50)
    T.check("FLAGRANT_2 -> results_in_ejection",
            f2_grade.results_in_ejection is True)

    # NORMAL -> 퇴장 아님
    normal_grade = classify_foul_grade(0.40, 0.50)
    T.check("NORMAL -> not results_in_ejection",
            normal_grade.results_in_ejection is False)

    # classify_decision_confidence + requires_human_review 일관성
    auto_dc = classify_decision_confidence(0.96)
    T.check("AUTO_CONFIRM -> not requires_human_review",
            auto_dc.requires_human_review is False)

    low_dc = classify_decision_confidence(0.50)
    T.check("LOW -> requires_human_review",
            low_dc.requires_human_review is True)

    # is_action_reviewable + classify_decision_confidence 연계
    # 신뢰도 0.60 -> LOW -> reviewable
    T.check("신뢰도 0.60: LOW이며 reviewable",
            classify_decision_confidence(0.60) == DecisionConfidence.LOW
            and is_action_reviewable(0.60) is True)

    # 신뢰도 0.90: HIGH이며 not reviewable (일반 플레이)
    T.check("신뢰도 0.90: HIGH이며 not reviewable (일반)",
            classify_decision_confidence(0.90) == DecisionConfidence.HIGH
            and is_action_reviewable(0.90) is False)

    # 신뢰도 0.90: 득점 플레이에서는 not reviewable (>= 0.85)
    T.check("신뢰도 0.90: HIGH이며 not reviewable (득점)",
            is_action_reviewable(0.90, is_scoring_play=True) is False)

    # 신뢰도 0.80: 일반에서는 not reviewable, 득점에서는 reviewable
    T.check("신뢰도 0.80: 일반 not reviewable, 득점 reviewable",
            is_action_reviewable(0.80) is False
            and is_action_reviewable(0.80, is_scoring_play=True) is True)

    # 빈 선언 패턴 없음
    import inspect
    source = inspect.getsource(referee_decision_constants)
    T.check("빈 선언 패턴 없음 (= {})",
            "= {}" not in source)
    T.check("빈 선언 패턴 없음 (= frozenset())",
            "= frozenset()" not in source)

    # === 최종 결과 ===
    success = T.summary()
    return 0 if success else 1


if __name__ == "__main__":
    rc = main()
    sys.exit(rc)
