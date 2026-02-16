# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/interfaces/unit
파일: test_storage_interface.py
설명: storage_interface.py 단위 테스트 (26 exports, 전체 메서드/프로퍼티 검증)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# cp949 인코딩 수정
# =============================================================================
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
from abc import ABC
from dataclasses import dataclass, fields as dc_fields
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, AsyncIterator, Iterator

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

# =============================================================================
# 테스트 대상 임포트
# =============================================================================
import numpy as np

from shared.constants.localization import SupportedLanguage
from shared.interfaces.storage_interface import (
    # 열거형
    StorageType,
    StorageState,
    ContentType,
    SortOrder,
    # 메타데이터
    FileMetadata,
    VideoMetadata,
    # 결과
    UploadResult,
    DownloadResult,
    # 메트릭
    StorageMetrics,
    RepositoryMetrics,
    # 기본 스토리지
    IStorage,
    # 비디오 스토리지
    IVideoStorage,
    # 캐시
    CacheEntry,
    ICache,
    # 분석 결과 스토리지
    AnalysisResultEntry,
    IAnalysisResultStorage,
    # 리포지토리
    SortCriteria,
    PaginationParams,
    PaginatedResult,
    FilterCriteria,
    QueryOptions,
    IRepository,
    IUserRepository,
    IVideoRepository,
    IAnalysisRepository,
    # 팩토리
    IStorageFactory,
    __version__,
    __all__,
)


# =============================================================================
# 테스트 하네스
# =============================================================================
class TestResult:
    def __init__(self): self.passed = 0; self.failed = 0; self.section = ""
    def set_section(self, name): self.section = name; print(f"\n{'='*60}\n  {name}\n{'='*60}")
    def ok(self, desc): self.passed += 1; print(f"  [PASS] {desc}")
    def fail(self, desc, detail=""): self.failed += 1; d = f" ({detail})" if detail else ""; print(f"  [FAIL] {desc}{d}")
    def check(self, cond, desc, detail=""):
        if cond: self.ok(desc)
        else: self.fail(desc, detail)
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}\n  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL\n{'='*60}")
        return self.failed == 0


# =============================================================================
# ABC 구체 스텁 클래스
# =============================================================================
class StubStorage(IStorage[dict]):
    """IStorage 구체 구현 스텁."""
    def __init__(self):
        self._type = StorageType.LOCAL
        self._state = StorageState.CONNECTED
        self._metrics = StorageMetrics()
    @property
    def storage_type(self) -> StorageType: return self._type
    @property
    def state(self) -> StorageState: return self._state
    @property
    def metrics(self) -> StorageMetrics: return self._metrics
    def connect(self, config): self._state = StorageState.CONNECTED
    def disconnect(self): self._state = StorageState.DISCONNECTED
    def upload(self, key, data, content_type="application/octet-stream", metadata=None):
        return UploadResult.success_result(key=key)
    def download(self, key): return DownloadResult.success_result(key=key, data=b"test")
    def download_to_file(self, key, local_path):
        return DownloadResult.success_result(key=key, local_path=local_path)
    def exists(self, key): return True
    def delete(self, key): return True
    def get_metadata(self, key):
        return FileMetadata(key=key, size_bytes=100, content_type="application/octet-stream",
                            last_modified=datetime.now(timezone.utc))
    def list_files(self, prefix="", max_results=1000): return []
    def get_signed_url(self, key, expires_in=timedelta(hours=1), for_upload=False):
        return f"https://signed.example.com/{key}"


class StubVideoStorage(IVideoStorage[dict]):
    """IVideoStorage 구체 구현 스텁."""
    def __init__(self):
        self._type = StorageType.S3
        self._state = StorageState.CONNECTED
        self._metrics = StorageMetrics()
    @property
    def storage_type(self) -> StorageType: return self._type
    @property
    def state(self) -> StorageState: return self._state
    @property
    def metrics(self) -> StorageMetrics: return self._metrics
    def connect(self, config): pass
    def disconnect(self): pass
    def upload(self, key, data, content_type="application/octet-stream", metadata=None):
        return UploadResult.success_result(key=key)
    def download(self, key): return DownloadResult.success_result(key=key)
    def download_to_file(self, key, local_path):
        return DownloadResult.success_result(key=key, local_path=local_path)
    def exists(self, key): return True
    def delete(self, key): return True
    def get_metadata(self, key): return None
    def list_files(self, prefix="", max_results=1000): return []
    def get_signed_url(self, key, expires_in=timedelta(hours=1), for_upload=False):
        return f"https://signed.example.com/{key}"
    def upload_video(self, key, video_path, extract_metadata=True):
        return UploadResult.success_result(key=key)
    def get_video_metadata(self, key):
        return VideoMetadata(key=key, size_bytes=5000000, content_type="video/mp4",
                             last_modified=datetime.now(timezone.utc), width=1920, height=1080, fps=30.0)
    def extract_frames(self, key, output_dir, fps=None, start_time=0.0, duration=None):
        return [f"{output_dir}/frame_0001.png"]
    def stream_frames(self, key, start_frame=0, end_frame=None, batch_size=1):
        yield [np.zeros((100, 100, 3), dtype=np.uint8)]
    def stream_frames_async(self, key, start_frame=0, end_frame=None, batch_size=1):
        async def _gen():
            yield [np.zeros((100, 100, 3), dtype=np.uint8)]
        return _gen()
    def get_streaming_url(self, key, expires_in=timedelta(hours=1)):
        return f"https://stream.example.com/{key}"


class StubCache(ICache[dict]):
    """ICache 구체 구현 스텁."""
    def __init__(self):
        self._state = StorageState.CONNECTED
        self._data: dict[str, Any] = {}
    @property
    def state(self) -> StorageState: return self._state
    def connect(self, config): self._state = StorageState.CONNECTED
    def disconnect(self): self._state = StorageState.DISCONNECTED
    def get(self, key): return self._data.get(key)
    def set(self, key, value, ttl=None): self._data[key] = value; return True
    def delete(self, key):
        if key in self._data: del self._data[key]; return True
        return False
    def exists(self, key): return key in self._data
    def clear(self, pattern=None): c = len(self._data); self._data.clear(); return c
    def get_many(self, keys): return {k: self._data[k] for k in keys if k in self._data}
    def set_many(self, items, ttl=None): self._data.update(items); return True
    def incr(self, key, delta=1):
        self._data[key] = self._data.get(key, 0) + delta; return self._data[key]
    def decr(self, key, delta=1):
        self._data[key] = self._data.get(key, 0) - delta; return self._data[key]


class StubAnalysisResultStorage(IAnalysisResultStorage[dict]):
    """IAnalysisResultStorage 구체 구현 스텁."""
    def __init__(self): self._results: dict[str, AnalysisResultEntry] = {}
    def connect(self, config): pass
    def disconnect(self): pass
    def save_result(self, entry):
        rid = f"result_{len(self._results)+1}"
        self._results[rid] = entry
        return rid
    def get_result(self, result_id): return self._results.get(result_id)
    def get_results_by_user(self, user_id, analysis_type=None, limit=100, offset=0):
        return [e for e in self._results.values() if e.user_id == user_id]
    def get_results_by_session(self, session_id):
        return [e for e in self._results.values() if e.session_id == session_id]
    def delete_result(self, result_id):
        if result_id in self._results: del self._results[result_id]; return True
        return False
    def get_statistics(self, user_id, start_date=None, end_date=None):
        return {"total": len([e for e in self._results.values() if e.user_id == user_id])}


@dataclass
class _FakeEntity:
    id: str = ""
    name: str = ""
    email: str = ""
    username: str = ""
    status: str = "active"


class StubRepository(IRepository[_FakeEntity, str]):
    """IRepository 구체 구현 스텁."""
    def __init__(self):
        self._data: dict[str, _FakeEntity] = {}
        self._metrics = RepositoryMetrics()
        self._counter = 0
    @property
    def entity_name(self) -> str: return "FakeEntity"
    @property
    def metrics(self) -> RepositoryMetrics: return self._metrics
    def create(self, entity):
        self._counter += 1; entity.id = f"id_{self._counter}"
        self._data[entity.id] = entity; return entity
    def get_by_id(self, entity_id): return self._data.get(entity_id)
    def get_all(self, options=None): return list(self._data.values())
    def update(self, entity): self._data[entity.id] = entity; return entity
    def delete(self, entity_id):
        if entity_id in self._data: del self._data[entity_id]; return True
        return False
    def exists(self, entity_id): return entity_id in self._data
    def count(self, options=None): return len(self._data)
    def find_one(self, options):
        items = list(self._data.values())
        if options and options.filters:
            for f in options.filters:
                items = [e for e in items if getattr(e, f.field, None) == f.value]
        return items[0] if items else None
    def find_by_ids(self, entity_ids):
        return [self._data[eid] for eid in entity_ids if eid in self._data]
    def create_many(self, entities):
        return [self.create(e) for e in entities]
    def update_many(self, entities):
        return [self.update(e) for e in entities]
    def delete_many(self, entity_ids):
        c = 0
        for eid in entity_ids:
            if self.delete(eid): c += 1
        return c
    def begin_transaction(self): return "tx"
    def commit_transaction(self, transaction): pass
    def rollback_transaction(self, transaction): pass


class StubUserRepository(IUserRepository[_FakeEntity]):
    """IUserRepository 구체 구현 스텁."""
    def __init__(self):
        self._data: dict[str, _FakeEntity] = {}
        self._metrics = RepositoryMetrics()
        self._counter = 0
    @property
    def entity_name(self) -> str: return "User"
    @property
    def metrics(self) -> RepositoryMetrics: return self._metrics
    def create(self, entity):
        self._counter += 1; entity.id = f"u_{self._counter}"
        self._data[entity.id] = entity; return entity
    def get_by_id(self, entity_id): return self._data.get(entity_id)
    def get_all(self, options=None): return list(self._data.values())
    def update(self, entity): self._data[entity.id] = entity; return entity
    def delete(self, entity_id):
        if entity_id in self._data: del self._data[entity_id]; return True
        return False
    def exists(self, entity_id): return entity_id in self._data
    def count(self, options=None): return len(self._data)
    def find_one(self, options):
        items = list(self._data.values())
        if options and options.filters:
            for f in options.filters:
                items = [e for e in items if getattr(e, f.field, None) == f.value]
        return items[0] if items else None
    def find_by_ids(self, entity_ids):
        return [self._data[eid] for eid in entity_ids if eid in self._data]
    def create_many(self, entities): return [self.create(e) for e in entities]
    def update_many(self, entities): return [self.update(e) for e in entities]
    def delete_many(self, entity_ids):
        return sum(1 for eid in entity_ids if self.delete(eid))
    def begin_transaction(self): return "tx"
    def commit_transaction(self, transaction): pass
    def rollback_transaction(self, transaction): pass
    def get_by_email(self, email):
        for e in self._data.values():
            if getattr(e, "email", None) == email: return e
        return None
    def get_by_username(self, username):
        for e in self._data.values():
            if getattr(e, "username", None) == username: return e
        return None
    def get_active_users(self, since=None): return list(self._data.values())


