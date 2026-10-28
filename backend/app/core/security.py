"""JWT verification for Supabase-issued access tokens.

All token verification lives here so endpoints only ever receive a verified
user identity. Two signing strategies are supported:

* **Asymmetric keys (default, recommended).** Supabase signs access tokens with
  a private key and publishes the public keys at the project's JWKS endpoint.
  Keys are fetched through ``PyJWKClient``, which caches the JWK set, so signing
  keys are not downloaded on every request.
* **Legacy HS256 shared secret (compatibility only).** Only used when
  ``SUPABASE_JWT_SECRET`` is explicitly configured *and* the token header
  declares HS256. New Supabase projects should not need this.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)

# Only these algorithms are ever accepted. ``none`` and any algorithm not in
# this list are rejected before any key material is looked up.
_ASYMMETRIC_ALGORITHMS = frozenset(
    {"ES256", "ES384", "ES512", "RS256", "RS384", "RS512"}
)
_LEGACY_ALGORITHM = "HS256"

bearer_scheme = HTTPBearer(auto_error=False)

_jwks_clients: dict[str, jwt.PyJWKClient] = {}
_jwks_lock = threading.Lock()


class AuthConfigurationError(RuntimeError):
    """Raised when token verification cannot be configured on the server."""


@dataclass(frozen=True)
class CurrentUser:
    """Verified identity extracted from a Supabase access token."""

    user_id: str
    claims: dict[str, Any] = field(default_factory=dict)

    @property
    def email(self) -> str | None:
        value = self.claims.get("email")
        return value if isinstance(value, str) else None


def _get_jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    """Return a cached JWKS client for the given URL.

    ``PyJWKClient`` caches the fetched JWK set internally (default lifespan:
    five minutes), so this avoids one key download per request.
    """
    client = _jwks_clients.get(jwks_url)
    if client is None:
        with _jwks_lock:
            client = _jwks_clients.get(jwks_url)
            if client is None:
                client = jwt.PyJWKClient(
                    jwks_url,
                    cache_jwk_set=True,
                    cache_keys=True,
                    lifespan=300,
                    timeout=10,
                )
                _jwks_clients[jwks_url] = client
    return client


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_options() -> dict[str, Any]:
    # ``exp`` and ``sub`` are always required; PyJWT also verifies the
    # signature and rejects expired tokens when these options are used.
    return {"require": ["exp", "sub"], "verify_signature": True, "verify_exp": True}


def _audience() -> str | None:
    return settings.supabase_jwt_audience


def verify_access_token(token: str) -> CurrentUser:
    """Verify a Supabase access token and return the authenticated user.

    Raises ``HTTPException`` for invalid/expired tokens and
    ``AuthConfigurationError`` when the server has no usable verification
    configuration.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid authentication token") from exc

    algorithm = header.get("alg")
    if not isinstance(algorithm, str):
        raise _unauthorized("Invalid authentication token")

    issuer = settings.supabase_issuer

    if algorithm == _LEGACY_ALGORITHM:
        if not settings.supabase_jwt_secret:
            # Never fall back to an unverified payload: without the shared
            # secret an HS256 token simply cannot be trusted.
            raise _unauthorized("Invalid authentication token")
        key: Any = settings.supabase_jwt_secret
        algorithms = [_LEGACY_ALGORITHM]
    elif algorithm in _ASYMMETRIC_ALGORITHMS:
        jwks_url = settings.resolved_jwks_url
        if not jwks_url:
            raise AuthConfigurationError(
                "SUPABASE_URL (or SUPABASE_JWKS_URL) must be configured to verify access tokens."
            )
        try:
            key = _get_jwks_client(jwks_url).get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError as exc:
            logger.warning("Unable to reach the Supabase JWKS endpoint: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is temporarily unavailable",
            ) from exc
        except jwt.PyJWTError as exc:
            raise _unauthorized("Invalid authentication token") from exc
        algorithms = [algorithm]
    else:
        raise _unauthorized("Invalid authentication token")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=_audience(),
            issuer=issuer,
            options=_decode_options(),
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Authentication token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("Invalid authentication token") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise _unauthorized("Invalid authentication token")

    return CurrentUser(user_id=subject, claims=claims)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    """FastAPI dependency returning the verified user for a bearer token."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Missing authentication credentials")

    if credentials.scheme.lower() != "bearer":
        raise _unauthorized("Invalid authentication scheme")

    try:
        return verify_access_token(credentials.credentials)
    except AuthConfigurationError as exc:
        logger.error("Authentication is not configured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured on the server",
        ) from exc
