# COURTVIEW 임포트 정의서 (Import Rules)

> **버전**: 1.0.0
> **최종 수정**: 2024-12-24
> **목적**: 모든 모듈 간 임포트 규칙 정의, 순환 참조 방지
> **필수**: 새 세션 시작 시 반드시 이 문서 참조

---

## 1. 계층 구조 다이어그램

### 1.1 전체 계층 (Layer) 구조

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    [Layer 10] pipeline/                              │   │
│  │         (모든 계층 통합, 최상위 오케스트레이션)                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    [Layer 9] api_server/                             │   │
│  │              (FastAPI, 라우트, 미들웨어, WebSocket)                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      [Layer 8] learning_system/                      │   │
│  │                   (셀프러닝, 강화학습, 캘리브레이션)                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    [Layer 7] feedback_system/                        │   │
│  │                 (피드백 생성, 추천, 레포트)                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌───────────────────────┬─────────────────────────────────────────────┐   │
│  │ [Layer 6] ai_referee/ │           [Layer 5] game_analysis/          │   │
│  │  (AI 심판, 규칙, 판정) │        (경기분석, 통계, 하이라이트)           │   │
│  └───────────────────────┴─────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    [Layer 4] motion_analysis/                        │   │
│  │            (슈팅, 드리블, 패스, 수비, 이동, 비교 분석)                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    [Layer 3] biomechanics/                           │   │
│  │               (운동학, 동역학, 신체계측, 연령/성별 기준)                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    [Layer 2] pose_estimation/                        │   │
│  │                  (포즈 모델, 키포인트, 검증)                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      [Layer 1] detection/                            │   │
│  │                 (공, 코트, 선수, 골대 감지/추적)                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  [Layer 0.5] infrastructure/                         │   │
│  │           (캐시, 큐, 이벤트버스, 스토리지, DB, 트레이싱)               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   [Layer 0] core_foundation/                         │   │
│  │             (설정, 모니터링, 레지스트리, 회복탄력성, 보안)              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    [공통] shared/, utils/                            │   │
│  │          (상수, 예외, DTO, 인터페이스, 유틸리티 - 모든 계층 사용)       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      [특수] workers/                                  │   │
│  │              (백그라운드 워커 - Layer 0, 0.5, 10만 사용)               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 의존성 흐름 방향

```
의존성 방향: 위 → 아래 (상위 계층이 하위 계층을 임포트)

    Layer 10 (pipeline)
        ↓
    Layer 9 (api_server)
        ↓
    Layer 8 (learning_system)
        ↓
    Layer 7 (feedback_system)
        ↓
    Layer 5, 6 (game_analysis, ai_referee)
        ↓
    Layer 4 (motion_analysis)
        ↓
    Layer 3 (biomechanics)
        ↓
    Layer 2 (pose_estimation)
        ↓
    Layer 1 (detection)
        ↓
    Layer 0.5 (infrastructure)
        ↓
    Layer 0 (core_foundation)

※ 역방향 임포트 절대 금지
※ shared, utils는 모든 계층에서 사용 가능
```

---

## 2. 계층별 임포트 규칙 요약표

| 계층 | 폴더명 | 임포트 가능 | 임포트 불가 |
|------|--------|------------|------------|
| Layer 0 | core_foundation | shared, utils | 모든 다른 계층 |
| Layer 0.5 | infrastructure | Layer 0, shared, utils | Layer 1~10 |
| Layer 1 | detection | Layer 0, 0.5, shared, utils | Layer 2~10 |
| Layer 2 | pose_estimation | Layer 0, 0.5, 1, shared, utils | Layer 3~10 |
| Layer 3 | biomechanics | Layer 0, 0.5, 2, shared, utils | Layer 4~10 |
| Layer 4 | motion_analysis | Layer 0, 0.5, 1, 2, 3, shared, utils | Layer 5~10 |
| Layer 5 | game_analysis | Layer 0, 0.5, 1, 2, 4, shared, utils | Layer 6~10 |
| Layer 6 | ai_referee | Layer 0, 0.5, 1, 2, 3, shared, utils | Layer 4, 5, 7~10 |
| Layer 7 | feedback_system | Layer 0, 0.5, 4, 5, shared, utils | Layer 6, 8~10 |
| Layer 8 | learning_system | Layer 0, 0.5, 4, 7, shared, utils | Layer 9~10 |
| Layer 9 | api_server | 모든 계층, shared, utils | - |
| Layer 10 | pipeline | 모든 계층, shared, utils | - |
| 공통 | shared | 없음 (순수 정의) | 모든 계층 |
| 공통 | utils | shared | 모든 계층 |
| 특수 | workers | Layer 0, 0.5, 10, shared, utils | Layer 1~9 |

---

## 3. 모듈별 상세 임포트 규칙

### 3.1 [Layer 0] core_foundation/

#### 3.1.1 core_foundation/config/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from shared.interfaces import *
from utils import *

# ❌ 금지되는 임포트
from core_foundation.monitoring import *  # 같은 계층 내 다른 모듈 - 주의 필요
from core_foundation.registry import *    # 순환 참조 위험
from infrastructure import *              # 상위 계층
from detection import *                   # 상위 계층
# ... Layer 1~10 모두 금지
```

**내부 모듈 간 규칙 (core_foundation 내부)**:
| 소스 | 타겟 | 허용 |
|------|------|------|
| config | monitoring | ❌ |
| config | registry | ❌ |
| config | resilience | ❌ |
| config | security | ❌ |
| monitoring | config | ✅ |
| monitoring | registry | ❌ |
| registry | config | ✅ |
| registry | monitoring | ✅ |
| resilience | config | ✅ |
| resilience | monitoring | ✅ |
| security | config | ✅ |
| security | monitoring | ✅ |

#### 3.1.2 core_foundation/monitoring/

```python
# ✅ 허용되는 임포트
from shared.constants import ErrorCodes, StatusCodes
from shared.exceptions import BaseException
from shared.dto import *
from utils.time_utils import *
from core_foundation.config import ConfigLoader, SchemaValidator

# ❌ 금지되는 임포트
from core_foundation.registry import *    # 순환 참조 위험
from infrastructure import *
from detection import *
# ... Layer 0.5~10 모두 금지
```

#### 3.1.3 core_foundation/registry/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.interfaces import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, ErrorTracker

# ❌ 금지되는 임포트
from core_foundation.resilience import *  # 순환 참조 위험
from infrastructure import *
# ... Layer 0.5~10 모두 금지
```

#### 3.1.4 core_foundation/resilience/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, ErrorTracker

# ❌ 금지되는 임포트
from core_foundation.registry import *    # 순환 참조 위험
from infrastructure import *
# ... Layer 0.5~10 모두 금지
```

#### 3.1.5 core_foundation/security/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import AuditLogger, ErrorTracker

# ❌ 금지되는 임포트
from core_foundation.registry import *
from infrastructure import *
# ... Layer 0.5~10 모두 금지
```

---

### 3.2 [Layer 0.5] infrastructure/