class StubVideoRepository(IVideoRepository[_FakeEntity]):
    """IVideoRepository 구체 구현 스텁."""
    def __init__(self):
        self._data: dict[str, _FakeEntity] = {}
        self._metrics = RepositoryMetrics()
        self._counter = 0
    @property
    def entity_name(self) -> str: return "Video"
    @property
    def metrics(self) -> RepositoryMetrics: return self._metrics
    def create(self, entity):
        self._counter += 1; entity.id = f"v_{self._counter}"
        self._data[entity.id] = entity; return entity
    def get_by_id(self, entity_id): return self._data.get(entity_id)
    def get_all(self, options=None): return list(self._data.values())
    def update(self, entity): self._data[entity.id] = entity; return entity
    def delete(self, entity_id):
        if entity_id in self._data: del self._data[entity_id]; return True
        return False
    def exists(self, entity_id): return entity_id in self._data
    def count(self, options=None): return len(self._data)
    def find_one(self, options):
        items = list(self._data.values())
        if options and options.filters:
            for f in options.filters:
                items = [e for e in items if getattr(e, f.field, None) == f.value]
        return items[0] if items else None
    def find_by_ids(self, entity_ids):
        return [self._data[eid] for eid in entity_ids if eid in self._data]
    def create_many(self, entities): return [self.create(e) for e in entities]
    def update_many(self, entities): return [self.update(e) for e in entities]
    def delete_many(self, entity_ids):
        return sum(1 for eid in entity_ids if self.delete(eid))
    def begin_transaction(self): return "tx"
    def commit_transaction(self, transaction): pass
    def rollback_transaction(self, transaction): pass
    def get_by_user_id(self, user_id, options=None):
        return [e for e in self._data.values() if getattr(e, "name", "") == user_id]
    def get_by_status(self, status, options=None):
        return [e for e in self._data.values() if getattr(e, "status", "") == status]
    def get_pending_analysis(self, limit=10):
        return list(self._data.values())[:limit]


class StubAnalysisRepository(IAnalysisRepository[_FakeEntity]):
    """IAnalysisRepository 구체 구현 스텁."""
    def __init__(self):
        self._data: dict[str, _FakeEntity] = {}
        self._metrics = RepositoryMetrics()
        self._counter = 0
    @property
    def entity_name(self) -> str: return "Analysis"
    @property
    def metrics(self) -> RepositoryMetrics: return self._metrics
    def create(self, entity):
        self._counter += 1; entity.id = f"a_{self._counter}"
        self._data[entity.id] = entity; return entity
    def get_by_id(self, entity_id): return self._data.get(entity_id)
    def get_all(self, options=None): return list(self._data.values())
    def update(self, entity): self._data[entity.id] = entity; return entity
    def delete(self, entity_id):
        if entity_id in self._data: del self._data[entity_id]; return True
        return False
    def exists(self, entity_id): return entity_id in self._data
    def count(self, options=None): return len(self._data)
    def find_one(self, options):
        items = list(self._data.values())
        if options and options.filters:
            for f in options.filters:
                items = [e for e in items if getattr(e, f.field, None) == f.value]
        return items[0] if items else None
    def find_by_ids(self, entity_ids):
        return [self._data[eid] for eid in entity_ids if eid in self._data]
    def create_many(self, entities): return [self.create(e) for e in entities]
    def update_many(self, entities): return [self.update(e) for e in entities]
    def delete_many(self, entity_ids):
        return sum(1 for eid in entity_ids if self.delete(eid))
    def begin_transaction(self): return "tx"
    def commit_transaction(self, transaction): pass
    def rollback_transaction(self, transaction): pass
    def get_by_video_id(self, video_id): return []
    def get_by_user_and_type(self, user_id, analysis_type, options=None): return []
    def get_latest_by_user(self, user_id, limit=10): return []
    def get_statistics_by_user(self, user_id, start_date=None, end_date=None):
        return {"total": 0}


class StubStorageFactory(IStorageFactory):
    """IStorageFactory 구체 구현 스텁."""
    def create_storage(self, storage_type, config): return StubStorage()
    def create_video_storage(self, storage_type, config): return StubVideoStorage()
    def create_cache(self, config): return StubCache()


# =============================================================================
# 테스트 함수
# =============================================================================
def test_module_metadata(tr: TestResult) -> None:
    """[A] 모듈 메타데이터 검증."""
    tr.set_section("[A] 모듈 메타데이터")

    # 버전 검증
    tr.check(__version__ == "1.1.0", "__version__ == '1.1.0'", f"got {__version__}")

    # __all__ 개수 검증
    tr.check(len(__all__) == 26, f"__all__에 26개 항목 ({len(__all__)}개)", f"got {len(__all__)}")

    # __all__ 내 모든 이름 임포트 가능 검증
    expected_names = [
        "StorageType", "StorageState", "ContentType", "SortOrder",
        "FileMetadata", "VideoMetadata",
        "UploadResult", "DownloadResult",
        "StorageMetrics", "RepositoryMetrics",
        "IStorage", "IVideoStorage",
        "CacheEntry", "ICache",
        "AnalysisResultEntry", "IAnalysisResultStorage",
        "SortCriteria", "PaginationParams", "PaginatedResult",
        "FilterCriteria", "QueryOptions",
        "IRepository", "IUserRepository", "IVideoRepository", "IAnalysisRepository",
        "IStorageFactory",
    ]
    for name in expected_names:
        tr.check(name in __all__, f"'{name}' in __all__")

    # shared.interfaces 패키지에서도 임포트 가능 검증
    import shared.interfaces as iface_pkg
    for name in expected_names:
        tr.check(hasattr(iface_pkg, name), f"shared.interfaces에서 '{name}' 접근 가능")


def test_storage_type_enum(tr: TestResult) -> None:
    """[B] StorageType 열거형 검증."""
    tr.set_section("[B] StorageType 열거형")

    # 멤버 수
    members = list(StorageType)
    tr.check(len(members) == 5, f"StorageType 멤버 5개 ({len(members)}개)")

    # 값 검증
    expected_values = {
        StorageType.LOCAL: "local", StorageType.S3: "s3", StorageType.GCS: "gcs",
        StorageType.AZURE_BLOB: "azure_blob", StorageType.MEMORY: "memory",
    }
    for member, val in expected_values.items():
        tr.check(member.value == val, f"StorageType.{member.name}.value == '{val}'")

    # __str__
    for member, val in expected_values.items():
        tr.check(str(member) == val, f"str(StorageType.{member.name}) == '{val}'")

    # isinstance(str, Enum) 검증
    tr.check(isinstance(StorageType.LOCAL, str), "StorageType은 str 상속")
    tr.check(isinstance(StorageType.LOCAL, Enum), "StorageType은 Enum 상속")

    # 다국어 이름
    for member in StorageType:
        ko = member.get_name(SupportedLanguage.KO)
        en = member.get_name(SupportedLanguage.EN)
        ja = member.get_name(SupportedLanguage.JA)
        zh = member.get_name(SupportedLanguage.ZH)
        es = member.get_name(SupportedLanguage.ES)
        tr.check(isinstance(ko, str) and len(ko) > 0, f"{member.name}.get_name(KO) = '{ko}'")
        tr.check(isinstance(en, str) and len(en) > 0, f"{member.name}.get_name(EN) = '{en}'")
        tr.check(isinstance(ja, str) and len(ja) > 0, f"{member.name}.get_name(JA) = '{ja}'")
        tr.check(isinstance(zh, str) and len(zh) > 0, f"{member.name}.get_name(ZH) = '{zh}'")
        tr.check(isinstance(es, str) and len(es) > 0, f"{member.name}.get_name(ES) = '{es}'")
        # 기본 인자 = KO
        tr.check(member.get_name() == ko, f"{member.name}.get_name() 기본값 == KO")
        # to_korean
        tr.check(member.to_korean == ko, f"{member.name}.to_korean == get_name(KO)")

    # is_cloud
    tr.check(StorageType.S3.is_cloud is True, "S3.is_cloud == True")
    tr.check(StorageType.GCS.is_cloud is True, "GCS.is_cloud == True")
    tr.check(StorageType.AZURE_BLOB.is_cloud is True, "AZURE_BLOB.is_cloud == True")
    tr.check(StorageType.LOCAL.is_cloud is False, "LOCAL.is_cloud == False")
    tr.check(StorageType.MEMORY.is_cloud is False, "MEMORY.is_cloud == False")

    # is_local
    tr.check(StorageType.LOCAL.is_local is True, "LOCAL.is_local == True")
    tr.check(StorageType.MEMORY.is_local is True, "MEMORY.is_local == True")
    tr.check(StorageType.S3.is_local is False, "S3.is_local == False")
    tr.check(StorageType.GCS.is_local is False, "GCS.is_local == False")
    tr.check(StorageType.AZURE_BLOB.is_local is False, "AZURE_BLOB.is_local == False")

    # is_persistent
    tr.check(StorageType.LOCAL.is_persistent is True, "LOCAL.is_persistent == True")
    tr.check(StorageType.S3.is_persistent is True, "S3.is_persistent == True")
    tr.check(StorageType.GCS.is_persistent is True, "GCS.is_persistent == True")
    tr.check(StorageType.AZURE_BLOB.is_persistent is True, "AZURE_BLOB.is_persistent == True")
    tr.check(StorageType.MEMORY.is_persistent is False, "MEMORY.is_persistent == False")


