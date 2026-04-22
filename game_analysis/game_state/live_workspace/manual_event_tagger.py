# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: game_analysis/live_workspace
파일: manual_event_tagger.py
설명: 수동 이벤트 추가/태깅/오버라이드 API
      - Human-in-the-Loop: 기록원/코치가 직접 이벤트 생성
      - AI 감지 이벤트에 태그(메모/라벨) 부착
      - AI 감지 이벤트 수동 오버라이드 (유형/선수/점수 수정)
      - 수동 이벤트 이력 관리

      Processing Cadence: 🟠 EVENT (<10ms)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-03-24
버전: 1.0.0

참조: shared/dto/game_dto.py (GameEvent), shared/constants/game_rule_constants.py
의존성: Phase 1B (event_detection 출력 — GameEvent DTO)
소비자: correction_sync.py, live_event_validator.py, Phase 2 statistics
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from shared.constants.game_rule_constants import GameEventType
from shared.dto.game_dto import GameEvent

logger: Final = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
_MAX_TAGS_PER_EVENT: Final[int] = 10
_MAX_MANUAL_EVENTS: Final[int] = 500
_MAX_TAG_LENGTH: Final[int] = 100
_MAX_OVERRIDE_HISTORY: Final[int] = 1000
_MANUAL_CONFIDENCE: Final[float] = 1.0  # 수동 이벤트 기본 신뢰도


# =============================================================================
# Enum
# =============================================================================
@unique
class TagCategory(Enum):
    """태그 카테고리."""
    CORRECTION = "correction"         # AI 오류 수정
    HIGHLIGHT = "highlight"           # 하이라이트 마킹
    COACHING_NOTE = "coaching_note"   # 코칭 메모
    REVIEW_FLAG = "review_flag"       # 리뷰 필요 플래그
    CUSTOM = "custom"                 # 사용자 정의

    @property
    def display_name_ko(self) -> str:
        """한글 표시명."""
        names = {
            "correction": "수정",
            "highlight": "하이라이트",
            "coaching_note": "코칭 메모",
            "review_flag": "리뷰 필요",
            "custom": "사용자 정의",
        }
        return names.get(self.value, self.value)


@unique
class OverrideField(Enum):
    """오버라이드 가능 필드."""
    EVENT_TYPE = "event_type"
    PRIMARY_PLAYER = "primary_player_id"
    SECONDARY_PLAYER = "secondary_player_id"
    TEAM_ID = "team_id"
    POINTS = "points"
    QUARTER = "quarter"
    GAME_CLOCK = "game_clock"
    DESCRIPTION = "description"


# =============================================================================
# 설정 클래스
# =============================================================================
@dataclass(slots=True)
class ManualEventTaggerConfig:
    """
    ManualEventTagger 설정.

    수동 이벤트/태그 관리 정책을 정의합니다.
    """

    max_tags_per_event: int = _MAX_TAGS_PER_EVENT
    max_manual_events: int = _MAX_MANUAL_EVENTS
    max_tag_length: int = _MAX_TAG_LENGTH
    max_override_history: int = _MAX_OVERRIDE_HISTORY
    manual_confidence: float = _MANUAL_CONFIDENCE

    @classmethod
    def from_yaml(cls, cfg: dict) -> ManualEventTaggerConfig:
        """YAML 설정에서 생성."""
        return cls(
            max_tags_per_event=cfg.get("max_tags_per_event", _MAX_TAGS_PER_EVENT),
            max_manual_events=cfg.get("max_manual_events", _MAX_MANUAL_EVENTS),
            max_tag_length=cfg.get("max_tag_length", _MAX_TAG_LENGTH),
            max_override_history=cfg.get(
                "max_override_history", _MAX_OVERRIDE_HISTORY,
            ),
            manual_confidence=cfg.get("manual_confidence", _MANUAL_CONFIDENCE),
        )


# =============================================================================
# 출력 DTO
# =============================================================================
@dataclass(slots=True)
class EventTag:
    """
    이벤트 태그.

    이벤트에 부착된 개별 태그 정보입니다.
    """

    tag_id: UUID
    event_id: UUID
    category: TagCategory
    label: str
    reason: str = ""
    tagger_id: str = ""
    created_at: float = 0.0  # timestamp (초)


