# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: feedback_system/analysis
파일: spatial_feedback.py
설명: 공간 분석 피드백 생성기 (전력분석원 수준).
      - 코트 활용도, 스페이싱, 드라이브 레인, 페인트 터치
      - 스페이싱 품질/일관성, 페인트 밀도, 약사이드 배치
      - 코너 스페이싱, 볼사이드 혼잡도, 종합 등급
      - SpacingData → FeedbackItem 변환 (15+ 항목)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-25
버전: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from shared.constants.feedback_constants import (
    FEEDBACK_MIN_DETAIL_POINTS,
    FeedbackSeverity,
)
from shared.dto.feedback_dto import (
    FeedbackCategory,
    FeedbackItem,
    FeedbackPriority,
    FeedbackType,
)
from shared.constants.player_constants import AgeGroup
from shared.dto.tactical_dto import SpacingData

from feedback_system.templates.feedback_formatter import FeedbackFormatter
from feedback_system.templates.korean_templates import KoreanTemplates
from feedback_system.templates.severity_mapper import SeverityMapper
from feedback_system.templates import get_default_severity_mapper, get_default_korean_templates


# =============================================================================
# 설정
# =============================================================================
@dataclass(slots=True)
class SpatialFeedbackConfig:
    """공간 분석 피드백 생성 설정."""

    min_items: int = FEEDBACK_MIN_DETAIL_POINTS
    max_items: int = 25
    age_group: AgeGroup = AgeGroup.ADULT

    # --- 기존 5개 분석 임계값 ---
    court_utilization_good: float = 65.0   # 코트 활용률 65%+ → 양호
    avg_spacing_good: float = 4.5          # 평균 간격 4.5m+ → 양호
    drive_lane_good: float = 60.0          # 드라이브 레인 개방도 60+ → 양호
    three_point_spacing_good: float = 5.0  # 3점 스페이싱 5.0m+ → 양호
    paint_touch_good: float = 0.3          # 페인트 터치 0.3+/점유 → 양호

    # --- 6. 스페이싱 품질 평가 ---
    spacing_quality_good: float = 70.0     # 스페이싱 품질 70+ → 양호
    spacing_quality_excellent: float = 85.0  # 스페이싱 품질 85+ → 우수

    # --- 7. 페인트 밀도 분석 ---
    paint_density_high: float = 0.50       # 페인트 터치 0.5+ → 높은 페인트 활용
    paint_density_low: float = 0.15        # 페인트 터치 0.15 미만 → 페인트 미활용

    # --- 8. 평균 간격 vs 최적 벤치마크 ---
    optimal_spacing_benchmark: float = 5.0  # NBA/FIBA 평균 최적 간격 5.0m
    spacing_deviation_warn: float = 1.5     # 편차 1.5m 이상 → 경고

    # --- 9. 스페이싱 일관성 (분산 추정) ---
    # 3점 간격 대비 평균 간격 비율로 분산 추정
    spacing_consistency_tight: float = 0.85  # 비율 0.85 이하 → 밀집
    spacing_consistency_loose: float = 1.25  # 비율 1.25 이상 → 과도 분산

    # --- 10. 약사이드 스페이싱 ---
    weak_side_ratio_good: float = 1.0       # 3점 간격/평균 간격 ≥ 1.0 → 양호

    # --- 11. 코너 스페이싱 기회 ---
    corner_opportunity_threshold: float = 5.5  # 3점 간격 5.5+ → 코너 기회 확보
    court_util_for_corner: float = 60.0        # 코트 활용률 60+ → 코너 배치 가능

    # --- 12. 볼사이드 혼잡도 경고 ---
    congestion_spacing_low: float = 3.8     # 평균 간격 3.8m 미만
    congestion_drive_low: float = 45.0      # 드라이브 레인 개방도 45 미만

    # --- 13. 스페이싱 품질 추세 (품질 → 실행 가능 조언) ---
    trend_action_threshold: float = 60.0    # 품질 60 미만 → 즉시 조치

    # --- 14. 페인트 밀도 vs 득점 효율 ---
    paint_efficiency_ratio_good: float = 0.35  # 페인트 터치 + 드라이브 개방도 결합

    # --- 15. 종합 등급 ---
    grade_a_threshold: float = 80.0   # 종합 80+ → A
    grade_b_threshold: float = 65.0   # 종합 65+ → B
    grade_c_threshold: float = 50.0   # 종합 50+ → C