def test_storage_state_enum(tr: TestResult) -> None:
    """[C] StorageState 열거형 검증."""
    tr.set_section("[C] StorageState 열거형")

    members = list(StorageState)
    tr.check(len(members) == 3, f"StorageState 멤버 3개 ({len(members)}개)")

    expected_values = {
        StorageState.DISCONNECTED: "disconnected",
        StorageState.CONNECTED: "connected",
        StorageState.ERROR: "error",
    }
    for member, val in expected_values.items():
        tr.check(member.value == val, f"StorageState.{member.name}.value == '{val}'")
        tr.check(str(member) == val, f"str(StorageState.{member.name}) == '{val}'")

    tr.check(isinstance(StorageState.CONNECTED, str), "StorageState은 str 상속")
    tr.check(isinstance(StorageState.CONNECTED, Enum), "StorageState은 Enum 상속")

    # 다국어 이름
    for member in StorageState:
        ko = member.get_name(SupportedLanguage.KO)
        en = member.get_name(SupportedLanguage.EN)
        ja = member.get_name(SupportedLanguage.JA)
        zh = member.get_name(SupportedLanguage.ZH)
        es = member.get_name(SupportedLanguage.ES)
        tr.check(isinstance(ko, str) and len(ko) > 0, f"{member.name}.get_name(KO) = '{ko}'")
        tr.check(isinstance(en, str) and len(en) > 0, f"{member.name}.get_name(EN) = '{en}'")
        tr.check(isinstance(ja, str) and len(ja) > 0, f"{member.name}.get_name(JA) = '{ja}'")
        tr.check(isinstance(zh, str) and len(zh) > 0, f"{member.name}.get_name(ZH) = '{zh}'")
        tr.check(isinstance(es, str) and len(es) > 0, f"{member.name}.get_name(ES) = '{es}'")
        tr.check(member.get_name() == ko, f"{member.name}.get_name() 기본값 == KO")
        tr.check(member.to_korean == ko, f"{member.name}.to_korean == get_name(KO)")

    # 특정 다국어 값 검증
    tr.check(StorageState.CONNECTED.get_name(SupportedLanguage.KO) == "연결됨",
             "CONNECTED KO == '연결됨'")
    tr.check(StorageState.CONNECTED.get_name(SupportedLanguage.EN) == "Connected",
             "CONNECTED EN == 'Connected'")
    tr.check(StorageState.DISCONNECTED.get_name(SupportedLanguage.JA) == "切断",
             "DISCONNECTED JA == '切断'")

    # is_connected / is_disconnected / is_error / is_available
    for member in StorageState:
        tr.check(member.is_connected == (member == StorageState.CONNECTED),
                 f"{member.name}.is_connected == {member == StorageState.CONNECTED}")
        tr.check(member.is_disconnected == (member == StorageState.DISCONNECTED),
                 f"{member.name}.is_disconnected == {member == StorageState.DISCONNECTED}")
        tr.check(member.is_error == (member == StorageState.ERROR),
                 f"{member.name}.is_error == {member == StorageState.ERROR}")
        tr.check(member.is_available == (member == StorageState.CONNECTED),
                 f"{member.name}.is_available == {member == StorageState.CONNECTED}")


def test_content_type_enum(tr: TestResult) -> None:
    """[D] ContentType 열거형 검증."""
    tr.set_section("[D] ContentType 열거형")

    members = list(ContentType)
    tr.check(len(members) == 11, f"ContentType 멤버 11개 ({len(members)}개)")

    # 값 검증
    expected_values = {
        ContentType.VIDEO_MP4: "video/mp4",
        ContentType.VIDEO_AVI: "video/x-msvideo",
        ContentType.VIDEO_MOV: "video/quicktime",
        ContentType.VIDEO_WEBM: "video/webm",
        ContentType.IMAGE_JPEG: "image/jpeg",
        ContentType.IMAGE_PNG: "image/png",
        ContentType.IMAGE_WEBP: "image/webp",
        ContentType.JSON: "application/json",
        ContentType.BINARY: "application/octet-stream",
        ContentType.NUMPY: "application/x-numpy",
        ContentType.PICKLE: "application/x-pickle",
    }
    for member, val in expected_values.items():
        tr.check(member.value == val, f"ContentType.{member.name}.value == '{val}'")
        tr.check(str(member) == val, f"str(ContentType.{member.name}) == '{val}'")

    tr.check(isinstance(ContentType.JSON, str), "ContentType은 str 상속")
    tr.check(isinstance(ContentType.JSON, Enum), "ContentType은 Enum 상속")

    # 다국어 이름
    for member in ContentType:
        ko = member.get_name(SupportedLanguage.KO)
        en = member.get_name(SupportedLanguage.EN)
        ja = member.get_name(SupportedLanguage.JA)
        zh = member.get_name(SupportedLanguage.ZH)
        es = member.get_name(SupportedLanguage.ES)
        tr.check(isinstance(ko, str) and len(ko) > 0, f"{member.name}.get_name(KO) = '{ko}'")
        tr.check(isinstance(en, str) and len(en) > 0, f"{member.name}.get_name(EN) = '{en}'")
        tr.check(isinstance(ja, str) and len(ja) > 0, f"{member.name}.get_name(JA) = '{ja}'")
        tr.check(isinstance(zh, str) and len(zh) > 0, f"{member.name}.get_name(ZH) = '{zh}'")
        tr.check(isinstance(es, str) and len(es) > 0, f"{member.name}.get_name(ES) = '{es}'")
        tr.check(member.get_name() == ko, f"{member.name}.get_name() 기본값 == KO")
        tr.check(member.to_korean == ko, f"{member.name}.to_korean == get_name(KO)")

    # 특정 다국어 값 검증
    tr.check(ContentType.VIDEO_MP4.get_name(SupportedLanguage.KO) == "비디오 (MP4)",
             "VIDEO_MP4 KO == '비디오 (MP4)'")
    tr.check(ContentType.IMAGE_JPEG.get_name(SupportedLanguage.EN) == "Image (JPEG)",
             "IMAGE_JPEG EN == 'Image (JPEG)'")
    tr.check(ContentType.JSON.get_name(SupportedLanguage.JA) == "JSONデータ",
             "JSON JA == 'JSONデータ'")
    tr.check(ContentType.NUMPY.get_name(SupportedLanguage.ZH) == "NumPy数组",
             "NUMPY ZH == 'NumPy数组'")
    tr.check(ContentType.PICKLE.get_name(SupportedLanguage.ES) == "Objeto Pickle",
             "PICKLE ES == 'Objeto Pickle'")

    # is_video
    video_types = {ContentType.VIDEO_MP4, ContentType.VIDEO_AVI, ContentType.VIDEO_MOV, ContentType.VIDEO_WEBM}
    for member in ContentType:
        expected = member in video_types
        tr.check(member.is_video == expected, f"{member.name}.is_video == {expected}")

    # is_image
    image_types = {ContentType.IMAGE_JPEG, ContentType.IMAGE_PNG, ContentType.IMAGE_WEBP}
    for member in ContentType:
        expected = member in image_types
        tr.check(member.is_image == expected, f"{member.name}.is_image == {expected}")

    # is_data
    data_types = {ContentType.JSON, ContentType.BINARY, ContentType.NUMPY, ContentType.PICKLE}
    for member in ContentType:
        expected = member in data_types
        tr.check(member.is_data == expected, f"{member.name}.is_data == {expected}")

    # extension 검증
    ext_map = {
        ContentType.VIDEO_MP4: ".mp4", ContentType.VIDEO_AVI: ".avi",
        ContentType.VIDEO_MOV: ".mov", ContentType.VIDEO_WEBM: ".webm",
        ContentType.IMAGE_JPEG: ".jpg", ContentType.IMAGE_PNG: ".png",
        ContentType.IMAGE_WEBP: ".webp", ContentType.JSON: ".json",
        ContentType.BINARY: ".bin", ContentType.NUMPY: ".npy",
        ContentType.PICKLE: ".pkl",
    }
    for member, ext in ext_map.items():
        tr.check(member.extension == ext, f"{member.name}.extension == '{ext}'")

    # from_extension 검증
    from_ext_cases = {
        "mp4": ContentType.VIDEO_MP4, "avi": ContentType.VIDEO_AVI,
        "mov": ContentType.VIDEO_MOV, "webm": ContentType.VIDEO_WEBM,
        "jpg": ContentType.IMAGE_JPEG, "jpeg": ContentType.IMAGE_JPEG,
        "png": ContentType.IMAGE_PNG, "webp": ContentType.IMAGE_WEBP,
        "json": ContentType.JSON, "bin": ContentType.BINARY,
        "npy": ContentType.NUMPY, "pkl": ContentType.PICKLE,
        "pickle": ContentType.PICKLE,
    }
    for ext, expected_ct in from_ext_cases.items():
        result = ContentType.from_extension(ext)
        tr.check(result == expected_ct, f"from_extension('{ext}') == {expected_ct.name}")

    # from_extension 알 수 없는 확장자
    tr.check(ContentType.from_extension("xyz") is None, "from_extension('xyz') == None")
    tr.check(ContentType.from_extension("docx") is None, "from_extension('docx') == None")

    # from_extension 대소문자 무관
    tr.check(ContentType.from_extension("MP4") == ContentType.VIDEO_MP4,
             "from_extension('MP4') 대소문자 무관")
    tr.check(ContentType.from_extension("Jpeg") == ContentType.IMAGE_JPEG,
             "from_extension('Jpeg') 대소문자 무관")

    # from_extension 앞에 점(.)이 있는 경우
    tr.check(ContentType.from_extension(".mp4") == ContentType.VIDEO_MP4,
             "from_extension('.mp4') 앞에 점 제거")
    tr.check(ContentType.from_extension(".PNG") == ContentType.IMAGE_PNG,
             "from_extension('.PNG') 앞에 점 + 대소문자 무관")


def test_sort_order_enum(tr: TestResult) -> None:
    """[E] SortOrder 열거형 검증."""
    tr.set_section("[E] SortOrder 열거형")

    members = list(SortOrder)
    tr.check(len(members) == 2, f"SortOrder 멤버 2개 ({len(members)}개)")

    tr.check(SortOrder.ASC.value == "asc", "ASC.value == 'asc'")
    tr.check(SortOrder.DESC.value == "desc", "DESC.value == 'desc'")
    tr.check(str(SortOrder.ASC) == "asc", "str(ASC) == 'asc'")
    tr.check(str(SortOrder.DESC) == "desc", "str(DESC) == 'desc'")

    tr.check(isinstance(SortOrder.ASC, str), "SortOrder은 str 상속")
    tr.check(isinstance(SortOrder.ASC, Enum), "SortOrder은 Enum 상속")

    # 다국어
    for member in SortOrder:
        ko = member.get_name(SupportedLanguage.KO)
        en = member.get_name(SupportedLanguage.EN)
        ja = member.get_name(SupportedLanguage.JA)
        zh = member.get_name(SupportedLanguage.ZH)
        es = member.get_name(SupportedLanguage.ES)
        tr.check(isinstance(ko, str) and len(ko) > 0, f"{member.name}.get_name(KO) = '{ko}'")
        tr.check(isinstance(en, str) and len(en) > 0, f"{member.name}.get_name(EN) = '{en}'")
        tr.check(isinstance(ja, str) and len(ja) > 0, f"{member.name}.get_name(JA) = '{ja}'")
        tr.check(isinstance(zh, str) and len(zh) > 0, f"{member.name}.get_name(ZH) = '{zh}'")
        tr.check(isinstance(es, str) and len(es) > 0, f"{member.name}.get_name(ES) = '{es}'")
        tr.check(member.get_name() == ko, f"{member.name}.get_name() 기본값 == KO")
        tr.check(member.to_korean == ko, f"{member.name}.to_korean == get_name(KO)")

    # 특정값
    tr.check(SortOrder.ASC.get_name(SupportedLanguage.KO) == "오름차순", "ASC KO == '오름차순'")
    tr.check(SortOrder.DESC.get_name(SupportedLanguage.KO) == "내림차순", "DESC KO == '내림차순'")
    tr.check(SortOrder.ASC.get_name(SupportedLanguage.EN) == "Ascending", "ASC EN == 'Ascending'")
    tr.check(SortOrder.DESC.get_name(SupportedLanguage.EN) == "Descending", "DESC EN == 'Descending'")

    # is_ascending / is_descending
    tr.check(SortOrder.ASC.is_ascending is True, "ASC.is_ascending == True")
    tr.check(SortOrder.ASC.is_descending is False, "ASC.is_descending == False")
    tr.check(SortOrder.DESC.is_ascending is False, "DESC.is_ascending == False")
    tr.check(SortOrder.DESC.is_descending is True, "DESC.is_descending == True")

    # reverse
    tr.check(SortOrder.ASC.reverse() == SortOrder.DESC, "ASC.reverse() == DESC")
    tr.check(SortOrder.DESC.reverse() == SortOrder.ASC, "DESC.reverse() == ASC")


