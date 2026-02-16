# -*- coding: utf-8 -*-
"""player_constants.py v2.0.0 검증 테스트"""

import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0


def check(name, condition, msg=""):
    global passed, failed
    if condition:
        print(f"[PASS] {name}")
        passed += 1
    else:
        print(f"[FAIL] {name} - {msg}")
        failed += 1


print("=" * 70)
print("player_constants.py v2.0.0 검증 테스트")
print("=" * 70)

# =========================================================================
# 파트 1: 모듈 임포트 및 기본 검증
# =========================================================================
# T-01: 모듈 임포트
try:
    from shared.constants.player_constants import (
        Gender, AgeGroup, SkillLevel,
        PLAYER_CLASS_ID_PLAYER,
        PLAYER_CLASS_ID_REFEREE,
        PLAYER_CLASS_ID_COACH,
        PLAYER_CLASS_ID_STAFF,
        PLAYER_CLASS_ID_UNKNOWN,
        PLAYER_CLASS_NAMES,
        TEAM_VALUE_DARK_THRESHOLD,
        TEAM_VALUE_LIGHT_THRESHOLD,
        TEAM_SKIN_HUE_RANGE,
        TEAM_SKIN_SAT_RANGE,
        TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD,
        NORMALIZE_MEAN,
        NORMALIZE_STD,
        CHEST_CROP_Y_START,
        CHEST_CROP_Y_END,
        CHEST_CROP_X_START,
        CHEST_CROP_X_END,
    )
    check("T-01: player_constants 모듈 임포트", True)
except Exception as e:
    check("T-01: player_constants 모듈 임포트", False, str(e))
    sys.exit(1)

# T-02: __init__.py 호환성
try:
    from shared.constants import (
        Gender as _g,
        AgeGroup as _a,
        SkillLevel as _s,
        PLAYER_CLASS_ID_PLAYER as _p1,
        PLAYER_CLASS_NAMES as _p2,
        TEAM_VALUE_DARK_THRESHOLD as _p3,
        TEAM_VALUE_LIGHT_THRESHOLD as _p4,
    )
    check("T-02: __init__.py 호환성", True)
except Exception as e:
    check("T-02: __init__.py 호환성", False, str(e))

# =========================================================================
# 파트 2: Enum 검증 - Gender
# =========================================================================
# T-03: Gender 2 멤버
check(
    "T-03: Gender 2 멤버",
    len(Gender) == 2,
    f"실제: {len(Gender)}",
)

# T-04: Gender str 상속
check(
    "T-04: Gender str 상속",
    isinstance(Gender.MALE, str)
    and str(Gender.MALE) == "male"
    and str(Gender.FEMALE) == "female",
)

# T-05: Gender.to_korean (property)
check(
    "T-05: Gender.to_korean",
    Gender.MALE.to_korean == "남성"
    and Gender.FEMALE.to_korean == "여성",
)

# T-06: Gender.get_name 다국어
from shared.constants.localization import SupportedLanguage
check(
    "T-06: Gender.get_name 다국어",
    Gender.MALE.get_name(SupportedLanguage.EN) == "Male"
    and Gender.FEMALE.get_name(SupportedLanguage.JA) == "女性"
    and all(isinstance(g.get_name(), str) for g in Gender),
)

# =========================================================================
# 파트 3: Enum 검증 - AgeGroup
# =========================================================================
# T-07: AgeGroup 4 멤버
check(
    "T-07: AgeGroup 4 멤버",
    len(AgeGroup) == 4,
    f"실제: {len(AgeGroup)}",
)

# T-08: AgeGroup.age_range
check(
    "T-08: AgeGroup.age_range",
    AgeGroup.YOUTH.age_range == (6, 12)
    and AgeGroup.TEEN.age_range == (13, 18)
    and AgeGroup.ADULT.age_range == (19, 49)
    and AgeGroup.SENIOR.age_range == (50, 99),
)

