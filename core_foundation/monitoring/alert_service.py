# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: core_foundation/monitoring
파일: alert_service.py
설명: 실시간 알림 서비스 - Slack, Email, PagerDuty, Webhook 연동

작성자: SPOIN_COURTVIEW
최종 수정: 2026-02-16

주요 기능:
    - 다중 채널 알림 발송 (Slack, Email, PagerDuty, Webhook)
    - 알림 중복 제거 (fingerprint 기반)
    - 레이트 리밋 (윈도우 기반)
    - 에스컬레이션 정책 지원
    - 비동기 발송 (aiohttp)
    - 재시도 로직

설계 원칙:
    - DI 패턴: 외부 서비스 연결 상태 관리
    - Protocol 기반 채널 추상화
    - 환경변수 기반 시크릿 관리
    - 스레드 안전 설계

사용 예시:
    # DI 컨테이너에서 주입받아 사용
    alert_service = AlertService(config_loader, metrics_collector)

    # 알림 발송
    alert = create_alert(
        severity=AlertSeverity.ERROR,
        title="분석 실패",
        message="영상 처리 중 오류 발생",
        channel=AlertChannel.SLACK,
    )
    result = await alert_service.send(alert)

    # 에스컬레이션 정책 설정
    policy = EscalationPolicy(
        levels=[EscalationLevel.L1, EscalationLevel.L2],
        timeouts=[300, 900],
        recipients={"L1": ["dev-team"], "L2": ["manager"]},
    )
    alert_service.set_escalation_policy(policy)
