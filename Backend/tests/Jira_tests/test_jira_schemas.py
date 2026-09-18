"""Unit tests for app/schemas/JiraSchemas.py — 100% coverage."""

import pytest

from app.schemas.JiraSchemas import (
    JiraFetchRequest,
    PushedTestCase,
    PushToJiraResponse,
    RequestModel,
    TestCase,
)
from app.schemas.user_stories import (
    EpicResponse,
    ImportResponse,
    ImportStoriesRequest,
    RefreshStoriesResponse,
    SelectedEpic,
    StoryResponse,
)

# ──────────────────────────────────────────────────────────────────
# TestCase.normalize()
# ──────────────────────────────────────────────────────────────────


class TestTestCaseNormalize:
    def _make(self, **kwargs):
        defaults = dict(title="T", priority="High")
        defaults.update(kwargs)
        return TestCase(**defaults)

    def test_id_set_from_tc_id_when_id_none(self):
        tc = self._make(tc_id="TC-1")
        tc.normalize()
        assert tc.id == "TC-1"

    def test_id_not_overwritten_when_already_set(self):
        tc = self._make(id="TC-ORIG", tc_id="TC-OTHER")
        tc.normalize()
        assert tc.id == "TC-ORIG"

    def test_steps_list_joined_with_pipe(self):
        tc = self._make(steps=["step1", "step2"])
        tc.normalize()
        assert tc.steps == "step1 | step2"

    def test_steps_string_unchanged(self):
        tc = self._make(steps="single step")
        tc.normalize()
        assert tc.steps == "single step"

    def test_steps_none_remains_none(self):
        tc = self._make(steps=None)
        tc.normalize()
        assert tc.steps is None

    def test_expected_list_joined(self):
        tc = self._make(expected=["e1", "e2"])
        tc.normalize()
        assert tc.expected == "e1 | e2"

    def test_scenario_clears_steps_and_expected_and_normalizes_given_when_then(self):
        tc = self._make(
            steps=["s"],
            expected=["e"],
            scenario={
                "given": ["g1", "g2"],
                "when": ["w1"],
                "then": ["t1"],
            },
        )
        tc.normalize()
        assert tc.steps is None
        assert tc.expected is None
        assert tc.scenario["given"] == "g1 | g2"
        assert tc.scenario["when"] == "w1"
        assert tc.scenario["then"] == "t1"

    def test_scenario_missing_keys_use_empty_list(self):
        tc = self._make(scenario={})
        tc.normalize()
        assert tc.scenario == {}

    def test_charter_mission_clears_steps_and_expected(self):
        tc = self._make(steps="s", expected="e", charter_mission="Explore login")
        tc.normalize()
        assert tc.steps is None
        assert tc.expected is None

    def test_charter_scope_list_joined(self):
        tc = self._make(charter_scope=["scope1", "scope2"])
        tc.normalize()
        assert tc.charter_scope == "scope1 | scope2"

    def test_charter_scope_string_unchanged(self):
        tc = self._make(charter_scope="single scope")
        tc.normalize()
        assert tc.charter_scope == "single scope"

    def test_techniques_list_joined(self):
        tc = self._make(techniques=["t1", "t2"])
        tc.normalize()
        assert tc.techniques == "t1 | t2"

    def test_normalize_returns_self(self):
        tc = self._make()
        result = tc.normalize()
        assert result is tc

    def test_all_optional_fields_none(self):
        tc = self._make()
        tc.normalize()
        assert tc.steps is None
        assert tc.expected is None

    def test_model_dump_after_normalize(self):
        tc = self._make(id="TC-1", steps=["a", "b"])
        tc.normalize()
        d = tc.model_dump()
        assert d["steps"] == "a | b"


# ──────────────────────────────────────────────────────────────────
# RequestModel
# ──────────────────────────────────────────────────────────────────


