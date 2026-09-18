"""Tests for the project-scoped user story database helpers."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from uuid import UUID

from app.database.user_stories_db import get_approved_user_stories_by_project

_PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")


def _story(story_key: str, title: str) -> MagicMock:
    story = MagicMock()
    story.story_key = story_key
    story.title = title
    return story


class GetApprovedUserStoriesByProjectTests(unittest.TestCase):
    """Verify the approved-stories-by-project query chain and error handling."""

    def _mock_db_returning(self, stories: list) -> tuple[MagicMock, MagicMock]:
        db = MagicMock()
        chain = db.query.return_value
        chain.join.return_value = chain
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.all.return_value = stories
        return db, chain

    def test_returns_stories_from_query_chain(self) -> None:
        stories = [_story("US-1", "First"), _story("US-2", "Second")]
        db, chain = self._mock_db_returning(stories)

        result = get_approved_user_stories_by_project(db, _PROJECT_ID)

        self.assertEqual(result, stories)
        chain.order_by.assert_called_once()

    def test_returns_empty_list_when_no_approved_stories(self) -> None:
        db, _ = self._mock_db_returning([])

        result = get_approved_user_stories_by_project(db, _PROJECT_ID)

        self.assertEqual(result, [])

    def test_query_is_scoped_to_project_and_approved_status(self) -> None:
        from app.models.epics_model import Epic
        from app.models.user_stories_model import UserStory

        db, chain = self._mock_db_returning([])

        get_approved_user_stories_by_project(db, _PROJECT_ID)

        db.query.assert_called_once_with(UserStory)
        chain.join.assert_called_once()
        join_args = chain.join.call_args.args
        self.assertEqual(join_args[0], Epic)

    def test_raises_and_logs_when_query_fails(self) -> None:
        from app.core.exceptions import DatabaseOperationException

        db = MagicMock()
        db.query.side_effect = RuntimeError("connection lost")

        with self.assertRaises(DatabaseOperationException):
            get_approved_user_stories_by_project(db, _PROJECT_ID)


if __name__ == "__main__":
    unittest.main()
