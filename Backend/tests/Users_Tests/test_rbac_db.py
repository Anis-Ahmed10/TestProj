from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.exceptions import DatabaseOperationException
from app.database.rbac_db import get_permissions_for_role


def _db_returning(names: list[str]) -> MagicMock:
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = names
    return db


class TestGetPermissionsForRole:
    def test_returns_permission_names_for_role(self) -> None:
        db = _db_returning(["client:read", "client:create"])

        result = get_permissions_for_role(db, "Test Lead")

        assert result == frozenset({"client:read", "client:create"})
        db.execute.assert_called_once()

    def test_role_with_no_permissions_returns_empty(self) -> None:
        db = _db_returning([])
        assert get_permissions_for_role(db, "Test Engineer") == frozenset()

    @pytest.mark.parametrize("role_name", [None, "", "   "])
    def test_blank_role_short_circuits_without_querying(self, role_name) -> None:
        db = MagicMock()
        assert get_permissions_for_role(db, role_name) == frozenset()
        db.execute.assert_not_called()

    def test_db_error_is_wrapped(self) -> None:
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        with pytest.raises(DatabaseOperationException):
            get_permissions_for_role(db, "Test Lead")
