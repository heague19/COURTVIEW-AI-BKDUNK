# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: shared/dto
파일: reid_dto.py
설명: Re-Identification 데이터 DTO (Data Transfer Object) 정의
      - ReID 특징 벡터, 갤러리, 매칭 결과
      - 선수 재식별을 위한 외관 특징 관리
      - 다국어 지원 (i18n)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-03
버전: 1.0.0
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID, uuid4

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 내부 모듈
# =============================================================================
from shared.constants.localization import SupportedLanguage
from shared.constants.reid_constants import (
    EMA_MOMENTUM,
    GALLERY_FEATURE_MAX_AGE,
    GALLERY_MAX_SIZE,
    SIMILARITY_THRESHOLD,
    MatchStatus,
    ReIDModel,
)
from shared.dto.geometry_dto import BoundingBox


# =============================================================================
# i18n 모듈 레벨 캐시
# =============================================================================

_REID_MATCH_I18N: Final[dict[str, dict[str, str]]] = {
    "ko": {
        "matched": "매칭됨: ID {id} (유사도: {sim})",
        "new": "새로운 인물",
        "ambiguous": "모호함: 후보 {count}명 (차이: {gap})",
        "status": "상태: {status}",
    },
    "en": {
        "matched": "Matched: ID {id} (similarity: {sim})",
        "new": "New person",
        "ambiguous": "Ambiguous: {count} candidates (gap: {gap})",
        "status": "Status: {status}",
    },
    "ja": {
        "matched": "マッチング: ID {id} (類似度: {sim})",
        "new": "新しい人物",
        "ambiguous": "曖昧: 候補 {count}名 (差: {gap})",
        "status": "状態: {status}",
    },
    "zh": {
        "matched": "匹配: ID {id} (相似度: {sim})",
        "new": "新人物",
        "ambiguous": "模糊: 候选 {count}人 (差距: {gap})",
        "status": "状态: {status}",
    },
    "es": {
        "matched": "Coincidencia: ID {id} (similitud: {sim})",
        "new": "Nueva persona",
        "ambiguous": "Ambiguo: {count} candidatos (diferencia: {gap})",
        "status": "Estado: {status}",
    },
}


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass(slots=True)
class ReIDFeature:
    """
    Re-ID 특징 벡터.

    단일 외관 특징 벡터와 관련 메타데이터입니다.

    >>> import numpy as np
    >>> feat = ReIDFeature(feature=np.random.randn(512).astype(np.float32))
    >>> feat.dimension
    512

    Attributes:
        feature: 특징 벡터 (정규화된 float32)
        confidence: 특징 품질/신뢰도
        frame_index: 추출된 프레임 인덱스
        timestamp: 추출 시간
        camera_id: 카메라 ID
        bbox: 원본 바운딩 박스
        quality_score: 이미지 품질 점수
        model_name: 사용된 모델명
    """

    feature: NDArray[np.float32]
    confidence: float = 1.0
    frame_index: int = 0
    timestamp: datetime | None = None
    camera_id: str | None = None
    bbox: BoundingBox | None = None
    quality_score: float = 1.0
    model_name: str = "osnet"

    def __post_init__(self) -> None:
        """초기화 후 처리."""
        # 특징 벡터 타입 확인 및 변환
        if not isinstance(self.feature, np.ndarray):
            self.feature = np.array(self.feature, dtype=np.float32)
        elif self.feature.dtype != np.float32:
            self.feature = self.feature.astype(np.float32)

        # 신뢰도 범위 검증
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.quality_score = max(0.0, min(1.0, self.quality_score))

    @property
    def dimension(self) -> int:
        """특징 벡터 차원."""
        return len(self.feature)

    @property
    def is_normalized(self) -> bool:
        """정규화 여부 확인."""
        norm = np.linalg.norm(self.feature)
        return abs(norm - 1.0) < 1e-5

    @property
    def norm(self) -> float:
        """L2 노름."""
        return float(np.linalg.norm(self.feature))

    def normalize(self) -> "ReIDFeature":
        """정규화된 새 특징 반환."""
        norm = np.linalg.norm(self.feature)
        if norm > 1e-12:
            normalized = self.feature / norm
        else:
            normalized = self.feature
        return ReIDFeature(
            feature=normalized,
            confidence=self.confidence,
            frame_index=self.frame_index,
            timestamp=self.timestamp,
            camera_id=self.camera_id,
            bbox=self.bbox,
            quality_score=self.quality_score,
            model_name=self.model_name,
        )

    def cosine_similarity(self, other: "ReIDFeature") -> float:
        """다른 특징과의 코사인 유사도."""
        # 정규화된 특징이면 내적이 코사인 유사도
        if self.is_normalized and other.is_normalized:
            return float(np.dot(self.feature, other.feature))

        # 정규화되지 않은 경우 직접 계산
        norm1 = np.linalg.norm(self.feature)
        norm2 = np.linalg.norm(other.feature)
        if norm1 < 1e-12 or norm2 < 1e-12:
            return 0.0
        return float(np.dot(self.feature, other.feature) / (norm1 * norm2))

    def euclidean_distance(self, other: "ReIDFeature") -> float:
        """다른 특징과의 유클리드 거리."""
        return float(np.linalg.norm(self.feature - other.feature))


