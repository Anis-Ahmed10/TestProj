"""Unit tests for app/database/application_log_db.py — 100% coverage."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import DatabaseOperationException
from app.database.application_log_db import create_log_entry, list_log_entries
from app.models.application_log_model import ApplicationLog
from app.models.users_models import User


def _fake_db():
    """Return a minimal mock that mimics a SQLAlchemy Session."""
    db = MagicMock()
    return db


def _dispatch_query(db, app_log_query_mock, user_query_mock=None):
    """Make db.query(ApplicationLog) and db.query(User) return distinct mocks.

    Plain MagicMock() makes db.query(...) return the same child mock no matter
    what model is passed in, which causes call/filter counts on the
    ApplicationLog query and the User lookup query to bleed into each other.
    This keeps them independent, matching real SQLAlchemy session behaviour.
    """

    def _query(model):
        if model is ApplicationLog:
            return app_log_query_mock
        if model is User:
            return user_query_mock
        return MagicMock()

    db.query.side_effect = _query


class TestCreateLogEntrySuccess:
    def test_all_optional_fields_passed_through(self):
        """Optional kwargs are forwarded to the ApplicationLog constructor."""
        db = _fake_db()
        uid = uuid.uuid4()
        pid = uuid.uuid4()

        create_log_entry(
            db=db,
            service_name="svc",
            http_method="POST",
            endpoint="/api/v1/thing",
            status_code=201,
            user_id=uid,
            message="created",
            project_id=pid,
            client_name="acme",
        )

        added_log = db.add.call_args[0][0]
        assert added_log.service_name == "svc"
        assert added_log.http_method == "POST"
        assert added_log.endpoint == "/api/v1/thing"
        assert added_log.status_code == 201
        assert added_log.user_id == uid
        assert added_log.message == "created"
        assert added_log.project_id == pid
        assert added_log.client_name == "acme"


class TestCreateLogEntryFailure:

    def test_logger_exception_called_on_failure(self):
        """logger.exception('application_log_create_entry_failed') is called."""
        db = _fake_db()
        db.commit.side_effect = IOError("disk full")

        with patch("app.database.application_log_db.logger") as mock_logger:
            with pytest.raises(DatabaseOperationException):
                create_log_entry(
                    db=db,
                    service_name="svc",
                    http_method="DELETE",
                    endpoint="/entries/1",
                )

        mock_logger.exception.assert_called_once_with("application_log_create_entry_failed")


class TestListLogEntriesSuccess:
    """Happy-path tests for list_log_entries."""

    def test_returns_all_entries_when_no_service_name_filter(self):
        """Without a service_name filter, all entries are returned."""
        db = _fake_db()
        fake_entries = [MagicMock(user_id=None), MagicMock(user_id=None)]

        query_mock = MagicMock()
        _dispatch_query(db, query_mock)
        query_mock.count.return_value = 2
        offset_query = query_mock.order_by.return_value.offset.return_value
        offset_query.limit.return_value.all.return_value = fake_entries

        entries, total = list_log_entries(db)

        assert entries == fake_entries
        assert total == 2
        # filter should NOT have been called
        query_mock.filter.assert_not_called()

    def test_filters_by_lowercased_service_name(self):
        """When service_name is provided it is lowercased before filtering."""
        db = _fake_db()
        fake_entries = [MagicMock(user_id=None)]

        query_mock = MagicMock()
        _dispatch_query(db, query_mock)
        filtered_query = query_mock.filter.return_value
        filtered_query.count.return_value = 1
        offset_query = filtered_query.order_by.return_value.offset.return_value
        offset_query.limit.return_value.all.return_value = fake_entries

        entries, total = list_log_entries(db, service_name="Jira")

        assert entries == fake_entries
        assert total == 1
        query_mock.filter.assert_called_once()

    def test_filters_by_multiple_comma_separated_service_names(self):
        """Multiple comma-separated service names use an IN filter."""
        db = _fake_db()
        fake_entries = [MagicMock(user_id=None)]

        query_mock = MagicMock()
        _dispatch_query(db, query_mock)
        filtered_query = query_mock.filter.return_value
        filtered_query.count.return_value = 1
        offset_query = filtered_query.order_by.return_value.offset.return_value
        offset_query.limit.return_value.all.return_value = fake_entries

        entries, total = list_log_entries(db, service_name="jira, ai")

        assert entries == fake_entries
        assert total == 1
        query_mock.filter.assert_called_once()

    def test_filters_by_project_id(self):
        """A project_id filter is applied when provided."""
        db = _fake_db()
        fake_entries = [MagicMock(user_id=None)]
        pid = uuid.uuid4()

        query_mock = MagicMock()
        _dispatch_query(db, query_mock)
        filtered_query = query_mock.filter.return_value
        filtered_query.count.return_value = 1
        offset_query = filtered_query.order_by.return_value.offset.return_value
        offset_query.limit.return_value.all.return_value = fake_entries

        entries, total = list_log_entries(db, project_id=pid)

        assert entries == fake_entries
        assert total == 1
        query_mock.filter.assert_called_once()

    def test_service_name_with_only_blank_entries_applies_no_filter(self):
        """A service_name of only commas/whitespace applies no filter."""
        db = _fake_db()
        fake_entries = [MagicMock(user_id=None)]

        query_mock = MagicMock()
        _dispatch_query(db, query_mock)
        query_mock.count.return_value = 1
        offset_query = query_mock.order_by.return_value.offset.return_value
        offset_query.limit.return_value.all.return_value = fake_entries

        entries, total = list_log_entries(db, service_name=" , ,")

        assert entries == fake_entries
        assert total == 1
        query_mock.filter.assert_not_called()

    def test_resolves_user_email_and_name_for_entries_with_user_id(self):
        """Entries with a user_id get user_email/user_name attached via the User lookup."""
        db = _fake_db()
        uid = uuid.uuid4()
        entry = MagicMock(user_id=uid)
        fake_entries = [entry]

        query_mock = MagicMock()
        user_query_mock = MagicMock()
        _dispatch_query(db, query_mock, user_query_mock)

        query_mock.count.return_value = 1
        offset_query = query_mock.order_by.return_value.offset.return_value
        offset_query.limit.return_value.all.return_value = fake_entries

        fake_user = MagicMock(id=uid, email="jane@example.com")
        fake_user.name = "Jane Doe"
        user_query_mock.filter.return_value.all.return_value = [fake_user]

        entries, total = list_log_entries(db)

        assert entries == fake_entries
        assert total == 1
        user_query_mock.filter.assert_called_once()
        assert entry.user_email == "jane@example.com"
        assert entry.user_name == "Jane Doe"
        # the ApplicationLog query's own filter must not be touched by the user lookup
        query_mock.filter.assert_not_called()

    def test_entry_without_matching_user_gets_none_email_and_name(self):
        """If no User row matches the entry's user_id, email/name are None."""
        db = _fake_db()
        uid = uuid.uuid4()
        entry = MagicMock(user_id=uid)
        fake_entries = [entry]

        query_mock = MagicMock()
        user_query_mock = MagicMock()
        _dispatch_query(db, query_mock, user_query_mock)

        query_mock.count.return_value = 1
        offset_query = query_mock.order_by.return_value.offset.return_value
        offset_query.limit.return_value.all.return_value = fake_entries

        user_query_mock.filter.return_value.all.return_value = []

        entries, total = list_log_entries(db)

        assert entries == fake_entries
        assert entry.user_email is None
        assert entry.user_name is None

    def test_entry_with_no_user_id_skips_lookup(self):
        """Entries with no user_id get None email/name and no User lookup is issued."""
        db = _fake_db()
        entry = MagicMock(user_id=None)
        fake_entries = [entry]

        query_mock = MagicMock()
        user_query_mock = MagicMock()
        _dispatch_query(db, query_mock, user_query_mock)

        query_mock.count.return_value = 1
        offset_query = query_mock.order_by.return_value.offset.return_value
        offset_query.limit.return_value.all.return_value = fake_entries

        entries, total = list_log_entries(db)

        assert entries == fake_entries
        assert entry.user_email is None
        assert entry.user_name is None
        user_query_mock.filter.assert_not_called()


class TestListLogEntriesFailure:
    """Error-path tests for list_log_entries."""

    def test_raises_database_operation_exception_on_error(self):
        """Any DB error is wrapped in DatabaseOperationException."""
        db = _fake_db()
        db.query.side_effect = RuntimeError("connection lost")

        with pytest.raises(DatabaseOperationException):
            list_log_entries(db)

    def test_logger_exception_called_on_failure(self):
        """logger.exception('application_log_list_failed') is invoked on error."""
        db = _fake_db()
        db.query.side_effect = RuntimeError("connection lost")

        with patch("app.database.application_log_db.logger") as mock_logger:
            with pytest.raises(DatabaseOperationException):
                list_log_entries(db)

        mock_logger.exception.assert_called_once_with("application_log_list_failed")
