from typing import cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.container import Container
from app.core.security import Principal, extract_bearer_token

# Registers the Bearer scheme in OpenAPI (gives /docs an Authorize button). Parsing and
# validation are done by extract_bearer_token + the verifier, so every failure has one format.
_bearer_scheme = HTTPBearer(auto_error=False, description="Access token (dev token locally, Entra token in production)")


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


async def get_principal(
    request: Request,
    _scheme: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    container: Container = Depends(get_container),
) -> Principal:
    """Authenticates the caller. Every protected route depends on this."""
    token = extract_bearer_token(request)
    return await container.verifier.verify(token)
