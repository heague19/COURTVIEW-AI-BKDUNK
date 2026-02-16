# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: tracking_dto.py
설명: 객체 추적 DTO (Data Transfer Object) 정의
      - 트랙 상태, 이력, 연관
      - 칼만 필터 상태, 추적 결과
      - 다국어 지원 (i18n)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.localization import SupportedLanguage
from shared.dto.geometry_dto import BoundingBox, Point2D, Point3D, Trajectory3D


# =============================================================================
# 열거형
# =============================================================================

class TrackState(str, Enum):
    """
    트랙 상태 열거형.

    객체 추적의 현재 상태를 나타냅니다.
    """

    TENTATIVE = "tentative"    # 임시 (확정 대기)
    CONFIRMED = "confirmed"    # 확정됨
    LOST = "lost"              # 추적 중단
    DELETED = "deleted"        # 삭제됨
    OCCLUDED = "occluded"      # 가려짐

    @property
    def is_active(self) -> bool:
        """활성 상태 여부."""
        return self in (TrackState.TENTATIVE, TrackState.CONFIRMED, TrackState.OCCLUDED)

    @property
    def is_visible(self) -> bool:
        """가시 상태 여부."""
        return self in (TrackState.TENTATIVE, TrackState.CONFIRMED)

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 상태명 반환.

        Args:
            lang: 언어 코드 (기본: 한국어)

        Returns:
            해당 언어의 상태명
        """
        translations: dict[TrackState, dict[SupportedLanguage, str]] = {
            TrackState.TENTATIVE: {
                SupportedLanguage.KO: "임시",
                SupportedLanguage.EN: "Tentative",
                SupportedLanguage.JA: "仮",
                SupportedLanguage.ZH: "临时",
                SupportedLanguage.ES: "Provisional",
            },
            TrackState.CONFIRMED: {
                SupportedLanguage.KO: "확정",
                SupportedLanguage.EN: "Confirmed",
                SupportedLanguage.JA: "確定",
                SupportedLanguage.ZH: "已确认",
                SupportedLanguage.ES: "Confirmado",
            },
            TrackState.LOST: {
                SupportedLanguage.KO: "추적 중단",
                SupportedLanguage.EN: "Lost",
                SupportedLanguage.JA: "追跡中断",
                SupportedLanguage.ZH: "丢失",
                SupportedLanguage.ES: "Perdido",
            },
            TrackState.DELETED: {
                SupportedLanguage.KO: "삭제됨",
                SupportedLanguage.EN: "Deleted",
                SupportedLanguage.JA: "削除済み",
                SupportedLanguage.ZH: "已删除",
                SupportedLanguage.ES: "Eliminado",
            },
            TrackState.OCCLUDED: {
                SupportedLanguage.KO: "가려짐",
                SupportedLanguage.EN: "Occluded",
                SupportedLanguage.JA: "遮蔽",
                SupportedLanguage.ZH: "被遮挡",
                SupportedLanguage.ES: "Ocluido",
            },
        }
        return translations[self].get(lang, translations[self][SupportedLanguage.KO])

    def to_korean(self) -> str:
        """한글 상태명 반환 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


class TrackSource(str, Enum):
    """
    트랙 소스 열거형.

    트랙이 생성/복구된 소스를 나타냅니다.
    """

    SINGLE_VIEW = "single_view"      # 단일 뷰에서 생성
    MULTI_VIEW = "multi_view"        # 멀티뷰 융합
    RECOVERED = "recovered"          # 오클루전 후 복구
    INTERPOLATED = "interpolated"    # 보간으로 생성
    MANUAL = "manual"                # 수동 지정

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 소스명 반환.

        Args:
            lang: 언어 코드 (기본: 한국어)

        Returns:
            해당 언어의 소스명
        """
        translations: dict[TrackSource, dict[SupportedLanguage, str]] = {
            TrackSource.SINGLE_VIEW: {
                SupportedLanguage.KO: "단일 뷰",
                SupportedLanguage.EN: "Single View",
                SupportedLanguage.JA: "シングルビュー",
                SupportedLanguage.ZH: "单视图",
                SupportedLanguage.ES: "Vista Única",
            },
            TrackSource.MULTI_VIEW: {
                SupportedLanguage.KO: "멀티뷰",
                SupportedLanguage.EN: "Multi-View",
                SupportedLanguage.JA: "マルチビュー",
                SupportedLanguage.ZH: "多视图",
                SupportedLanguage.ES: "Multi-Vista",
            },
            TrackSource.RECOVERED: {
                SupportedLanguage.KO: "복구됨",
                SupportedLanguage.EN: "Recovered",
                SupportedLanguage.JA: "復旧",
                SupportedLanguage.ZH: "已恢复",
                SupportedLanguage.ES: "Recuperado",
            },
            TrackSource.INTERPOLATED: {
                SupportedLanguage.KO: "보간됨",
                SupportedLanguage.EN: "Interpolated",
                SupportedLanguage.JA: "補間",
                SupportedLanguage.ZH: "插值",
                SupportedLanguage.ES: "Interpolado",
            },
            TrackSource.MANUAL: {
                SupportedLanguage.KO: "수동",
                SupportedLanguage.EN: "Manual",
                SupportedLanguage.JA: "手動",
                SupportedLanguage.ZH: "手动",
                SupportedLanguage.ES: "Manual",
            },
        }
        return translations[self].get(lang, translations[self][SupportedLanguage.KO])

    def to_korean(self) -> str:
        """한글 소스명 반환 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