#### 3.2.1 infrastructure/cache/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import InfrastructureException
from shared.interfaces import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, PerformanceProfiler
from core_foundation.resilience import CircuitBreaker, RetryMechanism

# ❌ 금지되는 임포트
from infrastructure.queue import *        # 같은 계층 - 주의 필요
from infrastructure.database import *     # 같은 계층 - 주의 필요
from detection import *
# ... Layer 1~10 모두 금지
```

**infrastructure 내부 모듈 간 규칙**:
| 소스 | 타겟 | 허용 | 비고 |
|------|------|------|------|
| cache | queue | ❌ | 독립 모듈 |
| cache | events | ❌ | 독립 모듈 |
| cache | storage | ❌ | 독립 모듈 |
| cache | database | ❌ | 독립 모듈 |
| cache | tracing | ✅ | 트레이싱은 공통 |
| queue | cache | ✅ | 캐시 결과 저장 |
| queue | tracing | ✅ | 트레이싱은 공통 |
| events | cache | ❌ | 독립 모듈 |
| events | tracing | ✅ | 트레이싱은 공통 |
| storage | cache | ✅ | 캐시 연동 |
| storage | tracing | ✅ | 트레이싱은 공통 |
| database | cache | ✅ | 캐시 연동 |
| database | tracing | ✅ | 트레이싱은 공통 |
| tracing | 모든 모듈 | ❌ | 트레이싱은 임포트 안함 |

#### 3.2.2 infrastructure/queue/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import InfrastructureException
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, ErrorTracker
from core_foundation.resilience import CircuitBreaker, RetryMechanism
from infrastructure.cache import CacheManager  # 결과 캐싱용
from infrastructure.tracing import Tracer

# ❌ 금지되는 임포트
from infrastructure.events import *       # 순환 위험
from infrastructure.database import *     # 독립 유지
from detection import *
# ... Layer 1~10 모두 금지
```

#### 3.2.3 infrastructure/events/

```python
# ✅ 허용되는 임포트
from shared.constants import EventTypes
from shared.exceptions import *
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.tracing import Tracer

# ❌ 금지되는 임포트
from infrastructure.cache import *        # 독립 유지
from infrastructure.queue import *        # 순환 위험
from infrastructure.database import *
from detection import *
# ... Layer 1~10 모두 금지
```

#### 3.2.4 infrastructure/storage/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import InfrastructureException
from shared.interfaces import StorageInterface
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from core_foundation.resilience import RetryMechanism
from infrastructure.cache import CacheManager  # 캐시 연동
from infrastructure.tracing import Tracer

# ❌ 금지되는 임포트
from infrastructure.queue import *
from infrastructure.events import *
from infrastructure.database import *
from detection import *
# ... Layer 1~10 모두 금지
```

#### 3.2.5 infrastructure/database/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import InfrastructureException
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, PerformanceProfiler
from core_foundation.resilience import CircuitBreaker, RetryMechanism
from infrastructure.cache import CacheManager  # 쿼리 캐시
from infrastructure.tracing import Tracer

# ❌ 금지되는 임포트
from infrastructure.queue import *
from infrastructure.events import *
from infrastructure.storage import *
from detection import *
# ... Layer 1~10 모두 금지
```

#### 3.2.6 infrastructure/tracing/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from utils.time_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector

# ❌ 금지되는 임포트 (가장 엄격)
from infrastructure.cache import *        # 금지
from infrastructure.queue import *        # 금지
from infrastructure.events import *       # 금지
from infrastructure.storage import *      # 금지
from infrastructure.database import *     # 금지
from detection import *
# ... Layer 1~10 모두 금지
```

---

### 3.3 [Layer 1] detection/

#### 3.3.1 detection/ball_detection/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from shared.interfaces import DetectorInterface
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, PerformanceProfiler
from core_foundation.registry import ModelRegistry
from infrastructure.cache import CacheManager, ModelCache
from infrastructure.tracing import Tracer

# ❌ 금지되는 임포트
from detection.court_detection import *   # 같은 계층 - 필요시만
from detection.player_detection import *  # 같은 계층 - 필요시만
from pose_estimation import *             # 상위 계층
from biomechanics import *                # 상위 계층
# ... Layer 2~10 모두 금지
```

**detection 내부 모듈 간 규칙**:
| 소스 | 타겟 | 허용 | 비고 |
|------|------|------|------|
| ball_detection | court_detection | ✅ | 코트 좌표 참조 |
| ball_detection | player_detection | ✅ | 선수-공 상호작용 |
| ball_detection | hoop_detection | ✅ | 골대-공 상호작용 |
| court_detection | ball_detection | ❌ | 역방향 금지 |
| court_detection | player_detection | ❌ | 독립 유지 |
| court_detection | hoop_detection | ✅ | 골대 위치 참조 |
| player_detection | ball_detection | ❌ | 역방향 금지 |
| player_detection | court_detection | ✅ | 코트 좌표 참조 |
| player_detection | hoop_detection | ❌ | 독립 유지 |
| hoop_detection | court_detection | ✅ | 코트 좌표 참조 |
| hoop_detection | ball_detection | ❌ | 역방향 금지 |
| hoop_detection | player_detection | ❌ | 독립 유지 |

#### 3.3.2 detection/court_detection/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from shared.interfaces import DetectorInterface
from utils import *
from utils.geometry_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.hoop_detection import HoopDetector  # 골대 위치

# ❌ 금지되는 임포트
from detection.ball_detection import *    # 역방향
from detection.player_detection import *  # 독립 유지
from pose_estimation import *
# ... Layer 2~10 모두 금지
```

#### 3.3.3 detection/player_detection/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from shared.interfaces import DetectorInterface
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from core_foundation.registry import ModelRegistry
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.court_detection import CourtMapper, ZoneClassifier  # 위치 참조

# ❌ 금지되는 임포트
from detection.ball_detection import *    # 역방향
from detection.hoop_detection import *    # 독립 유지
from pose_estimation import *
# ... Layer 2~10 모두 금지
```

#### 3.3.4 detection/hoop_detection/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from shared.interfaces import DetectorInterface
from utils import *
from utils.geometry_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.court_detection import CourtMapper  # 코트 좌표

# ❌ 금지되는 임포트
from detection.ball_detection import *    # 역방향
from detection.player_detection import *  # 독립 유지
from pose_estimation import *
# ... Layer 2~10 모두 금지
```

---

### 3.4 [Layer 2] pose_estimation/

#### 3.4.1 pose_estimation/models/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from shared.interfaces import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, PerformanceProfiler
from core_foundation.registry import ModelRegistry
from infrastructure.cache import ModelCache
from infrastructure.tracing import Tracer
from detection.player_detection import PlayerDetector, PlayerTracker

# ❌ 금지되는 임포트
from pose_estimation.processors import *  # 순환 위험
from pose_estimation.validators import *  # 순환 위험
from biomechanics import *
# ... Layer 3~10 모두 금지
```

