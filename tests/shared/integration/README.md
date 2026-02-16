# shared/ 모듈 통합 테스트

## 개요

`shared/` 모듈 전체의 통합 테스트입니다. 5개 서브모듈(constants, dto, interfaces, protocols, exceptions)의 교차 검증, 순환 참조 검사, export 정합성 검증, 모듈 간 타입 일관성 검증을 수행합니다.

## 테스트 파일

- **test_shared_integration.py**: 84개 테스트 (18개 섹션)

## 모듈 구조

```
shared/ (v2.0.0, 193 exports)
├── constants/ (v1.0.0, 216 exports, 26 modules)
├── dto/ (v1.0.0, 292 exports, 25 modules + __init__.py)
├── interfaces/ (v1.0.0, 81 exports, 4 modules)
├── protocols/ (v1.1.0, 4 exports, 2 modules)
└── exceptions/ (v1.2.0, 145 exports, 5 modules)

총 서브모듈 exports: 738
```

## 테스트 섹션 (A~R, 84 tests)

### [A] Top-level shared module (6 tests)
- `shared.__version__` == "2.0.0"
- `shared.__all__` 존재 및 193개 항목
- 모든 193개 항목 접근 가능
- `shared.__author__` 존재
- import 에러 없음
- 패키지 구조 확인 (`__path__` 존재)

### [B] Sub-module independence (10 tests)
- 5개 서브모듈 독립 import
- 각 서브모듈 `__version__`, `__all__` 존재
- export 개수 검증:
  - constants: 216
  - dto: 292
  - interfaces: 81
  - protocols: 4
  - exceptions: 145

### [C] No circular imports (5 tests)
- `importlib.import_module()`를 사용한 순환 참조 검사
- 모든 서브모듈 순환 참조 없음

### [D] Constants export validation (3 tests)
- 216개 모든 항목 접근 가능
- 모든 Enum 클래스 멤버 존재
- 주요 Enum 존재: Gender, AgeGroup, SkillLevel, ErrorCode

### [E] DTO export validation (3 tests)
- 292개 모든 항목 접근 가능
- 주요 DTO 클래스 존재: VideoSource, PipelineOptions, Point2D, Track
- DTO 클래스 필드 존재 (dataclass 및 Pydantic)

### [F] Interfaces export validation (3 tests)
- 81개 모든 항목 접근 가능
- 주요 인터페이스 존재: IAnalyzer, IDetector, IStorage, IRepository
- ABC 클래스에 abstractmethod 존재

### [G] Protocols export validation (3 tests)
- 4개 모든 항목 접근 가능
- 모든 Protocol이 runtime_checkable
- 주요 Protocol 존재: CameraProtocol, MultiCameraProtocol, StorageProtocol, AsyncStorageProtocol

### [H] Exceptions export validation (3 tests)
- 145개 모든 항목 접근 가능
- 모든 export가 Exception 클래스
- 주요 기본 예외 존재: CourtViewException, RetryableException, NonRetryableException, CriticalException

### [I] Exception hierarchy validation (6 tests)
- 모든 예외가 `CourtViewException` 상속
- 기본 예외 계층 확인:
  - RetryableException → CourtViewException
  - NonRetryableException → CourtViewException
  - CriticalException → CourtViewException
  - VideoException → CourtViewException
  - GPUException → CourtViewException

### [J] Interface ABC verification (5 tests)
- 주요 인터페이스가 ABC 상속
- 각 ABC에 최소 1개 이상 abstractmethod 존재
- 검증 대상: IAnalyzer, IDetector, IStorage, IGameEventDetector

### [K] Protocol runtime_checkable verification (4 tests)
- 모든 Protocol에 `_is_runtime_protocol` 속성 존재
- 검증 대상: CameraProtocol, MultiCameraProtocol, StorageProtocol, AsyncStorageProtocol

### [L] Constants → DTO type consistency (8 tests)
- Enum 타입 일관성 검증:
  - Gender: MALE, FEMALE 멤버 존재
  - AgeGroup: youth/teen/adult 멤버 존재
  - SkillLevel: BEGINNER ~ PROFESSIONAL 멤버 존재
  - RuleSet: FIBA, NBA, KBL 멤버 존재
  - ShotResult, PlayType, ViolationType, FoulType 존재

### [M] Cross-module data flow simulation (5 tests)
- 모듈 간 데이터 흐름 시뮬레이션:
  - DetectionTarget enum 사용 가능
  - BoundingBox 인스턴스 생성 가능
  - AnalysisResult 인스턴스 생성 가능
  - 예외 발생 및 catch 가능
  - Protocol isinstance 체크 동작

