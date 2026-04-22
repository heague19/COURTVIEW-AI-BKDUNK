# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: detection/player_detection
파일: team_classifier.py
설명: 유니폼 색상 기반 팀 분류기
      - 가슴 ROI 추출 + 피부색 마스킹 제외
      - HSV 히스토그램 주색상 분석
      - K-Means(k=2) 비지도 클러스터링으로 팀 자동 분류
      - 심판/코치/스태프는 분류 대상에서 제외
      - 멀티뷰 투표 지원

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-20
버전: 1.0.0

의존성:
    - shared/constants/player_constants.py: ROI 비율, 피부색 범위, 밝기 임계값
    - shared/dto/player_dto.py: Team
    - detection/player_detection/models.py: TeamClassifierConfig, _PlayerCandidate, _UniformROI
"""

from __future__ import annotations

# =============================================================================
# 표준 라이브러리
# =============================================================================
import logging
import threading
from collections import defaultdict
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
    CHEST_CROP_X_END,
    CHEST_CROP_X_START,
    CHEST_CROP_Y_END,
    CHEST_CROP_Y_START,
    NORMALIZE_MEAN,
    NORMALIZE_STD,
    PLAYER_CLASS_ID_PLAYER,
    TEAM_SKIN_HUE_RANGE,
    TEAM_SKIN_SAT_RANGE,
    TEAM_VALUE_DARK_THRESHOLD,
    TEAM_VALUE_LIGHT_THRESHOLD,
)
from shared.dto.player_dto import Team
from detection.player_detection.models import (
    TeamClassifierConfig,
    _PlayerCandidate,
    _UniformROI,
)

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 모듈 상수
# =============================================================================

# 피부색 HSV 범위 (마스킹 제외용)
_SKIN_HUE_LOW: Final[int] = TEAM_SKIN_HUE_RANGE[0]
_SKIN_HUE_HIGH: Final[int] = TEAM_SKIN_HUE_RANGE[1]
_SKIN_SAT_LOW: Final[int] = TEAM_SKIN_SAT_RANGE[0]
_SKIN_SAT_HIGH: Final[int] = TEAM_SKIN_SAT_RANGE[1]
_SKIN_VAL_LOW: Final[int] = 60
_SKIN_VAL_HIGH: Final[int] = 255

# K-Means 반복 횟수 / 수렴 기준
_KMEANS_MAX_ITER: Final[int] = 10
_KMEANS_EPSILON: Final[float] = 1.0
_KMEANS_ATTEMPTS: Final[int] = 3

# 클러스터링 최소 샘플 수
_MIN_SAMPLES_FOR_CLUSTERING: Final[int] = 2

# 색상 거리 임계값 (동일 팀 판정)
_COLOR_DISTANCE_THRESHOLD: Final[float] = 60.0

# 멀티뷰 투표 최소 일치 비율
_MULTI_VIEW_AGREEMENT_RATIO: Final[float] = 0.6

# 팀 분류 임베딩 모델 경로 (Triplet Loss 학습, 128-dim, K-Means 추론)
_DEFAULT_TEAM_MODEL_PATH: Final[str] = "weights/COURTVIEW_team.pt"
# 우선순위: weights/CV-team.pt > 학습 디렉토리 team_embed_v4.pt
_EMBED_MODEL_PATH: Final[str] = "weights/CV-team.pt"
_EMBED_MODEL_PATH_FALLBACK: Final[str] = (
    "D:/SPOIN/training/team_classification/weights/team_embed_v4.pt"
)

# DL 모델 입력 크기
_TEAM_DL_INPUT_SIZE: Final[tuple[int, int]] = (224, 224)
_EMBED_INPUT_SIZE: Final[tuple[int, int]] = (64, 128)  # (W, H)

# DL 모델 클래스 인덱스
_TEAM_DL_CLASS_A: Final[int] = 0  # team_a
_TEAM_DL_CLASS_B: Final[int] = 1  # team_b

# DL Primary + K-Means 보조 가중 비율
_DL_WEIGHT: Final[float] = 0.75
_KMEANS_WEIGHT: Final[float] = 0.25


# =============================================================================
# 팀 분류기
# =============================================================================

class TeamClassifier:
    """
    DL Primary + HSV K-Means 보조 하이브리드 팀 분류기.

    COURTVIEW_team.pt 자체 학습 ResNet 모델을 Primary로 사용하고,
    K-Means(k=2) 클러스터링을 보조로 적용합니다.
    모델 미존재 시 K-Means 단독으로 동작합니다.

    파이프라인:
        1. 가슴 ROI 추출 (bbox 내 상대 좌표)
        2. 피부색 마스킹 제외 (HSV 범위)
        3a. DL Primary: ROI → ResNet 추론 → team_a/team_b (75%)
        3b. K-Means 보조: HSV 히스토그램 → 클러스터 거리 (25%)
        4. 가중 합산 → 최종 팀 판정
        5. (멀티뷰) 동일 인물 다중 뷰 투표 → 최종 팀

    팀 색상 학습 (K-Means 보조):
        - 경기 시작 시 첫 N프레임(기본 30)의 색상 수집
        - 충분한 샘플 확보 후 자동 클러스터링
        - 클러스터 중심 고정 후 분류 모드 전환
        - 밝기(V채널)로 홈/원정 구분 (어두운=홈, 밝은=원정)

    사용 예시::

        >>> config = TeamClassifierConfig()
        >>> classifier = TeamClassifier()
        >>> classifier.initialize(config)
        >>> team, conf = classifier.classify(candidate, frame)
    """

    def __init__(self) -> None:
        """분류기 초기화."""
        self._lock = threading.RLock()
        self._config: TeamClassifierConfig | None = None
        self._initialized: bool = False

        # DL 모델 (COURTVIEW_team.pt)
        self._dl_model: Any = None  # torch.nn.Module
        self._dl_device: str = "cpu"
        self._dl_classes: list[str] = []

        # 클러스터 중심 (k=2): [H, S, V] 각 3차원
        self._cluster_centers: NDArray[np.float64] | None = None
        # 팀 A/B 매핑: 클러스터 인덱스 → Team
        self._cluster_team_map: dict[int, Team] = {}

        # 색상 샘플 수집 (클러스터링 전)
        self._color_samples: list[NDArray[np.float64]] = []
        self._calibration_done: bool = False

        # 트랙별 팀 잠금 (투표 기반 확정)
        # track_id → {"team_a": 횟수, "team_b": 횟수}
        self._track_votes: dict[int, dict[str, int]] = {}
        # track_id → 확정된 Team (None이면 미확정)
        self._track_locked: dict[int, Team] = {}
        # 팀 잠금 최소 투표 수
        _LOCK_MIN_VOTES: int = 3

        # 통계
        self._total_classified: int = 0
        self._total_skipped: int = 0

        logger.info("TeamClassifier 인스턴스 생성")

    # =========================================================================
    # 공개 속성
    # =========================================================================

    @property
    def is_initialized(self) -> bool:
        """초기화 완료 여부."""
        return self._initialized

    @property
    def is_calibrated(self) -> bool:
        """팀 색상 캘리브레이션 완료 여부."""
        return self._calibration_done

    @property
    def total_classified(self) -> int:
        """누적 분류 수."""
        return self._total_classified

    @property
    def cluster_centers(self) -> NDArray[np.float64] | None:
        """현재 클러스터 중심 (디버그용)."""
        if self._cluster_centers is None:
            return None
        return self._cluster_centers.copy()

    # =========================================================================
    # 초기화 / 종료
    # =========================================================================

    def initialize(self, config: TeamClassifierConfig) -> None:
        """
        분류기 초기화 및 DL 모델 로드.

        Args:
            config: 팀 분류 설정
        """
        with self._lock:
            self._config = config
            self._cluster_centers = None
            self._cluster_team_map.clear()
            self._color_samples.clear()
            self._calibration_done = False
            self._total_classified = 0
            self._total_skipped = 0

            # DL 모델 로드 (COURTVIEW_team.pt — ResNet18 KBL 학습)
            # 실내: DL 75% + K-Means 25% 하이브리드
            # 야외: DL 실패 시 K-Means 폴백
            self._load_dl_model(config)

            self._initialized = True
            logger.info("TeamClassifier 초기화 완료: %r", config)

    def _load_dl_model(self, config: TeamClassifierConfig) -> None:
        """
        팀 분류 임베딩 모델 로드 (team_embed_v3.pt).

        Triplet Loss 학습된 128-dim 임베딩 모델.
        경기 시작 시 K-Means 캘리브레이션으로 팀 자동 분리.
        """
        # 우선순위: weights/CV_team.pt → 학습 디렉토리 폴백 → 기존 분류 모델
        embed_path = Path(_EMBED_MODEL_PATH)
        embed_fallback_path = Path(_EMBED_MODEL_PATH_FALLBACK)
        legacy_path = Path(_DEFAULT_TEAM_MODEL_PATH)

        if embed_path.exists():
            model_path = embed_path
        elif embed_fallback_path.exists():
            model_path = embed_fallback_path
        else:
            model_path = legacy_path

        if not model_path.exists():
            logger.info("팀 분류 모델 없음, K-Means 단독 모드")
            self._dl_model = None
            return

        try:
            import torch
            import torch.nn as nn
            from torchvision import models as tv_models

            checkpoint = torch.load(
                str(model_path), map_location="cpu", weights_only=False,
            )
            self._dl_classes = checkpoint.get("classes", ["team_a", "team_b", "referee"])

            state_dict = checkpoint.get("model_state_dict", {})
            if not state_dict:
                self._dl_model = None
                return

            # 임베딩 모델 여부 판별 (embed_dim 키 존재)
            embed_dim = checkpoint.get("embed_dim", 0)
            self._is_embed_model = embed_dim > 0

            if self._is_embed_model:
                # TeamEmbedNet: ResNet18 → 128-dim L2 normalized
                class _TeamEmbedNet(nn.Module):
                    def __init__(self, dim: int = 128) -> None:
                        super().__init__()
                        backbone = tv_models.resnet18(weights=None)
                        self.features = nn.Sequential(*list(backbone.children())[:-1])
                        self.embed = nn.Sequential(
                            nn.Flatten(), nn.Linear(512, dim), nn.BatchNorm1d(dim),
                        )
                    def forward(self, x: torch.Tensor) -> torch.Tensor:
                        return nn.functional.normalize(
                            self.embed(self.features(x)), p=2, dim=1,
                        )

                model = _TeamEmbedNet(embed_dim)
                model.load_state_dict(state_dict)
                self._embed_centroids = None  # K-Means 센트로이드 (캘리브레이션 후 설정)
                self._embed_label_map = {}    # 클러스터 → Team 매핑
                self._embed_samples = []      # 캘리브레이션용 임베딩 수집

                # 사전 계산된 centroid 로드 (있으면 KMeans 스킵하고 직접 분류)
                self._preset_referee_centroid = None
                self._preset_team_a_centroid = None
                self._preset_team_b_centroid = None

                def _load_np(key: str) -> np.ndarray | None:
                    v = checkpoint.get(key)
                    if v is None:
                        return None
                    if torch.is_tensor(v):
                        v = v.cpu().numpy()
                    return np.asarray(v, dtype=np.float32)

                self._preset_referee_centroid = _load_np("referee_centroid")
                self._preset_team_a_centroid = _load_np("team_a_centroid")
                self._preset_team_b_centroid = _load_np("team_b_centroid")

                if (self._preset_team_a_centroid is not None
                        and self._preset_team_b_centroid is not None
                        and self._preset_referee_centroid is not None):
                    # 모든 centroid 사전 계산됨 → KMeans 스킵, 즉시 사용
                    self._embed_centroids = np.stack([
                        self._preset_team_a_centroid,
                        self._preset_team_b_centroid,
                        self._preset_referee_centroid,
                    ], axis=0)
                    self._embed_label_map = {
                        0: Team.TEAM_A,
                        1: Team.TEAM_B,
                        2: Team.REFEREE,
                    }
                    self._calibration_done = True
                    logger.info(
                        "사전 계산된 centroid 로드 → KMeans 스킵 "
                        "(team_a: %s, team_b: %s, ref: %s)",
                        checkpoint.get("team_a_n_samples", "?"),
                        checkpoint.get("team_b_n_samples", "?"),
                        checkpoint.get("referee_n_samples", "?"),
                    )
                elif self._preset_referee_centroid is not None:
                    logger.info(
                        "referee centroid만 로드 (KMeans로 team 분리): n=%s",
                        checkpoint.get("referee_n_samples", "?"),
                    )

                logger.info(
                    "팀 임베딩 모델 로드: %s (dim=%d, purity=%.1f%%)",
                    model_path.name, embed_dim,
                    checkpoint.get("purity", 0) * 100,
                )
            else:
                # 기존 직접 분류 모델 (COURTVIEW_team.pt 폴백)
                from torchvision.models.resnet import BasicBlock

                class _TeamResNet(nn.Module):
                    def __init__(self) -> None:
                        super().__init__()
                        self.features = nn.Sequential(
                            nn.Conv2d(3, 64, 7, stride=2, padding=3, bias=False),
                            nn.BatchNorm2d(64), nn.ReLU(inplace=True),
                            nn.MaxPool2d(3, stride=2, padding=1),
                            self._make_layer(64, 64, 2),
                            self._make_layer(64, 128, 2, stride=2),
                            self._make_layer(128, 256, 2, stride=2),
                            self._make_layer(256, 512, 2, stride=2),
                        )
                        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
                        self.classifier = nn.Sequential(
                            nn.Flatten(), nn.Dropout(0.5),
                            nn.Linear(512, 256), nn.ReLU(inplace=True),
                            nn.BatchNorm1d(256), nn.Dropout(0.3),
                            nn.Linear(256, 2),
                        )
                    @staticmethod
                    def _make_layer(in_ch, out_ch, blocks, stride=1):
                        downsample = None
                        if stride != 1 or in_ch != out_ch:
                            downsample = nn.Sequential(
                                nn.Conv2d(in_ch, out_ch, 1, stride=stride, bias=False),
                                nn.BatchNorm2d(out_ch),
                            )
                        layers = [BasicBlock(in_ch, out_ch, stride=stride, downsample=downsample)]
                        for _ in range(1, blocks):
                            layers.append(BasicBlock(out_ch, out_ch))
                        return nn.Sequential(*layers)
                    def forward(self, x):
                        return self.classifier(self.avgpool(self.features(x)))

                model = _TeamResNet()
                model.load_state_dict(state_dict)
                self._is_embed_model = False
                logger.info("기존 팀 분류 모델 로드: %s", model_path.name)

            # GPU 설정
            device = "cpu"
            if config.device == "cuda":
                if torch.cuda.is_available():
                    device = "cuda"
            model = model.to(device)
            model.eval()
            self._dl_model = model
            self._dl_device = device

        except Exception as exc:
            logger.warning("팀 분류 모델 로드 실패: %s", exc)
            self._dl_model = None

    @property
    def has_dl_model(self) -> bool:
        """DL 모델 로드 여부."""
        return self._dl_model is not None

    def _calibrate_embed(self) -> None:
        """임베딩 캘리브레이션 — 수집된 임베딩으로 K-Means(3) 클러스터링."""
        from sklearn.cluster import KMeans as _KMeans

        X = np.array(self._embed_samples)
        n_clusters = min(3, len(X))
        km = _KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
        km.fit(X)
        self._embed_centroids = km.cluster_centers_

        sizes = [(km.labels_ == k).sum() for k in range(n_clusters)]

        # CV-team.pt 모델은 ["team_a", "team_b", "referee"] 3-class 학습
        # 사전 계산된 referee_centroid가 있으면 클러스터 매핑에 직접 사용
        preset_ref = getattr(self, "_preset_referee_centroid", None)

        if n_clusters == 3 and preset_ref is not None:
            # 각 KMeans 센트로이드와 referee_centroid의 cosine distance
            # (모든 임베딩이 L2 정규화되어 있음)
            ref_sims = [
                float(np.dot(self._embed_centroids[k], preset_ref))
                for k in range(3)
            ]
            # 가장 가까운 (높은 유사도) 클러스터 = referee
            ref_cluster = int(np.argmax(ref_sims))
            other = [k for k in range(3) if k != ref_cluster]
            # 나머지 두 클러스터는 크기로 구분 (큰쪽/작은쪽)
            other_sorted = sorted(other, key=lambda k: sizes[k])
            self._embed_label_map = {
                ref_cluster: Team.REFEREE,
                other_sorted[0]: Team.TEAM_A,
                other_sorted[1]: Team.TEAM_B,
            }
            logger.info(
                "referee centroid 기반 매핑: ref_sims=%s → ref_cluster=%d",
                [f"{s:.3f}" for s in ref_sims], ref_cluster,
            )
        elif n_clusters == 3:
            # 폴백: 크기 기반
            sc = sorted(range(n_clusters), key=lambda k: sizes[k])
            self._embed_label_map = {
                sc[0]: Team.REFEREE,
                sc[1]: Team.TEAM_A,
                sc[2]: Team.TEAM_B,
            }
        elif n_clusters == 2:
            sc = sorted(range(n_clusters), key=lambda k: sizes[k])
            self._embed_label_map = {sc[0]: Team.TEAM_A, sc[1]: Team.TEAM_B}

        self._embed_samples.clear()
        self._calibration_done = True
        logger.info(
            "임베딩 캘리브레이션 완료: %d 클러스터, sizes=%s, label_map=%s",
            n_clusters, sizes,
            {k: v.value for k, v in self._embed_label_map.items()},
        )

    def shutdown(self) -> None:
        """분류기 종료 및 리소스 해제."""
        with self._lock:
            self._initialized = False
            self._dl_model = None
            self._dl_classes.clear()
            self._cluster_centers = None
            self._cluster_team_map.clear()
            self._color_samples.clear()
            self._calibration_done = False
            logger.info(
                "TeamClassifier 종료: 분류=%d, 스킵=%d",
                self._total_classified,
                self._total_skipped,
            )

    def reset(self) -> None:
        """통계 초기화 (캘리브레이션 유지)."""
        with self._lock:
            self._total_classified = 0
            self._total_skipped = 0

    # =========================================================================
    # Few-shot 캘리브레이션 (ResNet feature 기반)
    # =========================================================================

    def _extract_crop_feature(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
    ) -> NDArray[np.float64] | None:
        """
        선수 상체 crop → ResNet feature 임베딩 추출.

        torchvision ResNet18 pretrained의 avgpool 출력 (512D)을 사용합니다.
        모델은 첫 호출 시 lazy 로드.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지

        Returns:
            512D L2-정규화 특징 벡터 또는 None
        """
        if not hasattr(self, "_feature_model") or self._feature_model is None:
            try:
                import torch
                from torchvision import models, transforms

                model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
                model.fc = torch.nn.Identity()
                model.eval()
                self._feature_model = model
                self._feature_device = "cpu"
                self._feature_transform = transforms.Compose([
                    transforms.ToPILImage(),
                    transforms.Resize((128, 64)),
                    transforms.ToTensor(),
                    transforms.Normalize(
                        mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225],
                    ),
                ])
            except Exception as exc:
                logger.warning("ResNet feature extractor 로드 실패: %s", exc)
                self._feature_model = None
                return None

        fh, fw = frame.shape[:2]
        config = self._config
        if config is None:
            return None

        # 상체 ROI 크롭
        y1 = int(candidate.bbox_y)
        y2 = int(candidate.bbox_y + candidate.bbox_h * 0.6)  # 상체 60%
        x1 = int(candidate.bbox_x)
        x2 = int(candidate.bbox_x + candidate.bbox_w)

        x1 = max(0, min(x1, fw - 1))
        x2 = max(x1 + 1, min(x2, fw))
        y1 = max(0, min(y1, fh - 1))
        y2 = max(y1 + 1, min(y2, fh))

        crop = frame[y1:y2, x1:x2]
        if crop.shape[0] < 20 or crop.shape[1] < 10:
            return None

        try:
            import torch

            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            tensor = self._feature_transform(rgb).unsqueeze(0)

            with torch.no_grad():
                feat = self._feature_model(tensor).numpy().flatten()

            # L2 정규화
            norm = np.linalg.norm(feat)
            if norm > 1e-6:
                feat = feat / norm
            return feat.astype(np.float64)
        except Exception:
            return None

    def calibrate(
        self,
        candidates: list[_PlayerCandidate],
        frame: NDArray[np.uint8],
    ) -> bool:
        """
        Few-shot 팀 캘리브레이션 (ResNet feature + K-Means).

        경기 시작 시 여러 프레임에서 선수 crop의 ResNet feature를 수집하고,
        충분한 샘플이 모이면 K-Means(k=2)로 팀을 자동 분류합니다.
        HSV 색상 대신 512D 딥러닝 특징을 사용하여 정확도가 높습니다.

        Args:
            candidates: 현재 프레임의 선수 후보 목록
            frame: BGR 이미지

        Returns:
            캘리브레이션 완료 여부
        """
        if not self._initialized or self._config is None:
            return False

        with self._lock:
            if self._calibration_done:
                return True

            # 선수 클래스만 feature 수집
            for candidate in candidates:
                if candidate.class_id != PLAYER_CLASS_ID_PLAYER:
                    continue

                # ResNet feature 추출 시도
                feat = self._extract_crop_feature(candidate, frame)
                if feat is not None:
                    if not hasattr(self, "_feature_samples"):
                        self._feature_samples: list[NDArray[np.float64]] = []
                    self._feature_samples.append(feat)

                # HSV 색상도 병행 수집 (폴백용)
                roi = self._extract_uniform_roi(candidate, frame)
                if roi.is_valid:
                    hsv_vec = np.array(
                        [roi.dominant_hue, roi.dominant_saturation, roi.dominant_value],
                        dtype=np.float64,
                    )
                    self._color_samples.append(hsv_vec)

            # HSV K-Means 클러스터링 (가장 안정적)
            if len(self._color_samples) >= _MIN_SAMPLES_FOR_CLUSTERING * 2:
                return self._run_clustering()

            return False

    def _run_feature_clustering(self) -> bool:
        """
        ResNet feature 기반 K-Means(k=2) 클러스터링.

        512D feature 공간에서 클러스터링하여 HSV보다 정확한 팀 분류.

        Returns:
            성공 여부
        """
        feat_samples = getattr(self, "_feature_samples", [])
        samples = np.array(feat_samples, dtype=np.float32)

        if len(samples) < 10:
            return False

        criteria = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
            20,
            0.1,
        )

        try:
            compactness, labels, centers = cv2.kmeans(
                samples,
                K=2,
                bestLabels=None,
                criteria=criteria,
                attempts=5,
                flags=cv2.KMEANS_PP_CENTERS,
            )
        except cv2.error:
            logger.warning("Feature K-Means 실패, HSV 폴백")
            return False

        if centers is None or len(centers) < 2:
            return False

        # feature 클러스터 중심 저장
        self._feature_centers = centers.astype(np.float64)
        self._feature_team_map = {0: Team.TEAM_A, 1: Team.TEAM_B}

        # HSV 클러스터도 병행 (폴백용)
        if len(self._color_samples) >= _MIN_SAMPLES_FOR_CLUSTERING * 2:
            self._run_clustering()

        self._calibration_done = True
        self._feature_samples = []  # 메모리 해제

        logger.info(
            "Few-shot 팀 캘리브레이션 완료 (ResNet feature, %d 샘플)",
            len(samples),
        )

        return True

    def _classify_by_feature(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
    ) -> tuple[Team, float]:
        """
        ResNet feature 기반 팀 분류.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지

        Returns:
            (팀, 신뢰도) 튜플
        """
        centers = getattr(self, "_feature_centers", None)
        team_map = getattr(self, "_feature_team_map", None)
        if centers is None or team_map is None:
            return Team.UNKNOWN, 0.0

        feat = self._extract_crop_feature(candidate, frame)
        if feat is None:
            return Team.UNKNOWN, 0.0

        # 코사인 유사도 (L2 정규화된 벡터의 내적)
        sim_0 = float(np.dot(feat, centers[0]))
        sim_1 = float(np.dot(feat, centers[1]))

        if sim_0 > sim_1:
            team = team_map[0]
            confidence = (sim_0 - sim_1) / max(0.001, sim_0 + sim_1) + 0.5
        else:
            team = team_map[1]
            confidence = (sim_1 - sim_0) / max(0.001, sim_0 + sim_1) + 0.5

        return team, min(1.0, max(0.0, confidence))

    def _run_clustering(self) -> bool:
        """
        수집된 색상 샘플로 K-Means(k=2) 클러스터링 실행.

        클러스터 중심의 V(밝기)가 낮은 쪽을 TEAM_A(홈),
        높은 쪽을 TEAM_B(원정)로 매핑합니다.

        Returns:
            성공 여부
        """
        samples = np.array(self._color_samples, dtype=np.float32)

        if len(samples) < _MIN_SAMPLES_FOR_CLUSTERING * 2:
            return False

        criteria = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
            _KMEANS_MAX_ITER,
            _KMEANS_EPSILON,
        )

        try:
            compactness, labels, centers = cv2.kmeans(
                samples,
                K=2,
                bestLabels=None,
                criteria=criteria,
                attempts=_KMEANS_ATTEMPTS,
                flags=cv2.KMEANS_PP_CENTERS,
            )
        except cv2.error:
            logger.warning("K-Means 클러스터링 실패, 샘플 부족 또는 동일 색상")
            return False

        if centers is None or len(centers) < 2:
            return False

        self._cluster_centers = centers.astype(np.float64)

        # V(밝기) 기준으로 홈/원정 매핑
        # 어두운 유니폼 = TEAM_A(홈), 밝은 유니폼 = TEAM_B(원정)
        v_0 = float(centers[0][2])
        v_1 = float(centers[1][2])

        if v_0 <= v_1:
            self._cluster_team_map = {0: Team.TEAM_A, 1: Team.TEAM_B}
        else:
            self._cluster_team_map = {0: Team.TEAM_B, 1: Team.TEAM_A}

        self._calibration_done = True
        self._color_samples.clear()  # 메모리 해제

        logger.info(
            "TeamClassifier 캘리브레이션 완료: "
            "center_0=(H=%.0f, S=%.0f, V=%.0f)=%s, "
            "center_1=(H=%.0f, S=%.0f, V=%.0f)=%s",
            centers[0][0], centers[0][1], centers[0][2],
            self._cluster_team_map[0].value,
            centers[1][0], centers[1][1], centers[1][2],
            self._cluster_team_map[1].value,
        )

        return True

    # =========================================================================
    # 단일 후보 분류
    # =========================================================================

    def classify(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
    ) -> tuple[Team, float]:
        """
        단일 후보의 팀 분류 (DL Primary + K-Means 보조).

        DL 모델 존재 시: DL 75% + K-Means 25% 하이브리드 스코링.
        DL 모델 미존재 시: K-Means/밝기 단독 분류.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지

        Returns:
            (팀, 신뢰도) 튜플
        """
        if not self._initialized or self._config is None:
            return Team.UNKNOWN, 0.0

        with self._lock:
            # 선수가 아니면 분류 제외
            if candidate.class_id != PLAYER_CLASS_ID_PLAYER:
                self._total_skipped += 1
                return Team.UNKNOWN, 0.0

            # K-Means/밝기 보조 추론
            roi = self._extract_uniform_roi(candidate, frame)
            if not roi.is_valid:
                self._total_skipped += 1
                return Team.UNKNOWN, 0.0

            if self._calibration_done:
                aux_team, aux_conf = self._classify_by_cluster(roi)
            else:
                aux_team, aux_conf = self._classify_by_brightness(roi)

            # DL Primary 추론 (75%) + K-Means 보조 (25%)
            if self._dl_model is not None:
                dl_team, dl_conf = self._dl_inference(candidate, frame)
                if dl_team != Team.UNKNOWN:
                    if aux_team == dl_team:
                        final_conf = _DL_WEIGHT * dl_conf + _KMEANS_WEIGHT * aux_conf
                    else:
                        final_conf = dl_conf * _DL_WEIGHT
                    team = dl_team
                    final_conf = min(1.0, final_conf)
                else:
                    team = aux_team
                    final_conf = aux_conf
            else:
                team = aux_team
                final_conf = aux_conf

            if final_conf >= self._config.confidence_threshold:
                self._total_classified += 1
            return team, final_conf

    def classify_batch(
        self,
        candidates: list[_PlayerCandidate],
        frame: NDArray[np.uint8],
    ) -> list[tuple[Team, float]]:
        """
        진짜 배치 팀 분류.

        모든 선수 crop을 한 번에 GPU로 전송하여 단일 forward pass로 처리.
        DL 모델 미존재 또는 미보정 상태에서는 단일 추론으로 폴백.

        Args:
            candidates: 후보 목록
            frame: BGR 이미지

        Returns:
            (팀, 신뢰도) 튜플 목록 (입력 순서 유지)
        """
        if not self._initialized or self._config is None or not candidates:
            return [(Team.UNKNOWN, 0.0)] * len(candidates)

        # DL 임베딩 모델 미존재 → 단일 폴백
        with self._lock:
            dl_ready = (
                self._dl_model is not None
                and self._is_embed_model
            )

        if not dl_ready:
            return [self.classify(c, frame) for c in candidates]

        # 사전 centroid가 모두 있으면 aux 단계 스킵 (KMeans/HSV 불필요)
        has_preset_centroids = (
            getattr(self, "_preset_team_a_centroid", None) is not None
            and getattr(self, "_preset_team_b_centroid", None) is not None
            and getattr(self, "_preset_referee_centroid", None) is not None
        )

        with self._lock:
            try:
                import torch

                fh, fw = frame.shape[:2]
                mean = np.array(NORMALIZE_MEAN, dtype=np.float32)
                std = np.array(NORMALIZE_STD, dtype=np.float32)

                # 1) 모든 crop을 텐서로 스택
                tensors: list = []
                valid_indices: list[int] = []
                aux_results: list[tuple[Team, float]] = []

                for idx, cand in enumerate(candidates):
                    if cand.class_id != PLAYER_CLASS_ID_PLAYER:
                        aux_results.append((Team.UNKNOWN, 0.0))
                        continue

                    # 사전 centroid 사용 시 aux 계산 생략 (placeholder만 넣음)
                    if has_preset_centroids:
                        aux_results.append((Team.UNKNOWN, 0.0))
                    else:
                        roi = self._extract_uniform_roi(cand, frame)
                        if not roi.is_valid:
                            aux_results.append((Team.UNKNOWN, 0.0))
                            continue
                        if self._calibration_done:
                            aux_team, aux_conf = self._classify_by_cluster(roi)
                        else:
                            aux_team, aux_conf = self._classify_by_brightness(roi)
                        aux_results.append((aux_team, aux_conf))

                    # DL crop
                    x1 = max(0, int(cand.bbox_x))
                    y1 = max(0, int(cand.bbox_y))
                    x2 = min(fw, int(cand.bbox_x + cand.bbox_w))
                    y2 = min(fh, int(cand.bbox_y + cand.bbox_h))
                    if x2 - x1 < 10 or y2 - y1 < 20:
                        continue

                    roi_bgr = frame[y1:y2, x1:x2]
                    resized = cv2.resize(roi_bgr, _EMBED_INPUT_SIZE)
                    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                    normalized = (rgb - mean) / std
                    tensors.append(normalized.transpose(2, 0, 1))
                    valid_indices.append(idx)

                results: list[tuple[Team, float]] = list(aux_results)

                if not tensors:
                    return results

                # 2) 단일 배치 forward (캘리브레이션 전후 모두)
                batch = torch.from_numpy(np.stack(tensors, axis=0)).to(self._dl_device)
                with torch.no_grad():
                    embeddings = self._dl_model(batch).cpu().numpy()  # (N, 128)

                # 3a) 캘리브레이션 전: 임베딩 수집만, UNKNOWN 반환
                if self._embed_centroids is None:
                    for ti in range(embeddings.shape[0]):
                        self._embed_samples.append(embeddings[ti])
                    if len(self._embed_samples) >= 100:
                        self._calibrate_embed()
                    # results는 aux_results 그대로 사용 (이미 복사됨)
                    return results

                # 3b) 캘리브레이션 완료: 센트로이드 거리 계산
                for ti, idx in enumerate(valid_indices):
                    embedding = embeddings[ti]

                    if has_preset_centroids:
                        # cosine similarity 기반 (L2 정규화된 centroid)
                        sims = self._embed_centroids @ embedding  # (3,)
                        best_k = int(np.argmax(sims))
                        best_sim = float(sims[best_k])
                        # sim 범위 [-1, 1] → confidence [0, 1]
                        dl_conf = max(0.0, (best_sim + 1.0) / 2.0)
                        dl_team = self._embed_label_map.get(best_k, Team.UNKNOWN)
                        results[idx] = (dl_team, dl_conf)
                        if dl_conf >= self._config.confidence_threshold:
                            self._total_classified += 1
                        continue

                    # 레거시 KMeans 경로
                    dists = np.linalg.norm(
                        self._embed_centroids - embedding[np.newaxis, :], axis=1,
                    )
                    best_k = int(np.argmin(dists))
                    confidence = float(1.0 - dists[best_k] / (dists.max() + 1e-6))
                    dl_team = self._embed_label_map.get(best_k, Team.UNKNOWN)
                    dl_conf = max(0.0, confidence)

                    aux_team, aux_conf = aux_results[idx]
                    if dl_team != Team.UNKNOWN:
                        if aux_team == dl_team:
                            final_conf = _DL_WEIGHT * dl_conf + _KMEANS_WEIGHT * aux_conf
                        else:
                            final_conf = dl_conf * _DL_WEIGHT
                        results[idx] = (dl_team, min(1.0, final_conf))
                    else:
                        results[idx] = (aux_team, aux_conf)

                    if results[idx][1] >= self._config.confidence_threshold:
                        self._total_classified += 1

                return results

            except Exception as exc:
                logger.debug("배치 팀 분류 실패, 단일 폴백: %s", exc)
                return [self.classify(c, frame) for c in candidates]

    # =========================================================================
    # 내부 메서드 — DL 추론
    # =========================================================================

    def _dl_inference(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
    ) -> tuple[Team, float]:
        """
        팀 분류 모델 추론.

        임베딩 모델: crop → 128-dim → 센트로이드 거리 비교 → 팀 판정.
        기존 모델: crop → softmax → 직접 분류.
        """
        if self._dl_model is None or self._config is None:
            return Team.UNKNOWN, 0.0

        try:
            import torch

            fh, fw = frame.shape[:2]

            # 전체 bbox crop (임베딩 모델은 전체 선수 외형 사용)
            x1 = max(0, int(candidate.bbox_x))
            y1 = max(0, int(candidate.bbox_y))
            x2 = min(fw, int(candidate.bbox_x + candidate.bbox_w))
            y2 = min(fh, int(candidate.bbox_y + candidate.bbox_h))
            if x2 - x1 < 10 or y2 - y1 < 20:
                return Team.UNKNOWN, 0.0

            roi_bgr = frame[y1:y2, x1:x2]

            if self._is_embed_model:
                # 임베딩 모델: crop → 128-dim embedding
                resized = cv2.resize(roi_bgr, _EMBED_INPUT_SIZE)
                rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                mean = np.array(NORMALIZE_MEAN, dtype=np.float32)
                std = np.array(NORMALIZE_STD, dtype=np.float32)
                normalized = (rgb - mean) / std
                input_tensor = torch.from_numpy(
                    normalized.transpose(2, 0, 1)[np.newaxis, ...],
                ).to(self._dl_device)

                with torch.no_grad():
                    embedding = self._dl_model(input_tensor).cpu().numpy()[0]

                # 캘리브레이션 전: 임베딩 수집만
                if self._embed_centroids is None:
                    self._embed_samples.append(embedding)
                    # 30개 이상 모이면 자동 캘리브레이션
                    if len(self._embed_samples) >= 100:
                        self._calibrate_embed()
                    return Team.UNKNOWN, 0.0

                # 캘리브레이션 완료: 센트로이드 거리 비교
                dists = np.linalg.norm(
                    self._embed_centroids - embedding[np.newaxis, :], axis=1,
                )
                best_k = int(np.argmin(dists))
                # confidence: 1 - (최소거리 / 최대거리)
                confidence = float(1.0 - dists[best_k] / (dists.max() + 1e-6))
                team = self._embed_label_map.get(best_k, Team.UNKNOWN)
                return team, max(0.0, confidence)

            else:
                # 기존 직접 분류 모델
                import torch.nn.functional as F
                resized = cv2.resize(roi_bgr, _TEAM_DL_INPUT_SIZE)
                rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                mean = np.array(NORMALIZE_MEAN, dtype=np.float32)
                std = np.array(NORMALIZE_STD, dtype=np.float32)
                normalized = (rgb - mean) / std
                input_tensor = torch.from_numpy(
                    normalized.transpose(2, 0, 1)[np.newaxis, ...],
                ).to(self._dl_device)

                with torch.no_grad():
                    logits = self._dl_model(input_tensor)
                probs = F.softmax(logits, dim=1).cpu().numpy()[0]
                cls_idx = int(np.argmax(probs))
                confidence = float(probs[cls_idx])

                if cls_idx == _TEAM_DL_CLASS_A:
                    return Team.TEAM_A, confidence
                elif cls_idx == _TEAM_DL_CLASS_B:
                    return Team.TEAM_B, confidence
                return Team.UNKNOWN, confidence

        except Exception as exc:
            logger.debug("팀 분류 추론 실패: %s", exc)
            return Team.UNKNOWN, 0.0

    # =========================================================================
    # 멀티뷰 투표 분류
    # =========================================================================

    def classify_multi_view(
        self,
        candidate_views: dict[str, tuple[_PlayerCandidate, NDArray[np.uint8]]],
    ) -> tuple[Team, float]:
        """
        멀티뷰 투표 기반 팀 분류.

        동일 인물의 여러 카메라 뷰에서 독립 분류 후 다수결 투표.

        Args:
            candidate_views: 카메라 ID → (후보, BGR 프레임) 매핑

        Returns:
            (팀, 평균 신뢰도) 튜플
        """
        if not self._initialized or not candidate_views:
            return Team.UNKNOWN, 0.0

        votes: dict[Team, list[float]] = defaultdict(list)

        for cam_id, (candidate, frame) in candidate_views.items():
            team, conf = self.classify(candidate, frame)
            if team != Team.UNKNOWN:
                votes[team].append(conf)

        if not votes:
            return Team.UNKNOWN, 0.0

        # 다수결 + 평균 신뢰도
        best_team = Team.UNKNOWN
        best_count = 0
        best_avg_conf = 0.0
        total_votes = sum(len(v) for v in votes.values())

        for team, confs in votes.items():
            count = len(confs)
            avg_conf = sum(confs) / count

            if count > best_count or (count == best_count and avg_conf > best_avg_conf):
                best_team = team
                best_count = count
                best_avg_conf = avg_conf

        # 최소 일치 비율 검증
        if total_votes > 0:
            agreement = best_count / total_votes
            if agreement < _MULTI_VIEW_AGREEMENT_RATIO:
                return Team.UNKNOWN, best_avg_conf * agreement

        return best_team, best_avg_conf

    # =========================================================================
    # 내부 메서드 — ROI 추출
    # =========================================================================

    def _extract_uniform_roi(
        self,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
    ) -> _UniformROI:
        """
        가슴 영역 ROI 추출 + HSV 분석.

        bbox 내 설정된 비율 영역을 크롭하고, 피부색을 마스킹 제외한 후
        주색상을 HSV 히스토그램으로 추출합니다.

        Args:
            candidate: 선수 후보
            frame: BGR 이미지

        Returns:
            _UniformROI (유효하지 않으면 is_valid=False)
        """
        if self._config is None:
            return _UniformROI()

        config = self._config
        fh, fw = frame.shape[:2]

        # bbox 절대 좌표 → 가슴 ROI 절대 좌표
        roi_y1 = int(candidate.bbox_y + candidate.bbox_h * config.chest_y_start)
        roi_y2 = int(candidate.bbox_y + candidate.bbox_h * config.chest_y_end)
        roi_x1 = int(candidate.bbox_x + candidate.bbox_w * config.chest_x_start)
        roi_x2 = int(candidate.bbox_x + candidate.bbox_w * config.chest_x_end)

        # 프레임 경계 클리핑
        roi_x1 = max(0, min(roi_x1, fw - 1))
        roi_x2 = max(roi_x1 + 1, min(roi_x2, fw))
        roi_y1 = max(0, min(roi_y1, fh - 1))
        roi_y2 = max(roi_y1 + 1, min(roi_y2, fh))

        roi_bgr = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        pixel_count = roi_bgr.shape[0] * roi_bgr.shape[1]

        if pixel_count < config.min_roi_pixels:
            return _UniformROI(roi_pixel_count=pixel_count)

        # BGR → HSV
        roi_hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)

        # 피부색 마스크 생성 (제거할 영역)
        skin_mask = cv2.inRange(
            roi_hsv,
            np.array([_SKIN_HUE_LOW, _SKIN_SAT_LOW, _SKIN_VAL_LOW], dtype=np.uint8),
            np.array([_SKIN_HUE_HIGH, _SKIN_SAT_HIGH, _SKIN_VAL_HIGH], dtype=np.uint8),
        )
        skin_pixel_count = int(np.count_nonzero(skin_mask))
        skin_ratio = skin_pixel_count / max(1, pixel_count)

        # 유니폼 마스크 (피부색 반전)
        uniform_mask = cv2.bitwise_not(skin_mask)
        uniform_pixel_count = int(np.count_nonzero(uniform_mask))

        if uniform_pixel_count < config.min_roi_pixels:
            return _UniformROI(
                roi_pixel_count=pixel_count,
                skin_ratio=skin_ratio,
            )

        # 유니폼 영역만 추출
        uniform_pixels = roi_hsv[uniform_mask > 0]

        # 주색상 추출 (중앙값 기반 — 히스토그램 피크보다 강건)
        h_values = uniform_pixels[:, 0].astype(np.float64)
        s_values = uniform_pixels[:, 1].astype(np.float64)
        v_values = uniform_pixels[:, 2].astype(np.float64)

        dominant_hue = float(np.median(h_values))
        dominant_sat = float(np.median(s_values))
        dominant_val = float(np.median(v_values))

        hue_std = float(np.std(h_values))
        sat_mean = float(np.mean(s_values))
        val_mean = float(np.mean(v_values))

        return _UniformROI(
            dominant_hue=dominant_hue,
            dominant_saturation=dominant_sat,
            dominant_value=dominant_val,
            hue_std=hue_std,
            saturation_mean=sat_mean,
            value_mean=val_mean,
            skin_ratio=skin_ratio,
            roi_pixel_count=pixel_count,
            is_valid=True,
        )

    # =========================================================================
    # 내부 메서드 — 클러스터 기반 분류
    # =========================================================================

    def _classify_by_cluster(
        self,
        roi: _UniformROI,
    ) -> tuple[Team, float]:
        """
        클러스터 중심 거리 기반 팀 분류.

        HSV 색상 벡터와 두 클러스터 중심 간 유클리드 거리를 비교합니다.

        Args:
            roi: 유니폼 ROI 분석 결과

        Returns:
            (팀, 신뢰도) 튜플
        """
        if self._cluster_centers is None or not self._cluster_team_map:
            return Team.UNKNOWN, 0.0

        hsv = np.array(
            [roi.dominant_hue, roi.dominant_saturation, roi.dominant_value],
            dtype=np.float64,
        )

        dist_0 = float(np.linalg.norm(hsv - self._cluster_centers[0]))
        dist_1 = float(np.linalg.norm(hsv - self._cluster_centers[1]))

        # 두 거리 합 기준 신뢰도 산출
        total_dist = dist_0 + dist_1
        if total_dist < 1e-9:
            # 두 클러스터가 동일 위치 → 분류 불가
            return Team.UNKNOWN, 0.0

        if dist_0 <= dist_1:
            cluster_idx = 0
            confidence = 1.0 - (dist_0 / total_dist)
        else:
            cluster_idx = 1
            confidence = 1.0 - (dist_1 / total_dist)

        # 최소 거리가 임계값 초과 → 어느 팀에도 속하지 않음
        min_dist = min(dist_0, dist_1)
        if min_dist > _COLOR_DISTANCE_THRESHOLD:
            confidence *= 0.5  # 신뢰도 감쇄

        team = self._cluster_team_map.get(cluster_idx, Team.UNKNOWN)

        # Hue 표준편차가 크면 신뢰도 감쇄 (유니폼 색상 불균일)
        if roi.hue_std > 30.0:
            confidence *= 0.8

        return team, min(1.0, confidence)

    # =========================================================================
    # 내부 메서드 — 밝기 기반 폴백 분류
    # =========================================================================

    def _classify_by_brightness(
        self,
        roi: _UniformROI,
    ) -> tuple[Team, float]:
        """
        V(밝기) 기반 간이 분류 (캘리브레이션 미완료 시 폴백).

        어두운 유니폼 → TEAM_A(홈), 밝은 유니폼 → TEAM_B(원정).

        Args:
            roi: 유니폼 ROI 분석 결과

        Returns:
            (팀, 신뢰도) 튜플
        """
        v = roi.dominant_value

        if v < TEAM_VALUE_DARK_THRESHOLD:
            # 확실히 어두운 유니폼
            confidence = min(1.0, (TEAM_VALUE_DARK_THRESHOLD - v) / TEAM_VALUE_DARK_THRESHOLD)
            return Team.TEAM_A, max(0.5, confidence)

        if v > TEAM_VALUE_LIGHT_THRESHOLD:
            # 확실히 밝은 유니폼
            confidence = min(1.0, (v - TEAM_VALUE_LIGHT_THRESHOLD) / (255.0 - TEAM_VALUE_LIGHT_THRESHOLD))
            return Team.TEAM_B, max(0.5, confidence)

        # 중간 영역 → 분류 불확실
        return Team.UNKNOWN, 0.3

    # =========================================================================
    # 트랙 기반 팀 분류 (투표 + 잠금)
    # =========================================================================

    def classify_with_lock(
        self,
        track_id: int,
        candidate: _PlayerCandidate,
        frame: NDArray[np.uint8],
    ) -> tuple[Team, float]:
        """
        트랙 ID 기반 팀 분류 — 투표 + 잠금 + 겹침 보호.

        - 5회 연속 동일 팀 → 잠금 (영구 확정)
        - 잠금 후 재분류 안 함 (겹침 시 ID 스왑 방지)
        - 투표 시 다수결 방향과 반대 투표는 무시 (일관성 보호)

        Args:
            track_id: 추적 트랙 ID
            candidate: 선수 후보
            frame: BGR 이미지

        Returns:
            (팀, 신뢰도) 튜플
        """
        # 이미 잠금된 트랙이면 즉시 반환 (겹침 무관)
        locked = self._track_locked.get(track_id)
        if locked is not None:
            return locked, 1.0

        # 일반 분류 수행
        team, conf = self.classify(candidate, frame)

        if team == Team.UNKNOWN:
            return team, conf

        # 투표 누적
        team_name = team.value
        if track_id not in self._track_votes:
            self._track_votes[track_id] = {"team_a": 0, "team_b": 0}
        votes = self._track_votes[track_id]

        # 일관성 보호: 기존 다수 팀과 반대 투표가 들어오면 무시
        # (겹침으로 인한 잘못된 분류 방지)
        total_votes = votes["team_a"] + votes["team_b"]
        if total_votes >= 3:
            majority = "team_a" if votes["team_a"] > votes["team_b"] else "team_b"
            if team_name != majority:
                # 다수 방향과 반대 → 무시하고 다수 팀 반환
                majority_team = Team.TEAM_A if majority == "team_a" else Team.TEAM_B
                return majority_team, 0.8

        if team_name in votes:
            votes[team_name] += 1

        # 잠금 검사 (5회 이상 동일 — 3→5 강화)
        for tn, count in votes.items():
            if count >= 5:
                locked_team = Team.TEAM_A if tn == "team_a" else Team.TEAM_B
                self._track_locked[track_id] = locked_team
                logger.debug(
                    "팀 잠금: track_id=%d → %s (투표: %s)",
                    track_id, tn, votes,
                )
                return locked_team, 1.0

        # 아직 미잠금 → 현재 다수 팀 반환
        if votes["team_a"] > votes["team_b"]:
            return Team.TEAM_A, conf
        elif votes["team_b"] > votes["team_a"]:
            return Team.TEAM_B, conf

        return team, conf

    def clear_track(self, track_id: int) -> None:
        """트랙 삭제 시 투표/잠금 데이터 정리."""
        self._track_votes.pop(track_id, None)
        self._track_locked.pop(track_id, None)

    # =========================================================================
    # 수동 캘리브레이션
    # =========================================================================

    def set_team_colors(
        self,
        team_a_hsv: tuple[float, float, float],
        team_b_hsv: tuple[float, float, float],
    ) -> None:
        """
        수동으로 팀 색상 설정 (사용자 지정 또는 API 입력).

        Args:
            team_a_hsv: 팀 A(홈) 주색상 (H, S, V)
            team_b_hsv: 팀 B(원정) 주색상 (H, S, V)
        """
        with self._lock:
            self._cluster_centers = np.array(
                [list(team_a_hsv), list(team_b_hsv)],
                dtype=np.float64,
            )
            self._cluster_team_map = {0: Team.TEAM_A, 1: Team.TEAM_B}
            self._calibration_done = True
            self._color_samples.clear()
            logger.info(
                "TeamClassifier 수동 색상 설정: A=%s, B=%s",
                team_a_hsv,
                team_b_hsv,
            )

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def __repr__(self) -> str:
        cal_status = "calibrated" if self._calibration_done else "uncalibrated"
        dl_status = "DL" if self._dl_model is not None else "K-Means"
        return (
            f"TeamClassifier({dl_status}+{cal_status}, "
            f"classified={self._total_classified}, "
            f"skipped={self._total_skipped})"
        )


# =============================================================================
# 모듈 export 및 버전
# =============================================================================

__all__: list[str] = [
    "TeamClassifier",
    "TeamClassifierConfig",
]

__version__: str = "1.0.0"

__version__: str = "1.0.0"