# T-09: AgeGroup.from_age classmethod
check(
    "T-09: AgeGroup.from_age",
    AgeGroup.from_age(8) == AgeGroup.YOUTH
    and AgeGroup.from_age(15) == AgeGroup.TEEN
    and AgeGroup.from_age(25) == AgeGroup.ADULT
    and AgeGroup.from_age(60) == AgeGroup.SENIOR,
)

# T-10: AgeGroup.recommended_ball_size (FIBA 규정)
check(
    "T-10: AgeGroup.recommended_ball_size",
    AgeGroup.YOUTH.recommended_ball_size == 5
    and AgeGroup.TEEN.recommended_ball_size == 6
    and AgeGroup.ADULT.recommended_ball_size == 7
    and AgeGroup.SENIOR.recommended_ball_size == 7,
)

# T-11: AgeGroup.to_korean
check(
    "T-11: AgeGroup.to_korean",
    AgeGroup.YOUTH.to_korean == "유소년"
    and AgeGroup.TEEN.to_korean == "청소년"
    and AgeGroup.ADULT.to_korean == "성인"
    and AgeGroup.SENIOR.to_korean == "시니어",
)

# =========================================================================
# 파트 4: Enum 검증 - SkillLevel
# =========================================================================
# T-12: SkillLevel 4 멤버
check(
    "T-12: SkillLevel 4 멤버",
    len(SkillLevel) == 4,
    f"실제: {len(SkillLevel)}",
)

# T-13: SkillLevel.numeric_level (1-4)
check(
    "T-13: SkillLevel.numeric_level",
    SkillLevel.BEGINNER.numeric_level == 1
    and SkillLevel.INTERMEDIATE.numeric_level == 2
    and SkillLevel.ADVANCED.numeric_level == 3
    and SkillLevel.PROFESSIONAL.numeric_level == 4,
)

# T-14: SkillLevel.feedback_complexity
check(
    "T-14: SkillLevel.feedback_complexity",
    SkillLevel.BEGINNER.feedback_complexity == "simple"
    and SkillLevel.INTERMEDIATE.feedback_complexity == "detailed"
    and SkillLevel.ADVANCED.feedback_complexity == "technical"
    and SkillLevel.PROFESSIONAL.feedback_complexity == "expert",
)

# T-15: SkillLevel.tolerance_factor (초보 > 프로)
check(
    "T-15: SkillLevel.tolerance_factor",
    abs(SkillLevel.BEGINNER.tolerance_factor - 1.3) < 1e-9
    and abs(SkillLevel.INTERMEDIATE.tolerance_factor - 1.1) < 1e-9
    and abs(SkillLevel.ADVANCED.tolerance_factor - 0.95) < 1e-9
    and abs(SkillLevel.PROFESSIONAL.tolerance_factor - 0.8) < 1e-9,
)

# T-16: SkillLevel.to_korean
check(
    "T-16: SkillLevel.to_korean",
    SkillLevel.BEGINNER.to_korean == "초보"
    and SkillLevel.INTERMEDIATE.to_korean == "중급"
    and SkillLevel.ADVANCED.to_korean == "상급"
    and SkillLevel.PROFESSIONAL.to_korean == "프로",
)

# =========================================================================
# 파트 5: 일반 상수 값 검증
# =========================================================================
# T-17: YOLO 클래스 ID 값
check(
    "T-17: YOLO 클래스 ID 값",
    PLAYER_CLASS_ID_PLAYER == 0
    and PLAYER_CLASS_ID_REFEREE == 1
    and PLAYER_CLASS_ID_COACH == 2
    and PLAYER_CLASS_ID_STAFF == 3
    and PLAYER_CLASS_ID_UNKNOWN == 4,
)

# T-18: PLAYER_CLASS_NAMES 완전성
check(
    "T-18: PLAYER_CLASS_NAMES 완전성",
    len(PLAYER_CLASS_NAMES) == 5
    and PLAYER_CLASS_NAMES[0] == "player"
    and PLAYER_CLASS_NAMES[1] == "referee"
    and PLAYER_CLASS_NAMES[2] == "coach"
    and PLAYER_CLASS_NAMES[3] == "staff"
    and PLAYER_CLASS_NAMES[4] == "unknown",
)

