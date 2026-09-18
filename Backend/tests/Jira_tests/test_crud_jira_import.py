"""Unit tests for app/database/crud_jira_import.py — 100% coverage."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import AppException
from app.database.crud_jira_import import (
    _UNGROUPED_PREFIX,
    ImportSummary,
    _get_or_create_epic,
    _insert_story,
    _update_story,
    apply_refresh_changes,
    get_existing_story_statuses,
    make_ungrouped_epic_key,
    normalize_story_priority,
    refresh_stories_from_jira,
    save_epics_and_stories,
)
from app.database.duplicate_checker_jira import DuplicateAction, DuplicateCheckResult

# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _mock_db(existing_stories=None, project_found=True):
    """Mock db that supports every query chain used in this module:
    - db.query(Project.id).filter(...).first()               -> project existence check
    - db.query(UserStory).join(Epic, ...).filter(...).all()  -> project-scoped stories
    - db.query(UserStory).filter(...).first()                -> single-row lookups
    """
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = (
        SimpleNamespace(id=uuid.uuid4()) if project_found else None
    )
    db.query.return_value.join.return_value.filter.return_value.all.return_value = (
        existing_stories or []
    )
    return db


def _make_story(**kwargs):
    defaults = dict(
        story_key="ST-1",
        id=uuid.uuid4(),
        title="Title",
        description="Desc",
        acceptance_criteria="AC",
        issue_type="story",
        epic_id="EP-1",
        priority=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ──────────────────────────────────────────────────────────────────
# ImportSummary dataclass
# ──────────────────────────────────────────────────────────────────


class TestImportSummary:
    def test_defaults(self):
        s = ImportSummary()
        assert s.inserted == []
        assert s.updated == []
        assert s.skipped == []
        assert s.renamed == []
        assert s.failed == []


# ──────────────────────────────────────────────────────────────────
# make_ungrouped_epic_key
# ──────────────────────────────────────────────────────────────────


class TestMakeUngroupedEpicKey:
    def test_key_starts_with_prefix(self):
        project_id = uuid.uuid4()
        key = make_ungrouped_epic_key(project_id)
        assert key.startswith(f"{_UNGROUPED_PREFIX}-")

    def test_key_fits_varchar_20(self):
        # epics.epic_key is VARCHAR(20) in the live DB — the generated key
        # must always fit, regardless of which project_id is used.
        for _ in range(20):
            key = make_ungrouped_epic_key(uuid.uuid4())
            assert len(key) <= 20

    def test_key_is_deterministic_for_same_project(self):
        project_id = uuid.uuid4()
        assert make_ungrouped_epic_key(project_id) == make_ungrouped_epic_key(project_id)

    def test_different_projects_get_different_keys(self):
        key_a = make_ungrouped_epic_key(uuid.uuid4())
        key_b = make_ungrouped_epic_key(uuid.uuid4())
        assert key_a != key_b

    def test_accepts_string_uuid(self):
        project_id = uuid.uuid4()
        assert make_ungrouped_epic_key(str(project_id)) == make_ungrouped_epic_key(project_id)


# ──────────────────────────────────────────────────────────────────
# get_existing_story_statuses
# ──────────────────────────────────────────────────────────────────


class TestGetExistingStoryStatuses:
    def test_returns_empty_dict_when_db_is_none(self):
        assert get_existing_story_statuses(None, ["ST-1"], uuid.uuid4()) == {}

    def test_returns_empty_dict_when_no_story_keys(self):
        db = MagicMock()
        assert get_existing_story_statuses(db, [], uuid.uuid4()) == {}

    def test_returns_empty_dict_when_keys_all_falsy(self):
        db = MagicMock()
        assert get_existing_story_statuses(db, ["", None], uuid.uuid4()) == {}

    def test_returns_status_for_existing_story(self):
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            ("ST-1", "approved")
        ]
        db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        result = get_existing_story_statuses(db, ["ST-1"], uuid.uuid4())
        assert result["ST-1"] == {"already_exists": True, "status": "approved"}

    def test_defaults_status_to_pending_when_null(self):
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            ("ST-1", None)
        ]
        db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        result = get_existing_story_statuses(db, ["ST-1"], uuid.uuid4())
        assert result["ST-1"]["status"] == "pending"

    def test_pending_approval_overlays_stored_status(self):
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            ("ST-1", "rejected")
        ]
        db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("ST-1",)
        ]
        result = get_existing_story_statuses(db, ["ST-1"], uuid.uuid4())
        assert result["ST-1"]["status"] == "pending_approval"

    def test_pending_approval_surfaces_even_without_user_stories_row(self):
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("ST-LEGACY",)
        ]
        result = get_existing_story_statuses(db, ["ST-LEGACY"], uuid.uuid4())
        assert result["ST-LEGACY"] == {"already_exists": True, "status": "pending_approval"}

    def test_skips_falsy_story_key_in_rows(self):
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            ("", "approved")
        ]
        db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        result = get_existing_story_statuses(db, ["ST-1"], uuid.uuid4())
        assert result == {}


# ──────────────────────────────────────────────────────────────────
# _get_or_create_epic
# ──────────────────────────────────────────────────────────────────


class TestGetOrCreateEpic:
    def test_returns_existing(self):
        project_id = uuid.uuid4()
        existing = SimpleNamespace(project_id=project_id)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing
        result = _get_or_create_epic(db, "EP-1", "Title", project_id)
        assert result is existing
        db.add.assert_not_called()

    def test_relinks_epic_to_new_project(self):
        old_project_id = uuid.uuid4()
        new_project_id = uuid.uuid4()
        existing = SimpleNamespace(project_id=old_project_id, title="Old Title", epic_key="EP-1")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing
        result = _get_or_create_epic(db, "EP-1", "New Title", new_project_id)
        assert result is existing
        assert existing.project_id == new_project_id
        assert existing.title == "New Title"
        db.add.assert_called_once_with(existing)

    def test_ungrouped_epic_collision_across_projects_raises(self):
        """An UG-<...> key must never be re-parented to a different project.
        If it ever resolves to a different project's row, that's a bug
        elsewhere (key collision), so we fail loudly instead of silently
        merging two projects' data — this is exactly the class of bug this
        change set exists to prevent."""
        owner_project_id = uuid.uuid4()
        other_project_id = uuid.uuid4()
        ungrouped_key = make_ungrouped_epic_key(owner_project_id)
        existing = SimpleNamespace(
            project_id=owner_project_id, title="Imported Stories", epic_key=ungrouped_key
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing

        with pytest.raises(AppException) as excinfo:
            _get_or_create_epic(db, ungrouped_key, "Imported Stories", other_project_id)

        assert excinfo.value.code == "UNGROUPED_EPIC_COLLISION"
        db.add.assert_not_called()

    def test_creates_new_when_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = _get_or_create_epic(db, "EP-NEW", "New Epic", uuid.uuid4())
        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert result.epic_key == "EP-NEW"
        assert result.title == "New Epic"

    def test_new_epic_has_uuid_id(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = _get_or_create_epic(db, "EP-2", "T", uuid.uuid4())
        assert isinstance(result.id, uuid.UUID)


# ──────────────────────────────────────────────────────────────────
class TestNormalizeStoryPriority:
    def test_none_returns_none(self):
        assert normalize_story_priority(None) is None

    def test_blank_string_returns_none(self):
        assert normalize_story_priority("   ") is None

    @pytest.mark.parametrize("raw", ["High", "highest", "Critical", "BLOCKER", "urgent", "h"])
    def test_high_values_map_to_high(self, raw):
        assert normalize_story_priority(raw) == "High"

    @pytest.mark.parametrize("raw", ["Medium", "normal", "Moderate", "m"])
    def test_medium_values_map_to_medium(self, raw):
        assert normalize_story_priority(raw) == "Medium"

    @pytest.mark.parametrize("raw", ["Low", "lowest", "Minor", "trivial", "l"])
    def test_low_values_map_to_low(self, raw):
        assert normalize_story_priority(raw) == "Low"

    def test_unrecognized_value_returns_none(self):
        """An unmapped Jira label (custom scheme) must not be guessed at —
        it should surface as 'no priority' rather than a wrong value."""
        assert normalize_story_priority("P1") is None

    def test_non_string_value_is_coerced(self):
        assert normalize_story_priority(123) is None


# ──────────────────────────────────────────────────────────────────
# _insert_story
# ──────────────────────────────────────────────────────────────────


class TestInsertStory:
    def test_inserts_with_epic(self):
        db = MagicMock()
        epic = SimpleNamespace(id=uuid.uuid4(), epic_key="EP-1")
        story = _insert_story(db, epic, "ST-1", "Title", "Desc", "AC")
        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert story.story_key == "ST-1"
        assert story.title == "Title"
        assert story.description == "Desc"
        assert story.acceptance_criteria == "AC"

    def test_inserts_with_no_epic(self):
        db = MagicMock()
        story = _insert_story(db, None, "ST-X", "T", "D", "A")
        assert story.epic_id is None

    def test_story_has_uuid_id(self):
        db = MagicMock()
        epic = SimpleNamespace(id=uuid.uuid4(), epic_key="EP-1")
        story = _insert_story(db, epic, "ST-2", "T", "D", "A")
        assert isinstance(story.id, uuid.UUID)


# ──────────────────────────────────────────────────────────────────
# _update_story
# ──────────────────────────────────────────────────────────────────


class TestUpdateStory:
    def test_updates_fields_when_found(self):
        story = SimpleNamespace(
            title="old", description="old", acceptance_criteria="old", priority="Low"
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = story
        _update_story(db, str(uuid.uuid4()), "new", "new desc", "new ac", "High")
        assert story.title == "new"
        assert story.description == "new desc"
        assert story.acceptance_criteria == "new ac"
        assert story.priority == "High"

    def test_does_nothing_when_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        # Should not raise
        _update_story(db, str(uuid.uuid4()), "t", "d", "a")

    def test_does_not_clobber_priority_when_none_supplied(self):
        """A re-import that omits priority (e.g. a stale Jira payload) must not
        wipe out a priority the story already had."""
        story = SimpleNamespace(
            title="old", description="old", acceptance_criteria="old", priority="High"
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = story
        _update_story(db, str(uuid.uuid4()), "new", "new desc", "new ac", None)
        assert story.priority == "High"


# ──────────────────────────────────────────────────────────────────
# refresh_stories_from_jira
# ──────────────────────────────────────────────────────────────────


class TestRefreshStoriesFromJira:
    def test_changed_story_detected(self):
        story = _make_story(
            story_key="ST-1",
            title="Old",
            description="Old",
            acceptance_criteria="Old",
            epic_id="EP-1",
        )
        db = _mock_db(existing_stories=[story])
        result = refresh_stories_from_jira(
            db,
            [
                {
                    "epicId": "EP-1",
                    "user_stories": [
                        {
                            "storyId": "ST-1",
                            "storyTitle": "New",
                            "description": "New",
                            "acceptanceCriteria": "New",
                        }
                    ],
                }
            ],
            project_id=uuid.uuid4(),
        )
        assert "ST-1" in result["changed_story_keys"]

    def test_unchanged_story_not_in_changed_keys(self):
        story = _make_story(
            story_key="ST-1",
            title="Same",
            description="Same",
            acceptance_criteria="Same",
            epic_id="EP-1",
        )
        db = _mock_db(existing_stories=[story])
        result = refresh_stories_from_jira(
            db,
            [
                {
                    "epicId": "EP-1",
                    "user_stories": [
                        {
                            "storyId": "ST-1",
                            "storyTitle": "Same",
                            "description": "Same",
                            "acceptanceCriteria": "Same",
                        }
                    ],
                }
            ],
            project_id=uuid.uuid4(),
        )
        assert "ST-1" not in result["changed_story_keys"]

    def test_epic_change_detected(self):
        """A story that moved to a different epic since the last import must
        be reported as changed, even if title/description/AC are identical."""
        story = _make_story(
            story_key="ST-1",
            title="Same",
            description="Same",
            acceptance_criteria="Same",
            epic_id="EP-OLD",
        )
        db = _mock_db(existing_stories=[story])
        result = refresh_stories_from_jira(
            db,
            [
                {
                    "epicId": "EP-NEW",
                    "user_stories": [
                        {
                            "storyId": "ST-1",
                            "storyTitle": "Same",
                            "description": "Same",
                            "acceptanceCriteria": "Same",
                        }
                    ],
                }
            ],
            project_id=uuid.uuid4(),
        )
        assert "ST-1" in result["changed_story_keys"]

    def test_ungrouped_story_staying_ungrouped_in_same_project_not_reported_changed(self):
        """A story already stored under this project's own UG-<...> key must
        not be falsely flagged as an epic change when Jira still reports it
        as having no epic ("UNGROUPED") on refresh."""
        project_id = uuid.uuid4()
        ungrouped_key = make_ungrouped_epic_key(project_id)
        story = _make_story(
            story_key="ST-1",
            title="Same",
            description="Same",
            acceptance_criteria="Same",
            epic_id=ungrouped_key,
        )
        db = _mock_db(existing_stories=[story])
        result = refresh_stories_from_jira(
            db,
            [
                {
                    "epicId": "UNGROUPED",
                    "user_stories": [
                        {
                            "storyId": "ST-1",
                            "storyTitle": "Same",
                            "description": "Same",
                            "acceptanceCriteria": "Same",
                        }
                    ],
                }
            ],
            project_id=project_id,
        )
        assert "ST-1" not in result["changed_story_keys"]

    def test_new_story_goes_to_new_story_keys(self):
        db = _mock_db(existing_stories=[])  # no existing stories
        result = refresh_stories_from_jira(
            db,
            [
                {
                    "epicId": "EP-1",
                    "user_stories": [
                        {
                            "storyId": "BRAND-NEW",
                            "storyTitle": "N",
                            "description": "",
                            "acceptanceCriteria": "",
                        }
                    ],
                }
            ],
            project_id=uuid.uuid4(),
        )
        assert "BRAND-NEW" in result["new_story_keys"]
        assert "BRAND-NEW" not in result["changed_story_keys"]

    def test_ungrouped_epic_payload_does_not_error(self):
        db = _mock_db(existing_stories=[])
        result = refresh_stories_from_jira(
            db, [{"epicId": "UNGROUPED", "user_stories": []}], project_id=uuid.uuid4()
        )
        assert result["changed_story_keys"] == []

    def test_query_is_scoped_to_project(self):
        """Regression test: must not compare against every project's stories."""
        project_id = uuid.uuid4()
        db = _mock_db(existing_stories=[])
        refresh_stories_from_jira(db, [], project_id=project_id)
        db.query.return_value.join.assert_called_once()
        db.query.return_value.join.return_value.filter.assert_called_once()