# =============================================================================
# SpatialFeedbackGenerator 클래스
# =============================================================================
class SpatialFeedbackGenerator:
    """
    공간 분석 피드백 생성기.

    SpacingData를 입력받아 코트 활용도, 선수 간격,
    드라이브 레인, 페인트 터치, 스페이싱 품질, 약사이드 배치,
    코너 기회, 볼사이드 혼잡도, 종합 등급 등
    전력분석원급 피드백을 생성합니다 (15+ FeedbackItem).
    """

    __slots__ = (
        "_config",
        "_severity_mapper",
        "_templates",
        "_lock",
        "_total_generated",
    )

    def __init__(self, config: SpatialFeedbackConfig | None = None) -> None:
        self._config: SpatialFeedbackConfig = config or SpatialFeedbackConfig()
        self._severity_mapper = get_default_severity_mapper()
        self._templates = get_default_korean_templates()
        self._lock: RLock = RLock()
        self._total_generated: int = 0

    @property
    def name(self) -> str:
        return "SpatialFeedbackGenerator"

    @property
    def total_generated(self) -> int:
        return self._total_generated

    def generate(
        self,
        spacing: SpacingData,
    ) -> list[FeedbackItem]:
        """공간 분석 결과에서 전력분석원급 피드백 생성 (15+ 항목)."""
        items: list[FeedbackItem] = []
        cfg = self._config

        # 유효한 데이터가 하나도 없으면 빈 리스트
        util = spacing.court_utilization_pct
        avg_sp = spacing.avg_player_spacing
        drive = spacing.drive_lane_openness
        three_sp = spacing.three_point_spacing
        paint = spacing.paint_touch_frequency

        has_data = any(v > 0 for v in (util, avg_sp, drive, three_sp, paint))
        if not has_data:
            return items

        # === 1. 코트 활용도 ===
        if util > 0:
            items.append(self._court_utilization(util, cfg))

        # === 2. 평균 선수 간격 (플로어 스페이싱) ===
        if avg_sp > 0:
            items.append(self._avg_spacing(avg_sp, cfg))

        # === 3. 드라이브 레인 개방도 ===
        if drive > 0:
            items.append(self._drive_lane(drive, cfg))

        # === 4. 3점 라인 스페이싱 ===
        if three_sp > 0:
            items.append(self._three_point(three_sp, cfg))

        # === 5. 페인트 터치 빈도 ===
        if paint > 0:
            items.append(self._paint_touch(paint, cfg))

        # === 6. 스페이싱 품질 평가 (종합 품질 지수) ===
        if avg_sp > 0 and drive > 0:
            items.append(self._spacing_quality(avg_sp, drive, util, cfg))

        # === 7. 페인트 밀도 분석 ===
        if paint > 0:
            items.append(self._paint_density(paint, cfg))

        # === 8. 평균 간격 vs 최적 벤치마크 비교 ===
        if avg_sp > 0:
            items.append(self._spacing_vs_benchmark(avg_sp, cfg))

        # === 9. 스페이싱 일관성 (분산 분석) ===
        if avg_sp > 0 and three_sp > 0:
            items.append(self._spacing_consistency(avg_sp, three_sp, cfg))

        # === 10. 약사이드 스페이싱 ===
        if avg_sp > 0 and three_sp > 0:
            items.append(self._weak_side_spacing(avg_sp, three_sp, cfg))

        # === 11. 코너 스페이싱 기회 ===
        if three_sp > 0 and util > 0:
            items.append(self._corner_opportunity(three_sp, util, cfg))

        # === 12. 볼사이드 혼잡도 경고 ===
        if avg_sp > 0 and drive > 0:
            items.append(self._congestion_warning(avg_sp, drive, cfg))

        # === 13. 스페이싱 품질 추세 → 실행 가능 조언 ===
        if avg_sp > 0 and drive > 0:
            items.append(self._spacing_trend_action(avg_sp, drive, util, cfg))

        # === 14. 페인트 밀도 vs 득점 효율 ===
        if paint > 0 and drive > 0:
            items.append(self._paint_scoring_efficiency(paint, drive, cfg))

        # === 15. 종합 공간 등급 ===
        items.append(self._overall_spatial_grade(
            util, avg_sp, drive, three_sp, paint, cfg,
        ))

        with self._lock:
            self._total_generated += 1

        return items

    # =========================================================================
    # 1. 코트 활용도
    # =========================================================================
    def _court_utilization(
        self, util: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        good = util >= cfg.court_utilization_good
        sev = self._severity_mapper.from_score(util)
        if util >= 80.0:
            desc_detail = (
                "코트 전 영역을 매우 효과적으로 활용하고 있습니다. "
                "수비 로테이션 부담을 극대화하는 이상적인 포지셔닝입니다."
            )
        elif good:
            desc_detail = (
                "코트 전체를 효과적으로 활용하고 있습니다. "
                "주요 구역 간 균형 잡힌 점유율을 유지하세요."
            )
        elif util >= 50.0:
            desc_detail = (
                "코트의 절반 정도만 활용되고 있습니다. "
                "약사이드와 코너 영역으로 공간 확장을 시도하세요."
            )
        else:
            desc_detail = (
                "특정 구역에 심하게 편중되어 있습니다. "
                "오프볼 무브먼트와 스크린 플레이로 코트 전체를 활용하세요."
            )
        return self._make(
            category=FeedbackCategory.FOOTWORK,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.CORRECTION,
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="코트 활용도",
            description=f"코트 활용률 {util:.0f}%. {desc_detail}",
            current_value=util,
            ideal_value=cfg.court_utilization_good,
            unit="percent",
            confidence=0.85,
        )

    # =========================================================================
    # 2. 평균 선수 간격
    # =========================================================================
    def _avg_spacing(
        self, avg_sp: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        good = avg_sp >= cfg.avg_spacing_good
        if avg_sp >= 5.5:
            desc_detail = (
                "선수 간 간격이 넓어 패싱 레인과 드라이브 레인이 "
                "충분히 확보됩니다. 수비 수축을 방지하는 이상적 배치입니다."
            )
        elif good:
            desc_detail = (
                "선수 간 간격이 충분하여 패싱 레인이 확보됩니다. "
                "현재 간격을 유지하면서 볼 무브먼트를 이어가세요."
            )
        elif avg_sp >= 3.5:
            desc_detail = (
                "선수 간 간격이 다소 좁습니다. 수비가 헬프사이드로 "
                "쉽게 수축할 수 있어 간격을 넓히는 것이 필요합니다."
            )
        else:
            desc_detail = (
                "선수들이 뭉쳐 있어 수비가 쉽습니다. "
                "오프볼 무브와 스크린을 활용해 간격을 넓히세요."
            )
        return self._make(
            category=FeedbackCategory.COORDINATION,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="플로어 스페이싱",
            description=f"평균 선수 간격 {avg_sp:.1f}m. {desc_detail}",
            current_value=avg_sp,
            ideal_value=cfg.avg_spacing_good,
            unit="m",
            confidence=0.85,
        )

    # =========================================================================
    # 3. 드라이브 레인 개방도
    # =========================================================================
    def _drive_lane(
        self, drive: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        good = drive >= cfg.drive_lane_good
        sev = self._severity_mapper.from_score(drive)
        if drive >= 80.0:
            desc_detail = (
                "돌파 경로가 완전히 개방되어 드라이브 & 킥아웃 전술에 최적입니다. "
                "적극적인 침투를 통해 수비를 붕괴시키세요."
            )
        elif good:
            desc_detail = (
                "돌파 경로가 잘 확보되어 드라이브가 용이합니다. "
                "침투 후 킥아웃으로 오픈 슛 기회를 만들어 보세요."
            )
        elif drive >= 40.0:
            desc_detail = (
                "돌파 경로가 부분적으로 막혀 있습니다. "
                "스크린과 오프볼 무브로 레인 확보가 필요합니다."
            )
        else:
            desc_detail = (
                "돌파 경로가 심하게 막혀 있습니다. 스크린 플레이와 "
                "패싱으로 수비 구조를 먼저 흔든 뒤 침투를 시도하세요."
            )
        return self._make(
            category=FeedbackCategory.RELEASE,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.CORRECTION,
            priority=FeedbackFormatter.severity_to_priority(sev.severity),
            title="드라이브 레인 개방도",
            description=f"드라이브 레인 개방도 {drive:.0f}점. {desc_detail}",
            current_value=drive,
            ideal_value=cfg.drive_lane_good,
            confidence=0.85,
        )

    # =========================================================================
    # 4. 3점 라인 스페이싱
    # =========================================================================
    def _three_point(
        self, three_sp: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        good = three_sp >= cfg.three_point_spacing_good
        if three_sp >= 6.0:
            desc_detail = (
                "3점 슈터 배치가 매우 균형적이며 수비 로테이션을 "
                "최대한 늘릴 수 있는 배치입니다."
            )
        elif good:
            desc_detail = "3점 슈터 배치가 균형적입니다."
        else:
            desc_detail = (
                "3점 슈터가 한쪽에 몰려 있습니다. "
                "양 코너와 탑을 고루 활용해 수비 범위를 넓히세요."
            )
        return self._make(
            category=FeedbackCategory.COORDINATION,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="3점 라인 스페이싱",
            description=f"3점 슈터 간 평균 간격 {three_sp:.1f}m. {desc_detail}",
            current_value=three_sp,
            ideal_value=cfg.three_point_spacing_good,
            unit="m",
            confidence=0.80,
        )

    # =========================================================================
    # 5. 페인트 터치 빈도
    # =========================================================================
    def _paint_touch(
        self, paint: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        good = paint >= cfg.paint_touch_good
        if paint >= 0.5:
            desc_detail = (
                "매우 적극적인 페인트 침투가 이루어지고 있습니다. "
                "수비 파울 유도와 킥아웃 패스를 병행하면 더욱 효과적입니다."
            )
        elif good:
            desc_detail = (
                "적극적인 페인트 침투가 이루어지고 있습니다. "
                "킥아웃 패스와 병행하여 효율을 높이세요."
            )
        elif paint >= 0.15:
            desc_detail = (
                "페인트 침투가 다소 부족합니다. "
                "커팅과 드라이브 빈도를 늘려 수비를 수축시키세요."
            )
        else:
            desc_detail = (
                "페인트 침투가 매우 부족합니다. 점프슛에만 의존하면 "
                "득점 효율이 떨어집니다. 커팅과 드라이브를 적극 활용하세요."
            )
        return self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="페인트 터치 빈도",
            description=f"점유당 페인트 터치 {paint:.2f}회. {desc_detail}",
            current_value=paint,
            confidence=0.80,
        )

    # =========================================================================
    # 6. 스페이싱 품질 평가 (종합 품질 지수)
    # =========================================================================
    def _spacing_quality(
        self, avg_sp: float, drive: float, util: float,
        cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        """평균 간격 + 드라이브 레인 + 코트 활용률의 가중 합산 → 품질 지수."""
        # 간격 점수 (0~100): 4.5m 이상이면 100, 2.0m이면 0
        spacing_score = min(100.0, max(0.0, (avg_sp - 2.0) / 3.0 * 100.0))
        # 드라이브 레인은 이미 0~100
        # 코트 활용률은 이미 0~100
        util_adj = util if util > 0 else 50.0  # 데이터 없으면 중립값
        quality = spacing_score * 0.40 + drive * 0.35 + util_adj * 0.25

        if quality >= cfg.spacing_quality_excellent:
            label = "우수"
            fb_type = FeedbackType.POSITIVE
            desc_detail = (
                "공간 활용의 3대 요소(간격/드라이브 레인/코트 활용)가 "
                "모두 높은 수준입니다. 현재 배치를 유지하세요."
            )
        elif quality >= cfg.spacing_quality_good:
            label = "양호"
            fb_type = FeedbackType.POSITIVE
            desc_detail = (
                "전반적인 공간 활용이 양호합니다. "
                "약한 영역을 보완하면 상위 수준에 도달할 수 있습니다."
            )
        elif quality >= 50.0:
            label = "보통"
            fb_type = FeedbackType.IMPROVEMENT
            desc_detail = (
                "공간 활용이 평균 수준입니다. 선수 간 간격 확대와 "
                "오프볼 무브먼트 강화로 개선이 가능합니다."
            )
        else:
            label = "미흡"
            fb_type = FeedbackType.CORRECTION
            desc_detail = (
                "공간 활용 전반이 미흡합니다. 스크린 활용, 코너 배치, "
                "커팅 무브먼트를 통해 즉각적인 개선이 필요합니다."
            )
        return self._make(
            category=FeedbackCategory.COORDINATION,
            fb_type=fb_type,
            priority=FeedbackPriority.MEDIUM,
            title=f"스페이싱 품질: {label}",
            description=(
                f"스페이싱 품질 지수 {quality:.0f}/100 "
                f"(간격 {spacing_score:.0f} + 드라이브 {drive:.0f} + "
                f"코트활용 {util_adj:.0f} 가중합산). {desc_detail}"
            ),
            current_value=quality,
            ideal_value=cfg.spacing_quality_excellent,
            confidence=0.82,
        )

    # =========================================================================
    # 7. 페인트 밀도 분석
    # =========================================================================
    def _paint_density(
        self, paint: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        """페인트 터치 빈도를 밀도 관점에서 세분화 분석."""
        if paint >= cfg.paint_density_high:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title="페인트 밀도: 높음",
                description=(
                    f"점유당 페인트 터치 {paint:.2f}회로 높은 밀도입니다. "
                    f"공격의 중심이 페인트 존에 집중되어 있어 수비 파울 유도와 "
                    f"세컨드 찬스 포인트 확보에 유리합니다. "
                    f"외곽 슛과 병행하면 공격 다양성이 높아집니다."
                ),
                current_value=paint,
                confidence=0.80,
            )
        if paint >= cfg.paint_touch_good:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="페인트 밀도: 적정",
                description=(
                    f"점유당 페인트 터치 {paint:.2f}회로 적정 밀도입니다. "
                    f"페인트 침투와 외곽 공격의 균형이 잡혀 있습니다."
                ),
                current_value=paint,
                confidence=0.78,
            )
        if paint >= cfg.paint_density_low:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.IMPROVEMENT,
                priority=FeedbackPriority.LOW,
                title="페인트 밀도: 낮음",
                description=(
                    f"점유당 페인트 터치 {paint:.2f}회로 낮은 밀도입니다. "
                    f"외곽 의존도가 높아 슛 효율 변동이 클 수 있습니다. "
                    f"드라이브와 커팅으로 페인트 침투를 늘리세요."
                ),
                suggestion=(
                    "포스트업, 커팅, 드라이브를 통해 점유당 0.3회 이상의 "
                    "페인트 터치를 목표로 설정하세요."
                ),
                current_value=paint,
                confidence=0.78,
            )
        return self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="페인트 밀도: 매우 낮음",
            description=(
                f"점유당 페인트 터치 {paint:.2f}회로 매우 낮은 밀도입니다. "
                f"페인트 존 침투가 거의 이루어지지 않아 득점 효율이 "
                f"외곽 슛 적중률에 전적으로 의존합니다."
            ),
            suggestion=(
                "즉각적인 전술 조정이 필요합니다. 픽앤롤 빈도를 늘리고 "
                "커팅 플레이를 추가하여 페인트 침투를 강화하세요."
            ),
            current_value=paint,
            confidence=0.80,
        )

    # =========================================================================
    # 8. 평균 간격 vs 최적 벤치마크
    # =========================================================================
    def _spacing_vs_benchmark(
        self, avg_sp: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        """평균 간격을 NBA/FIBA 벤치마크와 비교."""
        benchmark = cfg.optimal_spacing_benchmark
        deviation = avg_sp - benchmark
        abs_dev = abs(deviation)

        if abs_dev <= 0.5:
            fb_type = FeedbackType.POSITIVE
            desc_detail = (
                f"최적 벤치마크({benchmark:.1f}m)에 매우 근접한 간격입니다. "
                f"현재 배치를 유지하면서 상황별 미세 조정을 하세요."
            )
        elif deviation > 0 and abs_dev <= cfg.spacing_deviation_warn:
            fb_type = FeedbackType.TIP
            desc_detail = (
                f"벤치마크 대비 {abs_dev:.1f}m 넓은 간격입니다. "
                f"수비 확장에 유리하지만 인사이드 연계가 느려질 수 있습니다."
            )
        elif deviation > 0:
            fb_type = FeedbackType.IMPROVEMENT
            desc_detail = (
                f"벤치마크 대비 {abs_dev:.1f}m 과도하게 넓습니다. "
                f"패싱 거리가 길어져 턴오버 위험이 증가합니다. "
                f"간격을 약간 좁혀 연계 플레이 속도를 높이세요."
            )
        elif abs_dev <= cfg.spacing_deviation_warn:
            fb_type = FeedbackType.IMPROVEMENT
            desc_detail = (
                f"벤치마크 대비 {abs_dev:.1f}m 좁은 간격입니다. "
                f"수비 수축에 취약할 수 있으니 약간 더 넓히세요."
            )
        else:
            fb_type = FeedbackType.CORRECTION
            desc_detail = (
                f"벤치마크 대비 {abs_dev:.1f}m 매우 좁습니다. "
                f"수비가 쉽게 도움수비와 더블팀이 가능합니다. "
                f"즉각적인 간격 확대가 필요합니다."
            )
        return self._make(
            category=FeedbackCategory.COORDINATION,
            fb_type=fb_type,
            priority=FeedbackPriority.LOW,
            title="벤치마크 대비 간격",
            description=(
                f"평균 간격 {avg_sp:.1f}m (벤치마크 {benchmark:.1f}m, "
                f"편차 {deviation:+.1f}m). {desc_detail}"
            ),
            current_value=avg_sp,
            ideal_value=benchmark,
            unit="m",
            confidence=0.80,
        )

    # =========================================================================
    # 9. 스페이싱 일관성 (분산 분석)
    # =========================================================================
    def _spacing_consistency(
        self, avg_sp: float, three_sp: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        """
        3점 간격 대비 평균 간격 비율로 스페이싱 일관성을 추정.
        비율이 1.0에 가까울수록 내/외곽 간격이 균일.
        """
        ratio = three_sp / avg_sp if avg_sp > 0 else 1.0

        if ratio < cfg.spacing_consistency_tight:
            label = "밀집"
            fb_type = FeedbackType.CORRECTION
            desc_detail = (
                f"3점 슈터 간격({three_sp:.1f}m)이 평균 간격({avg_sp:.1f}m) "
                f"대비 크게 좁아 외곽에서의 포지셔닝이 밀집되어 있습니다. "
                f"3점 슈터를 양 코너와 탑으로 분산 배치하세요."
            )
        elif ratio > cfg.spacing_consistency_loose:
            label = "과도 분산"
            fb_type = FeedbackType.IMPROVEMENT
            desc_detail = (
                f"3점 슈터 간격({three_sp:.1f}m)이 평균 간격({avg_sp:.1f}m) "
                f"대비 매우 넓어 인사이드 밀집이 의심됩니다. "
                f"내부 포지셔닝도 함께 넓혀 전체 균형을 맞추세요."
            )
        else:
            label = "균일"
            fb_type = FeedbackType.POSITIVE
            desc_detail = (
                f"3점 간격({three_sp:.1f}m)과 평균 간격({avg_sp:.1f}m)의 "
                f"비율이 {ratio:.2f}로 내외곽 간격이 균일합니다. "
                f"일관된 공간 활용을 유지하고 있습니다."
            )
        return self._make(
            category=FeedbackCategory.COORDINATION,
            fb_type=fb_type,
            priority=FeedbackPriority.LOW,
            title=f"스페이싱 일관성: {label}",
            description=(
                f"내외곽 간격 비율 {ratio:.2f} "
                f"(3점 {three_sp:.1f}m / 평균 {avg_sp:.1f}m). {desc_detail}"
            ),
            confidence=0.78,
        )

    # =========================================================================
    # 10. 약사이드 스페이싱
    # =========================================================================
    def _weak_side_spacing(
        self, avg_sp: float, three_sp: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        """
        약사이드(볼 반대편) 스페이싱 추정.
        3점 간격이 넓을수록 약사이드가 잘 벌려진 것으로 판단.
        """
        ratio = three_sp / avg_sp if avg_sp > 0 else 0.0
        good = ratio >= cfg.weak_side_ratio_good

        if ratio >= 1.2:
            desc_detail = (
                "약사이드 배치가 매우 우수합니다. 3점 슈터가 넓게 벌려져 "
                "수비 로테이션 거리가 길어 킥아웃 패스 기회가 풍부합니다."
            )
        elif good:
            desc_detail = (
                "약사이드 배치가 양호합니다. 볼 반대편 슈터가 적절히 "
                "배치되어 킥아웃 패스 옵션이 확보되어 있습니다."
            )
        elif ratio >= 0.8:
            desc_detail = (
                "약사이드 배치가 다소 부족합니다. 볼 반대편 공간이 좁아 "
                "수비가 빠르게 로테이션할 수 있습니다. "
                "약사이드 코너 포지셔닝을 강화하세요."
            )
        else:
            desc_detail = (
                "약사이드가 거의 비어 있지 않습니다. 볼사이드에 선수가 "
                "집중되어 수비 압박이 쉬워집니다. "
                "약사이드 코너/윙 포지션을 반드시 채우세요."
            )
        return self._make(
            category=FeedbackCategory.COORDINATION,
            fb_type=FeedbackType.POSITIVE if good else FeedbackType.IMPROVEMENT,
            priority=FeedbackPriority.MEDIUM if not good else FeedbackPriority.LOW,
            title="약사이드 스페이싱",
            description=(
                f"약사이드 지수 {ratio:.2f} "
                f"(3점 {three_sp:.1f}m / 평균 {avg_sp:.1f}m). {desc_detail}"
            ),
            suggestion=(
                "침투 시 약사이드 코너에 슈터를 배치하면 킥아웃 패스로 "
                "오픈 3점 기회를 만들 수 있습니다."
                if not good else None
            ),
            confidence=0.80,
        )

    # =========================================================================
    # 11. 코너 스페이싱 기회
    # =========================================================================
    def _corner_opportunity(
        self, three_sp: float, util: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        """
        3점 간격과 코트 활용률을 결합하여 코너3 기회 평가.
        코너3는 NBA 기준 가장 효율적인 슛 위치(eFG% 약 40%).
        """
        corner_ready = (
            three_sp >= cfg.corner_opportunity_threshold
            and util >= cfg.court_util_for_corner
        )
        if corner_ready:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title="코너 스페이싱 기회",
                description=(
                    f"3점 간격 {three_sp:.1f}m, 코트 활용률 {util:.0f}%로 "
                    f"양 코너에 슈터 배치 조건이 충족됩니다. "
                    f"코너3는 가장 짧은 3점 거리(6.75m)로 높은 eFG%를 기대할 수 있습니다. "
                    f"드라이브 & 킥아웃 → 코너3 전술을 적극 활용하세요."
                ),
                confidence=0.82,
            )

        # 조건 미충족 시 무엇이 부족한지 안내
        issues: list[str] = []
        if three_sp < cfg.corner_opportunity_threshold:
            issues.append(
                f"3점 간격({three_sp:.1f}m)이 코너 배치 기준 "
                f"({cfg.corner_opportunity_threshold:.1f}m) 미만"
            )
        if util < cfg.court_util_for_corner:
            issues.append(
                f"코트 활용률({util:.0f}%)이 코너 활용 기준 "
                f"({cfg.court_util_for_corner:.0f}%) 미만"
            )
        return self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.IMPROVEMENT,
            priority=FeedbackPriority.LOW,
            title="코너 스페이싱 부족",
            description=(
                f"코너3 활용 조건 미충족: {'; '.join(issues)}. "
                f"코너 슈터 배치를 위해 전체 포지셔닝 조정이 필요합니다."
            ),
            suggestion=(
                "오프볼 스크린으로 코너 슈터를 이동시키고 "
                "코트 양 끝을 적극적으로 활용하세요."
            ),
            confidence=0.78,
        )

    # =========================================================================
    # 12. 볼사이드 혼잡도 경고
    # =========================================================================
    def _congestion_warning(
        self, avg_sp: float, drive: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        """
        평균 간격이 좁고 드라이브 레인 개방도가 낮으면 볼사이드 혼잡 경고.
        """
        congested = (
            avg_sp < cfg.congestion_spacing_low
            and drive < cfg.congestion_drive_low
        )
        if congested:
            return self._make(
                category=FeedbackCategory.COORDINATION,
                fb_type=FeedbackType.WARNING,
                priority=FeedbackPriority.HIGH,
                title="볼사이드 혼잡도 경고",
                description=(
                    f"평균 간격 {avg_sp:.1f}m / 드라이브 레인 {drive:.0f}점으로 "
                    f"볼사이드가 심하게 혼잡합니다. 수비 더블팀과 함정수비에 "
                    f"매우 취약하며 턴오버 위험이 높습니다."
                ),
                suggestion=(
                    "즉시 약사이드로 선수를 분산시키세요. "
                    "스윙 패스를 통해 볼사이드 압력을 완화하고 "
                    "드라이브 레인을 확보한 후 침투하세요."
                ),
                current_value=avg_sp,
                confidence=0.85,
            )

        # 혼잡하지 않은 경우
        if avg_sp >= cfg.avg_spacing_good and drive >= cfg.drive_lane_good:
            return self._make(
                category=FeedbackCategory.COORDINATION,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title="볼사이드 밀도 양호",
                description=(
                    f"평균 간격 {avg_sp:.1f}m / 드라이브 레인 {drive:.0f}점으로 "
                    f"볼사이드 밀도가 적정합니다. 수비 수축 없이 "
                    f"자유로운 공격 전개가 가능합니다."
                ),
                confidence=0.82,
            )
        return self._make(
            category=FeedbackCategory.COORDINATION,
            fb_type=FeedbackType.TIP,
            priority=FeedbackPriority.LOW,
            title="볼사이드 밀도 주의",
            description=(
                f"평균 간격 {avg_sp:.1f}m / 드라이브 레인 {drive:.0f}점. "
                f"볼사이드 밀도가 다소 높습니다. "
                f"혼잡해지기 전에 간격을 넓히는 것을 권장합니다."
            ),
            confidence=0.78,
        )

    # =========================================================================
    # 13. 스페이싱 품질 추세 → 실행 가능 조언
    # =========================================================================
    def _spacing_trend_action(
        self, avg_sp: float, drive: float, util: float,
        cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        """스페이싱 품질 지수를 기반으로 즉시 실행 가능한 구체적 전술 조언 제공."""
        # 품질 지수 재계산 (6번과 동일 공식)
        spacing_score = min(100.0, max(0.0, (avg_sp - 2.0) / 3.0 * 100.0))
        util_adj = util if util > 0 else 50.0
        quality = spacing_score * 0.40 + drive * 0.35 + util_adj * 0.25

        if quality >= cfg.spacing_quality_excellent:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title="공간 전술 현황: 우수",
                description=(
                    f"스페이싱 품질 {quality:.0f}점으로 전술 실행이 원활합니다. "
                    f"현재 공간 운용 패턴을 유지하되 "
                    f"상대 수비 전환에 대비한 대안 포지셔닝을 준비하세요."
                ),
                confidence=0.82,
            )
        if quality >= cfg.trend_action_threshold:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="공간 전술 권고",
                description=(
                    f"스페이싱 품질 {quality:.0f}점입니다. "
                    f"{'간격 확대가' if avg_sp < cfg.avg_spacing_good else '드라이브 레인 확보가'} "
                    f"우선 개선 과제입니다. "
                    f"오프볼 스크린 빈도를 늘리고 약사이드 활용을 강화하세요."
                ),
                confidence=0.78,
            )
        # quality < trend_action_threshold → 즉시 조치
        # 가장 취약한 영역 식별
        weakest = "간격" if spacing_score < drive else "드라이브 레인"
        return self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.CORRECTION,
            priority=FeedbackPriority.MEDIUM,
            title="공간 전술: 즉시 조치 필요",
            description=(
                f"스페이싱 품질 {quality:.0f}점으로 즉각적인 전술 조정이 필요합니다. "
                f"가장 취약한 영역은 '{weakest}'입니다."
            ),
            suggestion=(
                f"{'선수 간 간격을 4.5m 이상으로 넓히세요. 모션 오펜스나 5-OUT 포메이션을 고려하세요.' if weakest == '간격' else '스크린 플레이로 수비를 움직이고 드라이브 경로를 확보한 후 침투하세요.'}"
            ),
            confidence=0.82,
        )

    # =========================================================================
    # 14. 페인트 밀도 vs 득점 효율
    # =========================================================================
    def _paint_scoring_efficiency(
        self, paint: float, drive: float, cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        """
        페인트 터치 빈도와 드라이브 레인 개방도를 결합하여
        인사이드 득점 효율을 추정.
        높은 페인트 터치 + 높은 드라이브 레인 = 효율적 인사이드 공격.
        """
        # 결합 지수: 페인트 기여도(0~1) * 50 + 드라이브 개방도(0~100) * 0.5
        paint_normalized = min(1.0, paint / 0.6)  # 0.6이면 1.0
        combined = paint_normalized * 50.0 + drive * 0.50

        if combined >= 70.0:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.POSITIVE,
                priority=FeedbackPriority.LOW,
                title="인사이드 공격 효율: 높음",
                description=(
                    f"페인트 터치 {paint:.2f}회 + 드라이브 개방도 {drive:.0f}점 "
                    f"→ 인사이드 효율 지수 {combined:.0f}/100. "
                    f"적극적인 침투와 열린 레인이 결합되어 "
                    f"높은 인사이드 득점 효율이 기대됩니다."
                ),
                current_value=combined,
                confidence=0.80,
            )
        if combined >= 45.0:
            return self._make(
                category=FeedbackCategory.TIP,
                fb_type=FeedbackType.TIP,
                priority=FeedbackPriority.LOW,
                title="인사이드 공격 효율: 보통",
                description=(
                    f"페인트 터치 {paint:.2f}회 + 드라이브 개방도 {drive:.0f}점 "
                    f"→ 인사이드 효율 지수 {combined:.0f}/100. "
                    f"인사이드 공격이 적정 수준이나 "
                    f"{'더 적극적인 페인트 침투가' if paint < cfg.paint_touch_good else '드라이브 레인 확보가'} "
                    f"효율 향상에 도움됩니다."
                ),
                current_value=combined,
                confidence=0.78,
            )
        return self._make(
            category=FeedbackCategory.TIP,
            fb_type=FeedbackType.IMPROVEMENT,
            priority=FeedbackPriority.MEDIUM,
            title="인사이드 공격 효율: 낮음",
            description=(
                f"페인트 터치 {paint:.2f}회 + 드라이브 개방도 {drive:.0f}점 "
                f"→ 인사이드 효율 지수 {combined:.0f}/100. "
                f"페인트 존 공격이 비효율적입니다."
            ),
            suggestion=(
                "드라이브 레인을 확보한 후 침투하고 "
                "페인트 존에서의 마무리 능력을 강화하세요. "
                "픽앤롤과 핸드오프 플레이가 효과적입니다."
            ),
            current_value=combined,
            confidence=0.80,
        )

    # =========================================================================
    # 15. 종합 공간 등급
    # =========================================================================
    def _overall_spatial_grade(
        self,
        util: float,
        avg_sp: float,
        drive: float,
        three_sp: float,
        paint: float,
        cfg: SpatialFeedbackConfig,
    ) -> FeedbackItem:
        """5개 원본 지표를 가중합산하여 A~F 종합 등급 산정."""
        # 각 지표를 0~100으로 정규화
        util_score = min(100.0, max(0.0, util))
        spacing_score = min(100.0, max(0.0, (avg_sp - 2.0) / 3.0 * 100.0)) if avg_sp > 0 else 0.0
        drive_score = min(100.0, max(0.0, drive))
        three_score = min(100.0, max(0.0, (three_sp - 3.0) / 4.0 * 100.0)) if three_sp > 0 else 0.0
        paint_score = min(100.0, max(0.0, paint / 0.6 * 100.0)) if paint > 0 else 0.0

        # 가중합산 (코트활용 20% + 간격 25% + 드라이브 25% + 3점 15% + 페인트 15%)
        total = (
            util_score * 0.20
            + spacing_score * 0.25
            + drive_score * 0.25
            + three_score * 0.15
            + paint_score * 0.15
        )

        if total >= cfg.grade_a_threshold:
            grade = "A"
            fb_type = FeedbackType.POSITIVE
            desc = (
                f"종합 공간 등급 A ({total:.0f}/100). "
                f"코트 활용({util_score:.0f}) / 간격({spacing_score:.0f}) / "
                f"드라이브({drive_score:.0f}) / 3점({three_score:.0f}) / "
                f"페인트({paint_score:.0f}) 전 영역에서 우수한 공간 활용입니다. "
                f"현재 포지셔닝 패턴을 유지하세요."
            )
        elif total >= cfg.grade_b_threshold:
            grade = "B"
            fb_type = FeedbackType.TIP
            # 가장 낮은 영역 식별
            scores = {
                "코트 활용": util_score, "선수 간격": spacing_score,
                "드라이브 레인": drive_score, "3점 배치": three_score,
                "페인트 침투": paint_score,
            }
            weakest_name = min(scores, key=scores.get)  # type: ignore[arg-type]
            desc = (
                f"종합 공간 등급 B ({total:.0f}/100). "
                f"전반적으로 양호하나 '{weakest_name}'({scores[weakest_name]:.0f}점) "
                f"영역의 보강으로 A등급 도달이 가능합니다."
            )
        elif total >= cfg.grade_c_threshold:
            grade = "C"
            fb_type = FeedbackType.IMPROVEMENT
            scores = {
                "코트 활용": util_score, "선수 간격": spacing_score,
                "드라이브 레인": drive_score, "3점 배치": three_score,
                "페인트 침투": paint_score,
            }
            sorted_scores = sorted(scores.items(), key=lambda x: x[1])
            bottom_two = [f"{name}({val:.0f}점)" for name, val in sorted_scores[:2]]
            desc = (
                f"종합 공간 등급 C ({total:.0f}/100). "
                f"개선 필요 영역: {', '.join(bottom_two)}. "
                f"이 영역들을 집중적으로 개선하면 공간 활용도가 크게 향상됩니다."
            )
        else:
            grade = "D"
            fb_type = FeedbackType.CORRECTION
            desc = (
                f"종합 공간 등급 D ({total:.0f}/100). "
                f"코트 활용({util_score:.0f}) / 간격({spacing_score:.0f}) / "
                f"드라이브({drive_score:.0f}) / 3점({three_score:.0f}) / "
                f"페인트({paint_score:.0f}). "
                f"공간 활용 전반에 걸쳐 근본적인 전술 재설계가 필요합니다."
            )

        return self._make(
            category=FeedbackCategory.TIP,
            fb_type=fb_type,
            priority=FeedbackPriority.MEDIUM,
            title=f"종합 공간 등급: {grade}",
            description=desc,
            current_value=total,
            ideal_value=cfg.grade_a_threshold,
            confidence=0.88,
        )

    # =========================================================================
    # 유틸리티
    # =========================================================================
    def reset(self) -> None:
        with self._lock:
            self._total_generated = 0

    def __repr__(self) -> str:
        return f"SpatialFeedbackGenerator(generated={self._total_generated})"

    @staticmethod
    def _make(
        *,
        category: FeedbackCategory,
        fb_type: FeedbackType,
        priority: FeedbackPriority,
        title: str,
        description: str,
        suggestion: str | None = None,
        current_value: float | None = None,
        ideal_value: float | None = None,
        unit: str | None = None,
        confidence: float = 0.80,
    ) -> FeedbackItem:
        """FeedbackItem 생성 헬퍼 (lineup_feedback.py 패턴 준수)."""
        return FeedbackItem(
            category=category,
            feedback_type=fb_type,
            priority=priority,
            body_parts=[],
            title=title,
            description=description,
            suggestion=suggestion,
            current_value=current_value,
            ideal_value=ideal_value,
            unit=unit,
            confidence=confidence,
        )


# =============================================================================
# 모듈 Export
# =============================================================================
__all__ = [
    "SpatialFeedbackGenerator",
    "SpatialFeedbackConfig",
]

__version__ = "1.0.0"