# T-19: 팀 분류 밝기 임계값
check(
    "T-19: 팀 분류 밝기 임계값",
    abs(TEAM_VALUE_DARK_THRESHOLD - 125.0) < 1e-9
    and abs(TEAM_VALUE_LIGHT_THRESHOLD - 140.0) < 1e-9
    and TEAM_VALUE_DARK_THRESHOLD < TEAM_VALUE_LIGHT_THRESHOLD,
)

# T-20: 피부색 HSV 범위
check(
    "T-20: 피부색 HSV 범위",
    TEAM_SKIN_HUE_RANGE == (0, 25)
    and TEAM_SKIN_SAT_RANGE == (40, 170),
)

# T-21: 딥러닝 신뢰도 임계값
check(
    "T-21: 딥러닝 신뢰도 임계값",
    abs(TEAM_CLASSIFICATION_CONFIDENCE_THRESHOLD - 0.7) < 1e-9,
)

# T-22: ImageNet 정규화 값
check(
    "T-22: ImageNet 정규화 값",
    abs(NORMALIZE_MEAN[0] - 0.485) < 1e-6
    and abs(NORMALIZE_MEAN[1] - 0.456) < 1e-6
    and abs(NORMALIZE_MEAN[2] - 0.406) < 1e-6
    and abs(NORMALIZE_STD[0] - 0.229) < 1e-6
    and abs(NORMALIZE_STD[1] - 0.224) < 1e-6
    and abs(NORMALIZE_STD[2] - 0.225) < 1e-6,
)

# T-23: 가슴 크롭 비율
check(
    "T-23: 가슴 크롭 비율",
    abs(CHEST_CROP_Y_START - 0.15) < 1e-9
    and abs(CHEST_CROP_Y_END - 0.55) < 1e-9
    and abs(CHEST_CROP_X_START - 0.30) < 1e-9
    and abs(CHEST_CROP_X_END - 0.70) < 1e-9,
)

# =========================================================================
# 파트 6: 메타 검증
# =========================================================================
# T-24: __all__ 개수 및 존재 확인
import shared.constants.player_constants as pc
all_list = pc.__all__
all_exist = all(hasattr(pc, name) for name in all_list)
check(
    f"T-24: __all__ {len(all_list)}개 항목 모두 존재",
    len(all_list) == 20 and all_exist,
    f"개수: {len(all_list)}, 존재: {all_exist}",
)

# T-25: .update() 패턴 부재
import inspect
source = inspect.getsource(pc)
check(
    "T-25: .update() 및 빈 선언 패턴 없음",
    ".update(" not in source
    and "= {}" not in source
    and "= frozenset()" not in source,
)

# T-26: typing 모더나이제이션 검증
check(
    "T-26: typing 모더나이제이션 (Dict/List/Tuple 미사용)",
    "Dict[" not in source
    and "List[" not in source
    and "Tuple[" not in source,
)

# T-27: 버전 검증
check("T-27: 버전 2.0.0", pc.__version__ == "2.0.0", f"실제: {pc.__version__}")

# =========================================================================
# 파트 7: 정적 분석 - old name 잔존 여부
# =========================================================================
print()
print("=" * 70)
print("player_detection 모듈 정적 분석 (old name 잔존 검증)")
print("=" * 70)

# old name 패턴 정의
OLD_NAMES = [
    "YOLO_CLASS_PLAYER",
    "YOLO_CLASS_REFEREE",
    "YOLO_CLASS_COACH",
    "YOLO_CLASS_STAFF",
    "YOLO_CLASS_UNKNOWN",
    "YOLO_CLASS_NAMES",
]

TEAM_OLD_NAMES = [
    "VALUE_DARK_THRESHOLD",
    "VALUE_LIGHT_THRESHOLD",
    "HSV_SKIN_HUE_RANGE",
    "HSV_SKIN_SAT_RANGE",
    "DEFAULT_CONFIDENCE_THRESHOLD",
]

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "detection", "player_detection")

