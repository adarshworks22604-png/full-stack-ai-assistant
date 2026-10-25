import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.requests import Request

from app.core.errors import AuthenticationError
from app.core.security import DevJwtVerifier, EntraJwtVerifier, extract_bearer_token
from tests.conftest import SECRET, make_token

TENANT = "tenant-1"
AUD = "api://outlook-assistant"


@pytest.fixture
def dev():
    return DevJwtVerifier(SECRET)


async def test_valid_dev_token_yields_principal(dev):
    p = await dev.verify(make_token("alice", ["payments"]))
    assert p.user_id == "alice" and p.products == frozenset({"payments"})


@pytest.mark.parametrize(
    "token",
    [
        make_token(exp_in=-3600),
        make_token(aud="someone-else"),
        make_token(iss="evil"),
        make_token(secret="x" * 40),
        make_token(extra={"products": "payments"}),  # wrong type
        "not-a-jwt",
        "",
    ],
)
async def test_bad_dev_tokens_are_rejected_with_a_generic_error(dev, token):
    with pytest.raises(AuthenticationError) as exc:
        await dev.verify(token)
    assert str(exc.value) == AuthenticationError.message  # no hint about why


async def test_alg_none_token_is_rejected(dev):
    now = int(time.time())
    token = jwt.encode(
        {"sub": "x", "iss": "outlook-assistant-dev", "aud": "outlook-assistant-api", "exp": now + 99},
        None,
        algorithm="none",
    )
    with pytest.raises(AuthenticationError):
        await dev.verify(token)


async def test_token_without_subject_is_rejected(dev):
    now = int(time.time())
    token = jwt.encode(
        {"iss": "outlook-assistant-dev", "aud": "outlook-assistant-api", "exp": now + 99}, SECRET, algorithm="HS256"
    )
    with pytest.raises(AuthenticationError):
        await dev.verify(token)


def _request(header: str | None) -> Request:
    headers = [(b"authorization", header.encode())] if header is not None else []
    return Request({"type": "http", "headers": headers})


@pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer", "Bearer   ", "token abc"])
def test_extract_bearer_rejects_malformed_headers(header):
    with pytest.raises(AuthenticationError):
        extract_bearer_token(_request(header))


def test_extract_bearer_accepts_case_insensitive_scheme():
    assert extract_bearer_token(_request("bearer abc.def")) == "abc.def"


# ---- Entra (RS256) with a locally generated key; no network ----
@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _entra(rsa_key, **kw):
    async def resolver(_token: str):
        if kw.pop("resolver_fails", False):
            raise RuntimeError("jwks unavailable")
        return rsa_key.public_key()

    return EntraJwtVerifier(
        tenant_id=TENANT,
        audience=AUD,
        issuer=None,
        group_product_map={"g-pay": ["payments"], "g-all": ["billing", "web-portal"]},
        key_resolver=resolver,
    )


def _entra_token(rsa_key, **over):
    now = int(time.time())
    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "aud": AUD,
        "tid": TENANT,
        "oid": "oid-1",
        "exp": now + 600,
        "iat": now,
        "groups": ["g-pay", "unknown-group"],
    }
    claims.update(over)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, rsa_key, algorithm="RS256")


async def test_entra_token_maps_groups_to_products(rsa_key):
    p = await _entra(rsa_key).verify(_entra_token(rsa_key))
    assert p.user_id == "oid-1" and p.products == frozenset({"payments"})


@pytest.mark.parametrize(
    "over",
    [
        {"tid": "other-tenant"},
        {"aud": "api://other"},
        {"iss": "https://evil.example/"},
        {"exp": int(time.time()) - 999},
        {"oid": None},
    ],
)
async def test_entra_rejects_wrong_tenant_audience_issuer_expiry_or_missing_identity(rsa_key, over):
    with pytest.raises(AuthenticationError):
        await _entra(rsa_key).verify(_entra_token(rsa_key, **over))


async def test_entra_only_accepts_rs256(rsa_key):
    """An HS256 token must be rejected even if everything else in it looks right."""
    now = int(time.time())
    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "aud": AUD,
        "tid": TENANT,
        "oid": "x",
        "exp": now + 99,
    }
    with pytest.raises(AuthenticationError):
        await _entra(rsa_key).verify(jwt.encode(claims, "k" * 40, algorithm="HS256"))
    with pytest.raises(AuthenticationError):
        await _entra(rsa_key).verify(jwt.encode(claims, None, algorithm="none"))


async def test_entra_key_resolution_failure_is_an_auth_failure(rsa_key):
    with pytest.raises(AuthenticationError):
        await _entra(rsa_key, resolver_fails=True).verify(_entra_token(rsa_key))
