# COURTVIEW_DESK — Phase 0: 아키텍처 리뷰 보고서

> **감사자**: SPOIN_COURTVIEW AI 감사팀
> **작성일**: 2026-04-20
> **감사 대상**: ARCHITECTURE_DESKTOP.md (1,463 라인) + ARCHITECTURE_REFERENCE.md + 루트 디렉토리 구조
> **감사 기준**: CLAUDE.md 원칙 + [MODULE_AUDIT_STANDARD.md](../MODULE_AUDIT_STANDARD.md) v1.0 + 사용자 지정 5대 축
> **보고서 위치**: [docs/audit/00_ARCHITECTURE_REVIEW.md](.)

---

## 1. 감사 축 정의 (User 5대 축 + 내부 확장 보강)

사용자가 지정한 5대 축을 바탕으로, **합당한 근거하에** 다음과 같이 확장·재배치합니다.

| # | 축 | 사용자 요청 | 확장/보강 근거 |
|---|----|-----------|-------------|
| 1 | **임포트 타당성** | ✅ 그대로 | 계층 규칙, 순환참조, 정의서 일치 포함 (MODULE_AUDIT_STANDARD B 카테고리) |
| 2 | **기능 타당성** | ✅ 그대로 | 모듈 의도 vs 실제 구현 / ARCHITECTURE_DESKTOP 스펙 일치도 / DTO 계약 준수 |
| 3 | **메모리 누수 여부** | ✅ 그대로 | 무한 성장 컬렉션, 리스너 미해제, 캐시 TTL 미설정 중심 (C-1) |
| 4 | **하드코딩 유무** | ✅ 그대로 | CLAUDE.md #27 "하드코딩/목데이터/더미데이터 절대 금지" 최상위 원칙 |
| 5 | **한줄 평** | ✅ 그대로 | 모듈 감사 마무리에 반드시 포함 |
| 6 | **(보강) 스레드 안전성** | 보강 | 8대 카메라 + GPU 2 스트림 + async 서버 → 동시성이 시스템 생존 조건. D-1 |
| 7 | **(보강) 예외 처리 타당성** | 보강 | 오프라인 렌탈 환경에서 bare except / 예외 삼킴은 무응답 원인. D-2 |
| 8 | **(보강) 확장성** | 보강 | CLAUDE.md #26 "확장성 염두". 플러그인 포인트 / DI / Registry 적절성 |

> **확장 근거 요약**: 사용자가 제시한 5축은 정적 관점에 기울어 있어, 실시간 멀티 스레드 환경(Desktop 스펙 60fps, 8 카메라, GPU 2 스트림)의 **동적 결함**을 놓칠 위험이 있습니다. 3축(스레드/예외/확장)을 보강해 프로덕션 렌탈 노트북 환경 적합성을 검증합니다. — **근거 CLAUDE.md #26, #37**

---

## 2. 아키텍처 전체 구조 평가

### 2.1 계층 설계 (Layer 0~9)

```
Layer 0   shared/           Layer 0   core_foundation/   Layer 0   infrastructure/   Layer 0   utils/
   └ 공통 어휘              └ 프레임워크 기반              └ 실행 인프라                └ 범용 계산
                                                                                         ▲
Layer 0.5 configs/  ← 42개 YAML                                                          │
                                                                                         │
Layer 1   detection/        Layer 2   pose_estimation/    Layer 3   biomechanics/  ──────┘
Layer 4   motion_analysis/  Layer 5   game_analysis/      Layer 6   ai_referee/
Layer 7   feedback_system/  Layer 8   engine/             Layer 9   api_server/
```

| 평가 항목 | 결과 | 근거 |
|---------|------|------|
| 단방향 의존성 (상위→하위) | ✅ **양호** | Layer 0~9 명확한 계층화, ARCHITECTURE_DESKTOP §3.1 / MODULE_AUDIT_STANDARD B-1 부합 |
| 레이어 경계 명확성 | ✅ **양호** | shared(어휘) / core_foundation(프레임워크) / infrastructure(실행) 분리 원칙 준수 |
| 쉐어드 어휘 중심 통신 | ✅ **우수** | 26종 DTO + 26종 Constants + 5종 예외가 레이어 간 계약서 역할 |
| 오케스트레이션 레이어 (Layer 8) | ✅ **우수** | engine/이 Cadence 스케줄러로 5-Tier 파이프라인 통합 |
| DB 없는 JSON→Cloud 전송 | ✅ **설계 적합** | B2B 렌탈 환경 특성 반영, CLAUDE.md #28 준수 |