class TestRequestModel:
    def test_valid_standard(self):
        rm = RequestModel(
            userStoryId="US-1",
            projectId="PROJ-1",
            format="standard",
            test_cases=[TestCase(title="T", priority="High")],
        )
        assert rm.format == "standard"

    def test_valid_bdd(self):
        rm = RequestModel(userStoryId="US-1", projectId="PROJ-1", format="bdd", test_cases=[])
        assert rm.format == "bdd"

    def test_valid_exploratory(self):
        rm = RequestModel(
            userStoryId="US-1", projectId="PROJ-1", format="exploratory", test_cases=[]
        )
        assert rm.format == "exploratory"

    def test_invalid_format_raises(self):
        with pytest.raises(Exception):
            RequestModel(userStoryId="US-1", projectId="PROJ-1", format="invalid", test_cases=[])


# ──────────────────────────────────────────────────────────────────
# PushedTestCase
# ──────────────────────────────────────────────────────────────────


class TestPushedTestCase:
    def test_pushed_status(self):
        p = PushedTestCase(tc_id="TC-1", jira_key="JIRA-10", status="pushed")
        assert p.status == "pushed"

    def test_duplicate_status(self):
        p = PushedTestCase(tc_id="TC-1", status="duplicate")
        assert p.jira_key is None

    def test_failed_status(self):
        p = PushedTestCase(tc_id="TC-1", status="failed")
        assert p.rename_note is None

    def test_invalid_status_raises(self):
        with pytest.raises(Exception):
            PushedTestCase(tc_id="TC-1", status="unknown")


# ──────────────────────────────────────────────────────────────────
# PushToJiraResponse defaults
# ──────────────────────────────────────────────────────────────────


class TestPushToJiraResponse:
    def test_defaults(self):
        r = PushToJiraResponse(
            total=5,
            pushed_count=3,
            duplicate_count=1,
            failed_count=1,
            db_saved_count=3,
        )
        assert r.pushed == []
        assert r.duplicates == []
        assert r.failed == []
        assert r.db_skipped == []
        assert r.db_failed == []
        assert r.project_link == ""


# ──────────────────────────────────────────────────────────────────
# JiraFetchRequest
# ──────────────────────────────────────────────────────────────────


class TestJiraFetchRequest:
    def test_required_fields(self):
        r = JiraFetchRequest(
            jira_url="https://company.atlassian.net",
            project_key="ADTD",
            api_token="secret",
        )
        assert r.last_sync is None

    def test_with_last_sync(self):
        from datetime import datetime

        dt = datetime(2024, 1, 1)
        r = JiraFetchRequest(
            jira_url="https://x.atlassian.net",
            project_key="X",
            api_token="t",
            last_sync=dt,
        )
        assert r.last_sync == dt


# ──────────────────────────────────────────────────────────────────
# StoryResponse / EpicResponse
# ──────────────────────────────────────────────────────────────────


class TestStoryResponse:
    def test_basic(self):
        s = StoryResponse(
            storyId="ST-1",
            storyTitle="Story",
            description="Desc",
            issue_type="story",
            status="pending",
        )
        assert s.acceptanceCriteria is None

    def test_with_ac(self):
        s = StoryResponse(
            storyId="ST-2",
            storyTitle="Story",
            description="D",
            acceptanceCriteria="AC",
            issue_type="story",
            status="pending",
        )
        assert s.acceptanceCriteria == "AC"


class TestEpicResponse:
    def test_empty_stories(self):
        e = EpicResponse(epicId="EP-1", epicTitle="Epic", user_stories=[])
        assert e.user_stories == []


# ──────────────────────────────────────────────────────────────────
# SelectedEpic / ImportStoriesRequest
# ──────────────────────────────────────────────────────────────────


class TestImportSchemasI:
    def test_selected_epic_default_title(self):
        se = SelectedEpic(epicId="EP-1", user_stories=[])
        assert se.epicTitle == ""

    def test_import_stories_request(self):
        import uuid

        project_id = uuid.uuid4()
        req = ImportStoriesRequest(selected_epics=[], project_id=project_id)
        assert req.selected_epics == []
        assert req.project_id == project_id


# ──────────────────────────────────────────────────────────────────
# ImportResponse / RefreshStoriesResponse
# ──────────────────────────────────────────────────────────────────