files_to_check = ["models.py", "player_detector.py", "team_classifier.py"]

for fname in files_to_check:
    fpath = os.path.join(BASE_DIR, fname)
    if not os.path.exists(fpath):
        check(f"T-S: {fname} 파일 존재", False, "파일 없음")
        continue

    with open(fpath, "r", encoding="utf-8") as f:
        source = f.read()

    # import 문과 주석 제외한 줄에서 old name 검색
    found_old = []
    for line_num, line in enumerate(source.split("\n"), 1):
        stripped = line.strip()
        # import 문, 주석, 문자열 리터럴은 건너뛰기
        if stripped.startswith(("#", "from ", "import ", '"', "'")):
            continue

        for old_name in OLD_NAMES:
            # 정확한 단어 매칭 (PLAYER_CLASS_ID_PLAYER에 포함된 것 제외)
            pattern = r'\b' + re.escape(old_name) + r'\b'
            if re.search(pattern, line):
                found_old.append(f"  L{line_num}: {old_name}")

    check(
        f"T-S-{fname}: old YOLO_CLASS_* 이름 없음",
        len(found_old) == 0,
        f"\n" + "\n".join(found_old) if found_old else "",
    )

# team_classifier.py 전용: 로컬 상수 정의 잔존 확인
tc_path = os.path.join(BASE_DIR, "team_classifier.py")
if os.path.exists(tc_path):
    with open(tc_path, "r", encoding="utf-8") as f:
        tc_source = f.read()

    # 로컬 정의가 남아있으면 안 됨
    local_defs_found = []
    for old in TEAM_OLD_NAMES:
        # "변수명 = 값" 형태의 로컬 정의 검색
        pattern = r'^' + re.escape(old) + r'\s*='
        for line_num, line in enumerate(tc_source.split("\n"), 1):
            if re.match(pattern, line.strip()):
                local_defs_found.append(f"  L{line_num}: {old}")

    check(
        "T-S-team_classifier.py: 로컬 상수 정의 제거됨",
        len(local_defs_found) == 0,
        f"\n" + "\n".join(local_defs_found) if local_defs_found else "",
    )

    # player_constants import 존재 확인
    check(
        "T-S-team_classifier.py: player_constants import 존재",
        "from shared.constants.player_constants import" in tc_source,
    )

# player_detector.py 전용: player_constants import 확인
pd_path = os.path.join(BASE_DIR, "player_detector.py")
if os.path.exists(pd_path):
    with open(pd_path, "r", encoding="utf-8") as f:
        pd_source = f.read()

    check(
        "T-S-player_detector.py: player_constants import 존재",
        "from shared.constants.player_constants import" in pd_source,
    )

# models.py 전용: player_constants import 확인
m_path = os.path.join(BASE_DIR, "models.py")
if os.path.exists(m_path):
    with open(m_path, "r", encoding="utf-8") as f:
        m_source = f.read()

    check(
        "T-S-models.py: player_constants import 존재",
        "from shared.constants.player_constants import" in m_source,
    )

    # 로컬 YOLO 정의가 없는지 확인
    local_yolo_defs = []
    for line_num, line in enumerate(m_source.split("\n"), 1):
        for old in OLD_NAMES:
            pattern = r'^' + re.escape(old) + r'\s*[:=]'
            if re.match(pattern, line.strip()):
                local_yolo_defs.append(f"  L{line_num}: {old}")

    check(
        "T-S-models.py: 로컬 YOLO_CLASS 정의 제거됨",
        len(local_yolo_defs) == 0,
        f"\n" + "\n".join(local_yolo_defs) if local_yolo_defs else "",
    )


print()
print("=" * 70)
print(f"결과: {passed}/{passed + failed} PASS | {failed} FAIL")
print("=" * 70)

if failed > 0:
    sys.exit(1)
