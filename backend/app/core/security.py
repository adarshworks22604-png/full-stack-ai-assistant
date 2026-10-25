"""Authentication: validate bearer tokens and build a Principal.

A user identity is only ever taken from a validated token, never from the request body.
Two verifiers:
  * DevJwtVerifier   - HS256 with a local secret. Refused by config unless APP_ENV=local.
  * EntraJwtVerifier - RS256 against Microsoft Entra ID signing keys (JWKS).
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import jwt
from fastapi import Request

from app.core.config import Settings
from app.core.errors import AuthenticationError

DEV_ISSUER = "outlook-assistant-dev"
DEV_AUDIENCE = "outlook-assistant-api"
ALL_PRODUCTS = "*"


@dataclass(frozen=True)
class Principal:
    user_id: str
    products: frozenset[str] = field(default_factory=frozenset)
    display_name: str | None = None


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> Principal: ...


def _fail() -> AuthenticationError:
    # One generic message for every failure: do not reveal why a token was rejected.
    return AuthenticationError()


class DevJwtVerifier:
    def __init__(self, secret: str, leeway: int = 30) -> None:
        self._secret = secret
        self._leeway = leeway

    async def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=DEV_AUDIENCE,
                issuer=DEV_ISSUER,
                leeway=self._leeway,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError:
            raise _fail() from None
        products = claims.get("products", [])
        if not isinstance(products, list) or not all(isinstance(p, str) for p in products):
            raise _fail()
        return Principal(user_id=str(claims["sub"]), products=frozenset(products), display_name=claims.get("name"))


KeyResolver = Callable[[str], Awaitable[Any]]


class EntraJwtVerifier:
    """Validates Entra ID access tokens: signature, issuer, audience, expiry and tenant."""

    def __init__(
        self,
        *,
        tenant_id: str,
        audience: str,
        issuer: str | None,
        group_product_map: dict[str, list[str]],
        key_resolver: KeyResolver | None = None,
        leeway: int = 30,
    ) -> None:
        self._tenant = tenant_id
        self._audience = audience
        self._issuer = issuer or f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        self._groups = group_product_map
        self._leeway = leeway
        self._resolve_key = key_resolver or self._default_resolver(tenant_id)

    @staticmethod
    def _default_resolver(tenant_id: str) -> KeyResolver:
        client = jwt.PyJWKClient(
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys", cache_keys=True, lifespan=3600
        )

        async def resolve(token: str) -> Any:
            # PyJWKClient does blocking network I/O, so keep it off the event loop.
            signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, token)
            return signing_key.key

        return resolve

    async def verify(self, token: str) -> Principal:
        try:
            key = await self._resolve_key(token)
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": ["exp", "aud", "iss"]},
            )
        except Exception:  # noqa: BLE001 - any failure here means "not authenticated"
            raise _fail() from None
        if claims.get("tid") != self._tenant:
            raise _fail()
        user_id = claims.get("oid") or claims.get("sub")
        if not user_id:
            raise _fail()
        groups = claims.get("groups", [])
        products: set[str] = set()
        if isinstance(groups, list):
            for group in groups:
                products.update(self._groups.get(str(group), []))
        return Principal(user_id=str(user_id), products=frozenset(products), display_name=claims.get("name"))


def build_verifier(settings: Settings) -> TokenVerifier:
    if settings.auth_mode == "dev":
        assert settings.dev_jwt_secret is not None  # guaranteed by Settings validation
        return DevJwtVerifier(settings.dev_jwt_secret.get_secret_value(), settings.jwt_leeway_seconds)
    assert settings.entra_tenant_id and settings.entra_audience
    return EntraJwtVerifier(
        tenant_id=settings.entra_tenant_id,
        audience=settings.entra_audience,
        issuer=settings.entra_issuer,
        group_product_map=json.loads(settings.entra_group_product_map),
        leeway=settings.jwt_leeway_seconds,
    )


def extract_bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError()
    return token.strip()