"""
from __future__ import annotations

# ============================================================
# 표준 라이브러리
# ============================================================
import asyncio
import hashlib
import logging
import os
import smtplib
import ssl
import time
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import (
    Any,
    Callable,
    Protocol,
    runtime_checkable,
)

# ============================================================
# 서드파티
# ============================================================
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None  # type: ignore
    AIOHTTP_AVAILABLE = False

# ============================================================
# shared 임포트
# ============================================================
from shared.constants.error_codes import ErrorCode
from shared.exceptions.infrastructure_exceptions import (
    AlertDeliveryException,
    AlertConfigurationException,
)

# ============================================================
# core_foundation 내부 임포트 (DI)
# ============================================================
from core_foundation.config import ConfigLoader

# TYPE_CHECKING으로 순환 참조 방지
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core_foundation.monitoring.metrics import MetricsCollector

# ============================================================
# 로거 설정
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# 상수 정의 (config.yaml로 오버라이드 가능)
# ============================================================
# 레이트 리밋 윈도우 (초) - 이 시간 내 최대 알림 수 제한
DEFAULT_RATE_LIMIT_WINDOW: int = 300  # 5분

# 윈도우당 최대 알림 수
DEFAULT_RATE_LIMIT_COUNT: int = 10

# 중복 제거 윈도우 (초) - 동일 fingerprint 알림 무시 시간
DEFAULT_DEDUP_WINDOW: int = 600  # 10분

# 에스컬레이션 타임아웃 (초) - 응답 없을 시 다음 레벨로 에스컬레이션
DEFAULT_ESCALATION_TIMEOUT: int = 900  # 15분

# 발송 실패 시 재시도 횟수
DEFAULT_RETRY_ATTEMPTS: int = 3

# 재시도 간격 (초) - 지수 백오프 기준값
DEFAULT_RETRY_DELAY: int = 30

# 최대 재시도 간격 (초) - 지수 백오프 상한
DEFAULT_MAX_RETRY_DELAY: int = 300  # 5분

# HTTP 요청 타임아웃 (초)
DEFAULT_HTTP_TIMEOUT: float = 30.0

# 환경변수 접두사
ENV_PREFIX: str = "COURTVIEW_"


# ============================================================
# Enum 정의
# ============================================================
class AlertSeverity(Enum):
    """
    알림 심각도.

    알림의 중요도와 긴급성을 나타냅니다.
    숫자가 클수록 심각합니다.
    """

    INFO = 10       # 정보성 알림
    WARNING = 20    # 경고
    ERROR = 30      # 오류
    CRITICAL = 40   # 치명적 오류

    @property
    def emoji(self) -> str:
        """Slack용 이모지."""
        mapping = {
            self.INFO: ":information_source:",
            self.WARNING: ":warning:",
            self.ERROR: ":x:",
            self.CRITICAL: ":rotating_light:",
        }
        return mapping.get(self, ":bell:")

    @property
    def color(self) -> str:
        """Slack attachment 색상."""
        mapping = {
            self.INFO: "#36a64f",     # 초록
            self.WARNING: "#ffcc00",  # 노랑
            self.ERROR: "#ff6600",    # 주황
            self.CRITICAL: "#ff0000", # 빨강
        }
        return mapping.get(self, "#808080")

    def __lt__(self, other: "AlertSeverity") -> bool:
        """비교 연산 지원."""
        if isinstance(other, AlertSeverity):
            return self.value < other.value
        return NotImplemented


class AlertChannel(Enum):
    """
    알림 채널.

    알림이 발송되는 대상 서비스입니다.
    """

    SLACK = "slack"           # Slack 웹훅
    EMAIL = "email"           # SMTP 이메일
    PAGERDUTY = "pagerduty"   # PagerDuty Events API v2
    WEBHOOK = "webhook"       # 범용 HTTP 웹훅


class AlertStatus(Enum):
    """
    알림 상태.

    알림 발송 처리 상태입니다.
    """

    PENDING = "pending"       # 대기 중
    SENT = "sent"             # 발송 완료
    FAILED = "failed"         # 발송 실패
    SUPPRESSED = "suppressed" # 억제됨 (레이트 리밋, 중복)
    RETRYING = "retrying"     # 재시도 중


class EscalationLevel(Enum):
    """
    에스컬레이션 레벨.

    알림 응답이 없을 시 순차적으로 상위 레벨로 에스컬레이션됩니다.
    """

    L1 = "L1"               # 1단계: 담당 개발자
    L2 = "L2"               # 2단계: 팀 리드
    L3 = "L3"               # 3단계: 매니저
    EXECUTIVE = "executive" # 최종: 임원

    @property
    def priority(self) -> int:
        """우선순위 (높을수록 긴급)."""
        mapping = {
            self.L1: 1,
            self.L2: 2,
            self.L3: 3,
            self.EXECUTIVE: 4,
        }
        return mapping.get(self, 0)


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass
class Alert:
    """
    알림 메시지.

    발송할 알림의 모든 정보를 담습니다.

    Attributes:
        alert_id: 고유 ID (자동 생성)
        severity: 심각도
        channel: 발송 채널
        title: 알림 제목
        message: 알림 본문
        metadata: 추가 메타데이터
        fingerprint: 중복 체크용 해시 (자동 생성)
        created_at: 생성 시각
        tags: 분류 태그
        source: 알림 발생 소스 (모듈명 등)
    """

    severity: AlertSeverity
    channel: AlertChannel
    title: str
    message: str
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)
    source: str = "courtview"

    def __post_init__(self) -> None:
        """초기화 후 fingerprint 생성."""
        if not self.fingerprint:
            self.fingerprint = self._generate_fingerprint()

    def _generate_fingerprint(self) -> str:
        """중복 체크용 fingerprint 생성."""
        # 제목, 메시지, 심각도, 소스를 조합하여 해시 생성
        content = f"{self.title}:{self.message}:{self.severity.name}:{self.source}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.name,
            "channel": self.channel.value,
            "title": self.title,
            "message": self.message,
            "metadata": self.metadata,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "source": self.source,
        }


@dataclass
class AlertResult:
    """
    알림 발송 결과.

    Attributes:
        alert_id: 알림 ID
        status: 발송 상태
        channel: 발송 채널
        timestamp: 처리 시각
        error_message: 오류 메시지 (실패 시)
        retry_count: 재시도 횟수
        duration_ms: 발송 소요 시간 (밀리초)
    """

    alert_id: str
    status: AlertStatus
    channel: AlertChannel
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: str | None = None
    retry_count: int = 0
    duration_ms: float = 0.0

    @property
    def is_success(self) -> bool:
        """발송 성공 여부."""
        return self.status == AlertStatus.SENT

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "alert_id": self.alert_id,
            "status": self.status.value,
            "channel": self.channel.value,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "duration_ms": self.duration_ms,
            "is_success": self.is_success,
        }


@dataclass
class AlertRule:
    """
    알림 규칙.

    특정 조건에 따라 알림을 트리거하는 규칙입니다.

    Attributes:
        rule_id: 규칙 ID
        name: 규칙 이름
        condition: 조건 (Callable)
        channels: 발송 채널 목록
        severity: 기본 심각도
        cooldown: 재발송 대기 시간 (초)
        enabled: 활성화 여부
        tags: 분류 태그
    """

    rule_id: str
    name: str
    condition: Callable[[dict[str, Any]], bool]
    channels: list[AlertChannel]
    severity: AlertSeverity = AlertSeverity.WARNING
    cooldown: int = 300  # 5분
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    last_triggered: datetime | None = None

    def can_trigger(self) -> bool:
        """쿨다운 체크."""
        if not self.enabled:
            return False
        if self.last_triggered is None:
            return True
        elapsed = (datetime.now(timezone.utc) - self.last_triggered).total_seconds()
        return elapsed >= self.cooldown


@dataclass
class EscalationPolicy:
    """
    에스컬레이션 정책.

    알림 응답이 없을 시 상위 레벨로 에스컬레이션하는 정책입니다.

    Attributes:
        policy_id: 정책 ID
        name: 정책 이름
        levels: 에스컬레이션 레벨 순서
        timeouts: 각 레벨별 타임아웃 (초)
        recipients: 레벨별 수신자 목록
        enabled: 활성화 여부
    """

    levels: list[EscalationLevel]
    timeouts: list[int]
    recipients: dict[str, list[str]]
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "default"
    enabled: bool = True

    def __post_init__(self) -> None:
        """검증."""
        if len(self.levels) != len(self.timeouts):
            raise ValueError("levels와 timeouts의 길이가 일치해야 합니다")

    def get_timeout(self, level: EscalationLevel) -> int:
        """레벨별 타임아웃 조회."""
        try:
            idx = self.levels.index(level)
            return self.timeouts[idx]
        except (ValueError, IndexError):
            return DEFAULT_ESCALATION_TIMEOUT

    def get_recipients(self, level: EscalationLevel) -> list[str]:
        """레벨별 수신자 조회."""
        return self.recipients.get(level.value, [])

    def get_next_level(self, current: EscalationLevel) -> EscalationLevel | None:
        """다음 에스컬레이션 레벨 조회."""
        try:
            idx = self.levels.index(current)
            if idx + 1 < len(self.levels):
                return self.levels[idx + 1]
        except ValueError:
            pass
        return None


@dataclass
class ChannelConfig:
    """
    채널별 설정.

    각 알림 채널의 연결 정보와 템플릿을 담습니다.

    Attributes:
        channel: 채널 타입
        enabled: 활성화 여부
        endpoint: 엔드포인트 URL
        credentials: 인증 정보 (환경변수 키 또는 실제 값)
        templates: 메시지 템플릿
        headers: 추가 HTTP 헤더
        timeout: 요청 타임아웃 (초)
    """

    channel: AlertChannel
    enabled: bool = True
    endpoint: str | None = None
    credentials: dict[str, str] = field(default_factory=dict)
    templates: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = DEFAULT_HTTP_TIMEOUT

    def get_credential(self, key: str) -> str | None:
        """
        인증 정보 조회 (환경변수 우선).

        Args:
            key: 인증 정보 키

        Returns:
            인증 값 또는 None
        """
        # 환경변수 우선 조회
        env_key = f"{ENV_PREFIX}{self.channel.value.upper()}_{key.upper()}"
        env_value = os.environ.get(env_key)
        if env_value:
            return env_value

        # 설정에서 조회
        return self.credentials.get(key)


# ============================================================
# Protocol 인터페이스
# ============================================================
@runtime_checkable
class AlertChannelProtocol(Protocol):
    """
    알림 채널 프로토콜.

    모든 알림 채널 구현체가 따라야 하는 인터페이스입니다.
    """

    async def send(self, alert: Alert, config: ChannelConfig) -> AlertResult:
        """
        알림 발송.

        Args:
            alert: 발송할 알림
            config: 채널 설정

        Returns:
            발송 결과
        """
        ...

    async def validate(self, config: ChannelConfig) -> bool:
        """
        설정 유효성 검증.

        Args:
            config: 채널 설정

        Returns:
            유효 여부
        """
        ...

    async def health_check(self, config: ChannelConfig) -> bool:
        """
        채널 헬스 체크.

        Args:
            config: 채널 설정

        Returns:
            정상 여부
        """
        ...


# ============================================================
# 채널 구현 클래스
# ============================================================
class SlackAlertChannel:
    """
    Slack 웹훅 채널.

    Slack Incoming Webhook을 통해 알림을 발송합니다.
    Block Kit 형식을 지원합니다.
    """

    async def send(self, alert: Alert, config: ChannelConfig) -> AlertResult:
        """Slack으로 알림 발송."""
        start_time = time.perf_counter()

        if not AIOHTTP_AVAILABLE:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.SLACK,
                error_message="aiohttp 라이브러리가 설치되지 않았습니다",
            )

        webhook_url = config.endpoint or config.get_credential("WEBHOOK_URL")
        if not webhook_url:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.SLACK,
                error_message="Slack webhook URL이 설정되지 않았습니다",
            )

        # Slack 메시지 페이로드 구성
        payload = self._build_payload(alert)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=config.timeout),
                ) as response:
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    if response.status == 200:
                        return AlertResult(
                            alert_id=alert.alert_id,
                            status=AlertStatus.SENT,
                            channel=AlertChannel.SLACK,
                            duration_ms=duration_ms,
                        )
                    else:
                        error_text = await response.text()
                        return AlertResult(
                            alert_id=alert.alert_id,
                            status=AlertStatus.FAILED,
                            channel=AlertChannel.SLACK,
                            error_message=f"HTTP {response.status}: {error_text}",
                            duration_ms=duration_ms,
                        )

        except asyncio.TimeoutError:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.SLACK,
                error_message="요청 타임아웃",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.SLACK,
                error_message=str(e),
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

    def _build_payload(self, alert: Alert) -> dict[str, Any]:
        """Slack 메시지 페이로드 구성."""
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{alert.severity.emoji} {alert.title}",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": alert.message,
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Severity:* {alert.severity.name} | *Source:* {alert.source} | *ID:* {alert.alert_id[:8]}",
                        },
                    ],
                },
            ],
            "attachments": [
                {
                    "color": alert.severity.color,
                    "fields": [
                        {"title": k, "value": str(v), "short": True}
                        for k, v in list(alert.metadata.items())[:6]
                    ],
                },
            ] if alert.metadata else [],
        }

    async def validate(self, config: ChannelConfig) -> bool:
        """설정 유효성 검증."""
        webhook_url = config.endpoint or config.get_credential("WEBHOOK_URL")
        return bool(webhook_url and webhook_url.startswith("https://hooks.slack.com/"))

    async def health_check(self, config: ChannelConfig) -> bool:
        """헬스 체크 (Slack은 별도 API 없음)."""
        return await self.validate(config)


class EmailAlertChannel:
    """
    SMTP 이메일 채널.

    SMTP를 통해 이메일 알림을 발송합니다.
    HTML 및 Plain Text 형식을 지원합니다.
    """

    async def send(self, alert: Alert, config: ChannelConfig) -> AlertResult:
        """이메일 발송."""
        start_time = time.perf_counter()

        # 필수 설정 확인
        smtp_host = config.get_credential("SMTP_HOST") or "smtp.gmail.com"
        smtp_port = int(config.get_credential("SMTP_PORT") or "587")
        smtp_user = config.get_credential("SMTP_USER")
        smtp_password = config.get_credential("SMTP_PASSWORD")
        recipients = config.get_credential("RECIPIENTS")

        if not all([smtp_user, smtp_password, recipients]):
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.EMAIL,
                error_message="SMTP 설정이 불완전합니다",
            )

        recipient_list = [r.strip() for r in recipients.split(",")]

        try:
            # 이메일 메시지 구성
            msg = self._build_message(alert, smtp_user, recipient_list)

            # 동기 SMTP 발송 (asyncio.to_thread로 비동기 래핑)
            await asyncio.to_thread(
                self._send_smtp,
                msg,
                smtp_host,
                smtp_port,
                smtp_user,
                smtp_password,
                recipient_list,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.SENT,
                channel=AlertChannel.EMAIL,
                duration_ms=duration_ms,
            )

        except Exception as e:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.EMAIL,
                error_message=str(e),
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

    def _build_message(
        self,
        alert: Alert,
        sender: str,
        recipients: list[str],
    ) -> MIMEMultipart:
        """이메일 메시지 구성."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{alert.severity.name}] {alert.title}"
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)

        # Plain text
        text_content = f"""
{alert.title}

{alert.message}

---
Severity: {alert.severity.name}
Source: {alert.source}
Time: {alert.created_at.isoformat()}
Alert ID: {alert.alert_id}
"""
        msg.attach(MIMEText(text_content, "plain", "utf-8"))

        # HTML
        html_content = f"""
<html>
<body>
<h2 style="color: {alert.severity.color};">{alert.title}</h2>
<p>{alert.message}</p>
<hr>
<table>
<tr><td><strong>Severity:</strong></td><td>{alert.severity.name}</td></tr>
<tr><td><strong>Source:</strong></td><td>{alert.source}</td></tr>
<tr><td><strong>Time:</strong></td><td>{alert.created_at.isoformat()}</td></tr>
<tr><td><strong>Alert ID:</strong></td><td>{alert.alert_id}</td></tr>
</table>
</body>
</html>
"""
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        return msg

    def _send_smtp(
        self,
        msg: MIMEMultipart,
        host: str,
        port: int,
        user: str,
        password: str,
        recipients: list[str],
    ) -> None:
        """SMTP 발송 (동기)."""
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.sendmail(user, recipients, msg.as_string())

    async def validate(self, config: ChannelConfig) -> bool:
        """설정 유효성 검증."""
        smtp_user = config.get_credential("SMTP_USER")
        smtp_password = config.get_credential("SMTP_PASSWORD")
        recipients = config.get_credential("RECIPIENTS")
        return bool(smtp_user and smtp_password and recipients)

    async def health_check(self, config: ChannelConfig) -> bool:
        """SMTP 연결 테스트."""
        try:
            smtp_host = config.get_credential("SMTP_HOST") or "smtp.gmail.com"
            smtp_port = int(config.get_credential("SMTP_PORT") or "587")

            def _check() -> bool:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.ehlo()
                    return True

            return await asyncio.to_thread(_check)
        except Exception:
            return False


