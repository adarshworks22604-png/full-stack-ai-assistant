"""Wiring: builds every long-lived object once and exposes it via app.state."""

import asyncio
from dataclasses import dataclass, field

from app.core.admission import AdmissionController
from app.core.config import Settings
from app.core.security import TokenVerifier, build_verifier
from app.integrations.base import BugTrackerClient, DocumentationSearchClient
from app.integrations.http_adapters import HttpBugTrackerClient, HttpDocumentationSearchClient
from app.integrations.http_client import ResilientHttpClient
from app.integrations.mock import MockBugTrackerClient, MockDocumentationSearchClient
from app.services.authorization import AccessPolicy
from app.services.chat_service import ChatService, MockChatService
from app.services.coordinator import ChatCoordinator
from app.services.feedback_store import FeedbackStore
from app.services.request_registry import RequestRegistry


@dataclass
class Container:
    settings: Settings
    verifier: TokenVerifier
    registry: RequestRegistry
    feedback: FeedbackStore
    coordinator: ChatCoordinator
    policy: AccessPolicy
    http_clients: list[ResilientHttpClient] = field(default_factory=list)

    async def aclose(self) -> None:
        for client in self.http_clients:
            await client.aclose()


def build_container(
    settings: Settings,
    *,
    verifier: TokenVerifier | None = None,
    chat_service: ChatService | None = None,
    bugs: BugTrackerClient | None = None,
    docs: DocumentationSearchClient | None = None,
) -> Container:
    policy = AccessPolicy()
    http_clients: list[ResilientHttpClient] = []

    if bugs is None or docs is None:
        if settings.use_mock_integrations:
            bugs = bugs or MockBugTrackerClient()
            docs = docs or MockDocumentationSearchClient()
        else:
            limiter = asyncio.Semaphore(settings.upstream_max_concurrency)  # shared across both APIs

            def make(name: str, url: str | None, token: object) -> ResilientHttpClient:
                assert url and token is not None  # guaranteed by Settings validation
                client = ResilientHttpClient.create(
                    name=name,
                    base_url=url,
                    token=token.get_secret_value(),  # type: ignore[attr-defined]
                    connect=settings.upstream_connect_timeout,
                    read=settings.upstream_read_timeout,
                    write=settings.upstream_write_timeout,
                    pool=settings.upstream_pool_timeout,
                    limiter=limiter,
                    max_retries=settings.upstream_max_retries,
                    backoff_base=settings.upstream_backoff_base_seconds,
                    backoff_max=settings.upstream_backoff_max_seconds,
                    max_response_bytes=settings.upstream_max_response_bytes,
                )
                http_clients.append(client)
                return client

            bugs = bugs or HttpBugTrackerClient(make("bug tracker", settings.bug_api_base_url, settings.bug_api_token))
            docs = docs or HttpDocumentationSearchClient(
                make("documentation search", settings.docs_api_base_url, settings.docs_api_token)
            )

    registry = RequestRegistry()
    admission = AdmissionController(
        rate_limit_per_minute=settings.rate_limit_per_minute,
        max_global=settings.max_concurrent_streams_global,
        max_per_user=settings.max_concurrent_streams_per_user,
    )
    service = chat_service or MockChatService(settings=settings, bugs=bugs, docs=docs, policy=policy)
    coordinator = ChatCoordinator(chat_service=service, registry=registry, admission=admission, settings=settings)
    return Container(
        settings=settings,
        verifier=verifier or build_verifier(settings),
        registry=registry,
        feedback=FeedbackStore(),
        coordinator=coordinator,
        policy=policy,
        http_clients=http_clients,
    )
