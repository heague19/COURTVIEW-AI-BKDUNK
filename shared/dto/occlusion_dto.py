# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: occlusion_dto.py
설명: 오클루전 데이터 DTO (Data Transfer Object) 정의
      - 오클루전 이벤트, 복구 결과
      - 뷰 가시성, 가려진 객체 정보
      - 다국어 지원 (i18n)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.localization import SupportedLanguage
from shared.constants.occlusion_constants import (
    OcclusionSeverity,
    OcclusionType,
    ResolutionStrategy,
)
from shared.dto.geometry_dto import BoundingBox, Point2D, Point3D


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class ViewVisibility:
    """
    뷰별 가시성 정보.

    특정 카메라 뷰에서 객체의 가시성 상태를 나타냅니다.

    Attributes:
        camera_id: 카메라 ID
        is_visible: 가시 여부
        visibility_ratio: 가시 비율 (0.0~1.0)
        visible_keypoints: 가시 키포인트 인덱스
        occluded_keypoints: 가려진 키포인트 인덱스
        confidence: 가시성 판단 신뢰도
        depth_estimate: 추정 깊이 (미터)
    """

    camera_id: str
    is_visible: bool = True
    visibility_ratio: float = 1.0
    visible_keypoints: set[int] = field(default_factory=set)
    occluded_keypoints: set[int] = field(default_factory=set)
    confidence: float = 1.0
    depth_estimate: float | None = None

    def __post_init__(self):
        """초기화 후 처리."""
        # 가시성 비율 범위 검증
        self.visibility_ratio = max(0.0, min(1.0, self.visibility_ratio))
        # 신뢰도 범위 검증
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def total_keypoints(self) -> int:
        """전체 키포인트 수."""
        return len(self.visible_keypoints) + len(self.occluded_keypoints)

    @property
    def visible_keypoint_ratio(self) -> float:
        """가시 키포인트 비율."""
        total = self.total_keypoints
        if total == 0:
            return 0.0
        return len(self.visible_keypoints) / total

    @property
    def is_partially_visible(self) -> bool:
        """부분 가시 여부."""
        return 0.0 < self.visibility_ratio < 1.0

    @property
    def is_fully_visible(self) -> bool:
        """완전 가시 여부."""
        return self.visibility_ratio >= 0.9

    @property
    def is_fully_occluded(self) -> bool:
        """완전 가림 여부."""
        return self.visibility_ratio <= 0.1


@dataclass
class OccludedObject:
    """
    가려진 객체 정보.

    오클루전으로 가려진 객체의 상세 정보입니다.

    Attributes:
        object_id: 객체 ID (트랙 ID)
        object_type: 객체 유형 (player, ball, referee 등)
        last_known_bbox: 마지막으로 알려진 바운딩 박스
        last_known_position: 마지막으로 알려진 2D 위치
        last_known_position_3d: 마지막으로 알려진 3D 위치
        occluded_since_frame: 오클루전 시작 프레임
        occluded_since_time: 오클루전 시작 시간
        occluder_ids: 가리는 객체 ID 목록
        visibility_per_view: 뷰별 가시성 정보
        estimated_position: 추정 위치 (2D)
        estimated_position_3d: 추정 위치 (3D)
        estimation_confidence: 추정 신뢰도
    """

    object_id: int
    object_type: str = "unknown"
    last_known_bbox: BoundingBox | None = None
    last_known_position: Point2D | None = None
    last_known_position_3d: Point3D | None = None
    occluded_since_frame: int = 0
    occluded_since_time: datetime | None = None
    occluder_ids: list[int] = field(default_factory=list)
    visibility_per_view: dict[str, ViewVisibility] = field(default_factory=dict)
    estimated_position: Point2D | None = None
    estimated_position_3d: Point3D | None = None
    estimation_confidence: float = 0.0

    @property
    def num_occluders(self) -> int:
        """가리는 객체 수."""
        return len(self.occluder_ids)

    @property
    def num_visible_views(self) -> int:
        """가시 뷰 수."""
        return sum(
            1 for v in self.visibility_per_view.values()
            if v.is_visible
        )

    @property
    def total_views(self) -> int:
        """전체 뷰 수."""
        return len(self.visibility_per_view)

    @property
    def best_visible_view(self) -> str | None:
        """가장 가시성이 좋은 뷰 ID."""
        if not self.visibility_per_view:
            return None

        best_view = max(
            self.visibility_per_view.items(),
            key=lambda x: (x[1].visibility_ratio, x[1].confidence),
        )
        return best_view[0] if best_view[1].is_visible else None

    @property
    def average_visibility(self) -> float:
        """평균 가시성."""
        if not self.visibility_per_view:
            return 0.0
        return sum(
            v.visibility_ratio for v in self.visibility_per_view.values()
        ) / len(self.visibility_per_view)

    def get_visible_views(self) -> list[str]:
        """가시 뷰 목록 반환."""
        return [
            camera_id for camera_id, vis in self.visibility_per_view.items()
            if vis.is_visible
        ]

    def occlusion_duration_frames(self, current_frame: int) -> int:
        """오클루전 지속 프레임 수."""
        return max(0, current_frame - self.occluded_since_frame)


