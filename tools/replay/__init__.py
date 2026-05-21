# -*- coding: utf-8 -*-
"""COURTVIEW Replay Analyzer — 녹화된 mp4/ts 영상으로부터 기록지/전력분석/하이라이트 추출.

T 형식: <sess>/cam<n>_Q<n>.ts (COURTVIEW DESK 녹화 결과 그대로)
B 형식: <폴더>/L1(CAM3)/*_NNNNNN.MP4 + sync.json (3분 컷 + 카메라간 시간 offset)
"""
from __future__ import annotations

__all__ = ["format_detector", "multi_file_ingestion", "calibration_dialog", "replay_runner"]
