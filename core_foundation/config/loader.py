"""
ConfigLoader - YAML/ENV 설정 파일 로더

Desktop Edition 로컬 최적화 버전
- YAML 설정 파일 로딩 및 캐싱
- 환경 변수 로딩 및 오버라이드
- 설정 병합 (우선순위: ENV > env_config > base_config)
- 경로 검증 및 보안
- 메모리 최적화 (<1MB)

성능 목표:
- YAML 로드: <10ms (캐시 미스)
- 캐시 조회: <0.1ms
- 메모리: <1MB (50개 파일 캐시)
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union, List
import os
from fnmatch import fnmatch

import yaml
from dotenv import load_dotenv

from core_foundation.exceptions.base import CourtViewError
from core_foundation.exceptions.validation import ConfigError


# 설정 상수
MAX_CACHE_SIZE = 50  # 최대 캐시 파일 수 (~500KB)
SENSITIVE_KEYS = {'password', 'api_key', 'secret', 'token', 'key'}  # 민감 정보 키


class ConfigLoader:
    """
    YAML/ENV 설정 로더 (Desktop 로컬 최적화)

    특징:
    - 캐싱: 동일 파일 중복 로딩 방지 (LRU 없음, Desktop은 파일 수 적음)
    - 병합: 기본값 + 환경별 + 환경변수 오버라이드
    - 검증: YAML 파싱 에러, 필수 키 누락 감지
    - 보안: 경로 이스케이프 방지, 안전한 YAML 로딩

    메모리 사용량: <1MB (캐시 포함)
    """

    def __init__(
        self,
        config_dir: Union[str, Path] = Path("./configs"),
        env_file: Union[str, Path] = Path(".env"),
        cache_enabled: bool = True,
        validate: bool = True
    ):
        """
        초기화

        Args:
            config_dir: YAML 설정 파일 디렉토리 (기본: ./configs)
            env_file: 환경 변수 파일 (기본: .env)
            cache_enabled: 캐싱 활성화 (기본: True)
            validate: 파일 존재 및 포맷 검증 (기본: True)

        Raises:
            ConfigError: config_dir이 존재하지 않을 때
        """
        self.config_dir = Path(config_dir).resolve()
        self.env_file = Path(env_file)
        self.cache_enabled = cache_enabled
        self.validate = validate

        # 비공개 속성
        self._cache: Dict[str, Dict[str, Any]] = {}  # 파일명 → 설정 딕셔너리
        self._env_vars: Dict[str, str] = {}  # COURTVIEW 관련 환경 변수만
        self._loaded: bool = False  # .env 로딩 완료 플래그

        # 설정 디렉토리 검증
        if validate and not self.config_dir.exists():
            raise ConfigError(f"Config directory not found: {self.config_dir}")

    def load_yaml(self, file_name: str) -> Dict[str, Any]:
        """
        YAML 파일 로드 (캐싱 지원)

        Args:
            file_name: YAML 파일명 (예: "detection/ball.yaml", "base/app.yaml")

        Returns:
            Dict[str, Any]: 파싱된 설정 딕셔너리

        Raises:
            ConfigError: 파일 없음, 파싱 실패, 경로 이스케이프 시도

        성능:
        - 캐시 히트: O(1) - dict 조회만 (~0.05ms)
        - 캐시 미스: O(n) - 파일 읽기 + 파싱 (~5ms)

        메모리:
        - 캐시당 ~10KB (평균 YAML 크기)
        - 최대 50개 파일 → ~500KB

        예시:
            >>> loader = ConfigLoader()
            >>> config = loader.load_yaml("detection/ball.yaml")
            >>> print(config["confidence_threshold"])
            0.75
        """
        # Step 1: 캐시 확인 (히트 시 즉시 반환)
        if self.cache_enabled and file_name in self._cache:
            return self._cache[file_name].copy()  # 복사본 반환 (원본 보호)

        # Step 2: 경로 검증 (보안: Path Traversal 방지)
        file_path = self._validate_path(file_name)

        # Step 3: 파일 존재 확인
        if not file_path.exists():
            raise ConfigError(f"Config file not found: {file_path}")

        # Step 4: YAML 파싱 (안전 모드)
        try:
            config = self._parse_yaml(file_path)
        except yaml.YAMLError as e:
            raise ConfigError(
                f"YAML parsing error in {file_name}: {e}",
                error_code="CV102"
            )

        # Step 5: 캐시 저장 (최대 크기 확인)
        if self.cache_enabled:
            if len(self._cache) >= MAX_CACHE_SIZE:
                # 가장 오래된 항목 제거 (간단한 FIFO - Desktop은 50개면 충분)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[file_name] = config

        return config.copy()

    def load_env(self, override: bool = True) -> Dict[str, str]:
        """
        .env 파일 로드 및 환경 변수 설정

        Args:
            override: 기존 환경 변수 덮어쓰기 (기본: True)

        Returns:
            Dict[str, str]: 로드된 COURTVIEW 관련 환경 변수

        동작:
        1. .env 파일 파싱
        2. os.environ에 설정 (override=True)
        3. COURTVIEW 관련 변수만 내부 저장소에 저장

        보안:
        - 민감 변수는 로깅하지 않음

        예시:
            >>> loader = ConfigLoader()
            >>> env_vars = loader.load_env()
            >>> print(env_vars.get("SERVER_PORT"))
            8000
        """
        # 이미 로드되었고 override=False면 캐시 반환
        if self._loaded and not override:
            return self._env_vars.copy()

        # .env 로드 (dotenv 사용)
        if self.env_file.exists():
            load_dotenv(self.env_file, override=override)
        else:
            # .env 파일 없어도 에러 아님 (환경 변수만 사용 가능)
            pass

        # COURTVIEW 관련 환경 변수만 필터링 (메모리 최적화)
        # 주의: CUDA_는 시스템 환경 변수이므로 제외 (GPU_ 사용)
        self._env_vars = {
            k: v for k, v in os.environ.items()
            if k.startswith((
                'COURTVIEW_',
                'SERVER_',
                'GPU_',
                'DEBUG',
                'DATABASE_',
                'STORAGE_',
                'VIDEO_',
                'OUTPUT_',
                'DATASET_',
                'LOG_',
                'MIN_CAMERAS',
                'MAX_CAMERAS',
                'DEFAULT_RULE_SET',
                'CONFIDENCE_THRESHOLD',
                'MULTI_ANGLE_THRESHOLD',
                'TARGET_FPS',
                'BATCH_SIZE',
                'NUM_WORKERS',
                'ENABLE_'
            ))
        }

        self._loaded = True
        return self._env_vars.copy()

    def merge_configs(
        self,
        base_config: Dict[str, Any],
        env_config: Optional[Dict[str, Any]] = None,
        env_override: Optional[Union[bool, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        설정 병합 (우선순위: ENV > env_config > base_config)

        Args:
            base_config: 기본 설정 (낮은 우선순위)
            env_config: 환경별 설정 (중간 우선순위)
            env_override: 환경 변수 오버라이드 (최고 우선순위)
                - Dict: 명시적 오버라이드 딕셔너리
                - True: .env 파일에서 자동 로드
                - False/None: 오버라이드 없음

        Returns:
            Dict[str, Any]: 병합된 설정

        병합 규칙:
        - 중첩 dict: 재귀적 병합
        - list: 덮어쓰기 (병합 안함)
        - scalar: 덮어쓰기

        예시:
            >>> base = {"port": 8000, "debug": False}
            >>> env = {"debug": True}
            >>> override = {"port": 9000}
            >>> result = loader.merge_configs(base, env, override)
            >>> print(result)
            {"port": 9000, "debug": True}  # override > env > base
        """
        result = base_config.copy()

        # Step 1: env_config 병합 (중간 우선순위)
        if env_config:
            result = self._deep_merge(result, env_config)

        # Step 2: 환경 변수 오버라이드 (최고 우선순위)
        if env_override:
            if isinstance(env_override, dict):
                # 명시적 딕셔너리 오버라이드
                result = self._deep_merge(result, env_override)
            elif env_override is True:
                # .env 파일에서 자동 로드
                if not self._loaded:
                    self.load_env()
                result = self._apply_env_override(result)

        return result

    def get(
        self,
        key_path: str,
        config: Optional[Dict[str, Any]] = None,
        default: Any = None
    ) -> Any:
        """
        점 표기법으로 중첩 설정 조회

        Args:
            key_path: 점으로 구분된 키 경로 (예: "detection.ball.confidence")
            config: 설정 딕셔너리 (None이면 base/app.yaml 로드)
            default: 기본값 (키 없을 때)

        Returns:
            Any: 설정 값 또는 기본값

        예시:
            >>> config = {
            ...     "detection": {
            ...         "ball": {
            ...             "confidence_threshold": 0.75
            ...         }
            ...     }
            ... }
            >>> loader.get("detection.ball.confidence_threshold", config)
            0.75
            >>> loader.get("detection.ball.min_size", config, default=10)
            10
        """
        if config is None:
            # 기본 설정 파일 로드
            config = self.load_yaml("base/app.yaml")

        return self._get_nested(config, key_path.split('.'), default)

    def clear_cache(self, pattern: Optional[str] = None) -> int:
        """
        캐시 클리어

        Args:
            pattern: 파일명 패턴 (예: "detection/*") - None이면 전체

        Returns:
            int: 삭제된 캐시 항목 수

        메모리 해제: O(n)

        예시:
            >>> loader.clear_cache("detection/*")  # detection 관련만
            3
            >>> loader.clear_cache()  # 전체
            15
        """
        count = 0

        if pattern is None:
            # 전체 클리어
            count = len(self._cache)
            self._cache.clear()
        else:
            # 패턴 매칭 항목만 삭제
            keys_to_delete = [k for k in self._cache.keys() if fnmatch(k, pattern)]
            for k in keys_to_delete:
                del self._cache[k]
                count += 1

        return count

    def require_env(self, key: str, error_message: Optional[str] = None) -> str:
        """
        필수 환경 변수 조회 (없으면 예외)

        Args:
            key: 환경 변수 키
            error_message: 커스텀 에러 메시지

        Returns:
            str: 환경 변수 값

        Raises:
            ConfigError: 환경 변수 누락

        예시:
            >>> loader.require_env("SERVER_PORT")
            "8000"
            >>> loader.require_env("MISSING_VAR")
            ConfigError: Required environment variable missing: MISSING_VAR
        """
        if not self._loaded:
            self.load_env()

        value = self._env_vars.get(key)
        if value is None:
            msg = error_message or f"Required environment variable missing: {key}"
            raise ConfigError(msg)

        return value

    # ==================== Private Methods ====================

    def _validate_path(self, file_name: str) -> Path:
        """
        경로 검증 (보안: Path Traversal 방지)

        방어:
        - 상위 디렉토리 이동 방지 (../)
        - 절대 경로 금지
        - configs/ 디렉토리 외부 접근 금지

        Args:
            file_name: 파일명 (상대 경로)

        Returns:
            Path: 검증된 절대 경로

        Raises:
            ConfigError: 보안 위반
        """
        # 절대 경로 금지
        if file_name.startswith('/') or file_name.startswith('\\'):
            raise ConfigError(f"Absolute path not allowed: {file_name}")

        # Windows 드라이브 문자 금지 (C:, D: 등)
        if len(file_name) >= 2 and file_name[1] == ':':
            raise ConfigError(f"Drive letter not allowed: {file_name}")

        # .. 금지 (상위 디렉토리 이동)
        if '..' in file_name:
            raise ConfigError(f"Path traversal not allowed: {file_name}")

        # 정규화된 경로 확인 (symlink 해결)
        file_path = (self.config_dir / file_name).resolve()
        config_dir_resolved = self.config_dir.resolve()

        # configs/ 디렉토리 외부 접근 금지
        if not str(file_path).startswith(str(config_dir_resolved)):
            raise ConfigError(
                f"Access outside config directory not allowed: {file_name}"
            )

        return file_path

    def _parse_yaml(self, file_path: Path) -> Dict[str, Any]:
        """
        안전한 YAML 파싱

        사용: yaml.safe_load (unsafe 금지)
        이유: 임의 Python 객체 실행 방지

        Args:
            file_path: YAML 파일 경로

        Returns:
            Dict[str, Any]: 파싱된 설정

        Raises:
            yaml.YAMLError: 파싱 실패
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            # ✅ 안전: safe_load (기본 타입만 허용)
            result = yaml.safe_load(f)

            # None 처리 (빈 파일)
            if result is None:
                return {}

            # dict 검증
            if not isinstance(result, dict):
                raise ConfigError(
                    f"YAML root must be a dictionary, got {type(result).__name__}"
                )

            return result

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        깊은 병합 (재귀적)

        병합 규칙:
        - dict: 재귀적 병합
        - list: 덮어쓰기 (병합 안함)
        - scalar: 덮어쓰기

        Args:
            base: 기본 딕셔너리
            override: 오버라이드 딕셔너리

        Returns:
            Dict[str, Any]: 병합된 딕셔너리
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # 중첩 dict → 재귀적 병합
                result[key] = self._deep_merge(result[key], value)
            else:
                # scalar 또는 list → 덮어쓰기
                result[key] = value

        return result

    def _apply_env_override(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        환경 변수로 설정 오버라이드

        변환 규칙:
        - SERVER_PORT → server.port
        - GPU_MEMORY_FRACTION → gpu.memory_fraction
        - DEBUG → debug

        타입 추론:
        - "true"/"false" → bool
        - 숫자 문자열 → int/float
        - 나머지 → str

        Args:
            config: 기본 설정

        Returns:
            Dict[str, Any]: 오버라이드된 설정
        """
        result = config.copy()

        for env_key, env_value in self._env_vars.items():
            # 키 변환 (대문자_언더스코어 → 소문자.점)
            config_key = env_key.lower().replace('_', '.')

            # 타입 추론
            typed_value = self._infer_type(env_value)

            # 중첩 키 설정
            self._set_nested(result, config_key.split('.'), typed_value)

        return result

    def _get_nested(
        self,
        data: Dict[str, Any],
        keys: List[str],
        default: Any = None
    ) -> Any:
        """
        중첩 딕셔너리에서 값 조회

        Args:
            data: 딕셔너리
            keys: 키 리스트 (["detection", "ball", "confidence"])
            default: 기본값

        Returns:
            Any: 조회된 값 또는 기본값
        """
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def _set_nested(self, data: Dict[str, Any], keys: List[str], value: Any) -> None:
        """
        중첩 딕셔너리에 값 설정

        Args:
            data: 딕셔너리 (수정됨)
            keys: 키 리스트
            value: 설정할 값
        """
        current = data

        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def _infer_type(self, value: str) -> Union[bool, int, float, str]:
        """
        문자열에서 타입 추론

        Args:
            value: 문자열 값

        Returns:
            Union[bool, int, float, str]: 추론된 타입 값
        """
        # bool
        if value.lower() in ('true', '1', 'yes', 'on'):
            return True
        if value.lower() in ('false', '0', 'no', 'off'):
            return False

        # int
        try:
            return int(value)
        except ValueError:
            pass

        # float
        try:
            return float(value)
        except ValueError:
            pass

        # str (기본)
        return value

    def _safe_log_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        민감 정보 마스킹 (로깅용)

        Args:
            config: 설정 딕셔너리

        Returns:
            Dict[str, Any]: 마스킹된 설정
        """
        return {
            k: '***' if any(s in k.lower() for s in SENSITIVE_KEYS) else v
            for k, v in config.items()
        }

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"ConfigLoader(config_dir={self.config_dir}, "
            f"cache_size={len(self._cache)}, "
            f"env_loaded={self._loaded})"
        )
