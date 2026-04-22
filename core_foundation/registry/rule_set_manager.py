# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/registry
파일: rule_set_manager.py
설명: 리그별 규칙 관리자
      - 활성 규칙 세트 관리 (FIBA/NBA/KBL/NBL/EUROLEAGUE)
      - 규칙 오버라이드 등록/조회
      - 규칙 변경 콜백 (리그 전환 시 알림)
      - 규칙 값 조회 (기본값 + 오버라이드 병합)
      - 스레드 안전 (RLock)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0
"""
from __future__ import annotations

# =============================================================================
# 표준 라이브러리 (Standard Library)
# =============================================================================
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Final


# =============================================================================
# 프로젝트 내부 (Project Internal) — Layer 0: shared만 참조
# =============================================================================
from shared.constants.referee_rule_constants import RuleSet


# =============================================================================
# 상수 정의
# =============================================================================

# 최대 오버라이드 수 (리그당)
MAX_OVERRIDES_PER_RULESET: Final[int] = 100

# 최대 콜백 수
MAX_CALLBACKS: Final[int] = 50

# 기본 규칙 세트
DEFAULT_RULE_SET: Final[RuleSet] = RuleSet.FIBA


# =============================================================================
# 규칙 오버라이드
# =============================================================================

@dataclass(slots=True)
class RuleOverride:
    """규칙 오버라이드 정보.

    Attributes:
        rule_key: 규칙 키 (예: "shot_clock_seconds")
        value: 오버라이드 값
        reason: 오버라이드 사유
    """

    rule_key: str
    value: Any
    reason: str = ""

    def __repr__(self) -> str:
        return (
            f"RuleOverride('{self.rule_key}', "
            f"value={self.value})"
        )


# =============================================================================
# 규칙 스냅샷
# =============================================================================

@dataclass(slots=True)
class RuleSnapshot:
    """현재 활성 규칙 스냅샷.

    Attributes:
        rule_set: 활성 규칙 세트
        base_rules: 기본 규칙 (RuleSet에서 제공)
        overrides: 적용된 오버라이드
        effective_rules: 최종 유효 규칙 (기본 + 오버라이드 병합)
    """

    rule_set: RuleSet
    base_rules: dict[str, Any]
    overrides: dict[str, Any]
    effective_rules: dict[str, Any]

    def __repr__(self) -> str:
        return (
            f"RuleSnapshot("
            f"{self.rule_set.value}, "
            f"overrides={len(self.overrides)})"
        )


# =============================================================================
# 타입 정의
# =============================================================================

# 규칙 변경 콜백: (old_rule_set, new_rule_set) -> None
RuleChangeCallback = Callable[[RuleSet, RuleSet], None]


# =============================================================================
# 핵심 클래스: RuleSetManager
# =============================================================================

class RuleSetManager:
    """리그별 규칙 관리자.

    활성 규칙 세트를 관리하고, 규칙 오버라이드를 적용한다.
    리그 전환 시 콜백을 통해 관련 모듈에 알린다.

    스레드 안전:
        모든 메서드는 RLock 보호.

    사용 예시::

        manager = RuleSetManager.get_instance()

        # 규칙 세트 설정
        manager.set_active(RuleSet.KBL)

        # 규칙 조회
        quarter_sec = manager.get_rule("quarter_duration_sec")
        three_pt = manager.get_rule("three_point_distance_meters")

        # 오버라이드
        manager.add_override("shot_clock_seconds", 30, reason="대회 규정")

        # 규칙 변경 콜백
        manager.add_change_callback(on_rule_change)

        # 스냅샷
        snapshot = manager.snapshot()
    """

    _instance: ClassVar[RuleSetManager | None] = None
    _class_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active: RuleSet = DEFAULT_RULE_SET
        self._overrides: dict[RuleSet, dict[str, RuleOverride]] = {}
        self._callbacks: list[RuleChangeCallback] = []

    # =========================================================================
    # Singleton
    # =========================================================================

    @classmethod
    def get_instance(cls) -> RuleSetManager:
        """Singleton 인스턴스 획득."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Singleton 초기화 (테스트용)."""
        with cls._class_lock:
            cls._instance = None

    # =========================================================================
    # 활성 규칙 세트
    # =========================================================================

    @property
    def active(self) -> RuleSet:
        """현재 활성 규칙 세트."""
        with self._lock:
            return self._active

    def set_active(self, rule_set: RuleSet) -> None:
        """활성 규칙 세트 변경.

        변경 시 등록된 콜백을 호출한다.

        Args:
            rule_set: 새 규칙 세트
        """
        with self._lock:
            old = self._active
            if old == rule_set:
                return

            self._active = rule_set
            callbacks = list(self._callbacks)

        # 콜백 실행 (lock 밖, 예외 격리)
        for callback in callbacks:
            try:
                callback(old, rule_set)
            except Exception:
                pass

    # =========================================================================
    # 규칙 조회
    # =========================================================================

    def get_rule(self, rule_key: str) -> Any:
        """규칙 값 조회.

        오버라이드 → 기본값 순으로 조회.

        Args:
            rule_key: 규칙 키

        Returns:
            규칙 값

        Raises:
            KeyError: 미등록 규칙
        """
        with self._lock:
            # 오버라이드 확인
            overrides = self._overrides.get(self._active, {})
            if rule_key in overrides:
                return overrides[rule_key].value

            # 기본값 조회 (RuleSet property)
            base = self._get_base_rules(self._active)
            if rule_key in base:
                return base[rule_key]

            raise KeyError(f"미등록 규칙: '{rule_key}'")

    def get_rule_optional(
        self,
        rule_key: str,
        default: Any = None,
    ) -> Any:
        """규칙 값 조회 (없으면 기본값).

        Args:
            rule_key: 규칙 키
            default: 기본 반환값

        Returns:
            규칙 값 또는 기본값
        """
        try:
            return self.get_rule(rule_key)
        except KeyError:
            return default

    def get_all_rules(self) -> dict[str, Any]:
        """현재 활성 규칙 전체 조회.

        Returns:
            규칙 키 → 값 딕셔너리 (기본 + 오버라이드 병합)
        """
        with self._lock:
            base = self._get_base_rules(self._active)
            result = dict(base)

            # 오버라이드 적용
            overrides = self._overrides.get(self._active, {})
            for key, override in overrides.items():
                result[key] = override.value

            return result

    # =========================================================================
    # 오버라이드 관리
    # =========================================================================

    def add_override(
        self,
        rule_key: str,
        value: Any,
        *,
        reason: str = "",
        rule_set: RuleSet | None = None,
    ) -> bool:
        """규칙 오버라이드 추가.

        Args:
            rule_key: 규칙 키
            value: 오버라이드 값
            reason: 사유
            rule_set: 대상 규칙 세트 (None이면 활성 세트)

        Returns:
            추가 성공 여부
        """
        with self._lock:
            target = rule_set or self._active
            overrides = self._overrides.setdefault(target, {})

            if (
                rule_key not in overrides
                and len(overrides) >= MAX_OVERRIDES_PER_RULESET
            ):
                return False

            overrides[rule_key] = RuleOverride(
                rule_key=rule_key,
                value=value,
                reason=reason,
            )
            return True

    def remove_override(
        self,
        rule_key: str,
        *,
        rule_set: RuleSet | None = None,
    ) -> bool:
        """규칙 오버라이드 제거.

        Args:
            rule_key: 규칙 키
            rule_set: 대상 규칙 세트 (None이면 활성 세트)

        Returns:
            제거 성공 여부
        """
        with self._lock:
            target = rule_set or self._active
            overrides = self._overrides.get(target, {})
            if rule_key in overrides:
                del overrides[rule_key]
                return True
            return False

    def get_overrides(
        self,
        rule_set: RuleSet | None = None,
    ) -> dict[str, RuleOverride]:
        """오버라이드 목록 조회.

        Args:
            rule_set: 대상 규칙 세트 (None이면 활성 세트)

        Returns:
            규칙 키 → RuleOverride (복사본)
        """
        with self._lock:
            target = rule_set or self._active
            overrides = self._overrides.get(target, {})
            return dict(overrides)

    def clear_overrides(
        self,
        rule_set: RuleSet | None = None,
    ) -> int:
        """오버라이드 전체 제거.

        Args:
            rule_set: 대상 규칙 세트 (None이면 활성 세트)

        Returns:
            제거된 오버라이드 수
        """
        with self._lock:
            target = rule_set or self._active
            overrides = self._overrides.get(target, {})
            count = len(overrides)
            overrides.clear()
            return count

    # =========================================================================
    # 콜백
    # =========================================================================

    def add_change_callback(self, callback: RuleChangeCallback) -> bool:
        """규칙 변경 콜백 등록.

        Args:
            callback: (old_rule_set, new_rule_set) -> None

        Returns:
            등록 성공 여부
        """
        with self._lock:
            if len(self._callbacks) >= MAX_CALLBACKS:
                return False
            self._callbacks.append(callback)
            return True

    def remove_change_callback(self, callback: RuleChangeCallback) -> bool:
        """규칙 변경 콜백 해제."""
        with self._lock:
            try:
                self._callbacks.remove(callback)
                return True
            except ValueError:
                return False

    # =========================================================================
    # 스냅샷
    # =========================================================================

    def snapshot(self) -> RuleSnapshot:
        """현재 규칙 스냅샷 생성.

        Returns:
            RuleSnapshot
        """
        with self._lock:
            base = self._get_base_rules(self._active)
            override_values: dict[str, Any] = {}

            overrides = self._overrides.get(self._active, {})
            for key, o in overrides.items():
                override_values[key] = o.value

            effective = dict(base)
            effective.update(override_values)

            return RuleSnapshot(
                rule_set=self._active,
                base_rules=dict(base),
                overrides=override_values,
                effective_rules=effective,
            )

    # =========================================================================
    # 관리
    # =========================================================================

    @property
    def override_count(self) -> int:
        """현재 활성 세트의 오버라이드 수."""
        with self._lock:
            overrides = self._overrides.get(self._active, {})
            return len(overrides)

    def __repr__(self) -> str:
        return (
            f"RuleSetManager("
            f"active={self._active.value}, "
            f"overrides={self.override_count})"
        )

    # =========================================================================
    # 내부 메서드
    # =========================================================================

    @staticmethod
    def _get_base_rules(rule_set: RuleSet) -> dict[str, Any]:
        """RuleSet에서 기본 규칙 추출.

        RuleSet Enum의 property를 딕셔너리로 변환.
        """
        return {
            "quarter_duration_sec": rule_set.quarter_duration_sec,
            "shot_clock_seconds": rule_set.shot_clock_seconds,
            "backcourt_seconds": rule_set.backcourt_seconds,
            "three_point_distance_meters": rule_set.three_point_distance_meters,
            "max_personal_fouls": rule_set.max_personal_fouls,
            "max_timeouts": rule_set.max_timeouts,
            "has_defensive_three_seconds": rule_set.has_defensive_three_seconds,
            "korean_name": rule_set.korean_name,
        }


# =============================================================================
# 모듈 Export 정의
# =============================================================================
__all__ = [
    # 데이터 클래스
    "RuleOverride",
    "RuleSnapshot",
    # 타입
    "RuleChangeCallback",
    # 핵심 클래스
    "RuleSetManager",
    # 상수
    "MAX_OVERRIDES_PER_RULESET",
    "MAX_CALLBACKS",
    "DEFAULT_RULE_SET",
]

__version__ = "1.0.0"