@dataclass
class OcclusionEvent:
    """
    오클루전 이벤트.

    오클루전 발생에 대한 이벤트 정보입니다.

    Attributes:
        event_id: 이벤트 고유 ID
        occlusion_type: 오클루전 유형
        severity: 오클루전 심각도
        start_frame: 시작 프레임
        end_frame: 종료 프레임 (진행 중이면 None)
        start_time: 시작 시간
        end_time: 종료 시간
        affected_track_ids: 영향받은 트랙 ID 목록
        occluder_track_ids: 가리는 트랙 ID 목록
        affected_objects: 가려진 객체 정보 목록
        camera_ids: 관련 카메라 ID 목록
        overlap_iou: 오버랩 IoU
        resolution_strategy: 적용된 해결 전략
        is_resolved: 해결 여부
        metadata: 추가 메타데이터
    """

    event_id: UUID = field(default_factory=uuid4)
    occlusion_type: OcclusionType = OcclusionType.UNKNOWN
    severity: OcclusionSeverity = OcclusionSeverity.NONE
    start_frame: int = 0
    end_frame: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    affected_track_ids: list[int] = field(default_factory=list)
    occluder_track_ids: list[int] = field(default_factory=list)
    affected_objects: list[OccludedObject] = field(default_factory=list)
    camera_ids: list[str] = field(default_factory=list)
    overlap_iou: float = 0.0
    resolution_strategy: ResolutionStrategy | None = None
    is_resolved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """진행 중인 이벤트인지."""
        return self.end_frame is None and not self.is_resolved

    @property
    def duration_frames(self) -> int | None:
        """이벤트 지속 프레임 수."""
        if self.end_frame is None:
            return None
        return self.end_frame - self.start_frame

    @property
    def duration_seconds(self) -> float | None:
        """이벤트 지속 시간 (초)."""
        if self.start_time is None or self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return delta.total_seconds()

    @property
    def num_affected_tracks(self) -> int:
        """영향받은 트랙 수."""
        return len(self.affected_track_ids)

    @property
    def is_multi_object(self) -> bool:
        """다중 객체 오클루전인지."""
        return len(self.affected_track_ids) > 1

    @property
    def is_recoverable(self) -> bool:
        """복구 가능한 오클루전인지."""
        return self.occlusion_type.is_recoverable

    @property
    def recommended_strategy(self) -> ResolutionStrategy:
        """권장 해결 전략."""
        return self.occlusion_type.recommended_strategy

    def mark_ended(
        self,
        end_frame: int,
        end_time: datetime | None = None,
    ) -> None:
        """이벤트 종료 표시."""
        self.end_frame = end_frame
        self.end_time = end_time or datetime.now(timezone.utc)

    def mark_resolved(
        self,
        strategy: ResolutionStrategy,
    ) -> None:
        """해결됨 표시."""
        self.is_resolved = True
        self.resolution_strategy = strategy

    def add_affected_track(
        self,
        track_id: int,
        occluded_object: OccludedObject | None = None,
    ) -> None:
        """영향받은 트랙 추가."""
        if track_id not in self.affected_track_ids:
            self.affected_track_ids.append(track_id)
        if occluded_object is not None:
            self.affected_objects.append(occluded_object)