**pose_estimation 내부 모듈 간 규칙**:
| 소스 | 타겟 | 허용 | 비고 |
|------|------|------|------|
| models | processors | ❌ | 순환 방지 |
| models | validators | ❌ | 순환 방지 |
| processors | models | ✅ | 모델 사용 |
| processors | validators | ❌ | 독립 유지 |
| validators | models | ✅ | 키포인트 정의 참조 |
| validators | processors | ✅ | 처리된 데이터 검증 |

#### 3.4.2 pose_estimation/processors/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from utils.math_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.player_detection import PlayerTracker
from pose_estimation.models import PoseModel, KeypointDefinition

# ❌ 금지되는 임포트
from pose_estimation.validators import *  # 독립 유지
from biomechanics import *
# ... Layer 3~10 모두 금지
```

#### 3.4.3 pose_estimation/validators/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import ValidationException
from shared.dto import *
from utils import *
from utils.math_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.tracing import Tracer
from pose_estimation.models import KeypointDefinition
from pose_estimation.processors import KeypointExtractor, PoseNormalizer

# ❌ 금지되는 임포트
from biomechanics import *
# ... Layer 3~10 모두 금지
```

---

### 3.5 [Layer 3] biomechanics/

#### 3.5.1 biomechanics/kinematics/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from utils.math_utils import *
from utils.geometry_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from pose_estimation.models import KeypointDefinition
from pose_estimation.processors import KeypointExtractor, PoseNormalizer
from pose_estimation.validators import AnatomicalValidator

# ❌ 금지되는 임포트
from biomechanics.dynamics import *       # 내부 순환 주의
from biomechanics.anthropometry import *  # 필요시만 허용
from motion_analysis import *
# ... Layer 4~10 모두 금지
```

**biomechanics 내부 모듈 간 규칙**:
| 소스 | 타겟 | 허용 | 비고 |
|------|------|------|------|
| kinematics | dynamics | ❌ | 독립 계산 |
| kinematics | anthropometry | ✅ | 신체 파라미터 필요 |
| kinematics | standards | ✅ | 기준값 참조 |
| dynamics | kinematics | ✅ | 속도/가속도 필요 |
| dynamics | anthropometry | ✅ | 질량/관성 필요 |
| dynamics | standards | ✅ | 기준값 참조 |
| anthropometry | kinematics | ❌ | 역방향 금지 |
| anthropometry | dynamics | ❌ | 역방향 금지 |
| anthropometry | standards | ✅ | 연령/성별 기준 |
| standards | 모든 모듈 | ❌ | 순수 데이터 |

#### 3.5.2 biomechanics/dynamics/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from utils.math_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.tracing import Tracer
from pose_estimation.models import KeypointDefinition
from pose_estimation.processors import PoseNormalizer
from biomechanics.kinematics import JointAngleCalculator, VelocityAnalyzer
from biomechanics.anthropometry import BodySegment, AgeGenderAdapter
from biomechanics.standards import *

# ❌ 금지되는 임포트
from motion_analysis import *
# ... Layer 4~10 모두 금지
```

#### 3.5.3 biomechanics/anthropometry/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from pose_estimation.models import KeypointDefinition
from pose_estimation.processors import PoseNormalizer
from biomechanics.standards import YouthStandards, TeenStandards, AdultStandards

# ❌ 금지되는 임포트
from biomechanics.kinematics import *     # 역방향 금지
from biomechanics.dynamics import *       # 역방향 금지
from motion_analysis import *
# ... Layer 4~10 모두 금지
```

#### 3.5.4 biomechanics/standards/

```python
# ✅ 허용되는 임포트 (최소한)
from shared.constants import *
from shared.dto import *

# ❌ 금지되는 임포트 (순수 데이터 모듈)
from utils import *                       # 가급적 금지
from core_foundation import *             # 금지
from infrastructure import *              # 금지
from pose_estimation import *             # 금지
from biomechanics.kinematics import *     # 금지
from biomechanics.dynamics import *       # 금지
from biomechanics.anthropometry import *  # 금지
# ... 모든 계층 금지
```

---

### 3.6 [Layer 4] motion_analysis/

#### 3.6.1 motion_analysis/shooting/ (🔄 v1.1.0 PHASE_08 동기화)

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import AnalysisException
from shared.dto import AnalysisDTO, FeedbackDTO
from shared.interfaces import AnalyzerInterface
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, PerformanceProfiler
from core_foundation.registry import ModelRegistry
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.ball_detection import BallDetector, BallTracker, BallState
from detection.hoop_detection import HoopDetector
from pose_estimation.backends import MediaPipeBackend  # 🔧 v3.4.0: pose_estimation v2.0.0
from pose_estimation.keypoint_types import UnifiedKeypoint, KeypointData  # 🔧 v3.4.0
from pose_estimation.validation import AnatomicalValidator  # 🔧 v3.4.0: validators → validation
from biomechanics.kinematics import JointAngleCalculator, VelocityAnalyzer, TrajectoryAnalyzer
from biomechanics.anthropometry import BodySegment, AgeGenderAdapter
from biomechanics.standards import *

# ❌ 금지되는 임포트
from motion_analysis.dribbling import *   # 같은 계층 - 독립 유지
from motion_analysis.passing import *     # 같은 계층 - 독립 유지
from motion_analysis.classification import *  # 역방향
from game_analysis import *               # 상위 계층
from ai_referee import *                  # 상위 계층
from feedback_system import *             # 상위 계층
# ... Layer 5~10 모두 금지
```

**motion_analysis 내부 모듈 간 규칙** (🔄 v1.1.0 PHASE_08 동기화):
| 소스 | 타겟 | 허용 | 비고 |
|------|------|------|------|
| shooting | dribbling | ❌ | 독립 분석 |
| shooting | passing | ❌ | 독립 분석 |
| shooting | defense | ❌ | 독립 분석 |
| shooting | movement | ✅ | 점프/풋워크 분석 필요 |
| shooting | comparison | ❌ | 역방향 |
| shooting | classification | ❌ | 역방향 |
| dribbling | shooting | ❌ | 독립 분석 |
| dribbling | movement | ✅ | 이동 분석 필요 |
| dribbling | comparison | ❌ | 역방향 |
| dribbling | classification | ❌ | 역방향 |
| passing | movement | ✅ | 이동 분석 필요 |
| passing | comparison | ❌ | 역방향 |
| defense | movement | ✅ | 풋워크 분석 필요 |
| defense | comparison | ❌ | 역방향 |
| movement | 다른 분석 | ❌ | 기초 분석 모듈 |
| comparison | shooting | ✅ | 슈팅 비교 |
| comparison | dribbling | ✅ | 드리블 비교 |
| comparison | passing | ✅ | 패스 비교 |
| comparison | defense | ✅ | 수비 비교 |
| comparison | movement | ✅ | 이동 비교 |
| classification | shooting | ❌ | 독립 분류 (키포인트 기반) |
| classification | dribbling | ❌ | 독립 분류 (키포인트 기반) |
| classification | 다른 분석 | ❌ | 순수 분류기 (외부 의존 최소화) |

