"""Duplicate checker component."""

from app.constants import (
    ACTION_NEW,
    ACTION_SKIP,
)
from app.utils.signatures import (
    build_row_signature,
    build_test_case_signature,
)


def validate_and_register_test_case(
    test_case,
    existing_rows,
    seen_contents,
):
    """Process and validate a test case."""

    test_case_signature = build_test_case_signature(test_case)

    if test_case_signature in seen_contents:
        return ACTION_SKIP

    existing_ids = set()
    duplicate_test_case_id_found = False

    for row in existing_rows:
        if build_row_signature(row) == test_case_signature:
            return ACTION_SKIP

        existing_test_case_id = row.get("tc_id")
        if existing_test_case_id:
            existing_ids.add(existing_test_case_id)
            if existing_test_case_id == test_case["id"]:
                duplicate_test_case_id_found = True

    if duplicate_test_case_id_found:
        counter = 1
        while True:
            new_id = f"{test_case['id']}_{counter}"
            if new_id not in existing_ids:
                test_case["id"] = new_id
                test_case["title"] = f"{test_case['title']}_{counter}"
                break
            counter += 1

    seen_contents.add(test_case_signature)

    existing_rows.append(
        {
            "tc_id": test_case["id"],
            "title": test_case["title"],
            "steps": test_case.get("steps"),
            "expected": test_case.get("expected"),
            "given_steps": (test_case.get("scenario") or {}).get("given"),
            "when_steps": (test_case.get("scenario") or {}).get("when"),
            "then_steps": (test_case.get("scenario") or {}).get("then"),
            "charter_mission": (test_case.get("charter_mission")),
        }
    )

    return ACTION_NEW
