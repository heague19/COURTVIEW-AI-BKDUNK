# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection
파일: reid_module.py

⚠️  **DEPRECATED (Phase 15 P15-06-DC1 확정)** ⚠️
    CV-reid 별도 모델 대신 `digit(등번호) + team(색상)` 조합으로 대체됨.
    본 921줄 ReIDModule 은 `__init__.py`에서 export 제외되어 있으며,
    테스트 코드만 직접 import 중. 향후 테스트 업데이트 후 완전 제거 예정.

설명: 외관 기반 선수 재식별 (Re-Identification) 모듈
      - ResNet50 PyTorch 모델 기반 512-dim 특징 벡터 추출 (COURTVIEW_reid.pt)
      - EMA(지수이동평균) 갤러리 관리
      - 코사인 유사도 기반 1:N 매칭
      - 크로스뷰 Re-ID 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-20 (DEPRECATED 마크)
버전: 1.0.0 (deprecated)

의존성:
    - shared/constants/reid_constants.py: 특징 차원, 유사도 임계값, 갤러리 파라미터
    - shared/constants/player_constants.py: 이미지 정규화 (ImageNet)
    - detection/player_detection/models.py: ReIDConfig, _PlayerCandidate

대체 모듈:
    - detection.player_detection.player_detector.PlayerDetector
      (digit_ocr + team_classifier 조합으로 별도 ReID 불필요)
