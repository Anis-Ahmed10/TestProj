"""Unit tests for DatabaseService — 100% coverage of databaseService.py."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import DatabaseOperationException
from app.services.databaseService import DatabaseService
from app.services.jiraService import JiraService

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_story(story_id="US-1", title="Story One"):
    s = MagicMock()
    s.storyId = story_id
    s.storyTitle = title
    s.description = "Some description"
    s.acceptanceCriteria = "AC text"
    s.issue_type = "story"
    s.already_exists = False
    s.status = "pending"
    return s


def _make_epic(epic_id="EP-1", stories=None):
    e = MagicMock()
    e.epicId = epic_id
    e.epicTitle = f"Epic {epic_id}"
    e.user_stories = stories or [_make_story()]
    return e


# ── get_story_statuses ───────────────────────────────────────────────────────


class TestGetStoryStatuses:
    @patch("app.services.databaseService.get_existing_story_statuses")
    def test_delegates_to_enrichment_with_keys_and_project(self, mock_enrich):
        expected = {"US-1": {"already_exists": True, "status": "pending_approval"}}
        mock_enrich.return_value = expected
        db = MagicMock()
        project_id = uuid.uuid4()

        result = DatabaseService.get_story_statuses(
            db=db, project_id=project_id, story_keys=["US-1", "US-2"]
        )

        assert result == expected
        mock_enrich.assert_called_once_with(db, ["US-1", "US-2"], project_id)


# ── save_test_cases ──────────────────────────────────────────────────────────


class TestSaveTestCases:

    @pytest.mark.asyncio
    async def test_returns_saved_count_and_cases(self):
        """Happy path: normalised test cases are bulk-saved and counts returned."""
        mock_tc = MagicMock()
        mock_tc.normalize.return_value.model_dump.return_value = {
            "id": "TC-1",
            "title": "Login test",
        }

        request = MagicMock()
        request.test_cases = [mock_tc]
        request.userStoryId = "US-42"
        request.format = "bdd"

        mock_result = MagicMock()
        mock_result.inserted = [{"id": "TC-1"}]
        mock_result.skipped = []
        mock_result.failed = []

        db = MagicMock()

        with patch(
            "app.services.databaseService.bulk_save_test_cases",
            return_value=mock_result,
        ) as mock_save:
            result = await DatabaseService.save_test_cases(request, db)

        mock_save.assert_called_once()
        assert result["saved_count"] == 1
        assert result["saved_test_cases"] == [{"id": "TC-1"}]
        assert result["skipped"] == []
        assert result["failed"] == []

    @pytest.mark.asyncio
    async def test_empty_test_cases_returns_zeros(self):
        """No test cases → saved_count is 0."""
        request = MagicMock()
        request.test_cases = []
        request.userStoryId = "US-1"
        request.format = "standard"

        mock_result = MagicMock()
        mock_result.inserted = []
        mock_result.skipped = []
        mock_result.failed = []

        db = MagicMock()

        with patch(
            "app.services.databaseService.bulk_save_test_cases",
            return_value=mock_result,
        ):
            result = await DatabaseService.save_test_cases(request, db)

        assert result["saved_count"] == 0


# ── save_selected_stories ───────────────────────────────────────────────────────


class TestSaveSelectedStories:

    def test_no_db_returns_total_count(self):
        """When db is None, returns imported_count without hitting the DB."""
        epics = [_make_epic(stories=[_make_story(), _make_story()])]
        result = DatabaseService.save_selected_stories(
            db=None, selected_epics=epics, project_id=uuid.uuid4()
        )

        assert result["imported_count"] == 2
        assert result["updated_count"] == 0
        assert result["failed_count"] == 0

    def test_happy_path_with_db(self):
        """With a real DB session, delegates to save_epics_and_stories."""
        epics = [_make_epic()]

        mock_summary = MagicMock()
        mock_summary.inserted = 1
        mock_summary.updated = 0
        mock_summary.failed = 0
        mock_summary.skipped = 0
        mock_summary.renamed = []

        db = MagicMock()

        with patch(
            "app.services.databaseService.save_epics_and_stories",
            return_value=mock_summary,
        ) as mock_fn:
            result = DatabaseService.save_selected_stories(db, epics, uuid.uuid4())

        mock_fn.assert_called_once()
        assert result["success"] is True
        assert result["inserted"] == 1

    def test_db_exception_raises_database_operation_exception(self):
        """DB failure rolls back and raises DatabaseOperationException."""
        epics = [_make_epic()]
        db = MagicMock()

        with patch(
            "app.services.databaseService.save_epics_and_stories",
            side_effect=RuntimeError("Connection lost"),
        ):
            with pytest.raises(DatabaseOperationException):
                DatabaseService.save_selected_stories(db, epics, uuid.uuid4())

        db.rollback.assert_called_once()

    def test_app_exception_rolls_back_and_reraises(self):
        """If save_epics_and_stories raises AppException, it rolls back and re-raises as-is."""
        from app.core.exceptions import AppException

        epics = [_make_epic()]
        db = MagicMock()
        original_exc = AppException(code="SOME_ERROR", message="something failed", status_code=400)

        with patch(
            "app.services.databaseService.save_epics_and_stories",
            side_effect=original_exc,
        ):
            with pytest.raises(AppException) as excinfo:
                DatabaseService.save_selected_stories(db, epics, uuid.uuid4())

        assert excinfo.value is original_exc
        db.rollback.assert_called_once()


# ── save_story_edit_log ─────────────────────────────────────────────────────────


class TestSaveStoryEditLog:

    def test_delegates_to_bulk_insert_edit_log(self):
        """Records are serialised and passed through to bulk_insert_edit_log."""
        from datetime import datetime, timezone

        from app.schemas.user_stories import StoryChangeSchema, StoryEditRecordSchema

        record = StoryEditRecordSchema(
            storyId="US-1",
            epicId="EP-1",
            changes=[
                StoryChangeSchema(field="storyTitle", before="Old", after="New"),
            ],
            editedAt=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db = MagicMock()

        with patch(
            "app.services.databaseService.bulk_insert_edit_log", return_value=3
        ) as mock_bulk:
            result = DatabaseService.save_story_edit_log(db, [record])

        assert result == 3
        mock_bulk.assert_called_once()
        _, kwargs = mock_bulk.call_args
        assert kwargs["db"] is db
        assert kwargs["records"][0]["storyId"] == "US-1"
        assert kwargs["records"][0]["epicId"] == "EP-1"
        assert kwargs["records"][0]["changes"][0]["field"] == "storyTitle"
        assert kwargs["records"][0]["changes"][0]["before"] == "Old"
        assert kwargs["records"][0]["changes"][0]["after"] == "New"
        assert kwargs["records"][0]["editedAt"] == record.editedAt

    def test_empty_edit_log_returns_zero(self):
        """An empty edit_log list results in an empty records list being passed through."""
        db = MagicMock()

        with patch(
            "app.services.databaseService.bulk_insert_edit_log", return_value=0
        ) as mock_bulk:
            result = DatabaseService.save_story_edit_log(db, [])

        assert result == 0
        mock_bulk.assert_called_once_with(db=db, records=[])


# ── refresh_imported_stories ────────────────────────────────────────────────────


class TestRefreshImportedStories:

    @pytest.mark.asyncio
    async def test_no_db_returns_empty_result(self):
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        with patch(
            "app.services.jiraService.JiraService.fetch_jira_data",
            new=AsyncMock(return_value=[]),
        ):
            result = await JiraService(db).refresh_imported_stories(
                jira_url="https://jira.example.com",
                project_key="PROJ",
                api_token="token",
                project_id=uuid.uuid4(),
            )
        assert result["updated_count"] == 0
        assert result["changed_story_keys"] == []

    @pytest.mark.asyncio
    async def test_happy_path_returns_changed_keys(self):
        db = MagicMock()
        fake_epics = [_make_epic()]

        with (
            patch(
                "app.services.jiraService.JiraService.fetch_jira_data",
                new=AsyncMock(return_value=fake_epics),
            ),
            patch(
                "app.services.jiraService.refresh_stories_from_jira",
                return_value={"changed_story_keys": ["US-1", "US-2"], "new_story_keys": []},
            ),
        ):
            result = await JiraService(db).refresh_imported_stories(
                jira_url="https://jira.example.com",
                project_key="PROJ",
                api_token="token",
                project_id=uuid.uuid4(),
            )

        assert result["updated_count"] == 2
        assert result["changed_story_keys"] == ["US-1", "US-2"]

    @pytest.mark.asyncio
    async def test_happy_path_new_story_keys_included(self):
        """new_story_keys from the refresh result appear in the response."""
        db = MagicMock()

        with (
            patch(
                "app.services.jiraService.JiraService.fetch_jira_data",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.jiraService.refresh_stories_from_jira",
                return_value={
                    "changed_story_keys": ["US-5"],
                    "new_story_keys": ["US-99"],
                },
            ),
        ):
            result = await JiraService(db).refresh_imported_stories(
                jira_url="https://jira.example.com",
                project_key="PROJ",
                api_token="token",
                project_id=uuid.uuid4(),
            )

        assert result["new_story_keys"] == ["US-99"]
        assert result["updated_count"] == 1

    @pytest.mark.asyncio
    async def test_exception_rolls_back_and_raises(self):
        """Any exception inside the try block rolls back and raises DatabaseOperationException."""
        db = MagicMock()

        with patch(
            "app.services.jiraService.JiraService.fetch_jira_data",
            new=AsyncMock(side_effect=RuntimeError("Jira down")),
        ):
            with pytest.raises(DatabaseOperationException):
                await JiraService(db).refresh_imported_stories(
                    jira_url="https://jira.example.com",
                    project_key="PROJ",
                    api_token="token",
                    project_id=uuid.uuid4(),
                )

        db.rollback.assert_called_once()


# ── apply_refresh_updates ───────────────────────────────────────────────────────


class TestApplyRefreshUpdates:
    """Tests for JiraService.apply_refresh_updates (previously untested)."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_updated_list(self):
        """
        fetch_jira_data succeeds → apply_refresh_changes called →
        result contains success=True and the updated list.
        """
        db = MagicMock()
        fake_epics = [_make_epic()]
        fake_updated = ["US-1", "US-2"]

        with (
            patch(
                "app.services.jiraService.JiraService.fetch_jira_data",
                new=AsyncMock(return_value=fake_epics),
            ) as mock_fetch,
            patch(
                "app.services.jiraService.apply_refresh_changes",
                return_value=fake_updated,
            ) as mock_apply,
        ):
            project_id = uuid.uuid4()
            result = await JiraService(db).apply_refresh_updates(
                jira_url="https://jira.example.com",
                project_key="PROJ",
                api_token="token",
                project_id=project_id,
            )

        mock_fetch.assert_awaited_once_with(
            "https://jira.example.com", "PROJ", "token", statuses=None, db=db, jira_email=""
        )
        mock_apply.assert_called_once_with(db, fake_epics, project_id)
        assert result["success"] is True
        assert result["updated"] == fake_updated

    @pytest.mark.asyncio
    async def test_empty_updated_list(self):
        """apply_refresh_changes returning [] still yields success=True."""
        db = MagicMock()

        with (
            patch(
                "app.services.jiraService.JiraService.fetch_jira_data",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.jiraService.apply_refresh_changes",
                return_value=[],
            ),
        ):
            result = await JiraService(db).apply_refresh_updates(
                jira_url="https://jira.example.com",
                project_key="PROJ",
                api_token="token",
                project_id=uuid.uuid4(),
            )

        assert result["success"] is True
        assert result["updated"] == []

    @pytest.mark.asyncio
    async def test_fetch_failure_propagates(self):
        """
        If fetch_jira_data raises, DatabaseOperationException is raised and db is rolled back.
        """
        db = MagicMock()

        with patch(
            "app.services.jiraService.JiraService.fetch_jira_data",
            new=AsyncMock(side_effect=RuntimeError("network down")),
        ):
            with pytest.raises(DatabaseOperationException, match="network down"):
                await JiraService(db).apply_refresh_updates(
                    jira_url="https://jira.example.com",
                    project_key="PROJ",
                    api_token="token",
                    project_id=uuid.uuid4(),
                )
        db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_changes_failure_propagates(self):
        """
        If apply_refresh_changes raises, DatabaseOperationException is raised
        and db is rolled back.
        """
        db = MagicMock()

        with (
            patch(
                "app.services.jiraService.JiraService.fetch_jira_data",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.jiraService.apply_refresh_changes",
                side_effect=Exception("DB write error"),
            ),
        ):
            with pytest.raises(DatabaseOperationException, match="DB write error"):
                await JiraService(db).apply_refresh_updates(
                    jira_url="https://jira.example.com",
                    project_key="PROJ",
                    api_token="token",
                    project_id=uuid.uuid4(),
                )
        db.rollback.assert_called_once()
