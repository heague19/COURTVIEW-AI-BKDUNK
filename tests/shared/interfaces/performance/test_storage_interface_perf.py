# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: tests/shared/interfaces/performance
파일: test_storage_interface_perf.py
설명: storage_interface.py 성능 테스트 (Enum, 데이터클래스, ABC 라이프사이클, 벌크 벤치마크)

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16
버전: 1.0.0
"""

# =============================================================================
# 표준 라이브러리
# =============================================================================
import gc
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT))

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
    # 팩토리
    IStorageFactory,
)


# =============================================================================
# 경량 스텁 클래스 (성능 테스트 전용, 외부 import 방지)
# =============================================================================
class _StubStorage(IStorage[dict]):
    """IStorage 경량 스텁 (성능 측정용)."""

    def __init__(self) -> None:
        self._state = StorageState.DISCONNECTED
        self._metrics = StorageMetrics()

    @property
    def storage_type(self) -> StorageType:
        return StorageType.MEMORY

    @property
    def state(self) -> StorageState:
        return self._state

    @property
    def metrics(self) -> StorageMetrics:
        return self._metrics

    def connect(self, config: dict) -> None:
        self._state = StorageState.CONNECTED

    def disconnect(self) -> None:
        self._state = StorageState.DISCONNECTED

    def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        return UploadResult.success_result(key=key, url=f"mem://{key}", upload_time_ms=0.1)

    def download(self, key: str) -> DownloadResult:
        return DownloadResult.success_result(key=key, data=b"stub", download_time_ms=0.1)

    def download_to_file(self, key: str, local_path: str) -> DownloadResult:
        return DownloadResult.success_result(key=key, local_path=local_path)

    def exists(self, key: str) -> bool:
        return True

    def delete(self, key: str) -> bool:
        return True

    def get_metadata(self, key: str) -> FileMetadata | None:
        return FileMetadata(
            key=key,
            size_bytes=1024,
            content_type="application/octet-stream",
            last_modified=datetime.now(timezone.utc),
        )

    def list_files(self, prefix: str = "", max_results: int = 1000) -> list[FileMetadata]:
        return [
            FileMetadata(
                key=f"{prefix}/file_{i}.bin",
                size_bytes=1024 * i,
                content_type="application/octet-stream",
                last_modified=datetime.now(timezone.utc),
            )
            for i in range(min(3, max_results))
        ]

    def get_signed_url(
        self,
        key: str,
        expires_in: timedelta = timedelta(hours=1),
        for_upload: bool = False,
    ) -> str:
        return f"https://signed.example.com/{key}"


# =============================================================================
# 성능 결과 헬퍼
# =============================================================================
class PerfResult:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.section = ""

    def set_section(self, name: str) -> None:
        self.section = name
        print(f"\n{'='*60}\n  {name}\n{'='*60}")

    def ok(self, desc: str) -> None:
        self.passed += 1
        print(f"  [PASS] {desc}")

    def fail(self, desc: str) -> None:
        self.failed += 1
        print(f"  [FAIL] {desc}")

    def info(self, desc: str) -> None:
        print(f"  [INFO] {desc}")

    def check(self, cond: bool, desc: str) -> None:
        if cond:
            self.ok(desc)
        else:
            self.fail(desc)

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}\n  TOTAL: {self.passed}/{total} PASS | {self.failed} FAIL\n{'='*60}")
        return self.failed == 0


# =============================================================================
# 측정 유틸리티
# =============================================================================
def measure(func, iterations: int = 10000, warmup: int = 1000) -> float:
    """함수 평균 실행 시간 측정 (마이크로초 반환)."""
    for _ in range(warmup):
        func()
    gc.disable()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter_ns() - start
    gc.enable()
    return elapsed / iterations / 1000  # 마이크로초


def bench(
    pr: PerfResult,
    func,
    desc: str,
    limit_us: float,
    iterations: int = 10000,
    warmup: int = 1000,
) -> None:
    """벤치마크 실행 및 결과 기록."""
    us = measure(func, iterations, warmup)
    pct = us / limit_us * 100
    pr.info(f"{desc}: {us:.3f}us ({pct:.1f}% of {limit_us}us)")
    pr.check(us < limit_us, f"{desc} < {limit_us}us")


# =============================================================================
# Section 1: StorageType 접근
# =============================================================================
def test_storage_type_access(pr: PerfResult) -> None:
    """StorageType 멤버 접근 성능 벤치마크."""
    pr.set_section("[1] StorageType 접근")

    # 멤버 접근
    bench(pr, lambda: StorageType.LOCAL, "StorageType.LOCAL 멤버 접근", 5.0)

    # .value 접근
    st = StorageType.S3
    bench(pr, lambda: st.value, "StorageType.value 접근", 5.0)

    # str() 변환
    bench(pr, lambda: str(st), "str(StorageType) 변환", 5.0)

    # is_cloud 프로퍼티
    bench(pr, lambda: st.is_cloud, "StorageType.is_cloud 프로퍼티", 5.0)

    # is_local 프로퍼티
    local = StorageType.LOCAL
    bench(pr, lambda: local.is_local, "StorageType.is_local 프로퍼티", 5.0)

    # is_persistent 프로퍼티
    mem = StorageType.MEMORY
    bench(pr, lambda: mem.is_persistent, "StorageType.is_persistent 프로퍼티", 5.0)

    # 전체 멤버 순회 (5개)
    bench(pr, lambda: list(StorageType), "StorageType 전체 순회 (5개)", 5.0)


# =============================================================================
# Section 2: StorageType.get_name
# =============================================================================
def test_storage_type_get_name(pr: PerfResult) -> None:
    """StorageType 다국어 이름 접근 성능 벤치마크."""
    pr.set_section("[2] StorageType.get_name")

    st = StorageType.S3

    # 기본 한국어
    bench(pr, lambda: st.get_name(), "get_name() 기본(KO)", 5.0)

    # 영어
    bench(pr, lambda: st.get_name(SupportedLanguage.EN), "get_name(EN)", 5.0)

    # 일본어
    bench(pr, lambda: st.get_name(SupportedLanguage.JA), "get_name(JA)", 5.0)

    # to_korean 프로퍼티
    bench(pr, lambda: st.to_korean, "to_korean 프로퍼티", 5.0)

    # 전체 멤버 get_name 순회
    bench(
        pr,
        lambda: [m.get_name() for m in StorageType],
        "전체 멤버 get_name 순회 (5개)",
        10.0,
    )


# =============================================================================
# Section 3: StorageState 접근 + get_name
# =============================================================================
def test_storage_state(pr: PerfResult) -> None:
    """StorageState 접근 및 다국어 이름 성능 벤치마크."""
    pr.set_section("[3] StorageState 접근 + get_name")

    ss = StorageState.CONNECTED

    # 멤버 접근
    bench(pr, lambda: StorageState.CONNECTED, "StorageState.CONNECTED 멤버 접근", 5.0)

    # is_connected 프로퍼티
    bench(pr, lambda: ss.is_connected, "is_connected 프로퍼티", 5.0)

    # is_available 프로퍼티
    bench(pr, lambda: ss.is_available, "is_available 프로퍼티", 5.0)

    # is_error 프로퍼티
    err = StorageState.ERROR
    bench(pr, lambda: err.is_error, "is_error 프로퍼티", 5.0)

    # get_name(KO)
    bench(pr, lambda: ss.get_name(SupportedLanguage.KO), "get_name(KO)", 5.0)

    # get_name(EN)
    bench(pr, lambda: ss.get_name(SupportedLanguage.EN), "get_name(EN)", 5.0)

    # 전체 순회
    bench(pr, lambda: list(StorageState), "StorageState 전체 순회 (3개)", 5.0)


# =============================================================================
# Section 4: ContentType 접근
# =============================================================================
def test_content_type_access(pr: PerfResult) -> None:
    """ContentType 멤버 접근 및 프로퍼티 성능 벤치마크."""
    pr.set_section("[4] ContentType 접근")

    ct = ContentType.VIDEO_MP4

    # 멤버 접근
    bench(pr, lambda: ContentType.VIDEO_MP4, "ContentType.VIDEO_MP4 멤버 접근", 5.0)

    # is_video 프로퍼티
    bench(pr, lambda: ct.is_video, "is_video 프로퍼티", 5.0)

    # is_image 프로퍼티
    img = ContentType.IMAGE_JPEG
    bench(pr, lambda: img.is_image, "is_image 프로퍼티", 5.0)

    # is_data 프로퍼티
    js = ContentType.JSON
    bench(pr, lambda: js.is_data, "is_data 프로퍼티", 5.0)

    # extension 프로퍼티
    bench(pr, lambda: ct.extension, "extension 프로퍼티", 5.0)

    # from_extension (유효한 확장자)
    bench(pr, lambda: ContentType.from_extension("mp4"), "from_extension('mp4')", 5.0)

    # from_extension (무효한 확장자 → None)
    bench(pr, lambda: ContentType.from_extension("xyz"), "from_extension('xyz') → None", 5.0)

    # 전체 순회 (11개)
    bench(pr, lambda: list(ContentType), "ContentType 전체 순회 (11개)", 5.0)


# =============================================================================
# Section 5: ContentType.get_name
# =============================================================================
def test_content_type_get_name(pr: PerfResult) -> None:
    """ContentType 다국어 이름 접근 성능 벤치마크."""
    pr.set_section("[5] ContentType.get_name")

    ct = ContentType.IMAGE_PNG

    # get_name(KO)
    bench(pr, lambda: ct.get_name(SupportedLanguage.KO), "get_name(KO)", 5.0)

    # get_name(EN)
    bench(pr, lambda: ct.get_name(SupportedLanguage.EN), "get_name(EN)", 5.0)

    # to_korean 프로퍼티
    bench(pr, lambda: ct.to_korean, "to_korean 프로퍼티", 5.0)

    # 전체 멤버 get_name 순회 (11개)
    bench(
        pr,
        lambda: [m.get_name() for m in ContentType],
        "전체 멤버 get_name 순회 (11개)",
        10.0,
    )


# =============================================================================
# Section 6: SortOrder
# =============================================================================
def test_sort_order(pr: PerfResult) -> None:
    """SortOrder 접근 및 프로퍼티 성능 벤치마크."""
    pr.set_section("[6] SortOrder")

    asc = SortOrder.ASC
    desc = SortOrder.DESC

    # 멤버 접근
    bench(pr, lambda: SortOrder.ASC, "SortOrder.ASC 멤버 접근", 5.0)

    # get_name(KO)
    bench(pr, lambda: asc.get_name(SupportedLanguage.KO), "get_name(KO)", 5.0)

    # get_name(EN)
    bench(pr, lambda: asc.get_name(SupportedLanguage.EN), "get_name(EN)", 5.0)

    # is_ascending 프로퍼티
    bench(pr, lambda: asc.is_ascending, "is_ascending 프로퍼티", 5.0)

    # is_descending 프로퍼티
    bench(pr, lambda: desc.is_descending, "is_descending 프로퍼티", 5.0)

    # reverse() 메서드
    bench(pr, lambda: asc.reverse(), "reverse() 메서드", 5.0)


# =============================================================================
# Section 7: FileMetadata
# =============================================================================
def test_file_metadata(pr: PerfResult) -> None:
    """FileMetadata 생성 및 프로퍼티 성능 벤치마크."""
    pr.set_section("[7] FileMetadata")

    now = datetime.now(timezone.utc)

    # 생성
    bench(
        pr,
        lambda: FileMetadata(
            key="videos/test.mp4",
            size_bytes=104857600,
            content_type="video/mp4",
            last_modified=now,
        ),
        "FileMetadata 생성",
        5.0,
    )

    fm = FileMetadata(
        key="videos/test_video.mp4",
        size_bytes=104857600,  # 100MB
        content_type="video/mp4",
        last_modified=now,
    )

    # size_mb 프로퍼티
    bench(pr, lambda: fm.size_mb, "size_mb 프로퍼티", 5.0)

    # size_gb 프로퍼티
    bench(pr, lambda: fm.size_gb, "size_gb 프로퍼티", 5.0)

    # extension 프로퍼티
    bench(pr, lambda: fm.extension, "extension 프로퍼티", 5.0)

    # filename 프로퍼티
    bench(pr, lambda: fm.filename, "filename 프로퍼티", 5.0)


# =============================================================================
# Section 8: UploadResult + DownloadResult
# =============================================================================
def test_upload_download_result(pr: PerfResult) -> None:
    """UploadResult / DownloadResult 팩토리 및 접근 성능 벤치마크."""
    pr.set_section("[8] UploadResult + DownloadResult")

    # UploadResult.success_result 팩토리
    bench(
        pr,
        lambda: UploadResult.success_result(
            key="upload/test.mp4",
            url="https://s3.example.com/upload/test.mp4",
            etag='"abc123"',
            upload_time_ms=150.5,
        ),
        "UploadResult.success_result 팩토리",
        10.0,
    )

    # UploadResult.failure_result 팩토리
    bench(
        pr,
        lambda: UploadResult.failure_result(
            key="upload/fail.mp4",
            error_message="네트워크 오류",
        ),
        "UploadResult.failure_result 팩토리",
        10.0,
    )

    # DownloadResult.success_result 팩토리
    bench(
        pr,
        lambda: DownloadResult.success_result(
            key="download/test.mp4",
            data=b"sample",
            download_time_ms=200.3,
        ),
        "DownloadResult.success_result 팩토리",
        10.0,
    )

    # DownloadResult.failure_result 팩토리
    bench(
        pr,
        lambda: DownloadResult.failure_result(
            key="download/fail.mp4",
            error_message="파일을 찾을 수 없음",
        ),
        "DownloadResult.failure_result 팩토리",
        10.0,
    )

    # 필드 접근
    ur = UploadResult.success_result(key="k", url="u", etag="e", upload_time_ms=1.0)
    bench(
        pr,
        lambda: (ur.success, ur.key, ur.url, ur.etag, ur.upload_time_ms),
        "UploadResult 필드 접근 (5개)",
        5.0,
    )

    # 최소 생성 (필수 필드만)
    bench(
        pr,
        lambda: UploadResult(success=True, key="minimal"),
        "UploadResult 최소 생성",
        5.0,
    )


# =============================================================================
# Section 9: StorageMetrics
# =============================================================================
def test_storage_metrics(pr: PerfResult) -> None:
    """StorageMetrics 생성 및 기록 성능 벤치마크."""
    pr.set_section("[9] StorageMetrics")

    # 생성
    bench(pr, lambda: StorageMetrics(), "StorageMetrics 생성", 5.0)

    # record_upload (성공)
    sm_ok = StorageMetrics()
    ur_ok = UploadResult.success_result(key="test.mp4", upload_time_ms=50.0)
    bench(
        pr,
        lambda: sm_ok.record_upload(ur_ok, 1024),
        "record_upload (성공)",
        10.0,
    )

    # record_upload (실패)
    sm_fail = StorageMetrics()
    ur_fail = UploadResult.failure_result(key="test.mp4", error_message="실패")
    bench(
        pr,
        lambda: sm_fail.record_upload(ur_fail, 0),
        "record_upload (실패)",
        10.0,
    )

    # record_download (성공)
    sm_dl = StorageMetrics()
    dr_ok = DownloadResult.success_result(key="test.mp4", download_time_ms=30.0)
    bench(
        pr,
        lambda: sm_dl.record_download(dr_ok, 2048),
        "record_download (성공)",
        10.0,
    )

    # 100회 갱신 + 필드 접근
    def _100x_update_and_access():
        m = StorageMetrics()
        ur = UploadResult.success_result(key="x", upload_time_ms=10.0)
        for _ in range(100):
            m.record_upload(ur, 512)
        _ = (
            m.total_uploads, m.total_bytes_uploaded,
            m.average_upload_time_ms, m.total_mb_uploaded,
        )
    bench(pr, _100x_update_and_access, "100x record_upload + 필드 접근", 500.0, iterations=1000, warmup=100)


# =============================================================================
# Section 10: CacheEntry + PaginatedResult
# =============================================================================
def test_cache_entry_paginated(pr: PerfResult) -> None:
    """CacheEntry / PaginatedResult 생성 및 프로퍼티 성능 벤치마크."""
    pr.set_section("[10] CacheEntry + PaginatedResult")

    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=1)

    # CacheEntry 생성
    bench(
        pr,
        lambda: CacheEntry(
            key="cache:user:123",
            value={"name": "test"},
            created_at=now,
            expires_at=exp,
        ),
        "CacheEntry 생성",
        5.0,
    )

    ce = CacheEntry(key="k", value=42, created_at=now, expires_at=exp)

    # is_expired 체크
    bench(pr, lambda: ce.is_expired, "is_expired 프로퍼티", 5.0)

    # ttl_seconds 체크
    bench(pr, lambda: ce.ttl_seconds, "ttl_seconds 프로퍼티", 5.0)

    # PaginatedResult 생성
    items = list(range(20))
    bench(
        pr,
        lambda: PaginatedResult(
            items=items,
            total_count=100,
            page=1,
            page_size=20,
        ),
        "PaginatedResult 생성",
        5.0,
    )

    pr_obj = PaginatedResult(items=items, total_count=100, page=1, page_size=20)

    # total_pages + has_next
    bench(
        pr,
        lambda: (pr_obj.total_pages, pr_obj.has_next, pr_obj.has_previous, pr_obj.is_empty),
        "total_pages + has_next + has_previous + is_empty",
        5.0,
    )


# =============================================================================
# Section 11: FilterCriteria + QueryOptions
# =============================================================================
def test_filter_query_options(pr: PerfResult) -> None:
    """FilterCriteria / QueryOptions 생성 및 체이닝 성능 벤치마크."""
    pr.set_section("[11] FilterCriteria + QueryOptions")

    # FilterCriteria 생성
    bench(
        pr,
        lambda: FilterCriteria(field="name", operator="eq", value="test"),
        "FilterCriteria 생성",
        5.0,
    )

    # 유효 연산자 확인 (VALID_OPERATORS ClassVar 접근)
    fc = FilterCriteria(field="age", operator="gte", value=18)
    bench(
        pr,
        lambda: fc.operator in FilterCriteria.VALID_OPERATORS,
        "VALID_OPERATORS 연산자 포함 확인",
        5.0,
    )

    # QueryOptions 생성
    bench(pr, lambda: QueryOptions(), "QueryOptions 빈 생성", 5.0)

    # add_filter 체이닝
    bench(
        pr,
        lambda: QueryOptions().add_filter("name", "eq", "test"),
        "add_filter 체이닝",
        10.0,
    )

    # add_sort 체이닝
    bench(
        pr,
        lambda: QueryOptions().add_sort("created_at", SortOrder.DESC),
        "add_sort 체이닝",
        10.0,
    )

    # with_pagination 체이닝
    bench(
        pr,
        lambda: QueryOptions().with_pagination(page=2, page_size=50),
        "with_pagination 체이닝",
        10.0,
    )


# =============================================================================
# Section 12: RepositoryMetrics
# =============================================================================
def test_repository_metrics(pr: PerfResult) -> None:
    """RepositoryMetrics 생성 및 기록 성능 벤치마크."""
    pr.set_section("[12] RepositoryMetrics")

    # 생성
    bench(pr, lambda: RepositoryMetrics(), "RepositoryMetrics 생성", 5.0)

    # record_query
    rm_q = RepositoryMetrics()
    bench(pr, lambda: rm_q.record_query(1.5, success=True), "record_query", 10.0)

    # record_create
    rm_c = RepositoryMetrics()
    bench(pr, lambda: rm_c.record_create(success=True), "record_create", 5.0)

    # record_error
    rm_e = RepositoryMetrics()
    bench(pr, lambda: rm_e.record_error("테스트 오류"), "record_error", 10.0)

    # 100회 갱신 + 필드 접근
    def _100x_repo_update():
        m = RepositoryMetrics()
        for _ in range(100):
            m.record_query(2.0)
        _ = (
            m.total_queries, m.average_query_time_ms,
            m.total_query_time_ms, m.failed_operations,
        )
    bench(pr, _100x_repo_update, "100x record_query + 필드 접근", 500.0, iterations=1000, warmup=100)


# =============================================================================
# Section 13: IStorage 라이프사이클
# =============================================================================
def test_storage_lifecycle(pr: PerfResult) -> None:
    """IStorage 스텁 라이프사이클 성능 벤치마크."""
    pr.set_section("[13] IStorage 라이프사이클")

    # _StubStorage 생성
    bench(pr, lambda: _StubStorage(), "_StubStorage 생성", 10.0)

    stub = _StubStorage()

    # connect
    bench(pr, lambda: stub.connect({}), "connect()", 10.0)

    # upload
    bench(
        pr,
        lambda: stub.upload("test.bin", b"data"),
        "upload()",
        10.0,
    )

    # download
    bench(pr, lambda: stub.download("test.bin"), "download()", 10.0)

    # list_files
    bench(pr, lambda: stub.list_files("prefix/"), "list_files()", 10.0)

    # disconnect
    bench(pr, lambda: stub.disconnect(), "disconnect()", 10.0)


# =============================================================================
# Section 14: 벌크 연산
# =============================================================================
def test_bulk_operations(pr: PerfResult) -> None:
    """1000건 벌크 연산 성능 벤치마크."""
    pr.set_section("[14] 벌크 연산 (1000건)")

    now = datetime.now(timezone.utc)

    # 1000x FileMetadata 생성
    def _bulk_file_metadata():
        for i in range(1000):
            FileMetadata(
                key=f"bulk/file_{i}.mp4",
                size_bytes=1024 * i,
                content_type="video/mp4",
                last_modified=now,
            )
    bench(pr, _bulk_file_metadata, "1000x FileMetadata 생성", 20000.0, iterations=100, warmup=10)

    # 1000x UploadResult 생성
    def _bulk_upload_result():
        for i in range(1000):
            UploadResult.success_result(
                key=f"upload/{i}.bin",
                url=f"https://s3.example.com/{i}",
                upload_time_ms=float(i),
            )
    bench(pr, _bulk_upload_result, "1000x UploadResult.success_result", 20000.0, iterations=100, warmup=10)

    # 1000x DownloadResult 생성
    def _bulk_download_result():
        for i in range(1000):
            DownloadResult.success_result(
                key=f"download/{i}.bin",
                data=b"x",
                download_time_ms=float(i),
            )
    bench(pr, _bulk_download_result, "1000x DownloadResult.success_result", 20000.0, iterations=100, warmup=10)

    # 1000x StorageMetrics.record_upload
    def _bulk_metrics_upload():
        m = StorageMetrics()
        ur = UploadResult.success_result(key="x", upload_time_ms=10.0)
        for _ in range(1000):
            m.record_upload(ur, 512)
    bench(pr, _bulk_metrics_upload, "1000x StorageMetrics.record_upload", 20000.0, iterations=100, warmup=10)

    # 1000x CacheEntry 생성
    exp = now + timedelta(hours=1)

    def _bulk_cache_entry():
        for i in range(1000):
            CacheEntry(
                key=f"cache:{i}",
                value=i,
                created_at=now,
                expires_at=exp,
            )
    bench(pr, _bulk_cache_entry, "1000x CacheEntry 생성", 20000.0, iterations=100, warmup=10)

    # 1000x FilterCriteria 생성
    def _bulk_filter_criteria():
        for i in range(1000):
            FilterCriteria(field=f"field_{i}", operator="eq", value=i)
    bench(pr, _bulk_filter_criteria, "1000x FilterCriteria 생성", 20000.0, iterations=100, warmup=10)

    # 1000x PaginatedResult 생성
    items = list(range(20))

    def _bulk_paginated_result():
        for i in range(1000):
            PaginatedResult(items=items, total_count=1000, page=i + 1, page_size=20)
    bench(pr, _bulk_paginated_result, "1000x PaginatedResult 생성", 20000.0, iterations=100, warmup=10)

    # 1000x QueryOptions.add_filter 체이닝
    def _bulk_query_add_filter():
        qo = QueryOptions()
        for i in range(1000):
            qo.add_filter(f"field_{i}", "eq", i)
    bench(pr, _bulk_query_add_filter, "1000x QueryOptions.add_filter", 20000.0, iterations=100, warmup=10)


# =============================================================================
# 메인 실행
# =============================================================================
def main() -> None:
    """전체 성능 테스트 실행."""
    print("=" * 60)
    print("  storage_interface.py 성능 테스트")
    print("  모듈: shared.interfaces.storage_interface")
    print("=" * 60)

    pr = PerfResult()

    # Section 1~14 실행
    test_storage_type_access(pr)          # 7 checks
    test_storage_type_get_name(pr)        # 5 checks
    test_storage_state(pr)                # 7 checks
    test_content_type_access(pr)          # 8 checks
    test_content_type_get_name(pr)        # 4 checks
    test_sort_order(pr)                   # 6 checks
    test_file_metadata(pr)                # 5 checks
    test_upload_download_result(pr)       # 6 checks
    test_storage_metrics(pr)              # 5 checks
    test_cache_entry_paginated(pr)        # 5 checks
    test_filter_query_options(pr)         # 6 checks
    test_repository_metrics(pr)           # 5 checks
    test_storage_lifecycle(pr)            # 6 checks
    test_bulk_operations(pr)              # 8 checks

    # 종합 결과
    success = pr.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
