from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.database.crud_test_cases import fetch_test_library_by_project
from app.models.epics_model import Epic
from app.models.test_cases_model import TestCase
from app.models.user_stories_model import UserStory
from app.schemas.test_cases import StatusFilter, TestCaseStatus
from app.services.internal import (
    _attach_epics,
    _attach_stories,
    _attach_test_cases_and_logs,
    _build_project_index,
    _index_edit_logs,
)

ALLOWED_TRANSITIONS: dict[TestCaseStatus, set[TestCaseStatus]] = {
    TestCaseStatus.pending: {TestCaseStatus.approved, TestCaseStatus.archived},
    TestCaseStatus.approved: {TestCaseStatus.archived},
    TestCaseStatus.archived: {TestCaseStatus.pending},  # Restore
}


def validate_transition(current: TestCaseStatus, target: TestCaseStatus) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Invalid status transition: {current} -> {target}")


def _normalize_uuid(value: str | UUID) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


@dataclass
class BulkRowResult:
    id: str
    status: TestCaseStatus | None
    success: bool
    error: str | None = None


def _iter_test_cases_for_ids(
    db: Session,
    *,
    test_case_ids: list[UUID],
    project_id: UUID | None = None,
) -> Iterable[TestCase]:
    if not test_case_ids:
        return []

    stmt = select(TestCase)
    if project_id is not None:
        stmt = (
            stmt.join(UserStory, TestCase.user_story_id == UserStory.story_key)
            .join(Epic, UserStory.epic_id == Epic.epic_key)
            .where(Epic.project_id == project_id)
        )
    stmt = stmt.where(TestCase.id.in_(test_case_ids))
    return db.execute(stmt).scalars().all()


def _build_not_found_result(requested_uuid: UUID) -> BulkRowResult:
    """Create a BulkRowResult for an ID that was not found in the database."""
    return BulkRowResult(
        id=str(requested_uuid),
        status=None,
        success=False,
        error="not found",
    )


def _update_single_test_case(
    db: Session,
    tc: TestCase,
    new_status: TestCaseStatus,
) -> tuple[BulkRowResult, bool]:
    original_status = tc.status
    try:
        current_status = TestCaseStatus(original_status)
        validate_transition(current_status, new_status)
        tc.status = new_status.value
        db.add(tc)

        return (
            BulkRowResult(
                id=str(tc.id),
                status=TestCaseStatus(tc.status),
                success=True,
                error=None,
            ),
            True,
        )

    except Exception as exc:
        logger.warning(
            "bulk_update_row_failed",
            extra={"tc_id": str(tc.id), "error": str(exc)},
        )
        try:
            current_status_on_error: TestCaseStatus | None = TestCaseStatus(original_status)
        except Exception:
            current_status_on_error = None

        return (
            BulkRowResult(
                id=str(tc.id),
                status=current_status_on_error,
                success=False,
                error=str(exc),
            ),
            False,
        )


def bulk_update_status_by_ids(
    db: Session,
    *,
    test_case_ids: list[str],
    new_status: TestCaseStatus,
    project_id: UUID | None = None,
) -> dict:
    if not test_case_ids:
        return {"found_count": 0, "updated_count": 0, "results": []}

    try:
        requested_test_case_ids = list(dict.fromkeys(_normalize_uuid(x) for x in test_case_ids))
    except Exception as exc:
        raise ValueError(f"Invalid id format: {exc}") from exc

    try:
        iter_kwargs: dict[str, Any] = {"test_case_ids": requested_test_case_ids}
        if project_id is not None:
            iter_kwargs["project_id"] = project_id
        found_test_cases: list[TestCase] = list(_iter_test_cases_for_ids(db, **iter_kwargs))
    except SQLAlchemyError:
        logger.exception("bulk_update_status_by_ids fetch failed")
        raise

    found_tc_by_id: dict[UUID, TestCase] = {tc.id: tc for tc in found_test_cases}

    updated_results: list[BulkRowResult] = []
    not_found_results: list[BulkRowResult] = []
    updated_count = 0
    for requested_uuid in requested_test_case_ids:
        tc = found_tc_by_id.get(requested_uuid)
        if tc is None:
            not_found_results.append(_build_not_found_result(requested_uuid))
            continue

        row_result, was_updated = _update_single_test_case(db, tc, new_status)
        updated_results.append(row_result)
        if was_updated:
            updated_count += 1

    if updated_count > 0:
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("bulk_update_status_by_ids commit failed")
            raise

    return {
        "found_count": len(found_test_cases),
        "updated_count": updated_count,
        "results": [r.__dict__ for r in updated_results + not_found_results],
    }


def fetch_test_library_payload_by_project(
    db: Session,
    project_id: UUID,
    status_filter: StatusFilter | None = "approved",
) -> list[dict[str, Any]]:
    """Fetch and assemble the nested test-library payload for a single project."""
    rows = fetch_test_library_by_project(db, project_id, status_filter=status_filter)
    if not rows:
        return []

    project_payloads, project_lookup = _build_project_index(rows["projects"])
    epic_lookup = _attach_epics(rows["epics"], project_lookup)
    story_lookup = _attach_stories(rows["user_stories"], epic_lookup)
    logs_by_story = _index_edit_logs(rows["story_edit_logs"])
    _attach_test_cases_and_logs(
        rows["test_cases"],
        story_lookup,
        logs_by_story,
    )

    return project_payloads
