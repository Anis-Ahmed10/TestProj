import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_request_authorizer
from app.components.authorizer import AuthenticatedUser, Role
from app.database import crud_test_cases
from app.database.crud_test_cases import (
    _insert_test_case,
    _load_existing_rows,
    update_jira_key,
)
from app.main import app
from app.models.epics_model import Epic
from app.models.project_models import Project
from app.models.story_edit_log_model import StoryEditLog
from app.models.test_cases_model import TestCase
from app.models.user_stories_model import UserStory
from app.services.internal import (
    _attach_epics,
    _attach_stories,
    _attach_test_cases_and_logs,
    _build_project_index,
    _index_edit_logs,
)
from app.services.test_case_service import fetch_test_library_payload_by_project


class _AllowAllAuthorizer:
    """Test authorizer that grants every permission; authz is not under test here."""

    def has_permission(self, user, permission) -> bool:
        return True

    def permissions_for(self, user) -> frozenset:
        return frozenset()


@pytest.fixture()
def client(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Test User",
        email="test.user@example.com",
        role=Role.TEST_LEAD.value,
        is_active=True,
    )
    app.dependency_overrides[get_request_authorizer] = lambda: _AllowAllAuthorizer()
    monkeypatch.setattr(
        "app.api.dependencies.get_visible_project_ids",
        lambda db, user_id: None,
    )
    monkeypatch.setattr(
        "app.database.users_db.get_user_by_id",
        lambda db, user_id: AuthenticatedUser(
            id=user_id,
            name="Test User",
            email="test.user@example.com",
            role=Role.TEST_LEAD.value,
            is_active=True,
        ),
    )
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_request_authorizer, None)


