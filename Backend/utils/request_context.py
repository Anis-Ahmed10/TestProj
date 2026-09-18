"""Context-local request correlation ID helpers."""

from contextvars import ContextVar, Token

_request_id: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(request_id: str) -> Token[str]:
    """Store the request ID for the current async context."""
    return _request_id.set(request_id)


def get_request_id() -> str:
    """Return the current request ID if one is available."""
    return _request_id.get()


def reset_request_id(token: Token[str]) -> None:
    """Reset the request ID context variable."""
    _request_id.reset(token)
