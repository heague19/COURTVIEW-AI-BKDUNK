# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: visual_feedback_generator.py
설명: 시각 피드백 메타데이터 생성기.
      - 슛 차트 오버레이, 히트맵, 이동 경로, 플레이 다이어그램
      - 슛존/패스 네트워크/수비 범위/리바운드 위치 등 17종 시각화
      - 시각화 메타데이터 구조 생성 (실제 렌더링은 프론트엔드)
      - game_feedback.yaml visual_feedback 설정 참조

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from shared.dto.feedback_dto import (
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackType,
)
from shared.constants.player_constants import AgeGroup


# =============================================================================
# 시각 피드백 메타데이터
# =============================================================================
@dataclass(slots=True, frozen=True)
class VisualElement:
    """시각 피드백 개별 요소."""

    element_type: str        # shot_chart, heatmap, movement_trail, play_diagram 등
    title: str               # 시각화 제목
    description: str         # 설명
    data_key: str            # 프론트에서 참조할 데이터 키
    priority: int = 1        # 렌더링 우선순위 (1=최고)


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class VisualFeedbackConfig:
    """시각 피드백 생성 설정."""

    max_items: int = 20
    age_group: AgeGroup = AgeGroup.ADULT

    # === 기본 시각화 ===
    include_shot_chart: bool = True
    include_heatmap: bool = True
    include_movement_trail: bool = True
    include_play_diagram: bool = True

    # === 슛 분석 시각화 ===
    include_shot_zone: bool = True
    include_shot_distance: bool = True
    include_hot_cold_zone: bool = True

    # === 이동/수비 시각화 ===
    include_movement_distance: bool = True
    include_defensive_coverage: bool = True

    # === 팀 전술 시각화 ===
    include_pass_network: bool = True
    include_spacing_metrics: bool = True
    include_possession_flow: bool = True
    include_fast_break_chart: bool = True

    # === 경기 흐름 시각화 ===
    include_quarter_comparison: bool = True
    include_rebound_chart: bool = True
    include_turnover_map: bool = True
    include_shot_clock_dist: bool = True

    # 히트맵 해상도
    heatmap_grid_x: int = 50
    heatmap_grid_y: int = 47

    # 오버레이 투명도
    overlay_opacity: float = 0.6


# =============================================================================
# 시각화 항목 정의 (element_type, title, description, data_key)
# =============================================================================
_VIS_DEFS: tuple[tuple[str, str, str, str], ...] = (
    # 0: shot_chart
    ("shot_chart_overlay", "슛 차트 오버레이",
     "코트 위 슈팅 위치 시각화", "shot_chart_data"),
    # 1: heatmap
    ("heatmap", "이동 히트맵",
     "선수 이동 빈도 히트맵", "heatmap_data"),
    # 2: movement_trail
    ("movement_trail", "이동 경로",
     "선수 이동 경로 시각화", "movement_trail_data"),
    # 3: play_diagram
    ("play_diagram", "플레이 다이어그램",
     "플레이 전개도 시각화", "play_diagram_data"),
    # 4: shot_zone
    ("shot_zone_breakdown", "슛 존 분석",
     "구역별 슈팅 분포 및 성공률", "shot_zone_data"),
    # 5: shot_distance
    ("shot_distance_chart", "슈팅 거리 분포",
     "근거리/중거리/장거리 슈팅 비율", "shot_distance_data"),
    # 6: hot_cold_zone
    ("hot_cold_zone", "핫/콜드 존",
     "구역별 슈팅 효율 히트맵 오버레이", "hot_cold_data"),
    # 7: movement_distance
    ("movement_distance_summary", "이동 거리 요약",
     "선수별 총 이동 거리 비교 차트", "movement_distance_data"),
    # 8: defensive_coverage
    ("defensive_coverage", "수비 커버리지",
     "수비 포지셔닝 범위 히트맵", "defensive_coverage_data"),
    # 9: pass_network
    ("pass_network", "패스 네트워크",
     "선수 간 패싱 연결도 시각화", "pass_network_data"),
    # 10: spacing_metrics
    ("spacing_overlay", "스페이싱 메트릭",
     "팀 간격 및 코트 활용도 오버레이", "spacing_data"),
    # 11: possession_flow
    ("possession_flow", "포제션 흐름",
     "볼 이동 패턴 및 공격 전개 경로", "possession_flow_data"),
    # 12: fast_break_chart
    ("fast_break_chart", "속공 분석 차트",
     "속공 vs 하프코트 공격 비교", "fast_break_data"),
    # 13: quarter_comparison
    ("quarter_comparison", "쿼터별 비교",
     "쿼터별 득점/효율 비교 차트", "quarter_comparison_data"),
    # 14: rebound_chart
    ("rebound_position_chart", "리바운드 위치",
     "리바운드 발생 위치 분포", "rebound_position_data"),
    # 15: turnover_map
    ("turnover_location_map", "턴오버 위치",
     "턴오버 발생 위치 및 유형 분포", "turnover_location_data"),
    # 16: shot_clock_dist
    ("shot_clock_distribution", "샷클락 분포",
     "샷클락 구간별 슈팅 시도 분포", "shot_clock_data"),
)


