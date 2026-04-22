# -*- coding: utf-8 -*-
"""
COURTVIEW - 런처 TensorRT 워밍업

첫 실행 시 또는 GPU/TRT 버전 변경 시 weights/*.onnx 를 순회하며
TensorRTEngine.build_or_load() 호출로 engine 캐시를 사전 빌드한다.

- 결과 engine 파일은 %APPDATA%\\COURTVIEW\\tensorrt_cache\\ 에 저장됨
- 진행률은 콜백(on_progress)으로 스플래시 UI 에 전달

설계 원칙:
- import torch/tensorrt 는 늦게 — 워밍업 시점까지 스플래시 빠르게 뜨도록
- 실패해도 스킵 가능 (경고만 찍고 서버 기동 허용 — CPU 대체 경로가 있을 수 있음)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-04-21
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

_logger = logging.getLogger("launcher.warmup")


@dataclass
class WarmupResult:
    """워밍업 요약."""
    total: int = 0
    built: int = 0
    cached: int = 0
    failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)  # (model, error)
    elapsed_sec: float = 0.0


ProgressFn = Callable[[int, int, str, str], None]
"""
on_progress(current_index, total, model_name, status)
  status: 'start' | 'cached' | 'building' | 'done' | 'error'
"""


def _discover_onnx_models(weights_dir: Path) -> list[Path]:
    """weights 폴더에서 TensorRT 대상 .onnx 선별.

    Skip:
      - 테스트/데모 onnx (파일명에 'test', 'sample', 'demo')
      - 크기 1MB 이하 (왜곡된 파일)
    """
    if not weights_dir.exists():
        return []

    candidates: list[Path] = []
    for p in weights_dir.glob("*.onnx"):
        name_lower = p.name.lower()
        if any(x in name_lower for x in ("test", "sample", "demo")):
            continue
        try:
            if p.stat().st_size < 1_000_000:  # 1MB
                continue
        except OSError:
            continue
        candidates.append(p)

    # 경량 모델 먼저 — 사용자가 빠른 피드백 느끼게
    candidates.sort(key=lambda x: x.stat().st_size)
    return candidates


def _onnx_sha256(onnx_path: Path) -> str:
    """ONNX 파일의 SHA-256 해시 (TensorRTEngine 내부 로직과 동일)."""
    import hashlib
    h = hashlib.sha256()
    with open(onnx_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_cache_hit(onnx_path: Path, cache_dir: Path) -> bool:
    """
    tensorrt_cache 폴더에 현재 ONNX 해시와 매칭되는 manifest 가 있으면 캐시 hit.

    GPU·TRT 버전 일치 여부는 TensorRTEngine.build_or_load() 가 재검증하므로
    여기서는 해시만 간단히 체크.
    """
    import json
    if not cache_dir.exists():
        return False
    try:
        target_hash = _onnx_sha256(onnx_path)
    except Exception:
        return False
    for mani in cache_dir.glob("*.manifest.json"):
        try:
            m = json.loads(mani.read_text(encoding="utf-8"))
            if m.get("onnx_hash") == target_hash:
                # 해당 해시의 engine 파일도 존재해야 함
                eng = mani.with_suffix("")  # remove .json
                eng = eng.with_suffix(".engine")
                if eng.exists():
                    return True
        except Exception:
            continue
    return False


# =============================================================================
# 실패 기록 — ONNX 해시 기반으로 "건드리지 마" 리스트
# TensorRT 와 호환 안 되는 모델을 매 실행마다 재시도하는 것 방지
# 파일 내용이 바뀌면 해시가 바뀌어 자동으로 재시도됨
# =============================================================================
def _failed_blocklist_path(cache_dir: Path) -> Path:
    return cache_dir / "tensorrt_failed.json"


def _load_failed_hashes(cache_dir: Path) -> dict[str, str]:
    """{onnx_hash: error_message} dict 반환."""
    import json
    p = _failed_blocklist_path(cache_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _record_failure(cache_dir: Path, onnx_hash: str, error: str) -> None:
    """실패 해시 기록 (다음 실행 시 skip)."""
    import json
    p = _failed_blocklist_path(cache_dir)
    data = _load_failed_hashes(cache_dir)
    data[onnx_hash] = error[:500]  # 에러 메시지 길이 제한
    try:
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _is_previously_failed(onnx_path: Path, cache_dir: Path) -> bool:
    """이전 실행에서 실패로 기록된 해시인지."""
    try:
        h = _onnx_sha256(onnx_path)
    except Exception:
        return False
    return h in _load_failed_hashes(cache_dir)


def _default_dims_for(model_stem: str) -> list[int]:
    """
    모델 파일명 기반 동적 차원 기본값 (B, C, H, W).

    ONNX 의 dim_value 가 0/dim_param 인 차원을 이 값으로 대체.
    """
    s = model_stem.lower()
    # YOLO 계열 (YOLOv8, YOLO11, 커스텀 Detect 모델) — 640×640 표준
    yolo_keys = (
        "yolo", "cv-bbox", "cv-digit",
        "player_detector", "courtview_player",
    )
    if any(k in s for k in yolo_keys):
        return [1, 3, 640, 640]

    # ViTPose — 256×192 (H×W, COCO pose 표준)
    if "vitpose" in s:
        return [1, 3, 256, 192]

    # HRNet (혹시 나중에 추가될 경우)
    if "hrnet" in s:
        return [1, 3, 256, 192]

    # MiDaS depth — 256×256
    if "midas" in s:
        return [1, 3, 256, 256]

    # 일반 기본값
    return [1, 3, 640, 640]


def _infer_input_shapes(onnx_path: Path) -> dict[str, tuple[int, ...]]:
    """
    ONNX 파일에서 입력 바인딩의 shape 자동 추출.

    동적 차원(dim_value=0 또는 dim_param) 은 모델별 기본값으로 대체.
    YOLO 계열은 (1,3,640,640), ViTPose 는 (1,3,256,192) 등.
    """
    try:
        import onnx
    except ImportError:
        _logger.warning("onnx 패키지 없음 — input_shapes 추출 불가")
        return {}

    try:
        model = onnx.load(str(onnx_path))
    except Exception as e:
        _logger.warning("onnx 로드 실패 (%s): %s", onnx_path.name, e)
        return {}

    defaults = _default_dims_for(onnx_path.stem)

    shapes: dict[str, tuple[int, ...]] = {}
    for inp in model.graph.input:
        name = inp.name
        dims: list[int] = []
        try:
            for i, d in enumerate(inp.type.tensor_type.shape.dim):
                v = d.dim_value if d.HasField("dim_value") else 0
                if v <= 0:
                    # 동적 차원 → 모델별 기본값 사용
                    v = defaults[i] if i < len(defaults) else 1
                dims.append(v)
        except Exception:
            continue
        if dims:
            shapes[name] = tuple(dims)
    return shapes


def warmup(
    on_progress: ProgressFn | None = None,
    skip_if_cached: bool = True,
) -> WarmupResult:
    """
    전체 워밍업.

    Args:
        on_progress: 진행률 콜백 (스플래시 UI 가 주입)
        skip_if_cached: True 면 이미 캐시에 있는 engine 은 빌드 안 함

    Returns:
        WarmupResult
    """
    from infrastructure.storage.paths import weights_dir, tensorrt_cache_dir

    weights = weights_dir()
    cache = tensorrt_cache_dir()

    _logger.info("워밍업 시작: weights=%s cache=%s", weights, cache)

    models = _discover_onnx_models(weights)
    result = WarmupResult(total=len(models))

    if not models:
        _logger.warning("워밍업 대상 .onnx 없음 (weights 폴더 비어있음)")
        return result

    def _progress(i: int, name: str, status: str):
        if on_progress:
            try:
                on_progress(i, result.total, name, status)
            except Exception:
                pass

    # TensorRTEngine 은 torch/tensorrt 를 임포트하므로 lazy
    try:
        from pose_estimation.backends.tensorrt_engine import TensorRTEngine, TensorRTConfig
    except Exception as e:
        _logger.exception("TensorRTEngine 임포트 실패 — 워밍업 스킵")
        result.failed = result.total
        result.failures.append(("__import__", str(e)))
        return result

    t0 = time.monotonic()

    for idx, onnx_path in enumerate(models):
        name = onnx_path.stem
        _progress(idx, name, "start")

        # 이전 실행에서 실패한 해시면 skip (PyTorch fallback 으로 서버 운영)
        if _is_previously_failed(onnx_path, cache):
            _logger.info("%s: 이전 실행에서 실패 기록 있음 — skip (PyTorch fallback)", name)
            result.failed += 1
            result.failures.append((name, "이전 실패 (blocklist)"))
            _progress(idx, name, "error")
            continue

        # 입력 형태 자동 추출
        input_shapes = _infer_input_shapes(onnx_path)
        if not input_shapes:
            _logger.warning("%s: input_shapes 추출 실패 — 건너뜀", name)
            result.failed += 1
            result.failures.append((name, "input_shapes 추출 실패"))
            _progress(idx, name, "error")
            continue

        # 캐시 hit 여부 — manifest 체크
        cache_hit = _check_cache_hit(onnx_path, cache) if skip_if_cached else False

        try:
            cfg = TensorRTConfig(
                enabled=True,
                fp16=True,
                workspace_mb=1024,
                cache_path=str(cache),
                min_batch_size=1,
                optimal_batch_size=1,
                max_batch_size=8,
            )
            engine = TensorRTEngine(cfg)

            _progress(idx, name, "cached" if cache_hit else "building")

            engine.build_or_load(
                onnx_path=str(onnx_path),
                input_shapes=input_shapes,
            )
            engine.release()

            if cache_hit:
                result.cached += 1
            else:
                result.built += 1
            _progress(idx, name, "done")

        except Exception as e:
            _logger.exception("모델 워밍업 실패: %s", name)
            # 실패 해시 블록리스트 기록 — 다음 실행 시 재시도 안 함
            try:
                h = _onnx_sha256(onnx_path)
                _record_failure(cache, h, f"{type(e).__name__}: {e}")
            except Exception:
                pass
            result.failed += 1
            result.failures.append((name, str(e)))
            _progress(idx, name, "error")

    result.elapsed_sec = time.monotonic() - t0
    _logger.info(
        "워밍업 완료: total=%d built=%d cached=%d failed=%d (%.1fs)",
        result.total, result.built, result.cached, result.failed, result.elapsed_sec,
    )
    return result


def should_warmup() -> bool:
    """
    워밍업 필요 여부 판단.

    - first_run.flag 가 없으면 True (첫 실행)
    - 캐시 폴더에 .engine 이 하나도 없으면 True
    - 그 외엔 False (fast startup)

    Note: manifest 의 GPU·TRT 버전 불일치는 TensorRTEngine.build_or_load() 가
           런타임에 자동 감지·재빌드하므로 여기서 체크 안 함.
    """
    from infrastructure.storage.paths import first_run_flag, tensorrt_cache_dir

    if not first_run_flag().exists():
        return True

    cache = tensorrt_cache_dir()
    has_any_engine = any(cache.glob("*.engine"))
    return not has_any_engine


def mark_first_run_complete() -> None:
    """워밍업 성공 후 플래그 작성."""
    from infrastructure.storage.paths import first_run_flag
    try:
        first_run_flag().write_text(
            "COURTVIEW first run completed.\n",
            encoding="utf-8",
        )
    except Exception:
        _logger.warning("first_run.flag 작성 실패 (무시)")


__all__ = ["warmup", "should_warmup", "mark_first_run_complete", "WarmupResult"]
