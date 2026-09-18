"""CRUD operations for story edit audit log."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.story_edit_log_model import StoryEditLog


def bulk_insert_edit_log(db: Session, records: list[dict]) -> int:
    """Insert story edit log records; returns count inserted."""
    if not records:
        return 0

    rows = [
        StoryEditLog(
            story_id=r["storyId"],
            epic_id=r["epicId"],
            changes=r["changes"],
            edited_at=r["editedAt"],
        )
        for r in records
    ]

    try:
        db.add_all(rows)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return len(rows)