class TrackedObjectType(str, Enum):
    """
    추적 객체 유형 열거형.

    추적되는 객체의 유형을 정의합니다.
    """

    PLAYER = "player"
    BALL = "ball"
    REFEREE = "referee"
    COACH = "coach"
    UNKNOWN = "unknown"

    def get_name(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 유형명 반환.

        Args:
            lang: 언어 코드 (기본: 한국어)

        Returns:
            해당 언어의 유형명
        """
        translations: dict[TrackedObjectType, dict[SupportedLanguage, str]] = {
            TrackedObjectType.PLAYER: {
                SupportedLanguage.KO: "선수",
                SupportedLanguage.EN: "Player",
                SupportedLanguage.JA: "選手",
                SupportedLanguage.ZH: "球员",
                SupportedLanguage.ES: "Jugador",
            },
            TrackedObjectType.BALL: {
                SupportedLanguage.KO: "공",
                SupportedLanguage.EN: "Ball",
                SupportedLanguage.JA: "ボール",
                SupportedLanguage.ZH: "球",
                SupportedLanguage.ES: "Balón",
            },
            TrackedObjectType.REFEREE: {
                SupportedLanguage.KO: "심판",
                SupportedLanguage.EN: "Referee",
                SupportedLanguage.JA: "審判",
                SupportedLanguage.ZH: "裁判",
                SupportedLanguage.ES: "Árbitro",
            },
            TrackedObjectType.COACH: {
                SupportedLanguage.KO: "코치",
                SupportedLanguage.EN: "Coach",
                SupportedLanguage.JA: "コーチ",
                SupportedLanguage.ZH: "教练",
                SupportedLanguage.ES: "Entrenador",
            },
            TrackedObjectType.UNKNOWN: {
                SupportedLanguage.KO: "미확인",
                SupportedLanguage.EN: "Unknown",
                SupportedLanguage.JA: "不明",
                SupportedLanguage.ZH: "未知",
                SupportedLanguage.ES: "Desconocido",
            },
        }
        return translations[self].get(lang, translations[self][SupportedLanguage.KO])

    def to_korean(self) -> str:
        """한글 유형명 반환 (하위 호환성)."""
        return self.get_name(SupportedLanguage.KO)


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class TrackHistory:
    """
    트랙 이력.

    트랙의 위치/속성 변화 기록입니다.

    Attributes:
        positions: 2D 위치 이력
        positions_3d: 3D 위치 이력 (선택적)
        timestamps: 타임스탬프 이력
        bboxes: 바운딩 박스 이력
        confidences: 신뢰도 이력
    """

    positions: list[Point2D] = field(default_factory=list)
    positions_3d: list[Point3D] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)
    bboxes: list[BoundingBox] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)

    @property
    def length(self) -> int:
        """이력 길이."""
        return len(self.positions)

    @property
    def duration(self) -> float:
        """이력 기간 (초)."""
        if len(self.timestamps) < 2:
            return 0.0
        return self.timestamps[-1] - self.timestamps[0]

    @property
    def last_position(self) -> Point2D | None:
        """마지막 위치."""
        return self.positions[-1] if self.positions else None

    @property
    def last_position_3d(self) -> Point3D | None:
        """마지막 3D 위치."""
        return self.positions_3d[-1] if self.positions_3d else None

    @property
    def last_bbox(self) -> BoundingBox | None:
        """마지막 바운딩 박스."""
        return self.bboxes[-1] if self.bboxes else None

    @property
    def average_confidence(self) -> float:
        """평균 신뢰도."""
        if not self.confidences:
            return 0.0
        return sum(self.confidences) / len(self.confidences)

    def to_trajectory_3d(self) -> Trajectory3D:
        """3D 궤적으로 변환."""
        return Trajectory3D(
            points=self.positions_3d.copy(),
            timestamps=self.timestamps.copy(),
        )

    def add_entry(
        self,
        position: Point2D,
        timestamp: float,
        bbox: BoundingBox | None = None,
        confidence: float = 1.0,
        position_3d: Point3D | None = None,
    ) -> None:
        """이력 항목 추가."""
        self.positions.append(position)
        self.timestamps.append(timestamp)
        if bbox is not None:
            self.bboxes.append(bbox)
        self.confidences.append(confidence)
        if position_3d is not None:
            self.positions_3d.append(position_3d)

    def trim(self, max_length: int) -> None:
        """이력 길이 제한."""
        if self.length > max_length:
            excess = self.length - max_length
            self.positions = self.positions[excess:]
            self.timestamps = self.timestamps[excess:]
            self.bboxes = self.bboxes[excess:] if self.bboxes else []
            self.confidences = self.confidences[excess:]
            self.positions_3d = self.positions_3d[excess:] if self.positions_3d else []


@dataclass
class KalmanState:
    """
    칼만 필터 상태.

    칼만 필터의 현재 상태를 저장합니다.

    Attributes:
        mean: 상태 평균 벡터
        covariance: 상태 공분산 행렬
        state_dim: 상태 차원
        measurement_dim: 측정 차원
    """

    mean: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(8, dtype=np.float64)
    )
    covariance: NDArray[np.float64] = field(
        default_factory=lambda: np.eye(8, dtype=np.float64)
    )
    state_dim: int = 8
    measurement_dim: int = 4

    @property
    def position(self) -> tuple[float, float]:
        """위치 (x, y)."""
        return (float(self.mean[0]), float(self.mean[1]))

    @property
    def size(self) -> tuple[float, float]:
        """크기 (w, h) 또는 (a, h)."""
        return (float(self.mean[2]), float(self.mean[3]))

    @property
    def velocity(self) -> tuple[float, float]:
        """속도 (vx, vy)."""
        if self.state_dim >= 6:
            return (float(self.mean[4]), float(self.mean[5]))
        return (0.0, 0.0)

    @property
    def position_uncertainty(self) -> float:
        """위치 불확실성 (표준편차)."""
        return float(np.sqrt(self.covariance[0, 0] + self.covariance[1, 1]))

    def to_bbox(self) -> BoundingBox:
        """바운딩 박스로 변환."""
        # [cx, cy, a, h, ...] 형식 가정 (a = 종횡비, h = 높이)
        cx, cy, a, h = self.mean[:4]
        w = a * h
        return BoundingBox(
            x=cx - w / 2,
            y=cy - h / 2,
            width=w,
            height=h,
        )


@dataclass
class Track:
    """
    단일 트랙.

    추적되는 단일 객체의 정보입니다.

    Attributes:
        track_id: 트랙 고유 ID
        state: 트랙 상태
        object_type: 객체 유형
        bbox: 현재 바운딩 박스
        position: 현재 위치 (중심점)
        position_3d: 현재 3D 위치 (선택적)
        confidence: 추적 신뢰도
        source: 트랙 소스
        history: 트랙 이력
        kalman_state: 칼만 필터 상태
        age: 트랙 나이 (프레임)
        hits: 감지 히트 수
        time_since_update: 마지막 업데이트 이후 프레임 수
        attributes: 추가 속성 (등번호, 팀 등)
    """

    track_id: int = 0
    state: TrackState = TrackState.TENTATIVE
    object_type: TrackedObjectType = TrackedObjectType.UNKNOWN
    bbox: BoundingBox | None = None
    position: Point2D | None = None
    position_3d: Point3D | None = None
    confidence: float = 1.0
    source: TrackSource = TrackSource.SINGLE_VIEW
    history: TrackHistory = field(default_factory=TrackHistory)
    kalman_state: KalmanState | None = None
    age: int = 0
    hits: int = 0
    time_since_update: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """초기화 후 처리."""
        if self.bbox is not None and self.position is None:
            self.position = self.bbox.center

    @property
    def is_confirmed(self) -> bool:
        """확정된 트랙인지."""
        return self.state == TrackState.CONFIRMED

    @property
    def is_active(self) -> bool:
        """활성 트랙인지."""
        return self.state.is_active

    @property
    def is_lost(self) -> bool:
        """추적 중단된 트랙인지."""
        return self.state in (TrackState.LOST, TrackState.DELETED)

    @property
    def velocity(self) -> tuple[float, float] | None:
        """현재 속도."""
        if self.kalman_state is not None:
            return self.kalman_state.velocity
        return None

    @property
    def jersey_number(self) -> int | None:
        """등번호."""
        return self.attributes.get("jersey_number")

    @property
    def team(self) -> str | None:
        """팀."""
        return self.attributes.get("team")

    def update(
        self,
        bbox: BoundingBox,
        confidence: float,
        timestamp: float,
        position_3d: Point3D | None = None,
    ) -> None:
        """트랙 업데이트."""
        self.bbox = bbox
        self.position = bbox.center
        self.confidence = confidence
        if position_3d is not None:
            self.position_3d = position_3d

        # 이력 추가
        self.history.add_entry(
            position=self.position,
            timestamp=timestamp,
            bbox=bbox,
            confidence=confidence,
            position_3d=position_3d,
        )

        self.hits += 1
        self.time_since_update = 0
        self.age += 1

    def mark_missed(self) -> None:
        """감지 실패 표시."""
        self.time_since_update += 1
        self.age += 1


@dataclass
class TrackAssociation:
    """
    트랙-감지 연관.

    트랙과 감지 결과 간의 연관 정보입니다.

    Attributes:
        track_id: 트랙 ID
        detection_index: 감지 인덱스
        cost: 연관 비용 (거리/비유사도)
        iou: IoU 값
        appearance_similarity: 외관 유사도
    """

    track_id: int
    detection_index: int
    cost: float = 0.0
    iou: float = 0.0
    appearance_similarity: float = 0.0

    @property
    def combined_score(self) -> float:
        """결합 점수 (높을수록 좋음)."""
        return self.iou * 0.5 + self.appearance_similarity * 0.5


@dataclass
class TrackingResult:
    """
    추적 결과.

    단일 프레임의 추적 결과입니다.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        tracks: 트랙 목록
        new_tracks: 새로 생성된 트랙 ID
        deleted_tracks: 삭제된 트랙 ID
        associations: 트랙-감지 연관
        processing_time: 처리 시간 (초)
        camera_id: 카메라 ID (멀티카메라용)
    """

    frame_index: int = 0
    timestamp: float = 0.0
    tracks: list[Track] = field(default_factory=list)
    new_tracks: list[int] = field(default_factory=list)
    deleted_tracks: list[int] = field(default_factory=list)
    associations: list[TrackAssociation] = field(default_factory=list)
    processing_time: float = 0.0
    camera_id: str | None = None

    @property
    def num_tracks(self) -> int:
        """트랙 수."""
        return len(self.tracks)

    @property
    def active_tracks(self) -> list[Track]:
        """활성 트랙 목록."""
        return [t for t in self.tracks if t.is_active]

    @property
    def confirmed_tracks(self) -> list[Track]:
        """확정된 트랙 목록."""
        return [t for t in self.tracks if t.is_confirmed]

    def get_track(self, track_id: int) -> Track | None:
        """트랙 ID로 조회."""
        for track in self.tracks:
            if track.track_id == track_id:
                return track
        return None

    def get_tracks_by_type(self, object_type: TrackedObjectType) -> list[Track]:
        """객체 유형으로 트랙 조회."""
        return [t for t in self.tracks if t.object_type == object_type]


@dataclass
class MultiViewTrackingResult:
    """
    멀티뷰 추적 결과.

    여러 뷰의 추적 결과를 통합합니다.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        view_results: 뷰별 추적 결과
        fused_tracks: 융합된 3D 트랙
        processing_time: 총 처리 시간 (초)
    """

    frame_index: int = 0
    timestamp: float = 0.0
    view_results: dict[str, TrackingResult] = field(default_factory=dict)
    fused_tracks: list[Track] = field(default_factory=list)
    processing_time: float = 0.0

    @property
    def num_views(self) -> int:
        """뷰 수."""
        return len(self.view_results)

    @property
    def num_fused_tracks(self) -> int:
        """융합된 트랙 수."""
        return len(self.fused_tracks)

    def get_view_result(self, camera_id: str) -> TrackingResult | None:
        """카메라 ID로 뷰 결과 조회."""
        return self.view_results.get(camera_id)


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # Re-export (다국어 지원)
    "SupportedLanguage",

    # Enum
    "TrackState",
    "TrackSource",
    "TrackedObjectType",

    # 데이터 클래스
    "Track",
    "TrackHistory",
    "TrackingResult",
    "TrackAssociation",
    "KalmanState",
    "MultiViewTrackingResult",
]

# 모듈 버전 정보
__version__ = "1.0.0"
