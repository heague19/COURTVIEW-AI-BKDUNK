# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/defensive_analysis
파일: defense_type_classifier.py
설명: 수비 스킴 분류기
      - 맨투맨 vs 존 수비 유형 자동 분류
      - 존 수비 세부 유형 분류 (2-3, 3-2, 1-3-1, 1-2-2)
      - 프레스 수비 감지 (풀코트/하프코트)
      - 특수 수비 감지 (박스앤원, 트라이앵글앤투)
      - 점유별 스킴 분류 → 경기 단위 집계

      Processing Cadence: 🔵 POSSESSION (<100ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: configs/game_analysis/tactical_analysis.yaml (defense 섹션)
의존성: shared.dto.tactical_dto (DefenseScheme, DefenseAnalysis)
         shared.constants.tactical_constants (MATCHUP_ASSIGNMENT_DISTANCE_M, DEFENSIVE_BREAKDOWN_DISTANCE_M)
소비자: defensive_analysis/__init__.py (종합), coaching_intelligence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

from shared.constants.tactical_constants import (
    MATCHUP_ASSIGNMENT_DISTANCE_M,
    DEFENSIVE_BREAKDOWN_DISTANCE_M,
)
from shared.dto.tactical_dto import DefenseScheme

logger: Final = logging.getLogger(__name__)

_MAX_POSSESSION_RECORDS: Final[int] = 500


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class DefenseTypeClassifierConfig:
    """수비 스킴 분류기 설정."""

    max_records: int = _MAX_POSSESSION_RECORDS
    # 맨투맨 판정: 각 수비자가 매치업 거리 이내에 있는 비율이 이 이상이면 맨투맨
    man_to_man_threshold: float = 0.70
    # 존 판정: 수비자 위치 클러스터가 존 패턴과 유사도 이 이상이면 존
    zone_similarity_threshold: float = 0.60
    # 프레스 판정: 수비 평균 위치가 하프라인 이상(풀코트) 또는 3/4 이상
    press_halfline_ratio: float = 0.65
    # 특수 수비: 한 명만 밀착 + 나머지 존 배치
    special_defense_single_mark_distance: float = MATCHUP_ASSIGNMENT_DISTANCE_M
    # 매치업 배정 거리
    assignment_distance_m: float = MATCHUP_ASSIGNMENT_DISTANCE_M
    # 수비 이탈 거리
    breakdown_distance_m: float = DEFENSIVE_BREAKDOWN_DISTANCE_M

    @classmethod
    def from_yaml(cls, cfg: dict) -> DefenseTypeClassifierConfig:
        """YAML 설정에서 생성."""
        defense = cfg.get("defense", {})
        matchup = defense.get("matchup", {})
        return cls(
            assignment_distance_m=matchup.get(
                "assignment_distance_m", MATCHUP_ASSIGNMENT_DISTANCE_M
            ),
            breakdown_distance_m=matchup.get(
                "breakdown_distance_m", DEFENSIVE_BREAKDOWN_DISTANCE_M
            ),
        )


# =============================================================================
# 내부 데이터
# =============================================================================
@dataclass(slots=True)
class _PossessionDefense:
    """점유별 수비 분류 기록."""

    possession_id: int
    scheme: DefenseScheme
    confidence: float  # 분류 신뢰도 (0~1)
    # 수비자별 매치업 상대와의 거리 (m)
    defender_distances: list[float] = field(default_factory=list)
    # 수비 포메이션 좌표 (5명의 [x, y])
    formation: list[tuple[float, float]] = field(default_factory=list)


# =============================================================================
# 존 패턴 정의 (정규화 좌표 기반, 하프코트 기준)
# =============================================================================
# 각 존 유형의 이상적 수비 위치 패턴 (y=0: 베이스라인, y=1: 하프라인)
# x: -1(좌) ~ +1(우), y: 0(골대) ~ 1(하프라인)
_ZONE_PATTERNS: Final[dict[DefenseScheme, list[tuple[float, float]]]] = {
    # 2-3: 2명 상단 + 3명 하단
    DefenseScheme.ZONE_2_3: [
        (-0.3, 0.6), (0.3, 0.6),   # 상단 2
        (-0.5, 0.25), (0.0, 0.2), (0.5, 0.25),  # 하단 3
    ],
    # 3-2: 3명 상단 + 2명 하단
    DefenseScheme.ZONE_3_2: [
        (-0.4, 0.6), (0.0, 0.65), (0.4, 0.6),  # 상단 3
        (-0.3, 0.25), (0.3, 0.25),  # 하단 2
    ],
    # 1-3-1: 1-3-1 형태
    DefenseScheme.ZONE_1_3_1: [
        (0.0, 0.7),   # 포인트
        (-0.4, 0.45), (0.0, 0.45), (0.4, 0.45),  # 중간 3
        (0.0, 0.15),  # 바텀
    ],
    # 1-2-2: 1-2-2 형태
    DefenseScheme.ZONE_1_2_2: [
        (0.0, 0.7),   # 포인트
        (-0.35, 0.5), (0.35, 0.5),  # 상단 2
        (-0.35, 0.2), (0.35, 0.2),  # 하단 2
    ],
}


# =============================================================================
# DefenseTypeClassifier
# =============================================================================
class DefenseTypeClassifier:
    """
    수비 스킴 자동 분류기.

    점유별 수비 포메이션과 매치업 거리를 분석하여
    맨투맨/존/프레스/특수 수비를 분류한다.

    사용법::

        classifier = DefenseTypeClassifier()
        scheme = classifier.classify_possession(
            possession_id=1,
            defender_positions=[(1.0, 2.0), (3.0, 4.0), ...],
            offensive_positions=[(1.5, 2.5), (3.5, 4.5), ...],
            court_length=28.0,
        )
        # scheme.scheme == DefenseScheme.MAN_TO_MAN
    """

    __slots__ = ("_config", "_lock", "_records", "_scheme_counts", "_total")

    def __init__(self, config: DefenseTypeClassifierConfig | None = None) -> None:
        self._config = config or DefenseTypeClassifierConfig()
        self._lock = RLock()
        self._records: list[_PossessionDefense] = []
        # 스킴별 누적 횟수
        self._scheme_counts: dict[DefenseScheme, int] = {s: 0 for s in DefenseScheme}
        self._total: int = 0

    # ------------------------------------------------------------------
    # 속성
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "DefenseTypeClassifier"

    @property
    def total_classified(self) -> int:
        with self._lock:
            return self._total

    @property
    def primary_scheme(self) -> DefenseScheme:
        """가장 빈번한 수비 스킴."""
        with self._lock:
            if self._total == 0:
                return DefenseScheme.MAN_TO_MAN
            return max(self._scheme_counts, key=self._scheme_counts.get)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # 핵심 메서드: 점유별 수비 분류
    # ------------------------------------------------------------------
    def classify_possession(
        self,
        possession_id: int,
        defender_positions: list[tuple[float, float]],
        offensive_positions: list[tuple[float, float]],
        court_length: float = 28.0,
    ) -> _PossessionDefense:
        """
        점유별 수비 스킴을 분류한다.

        Args:
            possession_id: 점유 ID
            defender_positions: 수비자 5명 좌표 [(x, y), ...]
            offensive_positions: 공격자 5명 좌표 [(x, y), ...]
            court_length: 코트 전체 길이 (m, 기본 28m)

        Returns:
            _PossessionDefense 분류 결과
        """
        with self._lock:
            # 1. 수비자-공격자 최근접 거리 계산
            distances = self._calculate_matchup_distances(
                defender_positions, offensive_positions,
            )

            # 2. 프레스 수비 감지 (코트 위치 기반)
            press_scheme = self._detect_press(defender_positions, court_length)
            if press_scheme is not None:
                record = _PossessionDefense(
                    possession_id=possession_id,
                    scheme=press_scheme,
                    confidence=0.80,
                    defender_distances=distances,
                    formation=list(defender_positions),
                )
                self._add_record(record)
                return record

            # 3. 맨투맨 판정: 대다수 수비자가 매치업 거리 이내
            man_ratio = sum(
                1 for d in distances if d <= self._config.assignment_distance_m
            ) / max(len(distances), 1)

            if man_ratio >= self._config.man_to_man_threshold:
                # 특수 수비 감지 (박스앤원, 트라이앵글앤투)
                special = self._detect_special_defense(distances, defender_positions)
                if special is not None:
                    record = _PossessionDefense(
                        possession_id=possession_id,
                        scheme=special,
                        confidence=0.65,
                        defender_distances=distances,
                        formation=list(defender_positions),
                    )
                    self._add_record(record)
                    return record

                record = _PossessionDefense(
                    possession_id=possession_id,
                    scheme=DefenseScheme.MAN_TO_MAN,
                    confidence=min(man_ratio, 1.0),
                    defender_distances=distances,
                    formation=list(defender_positions),
                )
                self._add_record(record)
                return record

            # 4. 존 수비 유형 분류
            zone_scheme, zone_conf = self._classify_zone(defender_positions, court_length)
            record = _PossessionDefense(
                possession_id=possession_id,
                scheme=zone_scheme,
                confidence=zone_conf,
                defender_distances=distances,
                formation=list(defender_positions),
            )
            self._add_record(record)
            return record

    # ------------------------------------------------------------------
    # 스킴 빈도 조회
    # ------------------------------------------------------------------
    def get_scheme_frequency(self) -> dict[str, float]:
        """스킴별 사용 빈도 (%)."""
        with self._lock:
            if self._total == 0:
                return {}
            return {
                scheme.value: (count / self._total) * 100.0
                for scheme, count in self._scheme_counts.items()
                if count > 0
            }

    def get_scheme_count(self, scheme: DefenseScheme) -> int:
        """특정 스킴 사용 횟수."""
        with self._lock:
            return self._scheme_counts.get(scheme, 0)

    # ------------------------------------------------------------------
    # 통계 / 리셋
    # ------------------------------------------------------------------
    def get_stats(self) -> dict[str, object]:
        """운영 통계."""
        with self._lock:
            return {
                "total_classified": self._total,
                "primary_scheme": self.primary_scheme.value,
                "scheme_frequency": self.get_scheme_frequency(),
                "records_cached": len(self._records),
            }

    def reset(self) -> None:
        """모든 상태 초기화."""
        with self._lock:
            self._records.clear()
            self._scheme_counts = {s: 0 for s in DefenseScheme}
            self._total = 0

    def __repr__(self) -> str:
        return (
            f"DefenseTypeClassifier(total={self._total}, "
            f"primary={self.primary_scheme.value})"
        )

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------
    def _add_record(self, record: _PossessionDefense) -> None:
        """기록 추가 + 메모리 가드."""
        self._records.append(record)
        self._scheme_counts[record.scheme] = (
            self._scheme_counts.get(record.scheme, 0) + 1
        )
        self._total += 1
        if len(self._records) > self._config.max_records:
            self._trim_records()

    def _trim_records(self) -> None:
        """오래된 기록 제거 (FIFO)."""
        overflow = len(self._records) - self._config.max_records
        if overflow > 0:
            self._records = self._records[overflow:]
            logger.debug("수비 분류 기록 %d건 제거", overflow)

    def _calculate_matchup_distances(
        self,
        defenders: list[tuple[float, float]],
        offenders: list[tuple[float, float]],
    ) -> list[float]:
        """
        각 수비자에 대해 가장 가까운 공격자와의 거리.

        헝가리안 알고리즘 대신 간단한 최근접 매칭 (O(n²), n=5).
        """
        distances: list[float] = []
        for dx, dy in defenders:
            min_dist = float("inf")
            for ox, oy in offenders:
                dist = ((dx - ox) ** 2 + (dy - oy) ** 2) ** 0.5
                if dist < min_dist:
                    min_dist = dist
            distances.append(min_dist)
        return distances

    def _detect_press(
        self,
        defenders: list[tuple[float, float]],
        court_length: float,
    ) -> DefenseScheme | None:
        """프레스 수비 감지: 수비자 평균 y가 하프라인 이상."""
        if not defenders:
            return None
        half = court_length / 2.0
        avg_y = sum(y for _, y in defenders) / len(defenders)
        ratio = avg_y / court_length if court_length > 0 else 0

        if ratio >= self._config.press_halfline_ratio:
            return DefenseScheme.FULL_COURT_PRESS
        if ratio >= self._config.press_halfline_ratio * 0.85:
            return DefenseScheme.HALF_COURT_PRESS
        return None

    def _detect_special_defense(
        self,
        distances: list[float],
        defenders: list[tuple[float, float]],
    ) -> DefenseScheme | None:
        """
        특수 수비 감지: 박스앤원 / 트라이앵글앤투.

        박스앤원: 1명만 극밀착 + 나머지 4명 존 배치
        트라이앵글앤투: 2명 밀착 + 나머지 3명 존 배치
        """
        tight_distance = self._config.special_defense_single_mark_distance * 0.5
        tight_count = sum(1 for d in distances if d <= tight_distance)

        if tight_count == 1:
            return DefenseScheme.BOX_AND_ONE
        if tight_count == 2:
            return DefenseScheme.TRIANGLE_AND_TWO
        return None

    def _classify_zone(
        self,
        defenders: list[tuple[float, float]],
        court_length: float,
    ) -> tuple[DefenseScheme, float]:
        """
        존 수비 세부 유형 분류.

        수비 포메이션을 정규화 좌표로 변환 후
        각 존 패턴과의 유사도를 비교하여 가장 유사한 존 선택.
        """
        if len(defenders) < 5:
            return DefenseScheme.ZONE_2_3, 0.50  # 폴백

        # 정규화: x → [-1, 1], y → [0, 1] (하프코트 기준)
        half = court_length / 2.0
        court_width = 15.0  # FIBA 코트 폭
        half_width = court_width / 2.0

        normalized: list[tuple[float, float]] = []
        for x, y in defenders:
            nx = max(-1.0, min(1.0, x / half_width)) if half_width > 0 else 0.0
            ny = max(0.0, min(1.0, y / half)) if half > 0 else 0.0
            normalized.append((nx, ny))

        # y값 기준 정렬 (상단 → 하단)
        normalized.sort(key=lambda p: -p[1])

        best_scheme = DefenseScheme.ZONE_2_3
        best_similarity = 0.0

        for scheme, pattern in _ZONE_PATTERNS.items():
            similarity = self._formation_similarity(normalized, pattern)
            if similarity > best_similarity:
                best_similarity = similarity
                best_scheme = scheme

        # 매치업 존 감지: 존 형태이지만 부분적 맨투맨 특성
        if best_similarity < self._config.zone_similarity_threshold:
            return DefenseScheme.MATCHUP_ZONE, max(best_similarity, 0.40)

        return best_scheme, best_similarity

    @staticmethod
    def _formation_similarity(
        actual: list[tuple[float, float]],
        pattern: list[tuple[float, float]],
    ) -> float:
        """
        포메이션 유사도 (0~1).

        실제 위치와 패턴 위치 간 평균 최소 거리의 역수.
        완벽 일치 = 1.0, 완전 불일치 → 0에 가까움.
        """
        if not actual or not pattern:
            return 0.0

        total_dist = 0.0
        used: set[int] = set()
        for ax, ay in actual:
            min_dist = float("inf")
            min_idx = 0
            for i, (px, py) in enumerate(pattern):
                if i in used:
                    continue
                dist = ((ax - px) ** 2 + (ay - py) ** 2) ** 0.5
                if dist < min_dist:
                    min_dist = dist
                    min_idx = i
            used.add(min_idx)
            total_dist += min_dist

        avg_dist = total_dist / len(actual)
        # 거리 0 → 유사도 1.0, 거리 1.0 → ~0.37, 거리 2.0 → ~0.14
        import math
        return math.exp(-avg_dist * 2.0)


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "DefenseTypeClassifier",
    "DefenseTypeClassifierConfig",
]

__version__ = "1.0.0"
