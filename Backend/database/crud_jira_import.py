"""CRUD operations for Jira import — epics + user_stories tables."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.logging import logger
from app.database.duplicate_checker_jira import DuplicateAction, check_story_duplicate
from app.models.epics_model import Epic
from app.models.project_models import Project
from app.models.story_approval_model import StoryApprovalRequest
from app.models.user_stories_model import UserStory

_UNGROUPED_PREFIX = "UG"

_PRIORITY_HIGH_VALUES = {"high", "highest", "critical", "blocker", "urgent", "h"}
_PRIORITY_MEDIUM_VALUES = {"medium", "normal", "moderate", "m"}
_PRIORITY_LOW_VALUES = {"low", "lowest", "minor", "trivial", "l"}


def normalize_story_priority(value: object) -> str | None:

    if value is None:
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    if text in _PRIORITY_HIGH_VALUES:
        return "High"
    if text in _PRIORITY_MEDIUM_VALUES:
        return "Medium"
    if text in _PRIORITY_LOW_VALUES:
        return "Low"

    return None


@dataclass
class ImportSummary:
    inserted: list[str] = field(default_factory=list)  # story_keys
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    renamed: list[dict] = field(default_factory=list)  # {original, renamed}
    failed: list[str] = field(default_factory=list)
    failed_reasons: list[dict] = field(default_factory=list)


def make_ungrouped_epic_key(project_id: uuid.UUID) -> str:
    compact = uuid.UUID(str(project_id)).hex[:16]
    return f"{_UNGROUPED_PREFIX}-{compact}"


def get_existing_story_statuses(
    db: Session,
    story_keys: list[str],
    project_id: uuid.UUID,
) -> dict[str, dict]:
    """Return duplicate metadata for already stored stories keyed by Jira story key,
    scoped to the specified project via epic relationship."""
    if not db or not story_keys:
        return {}

    normalized_keys = [story_key for story_key in story_keys if story_key]
    if not normalized_keys:
        return {}

    rows = (
        db.query(UserStory.story_key, UserStory.status)
        .join(Epic, UserStory.epic_id == Epic.epic_key)
        .filter(
            UserStory.story_key.in_(normalized_keys),
            Epic.project_id == project_id,
        )
        .all()
    )

    # A story with an open (pending) approval request is 'awaiting review'. Surface
    # that as a distinct status so re-import can badge it and block re-submitting it,
    # instead of the duplicate only being rejected at submit time. This takes
    # precedence over user_stories.status (which is NULL until a decision is made,
    # and stays 'rejected' even after the story is resubmitted for a fresh review).
    pending_approval_keys = {
        key
        for (key,) in db.query(StoryApprovalRequest.user_story_id)
        .filter(
            StoryApprovalRequest.user_story_id.in_(normalized_keys),
            StoryApprovalRequest.project_id == project_id,
            StoryApprovalRequest.status == "pending",
        )
        .distinct()
        .all()
    }

    result = {
        story_key: {
            "already_exists": True,
            "status": (status or "pending").strip().lower() or "pending",
        }
        for story_key, status in rows
        if story_key
    }

    # Overlay stories awaiting a reviewer decision. Done as an overlay (not just a
    # per-row branch) so it also surfaces — and blocks re-submitting — a story that
    # has a pending approval request but NO user_stories row: e.g. legacy submissions
    # made before stories were persisted at submit time. pending_approval wins over
    # any stored status.
    for key in pending_approval_keys:
        result[key] = {"already_exists": True, "status": "pending_approval"}

    return result


def save_epics_and_stories(
    db: Session,
    epics_payload: list[dict],
    project_id: uuid.UUID,
    commit: bool = True,
) -> ImportSummary:
    """Upsert epics + stories. Pass commit=False to defer the commit so this can
    share a transaction with a caller (e.g. atomic persist-then-submit-for-approval)."""
    summary = ImportSummary()

    project_exists = db.query(Project.id).filter(Project.id == project_id).first()
    if not project_exists:
        raise AppException(
            code="PROJECT_NOT_FOUND",
            message=(
                f"Project {project_id} not found. " "Select a valid project before saving stories."
            ),
            status_code=404,
        )

    existing_userstories_by_key: dict = {
        row.story_key: {
            "id": str(row.id),
            "title": row.title,
            "description": row.description or "",
            "acceptance_criteria": row.acceptance_criteria or "",
            "priority": row.priority,
        }
        for row in (
            db.query(UserStory)
            .join(Epic, UserStory.epic_id == Epic.epic_key)
            .filter(Epic.project_id == project_id)
            .all()
        )
        if row.story_key
    }
    existing_userstories_by_title: dict = {}
    for key, row in existing_userstories_by_key.items():
        norm = row["title"].strip().lower()
        existing_userstories_by_title.setdefault(norm, []).append(row)

    submitted_keys = [
        story.get("storyId", "")
        for epic_data in epics_payload
        for story in epic_data.get("user_stories", [])
        if story.get("storyId")
    ]
    global_story_keys: set[str] = (
        {
            key
            for (key,) in db.query(UserStory.story_key)
            .filter(UserStory.story_key.in_(submitted_keys))
            .all()
        }
        if submitted_keys
        else set()
    )

    for epic_data in epics_payload:
        epic_key = epic_data.get("epicId")
        epic_title = epic_data.get("epicTitle", "Unknown Epic")

        if epic_key == "UNGROUPED":
            epic_key = make_ungrouped_epic_key(project_id)
            epic_title = "Imported Stories"

        epic_db = _get_or_create_epic(
            db,
            epic_key,
            epic_title,
            project_id,
        )

        for story_data in epic_data.get("user_stories", []):
            story_key = story_data.get("storyId", "")
            story_title = story_data.get("storyTitle", "No Story Title")
            description = story_data.get("description", "")
            acceptance_criteria = story_data.get("acceptanceCriteria", "")
            priority = normalize_story_priority(story_data.get("priority"))

            result = check_story_duplicate(
                story_key=story_key,
                title=story_title,
                description=description,
                acceptance_criteria=acceptance_criteria,
                existing_by_key=existing_userstories_by_key,
                existing_by_title=existing_userstories_by_title,
                priority=priority,
                key_exists_elsewhere=lambda k: (
                    k in global_story_keys
                    or db.query(UserStory.story_key).filter(UserStory.story_key == k).first()
                    is not None
                ),
            )

            try:
                if result.action == DuplicateAction.SKIP:
                    summary.skipped.append(story_key)

                elif result.action == DuplicateAction.UPDATE:
                    _update_story(
                        db,
                        result.existing_id,
                        story_title,
                        description,
                        acceptance_criteria,
                        priority,
                    )
                    summary.updated.append(story_key)
                    # Update local cache
                    existing_userstories_by_key[story_key]["description"] = description
                    existing_userstories_by_key[story_key][
                        "acceptance_criteria"
                    ] = acceptance_criteria
                    existing_userstories_by_key[story_key]["priority"] = priority

                elif result.action == DuplicateAction.RENAME:
                    _insert_story(
                        db,
                        epic_db,
                        result.rename_key,
                        result.rename_title,
                        description,
                        acceptance_criteria,
                        priority,
                    )
                    summary.renamed.append(
                        {
                            "original": story_key,
                            "renamed": result.rename_key,
                        }
                    )
                    global_story_keys.add(result.rename_key)
                    existing_userstories_by_key[result.rename_key] = {
                        "id": "pending",
                        "title": result.rename_title,
                        "description": description,
                        "acceptance_criteria": acceptance_criteria,
                        "priority": priority,
                    }

                else:
                    if story_key in global_story_keys:
                        logger.error(
                            "story_key_collision_across_projects: story_key=%s "
                            "already exists in another project, skipping insert "
                            "for project_id=%s",
                            story_key,
                            project_id,
                        )
                        summary.failed.append(story_key)
                        summary.failed_reasons.append(
                            {
                                "story_key": story_key,
                                "reason": "ALREADY_IMPORTED_IN_ANOTHER_PROJECT",
                            }
                        )
                        continue

                    _insert_story(
                        db,
                        epic_db,
                        story_key,
                        story_title,
                        description,
                        acceptance_criteria,
                        priority,
                    )
                    summary.inserted.append(story_key)
                    global_story_keys.add(story_key)
                    existing_userstories_by_key[story_key] = {
                        "id": "pending",
                        "title": story_title,
                        "description": description,
                        "acceptance_criteria": acceptance_criteria,
                        "priority": priority,
                    }
                    existing_userstories_by_title.setdefault(
                        story_title.strip().lower(), []
                    ).append(existing_userstories_by_key[story_key])

            except Exception as exc:
                logger.error("Failed to save story %s: %s", story_key, exc)
                summary.failed.append(story_key)

    if commit:
        db.commit()
    return summary


def refresh_stories_from_jira(
    db: Session,
    fresh_epics: list[dict],
    project_id: uuid.UUID,
) -> dict:
    changed_keys: list[str] = []
    new_story_keys: list[str] = []

    # Scoped to this project only — matching against another project's
    # stories by story_key was relying on a global-uniqueness assumption
    # instead of an explicit project filter.
    existing_userstories_by_key: dict = {
        row.story_key: row
        for row in (
            db.query(UserStory)
            .join(Epic, UserStory.epic_id == Epic.epic_key)
            .filter(Epic.project_id == project_id)
            .all()
        )
        if row.story_key
    }

    for epic_data in fresh_epics:
        epic_key = epic_data.get("epicId")
        if epic_key == "UNGROUPED":
            epic_key = make_ungrouped_epic_key(project_id)

        for story_data in epic_data.get("user_stories", []):
            story_key = story_data.get("storyId", "")
            new_title = story_data.get("storyTitle", "")
            new_desc = story_data.get("description", "")
            new_ac = story_data.get("acceptanceCriteria", "")

            if story_key not in existing_userstories_by_key:
                # Brand new story appeared in Jira since last import
                new_story_keys.append(story_key)
                continue
            existing_story = existing_userstories_by_key[story_key]
            old_title = existing_story.title or ""
            old_desc = existing_story.description or ""
            old_ac = existing_story.acceptance_criteria or ""

            # Also detect the story having moved to a different epic since
            # the last import, not just content changes. Both old and new
            # ungrouped-epic values go through make_ungrouped_epic_key, so a
            # story staying "ungrouped" for this project is never reported
            # as a false epic change.
            old_epic = existing_story.epic_id or ""
            new_epic = epic_key or ""
            epic_changed = (epic_key is not None) and (old_epic != new_epic)

            if old_title != new_title or old_desc != new_desc or old_ac != new_ac or epic_changed:
                changed_keys.append(story_key)

    return {
        "changed_story_keys": changed_keys,
        "new_story_keys": new_story_keys,
    }


# ── Private helpers ────────────────────────────────────────────────────────────


def _get_or_create_epic(
    db: Session,
    epic_key: str,
    epic_title: str,
    project_id: uuid.UUID,
) -> Epic:

    existing_epic = db.query(Epic).filter(Epic.epic_key == epic_key).first()

    if existing_epic:
        if existing_epic.project_id != project_id:
            if epic_key.startswith(f"{_UNGROUPED_PREFIX}-"):
                # Unreachable in normal use (same project_id always derives the same key) —
                # kept as a guard so a hash collision or corrupted legacy data fails
                # instead of silently merging two projects' data.
                raise AppException(
                    code="UNGROUPED_EPIC_COLLISION",
                    message=(
                        f"Ungrouped epic key {epic_key} already belongs to "
                        f"project {existing_epic.project_id}, cannot reuse "
                        f"for project {project_id}."
                    ),
                    status_code=409,
                )
            logger.warning(
                "epic_relinked: epic_key=%s moved from project_id=%s to project_id=%s",
                epic_key,
                existing_epic.project_id,
                project_id,
            )
            existing_epic.project_id = project_id
            existing_epic.title = epic_title
            db.add(existing_epic)
        return existing_epic

    new_epic = Epic(
        id=uuid.uuid4(),
        project_id=project_id,
        epic_key=epic_key,
        title=epic_title,
    )

    db.add(new_epic)
    db.flush()

    return new_epic


def _insert_story(
    db: Session,
    epic: Optional[Epic],
    story_key: str,
    title: str,
    description: str,
    acceptance_criteria: str,
    priority: Optional[str] = None,
) -> UserStory:
    story = UserStory(
        id=uuid.uuid4(),
        epic_id=epic.epic_key if epic else None,
        story_key=story_key,
        title=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        priority=priority,
    )

    db.add(story)
    db.flush()
    return story


def _update_story(
    db: Session,
    story_id_str: str,
    title: str,
    description: str,
    acceptance_criteria: str,
    priority: Optional[str] = None,
) -> None:
    story_id = uuid.UUID(story_id_str)
    story = db.query(UserStory).filter(UserStory.id == story_id).first()
    if story:
        story.title = title
        story.description = description
        story.acceptance_criteria = acceptance_criteria
        if priority is not None:
            story.priority = priority


def apply_refresh_changes(
    db: Session,
    fresh_epics: list[dict],
    project_id: uuid.UUID,
):
    existing_userstories_by_key = {
        row.story_key: row
        for row in (
            db.query(UserStory)
            .join(Epic, UserStory.epic_id == Epic.epic_key)
            .filter(Epic.project_id == project_id)
            .all()
        )
        if row.story_key
    }

    updated = []

    for epic_data in fresh_epics:
        epic_key = epic_data.get("epicId")
        epic_title = epic_data.get("epicTitle", "Imported Stories")

        if epic_key == "UNGROUPED":
            epic_key = make_ungrouped_epic_key(project_id)
            epic_title = "Imported Stories"

        # Ensure the (possibly new) epic exists so a story that moved epics
        # in Jira can be re-pointed at it below.
        epic_db = _get_or_create_epic(db, epic_key, epic_title, project_id) if epic_key else None

        for story_data in epic_data.get("user_stories", []):

            story_key = story_data.get("storyId", "")

            if story_key not in existing_userstories_by_key:
                continue

            story = existing_userstories_by_key[story_key]

            new_title = story_data.get("storyTitle", "")
            new_desc = story_data.get("description", "")
            new_ac = story_data.get("acceptanceCriteria", "")

            old_epic = getattr(story, "epic_id", None) or ""
            new_epic = (epic_db.epic_key if epic_db else epic_key) or ""
            epic_changed = (epic_key is not None) and (old_epic != new_epic)

            if (
                story.title != new_title
                or story.description != new_desc
                or story.acceptance_criteria != new_ac
                or epic_changed
            ):

                story.title = new_title
                story.description = new_desc
                story.acceptance_criteria = new_ac
                if epic_key is not None:
                    story.epic_id = new_epic if new_epic else None

                updated.append(story_key)

    db.commit()

    return updated