@dataclass(slots=True)
class GalleryEntry:
    """
    갤러리 엔트리.

    특정 인물/객체의 갤러리 항목입니다.

    Attributes:
        entry_id: 엔트리 고유 ID
        person_id: 인물 ID (트랙 ID와 연관)
        features: 저장된 특징 목록
        mean_feature: 평균 특징 벡터 (EMA)
        last_update_frame: 마지막 업데이트 프레임
        last_update_time: 마지막 업데이트 시간
        total_observations: 총 관측 횟수
        team: 팀 (선택적)
        jersey_number: 등번호 (선택적)
        attributes: 추가 속성
    """

    entry_id: UUID = field(default_factory=uuid4)
    person_id: int = 0
    features: list[ReIDFeature] = field(default_factory=list)
    mean_feature: NDArray[np.float32] | None = None
    last_update_frame: int = 0
    last_update_time: datetime | None = None
    total_observations: int = 0
    team: str | None = None
    jersey_number: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def num_features(self) -> int:
        """저장된 특징 수."""
        return len(self.features)

    @property
    def has_mean_feature(self) -> bool:
        """평균 특징 존재 여부."""
        return self.mean_feature is not None

    @property
    def average_confidence(self) -> float:
        """평균 신뢰도."""
        if not self.features:
            return 0.0
        return sum(f.confidence for f in self.features) / len(self.features)

    @property
    def average_quality(self) -> float:
        """평균 품질."""
        if not self.features:
            return 0.0
        return sum(f.quality_score for f in self.features) / len(self.features)

    # 비즈니스 로직 이관 완료: add_feature, _update_mean_feature,
    # similarity_to, prune_old_features → detection/reid/ 서비스 레이어


@dataclass(slots=True)
class ReIDGallery:
    """
    Re-ID 갤러리.

    모든 인물의 특징을 관리하는 갤러리입니다.

    Attributes:
        gallery_id: 갤러리 고유 ID
        entries: 갤러리 엔트리 (person_id → entry)
        max_entries: 최대 엔트리 수
        max_features_per_entry: 엔트리당 최대 특징 수
        model_name: 사용된 Re-ID 모델
        created_at: 생성 시간
        last_update: 마지막 업데이트 시간
    """

    gallery_id: UUID = field(default_factory=uuid4)
    entries: dict[int, GalleryEntry] = field(default_factory=dict)
    max_entries: int = 50
    max_features_per_entry: int = GALLERY_MAX_SIZE
    model_name: str = "osnet"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_update: datetime | None = None

    @property
    def num_entries(self) -> int:
        """등록된 인물 수."""
        return len(self.entries)

    @property
    def total_features(self) -> int:
        """총 특징 수."""
        return sum(e.num_features for e in self.entries.values())

    @property
    def is_empty(self) -> bool:
        """비어있는지 여부."""
        return len(self.entries) == 0

    # 비즈니스 로직 이관 완료: add_entry, remove_entry, update_feature,
    # query, find_best_match, prune_all → detection/reid/ 서비스 레이어
    # get_entry는 단순 조회로 유지


