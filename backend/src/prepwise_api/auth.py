from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any, Protocol, cast

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prepwise_api.config import Settings, get_settings
from prepwise_api.database import get_session
from prepwise_api.models import User, UserRole
from prepwise_api.telemetry import record_safe_exception


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Validated identity and display claims from an Entra access token."""

    tenant_id: str
    object_id: str
    subject: str
    email: str | None
    display_name: str | None

    @property
    def external_subject(self) -> str:
        """Return a tenant-scoped immutable key for the local user mapping."""
        return f"{self.tenant_id}:{self.object_id}"


class SigningKey(Protocol):
    key: Any


class SigningKeyClient(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> SigningKey: ...


class InvalidAccessTokenError(Exception):
    """The supplied bearer token is not valid for the Prepwise API."""


class SigningKeysUnavailableError(Exception):
    """The identity provider's signing keys could not be reached."""


class AccessTokenValidator:
    """Validate Entra External ID access tokens and extract trusted claims."""

    def __init__(
        self,
        settings: Settings,
        signing_key_client: SigningKeyClient | None = None,
    ) -> None:
        self._settings = settings
        self._signing_key_client = signing_key_client or cast(
            SigningKeyClient,
            PyJWKClient(
                settings.entra_jwks_url,
                cache_jwk_set=True,
                lifespan=3600,
                timeout=5,
            ),
        )

    def validate(self, token: str) -> AccessTokenClaims:
        """Validate signature and required claims for a delegated API token."""
        try:
            signing_key = self._signing_key_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.entra_api_client_id,
                issuer=self._settings.entra_issuer,
                leeway=30,
                options={"require": ["aud", "exp", "iss", "oid", "scp", "sub", "tid", "ver"]},
            )
        except PyJWKClientConnectionError as error:
            raise SigningKeysUnavailableError from error
        except (PyJWKClientError, PyJWTError) as error:
            raise InvalidAccessTokenError from error

        tenant_id = _required_string_claim(payload, "tid")
        object_id = _required_string_claim(payload, "oid")
        subject = _required_string_claim(payload, "sub")
        version = _required_string_claim(payload, "ver")
        scopes = set(_required_string_claim(payload, "scp").split())

        if tenant_id != self._settings.entra_tenant_id:
            raise InvalidAccessTokenError
        if version != "2.0":
            raise InvalidAccessTokenError
        if self._settings.entra_api_scope not in scopes:
            raise InvalidAccessTokenError

        return AccessTokenClaims(
            tenant_id=tenant_id,
            object_id=object_id,
            subject=subject,
            email=_optional_string_claim(payload, "email", "preferred_username"),
            display_name=_optional_string_claim(payload, "name"),
        )


class TokenValidator(Protocol):
    def validate(self, token: str) -> AccessTokenClaims: ...


class E2EAccessTokenValidator:
    """Resolve fixed local identities for full-stack tests only."""

    _claims_by_token = {
        "prepwise-e2e-customer": AccessTokenClaims(
            tenant_id="e2e",
            object_id="customer",
            subject="customer",
            email="customer.e2e@example.invalid",
            display_name="E2E Customer",
        ),
        "prepwise-e2e-admin": AccessTokenClaims(
            tenant_id="e2e",
            object_id="admin",
            subject="admin",
            email="admin.e2e@example.invalid",
            display_name="E2E Admin",
        ),
    }

    def validate(self, token: str) -> AccessTokenClaims:
        try:
            return self._claims_by_token[token]
        except KeyError as error:
            raise InvalidAccessTokenError from error


def _required_string_claim(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise InvalidAccessTokenError
    return value


def _optional_string_claim(payload: dict[str, Any], *names: str) -> str | None:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value:
            return value
    return None


def create_access_token_validator(settings: Settings) -> TokenValidator:
    if settings.e2e_auth_enabled:
        if settings.app_env != "test":
            raise RuntimeError("E2E authentication may only be enabled in the test environment")
        return E2EAccessTokenValidator()
    return AccessTokenValidator(settings)


@lru_cache
def get_access_token_validator() -> TokenValidator:
    return create_access_token_validator(get_settings())


bearer_scheme = HTTPBearer(auto_error=False)


def get_access_token_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    validator: Annotated[TokenValidator, Depends(get_access_token_validator)],
) -> AccessTokenClaims:
    """Require and validate a bearer token without exposing validation details."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        return validator.validate(credentials.credentials)
    except InvalidAccessTokenError as error:
        raise _unauthorized() from error
    except SigningKeysUnavailableError as error:
        record_safe_exception(error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from error


def get_current_user(
    claims: Annotated[AccessTokenClaims, Depends(get_access_token_claims)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Resolve the current local user, creating it safely on first access."""
    user = session.scalar(select(User).where(User.external_subject == claims.external_subject))
    if user is not None:
        return user

    user = User(
        external_subject=claims.external_subject,
        email=claims.email,
        display_name=claims.display_name,
    )
    session.add(user)

    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        user = session.scalar(select(User).where(User.external_subject == claims.external_subject))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The authenticated identity conflicts with an existing user",
            ) from error
    else:
        session.refresh(user)

    return user


def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require the authenticated local user to have the admin role."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