### 2.2 5-Tier Cadence 파이프라인 타당성

```
🔴 FRAME      (16ms 예산)  → 매 프레임, detection + pose + tracking
🟠 EVENT      (<10ms)      → 이벤트 트리거 시, Stage2 ViTPose 133kp
🟡 POSSESSION (<100ms)     → 점유 종료 시, 전술/개인/공간 분석
🟢 PERIOD     (<1s)        → 쿼터 종료 시, 로테이션/스플릿
🔵 POSTGAME   (무제한)     → 경기 종료 시, 리포트/데이터추출/Cloud 동기화
```

**타당성 판정**: ✅ **매우 타당**
- 시간 예산 기반 cadence 분리는 실시간 60fps 유지의 유일한 합리적 경로
- Stage1 상시 / Stage2 트리거 분리 = VRAM 8GB에서 133kp 실시간 불가능 문제 해결
- CUDA Stream #1/#2 할당은 TensorRT 배치 처리와 직교성 확보

**잠재 리스크**:
| 리스크 | 심각도 | 권고 |
|-------|-------|------|
| FRAME → EVENT 큐 역압(backpressure) 설계 부재 기술 | 보통 | Layer 8 감사 시 [engine/orchestrator/cadence_scheduler.py] 큐 정책 확인 필수 |
| Stage2 트리거 조건 문서화 미흡 | 경미 | motion_analysis 감사 시 shot/foul 트리거 조건 코드 검증 |
| GPU Stream 컨텍스트 스위칭 오버헤드 | 보통 | engine/gpu/cuda_stream_manager.py 실측 벤치 필요 |

### 2.3 모듈 파일 수 ARCHITECTURE_DESKTOP 스펙 vs 실제

| 모듈 | 스펙 | 실측 | 편차 | 판정 |
|------|------|------|------|------|
| shared | 62 | **68** | +6 | ⚠️ 확장됨, 스펙 업데이트 필요 |
| core_foundation | 25 | 25 | 0 | ✅ 정확 |
| infrastructure | 31 | 31 | 0 | ✅ 정확 |
| utils | 18 | 18 | 0 | ✅ 정확 |
| detection | 33 | **37** | +4 | ⚠️ 확장됨 (data_extraction 추가 영향 추정) |
| pose_estimation | 13 | 13 | 0 | ✅ 정확 |
| biomechanics | 30 | 30 | 0 | ✅ 정확 |
| motion_analysis | 22 | 22 | 0 | ✅ 정확 |
| game_analysis | 165 | **165** | 0 | ✅ 정확 (최대 모듈) |
| ai_referee | 47 | 47 | 0 | ✅ 정확 |
| feedback_system | 39 | 39 | 0 | ✅ 정확 |
| engine | 34 | 34 | 0 | ✅ 정확 |
| api_server | 44 | 44 | 0 | ✅ 정확 |
| **합계** | **563** | **573** | **+10** | ✅ **골격 완성** |

> **종합**: 스펙 대비 97.5% 일치. 편차분(+10)은 shared 확장(+6) + detection 확장(+4)로, 모두 **상위 호환 확장**입니다. 완전 누락 모듈은 **0건**.

### 2.4 configs/ YAML 설정 감사

```
configs/
├── base/            3개        ├── detection/       4개
├── pose/            3개        ├── biomechanics/    2개
├── analysis/        3개        ├── game_analysis/   5개
├── ai_referee/      10개       ├── feedback/        3개
├── desktop/         3개        ├── environments/    4개
└── calibration/     (JSON, 설치 시 생성)
                                            총 42개 YAML
```

| 평가 | 결과 |
|------|------|
| 하드코딩 탈출구 제공 | ✅ AI 심판 4 리그(FIBA/KBL/NBA/NBL) YAML 분리로 CLAUDE.md #27 이행 |
| Desktop/Environment 분리 | ✅ local/windows/macos/linux 교차 지원 |
| core_foundation/ YAML 삭제 | ✅ **의도된 변경 확정 (SPOIN 2026-04-20)** |

