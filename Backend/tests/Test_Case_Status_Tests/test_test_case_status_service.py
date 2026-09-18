from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

import app.services.test_case_service as svc
from app.schemas.test_cases import TestCaseStatus


@dataclass
class FakeRow:
    id: UUID
    status: str | None


class FakeSavepoint:
    """Context manager that mimics db.begin_nested() (a SQLAlchemy savepoint)."""

    def __init__(self, session: "FakeSession"):
        self._session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Simulate savepoint rollback: undo last added row
            self._session._savepoint_rollback()
        return False  # Do not suppress exceptions


class FakeSession:
    def __init__(self, rows_by_ids: dict[UUID, Any] | None = None, fail_on_execute: bool = False):
        self.rows_by_ids = rows_by_ids or {}
        self.fail_on_execute = fail_on_execute
        self.commits: list[FakeRow] = []
        self.rollbacks = 0
        self.added: list[FakeRow] = []
        self._savepoint_staged: list[FakeRow] = []

    def execute(self, stmt):
        if self.fail_on_execute:
            raise SQLAlchemyError("db down")
        raise AssertionError("FakeSession.execute should not be called in these tests")

    def add(self, tc):
        self.added.append(tc)
        self._savepoint_staged.append(tc)

    def commit(self):
        # commit is called only after an in-memory update; record it.
        if self.added:
            self.commits.append(self.added[-1])

    def refresh(self, tc):
        # no-op for in-memory objects
        return None

    def rollback(self):
        self.rollbacks += 1

    def begin_nested(self):
        """Return a savepoint context manager."""
        return FakeSavepoint(self)

    def _savepoint_rollback(self):
        """Called by FakeSavepoint on exception to undo staged adds."""
        for row in self._savepoint_staged:
            if row in self.added:
                self.added.remove(row)
        self._savepoint_staged.clear()


def test_bulk_update_status_by_ids_empty_returns_early():
    db = FakeSession()
    result = svc.bulk_update_status_by_ids(
        db, test_case_ids=[], new_status=TestCaseStatus.approved
    )
    assert result == {"found_count": 0, "updated_count": 0, "results": []}


def test_bulk_update_status_by_ids_invalid_uuid_format_raises_value_error():
    db = FakeSession()
    with pytest.raises(ValueError) as exc:
        svc.bulk_update_status_by_ids(
            db, test_case_ids=["not-a-uuid"], new_status=TestCaseStatus.approved
        )

    assert "Invalid id format" in str(exc.value)


def test_bulk_update_status_by_ids_fetch_sqlalchemy_error_is_reraised(monkeypatch):
    db = FakeSession()

    def _iter_fail(_db, *, test_case_ids):
        raise SQLAlchemyError("boom")

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_fail)

    with pytest.raises(SQLAlchemyError):
        svc.bulk_update_status_by_ids(
            db, test_case_ids=[str(uuid4())], new_status=TestCaseStatus.approved
        )


def test_bulk_update_status_by_ids_row_failure_rolls_back_savepoint_and_sets_status_none(
    monkeypatch,
):
    """Fix 1 + Fix 3: savepoint rolls back; status in result is pre-mutation value."""
    row = FakeRow(id=uuid4(), status="bad_status_value")
    db = FakeSession()

    def _iter_ok(_db, *, test_case_ids):
        return [row]

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_ok)
    monkeypatch.setattr(
        svc,
        "validate_transition",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("nope")),
    )

    result = svc.bulk_update_status_by_ids(
        db, test_case_ids=[str(row.id)], new_status=TestCaseStatus.approved
    )

    assert result["found_count"] == 1
    assert result["updated_count"] == 0
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == str(row.id)
    assert result["results"][0]["success"] is False
    # "bad_status_value" can't be parsed as TestCaseStatus → status must be None
    assert result["results"][0]["status"] is None
    assert result["results"][0]["error"] is not None
    # Outer rollback must NOT have been called (savepoint handles isolation)
    assert db.rollbacks == 0


def test_bulk_update_status_by_ids_row_success_commits_and_returns_updated_status(monkeypatch):
    row = FakeRow(id=uuid4(), status=TestCaseStatus.pending.value)
    db = FakeSession()

    def _iter_ok(_db, *, test_case_ids):
        return [row]

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_ok)

    result = svc.bulk_update_status_by_ids(
        db, test_case_ids=[str(row.id)], new_status=TestCaseStatus.approved
    )

    assert result["found_count"] == 1
    assert result["updated_count"] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == str(row.id)
    assert result["results"][0]["success"] is True
    assert result["results"][0]["error"] is None
    assert result["results"][0]["status"] == TestCaseStatus.approved
    assert row.status == TestCaseStatus.approved.value
    assert db.rollbacks == 0