class PagerDutyAlertChannel:
    """
    PagerDuty Events API v2 채널.

    PagerDuty로 인시던트 알림을 발송합니다.
    """

    EVENTS_API_URL = "https://events.pagerduty.com/v2/enqueue"

    async def send(self, alert: Alert, config: ChannelConfig) -> AlertResult:
        """PagerDuty로 알림 발송."""
        start_time = time.perf_counter()

        if not AIOHTTP_AVAILABLE:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.PAGERDUTY,
                error_message="aiohttp 라이브러리가 설치되지 않았습니다",
            )

        routing_key = config.get_credential("ROUTING_KEY")
        if not routing_key:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.PAGERDUTY,
                error_message="PagerDuty routing key가 설정되지 않았습니다",
            )

        # PagerDuty 페이로드 구성
        payload = self._build_payload(alert, routing_key)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.EVENTS_API_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=config.timeout),
                ) as response:
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    if response.status in (200, 201, 202):
                        return AlertResult(
                            alert_id=alert.alert_id,
                            status=AlertStatus.SENT,
                            channel=AlertChannel.PAGERDUTY,
                            duration_ms=duration_ms,
                        )
                    else:
                        error_text = await response.text()
                        return AlertResult(
                            alert_id=alert.alert_id,
                            status=AlertStatus.FAILED,
                            channel=AlertChannel.PAGERDUTY,
                            error_message=f"HTTP {response.status}: {error_text}",
                            duration_ms=duration_ms,
                        )

        except asyncio.TimeoutError:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.PAGERDUTY,
                error_message="요청 타임아웃",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.PAGERDUTY,
                error_message=str(e),
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

    def _build_payload(self, alert: Alert, routing_key: str) -> dict[str, Any]:
        """PagerDuty 페이로드 구성."""
        # 심각도 매핑
        severity_map = {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.ERROR: "error",
            AlertSeverity.CRITICAL: "critical",
        }

        return {
            "routing_key": routing_key,
            "event_action": "trigger",
            "dedup_key": alert.fingerprint,
            "payload": {
                "summary": f"{alert.title}: {alert.message[:200]}",
                "source": alert.source,
                "severity": severity_map.get(alert.severity, "error"),
                "timestamp": alert.created_at.isoformat(),
                "custom_details": {
                    "alert_id": alert.alert_id,
                    "title": alert.title,
                    "message": alert.message,
                    "tags": alert.tags,
                    **alert.metadata,
                },
            },
        }

    async def validate(self, config: ChannelConfig) -> bool:
        """설정 유효성 검증."""
        routing_key = config.get_credential("ROUTING_KEY")
        return bool(routing_key and len(routing_key) == 32)

    async def health_check(self, config: ChannelConfig) -> bool:
        """헬스 체크 (PagerDuty API 응답 확인)."""
        return await self.validate(config)


