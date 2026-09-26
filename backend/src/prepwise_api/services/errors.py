class ApplicationServiceError(Exception):
    """Expected application-layer failure safe to expose to API and tool callers."""

    code = "application_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ApplicationNotFoundError(ApplicationServiceError):
    code = "not_found"


class ApplicationConflictError(ApplicationServiceError):
    code = "conflict"


class ApplicationValidationError(ApplicationServiceError):
    code = "validation_error"
