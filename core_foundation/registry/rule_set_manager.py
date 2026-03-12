# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: rule_set_manager.py
버전: 1.0.0
설명: 7개 리그 규칙 세트 로딩/캐싱 - FIBA, NBA, KBL, NBL, NCAA, B.League, PBA 심판 규정 관리

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-12

주요 기능:
    - 7개 리그 규칙 세트 관리 (FIBA, NBA, KBL, NBL, NCAA, B.League, PBA)
    - YAML 기반 규칙 세트 로딩
    - TTL 기반 규칙 세트 캐싱 (Dict + 시간 만료)
    - 규칙 세트 버전 관리
    - 리그 간 규칙 상속 (FIBA → 하위 리그)
    - 자체 규칙 세트 검증 로직

설계 원칙:
    - DI 패턴: ConfigLoader 주입
    - 스레드 안전: RLock 기반 동기화
    - 캐시 TTL: 기본 1시간, 설정 가능
    - 지연 로딩: 필요 시 규칙 세트 로드

사용 예시:
    # DI 컨테이너에서 주입받아 사용
    manager = RuleSetManager(config_loader)

    # 규칙 세트 로드
    fiba_rules = manager.get_rule_set(League.FIBA)
    nba_rules = manager.get_rule_set(League.NBA)

    # 특정 규칙 조회
    rule = manager.get_rule(League.NBA, "traveling")

    # 카테고리별 규칙 조회
    fouls = manager.get_rules_by_category(League.FIBA, RuleCategory.FOUL)