#### 3.6.2 motion_analysis/dribbling/ (🔄 v1.1.0 PHASE_08 동기화)

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import AnalysisException
from shared.dto import AnalysisDTO, FeedbackDTO
from shared.interfaces import AnalyzerInterface
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.ball_detection import BallDetector, BallTracker, BallState
from detection.player_detection import PlayerDetector
from detection.court_detection import CourtMapper
from multi_view.player_identification import MultiViewTracker  # 🔧 v4.0.0: player_tracker 이동
from pose_estimation.backends import MediaPipeBackend  # 🔧 v3.4.0: pose_estimation v2.0.0
from pose_estimation.keypoint_types import UnifiedKeypoint, KeypointData
from biomechanics.kinematics import JointAngleCalculator, VelocityAnalyzer
from biomechanics.anthropometry import AgeGenderAdapter
from biomechanics.standards import *
from motion_analysis.movement import FootworkAnalyzer, AgilityAnalyzer  # 🔧 v1.1.0: Sprint → Footwork

# ❌ 금지되는 임포트
from motion_analysis.shooting import *
from motion_analysis.passing import *
from motion_analysis.comparison import *  # 역방향
from motion_analysis.classification import *  # 역방향
from game_analysis import *
# ... Layer 5~10 모두 금지
```

#### 3.6.3 motion_analysis/passing/ (🔄 v1.1.0 PHASE_08 동기화)

> **v1.1.0 변경**: passing_criteria.py 추가, pose_estimation/detection 경로 업데이트

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import AnalysisException
from shared.dto import *
from shared.interfaces import AnalyzerInterface
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.ball_detection import BallDetector, BallTracker, BallState
from detection.player_detection import PlayerDetector
from multi_view.player_identification import MultiViewTracker  # 🔧 v4.0.0: player_tracker 이동
from pose_estimation.backends import MediaPipeBackend  # 🔧 v3.4.0: pose_estimation v2.0.0
from pose_estimation.keypoint_types import UnifiedKeypoint, KeypointData
from biomechanics.kinematics import JointAngleCalculator, VelocityAnalyzer, TrajectoryAnalyzer
from biomechanics.standards import *
from motion_analysis.movement import FootworkAnalyzer  # 🔧 v1.1.0: SprintAnalyzer → FootworkAnalyzer
from motion_analysis.passing.passing_criteria import *  # 🆕 v1.1.0: 패스 기준값

# ❌ 금지되는 임포트
from motion_analysis.shooting import *
from motion_analysis.dribbling import *
from motion_analysis.comparison import *  # 역방향
from motion_analysis.classification import *  # 역방향
from game_analysis import *
# ... Layer 5~10 모두 금지
```

#### 3.6.4 motion_analysis/defense/ (🔄 v1.1.0 PHASE_08 동기화)

> **v1.1.0 파일명 변경**: defensive_stance_analyzer → stance_analyzer, footwork_analyzer → movement_analyzer, positioning_analyzer → reaction_analyzer, defense_criteria 추가

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import AnalysisException
from shared.dto import *
from shared.interfaces import AnalyzerInterface
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.player_detection import PlayerDetector
from detection.court_detection import CourtMapper, ZoneClassifier
from multi_view.player_identification import MultiViewTracker  # 🔧 v4.0.0: player_tracker 이동
from pose_estimation.backends import MediaPipeBackend  # 🔧 v3.4.0: pose_estimation v2.0.0
from pose_estimation.keypoint_types import UnifiedKeypoint, KeypointData
from biomechanics.kinematics import JointAngleCalculator, VelocityAnalyzer
from biomechanics.standards import *
from motion_analysis.movement import FootworkAnalyzer, AgilityAnalyzer
from motion_analysis.defense.defense_criteria import *  # 수비 기준값

# ❌ 금지되는 임포트
from motion_analysis.shooting import *
from motion_analysis.dribbling import *
from motion_analysis.comparison import *  # 역방향
from game_analysis import *
# ... Layer 5~10 모두 금지
```

#### 3.6.5 motion_analysis/movement/ (🔄 v1.1.0 PHASE_08 동기화)

> **v1.1.0 구조 재설계**: sprint/jump/pivot_analyzer → footwork_analyzer 통합, movement_criteria 추가

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import AnalysisException
from shared.dto import *
from shared.interfaces import AnalyzerInterface
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.player_detection import PlayerDetector
from detection.court_detection import CourtMapper
from multi_view.player_identification import MultiViewTracker  # 🔧 v4.0.0: player_tracker 이동
from pose_estimation.backends import MediaPipeBackend  # 🔧 v3.4.0: pose_estimation v2.0.0
from pose_estimation.keypoint_types import UnifiedKeypoint, KeypointData
from biomechanics.kinematics import JointAngleCalculator, VelocityAnalyzer, AccelerationAnalyzer
from biomechanics.dynamics import ForceEstimator, EnergyAnalyzer
from biomechanics.anthropometry import BodySegment
from biomechanics.standards import *
from motion_analysis.movement.movement_criteria import *  # 이동 기준값

# ❌ 금지되는 임포트 (기초 모듈)
from motion_analysis.shooting import *
from motion_analysis.dribbling import *
from motion_analysis.passing import *
from motion_analysis.defense import *
from motion_analysis.comparison import *
from motion_analysis.classification import *
from game_analysis import *
# ... Layer 5~10 모두 금지
```

#### 3.6.6 motion_analysis/comparison/ (🔄 v1.1.0 PHASE_08 동기화)

> **v1.1.0 파일명 변경**: reference_comparator → template_matcher, deviation_analyzer → comparison_criteria

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import AnalysisException
from shared.dto import *
from utils import *
from utils.math_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.storage import VideoStorage
from infrastructure.tracing import Tracer
from pose_estimation.keypoint_types import UnifiedKeypoint, KeypointData  # 🔧 v3.4.0
from biomechanics.kinematics import JointAngleCalculator
from motion_analysis.shooting import ShootingPhaseAnalyzer, ShootingFormEvaluator
from motion_analysis.dribbling import DribbleTypeClassifier, DribbleFormEvaluator
from motion_analysis.passing import PassTypeClassifier
from motion_analysis.defense import StanceAnalyzer  # 🔧 v1.1.0: 파일명 변경
from motion_analysis.movement import FootworkAnalyzer, AgilityAnalyzer  # 🔧 v1.1.0: 구조 변경
from motion_analysis.comparison.comparison_criteria import *  # 비교 기준값

# ❌ 금지되는 임포트
from game_analysis import *
# ... Layer 5~10 모두 금지
```

---

#### 3.6.7 motion_analysis/classification/ (🆕 v1.1.0 PHASE_08 동기화)

> **v1.1.0 신규**: 동작 자동 분류 서브모듈 (키포인트 기반 순수 분류)

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager

# 로컬 모듈 (같은 패키지 내 Direct)
from motion_analysis.classification.action_types import *    # 동작 유형 열거형
from motion_analysis.classification.action_features import * # 특징 추출 함수

# ❌ 금지되는 임포트 (독립 분류기)
from motion_analysis.shooting import *      # 독립 유지
from motion_analysis.dribbling import *     # 독립 유지
from motion_analysis.passing import *       # 독립 유지
from motion_analysis.defense import *       # 독립 유지
from motion_analysis.movement import *      # 독립 유지
from motion_analysis.comparison import *    # 독립 유지
from game_analysis import *
# ... Layer 5~10 모두 금지
```

