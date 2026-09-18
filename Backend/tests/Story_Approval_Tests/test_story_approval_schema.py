"""Tests for story approval Pydantic schemas."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.schemas.story_approval import StoryApprovalDecisionRequest, StoryApprovalSubmitRequest


def _epics(story_ids=("STORY-42",)):
    """Build a minimal epics payload carrying the given story keys."""
    return [
        {
            "epicId": "EPIC-1",
            "epicTitle": "Epic 1",
            "user_stories": [
                {
                    "storyId": sid,
                    "storyTitle": f"Title {sid}",
                    "description": "desc",
                    "acceptanceCriteria": "ac",
                    "issue_type": "story",
                }
                for sid in story_ids
            ],
        }
    ]


class StoryApprovalSubmitRequestTests(unittest.TestCase):
    """Validate submit request schema constraints."""

    def test_requires_at_least_one_epic(self) -> None:
        with self.assertRaises(ValidationError):
            StoryApprovalSubmitRequest(
                epics=[],
                project_id="11111111-1111-1111-1111-111111111111",
                reviewer_emails=["reviewer@example.com"],
            )

    def test_validates_email_format(self) -> None:
        with self.assertRaises(ValidationError):
            StoryApprovalSubmitRequest(
                epics=_epics(),
                project_id="11111111-1111-1111-1111-111111111111",
                reviewer_emails=["not-an-email"],
            )

    def test_accepts_valid_payload(self) -> None:
        """Story keys are business keys (e.g. Jira issue keys), not UUIDs."""
        req = StoryApprovalSubmitRequest(
            epics=_epics(),
            project_id="11111111-1111-1111-1111-111111111111",
            reviewer_emails=["reviewer@example.com"],
        )
        story_ids = [s.storyId for e in req.epics for s in e.user_stories]
        self.assertEqual(story_ids, ["STORY-42"])
        self.assertEqual(req.reviewer_emails, ["reviewer@example.com"])

    def test_accepts_multiple_reviewers(self) -> None:
        req = StoryApprovalSubmitRequest(
            epics=_epics(),
            project_id="11111111-1111-1111-1111-111111111111",
            reviewer_emails=["reviewer1@example.com", "reviewer2@example.com"],
        )
        self.assertEqual(
            req.reviewer_emails,
            ["reviewer1@example.com", "reviewer2@example.com"],
        )

    def test_requires_at_least_one_reviewer(self) -> None:
        with self.assertRaises(ValidationError):
            StoryApprovalSubmitRequest(
                epics=_epics(),
                project_id="11111111-1111-1111-1111-111111111111",
                reviewer_emails=[],
            )


class StoryApprovalDecisionRequestTests(unittest.TestCase):
    """Validate decision request schema constraints."""

    def test_rejects_invalid_decision(self) -> None:
        with self.assertRaises(ValidationError):
            StoryApprovalDecisionRequest(decision="maybe")

    def test_accepts_approved(self) -> None:
        req = StoryApprovalDecisionRequest(decision="approved")
        self.assertEqual(req.decision, "approved")

    def test_accepts_rejected(self) -> None:
        req = StoryApprovalDecisionRequest(decision="rejected")
        self.assertEqual(req.decision, "rejected")