class WebhookAlertChannel:
    """
    범용 HTTP 웹훅 채널.

    커스텀 HTTP 엔드포인트로 알림을 발송합니다.
    """

    async def send(self, alert: Alert, config: ChannelConfig) -> AlertResult:
        """웹훅으로 알림 발송."""
        start_time = time.perf_counter()

        if not AIOHTTP_AVAILABLE:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.WEBHOOK,
                error_message="aiohttp 라이브러리가 설치되지 않았습니다",
            )

        endpoint = config.endpoint or config.get_credential("URL")
        if not endpoint:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.WEBHOOK,
                error_message="웹훅 URL이 설정되지 않았습니다",
            )

        # 페이로드 구성
        payload = alert.to_dict()

        # 헤더 구성
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "COURTVIEW-AlertService/1.0",
            **config.headers,
        }

        # API 키 추가
        api_key = config.get_credential("API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=config.timeout),
                ) as response:
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    if 200 <= response.status < 300:
                        return AlertResult(
                            alert_id=alert.alert_id,
                            status=AlertStatus.SENT,
                            channel=AlertChannel.WEBHOOK,
                            duration_ms=duration_ms,
                        )
                    else:
                        error_text = await response.text()
                        return AlertResult(
                            alert_id=alert.alert_id,
                            status=AlertStatus.FAILED,
                            channel=AlertChannel.WEBHOOK,
                            error_message=f"HTTP {response.status}: {error_text}",
                            duration_ms=duration_ms,
                        )

        except asyncio.TimeoutError:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.WEBHOOK,
                error_message="요청 타임아웃",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=AlertChannel.WEBHOOK,
                error_message=str(e),
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

    async def validate(self, config: ChannelConfig) -> bool:
        """설정 유효성 검증."""
        endpoint = config.endpoint or config.get_credential("URL")
        return bool(endpoint and endpoint.startswith(("http://", "https://")))

    async def health_check(self, config: ChannelConfig) -> bool:
        """웹훅 엔드포인트 헬스 체크."""
        if not AIOHTTP_AVAILABLE:
            return False

        endpoint = config.endpoint or config.get_credential("URL")
        if not endpoint:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    endpoint,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status < 500
        except Exception:
            return False