---

### 3.7 [Layer 5] game_analysis/

#### 3.7.1 game_analysis/event_detection/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import AnalysisException
from shared.dto import GameDTO
from shared.interfaces import DetectorInterface
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.ball_detection import BallDetector, BallTracker, BallState
from detection.player_detection import PlayerDetector, PlayerTracker, TeamClassifier
from detection.court_detection import CourtMapper, ZoneClassifier
from detection.hoop_detection import HoopDetector, NetAnalyzer
from pose_estimation.models import PoseModel
from pose_estimation.processors import KeypointExtractor
from motion_analysis.shooting import ShootingDetector
from motion_analysis.dribbling import DribbleDetector
from motion_analysis.passing import PassDetector
from motion_analysis.defense import StanceAnalyzer  # 🔧 v1.1.0: DefensiveStanceAnalyzer → StanceAnalyzer

# ❌ 금지되는 임포트
from game_analysis.statistics import *    # 내부 순환 주의
from game_analysis.highlight import *     # 내부 순환 주의
from ai_referee import *                  # 상위 계층
from feedback_system import *
# ... Layer 6~10 모두 금지
```

**game_analysis 내부 모듈 간 규칙**:
| 소스 | 타겟 | 허용 | 비고 |
|------|------|------|------|
| event_detection | statistics | ❌ | 역방향 |
| event_detection | shot_location | ❌ | 역방향 |
| event_detection | highlight | ❌ | 역방향 |
| event_detection | game_record | ❌ | 역방향 |
| statistics | event_detection | ✅ | 이벤트 기반 통계 |
| statistics | shot_location | ✅ | 슛 위치 통계 |
| shot_location | event_detection | ✅ | 슛 이벤트 필요 |
| shot_location | statistics | ❌ | 독립 유지 |
| highlight | event_detection | ✅ | 이벤트 기반 하이라이트 |
| highlight | statistics | ✅ | 흥미도 계산 |
| game_record | event_detection | ✅ | 이벤트 기록 |
| game_record | statistics | ✅ | 통계 기록 |
| game_record | shot_location | ✅ | 슛 위치 기록 |
| game_record | highlight | ✅ | 하이라이트 기록 |

#### 3.7.2 game_analysis/statistics/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import GameDTO
from utils import *
from utils.math_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.player_detection import PlayerTracker
from detection.court_detection import CourtMapper
from motion_analysis.shooting import ShootingDetector
from game_analysis.event_detection import (
    ShotEventDetector, ScoreDetector, ReboundDetector,
    StealDetector, BlockDetector, TurnoverDetector
)
from game_analysis.shot_location import ShotZoneMapper

# ❌ 금지되는 임포트
from game_analysis.highlight import *
from game_analysis.game_record import *   # 역방향
from ai_referee import *
# ... Layer 6~10 모두 금지
```

#### 3.7.3 game_analysis/shot_location/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import GameDTO
from utils import *
from utils.geometry_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.court_detection import CourtMapper, ZoneClassifier
from detection.hoop_detection import HoopDetector
from game_analysis.event_detection import ShotEventDetector, ScoreDetector

# ❌ 금지되는 임포트
from game_analysis.statistics import *    # 독립 유지
from game_analysis.highlight import *
from game_analysis.game_record import *   # 역방향
from ai_referee import *
# ... Layer 6~10 모두 금지
```

#### 3.7.4 game_analysis/highlight/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import GameDTO
from utils import *
from utils.video_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.storage import VideoStorage
from infrastructure.tracing import Tracer
from game_analysis.event_detection import *
from game_analysis.statistics import BasicStats, AdvancedStats

# ❌ 금지되는 임포트
from game_analysis.game_record import *   # 역방향
from ai_referee import *
# ... Layer 6~10 모두 금지
```

#### 3.7.5 game_analysis/game_record/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import GameDTO
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.storage import S3Storage
from infrastructure.database import AnalysisRepository
from infrastructure.tracing import Tracer
from game_analysis.event_detection import *
from game_analysis.statistics import BasicStats, AdvancedStats, ShotChart
from game_analysis.shot_location import ShotZoneMapper, ShotHeatmap
from game_analysis.highlight import HighlightDetector, ClipExtractor

# ❌ 금지되는 임포트
from ai_referee import *
# ... Layer 6~10 모두 금지
```

---

### 3.8 [Layer 6] ai_referee/

#### 3.8.1 ai_referee/rules/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from shared.interfaces import *
from utils import *
from core_foundation.config import ConfigLoader

# ❌ 금지되는 임포트 (순수 규칙 정의)
from core_foundation.monitoring import *  # 가급적 금지
from infrastructure import *              # 가급적 금지
from detection import *
from pose_estimation import *
from biomechanics import *
from ai_referee.violations import *       # 역방향
from ai_referee.fouls import *            # 역방향
from ai_referee.decisions import *        # 역방향
# ... Layer 4~10 모두 금지
```

**ai_referee 내부 모듈 간 규칙**:
| 소스 | 타겟 | 허용 | 비고 |
|------|------|------|------|
| rules | violations | ❌ | 순수 정의 |
| rules | fouls | ❌ | 순수 정의 |
| rules | decisions | ❌ | 순수 정의 |
| violations | rules | ✅ | 규칙 참조 |
| violations | fouls | ❌ | 독립 유지 |
| violations | decisions | ❌ | 역방향 |
| fouls | rules | ✅ | 규칙 참조 |
| fouls | violations | ❌ | 독립 유지 |
| fouls | decisions | ❌ | 역방향 |
| decisions | rules | ✅ | 규칙 참조 |
| decisions | violations | ✅ | 바이올레이션 판정 |
| decisions | fouls | ✅ | 파울 판정 |

#### 3.8.2 ai_referee/violations/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.ball_detection import BallDetector, BallTracker, BallState
from detection.player_detection import PlayerDetector, PlayerTracker
from detection.court_detection import CourtMapper, ZoneClassifier
from pose_estimation.models import KeypointDefinition
from pose_estimation.processors import KeypointExtractor
from biomechanics.kinematics import JointAngleCalculator, VelocityAnalyzer
from ai_referee.rules import BaseRules, FIBARules, NBARules, KBLRules, NBLRules

