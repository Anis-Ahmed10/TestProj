from app.components.duplicate_checker.TestCaseDuplicateChecker import (
    validate_and_register_test_case,
)
from app.constants import ACTION_NEW, ACTION_SKIP


def test_validate_duplicate_signature_skip():
    tc = {
        "id": "TC1",
        "title": "Title",
        "steps": "Step",
        "expected": "Expected",
    }

    existing_rows = []
    seen = set()

    validate_and_register_test_case(
        tc,
        existing_rows,
        seen,
    )

    result = validate_and_register_test_case(
        tc,
        existing_rows,
        seen,
    )

    assert result == ACTION_SKIP


def test_validate_duplicate_id_rename():
    tc = {
        "id": "TC1",
        "title": "Title",
        "steps": "Step",
        "expected": "Expected",
    }

    existing_rows = [
        {
            "tc_id": "TC1",
            "title": "Other",
            "steps": "Different",
            "expected": "Different",
        }
    ]

    seen = set()

    result = validate_and_register_test_case(
        tc,
        existing_rows,
        seen,
    )

    assert result == ACTION_NEW
    assert tc["id"] == "TC1_1"
    assert tc["title"] == "Title_1"


def test_validate_new_test_case():
    tc = {
        "id": "TC1",
        "title": "Title",
        "steps": "Step",
        "expected": "Expected",
    }

    result = validate_and_register_test_case(
        tc,
        [],
        set(),
    )

    assert result == ACTION_NEW
