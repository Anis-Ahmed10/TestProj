from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants import APPROVED_STATUS
from app.core.logging import logger
from app.models.epics_model import Epic
from app.models.project_models import Project
from app.models.story_edit_log_model import StoryEditLog
from app.models.test_cases_model import TestCase
from app.models.user_stories_model import UserStory
from app.schemas.test_cases import StatusFilter, TestCaseStatus
from app.utils.signatures import (
    build_row_signature,
    build_test_case_signature,
)

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "testcases"


@lru_cache(maxsize=1)
def _read_sql_file(filename: str) -> str:
    sql_path = SQL_DIR / filename
    try:
        return sql_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to read SQL file %s: %s", sql_path, exc)
        raise


@dataclass
class TestCaseSaveResult:
    """Summary of a bulk-save operation."""

    inserted: list[str] = field(default_factory=list)  # tc_ids pushed
    skipped: list[str] = field(default_factory=list)  # exact duplicates
    renamed: list[dict] = field(default_factory=list)  # {original, renamed}
    failed: list[str] = field(default_factory=list)


def bulk_save_test_cases(
    db: Session,
    test_cases: list[dict],
    user_story_id: str,
    format_type: str,
    jira_push_results: list[dict],  # [{tc_id, jira_key, status}]
    created_by: str = "system",
) -> TestCaseSaveResult:
    summary = TestCaseSaveResult()

    # Build a lookup from tc_id → jira_key so we can store the Jira story id
    jira_key_map: dict[str, str] = {
        r["tc_id"]: r.get("jira_key", "") for r in (jira_push_results or [])
    }

    # Pre-load existing rows for this user_story so duplicate check is fast
    existing_rows = _load_existing_rows(db, user_story_id)

    # In-flight dedup (catches duplicates within the current batch itself)
    seen_signatures: set[str] = {build_row_signature(r) for r in existing_rows}
    existing_ids: set[str] = {r["tc_id"] for r in existing_rows}

    try:
        for tc in test_cases:
            tc_id_original = tc.get("id", "")
            tc_signature = build_test_case_signature(tc)

            if tc_signature in seen_signatures:
                summary.skipped.append(tc_id_original)
                continue

            final_tc_id = tc_id_original

            if tc_id_original in existing_ids:
                final_tc_id = _next_available_id(
                    tc_id_original,
                    existing_ids,
                )
                summary.renamed.append(
                    {
                        "original": tc_id_original,
                        "renamed": final_tc_id,
                    }
                )

            _insert_test_case(
                db=db,
                tc=tc,
                tc_id=final_tc_id,
                user_story_id=user_story_id,
                format_type=format_type,
                jira_key=jira_key_map.get(tc_id_original, ""),
                created_by=created_by,
            )

            summary.inserted.append(final_tc_id)
            seen_signatures.add(tc_signature)
            existing_ids.add(final_tc_id)

        db.commit()

    except Exception as exc:
        logger.error("bulk_save_test_cases failed: %s", exc)
        db.rollback()
        raise

    return summary


def _load_existing_rows(db: Session, user_story_id: str) -> list[dict]:
    """
    Return existing test_cases rows for this user_story as plain dicts
    so the duplicate checker can work without ORM models.
    """
    try:
        rows = db.execute(
            text(_read_sql_file("fetch_testcases_byusid.sql")),
            {"usid": user_story_id},
        ).fetchall()

        result = []
        for row in rows:
            payload = row.test_data or {}
            if not isinstance(payload, dict):
                payload = {}
            scenario = payload.get("scenario") or {}
            result.append(
                {
                    "tc_id": payload.get("tc_id", ""),
                    "title": row.title,
                    "steps": payload.get("steps"),
                    "expected": payload.get("expected"),
                    "given_steps": scenario.get("given"),
                    "when_steps": scenario.get("when"),
                    "then_steps": scenario.get("then"),
                }
            )
        return result

    except Exception as exc:
        logger.error(
            "Failed to load test cases for user_story_id=%s: %s",
            user_story_id,
            exc,
        )
        raise


def _next_available_id(base_id: str, existing_ids: set[str]) -> str:
    """Return base_id_1, base_id_2 … until we find one not in existing_ids."""
    counter = 1
    while True:
        candidate = f"{base_id}_{counter}"
        if candidate not in existing_ids:
            return candidate
        counter += 1


