# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: ai_referee/rules
파일: rule_loader.py
설명: 리그별 규칙 YAML 로더
      - YAML 설정 파일에서 리그별 Rules 인스턴스 생성
      - base_rules 상속 지원 (NBA→FIBA 기반 오버라이드)
      - 리그별 규칙 캐시 (스레드 안전)
      - violation_thresholds + foul_criteria YAML 로딩
      - RuleParameters 일괄 생성

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조:
    - configs/ai_referee/*.yaml: 리그별 규칙 + 임계치
    - core_foundation/config/loader.py: YAML 로딩 인프라
    - shared/constants/referee_rule_constants.py: RuleSet enum
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from threading import RLock
from typing import Any, Final

import yaml

from shared.constants.referee_rule_constants import RuleSet
from shared.exceptions.validation_exceptions import (
    ConfigurationLoadException,
)

from ai_referee.rules.base_rule import RuleParameters
from ai_referee.rules.fiba_rules import FIBARules
from ai_referee.rules.kbl_rules import KBLRules
from ai_referee.rules.nba_rules import NBARules
from ai_referee.rules.nbl_rules import NBLRules

logger: Final = logging.getLogger(__name__)


# =============================================================================
# 상수
# =============================================================================
_DEFAULT_CONFIG_DIR: Final[str] = "configs/ai_referee"
_MAX_CACHE_SIZE: Final[int] = 10

# 리그별 YAML 파일 매핑
_LEAGUE_YAML_MAP: Final[dict[RuleSet, str]] = {
    RuleSet.FIBA: "fiba_rules.yaml",
    RuleSet.NBA: "nba_rules.yaml",
    RuleSet.KBL: "kbl_rules.yaml",
    RuleSet.NBL: "nbl_rules.yaml",
}

# 리그별 Rules 클래스 매핑
_LEAGUE_CLASS_MAP: Final[dict[RuleSet, type]] = {
    RuleSet.FIBA: FIBARules,
    RuleSet.NBA: NBARules,
    RuleSet.KBL: KBLRules,
    RuleSet.NBL: NBLRules,
}

# 임계치/기준 YAML 파일
_THRESHOLD_FILES: Final[dict[str, str]] = {
    "violation_thresholds": "violation_thresholds.yaml",
    "foul_criteria": "foul_criteria.yaml",
    "flagrant_criteria": "flagrant_criteria.yaml",
    "shooting_foul_criteria": "shooting_foul_criteria.yaml",
    "technical_criteria": "technical_criteria.yaml",
}


# =============================================================================
# YAML 로딩 유틸리티
# =============================================================================
def _deep_merge(base: dict, override: dict) -> dict:
    """
    딕셔너리 재귀적 병합.

    override의 값이 base를 덮어씁니다.
    중첩 dict는 재귀적으로 병합됩니다.

    Args:
        base: 기본 딕셔너리 (복사됨)
        override: 오버라이드 딕셔너리

    Returns:
        병합된 새 딕셔너리
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_yaml_file(file_path: Path) -> dict[str, Any]:
    """
    단일 YAML 파일 로딩.

    Args:
        file_path: YAML 파일 경로

    Returns:
        파싱된 딕셔너리

    Raises:
        ConfigurationLoadException: 파일 로딩/파싱 실패
    """
    if not file_path.exists():
        raise ConfigurationLoadException(
            f"규칙 설정 파일을 찾을 수 없습니다: {file_path}",
        )

    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigurationLoadException(
            f"YAML 파싱 오류: {file_path} — {exc}",
        ) from exc
    except OSError as exc:
        raise ConfigurationLoadException(
            f"파일 읽기 오류: {file_path} — {exc}",
        ) from exc

    if not isinstance(data, dict):
        raise ConfigurationLoadException(
            f"YAML 최상위가 dict가 아닙니다: {file_path} (type={type(data).__name__})",
        )

    return data


def _resolve_base_rules(
    cfg: dict[str, Any],
    config_dir: Path,
) -> dict[str, Any]:
    """
    base_rules 상속 해결.

    cfg에 'base_rules' 키가 있으면 해당 YAML을 로딩하고
    deep merge하여 상속된 규칙을 반환합니다.

    Args:
        cfg: 현재 리그 YAML 딕셔너리
        config_dir: 설정 파일 디렉토리

    Returns:
        base_rules가 해결된 딕셔너리
    """
    base_file = cfg.get("base_rules")
    if not base_file:
        return cfg

    base_path = config_dir / base_file
    base_cfg = _load_yaml_file(base_path)

    # base도 base_rules를 가질 수 있음 (재귀적 상속 — 현재 1단계만 지원)
    if "base_rules" in base_cfg:
        base_cfg = _resolve_base_rules(base_cfg, config_dir)

    # base를 기반으로 현재 cfg를 오버라이드
    merged = _deep_merge(base_cfg, cfg)

    # base_rules 키 제거 (최종 결과에서 불필요)
    merged.pop("base_rules", None)
    return merged


# =============================================================================
# RuleLoader — 규칙 로더
# =============================================================================
class RuleLoader:
    """
    리그별 규칙 YAML 로더.

    YAML 설정 파일에서 리그별 Rules 인스턴스를 생성합니다.
    base_rules 상속을 지원하며, 로딩된 규칙을 캐시합니다.

    사용법:
        loader = RuleLoader()
        fiba_rules = loader.load_rules(RuleSet.FIBA)
        nba_rules = loader.load_rules(RuleSet.NBA)
        thresholds = loader.load_violation_thresholds()
    """

    def __init__(
        self,
        config_dir: str | Path | None = None,
    ) -> None:
        """
        Args:
            config_dir: 규칙 설정 디렉토리 경로.
                        None이면 프로젝트 루트 기준 기본 경로 사용.
        """
        self._lock = RLock()

        if config_dir is not None:
            self._config_dir = Path(config_dir)
        else:
            # 프로젝트 루트 탐색 (현재 파일 기준 3단계 상위)
            project_root = Path(__file__).resolve().parent.parent.parent
            self._config_dir = project_root / _DEFAULT_CONFIG_DIR

        # 규칙 캐시: RuleSet → Rules 인스턴스
        self._rules_cache: dict[RuleSet, FIBARules] = {}

        # YAML 원본 캐시: 파일명 → dict
        self._yaml_cache: dict[str, dict[str, Any]] = {}

        # 임계치 캐시: 카테고리명 → dict
        self._threshold_cache: dict[str, dict[str, Any]] = {}

        logger.info(
            "RuleLoader 초기화: config_dir=%s", self._config_dir,
        )

    # === 속성 ===

    @property
    def config_dir(self) -> Path:
        """설정 디렉토리 경로."""
        return self._config_dir

    @property
    def cached_rule_sets(self) -> list[RuleSet]:
        """캐시된 리그 목록."""
        with self._lock:
            return list(self._rules_cache.keys())

    # === 규칙 로딩 ===

    def load_rules(self, rule_set: RuleSet) -> FIBARules:
        """
        리그별 규칙 로딩.

        캐시에 있으면 캐시에서 반환, 없으면 YAML에서 로딩 후 캐시.

        Args:
            rule_set: 리그 (FIBA/NBA/KBL/NBL)

        Returns:
            해당 리그의 Rules 인스턴스

        Raises:
            ConfigurationLoadException: 지원하지 않는 리그 또는 로딩 실패
        """
        with self._lock:
            # 캐시 확인
            if rule_set in self._rules_cache:
                return self._rules_cache[rule_set]

        # YAML 로딩 (lock 밖에서 I/O)
        rules = self._load_rules_from_yaml(rule_set)

        # 캐시 저장
        with self._lock:
            if len(self._rules_cache) >= _MAX_CACHE_SIZE:
                # LRU 대신 전체 초기화 (캐시 크기 제한)
                self._rules_cache.clear()
            self._rules_cache[rule_set] = rules

        logger.info(
            "규칙 로딩 완료: rule_set=%s, class=%s",
            rule_set.value, type(rules).__name__,
        )
        return rules

    def _load_rules_from_yaml(self, rule_set: RuleSet) -> FIBARules:
        """YAML에서 규칙 인스턴스 생성."""
        yaml_file = _LEAGUE_YAML_MAP.get(rule_set)
        if yaml_file is None:
            raise ConfigurationLoadException(
                f"지원하지 않는 리그입니다: {rule_set.value}",
            )

        rules_class = _LEAGUE_CLASS_MAP.get(rule_set)
        if rules_class is None:
            raise ConfigurationLoadException(
                f"규칙 클래스를 찾을 수 없습니다: {rule_set.value}",
            )

        # YAML 로딩 + base_rules 상속 해결
        file_path = self._config_dir / yaml_file
        cfg = _load_yaml_file(file_path)
        cfg = _resolve_base_rules(cfg, self._config_dir)

        # YAML 원본 캐시
        with self._lock:
            self._yaml_cache[yaml_file] = cfg

        # Rules 인스턴스 생성
        return rules_class.from_yaml(cfg)

    # === 임계치/기준 로딩 ===

    def load_violation_thresholds(self) -> dict[str, Any]:
        """
        바이올레이션 임계치 로딩.

        configs/ai_referee/violation_thresholds.yaml을 로딩합니다.

        Returns:
            바이올레이션 임계치 딕셔너리
        """
        return self._load_threshold("violation_thresholds")

    def load_foul_criteria(self) -> dict[str, Any]:
        """
        파울 기준 로딩.

        configs/ai_referee/foul_criteria.yaml을 로딩합니다.

        Returns:
            파울 기준 딕셔너리
        """
        return self._load_threshold("foul_criteria")

    def load_flagrant_criteria(self) -> dict[str, Any]:
        """플래그런트 파울 기준 로딩."""
        return self._load_threshold("flagrant_criteria")

    def load_shooting_foul_criteria(self) -> dict[str, Any]:
        """슈팅 파울 기준 로딩."""
        return self._load_threshold("shooting_foul_criteria")

    def load_technical_criteria(self) -> dict[str, Any]:
        """테크니컬 파울 기준 로딩."""
        return self._load_threshold("technical_criteria")

    def _load_threshold(self, category: str) -> dict[str, Any]:
        """
        임계치/기준 YAML 파일 로딩.

        Args:
            category: 임계치 카테고리 (violation_thresholds, foul_criteria 등)

        Returns:
            파싱된 딕셔너리

        Raises:
            ConfigurationLoadException: 파일 로딩 실패
        """
        with self._lock:
            if category in self._threshold_cache:
                return copy.deepcopy(self._threshold_cache[category])

        yaml_file = _THRESHOLD_FILES.get(category)
        if yaml_file is None:
            raise ConfigurationLoadException(
                f"알 수 없는 임계치 카테고리: {category}",
            )

        file_path = self._config_dir / yaml_file
        data = _load_yaml_file(file_path)

        with self._lock:
            self._threshold_cache[category] = data

        logger.info("임계치 로딩 완료: category=%s", category)
        return copy.deepcopy(data)

    # === RuleParameters 생성 ===

    def create_rule_parameters(
        self,
        rule_id: str,
        rule_reference: str,
        threshold_category: str,
        threshold_key: str,
        *,
        min_confidence: float = 0.50,
    ) -> RuleParameters:
        """
        특정 규칙에 대한 RuleParameters 생성.

        YAML 임계치에서 해당 규칙의 파라미터를 추출하여
        RuleParameters 인스턴스를 생성합니다.

        Args:
            rule_id: 규칙 ID (예: "FIBA-25.1")
            rule_reference: 규정 참조 (예: "FIBA Rule 25.1")
            threshold_category: 임계치 카테고리 (violation_thresholds, foul_criteria)
            threshold_key: 임계치 내 키 (예: "traveling", "blocking_foul")
            min_confidence: 최소 신뢰도 임계치

        Returns:
            RuleParameters 인스턴스
        """
        thresholds = self._load_threshold(threshold_category)

        # threshold_key로 해당 섹션 추출
        params_data = thresholds.get(threshold_key, {})
        if isinstance(params_data, dict):
            # min_confidence가 YAML에 정의되어 있으면 사용
            yaml_confidence = params_data.get("min_confidence")
            if yaml_confidence is not None:
                try:
                    min_confidence = float(yaml_confidence)
                except (TypeError, ValueError):
                    pass

        return RuleParameters(
            rule_id=rule_id,
            rule_reference=rule_reference,
            min_confidence=min_confidence,
            parameters=params_data if isinstance(params_data, dict) else {},
        )

    # === 다중 리그 로딩 ===

    def load_all_rules(self) -> dict[RuleSet, FIBARules]:
        """
        모든 리그 규칙 일괄 로딩.

        Returns:
            RuleSet → Rules 인스턴스 딕셔너리
        """
        results: dict[RuleSet, FIBARules] = {}
        for rule_set in _LEAGUE_YAML_MAP:
            try:
                results[rule_set] = self.load_rules(rule_set)
            except ConfigurationLoadException:
                logger.warning(
                    "리그 규칙 로딩 실패 (건너뜀): rule_set=%s",
                    rule_set.value,
                )
        return results

    # === 캐시 관리 ===

    def invalidate_cache(self, rule_set: RuleSet | None = None) -> None:
        """
        규칙 캐시 무효화.

        Args:
            rule_set: 특정 리그만 무효화. None이면 전체 무효화.
        """
        with self._lock:
            if rule_set is not None:
                self._rules_cache.pop(rule_set, None)
                yaml_file = _LEAGUE_YAML_MAP.get(rule_set)
                if yaml_file:
                    self._yaml_cache.pop(yaml_file, None)
            else:
                self._rules_cache.clear()
                self._yaml_cache.clear()
                self._threshold_cache.clear()

        logger.info(
            "캐시 무효화: rule_set=%s",
            rule_set.value if rule_set else "ALL",
        )

    def reload_rules(self, rule_set: RuleSet) -> FIBARules:
        """
        규칙 리로드 (캐시 무효화 후 재로딩).

        Args:
            rule_set: 리그

        Returns:
            새로 로딩된 Rules 인스턴스
        """
        self.invalidate_cache(rule_set)
        return self.load_rules(rule_set)

    # === 통계 ===

    def get_stats(self) -> dict[str, Any]:
        """로더 통계."""
        with self._lock:
            return {
                "config_dir": str(self._config_dir),
                "cached_rules": [r.value for r in self._rules_cache],
                "cached_yaml_files": list(self._yaml_cache.keys()),
                "cached_thresholds": list(self._threshold_cache.keys()),
            }

    def __repr__(self) -> str:
        with self._lock:
            cached = len(self._rules_cache)
        return (
            f"RuleLoader(config_dir={self._config_dir}, "
            f"cached={cached})"
        )


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "RuleLoader",
]

__version__ = "1.0.0"