def test_get_test_library_endpoint_success(monkeypatch, client: TestClient):
    expected_payload = [
        {
            "project_id": str(uuid.uuid4()),
            "project_name": "Demo Project",
            "epics": [
                {
                    "epic_id": str(uuid.uuid4()),
                    "epic_key": "EPIC-1",
                    "epic_title": "Demo Epic",
                    "user_stories": [
                        {
                            "id": str(uuid.uuid4()),
                            "story_key": "STORY-1",
                            "title": "Demo Story",
                            "description": "Story description",
                            "acceptance_criteria": "Criteria",
                            "priority": "High",
                            "story_edit_logs": [
                                {
                                    "changes": {"title": "updated"},
                                    "edited_at": "2024-01-01T00:00:00",
                                }
                            ],
                            "test_cases": [
                                {
                                    "id": str(uuid.uuid4()),
                                    "title": "Approved TC",
                                    "test_format_type": "bdd",
                                    "test_data": {"steps": []},
                                    "jira_key": "JIRA-1",
                                    "status": "approved",
                                    "created_at": "2024-01-01T00:00:00",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    project_id = uuid.uuid4()
    captured_kwargs = {}

    def _mock_fetch(_db, pid, status_filter="approved"):
        captured_kwargs["pid"] = pid
        captured_kwargs["status_filter"] = status_filter
        return expected_payload

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.fetch_test_library_payload_by_project",
        _mock_fetch,
    )

    resp = client.get(f"/api/v1/test-cases/library/{project_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "Test library retrieved successfully"
    assert body["data"] == expected_payload
    assert captured_kwargs["pid"] == project_id
    assert captured_kwargs["status_filter"] == "approved"


def test_get_test_library_endpoint_with_status_query_param(monkeypatch, client: TestClient):
    project_id = uuid.uuid4()
    captured_kwargs = {}

    def _mock_fetch(_db, pid, status_filter="approved"):
        captured_kwargs["pid"] = pid
        captured_kwargs["status_filter"] = status_filter
        return []

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.fetch_test_library_payload_by_project",
        _mock_fetch,
    )

    resp = client.get(f"/api/v1/test-cases/library/{project_id}?status=pending")
    assert resp.status_code == 200
    assert captured_kwargs["status_filter"] == "pending"


def test_get_test_library_endpoint_with_unapproved_query_param(monkeypatch, client: TestClient):
    project_id = uuid.uuid4()
    captured_kwargs = {}

    def _mock_fetch(_db, pid, status_filter="approved"):
        captured_kwargs["pid"] = pid
        captured_kwargs["status_filter"] = status_filter
        return []

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.fetch_test_library_payload_by_project",
        _mock_fetch,
    )

    resp = client.get(f"/api/v1/test-cases/library/{project_id}?status=unapproved")
    assert resp.status_code == 200
    assert captured_kwargs["status_filter"] == "pending"


def test_get_test_library_endpoint_with_all_query_param(monkeypatch, client: TestClient):
    project_id = uuid.uuid4()
    captured_kwargs = {}

    def _mock_fetch(_db, pid, status_filter="approved"):
        captured_kwargs["pid"] = pid
        captured_kwargs["status_filter"] = status_filter
        return []

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.fetch_test_library_payload_by_project",
        _mock_fetch,
    )

    resp = client.get(f"/api/v1/test-cases/library/{project_id}?status=all")
    assert resp.status_code == 200
    assert captured_kwargs["status_filter"] == "all"


def test_get_test_library_endpoint_with_invalid_status_returns_422(client: TestClient):
    project_id = uuid.uuid4()
    resp = client.get(f"/api/v1/test-cases/library/{project_id}?status=invalid_status")
    assert resp.status_code == 422


def test_get_test_library_endpoint_exception(monkeypatch, client: TestClient):
    project_id = uuid.uuid4()

    def _mock_fetch(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.api.v1.endpoints.test_cases.fetch_test_library_payload_by_project",
        _mock_fetch,
    )

    resp = client.get(f"/api/v1/test-cases/library/{project_id}")
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "TEST_LIBRARY_BY_PROJECT_FETCH_FAILED"


def test_fetch_test_library_payload_returns_empty_if_no_approved_test_cases(monkeypatch):
    monkeypatch.setattr(
        "app.services.test_case_service.fetch_test_library_by_project",
        lambda db, project_id, status_filter="approved": {},
    )

    result = fetch_test_library_payload_by_project(FakeDB(), uuid.uuid4())

    assert result == []


def test_fetch_raw_test_library_rows_returns_empty_when_no_test_cases():
    fake_db = FakeDB(query_results={TestCase: []})

    result = crud_test_cases.fetch_test_library_by_project(fake_db, uuid.uuid4())

    assert result == {}


def test_fetch_raw_test_library_rows_returns_empty_when_approved_cases_have_no_story_keys():
    test_case_obj = SimpleNamespace(user_story_id=None, status="approved")
    fake_db = FakeDB(
        query_results={
            TestCase: [test_case_obj],
        }
    )

    result = crud_test_cases.fetch_test_library_by_project(fake_db, uuid.uuid4())

    assert result == {}


@pytest.mark.parametrize("status_filter", ["approved", "pending", "unapproved", "all", None])
def test_fetch_raw_test_library_rows_with_status_filter_success(status_filter):
    pid = uuid.uuid4()
    test_case_obj = SimpleNamespace(
        user_story_id="STORY-1", status="approved", created_at="2024-01-01"
    )
    story_obj = SimpleNamespace(story_key="STORY-1", epic_id="EPIC-1")
    epic_obj = SimpleNamespace(epic_key="EPIC-1")
    project_obj = SimpleNamespace(id=pid)
    edit_log_obj = SimpleNamespace(story_id="STORY-1", changes={}, edited_at="2024-01-01")

    fake_db = FakeDB(
        query_results={
            TestCase: [test_case_obj],
            UserStory: [story_obj],
            Epic: [epic_obj],
            Project: [project_obj],
            StoryEditLog: [edit_log_obj],
        }
    )

    result = crud_test_cases.fetch_test_library_by_project(
        fake_db, pid, status_filter=status_filter
    )

    assert result["projects"] == [project_obj]
    assert result["epics"] == [epic_obj]
    assert result["user_stories"] == [story_obj]
    assert result["test_cases"] == [test_case_obj]


def test_fetch_raw_test_library_rows_no_project_found():
    pid = uuid.uuid4()
    test_case_obj = SimpleNamespace(
        user_story_id="STORY-1", status="approved", created_at="2024-01-01"
    )
    story_obj = SimpleNamespace(story_key="STORY-1", epic_id="EPIC-1")
    epic_obj = SimpleNamespace(epic_key="EPIC-1")

    fake_db = FakeDB(
        query_results={
            TestCase: [test_case_obj],
            UserStory: [story_obj],
            Epic: [epic_obj],
            Project: [],
        }
    )

    result = crud_test_cases.fetch_test_library_by_project(fake_db, pid)
    assert result["projects"] == []


def test_fetch_raw_test_library_rows_raises_on_db_error(monkeypatch):
    class BrokenDB(FakeDB):
        def query(self, *entities):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        crud_test_cases.fetch_test_library_by_project(BrokenDB(), uuid.uuid4())


def test_fetch_test_library_payload_build_nested_payload(monkeypatch):
    test_case_obj = SimpleNamespace(
        id="tc-1",
        user_story_id="STORY-1",
        title="Approved TC",
        test_format_type="bdd",
        test_data={"steps": []},
        jira_key="JIRA-1",
        status="approved",
        created_at="2024-01-01T00:00:00",
    )
    story_obj = SimpleNamespace(
        id="story-1",
        story_key="STORY-1",
        title="Story One",
        description="Story description",
        acceptance_criteria="Criteria",
        priority="High",
        epic_id="EPIC-1",
    )
    epic_obj = SimpleNamespace(
        id="epic-1",
        project_id="project-1",
        epic_key="EPIC-1",
        title="Epic One",
    )
    project_obj = SimpleNamespace(id="project-1", name="Project One")
    edit_log_obj = SimpleNamespace(
        story_id="STORY-1",
        changes={"field": "updated"},
        edited_at="2024-01-01T00:00:00",
    )

    def _mock_raw_rows(db, project_id, status_filter="approved"):
        return {
            "projects": [project_obj],
            "epics": [epic_obj],
            "user_stories": [story_obj],
            "story_edit_logs": [edit_log_obj],
            "test_cases": [test_case_obj],
        }

    monkeypatch.setattr(
        "app.services.test_case_service.fetch_test_library_by_project",
        _mock_raw_rows,
    )

    result = fetch_test_library_payload_by_project(FakeDB(), uuid.uuid4())

    assert result == [
        {
            "project_id": "project-1",
            "project_name": "Project One",
            "epics": [
                {
                    "epic_id": "epic-1",
                    "epic_key": "EPIC-1",
                    "epic_title": "Epic One",
                    "user_stories": [
                        {
                            "id": "story-1",
                            "story_key": "STORY-1",
                            "title": "Story One",
                            "description": "Story description",
                            "acceptance_criteria": "Criteria",
                            "priority": "High",
                            "story_edit_logs": [
                                {
                                    "changes": {"field": "updated"},
                                    "edited_at": "2024-01-01T00:00:00",
                                }
                            ],
                            "test_cases": [
                                {
                                    "id": "tc-1",
                                    "title": "Approved TC",
                                    "test_format_type": "bdd",
                                    "test_data": {"steps": []},
                                    "jira_key": "JIRA-1",
                                    "status": "approved",
                                    "created_at": "2024-01-01T00:00:00",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ]


def test_payload_returns_project_with_no_epics_if_approved_test_cases_have_no_story_keys(
    monkeypatch,
):

    test_case_obj = SimpleNamespace(
        id="tc-1",
        user_story_id=None,
        title="Approved TC",
        test_format_type="bdd",
        test_data={"steps": []},
        jira_key="JIRA-1",
        status="approved",
        created_at="2024-01-01T00:00:00",
    )

    monkeypatch.setattr(
        "app.services.test_case_service.fetch_test_library_by_project",
        lambda db, project_id, status_filter="approved": {
            "projects": [SimpleNamespace(id="project-1", name="Project One")],
            "epics": [],
            "user_stories": [],
            "story_edit_logs": [],
            "test_cases": [test_case_obj],
        },
    )

    result = fetch_test_library_payload_by_project(FakeDB(), uuid.uuid4())

    assert result == [
        {
            "project_id": "project-1",
            "project_name": "Project One",
            "epics": [],
        }
    ]


def test_fetch_test_library_payload_raises_on_db_error(monkeypatch):
    def _mock_raw_rows(db, project_id, status_filter="approved"):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.services.test_case_service.fetch_test_library_by_project",
        _mock_raw_rows,
    )

    with pytest.raises(RuntimeError):
        fetch_test_library_payload_by_project(FakeDB(), uuid.uuid4())


class FakeQuery:
    def __init__(self, results):
        self._results = results

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._results

    def first(self):
        return self._results[0] if self._results else None


class FakeDB:
    def __init__(self, query_results=None):
        self.query_results = query_results or {}
        self.executed = []
        self.committed = False
        self.rolled_back = False

    def query(self, *entities):
        model = entities[0] if entities else None
        if hasattr(model, "class_"):
            model = model.class_
        return FakeQuery(self.query_results.get(model, []))

    def execute(self, query, params=None):
        self.executed.append((query, params))
        return type("Result", (), {"rowcount": 1})()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_payload_returns_empty_if_no_approved_test_cases():
    fake_db = FakeDB(query_results={})

    result = fetch_test_library_payload_by_project(fake_db, uuid.uuid4())

    assert result == []


def test_payload_build_nested_payload():
    test_case_obj = SimpleNamespace(
        id="tc-1",
        user_story_id="STORY-1",
        title="Approved TC",
        test_format_type="bdd",
        test_data={"steps": []},
        jira_key="JIRA-1",
        status="approved",
        created_at="2024-01-01T00:00:00",
    )
    story_obj = SimpleNamespace(
        id="story-1",
        story_key="STORY-1",
        title="Story One",
        description="Story description",
        acceptance_criteria="Criteria",
        priority="High",
        epic_id="EPIC-1",
    )
    epic_obj = SimpleNamespace(
        id="epic-1",
        project_id="project-1",
        epic_key="EPIC-1",
        title="Epic One",
    )
    project_obj = SimpleNamespace(id="project-1", name="Project One")
    edit_log_obj = SimpleNamespace(
        story_id="STORY-1",
        changes={"field": "updated"},
        edited_at="2024-01-01T00:00:00",
    )

    fake_db = FakeDB(
        query_results={
            TestCase: [test_case_obj],
            UserStory: [story_obj],
            Epic: [epic_obj],
            Project: [project_obj],
            StoryEditLog: [edit_log_obj],
        }
    )

    result = fetch_test_library_payload_by_project(fake_db, uuid.uuid4())

    assert result == [
        {
            "project_id": "project-1",
            "project_name": "Project One",
            "epics": [
                {
                    "epic_id": "epic-1",
                    "epic_key": "EPIC-1",
                    "epic_title": "Epic One",
                    "user_stories": [
                        {
                            "id": "story-1",
                            "story_key": "STORY-1",
                            "title": "Story One",
                            "description": "Story description",
                            "acceptance_criteria": "Criteria",
                            "priority": "High",
                            "story_edit_logs": [
                                {
                                    "changes": {"field": "updated"},
                                    "edited_at": "2024-01-01T00:00:00",
                                }
                            ],
                            "test_cases": [
                                {
                                    "id": "tc-1",
                                    "title": "Approved TC",
                                    "test_format_type": "bdd",
                                    "test_data": {"steps": []},
                                    "jira_key": "JIRA-1",
                                    "status": "approved",
                                    "created_at": "2024-01-01T00:00:00",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ]


def test_bulk_save_test_cases_skips_duplicate_and_renames_conflicting_id(monkeypatch):
    existing_row = {"tc_id": "tc-1", "signature": "sig1"}
    monkeypatch.setattr(
        "app.database.crud_test_cases._load_existing_rows",
        lambda db, user_story_id: [existing_row],
    )
    monkeypatch.setattr(
        "app.database.crud_test_cases.build_row_signature",
        lambda row: row["signature"],
    )
    monkeypatch.setattr(
        "app.database.crud_test_cases.build_test_case_signature",
        lambda tc: tc["signature"],
    )

    inserted_calls = []

    def _mock_insert_test_case(db, tc, tc_id, user_story_id, format_type, jira_key, created_by):
        inserted_calls.append((tc_id, jira_key, created_by))

    monkeypatch.setattr(
        "app.database.crud_test_cases._insert_test_case",
        _mock_insert_test_case,
    )

    fake_db = FakeDB()
    test_cases = [
        {"id": "tc-1", "signature": "sig1"},
        {"id": "tc-1", "signature": "sig2"},
    ]
    summary = crud_test_cases.bulk_save_test_cases(
        db=fake_db,
        test_cases=test_cases,
        user_story_id="story-1",
        format_type="bdd",
        jira_push_results=[{"tc_id": "tc-1", "jira_key": "JIRA-1", "status": "approved"}],
        created_by="user-1",
    )

    assert summary.skipped == ["tc-1"]
    assert summary.inserted == ["tc-1_1"]
    assert summary.renamed == [{"original": "tc-1", "renamed": "tc-1_1"}]
    assert inserted_calls == [("tc-1_1", "JIRA-1", "user-1")]
    assert fake_db.committed is True
    assert fake_db.rolled_back is False


def test_update_jira_key_executes_database_update(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(
        "app.database.crud_test_cases._read_sql_file",
        lambda filename: "UPDATE SQL",
    )

    update_jira_key(fake_db, "story-1", "Test case title", "JIRA-1")

    assert len(fake_db.executed) == 1
    query, params = fake_db.executed[0]
    assert str(query) == "UPDATE SQL"
    assert params == {
        "user_story_id": "story-1",
        "tc_title": "Test case title",
        "jira_key": "JIRA-1",
    }


def test_load_existing_rows_handles_missing_payload(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(
        "app.database.crud_test_cases._read_sql_file",
        lambda filename: "SELECT SQL",
    )
    fake_db.execute = lambda query, params=None: type(
        "Result",
        (),
        {
            "fetchall": lambda self: [
                SimpleNamespace(test_data=None, title="Title A"),
                SimpleNamespace(
                    test_data={"tc_id": "tc-2", "scenario": {"given": "given"}}, title="Title B"
                ),
            ]
        },
    )()

    result = _load_existing_rows(fake_db, "story-1")

    assert result[0]["tc_id"] == ""
    assert result[0]["title"] == "Title A"
    assert result[1]["tc_id"] == "tc-2"
    assert result[1]["given_steps"] == "given"


def test_attach_epics_skips_when_project_missing():
    projects, lookup = _build_project_index([SimpleNamespace(id="project-1", name="Project One")])

    epics = [
        SimpleNamespace(
            id="epic-1",
            project_id="unknown-project",
            epic_key="EPIC-1",
            title="Epic One",
        )
    ]

    epic_lookup = _attach_epics(epics, lookup)

    assert epic_lookup == {}
    assert projects == [
        {
            "project_id": "project-1",
            "project_name": "Project One",
            "epics": [],
        }
    ]


def test_attach_stories_skips_when_epic_missing():
    projects, project_lookup = _build_project_index(
        [SimpleNamespace(id="project-1", name="Project One")]
    )

    # no epics attached => epic_lookup empty
    epic_lookup = _attach_epics([], project_lookup)

    stories = [
        SimpleNamespace(
            id="story-1",
            epic_id="unknown-epic",
            story_key="STORY-1",
            title="Story One",
            description="Story description",
            acceptance_criteria="Criteria",
            priority="High",
        )
    ]

    story_lookup = _attach_stories(stories, epic_lookup)

    assert story_lookup == {}
    assert projects[0]["epics"] == []


def test_attach_test_cases_and_logs_skips_when_story_missing():

    projects, project_lookup = _build_project_index(
        [SimpleNamespace(id="project-1", name="Project One")]
    )

    # Attach one epic but no matching story
    epic_lookup = _attach_epics(
        [
            SimpleNamespace(
                id="epic-1",
                project_id="project-1",
                epic_key="EPIC-1",
                title="Epic One",
            )
        ],
        project_lookup,
    )

    story_lookup = _attach_stories([], epic_lookup)
    logs_by_story = _index_edit_logs([])

    approved_test_cases = [
        SimpleNamespace(
            id="tc-1",
            user_story_id="STORY-1",  # missing in story_lookup
            title="Approved TC",
            test_format_type="bdd",
            test_data={"steps": []},
            jira_key="JIRA-1",
            status="approved",
            created_at="2024-01-01T00:00:00",
        )
    ]

    _attach_test_cases_and_logs(approved_test_cases, story_lookup, logs_by_story)

    assert projects == [
        {
            "project_id": "project-1",
            "project_name": "Project One",
            "epics": [
                {
                    "epic_id": "epic-1",
                    "epic_key": "EPIC-1",
                    "epic_title": "Epic One",
                    "user_stories": [],
                }
            ],
        }
    ]


def test_index_edit_logs_skips_rows_without_story_id():
    logs = [
        SimpleNamespace(
            story_id="", changes={"field": "ignored"}, edited_at="2024-01-01T00:00:00"
        ),
        SimpleNamespace(
            story_id=None, changes={"field": "ignored"}, edited_at="2024-01-02T00:00:00"
        ),
        SimpleNamespace(
            story_id="STORY-1", changes={"field": "kept"}, edited_at="2024-01-03T00:00:00"
        ),
    ]

    result = _index_edit_logs(logs)

    assert result == {
        "STORY-1": [
            {
                "changes": {"field": "kept"},
                "edited_at": "2024-01-03T00:00:00",
            }
        ]
    }


def test_insert_test_case_serializes_test_data(monkeypatch):

    fake_db = FakeDB()

    monkeypatch.setattr(
        "app.database.crud_test_cases._read_sql_file",
        lambda filename: "INSERT SQL",
    )

    _insert_test_case(
        fake_db,
        tc={
            "type": "ui",
            "steps": ["step1"],
            "expected": "expected",
            "scenario": {"given": "given"},
            "preconditions": "none",
            "title": "Title",
            "priority": "High",
            "tags": ["tag1"],
        },
        tc_id="tc-1",
        user_story_id="story-1",
        format_type="bdd",
        jira_key="JIRA-1",
        created_by="user-1",
    )

    assert len(fake_db.executed) == 1
    _, params = fake_db.executed[0]
    assert params["test_data"] == (
        '{"tc_id": "tc-1", '
        '"type": "ui", '
        '"steps": ["step1"], '
        '"expected": "expected", '
        '"scenario": {"given": "given"}, '
        '"preconditions": "none"}'
    )
    assert params["jira_key"] == "JIRA-1"
    assert params["created_by"] is None
