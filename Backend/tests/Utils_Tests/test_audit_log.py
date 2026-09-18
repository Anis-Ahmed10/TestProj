"""Tests for the shared audit_log decorator."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.core.exceptions import AppException
from app.utils.audit_log import audit_log

_DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class TestAuditLogDbResolution:
    """The decorator must find `db` even when the handler has no `service.db`."""

    def test_falls_back_to_direct_db_argument(self) -> None:
        @audit_log(service="logs", method="GET", endpoint="/logs")
        def get_logs(db, current_user_id):
            return "ok"

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            result = get_logs(db=object(), current_user_id=_DUMMY_USER_ID)

        assert result == "ok"
        mock_create_log.assert_called_once()
        assert mock_create_log.call_args.kwargs["user_id"] == _DUMMY_USER_ID

    def test_service_name_query_param_does_not_shadow_db_lookup(self) -> None:
        """A handler with its own `service` query param (e.g. a filter string)
        must not be mistaken for the `service.db` object convention."""

        @audit_log(service="logs", method="GET", endpoint="/logs")
        def get_logs(db, current_user_id, service=None):
            return "ok"

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            result = get_logs(db=object(), current_user_id=_DUMMY_USER_ID, service="jira")

        assert result == "ok"
        mock_create_log.assert_called_once()

    def test_prefers_service_db_when_both_present(self) -> None:
        class _Service:
            db = "service-db"

        @audit_log(service="clients", method="GET", endpoint="/clients")
        def list_clients(service, current_user_id):
            return "ok"

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            list_clients(service=_Service(), current_user_id=_DUMMY_USER_ID)

        assert mock_create_log.call_args.args[0] == "service-db"


class TestAuditLogExtraFieldsSafety:
    """A failing `extra` callable must never break the wrapped handler."""

    def test_extra_failure_is_swallowed_and_logged(self) -> None:
        def broken_extra(_kwargs):
            raise RuntimeError("lookup failed")

        @audit_log(
            service="programmes",
            method="GET",
            endpoint="/programmes/{programme_id}",
            extra=broken_extra,
        )
        def get_programme_details(service, current_user_id):
            return "ok"

        class _Service:
            db = object()

        with (
            patch("app.utils.audit_log.create_log_entry") as mock_create_log,
            patch("app.utils.audit_log._logger") as mock_logger,
        ):
            result = get_programme_details(service=_Service(), current_user_id=_DUMMY_USER_ID)

        assert result == "ok"
        mock_logger.warning.assert_called_once_with(
            "audit_log_extra_fields_failed",
            extra={"handler": "get_programme_details"},
            exc_info=True,
        )
        mock_create_log.assert_called_once()

    def test_extra_fields_are_forwarded_when_successful(self) -> None:
        @audit_log(
            service="programmes",
            method="GET",
            endpoint="/programmes/{programme_id}",
            extra=lambda kw: {"client_name": "Acme Corp"},
        )
        def get_programme_details(service, current_user_id):
            return "ok"

        class _Service:
            db = object()

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            get_programme_details(service=_Service(), current_user_id=_DUMMY_USER_ID)

        assert mock_create_log.call_args.kwargs["client_name"] == "Acme Corp"


class TestResolveArgumentsTypeErrorFallback:

    def test_bind_partial_used_when_bind_raises_type_error(self) -> None:
        import inspect

        class _FailingBindSignature:
            def __init__(self, real_sig):
                self._real = real_sig

            def bind(self, *args, **kwargs):
                raise TypeError("simulated bind failure")

            def bind_partial(self, *args, **kwargs):
                return self._real.bind_partial(*args, **kwargs)

        def _patched_signature(fn, _real_sig=inspect.signature):
            return _FailingBindSignature(_real_sig(fn))

        with (
            patch("app.utils.audit_log.inspect.signature", side_effect=_patched_signature),
            patch("app.utils.audit_log.create_log_entry") as mock_create_log,
        ):

            @audit_log(service="test", method="GET", endpoint="/test")
            def handler(db, current_user_id, **kwargs):
                return "ok"

            result = handler(db=object(), current_user_id=_DUMMY_USER_ID)

        assert result == "ok"
        mock_create_log.assert_called_once()
        assert mock_create_log.call_args.kwargs["user_id"] == _DUMMY_USER_ID

    def test_bind_partial_passes_through_available_args(self) -> None:

        sentinel_db = object()

        @audit_log(service="test", method="POST", endpoint="/test")
        def handler(db, current_user_id, optional_extra=None):
            return "done"

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            handler(sentinel_db, _DUMMY_USER_ID)

        mock_create_log.assert_called_once()
        assert mock_create_log.call_args.args[0] is sentinel_db
        assert mock_create_log.call_args.kwargs["user_id"] == _DUMMY_USER_ID


class TestSyncWrapperHTTPException:

    def test_http_exception_is_reraised_with_correct_status(self) -> None:

        @audit_log(service="test", method="GET", endpoint="/test")
        def handler(db, current_user_id):
            raise HTTPException(status_code=403, detail="Forbidden resource")

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            with pytest.raises(HTTPException) as exc_info:
                handler(db=object(), current_user_id=_DUMMY_USER_ID)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Forbidden resource"
        mock_create_log.assert_called_once()
        assert mock_create_log.call_args.kwargs["status_code"] == 403
        assert mock_create_log.call_args.kwargs["message"] == "Forbidden resource"

    def test_http_exception_detail_is_stringified(self) -> None:

        @audit_log(service="test", method="DELETE", endpoint="/test")
        def handler(db, current_user_id):
            raise HTTPException(status_code=404, detail={"msg": "Not found"})

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            with pytest.raises(HTTPException):
                handler(db=object(), current_user_id=_DUMMY_USER_ID)

        assert mock_create_log.call_args.kwargs["status_code"] == 404
        assert "Not found" in mock_create_log.call_args.kwargs["message"]


class TestSyncWrapperGenericExceptionWithErrorCode:

    def test_generic_exception_wrapped_in_app_exception(self) -> None:

        @audit_log(
            service="test",
            method="POST",
            endpoint="/test",
            error_code="TEST_FAILED",
            error_message="Something broke",
        )
        def handler(db, current_user_id):
            raise RuntimeError("boom")

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            with pytest.raises(AppException) as exc_info:
                handler(db=object(), current_user_id=_DUMMY_USER_ID)

        assert exc_info.value.code == "TEST_FAILED"
        assert exc_info.value.message == "Something broke"
        assert exc_info.value.status_code == 500
        assert isinstance(exc_info.value.__cause__, RuntimeError)
        mock_create_log.assert_called_once()
        assert mock_create_log.call_args.kwargs["status_code"] == 500
        assert mock_create_log.call_args.kwargs["message"] == "Something broke"

    def test_uses_default_unexpected_message_when_error_message_is_none(self) -> None:

        @audit_log(
            service="test",
            method="GET",
            endpoint="/test",
            error_code="GENERIC_FAIL",
        )
        def handler(db, current_user_id):
            raise ValueError("bad value")

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            with pytest.raises(AppException) as exc_info:
                handler(db=object(), current_user_id=_DUMMY_USER_ID)

        assert exc_info.value.message == "An unexpected error occurred"
        assert mock_create_log.call_args.kwargs["message"] == "An unexpected error occurred"


class TestSyncWrapperGenericExceptionBareRaise:

    def test_original_exception_reraised_when_no_error_code(self) -> None:

        @audit_log(service="test", method="GET", endpoint="/test")
        def handler(db, current_user_id):
            raise RuntimeError("unexpected failure")

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            with pytest.raises(RuntimeError, match="unexpected failure"):
                handler(db=object(), current_user_id=_DUMMY_USER_ID)

        mock_create_log.assert_called_once()
        assert mock_create_log.call_args.kwargs["status_code"] == 500

    def test_logger_exception_called_on_generic_error(self) -> None:

        @audit_log(service="myservice", method="PUT", endpoint="/test")
        def handler(db, current_user_id):
            raise TypeError("type mismatch")

        with (
            patch("app.utils.audit_log.create_log_entry"),
            patch("app.utils.audit_log._logger") as mock_logger,
        ):
            with pytest.raises(TypeError):
                handler(db=object(), current_user_id=_DUMMY_USER_ID)

        mock_logger.exception.assert_called_once_with("%s_operation_failed", "myservice")


class TestCallableSuccessMessage:
    """Covers the dynamic (callable) success_message path, sync and async."""

    def test_callable_success_message_receives_arguments_and_result(self) -> None:
        @audit_log(
            service="jira",
            method="GET",
            endpoint="/jira/fetch-issues",
            success_message=lambda kw, result: f"direction:Pull|items:{len(result)}|details:ok",
        )
        def handler(db, current_user_id):
            return [{"epicId": "E-1"}, {"epicId": "E-2"}]

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            result = handler(db=object(), current_user_id=_DUMMY_USER_ID)

        assert result == [{"epicId": "E-1"}, {"epicId": "E-2"}]
        assert mock_create_log.call_args.kwargs["message"] == "direction:Pull|items:2|details:ok"

    def test_callable_success_message_used_in_async_handler(self) -> None:
        @audit_log(
            service="jira",
            method="POST",
            endpoint="/jira/push-to-jira",
            success_message=(
                lambda kw, result: (f"direction:Push|items:{result['total']}|details:ok")
            ),
        )
        async def handler(db, current_user_id):
            return {"total": 3}

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            import asyncio

            result = asyncio.run(handler(db=object(), current_user_id=_DUMMY_USER_ID))

        assert result == {"total": 3}
        assert mock_create_log.call_args.kwargs["message"] == "direction:Push|items:3|details:ok"

    def test_existing_result_message_takes_priority_over_callable(self) -> None:
        class _Result:
            message = "explicit message wins"

        @audit_log(
            service="test",
            method="GET",
            endpoint="/test",
            success_message=lambda kw, result: "should not be used",
        )
        def handler(db, current_user_id):
            return _Result()

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            handler(db=object(), current_user_id=_DUMMY_USER_ID)

        assert mock_create_log.call_args.kwargs["message"] == "explicit message wins"

    def test_failing_callable_success_message_is_swallowed_and_logged(self) -> None:
        def broken_success_message(_kwargs, _result):
            raise RuntimeError("formatting failed")

        @audit_log(
            service="jira",
            method="GET",
            endpoint="/jira/fetch-issues",
            success_message=broken_success_message,
        )
        def handler(db, current_user_id):
            return "ok"

        with (
            patch("app.utils.audit_log.create_log_entry") as mock_create_log,
            patch("app.utils.audit_log._logger") as mock_logger,
        ):
            result = handler(db=object(), current_user_id=_DUMMY_USER_ID)

        assert result == "ok"
        mock_logger.warning.assert_called_once_with(
            "audit_log_success_message_failed",
            extra={"handler": "handler"},
            exc_info=True,
        )
        assert mock_create_log.call_args.kwargs["message"] is None

    def test_failing_callable_success_message_swallowed_in_async_handler(self) -> None:
        def broken_success_message(_kwargs, _result):
            raise RuntimeError("formatting failed")

        @audit_log(
            service="jira",
            method="POST",
            endpoint="/jira/push-to-jira",
            success_message=broken_success_message,
        )
        async def handler(db, current_user_id):
            return "ok"

        with (
            patch("app.utils.audit_log.create_log_entry") as mock_create_log,
            patch("app.utils.audit_log._logger") as mock_logger,
        ):
            import asyncio

            result = asyncio.run(handler(db=object(), current_user_id=_DUMMY_USER_ID))

        assert result == "ok"
        mock_logger.warning.assert_called_once_with(
            "audit_log_success_message_failed",
            extra={"handler": "handler"},
            exc_info=True,
        )
        assert mock_create_log.call_args.kwargs["message"] is None

    def test_pre_call_default_log_message_is_none_when_success_message_callable(self) -> None:
        """If the handler raises a bare Exception before returning, log_message
        must not end up as the raw (unresolved) callable object."""

        @audit_log(
            service="test",
            method="GET",
            endpoint="/test",
            success_message=lambda kw, result: "unused",
        )
        def handler(db, current_user_id):
            raise RuntimeError("boom")

        with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
            with pytest.raises(RuntimeError):
                handler(db=object(), current_user_id=_DUMMY_USER_ID)

        # generic exception path sets its own message; must not be the callable itself
        logged_message = mock_create_log.call_args.kwargs["message"]
        assert logged_message == "An unexpected error occurred"