def test_file_metadata(tr: TestResult) -> None:
    """[F] FileMetadata 데이터클래스 검증."""
    tr.set_section("[F] FileMetadata 데이터클래스")

    now = datetime.now(timezone.utc)
    fm = FileMetadata(
        key="videos/test_game.mp4",
        size_bytes=10485760,  # 10MB
        content_type="video/mp4",
        last_modified=now,
        etag="abc123",
        checksum="sha256:xyz",
        custom_metadata={"user": "test"},
    )

    tr.check(fm.key == "videos/test_game.mp4", "key 필드 설정")
    tr.check(fm.size_bytes == 10485760, "size_bytes 필드 설정")
    tr.check(fm.content_type == "video/mp4", "content_type 필드 설정")
    tr.check(fm.last_modified == now, "last_modified 필드 설정")
    tr.check(fm.etag == "abc123", "etag 필드 설정")
    tr.check(fm.checksum == "sha256:xyz", "checksum 필드 설정")
    tr.check(fm.custom_metadata == {"user": "test"}, "custom_metadata 필드 설정")

    # 기본값 검증
    fm2 = FileMetadata(key="a.json", size_bytes=100, content_type="application/json",
                       last_modified=now)
    tr.check(fm2.etag is None, "etag 기본값 None")
    tr.check(fm2.checksum is None, "checksum 기본값 None")
    tr.check(fm2.custom_metadata == {}, "custom_metadata 기본값 빈 딕셔너리")

    # size_mb
    tr.check(abs(fm.size_mb - 10.0) < 0.001, f"size_mb == 10.0 (got {fm.size_mb:.4f})")

    # size_gb
    tr.check(abs(fm.size_gb - 10.0 / 1024) < 0.0001, f"size_gb 계산 정확 (got {fm.size_gb:.6f})")

    # extension
    tr.check(fm.extension == ".mp4", f"extension == '.mp4' (got '{fm.extension}')")

    # filename
    tr.check(fm.filename == "test_game.mp4", f"filename == 'test_game.mp4' (got '{fm.filename}')")

    # 확장자 없는 파일
    fm3 = FileMetadata(key="data/Makefile", size_bytes=50, content_type="text/plain",
                       last_modified=now)
    tr.check(fm3.extension == "", "확장자 없는 파일 extension == ''")
    tr.check(fm3.filename == "Makefile", "확장자 없는 파일 filename == 'Makefile'")

    # 크기 0인 파일
    fm4 = FileMetadata(key="empty.txt", size_bytes=0, content_type="text/plain",
                       last_modified=now)
    tr.check(fm4.size_mb == 0.0, "size_bytes=0 → size_mb == 0.0")
    tr.check(fm4.size_gb == 0.0, "size_bytes=0 → size_gb == 0.0")


def test_upload_result(tr: TestResult) -> None:
    """[G] UploadResult 데이터클래스 검증."""
    tr.set_section("[G] UploadResult 데이터클래스")

    # 직접 생성
    ur = UploadResult(success=True, key="test.mp4", url="https://s3/test.mp4",
                      etag="e123", version_id="v1", upload_time_ms=150.5)
    tr.check(ur.success is True, "success == True")
    tr.check(ur.key == "test.mp4", "key == 'test.mp4'")
    tr.check(ur.url == "https://s3/test.mp4", "url 설정")
    tr.check(ur.etag == "e123", "etag 설정")
    tr.check(ur.version_id == "v1", "version_id 설정")
    tr.check(ur.upload_time_ms == 150.5, "upload_time_ms == 150.5")
    tr.check(ur.error_message is None, "error_message 기본값 None")

    # 기본값 검증
    ur2 = UploadResult(success=False, key="fail.mp4")
    tr.check(ur2.url is None, "url 기본값 None")
    tr.check(ur2.etag is None, "etag 기본값 None")
    tr.check(ur2.version_id is None, "version_id 기본값 None")
    tr.check(ur2.upload_time_ms == 0.0, "upload_time_ms 기본값 0.0")

    # success_result 팩토리
    sr = UploadResult.success_result(
        key="game.mp4", url="https://s3/game.mp4", etag="e1", version_id="v2",
        upload_time_ms=200.0,
    )
    tr.check(sr.success is True, "success_result → success == True")
    tr.check(sr.key == "game.mp4", "success_result → key")
    tr.check(sr.url == "https://s3/game.mp4", "success_result → url")
    tr.check(sr.etag == "e1", "success_result → etag")
    tr.check(sr.version_id == "v2", "success_result → version_id")
    tr.check(sr.upload_time_ms == 200.0, "success_result → upload_time_ms")
    tr.check(sr.error_message is None, "success_result → error_message None")

    # failure_result 팩토리
    fr = UploadResult.failure_result(key="bad.mp4", error_message="Timeout")
    tr.check(fr.success is False, "failure_result → success == False")
    tr.check(fr.key == "bad.mp4", "failure_result → key")
    tr.check(fr.error_message == "Timeout", "failure_result → error_message")
    tr.check(fr.url is None, "failure_result → url None")


def test_download_result(tr: TestResult) -> None:
    """[H] DownloadResult 데이터클래스 검증."""
    tr.set_section("[H] DownloadResult 데이터클래스")

    now = datetime.now(timezone.utc)
    fm = FileMetadata(key="vid.mp4", size_bytes=500, content_type="video/mp4",
                      last_modified=now)

    dr = DownloadResult(success=True, key="vid.mp4", data=b"\x00\x01",
                        local_path="/tmp/vid.mp4", metadata=fm, download_time_ms=50.0)
    tr.check(dr.success is True, "success == True")
    tr.check(dr.key == "vid.mp4", "key 설정")
    tr.check(dr.data == b"\x00\x01", "data 설정")
    tr.check(dr.local_path == "/tmp/vid.mp4", "local_path 설정")
    tr.check(dr.metadata is fm, "metadata 설정")
    tr.check(dr.download_time_ms == 50.0, "download_time_ms 설정")

    # 기본값
    dr2 = DownloadResult(success=False, key="x")
    tr.check(dr2.data is None, "data 기본값 None")
    tr.check(dr2.local_path is None, "local_path 기본값 None")
    tr.check(dr2.metadata is None, "metadata 기본값 None")
    tr.check(dr2.error_message is None, "error_message 기본값 None")
    tr.check(dr2.download_time_ms == 0.0, "download_time_ms 기본값 0.0")

    # success_result
    sr = DownloadResult.success_result(key="ok.mp4", data=b"data", local_path="/tmp/ok.mp4",
                                        metadata=fm, download_time_ms=30.0)
    tr.check(sr.success is True, "success_result → success True")
    tr.check(sr.key == "ok.mp4", "success_result → key")
    tr.check(sr.data == b"data", "success_result → data")
    tr.check(sr.local_path == "/tmp/ok.mp4", "success_result → local_path")
    tr.check(sr.download_time_ms == 30.0, "success_result → download_time_ms")

    # failure_result
    fr = DownloadResult.failure_result(key="err.mp4", error_message="Not found")
    tr.check(fr.success is False, "failure_result → success False")
    tr.check(fr.error_message == "Not found", "failure_result → error_message")
    tr.check(fr.data is None, "failure_result → data None")


def test_storage_metrics(tr: TestResult) -> None:
    """[I] StorageMetrics 데이터클래스 검증."""
    tr.set_section("[I] StorageMetrics 데이터클래스")

    sm = StorageMetrics()
    tr.check(sm.total_uploads == 0, "초기 total_uploads == 0")
    tr.check(sm.total_downloads == 0, "초기 total_downloads == 0")
    tr.check(sm.total_bytes_uploaded == 0, "초기 total_bytes_uploaded == 0")
    tr.check(sm.total_bytes_downloaded == 0, "초기 total_bytes_downloaded == 0")
    tr.check(sm.failed_operations == 0, "초기 failed_operations == 0")
    tr.check(sm.average_upload_time_ms == 0.0, "초기 average_upload_time_ms == 0.0")
    tr.check(sm.average_download_time_ms == 0.0, "초기 average_download_time_ms == 0.0")
    tr.check(sm.last_error is None, "초기 last_error None")
    tr.check(sm.last_error_time is None, "초기 last_error_time None")
    tr.check(sm.total_mb_uploaded == 0.0, "초기 total_mb_uploaded == 0.0")
    tr.check(sm.total_mb_downloaded == 0.0, "초기 total_mb_downloaded == 0.0")

    # 성공 업로드 기록
    ur_ok = UploadResult.success_result(key="a.mp4", upload_time_ms=100.0)
    sm.record_upload(ur_ok, 1048576)  # 1MB
    tr.check(sm.total_uploads == 1, "업로드 1회 후 total_uploads == 1")
    tr.check(sm.total_bytes_uploaded == 1048576, "업로드 bytes 기록")
    tr.check(abs(sm.average_upload_time_ms - 100.0) < 0.01, "평균 업로드 시간 100ms")
    tr.check(sm.failed_operations == 0, "성공 업로드 → failed_operations 변동 없음")

    # 두 번째 성공 업로드 (이동 평균 검증)
    ur_ok2 = UploadResult.success_result(key="b.mp4", upload_time_ms=200.0)
    sm.record_upload(ur_ok2, 2097152)  # 2MB
    tr.check(sm.total_uploads == 2, "업로드 2회 후 total_uploads == 2")
    tr.check(sm.total_bytes_uploaded == 1048576 + 2097152, "누적 bytes 합산")
    tr.check(abs(sm.average_upload_time_ms - 150.0) < 0.01, "이동 평균 업로드 시간 150ms")

    # total_mb_uploaded 검증
    expected_mb = (1048576 + 2097152) / (1024 * 1024)
    tr.check(abs(sm.total_mb_uploaded - expected_mb) < 0.001, f"total_mb_uploaded == {expected_mb}")

    # 실패 업로드 기록
    ur_fail = UploadResult.failure_result(key="c.mp4", error_message="Disk full")
    sm.record_upload(ur_fail, 0)
    tr.check(sm.total_uploads == 3, "실패 포함 total_uploads == 3")
    tr.check(sm.failed_operations == 1, "실패 업로드 → failed_operations == 1")
    tr.check(sm.last_error == "Disk full", "last_error == 'Disk full'")
    tr.check(sm.last_error_time is not None, "last_error_time 설정됨")

    # 성공 다운로드 기록
    dr_ok = DownloadResult.success_result(key="d.mp4", download_time_ms=50.0)
    sm.record_download(dr_ok, 524288)  # 0.5MB
    tr.check(sm.total_downloads == 1, "다운로드 1회 후 total_downloads == 1")
    tr.check(sm.total_bytes_downloaded == 524288, "다운로드 bytes 기록")
    tr.check(abs(sm.average_download_time_ms - 50.0) < 0.01, "평균 다운로드 시간 50ms")

    # 실패 다운로드 기록
    dr_fail = DownloadResult.failure_result(key="e.mp4", error_message="Timeout")
    sm.record_download(dr_fail, 0)
    tr.check(sm.total_downloads == 2, "실패 포함 total_downloads == 2")
    tr.check(sm.failed_operations == 2, "누적 failed_operations == 2")
    tr.check(sm.last_error == "Timeout", "다운로드 실패 후 last_error == 'Timeout'")

    # total_mb_downloaded
    expected_dl_mb = 524288 / (1024 * 1024)
    tr.check(abs(sm.total_mb_downloaded - expected_dl_mb) < 0.001,
             f"total_mb_downloaded == {expected_dl_mb}")