# ❌ 금지되는 임포트
from ai_referee.fouls import *            # 독립 유지
from ai_referee.decisions import *        # 역방향
from motion_analysis import *             # 금지 (Layer 4)
from game_analysis import *               # 금지 (Layer 5)
from feedback_system import *
# ... Layer 7~10 모두 금지
```

#### 3.8.3 ai_referee/fouls/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from detection.ball_detection import BallDetector, BallState
from detection.player_detection import PlayerDetector, PlayerTracker
from detection.court_detection import CourtMapper
from pose_estimation.models import KeypointDefinition
from pose_estimation.processors import KeypointExtractor
from biomechanics.kinematics import VelocityAnalyzer, AccelerationAnalyzer
from biomechanics.dynamics import ForceEstimator, MomentumCalculator
from ai_referee.rules import BaseRules, FIBARules, NBARules, KBLRules, NBLRules

# ❌ 금지되는 임포트
from ai_referee.violations import *       # 독립 유지
from ai_referee.decisions import *        # 역방향
from motion_analysis import *             # 금지 (Layer 4)
from game_analysis import *               # 금지 (Layer 5)
from feedback_system import *
# ... Layer 7~10 모두 금지
```

#### 3.8.4 ai_referee/decisions/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.storage import VideoStorage
from infrastructure.tracing import Tracer
from ai_referee.rules import BaseRules, FIBARules, NBARules, KBLRules, NBLRules
from ai_referee.violations import (
    TravelingDetector, DoubleDribbleDetector, BackcourtViolationDetector,
    ShotClockViolation, ThreeSecondViolation, FiveSecondViolation,
    EightSecondViolation, OutOfBoundsDetector
)
from ai_referee.fouls import (
    ContactDetector, PersonalFoulDetector, OffensiveFoulDetector,
    DefensiveFoulDetector, TechnicalFoulDetector, FlagrantFoulDetector
)

# ❌ 금지되는 임포트
from motion_analysis import *             # 금지 (Layer 4)
from game_analysis import *               # 금지 (Layer 5)
from feedback_system import *
# ... Layer 7~10 모두 금지
```

---

### 3.9 [Layer 7] feedback_system/

#### 3.9.1 feedback_system/generators/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import FeedbackDTO
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer
from motion_analysis.shooting import (
    ShootingPhaseAnalyzer, ShootingFormEvaluator, ReleaseAnalyzer, ShootingCriteria
)
from motion_analysis.dribbling import (
    DribbleTypeClassifier, DribbleFormEvaluator, DribbleCriteria
)
from motion_analysis.defense import StanceAnalyzer  # 🔧 v1.1.0: DefensiveStanceAnalyzer → StanceAnalyzer
from motion_analysis.movement import FootworkAnalyzer, AgilityAnalyzer  # 🔧 v1.1.0: Jump/Sprint → Footwork/Agility
from game_analysis.statistics import BasicStats, AdvancedStats

# ❌ 금지되는 임포트
from feedback_system.templates import *   # 내부 순환 주의
from feedback_system.recommendation import *  # 순환 주의
from ai_referee import *                  # 금지 (병렬 계층)
from learning_system import *
# ... Layer 8~10 모두 금지
```

**feedback_system 내부 모듈 간 규칙**:
| 소스 | 타겟 | 허용 | 비고 |
|------|------|------|------|
| generators | templates | ❌ | 순환 방지 |
| generators | recommendation | ❌ | 순환 방지 |
| generators | report | ❌ | 순환 방지 |
| templates | generators | ✅ | 피드백 포맷팅 |
| recommendation | generators | ✅ | 피드백 기반 추천 |
| recommendation | templates | ❌ | 독립 유지 |
| report | generators | ✅ | 피드백 포함 |
| report | templates | ✅ | 포맷팅 |
| report | recommendation | ✅ | 추천 포함 |

#### 3.9.2 feedback_system/templates/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.dto import FeedbackDTO
from utils import *
from core_foundation.config import ConfigLoader
from feedback_system.generators import (
    ShootingFeedback, DribblingFeedback, DefenseFeedback, GeneralFeedback
)

# ❌ 금지되는 임포트
from feedback_system.recommendation import *
from feedback_system.report import *      # 역방향
from learning_system import *
# ... Layer 8~10 모두 금지
```

#### 3.9.3 feedback_system/recommendation/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import FeedbackDTO
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.database import FeedbackRepository
from infrastructure.tracing import Tracer
from motion_analysis.shooting import ShootingCriteria
from motion_analysis.dribbling import DribbleCriteria
from feedback_system.generators import (
    ShootingFeedback, DribblingFeedback, DefenseFeedback
)

# ❌ 금지되는 임포트
from feedback_system.templates import *   # 독립 유지
from feedback_system.report import *      # 역방향
from learning_system import *
# ... Layer 8~10 모두 금지
```

#### 3.9.4 feedback_system/report/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import FeedbackDTO, GameDTO
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.storage import S3Storage
from infrastructure.database import FeedbackRepository, AnalysisRepository
from infrastructure.tracing import Tracer
from motion_analysis.shooting import ShootingFormEvaluator
from motion_analysis.dribbling import DribbleFormEvaluator
from game_analysis.statistics import BasicStats, AdvancedStats
from feedback_system.generators import *
from feedback_system.templates import KoreanTemplates, FeedbackFormatter
from feedback_system.recommendation import TrainingRecommender, DrillSelector

# ❌ 금지되는 임포트
from learning_system import *
# ... Layer 8~10 모두 금지
```

---

### 3.10 [Layer 8] learning_system/

#### 3.10.1 learning_system/self_learning/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, PerformanceProfiler
from infrastructure.cache import CacheManager
from infrastructure.database import AnalysisRepository, FeedbackRepository
from infrastructure.events import EventBus
from infrastructure.tracing import Tracer
from motion_analysis.shooting import ShootingCriteria, ShootingFormEvaluator
from motion_analysis.dribbling import DribbleCriteria, DribbleFormEvaluator
from feedback_system.generators import *
from feedback_system.recommendation import TrainingRecommender

# ❌ 금지되는 임포트
from learning_system.reinforcement import *  # 내부 순환 주의
from learning_system.calibration import *    # 내부 순환 주의
from api_server import *
from pipeline import *
```

**learning_system 내부 모듈 간 규칙**:
| 소스 | 타겟 | 허용 | 비고 |
|------|------|------|------|
| self_learning | reinforcement | ❌ | 독립 학습 |
| self_learning | calibration | ✅ | 임계값 조정 |
| reinforcement | self_learning | ❌ | 독립 학습 |
| reinforcement | calibration | ✅ | 임계값 조정 |
| calibration | self_learning | ❌ | 역방향 |
| calibration | reinforcement | ❌ | 역방향 |

#### 3.10.2 learning_system/reinforcement/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.database import AnalysisRepository
from infrastructure.tracing import Tracer
from motion_analysis.shooting import ShootingFormEvaluator
from motion_analysis.dribbling import DribbleFormEvaluator
from feedback_system.generators import *
from learning_system.calibration import ThresholdAdjuster, AccuracyMonitor

# ❌ 금지되는 임포트
from learning_system.self_learning import *  # 독립 유지
from api_server import *
from pipeline import *
```

#### 3.10.3 learning_system/calibration/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from utils.math_utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, PerformanceProfiler
from infrastructure.cache import CacheManager
from infrastructure.database import AnalysisRepository
from infrastructure.tracing import Tracer
from motion_analysis.shooting import ShootingCriteria
from motion_analysis.dribbling import DribbleCriteria

# ❌ 금지되는 임포트
from learning_system.self_learning import *  # 역방향
from learning_system.reinforcement import *  # 역방향
from api_server import *
from pipeline import *
```

