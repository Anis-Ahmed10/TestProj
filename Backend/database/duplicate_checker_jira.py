"""Duplicate checker for Jira import stories.

Rules:
  1. story_key AND title AND content (description/AC/priority) all same → SKIP
  2. story_key same but content different      → UPDATE in-place
  3. title same but story_key different        → RENAME incoming: append _1, _2 etc.
  4. brand new story_key and title             → INSERT
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DuplicateAction(str, Enum):
    INSERT = "insert"
    UPDATE = "update"
    SKIP = "skip"
    RENAME = "rename"


@dataclass
class DuplicateCheckResult:
    action: DuplicateAction
    rename_key: Optional[str] = None
    rename_title: Optional[str] = None
    existing_id: Optional[str] = None


def check_story_duplicate(
    story_key: str,
    title: str,
    description: str,
    acceptance_criteria: str,
    existing_by_key: dict,
    existing_by_title: dict,
    key_exists_elsewhere: Optional[callable] = None,
    priority: Optional[str] = None,
) -> DuplicateCheckResult:

    norm_title = _normalise(title)
    incoming_story_content = _content_hash(description, acceptance_criteria)

    if story_key in existing_by_key:
        existing_row = existing_by_key[story_key]
        existing_story_content = _content_hash(
            existing_row.get("description", ""),
            existing_row.get("acceptance_criteria", ""),
        )
        title_changed = norm_title != _normalise(existing_row.get("title", ""))
        priority_changed = "priority" in existing_row and priority != existing_row.get("priority")
        if (
            incoming_story_content == existing_story_content
            and not title_changed
            and not priority_changed
        ):
            return DuplicateCheckResult(
                action=DuplicateAction.SKIP,
                existing_id=existing_row["id"],
            )
        else:
            return DuplicateCheckResult(
                action=DuplicateAction.UPDATE,
                existing_id=existing_row["id"],
            )

    # --- Case 3: same title but different key ---
    if norm_title in existing_by_title:
        checker = key_exists_elsewhere or (lambda k: False)
        suffix = 1
        new_key = f"{story_key}_{suffix}"
        new_title = f"{title}_{suffix}"
        while new_key in existing_by_key or checker(new_key):
            suffix += 1
            new_key = f"{story_key}_{suffix}"
            new_title = f"{title}_{suffix}"

        return DuplicateCheckResult(
            action=DuplicateAction.RENAME,
            rename_key=new_key,
            rename_title=new_title,
        )

    # --- Case 4: completely new ---
    return DuplicateCheckResult(action=DuplicateAction.INSERT)


def _normalise(text: str) -> str:
    return text.strip().lower() if text else ""


def _content_hash(description: str, acceptance_criteria: str) -> str:
    return f"{_normalise(description)}||{_normalise(acceptance_criteria)}"