@dataclass
class OcclusionResolution:
    """
    오클루전 복구 결과.

    오클루전 해결 시도의 결과입니다.

    Attributes:
        event_id: 관련 오클루전 이벤트 ID
        track_id: 복구된 트랙 ID
        strategy_used: 사용된 해결 전략
        success: 복구 성공 여부
        confidence: 복구 결과 신뢰도
        recovered_position: 복구된 2D 위치
        recovered_position_3d: 복구된 3D 위치
        recovered_bbox: 복구된 바운딩 박스
        source_view_id: 복구에 사용된 뷰 ID (크로스뷰의 경우)
        interpolation_frames: 보간에 사용된 프레임 수
        prediction_frames: 예측된 프레임 수
        processing_time_ms: 처리 시간 (밀리초)
        fallback_strategies: 시도된 대체 전략 목록
        error_message: 오류 메시지 (실패 시)
    """

    event_id: UUID | None = None
    track_id: int = 0
    strategy_used: ResolutionStrategy = ResolutionStrategy.NONE
    success: bool = False
    confidence: float = 0.0
    recovered_position: Point2D | None = None
    recovered_position_3d: Point3D | None = None
    recovered_bbox: BoundingBox | None = None
    source_view_id: str | None = None
    interpolation_frames: int = 0
    prediction_frames: int = 0
    processing_time_ms: float = 0.0
    fallback_strategies: list[ResolutionStrategy] = field(default_factory=list)
    error_message: str | None = None

    @property
    def is_cross_view_recovery(self) -> bool:
        """크로스뷰 복구인지."""
        return self.strategy_used == ResolutionStrategy.CROSS_VIEW

    @property
    def is_interpolated(self) -> bool:
        """보간 복구인지."""
        return self.strategy_used == ResolutionStrategy.INTERPOLATION

    @property
    def is_predicted(self) -> bool:
        """예측 복구인지."""
        return self.strategy_used == ResolutionStrategy.PREDICTION

    @property
    def has_position(self) -> bool:
        """위치 정보가 있는지."""
        return self.recovered_position is not None

    @property
    def has_3d_position(self) -> bool:
        """3D 위치 정보가 있는지."""
        return self.recovered_position_3d is not None

    @property
    def has_bbox(self) -> bool:
        """바운딩 박스가 있는지."""
        return self.recovered_bbox is not None

    @property
    def num_fallback_attempts(self) -> int:
        """대체 전략 시도 횟수."""
        return len(self.fallback_strategies)

    def get_summary(
        self,
        lang: SupportedLanguage = SupportedLanguage.KO,
    ) -> str:
        """
        다국어 요약 반환.

        Args:
            lang: 언어 코드 (기본: 한국어)

        Returns:
            해당 언어의 복구 결과 요약
        """
        translations: dict[SupportedLanguage, dict[str, str]] = {
            SupportedLanguage.KO: {
                "success": "트랙 {track_id} 복구 성공 ({strategy}, 신뢰도: {confidence})",
                "failure": "트랙 {track_id} 복구 실패: {error}",
                "unknown_error": "알 수 없는 오류",
            },
            SupportedLanguage.EN: {
                "success": "Track {track_id} recovered ({strategy}, confidence: {confidence})",
                "failure": "Track {track_id} recovery failed: {error}",
                "unknown_error": "Unknown error",
            },
            SupportedLanguage.JA: {
                "success": "トラック {track_id} 復元成功 ({strategy}, 信頼度: {confidence})",
                "failure": "トラック {track_id} 復元失敗: {error}",
                "unknown_error": "不明なエラー",
            },
            SupportedLanguage.ZH: {
                "success": "轨迹 {track_id} 恢复成功 ({strategy}, 置信度: {confidence})",
                "failure": "轨迹 {track_id} 恢复失败: {error}",
                "unknown_error": "未知错误",
            },
            SupportedLanguage.ES: {
                "success": "Pista {track_id} recuperada ({strategy}, confianza: {confidence})",
                "failure": "Recuperación de pista {track_id} fallida: {error}",
                "unknown_error": "Error desconocido",
            },
        }

        msgs = translations.get(lang, translations[SupportedLanguage.KO])

        if self.success:
            # ResolutionStrategy도 다국어 지원 필요 시 확장 가능
            strategy_name = self.strategy_used.to_korean()
            return msgs["success"].format(
                track_id=self.track_id,
                strategy=strategy_name,
                confidence=f"{self.confidence:.1%}",
            )
        else:
            return msgs["failure"].format(
                track_id=self.track_id,
                error=self.error_message or msgs["unknown_error"],
            )

    def to_korean_summary(self) -> str:
        """한글 요약 반환 (하위 호환성)."""
        return self.get_summary(SupportedLanguage.KO)