@dataclass(slots=True)
class TagResult:
    """태그 작업 결과."""
    success: bool
    tag: EventTag | None = None
    message: str = ""


@dataclass(slots=True)
class OverrideRecord:
    """
    이벤트 오버라이드 기록.

    필드 수정 이력을 추적합니다.
    """

    override_id: UUID
    event_id: UUID
    field: OverrideField
    old_value: str
    new_value: str
    reason: str = ""
    overrider_id: str = ""
    created_at: float = 0.0


# =============================================================================
# ManualEventTagger
# =============================================================================
class ManualEventTagger:
    """
    수동 이벤트 태거.

    기록원/코치가 직접 이벤트를 생성하거나,
    AI 감지 이벤트에 태그를 부착하거나,
    이벤트 필드를 수동으로 수정할 수 있습니다.
    """

    def __init__(
        self,
        config: ManualEventTaggerConfig | None = None,
    ) -> None:
        self._config = config or ManualEventTaggerConfig()
        self._lock = RLock()

        # 수동 생성 이벤트 (event_id → GameEvent)
        self._manual_events: dict[UUID, GameEvent] = {}
        # 이벤트별 태그 (event_id → list[EventTag])
        self._tags: dict[UUID, list[EventTag]] = {}
        # 오버라이드 이력
        self._override_history: list[OverrideRecord] = []

    # === 속성 ===

    @property
    def name(self) -> str:
        return "ManualEventTagger"

    @property
    def manual_event_count(self) -> int:
        with self._lock:
            return len(self._manual_events)

    # === 수동 이벤트 생성 ===

    def create_event(
        self,
        event_type: GameEventType,
        frame_number: int,
        timestamp: float,
        *,
        primary_player_id: int | None = None,
        team_id: str | None = None,
        quarter: int | None = None,
        game_clock: str | None = None,
        points: int = 0,
        description: str | None = None,
        tagger_id: str = "",
    ) -> GameEvent:
        """
        수동 이벤트 생성.

        기록원/코치가 AI가 놓친 이벤트를 직접 생성합니다.

        Args:
            event_type: 이벤트 유형
            frame_number: 프레임 번호
            timestamp: 영상 내 시간 (초)
            primary_player_id: 주 선수 트래킹 ID
            team_id: 팀 ID
            quarter: 쿼터
            game_clock: 게임 시계 (MM:SS)
            points: 획득 점수
            description: 이벤트 설명
            tagger_id: 태거 ID (기록원 식별)

        Returns:
            생성된 GameEvent
        """
        event = GameEvent(
            event_id=uuid4(),
            event_type=event_type,
            frame_number=frame_number,
            timestamp=timestamp,
            primary_player_id=primary_player_id,
            team_id=team_id,
            quarter=quarter,
            game_clock=game_clock,
            points=points,
            description=description or f"수동 생성: {event_type.value}",
            confidence=self._config.manual_confidence,
        )

        with self._lock:
            # 메모리 가드
            if len(self._manual_events) >= self._config.max_manual_events:
                # 가장 오래된 이벤트 제거 (FIFO)
                oldest_id = next(iter(self._manual_events))
                del self._manual_events[oldest_id]
                self._tags.pop(oldest_id, None)
                logger.debug(
                    "수동 이벤트 메모리 가드: 가장 오래된 이벤트 제거 (id=%s)",
                    oldest_id,
                )

            self._manual_events[event.event_id] = event

            # 태거 식별 태그 자동 부착
            if tagger_id:
                self._tags.setdefault(event.event_id, []).append(
                    EventTag(
                        tag_id=uuid4(),
                        event_id=event.event_id,
                        category=TagCategory.CUSTOM,
                        label=f"created_by:{tagger_id}",
                        reason="수동 이벤트 생성자 기록",
                        tagger_id=tagger_id,
                        created_at=time.time(),
                    ),
                )

        logger.info(
            "수동 이벤트 생성: type=%s, frame=%d, player=%s",
            event_type.value, frame_number, primary_player_id,
        )
        return event

    # === 태그 관리 ===

    def add_tag(
        self,
        event_id: UUID,
        category: TagCategory,
        label: str,
        *,
        reason: str = "",
        tagger_id: str = "",
    ) -> TagResult:
        """
        이벤트에 태그 부착.

        AI 감지 이벤트 또는 수동 이벤트에 태그를 추가합니다.

        Args:
            event_id: 대상 이벤트 ID
            category: 태그 카테고리
            label: 태그 라벨
            reason: 태그 부착 사유
            tagger_id: 태거 ID

        Returns:
            TagResult — 작업 결과
        """
        # 라벨 길이 검증
        if len(label) > self._config.max_tag_length:
            return TagResult(
                success=False,
                message=f"태그 라벨 길이 초과: {len(label)} > {self._config.max_tag_length}",
            )

        if not label.strip():
            return TagResult(
                success=False,
                message="태그 라벨이 비어있습니다",
            )

        with self._lock:
            tags = self._tags.setdefault(event_id, [])

            # 태그 수 제한
            if len(tags) >= self._config.max_tags_per_event:
                return TagResult(
                    success=False,
                    message=(
                        f"이벤트당 최대 태그 수 초과: "
                        f"{len(tags)} >= {self._config.max_tags_per_event}"
                    ),
                )

            tag = EventTag(
                tag_id=uuid4(),
                event_id=event_id,
                category=category,
                label=label.strip(),
                reason=reason,
                tagger_id=tagger_id,
                created_at=time.time(),
            )
            tags.append(tag)

        return TagResult(success=True, tag=tag, message="태그 추가 완료")

    def remove_tag(self, event_id: UUID, tag_id: UUID) -> bool:
        """
        태그 제거.

        Args:
            event_id: 이벤트 ID
            tag_id: 태그 ID

        Returns:
            성공 여부
        """
        with self._lock:
            tags = self._tags.get(event_id)
            if tags is None:
                return False

            for i, tag in enumerate(tags):
                if tag.tag_id == tag_id:
                    del tags[i]
                    return True

        return False

    def get_tags(self, event_id: UUID) -> list[EventTag]:
        """이벤트의 태그 목록 반환 (방어적 복사)."""
        with self._lock:
            return list(self._tags.get(event_id, []))

    def get_tagged_events(
        self,
        category: TagCategory | None = None,
    ) -> list[UUID]:
        """
        태그가 부착된 이벤트 ID 목록 반환.

        Args:
            category: 필터링할 카테고리 (None=전체)

        Returns:
            이벤트 ID 리스트
        """
        with self._lock:
            if category is None:
                return [eid for eid, tags in self._tags.items() if tags]

            return [
                eid
                for eid, tags in self._tags.items()
                if any(t.category == category for t in tags)
            ]

    # === 오버라이드 ===

    def override_event(
        self,
        event: GameEvent,
        field_name: OverrideField,
        new_value: str,
        *,
        reason: str = "",
        overrider_id: str = "",
    ) -> GameEvent:
        """
        이벤트 필드 수동 오버라이드.

        AI 감지 이벤트의 특정 필드를 수정하여 새 GameEvent를 반환합니다.
        원본 GameEvent는 불변이므로 수정된 복사본을 반환합니다.

        Args:
            event: 원본 이벤트
            field_name: 수정할 필드
            new_value: 새 값 (문자열)
            reason: 수정 사유
            overrider_id: 수정자 ID

        Returns:
            수정된 GameEvent (새 인스턴스)
        """
        # 원본 값 추출
        old_value = self._get_field_value(event, field_name)

        # 수정된 이벤트 생성 (Pydantic model_copy 활용)
        update_dict = self._parse_override_value(field_name, new_value)
        corrected_event = event.model_copy(update=update_dict)

        # 오버라이드 기록
        record = OverrideRecord(
            override_id=uuid4(),
            event_id=event.event_id,
            field=field_name,
            old_value=str(old_value),
            new_value=new_value,
            reason=reason,
            overrider_id=overrider_id,
            created_at=time.time(),
        )

        with self._lock:
            self._override_history.append(record)
            # 메모리 가드
            if len(self._override_history) > self._config.max_override_history:
                trim = self._config.max_override_history // 5
                del self._override_history[:trim]

        logger.info(
            "이벤트 오버라이드: event_id=%s, field=%s, %s → %s",
            event.event_id, field_name.value, old_value, new_value,
        )
        return corrected_event

    # === 조회 ===

    def get_manual_events(self) -> list[GameEvent]:
        """수동 생성 이벤트 목록 반환 (방어적 복사)."""
        with self._lock:
            return list(self._manual_events.values())

    def get_override_history(
        self,
        event_id: UUID | None = None,
        max_count: int = 100,
    ) -> list[OverrideRecord]:
        """
        오버라이드 이력 조회.

        Args:
            event_id: 특정 이벤트 필터 (None=전체)
            max_count: 최대 반환 수

        Returns:
            OverrideRecord 리스트
        """
        with self._lock:
            if event_id is not None:
                filtered = [
                    r for r in self._override_history
                    if r.event_id == event_id
                ]
                return filtered[-max_count:]
            return list(self._override_history[-max_count:])

    def get_event_history(self) -> list[GameEvent]:
        """이벤트 이력 반환 (호환 인터페이스)."""
        return self.get_manual_events()

    def get_tagger_stats(self) -> dict[str, int]:
        """
        태거 통계 반환.

        Returns:
            manual_events, total_tags, total_overrides 포함 딕셔너리
        """
        with self._lock:
            total_tags = sum(len(tags) for tags in self._tags.values())
            return {
                "manual_events": len(self._manual_events),
                "total_tags": total_tags,
                "total_overrides": len(self._override_history),
                "tagged_events": sum(
                    1 for tags in self._tags.values() if tags
                ),
            }

    # === 리셋 ===

    def reset(self) -> None:
        """전체 상태 초기화."""
        with self._lock:
            self._manual_events.clear()
            self._tags.clear()
            self._override_history.clear()

    # === 내부 메서드 ===

    @staticmethod
    def _get_field_value(event: GameEvent, field_name: OverrideField) -> str:
        """이벤트에서 필드 값 추출."""
        field_map = {
            OverrideField.EVENT_TYPE: lambda e: e.event_type.value,
            OverrideField.PRIMARY_PLAYER: lambda e: str(e.primary_player_id),
            OverrideField.SECONDARY_PLAYER: lambda e: str(e.secondary_player_id),
            OverrideField.TEAM_ID: lambda e: str(e.team_id),
            OverrideField.POINTS: lambda e: str(e.points),
            OverrideField.QUARTER: lambda e: str(e.quarter),
            OverrideField.GAME_CLOCK: lambda e: str(e.game_clock),
            OverrideField.DESCRIPTION: lambda e: str(e.description),
        }
        extractor = field_map.get(field_name)
        if extractor is None:
            return ""
        return extractor(event)

    @staticmethod
    def _parse_override_value(
        field_name: OverrideField,
        value: str,
    ) -> dict:
        """오버라이드 값을 Pydantic update dict로 변환."""
        if field_name == OverrideField.EVENT_TYPE:
            return {"event_type": GameEventType(value)}
        if field_name == OverrideField.PRIMARY_PLAYER:
            return {"primary_player_id": int(value) if value != "None" else None}
        if field_name == OverrideField.SECONDARY_PLAYER:
            return {"secondary_player_id": int(value) if value != "None" else None}
        if field_name == OverrideField.TEAM_ID:
            return {"team_id": value if value != "None" else None}
        if field_name == OverrideField.POINTS:
            return {"points": int(value)}
        if field_name == OverrideField.QUARTER:
            return {"quarter": int(value) if value != "None" else None}
        if field_name == OverrideField.GAME_CLOCK:
            return {"game_clock": value if value != "None" else None}
        if field_name == OverrideField.DESCRIPTION:
            return {"description": value if value != "None" else None}
        return {}


# =============================================================================
# Export
# =============================================================================
__all__ = [
    "ManualEventTagger",
    "ManualEventTaggerConfig",
    "EventTag",
    "TagResult",
    "TagCategory",
    "OverrideField",
    "OverrideRecord",
]

__version__ = "1.0.0"