def test_bulk_update_status_by_ids_pre_mutation_status_reported_on_commit_failure(monkeypatch):
    """Error handler reports the ORIGINAL status, not the mutated new_status value."""
    original_status = TestCaseStatus.pending.value
    row = FakeRow(id=uuid4(), status=original_status)
    db = FakeSession()

    def _iter_ok(_db, *, test_case_ids):
        return [row]

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_ok)

    def _failing_add(_tc):
        raise RuntimeError("row update failed")

    db.add = _failing_add

    result = svc.bulk_update_status_by_ids(
        db, test_case_ids=[str(row.id)], new_status=TestCaseStatus.approved
    )

    assert result["found_count"] == 1
    assert result["updated_count"] == 0
    r = result["results"][0]
    assert r["success"] is False
    # Must report the ORIGINAL status (pending), not the target (approved)
    assert r["status"] == TestCaseStatus.pending
    assert "row update failed" in r["error"]


def test_bulk_update_status_by_ids_commit_failure_triggers_rollback(monkeypatch):
    original_status = TestCaseStatus.pending.value
    row = FakeRow(id=uuid4(), status=original_status)
    db = FakeSession()

    def _iter_ok(_db, *, test_case_ids):
        return [row]

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_ok)

    def _failing_commit():
        raise RuntimeError("commit failed")

    db.commit = _failing_commit

    with pytest.raises(RuntimeError) as exc:
        svc.bulk_update_status_by_ids(
            db, test_case_ids=[str(row.id)], new_status=TestCaseStatus.approved
        )

    assert "commit failed" in str(exc.value)
    assert db.rollbacks == 1


def test_bulk_update_status_by_ids_invalid_current_status_sets_status_none(monkeypatch):
    """Fix 3: covers the branch where pre_mutation_status_str itself is an invalid enum value."""

    row = FakeRow(id=uuid4(), status="not-a-valid-enum")

    db = FakeSession()

    def _iter_ok(_db, *, test_case_ids):
        return [row]

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_ok)

    # validate_transition will raise because TestCaseStatus("not-a-valid-enum") fails first,
    # so we just let the service run naturally.
    result = svc.bulk_update_status_by_ids(
        db,
        test_case_ids=[str(row.id)],
        new_status=TestCaseStatus.approved,
    )

    assert result["found_count"] == 1
    assert result["updated_count"] == 0
    assert result["results"][0]["id"] == str(row.id)
    assert result["results"][0]["success"] is False
    assert result["results"][0]["status"] is None


def test_bulk_update_status_by_ids_not_found_ids_reported_in_results(monkeypatch):
    """Fix 5: IDs present in the request but absent from the DB appear as not-found entries."""
    existing_row = FakeRow(id=uuid4(), status=TestCaseStatus.pending.value)
    missing_id = uuid4()

    db = FakeSession()

    def _iter_ok(_db, *, test_case_ids):
        # Only return the existing row, simulating one missing ID
        return [existing_row]

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_ok)

    result = svc.bulk_update_status_by_ids(
        db,
        test_case_ids=[str(existing_row.id), str(missing_id)],
        new_status=TestCaseStatus.approved,
    )

    assert result["found_count"] == 1  # only 1 row found in DB
    assert result["updated_count"] == 1  # the found row was updated
    assert len(result["results"]) == 2  # 1 success + 1 not-found

    result_by_id = {r["id"]: r for r in result["results"]}

    # The found row should succeed
    assert result_by_id[str(existing_row.id)]["success"] is True

    # The missing row should have a not-found error
    assert result_by_id[str(missing_id)]["success"] is False
    assert result_by_id[str(missing_id)]["error"] == "not found"
    assert result_by_id[str(missing_id)]["status"] is None


