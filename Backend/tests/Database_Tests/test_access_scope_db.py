"""Unit tests for app.database.access_scope_db."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch
from uuid import UUID

from app.core.exceptions import DatabaseOperationException
from app.database.access_scope_db import (
    get_visible_client_ids,
    get_visible_counts_by_client,
    get_visible_programme_ids,
    get_visible_project_ids,
)

_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
_ID_1 = UUID("11111111-1111-1111-1111-111111111111")
_ID_2 = UUID("22222222-2222-2222-2222-222222222222")

_MODULE = "app.database.access_scope_db"


def _user(role: str | None):
    """Minimal stand-in for a User row; only .role is read."""
    return SimpleNamespace(role=role)


def _db_returning_scalars(items):
    db = MagicMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = items
    db.execute.return_value = execute_result
    return db


def _db_returning_all(*row_sets):
    db = MagicMock()
    results = []
    for rows in row_sets:
        result = MagicMock()
        result.all.return_value = rows
        results.append(result)
    db.execute.side_effect = results
    return db


# ---------------------------------------------------------------------------
# get_visible_client_ids / get_visible_programme_ids / get_visible_project_ids
# ---------------------------------------------------------------------------

_SCALAR_FUNCS = {
    "client": get_visible_client_ids,
    "programme": get_visible_programme_ids,
    "project": get_visible_project_ids,
}


class VisibleIdsScalarFunctionsTests(unittest.TestCase):
    """Shared behavior across get_visible_{client,programme,project}_ids."""

    def test_manager_returns_scoped_ids(self) -> None:
        for label, func in _SCALAR_FUNCS.items():
            with self.subTest(level=label):
                db = _db_returning_scalars([_ID_1, _ID_2])
                with patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Manager")):
                    result = func(db, _USER_ID)
                self.assertEqual(result, {_ID_1, _ID_2})

    def test_lead_returns_scoped_ids(self) -> None:
        for label, func in _SCALAR_FUNCS.items():
            with self.subTest(level=label):
                db = _db_returning_scalars([_ID_1])
                with patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Lead")):
                    result = func(db, _USER_ID)
                self.assertEqual(result, {_ID_1})

    def test_engineer_returns_scoped_ids(self) -> None:
        for label, func in _SCALAR_FUNCS.items():
            with self.subTest(level=label):
                db = _db_returning_scalars([_ID_2])
                with patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Engineer")):
                    result = func(db, _USER_ID)
                self.assertEqual(result, {_ID_2})

    def test_no_visible_rows_returns_empty_set_not_none(self) -> None:
        for label, func in _SCALAR_FUNCS.items():
            with self.subTest(level=label):
                db = _db_returning_scalars([])
                with patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Manager")):
                    result = func(db, _USER_ID)
                self.assertEqual(result, set())
                self.assertIsNotNone(result)

    def test_unknown_user_fails_closed(self) -> None:
        for label, func in _SCALAR_FUNCS.items():
            with self.subTest(level=label):
                db = MagicMock()
                with patch(f"{_MODULE}.get_user_by_id", return_value=None):
                    result = func(db, _USER_ID)
                self.assertEqual(result, set())
                db.execute.assert_not_called()

    def test_unmapped_role_fails_closed(self) -> None:
        for label, func in _SCALAR_FUNCS.items():
            with self.subTest(level=label):
                db = MagicMock()
                with patch(f"{_MODULE}.get_user_by_id", return_value=_user("Some Other Role")):
                    result = func(db, _USER_ID)
                self.assertEqual(result, set())
                db.execute.assert_not_called()

    def test_none_role_fails_closed(self) -> None:
        """A user with no role assigned at all (nullable in the DB) also
        fails closed rather than being treated as unrestricted."""
        for label, func in _SCALAR_FUNCS.items():
            with self.subTest(level=label):
                db = MagicMock()
                with patch(f"{_MODULE}.get_user_by_id", return_value=_user(None)):
                    result = func(db, _USER_ID)
                self.assertEqual(result, set())

    def test_wraps_unexpected_error(self) -> None:
        for label, func in _SCALAR_FUNCS.items():
            with self.subTest(level=label):
                db = MagicMock()
                db.execute.side_effect = RuntimeError("boom")
                with patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Manager")):
                    with self.assertRaises(DatabaseOperationException):
                        func(db, _USER_ID)

    def test_reraises_database_operation_exception_unwrapped(self) -> None:
        for label, func in _SCALAR_FUNCS.items():
            with self.subTest(level=label):
                original = DatabaseOperationException("db down")
                db = MagicMock()
                db.execute.side_effect = original
                with patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Manager")):
                    with self.assertRaises(DatabaseOperationException) as context:
                        func(db, _USER_ID)
                self.assertIs(context.exception, original)


_ID_3 = UUID("33333333-3333-3333-3333-333333333333")

_RULE_HELPERS = {
    "client": ("_client_ids_managed", "_client_ids_led", "_client_ids_via_membership"),
    "programme": (
        "_programme_ids_managed",
        "_programme_ids_led",
        "_programme_ids_via_membership",
    ),
    "project": ("_project_ids_managed", "_project_ids_led", "_project_ids_via_membership"),
}


class VisibilityIsAdditiveAcrossAssignmentsTests(unittest.TestCase):
    """Every assignment rule is consulted for every role, and the results union.

    Keying visibility off the role instead made the rules mutually exclusive, so
    adding a Lead or Manager to a project team granted them no visibility at all —
    only the team-membership rule would have been skipped for them.
    """

    def _run(self, level, role):
        func = _SCALAR_FUNCS[level]
        managed, led, member = _RULE_HELPERS[level]
        db = MagicMock()
        with (
            patch(f"{_MODULE}.get_user_by_id", return_value=_user(role)),
            patch(f"{_MODULE}.{managed}", return_value={_ID_1}) as mock_managed,
            patch(f"{_MODULE}.{led}", return_value={_ID_2}) as mock_led,
            patch(f"{_MODULE}.{member}", return_value={_ID_3}) as mock_member,
        ):
            result = func(db, _USER_ID)
        return result, (mock_managed, mock_led, mock_member)

    def test_every_role_gets_the_union_of_all_three_rules(self) -> None:
        for role in ("Test Manager", "Test Lead", "Test Engineer"):
            for level in _SCALAR_FUNCS:
                with self.subTest(role=role, level=level):
                    result, mocks = self._run(level, role)
                    self.assertEqual(result, {_ID_1, _ID_2, _ID_3})
                    for mock in mocks:
                        mock.assert_called_once_with(ANY, _USER_ID)

    def test_team_membership_alone_makes_a_project_visible_to_a_lead(self) -> None:
        """The reported bug: a Test Lead added to a project team saw nothing."""
        db = MagicMock()
        with (
            patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Lead")),
            patch(f"{_MODULE}._project_ids_managed", return_value=set()),
            patch(f"{_MODULE}._project_ids_led", return_value=set()),
            patch(f"{_MODULE}._project_ids_via_membership", return_value={_ID_1}),
        ):
            result = get_visible_project_ids(db, _USER_ID)

        self.assertEqual(result, {_ID_1})

    def test_team_membership_alone_makes_a_project_visible_to_a_manager(self) -> None:
        db = MagicMock()
        with (
            patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Manager")),
            patch(f"{_MODULE}._project_ids_managed", return_value=set()),
            patch(f"{_MODULE}._project_ids_led", return_value=set()),
            patch(f"{_MODULE}._project_ids_via_membership", return_value={_ID_1}),
        ):
            result = get_visible_project_ids(db, _USER_ID)

        self.assertEqual(result, {_ID_1})


# ---------------------------------------------------------------------------
# get_visible_counts_by_client
# ---------------------------------------------------------------------------


class GetVisibleCountsByClientTests(unittest.TestCase):
    def test_manager_returns_none(self) -> None:
        """Manager's client-wide totals are already correct; no override."""
        db = MagicMock()
        with patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Manager")):
            result = get_visible_counts_by_client(db, _USER_ID)
        self.assertIsNone(result)
        db.execute.assert_not_called()

    def test_unknown_user_returns_empty_dict(self) -> None:
        db = MagicMock()
        with patch(f"{_MODULE}.get_user_by_id", return_value=None):
            result = get_visible_counts_by_client(db, _USER_ID)
        self.assertEqual(result, {})

    def test_unmapped_role_returns_empty_dict(self) -> None:
        db = MagicMock()
        with patch(f"{_MODULE}.get_user_by_id", return_value=_user("Some Other Role")):
            result = get_visible_counts_by_client(db, _USER_ID)
        self.assertEqual(result, {})

    def test_lead_with_no_visible_ids_returns_empty_dict(self) -> None:
        db = MagicMock()
        with (
            patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Lead")),
            patch(f"{_MODULE}.get_visible_programme_ids", return_value=set()),
            patch(f"{_MODULE}.get_visible_project_ids", return_value=set()),
        ):
            result = get_visible_counts_by_client(db, _USER_ID)
        self.assertEqual(result, {})
        db.execute.assert_not_called()

    def test_falls_back_to_none_if_underlying_visibility_is_unrestricted(self) -> None:
        db = MagicMock()
        with (
            patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Lead")),
            patch(f"{_MODULE}.get_visible_programme_ids", return_value={_ID_1}),
            patch(f"{_MODULE}.get_visible_project_ids", return_value=None),
        ):
            result = get_visible_counts_by_client(db, _USER_ID)
        self.assertIsNone(result)

    def test_lead_scopes_counts_per_client(self) -> None:
        client_a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        client_b = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        programme_1 = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        project_1 = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
        project_2 = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
        member_1 = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        member_2 = UUID("00000000-1111-2222-3333-444444444444")

        # Query order inside get_visible_counts_by_client: programmes, then
        # projects, then members.
        db = _db_returning_all(
            [(client_a, programme_1)],  # programmes query
            [(client_a, project_1), (client_b, project_2)],  # projects query
            [(client_a, member_1), (client_a, member_2)],  # members query
        )

        with (
            patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Lead")),
            patch(f"{_MODULE}.get_visible_programme_ids", return_value={programme_1}),
            patch(f"{_MODULE}.get_visible_project_ids", return_value={project_1, project_2}),
        ):
            result = get_visible_counts_by_client(db, _USER_ID)

        self.assertEqual(
            result[client_a],
            {"programmes_count": 1, "projects_count": 1, "active_members_count": 2},
        )
        self.assertEqual(
            result[client_b],
            {"programmes_count": 0, "projects_count": 1, "active_members_count": 0},
        )

    def test_wraps_unexpected_error(self) -> None:
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        with (
            patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Lead")),
            patch(f"{_MODULE}.get_visible_programme_ids", return_value={_ID_1}),
            patch(f"{_MODULE}.get_visible_project_ids", return_value={_ID_2}),
        ):
            with self.assertRaises(DatabaseOperationException):
                get_visible_counts_by_client(db, _USER_ID)

    def test_reraises_database_operation_exception_unwrapped(self) -> None:
        original = DatabaseOperationException("db down")
        db = MagicMock()
        db.execute.side_effect = original
        with (
            patch(f"{_MODULE}.get_user_by_id", return_value=_user("Test Lead")),
            patch(f"{_MODULE}.get_visible_programme_ids", return_value={_ID_1}),
            patch(f"{_MODULE}.get_visible_project_ids", return_value={_ID_2}),
        ):
            with self.assertRaises(DatabaseOperationException) as context:
                get_visible_counts_by_client(db, _USER_ID)
        self.assertIs(context.exception, original)


if __name__ == "__main__":
    unittest.main()