# =============================================================================
# VisualFeedbackGenerator 클래스
# =============================================================================
class VisualFeedbackGenerator:
    """
    시각 피드백 메타데이터 생성기.

    분석 결과를 기반으로 프론트엔드가 렌더링할 시각 피드백의
    메타데이터를 FeedbackItem 형태로 생성합니다.
    실제 이미지/차트 렌더링은 프론트엔드에서 수행합니다.
    """

    __slots__ = ("_config", "_lock", "_total_generated")

    def __init__(self, config: VisualFeedbackConfig | None = None) -> None:
        self._config: VisualFeedbackConfig = config or VisualFeedbackConfig()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "VisualFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    # -------------------------------------------------------------------------
    # 핵심: FeedbackItem 목록 생성
    # -------------------------------------------------------------------------
    def generate(
        self,
        *,
        has_shot_data: bool = False,
        has_tracking_data: bool = False,
        has_play_data: bool = False,
        has_defensive_data: bool = False,
        has_passing_data: bool = False,
        has_rebound_data: bool = False,
        has_turnover_data: bool = False,
        shot_count: int = 0,
        player_count: int = 0,
        quarter_count: int = 0,
    ) -> list[FeedbackItem]:
        """
        시각 피드백 메타데이터 생성.

        실제 데이터가 있는 항목만 시각 피드백으로 포함합니다.

        Args:
            has_shot_data: 슛 데이터 존재 여부
            has_tracking_data: 트래킹 데이터 존재 여부
            has_play_data: 플레이 데이터 존재 여부
            has_defensive_data: 수비 데이터 존재 여부
            has_passing_data: 패싱 데이터 존재 여부
            has_rebound_data: 리바운드 데이터 존재 여부
            has_turnover_data: 턴오버 데이터 존재 여부
            shot_count: 슛 시도 횟수
            player_count: 트래킹된 선수 수
            quarter_count: 쿼터 수

        Returns:
            FeedbackItem 목록 (시각 피드백 메타데이터)
        """
        items: list[FeedbackItem] = []
        cfg = self._config

        # 1. 슛 차트
        if cfg.include_shot_chart and has_shot_data and shot_count > 0:
            items.append(self._make(
                "슛 차트",
                f"총 {shot_count}개의 슈팅 위치를 코트 위에 표시합니다. "
                f"성공/실패를 색상으로 구분합니다.",
            ))

        # 2. 히트맵
        if cfg.include_heatmap and has_tracking_data:
            items.append(self._make(
                "이동 히트맵",
                f"선수 {player_count}명의 이동 히트맵입니다. "
                f"빈도가 높은 구역이 밝게 표시됩니다.",
            ))

        # 3. 이동 경로
        if cfg.include_movement_trail and has_tracking_data:
            items.append(self._make(
                "이동 경로",
                "주요 선수의 이동 경로를 시각적으로 표시합니다.",
            ))

        # 4. 플레이 다이어그램
        if cfg.include_play_diagram and has_play_data:
            items.append(self._make(
                "플레이 다이어그램",
                "주요 플레이의 선수 이동과 패싱 경로를 다이어그램으로 표시합니다.",
            ))

        # 5. 슛 존 분석
        if cfg.include_shot_zone and has_shot_data and shot_count > 0:
            items.append(self._make(
                "슛 존 분석",
                f"코트를 구역별로 나누어 {shot_count}개 슈팅의 분포와 성공률을 표시합니다. "
                f"페인트존, 미드레인지, 3점 라인별 효율을 한눈에 비교할 수 있습니다.",
            ))

        # 6. 슈팅 거리 분포
        if cfg.include_shot_distance and has_shot_data and shot_count > 0:
            items.append(self._make(
                "슈팅 거리 분포",
                "근거리(0-3m), 중거리(3-6.75m), 장거리(6.75m+) 구간별 "
                "슈팅 시도 비율과 성공률을 바 차트로 표시합니다.",
            ))

        # 7. 핫/콜드 존
        if cfg.include_hot_cold_zone and has_shot_data and shot_count >= 5:
            items.append(self._make(
                "핫/콜드 존",
                "코트를 격자로 분할하여 리그 평균 대비 슈팅 효율이 높은 구역(핫존)과 "
                "낮은 구역(콜드존)을 색상 그라데이션으로 표시합니다.",
            ))

        # 8. 이동 거리 요약
        if cfg.include_movement_distance and has_tracking_data and player_count > 0:
            items.append(self._make(
                "이동 거리 요약",
                f"트래킹된 {player_count}명 선수의 총 이동 거리를 비교합니다. "
                f"가장 많이 뛴 선수와 최소 이동 선수를 한눈에 파악할 수 있습니다.",
            ))

        # 9. 수비 커버리지
        if cfg.include_defensive_coverage and has_defensive_data:
            items.append(self._make(
                "수비 커버리지",
                "수비 시 각 선수의 위치 분포를 히트맵으로 표시합니다. "
                "수비 커버 범위가 넓은 선수와 좁은 선수를 시각적으로 비교합니다.",
            ))

        # 10. 패스 네트워크
        if cfg.include_pass_network and has_passing_data:
            items.append(self._make(
                "패스 네트워크",
                "선수 간 패스 빈도와 방향을 네트워크 그래프로 표시합니다. "
                "핵심 패스 경로와 고립된 선수를 파악할 수 있습니다.",
            ))

        # 11. 스페이싱 메트릭
        if cfg.include_spacing_metrics and has_tracking_data and player_count >= 5:
            items.append(self._make(
                "스페이싱 메트릭",
                "공격 시 5명 선수 간의 평균 거리와 코트 활용 면적을 "
                "오버레이로 표시합니다. 밀집 구간과 개방 구간을 확인할 수 있습니다.",
            ))

        # 12. 포제션 흐름
        if cfg.include_possession_flow and has_play_data and has_tracking_data:
            items.append(self._make(
                "포제션 흐름",
                "공격 포제션별 볼 이동 경로를 화살표로 표시합니다. "
                "패스, 드리블, 슈팅으로 이어지는 공격 패턴을 분석합니다.",
            ))

        # 13. 속공 분석 차트
        if cfg.include_fast_break_chart and has_tracking_data and has_play_data:
            items.append(self._make(
                "속공 분석 차트",
                "속공 공격과 하프코트 공격의 비율 및 득점 효율을 비교합니다. "
                "전환 공격의 효과를 시각적으로 확인할 수 있습니다.",
            ))

        # 14. 쿼터별 비교
        if cfg.include_quarter_comparison and quarter_count >= 2:
            items.append(self._make(
                "쿼터별 비교",
                f"{quarter_count}개 쿼터의 득점, 슈팅 효율, 턴오버 추이를 "
                f"라인 차트로 비교합니다. 경기 흐름 변화를 한눈에 파악합니다.",
            ))

        # 15. 리바운드 위치
        if cfg.include_rebound_chart and has_rebound_data:
            items.append(self._make(
                "리바운드 위치",
                "공격/수비 리바운드 발생 위치를 코트 위에 산점도로 표시합니다. "
                "리바운드 집중 구역과 박스아웃 효과를 분석합니다.",
            ))

        # 16. 턴오버 위치
        if cfg.include_turnover_map and has_turnover_data:
            items.append(self._make(
                "턴오버 위치",
                "턴오버 발생 위치와 유형(패스 미스, 트래블링, 스틸 당함 등)을 "
                "코트 위에 마커로 표시합니다.",
            ))

        # 17. 샷클락 분포
        if cfg.include_shot_clock_dist and has_shot_data and shot_count >= 5:
            items.append(self._make(
                "샷클락 분포",
                "샷클락 구간별(얼리/미드/레이트) 슈팅 시도 분포를 표시합니다. "
                "팀의 공격 템포와 샷 셀렉션 타이밍을 분석합니다.",
            ))

        with self._lock:
            self._total_generated += 1

        return items

    # -------------------------------------------------------------------------
    # 시각화 요소 메타데이터
    # -------------------------------------------------------------------------
    def get_visual_elements(
        self,
        *,
        has_shot_data: bool = False,
        has_tracking_data: bool = False,
        has_play_data: bool = False,
        has_defensive_data: bool = False,
        has_passing_data: bool = False,
        has_rebound_data: bool = False,
        has_turnover_data: bool = False,
        quarter_count: int = 0,
        shot_count: int = 0,
        player_count: int = 0,
    ) -> list[VisualElement]:
        """
        시각화 요소 메타데이터 목록 반환.

        프론트엔드에서 어떤 시각화를 렌더링할지 결정하는 데 사용됩니다.
        """
        elements: list[VisualElement] = []
        cfg = self._config
        pri = 0  # 우선순위 카운터

        # (조건, 정의 인덱스) 매핑
        checks: list[tuple[bool, int]] = [
            (cfg.include_shot_chart and has_shot_data, 0),
            (cfg.include_heatmap and has_tracking_data, 1),
            (cfg.include_movement_trail and has_tracking_data, 2),
            (cfg.include_play_diagram and has_play_data, 3),
            (cfg.include_shot_zone and has_shot_data and shot_count > 0, 4),
            (cfg.include_shot_distance and has_shot_data and shot_count > 0, 5),
            (cfg.include_hot_cold_zone and has_shot_data and shot_count >= 5, 6),
            (cfg.include_movement_distance and has_tracking_data and player_count > 0, 7),
            (cfg.include_defensive_coverage and has_defensive_data, 8),
            (cfg.include_pass_network and has_passing_data, 9),
            (cfg.include_spacing_metrics and has_tracking_data and player_count >= 5, 10),
            (cfg.include_possession_flow and has_play_data and has_tracking_data, 11),
            (cfg.include_fast_break_chart and has_tracking_data and has_play_data, 12),
            (cfg.include_quarter_comparison and quarter_count >= 2, 13),
            (cfg.include_rebound_chart and has_rebound_data, 14),
            (cfg.include_turnover_map and has_turnover_data, 15),
            (cfg.include_shot_clock_dist and has_shot_data and shot_count >= 5, 16),
        ]

        for cond, idx in checks:
            if cond:
                pri += 1
                et, title, desc, dk = _VIS_DEFS[idx]
                elements.append(VisualElement(
                    element_type=et,
                    title=title,
                    description=desc,
                    data_key=dk,
                    priority=pri,
                ))

        return elements

    # -------------------------------------------------------------------------
    # 유틸리티
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"VisualFeedbackGenerator(generated={self._total_generated})"

    @staticmethod
    def _make(title: str, description: str, **kw) -> FeedbackItem:
        """FeedbackItem 생성 헬퍼."""
        return FeedbackItem(
            category=kw.pop("category", FeedbackCategory.TIP),
            feedback_type=kw.pop("feedback_type", FeedbackType.TIP),
            priority=kw.pop("priority", FeedbackPriority.OPTIONAL),
            title=title,
            description=description,
            confidence=kw.pop("confidence", 1.0),
            **kw,
        )


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "VisualFeedbackGenerator",
    "VisualFeedbackConfig",
    "VisualElement",
]

__version__ = "1.0.0"