def test_video_metadata(tr: TestResult) -> None:
    """[J] VideoMetadata 데이터클래스 검증."""
    tr.set_section("[J] VideoMetadata 데이터클래스")

    now = datetime.now(timezone.utc)
    vm = VideoMetadata(
        key="games/final.mp4", size_bytes=104857600, content_type="video/mp4",
        last_modified=now, duration_seconds=120.5, width=1920, height=1080,
        fps=30.0, codec="h264", bitrate_kbps=5000, total_frames=3615,
    )

    # FileMetadata 상속 검증
    tr.check(isinstance(vm, FileMetadata), "VideoMetadata는 FileMetadata 상속")
    tr.check(vm.key == "games/final.mp4", "key 상속 필드")
    tr.check(vm.size_bytes == 104857600, "size_bytes 상속 필드")
    tr.check(vm.extension == ".mp4", "extension 상속 프로퍼티")
    tr.check(vm.filename == "final.mp4", "filename 상속 프로퍼티")

    # 비디오 전용 필드
    tr.check(vm.duration_seconds == 120.5, "duration_seconds 설정")
    tr.check(vm.width == 1920, "width 설정")
    tr.check(vm.height == 1080, "height 설정")
    tr.check(vm.fps == 30.0, "fps 설정")
    tr.check(vm.codec == "h264", "codec 설정")
    tr.check(vm.bitrate_kbps == 5000, "bitrate_kbps 설정")
    tr.check(vm.total_frames == 3615, "total_frames 설정")

    # aspect_ratio
    expected_ratio = 1920 / 1080
    tr.check(abs(vm.aspect_ratio - expected_ratio) < 0.001,
             f"aspect_ratio == {expected_ratio:.4f}")

    # resolution
    tr.check(vm.resolution == "1920x1080", "resolution == '1920x1080'")

    # 기본값 검증
    vm2 = VideoMetadata(key="x.mp4", size_bytes=0, content_type="video/mp4",
                        last_modified=now)
    tr.check(vm2.duration_seconds == 0.0, "기본 duration_seconds == 0.0")
    tr.check(vm2.width == 0, "기본 width == 0")
    tr.check(vm2.height == 0, "기본 height == 0")
    tr.check(vm2.fps == 0.0, "기본 fps == 0.0")
    tr.check(vm2.codec is None, "기본 codec None")
    tr.check(vm2.bitrate_kbps is None, "기본 bitrate_kbps None")
    tr.check(vm2.total_frames == 0, "기본 total_frames == 0")

    # height=0 → aspect_ratio=0.0
    tr.check(vm2.aspect_ratio == 0.0, "height=0 → aspect_ratio == 0.0")
    tr.check(vm2.resolution == "0x0", "기본 resolution == '0x0'")


def test_cache_entry(tr: TestResult) -> None:
    """[K] CacheEntry 데이터클래스 검증."""
    tr.set_section("[K] CacheEntry 데이터클래스")

    now = datetime.now(timezone.utc)

    # 만료되지 않은 캐시 (미래 만료)
    future = now + timedelta(hours=1)
    ce = CacheEntry(key="cache:user:1", value={"name": "test"}, created_at=now,
                    expires_at=future, access_count=5, last_accessed=now)
    tr.check(ce.key == "cache:user:1", "key 설정")
    tr.check(ce.value == {"name": "test"}, "value 설정")
    tr.check(ce.created_at == now, "created_at 설정")
    tr.check(ce.expires_at == future, "expires_at 설정")
    tr.check(ce.access_count == 5, "access_count 설정")
    tr.check(ce.last_accessed == now, "last_accessed 설정")
    tr.check(ce.is_expired is False, "미래 만료 → is_expired == False")
    tr.check(ce.ttl_seconds is not None, "미래 만료 → ttl_seconds != None")
    tr.check(ce.ttl_seconds > 0, "미래 만료 → ttl_seconds > 0")

    # 만료된 캐시 (과거 만료)
    past = now - timedelta(hours=1)
    ce2 = CacheEntry(key="cache:old", value="stale", created_at=now - timedelta(hours=2),
                     expires_at=past)
    tr.check(ce2.is_expired is True, "과거 만료 → is_expired == True")
    tr.check(ce2.ttl_seconds == 0.0, "과거 만료 → ttl_seconds == 0.0")

    # 만료 없는 캐시
    ce3 = CacheEntry(key="cache:perm", value=42, created_at=now, expires_at=None)
    tr.check(ce3.is_expired is False, "expires_at=None → is_expired == False")
    tr.check(ce3.ttl_seconds is None, "expires_at=None → ttl_seconds == None")

    # 기본값
    ce4 = CacheEntry(key="k", value="v", created_at=now)
    tr.check(ce4.expires_at is None, "기본 expires_at None")
    tr.check(ce4.access_count == 0, "기본 access_count == 0")
    tr.check(ce4.last_accessed is None, "기본 last_accessed None")


def test_analysis_result_entry(tr: TestResult) -> None:
    """[L] AnalysisResultEntry 데이터클래스 검증."""
    tr.set_section("[L] AnalysisResultEntry 데이터클래스")

    before = datetime.now(timezone.utc)
    entry = AnalysisResultEntry(
        session_id="sess_001",
        analysis_type="training",
        user_id="user_123",
        video_key="videos/train.mp4",
        result_data={"score": 85.5, "feedback": ["좋은 폼"]},
    )
    after = datetime.now(timezone.utc)

    tr.check(entry.session_id == "sess_001", "session_id 설정")
    tr.check(entry.analysis_type == "training", "analysis_type 설정")
    tr.check(entry.user_id == "user_123", "user_id 설정")
    tr.check(entry.video_key == "videos/train.mp4", "video_key 설정")
    tr.check(entry.result_data == {"score": 85.5, "feedback": ["좋은 폼"]}, "result_data 설정")

    # created_at 자동 설정 검증 (timezone-aware)
    tr.check(entry.created_at.tzinfo is not None, "created_at에 timezone 정보 존재")
    tr.check(before <= entry.created_at <= after, "created_at 범위 내 자동 생성")

    # metadata 기본값
    tr.check(entry.metadata == {}, "metadata 기본값 빈 딕셔너리")

    # 사용자 지정 created_at
    custom_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    entry2 = AnalysisResultEntry(
        session_id="s2", analysis_type="game", user_id="u2",
        video_key="v2.mp4", result_data={}, created_at=custom_time,
        metadata={"court": "indoor"},
    )
    tr.check(entry2.created_at == custom_time, "사용자 지정 created_at 유지")
    tr.check(entry2.metadata == {"court": "indoor"}, "사용자 지정 metadata 유지")


def test_sort_criteria(tr: TestResult) -> None:
    """[M] SortCriteria 데이터클래스 검증."""
    tr.set_section("[M] SortCriteria 데이터클래스")

    sc = SortCriteria(field="created_at", order=SortOrder.DESC)
    tr.check(sc.field == "created_at", "field 설정")
    tr.check(sc.order == SortOrder.DESC, "order 설정")

    # 기본 order = ASC
    sc2 = SortCriteria(field="name")
    tr.check(sc2.order == SortOrder.ASC, "기본 order == ASC")


def test_pagination_params(tr: TestResult) -> None:
    """[N] PaginationParams 데이터클래스 검증."""
    tr.set_section("[N] PaginationParams 데이터클래스")

    pp = PaginationParams(page=3, page_size=25)
    tr.check(pp.page == 3, "page 설정")
    tr.check(pp.page_size == 25, "page_size 설정")
    tr.check(pp.offset == (3 - 1) * 25, f"offset == {(3-1)*25}")
    tr.check(pp.limit == 25, "limit == page_size")

    # 기본값
    pp2 = PaginationParams()
    tr.check(pp2.page == 1, "기본 page == 1")
    tr.check(pp2.page_size == 20, "기본 page_size == 20")
    tr.check(pp2.offset == 0, "기본 offset == 0")
    tr.check(pp2.limit == 20, "기본 limit == 20")

    # page=1
    pp3 = PaginationParams(page=1, page_size=10)
    tr.check(pp3.offset == 0, "page=1 → offset == 0")


