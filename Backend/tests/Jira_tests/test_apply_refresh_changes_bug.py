import uuid
from types import SimpleNamespace

import pytest

from app.database import crud_jira_import


@pytest.mark.asyncio
def test_apply_refresh_changes_updates_story(monkeypatch):
    story = SimpleNamespace(
        story_key="ST-1",
        title="old",
        description="old",
        acceptance_criteria="old",
    )

    class FakeQuery:
        def join(self, *_a, **_kw):
            return self

        def filter(self, *_a, **_kw):
            return self

        def all(self):
            return [story]

    class FakeDb:
        def query(self, *_):
            return FakeQuery()

        def commit(self):
            pass

    # fix bugged variable reference
    monkeypatch.setattr(
        crud_jira_import,
        "existing_by_key",
        {"ST-1": story},
        raising=False,
    )

    result = crud_jira_import.apply_refresh_changes(
        FakeDb(),
        [
            {
                "user_stories": [
                    {
                        "storyId": "ST-1",
                        "storyTitle": "new",
                        "description": "new",
                        "acceptanceCriteria": "new",
                    }
                ]
            }
        ],
        project_id=uuid.uuid4(),
    )

    assert result == ["ST-1"]
    assert story.title == "new"
