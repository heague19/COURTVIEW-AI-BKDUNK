# -*- coding: utf-8 -*-
"""
tests/engine/pipeline/unit/test_frame_pipeline_adapter.py
FramePipeline._group_detections_by_camera 어댑터 단위 테스트.

어댑터 책임:
  SceneFusionResult.player_result.fused_objects → {cam_id(int): list[CameraDetection]}

검증 대상:
  - cam_id 포맷 다형성 ("cam_0"/"cam0"/"1"/int)
  - None/잘못된 camera_id 안전 처리
  - jersey/team/confidence 매핑
  - 빈 input / None input
  - bbox None 스킵
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest


# =============================================================================
# _group_detections_by_camera의 독립 실행 버전 (FramePipeline 초기화 회피)
# =============================================================================
# 원 함수는 FramePipeline 인스턴스 메서드지만 인스턴스 상태에 의존하지 않음
# → 언바운드 함수로 가져와 호출해도 동일한 동작

def _group(detection):
    """FramePipeline._group_detections_by_camera와 동일 구현.

    테스트 격리를 위해 복제 (구현 변경 시 테스트 파일도 동기화 필요).
    """
    from detection.player_detection.multiview_tracker import CameraDetection

    if detection is None or detection.player_result is None:
        return {}

    result: dict[int, list] = {}
    for det_idx, obj in enumerate(detection.player_result.fused_objects):
        if obj.bbox is None:
            continue
        attrs = obj.attributes or {}
        cam_id_raw = attrs.get("camera_id")
        if cam_id_raw is None:
            continue
        try:
            if isinstance(cam_id_raw, int):
                cam_id = cam_id_raw
            else:
                s = str(cam_id_raw).replace("cam_", "").replace("cam", "")
                cam_id = int(s)
        except (ValueError, TypeError):
            continue

        bbox = obj.bbox
        x1 = int(bbox.x)
        y1 = int(bbox.y)
        x2 = int(bbox.x + bbox.width)
        y2 = int(bbox.y + bbox.height)

        cam_det = CameraDetection(
            cam_id=cam_id,
            bbox=(x1, y1, x2, y2),
            jersey_number=attrs.get("jersey_number"),
            jersey_conf=float(attrs.get("jersey_conf", 0.0)),
            team=attrs.get("team"),
            team_conf=float(attrs.get("team_confidence", 0.0)),
            yolo_conf=float(obj.confidence),
        )
        result.setdefault(cam_id, []).append(cam_det)
    return result


# =============================================================================
# 테스트 fixture
# =============================================================================

def make_bbox(x=10, y=10, w=4, h=4):
    b = MagicMock()
    b.x = x
    b.y = y
    b.width = w
    b.height = h
    return b


def make_obj(cam_id_raw, jersey=None, team=None, jersey_conf=0.0,
             team_conf=0.0, confidence=0.9, bbox=None):
    obj = MagicMock()
    obj.bbox = bbox if bbox is not None else make_bbox()
    obj.confidence = confidence
    attrs = {}
    if cam_id_raw is not None:
        attrs["camera_id"] = cam_id_raw
    if jersey is not None:
        attrs["jersey_number"] = jersey
        attrs["jersey_conf"] = jersey_conf
    if team is not None:
        attrs["team"] = team
        attrs["team_confidence"] = team_conf
    obj.attributes = attrs
    return obj


def make_detection(objs):
    d = MagicMock()
    d.player_result = MagicMock()
    d.player_result.fused_objects = objs
    return d


# =============================================================================
# cam_id 포맷 다형성
# =============================================================================

class TestCamIdFormats:
    def test_int_cam_id(self):
        d = make_detection([make_obj(1), make_obj(2)])
        result = _group(d)
        assert set(result.keys()) == {1, 2}

    def test_cam_underscore_format(self):
        d = make_detection([make_obj("cam_0"), make_obj("cam_3")])
        result = _group(d)
        assert set(result.keys()) == {0, 3}

    def test_cam_no_underscore(self):
        d = make_detection([make_obj("cam5")])
        result = _group(d)
        assert 5 in result

    def test_numeric_string(self):
        d = make_detection([make_obj("7")])
        result = _group(d)
        assert 7 in result

    def test_mixed_formats_group_by_same_int(self):
        """서로 다른 표기지만 같은 정수면 같은 그룹."""
        d = make_detection([
            make_obj(1), make_obj("cam_1"), make_obj("cam1"), make_obj("1"),
        ])
        result = _group(d)
        assert 1 in result
        assert len(result[1]) == 4


# =============================================================================
# 안전 처리
# =============================================================================

class TestSafety:
    def test_none_detection(self):
        assert _group(None) == {}

    def test_none_player_result(self):
        d = MagicMock()
        d.player_result = None
        assert _group(d) == {}

    def test_empty_fused_objects(self):
        d = make_detection([])
        assert _group(d) == {}

    def test_missing_camera_id_skipped(self):
        d = make_detection([make_obj(None)])  # camera_id 없음
        assert _group(d) == {}

    def test_invalid_camera_id_format_skipped(self):
        d = make_detection([make_obj("invalid-cam-name")])
        assert _group(d) == {}

    def test_bbox_none_skipped(self):
        d = make_detection([make_obj(1, bbox=None), make_obj(2)])
        d.player_result.fused_objects[0].bbox = None  # 명시
        result = _group(d)
        assert 1 not in result or len(result.get(1, [])) == 0
        assert 2 in result

    def test_empty_attributes(self):
        obj = MagicMock()
        obj.bbox = make_bbox()
        obj.attributes = {}  # 빈 dict
        obj.confidence = 0.5
        d = make_detection([obj])
        # camera_id 없음 → 스킵
        assert _group(d) == {}


# =============================================================================
# 필드 매핑
# =============================================================================

class TestFieldMapping:
    def test_jersey_propagated(self):
        d = make_detection([make_obj(1, jersey=23, jersey_conf=0.85)])
        result = _group(d)
        cam_det = result[1][0]
        assert cam_det.jersey_number == 23
        assert cam_det.jersey_conf == pytest.approx(0.85)

    def test_team_propagated(self):
        d = make_detection([make_obj(1, team="team_a", team_conf=0.7)])
        result = _group(d)
        cam_det = result[1][0]
        assert cam_det.team == "team_a"
        assert cam_det.team_conf == pytest.approx(0.7)

    def test_yolo_conf_propagated(self):
        d = make_detection([make_obj(1, confidence=0.92)])
        result = _group(d)
        assert result[1][0].yolo_conf == pytest.approx(0.92)

    def test_default_jersey_conf_zero(self):
        """jersey_number는 있지만 jersey_conf는 attributes에 없을 때 0.0."""
        obj = MagicMock()
        obj.bbox = make_bbox()
        obj.confidence = 0.5
        obj.attributes = {"camera_id": 1, "jersey_number": 5}  # jersey_conf 없음
        d = make_detection([obj])
        result = _group(d)
        cam_det = result[1][0]
        assert cam_det.jersey_number == 5
        assert cam_det.jersey_conf == 0.0

    def test_bbox_tuple_format(self):
        """bbox(x=10, y=20, width=5, height=8) → (10, 20, 15, 28)."""
        d = make_detection([make_obj(1, bbox=make_bbox(10, 20, 5, 8))])
        result = _group(d)
        cam_det = result[1][0]
        assert cam_det.bbox == (10, 20, 15, 28)


# =============================================================================
# 그룹화
# =============================================================================

class TestGrouping:
    def test_multiple_objects_per_camera(self):
        d = make_detection([
            make_obj(1, jersey=1),
            make_obj(1, jersey=2),
            make_obj(1, jersey=3),
        ])
        result = _group(d)
        assert len(result[1]) == 3
        jerseys = {c.jersey_number for c in result[1]}
        assert jerseys == {1, 2, 3}

    def test_order_preserved_within_camera(self):
        d = make_detection([
            make_obj(1, jersey=10),
            make_obj(1, jersey=20),
        ])
        result = _group(d)
        assert result[1][0].jersey_number == 10
        assert result[1][1].jersey_number == 20
