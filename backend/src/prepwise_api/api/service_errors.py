from typing import NoReturn

from fastapi import HTTPException, status

from prepwise_api.services import (
    ApplicationConflictError,
    ApplicationNotFoundError,
    ApplicationServiceError,
    ApplicationValidationError,
)


def raise_service_http_error(error: ApplicationServiceError) -> NoReturn:
    """Translate an application-layer failure at the HTTP boundary."""
    if isinstance(error, ApplicationNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, ApplicationConflictError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(error, ApplicationValidationError):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:  # pragma: no cover - defensive for future service failures
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    raise HTTPException(status_code=status_code, detail=error.message) from error
