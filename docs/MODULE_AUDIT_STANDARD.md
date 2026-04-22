# COURTVIEW DESK — 모듈 코드 품질 검사 기준서 v1.0

> **기준 모듈**: `core_foundation/config/loader.py` (2026-03-06, 100/100)
> **적용 대상**: game_analysis 구축 전 전체 모듈 검사
> **작성일**: 2026-03-10

---

## 1. 검사 카테고리 및 배점

| 카테고리 | 배점 | 설명 |
|----------|------|------|
| A. 구조 설계 | 25점 | 파일 헤더, 클래스/타입 설계, 코드 구성 |
| B. 임포트 타당성 | 25점 | 계층 규칙, 순환참조, 정의서 준수 |
| C. 메모리 및 최적화 | 25점 | 누수 방지, 캐싱, 불필요한 복사 |
| D. 프로덕션 안정성 | 25점 | 스레드 안전, 예외 처리, 방어적 코딩 |
| **합계** | **100점** | |

---

## 2. A. 구조 설계 (25점)

### A-1. 파일 헤더 (5점)

```python
# 기준 패턴
# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: {모듈 경로}
파일: {파일명}.py
설명: {1줄 요약}

작성자: SPOIN_COURTVIEW
최종 수정: {날짜}
버전: {x.y.z}

주요 기능:
    - {기능1}
    - {기능2}

사용 예시:
    >>> {코드 예시}
"""
```

| 항목 | 감점 | 기준 |
|------|------|------|
| 헤더 docstring 누락 | -3 | 모듈/파일/설명/작성자/날짜 필수 |
| 사용 예시 누락 | -1 | 클래스 1개 이상 포함 파일은 필수 |
| 버전 정보 누락 | -1 | `__version__: str = "x.y.z"` 파일 끝 |

### A-2. 코드 구성 순서 (5점)

```
1. from __future__ import annotations
2. # === 표준 라이브러리 ===
3. # === 서드파티 라이브러리 ===
4. # === 프로젝트 모듈 ===
5. # === 로거 설정 ===
6. # === 타입 변수 ===
7. # === 상수 정의 ===
8. # === Enum 정의 ===
9. # === 데이터 클래스 ===
10. # === 메인 클래스 ===
11. # === 헬퍼 함수 ===
12. # === 모듈 Export 정의 ===
13. __version__
```

| 항목 | 감점 | 기준 |
|------|------|------|
| `from __future__ import annotations` 누락 | -2 | PEP 604/585 사용 시 필수 |
| 섹션 구분자 `# ===...===` 누락/불일치 | -1 | 3단 임포트 구분 필수 |
| 순서 위반 (Enum이 클래스 뒤 등) | -2 | 위 순서 준수 |

### A-3. 클래스/타입 설계 (10점)

| 항목 | 감점 | 기준 |
|------|------|------|
| Enum 미사용 (문자열 상수 직접 비교) | -3 | 3개 이상 선택지는 Enum 필수 |
| dataclass 미사용 (수동 __init__) | -2 | 데이터 컨테이너는 dataclass/Pydantic 필수 |
| 타입 힌트 누락 (메서드 시그니처) | -3 | 모든 public 메서드 반환 타입 필수 |
| PEP 604 미적용 (`Optional[X]` 사용) | -1 | `X \| None` 사용 |
| PEP 585 미적용 (`List[X]` 사용) | -1 | `list[X]` 사용 |

### A-4. Export 및 메타 (5점)

| 항목 | 감점 | 기준 |
|------|------|------|
| `__all__` 누락 | -3 | 카테고리 주석 포함 필수 |
| `__all__`과 실제 export 불일치 | -2 | 선언된 것만 export, 누락 없음 |
| `__repr__` 미구현 (주요 클래스) | -1 | 디버깅용 문자열 표현 필수 |

---

## 3. B. 임포트 타당성 (25점)

### B-1. 계층 규칙 준수 (10점)