---

### 3.11 [Layer 9] api_server/

#### 3.11.1 api_server/routes/v1/

```python
# ✅ 허용되는 임포트 (모든 계층 사용 가능)
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, HealthCheck
from core_foundation.registry import ServiceRegistry
from infrastructure.cache import CacheManager
from infrastructure.queue import TaskQueue, JobManager
from infrastructure.events import EventBus
from infrastructure.storage import S3Storage, VideoStorage
from infrastructure.database import *
from infrastructure.tracing import Tracer
from api_server.middleware import *
from api_server.services import *
from api_server.schemas import *

# ❌ 금지되는 임포트
from pipeline import *  # 서비스를 통해 간접 호출
```

#### 3.11.2 api_server/middleware/

```python
# ✅ 허용되는 임포트
from shared.constants import ErrorCodes, StatusCodes
from shared.exceptions import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, ErrorTracker
from core_foundation.security import SecretManager, AuditLogger
from core_foundation.resilience import RateLimiter
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer, CorrelationId

# ❌ 금지되는 임포트
from api_server.routes import *           # 역방향
from api_server.services import *         # 역방향
from pipeline import *
```

#### 3.11.3 api_server/websocket/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from infrastructure.cache import CacheManager
from infrastructure.events import EventBus
from infrastructure.tracing import Tracer

# ❌ 금지되는 임포트
from api_server.routes import *
from api_server.services import *
from pipeline import *
```

#### 3.11.4 api_server/services/

```python
# ✅ 허용되는 임포트 (핵심 - 파이프라인 호출)
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector
from core_foundation.registry import ServiceRegistry, PipelineCoordinator
from infrastructure.cache import CacheManager
from infrastructure.queue import TaskQueue, JobManager
from infrastructure.events import EventBus
from infrastructure.storage import S3Storage, VideoStorage
from infrastructure.database import *
from infrastructure.tracing import Tracer
from pipeline import (
    TrainingPipeline, GamePipeline, RefereePipeline
)

# ❌ 금지되는 임포트
from api_server.routes import *           # 역방향
from api_server.middleware import *       # 역방향
```

#### 3.11.5 api_server/schemas/

```python
# ✅ 허용되는 임포트 (최소한)
from shared.constants import *
from shared.dto import *

# ❌ 금지되는 임포트 (순수 스키마 정의)
from core_foundation import *
from infrastructure import *
from api_server.routes import *
from api_server.middleware import *
from api_server.services import *
```

---

### 3.12 [Layer 10] pipeline/

```python
# ✅ 허용되는 임포트 (모든 계층 통합)
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *

# Core Foundation
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, PerformanceProfiler, ErrorTracker
from core_foundation.registry import ModelRegistry, ServiceRegistry, PipelineCoordinator
from core_foundation.resilience import CircuitBreaker, RetryMechanism

# Infrastructure
from infrastructure.cache import CacheManager, ModelCache
from infrastructure.queue import TaskQueue, JobManager
from infrastructure.events import EventBus
from infrastructure.storage import S3Storage, VideoStorage
from infrastructure.database import *
from infrastructure.tracing import Tracer

# Detection
from detection.ball_detection import BallDetector, BallTracker
from detection.court_detection import CourtDetector, CourtMapper
from detection.player_detection import PlayerDetector, PlayerTracker
from detection.hoop_detection import HoopDetector

# Pose Estimation
from pose_estimation.models import PoseModel
from pose_estimation.processors import KeypointExtractor, PoseNormalizer
from pose_estimation.validators import ConfidenceFilter, AnatomicalValidator

# Biomechanics
from biomechanics.kinematics import JointAngleCalculator, VelocityAnalyzer
from biomechanics.anthropometry import AgeGenderAdapter

# Motion Analysis
from motion_analysis.shooting import *
from motion_analysis.dribbling import *
from motion_analysis.comparison import ReferenceComparator

# Game Analysis
from game_analysis.event_detection import *
from game_analysis.statistics import *
from game_analysis.highlight import HighlightDetector, ClipExtractor
from game_analysis.game_record import GameSheetGenerator

# AI Referee
from ai_referee.rules import *
from ai_referee.violations import *
from ai_referee.fouls import *
from ai_referee.decisions import DecisionEngine

# Feedback System
from feedback_system.generators import *
from feedback_system.recommendation import TrainingRecommender
from feedback_system.report import WeeklyReportGenerator

# Learning System
from learning_system.self_learning import PatternLearner
from learning_system.calibration import ThresholdAdjuster

# ❌ 금지되는 임포트
from api_server import *  # 역방향 (api_server가 pipeline을 호출)
```

---

### 3.13 [공통] shared/

```python
# shared/constants/
# ✅ 허용되는 임포트: 없음 (순수 상수 정의)
# ❌ 금지: 모든 외부 임포트

# shared/exceptions/
# ✅ 허용되는 임포트
from shared.constants import ErrorCodes
# ❌ 금지: 그 외 모든 임포트

# shared/dto/
# ✅ 허용되는 임포트
from shared.constants import *
# ❌ 금지: 그 외 모든 임포트

# shared/interfaces/
# ✅ 허용되는 임포트
from shared.constants import *
from shared.dto import *
# ❌ 금지: 그 외 모든 임포트
```

---

### 3.14 [공통] utils/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *

# ❌ 금지되는 임포트
from core_foundation import *
from infrastructure import *
from detection import *
# ... 모든 계층 금지
```

---

### 3.15 [특수] workers/

```python
# ✅ 허용되는 임포트
from shared.constants import *
from shared.exceptions import *
from shared.dto import *
from utils import *
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector, PerformanceProfiler
from core_foundation.resilience import RetryMechanism
from infrastructure.cache import CacheManager
from infrastructure.queue import TaskQueue, JobManager
from infrastructure.events import EventBus
from infrastructure.storage import VideoStorage
from infrastructure.database import *
from infrastructure.tracing import Tracer
from pipeline import (
    VideoPipeline, TrainingPipeline, GamePipeline, RefereePipeline
)

# ❌ 금지되는 임포트
from detection import *                   # 파이프라인 통해 사용
from pose_estimation import *             # 파이프라인 통해 사용
from biomechanics import *                # 파이프라인 통해 사용
from motion_analysis import *             # 파이프라인 통해 사용
from game_analysis import *               # 파이프라인 통해 사용
from ai_referee import *                  # 파이프라인 통해 사용
from feedback_system import *             # 파이프라인 통해 사용
from learning_system import *             # 파이프라인 통해 사용
from api_server import *                  # 완전 금지
```

---

## 4. 금지 패턴 모음

### 4.1 순환 참조 (Circular Import)