"""

import warnings as _warnings
_warnings.warn(
    "reid_module.py is DEPRECATED. Use PlayerDetector with digit+team "
    "ID composition instead. This module will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Final

# =============================================================================
# 서드파티 라이브러리
# =============================================================================
import cv2
import numpy as np
from numpy.typing import NDArray

# =============================================================================
# 프로젝트 모듈
# =============================================================================
from shared.constants.player_constants import (
    NORMALIZE_MEAN,
    NORMALIZE_STD,
    PLAYER_CLASS_ID_PLAYER,
    PLAYER_CLASS_ID_REFEREE,
)
from shared.constants.reid_constants import (
    BBOX_EXPANSION_RATIO,
    CROSS_VIEW_MIN_CONFIDENCE,
    EMA_MIN_SAMPLES,
    EMA_MOMENTUM_INITIAL,
    FEATURE_NORMALIZE_EPS,
    HIGH_SIMILARITY_THRESHOLD,
    LOW_SIMILARITY_THRESHOLD,
    MIN_BBOX_SIZE,
    NORMALIZE_FEATURES,
    REID_INPUT_SIZE,
)
from detection.player_detection.models import (
    ReIDConfig,
    _PlayerCandidate,
)

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 모듈 상수
# =============================================================================

# ResNet50 Re-ID 모델 경로 (COURTVIEW_reid.pt)
# backbone(ResNet50) + embedding(2048→512) + classifier(512→130)
# 추론 시 512-dim embedding 출력 (classifier 미사용)
_DEFAULT_REID_MODEL_PATH: Final[str] = "weights/COURTVIEW_reid.pt"

# 갤러리 정리 주기 (프레임)
_GALLERY_CLEANUP_INTERVAL: Final[int] = 100

# 매칭 결과 캐시 최대 크기
_MATCH_CACHE_MAX: Final[int] = 200


# =============================================================================
# 갤러리 엔트리 (인물별 특징 저장)
# =============================================================================

class _GalleryEntry:
    """
    갤러리 개별 인물 엔트리.

    EMA로 업데이트되는 대표 특징 벡터와 메타데이터를 관리합니다.

    Attributes:
        person_id: 인물 ID
        feature: EMA 대표 특징 벡터 (L2 정규화)
        sample_count: 누적 특징 샘플 수
        last_frame: 마지막 업데이트 프레임
        creation_frame: 생성 프레임
    """

    __slots__ = (
        "person_id",
        "feature",
        "sample_count",
        "last_frame",
        "creation_frame",
    )

    def __init__(
        self,
        person_id: int,
        feature: NDArray[np.float64],
        frame_index: int,
    ) -> None:
        self.person_id: int = person_id
        self.feature: NDArray[np.float64] = feature.copy()
        self.sample_count: int = 1
        self.last_frame: int = frame_index
        self.creation_frame: int = frame_index

    def update(
        self,
        new_feature: NDArray[np.float64],
        momentum: float,
        frame_index: int,
    ) -> None:
        """
        EMA로 대표 특징 업데이트.

        Args:
            new_feature: 새 특징 벡터 (L2 정규화)
            momentum: EMA 모멘텀 (0~1)
            frame_index: 현재 프레임
        """
        # 초기 수집 기간 → 낮은 모멘텀으로 빠르게 적응
        effective_momentum = momentum
        if self.sample_count < EMA_MIN_SAMPLES:
            effective_momentum = EMA_MOMENTUM_INITIAL

        self.feature = (
            effective_momentum * self.feature
            + (1.0 - effective_momentum) * new_feature
        )

        # 재정규화
        norm = float(np.linalg.norm(self.feature))
        if norm > FEATURE_NORMALIZE_EPS:
            self.feature /= norm

        self.sample_count += 1
        self.last_frame = frame_index

    @property
    def age(self) -> int:
        """마지막 업데이트 이후 경과 프레임."""
        return 0  # 외부에서 frame_index - last_frame으로 계산

    def __repr__(self) -> str:
        return (
            f"_GalleryEntry(id={self.person_id}, "
            f"samples={self.sample_count}, "
            f"last={self.last_frame})"
        )


# =============================================================================
# Re-ID 모듈
# =============================================================================

class ReIDModule:
    """
    외관 기반 선수 재식별 모듈.

    COURTVIEW_reid.pt (ResNet50 + embedding) PyTorch 모델로
    512-dim 외관 특징을 추출하고, EMA 갤러리에 저장합니다.
    코사인 유사도로 1:N 매칭하여 오클루전/프레임 아웃 후
    동일 인물을 재식별합니다.

    모델 미존재 시 색상 히스토그램 폴백으로 동작합니다.

    파이프라인:
        1. 선수 bbox 크롭 + 리사이즈 (256×128)
        2. ImageNet 정규화
        3. ResNet50 추론 → 512-dim embedding 벡터
        4. L2 정규화
        5. 갤러리 1:N 매칭 (코사인 유사도)
        6. EMA 갤러리 업데이트

    사용 예시::

        >>> config = ReIDConfig()
        >>> reid = ReIDModule()
        >>> reid.initialize(config)
        >>> feature = reid.extract_feature(candidate, frame)
        >>> match_id, similarity = reid.match(feature)
    """

    def __init__(self) -> None:
        """Re-ID 모듈 초기화."""
        self._lock = threading.RLock()
        self._config: ReIDConfig | None = None
        self._initialized: bool = False

        # PyTorch ResNet50 Re-ID 모델
        self._reid_model: Any = None  # torch.nn.Module
        self._reid_device: str = "cpu"

        # 갤러리: person_id → _GalleryEntry (LRU 순서 유지)
        self._gallery: OrderedDict[int, _GalleryEntry] = OrderedDict()
        self._next_person_id: int = 1

        # 현재 프레임 인덱스
        self._current_frame: int = 0
        self._last_cleanup_frame: int = 0

        # 통계
        self._total_extracted: int = 0
        self._total_matched: int = 0
        self._total_new: int = 0

        logger.info("ReIDModule 인스턴스 생성")

    # =========================================================================
    # 공개 속성
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def gallery_size(self) -> int:
        """갤러리 내 인물 수."""
        return len(self._gallery)

    @property
    def total_extracted(self) -> int:
        """누적 특징 추출 수."""
        return self._total_extracted

    @property
    def total_matched(self) -> int:
        """누적 매칭 수."""
        return self._total_matched

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    def initialize(self, config: ReIDConfig) -> None:
        """
        Re-ID 모듈 초기화 및 ResNet50 모델 로드.

        Args:
            config: Re-ID 설정
        """
        with self._lock:
            if self._initialized:
                logger.warning("이미 초기화된 Re-ID 모듈을 재초기화합니다")
                self.shutdown()

            self._config = config
            self._load_reid_model(config)

            self._gallery.clear()
            self._next_person_id = 1
            self._current_frame = 0
            self._last_cleanup_frame = 0
            self._total_extracted = 0
            self._total_matched = 0
            self._total_new = 0
            self._initialized = True
            logger.info("ReIDModule 초기화 완료: %r", config)

    def _load_reid_model(self, config: ReIDConfig) -> None:
        """
        COURTVIEW_reid.pt ResNet50 Re-ID 모델 로드.

        체크포인트 구조:
            - backbone: ResNet50 (avgpool까지)
            - embedding: Linear(2048, 512)
            - classifier: Linear(512, 130) — 추론 시 미사용

        추론 시 backbone → embedding → L2 정규화 → 512-dim 출력.

        Args:
            config: Re-ID 설정
        """
        model_path = Path(_DEFAULT_REID_MODEL_PATH)
        if not model_path.exists():
            logger.info(
                "COURTVIEW_reid.pt 미존재 (%s), 색상 히스토그램 폴백",
                model_path,
            )
            self._reid_model = None
            return

        try:
            import torch
            import torch.nn as nn
            from torchvision import models as tv_models

            checkpoint = torch.load(
                str(model_path), map_location="cpu", weights_only=False,
            )

            # state_dict 추출 (체크포인트 형식에 따라)
            if isinstance(checkpoint, dict):
                state_dict = checkpoint.get("model_state_dict", checkpoint)
            else:
                state_dict = checkpoint

            # 아키텍처 재구성: ResNet50 backbone + embedding + classifier
            # embedding 입출력 크기를 state_dict에서 추론
            embedding_weight = state_dict.get("embedding.weight")
            classifier_weight = state_dict.get("classifier.weight")

            if embedding_weight is None:
                logger.warning("embedding.weight 누락, Re-ID 모델 비활성화")
                self._reid_model = None
                return

            embed_out = embedding_weight.shape[0]  # 512
            embed_in = embedding_weight.shape[1]   # 2048

            # ResNet50 기반 Re-ID 모델 구성
            backbone = tv_models.resnet50(weights=None)
            # avgpool 출력: (batch, 2048)
            # fc 레이어 제거 → identity
            backbone.fc = nn.Identity()

            # 전체 모델 조립
            class _ReIDNet(nn.Module):
                """ResNet50 + Embedding Re-ID 네트워크."""

                def __init__(
                    self,
                    base: nn.Module,
                    embedding_layer: nn.Linear,
                ) -> None:
                    super().__init__()
                    self.backbone = base
                    self.embedding = embedding_layer

                def forward(self, x: torch.Tensor) -> torch.Tensor:
                    feat = self.backbone(x)       # (B, 2048)
                    emb = self.embedding(feat)    # (B, 512)
                    return emb

            embedding_layer = nn.Linear(embed_in, embed_out, bias=True)

            model = _ReIDNet(backbone, embedding_layer)

            # state_dict 로드 (backbone.* + embedding.*)
            # classifier는 추론 시 불필요하므로 strict=False
            model.load_state_dict(state_dict, strict=False)

            # GPU 설정
            device = "cpu"
            if config.device == "cuda":
                if torch.cuda.is_available():
                    device = "cuda"
                else:
                    logger.warning("CUDA 사용 불가, CPU로 Re-ID 모델 실행")

            model = model.to(device)
            model.eval()
            self._reid_model = model
            self._reid_device = device

            logger.info(
                "COURTVIEW_reid.pt 로드 완료: ResNet50+embedding(%d→%d), device=%s",
                embed_in,
                embed_out,
                device,
            )

        except Exception as exc:
            logger.warning(
                "COURTVIEW_reid.pt 로드 실패 (색상 히스토그램 폴백): %s", exc,
            )
            self._reid_model = None

    def shutdown(self) -> None:
        """Re-ID 모듈 종료 및 리소스 해제."""
        with self._lock:
            self._reid_model = None
            self._gallery.clear()
            self._initialized = False
            logger.info(
                "ReIDModule 종료: 추출=%d, 매칭=%d, 신규=%d",
                self._total_extracted,
                self._total_matched,
                self._total_new,
            )

    def reset(self) -> None:
        """갤러리 및 통계 초기화 (모델 유지)."""
        with self._lock:
            self._gallery.clear()
            self._next_person_id = 1
            self._total_extracted = 0
            self._total_matched = 0
            self._total_new = 0

    # =========================================================================
    # 특징 추출
    # =========================================================================

    def extract_feature(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
    ) -> NDArray[np.float64] | None:
        """
        선수 후보의 외관 특징 벡터 추출.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지

        Returns:
            512-dim L2 정규화 특징 벡터 (None이면 추출 실패)
        """
        if not self._initialized or self._config is None:
            return None

        # 선수/심판만 특징 추출
        if candidate.class_id not in (PLAYER_CLASS_ID_PLAYER, PLAYER_CLASS_ID_REFEREE):
            return None

        # bbox 크롭
        crop = self._crop_person(candidate, frame)
        if crop is None:
            return None

        # 모델 추론 또는 폴백
        if self._reid_model is not None:
            feature = self._resnet_inference(crop)
        else:
            feature = self._color_histogram_feature(crop)

        if feature is None:
            return None

        self._total_extracted += 1
        return feature

    def extract_batch(
        self,
        candidates: list[_PlayerCandidate],
        frame: NDArray[np.uint8],
    ) -> list[NDArray[np.float64] | None]:
        """
        배치 특징 추출.

        Args:
            candidates: 후보 목록
            frame: BGR 이미지

        Returns:
            특징 벡터 목록 (입력 순서 유지, 실패 시 None)
        """
        return [self.extract_feature(c, frame) for c in candidates]

    # =========================================================================
    # 매칭
    # =========================================================================

    def match(
        self,
        feature: NDArray[np.float64],
        frame_index: int = 0,
    ) -> tuple[int, float]:
        """
        특징 벡터를 갤러리와 1:N 매칭.

        Args:
            feature: 512-dim L2 정규화 특징 벡터
            frame_index: 현재 프레임 인덱스

        Returns:
            (person_id, similarity)
            매칭 실패 시 새 person_id 발급 (similarity=0.0)
        """
        with self._lock:
            if not self._initialized or self._config is None:
                return self._create_new_person(feature, frame_index), 0.0

            self._current_frame = frame_index
            config = self._config

            # 갤러리가 비어있으면 신규 등록
            if not self._gallery:
                return self._create_new_person(feature, frame_index), 0.0

            # 코사인 유사도 계산
            best_id = -1
            best_sim = -1.0

            for pid, entry in self._gallery.items():
                sim = self._cosine_similarity(feature, entry.feature)

                if sim > best_sim:
                    best_sim = sim
                    best_id = pid

            # 매칭 판정
            if best_sim >= config.similarity_threshold and best_id >= 0:
                # 매칭 성공 → 갤러리 업데이트
                entry = self._gallery[best_id]
                entry.update(feature, config.ema_momentum, frame_index)

                # LRU 업데이트
                self._gallery.move_to_end(best_id)

                self._total_matched += 1
                return best_id, best_sim

            # 매칭 실패 → 신규 등록
            return self._create_new_person(feature, frame_index), 0.0

    def match_or_update(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
        frame_index: int = 0,
        track_id: int | None = None,
    ) -> tuple[int, float]:
        """
        특징 추출 + 매칭/갤러리 업데이트 통합.

        track_id가 이미 갤러리에 있으면 업데이트만,
        없으면 매칭을 시도합니다.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지
            frame_index: 프레임 인덱스
            track_id: 추적 ID (있으면 직접 갤러리 업데이트)

        Returns:
            (person_id, similarity)
        """
        feature = self.extract_feature(candidate, frame)
        if feature is None:
            if track_id is not None and track_id in self._gallery:
                return track_id, 1.0
            return -1, 0.0

        with self._lock:
            config = self._config
            if config is None:
                return -1, 0.0

            # track_id가 갤러리에 존재하면 직접 업데이트
            if track_id is not None and track_id in self._gallery:
                entry = self._gallery[track_id]

                # 갱신 간격 체크
                if frame_index - entry.last_frame >= config.gallery_update_interval:
                    entry.update(feature, config.ema_momentum, frame_index)
                    self._gallery.move_to_end(track_id)

                return track_id, 1.0

            # 새 매칭 시도
            return self.match(feature, frame_index)

    # =========================================================================
    # 크로스뷰 Re-ID
    # =========================================================================

    def match_cross_view(
        self,
        features: dict[str, NDArray[np.float64]],
        frame_index: int = 0,
    ) -> tuple[int, float]:
        """
        멀티뷰 특징 융합 후 매칭.

        여러 카메라 뷰의 특징을 평균 융합하여 매칭합니다.

        Args:
            features: 카메라 ID → 특징 벡터 매핑
            frame_index: 프레임 인덱스

        Returns:
            (person_id, similarity)
        """
        if not features:
            return -1, 0.0

        # 특징 평균 융합
        feature_list = list(features.values())
        fused = np.mean(np.array(feature_list), axis=0).astype(np.float64)

        # L2 재정규화
        norm = float(np.linalg.norm(fused))
        if norm > FEATURE_NORMALIZE_EPS:
            fused /= norm

        return self.match(fused, frame_index)

    # =========================================================================
    # 갤러리 관리
    # =========================================================================

    def cleanup_gallery(self, current_frame: int) -> int:
        """
        오래된 갤러리 엔트리 정리.

        Args:
            current_frame: 현재 프레임 인덱스

        Returns:
            삭제된 엔트리 수
        """
        if self._config is None:
            return 0

        with self._lock:
            max_age = self._config.gallery_feature_max_age
            max_persons = self._config.gallery_max_persons

            removed = 0
            expired_ids: list[int] = []

            for pid, entry in self._gallery.items():
                if current_frame - entry.last_frame > max_age:
                    expired_ids.append(pid)

            for pid in expired_ids:
                del self._gallery[pid]
                removed += 1

            # 최대 인물 수 초과 → LRU로 가장 오래된 것 삭제
            while len(self._gallery) > max_persons:
                oldest_pid, _ = self._gallery.popitem(last=False)
                removed += 1

            if removed > 0:
                logger.debug(
                    "갤러리 정리: %d명 삭제, 현재 %d명",
                    removed,
                    len(self._gallery),
                )

            self._last_cleanup_frame = current_frame
            return removed

    def get_feature(self, person_id: int) -> NDArray[np.float64] | None:
        """
        갤러리에서 특정 인물의 대표 특징 조회.

        Args:
            person_id: 인물 ID

        Returns:
            특징 벡터 (없으면 None)
        """
        entry = self._gallery.get(person_id)
        if entry is None:
            return None
        return entry.feature.copy()

    def remove_person(self, person_id: int) -> None:
        """
        갤러리에서 인물 삭제.

        Args:
            person_id: 삭제할 인물 ID
        """
        with self._lock:
            self._gallery.pop(person_id, None)

    # =========================================================================
    # 내부 메서드 — 인물 크롭
    # =========================================================================

    @staticmethod
    def _crop_person(
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
    ) -> NDArray[np.uint8] | None:
        """
        후보 bbox 크롭 (확장 + 클리핑).

        Args:
            candidate: 선수 후보
            frame: BGR 이미지

        Returns:
            크롭 이미지 (None이면 유효하지 않음)
        """
        fh, fw = frame.shape[:2]

        # bbox 확장
        cx = candidate.center_x
        cy = candidate.center_y
        half_w = candidate.bbox_w * BBOX_EXPANSION_RATIO / 2.0
        half_h = candidate.bbox_h * BBOX_EXPANSION_RATIO / 2.0

        x1 = max(0, int(cx - half_w))
        y1 = max(0, int(cy - half_h))
        x2 = min(fw, int(cx + half_w))
        y2 = min(fh, int(cy + half_h))

        crop_w = x2 - x1
        crop_h = y2 - y1

        # 최소 크기 검증
        if crop_w < MIN_BBOX_SIZE[1] or crop_h < MIN_BBOX_SIZE[0]:
            return None

        return frame[y1:y2, x1:x2].copy()

    # =========================================================================
    # 내부 메서드 — ResNet50 Re-ID 추론
    # =========================================================================

    def _resnet_inference(
        self,
        crop: NDArray[np.uint8],
    ) -> NDArray[np.float64] | None:
        """
        ResNet50 Re-ID PyTorch 모델 추론.

        backbone(ResNet50) → embedding(2048→512) → L2 정규화 → 512-dim 출력.

        Args:
            crop: BGR 크롭 이미지

        Returns:
            512-dim L2 정규화 특징 벡터
        """
        if self._reid_model is None:
            return None

        try:
            import torch

            input_h, input_w = REID_INPUT_SIZE

            # 리사이즈
            resized = cv2.resize(crop, (input_w, input_h), interpolation=cv2.INTER_LINEAR)

            # BGR → RGB + float32 정규화
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0

            # ImageNet 정규화
            mean = np.array(NORMALIZE_MEAN, dtype=np.float32)
            std = np.array(NORMALIZE_STD, dtype=np.float32)
            normalized = (rgb - mean) / std

            # (H, W, C) → (1, C, H, W) tensor
            input_tensor = torch.from_numpy(
                normalized.transpose(2, 0, 1)[np.newaxis, ...],
            ).to(self._reid_device)

            # PyTorch 추론
            with torch.no_grad():
                embedding = self._reid_model(input_tensor)

            feature = embedding.cpu().numpy().flatten().astype(np.float64)

            # L2 정규화
            if NORMALIZE_FEATURES:
                norm = float(np.linalg.norm(feature))
                if norm > FEATURE_NORMALIZE_EPS:
                    feature /= norm

            return feature

        except Exception as exc:
            logger.debug("ResNet50 Re-ID 추론 실패: %s", exc)
            return None

    # =========================================================================
    # 내부 메서드 — 색상 히스토그램 폴백
    # =========================================================================

    @staticmethod
    def _color_histogram_feature(
        crop: NDArray[np.uint8],
    ) -> NDArray[np.float64] | None:
        """
        색상 히스토그램 기반 특징 추출 (모델 없을 때 폴백).

        HSV 히스토그램 + 공간 분할로 외관 특징을 생성합니다.
        정밀도는 ResNet50보다 낮지만 모델 없이 동작합니다.

        Args:
            crop: BGR 크롭 이미지

        Returns:
            L2 정규화 특징 벡터
        """
        if crop.size == 0:
            return None

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        h, w = hsv.shape[:2]

        # 상/중/하 3분할 히스토그램
        parts: list[NDArray[np.float64]] = []
        third_h = max(1, h // 3)

        for i in range(3):
            y_start = i * third_h
            y_end = min(h, (i + 1) * third_h) if i < 2 else h
            part = hsv[y_start:y_end, :, :]

            # H: 30 bins, S: 32 bins
            hist_h = cv2.calcHist(
                [part], [0], None, [30], [0, 180],
            ).flatten().astype(np.float64)
            hist_s = cv2.calcHist(
                [part], [1], None, [32], [0, 256],
            ).flatten().astype(np.float64)

            # 각 파트 히스토그램 정규화
            h_sum = hist_h.sum()
            if h_sum > 0:
                hist_h /= h_sum
            s_sum = hist_s.sum()
            if s_sum > 0:
                hist_s /= s_sum

            parts.append(hist_h)
            parts.append(hist_s)

        # 전체 연결 → 고정 길이 벡터
        feature = np.concatenate(parts)

        # L2 정규화
        norm = float(np.linalg.norm(feature))
        if norm > FEATURE_NORMALIZE_EPS:
            feature /= norm

        return feature

    # =========================================================================
    # 내부 메서드 — 유사도 / 신규 등록
    # =========================================================================

    @staticmethod
    def _cosine_similarity(
        a: NDArray[np.float64],
        b: NDArray[np.float64],
    ) -> float:
        """
        코사인 유사도 계산 (L2 정규화된 벡터 간).

        Args:
            a: 벡터 A
            b: 벡터 B

        Returns:
            코사인 유사도 (-1.0~1.0)
        """
        # L2 정규화된 벡터의 내적 = 코사인 유사도
        dot = float(np.dot(a, b))
        return max(-1.0, min(1.0, dot))

    def _create_new_person(
        self,
        feature: NDArray[np.float64],
        frame_index: int,
    ) -> int:
        """
        신규 인물 등록.

        Args:
            feature: 특징 벡터
            frame_index: 현재 프레임

        Returns:
            새 person_id
        """
        pid = self._next_person_id
        self._next_person_id += 1

        entry = _GalleryEntry(pid, feature, frame_index)
        self._gallery[pid] = entry

        # 최대 인물 수 초과 → 가장 오래된 것 삭제
        if self._config is not None:
            while len(self._gallery) > self._config.gallery_max_persons:
                self._gallery.popitem(last=False)

        self._total_new += 1
        return pid

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def __repr__(self) -> str:
        model_str = "ResNet50" if self._reid_model is not None else "histogram"
        return (
            f"ReIDModule({model_str}, "
            f"gallery={len(self._gallery)}, "
            f"extracted={self._total_extracted}, "
            f"matched={self._total_matched})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "ReIDModule",
    "ReIDConfig",
]

__version__: str = "1.0.0"