```
허용 방향 (상위 → 하위만 참조):
  shared/ ← 누구나 참조 가능
  core_foundation/ ← shared만 참조
  infrastructure/ ← shared, core_foundation 참조
  detection/ ← shared, core_foundation, infrastructure 참조
  pose_estimation/ ← shared, core_foundation, infrastructure 참조
  biomechanics/ ← 상위 모든 레이어 참조
  motion_analysis/ ← 상위 모든 레이어 참조
  game_analysis/ ← 상위 모든 레이어 참조
  multi_view/ ← 상위 모든 레이어 참조
```

| 항목 | 감점 | 기준 |
|------|------|------|
| 역방향 임포트 (하위→상위 아닌 상위→하위) | -5 | 절대 금지 |
| 동일 레이어 직접 임포트 | -3 | DTO 경유 또는 interface 사용 |
| 미구현 모듈 임포트 (선 구현) | 0 | 허용 (CLAUDE.md #34) |

### B-2. 순환참조 (10점)

| 항목 | 감점 | 기준 |
|------|------|------|
| 순환참조 발견 | -10 | 절대 금지 (CLAUDE.md #31) |
| TYPE_CHECKING 블록 미사용 (타입 전용 임포트) | -2 | 런타임 불필요 임포트는 TYPE_CHECKING 내 |

### B-3. 임포트 정리 (5점)

| 항목 | 감점 | 기준 |
|------|------|------|
| 미사용 임포트 | -1 | 사용하지 않는 import 잔류 |
| 와일드카드 임포트 (`from x import *`) | -3 | 절대 금지 |
| 상대 임포트 사용 | -1 | 절대 경로 임포트만 사용 |

---

## 4. C. 메모리 및 최적화 (25점)

### C-1. 메모리 누수 방지 (10점)

| 항목 | 감점 | 기준 | loader.py 기준 패턴 |
|------|------|------|---------------------|
| 무한 성장 가능 컬렉션 | -5 | 크기 제한 또는 TTL 필수 | `_ENTRIES_MAX_SIZE`, `_SPLIT_CACHE_MAX_SIZE` |
| 싱글톤 인스턴스 내 대량 데이터 축적 | -3 | clear() 또는 퇴거 정책 | `_put_entry()` FIFO, `clear()` |
| 이벤트 리스너/콜백 미해제 | -2 | 등록/해제 쌍 확인 | `on_change()` / `off_change()` (settings.py) |

### C-2. 불필요한 복사/연산 (8점)

| 항목 | 감점 | 기준 | loader.py 기준 패턴 |
|------|------|------|---------------------|
| 불필요한 deepcopy | -3 | in-place 가능하면 in-place | `_merge_into()` in-place 머지 |
| 반복 연산 미캐싱 | -2 | 동일 입력 반복 시 캐시 | `_split_key()` LRU 캐시 |
| 배치 작업 시 개별 처리 | -3 | 일괄 처리 패턴 사용 | `_defer_env` 배치 최적화 |

### C-3. 데이터 구조 효율성 (7점)

| 항목 | 감점 | 기준 | loader.py 기준 패턴 |
|------|------|------|---------------------|
| `__slots__` 미적용 (인스턴스 많은 클래스) | -2 | 다수 인스턴스 생성 클래스에 적용 | `__slots__`, `@dataclass(slots=True)` |
| `list` 대신 `tuple` 사용 가능한 불변 데이터 | -1 | 변경 없는 시퀀스는 tuple | `_split_key() → tuple[str, ...]` |
| O(n) 중복 체크 (`if x not in list`) | -2 | `dict`/`set`으로 O(1) | `_loaded_files: dict[str, None]` |
| 상수 tuple 타입 미지정 | -2 | `tuple[str, ...]` 명시 | `YAML_EXTENSIONS: tuple[str, ...]` |

---

## 5. D. 프로덕션 안정성 (25점)

### D-1. 스레드 안전 (8점)

| 항목 | 감점 | 기준 | loader.py 기준 패턴 |
|------|------|------|---------------------|
| 공유 상태 무보호 접근 | -5 | 읽기/쓰기 모두 lock | `_config_lock: RLock` 전 메서드 |
| 싱글톤 DCL 경쟁 조건 | -3 | 팩토리 메서드 + lock 내 완전 초기화 | `get_instance()` + `_do_init()` |
| 반복자 중 변경 가능 | -2 | 스냅샷 후 반복 | `items()` 스냅샷 패턴 |
| `set_multiple` 비원자적 | -3 | 단일 lock 블록 내 일괄 처리 | `set_multiple()` 단일 lock |

### D-2. 예외 처리 (8점)

| 항목 | 감점 | 기준 | loader.py 기준 패턴 |
|------|------|------|---------------------|
| bare except (`except:`) | -3 | 구체적 예외 타입 명시 | `except yaml.YAMLError`, `except json.JSONDecodeError` |
| 예외 삼킴 (catch 후 무시) | -3 | 최소 로깅 필수 | `logger.warning(...)` |
| 프로젝트 예외 미사용 (범용 Exception raise) | -2 | `shared.exceptions` 사용 | `ConfigurationException`, `ConfigurationParseException` |
| 원자적 롤백 미지원 (배치 작업) | -2 | 실패 시 이전 상태 복원 | `_atomic_config_update()` |

### D-3. 방어적 코딩 (9점)

| 항목 | 감점 | 기준 | loader.py 기준 패턴 |
|------|------|------|---------------------|
| 외부 입력 미검증 | -3 | 경계 입력 검증 필수 | `_parse_env_value()` 타입 추론 |
| 원본 참조 외부 노출 | -3 | 방어적 복사 반환 | `get_list() → list(value)`, `to_dict() → deepcopy` |
| 재귀 깊이 무제한 | -2 | 깊이 제한 상수 | `_MAX_NESTING_DEPTH = 32` |
| 컨테이너 타입 안전하지 않은 변환 | -2 | 화이트리스트 기반 | `_SAFE_CONVERT_TYPES` |
| None vs 부재 미구분 | -2 | sentinel 패턴 | `_MISSING: _Sentinel` |
| 내장 함수명 섀도잉 | -1 | 파라미터명 주의 | `config_format` (not `format`) |

---

## 6. 등급 기준

| 등급 | 점수 | 판정 | 후속 조치 |
|------|------|------|-----------|
| S | 95-100 | 기준 모듈 수준 | 그대로 유지 |
| A | 85-94 | 프로덕션 적합 | 경미 이슈만 권고 |
| B | 70-84 | 조건부 적합 | 보통 이슈 수정 후 재검사 |
| C | 50-69 | 부적합 | 심각/보통 이슈 전체 수정 필수 |
| F | 0-49 | 재작성 필요 | 구조 재설계 검토 |

---

## 7. 검사 절차

```
1단계: 파일 존재 확인
  └─ 해당 모듈의 모든 .py 파일 목록 확인
  └─ __init__.py 존재 및 __all__ 확인

2단계: 임포트 검증 (B 카테고리)
  └─ 계층 규칙 위반 grep
  └─ 순환참조 여부 확인
  └─ 미사용/와일드카드 임포트 확인

3단계: 구조 검사 (A 카테고리)
  └─ 파일 헤더 패턴 일치
  └─ 코드 구성 순서
  └─ 타입 힌트 / Enum / dataclass 사용

4단계: 메모리/최적화 (C 카테고리)
  └─ 무한 성장 컬렉션 확인
  └─ 불필요한 deepcopy 확인
  └─ __slots__ 적용 여부

5단계: 안정성 검사 (D 카테고리)
  └─ 스레드 안전 (lock 사용 패턴)
  └─ 예외 처리 패턴
  └─ 방어적 코딩 패턴

6단계: 점수 산정 및 등급 판정
  └─ 각 카테고리 감점 합산
  └─ 이슈 목록 + 수정 우선순위 작성
```

---

## 8. 검사 대상 모듈 목록

### Layer 0: shared/
| 모듈 | 파일 수 | 검사 상태 |
|------|---------|-----------|
| shared/constants/ | 26 | 대기 |
| shared/dto/ | 26 | 대기 |
| shared/exceptions/ | 5 | 대기 |
| shared/interfaces/ | 4 | 대기 |
| shared/protocols/ | 2 | 대기 |

### Layer 1: core_foundation/
| 모듈 | 파일 수 | 검사 상태 |
|------|---------|-----------|
| core_foundation/config/ | 4 | loader.py **기준(100/100)** |
| core_foundation/monitoring/ | 5 | 대기 |
| core_foundation/registry/ | 5 | 대기 |
| core_foundation/resilience/ | 2 | 대기 |
| core_foundation/security/ | 2 | 대기 |

### Layer 2: infrastructure/
| 모듈 | 파일 수 | 검사 상태 |
|------|---------|-----------|
| infrastructure/cache/ | 3 | 대기 |
| infrastructure/events/ | 3 | 대기 |
| infrastructure/multi_camera/ | 4 | 대기 |
| infrastructure/preprocessing/ | 7 | 대기 |
| infrastructure/storage/ | 7 | 대기 |
| infrastructure/tracing/ | 3 | 대기 |
| infrastructure/validation/ | 3 | 대기 |

### Layer 3: detection/
| 모듈 | 파일 수 | 검사 상태 |
|------|---------|-----------|
| detection/ball_detection/ | 3+ | 대기 |
| detection/court_detection/ | 3+ | 대기 |
| detection/hoop_detection/ | 2+ | 대기 |
| detection/player_detection/ | 3+ | 대기 |

### Layer 4: pose_estimation/
| 모듈 | 파일 수 | 검사 상태 |
|------|---------|-----------|
| pose_estimation/ | 6+ | 대기 |

### Layer 5: biomechanics/
| 모듈 | 파일 수 | 검사 상태 |
|------|---------|-----------|
| biomechanics/anthropometry/ | 4 | 대기 |
| biomechanics/kinematics/ | 6 | 대기 |
| biomechanics/dynamics/ | 5 | 대기 |
| biomechanics/standards/ | 6 | 대기 |

### Layer 6: motion_analysis/
| 모듈 | 파일 수 | 검사 상태 |
|------|---------|-----------|
| motion_analysis/shooting/ | 5 | 대기 |
| motion_analysis/dribbling/ | 5 | 대기 |
| motion_analysis/passing/ | 5 | 대기 |
| motion_analysis/defense/ | 6 | 대기 |
| motion_analysis/movement/ | 5 | 대기 |
| motion_analysis/classification/ | 4 | 대기 |
| motion_analysis/comparison/ | 3 | 대기 |

### Layer 7: multi_view/
| 모듈 | 파일 수 | 검사 상태 |
|------|---------|-----------|
| multi_view/core/ | 3 | 대기 |
| multi_view/fusion/ | 4 | 대기 |
| multi_view/occlusion/ | 2 | 대기 |
| multi_view/player_identification/ | 4 | 대기 |

### utils/
| 모듈 | 파일 수 | 검사 상태 |
|------|---------|-----------|
| utils/ | 9 | 대기 |

---

## 9. 검사 보고서 템플릿

```markdown
# {모듈명} 코드 품질 검사 보고서

## 기본 정보
- 파일: {파일명}
- 버전: {버전}
- 라인 수: {라인}

## A. 구조 설계 (25점)
- [ ] 파일 헤더 패턴
- [ ] 코드 구성 순서
- [ ] 클래스/타입 설계
- [ ] Export 정의
→ 점수: /25

## B. 임포트 타당성 (25점)
- [ ] 계층 규칙
- [ ] 순환참조
- [ ] 임포트 정리
→ 점수: /25

## C. 메모리 및 최적화 (25점)
- [ ] 메모리 누수 방지
- [ ] 불필요한 복사/연산
- [ ] 데이터 구조 효율성
→ 점수: /25

## D. 프로덕션 안정성 (25점)
- [ ] 스레드 안전
- [ ] 예외 처리
- [ ] 방어적 코딩
→ 점수: /25

## 합계: /100 (등급: )

## 이슈 목록
| # | 등급 | 카테고리 | 위치 | 설명 | 수정안 |
|---|------|----------|------|------|--------|

## 수정 우선순위
1. (심각) ...
2. (보통) ...
3. (경미) ...
```