@dataclass
class OcclusionAnalysisResult:
    """
    오클루전 분석 결과.

    프레임 또는 시퀀스의 오클루전 분석 전체 결과입니다.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        active_occlusions: 진행 중인 오클루전 이벤트
        resolved_occlusions: 해결된 오클루전 이벤트
        occluded_objects: 현재 가려진 객체 정보
        visibility_map: 객체별 뷰별 가시성
        resolutions: 복구 결과 목록
        processing_time_ms: 처리 시간 (밀리초)
    """

    frame_index: int = 0
    timestamp: float = 0.0
    active_occlusions: list[OcclusionEvent] = field(default_factory=list)
    resolved_occlusions: list[OcclusionEvent] = field(default_factory=list)
    occluded_objects: list[OccludedObject] = field(default_factory=list)
    visibility_map: dict[int, dict[str, ViewVisibility]] = field(default_factory=dict)
    resolutions: list[OcclusionResolution] = field(default_factory=list)
    processing_time_ms: float = 0.0

    @property
    def num_active_occlusions(self) -> int:
        """진행 중인 오클루전 수."""
        return len(self.active_occlusions)

    @property
    def num_occluded_objects(self) -> int:
        """가려진 객체 수."""
        return len(self.occluded_objects)

    @property
    def num_successful_resolutions(self) -> int:
        """성공한 복구 수."""
        return sum(1 for r in self.resolutions if r.success)

    @property
    def resolution_success_rate(self) -> float:
        """복구 성공률."""
        if not self.resolutions:
            return 0.0
        return self.num_successful_resolutions / len(self.resolutions)

    def get_object_visibility(
        self,
        object_id: int,
        camera_id: str,
    ) -> ViewVisibility | None:
        """특정 객체의 특정 뷰 가시성 조회."""
        if object_id not in self.visibility_map:
            return None
        return self.visibility_map[object_id].get(camera_id)

    def get_visible_objects_in_view(self, camera_id: str) -> list[int]:
        """특정 뷰에서 가시 객체 목록 조회."""
        visible = []
        for object_id, views in self.visibility_map.items():
            if camera_id in views and views[camera_id].is_visible:
                visible.append(object_id)
        return visible


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # Re-export (다국어 지원)
    "SupportedLanguage",

    # Enum (occlusion_constants에서 re-export)
    "OcclusionType",
    "OcclusionSeverity",
    "ResolutionStrategy",

    # 데이터 클래스
    "ViewVisibility",
    "OccludedObject",
    "OcclusionEvent",
    "OcclusionResolution",
    "OcclusionAnalysisResult",
]

# 모듈 버전 정보
__version__ = "1.0.0"
