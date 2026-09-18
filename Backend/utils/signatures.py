"""Pure helpers for normalising text and building comparison signatures.

Lives in the utils layer so components, services, and database code can all
depend on it without importing upward into the services layer.
"""


def normalize_text(value):
    """Normalize text content for comparison."""

    if isinstance(value, list):
        value = " ".join(value)

    return " ".join((value or "").strip().lower().split())


def build_test_case_signature(test_case):
    """Generate normalized comparison content from a test case."""

    if test_case.get("scenario"):

        scenario = test_case["scenario"]

        return (
            f"{normalize_text(scenario.get('given'))}|"
            f"{normalize_text(scenario.get('when'))}|"
            f"{normalize_text(scenario.get('then'))}"
        )

    if test_case.get("charter_mission"):

        return (
            f"{normalize_text(test_case.get('charter_mission'))}|"
            f"{normalize_text(test_case.get('charter_scope'))}|"
            f"{normalize_text(test_case.get('techniques'))}"
        )

    return (
        f"{normalize_text(test_case.get('steps'))}|" f"{normalize_text(test_case.get('expected'))}"
    )


def build_row_signature(row):
    """Generate normalized comparison content from a database row."""

    if row.get("given_steps") or row.get("when_steps") or row.get("then_steps"):

        return (
            f"{normalize_text(row.get('given_steps'))}|"
            f"{normalize_text(row.get('when_steps'))}|"
            f"{normalize_text(row.get('then_steps'))}"
        )

    if row.get("charter_mission"):

        return (
            f"{normalize_text(row.get('charter_mission'))}|"
            f"{normalize_text(row.get('charter_scope'))}|"
            f"{normalize_text(row.get('techniques'))}"
        )

    return f"{normalize_text(row.get('steps'))}|" f"{normalize_text(row.get('expected'))}"