def fetch_test_library_by_project(
    db: Session,
    project_id: uuid.UUID,
    status_filter: StatusFilter | None = APPROVED_STATUS,
) -> dict[str, Any]:
    """Return raw ORM collections of test cases for a single project.

    ``status_filter`` controls which test cases are returned:
      - ``"approved"`` (default) – only approved rows (original behaviour).
      - ``"pending"``            – only pending rows.
      - ``None`` or ``"all"``   – both approved and pending (excludes archived).
    """
    try:
        # 1. Fetch test cases using a join query based on project_id
        query = (
            db.query(TestCase)
            .join(UserStory, TestCase.user_story_id == UserStory.story_key)
            .join(Epic, UserStory.epic_id == Epic.epic_key)
            .filter(Epic.project_id == project_id)
        )

        if status_filter and status_filter != "all":
            query = query.filter(TestCase.status == status_filter)
        else:
            # "all" — show approved + pending, exclude archived
            query = query.filter(
                TestCase.status.in_([TestCaseStatus.approved.value, TestCaseStatus.pending.value])
            )

        test_cases = query.order_by(TestCase.created_at.desc()).all()

        if not test_cases:
            return {}

        # 2. Extract story keys from test cases
        story_keys = {
            str(getattr(tc, "user_story_id", ""))
            for tc in test_cases
            if getattr(tc, "user_story_id", None)
        }

        if not story_keys:
            return {}

        # 3. Fetch user stories for those story keys
        user_stories = db.query(UserStory).filter(UserStory.story_key.in_(list(story_keys))).all()

        # 4. Fetch epics for those user stories
        epic_keys = {
            getattr(story, "epic_id", "")
            for story in user_stories
            if getattr(story, "epic_id", None)
        }
        epics = db.query(Epic).filter(Epic.epic_key.in_(list(epic_keys))).all()

        # 5. Fetch story edit logs (only story_id, changes, and edited_at)
        story_edit_logs = (
            db.query(StoryEditLog.story_id, StoryEditLog.changes, StoryEditLog.edited_at)
            .filter(StoryEditLog.story_id.in_(list(story_keys)))
            .all()
        )

        # 6. Fetch project row
        project = db.query(Project).filter(Project.id == project_id).first()

        return {
            "projects": [project] if project else [],
            "epics": epics,
            "user_stories": user_stories,
            "story_edit_logs": story_edit_logs,
            "test_cases": test_cases,
        }
    except Exception as exc:
        logger.error(
            "fetch_raw_test_library_rows_by_project failed: project_id=%s %s",
            project_id,
            exc,
        )
        raise


def _insert_test_case(
    db: Session,
    tc: dict,
    tc_id: str,
    user_story_id: str,
    format_type: str,
    jira_key: str,
    created_by: str,
) -> None:
    try:
        test_data = {
            "tc_id": tc_id,
            "type": tc.get("type"),
            "steps": tc.get("steps"),
            "expected": tc.get("expected"),
            "scenario": tc.get("scenario"),
            "preconditions": tc.get("preconditions"),
        }

        query = text(_read_sql_file("test_cases.sql"))

        db.execute(
            query,
            {
                "id": str(uuid.uuid4())[:50],
                "user_story_id": user_story_id,
                "title": tc.get("title", ""),
                "priority": tc.get("priority", "Medium"),
                "test_case_type": format_type,
                "tags": tc.get("tags") or [],
                "jira_key": jira_key,
                "test_data": json.dumps(test_data),
                "created_by": None,
            },
        )

    except Exception as exc:
        logger.error(
            "Failed to insert test case tc_id=%s for user_story_id=%s: %s",
            tc_id,
            user_story_id,
            exc,
        )
        raise


def update_jira_key(db, user_story_id, tc_title, jira_key):
    try:
        result = db.execute(
            text(_read_sql_file("update_jirakey.sql")),
            {
                "user_story_id": user_story_id,
                "tc_title": tc_title,
                "jira_key": jira_key,
            },
        )

        logger.info(
            "update_jira_key: story=%s title=%r key=%s rows_matched=%s",
            user_story_id,
            tc_title,
            jira_key,
            result.rowcount,
        )

    except Exception as exc:
        logger.error(
            "Failed to update jira key for story=%s title=%r: %s",
            user_story_id,
            tc_title,
            exc,
        )
        raise


def count_test_cases_by_project(db: Session, project_id: uuid.UUID) -> dict:
    """Return a test-case status breakdown for a project.

    Walks test_cases -> user_stories -> epics -> project_id since test_cases
    only stores the (string) user_story_id, not a project FK directly.
    """
    try:
        rows = db.execute(
            text(_read_sql_file("count_by_project.sql")),
            {"project_id": str(project_id)},
        ).fetchall()

        counts = {"approved": 0, "pending": 0, "archived": 0}
        for row in rows:
            status, status_count = row[0], row[1]
            counts[status] = status_count

        total = sum(counts.values())
        pass_rate = round((counts["approved"] / total) * 100, 1) if total else 0.0

        return {
            "total": total,
            "approved": counts["approved"],
            "pending": counts["pending"],
            "archived": counts["archived"],
            "pass_rate": pass_rate,
        }
    except Exception as exc:
        logger.error(
            "Failed to count test cases for project_id=%s: %s",
            project_id,
            exc,
        )
        raise


def get_project_ids_for_test_case_ids(db: Session, test_case_ids: list[str]) -> set[uuid.UUID]:
    """Resolve the distinct set of project ids that own the given test cases."""
    if not test_case_ids:
        return set()

    try:
        rows = (
            db.query(Epic.project_id)
            .join(UserStory, UserStory.epic_id == Epic.epic_key)
            .join(TestCase, TestCase.user_story_id == UserStory.story_key)
            .filter(TestCase.id.in_(test_case_ids))
            .distinct()
            .all()
        )
        return {row[0] for row in rows if row[0] is not None}
    except Exception as exc:
        logger.error(
            "Failed to resolve project ids for test_case_ids=%s: %s",
            test_case_ids,
            exc,
        )
        raise


def get_project_id_for_user_story(db: Session, user_story_id: str) -> uuid.UUID | None:
    """Resolve the project a user story belongs to, or None if it doesn't exist."""
    row = (
        db.query(Epic.project_id)
        .join(UserStory, UserStory.epic_id == Epic.epic_key)
        .filter(UserStory.story_key == user_story_id)
        .first()
    )
    return row[0] if row else None
