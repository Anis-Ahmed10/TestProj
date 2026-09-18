"""Application-specific exceptions with safe frontend messages."""

from http import HTTPStatus

from fastapi import HTTPException


class AppException(Exception):
    """Base exception carrying an API-safe error code and message."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = HTTPStatus.BAD_REQUEST,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class InvalidInputError(AppException):
    """Raised when validated input still fails business constraints."""

    def __init__(self, message: str) -> None:
        super().__init__(
            code="INVALID_INPUT",
            message=message,
            status_code=HTTPStatus.BAD_REQUEST,
        )


class SanitizationError(AppException):
    """Raised when sensitive-data sanitization fails safely."""

    def __init__(self, message: str = "Unable to safely sanitize the request") -> None:
        super().__init__(
            code="SANITIZATION_FAILED",
            message=message,
            status_code=HTTPStatus.BAD_REQUEST,
        )


class AuthorizationError(AppException):
    """Raised when an authenticated user lacks permission for the requested action."""

    def __init__(self, message: str = "You do not have permission to perform this action") -> None:
        super().__init__(
            code="AUTHORIZATION_DENIED",
            message=message,
            status_code=HTTPStatus.FORBIDDEN,
        )


class JiraPushException(AppException):
    """Raised when an error occurs while pushing issues to Jira."""

    def __init__(self, message: str = "Failed to push issue to Jira") -> None:
        super().__init__(
            code="JIRA_PUSH_FAILED",
            message=message,
            status_code=HTTPStatus.BAD_REQUEST,
        )


class JiraNotConfiguredException(AppException):
    """Raised when a project is missing its Jira URL/Project Key, or the
    calling user hasn't saved their own Jira email/API token."""

    def __init__(
        self,
        message: str = (
            "Jira isn't fully configured yet. Set the Jira URL and Project Key "
            "also set your Jira email and API token in your Profile, then try again."
        ),
    ) -> None:
        super().__init__(
            code="JIRA_NOT_CONFIGURED",
            message=message,
            status_code=HTTPStatus.BAD_REQUEST,
        )


class JiraInstanceNotConfiguredException(AppException):
    """Raised while saving Profile credentials when none of the user's projects
    has a Jira URL, leaving no Jira instance to verify the credentials against."""

    def __init__(
        self,
        message: str = (
            "No project with a Jira URL is associated with your account yet. "
            "Ask a project lead to set the Jira URL in that project's Jira "
            "Integration tab, then save your credentials."
        ),
    ) -> None:
        super().__init__(
            code="JIRA_INSTANCE_NOT_CONFIGURED",
            message=message,
            status_code=HTTPStatus.BAD_REQUEST,
        )


class JiraCredentialsInvalidException(AppException):
    """Raised when a user's Jira email/API token fail to authenticate with Jira,
    or authenticate as a different Jira account than the email given."""

    def __init__(
        self,
        message: str = (
            "Could not connect to Jira with these credentials. " "Check the email and API token."
        ),
    ) -> None:
        super().__init__(
            code="JIRA_CREDENTIALS_INVALID",
            message=message,
            status_code=HTTPStatus.BAD_REQUEST,
        )


# Jira-fetch related exceptions
class JiraAuthException(HTTPException):
    def __init__(self, detail="Jira authentication failed"):
        super().__init__(status_code=401, detail=detail)


class JiraFetchException(HTTPException):
    def __init__(
        self,
        detail=("Could not reach Jira. It may be down or unreachable — please try again."),
    ):
        super().__init__(status_code=502, detail=detail)


class DatabaseOperationException(AppException):
    """Raised when a database operation fails unexpectedly."""

    def __init__(self, message: str = "Database operation failed") -> None:
        super().__init__(
            code="DATABASE_OPERATION_FAILED",
            message=message,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )


class SesEmailException(AppException):
    """Raised when SES email sending fails."""

    def __init__(self, message: str = "Failed to send email notification") -> None:
        super().__init__(
            code="SES_EMAIL_FAILED",
            message=message,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )


class ResourceNotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=message,
            status_code=HTTPStatus.NOT_FOUND,
        )