def test_paginated_result(tr: TestResult) -> None:
    """[O] PaginatedResult 데이터클래스 검증."""
    tr.set_section("[O] PaginatedResult 데이터클래스")

    # 일반 경우
    pr = PaginatedResult(items=["a", "b", "c"], total_count=10, page=1, page_size=3)
    tr.check(pr.items == ["a", "b", "c"], "items 설정")
    tr.check(pr.total_count == 10, "total_count 설정")
    tr.check(pr.page == 1, "page 설정")
    tr.check(pr.page_size == 3, "page_size 설정")
    tr.check(pr.total_pages == 4, "total_pages == ceil(10/3) == 4")
    tr.check(pr.has_next is True, "page=1, total_pages=4 → has_next True")
    tr.check(pr.has_previous is False, "page=1 → has_previous False")
    tr.check(pr.is_empty is False, "3개 아이템 → is_empty False")

    # 마지막 페이지
    pr2 = PaginatedResult(items=["x"], total_count=10, page=4, page_size=3)
    tr.check(pr2.has_next is False, "마지막 페이지 → has_next False")
    tr.check(pr2.has_previous is True, "page=4 → has_previous True")

    # 중간 페이지
    pr3 = PaginatedResult(items=["a", "b", "c"], total_count=10, page=2, page_size=3)
    tr.check(pr3.has_next is True, "중간 페이지 → has_next True")
    tr.check(pr3.has_previous is True, "중간 페이지 → has_previous True")

    # 빈 결과
    pr4 = PaginatedResult(items=[], total_count=0, page=1, page_size=20)
    tr.check(pr4.is_empty is True, "빈 아이템 → is_empty True")
    tr.check(pr4.total_pages == 0, "total_count=0 → total_pages == 0")
    tr.check(pr4.has_next is False, "빈 결과 → has_next False")
    tr.check(pr4.has_previous is False, "빈 결과 → has_previous False")

    # page_size=0 엣지 케이스
    pr5 = PaginatedResult(items=[], total_count=10, page=1, page_size=0)
    tr.check(pr5.total_pages == 0, "page_size=0 → total_pages == 0")

    # 정확히 나누어 떨어지는 경우
    pr6 = PaginatedResult(items=list(range(5)), total_count=15, page=1, page_size=5)
    tr.check(pr6.total_pages == 3, "15/5 = 3 페이지")


def test_filter_criteria(tr: TestResult) -> None:
    """[P] FilterCriteria 데이터클래스 검증."""
    tr.set_section("[P] FilterCriteria 데이터클래스")

    # 유효한 연산자 모두 테스트
    valid_ops = [
        "eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in",
        "contains", "startswith", "endswith", "is_null", "is_not_null", "between",
    ]
    tr.check(FilterCriteria.VALID_OPERATORS == valid_ops,
             f"VALID_OPERATORS 14개 일치")
    tr.check(len(FilterCriteria.VALID_OPERATORS) == 14,
             "VALID_OPERATORS 14개")

    for op in valid_ops:
        fc = FilterCriteria(field="name", operator=op, value="test")
        tr.check(fc.operator == op, f"유효 연산자 '{op}' 생성 성공")

    # 기본 필드 검증
    fc = FilterCriteria(field="status", operator="eq", value="active")
    tr.check(fc.field == "status", "field 설정")
    tr.check(fc.operator == "eq", "operator 설정")
    tr.check(fc.value == "active", "value 설정")

    # between 연산자
    fc_between = FilterCriteria(field="score", operator="between", value=[70, 100])
    tr.check(fc_between.value == [70, 100], "between value 리스트")

    # 잘못된 연산자 → ValueError
    raised = False
    try:
        FilterCriteria(field="x", operator="invalid_op", value=1)
    except ValueError as e:
        raised = True
        tr.check("지원되지 않는 연산자" in str(e), "ValueError 메시지에 '지원되지 않는 연산자' 포함")
    tr.check(raised, "잘못된 연산자 → ValueError 발생")

    raised2 = False
    try:
        FilterCriteria(field="x", operator="like", value="test")
    except ValueError:
        raised2 = True
    tr.check(raised2, "'like' 연산자 → ValueError 발생")


def test_query_options(tr: TestResult) -> None:
    """[Q] QueryOptions 데이터클래스 검증."""
    tr.set_section("[Q] QueryOptions 데이터클래스")

    # 기본값
    qo = QueryOptions()
    tr.check(qo.filters == [], "기본 filters 빈 리스트")
    tr.check(qo.sort == [], "기본 sort 빈 리스트")
    tr.check(qo.pagination is None, "기본 pagination None")
    tr.check(qo.include_deleted is False, "기본 include_deleted False")
    tr.check(qo.select_fields is None, "기본 select_fields None")

    # add_filter 체이닝
    result = qo.add_filter("name", "eq", "홍길동")
    tr.check(result is qo, "add_filter 체이닝 반환 self")
    tr.check(len(qo.filters) == 1, "add_filter 후 filters 1개")
    tr.check(qo.filters[0].field == "name", "add_filter 필드 확인")
    tr.check(qo.filters[0].operator == "eq", "add_filter 연산자 확인")
    tr.check(qo.filters[0].value == "홍길동", "add_filter 값 확인")

    # 연속 체이닝
    qo.add_filter("age", "gte", 18).add_filter("status", "eq", "active")
    tr.check(len(qo.filters) == 3, "연속 체이닝 후 filters 3개")

    # add_sort 체이닝
    qo2 = QueryOptions()
    result2 = qo2.add_sort("created_at", SortOrder.DESC)
    tr.check(result2 is qo2, "add_sort 체이닝 반환 self")
    tr.check(len(qo2.sort) == 1, "add_sort 후 sort 1개")
    tr.check(qo2.sort[0].field == "created_at", "add_sort 필드 확인")
    tr.check(qo2.sort[0].order == SortOrder.DESC, "add_sort 순서 확인")

    # add_sort 기본 정렬
    qo2.add_sort("name")
    tr.check(qo2.sort[1].order == SortOrder.ASC, "add_sort 기본 순서 ASC")

    # with_pagination 체이닝
    qo3 = QueryOptions()
    result3 = qo3.with_pagination(page=2, page_size=50)
    tr.check(result3 is qo3, "with_pagination 체이닝 반환 self")
    tr.check(qo3.pagination is not None, "with_pagination 후 pagination 설정")
    tr.check(qo3.pagination.page == 2, "with_pagination page 설정")
    tr.check(qo3.pagination.page_size == 50, "with_pagination page_size 설정")

    # 전체 체이닝 조합
    qo4 = (QueryOptions()
           .add_filter("type", "eq", "game")
           .add_sort("date", SortOrder.DESC)
           .with_pagination(page=1, page_size=10))
    tr.check(len(qo4.filters) == 1, "복합 체이닝 filters 1개")
    tr.check(len(qo4.sort) == 1, "복합 체이닝 sort 1개")
    tr.check(qo4.pagination is not None, "복합 체이닝 pagination 설정")


def test_repository_metrics(tr: TestResult) -> None:
    """[R] RepositoryMetrics 데이터클래스 검증."""
    tr.set_section("[R] RepositoryMetrics 데이터클래스")

    rm = RepositoryMetrics()
    tr.check(rm.total_queries == 0, "초기 total_queries == 0")
    tr.check(rm.total_creates == 0, "초기 total_creates == 0")
    tr.check(rm.total_updates == 0, "초기 total_updates == 0")
    tr.check(rm.total_deletes == 0, "초기 total_deletes == 0")
    tr.check(rm.failed_operations == 0, "초기 failed_operations == 0")
    tr.check(rm.average_query_time_ms == 0.0, "초기 average_query_time_ms == 0.0")
    tr.check(rm.total_query_time_ms == 0.0, "초기 total_query_time_ms == 0.0")
    tr.check(rm.last_error is None, "초기 last_error None")
    tr.check(rm.last_error_time is None, "초기 last_error_time None")

    # record_query 성공
    rm.record_query(50.0, success=True)
    tr.check(rm.total_queries == 1, "record_query 후 total_queries == 1")
    tr.check(rm.total_query_time_ms == 50.0, "record_query 후 total_query_time_ms == 50.0")
    tr.check(abs(rm.average_query_time_ms - 50.0) < 0.01, "평균 쿼리 시간 50ms")
    tr.check(rm.failed_operations == 0, "성공 쿼리 → failed 변동 없음")

    # record_query 두 번째 (평균 갱신)
    rm.record_query(100.0, success=True)
    tr.check(rm.total_queries == 2, "2회 쿼리 후 total_queries == 2")
    tr.check(abs(rm.average_query_time_ms - 75.0) < 0.01, "평균 쿼리 시간 75ms")

    # record_query 실패
    rm.record_query(30.0, success=False)
    tr.check(rm.total_queries == 3, "실패 포함 total_queries == 3")
    tr.check(rm.failed_operations == 1, "실패 쿼리 → failed_operations == 1")

    # record_create 성공/실패
    rm.record_create(success=True)
    tr.check(rm.total_creates == 1, "record_create 후 total_creates == 1")
    tr.check(rm.failed_operations == 1, "성공 create → failed 변동 없음")

    rm.record_create(success=False)
    tr.check(rm.total_creates == 2, "실패 create 포함 total_creates == 2")
    tr.check(rm.failed_operations == 2, "실패 create → failed_operations == 2")

    # record_update 성공/실패
    rm.record_update(success=True)
    tr.check(rm.total_updates == 1, "record_update 후 total_updates == 1")

    rm.record_update(success=False)
    tr.check(rm.total_updates == 2, "실패 update 포함 total_updates == 2")
    tr.check(rm.failed_operations == 3, "실패 update → failed_operations == 3")

    # record_delete 성공/실패
    rm.record_delete(success=True)
    tr.check(rm.total_deletes == 1, "record_delete 후 total_deletes == 1")

    rm.record_delete(success=False)
    tr.check(rm.total_deletes == 2, "실패 delete 포함 total_deletes == 2")
    tr.check(rm.failed_operations == 4, "실패 delete → failed_operations == 4")

    # record_error
    rm.record_error("Connection lost")
    tr.check(rm.failed_operations == 5, "record_error → failed_operations == 5")
    tr.check(rm.last_error == "Connection lost", "record_error → last_error 설정")
    tr.check(rm.last_error_time is not None, "record_error → last_error_time 설정")
    tr.check(rm.last_error_time.tzinfo is not None, "last_error_time timezone-aware")