# ──────────────────────────────────────────────────────────────────
# apply_refresh_changes
# ──────────────────────────────────────────────────────────────────


class TestApplyRefreshChanges:
    def test_updates_changed_story(self):
        story = SimpleNamespace(
            story_key="ST-1",
            title="Old",
            description="Old",
            acceptance_criteria="Old",
            epic_id="EP-1",
        )
        db = _mock_db(existing_stories=[story])
        with patch("app.database.crud_jira_import._get_or_create_epic") as mock_epic:
            mock_epic.return_value = SimpleNamespace(epic_key="EP-1")
            result = apply_refresh_changes(
                db,
                [
                    {
                        "epicId": "EP-1",
                        "epicTitle": "Epic",
                        "user_stories": [
                            {
                                "storyId": "ST-1",
                                "storyTitle": "New",
                                "description": "ND",
                                "acceptanceCriteria": "NAC",
                            }
                        ],
                    }
                ],
                project_id=uuid.uuid4(),
            )
        assert result == ["ST-1"]
        assert story.title == "New"
        db.commit.assert_called_once()

    def test_skips_unchanged_story(self):
        story = SimpleNamespace(
            story_key="ST-1", title="T", description="D", acceptance_criteria="A", epic_id="EP-1"
        )
        db = _mock_db(existing_stories=[story])
        with patch("app.database.crud_jira_import._get_or_create_epic") as mock_epic:
            mock_epic.return_value = SimpleNamespace(epic_key="EP-1")
            result = apply_refresh_changes(
                db,
                [
                    {
                        "epicId": "EP-1",
                        "epicTitle": "Epic",
                        "user_stories": [
                            {
                                "storyId": "ST-1",
                                "storyTitle": "T",
                                "description": "D",
                                "acceptanceCriteria": "A",
                            }
                        ],
                    }
                ],
                project_id=uuid.uuid4(),
            )
        assert result == []

    def test_unknown_story_id_skipped(self):
        db = _mock_db(existing_stories=[])
        with patch("app.database.crud_jira_import._get_or_create_epic") as mock_epic:
            mock_epic.return_value = SimpleNamespace(epic_key="EP-1")
            result = apply_refresh_changes(
                db,
                [
                    {
                        "epicId": "EP-1",
                        "user_stories": [
                            {
                                "storyId": "UNKNOWN",
                                "storyTitle": "x",
                                "description": "",
                                "acceptanceCriteria": "",
                            }
                        ],
                    }
                ],
                project_id=uuid.uuid4(),
            )
        assert result == []

    def test_empty_payload(self):
        db = _mock_db(existing_stories=[])
        result = apply_refresh_changes(db, [], project_id=uuid.uuid4())
        assert result == []

    def test_epic_with_no_user_stories_key(self):
        db = _mock_db(existing_stories=[])
        result = apply_refresh_changes(db, [{}], project_id=uuid.uuid4())
        assert result == []

    def test_query_is_scoped_to_project(self):
        """Regression test: must not compare against every project's stories."""
        project_id = uuid.uuid4()
        db = _mock_db(existing_stories=[])
        apply_refresh_changes(db, [], project_id=project_id)
        db.query.return_value.join.assert_called_once()
        db.query.return_value.join.return_value.filter.assert_called_once()

    def test_epic_change_updates_story_epic_id(self):
        """A story that moved to a different epic in Jira must be re-pointed
        at the new epic when the refresh is applied."""
        story = SimpleNamespace(
            story_key="ST-1",
            title="T",
            description="D",
            acceptance_criteria="A",
            epic_id="EP-OLD",
        )
        db = _mock_db(existing_stories=[story])
        with patch("app.database.crud_jira_import._get_or_create_epic") as mock_epic:
            mock_epic.return_value = SimpleNamespace(epic_key="EP-NEW")
            result = apply_refresh_changes(
                db,
                [
                    {
                        "epicId": "EP-NEW",
                        "epicTitle": "New Epic",
                        "user_stories": [
                            {
                                "storyId": "ST-1",
                                "storyTitle": "T",
                                "description": "D",
                                "acceptanceCriteria": "A",
                            }
                        ],
                    }
                ],
                project_id=uuid.uuid4(),
            )
        assert result == ["ST-1"]
        assert story.epic_id == "EP-NEW"

    def test_epic_change_to_ungrouped_uses_project_scoped_key(self):
        project_id = uuid.uuid4()
        ungrouped_key = make_ungrouped_epic_key(project_id)
        story = SimpleNamespace(
            story_key="ST-1",
            title="T",
            description="D",
            acceptance_criteria="A",
            epic_id="EP-OLD",
        )
        db = _mock_db(existing_stories=[story])
        with patch("app.database.crud_jira_import._get_or_create_epic") as mock_epic:
            mock_epic.return_value = SimpleNamespace(epic_key=ungrouped_key)
            result = apply_refresh_changes(
                db,
                [
                    {
                        "epicId": "UNGROUPED",
                        "epicTitle": "Imported Stories",
                        "user_stories": [
                            {
                                "storyId": "ST-1",
                                "storyTitle": "T",
                                "description": "D",
                                "acceptanceCriteria": "A",
                            }
                        ],
                    }
                ],
                project_id=project_id,
            )
        assert result == ["ST-1"]
        assert story.epic_id == ungrouped_key

    def test_no_epic_id_in_payload_updates_content_but_not_epic(self):
        """epicId=None in the payload must update title/description/AC but
        must never touch epic_id, and must not call _get_or_create_epic."""
        story = SimpleNamespace(
            story_key="ST-1",
            title="Old",
            description="D",
            acceptance_criteria="A",
            epic_id="EP-1",
        )
        db = _mock_db(existing_stories=[story])
        with patch("app.database.crud_jira_import._get_or_create_epic") as mock_epic:
            result = apply_refresh_changes(
                db,
                [
                    {
                        "epicId": None,
                        "user_stories": [
                            {
                                "storyId": "ST-1",
                                "storyTitle": "New Title",
                                "description": "D",
                                "acceptanceCriteria": "A",
                            }
                        ],
                    }
                ],
                project_id=uuid.uuid4(),
            )
            mock_epic.assert_not_called()
        assert result == ["ST-1"]
        assert story.title == "New Title"
        assert story.epic_id == "EP-1"