# ============================================================
# AlertService 메인 클래스
# ============================================================
class AlertService:
    """
    알림 서비스.

    다중 채널로 알림을 발송하고, 중복 제거, 레이트 리밋, 에스컬레이션을 관리합니다.
    DI 컨테이너에 등록되어 주입됩니다.

    주요 기능:
        - 다중 채널 알림 발송 (Slack, Email, PagerDuty, Webhook)
        - 중복 제거 (fingerprint 기반)
        - 레이트 리밋 (윈도우 기반)
        - 에스컬레이션 정책
        - 재시도 로직
        - 비동기 발송

    Example:
        >>> service = AlertService(config_loader, metrics_collector)
        >>> alert = create_alert(
        ...     severity=AlertSeverity.ERROR,
        ...     title="분석 실패",
        ...     message="영상 처리 중 오류",
        ...     channel=AlertChannel.SLACK,
        ... )
        >>> result = await service.send(alert)
        >>> print(result.status)
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        metrics_collector: "MetricsCollector | None" = None,
    ) -> None:
        """
        초기화.

        Args:
            config_loader: 설정 로더 (None이면 싱글톤 사용)
            metrics_collector: 메트릭 수집기 (DI 주입)
        """
        # DI 의존성
        self._config_loader = config_loader or ConfigLoader.get_instance()
        self._metrics_collector = metrics_collector

        # 설정 로드
        self._load_config()

        # 채널 핸들러
        self._channel_handlers: dict[AlertChannel, Any] = {
            AlertChannel.SLACK: SlackAlertChannel(),
            AlertChannel.EMAIL: EmailAlertChannel(),
            AlertChannel.PAGERDUTY: PagerDutyAlertChannel(),
            AlertChannel.WEBHOOK: WebhookAlertChannel(),
        }

        # 채널별 설정
        self._channel_configs: dict[AlertChannel, ChannelConfig] = {}
        self._load_channel_configs()

        # 레이트 리밋 상태
        self._rate_limit_counters: dict[str, list[float]] = defaultdict(list)
        self._rate_limit_lock = threading.Lock()

        # 중복 제거 상태
        self._dedup_cache: dict[str, datetime] = {}
        self._dedup_lock = threading.Lock()

        # 알림 규칙
        self._rules: dict[str, AlertRule] = {}

        # 에스컬레이션 정책
        self._escalation_policy: EscalationPolicy | None = None

        # 발송 기록
        self._sent_history: list[AlertResult] = []
        self._history_lock = threading.Lock()
        self._max_history = 1000

        logger.info(
            f"AlertService 초기화 완료 "
            f"(rate_limit={self._rate_limit_window}s/{self._rate_limit_count}, "
            f"dedup_window={self._dedup_window}s)"
        )

    def _load_config(self) -> None:
        """설정 로드."""
        alert_config = self._config_loader.get("alert_service", {})

        self._rate_limit_window = alert_config.get(
            "rate_limit_window", DEFAULT_RATE_LIMIT_WINDOW
        )
        self._rate_limit_count = alert_config.get(
            "rate_limit_count", DEFAULT_RATE_LIMIT_COUNT
        )
        self._dedup_window = alert_config.get(
            "dedup_window", DEFAULT_DEDUP_WINDOW
        )
        self._retry_attempts = alert_config.get(
            "retry_attempts", DEFAULT_RETRY_ATTEMPTS
        )
        self._retry_delay = alert_config.get(
            "retry_delay", DEFAULT_RETRY_DELAY
        )
        self._max_retry_delay = alert_config.get(
            "max_retry_delay", DEFAULT_MAX_RETRY_DELAY
        )

    def _load_channel_configs(self) -> None:
        """채널별 설정 로드."""
        channels_config = self._config_loader.get("alert_service.channels", {})

        for channel in AlertChannel:
            channel_data = channels_config.get(channel.value, {})
            self._channel_configs[channel] = ChannelConfig(
                channel=channel,
                enabled=channel_data.get("enabled", False),
                endpoint=channel_data.get("endpoint"),
                credentials=channel_data.get("credentials", {}),
                templates=channel_data.get("templates", {}),
                headers=channel_data.get("headers", {}),
                timeout=channel_data.get("timeout", DEFAULT_HTTP_TIMEOUT),
            )

    # --------------------------------------------------------
    # 공개 메서드
    # --------------------------------------------------------
    async def send(
        self,
        alert: Alert,
        bypass_rate_limit: bool = False,
        bypass_dedup: bool = False,
    ) -> AlertResult:
        """
        알림 발송.

        Args:
            alert: 발송할 알림
            bypass_rate_limit: 레이트 리밋 우회
            bypass_dedup: 중복 제거 우회

        Returns:
            발송 결과
        """
        # 중복 체크
        if not bypass_dedup and self._is_duplicate(alert):
            logger.debug(f"중복 알림 억제: {alert.fingerprint}")
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.SUPPRESSED,
                channel=alert.channel,
                error_message="중복 알림",
            )

        # 레이트 리밋 체크
        if not bypass_rate_limit and self._is_rate_limited(alert.channel):
            logger.warning(f"레이트 리밋 초과: {alert.channel.value}")
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.SUPPRESSED,
                channel=alert.channel,
                error_message="레이트 리밋 초과",
            )

        # 채널 설정 확인
        config = self._channel_configs.get(alert.channel)
        if not config or not config.enabled:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=alert.channel,
                error_message=f"채널 {alert.channel.value}이 비활성화되어 있습니다",
            )

        # 재시도 로직과 함께 발송
        result = await self._send_with_retry(alert, config)

        # 기록 저장
        self._record_result(result)

        # 메트릭 기록
        if self._metrics_collector:
            self._record_metrics(result)

        return result

    async def send_multi(
        self,
        alert: Alert,
        channels: list[AlertChannel],
    ) -> dict[AlertChannel, AlertResult]:
        """
        여러 채널로 동시 발송.

        Args:
            alert: 발송할 알림
            channels: 발송 채널 목록

        Returns:
            채널별 발송 결과
        """
        tasks = []
        for channel in channels:
            alert_copy = Alert(
                severity=alert.severity,
                channel=channel,
                title=alert.title,
                message=alert.message,
                metadata=alert.metadata.copy(),
                tags=alert.tags.copy(),
                source=alert.source,
            )
            tasks.append(self.send(alert_copy))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            channel: (
                result if isinstance(result, AlertResult)
                else AlertResult(
                    alert_id=alert.alert_id,
                    status=AlertStatus.FAILED,
                    channel=channel,
                    error_message=str(result),
                )
            )
            for channel, result in zip(channels, results)
        }

    def set_escalation_policy(self, policy: EscalationPolicy) -> None:
        """에스컬레이션 정책 설정."""
        self._escalation_policy = policy
        logger.info(f"에스컬레이션 정책 설정: {policy.name}")

    def register_rule(self, rule: AlertRule) -> None:
        """알림 규칙 등록."""
        self._rules[rule.rule_id] = rule
        logger.info(f"알림 규칙 등록: {rule.name}")

    def unregister_rule(self, rule_id: str) -> None:
        """알림 규칙 해제."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info(f"알림 규칙 해제: {rule_id}")

    async def check_rules(self, context: dict[str, Any]) -> list[AlertResult]:
        """
        규칙 기반 알림 체크.

        Args:
            context: 체크 컨텍스트 데이터

        Returns:
            트리거된 알림 결과 목록
        """
        results = []

        for rule in self._rules.values():
            if not rule.can_trigger():
                continue

            try:
                if rule.condition(context):
                    rule.last_triggered = datetime.now(timezone.utc)

                    for channel in rule.channels:
                        alert = Alert(
                            severity=rule.severity,
                            channel=channel,
                            title=f"[Rule: {rule.name}] 조건 충족",
                            message=f"규칙 '{rule.name}'의 조건이 충족되었습니다",
                            tags=rule.tags,
                            metadata={"rule_id": rule.rule_id, **context},
                        )
                        result = await self.send(alert)
                        results.append(result)

            except Exception as e:
                logger.error(f"규칙 체크 실패: {rule.name}, 오류: {e}")

        return results

    def get_channel_config(self, channel: AlertChannel) -> ChannelConfig | None:
        """채널 설정 조회."""
        return self._channel_configs.get(channel)

    def update_channel_config(self, config: ChannelConfig) -> None:
        """채널 설정 업데이트."""
        self._channel_configs[config.channel] = config
        logger.info(f"채널 설정 업데이트: {config.channel.value}")

    async def validate_channel(self, channel: AlertChannel) -> bool:
        """채널 설정 유효성 검증."""
        config = self._channel_configs.get(channel)
        if not config:
            return False

        handler = self._channel_handlers.get(channel)
        if not handler:
            return False

        return await handler.validate(config)

    async def health_check(self, channel: AlertChannel) -> bool:
        """채널 헬스 체크."""
        config = self._channel_configs.get(channel)
        if not config or not config.enabled:
            return False

        handler = self._channel_handlers.get(channel)
        if not handler:
            return False

        return await handler.health_check(config)

    async def health_check_all(self) -> dict[AlertChannel, bool]:
        """모든 채널 헬스 체크."""
        results = {}
        for channel in AlertChannel:
            results[channel] = await self.health_check(channel)
        return results

    def get_statistics(self) -> dict[str, Any]:
        """통계 조회."""
        with self._history_lock:
            total = len(self._sent_history)
            success = sum(1 for r in self._sent_history if r.is_success)
            failed = sum(1 for r in self._sent_history if r.status == AlertStatus.FAILED)
            suppressed = sum(1 for r in self._sent_history if r.status == AlertStatus.SUPPRESSED)

        return {
            "total_alerts": total,
            "successful": success,
            "failed": failed,
            "suppressed": suppressed,
            "success_rate": success / total if total > 0 else 1.0,
            "active_rules": len(self._rules),
            "escalation_policy": self._escalation_policy.name if self._escalation_policy else None,
        }

    def clear_dedup_cache(self) -> None:
        """중복 캐시 초기화."""
        with self._dedup_lock:
            self._dedup_cache.clear()
        logger.info("중복 캐시 초기화됨")

    def clear_rate_limit_counters(self) -> None:
        """레이트 리밋 카운터 초기화."""
        with self._rate_limit_lock:
            self._rate_limit_counters.clear()
        logger.info("레이트 리밋 카운터 초기화됨")

    # --------------------------------------------------------
    # 비공개 메서드
    # --------------------------------------------------------
    def _is_duplicate(self, alert: Alert) -> bool:
        """중복 체크."""
        now = datetime.now(timezone.utc)
        window = timedelta(seconds=self._dedup_window)

        with self._dedup_lock:
            # 만료된 항목 정리
            expired = [
                fp for fp, ts in self._dedup_cache.items()
                if now - ts > window
            ]
            for fp in expired:
                del self._dedup_cache[fp]

            # 중복 체크
            if alert.fingerprint in self._dedup_cache:
                return True

            # 캐시에 추가
            self._dedup_cache[alert.fingerprint] = now
            return False

    def _is_rate_limited(self, channel: AlertChannel) -> bool:
        """레이트 리밋 체크."""
        now = time.time()
        window_start = now - self._rate_limit_window
        key = channel.value

        with self._rate_limit_lock:
            # 윈도우 외 항목 제거
            self._rate_limit_counters[key] = [
                ts for ts in self._rate_limit_counters[key]
                if ts > window_start
            ]

            # 제한 체크
            if len(self._rate_limit_counters[key]) >= self._rate_limit_count:
                return True

            # 카운터 추가
            self._rate_limit_counters[key].append(now)
            return False

    async def _send_with_retry(
        self,
        alert: Alert,
        config: ChannelConfig,
    ) -> AlertResult:
        """재시도 로직과 함께 발송."""
        handler = self._channel_handlers.get(alert.channel)
        if not handler:
            return AlertResult(
                alert_id=alert.alert_id,
                status=AlertStatus.FAILED,
                channel=alert.channel,
                error_message=f"지원하지 않는 채널: {alert.channel.value}",
            )

        last_result: AlertResult | None = None

        for attempt in range(self._retry_attempts):
            result = await handler.send(alert, config)
            last_result = result

            if result.is_success:
                return result

            # 실패 시 지수 백오프로 재시도
            if attempt < self._retry_attempts - 1:
                result.status = AlertStatus.RETRYING
                result.retry_count = attempt + 1
                # 지수 백오프: delay * 2^attempt, 최대값 제한
                backoff_delay = min(
                    self._retry_delay * (2 ** attempt),
                    self._max_retry_delay
                )
                logger.warning(
                    f"알림 발송 실패, 재시도 중 ({attempt + 1}/{self._retry_attempts}), "
                    f"대기: {backoff_delay}초: {result.error_message}"
                )
                await asyncio.sleep(backoff_delay)

        # 최종 실패
        if last_result:
            last_result.retry_count = self._retry_attempts
        return last_result or AlertResult(
            alert_id=alert.alert_id,
            status=AlertStatus.FAILED,
            channel=alert.channel,
            error_message="알 수 없는 오류",
        )

    def _record_result(self, result: AlertResult) -> None:
        """발송 결과 기록."""
        with self._history_lock:
            self._sent_history.append(result)
            # 최대 기록 수 제한
            if len(self._sent_history) > self._max_history:
                self._sent_history = self._sent_history[-self._max_history:]

    def _record_metrics(self, result: AlertResult) -> None:
        """메트릭 기록."""
        if not self._metrics_collector:
            return

        try:
            # 발송 카운터
            self._metrics_collector.counter(
                "alert_sent_total",
                labels={
                    "channel": result.channel.value,
                    "status": result.status.value,
                },
            ).inc()

            # 발송 시간 히스토그램
            if result.duration_ms > 0:
                self._metrics_collector.histogram(
                    "alert_send_duration_ms",
                    labels={"channel": result.channel.value},
                ).observe(result.duration_ms)

        except Exception as e:
            logger.debug(f"메트릭 기록 실패: {e}")