def test_abc_storage(tr: TestResult) -> None:
    """[S] IStorage ABC 스텁 검증."""
    tr.set_section("[S] IStorage ABC 검증")

    tr.check(issubclass(IStorage, ABC), "IStorage는 ABC 상속")

    stub = StubStorage()
    tr.check(isinstance(stub, IStorage), "StubStorage는 IStorage 인스턴스")
    tr.check(stub.storage_type == StorageType.LOCAL, "storage_type 프로퍼티 반환")
    tr.check(stub.state == StorageState.CONNECTED, "state 프로퍼티 반환")
    tr.check(isinstance(stub.metrics, StorageMetrics), "metrics 프로퍼티 반환")

    stub.connect({})
    tr.check(stub.state == StorageState.CONNECTED, "connect 후 CONNECTED")

    stub.disconnect()
    tr.check(stub.state == StorageState.DISCONNECTED, "disconnect 후 DISCONNECTED")

    # upload
    ur = stub.upload("key.mp4", b"data")
    tr.check(isinstance(ur, UploadResult), "upload 반환 UploadResult")
    tr.check(ur.success is True, "upload 성공")

    # download
    dr = stub.download("key.mp4")
    tr.check(isinstance(dr, DownloadResult), "download 반환 DownloadResult")

    # download_to_file
    dr2 = stub.download_to_file("key.mp4", "/tmp/key.mp4")
    tr.check(isinstance(dr2, DownloadResult), "download_to_file 반환 DownloadResult")

    # exists / delete
    tr.check(stub.exists("key.mp4") is True, "exists 반환 bool")
    tr.check(stub.delete("key.mp4") is True, "delete 반환 bool")

    # get_metadata
    md = stub.get_metadata("key.mp4")
    tr.check(isinstance(md, FileMetadata), "get_metadata 반환 FileMetadata")

    # list_files
    files = stub.list_files(prefix="test/")
    tr.check(isinstance(files, list), "list_files 반환 list")

    # get_signed_url
    url = stub.get_signed_url("key.mp4")
    tr.check(isinstance(url, str), "get_signed_url 반환 str")


def test_abc_video_storage(tr: TestResult) -> None:
    """[T] IVideoStorage ABC 스텁 검증."""
    tr.set_section("[T] IVideoStorage ABC 검증")

    tr.check(issubclass(IVideoStorage, IStorage), "IVideoStorage는 IStorage 상속")

    stub = StubVideoStorage()
    tr.check(isinstance(stub, IVideoStorage), "StubVideoStorage는 IVideoStorage 인스턴스")
    tr.check(isinstance(stub, IStorage), "StubVideoStorage는 IStorage 인스턴스")

    # 비디오 전용 메서드
    ur = stub.upload_video("vid.mp4", "/local/vid.mp4")
    tr.check(isinstance(ur, UploadResult), "upload_video 반환 UploadResult")

    vm = stub.get_video_metadata("vid.mp4")
    tr.check(isinstance(vm, VideoMetadata), "get_video_metadata 반환 VideoMetadata")

    frames = stub.extract_frames("vid.mp4", "/tmp/frames")
    tr.check(isinstance(frames, list), "extract_frames 반환 list")
    tr.check(len(frames) > 0, "extract_frames 비어있지 않음")

    # stream_frames (Iterator)
    gen = stub.stream_frames("vid.mp4")
    batch = next(gen)
    tr.check(isinstance(batch, list), "stream_frames 배치 = list")
    tr.check(isinstance(batch[0], np.ndarray), "stream_frames 배치 원소 = np.ndarray")

    # get_streaming_url
    surl = stub.get_streaming_url("vid.mp4")
    tr.check(isinstance(surl, str), "get_streaming_url 반환 str")


def test_abc_cache(tr: TestResult) -> None:
    """[U] ICache ABC 스텁 검증."""
    tr.set_section("[U] ICache ABC 검증")

    tr.check(issubclass(ICache, ABC), "ICache는 ABC 상속")

    stub = StubCache()
    tr.check(isinstance(stub, ICache), "StubCache는 ICache 인스턴스")
    tr.check(stub.state == StorageState.CONNECTED, "state 프로퍼티")

    stub.connect({})
    stub.set("key1", "value1")
    tr.check(stub.get("key1") == "value1", "set/get 정상 동작")
    tr.check(stub.exists("key1") is True, "exists 정상 동작")

    stub.delete("key1")
    tr.check(stub.exists("key1") is False, "delete 후 exists False")

    stub.set_many({"a": 1, "b": 2})
    result = stub.get_many(["a", "b", "c"])
    tr.check(result == {"a": 1, "b": 2}, "set_many/get_many 정상 동작")

    count = stub.clear()
    tr.check(count == 2, "clear 반환 삭제 수")

    stub.incr("counter", 5)
    tr.check(stub.get("counter") == 5, "incr 정상 동작")

    stub.decr("counter", 3)
    tr.check(stub.get("counter") == 2, "decr 정상 동작")

    stub.disconnect()
    tr.check(stub.state == StorageState.DISCONNECTED, "disconnect 후 DISCONNECTED")


def test_abc_analysis_result_storage(tr: TestResult) -> None:
    """[V] IAnalysisResultStorage ABC 스텁 검증."""
    tr.set_section("[V] IAnalysisResultStorage ABC 검증")

    tr.check(issubclass(IAnalysisResultStorage, ABC), "IAnalysisResultStorage는 ABC 상속")

    stub = StubAnalysisResultStorage()
    tr.check(isinstance(stub, IAnalysisResultStorage), "스텁 인스턴스 확인")

    stub.connect({})

    entry = AnalysisResultEntry(
        session_id="s1", analysis_type="training", user_id="u1",
        video_key="v1.mp4", result_data={"score": 90},
    )
    rid = stub.save_result(entry)
    tr.check(isinstance(rid, str), "save_result 반환 str")

    got = stub.get_result(rid)
    tr.check(got is entry, "get_result 반환 저장된 항목")

    by_user = stub.get_results_by_user("u1")
    tr.check(len(by_user) == 1, "get_results_by_user 반환 1개")

    by_session = stub.get_results_by_session("s1")
    tr.check(len(by_session) == 1, "get_results_by_session 반환 1개")

    stats = stub.get_statistics("u1")
    tr.check(isinstance(stats, dict), "get_statistics 반환 dict")
    tr.check(stats.get("total") == 1, "get_statistics total == 1")

    deleted = stub.delete_result(rid)
    tr.check(deleted is True, "delete_result 성공")
    tr.check(stub.get_result(rid) is None, "삭제 후 get_result None")

    stub.disconnect()


def test_abc_repository(tr: TestResult) -> None:
    """[W] IRepository ABC 스텁 검증."""
    tr.set_section("[W] IRepository ABC 검증")

    tr.check(issubclass(IRepository, ABC), "IRepository는 ABC 상속")

    repo = StubRepository()
    tr.check(isinstance(repo, IRepository), "StubRepository는 IRepository 인스턴스")
    tr.check(repo.entity_name == "FakeEntity", "entity_name 프로퍼티")
    tr.check(isinstance(repo.metrics, RepositoryMetrics), "metrics 프로퍼티")

    # create
    e1 = repo.create(_FakeEntity(name="Alice"))
    tr.check(e1.id != "", "create 후 ID 할당")
    tr.check(e1.name == "Alice", "create 후 name 유지")

    # get_by_id
    got = repo.get_by_id(e1.id)
    tr.check(got is e1, "get_by_id 정상 반환")

    # get_all
    all_items = repo.get_all()
    tr.check(len(all_items) == 1, "get_all 1개 반환")

    # update
    e1.name = "Alice Updated"
    updated = repo.update(e1)
    tr.check(updated.name == "Alice Updated", "update 반영")

    # exists
    tr.check(repo.exists(e1.id) is True, "exists True")
    tr.check(repo.exists("nonexist") is False, "exists False")

    # count
    tr.check(repo.count() == 1, "count == 1")

    # find_one
    opts = QueryOptions().add_filter("name", "eq", "Alice Updated")
    found = repo.find_one(opts)
    tr.check(found is e1, "find_one 정상 반환")

    # find_by_ids
    e2 = repo.create(_FakeEntity(name="Bob"))
    found_many = repo.find_by_ids([e1.id, e2.id])
    tr.check(len(found_many) == 2, "find_by_ids 2개 반환")

    # create_many
    created = repo.create_many([_FakeEntity(name="C"), _FakeEntity(name="D")])
    tr.check(len(created) == 2, "create_many 2개 생성")

    # update_many
    for c in created:
        c.name = c.name + "_updated"
    updated_many = repo.update_many(created)
    tr.check(all("_updated" in u.name for u in updated_many), "update_many 반영")

    # delete_many
    ids_to_del = [c.id for c in created]
    del_count = repo.delete_many(ids_to_del)
    tr.check(del_count == 2, "delete_many 2개 삭제")

    # delete
    tr.check(repo.delete(e1.id) is True, "delete 성공")
    tr.check(repo.get_by_id(e1.id) is None, "삭제 후 get_by_id None")

    # soft_delete (기본 구현은 delete 호출)
    e3 = repo.create(_FakeEntity(name="SoftDel"))
    sd_result = repo.soft_delete(e3.id)
    tr.check(sd_result is True, "soft_delete 기본 구현 → delete 호출")

    # restore (기본 구현은 None 반환)
    restore_result = repo.restore("any_id")
    tr.check(restore_result is None, "restore 기본 구현 → None")

    # transaction
    tx = repo.begin_transaction()
    tr.check(tx is not None, "begin_transaction 반환값 존재")
    repo.commit_transaction(tx)
    repo.rollback_transaction(tx)

    # get_or_create: 기존 존재
    e4 = repo.create(_FakeEntity(name="Existing", email="exist@test.com"))
    got_entity, created_flag = repo.get_or_create(
        _FakeEntity(name="Existing"), lookup_fields=["name"])
    tr.check(got_entity is e4, "get_or_create 기존 엔티티 반환")
    tr.check(created_flag is False, "get_or_create created == False")

    # get_or_create: 신규 생성
    new_entity, created_flag2 = repo.get_or_create(
        _FakeEntity(name="NewOne"), lookup_fields=["name"])
    tr.check(new_entity.name == "NewOne", "get_or_create 신규 생성 name")
    tr.check(created_flag2 is True, "get_or_create created == True")

    # update_or_create: 기존 존재 → 수정
    upd_entity, upd_created = repo.update_or_create(
        _FakeEntity(name="NewOne", email="new@test.com"), lookup_fields=["name"])
    tr.check(upd_created is False, "update_or_create 기존 → created == False")

    # update_or_create: 신규 생성
    upd_entity2, upd_created2 = repo.update_or_create(
        _FakeEntity(name="BrandNew"), lookup_fields=["name"])
    tr.check(upd_created2 is True, "update_or_create 신규 → created == True")


def test_abc_user_repository(tr: TestResult) -> None:
    """[X] IUserRepository ABC 스텁 검증."""
    tr.set_section("[X] IUserRepository ABC 검증")

    tr.check(issubclass(IUserRepository, IRepository), "IUserRepository는 IRepository 상속")

    repo = StubUserRepository()
    tr.check(isinstance(repo, IUserRepository), "StubUserRepository 인스턴스 확인")
    tr.check(isinstance(repo, IRepository), "IRepository 인스턴스이기도 함")

    user = repo.create(_FakeEntity(name="TestUser", email="test@mail.com", username="tuser"))
    tr.check(user.id.startswith("u_"), "사용자 ID 접두사 'u_'")

    # get_by_email
    found_email = repo.get_by_email("test@mail.com")
    tr.check(found_email is user, "get_by_email 정상 반환")
    tr.check(repo.get_by_email("nope@mail.com") is None, "get_by_email 없는 이메일 → None")

    # get_by_username
    found_uname = repo.get_by_username("tuser")
    tr.check(found_uname is user, "get_by_username 정상 반환")
    tr.check(repo.get_by_username("nope") is None, "get_by_username 없는 사용자명 → None")

    # get_active_users
    actives = repo.get_active_users()
    tr.check(len(actives) >= 1, "get_active_users 1명 이상")