class TestImportResponse:
    def test_defaults(self):
        r = ImportResponse(success=True)
        assert r.inserted == []
        assert r.updated == []
        assert r.failed == []
        assert r.failed_reasons == []
        assert r.skipped == []
        assert r.renamed == []


class TestRefreshStoriesResponse:
    def test_defaults(self):
        r = RefreshStoriesResponse(success=True)
        assert r.imported_count == 0
        assert r.updated_count == 0
        assert r.failed_count == 0
        assert r.changed_story_keys == []
        assert r.new_story_keys == []


class TestJiraStoryUpdate:
    def test_required_fields_and_defaults(self):
        from app.schemas.user_stories import JiraStoryUpdate

        story = JiraStoryUpdate(storyId="ST-101", storyTitle="Title 101")
        assert story.storyId == "ST-101"
        assert story.storyTitle == "Title 101"
        assert story.description == ""
        assert story.acceptanceCriteria is None
        assert story.issue_type == "Story"
        assert story.already_exists is False
        assert story.status is None

    def test_all_fields(self):
        from app.schemas.user_stories import JiraStoryUpdate

        story = JiraStoryUpdate(
            storyId="ST-102",
            storyTitle="Full Story",
            description="Detailed description",
            acceptanceCriteria="Given ... When ... Then ...",
            issue_type="Task",
            already_exists=True,
            status="In Progress",
        )
        assert story.storyId == "ST-102"
        assert story.acceptanceCriteria == "Given ... When ... Then ..."
        assert story.status == "In Progress"


class TestJiraEpicUpdate:
    def test_defaults(self):
        from app.schemas.user_stories import JiraEpicUpdate

        epic = JiraEpicUpdate()
        assert epic.epicId is None
        assert epic.epicTitle is None
        assert epic.user_stories == []

    def test_with_stories(self):
        from app.schemas.user_stories import JiraEpicUpdate, JiraStoryUpdate

        epic = JiraEpicUpdate(
            epicId="EP-1",
            epicTitle="Epic 1",
            user_stories=[JiraStoryUpdate(storyId="ST-1", storyTitle="Story 1")],
        )
        assert epic.epicId == "EP-1"
        assert epic.epicTitle == "Epic 1"
        assert len(epic.user_stories) == 1
        assert epic.user_stories[0].storyId == "ST-1"


class TestJiraCredentialsRequest:
    """Length bounds keep oversized values from reaching the DB columns, where
    they would surface as a 500 rather than a validation error."""

    def _make(self, **kwargs):
        from app.schemas.JiraSchemas import JiraCredentialsRequest

        return JiraCredentialsRequest(**kwargs)

    def test_defaults_are_none(self):
        request = self._make()
        assert request.jira_email is None
        assert request.api_token is None

    def test_empty_strings_are_allowed_as_the_clear_signal(self):
        request = self._make(jira_email="", api_token="")
        assert request.jira_email == ""
        assert request.api_token == ""

    def test_rejects_email_longer_than_the_column(self):
        with pytest.raises(Exception):
            self._make(jira_email="a" * 246 + "@example.com")

    def test_rejects_token_that_would_overflow_once_encrypted(self):
        with pytest.raises(Exception):
            self._make(api_token="t" * 1025)

    def test_longest_accepted_token_still_fits_the_column_once_encrypted(self):
        """Pins max_length to the column: raising one without the other writes a 500."""
        from cryptography.fernet import Fernet

        from app.models.users_models import User
        from app.schemas.JiraSchemas import JiraCredentialsRequest

        max_length = JiraCredentialsRequest.model_fields["api_token"].metadata[0].max_length
        encrypted = Fernet(Fernet.generate_key()).encrypt(b"t" * max_length)

        assert len(encrypted) <= User.__table__.c.jira_api_token.type.length

    def test_accepts_a_realistic_scoped_token(self):
        request = self._make(jira_email="me@example.com", api_token="t" * 200)
        assert request.api_token == "t" * 200