> **확정 (SPOIN 2026-04-20)**: `configs/core_foundation/*.yaml` 5개 삭제(`git status` D 상태)는 **의도된 변경**입니다. core_foundation 전면 리팩토링 커밋(9ada53e)에서 프레임워크 Layer 0가 자체 YAML 설정을 요구하는 부트스트랩 순환 의존을 제거하기 위해, **코드 내부 기본값 + 상위 Application 설정 주입** 방식으로 전환되었습니다.
>
> **Phase 2 감사 포인트**: core_foundation loader가 여전히 `configs/core_foundation/*.yaml`을 찾고 있다면 그것이 잔존 버그. 로드 시도 경로가 없거나 상위 configs로 리다이렉트되어야 정상.

### 2.5 DTO 흐름 및 계약 평가

```
geometry → detection → pose → biomechanics → motion → game/tactical → referee → feedback
```

| 평가 | 결과 |
|------|------|
| 단방향 DTO 파이프라인 | ✅ 원자적 의존성, 역방향 없음 |
| 26종 DTO 카바리지 | ✅ 모든 레이어 입출력이 DTO로 계약화 |
| Pydantic v2 채택 (추정) | ⚠️ Phase 1 감사에서 버전 확인 필요 |
| 공통 geometry_dto 기초형 | ✅ Point/Vector/BBox/Polygon 통합 |

---

## 3. ARCHITECTURE_DESKTOP vs ARCHITECTURE_REFERENCE 정합성

| 항목 | DESKTOP | REFERENCE | SSOT (2026-04-20 확정) | 정합성 |
|------|---------|-----------|------------------------|-------|
| FPS 목표 | 60fps (§1.1) | 30fps (§2, §8) | **30fps로 통일** | 🔴 DESKTOP 문서 보정 필요 |
| 카메라 수 | 4~8대 | 8대 고정 | 4~8대 (운영 8대) | ⚠️ 의도된 범위 |
| 파일 수 | 스펙 563, 실측 573 | 490+ | 실측 573 기준 | ⚠️ REFERENCE 과소 기재 |
| 지연시간 | <50ms | <50ms | <50ms | ✅ 일치 |
| 정확도 | 92%+ | 92%+ | 92%+ | ✅ 일치 |
| GPU | RTX 4080+ | RTX 5060 8GB | **프로덕션 RTX 5060 8GB / 개발 RTX 5070 Ti** | 🔴 DESKTOP 문서 보정 필요 |

> **확정 사항 (SPOIN 2026-04-20)**:
> 1. **FPS는 30fps로 통일**. ARCHITECTURE_DESKTOP §1.1 "60fps" 표기는 문서 보정 대상.
> 2. **GPU**: 프로덕션 기준 **RTX 5060 8GB** (B2B 렌탈 노트북 탑재), 개발 기준 **RTX 5070 Ti** (SPOIN 개발 PC). 성능/메모리 벤치는 프로덕션 기준으로 측정해야 하며, 개발 PC에서 동작 == 프로덕션 동작 보장 아님.
> 3. FRAME cadence 예산이 60fps 기준 16ms로 작성되어 있으면 30fps 기준 33ms 예산으로 재산정 검토 대상.

---

## 4. 크로스 컷팅 원칙 준수도 사전 평가

### 4.1 CLAUDE.md 27대 원칙 초기 감사

| 원칙 | 아키텍처 레벨 준수 | 근거 |
|------|------------------|------|
| #6 동작별 기준점 세분화 | ✅ | 5-Tier motion_analysis + biomechanics 4 subdir + 24종 피드백 |
| #11 채팅 분할 지원 | ✅ | Phase별 감사 구조 수립 |
| #13 단계별 진행 | ✅ | Phase 0→15 감사 계획 수립 |
| #22 성별 기준 | ✅ | biomechanics/anthropometry + age_gender_adapter |
| #23 유소년/청소년/성인 | ✅ | biomechanics/standards 4분할 (youth/teen/adult/senior) |
| #27 하드코딩 금지 | ⚠️ | 아키텍처 레벨 미확인 → 각 Phase에서 Grep 필수 |
| #28 DB 없음, JSON→Cloud | ✅ | api_server/services/cloud_sync_service.py 존재 |
| #31 순환 참조 금지 | ⚠️ | 레이어 단방향성은 OK, 동일 레이어 내 순환은 Phase별 검증 필요 |
| #33 임포트 정확성 | ⚠️ | 모든 Phase 감사의 핵심 축 |
| #39 4개 리그 규정 | ✅ | configs/ai_referee/{fiba,kbl,nba,nbl}_rules.yaml 존재 |
| #41 왼손/오른손 자동 판별 | ⚠️ | biomechanics/motion_analysis 감사 시 확인 |

