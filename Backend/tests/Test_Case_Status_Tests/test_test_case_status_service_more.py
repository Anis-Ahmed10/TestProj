from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.selectable import Select

import app.services.test_case_service as svc
from app.schemas.test_cases import TestCaseStatus


@dataclass
class FakeRow:
    id: UUID
    status: str | None


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class SessionThatAcceptsSelect:
    """Minimal fake session to cover `_iter_test_cases_for_ids` without a real DB."""

    def __init__(self, rows: list[FakeRow], *, fail_on_execute: bool = False):
        self._rows = rows
        self.fail_on_execute = fail_on_execute
        self.execute_called = 0

    def execute(self, stmt: Select):
        self.execute_called += 1
        if self.fail_on_execute:
            raise SQLAlchemyError("db down")
        # service only uses `.scalars().all()`; we return an object implementing that chain
        return FakeScalarResult(self._rows)

    def begin_nested(self):
        """Return a no-op savepoint context manager."""

        class _NoOpSavepoint:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return _NoOpSavepoint()

    def add(self, tc):
        pass

    def refresh(self, tc):
        pass

    def rollback(self):
        pass


def test_normalize_uuid_accepts_uuid_instance():
    u = uuid4()
    assert svc._normalize_uuid(u) == u


def test_iter_test_cases_for_ids_empty_returns_empty_list():
    db = SessionThatAcceptsSelect([])
    rows = svc._iter_test_cases_for_ids(db, test_case_ids=[])
    assert rows == []
    assert db.execute_called == 0


def test_iter_test_cases_for_ids_happy_path_executes_and_returns_rows():
    rows = [FakeRow(id=uuid4(), status=TestCaseStatus.pending.value)]
    db = SessionThatAcceptsSelect(rows)

    ids = [rows[0].id]
    out = svc._iter_test_cases_for_ids(db, test_case_ids=ids)

    # `_iter_test_cases_for_ids` returns `scalars().all()` => list
    assert out == rows
    assert db.execute_called == 1


def test_iter_test_cases_for_ids_with_project_id_executes_and_returns_rows():
    rows = [FakeRow(id=uuid4(), status=TestCaseStatus.pending.value)]
    db = SessionThatAcceptsSelect(rows)

    ids = [rows[0].id]
    out = svc._iter_test_cases_for_ids(db, test_case_ids=ids, project_id=uuid4())

    assert out == rows
    assert db.execute_called == 1


def test_iter_test_cases_for_ids_sqlalchemy_error_bubbles():
    db = SessionThatAcceptsSelect([], fail_on_execute=True)

    ids = [uuid4()]
    with pytest.raises(SQLAlchemyError):
        _ = svc._iter_test_cases_for_ids(db, test_case_ids=ids)


def test_bulk_update_status_by_ids_exception_handler_status_conversion_succeeds(monkeypatch):
    """Covers the except-handler branch where `TestCaseStatus(pre_mutation_status_str)` succeeds.

    Fix 3: the pre-mutation value is captured before tc.status is mutated, so the
    error handler always reads the original status even after a failed savepoint.
    """

    row = FakeRow(id=uuid4(), status=TestCaseStatus.pending.value)

    def _iter_ok(_db, *, test_case_ids):
        return [row]

    monkeypatch.setattr(svc, "_iter_test_cases_for_ids", _iter_ok)
    # Force validate_transition to fail; then except-handler will do
    # `TestCaseStatus(pre_mutation_status_str)`.
    # Since the original tc.status is a valid enum value, `status` should be non-None.
    monkeypatch.setattr(
        svc,
        "validate_transition",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("nope")),
    )

    db = SessionThatAcceptsSelect([])
    # Patch add/commit/rollback/refresh onto this fake session instance.
    db.added = []  # type: ignore[attr-defined]

    def _add(tc):
        db.added.append(tc)  # type: ignore[attr-defined]

    def _commit():
        return None

    def _refresh(_tc):
        return None

    def _rollback():
        return None

    db.add = _add  # type: ignore[attr-defined]
    db.commit = _commit  # type: ignore[attr-defined]
    db.refresh = _refresh  # type: ignore[attr-defined]
    db.rollback = _rollback  # type: ignore[attr-defined]

    result = svc.bulk_update_status_by_ids(
        db, test_case_ids=[str(row.id)], new_status=TestCaseStatus.approved
    )

    assert result["found_count"] == 1
    assert result["updated_count"] == 0
    assert result["results"][0]["success"] is False
    # Pre-mutation status (pending) must be reported, not the target (approved)
    assert result["results"][0]["status"] == TestCaseStatus.pending
    assert "nope" in result["results"][0]["error"]