@dataclass(slots=True)
class ReIDMatch:
    """
    Re-ID 매칭 결과.

    Re-ID 쿼리의 결과입니다.

    Attributes:
        query_feature: 쿼리 특징
        status: 매칭 상태
        matched_person_id: 매칭된 인물 ID (있는 경우)
        similarity: 매칭 유사도
        confidence: 매칭 신뢰도
        candidates: 후보 목록 [(person_id, similarity), ...]
        is_ambiguous: 모호한 매칭인지
        processing_time_ms: 처리 시간 (밀리초)
    """

    query_feature: ReIDFeature | None = None
    status: MatchStatus = MatchStatus.FAILED
    matched_person_id: int | None = None
    similarity: float = 0.0
    confidence: float = 0.0
    candidates: list[tuple[int, float]] = field(default_factory=list)
    is_ambiguous: bool = False
    processing_time_ms: float = 0.0

    @property
    def is_matched(self) -> bool:
        """매칭 성공 여부."""
        return self.status == MatchStatus.MATCHED

    @property
    def is_new(self) -> bool:
        """새로운 인물 여부."""
        return self.status == MatchStatus.NEW

    @property
    def is_successful(self) -> bool:
        """성공적인 결과 여부 (매칭 또는 새 인물)."""
        return self.status.is_successful

    @property
    def num_candidates(self) -> int:
        """후보 수."""
        return len(self.candidates)

    @property
    def top_candidate(self) -> tuple[int, float] | None:
        """최상위 후보."""
        return self.candidates[0] if self.candidates else None

    @property
    def second_candidate(self) -> tuple[int, float] | None:
        """두 번째 후보."""
        return self.candidates[1] if len(self.candidates) > 1 else None

    @property
    def similarity_gap(self) -> float:
        """
        1위와 2위 유사도 차이.

        모호한 매칭 판단에 사용됩니다.
        """
        num_candidates = len(self.candidates)
        if num_candidates < 2:
            return 1.0  # 후보가 1개 이하면 모호하지 않음
        return self.candidates[0][1] - self.candidates[1][1]

    def get_summary(self, lang: SupportedLanguage = SupportedLanguage.KO) -> str:
        """
        다국어 매칭 결과 요약 반환.

        Args:
            lang: 언어 코드 (기본: 한국어)

        Returns:
            해당 언어의 매칭 결과 요약
        """
        msgs = _REID_MATCH_I18N.get(lang.value, _REID_MATCH_I18N["ko"])

        if self.is_matched:
            return msgs["matched"].format(
                id=self.matched_person_id,
                sim=f"{self.similarity:.1%}",
            )
        elif self.is_new:
            return msgs["new"]
        elif self.is_ambiguous:
            return msgs["ambiguous"].format(
                count=self.num_candidates,
                gap=f"{self.similarity_gap:.1%}",
            )
        else:
            return msgs["status"].format(status=self.status.to_korean())

    def to_korean_summary(self) -> str:
        """한글 요약 반환 (하위 호환성)."""
        return self.get_summary(SupportedLanguage.KO)


@dataclass(slots=True)
class ReIDResult:
    """
    Re-ID 전체 결과.

    프레임 또는 배치의 Re-ID 처리 결과입니다.

    Attributes:
        frame_index: 프레임 인덱스
        timestamp: 타임스탬프
        matches: 매칭 결과 목록
        new_persons: 새로 등록된 인물 ID 목록
        gallery_updates: 갤러리 업데이트 수
        processing_time_ms: 총 처리 시간
    """

    frame_index: int = 0
    timestamp: float = 0.0
    matches: list[ReIDMatch] = field(default_factory=list)
    new_persons: list[int] = field(default_factory=list)
    gallery_updates: int = 0
    processing_time_ms: float = 0.0

    @property
    def num_matches(self) -> int:
        """매칭 수."""
        return len(self.matches)

    @property
    def num_successful(self) -> int:
        """성공적인 매칭 수."""
        return sum(1 for m in self.matches if m.is_successful)

    @property
    def num_ambiguous(self) -> int:
        """모호한 매칭 수."""
        return sum(1 for m in self.matches if m.is_ambiguous)

    @property
    def success_rate(self) -> float:
        """성공률."""
        if not self.matches:
            return 0.0
        return self.num_successful / len(self.matches)

    def get_match_for_track(self, track_id: int) -> ReIDMatch | None:
        """트랙 ID에 해당하는 매칭 결과 조회."""
        for match in self.matches:
            if match.matched_person_id == track_id:
                return match
        return None


# =============================================================================
# 모듈 Export 정의 (PHASE_01 정의서 준수)
# =============================================================================

__all__ = [
    # 데이터 클래스
    "ReIDFeature",
    "GalleryEntry",
    "ReIDGallery",
    "ReIDMatch",
    "ReIDResult",
]

# 모듈 버전 정보
__version__ = "1.0.0"