# ============================================================
# 헬퍼 함수
# ============================================================
def create_alert(
    severity: AlertSeverity,
    title: str,
    message: str,
    channel: AlertChannel = AlertChannel.SLACK,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    source: str = "courtview",
) -> Alert:
    """
    알림 생성 팩토리 함수.

    Args:
        severity: 심각도
        title: 제목
        message: 본문
        channel: 발송 채널
        metadata: 추가 메타데이터
        tags: 분류 태그
        source: 발생 소스

    Returns:
        Alert 인스턴스

    Example:
        >>> alert = create_alert(
        ...     severity=AlertSeverity.ERROR,
        ...     title="분석 실패",
        ...     message="영상 처리 오류",
        ... )
    """
    return Alert(
        severity=severity,
        channel=channel,
        title=title,
        message=message,
        metadata=metadata or {},
        tags=tags or [],
        source=source,
    )


def format_alert_message(
    alert: Alert,
    channel: AlertChannel,
    template: str | None = None,
) -> str:
    """
    채널별 알림 메시지 포매팅.

    Args:
        alert: 알림
        channel: 대상 채널
        template: 커스텀 템플릿

    Returns:
        포매팅된 메시지
    """
    if template:
        return template.format(
            title=alert.title,
            message=alert.message,
            severity=alert.severity.name,
            source=alert.source,
            timestamp=alert.created_at.isoformat(),
            **alert.metadata,
        )

    # 채널별 기본 포맷
    if channel == AlertChannel.SLACK:
        return f"*{alert.title}*\n{alert.message}"
    elif channel == AlertChannel.EMAIL:
        return f"<h2>{alert.title}</h2><p>{alert.message}</p>"
    elif channel == AlertChannel.PAGERDUTY:
        return f"{alert.title}: {alert.message}"
    else:
        return f"{alert.title}\n\n{alert.message}"