"""

from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# ============================================================
# 서드파티
# ============================================================
import yaml

# ============================================================
# shared 임포트
# ============================================================
from shared.exceptions.validation_exceptions import (
    RuleSetNotFoundException,
    RuleSetValidationException,
)

# ============================================================
# core_foundation 내부 임포트 (DI)
# ============================================================
from core_foundation.config import ConfigLoader

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)


# ============================================================
# Enum 정의
# ============================================================
class League(Enum):
    """
    리그 타입.

    지원하는 7개 농구 리그입니다.

    Attributes:
        FIBA: 국제농구연맹 (기본 규칙, 다른 리그의 기반)
        NBA: 미국 프로농구
        KBL: 한국프로농구
        NBL: 호주프로농구
        NCAA: 미국 대학농구
        B_LEAGUE: 일본 B.리그
        PBA: 필리핀프로농구
    """

    FIBA = "fiba"
    NBA = "nba"
    KBL = "kbl"
    NBL = "nbl"
    NCAA = "ncaa"
    B_LEAGUE = "b_league"
    PBA = "pba"

    @property
    def display_name(self) -> str:
        """표시명 반환."""
        names = {
            self.FIBA: "FIBA (국제농구연맹)",
            self.NBA: "NBA (미국 프로농구)",
            self.KBL: "KBL (한국프로농구)",
            self.NBL: "NBL (호주프로농구)",
            self.NCAA: "NCAA (미국 대학농구)",
            self.B_LEAGUE: "B.League (일본 프로농구)",
            self.PBA: "PBA (필리핀프로농구)",
        }
        return names.get(self, self.value)

    @property
    def country(self) -> str:
        """소속 국가/지역."""
        countries = {
            self.FIBA: "International",
            self.NBA: "USA",
            self.KBL: "South Korea",
            self.NBL: "Australia",
            self.NCAA: "USA",
            self.B_LEAGUE: "Japan",
            self.PBA: "Philippines",
        }
        return countries.get(self, "Unknown")


class RuleCategory(Enum):
    """
    규칙 카테고리.

    농구 규칙의 주요 분류입니다.
    """

    VIOLATION = "violation"      # 바이올레이션 (트래블링, 더블드리블 등)
    FOUL = "foul"                # 파울 (개인파울, 테크니컬 등)
    TIMING = "timing"            # 시간 규칙 (쿼터, 샷클락 등)
    COURT = "court"              # 코트 규정 (라인, 구역 등)
    EQUIPMENT = "equipment"      # 장비 규정 (공, 골대 등)
    SCORING = "scoring"          # 득점 규정 (2점, 3점, 자유투)
    SUBSTITUTION = "substitution"  # 교체 규정
    OUT_OF_BOUNDS = "out_of_bounds"  # 아웃 오브 바운즈

    @property
    def display_name(self) -> str:
        """표시명 반환."""
        names = {
            self.VIOLATION: "바이올레이션",
            self.FOUL: "파울",
            self.TIMING: "시간 규칙",
            self.COURT: "코트 규정",
            self.EQUIPMENT: "장비 규정",
            self.SCORING: "득점 규정",
            self.SUBSTITUTION: "교체 규정",
            self.OUT_OF_BOUNDS: "아웃 오브 바운즈",
        }
        return names.get(self, self.value)


class RuleSeverity(Enum):
    """
    규칙 심각도.

    규칙 위반 시 심각도 수준입니다.
    """

    MINOR = "minor"                  # 경미한 위반
    MODERATE = "moderate"            # 보통 위반
    SEVERE = "severe"                # 심각한 위반
    DISQUALIFYING = "disqualifying"  # 퇴장 수준

    @property
    def penalty_weight(self) -> float:
        """페널티 가중치."""
        weights = {
            self.MINOR: 0.25,
            self.MODERATE: 0.5,
            self.SEVERE: 0.75,
            self.DISQUALIFYING: 1.0,
        }
        return weights.get(self, 0.5)


# ============================================================
# 상수 정의
# ============================================================
# 지원 리그 목록 (불변)
SUPPORTED_LEAGUES: frozenset[str] = frozenset({
    League.FIBA.value,
    League.NBA.value,
    League.KBL.value,
    League.NBL.value,
    League.NCAA.value,
    League.B_LEAGUE.value,
    League.PBA.value,
})

# 기본 규칙 세트 경로 (프로젝트 루트 기준)
DEFAULT_RULE_SET_PATH: Path = Path("configs/rules")

# 규칙 세트 스키마 버전
RULE_SET_SCHEMA_VERSION: str = "v1.0.0"

# 캐시 TTL (초) - 기본 1시간
DEFAULT_CACHE_TTL: int = 3600

# 최대 캐시 크기 (규칙 세트 수)
MAX_CACHE_SIZE: int = 50

# 규칙 우선순위 가중치 (높을수록 우선)
RULE_PRIORITY_WEIGHTS: dict[str, float] = {
    "safety": 1.0,       # 안전 관련 규칙 최우선
    "scoring": 0.9,      # 득점 관련
    "timing": 0.8,       # 시간 관련
    "foul": 0.7,         # 파울 관련
    "violation": 0.6,    # 바이올레이션
    "court": 0.5,        # 코트 규정
    "equipment": 0.4,    # 장비 규정
    "default": 0.5,      # 기본값
}

# 리그 상속 계층 (FIBA가 기본, 각 리그는 FIBA를 상속)
LEAGUE_HIERARCHY: dict[str, list[str]] = {
    League.FIBA.value: [],  # FIBA는 최상위
    League.NBA.value: [League.FIBA.value],
    League.KBL.value: [League.FIBA.value],
    League.NBL.value: [League.FIBA.value],
    League.NCAA.value: [League.FIBA.value],
    League.B_LEAGUE.value: [League.FIBA.value],
    League.PBA.value: [League.FIBA.value],
}

# 폴백 리그 (규칙을 찾지 못할 때 참조)
DEFAULT_FALLBACK_LEAGUE: str = League.FIBA.value

# 리그별 기본 설정값
# 쿼터 시간 (초)
QUARTER_DURATION: dict[League, int] = {
    League.FIBA: 600,      # 10분
    League.NBA: 720,       # 12분
    League.KBL: 600,       # 10분
    League.NBL: 600,       # 10분
    League.NCAA: 1200,     # 20분 (전후반제)
    League.B_LEAGUE: 600,  # 10분
    League.PBA: 720,       # 12분
}

# 샷클락 (초)
SHOT_CLOCK: dict[League, int] = {
    League.FIBA: 24,
    League.NBA: 24,
    League.KBL: 24,
    League.NBL: 24,
    League.NCAA: 30,       # 남녀 모두 30초
    League.B_LEAGUE: 24,
    League.PBA: 24,
}

# 3점 라인 거리 (cm)
THREE_POINT_DISTANCE: dict[League, int] = {
    League.FIBA: 675,      # 6.75m (코너 6.6m)
    League.NBA: 723,       # 7.24m (코너 6.7m)
    League.KBL: 675,       # FIBA 기준
    League.NBL: 675,       # FIBA 기준
    League.NCAA: 675,      # FIBA 기준 채택
    League.B_LEAGUE: 675,  # FIBA 기준
    League.PBA: 675,       # FIBA 기준
}

# 개인 파울 퇴장 기준
PERSONAL_FOUL_LIMIT: dict[League, int] = {
    League.FIBA: 5,
    League.NBA: 6,
    League.KBL: 5,
    League.NBL: 5,
    League.NCAA: 5,
    League.B_LEAGUE: 5,
    League.PBA: 6,
}


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass(slots=True)
class RuleCondition:
    """
    규칙 조건.

    규칙이 적용되는 조건을 정의합니다.

    Attributes:
        condition_type: 조건 타입 (time, distance, count 등)
        parameters: 조건 파라미터
        threshold: 임계값
        comparison: 비교 연산자 (gt, lt, eq, gte, lte)
    """

    condition_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    threshold: float | None = None
    comparison: str = "eq"

    def evaluate(self, value: Any) -> bool:
        """
        조건 평가.

        Args:
            value: 평가할 값

        Returns:
            조건 충족 여부
        """
        if self.threshold is None:
            return True

        try:
            numeric_value = float(value)
            if self.comparison == "gt":
                return numeric_value > self.threshold
            elif self.comparison == "lt":
                return numeric_value < self.threshold
            elif self.comparison == "gte":
                return numeric_value >= self.threshold
            elif self.comparison == "lte":
                return numeric_value <= self.threshold
            elif self.comparison == "eq":
                return abs(numeric_value - self.threshold) < 1e-6
            else:
                return False
        except (TypeError, ValueError):
            return False


@dataclass(slots=True)
class Penalty:
    """
    패널티 정의.

    규칙 위반 시 적용되는 패널티입니다.

    Attributes:
        penalty_type: 패널티 타입 (turnover, free_throw, technical 등)
        description: 패널티 설명
        duration: 시간 패널티 (초, 해당 시)
        count: 자유투 횟수 등
        escalation: 에스컬레이션 규칙 (반복 위반 시)
    """

    penalty_type: str
    description: str
    duration: int | None = None
    count: int | None = None
    escalation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환."""
        result = {
            "penalty_type": self.penalty_type,
            "description": self.description,
        }
        if self.duration is not None:
            result["duration"] = self.duration
        if self.count is not None:
            result["count"] = self.count
        if self.escalation:
            result["escalation"] = self.escalation
        return result


@dataclass(slots=True)
class Rule:
    """
    개별 규칙.

    농구 경기 규칙의 단위입니다.

    Attributes:
        rule_id: 규칙 고유 ID
        name: 규칙 이름
        category: 규칙 카테고리
        severity: 심각도
        description: 규칙 설명
        conditions: 적용 조건 목록
        penalties: 패널티 목록
        league_specific: 리그별 특수 규정
        references: 참조 문서/조항
        effective_date: 시행일
        expiry_date: 만료일 (None이면 무기한)
    """

    rule_id: str
    name: str
    category: RuleCategory
    severity: RuleSeverity
    description: str
    conditions: list[RuleCondition] = field(default_factory=list)
    penalties: list[Penalty] = field(default_factory=list)
    league_specific: dict[str, Any] = field(default_factory=dict)
    references: list[str] = field(default_factory=list)
    effective_date: datetime | None = None
    expiry_date: datetime | None = None

    def is_active(self, check_date: datetime | None = None) -> bool:
        """
        규칙 활성 여부 확인.

        Args:
            check_date: 확인 날짜 (None이면 현재)

        Returns:
            활성 여부
        """
        now = check_date or datetime.now(timezone.utc)

        if self.effective_date and now < self.effective_date:
            return False
        if self.expiry_date and now > self.expiry_date:
            return False
        return True

    def get_priority(self) -> float:
        """규칙 우선순위 반환."""
        category_weight = RULE_PRIORITY_WEIGHTS.get(
            self.category.value,
            RULE_PRIORITY_WEIGHTS["default"]
        )
        severity_weight = self.severity.penalty_weight
        return category_weight * severity_weight

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "conditions": [
                {
                    "type": c.condition_type,
                    "parameters": c.parameters,
                    "threshold": c.threshold,
                    "comparison": c.comparison,
                }
                for c in self.conditions
            ],
            "penalties": [p.to_dict() for p in self.penalties],
            "league_specific": self.league_specific,
            "references": self.references,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
        }