```python
# ❌ 절대 금지: 순환 참조
# 파일: motion_analysis/shooting/shooting_detector.py
from feedback_system.generators import ShootingFeedback  # 금지!

# 파일: feedback_system/generators/shooting_feedback.py
from motion_analysis.shooting import ShootingDetector  # 이미 임포트됨 → 순환!
```

### 4.2 역방향 임포트 (Upward Import)

```python
# ❌ 절대 금지: 하위 계층에서 상위 계층 임포트
# 파일: detection/ball_detection/ball_detector.py
from motion_analysis.shooting import ShootingDetector  # 금지!
from game_analysis.event_detection import ShotEventDetector  # 금지!
from api_server.routes import AnalysisRoutes  # 금지!
```

### 4.3 같은 계층 내 양방향 임포트

```python
# ❌ 금지: 양방향 의존성
# 파일: infrastructure/cache/cache_manager.py
from infrastructure.database import ConnectionPool  # 허용

# 파일: infrastructure/database/connection_pool.py
from infrastructure.cache import CacheManager  # 허용되지만...

# 결과: cache ↔ database 양방향 → 하나만 허용해야 함
# 해결: database → cache 방향만 허용 (캐시가 더 기초)
```

### 4.4 건너뛰기 임포트 (Skip Import)

```python
# ⚠️ 주의: 계층 건너뛰기
# 파일: feedback_system/generators/shooting_feedback.py
from detection.ball_detection import BallDetector  # 가능하지만 비권장

# 권장: motion_analysis를 통해 간접 사용
from motion_analysis.shooting import ShootingDetector  # 이미 detection 사용
```

---

## 5. 올바른 패턴 예시

### 5.1 표준 임포트 순서

```python
# 파일: motion_analysis/shooting/shooting_detector.py

# 1. 표준 라이브러리
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

# 2. 서드파티 라이브러리
import numpy as np
import cv2

# 3. shared (공통 모듈)
from shared.constants import AnalysisType, ErrorCodes
from shared.exceptions import AnalysisException
from shared.dto import AnalysisDTO
from shared.interfaces import AnalyzerInterface

# 4. utils (유틸리티)
from utils.math_utils import calculate_angle
from utils.geometry_utils import normalize_coordinates

# 5. core_foundation (Layer 0)
from core_foundation.config import ConfigLoader
from core_foundation.monitoring import MetricsCollector

# 6. infrastructure (Layer 0.5)
from infrastructure.cache import CacheManager
from infrastructure.tracing import Tracer

# 7. detection (Layer 1)
from detection.ball_detection import BallDetector, BallState
from detection.hoop_detection import HoopDetector

# 8. pose_estimation (Layer 2)
from pose_estimation.models import PoseModel, KeypointDefinition
from pose_estimation.processors import KeypointExtractor

# 9. biomechanics (Layer 3)
from biomechanics.kinematics import JointAngleCalculator
from biomechanics.standards import AdultStandards
```

### 5.2 조건부 임포트 (선택적 의존성)

```python
# 파일: detection/ball_detection/ball_detector.py

from typing import TYPE_CHECKING

# 런타임에 필요 없는 타입 힌트용 임포트
if TYPE_CHECKING:
    from detection.court_detection import CourtMapper  # 타입 힌트만
```

### 5.3 지연 임포트 (Lazy Import)

```python
# 파일: pipeline/training_pipeline.py

class TrainingPipeline:
    def __init__(self):
        self._shooting_analyzer = None

    @property
    def shooting_analyzer(self):
        # 지연 임포트: 실제 사용 시점에 로드
        if self._shooting_analyzer is None:
            from motion_analysis.shooting import ShootingPhaseAnalyzer
            self._shooting_analyzer = ShootingPhaseAnalyzer()
        return self._shooting_analyzer
```

---

## 6. 빠른 참조표

### 6.1 "이 모듈에서 뭘 임포트할 수 있지?" 빠른 조회

| 현재 작업 모듈 | 임포트 가능 |
|---------------|------------|
| core_foundation/* | shared, utils |
| infrastructure/* | shared, utils, core_foundation |
| detection/* | shared, utils, core_foundation, infrastructure |
| pose_estimation/* | shared, utils, core_foundation, infrastructure, detection |
| biomechanics/* | shared, utils, core_foundation, infrastructure, pose_estimation |
| motion_analysis/* | shared, utils, core_foundation, infrastructure, detection, pose_estimation, biomechanics |
| game_analysis/* | shared, utils, core_foundation, infrastructure, detection, pose_estimation, motion_analysis |
| ai_referee/* | shared, utils, core_foundation, infrastructure, detection, pose_estimation, biomechanics |
| feedback_system/* | shared, utils, core_foundation, infrastructure, motion_analysis, game_analysis |
| learning_system/* | shared, utils, core_foundation, infrastructure, motion_analysis, feedback_system |
| api_server/* | 모든 계층 (pipeline 제외) |
| pipeline/* | 모든 계층 (api_server 제외) |
| workers/* | shared, utils, core_foundation, infrastructure, pipeline |

### 6.2 "이 모듈을 누가 임포트할 수 있지?" 빠른 조회

| 모듈 | 임포트 하는 곳 |
|------|---------------|
| shared/* | 모든 곳 |
| utils/* | 모든 곳 |
| core_foundation/* | 모든 곳 (shared, utils 제외) |
| infrastructure/* | Layer 1~10, workers |
| detection/* | Layer 2~10, workers(간접) |
| pose_estimation/* | Layer 3~10 |
| biomechanics/* | Layer 4, 6~10 |
| motion_analysis/* | Layer 5, 7~10 |
| game_analysis/* | Layer 7~10 |
| ai_referee/* | Layer 9, 10 |
| feedback_system/* | Layer 8~10 |
| learning_system/* | Layer 9, 10 |
| api_server/* | 없음 (최상위) |
| pipeline/* | api_server, workers |
| workers/* | 없음 (독립 실행) |

---

## 7. 버전 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0.0 | 2024-12-24 | 초기 임포트 정의서 작성 |
| 1.1.0 | 2026-02-05 | **PHASE_08 동기화 - motion_analysis 구조 개편** |
|       |            | - **defense/ 파일명 변경**: defensive_stance_analyzer → stance_analyzer, footwork_analyzer → movement_analyzer, positioning_analyzer → reaction_analyzer, defense_criteria 추가 |
|       |            | - **movement/ 구조 재설계**: sprint/jump/pivot_analyzer → footwork_analyzer 통합, movement_criteria 추가 |
|       |            | - **comparison/ 파일명 변경**: reference_comparator → template_matcher, deviation_analyzer → comparison_criteria |
|       |            | - **passing/ 확장**: passing_criteria.py 추가 |
|       |            | - **classification/ 신규**: action_types.py, action_features.py, action_classifier.py |
|       |            | - **pose_estimation 경로 업데이트**: models/processors → backends/keypoint_types/validation (v2.0.0 동기화) |
|       |            | - **player_tracker 경로 업데이트**: detection → multi_view (v4.0.0 동기화) |
|       |            | - 내부 모듈 간 규칙표에 classification 추가 |