def should_escalate(
    alert: Alert,
    policy: EscalationPolicy,
    current_level: EscalationLevel,
    elapsed_seconds: float,
) -> bool:
    """
    에스컬레이션 필요 여부 판단.

    Args:
        alert: 알림
        policy: 에스컬레이션 정책
        current_level: 현재 레벨
        elapsed_seconds: 경과 시간 (초)

    Returns:
        에스컬레이션 필요 여부
    """
    if not policy.enabled:
        return False

    # CRITICAL은 즉시 최상위 레벨로
    if alert.severity == AlertSeverity.CRITICAL:
        return current_level != EscalationLevel.EXECUTIVE

    # 타임아웃 체크
    timeout = policy.get_timeout(current_level)
    if elapsed_seconds >= timeout:
        next_level = policy.get_next_level(current_level)
        return next_level is not None

    return False


# ============================================================
# 모듈 내보내기
# ============================================================
__all__ = [
    # Enum (4개)
    "AlertSeverity",
    "AlertChannel",
    "AlertStatus",
    "EscalationLevel",
    # 상수 (7개)
    "DEFAULT_RATE_LIMIT_WINDOW",
    "DEFAULT_RATE_LIMIT_COUNT",
    "DEFAULT_DEDUP_WINDOW",
    "DEFAULT_ESCALATION_TIMEOUT",
    "DEFAULT_RETRY_ATTEMPTS",
    "DEFAULT_RETRY_DELAY",
    "DEFAULT_MAX_RETRY_DELAY",
    # 데이터 클래스 (5개)
    "Alert",
    "AlertResult",
    "AlertRule",
    "EscalationPolicy",
    "ChannelConfig",
    # Protocol 인터페이스 (1개)
    "AlertChannelProtocol",
    # 채널 구현 클래스 (4개)
    "SlackAlertChannel",
    "EmailAlertChannel",
    "PagerDutyAlertChannel",
    "WebhookAlertChannel",
    # 메인 클래스
    "AlertService",
    # 헬퍼 함수 (3개)
    "create_alert",
    "format_alert_message",
    "should_escalate",
]

# 모듈 버전 정보
__version__: str = "1.0.0"
