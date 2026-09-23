from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from prepwise_api.auth import AccessTokenValidator, InvalidAccessTokenError
from prepwise_api.config import Settings

TENANT_ID = "1a782388-bf90-4ea8-af8f-bcc755f5cd7e"
API_CLIENT_ID = "82773ea0-fcf3-4874-81c3-3cd0da7d00c7"


class StaticSigningKeyClient:
    def __init__(self, public_key: rsa.RSAPublicKey) -> None:
        self._signing_key = SimpleNamespace(key=public_key)

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        del token
        return self._signing_key


@pytest.fixture
def token_factory() -> Any:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = Settings()
    validator = AccessTokenValidator(
        settings,
        signing_key_client=StaticSigningKeyClient(private_key.public_key()),
    )

    def create_token(**overrides: Any) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "aud": API_CLIENT_ID,
            "exp": now + timedelta(minutes=5),
            "iat": now,
            "iss": settings.entra_issuer,
            "name": "Prepwise Customer",
            "oid": "d074c8a4-4494-4597-9d33-2df93b5f9959",
            "preferred_username": "customer@example.com",
            "scp": "access_as_user",
            "sub": "pairwise-subject",
            "tid": TENANT_ID,
            "ver": "2.0",
        }
        payload.update(overrides)
        return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key"})

    return validator, create_token


def test_valid_token_returns_tenant_scoped_identity(token_factory: Any) -> None:
    validator, create_token = token_factory

    claims = validator.validate(create_token())

    assert claims.external_subject == (
        "1a782388-bf90-4ea8-af8f-bcc755f5cd7e:d074c8a4-4494-4597-9d33-2df93b5f9959"
    )
    assert claims.email == "customer@example.com"
    assert claims.display_name == "Prepwise Customer"


@pytest.mark.parametrize(
    ("overrides"),
    [
        {"aud": "another-api"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"iss": "https://issuer.example.invalid"},
        {"scp": "another_scope"},
        {"tid": "00000000-0000-0000-0000-000000000000"},
        {"ver": "1.0"},
    ],
)
def test_invalid_or_expired_tokens_are_rejected(
    token_factory: Any,
    overrides: dict[str, Any],
) -> None:
    validator, create_token = token_factory

    with pytest.raises(InvalidAccessTokenError):
        validator.validate(create_token(**overrides))


def test_external_id_endpoints_match_published_tenant_metadata() -> None:
    settings = Settings()

    assert settings.entra_issuer == (
        "https://1a782388-bf90-4ea8-af8f-bcc755f5cd7e.ciamlogin.com/"
        "1a782388-bf90-4ea8-af8f-bcc755f5cd7e/v2.0"
    )
    assert settings.entra_jwks_url == (
        "https://prepwisecustomers.ciamlogin.com/"
        "1a782388-bf90-4ea8-af8f-bcc755f5cd7e/discovery/v2.0/keys"
    )