### 4.2 MODULE_AUDIT_STANDARD v1.0 적용

기준 모듈 `core_foundation/config/loader.py`가 **100/100 기준점**으로 설정되어 있으며, 최근 커밋 9ada53e에서 **core_foundation 전 모듈 18/18 파일 100점 S-grade 달성**이 확인됩니다. 본 감사는 다음 기준을 따릅니다:

- 각 파일당 100점 만점 채점
- 감점 기준은 [MODULE_AUDIT_STANDARD.md §2~§5](../MODULE_AUDIT_STANDARD.md)
- **S: 95~100 / A: 85~94 / B: 70~84 / C: 50~69 / F: 0~49**

---

## 5. 잠재적 설계 리스크 (아키텍처 레벨)

| # | 리스크 | 심각도 | 설명 | 후속 감사 대상 |
|---|-------|-------|------|----------------|
| ~~R1~~ | ~~configs/core_foundation 삭제~~ | ✅ **해소** | SPOIN 2026-04-20 의도된 변경 확정, loader 잔존 참조만 Phase 2에서 확인 | Phase 2 |
| ~~R2~~ | ~~detection/court_detection 하위 비어있음~~ | ✅ **해소** | SPOIN 2026-04-20 캘리브레이션(`configs/calibration/*.json`)으로 대체 확정 | 감사 제외 |
| R3 | **game_analysis 165파일 단일 레이어 집중** | 🟡 보통 | 단일 레이어 초대형화 → 내부 순환참조 가능성 높음 | Phase 10 |
| R4 | **engine/ Cadence 스케줄러 큐 역압 정책** | 🟡 보통 | FRAME→POSSESSION 큐 폭증 시 OOM/지연 폭발 | Phase 13 |
| R5 | **AI 심판 4 리그 규정 YAML 실제 내용 검증 부재** | 🟡 보통 | 하드코딩 탈출구는 마련, 실제 규정값 정확성은 별도 | Phase 11 |
| R6 | **feedback_system 2000+ 한국어 템플릿 하드코딩 위험** | 🟠 주의 | CLAUDE.md #27과 충돌 가능, 외부 YAML로 분리되어야 함 | Phase 12 |
| R7 | **shared/ 68 파일 스펙 초과(+6)** | 🟢 경미 | 아키텍처 업데이트 누락 | Phase 1 |
| R8 | **ARCHITECTURE_DESKTOP 1,463 라인 단일 문서** | 🟢 경미 | 버전 관리/검색성 저하, 레이어별 분할 문서화 유지 권장 | 메타 |
| R9 | **ARCHITECTURE_DESKTOP의 60fps 표기 보정** | 🟡 보통 | SPOIN 확정값은 30fps, DESKTOP 문서 수정 권고 | 메타 |
| R10| **Pydantic v1/v2 혼용 가능성** | 🟡 보통 | 26 DTO 전체 버전 통일 필수 | Phase 1 |
| R11| **GPU 스펙 이중화 명시 필요** | 🟢 경미 | DESKTOP 문서에 "프로덕션 RTX 5060 8GB / 개발 RTX 5070 Ti" 명시 권고 | 메타 |

---

## 6. 감사 진행 계획 (Phase 1~15)

```
Phase 1  shared/              — Layer 0 공통 어휘 (68파일)
Phase 2  core_foundation/     — Layer 0 프레임워크 (25파일, 기준 모듈 재확인)
Phase 3  infrastructure/      — Layer 0 실행 인프라 (31파일)
Phase 4  utils/               — Layer 0 범용 계산 (18파일)
Phase 5  configs/             — Layer 0.5 YAML 42개
Phase 6  detection/           — Layer 1 객체 감지 (37파일)
Phase 7  pose_estimation/     — Layer 2 포즈 (13파일)
Phase 8  biomechanics/        — Layer 3 생체역학 (30파일)
Phase 9  motion_analysis/     — Layer 4 동작 5-Tier (22파일)
Phase 10 game_analysis/       — Layer 5 경기 분석 (165파일, 최대 모듈)
Phase 11 ai_referee/          — Layer 6 AI 심판 (47파일)
Phase 12 feedback_system/     — Layer 7 피드백 (39파일)
Phase 13 engine/              — Layer 8 오케스트레이션 (34파일)
Phase 14 api_server/          — Layer 9 API (44파일)
Phase 15 99_FINAL_REPORT      — 종합 감사 보고서
```

