from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from app.core.exceptions import AppException
from app.database.application_log_db import create_log_entry

_logger = logging.getLogger(__name__)

_UNEXPECTED_MESSAGE = "An unexpected error occurred"


def audit_log(
    *,
    service: str,
    method: str,
    endpoint: str,
    success_status: int = 200,
    success_message: str | Callable[[dict[str, Any], Any], str] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    extra: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable:

    def decorator(fn: Callable) -> Callable:
        signature = inspect.signature(fn)

        def _resolve_arguments(args: tuple, kwargs: dict) -> dict[str, Any]:
            try:
                bound = signature.bind(*args, **kwargs)
            except TypeError:
                bound = signature.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            return dict(bound.arguments)

        def _resolve_success_message(
            arguments: dict[str, Any], result: Any, fn_name: str
        ) -> str | None:
            existing_message = getattr(result, "message", None)
            if existing_message:
                return existing_message
            if callable(success_message):
                try:
                    return success_message(arguments, result)
                except Exception:
                    _logger.warning(
                        "audit_log_success_message_failed",
                        extra={"handler": fn_name},
                        exc_info=True,
                    )
                    return None
            return success_message

        def _emit(
            db: Any,
            user_id: Any,
            status_code: int,
            log_message: str | None,
            extra_fields: dict[str, Any],
            fn_name: str,
        ) -> None:
            if db is None:
                return
            try:
                create_log_entry(
                    db,
                    service_name=service,
                    http_method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    user_id=user_id,
                    message=log_message,
                    **extra_fields,
                )
            except Exception:
                _logger.warning(
                    "application_log_entry_failed",
                    extra={"handler": fn_name},
                    exc_info=True,
                )

        def _resolve_extra_fields(arguments: dict[str, Any], fn_name: str) -> dict[str, Any]:
            if extra is None:
                return {}
            try:
                return extra(arguments)
            except Exception:
                _logger.warning(
                    "audit_log_extra_fields_failed",
                    extra={"handler": fn_name},
                    exc_info=True,
                )
                return {}

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                arguments = _resolve_arguments(args, kwargs)
                db = getattr(arguments.get("service"), "db", None)
                if db is None:
                    db = arguments.get("db")
                user_id = arguments.get("current_user_id")
                extra_fields = _resolve_extra_fields(arguments, fn.__name__)
                status_code = success_status
                log_message = None if callable(success_message) else success_message
                try:
                    result = await fn(*args, **kwargs)
                    log_message = _resolve_success_message(arguments, result, fn.__name__)
                    return result
                except AppException as exc:
                    status_code = exc.status_code
                    log_message = exc.message
                    raise
                except HTTPException as exc:
                    status_code = exc.status_code
                    log_message = str(exc.detail)
                    raise
                except Exception as exc:
                    status_code = 500
                    log_message = error_message or _UNEXPECTED_MESSAGE
                    _logger.exception("%s_operation_failed", service)
                    if error_code is not None:
                        raise AppException(
                            code=error_code,
                            message=log_message,
                            status_code=500,
                        ) from exc
                    raise
                finally:
                    _emit(db, user_id, status_code, log_message, extra_fields, fn.__name__)

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            arguments = _resolve_arguments(args, kwargs)
            db = getattr(arguments.get("service"), "db", None)
            if db is None:
                db = arguments.get("db")
            user_id = arguments.get("current_user_id")
            extra_fields = _resolve_extra_fields(arguments, fn.__name__)
            status_code = success_status
            log_message = None if callable(success_message) else success_message
            try:
                result = fn(*args, **kwargs)
                log_message = _resolve_success_message(arguments, result, fn.__name__)
                return result
            except AppException as exc:
                status_code = exc.status_code
                log_message = exc.message
                raise
            except HTTPException as exc:
                status_code = exc.status_code
                log_message = str(exc.detail)
                raise
            except Exception as exc:
                status_code = 500
                log_message = error_message or _UNEXPECTED_MESSAGE
                _logger.exception("%s_operation_failed", service)
                if error_code is not None:
                    raise AppException(
                        code=error_code,
                        message=log_message,
                        status_code=500,
                    ) from exc
                raise
            finally:
                _emit(db, user_id, status_code, log_message, extra_fields, fn.__name__)

        return sync_wrapper

    return decorator