def test_bulk_update_status_by_ids_structured_logging_on_row_failure(monkeypatch, caplog):
    """Fix 4: warning log uses event-name message + extra={} with snake_case keys."""
    row = FakeRow(id=uuid4(), status=TestCaseStatus.pending.value)
    db = FakeSession()

    def _iter_ok(_db, *, test_case_ids):
        return [row]

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_ok)
    monkeypatch.setattr(
        svc,
        "validate_transition",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("forced error")),
    )

    with caplog.at_level(logging.WARNING, logger="app.services.test_case_service"):
        svc.bulk_update_status_by_ids(
            db, test_case_ids=[str(row.id)], new_status=TestCaseStatus.approved
        )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    # Event name is the message string
    assert record.getMessage() == "bulk_update_row_failed"
    # User data is in extra fields, not interpolated into the message
    assert hasattr(record, "tc_id")
    assert record.tc_id == str(row.id)
    assert hasattr(record, "error")
    assert "forced error" in record.error


def test_validate_transition_allows_expected_transitions():
    # pending -> approved is allowed
    svc.validate_transition(TestCaseStatus.pending, TestCaseStatus.approved)

    # approved -> archived is allowed
    svc.validate_transition(TestCaseStatus.approved, TestCaseStatus.archived)

    # archived -> pending is allowed
    svc.validate_transition(TestCaseStatus.archived, TestCaseStatus.pending)


def test_validate_transition_rejects_disallowed_transition():
    with pytest.raises(ValueError):
        svc.validate_transition(TestCaseStatus.pending, TestCaseStatus.pending)


# ---------------------------------------------------------------------------
# Direct tests for the two extracted helper functions
# ---------------------------------------------------------------------------


def test_build_not_found_result_returns_correct_shape():
    """_build_not_found_result must return a BulkRowResult with the expected fields."""
    uid = uuid4()
    result = svc._build_not_found_result(uid)

    assert result.id == str(uid)
    assert result.status is None
    assert result.success is False
    assert result.error == "not found"


def test_update_single_test_case_success_path():
    """_update_single_test_case returns (result, True) when the transition succeeds."""
    row = FakeRow(id=uuid4(), status=TestCaseStatus.pending.value)
    db = FakeSession()

    result, was_updated = svc._update_single_test_case(db, row, TestCaseStatus.approved)

    assert was_updated is True
    assert result.success is True
    assert result.id == str(row.id)
    assert result.error is None
    assert result.status == TestCaseStatus.approved


def test_update_single_test_case_invalid_current_status_returns_status_none():
    """_update_single_test_case captures pre_mutation_status_str and returns status=None
    when that string cannot be parsed as a TestCaseStatus enum value.
    """
    row = FakeRow(id=uuid4(), status="not-a-valid-enum")
    db = FakeSession()

    result, was_updated = svc._update_single_test_case(db, row, TestCaseStatus.approved)

    assert was_updated is False
    assert result.success is False
    assert result.status is None
    assert result.error is not None


def test_update_single_test_case_transition_failure_reports_original_status(monkeypatch):
    row = FakeRow(id=uuid4(), status=TestCaseStatus.pending.value)
    db = FakeSession()

    monkeypatch.setattr(
        svc,
        "validate_transition",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad transition")),
    )

    result, was_updated = svc._update_single_test_case(db, row, TestCaseStatus.approved)

    assert was_updated is False
    assert result.success is False
    # Pre-mutation status must be reported (pending), not the target (approved)
    assert result.status == TestCaseStatus.pending
    assert "bad transition" in result.error


def test_bulk_update_status_by_ids_duplicate_ids_are_deduplicated(monkeypatch):
    row = FakeRow(id=uuid4(), status=TestCaseStatus.pending.value)
    db = FakeSession()

    def _iter_ok(_db, *, test_case_ids):
        assert len(test_case_ids) == 1
        return [row]

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_ok)

    result = svc.bulk_update_status_by_ids(
        db,
        test_case_ids=[str(row.id), str(row.id)],
        new_status=TestCaseStatus.approved,
    )

    assert result["found_count"] == 1
    assert result["updated_count"] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == str(row.id)
    assert result["results"][0]["success"] is True


def test_bulk_update_status_by_ids_with_project_id(monkeypatch):
    row = FakeRow(id=uuid4(), status=TestCaseStatus.pending.value)
    db = FakeSession()
    captured = {}

    def _iter_ok(_db, *, test_case_ids, project_id=None):
        captured["project_id"] = project_id
        return [row]

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_ok)

    target_project_id = uuid4()
    result = svc.bulk_update_status_by_ids(
        db,
        test_case_ids=[str(row.id)],
        new_status=TestCaseStatus.approved,
        project_id=target_project_id,
    )

    assert result["found_count"] == 1
    assert result["updated_count"] == 1
    assert captured["project_id"] == target_project_id