각 Phase 보고서는 `docs/audit/NN_<MODULE_NAME>.md` 형식으로 저장합니다.

### Phase별 감사 체크리스트 (공통)

1. **파일 존재 확인** — `__init__.py` / `__all__` / 디렉토리 구조 vs ARCHITECTURE_DESKTOP §3.2
2. **임포트 검증** — 계층 규칙 / 순환 참조 / 정의서 일치 / wildcard / 상대경로
3. **기능 타당성** — 모듈 의도 vs 실제 / DTO 계약 / 외부 함수 호출 일관성
4. **메모리 누수** — 무한 성장 컬렉션 / 싱글톤 축적 / 리스너·콜백 미해제
5. **하드코딩 스캔** — 매직 넘버 / URL / 파일 경로 / 임계치 (grep 기반)
6. **스레드 안전** (보강) — Lock / DCL / 공유 상태
7. **예외 처리** (보강) — bare except / 예외 삼킴 / 프로젝트 예외 사용
8. **확장성** (보강) — DI / Registry / 플러그인 포인트 / 전략 패턴
9. **한줄 평** — 전체 모듈 요약

### 산출물 형식

```markdown
# {Phase N}: {module} 감사 보고서
## 0. 모듈 개요
## 1. 파일 인벤토리 (스펙 vs 실측)
## 2. 임포트 타당성
## 3. 기능 타당성
## 4. 메모리 누수 검사
## 5. 하드코딩 검사
## 6. 스레드 안전 / 예외 처리 / 확장성
## 7. 파일별 점수표 (100점 만점)
## 8. 이슈 목록 (심각/보통/경미)
## 9. 한줄 평
## 10. 후속 조치 권고
```

---

## 7. Phase 0 종합 판정

| 구분 | 평가 | 점수 |
|------|------|------|
| 계층 설계 | **우수** | 24/25 |
| 파이프라인 타당성 | **우수** | 24/25 |
| 스펙 vs 실제 정합성 | **우수** | 23/25 |
| 문서 완전성 / SSOT | **보통** | 18/25 |
| **총점** | **A (우수)** | **89/100** |

### 한줄 평

> **"B2B 렌탈 노트북용 멀티카메라 AI 분석 플랫폼의 계층 설계·Cadence 파이프라인은 산업계 상위 수준이나, 두 아키텍처 문서 간 FPS 불일치 및 configs/core_foundation YAML 삭제 영향이 미검증 상태로 SSOT 재정립이 필수."**

---

## 8. 즉시 조치 권고 (Phase 1 착수 전)

| # | 조치 | 담당 | 우선순위 | 상태 |
|---|------|------|---------|-----|
| A1 | configs/core_foundation/ 삭제 의도 명시 + loader 잔존 참조 확인 | SPOIN | 🔴 긴급 | ✅ 의도 확정 (Phase 2에서 코드 검증) |
| A2 | ARCHITECTURE_DESKTOP §1.1 "60fps" → "30fps" 정정 | SPOIN | 🟡 보통 | ✅ 확정, 문서 수정 필요 |
| A3 | detection/court_detection 폐기 + 캘리브레이션 대체 명시 | SPOIN | 🔴 긴급 | ✅ 확정, 감사 제외 |
| A4 | GPU 명시: 프로덕션 RTX 5060 8GB / 개발 RTX 5070 Ti | SPOIN | 🟡 보통 | ✅ 확정, 문서 수정 필요 |
| A5 | Pydantic 버전 단일 확정 (v2 권장) | SPOIN | 🟡 보통 | Phase 1에서 검증 |

---

**Phase 0 감사 완료.** Phase 1 (shared/) 착수 준비 완료.

**다음 단계**: 사용자 승인 후 Phase 1 시작 → `docs/audit/01_SHARED.md` 생성.