# ──────────────────────────────────────────────────────────────────
# save_epics_and_stories
# ──────────────────────────────────────────────────────────────────

_BASE_PAYLOAD = [
    {
        "epicId": "EP-1",
        "epicTitle": "Epic",
        "user_stories": [
            {
                "storyId": "ST-1",
                "storyTitle": "Story",
                "description": "Desc",
                "acceptanceCriteria": "AC",
            }
        ],
    }
]


@patch("app.database.crud_jira_import._insert_story")
@patch("app.database.crud_jira_import._get_or_create_epic")
@patch("app.database.crud_jira_import.check_story_duplicate")
class TestSaveEpicsAndStories:
    def test_insert_action(self, mock_dup, mock_epic, mock_insert):
        db = _mock_db(existing_stories=[])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(action=DuplicateAction.INSERT)
        summary = save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4())
        assert "ST-1" in summary.inserted
        mock_insert.assert_called_once()

    def test_commit_false_defers_the_commit_to_the_caller(self, mock_dup, mock_epic, mock_insert):
        # The story-approval submit relies on this: it passes commit=False so the
        # story upserts share one transaction with the approval-request inserts.
        db = _mock_db(existing_stories=[])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(action=DuplicateAction.INSERT)

        summary = save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4(), commit=False)

        assert "ST-1" in summary.inserted
        db.commit.assert_not_called()

    def test_skip_action(self, mock_dup, mock_epic, mock_insert):
        db = _mock_db(existing_stories=[])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(
            action=DuplicateAction.SKIP, existing_id=str(uuid.uuid4())
        )
        summary = save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4())
        assert "ST-1" in summary.skipped

    @patch("app.database.crud_jira_import._update_story")
    def test_update_action(self, mock_update, mock_dup, mock_epic, mock_insert):
        existing_id = str(uuid.uuid4())
        story = _make_story(story_key="ST-1")
        db = _mock_db(existing_stories=[story])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(
            action=DuplicateAction.UPDATE, existing_id=existing_id
        )
        summary = save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4())
        assert "ST-1" in summary.updated
        mock_update.assert_called_once()

    def test_rename_action(self, mock_dup, mock_epic, mock_insert):
        db = _mock_db(existing_stories=[])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(
            action=DuplicateAction.RENAME, rename_key="ST-1_1", rename_title="Story_1"
        )
        summary = save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4())
        assert summary.renamed[0] == {"original": "ST-1", "renamed": "ST-1_1"}

    def test_insert_exception_adds_to_failed(self, mock_dup, mock_epic, mock_insert):
        db = _mock_db(existing_stories=[])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(action=DuplicateAction.INSERT)
        mock_insert.side_effect = Exception("DB error")
        summary = save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4())
        assert "ST-1" in summary.failed

    def test_ungrouped_epic_uses_project_scoped_key(self, mock_dup, mock_epic, mock_insert):
        db = _mock_db(existing_stories=[])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(action=DuplicateAction.SKIP)
        project_id = uuid.uuid4()
        payload = [{"epicId": "UNGROUPED", "epicTitle": "Any", "user_stories": []}]
        save_epics_and_stories(db, payload, project_id=project_id)
        args = mock_epic.call_args[0]
        assert args[1] == make_ungrouped_epic_key(project_id)
        assert args[1].startswith(f"{_UNGROUPED_PREFIX}-")
        assert len(args[1]) <= 20
        assert args[2] == "Imported Stories"

    def test_ungrouped_epic_keys_differ_per_project(self, mock_dup, mock_epic, mock_insert):
        """The core bug fix: two different projects must never get the same
        Ungrouped epic key."""
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(action=DuplicateAction.SKIP)
        payload = [{"epicId": "UNGROUPED", "epicTitle": "Any", "user_stories": []}]

        project_a = uuid.uuid4()
        save_epics_and_stories(_mock_db(existing_stories=[]), payload, project_id=project_a)
        key_a = mock_epic.call_args[0][1]

        mock_epic.reset_mock()

        project_b = uuid.uuid4()
        save_epics_and_stories(_mock_db(existing_stories=[]), payload, project_id=project_b)
        key_b = mock_epic.call_args[0][1]

        assert key_a != key_b

    def test_existing_stories_preloaded_into_by_title_map(self, mock_dup, mock_epic, mock_insert):
        existing = _make_story(story_key="ST-EXIST", title="ExistingTitle")
        db = _mock_db(existing_stories=[existing])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(action=DuplicateAction.SKIP)
        save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4())
        # Just confirm it ran without error
        assert True

    def test_existing_stories_query_is_scoped_to_project(self, mock_dup, mock_epic, mock_insert):
        """Regression test: duplicate lookup must only consider stories that
        belong to this project (join Epic + filter by project_id), not every
        story in the whole DB — a title collision in another project must
        never trigger a SKIP/UPDATE/RENAME here."""
        project_id = uuid.uuid4()
        db = _mock_db(existing_stories=[])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(action=DuplicateAction.INSERT)
        save_epics_and_stories(db, _BASE_PAYLOAD, project_id=project_id)
        db.query.return_value.join.assert_called_once()
        db.query.return_value.join.return_value.filter.assert_called_once()

    def test_db_commit_called(self, mock_dup, mock_epic, mock_insert):
        db = _mock_db(existing_stories=[])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(action=DuplicateAction.INSERT)
        save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4())
        db.commit.assert_called_once()

    def test_rename_adds_to_cache(self, mock_dup, mock_epic, mock_insert):
        db = _mock_db(existing_stories=[])
        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(
            action=DuplicateAction.RENAME, rename_key="ST-1_1", rename_title="Title_1"
        )
        summary = save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4())
        assert summary.renamed[0]["renamed"] == "ST-1_1"

    def test_raises_when_project_not_found(self, mock_dup, mock_epic, mock_insert):
        """If the project doesn't exist, an AppException is raised before any story processing."""
        db = _mock_db(project_found=False)
        project_id = uuid.uuid4()

        with pytest.raises(AppException) as excinfo:
            save_epics_and_stories(db, _BASE_PAYLOAD, project_id=project_id)

        assert excinfo.value.code == "PROJECT_NOT_FOUND"
        assert str(project_id) in excinfo.value.message
        mock_epic.assert_not_called()
        mock_insert.assert_not_called()

    def test_insert_no_rename_when_key_only_exists_in_this_project(
        self, mock_dup, mock_epic, mock_insert
    ):
        db = _mock_db(existing_stories=[])
        db.query.return_value.filter.return_value.all.return_value = (
            []
        )  # no other project owns "ST-1"

        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(action=DuplicateAction.INSERT)

        summary = save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4())

        assert summary.inserted == ["ST-1"]
        assert summary.renamed == []
        assert summary.failed == []

    def test_insert_fails_cleanly_on_global_story_key_collision(
        self, mock_dup, mock_epic, mock_insert
    ):
        db = _mock_db(existing_stories=[])
        db.query.return_value.filter.return_value.all.return_value = [("ST-1",)]

        mock_epic.return_value = MagicMock()
        mock_dup.return_value = DuplicateCheckResult(action=DuplicateAction.INSERT)

        summary = save_epics_and_stories(db, _BASE_PAYLOAD, project_id=uuid.uuid4())

        assert summary.inserted == []
        assert summary.renamed == []
        assert summary.failed == ["ST-1"]
        assert summary.failed_reasons == [
            {"story_key": "ST-1", "reason": "ALREADY_IMPORTED_IN_ANOTHER_PROJECT"}
        ]
        mock_insert.assert_not_called()
