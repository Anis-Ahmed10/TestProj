"""Unit tests for app/database/crud_test_cases.py — 100% coverage."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.database import crud_test_cases
from app.database.crud_test_cases import (
    _insert_test_case,
    _load_existing_rows,
    _next_available_id,
    _read_sql_file,
    bulk_save_test_cases,
    count_test_cases_by_project,
    update_jira_key,
)

# ──────────────────────────────────────────────────────────────────
# TestCaseSaveResult dataclass
# ──────────────────────────────────────────────────────────────────


class TestTestCaseSaveResult:
    def test_defaults(self):
        r = crud_test_cases.TestCaseSaveResult()
        assert r.inserted == []
        assert r.skipped == []
        assert r.renamed == []
        assert r.failed == []


# ──────────────────────────────────────────────────────────────────
# _next_available_id
# ──────────────────────────────────────────────────────────────────


class TestNextAvailableId:
    def test_returns_base_1_when_free(self):
        assert _next_available_id("TC-1", set()) == "TC-1_1"

    def test_increments_counter_when_taken(self):
        existing = {"TC-1_1", "TC-1_2"}
        assert _next_available_id("TC-1", existing) == "TC-1_3"

    def test_single_step_increment(self):
        existing = {"TC-2_1"}
        assert _next_available_id("TC-2", existing) == "TC-2_2"


# ──────────────────────────────────────────────────────────────────
# _load_existing_rows
# ──────────────────────────────────────────────────────────────────


class TestReadSqlFile:
    def test_raises_when_sql_file_is_missing(self):
        with pytest.raises(FileNotFoundError):
            _read_sql_file("missing_sql_file.sql")


class TestLoadExistingRows:
    def _make_db_with_rows(self, rows):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = rows
        return db

    def test_returns_empty_list_when_no_rows(self):
        db = self._make_db_with_rows([])
        result = _load_existing_rows(db, "US-1")
        assert result == []

    def test_parses_test_data_dict(self):
        # FIX: removed the invalid `tc.get("type")` reference — use a plain string instead
        test_data = {
            "tc_id": "TC-1",
            "type": "standard",
            "steps": "step1",
            "expected": "exp1",
            "scenario": {"given": "g", "when": "w", "then": "t"},
            "charter_mission": "mission",
            "charter_scope": "scope",
            "techniques": "tech",
        }
        row = SimpleNamespace(title="Title", test_data=test_data)
        db = self._make_db_with_rows([row])
        result = _load_existing_rows(db, "US-1")
        assert len(result) == 1
        assert result[0]["tc_id"] == "TC-1"
        assert result[0]["steps"] == "step1"
        assert result[0]["given_steps"] == "g"

    def test_handles_none_test_data(self):
        row = SimpleNamespace(title="T", test_data=None)
        db = self._make_db_with_rows([row])
        result = _load_existing_rows(db, "US-1")
        assert result[0]["tc_id"] == ""

    def test_handles_non_dict_test_data(self):
        row = SimpleNamespace(title="T", test_data="not-a-dict")
        db = self._make_db_with_rows([row])
        result = _load_existing_rows(db, "US-1")
        # non-dict gets replaced with {}
        assert result[0]["tc_id"] == ""

    def test_missing_scenario_key(self):
        test_data = {"tc_id": "TC-2"}
        row = SimpleNamespace(title="T", test_data=test_data)
        db = self._make_db_with_rows([row])
        result = _load_existing_rows(db, "US-1")
        assert result[0]["given_steps"] is None
        assert result[0]["when_steps"] is None
        assert result[0]["then_steps"] is None

    def test_raises_when_load_existing_rows_fails(self):
        db = MagicMock()
        db.execute.side_effect = Exception("query failed")

        with pytest.raises(Exception, match="query failed"):
            _load_existing_rows(db, "US-1")


# ──────────────────────────────────────────────────────────────────
# _insert_test_case
# ──────────────────────────────────────────────────────────────────


class TestInsertTestCase:
    def _make_tc(self, **kwargs):
        defaults = {
            "title": "TC title",
            "priority": "High",
            "steps": "step1",
            "expected": "exp",
            "scenario": None,
            "preconditions": None,
            "tags": ["smoke"],
        }
        defaults.update(kwargs)
        return defaults

    def test_executes_insert(self):
        db = MagicMock()
        _insert_test_case(
            db=db,
            tc=self._make_tc(),
            tc_id="TC-1",
            user_story_id="US-1",
            format_type="standard",
            jira_key="JIRA-10",
            created_by="system",
        )
        db.execute.assert_called_once()

    def test_created_by_is_none_in_params(self):
        """created_by column is UUID so we always pass None."""
        db = MagicMock()
        _insert_test_case(
            db=db,
            tc=self._make_tc(),
            tc_id="TC-2",
            user_story_id="US-1",
            format_type="bdd",
            jira_key="",
            created_by="system",
        )
        _, kwargs = db.execute.call_args
        params = db.execute.call_args[0][1]
        assert params["created_by"] is None

    def test_test_data_json_contains_tc_id(self):
        db = MagicMock()
        _insert_test_case(
            db=db,
            tc=self._make_tc(),
            tc_id="TC-99",
            user_story_id="US-2",
            format_type="exploratory",
            jira_key="J-5",
            created_by="system",
        )
        params = db.execute.call_args[0][1]
        test_data = json.loads(params["test_data"])
        assert test_data["tc_id"] == "TC-99"
        assert params["jira_key"] == "J-5"

    def test_id_is_truncated_to_50_chars(self):
        db = MagicMock()
        _insert_test_case(
            db=db,
            tc=self._make_tc(),
            tc_id="TC-X",
            user_story_id="US-1",
            format_type="standard",
            jira_key="",
            created_by="system",
        )
        params = db.execute.call_args[0][1]
        assert len(params["id"]) <= 50

    def test_tags_none_uses_empty_list(self):
        db = MagicMock()
        tc = self._make_tc(tags=None)
        _insert_test_case(
            db=db,
            tc=tc,
            tc_id="TC-3",
            user_story_id="US-1",
            format_type="standard",
            jira_key="",
            created_by="system",
        )
        params = db.execute.call_args[0][1]
        assert params["tags"] == []

    def test_raises_when_insert_fails(self):
        db = MagicMock()
        db.execute.side_effect = Exception("insert failed")

        with pytest.raises(Exception, match="insert failed"):
            _insert_test_case(
                db=db,
                tc=self._make_tc(),
                tc_id="TC-4",
                user_story_id="US-1",
                format_type="standard",
                jira_key="",
                created_by="system",
            )


# ──────────────────────────────────────────────────────────────────
# bulk_save_test_cases
# ──────────────────────────────────────────────────────────────────


def _make_tc_dict(**kwargs):
    defaults = {
        "id": "TC-1",
        "title": "Test Title",
        "priority": "High",
        "steps": "Do this",
        "expected": "See that",
        "scenario": None,
        "tags": [],
    }
    defaults.update(kwargs)
    return defaults


class TestBulkSaveTestCases:
    @patch("app.database.crud_test_cases._insert_test_case")
    @patch("app.database.crud_test_cases._load_existing_rows")
    @patch("app.database.crud_test_cases.build_test_case_signature")
    @patch("app.database.crud_test_cases.build_row_signature")
    def test_inserts_new_test_case(self, mock_row_sig, mock_tc_sig, mock_load, mock_insert):
        mock_load.return_value = []
        mock_tc_sig.return_value = "sig-unique"
        mock_row_sig.return_value = "sig-row"
        db = MagicMock()
        result = bulk_save_test_cases(
            db=db,
            test_cases=[_make_tc_dict()],
            user_story_id="US-1",
            format_type="standard",
            jira_push_results=[{"tc_id": "TC-1", "jira_key": "J-1"}],
        )
        assert "TC-1" in result.inserted
        mock_insert.assert_called_once()

    @patch("app.database.crud_test_cases._insert_test_case")
    @patch("app.database.crud_test_cases._load_existing_rows")
    @patch("app.database.crud_test_cases.build_test_case_signature")
    @patch("app.database.crud_test_cases.build_row_signature")
    def test_skips_duplicate_signature(self, mock_row_sig, mock_tc_sig, mock_load, mock_insert):
        # Existing row has same signature → SKIP
        existing = {
            "tc_id": "TC-OTHER",
            "title": "T",
            "steps": None,
            "expected": None,
            "given_steps": None,
            "when_steps": None,
            "then_steps": None,
            "charter_mission": None,
        }
        mock_load.return_value = [existing]
        mock_row_sig.return_value = "same-sig"
        mock_tc_sig.return_value = "same-sig"
        db = MagicMock()
        result = bulk_save_test_cases(
            db=db,
            test_cases=[_make_tc_dict()],
            user_story_id="US-1",
            format_type="standard",
            jira_push_results=[],
        )
        assert "TC-1" in result.skipped
        mock_insert.assert_not_called()

    @patch("app.database.crud_test_cases._insert_test_case")
    @patch("app.database.crud_test_cases._load_existing_rows")
    @patch("app.database.crud_test_cases.build_test_case_signature")
    @patch("app.database.crud_test_cases.build_row_signature")
    def test_renames_when_id_exists_but_different_content(
        self, mock_row_sig, mock_tc_sig, mock_load, mock_insert
    ):
        existing = {
            "tc_id": "TC-1",
            "title": "T",
            "steps": None,
            "expected": None,
            "given_steps": None,
            "when_steps": None,
            "then_steps": None,
            "charter_mission": None,
        }
        mock_load.return_value = [existing]
        mock_row_sig.return_value = "old-sig"
        mock_tc_sig.return_value = "new-sig"
        db = MagicMock()
        result = bulk_save_test_cases(
            db=db,
            test_cases=[_make_tc_dict()],
            user_story_id="US-1",
            format_type="standard",
            jira_push_results=[],
        )
        assert result.renamed[0]["original"] == "TC-1"
        assert result.renamed[0]["renamed"] == "TC-1_1"

    @patch("app.database.crud_test_cases._insert_test_case")
    @patch("app.database.crud_test_cases._load_existing_rows")
    @patch("app.database.crud_test_cases.build_test_case_signature")
    @patch("app.database.crud_test_cases.build_row_signature")
    def test_failed_when_insert_raises(self, mock_row_sig, mock_tc_sig, mock_load, mock_insert):
        db = MagicMock()

        with (
            patch(
                "app.database.crud_test_cases._load_existing_rows",
                return_value=[],
            ),
            patch(
                "app.database.crud_test_cases._insert_test_case",
                side_effect=Exception("DB boom"),
            ),
        ):
            with pytest.raises(Exception, match="DB boom"):
                bulk_save_test_cases(
                    db=db,
                    test_cases=[
                        {
                            "id": "TC-1",
                            "title": "Test",
                        }
                    ],
                    user_story_id="US-1",
                    format_type="bdd",
                    jira_push_results=[],
                )

        db.rollback.assert_called_once()

    @patch("app.database.crud_test_cases._insert_test_case")
    @patch("app.database.crud_test_cases._load_existing_rows")
    @patch("app.database.crud_test_cases.build_test_case_signature")
    @patch("app.database.crud_test_cases.build_row_signature")
    def test_db_commit_called_on_success(self, mock_row_sig, mock_tc_sig, mock_load, mock_insert):
        mock_load.return_value = []
        mock_tc_sig.return_value = "sig"
        mock_row_sig.return_value = "row"
        db = MagicMock()
        bulk_save_test_cases(
            db=db,
            test_cases=[_make_tc_dict()],
            user_story_id="US-1",
            format_type="standard",
            jira_push_results=[],
        )
        db.commit.assert_called_once()

    @patch("app.database.crud_test_cases._insert_test_case")
    @patch("app.database.crud_test_cases._load_existing_rows")
    @patch("app.database.crud_test_cases.build_test_case_signature")
    @patch("app.database.crud_test_cases.build_row_signature")
    def test_db_commit_failure_raises_and_rolls_back(
        self, mock_row_sig, mock_tc_sig, mock_load, mock_insert
    ):
        mock_load.return_value = []
        mock_tc_sig.return_value = "sig"
        mock_row_sig.return_value = "row"
        db = MagicMock()
        db.commit.side_effect = Exception("commit fail")
        with pytest.raises(Exception, match="commit fail"):
            bulk_save_test_cases(
                db=db,
                test_cases=[_make_tc_dict()],
                user_story_id="US-1",
                format_type="standard",
                jira_push_results=[],
            )
        db.rollback.assert_called_once()

    @patch("app.database.crud_test_cases._insert_test_case")
    @patch("app.database.crud_test_cases._load_existing_rows")
    @patch("app.database.crud_test_cases.build_test_case_signature")
    @patch("app.database.crud_test_cases.build_row_signature")
    def test_missing_id_uses_empty_string(self, mock_row_sig, mock_tc_sig, mock_load, mock_insert):
        tc = {
            "title": "Login Test",
        }

        db = MagicMock()

        result = bulk_save_test_cases(
            db=db,
            test_cases=[tc],
            user_story_id="US-1",
            format_type="bdd",
            jira_push_results=[],
        )

        assert result.inserted == [""]

    @patch("app.database.crud_test_cases._insert_test_case")
    @patch("app.database.crud_test_cases._load_existing_rows")
    @patch("app.database.crud_test_cases.build_test_case_signature")
    @patch("app.database.crud_test_cases.build_row_signature")
    def test_empty_test_cases_returns_empty_summary(
        self, mock_row_sig, mock_tc_sig, mock_load, mock_insert
    ):
        mock_load.return_value = []
        db = MagicMock()
        result = bulk_save_test_cases(
            db=db,
            test_cases=[],
            user_story_id="US-1",
            format_type="standard",
            jira_push_results=[],
        )
        assert result.inserted == []
        assert result.skipped == []

    @patch("app.database.crud_test_cases._insert_test_case")
    @patch("app.database.crud_test_cases._load_existing_rows")
    @patch("app.database.crud_test_cases.build_test_case_signature")
    @patch("app.database.crud_test_cases.build_row_signature")
    def test_jira_key_map_used_when_push_results_provided(
        self, mock_row_sig, mock_tc_sig, mock_load, mock_insert
    ):
        mock_load.return_value = []
        mock_tc_sig.return_value = "sig3"
        mock_row_sig.return_value = "row3"
        db = MagicMock()
        bulk_save_test_cases(
            db=db,
            test_cases=[_make_tc_dict(id="TC-1")],
            user_story_id="US-1",
            format_type="standard",
            jira_push_results=[{"tc_id": "TC-1", "jira_key": "JIRA-99"}],
        )
        call_kwargs = mock_insert.call_args[1]
        assert call_kwargs["jira_key"] == "JIRA-99"

    @patch("app.database.crud_test_cases._insert_test_case")
    @patch("app.database.crud_test_cases._load_existing_rows")
    @patch("app.database.crud_test_cases.build_test_case_signature")
    @patch("app.database.crud_test_cases.build_row_signature")
    def test_none_jira_push_results_handled(
        self, mock_row_sig, mock_tc_sig, mock_load, mock_insert
    ):
        mock_load.return_value = []
        mock_tc_sig.return_value = "sig4"
        mock_row_sig.return_value = "row4"
        db = MagicMock()
        result = bulk_save_test_cases(
            db=db,
            test_cases=[_make_tc_dict()],
            user_story_id="US-1",
            format_type="standard",
            jira_push_results=None,
        )
        assert "TC-1" in result.inserted


class TestUpdateJiraKey:
    def test_updates_jira_key(self):
        db = MagicMock()

        result = MagicMock()
        result.rowcount = 1
        db.execute.return_value = result

        update_jira_key(
            db=db,
            user_story_id="US-1",
            tc_title="Login Test",
            jira_key="ADTD-123",
        )

        db.execute.assert_called_once()

    def test_logs_zero_rows_updated(self):
        db = MagicMock()

        result = MagicMock()
        result.rowcount = 0
        db.execute.return_value = result

        update_jira_key(
            db=db,
            user_story_id="US-1",
            tc_title="Missing Test",
            jira_key="ADTD-999",
        )

        db.execute.assert_called_once()

    def test_raises_when_update_jira_key_fails(self):
        db = MagicMock()
        db.execute.side_effect = Exception("update failed")

        with pytest.raises(Exception, match="update failed"):
            update_jira_key(
                db=db,
                user_story_id="US-1",
                tc_title="Login Test",
                jira_key="ADTD-123",
            )


# ──────────────────────────────────────────────────────────────────
# count_test_cases_by_project
# ──────────────────────────────────────────────────────────────────


class TestCountTestCasesByProject:
    def test_returns_breakdown_and_pass_rate(self):
        import uuid

        db = MagicMock()
        result = MagicMock()
        result.fetchall.return_value = [
            ("approved", 3),
            ("pending", 1),
            ("archived", 0),
        ]
        db.execute.return_value = result
        project_id = uuid.uuid4()

        counts = count_test_cases_by_project(db, project_id)

        assert counts["total"] == 4
        assert counts["approved"] == 3
        assert counts["pending"] == 1
        assert counts["archived"] == 0
        assert counts["pass_rate"] == 75.0
        db.execute.assert_called_once()

    def test_zero_total_gives_zero_pass_rate(self):
        import uuid

        db = MagicMock()
        result = MagicMock()
        result.fetchall.return_value = []
        db.execute.return_value = result

        counts = count_test_cases_by_project(db, uuid.uuid4())

        assert counts["total"] == 0
        assert counts["pass_rate"] == 0.0

    def test_raises_and_logs_on_failure(self):
        import uuid

        db = MagicMock()
        db.execute.side_effect = Exception("query failed")

        with pytest.raises(Exception, match="query failed"):
            count_test_cases_by_project(db, uuid.uuid4())