### [N] Name collision detection (4 tests)
- 서브모듈 간 이름 충돌 감지 및 문서화
- 예상된 충돌 (설계상 의도됨):
  - BallState, ShotType, TrackState, VideoFormat, EventType 등
- shared/__init__.py에서 별칭 처리 확인:
  - GameEventType (dto.game_dto.EventType)
  - StorageVideoMetadata (interfaces.storage_interface.VideoMetadata)
- 충돌 해결 검증:
  - constants.EventType ≠ dto.game_dto.EventType
  - dto.VideoMetadata ≠ interfaces.VideoMetadata

### [O] Alias consistency (3 tests)
- 별칭 일관성 검증:
  - shared.GameEventType == dto.game_dto.EventType
  - shared.StorageVideoMetadata == interfaces.storage_interface.VideoMetadata
  - constants.EventType와 dto.EventType 구분 확인

### [P] Import path consistency (5 tests)
- import 경로 일관성 검증 (같은 객체 참조):
  - Gender: direct path == package path
  - ErrorCode: shared == constants
  - VideoSource: shared == dto
  - IAnalyzer: shared == interfaces
  - CourtViewException: shared == exceptions

### [Q] Version consistency (3 tests)
- shared.__version__ 존재
- 모든 서브모듈 __version__ 존재
- 모든 버전이 semver 형식 (X.Y.Z)

### [R] Module completeness (5 tests)
- 모듈 파일 개수 검증:
  - constants/: 26개 파일 (__init__.py 제외)
  - dto/: 25개 파일 (__init__.py 제외)
  - interfaces/: 4개 이상 파일
  - protocols/: 2개 이상 파일
  - exceptions/: 5개 이상 파일

## 실행 방법

```bash
# 프로젝트 루트에서 실행
python tests/shared/integration/test_shared_integration.py
```

## 테스트 결과 형식

```
======================================================================
  shared/ 모듈 전체 통합 테스트
  서브모듈: constants(216) + dto(292) + interfaces(81) + protocols(4) + exceptions(145)
  총 exports: 738 (shared 상위: 193)
======================================================================

======================================================================
  섹션 A
======================================================================
  [PASS] shared.__version__ == 2.0.0
  [PASS] shared.__all__ exists with 193 items
  ...

======================================================================
  shared/ 통합 테스트 최종 결과
======================================================================
  총 테스트: 84
  PASS: 84
  FAIL: 0
  실행 시간: 0.308초
======================================================================
```

## 테스트 하네스 패턴

pytest를 사용하지 않고 자체 테스트 하네스를 구현:

```python
@dataclass
class TestResult:
    section: str
    name: str
    passed: bool
    message: str = ""

def run_test(section: str, name: str, test_fn):
    global total_pass, total_fail
    try:
        test_fn()
        results.append(TestResult(section, name, True))
        total_pass += 1
    except Exception as e:
        results.append(TestResult(section, name, False, str(e)))
        total_fail += 1
```

## 주의사항

1. **Path depth**: `parents[3]` 사용 (test_shared_integration.py → integration → shared → tests → COURTVIEW_DESK)
2. **CP949 인코딩 fix**: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")`
3. **예상된 이름 충돌**: 설계상 의도된 충돌은 오류가 아님 (별칭으로 처리됨)
4. **실행 위치**: 프로젝트 루트에서 실행 필요

## 검증 완료

- ✅ 84/84 테스트 통과 (100%)
- ✅ 순환 참조 없음
- ✅ 모든 export 접근 가능
- ✅ 예외 계층 구조 올바름
- ✅ 타입 일관성 확인
- ✅ 이름 충돌 적절히 처리됨
- ✅ import 경로 일관성 확인
- ✅ 버전 semver 준수

## 관련 문서

- `shared/constants/__init__.py`: v1.0.0, 216 exports
- `shared/dto/__init__.py`: v1.0.0, 292 exports
- `shared/interfaces/__init__.py`: v1.0.0, 81 exports
- `shared/protocols/__init__.py`: v1.1.0, 4 exports
- `shared/exceptions/__init__.py`: v1.2.0, 145 exports
- `shared/__init__.py`: v2.0.0, 193 exports

## 작성자

SPOIN_COURTVIEW

## 최종 수정

2026-02-16

## 버전

1.0.0