def test_abc_video_repository(tr: TestResult) -> None:
    """[Y] IVideoRepository ABC 스텁 검증."""
    tr.set_section("[Y] IVideoRepository ABC 검증")

    tr.check(issubclass(IVideoRepository, IRepository), "IVideoRepository는 IRepository 상속")

    repo = StubVideoRepository()
    tr.check(isinstance(repo, IVideoRepository), "StubVideoRepository 인스턴스 확인")

    vid = repo.create(_FakeEntity(name="user1", status="pending"))
    tr.check(vid.id.startswith("v_"), "비디오 ID 접두사 'v_'")

    # get_by_user_id
    by_user = repo.get_by_user_id("user1")
    tr.check(isinstance(by_user, list), "get_by_user_id 반환 list")

    # get_by_status
    by_status = repo.get_by_status("pending")
    tr.check(isinstance(by_status, list), "get_by_status 반환 list")

    # get_pending_analysis
    pending = repo.get_pending_analysis(limit=5)
    tr.check(isinstance(pending, list), "get_pending_analysis 반환 list")


def test_abc_analysis_repository(tr: TestResult) -> None:
    """[Z] IAnalysisRepository ABC 스텁 검증."""
    tr.set_section("[Z] IAnalysisRepository ABC 검증")

    tr.check(issubclass(IAnalysisRepository, IRepository), "IAnalysisRepository는 IRepository 상속")

    repo = StubAnalysisRepository()
    tr.check(isinstance(repo, IAnalysisRepository), "StubAnalysisRepository 인스턴스 확인")

    ent = repo.create(_FakeEntity(name="analysis1"))
    tr.check(ent.id.startswith("a_"), "분석 ID 접두사 'a_'")

    # 특화 메서드 반환 타입
    by_vid = repo.get_by_video_id("vid1")
    tr.check(isinstance(by_vid, list), "get_by_video_id 반환 list")

    by_ut = repo.get_by_user_and_type("u1", "training")
    tr.check(isinstance(by_ut, list), "get_by_user_and_type 반환 list")

    latest = repo.get_latest_by_user("u1")
    tr.check(isinstance(latest, list), "get_latest_by_user 반환 list")

    stats = repo.get_statistics_by_user("u1")
    tr.check(isinstance(stats, dict), "get_statistics_by_user 반환 dict")


def test_abc_storage_factory(tr: TestResult) -> None:
    """[AA] IStorageFactory ABC 스텁 검증."""
    tr.set_section("[AA] IStorageFactory ABC 검증")

    tr.check(issubclass(IStorageFactory, ABC), "IStorageFactory는 ABC 상속")

    factory = StubStorageFactory()
    tr.check(isinstance(factory, IStorageFactory), "StubStorageFactory 인스턴스 확인")

    # create_storage
    storage = factory.create_storage(StorageType.LOCAL, {})
    tr.check(isinstance(storage, IStorage), "create_storage 반환 IStorage")

    # create_video_storage
    vstorage = factory.create_video_storage(StorageType.S3, {})
    tr.check(isinstance(vstorage, IVideoStorage), "create_video_storage 반환 IVideoStorage")

    # create_cache
    cache = factory.create_cache({})
    tr.check(isinstance(cache, ICache), "create_cache 반환 ICache")


def test_edge_cases(tr: TestResult) -> None:
    """[AB] 엣지 케이스 검증."""
    tr.set_section("[AB] 엣지 케이스")

    # PaginatedResult page_size=0 → total_pages=0
    pr = PaginatedResult(items=[], total_count=100, page=1, page_size=0)
    tr.check(pr.total_pages == 0, "page_size=0 → total_pages == 0")

    # PaginatedResult 빈 아이템
    pr2 = PaginatedResult(items=[], total_count=0, page=1, page_size=10)
    tr.check(pr2.is_empty is True, "빈 아이템 → is_empty True")
    tr.check(pr2.total_pages == 0, "total_count=0 → total_pages == 0")
    tr.check(pr2.has_next is False, "빈 결과 has_next False")
    tr.check(pr2.has_previous is False, "빈 결과 has_previous False")

    # FilterCriteria 모든 14개 유효 연산자
    ops = FilterCriteria.VALID_OPERATORS
    for op in ops:
        try:
            fc = FilterCriteria(field="f", operator=op, value="v")
            tr.check(True, f"유효 연산자 '{op}' 생성 성공 (엣지)")
        except Exception as e:
            tr.check(False, f"유효 연산자 '{op}' 생성 실패", str(e))

    # FilterCriteria 잘못된 연산자
    for bad_op in ["regex", "LIKE", "===", "!=", ""]:
        raised = False
        try:
            FilterCriteria(field="f", operator=bad_op, value="v")
        except ValueError:
            raised = True
        tr.check(raised, f"잘못된 연산자 '{bad_op}' → ValueError")

    # QueryOptions 체이닝 반환값 검증
    qo = QueryOptions()
    r1 = qo.add_filter("a", "eq", 1)
    r2 = r1.add_sort("b")
    r3 = r2.with_pagination(1, 10)
    tr.check(r1 is qo, "add_filter 체이닝 self 반환")
    tr.check(r2 is qo, "add_sort 체이닝 self 반환")
    tr.check(r3 is qo, "with_pagination 체이닝 self 반환")

    # CacheEntry expires_at=None
    now = datetime.now(timezone.utc)
    ce = CacheEntry(key="perm", value="data", created_at=now, expires_at=None)
    tr.check(ce.is_expired is False, "expires_at=None → not expired")
    tr.check(ce.ttl_seconds is None, "expires_at=None → ttl_seconds None")

    # FileMetadata 확장자 없는 경우
    fm = FileMetadata(key="noext", size_bytes=10, content_type="text/plain",
                      last_modified=now)
    tr.check(fm.extension == "", "확장자 없는 key → extension ''")
    tr.check(fm.filename == "noext", "확장자 없는 key → filename 'noext'")

    # ContentType.from_extension 알 수 없는 확장자
    tr.check(ContentType.from_extension("unknown") is None, "알 수 없는 확장자 → None")
    tr.check(ContentType.from_extension("exe") is None, "'exe' → None")
    tr.check(ContentType.from_extension("") is None, "빈 문자열 → None")

    # ContentType.from_extension 대소문자 무관
    tr.check(ContentType.from_extension("MP4") == ContentType.VIDEO_MP4, "'MP4' 대소문자 무관")
    tr.check(ContentType.from_extension("Json") == ContentType.JSON, "'Json' 대소문자 무관")
    tr.check(ContentType.from_extension("PKL") == ContentType.PICKLE, "'PKL' 대소문자 무관")

    # ContentType.from_extension 앞에 점
    tr.check(ContentType.from_extension(".mp4") == ContentType.VIDEO_MP4, "'.mp4' 앞에 점 제거")
    tr.check(ContentType.from_extension(".JSON") == ContentType.JSON, "'.JSON' 점+대소문자")
    tr.check(ContentType.from_extension(".avi") == ContentType.VIDEO_AVI, "'.avi' 점 제거")
    tr.check(ContentType.from_extension(".webp") == ContentType.IMAGE_WEBP, "'.webp' 점 제거")

    # VideoMetadata height=0 aspect_ratio
    vm = VideoMetadata(key="z.mp4", size_bytes=0, content_type="video/mp4",
                       last_modified=now, width=1920, height=0)
    tr.check(vm.aspect_ratio == 0.0, "height=0 → aspect_ratio == 0.0 (0 나누기 방지)")

    # StorageType 상호배타성 (클라우드이면서 로컬이 아닌지)
    for st in StorageType:
        if st.is_cloud:
            tr.check(st.is_local is False, f"{st.name} 클라우드 → 로컬 아님")
        if st.is_local:
            tr.check(st.is_cloud is False, f"{st.name} 로컬 → 클라우드 아님")


# =============================================================================
# 메인 함수
# =============================================================================
def main() -> None:
    """메인 테스트 실행 함수."""
    print("=" * 60)
    print("  storage_interface.py 단위 테스트")
    print("  대상: shared/interfaces/storage_interface.py")
    print(f"  버전: {__version__}")
    print("=" * 60)

    tr = TestResult()

    # [A] 모듈 메타데이터
    test_module_metadata(tr)

    # [B] StorageType 열거형
    test_storage_type_enum(tr)

    # [C] StorageState 열거형
    test_storage_state_enum(tr)

    # [D] ContentType 열거형
    test_content_type_enum(tr)

    # [E] SortOrder 열거형
    test_sort_order_enum(tr)

    # [F] FileMetadata 데이터클래스
    test_file_metadata(tr)

    # [G] UploadResult 데이터클래스
    test_upload_result(tr)

    # [H] DownloadResult 데이터클래스
    test_download_result(tr)

    # [I] StorageMetrics 데이터클래스
    test_storage_metrics(tr)

    # [J] VideoMetadata 데이터클래스
    test_video_metadata(tr)

    # [K] CacheEntry 데이터클래스
    test_cache_entry(tr)

    # [L] AnalysisResultEntry 데이터클래스
    test_analysis_result_entry(tr)

    # [M] SortCriteria 데이터클래스
    test_sort_criteria(tr)

    # [N] PaginationParams 데이터클래스
    test_pagination_params(tr)

    # [O] PaginatedResult 데이터클래스
    test_paginated_result(tr)

    # [P] FilterCriteria 데이터클래스
    test_filter_criteria(tr)

    # [Q] QueryOptions 데이터클래스
    test_query_options(tr)

    # [R] RepositoryMetrics 데이터클래스
    test_repository_metrics(tr)

    # [S] IStorage ABC
    test_abc_storage(tr)

    # [T] IVideoStorage ABC
    test_abc_video_storage(tr)

    # [U] ICache ABC
    test_abc_cache(tr)

    # [V] IAnalysisResultStorage ABC
    test_abc_analysis_result_storage(tr)

    # [W] IRepository ABC
    test_abc_repository(tr)

    # [X] IUserRepository ABC
    test_abc_user_repository(tr)

    # [Y] IVideoRepository ABC
    test_abc_video_repository(tr)

    # [Z] IAnalysisRepository ABC
    test_abc_analysis_repository(tr)

    # [AA] IStorageFactory ABC
    test_abc_storage_factory(tr)

    # [AB] 엣지 케이스
    test_edge_cases(tr)

    # 최종 요약
    success = tr.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
