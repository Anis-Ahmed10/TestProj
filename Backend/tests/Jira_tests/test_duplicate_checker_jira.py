"""Unit tests for app/components/duplicate_checker/TestCaseDuplicateChecker.py — 100% coverage."""

from __future__ import annotations

from unittest.mock import patch

from app.components.duplicate_checker.TestCaseDuplicateChecker import (
    validate_and_register_test_case,
)
from app.constants import ACTION_NEW, ACTION_SKIP

# ──────────────────────────────────────────────────────────────────
# validate_and_register_test_case
# ──────────────────────────────────────────────────────────────────


def _make_tc(tc_id="TC-1", title="Title", steps="s", expected="e"):
    return {
        "id": tc_id,
        "title": title,
        "steps": steps,
        "expected": expected,
        "scenario": None,
        "charter_mission": None,
    }


class TestValidateAndRegisterTestCase:
    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_test_case_signature")
    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_row_signature")
    def test_new_test_case_returns_action_new(self, mock_row_sig, mock_tc_sig):
        mock_tc_sig.return_value = "unique-sig"
        mock_row_sig.return_value = "other-sig"

        action = validate_and_register_test_case(_make_tc(), existing_rows=[], seen_contents=set())
        assert action == ACTION_NEW

    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_test_case_signature")
    def test_duplicate_signature_in_seen_returns_skip(self, mock_tc_sig):
        mock_tc_sig.return_value = "dup-sig"

        action = validate_and_register_test_case(
            _make_tc(), existing_rows=[], seen_contents={"dup-sig"}
        )
        assert action == ACTION_SKIP

    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_test_case_signature")
    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_row_signature")
    def test_same_row_signature_returns_skip(self, mock_row_sig, mock_tc_sig):
        mock_tc_sig.return_value = "new-sig"
        mock_row_sig.return_value = "new-sig"  # row has same sig as new TC

        existing_rows = [
            {
                "tc_id": "TC-OTHER",
                "title": "T",
                "steps": None,
                "expected": None,
                "given_steps": None,
                "when_steps": None,
                "then_steps": None,
                "charter_mission": None,
            }
        ]
        action = validate_and_register_test_case(
            _make_tc(), existing_rows=existing_rows, seen_contents=set()
        )
        assert action == ACTION_SKIP

    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_test_case_signature")
    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_row_signature")
    def test_duplicate_id_gets_renamed(self, mock_row_sig, mock_tc_sig):
        mock_tc_sig.return_value = "new-content-sig"
        mock_row_sig.return_value = "old-row-sig"

        existing_rows = [
            {
                "tc_id": "TC-1",  # Same ID
                "title": "T",
                "steps": None,
                "expected": None,
                "given_steps": None,
                "when_steps": None,
                "then_steps": None,
                "charter_mission": None,
            }
        ]
        tc = _make_tc(tc_id="TC-1")
        action = validate_and_register_test_case(
            tc, existing_rows=existing_rows, seen_contents=set()
        )
        assert action == ACTION_NEW
        assert tc["id"] == "TC-1_1"
        assert tc["title"] == "Title_1"

    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_test_case_signature")
    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_row_signature")
    def test_renamed_id_increments_until_free(self, mock_row_sig, mock_tc_sig):
        mock_tc_sig.return_value = "new-sig"
        mock_row_sig.return_value = "old-row"

        existing_rows = [
            {
                "tc_id": "TC-1",
                "title": "T",
                "steps": None,
                "expected": None,
                "given_steps": None,
                "when_steps": None,
                "then_steps": None,
                "charter_mission": None,
            },
            {
                "tc_id": "TC-1_1",
                "title": "T2",
                "steps": None,
                "expected": None,
                "given_steps": None,
                "when_steps": None,
                "then_steps": None,
                "charter_mission": None,
            },
        ]
        tc = _make_tc(tc_id="TC-1")
        # Override build_row_signature to never match
        with patch(
            "app.components.duplicate_checker.TestCaseDuplicateChecker.build_row_signature",
            return_value="never-matches",
        ):
            action = validate_and_register_test_case(
                tc, existing_rows=existing_rows, seen_contents=set()
            )
        assert action == ACTION_NEW

    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_test_case_signature")
    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_row_signature")
    def test_registered_tc_added_to_seen_contents(self, mock_row_sig, mock_tc_sig):
        mock_tc_sig.return_value = "fresh-sig"
        mock_row_sig.return_value = "row-sig"

        seen = set()
        validate_and_register_test_case(_make_tc(), existing_rows=[], seen_contents=seen)
        assert "fresh-sig" in seen

    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_test_case_signature")
    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_row_signature")
    def test_registered_tc_added_to_existing_rows(self, mock_row_sig, mock_tc_sig):
        mock_tc_sig.return_value = "s1"
        mock_row_sig.return_value = "s2"

        rows = []
        validate_and_register_test_case(_make_tc(), existing_rows=rows, seen_contents=set())
        assert len(rows) == 1
        assert rows[0]["tc_id"] == "TC-1"

    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_test_case_signature")
    @patch("app.components.duplicate_checker.TestCaseDuplicateChecker.build_row_signature")
    def test_existing_row_without_tc_id_doesnt_crash(self, mock_row_sig, mock_tc_sig):
        mock_tc_sig.return_value = "s1"
        mock_row_sig.return_value = "s2"

        rows = [
            {
                "tc_id": None,
                "title": "T",
                "steps": None,
                "expected": None,
                "given_steps": None,
                "when_steps": None,
                "then_steps": None,
                "charter_mission": None,
            }
        ]
        action = validate_and_register_test_case(
            _make_tc(), existing_rows=rows, seen_contents=set()
        )
        assert action == ACTION_NEW
