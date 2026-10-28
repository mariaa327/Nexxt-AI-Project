"""Authentication tests.

Signing keys are generated locally and the JWKS client is stubbed, so these
tests verify real signature checking without any network access.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import settings
from app.core.database import get_db
from app.main import app

ISSUER = "https://test-project.supabase.co/auth/v1"
USER_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(scope="module")
def rsa_keys() -> tuple[Any, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def jwks_configured(
    monkeypatch: pytest.MonkeyPatch, rsa_keys: tuple[Any, Any]
) -> tuple[Any, Any]:
    """Configure asymmetric verification with a stubbed JWKS client."""
    private_key, public_key = rsa_keys
    monkeypatch.setattr(settings, "supabase_url", "https://test-project.supabase.co")
    monkeypatch.setattr(settings, "supabase_jwks_url", None)

    class StubJWKClient:
        def get_signing_key_from_jwt(self, _token: str) -> jwt.PyJWK:
            return jwt.PyJWK.from_dict(_public_jwk(public_key))

    monkeypatch.setattr(security, "_get_jwks_client", lambda _url: StubJWKClient())
    return private_key, public_key


def _public_jwk(public_key: Any) -> dict[str, Any]:
    import json

    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    jwk["kid"] = "test-key"
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    return jwk


def _token(private_key: Any, **overrides: Any) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": USER_ID,
        "iss": ISSUER,
        "aud": "authenticated",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "email": "student@example.com",
        "role": "authenticated",
    }
    payload.update(overrides.pop("claims", {}))
    headers = {"kid": "test-key", **overrides.pop("headers", {})}
    algorithm = overrides.pop("algorithm", "RS256")
    return jwt.encode(payload, private_key, algorithm=algorithm, headers=headers)


# --- Unit tests on verify_access_token ------------------------------------


def test_valid_asymmetric_token_returns_user(jwks_configured: tuple[Any, Any]) -> None:
    private_key, _ = jwks_configured
    user = security.verify_access_token(_token(private_key))

    assert user.user_id == USER_ID
    assert user.email == "student@example.com"


def test_expired_token_is_rejected(jwks_configured: tuple[Any, Any]) -> None:
    private_key, _ = jwks_configured
    past = datetime.now(UTC) - timedelta(minutes=10)
    token = _token(
        private_key, claims={"exp": past, "iat": past - timedelta(minutes=5)}
    )

    with pytest.raises(HTTPException) as exc_info:
        security.verify_access_token(token)
    assert exc_info.value.status_code == 401


def test_wrong_issuer_is_rejected(jwks_configured: tuple[Any, Any]) -> None:
    private_key, _ = jwks_configured
    token = _token(private_key, claims={"iss": "https://evil.example.com/auth/v1"})

    with pytest.raises(HTTPException) as exc_info:
        security.verify_access_token(token)
    assert exc_info.value.status_code == 401


def test_missing_subject_is_rejected(jwks_configured: tuple[Any, Any]) -> None:
    private_key, _ = jwks_configured
    token = _token(private_key, claims={"sub": None})

    with pytest.raises(HTTPException) as exc_info:
        security.verify_access_token(token)
    assert exc_info.value.status_code == 401


def test_token_signed_with_another_key_is_rejected(
    jwks_configured: tuple[Any, Any],
) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(HTTPException) as exc_info:
        security.verify_access_token(_token(other_key))
    assert exc_info.value.status_code == 401


def test_unsigned_alg_none_token_is_rejected(jwks_configured: tuple[Any, Any]) -> None:
    token = jwt.encode(
        {
            "sub": USER_ID,
            "iss": ISSUER,
            "aud": "authenticated",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        key="",
        algorithm="none",
    )

    with pytest.raises(HTTPException) as exc_info:
        security.verify_access_token(token)
    assert exc_info.value.status_code == 401


def test_hs256_token_rejected_when_no_legacy_secret(
    jwks_configured: tuple[Any, Any],
) -> None:
    token = _token("shared-secret-value-that-is-long-enough", algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        security.verify_access_token(token)
    assert exc_info.value.status_code == 401


def test_hs256_token_accepted_with_explicit_legacy_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "supabase_url", "https://test-project.supabase.co")
    monkeypatch.setattr(
        settings, "supabase_jwt_secret", "shared-secret-value-that-is-long-enough"
    )

    user = security.verify_access_token(
        _token("shared-secret-value-that-is-long-enough", algorithm="HS256")
    )

    assert user.user_id == USER_ID


def test_hs256_token_with_wrong_secret_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "supabase_url", "https://test-project.supabase.co")
    monkeypatch.setattr(
        settings, "supabase_jwt_secret", "shared-secret-value-that-is-long-enough"
    )

    with pytest.raises(HTTPException) as exc_info:
        security.verify_access_token(
            _token("a-different-secret-that-is-long-enough", algorithm="HS256")
        )
    assert exc_info.value.status_code == 401


def test_asymmetric_token_without_supabase_configuration_raises_config_error() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(security.AuthConfigurationError):
        security.verify_access_token(_token(private_key))


def test_malformed_token_is_rejected(jwks_configured: tuple[Any, Any]) -> None:
    with pytest.raises(HTTPException) as exc_info:
        security.verify_access_token("not-a-jwt")
    assert exc_info.value.status_code == 401


# --- Endpoint-level authentication checks ---------------------------------


@pytest.fixture
def endpoint_client(db_session: Any, fake_agent: Any) -> TestClient:
    """Client with database/agent overridden but real authentication enabled."""
    from app.api.endpoints.agent import get_agent_service

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_agent_service] = lambda: fake_agent
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_agent_endpoint_requires_authorization_header(
    endpoint_client: TestClient,
) -> None:
    response = endpoint_client.post("/api/agent/run", json={"prompt": "Hello"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_agent_endpoint_rejects_malformed_header(endpoint_client: TestClient) -> None:
    response = endpoint_client.post(
        "/api/agent/run",
        json={"prompt": "Hello"},
        headers={"Authorization": "Token abc123"},
    )

    assert response.status_code == 401


def test_agent_endpoint_rejects_invalid_bearer_token(
    endpoint_client: TestClient, jwks_configured: tuple[Any, Any]
) -> None:
    response = endpoint_client.post(
        "/api/agent/run",
        json={"prompt": "Hello"},
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401


def test_agent_endpoint_rejects_token_signed_by_other_key(
    endpoint_client: TestClient, jwks_configured: tuple[Any, Any]
) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    response = endpoint_client.post(
        "/api/agent/run",
        json={"prompt": "Hello"},
        headers={"Authorization": f"Bearer {_token(other_key)}"},
    )

    assert response.status_code == 401


def test_agent_endpoint_accepts_valid_token(
    endpoint_client: TestClient, jwks_configured: tuple[Any, Any], db_session: Any
) -> None:
    from app.models.domain import AgentTask

    private_key, _ = jwks_configured
    response = endpoint_client.post(
        "/api/agent/run",
        json={"prompt": "What is a vector database?"},
        headers={"Authorization": f"Bearer {_token(private_key)}"},
    )

    assert response.status_code == 201
    stored = db_session.query(AgentTask).one()
    assert stored.user_id == USER_ID
