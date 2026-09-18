from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.exceptions import JiraAuthException, JiraFetchException
from app.services.jiraService import JiraService


@pytest.mark.asyncio
async def test_fetch_jira_http_error(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            raise httpx.HTTPError("boom")

    monkeypatch.setattr(
        "app.services.jiraService.httpx.AsyncClient",
        lambda **kwargs: FakeClient(),
    )

    with pytest.raises(JiraFetchException):
        await JiraService.fetch_jira_data(
            "url",
            "proj",
            "token",
            jira_email="me@example.com",
        )


@pytest.mark.asyncio
async def test_fetch_jira_auth_failure(monkeypatch):
    class FakeResponse:
        status_code = 401

        def raise_for_status(self):
            pass

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.jiraService.httpx.AsyncClient",
        lambda **kwargs: FakeClient(),
    )

    with pytest.raises(JiraAuthException):
        await JiraService.fetch_jira_data(
            "url",
            "proj",
            "token",
            jira_email="me@example.com",
        )


@pytest.mark.asyncio
async def test_push_bulk_to_jira_http_error(monkeypatch):
    from unittest.mock import MagicMock

    service = JiraService(db=MagicMock())

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            raise httpx.HTTPError("boom")

    monkeypatch.setattr(
        "app.services.jiraService.httpx.AsyncClient",
        lambda **kwargs: FakeClient(),
    )

    # push_bulk_to_jira now requires user_story_id, jira_url, project_key, api_token
    success, failed = await service.push_bulk_to_jira(
        [
            {
                "id": "TC-1",
                "title": "Title",
                "priority": "High",
                "steps": "",
                "expected": "",
            }
        ],
        "standard",
        user_story_id="US-1",
        jira_url="https://jira.example.com",
        project_key="PROJ",
        api_token="tok",
        jira_email="me@example.com",
    )

    assert success == []
    assert len(failed) == 1


@pytest.mark.asyncio
async def test_service_placeholder():
    mock_service = AsyncMock()
    mock_service.push_to_jira.return_value = {"success": True}

    result = await mock_service.push_to_jira()

    assert result["success"] is True