@dataclass(slots=True)
class RuleSetMetadata:
    """
    규칙 세트 메타데이터.

    로드된 규칙 세트의 부가 정보입니다.

    Attributes:
        content_hash: 규칙 세트 내용 해시
        loaded_at: 로드 시간
        source_path: 소스 파일 경로
        file_modified_at: 파일 수정 시간
    """

    content_hash: str
    loaded_at: datetime
    source_path: Path | None = None
    file_modified_at: datetime | None = None

    def is_stale(self, ttl_seconds: int) -> bool:
        """
        캐시 만료 여부 확인.

        Args:
            ttl_seconds: TTL (초)

        Returns:
            만료 여부
        """
        elapsed = (datetime.now(timezone.utc) - self.loaded_at).total_seconds()
        return elapsed > ttl_seconds


@dataclass(slots=True)
class RuleSet:
    """
    규칙 세트.

    리그별 규칙 모음입니다.

    Attributes:
        league: 리그
        version: 버전
        rules: 규칙 목록
        metadata: 메타데이터
        effective_date: 시행일
        expiry_date: 만료일
        parent_league: 상속받는 리그 (있는 경우)
    """

    league: League
    version: str
    rules: list[Rule]
    metadata: RuleSetMetadata | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    parent_league: League | None = None

    def get_rule(self, rule_id: str) -> Rule | None:
        """
        ID로 규칙 조회.

        Args:
            rule_id: 규칙 ID

        Returns:
            규칙 (없으면 None)
        """
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    def get_rules_by_category(self, category: RuleCategory) -> list[Rule]:
        """
        카테고리별 규칙 조회.

        Args:
            category: 규칙 카테고리

        Returns:
            해당 카테고리의 규칙 목록
        """
        return [r for r in self.rules if r.category == category]

    def get_active_rules(self, check_date: datetime | None = None) -> list[Rule]:
        """
        활성 규칙만 조회.

        Args:
            check_date: 확인 날짜

        Returns:
            활성 규칙 목록
        """
        return [r for r in self.rules if r.is_active(check_date)]

    @property
    def rule_count(self) -> int:
        """규칙 수."""
        return len(self.rules)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환."""
        return {
            "league": self.league.value,
            "version": self.version,
            "rule_count": self.rule_count,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "parent_league": self.parent_league.value if self.parent_league else None,
            "rules": [r.to_dict() for r in self.rules],
        }


@dataclass(slots=True)
class LeagueConfig:
    """
    리그별 설정.

    리그의 기본 설정값입니다.

    Attributes:
        league: 리그
        quarter_duration: 쿼터 시간 (초)
        shot_clock: 샷클락 (초)
        three_point_distance: 3점 라인 거리 (cm)
        personal_foul_limit: 개인 파울 퇴장 기준
        court_width: 코트 너비 (cm)
        court_length: 코트 길이 (cm)
        hoop_height: 골대 높이 (cm)
        ball_size: 공 크기 (호)
        overtime_duration: 연장전 시간 (초)
    """

    league: League
    quarter_duration: int
    shot_clock: int
    three_point_distance: int
    personal_foul_limit: int
    court_width: int = 1500    # 15m
    court_length: int = 2800   # 28m
    hoop_height: int = 305     # 3.05m
    ball_size: int = 7         # 7호 (남자), 6호 (여자)
    overtime_duration: int = 300  # 5분

    @classmethod
    def for_league(cls, league: League) -> "LeagueConfig":
        """
        리그 설정 생성.

        Args:
            league: 리그

        Returns:
            리그 설정
        """
        return cls(
            league=league,
            quarter_duration=QUARTER_DURATION.get(league, 600),
            shot_clock=SHOT_CLOCK.get(league, 24),
            three_point_distance=THREE_POINT_DISTANCE.get(league, 675),
            personal_foul_limit=PERSONAL_FOUL_LIMIT.get(league, 5),
        )


# ============================================================
# Protocol 정의
# ============================================================
@runtime_checkable
class RuleSetLoaderProtocol(Protocol):
    """
    규칙 세트 로더 프로토콜.

    규칙 세트 로딩을 위한 인터페이스입니다.
    """

    def load(self, league: League, version: str | None = None) -> RuleSet:
        """규칙 세트 로드."""
        ...

    def validate(self, rule_set: RuleSet) -> bool:
        """규칙 세트 검증."""
        ...

    def get_version(self, league: League) -> str:
        """최신 버전 조회."""
        ...


# ============================================================
# 메인 클래스
# ============================================================
class RuleSetManager:
    """
    규칙 세트 매니저.

    7개 리그의 규칙 세트를 관리합니다.
    DI 패턴으로 ConfigLoader를 주입받습니다.

    Attributes:
        _config_loader: 설정 로더
        _cache: 규칙 세트 캐시
        _lock: 스레드 잠금
        _cache_ttl: 캐시 TTL
        _rule_set_path: 규칙 세트 경로
    """

    def __init__(
        self,
        config_loader: ConfigLoader,
        rule_set_path: Path | None = None,
        cache_ttl: int | None = None,
    ) -> None:
        """
        규칙 세트 매니저 초기화.

        Args:
            config_loader: 설정 로더 (DI 주입)
            rule_set_path: 규칙 세트 경로 (None이면 기본값)
            cache_ttl: 캐시 TTL (초, None이면 설정에서 로드)
        """
        self._config_loader = config_loader
        self._lock = threading.RLock()
        self._cache: dict[str, RuleSet] = {}

        # 설정에서 값 로드
        registry_config = config_loader.get("registry", {})
        rule_set_config = registry_config.get("rule_set_manager", {})

        self._rule_set_path = rule_set_path or Path(
            rule_set_config.get("path", str(DEFAULT_RULE_SET_PATH))
        )
        self._cache_ttl = cache_ttl or rule_set_config.get(
            "cache_ttl", DEFAULT_CACHE_TTL
        )

        # 내장 규칙 초기화
        self._builtin_rules: dict[League, list[Rule]] = {}
        self._initialize_builtin_rules()

        logger.info(
            "RuleSetManager 초기화 완료",
            extra={
                "rule_set_path": str(self._rule_set_path),
                "cache_ttl": self._cache_ttl,
                "supported_leagues": list(SUPPORTED_LEAGUES),
            },
        )

    def __repr__(self) -> str:
        """RuleSetManager 인스턴스 표현."""
        with self._lock:
            cached = len(self._cache)
            builtin = sum(len(r) for r in self._builtin_rules.values())
        return (
            f"RuleSetManager(cached={cached}, "
            f"builtin_rules={builtin}, "
            f"cache_ttl={self._cache_ttl}s)"
        )

    def _initialize_builtin_rules(self) -> None:
        """내장 규칙 초기화."""
        # 각 리그별 기본 규칙 생성
        for league in League:
            self._builtin_rules[league] = self._create_builtin_rules(league)

    def _create_builtin_rules(self, league: League) -> list[Rule]:
        """
        리그별 내장 규칙 생성.

        Args:
            league: 리그

        Returns:
            내장 규칙 목록
        """
        rules: list[Rule] = []

        # === 바이올레이션 규칙 ===
        # 트래블링
        rules.append(Rule(
            rule_id=f"{league.value}_traveling",
            name="트래블링",
            category=RuleCategory.VIOLATION,
            severity=RuleSeverity.MINOR,
            description="공을 소유한 상태에서 피벗 풋을 이동하거나, 드리블 없이 3보 이상 이동",
            conditions=[
                RuleCondition(
                    condition_type="steps_without_dribble",
                    threshold=3.0,
                    comparison="gte",
                ),
            ],
            penalties=[
                Penalty(
                    penalty_type="turnover",
                    description="공격권 상실",
                ),
            ],
            references=["FIBA Rule 25"],
        ))

        # 더블 드리블
        rules.append(Rule(
            rule_id=f"{league.value}_double_dribble",
            name="더블 드리블",
            category=RuleCategory.VIOLATION,
            severity=RuleSeverity.MINOR,
            description="드리블을 중단한 후 다시 드리블을 시작",
            penalties=[
                Penalty(
                    penalty_type="turnover",
                    description="공격권 상실",
                ),
            ],
            references=["FIBA Rule 24"],
        ))

        # 캐리 (팔미핑)
        rules.append(Rule(
            rule_id=f"{league.value}_carrying",
            name="캐리 (팔미핑)",
            category=RuleCategory.VIOLATION,
            severity=RuleSeverity.MINOR,
            description="드리블 중 손바닥이 공 아래로 들어가 잠시 멈추는 행위",
            penalties=[
                Penalty(
                    penalty_type="turnover",
                    description="공격권 상실",
                ),
            ],
            references=["FIBA Rule 24.1.2"],
        ))

        # 킥볼
        rules.append(Rule(
            rule_id=f"{league.value}_kicked_ball",
            name="킥볼",
            category=RuleCategory.VIOLATION,
            severity=RuleSeverity.MINOR,
            description="의도적으로 다리나 발로 공을 차거나 막는 행위",
            penalties=[
                Penalty(
                    penalty_type="violation",
                    description="상대팀 스로인",
                ),
            ],
            references=["FIBA Rule 23"],
        ))

        # 샷클락 바이올레이션
        shot_clock = SHOT_CLOCK.get(league, 24)
        rules.append(Rule(
            rule_id=f"{league.value}_shot_clock_violation",
            name="샷클락 바이올레이션",
            category=RuleCategory.TIMING,
            severity=RuleSeverity.MINOR,
            description=f"{shot_clock}초 내에 슛을 시도하지 않음",
            conditions=[
                RuleCondition(
                    condition_type="shot_clock_expired",
                    threshold=float(shot_clock),
                    comparison="gte",
                ),
            ],
            penalties=[
                Penalty(
                    penalty_type="turnover",
                    description="공격권 상실",
                ),
            ],
            league_specific={"shot_clock_seconds": shot_clock},
            references=["FIBA Rule 29"],
        ))

        # 백코트 바이올레이션 (8초 룰)
        backcourt_time = 8 if league != League.NCAA else 10
        rules.append(Rule(
            rule_id=f"{league.value}_backcourt_violation",
            name="백코트 바이올레이션",
            category=RuleCategory.TIMING,
            severity=RuleSeverity.MINOR,
            description=f"공격 시작 후 {backcourt_time}초 내에 프론트코트로 공을 넘기지 않음",
            conditions=[
                RuleCondition(
                    condition_type="backcourt_time",
                    threshold=float(backcourt_time),
                    comparison="gte",
                ),
            ],
            penalties=[
                Penalty(
                    penalty_type="turnover",
                    description="공격권 상실",
                ),
            ],
            league_specific={"backcourt_seconds": backcourt_time},
            references=["FIBA Rule 28"],
        ))

        # 3초 룰
        rules.append(Rule(
            rule_id=f"{league.value}_three_second_violation",
            name="3초 바이올레이션",
            category=RuleCategory.TIMING,
            severity=RuleSeverity.MINOR,
            description="공격 시 페인트 구역에 3초 이상 머무름",
            conditions=[
                RuleCondition(
                    condition_type="paint_time",
                    threshold=3.0,
                    comparison="gte",
                ),
            ],
            penalties=[
                Penalty(
                    penalty_type="turnover",
                    description="공격권 상실",
                ),
            ],
            references=["FIBA Rule 26"],
        ))

        # 5초 인바운드
        rules.append(Rule(
            rule_id=f"{league.value}_five_second_inbound",
            name="5초 인바운드 바이올레이션",
            category=RuleCategory.TIMING,
            severity=RuleSeverity.MINOR,
            description="스로인 시 5초 내에 패스하지 않음",
            conditions=[
                RuleCondition(
                    condition_type="inbound_time",
                    threshold=5.0,
                    comparison="gte",
                ),
            ],
            penalties=[
                Penalty(
                    penalty_type="turnover",
                    description="공격권 상실",
                ),
            ],
            references=["FIBA Rule 17"],
        ))

        # === 파울 규칙 ===
        # 개인 파울
        foul_limit = PERSONAL_FOUL_LIMIT.get(league, 5)
        rules.append(Rule(
            rule_id=f"{league.value}_personal_foul",
            name="개인 파울",
            category=RuleCategory.FOUL,
            severity=RuleSeverity.MODERATE,
            description="상대 선수에 대한 불법적인 신체 접촉",
            penalties=[
                Penalty(
                    penalty_type="foul",
                    description="파울 기록",
                    escalation={
                        "limit": foul_limit,
                        "action": "disqualification",
                    },
                ),
            ],
            league_specific={"foul_limit": foul_limit},
            references=["FIBA Rule 33"],
        ))

        # 슈팅 파울
        rules.append(Rule(
            rule_id=f"{league.value}_shooting_foul",
            name="슈팅 파울",
            category=RuleCategory.FOUL,
            severity=RuleSeverity.MODERATE,
            description="슛 동작 중인 선수에 대한 파울",
            penalties=[
                Penalty(
                    penalty_type="free_throw",
                    description="자유투 2회 또는 3회",
                    count=2,
                ),
            ],
            references=["FIBA Rule 43"],
        ))

        # 테크니컬 파울
        rules.append(Rule(
            rule_id=f"{league.value}_technical_foul",
            name="테크니컬 파울",
            category=RuleCategory.FOUL,
            severity=RuleSeverity.SEVERE,
            description="스포츠맨십에 위배되는 행위, 심판에 대한 항의 등",
            penalties=[
                Penalty(
                    penalty_type="technical",
                    description="자유투 1회 + 공격권",
                    count=1,
                    escalation={
                        "second_offense": "ejection",
                    },
                ),
            ],
            references=["FIBA Rule 36"],
        ))

        # 플래그런트 파울 (언스포츠맨라이크)
        rules.append(Rule(
            rule_id=f"{league.value}_flagrant_foul",
            name="플래그런트 파울" if league == League.NBA else "언스포츠맨라이크 파울",
            category=RuleCategory.FOUL,
            severity=RuleSeverity.SEVERE,
            description="과도한 신체 접촉이나 위험한 플레이",
            penalties=[
                Penalty(
                    penalty_type="flagrant",
                    description="자유투 2회 + 공격권",
                    count=2,
                    escalation={
                        "level_2": "ejection",
                    },
                ),
            ],
            references=["FIBA Rule 37" if league != League.NBA else "NBA Rule 12B-IV"],
        ))

        # 오펜시브 파울
        rules.append(Rule(
            rule_id=f"{league.value}_offensive_foul",
            name="오펜시브 파울",
            category=RuleCategory.FOUL,
            severity=RuleSeverity.MODERATE,
            description="공격 선수가 수비 선수에게 범하는 파울 (차지 등)",
            penalties=[
                Penalty(
                    penalty_type="turnover",
                    description="공격권 상실 + 파울 기록",
                ),
            ],
            references=["FIBA Rule 33.9"],
        ))

        # === 득점 규칙 ===
        three_pt_distance = THREE_POINT_DISTANCE.get(league, 675)
        rules.append(Rule(
            rule_id=f"{league.value}_three_point",
            name="3점 슛",
            category=RuleCategory.SCORING,
            severity=RuleSeverity.MINOR,
            description=f"3점 라인({three_pt_distance/100}m) 밖에서의 성공 슛은 3점",
            conditions=[
                RuleCondition(
                    condition_type="distance_from_basket",
                    threshold=float(three_pt_distance),
                    comparison="gte",
                ),
            ],
            league_specific={"three_point_distance_cm": three_pt_distance},
            references=["FIBA Rule 16"],
        ))

        # 자유투
        rules.append(Rule(
            rule_id=f"{league.value}_free_throw",
            name="자유투",
            category=RuleCategory.SCORING,
            severity=RuleSeverity.MINOR,
            description="파울 시 주어지는 무방해 슛, 성공 시 1점",
            league_specific={"free_throw_line_distance_cm": 460},  # 4.6m
            references=["FIBA Rule 43"],
        ))

        # === 골텐딩/인터피어런스 ===
        rules.append(Rule(
            rule_id=f"{league.value}_goaltending",
            name="골텐딩",
            category=RuleCategory.VIOLATION,
            severity=RuleSeverity.MODERATE,
            description="하강 중인 공이나 림 위에 있는 공을 터치",
            penalties=[
                Penalty(
                    penalty_type="basket_awarded",
                    description="득점 인정 (공격팀) 또는 바이올레이션 (수비팀)",
                ),
            ],
            references=["FIBA Rule 31"],
        ))

        # === 아웃 오브 바운즈 ===
        rules.append(Rule(
            rule_id=f"{league.value}_out_of_bounds",
            name="아웃 오브 바운즈",
            category=RuleCategory.OUT_OF_BOUNDS,
            severity=RuleSeverity.MINOR,
            description="공이나 공을 소유한 선수가 코트 경계선을 넘음",
            penalties=[
                Penalty(
                    penalty_type="turnover",
                    description="마지막으로 터치한 팀의 공격권 상실",
                ),
            ],
            references=["FIBA Rule 23"],
        ))

        return rules

    def get_rule_set(
        self,
        league: League,
        version: str | None = None,
        include_inherited: bool = True,
    ) -> RuleSet:
        """
        규칙 세트 조회.

        Args:
            league: 리그
            version: 버전 (None이면 최신)
            include_inherited: 상속 규칙 포함 여부

        Returns:
            규칙 세트

        Raises:
            RuleSetNotFoundException: 규칙 세트를 찾을 수 없을 때
        """
        cache_key = f"{league.value}:{version or 'latest'}"

        with self._lock:
            # 캐시 확인
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                if cached.metadata and not cached.metadata.is_stale(self._cache_ttl):
                    logger.debug(f"규칙 세트 캐시 히트: {cache_key}")
                    return cached

            # 규칙 세트 로드
            rule_set = self._load_rule_set(league, version, include_inherited)

            # 캐시 저장
            self._cache[cache_key] = rule_set

            # 캐시 크기 제한
            if len(self._cache) > MAX_CACHE_SIZE:
                self._evict_oldest_cache()

            return rule_set

    def _load_rule_set(
        self,
        league: League,
        version: str | None,
        include_inherited: bool,
    ) -> RuleSet:
        """
        규칙 세트 로드.

        Args:
            league: 리그
            version: 버전
            include_inherited: 상속 규칙 포함 여부

        Returns:
            규칙 세트
        """
        # 내장 규칙 가져오기
        rules = list(self._builtin_rules.get(league, []))

        # 상속 규칙 포함
        if include_inherited and league != League.FIBA:
            parent_leagues = LEAGUE_HIERARCHY.get(league.value, [])
            for parent_league_value in parent_leagues:
                try:
                    parent_league = League(parent_league_value)
                    parent_rules = self._builtin_rules.get(parent_league, [])
                    # 중복 ID 제외하고 추가
                    existing_ids = {r.rule_id for r in rules}
                    for rule in parent_rules:
                        # 상속 규칙은 리그 프리픽스 변경
                        inherited_id = rule.rule_id.replace(
                            f"{parent_league.value}_",
                            f"{league.value}_inherited_"
                        )
                        if inherited_id not in existing_ids and rule.rule_id not in existing_ids:
                            # 깊은 복사 대신 새 객체 생성
                            inherited_rule = Rule(
                                rule_id=inherited_id,
                                name=rule.name,
                                category=rule.category,
                                severity=rule.severity,
                                description=rule.description,
                                conditions=rule.conditions,
                                penalties=rule.penalties,
                                league_specific={
                                    **rule.league_specific,
                                    "inherited_from": parent_league.value,
                                },
                                references=rule.references,
                                effective_date=rule.effective_date,
                                expiry_date=rule.expiry_date,
                            )
                            rules.append(inherited_rule)
                except ValueError:
                    logger.warning(f"알 수 없는 상위 리그: {parent_league_value}")

        # 파일에서 추가 규칙 로드 시도
        file_rules = self._load_rules_from_file(league, version)
        if file_rules:
            existing_ids = {r.rule_id for r in rules}
            for rule in file_rules:
                if rule.rule_id not in existing_ids:
                    rules.append(rule)

        # 메타데이터 생성
        content_hash = self._compute_hash(rules)
        metadata = RuleSetMetadata(
            content_hash=content_hash,
            loaded_at=datetime.now(timezone.utc),
        )

        # 규칙 세트 생성
        return RuleSet(
            league=league,
            version=version or RULE_SET_SCHEMA_VERSION,
            rules=rules,
            metadata=metadata,
            parent_league=League.FIBA if league != League.FIBA else None,
        )

    def _load_rules_from_file(
        self,
        league: League,
        version: str | None,
    ) -> list[Rule]:
        """
        파일에서 규칙 로드.

        Args:
            league: 리그
            version: 버전

        Returns:
            로드된 규칙 목록
        """
        # 파일 경로 구성
        file_name = f"{league.value}.yaml"
        if version:
            file_name = f"{league.value}_{version}.yaml"

        file_path = self._rule_set_path / file_name

        if not file_path.exists():
            logger.debug(f"규칙 세트 파일 없음: {file_path}")
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "rules" not in data:
                return []

            rules = []
            for rule_data in data["rules"]:
                rule = self._parse_rule(rule_data, league)
                if rule:
                    rules.append(rule)

            logger.info(
                f"파일에서 규칙 {len(rules)}개 로드",
                extra={"league": league.value, "file": str(file_path)},
            )
            return rules

        except Exception as e:
            logger.warning(f"규칙 세트 파일 로드 실패: {file_path}, 오류: {e}")
            return []

    def _parse_rule(self, data: dict[str, Any], league: League) -> Rule | None:
        """
        규칙 데이터 파싱.

        Args:
            data: 규칙 데이터
            league: 리그

        Returns:
            파싱된 규칙 (실패 시 None)
        """
        try:
            # 필수 필드 검증
            required = ["rule_id", "name", "category", "description"]
            for field in required:
                if field not in data:
                    logger.warning(f"필수 필드 누락: {field}")
                    return None

            # 카테고리 파싱
            try:
                category = RuleCategory(data["category"])
            except ValueError:
                category = RuleCategory.VIOLATION

            # 심각도 파싱
            try:
                severity = RuleSeverity(data.get("severity", "minor"))
            except ValueError:
                severity = RuleSeverity.MINOR

            # 조건 파싱
            conditions = []
            for cond_data in data.get("conditions", []):
                conditions.append(RuleCondition(
                    condition_type=cond_data.get("type", ""),
                    parameters=cond_data.get("parameters", {}),
                    threshold=cond_data.get("threshold"),
                    comparison=cond_data.get("comparison", "eq"),
                ))

            # 패널티 파싱
            penalties = []
            for pen_data in data.get("penalties", []):
                penalties.append(Penalty(
                    penalty_type=pen_data.get("type", ""),
                    description=pen_data.get("description", ""),
                    duration=pen_data.get("duration"),
                    count=pen_data.get("count"),
                    escalation=pen_data.get("escalation"),
                ))

            return Rule(
                rule_id=data["rule_id"],
                name=data["name"],
                category=category,
                severity=severity,
                description=data["description"],
                conditions=conditions,
                penalties=penalties,
                league_specific=data.get("league_specific", {}),
                references=data.get("references", []),
            )

        except Exception as e:
            logger.warning(f"규칙 파싱 실패: {e}")
            return None

    def _compute_hash(self, rules: list[Rule]) -> str:
        """
        규칙 목록 해시 계산.

        Args:
            rules: 규칙 목록

        Returns:
            SHA-256 해시
        """
        content = "".join(r.rule_id for r in sorted(rules, key=lambda x: x.rule_id))
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _evict_oldest_cache(self) -> None:
        """가장 오래된 캐시 항목 제거."""
        if not self._cache:
            return

        oldest_key = None
        oldest_time = datetime.now(timezone.utc)

        for key, rule_set in self._cache.items():
            if rule_set.metadata and rule_set.metadata.loaded_at < oldest_time:
                oldest_time = rule_set.metadata.loaded_at
                oldest_key = key

        if oldest_key:
            del self._cache[oldest_key]
            logger.debug(f"캐시 항목 제거: {oldest_key}")

    def get_rule(
        self,
        league: League,
        rule_id: str,
        fallback: bool = True,
    ) -> Rule | None:
        """
        특정 규칙 조회.

        Args:
            league: 리그
            rule_id: 규칙 ID
            fallback: 폴백 리그에서 조회 여부

        Returns:
            규칙 (없으면 None)
        """
        rule_set = self.get_rule_set(league)
        rule = rule_set.get_rule(rule_id)

        if rule is None and fallback and league != League.FIBA:
            # 폴백 리그에서 조회
            fallback_set = self.get_rule_set(League.FIBA)
            # 리그 프리픽스를 FIBA로 변경하여 조회
            fiba_rule_id = rule_id.replace(f"{league.value}_", f"{League.FIBA.value}_")
            rule = fallback_set.get_rule(fiba_rule_id)

        return rule

    def get_rules_by_category(
        self,
        league: League,
        category: RuleCategory,
    ) -> list[Rule]:
        """
        카테고리별 규칙 조회.

        Args:
            league: 리그
            category: 카테고리

        Returns:
            규칙 목록
        """
        rule_set = self.get_rule_set(league)
        return rule_set.get_rules_by_category(category)

    def get_league_config(self, league: League) -> LeagueConfig:
        """
        리그 설정 조회.

        Args:
            league: 리그

        Returns:
            리그 설정
        """
        return LeagueConfig.for_league(league)

    def validate_rule_set(self, rule_set: RuleSet) -> bool:
        """
        규칙 세트 검증.

        Args:
            rule_set: 규칙 세트

        Returns:
            유효 여부

        Raises:
            RuleSetValidationException: 검증 실패 시
        """
        errors: list[dict[str, Any]] = []

        # 기본 검증
        if not rule_set.rules:
            errors.append({
                "field": "rules",
                "error": "규칙이 없습니다",
            })

        # 규칙별 검증
        seen_ids: set[str] = set()
        for rule in rule_set.rules:
            # 중복 ID 검사
            if rule.rule_id in seen_ids:
                errors.append({
                    "field": "rule_id",
                    "value": rule.rule_id,
                    "error": "중복된 규칙 ID",
                })
            seen_ids.add(rule.rule_id)

            # 필수 필드 검사
            if not rule.name:
                errors.append({
                    "field": f"{rule.rule_id}.name",
                    "error": "이름이 없습니다",
                })
            if not rule.description:
                errors.append({
                    "field": f"{rule.rule_id}.description",
                    "error": "설명이 없습니다",
                })

        if errors:
            raise RuleSetValidationException(
                league=rule_set.league.value,
                validation_errors=errors,
            )

        return True

    def clear_cache(self, league: League | None = None) -> int:
        """
        캐시 클리어.

        Args:
            league: 리그 (None이면 전체)

        Returns:
            삭제된 항목 수
        """
        with self._lock:
            if league is None:
                count = len(self._cache)
                self._cache.clear()
                logger.info(f"전체 캐시 클리어: {count}개")
                return count

            count = 0
            keys_to_delete = [
                k for k in self._cache.keys()
                if k.startswith(f"{league.value}:")
            ]
            for key in keys_to_delete:
                del self._cache[key]
                count += 1

            logger.info(f"{league.value} 캐시 클리어: {count}개")
            return count

    def get_supported_leagues(self) -> list[League]:
        """지원 리그 목록 반환."""
        return list(League)

    def shutdown(self) -> None:
        """매니저 종료."""
        with self._lock:
            self._cache.clear()
        logger.info("RuleSetManager 종료")


# ============================================================
# 헬퍼 함수
# ============================================================
def load_rule_set(
    league: League | str,
    version: str | None = None,
    config_loader: ConfigLoader | None = None,
) -> RuleSet:
    """
    규칙 세트 로드 헬퍼 함수.

    Args:
        league: 리그 (League enum 또는 문자열)
        version: 버전
        config_loader: 설정 로더 (None이면 전역 매니저 사용)

    Returns:
        규칙 세트

    Raises:
        RuleSetNotFoundException: 규칙 세트를 찾을 수 없을 때
    """
    # 문자열이면 League enum으로 변환
    if isinstance(league, str):
        try:
            league = League(league.lower())
        except ValueError:
            raise RuleSetNotFoundException(
                league=league,
                details={"available_leagues": [l.value for l in League]},
            )

    manager = _get_manager(config_loader)
    return manager.get_rule_set(league, version)


def get_rule_by_id(
    league: League | str,
    rule_id: str,
    config_loader: ConfigLoader | None = None,
) -> Rule | None:
    """
    ID로 규칙 조회 헬퍼 함수.

    Args:
        league: 리그
        rule_id: 규칙 ID
        config_loader: 설정 로더

    Returns:
        규칙 (없으면 None)
    """
    if isinstance(league, str):
        try:
            league = League(league.lower())
        except ValueError:
            return None

    manager = _get_manager(config_loader)
    return manager.get_rule(league, rule_id)


def get_rules_by_category(
    league: League | str,
    category: RuleCategory | str,
    config_loader: ConfigLoader | None = None,
) -> list[Rule]:
    """
    카테고리별 규칙 조회 헬퍼 함수.

    Args:
        league: 리그
        category: 카테고리
        config_loader: 설정 로더

    Returns:
        규칙 목록
    """
    if isinstance(league, str):
        try:
            league = League(league.lower())
        except ValueError:
            return []

    if isinstance(category, str):
        try:
            category = RuleCategory(category.lower())
        except ValueError:
            return []

    manager = _get_manager(config_loader)
    return manager.get_rules_by_category(league, category)


def merge_rule_sets(
    rule_sets: list[RuleSet],
    priority_order: list[League] | None = None,
) -> RuleSet:
    """
    다중 규칙 세트 병합.

    Args:
        rule_sets: 병합할 규칙 세트 목록
        priority_order: 우선순위 순서 (앞쪽이 높음)

    Returns:
        병합된 규칙 세트
    """
    if not rule_sets:
        raise ValueError("병합할 규칙 세트가 없습니다")

    if len(rule_sets) == 1:
        return rule_sets[0]

    # 우선순위 정렬
    if priority_order:
        rule_sets = sorted(
            rule_sets,
            key=lambda rs: (
                priority_order.index(rs.league)
                if rs.league in priority_order
                else len(priority_order)
            )
        )

    # 규칙 병합 (후순위가 선순위를 오버라이드)
    merged_rules: dict[str, Rule] = {}
    for rule_set in reversed(rule_sets):
        for rule in rule_set.rules:
            # 규칙 ID에서 리그 프리픽스 제거하여 통합 ID 생성
            base_id = rule.rule_id
            for league in League:
                base_id = base_id.replace(f"{league.value}_", "")
                base_id = base_id.replace(f"{league.value}_inherited_", "")

            if base_id not in merged_rules:
                merged_rules[base_id] = rule

    # 메타데이터 생성
    content_hash = hashlib.sha256(
        "".join(sorted(merged_rules.keys())).encode()
    ).hexdigest()[:16]

    return RuleSet(
        league=rule_sets[0].league,  # 첫 번째 리그를 대표로
        version=f"merged_{RULE_SET_SCHEMA_VERSION}",
        rules=list(merged_rules.values()),
        metadata=RuleSetMetadata(
            content_hash=content_hash,
            loaded_at=datetime.now(timezone.utc),
        ),
    )


def validate_rule_set(
    rule_set: RuleSet,
    config_loader: ConfigLoader | None = None,
) -> bool:
    """
    규칙 세트 검증 헬퍼 함수.

    Args:
        rule_set: 규칙 세트
        config_loader: 설정 로더

    Returns:
        유효 여부
    """
    manager = _get_manager(config_loader)
    return manager.validate_rule_set(rule_set)


# ============================================================
# 리그별 팩토리 함수
# ============================================================
def get_fiba_rules(config_loader: ConfigLoader | None = None) -> RuleSet:
    """FIBA 국제 규칙 로드."""
    return load_rule_set(League.FIBA, config_loader=config_loader)


def get_nba_rules(config_loader: ConfigLoader | None = None) -> RuleSet:
    """NBA 규칙 로드."""
    return load_rule_set(League.NBA, config_loader=config_loader)


def get_kbl_rules(config_loader: ConfigLoader | None = None) -> RuleSet:
    """KBL 한국 규칙 로드."""
    return load_rule_set(League.KBL, config_loader=config_loader)


def get_nbl_rules(config_loader: ConfigLoader | None = None) -> RuleSet:
    """NBL 호주 규칙 로드."""
    return load_rule_set(League.NBL, config_loader=config_loader)


def get_ncaa_rules(config_loader: ConfigLoader | None = None) -> RuleSet:
    """NCAA 미국 대학 규칙 로드."""
    return load_rule_set(League.NCAA, config_loader=config_loader)


def get_b_league_rules(config_loader: ConfigLoader | None = None) -> RuleSet:
    """B.League 일본 규칙 로드."""
    return load_rule_set(League.B_LEAGUE, config_loader=config_loader)


def get_pba_rules(config_loader: ConfigLoader | None = None) -> RuleSet:
    """PBA 필리핀 규칙 로드."""
    return load_rule_set(League.PBA, config_loader=config_loader)


# ============================================================
# 전역 매니저 관리
# ============================================================
_global_manager: RuleSetManager | None = None
_global_lock = threading.Lock()


def _get_manager(config_loader: ConfigLoader | None = None) -> RuleSetManager:
    """
    전역 매니저 인스턴스 반환.

    Args:
        config_loader: 설정 로더 (None이면 기본 생성)

    Returns:
        RuleSetManager 인스턴스
    """
    global _global_manager

    with _global_lock:
        if _global_manager is None:
            if config_loader is None:
                config_loader = ConfigLoader()
            _global_manager = RuleSetManager(config_loader)

        return _global_manager


def _reset_manager() -> None:
    """
    전역 매니저 리셋 (테스트용).

    주의: 프로덕션에서는 사용하지 마세요.
    """
    global _global_manager

    with _global_lock:
        if _global_manager is not None:
            _global_manager.shutdown()
            _global_manager = None
            logger.info("전역 RuleSetManager 리셋")


# ============================================================
# 모듈 Export
# ============================================================
__all__ = [
    # Enum (3개)
    "League",
    "RuleCategory",
    "RuleSeverity",
    # 상수 (8개)
    "SUPPORTED_LEAGUES",
    "DEFAULT_RULE_SET_PATH",
    "RULE_SET_SCHEMA_VERSION",
    "DEFAULT_CACHE_TTL",
    "MAX_CACHE_SIZE",
    "RULE_PRIORITY_WEIGHTS",
    "LEAGUE_HIERARCHY",
    "DEFAULT_FALLBACK_LEAGUE",
    # 데이터 클래스 (6개)
    "Rule",
    "RuleSet",
    "RuleCondition",
    "Penalty",
    "RuleSetMetadata",
    "LeagueConfig",
    # Protocol (1개)
    "RuleSetLoaderProtocol",
    # 메인 클래스
    "RuleSetManager",
    # 헬퍼 함수 (5개)
    "load_rule_set",
    "get_rule_by_id",
    "get_rules_by_category",
    "merge_rule_sets",
    "validate_rule_set",
    # 리그별 팩토리 함수 (7개)
    "get_fiba_rules",
    "get_nba_rules",
    "get_kbl_rules",
    "get_nbl_rules",
    "get_ncaa_rules",
    "get_b_league_rules",
    "get_pba_rules",
    # 전역 함수 (2개)
    "_get_manager",
    "_reset_manager",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
